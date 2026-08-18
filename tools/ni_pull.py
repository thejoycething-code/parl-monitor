"""Harvest the Northern Ireland Assembly into its own table.

    python3 tools/ni_pull.py                  # questions since 2024, motions, diary
    python3 tools/ni_pull.py --since 2008-01-01   # the full eighteen-year history
    python3 tools/ni_pull.py --days 120       # a longer forward diary

Writes to `ni_items`, NEVER to `items`. The published edition is built by
"SELECT ... FROM items", so keeping NI in a separate table is what guarantees
it cannot appear in the Slack digest -- see the schema comment in src/db.py.

Classification reuses the WESTMINSTER taxonomy and the same `pq_sweep_terms`,
because the vocabulary is the same vocabulary. What differs is the ground: an
NI question about abortion is asking about a law imposed from outside, so the
same term carries different weight. That judgement belongs to a human reading
the monitor, not to a score computed here.

Gaps are recorded rather than raised. A sweep of forty terms must not lose
thirty-nine because one timed out, and the run prints what it failed to fetch.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import HttpClient
from src.ingest import niassembly

# Questions run to 2008. Two years is enough to read the current Assembly
# without making every run re-classify eighteen years of history; --since
# opens it up when you actually want the long view.
DEFAULT_SINCE_YEARS = 2
DEFAULT_DIARY_DAYS = 60


def load_filter():
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    return tax, wl


def sweep_terms():
    import yaml
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as fh:
        settings = yaml.safe_load(fh) or {}
    terms = settings.get("pq_sweep_terms") or []
    # The endpoint rejects anything shorter than three characters, so filter
    # here rather than burning a request to be told.
    return [t for t in terms if len(t) >= niassembly.MIN_SEARCH]


def store(conn, row, today):
    """Upsert one row, preserving first_seen. Same contract as un_store."""
    existing = conn.execute("SELECT first_seen FROM ni_items WHERE id = ?",
                            (row["id"],)).fetchone()
    first_seen = existing["first_seen"] if existing else today
    conn.execute(
        "INSERT OR REPLACE INTO ni_items (id, kind, reference, title, dated, "
        "tablers, parties, category, areas, matched_terms, url, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (row["id"], row["kind"], row.get("reference"), row.get("title"),
         row.get("dated"), row.get("tablers"),
         json.dumps(row.get("parties") or []), row.get("category"),
         json.dumps(row.get("areas") or []),
         json.dumps(row.get("matched_terms") or []),
         row.get("url"), first_seen, today))
    return existing is None


def main():
    today = datetime.date.today()
    since = today.replace(year=today.year - DEFAULT_SINCE_YEARS)
    if "--since" in sys.argv:
        since = datetime.date.fromisoformat(sys.argv[sys.argv.index("--since") + 1])
    days = DEFAULT_DIARY_DAYS
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax, wl = load_filter()
    terms = sweep_terms()
    print("NI Assembly harvest: questions since {0}, diary {1} days, {2} terms"
          .format(since.isoformat(), days, len(terms)))

    gaps, new, seen = [], 0, 0

    # -- questions ----------------------------------------------------------
    stored_q = {}
    for term in terms:
        found, err = niassembly.fetch_questions(client, term, since=since)
        if err:
            gaps.append("question term {0!r}: {1}".format(term, err))
            continue
        for q in found:
            # One question can match several sweep terms; classify once and
            # let the taxonomy decide the areas rather than the search term.
            stored_q[q.doc_id] = q
    for q in stored_q.values():
        res = filt.filter_item(tax, wl, q.text)
        if not res.matched():
            continue
        seen += 1
        new += store(conn, {
            "id": q.id, "kind": "question", "reference": q.reference,
            "title": q.text, "dated": q.tabled.isoformat() if q.tabled else None,
            "category": "oral" if q.oral else "written",
            "areas": res.issue_areas, "matched_terms": res.matched_terms,
            "url": q.url}, today.isoformat())

    # -- motions ------------------------------------------------------------
    try:
        motions = niassembly.fetch_motions(client, since=since)
    except Exception as exc:                        # noqa: BLE001
        motions = []
        gaps.append("no-day-named motions: {0}: {1}".format(type(exc).__name__, exc))
    for m in motions:
        res = filt.filter_item(tax, wl, m.title)
        if not res.matched():
            continue
        seen += 1
        new += store(conn, {
            "id": m.id, "kind": "motion", "title": m.title,
            "dated": m.tabled.isoformat() if m.tabled else None,
            "tablers": m.tablers_raw, "parties": m.parties,
            "category": m.category, "areas": res.issue_areas,
            "matched_terms": res.matched_terms, "url": None}, today.isoformat())

    # -- forward diary ------------------------------------------------------
    try:
        diary = niassembly.fetch_diary(client, today,
                                       today + datetime.timedelta(days=days))
    except Exception as exc:                        # noqa: BLE001
        diary = []
        gaps.append("business diary: {0}: {1}".format(type(exc).__name__, exc))
    for d in diary:
        # The diary carries no subject text -- only a committee name -- so it
        # is stored UNFILTERED and shown as context. Classifying a committee
        # name would flag "Committee for Health" on every health term and
        # bury the rows that matter.
        res = filt.filter_item(tax, wl, d.organisation)
        seen += 1
        new += store(conn, {
            "id": d.id, "kind": "diary", "title": d.organisation,
            "dated": d.starts.isoformat() if d.starts else None,
            "category": d.event_type, "areas": res.issue_areas,
            "matched_terms": res.matched_terms, "url": None}, today.isoformat())

    conn.commit()
    print("{0} classified row(s) stored, {1} of them new.".format(seen, new))
    if gaps:
        print("\n{0} gap(s) -- printed, never swallowed:".format(len(gaps)))
        for g in gaps:
            print("  * {0}".format(g))
    else:
        print("no gaps.")
    print("\nStored in ni_items, not items: this cannot reach the Slack digest.")
    print("Read it with: python3 tools/ni_monitor.py")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
