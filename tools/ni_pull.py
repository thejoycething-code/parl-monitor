"""Harvest the Northern Ireland Assembly into its own table.

    python3 tools/ni_pull.py                  # questions since 2024, motions, diary
    python3 tools/ni_pull.py --since 2008-01-01   # the full eighteen-year history
    python3 tools/ni_pull.py --days 120       # a longer forward diary

Writes to `ni_items`, NEVER to `items`. The published edition is built by
"SELECT ... FROM items", so keeping NI in a separate table is what guarantees
it cannot appear in the Slack digest -- see the schema comment in src/db.py.

Classification reuses the WESTMINSTER taxonomy plus the v0.5 NI vocabulary,
and sweeps `pq_sweep_terms` plus the NI-only `ni_sweep_terms`. What differs is the ground: an
NI question about abortion is asking about a law imposed from outside, so the
same term carries different weight. That judgement belongs to a human reading
the monitor, not to a score computed here.

Gaps are recorded rather than raised. A sweep of forty terms must not lose
thirty-nine because one timed out, and the run prints what it failed to fetch.

DO NOT RUN THIS ALONGSIDE tools/ni_divisions.py. Both write the same SQLite
file, and running them concurrently on 2026-08-18 cost the roster with
"database is locked" -- reported as a gap, which is how it was noticed, but
the roster is the join table everything else depends on. They are quick; run
them one after the other.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, ni_store
from src.http import HttpClient
from src.ingest import hansard, niassembly

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
    """pq_sweep_terms plus the NI-only ni_sweep_terms, ready for the search.

    THE HYPHEN BUG, measured 2026-08-18: the NI question search is a literal
    substring match, so a hyphenated term returns ZERO where its spoken form
    returns everything -- "puberty-blockers" 0 against "puberty blockers" 32,
    "assisted-dying" 0 against "assisted dying" 4. Every multi-word sweep term
    silently found nothing until this run; the 20 questions stored to that
    point had all come from single-word terms. hansard.spoken_form exists for
    exactly this shape (the same hyphens cost hits in Westminster Hansard),
    so it is reused rather than re-derived.
    """
    import yaml
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as fh:
        settings = yaml.safe_load(fh) or {}
    terms = list(settings.get("pq_sweep_terms") or [])
    terms += [t for t in (settings.get("ni_sweep_terms") or [])
              if t not in terms]
    # The endpoint rejects anything shorter than three characters, so filter
    # here rather than burning a request to be told.
    return [hansard.spoken_form(t) for t in terms
            if len(t) >= niassembly.MIN_SEARCH]


def store(conn, row, today):
    """Upsert one row, preserving first_seen. Same contract as un_store."""
    existing = conn.execute("SELECT first_seen FROM ni_items WHERE id = ?",
                            (row["id"],)).fetchone()
    first_seen = existing["first_seen"] if existing else today
    conn.execute(
        "INSERT OR REPLACE INTO ni_items (id, kind, reference, title, dated, "
        "tablers, parties, category, areas, matched_terms, url, "
        "tabler_person_id, tabler, tabler_seat, minister, department, "
        "answered, answer, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (row["id"], row["kind"], row.get("reference"), row.get("title"),
         row.get("dated"), row.get("tablers"),
         json.dumps(row.get("parties") or []), row.get("category"),
         json.dumps(row.get("areas") or []),
         json.dumps(row.get("matched_terms") or []),
         row.get("url"), row.get("tabler_person_id"), row.get("tabler"),
         row.get("tabler_seat"), row.get("minister"), row.get("department"),
         row.get("answered"), row.get("answer"), first_seen, today))
    return existing is None


def store_members(conn, members, today):
    for m in members:
        existing = conn.execute(
            "SELECT first_seen FROM ni_members WHERE person_id = ?",
            (m.person_id,)).fetchone()
        conn.execute(
            "INSERT OR REPLACE INTO ni_members (person_id, name, display_name, "
            "party, constituency, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
            (m.person_id, m.name, m.display_name, m.party, m.constituency,
             existing["first_seen"] if existing else today, today))


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

    # -- roster -------------------------------------------------------------
    # Fetched first: no question or division payload carries a party, only a
    # PersonId, so attribution is worthless without this join table.
    try:
        members = niassembly.fetch_members(client)
        store_members(conn, members, today.isoformat())
        print("{0} sitting MLAs stored.".format(len(members)))
    except Exception as exc:                        # noqa: BLE001
        gaps.append("member roster: {0}: {1}".format(type(exc).__name__, exc))

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
    matched = []
    for q in stored_q.values():
        res = filt.filter_item(tax, wl, q.text)
        if res.matched():
            matched.append((q, res))
    # ENRICH ONLY THE MATCHES. The search endpoint returns no member name, so
    # attribution costs one GetQuestionDetails call per question. Classifying
    # first keeps that bill proportional to what we actually care about --
    # measured 2026-08-18: 20 detail calls, versus 90 calls and ~36MB to pull
    # every MLA's full question history via GetQuestionsByMember.
    print("enriching {0} matched question(s) with tabler and answer..."
          .format(len(matched)))
    for q, res in matched:
        detail, err = niassembly.fetch_question_detail(client, q.doc_id)
        if err:
            gaps.append("question detail {0}: {1}".format(q.reference, err))
        seen += 1
        new += store(conn, {
            "id": q.id, "kind": "question", "reference": q.reference,
            "title": q.text, "dated": q.tabled.isoformat() if q.tabled else None,
            "category": q.series,
            "areas": res.issue_areas, "matched_terms": res.matched_terms,
            "url": q.url,
            "tabler_person_id": detail.tabler_person_id if detail else None,
            "tabler": detail.tabler if detail else None,
            "tabler_seat": detail.constituency if detail else None,
            "minister": detail.minister if detail else None,
            "department": detail.department if detail else None,
            "answered": (detail.answered.isoformat()
                         if detail and detail.answered else None),
            "answer": detail.answer if detail else None}, today.isoformat())

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

    # -- forward Order Paper --------------------------------------------------
    # The diary above names committees and rooms; this names the BUSINESS. All
    # items in the window are stored (an Order Paper is small and "what is the
    # Assembly doing next week" wants the whole answer), with areas where the
    # title matches so the monitor can mark OURS.
    try:
        plenary = niassembly.fetch_plenary_forward(
            client, today, today + datetime.timedelta(days=days))
    except Exception as exc:                        # noqa: BLE001
        plenary = []
        gaps.append("forward order paper: {0}: {1}".format(
            type(exc).__name__, exc))
    for p in plenary:
        res = filt.filter_item(tax, wl, p.title)
        seen += 1
        new += store(conn, {
            "id": p.id, "kind": "plenary", "title": p.title,
            "dated": p.when.isoformat() if p.when else None,
            "category": p.kind, "areas": res.issue_areas,
            "matched_terms": res.matched_terms, "url": None}, today.isoformat())

    # -- party as at the tabling date ---------------------------------------
    # Done AFTER the questions are stored, because the set of dates to resolve
    # is exactly the set of dates we ended up keeping. Fetching the current
    # roster alone would attribute a 2025 question to the party the member
    # sits in today, which is how Doug Beattie's UUP questions read
    # "Independent" before this was wired in.
    qdates = {r[0] for r in conn.execute(
        "SELECT DISTINCT dated FROM ni_items WHERE kind = 'question' "
        "AND dated IS NOT NULL")}
    fetched, aff_gaps = ni_store.resolve_dates(
        conn, client, qdates, today.isoformat(), niassembly.fetch_members_at)
    gaps.extend(aff_gaps)
    conn.commit()
    print("party resolved for {0} new date(s); {1} date(s) held in total."
          .format(fetched, len(ni_store.dates_present(conn))))

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
