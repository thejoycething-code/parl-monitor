#!/usr/bin/env python3
"""Build a German debate pack for one debate.

    python3 tools/de_debate_pack.py --date 2026-09-24 --find Rechtshilfe
    python3 tools/de_debate_pack.py --date 2026-09-24 --top "TOP 11"
    python3 tools/de_debate_pack.py --date 2026-09-24 --find Rechtshilfe --dry-run
    python3 tools/de_debate_pack.py --pack data/packs/de-2026-09-24-... --onside

Christopher, 25 September 2026: "Build the debate packs." The German
equivalent of tools/debate_pack.py, and it could not exist until the
bundestag.de block lifted overnight.

WHAT IT READS.
  * The Stenografischer Bericht from DIP (plenarprotokoll-text), parsed by
    src/de_protocol.py -- the same parser the speeches collector uses. The
    collector stores only speeches on our ground; a pack needs EVERY
    speaker in the debate, so this parses the protocol itself.
  * The Bundestag Mediathek's own list for that sitting, which publishes
    one video per speech with the speaker, their party and the wall-clock
    second they rose. About 40 requests for a sitting, paced.

WHAT IT DOES NOT DO. It does not read direction, and it does not download
footage. Who is with us is the checklist's question and a human answers it;
the Bundestag's terms for its recordings are its own and we have not read
them, so the pack links to their player and stops.

COST. No API calls: DIP and the Mediathek are both free. The only spend in
a German pack would be a stance pass, and there is not one here.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import de_debatepack as dp, de_protocol, dip  # noqa: E402
from src.http import HttpClient  # noqa: E402


def protocol_for(client, key, date, log=print):
    """The sitting's protocol text, or None. Bundestag only."""
    for reply in dip.pages(client, "plenarprotokoll-text", key, limit_pages=4,
                           feed="de-pack", slug="protocols",
                           **{"f.zuordnung": "BT", "f.datum.start": date,
                              "f.datum.end": date}):
        for doc in reply.get("documents") or []:
            if (doc.get("text") or "").strip():
                return doc
    log("  [gap] de-pack: no Bundestag protocol with text for {0}".format(date))
    return None


def split_number(dokumentnummer):
    """'21/96' -> (21, 96)."""
    hit = re.match(r"\s*(\d+)\s*/\s*(\d+)", dokumentnummer or "")
    return (int(hit.group(1)), int(hit.group(2))) if hit else (None, None)


def speeches_in(text, term=None):
    """Every speech in the protocol, chair excluded, optionally narrowed.

    A debate is not delimited in the text by anything a parser can trust --
    the agenda item headings are in the table of contents, not beside the
    speeches -- so --find narrows by what was SAID. That is a blunt
    instrument and the pack says so in its own round-up: a speaker who never
    used the word is not in it.
    """
    parsed, _skipped = de_protocol.parse_speeches(text)
    rows = []
    for speaker, party, role, body in parsed:
        if role == "chair":
            continue
        if term and term.lower() not in body.lower():
            continue
        rows.append({"speaker": speaker, "party": party, "role": role,
                     "body": body, "excerpt": " ".join(body.split())[:300]})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="sitting date, YYYY-MM-DD")
    ap.add_argument("--find", help="narrow to speeches mentioning this word")
    ap.add_argument("--title", help="what to call the pack")
    ap.add_argument("--top", help="select the agenda item by its heading")
    ap.add_argument("--list", action="store_true",
                    help="list the sitting's agenda items and stop")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and count; write nothing, fetch no video")
    ap.add_argument("--pack", help="an existing pack folder")
    ap.add_argument("--onside", action="store_true",
                    help="with --pack: read the filled checklist and report")
    args = ap.parse_args()

    if args.pack and args.onside:
        rows = dp.parse_checklist(os.path.join(args.pack, "checklist.md"))
        yes = [r for r in rows if r[1]]
        print("onside: {0} of {1} answered; {2} yes".format(
            len(rows), len(rows), len(yes)))
        for name, ok, note in rows:
            print("  {0:<34} {1}{2}".format(
                name[:34], "yes" if ok else "no", "  " + note if note else ""))
        return 0

    if not args.date:
        ap.error("--date is required")

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    key = dip.api_key(client=client)
    if not key:
        print("  [gap] de-pack: no DIP key; cannot read the protocol")
        return 1
    doc = protocol_for(client, key, args.date)
    if not doc:
        return 1
    wahlperiode, sitzung = split_number(doc.get("dokumentnummer"))
    text = doc["text"]
    preliminary = "Vorabfassung" in text
    start = dp.sitting_start(text)
    parsed = speeches_in(text)
    print("protocol {0} | {1} chars | {2} speech(es){3}".format(
        doc.get("dokumentnummer"), len(text), len(parsed),
        " | VORABFASSUNG, may omit whole agenda items" if preliminary else ""))

    media = dp.fetch_media(client, wahlperiode, sitzung)
    print("mediathek: {0} entries for sitting {1}/{2}".format(
        len(media), wahlperiode, sitzung))
    if args.list:
        for heading, entries in dp.tops(media).items():
            print("   {0:>3}  {1}".format(len(entries), heading[:96]))
        return 0

    term = args.top or args.find
    if not term:
        ap.error("--find, --top or --list is required")
    heading, entries = dp.select_top(media, term)
    if not entries:
        print("  no agenda item matched '{0}'. --list shows them.".format(term))
        return 1

    rows, with_text = dp.rows_from_media(entries, parsed)
    if not rows:
        print("  nothing to pack")
        return 1
    print("  {0}".format(heading[:100]))
    print("  {0} speaker(s); the protocol carries the words of {1}".format(
        len(rows), with_text))
    if args.dry_run:
        for r in rows[:12]:
            print("   {0:<28} {1:<22} {2} {3}".format(
                (r["speaker"] or "")[:28], (r["party"] or "")[:22],
                (r["video"] or {}).get("clock") or "-",
                "" if r["body"] else "(no text in this protocol)"))
        print("  dry run: nothing written")
        return 0

    title = args.title or heading
    debate = {"title": title, "date": args.date, "sitzung": sitzung,
              "wahlperiode": wahlperiode}
    patterns = [args.find] if args.find else dp.topic_terms(heading)
    folder = dp.write_pack(debate, rows, with_text, patterns, start)
    whole = dp.whole_debate_video(entries)
    print("pack: {0}".format(os.path.relpath(folder, ROOT)))
    if whole:
        print("  whole debate: {0}".format(dp.VIDEO_URL.format(whole["videoid"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
