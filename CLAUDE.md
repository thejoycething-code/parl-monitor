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

## Weekly operations (the Monday ritual)

The Sunday 21:04 launchd job (`com.citizengo.parlmonitor`) runs the pull
unattended. On Monday, in a Claude Code session, run these steps in order:

1. **Score the triage queue** at `reviews/triage-queue-<week>.md` per the
   embedded section 7 rubric (in-session scoring; no API key).
2. **Apply review decisions**: `reviews/review-<week>.md` — Christopher (or a
   session acting on his instructions) sets PRIORITY/OWNER; every ACT needs an
   owner or the render refuses.
3. **Render**: `python3 run_weekly.py --render <week>`.
4. **Post to Slack** (#campaigns-en-gb, C9RH217PZ): create a Canvas titled
   "Parliamentary Monitor — week commencing <date> (Edition N)" holding the
   full edition, then a short summary message (top lines + any ACT items)
   linking the Canvas.
5. **Create the week's Asana reading task** (a fresh task each week — do NOT
   use Asana recurrence; the point is a live link to the latest edition):
   - name: "Read the Parliamentary Monitor — w/c <date>"
   - assignee: me (cjoyce@citizengo.net), due that Monday
   - notes: link to this week's Canvas, any ACT items with owners, deadlines
     falling within 3 weeks, and the standing checklist (scan Movement column;
     confirm ACT owners; review upcoming deadlines; decide held-at-NOTE items).
6. Commit any config/review changes (small, single-purpose commits).

## When uncertain

- Observed API behaviour beats documentation. Record divergences in `docs/api-notes.md` and continue.
- Spec ambiguity: take the smallest reasonable interpretation and flag it in your summary.
- Ideas beyond the spec: log them in `docs/phase-2-notes.md`. Do not build them.
