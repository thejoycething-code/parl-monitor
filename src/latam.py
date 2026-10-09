"""What the Latam monitor reads from each country's store, in one shape.

Shared by tools/latam_monitor.py (the monthly edition) and
tools/latam_alerts.py (the instant alerts), so the two can never disagree
about what counts as news on our ground.

THE EDITION'S COUNTRIES (docs/country-decisions-2026-10-10.md, "Edition
structure"): every Latin American country where CitizenGO works through
CitizenGO Latam. Eleven have a collector and a store (`<cc>_store`,
`tools/<cc>_rollcalls.py`); Costa Rica and Paraguay wait for access (CR1,
PY1); Venezuela has the news-feed note (tools/ve_news.py) and Nicaragua the
gazette check (tools/nic_gaceta.py, prefix `nic`, never `ni`).

AN ITEM is one dict:

    cc, kind, key, date, title, status, areas, tier, watched, url, lines

`title` is the source's own Spanish, verbatim. `kind` is one of KINDS.
`areas` are visible area numbers (migration, area 11, is matched and stored
but never shown, as everywhere in this repo; Chile's CL2). `watched` means
the item's key is in config/watchlist-<cc>.yaml. `lines` are extra English
lines (a vote's tally and party split). Nothing is an item unless the
collector's filter pass (shared taxonomy-es for the country's code, guards
and vetoes, src/filter.py) or the watchlist put it on our ground: raw
keyword hits are never read here.

SCORES (X16: the AI judge stays off). score() runs src/triage.py's stub:
tier 1 or watched scores 2, tier 2 scores 1. It orders items; it is not a
verdict, and no vote carries one.

Read-only on the store.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
# One alert ledger per country (data/latam-alerts/<cc>.json): what was sent,
# each watched item's last status, and the stage moves seen. Per country so
# two countries' jobs (the Mini and a GitHub backup) never edit one file.
LEDGER_DIR = os.path.join(ROOT, "data", "latam-alerts")

# (code, name, chamber line). Order is the edition's order for ties.
COUNTRIES = (
    ("co", "Colombia", "Congreso de la República"),
    ("cl", "Chile", "Congreso Nacional"),
    ("pe", "Peru", "Congreso de la República"),
    ("ec", "Ecuador", "Asamblea Nacional"),
    ("bo", "Bolivia", "Asamblea Legislativa Plurinacional"),
    ("uy", "Uruguay", "Asamblea General"),
    ("py", "Paraguay", "Congreso Nacional"),
    ("gt", "Guatemala", "Congreso de la República"),
    ("pa", "Panama", "Asamblea Nacional"),
    ("hn", "Honduras", "Congreso Nacional"),
    ("sv", "El Salvador", "Asamblea Legislativa"),
    ("do", "Dominican Republic", "Congreso Nacional"),
    ("cr", "Costa Rica", "Asamblea Legislativa"),
    ("ve", "Venezuela", "Asamblea Nacional"),
    ("nic", "Nicaragua", "La Gaceta, Diario Oficial"),
)
NAMES = {c: n for c, n, _ in COUNTRIES}
COLLECTED = ("co", "cl", "pe", "ec", "bo", "uy", "gt", "pa", "hn", "sv", "do")
PENDING = {
    "cr": "waiting on the Asamblea Legislativa to clear access, CR1",
    "py": "waiting on the Senate's IT office to clear access, PY1",
}
HIDDEN_AREAS = (11,)

# English labels, British spelling, for the taxonomy-es area numbers.
AREA_LABELS = {
    1: "abortion", 2: "assisted dying", 3: "gender medicine and children",
    4: "conversion practices", 5: "sex-based rights", 6: "parental rights and education",
    7: "free speech and civil liberties", 8: "religious freedom", 9: "marriage and family",
    10: "surrogacy and embryology", 11: "migration", 12: "prostitution and trafficking",
    13: "organ donation",
}

KINDS = {
    "new": "New bill",
    "moved": "Stage move",
    "updated": "Updated on the register",
    "vote": "Recorded vote",
    "report": "Committee report",
    "agenda": "On the plenary agenda",
    "press": "Congress press item",
    "pedido": "Pedido de informes",
    "law": "Law promulgated",
    "gazette": "Gazette notice",
    "news": "Assembly news item",
}


# --- small helpers --------------------------------------------------------------

def clean(text):
    """One line, no em dashes (CLAUDE.md: rendered editions carry none)."""
    return " ".join((text or "").replace("—", " - ").replace("–", "-").split())


def clip(text, n):
    text = clean(text)
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def areas_of(raw):
    """Visible areas from a JSON list column; [] for NULL or junk."""
    try:
        got = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        return []
    return sorted({int(a) for a in got if str(a).isdigit() and int(a) not in HIDDEN_AREAS})


def area_text(areas):
    return ", ".join(AREA_LABELS.get(a, str(a)) for a in areas)


def day(value):
    return (value or "")[:10]


def rows(conn, sql, params=()):
    """Rows as sqlite3.Row; [] when the table is missing (a store that has
    not run this country's collector yet)."""
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


_WATCH = {}


def watchlist(cc, config_dir=None):
    """{key: entry} from config/watchlist-<cc>.yaml, every section merged
    (bills, divisions, initiatives, expedientes, piezas, watch). {} when the
    country has no file."""
    path = os.path.join(config_dir or CONFIG, "watchlist-{0}.yaml".format(cc))
    if path not in _WATCH:
        out = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            for section in raw.values():
                if isinstance(section, dict):
                    for k, v in section.items():
                        out[str(k)] = v if isinstance(v, dict) else {}
        _WATCH[path] = out
    return _WATCH[path]


def item(cc, kind, key, date, title, areas, tier, watched=False, status=None, url=None,
         lines=None):
    return {"cc": cc, "kind": kind, "key": str(key), "date": day(date), "title": clean(title),
            "status": clean(status) or None, "areas": list(areas), "tier": tier,
            "watched": bool(watched), "url": url, "lines": list(lines or [])}


def on_ground(areas_raw, watched):
    return bool(areas_of(areas_raw)) or watched


# --- votes: tallies and party splits ----------------------------------------------

YES = {"yes", "si", "sí", "afirmativo", "a favor", "favor"}
NO = {"no", "en contra", "contra"}
ABST = {"abst", "abstencion", "abstención", "blanco", "abstencion/blanco"}


def bucket(position):
    p = (position or "").strip().lower()
    if p in YES:
        return 0
    if p in NO:
        return 1
    if p in ABST:
        return 2
    return None


def split_line(groups, label="By party"):
    """'By party (for-against): PSUV 54-0, ...' from {party: [yes, no]}."""
    parts = ["{0} {1}-{2}".format(p or "unknown", v[0], v[1])
             for p, v in sorted(groups.items(), key=lambda kv: (-(kv[1][0] + kv[1][1]), kv[0] or ""))
             if v[0] or v[1]]
    return "{0} (for-against): {1}".format(label, ", ".join(parts)) if parts else None


def party_split(conn, sql, params):
    """{party: [yes, no]} from (party, position) rows."""
    groups = {}
    for r in rows(conn, sql, params):
        b = bucket(r[1])
        if b is None or b == 2:
            continue
        groups.setdefault(r[0], [0, 0])[b] += 1
    return groups


def tally(yes, no, abstain=None, result=None):
    bits = ["{0} for, {1} against".format(yes if yes is not None else "?",
                                          no if no is not None else "?")]
    if abstain:
        bits.append("{0} abstaining".format(abstain))
    line = "Tally: " + ", ".join(bits)
    if result:
        line += "; result as recorded: “{0}”".format(clean(result))
    return line


def positions_line(n):
    return "{0} member positions stored.".format(n) if n else None


def matched_line(own_raw, refs):
    """Say when a vote's areas are only its bill's (the US edition's rule):
    a procedural vote on a bill inherits the bill's areas."""
    if own_raw is None or areas_of(own_raw):
        return None
    refs = [r for r in (refs or []) if r]
    return "Areas from the bill it names{0}, not the vote's own words.".format(
        " ({0})".format(", ".join(refs[:3])) if refs else "")


def vote_item(cc, key, date, title, areas_raw, tier, watched, yes, no, abstain=None,
              result=None, split=None, positions=None, url=None, split_label="By party",
              matched=None):
    lines = [tally(yes, no, abstain, result)]
    if matched:
        lines.append(matched)
    s = split_line(split or {}, split_label) if split else None
    if s:
        lines.append(s)
    p = positions_line(positions)
    if p:
        lines.append(p)
    return item(cc, "vote", key, date, title, areas_of(areas_raw), tier, watched, url=url,
                lines=lines)


# --- the adapters, one per collected country -----------------------------------

def _win(col):
    return "substr({0},1,10) > ? AND substr({0},1,10) <= ?".format(col)


def items_co(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM co_bills WHERE " + _win("filed_at"), (since, until)):
        w = r["bill_key"] in wl or (r["other_key"] or "") in wl
        if on_ground(r["areas"], w):
            out.append(item("co", "new", r["bill_key"], r["filed_at"], r["nickname"] or r["title"],
                            areas_of(r["areas"]), r["tier"], w, r["status"], r["url"]))
    for r in rows(conn, "SELECT * FROM co_divisions WHERE " + _win("date"), (since, until)):
        w = (r["bill_key"] or "") in wl
        if not on_ground(r["areas"], w):
            continue
        split = party_split(conn, "SELECT m.party, v.position FROM co_votes v LEFT JOIN co_members m "
                                  "USING (member_key) WHERE v.division_key=?", (r["division_key"],))
        n = sum(a + b for a, b in split.values())
        out.append(vote_item("co", r["division_key"], r["date"], r["question"], r["areas"], None, w,
                             r["yes"], r["no"], split=split, positions=n))
    return out


def items_cl(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM cl_bills WHERE " + _win("introduced"), (since, until)):
        w = r["boletin"] in wl
        if on_ground(r["areas"], w):
            out.append(item("cl", "new", r["boletin"], r["introduced"], r["title"],
                            areas_of(r["areas"]), r["tier"], w, r["status"] or r["stage"]))
    for r in rows(conn, "SELECT * FROM cl_divisions WHERE " + _win("date"), (since, until)):
        w = (r["boletin"] or "") in wl
        if not on_ground(r["areas"], w):
            continue
        split = party_split(conn, "SELECT party, position FROM cl_votes WHERE division_key=?",
                            (r["division_key"],))
        n = rows(conn, "SELECT COUNT(*) FROM cl_votes WHERE division_key=?", (r["division_key"],))
        title = " ".join(x for x in (r["description"], r["text"]) if x)
        out.append(vote_item("cl", r["division_key"], r["date"], title, r["areas"], r["tier"], w,
                             r["yes"], r["no"], r["abstain"], r["result"], split,
                             n[0][0] if n else None,
                             matched=matched_line(r["own_areas"], [r["boletin"]])))
    return out


def items_pe(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM pe_bills WHERE " + _win("presented"), (since, until)):
        w = r["bill_key"] in wl
        if on_ground(r["areas"], w):
            out.append(item("pe", "new", r["bill_key"], r["presented"], r["title"],
                            areas_of(r["areas"]), r["tier"], w, r["status"]))
    for r in rows(conn, "SELECT * FROM pe_divisions WHERE " + _win("date"), (since, until)):
        refs = json.loads(r["bill_refs"] or "[]")
        w = any(k in wl for k in refs)
        if not on_ground(r["areas"], w):
            continue
        split = party_split(conn, "SELECT bancada, position FROM pe_votes WHERE division_key=?",
                            (r["division_key"],))
        n = rows(conn, "SELECT COUNT(*) FROM pe_votes WHERE division_key=?", (r["division_key"],))
        out.append(vote_item("pe", r["division_key"], r["date"], r["subject"], r["areas"], r["tier"],
                             w, r["yes"], r["no"], r["abstain"], None, split,
                             n[0][0] if n else None, r["source_url"], "By bancada",
                             matched_line(r["own_areas"], refs)))
    return out


def items_ec(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM ec_divisions WHERE " + _win("date"), (since, until)):
        w = r["division_key"] in wl
        if not on_ground(r["areas"], w):
            continue
        split = party_split(conn, "SELECT COALESCE(ro.party, ro.party_slug), v.position FROM ec_votes v "
                                  "LEFT JOIN ec_roster ro ON ro.name_key = v.name_key "
                                  "WHERE v.division_key=?", (r["division_key"],))
        title = " / ".join(x for x in (r["theme"], r["proposal"]) if x)
        out.append(vote_item("ec", r["division_key"], r["date"], title, r["areas"], r["tier"], w,
                             r["yes"], r["no"], (r["abstain"] or 0) + (r["blank"] or 0) or None,
                             None, split, r["positions"], None, "By party on the current roster"))
    return out


def items_bo(conn, since, until, wl):
    """Bolivia publishes no filing dates in a form the store keeps, so a bill
    is news when its register entry changed this month: a logged status move
    (bo_bill_changes, old value known) or a register modification."""
    out, moved = [], set()
    for r in rows(conn, "SELECT c.*, b.title, b.areas, b.tier, b.dip_link FROM bo_bill_changes c "
                        "JOIN bo_bills b USING (bill_key) WHERE c.old IS NOT NULL AND "
                        + _win("c.seen"), (since, until)):
        w = r["bill_key"] in wl
        if on_ground(r["areas"], w):
            moved.add(r["bill_key"])
            out.append(item("bo", "moved", r["bill_key"], r["seen"], r["title"],
                            areas_of(r["areas"]), r["tier"], w,
                            "{0} → {1}".format(clean(r["old"]), clean(r["new"])), r["dip_link"]))
    for r in rows(conn, "SELECT * FROM bo_bills WHERE " + _win("dip_modified"), (since, until)):
        w = r["bill_key"] in wl
        if r["bill_key"] not in moved and on_ground(r["areas"], w):
            out.append(item("bo", "updated", r["bill_key"], r["dip_modified"], r["title"],
                            areas_of(r["areas"]), r["tier"], w,
                            " / ".join(x for x in (r["dip_status"], r["sen_stage"]) if x),
                            r["dip_link"]))
    return out


def items_uy(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM uy_questions WHERE " + _win("date"), (since, until)):
        w = r["question_key"] in wl
        if on_ground(r["areas"], w):
            out.append(item("uy", "pedido", r["question_key"], r["date"], r["tema"],
                            areas_of(r["areas"]), r["tier"], w, r["estado"], r["url_oficio"],
                            ["Asked of {0} by {1}.".format(clean(r["organismo"]).title(),
                                                          clean(r["autores"]))]))
    for r in rows(conn, "SELECT * FROM uy_laws WHERE " + _win("promulgated"), (since, until)):
        key = "ley:{0}".format(r["law_number"])
        w = key in wl
        if on_ground(r["areas"], w):
            out.append(item("uy", "law", key, r["promulgated"],
                            "Ley {0}: {1}".format(r["law_number"], r["name"] or ""),
                            areas_of(r["areas"]), r["tier"], w, None, r["url"]))
    return out


def items_gt(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM gt_initiatives WHERE " + _win("conocio_pleno"), (since, until)):
        w = r["numero"] in wl
        if on_ground(r["areas"], w):
            out.append(item("gt", "new", "Iniciativa " + r["numero"], r["conocio_pleno"], r["resumen"],
                            areas_of(r["areas"]), r["tier"], w, "Plenary took notice", r["pdf_url"]))
    for r in rows(conn, "SELECT * FROM gt_divisions WHERE " + _win("date"), (since, until)):
        w = (r["iniciativa"] or "") in wl
        if not on_ground(r["areas"], w):
            continue
        split = party_split(conn, "SELECT m.bloque, v.position FROM gt_votes v LEFT JOIN gt_members m "
                                  "ON m.name_key = v.name_key WHERE v.division_key=?",
                            (r["division_key"],))
        out.append(vote_item("gt", r["division_key"], r["date"], r["title"], r["areas"], r["tier"], w,
                             r["yes"], r["no"], None, None, split, r["positions"], None,
                             "By current bloc (GT4)"))
    return out


def items_pa(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM pa_bills WHERE " + _win("presented"), (since, until)):
        w = str(r["ficha"]) in wl
        if on_ground(r["areas"], w):
            out.append(item("pa", "new", "Ficha {0}".format(r["ficha"]), r["presented"], r["title"],
                            areas_of(r["areas"]), r["tier"], w, r["stage"], r["doc_url"]))
    for r in rows(conn, "SELECT s.*, b.title, b.areas, b.tier, b.doc_url, b.presented FROM pa_bill_stages s "
                        "JOIN pa_bills b USING (ficha) WHERE " + _win("s.date")
                        + " ORDER BY s.ficha, s.seq", (since, until)):
        w = str(r["ficha"]) in wl
        if not on_ground(r["areas"], w) or (day(r["presented"]) > since and r["stage"] in (
                "Preliminar", "Prohijado")):
            continue
        out.append(item("pa", "moved", "Ficha {0}".format(r["ficha"]), r["date"], r["title"],
                        areas_of(r["areas"]), r["tier"], w,
                        "{0}: {1}".format(clean(r["stage"]), clean(r["comment"])), r["doc_url"]))
    return out


def items_hn(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM hn_bills WHERE " + _win("fecha"), (since, until)):
        w = (r["numero"] or "") in wl
        if on_ground(r["areas"], w):
            kind = "new" if (r["estado"] or "Iniciativa") == "Iniciativa" else "moved"
            out.append(item("hn", kind, r["numero"] or r["project_id"], r["fecha"], r["titulo"],
                            areas_of(r["areas"]), r["tier"], w, r["estado"]))
    for r in rows(conn, "SELECT a.*, s.schedule, s.name AS session FROM hn_agenda_items a JOIN hn_sessions s "
                        "USING (room_id) WHERE " + _win("s.schedule"), (since, until)):
        w = (r["project_number"] or "") in wl
        if on_ground(r["areas"], w):
            out.append(item("hn", "agenda", r["project_number"] or "agenda-{0}".format(r["room_item_id"]),
                            r["schedule"], r["name"], areas_of(r["areas"]), r["tier"], w,
                            clean(r["list_name"]) or None,
                            lines=["Session: {0}.".format(clean(r["session"]))]))
    for r in rows(conn, "SELECT * FROM hn_news WHERE " + _win("created_at"), (since, until)):
        if on_ground(r["areas"], False):
            w = any(k in (r["body"] or "") + (r["title"] or "") for k in wl)
            out.append(item("hn", "press", "press-" + str(r["post_id"]), r["created_at"], r["title"],
                            areas_of(r["areas"]), r["tier"], w))
    for r in rows(conn, "SELECT * FROM hn_gazette WHERE " + _win("date"), (since, until)):
        if on_ground(r["areas"], False):
            out.append(item("hn", "gazette", "Gaceta {0}".format(r["issue"]), r["date"],
                            clip(r["summary"], 300), areas_of(r["areas"]), r["tier"], False,
                            url=r["url"]))
    return out


def items_sv(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT d.*, s.date FROM sv_dictamenes d JOIN sv_sessions s USING (session_key) "
                        "WHERE " + _win("s.date"), (since, until)):
        w = (r["expediente"] or "") in wl
        if on_ground(r["areas"], w):
            out.append(item("sv", "report", "Dictamen {0}".format(r["dictamen_key"]), r["date"],
                            r["extracto"], areas_of(r["areas"]), r["tier"], w,
                            "{0}, {1}".format(clean(r["comision"]), clean(r["resultado"])), r["pdf_url"]))
    for r in rows(conn, "SELECT v.*, d.extracto AS d_text, p.leyenda AS p_title, p.extracto AS p_text "
                        "FROM sv_divisions v LEFT JOIN sv_dictamenes d ON d.dictamen_key = v.item_key "
                        "LEFT JOIN sv_piezas p ON p.pieza_key = v.item_key WHERE " + _win("v.date"),
                  (since, until)):
        w = (r["expediente"] or "") in wl or (r["item_key"] or "") in wl
        if not on_ground(r["areas"], w):
            continue
        try:
            groups = {k: list(v) for k, v in json.loads(r["groups"] or "{}").items()}
        except (TypeError, ValueError):
            groups = {}
        what = r["d_text"] or r["p_text"] or r["p_title"] or ""
        title = "{0}: {1}".format(clean(r["label"]), clip(what, 400)) if what else r["label"]
        out.append(vote_item("sv", r["division_key"], r["date"], title, r["areas"], r["tier"], w,
                             r["yes"], r["no"], r["abstain"], None, groups, r["positions"],
                             r["pdf_url"]))
    return out


def items_do(conn, since, until, wl):
    out = []
    for r in rows(conn, "SELECT * FROM do_bills WHERE " + _win("deposited"), (since, until)):
        w = r["bill_key"] in wl
        if on_ground(r["areas"], w):
            out.append(item("do", "new", r["bill_key"], r["deposited"], r["title"],
                            areas_of(r["areas"]), r["tier"], w, r["status"]))
    for r in rows(conn, "SELECT * FROM do_bills WHERE " + _win("last_change")
                  + " AND substr(deposited,1,10) <= ?", (since, until, since)):
        w = r["bill_key"] in wl
        if on_ground(r["areas"], w):
            out.append(item("do", "moved", r["bill_key"], r["last_change"], r["title"],
                            areas_of(r["areas"]), r["tier"], w, r["status"]))
    for r in rows(conn, "SELECT * FROM do_divisions WHERE " + _win("date"), (since, until)):
        refs = json.loads(r["bill_refs"] or "[]")
        w = any(k in wl for k in refs)
        if not on_ground(r["areas"], w):
            continue
        split = party_split(conn, "SELECT party, position FROM do_votes WHERE division_key=?",
                            (r["division_key"],))
        out.append(vote_item("do", r["division_key"], r["date"], r["motion"] or r["title"], r["areas"],
                             r["tier"], w, r["yes"], r["no"], r["abstain"], None, split,
                             r["positions"], matched=matched_line(r["own_areas"], refs)))
    return out


ADAPTERS = {"co": items_co, "cl": items_cl, "pe": items_pe, "ec": items_ec, "bo": items_bo,
            "uy": items_uy, "gt": items_gt, "pa": items_pa, "hn": items_hn, "sv": items_sv,
            "do": items_do}


def ve_items(conn, since, until, config_dir=None):
    """Venezuela's news items on our ground; watched when a hand-watched
    item's match terms appear (config/watchlist-ve.yaml)."""
    wl = watchlist("ve", config_dir)
    out = []
    for r in rows(conn, "SELECT * FROM ve_news WHERE " + _win("date"), (since, until)):
        text = "{0} {1}".format(r["title"] or "", r["body"] or "").lower()
        hit = [k for k, v in wl.items() if any(m.lower() in text for m in (v.get("match") or []))]
        if on_ground(r["areas"], bool(hit)):
            areas = sorted(set(areas_of(r["areas"])) | {a for k in hit for a in wl[k].get("areas", [])})
            out.append(item("ve", "news", r["url"], r["date"], r["title"], areas, r["tier"],
                            bool(hit), hit[0] if hit else None, r["url"]))
    return out


def nic_items(conn, since, until):
    """Nicaragua's gazette notices on our ground; the edition shows area 8."""
    out = []
    for r in rows(conn, "SELECT * FROM nic_gazette_items WHERE " + _win("date"), (since, until)):
        if on_ground(r["areas"], False):
            out.append(item("nic", "gazette", r["item_key"], r["date"], r["heading"],
                            areas_of(r["areas"]), r["tier"], False,
                            "La Gaceta No. {0}".format(r["issue"]), r["url"]))
    return out


def ledger_moves(ledger, cc, since, until):
    """Stage moves of watched items that only the alert pass can see (a
    country whose store keeps no change dates), from data/latam-alerts.json."""
    out = []
    for m in (ledger or {}).get("moves", []):
        if m.get("cc") == cc and since < m.get("date", "") <= until:
            out.append(item(cc, "moved", m["key"], m["date"], m.get("title"), m.get("areas") or [],
                            1, True, "{0} → {1}".format(clean(m.get("old")), clean(m.get("new"))),
                            m.get("url")))
    return out


# Countries whose store dates a stage move itself; the others take moves
# from the alert ledger.
SOURCE_MOVES = ("bo", "pa", "do", "hn")


def country_items(conn, cc, since, until, ledger=None, config_dir=None):
    if cc == "ve":
        return ve_items(conn, since, until, config_dir)
    if cc == "nic":
        return nic_items(conn, since, until)
    if cc not in ADAPTERS:
        return []
    got = ADAPTERS[cc](conn, since, until, watchlist(cc, config_dir))
    if cc not in SOURCE_MOVES:
        got += ledger_moves(ledger, cc, since, until)
    return collapse(got)


# --- watched items' current status (for moves) --------------------------------

STATUS_SQL = {
    "co": "SELECT bill_key AS key, status, COALESCE(nickname, title) AS title, url, areas FROM co_bills",
    "cl": "SELECT boletin AS key, COALESCE(status,'') || CASE WHEN stage IS NOT NULL THEN ' / ' || stage "
          "ELSE '' END AS status, title, NULL AS url, areas FROM cl_bills",
    "pe": "SELECT bill_key AS key, status, title, NULL AS url, areas FROM pe_bills",
    "gt": "SELECT numero AS key, NULL AS status, resumen AS title, pdf_url AS url, areas FROM gt_initiatives",
    "uy": "SELECT 'ley:' || law_number AS key, 'promulgated' AS status, name AS title, url, areas FROM uy_laws",
    "hn": "SELECT numero AS key, estado AS status, titulo AS title, NULL AS url, areas FROM hn_bills",
    "bo": "SELECT bill_key AS key, COALESCE(dip_status,'') || ' / ' || COALESCE(sen_stage,'') AS status, "
          "title, dip_link AS url, areas FROM bo_bills",
    "pa": "SELECT CAST(ficha AS TEXT) AS key, stage AS status, title, doc_url AS url, areas FROM pa_bills",
    "do": "SELECT bill_key AS key, status, title, NULL AS url, areas FROM do_bills",
}


def watched_status(conn, cc, config_dir=None):
    """{key: (status, title, url, areas)} for every watched item the store holds."""
    wl = watchlist(cc, config_dir)
    if cc not in STATUS_SQL or not wl:
        return {}
    out = {}
    for r in rows(conn, STATUS_SQL[cc]):
        if str(r["key"]) in wl and r["status"]:
            out[str(r["key"])] = (clean(r["status"]), clean(r["title"]), r["url"],
                                  areas_of(r["areas"]) or wl[str(r["key"])].get("areas", []))
    return out


# --- scoring (stub triage only: X16) --------------------------------------------

def score(items):
    """Attach the stub triage score to each item and return them ordered:
    watched first, then score, then date (newest first)."""
    from src import triage
    tis = [triage.TriageItem(id=str(i), title=it["title"], text=it["title"], tier=it["tier"],
                             issue_areas=it["areas"], watchlist_hit=it["watched"])
           for i, it in enumerate(items)]
    # The AI judge is deferred (X16): stub, whatever TRIAGE says.
    for res in triage.triage(tis, mode="stub"):
        items[int(res.id)]["score"] = res.score
    return sorted(items, key=lambda it: (not it["watched"], -it.get("score", 0),
                                         it["kind"] != "vote", _neg(it["date"])))


def _neg(iso):
    try:
        return -datetime.date.fromisoformat(iso).toordinal()
    except (TypeError, ValueError):
        return 0


def load_ledger(directory=None):
    """Every country's ledger merged, for the edition: {"moves": [...]}, or
    None when no alert pass has run yet."""
    directory = directory or LEDGER_DIR
    if not os.path.isdir(directory):
        return None
    moves = []
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                moves += (json.load(fh) or {}).get("moves", [])
    return {"moves": moves}


def collapse(items):
    """One line per (country, kind, key) for stage moves: a Panama bill that
    went to subcommittee and back in one month is one item whose status
    reads the moves in order."""
    out, seen = [], {}
    for it in sorted(items, key=lambda i: (i["date"], i["key"])):
        if it["kind"] != "moved":
            out.append(it)
            continue
        k = (it["cc"], it["key"])
        if k in seen:
            prev = seen[k]
            if it["status"] and it["status"] not in (prev["status"] or ""):
                prev["status"] = "{0}; then {1}".format(prev["status"], it["status"])
            prev["date"] = max(prev["date"], it["date"])
            prev["watched"] = prev["watched"] or it["watched"]
            continue
        it = dict(it)
        seen[k] = it
        out.append(it)
    return out
