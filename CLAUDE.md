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

**Primary runtime: GitHub Actions** (repo `thejoycething-code/parl-monitor`,
private; migrated 2026-08-03 after a green test run). The laptop is a dev
machine and manual fallback only -- its launchd jobs are retired (plists
archived in tools/launchd-retired/). State (store, raw archive, editions,
reviews) is committed by each workflow run; **always `git pull` before local
work**, the bot commits to main.

- **Sunday 21:04 London** (.github/workflows/sunday-pull.yml): pull all feeds,
  archive raw, filter, triage (TRIAGE=auto: live scoring via ANTHROPIC_API_KEY
  Actions secret), emit review file for the coming week, commit state.
- **Optional human window until Monday 06:30**: edit reviews/review-<week>.md
  (via laptop + push, or the GitHub web editor). Decisions merge-preserve.
- **Monday 06:30 London** (.github/workflows/monday-publish.yml): render, post
  to Slack (skipped until SLACK_BOT_TOKEN secret exists -- bot app awaiting
  workspace admin approval; interim: post in-session as Christopher with his
  explicit weekly go-ahead), create the Asana reading task (ASANA_PAT secret),
  commit state.
- Cron is UTC with a London-hour guard step (BST/GMT drift); duplicate slots
  self-skip. Local manual runs still work: run_weekly.py / run_monday.py with
  config/secrets.yaml (gitignored; template in secrets.yaml.example).

## When uncertain

- Observed API behaviour beats documentation. Record divergences in `docs/api-notes.md` and continue.
- Spec ambiguity: take the smallest reasonable interpretation and flag it in your summary.
- Ideas beyond the spec: log them in `docs/phase-2-notes.md`. Do not build them.
