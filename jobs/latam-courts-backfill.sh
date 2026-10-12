#!/bin/bash
# Parity phases, set B (10 October 2026): the one-off backfills behind X8
# (constitutional courts), BO4 (Bolivian written questions) and UY5 (Uruguay's
# Diario vote totals), BY HAND on the Mac Mini, once, after the merge and
# BEFORE the first weekly runs of Colombia, Ecuador, Peru, Bolivia and
# Uruguay, so their first editions start from a seeded store (src/courts.py
# news_rows and src/latam.py items_uy_diario treat what a table held on its
# first day as history, never as news). Not scheduled: no plist, no workflow.
#
#   cd ~ && nohup ~/runner/parl-monitor/tools/mini_run.sh latam-courts-backfill \
#     >> ~/runner/logs/latam-courts-backfill.log 2>&1 &
#
# What it reads, all keyless (about 25 minutes):
#   * Colombia: the Court's exhortations file, whole (one request);
#   * Ecuador: the Court's judgment summaries and bulletins since 2019
#     (WordPress API, about 20 pages, two seconds apart);
#   * Peru: the Tribunal's press-note RSS feed, which holds the whole archive
#     (4,378 notes, 15 MB, ONE request at its Crawl-delay of 30 s);
#   * Bolivia: every written question of both chambers (Senado 48 pages,
#     Diputados 24 pages; about two minutes);
#   * Uruguay: the L legislature's Diarios de Sesiones (about 80 PDFs, 2 to
#     7 MB each, two seconds apart; the index is refreshed first).
# Portugal's court is NOT backfilled here: it rate-limits hard, so the weekly
# reads it ten rulings at a time.
#
# Each step records its own gaps and never stops the others; then the raw
# archive and the store are published.
set -eo pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never a weekly's (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Latam courts backfill}"
export PYTHONUNBUFFERED=1
python3 tools/co_courts.py || echo "  [gap] co-courts recorded gaps or failed"
python3 tools/ec_courts.py --since 2019-01-01 || echo "  [gap] ec-courts recorded gaps or failed"
python3 tools/pe_courts.py --backfill-feed || echo "  [gap] pe-courts recorded gaps or failed"
python3 tools/bo_rollcalls.py --no-bills || echo "  [gap] bo members failed; questions keep names as printed"
python3 tools/bo_questions.py --backfill || echo "  [gap] bo-questions recorded gaps or failed"
python3 tools/uy_rollcalls.py --no-laws || echo "  [gap] the Uruguay Diario index was not refreshed"
python3 tools/uy_diario.py --max 120 || echo "  [gap] uy-diario recorded gaps or failed"
# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
