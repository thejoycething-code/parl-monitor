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
# Triage and stance spend (the routine weekly) and the edition is DMed.
#
# mini_run: commit editions reviews docs/judge-eval.md partner_site/de-issues.html partner_site/de-issue-*.html partner_site/de-votes.html
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
  python3 tools/de_committees.py
  python3 tools/de_profiles.py
  python3 tools/de_triage.py
  python3 tools/de_stance.py --limit 200
  python3 tools/de_briefs.py
  python3 tools/de_issues.py
  python3 tools/de_monitor.py --edition --dm
) || rc=1

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

WEEK=$(TZ=Europe/London python3 -c "import datetime; t=datetime.date.today(); print((t - datetime.timedelta(days=t.weekday())).isoformat())")
echo "German judge evaluation for week commencing $WEEK"
python3 tools/de_judge_eval.py ingest || rc=1
python3 tools/de_judge_eval.py sample --week "$WEEK" || rc=1
python3 tools/de_judge_eval.py report --write || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
