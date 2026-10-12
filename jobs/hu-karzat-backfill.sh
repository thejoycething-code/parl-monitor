#!/bin/bash
# Hungary, HU7: the 43rd term's papers, recorded votes and member positions
# from karzat's open data (CC BY 4.0), BY HAND on the Mac Mini, once. Not a
# feed and not scheduled (no plist, no workflow): karzat stopped updating
# around 28 August 2026, so this is a one-off historical backfill, safe to
# rerun if it ever updates (every write is an upsert; a commit already loaded
# is skipped unless FORCE=true).
#
#   cd ~ && nohup ~/runner/parl-monitor/tools/mini_run.sh hu-karzat-backfill \
#     >> ~/runner/logs/hu-karzat-backfill.log 2>&1 &
#
#     KARZAT_COMMIT   a karzat commit to pin (default: its newest data commit)
#     FORCE=true      reload a commit already loaded
#
# Reads ONLY karzat's derived files from GitHub (four JSON files, about 4 MB,
# a handful of requests); never parlament.hu, never karzat's site. Then the
# one-off read for Chris, "since 9 May" (every vote and paper the backfill
# put on our ground, with the attribution), is written to
# editions/hu-karzat-backfill.md and committed with the store; no DM. Then
# the raw archive and the store are published.
#
# mini_run: commit editions
set -eo pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never the weekly's (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Hungary karzat backfill}"
export PYTHONUNBUFFERED=1
args=()
[ -n "${KARZAT_COMMIT:-}" ] && args+=(--commit "$KARZAT_COMMIT")
[ "${FORCE:-}" = "true" ] && args+=(--force)
python3 tools/hu_karzat_backfill.py ${args[@]+"${args[@]}"}
python3 tools/hu_karzat_backfill.py --summary --out editions/hu-karzat-backfill.md \
  || echo "  [gap] the backfill summary failed to render"
# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
