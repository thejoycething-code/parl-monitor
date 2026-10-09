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
- **On the Mini, `~/runner/env` needs** `SLACK_BOT_TOKEN` (already there for Division watch) and, only when the repo variable `US_JUDGE` is `on`, `ANTHROPIC_API_KEY`. `JOB_TIMEOUT` is three hours in the plist: the step budgets (roll calls, Federal Register, Supreme Court, week ahead, the states, judge, a wait for the Senate half on GitHub) add up to about two and three quarters; the Congressional Record runs last of the collectors on what is left, at most 15 minutes, always keeping 40 for the judge, the edition and the transfers. The Congressional Record step needs `CONGRESS_API_KEY` there too (the same key as the amendment purposes).

Install on the Mini, after `git pull` in `~/runner/parl-monitor`:
```
cp ~/runner/parl-monitor/ops/launchd/net.citizengo.parlmonitor.us-weekly.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.us-weekly.plist
```
A first test by hand: `RUNNER_REF=main bash ~/runner/parl-monitor/tools/mini_run.sh us-weekly` (it posts the DM if no edition is committed for today).

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

- **One script, two callers:** `jobs/au-weekly.sh` runs `tools/au_rollcalls.py`, the week ahead (`tools/au_schedule.py`, about 20 seconds), debates (`tools/au_debates.py`, 10-minute budget), the judge when the repo variable `AU_JUDGE` is `on` (it is, since 9 October 2026), then the edition (`tools/au_monitor.py --edition --dm`), and on the Mini publishes the raw archive and the store itself (`raw_state.py --push`, `db_state.py --push`), as `tools/mini_run.sh` requires. It needs the store, so it carries no `no-store` line; its `# mini_run: commit editions` line makes the runner commit `editions/` too.
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

They record their own heartbeats ("Provinces backfill", "Canada backfill"),
never the weekly's. They hold the lock while they run, so the scheduled jobs
queue behind them (up to two hours): start a long one when the calendar is
quiet (`launchctl list | grep parlmonitor` and the plists list the times).
The GitHub dispatch forms still work, as a fallback.

The scoping probes (`*-probe.yml`, `probe-hosts.yml`) stay on GitHub: they
exist to ask whether a site answers GitHub's runners, which only a runner
can answer. They are one-off; delete each once its collector is built.
