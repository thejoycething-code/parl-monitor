#!/bin/bash
# Australia weekly: members, bills and House and Senate divisions of the
# Federal Parliament (tools/au_rollcalls.py), the week ahead
# (tools/au_schedule.py), speeches on our ground (tools/au_debates.py), the
# states and territories (tools/au_states.py), the judge when AU_JUDGE is on,
# the edition and its DM to Christopher (tools/au_monitor.py), then (on the
# Mini) publish the raw archive and the store.
#
# Called by .github/workflows/au-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh au-weekly. One script, two callers. Both callers fetch
# the store first and commit data/, editions/, partner_site/ and docs/
# afterwards.
#
#     AU_RECLASSIFY=true    re-derive every stored AU bill's and division's
#                           areas, offline, before the pull (after a taxonomy
#                           or watchlist-au change), the states' too
#                           (watchlist-au-states)
#     AU_JUDGE=on           score new items with the PAID API judge (SPEND
#                           NEEDS A YES; read from the repo variable when unset
#                           and gh is available). The paid alternative, OFF:
#                           since 9 October 2026 the free default is the
#                           session judge, jobs/au-session-judge.sh (Claude
#                           Code on the Mini, Fridays 03:10), which rewrites
#                           this edition with its scores.
#     AU_PUBLISH=false      collect and write the edition only. The GitHub workflow sets it and
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
# AU_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
#
# SPEAKS ONCE A DAY. An edition already committed for today means another
# run (the Mini, or a GitHub backup) has sent the DM: it is rewritten, not
# resent, as jobs/us-weekly.sh does.
#
# mini_run: commit editions partner_site docs
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Australia weekly}"
# The DM goes to Christopher alone (decided 9 October 2026). On the Mini the
# Slack token comes from ~/runner/env, as for Division watch.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "${AU_RECLASSIFY:-}" = "true" ]; then
  python3 tools/au_rollcalls.py --reclassify
  python3 tools/au_states.py --reclassify || echo "  [gap] the states reclassify failed"
fi
rc=0
# The collector's budget is what the job's limit leaves after the publish and
# the later steps, at most 45 minutes (tools/collector_budget.sh): a fixed
# budget plus the Mini's 15-minute store upload overran the hour (10 October).
# The third argument keeps the debates' 10 minutes and the states' 8 (below).
python3 tools/au_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS" 1080)" || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "au-rollcalls failed (exit $rc); no edition, nothing published"
  exit "$rc"
fi

# The week ahead (tools/au_schedule.py): the Register's open-for-disallowance
# list and the Handbook's Parliaments, a few requests, about 20 seconds. After
# the collector, because an instrument joins its enabling Act's bill through
# au_bills. A failure is a gap, never a lost edition: the edition then says
# when the week ahead was last read, or that it never was.
python3 tools/au_schedule.py || echo "  [gap] au-schedule exited non-zero; Coming up shows the last read"

# Debates (tools/au_debates.py): speeches on our ground from the same day
# files, after the collector so au_offices knows every speaker. Newest days
# first under a 10-minute budget (the workflow allows 60 minutes in all):
# the 48th Parliament's backfill (158 day files, about 8 s each) drains over
# three runs, then a sitting week is about a minute. A failure is a gap: the
# days it missed are read next run.
python3 tools/au_debates.py --budget-seconds 600 || echo "  [gap] au-debates exited non-zero; unread days wait for next week"

# The states and territories (tools/au_states.py, docs/australia-states-scope.md,
# 13 October 2026): each state's bills with their stage, Acts, and divisions
# with every member's vote (New South Wales from its Hansard API; Victoria,
# South Australia, Tasmania and the ACT from their Votes and Proceedings,
# Minutes or Hansard records, added the same day), into the aus_* tables, for
# the edition's States and territories section. Twelve sources, robots.txt
# asked at run time; the budget went from 5 to 8 minutes for the four records
# sources, each capped per run, whose first backfill and NSW's drain newest
# first over a few weekly runs. Exit 3 is gaps recorded, never a lost
# edition: last week's rows stand.
python3 tools/au_states.py --budget-seconds "$(bash tools/collector_budget.sh 480 "$SECONDS")" \
  || echo "  [gap] au-states: the states layer recorded gaps or failed; last week's rows stand"

JUDGE="${AU_JUDGE:-}"
if [ -z "$JUDGE" ] && [ -z "${GITHUB_ACTIONS:-}" ] && command -v gh >/dev/null 2>&1; then
  JUDGE=$(gh variable get AU_JUDGE -R thejoycething-code/parl-monitor 2>/dev/null || true)
fi
if [ "$JUDGE" = "on" ]; then
  python3 tools/au_triage.py --limit 800 --budget-seconds 1800 || echo "  [gap] au-triage exited non-zero; unscored items wait for next week"
else
  python3 tools/au_triage.py --dry-run
fi

# The 5CA sheets (tools/au_5ca.py, data/5ca/au-5ca-*.csv): offline, from the
# store just collected, as prov_5ca.py runs in the provinces weekly. Only
# SIGNED readings in config/au_stance.yaml place anyone. A failure is a gap,
# never a lost week.
python3 tools/au_5ca.py --all || echo "  [gap] the 5CA sheets failed; last week's stand"

# The vote tracker and member profiles (tools/make_au_votes.py ->
# partner_site/au-votes.html and docs/au-votes.html): offline, from the same
# store, seconds, AFTER the 5CA step because profiles show 5CA placements and
# both read config/au_stance.yaml the same way. Directions only from SIGNED
# readings; with none signed the page shows the record and labels nobody.
# Committed with this run; the partner site ships it at its next deploy.
python3 tools/make_au_votes.py \
  || echo "  [gap] the Australian vote tracker failed to build; last week's page stands"

TODAY=$(date +%Y-%m-%d)
# Government consultations and publications (tools/gov_docs_step.sh,
# tools/country_gov_docs.py, src/gov_docs.py, 16 October 2026): this
# country's government consultations and publications on our ground into
# gov_docs, before the edition, so the countdown's deadline rows are this
# week's. Never fatal: a source that failed is a [gap] line and a gaps row.
bash tools/gov_docs_step.sh au
if git ls-files --error-unmatch "editions/au-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/au_monitor.py --edition
else
  python3 tools/au_monitor.py --edition --dm
fi

if [ "${AU_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "au-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
