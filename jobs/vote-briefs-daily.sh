#!/bin/bash
# Daily vote briefs on the Mac Mini (tools/mini_run.sh vote-briefs-daily):
# ONE job for every country whose parliament publishes its votes the same day
# cheaply and openly, read directly: the Netherlands (Tweede Kamer OData),
# Poland (Sejm API), Switzerland (the Nationalrat, OData), Brazil (Câmara API
# v2 and Senado) and Italy (Senate SPARQL, Openpolis for the Camera).
#
# Handover item 1 (docs/country-parity-handover.md, 10 October 2026). Each
# country's own collector parses and classifies the last few days of votes
# into a throwaway store in a temporary directory (src/vote_brief_sources.py);
# the edition's own reader picks the watched and tier-1 votes; each is
# briefed once to data/briefs/ and the run sends ONE DM to Chris alone
# (src/country_vote_brief.py). data/vote-briefs/<cc>.json, shared with the
# step in each country's weekly job, keeps a vote from being briefed twice.
# Every other country with member votes is briefed after its weekly (or
# fortnightly) collection instead; France too (one 27 MB nightly zip).
#
# THE DAILY SWEEP (11 October 2026; src/country_day_sweep.py, readers in
# src/day_sweep_sources.py): the same run then reads what is NEW on our
# ground, not only votes (bills, motions, questions, agenda points) for the
# Netherlands, Poland, Switzerland, Brazil, Italy, Austria, France (its
# agenda, once a day) and Spain (from 23 December 2026) into the same
# throwaway store; tier 1 and watched only, judged by the noise rules'
# minimum evidence like the briefs, de-duplicated against the weekly
# editions, the vote briefs and data/day-sweep/<cc>.json, and the run sends
# ONE DM for the briefs and the new items together (nothing when nothing).
# Measured 11 October 2026: about 45 s for the whole run, votes and sweep.
# The same evening (branch gaps-day-sweep) the sweep added Belgium,
# Portugal, Croatia, Slovakia, Argentina, France's new dossiers, and Chile,
# Peru, Ecuador, Bolivia, the Dominican Republic, Panama, Honduras and
# Uruguay through the Latam alerts' path and ledger (no double send with
# tools/latam_alerts.py): about 2 minutes for the whole run from the laptop
# (55 s before), each request retried at most once.
#
# Lean: a quiet day costs a handful of requests per country; a reader that
# fails is a [gap] line and costs the others nothing. No store is read or
# written; the raw payloads it archived are published at the end.
#
# MINI ONLY, NO GITHUB WORKFLOW (the backstop is each country's weekly step).
#
#     VOTE_BRIEFS_DAYS=N   look back N days (default 3)
#     DAY_SWEEP=off        brief the votes only, no sweep of new items
#
# mini_run: no-store   (reads and writes no store, so the Mini skips the pull)
set -eo pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Daily vote briefs}"
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
export PYTHONUNBUFFERED=1
ARGS=(--daily --send)
[ -n "${VOTE_BRIEFS_DAYS:-}" ] && ARGS+=(--days "$VOTE_BRIEFS_DAYS")
[ "${DAY_SWEEP:-}" = "off" ] && ARGS+=(--no-sweep)
python3 tools/country_vote_briefs.py "${ARGS[@]}"
# No pull first: a push merges the published folder beneath the local
# files, so a folder two runs archive into on the same day ends as the union.
python3 tools/raw_state.py --push
