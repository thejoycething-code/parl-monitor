#!/bin/bash
# Coverage watch: is everything still being tracked?
#
# Called by .github/workflows/coverage-watch.yml and, on the Mac Mini, by
# tools/mini_run.sh coverage. One script, two callers (docs/mac-mini-runner.md).
# Both callers fetch the store first. READ-ONLY: it never writes data/.
#
# Exits non-zero when a pipeline has stopped, a feed has gone quiet, or a
# pipeline ran green over data it did not refresh.
set -eo pipefail
cd "$(dirname "$0")/.."
python3 tools/coverage.py
