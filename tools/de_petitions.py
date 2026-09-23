#!/usr/bin/env python3
"""Bundestag e-petitions open for co-signature -- the deadline layer.

    python3 tools/de_petitions.py
    python3 tools/de_petitions.py --no-bodies

Christopher, 23 September 2026: build the deadline-bearing section, because
"Germany has no deadline-bearing section at all" was the gap that mattered
most. Every other German section reports what is happening. This one is the
only one that can say RESPOND BY A DATE, which is the difference between
intelligence and campaigning.

WHY PETITIONS AND NOT MINISTRY CONSULTATIONS. The nearer analogue to
Westminster's calls for evidence is the Verbändeanhörung on a Referentenentwurf
-- but probed on 23 September 2026 there is NO central source for them: BMJV
serves its list, BMFSFJ 404s on the equivalent path, and each ministry
publishes to its own unstable URL. That is N fragile scrapers for one section.
The Bundestag's own petitions are one source, with a published closing date on
every item, so they are what this delivers. Verbändeanhörung is scoped, not
built, and this file does not pretend to cover it.

THE SOURCE, and it needs a session. The overview page is JavaScript; the cards
come from

  /epet/petuebersicht/mz.nc.content.teaser-petitionen-cards.$$$.ssi.true
      .status.2.page.<n>.batchsize.8.html

Measured: batchsize is fixed at EIGHT -- 20, 50 and 100 each return "Die
angefragte URL ist ungültig" -- so 81 open petitions is eleven pages. Without
cookies the endpoint returns zero bytes, so the client is built on a cookie
jar and the start page is fetched first to establish the session.

THE DEADLINE IS EXACT, not derived from the "Es bleiben noch: 5 Tage" string
the page shows a human. Each card carries two epoch-millisecond stamps, the
opening and the closing of the Mitzeichnungsfrist, and those are what is
stored. A day count computed from a rendered string would drift by a day
around midnight and be wrong in exactly the week it mattered.

NO SIGNATURE GATE, deliberately. Westminster needed one because its first
sweep met 2,279 open petitions and admitted 269 on tier-2 words alone.
Germany has 81 open at a time, so every matched petition is stored and the
volume problem does not exist. If that changes, the Bundestag's own quorum --
30,000 signatures inside the Mitzeichnungsfrist for a committee hearing -- is
the threshold to reach for, not Westminster's 10,000.

A NOTE ON PLACEMENT. Christopher decided on 2026-09-07 that Westminster
petitions are collated and NEVER rendered in the weekly report. This is a
different edition and the whole point of the build was a section with
deadlines in it, so German petitions DO render -- but that is a decision he
should confirm, and de_monitor.SHOW_PETITIONS is the one line that reverses
it.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmllib
import http.cookiejar
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

BASE = "https://epetitionen.bundestag.de"
START = BASE + "/epet/petuebersicht.html"
# status.2 is the Mitzeichnungsfrist -- open for co-signature. batchsize is
# fixed at 8 by the server; anything else is rejected outright.
CARDS = (BASE + "/epet/petuebersicht/mz.nc.content.teaser-petitionen-cards."
         "$$$.ssi.true.status.2.page.{0}.batchsize.8.html")
DETAIL = BASE + "/petitionen/_{0}/_{1}/_{2}/Petition_{3}.nc.html"

MAX_PAGES = 30          # 81 petitions is 11; the cap is a runaway guard only
BODY_LIMIT = 40

CARD_SPLIT = re.compile(r'(?=<a[^>]+Petition_\d+\.nc\.html)')
PET_ID = re.compile(r"Petition_(\d+)\.nc\.html")
# THE DETAIL HREF IS TAKEN FROM THE CARD, never rebuilt from the id. The
# real path carries the date the petition opened --
# /petitionen/_2026/_07/_07/Petition_204144.nc.html -- and a URL assembled
# from the id alone is dead. Built that way it did not 404 cleanly either:
# the client retried it with backoff, so the run simply stopped making
# progress with nothing in the log to say why.
HREF = re.compile(r'href="(/petitionen/[^"]*Petition_\d+\.nc\.html)"')
EPOCH = re.compile(r"\b(1\d{12})\b")
SIGS = re.compile(r"Mitzeichnungen:\s*(\d+)")
TITLE = re.compile(r'title="([^"]{3,300})"')


def session_client(raw_dir):
    """An HttpClient carrying a cookie jar, with the session primed.

    The card endpoint returns ZERO BYTES without cookies -- not an error page,
    nothing at all -- so a client without a jar would report an empty feed
    rather than a broken one.
    """
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar))
    client = HttpClient(raw_dir=raw_dir, opener=opener)
    client.get_text(START, "de-petitions", "session", archive=False)
    return client


def text_of(fragment):
    return htmllib.unescape(re.sub(r"\s+", " ",
                                   re.sub(r"<[^>]+>", " ", fragment))).strip()


def iso(epoch_ms):
    return datetime.datetime.utcfromtimestamp(
        int(epoch_ms) / 1000).date().isoformat()


def parse_cards(page_html):
    """[{petition_id, title, topic, opened, closes, signatures}] for one page.

    A card missing its dates is KEPT, with them empty, and the caller counts
    it. Dropping it would hide a petition because of a markup change, and an
    item that vanishes looks exactly like an item that was never there.
    """
    out = []
    for part in CARD_SPLIT.split(page_html):
        m = PET_ID.search(part)
        if not m:
            continue
        flat = text_of(part)
        stamps = EPOCH.findall(part)
        title = TITLE.search(part)
        sigs = SIGS.search(flat)
        href = HREF.search(part)
        out.append({
            "petition_id": m.group(1),
            "url": BASE + href.group(1) if href else None,
            "title": htmllib.unescape(title.group(1)).strip() if title else None,
            "opened": iso(stamps[0]) if len(stamps) >= 1 else None,
            "closes": iso(stamps[1]) if len(stamps) >= 2 else None,
            "signatures": int(sigs.group(1)) if sigs else None,
        })
    return out


def pull(conn, client, today, log=print, max_pages=MAX_PAGES):
    """Every petition currently open for co-signature."""
    seen = new = undated = unlinked = 0
    for page in range(max_pages):
        try:
            raw = client.get_text(CARDS.format(page), "de-petitions",
                                  "cards-{0}".format(page), archive=False)
        except (FetchError, ValueError) as exc:
            log("  [gap] de-petitions: page {0} unreadable ({1})".format(
                page, str(exc)[:70]))
            db.record_gap(conn, "de-petitions",
                          "petition page {0} unreadable: {1}".format(
                              page, str(exc)[:110]), today)
            break
        cards = parse_cards(raw)
        if not cards:
            break               # past the last page
        for c in cards:
            seen += 1
            if not c["closes"]:
                undated += 1
            if not c["url"]:
                # Countable, not fatal: the row still carries its deadline,
                # which is the point of the section, and only the body read
                # is lost.
                unlinked += 1
            before = conn.execute(
                "SELECT 1 FROM de_petitions WHERE petition_id = ?",
                (c["petition_id"],)).fetchone()
            if not before:
                new += 1
            conn.execute(
                "INSERT INTO de_petitions (petition_id, title, opened, "
                "closes, signatures, url, first_seen, last_seen) VALUES "
                "(?,?,?,?,?,?,?,?) ON CONFLICT(petition_id) DO UPDATE SET "
                "title=excluded.title, closes=excluded.closes, "
                # url BELONGS in the conflict branch. Left out, a row already
                # in the store never receives it however many times the
                # collector runs -- which is precisely how 637 members kept a
                # NULL parliament for weeks. A column that only an INSERT can
                # fill is a column that existing rows will never have.
                "signatures=excluded.signatures, url=excluded.url, "
                "opened=COALESCE(de_petitions.opened, excluded.opened), "
                "last_seen=excluded.last_seen",
                (c["petition_id"], c["title"], c["opened"], c["closes"],
                 c["signatures"], c["url"], today, today))
            # The snapshot is what makes movement visible next week.
            conn.execute(
                "INSERT OR REPLACE INTO de_petition_snapshots "
                "(petition_id, captured_at, signatures) VALUES (?,?,?)",
                (c["petition_id"], today, c["signatures"]))
    conn.commit()
    if unlinked:
        log("  [gap] de-petitions: {0} petition(s) had no detail link; their "
            "text cannot be read".format(unlinked))
        db.record_gap(conn, "de-petitions",
                      "{0} petition(s) had no detail href".format(unlinked),
                      today)
    if undated:
        log("  [gap] de-petitions: {0} petition(s) carried no closing "
            "date".format(undated))
        db.record_gap(conn, "de-petitions",
                      "{0} petition(s) had no readable Mitzeichnungsfrist"
                      .format(undated), today)
    return seen, new


def read_bodies(conn, client, today, tax, wl, log=print, limit=BODY_LIMIT):
    """Classify each petition on its TEXT, not its title.

    A petition title is a subject line ("Strafprozessordnung"); the text and
    the Begründung are where the substance is. body_read is stamped either
    way so an unreadable petition is not retried for ever.
    """
    rows = conn.execute(
        "SELECT petition_id, title, url FROM de_petitions WHERE body_read IS "
        "NULL AND url IS NOT NULL ORDER BY closes LIMIT ?",
        (int(limit),)).fetchall()
    read = matched = failed = 0
    for r in rows:
        try:
            raw = client.get_text(r["url"], "de-petitions",
                                  "pet-" + r["petition_id"], archive=False)
            body = text_of(re.sub(r"<script.*?</script>", "", raw,
                                  flags=re.S))
        except (FetchError, ValueError) as exc:
            log("  [body] petition {0}: unreadable ({1})".format(
                r["petition_id"], str(exc)[:60]))
            conn.execute("UPDATE de_petitions SET body_read = ? WHERE "
                         "petition_id = ?", (today, r["petition_id"]))
            failed += 1
            continue
        read += 1
        hits = filt.match_passages(tax, wl, body, title=r["title"] or "")
        areas, terms, excerpt = filt.aggregate_passages(hits)
        if areas:
            matched += 1
            log("  [petition] {0} {1}: {2}".format(
                r["petition_id"], areas, (r["title"] or "")[:52]))
        conn.execute(
            "UPDATE de_petitions SET areas = ?, matched_terms = ?, "
            "excerpt = ?, body_read = ? WHERE petition_id = ?",
            (json.dumps(sorted(set(areas or []))),
             json.dumps(sorted(set(terms or []))),
             (excerpt or "")[:400] or None, today, r["petition_id"]))
    conn.commit()
    return read, matched, failed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-bodies", action="store_true")
    ap.add_argument("--limit", type=int, default=BODY_LIMIT)
    args = ap.parse_args()

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))
    client = session_client(os.path.join(ROOT, "data", "raw"))

    seen, new = pull(conn, client, today)
    read = matched = failed = 0
    if not args.no_bodies:
        read, matched, failed = read_bodies(conn, client, today, tax, wl,
                                            limit=args.limit)
    soon = conn.execute(
        "SELECT COUNT(*) FROM de_petitions WHERE closes >= ? AND closes <= ? "
        "AND areas IS NOT NULL AND areas != '[]'",
        (today, (datetime.date.fromisoformat(today)
                 + datetime.timedelta(days=14)).isoformat())).fetchone()[0]
    print("de-petitions: {0} open for co-signature, {1} new, {2} read, {3} on "
          "our ground, {4} unreadable; {5} on our ground close within 14 "
          "days.".format(seen, new, read, matched, failed, soon))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
