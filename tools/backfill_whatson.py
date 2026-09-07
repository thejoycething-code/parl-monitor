"""Fill this week's stored What's On rows with the event fields the table needs.

    python3 tools/backfill_whatson.py            # report only
    python3 tools/backfill_whatson.py --apply    # write

Christopher chose the Week ahead table on 2026-09-07 ("Go for pick C").
The renderer wants Parliament's event id, start and end time, house,
location, description and the leading member on every stored event, and
run_weekly stores them from this Sunday on. Rows already in the store
carry only the diary label, so this reads the raw What's On files the
pull saved under data/raw and matches each stored row to its event by
date and label. The item id is left alone: the judge's why-line hangs
off it. Duplicates (one per Sunday that saw the event) are left too; the
renderer folds them by event id.

ONE WRITER AT A TIME: pull the store first, push it after.
"""

import glob
import gzip
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import whatson


def raw_events():
    """{(date, label): Event} across every saved What's On range."""
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*", "whatson_range-*.json.gz"))):
        try:
            rows = json.load(gzip.open(path))
        except (OSError, ValueError):
            continue
        for row in rows if isinstance(rows, list) else []:
            e = whatson.parse_event(row)
            if e.start_date and e.id:
                out[(e.start_date.isoformat(), whatson.event_label(e))] = e
    return out


def payload(e):
    return {"event_id": e.id, "start_time": e.start_time or None,
            "end_time": e.end_time or None,
            "house": whatson._text(e.house) or None,
            "type": whatson._text(e.type) or None,
            "category": whatson._text(e.category) or None,
            "description": whatson._collapse(whatson._text(e.description)) or None,
            "bill_id": e.bill_id, "bill_name": e.bill_name or None,
            "members": e.members or []}


def main(argv):
    apply = "--apply" in argv
    db = os.path.join(ROOT, "data", "parl-monitor.db")
    conn = sqlite3.connect(db)
    events = raw_events()
    rows = conn.execute(
        "SELECT id, event_date, title, extra FROM items WHERE source_feed='whatson'").fetchall()
    filled, missing = 0, []
    for item_id, date, title, extra in rows:
        cur = json.loads(extra) if extra else {}
        if cur.get("event_id"):
            continue
        e = events.get((date, title))
        if not e:
            missing.append((item_id, title[:60]))
            continue
        cur.update(payload(e))
        if apply:
            conn.execute("UPDATE items SET extra=?, url=COALESCE(url, ?) WHERE id=?",
                         (json.dumps(cur), whatson.event_url(e), item_id))
        filled += 1
    if apply:
        conn.commit()
    print("whatson backfill: {0} row(s) {1}, {2} unmatched, {3} raw event(s) seen".format(
        filled, "filled" if apply else "would fill", len(missing), len(events)))
    for item_id, title in missing:
        print("   unmatched: {0}  {1}".format(item_id, title))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
