# Canada: scoping the Parliament of Canada monitor

Probed live on 26 September 2026. Every number below was measured, not
estimated, and is reproducible from `tools/ca_rollcalls.py` and the notes
here. Groundwork only: nothing is scheduled, nothing reads the `ca_*` tables,
and the live run was made into a scratch database, not the store.

## The finding that shapes everything

**The English taxonomy works in Canada.** This is the opposite of the German
result. Federal Canada is bilingual, every division subject and bill title
has an English text, and `config/taxonomy.yaml` read it without change:

| Session | Divisions | On our ground | Bills | On our ground |
|---|---|---|---|---|
| 45-1 (May 2025 onwards) | 174 | 12 | 187 | 12 |
| 44-1 (Nov 2021 to Jan 2025) | 928 | 12 | 412 | 17 |

"On our ground" means an area other than 11: migration is classified and
stored but, as everywhere, collated and not campaigned. Counting migration,
the unpatched taxonomy matched 23 of 174 divisions in 45-1.

**What it missed was Canadian naming, not Canadian language.** Each miss
went into `config/watchlist-ca.yaml` with its reason:

- **C-34, the Digital Safety Act.** This is the government's online harms
  bill. The taxonomy knows the UK name, "Online Safety Act", and Canada says
  "Digital Safety". It is the largest single blind spot found.
- **C-9, the Combatting Hate Act**, was filed under area 7 only, on "hate
  crime". Its removal of the religious-text defence in s.319(3)(b) is area 8,
  and the title never mentions it.
- **C-311 (44th), violence against pregnant women.** This was the defining
  pro-life recorded vote of that Parliament, defeated at second reading on
  14 June 2023. Nothing in the taxonomy says "pregnant".
- **C-270 (44th)** says "pornographic" where the term list says
  "pornography". S-210 and C-216 (children online), and C-255 and C-290
  (attacks on places of worship), were missed too.

Consider a taxonomy change: stem "pornograph*" in the English list itself.
The same miss will happen at Westminster. That call belongs to Christopher
and his taxonomy versioning, so this build did not make it.

## What Canada publishes

### House of Commons: works today, open, no key

- **Divisions, one call per session.**
  `ourcommons.ca/members/en/votes/xml?parlSession=45-1` returns all 174
  divisions (139 KB), each with the House's own result, the Yea/Nay/Paired
  tallies, a document type and the bill number.
- **Every member's position, one call per division.**
  `ourcommons.ca/members/en/votes/45/1/174/xml` (about 250 KB) gives each
  participant with the **caucus they voted in**, so party-at-the-time comes
  free. This lesson cost us in Northern Ireland.
- **Members.** `ourcommons.ca/members/en/search/xml` lists 337 current
  members: Liberal 173, Conservative 137, Bloc 21, NDP 5, Green 1.
  `?parliament=44` returns the previous House.
- **Hansard, one XML per sitting.**
  `ourcommons.ca/Content/House/451/Debates/144/HAN144-E.XML` is 300 KB. It
  has 191 interventions, each speaker tagged with a stable `DbId`, plus
  `Timestamp` elements every five minutes (`Hr`/`Mn`). That is better than
  the Bundestag protocol and close to Westminster, so debate packs are
  buildable. **The `DbId` is not the member**: it identifies a member in a
  role, and none of sitting 144's 191 matched a PersonId (see phase 2).
- **Petitions.** The search form and its XML export carry a **reCAPTCHA
  token**. The form's endpoint (`Petition/SearchAsync`) answers without one,
  but we don't build on a form guarded by bot detection. The route used is
  the public **Details page per petition**, fetched by GET:
  `ourcommons.ca/petitions/en/Petition/Details?Petition=e-7000`. That page
  has the full prayer text, the House's keywords, the dates, the MP's
  PersonId and the government's response. Paper petitions matter here: MPs
  present pro-life and conscience petitions every sitting week, and the
  government must answer each one.

### LEGISinfo (parl.ca): works today, open, no key

- `parl.ca/legisinfo/en/bills/json?parlsession=45-1` returns all 187 bills
  in one call (947 KB). Each carries status, sponsor, government flag, the
  date of every stage and royal assent.
- `parl.ca/legisinfo/en/bill/45-1/c-34/json` is the detail record. **The
  short legislative summary was empty for every bill in the list**, so
  classification runs on titles.
- Bill text is **PDF**:
  `parl.ca/Content/Bills/451/Government/C-34/C-34_1/C-34_1.PDF` (804 KB). The
  obvious `.xml` sibling is a 404. Body matching, as `src/eudoc.py` does it,
  would mean `pypdf`, which the weekly already installs.

### Senate: works today, HTML only

`sencanada.ca/en/in-the-chamber/votes/45-1` is a table of 36 recorded votes,
and each vote has a details page
(`/en/in-the-chamber/votes/details/<id>/45-1`). There is no XML or JSON. The
Senate carried real fights on our ground this session, all of them on C-9:

- **3 June 2026:** the committee report adopting amendments was defeated
  32-41.
- **4 June 2026:** Senator Martin's third-reading amendment was defeated
  21-40, and the bill then passed 45-13.

The Senate recorded 36 votes where the House recorded 174, so most Senate
business passes on voice. A Senate section is worth building, but it is a
scraper.

### Third party: api.openparliament.ca, keyless JSON

Votes, bills, debates and speeches, current to 25 September 2026 (sitting
144). This is useful as a cross-check and as a fallback. **Do not build on
it**: it is one volunteer's service, its documentation page sits behind a
Cloudflare challenge, and the House's own feeds already cover everything it
serves.

### Not answering on the day

- **Canada Gazette RSS** (`gazette.gc.ca/rss/p1-eng.xml`, p2): 503 on three
  tries over an hour in the morning. It answered that afternoon, and the
  collector is now built (phase 2 below). A 503 is an outage to record, not
  an empty week.
- **Supreme Court RSS**: the guessed `decisions.scc-csc.ca` path returns 404.
  The case index page answers 200. The right feed has not been found yet.
- **Order Paper written questions** were not probed; the `NoticePaper` XML
  path tried was a 404.

### Provinces: reachable, not probed for data

Ontario (ola.org), Alberta (assembly.ab.ca), British Columbia (leg.bc.ca) and
Quebec (assnat.qc.ca) all answered 200 with HTML. None was probed for a data
feed. Two things matter before anyone says yes to provinces:

- **Much of our ground is provincial in Canada.** Education, and so parental
  rights and gender policy in schools, belongs to the provinces. So does
  health care delivery, including MAID provision and conscience rules for
  clinicians. Examples are Alberta's 2024 laws on gender medicine for minors,
  Saskatchewan's use of the notwithstanding clause for its pronoun policy,
  and New Brunswick's Policy 713. A federal-only monitor will miss these.
- **Quebec works in French.** The German lesson applies there in full: a
  French term layer, drafted with a native reader, before Quebec items are
  classified at all.

## Phase 1: built, 26 September 2026

- `tools/ca_rollcalls.py` collects House divisions, member positions and
  LEGISinfo bills into four tables, `ca_members`, `ca_divisions`, `ca_votes`
  and `ca_bills`.
- The schema is in `src/ca_store.py`, not `src/db.py`. That keeps a scoping
  build clear of work in progress on the shared schema. Fold it into
  `init_db` when the monitor is adopted.
- `config/watchlist-ca.yaml` holds the Canadian additions.
- `tests/test_ca_rollcalls.py` has 13 tests, and none of them uses the
  network.

Design choices, each with a test:

- **Every division is stored; positions are fetched only on our ground.**
  The list costs one call, and positions cost one call per division. Both
  sessions came to 24 position fetches in total.
- **`positions_fetched` decides the skip, not whether the row exists.** A
  division that gains an area after `--reclassify` is still owed its fetch.
  The German members kept a NULL for ever because the collector skipped any
  row it already had.
- **The House's result is stored, never derived from the tallies.**
- **A paired member is stored as Paired, not Yea.** The House's display name
  says "Yea" for a paired Yea, so the booleans decide.
- **An empty participant list is recorded as a gap**, and the fetch stays
  owed.

**Measured result of the live run into a scratch database:** 1,102
divisions, 24 with positions, 468 members, 7,890 positions and 599 bills,
with no gaps. The C-9 third-reading split (division 93) came out as
Liberal 164 Yea, Bloc 22 Yea, Conservative 131 Nay, NDP 5 Nay, Green 1 Nay,
with 10 paired. That matches the House's tally of 186-137 exactly.

I checked all 24 fetched divisions against their tallies. One does not
match. Division 609 of 44-1 (S-210, 13 December 2023) is tallied at 133 Nays
but has only 132 Nay rows. Nobody has explained the gap yet, and it is
recorded here so a 5CA doesn't read a missing member as an absence. Possible
causes are a member who left before the per-member record was built, or a
correction to the record.

## Phase 2: Hansard, petitions, Senate and Gazette, built 26 September 2026

Two collectors, `tools/ca_hansard.py` and `tools/ca_petitions.py`, write four
new tables in `src/ca_store.py`: `ca_sittings`, `ca_speeches`,
`ca_speaker_roles` and `ca_petitions`. `tests/test_ca_hansard_petitions.py`
has 19 tests. Both collectors were run live into a scratch database only.
Nothing is scheduled.

### Hansard

**Measured on sittings 138-144 (17 June to 25 September 2026):**

- 2,139 interventions read, 228 of them the chair's (counted, not stored).
- 35 speeches on our ground.
- Every one of the 35 attributed to a member. 294 speaker roles learned.

The speeches on our ground covered:

- the C-218 MAID debate (eight members, 23 September);
- MAID petitions presented in Routine Proceedings;
- S-209 age verification;
- a sex-selective abortion speech in the C-22 debate;
- places of worship in an Islamophobia statement.

How it works:

- **The collector resumes at the highest sitting read, plus one.** It stops
  at the first sitting the House hasn't published. That sitting 404s
  through a redirect to the House's error page, and it's recorded as the
  frontier, not a gap.
- **A failed sitting stops the walk**, so no sitting is ever skipped.
- **Every sitting read gets a `ca_sittings` row** with its totals, so "a
  quiet week" and "never read" stay different facts.

**The speaker's `DbId` is a role, not a person.** Kevin Lamoureux speaking
as a parliamentary secretary is DbId 332542, and his PersonId is 30552.
Attribution works like this:

- The **riding** in the label resolves the member ("Gabriel Hardy
  (Montmorency—Charlevoix, CPC)"). Ridings are unique.
- If there is no riding, a **unique name** is the fallback.
- Once resolved, the DbId is **remembered**, so a bare "Gabriel Hardy" or
  "Minister of Finance" resolves later.
- A speaker that resolves by none of these is stored with `person_id`
  NULL and counted. It is never guessed.

**Two structure traps, both fixed and tested:**

- **Petitions lost their subject.** Only the first petition in Routine
  Proceedings carries the title "Petitions"; the rest have only a qualifier
  ("Medical Assistance in Dying"). An untitled subject now inherits the last
  title, so they read "Petitions — Medical Assistance in Dying".
- **Resumed debates lost their bill.** A resumed debate prints only the
  short title ("Protecting Young Persons from Exposure to Pornography Act").
  The bill number now comes from `ca_bills`. The procedural text also writes
  "Bill C‑218" with a non-breaking hyphen, and the parser handles that.

**A recall trap in the shared taxonomy.** "Medical assistance in dying" is
Canada's statutory term, but `config/taxonomy.yaml` holds it at **tier 2**.
Per-passage matching admits only tier 1 or a watchlist hit, so a speech that
said the phrase and never "MAID" was dropped unless its debate title matched.
Adding the phrase to `config/watchlist-ca.yaml` took the seven sittings from
30 speeches to 35. The fix is Canada-only. Whether Westminster wants the same
is Christopher's call. "Pornography" is also tier 2, and the S-209 debates
got in on their title.

### Petitions

**Two number spaces, both walked:**

- **Presented petitions: `451-00001` upwards, with no holes.** These cover
  paper and electronic alike: an e-petition gets a 451- number when an MP
  presents it, and `451-01121` serves the e-7000 page. So the walk finds
  every petition the House has received, and stops after three empty pages
  in a row. On 26 September the highest was 451-01218.
- **Open e-petitions: e- numbers only, and sparse.** e-7810 was live while
  e-7800 to e-7815 around it were empty; they are drafts not yet published.
  An unpublished number answers **200 with an empty body**, so probing a
  window of 190 numbers around the frontier costs almost nothing. This is
  the early-warning layer.

**Refresh:** a petition on our ground is refetched while it is open or
awaiting the government's response.

**Response text:** kept for our petitions only.

**Measured result of the live run:**

- 324 pages fetched: 89 petitions, 235 empty numbers, no gaps.
- 15 petitions on our ground.
- Presented: four paper petitions backing Tamara Jansen's C-218 (MAID
  safeguards), with about 30 signatures each, and two more on MAID.
- Open: e-7738 (EI benefits after stillbirth, 469 signatures), e-7765
  (pregnancy loss), and child-protection and trafficking petitions.

**A bug found live and fixed.** The probe window first followed the highest
e- number **stored**. But the 451- walk stores presented e-petitions, which
are older. The window centred on e-7719 and skipped every open petition above
e-7760, e-7810 included. The measured seed is now a floor, and there's a
test for it.

**Tier 2 needs the judge.** Several matches were noise. Examples are
"misinformation" on a US-tariffs petition, "places of worship" on an IRGC
petition, and "disinformation" on a foreign-affairs petition. All were tier 2.
The Westminster early-warning gate is tier 1 or watchlist, with tier 2 only
past 10,000 signatures. That gate, or the judge, belongs in whatever edition
reads this table. The table itself stores everything, honestly labelled.

### Senate votes

`tools/ca_senate.py` reads two kinds of page on sencanada.ca:

- the session's vote table: 36 votes in 45-1, with date, title, tallies,
  related bill and result;
- one details page per vote, fetched for votes on our ground only.

Votes go into `ca_divisions` with `chamber='senate'`. Senators go into
`ca_senators`, with ids prefixed `senator-` so they can never collide with a
House PersonId.

**Measured on 45-1:**

- 36 votes listed and 4 on our ground: three on C-9 and C-16's third
  reading.
- 95 senators, and no gaps.
- The Martin amendment to C-9 came out Yea 21, Nay 40, Abstention 2, exactly
  the Senate's tally. By group, ISG voted 27 Nay against 2 Yea, and C voted
  8 Yea.

How it works:

- **Every seated senator is listed on a details page, not only those who
  voted.** Sitting 4 June 2025 had 104 rows for a 76-vote division, and the
  other 28 rows carry no mark. They are stored as `Did not vote`, because a
  5CA reads an absence.
- **The source is HTML only, so the tally is the check on the parse.**
  Positions that don't add up to the list page's Yea/Nay/Abstention counts
  are a gap, and the fetch stays owed. So is a list that parses to nothing
  (a redesign).
- **Senate titles use a bill's short title** ("Combatting Hate Act – C-9"),
  so the long title is joined in from `ca_bills`.

### The Canada Gazette

`tools/ca_gazette.py` starts from the Part I and Part II RSS feeds. These
list **issues**, not items: 436 and 232 of them, back to December 2019. For
each unread issue in the window (60 days by default) it reads the issue's
index, then reads each item according to where it lives:

- **A regulation, order or supplement has its own page.** That page is read
  whole and matched per passage, with its title as a passage. A Regulatory
  Impact Analysis Statement runs to 80,000 characters, and whole-document
  matching would tag it with every area it touches.
- **A notice is an anchor on a page it shares** (`commis-eng.html#cs9`).
  Each shared page is fetched once and cut at the item anchors. The notice's
  own text is stored and matched.
- **An extra edition's feed link is the document itself**, not an index.
  The first run read it as an index, found nothing, and correctly logged
  two gaps. It is now one item, read whole.

**Notices were title-only at first, and that was wrong.** The Canada Revenue
Agency's "Revocation of registration of charities" names nobody in its
title. The charities (on 8 August, a string of merging Catholic parishes)
appear only in the text. CRA revocations are exactly where the
charitable-status question above would first show in the record. The notice
text is now stored, so a revoked religious or pro-life charity is a query,
not a hope.

**Part I proposed regulations carry their comment deadline.** "Within 30
days after the date of publication" becomes `comment_until`, because the
comment deadline is the whole point of watching Part I. An issue with a
failed item is not marked read, so it is retried whole.

**Measured over the last 60 days:**

- 16 issues read, with 216 items: 167 notices, 41 regulations and 8
  documents or extras.
- No gaps.
- **Three items on our ground, and none of them a real campaign item:**
  - two Ebola travel orders that cite the International Health Regulations,
    which is tier 1 in area 7 by design;
  - an immigration regulation.

That is a quiet summer, not a broken filter; the titles checked by hand
turned up nothing missed. Expect the Gazette to matter in bursts: MAID
monitoring regulations before March 2027, and any regulation under C-34.

**Before the RSS: the yearly archive (built 28 September 2026).** The RSS
stops at December 2019. For a `--since` before 2020 the collector reads the
yearly archive pages (`rp-pr/p1/2014/index-eng.html`), which link each
issue's index. The pre-2020 index pages parse like the current ones. Four
details differ:

- **Coverage.** HTML starts in 2011 for Part I and 2012 for Part II. All
  of 2010 and Part II of 2011 are PDF only: 117 issues (57 Part I, 31 and 29
  Part II; the rest of those years' PDFs are quarterly consolidations, which
  are skipped). Since 29 September 2026 they are read from the PDF (below).
- **Encoding.** The old pages declare utf-8 but are Windows-1252. They are
  decoded leniently, so "Montréal" is not stored mangled.
- **Part II extras.** A Part II extra edition has no index; the year page
  links its regulations directly. They are grouped by folder into one issue.
- **When the archive is read.** Only for a start date before 2020. A weekly
  run never touches the archive.

Size: about 780 issues from 2011 to 2019. At the 3,000-second budget per
run, that takes two or three backfill runs.

**The PDF-only issues (built 29 September 2026).** `src/ca_gazette_pdf.py`
reads them. The steps:

- **English only.** Every page is bilingual in two columns, English left.
  pypdf's layout engine gives each text fragment its position, and only the
  fragments left of where the French column starts are kept. That position is
  read per page, from the commonest left edge in the middle of the page.
- **Where items begin and end.** In Part I, each notice or proposed
  regulation ends with its insertion code (`[23-1-o]`). In Part II, each
  instrument opens with "Registration SOR/2010-110 May 19, 2010".
- **Sections.** A Part I item's section comes from the table of contents,
  matched by page number.
- **Addresses.** Each item's URL is the PDF with a `#page=N` anchor.
  PDFs are not kept in the raw archive.
- **What's stored.** The text is the English column. `matched_on` is `pdf`.

Measured on 12 live issues (2010 and Part II 2011): 182 items, no gaps.
Titles are good. A few are cut at a line wrap. A letter-spaced heading
comes out spaced ("PILO TA GE AC T"). The odd corporate notice keeps a
French word. The layout function is a private pypdf interface, so the
workflow pins pypdf. If the interface moves, an issue becomes a gap
("PDF unreadable"), never an empty issue.

### What a full backfill costs

These are one-off, announced, and run from CI, paced. That is the rule
bought by the Bundestag block of 24 September.

- **Hansard for 45-1:** 144 sittings, about 40 MB.
- **Presented petitions for 45-1:** about 1,220 pages, about 140 MB.
- **The Gazette for 45-1:** about 70 issues, perhaps 350 item pages.
- **The Senate:** nothing. Its whole session is 36 rows and a handful of
  details pages.

The weekly load is about:

- 4 sittings;
- 30 to 60 petition pages, plus 190 near-empty probes;
- 2 Gazette issues;
- the Senate's vote list.

### Committee evidence (House and joint), built 2 October 2026

`tools/ca_committees.py`. Nothing schedules it yet.

**The source.** Three hops per committee and session, and no search
(robots.txt disallows `/Search/` on ourcommons.ca):

1. The meeting list,
   `ourcommons.ca/Committees/en/<ACR>/Meetings?parl=P&session=S`. Joint
   committees (AMAD, REGS, BILI) are on **parl.ca**; the ourcommons URL
   404s for them. One page holds the whole session: date, number, study
   titles, an In Camera lock, and an Evidence link.
2. The Evidence page (`DocumentViewer/.../meeting-<N>/evidence`). It is
   about 700 KB, and its only use is the link to the XML. It is not
   archived.
3. The XML (`/Content/Committee/<PS>/<ACR>/Evidence/EV<id>/...-E.XML`). It
   uses House Hansard's own schema, so `ca_hansard.parse_sitting` reads it
   unchanged. It is archived. Committee files have no debate title, so the
   meeting's **study titles** are the title passage.

**Who is who comes from the XML's `Affiliation Type`.** The codes were
observed, not documented, so the tests pin them:

- **28 is a witness.** A witness never gets a `person_id` and never goes
  into `ca_speeches`. What a witness says on our ground goes to
  **`ca_testimony`**, with their name, affiliation and organisation. The
  organisation is the last part of the first label, so "Dr. Ramona Coelho
  (Physician, As an Individual)" gives "As an Individual".
- **35 and 36 are the chair, 26 a committee researcher and 27 the clerk.**
  These, and any label starting "The ", are counted and not stored.
- **Everyone else is a member.** An MP resolves by riding, then by a
  unique name, against `ca_members`. A senator on a joint committee
  resolves by a unique name against `ca_senators`. If neither resolves
  uniquely, the speaker stays NULL; nobody is guessed.
  - A first name may be a short form only when the document itself calls
    the speaker a senator: "Stan" and "Stanley" Kutcher are the same man.
  - Committee DbIds are not Hansard DbIds, and one person can have two in
    the same file (Mégie). So identity is learned per document, and
    `ca_speaker_roles` is never touched.

**What is stored.** Only interventions on our ground (per passage, as in
Hansard):

- A member's goes to `ca_speeches` with `forum='committee'`,
  `committee=<ACR>`, `chamber` set to `commons` or `senate`, and a
  speech_id of `cmte-<PS>-<ACR>-<NN>-<intervention id>`, which can never
  collide with a Hansard id.
- Every meeting read gets a **`ca_committee_meetings`** row with its totals.
  Its status is one of:
  - `read`;
  - `in_camera` (no Evidence link, which is not a gap);
  - `no_evidence` (public, but no transcript linked yet; checked again on
    every run).

  A meeting that is `read` or `in_camera` is never fetched again.

**Committees.** By default it reads every public meeting of the key eight:
JUST, HESA, FEWO, ETHI, AMAD, SECU, HUMA and CHPC. `--all-committees` adds
every other committee on the House's committee page, plus SDIR. For those,
it fetches a meeting only if its study title matches the taxonomy.

**Gaps.** These are recorded with `db.record_gaps` and the meeting gets no
row, so it is retried:

- a meeting list that won't load;
- an Evidence page with no XML link;
- an XML that won't parse, or that belongs to another meeting.

If five meetings in a row fail, the run stops. `--limit` counts meetings
attempted.

**Measured (smoke run, 2 October 2026, AMAD 44-1 meetings 1-5, scratch
store):**

- 42 meetings listed, 12 in camera.
- 1,123 interventions:
  - 415 by the chair and officers, counted;
  - 312 by witnesses, all on our ground and all in `ca_testimony`;
  - 396 by members and senators. 328 of them were on our ground, and all
    328 were attributed. The other 68 were the election of the joint
    chairs at meeting 1.
- Senators resolved once `ca_senators` was filled from two Senate vote
  pages. With it empty, 70 of the senators' interventions stayed NULL, as
  they should.

**Two limits.**

- **The title gate is strict.** SDIR's 44-1 study titles ("Current Human
  Rights Situation in Nigeria", "Situation of the Hazaras in Afghanistan")
  match no taxonomy term, so none of its 63 meetings passed. Make SDIR a
  key committee, or widen the taxonomy, if religious persecution hearings
  should come in.
- **The committee page lists only the current committees.** A special
  committee from an older Parliament has to be named with `--committee`.

**Not built:** committee reports (`ca_committee_reports`, matched on the
PDF body) and Senate committees.

## Phase 3: the Canadian 5CA, built 26 September 2026

`tools/ca_5ca.py` writes one sheet per area and chamber to
`data/5ca/ca-5ca-<chamber>-<area>.csv`. The filenames are stable, so reruns
overwrite rather than pile up in git. It reads the store only. The meanings
come from `config/ca_stance.yaml`, the Canadian mirror of
`config/ni_stance.yaml`.

### The rule, and why nothing is placed yet

A person writes what a Yea on a division meant, and the tool applies it.
**Every one of the 30 entries was drafted by Claude**, so:

- 22 readings carry `draft: true`. Seven of these were `read_first` until
  their texts were pulled the same day (see "The seven texts" below).
- 8 are `placeable: false`: unanimous votes, procedural ones, and C-9's
  concurrence in the Senate's noose.

A draft places nobody, so every sheet today lists evidence and leaves every
column blank. That is the design. Confirming a reading means deleting its
`draft: true` line. A `read_first` entry needs its text read and its yea/nay
values written; deleting its draft flag alone confirms nothing, and the tool
treats it as unread.

**What can place a member once confirmed:**

- a recorded **vote** (weight 5);
- **sponsoring a private member's bill** (weight 3). Sponsors come from
  LEGISinfo's detail record: the bill *list* leaves every sponsor field
  blank, which I measured for all 187 bills of 45-1.

**What never places anyone:**

- **speeches**: activity, not direction;
- **petitions**: the House says presenting one doesn't imply endorsement;
- **paired votes and Senate abstentions**: no direction is recorded.

### What the C-9 readings rest on, checked against the bill texts

- **The repeal of s.319(3)(b) was added at committee.** That is the defence
  for good-faith opinions on religious subjects or texts. It is absent at
  first reading, present in "as amended by committee", and in the Royal
  Assent text.
- **The committee also struck "religion"** from the legitimate-purpose
  defence for displaying a hate symbol.
- **The Senate's only substantive change that became law was adding "a
  noose"** to the banned symbols. So every Senate attempt on the religious
  defence failed.
- **A for-greater-certainty clause remains**, protecting "educational,
  religious, political or scientific" statements made without wilfully
  promoting hatred.

**A Nay on C-9's third reading is drafted at +1, not +2.** It opposes the
whole bill, not the clause. The clause-specific votes, below, carry the
full-strength readings.

### The seven texts, pulled 26 September 2026

- **House texts** come from each division's own page
  (`ourcommons.ca/members/en/votes/<parl>/<sess>/<n>`). The page gives the
  motion text, the mover and the sitting number.
- **Senate texts** come from the Journals of the Senate, linked from the
  vote table.
- **The committee report's recommendations** come from its PDF.
- Each entry now carries `text:`, `moved_by:` and `source:`.

| Vote | What it actually was | Proposed (still draft) |
|---|---|---|
| House 640, 14 Feb 2024 | Bloc (Gaudreau) reasoned amendment: decline C-62 because it does not also allow advance requests | Yea −2; a Nay places nobody (the whole House outside the Bloc) |
| House 874, 31 Oct 2024 | Bloc (Thériault): concur in the joint committee report of Feb 2023, which recommends MAID for mature minors (rec. 16) and advance requests (rec. 21) | Yea −2, Nay +1 (the report also recommends palliative care) |
| House 92, 25 Mar 2026 | Conservative (Brock): send C-9 back to committee with the sole purpose of **restoring s.319(3)(b) and (3.1)(b)** | Yea +2, Nay −2: *the* clause-specific C-9 vote |
| House 167, 17 Jun 2026 | Conservative (Lawton): discharge the order and withdraw C-9 | Yea +1, Nay −1 |
| House 168, 17 Jun 2026 | Government: concur in the Senate's one amendment, which added "a noose" | Never places: not our ground |
| Senate 700344, 4 Jun 2026 | Martin/Batters: rewrite C-9's safe-harbour clause 11.1(1). It adds "in good faith" and deletes "if they do not wilfully promote hatred against an identifiable group", so good-faith religious and public-interest statements are protected outright | Yea +2, Nay −1 |
| Senate 699935, 3 Jun 2026 | Human Rights committee report. It creates a **new offence** of promoting hatred against Indigenous Peoples by "condoning, denying or downplaying" the residential school system; it also adds the noose and widens an exception at places of worship | Yea −1, Nay +1: the most sensitive reading in the file |

Three things the texts overturned:

- **The Martin amendment does not restore s.319(3)(b).** An earlier draft
  assumed it did. It rewrites the bill's own clarification clause into
  something close to the repealed defence, which is why the Nay is −1: a
  senator can object to the drafting without opposing religious expression.
- **The Senate made one amendment, not several.** Senator Bernard's noose
  motion, adopted on 4 June after the committee report carrying the same
  line was defeated the day before.
- **The committee report was not ours.** Its substance was a new
  "denialism" speech offence, and the Conservatives voted against it. Who
  voted how would have suggested the opposite reading.

**A crash, found here and fixed.** C-62's reasoned amendment scores only
the Yea side. A *confirmed* entry with one side blank raised a KeyError, and
it would have done so the moment Christopher confirmed it. The tool now
renders that side as "carries no value", and a test covers it.

**Preview with every reading confirmed as drafted:**

| Sheet | ++ | + | 0 | - | -- | Check |
|---|---|---|---|---|---|---|
| Commons, freedom of religion | 121 | 19 | 4 | 5 | 188 | ++ 121 against 123 on House 92 (two of the 123 have left, including the mover) |
| Commons, free speech | 122 | 19 | 3 | 5 | 188 | 13 capped for missing House 92 |
| Commons, assisted dying | 94 | 3 | 124 | 0 | 116 | ++ 94 against 150 on C-314 |
| Senate, freedom of religion | 21 | 11 | 17 | 9 | 37 | ++ 21 against 21 who backed Martin |

### Three rules carried over from Westminster, each with a test

- **The absence cap.** A member at ++ is capped at + if they missed the
  area's latest *decisive* signed division, having voted elsewhere in that
  session. "Decisive" means our side scores +2. The first version counted
  C-62, whose Nay scores −2 but whose Yea is only +1. It capped 14 C-314 Yea
  voters, Chris Warkentin among them, for missing a delay vote.
- **The lobby check.** Sitting ++ against the size of our lobby on that
  division. It applies only when our side scores +2. The first preview
  raised a false alarm on C-9's third reading, where our side scores +1 and
  ++ rests on older votes.
- **Everyone who voted is listed; the totals count sitting members only.**
  - Former members are labelled, and not counted.
  - `ca_members.sitting` comes from the House's *current* roster. The
    parliament roster (`?parliament=45`) returned 349 for a 343-seat House,
    because it keeps members who have left.
  - Cathay Wagantall, C-311's sponsor, spoke on 17 June 2026 and is not on
    today's roster. Her seat, Yorkton—Melville, has no member at all.

### Preview: what confirming every draft as written would produce

Scratch data, not the store; `--stance` points at a copy with the drafts
removed.

| Sheet (Commons) | ++ | + | 0 | - | -- | Check |
|---|---|---|---|---|---|---|
| Abortion (C-311 only) | 88 | 0 | 134 | 0 | 115 | ++ 88 against a lobby of 113 |
| Assisted dying | 104 | 8 | 125 | 0 | 100 | ++ 104 against a lobby of 150 on C-314 |
| Parental rights / education | 124 | 0 | 134 | 79 | 0 | ++ 124 against a lobby of 189 on S-210 |
| Freedom of religion (C-9 only) | 0 | 143 | 10 | 0 | 184 | C-9 scores our side +1 |

The Senate sheets on free speech and religion come out 0 / 13 / 37 / 0 / 45:
the 13 who voted against C-9 at third reading, and the 45 who voted for it.

### Also fixed on the way: the Canadian tables were never declared

Since phase 1, `tests/test_db.py` had been failing its check that every table
written is declared. The Canadian tables lived in `src/ca_store.py`, outside
the shared schema, and so outside `db.TABLES`. That check runs inside the
**Deploy tracker** workflow. It had not been dispatched since, so nothing was
blocked, but the next deploy would have been.

- `db.init_db` now calls `ca_store.ensure_schema`, and the eleven tables are
  in `db.TABLES`.
- `tools/coverage.py` exempts the five Canadian tables that have a sighting
  column, with the reason that nothing schedules them. They must move into
  FEEDS the day a Canadian weekly runs.
- The full suite passes: 2,273 tests.

### What Christopher decides

1. **Confirm or correct the 16 drafts.** The C-9 lines, and the −1 on an
   S-210 Nay (privacy, not hostility), are the ones most worth a second
   look.
2. **Check the seven readings made from texts pulled on 26 September**,
   especially the Senate committee report. Is CitizenGO's line against a
   residential-school "denialism" offence settled?
3. **Decide whether C-16 (the Protecting Victims Act) is ours at all.** Its
   eight divisions are evidence only until then.
4. **Say whether the sheets go anywhere.** They are written locally and
   posted nowhere, like every other 5CA.

## The weekly schedule, 26 September 2026

`.github/workflows/ca-weekly.yml` ("Canada weekly") runs Tuesday at 10:00
UTC, with a retry at 12:00. The retry is gated off if the first run
succeeded.

**Why Tuesday.** Fifteen workflows share the `parl-monitor-state`
concurrency group, and GitHub keeps only one run waiting per group, so a
second arrival cancels the one queued. Tuesday between the 07:00 day sweep
and the 18:00 division watch is the widest clear window, even with the 3–5
hours of cron drift this repo has measured. It also comes after the whole
sitting week and after both Gazette parts.

**What it runs, in order:**

1. `ca_rollcalls` (divisions, positions on our ground, bills, sponsors);
2. `ca_senate`;
3. `ca_hansard`;
4. `ca_petitions --limit 300`;
5. `ca_gazette`.

Each collector runs whatever the one before did. A gap still fails the job,
so the alert fires, but a Gazette 503 does not cost the week's Hansard.

**No Slack, no posting.** It collects into the store and publishes the
store. Since 27 September 2026 it makes ONE kind of API call: the petitions
judge (`tools/ca_triage.py`), a 0-3 score and a why-line for each petition
on our ground, newest first, on a 20-minute clock, recorded in `api_spend`
as `ca-triage`. Migration-only petitions are not judged.

**The empty-store problem, and the seeds.** On a store that has read nothing,
Hansard and the presented-petitions walk would start at sitting 1 and
451-00001. A capped weekly would then spend months in 2025 and never reach
the present. So an empty store starts at a measured seed: sitting 138
(`SEED_SITTING`) and petition 451-01190 (`PRESENTED_SEED`).

**Everything before the seeds is the backfill.** It runs only when the
workflow is dispatched by hand with `backfill: true`, and it is announced
first, under the Bundestag rule. It covers:

- 45-1 sittings 1–137, about 40 MB;
- presented petitions 451-00001 to 01189, about 140 MB;
- the 44th Parliament's divisions and bills;
- the Gazette since 26 May 2025.

**The backfill reads what is missing, not a range.** Both `--backfill` modes
work from what is missing below the highest item held. A run cut short by its
budget therefore resumes at the hole when dispatched again. Walking forward
from 1 would, the second time, start at the frontier and never see the gap.

**Watching:**

- `tools/coverage.py` carries a "Canada weekly" heartbeat.
- **Cadence-checked:** divisions, bills and members, which are re-stamped
  every run even in recess, and petitions, with a week's extra grace.
- **Clobber check:** divisions, bills and members only.
- **Write-once:** senators, sittings and Gazette issues.
- "Canada weekly" is on the failure alert.
- The dormant exemption added in phase 3 is gone.

**First run.** The first run creates nothing new in the store's schema;
`init_db` has created the eleven Canadian tables since phase 3. It fills
them from the seeds forward.

## Proposed phasing

1. **Phase 1 (done, scheduled): House divisions, positions, bills.**
2. **Phase 2 (done, scheduled): Hansard, petitions, Senate votes, the
   Canada Gazette.** Collected weekly; no edition reads them yet.
3. **Phase 3 (built, awaiting sign-off): the Canadian 5CA.** See below.
   Every reading is a draft, so every sheet is an evidence list until
   Christopher confirms readings in `config/ca_stance.yaml`.
4. **Phase 4, if wanted: provinces.** Alberta, Saskatchewan and Ontario come
   first on our ground. Quebec comes only with a French term layer.

## Dates that matter

- **17 March 2027: MAID for mental illness as the sole underlying condition
  comes into force**, under the delay C-62 enacted in 2024, unless Parliament
  acts again. This is the dominant federal date on our ground for the next
  six months. C-218, C-260 and S-231 are all live MAID bills now.
- **C-34 (Digital Safety Act)** has been at second reading since June 2026.
- **The charitable-status question.** It has been *reported*, and not
  verified here, that the Finance Committee's pre-budget report of December
  2025 recommended ending "advancement of religion" as a charitable purpose
  and denying charitable status to pro-life organisations. The watchlist
  carries the phrase so that any division or bill using it is caught. Verify
  against the committee report before anyone campaigns on it.

## Open questions for Christopher

1. **Who reads it?** Is there a CitizenGO Canada team or campaigner, and do
   they want an edition of their own (the EU and German pattern) or a DM?
2. **Federal only, or provinces too?** If provinces, which ones, and is
   Quebec in, given it needs a French term layer?
3. **The watchlist is a groundwork draft.** Someone who campaigns in Canada
   should confirm the areas, especially C-9 as area 8 and whether S-228
   (sterilization procedures) belongs to us. S-228 was left out.
4. **Stem "pornograph*" in the shared taxonomy?** The miss is not Canadian.
5. **The Senate and petitions are scrapers**, not feeds. Are they worth the
   upkeep for a section, or should they wait until the House coverage has
   earned it?
