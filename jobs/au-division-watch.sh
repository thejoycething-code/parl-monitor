#!/bin/bash
# Australia division watch: brief new House and Senate divisions on our ground
# from the Hansard OpenAustralia posted overnight, then publish the payloads it
# archived to the raw-archive release.
#
# Called by .github/workflows/au-division-watch.yml and, on the Mac Mini, by
# tools/mini_run.sh au-division-watch. One script, two callers
# (docs/mac-mini.md). The caller commits data/briefs and data/raw.json.
#
# Speaks once per division: a brief that exists is neither rewritten nor
# resent, so overlapping slots (or the Mini and a late GitHub backup) are
# harmless. The DM goes to Christopher alone (src/vote_brief.py fixes the
# recipient); on the Mini the Slack token comes from ~/runner/env.
#
#     DIVISION_SINCE=YYYY-MM-DD   look back to this date (blank = the tool's window)
#     DIVISION_FORCE=true         rewrite and resend briefs that exist
#
# mini_run: no-store   (reads and writes no store, so the Mini skips the pull)
set -eo pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Australia division watch}"
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
ARGS=()
[ -n "${DIVISION_SINCE:-}" ] && ARGS+=(--since "$DIVISION_SINCE")
[ "${DIVISION_FORCE:-}" = "true" ] && ARGS+=(--force)
python3 tools/au_division_brief.py "${ARGS[@]}"
# No pull first: a push merges the published folder beneath the local
# files, so a folder two runs archive into on the same day ends as the union.
python3 tools/raw_state.py --push
