# Division candidates for review

*Divisions the title sweep could not see, flagged by the taxonomy on the title or by tagged speeches in the same debate. READ THE "(title)" TAG WITH CARE: on a Bill-name title ("Crime and Policing Bill: motion to disagree with Lords Amendment 359") it means the Bill is on the watchlist for that area, not that the vote was about it -- batch 1 found every Crime and Policing ping-pong vote so tagged was about fly-tipping, youth diversion orders, the IRGC or fixed penalty notices. Nothing here is in the ledger or the tracker. To add one: put it in config/vote_tracker.yaml with a meaning line you have written. Its voters are ledgered by `tools/ledger_tracker_divisions.py`, which the Monday publish runs before the tracker builds (an earlier version of this note said the Score stance run did it; nothing did, and on 10 Sept 2026 thirteen of twenty-three signed-off divisions turned out to have no voters in the ledger -- correctly rendered on the tracker page, which reads the raw payloads, but contributing nothing to any 5CA placement). Generated 8 Sept 2026 by tools/find_division_candidates.py; queues in data/division-candidates.json (2020-26) and data/division-candidates-2017-2019.json.*

## Health Bill report stage, 8 September 2026 — meaning lines drafted, awaiting sign-off

*Found on 10 Sept from Joy Morrissey's reference to "last night's vote on puberty blockers"
at Women and Equalities questions. NONE of the four divisions that day is in `cv_divisions`
or the ledger: every title reads "Health Bill: Report Stage: New Clause 142", which carries
no taxonomy term, so the title sweep cannot see them. The clause text comes from the Bills
API (bill 4124, stage 21130); `our side` is verified against the sponsor's OWN vote in each
division, because a division's direction can never be read off its title.*

**Two of these would need a tracker issue that does not exist yet** — there is no issue for
gender medicine (area 3) or single-sex spaces (area 5) in config/vote_tracker.yaml. Creating
them is an editorial decision, not a meaning line, so nothing here has been added to the
tracker.

- [ ] `2421` 2026-09-08 [Health Bill: Report Stage: New Clause 142](https://votes.parliament.uk/Votes/Commons/Division/2421) — **Puberty blockers**, area 3. Lead Dr Caroline Johnson (Con), 9 sponsors. Result 108 Aye / 357 No: **defeated**. Our side: **AYE** (Johnson voted Aye as sponsor).
      - The clause: within three months, the Secretary of State must make regulations ensuring puberty blockers may not be prescribed, dispensed or supplied to under-18s for gender dysphoria or gender incongruence, nor given in related clinical trials without Parliament's specific approval.
      - `meaning_aye` (draft): Voted to ban puberty blockers for under-18s for gender dysphoria, and to require Parliament's approval before any clinical trial.
      - `meaning_no` (draft): Voted against banning puberty blockers for under-18s.

- [ ] `2422` 2026-09-08 [Health Bill: Report Stage: New Clause 143](https://votes.parliament.uk/Votes/Commons/Division/2422) — **Single sex facilities**, area 5. Lead Dr Caroline Johnson (Con), 8 sponsors. Result 106 Aye / 302 No: **defeated**. Our side: **AYE** (Johnson voted Aye as sponsor).
      - The clause: requires the Secretary of State to ensure single-sex changing rooms, toilets and washing facilities for NHS staff, and single-sex wards and washing facilities for NHS patients, with exemptions for children, intensive care and named circumstances.
      - `meaning_aye` (draft): Voted to require single-sex wards, toilets and changing facilities for NHS patients and staff.
      - `meaning_no` (draft): Voted against requiring single-sex facilities in the NHS.

- [x] `2423` 2026-09-08 [Health Bill: Report Stage: Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/2423) — **NOT OURS. Do not add.** Clause 63 identified 10 Sept: "Transfer of HSSIB's functions to CQC", at page 45 line 40 of Bill 131 as amended in Committee, which matches the amendment's "page 45, line 39". So Dr Caroline Johnson's Amendment 1 would have kept the Health Services Safety Investigations Body independent instead of folding its functions into the Care Quality Commission. That is NHS structure and patient safety, not life, family or freedom. It touches none of the twelve areas.
      - Why it nearly got in: it drew the largest support of the four (162 Aye / 297 No) and was led by the same member who led the two that ARE ours, so it looked of a piece with them. Ledgering it would have placed about 450 members on a values sheet for a vote about an arm's-length body.
      - **Read the right version.** In HL Bill 52 (as brought from the Commons) clause 63 is "Sections 58 to 62: interpretation" and the HSSIB transfer is clause 65 -- the numbering shifted when Government new clauses were added at report stage. The version to read for a report-stage amendment is the one before the House that day: Bill 131 as amended in Committee.

- [ ] `2420` 2026-09-08 [Health Bill: Report Stage: New Clause 140](https://votes.parliament.uk/Votes/Commons/Division/2420) — **Corridor care**, lead Helen Morgan (LD). Listed for completeness: NOT one of ours, and no meaning line is proposed.

## Batch 1 — reviewed 10 September 2026 (20 of 130): three to add, seventeen not ours

*Method: each division's record from the Commons Votes API (result, tellers); the amendment or
motion text from the Bills API where it exists, otherwise from the Hansard debate of the day
(the Deputy Speaker's grouping and the Minister's tour of the amendments); our side from how the
members who argued the point voted, never from the title. Debate dumps are in the session
scratchpad, not the repo.*

**Add to the tracker (a new issue is needed: children's access to social media, area 6):**

- [ ] `2320` 2026-04-15 [Children's Wellbeing and Schools Bill: Amendments (a) to (f) in lieu of Lords Amendment 38](https://votes.parliament.uk/Votes/Commons/Division/2320) — **Under-16 social media ban**, area 6. Lords Amendment 38 (Lord Nash, Con) would have barred under-16s from social media platforms; the Government's amendments in lieu replaced it with a power to act after its consultation and a duty to report progress within six months. Result 256 Aye / 150 No: **Government amendments in lieu agreed, the ban dropped**. Our side: **NO** (Laura Trott, who argued for the ban as shadow Secretary of State, voted No; the Minister, Olivia Bailey, Aye; Munira Wilson (LD) and Aphra Brandreth (Con), who spoke for the ban, No).
      - `meaning_aye` (draft): Voted to replace the Lords' ban on under-16s using social media with a Government consultation and a six-month progress report.
      - `meaning_no` (draft): Voted to keep the Lords' ban on under-16s using social media.
- [ ] `2338` 2026-04-22 [Children's Wellbeing and Schools Bill: motion to insist on Amendment 38J and disagree with Lords Amendments 38V to 38X](https://votes.parliament.uk/Votes/Commons/Division/2338) — **Under-16 social media ban, third round**, area 6. The Lords had amended the Government's own clause (38J, a power to require internet service providers to restrict children's access) to bind it to act; the Government insisted on the unamended power. Result 260 Aye / 161 No: **Government insisted; Lords amendments rejected**. Our side: **NO** (Trott: "they have chosen to vote against a ban for a third time"; Trott, Brandreth, Wilson No; Bailey Aye). Same issue as 2320; the first-round Commons division on Lords Amendment 38 (stage 20498, March 2026) should be looked for when this issue is created.
      - `meaning_aye` (draft): Voted with the Government to keep only a discretionary power over children's access to social media, rejecting the Lords' duty to act.
      - `meaning_no` (draft): Voted for the Lords' amendments binding the Government to restrict under-16s' access to social media.
- [ ] `2323` 2026-04-15 [Children's Wellbeing and Schools Bill: Amendments (a) to (c) in lieu of Lords Amendment 106](https://votes.parliament.uk/Votes/Commons/Division/2323) — **Smartphones in schools**, area 6, **editorial call**: Lords Amendment 106 would have required schools to prohibit smartphones during the school day; the Government's amendments in lieu made it a power to put guidance on a statutory footing by regulations. Result 248 Aye / 139 No. Our side, IF this is one of ours: **NO** (Trott, Brandreth, Wilson No; Bailey Aye). Whether phones in schools is a CitizenGO issue is your decision; the social media ban above plainly is.
      - `meaning_aye` (draft): Voted to replace the Lords' school-day smartphone ban with a power to make phone guidance statutory.
      - `meaning_no` (draft): Voted to require schools to ban smartphones during the school day.

**Not ours (checked against the debate, not the title):**

- [x] `2416` 2026-09-02 Representation of the People Bill: Third Reading — franchise at 16, automatic registration, donations rules. None of the twelve areas. (411 / 102.)
- [x] `2415` 2026-09-02 RotP Bill NC88 (Lisa Smart, LD) — a Royal Commission on a cap on political donations. Not ours. (85 / 427.)
- [x] `2414` 2026-09-02 RotP Bill NC67 (Paul Holmes, Con) — an offence of publishing election campaign material in a foreign language. Elections law; touches no area (the area 11 tag was same-debate migration speeches, and area 11 is never campaigned). (105 / 410.)
- [x] `2413` 2026-09-02 RotP Bill NC65 (Paul Holmes, Con) — an independent review of overseas electors' registration. Not ours. (166 / 346.)
- [x] `2402` 2026-07-08 Draft Children's Wellbeing and Schools Act 2026 (Establishment of Schools) (Consequential Amendments) Regulations — deferred division approving consequential regulations after the end of the academy presumption. Schools structure, not parental rights; "schools" matched the title. (369 / 102.)
- [x] `2351` 2026-05-19 King's Speech, amendment (i) — the Opposition's regret amendment on oil and gas licensing, Rosebank, Wylfa and the carbon tax (text in Hansard, 19 May, Energy Security day). Same-debate tags came from other days of the Address debate. (108 / 323.)
- [x] `2339` 2026-04-22 Crime and Policing Bill: insist on 439C/439D — proscription of the Islamic Revolutionary Guard Corps (Lords Amendment 359/439 line). Not ours. (253 / 143.)
- [x] `2327` 2026-04-20 Crime and Policing Bill: in lieu of Lords Amendments 359 and 439 — IRGC proscription. Not ours. (292 / 158.)
- [x] `2326` 2026-04-20 Crime and Policing Bill: in lieu of Lords Amendment 342 — consultation duty before youth diversion orders (Baroness Doocey). Not ours. (294 / 61.)
- [x] `2325` 2026-04-20 Crime and Policing Bill: in lieu of Lords Amendment 11 — seizure of vehicles used for fly-tipping. Not ours. (294 / 156.)
- [x] `2324` 2026-04-20 Crime and Policing Bill: amendments to 2B/2C in lieu — fixed penalty notices issued for profit by enforcement contractors (Lib Dem line). Not ours. (293 / 159.)
- [x] `2322` 2026-04-15 Children's Wellbeing and Schools Bill: in lieu of Lords Amendment 102 — the schools adjudicator's power to lower a published admission number. Admissions machinery; "parental choice" appears but it is not a parental-rights vote. (259 / 136.)
- [x] `2321` 2026-04-15 Children's Wellbeing and Schools Bill: disagree with Lords Amendment 41B — a review of the cap on branded school uniform items. Not ours. (254 / 144.)
- [x] `2311` 2026-04-14 Crime and Policing Bill: agree with all remaining Lords amendments — the bulk motion; the 21 Noes were told by Apsana Begum and Kim Johnson (Labour left). Nothing in the remaining amendments is on our issues. (247 / 21.)
- [x] `2310` 2026-04-14 Crime and Policing Bill: disagree with Lords Amendment 359 — IRGC proscription. Not ours. (277 / 158.)
- [x] `2309` 2026-04-14 Crime and Policing Bill: disagree with Lords Amendment 357 — removing the "historical" safeguard from the offence of glorifying terrorism (Baroness Foster; DUP/UUP tellers). Terrorism law, not ours. (278 / 73.)
- [x] `2308` 2026-04-14 Crime and Policing Bill: disagree with Lords Amendment 342 — youth diversion orders consultation. Not ours. (281 / 70.)

**Flag for batch 2, found while reading 14 April:** `2306` (disagree with Lords Amendment 334) IS ours — the Lords amendment ended the recording of non-crime hate incidents and required any future guidance to have "due regard to the right to freedom of expression"; the Government moved to disagree and won 356 / 90 (Hansard Division No. 472). Area 7. Our side will be NO. Also from that day, `2304` (Lords Amendment 311, Lord Walney: a power to designate "extreme criminal protest groups") is a civil-liberties vote worth a deliberate decision rather than a reflex either way.

## This Parliament and the last, 2020 to 2026 (110 still to review)

- [ ] `2306` 2026-04-14 [Crime and Policing Bill: motion to disagree with Lords Amendment 334](https://votes.parliament.uk/Votes/Commons/Division/2306) — Abortion (title)
- [ ] `2305` 2026-04-14 [Crime and Policing Bill: motion to disagree with Lords Amendment 333](https://votes.parliament.uk/Votes/Commons/Division/2305) — Abortion (title)
- [ ] `2304` 2026-04-14 [Crime and Policing Bill: motion to disagree with Lords Amendment 311](https://votes.parliament.uk/Votes/Commons/Division/2304) — Abortion (title)
- [ ] `2303` 2026-04-14 [Crime and Policing Bill: motion to disagree with Lords Amendment 11](https://votes.parliament.uk/Votes/Commons/Division/2303) — Abortion (title)
- [ ] `2301` 2026-04-14 [Crime and Policing Bill: motion to disagree with Lords Amendment 6](https://votes.parliament.uk/Votes/Commons/Division/2301) — Abortion (title)
- [ ] `2300` 2026-04-14 [Crime and Policing Bill: motion to disagree with Lords Amendment 2](https://votes.parliament.uk/Votes/Commons/Division/2300) — Abortion (title)
- [ ] `2277` 2026-03-10 [Courts and Tribunals Bill: Second Reading](https://votes.parliament.uk/Votes/Commons/Division/2277) — Prostitution, trafficking and sexual exploitation, Free speech, privacy and civil liberties, Conversion practices, Migration (same debate)
- [ ] `2276` 2026-03-10 [Courts and Tribunals Bill: Reasoned Amendment to Second Reading](https://votes.parliament.uk/Votes/Commons/Division/2276) — Prostitution, trafficking and sexual exploitation, Free speech, privacy and civil liberties, Conversion practices, Migration (same debate)
- [ ] `2275` 2026-03-09 [Children's Wellbeing and Schools Bill: motion to disagree with Lords Amendment 106](https://votes.parliament.uk/Votes/Commons/Division/2275) — Parental rights education (title)
- [ ] `2274` 2026-03-09 [Children's Wellbeing and Schools Bill: motion to disagree with Lords Amendment 102](https://votes.parliament.uk/Votes/Commons/Division/2274) — Parental rights education (title)
- [ ] `2273` 2026-03-09 [Children's Wellbeing and Schools Bill: motion to disagree with Lords Amendment 44](https://votes.parliament.uk/Votes/Commons/Division/2273) — Parental rights education (title)
- [ ] `2272` 2026-03-09 [Children's Wellbeing and Schools Bill: motion to disagree with Lords Amendment 41](https://votes.parliament.uk/Votes/Commons/Division/2272) — Parental rights education (title)
- [ ] `2271` 2026-03-09 [Children's Wellbeing and Schools Bill: motion to disagree with Lords Amendment 38](https://votes.parliament.uk/Votes/Commons/Division/2271) — Parental rights education (title)
- [ ] `2270` 2026-03-09 [Children's Wellbeing and Schools Bill: motion to disagree with Lords Amendment 37](https://votes.parliament.uk/Votes/Commons/Division/2270) — Parental rights education (title)
- [ ] `2269` 2026-03-09 [Children's Wellbeing and Schools Bill: motion to disagree with Lords Amendment 17](https://votes.parliament.uk/Votes/Commons/Division/2269) — Parental rights education (title)
- [ ] `2268` 2026-03-09 [Children's Wellbeing and Schools Bill: motion to disagree with Lords Amendment 16](https://votes.parliament.uk/Votes/Commons/Division/2268) — Parental rights education (title)
- [ ] `2266` 2026-02-24 [Opposition Day: Protections for children from online harms](https://votes.parliament.uk/Votes/Commons/Division/2266) — Free speech, privacy and civil liberties (title)
- [ ] `2065` 2025-06-18 [Crime and Policing Bill: Third Reading](https://votes.parliament.uk/Votes/Commons/Division/2065) — Abortion (title)
- [ ] `2064` 2025-06-18 [Crime and Policing Bill Report Stage: New Clause 130](https://votes.parliament.uk/Votes/Commons/Division/2064) — Abortion (title)
- [ ] `2063` 2025-06-18 [Crime and Policing Bill Report Stage: New Clause 121](https://votes.parliament.uk/Votes/Commons/Division/2063) — Abortion (title)
- [ ] `2062` 2025-06-18 [Crime and Policing Bill Report Stage: New Clause 88](https://votes.parliament.uk/Votes/Commons/Division/2062) — Abortion (title)
- [ ] `2061` 2025-06-18 [Crime and Policing Bill Report Stage: New Clause 43](https://votes.parliament.uk/Votes/Commons/Division/2061) — Abortion (title)
- [ ] `2057` 2025-06-17 [Crime and Policing Bill Report Stage: Amendment 160](https://votes.parliament.uk/Votes/Commons/Division/2057) — Abortion (title)
- [ ] `2056` 2025-06-17 [Crime and Policing Bill Report Stage: Amendment 19](https://votes.parliament.uk/Votes/Commons/Division/2056) — Abortion (title)
- [ ] `2055` 2025-06-17 [Crime and Policing Bill Report Stage: Amendment 175](https://votes.parliament.uk/Votes/Commons/Division/2055) — Abortion (title)
- [ ] `2054` 2025-06-17 [Crime and Policing Bill Report Stage: Amendment 174](https://votes.parliament.uk/Votes/Commons/Division/2054) — Abortion (title)
- [ ] `1981` 2025-03-26 [Tobacco and Vapes Bill: Third Reading](https://votes.parliament.uk/Votes/Commons/Division/1981) — Free speech, privacy and civil liberties (same debate)
- [ ] `1980` 2025-03-26 [Tobacco and Vapes Bill Report Stage: Amendment 85](https://votes.parliament.uk/Votes/Commons/Division/1980) — Free speech, privacy and civil liberties (same debate)
- [ ] `1979` 2025-03-26 [Tobacco and Vapes Bill Report Stage: Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/1979) — Free speech, privacy and civil liberties (same debate)
- [ ] `1978` 2025-03-26 [Tobacco and Vapes Bill Report Stage: New Clause 19](https://votes.parliament.uk/Votes/Commons/Division/1978) — Free speech, privacy and civil liberties (same debate)
- [ ] `1977` 2025-03-26 [Tobacco and Vapes Bill Report Stage: New Clause 2](https://votes.parliament.uk/Votes/Commons/Division/1977) — Free speech, privacy and civil liberties (same debate)
- [ ] `1956` 2025-03-18 [Children's Wellbeing and Schools Bill Report Stage: Amendment 210](https://votes.parliament.uk/Votes/Commons/Division/1956) — Parental rights education (title)
- [ ] `1955` 2025-03-18 [Children's Wellbeing and Schools Bill Report Stage: Amendment 209](https://votes.parliament.uk/Votes/Commons/Division/1955) — Parental rights education (title)
- [ ] `1954` 2025-03-18 [Children's Wellbeing and Schools Bill Report Stage: New Clause 34](https://votes.parliament.uk/Votes/Commons/Division/1954) — Parental rights education (title)
- [ ] `1953` 2025-03-18 [Children's Wellbeing and Schools Bill Report Stage: New Clause 7](https://votes.parliament.uk/Votes/Commons/Division/1953) — Parental rights education (title)
- [ ] `1952` 2025-03-17 [Children's Wellbeing and Schools Bill Report Stage: Amendment 171](https://votes.parliament.uk/Votes/Commons/Division/1952) — Parental rights education (title)
- [ ] `1951` 2025-03-17 [Children's Wellbeing and Schools Bill Report Stage: Amendment 188](https://votes.parliament.uk/Votes/Commons/Division/1951) — Parental rights education (title)
- [ ] `1950` 2025-03-17 [Children's Wellbeing and Schools Bill Report Stage: New Clause 36](https://votes.parliament.uk/Votes/Commons/Division/1950) — Parental rights education (title)
- [ ] `1900` 2025-01-08 [Reasoned amendment on Children's Wellbeing and Schools Bill](https://votes.parliament.uk/Votes/Commons/Division/1900) — Parental rights education (title)
- [ ] `1817` 2024-05-15 [Criminal Justice Bill Report Stage: New Clause 91](https://votes.parliament.uk/Votes/Commons/Division/1817) — Abortion, Free speech, privacy and civil liberties, Area 12 (same debate)
- [ ] `1816` 2024-05-15 [Criminal Justice Bill Report Stage: New Clause 59](https://votes.parliament.uk/Votes/Commons/Division/1816) — Abortion, Free speech, privacy and civil liberties, Area 12 (same debate)
- [ ] `1815` 2024-05-15 [Criminal Justice Bill Report Stage: New Clause 44](https://votes.parliament.uk/Votes/Commons/Division/1815) — Abortion, Free speech, privacy and civil liberties, Area 12 (same debate)
- [ ] `1787` 2024-04-16 [Tobacco and Vapes Bill: Second Reading](https://votes.parliament.uk/Votes/Commons/Division/1787) — Prostitution, trafficking and sexual exploitation (same debate)
- [ ] `1683` 2023-11-29 [Data Protection and Digital Information Bill: Third Reading](https://votes.parliament.uk/Votes/Commons/Division/1683) — Free speech, privacy and civil liberties (same debate)
- [ ] `1682` 2023-11-29 [Data Protection and Digital Information Bill Report Stage: New Schedule 1](https://votes.parliament.uk/Votes/Commons/Division/1682) — Free speech, privacy and civil liberties (same debate)
- [ ] `1681` 2023-11-29 [Data Protection and Digital Information Bill Report Stage: Amendment 218](https://votes.parliament.uk/Votes/Commons/Division/1681) — Free speech, privacy and civil liberties (same debate)
- [ ] `1680` 2023-11-29 [Data Protection and Digital Information Bill Report Stage: Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/1680) — Free speech, privacy and civil liberties (same debate)
- [ ] `1679` 2023-11-29 [Data Protection and Digital Information Bill Report Stage: Amendment 5](https://votes.parliament.uk/Votes/Commons/Division/1679) — Free speech, privacy and civil liberties (same debate)
- [ ] `1678` 2023-11-29 [Data Protection and Digital Information Bill Report Stage: Amendment 224](https://votes.parliament.uk/Votes/Commons/Division/1678) — Free speech, privacy and civil liberties (same debate)
- [ ] `1677` 2023-11-29 [Data Protection and Digital Information Bill Report Stage: Amendment 11](https://votes.parliament.uk/Votes/Commons/Division/1677) — Free speech, privacy and civil liberties (same debate)
- [ ] `1676` 2023-11-29 [Data Protection and Digital Information Bill: Re-committal motion](https://votes.parliament.uk/Votes/Commons/Division/1676) — Free speech, privacy and civil liberties (same debate)
- [ ] `1667` 2023-11-15 [King's Speech Motion for an Address: Amendment (k)](https://votes.parliament.uk/Votes/Commons/Division/1667) — Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `1666` 2023-11-15 [King's Speech Motion for an Address: Amendment (h)](https://votes.parliament.uk/Votes/Commons/Division/1666) — Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `1665` 2023-11-15 [King's Speech Motion for an Address: amendment (r)](https://votes.parliament.uk/Votes/Commons/Division/1665) — Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `1664` 2023-11-14 [King's Speech Motion for an Address: amendment (m)](https://votes.parliament.uk/Votes/Commons/Division/1664) — Parental rights education, Free speech, privacy and civil liberties, Marriage and family, Migration (same debate)
- [ ] `1663` 2023-10-25 [Economic Activity of Public Bodies (Overseas Matters) Bill Report Stage: Amendment 28](https://votes.parliament.uk/Votes/Commons/Division/1663) — Free speech, privacy and civil liberties (same debate)
- [ ] `1662` 2023-10-25 [Economic Activity of Public Bodies (Overseas Matters) Bill Report Stage: Amendment 7](https://votes.parliament.uk/Votes/Commons/Division/1662) — Free speech, privacy and civil liberties (same debate)
- [ ] `1661` 2023-10-25 [Economic Activity of Public Bodies (Overseas Matters) Bill Report Stage: Amendment 13](https://votes.parliament.uk/Votes/Commons/Division/1661) — Free speech, privacy and civil liberties (same debate)
- [ ] `1660` 2023-10-25 [Economic Activity of Public Bodies (Overseas Matters) Bill Report Stage: Amendment 14](https://votes.parliament.uk/Votes/Commons/Division/1660) — Free speech, privacy and civil liberties (same debate)
- [ ] `1588` 2023-07-11 [Illegal Migration Bill: motion to disagree with Lords Amendment 6](https://votes.parliament.uk/Votes/Commons/Division/1588) — Migration (title)
- [ ] `1587` 2023-07-11 [Illegal Migration Bill: motion to disagree with Lords Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/1587) — Migration (title)
- [ ] `1583` 2023-06-28 [Relationships and Sexuality Education (Northern Ireland) (Amendment) Regulations 2023](https://votes.parliament.uk/Votes/Commons/Division/1583) — Parental rights education (title)
- [ ] `1534` 2023-04-26 [Illegal Migration Bill - Third Reading](https://votes.parliament.uk/Votes/Commons/Division/1534) — Migration (title)
- [ ] `1533` 2023-04-26 [Illegal Migration Bill Report Stage: Amendment 2](https://votes.parliament.uk/Votes/Commons/Division/1533) — Migration (title)
- [ ] `1532` 2023-04-26 [Illegal Migration Bill Report Stage: Amendment 45](https://votes.parliament.uk/Votes/Commons/Division/1532) — Migration (title)
- [ ] `1531` 2023-04-26 [Illegal Migration Bill Report Stage: New Clause 15](https://votes.parliament.uk/Votes/Commons/Division/1531) — Migration (title)
- [ ] `1530` 2023-04-26 [Illegal Migration Bill Report Stage: New Clause 10](https://votes.parliament.uk/Votes/Commons/Division/1530) — Migration (title)
- [ ] `1529` 2023-04-26 [Illegal Migration Bill Report Stage: New Clause 9](https://votes.parliament.uk/Votes/Commons/Division/1529) — Migration (title)
- [ ] `1514` 2023-03-28 [Illegal Migration Bill: Committee of the whole House: New Clause 27](https://votes.parliament.uk/Votes/Commons/Division/1514) — Migration (title)
- [ ] `1513` 2023-03-28 [Illegal Migration Bill: Committee of the whole House: New Clause 21](https://votes.parliament.uk/Votes/Commons/Division/1513) — Migration (title)
- [ ] `1512` 2023-03-28 [Illegal Migration Bill: Committee of the whole House: Amendment 288](https://votes.parliament.uk/Votes/Commons/Division/1512) — Migration (title)
- [ ] `1511` 2023-03-28 [Illegal Migration Bill: Committee of the whole House: Clause 11 stand part](https://votes.parliament.uk/Votes/Commons/Division/1511) — Migration (title)
- [ ] `1510` 2023-03-28 [Illegal Migration Bill: Committee of the whole House: Amendment 189](https://votes.parliament.uk/Votes/Commons/Division/1510) — Migration (title)
- [ ] `1499` 2023-03-13 [Illegal Migration Bill: Money](https://votes.parliament.uk/Votes/Commons/Division/1499) — Migration (title)
- [ ] `1498` 2023-03-13 [Illegal Migration Bill: Programme motion](https://votes.parliament.uk/Votes/Commons/Division/1498) — Migration (title)
- [ ] `1497` 2023-03-13 [Illegal Migration Bill: Second Reading](https://votes.parliament.uk/Votes/Commons/Division/1497) — Migration (title)
- [ ] `1496` 2023-03-13 [Illegal Migration Bill: Reasoned Amendment to Second Reading](https://votes.parliament.uk/Votes/Commons/Division/1496) — Migration (title)
- [ ] `1495` 2023-03-07 [Public Order Bill: Motion to disagree with Lords Amendment 20](https://votes.parliament.uk/Votes/Commons/Division/1495) — Abortion, Free speech, privacy and civil liberties (same debate)
- [ ] `1494` 2023-03-07 [Public Order Bill: Amendment (a) in lieu of Lords Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/1494) — Abortion, Free speech, privacy and civil liberties (same debate)
- [ ] `1493` 2023-03-07 [Public Order Bill: Motion to disagree with Lords Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/1493) — Abortion, Free speech, privacy and civil liberties (same debate)
- [ ] `1492` 2023-03-07 [Public Order Bill: Motion to disagree with Lords Amendment 6](https://votes.parliament.uk/Votes/Commons/Division/1492) — Abortion, Free speech, privacy and civil liberties (same debate)
- [ ] `1456` 2023-01-18 [Retained EU Law (Revocation and Reform) Bill: Third Reading](https://votes.parliament.uk/Votes/Commons/Division/1456) — Free speech, privacy and civil liberties (same debate)
- [ ] `1455` 2023-01-18 [Retained EU Law (Revocation and Reform) Bill Report Stage: Amendment 36](https://votes.parliament.uk/Votes/Commons/Division/1455) — Free speech, privacy and civil liberties (same debate)
- [ ] `1454` 2023-01-18 [Retained EU Law (Revocation and Reform) Bill Report Stage: Amendment 19](https://votes.parliament.uk/Votes/Commons/Division/1454) — Free speech, privacy and civil liberties (same debate)
- [ ] `1453` 2023-01-18 [Retained EU Law (Revocation and Reform) Bill Report Stage: Amendment 28](https://votes.parliament.uk/Votes/Commons/Division/1453) — Free speech, privacy and civil liberties (same debate)
- [ ] `1452` 2023-01-18 [Retained EU Law (Revocation and Reform) Bill Report Stage: Amendment 18](https://votes.parliament.uk/Votes/Commons/Division/1452) — Free speech, privacy and civil liberties (same debate)
- [ ] `1422` 2022-12-07 [Financial Services and Markets Bill Report Stage: New Clause 1](https://votes.parliament.uk/Votes/Commons/Division/1422) — Gender medicine children, Free speech, privacy and civil liberties (same debate)
- [ ] `1370` 2022-10-18 [Public Order Bill: Third Reading](https://votes.parliament.uk/Votes/Commons/Division/1370) — Abortion, Free speech, privacy and civil liberties (same debate)
- [ ] `1369` 2022-10-18 [Public Order Bill Report Stage: Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/1369) — Abortion, Free speech, privacy and civil liberties (same debate)
- [ ] `1367` 2022-10-18 [Public Order Bill Report Stage: New Clause 5](https://votes.parliament.uk/Votes/Commons/Division/1367) — Abortion, Free speech, privacy and civil liberties (same debate)
- [ ] `1366` 2022-10-18 [Public Order Bill Report Stage: New Clause 4](https://votes.parliament.uk/Votes/Commons/Division/1366) — Abortion, Free speech, privacy and civil liberties (same debate)
- [ ] `1351` 2022-07-18 [Confidence in Her Majesty’s Government](https://votes.parliament.uk/Votes/Commons/Division/1351) — Free speech, privacy and civil liberties (same debate)
- [ ] `1323` 2022-06-21 [Opposition Day: Adviser on Ministerial Interests](https://votes.parliament.uk/Votes/Commons/Division/1323) — Free speech, privacy and civil liberties (same debate)
- [ ] `1313` 2022-05-23 [Public Order Bill: Second Reading](https://votes.parliament.uk/Votes/Commons/Division/1313) — Abortion, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `1312` 2022-05-23 [Public Order Bill: Reasoned Amendment to Second Reading](https://votes.parliament.uk/Votes/Commons/Division/1312) — Abortion, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `1307` 2022-05-17 [Queen's Speech debate (Opposition amendment v)](https://votes.parliament.uk/Votes/Commons/Division/1307) — Prostitution, trafficking and sexual exploitation, Sex based rights, Gender medicine children, Parental rights education, Free speech, privacy and civil liberties (same debate)
- [ ] `1107` 2021-09-22 [Compensation (London Capital & Finance plc and Fraud Compensation Fund) Bill Report Stage: Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/1107) — Free speech, privacy and civil liberties (same debate)
- [ ] `1026` 2021-05-18 [Queen's Speech (Motion for an Address): Amendment (h)](https://votes.parliament.uk/Votes/Commons/Division/1026) — Assisted dying, Sex based rights, Gender medicine children, Parental rights education, Free speech, privacy and civil liberties, Freedom of religion, Migration (same debate)
- [ ] `1002` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 43](https://votes.parliament.uk/Votes/Commons/Division/1002) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `1001` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 42](https://votes.parliament.uk/Votes/Commons/Division/1001) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `1000` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 41](https://votes.parliament.uk/Votes/Commons/Division/1000) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `999` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 40](https://votes.parliament.uk/Votes/Commons/Division/999) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `998` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 38](https://votes.parliament.uk/Votes/Commons/Division/998) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `997` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 37](https://votes.parliament.uk/Votes/Commons/Division/997) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `996` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 33](https://votes.parliament.uk/Votes/Commons/Division/996) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `995` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 9](https://votes.parliament.uk/Votes/Commons/Division/995) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `994` 2021-04-15 [Domestic Abuse Bill: Motion to disagree with Lords Amendment 1](https://votes.parliament.uk/Votes/Commons/Division/994) — Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `935` 2021-01-06 [Public Health (S.I. No. 8)](https://votes.parliament.uk/Votes/Commons/Division/935) — Parental rights education, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `815` 2020-07-06 [Domestic Abuse Bill Report Stage: New Clause 23](https://votes.parliament.uk/Votes/Commons/Division/815) — Abortion, Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `814` 2020-07-06 [Domestic Abuse Bill: Report Stage: New Clause 22](https://votes.parliament.uk/Votes/Commons/Division/814) — Abortion, Gender medicine children, Free speech, privacy and civil liberties, Migration (same debate)

## The 2017 Parliament (7)

- [ ] `650` 2019-03-27 [Draft Relationships Education, Relationships and Sex Education and Health Education (England) Regulations 2019](https://votes.parliament.uk/Votes/Commons/Division/650) — Parental rights education (title)
- [ ] `539` 2018-11-28 [Offensive Weapons Bill - report NC6](https://votes.parliament.uk/Votes/Commons/Division/539) — Assisted dying, Free speech, privacy and civil liberties (same debate)
- [ ] `538` 2018-11-28 [Offensive Weapons Bill - Report Govt Amdts 26 to 55](https://votes.parliament.uk/Votes/Commons/Division/538) — Assisted dying, Free speech, privacy and civil liberties (same debate)
- [ ] `422` 2018-05-09 [Data Protection Bill [Lords]: Report Stage Amdt 15](https://votes.parliament.uk/Votes/Commons/Division/422) — Abortion, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `421` 2018-05-09 [Data Protection Bill [Lords]: Report Stage Amdt 5](https://votes.parliament.uk/Votes/Commons/Division/421) — Abortion, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `420` 2018-05-09 [Data Protection Bill [Lords]: Report Stage New Clause 4](https://votes.parliament.uk/Votes/Commons/Division/420) — Abortion, Free speech, privacy and civil liberties, Migration (same debate)
- [ ] `419` 2018-05-09 [Data Protection Bill [Lords]: Report stage New Clause 18](https://votes.parliament.uk/Votes/Commons/Division/419) — Abortion, Free speech, privacy and civil liberties, Migration (same debate)
