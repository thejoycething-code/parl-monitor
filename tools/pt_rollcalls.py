#!/usr/bin/env python3
"""Portugal: deputies, initiatives and plenary votes of the Assembleia da Republica.

    python3 tools/pt_rollcalls.py                     # the current legislature
    python3 tools/pt_rollcalls.py --legislature XVI   # an earlier one
    python3 tools/pt_rollcalls.py --reclassify        # re-derive areas, offline
    python3 tools/pt_rollcalls.py --db /tmp/pt.db     # anywhere but the store
    python3 tools/pt_rollcalls.py --file ini.json     # a dump already on disk

PHASE 1 (9 October 2026). See docs/portugal-scope.md. One source, open,
keyless and official: the Assembleia's open-data dumps (Dados Abertos), one
JSON file per dataset per legislature.

  * Iniciativas<LEG>_json.txt -- every initiative of the legislature with
    its whole history (IniEventos), and every vote taken on it inside the
    event that took it. 97 MB for the XVII legislature, 82 seconds from the
    laptop, 5.6 MB gzipped in the raw archive. Re-read whole every week.
  * InformacaoBase<LEG>_json.txt -- the deputies (effective and substitute),
    their group and circle. 0.6 MB.

THE DOWNLOAD URLS ARE NOT GUESSABLE. Each file sits behind an encrypted
`path=` token (app.parlamento.pt/webutils/docs/doc.txt?path=...&fich=...).
The token was the same on every visit on 9 October 2026, but nothing
promises that, so the collector finds it each run: the dataset page links a
folder per legislature, and the folder page links the file. Three requests
per dataset, about 370 KB of HTML each.

PORTUGAL VOTES BY GROUP. See src/pt_store.py: the record is each group's
position, plus the names of deputies who broke from it. parse_detail reads
the record's `detalhe` markup into those two layers and nothing more.

CLASSIFICATION. config/taxonomy-pt.yaml when it exists (Chris approves the
term list proposed in docs/portugal-scope.md first; it is not generated
here), otherwise the shared English taxonomy, which is blind to Portuguese:
5 of the 2,328 initiatives of the XVII legislature, all of them because
"Chat Control" is written in English. config/watchlist-pt.yaml, applied by
initiative KEY, carries what matters meanwhile. --reclassify re-derives
everything offline the day the Portuguese file lands.

EXIT CODES. 0 clean; 3 when it stored what it could and recorded gaps (the
weekly publishes that run, as jobs/au-weekly.sh does); 1 when it could not
read the initiatives at all.

Separation guarantee: writes pt_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, pt_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "pt-rollcalls"
CURRENT_LEGISLATURE = "XVII"
TAXONOMY_PT = os.path.join(ROOT, "config", "taxonomy-pt.yaml")
TAXONOMY_EN = os.path.join(ROOT, "config", "taxonomy.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "pt"
SITE = "https://www.parlamento.pt"
DATASETS = {
    "initiatives": ("/Cidadania/Paginas/DAIniciativas.aspx", "Iniciativas"),
    "members": ("/Cidadania/Paginas/DAInformacaoBase.aspx", "InformacaoBase"),
}
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)
POSITIONS = {"a favor": "A Favor", "contra": "Contra", "abstenção": "Abstenção",
             "abstencao": "Abstenção", "ausência": "Ausente", "ausencia": "Ausente"}
# The record's 'Veto (Receção)' is one event per veto received; the
# Constitutional Court's rulings reach the Assembleia this way (a veto for
# unconstitutionality), not as a phase of their own.
VETO_PHASE = "Veto (Receção)"
LAW_PHASE = "Lei (Publicação DR)"


def taxonomy_path():
    return TAXONOMY_PT if os.path.exists(TAXONOMY_PT) else TAXONOMY_EN


def ini_key(leg, ini_type, number):
    return "{0}/{1}/{2}".format(leg, ini_type, int(number))


def division_key(leg, vote_id):
    return "{0}/{1}".format(leg, int(vote_id))


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


# --- finding the files -------------------------------------------------------

_ANCHOR = re.compile(r'<a [^>]*href="([^"]+)"[^>]*>([^<]{0,160})', re.I)


def anchors(page):
    """[(href, text)] with entities decoded, in page order."""
    return [(html.unescape(h), html.unescape(t).strip()) for h, t in _ANCHOR.findall(page or "")]


def folder_link(page, leg):
    """The dataset page's link to one legislature's folder, or None."""
    want = "{0} Legislatura".format(leg)
    for href, text in anchors(page):
        if text == want and "Path=" in href:
            return href if href.startswith("http") else SITE + href
    return None


def json_link(page, stem, leg):
    """The folder page's link to <stem><leg>_json.txt, or None. The exact
    filename is matched, so 'IniciativasXVII' never finds 'IniciativasXVI'."""
    want = "{0}{1}_json.txt".format(stem, leg)
    for href, text in anchors(page):
        if "webutils/docs/" in href and text == want:
            return href
    return None


def fetch_dataset(client, name, leg):
    """The parsed JSON of one dataset for one legislature. Raises FetchError
    or ValueError (a page that no longer links what it did)."""
    page_path, stem = DATASETS[name]
    page = client.get_text(SITE + page_path, FEED, "page-" + name, archive=False)
    folder = folder_link(page, leg)
    if not folder:
        raise ValueError("{0}: no '{1} Legislatura' folder on {2}".format(name, leg, page_path))
    listing = client.get_text(folder, FEED, "folder-{0}-{1}".format(name, leg), archive=False)
    url = json_link(listing, stem, leg)
    if not url:
        raise ValueError("{0}: folder lists no {1}{2}_json.txt".format(name, stem, leg))
    raw = client.get_bytes(url, FEED, "{0}-{1}".format(name, leg), timeout=300)
    return json.loads(raw.decode("utf-8-sig"))


# --- the vote record ---------------------------------------------------------

_BLOCK = re.compile(r"^(\d+)-(.+)$")
_PERSON = re.compile(r"^(.+?)\s*\(([^()]+)\)$")


def parse_detail(detail):
    """'A Favor: <I>PSD</I>, <I> 13-PS</I>, <I> Pedro Vaz (PS)</I><BR>Contra: ...'
    -> (groups, people).

    groups: [(party, position, members)] -- members None for a whole group,
            N for a breakaway block printed as 'N-PARTY'.
    people: [(name, party, position)] -- deputies named in the record.
    Anything the parser does not recognise is returned as a group so it is
    stored rather than lost; an unknown label is kept verbatim."""
    groups, people = [], []
    for seg in re.split(r"(?i)<br\s*/?>", detail or ""):
        text = re.sub(r"<[^>]+>", "", seg).strip()
        if ":" not in text:
            continue
        label, rest = text.split(":", 1)
        position = POSITIONS.get(label.strip().lower(), label.strip())
        for item in (i.strip() for i in rest.split(",")):
            if not item:
                continue
            person = _PERSON.match(item)
            block = _BLOCK.match(item)
            if person:
                people.append((person.group(1).strip(), person.group(2).strip(), position))
            elif block:
                groups.append((block.group(2).strip(), position, int(block.group(1))))
            else:
                groups.append((item, position, None))
    return groups, people


def _votes(event):
    v = event.get("Votacao") or []
    return v if isinstance(v, list) else [v]


def parse_initiative(rec):
    """One record of the Iniciativas dump -> a plain dict, votes included."""
    leg, itype, nr = rec.get("IniLeg"), rec.get("IniTipo"), rec.get("IniNr")
    if not (leg and itype and nr):
        return None
    events = sorted(rec.get("IniEventos") or [],
                    key=lambda e: (e.get("DataFase") or "", int(e.get("EvtId") or 0)))
    other = rec.get("IniAutorOutros") or {}
    out = {
        "key": ini_key(leg, itype, nr), "ini_id": int(rec["IniId"]) if rec.get("IniId") else None,
        "legislature": leg, "type": itype, "type_desc": rec.get("IniDescTipo"),
        "number": int(nr), "title": (rec.get("IniTitulo") or "").strip() or None,
        "epigraph": (rec.get("IniEpigrafe") or "").strip() or None,
        "authors_gp": sorted({g.get("GP") for g in (rec.get("IniAutorGruposParlamentares") or [])
                              if g.get("GP")}),
        "author_other": other.get("nome"),
        "authors": [(int(a["idCadastro"]), a.get("GP")) for a in (rec.get("IniAutorDeputados") or [])
                    if a.get("idCadastro")],
        "entered": events[0].get("DataFase") if events else None,
        "latest_phase": events[-1].get("Fase", "").strip() if events else None,
        "latest_phase_at": events[-1].get("DataFase") if events else None,
        "law_published": next((e.get("DataFase") for e in events if e.get("Fase") == LAW_PHASE), None),
        "vetoes": sum(1 for e in events if e.get("Fase") == VETO_PHASE),
        "text_url": rec.get("IniLinkTexto"),
        "divisions": [],
    }
    for e in events:
        for v in _votes(e):
            if not v.get("id"):
                continue
            groups, people = parse_detail(v.get("detalhe"))
            absent = v.get("ausencias") or []
            out["divisions"].append({
                "key": division_key(leg, v["id"]), "vote_id": int(v["id"]),
                "legislature": leg, "date": v.get("data") or e.get("DataFase"),
                "phase": (e.get("Fase") or "").strip() or None,
                "description": (v.get("descricao") or "").strip() or None,
                "result": v.get("resultado"), "unanimous": 1 if v.get("unanime") else 0,
                "meeting": v.get("reuniao"), "meeting_type": v.get("tipoReuniao"),
                "detail": v.get("detalhe"),
                "absent": absent if isinstance(absent, list) else [absent],
                "groups": groups, "people": people})
    return out


# --- classify and store ------------------------------------------------------

def empty_watchlist():
    """The Portugal watchlist is applied by KEY (pt_store.add_watch_areas)."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify_initiative(tax, wl, ini):
    res = filt.filter_item(tax, wl, ini["title"] or "", ini["epigraph"] or "",
                           title=ini["title"] or "")
    return pt_store.add_watch_areas(res, ini["key"])


def classify_division(tax, wl, d, ini_areas):
    own = filt.filter_item(tax, wl, d.get("description") or "", title="")
    return own, sorted(set(own.issue_areas or []) | set(ini_areas or []))


def store_initiative(conn, ini, res, today):
    conn.execute(
        "INSERT INTO pt_initiatives (ini_key, ini_id, legislature, ini_type, type_desc, number, "
        "title, epigraph, authors_gp, author_other, entered, latest_phase, latest_phase_at, "
        "law_published, vetoes, text_url, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(ini_key) DO UPDATE SET ini_id=excluded.ini_id, title=excluded.title, "
        "epigraph=excluded.epigraph, authors_gp=excluded.authors_gp, "
        "author_other=excluded.author_other, entered=excluded.entered, "
        "latest_phase=excluded.latest_phase, latest_phase_at=excluded.latest_phase_at, "
        "law_published=excluded.law_published, vetoes=excluded.vetoes, "
        "text_url=excluded.text_url, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (ini["key"], ini["ini_id"], ini["legislature"], ini["type"], ini["type_desc"],
         ini["number"], ini["title"], ini["epigraph"], pt_store.dumps(ini["authors_gp"]),
         ini["author_other"], ini["entered"], ini["latest_phase"], ini["latest_phase_at"],
         ini["law_published"], ini["vetoes"], ini["text_url"], pt_store.dumps(res.issue_areas),
         pt_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier,
         today, today))
    for cad, party in ini["authors"]:
        conn.execute("INSERT OR REPLACE INTO pt_authors (ini_key, cad_id, party) VALUES (?,?,?)",
                     (ini["key"], cad, party))


class Resolver:
    """Name + party -> cad_id, from pt_members. A name held by one deputy
    resolves on the name; a name held by several resolves only if the party
    tells them apart. Otherwise None: never a guess."""

    def __init__(self, conn):
        self.by_name = {}
        for cad, name, party in conn.execute("SELECT cad_id, name, party FROM pt_members"):
            self.by_name.setdefault((name or "").strip().lower(), []).append((cad, party))

    def get(self, name, party):
        hits = self.by_name.get((name or "").strip().lower(), [])
        if len(hits) == 1:
            return hits[0][0]
        same = [c for c, p in hits if p == party]
        return same[0] if len(same) == 1 else None


def store_division(conn, d, ini_key_, ini_areas, tax, wl, resolver, today):
    own, areas = classify_division(tax, wl, d, ini_areas)
    conn.execute(
        "INSERT INTO pt_divisions (division_key, vote_id, legislature, ini_key, date, phase, "
        "description, result, unanimous, meeting, meeting_type, detail, absent_groups, "
        "own_areas, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET ini_key=excluded.ini_key, date=excluded.date, "
        "phase=excluded.phase, description=excluded.description, result=excluded.result, "
        "unanimous=excluded.unanimous, detail=excluded.detail, "
        "absent_groups=excluded.absent_groups, own_areas=excluded.own_areas, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (d["key"], d["vote_id"], d["legislature"], ini_key_, d["date"], d["phase"],
         d["description"], d["result"], d["unanimous"], d["meeting"], d["meeting_type"],
         d["detail"], pt_store.dumps(d["absent"]), pt_store.dumps(own.issue_areas),
         pt_store.dumps(areas), pt_store.dumps(own.matched_terms), own.tier, today, today))
    # The record is replaced whole: a corrected detalhe must not leave the
    # old positions behind.
    conn.execute("DELETE FROM pt_group_votes WHERE division_key=?", (d["key"],))
    conn.execute("DELETE FROM pt_votes WHERE division_key=?", (d["key"],))
    for party, position, members in d["groups"]:
        conn.execute("INSERT OR REPLACE INTO pt_group_votes (division_key, party, position, "
                     "members) VALUES (?,?,?,?)", (d["key"], party, position, members))
    for party in d["absent"]:
        conn.execute("INSERT OR IGNORE INTO pt_group_votes (division_key, party, position, "
                     "members) VALUES (?,?,?,NULL)", (d["key"], party, "Ausente"))
    unresolved = 0
    for name, party, position in d["people"]:
        cad = resolver.get(name, party)
        unresolved += cad is None
        conn.execute("INSERT OR REPLACE INTO pt_votes (division_key, name, party, position, "
                     "cad_id) VALUES (?,?,?,?,?)", (d["key"], name, party, position, cad))
    return areas, unresolved


def store_records(conn, records, today, tax=None, wl=None, log=print):
    """Every initiative and its votes. Returns (initiatives, ours, divisions,
    divisions ours, unresolved names)."""
    tax = tax if tax is not None else filt.load_taxonomy(taxonomy_path(), country=TAXONOMY_COUNTRY)
    wl = wl if wl is not None else empty_watchlist()
    resolver = Resolver(conn)
    n = ours = nd = ours_d = unresolved = 0
    for rec in records or []:
        ini = parse_initiative(rec)
        if not ini:
            continue
        res = classify_initiative(tax, wl, ini)
        store_initiative(conn, ini, res, today)
        n += 1
        ours += on_our_ground(res.issue_areas)
        for d in ini["divisions"]:
            areas, u = store_division(conn, d, ini["key"], res.issue_areas, tax, wl, resolver, today)
            nd += 1
            ours_d += on_our_ground(areas)
            unresolved += u
    conn.commit()
    return n, ours, nd, ours_d, unresolved


# --- members -----------------------------------------------------------------

def _latest(rows, start):
    rows = [r for r in (rows or []) if r]
    return sorted(rows, key=lambda r: r.get(start) or "")[-1] if rows else {}


def parse_members(data):
    """InformacaoBase -> [member dict]. One row per DepCadId (measured: 1,446
    rows and 1,446 ids for the XVII, effective deputies and substitutes)."""
    out = []
    for dep in (data or {}).get("Deputados") or []:
        if dep.get("DepCadId") is None:
            continue
        gp = _latest(dep.get("DepGP"), "gpDtInicio")
        sit = _latest(dep.get("DepSituacao"), "sioDtInicio")
        out.append({"cad_id": int(dep["DepCadId"]),
                    "name": (dep.get("DepNomeParlamentar") or "").strip() or None,
                    "full_name": (dep.get("DepNomeCompleto") or "").strip() or None,
                    "party": gp.get("gpSigla"), "circle": dep.get("DepCPDes"),
                    "situation": sit.get("sioDes"), "legislature": dep.get("LegDes")})
    return out


def store_members(conn, members, today):
    for m in members:
        conn.execute(
            "INSERT INTO pt_members (cad_id, name, full_name, party, circle, situation, "
            "legislature, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(cad_id) DO UPDATE SET name=COALESCE(excluded.name, pt_members.name), "
            "full_name=COALESCE(excluded.full_name, pt_members.full_name), "
            "party=COALESCE(excluded.party, pt_members.party), circle=excluded.circle, "
            "situation=excluded.situation, legislature=excluded.legislature, "
            "last_seen=excluded.last_seen",
            (m["cad_id"], m["name"], m["full_name"], m["party"], m["circle"], m["situation"],
             m["legislature"], today, today))
    conn.commit()
    return len(members)


# --- offline -----------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    """Re-derive initiative areas, then division areas, offline, after a
    taxonomy or watchlist change. Initiatives first: votes inherit from them."""
    tax = tax if tax is not None else filt.load_taxonomy(taxonomy_path(), country=TAXONOMY_COUNTRY)
    wl = empty_watchlist()
    changed_i = changed_d = 0
    for key, title, epigraph, areas in conn.execute(
            "SELECT ini_key, title, epigraph, areas FROM pt_initiatives").fetchall():
        res = classify_initiative(tax, wl, {"key": key, "title": title, "epigraph": epigraph})
        new = pt_store.dumps(res.issue_areas)
        changed_i += new != (areas or "[]")
        conn.execute("UPDATE pt_initiatives SET areas=?, matched_terms=?, tier=? WHERE ini_key=?",
                     (new, pt_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    ini_areas = {k: json.loads(a or "[]") for k, a in
                 conn.execute("SELECT ini_key, areas FROM pt_initiatives")}
    for key, ikey, desc, areas in conn.execute(
            "SELECT division_key, ini_key, description, areas FROM pt_divisions").fetchall():
        own, combined = classify_division(tax, wl, {"description": desc}, ini_areas.get(ikey))
        new = pt_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE pt_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (pt_store.dumps(own.issue_areas), new, pt_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("pt-rollcalls: reclassified under {0}; {1} initiative(s) and {2} vote(s) changed "
        "area".format(os.path.basename(taxonomy_path()), changed_i, changed_d))
    return changed_i, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} initiative(s), {1} on our ground; {2} vote(s), {3} on our ground; "
        "{4} deputy(ies), {5} group position(s), {6} named deputy position(s)".format(
            n("SELECT COUNT(*) FROM pt_initiatives"), ours("pt_initiatives"),
            n("SELECT COUNT(*) FROM pt_divisions"), ours("pt_divisions"),
            n("SELECT COUNT(*) FROM pt_members"), n("SELECT COUNT(*) FROM pt_group_votes"),
            n("SELECT COUNT(*) FROM pt_votes")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", default=CURRENT_LEGISLATURE)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--file", help="read the Iniciativas JSON from this path, not the site")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored initiatives and votes, offline")
    # Accepted for the weekly's sake (jobs/pt-weekly.sh passes it as every
    # job does); the whole pull is five requests, so nothing here is drained.
    ap.add_argument("--budget-seconds", type=float, default=None)
    args = ap.parse_args()
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    leg = args.legislature.upper()
    gaps = 0
    if not args.no_members:
        try:
            members = parse_members(fetch_dataset(client, "members", leg))
            print("pt-rollcalls: {0} deputy(ies), effective and substitute, {1}".format(
                store_members(conn, members, today), leg))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "members {0}: {1}".format(leg, str(exc)[:200]))
            print("  [gap] members {0}: {1}".format(leg, str(exc)[:100]))
            gaps += 1
            conn.commit()
    try:
        if args.file:
            with open(args.file, encoding="utf-8-sig") as fh:
                records = json.load(fh)
        else:
            records = fetch_dataset(client, "initiatives", leg)
    except (FetchError, ValueError, OSError) as exc:
        _gap(conn, today, "initiatives {0}: {1}".format(leg, str(exc)[:200]))
        conn.commit()
        print("  [gap] initiatives {0}: {1}".format(leg, str(exc)[:100]))
        print("pt-rollcalls: no initiatives read; nothing stored")
        conn.close()
        return 1
    n, ours, nd, ours_d, unresolved = store_records(conn, records, today)
    print("pt-rollcalls: {0} initiative(s), {1} on our ground; {2} vote(s), {3} on our "
          "ground ({4})".format(n, ours, nd, ours_d, os.path.basename(taxonomy_path())))
    if unresolved:
        # Not a gap: the name is stored as printed, only the link to a
        # deputy id is missing, and the record itself is complete.
        print("pt-rollcalls: {0} named position(s) not matched to a deputy id".format(unresolved))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
