"""One-off six-month backfill of the MP intelligence ledger.

Sweeps every configured PQ term through the (slow) written-questions API,
paging back to the cutoff, plus EDM terms; taxonomy-filters each hit; writes
mp_events rows for the asker/sponsor and caches member resolutions.

Idempotent: record_event dedupes on (member, kind, ref), so re-running after
a network failure only fills gaps. Items are NOT written -- the ledger is
history; the items store remains the weekly editorial flow.

  python3 tools/backfill_mp_ledger.py 2026-02-03
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, intel, members
from src.http import FetchError, HttpClient
from src.ingest import edms, pqs

MAX_PAGES_PER_TERM = 5   # 5 x 100 answered PQs per term is ample for 6 months


def load_settings():
    import yaml
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve(conn, client, member_id, cache):
    if member_id in cache:
        return cache[member_id]
    try:
        member = members.resolve(conn, client, member_id)
    except FetchError:
        member = None
    cache[member_id] = member
    return member


def backfill_pqs(conn, client, tax, wl, terms, cutoff, cache):
    from urllib.parse import quote
    written = 0
    for term in terms:
        for page in range(MAX_PAGES_PER_TERM):
            url = ("https://questions-statements-api.parliament.uk/api/writtenquestions/questions"
                   "?searchTerm={0}&answered=Answered&take=100&skip={1}").format(quote(term), page * 100)
            try:
                payload = client.get_json(url, "pq", "backfill-{0}-p{1}".format(term, page))
            except FetchError as exc:
                print("  [gap] '{0}' page {1}: {2}".format(term, page, exc.cause))
                break
            batch = pqs.parse_response(payload)
            if not batch:
                break
            oldest = min((q.date_answered for q in batch if q.date_answered), default=None)
            for q in batch:
                if not q.date_answered or q.date_answered < cutoff:
                    continue
                r = filt.filter_item(tax, wl, q.heading or "", q.question_text or "", q.answer_text or "")
                if not r.matched() or not q.asking_member_id:
                    continue
                if resolve(conn, client, q.asking_member_id, cache) is None:
                    continue
                intel.record_event(conn, q.asking_member_id, q.date_answered.isoformat(),
                                   "pq", "pq:{0}".format(q.id), q.heading)
                written += 1
            if oldest and oldest < cutoff:
                break
        print("  pq '{0}' done ({1} events so far)".format(term, written))
    return written


def backfill_edms(conn, client, tax, wl, terms, cutoff, cache):
    written = 0
    for term in terms:
        try:
            motions = edms.fetch_edms(client, term, take=100)
        except FetchError as exc:
            print("  [gap] edm '{0}': {1}".format(term, exc.cause))
            continue
        for e in motions:
            if not e.date_tabled or e.date_tabled < cutoff:
                continue
            r = filt.filter_item(tax, wl, e.title or "", e.motion_text or "")
            if not r.matched():
                continue
            member_id = getattr(e, "member_id", None)
            if not member_id or resolve(conn, client, member_id, cache) is None:
                continue
            intel.record_event(conn, member_id, e.date_tabled.isoformat(),
                               "edm", "edm:{0}".format(e.id),
                               "Sponsored EDM: {0} ({1} signatures)".format(e.title, e.signature_count))
            written += 1
        print("  edm '{0}' done ({1} events so far)".format(term, written))
    return written


def main():
    cutoff = datetime.date.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2026-02-03")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    settings = load_settings()
    cache = {}

    print("backfilling ledger since {0}".format(cutoff))
    n_pq = backfill_pqs(conn, client, tax, wl, settings.get("pq_sweep_terms") or [], cutoff, cache)
    n_edm = backfill_edms(conn, client, tax, wl, settings.get("edm_sweep_terms") or [], cutoff, cache)
    print("done: {0} pq events, {1} edm events".format(n_pq, n_edm))
    print("ledger:", intel.ledger_stats(conn))
    conn.close()


if __name__ == "__main__":
    main()
