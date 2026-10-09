# Ireland: scoping the Oireachtas monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` with
the repo's honest User-Agent and a half-second throttle. Every number below
was measured, not estimated. The national Oireachtas only (Dáil and Seanad);
local government and the Assembly in Belfast are out of scope here.

## Decisions (Christopher, 9 October 2026)

These mirror the US decisions of the same day. The first four were assumed
in the first draft of this document and confirmed by Christopher on
9 October 2026.

- **Own edition.** Ireland gets its own edition, not a section of the UK one
  (`tools/ie_monitor.py`, below).
- **To Christopher alone at first**, until it is good: a Slack DM, nothing
  posted to a channel.
- **Shared English taxonomy, unchanged.** `docs/keyword-taxonomy.md` and
  `config/taxonomy.yaml` were not touched. Irish vocabulary is *proposed*
  below for Christopher to approve. Named bills whose titles miss sit in
  `config/watchlist-ie.yaml`, applied by bill key.
- **Scope: the national Oireachtas first** (Dáil, Seanad and their
  committees).
- **Contraception is a life issue** (area 1), as decided for the US (the
  shared taxonomy carries it). It
  matters here: the Health (Provision of Contraception Prescribing Service in
  Retail Pharmacy Businesses) Act 2026 lands in area 1 on that rule alone.

## Phase 1: built, 9 October 2026

`tools/ie_rollcalls.py` into `ie_members`, `ie_member_parties`, `ie_bills`,
`ie_sponsors`, `ie_bill_debates`, `ie_divisions` and `ie_votes` (schema in
`src/ie_store.py`, declared in `db.TABLES`). Live run into a scratch
database, not the store:

| | Read | On our ground |
|---|---|---|
| Bills with any event since 29 November 2024 | 419 | 31 |
| of which bills of the current Houses (see below) | 239 | 21 (13 without the watchlist) |
| Divisions: Dáil 429, Seanad 221, committee 61 | 711 | 40 |
| Votes (Yes 37,613, No 35,365, Abstain 151) | 73,129 | |
| Members: 176 Dáil, 60 Seanad, one in both | 235 | |
| Party spells | 239 | |
| Sponsorships | 1,268 | |

**11.5 seconds, 9 requests, no gaps.** Every one of the 73,129 votes found
the party its member held on the day. A dry run (`--dry-run`) reads one page
of each list and stores nothing.

- "Bills of the current Houses" are the 239 whose latest stage was taken in
  the 34th Dáil or 27th Seanad, which were enacted since, or which were
  restored to the order paper. The other 180 appear only because a lapse was
  recorded after the Dáil first met.
- **164 bills are alive** (19 Government, 145 Private Members'), by the rule
  in "Bills fall" below, not by the API's `status`.
- **Every division is re-read whole each week.** It is 9 requests, and it is
  what re-stamps `last_seen` for the coverage watch, so unlike the US
  divisions these move in recess too.

## Phase 1b: amendment votes given their own text (built 9 October 2026)

`tools/ie_rollcalls.py` now reads the debate transcript behind every
amendment division ("Amendment put:", "Amendment to amendment put:",
"Seanad amendment put:", "Recommendation put:"). Each transcript is the
day's Akoma Ntoso XML (keyless, the debate URI with `/debate/mul@/main.xml`);
each division in it is a `<voting eId="vote_N">` pointing at its "Amendment
put:" summary, and walking back from there to the nearest "I move amendment
No. 9: In page 21, line 9, ..." gives the amendment as moved. The walk stops
at an earlier disposal ("put and declared lost", "not moved", "agreed to"),
so a division never takes someone else's amendment. The text (from "I move",
at most 1,200 characters) is stored in `ie_divisions.amendment_text` with
`amendment_ref` ("amendment No. 9"), and joins the division's **own** text.
`own_areas` and `areas` keep the US meaning: own text alone, and own plus
the bill's. Measured on the first run:

| | Amendment divisions | Amendment found |
|---|---|---|
| On bills (all stages, both Houses, committee) | 248 | 201 |
| On motions | 106 | 24 |
| Other (no bill, no motion) | 16 | 5 |
| **All** (126 transcripts, 57 seconds, no gaps) | **370** | **230** |

By chamber: Dáil 77 of 195, Seanad 121 of 138, committee 32 of 37. Motion
amendments are mostly moved on the Tuesday and divided on the Wednesday, so
the transcript of the division's day does not hold them: those keep
`amendment_text = ''` (read, nothing found) rather than a guess.

**The effect.** Divisions on our ground on their own text went from **6 to
11**, and divisions on our ground in all from 40 to 45. The new five: an
opposition amendment to the Criminal Justice (International Cooperation on
Electronic Evidence) Bill invoking the EU Rule of Law Conditionality
Regulation (area 7, lost 65 to 79), two amendments to the Criminal Law,
Civil Law and Defence Bill on children's evidence (area 6), an amendment to
a Seanad amendment of the International Protection Bill on representatives
for children (area 6), and a Seanad motion amendment on domestic violence
(area 5). Triage should decide which of these are ours. **The Mental Health
Bill's amendment votes were read too: 27 of its 28, and not one matched
anything of its own.** They still carry the bill's area 6, but the edition
now folds them into one count line ("27 amendment divisions ... read and
matched nothing of their own") instead of listing 27 findings.

## The finding that shapes everything

**A division names no bill.** All 711 division records carry
`isBill: false` and no bill field at all. What a division does carry is the
debate section it was taken in (a debate URI and `dbsect_N`), and each bill
record lists the debate sections that carried it. Joined on that pair, an ID
join and never a title:

| | Divisions | Joined to a bill |
|---|---|---|
| Dáil | 429 | 174 |
| Seanad | 221 | 169 |
| Committee | 61 | 48 |
| **All** | **711** | **391, on 95 bills** |

399 divisions name a bill in their debate title; 391 of them join. The 8
others sit in sections the bill record does not list: a motion to restore a
bill to the order paper, three instructions to committee, a waiver of
pre-legislative scrutiny, two Report or Second Stage sections, and one
committee whose title uses a hyphen where the others use a colon. They keep
the bill's printed name in `debate_bill`, as text, and no `bill_key`. No
section in the store carries two bills, but 10 sections in the bill records
do; a division landing in one of them joins neither and records a gap.

**The English taxonomy finds little on its own.** The unchanged
`config/taxonomy.yaml`, run over the 239 bills of the current Houses:

| Text matched | Bills on our ground (not 11) |
|---|---|
| Short titles only | 8 |
| Short + long titles | 13 |
| Short + long titles + watchlist-ie (8 keys) | 21 |

There is no CRS-style summary in Ireland. The long title ("Bill entitled an
Act to...") is the only description, and bill text exists only as PDF.

On our ground by area (current Houses, with the watchlist): abortion 6,
parental rights 6, free speech 8, sex-based rights 2, trafficking and
exploitation 2, surrogacy and embryology 1. Migration (3) is collated, not
counted.

**A vote's own text finds almost nothing.** Matched on its own debate title
and subject line, the taxonomy found **6 of 711** divisions. Joined to the
bill, **40**. As in the US, the vote often says nothing: 367 of the 711 are
amendment votes whose subject is "Amendment put:" and no more.

### The votes on our ground

- **Restoring an abortion bill, 17 December 2025** (Dáil): the motion to
  restore the Health (Regulation of Termination of Pregnancy) (Amendment)
  Bill 2023 to the order paper was **lost 71 to 73**. Matched on its own
  title; it joins no bill (see above).
- **Reproductive Rights (Amendment) Bill 2026**, Second Stage, 13 May 2026:
  lost 30 to 85.
- **Health (Abolition of Three Day Wait Rule) (Amendment) Bill 2026**, 17
  June 2026: a division at Second Stage carried 86 to 70. The record prints
  only "Question put:", so whether it was the Bill or a Government amendment
  is in the transcript, not the data. The bill is still at Second Stage.
- **Online Safety (Recommender Algorithms) Bill 2026**, 4 March 2026: an
  amendment carried 80 to 63 and the API now marks the bill Defeated. Found
  only through the watchlist.
- **Child Trafficking and Child Sexual Exploitation Material (Amendment) Bill
  2022**, Seanad Report Stage, 5 November 2025: amendments to replace "child
  pornography" with "child sexual abuse material" lost 14 to 31, and the
  motion to receive the Bill for final consideration lost 13 to 28.
- **Mental Health Bill 2024**: 31 divisions (8 Dáil, 23 Seanad), 28 of them
  amendment votes, all in area 6 because the bill's long title mentions
  parental consent. This is the NDAA lesson again, see below.

## What it missed: Irish naming

A recall check against 30 named Irish bills on our ground, of any year:
**14 caught, 16 missed** on short and long titles. The misses are Irish
names for things the taxonomy knows:

- **Dying with Dignity Bill 2015 and 2020** (area 2). "Dying with dignity"
  is not a term. The Voluntary Assisted Dying Bill 2024 did match.
- **Criminal Justice (Hate Offences) Bill 2022** (area 7). This is the
  Incitement to Violence or Hatred and Hate Offences Bill: it was renamed
  when the incitement part was dropped, and **the API holds only the final
  title**. Its long title says "offences aggravated by hatred" and
  "protected characteristics". A search for "Incitement" finds nothing after
  1988.
- **Online Safety and Media Regulation Bill 2022** and the **Online Safety
  (Recommender Algorithms) Bill 2026** (area 7). "Online Safety Act" is a
  term; "online safety" on its own is not.
- **Artificial Intelligence Companion Services (Protection of Children) Bill
  2026** (areas 6, 7): its long title says "age-assurance", hyphenated, and
  the term is "age assurance".
- **Every referendum bill.** The Thirty-sixth Amendment (repeal of the
  Eighth, 2018), the Thirty-ninth (The Family, 2023) and the Fortieth (Care,
  2023) have the long title "an Act to amend the Constitution" and nothing
  else. The Thirty-seventh (blasphemy, 2018) says "blasphemous matter", which
  is not a term. Referendum bills need the watchlist, or bill text.
- **Health (Assisted Human Reproduction) Bill 2023** (area 10). "Assisted
  human reproduction" is the Irish statutory name for the area. The 2022
  Bill (now the AHR Act 2024) matched only because it says "surrogacy".
- **Sex for rent**: the Ban on Sex for Rent Bill 2022 and the Prohibition of
  Advertising or Importuning Sex for Rent Bill 2025 (area 12). The Criminal
  Law (Sexual Offences) Bill 2015, which criminalised the purchase of sex,
  matched area 7 on "pornography" but not area 12.
- **Human Tissue (Transplantation, Post-Mortem, Anatomical Examination and
  Public Display) Bill 2022** (area 13): the opt-out organ donation law.
- **Education (Admission to Schools) Bill 2016** (area 8): the baptism
  barrier. Whether school admission by religion is our ground is a scope
  question.

### Irish vocabulary (proposed 9 October 2026; adopted at v1.20, below)

| Term | Area | Tier | Why |
|---|---|---|---|
| dying with dignity | 2 | 1 | Two bills of that name |
| online safety | 7 | 2 | The Irish regulator's whole field; triage decides |
| age-assurance (or a hyphen rule in the matcher) | 7 | 1 | The term exists unhyphenated |
| aggravated by hatred, protected characteristic* | 7 | 2 | The hate offences family |
| blasphem* | 8 | 1 | The 2018 referendum |
| assisted human reproduction | 10 | 1 | The statutory name |
| sex for rent | 12 | 1 | Two bills, no other route |
| human tissue (with transplant*) | 13 | 2 | The opt-out donation law |
| parental choice | 6 | 2 | "Parental Choice in Education", a Dáil motion, missed |
| Coimisiún na Meán | 7 | 2 | The online safety regulator, named in Irish in English texts |

**Adopted at taxonomy v1.20** (Christopher, 9 October 2026: "Add the state
keyword and other candidates to the taxonomy"), each measured against v1.19
on the stored Irish bills and divisions and on every other stored corpus
(docs/keyword-taxonomy.md has the per-term counts). In Ireland 4 bills and 6
divisions gain an area, all of them newly on our ground: the Ban on Sex for
Rent Bill 2022; the Broadcasting (Amendment) Bill 2026 and the Broadcasting
(All Ireland Service) (Amendment) Bill 2025 (on "Coimisiún na Meán", tier 2,
so the judge weighs them), the Seanad's two Online Safety motion divisions,
and the Dáil's two Parental Choice in Education divisions.

- **As proposed:** "dying with dignity" (area 2, tier 1), "online safety"
  (7, tier 2), "age-assurance" (7, tier 1), "aggravated by hatred" (7, tier
  2; no row today), "assisted human reproduction" (10, tier 1), "sex for
  rent" (12, tier 1), "Coimisiún na Meán" (7, tier 2).
- **Narrowed:** "blasphem\*" joined area 8 at **tier 1** (blasphemy laws are
  religious-freedom ground: 28 Westminster ledger rows and 5 Holyrood items
  gain area 8, all of them Pakistan, Egypt, Asia Bibi and the like); "human
  tissue" is guarded by transplant, donation, donor, post-mortem or
  authorisation company (bare, it took two Florida HIV bills); "parental
  choice" is adopted only as "parental choice in education" (bare, it took
  Idaho's Parental Choice Tax Credit, early-learning rates and a nappy
  motion).
- **Rejected:** "protected characteristic\*" (Senedd standards and transport
  questions, California employment bills: the phrase is the Equality Act's
  everyday vocabulary, and area 5 already carries the singular at tier 2).
- Stored rows pick it up only when the Irish weekly runs with
  `IE_RECLASSIFY=true` (`tools/ie_rollcalls.py --reclassify`); the watchlist
  (`config/watchlist-ie.yaml`) is unchanged.

### What it caught that it should not have

- **The Minister for Justice, Home Affairs and Migration.** The department's
  name puts "migration" in every justice text: 916 of the 8,052 written and
  oral questions of September 2026 were addressed to him, and the taxonomy
  filed 929 of the month's questions under area 11. `tools/ie_rollcalls.py`
  strikes the office from the text before matching (`strip_offices`), which
  takes the month to 158. Migration said anywhere else still counts. One
  bill's long title names him.
- **"stillbirth\*"** put the Non-Binary and Intersex Recognition Bill 2026 in
  area 1 (it amends civil registration); the Civil Registration (Amendment)
  (Certificate of Life) Bill 2022 is a fair area 1 hit on the same term.
- **"reproductive healthcare"** put the Organisation of Working Time
  (Reproductive Health Related Leave) Bill 2021 in area 1; **"decriminalis\*"**
  a drugs bill; **"coercion"** the Coercion of a Minor (Misuse of Drugs
  Amendment) Bill 2022 in area 2.
- **"parental consent"** puts the Mental Health Bill 2024 and its 31
  divisions in area 6. It deals with children's consent to mental health
  treatment, so this one is triage's call, not a bug.

## Amendment votes (the US omnibus lesson)

Ireland has no omnibus riders, but it has the same blind spot: **245 of the
391 joined divisions are amendment votes**, and the record says only
"Amendment put:". The vote inherits its bill's areas whole, which is how 31
Mental Health Bill divisions all read as area 6. What was moved is in two
places, both free:

- **The debate transcript** (Akoma Ntoso XML, one file per sitting day,
  300 to 780 KB): "We move to amendment No. 1 in the names of Senators
  Flynn, Black, Higgins and Ruane", then the division with its `vote_N`. The
  debate section also names the bill by ID (`refersTo="#bill.2022.14..."`),
  a second ID route for the 8 divisions the bill records miss.
- **The amendment lists**: 211 numbered lists for the bills since November
  2024, **PDF only** (no XML anywhere in the bill data: 545 bill versions,
  0 with XML).

Phase 1b (above) now reads the transcript; the amendment lists stay unread,
since the motion as moved quotes the amendment's text in almost every case.

**Motions** are the other half of the Dáil's divisions: 207 divisions on
motions (mostly Private Members' business), none on our ground. The motion
title is all the division carries, and "Parental Choice in Education" and
"Online Safety" (a Seanad motion) both missed. The motion text is in the
transcript.

## Bills fall on dissolution, and the API still says "Current"

Every bill lapses when the Dáil is dissolved (Dáil bills on 8 November 2024);
bills before the Seanad lapsed when the 26th Seanad ended (29 January 2025).
A lapsed bill can be **restored** by motion in the new House, at the stage it
had reached, and keeps its number. The API records both as events.

The trap is `status`. On 9 October 2026, of the 266 bills the API marks
**Current**, **102 had lapsed and were never restored**: the Voluntary
Assisted Dying Bill 2024 is one, "Current" with its last stage in the 33rd
Dáil. So `ie_bills.alive` is derived:

> alive = status is Current AND (the latest stage was taken in the 34th Dáil
> or 27th Seanad, OR the latest restoration is after the latest lapse)

A restored bill's latest stage can be in an old House: the Provision of
Objective Sex Education Bill 2018 was restored in this Dáil and still shows
its 32nd Dáil Second Stage. Note also that `mostRecentStage` is the last
stage *completed*: a bill defeated at Second Stage shows "First Stage".

At the next general election every bill lapses at once, and
`config/watchlist-ie.yaml` has to be re-checked: a restored bill keeps its
key, a re-introduced one gets a new number.

## What Ireland publishes

### The Oireachtas Open Data API: works today, open, no key

`api.oireachtas.ie/v1`, documented in `api.oireachtas.ie/v1/swagger.json`.
robots.txt allows everything. Fast: a 200-record page in 0.3 to 1.5 s.

- `/members?chamber_id=<house>`: the roster with **dated party spells**,
  constituency or panel, offices and committee memberships. 176 for the 34th
  Dáil (174 seats: Catherine Connolly left on 25 October 2025 and Paschal
  Donohoe on 21 November 2025; two by-election winners from 25 May 2026), 60
  for the 27th Seanad. Two members changed party in this Oireachtas (Eoin
  Hayes, Martin Conway), and the change date sits on both spells, so the
  spell that *starts* that day is the one in force.
- `/legislation`: 6,048 bills since 1922. Titles in English and Irish, long
  titles, sponsors (Government bills by office, "Minister for Health", with
  no member), stages, events (Published, Lapsed, Restored, Enacted),
  debate sections, versions and amendment lists (PDF links), and the Act.
  `date_start` selects bills with any event since that date.
- `/votes` (and its undocumented alias `/divisions`): every division with
  **every member's vote** (Tá, Níl, Staon), the tellers and the outcome.
  **No party** on the vote; it comes from the member's spells. Vote IDs
  restart (220 distinct `vote_N` across 429 Dáil divisions), so the key is
  the URI path. `chamber_type=committee` gives committee divisions (61 since
  November 2024), where Committee Stage amendments are voted.
- `/questions`: written and oral PQs with answers (`show_answers`). 8,052 in
  September 2026 (7,933 written, 119 oral); 72 on our ground. Dáil only:
  the Seanad has none. Collected since phase 2.
- `/debates`: 178 Dáil and 157 Seanad debate records in this Oireachtas,
  1,060 committee records, each with an Akoma Ntoso XML transcript.
- `/constituencies` (43), `/parties` (11 in the Dáil), `/houses`.

**Gotchas, all measured:**

- **Counts saturate at 10,000** (`/votes` and `/questions` unfiltered both say
  exactly 10,000). Never page to the count; page to a short page.
- **`skip` above 10,000 is a 422**, and so is `limit` above 1,000. A year of
  PQs is more than 10,000, so PQs must be paged by month.
- **Status 200 with nothing in it:** an unknown House returns 200 and zero
  results; a non-numeric `limit` silently returns 10 records. The collector
  treats an empty roster or bill list as a gap.
- A 404 is a JSON body, `{"message": "Not found."}`.
- `/committees` does not exist. Committees are known only through member
  records (92 committee names in this Oireachtas) and their debate records.

### Bill text and amendments: PDF only

Bills, explanatory memoranda and amendment lists are PDFs on
`data.oireachtas.ie` (a bill about 470 KB). Of the 545 bill versions since
November 2024, 529 are English, 12 bilingual, **4 Irish only**. Body
matching needs a PDF step (as `src/ca_gazette_pdf.py` does for Canada).

### The Oireachtas website: a CAPTCHA

`oireachtas.ie/en/debates/questions/` answers with an AWS WAF "Human
Verification" CAPTCHA (status 405). Not used, per the rule on bot detection.
The API carries everything the edition needs except the week ahead, which
comes from `/en/detailed-schedule/`: that page answers, and robots.txt
allows it (phase 2).

### Irish-language text

All 419 bills carry English short and long titles (3,179 older bills, mostly
pre-1990, have no English long title). Of the 711 division titles, 73 carry
Irish, but nearly all are bilingual ("An tOrd Gnó - Order of Business"). Only
3 are Irish only: two divisions on the motion "Oideachas trí Mheán na
Gaeilge" (Irish-medium education, 5 March 2025) and one committee election.
Stage names are sometimes Irish inside an English title ("An Dara Céim").
The English taxonomy is blind to all of these; at today's volume a human
reads them.

### Iris Oifigiúil: reachable, but robots.txt says no

The state gazette publishes two PDF issues a week (about 1.9 MB each). Its
robots.txt is `Disallow: /` for every agent, so it is **not collected**.
Christopher's call whether to ask, or to read it by hand.

### gov.ie consultations: refused from the laptop

`gov.ie` (consultations, the RSS feed, `assets.gov.ie`) answers **403 from
CloudFront** to our UA, a browser UA and curl alike: an address block, like
`gov.wales` and `senate.gov`. **Not yet tested from GitHub's runners**; that
is the next step before deciding anything (a one-off probe workflow, as for
the US Senate).

### Irish Statute Book: works, HTML

`irishstatutebook.ie/eli/...`: every Act and SI, with "Bill History" and
commencement links. 476 SIs listed for 2026 so far. This is the enacted-law
and statutory-instrument side (the equivalent of legislation.gov.uk).

### Citizens' Assembly: works, WordPress with a feed

`citizensassembly.ie` (an RSS feed and `wp-json`). No assembly is sitting:
the latest, on drugs use, has reported. The 2016 to 2018 Assembly is the one
that recommended repealing the Eighth Amendment, so a new one is worth an
alert, not a weekly pull.

## The edition (built 9 October 2026)

`tools/ie_monitor.py` (`--edition`, `--dm`, `--print`, `--date`), modelled
on `tools/us_monitor.py`, writes `editions/ie-monitor-<date>.md` and DMs a
short summary to Christopher alone (U05LJP0BT61). Read-only on the store.

- **Sections:** top lines (or, in a quiet week, "no division on our ground
  this week" with the last Dáil and Seanad division dates); dates that matter
  (Budget 2027, the latest dissolution date with the count of live bills
  that would lapse, the sitting pattern); divisions this week, folded where
  the same question was put repeatedly, each with outcome, Tá-Níl(-Staon),
  the party split at the vote and what matched (own text, amendment, or
  bill only), and in a quiet month the latest divisions on our ground;
  bills that moved; new bills (by First Stage date); live bills (by the
  `alive` rule, never the API's `status`); enacted; defeated or withdrawn;
  lapsed and not restored; coverage.
- **No verdicts.** No line says who won. A Government amendment that carries
  on a Private Members' bill can end it, and only a human says which way a
  vote cut.
- **Inherited areas marked**, and amendments read and blank folded (above).
- **Renders with no scores**, and says so.
- **Speaks once a day**, as `jobs/us-weekly.sh` does: an edition already
  committed for today is rewritten, not resent. `jobs/ie-weekly.sh` runs it
  after the collector (even in a week with gaps), and both the workflow and
  the Mini (`# mini_run: commit editions`) commit `editions/`.
- **Questions, debate and the week ahead** since phase 2 (below).

The first render, from the scratch database of 9 October 2026: no division
on our ground this week (the Dáil last divided on 6 October, the Seanad on
16 July); the latest on our ground listed with party splits (the
Reproductive Rights Bill, lost 30 to 85 with 36 abstaining, Sinn Féin's 33
among them); 17 live bills on our ground, 2 enacted, 2 defeated, 10 lapsed
and not restored.

## The judge (wired 9 October 2026, on since 9 October)

`tools/ie_triage.py`, modelled on `tools/us_triage.py`: the same judge, model
and rubric (`src/triage.py`) with an **Irish frame** (the abortion Act of
2018 and the three-day wait, Dying with Dignity, AHR, gender recognition,
RSE and patronage, Coimisiún na Meán, hate offences, referendum bills,
timed amendments). It judges bills on our ground and divisions whose own
text or amendment matched; a division that only inherits takes its bill's
score. Scores are written once, ever; `--rescore` re-queues one.

**SPEND NEEDS A YES.** The weekly runs it only when the repository variable
`IE_JUDGE` is `on`, as `US_JUDGE` gates the US judge. **It is on** (Christopher,
9 October 2026). The first `--dry-run`, before phase 2: 42 items (31 bills,
11 divisions), 11 calls, about $0.10. With questions and speeches, see
phase 2 above.

## Phase 2: questions, debates and the week ahead (built 9 October 2026)

Three new steps in `jobs/ie-weekly.sh`, after the collector and before the
judge, each with its own `source_runs` heartbeat ('IE schedule', 'IE
questions', 'IE debates'). Schema in `src/ie_store.py`: `ie_questions`,
`ie_speeches`, `ie_windows` (one row per feed and week read, with what was
read and stored, by area: the measurement survives without the rows),
`ie_schedule` and `ie_schedule_days`. Measured by a live backfill into a
scratch store on 9 October 2026 (`--db /tmp/...`), never the real one.

### Parliamentary questions (`tools/ie_questions.py`)

`/questions?show_answers=true`, a week (Monday to Sunday) at a time, pages
of 1,000 to a short page. **Dáil only**: the Seanad has no PQs, and the
API's chamber filter is ignored on `/questions` (every record is the
Dáil's). Stored **on our ground only**, on the question's own words and
heading, the Minister's office struck first (`strip_offices`, which now
strikes "Department of Justice, Home Affairs and Migration" too). The answer
never lends an area. A row keeps one sentence of the answer
(`answer_takeaway`, at most 200 characters), its shape and who gave it; the
edition prints that line and the link, never the answer.

| Since the 34th Dáil met (98 weeks from 25 November 2024) | |
|---|---|
| Questions read | **130,612** (65 weeks with any; the rest recess or dissolution) |
| A sitting week | about **2,000** asked (most 4,313), **36** on our ground |
| On our ground, stored | **2,367** (2,333 written, 34 oral) |
| By area (a question can carry two) | parental rights 546, sex-based rights 516, free speech 387, abortion 333, surrogacy and embryology 226, gender medicine for children 151, assisted dying 147, others under 50; migration-only not stored |
| Answer shapes | **448 "referred for direct reply"** (the HSE will answer the Deputy), 71 no settled position, 48 data not held, 33 no policy, 18 passed on, 14 deferred; the rest substantive |
| Time | **9.6 minutes** for the whole backfill (about 6 s a week) |

The takeaway is the sentence carrying a decline when there is one (the
Northern Irish shapes in `src/ni_answers.py`, less devolution's "not our
remit", plus two Irish ones: referred to the HSE for direct reply, and a
deferred reply), else the first that says something ("I propose to take
Questions Nos. 554 and 581 together" and thanks are passed over). The
answering label is printed two ways: with the Minister's name in brackets,
or the bare office run straight into the text ("Minister for Health As this
is an operational matter..."); the bare office is struck only when it is
the office asked or its Minister of State. 35 of 2,350 answers kept no
label. Not archived raw: a week with answers is 3 to 6 MB, every byte
re-fetchable.

### Debate speeches (`tools/ie_debates.py`)

`/debates`, plenary (`chamber_type=house`) and committee apart, a week at a
time. Each record carries every section's full text inline with each
speaker's memberCode, so no XML is read. A **speech** is all one member said
in one debate section. Oral PQ sections (debateType `question`) are skipped:
`ie_questions` holds them. Leaders' Questions, Questions on Policy or
Legislation, Topical Issues and Commencement Matters are read. Committee
witnesses carry no memberCode and are not stored.

**The rule** (copied from the US Congressional Record, `tools/us_record.py`,
and made narrower; documented in the module): areas come from the member's
**own words**, passage by passage, tier 1 only, the office struck first.
Something is lent only when the member's own words matched nothing **and**
they spoke at least 150 words, in three cases: the section's bill is on
`config/watchlist-ie.yaml` ('watch', by key); the bill's **short title**
is on our ground ('bill'; never the long title, the Mental Health Bill's
"parental consent" lesson); or there is no bill and the section's own
title matched ('heading', a motion). The bill is the one whose record lists
the section (`ie_bill_debates`, the divisions' ID join), else the bill the
section names by URI. Never a title.

| Since the 34th Dáil met (98 weeks) | Plenary | Committee |
|---|---|---|
| Debate records read | 336 | 1,061 |
| Member speeches read | 19,239 | 3,537 |
| On our ground, stored | 603 | 98 (88 rows after upserts) |
| A sitting week (plenary) | about 406 speeches, 13 on our ground | |

691 rows stored: **653 on the member's own words, 37 lent by a watchlist
bill, 1 by a bill's title** (the heading lend found none). By area: free
speech 308, abortion 184, parental rights 87, marriage and family 79, sex-
based rights 78, surrogacy 42, migration 37 (with another area). The
sections with most: Pride statements (27 and 22), the Harassment (intimate
images) Bill Second Stage (27), the Reproductive Rights Bill (25), the
Online Safety (Recommender Algorithms) Bill (22), the Three Day Wait Bill
(18, and 13 at the Health committee). **16.7 minutes** for the whole
backfill, almost all of it CPU (the passage matcher), not the network.
Excerpts are at most 400 characters, cut around the term that matched.

### The week ahead (`tools/ie_schedule.py`)

**The API has no schedule**: `/debates` and `/questions` return nothing for a
future date, and the swagger lists no order paper. The keyless official
source is the Oireachtas's own **detailed schedule page**,
`www.oireachtas.ie/en/detailed-schedule/` (1.7 MB, one tab each for the
Dáil, the Seanad and committees, about two weeks back and as far ahead as
anything is posted). It answers our UA (unlike the debate and question
pages, which are behind the WAF CAPTCHA), and robots.txt forbids only
query strings and search, so it is read without one, once a run, and
archived. Lines are **keyed by the bill link** they carry
(`/en/bills/bill/2026/19/`); a bill named without a link (most Dáil lines
and committee agendas) keeps its printed name as text, no key.

Read on Friday 9 October 2026: the **Seanad** had its week posted (16
items on 13 to 15 October, the Media Regulation Bill's Committee Stage on
the 14th, a watchlist bill), **committees** 24 meetings (the SLAPP Bill's
Committee Stage at the Select Committee on Justice on the 13th, by its
link), and the **Dáil** nothing: "No business is currently scheduled. Dáil
Éireann resumes on Tuesday, 13 October 2026". The Dáil's week follows its
Business Committee report, later than a Friday-morning run. The edition
says which, and says "in recess" when the resumption date is past its
window. Also probed: the Dáil's order-paper app (`dailbusiness.oir.ie`) has
a keyless JSON API (`dailbusinessapi.oir.ie/api/v1/dailbusiness/items`)
with `isSittingDay`, `indicativeBusiness` and the Business Committee report
PDF, but it held no business for the coming week that morning, so there
was nothing to build a parser against. Worth a second look when a week is
posted.

### In the edition and the judge

`tools/ie_monitor.py` gains **Coming up** (after the dates), **Debate this
week** (grouped by section: chamber, date, the bill by key, the members and
parties, two excerpts, what matched) and **Questions this week** (asker and
party, the office, heading and link, the question clipped, the answer's one
line; 15 listed, the rest counted by area), a top line each, and DM lines
for debate, questions and the week ahead. `tools/ie_triage.py` now queues
questions and speeches on their own words (a lent speech takes its bill's
score, as an inheriting division does), newest first, 200 a run.

**Backlog by `--dry-run` on the backfilled scratch store: 3,072 unscored
items, about $7.31 if judged at once (768 calls); the weekly's 200 a run is
about $0.48 a run.** A sitting week adds about 50 (36 questions, 13
speeches), so the old backlog drains in roughly 20 weeks, newest first.

### Running it

Each step gets what the job has left, capped: **5 minutes each on GitHub**
(the backup; the workflow's timeout is now 45 minutes) and **15 (questions)
and 20 (debates) on the Mini**, always keeping 20 minutes for the judge and
5 for the edition and the store. At the measured rates the first Mini run
drains the whole questions backfill and most of the debates one. Coverage
watches `ie_windows` and `ie_schedule_days` weekly (both move every run,
recess included) and `ie_questions`, `ie_speeches` and `ie_schedule` with a
month plus a month's grace (the summer recess was 62 days, less the
fortnight the re-read keeps rows fresh).

## What an Irish edition would look like (the proposal it was built from)

Westminster's sections map well: bills, divisions (Dáil, Seanad and
committee, with party at the vote), PQs (written and oral, with answers),
debates (transcripts), committees (from the transcripts). No EDMs, no
e-petitions (the Joint Committee on Public Petitions exists; not probed).
Consultations depend on gov.ie answering CI. Statutory instruments from the
Statute Book. Restoration motions after an election are a section of their
own: they are where lapsed bills on our ground live or die.

**The 5CA translates.** Every vote carries the member's code, party comes
from dated spells, and Private Members' bills carry their sponsors. The
Dáil's 339 Wednesday divisions (of 429) are the weekly division time, which
makes a Wednesday-night brief the natural same-day product.

## The weekly schedule

`.github/workflows/ie-weekly.yml`, gated by `mini-check.yml` (job
`IE_WEEKLY`): **Friday 08:30 UTC** cron, the Mac Mini at **09:30 London**
(half an hour before the Mini's US weekly at 10:00 London; the runner's lock
queues one behind the other for up to 30 minutes)
(`ops/launchd/net.citizengo.parlmonitor.ie-weekly.plist`), both through
`jobs/ie-weekly.sh`. Friday 08:30 collides with no other cron in the repo
(checked against every workflow, and tested), and is clear of the US
weekly's 10:00 and 12:00. One slot only: GitHub keeps one pending run per
state group, so a retry slot could cancel the US run. Watched by the failure
alert and `tools/coverage.py` (members, bills and divisions all weekly).
**It runs only once merged to main**, and the launchd job needs installing
on the Mini (docs/mac-mini.md).

## The same-day vote brief (built 9 October 2026, branch `vote-briefs`)

Parity with the UK Division watch (Christopher: "start the same-day vote briefs"). `tools/ie_division_brief.py` (rules and rendering in `src/vote_brief.py`), `jobs/ie-division-watch.sh`, `.github/workflows/ie-division-watch.yml` (`IE_DIVISION_WATCH`), `ops/launchd/net.citizengo.parlmonitor.ie-division-watch.plist`. No store.

- **Read directly from the API**: `/votes` for the Dail, the Seanad and committees over the window (three days), archived; `/legislation` since the Dail's first day (one request, 419 bills, 3.7 MB; not archived, the weekly archives it), because the API's date filter is on a bill's events and a Second Stage resumed for a deferred division is not one (measured: the three-day-wait Bill of 17 June is absent from a 15-18 June window); `/members` for party spells; the day's transcript only for an amendment vote. Joined and classified exactly as `ie_rollcalls` does (debate section join, `classify_division`, party AT THE VOTE via `PartyBook`).
- **What it says.** House or committee, date, debate, the subject line, the API's outcome word, Tá/Níl/Staon, the party split, what matched (`amendment`, `own text` or `bill only`), the amendment as moved when the transcript has it (or that it is not published yet), the tellers, name lists, and the 5CA reading's STATUS in `config/ie_stance.yaml`.
- **Schedule, from measurement.** From the debate transcripts' recorded times: Wednesday's deferred divisions fall 19:00-19:40 (23 and 30 September), late sittings divide until 22:00-23:30 (Budget day 6 October, 8 July). The API has no per-division timestamp and the Dail did not sit on 9 October, so the API's own lag could not be timed; Thursday 8 October's record was up by 10:04 UTC the next morning at the latest. Slots: 22:50 London Tue-Thu and 07:50 London Wed-Fri. Each brief records its generation time, so the first weeks measure the lag; drop or move a slot then.
- Dry run of 9 October 2026 (window 22 September to 9 October): 29 divisions, none on our ground. On 15-18 June: 24 divisions, 2 on our ground, among them `dail/34/2026-06-17/vote_149` (the three-day-wait Bill, FF 12-30, FG 11-23), "reading awaiting sign-off".

## Proposed phasing

1. **Phase 1 (built): members, bills, divisions with every vote.** Plenary
   and committee divisions, joined to bills by debate section ID.
2. **Phase 1b (built): amendments.** The amendment behind each division from
   the transcript. The edition and the judge (on since 9 October) are built too.
3. **Phase 2 (built 9 October 2026): PQs, debates and the week ahead.** PQs
   and speeches paged by week, offices struck before matching; the
   Oireachtas detailed schedule for Coming up.
4. **Phase 3: consultations and statutory instruments**, once gov.ie is
   tested from CI.
5. **Phase 4: the Irish 5CA** (votes, sponsorships, PQs).

## Dates that matter

- **Budget 2027**: the Financial Resolutions were voted on Tuesday 6 October
  2026 (measured). The Finance Bill and Social Welfare Bill follow through
  the autumn.
- **The autumn session**: the Dáil's first division was on 16 September
  2026; the Seanad has not divided since 16 July 2026. Last winter the Dáil's
  last division was on 17 December 2025 and its first on 13 January 2026; in
  summer, 15 July to 16 September 2026 with one recall on 28 August.
- **Wednesday nights**: the Dáil's weekly division time (339 of 429).
- **Bills live now on our ground**: the Health (Regulation of Termination of
  Pregnancy) (Amendment) Bill 2026 and the Three Day Wait Bill (both at
  Second Stage), the Gender Recognition (Amendment) (Prisons) Bill 2025, the
  Non-Binary and Intersex Recognition Bill 2026, the Protection of Children
  (Online Age Verification) Bill 2026 (Seanad Committee Stage), and the
  Child Trafficking and CSEM Bill 2022 (Seanad Report Stage).
- **The next general election.** The 34th Dáil first sat on 18 December 2024
  (its first division, measured). By statute a Dáil lasts at most five years
  from its first meeting, so it must be dissolved by December 2029 (law, not
  measured). Every bill lapses then; restoration motions follow.

## Open questions for Christopher

Settled: the assumed decisions (confirmed 9 October 2026); the judge
(`IE_JUDGE` on, 9 October 2026; its phase 2 backlog is above); the Irish
vocabulary (adopted at taxonomy v1.20, narrowed or rejected term by term).

1. **The watchlist** (`config/watchlist-ie.yaml`, 8 bills): especially the
   free-speech entries (SLAPP, Media Regulation, the intimate-image bills).
   Are they our ground? Since phase 2 it also lends to speeches (37 so far)
   and puts both bills in Coming up this week.
2. **Scope questions**: school admission by religion (the baptism barrier),
   guardianship bills, pregnancy loss leave, the Mental Health Bill's
   consent provisions.
3. **Iris Oifigiúil** forbids robots. Ask them, read it by hand, or leave it?
4. **gov.ie**: may a one-off probe workflow test it from GitHub's runners?
5. **Committee hearings**: committee divisions are kept (61, 48 on bills)
   and members' words in committee are read (98 speeches on our ground);
   witnesses' evidence (as in Canada's committees) is not. Collect it?
