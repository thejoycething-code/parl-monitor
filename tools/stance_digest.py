#!/usr/bin/env python3
"""The weekly "stances awaiting sign-off" digest: one Slack DM to Chris.

    python3 tools/stance_digest.py --print          # show it, send nothing
    python3 tools/stance_digest.py --dm             # send it (once a week)
    python3 tools/stance_digest.py --dm --force     # send again this week

Lists, by country, the 5CA readings in config/<cc>_stance.yaml that wait for
a named person (src/country5ca.py): proposed readings, procedural calls and
the votes that need reading, the newest proposed ones by key, and any boxes
ticked in a guide but not yet applied. Chris alone receives it (the DM goes
through country_edition.send_dm, which forces his id). It is sent at most
once per ISO week: the text is kept in data/stance-digest/<year>-W<week>.md,
and a week already there is not resent. Nothing waiting, nothing sent.

Runs in jobs/editions-session-judge.sh (Sundays 16:45 London, Mini only),
after the week's country weeklies and the drafting step.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402

STATE_DIR = os.path.join(ROOT, "data", "stance-digest")


def week_path(today, state_dir=None):
    y, w, _ = datetime.date.fromisoformat(today).isocalendar()
    return os.path.join(state_dir or STATE_DIR, "{0}-W{1:02d}.md".format(y, w))


def main(argv=None, send=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dm", action="store_true")
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--force", action="store_true", help="send even if sent this week")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--state-dir", default=STATE_DIR)
    args = ap.parse_args(argv)
    text = c5.digest_text(args.date)
    if text is None:
        print("stance digest: nothing awaits sign-off; nothing sent")
        return 0
    if args.print or not args.dm:
        print(text)
        if not args.dm:
            return 0
    path = week_path(args.date, args.state_dir)
    if os.path.exists(path) and not args.force:
        print("stance digest: already sent this week ({0}); not resent".format(
            os.path.relpath(path, ROOT) if path.startswith(ROOT) else path))
        return 0
    if send is None:
        from src import country_edition
        send = country_edition.send_dm
    result = send(text)
    print("stance digest dm: {0}".format(result))
    if isinstance(result, dict) and (result.get("error") or result.get("skipped")):
        return 1 if result.get("error") else 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as h:
        h.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
