#!/usr/bin/env python3
"""Senate of Canada: recorded votes and every senator's position.

    python3 tools/ca_senate.py                     # the current session
    python3 tools/ca_senate.py --session 44-1
    python3 tools/ca_senate.py --db /tmp/ca.db
    python3 tools/ca_senate.py --all-positions     # every vote, not only ours

GROUNDWORK, phase 2 (26 September 2026). Nothing schedules this.

THE SOURCE IS HTML. sencanada.ca publishes no XML or JSON for votes:
  * /en/in-the-chamber/votes/<session>  -- one table of every recorded vote
    (36 in 45-1): date, title, tallies, related bill, result.
  * /en/in-the-chamber/votes/details/<id>/<session>  -- every senator who
    voted, their affiliation (ISG, CSG, PSG, C, Non-affiliated) and province,
    with the position marked in one of three columns.
Both are parsed on their markup, so a redesign of sencanada.ca breaks this
collector LOUDLY: a list with no rows, or a details page with no senators,
is a gap, never an empty vote.

WHY THE SENATE AT ALL, when it records a vote a fifth as often as the
House: it is where the fights we lose in the Commons are fought again. On
C-9 the Senate adopted-then-rejected its committee's amendments (32-41, 3
June 2026) and defeated Senator Martin's third-reading amendment 21-40
before passing the bill 45-13. None of that is visible from the House.

THE SAME RULES AS THE HOUSE (tools/ca_rollcalls.py): every vote stored,
positions fetched on our ground only, `positions_fetched` decides the skip,
the Senate's own result is stored and never derived, and an empty senator
list is a gap with the fetch still owed.

CLASSIFICATION. A Senate title uses the SHORT title ("Combatting Hate Act –
C-9 – Third Reading"), so the bill's LONG title is joined in from ca_bills
when tools/ca_rollcalls.py has stored it. Without it the watchlist's short
names still catch the flagship bills.

Separation guarantee: writes ca_divisions (chamber='senate'), ca_senators,
ca_votes and gaps only. ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ca-senate"
CURRENT_SESSION = "45-1"
BASE = "https://sencanada.ca"
LIST = BASE + "/en/in-the-chamber/votes/{0}"
DETAIL = BASE + "/en/in-the-chamber/votes/details/{0}/{1}"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")
HIDDEN_AREAS = (11,)
POSITIONS = ("Yea", "Nay", "Abstention")
# The earliest session sencanada.ca publishes recorded votes for, MEASURED
# 27 September 2026: the 41-1 page renders its session menu and its "Below is
# a list of standing votes" heading and then no votes at all, while 42-1 lists
# 197. Earlier sessions are skipped and SAID to be skipped. Without this an
# empty list reads as a redesign ("markup changed?"), which is a gap, which
# fails the run and fires the alert on a session that simply has no records.
FIRST_PUBLISHED = (42, 1)
DID_NOT_VOTE = "Did not vote"

TAG = re.compile(r"<[^>]+>")
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TD = re.compile(r"<td([^>]*)>(.*?)</td>", re.S)
BILL = re.compile(r"\b([CS])-(\d{1,4})\b")


def _clean(fragment):
    return " ".join(htmlmod.unescape(TAG.sub(" ", fragment or "")).split())


def parse_session(code):
    hit = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not hit:
        raise ValueError("session must look like 45-1, not {0!r}".format(code))
    return int(hit.group(1)), int(hit.group(2))


def _count(label, text):
    hit = re.search(label + r":\s*(\d+)", text)
    return int(hit.group(1)) if hit else None


def parse_list(page):
    """Every vote row of a session's table, in the Senate's order."""
    out = []
    for row in ROW.findall(page or ""):
        link = re.search(r'href="/en/in-the-chamber/votes/details/(\d+)/[^"]*"[^>]*>(.*?)</a>', row, re.S)
        if not link:
            continue            # the header row, or anything that is not a vote
        cells = TD.findall(row)
        when = re.search(r'data-order="(\d{4}-\d{2}-\d{2})', row)
        text = _clean(row)
        bill = None
        for attrs, cell in cells:
            b = BILL.search(_clean(cell))
            if b and "LEGISInfo" in cell:
                bill = "{0}-{1}".format(b.group(1), b.group(2))
        out.append({
            "vote_id": int(link.group(1)),
            "date": when.group(1) if when else None,
            "title": _clean(link.group(2)),
            "yeas": _count("Yeas", text), "nays": _count("Nays", text),
            "abstentions": _count("Abstentions", text),
            "bill_number": bill,
            "result": _clean(cells[-1][1]) if cells else None,
        })
    return out


def parse_detail(page):
    """[{person_id, name, affiliation, province, position}] for one vote."""
    body = page or ""
    start = body.find('id="sc-vote-details-table"')
    body = body[start:] if start >= 0 else ""
    out = []
    for row in ROW.findall(body):
        who = re.search(r'href="/en/in-the-chamber/votes/senator/(\d+)/[^"]*"[^>]*>(.*?)</a>', row, re.S)
        if not who:
            continue
        cells = TD.findall(row)
        if len(cells) < 6:
            continue
        # The position is the one of the last three cells the Senate sorts
        # first ("aaa") and marks with an icon; the others are empty "zzz".
        # The table lists EVERY seated senator: 104 rows for a 76-vote
        # division on 4 June 2025, the other 28 with no mark at all. Those
        # are stored as DID_NOT_VOTE -- an absence is a fact a 5CA reads --
        # and two marks on one row is unreadable (None, and a gap).
        marks = [('data-order="aaa"' in attrs) or ("fa-times" in cell)
                 for attrs, cell in cells[-3:]]
        position = (POSITIONS[marks.index(True)] if marks.count(True) == 1
                    else DID_NOT_VOTE if not any(marks) else None)
        out.append({"person_id": "senator-" + who.group(1), "name": _clean(who.group(2)),
                    "affiliation": _clean(cells[1][1]) or None,
                    "province": _clean(cells[2][1]) or None, "position": position})
    return out


def check_against_tally(senators, yeas, nays, abstentions):
    """None if the parsed positions add up to the Senate's own tally, else why not.

    The markup is the only structure there is, so the tally on the list page
    is the independent check that the details page was read right."""
    if not senators:
        return "no senators parsed (markup changed?)"
    if any(s["position"] is None for s in senators):
        return "a row carried more than one mark"
    got = [sum(1 for s in senators if s["position"] == p) for p in POSITIONS]
    want = [yeas, nays, abstentions]
    if any(w is not None and g != w for g, w in zip(got, want)):
        return "parsed {0} against the tally {1}".format(
            "/".join(map(str, got)), "/".join(str(w) for w in want))
    return None


def long_titles(conn, parl, sess):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT number, long_title FROM ca_bills WHERE parliament=? AND session=?",
        (parl, sess))}


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def store_vote(conn, parl, sess, v, res, today):
    key = "senate-{0}-{1}-{2}".format(parl, sess, v["vote_id"])
    conn.execute(
        "INSERT INTO ca_divisions (division_key, chamber, parliament, session, number, "
        "date, subject, result, yeas, nays, abstentions, bill_number, areas, "
        "matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET subject=excluded.subject, "
        "result=excluded.result, yeas=excluded.yeas, nays=excluded.nays, "
        "abstentions=excluded.abstentions, bill_number=excluded.bill_number, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (key, "senate", parl, sess, v["vote_id"], v["date"], v["title"], v["result"],
         v["yeas"], v["nays"], v["abstentions"], v["bill_number"],
         json.dumps(res.issue_areas or []),
         json.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))
    return key


def store_positions(conn, key, senators, today):
    for s in senators:
        conn.execute(
            "INSERT INTO ca_senators (person_id, name, affiliation, province, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(person_id) DO UPDATE SET name=excluded.name, "
            "affiliation=excluded.affiliation, province=excluded.province, "
            "last_seen=excluded.last_seen",
            (s["person_id"], s["name"], s["affiliation"], s["province"], today, today))
        conn.execute("INSERT OR REPLACE INTO ca_votes (division_key, person_id, "
                     "position, party) VALUES (?,?,?,?)",
                     (key, s["person_id"], s["position"], s["affiliation"]))
    conn.execute("UPDATE ca_divisions SET positions_fetched=1 WHERE division_key=?", (key,))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def pull(conn, client, today, session=CURRENT_SESSION, tax=None, wl=None, log=print,
         limit=None, budget=None, all_positions=False):
    """Returns (listed, ours, fetched, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    parl, sess = parse_session(session)
    if (parl, sess) < FIRST_PUBLISHED:
        log("  {0}: the Senate publishes no recorded votes online before {1}-{2}; "
            "nothing to collect, and not a gap".format(session, *FIRST_PUBLISHED))
        return 0, 0, 0, 0
    votes = parse_list(client.get_text(LIST.format(session), FEED,
                                       "list-" + session, archive=False))
    if not votes:
        # A session with no recorded votes is possible on its first day and
        # on no other; a list we could not read looks identical.
        _gap(conn, today, "{0}: vote list had no rows (markup changed?)".format(session))
        conn.commit()
        log("  [gap] {0}: the vote list parsed to nothing".format(session))
        return 0, 0, 0, 1
    titles = long_titles(conn, parl, sess)
    ours = 0
    for v in votes:
        res = filt.filter_item(tax, wl, v["title"], titles.get(v["bill_number"]) or "")
        # A watched bill KEY tags its Senate votes too: same file, same keys.
        ca_store.add_bill_key_areas(res, parl, sess, v["bill_number"])
        store_vote(conn, parl, sess, v, res, today)
        ours += on_our_ground(res.issue_areas)
    conn.commit()
    want = conn.execute(
        "SELECT division_key, number, areas, yeas, nays, abstentions FROM ca_divisions "
        "WHERE chamber='senate' "
        "AND parliament=? AND session=? AND positions_fetched=0 ORDER BY number",
        (parl, sess)).fetchall()
    fetched = gaps = 0
    for key, vote_id, areas, yeas, nays, abstentions in want:
        if not all_positions and not on_our_ground(json.loads(areas or "[]")):
            continue
        if limit is not None and fetched >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("Senate vote details", fetched))
            break
        try:
            senators = parse_detail(client.get_text(DETAIL.format(vote_id, session), FEED,
                                                    "vote-{0}".format(vote_id), archive=False))
        except FetchError as exc:
            _gap(conn, today, "{0}: {1}".format(key, exc))
            log("  [gap] {0}: {1}".format(key, str(exc)[:70]))
            gaps += 1
            continue
        problem = check_against_tally(senators, yeas, nays, abstentions)
        if problem:
            _gap(conn, today, "{0}: {1}".format(key, problem))
            log("  [gap] {0}: {1}".format(key, problem))
            gaps += 1
            continue
        store_positions(conn, key, senators, today)
        conn.commit()
        fetched += 1
    return len(votes), ours, fetched, gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=CURRENT_SESSION)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--all-positions", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    args = ap.parse_args()
    parse_session(args.session)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    listed, ours, fetched, gaps = pull(conn, client, today, session=args.session,
                                       limit=args.limit, budget=drain.Budget(args.budget_seconds),
                                       all_positions=args.all_positions)
    print("ca-senate: {0}: {1} vote(s) listed, {2} on our ground, {3} position "
          "fetch(es), {4} gap(s).".format(args.session, listed, ours, fetched, gaps))
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    print("  store: {0} Senate vote(s), {1} with positions, {2} senator(s)".format(
        n("SELECT COUNT(*) FROM ca_divisions WHERE chamber='senate'"),
        n("SELECT COUNT(*) FROM ca_divisions WHERE chamber='senate' AND positions_fetched=1"),
        n("SELECT COUNT(*) FROM ca_senators")))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
