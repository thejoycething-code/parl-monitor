#!/usr/bin/env python3
"""Rank the confirmed-onside speeches for campaign value and pick the best to cut.

    python3 tools/pick_speeches.py --pack data/packs/<folder> --dry-run          # who would be judged, no spend
    python3 tools/pick_speeches.py --pack data/packs/<folder> --top 8            # one call; writes selection.md
    python3 tools/pick_speeches.py --pack data/packs/<folder> --top 8 --write-sequence   # ...and sequence.md for the top 8

Requires a confirmed checklist (--apply): the judge orders onside speakers, it never
decides who is onside. --write-sequence keeps the old sequence.md as sequence-previous.md.
Costs one Anthropic call, recorded in api_spend as 'speech-pick'. ONE WRITER AT A TIME
on the store: pull before, push after.
"""

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, publish, selectspeeches as sel, socialcut as sc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--min-words", type=int, default=sel.MIN_WORDS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write-sequence", action="store_true")
    args = ap.parse_args()
    pack = args.pack.rstrip("/")
    meta = json.load(open(os.path.join(pack, "pack.json")))
    speeches = sc.parse_speeches(open(os.path.join(pack, "speeches.md"), encoding="utf-8").read())
    cands = sel.candidates(speeches, min_words=args.min_words)
    print("%s: %d confirmed onside, %d with a speech of %d+ words" % (
        meta.get("title"), sum(1 for s in speeches if s.get("confirmed") == "yes"), len(cands), args.min_words))
    if not cands:
        raise SystemExit("nothing to judge: confirm ONSIDE in checklist.md and run tools/debate_pack.py --pack F --apply first")
    if args.dry_run:
        chars = len(sel.build_payload(meta, cands)["messages"][0]["content"])
        print("would judge %d speakers, ~%d tokens (about $%.2f)" % (len(cands), chars // 4, (chars / 4 * 3 + sel.MAX_TOKENS * 15) / 1e6))
        for c in cands:
            print("   %-28s %-8s %5d words" % (c["name"], c["party"], c["words"]))
        return
    secrets = publish.load_secrets()
    key = secrets.get("anthropic_api_key")
    if not key:
        raise SystemExit("no anthropic_api_key in config/secrets.yaml")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    ranked, problems, usage = sel.judge(meta, cands, key, conn=conn)
    conn.commit(); conn.close()
    open(os.path.join(pack, "selection.md"), "w", encoding="utf-8").write(sel.selection_md(meta, ranked, problems, args.top))
    json.dump({"top": args.top, "ranked": ranked, "problems": problems}, open(os.path.join(pack, "selection.json"), "w"), indent=1)
    print("ranked %d; %d check note(s); tokens in %s out %s" % (len(ranked), len(problems), usage.get("input_tokens"), usage.get("output_tokens")))
    for i, r in enumerate(ranked[:args.top], 1):
        print("  %d. %-26s %2.0f  %s%s" % (i, r["name"], r["score"], r["angle"], "" if r["passage"] else "  (no verbatim passage)"))
    for p in problems:
        print("  [check] %s" % p)
    if args.write_sequence:
        seq = os.path.join(pack, "sequence.md")
        if os.path.exists(seq):
            shutil.copy(seq, os.path.join(pack, "sequence-previous.md"))
        from src import filter as filt
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        areas = [a for a in (meta.get("areas") or []) if a != 11] or list(tax.terms)
        patterns = [it[1] for a in areas for _t, items in sorted((tax.terms.get(a) or {}).items()) for it in items]
        open(seq, "w", encoding="utf-8").write(sel.sequence_md(meta, ranked, args.top, speeches, patterns))
        print("wrote sequence.md for the top %d (previous kept as sequence-previous.md)" % args.top)


if __name__ == "__main__":
    main()
