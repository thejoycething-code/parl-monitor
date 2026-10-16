"""UK Parliament e-petitions on our ground -> uk_petitions (16 October 2026).

    python3 tools/uk_petitions.py [--db PATH] [--full-closed] [--today YYYY-MM-DD]

Run by the Sunday pull (jobs/sunday-pull.sh) after run_weekly.py, so the
Monday edition can show petitions on our issues with their signatures, the
10,000 / 100,000 thresholds, the Government response and the Westminster
Hall debate.

SOURCE. petition.parliament.uk's public JSON (the "JSON" link on every
listing and petition page): /petitions.json?state=open|closed&page=N, 25 a
page ordered by signatures (each row carries the debate block: when it
was debated and the Hansard transcript), and /petitions/<id>.json for one
petition. robots.txt
(read 16 October 2026) disallows only admin, signing and sponsor paths;
every request here still asks it at run time (src/robots_guard.guard).

WHAT IS KEPT. Every petition the English taxonomy matches on its action +
background + additional details, open, or closed within the last
WINDOW_DAYS, under the same precision gate as the older collated sweep
(run_weekly.sweep_petitions): tier 1 or a watchlist name, or tier 2 once the
petition has 10,000 signatures (tier-2 vocabulary alone admitted 168 of 269
petitions on the first sweep, 7 September 2026). settings.petition_exclusions
apply. No signer data is stored (counts by constituency, the creator's name).

CLOSED PETITIONS. The listing has no date order, so finding the petitions
that closed in the last three months means reading every closed page (225 on
16 October 2026). That full scan runs when none has completed in the last
CLOSED_RESCAN_DAYS (and on --full-closed); every other week the petitions
already held that are not in the open listing any more are re-read one by
one from /petitions/<id>.json, which is how a petition that closed during
the week gets its final count.

FAILING LOUD. Every source that could not be read is a [gap] line and a
gaps row for the coming edition (the edition's footer prints them), and the
exit status is 1, so the Sunday pull's rc says so too.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, robots_guard, uk_civic_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.ingest import petitions  # noqa: E402

FEED = "uk_petitions"
LIST_API = "https://petition.parliament.uk/petitions.json?state={0}"
DETAIL_API = "https://petition.parliament.uk/petitions/{0}.json"
WINDOW_DAYS = 92
CLOSED_RESCAN_DAYS = 28
MAX_PAGES = {"open": 200, "closed": 400}
MAX_SECONDS = 15 * 60


def edition_week(today):
    """The UK edition the Sunday pull feeds: tomorrow's Monday on a Sunday,
    else this week's (jobs/sunday-pull.sh, WEEK)."""
    if today.weekday() == 6:
        return (today + datetime.timedelta(days=1)).isoformat()
    return (today - datetime.timedelta(days=today.weekday())).isoformat()


def write_gaps(conn, today, gaps):
    """The run's gaps, as rows for the edition the Sunday pull feeds (its
    footer prints them). run_weekly.py --pull clears that edition's gaps when
    it starts; this runs after it, so these stand."""
    edition = edition_week(today)
    for detail in gaps:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)", (edition, FEED, detail))
    conn.commit()
    return edition


def threshold(p):
    if p.debate_reached or p.signatures >= petitions.DEBATE_THRESHOLD:
        return "100k"
    if p.response_reached or p.signatures >= petitions.RESPONSE_THRESHOLD:
        return "10k"
    return None


def parse_row(row):
    """A petitions.Petition plus the fields this table adds (closed_at, the
    response summary, the debate block: listing and detail both carry it)."""
    p = petitions.parse_petition(row)
    a = row.get("attributes") or {}
    p.closed_at = petitions._day(a.get("closed_at"))
    resp = a.get("government_response") or {}
    p.response_summary = (resp.get("summary") or "").strip() or None
    if not p.government_response_at and resp.get("responded_on"):
        p.government_response_at = resp.get("responded_on")
    debate = a.get("debate") or {}
    p.debated_on = debate.get("debated_on")
    p.debate_url = debate.get("transcript_url") or None
    return p


def debate_date(p):
    return p.debated_on or p.scheduled_debate_date


def in_window(p, today):
    if p.state == "open":
        return True
    cutoff = (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    return bool(p.closed_at and p.closed_at >= cutoff)


def on_our_ground(tax, wl, p):
    """(FilterResult, kept?) under the collated sweep's precision gate."""
    r = filt.filter_item(tax, wl, p.action, p.text)
    if not r.matched():
        return r, False
    if not (r.tier == 1 or r.watchlist_hits) and p.signatures < petitions.RESPONSE_THRESHOLD:
        return r, False
    return r, True


def store(conn, p, r, today_iso):
    old = conn.execute("SELECT threshold_reached, threshold_first_seen FROM uk_petitions WHERE petition_id = ?",
                       (p.id,)).fetchone()
    th = threshold(p)
    if old is None:
        first_seen_th = today_iso if th else None
    elif (old["threshold_reached"] or None) != th:
        first_seen_th = today_iso if th else None
    else:
        first_seen_th = old["threshold_first_seen"]
    held = 1 if (p.debated_on or p.debate_outcome_at) else 0
    conn.execute(
        "INSERT INTO uk_petitions (petition_id, title, state, signatures, threshold_reached, response_date, "
        "debate_date, url, areas, matched_terms, first_seen, last_seen, tier, opened_at, closing_date, closed_at, "
        "response_threshold_at, debate_threshold_at, threshold_first_seen, debate_held, debate_url, "
        "response_summary, departments) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(petition_id) DO UPDATE SET title=excluded.title, state=excluded.state, "
        "signatures=excluded.signatures, threshold_reached=excluded.threshold_reached, "
        "response_date=excluded.response_date, debate_date=COALESCE(excluded.debate_date, uk_petitions.debate_date), "
        "url=excluded.url, areas=excluded.areas, matched_terms=excluded.matched_terms, last_seen=excluded.last_seen, "
        "tier=excluded.tier, opened_at=excluded.opened_at, closing_date=excluded.closing_date, "
        "closed_at=excluded.closed_at, response_threshold_at=excluded.response_threshold_at, "
        "debate_threshold_at=excluded.debate_threshold_at, threshold_first_seen=excluded.threshold_first_seen, "
        "debate_held=MAX(excluded.debate_held, COALESCE(uk_petitions.debate_held, 0)), "
        "debate_url=COALESCE(excluded.debate_url, uk_petitions.debate_url), "
        "response_summary=COALESCE(excluded.response_summary, uk_petitions.response_summary), "
        "departments=excluded.departments",
        (p.id, p.action, p.state, p.signatures, th, p.government_response_at, debate_date(p), p.url,
         json.dumps(r.issue_areas), json.dumps(r.matched_terms + r.watchlist_hits), today_iso, today_iso,
         r.tier, p.opened_at, p.closing_date or p.closed_at, p.closed_at, p.response_reached, p.debate_reached,
         first_seen_th, held, p.debate_url, p.response_summary, json.dumps(p.departments)))
    conn.execute("INSERT OR REPLACE INTO uk_petition_counts (petition_id, captured_at, signatures) VALUES (?,?,?)",
                 (p.id, today_iso, p.signatures))


class Sweep:
    def __init__(self, client, conn, tax, wl, today, log=print, clock=time.monotonic, max_seconds=MAX_SECONDS):
        self.client, self.conn, self.tax, self.wl = client, conn, tax, wl
        self.today, self.today_iso = today, today.isoformat()
        self.log = log
        self.clock = clock
        self.deadline = clock() + max_seconds
        self.gaps = []
        self.excluded = set()

    def gap(self, detail):
        self.gaps.append(detail)
        self.log("  [gap] {0}: {1}".format(FEED, detail))

    def listing(self, state):
        """-> ({id: Petition}, complete?) for every page of one state."""
        out, url, pages = {}, LIST_API.format(state), 0
        while url and pages < MAX_PAGES[state]:
            if self.clock() > self.deadline:
                self.gap("{0} listing stopped at page {1}: time budget spent; the rest is read next run"
                         .format(state, pages))
                return out, False
            try:
                payload = self.client.get_json(url, FEED, "{0}-p{1}".format(state, pages + 1), archive=False)
            except FetchError as exc:
                self.gap("{0} listing failed at page {1}: {2}".format(state, pages + 1, str(exc)[:160]))
                return out, False
            for row in payload.get("data") or []:
                if row.get("id"):
                    p = parse_row(row)
                    out[p.id] = p
            url = (payload.get("links") or {}).get("next")
            pages += 1
        if url:
            self.gap("{0} listing capped at {1} pages".format(state, pages))
            return out, False
        return out, True

    def detail(self, pid):
        try:
            payload = self.client.get_json(DETAIL_API.format(pid), FEED, "petition-{0}".format(pid))
        except FetchError as exc:
            self.gap("petition {0} could not be re-read: {1}".format(pid, str(exc)[:120]))
            return None
        data = payload.get("data") or {}
        return parse_row(data) if data.get("id") else None

    def keep(self, p):
        if p.id in self.excluded or not in_window(p, self.today):
            return None
        r, ok = on_our_ground(self.tax, self.wl, p)
        return r if ok else None

    def run(self, full_closed=False, settings=None):
        self.excluded = petitions.exclusions(settings or {})
        stats = {"open": 0, "closed": 0, "matched": 0, "reread": 0}
        open_rows, open_ok = self.listing("open")
        stats["open"] = len(open_rows)
        uk_civic_store.record_run(self.conn, FEED + ":open", self.today_iso, open_ok, len(open_rows))
        found = dict(open_rows)

        last_scan = uk_civic_store.last_ok_run(self.conn, FEED + ":closed-scan")
        due = full_closed or not last_scan or (
            self.today - datetime.date.fromisoformat(last_scan)).days >= CLOSED_RESCAN_DAYS
        if due:
            closed_rows, closed_ok = self.listing("closed")
            stats["closed"] = len(closed_rows)
            uk_civic_store.record_run(self.conn, FEED + ":closed-scan", self.today_iso, closed_ok,
                                      len(closed_rows))
            for pid, p in closed_rows.items():
                found.setdefault(pid, p)
        # Held petitions missing from this run's listings: closed during the
        # week (or since the last full scan). Re-read each; only a complete
        # open listing proves absence.
        if open_ok:
            cutoff = (self.today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
            held = [r[0] for r in self.conn.execute(
                "SELECT petition_id FROM uk_petitions WHERE state = 'open' OR closed_at >= ?", (cutoff,))]
            for pid in held:
                if pid in found:
                    continue
                if self.clock() > self.deadline:
                    self.gap("re-reads stopped: time budget spent")
                    break
                p = self.detail(pid)
                if p:
                    found[pid] = p
                    stats["reread"] += 1

        kept = []
        for p in found.values():
            r = self.keep(p)
            if r is not None:
                kept.append((p, r))
        for p, r in kept:
            store(self.conn, p, r, self.today_iso)
        self.conn.commit()
        stats["matched"] = len(kept)
        uk_civic_store.record_run(self.conn, FEED, self.today_iso, not self.gaps,
                                  len(found), len(kept), "; ".join(self.gaps)[:500] or None)
        return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--full-closed", action="store_true", help="read every closed page this run")
    ap.add_argument("--today", help="YYYY-MM-DD (tests and replays)")
    ap.add_argument("--max-seconds", type=int, default=MAX_SECONDS)
    args = ap.parse_args(argv)
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    conn = db.init_db(db.connect(args.db))
    client = robots_guard.guard(HttpClient(raw_dir=os.path.join(ROOT, "data", "raw")), FEED)
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    import yaml
    settings_path = os.path.join(ROOT, "config", "settings.yaml")
    settings = yaml.safe_load(open(settings_path, encoding="utf-8")) if os.path.exists(settings_path) else {}
    sweep = Sweep(client, conn, tax, wl, today, max_seconds=args.max_seconds)
    try:
        stats = sweep.run(full_closed=args.full_closed, settings=settings or {})
    except Exception as exc:                                # noqa: BLE001
        sweep.gap("sweep failed: {0}".format(str(exc)[:200]))
        stats = {}
    write_gaps(conn, today, sweep.gaps)
    print("uk_petitions: {0} open, {1} closed read, {2} re-read; {3} on our ground; {4} gap(s)".format(
        stats.get("open", 0), stats.get("closed", 0), stats.get("reread", 0), stats.get("matched", 0),
        len(sweep.gaps)))
    return 1 if sweep.gaps else 0


if __name__ == "__main__":
    sys.exit(main())
