#!/usr/bin/env python3
"""Croatia: party history from the Sabor's plenary transcripts (X6).

    python3 tools/hr_party_history.py                       # one budgeted run
    python3 tools/hr_party_history.py --budget-seconds 300
    python3 tools/hr_party_history.py --db /tmp/hr.db

WHY. The Sabor's vote service prints names and positions, no party, so
hr_votes.party_seen is the party in the member list when the vote was
collected (src/hr_store.py). Chris's X6 (10 October 2026): source party
history before relying on party at the vote. The transcripts are that
source: every contribution in edoc.sabor.hr's FonogramView is headed
"Surname, Name (PARTY)" under the day's date ("29.09.2026."), so each
heading is a dated sighting of the speaker's party, in the Sabor's own words.
src/member_profiles.py folds the sightings into spells and states, for each
vote, the party seen in debate around it, or says it does not know.

THE WALK. Transcript ids (tdrid) are one sequence across the e-Doc system;
the 11th Sabor's run from 2016676 (22 May 2024, measured 10 October 2026).
The list page (Fonogrami.aspx) shows the ten newest transcripts and pages by
script, so it is read once for the newest id (the frontier) and the walk
reads ids, newest first, from just above the frontier down to START,
skipping ids already read. An id with no transcript yet (an agenda
item announced, not debated) is stored with saziv NULL and re-read while it
is within RECHECK of the newest id read: an item is numbered before its
debate. A clock budget (src/drain.py) stops the walk cleanly; the next run
resumes from the store. Contributions from another saziv's transcript are
not read as party history for this one.

WHAT IS STORED. hr_transcripts (one row per id read) and hr_party_seen (one
row per member, day and party, the heading's party verbatim). A heading is
kept only when its "Surname, Name" is exactly one hr_members name of the
same saziv; ministers and guests have no party heading or no member row and
are not stored. Nothing else is written; robots.txt on edoc.sabor.hr is
absent (404, 10 October 2026), www.sabor.hr's disallows none of this.

Exit 0 when the run stored what it read, 3 when it recorded gaps.
"""

from __future__ import annotations

import argparse
import datetime
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "hr-transcripts"
HOST = "edoc.sabor.hr"
VIEW = "https://edoc.sabor.hr/Views/FonogramView.aspx?tdrid={0}&type=HTML"
LIST = "https://edoc.sabor.hr/Fonogrami.aspx"
START = 2016676            # first transcript of the 11th Sabor (22 May 2024)
SAZIV = "XI"
SAZIV_NO = 11
LOOKAHEAD = 40             # ids tried above the newest read
RECHECK = 300              # an empty id this close to the newest is re-read
THROTTLE_S = 1.0
DEFAULT_BUDGET_S = 900.0

_DAY = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\.?\s*$")
_HEAD = re.compile(r"^\s*([^\n()<>]{3,80}?,\s*[^\n()<>]{2,60}?)\s*\(([^()\n<>]{1,40})\)\s*$")
_SAZIV = re.compile(r"Saziv:\s*([IVXLC]+),\s*sjednica:\s*(\d+)")


def fold(text):
    """Case-, accent- and space-insensitive name key."""
    from src.noise import fold as _fold
    return " ".join(_fold(text or "").lower().replace(",", " , ").split())


def lines_of(page):
    """The transcript page as text lines, tags dropped."""
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page or "", flags=re.S | re.I)
    page = re.sub(r"<br\s*/?>|</(p|div|h\d|li|tr|td|span)>", "\n", page, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    return [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in text.split("\n") if ln.strip()]


def parse(page):
    """{'saziv', 'session_no', 'title', 'sightings': [(name, party, iso_date)]}
    or None when the page holds no transcript."""
    m = _SAZIV.search(page or "")
    if not m:
        return None
    lines = lines_of(page)
    out = {"saziv": m.group(1), "session_no": m.group(2), "title": None, "sightings": []}
    day = None
    for i, ln in enumerate(lines):
        d = _DAY.match(ln)
        if d:
            try:
                day = datetime.date(int(d.group(3)), int(d.group(2)), int(d.group(1))).isoformat()
            except ValueError:
                pass
            continue
        h = _HEAD.match(ln)
        if h and day:
            out["sightings"].append((h.group(1).strip(), h.group(2).strip(), day))
        elif out["title"] is None and day is None and len(ln) > 25 and not ln.startswith(
                ("Saziv", "Rasprave", "Povratak", ".")):
            out["title"] = ln[:400]
    return out


def members(conn, saziv_no=SAZIV_NO):
    """{folded 'Surname, Name': slug} for one saziv; a name two members share
    maps to None and is never used."""
    out = {}
    for slug, name in conn.execute("SELECT slug, name FROM hr_members WHERE saziv = ?",
                                   (saziv_no,)):
        k = fold(name)
        out[k] = None if k in out else slug
    return out


def store(conn, tdrid, got, roster, today):
    """Write one transcript's row and its sightings; returns sightings kept."""
    if got is None:
        conn.execute("INSERT OR REPLACE INTO hr_transcripts (tdrid, saziv, session_no, title, "
                     "first_date, last_date, speakers, read_at) VALUES (?,NULL,NULL,NULL,NULL,"
                     "NULL,0,?)", (tdrid, today))
        return 0
    kept = 0
    days = sorted({d for _, _, d in got["sightings"]})
    if got["saziv"] == SAZIV:
        for name, party, day in got["sightings"]:
            slug = roster.get(fold(name))
            if not slug:
                continue
            conn.execute("INSERT INTO hr_party_seen (slug, date, party, tdrid) VALUES (?,?,?,?) "
                         "ON CONFLICT(slug, date, party) DO UPDATE SET tdrid = excluded.tdrid",
                         (slug, day, party, tdrid))
            kept += 1
    conn.execute("INSERT OR REPLACE INTO hr_transcripts (tdrid, saziv, session_no, title, "
                 "first_date, last_date, speakers, read_at) VALUES (?,?,?,?,?,?,?,?)",
                 (tdrid, got["saziv"], got["session_no"], got["title"],
                  days[0] if days else None, days[-1] if days else None,
                  len(got["sightings"]), today))
    return kept


def frontier(page):
    """The newest transcript id on the list page, or None."""
    ids = [int(x) for x in re.findall(r"FonogramView\.aspx\?tdrid=(\d+)", page or "")]
    return max(ids) if ids else None


def todo(conn, start=START, lookahead=LOOKAHEAD, recheck=RECHECK, newest=None):
    """Ids to read, newest first: unread ids from START to just above the
    newest transcript (the list page's, or the newest read), and empty ids
    within RECHECK of it."""
    read = dict(conn.execute("SELECT tdrid, saziv FROM hr_transcripts WHERE tdrid >= ?",
                             (start,)).fetchall())
    found = [t for t, s in read.items() if s]
    top = max([start] + found + ([newest] if newest else []))
    out = []
    for t in range(top + lookahead, start - 1, -1):
        if t not in read:
            out.append(t)
        elif not read[t] and t >= top - recheck:
            out.append(t)
    return out


def run(conn, client, today, budget=None, log=print, limit=None):
    """Returns (read, transcripts, sightings, gaps)."""
    roster = members(conn)
    if not roster:
        log("  hr-party-history: no members of the {0}th Sabor stored yet; nothing to match"
            .format(SAZIV_NO))
        return 0, 0, 0, 0
    read = found = kept = gaps = 0
    try:
        newest = frontier(client.get_text(LIST, FEED, "fonogrami"))
    except FetchError as exc:
        log("  [gap] transcript list: {0}; walking from the newest id read".format(
            str(exc)[:80]))
        newest, gaps = None, 1
    for tdrid in todo(conn, newest=newest):
        if limit is not None and read >= limit:
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("transcripts", read))
            break
        try:
            page = client.get_text(VIEW.format(tdrid), FEED, "fonogram-{0}".format(tdrid))
        except FetchError as exc:
            log("  [gap] transcript {0}: {1}".format(tdrid, str(exc)[:80]))
            gaps += 1
            continue
        got = parse(page)
        kept += store(conn, tdrid, got, roster, today)
        read += 1
        found += 1 if got else 0
        if read % 25 == 0:
            conn.commit()
    conn.commit()
    return read, found, kept, gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--budget-seconds", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many transcript fetches")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    client.enable_gzip(HOST)
    conn = db.init_db(db.connect(args.db))
    today = datetime.date.today().isoformat()
    read, found, kept, gaps = run(conn, client, today, drain.Budget(args.budget_seconds),
                                  limit=args.limit)
    total = conn.execute("SELECT COUNT(*), COUNT(DISTINCT slug) FROM hr_party_seen").fetchone()
    print("hr-party-history: {0} id(s) read, {1} transcript(s), {2} party sighting(s) kept; "
          "{3} sighting(s) of {4} member(s) stored in all; {5} gap(s)".format(
              read, found, kept, total[0], total[1], gaps))
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
