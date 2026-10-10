#!/usr/bin/env python3
"""Peru: read the scan-only plenary vote records with Tesseract (X7), when the
Mini has it. Skips cleanly everywhere else.

    python3 tools/pe_ocr.py               # up to 3 scans a run
    python3 tools/pe_ocr.py --max 20      # a larger batch (Mini, by hand)
    python3 tools/pe_ocr.py --check       # say whether OCR is available, read nothing

X7, approved 10 October 2026; the design is in src/ocr.py and the install
steps in docs/mac-mini.md ("OCR (Tesseract, X7)"). Nothing is installed by
this tool.

WHAT IT DOES. tools/pe_rollcalls.py records every vote file it meets in
pe_vote_files, with text_layer = 0 for a printer scan (the signed records:
nothing to read, so no positions for those sittings). This step takes the
scans not yet in pe_vote_ocr, newest first, downloads each (1 to 14 MB, not
archived: the URL is the provenance) and stores Tesseract's text with the
engine's own version line. IT DOES NOT PARSE POSITIONS: a parser for OCR'd
vote sheets, tested on hand-checked sheets, is the next step and is not
built (src/ocr.py, "ACCURACY").

WITHOUT TESSERACT (the laptop, GitHub's runners, the Mini until installed):
one "[skip]" line, exit 0, nothing read or written. The Peru weekly calls it
after the collector, so the job is unchanged until the Mini has Tesseract.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, ocr  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "pe-ocr"
LANG = "spa"
MAX_READ = 3


def pending(conn, limit):
    return conn.execute(
        "SELECT f.url FROM pe_vote_files f LEFT JOIN pe_vote_ocr o ON o.url = f.url "
        "WHERE f.text_layer = 0 AND o.url IS NULL ORDER BY f.uploaded DESC, f.url LIMIT ?",
        (limit,)).fetchall()


def store(conn, url, pages, engine, today):
    text = "\f".join(t for _, t in pages)
    conn.execute(
        "INSERT INTO pe_vote_ocr (url, engine, lang, pages, chars, text, read_at) "
        "VALUES (?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET engine=excluded.engine, "
        "lang=excluded.lang, pages=excluded.pages, chars=excluded.chars, text=excluded.text, "
        "read_at=excluded.read_at",
        (url, engine, LANG, len(pages), len(text), text, today))
    conn.commit()
    return len(text)


def run(conn, client, today, limit=MAX_READ, log=print):
    """Returns (read, gaps), or None when OCR is unavailable."""
    if not ocr.available(LANG):
        log("[skip] pe-ocr: {0}; scans stay unread".format(ocr.why_not(LANG)))
        return None
    engine = ocr.version()
    read = gaps = 0
    for (url,) in pending(conn, limit):
        try:
            raw = client.get_bytes(url, FEED, url.rsplit("/", 1)[-1], archive=False)
        except FetchError as exc:
            gaps += 1
            db.record_gap(conn, FEED, "scan unreadable: {0} ({1})".format(url, str(exc)[:80]),
                          today)
            continue
        pages = ocr.pdf_text(raw, LANG) or []
        n = store(conn, url, pages, engine, today)
        read += 1
        log("  [ocr] {0}: {1} page(s), {2} characters".format(url.rsplit("/", 1)[-1],
                                                            len(pages), n))
    return read, gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--max", type=int, default=MAX_READ)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        ok = ocr.available(LANG)
        print("pe-ocr: OCR {0}{1}".format("available: " + (ocr.version() or "?") if ok
                                         else "unavailable: ", "" if ok else ocr.why_not(LANG)))
        return 0
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    got = run(conn, HttpClient(raw_dir=args.raw_dir, throttle=1.0), today, args.max)
    conn.close()
    if got is None:
        return 0
    read, gaps = got
    print("pe-ocr: {0} scan(s) read".format(read))
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
