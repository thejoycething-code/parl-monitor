#!/usr/bin/env python3
"""Italy's regional councils (IT3, 12 October 2026): bills and motions of the
councils with a usable source, into it_reg_acts (src/it_store.py).

    python3 tools/it_regions.py                      # every council below
    python3 tools/it_regions.py --region lom tn      # some of them
    python3 tools/it_regions.py --reclassify         # offline, after a taxonomy change
    python3 tools/it_regions.py --dry-run            # one read per council, store nothing

Scoped, live-probed, in docs/italy-regions-scope.md. Four councils are read;
the other sixteen are listed there with the reason (geo-blocked or timing
out from the UK, a robots.txt that refuses every agent, an Akamai refusal,
search forms only).

  lom  Lombardia. The council's own open data on dati.lombardia.it (Socrata),
       "CRL - Elenco PDL" (8muw-8v6p): every act of the legislature with its
       stage dates (presented, assigned, committee vote, Aula vote, law).
       One SODA query for the current legislature, re-read whole each run.
       Kept: Pdl (regional bills), Plp (bills proposed to Parliament), Pda
       (administrative acts) and Inp (popular initiatives and petitions);
       reports, opinions and appointments are not on our ground.
  tn   Provincia autonoma di Trento (its council is a regional legislature in
       all but name). Open-data XML at /open_data/ (robots.txt disallows
       /opendata/, not this path): disegni di legge, mozioni, ordini del
       giorno and petizioni of the legislature, each file re-read whole.
       Keyed on the council's document id (at_id), because a motion is
       published before it has a number.
  cam  Campania. The council's list of proposte e disegni di legge
       (/leggi-progetti/proposte), newest first, read page by page until the
       legislature changes. No status is published in the list.
  mar  Marche. The council's index of PdL of the legislature
       (iter_degli_atti/pdl/index9.php), ten a page with the outcome
       ("Esito") where there is one.

CLASSIFICATION as the national collector does it (tools/it_rollcalls.py):
config/taxonomy-it.yaml for "it" on the title (plus Trento's subject heading
and Campania's categories), and config/watchlist-it.yaml's `regional`
section BY KEY. Nothing is hand-classified.

STATUS. Lombardia dates every stage, so its status_date is the source's. The
others print only the current status: a run that sees a stored act's status
change stamps the day it saw it (status_seen = 1), and the first sighting of
an act is never a change, so the first run does not report every act as a
stage move.

Exit 0, or 3 when it stored what it could and recorded gaps (the gaps table
and [gap] lines): jobs/it-weekly.sh treats its failure as a [gap] line and
never as the run's.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, it_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "it-regions"
TAXONOMY_IT = os.path.join(ROOT, "config", "taxonomy-it.yaml")
TAXONOMY_COUNTRY = "it"
BUDGET_S = 300

REGIONS = {
    "lom": "Lombardia",
    "tn": "Provincia autonoma di Trento",
    "cam": "Campania",
    "mar": "Marche",
}
ORDER = ("lom", "cam", "mar", "tn")

# --- Lombardia ---------------------------------------------------------------
LOM_LEGISLATURE = "XII"
LOM_SODA = "https://www.dati.lombardia.it/resource/8muw-8v6p.json"
LOM_KINDS = {"Pdl": "Progetto di legge", "Plp": "Proposta di legge al Parlamento",
             "Pda": "Proposta di atto amministrativo",
             "Inp": "Atto di iniziativa popolare"}
LOM_LIMIT = 5000

# --- Trento ------------------------------------------------------------------
TN_BASE = "https://www.consiglio.provincia.tn.it/open_data/{0}_opendata.xml"
TN_KINDS = ("DDL", "MOZ", "ODG", "PET")

# --- Campania ----------------------------------------------------------------
CAM_LIST = "https://www.cr.campania.it/leggi-progetti/proposte"
CAM_LEGISLATURE = "XII"
CAM_MAX_PAGES = 15

# --- Marche ------------------------------------------------------------------
MAR_LEGISLATURE = "XII"
MAR_LIST = ("https://www.consiglio.marche.it/banche_dati_e_documentazione/iter_degli_atti/"
            "pdl/index9.php")
MAR_PAGE = 10
MAR_MAX_PAGES = 20


# --- small helpers -------------------------------------------------------------

def text(s):
    """Tags dropped, entities decoded, whitespace folded."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def unquote_title(s):
    """Lombardia wraps every title in quotes, straight or curly."""
    s = (s or "").strip()
    s = re.sub(r'^[\s"“”«]+', "", s)
    s = re.sub(r'[\s"“”»]+\.?$', "", s)
    return s.strip()


def iso(s):
    """'2026-10-02T00:00:00.000', '2026-10-02' or '08/10/2026' -> '2026-10-02'."""
    s = (s or "").strip()
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)", s)
    if m:
        return "-".join(m.groups())
    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", s)
    if m:
        return "{2}-{1}-{0}".format(*m.groups())
    return None


def _name(signatory):
    """Lombardia's '-704-Nicola DI MARCO' -> 'Nicola DI MARCO'."""
    return re.sub(r"^-\d+-", "", (signatory or "").strip())


# --- parsers (pure: text in, acts out) -----------------------------------------

def lom_url(leg=LOM_LEGISLATURE):
    where = "legislatura='{0}' AND tipo_atto in({1})".format(
        leg, ",".join("'{0}'".format(k) for k in LOM_KINDS))
    return LOM_SODA + "?" + urllib.parse.urlencode(
        {"$where": where, "$limit": LOM_LIMIT, "$order": "id_atto"})


def parse_lombardia(rows):
    """Acts from the SODA rows (a list of dicts)."""
    out = []
    for r in rows:
        kind = r.get("tipo_atto")
        if kind not in LOM_KINDS or not r.get("id_atto"):
            continue
        leg = r.get("legislatura") or LOM_LEGISLATURE
        stages = [("presented", iso(r.get("data_presentazione")), None),
                  ("assigned", iso(r.get("data_assegnazione_referente")), None),
                  ("committee", iso(r.get("data_votazione_com_commissione_referente_o_redigente_o_deliberante")),
                   r.get("esito_votazione_com_referente_o_redigente_o_deliberante")),
                  ("aula", iso(r.get("data_votazione_aula")), r.get("esito_votazione_aula")),
                  ("law", iso(r.get("data_lr")), None)]
        dated = [d for _, d, _ in stages if d]
        status = r.get("stato") or None
        bits = [status] if status else []
        if r.get("esito_votazione_aula"):
            bits.append("Aula: {0}".format(r["esito_votazione_aula"].lower()))
        elif r.get("esito_votazione_com_referente_o_redigente_o_deliberante"):
            bits.append("commissione: {0}".format(
                r["esito_votazione_com_referente_o_redigente_o_deliberante"].lower()))
        if r.get("tipo_chiusura"):
            bits.append(r["tipo_chiusura"].lower())
        law = None
        if r.get("n_lr") and r.get("data_lr"):
            law = "l.r. {0}/{1}".format(str(r["n_lr"]).split(".")[0], iso(r["data_lr"])[:4])
        first = _name(r.get("primo_firmatario"))
        signers = [_name(x) for x in (r.get("firmatari") or "").split(";") if x.strip()]
        initiative = first or None
        if first and len(signers) > 1:
            initiative = "{0} and {1} other(s)".format(first, len(signers) - 1)
        elif not first and r.get("tipo_iniziativa"):
            initiative = re.sub(r"^\d+_", "", r["tipo_iniziativa"]).capitalize()
        out.append({
            "key": "lom/{0}/{1}".format(leg, r["id_atto"].rsplit("-", 1)[0]),
            "region": "lom", "kind": kind, "legislature": leg, "number": r.get("n_atto"),
            "label": "{0} n. {1}/{2}".format(LOM_KINDS[kind], r.get("n_atto"), leg),
            "title": unquote_title(r.get("oggetto")), "presented": iso(r.get("data_presentazione")),
            "status": "; ".join(bits) or None, "status_date": max(dated) if dated else None,
            "initiative": initiative,
            "committee": r.get("com_referente_co_referente_redigente_o_deliberante") or None,
            "law": law, "subject": None, "url": r.get("link_atto_bancadati") or None})
    return out


def _tn_text(el, tag):
    got = el.find(tag)
    return re.sub(r"\s+", " ", got.text or "").strip() if got is not None and got.text else ""


def parse_trento(raw, kind=None):
    """Acts from one of Trento's open-data XML files (bytes or str)."""
    if isinstance(raw, str):
        raw = raw.encode("iso-8859-1", "replace")
    root = ET.fromstring(raw)
    out = []
    for a in root.findall("atto"):
        k = _tn_text(a, "tipo_atto") or kind
        url = _tn_text(a, "url")
        m = re.search(r"at_id=(\d+)", url)
        if not m:
            continue
        leg = _tn_text(a, "legislatura") or "XVII"
        status = re.sub(r"^\(stato\)\s*", "", _tn_text(a, "stato_corrente")) or None
        esito = _tn_text(a, "esito")
        if esito and status and esito.lower() not in status.lower():
            status = "{0}; {1}".format(status, esito)
        mat = a.find("materia_principale")
        subject = _tn_text(mat, "voce") if mat is not None else ""
        ddl = a.find("disegno_di_legge")
        title = _tn_text(a, "oggetto")
        if ddl is not None and _tn_text(ddl, "rappresentazione"):
            subject = "{0}; on {1}".format(subject, _tn_text(ddl, "rappresentazione")).strip("; ")
        out.append({
            "key": "tn/{0}/at{1}".format(leg, m.group(1)), "region": "tn", "kind": k,
            "legislature": leg, "number": _tn_text(a, "numero_atto") or None,
            "label": _tn_text(a, "rappresentazione") or k, "title": title,
            "presented": iso(_tn_text(a, "data_presentazione")), "status": status,
            "status_date": None, "initiative": _tn_text(a, "primo_firmatario") or None,
            "committee": _tn_text(a, "commissione_competente") or None, "law": None,
            "subject": subject or None, "url": url})
    return out


_CAM_FIELD = re.compile(r'views-label-(value(?:-\d)?)">[^<]*</strong>\s*<span class="field-content">(.*?)</span>',
                        re.S)


def parse_campania(page):
    """Acts from one page of Campania's list."""
    out = []
    for li in re.findall(r'<li class="views-row.*?</li>', page, re.S):
        f = {k: text(v) for k, v in _CAM_FIELD.findall(li)}
        link = re.search(r'href="(/leggi-progetti/proposte/dettaglio-documento\?id=(\d+))"', li)
        if not link:
            continue
        leg = f.get("value-5") or None
        number = f.get("value") or None
        signers = ", ".join(x.strip() for x in (f.get("value-3") or "").split(",") if x.strip())
        out.append({
            "key": "cam/{0}/{1}".format(leg or "?", link.group(2)), "region": "cam",
            "kind": "PDL", "legislature": leg, "number": number,
            "label": "Proposta di legge n. {0}/{1}".format(number, leg) if number else "Proposta di legge",
            "title": f.get("value-2") or "", "presented": iso(f.get("value-1")),
            "status": None, "status_date": None, "initiative": signers or None,
            "committee": None, "law": None, "subject": f.get("value-6") or None,
            "url": "https://www.cr.campania.it" + html.unescape(link.group(1))})
    return out


def parse_marche(page, leg=MAR_LEGISLATURE):
    """Acts from one page of the Marche council's PdL index."""
    out = []
    for row in re.findall(r"<tr class='altrow\d'>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 4:
            continue
        link = re.search(r'href="(scheda9\.php\?id=(\d+))"', cells[2])
        # '72/26 del 08/10/2026'; a statutory bill reads '65/26 PDLS del ...'.
        m = re.match(r"(\d+)/(\d\d)\s*([A-Z]*)\s*del\s*(\d\d/\d\d/\d{4})", text(cells[0]))
        if not link or not m:
            continue
        status = text(cells[3]) or None
        # An enacted bill's outcome links its law: 'Legge n. 6 del 22/06/2026'.
        law = re.search(r"Legge n\. (\d+) del \d\d/\d\d/(\d{4})", status or "")
        statutory = m.group(3) == "PDLS"
        out.append({
            "key": "mar/{0}/pdl-{1}".format(leg, m.group(1)), "region": "mar",
            "kind": m.group(3) or "PDL", "legislature": leg, "number": m.group(1),
            "label": "Proposta di legge {0}n. {1}/{2}".format(
                "statutaria " if statutory else "", m.group(1), leg),
            "title": text(cells[2]), "presented": iso(m.group(4)), "status": status,
            "status_date": None, "initiative": text(cells[1]) or None, "committee": None,
            "law": "l.r. {0}/{1}".format(*law.groups()) if law else None, "subject": None,
            "url": MAR_LIST.rsplit("/", 1)[0] + "/" + link.group(1)})
    return out


# --- classification and storing --------------------------------------------------

def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, wl, a, watch_path=None):
    res = filt.filter_item(tax, wl, a.get("title") or "", a.get("subject") or "",
                           title=a.get("title") or "")
    return it_store.add_watch_areas(res, a["key"], watch_path)


def store_act(conn, a, res, today):
    """Insert or update one act. Returns 'new', 'moved' or 'same'."""
    old = conn.execute("SELECT status, status_date, status_seen FROM it_reg_acts WHERE act_key=?",
                       (a["key"],)).fetchone()
    status_date, seen = a.get("status_date"), 0
    state = "new" if old is None else "same"
    if old is not None:
        if a.get("status_date"):
            if a["status_date"] != old[1]:
                state = "moved"
        elif (a.get("status") or None) != (old[0] or None):
            status_date, seen, state = today, 1, "moved"
        else:
            status_date, seen = old[1], old[2] or 0
    conn.execute(
        "INSERT INTO it_reg_acts (act_key, region, kind, legislature, number, label, title, "
        "presented, status, status_date, status_seen, initiative, committee, law, subject, url, "
        "areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(act_key) DO UPDATE SET kind=excluded.kind, number=excluded.number, "
        "label=excluded.label, title=excluded.title, presented=excluded.presented, "
        "status=excluded.status, status_date=excluded.status_date, "
        "status_seen=excluded.status_seen, initiative=excluded.initiative, "
        "committee=excluded.committee, law=excluded.law, subject=excluded.subject, "
        "url=excluded.url, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (a["key"], a["region"], a["kind"], a.get("legislature"), a.get("number"), a.get("label"),
         a.get("title"), a.get("presented"), a.get("status"), status_date, seen,
         a.get("initiative"), a.get("committee"), a.get("law"), a.get("subject"), a.get("url"),
         it_store.dumps(res.issue_areas),
         it_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))
    return state


def store_all(conn, acts, tax, wl, today):
    """(read, on our ground, new, moved)."""
    n = ours = new = moved = 0
    for a in acts:
        res = classify(tax, wl, a)
        state = store_act(conn, a, res, today)
        n += 1
        if [x for x in (res.issue_areas or []) if x != 11]:
            ours += 1
        new += state == "new"
        moved += state == "moved"
    conn.commit()
    return n, ours, new, moved


def _gap(conn, today, detail, log=print):
    log("  [gap] " + detail)
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    conn.commit()


# --- fetching --------------------------------------------------------------------

def fetch_lombardia(client, log=print, budget=None):
    rows = client.get_json(lom_url(), FEED, "lombardia-pdl")
    return parse_lombardia(rows or []), 0


def fetch_trento(client, log=print, budget=None):
    acts, gaps = [], 0
    for kind in TN_KINDS:
        if budget is not None and budget.exhausted():
            log(budget.disclose("Trento files", len(acts)))
            return acts, gaps + 1
        raw = client.get_bytes(TN_BASE.format(kind), FEED, "trento-" + kind.lower())
        acts += parse_trento(raw, kind)
    return acts, gaps


def fetch_campania(client, log=print, budget=None):
    acts = []
    for page in range(CAM_MAX_PAGES):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Campania pages", page))
            return acts, 1
        url = CAM_LIST + ("?page={0}".format(page) if page else "")
        got = parse_campania(client.get_text(url, FEED, "campania-p{0}".format(page),
                                             headers={"Accept": "text/html"}))
        mine = [a for a in got if a["legislature"] == CAM_LEGISLATURE]
        acts += mine
        if not got or len(mine) < len(got):
            break
    return acts, 0


def fetch_marche(client, log=print, budget=None):
    acts = []
    for page in range(MAR_MAX_PAGES):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Marche pages", page))
            return acts, 1
        url = MAR_LIST + ("?start={0}&leg={1}".format(page * MAR_PAGE, MAR_LEGISLATURE)
                          if page else "")
        page_text = client.get_text(url, FEED, "marche-p{0}".format(page),
                                    fallback_encoding="cp1252")
        acts += parse_marche(page_text)
        if len(re.findall(r"<tr class='altrow\d'>", page_text)) < MAR_PAGE:
            break
    return acts, 0


FETCH = {"lom": fetch_lombardia, "tn": fetch_trento, "cam": fetch_campania,
         "mar": fetch_marche}


def reclassify(conn, tax, watch_path=None):
    wl = empty_watchlist()
    n = 0
    for r in conn.execute("SELECT act_key, title, subject FROM it_reg_acts").fetchall():
        res = classify(tax, wl, {"key": r[0], "title": r[1], "subject": r[2]}, watch_path)
        conn.execute("UPDATE it_reg_acts SET areas=?, matched_terms=?, tier=? WHERE act_key=?",
                     (it_store.dumps(res.issue_areas),
                      it_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, r[0]))
        n += 1
    conn.commit()
    print("it-regions: reclassified {0} regional act(s)".format(n))


def summary(conn):
    for region in ORDER:
        row = conn.execute("SELECT COUNT(*), SUM(CASE WHEN areas NOT IN ('[]','[11]') THEN 1 "
                           "ELSE 0 END), MAX(presented) FROM it_reg_acts WHERE region=?",
                           (region,)).fetchone()
        print("it-regions: {0}: {1} act(s) stored, {2} on our ground, newest presented {3}".format(
            REGIONS[region], row[0], row[1] or 0, row[2] or "-"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--region", nargs="*", choices=ORDER, help="default: every council")
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="read each council once, print what was parsed, store nothing")
    args = ap.parse_args(argv)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    regions = args.region or list(ORDER)
    if args.dry_run:
        for region in regions:
            try:
                acts, _ = FETCH[region](client, budget=drain.Budget(60))
            except (FetchError, ValueError, ET.ParseError) as e:
                print("it-regions: {0}: FAILED {1}".format(REGIONS[region], e))
                continue
            newest = max((a["presented"] or "" for a in acts), default="-")
            print("it-regions: {0}: {1} act(s), newest presented {2}".format(
                REGIONS[region], len(acts), newest))
        return 0
    if not os.path.exists(TAXONOMY_IT):
        print("it-regions: config/taxonomy-it.yaml is missing; nothing classified")
        return 1
    conn = db.init_db(db.connect(args.db))
    tax = filt.load_taxonomy(TAXONOMY_IT, country=TAXONOMY_COUNTRY)
    print("it-regions: taxonomy taxonomy-it.yaml (v{0})".format(tax.version))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    for region in regions:
        if budget.exhausted():
            print(budget.disclose("councils", regions.index(region)))
            _gap(conn, today, "{0}: time budget spent before it was read".format(REGIONS[region]))
            gaps += 1
            continue
        try:
            acts, g = FETCH[region](client, budget=budget)
        except (FetchError, ValueError, ET.ParseError) as e:
            _gap(conn, today, "{0}: not read ({1})".format(REGIONS[region], str(e)[:200]))
            gaps += 1
            continue
        if g:
            _gap(conn, today, "{0}: read in part (time budget)".format(REGIONS[region]))
        gaps += g
        if not acts:
            _gap(conn, today, "{0}: the source answered with no acts".format(REGIONS[region]))
            gaps += 1
            continue
        n, ours, new, moved = store_all(conn, acts, tax, wl, today)
        print("it-regions: {0}: {1} act(s) read, {2} on our ground, {3} new to the store, "
              "{4} with a changed status".format(REGIONS[region], n, ours, new, moved))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
