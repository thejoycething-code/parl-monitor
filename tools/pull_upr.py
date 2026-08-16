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

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml

from src import filter as filt
from src.http import FetchError, HttpClient
from src.ingest import upr


def load_settings():
    with open(os.path.join(ROOT, "config", "un-settings.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    refused_only = "--refused-only" in sys.argv
    settings = load_settings()
    wanted = args or (settings.get("upr_issues") or [])

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    try:
        issue_ids = upr.fetch_issue_ids(client)
    except FetchError as exc:
        print("could not read the Issues thesaurus: {0}".format(exc))
        return 1
    if not issue_ids:
        print("Issues thesaurus came back empty; refusing to harvest blind")
        return 1

    kept, discarded, gaps = [], 0, []
    for label in wanted:
        issue_id = issue_ids.get(label)
        if not issue_id:
            # Louder than a silent skip: a renamed tag would otherwise look
            # like an issue nobody has raised.
            gaps.append("{0}: no such issue tag (renamed upstream?)".format(label))
            continue
        try:
            recs, total, truncated = upr.fetch_recommendations(
                client, issue_id, label,
                page_size=settings.get("upr_page_size") or 100,
                max_pages=settings.get("upr_max_pages") or 20)
        except FetchError as exc:
            gaps.append("{0}: failed after {1} attempts".format(label, exc.attempts))
            continue
        on_topic = []
        for rec in recs:
            if filt.filter_item(tax, wl, rec.text).matched():
                on_topic.append(rec)
            else:
                discarded += 1
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

    print("\nsample:")
    for rec in recs[:5]:
        print("  {0} -> {1} [{2}]".format(
            rec.recommending_state, rec.state_under_review, rec.response))
        print("    {0}".format((rec.text or "")[:96]))
        print("    {0}".format(rec.url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
