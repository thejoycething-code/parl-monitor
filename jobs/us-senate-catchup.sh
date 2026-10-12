#!/bin/bash
# US Senate catch-up, BY HAND on the Mac Mini (12 October 2026). Not
# scheduled (no plist, no workflow of its own): the US weekly asks GitHub for
# the Senate half every Friday (jobs/us-weekly.sh), and this asks for that
# same half between weeklies, e.g. after the 10 October half was skipped by
# the Mini's own running marker (fixed in d68ad211).
#
#   cd ~ && nohup ~/runner/parl-monitor/tools/mini_run.sh us-senate-catchup \
#     >> ~/runner/logs/us-senate-catchup.log 2>&1 &
#
# senate.gov refuses the Mini, so this dispatches us-weekly.yml with
# senate_only=true (every Senate vote of the Congress not yet stored,
# published, no edition) and waits HOLDING THE MINI'S LOCK, so no Mini job
# publishes the store under it. Passes only if GitHub's pull job ran and
# passed: a run whose gate skipped the work also concludes "success".
#
# mini_run: no-store   (GitHub reads and publishes the store; the Mini holds the clock and the lock)
set -eo pipefail
cd "$(dirname "$0")/.."
REPO="thejoycething-code/parl-monitor"
REF="${RUNNER_REF:-main}"
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run us-weekly.yml -R "$REPO" --ref "$REF" -f senate_only=true
echo "us-senate-catchup: dispatched us-weekly.yml (senate_only) on $REF"
run_id=
for _ in $(seq 1 20); do
  sleep 6
  run_id=$(gh run list -R "$REPO" --workflow us-weekly.yml --event workflow_dispatch \
           --branch "$REF" -L 5 --json databaseId,createdAt \
           --jq "[.[] | select(.createdAt >= \"$since\")][0].databaseId // empty")
  [ -n "$run_id" ] && break
done
if [ -z "$run_id" ]; then
  echo "us-senate-catchup: the dispatched run never appeared; nothing was collected" >&2
  exit 1
fi
echo "us-senate-catchup: waiting for GitHub run $run_id, holding the Mini's lock"
if ! gh run watch "$run_id" -R "$REPO" --exit-status >/dev/null; then
  echo "us-senate-catchup: GitHub run $run_id failed: https://github.com/$REPO/actions/runs/$run_id" >&2
  exit 1
fi
PULL=$(gh run view "$run_id" -R "$REPO" --json jobs --jq '[.jobs[] | select(.name == "pull")][0].conclusion // "missing"')
if [ "$PULL" != "success" ]; then
  echo "us-senate-catchup: GitHub run $run_id did not collect (its pull job: $PULL)" >&2
  exit 1
fi
gh run view "$run_id" -R "$REPO" --log 2>/dev/null | grep -E 'Senate|senate' | grep -E 'stored|vote\(s\)|gap' | sed 's/^.*Z //' | tail -5 || true
echo "us-senate-catchup: GitHub run $run_id collected and published"
