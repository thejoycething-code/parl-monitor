#!/bin/bash
# Monday publish on the Mac Mini (tools/mini_run.sh monday-publish, Mondays
# 04:00 London): render the edition, post it to #campaigns-en-gb, create the
# Asana reading task, run the judge evaluation, then publish the raw archive
# and the store. The partner site is deployed by GitHub's Deploy tracker,
# which jobs/monday-publish.after.sh starts once the commit has landed (the
# Vercel token lives in GitHub). .github/workflows/monday-publish.yml is the
# backup: it skips while this runs (MINI_RUN_MONDAY_PUBLISH) and after it ran.
#
# THE SAME STEPS AS THE WORKFLOW, IN ITS ORDER (tests/test_mini_jobs.py holds
# the two together).
#
# ALREADY PUBLISHED THIS WEEK (run_monday.py writes duplicate=1, from
# publish_log): this run's render is from a store older than the one the
# real run published, so it is thrown away whole -- edition, site, reviews
# and the local store -- and nothing is published or committed, exactly as
# the workflow skips its publish and commit steps.
#
#     NO_PUBLISH=1   render without the Slack post and the Asana task
#
# mini_run: commit config/debate_watch.yaml editions reviews docs/judge-eval.md docs/mp-votes.html partner_site
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Monday publish}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1
python3 tools/backfill_pq_links.py || exit 1

OUT="$(mktemp -t monday-publish.XXXXXX)"
rc=0
GITHUB_OUTPUT="$OUT" python3 run_monday.py || rc=$?
if grep -q '^duplicate=1' "$OUT"; then
  echo "this week is already published (publish_log): discarding this run's render"
  git checkout -q -- .
  git clean -fdq -- config data docs editions partner_site reviews
  python3 tools/db_state.py --pull || exit 1
  exit 0
fi

WEEK=$(TZ=Europe/London python3 -c "import datetime; t=datetime.date.today(); print((t - datetime.timedelta(days=t.weekday())).isoformat())")
echo "Judge evaluation for week commencing $WEEK"
python3 tools/judge_eval.py ingest || rc=1
python3 tools/judge_eval.py sample --week "$WEEK" || rc=1
python3 tools/judge_eval.py report --write || rc=1

python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
