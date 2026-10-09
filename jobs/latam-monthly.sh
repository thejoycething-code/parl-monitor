#!/bin/bash
# Latam monthly: Venezuela's news-feed check (tools/ve_news.py) and
# Nicaragua's La Gaceta check (tools/nic_gaceta.py), their alerts, then the
# Latam edition and its DM to Chris (tools/latam_monitor.py), then publish
# the raw archive and the store.
#
# The eleven collected countries are NOT collected here: each keeps its own
# weekly job (jobs/<cc>-weekly.sh; Guatemala fortnightly on GitHub, X9),
# which runs that country's alert pass right after its collector. This job
# only reads their stores.
#
# Called by .github/workflows/latam-monthly.yml and, on the Mac Mini, by
# tools/mini_run.sh latam-monthly (the 1st of each month). One script, two
# callers. Both fetch the store first; this script publishes the archive and
# the store itself, and the caller commits data/ and editions/.
#
# SPEAKS ONCE A DAY. An edition already committed for today means another
# run (the Mini, or the GitHub backup) has sent the DM: it is rewritten, not
# resent.
#
#     LATAM_RECLASSIFY=true   re-derive the Venezuela and Nicaragua rows'
#                             areas first (after a taxonomy-es change)
#
# A refused source is a [gap] line and never stops the edition: the edition
# says the feed or the gazette was not read.
#
# mini_run: commit editions
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Latam monthly}"
# The DM goes to Chris alone (the tools also force his id).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
LOG="${LATAM_LOG_DIR:-/tmp}"
mkdir -p "$LOG"

if [ "${LATAM_RECLASSIFY:-}" = "true" ]; then
  python3 tools/ve_news.py --reclassify | tee "$LOG/latam-reclassify.log"
  python3 tools/nic_gaceta.py --reclassify | tee -a "$LOG/latam-reclassify.log"
fi

python3 tools/ve_news.py | tee "$LOG/ve-news.log" \
  || echo "  [gap] ve-news stopped early; the edition says what it holds"
python3 tools/nic_gaceta.py | tee "$LOG/nic-gaceta.log" \
  || echo "  [gap] nic-gaceta stopped early or met an issue without text; the edition says what it holds"
python3 tools/latam_alerts.py --country ve --country nic --send | tee "$LOG/latam-alerts.log" \
  || echo "  [gap] latam-alerts failed for ve/nic; the next run retries"

TODAY=$(date +%Y-%m-%d)
if git ls-files --error-unmatch "editions/latam-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/latam_monitor.py --edition | tee "$LOG/latam-monitor.log"
else
  python3 tools/latam_monitor.py --edition --dm | tee "$LOG/latam-monitor.log"
fi

# The raw archive before the store: a store citing payloads the archive
# lacks is the worse failure. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
