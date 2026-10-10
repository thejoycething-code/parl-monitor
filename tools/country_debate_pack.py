#!/usr/bin/env python3
"""Build a debate pack for one debate in a new country (src/country_debatepack.py).

    python3 tools/country_debate_pack.py --country it --date 2026-10-14 --list
    python3 tools/country_debate_pack.py --country it --date 2026-10-14 --find "consenso informato"
    python3 tools/country_debate_pack.py --country it --date 2026-10-14 --item 19/S.1735
        [--speakers "Lucio Malan; Simona Malpezzi"] [--chamber senato] [--topic-votes 6]
        [--since 2025-01-01] [--db PATH] [--out DIR] [--dry-run] [--sample]
    python3 tools/country_debate_pack.py --pack data/packs/it-2026-10-14-... --onside

A manual command, like tools/debate_pack.py (UK) and tools/de_debate_pack.py
(Germany): no scheduled job. Reads the store read-only; fetches nothing, calls
no AI, posts nothing. Writes data/packs/<cc>-<date>-<slug>/.

--find narrows by the item's own words or keys; --item names the bill,
dossier or division key exactly (by ID, never by title). When several
subjects match, they are listed and nothing is written: rerun with --item.
--list shows the subjects on our ground around the date (upcoming agenda
points and the recent items) and stops.

Placements come only from readings a named person has confirmed in
config/<cc>_stance.yaml; until then the pack says "awaiting sign-off".

Countries: {countries}.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import country_debatepack as dp  # noqa: E402

__doc__ = __doc__.format(countries=", ".join(dp.COUNTRIES))


def show(subject, n=None):
    dates = sorted(subject["dates"])
    when = "{0}..{1}".format(dates[0], dates[-1]) if len(dates) > 1 else (dates[0] if dates else "-")
    kinds = sorted({c.get("kind") or c["source"] for c in subject["cands"]})
    print("  {0}{1:<22} {2:<23} {3}{4} [{5}] {6}".format(
        "{0:>2}. ".format(n) if n else "", dp.clip(subject["subject"], 22), when,
        "watched " if subject["watched"] else "", ",".join(str(a) for a in subject["areas"]) or "-",
        "/".join(kinds), dp.clip(subject["title"], 70)))


def onside(folder):
    rows = dp.parse_checklist(os.path.join(folder, "checklist.md"))
    yes = [r for r in rows if r[2]]
    print("onside: {0} line(s) answered; {1} yes".format(len(rows), len(yes)))
    for kind, name, ok, note in rows:
        print("  {0:<7} {1:<34} {2}{3}".format(kind, name[:34], "yes" if ok else "no",
                                               "  " + note if note else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--country", help="country code")
    ap.add_argument("--date", help="the debate date, YYYY-MM-DD (default today)")
    ap.add_argument("--find", help="narrow to subjects whose words or keys contain this")
    ap.add_argument("--item", help="the bill, dossier or division key, exactly")
    ap.add_argument("--list", action="store_true", help="list subjects around the date and stop")
    ap.add_argument("--since", help="earliest item date to search (default a year before --date)")
    ap.add_argument("--speakers", help="names on the speakers' list, separated by ';'")
    ap.add_argument("--chamber", help="the chamber (the store's code); default the bill's last vote")
    ap.add_argument("--topic-votes", type=int, default=dp.TOPIC_VOTES)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--config-dir", help="config directory (default config/)")
    ap.add_argument("--out", help="pack folder (default data/packs/<cc>-<date>-<slug>/)")
    ap.add_argument("--dry-run", action="store_true", help="find and count; write nothing")
    ap.add_argument("--sample", action="store_true", help="mark the pack SAMPLE (a scoping store)")
    ap.add_argument("--today", help="the build date stamped on the pack (default today)")
    ap.add_argument("--pack", help="an existing pack folder")
    ap.add_argument("--onside", action="store_true", help="with --pack: report the checklist")
    args = ap.parse_args(argv)

    if args.pack and args.onside:
        return onside(args.pack)
    cc = (args.country or "").strip().lower()
    if cc not in dp.COUNTRIES:
        ap.error("--country is one of: " + ", ".join(dp.COUNTRIES))
    date = args.date or datetime.date.today().isoformat()
    if not os.path.exists(args.db):
        print("country-debate-pack: no store at {0}".format(args.db))
        return 1
    conn = c5.connect_ro(args.db)
    try:
        if args.list:
            subs = dp.find_subjects(conn, cc, date, since=args.since or dp._plus(date, -30),
                                    config_dir=args.config_dir)
            print("{0}: {1} subject(s) on our ground from {2} to {3}".format(
                cc, len(subs), args.since or dp._plus(date, -30), dp._plus(date, dp.AHEAD_DAYS)))
            for i, s in enumerate(subs, 1):
                show(s, i)
            return 0
        if not (args.find or args.item):
            ap.error("--find, --item or --list is required")
        subs = dp.find_subjects(conn, cc, date, args.find, args.item, args.since, args.config_dir)
        if not subs:
            print("nothing on our ground matches {0} for {1} around {2}. --list shows what "
                  "there is.".format(repr(args.item or args.find), cc, date))
            return 1
        if len(subs) > 1:
            print("several subjects match; name one with --item:")
            for i, s in enumerate(subs, 1):
                show(s, i)
            return 1
        subject = subs[0]
        speakers = [s.strip() for s in (args.speakers or "").split(";") if s.strip()]
        pack = dp.assemble(conn, cc, date, subject, chamber=args.chamber, speakers=speakers,
                           config_dir=args.config_dir, today=args.today,
                           topic_limit=args.topic_votes)
    finally:
        conn.close()

    print("{0} {1}: {2}".format(cc, subject["subject"], dp.clip(pack["title"], 90)))
    print("  {0} vote(s) on the bill ({1} decisive), {2} topic vote(s), {3} agenda point(s) "
          "[agenda {4}], {5} member(s), {6} to watch, {7} confirmed reading(s)".format(
              len(pack["bill_votes"]), len(pack["decisive"]), len(pack["topic_votes"]),
              len(pack["agenda"]), pack["agenda_state"], len(pack["members"]), len(pack["watch"]),
              pack["confirmed"]))
    if not pack["confirmed"]:
        print("  placements: awaiting sign-off (none confirmed on areas {0})".format(
            pack["areas"] or "-"))
    if args.dry_run:
        print("  dry run: nothing written")
        return 0
    folder = dp.write_pack(pack, args.out, sample=args.sample)
    print("pack: {0}".format(os.path.relpath(folder, ROOT) if folder.startswith(ROOT) else folder))
    return 0


if __name__ == "__main__":
    sys.exit(main())
