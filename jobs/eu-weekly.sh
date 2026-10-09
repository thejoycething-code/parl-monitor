#!/bin/bash
# EU weekly on the Mac Mini (tools/mini_run.sh eu-weekly, Saturdays 11:00 London).
# .github/workflows/eu-weekly.yml is the backup and skips itself when this has run
# (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW'S SCHEDULED RUN, IN ITS ORDER
# (tests/test_mini_jobs.py holds the two together). As there, the steps stop at the first failure.
# Whatever was gathered is published, as the workflow's guarded publish
# steps do.
# Triage spends (the routine weekly) and the edition is DMed, with the
# secrets in config/secrets.yaml, as the workflow writes them.
#
# mini_run: commit editions partner_site docs briefs
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-EU weekly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
(
  set -e
  python3 tools/eu_dossiers.py
  python3 tools/eu_agenda.py
  python3 tools/eu_texts.py
  python3 tools/eu_rollcalls.py
  python3 tools/eu_courts.py
  python3 tools/eu_pqs.py
  python3 tools/eu_eci.py
  python3 tools/eu_committees.py
  python3 tools/eu_speeches.py
  python3 tools/eu_meps_enrich.py
  python3 tools/eu_triage.py
  python3 tools/eu_monitor.py --edition --dm
  python3 tools/make_eu_tracker.py
  python3 tools/make_eu_5ca.py
) || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
