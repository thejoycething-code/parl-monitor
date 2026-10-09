# Mac Mini runner: the Mini goes first, GitHub is the backup

Written 9 Oct 2026 from the MacBook session "Mac Mini AI Agent setup". It's meant to be carried out **on the Mac Mini** by a Claude Code session using Chris's **personal** Claude account (the 20x plan). The work account stays on whatever already runs there.

## Goal
1. Every scheduled parl-monitor job runs **on the Mini first**, at the exact time.
2. Each GitHub workflow keeps its schedule **only as a backup**. It exits within a minute if the Mini already ran that slot.
3. GitHub Actions use falls from about 11,500 to **under 2,000 minutes a month** (the free private allowance). Then the repo can go **private again**. Chris flips that switch himself.
4. Coverage watch stops failing every day for the same problem. Its warnings are compiled into **one daily health summary**.

## Evidence (MacBook, 9 Oct; runs 17 Sep–9 Oct)
- **Scheduled runs start late.** Monday publish starts 5½–12½ h late, Day sweep 2–7 h, Coverage watch 4–7 h.
- **Some never start.** Division watch ran 17 of about 35 expected times.
- **Minutes per 30 days, about 11,500 in total:**
  - manual dispatches, about 8,100: Provinces 3,910, Canada 1,397, Historic backfill 1,407, Germany backfill 752 and others;
  - scheduled runs, about 2,800;
  - Failure alert, about 420.
- **Store writers already share `concurrency: parl-monitor-state`.** Failures come from the push loop losing to *human/session* pushes: 372 human commits to main in 3 weeks against 236 bot commits. The loop is `pull --rebase || true`, then 3 pushes 5–15 s apart. A rebase conflict leaves the tree mid-rebase, and every retry then fails.
- Nothing outside the repo depends on it being public: no Pages site, and no raw/release URLs in the other projects. The site deploys to Vercel. The store is read with `GH_TOKEN`.

## Step 0: check before changing anything
- Which user/account runs the existing scheduled tasks on this Mini? List them (Claude Desktop scheduled tasks, `launchctl list | grep -v com.apple`, `crontab -l`). Report them to Chris and don't move them.
- Is the Claude Code CLI installed? Give the agent its own config dir so it never mixes with the work login: `CLAUDE_CONFIG_DIR=~/.claude-agent claude` → sign in with the personal account.
- Power: `pmset -g`, aiming for `sleep 0`, `autorestart 1` (restart after a power cut), `womp 1`. Changing these needs admin and the Mini is CGO-managed. If it's blocked, tell Chris instead of working around it. Check whether FileVault stops it coming back unattended after a restart.

## Step 1: a separate runner clone
`~/runner/parl-monitor`, a clean clone used **only** by scheduled jobs. Development stays in the existing clone, so a session's half-finished edits never ride along with a data commit.

## Step 2: one script, two callers
- For each job, move the workflow's `run:` steps into `jobs/<job>.sh`.
- The GitHub workflow then calls the same script, so there is one source of truth.
- Do it **one job at a time** and check that the output matches before moving to the next.

Wrapper `tools/mini_run.sh <job>`:
1. Take a lock (`mkdir ~/runner/locks/state` as an atomic lock; there's no flock on macOS). This is the Mini's version of the concurrency group.
2. `git pull --rebase` in the runner clone, then `python3 tools/db_state.py --pull`.
3. Run `jobs/<job>.sh` with a time limit.
4. Commit only `data/`, then push with the hardened loop (Step 4).
5. Record the slot: `gh variable set MINI_LAST_<JOB> --body "$(date -u +%FT%TZ)"`.
6. Ping the heartbeat URL (Healthchecks.io free tier). **Chris creates that account. Agents must not create accounts.**
7. On failure, DM Chris (U05LJP0BT61) using the existing `tools/alert_failure.py`.

Schedule with launchd plists in `~/Library/LaunchAgents/net.citizengo.parlmonitor.<job>.plist`, at the same UTC times the workflows meant to run.

## Step 3: GitHub as backup
- Add a first job `mini-check` to each scheduled workflow. It compares `vars.MINI_LAST_<JOB>` with the slot's time. If the Mini already ran the slot, the real job is skipped (`needs` + `if`).
- A skipped run costs about 1 minute. A late GitHub run still rescues a day the Mini missed.
- Rough budget: about 150–250 minutes a month of checks, plus real rescues.
- Keep `workflow_dispatch` on every workflow for manual use.
- Development and backfill runs (Provinces, Canada, Historic and Germany backfills, Score stance, probes) are **run locally on the Mini** from now on, not dispatched. That alone removes about 8,000 minutes a month.

## Step 4: harden the push loop (in all 18 workflows and in mini_run.sh)
```bash
for attempt in 1 2 3 4 5 6; do
  if git pull --rebase --autostash origin "$BRANCH"; then
    git push && break
  else
    git rebase --abort || true   # never leave the tree mid-rebase
    echo "rebase conflict (attempt $attempt)"
  fi
  sleep $(( attempt * 10 + RANDOM % 10 ))
done
```
Most of today's losses come from short waits and from retrying while stuck mid-rebase, so start with the version above. A real conflict in `data/` means two writers ran at once. That should stop happening once the Mini lock and the GitHub backup check are in place. If it still happens, the run should fail loudly, not re-commit over someone else's data.
Keep the existing check that `HEAD == FETCH_HEAD` afterwards. Sessions should avoid committing `data/` to main by hand.

## Step 5: compiled coverage warnings
- `tools/coverage.py --state data/coverage-state.json`. It remembers what it has already reported.
- It **exits 0** for known, unchanged problems. It exits 1 only for a **new** problem, or for one that has got worse (for example NI 12 days overdue → 19).
- The Mini's **daily health summary** (07:30 London, Slack self-DM `D05LMLVU090`) lists:
  - what ran overnight, what failed and what's queued;
  - every overdue source, with new ones marked.

## Migration order (one at a time, compare outputs, then move on)
1. Coverage watch (read-only, lowest risk) + compiled warnings + health summary
2. Division watch, Day sweep, EU day sweep (the time-critical ones)
3. Sunday pull, then Monday publish (replaces `dispatch_monday.sh` on the MacBook; unload that plist once this works)
4. Weeklies: Holyrood, Senedd, NI, EU, Germany, Canada, Provinces; UPR monthly
5. Failure alert: when the Mini is primary, GitHub failures are rare. Leave it as is.

## Going private (Chris does it)
- Wait for 7 days with GitHub use under 60 minutes a day: `gh api /repos/thejoycething-code/parl-monitor/actions/runs`. The billing page shows minutes once the repo is private.
- Then `gh repo edit thejoycething-code/parl-monitor --visibility private --accept-visibility-change-consequences`.
- Afterwards, check that Vercel deploys and `db_state.py --pull` still work.
