"""Pull the Register of Members' Financial Interests into the store.

    python3 tools/pull_interests.py

The Interests API only pages NEWEST-FIRST (its two sort orders are
PublishingDateDescending and CategoryAscending), which shapes the design:

- The first ever run is a full backfill (~4,100 interests, ~205 slow
  pages). It commits page by page and, if interrupted, resumes by skipping
  roughly what is already held -- the small overlap re-fetches a page or
  two, which the upsert makes harmless.
- Once a sweep has run to the end, a marker row ('interests-backfill' in
  pull_log) records that the register's depths have been reached, and
  every later run asks only for what was published since a fortnight
  before the newest row held -- a handful of requests.

Without the marker, a PublishedFrom cutoff after an interrupted
newest-first sweep would silently orphan the register's tail: the newest
rows would exist, the cutoff would clear them, and the old rows would
never be fetched at all.

This is the official public register, published by Parliament for
publication. The public page ships only a COUNT per member and a link to
the member's own register page; the structured detail stays in the store
for campaign research.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import HttpClient

API = "https://interests-api.parliament.uk/api/v1/Interests"
PAGE = 20          # the API's maximum take
MARKER = "interests-backfill"      # pull_log key; week-shaped column, reused
                                   # deliberately for a one-off completion flag


def upsert(conn, items):
    written = 0
    for it in items:
        member = it.get("member") or {}
        if not member.get("id"):
            continue     # an interest with no member cannot be filed
        conn.execute(
            "INSERT OR REPLACE INTO member_interest (interest_id, member_id, "
            "house, category, summary, registered, published, fields) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (it["id"], member["id"], member.get("house"),
             (it.get("category") or {}).get("name") or "?",
             it.get("summary"),
             (it.get("registrationDate") or "")[:10] or None,
             (it.get("publishedDate") or "")[:10] or None,
             json.dumps(it.get("fields") or [], separators=(",", ":"))))
        written += 1
    return written


def sweep(conn, client, since=None, skip=0):
    """Page from `skip` to the end; returns (written, completed)."""
    written, total = 0, None
    qs = "&PublishedFrom={0}".format(since) if since else ""
    while True:
        url = "{0}?Take={1}&Skip={2}{3}".format(API, PAGE, skip, qs)
        try:
            payload = client.get_json(url, "interests", "page", archive=False)
        except Exception as exc:
            db.record_gap(conn, "interests",
                          "page at skip={0}: {1}".format(skip, exc))
            return written, False
        if total is None:
            total = payload.get("totalResults") or 0
        items = payload.get("items") or []
        written += upsert(conn, items)
        conn.commit()            # page by page, so an interrupted run keeps
        skip += PAGE             # what it fetched
        if len(items) < PAGE or skip >= total:
            return written, True


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))

    done_before = conn.execute(
        "SELECT completed_at FROM pull_log WHERE week = ?", (MARKER,)).fetchone()
    if done_before:
        import datetime
        # The register publishes roughly fortnightly, so weekly sweeps are
        # mostly wasted requests (Christopher, 2026-08-31: "not a weekly
        # thing"). Run only when the last completed sweep is 13+ days old;
        # the sunday-pull step then fires it about every other week.
        last = (done_before[0] or "")[:10]
        today = datetime.date.today()
        if last and (today - datetime.date.fromisoformat(last)).days < 13:
            held = conn.execute(
                "SELECT COUNT(*) FROM member_interest").fetchone()[0]
            print("interests: swept {0}, register publishes fortnightly -- "
                  "skipping; {1} held".format(last, held))
            return 0
        newest = conn.execute(
            "SELECT MAX(published) FROM member_interest").fetchone()[0]
        cutoff = (datetime.date.fromisoformat(newest[:10])
                  - datetime.timedelta(days=14)).isoformat()
        written, completed = sweep(conn, client, since=cutoff)
        mode = "incremental since {0}".format(cutoff)
        if completed:
            conn.execute("UPDATE pull_log SET completed_at = datetime('now') "
                         "WHERE week = ?", (MARKER,))
            conn.commit()
    else:
        held = conn.execute(
            "SELECT COUNT(*) FROM member_interest").fetchone()[0]
        resume_at = (held // PAGE) * PAGE      # near where the last run died
        written, completed = sweep(conn, client, skip=resume_at)
        mode = "backfill from skip {0}".format(resume_at)
        if completed:
            conn.execute("INSERT OR REPLACE INTO pull_log (week, completed_at) "
                         "VALUES (?, datetime('now'))", (MARKER,))
            conn.commit()

    held, membered = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT member_id) FROM member_interest"
    ).fetchone()
    print("interests: {0} fetched ({1}, {2}); {3} held in total across "
          "{4} members".format(
              written, mode, "complete" if completed else "INTERRUPTED",
              held, membered))
    return 0 if completed else 1


if __name__ == "__main__":
    sys.exit(main())
