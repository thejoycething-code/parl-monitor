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
#                           areas, offline, before the pull (after
#                           config/taxonomy-pl.yaml or watchlist-pl changes)
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
# mini_run: commit editions profiles
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Poland weekly}"
if [ "${PL_RECLASSIFY:-}" = "true" ]; then
  python3 tools/pl_rollcalls.py --reclassify
fi
rc=0
python3 tools/pl_rollcalls.py --budget-seconds 2700 || rc=$?
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py pl || echo "  [gap] the week-ahead agenda step failed"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/pl-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/pl_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/pl_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/pl/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py pl \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "pl-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "pl-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
