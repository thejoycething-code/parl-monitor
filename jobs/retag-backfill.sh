#!/bin/bash
# Retag stored UK, devolved and EU rows on the Mac Mini, BY HAND, after a
# taxonomy change (9 October 2026, v1.20). The same steps as the "retag stored
# rows" mode of backfill.yml, which now runs here instead (CLAUDE.md: repairs
# run on the Mini, never as a GitHub dispatch). The GitHub run of v1.20's retag
# did its work and then lost the store race to a Mini job publishing at the
# same moment ("parl-monitor.db.prev is on the release"); under the runner's
# lock that cannot happen.
#
#   cd ~ && RETAG_BASELINE=9437b29d~1 JOB_TIMEOUT=7200 \
#     nohup ~/runner/parl-monitor/tools/mini_run.sh retag-backfill \
#     >> ~/runner/logs/retag-backfill.log 2>&1 &
#
#     RETAG_BASELINE=<git ref>   the commit whose config/taxonomy.yaml the stored
#                                tags were made under (the trust check refuses a
#                                table whose stored tags it cannot reproduce)
#
# Canada has its own: CA_RETAG=true through jobs/ca-backfill.sh. The US, Irish
# and Australian rows are re-derived by their weeklies' reclassify inputs.
set -o pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never a weekly's (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Retag backfill}"
export PYTHONUNBUFFERED=1
[ -n "${RETAG_BASELINE:-}" ] || { echo "set RETAG_BASELINE to the previous taxonomy's commit (e.g. 9437b29d~1)"; exit 2; }
git show "${RETAG_BASELINE}:config/taxonomy.yaml" > /tmp/baseline-taxonomy.yaml \
  || { echo "no config/taxonomy.yaml at $RETAG_BASELINE"; exit 2; }
head -4 /tmp/baseline-taxonomy.yaml | grep -i version
python3 tools/raw_state.py --pull || exit 1

rc=0
python3 tools/retag_items.py --apply --baseline /tmp/baseline-taxonomy.yaml || rc=1
python3 tools/retag_passages.py --apply | grep -vE "^  (Spoke| +areas| +excerpt)" || rc=1
# NI division areas are owned by ni_classify; signed verdicts are re-applied
# after a retag (2 Oct 2026). Offline, no model.
python3 tools/ni_classify.py --apply | grep -vE "^      " || rc=1
python3 tools/sp_score.py --apply || rc=1
python3 tools/devolved_score.py --nation wales --apply || rc=1
python3 tools/devolved_score.py --nation ni --apply || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
