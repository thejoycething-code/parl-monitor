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
# Lean: a quiet day costs a handful of requests per country; a reader that
# fails is a [gap] line and costs the others nothing. No store is read or
# written; the raw payloads it archived are published at the end.
#
# MINI ONLY, NO GITHUB WORKFLOW (the backstop is each country's weekly step).
#
#     VOTE_BRIEFS_DAYS=N   look back N days (default 3)
#
# mini_run: no-store   (reads and writes no store, so the Mini skips the pull)
set -eo pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Daily vote briefs}"
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
export PYTHONUNBUFFERED=1
ARGS=(--daily --send)
[ -n "${VOTE_BRIEFS_DAYS:-}" ] && ARGS+=(--days "$VOTE_BRIEFS_DAYS")
python3 tools/country_vote_briefs.py "${ARGS[@]}"
# No pull first: a push merges the published folder beneath the local
# files, so a folder two runs archive into on the same day ends as the union.
python3 tools/raw_state.py --push
