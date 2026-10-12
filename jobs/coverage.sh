#!/bin/bash
# Coverage watch: is everything still being tracked?
#
# Called by .github/workflows/coverage-watch.yml and, on the Mac Mini, by
# tools/mini_run.sh coverage. One script, two callers (docs/mac-mini-runner.md).
# Both callers fetch the store first. It writes only its own state file.
#
# Exits non-zero when a pipeline has stopped, a feed has gone quiet, or a
# pipeline ran green over data it did not refresh -- but only the FIRST time
# it sees that problem, or when it has grown a week since last said
# (--state, docs/mac-mini-runner.md step 5). Every overdue source is still
# listed daily in the health summary (jobs/health.sh).
#
# The state lives in data/coverage-state.json. The Mini commits it; the
# GitHub backup is read-only and compares against the committed copy.
set -eo pipefail
cd "$(dirname "$0")/.."
python3 tools/coverage.py --state data/coverage-state.json
