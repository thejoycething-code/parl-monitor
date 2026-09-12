#!/usr/bin/env python3
"""Our MP-named campaigns against the record: who we targeted, where they sit now.

    python3 tools/campaign_targets.py [--area N]

Reads campaign_performance for petitions named after a member ("Tell Clive Lewis:
No to assisted suicide", "Urge Sarah Pochin to vote no..."), matches them to the
members cache, and prints each target's current 5CA column on the area with the
WAVERING flag if set. The same matching feeds the TARGETED comment on every 5CA
row. Christopher, 12 Sept 2026: the cross-check done by hand after the Second
Reading, as a standing column.

Refreshing the campaign log is a by-hand step (no Looker credential in CI): ask Max
in #campaigns-en-gb for the lifetime numbers and run tools/log_campaign_performance.py
on his reply, or pull the Looker export and run tools/load_looker_campaigns.py.
Weekly is enough; the targets list only changes when a campaign launches.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, stance  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", type=int, default=2)
    args = ap.parse_args()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    targets = stance.campaign_targets(conn)
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    rows = {r["member_id"]: r for r in stance.suggest_rows(conn, args.area, full_roster=True, overrides_cfg=cfg)}
    print("%d members targeted by name; area %d placement today:" % (len(targets), args.area))
    for mid, camps in sorted(targets.items(), key=lambda kv: kv[1][0][1] or ""):
        r = rows.get(mid)
        name = conn.execute("SELECT name FROM members WHERE id = ?", (mid,)).fetchone()
        print("  %-24s %-3s %-9s %s" % ((name[0] if name else mid), r["column"] if r else "?",
                                       ("WAVERING" if r and r.get("wavering") else ""),
                                       "; ".join("%s (%s)" % (c[:48], (d or "")[:7]) for c, d in camps)))


if __name__ == "__main__":
    main()
