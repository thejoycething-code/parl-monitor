#!/usr/bin/env python3
"""Speech clips for social, the new countries: pick, then cut. Manual, like the UK's.

    python3 tools/country_clips.py sources                       # what each country allows, and why
    python3 tools/country_clips.py pick at --date 2026-09-23 --find "Abtreibung" --top 6
    python3 tools/country_clips.py pick ch --since 2026-09-08 --until 2026-09-26 --find "Suizid"
    python3 tools/country_clips.py pick fr --date 2026-10-09 --live      # read the day from the source
    python3 tools/country_clips.py cut --pack data/clips/<folder> --locate-only    # spans only, no footage
    python3 tools/country_clips.py cut --pack data/clips/<folder>                  # fetch, align, cut, caption
    python3 tools/country_clips.py cut --pack data/clips/<folder> --only "Name" --video speech.mp4   # NL
    python3 tools/country_clips.py moments nl --pack data/clips/<folder>          # where on Debat Direct
    python3 tools/country_clips.py purge                          # delete source footage past retention

The pick reads the store (data/parl-monitor.db) read-only, or with --live the
country's own collector into memory; it makes no AI call. The cut fetches only
each speech's span of official video, transcribes it (faster-whisper, model
"small"), aligns the passage, and renders a captioned 9:16 and 16:9 clip with
the source credit. It never posts, uploads or sends anything: the clips are
files for a person. Countries whose terms ask for prior agreement (BE)
refuse to cut until config/clip-sources.yaml records it; France's agreement
(12 October 2026) is recorded, and its clips are cut trim-only (no edit
beyond the start and end, credit "Archives audiovisuelles de l'Assemblée
nationale"), which the tool enforces. See
docs/debate-pack-social.md, "Speech clips, new countries".
"""

import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_clips as cc  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sources")
    p = sub.add_parser("pick")
    p.add_argument("country")
    p.add_argument("--date")
    p.add_argument("--since")
    p.add_argument("--until")
    p.add_argument("--find", help="words the debate's title must contain (accents ignored)")
    p.add_argument("--debate", help="a debate_id exactly")
    p.add_argument("--top", type=int, default=6)
    p.add_argument("--live", action="store_true", help="read --date from the source (no store write)")
    p.add_argument("--store", default=cc.STORE)
    p.add_argument("--out", default=cc.PACKS)
    c = sub.add_parser("cut")
    c.add_argument("--pack", required=True)
    c.add_argument("--only", action="append")
    c.add_argument("--video", help="a speech file a person downloaded (NL: Debat Direct)")
    c.add_argument("--locate-only", action="store_true")
    c.add_argument("--model", default=cc.WHISPER_MODEL)
    m = sub.add_parser("moments")
    m.add_argument("country", choices=["nl"])
    m.add_argument("--pack", required=True)
    g = sub.add_parser("purge")
    g.add_argument("--pack", help="one pack (default: every pack under data/clips)")
    args = ap.parse_args(argv)
    sources = cc.load_sources()

    if args.cmd == "sources":
        print(cc.sources_table(sources))
        for k, e in sources.items():
            print("\n{0} ({1}): {2}".format(k.upper(), e["status"], " ".join((e.get("terms") or "").split())))
        return 0

    if args.cmd == "pick":
        code = args.country.lower()
        entry = sources.get(code)
        if not entry:
            raise SystemExit("{0}: not in config/clip-sources.yaml".format(code))
        if entry["status"] == "not-built":
            raise SystemExit("{0}: {1}".format(code, " ".join(entry["terms"].split())))
        if args.live:
            if not args.date:
                raise SystemExit("--live reads one day: give --date")
            rows = cc.live_rows(code, args.date, cc._client(code))
        else:
            if not os.path.exists(args.store):
                raise SystemExit("no store at {0} (pull it, or use --live --date)".format(args.store))
            conn = sqlite3.connect("file:{0}?mode=ro".format(args.store), uri=True)
            try:
                rows = cc.store_rows(conn, code, date=args.date, since=args.since, until=args.until)
            except sqlite3.OperationalError as exc:
                raise SystemExit("{0}: {1} (has the {2} chamber step run?)".format(args.store, exc, code.upper()))
            conn.close()
        rows = cc.select(rows, find=args.find, debate_id=args.debate)
        cands = cc.candidates(rows)
        if not cands:
            raise SystemExit("no speech on our ground long enough for a clip in that window")
        pack = cc.write_pack(code, rows, cands, entry, top=args.top,
                             date=args.date or cands[0]["date"], out_dir=args.out)
        print("{0} candidate(s), {1} with a passage; wrote {2}".format(
            len(cands), sum(1 for x in cands if x["passage"]), os.path.relpath(pack, ROOT)))
        print("status {0}: {1}".format(entry["status"], "edit sequence.md, then cut" if entry["status"] == "open"
                                       else "see README.md before cutting"))
        return 0

    if args.cmd == "cut":
        try:
            report = cc.cut_pack(args.pack.rstrip("/"), sources, only=args.only, video=args.video,
                                 model=args.model, locate_only=args.locate_only)
        except cc.ClipRefused as exc:
            raise SystemExit("refused: {0}".format(exc))
        done = sum(1 for r in report if r[1] in ("CUT", "LOCATED"))
        print("{0} of {1} {2}; see {3}".format(done, len(report), "located" if args.locate_only else "cut",
                                              os.path.join(args.pack, "locate.md" if args.locate_only else "clips.md")))
        return 0

    if args.cmd == "moments":
        import json
        state = json.load(open(os.path.join(args.pack, "pack.json"), encoding="utf-8"))
        seq = cc.parse_sequence(open(os.path.join(args.pack, "sequence.md"), encoding="utf-8").read())
        by_id = {s["speech_id"]: s for s in state["speeches"]}
        client = cc._client("nl")
        for e in seq:
            row = by_id.get(e.get("speech")) or {}
            got = cc.debatdirect_moments(row.get("date") or state["date"], e["name"], row.get("debate"), client)
            print("## {0}".format(e["name"]))
            for name, at, url in got or [("not found on Debat Direct's plenary agenda", "", "")]:
                print("  {0} {1} {2}".format(at, name, url))
        return 0

    if args.cmd == "purge":
        packs = [args.pack] if args.pack else [os.path.join(cc.PACKS, d) for d in sorted(os.listdir(cc.PACKS))] \
            if os.path.isdir(cc.PACKS) else []
        for pk in packs:
            import json
            try:
                code = json.load(open(os.path.join(pk, "pack.json")))["country"]
            except (OSError, ValueError, KeyError):
                continue
            cc.purge(pk, int((sources.get(code) or {}).get("retention_days") or 30))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
