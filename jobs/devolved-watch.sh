#!/bin/bash
# Devolved watch: brief new divisions on our ground at Holyrood, the Senedd
# and the Assembly, then publish the payloads it archived to the raw-archive
# release.
#
# Called by .github/workflows/devolved-watch.yml and, on the Mac Mini, by
# tools/mini_run.sh devolved-watch. One script, two callers. The caller
# commits data/briefs and data/raw.json (the runner commits data/ whole).
#
# Speaks once per division: a brief that exists is neither rewritten nor
# resent, so the evening and next-day slots, or the Mini and a late GitHub
# backup, never say a thing twice. Each run looks back seven days.
#
#     DEVOLVED_NATION=scotland|wales|ni   one nation (blank = all three)
#     DEVOLVED_SINCE=YYYY-MM-DD           look back to this date instead
#     DEVOLVED_FORCE=true                 rewrite and resend briefs that exist
#
# mini_run: no-store   (reads and writes no store, so the Mini skips the pull)
set -eo pipefail
cd "$(dirname "$0")/.."
ARGS=()
[ -n "${DEVOLVED_NATION:-}" ] && ARGS+=(--nation "$DEVOLVED_NATION")
[ -n "${DEVOLVED_SINCE:-}" ] && ARGS+=(--since "$DEVOLVED_SINCE")
[ "${DEVOLVED_FORCE:-}" = "true" ] && ARGS+=(--force)
python3 tools/devolved_brief.py "${ARGS[@]}"
# No pull first: a push merges the published folder beneath the local
# files, so a folder two runs archive into on the same day ends as the union.
python3 tools/raw_state.py --push
