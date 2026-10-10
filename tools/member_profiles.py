#!/usr/bin/env python3
"""Member profiles for a new country edition, from its store (src/member_profiles.py).

    python3 tools/member_profiles.py pl                 # profiles/pl/, the weekly step
    python3 tools/member_profiles.py pl hr cl           # several countries
    python3 tools/member_profiles.py hr --db /tmp/hr.db --out /tmp/p --sample

One Markdown profile per member with a record on our ground (votes, bills
authored, questions), and profiles/<cc>/index.md listing every member. The
directory is rewritten each run: a member who no longer has a record loses
their file. Read-only on the store; nothing is posted or DMed. Run as the
step after the collector in each country's weekly job (jobs/<cc>-weekly.sh),
which commits profiles/ with the editions (# mini_run: commit ... profiles).

Exit 0 when every country rendered, 1 when one failed (its error printed;
the others still rendered).
"""

from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import member_profiles as mp  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("countries", nargs="+", help="country codes: " + " ".join(mp.COUNTRIES))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out", default=os.path.join(ROOT, "profiles"))
    ap.add_argument("--date", default=datetime.date.today().isoformat(),
                    help="the store's reading date (default today)")
    ap.add_argument("--sample", action="store_true",
                    help="mark every file SAMPLE (a scoping store, never published)")
    args = ap.parse_args(argv)
    bad = [c for c in args.countries if c not in mp.SPECS]
    if bad:
        ap.error("no profile spec for: " + ", ".join(bad))
    if not os.path.exists(args.db):
        print("member-profiles: no store at {0}".format(args.db))
        return 1
    conn = sqlite3.connect("file:{0}?mode=ro".format(args.db), uri=True)
    rc = 0
    for cc in args.countries:
        try:
            data = mp.build(conn, cc, args.date)
            written, removed = mp.write(data, args.out, sample=args.sample)
        except Exception:  # one country's failure never costs the others
            traceback.print_exc()
            print("  [gap] member-profiles {0}: failed; nothing written for it".format(cc))
            rc = 1
            continue
        members = data["members"].values()
        print("member-profiles {0}: {1} member(s), {2} profile(s) written to {3}/{0}/, {4} "
              "removed; {5} vote(s) on our ground, {6} position(s), {7} authored, {8} "
              "question(s){9}".format(
                  cc, len(data["members"]), written, os.path.relpath(args.out, ROOT)
                  if args.out.startswith(ROOT) else args.out, removed, data["votes"],
                  sum(len(m.votes) for m in members), sum(len(m.authored) for m in members),
                  sum(len(m.questions) for m in members), " [sample]" if args.sample else ""))
    conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
