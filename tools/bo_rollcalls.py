"""Bolivia's Asamblea Legislativa Plurinacional, phase 1: members of both
chambers and every proyecto de ley with its status in each chamber. Built 9
October 2026; see docs/bolivia-scope.md for every number behind it.

    python3 tools/bo_rollcalls.py                  # members, bills (current year + recent changes)
    python3 tools/bo_rollcalls.py --backfill       # every Diputados bill record since 2020 (55 pages)
    python3 tools/bo_rollcalls.py --reclassify     # offline, after a taxonomy change

THERE ARE NO ROLL CALLS. The name keeps the country tools' pattern
(tools/us_rollcalls.py, tools/pe_rollcalls.py) so the job, coverage and alert
wiring read the same; but neither chamber publishes how members voted. The
Diputados vote electronically and never release the result per member; the
Senado API's `sesiones` list is empty; the chambers' news reports say "por
mayoria" or "por unanimidad" without names. A bill's movement between
stages is the strongest signal on offer, and that is what this collects.

SOURCES, all open and keyless:

  * Diputados bills: diputados.gob.bo's WordPress REST API, custom post type
    `ley` (5,352 records, December 2020 on). Each carries the bill number,
    description, status (`acf.estado_de_ley`), legislative year and
    committee. Read every week: the current legislative year whole (958
    records on 9 October 2026, 10 pages) and anything else modified in the
    last RECENT_DAYS, so an older bill's promulgation is seen too.
  * Senado bills: the Senado site's own JSON API, apisi.senado.gob.bo/page,
    one list per stage (`ley-tratamiento`, `ley-aprobados`,
    `ley-sancionada`, `ley-promulgada`, `ley-rechazada`, `ley-devuelto`;
    754 records), 100 a page.
  * Members: `wp/v2/diputados` (255 posts: names and role only, no party)
    and the Senado API's `senadores/pleno` (72: 36 titulares and their
    suplentes, with bancada and department).

CLASSIFICATION. `config/taxonomy-es.yaml` when it exists (Chris approves the
Spanish term list first; docs/bolivia-scope.md), otherwise the English
`config/taxonomy.yaml`, which matched none of 6,106 Bolivian titles and is
used only so the plumbing runs. Text and terms are accent-folded before
matching. `config/watchlist-bo.yaml` adds areas by bill key, never by title.

Exit codes: 0 clean; 3 stored what it could and recorded gaps (the job
script publishes that run); anything else, nothing worth publishing.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import tempfile
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import bo_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "bo-rollcalls"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
TAXONOMY_EN = os.path.join(ROOT, "config", "taxonomy.yaml")
BUDGET_S = 1800.0
HIDDEN_AREAS = (11,)   # migration is collated, never campaigned
RECENT_DAYS = 21       # three weekly runs' overlap for older bills that move

DIP = "https://diputados.gob.bo/wp-json/wp/v2"
DIP_FIELDS = "id,modified,slug,link,acf,estado_de_ley,legislatura_de_ley,comision_de_ley"
DIP_MEMBER_FIELDS = "id,modified,slug,link,acf,cargo"
SEN = "https://apisi.senado.gob.bo/page"
SEN_FILES = "https://apisi.senado.gob.bo"
# Senado list -> stage, and how far along it is (a bill sits in two lists for
# a while: 'aprobados' and 'sancionada' overlapped on four bills).
SEN_STAGES = (("ley-tratamiento", "tratamiento", 1), ("ley-aprobados", "aprobados", 2),
              ("ley-devuelto", "devuelto", 3), ("ley-rechazada", "rechazada", 4),
              ("ley-sancionada", "sancionada", 5), ("ley-promulgada", "promulgada", 6))
PER_PAGE = 100


# --- text helpers --------------------------------------------------------------

def fold(text):
    """Accents off, case kept: 'Educación' -> 'Educacion', 'ñ' -> 'n'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def _fold_tree(value):
    if isinstance(value, str):
        return fold(value)
    if isinstance(value, list):
        return [_fold_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: _fold_tree(v) for k, v in value.items()}
    return value


def taxonomy_path():
    return TAXONOMY_ES if os.path.exists(TAXONOMY_ES) else TAXONOMY_EN


def load_taxonomy(path=None):
    """The taxonomy with every term accent-folded, through filter's own loader
    (so guards, vetoes and inner stars behave exactly as elsewhere)."""
    import yaml
    with open(path or taxonomy_path(), "r", encoding="utf-8") as handle:
        raw = _fold_tree(yaml.safe_load(handle))
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as tmp:
        yaml.safe_dump(raw, tmp, allow_unicode=True)
    try:
        return filt.load_taxonomy(tmp.name)
    finally:
        os.unlink(tmp.name)


def empty_watchlist():
    """watchlist-bo is applied by KEY (bo_store.add_watch_areas)."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    print("[gap] " + detail)


def _wp_pages(client, url, slug, log_gap):
    """Every page of a WordPress collection. WordPress answers 400 past the
    last page; a short page is the last one."""
    page, out = 1, []
    while True:
        sep = "&" if "?" in url else "?"
        try:
            recs = client.get_json("{0}{1}per_page={2}&page={3}".format(url, sep, PER_PAGE, page),
                                   FEED, "{0}-p{1}".format(slug, page))
        except FetchError as exc:
            if page > 1 and "400" in str(exc):
                break
            log_gap("{0} page {1}: {2}".format(slug, page, exc))
            return out, False
        out.extend(recs or [])
        if len(recs or []) < PER_PAGE:
            break
        page += 1
    return out, True


# --- members -------------------------------------------------------------------

def parse_dip_member(rec, cargos=None):
    acf = rec.get("acf") if isinstance(rec.get("acf"), dict) else {}
    name = clean(acf.get("nombre") or (rec.get("title") or {}).get("rendered") or rec.get("slug"))
    role = clean(acf.get("Diputado(a)")) or None
    names = [cargos.get(c) for c in (rec.get("cargo") or []) if cargos and cargos.get(c)]
    return {
        "member_key": "diputados/{0}".format(rec["slug"]),
        "chamber": "diputados", "name": name, "party": None, "party_code": None,
        "department": None, "role": ", ".join(names) or role, "titular": None,
        "source_id": rec.get("id"), "link": rec.get("link"),
        "as_of": (rec.get("modified") or "")[:10] or None,
    }


def parse_sen_member(rec):
    bancada = rec.get("bancada") or {}
    first, last = clean(rec.get("nombre")), clean(rec.get("apellidos"))
    titular = {83: 1, 84: 0}.get(rec.get("es_titular"))
    return {
        "member_key": "senado/{0}".format(rec["id"]),
        "chamber": "senado", "name": " ".join(p for p in (first.title(), last.title()) if p),
        "party": clean(bancada.get("nombre")) or None,
        "party_code": fold(clean(bancada.get("sigla"))).upper() or None,
        "department": clean((rec.get("brigada_catalogo") or {}).get("name")) or None,
        "role": clean((rec.get("cargo_directiva_catalogo") or {}).get("name"))
        or ("Senador(a) titular" if titular == 1 else "Senador(a) suplente" if titular == 0 else None),
        "titular": titular, "source_id": rec.get("id"),
        "link": "https://senado.gob.bo/", "as_of": None,
    }


def store_member(conn, m, today):
    conn.execute(
        "INSERT INTO bo_members (member_key, chamber, name, party, party_code, department, role, "
        "titular, source_id, link, as_of, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(member_key) DO UPDATE SET name=excluded.name, party=excluded.party, "
        "party_code=excluded.party_code, department=excluded.department, role=excluded.role, "
        "titular=excluded.titular, source_id=excluded.source_id, link=excluded.link, "
        "as_of=excluded.as_of, last_seen=excluded.last_seen",
        (m["member_key"], m["chamber"], m["name"], m["party"], m["party_code"], m["department"],
         m["role"], m["titular"], m["source_id"], m["link"], m["as_of"], today, today))


def sen_rows(reply):
    """The Senado API wraps lists as {"data": [...]} and pages as
    {"data": {"data": [...], "last_page": n}}."""
    data = reply.get("data", reply) if isinstance(reply, dict) else reply
    if isinstance(data, dict):
        return data.get("data") or [], int(data.get("last_page") or 1), data.get("total")
    return data or [], 1, len(data or [])


def pull_members(conn, client, today, log=print):
    """Both chambers. Returns (stored, gaps)."""
    stored = gaps = 0

    def gap(detail):
        nonlocal gaps
        _gap(conn, today, "members " + detail)
        gaps += 1

    cargos = {}
    try:
        for c in client.get_json(DIP + "/cargo?per_page=100&_fields=id,name", FEED, "dip-cargo"):
            cargos[c["id"]] = clean(c.get("name"))
    except FetchError as exc:
        gap("diputados cargo names: {0}".format(exc))
    recs, _ok = _wp_pages(client, DIP + "/diputados?_fields=" + DIP_MEMBER_FIELDS,
                          "dip-members", gap)
    for rec in recs:
        store_member(conn, parse_dip_member(rec, cargos), today)
        stored += 1
    try:
        rows, _last, _total = sen_rows(client.get_json(SEN + "/senadores/pleno", FEED, "sen-pleno"))
        for rec in rows:
            store_member(conn, parse_sen_member(rec), today)
            stored += 1
    except FetchError as exc:
        gap("senado pleno: {0}".format(exc))
    conn.commit()
    log("bo-rollcalls: {0} member(s) from the two chambers".format(stored))
    return stored, gaps


# --- bills ---------------------------------------------------------------------

def parse_dip_bill(rec, committees=None):
    """A diputados.gob.bo `ley` post -> a bill dict (key from the number,
    falling back to the post id for the 0.7% that print none)."""
    acf = rec.get("acf") if isinstance(rec.get("acf"), dict) else {}
    titulo = clean(acf.get("titulo") or (rec.get("title") or {}).get("rendered"))
    key = bo_store.dip_key(titulo, clean(acf.get("ley_nro")))
    if key is None:
        key = ("DIP-WP {0}".format(rec["id"]), "OTHER", None, None, None)
    bill_key, kind, origin, number, leg = key
    law = None
    ley_nro = clean(acf.get("ley_nro"))
    if kind == "LEY":
        law = bill_key
    elif ley_nro and bo_store.law_key(ley_nro):
        law = bo_store.law_key(ley_nro)[0]
    names = [committees.get(c) for c in (rec.get("comision_de_ley") or [])
             if committees and committees.get(c)]
    file_id = acf.get("archivo_ley")
    return {
        "bill_key": bill_key, "kind": kind, "origin": origin, "number": number,
        "legislatura": leg, "title": clean(acf.get("descripcion")) or None,
        "law_number": law, "dip_status": clean(acf.get("estado_de_ley")) or None,
        "dip_committee": "; ".join(names) or None, "dip_id": rec.get("id"),
        "dip_link": rec.get("link"), "dip_modified": (rec.get("modified") or "")[:19] or None,
        "dip_file": file_id if isinstance(file_id, int) else None,
    }


def parse_sen_bill(rec, stage):
    key = bo_store.sen_key(clean(rec.get("titulo")))
    if key is None:
        key = ("SEN {0}".format(rec["id"]), "OTHER", None, None, None)
    bill_key, kind, origin, number, leg = key
    return {
        "bill_key": bill_key, "kind": kind, "origin": origin, "number": number,
        "legislatura": leg, "title": clean(rec.get("asunto")) or None,
        "law_number": bill_key if kind == "LEY" else None,
        "sen_stage": stage, "sen_id": rec.get("id"),
        "sen_document": rec.get("documento") or None,
    }


def classify_bill(tax, wl, key, title, watch=None):
    res = filt.filter_item(tax, wl, fold(title or ""), title=fold(title or ""))
    return bo_store.add_watch_areas(res, key, wl=watch)


def _note_change(conn, key, today, field, old, new):
    if new is not None and new != old:
        conn.execute("INSERT OR REPLACE INTO bo_bill_changes (bill_key, seen, field, old, new) "
                     "VALUES (?,?,?,?,?)", (key, today, field, old, new))
        return 1
    return 0


def upsert_bill(conn, b, tax, wl, watch, today):
    """Merge one chamber's view of a bill into its row. Returns (areas, moved)."""
    row = conn.execute("SELECT title, dip_status, sen_stage, law_number FROM bo_bills "
                       "WHERE bill_key=?", (b["bill_key"],)).fetchone()
    old_title, old_dip, old_sen, old_law = row if row else (None, None, None, None)
    title = b.get("title") or old_title
    if old_title and b.get("title") and len(old_title) > len(b["title"]):
        title = old_title   # the longest description either chamber gave
    res = classify_bill(tax, wl, b["bill_key"], title, watch)
    if row is None:
        conn.execute(
            "INSERT INTO bo_bills (bill_key, kind, origin, number, legislatura, first_seen) "
            "VALUES (?,?,?,?,?,?)",
            (b["bill_key"], b["kind"], b["origin"], b["number"], b["legislatura"], today))
    sets = {"title": title, "law_number": b.get("law_number") or old_law,
            "areas": bo_store.dumps(res.issue_areas),
            "matched_terms": bo_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
            "tier": res.tier, "last_seen": today}
    for col in ("dip_status", "dip_committee", "dip_id", "dip_link", "dip_modified", "dip_file",
                "sen_stage", "sen_id", "sen_document"):
        if col in b:
            sets[col] = b[col]
    conn.execute("UPDATE bo_bills SET {0} WHERE bill_key=?".format(
        ", ".join("{0}=?".format(c) for c in sets)), list(sets.values()) + [b["bill_key"]])
    moved = 0
    if "dip_status" in b:
        moved += _note_change(conn, b["bill_key"], today, "dip_status", old_dip, b["dip_status"])
    if "sen_stage" in b:
        moved += _note_change(conn, b["bill_key"], today, "sen_stage", old_sen, b["sen_stage"])
    return res.issue_areas, moved


def _latest_per_key(bills):
    """Several posts can carry one key (a PL and its approved PLA text); the
    most recently modified post speaks for the bill, the longest title wins."""
    best = {}
    for b in bills:
        cur = best.get(b["bill_key"])
        if cur is None or (b["dip_modified"] or "") > (cur["dip_modified"] or ""):
            if cur is not None and len(cur.get("title") or "") > len(b.get("title") or ""):
                b = dict(b, title=cur["title"])
            best[b["bill_key"]] = b
        elif len(b.get("title") or "") > len(cur.get("title") or ""):
            cur["title"] = b["title"]
    return list(best.values())


def current_legislatura(client):
    """The legislatura_de_ley term with the latest years in its name
    ('Legislatura 2025-2026' -> id 274 on 9 October 2026), and the committee
    names. Read every run: the year rolls over each November."""
    terms = client.get_json(DIP + "/legislatura_de_ley?per_page=100&_fields=id,name",
                            FEED, "dip-legislaturas")
    best = max(terms, key=lambda t: re.findall(r"\d{4}", t.get("name") or "") or ["0"])
    comms = client.get_json(DIP + "/comision_de_ley?per_page=100&_fields=id,name",
                            FEED, "dip-comisiones")
    return best["id"], clean(best.get("name")), {c["id"]: clean(c.get("name")) for c in comms}


def pull_dip_bills(conn, client, today, tax, wl, watch, backfill=False, log=print, budget=None):
    """Returns (read, ours, moved, gaps)."""
    gaps = 0

    def gap(detail):
        nonlocal gaps
        _gap(conn, today, "diputados bills " + detail)
        gaps += 1

    try:
        leg_id, leg_name, committees = current_legislatura(client)
    except (FetchError, ValueError) as exc:
        gap("taxonomies: {0}".format(exc))
        return 0, 0, 0, gaps
    base = DIP + "/ley?orderby=modified&order=desc&_fields=" + DIP_FIELDS
    recs = []
    if backfill:
        got, _ok = _wp_pages(client, base, "dip-ley-all", gap)
        recs += got
    else:
        got, _ok = _wp_pages(client, base + "&legislatura_de_ley={0}".format(leg_id),
                             "dip-ley-current", gap)
        recs += got
        since = (datetime.date.fromisoformat(today)
                 - datetime.timedelta(days=RECENT_DAYS)).isoformat() + "T00:00:00"
        got, _ok = _wp_pages(client, base + "&modified_after=" + since, "dip-ley-recent", gap)
        recs += got
    if budget is not None and budget.exhausted():
        log(budget.disclose("diputados bills", 0))
    bills = _latest_per_key(parse_dip_bill(r, committees) for r in recs)
    read = ours = moved = 0
    for b in bills:
        areas, m = upsert_bill(conn, b, tax, wl, watch, today)
        read += 1
        ours += on_our_ground(areas)
        moved += m
    conn.commit()
    log("bo-rollcalls: {0} Diputados bill(s) read ({1}), {2} on our ground, {3} status move(s)".format(
        read, leg_name if not backfill else "backfill", ours, moved))
    return read, ours, moved, gaps


def pull_sen_bills(conn, client, today, tax, wl, watch, log=print, budget=None):
    """Every Senado stage list, whole. Returns (read, ours, moved, gaps)."""
    gaps = 0
    found = {}
    for endpoint, stage, rank in SEN_STAGES:
        page, last = 1, 1
        while page <= last:
            if budget is not None and budget.exhausted():
                log(budget.disclose("senado bills", len(found)))
                _gap(conn, today, "budget spent before senado {0} page {1}".format(endpoint, page))
                return 0, 0, 0, gaps + 1
            try:
                reply = client.get_json("{0}/{1}/buscar?per_page={2}&page={3}".format(
                    SEN, endpoint, PER_PAGE, page), FEED, "sen-{0}-p{1}".format(endpoint, page))
            except (FetchError, ValueError) as exc:
                _gap(conn, today, "senado bills {0} page {1}: {2}".format(endpoint, page, exc))
                gaps += 1
                break
            rows, last, _total = sen_rows(reply)
            for rec in rows:
                b = parse_sen_bill(rec, stage)
                cur = found.get(b["bill_key"])
                if cur is None or rank > cur[0]:
                    if cur is not None and len(cur[1].get("title") or "") > len(b.get("title") or ""):
                        b["title"] = cur[1]["title"]
                    found[b["bill_key"]] = (rank, b)
            page += 1
    read = ours = moved = 0
    for _rank, b in found.values():
        areas, m = upsert_bill(conn, b, tax, wl, watch, today)
        read += 1
        ours += on_our_ground(areas)
        moved += m
    conn.commit()
    log("bo-rollcalls: {0} Senado bill(s) read, {1} on our ground, {2} stage move(s)".format(
        read, ours, moved))
    return read, ours, moved, gaps


# --- offline -------------------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    tax = tax if tax is not None else load_taxonomy()
    wl = empty_watchlist()
    watch = bo_store.watchlist()
    changed = 0
    for key, title, areas in conn.execute("SELECT bill_key, title, areas FROM bo_bills").fetchall():
        res = classify_bill(tax, wl, key, title, watch)
        new = bo_store.dumps(res.issue_areas)
        changed += new != (areas or "[]")
        conn.execute("UPDATE bo_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (new, bo_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    conn.commit()
    log("bo-rollcalls: reclassified; {0} bill(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = sum(on_our_ground(json.loads(a or "[]"))
               for (a,) in conn.execute("SELECT areas FROM bo_bills"))
    log("  store: {0} bill(s), {1} on our ground, {2} in both chambers; {3} status change(s) "
        "logged; {4} member(s) ({5} diputados, {6} senado)".format(
            n("SELECT COUNT(*) FROM bo_bills"), ours,
            n("SELECT COUNT(*) FROM bo_bills WHERE dip_id IS NOT NULL AND sen_id IS NOT NULL"),
            n("SELECT COUNT(*) FROM bo_bill_changes"),
            n("SELECT COUNT(*) FROM bo_members"),
            n("SELECT COUNT(*) FROM bo_members WHERE chamber='diputados'"),
            n("SELECT COUNT(*) FROM bo_members WHERE chamber='senado'")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--backfill", action="store_true",
                    help="read every Diputados bill record, not just this year's and recent moves")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    # Both hosts are small Bolivian government servers (one ~4s per page of
    # 100 at our pace): one request a second, never the default 0.2s.
    client.set_host_throttle("diputados.gob.bo", 1.0)
    client.set_host_throttle("apisi.senado.gob.bo", 1.0)
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    tax = load_taxonomy()
    print("bo-rollcalls: taxonomy {0}".format(os.path.basename(taxonomy_path())))
    wl = empty_watchlist()
    watch = bo_store.watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        _n, g = pull_members(conn, client, today)
        gaps += g
    if not args.no_bills:
        *_r, g = pull_dip_bills(conn, client, today, tax, wl, watch, backfill=args.backfill,
                                budget=budget)
        gaps += g
        *_r, g = pull_sen_bills(conn, client, today, tax, wl, watch, budget=budget)
        gaps += g
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
