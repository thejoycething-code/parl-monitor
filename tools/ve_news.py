#!/usr/bin/env python3
"""Venezuela's light monthly check: the Asamblea Nacional's Legislativa news.

    python3 tools/ve_news.py                    # read back to the newest stored date
    python3 tools/ve_news.py --since 2026-09-01
    python3 tools/ve_news.py --reclassify       # offline, after a taxonomy-es change

Chris, 10 October 2026 (VE1 "build something", VE2, VE3): no Venezuela
edition and no parliamentary section, but a monthly keyword note in the Latam
monitor from the Assembly's news feed, plus the reform of the Ley contra el
Odio watched by hand (config/watchlist-ve.yaml). docs/venezuela-scope.md
measured why it is this small: no recorded votes are published, the bill
register stopped in July 2022, the agendas are scanned images, and two of
203 news items in six months touched our ground.

Read: www.asambleanacional.gob.ve/noticias?categoria=Legislativa&page=N
(robots.txt allows everything; keyless; about 15 items a page), newest
first, until a page's oldest item is older than the cutoff; then each new
article's page for its body. Every response goes through src/http.py, so
it carries the CitizenGO User-Agent, is throttled and archived before parsing.

Classification is the shared taxonomy-es loaded for code `ve` through
src/filter.py (accent-folded, guards and vetoes applied). Nothing here is
published raw: tools/latam_monitor.py prints only rows the filter matched,
through the stub triage.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, latam_store  # noqa: E402

BASE = "https://www.asambleanacional.gob.ve"
LIST = BASE + "/noticias?categoria=Legislativa&page={0}"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
THROTTLE_S = 2.0
MAX_PAGES = 40          # about 600 items; a month is about 35
FIRST_RUN_DAYS = 45

CARD = re.compile(
    r'<a href="(https://www\.asambleanacional\.gob\.ve/noticias/[^"]+)"><h3[^>]*><b>(.*?)</b>'
    r'.*?Fecha: (\d\d)/(\d\d)/(\d{4})', re.S)


def parse_list(page_html):
    """[(url, title, iso date)] from one list page, newest first."""
    out = []
    for url, title, d, m, y in CARD.findall(page_html or ""):
        out.append((url, " ".join(html.unescape(re.sub(r"<[^>]+>", " ", title)).split()),
                    "{0}-{1}-{2}".format(y, m, d)))
    return out


def parse_body(page_html):
    """The article's text: from 'Fecha:' to the footer, tags stripped."""
    t = page_html or ""
    a = t.find("Fecha:")
    b = t.find("an-text-white", a)
    if a >= 0 and b > a:
        cut = t.rfind("<", a, b)          # the start of the footer's tag, not mid-attribute
        t = t[a:cut if cut > a else b]
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t)).split())[:6000]


def load_taxonomy(path=TAXONOMY_ES):
    return filt.load_taxonomy(path, country="ve") if os.path.exists(path) else None


_NO_WATCH = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, title, body):
    """(areas, matched_terms, tier); areas None when there is no taxonomy."""
    if tax is None:
        return None, [], None
    res = filt.filter_item(tax, _NO_WATCH, title or "", body or "")
    return sorted(set(res.issue_areas or [])), list(res.matched_terms or []), res.tier


def _dumps(v):
    return None if v is None else json.dumps(v, ensure_ascii=False)


def store(conn, url, date, title, body, tax, today):
    areas, terms, tier = classify(tax, title, body)
    conn.execute(
        "INSERT INTO ve_news (url, date, title, body, areas, matched_terms, tier, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET date=excluded.date, "
        "title=excluded.title, body=excluded.body, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (url, date, title, body, _dumps(areas), _dumps(terms), tier, today, today))


def reclassify(conn, tax):
    n = 0
    for url, title, body in conn.execute("SELECT url, title, body FROM ve_news").fetchall():
        areas, terms, tier = classify(tax, title, body)
        conn.execute("UPDATE ve_news SET areas=?, matched_terms=?, tier=? WHERE url=?",
                     (_dumps(areas), _dumps(terms), tier, url))
        n += 1
    conn.commit()
    return n


def collect(conn, client, since, today, tax, max_pages=MAX_PAGES):
    """Walk the list back to `since`; fetch bodies of articles not stored yet.
    Returns (listed, new)."""
    known = {r[0] for r in conn.execute("SELECT url FROM ve_news")}
    listed = new = 0
    for page in range(1, max_pages + 1):
        cards = parse_list(client.get_text(LIST.format(page), "ve-news", "list-p{0}".format(page)))
        if not cards:
            break
        for url, title, date in cards:
            if date < since:
                continue
            listed += 1
            if url in known:
                conn.execute("UPDATE ve_news SET last_seen=? WHERE url=?", (today, url))
                continue
            slug = re.sub(r"[^A-Za-z0-9]+", "-", url.rsplit("/", 1)[-1])[:80]
            body = parse_body(client.get_text(url, "ve-news", "item-" + slug))
            store(conn, url, date, title, body, tax, today)
            known.add(url)
            new += 1
        conn.commit()
        if min(c[2] for c in cards) < since:
            break
    return listed, new


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--since", help="ISO date; default: the newest stored item less a week")
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = ap.parse_args()
    conn = db.connect(args.db)
    latam_store.ensure_schema(conn)
    tax = load_taxonomy()
    if args.reclassify:
        print("ve-news: reclassified {0} item(s)".format(reclassify(conn, tax)))
        return 0
    today = datetime.date.today().isoformat()
    newest = conn.execute("SELECT MAX(date) FROM ve_news").fetchone()[0]
    since = args.since or (
        (datetime.date.fromisoformat(newest) - datetime.timedelta(days=7)).isoformat() if newest
        else (datetime.date.today() - datetime.timedelta(days=FIRST_RUN_DAYS)).isoformat())
    from src.http import FetchError, HttpClient
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    try:
        listed, new = collect(conn, client, since, today, tax, args.max_pages)
    except FetchError as exc:
        conn.commit()
        print("  [gap] ve-news: {0}".format(exc))
        return 3
    conn.row_factory = sqlite3.Row
    on = conn.execute("SELECT COUNT(*) FROM ve_news WHERE areas IS NOT NULL AND areas != '[]'"
                      ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM ve_news").fetchone()[0]
    print("ve-news: {0} item(s) listed since {1}, {2} new; store: {3} item(s), {4} on our "
          "ground".format(listed, since, new, total, on))
    return 0


if __name__ == "__main__":
    sys.exit(main())
