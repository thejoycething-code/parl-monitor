#!/usr/bin/env python3
"""Put a debate pack's deliverables on Google Drive and record the folder link.

    python3 tools/drive_pack.py --pack data/packs/<folder> [--dry-run]

Reel, full-speech clips (subtitled), .srt files, contact sheet, report, selection and
the cut logs go to "Debate footage / <date> <title>" in the Automated Briefs shared
drive. Idempotent. The folder URL lands in pack.json ("drive"), and
tools/debate_report.py --publish links it from the canvas. Footage is Parliament's
under the Parliamentary Recording Unit's terms; the folder is internal.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import drivepack  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true", help="bin clips on Drive the cutters named but the pack no longer has")
    args = ap.parse_args()
    url, done = drivepack.publish(args.pack.rstrip("/"), log=print, dry_run=args.dry_run, prune=args.prune)
    n_up = sum(1 for d in done if not d.get("skipped")); n_skip = sum(1 for d in done if d.get("skipped"))
    print("%s\n%d uploaded, %d already there" % (url, n_up, n_skip))


if __name__ == "__main__":
    main()
