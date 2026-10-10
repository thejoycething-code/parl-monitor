#!/usr/bin/env python3
"""The Eerste Kamer (Dutch Senate): its votes, party by party or member by
member, and the bills and motions they were on, from its own web pages (NL4,
Chris, 10 October 2026: the Eerste Kamer via its web pages).

    python3 tools/nl_eerstekamer.py                    # the weekly pull
    python3 tools/nl_eerstekamer.py --since 2023-06-13 # back to a date
    python3 tools/nl_eerstekamer.py --reclassify       # offline, after a taxonomy change
    python3 tools/nl_eerstekamer.py --dry-run          # one page, store nothing
    python3 tools/nl_eerstekamer.py --db /tmp/nl.db    # anywhere but the store

THE SOURCE. eerstekamer.nl has no API: /opendata is 404 and the Tweede
Kamer's OData portal carries no Eerste Kamer votes (docs/netherlands-scope.md).
Its page "Stemmingen per vergaderdag" (/stemmingen_per_vergaderdag) lists,
sitting day by sitting day, every vote: the bill or motion with its
Kamerstuk number and a link to its page, how it was decided ("Stemming bij
zitten en opstaan", a show of hands; "Hoofdelijke stemming", a roll call;
"Hamerstuk", passed without a vote), the result in the Kamer's own word
(aangenomen / verworpen), and who was for and against: fracties on a show
of hands, every senator by name with their fractie on a roll call, and on a
hamerstuk the fracties that asked for their dissent to be recorded
("aantekening gevraagd"). 25 votes a page, newest first; the link to the
next page carries `start_006=<n>&dlastinprev=<date>`.

POLITELY. robots.txt (read 10 October 2026) disallows only search, print
layouts, comment forms, sort parameters and doubled start parameters; the
pages read here are none of those. One page a second at most (the host
throttle), the honest CitizenGO user agent, every page archived to
data/raw. A weekly run reads back to two weeks before the newest stored
vote: one to three pages. The first run reads to --since (default: the
present Senate's first sitting, 13 June 2023), about 150 pages.

KEYS, NEVER TITLES. A vote is 'ek-<YYYYMMDD>-<reference>': the sitting date
and the Kamerstuk reference as printed ('37020-M' for motion M in dossier
37.020, '36791' for the bill, 'CLXXVII-F' for an amendment to a Rules of
Procedure proposal); a second vote on the same reference the same day gets
'-2'. The dossier number is what config/watchlist-nl.yaml is keyed on, the
same numbers as the Tweede Kamer's, so the watchlist applies unchanged.

CLASSIFICATION: config/taxonomy-nl.yaml for `nl` on the title, plus the
watchlist by dossier. Bills (nl_ek_bills) take their title from the vote
list; a vote on a bill inherits the bill's areas, a motion carries its own.

WHAT IS NOT DERIVED. A show of hands records fracties, not senators; the
edition says so and gives no member positions for it (the Tweede Kamer's
X5 derivation needs a sitting-member list per fractie, which this collector
does not read). A roll call records every senator.

Separation guarantee: writes nl_ek_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store. Exit 3 when it stored what it could and
recorded gaps (jobs/nl-weekly.sh still publishes), 0 when clean.
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

from src import db, drain, filter as filt, nl_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "nl-eerstekamer"
HOST = "https://www.eerstekamer.nl"
LIST = HOST + "/stemmingen_per_vergaderdag"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-nl.yaml")
TAXONOMY_COUNTRY = "nl"
# The present Senate first sat on 13 June 2023 (elected 30 May 2023).
SINCE_DEFAULT = "2023-06-13"
LOOKBACK_DAYS = 14
MAX_PAGES = 400
HIDDEN_AREAS = (11,)
BUDGET_S = drain.DEFAULT_S

MONTHS = {"januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
          "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
          "december": 12}
_DAY = re.compile(r'<h2><a id="p\d+"></a>\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})')
_ITEM = '<li class="opsomitem met_image image_breed">'
_RESULT_IMG = re.compile(r'<div class="opsomteken">\s*<img[^>]*alt="([^"]*)"')
_REF = re.compile(r'\(<a href="(/(?:wetsvoorstel|motiedossier|kamerstukdossier|behandeling)/'
                  r'[^"]+)">([^<]+)</a>\)')
# The decision line: 'Stemming bij zitten en opstaan, aangenomen' (a show of
# hands, its sides folded under it), 'Hoofdelijke stemming, verworpen' (a roll
# call), 'Algemene stemmen, aangenomen' (unanimous, no sides) or 'Hamerstuk'.
# 'Zonder stemmen' (passed without a vote) is printed with or without its
# result word.
METHODS = ("Stemming bij zitten en opstaan", "Hoofdelijke stemming", "Algemene stemmen",
           "Zonder stemmen")
_METHOD = re.compile(r'<a href="[^"]*">\s*((?:' + "|".join(METHODS) + r')[^<]*?)\s*</a>',
                     re.S | re.I)
_HAMER = re.compile(r'<a href="[^"]*">\s*Hamerstuk\s*</a>')
_SIDE = re.compile(r"<strong>([^<:]+):</strong>\s*(.*?)<br\s*/?>", re.S)
_NEXT = re.compile(r'<a href="(/stemmingen_per_vergaderdag\?start_006=[^"]+)"[^>]*>\s*'
                   r'<span>eerdere stemmingen</span>')
_MEMBER = re.compile(r"^(.*\S)\s+\(([^()]+)\)$")


# --- parsing (pure) -------------------------------------------------------------

def _text(markup):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))).strip()


def split_list(text):
    """'BBB, PVV en SGP' -> ['BBB', 'PVV', 'SGP']. Dutch lists end ' en '."""
    text = (text or "").strip()
    if not text:
        return []
    head, sep, last = text.rpartition(" en ")
    parts = (head.split(", ") + [last]) if sep else [text]
    return [p.strip() for p in parts if p.strip()]


def parse_date(day, month, year):
    m = MONTHS.get(month.lower())
    return datetime.date(int(year), m, int(day)).isoformat() if m else None


def reference(link_text):
    """(dossier, reference) from the Kamerstuk link's text:
    '37.020, M' -> ('37020', '37020-M'); '36.791' -> ('36791', '36791');
    '36.455 (R2188)' -> ('36455', '36455');
    '36.945 I' -> ('36945-I', '36945-I'); '36.800 M, F' -> ('36800-M', '36800-M-F');
    '36.703 / 36.704 / 36.855, O' -> ('36703', '36703-36704-36855-O');
    'EK CLXXVII  F' -> ('CLXXVII', 'CLXXVII-F'); 'CLXXVII' -> ('CLXXVII', 'CLXXVII').
    Words that are not a Kamerstuk number ('nog niet als Kamerstuk
    gepubliceerd') are dropped."""
    t = re.sub(r"\s+", " ", html.unescape(link_text or "")).strip()
    t = re.sub(r"^EK\s+", "", t)
    t = re.sub(r"\s*\([^()]*\)", "", t).strip()    # '36.455 (R2188)': the Rijkswet number
    m = re.match(r"^([IVXLCDM]+)(?:\s+([A-Z]{1,3}))?$", t)
    if m:
        return m.group(1), m.group(1) + ("-" + m.group(2) if m.group(2) else "")
    head, sep, tail = t.rpartition(",")
    letter = tail.strip() if sep and re.match(r"^[A-Z]{1,3}\d*$", tail.strip()) else None
    if not letter:
        head = t
    parts = []
    for part in head.split("/"):
        pm = re.match(r"^\s*(\d{1,3}(?:\.\d{3})?)(?:\s+([A-Z]+))?\b", part)
        if pm:
            parts.append(pm.group(1).replace(".", "") + ("-" + pm.group(2) if pm.group(2) else ""))
    if not parts:
        clean = re.sub(r"[^\w.-]+", "-", t).strip("-")
        return clean or None, clean or None
    return parts[0], "-".join(parts) + ("-" + letter if letter else "")


def kind_of(path):
    return {"wetsvoorstel": "bill", "motiedossier": "motion", "kamerstukdossier": "other",
            "behandeling": "amendment"}.get((path or "/").split("/")[1], "other")


def parse_item(chunk):
    """One vote's <li> -> dict, or None when it names no Kamerstuk."""
    ref = _REF.search(chunk)
    if not ref:
        return None
    title = _text(chunk[chunk.find('<div class="opsomtekst">'):ref.start()])
    dossier, refkey = reference(ref.group(2))
    hit = _RESULT_IMG.search(chunk)
    result_img = (hit.group(1) if hit else "").strip().lower() or None
    sides = {label.strip().lower(): split_list(_text(body))
             for label, body in _SIDE.findall(chunk)}
    if _HAMER.search(chunk):
        method, result = "Hamerstuk", result_img or "aangenomen"
    else:
        m = _METHOD.search(chunk, ref.end())
        words = _text(m.group(1)) if m else ""
        method, _, said = words.partition(",")
        method = method.strip() or None
        result = said.strip().lower() or result_img
    roll = (method or "").lower().startswith("hoofdelijk")
    return {"title": title, "url": HOST + ref.group(1), "kind": kind_of(ref.group(1)),
            "dossier": dossier, "ref": refkey, "method": method, "result": result,
            "roll_call": roll, "voor": sides.get("voor", []), "tegen": sides.get("tegen", []),
            "aantekening": sides.get("aantekening gevraagd", [])}


def parse_page(text):
    """(votes in page order with their date, next page path or None). A day
    heading may read '22 september 2026 (vervolg)': the day continues from
    the page before."""
    votes = []
    marks = [(m.start(), parse_date(*m.groups())) for m in _DAY.finditer(text)]
    for i, (pos, date) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        block = text[pos:end]
        for chunk in block.split(_ITEM)[1:]:
            item = parse_item(chunk)
            if item:
                item["date"] = date
                votes.append(item)
    nxt = _NEXT.search(text)
    return votes, (html.unescape(nxt.group(1)) if nxt else None)


def member_side(entry):
    """'Andrea van Langen-Visbeek (BBB)' -> ('Andrea van Langen-Visbeek', 'BBB')."""
    m = _MEMBER.match(entry or "")
    return (m.group(1), m.group(2)) if m else (entry, None)


def assign_keys(votes, taken=None):
    """Give each vote its key; a repeat of a reference on one day gets '-2'."""
    seen = dict(taken or {})
    for v in votes:
        base = "ek-{0}-{1}".format((v["date"] or "").replace("-", ""), v["ref"])
        n = seen.get(base, 0) + 1
        seen[base] = n
        v["key"] = base if n == 1 else "{0}-{1}".format(base, n)
    return votes


# --- classification and storage -------------------------------------------------

def load_taxonomy(path=None):
    path = path or TAXONOMY
    if os.path.exists(path):
        return filt.load_taxonomy(path, country=TAXONOMY_COUNTRY)
    return filt.Taxonomy(version="none", terms={}, exclusions=set())


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _watch_keys(dossier, ref=None):
    """'36945-I' is watched as itself or as '36945'; a motion in several
    dossiers ('36703-36704-36855-O') under any of them."""
    keys = []
    for k in [dossier] + re.findall(r"\b\d{5}\b", ref or ""):
        if not k:
            continue
        for x in (k, k.split("-")[0]):
            if x not in keys:
                keys.append(x)
    return keys


def classify(tax, wl, title, dossier, watch_path=None, ref=None):
    res = filt.filter_item(tax, wl, title or "")
    return nl_store.add_watch_areas(res, None, _watch_keys(dossier, ref), watch_path)


def _gap(conn, today, detail, log=print):
    log("  [gap] " + detail)
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def store_bill(conn, v, res, today):
    conn.execute(
        "INSERT INTO nl_ek_bills (dossier, title, url, last_vote, last_result, areas, "
        "matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(dossier) DO UPDATE SET title=excluded.title, url=excluded.url, "
        "last_vote=CASE WHEN excluded.last_vote >= COALESCE(nl_ek_bills.last_vote, '') "
        "THEN excluded.last_vote ELSE nl_ek_bills.last_vote END, "
        "last_result=CASE WHEN excluded.last_vote >= COALESCE(nl_ek_bills.last_vote, '') "
        "THEN excluded.last_result ELSE nl_ek_bills.last_result END, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (v["dossier"], v["title"], v["url"], v["date"], v["result"],
         nl_store.dumps(res.issue_areas),
         nl_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier,
         today, today))


def _bill_areas(conn, dossier):
    row = conn.execute("SELECT areas FROM nl_ek_bills WHERE dossier=?", (dossier,)).fetchone()
    return json.loads(row[0] or "[]") if row else []


def store_vote(conn, v, tax, wl, today, watch_path=None):
    """Upsert one vote and its sides. Returns its combined areas."""
    own = classify(tax, wl, v["title"], v["dossier"], watch_path, v["ref"])
    if v["kind"] == "bill":
        store_bill(conn, v, own, today)
    lent = _bill_areas(conn, v["dossier"]) if v["kind"] != "bill" else []
    areas = sorted(set(own.issue_areas or []) | set(lent))
    conn.execute(
        "INSERT INTO nl_ek_divisions (division_key, date, kind, dossier, ref, title, url, method, "
        "result, roll_call, voor, tegen, aantekening, own_areas, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET title=excluded.title, url=excluded.url, "
        "method=excluded.method, result=excluded.result, roll_call=excluded.roll_call, "
        "voor=excluded.voor, tegen=excluded.tegen, aantekening=excluded.aantekening, "
        "own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (v["key"], v["date"], v["kind"], v["dossier"], v["ref"], v["title"], v["url"],
         v["method"], v["result"], int(v["roll_call"]), len(v["voor"]) if v["roll_call"] else None,
         len(v["tegen"]) if v["roll_call"] else None,
         nl_store.dumps(v["aantekening"]), nl_store.dumps(own.issue_areas), nl_store.dumps(areas),
         nl_store.dumps((own.matched_terms or []) + (own.watchlist_hits or [])), own.tier,
         today, today))
    conn.execute("DELETE FROM nl_ek_votes WHERE division_key=?", (v["key"],))
    for position, side in (("voor", v["voor"]), ("tegen", v["tegen"]),
                           ("aantekening", v["aantekening"])):
        for entry in side:
            if v["roll_call"] and position != "aantekening":
                name, fractie = member_side(entry)
                kind, actor = "lid", name
            else:
                kind, actor, fractie = "fractie", entry, entry
            conn.execute("INSERT OR REPLACE INTO nl_ek_votes (division_key, kind, actor, fractie, "
                         "position) VALUES (?,?,?,?,?)", (v["key"], kind, actor, fractie, position))
    return areas


# --- the pull ------------------------------------------------------------------------

def pull(conn, client, today, since=None, tax=None, wl=None, log=print, budget=None,
         max_pages=MAX_PAGES, watch_path=None):
    """Read pages newest first until a whole page is older than `since` (by
    default two weeks before the newest stored vote, or SINCE_DEFAULT on an
    empty store). Returns (read, ours, gaps)."""
    tax = tax if tax is not None else load_taxonomy()
    wl = wl if wl is not None else empty_watchlist()
    if since is None:
        (newest,) = conn.execute("SELECT MAX(date) FROM nl_ek_divisions").fetchone()
        since = ((datetime.date.fromisoformat(newest) - datetime.timedelta(days=LOOKBACK_DAYS))
                 .isoformat() if newest else SINCE_DEFAULT)
    url, page, gaps, collected = LIST, 0, 0, []
    while url and page < max_pages:
        if budget is not None and budget.exhausted():
            log(budget.disclose("Eerste Kamer vote pages", page))
            _gap(conn, today, "Eerste Kamer: budget spent at page {0}".format(page + 1), log)
            gaps += 1
            break
        try:
            text = client.get_text(url, FEED, "stemmingen-p{0}".format(page + 1))
        except FetchError as exc:
            _gap(conn, today, "Eerste Kamer page {0}: {1}".format(page + 1, exc), log)
            gaps += 1
            break
        page += 1
        votes, nxt = parse_page(text)
        if not votes and page == 1:
            _gap(conn, today, "Eerste Kamer page 1: no votes parsed (layout changed?)", log)
            gaps += 1
            break
        collected.extend(v for v in votes if (v["date"] or "") >= since)
        # A page that reaches back past `since` completes every day from
        # `since` on (a day continued from the page before is marked
        # "(vervolg)"), so the next page is not needed.
        if votes and min(v["date"] or "" for v in votes) < since:
            break
        url = HOST + nxt if nxt else None
    # Keys by day, in the page order (newest first) reversed, so a day's
    # first vote on a reference keeps the plain key whatever the paging.
    collected.reverse()
    assign_keys(collected)
    ours = 0
    for v in collected:
        ours += on_our_ground(store_vote(conn, v, tax, wl, today, watch_path))
    conn.commit()
    return len(collected), ours, gaps


def reclassify(conn, tax=None, log=print, watch_path=None):
    """Re-derive bill areas, then vote areas, offline."""
    tax = tax if tax is not None else load_taxonomy()
    wl = empty_watchlist()
    changed = 0
    for dossier, title in conn.execute("SELECT dossier, title FROM nl_ek_bills").fetchall():
        res = classify(tax, wl, title, dossier, watch_path)
        conn.execute("UPDATE nl_ek_bills SET areas=?, matched_terms=?, tier=? WHERE dossier=?",
                     (nl_store.dumps(res.issue_areas),
                      nl_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, dossier))
    for key, kind, dossier, ref, title, areas in conn.execute(
            "SELECT division_key, kind, dossier, ref, title, areas FROM nl_ek_divisions").fetchall():
        own = classify(tax, wl, title, dossier, watch_path, ref)
        lent = _bill_areas(conn, dossier) if kind != "bill" else []
        new = nl_store.dumps(sorted(set(own.issue_areas or []) | set(lent)))
        changed += new != (areas or "[]")
        conn.execute("UPDATE nl_ek_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (nl_store.dumps(own.issue_areas), new,
                      nl_store.dumps((own.matched_terms or []) + (own.watchlist_hits or [])),
                      own.tier, key))
    conn.commit()
    log("nl-eerstekamer: reclassified; {0} vote(s) changed area".format(changed))
    return changed


HEARTBEAT = "NL Eerste Kamer"


def stamp(conn, today):
    """The step's own heartbeat (tools/coverage.py AWAITING_FIRST_RUN): the
    weekly it belongs to had its heartbeat before this step's tables existed."""
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/nl_eerstekamer.py"))
    conn.commit()


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = sum(on_our_ground(json.loads(a or "[]"))
               for (a,) in conn.execute("SELECT areas FROM nl_ek_divisions"))
    log("  store: {0} Eerste Kamer vote(s), {1} on our ground, {2} roll call(s); {3} bill(s)".format(
        n("SELECT COUNT(*) FROM nl_ek_divisions"), ours,
        n("SELECT COUNT(*) FROM nl_ek_divisions WHERE roll_call=1"),
        n("SELECT COUNT(*) FROM nl_ek_bills")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--since", help="read back to this date (default: two weeks before the "
                                    "newest stored vote; {0} on an empty store)".format(SINCE_DEFAULT))
    ap.add_argument("--taxonomy")
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="read one page, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    client.set_host_throttle("www.eerstekamer.nl", 1.0)
    today = datetime.date.today().isoformat()
    tax = load_taxonomy(args.taxonomy)
    if args.dry_run:
        votes, nxt = parse_page(client.get_text(LIST, FEED, "dry", archive=False))
        print("nl-eerstekamer: {0} vote(s) on page 1, newest {1}, next page {2}".format(
            len(votes), max((v["date"] for v in votes), default="-"), "yes" if nxt else "no"))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    read, ours, gaps = pull(conn, client, today, since=args.since, tax=tax,
                            budget=drain.Budget(args.budget_seconds))
    print("nl-eerstekamer: {0} vote(s) read, {1} on our ground, {2} gap(s)".format(read, ours, gaps))
    if read or not gaps:
        stamp(conn, today)
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
