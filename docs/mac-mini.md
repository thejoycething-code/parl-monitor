# The debate tasks on the Mac Mini

Christopher, 8 October 2026: "Let's move clips to my Mac Mini machine."

Two Claude desktop scheduled tasks make the UK debate packs. They moved from the laptop to the Mac Mini, which stays awake:

| Task | When | What it does |
|---|---|---|
| `debate-day-net` | weekdays 16:45 London | Flags a debate on our ground that grew during the day (tools/debate_watch.py net), commits config/debate_watch.yaml, DMs Christopher when it flags one. |
| `tia-second-reading-debate-pack` | weekdays 18:30 London | On a flagged day: the pack, the selection and sequence, the provisional report (approval DM), the vertical reels and the subtitled full speeches. |

The clips stay on the Mini in `data/packs/<pack>/clips/` for review. Footage reaches Drive only when Christopher publishes (`debate_report.py --publish --with-clips`), as before.

Everything else already runs in GitHub Actions. The Monday publish is started by a cloud routine since 8 October; see `.github/workflows/monday-publish.yml`.

## The move

1. **On the Mini, get the setup script and run it:**
   ```
   gh auth login        # as thejoycething-code, never the work account
   gh repo clone thejoycething-code/parl-monitor ~/parl-monitor
   bash ~/parl-monitor/tools/macmini_setup.sh
   ```
   It installs the Python packages (the bundled ffmpeg, yt-dlp, faster-whisper) and lists what is still to do. Rerun it after each step until it says "Ready".
2. **Copy the two secret files by hand** (AirDrop or a USB stick, not chat or email): `~/parl-monitor/config/secrets.yaml` and `~/parl-monitor/config/google-service-account.json`, from the laptop to the same paths on the Mini.
3. **Turn off sleep** on the Mini (System Settings > Energy). Claude must be open and signed in for scheduled tasks to fire.
4. **Create the tasks.** Open Claude on the Mini, start a Code session in `~/parl-monitor`, and say:
   > Create two scheduled tasks from ops/scheduled-tasks/: debate-day-net, weekdays at 16:45, from debate-day-net.md; and tia-second-reading-debate-pack, weekdays at 18:30, from tia-second-reading-debate-pack.md. Use each file's text (after the front matter) as the task prompt. If my home folder here is not /Users/chrisjoyce, replace that path in the prompts.
5. **Retire the laptop's copies only after the Mini's first clean run** (a quiet 16:45 net and a quiet 18:30 on an unflagged day are enough): disable both tasks in the laptop's Claude app, or ask a session there to.

The prompts in `ops/scheduled-tasks/` are the laptop's task prompts as of 8 October 2026. Edit them there and recreate the tasks when they change.

## Moving everything else (chats, tasks, memory, app profiles)

Migration Assistant is not an option, so `ops/copy_to_mini.sh` copies over the local network with rsync and SSH, from the laptop:

```
bash ops/copy_to_mini.sh you@mac-mini.local          # dry run first
bash ops/copy_to_mini.sh you@mac-mini.local --go     # then for real
```

Before: Remote Login on the Mini, Claude quit on both machines, Full Disk Access for Terminal on the laptop. It copies ~/.claude (Code-tab chats, memory, scheduled tasks, settings), ~/.claude.json, the three Claude app profiles without their caches, ~/.local, and the project folders with their secrets; it leaves out parl-monitor/.claude/worktrees. If the Mini's home folder differs from /Users/chrisjoyce it rewrites the paths afterwards. Cloud routines and claude.ai chats need no copy: they follow the account.

After: sign in to Claude on the Mini (logins are in the Keychain, not copied), `gh auth login`, run `tools/macmini_setup.sh`, then turn the laptop's scheduled tasks off so nothing posts twice.

## The HUDOC relay (8 October 2026)

HUDOC refuses GitHub Actions (403) but answers the Mini. Christopher: "Run the HUDOC search from the Mini". The launchd job `net.citizengo.parlmonitor.hudoc-relay` (plist in `ops/launchd/`) runs `tools/hudoc_relay.sh` daily at 07:30: in its own clone (`~/parl-relay`) it runs `tools/eu_courts.py --relay` and commits the replies to `data/hudoc-relay/`. The EU weekly reads them when its own search is refused, if they are at most 8 days old; otherwise it records a gap as before. Log: `~/parl-chains/hudoc-relay.log`. It needs the Mini awake and `gh` logged in; it never touches the store. The JSON API answers our client with a Cloudflare challenge from the Mini too, so the relay reads HUDOC's RSS search feed; if that also answers GitHub Actions, the relay is a spare.

## US weekly on the Mini (9 October 2026)

Christopher: "add the US weekly to the Mini". `jobs/us-weekly.sh` is now the one script both callers run: `tools/mini_run.sh us-weekly` on the Mini (launchd, Fridays 10:00 London, plist in `ops/launchd/`) and `.github/workflows/us-weekly.yml` as the backup (Friday 10:00 UTC, gated by `mini-check` with `MINI_LAST_US_WEEKLY`; the old 12:00 retry slot is gone).

- **senate.gov refuses Christopher's home connection** (the laptop, 9 October). If it refuses the Mini too, the script dispatches a Senate-only run on GitHub (`senate_only=true`), waits for it to publish the store, fetches the store again and does the rest with `--no-senate`. If that fails, the edition goes out without the week's Senate votes and the log says so in a `[gap]` line.
- **The edition is committed by the runner**: the script's `# mini_run: commit editions` line tells `mini_run.sh` to commit `editions/` beside `data/`.
- **Speaks once a day**: an edition already committed for today is rewritten without resending the DM, so a GitHub backup after a Mini run cannot DM twice.
- **On the Mini, `~/runner/env` needs** `SLACK_BOT_TOKEN` (already there for Division watch) and, only when the repo variable `US_JUDGE` is `on`, `ANTHROPIC_API_KEY`. `JOB_TIMEOUT` is three hours in the plist: the step budgets (roll calls, Federal Register, Supreme Court, week ahead, judge, a wait for the Senate half on GitHub) add up to about two and a quarter.

Install on the Mini, after `git pull` in `~/runner/parl-monitor`:
```
cp ~/runner/parl-monitor/ops/launchd/net.citizengo.parlmonitor.us-weekly.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.us-weekly.plist
```
A first test by hand: `RUNNER_REF=main bash ~/runner/parl-monitor/tools/mini_run.sh us-weekly` (it posts the DM if no edition is committed for today).

## Australia weekly (9 October 2026, branch `australia`)

docs/mac-mini-runner.md (the migration list for the launchd runner) is not on this branch, so the new job is recorded here; move this entry into that list when the branches meet.

| Job | Mini (launchd, London time) | GitHub backup (UTC) | Gate |
|---|---|---|---|
| `au-weekly` | Fridays 02:00 (`ops/launchd/net.citizengo.parlmonitor.au-weekly.plist`) | Fridays 02:00, retry 04:00 (`.github/workflows/au-weekly.yml`) | `MINI_LAST_AU_WEEKLY`, grace 200 minutes |

- **One script, two callers:** `jobs/au-weekly.sh` runs `tools/au_rollcalls.py`, the judge when the repo variable `AU_JUDGE` is `on` (it is not), then the edition (`tools/au_monitor.py --edition --dm`), and on the Mini publishes the raw archive and the store itself (`raw_state.py --push`, `db_state.py --push`), as `tools/mini_run.sh` requires. It needs the store, so it carries no `no-store` line; its `# mini_run: commit editions` line makes the runner commit `editions/` too.
- **Speaks once a day**, as the US weekly: an edition already committed for today is rewritten without resending the DM.
- **On the Mini, `~/runner/env` needs** `SLACK_BOT_TOKEN` (already there for Division watch) and, only when `AU_JUDGE` is `on`, `ANTHROPIC_API_KEY`.
- **The aph.gov.au probe** can be run here by hand, read-only: `python3 tools/au_probe.py --out /tmp/au-probe` (Christopher decides; see docs/australia-scope.md).
- **Heartbeat name:** on the Mini there is no `GITHUB_WORKFLOW`, so the script sets it to "Australia weekly"; otherwise `db_state.py --push` would stamp the run as "local" and the coverage watch would never see it.
- **Why 200 minutes of grace:** the Mini runs once and must cover both GitHub slots. 02:00 London is 01:00 UTC in summer, three hours before the 04:00 retry.
- **Exit codes:** the collector exits 3 when it stored what it could and recorded gaps; the script publishes and exits 0 so the commit step runs. Any other failure publishes nothing and exits non-zero.
- **Install on the Mini** (after the branch is merged to main, because `mini_run.sh` records the slot only for main): `cp ops/launchd/net.citizengo.parlmonitor.au-weekly.plist ~/Library/LaunchAgents/` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.au-weekly.plist`.
- **Sources:** data.openaustralia.org.au, handbookapi.aph.gov.au and api.prod.legislation.gov.au all answered the laptop on 9 October 2026; www.aph.gov.au and ParlInfo did not (Azure WAF). Whether the Mini's network fares differently has not been tried.

## Ireland weekly on the runner (9 October 2026, not yet installed)

Like the US weekly, it **writes the store** and sends a DM:

- `jobs/ie-weekly.sh` (one script, two callers): `tools/ie_rollcalls.py`, then, on the Mini, `raw_state.py --push` and `db_state.py --push`. There it exits 0 once both are published, even when the collector recorded gaps, because `mini_run.sh` commits `data/` only after a clean exit and a published store without its committed sidecar is refused by every later pull. Gaps stay in the gaps table and the log, and on the Mini they page nobody yet. On GitHub the workflow sets `IE_PUBLISH=false` and publishes with its own guarded steps, as us-weekly does, so a gap turns the run red and the store and sidecar still land.
- It exports `GITHUB_WORKFLOW="Ireland weekly"` when unset, so a Mini run stamps the pipeline's heartbeat rather than "local".
- **The edition** (`tools/ie_monitor.py`) is written by the same script after the collector, and its `# mini_run: commit editions` line makes the runner commit `editions/` beside `data/`. It **speaks once a day**: an edition already committed for today is rewritten without resending the DM. The DM goes to Christopher alone (`SLACK_DM_USER_ID` defaults to U05LJP0BT61); `~/runner/env` already holds `SLACK_BOT_TOKEN` for Division watch.
- **The judge** (`tools/ie_triage.py`) runs only when the repo variable `IE_JUDGE` is `on` (read with `gh variable get` on the Mini); then `~/runner/env` also needs `ANTHROPIC_API_KEY`. It is off.
- The Mini runs it at 09:30 London, half an hour before the US weekly at 10:00; the lock queues the second for up to 30 minutes.
- launchd: `ops/launchd/net.citizengo.parlmonitor.ie-weekly.plist`, Fridays 09:30 London. Backup: `.github/workflows/ie-weekly.yml`, cron `30 8 * * 5`, gated by `mini-check.yml` with job `IE_WEEKLY`. In winter (GMT) the GitHub slot comes an hour before the Mini, so a punctual backup can run first and the Mini then runs again; both are idempotent.
- Install after merge to main: copy the plist to `~/Library/LaunchAgents` and `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.ie-weekly.plist`. Optional heartbeat: `HC_IE_WEEKLY` in `~/runner/env`.

## Portugal weekly (9 October 2026, branch `portugal`)

| Job | Mini (launchd, London time) | GitHub backup (UTC) | Gate |
|---|---|---|---|
| `pt-weekly` | Saturdays 15:00 (`ops/launchd/net.citizengo.parlmonitor.pt-weekly.plist`) | Saturdays 16:00, retry 19:00 (`.github/workflows/pt-weekly.yml`) | `MINI_LAST_PT_WEEKLY`, grace 320 minutes |

- **One script, two callers:** `jobs/pt-weekly.sh` runs `tools/pt_rollcalls.py`, then publishes the raw archive and the store itself (`raw_state.py --push`, `db_state.py --push`), as `tools/mini_run.sh` requires. It needs the store, so it carries no `no-store` line.
- **Heartbeat name:** the script sets `GITHUB_WORKFLOW` to "Portugal weekly" on the Mini, so the coverage watch sees its runs.
- **Why 320 minutes of grace:** the Mini runs once and must cover both GitHub slots. 15:00 London is 14:00 UTC in summer, five hours before the 19:00 retry.
- **Exit codes:** the collector exits 3 when it stored what it could and recorded gaps; the script publishes and exits 0. Exit 1 (no initiatives read) publishes nothing.
- **Install on the Mini** (after the branch is merged to main): `cp ops/launchd/net.citizengo.parlmonitor.pt-weekly.plist ~/Library/LaunchAgents/` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.pt-weekly.plist`.
- **Source:** www.parlamento.pt and app.parlamento.pt answered the laptop on 9 October 2026; each run downloads about 98 MB (the initiatives file is 97 MB, about 80 seconds).

## Slovakia weekly (9 October 2026, branch `slovakia`)

docs/mac-mini-runner.md (the migration list for the launchd runner) is not on this branch, so the new job is recorded here; move this entry into that list when the branches meet. Same pattern as `au-weekly` on the `australia` branch.

| Job | Mini (launchd, London time) | GitHub backup (UTC) | Gate |
|---|---|---|---|
| `sk-weekly` | Tuesdays 02:00 (`ops/launchd/net.citizengo.parlmonitor.sk-weekly.plist`) | Tuesdays 02:00, retry 04:00 (`.github/workflows/sk-weekly.yml`) | `MINI_LAST_SK_WEEKLY`, grace 200 minutes |

- **One script, two callers:** `jobs/sk-weekly.sh` runs `tools/sk_rollcalls.py`, then on the Mini publishes the raw archive and the store itself (`raw_state.py --push`, `db_state.py --push`), as `tools/mini_run.sh` requires. On GitHub it runs with `SK_PUBLISH=false` and the workflow publishes in its own guarded steps. It needs the store, so it carries no `no-store` line.
- **Heartbeat name:** the script sets `GITHUB_WORKFLOW` to "Slovakia weekly" when it is unset, so the Mini's runs reach the coverage watch.
- **Why 200 minutes of grace:** the Mini runs once and must cover both GitHub slots; 02:00 London is 01:00 UTC in summer.
- **Install on the Mini** (after the branch is merged to main): `cp ops/launchd/net.citizengo.parlmonitor.sk-weekly.plist ~/Library/LaunchAgents/` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.sk-weekly.plist`.
- **Source:** www.nrsr.sk only (its open-data JSON and its vote pages), both keyless; both answered the laptop on 9 October 2026. The vote pages took 1.7 to 96 seconds each, so the collector stops reading them at 45 minutes and resumes next week.
