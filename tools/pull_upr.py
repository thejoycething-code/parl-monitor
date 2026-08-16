"""Harvest UPR recommendations on our issues and report by state.

    python3 tools/pull_upr.py                 # every configured issue
    python3 tools/pull_upr.py "Right to life"  # one issue
    python3 tools/pull_upr.py --refused-only   # only what states declined

Every UN member state is reviewed by the others every 4-5 years, and each
recommendation records whether the state SUPPORTED or NOTED it. "Noted" is
the diplomatic form of refusal, so this is a per-state record of positions
taken -- the UN analogue of the Commons vote tracker.

Relevance is decided by the taxonomy filter on the recommendation text, NOT
by the UPR issue tag: the UN's "Right to life" is largely death-penalty work.
Rows the filter rejects are counted and reported, never silently dropped.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml

from src import db, filter as filt
from src.http import FetchError, HttpClient
from src.ingest import upr


def load_settings():
    with open(os.path.join(ROOT, "config", "un-settings.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def store(conn, rec, result):
    """Upsert one recommendation with the taxonomy verdict that admitted it.

    Upsert rather than insert: a recommendation's response can change (a state
    can revisit a "Noted" at the next cycle) and re-running must refresh it
    without duplicating. issue_areas and matched_terms are stored because the
    taxonomy is maintained by reading back what it actually matched.
    """
    import datetime
    conn.execute(
        "INSERT INTO upr_recommendations (id, first_seen, captured_at, text, state_under_review, "
        "sur_group, recommending_state, rs_group, response, refused, issues, "
        "issue_areas, matched_terms, cycle, session, action_category, url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        # first_seen is deliberately NOT in the update list: it records when a
        # recommendation entered our store, and a re-read must not move it.
        "ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at, "
        "text=excluded.text, response=excluded.response, refused=excluded.refused, "
        "issues=excluded.issues, issue_areas=excluded.issue_areas, "
        "matched_terms=excluded.matched_terms",
        (rec.id, datetime.date.today().isoformat(),
         datetime.date.today().isoformat(), rec.text, rec.state_under_review,
         rec.sur_group, rec.recommending_state, rec.rs_group, rec.response,
         1 if rec.refused else 0, json.dumps(rec.issues),
         json.dumps(result.issue_areas),
         json.dumps(result.matched_terms + result.watchlist_hits),
         rec.cycle, rec.session, rec.action_category, rec.url))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    refused_only = "--refused-only" in sys.argv
    settings = load_settings()
    # Terms first: quoted phrases narrow server-side, where issue tags mean
    # fetching thousands to keep dozens. Issue tags stay available via
    # --by-issue for coverage checks against the terms.
    by_issue = "--by-issue" in sys.argv
    if by_issue:
        wanted = args or (settings.get("upr_issues") or [])
    else:
        wanted = args or (settings.get("upr_search_terms") or [])

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    issue_ids = {}
    if by_issue:
        try:
            issue_ids = upr.fetch_issue_ids(client)
        except FetchError as exc:
            print("could not read the Issues thesaurus: {0}".format(exc))
            return 1
        if not issue_ids:
            print("Issues thesaurus came back empty; refusing to harvest blind")
            return 1

    # Snapshot the ids we already hold. "New" is then a set difference, not a
    # date comparison: first_seen was backfilled for existing rows when the
    # column was added, so on that day every row carried the current date and
    # a date test reported the entire store as new.
    before = {r["id"] for r in conn.execute("SELECT id FROM upr_recommendations")}

    kept, discarded, gaps = [], 0, []
    for label in wanted:
        issue_id, term = None, None
        if by_issue:
            issue_id = issue_ids.get(label)
            if not issue_id:
                # Louder than a silent skip: a renamed tag would otherwise
                # look like an issue nobody has raised.
                gaps.append("{0}: no such issue tag (renamed upstream?)".format(label))
                continue
        else:
            term = label
            if not (label.startswith('"') and label.endswith('"')):
                # Unquoted multi-word terms match loosely and return the whole
                # database. Refuse rather than harvest 10,000 rows by accident.
                gaps.append("{0}: not a quoted phrase; skipped".format(label))
                continue
        try:
            recs, total, truncated = upr.fetch_recommendations(
                client, issue_id=issue_id, issue_label=label, search_term=term,
                page_size=settings.get("upr_page_size") or 100,
                max_pages=settings.get("upr_max_pages") or 20)
        except FetchError as exc:
            gaps.append("{0}: failed after {1} attempts".format(label, exc.attempts))
            continue
        on_topic = []
        for rec in recs:
            result = filt.filter_item(tax, wl, rec.text)
            if result.matched():
                on_topic.append(rec)
                store(conn, rec, result)
            else:
                discarded += 1
        conn.commit()
        kept.extend(on_topic)
        note = " (TRUNCATED at max_pages)" if truncated else ""
        print("{0:<38} {1:>4} fetched, {2:>3} on-topic{3}".format(
            label[:38], total if total is not None else len(recs), len(on_topic), note))

    # Deduplicate: issues are multi-valued, so one recommendation can arrive
    # under several tags.
    unique = {r.id: r for r in kept}
    recs = list(unique.values())
    if refused_only:
        recs = [r for r in recs if r.refused]

    print("\n{0} on-topic recommendation(s), {1} discarded as off-topic, "
          "{2} duplicate(s) merged".format(len(recs), discarded, len(kept) - len(unique)))
    if gaps:
        print("GAPS ({0}):".format(len(gaps)))
        for g in gaps:
            print("  " + g)

    tally = upr.by_state(recs)
    if tally:
        print("\n{0:<28} {1:>9} {2:>8}".format("state under review", "supported", "refused"))
        for state, row in sorted(tally.items(),
                                 key=lambda kv: -(kv[1]["refused"] + kv[1]["supported"])):
            print("{0:<28} {1:>9} {2:>8}".format(state[:28], row["supported"], row["refused"]))

    stored = conn.execute("SELECT COUNT(*) FROM upr_recommendations").fetchone()[0]
    print("\nstored: {0} recommendation(s) in upr_recommendations".format(stored))

    # What actually arrived this run. The database trails the UPR calendar by
    # roughly nine months (see un-settings.yaml), so a monthly run is mostly
    # re-reads: the handful of genuinely new rows is the whole signal, and
    # printing the total alone would bury it.
    after = {r["id"] for r in conn.execute("SELECT id FROM upr_recommendations")}
    new_ids = after - before
    fresh = [r for r in conn.execute(
        "SELECT id, state_under_review s, recommending_state r, response p, text t, url u "
        "FROM upr_recommendations ORDER BY s") if r["id"] in new_ids]
    print("NEW this run: {0}".format(len(fresh)))
    for row in fresh[:25]:
        print("  {0} <- {1} [{2}]".format(row["s"], row["r"], row["p"]))
        print("    {0}".format((row["t"] or "").strip()[:100]))
    if len(fresh) > 25:
        print("  ...and {0} more".format(len(fresh) - 25))

    print("\nsample:")
    for rec in recs[:5]:
        print("  {0} -> {1} [{2}]".format(
            rec.recommending_state, rec.state_under_review, rec.response))
        print("    {0}".format((rec.text or "")[:96]))
        print("    {0}".format(rec.url))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
