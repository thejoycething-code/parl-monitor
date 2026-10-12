#!/bin/bash
# Mexico weekly, the Mac Mini's half: the CLOCK, not the work.
#
# mini_run: no-store   (reads and writes no store, so the Mini skips the pull)
#
# Run by tools/mini_run.sh mx-weekly (launchd, Saturdays 15:30 London). The
# Chamber of Deputies' hosts refuse UK addresses -- every diputados.gob.mx
# address timed out from the laptop in London on 9 October 2026, while
# GitHub's runners read them (docs/mexico-scope.md). So the Mini keeps the
# time and GitHub does the work: this dispatches .github/workflows/mx-weekly.yml,
# which runs jobs/mx-collect.sh against the store. A hand dispatch always
# runs past the workflow's mini-check gate; the stamp mini_run.sh records
# afterwards (MINI_LAST_MX_WEEKLY) makes the backup crons skip.
#
# It still asks the Chamber first, and says so if the answer ever changes:
# if the Mini can reach it, the collector could run here instead, and that
# is a decision for Christopher, not for this script.
set -eo pipefail
cd "$(dirname "$0")/.."
REPO="thejoycething-code/parl-monitor"
REF="${RUNNER_REF:-main}"
# Fortnightly (X9, 10 October 2026): the Mini dispatches only in an ODD ISO
# week (Guatemala takes the even ones). MX_FORCE=true overrides by hand.
week=$(date -u +%V)
if [ $((10#$week % 2)) -eq 0 ] && [ "${MX_FORCE:-}" != "true" ]; then
  echo "mx-weekly: ISO week $week is even; Mexico runs fortnightly (X9), nothing to dispatch"
  exit 0
fi
UA="CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)"
if curl -sS -m 20 -o /dev/null -A "$UA" https://gaceta.diputados.gob.mx/gp_indice.html 2>/dev/null; then
  echo "mx-weekly: gaceta.diputados.gob.mx ANSWERS this host; the collector could run here (see docs/mexico-scope.md). Dispatching to GitHub as designed."
else
  echo "mx-weekly: gaceta.diputados.gob.mx does not answer this host (expected from the UK); dispatching to GitHub"
fi
# A backup cron that already ran today (GitHub on time, the Mini late) has
# done the week's work: a second run would only re-read it.
TODAY="$(date -u +%Y-%m-%d)T00:00:00Z"
BUSY=$(gh api "repos/$REPO/actions/workflows/mx-weekly.yml/runs?per_page=20" \
       --jq "[.workflow_runs[]
              | select(.created_at >= \"$TODAY\")
              | select(.conclusion == \"success\" or .status == \"in_progress\" or .status == \"queued\")]
             | length" 2>/dev/null || echo 0)
# A run the gate skipped also concludes "success", so MX_FORCE (a recovery by
# hand) looks past this check.
if [ "${BUSY:-0}" -gt 0 ] && [ "${MX_FORCE:-}" != "true" ]; then
  echo "mx-weekly: $BUSY run(s) already succeeded or are running today; nothing to dispatch"
  exit 0
fi
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run mx-weekly.yml -R "$REPO" --ref "$REF" -f from_mini=true
echo "mx-weekly: dispatched mx-weekly.yml on $REF"
# HOLD THE LOCK UNTIL GITHUB HAS PUBLISHED (12 October 2026). On 10 October
# this script returned at once, mini_run released the lock, and a Mini job
# published the store while GitHub collected: the run read 8,388
# iniciativas and 285 votes, then refused to publish ("THE STORE MOVED UNDER
# YOU") and the fortnight's Mexico was lost. Waiting here keeps every Mini
# job queued behind it, as the US weekly's Senate half does. The plist gives
# the job two hours (the run takes about 45 minutes, its timeout is 75).
run_id=
for _ in $(seq 1 20); do
  sleep 6
  run_id=$(gh run list -R "$REPO" --workflow mx-weekly.yml --event workflow_dispatch \
           --branch "$REF" -L 5 --json databaseId,createdAt \
           --jq "[.[] | select(.createdAt >= \"$since\")][0].databaseId // empty")
  [ -n "$run_id" ] && break
done
if [ -z "$run_id" ]; then
  echo "mx-weekly: the dispatched run never appeared; nothing was collected" >&2
  exit 1
fi
echo "mx-weekly: waiting for GitHub run $run_id, holding the Mini's lock"
if ! gh run watch "$run_id" -R "$REPO" --exit-status >/dev/null; then
  echo "mx-weekly: GitHub run $run_id failed: https://github.com/$REPO/actions/runs/$run_id" >&2
  exit 1
fi
# "Success" is not enough: a run whose gate skipped the work also succeeds
# (12 October 2026). The collecting job itself must have run and passed.
PULL=$(gh run view "$run_id" -R "$REPO" --json jobs --jq '[.jobs[] | select(.name == "pull")][0].conclusion // "missing"')
if [ "$PULL" != "success" ]; then
  echo "mx-weekly: GitHub run $run_id did not collect (its pull job: $PULL)" >&2
  exit 1
fi
echo "mx-weekly: GitHub run $run_id collected and published"
