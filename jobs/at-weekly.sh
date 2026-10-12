#!/bin/bash
# Austria weekly: members, Verhandlungsgegenstände and Klub votes of the
# Nationalrat and the Bundesrat (tools/at_rollcalls.py), then publish the raw
# archive and the store.
#
# Called by .github/workflows/at-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh at-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards.
#
#     AT_RECLASSIFY=true    re-derive every stored AT item's and division's
#                           areas (and the Landtage's), offline, before the pull
#                           (after a taxonomy-de or watchlist-at change)
#     AT_PUBLISH=false      collect only. The GitHub workflow sets it and
#                           publishes in its own steps, under the same
#                           condition as its commit step, as every store
#                           workflow there does (tests/test_vote_tracker_display.py
#                           StorePublishGuardTests). On the Mini, publishing is
#                           this script's last step, as mini_run.sh requires.
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (in the gaps table and as [gap] lines in the log): that
# run is still published, and this script exits 0 so mini_run.sh commits the
# sidecars with it. Any other failure publishes NOTHING and exits non-zero: a
# half-written store is not worth a published store whose sidecar never got
# committed, and the next run re-reads whatever this one missed. With
# AT_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
#
# THE EDITION (10 October 2026): after the collector, the Austrian weekly
# edition (tools/at_monitor.py, src/country_edition.py) is rendered to
# editions/at-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions profiles briefs reviews
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Austria weekly}"
if [ "${AT_RECLASSIFY:-}" = "true" ]; then
  python3 tools/country_petitions.py at --reclassify
  python3 tools/at_rollcalls.py --reclassify
  python3 tools/at_chamber.py --reclassify
  python3 tools/at_landtage.py --reclassify
fi
rc=0
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
# The 300 s kept back is the Landtage step's below.
python3 tools/at_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS" 300)" || rc=$?
# What was said and asked in the chamber (tools/at_chamber.py, parity layer 5):
# time-boxed to what is left of the hour, never fatal, skipped on GitHub.
bash tools/chamber_step.sh at "$SECONDS"
# The Landtage (tools/at_landtage.py, AT6, 12 October 2026): seven of the nine
# Land parliaments' documents into atl_*, before the edition that shows them
# in its own section, and Vienna's Gemeinderat (12 October 2026: 23 INFODAT
# pages, 28 s). At most five minutes (a week's read is under two minutes);
# exit 3 (gaps) or any failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/at_landtage.py --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")" \
    || echo "  [gap] the Landtage step recorded gaps or failed; the edition shows what was read"
fi
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py at || echo "  [gap] the week-ahead agenda step failed"
fi
# Petitions and consultations (tools/country_petitions.py, src/petitions.py):
# this country's open petitions, initiatives and consultations read into the
# store before the edition, which shows the new ones on our ground, the
# thresholds crossed and the deadlines. Its failure is a [gap] line, never
# the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_petitions.py at || echo "  [gap] the petitions step failed"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  # THE REVIEW WINDOW (src/edition_review.py, config/edition-review.yaml): with the
  # review on, --dm writes reviews/at-review-<date>.md instead of sending, and
  # jobs/edition-publish.sh sends the edition, honouring the review, at the window's end.
  if git ls-files --error-unmatch "editions/at-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/at_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/at_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Member intelligence (tools/member_intel.py, src/member_intel.py): committee functions, the parlament.gv.at Filter API, two requests,
# into mi_groups / mi_interests before the profiles read them. A failure is a
# [gap] line; last week's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_intel.py at \
    || echo "  [gap] member-intel: at not fully read; last week's rows kept"
fi
# Length of service (tools/member_service.py, src/member_service.py): every period each
# member has sat, from each member's biography on parlament.gv.at (one request a member, every four weeks);
# (the tool skips a read that is not due), before the profiles and vote pages read it.
# A failure is a [gap] line; last run's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_service.py at \
    || echo "  [gap] member-service: at not fully read; last run's rows kept"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/at/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py at \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "${AT_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/at.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country at --send \
    || echo "  [gap] vote briefs failed for at; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "at-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "at-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/at_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc at \
  || echo "  [gap] country-briefs failed for at; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
