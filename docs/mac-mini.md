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
- **On the Mini, `~/runner/env` needs** `SLACK_BOT_TOKEN` (already there for Division watch) and, only when the repo variable `US_JUDGE` is `on` (the paid alternative; off since 9 October 2026, when the session judge, below, became the default), `ANTHROPIC_API_KEY`. `JOB_TIMEOUT` is three hours in the plist: the step budgets (roll calls, Federal Register, Supreme Court, week ahead, the states, judge, a wait for the Senate half on GitHub) add up to about two and three quarters; the Congressional Record runs last of the collectors on what is left, at most 15 minutes, always keeping 40 for the judge, the edition and the transfers. The Congressional Record step needs `CONGRESS_API_KEY` there too (the same key as the amendment purposes).

Install on the Mini, after `git pull` in `~/runner/parl-monitor`:
```
cp ~/runner/parl-monitor/ops/launchd/net.citizengo.parlmonitor.us-weekly.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.us-weekly.plist
```
A first test by hand: `RUNNER_REF=main bash ~/runner/parl-monitor/tools/mini_run.sh us-weekly` (it posts the DM if no edition is committed for today).

## Next on the Mini: checklist (9 October 2026, end of day)

Everything below is merged to main. In order, after `cd ~/runner/parl-monitor && git pull`:

1. **Keys in `~/runner/env`** (no backticks around the values): `CONGRESS_API_KEY`, `OPENSTATES_API_KEY`; `SLACK_BOT_TOKEN` is already there. The US, Irish and Australian judges no longer need `ANTHROPIC_API_KEY`: since 9 October 2026 the free session judges score them (below, "Session judges"), and `US_JUDGE`, `IE_JUDGE` and `AU_JUDGE` go off after the merge (the key stays for the UK passes, and for a paid judge switched back on).
2. **Install the new plists** (skip any `launchctl list | grep parlmonitor` already shows):
   ```
   for j in us-weekly ie-weekly au-weekly us-division-watch ie-division-watch au-division-watch devolved-watch \
            prov-session-judge us-session-judge ie-session-judge au-session-judge; do
     cp ~/runner/parl-monitor/ops/launchd/net.citizengo.parlmonitor.$j.plist ~/Library/LaunchAgents/
     launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.$j.plist
   done
   ```
   The division watches' first runs brief anything on our ground from their look-back window once; preview without a DM with each tool's `--no-dm --out /tmp/x`. The four session judges need Claude Code signed in to the work account first: `claude auth status --text` must show claude.ai, not an API key (below, "Session judges").
3. **The re-derive runs for taxonomy v1.20 and v1.21**, one at a time (below, "the v1.20 retag"; the baseline `9437b29d~1` still holds for v1.21).
4. **The aph.gov.au probe** (below). The APH Web Manager was emailed on 9 October regardless.

## Next on the Mini: the v1.20 retag (9 October 2026)

Taxonomy v1.20 is merged. The US, Irish and Australian rows were re-derived by
their weeklies; the UK, devolved and EU retag ran on GitHub, did its work, and
then refused to publish because a Mini job was publishing at the same moment.
Run it here instead, then Canada's (the two commands under "Backfills" below:
`retag-backfill` with `RETAG_BASELINE=9437b29d~1`, then `ca-backfill` with
`CA_RETAG=true`). Then the US: its GitHub reclassify runs did their work twice
and lost the store race to Mini jobs both times, so run the weekly here with
both inputs (no DM: today's edition is already committed, so it is rewritten,
not resent):

    cd ~ && US_RECLASSIFY=true US_STATES_FULL=true JOB_TIMEOUT=10800 \
      nohup ~/runner/parl-monitor/tools/mini_run.sh us-weekly \
      >> ~/runner/logs/us-weekly.log 2>&1 &

One at a time: each holds the runner's lock, so starting all three just
queues them (up to LOCK_WAIT each); better to start the next when the last
has finished. Expected, from the GitHub run's dry part: sp_items +118
gained, eu_speeches refused by the trust check (its mapping is wrong, so it is
left alone, as designed).

## Next on the Mini: the aph.gov.au probe (9 October 2026)

**Why.** www.aph.gov.au and parlinfo.aph.gov.au refuse the laptop and, since
run 37887925082 the same day, GitHub's runners too (403 on robots.txt); the
High Court times out. The Mini is the last network to try before asking APH
for access. The APH Web Manager (webmanager@aph.gov.au) was emailed on 9
October 2026 asking for access; the probe still says whether the Mini is
answered meanwhile.

**Steps** (in the development clone, not the runner clone; the probe touches
no store and commits nothing):

```
cd ~/parl-monitor && git pull
mkdir -p /tmp/au-probe && python3 tools/au_probe.py --out /tmp/au-probe | tee /tmp/au-probe/summary.txt
```

It asks once per target (Bills Search, a bill homepage, ParlInfo, Votes and
Proceedings, the Journals of the Senate, the sitting calendar, committees,
Senate estimates, the High Court), honours robots.txt, waits at least 3 s
between requests, and **stops a host at its first 403 or challenge: never
retry with another User-Agent, a VPN or a browser.**

**Then:**

1. Record the table in docs/australia-scope.md, under "The aph.gov.au probe",
   as a "From the Mac Mini" row set beside the GitHub one, and commit it
   (docs only, so straight to main is fine; `git pull --rebase` first).
2. Tell Christopher in one line (Slack self-DM D05LMLVU090):
   - **Refused** (403 or challenge on aph.gov.au/ParlInfo): "APH refuses the
     Mini too; send the APH draft."
   - **Answered**: "APH answers the Mini; hold the APH draft." Then aph.gov.au
     becomes a Mini-only source, as senate.gov is GitHub-only for the US:
     phase 1b (amendment sheets, bills digests, the sitting calendar) can be
     built to run from the Mini, with the GitHub backup logging one [gap].
3. The High Court is separate: a timeout there is not a block, so note it
   and move on.

## Australia weekly (9 October 2026, branch `australia`)

docs/mac-mini-runner.md (the migration list for the launchd runner) is not on this branch, so the new job is recorded here; move this entry into that list when the branches meet.

| Job | Mini (launchd, London time) | GitHub backup (UTC) | Gate |
|---|---|---|---|
| `au-weekly` | Fridays 02:00 (`ops/launchd/net.citizengo.parlmonitor.au-weekly.plist`) | Fridays 02:00, retry 04:00 (`.github/workflows/au-weekly.yml`) | `MINI_LAST_AU_WEEKLY`, grace 200 minutes |

- **One script, two callers:** `jobs/au-weekly.sh` runs `tools/au_rollcalls.py`, the week ahead (`tools/au_schedule.py`, about 20 seconds), debates (`tools/au_debates.py`, 10-minute budget), the paid API judge when the repo variable `AU_JUDGE` is `on` (off: the free session judge, below, is the default since 9 October 2026), then the edition (`tools/au_monitor.py --edition --dm`), and on the Mini publishes the raw archive and the store itself (`raw_state.py --push`, `db_state.py --push`), as `tools/mini_run.sh` requires. It needs the store, so it carries no `no-store` line; its `# mini_run: commit editions` line makes the runner commit `editions/` too.
- **Speaks once a day**, as the US weekly: an edition already committed for today is rewritten without resending the DM.
- **On the Mini, `~/runner/env` needs** `SLACK_BOT_TOKEN` (already there for Division watch) and, only when `AU_JUDGE` is `on` (off), `ANTHROPIC_API_KEY`.
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
- **The judge** (`tools/ie_triage.py`) runs only when the repo variable `IE_JUDGE` is `on` (read with `gh variable get` on the Mini); then `~/runner/env` also needs `ANTHROPIC_API_KEY`. It is off: the free session judge (below, "Session judges") is the default.
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

## Colombia weekly (9 October 2026, branch `colombia`)

docs/mac-mini-runner.md (the migration list for the launchd runner) is not on this branch, so the new job is recorded here; move this entry into that list when the branches meet.

| Job | Mini (launchd, London time) | GitHub backup (UTC) | Gate |
|---|---|---|---|
| `co-weekly` | Thursdays 09:30 (`ops/launchd/net.citizengo.parlmonitor.co-weekly.plist`) | Thursdays 09:30, retry 11:30 (`.github/workflows/co-weekly.yml`) | `MINI_LAST_CO_WEEKLY`, grace 200 minutes |

- **One script, two callers:** `jobs/co-weekly.sh` runs `tools/co_rollcalls.py`, then publishes the raw archive and the store itself (`raw_state.py --push`, `db_state.py --push`), as `tools/mini_run.sh` requires. It needs the store, so it carries no `no-store` line.
- **Heartbeat name:** the script sets `GITHUB_WORKFLOW` to "Colombia weekly" when it is unset, so the Mini's runs reach the coverage watch.
- **Why 200 minutes of grace:** the Mini runs once and must cover both GitHub slots. 09:30 London is 08:30 UTC in summer, three hours before the 11:30 retry (half an hour later than first built: Chile holds 09:00 and 11:00).
- **Exit codes:** the collector exits 3 when it stored what it could and recorded gaps; the script publishes and exits 0 so the commit step runs. Any other failure publishes nothing and exits non-zero.
- **Install on the Mini** (after the branch is merged to main, because `mini_run.sh` records the slot only for main): `cp ops/launchd/net.citizengo.parlmonitor.co-weekly.plist ~/Library/LaunchAgents/` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.co-weekly.plist`.
- **Sources:** www.camara.gov.co, leyes.senado.gov.co and www.datos.gov.co all answered the laptop on 9 October 2026 with the honest UA. Whether the Mini's network fares differently has not been tried.

## Hungary weekly, phase 0 (10 October 2026, branch `hu-gazette`)

The Magyar Közlöny (Hungary's official gazette) and the Hungarian edition (HU6, docs/hungary-scope.md). The Országgyűlés's own site answers with a CAPTCHA, so bills and votes wait for the W-API token (HU1).

| Job | Mini (launchd, London time) | GitHub backup (UTC) | Gate |
|---|---|---|---|
| `hu-weekly` | Wednesdays 03:00 (`ops/launchd/net.citizengo.parlmonitor.hu-weekly.plist`) | Wednesdays 03:00, retry 05:00 (`.github/workflows/hu-weekly.yml`) | `MINI_LAST_HU_WEEKLY`, grace 200 minutes |

- **One script, two callers:** `jobs/hu-weekly.sh` runs `tools/hu_gazette.py` (the RSS feed, then each new issue's PDF and its contents page, one request every 2 s), then the edition (`tools/hu_monitor.py --edition --dm`, to Chris alone, once a day), then publishes the raw archive and the store itself (`raw_state.py --push`, `db_state.py --push`). Its `# mini_run: commit editions` line makes the runner commit `editions/` too.
- **The slot:** Saturday is full; nothing else starts on a Wednesday before 05:30 UTC (the coverage watch) on GitHub, or before the 08:00 day sweep on the Mini. Wednesday morning follows the Monday and Tuesday sittings, which suits phase 1's votes too.
- **The first run is the backfill:** no stored issue, so the collector reads back to the start of the term (9 May 2026) through the front-page listing; its 30-minute budget stops it cleanly and the next run resumes. It is the scheduled job's own first run, not a dispatch.
- **Heartbeat name:** the script sets `GITHUB_WORKFLOW` to "Hungary weekly" when it is unset.
- **Exit codes:** the collector exits 3 when it stored what it could and recorded gaps (an issue whose contents could not be read); the script publishes and exits 0. Any other failure publishes nothing and exits non-zero.
- **Install on the Mini** (after the branch is merged to main): `bash ops/install_country_jobs.sh` (it lists `hu-weekly`), or `cp ops/launchd/net.citizengo.parlmonitor.hu-weekly.plist ~/Library/LaunchAgents/` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.hu-weekly.plist`.
- **Source:** magyarkozlony.hu answered the laptop on 9 and 10 October 2026 with the honest UA; its robots.txt disallows nothing. Never parlament.hu.

## Hungary: the karzat backfill, by hand, once (10 October 2026, branch `hu-karzat`)

HU7: the 43rd term's papers, recorded votes and member positions from 9 May to 28 August 2026, from karzat's open data (github.com/abognar-git/karzat, `data/derived/`, CC BY 4.0), until the W-API token (HU1). karzat stopped updating around 28 August, so this is a **manual job, not a feed**: no plist, no workflow, no schedule. After the branch is merged to main, on the Mini:

    cd ~ && nohup ~/runner/parl-monitor/tools/mini_run.sh hu-karzat-backfill \
      >> ~/runner/logs/hu-karzat-backfill.log 2>&1 &

    # pin a karzat commit:          KARZAT_COMMIT=4f932a3a0513b67fc4b2adf31aa9536ae928ae16
    # reload a commit already in:   FORCE=true

- **What it does:** `jobs/hu-karzat-backfill.sh` runs `tools/hu_karzat_backfill.py` (the GitHub API for karzat's newest data commit, then four JSON files from raw.githubusercontent.com at that commit, about 4 MB, archived to `data/raw/<date>/hu-karzat_*`; never parlament.hu, never karzat's site), loads `hu_members`, `hu_papers`, `hu_divisions`, `hu_votes` and `hu_sources`, writes the one-off read for Chris, `editions/hu-karzat-backfill.md` ("since 9 May": every vote and paper on our ground, with the attribution; no DM), then publishes the raw archive and the store. `# mini_run: commit editions` commits the summary.
- **Seconds, not minutes:** measured on the laptop, the load takes under a second once the files are fetched.
- **Rerunning is safe:** every write is an upsert on the parliament's own keys; a commit already loaded is skipped unless `FORCE=true`; a row from the House's own record (the W-API, later) is never overwritten.
- **Heartbeat name:** "Hungary karzat backfill" (`tools/coverage.py` ON_DEMAND), never the weekly's.
- **After a taxonomy or watchlist change:** the weekly's `HU_RECLASSIFY=true` re-derives karzat's rows too (`tools/hu_karzat_backfill.py --reclassify`, offline).
- **The summary again, any time:** `python3 tools/hu_karzat_backfill.py --summary` (stdout) or `--out FILE`.

## Latam monthly and the Latam alerts (10 October 2026, branch `latam`)

The Latam monitor (docs/country-decisions-2026-10-10.md, "Edition structure"): one monthly edition for the fifteen CitizenGO Latam countries, to Chris alone by DM, plus instant alerts between editions.

| Job | Mini (launchd, London time) | GitHub backup (UTC) | Gate |
|---|---|---|---|
| `latam-monthly` | the 1st of each month, 13:15 (`ops/launchd/net.citizengo.parlmonitor.latam-monthly.plist`) | the 1st, 12:15, retry 15:15 (`.github/workflows/latam-monthly.yml`) | `MINI_LAST_LATAM_MONTHLY`, grace 200 minutes |

- **What it runs:** `jobs/latam-monthly.sh`: Venezuela's news check (`tools/ve_news.py`), Nicaragua's La Gaceta check (`tools/nic_gaceta.py`), the alerts for those two, then `tools/latam_monitor.py --edition --dm` and the publish. It needs the store (it reads every Latam country's tables), so it carries no `no-store` line, and it commits `editions/` (`# mini_run: commit editions`). An edition already committed for the day is rewritten, not resent.
- **The slot:** nothing on main starts at :15, and the 1st falls on any weekday, so the slot avoids every weekly's hour (the nearest: Dominican Republic weekly, Sundays 12:00; Bolivia weekly, Sundays 12:30). Saturday is untouched except when the 1st is a Saturday, and then only at :15.
- **The alerts ride on the country jobs.** Each Latam country's weekly script (`jobs/{co,cl,pe,ec,bo,uy,gt,pa,hn,sv,do}-weekly.sh`) runs `tools/latam_alerts.py --country <cc> --send` straight after its collector, on the Mini and on GitHub alike; each workflow passes `SLACK_BOT_TOKEN` to that step. The ledger is `data/latam-alerts/<cc>.json` (one file per country, so two jobs never edit one file), committed with `data/`. The first pass for a country seeds the ledger and sends nothing. On the Mini the token comes from `~/runner/env`, as for Division watch; without it the DM is reported skipped and the run goes on.
- **No consolidated `latam-weekly`.** Each country's Mini plist and GitHub workflow stay as they are: a single plist running eleven collectors in sequence would need every workflow's gate moved to one `MINI_LAST_LATAM_WEEKLY` stamp at one time, and the collectors' slots were spread on purpose (Thursday to Sunday). Guatemala stays fortnightly on GitHub (X9).
- **Heartbeat name:** "Latam monthly", watched by tools/coverage.py (31 days, 7 of grace, as the UPR monthly) and the failure alert.
- **Install on the Mini** (after the branch is merged to main): `cp ops/launchd/net.citizengo.parlmonitor.latam-monthly.plist ~/Library/LaunchAgents/` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.latam-monthly.plist`.
- **Sources:** www.asambleanacional.gob.ve (robots.txt allows all) and www.lagaceta.gob.ni (robots.txt 404, nothing disallowed; the issue PDF is embedded in each issue page) both answered the laptop on 9 October 2026 with the honest UA.

## Devolved watch and devolved member records (9 October 2026, branch `devolved-intel`)

Christopher: parity for Scotland, Wales and Northern Ireland.

**The devolved watch** (`jobs/devolved-watch.sh` -> `tools/devolved_brief.py`) is the Westminster division watch's sibling: for each NEW division on our ground at Holyrood, the Senedd or the Assembly it writes `data/briefs/<nation>-division-<id>.md` and sends one DM per run to Christopher alone (U05LJP0BT61, fixed in the tool): the question, result, tally, party split (and the designation split in NI), what matched, the link and the 5CA reading status (the signed direction per lobby, or "awaiting sign-off"). No verdicts. It speaks once per division and looks back seven days, so late publication is caught by the next slot. It touches no store (`# mini_run: no-store`); the runner commits `data/briefs` and `data/raw.json`.

- **Slots, London time:** 20:30 Mon-Thu (after Holyrood's Decision Time results, published 17:08-19:00 on 17 of 27 measured sitting days; the Senedd votes Tue/Wed evening, the Assembly divides Mon/Tue) and 12:45 Tue-Fri (Holyrood's next-morning batch, 09:10-12:22 on 7 of 27 days). At least an hour from every Westminster division watch slot on the runner lock (19:00 and 22:00 Mon-Thu; 14:00, 16:00, 18:00 Fri). GitHub's backup: `.github/workflows/devolved-watch.yml`, crons 19:30 UTC Mon-Thu and 11:45 UTC Tue, Thu and Fri (Wednesday midday is the Provinces weekly's window on GitHub), gated by `mini-check` with `MINI_LAST_DEVOLVED_WATCH`.
- **Needs** `SLACK_BOT_TOKEN` in `~/runner/env` (already there for Division watch). A run fetches Holyrood's 2026 votes (~2MB) and, when there is a division to classify, the motions dump (110MB, about 40 seconds); the Senedd index and vote XMLs; parlparse (27MB) only when a Senedd division is to be briefed; the Assembly's division list, results, member votes and Hansard.
- **First run:** it briefs anything on our ground from the last seven days once. To see what it would say first, without a DM:
  `cd ~/runner/parl-monitor && python3 tools/devolved_brief.py --no-dm --out /tmp/devolved-briefs`

Install, after `git pull` in `~/runner/parl-monitor`:
```
cp ~/runner/parl-monitor/ops/launchd/net.citizengo.parlmonitor.devolved-watch.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.devolved-watch.plist
```
A first test by hand: `RUNNER_REF=main bash ~/runner/parl-monitor/tools/mini_run.sh devolved-watch` (this sends the DM for anything new). One nation, or a longer look back: `DEVOLVED_NATION=ni DEVOLVED_SINCE=2026-09-28 bash ~/runner/parl-monitor/tools/mini_run.sh devolved-watch`.

**Member records** need no install: the Holyrood, Senedd and Assembly weeklies (`jobs/{sp,sd,ni}-weekly.sh`) now rebuild `msp-votes.html`, `ms-votes.html` and `mla-votes.html` after the 5CA sheets, and the runner commits them (`# mini_run: commit partner_site/... docs/...`). Each member's card carries "On our ground": divisions with their lobby and the signed 5CA reading where there is one, questions and motions as one line and a link, speeches, and the 5CA placement per area (`src/devolved_intel.py`). The Monday publish deploys them as before.

## Weekly country editions (10 October 2026, branch `editions-core`)

The own-edition countries (docs/country-decisions-2026-10-10.md, "Edition structure") each get a weekly edition, to Chris alone by DM, archived to `editions/<cc>-monitor-<date>.md`. One framework renders them all (`src/country_edition.py`; adapters in `src/editions/<cc>.py`; entry points `tools/<cc>_monitor.py`). First batch: Austria, the Netherlands (votes only, NL3), Belgium and Poland. Second batch (branch `editions-it-ch-fr-pt`): Italy, Switzerland, France and Portugal, in `jobs/{it,ch,fr,pt}-weekly.sh` the same way.

- **No new plists or workflows.** The edition is the last step of each country's existing weekly (`jobs/{at,nl,be,pl}-weekly.sh`), after the collector and before the publish, so it runs wherever the weekly runs: the Mini first, GitHub as the backup. A collector that failed outright (not exit 3, gaps) skips the edition.
- **Committed and spoken once a day**, as the US weekly: each script carries `# mini_run: commit editions`, each workflow commits `data/ editions/`, and an edition already committed for today is rewritten without resending the DM.
- **The DM** goes to Chris alone: the scripts default `SLACK_DM_USER_ID` to U05LJP0BT61 and the code forces it whatever the secrets say. On the Mini the token comes from `~/runner/env` (`SLACK_BOT_TOKEN`, already there); the workflows pass the secret. Without a token the DM is reported skipped and the run goes on.
- **Noise:** `config/edition-noise-<cc>.yaml` and `config/edition-mute-<cc>.yaml` (src/noise.py, the Latam filters generalised; no model, X16).

## Installing the country jobs (10 October 2026)

One command installs every country-edition job and the Latam monthly, after the runner clone has pulled main:

```
cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh
```

It skips jobs already loaded, so it is safe to rerun. Mexico's plist is only the clock that dispatches its GitHub run; Guatemala is installed only if `congreso.gob.gt` answers the Mini (GT1), otherwise it stays on GitHub. It also runs the approved reachability checks for Uruguay (UY1, parlamento.gub.uy) and Argentina (AR2, votaciones.hcdn.gob.ar). Log: `~/parl-chains/install-countries.log`.

## US, Ireland and Australia division watches (9 October 2026, branch `vote-briefs`)

Christopher: "start the same-day vote briefs" for the US, Ireland and Australia, in parity with the UK Division watch. Three jobs, each `# mini_run: no-store` (no store pulled or published; the raw archive is published), each speaking once per division (a brief in `data/briefs/<cc>-division-<key>.md` is never rewritten or resent), one DM per run to Christopher alone (`src/vote_brief.py` fixes the recipient). Shared code: `src/vote_brief.py`; tools: `tools/{us,ie,au}_division_brief.py`.

| Job | Mini (London, launchd) | GitHub backup (UTC, gated by `mini-check`) | Why (measured 9 October 2026) |
|---|---|---|---|
| `us-division-watch` (House) | 22:40 Mon-Fri; 01:40 and 04:40 Tue-Sat | `40 21 * * 1-5`, `40 0,3 * * 2-6` (`US_DIVISION_WATCH`) | the last House vote of a 2026 sitting day fell 21:00-01:00 London on 45 of 72 days, 15:00-16:00 on getaway days, 02:00-04:00 on 5; the Clerk's file is up within the hour |
| US Senate half | none: senate.gov refuses the Mini | `50 0,3 * * 2-6`, ungated (`senate` job) | the only network that can read senate.gov; about ten minutes a week |
| `ie-division-watch` | 22:50 Tue-Thu; 07:50 Wed-Fri | `50 21 * * 2-4`, `50 6 * * 3-5` (`IE_DIVISION_WATCH`) | Wednesday deferred divisions 19:00-19:40, late nights to 23:30; the API's lag is unmeasured (no per-division stamp), so an evening and a next-morning slot |
| `au-division-watch` | 01:20 and 06:20 Tue-Fri | `20 0,5 * * 2-5` (`AU_DIVISION_WATCH`) | OpenAustralia posts a sitting day at 09:05 Canberra the next morning: 22:05-00:05 London by season |

- **On the Mini, `~/runner/env` needs** `SLACK_BOT_TOKEN` (already there for Division watch). `CONGRESS_API_KEY`, already there for the US weekly, lets the US watch give a same-day House amendment vote its purpose before BILLSTATUS catches up.
- **Install on the Mini** (after the branch is merged to main, because `mini_run.sh` records the slot only for main):

```
cd ~/runner/parl-monitor && git pull --ff-only
for j in us-division-watch ie-division-watch au-division-watch; do
  cp ops/launchd/net.citizengo.parlmonitor.$j.plist ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.$j.plist
done
```

- **A dry run by hand** (prints what would be briefed, sends nothing, writes into a scratch folder): `python3 tools/us_division_brief.py --since 2026-09-15 --no-dm --out /tmp/briefs --raw-dir /tmp/raw` (same flags for `ie_` and `au_`). Optional heartbeats: `HC_US_DIVISION_WATCH`, `HC_IE_DIVISION_WATCH`, `HC_AU_DIVISION_WATCH`.

## Provinces session judge (9 October 2026, branch `prov-free-judge`)

Christopher asked for free alternatives to API-paid scoring ("Do option 2, then set up option 3"). Option 3: **Claude Code on the Mini scores the provinces' pending items on the work subscription's plan allowance, not the API.** It is the default provincial judge; `PROV_JUDGE` (the paid API judge inside the Provinces weekly) stays the alternative, and off.

- **Job:** `jobs/prov-session-judge.sh` through `tools/mini_run.sh`, Wednesdays **16:15 London** (`ops/launchd/net.citizengo.parlmonitor.prov-session-judge.plist`, `JOB_TIMEOUT` 5400), after the Provinces weekly's 11:00 slot (it queues on the runner lock if the weekly is still going) and clear of the 19:00 Division watch. **Mini only:** no GitHub workflow and no `mini-check` gate, because the CLI and the subscription live here. Heartbeat "Provinces session judge" (`tools/coverage.py` ON_DEMAND, no cadence expected); a failure DMs through `mini_run.sh` as for every job.
- **Steps:** `tools/session_judge.sh tools/prov_triage.py 100 25`: up to four rounds of `prov_triage.py --queue-out` (the newest 25 pending items, noise-muted ones left out, with the provincial frame and the text the API judge would read) -> `claude -p` fills in SCORE and WHY -> `prov_triage.py --queue-in` (strict, item by item: one digit 0-3 and a why-line or refused with its reason; written to `prov_scores` exactly as API scores are, model `claude-code-session`, once ever). It stops at 100 items offered (`SESSION_JUDGE_MAX`) or when a round scores nothing, and logs `session judge: N item(s) scored this run`. Then it rewrites the week's edition with the scores (no DM; the weekly sent it), and publishes the raw archive and the store.
- **The exact command** (in a fresh temp folder holding only `queue.md`; the prompt goes on stdin):

```
claude -p --model sonnet --tools Read,Edit --allowedTools Read,Edit \
  --permission-mode acceptEdits --strict-mcp-config --no-session-persistence \
  --restricted --permission-prompts none
```

  `--tools Read,Edit` is all it has; `--restricted` confines those to the folder and ignores user and project settings; `--permission-prompts none` denies anything that would ask; `--strict-mcp-config` loads no MCP server. `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` are unset for it, so a key in `~/runner/env` can never turn it into API spend. Tried on the laptop on 9 October 2026 with two invented items (13 seconds, both scored, file parsed clean); never against the real store there.
- **If `claude` is missing, signed out, or signed in with an API key** (`claude auth status --json` must say `loggedIn` with `authMethod` `claude.ai`), or lacks `--restricted` / `--permission-prompts`: one `[gap]` line, exit clean, the store not opened or published.
- **Install on the Mini** (after the branch is merged to main):

```
claude auth status --text          # must show the work account (claude.ai), not an API key
cd ~/runner/parl-monitor && git pull --ff-only
cp ops/launchd/net.citizengo.parlmonitor.prov-session-judge.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.prov-session-judge.plist
```

  Claude Code must be installed for the user launchd runs as (`~/.local/bin/claude` is on `mini_run.sh`'s PATH) and signed in to the **work account** (`claude auth login`). Each run uses plan allowance (four short sessions of 25 items a week at most), not API spend. A first run by hand: `cd ~ && JOB_TIMEOUT=5400 ~/runner/parl-monitor/tools/mini_run.sh prov-session-judge`.
- **Backlog:** 375 provincial items were unscored on our ground on the store of 9 October 2026 once the noise filter's mutes are left out (426 before); at 100 a week the backlog clears in four weeks, newest first. Raise `SESSION_JUDGE_MAX` in the plist's environment to go faster.
- **The US, Irish and Australian judges** adopted the same queue and runner on 9 October 2026: below.

## Session judges: US, Ireland, Australia (9 October 2026, branch `free-judges-us-ie-au`)

Christopher: "Switch US, Ireland and Australia scoring to the free route". Built on the provinces pattern above: **Claude Code on the Mini scores each country's pending items on the work subscription's plan allowance, not the API, and is the default judge.** `US_JUDGE`, `IE_JUDGE` and `AU_JUDGE` (the paid API judges inside the weeklies, whose gated steps stay) are the alternative, and go off after the merge.

| Job | Mini (launchd, London time) | Cap (`SESSION_JUDGE_MAX`) | `JOB_TIMEOUT` | Heartbeat (ON_DEMAND) |
|---|---|---|---|---|
| `au-session-judge` | Fridays **03:10**, after the Australia weekly (02:00, an hour at most), before the 04:40 US division watch | 100 (4 sessions) | 5400 | "Australia session judge" |
| `ie-session-judge` | Fridays **18:30**, after the Ireland weekly (09:30) and Friday's 18:00 Division watch | 100 (4 sessions) | 5400 | "Ireland session judge" |
| `us-session-judge` | Fridays **19:30**, after the US weekly (10:00, up to three hours) and the Ireland session judge, clear of the 22:00 Day sweep | 150 (6 sessions) | 7200 | "US session judge" |

- **Each job** (`jobs/<cc>-session-judge.sh`, through `tools/mini_run.sh`; Mini only, no GitHub workflow, no `mini-check` gate): `tools/session_judge.sh tools/<cc>_triage.py <cap> 25`, i.e. rounds of `<cc>_triage.py --queue-out` (the newest 25 pending items, with that country's frame and the very text the API judge reads: US bills, roll calls with their amendment purposes, Federal Register, the Court, Record speeches and state bills; Irish bills, divisions, questions and speeches; Australian bills, divisions and speeches) -> `claude -p` (the same confined command as the provinces) -> `<cc>_triage.py --queue-in` (strict, item by item; another judge's file, by its marker line, is refused whole). Scores go through each tool's own `apply()` onto the rows (`triage_score`, `why_it_matters`), once ever; those rows have no model column, so `session_scores` notes each one as model `claude-code-session`. Then the latest edition of the last seven days is rewritten with the scores (no DM), and the raw archive and the store are published.
- **No claude, signed out, or signed in with an API key:** one `[gap]` line, a clean exit, the store not opened or published, exactly as for the provinces. `ANTHROPIC_API_KEY` is never passed to claude.
- **Why these caps** (Christopher's work plan is "5x, keep jobs lean"; 14 sessions of 25 a week, 22 with the provinces' four and the editions' four). Measured with each tool's `--dry-run` on a scratch copy of the store published on 9 October 2026: **nothing pending in any of the three**, because the paid judges scored their first backlogs that day (US 845, Ireland 52, Australia 97 items on our ground). The newer sources are not yet in the published store, so the weekly volume comes from their scope measurements: **US** some 50 to 65 items a week (5 bills, 1 to 2 executive actions, 20 to 25 Record speeches in a sitting week, about 25 state bills out of session), plus the Record's 1,083-speech backfill landing at about 100 a week for ten weeks: 150; **Ireland** about 50 a sitting week (36 questions, 13 speeches), plus a questions and debates backfill of about 3,000 that drains at some 50 a week: 100; **Australia** about 30 a sitting week, plus a 690-speech debates backfill over three runs: 100. Newest first everywhere, so each edition's week is scored before the history. Raise `SESSION_JUDGE_MAX` in a plist's `EnvironmentVariables` to drain faster.
- **Install on the Mini** (after the branch is merged to main): in the checklist loop above, or

```
claude auth status --text          # must show the work account (claude.ai), not an API key
cd ~/runner/parl-monitor && git pull --ff-only
for j in us-session-judge ie-session-judge au-session-judge; do
  cp ops/launchd/net.citizengo.parlmonitor.$j.plist ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.$j.plist
done
```

  A first run by hand: `cd ~ && JOB_TIMEOUT=7200 ~/runner/parl-monitor/tools/mini_run.sh us-session-judge` (and `ie-`, `au-`). Then switch the repo variables `US_JUDGE`, `IE_JUDGE` and `AU_JUDGE` off (Christopher, after the merge), so the weeklies stop paying.
- **`US_RESCORE`** stays with the paid path (it runs only when `US_JUDGE` is on).

## Editions session judge (10 October 2026, branch `editions-free-judge`)

Chris approved the free session judge for the fifteen country editions and the Latam monitor (docs/country-decisions-2026-10-10.md, "The free session judge"): **Claude Code on the Mini scores their pending items on the plan allowance, not the API.** The paid API judge stays off (X16).

- **Job:** `jobs/editions-session-judge.sh` through `tools/mini_run.sh`, Sundays **16:45 London** (`ops/launchd/net.citizengo.parlmonitor.editions-session-judge.plist`, `JOB_TIMEOUT` 5400): after the week's last country weekly (Honduras, Sundays 14:00; it queues on the runner lock if one is still going), clear of every other slot (the Provinces session judge is Wednesdays 16:15) and done before the German weekly at 20:00. **Mini only:** no GitHub workflow, no `mini-check` gate. Heartbeat "Editions session judge" (`tools/coverage.py` ON_DEMAND).
- **Plan usage, kept lean** (the plan is shared with Chris's other scheduled jobs): one job a week for all sixteen editions, `tools/session_judge.sh tools/edition_judge.py 100 25`: at most 100 items (`SESSION_JUDGE_MAX`), four sessions of 25, in one order across countries: watched, then tier 1, then tier 2, newest first. The same confined `claude -p` command as the provinces judge (Read and Edit only, in a temp folder holding only `queue.md`, no MCP, `ANTHROPIC_API_KEY` unset).
- **Steps:** score; `tools/edition_judge.py --rerender --dm` rewrites in place the latest edition of each country scored today (within its cadence; the Latam edition when under a week old) and sends ONE DM to Chris only if the scores changed what leads an edition already sent; `tools/latam_alerts.py --send` for every Latam country, which sends the tier-1 items held for the judge if it scored them 2 or 3; then the raw archive and the store.
- **Why rewrite and not judge before the DM:** the country weeklies fall on six different days (Slovakia Tuesday, Hungary Wednesday, the Netherlands, Chile and Colombia Thursday, most on Saturday, Poland and five Latam countries on Sunday). Judging before each DM would mean a judge run per weekly, six sessions or more a week, against a plan Chris's other jobs share. One run after them all keeps usage to four short sessions, and the DMs stay on time; the provinces judge does the same (rewrite, no re-DM). The one "scored update" DM covers the case that matters, a different lead.
- **If `claude` is missing, signed out or on an API key:** one `[gap]` line, exit clean, nothing rewritten or published; the editions render as before and the Latam alerts stop holding once the judge has scored nothing for 14 days.
- **Install on the Mini** (after the branch is merged to main): `claude auth status --text` must show Chris's claude.ai account, then `cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh` (it installs this job with the country jobs and prints the claude sign-in state). A first run by hand: `cd ~ && JOB_TIMEOUT=5400 ~/runner/parl-monitor/tools/mini_run.sh editions-session-judge`. To see what is pending without scoring: `python3 tools/edition_judge.py`.

## Backfills run on the Mini (9 October 2026)

Dispatching a backfill to GitHub cost 2,604 Actions minutes in one week
(Provinces 2,308, Canada 296), against the 60-a-day bar for making the repo
private (the 07:30 health summary tracks it). They now run here, under the
runner's lock, with the same options as the dispatch forms; each publishes
the raw archive then the store and commits the pointers, and a failure DMs
with the end of its output. Nothing caps the clock here, but give
`mini_run.sh` a `JOB_TIMEOUT` above it.

    cd ~ && PROVINCES="nb on" SINCE=2010-01-01 MINUTES=280 JOB_TIMEOUT=18000 \
      nohup ~/runner/parl-monitor/tools/mini_run.sh prov-backfill \
      >> ~/runner/logs/prov-backfill.log 2>&1 &

    # Hansard speeches instead of votes: SPEECHES_SINCE=2010-01-01

    cd ~ && CA_OLDER_SESSIONS="43-2 43-1" CA_OLDER_PETITIONS=true JOB_TIMEOUT=14400 \
      nohup ~/runner/parl-monitor/tools/mini_run.sh ca-backfill \
      >> ~/runner/logs/ca-backfill.log 2>&1 &

    # also: CA_BACKFILL=true, CA_ROLLCALL_SESSIONS, CA_GAZETTE_SINCE (+CA_GAZETTE_FORGET),
    # CA_FEDERAL_BACKFILL="senate|committees|courts", CA_REFRESH_MEMBERS=true, CA_RETAG=true

    # After a taxonomy change: UK, devolved and EU rows (the trust check needs
    # the commit of the PREVIOUS taxonomy), then Canada's.
    cd ~ && RETAG_BASELINE=9437b29d~1 JOB_TIMEOUT=7200 \
      nohup ~/runner/parl-monitor/tools/mini_run.sh retag-backfill \
      >> ~/runner/logs/retag-backfill.log 2>&1 &
    cd ~ && CA_RETAG=true JOB_TIMEOUT=3600 \
      nohup ~/runner/parl-monitor/tools/mini_run.sh ca-backfill \
      >> ~/runner/logs/ca-backfill.log 2>&1 &

    # Hungary, once: karzat's open data, 9 May to 28 August 2026 (HU7; see
    # "Hungary: the karzat backfill" above).
    cd ~ && nohup ~/runner/parl-monitor/tools/mini_run.sh hu-karzat-backfill \
      >> ~/runner/logs/hu-karzat-backfill.log 2>&1 &

    # Slovakia, SK6: the term's backlog of bill documents (about 836 prints,
    # two and a half hours at nrsr.sk's speed); 55 minutes a run, so run it
    # three times, never on a Tuesday morning (the Slovak weekly).
    cd ~ && nohup ~/runner/parl-monitor/tools/mini_run.sh sk-docs-backfill \
      >> ~/runner/logs/sk-docs-backfill.log 2>&1 &

They record their own heartbeats ("Provinces backfill", "Canada backfill"),
never the weekly's. They hold the lock while they run, so the scheduled jobs
queue behind them (up to two hours): start a long one when the calendar is
quiet (`launchctl list | grep parlmonitor` and the plists list the times).
The GitHub dispatch forms still work, as a fallback.

The scoping probes (`*-probe.yml`, `probe-hosts.yml`) stay on GitHub: they
exist to ask whether a site answers GitHub's runners, which only a runner
can answer. They are one-off; delete each once its collector is built.

## Later phases, set A (10 October 2026, branch `parity-phases-a`)

No new scheduled job and no new plist: each phase is a step in a weekly the
Mini already runs, so `ops/install_country_jobs.sh` is unchanged. After the
merge the runner picks them up on its next `git pull` (mini_run.sh does it).

| Phase | Where it runs | What the Mini does |
|---|---|---|
| FR5, the Senat | `jobs/fr-weekly.sh`, after `fr_rollcalls.py` (Saturdays) | `tools/fr_senat.py`: one 1-byte request for the Dosleg dump's headers; downloads the 16 MB zip only when it changed and the last download is six or more days old; about 15 seconds to load. Its own heartbeat "FR Senat". |
| NL4, the Eerste Kamer | `jobs/nl-weekly.sh`, after `nl_rollcalls.py` (Thursdays) | `tools/nl_eerstekamer.py`: eerstekamer.nl's vote pages, one a second, back to two weeks before the newest stored vote. The first run reads back to June 2023: 46 pages, about 3 minutes. Heartbeat "NL Eerste Kamer". |
| IT2, the Camera's SPARQL | `jobs/it-weekly.sh`, inside `it_rollcalls.py` | Nothing new to install. `IT_CAMERA_SOURCE=openpolis` or `camera` in `~/runner/env` overrides the default `auto`. |
| CH6, Swiss Italian texts | `jobs/ch-weekly.sh`, inside `ch_rollcalls.py` | A third language pass (22 more pages on a full read, a few on a weekly one). The first weekly after the merge reads every business's Italian record once (about 6,700 have one; Fragestunde questions mostly do not and are marked so). |
| SK6, Slovak bill documents | `jobs/sk-weekly.sh` (Tuesdays): documents get the first 10 minutes of the old 45-minute positions budget | The backlog by hand: `sk-docs-backfill` above, three runs. |

