#!/usr/bin/env python3
"""Every period each sitting member has served in the Commons.

Built 2026-08-26, after Christopher spotted that Nigel Farage's page claimed
seven good votes while saying "MP since 13 Aug 2026".

WHAT WAS WRONG. `members.since` is the start of a member's CURRENT membership
period, which is what the roster endpoint gives. For the 643 members returned
at the 2024 general election that is 2024-07-04 regardless of how long they
have actually served, and for Farage -- who left on 2026-07-08 and returned on
2026-08-13 -- it is a date after every vote we hold for him.

Two things broke as a result, on the public page:

  * "MP since 4 July 2024" appeared on Diane Abbott's page. She has been an
    MP since 1987. 284 sitting members have votes in our ledger that predate
    their recorded `since`.
  * "NOT YET AN MP" excused absences. The rule was `since > division date`,
    so every member re-elected in 2024 who missed a 2020 division was
    credited with not having been in Parliament -- when many were sitting
    and simply did not vote. That is a false excuse in one direction and,
    for Farage, a page contradicting itself in the other.

Members/History carries houseMembershipHistory: every period, with its start,
its end, and the seat. Diane Abbott returns 10 periods from 1987-06-11.
Eligibility for a division is then a real question with a real answer -- did
any period cover that date -- rather than a guess from one date.

The endpoint batches by id and rejects 50, so it runs 20 at a time: about 33
requests for the House, a few minutes, and no cost. Free Parliament API.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import HttpClient

MEMBERS_API = "https://members-api.parliament.uk/api"
BATCH = 20          # 50 returns HTTP 400


def parse_history(value):
    """(member_id, [(started, ended, seat)]) from one History record.

    Commons only: a member who later went to the Lords has periods in both,
    and a Lords period never made them eligible to vote in a Commons
    division.
    """
    mid = value.get("id")
    out = []
    for period in (value.get("houseMembershipHistory") or []):
        if period.get("house") != 1:
            continue
        start = (period.get("membershipStartDate") or "")[:10]
        if not start:
            continue
        end = (period.get("membershipEndDate") or "")[:10] or None
        out.append((start, end, period.get("membershipFrom")))
    return mid, sorted(out)


def parse_parties(value):
    """(member_id, [(party, started, ended)]) from the same History record.

    A whip is a party instruction, so the party a member sat for ON THE DAY
    of a division is what decides whether a whip claim can be made about
    them. members.party is only today's, and defectors change mid-Parliament.
    """
    mid = value.get("id")
    out = []
    for spell in (value.get("partyHistory") or []):
        start = (spell.get("startDate") or "")[:10]
        name = (spell.get("party") or {}).get("name")
        if not start or not name:
            continue
        out.append((name, start, (spell.get("endDate") or "")[:10] or None))
    return mid, sorted(out, key=lambda x: x[1])


def store_parties(conn, mid, spells):
    conn.execute("DELETE FROM member_party WHERE member_id = ?", (mid,))
    for name, start, end in spells:
        conn.execute(
            "INSERT OR REPLACE INTO member_party (member_id, party, started, ended) "
            "VALUES (?,?,?,?)", (mid, name, start, end))


def store(conn, mid, periods):
    # Replace rather than upsert: a period's END date changes when a member
    # leaves, and a stale open-ended row would keep them eligible forever.
    conn.execute("DELETE FROM member_service WHERE member_id = ?", (mid,))
    for start, end, seat in periods:
        conn.execute(
            "INSERT OR REPLACE INTO member_service (member_id, started, ended, seat) "
            "VALUES (?,?,?,?)", (mid, start, end, seat))


def served_on(periods, date):
    """Was this member sitting on `date`?"""
    for start, end, _seat in periods:
        if start <= date and (end is None or date <= end):
            return True
    return False


def first_elected(periods):
    return min((p[0] for p in periods), default=None)


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM members WHERE current_mp = 1 ORDER BY id")]
    print("sitting members: {0}".format(len(ids)))

    done = gaps = 0
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        query = "&".join("ids={0}".format(x) for x in chunk)
        url = "{0}/Members/History?{1}".format(MEMBERS_API, query)
        try:
            payload = client.get_json(url, "members", "history-{0}".format(i))
        except Exception as exc:                      # noqa: BLE001
            # One bad batch must not lose the rest: the table is rebuilt per
            # member, so a partial run is safe to re-run.
            print("  batch {0}: FAILED {1}".format(i, exc))
            continue
        for record in payload:
            mid, periods = parse_history(record.get("value") or {})
            if mid is None or not periods:
                continue
            store(conn, mid, periods)
            pid, spells = parse_parties(record.get("value") or {})
            if pid is not None and spells:
                store_parties(conn, pid, spells)
            done += 1
            if len(periods) > 1:
                gaps += 1
        conn.commit()
        print("  {0}/{1}".format(min(i + BATCH, len(ids)), len(ids)))

    conn.commit()
    print("stored service history for {0} members "
          "({1} with more than one period)".format(done, gaps))

    # What this changes, stated rather than assumed.
    rows = conn.execute("""
        SELECT m.name, m.since, MIN(s.started) first
        FROM members m JOIN member_service s ON s.member_id = m.id
        WHERE m.current_mp = 1 GROUP BY m.id
        HAVING first < m.since ORDER BY first LIMIT 5""").fetchall()
    older = conn.execute("""
        SELECT COUNT(*) FROM (SELECT m.id FROM members m
        JOIN member_service s ON s.member_id = m.id WHERE m.current_mp = 1
        GROUP BY m.id HAVING MIN(s.started) < m.since)""").fetchone()[0]
    print("members whose service predates members.since: {0}".format(older))
    for r in rows:
        print("   {0:<24} since {1} -> first elected {2}".format(
            r["name"], r["since"], r["first"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
