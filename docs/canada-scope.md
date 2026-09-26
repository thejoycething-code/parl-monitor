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
  tries over an hour, and the site's index page gave 503 too. Part I (draft
  regulations) and Part II (made regulations) are the SI equivalent. Retry
  before concluding anything.
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

## Phase 2: Hansard and petitions, built 26 September 2026

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

### What a full backfill costs

These are one-off, announced, and run from CI, paced. That is the rule
bought by the Bundestag block of 24 September.

- **Hansard for 45-1:** 144 sittings, about 40 MB.
- **Presented petitions for 45-1:** about 1,220 pages, about 140 MB.

The weekly load is about 4 sittings, 30 to 60 petition pages and 190
near-empty probes.

## Proposed phasing

1. **Phase 1 (done): House divisions, positions, bills.** Schedule it weekly
   once there is an edition to put it in. It is 2 list calls plus a handful
   of detail calls a week.
2. **Phase 2 (done for Hansard and petitions, see below).** Still to build:
   the Senate vote table and details pages, and the Gazette's Parts I and II
   once the host answers.
3. **Phase 3: the Canadian 5CA.** A division's meaning is signed by hand here
   as everywhere. Candidates already in the store include C-311 (2023),
   C-314 (2023), C-62 (2024), both S-210/C-270 age-verification votes, and C-9
   in both Houses. Two of these have no Westminster analogue: a whipped
   government MAID bill (C-62), and a Senate that amends and is overruled
   (C-9, June 2026).
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
