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

### NI vocabulary (taxonomy v0.5) and the hyphen bug (2026-08-18)

**Every hyphenated sweep term returned ZERO from the NI question search.** The
endpoint is a literal substring match: "puberty-blockers" 0 against "puberty
blockers" 32; "assisted-dying" 0 against "assisted dying" 4; "gender-dysphoria"
0 against "gender dysphoria" 4. The 20 questions stored before this fix had all
come from single-word terms. `ni_pull.sweep_terms` now passes every term
through `hansard.spoken_form` -- the helper that exists because the same
hyphens were quietly costing hits in Westminster Hansard.

**Taxonomy v0.5** adds NI vocabulary, every term measured against a year of
plenary Hansard (54 archived sittings, 20.7M chars) and the 18-year question
index before earning a place. Headlines: "relationships and sexuality
education" is the NI statutory term (47 questions, 28 since 2024 -- the
existing GB wording "relationships and sex education" matched none of them);
"Knowing Our Identity" and "Brackenburn" are NI's youth and adult gender
services (the Tavistock/GIDS vocabulary misses both entirely). NI-only terms
are swept via a separate `ni_sweep_terms` list in settings.yaml so the
Westminster PQ sweep is untouched.

Probed and deliberately NOT added: **CEDAW** -- zero hits in a year of plenary
and zero questions in eighteen years. The framework Westminster cited to
impose the 2019 abortion law is never named in NIA discourse, which is itself
a finding: the argument there is not conducted on the UN's terms. Also "both
lives" (1 plenary + 0 questions).

### NI 5CA (2026-08-18): placement only from human-confirmed meaning lines

`tools/ni_5ca.py` builds a make_5ca.py-shaped CSV (same header, plus a
DESIGNATION column -- a cross-community vote needs majorities in both
designations, so "48 of 90" can still lose). The Westminster engine places
members from the Claude-scored `stance` table; NI forbids estimated stances,
so the transferable mechanism is the human-authored `overrides` pattern:
`config/ni_stance.yaml` records what an aye MEANS per division, and the tool
merely applies it. An entry carrying `draft: true` places NOBODY -- the three
seeded entries are Claude drafts awaiting Christopher's review, and until each
flag is removed the sheet is evidence-only. Questions never place anyone
(activity, not direction). Conflicts are flagged, never averaged. The sheet is
never posted anywhere.

YAML trap in ni_stance.yaml: an unquoted `no:` key parses as boolean False
(YAML 1.1), so `ni_5ca.load_stance` normalises both spellings -- covered by a
test, because an edit that drops the quotes would otherwise silently lose the
no-lobby meaning.

### NI forward Order Paper (probed 2026-08-18)

`plenary.asmx/GetPlenaryItemsPlenaryDate_JSON?startDate=&endDate=` accepts
FUTURE ranges and returns the scheduled plenary business by sitting date:
DocumentID, Title, PlenaryType, PlenaryDate (the sitting), TabledDate (the
announcement). This is the NI equivalent of Westminster's What's On, and it is
what the business diary is not -- the diary names committees and rooms, this
names the business. Measured: one sitting week (2026-06-29) carried 31 titled
items (18 motions, 6 petitions of concern, oral and written statements);
during recess only WMSs are tabled ahead, with motions arriving roughly four
weeks out per TabledDate.

The parameter is a RANGE (startDate/endDate), not the single plenaryDate the
operation name suggests -- probing `?plenaryDate=` returns 500 "Missing
parameter: startDate".

Petitions of concern appear as their own PlenaryType and are flagged in the
monitor: a petition of concern turns the affected vote cross-community, so a
simple majority stops being enough. Seeing one COMING is worth more than
reading it in the aftermath.

Stored as ni_items kind='plenary' by tools/ni_pull.py, whole window (an Order
Paper is small and "what is the Assembly doing next week" wants the whole
answer), classified on title for the OURS mark.

### GetAllCurrentMembers is BROKEN upstream, and the fallback lags (2026-08-19)

Found by rehearsing the weekly workflow, which is exactly what a rehearsal is
for: the run printed "0 sitting MLAs stored" and then "no gaps".

`members.asmx/GetAllCurrentMembers_JSON` answers **HTTP 200 with
`{"AllMembersList": null}`** -- a success carrying nothing, three times in a
row. It is that one operation, not the service: `GetAllMembers_JSON` (161KB),
`GetAllConstituencies_JSON` and `GetAllMembersByGivenDate_JSON` all still
return data. This is the "block disguised as success" class already recorded
for the UN sources, and it is the most dangerous shape of failure because
nothing raises.

`GetAllMembersByGivenDate_JSON` for today is the same payload shape, so
`parse_members` serves it unchanged -- but it **LAGS**:

| specificDate | members |
| --- | --- |
| 2026-08-19 (today) | **0** |
| 2026-08-18 | 90 |
| 2026-08-17 | 90 |
| 2026-08-15 | 90 |
| 2026-08-12 | 90 |

So a fallback that asked only for today would ALSO have come back empty, and
the Saturday 06:00 run would never have refreshed the roster -- the join table
every attribution depends on -- while reporting no gaps. `fetch_members` now
steps back up to `MEMBER_FALLBACK_DAYS = 7`, stops at the first populated day,
and returns its SOURCE ("by-date fallback (2026-08-18)") so a fallback roster
can never read as the primary. Verified live: 90 members, correct party split.

Two rules restated, because this broke both:
  * An empty-but-errorless reply is a GAP, not a zero. `resolve_dates` already
    applied this to the by-date roster; the current roster was the
    inconsistent one, and `ni_pull` now records a gap for an empty roster AND
    for a successful-but-fallback one.
  * An empty fallback is not a successful fallback. The first version of the
    fix returned `([], "by-date fallback (...)")` when the fallback was also
    empty -- the same trap one level down, caught by a test.

Also fixed in the same rehearsal: an ANSWERED question is final, so its
GetQuestionDetails call is made once. 203 of 217 stored questions (94%)
already held an answer and were being re-fetched every week to learn nothing;
the enrichment loop was 8 of the run's 10.5 minutes. Unanswered questions are
still re-fetched -- the answer arrives later and that is the one case a row can
change. A `carry` helper keeps a skipped fetch from blanking a column a
previous run filled. Measured: ni_pull 509s -> 285s.

### NI motion text: GetPlenaryDetails closes the motions zero (2026-08-19)

`plenary.asmx/GetPlenaryDetails_JSON?documentid=` returns a plenary item's
operative **Text**. `GetNoDayNamedMotions_JSON` gives only DocumentID,
MotionCategory, Title, TabledDate and MotionTablers -- a three-to-six-word
title and no body -- which is why 0 of 33 motions classified for as long as the
feed existed. The monitor's own honesty text named this: "the endpoint gives no
motion body... the fix is the motion text."

Measured after the fix: **3 of 33 match on their wording, 0 of 33 matched on
their title.** The best find is the case for the whole exercise:

  "Women's Rights in Northern Ireland Prisons" (Independent, unscheduled)
  -> area 5 on single-sex space*, For Women Scotland, transgender,
     women's prison*

The title alone misses it because "women's prison" is not contiguous in
"Northern Ireland Prisons"; the body cites the For Women Scotland judgment
directly. It is also the same subject as Justice Bill amendment 97
(accommodation of women prisoners) -- one issue, two vehicles, which is the
kind of thread a watching brief exists to see. Also caught: "Modernising
Divorce Laws" -> area 9 (no-fault divorce) and "Standing up to Racism" ->
areas 7, 11.

The fetch CANNOT be gated on a prior match the way question enrichment is: the
title is the thing that fails to classify, so there is nothing to gate on. It
is 33 requests, and a motion already holding its `body` is skipped -- a tabled
text does not change, and a scheduled motion leaves the no-day-named list
rather than being rewritten in place. Stored in the new `ni_items.body` column
whole, so re-classification after a taxonomy regeneration is offline.

Classified with `filter_item` on (title, body), not `match_passages`: a motion
is a whole short document, the same reasoning as an amendment in ni_classify.

Still unclassifiable from this route: nothing. The remaining motions genuinely
are not ours -- rural transport, childhood cancer awareness, waiting lists.

### NI committee agendas: the subject, not just the room (2026-08-19)

`plenary.asmx/GetCommitteeAgendaItemsCommitteeMeetingId?eventId=` returns a
committee meeting's agenda, keyed on the event id the business diary already
stores. This closes the gap the monitor named: the diary gives a committee NAME
and a room, so an OURS mark on it meant the committee was ours, never the
agenda.

**XML ONLY.** This operation has no `_JSON` sibling -- asking for one returns
500 "Web Service method name is not valid". The three `GetCommitteeAgendaItems*`
operations are the only ones on plenary.asmx without JSON variants, so this is
the one NI feed parsed with ElementTree.

**The key is (event_id, ItemOrder), NOT ItemId.** One subject occupies several
slots because a committee commonly runs an item in public and then again in
closed session: the 20 August meeting listed three EU regulations in public and
the same three closed, so ItemId repeated and keying on it collapsed nine slots
to four -- taking the public/closed distinction with them. `AgendaItem.closed`
surfaces that, because a closed session cannot be observed and that changes what
a campaign can do about it.

Measured across the stored 60-day diary: **80 slots over 11 meetings, 1 on our
ground, 6 meetings with no agenda published yet** (correctly reported as such
rather than as an empty agenda -- a meeting weeks out often has none).

The one hit is the argument for the feature:

  2026-09-09  Committee for FINANCE
  -> "Marriage and Civil Partnership Bill - Committee Deliberation"  area 9

Nobody would think to look for a marriage bill at the Finance committee, and
"Committee for Finance" classifies to nothing. Three weeks' notice of a
committee deliberation on it is exactly what a forward view is for.

An empty agenda is NOT a gap; a fetch error is. Yield will be low most weeks --
committee business is overwhelmingly budgets, EU regulations and departmental
briefings -- which is an argument for the OURS filter, not against the feed.

Motions are stored WHETHER OR NOT they match, like the business diary. Storing
only matches meant the body cache held only matches, so the 30 non-matching
motions were re-fetched every week -- the second run reported "30 newly
fetched" -- and a taxonomy regeneration could not re-test a motion whose
wording had been discarded. The monitor filters on `areas` at display time and
prints how many of the tabled motions matched, so a small hit count reads as
the filter working rather than as a thin feed.

### NI motion sponsorship: the 5CA's missing middle (2026-08-19)

`plenary.asmx/GetPlenaryTablers_JSON?documentId=` gives who tabled a plenary
item, with `TablerPersonID` and -- the part that matters -- a
**`TablerSequence`**. Sequence 1 is the PROPOSER; 2+ are co-signatories, which
is the same distinction Westminster draws between sponsoring an EDM (weight 3)
and signing one (weight 2). NI previously had votes (which need a human meaning
line) and questions (activity, never direction) and nothing in between.

The motion list's own `MotionTablers` string cannot do this job, twice over:

  * It carries no PersonId, so it cannot be joined to the roster or to
    ni_affiliations for party-as-at-date.
  * **Its order after the first name is NOT the tabling sequence.** Measured on
    motion 448545: the string reads Armstrong / Donnelly / McReynolds /
    McMurray, where the real sequence is Armstrong(1) / McMurray(2) /
    McReynolds(3) / Donnelly(4). The proposer happens to come first in both, so
    inferring sequence from the string looks right and is wrong from position 2.

Fetched only for motions already classified into an area -- genuinely gateable
here, unlike the motion body, because classification has happened by that point.

THE FINDING THAT JUSTIFIES IT. The women's-prisons motion (491925) was PROPOSED
by Mr Doug Beattie MC on 2026-06-22, and Beattie then voted AYE on Justice Bill
amendment 97 (accommodation of women prisoners) on 2026-06-30. Two independent
acts on one subject, eight days apart, in two different vehicles -- and the
as-at party resolution shows he had left the UUP a fortnight earlier (UUP on
2026-06-08, Independent by 2026-06-22). A vote alone is one data point; a vote
plus the motion the member authored is a pattern, which is what a 5CA column is
supposed to rest on.

Sponsorship enters the 5CA through `motions:` in config/ni_stance.yaml, on the
same terms as divisions: a human writes what sponsoring the text MEANS, and a
`draft: true` entry places nobody. The SEQUENCE changes the evidence weight,
never the direction -- a co-signatory advances the same text as the proposer,
just less prominently -- so `NI_KIND_WEIGHT` is vote 5 > motion 3 >
motion-signed 2 > question 1, and a recorded vote outranks a signature of equal
magnitude because it is the only act with a recorded direction.

Two of the three classified motions are deliberately left WITHOUT a reading:
"Standing up to Racism" (areas 7, 11) and "Modernising Divorce Laws" (area 9)
are neither ours nor against us on their text, and inventing a direction to
fill a cell is what that file exists to prevent. They appear as evidence with
no placement.

Fixture correction found while doing this: tests/test_ni_store.py used person id
5340 for Beattie under a docstring claiming "his real person id". His real id is
5786. The tests passed because they were self-consistent, but the docstring was
false; corrected and verified against the live roster.

### NI ministerial answers: read the refusals (2026-08-19)

203 of 217 stored questions already hold their answer, so reading them costs no
fetches. What that is worth is NOT what it first looks like.

**Area discovery is nearly worthless here.** Classifying the answer text finds
7 of 203 answers carrying an area the question lacked -- one per area, spread
evenly, i.e. noise. Measured before building, and it is why this feature is not
"classify the answers".

**The SHAPE of the answer is the value.** 28 of 203 (14%) decline: the data is
not held, no guidance was issued, the matter is not Northern Ireland's, or no
position has settled. No answer matches two shapes, so 28 pattern hits means 28
distinct answers -- checked, because the first version of this module scored
only 14 and the gap turned out to be two phrases dropped when the patterns were
rewritten from the measuring probe: `responsibility of/rests with/lies with`
(8 answers, "not a policy or legislative responsibility of my Department") and
`in due course` (6). Both restored, both now carrying a regression test. The
lesson is the one this repo keeps relearning: a rewrite that narrows a pattern
looks identical until you compare its count against the measurement it came
from. Those are the quotable ones, and the phrasings recur, so
they are matched structurally -- the same approach as emerging.rights_claims,
a pattern over how government answers rather than a list of subjects:

| shape | count | real example |
| --- | --- | --- |
| not our remit | 10 | EHRC guidance is from "a body which does not have functions in Northern Ireland" |
| no settled position | 8 | a draft report's contents "do not represent the Department's settled position" |
| no policy issued | 5 | "My Department has not issued standalone guidance" (chaplaincy + safe access zones) |
| data not held | 4 | "does not hold information on the indication for which drugs have been prescribed" (puberty blockers) |
| passed to another body | 1 | responsibility "transferred ... to local councils in 2015" |

175 answers carry no shape at all, which is the correct result: they are
substantive. `shape()` returning '' is a real answer, not an unclassified one.

Ordered most-specific first, so an answer that declines BOTH the remit and the
data reads as the remit refusal -- the harder wall.

`quote()` returns the SENTENCE carrying the refusal rather than a slice: an
answer averages 980 characters and runs to 4,733, and the opening sentence is
usually a pleasantry ("I recognise the valuable role that chaplaincy services
play...") while the refusal is two sentences later.

**answer_areas / answer_terms / answer_shape are stored SEPARATELY from
`areas`**, and must stay that way. `areas` is the MLA's evidence and feeds the
5CA; a Minister's reply is not the asker's position, and merging them would
credit a member with ground they never took. A test asserts tools/ni_5ca.py
contains neither answer_areas nor answer_shape.

Known limitation, recorded rather than papered over: only answers to questions
that ALREADY matched the taxonomy are held, because detail is fetched only for
matches. An answer on our ground to a question that is not would be missed.
Catching that would mean a detail fetch for every swept question -- thousands --
and since the sweep terms ARE our vocabulary, a swept question that fails the
taxonomy but whose answer passes it is a narrow case. Not built.

Classification happens at store time in ni_pull, so it backfills with no fetch:
every matched question is re-stored on each run.

## Written Questions sweep terms for area 7 (2026-08-20)

Measured with `tools/check_sweep_terms.py` when area 7 was widened to civil
liberties. **Read the tool's `state` with care: it reflects the total only.**
Every term below was judged on its newest headings, and two that the tool
called "good" were rejected on topicality.

| term | total | newest headings | verdict |
|---|---|---|---|
| `pandemic-treaty` | 5 | Disease Control: International Cooperation | keep |
| `pandemic-accord` | 7 | Development Aid: Health | keep, marginal but tiny |
| `digital-ID` | 430 | Digital ID Advisory Group | keep |
| `digital-identity` | 194 | Proof of Identity: Digital Technology | keep |
| `CBDC` | 34 | Central Bank Digital Currencies | keep |
| `IHR` | 95 | **Antisemitism**, Antisemitism | REJECT |
| `health-regulations` | 234 | **Health Hazards: Chemicals** | REJECT |
| `international-health-regulations` | — | HTTP 500 | cannot serve |
| `international health regulations` | — | HTTP 500 | cannot serve |
| `international` (bare) | — | HTTP 500 | cannot serve |

Two findings worth keeping.

**`IHR` matches IHRA in the search.** 95 results whose newest are about
antisemitism: the API matches loosely and picks up the International Holocaust
Remembrance Alliance definition. Our own taxonomy term `IHR` does NOT have this
problem — it is ALL-CAPS so it matches case-sensitively, and it is
word-anchored, tested directly against "the IHRA definition of antisemitism"
and three variants, all correctly rejected. The looseness is the API's, not the
regex's.

**Anything containing "international" answers HTTP 500.** The hyphenated form,
the spaced form and the bare word all fail, so there is no phrasing that
reaches the International Health Regulations through this endpoint. The gap is
recorded in `config/settings.yaml` rather than left to look like coverage;
`pandemic-treaty` and `pandemic-accord` overlap the same material, and the
taxonomy still classifies IHR correctly in anything another term fetches.

**Cost shape of a sweep term.** `pqs.fetch_questions(client, term, take=6)`
takes six per term per run whatever the total, so a term with 430 matches costs
the same as one with 5 — six items into the paid triage pass. Adding five terms
adds at most 30 items a week. This is why a high total is a *precision* problem
(the six you get are the newest of mostly-irrelevant matches), not a cost one.

### What the first real run taught (w/c 2026-08-24)

The pull ran clean and produced **0 items awaiting review**, which is correct
and worth understanding.

`run_weekly` keeps only questions answered within **7 days** of the week start
(`since = week_start - 7`, then `pqs.since()` filters client-side). Every new
term's newest answer predates that window:

| term | lifetime total | newest ANSWERED | verdict |
|---|---|---|---|
| `digital-ID` | 430 | 2026-07-17 | live |
| `digital-identity` | 194 | 2026-07 era | live |
| `CBDC` | 34 | 2025-07-24 | dormant |
| `pandemic-treaty` | 5 | **2023-04-24** | dormant |
| `pandemic-accord` | 7 | 2023 era | dormant |

**`check_sweep_terms.py` measures the wrong thing for this purpose.** It reports
a lifetime total and the newest headings, so it catches an imprecise term — but
it cannot tell a live term from a dormant one, and the weekly only ever sees a
7-day window. "5 matches, all on topic" read as a good term; in fact Parliament
stopped asking written questions about the pandemic treaty in 2023, so that
term will essentially never contribute. Judge a candidate on **the date of its
newest answer**, not its total. The dormant terms are kept and labelled: they
cost at most six items in the week they finally fire.

Combined with summer recess (no questions answered since 17 August on any of
the 44 terms), the run cost effectively nothing — no items reached the paid
triage pass at all.

### The Hansard sweep returning zero: RESOLVED, it was recess

All 44 archives read `TotalResultCount: 0`, including `assisted-suicide` and
`age-verification`, and the previous run was the same. **Not a bug.** The
weekly asks Hansard for the EDITION WEEK only:

```python
hansard.search_contributions(client, hansard.spoken_form(term),
                             week_start.isoformat(), week_end.isoformat())
```

Probed live to confirm, rather than reasoned about:

| term | range | total | newest |
|---|---|---|---|
| assisted dying | 2026-08-24..30 | 0 | — |
| assisted dying | 2026-08-17..23 | 0 | — |
| assisted dying | June 2026 | 47 | 2026-06-23 |
| assisted dying | all 2026 | 522 | 2026-07-03 |
| digital ID | all 2026 | 1189 | 2026-07-23 |

The last sitting contributions are late July; the House is in summer recess.
Zero is the correct answer for both weeks pulled.

**What misled me was our own archive filename.** The slug was
`search-{term}-{start[:4]}-s{skip}`, so a one-week request was filed as
`hansard_search-digital-id-2026-s0.json.gz` — which reads as a whole-year
search, making 44 legitimate zeroes look like a broken sweep. The slug now
carries the full range (`...-2026-08-24-to-2026-08-30-s0`), with a test that two
weeks in one year cannot share a slug.

### Hansard splits a phrase into words, and the taxonomy catches it

`SearchTerms` in the response for "digital ID" comes back as
`['digital', 'id']` — the API searches the words separately, which is why the
term reports 1189 contributions for 2026. The pipeline is self-correcting:
every contribution is re-filtered through the taxonomy, which wants the exact
phrase. **Of the first 100 fetched, 11 passed and 89 were dropped.** So the real
ledger yield for `digital-ID` is roughly 5-6 rows per sitting week, not 50.

Corrected per-term picture for the five new terms, 2026:

| term | Hansard 2026 | newest | written questions |
|---|---|---|---|
| `digital-ID` | 1189 raw (~11% survive) | 2026-07-23 | live, 2026-07-17 |
| `digital-identity` | 72 | 2026-07-23 | live |
| `pandemic-treaty` | **3** | **2026-07-14** | dormant since 2023 |
| `pandemic-accord` | **1** | **2026-07-16** | dormant since 2023 |
| `CBDC` | 0 | — | dormant, 2025-07-24 |

**This corrects the "DORMANT" labels recorded above.** `pandemic-treaty` and
`pandemic-accord` are dormant only in WRITTEN QUESTIONS; they are live in
DEBATES as recently as July 2026. A sweep term feeds both APIs, so judging it on
one of them was measuring half the picture. Only `CBDC` is dormant in both.

**And it corrects the cost claim.** Hansard contributions do NOT go through the
paid triage pass — `_hansard()` calls `intel.record_event` into the MP ledger,
never `store_item` — so the "at most 30 items a week" figure for triage stands.
But it covered only the PQ side: Hansard also adds ledger rows, and those feed
MP intelligence and area 7's 5CA.

## What publishes on a Monday, and two guards worth knowing (2026-08-20)

Audited after clearing a `brief_log` rejection nearly caused an unrequested
Drive upload. `run_monday.py` has five outward-facing steps and each has its own
gate:

| step | gate | state on 2026-08-20 |
|---|---|---|
| Slack edition + canvas | a `publish_log` row for the week | w/c 08-24 absent -> **will post** |
| Asana reading task | same as above | will be created |
| partner site deploy | none (always) | will deploy |
| new briefs (each creates an Asana approval task) | slug absent from `brief_log` | "nothing new" -> none |
| `check_brief_approvals` | `status='pending' AND asana_gid IS NOT NULL` | empty |
| `publish_briefs_to_drive` | `status='pending' AND drive_file_id IS NULL` | empty |

All six briefs are `rejected`, so the two brief-publishing queues are inert.

**`rejected` is load-bearing in two places, not one.** `make_briefs` refuses to
regenerate it, AND the Drive publisher refuses to publish it. Clearing a
`brief_log` row to rebuild a brief for inspection re-arms a scheduled
outward-facing job. Restore the row, or set `drive_file_id` to a sentinel,
before the next Monday run.

**A manual pull silently disables the scheduled one.** `pull()` guards on
`pull_log`, and the Sunday workflow runs `run_weekly.py --pull "$WEEK"` with no
`--force`. On a Sunday `$WEEK` is tomorrow's Monday, so pulling the NEXT week by
hand mid-week writes the row that Sunday's run then trips over: it prints
"already pulled", collects nothing, and Monday publishes an edition built from
the older data. Found here because the next week had been pulled on the Thursday
to exercise new sweep terms; the row was deleted so Sunday runs normally.

If a mid-week pull of the coming week is ever wanted deliberately, delete its
`pull_log` row afterwards or expect the Sunday run to no-op.

Other scheduled workflows, checked at the same time: `ni-weekly` (Sat 06:00 and
14:00 UTC) is a pull with no publish attached, so NI still cannot reach Slack;
`un-calls-weekly` has its cron **commented out** and is dispatch-only, so nothing
UN publishes; `upr-monthly` is the 3rd of the month. Only `monday-publish`
publishes.

## The WHO name needed the same guard as the acronym (v0.8, 2026-08-20)

Found by reading the full NI monitor after widening area 7. The motion
**"Addressing the Mental Health Crisis"** was showing at area 7, matched on
`World Health Organisation` — and its text only says its recommendations

> align with recent calls from the World Health Organisation and the United
> Nations for systematic mental health reform

WHO as a research citation, not health sovereignty. At v0.6 the acronym `WHO`
was carefully protected — all-caps for case-sensitivity, plus a `[with:
pandemic, treaty, "health regulations", accord]` guard — and the **spelled-out
name was left unguarded**, which is the same term with none of the protection.
Any health motion citing WHO would have matched.

Both spellings now carry the same guard. Blast radius when found: one stored row
in `ni_items`, none in `mp_events`. NI matched motions went 4 to 3, and the
remaining three are right: Modernising Divorce Laws [9], Standing up to Racism
[7, 11], Women's Rights in Northern Ireland Prisons [5].

**The lesson is about guarding a concept, not a string.** Guarding `WHO` while
leaving `World Health Organisation` open protected the spelling, not the
meaning. When a term needs company, every way of writing that term needs the
same company.

## Holyrood open data, probed 2026-08-20 (phase 1 of the watching brief)

`data.parliament.scot/api/*`, keyless. The full endpoint index is at
`/api/apilist` (209 entries). Traps found by probing, not reading:

* **The API list lies about votes.** It advertises `Votesmotions` (plural),
  which 404s for every year. The real endpoint is singular lowercase
  `votesmotion?year=N` (19MB / 19,473 per-MSP rows for 2026).
* **The motions endpoint ignores `?year=`.** It accepts the parameter and
  serves the full 110MB / 84,751-row dump since 1999 either way. Check sizes,
  not status codes.
* **No search API exists** -- questions come as whole-year dumps
  (`Motionsquestionsanswersquestions?year=N`, 7MB / 4,717 rows for 2026). So
  the Holyrood brief has NO sweep terms: the taxonomy classifies every row,
  and the entire NI/Westminster family of search-term traps (loose matching,
  hyphen sensitivity, dormant terms) does not exist here.
* **Answers arrive inline** on the question row (`AnswerText`), so there is no
  per-answer fetch to guard -- the thing NI spent 8 minutes a week on until
  guarded.
* **Party history is native date ranges** (`/api/memberparties`,
  `ValidFromDate`/`ValidUntilDate`, null = current; 976 rows, and exactly 129
  current = the chamber). Party-as-at-date needs no reconstruction.
* **Year dumps are fetched with `archive=False`** (new HttpClient option):
  data/raw is committed to git weekly and the API serves these canonically by
  year, re-fetchable at will. `sp_items.body` stores the text whole, so
  offline re-classification (`sp_pull.py --reclassify`) never re-fetches.
* Text carries HTML entities (`&rsquo;`, `&pound;`) -- unescape before
  classifying or phrase terms fail on the entity.
* The Official Report is `orsplenarymeeting?year=N` (65MB for 2026) --
  phase 3, offline classification like NI Hansard. Committee reports are
  `Orscommitteemeeting?year=N` and the apilist stops advertising it after
  2024; unverified whether later years exist.

First pull: 15,297 rows (4,717 questions 2026 + 10,580 motions since
2024-01-01), 146 questions and 113 tier-1 motions on our ground. The chamber is
session 7 (post-May-2026 election): S7W references, Reform UK MSPs on the
roster.

### Two taxonomy bugs Holyrood exposed, one of them Westminster's

* **`RSE` is also the Royal Society of Edinburgh.** 3 of the first 5 Scottish
  rows matching the term were the Society. Guarded with education company at
  v0.9; measured first -- all 4 real Westminster excerpts keep company.
* **`Law Commission` was a Westminster false-positive factory.** 141 ledger
  lines match it and only 6 keep marriage/family company -- the rest are
  leasehold, digital wills, self-harm internet regulation, quietly inflating
  area 9 evidence in the Westminster 5CA all along. Guarded at v0.9. The
  STORED mp_events areas are stale until the next ledger backfill re-runs;
  recorded here so the inflation is known before it is fixed.

### The tier gate

Holyrood tables thousands of congratulatory motions a year, and tier-2
vocabulary alone filed a dental-charity fundraiser under assisted dying
("hospice") and a stoma-friendly airport under sex-based rights ("changing
room*"). `sp_items.tier` records the match tier; the monitor shows tier 1
(113 motions, genuinely ours) and counts tier-2-only rows as held. Westminster
gates tier 2 behind paid triage; the watching brief gates it behind a column,
for free.

## Holyrood phase 2: divisions (2026-08-20)

`votesmotion?year=N` ingested for 2024-2026: **656 divisions, 84,567 vote
positions**, 58 classified by their own motion's wording (24 tier-1), zero
unlinked references. The headline record arrived whole: the Assisted Dying
(Scotland) Bill's Stage 3 defeat on 2026-03-17, 57-69, with all 129 MSPs'
positions -- alongside its Stage 1 (70-56) and the financial resolution
(70-31), so the trajectory is queryable.

Findings that shaped the code:

* **Two Detail schemas coexist in one dump.** Most rows carry
  `MotionAgendaItemID`; 1,419 of 19,473 rows in 2026 -- 11 whole divisions --
  carry `BackupAgendaItemID` instead. Keying on the first alone silently
  dropped those 11, caught only by cross-checking the division count against
  an independent (reference, time) grouping. The stored key is prefixed
  (`m<id>` / `b<id>`) so the two ID spaces cannot collide. Regression-tested
  with one fixture division per schema.
* **Classification is an exact-key join, not text matching.** A division's
  reference `S7M-00469.5` IS amendment 5 to motion S7M-00469, and both are
  rows in the motions dump with their own full text, already in sp_items.
  The thing NI needed a Hansard amendment parser for arrives here as a
  foreign key. A division whose reference is absent from sp_items is stored
  unclassified and counted, never guessed.
* **Every MSP appears in every division** (129/128 rows), with `Not Voted`
  and `Abstain` as first-class values -- absence is data. The API also stamps
  each vote row with the voter's party at the time AND `MSPSharesParty`, its
  own whip-agreement flag, which the 5CA phase can use directly.

## Holyrood phase 4: stance file, 5CA, weekly workflow (2026-08-20)

* **config/sp_stance.yaml** -- same contract as NI: a human writes what a vote
  means, `draft: true` places nobody, sign conflicts flagged never averaged.
  Seeded with THREE drafts, texts quoted from the words voted on: the Stage 3
  passage vote (S6M-21005, aye -2 / no +2 -- the vote that killed the Bill),
  Stage 1 general principles (S6M-17416, aye -1 / no +1, weaker by the
  allow-scrutiny convention: 13 more ayes than Stage 3), and the wrecking
  amendment to Protecting Single-sex Spaces (S6M-16755.3, aye -1 / no +1,
  with a confirmation caution: its Equality Act citation reads differently
  post-For Women Scotland than it did in March 2025). Two candidates were
  deliberately NOT seeded -- their stored texts truncate before the operative
  words, and a meaning line must be drafted from what was voted on.
* **tools/sp_5ca.py** -- 129 current MSPs, placement only from confirmed
  meaning lines; questions are activity, not direction. Holyrood adds a
  REBELLED marker on evidence lines from the API's own MSPSharesParty flag --
  a chosen act against the party line, free with the data. All-draft run
  verified: 67 of 129 with evidence, 0 placed. (67 not 129: the assisted
  dying votes are session-6 divisions, so only re-elected MSPs carry them.)
* **Motionsquestionsanswerssupports answered 503** twice on 2026-08-20, so
  co-signatories are not held; proposer sponsorship works via the motion's own
  msp_id. Retry when adding motion meaning lines.
* **.github/workflows/sp-weekly.yml** -- Friday 06:00 UTC + 14:00 retry
  (Holyrood sits Tue-Thu; clear of NI Sat, Sunday pull, Monday publish), same
  parl-monitor-state concurrency group, NO publish step, separation-tested.
* Fixed in passing: a stray Arabic character in the Vote dataclass field name
  (`party_abbر`) -- Python accepts unicode identifiers, so it compiled and
  passed tests while being untypeable.

## The corrective ledger backfill (2026-08-21)

The two documented defects in stored Westminster data are fixed, and the
numbers are large enough to matter.

**The hyphen under-collection was a third of the debate ledger.** Re-running
backfill_hansard (now via `spoken_form`) over all 44 terms, 2020->today, grew
debate events from **15,199 to 20,632** -- 5,433 speeches (+36%) that the
hyphenated searches never returned. The single biggest recoveries were
home-education (~1,470) and the migration family; abortion-clinics, the term
that exposed the bug (0 hyphenated vs 3 spaced), recovered ~140.

**The Law Commission / RSE inflation is gone.** retag_passages re-derived
every pq and debate row offline from data/raw (full text coverage, zero
rows without archived text). Rows carrying area 9 fell from **368 to 133**
(debate 342->115, pq 26->18) -- nearly two-thirds of the marriage-and-family
evidence was leasehold, digital wills, hate-crime and elections material
admitted by the unguarded "Law Commission". The regenerated area 9 sheet
reads ++2 +9 0x629 -7 --3 on 54 MPs with evidence: a much smaller, much more
honest sheet.

Order of operations that worked: re-fetch first (refreshes areas at store
time AND recovers missing speeches, since record_event upserts on conflict),
then retag as the offline sweep for anything the re-fetch did not touch.
The PQ side needed retag alone -- its raw archives held full text for all
3,846 rows.

## Holyrood has TWO vote classes, and votesmotion carries only one (2026-08-21)

Christopher asked why not all votes were included; he was right that they were
not. `votesmotion` carries MOTION decisions (final passage, amendments to
motions) with per-MSP votes. **Bill AMENDMENT divisions -- Stage 2/3 amendment
votes -- exist only in the Official Report, as prose aggregates**: "The result
of the division is: For 47, Against 67, Abstentions 0. Amendment 6 disagreed
to." In 2026 that second class was **530 of 672** division results, including
all **215** of the Assisted Dying Bill's Stage 3 amendment fight on 13 March.

Now harvested into sp_divisions with `source='official-report'` and the
amendment number and outcome parsed from the same row (measured first: exactly
one result per contribution row, and the outcome always sits in the same
text). Rows citing a motion reference (142 in 2026) are skipped as duplicates
of votesmotion. 1,348 stored for 2024-2026, 217 on our ground by bill heading.

**No per-member roll-call exists anywhere in the open data** for this class --
the OR prints aggregates only -- so these divisions are record and context and
can never place anyone in a 5CA. OPEN QUESTION: parliament.scot's
votes-and-divisions pages may carry the rolls; if per-MSP amendment votes are
ever wanted (they would be the richest stance evidence Holyrood has), that is
a website-scrape question, not an API one.

Also confirmed today: S6M-17416 (Stage 1 general principles, aye -1 / no +1 --
weights stand, Stage 1 ayes include allow-scrutiny votes). Two of three
meaning lines are now confirmed; the assisted-dying 5CA places from both.
