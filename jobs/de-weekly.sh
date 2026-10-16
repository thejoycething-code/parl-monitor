#!/bin/bash
# Germany weekly on the Mac Mini (tools/mini_run.sh de-weekly, Sundays 20:00 London).
# .github/workflows/de-weekly.yml is the backup and skips itself when this has run
# (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW'S SCHEDULED RUN, IN ITS ORDER
# (tests/test_mini_jobs.py holds the two together). As there, the steps stop at the first failure. The judge evaluation runs whatever
# happened, as there.
# Whatever was gathered is published, as the workflow's guarded publish
# steps do.
# Triage and stance no longer spend (paid AI off, 16 October 2026): without
# DE_TRIAGE_PAID=1 / DE_STANCE_PAID=1 they leave their rows to the free
# session judge (jobs/europe-session-judge.sh, Mondays 14:30). The edition is DMed.
#
# mini_run: commit editions reviews docs/judge-eval.md partner_site/de-issues.html partner_site/de-issue-*.html partner_site/de-votes.html profiles
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Germany weekly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
(
  set -e
  python3 tools/de_rollcalls.py --all
  python3 tools/de_documents.py --mode terms
  python3 tools/de_agenda.py
  python3 tools/de_speeches.py
  python3 tools/de_petitions.py
  python3 tools/de_courts.py
  python3 tools/de_amendments.py
  # What a roll call is ON (16 October 2026, tools/amendment_text.py, src/amendtext_de.py):
  # the Drucksache's DIP text; exit 3 (gaps recorded) is not a failure.
  python3 tools/amendment_text.py --cc de --budget-seconds 300 || [ $? -eq 3 ]
  python3 tools/de_committees.py
  python3 tools/de_profiles.py
  python3 tools/de_triage.py
  python3 tools/de_stance.py --limit 200
  python3 tools/de_briefs.py
  python3 tools/de_issues.py
  # Government consultations and publications (tools/gov_docs_step.sh,
  # tools/country_gov_docs.py, src/gov_docs.py, 16 October 2026): this
  # country's government consultations and publications on our ground into
  # gov_docs, before the edition, so the countdown's deadline rows are this
  # week's. Never fatal: a source that failed is a [gap] line and a gaps row.
  bash tools/gov_docs_step.sh de
  python3 tools/de_monitor.py --edition --dm
) || rc=1

# Forward regional agendas (tools/regional_agenda_step.sh, 16 October 2026):
# the sixteen Landtage' upcoming plenary and committee agendas into regional_agenda,
# for the countdown. At most five minutes; a region not read is a [gap] line
# and keeps its stored rows, never the run's.
bash tools/regional_agenda_step.sh de "$SECONDS"

# The 5CA sheets (tools/de_5ca.py, data/5ca/de-5ca-bundestag-*.csv) and the
# vote page (tools/make_de_votes.py, partner_site/de-votes.html): offline, from
# the store as it stands, seconds to run, as the US, Irish and Australian
# weeklies run theirs. They run whatever the collectors did. Only SIGNED
# readings in config/de_stance.yaml place anyone or colour a vote. A failure is
# a gap, never a lost week: last week's sheets and page stand.
python3 tools/de_5ca.py --all \
  || echo "  [gap] de-5ca: the 5CA sheets failed; last week's stand"
python3 tools/make_de_votes.py \
  || echo "  [gap] de-votes: the vote page failed; last week's stands"

# THE SHARED COUNTRY FRAMEWORKS (16 October 2026, branch de-ca-gaps), read
# through the reader adapter src/editions/de.py; each failure is a [gap]
# line, never the run's, and none of them touches the German edition above.
# The week ahead in the shared agenda table (tools/country_agenda.py,
# src/agendas/de.py): the plenary Tagesordnung for the coming sitting week
# and the committees' sittings, for the daily sweep and the profiles.
python3 tools/country_agenda.py de \
  || echo "  [gap] the shared agenda step failed for de"
# Member intelligence (tools/member_intel.py, src/member_intel.fetch_de):
# every Bundestag committee's members from the Bundestag's own committee
# pages (about 80 requests, robots.txt asked); last week's rows stand on a
# failure. Nebentätigkeiten stay off (DE_SIDEJOBS) until Chris decides.
python3 tools/member_intel.py de \
  || echo "  [gap] member-intel: de not fully read; last week's rows kept"
# Member profiles (tools/member_profiles.py): profiles/de/, this term's
# Bundestag members, their recorded positions on our ground and their seats.
python3 tools/member_profiles.py de \
  || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# the Bundestag's watched and tier-1 recorded votes not briefed yet (the
# daily job, jobs/vote-briefs-daily.sh, briefs most of them the day they
# are taken), one DM to Chris alone, de-duplicated in data/vote-briefs/de.json.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
python3 tools/country_vote_briefs.py --country de --send \
  || echo "  [gap] vote briefs failed for de; the next run retries"

WEEK=$(TZ=Europe/London python3 -c "import datetime; t=datetime.date.today(); print((t - datetime.timedelta(days=t.weekday())).isoformat())")
echo "German judge evaluation for week commencing $WEEK"
python3 tools/de_judge_eval.py ingest || rc=1
python3 tools/de_judge_eval.py sample --week "$WEEK" || rc=1
python3 tools/de_judge_eval.py report --write || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
