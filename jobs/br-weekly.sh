#!/bin/bash
# Brazil weekly: members, nominal votes of the Câmara dos Deputados and the
# Senado Federal with every position, and the bills they are about
# (tools/br_rollcalls.py), the state assemblies (tools/br_states.py), then
# publish the raw archive and the store.
#
# Called by .github/workflows/br-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh br-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     BR_RECLASSIFY=true    re-derive every stored BR bill's and division's
#                           areas, offline, before the pull (after a
#                           watchlist-br change, or once taxonomy-pt exists),
#                           and the state assemblies' bills (tools/br_states.py)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero: a half-written
# store is not worth the divergence of a published store whose sidecar never
# got committed, and the next run re-reads whatever this one missed.
#
# THE EDITION (10 October 2026): after the collector, the Brazilian weekly
# edition (tools/br_monitor.py, src/editions/br.py on
# src/country_edition.py) is rendered to editions/br-monitor-<date>.md and
# DMed to Chris alone. Once a day: an edition already committed for today
# is rewritten, not resent. Its failure is a [gap] line and never costs the
# store.
#
# SANTA CATARINA ANSWERS ONLY GITHUB (13 October 2026; Chris: include it in
# the GitHub-side step). ALESC's e-Legis portal answers GitHub's runners and
# not the Mini, so tools/br_states.py's `sc` source runs where it answers, on
# the US Senate half's pattern (tools/github_half.sh): inline on GitHub's own
# run; on the Mini, a GitHub run of this workflow with states_github=true,
# asked for at the START of the week before anything is written, while the
# Mini holds its lock (one store writer at a time). The Mini then fetches the
# store again and leaves `sc` out of its own state-assemblies step. Mato
# Grosso is not read (its report pages and filters only under /proposicao?,
# which robots.txt disallows; its API needs OAuth credentials).
#
#     BR_STATES_GITHUB=true the GitHub-only state sources (sc) only, published,
#                           no edition: the half GitHub runs for the Mini
#
# mini_run: commit editions profiles briefs reviews
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Brazil weekly}"
BR_GH_SOURCES=sc
if [ "${BR_STATES_GITHUB:-}" = "true" ]; then
  # The half GitHub runs for the Mini: the GitHub-only sources, then the raw
  # archive and the store. br_states.py exits 3 on gaps: still published.
  python3 tools/br_states.py --sources "$BR_GH_SOURCES" --budget-seconds 600 \
    || echo "  [gap] br-states: the GitHub-only sources ($BR_GH_SOURCES) recorded gaps or failed"
  python3 tools/raw_state.py --push
  python3 tools/db_state.py --push
  exit 0
fi
# Where the GitHub-only sources are read this week: here (GitHub's own run),
# by GitHub's half (asked for now, before this machine writes anything), or
# not at all (a [gap] line says so).
BR_STATES_ARGS=()
if [ -z "${GITHUB_ACTIONS:-}" ] \
   && ! curl -fsS -o /dev/null -m 20 -A "parl-monitor (CitizenGO parliamentary monitor)" \
        https://portalelegis.alesc.sc.gov.br/proposicoes/processo-legislativo 2>/dev/null; then
  echo "ALESC (Santa Catarina) does not answer this machine; asking GitHub for the states half"
  BR_STATES_ARGS=(--exclude-sources "$BR_GH_SOURCES")
  source tools/github_half.sh
  if github_half br-weekly.yml -f states_github=true; then
    echo "GitHub published the GitHub-only state sources ($BR_GH_SOURCES)"
  else
    echo "  [gap] br-states: GitHub's half failed, never started or could not be asked for; Santa Catarina is not read this week"
  fi
fi
if [ "${BR_RECLASSIFY:-}" = "true" ]; then
  python3 tools/country_petitions.py br --reclassify
  python3 tools/country_gov_docs.py br --reclassify
  python3 tools/br_rollcalls.py --reclassify
  python3 tools/br_chamber.py --reclassify
  python3 tools/br_states.py --reclassify
fi
rc=0
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
# The third argument keeps 600 s for the state-assemblies step below.
python3 tools/br_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS" 600)" || rc=$?
# The state assemblies (tools/br_states.py, docs/brazil-regions-scope.md): the
# bills, stages and published votes of ALESP (open-data files), ALMG (its
# open-data API since 15 October 2026, never paging; its bill search as fallback), ALERJ (its Notes view) and the SAPL houses (Acre, Alagoas,
# Amazonas, Paraíba, Piauí, Rondônia, Tocantins; Roraima and Maranhão tried),
# and, by the alternative routes of 13 October 2026, ALRN, ALECE, ALEPE and
# ALEPA's bills from their own data on other hosts and the laws Paraná and
# Goiás publish (the Casa Civil's legislation portals; about a minute in all),
# into the brs_* tables, for the edition's "State assemblies" section. The
# sources are read in parallel; every SAPL robots.txt asks a minute between
# requests, so the step takes its whole budget when the houses have news.
# Its failure or gaps are [gap] lines, never the run's: the Congress's store
# is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/br_states.py --budget-seconds "$(bash tools/collector_budget.sh 600 "$SECONDS")" "${BR_STATES_ARGS[@]}" \
    || echo "  [gap] br-states: the state assemblies recorded gaps or failed; last run's rows stand"
fi
# What was said and asked in the chamber (tools/br_chamber.py, parity layer 5):
# time-boxed to what is left of the hour, never fatal, skipped on GitHub.
bash tools/chamber_step.sh br "$SECONDS"
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py br || echo "  [gap] the week-ahead agenda step failed"
fi
# Petitions and consultations (tools/country_petitions.py, src/petitions.py):
# this country's open petitions, initiatives and consultations read into the
# store before the edition, which shows the new ones on our ground, the
# thresholds crossed and the deadlines. Its failure is a [gap] line, never
# the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_petitions.py br --detail-limit 15 || echo "  [gap] the petitions step failed"
fi
# Government consultations and publications (tools/gov_docs_step.sh,
# tools/country_gov_docs.py, src/gov_docs.py, 16 October 2026): this
# country's government consultations and publications on our ground into
# gov_docs, before the edition, so the countdown's deadline rows are this
# week's. Never fatal: a source that failed is a [gap] line and a gaps row.
bash tools/gov_docs_step.sh br
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  # THE REVIEW WINDOW (src/edition_review.py, config/edition-review.yaml): with the
  # review on, --dm writes reviews/br-review-<date>.md instead of sending, and
  # jobs/edition-publish.sh sends the edition, honouring the review, at the window's end.
  if git ls-files --error-unmatch "editions/br-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/br_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/br_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Member intelligence (tools/member_intel.py, src/member_intel.py): fronts on our ground weekly, the rest in rotation; organs from one bulk file,
# into mi_groups / mi_interests before the profiles read them. A failure is a
# [gap] line; last week's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_intel.py br \
    || echo "  [gap] member-intel: br not fully read; last week's rows kept"
fi
# Attendance (tools/country_attendance.py, src/attendance.py): the Câmara's presence register (eventosPresencaDeputados, committees and the plenary's deliberative sessions) and the tramitações of the bills on our ground,
# into att_sittings / att_marks / att_referrals before the profiles read them. A failure is a
# [gap] line; last week's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_attendance.py br \
    || echo "  [gap] attendance: br not fully read; last week's rows kept"
fi
# Length of service (tools/member_service.py, src/member_service.py): every period each
# member has sat, from the Câmara's historico and the Senado's mandatos, a request a member, every four weeks, 25-minute budget;
# (the tool skips a read that is not due), before the profiles and vote pages read it.
# A failure is a [gap] line; last run's rows stand and the store is still published.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_service.py br \
    || echo "  [gap] member-service: br not fully read; last run's rows kept"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/br/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py br \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/br.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country br --send \
    || echo "  [gap] vote briefs failed for br; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "br-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "br-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/br_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc br \
  || echo "  [gap] country-briefs failed for br; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
