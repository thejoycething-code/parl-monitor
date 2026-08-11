"""Pull the full Commons roster into the members cache.

    python3 tools/pull_commons_roster.py

Flags every sitting MP current_mp=1 (clearing old flags, so departed MPs
drop off) and refreshes name/party/seat. Full-roster 5CA sheets
(tools/make_5ca.py) select on this flag. ~33 Members API calls; re-run
after by-elections or whenever the roster feels stale.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, members
from src.http import HttpClient


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    roster = members.fetch_commons_roster(client)
    members.mark_roster(conn, roster)
    peers = members.fetch_lords_roster(client)
    members.mark_roster(conn, peers, flag="current_peer")
    print("roster: {0} sitting MPs, {1} sitting peers".format(len(roster), len(peers)))
    parties = {}
    for m in roster:
        parties[m.party] = parties.get(m.party, 0) + 1
    for party, n in sorted(parties.items(), key=lambda kv: -kv[1]):
        print("  {0}: {1}".format(party, n))
    conn.close()


if __name__ == "__main__":
    main()
