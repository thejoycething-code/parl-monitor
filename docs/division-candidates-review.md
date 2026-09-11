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

- [x] `2320` **SIGNED OFF 11 Sept** — 2026-04-15 [Children's Wellbeing and Schools Bill: Amendments (a) to (f) in lieu of Lords Amendment 38](https://votes.parliament.uk/Votes/Commons/Division/2320) — **Under-16 social media ban**, area 6. Lords Amendment 38 (Lord Nash, Con) would have barred under-16s from social media platforms; the Government's amendments in lieu replaced it with a power to act after its consultation and a duty to report progress within six months. Result 256 Aye / 150 No: **Government amendments in lieu agreed, the ban dropped**. Our side: **NO** (Laura Trott, who argued for the ban as shadow Secretary of State, voted No; the Minister, Olivia Bailey, Aye; Munira Wilson (LD) and Aphra Brandreth (Con), who spoke for the ban, No).
      - `meaning_aye` (draft): Voted to replace the Lords' ban on under-16s using social media with a Government consultation and a six-month progress report.
      - `meaning_no` (draft): Voted to keep the Lords' ban on under-16s using social media.
- [x] `2338` **SIGNED OFF 11 Sept** — 2026-04-22 [Children's Wellbeing and Schools Bill: motion to insist on Amendment 38J and disagree with Lords Amendments 38V to 38X](https://votes.parliament.uk/Votes/Commons/Division/2338) — **Under-16 social media ban, third round**, area 6. The Lords had amended the Government's own clause (38J, a power to require internet service providers to restrict children's access) to bind it to act; the Government insisted on the unamended power. Result 260 Aye / 161 No: **Government insisted; Lords amendments rejected**. Our side: **NO** (Trott: "they have chosen to vote against a ban for a third time"; Trott, Brandreth, Wilson No; Bailey Aye). Same issue as 2320; the first-round Commons division on Lords Amendment 38 (stage 20498, March 2026) should be looked for when this issue is created.
      - `meaning_aye` (draft): Voted with the Government to keep only a discretionary power over children's access to social media, rejecting the Lords' duty to act.
      - `meaning_no` (draft): Voted for the Lords' amendments binding the Government to restrict under-16s' access to social media.
- [x] `2323` **SIGNED OFF 11 Sept** — 2026-04-15 [Children's Wellbeing and Schools Bill: Amendments (a) to (c) in lieu of Lords Amendment 106](https://votes.parliament.uk/Votes/Commons/Division/2323) — **Smartphones in schools**, area 6, **editorial call**: Lords Amendment 106 would have required schools to prohibit smartphones during the school day; the Government's amendments in lieu made it a power to put guidance on a statutory footing by regulations. Result 248 Aye / 139 No. Our side, IF this is one of ours: **NO** (Trott, Brandreth, Wilson No; Bailey Aye). Whether phones in schools is a CitizenGO issue is your decision; the social media ban above plainly is.
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

## Batch 2 — reviewed 10 September 2026 (20 of 130): four added to the tracker unsigned, five for your decision, eleven not ours

*Same method as batch 1. Debates read: Commons 9 March 2026 (Children's Wellbeing and Schools
Bill, first Lords round), 14 April 2026 (Crime and Policing Bill, first Lords round), 24 February
2026 (Opposition Day), 10 March 2026 (Courts and Tribunals Bill), 18 June 2025 (Crime and
Policing Bill report stage).*

**Added to `config/vote_tracker.yaml` unsigned (issue `children-social-media` created with
your agreement of 10 Sept; 2306 under the existing `non-crime-hate`):**

- [x] `2306` **SIGNED OFF 11 Sept** — 2026-04-14 Crime and Policing Bill: disagree with Lords Amendment 334 — **Non-crime hate incidents**, area 7. The Lords amendment ended the investigation and recording of NCHIs and required any future guidance to have "due regard to the right to freedom of expression" (Matt Vickers quoting Lord Hogan-Howe: "we need to move on from the recording of non-crime hate incidents by removing them altogether from police systems"). Government motion to disagree carried 356 / 90. Our side **NO** (Vickers and Philp No; Sarah Jones Aye; the Liberal Democrats voted Aye with the Government this round, unlike June 2025).
- [x] `2271` **SIGNED OFF 11 Sept** — 2026-03-09 CWS Bill: disagree with Lords Amendment 38 — the **under-16 social media ban**, first round (Lord Nash). 307 / 173. Our side **NO** (Trott, Wilson No; Bailey Aye). Landmark.
- [x] `2275` **SIGNED OFF 11 Sept** — 2026-03-09 CWS Bill: disagree with Lords Amendment 106 — **smartphones banned in schools**, first round. 304 / 177. Our side **NO**. Landmark.
- [x] `2270` **SIGNED OFF 11 Sept** — 2026-03-09 CWS Bill: disagree with Lords Amendment 37 — **children's use of VPNs**, paired with 38 in the Minister's speech ("social media, VPNs and phones in schools"); the Government's amendments in lieu took a power to "age-restrict or limit children's VPN use". 321 / 106: Conservatives against, Liberal Democrats did not oppose. Our side **NO**; not a landmark.

**Your decision (drafted but NOT added):**

- [ ] `2273` 2026-03-09 CWS Bill: disagree with Lords Amendment 44 — **home education consent**, area 6, direction contested. Lords Amendment 44 (pressed by the Conservatives after the Sara Sharif review) would have EXTENDED the Bill's requirement for local-authority consent before home-educating to "any child who has ever had a child protection plan"; the Minister opposed it "on principle" because extending the consent requirement "would risk discouraging families from seeking or continuing to receive help". 315 / 109 (Conservatives, DUP, some Independents against). This cuts across the parental-rights card: the Government's position is the LESS restrictive one for parents. If you want it on the tracker it belongs under `parental-rights`, and our side is your call, not mine.
- [ ] `2304` 2026-04-14 Crime and Policing Bill: disagree with Lords Amendment 311 — Lord Walney's power for the Secretary of State to designate "extreme criminal protest groups" (not terrorist proscription: restricting membership, promotion, fundraising). 300 / 101 (Conservatives against the disagree, i.e. for the power; Liberal Democrats "cautious"). A civil-liberties vote under area 7's widened remit, but the pro-liberty side is arguably the Government's. Decide deliberately or leave it out.
- [ ] `2063` 2025-06-18 Crime and Policing Bill report stage: New Clause 121 (Dame Caroline Dinenage, Con) — extend the **extreme pornography** offence to material depicting an act "which affects a person's ability to breathe and constitutes battery" (strangulation). 114 Aye / 310 No: rejected, Government against; the Government later legislated the same policy in the Lords. Pornography is a tier-2 term in areas 7 and 12. If it is ours: our side **AYE** (Con tellers Aye).
- [ ] `2277` / `2276` 2026-03-10 Courts and Tribunals Bill: Second Reading (304 / 203) and the Opposition's reasoned amendment (203 / 311) — curtailing the right to elect **jury trial** for either-way offences. The "prostitution" tag came from same-debate speeches. Trial by jury is a civil-liberties question, not a CitizenGO campaign; I would leave both out unless you say otherwise.
- [ ] `2266` 2026-02-24 Opposition Day: "Protections for children from online harms" — a Liberal Democrat BUSINESS motion giving Commons time on 9 March to their Online Services (Age Restrictions) Bill. 69 / 279; Conservatives largely absent. Procedural, so I would not track it, though its subject is the social-media issue above.

**Not ours (checked against the debate):**

- [x] `2305` 2026-04-14 C&P: disagree with Lords Amendment 333 — closure notices and orders for rogue premises (vape shops). (301 / 157.)
- [x] `2303` 2026-04-14 C&P: disagree with Lords Amendment 11 — seizure of fly-tipping vehicles. (291 / 174.)
- [x] `2301` 2026-04-14 C&P: disagree with Lords Amendment 6 — a local-authority duty to clear fly-tipped waste. (299 / 169.)
- [x] `2300` 2026-04-14 C&P: disagree with Lords Amendment 2 — fixed penalty notices issued for profit (Lib Dem line). (307 / 176.)
- [x] `2274` 2026-03-09 CWS: disagree with Lords Amendment 102 — schools adjudicator and admission numbers. (315 / 163.)
- [x] `2272` 2026-03-09 CWS: disagree with Lords Amendment 41 — a cost cap on school uniform. (316 / 171.)
- [x] `2269` 2026-03-09 CWS: disagree with Lords Amendment 17 — recording sibling contact in care plans. (306 / 182.)
- [x] `2268` 2026-03-09 CWS: disagree with Lords Amendment 16 — a review of the adoption and special guardianship support fund. (309 / 181.)
- [x] `2065` 2025-06-18 Crime and Policing Bill: Third Reading — the whole Bill; the abortion clause (NC1) is tracked on its own division. (312 / 95.)
- [x] `2064` 2025-06-18 C&P report stage: New Clause 130 (Matt Vickers) — tool theft and unlicensed boot sales. (178 / 313.)

## Batch 3 — reviewed 11 September 2026 (20 of 130): one added unsigned, one for your decision, eighteen not ours

*Debates read: Commons 17 and 18 June 2025 (Crime and Policing Bill report stage), 26 March 2025
(Tobacco and Vapes Bill), 17 and 18 March 2025 (Children's Wellbeing and Schools Bill report
stage), 8 January 2025 (its Second Reading), 15 May 2024 (Criminal Justice Bill). Amendment texts
from the Bills API for the CWS Bill; the Bills API holds no amendments for the Crime and Policing
Bill's Commons report stage, so those came from the Speaker's grouping in Hansard.*

**Added to `config/vote_tracker.yaml` unsigned:**

- [x] `1950` **SIGNED OFF? not yet** — 2025-03-17 CWS Bill report stage: New Clause 36 (Laura Trott) — the Commons **origin of the children-social-media issue**: CMO advice for parents on smartphones and social media, a research plan, and a phone ban in every school. 159 / 317. Our side **AYE** (Trott moved it and voted Aye; Phillipson No; Conservatives, Liberal Democrats, Reform and DUP for).

**Your decision (drafted but NOT added):**

- [ ] `1900` 2025-01-08 Reasoned amendment to the CWS Bill's Second Reading (Trott) — a composite: it declines a Second Reading over academy freedoms, teacher pay, QTS and the curriculum, and ends by calling for "a national statutory inquiry into historical child sexual exploitation, focused on grooming gangs". 111 / 364 (Conservatives, Reform, DUP for). The grooming-gangs inquiry is area 12; the other nine tenths of the text is schools policy. I would not put a composite reasoned amendment on a values tracker, but the inquiry call is the reason it was tagged, so it is your call. If added: `parental-rights` or a new area-12 issue; our side AYE.

**Not ours (checked against the amendment text):**

- [x] `2062` 2025-06-18 C&P report stage NC88 (Lib Dem) — senior-manager liability for water pollution. (178 / 313.)
- [x] `2061` 2025-06-18 C&P NC43 (Mike Martin, LD) — automatic commencement of the Protection from Sex-based Harassment in Public Act 2023. Public-order law; not one of the twelve areas. (147 / 305.)
- [x] `2057` 2025-06-17 C&P Amendment 160 (Lib Dem) — no protest conditions until a live facial recognition code of practice is approved by Parliament. Civil liberties, but surveillance policy rather than anything CitizenGO campaigns on. (89 / 428.)
- [x] `2056` 2025-06-17 C&P Amendment 19 — spiking offence extended to recklessness. (189 / 328.)
- [x] `2055` 2025-06-17 C&P Amendment 175 — weapon possession with intent: maximum sentence 4 to 14 years. (184 / 336.)
- [x] `2054` 2025-06-17 C&P Amendment 174 — consult on penalty points for fly-tipping and littering. (194 / 335.)
- [x] `1981` 2025-03-26 Tobacco and Vapes Bill: Third Reading — the generational smoking ban; the 41 Noes (Leigh and Swayne telling) were the libertarian objection. Not a CitizenGO issue. (366 / 41.)
- [x] `1980` 2025-03-26 Tobacco Amendment 85 — limit outdoor smoke-free designations to hospitals, playgrounds and schools. (92 / 303.)
- [x] `1979` 2025-03-26 Tobacco Amendment 1 (Lib Dem) — fixed-penalty income to local public health. (72 / 304.)
- [x] `1978` 2025-03-26 Tobacco NC19 — annual reports on illegal tobacco and vape sales. (159 / 307.)
- [x] `1977` 2025-03-26 Tobacco NC2 — ban on plastic cigarette filters. (137 / 304.)
- [x] `1956` 2025-03-18 CWS Amendment 210 (Trott) — leave out clause 51, one of the academy-freedom clauses. (167 / 324.)
- [x] `1955` 2025-03-18 CWS Amendment 209 (Trott) — leave out clause 45, the repeal of the duty to make failing schools academies. (107 / 324.)
- [x] `1954` 2025-03-18 CWS NC34 (Green) — free school lunches for all primary pupils. (77 / 315.)
- [x] `1953` 2025-03-18 CWS NC7 (Lib Dem) — free school meals for households under £20,000. (77 / 313.)
- [x] `1952` 2025-03-17 CWS Amendment 171 (Lib Dem) — independent special schools within the profit cap. (65 / 317.)
- [x] `1951` 2025-03-17 CWS Amendment 188 (Trott) — mandatory inspection of children's-home groups instead of improvement notices. (160 / 319.)
- [x] `1817` 2024-05-15 Criminal Justice Bill NC91 (Tim Farron, LD) — an offence of failing to meet water pollution commitments. The "abortion" tag was the watched Bill; the abortion new clauses that day were never reached. (17 / 268.)

## Batch 4 — reviewed 11 September 2026 (20 of 130): one recommended for a new issue, four for your decision, fifteen not ours

*Debates read: Commons 15 May 2024 (Criminal Justice Bill report stage), 16 April 2024 (Tobacco
and Vapes Bill Second Reading), 29 November 2023 (Data Protection and Digital Information Bill
report stage), 14-15 November 2023 (Debate on the Address), 25 October 2023 (Economic Activity of
Public Bodies (Overseas Matters) Bill report stage), 11 July 2023 (Illegal Migration Bill, Lords
amendments). Amendment texts from the Speaker's groupings in Hansard.*

**Recommended: a new area-12 issue (your call; nothing added):**

- [ ] `1815` 2024-05-15 Criminal Justice Bill report stage: New Clause 44 (Jess Phillips, Lab) — **sexual exploitation of an adult**, area 12. It would have renamed the Sexual Offences Act 2003 offences of "causing or inciting prostitution for gain" and "controlling prostitution for gain" as sexual exploitation, and defined it as conduct that "manipulates, deceives, coerces or controls another person to undertake sexual activity" — the change the STAGE partnership against adult sexual exploitation has sought so that adult victims are treated as victims. The Minister (Laura Farris) resisted "not because there is any real dispute of principle, but because there is dispute of degree". 167 / 275: Labour, Lib Dem, Green, Plaid, SDLP, Alliance, one DUP for; Conservatives against. Our side, if area 12 means what the taxonomy says: **AYE** (Phillips and Diana Johnson Aye; Farris and Philp No). There is no area-12 issue on the tracker yet; this would be the first. The Bill fell at the 2024 dissolution.
      - `meaning_aye` (draft): Voted to recognise adults manipulated, deceived, coerced or controlled into sexual activity as victims of sexual exploitation in law.
      - `meaning_no` (draft): Voted against redefining the prostitution offences as sexual exploitation of an adult.

**Your decision (drafted but NOT added):**

- [ ] `1588` 2023-07-11 Illegal Migration Bill: disagree with Lords Amendment 6 — the **modern slavery** protections Theresa May and Iain Duncan Smith fought for (Tim Farron: on "amendments 6 and 56" May "made an outstanding speech"). The Government moved to disagree and offered an amendment in lieu; 303 / 227 on party lines, May abstained, Duncan Smith voted with the Government. Tagged migration (area 11, hidden, never campaigned), but the substance is trafficking (area 12). Because it is inseparable from the small-boats policy and even its champions split on the amendment in lieu, I would leave it off; if you want the anti-trafficking vote recorded, our side would be NO.
- [ ] `1682` 2023-11-29 DPDI Bill: Government New Schedule 1 — the power to require banks to hand over benefit claimants' account data to detect welfare fraud, added at report stage without committee scrutiny (hence `1676`, Labour's re-committal motion, 209 / 275). 274 / 52: SNP against, Labour abstained. A privacy and civil-liberties vote under area 7's widened remit; CitizenGO has campaigned on digital ID, not on this. Leave out unless you want privacy votes tracked.
- [ ] `1663` 2023-10-25 Economic Activity of Public Bodies (Overseas Matters) Bill: Amendment 28 (SNP) — that nothing in the clause-4 "gagging clause" (public bodies may not even say they would boycott) should conflict with Article 10 freedom of expression or Article 9 freedom of religion under the Human Rights Act. 197 / 275. A genuine free-speech amendment to an anti-BDS Bill: the direction depends on which CitizenGO values you weigh, so it needs a deliberate decision rather than a tag.
- [ ] `1676` 2023-11-29 DPDI Bill: re-committal motion — procedural companion to 1682 above; decide together.

**Not ours (checked against the amendment or motion text):**

- [x] `1816` 2024-05-15 CJB NC59 — a ban on "ninja swords". (171 / 272.)
- [x] `1787` 2024-04-16 Tobacco and Vapes Bill: Second Reading — the generational ban; the "prostitution" tag was a same-debate speech. (383 / 67.)
- [x] `1683` 2023-11-29 DPDI Bill: Third Reading — the whole Bill. (269 / 31.)
- [x] `1681` 2023-11-29 DPDI Amendment 218 — leave out clause 87, direct marketing by parties for "democratic engagement". (194 / 275.)
- [x] `1680` 2023-11-29 DPDI Amendment 1 — a definition of "high risk processing". (198 / 275.)
- [x] `1679` 2023-11-29 DPDI Amendment 5 — automated-decision protections where a decision is "partly" automated. (195 / 273.)
- [x] `1678` 2023-11-29 DPDI Amendment 224 (SNP) — leave out clause 12 on automated decision-making. (37 / 279.)
- [x] `1677` 2023-11-29 DPDI Amendment 11 — special category data in employment. (200 / 276.)
- [x] `1667` 2023-11-15 King's Speech amendment (k) (Liberal Democrat) and `1666` amendment (h) (SNP: Gaza ceasefire) and `1665` amendment (r) (Labour: Israel and Palestine, humanitarian pauses) — the Middle East amendments; same-debate tags. (25 / 303; 125 / 293; 183 / 290.)
- [x] `1664` 2023-11-14 King's Speech amendment (m) (Labour) — OBR forecasts for fiscal events. (228 / 314.)
- [x] `1662` 2023-10-25 BDS Bill Amendment 7 (Swayne / Antoniazzi) — remove the clause naming Israel, the OPT and the Golan Heights as territories Ministers may never exempt. Foreign policy. (207 / 269.)
- [x] `1661` 2023-10-25 BDS Bill Amendment 13 — exemption for decisions under a published human-rights policy. (197 / 276.)
- [x] `1660` 2023-10-25 BDS Bill Amendment 14 — Ministers' power to amend the Schedule by regulations. (200 / 273.)

## This Parliament and the last, 2020 to 2026 (50 still to review)

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
