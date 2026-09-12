#!/usr/bin/env python3
"""Read a debate mid-flight and name the members whose words contradict their votes.

    python3 tools/live_debate.py --date 2026-09-11 --find "Terminally Ill Adults" --area 2 [--dm]

Builds or refreshes the pack (tools/debate_pack.py; the stance read is cached per
speaker, so only new speakers cost a call), then compares each speaker's reading
with their last vote on the area and prints WOBBLE / SLIP lines; --dm sends them to
Christopher. Run at lunchtime and again before the division. Store: pull before, push
after (the pack build records its spend).
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, livedebate, publish, socialcut as sc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True); ap.add_argument("--find", required=True)
    ap.add_argument("--house", default="Commons"); ap.add_argument("--area", type=int, required=True)
    ap.add_argument("--pack", help="an existing pack folder; skips the build")
    ap.add_argument("--dm", action="store_true")
    args = ap.parse_args()
    pack = args.pack
    if not pack:
        out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "debate_pack.py"), "--date", args.date, "--find", args.find, "--house", args.house],
                             capture_output=True, text=True)
        print(out.stdout.strip()[-600:])
        for line in out.stdout.splitlines():
            if line.startswith("pack: "):
                pack = os.path.join(ROOT, line.split("pack: ", 1)[1].strip())
        if not pack:
            raise SystemExit("no pack built: " + (out.stderr or out.stdout)[-300:])
    meta = json.load(open(os.path.join(pack, "pack.json")))
    speeches = sc.parse_speeches(open(os.path.join(pack, "speeches.md"), encoding="utf-8").read())
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    found = livedebate.wobbles(conn, meta, speeches, args.area)
    conn.close()
    text = livedebate.dm_text(meta, speeches, found, as_of=datetime.datetime.now().strftime("%H:%M"))
    print(text)
    if args.dm:
        r = publish.slack_dm(publish.load_secrets(), text)
        print("DM:", r.get("message_ts") or r)


if __name__ == "__main__":
    main()
