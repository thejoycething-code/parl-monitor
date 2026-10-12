#!/bin/bash
# The daily health summary DM, 07:30 London (docs/mac-mini-runner.md, step 5):
# what ran in the last 24 hours on the Mini and on GitHub, what failed, what
# is running or queued, and every overdue source with new ones marked.
#
# Mac Mini only (tools/mini_run.sh health): it reads the Mini's own logs, and
# if the Mini is down the missing summary is itself the signal. It reads the
# store (for coverage) and writes nothing.
set -eo pipefail
cd "$(dirname "$0")/.."
python3 tools/health_summary.py --dm
