#!/bin/bash
# The GitHub-side step, shared (13 October 2026). Some legislatures answer
# GitHub's US runners and not the Mac Mini (or anything on a UK network):
#
#   source             job                  workflow input   reader
#   senate.gov         jobs/us-weekly.sh    senate_only      tools/us_rollcalls.py (Senate)
#   NJ, MA, MI         jobs/us-weekly.sh    states_github    tools/us_states_github.py
#   Santa Catarina     jobs/br-weekly.sh    states_github    tools/br_states.py --sources sc
#
# THE STORE-SAFETY PATTERN (one store writer at a time; never dispatched from
# the laptop). The weekly runs on the Mini first. At the START of its run,
# before it writes anything, the Mini asks GitHub (gh workflow run) for a run
# of the same workflow with the half's input set, and waits while it HOLDS
# ITS LOCK, so no other Mini job writes the store meanwhile; GitHub's run is
# in the parl-monitor-state concurrency group, so no other GitHub job does
# either. GitHub's run pulls the store, reads the GitHub-only sources,
# publishes the raw archive and the store (db_state.py --push, which refuses
# to publish over a store it has not seen) and commits the sidecar. The Mini
# then pulls the branch and the store again and does the rest of its week,
# leaving those sources out. GitHub's own scheduled run (the backup, when
# the Mini has not run) reads them inline. There is no separate GitHub
# schedule to overlap with the Mini: the half runs inside the weekly's own
# slot, while the Mini waits.
#
#     source tools/github_half.sh
#     github_half us-weekly.yml -f senate_only=true -f states_github=true && echo published
#
# Returns 0 only when GitHub's run started, its pull job ran AND passed
# ("success" alone is not enough: a run whose gate skipped the work also
# succeeds, as the Senate half did on 10 October 2026), and the store was
# fetched again. Never call it on GitHub (GITHUB_ACTIONS) or from the laptop.

github_half() {
  local workflow="$1"; shift
  if [ -n "${GITHUB_ACTIONS:-}" ] || [ -z "${GH_TOKEN:-}" ] || ! command -v gh >/dev/null 2>&1; then
    echo "  github-half: gh unavailable here (or already on GitHub); not dispatched"
    return 2
  fi
  local repo=thejoycething-code/parl-monitor
  local branch since run_id=
  branch=$(git rev-parse --abbrev-ref HEAD)
  since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  if ! gh workflow run "$workflow" -R "$repo" --ref "$branch" "$@"; then
    echo "  github-half: could not dispatch $workflow"
    return 3
  fi
  for _ in $(seq 1 20); do
    sleep 6
    run_id=$(gh run list -R "$repo" --workflow "$workflow" --event workflow_dispatch \
             --branch "$branch" -L 5 --json databaseId,createdAt \
             --jq "[.[] | select(.createdAt >= \"$since\")][0].databaseId // empty")
    [ -n "$run_id" ] && break
  done
  if [ -n "$run_id" ] && gh run watch "$run_id" -R "$repo" --exit-status >/dev/null \
     && [ "$(gh run view "$run_id" -R "$repo" --json jobs \
             --jq '[.jobs[] | select(.name == "pull")][0].conclusion // "missing"')" = "success" ]; then
    echo "  github-half: run $run_id of $workflow published; fetching the store again"
    git pull -q --rebase --autostash origin "$branch"
    python3 tools/db_state.py --pull
    return 0
  fi
  echo "  github-half: run ${run_id:-none} of $workflow failed or never started"
  return 1
}
