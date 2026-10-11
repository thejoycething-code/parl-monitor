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

## Chamber step: debates, speeches and questions (10 October 2026, branch `parity-debates`)

What was said and asked in the chamber, for the new country editions (parity layer 5; `src/chamber_store.py`, one collector per country, `tools/<cc>_chamber.py`). Built for the Netherlands, Switzerland, Austria, France, Belgium (speeches) and the Netherlands, Poland, France, Portugal, Brazil (questions).

- **No new plists, jobs or workflows.** Each is a step of its country's existing weekly (`jobs/{nl,ch,at,fr,be,pl,pt,br}-weekly.sh`), between the collector and the edition, through `bash tools/chamber_step.sh <cc> "$SECONDS"`, so nothing needs installing: the Mini picks it up on its next `git pull`.
- **Time-boxed to the hour.** The step gets what is left of the job's `JOB_TIMEOUT` (3600 on the Mini; Poland's is 4500) after 25 minutes for the publish and the later steps, at most ten (`tools/collector_budget.sh`); a minute or less left, it says so and skips, and the next run's three-week lookback reads what it missed.
- **Never fatal, never on GitHub.** A failure is a `[gap]` line (and a row in `gaps`); the store, the edition and the publish go on. On GitHub (`GITHUB_ACTIONS=true`, the backup) the step is skipped: the backups' timeouts are 30 to 60 minutes and the Mini catches up.
- **First run reads from 1 September 2026**, so the tables are not empty when tools/coverage.py starts watching them (`<CC> chamber` step heartbeats, AWAITING_FIRST_RUN until then). Austria's first run takes two or three weeklies to drain (one request per speech).
- **Reclassify:** each `<CC>_RECLASSIFY=true` run also runs `tools/<cc>_chamber.py --reclassify`.
- **By hand on the Mini** (one writer at a time; never while a weekly runs): `cd ~/runner/parl-monitor && python3 tools/nl_chamber.py --since 2026-09-01`.

## Week ahead for the country editions (10 October 2026, branch `parity-week-ahead`)

Handover item 4. `tools/country_agenda.py <cc>` reads a country's agenda into the shared `country_agenda` table (src/agenda.py; one source module per country in `src/agendas/`), matches each point to the store's bills by number and flags watched and tier-1 points; the edition's "Week ahead" section shows the next fortnight and its Coverage line says how far the agenda reaches and when the next sitting is.

- **A step, not a job.** It runs inside `jobs/{nl,pl,ch,br,it,fr,at,es,ar}-weekly.sh`, after the collector and before the edition, so it needs no plist, no workflow and no slot: nothing to install beyond the usual `git pull`. Its failure is a `[gap]` line; it never stops the publish or the edition. It adds well under a minute to each weekly (NL one OData page, PL one call, CH two, BR up to 80 pautas at a second each, IT two pages, FR one 8 MB zip, AT the Termine list and up to 40 agendas, ES and AR three or four week pages).
- **Sources:** NL Tweede Kamer OData (Activiteit, Agendapunt); PL Sejm API proceedings (planned sittings included); CH Parliament Webservices (Meeting, Subject: empty between sessions); BR Câmara eventos and pauta, Senado plenary agenda; IT the Camera's Assembly calendar (the Senate refuses us); FR the AN's Agenda.json.zip (archived, as FR3); AT Termine and Tagesordnungen (robots.txt checked per document); ES the Congreso's weekly agenda page (dissolved until 23 December: the section fills when the XVI sits); AR the Senate's agenda of activities (cultural events left out; not the Diputados agenda on www.hcdn.gob.ar).
- **A failed read keeps the last good one**: the edition shows it with its date in the Coverage line, and the gap is in the gaps table as `<cc>-agenda`. The Sejm API did not answer the laptop at times on 10 October (40 s timeouts); with the client's retries the PL step can take a few minutes before it gives up.
- **By hand:** `python3 tools/country_agenda.py pl --db /tmp/x.db` reads into a scratch store; never run it on the runner's store while a weekly is publishing.

## Petitions and consultations for the country editions (11 October 2026, branch `ukp-petitions-consult`)

`tools/country_petitions.py <cc>` reads a country's petitions, citizens' initiatives and government consultations into the shared `country_petitions` table (src/petitions.py; one source module per country in `src/petition_sources/`), classifies them with the country's taxonomies, snapshots signature counts, and the edition's "Petitions and consultations" section shows the new ones on our ground, thresholds crossed and deadlines.

- **A step, not a job.** It runs inside `jobs/{fr,at,ch,it,pt,pl,be,nl,br,ar,co}-weekly.sh`, after the collector and before the edition (Colombia's rows go to the monthly Latam edition), so there is no plist, workflow or slot to add: nothing to install beyond the usual `git pull`. Its failure is a `[gap]` line (`<cc>-petitions-<source>` in the gaps table) and never stops the publish or the edition. Each `<CC>_RECLASSIFY=true` run also runs `--reclassify`.
- **Time:** seconds for most (one to three requests). France reads 21 listing pages and up to 60 item pages a run (a few minutes on the first runs, while the Sénat's 89 and the AN's matching petitions are read). Brazil's e-Cidadania pages take 20 seconds to several minutes each (measured 11 October): each listing stops paging after 10 minutes, and item pages stop at 15 a run (`--detail-limit 15`) or once the country's step is 10 minutes old (`DETAIL_SECONDS`, every country), so the Brazilian step is bounded at about half an hour and the rest is read next week.
- **The first run is the baseline**: everything already open is stored but not shown as new; only items opened in the edition's window are. From the second run, new items, thresholds crossed and 10,000-signature weeks appear.
- **Campaign view:** `python3 tools/country_petitions.py it at --report` prints every open item on our ground, nearest a threshold first, offline (read-only).
- **By hand:** `python3 tools/country_petitions.py fr --db /tmp/x.db` into a scratch store; never on the runner's store while a weekly is publishing.

## Member profiles in the country weeklies (10 October 2026, branch `parity-profiles`)

Handover item 3: one Markdown profile per member with a record on our ground, for the 23 countries with a member list (`profiles/<cc>/`, an `index.md` per country), from `src/member_profiles.py` through `tools/member_profiles.py <cc>`.

- **No new plists, workflows or cron slots.** It is a step of each country's existing weekly (`jobs/<cc>-weekly.sh`; Mexico's `jobs/mx-collect.sh` on GitHub), after the collector and before the publish, only when the collector stored something (exit 0 or 3). It reads the store and takes seconds; a failure is a `[gap] member-profiles` line and never costs the store.
- **Committed with the store:** each script's `# mini_run: commit` line now names `profiles` (beside `editions` where the country has one), and each workflow's commit step adds `profiles/`. The directory is rewritten whole: a member who no longer has a record loses their file. Nothing is posted or DMed.
- **Croatia** first reads plenary transcripts for party history (`tools/hr_party_history.py`, X6): edoc.sabor.hr, one request a second, newest first, ten minutes a run (`HR_TRANSCRIPT_SECONDS`); the 11th Sabor's ~950 transcripts drain over the first few weeks, then a run reads the week's new ones.
- **Chile** first asks the BCN for senators' party history (`tools/cl_senate_parties.py`, one SPARQL request to datos.bcn.cl, which asks for a 10-second crawl delay).
- Nothing to install on the Mini beyond the usual `git pull` of the runner clone.

## Member intelligence in seven country weeklies (11 October 2026, branch `ukp-member-intel`)

Committees, cross-party groups and registers of interests (`tools/member_intel.py <cc>`, `src/member_intel.py`) for BR, NL, CH, PL, FR, IT and AT, into the store's `mi_groups`, `mi_interests` and `mi_runs`; the profiles step that follows shows them (handover section 3b).

- **No new plists, workflows or cron slots.** A step of `jobs/<cc>-weekly.sh` for those seven, just before the member profiles, only when the collector stored something (exit 0 or 3). A failure is a `[gap] member-intel` line; last week's rows stand and the store is still published.
- **Cost per run:** PL one request; AT two; IT one SPARQL query; FR the 5 MB AMO10 zip; CH about four OData pages; NL about a dozen OData pages; BR one 7.7 MB bulk file, four pages of fronts, then the members of the 8 fronts on our ground and an eighth of the other 312 (about 50 requests at 3 s, under three minutes). `python3 tools/member_intel.py br --full` reads every front at once (about 15 minutes) and is never needed in the weekly.
- **Coverage:** `mi_runs.last_seen` is watched (`tools/coverage.py`, cadence 7, grace 4); the log line `member-intel <cc>:` says what each source gave.
- Nothing to install beyond the usual `git pull` of the runner clone.

## Attendance in five country weeklies (11 October 2026, branch `ukp2-attendance`)

Who attended the committee and plenary sittings (`tools/country_attendance.py <cc>`, `src/attendance.py`) for BR, FR, CL, NL and CO, into the store's `att_sittings`, `att_marks`, `att_referrals` and `att_runs`; the profiles step that follows shows it, and the debate packs show who attended the committee handling the bill (handover section 3c). Plenary vote participation for IT, CH, PL, ES, AR, PE, DO and HU is derived from the stored votes at render time: no step, no fetch.

- **No new plists, workflows or cron slots.** A step of `jobs/<cc>-weekly.sh` for those five, after member intelligence and just before the member profiles, only when the collector stored something (exit 0 or 3). A failure is a `[gap] attendance` line; last week's rows stand and the store is still published.
- **Cost per run (measured 11 October 2026 from the laptop):** BR about 75 s (the 9 MB presence CSV, not archived because the year's file is republished whole each night; the event and organ files; one tramitações request for each of the 38 bills on our ground); FR the 8.4 MB Agenda zip, a few seconds; NL two OData pages; CO nothing fetched (copied from `co_attendance`); CL about 5 minutes on the first run (98 plenary sessions of 2026 at one request each), then only the week's new sessions plus the committee list and one request per committee.
- **Backfill (optional, by hand on the Mini, outside the overnight window):** `python3 tools/country_attendance.py br cl --years 2025 2026` reads the previous year as well. Not needed for the profiles; it lengthens the period the counts cover.
- **Coverage:** `att_runs.last_seen` is watched (`tools/coverage.py`, cadence 7, grace 4); the log line `attendance <cc>:` says what each source gave.

## Length of service in eighteen country weeklies (11 October 2026, branch `ukp2-service`)

Every period each member has sat and their dated groups (`tools/member_service.py <cc>`, `src/member_service.py`), into the store's `ms_periods`, `ms_party` and `ms_runs`; the profiles and the vote pages read them (handover section 3c).

- **No new plists, workflows or cron slots.** A step of `jobs/<cc>-weekly.sh` (Mexico's `jobs/mx-collect.sh`) for CH, NL, FR, AT, PT, IT, ES, PL, BR, SK, HR, BE, CL, HU, AR, PE, DO and MX, just before the member profiles, only when the collector stored something (exit 0 or 3). A failure is a `[gap] member-service` line; last run's rows stand and the store is still published.
- **Cadence:** the tool reads a source only when it is due (`STALE_DAYS`): weekly for CH and NL (a few requests) and the six store-only countries (CL, HU, AR, PE, DO, MX: no fetch); every four weeks for FR (AMO30, 13 MB), PT (17 files), IT (19 SPARQL queries), ES (17 files), PL (8 terms), SK (9 terms), HR (about 20 pages), BE (9 pages at the Chamber's 5-second crawl delay), AT (one biography a member, about 243 at a second each) and BR (one request a member, about 600; a 25-minute budget). AT and BR read the longest-unread members first; members not reached keep their last rows, and a run cut short is due again the next week. `--force` reads now.
- **Coverage:** `ms_runs.last_seen` is watched (`tools/coverage.py`, cadence 7, grace 4); the log line `member-service <cc>:` says what each source gave, or that it was not due.
- Nothing to install beyond the usual `git pull` of the runner clone.

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

## Vote briefs for the new countries (10 October 2026, branch `parity-vote-briefs`)

Handover item 1 (docs/country-parity-handover.md): same-day vote briefs, the UK division watch's rules, for the twenty new countries with member votes. Shared code `src/country_vote_brief.py`, daily readers `src/vote_brief_sources.py`, tool `tools/country_vote_briefs.py`. Watched and tier-1 votes only (the edition's own reader and noise rules; a tier-1 vote the session judge read needs 2 or 3), one brief per bill per day in `data/briefs/<cc>-votes-<date>-<key>.md` naming every member who voted against their group's majority (X6 countries name nobody; X5 countries say the positions are derived), ONE DM per run to Chris alone, de-duplicated in `data/vote-briefs/<cc>.json` (the first pass per country seeds silently).

- **After each weekly collection (no new job):** a step in `jobs/<cc>-weekly.sh` for Italy, Switzerland, France, the Netherlands, Belgium, Poland, Croatia, Slovakia, Spain, Brazil, Argentina (Senate), Austria and Portugal (X5, derived), Chile, Peru, Ecuador, the Dominican Republic, El Salvador and Guatemala (GitHub, fortnightly), and `jobs/mx-collect.sh` for Mexico (GitHub, fortnightly): `python3 tools/country_vote_briefs.py --country <cc> --send`, over 14 days, after the collector, never stopping the run. In the Latam jobs it runs before `latam_alerts.py`, which no longer alerts a vote the brief has sent. Poland's step also writes `data/vote-briefs/pl-parents.json` (the processes on our ground and their prints) for the daily reader.
- **Daily, one job:** `jobs/vote-briefs-daily.sh` (`# mini_run: no-store`), **21:40 London Mon-Fri and 06:40 Tue-Sat** (`ops/launchd/net.citizengo.parlmonitor.vote-briefs-daily.plist`, `JOB_TIMEOUT` 1200), clear of every other slot. It reads the Netherlands (Tweede Kamer OData, one request), Poland (Sejm API: index, the sittings in the window, positions for the votes to brief), Switzerland (Nationalrat OData during a session), Brazil (Câmara API v2 and Senado) and Italy (Senate SPARQL, Openpolis) for the last three days into a throwaway store in a temporary folder, briefs, and publishes the raw archive. A reader that fails is a `[gap]` line. **Mini only:** no GitHub workflow (each weekly step is the backstop); heartbeat "Daily vote briefs" (`tools/coverage.py` ON_DEMAND). France is not daily: the Assemblée publishes only a 27 MB nightly zip, and a ranged read of its newest members is unsafe (its CDN served two builds of the file to successive range requests on 10 October).
- **Measured on 10 October 2026 from the laptop:** the daily pass took 30 seconds (the Netherlands' 6 October votes: 18 votes, 9 briefs; Poland's sitting 66: 166 votes, none watched or tier 1; no Swiss session; Brazil in its election recess). `dati.senato.it` answered **403** to the laptop, and the Sejm's print endpoints timed out (hence the store map); both readers fail cleanly. Whether the Mini reaches `dati.senato.it` is the first thing to check in the job's log.
- **Install on the Mini** (after merge): `cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh` (it now lists `vote-briefs-daily`). A dry run by hand, nothing sent or recorded: `python3 tools/country_vote_briefs.py --daily --no-seed --out /tmp/briefs --raw-dir /tmp/raw`; from the store: `python3 tools/country_vote_briefs.py --country pl --since 2026-09-01 --no-seed --out /tmp/briefs`. Samples: `docs/vote-brief-samples/`.

## Daily sweep of new items for the new countries (11 October 2026, branch `ukp-day-sweep`)

The UK day sweep's same-day alert for what is NEW on our ground (bills, motions, questions, agenda points), not only votes. **A step of the daily vote-briefs job above, not a new job:** `jobs/vote-briefs-daily.sh` runs `tools/country_vote_briefs.py --daily --send`, which reads the votes, then the new items, into the same throwaway store and sends **ONE DM** to Chris (the vote briefs first, then the new items; nothing at all when there is nothing). Same slots (21:40 Mon-Fri, 06:40 Tue-Sat London), same lock, same `JOB_TIMEOUT` 1200; no plist, no workflow, no install step beyond the merge (the runner clone picks it up on its next pull). Shared code `src/country_day_sweep.py`, readers `src/day_sweep_sources.py`.

- **What alerts:** kinds new, question and agenda from the edition's own reader (noise rules and mute list applied) plus the reader's own items where the edition lacks the kind (the Dutch motions: the Dutch edition stays votes, speeches and questions, NL3); watched, or tier 1 with the noise rules' minimum evidence; a judged item only at 2 or 3 (the daily job pulls no store, so it judges by evidence, as the vote briefs do).
- **Never twice, never what Chris has seen:** `data/day-sweep/<cc>.json` (committed with `data/`; the first pass per country seeds silently), the country's editions of the last 21 days (`editions/<cc>-monitor-<date>.md`, samples ignored), and the run's own vote briefs (an item on a bill a qualifying vote is on is left to the brief). Every item alerted in a run is written to `data/briefs/day-sweep-<date>.md`; the DM shows at most 20.
- **Countries and cost** (measured 11 October 2026 from the laptop; the whole daily run, votes and sweep, took about 45 s): the Netherlands (new Moties, Amendementen and bills by `GestartOp`, Kamervragen, the agenda: 3 requests), Poland (the newest 150 processes, interpellations and written questions, the proceedings: 4), Switzerland (businesses submitted in the window, German and French, the sessions programme: 3-4), Brazil (the Câmara's PL, PLP, PEC and PDL presented in the window, requests for information, the pauta: 3 + a pauta per deliberative event), Italy (Senate SPARQL bills presented in the window, the Camera's calendar: 4), Austria (the item list for each chamber restricted by `DATUM_VON` to the window, the Termine and their Tagesordnungen: 3 + agendas), France (the Assemblée's Agenda.json.zip only, 8.4 MB, **once a day**, archived only on a day it alerts; bills and questions are weekly-only nightly dumps of 10.7 and 55 MB), Spain (the Congreso's two initiative files and its agenda **from 23 December 2026**; skipped before).
- **Switches:** `DAY_SWEEP=off` in the job's environment briefs the votes only; by hand, `--no-sweep` or `--sweep-only`. A dry run, nothing sent or recorded: `python3 tools/country_vote_briefs.py --daily --sweep-only --no-seed --out /tmp/briefs --raw-dir /tmp/raw`. Samples: `docs/day-sweep-samples/`.
- **First runs on the Mini:** the first sweep pass per country seeds `data/day-sweep/<cc>.json` silently, so the first DM with new items comes on the second run. Check the log for `[gap]` lines (the Sejm API timed out on the laptop on 10 October; the Mini reads it for the weekly).

## Editions session judge (10 October 2026, branch `editions-free-judge`)

Chris approved the free session judge for the fifteen country editions and the Latam monitor (docs/country-decisions-2026-10-10.md, "The free session judge"): **Claude Code on the Mini scores their pending items on the plan allowance, not the API.** The paid API judge stays off (X16).

- **Job:** `jobs/editions-session-judge.sh` through `tools/mini_run.sh`, Sundays **16:45 London** (`ops/launchd/net.citizengo.parlmonitor.editions-session-judge.plist`, `JOB_TIMEOUT` 5400): after the week's last country weekly (Honduras, Sundays 14:00; it queues on the runner lock if one is still going), clear of every other slot (the Provinces session judge is Wednesdays 16:15) and done before the German weekly at 20:00. **Mini only:** no GitHub workflow, no `mini-check` gate. Heartbeat "Editions session judge" (`tools/coverage.py` ON_DEMAND).
- **Plan usage, kept lean** (the plan is shared with Chris's other scheduled jobs): one job a week for all sixteen editions, `tools/session_judge.sh tools/edition_judge.py 100 25`: at most 100 items (`SESSION_JUDGE_MAX`), four sessions of 25, in one order across countries: watched, then tier 1, then tier 2, newest first. The same confined `claude -p` command as the provinces judge (Read and Edit only, in a temp folder holding only `queue.md`, no MCP, `ANTHROPIC_API_KEY` unset).
- **Steps:** score; `tools/edition_judge.py --rerender --dm` rewrites in place the latest edition of each country scored today (within its cadence; the Latam edition when under a week old) and sends ONE DM to Chris only if the scores changed what leads an edition already sent; `tools/latam_alerts.py --send` for every Latam country, which sends the tier-1 items held for the judge if it scored them 2 or 3; then the raw archive and the store.
- **Why rewrite and not judge before the DM:** the country weeklies fall on six different days (Slovakia Tuesday, Hungary Wednesday, the Netherlands, Chile and Colombia Thursday, most on Saturday, Poland and five Latam countries on Sunday). Judging before each DM would mean a judge run per weekly, six sessions or more a week, against a plan Chris's other jobs share. One run after them all keeps usage to four short sessions, and the DMs stay on time; the provinces judge does the same (rewrite, no re-DM). The one "scored update" DM covers the case that matters, a different lead.
- **If `claude` is missing, signed out or on an API key:** one `[gap]` line, exit clean, nothing scored or rewritten (only the store is published, for the rule-made vote meanings, below); the editions render as before and the Latam alerts stop holding once the judge has scored nothing for 14 days.
- **Install on the Mini** (after the branch is merged to main): `claude auth status --text` must show Chris's claude.ai account, then `cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh` (it installs this job with the country jobs and prints the claude sign-in state). A first run by hand: `cd ~ && JOB_TIMEOUT=5400 ~/runner/parl-monitor/tools/mini_run.sh editions-session-judge`. To see what is pending without scoring: `python3 tools/edition_judge.py`.

## Vote meanings for the new countries (11 October 2026, branch `ukp-meanings`)

What a Yes and a No actually meant, in plain English, for every watched and tier-1 vote in the new countries with recorded votes (src/vote_meanings.py, tools/vote_meanings.py; the UK's `meaning_aye`/`meaning_no` lines generalised). **No new job and no new plist**: two steps inside `editions-session-judge` (Sundays 16:45).

- **First, offline, seconds:** `tools/vote_meanings.py --rules` stores the rule line of each such vote in the store's `vote_meanings` table (from the vote's own wording, the kind of vote and the bill's English description in the watchlist or `bill_directions`).
- **Then, AFTER the editions' scores and inside the same weekly budget:** the job reads how many items the scores were offered (`session judge: ...; N offered, cap 100`) and gives what is left to `tools/session_judge.sh tools/vote_meanings.py <left> 25`, with the YES/NO prompt (`SESSION_JUDGE_PROMPT`, an additive option of session_judge.sh). So the week never goes over about 100 items in all; when the scores use them all, the meanings wait a week. The judge is offered only votes the rules cannot read and rule lines that quote a source title because no English description is on file, watched first, newest first. `UNCLEAR` is stored and not offered again.
- **If `claude` is signed out:** the rule lines are still stored and the store is published; nothing else changes.
- **A person overrides any line** in `config/vote-meanings-<cc>.yaml` (`meaning_yes`, `meaning_no`, `by`, `"on"`), as the UK does in its stance files; `python3 tools/vote_meanings.py --check` lists problems. The person's line wins everywhere at the next render.
- **Shown in:** the editions and the Latam monitor (under each watched or tier-1 vote), the same-day vote briefs and their DM, member profiles ("their vote meant"), debate packs (labelled in the pack's language, the line in English) and the 5CA readings guides. Rule lines are computed at render time too, so a vote newer than the last Sunday run still shows one.
- **By hand:** `python3 tools/vote_meanings.py` (counts by country and what waits for the judge), `--show pl` (each vote's lines).

## Courts, Bolivian questions, Uruguay's Diario totals and OCR (10 October 2026, branch `parity-phases-b`)

Parity work, set B (docs/country-parity-handover.md, item 6). **No new
scheduled job and no new plist**: each piece is a step inside a country
weekly that already runs on the Mini (and on its GitHub backup), after the
collector and before the alerts or the edition. Each records its own gaps in
the store and never stops its weekly.

| Weekly (existing slot) | New step | What it reads | Added time |
|---|---|---|---|
| `co-weekly` (Thu 09:30) | `tools/co_courts.py` (X8, CO4) | the Corte Constitucional's exhortations file, datos.gov.co `fbtr-7k2r`, whole | one request |
| `ec-weekly` (Sat 15:30) | `tools/ec_courts.py` (X8) | the Corte Constitucional's WordPress API: judgment summaries, bulletins, statements since 30 days before the newest held | 1-2 requests |
| `pe-weekly` (Sat 16:00) | `tools/pe_courts.py` (X8) | the Tribunal Constitucional's press notes, at its robots.txt Crawl-delay of 30 s | about 4 minutes |
| `pe-weekly` | `tools/pe_ocr.py` (X7) | Tesseract over the scan-only vote records; skips without Tesseract | 0 until installed |
| `pt-weekly` (Sat 15:00) | `tools/pt_courts.py` (X8) | the Tribunal Constitucional's acórdãos: 30 s apart, at most ten read, no retries; a 429 ends it with one gap | about 6 minutes |
| `bo-weekly` (Sun 11:00) | `tools/bo_questions.py` (BO4) | written questions, Senado API and Diputados WordPress, newest three pages each | about 10 s |
| `uy-weekly` (Sun 08:00) | `tools/uy_diario.py` (UY5) | up to four new Diarios de Sesiones (PDF, pypdf), vote totals only | about 1 minute |

The Uruguay workflow now installs `pypdf==6.14.2`, as Peru's does; the
Portugal workflow's timeout is 40 minutes (was 30).
Portugal, Ecuador and Peru share Saturday afternoon (15:00, 15:30, 16:00):
Portugal's few extra minutes can push Ecuador's start back behind the
runner's lock, which queues it; nothing is lost.

**Once, by hand, after the merge and before those weeklies' next runs**, the
backlog (the editions treat what a table holds on its first day as history,
never as news, so this seeds them quietly):

    cd ~ && JOB_TIMEOUT=3600 nohup ~/runner/parl-monitor/tools/mini_run.sh latam-courts-backfill \
      >> ~/runner/logs/latam-courts-backfill.log 2>&1 &

`jobs/latam-courts-backfill.sh`: Colombia's file, Ecuador's Court since
2019, Peru's whole press-note archive (the RSS feed, 4,378 notes, 15 MB, one
request), every Bolivian question (after refreshing the members), and the L
legislature's Diarios (about 80 PDFs). About 25 minutes; heartbeat "Latam
courts backfill" (ON_DEMAND). Portugal's court is not backfilled: it is read
ten rulings a week.

### OCR (Tesseract, X7)

Approved 10 October 2026 (X7): Tesseract, free and local, reads the scans
no text layer covers: Peru's signed vote records (wired: `tools/pe_ocr.py`
in `pe-weekly`), and, once their document layers exist, Croatia's
opposition bills and Colombia's Gazette vote registers. Design and limits:
`src/ocr.py`. **Nothing is installed by the code**, and every step skips
cleanly ("[skip] pe-ocr: tesseract not installed") until this is done.

To install, on the Mini, as the runner's user (Homebrew, no paid service):

    brew install tesseract tesseract-lang
    tesseract --version                       # 5.x
    tesseract --list-langs | grep -E '^(spa|hrv)$'   # both must be listed

`tesseract-lang` brings every language's data (spa for Peru and Colombia,
hrv for Croatia; about 650 MB). If launchd's PATH lacks Homebrew's bin,
`src/ocr.py` also looks in `/opt/homebrew/bin` and `/usr/local/bin`, or set
`TESSERACT_CMD` in the job's environment. Check without reading anything:

    cd ~/runner/parl-monitor && python3 tools/pe_ocr.py --check

What it does once installed: up to three scan-only Peru vote records a run
(`pe_vote_files.text_layer = 0`), each page's embedded image through
`tesseract -l spa --psm 6`, the text stored in `pe_vote_ocr` with the
engine's version. **It parses no positions**: a parser for OCR'd vote
sheets, tested against hand-checked sheets, is the next step and is not
built. GitHub's runners have no Tesseract, so the backup skips the step.
## New-country 5CA stance steps and the sign-off digest (10 October 2026, branch `parity-5ca`)

Three offline steps at the head of `jobs/editions-session-judge.sh` (Sundays 16:45 London, Mini only), after the week's country weeklies and before the judge; no new job, no new slot, no GitHub workflow:

- `python3 tools/country_5ca.py --all-countries --prune-off-ground --draft --signoff-doc --sheets --shortlist`: first (`--prune-off-ground`, 11 October 2026) removes the unsigned, untouched entries whose vote a reclassification took off our ground (a confirmed or hand-edited one is kept and reported; the shortlist sinks it with the command); then, for each new country with member-level or party-group votes (IT, CH, FR, NL, BE, PL, HR, SK, ES, BR, AR, MX, HU, AT, PT, CL, PE, EC, DO, SV, GT), appends drafts for the week's new watched and tier-1 votes to `config/<cc>_stance.yaml` (rules, no AI; an existing entry is never touched), rewrites `docs/5ca-<cc>-readings.md` (a box ticked but not yet applied stays ticked), writes `data/5ca/<cc>-5ca-*.csv` from CONFIRMED readings only, and (`--shortlist`, 11 October 2026, src/shortlist5ca.py) rewrites `docs/5ca-<cc>-shortlist.md`, the waiting readings ranked by what to sign first, with each one's exact command (it confirms nothing). Seconds; reads the store, writes no table.
- `python3 tools/make_country_5ca_web.py` (camp-5ca-sheets, 10 October 2026): the new countries' 5CA tracker and partner sheet, one page with a country switcher. `docs/5ca-countries.html` (internal) every week, every country: area sheets from confirmed readings, or "Awaiting sign-off: N readings" and no placement. `partner_site/5ca-countries.html` only for the countries with a confirmed reading that places someone; with none it is not written (and a stale one is removed), and the partner nav links it only while it exists. Monday's deploy ships it. Change since last week: `data/5ca/country-web-state.json`. Seconds; reads the store only for a country with a confirmed reading.
- `python3 tools/country_5ca_post.py --all-countries --refresh` (ukp3-5ca-post, 11 October 2026): the new countries' 5CA for Chris alone. Each chamber and area with a CONFIRMED reading that places someone (the `publishable_sheets` gate) becomes a canvas shared with his user id only (forced, never a channel); a later run rewrites the same canvas in place, and `--refresh` touches only the canvases whose confirmed readings changed (a withdrawn reading rewrites its canvas to "no placement now"). One DM lists the canvases touched. Nothing confirmed or nothing changed: no Slack call, no message. Canvas ids and fingerprints: `data/5ca/country-post-state.json` (committed with data/). By hand: `--cc CC [--area N] [--to canvas|dm|both] [--dry-run]`.
- `python3 tools/stance_digest.py --dm`: one DM to Chris, at most once per ISO week (`data/stance-digest/<year>-W<week>.md` records the send), leading with each country's top 5 readings to sign first (the shortlist's ranking), then one line of counts. Nothing waiting, nothing sent.
- Commit: `# mini_run: commit editions config docs partner_site` (the job writes `config/*_stance.yaml`, `docs/5ca-*-readings.md`, `docs/5ca-countries.html` and, once a reading is confirmed, `partner_site/5ca-countries.html`). A failure in either step is a `[gap]` line; the judge still runs.
- **Nothing on the Mini confirms a reading.** Confirming is `python3 tools/country_5ca.py --cc CC --sign-from-doc --by NAME` (or `--confirm KEY --by NAME`), run by a person on a laptop, then pushed. `--by` must be Chris or a name in `config/stance_signers.yaml`.
- Install: nothing new; the next `git pull` on the runner picks the steps up.

## New-country vote pages, vote tracker and bill timelines (11 October 2026, branch `ukp-vote-pages`)

One offline step in `jobs/editions-session-judge.sh` (Sundays 16:45 London, Mini only), after the judge's rewrite so its scores decide what is on our ground, and also on a judge gap (exit 3), since the pages need no judge; no new job, no new slot, no GitHub workflow:

- `python3 tools/make_country_votes.py`: `partner_site/<cc>-votes.html` for each new country with votes on our ground (a country with none gets no page, a stale one is removed), `partner_site/votes-countries.html` (the tracker) and `partner_site/bill-timelines.html` (watched bills). Reads the store and `config/` only, about a minute; writes no table. Records only: no vote is labelled for or against our side until its reading is CONFIRMED.
- Commit: the job's existing `# mini_run: commit editions config docs partner_site`; Monday's deploy ships the pages behind the partner passphrase. A failure is a `[gap]` line; last week's pages stand.
- Install: nothing new; the next `git pull` on the runner picks the step up.

## New-country campaign brief drafts (10 October 2026, branch `camp-briefs`)

One offline step in each new country's weekly job (`jobs/<cc>-weekly.sh` for the fourteen own editions and the eleven collected Latam countries, `jobs/mx-collect.sh` for Mexico, which collects on GitHub), after the collector and the edition or alerts, before the publish; no new job, no new slot:

- `python3 tools/country_briefs.py --cc CC`: drafts an RF4 Campaigns Brief (`briefs/<cc>-<title>-<key>.md` and `.csv`, plus `-5ca.csv` once CONFIRMED readings place anyone) for each watched or tier-1 bill that moved in the last 90 days, at most eight new ones a run; refreshes the unedited briefs it wrote before (a fingerprint in `data/country-briefs/<cc>.json`), leaves an edited one alone. Campaigner text in the country's language (`config/country-briefs.yaml`), facts from the store only, no AI call. Every brief is **NOT READY** (banner, form Notes line, `brief_log` status `not-ready`) until the bill's direction and every reading of its watched or tier-1 votes in `config/<cc>_stance.yaml` are confirmed by a named person; then `draft`. Seconds; writes `brief_log` rows in the store before it is published.
- Commit: `briefs` added to each job's `# mini_run: commit` line, and `briefs/` to each workflow's `git add`. A failure is a `[gap]` line; the store is still published.
- **It sends nothing**: no DM, no Asana task (the UK and German editions carry no brief line, so the country editions do not either). `not-ready` and `draft` are not statuses the UK Drive publisher picks up; the Sunday Drive step below puts them on Drive (11 October 2026).
- **Nothing on the Mini confirms anything.** A bill's direction is confirmed on a laptop with `python3 tools/country_5ca.py --cc CC --confirm-direction KEY --by NAME` (readings as above), then pushed; the next weekly refreshes the brief.
- Install: nothing new; the next `git pull` on the runner picks the step up.

## Health summary and Drive for the new countries (11 October 2026, branch `ukp-health-drive`)

No new job, no new plist, `ops/install_country_jobs.sh` unchanged: the runner picks both up on its next `git pull`.

- **Health summary** (the 07:30 `health` job, `tools/health_summary.py`, new `src/country_health.py`): one section, "Country editions (new countries)", with one line per region (Europe: the twelve European countries, the `sk-docs-backfill` and `hu-karzat-backfill`; Latam: the fourteen Latin American countries, `latam-monthly` and `latam-courts-backfill`) and one for the shared jobs (`vote-briefs-daily`, `editions-session-judge`). A clean region is one line ("all 12 jobs ok, editions 12/12 current, no step gaps"). Otherwise the headline counts, then: failed jobs (the stage, last good run), unfinished ones, stale ones (no good Mini run within the job's cadence plus a grace: 1 day for daily, 2 for weekly, 3 for fortnightly, 7 for monthly; the cadence from `tools/coverage.py` PIPELINES when the job stamps a heartbeat there, else from its plist), these countries' overdue sources from `coverage.check` (taken out of the general "Overdue sources" list, whose heading says how many moved), step gaps in each job's last run by step (edition, vote briefs, judge, agenda, chamber, courts, backfill, profiles, briefs, drive, alerts), editions older than their cadence (`editions/<cc>-monitor-<date>.md`), jobs with no Mini run yet, and the collectors' own source gaps as one count per country. The Mini list above it no longer names these jobs' failures one by one ("N more on the new countries' jobs"). Reads the Mini's logs and the store only. Try it on a copy of the logs: `python3 tools/health_summary.py --logs DIR --offline`.
- **Drive** (a step of the Sunday 16:45 `editions-session-judge`, after the 5CA steps and before the judge, so a judge gap never skips it; `tools/country_drive.py`, `src/country_drive.py`): the new countries' campaign briefs become Sheets copied from the UK brief template (`publish_briefs_to_drive.publish_one`, with the new `parent` and `title` arguments) and their real debate packs are uploaded (`src/drivepack` helpers), in the Automated Briefs shared drive under `Country editions/<Country>/Campaign briefs/` and `Country editions/<Country>/Debate packs/<date> <title>/`. Folders are found or made by `drivepack.find_or_create_folder` with the existing service account key (`~/runner/parl-monitor/config/google-service-account.json`, present on the Mini; `google-auth` is in `~/runner/venv`). Title `<YYYY-MM> <CC> Brief DRAFT (NOT READY): <subject>`, renamed in place when the brief turns READY; the 5CA tab says "awaiting sign-off" instead of the template's sample rows. Only what exists; samples and `rejected` briefs never (a rejected one's sheet goes to Drive's bin). No duplicates: `data/country-drive.json` (committed with `data/`) records each sheet and the fingerprint it was filled from, unchanged briefs are skipped and refreshed ones rewritten in place, and each sheet carries its slug as a Drive appProperty so a lost ledger adopts the sheets already made. Pack files are matched by name and MD5. At most 30 new sheets a run (63 briefs waited on 11 October, so about three Sundays to catch up). A failure is a `[gap]` line. Preview: `python3 tools/country_drive.py --dry-run` (asks Drive what exists, writes nothing) or `--dry-run --offline`; `--ready-only` leaves NOT READY drafts out.

## The store is published compressed (11 October 2026, branch `store-compress`)

The store reached 1.76 GB on 11 October (1.0 GB on 9 October) against GitHub's 2 GiB limit per release asset. `tools/db_state.py --push` now uploads it gzipped as `parl-monitor.db.gz` on the `db-state` release; nothing in the store changes.

- **Push:** compresses beside the store (`data/parl-monitor.db.gz`, gitignored, removed afterwards) at gzip level 4, proves the .gz decompresses to the store's sha, uploads it through the same keep-the-old-copy-aside swap (`parl-monitor.db.gz.prev` while uploading), then checks GitHub's digest of the upload against ours. Only a verified upload retires the old uncompressed `parl-monitor.db` asset. Measured on the laptop: the 963 MB store of 9 October compresses to 241 MB (4.0x) in about 10 s; 1.76 GB should take about 20 s and come to some 440 MB.
- **Sidecar:** `sha256` and `bytes` are still the UNCOMPRESSED store (what a pull verifies and what the lineage guard compares); `gz_sha256`, `gz_bytes` and `asset_name` describe the asset. `.store-pulled` records both shas, so the live-asset check knows the published .gz as ours.
- **Pull:** takes the form the committed sidecar names (`gz_sha256` present: the .gz; absent: the raw asset), falls back to the other, then to a `.prev`; decompresses beside the working store and installs it only once the uncompressed sha matches. A corrupt or truncated download leaves the working store untouched.
- **The switch:** the Mini runs main's `db_state.py` on every job (the wrapper updates the runner clone before it pulls) and every workflow checks out main, so once this is merged every reader and writer is on the new code. The first compressed push deletes the raw asset; until then pulls take the raw one. A run that started before the merge pulls the raw asset as before; if it then pushes after a compressed publish, the lineage guard refuses it, because the sidecar on main names a store it never held. A branch test (`RUNNER_REF`) or a laptop on a branch without this change cannot pull once the raw asset is gone: merge main first.
- **Size guard:** every push warns (a `::warning::` annotation on GitHub) once the store passes 1.6 GB uncompressed or the .gz passes 1.5 GB, and refuses outright above 2 GiB compressed rather than fail mid-upload. The 07:30 health DM has a "Store" line with both sizes and the same warnings. At 1.76 GB the first warning is already on: the next step is splitting the store into several assets.

## A failed upload is retried; a fresh .prev is left alone (11 October 2026)

Twice (pt-weekly 10 October, nl-weekly 11 October, and a prov-backfill on 9 October) a Mini push failed with `gh upload failed: HTTP 404` and then said "ANOTHER PUBLISH LANDED" when nobody else had published. Cause: a GitHub run's `db_state.py --pull` (Member profiles 14:21Z on 10 October, Dominican Republic weekly 17:33Z on 11 October) found only `parl-monitor.db[.gz].prev`, took it for a failed push and renamed it back while the Mini was still uploading. The Mini's upload then failed, its own rename back hit the name clash, and the failure path called the store it found under the name a rival without looking at its digest. It was the Mini's own previous store.

- **Pull:** a `.prev` set aside less than 30 minutes ago (GitHub's `updated_at`), or of unknown age, is downloaded read-only and NOT renamed back: a push may be uploading. An older one is still recovered as before.
- **Push:** after an upload error the release and origin/main's sidecar are read again. The name holding our own upload ("landed") goes to verification; the name holding a store this copy has held (our kept-aside copy), an unfinished asset, or nothing, is "no other publish seen", and the upload is retried, three attempts over about two minutes (30 s, 90 s), with the same check just before each retry. A finished asset with a digest never seen here, or none, or an unseen sha on origin/main is a genuine race and refuses at once as before ("ANOTHER PUBLISH LANDED ... never seen here"). After the last attempt the keep-aside copy is renamed back ("UPLOAD FAILED, no other publish seen ... RESTORED").
- `tools/raw_state.py` does not share this path: it uploads with `gh release upload --clobber` and has no keep-aside swap or race check.

## The runner's lock: first in, first out (11 October 2026)

Every job goes through `tools/mini_run.sh`, which lets one job at a time
touch the runner clone and the store. Until 11 October the lock was a bare
`mkdir` poll every 15 seconds, not a queue: whichever waiter happened to look
when the lock came free took it. On 10 October `at-weekly` arrived at 02:00
UTC and waited 7,200 s while `hr-weekly`, `latam-courts-backfill`,
`be-weekly` and `us-division-watch` each took the lock ahead of it; its
failure then named whoever held the lock at that moment, which misled us.

**How it works now:**

- Each waiter writes a ticket in `~/runner/locks/queue/`, named by its
  arrival (microseconds since the epoch, from perl's Time::HiRes) and its
  PID; the file holds the job name. `ls ~/runner/locks/queue` is the queue,
  oldest first; `cat ~/runner/locks/state/job` is the holder.
- Only the oldest LIVE ticket may take the lock (`mkdir ~/runner/locks/state`).
  A ticket whose PID is gone, or whose PID now runs something other than
  `mini_run`, is removed with a log line ("dropped the ticket of pid N").
- The holder removes its ticket as soon as it has the lock, and a failure or
  an exit removes it too.
- A lock whose owner is dead (a crash or a power cut) is stale, and the head
  of the queue takes it over ("stale lock from pid N (job); taking it"), as
  before.
- `LOCK_WAIT` (two hours) is still the cap, counted from the job's own
  arrival. A job that gives up says who was in its way, in queue order,
  for example:

      FAILED at lock: waited 7200s; ahead of us when we gave up: hr-weekly, be-weekly; holder: latam-courts-backfill

  A job that has to wait says so once when it arrives ("queued for the
  lock; ahead of us: ...; holder: ...").
- The self-update is unchanged: when step 2 brings a new wrapper, the run
  re-execs it under the same PID, which still holds the lock, so it takes no
  ticket and never queues a second time.
- The first runs after the merge may still meet an old wrapper waiting with
  a bare poll (no ticket). It can take the lock out of turn once; it cannot
  break anything, because `mkdir` still decides who holds the lock.

Tests: `tests/test_mini_run_lock.py` runs the lock block itself under
`/bin/bash` with several waiters in a temp folder (arrival order, a dead
waiter's ticket, the stale lock, the failure line, the re-exec).

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

    # Latam courts, Bolivian questions, Uruguay's Diarios, once (see "Courts,
    # Bolivian questions, Uruguay's Diario totals and OCR" above).
    cd ~ && JOB_TIMEOUT=3600 nohup ~/runner/parl-monitor/tools/mini_run.sh latam-courts-backfill \
      >> ~/runner/logs/latam-courts-backfill.log 2>&1 &

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

**Keep hand-run backfills out of the overnight country-weekly window,
00:00 to 05:00 London.** The plists put these jobs there: Italy 01:00,
Croatia 01:30, Belgium 02:30 and Austria 03:00 on Saturdays; the Sunday pull
02:00 and Poland 04:00 on Sundays; the Monday publish 04:00 on Mondays;
Slovakia 02:00 on Tuesdays; Hungary 03:00 on Wednesdays; the Netherlands
03:00 on Thursdays; Australia 02:00 (and its session judge 03:10) on Fridays;
plus the US division watch at 01:40 and 04:40 and the Australian one at
01:20, Tuesday to Saturday. The lock is first in, first out, so a backfill
started there does not jump the queue, but every job that arrives after it
waits for all of it. A backfill should be finished, not just started, before
00:00: start it no later than midnight minus its `JOB_TIMEOUT`. Friday
night is the worst night: on 10 October the hand-run
`latam-courts-backfill` took the lock in the middle of the Saturday weeklies,
and Austria's weekly gave up after 7,200 s.

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
| Swiss IVG guard (11 October 2026, branch `ch-ivg-guard`) | `jobs/ch-weekly.sh` once with `CH_RECLASSIFY=true`, then `jobs/editions-session-judge.sh` | taxonomy-fr and taxonomy-it no longer read the Invalidity Insurance Act's "IVG" as abortion for `ch`. After the merge, once on the Mini (never while another job writes the store): `cd ~ && CH_RECLASSIFY=true JOB_TIMEOUT=5400 nohup ~/runner/parl-monitor/tools/mini_run.sh ch-weekly > ~/ch-reclassify.log 2>&1 &` (it re-reads the businesses, about two minutes, re-derives every division, and is otherwise the normal weekly, edition DM included). 14 divisions leave area 1 (22.062, 24.066, 24.078). The next editions-session-judge (Sunday 16:45 London) then prunes their 14 unsigned stance drafts (`--prune-off-ground`); to see it first: `python3 tools/country_5ca.py --cc ch --prune-off-ground --dry-run`. |
| SK6, Slovak bill documents | `jobs/sk-weekly.sh` (Tuesdays): documents get the first 10 minutes of the old 45-minute positions budget | The backlog by hand: `sk-docs-backfill` above, three runs. |


## Edition review window and edition publish (11 October 2026, branch `ukp-review-window`)

UK parity for the new country editions: Chris may cut or edit before an edition goes out (`src/edition_review.py`, `tools/edition_review.py`, `config/edition-review.yaml`; on by default for the fifteen own editions and the Latam monthly).

- **The weeklies no longer DM their edition.** `tools/<cc>_monitor.py --edition --dm` (and `tools/latam_monitor.py`) writes the edition as a draft, writes `reviews/<cc>-review-<date>.md` (`latam-review-<date>.md`) and records the window in `data/edition-reviews/<cc>-<date>.json`. Each own-edition weekly now commits `reviews` (`# mini_run: commit ... reviews`; the GitHub backups and Mexico's GitHub run add `reviews/`). A same-day rerun and the Sunday 16:45 session judge rewrite the draft and the review file, keeping every decision. `--no-review` sends at once, as before.
- **Reviewing:** edit the review file on main before the window ends: `DECISION: keep | cut | edit` with `TAKEAWAY:` per item, `NOTE:` for the edition, `PUBLISH: go | hold | now`. Unedited, it goes out unchanged.
- **The window:** 06:30 London the morning after the edition's date by default (Saturday weeklies on Sunday, Poland on Monday, Slovakia on Wednesday, Hungary on Thursday, the Netherlands on Friday, the Latam monthly on the 2nd). Per country in `config/edition-review.yaml` (`publish_at`, `after_days`, `review`).
- **New Mini job `edition-publish`:** `jobs/edition-publish.sh`, **06:31 and 21:10 London daily** (`ops/launchd/net.citizengo.parlmonitor.edition-publish.plist`, `JOB_TIMEOUT` 1800). `# mini_run: no-store`: it checks `data/edition-reviews/` first (`tools/edition_review.py --due`, exit 3 when nothing is due) and pulls the 895 MB store only when an edition is due; it reads the store and never publishes it. It renders each due edition with the review honoured, rewrites `editions/<cc>-monitor-<date>.md`, DMs Chris alone, marks the window sent, then creates or rewrites the week's ONE combined Asana reading task ("Read the country editions - w/c <Monday>", assignee "me" in the workspace, as the UK task; due the Friday). It needs `asana_pat` in `config/secrets.yaml` (or `ASANA_PAT`); without it the task is reported skipped and retried at the next send. A failed DM leaves the edition unsent for the next run. Mini only, no GitHub workflow; "Edition publish" in `tools/coverage.py` ON_DEMAND. Slots: clear of every job; the 06:20 Australia division watch (Tue-Fri) may hold the lock for a few minutes, the 06:40 vote briefs queue behind it for seconds, and 21:10 is before the 21:40 vote briefs and the 22:00 day sweep, more than half an hour from every session judge.
- **Not reviewed, still immediate:** the same-day vote briefs (`country_vote_briefs.py --send`, daily and in each weekly), the Latam instant alerts, the stance digest.
- **Install on the Mini** (after merge): `cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh` (it now lists `edition-publish`). Check: `python3 tools/edition_review.py --status`; a rehearsal that sends nothing: `python3 tools/edition_review.py --publish --dry-run --now 2026-10-12T06:31+01:00`.
- **If the Mini is down:** nothing is lost; the windows wait in `data/edition-reviews/` and the next run sends every edition then due. A weekly run by its GitHub backup opens its review the same way.

## Collector budgets leave room for the publish (11 October 2026, branch `do-sv-fixes`)

- **What broke:** the Dominican Republic's first backfill on the Mini (10 October) spent its fixed 45-minute collector budget, then the vote briefs, alerts, profiles, briefs and the publish ran past `JOB_TIMEOUT` (3600 s) and it was killed before it published. On the Mini the store upload alone takes 13 to 16 minutes (raw archive to store `published_utc` in the sidecars of the Mini's runs on 10 and 11 October: a 1.64 to 1.76 GB store), against about 40 seconds on GitHub.
- **The fix:** every country weekly's collector budget is `tools/collector_budget.sh <cap> "$SECONDS" [later]`: the smaller of the old cap and `JOB_TIMEOUT` less what the job has spent, less its own later budgeted steps, less 20 minutes for the publish and 5 for the unbudgeted steps. Under the hour that is about 35 minutes; a longer plist `JOB_TIMEOUT` gives back up to the cap. On GitHub the cap is unchanged. `tools/mini_run.sh` now exports `JOB_TIMEOUT`, so jobs see the real limit (Ireland's weekly had assumed three hours). The chamber step, Ireland's questions and debates and the US Congressional Record keep the same 20 minutes for the transfers on the Mini.
- **If the store keeps growing** and the upload passes 20 minutes, raise `PUBLISH_S` in `tools/collector_budget.sh` (and the `TRANSFERS` of `jobs/ie-weekly.sh` and `jobs/us-weekly.sh`).

## Words since the last vote for the new countries (11 October 2026, branch `ukp2-since-last-vote`)

No job and no Mini step: `tools/country_since_vote.py --cc nl|ch|at|fr|be` is a hand
command (docs/debate-pack-social.md, "Between votes, new countries"). It opens the store
read-only, so it runs while a weekly holds it, and writes only `data/briefs/<cc>-since-vote*.md`
(with `--write`) and a reads template (`--queue-out`). The optional profile section
(`tools/member_profiles.py <cc> --since-vote`) is not switched on in any weekly.

## Speech clips for the new countries (11 October 2026, branch `ukp-speech-clips`)

No job: `tools/country_clips.py` is a hand command (docs/debate-pack-social.md, "Speech
clips, new countries"). It reads the store read-only and writes only into
`data/clips/<pack>/`, so it is safe while a weekly holds the store, and it never posts.

- **The footage bundle is not installed** (checked over SSH, 11 October 2026: neither
  `/usr/bin/python3` nor `~/runner/venv` imports `faster_whisper`, and there is no
  `ffmpeg`). Step 3 of `tools/macmini_setup.sh` installs it (`pip install --user
  imageio-ffmpeg yt-dlp faster-whisper`); the UK's `social_cut.py` and `speech_cut.py`
  need the same. Run it from a session on the Mini, not over SSH by an agent.
- **The multilingual Whisper model** (`small`, about 480 MB) is fetched by faster-whisper
  the first time a cut runs (the UK uses the English-only `small.en`). Run the first cut by
  hand so the download is seen.
- Fetched source footage is deleted after 30 days (`purge`, also run at the start of each
  cut); finished clips stay in the pack.

## Debate report for the new countries (11 October 2026, branch `ukp2-debate-report`)

No job: `tools/country_debate_report.py` is a hand command (docs/debate-pack-social.md,
"Debate report, new countries"). It reads the store read-only and writes only into
`data/debate-reports/<folder>/`. The Mini's part is the TRANSLATIONS, by the free session
judge on the work account's plan (no API key), run by hand in a session on the Mini (not
over SSH: the keychain), when a report is wanted:

    cd ~/runner/parl-monitor
    SESSION_JUDGE_PROMPT="$(python3 tools/country_debate_report.py --prompt)" \
      bash tools/session_judge.sh tools/country_debate_report.py 40 20 --report data/debate-reports/<folder>
    python3 tools/country_debate_report.py --report data/debate-reports/<folder> --render --dm

A report has a few dozen items at most (title, one passage per speaker, each vote's
question): they come out of the week's ~100 session items only when someone runs this.
Without the judge a person writes the translations into `translations.yaml` on any machine.
