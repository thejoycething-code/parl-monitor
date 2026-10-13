#!/bin/bash
# Belgium weekly: members, dossiers, plenary sittings and recorded votes of
# the federal Chamber (tools/be_rollcalls.py), then publish the raw archive
# and the store.
#
# Called by .github/workflows/be-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh be-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     BE_RECLASSIFY=true    re-apply config/watchlist-be.yaml to every stored
#                           dossier and division, offline, before the pull
#
#     BE_PUBLISH=false      collect only (GitHub, whose own steps publish)
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (in the gaps table and as [gap] lines in the log): that
# run is still published, and this script exits 0 so mini_run.sh commits the
# sidecars with it. Any other failure publishes NOTHING and exits non-zero: a
# half-written store is not worth a published store whose sidecar never got
# committed, and the next run re-reads whatever this one missed. With
# BE_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
#
# COMMUNITIES AND REGIONS (13 October 2026): tools/be_regions.py after the
# collector reads the regional and community parliaments for the edition's
# "Communities and regions" section (BE_RECLASSIFY re-applies the lists to them too).
#
# THE EDITION (10 October 2026): after the collector, the Belgian weekly
# edition (tools/be_monitor.py, src/country_edition.py) is rendered to
# editions/be-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions profiles briefs reviews
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Belgium weekly}"
if [ "${BE_RECLASSIFY:-}" = "true" ]; then
  python3 tools/country_petitions.py be --reclassify
  python3 tools/be_rollcalls.py --reclassify
  python3 tools/be_chamber.py --reclassify
  python3 tools/be_regions.py --reclassify || echo "  [gap] the regional reclassify failed"
fi
rc=0
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
# The third argument keeps the communities and regions' 5 minutes (below) out of it.
python3 tools/be_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS" 300)" || rc=$?
# The communities and regions (tools/be_regions.py, docs/belgium-regions-scope.md):
# the Flemish, Walloon, French Community (FWB), Brussels and COCOM parliaments
# into the ber_* tables, with the Flemish recorded votes, before the edition,
# which shows them in a "Communities and regions" section of their own. About
# 30 requests, 20 s on the laptop. Its failure (exit other than 0 or 3) is a
# [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  r=0
  python3 tools/be_regions.py --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")" || r=$?
  if [ "$r" -ne 0 ] && [ "$r" -ne 3 ]; then
    echo "  [gap] the communities and regions step failed (exit $r); last week's documents stand"
  fi
fi
# What was said and asked in the chamber (tools/be_chamber.py, parity layer 5):
# time-boxed to what is left of the hour, never fatal, skipped on GitHub.
bash tools/chamber_step.sh be "$SECONDS"
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py be || echo "  [gap] the week-ahead agenda step failed"
fi
# Petitions and consultations (tools/country_petitions.py, src/petitions.py):
# this country's open petitions, initiatives and consultations read into the
# store before the edition, which shows the new ones on our ground, the
# thresholds crossed and the deadlines. Its failure is a [gap] line, never
# the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_petitions.py be || echo "  [gap] the petitions step failed"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  # THE REVIEW WINDOW (src/edition_review.py, config/edition-review.yaml): with the
  # review on, --dm writes reviews/be-review-<date>.md instead of sending, and
  # jobs/edition-publish.sh sends the edition, honouring the review, at the window's end.
  if git ls-files --error-unmatch "editions/be-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/be_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/be_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Length of service (tools/member_service.py, src/member_service.py): every period each
# member has sat, from the Chamber's member list of each legislature (crawl-delay 5), every four weeks;
# (the tool skips a read that is not due), before the profiles and vote pages read it.
# A failure is a [gap] line; last run's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_service.py be \
    || echo "  [gap] member-service: be not fully read; last run's rows kept"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/be/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py be \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "${BE_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/be.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country be --send \
    || echo "  [gap] vote briefs failed for be; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "be-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "be-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/be_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc be \
  || echo "  [gap] country-briefs failed for be; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
