# US Congress 5CA: readings to sign

Every reading below was DRAFTED by Claude on 9 October 2026 from the store
(us_divisions, us_votes, us_bills, us_cosponsors) and the amendment purposes
the House printed. None is signed, so `tools/us_5ca.py` places nobody yet:
every sheet in data/5ca/us-5ca-*.csv is an evidence list ending "NO SIGNED
READINGS". The direction of a vote is your judgement, never the tool's.

Scale: +2 / -2 a vote or bill squarely on our ground; +1 / -1 a weaker or
procedural signal (a cloture vote, a motion to proceed, a cosponsorship);
"no value" on a side means its lobby tells no member apart. A motion to
recommit in the 119th House carries no instructions: it is the minority's
last procedural vote against the bill, so it is drafted as evidence only.

**How to sign.** Tick `[x]` on each reading you accept as drafted, then run the tool with `--sign-from-doc` (it deletes those entries' `draft: true` lines in `config/us_stance.yaml` and stamps `signed:`). To change a value, edit `config/us_stance.yaml` first and leave the box empty; to strike a reading, write `placeable: false` and a `reason:`. Nothing unticked places anyone.

## Divisions

### [ ] `house-119-1-12` On Passage: Protection of Women and Girls in Sports Act of 2025

- **When / result:** 2025-01-14; Passed 218-206
- **Motion:** Protection of Women and Girls in Sports Act
- **A Yea means:** For passing the bill: Title IX barred from letting males take part in athletics designated for women or girls, sex defined by reproductive biology and genetics at birth.
- **Lobbies:** Yea: R 216, D 2. Nay: D 206.
- **Proposed direction:** Yea +2 (Voted to pass the Protection of Women and Girls in Sports Act: women's and girls' school sport kept for females.); Nay -2 (Voted against keeping women's and girls' school sport for females.)

### [ ] `house-119-1-11` On Motion to Recommit: Protection of Women and Girls in Sports Act of 2025

- **When / result:** 2025-01-14; Failed 208-218
- **Motion:** Protection of Women and Girls in Sports Act
- **A Yea means:** For sending H.R. 28 back to committee, i.e. against the bill.
- **Lobbies:** Yea: D 208. Nay: R 217, D 1.
- **Proposed direction:** evidence only, never places -- A motion to recommit in the 119th House carries no instructions: it is the minority's last procedural vote to send the bill back, cast on party lines. The passage vote the same day carries the reading; this one would only count the same members twice.

### [ ] `senate-119-1-100` On Cloture on the Motion to Proceed S. 9: Protection of Women and Girls in Sports Act of 2025

- **When / result:** 2025-03-03; Cloture on the Motion to Proceed Rejected 51-45
- **Motion:** Motion to Invoke Cloture: Motion to Proceed to S. 9 | A bill to provide that for purposes of determining compliance with title IX of the Education Amendments of 1972 in athletics, sex shall be recognized based solely on a person's reproductive biology and genetics at birth.
- **A Yea means:** For invoking cloture on the motion to proceed to S. 9: ending the filibuster so the Senate could take the bill up. 60 needed; it failed.
- **Lobbies:** Yea: R 51. Nay: D 43, I 2.
- **Proposed direction:** Yea +2 (Voted to let the Senate take up the Protection of Women and Girls in Sports Act (cloture on the motion to proceed).); Nay -2 (Voted to keep the Protection of Women and Girls in Sports Act from the Senate floor (against cloture).)
- **Flag for you:** A cloture vote on a motion to proceed is procedure in form, but it was the Senate's only vote on S. 9 and the filibuster is how the bill died. Drafted at +/-2 as the de facto vote; +/-1 if you read cloture as procedure.

### [ ] `house-119-1-27` On Passage: Born-Alive Abortion Survivors Protection Act

- **When / result:** 2025-01-23; Passed 217-204
- **Motion:** Born-Alive Abortion Survivors Protection Act
- **A Yea means:** For passing the bill: a child born alive after an attempted abortion must receive the care any other child of that gestational age would, and be admitted to hospital.
- **Lobbies:** Yea: R 216, D 1. Nay: D 204.
- **Proposed direction:** Yea +2 (Voted to pass the Born-Alive Abortion Survivors Protection Act.); Nay -2 (Voted against requiring care for children born alive after an attempted abortion.)

### [ ] `house-119-1-26` On Motion to Recommit: Born-Alive Abortion Survivors Protection Act

- **When / result:** 2025-01-23; Failed 205-216
- **Motion:** Born-Alive Abortion Survivors Protection Act
- **A Yea means:** For sending H.R. 21 back to committee, i.e. against the bill.
- **Lobbies:** Yea: D 205. Nay: R 216.
- **Proposed direction:** evidence only, never places -- A motion to recommit in the 119th House carries no instructions: it is the minority's last procedural vote to send the bill back, cast on party lines. The passage vote the same day carries the reading; this one would only count the same members twice.

### [ ] `senate-119-1-11` On Cloture on the Motion to Proceed S. 6: Born-Alive Abortion Survivors Protection Act

- **When / result:** 2025-01-22; Cloture on the Motion to Proceed Rejected 52-47
- **Motion:** Motion to Invoke Cloture: Motion to Proceed to S.6 | A bill to amend title 18, United States Code, to prohibit a health care practitioner from failing to exercise the proper degree of care in the case of a child who survives an abortion or attempted abortion.
- **A Yea means:** For invoking cloture on the motion to proceed to S. 6 (Born-Alive). 60 needed; it failed 52-47.
- **Lobbies:** Yea: R 52. Nay: D 45, I 2.
- **Proposed direction:** Yea +2 (Voted to let the Senate take up the Born-Alive Abortion Survivors Protection Act (cloture).); Nay -2 (Voted to keep the Born-Alive Abortion Survivors Protection Act from the Senate floor (against cloture).)
- **Flag for you:** As for S. 9: cloture on the motion to proceed, drafted at +/-2 as the Senate's only vote on the bill.

### [ ] `house-119-1-351` On Passage: Protect Children’s Innocence Act

- **When / result:** 2025-12-17; Passed 216-211
- **Motion:** Protect Children’s Innocence Act
- **A Yea means:** For passing the Protect Children's Innocence Act: a federal crime to perform procedures or give hormones to a minor to change the body to correspond to a sex other than the biological sex.
- **Lobbies:** Yea: R 213, D 3. Nay: D 207, R 4.
- **Proposed direction:** Yea +2 (Voted to pass the Protect Children's Innocence Act (criminalising gender transition procedures on minors).); Nay -2 (Voted against the Protect Children's Innocence Act.)
- **Flag for you:** Four Republicans voted Nay and three Democrats Yea; whether the criminal-law route (rather than funding) is CitizenGO's ask is your call. Drafted +/-2.

### [ ] `house-119-1-350` On Motion to Recommit: Protect Children’s Innocence Act

- **When / result:** 2025-12-17; Failed 210-218
- **Motion:** Protect Children’s Innocence Act
- **A Yea means:** For sending H.R. 3492 back to committee, i.e. against the bill.
- **Lobbies:** Yea: D 210. Nay: R 218.
- **Proposed direction:** evidence only, never places -- A motion to recommit in the 119th House carries no instructions: it is the minority's last procedural vote to send the bill back, cast on party lines. The passage vote the same day carries the reading; this one would only count the same members twice.

### [ ] `house-119-1-362` On Passage: Do No Harm in Medicaid Act

- **When / result:** 2025-12-18; Passed 215-201
- **Motion:** Do No Harm in Medicaid Act
- **A Yea means:** For passing the Do No Harm in Medicaid Act: no federal Medicaid payment for gender transition procedures for under-18s.
- **Lobbies:** Yea: R 211, D 4. Nay: D 201.
- **Proposed direction:** Yea +2 (Voted to end federal Medicaid funding of gender transition procedures for minors.); Nay -2 (Voted to keep federal Medicaid funding of gender transition procedures for minors.)

### [ ] `house-119-1-361` On Motion to Recommit: Do No Harm in Medicaid Act

- **When / result:** 2025-12-18; Failed 204-212
- **Motion:** Do No Harm in Medicaid Act
- **A Yea means:** For sending H.R. 498 back to committee, i.e. against the bill.
- **Lobbies:** Yea: D 204. Nay: R 212.
- **Proposed direction:** evidence only, never places -- A motion to recommit in the 119th House carries no instructions: it is the minority's last procedural vote to send the bill back, cast on party lines. The passage vote the same day carries the reading; this one would only count the same members twice.

### [ ] `house-119-1-245` On Agreeing to the Amendment: Streamlining Procurement for Effective Execution and Delivery and National Defense Authorization Act for Fiscal Year 2026 (Norman 

- **When / result:** 2025-09-10; Agreed to 221-210
- **Motion:** An amendment numbered 13 printed in Part A of House Report 119-255 to prohibit the provision of gender transition procedures, including surgery or medication, through the Exceptional Family Medical Program. | Amendment prohibits the provision of gender transition procedures, including surgery or medication, through the Exceptional Family Medical Program.
- **A Yea means:** For the Norman amendment: no gender transition procedures (surgery or medication) through the Exceptional Family Member Program.
- **Lobbies:** Yea: R 217, D 4. Nay: D 209, R 1.
- **Proposed direction:** Yea +2 (Voted to bar gender transition procedures through the military's Exceptional Family Member Program.); Nay -2 (Voted against barring gender transition procedures through the Exceptional Family Member Program.)

### [ ] `house-119-1-246` On Agreeing to the Amendment: Streamlining Procurement for Effective Execution and Delivery and National Defense Authorization Act for Fiscal Year 2026 (Mace of

- **When / result:** 2025-09-10; Agreed to 221-207
- **Motion:** An amendment numbered 14 printed in Part A of House Report 119-255 to prohibit DoD from covering or furnishing gender-related medical treatment under TRICARE. | Amendment prohibits the Department of Defense from covering or furnishing gender-related medical treatment under TRICARE.
- **A Yea means:** For the Mace amendment: DoD may not cover or furnish gender-related medical treatment under TRICARE.
- **Lobbies:** Yea: R 215, D 6. Nay: D 205, R 2.
- **Proposed direction:** Yea +2 (Voted to end TRICARE coverage of gender-related medical treatment.); Nay -2 (Voted to keep TRICARE coverage of gender-related medical treatment.)

### [ ] `house-119-1-247` On Agreeing to the Amendment: Streamlining Procurement for Effective Execution and Delivery and National Defense Authorization Act for Fiscal Year 2026 (Mace of

- **When / result:** 2025-09-10; Agreed to 227-201
- **Motion:** An amendment numbered 15 printed in Part A of House Report 119-255 to prohibit the Superintendent of a Service Academy from allowing a cadet or midshipman who is male from participating in an athletic program or activity that is designated exclusively for females. | Amendment prohibits the Superintendent of a Service Academy from allowing a cadet or midshipman who is male from participating in an athletic program or activity that is designated exclusively for females.
- **A Yea means:** For the Mace amendment: no male cadet or midshipman in a service academy athletic programme designated for females.
- **Lobbies:** Yea: R 217, D 10. Nay: D 201.
- **Proposed direction:** Yea +2 (Voted to keep women's sport at the service academies for females.); Nay -2 (Voted against keeping women's sport at the service academies for females.)

### [ ] `house-119-1-248` On Agreeing to the Amendment: Streamlining Procurement for Effective Execution and Delivery and National Defense Authorization Act for Fiscal Year 2026 (Mace of

- **When / result:** 2025-09-10; Agreed to 221-210
- **Motion:** An amendment numbered 16 printed in Part A of House Report 119-255 to prohibit the Secretary of Defense from soliciting information through a form or survey regarding the gender identity of an individual, providing an option to indicate the sex or gender of an individual is something other than male or female, and requiring the Secretary reject a response other than male or female to a required question on a form or survey regarding sex or gender. | Amendment prohibits the Secretary of Defense from soliciting information through a form or survey regarding the gender identity of an individual, providing an option to indicate the sex or gender of an individual is something other than male or f
- **A Yea means:** For the Mace amendment: DoD forms may not ask about gender identity or offer a sex other than male or female.
- **Lobbies:** Yea: R 217, D 4. Nay: D 209, R 1.
- **Proposed direction:** Yea +1 (Voted to keep DoD forms to male and female, without gender identity questions.); Nay -1 (Voted to allow gender identity questions and non-binary options on DoD forms.)
- **Flag for you:** Drafted at +/-1: record-keeping, a weaker signal than the medical and sport votes beside it.

### [ ] `house-119-1-249` On Agreeing to the Amendment: Streamlining Procurement for Effective Execution and Delivery and National Defense Authorization Act for Fiscal Year 2026 (Mace of

- **When / result:** 2025-09-10; Agreed to 219-209
- **Motion:** An amendment numbered 17 printed in Part A of House Report 119-255 to prohibit individuals from accessing or using single-sex spaces on military installations which do not correspond to the biological sex of the individual. | Amendment prohibits individuals from accessing or using single-sex spaces on military installations which do not correspond to the biological sex of the individual.
- **A Yea means:** For the Mace amendment: single-sex spaces on military installations by biological sex.
- **Lobbies:** Yea: R 216, D 3. Nay: D 208, R 1.
- **Proposed direction:** Yea +2 (Voted to keep single-sex spaces on military installations by biological sex.); Nay -2 (Voted against single-sex spaces by biological sex on military installations.)

### [ ] `house-119-2-266` On Agreeing to the Amendment: National Defense Authorization Act for Fiscal Year 2027 (Boebert of Colorado Part A Amendment No. 18)

- **When / result:** 2026-07-21; Failed 212-217
- **Motion:** An amendment numbered 18 printed in Part A of House Report 119-755 to codify Executive Order 14183, which implements a ban on transgender service members by requiring all personnel to serve in accordance with their biological sex, citing military readiness and discipline. | Amendment sought to codify Executive Order 14183, which implements a ban on transgender service members by requiring all personnel to serve in accordance with their biological sex, citing military readiness and discipline.
- **A Yea means:** For the Boebert amendment: codify Executive Order 14183, every service member to serve according to biological sex (the transgender service ban). It failed 212-217.
- **Lobbies:** Yea: R 211, I 1. Nay: D 213, R 4.
- **Proposed direction:** Yea +1 (Voted to codify service by biological sex in the armed forces (EO 14183).); Nay -1 (Voted against codifying service by biological sex in the armed forces.)
- **Flag for you:** Military personnel policy rather than a core CitizenGO ask: drafted at +/-1. Four Republicans voted Nay; strike it (placeable: false) if it is off our ground.

### [ ] `house-119-2-267` On Agreeing to the Amendment: National Defense Authorization Act for Fiscal Year 2027 (Mace of South Carolina Part A Amendment No. 19)

- **When / result:** 2026-07-21; Agreed to 219-208
- **Motion:** An amendment numbered 19 printed in Part A of House Report 119-755 to prohibit gender related medical care under TRICARE and to prevent TRICARE from covering certain gender related medical procedures and treatments. | Amendment prohibits gender-related medical care under TRICARE and prevents TRICARE from covering certain gender-related medical procedures and treatments.
- **A Yea means:** For the Mace amendment: no gender-related medical care under TRICARE.
- **Lobbies:** Yea: R 213, D 5, I 1. Nay: D 207, R 1.
- **Proposed direction:** Yea +2 (Voted to end TRICARE coverage of gender-related medical care.); Nay -2 (Voted to keep TRICARE coverage of gender-related medical care.)

### [ ] `house-119-2-268` On Agreeing to the Amendment: National Defense Authorization Act for Fiscal Year 2027 (Mace of South Carolina Part A Amendment No. 20)

- **When / result:** 2026-07-21; Agreed to 221-203
- **Motion:** An amendment numbered 20 printed in Part A of House Report 119-755 to prohibit male participation in female sports at DoDEA schools. | Amendment prohibits male participation in female sports at Department of Defense Education Activity schools.
- **A Yea means:** For the Mace amendment: no male participation in female sports at DoD Education Activity schools.
- **Lobbies:** Yea: R 215, D 5, I 1. Nay: D 203.
- **Proposed direction:** Yea +2 (Voted to keep girls' sport at DoD schools for girls.); Nay -2 (Voted against keeping girls' sport at DoD schools for girls.)

### [ ] `house-119-2-273` On Agreeing to the Amendment: National Defense Authorization Act for Fiscal Year 2027 (Self of Texas Part A Amendment No. 28)

- **When / result:** 2026-07-22; Agreed to 221-210
- **Motion:** An amendment numbered 28 printed in Part A of House Report 119-755 to codify protections and responsibilities for chaplains and subject such protections to prosecution under the Uniform Code of Military Justice. | Amendment codifies protections and responsibilities for chaplains and subjects such protections to prosecution under the Uniform Code of Military Justice.
- **A Yea means:** For the Self amendment: codify chaplains' protections and responsibilities, enforceable under the UCMJ.
- **Lobbies:** Yea: R 217, D 3, I 1. Nay: D 210.
- **Proposed direction:** Yea +1 (Voted to codify protections for military chaplains.); Nay -1 (Voted against codifying protections for military chaplains.)
- **Flag for you:** Religious freedom (area 8). The purpose text is short; drafted at +/-1 until the amendment is read.

### [ ] `house-119-2-37` On Passage: Supporting Pregnant and Parenting Women and Families Act

- **When / result:** 2026-01-21; Passed 215-209
- **Motion:** Supporting Pregnant and Parenting Women and Families Act
- **A Yea means:** For passing the Supporting Pregnant and Parenting Women and Families Act: states may use TANF funds for pregnancy centres that support the life of the mother and the unborn child.
- **Lobbies:** Yea: R 214, D 1. Nay: D 209.
- **Proposed direction:** Yea +2 (Voted to let TANF funds support pro-life pregnancy centres.); Nay -2 (Voted against TANF funding for pro-life pregnancy centres.)

### [ ] `house-119-2-47` On Passage: Pregnant Students’ Rights Act

- **When / result:** 2026-01-22; Passed 217-211
- **Motion:** Pregnant Students’ Rights Act
- **A Yea means:** For passing the Pregnant Students' Rights Act: colleges must tell students of their rights and resources to carry a pregnancy to term.
- **Lobbies:** Yea: R 216, D 1. Nay: D 211.
- **Proposed direction:** Yea +1 (Voted to require colleges to inform pregnant students of resources to carry to term.); Nay -1 (Voted against requiring colleges to inform pregnant students of resources to carry to term.)
- **Flag for you:** An information duty, not a protection: drafted at +/-1.

### [ ] `senate-119-2-12` On Cloture on the Motion to Proceed S. 3627: Pregnant Students’ Rights Act

- **When / result:** 2026-01-27; Cloture on the Motion to Proceed Rejected 47-45
- **Motion:** Motion to Invoke Cloture on the Motion to Proceed to S. 3627 | A bill to require institutions of higher education to disseminate information on the rights of, and accommodations and resources for, pregnant students, and for other purposes.
- **A Yea means:** For cloture on the motion to proceed to S. 3627, the Senate's Pregnant Students' Rights Act. It failed 47-45.
- **Lobbies:** Yea: R 47. Nay: D 43, I 2.
- **Proposed direction:** Yea +1 (Voted to let the Senate take up the Pregnant Students' Rights Act (cloture).); Nay -1 (Voted to keep the Pregnant Students' Rights Act from the Senate floor.)

### [ ] `senate-119-2-72` On the Motion to Proceed S.J.Res. 103: A joint resolution providing for congressional disapproval under chapter 8 of title 5, United States Code, of the rule su

- **When / result:** 2026-03-25; Motion to Proceed Rejected 48-50
- **Motion:** Motion to proceed to S.J. Res. 103 | A joint resolution providing for congressional disapproval under chapter 8 of title 5, United States Code, of the rule submitted by the Department of Veterans Affairs relating to "Reproductive Health Services".
- **A Yea means:** For proceeding to S.J.Res. 103, which would overturn the VA rule on 'Reproductive Health Services' (the rule that took abortion out of veterans' care). The motion failed 48-50.
- **Lobbies:** Yea: D 44, R 2, I 2. Nay: R 50.
- **Proposed direction:** Yea -2 (Voted to take up the resolution restoring abortion in VA care.); Nay +2 (Voted against taking up the resolution restoring abortion in VA care.)
- **Flag for you:** Here a YEA is AGAINST us: S.J.Res. 103 disapproves a rule that restricts abortion. A motion to proceed, drafted at +/-2 as the resolution's only vote; check the rule's text before signing.

### [ ] `house-119-2-184` On Passage: Stopping Indoctrination and Protecting Kids Act

- **When / result:** 2026-05-20; Passed 217-198
- **Motion:** PROTECT Kids Act
- **A Yea means:** For passing the PROTECT Kids Act: elementary and middle schools must get parental consent before changing a child's gender markers, pronouns, name on forms, or sex-based accommodations.
- **Lobbies:** Yea: R 208, D 8, I 1. Nay: D 198.
- **Proposed direction:** Yea +2 (Voted to require parental consent before a school socially transitions a child.); Nay -2 (Voted against requiring parental consent before a school socially transitions a child.)

### [ ] `senate-119-1-82` On the Amendment S.Amdt. 971 to S.Con.Res. 7 (No short title on file): An original concurrent resolution setting forth the congressional budget for the United S

- **When / result:** 2025-02-21; Amendment Rejected 49-51
- **Motion:** Duckworth Amdt. No. 971 | To establish a deficit-neutral reserve fund relating to protecting access to fertility services, and eliminating barriers for families in need of high-quality, affordable fertility services by expanding nationwide coverage for in vitro fertilization. | To establish a deficit-neutral reserve fund relating to protecting access to fertility services, and eliminating barriers for families in need of high-quality, affordable fertility services by expanding nationwide coverage for in vitro fertilization.
- **A Yea means:** For the Duckworth amendment to the budget resolution: a deficit-neutral reserve fund for expanding IVF coverage nationwide. Rejected 49-51.
- **Lobbies:** Yea: D 45, R 2, I 2. Nay: R 51.
- **Proposed direction:** none -- CitizenGO's position on public IVF coverage is not written down anywhere in the repo, and a reserve-fund amendment to a budget resolution is a messaging vote. No direction proposed: give one, or mark it placeable: false.

### [ ] `house-119-1-119` On Motion to Suspend the Rules and Pass: Stop Forced Organ Harvesting Act of 2025

- **When / result:** 2025-05-07; Passed 406-1
- **Motion:** Stop Forced Organ Harvesting Act
- **A Yea means:** For passing the Stop Forced Organ Harvesting Act under suspension: sanctions on persons involved in forced organ harvesting.
- **Lobbies:** Yea: R 203, D 203. Nay: R 1.
- **Proposed direction:** evidence only, never places -- Passed 406-1: the lobby tells no member apart.

## Bills (sponsorship)

### [ ] `119/hr/21` Born-Alive Abortion Survivors Protection Act (House)

- **When / result:** sponsor Rep. Wagner, Ann [R-MO-2]; 163 cosponsors; areas [1]
- **Proposed direction:** sponsor +2 (Introduced the Born-Alive Abortion Survivors Protection Act.); cosponsor +1 (Cosponsored the Born-Alive Abortion Survivors Protection Act.)

### [ ] `119/s/6` Born-Alive Abortion Survivors Protection Act (Senate)

- **When / result:** sponsor Sen. Lankford, James [R-OK]; 50 cosponsors; areas [1]
- **Proposed direction:** sponsor +2 (Introduced the Born-Alive Abortion Survivors Protection Act.); cosponsor +1 (Cosponsored the Born-Alive Abortion Survivors Protection Act.)

### [ ] `119/hr/7` No Taxpayer Funding for Abortion and Abortion Insurance Full Disclosure Act (House)

- **When / result:** sponsor Rep. Smith, Christopher H. [R-NJ-4]; 128 cosponsors; areas [1]
- **Proposed direction:** sponsor +2 (Introduced the bill making the Hyde Amendment permanent.); cosponsor +1 (Cosponsored the bill making the Hyde Amendment permanent.)

### [ ] `119/s/186` No Taxpayer Funding for Abortion and Abortion Insurance Full Disclosure Act (Senate)

- **When / result:** sponsor Sen. Wicker, Roger F. [R-MS]; 50 cosponsors; areas [1]
- **Proposed direction:** sponsor +2 (Introduced the bill making the Hyde Amendment permanent.); cosponsor +1 (Cosponsored the bill making the Hyde Amendment permanent.)

### [ ] `119/hr/722` Life at Conception Act

- **When / result:** sponsor Rep. Burlison, Eric [R-MO-7]; 116 cosponsors; areas [1]
- **Proposed direction:** sponsor +2 (Introduced the Life at Conception Act.); cosponsor +1 (Cosponsored the Life at Conception Act.)

### [ ] `119/hr/589` FACE Act Repeal Act of 2025

- **When / result:** sponsor Rep. Roy, Chip [R-TX-21]; 44 cosponsors; areas [1, 8]
- **Proposed direction:** sponsor +2 (Introduced the repeal of the FACE Act, under which pro-life sidewalk counsellors and protesters were prosecuted.); cosponsor +1 (Cosponsored the repeal of the FACE Act.)

### [ ] `119/hr/271` Defund Planned Parenthood Act of 2025

- **When / result:** sponsor Rep. Fischbach, Michelle [R-MN-7]; 60 cosponsors; areas [1]
- **Proposed direction:** sponsor +2 (Introduced the bill ending federal funding of Planned Parenthood.); cosponsor +1 (Cosponsored the bill ending federal funding of Planned Parenthood.)

### [ ] `119/hr/12` Women's Health Protection Act of 2025 (House)

- **When / result:** sponsor Rep. Chu, Judy [D-CA-28]; 209 cosponsors; areas [1]
- **Proposed direction:** sponsor -2 (Introduced the bill creating a federal statutory right to abortion.); cosponsor -1 (Cosponsored the federal statutory right to abortion.)

### [ ] `119/s/2150` Women's Health Protection Act of 2025 (Senate)

- **When / result:** sponsor Sen. Baldwin, Tammy [D-WI]; 46 cosponsors; areas [1]
- **Proposed direction:** sponsor -2 (Introduced the bill creating a federal statutory right to abortion.); cosponsor -1 (Cosponsored the federal statutory right to abortion.)

### [ ] `119/hr/4611` EACH Act of 2025

- **When / result:** sponsor Rep. Pressley, Ayanna [D-MA-7]; 202 cosponsors; areas [1]
- **Proposed direction:** sponsor -2 (Introduced the bill to repeal the Hyde Amendment's effect (abortion coverage in federal insurance).); cosponsor -1 (Cosponsored the EACH Act (abortion coverage in federal insurance).)

### [ ] `119/hr/2029` Stop Comstock Act

- **When / result:** sponsor Rep. Balint, Becca [D-VT-At Large]; 146 cosponsors; areas [1]
- **Proposed direction:** sponsor -2 (Introduced the bill to repeal the Comstock Act's bar on mailing abortion drugs.); cosponsor -1 (Cosponsored the repeal of the Comstock Act's bar on mailing abortion drugs.)

### [ ] `119/sjres/103` S.J.Res. 103: disapproving the VA rule on 'Reproductive Health Services'

- **When / result:** sponsor Sen. Blumenthal, Richard [D-CT]; 39 cosponsors; areas [1]
- **Proposed direction:** sponsor -2 (Introduced the resolution restoring abortion in VA care.); cosponsor -1 (Cosponsored the resolution restoring abortion in VA care.)

### [ ] `119/hr/28` Protection of Women and Girls in Sports Act (House)

- **When / result:** sponsor Rep. Steube, W. Gregory [R-FL-17]; 83 cosponsors; areas [5]
- **Proposed direction:** sponsor +2 (Introduced the Protection of Women and Girls in Sports Act.); cosponsor +1 (Cosponsored the Protection of Women and Girls in Sports Act.)

### [ ] `119/s/9` Protection of Women and Girls in Sports Act (Senate)

- **When / result:** sponsor Sen. Tuberville, Tommy [R-AL]; 44 cosponsors; areas [5]
- **Proposed direction:** sponsor +2 (Introduced the Protection of Women and Girls in Sports Act.); cosponsor +1 (Cosponsored the Protection of Women and Girls in Sports Act.)

### [ ] `119/hr/3492` Protect Children's Innocence Act

- **When / result:** sponsor Rep. Greene, Marjorie Taylor [R-GA-14]; 44 cosponsors; areas [3, 5]
- **Proposed direction:** sponsor +2 (Introduced the Protect Children's Innocence Act.); cosponsor +1 (Cosponsored the Protect Children's Innocence Act.)

### [ ] `119/hr/498` Do No Harm in Medicaid Act

- **When / result:** sponsor Rep. Crenshaw, Dan [R-TX-2]; 6 cosponsors; areas [3, 5]
- **Proposed direction:** sponsor +2 (Introduced the Do No Harm in Medicaid Act.); cosponsor +1 (Cosponsored the Do No Harm in Medicaid Act.)

### [ ] `119/hr/5483` Chloe Cole Act

- **When / result:** sponsor Rep. Onder, Robert F. [R-MO-3]; 44 cosponsors; areas [3]
- **Proposed direction:** sponsor +2 (Introduced the Chloe Cole Act.); cosponsor +1 (Cosponsored the Chloe Cole Act.)

### [ ] `119/hr/2616` PROTECT Kids Act (Stopping Indoctrination and Protecting Kids Act)

- **When / result:** sponsor Rep. Walberg, Tim [R-MI-5]; 4 cosponsors; areas [6]
- **Proposed direction:** sponsor +2 (Introduced the PROTECT Kids Act (parental consent for social transition at school).); cosponsor +1 (Cosponsored the PROTECT Kids Act.)

### [ ] `119/hr/15` Equality Act (House)

- **When / result:** sponsor Rep. Takano, Mark [D-CA-39]; 218 cosponsors; areas [5, 8]
- **Proposed direction:** sponsor -2 (Introduced the Equality Act (gender identity in the Civil Rights Act, overriding single-sex spaces and RFRA defences).); cosponsor -1 (Cosponsored the Equality Act.)

### [ ] `119/s/1503` Equality Act (Senate)

- **When / result:** sponsor Sen. Merkley, Jeff [D-OR]; 46 cosponsors; areas [5, 8]
- **Proposed direction:** sponsor -2 (Introduced the Equality Act.); cosponsor -1 (Cosponsored the Equality Act.)

### [ ] `119/hr/2487` Transgender Health Care Access Act

- **When / result:** sponsor Rep. Balint, Becca [D-VT-At Large]; 80 cosponsors; areas [5]
- **Proposed direction:** sponsor -2 (Introduced the Transgender Health Care Access Act.); cosponsor -1 (Cosponsored the Transgender Health Care Access Act.)

47 entries.
