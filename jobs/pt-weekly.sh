#!/bin/bash
# Portugal weekly: deputies, initiatives and plenary votes of the Assembleia
# da Republica (tools/pt_rollcalls.py), then publish the raw archive and the
# store.
#
# Called by .github/workflows/pt-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh pt-weekly. One script, two callers (the jobs/au-weekly.sh
# pattern). Both callers fetch the store first and commit data/ afterwards.
#
#     PT_RECLASSIFY=true    re-derive every stored PT initiative's and vote's
#                           areas, offline, before the pull (after a taxonomy
#                           or watchlist-pt change, and the day
#                           config/taxonomy-pt.yaml first lands)
#     PT_PUBLISH=false      collect only. The GitHub workflow sets it and
#                           publishes in its own steps, under the same
#                           condition as its commit step. On the Mini,
#                           publishing is this script's last step, as
#                           mini_run.sh requires.
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (the deputies file failed but the initiatives were read):
# that run is still published, and this script exits 0 so mini_run.sh
# commits the sidecars with it. Exit 1 (no initiatives read) or anything else
# publishes NOTHING and exits non-zero; next week re-reads the whole
# legislature anyway. With PT_PUBLISH=false the collector's exit code is
# passed straight through, so a gap turns the GitHub step red and the
# failure alert hears of it.
#
# THE EDITION (10 October 2026): after the collector, the Portuguese weekly
# edition (tools/pt_monitor.py, src/country_edition.py) is rendered to
# editions/pt-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions profiles briefs reviews
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Portugal weekly}"
if [ "${PT_RECLASSIFY:-}" = "true" ]; then
  python3 tools/country_petitions.py pt --reclassify
  python3 tools/pt_rollcalls.py --reclassify
  python3 tools/pt_chamber.py --reclassify
fi
rc=0
# PT6 (10 October 2026): PT_LEGISLATURE=XV or XVI reads that legislature's
# files instead of the current one (the backfill, dispatched from CI).
leg=()
case "${PT_LEGISLATURE:-}" in
  "") ;;
  XV|XVI|XVII) leg=(--legislature "$PT_LEGISLATURE") ;;
  *) echo "pt-weekly: unknown legislature '${PT_LEGISLATURE}'"; exit 2 ;;
esac
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
python3 tools/pt_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS")" "${leg[@]}" || rc=$?
# X8 (10 October 2026): the Tribunal Constitucional's acórdãos
# (tools/pt_courts.py): 30 s between requests, at most ten rulings read, so
# about six minutes; a 429 ends it with one gap. Not on a backfill run.
# Gaps go to the store; a failure never stops the run.
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ -z "${PT_LEGISLATURE:-}" ]; then
  python3 tools/pt_courts.py \
    || echo "  [gap] pt-courts recorded gaps or failed; the next run retries"
fi
# What was said and asked in the chamber (tools/pt_chamber.py, parity layer 5):
# time-boxed to what is left of the hour, never fatal, skipped on GitHub and
# on a backfill run (PT_LEGISLATURE set).
if [ -z "${PT_LEGISLATURE:-}" ]; then
  bash tools/chamber_step.sh pt "$SECONDS"
fi
# What a vote is ON, not just its title (16 October 2026, tools/amendment_text.py,
# src/amendtext_pt.py): for votes whose titles only name an amendment, motion or
# order of the day, the proposals papers among the initiative's annexes in the Iniciativas dump, matched with the country's taxonomy; a tier-1 term in
# the text's purpose adds its areas to the vote (amendment_text). After the
# collector and any reclassify, because it re-applies every cached match the
# collector's upsert reset. New reads within its budget; the rest wait a week.
# Its failure (exit other than 0 or 3) is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  r=0
  python3 tools/amendment_text.py --cc pt --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")" || r=$?
  if [ "$r" -ne 0 ] && [ "$r" -ne 3 ]; then
    echo "  [gap] the amendment text step failed (exit $r); last week's reads stand"
  fi
fi
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py pt || echo "  [gap] the week-ahead agenda step failed"
fi
# Petitions and consultations (tools/country_petitions.py, src/petitions.py):
# this country's open petitions, initiatives and consultations read into the
# store before the edition, which shows the new ones on our ground, the
# thresholds crossed and the deadlines. Its failure is a [gap] line, never
# the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_petitions.py pt || echo "  [gap] the petitions step failed"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM; nor on a backfill run,
# PT_LEGISLATURE set).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ -z "${PT_LEGISLATURE:-}" ]; then
  TODAY=$(date +%Y-%m-%d)
  # THE REVIEW WINDOW (src/edition_review.py, config/edition-review.yaml): with the
  # review on, --dm writes reviews/pt-review-<date>.md instead of sending, and
  # jobs/edition-publish.sh sends the edition, honouring the review, at the window's end.
  if git ls-files --error-unmatch "editions/pt-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/pt_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/pt_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Length of service (tools/member_service.py, src/member_service.py): every period each
# member has sat, from InformacaoBase for every legislature, every four weeks;
# (the tool skips a read that is not due), before the profiles and vote pages read it.
# A failure is a [gap] line; last run's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_service.py pt \
    || echo "  [gap] member-service: pt not fully read; last run's rows kept"
fi
# Plenary attendance (tools/country_attendance.py, src/attendance.py; 11 October
# 2026): the Assembleia's roll for each plenary sitting of the XVII legislature
# (parlamento.pt "Presenças às Reuniões Plenárias", an HTML page per sitting,
# about 2 s each), into att_sittings / att_marks before the profiles read them.
# Each run reads the new sittings and those of the last three weeks again (a
# Falta is justified later), at most 40 rolls and 5 minutes of what the hour
# leaves (tools/collector_budget.sh): the first runs backfill the legislature's
# 119 sittings 40 at a time, three weeks. Not on a backfill run (PT_LEGISLATURE
# set). A failure is a [gap] line; last week's rows stand and the store is
# still published.
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ -z "${PT_LEGISLATURE:-}" ]; then
  python3 tools/country_attendance.py pt --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")" \
    || echo "  [gap] attendance: pt not fully read; last week's rows kept"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/pt/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py pt \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "${PT_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/pt.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country pt --send \
    || echo "  [gap] vote briefs failed for pt; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "pt-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "pt-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/pt_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc pt \
  || echo "  [gap] country-briefs failed for pt; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
