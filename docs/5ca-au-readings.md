# Australian Parliament 5CA: readings to sign

Every reading below was DRAFTED by Claude on 9 October 2026 from the store
(au_divisions, au_votes) and the motion text Hansard printed before each
division. None is signed, so `tools/au_5ca.py` places nobody yet: every
sheet in data/5ca/au-5ca-*.csv is an evidence list ending "NO SIGNED
READINGS".

Aye is written `yea:`, No `nay:`. A PAIR places nobody: Hansard does not say
which side each partner was on. Most Senate divisions on our ground are on
whether a private senator's bill may be introduced or restored to the Notice
Paper, not on its merits; those are drafted at +/-1.

**How to sign.** Tick `[x]` on each reading you accept as drafted, then run the tool with `--sign-from-doc` (it deletes those entries' `draft: true` lines in `config/au_stance.yaml` and stamps `signed:`). To change a value, edit `config/au_stance.yaml` first and leave the box empty; to strike a reading, write `placeable: false` and a `reason:`. Nothing unticked places anyone.

## Divisions

### [ ] `senate-2025-07-31-13` Sex Discrimination Amendment (Restoring Biological Definitions) Bill 2025; First Reading: The question is that general business notion of motion No. 68 standing in the name of Senators Antic and Canav

- **When / result:** 2025-07-31; Ayes 25, Noes 36, pairs 6
- **A Aye means:** For introducing the Sex Discrimination Amendment (Restoring Biological Definitions) Bill 2025 (Senators Antic and Canavan): letting it be read a first time.
- **Lobbies:** Aye: Liberal Party 18, Pauline Hanson's One Nation Party 3, National Party 2, United Australia Party 1, Liberal National Party 1. No: Australian Labor Party 23, Australian Greens 10, Independent 3. Paired (side not published): Australian Labor Party 6, Liberal Party 3, National Party 1, Liberal National Party 1, Country Liberal Party 1.
- **Proposed direction:** Aye +1 (Voted to let the bill restoring biological definitions of sex into the Sex Discrimination Act be introduced.); No -1 (Voted to refuse the bill restoring biological definitions of sex its introduction.)
- **Flag for you:** A vote on whether a private senator's bill may be introduced (or restored to the Notice Paper), not on its merits: drafted at +/-1. Refusing a first reading is unusual, so the vote is still a real signal.

### [ ] `senate-2026-06-29-5` Consideration of Legislation: The question is that notice of motion No. 532, standing in the name of Senator Hanson, be agreed to.

- **When / result:** 2026-06-29; Ayes 25, Noes 32, pairs 8
- **Motion:** I move:(1) That so much of the standing orders be suspended as would prevent this resolution having effect.(2) That the Sex Discrimination Amendment (Acknowledging Biological Reality) Bill 2024 be restored to the Notice Paper and consideration of the bill resume at the first reading stage.
- **A Aye means:** For suspending standing orders to restore the Sex Discrimination Amendment (Acknowledging Biological Reality) Bill 2024 (Senator Hanson) to the Notice Paper at first reading.
- **Lobbies:** Aye: Liberal Party 16, Pauline Hanson's One Nation Party 4, National Party 2, United Australia Party 1, Liberal National Party 1, Independent 1. No: Australian Labor Party 22, Australian Greens 10. Paired (side not published): Australian Labor Party 8, Liberal Party 5, National Party 1, Liberal National Party 1, Country Liberal Party 1.
- **Proposed direction:** Aye +1 (Voted to restore the bill acknowledging biological sex in the Sex Discrimination Act to the Notice Paper.); No -1 (Voted against restoring the bill acknowledging biological sex to the Notice Paper.)
- **Flag for you:** A vote on whether a private senator's bill may be introduced (or restored to the Notice Paper), not on its merits: drafted at +/-1. Refusing a first reading is unusual, so the vote is still a real signal. Also a suspension of standing orders, which some senators oppose on principle.

### [ ] `senate-2026-07-01-16` Sex Discrimination Amendment (Restoring Common Sense and Recognising Biological Sex) Bill 2026; First Reading: The question is that the motion as moved by Senator Cash be agreed to.

- **When / result:** 2026-07-01; Ayes 21, Noes 30, pairs 11
- **Motion:** I move:That the following bill be introduced:A Bill for an Act to amend the Sex Discrimination Act 1984, and for related purposes. A division having been called and the bells being rung—
- **A Aye means:** For introducing the Sex Discrimination Amendment (Restoring Common Sense and Recognising Biological Sex) Bill 2026 (Senator Cash, Opposition).
- **Lobbies:** Aye: Liberal Party 14, Pauline Hanson's One Nation Party 3, National Party 2, United Australia Party 1, Country Liberal Party 1. No: Australian Labor Party 19, Australian Greens 10, Independent 1. Paired (side not published): Australian Labor Party 11, Liberal Party 7, Liberal National Party 2, National Party 1, Jacqui Lambie Network 1.
- **Proposed direction:** Aye +1 (Voted to let the bill recognising biological sex in the Sex Discrimination Act be introduced.); No -1 (Voted to refuse the bill recognising biological sex its introduction.)
- **Flag for you:** A vote on whether a private senator's bill may be introduced (or restored to the Notice Paper), not on its merits: drafted at +/-1. Refusing a first reading is unusual, so the vote is still a real signal. 11 pairs a side: 22 senators place nobody here.

### [ ] `senate-2026-09-15-8` Consideration of Legislation: The question is that general business notice of motion No. 713 standing in the name of Senator Cash be agreed to.

- **When / result:** 2026-09-15; Ayes 22, Noes 32, pairs 10
- **Motion:** I move:1. That so much of the standing orders be suspended as would prevent this resolution having effect.2. That the Sex Discrimination Amendment (Restoring Common Sense and Recognising Biological Sex) Bill 2026 be restored to the Notice Paper and consideration of the bill resume at the first reading stage.
- **A Aye means:** For suspending standing orders to restore Senator Cash's Restoring Common Sense and Recognising Biological Sex Bill 2026 to the Notice Paper at first reading.
- **Lobbies:** Aye: Liberal Party 14, Pauline Hanson's One Nation Party 4, United Australia Party 1, National Party 1, Liberal National Party 1, Country Liberal Party 1. No: Australian Labor Party 21, Australian Greens 9, Independent 1, Australia's Voice 1. Paired (side not published): Australian Labor Party 9, Liberal Party 7, National Party 2, Liberal National Party 1, Australian Greens 1.
- **Proposed direction:** Aye +1 (Voted to restore the bill recognising biological sex to the Notice Paper.); No -1 (Voted against restoring the bill recognising biological sex to the Notice Paper.)
- **Flag for you:** A vote on whether a private senator's bill may be introduced (or restored to the Notice Paper), not on its merits: drafted at +/-1. Refusing a first reading is unusual, so the vote is still a real signal.

### [ ] `senate-2026-03-31-8` Community Affairs References Committee; Reference: The question is that business of the Senate notice of motion No. 1 be agreed to.

- **When / result:** 2026-03-31; Ayes 19, Noes 41, pairs None
- **Motion:** I move:That the following matter be referred to the Community Affairs References Committee for inquiry and report by 2 November 2026:The suitability of current Commonwealth Government guidelines regarding gender dysphoria for minors, with particular reference to:(a) the science behind medical intervention;(b) alternative treatments including counselling;(c) international trends in treatment;(d) lived experience of transitioners;(e) other reviews that may be underway or recently completed; and(f) any other related matters.
- **A Aye means:** For referring the Commonwealth's guidelines on gender dysphoria in minors to the Community Affairs References Committee: the science of medical intervention, alternatives such as counselling, international trends, and detransitioners' experience.
- **Lobbies:** Aye: Liberal Party 9, Pauline Hanson's One Nation Party 4, National Party 2, Liberal National Party 2, United Australia Party 1, Country Liberal Party 1. No: Australian Labor Party 23, Australian Greens 10, Liberal Party 6, Independent 2.
- **Proposed direction:** Aye +1 (Voted for a Senate inquiry into gender medicine for minors (science, counselling, detransitioners).); No -1 (Voted against a Senate inquiry into gender medicine for minors.)
- **Flag for you:** An inquiry, not a law: drafted at +/-1. Six Liberals voted No with Labor and the Greens, so the vote does tell members apart.

### [ ] `senate-2025-11-03-3` Fair Work Amendment (Baby Priya's) Bill 2025; In Committee: The question is that amendment (1) on sheet 3479 be agreed to.

- **When / result:** 2025-11-03; Ayes 7, Noes 39, pairs None
- **Motion:** I move my amendment on sheet 3479:(1) Schedule 1, item 5, page 5 (after line 16), at the end of section 333X, add: Exclusions(7) Despite subsection (1), this section does not apply if the child:(a) is stillborn because of an intentional termination (other than by child-birth) of a pregnancy; or(b) dies because of an intentional termination (other than by child-birth) of a pregnancy (whether the death occurs before, during or after delivery).Note: An intentional termination of pregnancy includes, for example, a medical termination involving the administration of a drug.
- **A Aye means:** For the amendment to the Fair Work Amendment (Baby Priya's) Bill 2025: the new leave for parents of a stillborn child would not apply where the stillbirth or death followed an intentional termination of pregnancy.
- **Lobbies:** Aye: Pauline Hanson's One Nation Party 3, Liberal Party 2, United Australia Party 1, Country Liberal Party 1. No: Australian Labor Party 21, Australian Greens 10, National Party 2, Liberal Party 2, Independent 2, Liberal National Party 1, Australia's Voice 1.
- **Proposed direction:** Aye +1 (Voted to keep abortion out of the stillbirth leave entitlement.); No no value (-)
- **Flag for you:** Uncertain: the amendment denies bereavement leave to parents after an abortion, which CitizenGO may not want to be seen backing. Drafted Aye +1 with the No side at no value (39 of 46 voted No, including most of the Coalition, so a No tells no member apart). Strike it if it is off message.

### [ ] `house-2026-01-20-5` Combatting Antisemitism, Hate and Extremism (Criminal and Migration Laws) Bill 2026; Consideration in Detail: The question is that the bill, as amended, be agreed to.

- **When / result:** 2026-01-20; Ayes 116, Noes 7, pairs None
- **Motion:** I move amendments (1) to (3) on sheet 1 and the amendment on sheet 2 as circulated in my name together:(1) Schedule 1, item 7, page 4 (line 31), omit subparagraph 80.2DA(1)(b)(ii), substitute:(ii) a spiritual leader who provides religious instruction or religious pastoral care; or(iia) a leader of a prohibited hate group (within the meaning of Part 5.3B); or(2) Schedule 1, item 7, page 5 (line 12), omit subparagraph 80.2DA(2)(b)(ii), substitute:(ii) a spiritual leader who provides religious instruction or religious pastoral care; or(iia) a leader of a prohibited hate group (within the meaning of Part 5.3B); or(3) Schedule 2, page 43 (after line 28), after item 2, insert:2A Paragraph 5C(1)(d)Omit "there is a risk", substitute "there is a reasonable risk"._____SHEET 2(1) Schedule 1, item 13, page 13 (after line 31), at the end of section 114A.3, add:(7) In this section, a reference to race
- **A Aye means:** For agreeing to the bill, as amended, at consideration in detail: new hate-speech and hate-group offences, with aggravation for 'spiritual leaders' who incite.
- **Lobbies:** Aye: Australian Labor Party 85, Liberal Party 16, Liberal National Party 7, Independent 7, National Party 1. No: Independent 2, Pauline Hanson's One Nation Party 1, National Party 1, Liberal National Party 1, Katter's Australian Party 1, Centre Alliance 1.
- **Proposed direction:** Aye -1 (Voted for the hate speech and hate group offences bill.); No no value (-)
- **Flag for you:** Uncertain direction. CitizenGO opposed hate-speech laws in Ireland and Scotland; this bill adds offences aimed at preachers ('a spiritual leader who provides religious instruction'). But it is framed against antisemitism, and the No lobby is a mix (One Nation, Katter, Nationals, independents). Drafted Aye -1 only, No at no value. Strike it, or sign the No side too, as you judge.

### [ ] `senate-2026-01-20-22` Combatting Antisemitism, Hate and Extremism (Criminal and Migration Laws) Bill 2026; Limitation of Debate: The question is that the remaining stages of the bill be agreed to and the bill be now passed

- **When / result:** 2026-01-20; Ayes 38, Noes 22, pairs None
- **A Aye means:** For passing the bill (remaining stages under a limitation of debate).
- **Lobbies:** Aye: Australian Labor Party 28, Liberal Party 10. No: Australian Greens 10, Pauline Hanson's One Nation Party 3, National Party 3, Independent 2, United Australia Party 1, Liberal Party 1, Liberal National Party 1, Australia's Voice 1.
- **Proposed direction:** Aye -1 (Voted to pass the hate speech and hate group offences bill.); No no value (-)
- **Flag for you:** As for the House vote: the No lobby joins the Greens (opposing for the opposite reasons) with One Nation, the Nationals and UAP, so a No tells no member's direction apart. Drafted Aye -1 only.

### [ ] `house-2026-09-10-3` Online Safety Amendment (Strengthening Enforcement for the Social Media Minimum Age) Bill 2026; Consideration of Senate Message: The question is that the Senate amendments be agreed to.

- **When / result:** 2026-09-10; Ayes 95, Noes 37, pairs None
- **Motion:** I move:That the amendments be agreed to.Australia's social media minimum age law was the first of its kind in the world, and we were clear from the start that we would need to be flexible as that law was implemented because, as lawmakers, we have to be as agile as the technology we are trying to protect our kids from. It's clear to most Australians that social media companies are pulling out every trick in the global big tech playbook to do the bare minimum. Today the Albanese government has sent a clear message to big tech. If you want to do business in Australia, you must follow Australian laws.I thank the senators and members who worked constructively with the government to strengthen the eSafety Commissioner's powers to hold these companies to account. Australian families will remember that you stood with them on the right side of history. Australian families will not forget the sena
- **A Aye means:** For agreeing to the Senate amendments to the Online Safety Amendment (Strengthening Enforcement for the Social Media Minimum Age) Bill 2026.
- **Lobbies:** Aye: Australian Labor Party 86, Independent 8, Australian Greens 1. No: Liberal Party 16, National Party 10, Liberal National Party 10, Pauline Hanson's One Nation Party 1.
- **Proposed direction:** none -- CitizenGO's position on the under-16 social media ban (child protection against age verification, digital ID and speech) is not written down in the repo. No direction proposed; the Coalition voted No on enforcement grounds, Labor Aye.

9 entries.
