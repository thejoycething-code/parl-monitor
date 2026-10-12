# CLAUDE.md — CitizenGO Parliamentary Monitor

## Project

A weekly parliamentary monitoring pipeline: ingest UK Parliament open data (plus gov.uk and Holyrood), filter through an issue taxonomy, store structured records in SQLite, render a Monday digest as a byproduct of the store.

**The authoritative spec is `docs/claude-code-handoff-parl-monitor.md`. Read it in full at the start of every work session before writing or changing code.** Companion context (not spec): `docs/keyword-taxonomy.md`, `docs/digest-template.md`, and `docs/pilot-2026-08-03.md` (the reference edition that acceptance reproduces).

## Hard rules (mirror of handoff §11 — never break these)

- Key everything on bill IDs, never titles. Two live bills share a title right now.
- `isDefeated=false` does not mean a bill is alive. Prorogation falls are detected via `includedSessionIds`, per handoff §4.1.
- Never publish raw keyword hits; Parliament's search relevance is loose. Everything goes through filter + triage.
- Never use `answeredWhenFrom` or `expandMember=true` on the Written Questions API.
- Never request What's On ranges over four weeks.
- Never paste full PQ answers into editions: takeaway line and link only.
- Never render an [ACT] item without a non-null owner. Fail the render instead.
- Never hand-edit `config/taxonomy.yaml`; it is generated from `docs/keyword-taxonomy.md`.

## Environment and working norms

- Python 3.11+, stdlib-first (`urllib`, `sqlite3`, `re`) plus `pyyaml`. No frameworks, no ORMs, no async unless a measured need appears.
- Parliament APIs are keyless and may be probed live, but only through `src/http.py` (UA string, throttle, retry with backoff per handoff §3). Archive every raw response to `data/raw/` before parsing, including during development.
- Acceptance tests run against the frozen fixtures in `data/raw/2026-08-01/`. If live data diverges from fixtures, fixtures win for tests; record the divergence in `docs/api-notes.md`.
- `ANTHROPIC_API_KEY` may be absent. Everything must run end to end with `TRIAGE=stub`.
- Rendered editions use British spelling and contain no em dashes.
- Small single-purpose commits with plain descriptive messages. Write tests alongside each ingester using the fixtures. Run the full test suite before reporting any build step complete.

## Build order and checkpoints

Follow handoff §10 strictly, in order. There are two hard stops for human review; do not work past them without explicit sign-off:

1. **Checkpoint 1, after step 2** (`http.py`, `db.py`, `ingest/bills.py`, `board.py`): demonstrate retry behaviour under a simulated timeout, and the four board transitions (new bill, stage advance, Royal Assent, prorogation fall) tested against bills 4157 and 3774 from fixtures.
2. **Checkpoint 2, after step 7**: present the generated edition side by side with `docs/pilot-2026-08-03.md` and walk the nine acceptance criteria from handoff §9 point by point.

## Weekly operations

**Primary runtime: the Mac Mini** (since 9 October 2026; docs/mac-mini.md).
launchd runs every scheduled job first, at its London time, through
`~/runner/parl-monitor/tools/mini_run.sh <job>` -> `jobs/<job>.sh`, in its own
runner clone (never the dev clone) under one lock. **GitHub Actions is the
backup**: each scheduled workflow's `mini-check` gate skips while the Mini is
running the job and after it has run it (repo variables `MINI_RUN_<JOB>`,
`MINI_LAST_<JOB>`), and runs it only when the Mini did not. State (store, raw
archive, editions, reviews) is committed by each run; **always `git pull`
before local work**, the bot commits to main. The 07:30 London health DM says
what ran where, what failed, what is overdue, and GitHub's minutes.

- **Sunday 02:00 London**: the Sunday pull (jobs/sunday-pull.sh): pull all
  feeds, archive raw, filter, triage (TRIAGE=auto, live scoring), commit state.
- **Monday 04:00 London**: the Monday publish (jobs/monday-publish.sh): render,
  post the edition to #campaigns-en-gb, judge evaluation, commit state; then
  GitHub's Deploy tracker deploys the partner site (the Vercel token is a
  GitHub secret). A cloud routine pushes a backstop trigger at 06:30.
- The weeklies, the daily sweeps, the division watch and the monthlies run the
  same way; `ops/launchd/*.plist` hold their times.
- Local manual runs still work: run_weekly.py / run_monday.py with
  config/secrets.yaml (gitignored; template in secrets.yaml.example).

**Rules for working with the runner** (they keep the repo under 60 GitHub
Actions minutes a day, the bar for making it private again):

- **Backfills, repairs and other long one-off collection run on the Mac Mini,
  never as a GitHub dispatch.** Use `jobs/prov-backfill.sh`,
  `jobs/ca-backfill.sh`, or a new `jobs/<x>-backfill.sh` built the same way,
  through `tools/mini_run.sh` (commands in docs/mac-mini.md). Dispatched
  backfills cost 2,604 Actions minutes in the week to 9 October. A backfill
  names its own heartbeat (coverage.py ON_DEMAND), never the weekly's.
- **Only work that must come from GitHub's network runs there**: scoping
  probes (`*-probe.yml`, `probe-hosts.yml`) that ask whether a site answers
  GitHub's runners, and the halves of a job a site refuses the Mini (US
  weekly's Senate votes). Delete a probe workflow once its collector is built.
- **A new scheduled job gets a Mini job and a gate**: `jobs/<job>.sh` (export
  `GITHUB_WORKFLOW` with its pipeline name; publish the raw archive, then the
  store), a plist in `ops/launchd/`, and `mini-check` in front of its
  workflow. tests/test_mini_jobs.py holds the pairs together.
- **Never run collection in the dev clone while a Mini job may be publishing**,
  and never dispatch a job the Mini is running: the store guard refuses a
  second writer, and the loser fails.

## When uncertain

- Observed API behaviour beats documentation. Record divergences in `docs/api-notes.md` and continue.
- Spec ambiguity: take the smallest reasonable interpretation and flag it in your summary.
- Ideas beyond the spec: log them in `docs/phase-2-notes.md`. Do not build them.
