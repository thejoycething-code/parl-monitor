#!/bin/bash
# Croatia weekly: members, session agendas and recorded votes of the
# Hrvatski sabor (tools/hr_rollcalls.py), then publish the raw archive and
# the store.
#
# Called by .github/workflows/hr-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh hr-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     HR_RECLASSIFY=true    re-derive every stored HR item's and vote's
#                           areas, offline, before the pull (after
#                           config/taxonomy-hr.yaml or watchlist-hr changes)
#     HR_PUBLISH=false      collect only; the GitHub workflow publishes in
#                           its own steps, under its commit step's condition
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
#
# THE FIRST RUN reads the whole 11th Sabor: 30 minutes from the laptop on
# 9 October 2026, inside the 45-minute budget. If the site is slower, the
# budget stores the newest votes and discloses the rest, which drain on the
# following runs. A normal week is the two latest sessions' agendas and the
# handful of votes held since.
# mini_run: commit editions profiles briefs
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Croatia weekly}"
if [ "${HR_RECLASSIFY:-}" = "true" ]; then
  python3 tools/hr_rollcalls.py --reclassify
fi
rc=0
python3 tools/hr_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  # The weekly edition (src/country_edition.py, tools/hr_monitor.py), to Chris
  # alone by DM, archived to editions/. Once a day: an edition already
  # committed for today is rewritten, not resent. A failed render never stops
  # the publish below.
  export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/hr-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/hr_monitor.py --edition \
      || echo "  [gap] hr-monitor: the edition failed to render; the store is still published"
  else
    python3 tools/hr_monitor.py --edition --dm \
      || echo "  [gap] hr-monitor: the edition or its DM failed; the store is still published"
  fi
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/hr/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  # X6: party history from the Sabor's transcripts (tools/hr_party_history.py),
  # newest first under its own clock (ten minutes: the workflow's hour also holds
  # the collector); the profiles read what it has stored. The first reads of the
  # 11th Sabor's ~950 transcripts drain over a few weeks.
  python3 tools/hr_party_history.py --budget-seconds "${HR_TRANSCRIPT_SECONDS:-600}" \
    || echo "  [gap] hr-party-history: transcripts not all read; the rest drain next run"
  python3 tools/member_profiles.py hr \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "${HR_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/hr.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country hr --send \
    || echo "  [gap] vote briefs failed for hr; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "hr-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "hr-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/hr_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc hr \
  || echo "  [gap] country-briefs failed for hr; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
