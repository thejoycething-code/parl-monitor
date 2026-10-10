#!/bin/bash
# Uruguay weekly: the Cámara de Representantes' roll, pedidos de informes and
# Diario de Sesiones index (documentos.diputados.gub.uy), and every new law
# from IMPO (tools/uy_rollcalls.py), then publish the raw archive and the store.
#
# Called by .github/workflows/uy-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh uy-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     UY_RECLASSIFY=true    re-derive every stored UY question's and law's
#                           areas, offline, before the pull (after
#                           config/taxonomy-es.yaml or watchlist-uy changes)
#
# The first run backfills the laws from Ley 20.380 (September 2024): about
# 150 laws at IMPO's Crawl-delay of ten seconds. The budget (45 minutes)
# stops it cleanly and the next run resumes from the store.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
# mini_run: commit profiles
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Uruguay weekly}"
export PYTHONUNBUFFERED=1
if [ "${UY_RECLASSIFY:-}" = "true" ]; then
  python3 tools/uy_rollcalls.py --reclassify
fi
rc=0
python3 tools/uy_rollcalls.py --budget-seconds 2700 || rc=$?
# Instant Latam alerts (tools/latam_alerts.py): this country's watched and
# tier-1 items, a short DM each to Chris alone, de-duplicated in
# data/latam-alerts/uy.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/latam_alerts.py --country uy --send \
    || echo "  [gap] latam-alerts failed for uy; the next run retries"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/uy/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py uy \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "uy-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "uy-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
