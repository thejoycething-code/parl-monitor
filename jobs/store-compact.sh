#!/bin/bash
# Compact the store ONCE, BY HAND on the Mac Mini (12 October 2026,
# docs/store-split-plan.md Stage 1, approved by Chris: "Yes, build and merge
# it"). Not scheduled: no plist, no workflow. tools/store_compact.py rebuilds
# the rowid vote tables WITHOUT ROWID (one transaction each, row counts and a
# checksum verified) and VACUUMs; then the store is published. Measured on a
# laptop copy of the 12 October store: 1,825 MB to 1,480 MB raw, 447 MB to
# 308 MB compressed, in under a minute. A store writer like any other: it
# holds mini_run.sh's lock (first in, first out), so it queues behind
# whatever job is running and nothing else touches the store meanwhile.
# Idempotent: a second run finds nothing to rebuild and only vacuums.
#
#   cd ~ && nohup ~/runner/parl-monitor/tools/mini_run.sh store-compact \
#     >> ~/runner/logs/store-compact.log 2>&1 &
#
# Every store built from scratch already has the new form (the CREATE TABLE
# statements say WITHOUT ROWID), and every later push vacuums
# (tools/db_state.py vacuum_store), so this never needs to run again.
set -eo pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never a weekly's (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Store compact}"
export PYTHONUNBUFFERED=1
python3 tools/store_compact.py --dry-run
python3 tools/store_compact.py
python3 tools/db_state.py --push
