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
import re
import sys
from concurrent import futures

import yaml

from src import (actionable, board, db, digest, filter as filt, intel, members, publish, review,
                 spend, stance, triage)
from src.http import FetchError, HttpClient
from src.ingest import (bills, committees, consultations, divisions, edms, hansard,
                        legislation, pqs, scotland, sis, whatson, wms)

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
               date_tabled=None, extra=None, mp_refs=None):
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
        "event_date, deadline, date_tabled, issue_areas, matched_terms, tier, triage_score, extra, mp_refs) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at, title=excluded.title, "
        "url=excluded.url, event_date=excluded.event_date, deadline=excluded.deadline, "
        "date_tabled=excluded.date_tabled, issue_areas=excluded.issue_areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, extra=excluded.extra, "
        "mp_refs=excluded.mp_refs",
        (item_id, datetime.date.today().isoformat(), feed, item_type, title, url, event_date, deadline,
         date_tabled,
         json.dumps(result.issue_areas), json.dumps(result.matched_terms + result.watchlist_hits),
         result.tier, json.dumps(extra) if extra else None,
         str(mp_refs) if mp_refs else None),
    )
    conn.commit()


def record_gap(conn, edition, feed, detail):
    conn.execute("INSERT INTO gaps (edition, feed, detail) VALUES (?, ?, ?)",
                 (edition, feed, detail))
    conn.commit()


def _pq_gap_detail(term, attempts):
    """The gaps row for a failed PQ term. One place, so resweep can match it."""
    return ("sweep term '{0}' failed after {1} attempts; results missing this "
            "week".format(term, attempts))


# Terms fetched at once in the PQ sweep. Written questions dominate the pull
# -- 39 terms at 30-50s each, one at a time, is most of it -- and until
# 2026-08-17 nothing in the pipeline fetched in parallel at all, so the
# HttpClient's per-host semaphore had never once been contended.
# Only the FETCH is parallel. Storing stays on the calling thread: the sqlite
# connection is not shared across threads, and member resolution writes to it.
# THREE, but do NOT read a speed claim into it. Full measurements, forced
# pulls on 2026-08-17, every one clean (zero gaps, the same 21 items):
#     sequential      17m54s
#     concurrency 3   12m13s   then 17m45s on a repeat
#     concurrency 6   16m47s
# The spread WITHIN one setting (12m13s to 17m45s) is larger than any gap
# between settings, so this run-to-run noise swamps the effect and none of
# these differences is real on this evidence. An earlier commit here claimed
# "32% off" from the 12m13s figure alone; that was one sample and it did not
# reproduce. Parallel fetching is kept because three clean runs show it costs
# nothing and the mechanism is sound on a slow I/O-bound API -- not because it
# has been shown to help. The cold Sunday run is the first honest test.
# HttpClient's per-host semaphore is wired to this number below; leaving it at
# its own default of 4 silently capped a 6-worker pool at 4.
PQ_SWEEP_CONCURRENCY = 3


def _fetch_terms(client, terms, workers=PQ_SWEEP_CONCURRENCY):
    """{term: questions | FetchError}, fetched `workers` at a time.

    Exceptions are returned rather than raised so the caller decides, in
    deterministic term order, what is a gap -- otherwise which term failed
    would depend on which thread finished first.
    """
    out = {}
    if workers <= 1 or len(terms) <= 1:
        for term in terms:
            try:
                out[term] = pqs.fetch_questions(client, term)
            except FetchError as exc:
                out[term] = exc
        return out
    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        submitted = {pool.submit(pqs.fetch_questions, client, term): term
                     for term in terms}
        for future in futures.as_completed(submitted):
            term = submitted[future]
            try:
                out[term] = future.result()
            except FetchError as exc:
                out[term] = exc
    return out


def sweep_pqs(client, conn, tax, wl, week_start, edition, terms):
    """Weekly written-questions sweep (handoff 4.2, 3).

    The API is slow and flaky; a term that fails after retries is logged to
    gaps and disclosed in the footer, never silently dropped. Results are
    filtered client-side on dateAnswered (never answeredWhenFrom) and then
    through the taxonomy: Parliament's search relevance is loose.

    Returns the terms that failed, for resweep_pq_gaps to try again later.
    """
    since = week_start - datetime.timedelta(days=7)
    failed = []
    fetched = _fetch_terms(client, terms)
    for term in terms:                     # deterministic, whatever finished first
        outcome = fetched.get(term)
        if isinstance(outcome, FetchError):
            record_gap(conn, edition, "pq", _pq_gap_detail(term, outcome.attempts))
            failed.append(term)
            continue
        _store_pq_questions(client, conn, tax, wl, since, edition, outcome or [])
    return failed


def resweep_pq_gaps(client, conn, tax, wl, week_start, edition, terms):
    """One more attempt at the terms that gapped, at the END of the pull.

    Written Questions failures cluster on a term for a window of minutes
    rather than for good: "border-security" failed four times in ten minutes
    and answered three times in the next ten (2026-08-17). Retrying inside
    the sweep cannot exploit that -- the attempts are seconds apart -- so this
    runs after every other feed, which puts twenty-odd minutes between the
    two tries without adding a single second of waiting.

    Costs nothing on a clean week: no gaps, no calls. On a bad one it costs
    one call per gapped term. A rescued term has its gaps row deleted, so the
    edition footer stops disclosing a gap that no longer exists.
    """
    if not terms:
        return 0
    since = week_start - datetime.timedelta(days=7)
    rescued = 0
    for term in terms:
        try:
            questions = pqs.fetch_questions(client, term)
        except FetchError:
            continue          # the gaps row stands; the footer discloses it
        _store_pq_questions(client, conn, tax, wl, since, edition, questions)
        conn.execute("DELETE FROM gaps WHERE edition = ? AND feed = 'pq' "
                     "AND detail LIKE ?", (edition, "sweep term '%s' failed%%" % term))
        conn.commit()
        rescued += 1
    return rescued


def _store_pq_questions(client, conn, tax, wl, since, edition, questions):
    """Filter a term's questions through the taxonomy and store what survives."""
    for q in pqs.since(questions, since):
        # EVERY result in the window is fetched in full BEFORE the filter
        # runs (Christopher, 2026-09-06: "Make the change"). The search
        # payload carries ~255 characters of the question and no answer,
        # so filtering on it first meant a question whose only matching
        # phrase sat past the cut -- or in the minister's answer -- was
        # never seen at all. About 240 calls a week at 0.2s each, under a
        # minute, free; and every reader of a stored row (5CA quotes, the
        # roll, the stance judge, a retag) now reads the text the filter
        # actually matched. A failed detail fetch falls back to the stub,
        # so a flaky API narrows recall for a week rather than losing rows.
        q = pqs.complete(client, q, log=print)
        r = filt.filter_item(tax, wl, q.heading or "", q.question_text or "", q.answer_text or "")
        if not r.matched():
            continue
        title = "PQ {0} ({1}): {2}, answered {3}".format(
            q.uin, q.house, q.heading, q.date_answered)
        # The asker and the department are what make a question readable:
        # resolve the member now so the edition can name them (the store
        # kept neither, which is why lines used to be anonymous).
        asker = None
        if q.asking_member_id:
            try:
                asker = members.resolve(conn, client, q.asking_member_id)
            except Exception:
                asker = None
        extra = {
            "heading": q.heading,
            "uin": q.uin,
            "house": q.house,
            "department": q.answering_body,
            "member": asker.name if asker else None,
            "party": asker.party if asker else None,
            "seat": asker.seat if asker else None,
            "question_text": (q.question_text or "")[:600],
        }
        store_item(conn, "pq:{0}".format(q.id), "pq", "question", title, q.url, r,
                   event_date=q.date_answered.isoformat() if q.date_answered else None,
                   date_tabled=q.date_tabled.isoformat() if q.date_tabled else None,
                   extra=extra, mp_refs=q.asking_member_id)
        if q.asking_member_id and (r.tier == 1 or r.watchlist_hits):
            try:
                members.resolve(conn, client, q.asking_member_id)
            except Exception:
                pass  # resolution is best-effort; ledger row still lands
            intel.record_event(conn, q.asking_member_id,
                               q.date_answered.isoformat() if q.date_answered else edition,
                               "pq", "pq:{0}".format(q.id),
                               intel.annotated_line(q.heading, r.matched_terms + r.watchlist_hits),
                               areas=r.issue_areas)


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
            if e.date_tabled and (r.tier == 1 or r.watchlist_hits):
                if e.member_id:
                    try:
                        members.resolve(conn, client, e.member_id)
                    except Exception:
                        pass  # resolution is best-effort
                    intel.record_event(conn, e.member_id, e.date_tabled.isoformat(),
                                       "edm", "edm:{0}".format(e.id),
                                       intel.annotated_line("Sponsored EDM: {0}".format(e.title),
                                                            r.matched_terms + r.watchlist_hits),
                                       areas=r.issue_areas)
                # Every live co-signature is a cheap, unambiguous endorsement --
                # exactly the stance signal 5CA placement needs. Ledgered for
                # profiles; never listed in the weekly section (same rule as votes).
                try:
                    sponsors = edms.fetch_sponsors(client, e.id)
                except Exception:
                    sponsors = []  # best-effort enrichment; sponsor event already landed
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
    pq_failed = sweep_pqs(client, conn, tax, wl, week_start, edition,
                          settings.get("pq_sweep_terms") or [])
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
            detail = sis.fetch_si_detail(client, si.id)  # text link + enabling Act
            approved = None
            division = None
            if div51 and divisions.matches_watchlist(div51.title, [e[0] for e in wl.act_shorts]):
                approved = div51.date.isoformat() if div51.date else None
                division = {"result": "{0} to {1}".format(div51.aye_count, div51.no_count),
                            "date": approved, "url": div51.url}
            extra = {
                "procedure": si.procedure,
                "act": ", ".join(detail.enabling_acts or []),
                "laid": si.laid_date.isoformat() if si.laid_date else None,
                "made": si.paper_made_date.isoformat() if si.paper_made_date else None,
                "division": division,
                "text_link": detail.text_link,
                "status": sis.status_line(si.procedure,
                                          si.laid_date.isoformat() if si.laid_date else None,
                                          approved,
                                          si.paper_made_date.isoformat() if si.paper_made_date else None),
            }
            store_item(conn, "si:" + str(si.id), "si", "si", si.name, detail.tracker_url, r,
                       event_date=si.laid_date.isoformat() if si.laid_date else None,
                       extra=extra)

    def _whatson():
        # Two horizons: the edition week (Week ahead) and the EIGHT weeks
        # after it (Further afield). Three weeks (Christopher, 2026-08-24)
        # became eight on 2026-09-01: Caroline asked for a one-to-two-month
        # forward look so a campaign can be built in time, and the EU
        # monitor already sees 60 days -- both monitors now look as far as
        # their sources publish. What's On simply returns nothing for weeks
        # Parliament has not yet scheduled, so the far end costs only a few
        # extra chunked calls.
        for horizon, (h_start, h_end) in (
                ("week", (week_start, week_end)),
                ("further", (week_end + datetime.timedelta(days=1),
                             week_end + datetime.timedelta(days=56)))):
            for e in whatson.fetch_events(client, h_start, h_end):
                text = whatson.event_text(e)
                r = filt.filter_item(tax, wl, text)
                if not r.matched():
                    continue
                label = whatson.event_label(e)
                event_date = e.start_date.isoformat() if e.start_date else None
                store_item(conn,
                           "whatson:{0}:{1}".format(event_date,
                                                    abs(hash(label)) % 10 ** 8),
                           "whatson", "event", label, None, r,
                           event_date=event_date,
                           extra={"horizon": horizon})

    def _divisions():
        # A Monday 06:30 edition REPORTS the week just ended and PREVIEWS the
        # week starting. Divisions were fetched for the edition week itself,
        # which on publication morning has not happened -- so the Votes
        # section could never populate in a sitting week. Found by the
        # 2026-08-24 rehearsal, one week before the first sitting edition.
        report_start = week_start - datetime.timedelta(days=7)
        report_end = week_start - datetime.timedelta(days=1)
        found = []
        day = report_start
        while day <= report_end:
            found.extend(("Commons", "c", divisions.fetch_commons_breakdown, dv)
                         for dv in divisions.fetch_commons_divisions(client, day.isoformat()))
            day += datetime.timedelta(days=1)
        found.extend(("Lords", "l", divisions.fetch_lords_breakdown, dv) for dv in
                     divisions.fetch_lords_divisions(client, report_start.isoformat(),
                                                     report_end.isoformat()))
        for house, prefix, breakdown, dv in found:
            r = filt.filter_item(tax, wl, dv.title or "")
            if not r.matched():
                continue
            title = " ".join((dv.title or "").split())  # source carries double spaces
            store_item(conn, "division:{0}".format(dv.id), "division", "division",
                       "Division #{0} ({1}-{2}): {3}".format(dv.number, dv.aye_count, dv.no_count, title),
                       dv.url, r, event_date=dv.date.isoformat() if dv.date else None)
            # Member-level breakdown -> ledger (profiles, timelines, 5CA).
            # Precision-gated like every other ledger path; never listed in
            # the weekly section, only counted (Christopher's flooding rule).
            if not (r.tier == 1 or r.watchlist_hits) or not dv.date:
                continue
            try:
                division, voters = breakdown(client, dv.id)
            except Exception as exc:
                record_gap(conn, edition, "division",
                           "division {0} breakdown unavailable: {1}".format(dv.id, exc))
                continue
            division.house = house
            intel.record_votes(conn, division, voters, prefix, r.issue_areas)

    def _hansard():
        """Spoken contributions -> ledger. The MP section's standing subtitle
        promises debates, so this is what makes good on it each week."""
        for term in (settings.get("pq_sweep_terms") or []):
            try:
                # The list is hyphenated for the Written Questions API's
                # benefit; Hansard wants the spoken form (hansard.spoken_form).
                speeches = hansard.search_contributions(
                    client, hansard.spoken_form(term),
                    week_start.isoformat(), week_end.isoformat())
            except FetchError as exc:
                record_gap(conn, edition, "hansard",
                           "term '{0}' failed after {1} attempts".format(term, exc.attempts))
                continue
            for s in speeches:
                if not (s.member_id and s.date):
                    continue
                # Passage-level: a long speech is tagged with the areas its
                # passages actually support, and the strongest passage becomes
                # the excerpt the 5CA Comments column quotes.
                matches = filt.match_passages(tax, wl, s.text or "",
                                              title=s.debate_title or "")
                if not matches:
                    continue
                areas, terms, excerpt = filt.aggregate_passages(matches)
                try:
                    members.resolve(conn, client, s.member_id)
                except Exception:
                    pass  # resolution is best-effort; the ledger row still lands
                intel.record_event(
                    conn, s.member_id, s.date.isoformat(), "debate",
                    "hansard:{0}".format(s.ext_id),
                    intel.annotated_line("Spoke: {0}".format(s.debate_title), terms),
                    areas=areas, excerpt=excerpt)

    def _wms():
        report_start = week_start - datetime.timedelta(days=7)
        report_end = week_start - datetime.timedelta(days=1)
        for st in wms.fetch_statements(client, report_start.isoformat(), take=80):
            # made_when is a date, not a string -- compare dates.
            if not (st.made_when and report_start <= st.made_when <= report_end):
                continue
            r = filt.filter_item(tax, wl, st.title or "", st.text or "")
            if r.matched():
                store_item(conn, "wms:{0}".format(st.id), "wms", "statement",
                           "WMS ({0}): {1}".format(st.house, st.title), None, r,
                           event_date=st.made_when.isoformat())

    def _committees():
        for call in committees.fetch_open_calls(client):
            r = filt.filter_item(tax, wl, call.title or "")
            if not r.matched():
                continue
            names = committees.resolve_committees(client, call.id)
            label = "{0}: {1} ({2}), evidence closes {3}".format(
                ", ".join(names) or "Committee", call.title, call.type_name,
                call.deadline.isoformat() if call.deadline else "rolling")
            store_item(conn, "committee:{0}".format(call.id), "committee", "inquiry",
                       label, call.url, r,
                       deadline=call.deadline.isoformat() if call.deadline else None)

    # One failing feed degrades to a disclosed gap; the pull continues.
    for feed_name, fetch in [("consultation", _consultations), ("si", _sis),
                             ("whatson", _whatson), ("division", _divisions), ("wms", _wms),
                             ("committee", _committees), ("hansard", _hansard)]:
        try:
            fetch()
        except FetchError as exc:
            record_gap(conn, edition, feed_name,
                       "feed unavailable after {0} attempts; items missing this week ({1})".format(
                           exc.attempts, exc.cause))

    # Last thing in the pull, deliberately: every feed above has now put
    # twenty-odd minutes between the failed attempt and this one, which is
    # the only separation observed to rescue a windowed Written Questions
    # failure. No gaps -> no calls.
    if pq_failed:
        rescued = resweep_pq_gaps(client, conn, tax, wl, week_start, edition, pq_failed)
        print("pq resweep: {0} of {1} gapped term(s) recovered ({2})".format(
            rescued, len(pq_failed), ", ".join(pq_failed)))


ASSENT_FRESH_DAYS = 14
CLOSURE_FRESH_DAYS = 28  # settings.yaml closure_fresh_days overrides


def split_stale_closures(closures, week_start, fresh_days=CLOSURE_FRESH_DAYS):
    """(fresh, stale) closing rows by terminal-event date.

    A closing entry is news when the bill fell or gained assent recently; a
    cold-start or backfill catch-up months later is not -- it is recorded in
    bills_board (the once-ever guard) but never rendered. Rows with no
    parseable terminal date count as fresh: better an odd obituary than a
    silent disappearance.
    """
    cutoff = (week_start - datetime.timedelta(days=fresh_days)).isoformat()
    fresh, stale = [], []
    for row in closures:
        closed = row.closed_date
        if not closed:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", row.closed_note or "")
            closed = m.group(1) if m else None
        (stale if (closed and closed < cutoff) else fresh).append(row)
    return fresh, stale


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
    "whatson": "week_ahead", "division": "votes", "wms": "statements",
    "edm": "edms",
}



def devolved_from_store(conn, week_commencing, days=30, hidden=(11,)):
    """The Devolved section's payload, READ from the watching-brief tables.

    Nothing here writes: sp_*/sd_*/ni_*/dg_* remain unable to reach items or
    mp_events, which is the separation guarantee. Only three things earn a
    place -- an open consultation (actionable), a bill at a live stage, and a
    vote in the recent window. Everything else stays in the monitors.
    """
    def shown(raw):
        return [a for a in json.loads(raw or "[]") if a not in hidden]

    since = (datetime.date.fromisoformat(week_commencing)
             - datetime.timedelta(days=days)).isoformat()
    live_since = (datetime.date.fromisoformat(week_commencing)
                  - datetime.timedelta(days=365)).isoformat()
    nation_label = {"scotland": "Scotland", "wales": "Wales", "ni": "N. Ireland"}
    out = {"consultations": [], "bills": [], "divisions": []}

    # Which of these rows the action-window rule promotes (spec
    # docs/parl-monitor-devolved-fix.md): those are briefed and appear in
    # Top lines; the remainder stay a watching brief. The table says which
    # is which, and flags late detection -- first seen under 21 days from
    # the deadline -- so that failure mode is visible, not silent.
    try:
        promoted = {c["key"]: c for c in
                    actionable.devolved_actionable(conn, week_commencing)}
    except Exception:                                   # noqa: BLE001
        promoted = {}
    try:
        rows = conn.execute(
            "SELECT key, nation, title, url, closes, areas, first_seen "
            "FROM dg_consultations "
            "WHERE (closes IS NULL OR closes >= ?) ORDER BY "
            "COALESCE(closes, '9999')", (week_commencing,)).fetchall()
    except Exception:                                   # noqa: BLE001
        rows = []
    for r in rows:
        if not shown(r["areas"]):
            continue
        closes = r["closes"] or "no date published"
        if r["closes"]:
            left = (datetime.date.fromisoformat(r["closes"])
                    - datetime.date.fromisoformat(week_commencing)).days
            closes = "{0} ({1} days)".format(r["closes"], left)
        out["consultations"].append({
            "title": r["title"], "url": r["url"], "closes": closes,
            "nation": nation_label.get(r["nation"], r["nation"]),
            "actionable": r["key"] in promoted,
            "late": actionable.late_detection(r["first_seen"], r["closes"])})

    for table, where, sql in (
            ("sp_bills", "Holyrood",
             "SELECT name AS title, latest_stage AS stage, "
             "latest_stage_date AS dated, areas FROM sp_bills"),
            ("sd_bills", "Senedd",
             "SELECT title, latest_stage AS stage, stage_date AS dated, "
             "areas FROM sd_bills")):
        try:
            rows = conn.execute(sql).fetchall()
        except Exception:                               # noqa: BLE001
            continue
        for r in rows:
            # A stage NAME is not liveness: sp_bills still carries "Stage 3"
            # for bills that passed in 2011 and 2014. Only a bill whose
            # latest stage MOVED inside the last year is current business.
            if not shown(r["areas"]) or not (r["stage"] or "").startswith(
                    ("Stage", "Introduced")):
                continue
            if not r["dated"] or r["dated"] < live_since:
                continue
            out["bills"].append({"title": r["title"], "where": where,
                                 "stage": r["stage"], "date": r["dated"]})

    for sql, where in (
            ("SELECT dated, title, result, areas, tier FROM sp_divisions "
             "WHERE source='votesmotion' AND dated >= ?", "Holyrood"),
            ("SELECT dated, title, result, areas, 1 AS tier FROM sd_divisions "
             "WHERE dated >= ?", "Senedd")):
        try:
            rows = conn.execute(sql, (since,)).fetchall()
        except Exception:                               # noqa: BLE001
            continue
        for r in rows:
            if not shown(r["areas"]) or r["tier"] != 1:
                continue
            out["divisions"].append({
                "dated": r["dated"],
                "title": "{0}: {1}".format(where, (r["title"] or "")[:70]),
                "result": (r["result"] or "?")[:40]})
    out["divisions"].sort(key=lambda v: v["dated"], reverse=True)
    out["divisions"] = out["divisions"][:6]
    return out


def sections_from_store(conn, edition):
    """Build edition sections by querying reviewed items (digest as byproduct)."""
    rows = conn.execute(
        "SELECT id, source_feed, title, url, event_date, deadline, triage_score, "
        "why_it_matters, extra, issue_areas "
        "FROM items WHERE triage_score >= 2 ORDER BY source_feed, event_date, id"
    ).fetchall()
    # Background-scored questions (triage 1) never reach the review file and so
    # carry no tag. They are real captures all the same, so the companion page
    # lists them: with questions dropped from the MP section, this is the only
    # place they would otherwise be invisible.
    background = conn.execute(
        "SELECT id, title, url, event_date, extra, issue_areas FROM items "
        "WHERE source_feed = 'pq' AND priority_tag IS NULL AND triage_score = 1 "
        "ORDER BY event_date, id").fetchall()
    area_labels = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    edition.companion_url = (load_settings().get("partner_site_url") or "").rstrip("/")
    edition.companion_url = (edition.companion_url + "/questions.html"
                             if edition.companion_url else None)
    # Dated sections render ONLY within a window before this edition's
    # Monday (Christopher, 2026-08-23): without one, every scored item
    # re-rendered in every edition forever -- the 17 Aug edition showed PQ
    # answers from 28 July. Windows are [Monday-N, Monday), so a
    # Monday-morning event rolls to the next edition instead of showing
    # twice, and a dateless row cannot prove it is fresh so it never
    # renders. Questions and statements get the week; EDMs get 60 days
    # (they gather signatures over weeks, so they stay on the monitor
    # longer -- Christopher, same day). Everything stays in the store and
    # the ledger regardless.
    week_start = datetime.date.fromisoformat(edition.week_commencing)
    week_end_iso = (week_start + datetime.timedelta(days=6)).isoformat()
    window_days = {"pq": 7, "wms": 7, "edm": 60}

    def in_window(feed, event_date):
        days = window_days.get(feed)
        if days is None:
            return True
        floor = (week_start - datetime.timedelta(days=days)).isoformat()
        return bool(event_date) and floor <= event_date < week_start.isoformat()

    for r in rows:
        feed = r["source_feed"]
        if not in_window(feed, r["event_date"]):
            continue
        if feed == "pq":
            extra = json.loads(r["extra"]) if r["extra"] else {}
            areas = json.loads(r["issue_areas"] or "[]")
            edition.pq_rows.append({
                "member": extra.get("member"), "party": extra.get("party"),
                "seat": extra.get("seat"), "house": extra.get("house"),
                "heading": extra.get("heading") or r["title"],
                "department": extra.get("department"), "url": r["url"],
                "date": r["event_date"], "tag": r["triage_score"],
                "why": r["why_it_matters"] or "",
                "area": areas[0] if areas else None,
                "area_label": area_labels.get(areas[0]) if areas else "Other",
            })
            continue
        if feed in ("consultation", "committee"):
            title = r["title"]
            if feed == "consultation" and title.startswith("Consultation: "):
                title = title[len("Consultation: "):]
            why = r["why_it_matters"] or ""
            if feed == "committee":
                # Stored label: "{committees}: {title} ({type}), evidence closes {date}"
                m = re.match(r"^(?P<cmte>[^:]+): (?P<rest>.+) \((?P<kind>[^)]+)\), evidence closes .+$", title)
                if m:
                    title = m.group("rest")
                    why = (m.group("cmte") + ("; " + why if why else "")).strip()
            edition.deadlines.append({
                "type": "Consultation" if feed == "consultation" else "Evidence",
                "title": title, "url": r["url"], "why": why, "deadline": r["deadline"],
            })
            # The deadline table carries no tag or owner, so an ACT decided at
            # review was rendering as an ordinary row: urgency the edition (and
            # the Slack summary, which reads the [ACT] bullets) never showed.
            # ACT deadline items therefore also emit a top line.
            if r["triage_score"] == 3:
                edition.top_lines.append(digest.Line(
                    text="{0} - {1}".format(title, r["why_it_matters"] or why),
                    tag=3, owner=None, url=r["url"],
                    deadline=r["deadline"], date=r["event_date"]))
            continue
        if feed == "si":
            extra = json.loads(r["extra"]) if r["extra"] else {}
            edition.si_rows.append({
                "name": r["title"], "url": r["url"], "why": r["why_it_matters"] or "",
                "procedure": extra.get("procedure"), "act": extra.get("act"),
                "status": extra.get("status"), "division": extra.get("division"),
                "text_link": extra.get("text_link"),
            })
            continue
        target = SECTION_FOR_FEED.get(feed)
        if not target:
            continue
        if feed == "whatson" and (r["event_date"] or "") > week_end_iso:
            target = "further_ahead"
        line = digest.Line(
            text=r["why_it_matters"] or r["title"],
            tag=r["triage_score"], owner=None, url=r["url"],
            deadline=r["deadline"], date=r["event_date"],
        )
        getattr(edition, target).append(line)

    edition.devolved = devolved_from_store(
        conn, edition.week_commencing)

    # Across the parliaments: prebuilt markdown over every store the
    # system holds (Westminster, three devolved, the EU's instruments).
    from src import across as _across
    from src import intel as _intel
    edition.across = _across.render(
        _across.collect(conn, edition.week_commencing),
        _intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml")))

    # Actionable devolved items reach Top lines, not only the canvas table
    # below the fold (docs/parl-monitor-devolved-fix.md: the RE consultation
    # WAS in Edition 5's canvas, in a section whose subheading told the
    # reader it asked nothing of them). Score-3 Westminster deadline items
    # already emit top lines above; these are their devolved equals.
    for c in actionable.devolved_actionable(conn, edition.week_commencing):
        edition.top_lines.append(digest.Line(
            text="{0} ({1}) - open consultation on our ground{2}".format(
                c["title"], c["nation_label"],
                "; surfaced late, deadline close" if c["late_detection"] else ""),
            tag=3, owner=None, url=c["url"],
            deadline=c["closes"], date=None))
    # The late-detection counter for the footer: every consultation the
    # Devolved table shows this week that was first seen under 21 days
    # before its deadline, actionable or just-closed alike.
    edition.late_detections = sum(
        1 for c in (edition.devolved or {}).get("consultations", [])
        if c.get("late"))

    for r in background:
        extra = json.loads(r["extra"]) if r["extra"] else {}
        areas = json.loads(r["issue_areas"] or "[]")
        if not areas:
            continue
        edition.pq_background.append({
            "member": extra.get("member"), "party": extra.get("party"),
            "seat": extra.get("seat"), "house": extra.get("house"),
            "heading": extra.get("heading") or r["title"],
            "department": extra.get("department"), "url": r["url"],
            "date": r["event_date"], "tag": None, "why": "",
            "question_text": extra.get("question_text"),
            "area": areas[0], "area_label": area_labels.get(areas[0]) or "Other",
        })
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
    mode = mode or os.environ.get("TRIAGE", "auto")
    if mode == "auto":
        # Unattended default: live scoring when a key is configured, else the
        # deterministic stub (a queue file would block an unattended Monday).
        from src import publish
        key = publish.load_secrets().get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if key:
            os.environ.setdefault("ANTHROPIC_API_KEY", key)
            mode = "live"
        else:
            mode = "stub"
    items = triage.pending_items(conn, wl)
    if not items:
        return "no pending items"
    if mode == "session":
        path, count = triage.generate_queue_file(conn, wl, week_commencing, queue_path(week_commencing))
        return "queue file for session scoring: {0} ({1} items)".format(path, count)
    if mode == "live":
        # A capped or exhausted API must not cost us the whole pull: fall back
        # to the deterministic stub and disclose it. Everything downstream is
        # built to work on stub scores (CLAUDE.md).
        def _spend(usage, model):
            spend.record(conn, "triage", model, usage)

        try:
            results = triage.triage(items, mode="live", usage_sink=_spend)
        except Exception as exc:
            record_gap(conn, week_commencing, "triage",
                       "live scoring failed ({0}); deterministic stub scores "
                       "used instead, so this edition needs a human review "
                       "pass".format(str(exc)[:160]))
            print("triage: live failed ({0}); falling back to stub".format(exc))
            mode = "stub"
            results = triage.score_stub(items)
    else:
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


def run_stance_pass(conn, week_commencing):
    """Place this week's new ledger evidence on the 5CA gradient.

    Unattended by necessity (Christopher, 2026-08-05: session scoring needs a
    human, so the API it is). Cost tracks refs, not volume: a 600-voter
    division is two refs, one per direction. A sitting week is typically
    3-5 batches, pennies; settings.stance_weekly_max_refs caps a freak week
    and the remainder is disclosed, never dropped, then scored next run.
    """
    if os.environ.get("NO_STANCE") == "1":
        return "skipped: NO_STANCE=1 (rehearsal -- scoring spends money)"
    key = (publish.load_secrets().get("anthropic_api_key")
           or os.environ.get("ANTHROPIC_API_KEY"))
    if not key:
        return "skipped: no anthropic_api_key (5CA sheets keep their existing scores)"
    settings = load_settings()
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    messages = []
    stats = stance.score_pending(
        conn, os.path.join(ROOT, "data", "raw"), key,
        datetime.date.today().isoformat(),
        max_refs=settings.get("stance_weekly_max_refs") or 400,
        overrides_cfg=cfg, since_days=14,
        log=messages.append)
    for msg in messages:
        record_gap(conn, week_commencing, "stance", msg)
    if stats["deferred"]:
        record_gap(conn, week_commencing, "stance",
                   "{0} refs over the weekly cap; they score on the next run".format(
                       stats["deferred"]))
    return ("{scored} evidence refs placed, {failed_batches} batch(es) failed, "
            "{deferred} deferred, overrides on {overridden}".format(**stats))


def pull(week_commencing, db_name, force=False):
    """Phase 1: ingest, filter, triage pass, store; emit the review checklist.

    Idempotent per week, like the Monday publish: a completed pull writes a
    pull_log row (committed with the run's state), and a later run for the
    same week skips. This is what makes retry cron slots safe -- extras find
    the marker and exit, only a genuinely failed week gets re-pulled.
    """
    week_start = datetime.date.fromisoformat(week_commencing)
    week_end = week_start + datetime.timedelta(days=6)
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", db_name)))
    conn.execute("CREATE TABLE IF NOT EXISTS pull_log ("
                 "week TEXT PRIMARY KEY, completed_at TEXT)")
    done = conn.execute("SELECT completed_at FROM pull_log WHERE week = ?",
                        (week_commencing,)).fetchone()
    if done and not force:
        conn.close()
        return ("(already pulled for w/c {0} at {1}; use --force to re-pull)"
                .format(week_commencing, done["completed_at"]), 0,
                "skipped: already pulled")
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"),  # archives under today's date
                        host_concurrency=PQ_SWEEP_CONCURRENCY)
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    # Re-pull idempotency: this edition's gap rows are rewritten by this run.
    conn.execute("DELETE FROM gaps WHERE edition = ?", (week_commencing,))
    conn.commit()

    ingest_all(client, conn, tax, wl, week_start, week_end)
    triage_status = run_triage_pass(conn, wl, week_commencing)
    try:
        print("stance: " + run_stance_pass(conn, week_commencing))
    except Exception as exc:
        # The edition never depends on stance scores; a failure here is a
        # disclosed gap, not a lost pull.
        record_gap(conn, week_commencing, "stance", "pass failed: {0}".format(exc))
        print("stance: failed ({0}); recorded as a gap".format(exc))

    # The editorial loop is retired (Christopher, 2026-08-21): no review file
    # is written and nothing waits for one. Rendering is score-driven.
    path = "(editorial loop retired: no review file)"
    count = conn.execute("SELECT COUNT(*) FROM items WHERE triage_score >= 2 "
                         "AND first_seen_edition = ?", (week_commencing,)
                         ).fetchone()[0] if _has_col(conn, "items",
                                                     "first_seen_edition") \
        else conn.execute("SELECT COUNT(*) FROM items WHERE triage_score >= 2"
                          ).fetchone()[0]
    conn.execute("INSERT OR REPLACE INTO pull_log (week, completed_at) VALUES (?, ?)",
                 (week_commencing, datetime.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return path, count, triage_status


def _has_col(conn, table, col):
    return col in [c[1] for c in conn.execute(
        "PRAGMA table_info({0})".format(table))]


def render_edition(week_commencing, db_name, draft=False):
    """Phase 2: render from the store, score-driven (editorial loop retired)."""
    week_start = datetime.date.fromisoformat(week_commencing)
    week_end = week_start + datetime.timedelta(days=6)
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", db_name)))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"),  # archives under today's date
                        host_concurrency=PQ_SWEEP_CONCURRENCY)

    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    apply_queue_if_scored(conn, wl, week_commencing)  # session-scored triage, if present

    # Editorial loop retired: no review edits to apply; scores decide.

    week_events = whatson.fetch_events(client, week_start, week_end)
    mode = "recess" if whatson.is_recess(week_events) else "normal"
    number = 1 + conn.execute("SELECT COUNT(*) FROM editions WHERE "
                              "week_commencing < ?",
                              (week_commencing,)).fetchone()[0]
    edition = digest.Edition(week_commencing=week_commencing, number=number,
                             mode=mode)
    edition.taxonomy_version = filt.load_taxonomy(
        os.path.join(ROOT, "config", "taxonomy.yaml")).version

    # Bills closed in OTHER editions are suppressed; bills closed in THIS
    # edition still render here (re-rendering must not lose closing entries).
    already_closed = board.load_closed_bill_ids(conn, exclude_edition=week_commencing)
    edition.board_rows, closures = build_board_rows(client, week_start, already_closed, wl)
    hr_rows, hr_closures = holyrood_rows(client, wl)
    edition.board_rows.extend(r for r in hr_rows if r.bill_id not in already_closed)
    closures = closures + [r for r in hr_closures if r.bill_id not in already_closed]

    # Stale closures (terminal event older than the freshness window) are
    # recorded for the once-ever guard but never rendered.
    fresh_days = load_settings().get("closure_fresh_days") or CLOSURE_FRESH_DAYS
    fresh_closures, stale_closures = split_stale_closures(closures, week_start, fresh_days)
    for row in closures:
        board.record_closure(conn, row, week_commencing)
    if stale_closures:
        stale_ids = {r.bill_id for r in stale_closures}
        edition.board_rows = [r for r in edition.board_rows if r.bill_id not in stale_ids]

    # Movement markers: diff live rows against last edition's stored snapshots
    # and persist this edition's (idempotent within an edition).
    board.apply_snapshots(conn, edition.board_rows, week_commencing)

    sections_from_store(conn, edition)

    window_start = (week_start - datetime.timedelta(days=7)).isoformat()
    edition.mp_notes = digest.mp_lines_from_events(
        intel.events_for_week(conn, window_start, week_end.isoformat()))

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
    return os.environ.get("PARL_DB") or "parl-monitor.db"


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    phase = "--draft"
    if argv and argv[0].startswith("--"):
        phase = argv.pop(0)
    week = argv[0] if argv else "2026-08-03"
    db_name = _db_name(week)

    if phase == "--pull":
        path, count, triage_status = pull(week, db_name, force="--force" in argv)
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
