#!/usr/bin/env python3
"""What the Bundestag's committees are about to sit on.

    python3 tools/de_agenda.py
    python3 tools/de_agenda.py --no-bodies      # feed only, no PDF reads

Christopher, 22 September 2026: "The focus should be on upcoming items and
debates with the weekly canvas, not what's in the past."

WHY THIS EXISTS AT ALL, measured 23 September 2026: DIP returns ZERO results
for any future date. It is a record of what has happened, not a diary, so the
stage of a Vorgang was the only forward signal the monitor had -- "referred to
committee" tells you something is pending but never WHEN. This feed does: it
lists sittings still to come, with their dates.

WHAT THE SOURCE IS, AND WHAT IT IS NOT
--------------------------------------
https://www.bundestag.de/static/appdata/includes/rss/tagesordnungen.rss

It is a ROLLING WINDOW of about fifteen items covering the days immediately
ahead -- not a term's calendar, and not a plenary diary. Miss a week and that
week is gone; there is no archive to backfill from, which is why the collector
runs weekly and stores what it sees rather than re-deriving it. The edition
says how far ahead the feed actually reached, because "nothing on our ground
next month" and "the feed only goes to Friday" are different facts.

THE SUBJECT IS IN THE PDF. The RSS title carries the committee, the sitting
number, the date and whether it is public -- but not what is ON the agenda. A
committee name is far too broad to classify on ("Digitales,
Staatsmodernisierung" would match nothing or everything), so the agenda PDF is
read and each Tagesordnungspunkt matched against config/taxonomy-de.yaml, the
same body-matching tools/de_documents.py does for Drucksachen. Probed first:
these PDFs are real text, about 6,000 characters over four pages, with
numbered agenda points carrying bill titles and BT-Drucksache numbers.

NO VERDICTS and no inference about what a committee will decide. This says
what is on the paper and when.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "https://www.bundestag.de/static/appdata/includes/rss/tagesordnungen.rss"
DC = "{http://purl.org/dc/elements/1.1/}"

# A sitting whose agenda we will read. Kept low deliberately: the window only
# ever holds about fifteen, and a cap that is never reached is a cap that
# cannot surprise anyone.
BODY_LIMIT = 40

DRUCKSACHE = re.compile(r"BT-Drucks(?:ache)?\.?\s*(\d{1,2}/\d{1,6})")
TOP = re.compile(r"Tagesordnungspunkt\s+\d+", re.I)


def openness(title):
    """Public, partly public, or closed -- from the RSS title's own wording.

    Worth carrying: a public hearing (öffentliche Anhörung) is a sitting we
    could attend or brief for, and a closed one is not.
    """
    low = (title or "").lower()
    # ORDER MATTERS, and getting it wrong inverts the answer: "nicht
    # öffentlich" and "teilweise öffentlich" both CONTAIN "öffentlich", so a
    # plain substring test on the short word first labels a closed sitting
    # public. The narrowest phrase is tested first for exactly that reason.
    if "nicht öffentlich" in low:
        return "closed"
    if "teilweise öffentlich" in low:
        return "partly public"
    if "öffentlich" in low:            # covers "öffentliche Anhörung"
        return "public"
    return None


def committee_of(title):
    """The Ausschuss, which the feed puts before the first colon."""
    return (title or "").split(":", 1)[0].strip() or None


def parse_feed(xml_text):
    """[(item_id, committee, title, date, time, openness, url)] for every item.

    Dates come from dc:date, which is ISO and unambiguous; the German date in
    the title is not parsed. A date that cannot be read is NOT dropped -- the
    row is stored dateless and disclosed, because an item silently discarded
    for a format change is indistinguishable from a quiet week.
    """
    out = []
    root = ET.fromstring(xml_text)
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or "").strip() or link
        raw = (it.findtext(DC + "date") or "").strip()
        date = time = None
        try:
            stamp = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            date, time = stamp.date().isoformat(), stamp.strftime("%H:%M")
        except ValueError:
            pass
        if not guid:
            continue
        out.append((guid, committee_of(title), title, date, time,
                    openness(title), link or guid))
    return out


def pull(conn, client, today, log=print):
    """Store every sitting the feed is carrying. Upsert, so a sitting whose
    agenda is amended (the feed issues Ergänzungsmitteilungen) re-stamps
    rather than duplicating."""
    try:
        raw = client.get_text(FEED, "de-agenda", "tagesordnungen")
    except (FetchError, ValueError) as exc:
        log("  [gap] de-agenda: feed unreadable ({0})".format(str(exc)[:80]))
        db.record_gap(conn, "de-agenda",
                      "Tagesordnungen feed unreadable: {0}".format(str(exc)[:120]),
                      today)
        return 0, 0, None
    try:
        items = parse_feed(raw)
    except ET.ParseError as exc:
        log("  [gap] de-agenda: feed is not XML ({0})".format(str(exc)[:80]))
        db.record_gap(conn, "de-agenda",
                      "Tagesordnungen feed unparseable: {0}".format(str(exc)[:120]),
                      today)
        return 0, 0, None
    new = 0
    undated = 0
    horizon = None
    for item_id, cttee, title, date, time, open_, url in items:
        if date is None:
            undated += 1
        elif horizon is None or date > horizon:
            horizon = date
        before = conn.execute("SELECT 1 FROM de_agenda WHERE item_id = ?",
                              (item_id,)).fetchone()
        if not before:
            new += 1
        conn.execute(
            "INSERT INTO de_agenda (item_id, kind, committee, title, date, "
            "time, openness, url, first_seen, last_seen) VALUES "
            "(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET "
            "title=excluded.title, date=excluded.date, time=excluded.time, "
            "openness=excluded.openness, last_seen=excluded.last_seen",
            (item_id, "committee", cttee, title, date, time, open_, url,
             today, today))
    conn.commit()
    if undated:
        # SAID, not swallowed. A date format change would otherwise empty the
        # forward section while the run reported success.
        log("  [gap] de-agenda: {0} item(s) carried no readable date".format(undated))
        db.record_gap(conn, "de-agenda",
                      "{0} agenda item(s) had no readable dc:date".format(undated),
                      today)
    return len(items), new, horizon


def read_text(client, url):
    """The agenda PDF as text. Probed 23 September 2026: these are real text,
    about 6,000 characters over four pages, not scans."""
    import pypdf
    blob = client.get_bytes(url, "de-agenda", "to-" + url.rsplit("/", 1)[-1])
    reader = pypdf.PdfReader(io.BytesIO(blob))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def read_bodies(conn, client, today, tax, wl, log=print, limit=BODY_LIMIT):
    """Read each unread agenda and classify it on its CONTENT.

    body_read is stamped whether the read worked or not: an agenda that cannot
    be parsed must not be retried every week for ever.
    """
    # EVERY unread agenda in the window, not just the future-dated ones.
    # The first live run read 6 of 15 because it filtered on date >= today --
    # and the nine it skipped included Gesundheit, Inneres and Menschenrechte,
    # the three committees most likely to be on our ground. They had sat the
    # previous day. Since body_read stays NULL for a skipped row and the feed
    # is a ROLLING WINDOW with no archive, those agendas would never have been
    # read by any later run: the window drops them and nothing brings them
    # back. Reading the lot costs fifteen PDFs at most; the EDITION decides
    # what is still ahead, which is a display question, not a collection one.
    rows = conn.execute(
        "SELECT item_id, title, url FROM de_agenda WHERE body_read IS NULL "
        "ORDER BY date DESC LIMIT ?", (int(limit),)).fetchall()
    read = matched = failed = 0
    for r in rows:
        try:
            body = read_text(client, r["url"])
        except Exception as exc:                            # noqa: BLE001
            # pypdf raises a zoo of its own exceptions; any of them means the
            # same thing here and none should stop the run.
            log("  [body] {0}: unreadable ({1})".format(
                (r["title"] or "?")[:40], str(exc)[:60]))
            conn.execute("UPDATE de_agenda SET body_read = ? WHERE item_id = ?",
                         (today, r["item_id"]))
            failed += 1
            continue
        if not body.strip():
            conn.execute("UPDATE de_agenda SET body_read = ? WHERE item_id = ?",
                         (today, r["item_id"]))
            failed += 1
            continue
        read += 1
        # The committee name is NOT passed as the title: it is broad enough to
        # drag in matches the agenda itself does not support.
        hits = filt.match_passages(tax, wl, body)
        areas, terms, excerpt = filt.aggregate_passages(hits)
        drucks = sorted(set(DRUCKSACHE.findall(body)))
        if areas:
            matched += 1
            log("  [agenda] {0} {1}: {2}".format(
                r["item_id"][-12:], areas, (r["title"] or "")[:52]))
        conn.execute(
            "UPDATE de_agenda SET areas = ?, matched_terms = ?, excerpt = ?, "
            "drucksachen = ?, body_read = ? WHERE item_id = ?",
            (json.dumps(sorted(set(areas or []))),
             json.dumps(sorted(set(terms or []))),
             (excerpt or "")[:400] or None, json.dumps(drucks), today,
             r["item_id"]))
    conn.commit()
    return read, matched, failed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-bodies", action="store_true",
                    help="store the feed without reading any agenda PDF")
    ap.add_argument("--limit", type=int, default=BODY_LIMIT)
    args = ap.parse_args()

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))

    seen, new, horizon = pull(conn, client, today)
    read = matched = failed = 0
    if not args.no_bodies:
        read, matched, failed = read_bodies(conn, client, today, tax, wl,
                                            limit=args.limit)
    # The horizon is reported EVERY run. "Nothing on our ground next month"
    # and "the feed only reaches Friday" look identical in an edition that
    # does not say how far it could see.
    print("de-agenda: {0} sitting(s) in the window, {1} new, {2} agenda(s) "
          "read, {3} on our ground, {4} unreadable; feed reaches {5}.".format(
              seen, new, read, matched, failed, horizon or "no dated item"))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
