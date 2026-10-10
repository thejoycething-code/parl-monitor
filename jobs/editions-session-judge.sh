#!/bin/bash
# Country editions and Latam session judge on the Mac Mini
# (tools/mini_run.sh editions-session-judge, Sundays 16:45 London, after the
# last of the week's country weeklies: the Saturday European and Latin
# American ones and Sunday's Uruguay, Dominican Republic, El Salvador,
# Bolivia and Honduras).
#
# THE FREE JUDGE (Chris, 10 October 2026; docs/country-decisions-2026-10-10.md,
# X16 and "The free session judge"): Claude Code on the Mini, signed in to
# Chris's claude.ai account, scores the fifteen country editions' and the
# Latam monitor's pending items on the plan allowance, not the API
# (tools/session_judge.sh, tools/edition_judge.py --queue-out / --queue-in).
# The paid AI judge stays off.
#
# LEAN ON THE PLAN, which Chris's other scheduled jobs share: ONE job a week
# for all sixteen, at most SESSION_JUDGE_MAX items (100) in sessions of 25,
# in one priority order across countries (watched, then tier 1, then tier 2,
# newest first).
#
# MINI ONLY, NO GITHUB WORKFLOW: the CLI and the subscription live here. Its
# heartbeat is its own ("Editions session judge", tools/coverage.py
# ON_DEMAND), and a failure DMs through mini_run.sh.
#
# Order: score; rewrite in place the editions of the countries scored today
# (the latest edition of each, within its cadence; the Latam edition when
# under a week old), with ONE DM to Chris only when the scores changed what
# leads an edition already sent; the Latam alert pass for every country, so
# the tier-1 items held for the judge go out now if it scored them 2 or 3;
# then the raw archive and the store. When claude is missing or not signed
# in, a [gap] line and a clean exit: nothing is touched or published.
#
# THE 5CA STANCE STEPS (10 October 2026; src/country5ca.py, docs/5ca-notes.md
# "The new country editions"), first and offline, seconds to run: draft
# config/<cc>_stance.yaml entries for the week's new watched and tier-1 votes
# in every new country (by rules, no AI; nothing is ever confirmed here),
# rewrite each docs/5ca-<cc>-readings.md keeping any ticks not yet applied,
# write the 5CA sheets from CONFIRMED readings only (data/5ca/<cc>-5ca-*.csv),
# then the weekly "stances awaiting sign-off" digest, one DM to Chris, once
# per ISO week (tools/stance_digest.py). A failure is a [gap] line; the
# judge still runs. They read the store and write no table, so they need no
# publish of their own.
#
# mini_run: commit editions config docs
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Editions session judge}"
export PYTHONUNBUFFERED=1
# The DMs go to Chris alone (the tools also force his id).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"

python3 tools/country_5ca.py --all-countries --draft --signoff-doc --sheets \
  || echo "  [gap] the 5CA stance step failed for a country; the others stand"
python3 tools/stance_digest.py --dm || echo "  [gap] the stance digest DM failed; next week's covers it"

rc=0
bash tools/session_judge.sh tools/edition_judge.py "${SESSION_JUDGE_MAX:-100}" 25
jrc=$?
if [ "$jrc" -eq 3 ]; then
  exit 0                      # a gap, already logged; nothing to publish
fi
[ "$jrc" -eq 0 ] || rc=1

# The week's editions, rewritten with the scores; one DM only if a lead changed.
python3 tools/edition_judge.py --rerender --dm || { echo "  [gap] the rewrite failed"; rc=1; }

# The Latam alerts, every country: releases what was held for the judge.
python3 tools/latam_alerts.py --send || echo "  [gap] latam-alerts failed; the next country run retries"

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
