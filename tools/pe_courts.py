#!/usr/bin/env python3
"""Peru's Tribunal Constitucional: its press notes on rulings and hearings (X8).

    python3 tools/pe_courts.py                  # the weekly read (slow: 30 s a page)
    python3 tools/pe_courts.py --backfill-feed  # once, on the Mini: the whole archive
    python3 tools/pe_courts.py --dry-run
    python3 tools/pe_courts.py --reclassify
    python3 tools/pe_courts.py --db /tmp/pe.db

X8, approved 10 October 2026. The Tribunal Constitucional rules on our
ground in Peru (religious symbols in courts, 2011; registration of
religious bodies, 2021; same-sex marriages contracted abroad, 2020) and
the Congress monitor saw none of it.

THE SOURCE: the Tribunal's press notes, www.tc.gob.pe/institucional/
notas-de-prensa/, keyless HTML (WordPress; the REST API exposes no posts).
robots.txt asks for `Crawl-delay: 30`, honoured with a per-host throttle:
every request to the host is at least thirty seconds after the last.

  * WEEKLY: the listing's first page (six notes, each with its date, title
    and opening sentence), then the next page only while every note on the
    page is new, at most MAX_PAGES. A new note is read in full (its own
    page) when its headline reports a ruling or a hearing, or its title and
    opening match our ground; at most MAX_NOTES a run. A run of eight
    requests is four minutes.
  * --backfill-feed: the notes' RSS feed, /institucional/notas-de-prensa/
    feed/, which serves the WHOLE archive (4,378 notes back to 2001, 15 MB,
    every note's full text) in one request. Run once, on the Mini; never
    weekly.

WHAT IS CLASSIFIED: the note's headline and text (the Tribunal's own words
about its decision), never the sentencia. Most notes are institutional (a
magistrate's lecture, a book fair): they are stored as kind 'press' and
never shown, whatever their words match. Kind 'ruling' when the headline
reports a decision ("TC declaró fundada...", "sentencia"), 'hearing' when it
announces or reports a hearing (the Pleno's audiencias, with their case
lists linked); the key is the note's own slug.

NOT HERE: the sentencias themselves. The Tribunal's jurisprudence search
(the Ventanilla Jurisdiccional) was not probed for an open listing; its
press notes are the seam used. Recorded in docs/peru-scope.md.

ONE WRITER AT A TIME on data/parl-monitor.db. Exit 3: stored what it could
and recorded gaps.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmllib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import courts, db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

CC = "pe"
FEED = "pe-courts"
COURT = "Tribunal Constitucional del Perú"
HOST = "www.tc.gob.pe"
LISTING = "https://www.tc.gob.pe/institucional/notas-de-prensa/"
RSS = LISTING + "feed/"
CRAWL_DELAY_S = 30.0          # robots.txt, read 10 October 2026
MAX_PAGES = 3
MAX_NOTES = 6

MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
          "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
          "diciembre": 12}
RULING = re.compile(r"\b(declar[oó]|declara|fundada|infundada|improcedente|inconstitucional|"
                    r"sentencia|fall[oó]|orden[oó]|dispuso|resolvi[oó]|rechaz[oó]|rechazan|"
                    r"no puede|no afecta|se pronuncia)\b", re.I)
HEARING = re.compile(r"\b(audiencia|ver[aá] causa|ver[aá] (?:un total de )?\d+|al voto|"
                     r"sesionar[aá]|sesion[oó])\b", re.I)
# A note about a lecture, a book or a visit is not a ruling even when its
# headline says "sentencias" ("sentencias emblemáticas fueron analizadas").
INSTITUTIONAL = re.compile(r"\b(expuso|expondr[aá]|conferencia|conversatorio|libro|feria|"
                           r"curso|c[aá]tedra|visit[aó]|visita|reuni[oó]n|seminario|disert[oó]|recibid[oa]|"
                           r"congreso internacional|agenda constitucional|aniversario)\b", re.I)
ITEM = re.compile(r'<div class="col-12 col-lg-6 items_not_p[^"]*">(.*?)<div class="boton_leer_mas">',
                  re.S)


def kind_of(title):
    if INSTITUTIONAL.search(title or ""):
        return "press"
    if RULING.search(title or ""):
        return "ruling"
    if HEARING.search(title or ""):
        return "hearing"
    return "press"


def es_date(text):
    """'octubre 9, 2026' or '9 de octubre de 2026' -> '2026-10-09'."""
    t = (text or "").lower()
    m = re.search(r"([a-z]+)\s+(\d{1,2}),\s*(\d{4})", t)
    if m and m.group(1) in MONTHS:
        return datetime.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))).isoformat()
    m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", t)
    if m and m.group(2) in MONTHS:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
    return None


def slug(url):
    return "pe:" + (url or "").rstrip("/").rsplit("/", 1)[-1]


def parse_listing(page_html):
    """[{url, date, title, excerpt}] from one listing page."""
    out = []
    for block in ITEM.findall(page_html or ""):
        link = re.search(r'<h5><a href="([^"]+)">(.*?)</a></h5>', block, re.S)
        if not link:
            continue
        date = re.search(r'<span class="date_post_not">([^<]+)</span>', block)
        excerpt = re.search(r'<p class="descrip">(.*?)</p>\s*</p>|<p class="descrip">(.*?)</p>',
                            block, re.S)
        out.append({"url": link.group(1), "title": courts.flat(link.group(2)),
                    "date": es_date(date.group(1)) if date else None,
                    "excerpt": courts.flat((excerpt.group(1) or excerpt.group(2)) if excerpt else "")
                    .replace("[…]", "").strip()})
    return out


def parse_note(page_html):
    """(date, title, text, case lists) from a note's own page."""
    a = page_html.find('<h1 class="my-3">')
    if a < 0:
        return None, None, None, []
    b = page_html.find("<footer", a)
    body = page_html[a:b if b > 0 else None]
    title = re.search(r'<h1 class="my-3">(.*?)</h1>', body, re.S)
    date = re.search(r'<span class="date_post_not[^"]*">([^<]+)</span>', page_html)
    lists = re.findall(r'href="(https://www\.tc\.gob\.pe/audiencia/[^"]+)"', body)
    text = courts.flat(body[title.end():] if title else body)
    return (es_date(date.group(1)) if date else None,
            courts.flat(title.group(1)) if title else None, text,
            [htmllib.unescape(u) for u in lists])


def row_of(url, date, title, text, lists=()):
    kind = kind_of(title)
    return {"ruling_key": slug(url), "court": COURT, "kind": kind, "case_no": _case(text),
            "date": date, "title": title, "summary": text,
            "decision": None,
            "formation": "{0} case list(s) linked".format(len(lists)) if lists else None,
            "url": url, "source": "tc.gob.pe notas de prensa"}


def _case(text):
    m = re.search(r"\b(?:Exp(?:ediente)?\.?\s*(?:N\.?\s*[°º]\s*)?)(\d{4,5}-\d{4}-[A-Z]{2,3}/TC)",
                  text or "")
    return m.group(1) if m else None


def parse_feed(xml):
    """Every <item> of the notes' RSS as (url, date, title, text)."""
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml or "", re.S):
        link = re.search(r"<link>(.*?)</link>", it, re.S)
        title = re.search(r"<title>(.*?)</title>", it, re.S)
        date = re.search(r"<pubDate>(.*?)</pubDate>", it)
        body = re.search(r"<content:encoded>(.*?)</content:encoded>", it, re.S)
        if not link:
            continue
        text = body.group(1) if body else ""
        text = text.replace("<![CDATA[", "").replace("]]>", "")
        iso = None
        if date:
            try:
                iso = datetime.datetime.strptime(date.group(1).strip()[:16],
                                                 "%a, %d %b %Y").date().isoformat()
            except ValueError:
                iso = None
        out.append((link.group(1).strip(), iso, courts.flat(title.group(1)) if title else "",
                    courts.flat(text)))
    return out


def stored(conn, key):
    return conn.execute("SELECT 1 FROM pe_rulings WHERE ruling_key=?", (key,)).fetchone()


def pull(conn, client, today, tax, log=print, max_pages=MAX_PAGES, max_notes=MAX_NOTES):
    """Returns (read, new, ours, gaps)."""
    client.set_host_throttle(HOST, CRAWL_DELAY_S)
    read = new = ours = 0
    fresh = []
    for page in range(1, max_pages + 1):
        url = LISTING if page == 1 else "{0}page/{1}/".format(LISTING, page)
        try:
            page_html = client.get_text(url, FEED, "notas-p{0}".format(page))
        except FetchError as exc:
            db.record_gap(conn, FEED, "press-note listing page {0} unreadable: {1}".format(
                page, str(exc)[:120]), today)
            conn.commit()
            return read, new, ours, 1
        notes = parse_listing(page_html)
        if not notes:
            db.record_gap(conn, FEED, "press-note listing page {0} parsed to zero notes; its "
                                      "markup may have changed".format(page), today)
            conn.commit()
            return read, new, ours, 1
        unseen = [n for n in notes if not stored(conn, slug(n["url"]))]
        # Re-stamp the notes already held, so tools/coverage.py sees the
        # listing answer every week even when it has nothing new.
        for n in notes:
            conn.execute("UPDATE pe_rulings SET last_seen=? WHERE ruling_key=?",
                         (today, slug(n["url"])))
        fresh.extend(unseen)
        if len(unseen) < len(notes):
            break
    gaps = 0
    deep = 0
    for n in reversed(fresh):           # oldest first, so a cut run resumes cleanly
        read += 1
        row = row_of(n["url"], n["date"], n["title"], n["excerpt"])
        areas, _, _ = courts.classify(tax, n["title"], n["excerpt"])
        if (row["kind"] in courts.SHOWN or courts.on_ground(areas)) and deep < max_notes:
            deep += 1
            try:
                note_html = client.get_text(n["url"], FEED, "note-" + slug(n["url"])[3:], archive=True)
                date, title, text, lists = parse_note(note_html)
                if text:
                    row = row_of(n["url"], date or n["date"], title or n["title"], text, lists)
            except FetchError as exc:
                gaps += 1
                db.record_gap(conn, FEED, "press note unreadable, stored from the listing: "
                                          "{0} ({1})".format(n["url"], str(exc)[:80]), today)
        is_new, areas = courts.upsert(conn, CC, row, tax, today)
        new += is_new
        if courts.on_ground(areas):
            ours += 1
            log("  [court] {0} {1} {2}: {3}".format(row["kind"], row["ruling_key"], areas,
                                                 row["title"][:70]))
    conn.commit()
    return read, new, ours, gaps


def backfill_feed(conn, client, today, tax, xml=None, log=print):
    """The whole archive from the RSS feed, one request (15 MB). Returns
    (read, new, ours, gaps)."""
    if xml is None:
        client.set_host_throttle(HOST, CRAWL_DELAY_S)
        try:
            xml = client.get_text(RSS, FEED, "feed-all", archive=False)
        except FetchError as exc:
            db.record_gap(conn, FEED, "press-note feed unreadable: {0}".format(str(exc)[:120]),
                          today)
            conn.commit()
            return 0, 0, 0, 1
    read = new = ours = 0
    for url, date, title, text in parse_feed(xml):
        read += 1
        is_new, areas = courts.upsert(conn, CC, row_of(url, date, title, text), tax, today)
        new += is_new
        ours += courts.on_ground(areas)
    conn.commit()
    return read, new, ours, 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--backfill-feed", action="store_true",
                    help="read the whole archive from the RSS feed (once, on the Mini)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    tax = courts.load_taxonomy(CC)
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    if args.reclassify:
        print("pe-courts: {0} note(s) reclassified".format(courts.reclassify(conn, CC, tax)))
        return 0
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0)
    if args.backfill_feed:
        read, new, ours, gaps = backfill_feed(conn, client, today, tax)
    else:
        read, new, ours, gaps = pull(conn, client, today, tax)
    print("pe-courts: {0} press note(s) read, {1} new, {2} on our ground{3}.".format(
        read, new, ours, " (dry run, nothing stored)" if args.dry_run else ""))
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
