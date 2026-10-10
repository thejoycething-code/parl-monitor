#!/bin/bash
# France weekly: deputies, dossiers legislatifs and scrutins of the
# Assemblee nationale (tools/fr_rollcalls.py), then publish the raw archive
# and the store.
#
# Called by .github/workflows/fr-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh fr-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     FR_RECLASSIFY=true    re-derive every stored FR dossier's and division's
#                           areas, offline, before the pull (after a taxonomy
#                           or watchlist-fr change), the Senat's included (FR5)
#
# THE SENAT (FR5, 10 October 2026): tools/fr_senat.py runs after the
# Assemblee's collector; it downloads data.senat.fr's Dosleg dump at most
# weekly and only when it changed, and otherwise does nothing.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
#
# THE EDITION (10 October 2026): after the collector, the French weekly
# edition (tools/fr_monitor.py, src/country_edition.py) is rendered to
# editions/fr-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions profiles
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when db_state.py publishes) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-France weekly}"
if [ "${FR_RECLASSIFY:-}" = "true" ]; then
  python3 tools/fr_rollcalls.py --reclassify
  python3 tools/fr_senat.py --reclassify
fi
rc=0
python3 tools/fr_rollcalls.py || rc=$?
# The Senat (FR5, 10 October 2026): data.senat.fr's Dosleg dump, downloaded
# at most weekly and only when it changed (a one-byte request reads its
# headers first), after the Assemblee so a Senate dossier can be joined to
# the Assemblee's. A gap (exit 3) is reported like the Assemblee's; a failure
# is logged and never stops the Assemblee's publish below.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  sr=0
  python3 tools/fr_senat.py || sr=$?
  if [ "$sr" -eq 3 ]; then
    rc=3
  elif [ "$sr" -ne 0 ]; then
    echo "  [gap] fr-senat failed (exit $sr); the Assemblee is still published"
  fi
fi
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py fr || echo "  [gap] the week-ahead agenda step failed"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; }; then
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/fr-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/fr_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/fr_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/fr/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py fr \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/fr.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country fr --send \
    || echo "  [gap] vote briefs failed for fr; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "fr-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "fr-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
