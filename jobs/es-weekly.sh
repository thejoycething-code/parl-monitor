#!/bin/bash
# Spain weekly: legislative initiatives, plenary votes with every deputy's
# position, and deputies of the Congreso de los Diputados
# (tools/es_rollcalls.py), the seventeen regional parliaments' layer
# (tools/es_regions.py), then publish the raw archive and the store.
#
# Called by .github/workflows/es-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh es-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     ES_RECLASSIFY=true    re-derive every stored ES initiative's and
#                           division's areas, and the regional layer's, offline,
#                           before the pull (after config/taxonomy-es.yaml or
#                           watchlist-es changes)
#
# The first run backfills the XV legislature: 146 voting days and about
# 3,000 vote files at one request a second. The budget (45 minutes) stops it
# cleanly and the next run resumes from the store, so the backfill is spread
# over two or three runs rather than hammering congreso.es in one.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
# mini_run: commit editions profiles briefs reviews
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Spain weekly}"
if [ "${ES_RECLASSIFY:-}" = "true" ]; then
  python3 tools/es_rollcalls.py --reclassify
  python3 tools/es_regions.py --reclassify
fi
rc=0
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
# The third argument keeps 300 s for the regional step below.
python3 tools/es_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS" 300)" || rc=$?
# The regional layer (tools/es_regions.py, docs/spain-regions-scope.md): the
# seventeen communities' laws from the BOE's open-data summaries and the bills
# in passage that Andalucía, Canarias, La Rioja, Cantabria and the Corts
# Valencianes list, into the esr_* tables, for the edition's "Regional
# parliaments" section. About a minute (one BOE request per issue since the
# last read, five list pages). Its failure or gaps are [gap] lines, never the
# run's: the Congreso's store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/es_regions.py --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")" \
    || echo "  [gap] es-regions: the regional layer recorded gaps or failed; last run's rows stand"
fi
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py es || echo "  [gap] the week-ahead agenda step failed"
fi
# Length of service (tools/member_service.py, src/member_service.py): every period each
# member has sat, from the Congreso's odsDiputados files, every four weeks;
# (the tool skips a read that is not due), before the profiles and vote pages read it.
# A failure is a [gap] line; last run's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_service.py es \
    || echo "  [gap] member-service: es not fully read; last run's rows kept"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/es/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py es \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/es.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country es --send \
    || echo "  [gap] vote briefs failed for es; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "es-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "es-rollcalls recorded gaps; publishing what it stored"
# Government consultations and publications (tools/gov_docs_step.sh,
# tools/country_gov_docs.py, src/gov_docs.py, 16 October 2026): this
# country's government consultations and publications on our ground into
# gov_docs, before the edition, so the countdown's deadline rows are this
# week's. Never fatal: a source that failed is a [gap] line and a gaps row.
bash tools/gov_docs_step.sh es
# The weekly edition (src/country_edition.py, tools/es_monitor.py), to Chris
# alone by DM, archived to editions/. Once a day: an edition already
# committed for today is rewritten, not resent. A failed render never stops
# the publish below.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
TODAY=$(date +%Y-%m-%d)
# THE REVIEW WINDOW (src/edition_review.py, config/edition-review.yaml): with the
# review on, --dm writes reviews/es-review-<date>.md instead of sending, and
# jobs/edition-publish.sh sends the edition, honouring the review, at the window's end.
if git ls-files --error-unmatch "editions/es-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/es_monitor.py --edition \
    || echo "  [gap] es-monitor: the edition failed to render; the store is still published"
else
  python3 tools/es_monitor.py --edition --dm \
    || echo "  [gap] es-monitor: the edition or its DM failed; the store is still published"
fi
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/es_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc es \
  || echo "  [gap] country-briefs failed for es; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
