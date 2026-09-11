#!/usr/bin/env python3
"""Cut every onside speech in a pack as a subtitled 16:9 clip, word-exact.

    python3 tools/speech_cut.py --pack data/packs/<folder>                 # the speakers in sequence.md
    python3 tools/speech_cut.py --pack data/packs/<folder> --all           # every onside speech
    python3 tools/speech_cut.py --pack data/packs/<folder> --only "Shivani Raja"
    python3 tools/speech_cut.py --pack data/packs/<folder> --confirmed-only  # ignore the pass read

Before the checklist is confirmed the pass read stands in (PROVISIONAL), as it does for
--draft and --provisional. Outputs: clips/final/speech-NN-<name>-<time>.mp4 (subtitled,
name plate, logo), the same -clean.mp4, a .srt, and speeches-cut.md in the pack.
Footage is Parliament's under the Parliamentary Recording Unit's terms.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from src import speechcut  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--only", action="append", help="speaker name(s) to cut; repeatable")
    ap.add_argument("--confirmed-only", action="store_true", help="cut confirmed-onside speakers only, never the pass read")
    ap.add_argument("--all", action="store_true", help="every onside speaker, not only those in sequence.md")
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()
    from social_cut import tools
    _yt, ff = tools()
    if not ff:
        raise SystemExit("no ffmpeg (brew install ffmpeg, or pip install imageio-ffmpeg)")
    only = args.only
    seq = os.path.join(args.pack.rstrip("/"), "sequence.md")
    if not only and not args.all and os.path.exists(seq):
        # A Second Reading can have thirty speakers on our side; at 200 MB and several
        # minutes of transcription each, cutting them all unasked is hours of work the
        # campaigner may not want. The sequence names the speakers judged worth a reel;
        # start there, --all for the rest.
        from src import socialcut
        only = [e["name"] for e in socialcut.parse_sequence(open(seq, encoding="utf-8").read())]
        print("cutting the %d speaker(s) in sequence.md (--all for every onside speaker)" % len(only))
    rows = speechcut.build(args.pack.rstrip("/"), ff, log=print, whisper_model=args.model,
                           only=only, provisional=not args.confirmed_only, height=args.height)
    print("%d speech(es) cut; see %s/speeches-cut.md" % (sum(1 for r in rows if r[2]), args.pack.rstrip("/")))


if __name__ == "__main__":
    main()
