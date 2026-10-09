# United States: scoping the Congress monitor

Probed live on 9 October 2026, from the laptop. Every number below was
measured, not estimated. Groundwork only: nothing is built, scheduled or
stored, and the probe data sits outside the repo. Congress only; the state
legislatures are a later decision, taken in blocks (see the end).

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
Amendment No. 1") but not its purpose. The purpose text lives in two places:

- the Congress.gov API `amendment` endpoint (needs a key, see below);
- the House Rules Committee's amendment lists (rules.house.gov), which give
  each made-in-order amendment's one-line summary before the floor vote.
  Not probed yet.

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

### Senate roll calls: blocked from the laptop

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

### Floor schedule: works today, open, no key

`docs.house.gov/billsthisweek/<yyyymmdd>/<yyyymmdd>.xml` is the Majority
Leader's list for the week, with bill text links. The latest is the week of
14 September 2026. Nothing has been posted since, because the House is out
campaigning ahead of the midterms. This is the What's On equivalent.

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

## Proposed phasing

1. **Phase 1: House roll calls, bills, members.** `tools/us_rollcalls.py`
   into `us_members`, `us_bills`, `us_divisions`, `us_votes`, with the schema in
   `src/us_store.py` (the Canada pattern, kept out of `src/db.py`). Bills from
   BILLSTATUS bulk, matched on titles + CRS subjects + summary. Divisions keyed
   to bill IDs (`119/hr/28`), never titles. A `config/watchlist-us.yaml` with the
   misses above.
2. **Phase 1b: amendment purposes.** Needs the Congress.gov key. Without it
   the NDAA and appropriations votes are unreadable.
3. **Phase 2: Senate votes** (once reachable from CI), **floor schedule**,
   **Federal Register**.
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
  on a two-year cycle and `board.py`'s fall logic needs a US rule for it: a
  bill is dead when its Congress ends, whatever its last action says.
  Bills are re-introduced in the 120th under new numbers, so the watchlist
  must be keyed per Congress, with the short title as the link between
  versions.

## State legislatures: the blocks question (not scoped yet)

As in Canada, much of the ground is state-level: abortion law since Dobbs,
gender medicine for minors, school policy, assisted dying (legal in about a dozen
jurisdictions). There are 50 legislatures, most part-time, with very different
sites. Possible ways to block them, for Christopher to choose:

- **By issue salience:** states with live fights on our ground first.
- **By session calendar:** most legislatures sit January to spring; Texas
  meets in odd years only. A block that sits in 2027 is worth doing first.
- **By data source:** a third-party aggregator (Open States / Plural Policy,
  LegiScan) covers all 50 in one schema, which would collapse 50 scrapers
  into one collector. Not probed. Terms of use and keys to check.

## Open questions for Christopher

1. **Who reads it?** Is there a CitizenGO US team or campaigner, and do they
   want an edition of their own or a section?
2. **The Congress.gov / api.data.gov key.** Free and immediate, but it should
   be requested in his name or the team's. Phase 1b needs it.
3. **Taxonomy:** Equality Act (US), Comstock, mifepristone, gender
   transition / experimentation, life at conception, personhood, Section 230,
   COPPA, Title IX. US watchlist, or the shared term list?
4. **Scope:** DEI, antisemitism, contraception. In or out?
5. **Executive actions** as a section: yes or no?
6. **Senate:** re-test from CI. If it is blocked there too, the fallback is
   GovTrack or ProPublica-style third parties, which the Canada rule says not to
   build on.
7. **Which state block first?**
