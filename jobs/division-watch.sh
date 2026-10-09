#!/bin/bash
# Division watch: brief today's divisions on our ground, then publish the
# division payloads it archived to the raw-archive release.
#
# Called by .github/workflows/division-watch.yml and, on the Mac Mini, by
# tools/mini_run.sh division-watch. One script, two callers
# (docs/mac-mini-runner.md). The caller commits data/briefs and data/raw.json.
#
# Speaks once per division: a brief that exists is neither rewritten nor
# resent, so overlapping slots (or the Mini and a late GitHub backup) are
# harmless.
#
#     DIVISION_DATE=YYYY-MM-DD   sitting day to brief (blank = today)
#     DIVISION_FORCE=true        rewrite and resend briefs that exist
#
# mini_run: no-store   (reads and writes no store, so the Mini skips the pull)
set -eo pipefail
cd "$(dirname "$0")/.."
ARGS=()
[ -n "${DIVISION_DATE:-}" ] && ARGS+=(--date "$DIVISION_DATE")
[ "${DIVISION_FORCE:-}" = "true" ] && ARGS+=(--force)
python3 tools/division_brief.py "${ARGS[@]}"
# No pull first: a push merges the published folder beneath the local
# files, so a folder two runs archive into on the same day ends as the union.
python3 tools/raw_state.py --push
