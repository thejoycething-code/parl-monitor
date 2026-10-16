#!/bin/bash
# US weekly: members, bills, House roll calls and Senate votes of the current
# Congress, the week ahead (floor lists and committee meetings, both
# chambers), the Federal Register's executive actions and the Supreme Court
# (9 October 2026), the fifty state legislatures (Open States, same day), the
# Congressional Record's floor speeches, the judge when US_JUDGE is on, then
# the edition and its DM.
#
# Called by .github/workflows/us-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh us-weekly. One script, two callers (docs/mac-mini.md).
# Both callers fetch the store first; this script publishes the raw archive
# and the store itself, and the caller commits data/ and editions/.
#
# SENATE.GOV REFUSES SOME NETWORKS. It answered 403 to every page from the
# laptop on Christopher's home connection (9 October 2026) and answers
# GitHub's runners. So the Senate half goes one of two ways:
#   * senate.gov answers this machine: everything runs here.
#   * it refuses (the Mini, if it shares that connection): the script asks
#     GitHub for a Senate-only run (us-weekly.yml, input senate_only), waits
#     for it to publish, fetches the store again and does the rest here with
#     --no-senate. If GitHub cannot be reached, the week goes ahead without
#     the new Senate votes and says so in a [gap] line.
#
# NEW JERSEY, MASSACHUSETTS AND MICHIGAN ANSWER ONLY GITHUB (13 October 2026;
# Christopher: "Add the GitHub step, skip NY"). Their legislatures time out
# or refuse UK networks and answer GitHub's US runners, so
# tools/us_states_github.py runs where they answer, on the Senate half's
# pattern above:
#   * they answer this machine (GitHub's own run): the step runs inline,
#     after the other state readers;
#   * they do not (the Mini): the same dispatch that asks GitHub for the
#     Senate half asks it for the states half too (us-weekly.yml input
#     states_github), at the START of the week, before this machine writes
#     anything, while the Mini holds its lock: one store writer at a time.
#     GitHub reads Open States for NJ, MA and MI, then the three
#     legislatures on top, and publishes the store; this machine fetches it
#     again and leaves those three states out of its own Open States step
#     (--exclude-states), so nothing it reads later wipes the same-day rows.
#     If GitHub cannot be reached, the week goes ahead with Open States alone
#     for the three and says so in a [gap] line.
#
# SPEAKS ONCE A DAY. An edition already committed for today means another
# run (the Mini, or a GitHub backup) has sent the DM: it is rewritten, not
# resent.
#
#     US_RECLASSIFY=true    re-derive stored areas first (taxonomy change)
#     US_SENATE_ONLY=true   the Senate-only half GitHub runs for the Mini
#     US_SENATE_CONGRESS=N  the Senate votes of Congress N only (GitHub, by
#                           hand: us-weekly.yml's `congress` input); implies
#                           US_SENATE_ONLY. US_SENATE_BUDGET=seconds (4500)
#     US_STATES_GITHUB=true the NJ/MA/MI states half GitHub runs for the Mini
#                           (with or without US_SENATE_ONLY; no edition)
#     US_RECORD_BUDGET=N    seconds for the Congressional Record step
#     US_JUDGE=on           score new items with the PAID API judge (read from
#                           the repo variable when unset and gh is available).
#                           The paid alternative, OFF: since 9 October 2026
#                           the free default is the session judge,
#                           jobs/us-session-judge.sh (Claude Code on the Mini,
#                           Fridays 19:30), which rewrites this edition with
#                           its scores. US_RESCORE stays with this paid path.
#
# THE CONGRESS COMES FROM THE DATE (src/us_store.congress_on): the 119th
# until 2 January 2027, the 120th from 3 January. For the first 45 days of a
# new Congress the previous one is collected too (CATCH_UP), so its last
# votes and its bills' final statuses still land; the edition then shows its
# unenacted bills as fallen. tools/us_schedule.py derives the Congress itself.
#
# mini_run: commit editions partner_site docs
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it, or
# tools/coverage.py would see this pipeline stop the day GitHub's backup skips.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-US weekly}"
LOG="${US_LOG_DIR:-/tmp}"
mkdir -p "$LOG"
read -r CONGRESS SESSION CATCH_UP <<<"$(python3 tools/us_rollcalls.py --print-congress)"
[ "$CATCH_UP" = "-" ] && CATCH_UP=
echo "US weekly: ${CONGRESS}th Congress, session $SESSION${CATCH_UP:+; catching up the ${CATCH_UP}th}"
SENATE_MENU="https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_${CONGRESS}_${SESSION}.xml"
# The DM goes to Christopher alone (9 October 2026). On the Mini the Slack
# token comes from ~/runner/env, as for Division watch.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
UA="parl-monitor (CitizenGO parliamentary monitor; thejoycething-code/parl-monitor)"

if [ "${US_RECLASSIFY:-}" = "true" ]; then
  python3 tools/us_rollcalls.py --reclassify | tee "$LOG/us-reclassify.log"
  python3 tools/us_federal_register.py --reclassify | tee -a "$LOG/us-reclassify.log"
  python3 tools/us_courts.py --reclassify | tee -a "$LOG/us-reclassify.log"
  # Narrows only: a widened net needs `tools/us_states.py --full` (bulk re-read).
  python3 tools/us_states.py --reclassify | tee -a "$LOG/us-reclassify.log"
fi

# The GitHub-only states (tools/us_states_github.py): which of their hosts
# this machine can reach decides whether the step runs here or on GitHub.
GH_STATES="nj,ma,mi"
gh_states_reach() {
  local u
  for u in https://pub.njleg.gov/votes/ https://malegislature.gov/robots.txt \
           https://www.legislature.mi.gov/Home/AutomatedDataCollectionPolicy; do
    curl -fsS -o /dev/null -m 20 -A "$UA" "$u" 2>/dev/null || return 1
  done
}
gh_states_half() {
  # Open States first for the three (their bulk files and top-up), then the
  # legislatures' own same-day rows on top (the weekly's order). Neither
  # stops the publish below.
  python3 tools/us_states.py --states "$GH_STATES" --budget-seconds 300 | tee "$LOG/us-states.log" \
    || echo "  [gap] the Open States read for NJ, MA and MI ended with gaps"
  python3 tools/us_states_github.py --budget-seconds "${1:-600}" | tee "$LOG/us-states-github.log" \
    || echo "  [gap] the GitHub states step (NJ, MA, MI) ended with gaps; Open States stands"
}

# An earlier Congress's Senate votes (US_SENATE_CONGRESS, the `congress`
# input of us-weekly.yml, 14 October 2026): senate.gov refuses the Mini, so
# only GitHub can read, say, the 118th Senate. Chris dispatches it by hand;
# it implies the Senate-only half and reads that Congress alone.
SENATE_CONGRESS="${US_SENATE_CONGRESS:-}"
if [ -n "$SENATE_CONGRESS" ]; then
  if ! [[ "$SENATE_CONGRESS" =~ ^[0-9]+$ ]] || [ "$SENATE_CONGRESS" -lt 101 ] \
     || [ "$SENATE_CONGRESS" -gt "$CONGRESS" ]; then
    echo "US_SENATE_CONGRESS must be a Congress number from 101 to $CONGRESS, not '$SENATE_CONGRESS'"
    exit 2
  fi
  US_SENATE_ONLY=true
fi

if [ "${US_SENATE_ONLY:-}" = "true" ] || [ "${US_STATES_GITHUB:-}" = "true" ]; then
  # The half GitHub runs for the Mini (or both halves in one run): what was
  # asked, then the raw archive and the store, and no edition.
  if [ -n "$SENATE_CONGRESS" ] && [ "$SENATE_CONGRESS" != "$CONGRESS" ]; then
    # Only the votes not yet stored are read, so a run cut short by its
    # budget resumes where it stopped (about 690 votes in a two-year
    # Congress). No week ahead: that is the current Congress's.
    rc=0
    python3 tools/us_rollcalls.py --congress "$SENATE_CONGRESS" --no-bills --no-rolls \
      --no-members --budget-seconds "${US_SENATE_BUDGET:-4500}" \
      | tee "$LOG/us-rollcalls-senate-$SENATE_CONGRESS.log" || rc=$?
    [ "$rc" -ne 0 ] && echo "  [gap] the ${SENATE_CONGRESS}th Senate read ended with gaps (exit $rc); what was read is published"
    python3 tools/raw_state.py --push
    python3 tools/db_state.py --push
    exit 0
  fi
  if [ "${US_SENATE_ONLY:-}" != "true" ]; then
    gh_states_half 600
    python3 tools/raw_state.py --push
    python3 tools/db_state.py --push
    exit 0
  fi
  if [ "${US_STATES_GITHUB:-}" = "true" ]; then gh_states_half 600; fi
  if [ -n "$CATCH_UP" ]; then
    python3 tools/us_rollcalls.py --congress "$CATCH_UP" --no-bills --no-rolls --no-members \
      --budget-seconds 600 | tee "$LOG/us-rollcalls-catch-up.log" \
      || echo "  [gap] Senate catch-up of the ${CATCH_UP}th Congress ended with gaps"
  fi
  python3 tools/us_rollcalls.py --congress "$CONGRESS" --no-bills --no-rolls --no-members \
    --budget-seconds 1500 | tee "$LOG/us-rollcalls.log"
  python3 tools/us_schedule.py --senate-only | tee "$LOG/us-schedule.log" \
    || echo "  [gap] the Senate week ahead stopped early; its gaps are in the store"
  python3 tools/raw_state.py --push
  python3 tools/db_state.py --push
  exit 0
fi

SENATE_ARGS=()
NEED_SENATE=false
NEED_STATES=false
# How the GitHub-only states go this week: here (inline), done by GitHub's
# half (github), or not at all (skipped, a [gap] line said why).
GH_STATES_MODE=inline
if ! curl -fsS -o /dev/null -m 30 -A "$UA" "$SENATE_MENU" 2>/dev/null; then
  echo "senate.gov refuses this machine; asking GitHub for the Senate half"
  SENATE_ARGS=(--no-senate)
  NEED_SENATE=true
fi
if [ -z "${GITHUB_ACTIONS:-}" ] && ! gh_states_reach; then
  echo "the New Jersey, Massachusetts or Michigan legislature does not answer this machine; asking GitHub for the states half"
  NEED_STATES=true
  GH_STATES_MODE=skipped
fi
if [ "$NEED_SENATE" = "true" ] || [ "$NEED_STATES" = "true" ]; then
  # One run for both halves (the Mini waits once), while the Mini holds its
  # lock: GitHub's run is the only store writer meanwhile (tools/github_half.sh).
  source tools/github_half.sh
  if github_half us-weekly.yml -f senate_only="$NEED_SENATE" -f states_github="$NEED_STATES"; then
    echo "GitHub published its half (senate $NEED_SENATE, states $NEED_STATES)"
    if [ "$NEED_STATES" = "true" ]; then GH_STATES_MODE=github; fi
  else
    if [ "$NEED_SENATE" = "true" ]; then echo "  [gap] Senate half on GitHub failed, never started or could not be asked for; this week has no new Senate votes"; fi
    if [ "$NEED_STATES" = "true" ]; then echo "  [gap] states half on GitHub failed, never started or could not be asked for; NJ, MA and MI rest on Open States this week"; fi
  fi
fi

if [ -n "$CATCH_UP" ]; then
  # The ended Congress, once a week for its first 45 days gone: final bill
  # statuses, late roll calls, and their amendment purposes.
  python3 tools/us_rollcalls.py --congress "$CATCH_UP" --no-members --budget-seconds 1200 \
    "${SENATE_ARGS[@]}" | tee "$LOG/us-rollcalls-catch-up.log" \
    || echo "  [gap] catch-up of the ${CATCH_UP}th Congress ended with gaps; the current one still runs"
fi
python3 tools/us_rollcalls.py --congress "$CONGRESS" --budget-seconds 2700 "${SENATE_ARGS[@]}" \
  | tee "$LOG/us-rollcalls.log" \
  || echo "  [gap] Congress step ended with gaps; what it stored stands"

# The week ahead, after the bills (its rows join us_bills for areas) and
# before the edition that prints it. Non-zero means a gap, recorded in the
# store and said in the edition; it never stops the week's edition.
python3 tools/us_schedule.py "${SENATE_ARGS[@]}" | tee "$LOG/us-schedule.log" \
  || echo "  [gap] the week ahead stopped early; the edition says what it has"

# The executive and the Court. Neither depends on the Congress: the Federal
# Register runs by publication date and the Court by its October Term, which
# tools/us_courts.py derives from the date. Neither stops the edition: a
# refused source is a [gap] line (and a gaps row), and the edition says what
# it holds. The Court's first run reads about 275 order PDFs (some 18
# minutes at robots.txt's one a second); its budget caps a run at 15 minutes
# and the rest are read the next week, unread files never marked read.
python3 tools/us_federal_register.py | tee "$LOG/us-federal-register.log" \
  || echo "  [gap] Federal Register step failed; this week's executive actions may be missing"
python3 tools/us_courts.py --budget-seconds 900 | tee "$LOG/us-courts.log" \
  || echo "  [gap] Supreme Court step failed; this week's opinions and grants may be missing"

# The fifty state legislatures (tools/us_states.py, 9 October 2026), through
# Open States, before the judge so state bills that moved can be scored.
# NO PAID TIER: the week is read from the per-session bulk files (keyless;
# Open States writes a new one nightly for every session that changed), and
# the free key spends two requests on the session list plus a top-up of the
# last day for live bills on our ground (about 70 to 90 in a sitting week).
# A ledger in the store keeps every run of a UTC day under 225 of the key's
# 250, so this and a backup run the same day cannot overrun. States not
# reached inside the budget go first next week (the rotation). 10 minutes on
# GitHub keeps the job's step budgets under its 120; 30 on the Mini.
# No OPENSTATES_API_KEY: one [gap] line and the step skips.
# US_STATES_FULL=true re-reads every current bulk file whole: after a
# taxonomy change that WIDENS the net (v1.20, 9 October 2026: 91 state bills
# newly on our ground were never stored), since --reclassify only narrows.
# Measured at 945 s for all 66 sessions, so it gets 30 minutes on GitHub too;
# the Record step after it takes only what the job has left.
STATES_ARGS=()
# GitHub's states half has read NJ, MA and MI from Open States and laid the
# legislatures' same-day rows on top: this run leaves those three out.
if [ "$GH_STATES_MODE" = "github" ]; then STATES_ARGS+=(--exclude-states "$GH_STATES"); fi
if [ "${US_STATES_FULL:-}" = "true" ]; then STATES_ARGS+=(--full); STATES_BUDGET=1800
elif [ -n "${GITHUB_ACTIONS:-}" ]; then STATES_BUDGET="${US_STATES_BUDGET:-600}"
else STATES_BUDGET="${US_STATES_BUDGET:-1800}"; fi
python3 tools/us_states.py --budget-seconds "$STATES_BUDGET" "${STATES_ARGS[@]}" | tee "$LOG/us-states.log" \
  || echo "  [gap] the state legislatures step ended with gaps; the edition says what it has"

# Alternative sources for the states (13 October 2026; Christopher: "We
# can't pay for Open States access so may need to explore alternatives
# whilst keeping the current tier we have"). AFTER the Open States step, so
# their same-day rows are merged on top of its (a day behind) and not wiped
# by it; Open States supersedes them once its own files catch up.
#  * tools/us_states_direct.py: Kansas (KLISS API), California (leginfo
#    daily change files) and Texas (the Legislative Council's FTP), no key.
#    Texas lists about 130 FTP directories (about 4 minutes) before reading
#    changed files; a run cut short says so and the rest go next week.
#  * tools/us_states_legiscan.py: every state, same day, on LegiScan's free
#    public key (LEGISCAN_API_KEY; unset, one line and it skips). DROPPED
#    13 October 2026 (Christopher: "Legiscan needs an API for each state so
#    look for other methods"): no key will be added; the step stays and skips. At most
#    1,500 queries a run and 9,000 a calendar month (ledger in the store).
# Next week's Open States top-up leaves out states a direct reader covered
# and, while LegiScan is active, tops up only watched and tier-1 bills.
if [ -n "${GITHUB_ACTIONS:-}" ]; then DIRECT_BUDGET=360; LEGISCAN_BUDGET=300
else DIRECT_BUDGET=900; LEGISCAN_BUDGET=900; fi
python3 tools/us_states_direct.py --budget-seconds "$DIRECT_BUDGET" | tee "$LOG/us-states-direct.log" \
  || echo "  [gap] the state feeds step (KS, CA, TX) ended with gaps; Open States stands"
python3 tools/us_states_legiscan.py --budget-seconds "$LEGISCAN_BUDGET" | tee "$LOG/us-states-legiscan.log" \
  || echo "  [gap] the LegiScan step ended with gaps; Open States stands"
# Other official routes (13 October 2026; Christopher: "Where states block
# find other routes", and LegiScan dropped the same day: "Legiscan needs an
# API for each state so look for other methods"). tools/us_states_routes.py:
# Pennsylvania's LDPC bill-history export (every bill, hourly, one 1.7 MB
# zip), the Missouri House's XML exports (Crawl-delay 20, so a capped number
# of bills on our ground a run) and Arkansas's bill pages (the days' moved
# bills, roll calls by name: Open States has no Arkansas votes). No key;
# robots.txt asked every run. docs/us-states-scope.md, "Other routes".
if [ -n "${GITHUB_ACTIONS:-}" ]; then ROUTES_BUDGET=300; ROUTES_ARGS=(--mo-max-files 10 --ar-max-bills 40)
else ROUTES_BUDGET=900; ROUTES_ARGS=(); fi
python3 tools/us_states_routes.py --budget-seconds "$ROUTES_BUDGET" "${ROUTES_ARGS[@]}" | tee "$LOG/us-states-routes.log" \
  || echo "  [gap] the state routes step (PA, MO, AR) ended with gaps; Open States stands"

# New Jersey, Massachusetts and Michigan (tools/us_states_github.py, 13
# October 2026; Christopher: "Add the GitHub step, skip NY"): after the other
# state readers, where those legislatures answer (GitHub's runners). On the
# Mini the dispatched GitHub half did it at the start of the week (above).
# Budgets: 5 minutes inline on GitHub, inside the 120 (the Record step below
# takes what is left); the dispatched half has 10.
case "$GH_STATES_MODE" in
  inline)
    python3 tools/us_states_github.py --budget-seconds 300 --ma-max-bills 40 --mi-max-bills 30 \
      | tee "$LOG/us-states-github.log" \
      || echo "  [gap] the GitHub states step (NJ, MA, MI) ended with gaps; Open States stands" ;;
  github)
    echo "us-states-github: done by GitHub's half this week (NJ, MA, MI)" | tee "$LOG/us-states-github.log" ;;
  *)
    echo "  [gap] us-states-github: NJ, MA and MI not read from their legislatures this week; Open States stands" \
      | tee "$LOG/us-states-github.log" ;;
esac

# The Congressional Record (phase 3a, 9 October 2026): floor speeches on our
# ground, before the judge (which scores them) and the edition (its Floor
# debate section). Keyed: without CONGRESS_API_KEY it is one [gap] line and
# the edition says what it already holds. The 119th Congress's backfill is
# about 20,000 granule pages at three or four a second, some 95 minutes; it
# drains newest first, so recent weeks are read first and the rest arrive
# over the following weeks.
#
# ITS BUDGET IS WHAT THE JOB HAS LEFT, not a fixed slice. It runs after every
# other collector, so the clock ($SECONDS) knows what they really took; it
# gets at most 10 minutes on GitHub and 15 on the Mini, and never more than
# the job's limit (GitHub 120 minutes, the Mini three hours) less 30 minutes
# for the judge and, for the edition and the store transfers, 10 on GitHub
# and 20 on the Mini (its store upload took 13 to 16 minutes on 10 and 11
# October 2026; tools/collector_budget.sh).
# Short of a minute, it skips this week and says so.
if [ -n "${GITHUB_ACTIONS:-}" ]; then JOB_LIMIT=7200; RECORD_MAX=600; TRANSFERS=600
else JOB_LIMIT="${JOB_TIMEOUT:-10800}"; RECORD_MAX=900; TRANSFERS=1200; fi
# The judge's half hour is always kept: on the Mini whether it runs is only
# known below, from the repo variable.
LEFT=$(( JOB_LIMIT - SECONDS - 1800 - TRANSFERS ))
RECORD_BUDGET="${US_RECORD_BUDGET:-$(( LEFT < RECORD_MAX ? LEFT : RECORD_MAX ))}"
if [ "$RECORD_BUDGET" -ge 60 ]; then
  python3 tools/us_record.py --budget-seconds "$RECORD_BUDGET" | tee "$LOG/us-record.log" \
    || echo "  [gap] Congressional Record step ended with gaps; the edition shows what the store holds"
else
  echo "  [gap] Congressional Record skipped: ${RECORD_BUDGET}s left in the job's budget" \
    | tee "$LOG/us-record.log"
fi

JUDGE="${US_JUDGE:-}"
if [ -z "$JUDGE" ] && [ -z "${GITHUB_ACTIONS:-}" ] && command -v gh >/dev/null 2>&1; then
  JUDGE=$(gh variable get US_JUDGE -R thejoycething-code/parl-monitor 2>/dev/null || true)
fi
if [ "$JUDGE" = "on" ]; then
  # US_RESCORE: space-separated keys to judge again on a human's say-so
  # ('119/hr/28', 'us_divisions:house-119-1-240'). Spend: announce it.
  if [ -n "${US_RESCORE:-}" ]; then
    python3 tools/us_triage.py --rescore $US_RESCORE --dry-run | tee "$LOG/us-triage-rescore.log" \
      || echo "  [gap] the rescore listing failed"
  fi
  # A judge gap must not cost the run: on 9 October 2026 one item the judge
  # could not parse (us_bills:119/s/48) exited 1 here, set -e stopped the
  # script before the publish below, and the reclassify, the states, the
  # Record and 204 paid scores were all thrown away with the runner.
  python3 tools/us_triage.py --limit 800 --budget-seconds 1800 | tee "$LOG/us-triage.log" \
    || echo "  [gap] the judge left items unscored; they are retried next run"
fi

# The 5CA sheets (tools/us_5ca.py, data/5ca/us-5ca-*.csv): offline, from the
# store just collected, seconds to run, as prov_5ca.py runs in the provinces
# weekly. They place members only from SIGNED readings in config/us_stance.yaml;
# until one is signed every sheet is an evidence list and says so.
python3 tools/us_5ca.py --all | tee "$LOG/us-5ca.log" \
  || echo "  [gap] the 5CA sheets failed; last week's stand"

# The vote tracker and member profiles (tools/make_us_votes.py ->
# partner_site/us-votes.html and docs/us-votes.html): offline, from the same
# store, seconds, AFTER the 5CA step because profiles show 5CA placements and
# both read config/us_stance.yaml the same way. Directions only from SIGNED
# readings; with none signed the page shows the record and labels nobody.
# The page is committed with this run; the partner site ships it at its next
# deploy (Monday publish's Deploy tracker deploys the committed partner_site/).
python3 tools/make_us_votes.py | tee "$LOG/us-votes.log" \
  || echo "  [gap] the US vote tracker failed to build; last week's page stands"

TODAY=$(date +%Y-%m-%d)
# Government consultations and publications (tools/gov_docs_step.sh,
# tools/country_gov_docs.py, src/gov_docs.py, 16 October 2026): this
# country's government consultations and publications on our ground into
# gov_docs, before the edition, so the countdown's deadline rows are this
# week's. Never fatal: a source that failed is a [gap] line and a gaps row.
bash tools/gov_docs_step.sh us
if git ls-files --error-unmatch "editions/us-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/us_monitor.py --edition | tee "$LOG/us-monitor.log" \
    || echo "  [gap] the edition failed to render"
else
  python3 tools/us_monitor.py --edition --dm | tee "$LOG/us-monitor.log" \
    || echo "  [gap] the edition or its DM failed"
fi

# The raw archive before the store: a store citing payloads the archive
# lacks is the worse failure. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
