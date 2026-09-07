"""Run the 2026-09-07 sources for one edition week, outside the Sunday pull.

    python3 tools/pull_sources.py --week 2026-09-07 [--only amendments,reports,judgments,oral,regulators,petitions]

Same functions the Sunday pull calls (run_weekly.sweep_*), so this is the
seed run and the re-run tool, not a second implementation. ONE WRITER AT A
TIME: pull the store first, push it after. Items land unscored and are
judged by the next pull.
"""

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import run_weekly
from src import db, filter as filt
from src.http import HttpClient


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", required=True, help="edition Monday, YYYY-MM-DD")
    ap.add_argument("--only", default="amendments,reports,judgments,oral,regulators,petitions,sections,links")
    args = ap.parse_args()
    week_start = datetime.date.fromisoformat(args.week)
    rs, re_ = week_start - datetime.timedelta(days=7), week_start - datetime.timedelta(days=1)
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    only = set(args.only.split(","))
    calls = {
        "amendments": lambda: run_weekly.sweep_amendments(client, conn, tax, wl, week_start, args.week),
        "reports": lambda: run_weekly.sweep_reports(client, conn, tax, wl, rs, re_, args.week),
        "judgments": lambda: run_weekly.sweep_judgments(client, conn, tax, wl, rs, re_, args.week),
        "oral": lambda: run_weekly.sweep_oral(client, conn, tax, wl, rs, re_, args.week),
        "regulators": lambda: run_weekly.sweep_regulators(client, conn, tax, wl, args.week),
        "sections": lambda: run_weekly.sweep_hansard_sections(client, conn, rs, re_),
        "links": lambda: run_weekly.link_whatson_to_hansard(conn, datetime.date.today()),
    }
    for name, call in calls.items():
        if name not in only:
            continue
        try:
            call()
        except Exception as exc:                            # noqa: BLE001
            print("{0}: FAILED {1}".format(name, exc))
    if "petitions" in only:
        import importlib.util
        spec = importlib.util.spec_from_file_location("dvp", os.path.join(ROOT, "tools", "dv_petitions.py"))
        dvp = importlib.util.module_from_spec(spec); spec.loader.exec_module(dvp)
        for nation in ("wales", "scotland"):
            try:
                dvp.sweep(nation, client, conn, tax, wl, datetime.date.today())
            except Exception as exc:                        # noqa: BLE001
                print("{0} petitions: FAILED {1}".format(nation, exc))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
