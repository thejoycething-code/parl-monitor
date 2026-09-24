#!/usr/bin/env python3
"""Who a German parliamentarian is in the House: seat, list, committees.

    python3 tools/de_profiles.py                 # the next batch, priority first
    python3 tools/de_profiles.py --limit 400
    python3 tools/de_profiles.py --all           # everyone, a deliberate backfill
    python3 tools/de_profiles.py --dry-run

Christopher, 24 September 2026: "Build member profiles." de_members held a
name, a party and a parliament and nothing else, so the monitor could say
what a member said and not who they are -- and a campaigner cannot act on a
stance placement without knowing whether the member answers to a
constituency.

WHAT IS COLLECTED, AND WHAT IS NOT. Official, role-related, public: the
abgeordnetenwatch politician id and public profile, the constituency, the
electoral list, whether the seat was won directly or from a list, and
committee memberships with their roles. NOTHING PERSONAL -- no date of
birth, no biography, no private contact. The API offers more than this and
the extra is deliberately left where it is.

MANDATE_WON IS THE FIELD THAT MATTERS. A directly elected member answers to a
place and its voters; a list member does not, and a supporter writing to them
as "my MP" is writing to someone who was never theirs. That distinction
changes who a campaign can usefully mobilise, and it is one field.

PRIORITY ORDER, BECAUSE 2,517 MANDATES IS TOO MANY. Members we can already
say something about come first: those with a stance placement from their own
words, then those who voted in a matched division that is not migration-only.
That is about 281 people -- the ones a campaigner might actually contact --
against 2,517 rows, most of them Land members who have never touched our
ground. The rest fill in over later runs.

INCREMENTAL, like tools/eu_meps_enrich.py: a member with a politician_id is
skipped, so after the first passes this costs new arrivals only. person_id is
a MANDATE id and politician_id is the person, so a member re-elected appears
as a new mandate with the same politician_id -- which is what will let service
be followed across terms when there is a second term to follow.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

API = "https://www.abgeordnetenwatch.de/api/v2"
MANDATE = API + "/candidacies-mandates/{0}"
COMMITTEES = API + "/committee-memberships?candidacy_mandate={0}&range_end=50"

# One run's worth. Two calls per member, so a cap of 150 is about 300
# requests -- minutes, not an hour. The weekly picks up where the last left
# off because the skip is "has a politician_id".
BATCH = 150

# Members we can already say something about, hardest evidence first. A
# stance placement means we have their own words; a vote in a matched,
# non-migration division means we know how they acted. Everyone else is a
# name we have never had cause to look at.
PRIORITY_SQL = """
SELECT m.person_id FROM de_members m WHERE m.politician_id IS NULL AND (
    EXISTS (SELECT 1 FROM de_speeches s JOIN stance st
            ON st.ref = 'de-speech:' || s.speech_id
            WHERE s.person_id = m.person_id)
    OR EXISTS (SELECT 1 FROM de_votes v JOIN de_divisions d
               ON d.vote_id = v.vote_id
               WHERE v.person_id = m.person_id AND d.areas IS NOT NULL
               AND d.areas != '[]' AND d.areas NOT LIKE '%11%')
)
"""
REST_SQL = "SELECT person_id FROM de_members WHERE politician_id IS NULL"


def targets(conn, limit, everyone=False):
    """person_ids to fetch, the ones we can say something about first."""
    first = [r[0] for r in conn.execute(PRIORITY_SQL)]
    if not everyone and len(first) >= limit:
        return first[:limit], len(first)
    rest = [r[0] for r in conn.execute(REST_SQL) if r[0] not in set(first)]
    wanted = first + rest
    return (wanted if everyone else wanted[:limit]), len(first)


def profile_of(doc):
    """The official fields, and only those."""
    m = (doc or {}).get("data") or {}
    pol = m.get("politician") or {}
    ed = m.get("electoral_data") or {}
    constituency = (ed.get("constituency") or {}).get("label") \
        if ed.get("constituency") else None
    lst = (ed.get("electoral_list") or {}).get("label") \
        if ed.get("electoral_list") else None
    return {
        "politician_id": str(pol["id"]) if pol.get("id") is not None else None,
        "profile_url": pol.get("abgeordnetenwatch_url"),
        "constituency": constituency,
        "electoral_list": lst,
        "mandate_won": ed.get("mandate_won"),
    }


def committees_of(doc):
    """[(committee, role)] -- the role verbatim, never normalised."""
    out = []
    for r in (doc or {}).get("data") or []:
        label = (r.get("committee") or {}).get("label")
        if label:
            out.append((label, r.get("committee_role")))
    return out


def pull(conn, client, today, limit=BATCH, everyone=False, log=print,
         dry_run=False):
    wanted, priority_total = targets(conn, limit, everyone)
    done = failed = committees = 0
    for person_id in wanted:
        try:
            doc = client.get_json(MANDATE.format(person_id), "de-profiles",
                                  "m-" + str(person_id), archive=False)
        except (FetchError, ValueError) as exc:
            log("  [gap] mandate {0}: {1}".format(person_id, str(exc)[:60]))
            failed += 1
            continue
        got = profile_of(doc)
        if not got["politician_id"]:
            # No politician on the mandate: real for a vacant or historic
            # seat. Counted, not retried for ever -- but NOT written as a
            # blank politician_id, or the skip would swallow it silently.
            log("  [gap] mandate {0}: no politician attached".format(person_id))
            failed += 1
            continue
        if dry_run:
            done += 1
            continue
        conn.execute(
            "UPDATE de_members SET politician_id = ?, profile_url = ?, "
            "constituency = ?, electoral_list = ?, mandate_won = ?, "
            "last_seen = ? WHERE person_id = ?",
            (got["politician_id"], got["profile_url"], got["constituency"],
             got["electoral_list"], got["mandate_won"], today, person_id))
        try:
            cdoc = client.get_json(COMMITTEES.format(person_id), "de-profiles",
                                   "c-" + str(person_id), archive=False)
        except (FetchError, ValueError) as exc:
            log("  [gap] committees {0}: {1}".format(person_id, str(exc)[:60]))
            cdoc = None
        for committee, role in committees_of(cdoc):
            conn.execute(
                "INSERT INTO de_affiliations (person_id, committee, role, "
                "first_seen, last_seen) VALUES (?,?,?,?,?) "
                "ON CONFLICT(person_id, committee) DO UPDATE SET "
                "role=excluded.role, last_seen=excluded.last_seen",
                (person_id, committee, role, today, today))
            committees += 1
        done += 1
    if not dry_run:
        conn.commit()
    return done, failed, committees, priority_total


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=BATCH)
    ap.add_argument("--all", action="store_true",
                    help="every unprofiled member, a deliberate backfill")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    today = datetime.date.today().isoformat()

    done, failed, committees, priority = pull(
        conn, client, today, limit=args.limit, everyone=args.all,
        dry_run=args.dry_run)
    left = conn.execute("SELECT COUNT(*) FROM de_members WHERE politician_id "
                        "IS NULL").fetchone()[0]
    # RECOUNTED AFTER THE RUN. The first version printed the priority figure
    # measured BEFORE fetching, so a run that profiled all 281 priority
    # members reported "2236 still unprofiled (281 of them are members we
    # can already say something about)" -- describing work it had just
    # finished as still outstanding. A run must not be wrong about itself.
    _, priority_left = targets(conn, limit=0, everyone=True)
    print("de-profiles: {0} member(s) profiled, {1} committee seat(s) "
          "recorded, {2} unreadable; {3} still unprofiled, {4} of them "
          "members we can already say something about{5}.".format(
              done, committees, failed, left, priority_left,
              " [dry run]" if args.dry_run else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
