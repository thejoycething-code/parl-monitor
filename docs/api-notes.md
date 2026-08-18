# API and environment notes

Divergences between the handoff/spec and observed reality. Per CLAUDE.md:
"Observed API behaviour beats documentation. Record divergences here and continue."

## Repo / fixtures (recorded 2026-08-01, build start)

- **Fixtures absent.** `data/raw/2026-08-01/` did not exist at build start, and no
  pilot edition (`docs/pilot-2026-08-03.md`) was present. Section 9 acceptance and
  Checkpoint 1's "four board transitions tested against 4157 and 3774 from fixtures"
  cannot be run against fixtures until these are supplied or regenerated. Awaiting a
  decision on how to source them (live probe + archive, reconstruct from spec, or
  supply the pilot pack). See the build summary.
- **Repo layout** was four loose markdown files at top level; created the section 2
  layout and moved the docs into `docs/`.

## Environment

- **Python 3.9.6** on this machine; spec requires 3.11+. Source is written to run on
  3.9 (no `match`, no PEP 604 runtime unions) while targeting 3.11. Flag for the real
  runtime.
- `pyyaml` and `httpx` not installed. `http.py`/`db.py` use stdlib `urllib`/`sqlite3`
  only; `pyyaml` will be needed once config parsing lands (step 4).

## Scottish Parliament (observed 2026-08-01)

- **The bills API did NOT time out.** `data.parliament.scot/api/bills` returned 473
  rows in ~5s; the pilot recorded a 60s timeout. The 90s timeout and 30-day cache
  from handoff 4.11 are retained as insurance, but the endpoint is currently healthy.
- **The API carries no status.** Rows are identity only: `ID, Reference, ShortName,
  FullName, BillTypeID, PersonID, ThirdPartyOrganisation`. It cannot tell you whether
  a bill fell or passed, so the page scrape is not a fallback for the API, it is the
  only route to status. The API is still useful for id/title lookup.
- **Status-parsing trap:** the bill page contains "Current status:" lines belonging to
  *motions* on that page (e.g. "Taken in the Chamber on Tuesday, 13 May 2025"), not to
  the bill. Keying on that string yields a motion date. The bill's own status is the
  sentence "The Bill fell on {date} at {stage}"; `scotland.parse_status()` matches that
  shape and a test asserts the motion date is not returned.
- Holyrood board rows are namespaced with a **negative bill_id** derived from the
  Scottish ID (e.g. -445), because `bills_board.bill_id` is a shared integer PK.
  Their board link uses parliament.scot, via `BoardRow.link`.

## Single continuous store (fixed 2026-08-02)

Early builds gave each week its own SQLite file (`parl-monitor-<week>.db`), a
testing convenience that silently broke every week-on-week feature: movement
snapshots, the one-closing-entry guard, and EDM signature deltas all diff this
edition against the last, which requires one continuous `data/parl-monitor.db`
(as the handoff section 5 schema always assumed -- `editions`, `edm_signatures`
and `board_snapshot` are keyed by edition within one store). The 2026-08-03
edition's state was migrated in as the seed. Per-week db files are dead.

Also fixed the same day: `board.apply_snapshots()` now persists per-bill
movement snapshots at render (previously nothing wrote `board_snapshot`, so
every edition rendered every bill as NEW forever). Snapshot JSON keeps
`{edition, current, previous}` so re-rendering an edition is idempotent.

## Closing-entry guard bug (found and fixed 2026-08-01)

`run_weekly.build_board_rows()` passed a hardcoded `closed_bill_ids=set()`, a leftover
from the cold-start demo, so Westminster closing entries re-emitted on every edition
while Holyrood (which consulted the DB) did not. Now the closed set is loaded from
`bills_board` for both. Verified: edition 1 emits 4 closing entries, edition 2 emits 0.
Regression test in `tests/test_board.py`.

## What's On StartTime (observed 2026-08-01)

`StartTime` is **never null**: it is `HH:MM` for diarised business (103/167 rows in
w/c 2026-07-06, mostly committee oral evidence) and an **empty string** for chamber
business that runs in Order Paper sequence rather than at a clock time: oral
questions, orders and regulations, ministerial statements, urgent questions,
adjournment debates (64/167).

An empty StartTime therefore means "sequenced", not "time to be announced".
`whatson.event_label()` renders **"after other business"** in that position
(Christopher's call, 2026-08-01) so readers can tell order-paper business from a
missing time. Times are formatted to the digest-template style (`11:30` ->
`11.30am`). `EventActivities[].StartTime` uses a different format again
(`'10:00 am'`) and can differ from the row-level time; not currently used.

Source descriptions occasionally carry double spaces; `event_label()` collapses
whitespace.

## Config generation (step 4)

- `config/taxonomy.yaml` and `config/watchlist.yaml` were created verbatim from
  handoff section 6 (the authoritative "generated config"). The handoff yaml is
  **v0.2** (four pilot patches) but `docs/keyword-taxonomy.md` is still **v0.1**,
  so a true md->yaml regenerator plus a v0.2 update of the md is outstanding
  (handoff step 8 / phase 2). Until then, taxonomy.yaml is the source of truth for
  matching and must not be hand-edited for content.
- `config/watchlist.yaml` keeps the Holyrood block but `filter.py` does NOT load
  it (Westminster-only for now).

## Spec corrections to apply later

- **Triage model id.** Handoff section 7 pins `claude-sonnet-4-6`, which is not a
  valid current model id (current line is the Claude 5 family; Sonnet is
  `claude-sonnet-5`). Phase 1 runs `TRIAGE=stub`, so non-blocking now; correct before
  the live triage pass.
- **Seed-list divergence.** `docs/keyword-taxonomy.md` and handoff section 6
  `watchlist.yaml` list different parliamentarians. Acceptance 9.5 depends on Andrew
  Snowden and Baroness Maclean, present only in the handoff watchlist, so
  `config/watchlist.yaml` (handoff section 6) is authoritative for matching.

## Royal Assent date divergence (live probe, 2026-08-01)

Live-probed the keyless Bills API and archived real fixtures into
`data/raw/2026-08-01/`. Board dates for 4157 and 3774 matched acceptance 9.1/9.2
exactly (4157 next date 2026-09-11; 3774 frozen at Lords Committee, 14 sittings
2025-11-14 -> 2026-04-24, session 39 excluded from current session 40 so fallen
with `isDefeated=false`). BUT:

- **Both Acts' Royal Assent *stage sitting* date is 2026-04-29** (bill 3938 Crime
  and Policing Act 2026; bill 3909 Children's Wellbeing and Schools Act 2026).
  Acceptance 9.2 expects **2026-05-11** (CPA) and **2026-06-26** (CWSA), and 9.3
  says s.241 CPA is "in force at Royal Assent" on 11 May 2026.
- The bills-api RA-*stage* date and the legislation.gov.uk *commencement/in-force*
  date are different events. `board.py` reads the feed's RA-stage date (correct for
  the board feed). Reconciling the closing-entry date against the acceptance values
  belongs to the legislation.gov.uk ingester (step 3) and Checkpoint 2.
- **DECIDED (Christopher, 2026-08-01):** the board closing entry shows the
  **parliamentary RA-stage date** (bills-api), i.e. 2026-04-29 here. `board.py`
  already reads this. Consequence: acceptance 9.2's stated values (2026-05-11 /
  2026-06-26) will NOT be reproduced by the board.
- **Follow-up from step 3:** legislation.gov.uk confirms ukpga/2026/20 **s.241**
  "Removal of women from the criminal law related to abortion" and **s.242**, both
  "in force at Royal Assent" (acceptance 9.3 holds as written). The section HTML
  carries no explicit "11 May 2026" date, so that specific date from the taxonomy
  note is not in live data; the RA-stage date remains 2026-04-29.
- **Correction:** an earlier probe of mine used a positional zip of separate
  ContentsNumber/ContentsTitle lists and mis-reported the abortion clause as s.22.
  The real XML (ContentRef="section-241") and the adjacency parser both give
  **s.241**. No s.22 divergence exists; the spec was right.

## Cold-start closing entries — RESOLVED (Option B, Westminster-only)

Acceptance 9.2 expects four closing entries on the first-ever edition, but a
relational transition ("close a bill that was live last edition") can never fire
on a cold board with no prior snapshot and no live rows for the terminal bills.

**DECIDED (Christopher, 2026-08-01):** Option B — terminal state is detected
**absolutely**, not relationally. `board.discover_closures()` evaluates candidate
bills (watchlist + acts_watch short-title searches) each run and emits a closing
entry for any that is terminal (Act, or session-excluded) and has no
`closed_edition` yet; the guard makes it fire once ever. Implemented + tested
(`load_closed_bill_ids` / `record_closure`, idempotency proven end-to-end).

**Scope:** Westminster only for now. Holyrood fall detection (the assisted-dying
bill, acceptance 9.2's fourth close) is deferred to the Scotland ingester
(section 4.11) and is NOT in this discovery path yet. So the cold run currently
surfaces three closures (3774, 3938, 3909), not four.

## Spec deviation: area 11 (migration), 2026-08-03

Christopher's decision: migration is a standing campaign area. The handoff
section 7 system prompt (spec says verbatim) is extended with a migration
clause so triage scores the new area rather than discarding its items; the
taxonomy master gains area 11 (bare migration/immigration/asylum at tier 2,
triage-gated); bill 4254 (Immigration and Asylum Bill) joins the board; the
Border Security, Asylum and Immigration Act 2025 joins acts_watch for SI
implementation tracking (no bill_id on purpose: its 2025 assent predates the
monitor, so no closing entry).

## Format deviation: section order (owner decision, 2026-08-03)

The digest-template's original order (board as section 2) is superseded:
Top lines lead, the week's diary (Week ahead) comes second, and the Active
bills board renders as section 10, before MP intelligence notes. Rationale:
the briefing should open with what is happening and close with standing
reference material. Renderer, tests, sample reference and both published
editions updated; docs/digest-template.md left as the historical spec.

## Northern Ireland Assembly (probed 2026-08-18)

The handoff (§8, phase 2) lists `aims.niassembly.gov.uk` as "research needed".
That host is NOT the open data service and will waste time: `/api/` there
301s to https and then 404s. The service is **`data.niassembly.gov.uk`**, five
.asmx endpoints each offering XML, JSON and JSONP variants. Keyless, no
registration, HTTP (not HTTPS-only). `aims.niassembly.gov.uk` is still useful
as the human-facing page for a question by document id.

Services: `questions`, `plenary`, `members`, `hansard`, `organisations`.

What was probed and works:

| Call | Params | Notes |
| --- | --- | --- |
| `questions.asmx/GetQuestionsBySearchText_JSON` | `searchText` (3+ chars) | 242 rows for "abortion", 2008-03-07 to 2026-06-04 |
| `plenary.asmx/GetNoDayNamedMotions_JSON` | none | tablers WITH party in one field |
| `plenary.asmx/GetBusinessDiary_JSON` | `startDate`, `endDate` | forward sittings + committee meetings |

Three traps, all of which shaped `src/ingest/niassembly.py`:

1. **No date parameter and no paging on the question search.** It returns the
   entire history in one response every time. The window is therefore applied
   client-side after the fetch. This is not waste -- it is the only cheap way
   to ask what the Assembly has said about an issue over eighteen years.
2. **A one-row result collapses to a bare object, not a list of one.** Every
   envelope is doubly nested (`{"QuestionsList": {"Question": ...}}`) and the
   inner value is a list for 2+ rows and an object for exactly 1. Code that
   assumes a list silently sees nothing on single-hit terms.
3. **Search results carry no member name.** Only DocumentId, Reference,
   TabledDate, QuestionText. Attributing a question to an MLA costs one
   `GetQuestionDetails` call each, so no MLA ledger is built.

Not built: `plenary.asmx/GetDivisionMemberVoting_JSON` and
`GetVotesOnDivision_JSON`. These are the high-value 5CA-equivalent evidence (a
vote outranks a question 5:1) and are the obvious next step.

**Kept out of the digest deliberately** (Christopher, 2026-08-18). NI is a
watching brief, so it is stored in its own `ni_items` table and read through
`tools/ni_monitor.py`. The published edition is built by `SELECT ... FROM
items`, so a separate table -- not a flag on a row -- is what makes it
structurally impossible for NI to reach Slack. `tests/test_niassembly.py`
asserts `tools/ni_pull.py` contains no write to `items`.
