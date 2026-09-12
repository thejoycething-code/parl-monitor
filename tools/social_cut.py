#!/usr/bin/env python3
"""Build the social cut for a debate pack from its sequence.md.

    python3 tools/social_cut.py --pack data/packs/<folder>            # pull 1080p windows, cut, crop, caption, render
    python3 tools/social_cut.py --pack data/packs/<folder> --render   # re-cut and re-render from the windows already downloaded

Write sequence.md first (who, in what order, which spoken words; see
docs/debate-pack-social.md). The pack needs clips/whole-debate.words.json, made by
`tools/debate_pack.py --pack F --cut cuts.md` or by transcribing the whole-debate file,
so each passage can be found in time before its 1080p window is pulled.

Outputs land in clips/final/ (social-cut-*.mp4, a contact sheet) and the pack root
(social-cut.ass, social-cut.md). Footage is Parliament's, under the Parliamentary
Recording Unit's terms.
"""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import socialcut  # noqa: E402


def tools():
    yt = shutil.which("yt-dlp") or os.path.expanduser("~/Library/Python/3.9/bin/yt-dlp")
    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:                                   # noqa: BLE001
            ff = None
    return (yt if os.path.exists(yt) else None), ff


def area_patterns(areas):
    """The taxonomy's term patterns for the pack's areas, as debate_pack builds them."""
    from src import filter as filt
    tax = filt.load_taxonomy(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "config", "taxonomy.yaml"))
    areas = [a for a in areas if a != 11] or list(tax.terms)
    return [it[1] for a in areas for _t, items in sorted((tax.terms.get(a) or {}).items()) for it in items]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True, help="the pack folder (data/packs/<date>-<slug>)")
    ap.add_argument("--render", action="store_true", help="skip downloads; re-cut and re-render from the windows on disk")
    ap.add_argument("--draft", action="store_true", help="write a first sequence.md of 30-60s passages from speeches.md (confirmed onside, or the pass read while the checklist is blank -- then marked PROVISIONAL); refuses to overwrite")
    ap.add_argument("--transcribe", action="store_true", help="transcribe clips/00-whole-debate-*.mp4 into clips/whole-debate.words.json and stop")
    ap.add_argument("--model", default="small.en", help="faster-whisper model (default small.en)")
    args = ap.parse_args()
    from src import packlock
    packlock.acquire(args.pack.rstrip('/'), 'social_cut', force=bool(os.environ.get('PARL_FORCE_LOCK')))
    yt, ff = tools()
    if not ff:
        raise SystemExit("no ffmpeg: pip install --user imageio-ffmpeg")
    if args.draft:
        import json
        seq = os.path.join(args.pack, "sequence.md")
        if os.path.exists(seq):
            raise SystemExit("sequence.md already exists; delete or rename it first")
        state = json.load(open(os.path.join(args.pack, "pack.json")))
        speeches_path = os.path.join(args.pack, "speeches.md")
        if not os.path.exists(speeches_path):
            raise SystemExit("no speeches.md in the pack; build it with tools/debate_pack.py first")
        text = socialcut.draft_reel_sequence(open(speeches_path, encoding="utf-8").read(),
                                             state.get("title", "debate"), state.get("date", ""),
                                             area_patterns(state.get("areas") or []))
        open(seq, "w", encoding="utf-8").write(text)
        print("wrote %s (%d speakers%s). Reorder, trim, then run without --draft."
              % (seq, text.count("\n## "), "; PROVISIONAL" if socialcut.PROVISIONAL_LINE in text else ""))
        return
    if args.transcribe:
        words = socialcut.transcribe_whole(args.pack, ff, whisper_model=args.model)
        print("%d words in clips/whole-debate.words.json" % len(words))
        return
    if not yt and not args.render:
        raise SystemExit("no yt-dlp: pip install --user yt-dlp (or use --render with windows already downloaded)")
    print("social cut for", args.pack)
    items = socialcut.build(args.pack, ff, yt, render_only=args.render, log=print, whisper_model=args.model)
    total = sum(i["duration"] for i in items)
    print("%d excerpts, %.1fs. Check clips/final/social-cut-contact-sheet.jpg for the crops and social-cut.md for the words heard." % (len(items), total))


if __name__ == "__main__":
    main()
