# Oireachtas 5CA: readings to sign

Every reading below was DRAFTED by Claude on 9 October 2026 from the store
(ie_divisions, ie_votes, ie_sponsors) and the Dail debate records of the day,
read for the question put and the tellers. None is signed, so
`tools/ie_5ca.py` places nobody yet: every sheet in data/5ca/ie-5ca-*.csv is
an evidence list ending "NO SIGNED READINGS".

Ta is stored as 'Yes' and written `yea:`; Nil as 'No', `nay:`. Staon (a
recorded abstention) never places anyone. The store holds the 34th Dail and
the 27th Seanad only (from December 2024 and February 2025): the safe access
zones Act and the hate offences votes were in the 33rd Dail and are not in it,
so they cannot be read here.

**How to sign.** Tick `[x]` on each reading you accept as drafted, then run the tool with `--sign-from-doc` (it deletes those entries' `draft: true` lines in `config/ie_stance.yaml` and stamps `signed:`). To change a value, edit `config/ie_stance.yaml` first and leave the box empty; to strike a reading, write `placeable: false` and a `reason:`. Nothing unticked places anyone.

## Divisions

### [ ] `dail/34/2026-06-17/vote_149` Health (Abolition of Three Day Wait Rule) (Amendment) Bill 2026: Second Stage (Resumed) [Private Members]: Question put:

- **When / result:** 2026-06-17; Carried (Tá 86, Níl 70, Staon 0)
- **Motion:** Second Stage of the Health (Abolition of Three Day Wait Rule) (Amendment) Bill 2026 (David Cullinane, Sinn Fein): "That the Bill be now read a Second Time." The Bill amends the Health (Regulation of Termination of Pregnancy) Act 2018 to abolish the mandatory three-day wait for an abortion. Deferred division of 16 June, taken 17 June.
- **A Ta (Yes) means:** For giving the Bill a Second Reading: abolishing the three-day wait before an abortion.
- **Lobbies:** Tá: Sinn Féin 35, Social Democrats 12, Fianna Fáil 12, Fine Gael 11, Labour Party 10, People Before Profit-Solidarity 3, Independent 2, Green Party 1. Níl: Fianna Fáil 30, Fine Gael 23, Independent 12, Independent Ireland 3, Aontú 2.
- **Tellers:** Tá, Deputies Pádraig Mac Lochlainn and David Cullinane; Níl, Deputies Peadar Tóibín and Carol Nolan.
- **Proposed direction:** Ta (Yes) -2 (Voted to give a Second Reading to the Bill abolishing the three-day wait before an abortion.); Nil (No) +2 (Voted against the Bill abolishing the three-day wait before an abortion.)
- **Flag for you:** Carried 86-70 with Fianna Fail (12 Ta, 30 Nil) and Fine Gael (11 Ta, 23 Nil) split: the members this sheet exists to find. Tellers confirm the sides: Ta Mac Lochlainn and Cullinane (SF), Nil Toibin and Nolan.

### [ ] `dail/34/2026-05-13/vote_110` Reproductive Rights (Amendment) Bill 2026: Second Stage (Resumed) [Private Members]: Question put: "That the Bill be now read a Second Time."

- **When / result:** 2026-05-13; Lost (Tá 30, Níl 85, Staon 36)
- **Motion:** Second Stage of the Reproductive Rights (Amendment) Bill 2026 (Holly Cairns, Social Democrats): "That the Bill be now read a Second Time." The Bill enacts the O'Shea review's recommendations: terminations for medical reasons, removal of the three-day wait, and ending the criminalisation of doctors.
- **A Ta (Yes) means:** For giving the Bill a Second Reading: widening the 2018 abortion law.
- **Lobbies:** Tá: Social Democrats 11, Labour Party 10, People Before Profit-Solidarity 3, Independent 2, Fine Gael 2, Green Party 1, Fianna Fáil 1. Níl: Fianna Fáil 40, Fine Gael 30, Independent 9, Independent Ireland 4, Aontú 2. Staon: Sinn Féin 33, Fianna Fáil 3.
- **Tellers:** Tá, Deputies Holly Cairns and Pádraig Rice; Níl, Deputies Peadar Tóibín and Paul Lawless.
- **Proposed direction:** Ta (Yes) -2 (Voted to give a Second Reading to the Bill widening the 2018 abortion law (O'Shea recommendations).); Nil (No) +2 (Voted against the Bill widening the 2018 abortion law.)
- **Flag for you:** Lost 30-85 with 36 Staon (33 Sinn Fein abstained). A Staon places nobody; Sinn Fein's abstention here and Ta on the three-day wait a month later are both on their rows as evidence.

### [ ] `dail/34/2025-12-17/vote_205` Health (Regulation of Termination of Pregnancy) (Amendment) Bill 2023: Restoration to Order Paper (Resumed): Question again put:

- **When / result:** 2025-12-17; Lost (Tá 71, Níl 73, Staon 4)
- **Motion:** Motion (Paul Murphy, PBP): that the Health (Regulation of Termination of Pregnancy) (Amendment) Bill 2023, which lapsed on the dissolution of the 33rd Dail, be restored to the Order Paper at Committee Stage. Question again put after an electronic division.
- **A Ta (Yes) means:** For restoring the lapsed 2023 Bill amending the abortion Act to the Order Paper.
- **Lobbies:** Tá: Sinn Féin 35, Social Democrats 10, Labour Party 7, Fine Gael 7, Fianna Fáil 5, People Before Profit-Solidarity 3, Independent 2, Green Party 1, 100% RDR 1. Níl: Fianna Fáil 35, Fine Gael 23, Independent 10, Independent Ireland 3, Aontú 2. Staon: Fine Gael 2, Fianna Fáil 2.
- **Tellers:** Tá, Deputies Paul Murphy and Ruth Coppinger; Níl, Deputies Danny Healy-Rae and Paul Lawless.
- **Proposed direction:** Ta (Yes) -1 (Voted to restore the lapsed Bill amending the abortion Act to the Order Paper.); Nil (No) +1 (Voted against restoring the lapsed Bill amending the abortion Act.)
- **Flag for you:** A restoration motion, procedure in form: drafted at +/-1. Lost 71-73-4; 5 Fianna Fail and 7 Fine Gael voted Ta.

### [ ] `dail/34/2025-05-14/vote_58` Parental Choice in Education: Motion (Resumed) [Private Members]: Amendment put:

- **When / result:** 2025-05-14; Carried (Tá 84, Níl 65, Staon 0)
- **Motion:** Government amendment No. 1 to the Social Democrats' 'Parental Choice in Education' motion (Jen Cummins): delete the motion and substitute the Government's text. The original motion called for all new schools under non-religious patronage, faith formation outside the school day, and repeal of section 37.1 of the Employment Equality Act; the Government's text keeps both faith-based and multi-denominational choice and continues the reconfiguration process.
- **A Ta (Yes) means:** For replacing the Social Democrats' motion with the Government's text.
- **Lobbies:** Tá: Fianna Fáil 44, Fine Gael 32, Independent 8. Níl: Sinn Féin 34, Labour Party 11, Social Democrats 8, Independent 4, Independent Ireland 3, People Before Profit-Solidarity 2, Aontú 2, Green Party 1.
- **Tellers:** Tá, Deputies Mary Butler and Emer Currie; Níl, Deputies Jen Cummins and Cian O'Callaghan.
- **Proposed direction:** evidence only, never places -- A Government-versus-opposition division: the Government's text against the opposition's, whipped on both sides. Aontu voted Nil with the Social Democrats and Sinn Fein, for opposition reasons; a Nil does not mean support for removing faith formation, nor a Ta support for denominational schools. The motion is evidence of who carried the secular text, not a direction.

### [ ] `dail/34/2025-05-14/vote_59` Parental Choice in Education: Motion (Resumed) [Private Members]: Question put: "That the motion, as amended, be agreed to."

- **When / result:** 2025-05-14; Carried (Tá 87, Níl 62, Staon 0)
- **Motion:** "That the motion, as amended, be agreed to": the Government's text on parental choice in education.
- **A Ta (Yes) means:** For the motion as amended by the Government.
- **Lobbies:** Tá: Fianna Fáil 44, Fine Gael 32, Independent 8, Independent Ireland 3. Níl: Sinn Féin 34, Labour Party 11, Social Democrats 8, Independent 4, People Before Profit-Solidarity 2, Aontú 2, Green Party 1.
- **Tellers:** Tá, Deputies Mary Butler and Emer Currie; Níl, Deputies Jen Cummins and Cian O'Callaghan.
- **Proposed direction:** evidence only, never places -- A Government-versus-opposition division: the Government's text against the opposition's, whipped on both sides. Same lobbies as the amendment before it (Aontu in the Nil lobby).

### [ ] `dail/34/2026-07-08/vote_177` Civil Liability (Child Sexual Abuse Proceedings Against Unincorporated Bodies of Persons) Bill 2025: Second Stage (Resumed) [Private Members]: Amendment put:

- **When / result:** 2026-07-08; Carried (Tá 80, Níl 65, Staon 0)
- **Motion:** Government amendment to the Second Stage of the Civil Liability (Child Sexual Abuse Proceedings Against Unincorporated Bodies of Persons) Bill 2025 (Ivana Bacik, Labour): read the Bill a second time 'this day six months' to consider its legal and policy implications. The Bill lets abuse survivors sue unincorporated bodies (religious congregations among them) and reach associated trusts' assets.
- **A Ta (Yes) means:** For deferring the Bill six months (the Government's timed amendment).
- **Lobbies:** Tá: Fianna Fáil 42, Fine Gael 32, Independent 6. Níl: Sinn Féin 37, Social Democrats 10, Labour Party 9, Independent 3, People Before Profit-Solidarity 2, Independent Ireland 2, Aontú 2.
- **Tellers:** Tá, Deputies Mary Butler and John Clendennen; Níl, Deputies Ivana Bacik and Duncan Smith.
- **Proposed direction:** evidence only, never places -- A Government-versus-opposition division: the Government's text against the opposition's, whipped on both sides. A timed amendment on a redress bill; abuse redress is not a CitizenGO position either way, and the vote tells no member's stance on our ground apart.
- **Flag for you:** If the reach into religious congregations' trust assets is a freedom-of-religion concern for CitizenGO, say so and it can be read again.

### [ ] `seanad/27/2025-11-05/vote_3` Child Trafficking and Child Sexual Exploitation Material (Amendment) Bill 2022: Report Stage: Question put: "That the Bill be received for final consideration."

- **When / result:** 2025-11-05; Lost (Tá 13, Níl 28, Staon None)
- **Motion:** Report Stage of the Child Trafficking and Child Sexual Exploitation Material (Amendment) Bill 2022 (Eileen Flynn): "That the Bill be received for final consideration." The Bill renames 'child pornography' as 'child sexual abuse material' in the statute book.
- **A Ta (Yes) means:** For moving the Bill to its final stage.
- **Lobbies:** Tá: Independent 5, Sinn Féin 4, Labour Party 2, Green Party 1, Aontú 1. Níl: Fine Gael 15, Fianna Fáil 12, Independent 1.
- **Tellers:** Tá, Senators Eileen Flynn and Lynn Ruane; Níl, Senators Garret Ahearn and Paul Daly..
- **Proposed direction:** evidence only, never places -- Terminology: the Bill renames an offence, and the Government opposed it on drafting grounds (lost 13-28). Neither lobby is for or against CitizenGO's ground.

## Bills (sponsorship)

### [ ] `2026/47` Health (Abolition of Three Day Wait Rule) (Amendment) Bill 2026

- **When / result:** sponsors David Cullinane; status Current; areas [1]
- **Proposed direction:** sponsor -2 (Sponsored the Bill abolishing the three-day wait before an abortion.)

### [ ] `2026/40` Reproductive Rights (Amendment) Bill 2026

- **When / result:** sponsors Holly Cairns; status Defeated; areas [1]
- **Proposed direction:** sponsor -2 (Sponsored the Bill widening the 2018 abortion law.)

### [ ] `2026/10` Health (Regulation of Termination of Pregnancy) (Amendment) Bill 2026

- **When / result:** sponsors Paul Murphy, Richard Boyd Barrett, Ruth Coppinger; status Current; areas [1]
- **Proposed direction:** sponsor -2 (Sponsored the Bill abolishing the three-day wait for abortion on request.)

### [ ] `2024/50` Voluntary Assisted Dying Bill 2024

- **When / result:** sponsors Gino Kenny; status Current; areas [2]
- **Proposed direction:** sponsor -2 (Sponsored the Bill legalising assisted dying.)

### [ ] `2026/92` Non-Binary and Intersex Recognition Bill 2026

- **When / result:** sponsors Paul Murphy, Richard Boyd Barrett, Ruth Coppinger; status Current; areas [1, 5]
- **Proposed direction:** sponsor -2 (Sponsored the Bill recognising a non-binary gender in law (X markers, Gender Recognition Act).)

### [ ] `2018/39` Prohibition of Conversion Therapies Bill 2018

- **When / result:** sponsors Alice-Mary Higgins, Aodhán Ó Ríordáin, Catherine Ardagh, Colette Kelleher, David P.B. Norris, Fintan Warfield, Frances Black, Gerard P. Craughwell, Grace O'Sullivan, Ivana Bacik, Jerry Buttimer, Joan Freeman, Kevin Humphreys, Lynn Ruane, Máire Devine, Niall Ó Donnghaile, Paul Gavan, Pádraig Mac Lochlainn, Rose Conway-Walsh, Victor Boyhan; status Lapsed; areas [4, 5]
- **Proposed direction:** sponsor -2 (Sponsored the 2018 Bill banning 'conversion therapy' as defined by gender identity and expression.)

### [ ] `2025/77` Gender Recognition (Amendment) (Prisons) Bill 2025

- **When / result:** sponsors Paul Lawless, Peadar Tóibín; status Current; areas [5]
- **Proposed direction:** sponsor +2 (Sponsored the Bill providing single-sex accommodation in prisons.)

### [ ] `2026/77` Protection of Children (Online Age Verification) Bill 2026

- **When / result:** sponsors Aidan Davitt, Aubrey McCarthy, Diarmuid Wilson, Gerard P. Craughwell, Joe Conway, Michael McDowell, Rónán Mullen, Sarah O'Reilly, Sharon Keogan; status Current; areas [6, 7]
- **Proposed direction:** sponsor +1 (Sponsored the Bill requiring age verification for online pornography.)

### [ ] `2024/57` Protection of Children (Online Age Verification) Bill 2024

- **When / result:** sponsors Aidan Davitt, Diarmuid Wilson, Erin McGreehan, Gerard P. Craughwell, Michael McDowell, Rónán Mullen, Sharon Keogan; status Lapsed; areas [6, 7]
- **Proposed direction:** sponsor +1 (Sponsored the Bill requiring age verification for online pornography.)

16 entries.
