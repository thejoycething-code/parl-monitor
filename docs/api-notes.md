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

## NI Assembly: attribution and divisions (probed 2026-08-18)

**Attribution route chosen by measurement, not preference.** Two ways exist to
put a member's name on a question:

| Route | Cost for our use | Extra data |
| --- | --- | --- |
| `GetQuestionDetails_JSON?documentId=` | 1 request per MATCHED question (20) at 1.3KB | minister, department, **full answer text**, answered date |
| `GetQuestionsByMember_JSON?personId=` | 90 requests, ~36MB (670 questions / 399KB for one member) | no answer text |

Detail-per-match wins on both count and richness, because we classify first
and enrich only what matched. `TablerPersonId` joins to
`members.asmx/GetAllCurrentMembers_JSON` (90 MLAs) for party and constituency
-- no question or division payload carries a party.

**Divisions.** `plenary.asmx/GetVotesOnDivision_JSON?startDate=&endDate=`
enumerates them (139 in the twelve months to 2026-08-18: 132 Simple Majority,
7 Cross-Community). `GetDivisionMemberVoting_JSON?documentId=` gives per-MLA
positions with `Designation` (Unionist/Nationalist/Other), which is
load-bearing: a cross-community vote needs a majority in BOTH designations, so
a bare aye/no tally misreads it.

Three traps:

1. **`DivisionSubject` is truncated at 100 characters** -- 49 of 139 rows sit
   exactly on the cap. The proposer's closing `]` is therefore often missing
   ("... (Day 4) [Minister of Justice - D"). Any tidy-up regex that requires a
   closing bracket leaves a different fake suffix on each amendment and the
   grouping shatters: "Justice Bill" split into five variants before this was
   handled in `bill_of()`.
2. **Their own field name is misspelled `DivisonType`** (no second "i").
   `parse_divisions` reads both spellings so an upstream fix cannot silently
   blank the column and hide cross-community votes.
3. **The subject names an amendment NUMBER, never its content.** 0 of 139
   divisions matched the taxonomy on their subject line. This is not a broken
   filter -- "Amendment 97 - Consideration Stage: Justice Bill" simply does not
   say what amendment 97 does.

Consequence for design: the unit of interest is the BILL, derived by
`bill_of()`, and which bills matter is a human judgement recorded in
`config/ni_watch.yaml` with a `why` line. This is deliberately the same
discipline as `config/vote_tracker.yaml` on the Westminster side, where a
division only becomes trackable once somebody writes down what it means.
`tools/ni_divisions.py --review` prints the ranked candidate list and fetches
nothing per-member.

Still not built: no NI equivalent of the 5CA. Attribution and votes are stored,
but nothing estimates a stance -- same rule as RF4 never being auto-filled.

### NI bill-name matching: prefix, not equality (fixed 2026-08-18)

The 100-character cap cuts the bill NAME, not only the trailing furniture, so
one Act arrives under several spellings:

    Inquiry (Mother and Baby Institutions, Magdalene Laundrie
    Inquiry (Mother and Baby Institutions, Magdalene Laundries and W

An exact-match watch list found NEITHER, and did so silently. Two fixes:

  * `bill_matches()` compares by PREFIX (truncation only removes a suffix, so
    prefix matching is its inverse) and ALSO accepts 50 identical leading
    characters, because truncation can land mid-name and leave two strings
    diverging rather than nesting. Thresholds: 12-char stem for a clean prefix,
    50 chars for a divergent pair. Verified against near-miss real pairs
    ("The Executive's Approach to Hate" vs "The Executive's Multi-Year Budget")
    which correctly do NOT match.
  * `tools/ni_divisions.py` now WARNS when a watch entry matches no division in
    the window. A silently-ignored watch line is a bill you believe you are
    monitoring and are not. This is what surfaced the error above: the config
    name had been written "...Magdalene Laundries) Bill" from memory, when the
    Act is "...Magdalene Laundries and Workhouses) Bill".

Recovered 3 divisions (34 -> 37) and 198 member positions.

A follow-on mistake worth keeping, because the shape of it recurs. Having
learned that an unclosed trailing `]` is truncation furniture, I generalised
to "an unclosed trailing `(` is too". It is not: "Inquiry (Mother and Baby
Institutions, Magdalene Laundrie" carries an unclosed paren that is part of
the NAME, and the blanket rule cut it to "Inquiry", quietly dropping the two
divisions the prefix fix had just recovered (37 -> 35). Only the bill
REFERENCE is furniture when unclosed, so the pattern is `\(NIA[^)]*$` -- "NIA"
rather than the full "NIA Bill" because the cap can fall mid-word ("(NIA Bil").
Caught only because the unmatched-watch WARNING fired; without that print the
count would have slid from 37 to 35 in silence. Covered by a regression test.

Canonical naming, same fix: when a division matches a watch entry, the stored
`bill` becomes the ni_watch.yaml name rather than the derived one. Otherwise
one Act sits in three groups, since every amendment truncates at a different
point.

**Do not run ni_pull.py and ni_divisions.py concurrently.** Both write the same
SQLite file; doing so cost the roster fetch with "database is locked". It was
reported as a gap rather than swallowed, which is how it was caught, but the
roster is the join table party attribution depends on.

### NI question series: trust the reference prefix (fixed 2026-08-18)

`category` was derived from `QOralAnswerRequested`, which disagreed with the
reference prefix on 2 of 20 matched questions (AQO 2937/22-27 and AQO
3230/22-27, both flagged false while carrying an AQO reference). AQO **is** the
oral series and AQW the written one, so the prefix is authoritative and the
flag is now only a fallback for an unreadable reference. `Question.series`
replaces the inline ternary; two stored rows were corrected from the archived
responses rather than re-fetched.

### NI party per-date: WIRED IN (2026-08-18)

`GetAllCurrentMembers_JSON` is current members only, so the party on a question
or vote was the member's party NOW. Doug Beattie asked as UUP leader and read
"Independent". Now resolved via
`members.asmx/GetAllMembersByGivenDate_JSON?specificDate=YYYY-MM-DD`.

  * **Identical payload shape** to GetAllCurrentMembers (same 14 keys), so
    `parse_members` serves both -- no second parser.
  * **Confirmed on the real case:** Beattie returns "Ulster Unionist Party" for
    2025-09-19 and 2026-02-26, against "Independent" on the current roster.
  * **One request per distinct date, cached.** Measured 25 for the current
    store: 18 question dates, 9 watched-division dates, 2 shared. Each response
    carries all 90 members, so the whole roster is stored per date and "who was
    in which party when" becomes answerable generally.

`src/ni_store.py` holds the resolution (mirroring `src/un_store.py`).
`party_at()` returns a SOURCE alongside the party -- `as-at`, `current` or
`unknown` -- and `label()` renders a `current` fallback as "(party today)".
The source is returned rather than optional on purpose: an unmarked party is
exactly what filed Beattie's UUP questions under Independent, so a caller
cannot reintroduce the bug by forgetting to ask. A test asserts ni_monitor.py
contains no `JOIN ni_members` for party.

### NI Hansard: classifying a division by its amendment's wording (2026-08-18)

`hansard.asmx/GetHansardComponentsByPlenaryDate_JSON?plenaryDate=YYYY-MM-DD`.
~700KB mean, 806KB max, 182KB gzipped, one request per sitting date, keyless.
An ordered component tree, not rows of records.

**TWO EXACT KEYS. Neither is a string match, and that is why this is reliable.**

  * `ComponentType == "Division"` carries `RelatedItemId` == the division's
    `DocumentID`. Verified 7 of 7 on 2026-06-30 and 139 of 139 across every
    division date. This IDENTIFIES the division -- no amendment-number regex is
    needed for that job.
  * That component's `ParentComponentId` is the `ComponentId` of its enclosing
    `Header`. This SCOPES the window.

Three traps, each of which produced a wrong answer before being fixed:

1. **Do not scan backwards for the nearest Header.** A division can sit hundreds
   of components after its own header. On 2026-04-20, nearest-preceding-header
   attributed division 477724 ("Final Stage: Hospital Parking Charges Bill") to a
   Marriage and Civil Partnership Bill motion and classified it **area 9** on
   `civil partnership`. The parent pointer resolves it.
2. **Do not gate on a name comparison.** Hansard inverts word order -- header
   "Hate: Executive Approach" against subject "The Executive's Approach to Hate"
   -- so `bill_matches(bill_of(subject), header)` rejected 23 of 139 CORRECT
   windows. A name mismatch is worth reporting, never worth acting on.
3. **`ComponentHeader` is not a scope key.** It is header DEPTH: "level 1",
   "level 2", "level 3" and a time. The scope is the component whose
   `ComponentType` is `Header`, a different field. `ParentComponentId` and
   `RelatedItemId` are also ABSENT (key omitted, not null) on most components.

**FOUR amendment openers, all needed.** Finding only the first two left 25 of 83
amendment votes unexplained; all four together leave 4.

| Opener | Component | Wording carrier |
| --- | --- | --- |
| `Amendment No 97 proposed:` (or `... proposed on 15 June 2026:`) | Procedure Line | `Bill Text` |
| `Which amendments were:` / `Which amendment was:` | Procedure Line | `Plenary Item Text`, `No 1:`-prefixed |
| `I beg to move amendment No 1:` | **Spoken Text** | `Plenary Item Text` |
| `I beg to move the following amendment:` (UNNUMBERED) | **Spoken Text** | `Plenary Item Text` |

The `Question put...` line states what was actually voted on and disagrees with
the subject (83 amendment votes either way, but not the same 83). Where it is
unnumbered ("That the amendment be made") the subject's number is the fallback
-- and a single unnumbered candidate wins even when a subject hint exists, since
requiring the hint to be absent disqualified the very case it was meant to help.

**Classify with `filter_item`, NOT `match_passages`.** The passage gate keeps only
tier-1-or-watchlist passages, which is right for one stray term in a 3,000-word
speech and wrong here: an amendment IS the whole document and it is short.
Measured -- the gate drops amendment 97 (area 5, tier 2, `Equality Act 2010`) and
amendment 73 (area 7, `blasphemy`), precisely the interesting ones.
`split_passages`/`aggregate_passages` are still used, but only for the excerpt.

**Never label an empty amendment body as amendment text.** Doing so left
`classify_fields` returning the MOTION under an amendment label: division 476834
classified area 5 off its motion while reporting `source=amendment-text`. This is
the same unmarked-fallback bug as `ni_store.party_at`, and it recurred here in a
new place. Regression test in `tests/test_ni_hansard.py`.

**Yield, 139 divisions over 54 dates:** 139 scoped, 83 on an amendment, 79 with
amendment text, 55 item-text-only, 5 no text, 4 gaps, and **4 divisions carry an
issue area against a baseline of 0** -- Justice Bill amendment 97 (area 5,
accommodation of women prisoners), Justice Bill amendment 73 (area 7, blasphemy),
Deaths/Still-Births/Baby Loss amendment 5 (area 1, termination of pregnancy) and
one unwatched motion (area 5). Three of the four are on bills already in
`config/ni_watch.yaml`: classification corroborates the hand-picked list rather
than replacing it.

`HttpClient` is WRITE-ONLY -- it archives every response and never reads one
back -- so `ni_hansard.load_sitting` reads `data/raw` directly, the same offline
route as `stance.build_text_map`. Without it the classifier re-fetched all 54
sittings on every run. Column ownership is written on the table in `src/db.py`:
`ni_divisions.py` owns identity and `watched`, `ni_classify.py` owns everything
derived. The harvester was changed from `INSERT OR REPLACE` to a named upsert
because the former blanked classified areas on every harvest.
