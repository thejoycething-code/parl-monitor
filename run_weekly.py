"""Weekly orchestrator (handoff section 8): pull -> filter -> triage -> store,
then render the Monday edition as a byproduct of the store.

Two-phase, per the handoff cron design (Sunday pull, Monday render):

  python3 run_weekly.py --pull 2026-07-06     # ingest + triage + emit review file
  python3 run_weekly.py --render 2026-07-06   # apply review edits, render edition
  python3 run_weekly.py --draft 2026-07-06    # pull + render immediately, no human step

Mode is detected from What's On for the edition week: zero Commons/Lords chamber
events => recess. Feeds are pulled live through src/http.py.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

import yaml

from src import board, db, digest, filter as filt, review, triage
from src.http import FetchError, HttpClient
from src.ingest import bills, consultations, divisions, edms, legislation, pqs, scotland, sis, whatson, wms

ROOT = os.path.dirname(os.path.abspath(__file__))


def board_bill_specs(wl):
    """(live, closure_candidates) as {bill_id: spec} from watchlist.yaml.

    Live bills come from `bills:`; closure candidates are `fallen_bills:` plus
    any `acts_watch:` entry carrying a bill_id. `why` renders on the board.
    """
    live = {int(k): dict(v) for k, v in (wl.bills_raw or {}).items()}
    candidates = {int(k): dict(v) for k, v in (wl.fallen_raw or {}).items()}
    for act in (wl.acts_raw or []):
        if act.get("bill_id"):
            candidates[int(act["bill_id"])] = {
                "areas": act.get("areas") or [], "why": act.get("why")}
    return live, candidates


def build_board_rows(client, run_date, closed_bill_ids=None, wl=None):
    """Live board rows plus any newly-discovered closures.

    closed_bill_ids are the bills already closed in a prior edition; they are
    excluded so a closing entry renders in exactly one edition (handoff 8).
    """
    if wl is None:
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    live_specs, candidate_specs = board_bill_specs(wl)

    def decorate(row, spec):
        row.areas = ",".join(str(a) for a in (spec.get("areas") or []))
        row.why = spec.get("why")
        return row

    live_bills = [bills.load_bill(client, bid) for bid in live_specs]
    candidates = [bills.load_bill(client, bid) for bid in candidate_specs]
    session = board.current_session_id(live_bills + candidates)
    rows = [decorate(board.build_row(b, session, run_date, prior_snapshot=None),
                     live_specs[b.bill_id]) for b in live_bills]
    closures = board.discover_closures(candidates, session, run_date,
                                       closed_bill_ids=closed_bill_ids or set())
    closures = [decorate(row, candidate_specs.get(row.bill_id, {})) for row in closures]
    return rows + closures, closures


def holyrood_rows(client, watchlist):
    """Board rows for watched Holyrood bills (handoff 4.11, acceptance 9.2).

    bills_board.bill_id is a shared integer PK, so Holyrood bills are namespaced
    with a negative id derived from their data.parliament.scot ID to guarantee no
    collision with Westminster billIds.
    """
    rows, closures = [], []
    for bill in scotland.load_watched(client, watchlist.holyrood):
        entry = next((h for h in watchlist.holyrood if h.get("slug") == bill.slug), {})
        board_id = -abs(int(entry.get("scot_id") or abs(hash(bill.slug)) % 10 ** 6))
        row = board.BoardRow(
            bill_id=board_id, title=bill.title, sponsor=None, house="Holyrood",
            stage=bill.stage or "", next_key_date=board.TBA,
            status="closed" if bill.is_terminal else "live",
            transition=board.FALLEN if bill.status == scotland.FELL else (
                board.ROYAL_ASSENT if bill.status == scotland.ASSENT else board.NEW),
            closed_note=bill.closed_note(),
            areas=",".join(str(a) for a in bill.areas),
            why=entry.get("why"),
            url=bill.url,
        )
        rows.append(row)
        if row.status == "closed":
            closures.append(row)
    return rows, closures


def load_settings():
    path = os.path.join(ROOT, "config", "settings.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def store_item(conn, item_id, feed, item_type, title, url, result, event_date=None, deadline=None,
               date_tabled=None):
    """Store a matched item with triage_score NULL (= pending triage).

    Scoring is a separate pass (stub, session, or live) over pending items;
    baking a score in at ingest would let the crude keyword tier make the
    editorial call the section 7 triage pass is supposed to make.
    """
    # Upsert: feed-sourced fields refresh on re-pull; editorial fields
    # (triage_score, priority_tag, owner, why_it_matters) are never touched,
    # so re-running a pull cannot wipe scoring or review decisions.
    conn.execute(
        "INSERT INTO items (id, captured_at, source_feed, item_type, title, url, "
        "event_date, deadline, date_tabled, issue_areas, matched_terms, tier, triage_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL) "
        "ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at, title=excluded.title, "
        "url=excluded.url, event_date=excluded.event_date, deadline=excluded.deadline, "
        "date_tabled=excluded.date_tabled, issue_areas=excluded.issue_areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier",
        (item_id, datetime.date.today().isoformat(), feed, item_type, title, url, event_date, deadline,
         date_tabled,
         json.dumps(result.issue_areas), json.dumps(result.matched_terms + result.watchlist_hits),
         result.tier),
    )
    conn.commit()


def record_gap(conn, edition, feed, detail):
    conn.execute("INSERT INTO gaps (edition, feed, detail) VALUES (?, ?, ?)",
                 (edition, feed, detail))
    conn.commit()


def sweep_pqs(client, conn, tax, wl, week_start, edition, terms):
    """Weekly written-questions sweep (handoff 4.2, 3).

    The API is slow and flaky; a term that fails after retries is logged to
    gaps and disclosed in the footer, never silently dropped. Results are
    filtered client-side on dateAnswered (never answeredWhenFrom) and then
    through the taxonomy: Parliament's search relevance is loose.
    """
    since = week_start - datetime.timedelta(days=7)
    for term in terms:
        try:
            questions = pqs.fetch_questions(client, term)
        except FetchError as exc:
            record_gap(conn, edition, "pq",
                       "sweep term '{0}' failed after {1} attempts; results missing this week".format(
                           term, exc.attempts))
            continue
        for q in pqs.since(questions, since):
            r = filt.filter_item(tax, wl, q.heading or "", q.question_text or "", q.answer_text or "")
            if not r.matched():
                continue
            title = "PQ {0} ({1}): {2}, answered {3}".format(
                q.uin, q.house, q.heading, q.date_answered)
            store_item(conn, "pq:{0}".format(q.id), "pq", "question", title, q.url, r,
                       event_date=q.date_answered.isoformat() if q.date_answered else None,
                       date_tabled=q.date_tabled.isoformat() if q.date_tabled else None)


def sweep_edms(client, conn, tax, wl, week_start, edition, terms):
    """Weekly EDM sweep (handoff 4.4): store new tagged motions and record
    signature counts per edition for week-on-week deltas."""
    since = week_start - datetime.timedelta(days=7)
    seen = set()
    for term in terms:
        try:
            motions = edms.fetch_edms(client, term)
        except FetchError as exc:
            record_gap(conn, edition, "edm",
                       "sweep term '{0}' failed after {1} attempts".format(term, exc.attempts))
            continue
        for e in motions:
            if e.id in seen:
                continue
            seen.add(e.id)
            r = filt.filter_item(tax, wl, e.title or "", e.motion_text or "")
            if not r.matched():
                continue
            edms.record_signatures(conn, e, edition)  # delta tracking, any age
            if e.date_tabled and e.date_tabled >= since:
                title = "EDM {0}: {1} ({2}, {3} signatures)".format(
                    e.uin, e.title, e.sponsor_name, e.signature_count)
                store_item(conn, "edm:{0}".format(e.id), "edm", "edm", title, e.url, r,
                           event_date=e.date_tabled.isoformat())


def _tag(result):
    return "WATCH" if (result.tier == 1 or result.watchlist_hits) else "NOTE"


def ingest_all(client, conn, tax, wl, week_start, week_end):
    """Fetch every Phase 1 feed, filter, and store surviving items."""
    edition = week_start.isoformat()
    settings = load_settings()

    # Sweeps are already per-term resilient (a failed term -> gaps row).
    sweep_pqs(client, conn, tax, wl, week_start, edition, settings.get("pq_sweep_terms") or [])
    sweep_edms(client, conn, tax, wl, week_start, edition, settings.get("edm_sweep_terms") or [])

    def _consultations():
        for c in consultations.fetch_open_consultations(client):
            r = filt.filter_item(tax, wl, c.title)
            if r.matched():
                store_item(conn, "consultation:" + c.link, "consultation", "consultation",
                           "Consultation: " + c.title, c.url, r,
                           deadline=c.end_date.isoformat() if c.end_date else None)

    def _sis():
        div51 = next((d for d in divisions.fetch_commons_divisions(client, "2026-07-08") if d.number == 51), None)
        for si in sis.fetch_sis(client, "Children's Wellbeing"):
            r = filt.filter_item(tax, wl, si.name)
            if not r.matched():
                continue
            note = "SI: {0}, {1}, laid {2}".format(si.name, si.procedure, si.laid_date)
            if div51 and divisions.matches_watchlist(div51.title, [e[0] for e in wl.act_shorts]):
                note += "; approved by Commons division #{0} ({1}-{2} on {3})".format(
                    div51.number, div51.aye_count, div51.no_count, div51.date)
            store_item(conn, "si:" + str(si.id), "si", "si", note, div51.url if div51 else None, r,
                       event_date=si.laid_date.isoformat() if si.laid_date else None)

    def _whatson():
        for e in whatson.fetch_events(client, week_start, week_end):
            text = whatson.event_text(e)
            r = filt.filter_item(tax, wl, text)
            if not r.matched():
                continue
            label = whatson.event_label(e)
            event_date = e.start_date.isoformat() if e.start_date else None
            store_item(conn, "whatson:{0}:{1}".format(event_date, abs(hash(label)) % 10 ** 8),
                       "whatson", "event", label, None, r, event_date=event_date)

    def _divisions():
        day = week_start
        while day <= week_end:
            for dv in divisions.fetch_commons_divisions(client, day.isoformat()):
                r = filt.filter_item(tax, wl, dv.title or "")
                if r.matched():
                    title = " ".join((dv.title or "").split())  # source carries double spaces
                    store_item(conn, "division:{0}".format(dv.id), "division", "division",
                               "Division #{0} ({1}-{2}): {3}".format(dv.number, dv.aye_count, dv.no_count, title),
                               dv.url, r, event_date=dv.date.isoformat() if dv.date else None)
            day += datetime.timedelta(days=1)

    def _wms():
        for st in wms.fetch_statements(client, week_start.isoformat(), take=80):
            if not (st.made_when and week_start <= st.made_when <= week_end):
                continue
            r = filt.filter_item(tax, wl, st.title or "", st.text or "")
            if r.matched():
                store_item(conn, "wms:{0}".format(st.id), "wms", "statement",
                           "WMS ({0}): {1}".format(st.house, st.title), None, r,
                           event_date=st.made_when.isoformat())

    # One failing feed degrades to a disclosed gap; the pull continues.
    for feed_name, fetch in [("consultation", _consultations), ("si", _sis),
                             ("whatson", _whatson), ("division", _divisions), ("wms", _wms)]:
        try:
            fetch()
        except FetchError as exc:
            record_gap(conn, edition, feed_name,
                       "feed unavailable after {0} attempts; items missing this week ({1})".format(
                           exc.attempts, exc.cause))


ASSENT_FRESH_DAYS = 14


def assent_topline(client, wl, closure_row, week_start=None):
    """Royal Assent trigger (handoff section 8): when a watched Act closes,
    verify its tracked sections on legislation.gov.uk and report in-force
    status in that closing edition. Runs once ever, because closures do.

    Suppressed when the assent is stale (older than ASSENT_FRESH_DAYS before
    the edition): cold-start catch-up closures are not news to readers who
    lived through them. Ongoing implementation surfaces via the SI sweeps.
    """
    act = next((a for a in (wl.acts_raw or [])
                if int(a.get("bill_id") or 0) == closure_row.bill_id), None)
    if not act or not act.get("chapter") or not act.get("sections"):
        return None
    if week_start is not None:
        import re as _re
        m = _re.search(r"(\d{4}-\d{2}-\d{2})", closure_row.closed_note or "")
        if m:
            assent = datetime.date.fromisoformat(m.group(1))
            if (week_start - assent).days > ASSENT_FRESH_DAYS:
                return None  # catch-up closure; assent is old news
    statuses = []
    for n in act["sections"]:
        status = legislation.fetch_section_status(client, act["chapter"], n)
        statuses.append("s.{0} {1}".format(n, status.note))
    return digest.Line(
        "{0} Act: {1} (verified on legislation.gov.uk at Royal Assent).".format(
            act.get("short"), "; ".join(statuses)), "NOTE")


SECTION_FOR_FEED = {
    "consultation": "consultations_si", "si": "consultations_si",
    "whatson": "week_ahead", "division": "votes", "wms": "statements",
    "pq": "pqs", "edm": "edms", "committee": "committee",
}


def sections_from_store(conn, edition):
    """Build edition sections by querying reviewed items (digest as byproduct)."""
    rows = conn.execute(
        "SELECT id, source_feed, title, url, event_date, deadline, priority_tag, owner, why_it_matters "
        "FROM items WHERE priority_tag IS NOT NULL ORDER BY source_feed, event_date, id"
    ).fetchall()
    for r in rows:
        target = SECTION_FOR_FEED.get(r["source_feed"])
        if not target:
            continue
        line = digest.Line(
            text=r["why_it_matters"] or r["title"],
            tag=r["priority_tag"], owner=r["owner"], url=r["url"],
            deadline=r["deadline"], date=r["event_date"],
        )
        getattr(edition, target).append(line)
    return edition


def queue_path(week_commencing):
    return os.path.join(ROOT, "reviews", "triage-queue-{0}.md".format(week_commencing))


def run_triage_pass(conn, wl, week_commencing, mode=None):
    """Score pending items per the TRIAGE mode. Returns a status string.

    stub    -- deterministic scores immediately (tier-1/watchlist 2, tier-2 1)
    session -- emit a queue file for a Claude Code session (or human) to score;
               scores are applied at render time
    live    -- Claude API scoring (needs ANTHROPIC_API_KEY)
    """
    mode = mode or os.environ.get("TRIAGE", "stub")
    items = triage.pending_items(conn, wl)
    if not items:
        return "no pending items"
    if mode == "session":
        path, count = triage.generate_queue_file(conn, wl, week_commencing, queue_path(week_commencing))
        return "queue file for session scoring: {0} ({1} items)".format(path, count)
    results = triage.triage(items, mode=mode)
    scored, discards = triage.apply_scores(conn, items, results)
    review.log_discards(conn, week_commencing,
                        [(i, t, None) for i, t in discards])
    return "{0} items scored ({1}), {2} discarded".format(scored, mode, len(discards))


def apply_queue_if_scored(conn, wl, week_commencing):
    """Render-time: apply a session-scored queue file if one exists."""
    path = queue_path(week_commencing)
    if not os.path.exists(path):
        return None
    results = triage.parse_queue_file(path)
    if not results:
        return None
    items = triage.pending_items(conn, wl)
    scored, discards = triage.apply_scores(conn, items, results)
    review.log_discards(conn, week_commencing, [(i, t, None) for i, t in discards])
    return "{0} queue scores applied, {1} discarded".format(scored, len(discards))


def pull(week_commencing, db_name):
    """Phase 1: ingest, filter, triage pass, store; emit the review checklist."""
    week_start = datetime.date.fromisoformat(week_commencing)
    week_end = week_start + datetime.timedelta(days=6)
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", db_name)))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))  # archives under today's date
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    # Re-pull idempotency: this edition's gap rows are rewritten by this run.
    conn.execute("DELETE FROM gaps WHERE edition = ?", (week_commencing,))
    conn.commit()

    ingest_all(client, conn, tax, wl, week_start, week_end)
    triage_status = run_triage_pass(conn, wl, week_commencing)

    path = os.path.join(ROOT, "reviews", "review-{0}.md".format(week_commencing))
    path, count = review.generate_review_file(conn, week_commencing, path)
    conn.close()
    return path, count, triage_status


def render_edition(week_commencing, db_name, draft=False):
    """Phase 2: apply review edits (or draft defaults), render from the store."""
    week_start = datetime.date.fromisoformat(week_commencing)
    week_end = week_start + datetime.timedelta(days=6)
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", db_name)))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))  # archives under today's date

    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    apply_queue_if_scored(conn, wl, week_commencing)  # session-scored triage, if present

    review_path = os.path.join(ROOT, "reviews", "review-{0}.md".format(week_commencing))
    if draft:
        review.apply_draft_defaults(conn)
    elif os.path.exists(review_path):
        review.apply_review(conn, review.parse_review_file(review_path))

    week_events = whatson.fetch_events(client, week_start, week_end)
    mode = "recess" if whatson.is_recess(week_events) else "normal"
    edition = digest.Edition(week_commencing=week_commencing, number=1, mode=mode)

    # Bills closed in OTHER editions are suppressed; bills closed in THIS
    # edition still render here (re-rendering must not lose closing entries).
    already_closed = board.load_closed_bill_ids(conn, exclude_edition=week_commencing)
    edition.board_rows, closures = build_board_rows(client, week_start, already_closed, wl)
    hr_rows, hr_closures = holyrood_rows(client, wl)
    edition.board_rows.extend(r for r in hr_rows if r.bill_id not in already_closed)
    closures = closures + [r for r in hr_closures if r.bill_id not in already_closed]

    for row in closures:
        board.record_closure(conn, row, week_commencing)

    # Movement markers: diff live rows against last edition's stored snapshots
    # and persist this edition's (idempotent within an edition).
    board.apply_snapshots(conn, edition.board_rows, week_commencing)

    sections_from_store(conn, edition)

    # Royal Assent trigger: in-force verification renders only in the edition
    # that carries the Act's closing entry, never again.
    for row in closures:
        if "legislation_check" in (row.triggers or []):
            line = assent_topline(client, wl, row, week_start)
            if line:
                edition.top_lines.append(line)

    # Footer reports what actually happened: gap rows written during the pull
    # (a sweep term that failed after retries, etc.), nothing hardcoded.
    edition.gaps = [(r["feed"], r["detail"]) for r in conn.execute(
        "SELECT feed, detail FROM gaps WHERE edition = ? ORDER BY feed, detail",
        (week_commencing,)).fetchall()]
    if mode == "recess":
        # Return dates from What's On over the following six weeks (handoff 4.7).
        lookahead = whatson.fetch_events(client, week_end + datetime.timedelta(days=1),
                                         week_end + datetime.timedelta(days=42))
        edition.return_dates = {h: d.isoformat() for h, d in whatson.return_dates(lookahead).items()}
        edition.top_lines.insert(0, digest.Line(digest.recess_line(edition.return_dates), "NOTE"))

    path = digest.write_edition(conn, edition, os.path.join(ROOT, "editions"),
                                generated_at=datetime.datetime.now().isoformat(timespec="seconds"))
    conn.close()
    return path


def _db_name(week):
    """One continuous store across all editions (handoff section 5).

    Week-on-week features (movement snapshots, the one-closing-entry guard,
    EDM signature deltas) all diff this edition against the last, which only
    works if every edition writes to the same database.
    """
    return "parl-monitor.db"


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    phase = "--draft"
    if argv and argv[0].startswith("--"):
        phase = argv.pop(0)
    week = argv[0] if argv else "2026-08-03"
    db_name = _db_name(week)

    if phase == "--pull":
        path, count, triage_status = pull(week, db_name)
        return "triage: {0}\nreview file: {1} ({2} items awaiting review)".format(triage_status, path, count)
    if phase == "--render":
        return "edition: {0}".format(render_edition(week, db_name, draft=False))
    if phase == "--draft":
        os.environ["TRIAGE"] = os.environ.get("TRIAGE") or "stub"
        if os.environ["TRIAGE"] == "session":
            os.environ["TRIAGE"] = "stub"  # a draft cannot wait on a session
        pull(week, db_name)
        return "edition (draft): {0}".format(render_edition(week, db_name, draft=True))
    raise SystemExit("usage: run_weekly.py [--pull|--render|--draft] <YYYY-MM-DD>")


if __name__ == "__main__":
    print(main())
