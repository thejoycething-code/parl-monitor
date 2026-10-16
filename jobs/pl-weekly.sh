#!/bin/bash
# Poland weekly: deputies, prints, legislative processes and recorded votes
# of the Sejm (tools/pl_rollcalls.py), then publish the raw archive and the
# store.
#
# Called by .github/workflows/pl-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh pl-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     PL_RECLASSIFY=true    re-derive every stored PL process's and vote's
#                           areas (and the sejmiki's acts), offline, before
#                           the pull (after config/taxonomy-pl.yaml or
#                           watchlist-pl changes)
#
# The first run backfills the 10th term: 66 sittings and 4,941 votes, one
# vote detail (every deputy's position) per request at one a second. The
# budget (45 minutes) stops it cleanly, newest first, and the next run
# resumes from the store, so the backfill is spread over two runs rather
# than hammering api.sejm.gov.pl in one.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
#
# THE EDITION (10 October 2026): after the collector, the Polish weekly
# edition (tools/pl_monitor.py, src/country_edition.py) is rendered to
# editions/pl-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions profiles briefs reviews
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Poland weekly}"
if [ "${PL_RECLASSIFY:-}" = "true" ]; then
  python3 tools/country_petitions.py pl --reclassify
  python3 tools/country_gov_docs.py pl --reclassify
  python3 tools/pl_rollcalls.py --reclassify
  python3 tools/pl_chamber.py --reclassify
  python3 tools/pl_regions.py --reclassify || echo "  [gap] the regional reclassify failed"
fi
rc=0
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
# The third argument keeps the sejmiki's 5 minutes (below) out of it.
python3 tools/pl_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS" 300)" || rc=$?
# What was said and asked in the chamber (tools/pl_chamber.py, parity layer 5):
# time-boxed to what is left of the hour, never fatal, skipped on GitHub.
bash tools/chamber_step.sh pl "$SECONDS"
# The voivodeship assemblies (tools/pl_regions.py, docs/poland-regions-scope.md,
# 13 October 2026): the sixteen sejmiki's acts from fifteen voivodeship
# journals (two JSON requests each) and thirteen sejmiki's own registers of
# resolutions (four until the second build the same day), into plr_acts
# before the edition, which shows them in a "Regional assemblies" section.
# Time-boxed to five minutes of what is left of the hour
# (tools/collector_budget.sh), robots.txt asked at run time; its failure or
# gaps are a [gap] line, never the run's. Measured from the laptop with the
# thirteen registers: 106 s for the first read, 74 s for a weekly one, so
# the five minutes stand.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/pl_regions.py --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")" \
    || echo "  [gap] pl-regions: the regional layer recorded gaps or failed; last run's rows stand"
fi
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py pl || echo "  [gap] the week-ahead agenda step failed"
fi
# Petitions and consultations (tools/country_petitions.py, src/petitions.py):
# this country's open petitions, initiatives and consultations read into the
# store before the edition, which shows the new ones on our ground, the
# thresholds crossed and the deadlines. Its failure is a [gap] line, never
# the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_petitions.py pl || echo "  [gap] the petitions step failed"
fi
# Government consultations and publications (tools/gov_docs_step.sh,
# tools/country_gov_docs.py, src/gov_docs.py, 16 October 2026): this
# country's government consultations and publications on our ground into
# gov_docs, before the edition, so the countdown's deadline rows are this
# week's. Never fatal: a source that failed is a [gap] line and a gaps row.
bash tools/gov_docs_step.sh pl
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  # THE REVIEW WINDOW (src/edition_review.py, config/edition-review.yaml): with the
  # review on, --dm writes reviews/pl-review-<date>.md instead of sending, and
  # jobs/edition-publish.sh sends the edition, honouring the review, at the window's end.
  if git ls-files --error-unmatch "editions/pl-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/pl_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/pl_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Member intelligence (tools/member_intel.py, src/member_intel.py): every committee with its members, one Sejm API request,
# into mi_groups / mi_interests before the profiles read them. A failure is a
# [gap] line; last week's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_intel.py pl \
    || echo "  [gap] member-intel: pl not fully read; last week's rows kept"
fi
# Length of service (tools/member_service.py, src/member_service.py): every period each
# member has sat, from the Sejm API's MP list of every term, every four weeks;
# (the tool skips a read that is not due), before the profiles and vote pages read it.
# A failure is a [gap] line; last run's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_service.py pl \
    || echo "  [gap] member-service: pl not fully read; last run's rows kept"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/pl/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py pl \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/pl.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country pl --send \
    || echo "  [gap] vote briefs failed for pl; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "pl-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "pl-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/pl_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc pl \
  || echo "  [gap] country-briefs failed for pl; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
