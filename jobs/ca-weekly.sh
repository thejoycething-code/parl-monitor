#!/bin/bash
# Canada weekly on the Mac Mini (tools/mini_run.sh ca-weekly, Tuesdays 11:00 London).
# .github/workflows/ca-weekly.yml is the backup and skips itself when this has run
# (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW'S SCHEDULED RUN, IN ITS ORDER
# (tests/test_mini_jobs.py holds the two together). As there, every step runs whatever the one before did.
# Whatever was gathered is published, as the workflow's guarded publish
# steps do.
# The dispatch-only backfills and repairs stay on GitHub. The petition
# judge no longer spends (paid AI off, 16 October 2026): without
# CA_TRIAGE_PAID=1 it leaves its rows to the free session judge
# (jobs/prov-session-judge.sh, Wednesdays 16:15). Then
# the edition and its DM (tools/ca_monitor.py), committed with the state.
#
# 16 October 2026 (branch ca-gaps): the shared country frameworks reach
# Canada through a reader adapter (src/editions/ca.py): the week ahead
# (tools/country_agenda.py ca, before the edition, which renders it as This
# week and Further afield), member profiles (profiles/ca/, committed) and the
# same-day vote briefs after the collectors (data/vote-briefs/ca.json; the
# daily job briefs the House's divisions the day they are taken). The vote
# pages, tracker and bill timelines are rebuilt for every country by the
# Sunday editions-session-judge job (tools/make_country_votes.py), Canada
# included: no step here.
#
# mini_run: commit editions profiles
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Canada weekly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
python3 tools/ca_rollcalls.py --session 45-1 || rc=1
python3 tools/ca_senate.py --session 45-1 || rc=1
python3 tools/ca_hansard.py --session 45-1 || rc=1
python3 tools/ca_senate_debates.py --session 45-1 --budget-seconds 900 || rc=1
# Committee evidence (tools/ca_committees.py): House and joint committee
# meetings of the key nine, members' interventions to ca_speeches, witnesses
# only to ca_testimony. Budget-aware since 12 October 2026: at most 20
# minutes, less if the steps before it overran, keeping the judge's 20 and
# the publish (tools/collector_budget.sh; GitHub gets the cap unchanged). A
# meeting left unread is read next week; gaps are recorded, never fatal to
# the steps after it.
python3 tools/ca_committees.py --session 45-1 --budget-seconds "$(bash tools/collector_budget.sh 1200 "$SECONDS" 2700)" || rc=1
# Senate committee transcripts (tools/ca_senate_committees.py, 12 October
# 2026): SOCI, LCJC and RIDR in full, SECD by study title. Senators'
# interventions to ca_speeches (chamber='senate', forum='committee'),
# witnesses only to ca_testimony. At most 15 minutes, less if the steps
# before it overran; the first runs are the 45-1 baseline, drained 40
# transcripts a week. Gaps recorded, never fatal to the steps after it.
python3 tools/ca_senate_committees.py --session 45-1 --budget-seconds "$(bash tools/collector_budget.sh 900 "$SECONDS" 1800)" || rc=1
# Committee reports, House (the key nine) and Senate (SOCI, LCJC, RIDR), with
# their recommendations and any government response
# (tools/ca_committee_reports.py, 12 October 2026). At most 10 minutes.
python3 tools/ca_committee_reports.py --session 45-1 --budget-seconds "$(bash tools/collector_budget.sh 600 "$SECONDS" 1200)" || rc=1
python3 tools/ca_courts.py || rc=1
python3 tools/ca_petitions.py --limit 300 || rc=1
python3 tools/ca_gazette.py || rc=1
python3 tools/ca_triage.py --limit 2000 --budget-seconds 1200 || rc=1

# The 5CA sheets (tools/ca_5ca.py, data/5ca/ca-5ca-*.csv): offline, from the
# store just collected and judged, seconds to run, as us_5ca/ie_5ca/au_5ca
# run in their weeklies. Only SIGNED readings in config/ca_stance.yaml place
# anyone. A failure is a gap, never a lost week; last week's sheets stand.
python3 tools/ca_5ca.py --all || echo "  [gap] the 5CA sheets failed; last week's stand"

# The week ahead (src/agenda.py, src/agendas/ca.py, tools/country_agenda.py):
# House committee notices, the Projected Order of Business and the sitting
# calendar, the Senate's committee schedule and Order Paper, into the shared
# agenda table under cc='ca', robots.txt asked at run time. Before the
# edition, which renders it. A failure is a [gap] line; last week's read stands.
python3 tools/country_agenda.py ca || echo "  [gap] the week-ahead agenda step failed"
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/ca/
# rewritten from the store just collected; never posted or DMed. A failure
# is a [gap] line and never costs the store.
python3 tools/member_profiles.py ca \
  || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"

# The edition (tools/ca_monitor.py, 9 October 2026): editions/ca-monitor-<date>.md
# from the store just collected and judged, and a DM to Christopher alone.
# SPEAKS ONCE A DAY, as jobs/us-weekly.sh does: an edition already committed
# for today means another run (the Mini, or GitHub's backup) has sent the DM,
# so it is rewritten, not resent. On the Mini the Slack token comes from
# ~/runner/env.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# House and Senate divisions on our ground (watched, or tier 1) not briefed
# yet, written to data/briefs/ and sent in one DM to Chris alone,
# de-duplicated in data/vote-briefs/ca.json (shared with the daily job,
# committed with data/; the first pass seeds it silently). Never stops the run.
python3 tools/country_vote_briefs.py --country ca --send \
  || echo "  [gap] vote briefs failed for ca; the next run retries"
TODAY=$(date +%Y-%m-%d)
if git ls-files --error-unmatch "editions/ca-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/ca_monitor.py --edition || { echo "  [gap] the edition failed to render"; rc=1; }
else
  python3 tools/ca_monitor.py --edition --dm || { echo "  [gap] the edition or its DM failed"; rc=1; }
fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
