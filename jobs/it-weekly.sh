#!/bin/bash
# Italy weekly: bills of both chambers, Senate and Camera votes, and every
# member's position on the votes on our ground (tools/it_rollcalls.py), then
# publish the raw archive and the store.
#
# Called by .github/workflows/it-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh it-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards. On the Mini, publishing is
# this script's own last step, as mini_run.sh requires; the workflow sets
# IT_PUBLISH=false and publishes in its own steps.
#
#     IT_RECLASSIFY=true    re-derive every stored IT bill's and division's
#                           areas, offline, before the pull (after the Italian
#                           taxonomy lands or watchlist-it changes); the
#                           regional councils' acts too (IT3)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero: a half-written
# store is not worth the divergence of a published store whose sidecar never
# got committed, and the next run re-reads whatever this one missed.
#
# THE SENATE'S AMENDMENT TEXTS (12 October 2026): after the regional councils,
# tools/it_senato_amendments.py (see its step below).
#
# THE EDITION (10 October 2026): after the collector, the Italian weekly
# edition (tools/it_monitor.py, src/country_edition.py) is rendered to
# editions/it-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions profiles briefs reviews
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Italy weekly}"
if [ "${IT_RECLASSIFY:-}" = "true" ]; then
  python3 tools/country_petitions.py it --reclassify
  python3 tools/it_rollcalls.py --reclassify
  python3 tools/it_regions.py --reclassify || echo "  [gap] the regional reclassify failed"
fi
rc=0
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
# The third argument keeps the regional councils' 5 minutes and the Senate
# amendment texts' 5 minutes (below) out of it.
python3 tools/it_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS" 600)" || rc=$?
# The regional councils (IT3, tools/it_regions.py, docs/italy-regions-scope.md):
# Lombardia, Campania, Marche and the Provincia autonoma di Trento into
# it_reg_acts, before the edition, which shows them in a section of their own.
# About twenty requests. Its failure (exit other than 0 or 3) is a [gap] line,
# never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  r=0
  python3 tools/it_regions.py --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")" || r=$?
  if [ "$r" -ne 0 ] && [ "$r" -ne 3 ]; then
    echo "  [gap] the regional councils step failed (exit $r); last week's acts stand"
  fi
fi
# The Senate's amendment texts (12 October 2026, tools/it_senato_amendments.py,
# src/it_amendments.py): for the Senate acts with votes on our ground, the
# amendment and order-of-the-day files from the Senate's own GitHub
# repository (AkomaNtosoBulkData) into it_senate_amendments, each vote linked
# to its text, so the 5CA drafts, the amendment worklist and the session
# judge's queue carry the text. One git trees API request per act due and
# raw files only when new or changed (GitHub's anonymous 60 an hour; a
# GITHUB_TOKEN already in the runner's environment is used if present).
# After the collector, so this week's votes are linked. Its failure (exit
# other than 0 or 3) is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  r=0
  python3 tools/it_senato_amendments.py --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")" || r=$?
  if [ "$r" -ne 0 ] && [ "$r" -ne 3 ]; then
    echo "  [gap] the Senate amendment texts step failed (exit $r); last week's texts stand"
  fi
fi
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py it || echo "  [gap] the week-ahead agenda step failed"
fi
# Petitions and consultations (tools/country_petitions.py, src/petitions.py):
# this country's open petitions, initiatives and consultations read into the
# store before the edition, which shows the new ones on our ground, the
# thresholds crossed and the deadlines. Its failure is a [gap] line, never
# the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_petitions.py it || echo "  [gap] the petitions step failed"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; }; then
  TODAY=$(date +%Y-%m-%d)
  # THE REVIEW WINDOW (src/edition_review.py, config/edition-review.yaml): with the
  # review on, --dm writes reviews/it-review-<date>.md instead of sending, and
  # jobs/edition-publish.sh sends the edition, honouring the review, at the window's end.
  if git ls-files --error-unmatch "editions/it-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/it_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/it_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Member intelligence (tools/member_intel.py, src/member_intel.py): the Camera's organ memberships, dati.camera.it SPARQL,
# into mi_groups / mi_interests before the profiles read them. A failure is a
# [gap] line; last week's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_intel.py it \
    || echo "  [gap] member-intel: it not fully read; last week's rows kept"
fi
# Length of service (tools/member_service.py, src/member_service.py): every period each
# member has sat, from dati.camera.it SPARQL, one query a legislature, every four weeks;
# (the tool skips a read that is not due), before the profiles and vote pages read it.
# A failure is a [gap] line; last run's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_service.py it \
    || echo "  [gap] member-service: it not fully read; last run's rows kept"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/it/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py it \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/it.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country it --send \
    || echo "  [gap] vote briefs failed for it; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "it-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "it-rollcalls recorded gaps; they are in the gaps table and the log"
# On GitHub the workflow publishes in steps of its own (IT_PUBLISH=false).
if [ "${IT_PUBLISH:-true}" = "false" ]; then
  exit 0
fi
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/it_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc it \
  || echo "  [gap] country-briefs failed for it; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
