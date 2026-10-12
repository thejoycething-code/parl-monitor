#!/bin/bash
# Guatemala weekly: initiatives, plenary votes with every deputy's position,
# and deputies of the Congreso de la República (tools/gt_rollcalls.py), then
# publish the raw archive and the store.
#
# Called by .github/workflows/gt-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh gt-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     GT_RECLASSIFY=true    re-derive every stored GT initiative's and
#                           division's areas, offline, before the pull (after
#                           config/taxonomy-es.yaml or watchlist-gt changes)
#
# The first runs backfill the X legislature from 14 January 2024: 190 session
# pages and about 2,660 vote pages at one request every two seconds. The
# budget (45 minutes) stops each run cleanly and the next resumes from the
# store, so the backfill is spread over three runs or so.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps: that run is still published, and this script exits 0 so the caller
# commits the sidecars with it. Exit 1 includes a BOT CHALLENGE (the scoping
# laptop was refused by the site's WAF; GitHub's runners were not): nothing
# is published, and on the Mini the GitHub backup then runs at its slot.
# mini_run: commit profiles briefs
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed
# on the workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it
# here or the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Guatemala weekly}"
# Fortnightly (X9, 10 October 2026): a scheduled run does the work only in
# an EVEN ISO week. On GitHub the workflow's gate decides; here the Mini's
# weekly launchd slot skips itself in an odd week. GT_FORCE=true overrides
# (a run by hand).
if [ -z "${GITHUB_ACTIONS:-}" ] && [ "${GT_FORCE:-}" != "true" ]; then
  week=$(date -u +%V)
  if [ $((10#$week % 2)) -ne 0 ]; then
    echo "gt-weekly: ISO week $week is odd; Guatemala runs fortnightly (X9), nothing to do"
    exit 0
  fi
fi
# THE MINI IS REFUSED (12 October 2026, the first Mini run): congreso.gob.gt
# answered the Mini with the same bot challenge as the scoping laptop, while
# GitHub's runners read every page (docs/guatemala-scope.md). The challenge is
# never worked around. So on the Mini, when the site challenges it, this asks
# GitHub to do the work (gt-weekly.yml, from_mini) and waits HOLDING THE
# MINI'S LOCK, so no Mini job publishes the store under it, as Mexico does.
# It passes only if GitHub's pull job itself ran and passed. If the site ever
# answers the Mini, the collector below runs here instead, unchanged.
if [ -z "${GITHUB_ACTIONS:-}" ]; then
  UA="CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)"
  code=$(curl -sS -m 30 -o /dev/null -w "%{http_code}" -A "$UA" https://www.congreso.gob.gt/ 2>/dev/null || echo 000)
  if [ "$code" != "200" ]; then
    REPO="thejoycething-code/parl-monitor"
    REF="${RUNNER_REF:-main}"
    echo "gt-weekly: congreso.gob.gt answers this host $code (a challenge, never worked around); dispatching to GitHub"
    since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    gh workflow run gt-weekly.yml -R "$REPO" --ref "$REF" -f from_mini=true \
      -f reclassify="${GT_RECLASSIFY:-false}"
    run_id=
    for _ in $(seq 1 20); do
      sleep 6
      run_id=$(gh run list -R "$REPO" --workflow gt-weekly.yml --event workflow_dispatch \
               --branch "$REF" -L 5 --json databaseId,createdAt \
               --jq "[.[] | select(.createdAt >= \"$since\")][0].databaseId // empty")
      [ -n "$run_id" ] && break
    done
    if [ -z "$run_id" ]; then
      echo "gt-weekly: the dispatched run never appeared; nothing was collected" >&2
      exit 1
    fi
    echo "gt-weekly: waiting for GitHub run $run_id, holding the Mini's lock"
    if ! gh run watch "$run_id" -R "$REPO" --exit-status >/dev/null; then
      echo "gt-weekly: GitHub run $run_id failed: https://github.com/$REPO/actions/runs/$run_id" >&2
      exit 1
    fi
    PULL=$(gh run view "$run_id" -R "$REPO" --json jobs --jq '[.jobs[] | select(.name == "pull")][0].conclusion // "missing"')
    if [ "$PULL" != "success" ]; then
      echo "gt-weekly: GitHub run $run_id did not collect (its pull job: $PULL)" >&2
      exit 1
    fi
    echo "gt-weekly: GitHub run $run_id collected and published"
    exit 0
  fi
fi
if [ "${GT_RECLASSIFY:-}" = "true" ]; then
  python3 tools/gt_rollcalls.py --reclassify
fi
rc=0
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
python3 tools/gt_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS")" || rc=$?
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/gt.json (committed with data/). Before the alerts:
# a vote briefed here is not alerted again. Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country gt --send \
    || echo "  [gap] vote briefs failed for gt; the next run retries"
fi
# Instant Latam alerts (tools/latam_alerts.py): this country's watched and
# tier-1 items, a short DM each to Chris alone, de-duplicated in
# data/latam-alerts/gt.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/latam_alerts.py --country gt --send \
    || echo "  [gap] latam-alerts failed for gt; the next run retries"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/gt/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py gt \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "gt-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "gt-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/gt_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc gt \
  || echo "  [gap] country-briefs failed for gt; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
