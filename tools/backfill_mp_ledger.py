"""Historic backfill of the MP intelligence ledger (PQs + EDMs).

    python3 tools/backfill_mp_ledger.py 2020-01-01 2026-08-24
    python3 tools/backfill_mp_ledger.py 2020-01-01 --terms religious-education

Sweeps every configured PQ term through the (slow) written-questions API and
every EDM term through the motions API, in YEAR WINDOWS from the cutoff --
both APIs take date filters, so each term-year pages independently and no
window needs deep skip pagination. Taxonomy-filters each hit (tier-1 or
watchlist precision gate); writes mp_events rows for askers, sponsors and
EDM co-signatories; caches member resolutions.

Idempotent: record_event upserts on (member, kind, ref), so re-running after
a network failure only fills gaps, and re-runs refresh annotations. Items
are NOT written -- the ledger is history; the items store remains the weekly
editorial flow.

  python3 tools/backfill_mp_ledger.py 2020-01-01
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

MAX_PAGES_PER_WINDOW = 10   # 1000 answered PQs per term-year is ample


def year_windows(cutoff, end):
    """[(from, to)] ISO date pairs, one per calendar year in the range."""
    windows = []
    for year in range(cutoff.year, end.year + 1):
        start = max(cutoff, datetime.date(year, 1, 1))
        stop = min(end, datetime.date(year, 12, 31))
        windows.append((start.isoformat(), stop.isoformat()))
    return windows


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


def backfill_pqs(conn, client, tax, wl, terms, cutoff, end, cache):
    from urllib.parse import quote
    written = 0
    windows = year_windows(cutoff, end)
    for term in terms:
        for w_from, w_to in windows:
            for page in range(MAX_PAGES_PER_WINDOW):
                url = ("https://questions-statements-api.parliament.uk/api/writtenquestions/questions"
                       "?searchTerm={0}&answered=Answered&take=100&skip={1}"
                       "&answeredWhenFrom={2}&answeredWhenTo={3}").format(
                           quote(term), page * 100, w_from, w_to)
                try:
                    payload = client.get_json(
                        url, "pq", "backfill-{0}-{1}-p{2}".format(term, w_from[:4], page))
                except FetchError as exc:
                    print("  [gap] '{0}' {1} page {2}: {3}".format(term, w_from[:4], page, exc.cause))
                    break
                batch = pqs.parse_response(payload)
                if not batch:
                    break
                for q in batch:
                    if not q.date_answered:
                        continue
                    r = filt.filter_item(tax, wl, q.heading or "", q.question_text or "", q.answer_text or "")
                    if not (r.tier == 1 or r.watchlist_hits) or not q.asking_member_id:
                        continue  # tier-2-only matches are untriaged noise here
                    if resolve(conn, client, q.asking_member_id, cache) is None:
                        continue
                    intel.record_event(conn, q.asking_member_id, q.date_answered.isoformat(),
                                       "pq", "pq:{0}".format(q.id),
                                       intel.annotated_line(q.heading, r.matched_terms + r.watchlist_hits),
                                       areas=r.issue_areas)
                    written += 1
                if len(batch) < 100:
                    break
        print("  pq '{0}' done ({1} events so far)".format(term, written))
    return written


def backfill_edms(conn, client, tax, wl, terms, cutoff, end, cache):
    written = 0
    for term in terms:
        motions, skip = [], 0
        failed = False
        for w_from, w_to in year_windows(cutoff, end):
            skip = 0
            while True:
                try:
                    batch = edms.fetch_edms(client, term, take=100, skip=skip,
                                            tabled_from=w_from, tabled_to=w_to)
                except FetchError as exc:
                    print("  [gap] edm '{0}' {1}: {2}".format(term, w_from[:4], exc.cause))
                    failed = True
                    break
                motions.extend(batch)
                if len(batch) < 100:
                    break
                skip += 100
            if failed:
                break
        seen = set()
        for e in motions:
            if e.id in seen:
                continue
            seen.add(e.id)
            if not e.date_tabled or e.date_tabled < cutoff:
                continue
            r = filt.filter_item(tax, wl, e.title or "", e.motion_text or "")
            if not (r.tier == 1 or r.watchlist_hits):
                continue
            member_id = getattr(e, "member_id", None)
            if member_id and resolve(conn, client, member_id, cache) is not None:
                intel.record_event(conn, member_id, e.date_tabled.isoformat(),
                                   "edm", "edm:{0}".format(e.id),
                                   intel.annotated_line(
                                       "Sponsored EDM: {0} ({1} signatures)".format(e.title, e.signature_count),
                                       r.matched_terms + r.watchlist_hits),
                                   areas=r.issue_areas)
                written += 1
            # Co-signatories: one detail call per matched EDM; member details
            # are embedded so the cache seeds without Members API traffic.
            try:
                sponsors = edms.fetch_sponsors(client, e.id)
            except FetchError as exc:
                print("  [gap] edm {0} sponsors: {1}".format(e.id, exc.cause))
                sponsors = []
            for s in sponsors:
                if s.withdrawn or not s.member_id or (s.order or 0) <= 1:
                    continue
                if s.name and not members.cache_get(conn, s.member_id):
                    members.cache_put(conn, members.Member(
                        id=s.member_id, name=s.name, party=s.party,
                        seat=s.seat, house="Commons"))
                intel.record_event(conn, s.member_id, e.date_tabled.isoformat(),
                                   "edm-signed", "edm:{0}".format(e.id),
                                   intel.annotated_line("Signed EDM: {0}".format(e.title),
                                                        r.matched_terms + r.watchlist_hits),
                                   areas=r.issue_areas)
                written += 1
        print("  edm '{0}' done ({1} events so far)".format(term, written))
    return written


def _scoped(configured, wanted, label):
    """Sweep terms narrowed by --terms, so adding ONE taxonomy term does not
    mean re-sweeping all 44 across seven years. Names are matched exactly and
    an unknown one is an error, not a silent empty sweep."""
    if not wanted:
        return configured
    unknown = [t for t in wanted if t not in configured]
    if unknown:
        raise SystemExit("not in {0}: {1}\nconfigured: {2}".format(
            label, ", ".join(unknown), ", ".join(map(str, configured))))
    return [t for t in configured if t in wanted]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    wanted = []
    if "--terms" in sys.argv:
        wanted = [t.strip() for t in
                  sys.argv[sys.argv.index("--terms") + 1].split(",") if t.strip()]
    cutoff = datetime.date.fromisoformat(args[0] if args else "2026-02-03")
    end = datetime.date.fromisoformat(args[1]) if len(args) > 1 else datetime.date.today()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    settings = load_settings()
    cache = {}

    print("backfilling ledger {0} -> {1}".format(cutoff, end))
    pq_terms = _scoped(settings.get("pq_sweep_terms") or [], wanted,
                       "pq_sweep_terms")
    edm_terms = _scoped(settings.get("edm_sweep_terms") or [], wanted,
                        "edm_sweep_terms") if not wanted else [
        t for t in (settings.get("edm_sweep_terms") or []) if t in wanted]
    if wanted:
        print("scoped to: pq {0} | edm {1}".format(pq_terms or "-",
                                                   edm_terms or "-"))
    n_pq = backfill_pqs(conn, client, tax, wl, pq_terms, cutoff, end, cache)
    n_edm = backfill_edms(conn, client, tax, wl, edm_terms, cutoff, end, cache)
    print("done: {0} pq events, {1} edm events".format(n_pq, n_edm))
    print("ledger:", intel.ledger_stats(conn))
    conn.close()


if __name__ == "__main__":
    main()
