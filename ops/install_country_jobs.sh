#!/bin/bash
# Install the country-edition launchd jobs on the Mac Mini, and run the
# reachability checks Chris approved on 10 October 2026
# (docs/country-decisions-2026-10-10.md: GT1, UY1, AR2).
#
# Run on the Mini, from the runner clone, after pulling main:
#   cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh
#
# Safe to rerun: a job already loaded is left alone. Nothing is pushed,
# posted or written outside ~/Library/LaunchAgents and the log below.

set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/parl-chains"
LOG="$LOG_DIR/install-countries.log"
UA="CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)"
mkdir -p "$AGENTS" "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1
echo "== install_country_jobs $(date -u +%Y-%m-%dT%H:%MZ) at $(git -C "$REPO" rev-parse --short HEAD)"

# Mexico's plist is only the clock: it dispatches the GitHub run.
JOBS="at-weekly nl-weekly pl-weekly it-weekly ch-weekly be-weekly fr-weekly
pt-weekly sk-weekly hr-weekly es-weekly br-weekly ar-weekly mx-weekly
co-weekly cl-weekly pe-weekly ec-weekly bo-weekly uy-weekly pa-weekly
hn-weekly sv-weekly do-weekly latam-monthly"

install_job() {
  local label="net.citizengo.parlmonitor.$1"
  local src="$REPO/ops/launchd/$label.plist"
  if [ ! -f "$src" ]; then echo "MISSING  $1 (no plist in ops/launchd)"; return; fi
  if launchctl print "gui/$(id -u)/$label" >/dev/null 2>&1; then
    echo "LOADED   $1 (already installed, left alone)"; return
  fi
  cp "$src" "$AGENTS/" && launchctl bootstrap "gui/$(id -u)" "$AGENTS/$label.plist" \
    && echo "INSTALLED $1" || echo "FAILED   $1"
}

for j in $JOBS; do install_job "$j"; done

# GT1: Guatemala runs from GitHub unless the Congreso answers the Mini.
code=$(curl -m 20 -s -o /dev/null -w "%{http_code}" -A "$UA" https://www.congreso.gob.gt/)
echo "GT1 congreso.gob.gt from the Mini: HTTP $code"
if [ "$code" = "200" ]; then
  install_job gt-weekly
else
  echo "GT1 not installed on the Mini: Guatemala stays on GitHub (fortnightly)."
fi

# UY1: does parlamento.gub.uy answer the Mini's own connection? (VPN off.)
echo "UY1 probing parlamento.gub.uy (read-only, robots honoured, stops at any challenge)"
python3 "$REPO/tools/probe_hosts.py" --out /tmp/uy-probe --max 3 https://parlamento.gub.uy/ \
  && cat /tmp/uy-probe/*/index.tsv 2>/dev/null

# AR2: does the Diputados vote site complete a connection from the Mini?
code=$(curl -m 30 -s -o /dev/null -w "%{http_code}" -A "$UA" https://votaciones.hcdn.gob.ar/)
echo "AR2 votaciones.hcdn.gob.ar from the Mini: HTTP $code (000 = no connection)"

echo "== done. Paste this log back to Claude: $LOG"
