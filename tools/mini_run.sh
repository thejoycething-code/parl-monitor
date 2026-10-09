#!/bin/bash
# Run one scheduled job on the Mac Mini (docs/mac-mini-runner.md, step 2).
#
#     tools/mini_run.sh <job>        # runs jobs/<job>.sh
#
# The Mini goes first and GitHub is the backup: GitHub's cron starts runs
# hours late or not at all (Division watch ran 17 of ~35 times in Sep-Oct),
# so launchd calls this at the slot's time and each workflow skips itself
# when MINI_LAST_<JOB> says the Mini already ran.
#
# It works in its OWN clone (~/runner/parl-monitor), never in ~/parl-monitor,
# so a session's half-finished edits never ride along with a data commit.
# The lock is the Mini's version of the parl-monitor-state concurrency group:
# one job at a time touches the runner clone and the store.
#
# Optional, in ~/runner/env (not in the repo):
#     HC_<JOB>=https://hc-ping.com/...   heartbeat per job (Chris creates it)
#     RUNNER_REF=<branch>                test a branch instead of main
set -u
# Everything runs inside main(): bash reads a script as it goes, and step 2
# rewrites this very file when it updates the clone. The first run on the Mini
# (9 October) ran half the old wrapper that way. A function is read whole
# before it runs, so the file can change underneath it.
main() {
SELF_SUM=$(shasum "$0" | cut -c1-40)
JOB="${1:?usage: mini_run.sh <job>}"
RUNNER="${RUNNER_HOME:-$HOME/runner}"
CLONE="$RUNNER/parl-monitor"
LOCK="$RUNNER/locks/state"
JOB_TIMEOUT="${JOB_TIMEOUT:-3600}"   # seconds
LOCK_WAIT="${LOCK_WAIT:-1800}"       # seconds to queue behind another job
export PATH="$RUNNER/venv/bin:$HOME/.local/bin:/Library/Frameworks/Python.framework/Versions/3.14/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
[ -f "$RUNNER/env" ] && . "$RUNNER/env"
REF="${RUNNER_REF:-main}"
UPPER=$(echo "$JOB" | tr 'a-z-' 'A-Z_')
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "$STARTED mini_run $JOB (ref $REF)"

STAGE=start
fail() {
  echo "  FAILED at $STAGE: $*"
  [ -d "$LOCK" ] && [ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ] && rm -rf "$LOCK"
  hc="HC_$UPPER"; [ -n "${!hc:-}" ] && curl -fsS -m 10 --retry 3 "${!hc}/fail" >/dev/null
  # Never let the alerter mask the failure: it prints when Slack is down.
  ( cd "$CLONE" 2>/dev/null &&
    FAILED_WORKFLOW="Mini: $JOB" FAILED_STEP="$STAGE" \
    FAILED_RUN_URL="Mac Mini log: $RUNNER/logs/$JOB.log" \
    python3 tools/alert_failure.py )
  exit 1
}

# 1. The lock. mkdir is atomic; macOS has no flock. A lock whose owner is
# dead is stale (a crash or a power cut) and is taken over.
STAGE=lock
mkdir -p "$RUNNER/locks" "$RUNNER/logs"
waited=0
# A re-run of a newer wrapper (step 2) keeps the PID, so the lock is still ours.
until [ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ] || mkdir "$LOCK" 2>/dev/null; do
  owner=$(cat "$LOCK/pid" 2>/dev/null)
  if [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; then
    echo "  stale lock from pid $owner ($(cat "$LOCK/job" 2>/dev/null)); taking it"
    rm -rf "$LOCK"; continue
  fi
  [ "$waited" -ge "$LOCK_WAIT" ] && fail "lock held by $(cat "$LOCK/job" 2>/dev/null) for ${waited}s"
  sleep 15; waited=$((waited + 15))
done
echo $$ > "$LOCK/pid"; echo "$JOB" > "$LOCK/job"
trap 'rm -rf "$LOCK"' EXIT

# 2. Bring the clone up to date. The clone is ours alone: an unfinished
# rebase or uncommitted edits are leftovers of a crashed run. Local COMMITS
# are kept, so data a crashed run committed but never pushed goes out now.
STAGE="update clone"
cd "$CLONE" || fail "no runner clone at $CLONE"
git rebase --abort >/dev/null 2>&1
git reset -q --hard HEAD
git fetch -q origin "$REF" || fail "git fetch"
git checkout -q "$REF" 2>/dev/null || git checkout -q -b "$REF" "origin/$REF" || fail "checkout $REF"
git rebase -q "origin/$REF" || { git rebase --abort; fail "rebase onto origin/$REF"; }
[ -f "jobs/$JOB.sh" ] || fail "no jobs/$JOB.sh on $REF"
# The update brought a different wrapper: run that one instead, holding the lock.
if [ -z "${MINI_RUN_FRESH:-}" ] && [ "$(shasum tools/mini_run.sh | cut -c1-40)" != "$SELF_SUM" ]; then
  echo "  the wrapper changed; re-running the new one"
  trap - EXIT
  MINI_RUN_FRESH=1 exec bash "$CLONE/tools/mini_run.sh" "$JOB"
fi

STAGE="fetch the store"
GH_TOKEN=$(gh auth token) || fail "gh is not signed in"
export GH_TOKEN
# The store is 895MB and every pull downloads it whole, so a job that never
# touches it says so with a "mini_run: no-store" line in its script.
if grep -q '^# mini_run: no-store' "jobs/$JOB.sh"; then
  echo "  no store needed"
  rm -f data/.store-pulled data/parl-monitor.db
else
  python3 tools/db_state.py --pull || fail "db_state --pull"
fi

# 3. The job, under a time limit (perl alarm: macOS ships no timeout(1)).
STAGE="jobs/$JOB.sh"
perl -e 'alarm shift; exec @ARGV' "$JOB_TIMEOUT" bash "jobs/$JOB.sh"
rc=$?
[ "$rc" -eq 142 ] && fail "timed out after ${JOB_TIMEOUT}s"
[ "$rc" -ne 0 ] && fail "exit $rc"

# 4. Commit data/, plus any folder the job names. Publishing the store and
# the raw archive is the job's own last step (db_state.py / raw_state.py --push, as on GitHub),
# and each push rewrites its sidecar. A store that changed while its
# sidecar did not was never published: committing then would go out half.
STAGE="commit state"
if [ data/parl-monitor.db -nt data/.store-pulled ] && git diff --quiet -- data/parl-monitor.db.json; then
  fail "the job changed the store but did not publish it (db_state.py --push)"
fi
git add -A data
# A job that writes outside data/ names the folder: "# mini_run: commit editions".
for extra in $(sed -n 's/^# mini_run: commit //p' "jobs/$JOB.sh"); do
  case "$extra" in data|data/*|""|/*|*..*) continue ;; esac
  [ -e "$extra" ] && git add -A -- "$extra"
done
if ! git diff --cached --quiet; then
  git commit -q -m "$JOB (Mini): $(date -u +%Y-%m-%dT%H:%M)Z"
  STAGE=push
  pushed=
  for attempt in 1 2 3 4 5 6; do
    if git pull -q --rebase --autostash origin "$REF"; then
      git push -q origin "HEAD:$REF" && { pushed=1; break; }
    else
      git rebase --abort >/dev/null 2>&1   # never leave the tree mid-rebase
      echo "  rebase conflict (attempt $attempt)"
    fi
    sleep $(( attempt * 10 + RANDOM % 10 ))
  done
  [ -n "$pushed" ] || fail "push failed six times"
  git fetch -q origin "$REF"
  [ "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)" ] || fail "HEAD is not FETCH_HEAD after push"
  echo "  pushed $(git rev-parse --short HEAD)"
else
  echo "  nothing to commit"
fi

# 5. Record the slot, so the GitHub backup skips itself. Only for main: a
# branch test must not tell production that the slot ran.
STAGE="record slot"
if [ "$REF" = main ]; then
  gh variable set "MINI_LAST_$UPPER" --body "$STARTED" -R thejoycething-code/parl-monitor \
    || fail "gh variable set MINI_LAST_$UPPER"
fi

# 6. Heartbeat.
hc="HC_$UPPER"; [ -n "${!hc:-}" ] && curl -fsS -m 10 --retry 3 "${!hc}" >/dev/null
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) mini_run $JOB done"
}
main "$@"
exit $?
