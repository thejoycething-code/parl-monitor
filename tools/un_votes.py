"""Recorded votes from an HRC session report: who voted how, on what.

    python3 tools/un_votes.py 58              # harvest session 58
    python3 tools/un_votes.py 58 --state Cuba # then how one state voted

The UN analogue of the Commons vote tracker, and unlike the UPR tracker it is
CURRENT: a session report is published within weeks of the session closing.

Subjects come from un_documents where the draft has already been read, so a
vote reads as "L.30/Rev.1 — Promotion and protection of the rights of
children — 27 for, 4 against, 16 abstaining" rather than as a bare symbol.
Harvest the drafts first (tools/un_drafts.py --hrc 58) to get subjects.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import HttpClient
from src.ingest import un_docs, un_votes as votes_mod

# The Council has 47 members. A tally may be LOWER (an absent member appears
# in none of the three lists) but never higher, so this is a ceiling check on
# the parse rather than an equality test.
COUNCIL_SIZE = 47


def store(conn, report, votes, today):
    for v in votes:
        for position, group in (("for", v.favour), ("against", v.against),
                                ("abstain", v.abstaining)):
            for state in group:
                conn.execute(
                    "INSERT INTO un_votes (report, draft, state, position, captured_at) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT(report, draft, state) "
                    "DO UPDATE SET position=excluded.position",
                    (report, v.draft, state, position, today))
    conn.commit()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    session = int(args[0]) if args else 58
    state = None
    if "--state" in sys.argv:
        state = sys.argv[sys.argv.index("--state") + 1]

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    print("reading A/HRC/{0}/2 (session reports run to ~200 pages)".format(session),
          flush=True)
    try:
        votes, report = votes_mod.fetch_session_votes(client, session, un_docs)
    except Exception as exc:
        print("could not read the report: {0}".format(str(exc)[:90]))
        return 1
    if not votes:
        print("no recorded votes found in {0}. Either the session took every "
              "text without a vote, or the report layout has changed -- check "
              "before believing the former.".format(report))
        return 1

    suspect = [v for v in votes if sum(v.tally) > COUNCIL_SIZE]
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    stored = {r["symbol"]: r for r in
              conn.execute("SELECT symbol, subject, title, kind, amends, areas, "
                           "agenda_item FROM un_documents")}

    def lookup(draft):
        """Topic/areas for a draft, falling back to the unrevised symbol.

        Prefers the draft's OWN title over the agenda item title: HRC item 3
        is an omnibus, so the item title says nothing about the text voted on.
        """
        row = stored.get(draft) or stored.get(votes_mod.base_symbol(draft))
        if not row:
            return (None, None, None, None, None)
        return (row["title"] or row["subject"], row["areas"], row["agenda_item"],
                row["kind"], row["amends"])
    store(conn, report, votes, datetime.date.today().isoformat())

    import json
    print("\n{0} recorded vote(s) in {1}\n".format(len(votes), report))
    joined = 0
    for v in votes:
        subject, areas_json, item, kind, amends = lookup(v.draft)
        areas = json.loads(areas_json or "[]")
        if subject:
            joined += 1
        mark = "OURS" if areas else "    "
        print("{0}  {1:<22} {2:>2} for / {3:>2} against / {4:>2} abstaining".format(
            mark, v.draft or "?", *v.tally))
        label = kind or "?"
        if amends:
            label += " to " + amends
        print("        {0:<28} {1}".format(
            label, (subject or "(unknown - run un_drafts.py)")[:56]))
        if areas:
            print("        areas {0}   against: {1}".format(
                ",".join(str(a) for a in areas), ", ".join(v.against[:6]) or "none"))
    print("\njoined to a subject: {0} of {1}".format(joined, len(votes)))
    if suspect:
        print("\nWARNING: {0} block(s) exceed the {1}-member Council, which means "
              "the parse picked up something that is not a state.".format(
                  len(suspect), COUNCIL_SIZE))

    if state:
        print("\n{0}:".format(state))
        rows = conn.execute(
            "SELECT draft, position FROM un_votes WHERE report = ? AND state = ? "
            "ORDER BY draft", (report, state)).fetchall()
        if not rows:
            print("  not recorded in this session -- absent, or not a member.")
        for r in rows:
            print("  {0:<22} {1:<8} {2}".format(
                r["draft"], r["position"], (lookup(r["draft"])[0] or "")[:50]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
