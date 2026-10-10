#!/bin/bash
# Netherlands weekly: the Tweede Kamer's fracties, members and every vote
# with every position (tools/nl_rollcalls.py), then publish the raw archive
# and the store.
#
# Called by .github/workflows/nl-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh nl-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     NL_RECLASSIFY=true    re-derive every stored NL zaak's and vote's areas,
#                           offline, before the pull (after Chris approves
#                           config/taxonomy-nl.yaml, or a watchlist-nl change)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero: a half-written
# store is not worth the divergence of a published store whose sidecar never
# got committed, and the next run re-reads whatever this one missed (the
# collector re-reads a six-week window every week).
#
# THE EDITION (10 October 2026): after the collector, the Dutch weekly
# edition (tools/nl_monitor.py, src/country_edition.py) is rendered to
# editions/nl-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions profiles
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Netherlands weekly}"
if [ "${NL_RECLASSIFY:-}" = "true" ]; then
  python3 tools/nl_rollcalls.py --reclassify
  python3 tools/nl_chamber.py --reclassify
fi
rc=0
python3 tools/nl_rollcalls.py --budget-seconds 2700 || rc=$?
# What was said and asked in the chamber (tools/nl_chamber.py, parity layer 5):
# time-boxed to what is left of the hour, never fatal, skipped on GitHub.
bash tools/chamber_step.sh nl "$SECONDS"
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py nl || echo "  [gap] the week-ahead agenda step failed"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/nl-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/nl_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/nl_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/nl/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py nl \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "nl-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "nl-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
