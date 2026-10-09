#!/usr/bin/env python3
"""Nicaragua's light check: La Gaceta, Diario Oficial, for religious freedom.

    python3 tools/nic_gaceta.py                     # issues since the newest stored
    python3 tools/nic_gaceta.py --since 2026-09-01
    python3 tools/nic_gaceta.py --reclassify        # offline, after a taxonomy-es change

Chris, 10 October 2026 (NI1 no parliamentary section, NI2 yes): La Gaceta is
in scope for religious-freedom tracking, church and NGO closures. The
Assembly is the wrong place to look (docs/nicaragua-scope.md: none of 146
items voted in two years touched our ground); the cancellations of the legal
status (personalidad jurídica) of churches, religious associations and
foundations are Interior Ministry decisions published in the gazette.

REACHABLE, MEASURED 9 OCTOBER 2026 (from the laptop, CitizenGO UA):
  * https://www.lagaceta.gob.ni/robots.txt answers 404, so nothing is
    disallowed; no key, no login, no challenge on the pages read here.
  * /ediciones?page=N lists the issues newest first, nine a page, each a page
    such as /la-gaceta-no-184-jueves-08-de-octubre-de-2026/ (slugs are
    irregular: 'mie-rcoles', 'del-29-de-septiembre'; the number and the
    date are read from the slug's two ends).
  * The issue page EMBEDS the whole PDF as base64 for its PDF.js viewer
    (No. 184: a 1.6 MB page holding an 870 KB, 44-page PDF). There is no
    separate download; the subscription the site sells is for print.
  * The PDF has a text layer: simple TrueType fonts, WinAnsi, TJ arrays.
    Read here with a stdlib reader (no pypdf), good enough to split notices
    and match terms. The bare domain lagaceta.gob.ni fails TLS; only www.

ARCHIVE. The decoded PDF is archived (data/raw/<date>/nic-gaceta_*.json.gz),
not the 1.6 MB page around it, whose remainder is site chrome: the PDF is
the response's whole substance, at about half the bytes.

WHAT IS KEPT. Each issue is split into notices; a notice is stored only when
the shared taxonomy-es (code `nic`, accent-folded, guards and vetoes)
matches it, so the store holds a few rows a month, not the gazette. The
Latam edition prints only area 8 (religious freedom: "personalidad jurídica"
with "cancela*", "organismos sin fines de lucro", Ley 1115, "agentes
extranjeros"...) and counts the rest.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import re
import sqlite3
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, latam_store  # noqa: E402

BASE = "https://www.lagaceta.gob.ni"
LIST = BASE + "/ediciones?page={0}&search="
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
THROTTLE_S = 2.0
MAX_PAGES = 6            # 54 issues; a month is about 21
FIRST_RUN_DAYS = 35
MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
          "noviembre": 11, "diciembre": 12}
ISSUE_HREF = re.compile(r'href="(/la-gaceta-no-(\d+)-[^"]*?-(\d{1,2})-de-([a-z]+)-de-(\d{4})/)"')


# --- the listing --------------------------------------------------------------

def parse_list(page_html):
    """[(path, issue number, iso date)] from an /ediciones page, unique, in
    page order (newest first)."""
    out, seen = [], set()
    for path, num, day, month, year in ISSUE_HREF.findall(page_html or ""):
        if path in seen or month not in MONTHS:
            continue
        seen.add(path)
        out.append((path, int(num), "{0}-{1:02d}-{2:02d}".format(year, MONTHS[month], int(day))))
    return out


def embedded_pdf(page_html):
    """The PDF the issue page embeds as base64, or None."""
    blobs = re.findall(r"JVBERi[A-Za-z0-9+/=]{200,}", page_html or "")
    if not blobs:
        return None
    try:
        return base64.b64decode(max(blobs, key=len))
    except (ValueError, TypeError):
        return None


# --- a small stdlib PDF text reader -------------------------------------------

_ESC = {b"n": b"\n", b"r": b"", b"t": b" ", b"b": b"", b"f": b"", b"(": b"(", b")": b")",
        b"\\": b"\\"}


def _unescape(b):
    def rep(m):
        g = m.group(1)
        if g[:1].isdigit():
            return bytes([int(g, 8) & 0xFF])
        return _ESC.get(g, g)
    return re.sub(rb"\\([0-7]{1,3}|.)", rep, b, flags=re.S)


def pdf_pages(data):
    """One string per content stream that draws text, in file order. WinAnsi
    literal strings only (what La Gaceta's TrueType fonts use); a kerning gap
    wider than 200 thousandths of an em is a space; text drawn in render mode
    1 (the stroked shadow copy La Gaceta prints under headings) is skipped.
    Anything unreadable yields nothing rather than an exception."""
    pages = []
    for m in re.finditer(rb"stream(\r\n|\n|\r)", data or b""):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        try:
            s = zlib.decompressobj().decompress(data[start:end])
        except zlib.error:
            continue
        if not re.search(rb"T[Jj]\b", s):
            continue
        blocks = []
        for bt in re.findall(rb"BT(.*?)ET", s, re.S):
            if re.search(rb"\b1 Tr\b", bt):
                continue
            parts = []
            for arr, single in re.findall(
                    rb"\[((?:\\.|[^\]])*)\]\s*TJ|\(((?:\\.|[^\\)])*)\)\s*Tj", bt, re.S):
                if single:
                    parts.append(_unescape(single))
                    continue
                for strg, num in re.findall(rb"\(((?:\\.|[^\\)])*)\)|(-?\d+\.?\d*)", arr):
                    if strg or not num:
                        parts.append(_unescape(strg))
                    elif float(num) < -200:
                        parts.append(b" ")
            text = b"".join(parts).decode("cp1252", "replace").strip()
            if text:
                blocks.append(text)
        if blocks:
            pages.append(" ".join(" ".join(blocks).split()))
    return pages


SPLIT = re.compile(r"_{6,}|(?=\bReg\. \d{4}-\d+)")


def notices(pages):
    """The issue cut into notices: at the gazette's rule lines and at each
    'Reg. 2026-00944' registration stamp. The SUMARIO page is dropped, so a
    contents line never stands in for its notice."""
    out = []
    for page in pages:
        if "SUMARIO" in page[:200]:
            continue
        for chunk in SPLIT.split(page):
            chunk = chunk.strip()
            if len(chunk) >= 80:
                out.append(chunk)
    return out


# --- classification -----------------------------------------------------------

def load_taxonomy(path=TAXONOMY_ES):
    return filt.load_taxonomy(path, country="nic") if os.path.exists(path) else None


_NO_WATCH = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, text):
    if tax is None:
        return [], [], None
    res = filt.filter_item(tax, _NO_WATCH, text[:300], text)
    return sorted(set(res.issue_areas or [])), list(res.matched_terms or []), res.tier


def store_issue(conn, path, issue, date, pdf, tax, today):
    """Split, classify and store one issue. Returns the notices kept."""
    year = int(date[:4])
    pages = pdf_pages(pdf) if pdf else []
    items = notices(pages)
    kept = 0
    for n, text in enumerate(items, 1):
        areas, terms, tier = classify(tax, text)
        if not areas:
            continue
        kept += 1
        conn.execute(
            "INSERT INTO nic_gazette_items (item_key, issue, date, url, heading, text, areas, "
            "matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(item_key) DO UPDATE SET areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, tier=excluded.tier, text=excluded.text, "
            "heading=excluded.heading, last_seen=excluded.last_seen",
            ("{0}/{1}/{2}".format(year, issue, n), issue, date, BASE + path, text[:160],
             text[:2000], json.dumps(areas), json.dumps(terms, ensure_ascii=False), tier,
             today, today))
    conn.execute(
        "INSERT OR REPLACE INTO nic_gazette_issues (issue, year, date, url, pages, items, read_at) "
        "VALUES (?,?,?,?,?,?,?)", (issue, year, date, BASE + path, len(pages), len(items), today))
    conn.commit()
    return kept


def reclassify(conn, tax):
    n = 0
    for key, text in conn.execute("SELECT item_key, text FROM nic_gazette_items").fetchall():
        areas, terms, tier = classify(tax, text or "")
        conn.execute("UPDATE nic_gazette_items SET areas=?, matched_terms=?, tier=? "
                     "WHERE item_key=?", (json.dumps(areas), json.dumps(terms, ensure_ascii=False),
                                          tier, key))
        n += 1
    conn.commit()
    return n


def collect(conn, client, since, today, tax, max_pages=MAX_PAGES):
    """Issues dated on or after `since` and not read yet. Returns
    (issues read, notices kept, issues without a text layer)."""
    read = {(r[0], r[1]) for r in conn.execute("SELECT year, issue FROM nic_gazette_issues")}
    n_read = kept = blind = 0
    for page in range(1, max_pages + 1):
        cards = parse_list(client.get_text(LIST.format(page), "nic-gaceta", "list-p{0}".format(page)))
        if not cards:
            break
        for path, issue, date in cards:
            if date < since or (int(date[:4]), issue) in read:
                continue
            page_html = client.get_text(BASE + path, "nic-gaceta", "issue-{0}-{1}".format(
                date[:4], issue), archive=False)
            pdf = embedded_pdf(page_html)
            if pdf:
                client._archive(pdf, "nic-gaceta", "pdf-{0}-{1}".format(date[:4], issue))
            got = store_issue(conn, path, issue, date, pdf, tax, today)
            n_read += 1
            kept += got
            if not pdf or not conn.execute(
                    "SELECT pages FROM nic_gazette_issues WHERE issue=? AND year=?",
                    (issue, int(date[:4]))).fetchone()[0]:
                blind += 1
                print("  [gap] nic-gaceta: No. {0} of {1} has no readable text".format(issue, date))
        if min(c[2] for c in cards) < since:
            break
    return n_read, kept, blind


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--since", help="ISO date; default: the newest stored issue")
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = ap.parse_args()
    conn = db.connect(args.db)
    latam_store.ensure_schema(conn)
    tax = load_taxonomy()
    if args.reclassify:
        print("nic-gaceta: reclassified {0} notice(s)".format(reclassify(conn, tax)))
        return 0
    today = datetime.date.today().isoformat()
    newest = conn.execute("SELECT MAX(date) FROM nic_gazette_issues").fetchone()[0]
    since = args.since or newest or (
        datetime.date.today() - datetime.timedelta(days=FIRST_RUN_DAYS)).isoformat()
    from src.http import FetchError, HttpClient
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    try:
        n_read, kept, blind = collect(conn, client, since, today, tax, args.max_pages)
    except FetchError as exc:
        conn.commit()
        print("  [gap] nic-gaceta: {0}".format(exc))
        return 3
    conn.row_factory = sqlite3.Row
    rel = conn.execute("SELECT COUNT(*) FROM nic_gazette_items WHERE areas LIKE '%8%'").fetchone()[0]
    print("nic-gaceta: {0} issue(s) read since {1}, {2} notice(s) on our ground, {3} without "
          "text; store: {4} religious-freedom notice(s)".format(n_read, since, kept, blind, rel))
    return 3 if blind else 0


if __name__ == "__main__":
    sys.exit(main())
