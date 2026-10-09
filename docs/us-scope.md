# United States: scoping the Congress monitor

Probed live on 9 October 2026, from the laptop. Every number below was
measured, not estimated. Groundwork only: nothing is built, scheduled or
stored, and the probe data sits outside the repo. Congress only; the state
legislatures are a later decision, taken in blocks (see the end).

## Decisions (Christopher, 9 October 2026)

- **Own edition.** The US gets its own edition, not a section.
- **Shared keyword list, no addendum.** American terms sit in the main area
  lists of docs/keyword-taxonomy.md (v1.17) beside the British ones:
  mifepristone is not an American issue. (A first cut on 9 October kept them
  in a separate addendum section; Christopher had them merged the same day.)
  Named bills whose titles would collide go in `config/watchlist-us.yaml`,
  applied by bill key.
- **All 50 state legislatures**, after Congress.
- **Contraception is a life issue** (area 1). **Antisemitism is out.** **DEI**
  is not a term of its own: it is caught where it meets the areas already
  watched (gender, sex-based rights, schools).
- **The US edition goes to Christopher alone** until it is good.
- Not yet decided: the executive-actions section.

## Phase 1: built, 9 October 2026

`tools/us_rollcalls.py` into `us_members`, `us_bills`, `us_cosponsors`,
`us_divisions` and `us_votes` (schema in `src/us_store.py`, declared in
`db.TABLES`). Live run into a scratch database, not the store:

| | Read | On our ground |
|---|---|---|
| Bills and resolutions, 119th Congress | 19,596 | 715 |
| House roll calls | 676 | 121 |
| Member positions | 292,248 | |
| Cosponsorships | 182,211 | |
| Members (crosswalk + former members from bills and votes) | 556 | |

Five and a half minutes, no gaps. The American terms took bills on our ground
from 650 to 715 and caught votes the unchanged taxonomy missed: the
Stopping Indoctrination and Protecting Kids Act, the Do No Harm in Medicaid
Act, the Protect Children's Innocence Act.

- **Every position is stored.** The positions come in the same file as the
  vote, so there is no per-division fetch to save, unlike Canada.
- **Votes inherit their bill's areas**; `own_areas` keeps the vote's own
  match apart. The cost was visible at once: every FY2027 NDAA amendment
  vote carried area 8 because the bill's summary mentions chaplains. Phase 1b
  (below) stops that for every House amendment vote whose purpose is known.
- **Not scheduled.** The three sighting tables are exempt in
  `tools/coverage.py` until a US weekly workflow exists; that exemption must
  move to FEEDS when it does.

## Phase 1b: amendment purposes, built 9 October 2026 (two sources)

A House amendment vote's `amendment_key` ('119/hamdt/242'),
`amendment_text` ("description | purpose"), `amendment_checked` and
`purpose_source` on `us_divisions` are filled from two sources, in order:

1. **BILLSTATUS, keyless, first.** The purpose was already in a file we
   download: the BILLSTATUS bulk record of a bill lists every House
   amendment to it, with its description ("An amendment numbered 1 printed
   in Part A of House Report 119-755 to strike section 1213..."), its
   purpose and the roll calls it was voted on. Read with the bills, at no
   extra request (`link_amendments`, `purpose_source='billstatus'`).
2. **Congress.gov API, keyed, for what BILLSTATUS has not explained.**
   BILLSTATUS lags the floor by days. With `CONGRESS_API_KEY` (an
   X-Api-Key header, never in a URL, log or gap row), `fill_amendments`
   maps each remaining roll call to its amendment (`house-vote`, then
   `amendment`) and marks it `purpose_source='congress-api'`. A later
   BILLSTATUS run never overwrites what the API gave. No key: the step
   says so and the vote waits for BILLSTATUS.

Keyless sources probed live on 9 October 2026:

| Source | Answers | Gives |
|---|---|---|
| BILLSTATUS bulk (GovInfo) | yes | every House amendment, its purpose, its roll calls. **The route.** |
| rules.house.gov bill pages | yes (920 KB for H.R. 8800) | all 1,400 submitted NDAA amendments with one-line summaries and status; links to the Rules reports |
| Rules Committee reports (GovInfo CRPT HTML) | yes | the made-in-order summaries numbered as the Clerk numbers them ("Part A Amendment No. 1"). A fallback, not needed |
| Clerk roll-call XML | yes | the amendment's sponsor-or-designee and its floor sequence number only; no purpose |
| congress.gov amendment pages | **403** | not worked around |

Two traps the Clerk sets: the "Amendment No." in its author line is the
**Rules report's** number, not the floor sequence (`amendment-num`); and
the member named may be a designee (Boebert offered Roy's amendments Nos.
1 to 4 to H.R. 8800). The BILLSTATUS route joins on the roll number, so
neither matters; where two amendment records claim one roll, the one whose
sponsor the Clerk names wins. An **en bloc** amendment's description is a
list of numbers, not a purpose: it is stored with no purpose and keeps
inheriting.

**The rule** (documented once, in `tools/us_rollcalls.py`; the en bloc
test is `us_store.has_own_purpose`, shared with the edition): `own_areas`
is always what the vote's own text matched, now including the amendment
text. A House vote whose amendment text is a real purpose takes `own_areas`
**alone**; every other vote (passage, recommit, rules, en bloc, Senate
votes, an amendment no source has explained yet) still adds its bill's
areas. The edition prints the purpose
under the vote and says "matched on amendment purpose".

**Measured on the 119th Congress, BILLSTATUS alone, no key** (676 House
roll calls, scratch store):

- **90 House amendment votes; all 90 matched to a BILLSTATUS amendment,
  89 with a purpose** (the 90th is an en bloc on H.R. 3944). Six more votes
  concur in a Senate amendment; they are not House amendments and are left
  alone.
- **House roll calls on our ground: 132 before, 83 after.** Every one of
  the 49 that left was an amendment vote that had only inherited.
- **NDAA FY2027 (H.R. 8800): 19 amendment votes, all 19 inherited area 8
  before; 2 kept an area on their own purpose, 17 lost it.** Kept: roll
  266 (Boebert No. 18, codify the ban on transgender service members: sex
  based rights) and roll 273 (Self No. 28, protections for chaplains:
  freedom of religion).
- **NDAA FY2026 (H.R. 3838): 17 amendment votes, all inherited; 2 kept,
  15 lost.**
- **Appropriations (H.R. 3944, 4016, 4553, 7006, 7148, 8469, 8595): 29
  amendment votes, 18 inherited before; 1 kept (the H.R. 3944 en bloc,
  still inheriting), 17 lost.** None of the 17 is on our ground on a
  reading (Ukraine, Taiwan, Israel, the UN, Fulbright, two judges' pay).

**What the strict rule now misses: American wording, again.** Five of the
votes that lost their inherited area are on our ground, and the taxonomy
does not match their purposes: H.R. 8800 rolls 267 ("gender related medical
care under TRICARE") and 268 ("male participation in female sports at
DoDEA schools"); H.R. 3838 rolls 246 ("gender-related medical treatment"),
247 (male cadets in women's athletics) and 248 (a survey on "gender
identity"). Before, they showed only as noise under "freedom of religion";
now they do not show at all. The fix is terms in docs/keyword-taxonomy.md
(Christopher's call, then regenerate `config/taxonomy.yaml`), not a return
to inheritance.

## The finding that shapes everything

**The English taxonomy mostly works in the US, but only if a vote is joined
to its bill.** `config/taxonomy.yaml`, unchanged, run over all 19,596 bills
and resolutions of the 119th Congress:

| Text matched | Bills with any area | On our ground (not 11) |
|---|---|---|
| Titles only | 1,006 | 468 |
| Titles + CRS subject terms + CRS summary | 1,321 | 650 |

On our ground by area (full text): abortion 175, free speech 124, parental
rights 122, prostitution and trafficking 90, freedom of religion 56, sex-based
rights 52, assisted dying 38, surrogacy and embryology 20, organ donation 15,
marriage 12, gender medicine 9, conversion practices 4.

**House roll calls are the trap.** The Clerk's vote record carries a
description line, but it is blank for most amendment and procedural votes.
Matched on its own text, the taxonomy found **9 of 676** House roll calls in
the 119th Congress. Joined to the bill record by bill number, it found **116
roll calls on 38 measures**. That is the Westminster hard rule again: key on
the bill ID, never the title. Here the vote often has no title at all.

**Recall, checked against Congress's own subject index.** The Congressional
Research Service tags every bill with subject terms. Against those tags:

- **Abortion: 72 of 72 caught. Human trafficking: 68 of 68. Pornography: 25 of 25.**
- **Sex, gender, sexual orientation discrimination: 29 of 66.** The misses are
  American names for things the taxonomy knows in British English.

### What it missed: American naming, not American issues

Each needs a US watchlist entry or a taxonomy decision (Christopher's call,
as with "pornograph*" in Canada):

- **Equality Act (H.R. 15, 218 cosponsors; S. 1503).** The US Equality Act
  adds sexual orientation and gender identity to the Civil Rights Act. It is
  the largest single miss. The UK term is "Equality Act 2010",
  so the US bill passes through.
- **Stop Comstock Act (H.R. 2029, 146 cosponsors; S. 951).** Comstock is the
  1873 law on mailing abortion drugs. Neither "Comstock" nor "mifepristone"
  is in the taxonomy, although "chemical abortion" bills matched on their
  summaries.
- **End Taxpayer Funding of Gender Experimentation Act (H.R. 2202, S. 977).**
  "Gender experimentation" and "gender transition" are not terms.
- **Children online:** Children and Teens' Online Privacy Protection Act
  (COPPA 2.0, S. 836), Kids Off Social Media Act (S. 278), Sunset Section 230
  Act (S. 3546). KOSA (S. 1748) and the SCREEN Act did match.
- **Girls' sports:** Fair Play for Girls Act (S. 74), Protection of Women in
  Olympic and Amateur Sports Act (S. 405). The flagship Protection of Women
  and Girls in Sports Act (H.R. 28, S. 9) did match.
- **Schools:** Say No to Indoctrination Act (S. 2251), Dismantle DEI Act.
  Whether DEI is our ground is a scope question, not a vocabulary one.
- **Life at Conception Act of 2026 (S. 3667)** missed while the House version
  (H.R. 722) hit. The House bill has a CRS summary and the Senate bill does
  not yet; the title alone carries no term. "Life at conception" and
  "personhood" belong in the term list.
- **Antisemitism Awareness Act (H.R. 1007, S. 558).** Not in scope today. The
  UK taxonomy carries anti-Muslim hostility under area 7; whether antisemitism
  sits beside it is a scope decision.
- Contraception bills (Right to Contraception Act and others) miss. Probably
  correct, but say so explicitly.

### What it caught that it should not have

Area 12 (trafficking) is noisy in the US: "human trafficking" appears in
almost every border and immigration bill (Kayla Hamilton Act, Secure America
Act, the FY2026 NDAA), so those land in 12 when they are really area 11. The
CBDC and encryption terms pull in crypto-market and telecoms bills (CLARITY
Act, a housing bill, a mobile-networks bill). Triage would score these low,
but area 12 needs a US guard.

## The omnibus problem (no Westminster equivalent)

**Most of the US fight on our ground happens as riders inside must-pass
bills**, not as standalone bills. Of the 38 voted measures, the heaviest are:

- **NDAA FY2027 (H.R. 8800): 21 roll calls**, almost all amendment votes, matched only
  on "chaplain*" in the bill's summary.
- **Appropriations and continuing resolutions:** H.R. 7148 (Consolidated
  Appropriations Act, 2026), H.R. 5371, H.R. 6500, H.R. 9770 (CR for FY2027),
  H.R. 1968, H.R. 8595, H.R. 7006, all matched on "abortion" (the Hyde
  Amendment language) or "religious freedom" in a 100-page summary.
- **H.R. 1, the reconciliation bill**, which carried the Planned Parenthood
  defunding provision. It matched on abortion and unborn, which is right, but
  it would match those words in any year.

So the bill-level match says "this omnibus touches abortion", which is
always true and never news. **What matters is which amendment was voted
on.** The roll-call XML names the amendment and its author ("Roy of Texas
Amendment No. 1") but not its purpose. The purpose text lives in the
BILLSTATUS amendment records (keyless), the Congress.gov API `amendment`
endpoint (keyed) and the House Rules Committee's amendment lists and
reports (rules.house.gov, keyless). Phase 1b above uses the first two.

This is the US equivalent of the EU lesson: match the division on its own
text, inherit from the parent bill only with care. Amendment-level matching
is a phase 1 requirement, not a refinement.

## What the US publishes

### House roll calls: works today, open, no key

- `clerk.house.gov/evs/<year>/roll<NNN>.xml`, one file per vote, about 95 KB.
  2025: 362 votes. 2026: 314 votes, the last on 16 September 2026.
  676 in all, which matches Congress.gov's count.
- **Every member's position in the same file**, with party and state at the
  time and the member's **Bioguide ID** (`name-id="A000370"`), the stable
  key across every US source. Party-at-the-time comes free, as in Canada.
- **Gotcha:** a roll number that does not exist returns **HTTP 200** with an
  error body (`Error sanitizing file "roll363.xml"`), not a 404. A collector
  that trusts the status code runs on for ever and stores error pages.
  Validate on `<vote-metadata>`.
- Also on Congress.gov as `/v3/house-vote/119` (beta), keyed, pointing back
  to the Clerk's XML. The Clerk is the primary source.

### Senate roll calls: built 9 October 2026, runs from CI only

**Resolved.** senate.gov refuses the laptop on every page with Proton VPN
OFF too (traffic straight through the home router), with curl and with
Python's urllib alike: an address block, not a VPN or UA one. GitHub's
runners get everything (the one-off `us-senate-probe.yml`). So the Senate
half of `tools/us_rollcalls.py` runs in the US weekly workflow; locally it
logs one gap per session and carries on. Its tests use real files that probe
saved (`tests/fixtures/us_senate/`).

What the Senate publishes, measured from CI: a menu per session (659 votes
in 2025, 256 in 2026 to 30 September) and one XML per vote with every
senator's position, party and LIS ID. Of the 915: **445 are nominations**
(judges, cabinet, en bloc packages) which only the Senate votes on; **190
link to a bill on our ground**, but about twenty of those are the same
shutdown-CR cloture vote taken again and again, which the edition must
fold. Unlike the House, a Senate amendment vote carries the amendment's
**purpose** ("To prohibit the use of funds..."), and the vote file carries
the bill's long title, so Senate votes classify on their own text before
the bill lends anything.

Positions are keyed on LIS IDs and mapped to Bioguide: sitting senators from
the crosswalk (all 100 carry one), former senators from the historical
crosswalk, fetched only when an unknown ID appears. An ID nobody knows is
dropped and recorded as a gap, never stored under a guess.

### (Superseded) Senate roll calls: blocked from the laptop

`senate.gov` returned **403 Access Denied on every page, including the
homepage**, with our honest UA and with curl's default. It is a network
block, not a UA filter. The Canada probes ran through Christopher's Proton
VPN, which is the likeliest cause. **Re-test from GitHub Actions** before
deciding anything. The source, when reachable, is
`senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_<session>.xml`
(every vote of a session in one call) plus one XML per vote. Congress.gov
has no Senate vote endpoint (`/v3/senate-vote` is 404).

The Senate matters: the Born-Alive Act (S. 6) and the girls' sports bill
(S. 9) both died there on cloture this Congress.

### Bills: works today, open, no key (bulk) or keyed (API)

- **GovInfo BILLSTATUS bulk XML**, one zip per bill type:
  `govinfo.gov/bulkdata/BILLSTATUS/119/hr/BILLSTATUS-119-hr.zip`
  (32 MB for House bills; all eight types are about 54 MB). Each record has
  titles (official, short, popular), **CRS subject terms**, **CRS
  summaries**, sponsor, cosponsors, actions and committees. That is much
  richer than LEGISinfo, whose summaries were empty.
- **Congress.gov API** (`api.congress.gov/v3`): bills, amendments, committee
  meetings, nominations. 19,602 bills in the 119th. Needs an api.data.gov
  key. `DEMO_KEY` answers but allows **10 requests an hour**, so a real key
  is needed. It is free and issued instantly by email; Christopher should
  request it himself.
- **Bill text:** GovInfo BILLS collection, XML. Body matching as
  `src/eudoc.py` does it would work directly, with no PDF step.

### Members: works today, open, no key

`unitedstates.github.io/congress-legislators/legislators-current.json`:
539 current members (House 221 R, 217 D, 1 I; Senate 53 R, 45 D, 2 I), each
with Bioguide, LIS (Senate vote ID), GovTrack, OpenSecrets, Wikidata and
other IDs. It is a volunteer project, but it is the standard crosswalk and
the Bioguide IDs come from Congress. Use it for identity, not for votes.

### Floor schedule and committee meetings: built 9 October 2026, no key

The What's On equivalent. `tools/us_schedule.py` reads what is SCHEDULED
from today to the Sunday after the coming Monday (a Friday run: ten days)
into `us_schedule` (one bill at one event, keyed on the bill key and joined
to `us_bills` for areas and scores), `us_meetings` (every committee meeting,
with or without a bill) and `us_schedule_weeks` (what each source answered
for each week asked). The edition prints it as **Coming up**, after the
dates that matter. Run from `jobs/us-weekly.sh` after the bills and before
the edition. Sources, all keyless:

- **House floor:** `docs.house.gov/billsthisweek/<yyyymmdd>/<yyyymmdd>.xml`,
  the Majority Leader's list for the week, by WEEK only (it never says which
  day). A week the House is out answers **404**, read as "no list", not a
  failure. `docs.house.gov/floor/` names the latest week posted; when no
  week ahead is listed, that list is read again so the edition can say when
  the House last scheduled business, and the table keeps moving in recess.
- **House committees:** the repository's day pages
  (`Committee/Calendar/ByDay.aspx?DayID=<mmddyyyy>`), then each meeting's
  page for its kind, its status (rescheduled, postponed, cancelled) and its
  "Text of Legislation". The week view is NOT complete (14 meetings for the
  week of 14 September against 17 on the 16th alone). The "Meeting XML" is a
  postback, and on the one markup tried its `<legis-num>` dropped the bill
  type on half the bills ("10355" for H.R. 10355), so the page is read.
- **Senate committees:** `senate.gov/general/committee_schedules/hearings.xml`,
  with the bills each meeting takes as `<AssociatedDocument>` (`PN`, a
  nomination, is left out).
- **Senate floor:** `senate.gov/legislative/schedule/floor_schedule.htm`, the
  next sitting only ("Convene at 3:00 p.m."), rarely with a bill.

**senate.gov refuses the laptop** (403, as for the roll calls) and answered
the `probe-hosts` workflow from GitHub on 9 October. So the Senate half runs
in the Senate-only GitHub run the Mini asks for (`--senate-only`, in the
same branch of `jobs/us-weekly.sh` as the Senate votes); locally it logs one
`[gap]`, marks the weeks `refused`, and the edition says the Senate was not
read. A refusal never overwrites a week an earlier run read. The Senate
fixtures of the week of 14 September are senate.gov's own files as the
Internet Archive saved them that morning; the recess ones came from the
probe workflow.

Each scheduled bill is classified on its OWN line too (`own_areas`): the
floor item's text, the House legislation entry, the Senate document
description. Never the meeting's title, which would lend one bill's words to
every other bill on the agenda (the first build gave all ten bills of a
Senate Commerce markup "free speech" because one of them was the JAWBONE
Act).

**Measured, week of 14 to 18 September 2026** (the last the House sat; live
for the House, fixtures for the Senate, joined to the real store):

| | Listed | Bill rows | On our ground |
|---|---|---|---|
| House floor list | 78 items (3 categories), every one naming a bill | 78 | 2: H.R. 7834 Safe Cloud Storage Act, H.R. 9086 Foreign Service Modernization Act |
| House committee meetings | 41 (30 hearings, 9 markups, 2 meetings) | 118 | 0 |
| Senate committee meetings | 17 (13 hearings, 4 business meetings) | 39 | 1: the Commerce markup taking S. 4749, the JAWBONE Act |

Every one of the 235 bill rows joined a bill already in `us_bills`. The
week took 47 requests and 11 seconds. **Live, 9 October 2026** (into a
scratch copy of the store): no list for the weeks of 5 and 12 October (404),
no House committee meeting on any of the ten days, the 14 September list
read again, and the House committee week of 14 September read once as a
seed (a first run in recess would otherwise leave `us_meetings` empty for
weeks, which the coverage watch reads as a wipe); Senate one gap.

Watched by `tools/coverage.py`: `us_schedule_weeks` weekly (a row per week
asked, every run), `us_schedule` weekly with a week's grace, `us_meetings` a
month plus a month's grace (the House posts no meeting in recess). The step
stamps its own heartbeat, `US schedule`, which excuses the empty tables
until its first run.

### Congressional Record (debates): works, keyed

GovInfo `CREC` collection: one package per day (35 issues since
1 September 2026), split into granules per speech segment, with speakers
tagged. It is the Hansard equivalent for debate packs. It needs the same
api.data.gov key.

### Federal Register: works today, open, no key

`federalregister.gov/api/v1/documents.json`. This is the executive side
(rules, proposed rules, executive orders, comment periods), the equivalent
of gov.uk consultations. Phrase counts since 20 January 2025: "religious
liberty" 31, "abortion" 28, "gender-affirming" 9, "parental rights" 11,
"pornography" 12. "Euthanasia" (13) is animal welfare and noise. In the US,
much of our ground moves by executive order and agency rule, not statute.

Regulations.gov (comment dockets) needs the same key. It answered with
`DEMO_KEY`.

### Supreme Court: reachable, HTML

`supremecourt.gov/opinions/slipopinion/25` lists the term's opinions as PDF
links (75 on the page). It is a scraper, as the SCC collector is.

### Not available

- **Petitions:** none. The White House's We the People site is gone and
  Congress has no petition system. No equivalent of the e-petitions section.
- **Written questions:** none. Members write letters, which are not
  published centrally. No equivalent of PQs or WMS.

## What a US edition would look like (proposal)

Westminster's sections map as follows: bills (BILLSTATUS), divisions (House
roll calls, Senate when unblocked), debates (Congressional Record), What's
On (floor schedule plus committee meetings), consultations (Federal Register
comment periods). No PQs, no EDMs, no petitions. Add an **executive actions**
section (executive orders and agency rules), which Westminster does not need.

**The 5CA translates.** Every member has a Bioguide ID, every House vote
carries positions and party-at-the-time, and cosponsorship is a strong
signal Westminster lacks: H.R. 7 (No Taxpayer Funding for Abortion) has 128
cosponsors, H.R. 15 (Equality Act) 218. Cosponsoring is a public, recorded
position, so it can sit just under a vote in the evidence hierarchy.

## The weekly schedule

`.github/workflows/us-weekly.yml`: Friday 10:00 UTC, retry 12:00 (06:00 in
Washington, after Thursday's votes). Members, all bills (the BILLSTATUS zips
are re-read whole), new House roll calls, new Senate votes, the week ahead. Watched by the
failure alert and `tools/coverage.py` (bills and members weekly; votes a
month plus a month's grace, because the House cast no vote between
16 September and the midterms). A hand dispatch can reclassify first.
**It runs only once merged to main**: GitHub schedules from the default branch.

## Proposed phasing

1. **Phase 1: House roll calls, bills, members.** `tools/us_rollcalls.py`
   into `us_members`, `us_bills`, `us_divisions`, `us_votes`, with the schema in
   `src/us_store.py` (the Canada pattern, kept out of `src/db.py`). Bills from
   BILLSTATUS bulk, matched on titles + CRS subjects + summary. Divisions keyed
   to bill IDs (`119/hr/28`), never titles. A `config/watchlist-us.yaml` with the
   misses above.
2. **Phase 1b: amendment purposes (built 9 October):** BILLSTATUS first,
   keyless; the Congress.gov key, when present, fills the lag.
3. **Phase 2: Senate votes and the week ahead (floor lists, committee
   meetings; both built 9 October)**, then the **Federal Register**.
4. **Phase 3: Congressional Record** debate packs and the US 5CA (votes +
   cosponsorships).
5. **Phase 4: state legislatures, in blocks.** See below.

## Dates that matter

- **3 November 2026: midterm elections.** Every House seat and a third of the
  Senate. The House has not voted since 16 September.
- **Lame duck, mid-November to December 2026.** FY2027 funding (the CR,
  H.R. 9770, is the vehicle) and the FY2027 NDAA (H.R. 8800) are the
  must-pass bills where riders on our ground will be fought.
- **3 January 2027: the 119th Congress ends and every pending bill dies.**
  All 19,596 bills and resolutions fall at once. This is a prorogation fall
  on a two-year cycle: a bill is dead when its Congress ends, whatever its
  last action says (built: see the rollover below).
  Bills are re-introduced in the 120th under new numbers, so the watchlist
  must be keyed per Congress, with the short title as the link between
  versions.

### The rollover (built 9 October 2026)

- **The current Congress is a date.** `us_store.congress_on(day)`: Congress
  n sits from 3 January of 1789 + 2(n - 1), so the 120th from 3 January
  2027; session 1 in the odd year, 2 in the even. 1 and 2 January 2027 are
  still the 119th. Nothing hard-codes 119 any more: `us_rollcalls.py`
  defaults to it, and `jobs/us-weekly.sh` reads
  `us_rollcalls.py --print-congress` ("119 2 -") for the Congress, the
  session and the Senate menu (`vote_menu_<congress>_<session>.xml`).
  `tools/us_schedule.py` derives the Congress the same way for the bill
  numbers it reads off the week-ahead pages.
- **The old Congress is finished off.** For the first 45 days of a new
  Congress `--print-congress` names the previous one ("120 1 119") and the
  job collects it first, every week: its bills' final statuses in
  BILLSTATUS (a bill presented before 3 January can be signed after it),
  any late roll calls, and their amendment purposes. A gap there does not
  stop the current Congress's run.
- **The edition shows the fall.** Once a Congress has ended, its bills not
  enacted are "Fell with the 119th Congress", never pending: they leave
  the live and committee lists, the header and the countdown move to the
  120th, and for 60 days a top line and a "Fell with the 119th Congress"
  section (most-backed 15) count them; the DM says so too. A simple
  resolution agreed to in its chamber is finished business, not a fall,
  and no longer counts as pending either (740 pending on 9 October became
  727 that can actually fall).

## State legislatures: all 50 (decided 9 October 2026, not built)

Christopher wants all 50. That rules out one scraper per state as a first
step: fifty sites, most part-time, each with its own format. The route is an
aggregator, probed 9 October 2026:

- **Open States / Plural Policy** covers all 50 (plus DC and Puerto Rico)
  in one schema: bills, actions, sponsors, votes, people.
  - People: `data.openstates.org/people/current/<state>.csv`, **open, no
    key** (Texas: 117 KB).
  - Bills and votes: API v3 (`v3.openstates.org`) **needs a free API key**
    (403 without one), tied to an account.
  - Bulk per-session downloads (`open.pluralpolicy.com/data/`) sit **behind
    a login**.
  - So Christopher (or the team) needs to create the account. Claude cannot.
- **LegiScan**: the API needs a key, and the site answered our probe with a
  Cloudflare bot challenge. Not built on, per the Canada rule on bot
  detection.

Open questions before building: the API key's rate limit (to be read from the
account page, not guessed) decides whether one weekly run can cover 50
states or has to rotate through them in blocks; and the vote coverage of
part-time legislatures needs measuring per state. The original idea of
blocks still applies to the build order, if not to the scope:



As in Canada, much of the ground is state-level: abortion law since Dobbs,
gender medicine for minors, school policy, assisted dying (legal in about a dozen
jurisdictions). Possible build orders:

- **By issue salience:** states with live fights on our ground first.
- **By session calendar:** most legislatures sit January to spring; Texas
  meets in odd years only. A block that sits in 2027 is worth doing first.

## Open questions for Christopher

1. ~~Who reads it?~~ Own edition, to Christopher alone for now (decided
   9 October): a Slack DM, and he owns the Asana task.
2. **The Congress.gov / api.data.gov key.** Free and immediate, but it should
   be requested in his name or the team's. Phase 1b no longer needs it (it
   only closes BILLSTATUS's lag); the Congressional Record and
   Regulations.gov still do.
3. ~~Taxonomy~~: shared list, merged into the areas (decided 9 October; v1.17).
4. **Scope:** DEI, antisemitism, contraception. In or out?
5. **Executive actions** as a section: yes or no?
6. ~~Senate~~: built 9 October; collected from CI, where senate.gov answers.
7. ~~Which state block first?~~ All 50 (decided 9 October), via Open
   States: **an account and API key are needed**.
