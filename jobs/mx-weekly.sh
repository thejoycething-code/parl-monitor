#!/bin/bash
# Mexico weekly, the Mac Mini's half: the CLOCK, not the work.
#
# mini_run: no-store   (reads and writes no store, so the Mini skips the pull)
#
# Run by tools/mini_run.sh mx-weekly (launchd, Saturdays 04:00 London). The
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
if [ "${BUSY:-0}" -gt 0 ]; then
  echo "mx-weekly: $BUSY run(s) already succeeded or are running today; nothing to dispatch"
  exit 0
fi
gh workflow run mx-weekly.yml -R "$REPO" --ref "$REF"
echo "mx-weekly: dispatched mx-weekly.yml on $REF"
