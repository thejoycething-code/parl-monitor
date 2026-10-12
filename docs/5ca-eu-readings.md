# European Parliament 5CA: readings to sign

Every unsigned reading below was DRAFTED by Claude on 9 October 2026 from
the store (eu_divisions, eu_votes, eu_meps) and the adopted texts, read in
full. None is signed, so `tools/make_eu_5ca.py` places nobody on them: the
EU 5CA still rests on the signed divisions only. The direction of a vote is
your judgement, never the tool's.

Three kinds of draft. **Proposed side**: our side favour or against, with the
two meaning lines and a confidence. **Evidence only**: never places anyone
(no name lists, near-unanimous, a split part without the contested words,
words not on our ground, migration); ticking it accepts that. **No
direction**: the amendment's words are not in the store, or the call is
yours; these cannot be ticked into force. Write `our_side` (favor/against)
and both meaning lines in `config/eu_divisions.yaml` first, or
`placeable: false` with a `reason:`.

Lobbies are favour-against-abstention by each MEP's current group.

**How to sign.** Tick `[x]` on each reading you accept as drafted, then run `python3 tools/make_eu_5ca.py --sign-from-doc`. It deletes those entries' `draft: true` lines in `config/eu_divisions.yaml` and sets `signed_off: true` with a dated note. To change a side or a meaning, edit `config/eu_divisions.yaml` first and leave the box empty. Nothing unticked places anyone.

**Where it stands:** 12 signed and placing, 0 signed evidence-only, 192 drafted and unsigned, 202 with no direction yet.

| Report | Sitting | Proposed side | No direction | Evidence only | Signed |
|---|---|---|---|---|---|
| Care society report | 2026-05-21 | 5 | 2 | 27 | 0 |
| Development cooperation and irregular migration | 2026-06-16 | 0 | 0 | 18 | 0 |
| Transnational repression report | 2026-06-16 | 0 | 1 | 8 | 0 |
| Türkiye 2025 report | 2026-06-17 | 0 | 25 | 3 | 0 |
| Nicaragua political prisoners | 2026-06-18 | 0 | 1 | 0 | 0 |
| Recruitment of children by organised crime | 2026-06-18 | 0 | 0 | 10 | 0 |
| Media literacy strategy | 2026-07-07 | 0 | 6 | 7 | 0 |
| SDG resolution (2026 High-Level Political Forum) | 2026-07-07 | 0 | 1 | 0 | 1 |
| ePrivacy scanning derogation | 2026-07-07 | 0 | 0 | 0 | 1 |
| Cyprus 1974 resolution | 2026-07-08 | 0 | 10 | 9 | 3 |
| Moldova 2025 report | 2026-07-08 | 0 | 3 | 2 | 0 |
| Serbia 2025 report | 2026-07-08 | 0 | 1 | 1 | 0 |
| Maria Shahbaz / girls in Pakistan | 2026-07-09 | 1 | 4 | 0 | 0 |
| Nigeria | 2026-07-09 | 2 | 4 | 1 | 1 |
| ePrivacy derogation | 2026-07-09 | 0 | 2 | 0 | 3 |
| EU Youth Strategy report | 2026-09-15 | 0 | 6 | 2 | 0 |
| European Democracy Shield | 2026-09-15 | 0 | 1 | 0 | 1 |
| Gender inequalities in health report | 2026-09-16 | 20 | 9 | 50 | 0 |
| Global health resilience | 2026-09-17 | 1 | 0 | 0 | 0 |
| Social media and young people | 2026-09-17 | 1 | 1 | 1 | 2 |
| EU-China recommendation | 2026-10-07 | 0 | 31 | 15 | 0 |
| Islamist entryism / Muslim Brotherhood | 2026-10-08 | 0 | 94 | 8 | 0 |

## Care society report (2026-05-21)

### [ ] `MTG-PL-2026-05-21-DEC-192536` Motion for a resolution (as a whole)

- **Result:** ADOPTED 263-83-154
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 99-3-11, S&D 3-4-78, PfE 26-35-4, ECR 7-10-43, Renew 41-7-11, Greens 42-0-0, Left 34-0-0, ESN 0-18-3, NI 10-6-4, ? 1-0-0
- **Proposed side:** AGAINST (low confidence)
  - favour: Backed the care-society report, which besides its care and work-life policy says that access to abortion services helps parents with family planning (recital R) and calls on the Member States to provide affordable access to abortion services (§ 78).
  - against: Opposed the care-society report, whose text asks the Member States to provide affordable access to abortion services as family-planning support.
- **Flag for you:** Mostly care and work-life policy; the abortion content is recital R and § 78, both voted separately (R/2 and § 79 in the motion's numbering, drafted below). The Socialists abstained almost en bloc (3-4-78), so the against lobby is small (83). Sign evidence-only instead if you would rather place members on the abortion lines alone.

### [ ] `MTG-PL-2026-05-21-DEC-193093` § 37/2: the words ‘gender mainstreaming and gender’ and ‘to be implemented’

- **Result:** REJECTED 245-275-20
- **A favour vote means:** For keeping the words ‘gender mainstreaming and gender’ and ‘to be implemented’
- **Lobbies:** EPP 18-97-11, S&D 92-1-0, PfE 0-68-2, ECR 1-65-0, Renew 51-10-1, Greens 42-0-0, Left 35-0-0, ESN 0-24-0, NI 5-9-6, ? 1-1-0
- **Proposed side:** AGAINST (low confidence)
  - favour: Voted to keep 'gender mainstreaming and gender' and 'to be implemented' in § 37 of the care report (rejected 245-275).
  - against: Voted to strike 'gender mainstreaming' from § 37 of the care report.
- **Flag for you:** Gender mainstreaming is standard EU equality language. Whether it is CitizenGO's ground (area 5, sex-based rights) is your call; recital A/2 below is the same question. Sign both or neither.

### [ ] `MTG-PL-2026-05-21-DEC-193103` § 79

- **Result:** ADOPTED 327-154-31
- **A favour vote means:** For keeping § 79 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 78 (inferred: motion numbering -1, from the nearest quoted split): 78. Notes that proper access to reproductive healthcare and abortion services can help parents avoid the stress of unexpected pregnancies and contribute to family planning; calls on the Member States to provide affordable access to such services;
- **Lobbies:** EPP 56-46-16, S&D 86-0-0, PfE 29-31-7, ECR 8-48-6, Renew 58-1-1, Greens 42-0-0, Left 34-0-0, ESN 1-21-0, NI 12-7-1, ? 1-0-0
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted for the paragraph noting that access to reproductive healthcare and abortion services helps parents avoid the stress of unexpected pregnancies, and calling on the Member States to provide affordable access to them.
  - against: Voted against the paragraph calling on the Member States to provide affordable access to abortion services.
- **Flag for you:** Plain paragraph vote: the text is § 78 of the adopted text, located by the -1 offset the quoted splits show for this report. The lobbies fit (EPP 56-46-16, ECR 8-48). Check the motion's § 79 if you can.

### [ ] `MTG-PL-2026-05-21-DEC-193108` Recital A/2: ‘whereas gender mainstreaming and an intersectional approach should be implemented and integrated…

- **Result:** ADOPTED 303-178-27
- **A favour vote means:** For keeping the words ‘whereas gender mainstreaming and an intersectional approach should be implemented and integrated across all EU policies;’
- **Text:** Adopted recital A (quote found in the adopted text): A. whereas gender equality is one of the EU’s founding values; whereas gender mainstreaming and an intersectional approach should be implemented and integrated across all EU policies;
- **Lobbies:** EPP 83-24-14, S&D 85-0-0, PfE 1-60-3, ECR 2-60-0, Renew 50-6-2, Greens 43-0-0, Left 34-0-0, ESN 0-22-0, NI 4-6-8, ? 1-0-0
- **Proposed side:** AGAINST (low confidence)
  - favour: Voted for recital A/2: 'whereas gender mainstreaming and an intersectional approach should be implemented and integrated across all EU policies'.
  - against: Voted against making gender mainstreaming and an intersectional approach a rule for all EU policies.
- **Flag for you:** Same question as § 37/2: is gender mainstreaming CitizenGO's ground? Sign both or neither.

### [ ] `MTG-PL-2026-05-21-DEC-193112` Recital R/2: the words ‘and abortion services’

- **Result:** ADOPTED 320-152-34
- **A favour vote means:** For keeping the words ‘and abortion services’
- **Lobbies:** EPP 57-47-15, S&D 84-0-0, PfE 27-30-6, ECR 6-46-9, Renew 59-1-0, Greens 43-0-0, Left 34-0-0, ESN 0-21-1, NI 9-7-3, ? 1-0-0
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted to keep the words 'and abortion services' in recital R, which says increased access to reproductive healthcare and abortion services may help parents with family planning and reduce the stress of unexpected pregnancies.
  - against: Voted to strike 'and abortion services' from recital R, refusing to present abortion as a family-planning aid for parents.

### [ ] `MTG-PL-2026-05-21-DEC-193082` After § 14 – Am 2

- **Result:** REJECTED 181-342-20
- **A favour vote means:** For amendment 2 (inserting After § 14). Its words are not in the store.
- **Lobbies:** EPP 5-105-18, S&D 1-92-0, PfE 71-0-0, ECR 65-0-1, Renew 4-56-1, Greens 0-43-0, Left 0-36-0, ESN 24-0-0, NI 10-9-0, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-05-21-DEC-193087` After § 28 – Am 3

- **Result:** REJECTED 190-311-39
- **A favour vote means:** For amendment 3 (inserting After § 28). Its words are not in the store.
- **Lobbies:** EPP 5-98-23, S&D 2-91-0, PfE 71-0-0, ECR 64-0-0, Renew 4-58-0, Greens 0-43-0, Left 5-18-12, ESN 24-0-0, NI 14-3-3, ? 1-0-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-05-21-DEC-192533` § 56

- **Result:** ADOPTED 259-229-32
- **A favour vote means:** For keeping § 56 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 55 (inferred: motion numbering -1, from the nearest quoted split): 55. Calls on the Member States to invest in a care economy and to implement the Council recommendations on the revision of the Barcelona targets on early childhood education and care and on access to affordable high-quality long-term care under the EU care strategy, and to include in their implementation reports the identification of good practices, gaps and progress mapping, together with strategies to encourage greater participation of men in the care sector, and to address undeclared care work, identifying the main drivers and proposing tailored solutions; calls on the Commission to ensure that the European Child
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-05-21-DEC-192534` After § 65

- **Result:** REJECTED 195-257-53
- **A favour vote means:** For keeping After § 65 as drafted (a separate vote on that paragraph or recital).
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-05-21-DEC-193081` § 14

- **Result:** ADOPTED 496-7-35
- **A favour vote means:** For keeping § 14 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 13 (inferred: motion numbering -1, from the nearest quoted split): 13. Highlights that by 2070, almost 30 % of the EU population will be aged 65 or over, which, together with other factors such as higher life expectancy and the growing care needs of persons with disabilities, may lead to higher demand for care services that put significant pressure on health and welfare systems, while the number of people requiring long-term care is expected to increase from 30,8 million in 2019 to 38.1 million in 2050; notes that current needs already pose a challenge, where one in five persons in need of long-term care cannot access such services due to affordability constraints;
- **Lobbies:** EPP 128-0-0, S&D 91-0-0, PfE 63-0-7, ECR 60-4-1, Renew 62-0-0, Greens 42-0-0, Left 31-1-2, ESN 1-2-21, NI 16-0-4, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (496-7): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-05-21-DEC-193083` § 15

- **Result:** ADOPTED 460-14-64
- **A favour vote means:** For keeping § 15 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 14 (inferred: motion numbering -1, from the nearest quoted split): 14. Considers that a care society recognises the vital role of care, encompassing both formal and informal care, throughout every stage of life, and integrates it into its policies, addressing all types of care provided predominantly by women, including early childhood education and care and long-term care;
- **Lobbies:** EPP 126-0-1, S&D 90-0-0, PfE 33-9-29, ECR 57-0-8, Renew 59-1-0, Greens 43-0-0, Left 36-0-0, ESN 1-2-21, NI 14-2-4, ? 1-0-1
- **Proposed:** evidence only, never places -- Near-unanimous (460-14): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-05-21-DEC-193084` § 19

- **Result:** ADOPTED 505-29-9
- **A favour vote means:** For keeping § 19 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 18 (inferred: motion numbering -1, from the nearest quoted split): 18. Calls for awareness-raising campaigns targeting men, encouraging men to take up an equal share of caregiving responsibilities, thereby enabling stronger female labour force participation, taking into account the impact of social media, strengthening the fight against gender stereotypes, together with educational initiatives and other measures, such as promoting workplace cultures that value and support this care parity; calls for the launch of EU-wide awareness campaigns that revalue care work and challenge traditional gender stereotypes;
- **Lobbies:** EPP 126-1-0, S&D 93-0-0, PfE 64-7-0, ECR 61-0-5, Renew 61-0-0, Greens 43-0-0, Left 36-0-0, ESN 3-17-4, NI 16-4-0, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (505-29): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-05-21-DEC-193085` § 22

- **Result:** ADOPTED 321-118-102
- **A favour vote means:** For keeping § 22 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 21 (inferred: motion numbering -1, from the nearest quoted split): 21. Stresses the importance of the proper implementation of effective measures and policies, including the Work-Life Balance Directive, to ensure genuine work-life balance; calls on the Commission to carefully monitor the implementation of this directive and highlights the need to close the gender pay and pension gaps by enforcing existing legal frameworks and ensuring their effectiveness;
- **Lobbies:** EPP 62-37-26, S&D 84-3-5, PfE 28-9-34, ECR 6-30-29, Renew 45-17-1, Greens 43-0-0, Left 36-0-0, ESN 0-19-5, NI 16-3-1, ? 1-0-1
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193089` § 36/1: the text without the words ‘especially when profit motives are low’

- **Result:** ADOPTED 472-33-33
- **A favour vote means:** For keeping the passage WITHOUT the words ‘especially when profit motives are low’; those words were put separately as the next part.
- **Text:** Adopted § 35 (quote found in the adopted text): 35. Highlights the importance of social economy enterprises and cooperatives in providing care services in areas and for populations that are underserved by the traditional public or private providers, especially when profit motives are low;
- **Lobbies:** EPP 124-4-0, S&D 91-0-0, PfE 34-22-14, ECR 65-0-1, Renew 62-0-0, Greens 43-0-0, Left 35-0-0, ESN 4-2-18, NI 13-4-0, ? 1-1-0
- **Proposed:** evidence only, never places -- Near-unanimous (472-33): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-05-21-DEC-193090` § 36/2: the words ‘especially when profit motives are low’

- **Result:** ADOPTED 299-134-103
- **A favour vote means:** For keeping the words ‘especially when profit motives are low’
- **Text:** Adopted § 35 (quote found in the adopted text): 35. Highlights the importance of social economy enterprises and cooperatives in providing care services in areas and for populations that are underserved by the traditional public or private providers, especially when profit motives are low;
- **Lobbies:** EPP 1-94-31, S&D 92-0-0, PfE 54-1-15, ECR 5-10-50, Renew 53-5-1, Greens 43-0-0, Left 35-0-0, ESN 1-21-2, NI 13-3-4, ? 2-0-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193092` § 37/1: the text without the words ‘gender mainstreaming and gender’ and ‘to be implemented’

- **Result:** ADOPTED 286-182-65
- **A favour vote means:** For keeping the passage WITHOUT the words ‘gender mainstreaming and gender’ and ‘to be implemented’; those words were put separately as the next part.
- **Lobbies:** EPP 18-105-2, S&D 91-0-0, PfE 31-6-32, ECR 5-57-2, Renew 55-4-1, Greens 43-0-0, Left 36-0-0, ESN 0-5-19, NI 6-5-8, ? 1-0-1
- **Proposed:** evidence only, never places -- This part put the passage WITHOUT the contested words, which were voted as the next part; it records nothing about those words.

### [ ] `MTG-PL-2026-05-21-DEC-193094` § 38

- **Result:** ADOPTED 334-135-70
- **A favour vote means:** For keeping § 38 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 37 (inferred: motion numbering -1, from the nearest quoted split): 37. Stresses the need to ensure the participation of care workers and their representatives in all stages of policymaking, including the design, implementation and evaluation of policies that affect them;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-05-21-DEC-193095` § 43

- **Result:** ADOPTED 261-105-174
- **A favour vote means:** For keeping § 43 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 42 (inferred: motion numbering -1, from the nearest quoted split): 42. Denounces the fact that many care and domestic workers are facing a highly precarious situation and experiencing intersectional discrimination as a result of their race or ethnicity, gender, socio-economic status or nationality, and the fact that many of these workers are women who do not have an official employment contract, and are thus more vulnerable to exploitation and often lack access to their rights, in particular to decent work and social protection;
- **Lobbies:** EPP 14-2-110, S&D 93-0-0, PfE 1-28-41, ECR 3-49-14, Renew 59-0-2, Greens 43-0-0, Left 35-0-0, ESN 0-21-3, NI 12-5-3, ? 1-0-1
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193097` § 49/1: the text without the words ‘rights’

- **Result:** ADOPTED 421-77-33
- **A favour vote means:** For keeping the passage WITHOUT the words ‘rights’; those words were put separately as the next part.
- **Lobbies:** EPP 112-2-7, S&D 93-0-0, PfE 42-10-18, ECR 17-44-2, Renew 61-0-0, Greens 43-0-0, Left 35-0-0, ESN 3-19-1, NI 14-2-4, ? 1-0-1
- **Proposed:** evidence only, never places -- This part put the passage WITHOUT the contested words, which were voted as the next part; it records nothing about those words.

### [ ] `MTG-PL-2026-05-21-DEC-193098` § 49/2: the words ‘rights’

- **Result:** ADOPTED 358-134-30
- **A favour vote means:** For keeping the words ‘rights’
- **Lobbies:** EPP 77-27-11, S&D 91-0-0, PfE 33-27-9, ECR 7-50-6, Renew 60-0-0, Greens 43-0-0, Left 35-0-0, ESN 1-23-0, NI 10-6-4, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193099` § 53

- **Result:** ADOPTED 248-158-114
- **A favour vote means:** For keeping § 53 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 52 (inferred: motion numbering -1, from the nearest quoted split): 52. Urges the application of gender budgeting to ensure that spending on care services directly reduces inequalities faced by women and girls;
- **Lobbies:** EPP 22-19-76, S&D 92-0-0, PfE 0-58-9, ECR 1-42-20, Renew 50-7-2, Greens 41-0-0, Left 35-0-0, ESN 0-24-0, NI 6-7-7, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193100` § 55

- **Result:** ADOPTED 373-76-79
- **A favour vote means:** For keeping § 55 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 54 (inferred: motion numbering -1, from the nearest quoted split): 54. Emphasises the need to consult all relevant stakeholders during the preparation of the announced care deal, at EU, national and local level, including informal carer representatives and patient organisations, so as to avoid policy silos, and to take into account the diversity of situations and needs;
- **Lobbies:** EPP 88-11-19, S&D 92-0-0, PfE 36-14-19, ECR 6-26-33, Renew 59-3-0, Greens 42-0-0, Left 35-0-0, ESN 1-21-1, NI 13-1-6, ? 1-0-1
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193101` § 58

- **Result:** ADOPTED 507-3-16
- **A favour vote means:** For keeping § 58 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 57 (inferred: motion numbering -1, from the nearest quoted split): 57. Stresses that care provided to persons with disabilities needs to prioritise autonomy, as these individuals should be able to decide where and with whom they live, as well as dignity and inclusion through a human-rights-based and person-centred approach, reflecting the ongoing shift in care provision; emphasises that this can be achieved by improving their care conditions, such as through high-quality, home-based care or other residential options that would meet their needs, including independent and accessible living, and by including persons with disabilities in the design of the care systems, while also promo
- **Lobbies:** EPP 119-0-0, S&D 88-2-0, PfE 64-0-6, ECR 61-0-4, Renew 59-1-0, Greens 42-0-0, Left 34-0-0, ESN 22-0-2, NI 16-0-4, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (507-3): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-05-21-DEC-193102` § 64

- **Result:** ADOPTED 266-234-25
- **A favour vote means:** For keeping § 64 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 63 (inferred: motion numbering -1, from the nearest quoted split): 63. Calls on the Commission to present a directive on the right to disconnect to protect all workers, particularly parents and caregivers;
- **Lobbies:** EPP 22-95-5, S&D 89-0-0, PfE 26-36-7, ECR 1-61-2, Renew 39-17-4, Greens 42-0-0, Left 33-0-0, ESN 1-20-3, NI 12-4-4, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193104` § 81

- **Result:** ADOPTED 307-146-58
- **A favour vote means:** For keeping § 81 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 80 (inferred: motion numbering -1, from the nearest quoted split): 80. Welcomes the Commission’s announcement of a comprehensive European Care Deal to be published in 2027, thereby renewing the European care strategy as a more ambitious and coherent framework;
- **Lobbies:** EPP 86-11-22, S&D 85-0-1, PfE 1-65-0, ECR 0-37-24, Renew 47-7-5, Greens 43-0-0, Left 34-0-0, ESN 0-22-0, NI 10-4-6, ? 1-0-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193105` § 83

- **Result:** ADOPTED 427-42-42
- **A favour vote means:** For keeping § 83 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 82 (inferred: motion numbering -1, from the nearest quoted split): 82. Highlights that greater investment in public health and social care, including workers’ wages and training, is essential to improve recruitment and retention in order to secure quality jobs that increase the attractiveness of working in the care sector;
- **Lobbies:** EPP 116-1-0, S&D 86-0-0, PfE 49-11-7, ECR 25-9-27, Renew 57-0-3, Greens 43-0-0, Left 34-0-0, ESN 0-19-3, NI 16-2-2, ? 1-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (427-42): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-05-21-DEC-193107` Recital A/1: ‘whereas gender equality is one of the EU’s founding values;’

- **Result:** ADOPTED 437-28-48
- **A favour vote means:** For keeping the words ‘whereas gender equality is one of the EU’s founding values;’
- **Text:** Adopted recital A (quote found in the adopted text): A. whereas gender equality is one of the EU’s founding values; whereas gender mainstreaming and an intersectional approach should be implemented and integrated across all EU policies;
- **Lobbies:** EPP 117-0-5, S&D 87-0-0, PfE 44-12-11, ECR 43-6-13, Renew 59-0-0, Greens 43-0-0, Left 33-0-0, ESN 0-5-16, NI 10-5-3, ? 1-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (437-28): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-05-21-DEC-193109` Recital F

- **Result:** ADOPTED 473-12-26
- **A favour vote means:** For keeping Recital F as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital F (motion numbering unchanged (checked against the nearest quoted split)): F. whereas rural, remote and island areas and outermost regions lack sufficient or adequate social care and support services, which may reinforce the economic and social challenges they might already face; whereas access to these services in those areas remains a challenge given their declining and ageing populations, and a lack of connectivity and infrastructure; whereas this can contribute to the lower attractiveness of these areas as places to live and work; whereas this disproportionately affects women, who face additional difficulties in trying to reconcile work and private life; whereas these are
- **Lobbies:** EPP 120-1-0, S&D 87-0-0, PfE 59-6-1, ECR 56-1-4, Renew 58-0-0, Greens 43-0-0, Left 34-0-0, ESN 2-1-18, NI 13-3-3, ? 1-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (473-12): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-05-21-DEC-193111` Recital R/1: the text without the words ‘and abortion services’

- **Result:** ADOPTED 384-113-13
- **A favour vote means:** For keeping the passage WITHOUT the words ‘and abortion services’; those words were put separately as the next part.
- **Lobbies:** EPP 93-23-2, S&D 87-0-0, PfE 38-26-1, ECR 12-43-6, Renew 60-0-0, Greens 43-0-0, Left 34-0-0, ESN 1-18-2, NI 15-3-2, ? 1-0-0
- **Proposed:** evidence only, never places -- This part put the passage WITHOUT the contested words, which were voted as the next part; it records nothing about those words.

### [ ] `MTG-PL-2026-05-21-DEC-193114` Recital S/1: ‘whereas the Work-Life Balance Directive has not been fully implemented in several Member States;…

- **Result:** ADOPTED 344-111-50
- **A favour vote means:** For keeping the words ‘whereas the Work-Life Balance Directive has not been fully implemented in several Member States;’
- **Text:** Adopted recital S (quote found in the adopted text): S. whereas the Work-Life Balance Directive has not been fully implemented in several Member States; whereas its provision on carers’ right to leave of five working days per year is insufficient to provide adequate care or to organise formal care and is not covered by the same safeguards regarding remuneration and income support as other types of family leave;
- **Lobbies:** EPP 111-4-2, S&D 84-0-0, PfE 6-46-12, ECR 3-29-30, Renew 52-8-0, Greens 43-0-0, Left 33-0-0, ESN 0-22-0, NI 11-2-6, ? 1-0-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193115` Recital S/2: ‘whereas its provision on carers’ right to leave of five working days per year is insufficient to…

- **Result:** ADOPTED 273-160-79
- **A favour vote means:** For keeping the words ‘whereas its provision on carers’ right to leave of five working days per year is insufficient to provide adequate care or to organise formal care and is not c…
- **Lobbies:** EPP 25-82-13, S&D 86-0-0, PfE 26-9-30, ECR 3-34-25, Renew 43-12-5, Greens 43-0-0, Left 34-0-0, ESN 0-21-1, NI 12-2-5, ? 1-0-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193116` Recital AC

- **Result:** ADOPTED 238-217-57
- **A favour vote means:** For keeping Recital AC as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital AC (motion numbering unchanged (checked against the nearest quoted split)): AC. whereas many care and domestic workers in Europe are migrant women, who face a highly precarious situation and experience intersectional discrimination owing to their nationality, race or ethnicity, gender and socio-economic and residence status; whereas these migrants are making up for the lack of public and affordable care in the EU and they are not being treated equally in terms of their social rights and access to decent working conditions;
- **Lobbies:** EPP 7-94-22, S&D 87-0-0, PfE 0-41-24, ECR 1-54-6, Renew 54-0-2, Greens 43-0-0, Left 34-0-0, ESN 0-20-2, NI 11-8-1, ? 1-0-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193117` Recital AF

- **Result:** ADOPTED 285-198-30
- **A favour vote means:** For keeping Recital AF as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital AF (motion numbering unchanged (checked against the nearest quoted split)): AF. whereas the establishment of a European Care Deal, minimum wages and access to high-quality, free public services would contribute to reducing poverty and closing the care gap, as well as the gender pay gap and the pension gap;
- **Lobbies:** EPP 79-32-11, S&D 83-0-3, PfE 0-64-2, ECR 0-59-2, Renew 37-19-4, Greens 42-0-0, Left 34-0-0, ESN 2-20-0, NI 7-4-8, ? 1-0-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

### [ ] `MTG-PL-2026-05-21-DEC-193118` Recital AH

- **Result:** ADOPTED 294-144-70
- **A favour vote means:** For keeping Recital AH as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital AH (motion numbering unchanged (checked against the nearest quoted split)): AH. whereas the 2026-2030 gender equality strategy, published on 5 March 2026, mentions that the European care strategy will be developed into the European Care Deal to be delivered in 2027;
- **Lobbies:** EPP 84-22-15, S&D 85-0-0, PfE 0-41-24, ECR 0-38-24, Renew 44-13-1, Greens 41-0-0, Left 34-0-0, ESN 0-22-0, NI 5-8-6, ? 1-0-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on care society report policy, not on our issues.

## Development cooperation and irregular migration (2026-06-16)

### [ ] `MTG-PL-2026-06-16-DEC-194308` Alternative motion for a resolution – Am 1

- **Result:** REJECTED 150-474-47
- **A favour vote means:** For amendment 1 (amending Alternative motion for a resolution). Its words are not in the store.
- **Lobbies:** EPP 1-168-1, S&D 0-130-0, PfE 78-0-0, ECR 34-4-43, Renew 0-68-0, Greens 0-48-0, Left 0-43-0, ESN 25-0-0, NI 11-12-3, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194309` After § 1 – Am 9

- **Result:** REJECTED 224-404-31
- **A favour vote means:** For amendment 9 (inserting After § 1). Its words are not in the store.
- **Lobbies:** EPP 29-114-26, S&D 7-125-0, PfE 74-0-0, ECR 74-1-4, Renew 0-66-0, Greens 0-47-0, Left 0-39-0, ESN 25-0-0, NI 14-11-1, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194312` § 11/2: the words ‘to diversify and implement legal pathways’

- **Result:** ADOPTED 455-211-7
- **A favour vote means:** For keeping the words ‘to diversify and implement legal pathways’
- **Text:** Adopted § 11 (quote found in the adopted text): 11. Underlines the need to ensure greater private sector involvement, to diversify and implement legal pathways, recognise skills, engage EU development banks, and develop innovative approaches to blending funds within the Team Europe framework and while contributing to the Global Gateway; encourages the participation of the European private sector in development projects in partner countries, ensuring support for a safe and transparent investment framework that facilitates the involvement of small and medium-sized enterprises and the creation of local production chains;
- **Lobbies:** EPP 155-16-0, S&D 130-1-0, PfE 0-78-0, ECR 3-78-0, Renew 66-0-2, Greens 48-0-0, Left 42-0-1, ESN 0-24-1, NI 10-13-3, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194313` § 15 – Am 10

- **Result:** REJECTED 234-423-14
- **A favour vote means:** For amendment 10 (amending § 15). Its words are not in the store.
- **Lobbies:** EPP 35-128-8, S&D 6-124-0, PfE 78-0-0, ECR 77-0-4, Renew 0-68-0, Greens 0-48-0, Left 1-42-0, ESN 24-0-0, NI 12-12-2, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194316` § 15/2: ‘as well as by providing safer alternatives through the creation of legal channels for safe and regula…

- **Result:** ADOPTED 253-165-214
- **A favour vote means:** For keeping the words ‘as well as by providing safer alternatives through the creation of legal channels for safe and regular migration and labour mobility; underlines that strict b…
- **Text:** Adopted § 15 (quote found in the adopted text): 15. Emphasises the need to combat human smuggling and trafficking through strengthened international and multilateral cooperation with partner countries, including, where appropriate, with local authorities, security forces and civil society organisations, on crime prevention, victim protection, enhanced law enforcement, public awareness campaigns to counteract disinformation, the prosecution of perpetrators and the prevention of the exploitation of migrants by criminal networks and migrant smugglers, as well as by providing safer alternatives through the creation of legal channels for safe and regular migration and labour mobility; underlines 
- **Lobbies:** EPP 5-11-153, S&D 88-0-4, PfE 0-73-5, ECR 2-36-43, Renew 59-6-3, Greens 48-0-0, Left 43-0-0, ESN 0-24-1, NI 7-14-5, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194320` After § 18 – Am 4

- **Result:** ADOPTED 431-223-10
- **A favour vote means:** For amendment 4 (inserting After § 18). Its words are not in the store.
- **Lobbies:** EPP 170-0-0, S&D 20-102-3, PfE 73-5-0, ECR 80-0-0, Renew 42-24-1, Greens 1-43-4, Left 0-43-0, ESN 24-0-1, NI 20-5-1, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194322` After § 25 – Am 11

- **Result:** REJECTED 222-429-14
- **A favour vote means:** For amendment 11 (inserting After § 25). Its words are not in the store.
- **Lobbies:** EPP 33-128-3, S&D 1-125-5, PfE 78-0-0, ECR 72-6-3, Renew 1-67-0, Greens 0-48-0, Left 0-43-0, ESN 24-0-0, NI 12-11-3, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194326` After § 33 – Am 12

- **Result:** REJECTED 244-410-12
- **A favour vote means:** For amendment 12 (inserting After § 33). Its words are not in the store.
- **Lobbies:** EPP 44-119-8, S&D 4-121-3, PfE 78-0-0, ECR 78-0-1, Renew 0-67-0, Greens 0-48-0, Left 0-43-0, ESN 24-0-0, NI 15-11-0, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194332` Recital G/2: ‘whereas a majority of migrants coming to Europe arrive through legal channels; whereas SDG 10 ta…

- **Result:** ADOPTED 438-182-50
- **A favour vote means:** For keeping the words ‘whereas a majority of migrants coming to Europe arrive through legal channels; whereas SDG 10 target 7 calls for countries to facilitate the orderly, safe, re…
- **Text:** Adopted recital G (quote found in the adopted text): G. whereas since 2015, the EU has been facing unprecedented migration flows, the management of which has required sustained effort from Member States, and whereas it is therefore necessary to strengthen European development policies to address the root causes of irregular migration and forced displacement, given that over 8,5 million requests for asylum were submitted in EU Member States between 2015 and 2024; whereas the irregular border crossings at the EU’s external borders fell by over one quarter (26 %) in 2025 to almost 178 000; whereas a majority of migrants coming to Europe arrive through legal channels; whereas SDG 10 target 7 cal
- **Lobbies:** EPP 135-29-4, S&D 132-0-0, PfE 0-78-0, ECR 3-38-40, Renew 67-0-0, Greens 48-0-0, Left 43-0-0, ESN 0-25-0, NI 9-11-6, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194335` Recital I

- **Result:** ADOPTED 348-304-16
- **A favour vote means:** For keeping Recital I as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital I (motion numbering unchanged (checked against the nearest quoted split)): I. whereas many countries of origin of asylum applicants are low- and middle-income countries; whereas acceptance rates for asylum seekers from these countries vary considerably;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-194336` Recital J

- **Result:** ADOPTED 408-200-63
- **A favour vote means:** For keeping Recital J as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital J (motion numbering unchanged (checked against the nearest quoted split)): J. whereas in 2024, EU countries granted protection status to 437 900 asylum seekers, up 6,9 % compared with 2023 (409 530); whereas this was the highest number since the peaks recorded after the refugee crisis related to the war in Syria in 2016 and 2017; whereas the recognition rate at the EU level, meaning the share of positive decisions among the total number of asylum decisions, was 51,4 % for first instance decisions in 2024;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-194339` Recital K

- **Result:** ADOPTED 341-234-91
- **A favour vote means:** For keeping Recital K as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital K (motion numbering unchanged (checked against the nearest quoted split)): K. whereas in 2024, 124 000 non-EU citizens were refused entry into the EU, 919 000 were found without status, 453 000 were issued return decisions and around 110 000 were effectively returned to a country outside the EU; whereas roughly 20 % of those who were issued return decisions were actually returned;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-194341` Recital Q – Am 6

- **Result:** REJECTED 236-425-7
- **A favour vote means:** For amendment 6 (amending Recital Q). Its words are not in the store.
- **Lobbies:** EPP 36-131-4, S&D 3-126-0, PfE 76-0-1, ECR 79-0-0, Renew 2-66-0, Greens 0-48-0, Left 0-43-0, ESN 25-0-0, NI 14-10-2, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194345` Recital U

- **Result:** ADOPTED 419-226-20
- **A favour vote means:** For keeping Recital U as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital U (motion numbering unchanged (checked against the nearest quoted split)): U. whereas the EU Pact on Migration and Asylum emphasises the importance of the external dimension of migration by developing comprehensive partnerships based on political dialogue, mutual commitment and a whole-of-route approach;
- **Lobbies:** EPP 162-2-5, S&D 120-2-6, PfE 0-78-0, ECR 51-26-3, Renew 67-0-0, Greens 1-43-4, Left 0-42-0, ESN 0-25-0, NI 18-6-2, ? 0-2-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194351` Recital AC/2: ‘and developing legal migration pathways;’

- **Result:** ADOPTED 442-178-46
- **A favour vote means:** For keeping the words ‘and developing legal migration pathways;’
- **Text:** Adopted recital AC (quote found in the adopted text): AC. whereas development cooperation plays an essential role in contributing to addressing the root causes of irregular migration and forced displacement, as well as combating the smuggling of human beings, protecting refugees and people in need of international protection, supporting refugee-hosting countries and developing legal migration pathways;
- **Lobbies:** EPP 154-16-0, S&D 124-1-1, PfE 0-78-0, ECR 2-38-41, Renew 62-6-0, Greens 47-0-0, Left 43-0-0, ESN 0-25-0, NI 9-13-4, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194355` After recital AI – Am 7

- **Result:** REJECTED 218-419-30
- **A favour vote means:** For amendment 7 (inserting After recital AI). Its words are not in the store.
- **Lobbies:** EPP 23-125-21, S&D 2-124-3, PfE 78-0-0, ECR 76-0-4, Renew 0-67-0, Greens 0-48-0, Left 0-43-0, ESN 24-1-0, NI 14-10-2, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194356` Recital AJ – Am 8

- **Result:** REJECTED 221-426-21
- **A favour vote means:** For amendment 8 (amending Recital AJ). Its words are not in the store.
- **Lobbies:** EPP 31-131-7, S&D 0-123-6, PfE 76-1-1, ECR 76-0-5, Renew 0-68-0, Greens 0-48-0, Left 0-42-0, ESN 24-1-0, NI 13-11-2, ? 1-1-0
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

### [ ] `MTG-PL-2026-06-16-DEC-194357` Motion for a resolution (as a whole)

- **Result:** ADOPTED 344-237-66
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 104-32-21, S&D 121-0-5, PfE 0-75-0, ECR 3-49-27, Renew 65-1-2, Greens 48-0-0, Left 0-42-1, ESN 0-24-0, NI 3-13-9, ? 0-1-1
- **Proposed:** evidence only, never places -- A development and migration report. Migration (area 11) is collated but excluded from the 5CA (config/stance_overrides.yaml); this report's freedom-of-religion tag rests on one passing mention in recital A.

## Transnational repression report (2026-06-16)

### [ ] `MTG-PL-2026-06-16-DEC-193893` § 7 – Am 2

- **Result:** REJECTED 201-462-7
- **A favour vote means:** For amendment 2 (amending § 7). Its words are not in the store.
- **Lobbies:** EPP 6-164-1, S&D 0-131-0, PfE 78-0-0, ECR 75-1-4, Renew 0-68-0, Greens 0-47-0, Left 0-42-0, ESN 25-0-0, NI 16-8-2, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-16-DEC-193896` § 25

- **Result:** ADOPTED 345-288-36
- **A favour vote means:** For keeping § 25 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 25 (adopted-text numbering assumed equal to the motion (unchecked)): 25. Highlights the needs for prevention, protection, stabilisation, accountability and deterrence, and the need to address existing protection gaps, including access to legal and administrative assistance, and psychosocial support; further stresses the need to develop rapid response capabilities within the competent authorities;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-193899` § 26

- **Result:** ADOPTED 331-305-34
- **A favour vote means:** For keeping § 26 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 26 (adopted-text numbering assumed equal to the motion (unchecked)): 26. Highlights the serious psychological, social and security consequences of TNR for victims and their families; calls on the Member States to recognise psychosocial harm as an integral feature of TNR and to ensure access to multilingual, and trauma-informed mental health support; recalls in that respect the consequences and psychological burden caused by strategic lawsuits against public participation (SLAPPs) on journalists or legal pressure on academics;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-193902` § 38

- **Result:** ADOPTED 386-254-30
- **A favour vote means:** For keeping § 38 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 38 (adopted-text numbering assumed equal to the motion (unchecked)): 38. Recalls the report by its PEGA Committee (Committee of Inquiry to investigate the use of Pegasus and equivalent surveillance spyware), which contained recommendations on combating the illegal use of spyware, in particular intrusive spyware; laments that the Commission, to this date, has not taken the recommendations on board, even though issues prevail; calls, in that context, on Member States and the Commission to implement the recommendations of Parliament’s PEGA Committee, and to strengthen safeguards against spyware proliferation and abuse, and counter deficiencies in national legislation through better en
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-193903` § 41

- **Result:** ADOPTED 336-288-43
- **A favour vote means:** For keeping § 41 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 41 (adopted-text numbering assumed equal to the motion (unchecked)): 41. Stresses that family reunification and other protective pathways reduce exposure to coercion-by-proxy;
- **Lobbies:** EPP 6-157-4, S&D 127-1-3, PfE 0-72-6, ECR 42-16-22, Renew 63-4-0, Greens 48-0-0, Left 43-0-0, ESN 0-25-0, NI 6-12-8, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on transnational repression report policy, not on our issues.

### [ ] `MTG-PL-2026-06-16-DEC-193906` § 45

- **Result:** REJECTED 305-356-8
- **A favour vote means:** For keeping § 45 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 45 (adopted-text numbering assumed equal to the motion (unchecked)): 45. Calls on the Member States to remain vigilant and refuse, document and report informal, coercive or extralegal requests from foreign authorities to surveil, detain, restrict, intimidate or hand over exiles or members of diaspora communities, including when such requests are conveyed through diplomatic channels; calls, in this context, for enhanced scrutiny involving persons at risk of TNR; further calls on Member States to refrain from extraditing victims or potential victims of TNR and to ensure their protection within the EU;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-193909` § 60

- **Result:** REJECTED 295-364-11
- **A favour vote means:** For keeping § 60 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 60 (adopted-text numbering assumed equal to the motion (unchecked)): 60. Invites the Member States to ensure that the individual circumstances of applicants who are victims of TNR are properly addressed; calls on the Member States and other Schengen area countries to use the EU’s Visa Code and Handbook consistently and flexibly to address protection needs for persons targeted by TNR;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-193912` § 61

- **Result:** REJECTED 300-354-18
- **A favour vote means:** For keeping § 61 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 61 (adopted-text numbering assumed equal to the motion (unchecked)): 61. Stresses the need to increase the cost of TNR and strengthen deterrence, including through effective investigation and prosecution of perpetrators and enablers; calls on the Member States to establish clear legal liability for individuals and entities who knowingly facilitate or profit from acts of TNR on behalf of foreign states; calls furthermore for the effective implementation of corporate human rights due diligence obligations, including under the Directive on corporate sustainability due diligence; believes that an adequate measure to counter the rising phenomenon of TNR perpetrated by authoritarian regi
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-16-DEC-193913` Motion for a resolution (as a whole)

- **Result:** ADOPTED 434-128-104
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 169-0-1, S&D 126-0-0, PfE 0-72-6, ECR 11-11-58, Renew 68-0-0, Greens 46-0-2, Left 12-0-31, ESN 0-25-0, NI 1-19-6, ? 1-1-0
- **Proposed:** evidence only, never places -- A resolution on authoritarian states' repression of dissidents abroad. Its free-speech tag rests on the digital-repression paragraphs (§§ 34-35, 39), which ask platforms to act against state-sponsored censorship and harassment, partly under the DSA. Protecting dissidents cuts neither way for CitizenGO.
- **Flag for you:** If you read §§ 34-35 as DSA enforcement over speech (the Democracy Shield reading), the side would be against. Drafted evidence-only.

## Türkiye 2025 report (2026-06-17)

### [ ] `MTG-PL-2026-06-17-DEC-194044` § 1 – Am 33

- **Result:** REJECTED 179-445-27
- **A favour vote means:** For amendment 33 (amending § 1). Its words are not in the store.
- **Lobbies:** EPP 14-153-1, S&D 3-122-0, PfE 70-0-0, ECR 49-11-19, Renew 0-68-2, Greens 0-45-1, Left 0-42-0, ESN 26-0-0, NI 17-3-4, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194045` § 1 – Am 8

- **Result:** REJECTED 123-512-21
- **A favour vote means:** For amendment 8 (amending § 1). Its words are not in the store.
- **Lobbies:** EPP 13-155-0, S&D 0-125-0, PfE 64-6-7, ECR 16-61-1, Renew 0-70-0, Greens 0-45-0, Left 0-41-0, ESN 26-0-0, NI 4-8-12, ? 0-1-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194046` After § 5 – Am 34

- **Result:** REJECTED 173-448-20
- **A favour vote means:** For amendment 34 (inserting After § 5). Its words are not in the store.
- **Lobbies:** EPP 16-150-1, S&D 3-116-0, PfE 64-0-6, ECR 50-26-2, Renew 0-69-2, Greens 0-45-1, Left 0-40-0, ESN 25-0-0, NI 15-1-8, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194047` § 6 – Am 1

- **Result:** REJECTED 236-377-42
- **A favour vote means:** For amendment 1 (amending § 6). Its words are not in the store.
- **Lobbies:** EPP 11-157-0, S&D 10-113-0, PfE 68-7-0, ECR 51-5-21, Renew 69-2-0, Greens 3-43-0, Left 2-31-9, ESN 17-9-0, NI 5-8-12, ? 0-2-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194048` § 12 – Am 2

- **Result:** ADOPTED 327-291-40
- **A favour vote means:** For amendment 2 (amending § 12). Its words are not in the store.
- **Lobbies:** EPP 4-162-1, S&D 19-105-0, PfE 54-7-15, ECR 73-1-5, Renew 71-0-0, Greens 46-0-0, Left 42-0-0, ESN 1-9-15, NI 16-6-4, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194050` § 22 – Am 4

- **Result:** ADOPTED 342-260-61
- **A favour vote means:** For amendment 4 (amending § 22). Its words are not in the store.
- **Lobbies:** EPP 20-147-2, S&D 23-101-0, PfE 64-0-13, ECR 76-1-2, Renew 70-1-0, Greens 46-0-0, Left 8-0-35, ESN 18-5-3, NI 16-5-5, ? 1-0-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194051` After § 26 – Am 35

- **Result:** REJECTED 256-373-17
- **A favour vote means:** For amendment 35 (inserting After § 26). Its words are not in the store.
- **Lobbies:** EPP 63-105-2, S&D 0-112-1, PfE 76-0-0, ECR 77-1-1, Renew 3-68-0, Greens 0-46-0, Left 0-40-0, ESN 22-0-3, NI 14-0-10, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194052` After § 35 – Am 36

- **Result:** REJECTED 213-433-13
- **A favour vote means:** For amendment 36 (inserting After § 35). Its words are not in the store.
- **Lobbies:** EPP 22-147-0, S&D 3-121-0, PfE 77-0-0, ECR 73-2-3, Renew 0-70-0, Greens 0-45-1, Left 0-42-0, ESN 18-0-7, NI 19-5-2, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194053` After § 35 – Am 42

- **Result:** REJECTED 135-502-13
- **A favour vote means:** For amendment 42 (inserting After § 35). Its words are not in the store.
- **Lobbies:** EPP 1-164-0, S&D 37-82-1, PfE 0-76-1, ECR 1-74-2, Renew 6-63-2, Greens 41-2-1, Left 42-0-0, ESN 2-24-0, NI 4-16-6, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194054` § 36 – Am 13

- **Result:** REJECTED 196-457-5
- **A favour vote means:** For amendment 13 (amending § 36). Its words are not in the store.
- **Lobbies:** EPP 1-165-2, S&D 0-124-0, PfE 77-0-0, ECR 74-3-1, Renew 0-70-0, Greens 0-46-0, Left 0-42-0, ESN 24-1-0, NI 19-5-2, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194055` After § 36 – Am 14

- **Result:** REJECTED 185-458-10
- **A favour vote means:** For amendment 14 (inserting After § 36). Its words are not in the store.
- **Lobbies:** EPP 7-160-1, S&D 0-124-0, PfE 69-6-0, ECR 73-3-2, Renew 0-70-0, Greens 0-45-0, Left 0-43-0, ESN 24-0-0, NI 12-5-7, ? 0-2-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194056` After § 37 – Am 37

- **Result:** REJECTED 204-436-6
- **A favour vote means:** For amendment 37 (inserting After § 37). Its words are not in the store.
- **Lobbies:** EPP 9-156-3, S&D 0-122-0, PfE 69-0-0, ECR 78-1-0, Renew 2-69-0, Greens 1-45-0, Left 0-40-0, ESN 26-0-0, NI 19-2-3, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194057` After § 37 – Am 39

- **Result:** REJECTED 229-401-12
- **A favour vote means:** For amendment 39 (inserting After § 37). Its words are not in the store.
- **Lobbies:** EPP 23-140-6, S&D 1-107-1, PfE 77-0-0, ECR 78-1-0, Renew 0-68-1, Greens 0-46-0, Left 1-38-2, ESN 26-0-0, NI 22-0-2, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194058` § 39 – Am 29

- **Result:** REJECTED 193-431-28
- **A favour vote means:** For amendment 29 (amending § 39). Its words are not in the store.
- **Lobbies:** EPP 7-155-6, S&D 1-121-0, PfE 65-0-12, ECR 74-0-3, Renew 2-69-0, Greens 0-45-0, Left 0-40-0, ESN 25-0-1, NI 19-0-5, ? 0-1-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194059` § 40 – Am 30

- **Result:** REJECTED 224-408-9
- **A favour vote means:** For amendment 30 (amending § 40). Its words are not in the store.
- **Lobbies:** EPP 23-144-2, S&D 1-111-0, PfE 77-0-0, ECR 73-1-3, Renew 1-70-0, Greens 0-46-0, Left 0-35-2, ESN 26-0-0, NI 22-0-2, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194060` § 40 – Am 31

- **Result:** REJECTED 241-345-31
- **A favour vote means:** For amendment 31 (amending § 40). Its words are not in the store.
- **Lobbies:** EPP 7-146-1, S&D 1-108-0, PfE 70-0-0, ECR 76-1-1, Renew 52-5-12, Greens 0-46-0, Left 0-38-2, ESN 13-0-13, NI 22-0-2, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194061` § 40 – Am 32

- **Result:** REJECTED 207-428-4
- **A favour vote means:** For amendment 32 (amending § 40). Its words are not in the store.
- **Lobbies:** EPP 13-153-2, S&D 1-118-0, PfE 68-0-0, ECR 77-1-0, Renew 2-69-0, Greens 1-45-0, Left 0-40-0, ESN 24-1-0, NI 21-0-2, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194069` After § 43 – Am 48

- **Result:** REJECTED 186-403-69
- **A favour vote means:** For amendment 48 (inserting After § 43). Its words are not in the store.
- **Lobbies:** EPP 9-158-2, S&D 8-114-2, PfE 64-10-3, ECR 34-15-30, Renew 1-68-0, Greens 2-35-8, Left 42-0-0, ESN 6-1-18, NI 19-1-6, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194070` After § 43 – Am 49

- **Result:** REJECTED 89-447-116
- **A favour vote means:** For amendment 49 (inserting After § 43). Its words are not in the store.
- **Lobbies:** EPP 9-160-0, S&D 9-109-3, PfE 2-25-50, ECR 3-58-15, Renew 0-68-0, Greens 5-2-39, Left 42-0-0, ESN 2-17-7, NI 16-7-2, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194071` § 46 – Am 5

- **Result:** ADOPTED 307-294-53
- **A favour vote means:** For amendment 5 (amending § 46). Its words are not in the store.
- **Lobbies:** EPP 13-156-0, S&D 20-105-0, PfE 68-0-9, ECR 76-2-0, Renew 69-1-0, Greens 45-0-0, Left 3-2-35, ESN 4-20-2, NI 8-8-6, ? 1-0-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194072` After § 46 – Am 40

- **Result:** REJECTED 224-401-17
- **A favour vote means:** For amendment 40 (inserting After § 46). Its words are not in the store.
- **Lobbies:** EPP 32-131-4, S&D 1-111-1, PfE 75-0-0, ECR 75-0-0, Renew 3-67-0, Greens 0-46-0, Left 0-42-0, ESN 24-0-2, NI 13-3-10, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194073` After § 48 – Am 17

- **Result:** REJECTED 144-430-58
- **A favour vote means:** For amendment 17 (inserting After § 48). Its words are not in the store.
- **Lobbies:** EPP 10-144-8, S&D 0-120-0, PfE 61-8-5, ECR 33-5-38, Renew 0-65-0, Greens 0-45-0, Left 0-38-2, ESN 24-0-0, NI 15-4-5, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194074` After § 49 – Am 38

- **Result:** REJECTED 207-412-24
- **A favour vote means:** For amendment 38 (inserting After § 49). Its words are not in the store.
- **Lobbies:** EPP 13-146-6, S&D 0-118-0, PfE 77-0-0, ECR 78-1-0, Renew 2-65-0, Greens 0-39-6, Left 0-42-0, ESN 18-0-8, NI 19-0-4, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194075` § 57 – Am 6

- **Result:** REJECTED 202-348-107
- **A favour vote means:** For amendment 6 (amending § 57). Its words are not in the store.
- **Lobbies:** EPP 3-165-2, S&D 5-114-5, PfE 55-7-15, ECR 50-9-19, Renew 69-0-0, Greens 1-0-45, Left 8-23-8, ESN 2-24-0, NI 8-5-13, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-194076` After § 64 – Am 18

- **Result:** REJECTED 202-433-16
- **A favour vote means:** For amendment 18 (inserting After § 64). Its words are not in the store.
- **Lobbies:** EPP 15-147-8, S&D 0-124-0, PfE 71-0-0, ECR 77-1-0, Renew 0-70-0, Greens 0-46-0, Left 1-42-0, ESN 25-0-0, NI 13-2-8, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-06-17-DEC-193623` § 40

- **Result:** REJECTED 260-357-44
- **A favour vote means:** For keeping § 40 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 40 (adopted-text numbering assumed equal to the motion (unchecked)): 40. Welcomes the steps taken by the UN Secretary-General towards a resumption of comprehensive settlement talks, including his appointment of a Personal Envoy on Cyprus; calls on the Commission to rapidly appoint a new European Commission Special Envoy for Cyprus; welcomes the two informal meetings held in a broader format, under the auspices of the UN Secretary-General, in Geneva in March 2025 and New York in July 2025, as well as the various meetings in Cyprus of President Nikos Christodoulides and leader of the Turkish Cypriot community Tufan Erhürman including the meeting of December 2025, in which a joint sta
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-06-17-DEC-193644` Motion for a resolution (as a whole)

- **Result:** ADOPTED 381-107-171
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 138-0-32, S&D 121-1-2, PfE 0-59-17, ECR 4-5-69, Renew 66-1-3, Greens 45-0-0, Left 4-0-38, ESN 0-26-0, NI 2-14-10, ? 1-1-0
- **Proposed:** evidence only, never places -- An enlargement country report pulling both ways for CitizenGO: press freedom (§ 16) and freedom of religion for minorities (§ 27) on one side, the Istanbul Convention (§ 20) and LGBTI rights (§ 21) on the other. The vote was on Türkiye's EU path.

### [ ] `MTG-PL-2026-06-17-DEC-194049` § 15 – Am 3

- **Result:** ADOPTED 555-56-50
- **A favour vote means:** For amendment 3 (amending § 15). Its words are not in the store.
- **Lobbies:** EPP 166-3-1, S&D 124-0-0, PfE 57-0-19, ECR 34-40-4, Renew 70-0-0, Greens 46-0-0, Left 43-0-0, ESN 1-11-14, NI 13-2-11, ? 1-0-1
- **Proposed:** evidence only, never places -- Near-unanimous (555-56): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

## Nicaragua political prisoners (2026-06-18)

### [ ] `MTG-PL-2026-06-18-DEC-194628` After § 3 – Am 1

- **Result:** REJECTED 186-336-37
- **A favour vote means:** For amendment 1 (inserting After § 3). Its words are not in the store.
- **Lobbies:** EPP 0-137-3, S&D 102-3-2, PfE 0-44-14, ECR 0-62-4, Renew 5-57-0, Greens 41-0-0, Left 35-1-0, ESN 0-21-3, NI 2-11-11, ? 1-0-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

## Recruitment of children by organised crime (2026-06-18)

### [ ] `MTG-PL-2026-06-18-DEC-194397` § 3

- **Result:** ADOPTED 431-58-78
- **A favour vote means:** For keeping § 3 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 3 (motion numbering unchanged (checked against the nearest quoted split)): 3. Recalls that a child is first and foremost a child and should be treated accordingly, and calls on the Member States to ensure that a child’s best interest is always the primary consideration;
- **Lobbies:** EPP 140-0-1, S&D 108-0-0, PfE 14-14-35, ECR 6-38-20, Renew 62-0-0, Greens 43-0-0, Left 37-0-0, ESN 3-5-15, NI 16-1-7, ? 2-0-0
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

### [ ] `MTG-PL-2026-06-18-DEC-194398` § 14 – Am 6

- **Result:** REJECTED 181-379-10
- **A favour vote means:** For amendment 6 (amending § 14). Its words are not in the store.
- **Lobbies:** EPP 11-125-6, S&D 0-108-0, PfE 62-0-1, ECR 65-0-0, Renew 0-61-1, Greens 0-42-1, Left 0-37-0, ESN 24-0-0, NI 18-5-1, ? 1-1-0
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

### [ ] `MTG-PL-2026-06-18-DEC-194400` § 14/1: ‘Emphasises that children involved in criminal activities as a result of recruitment must be considere…

- **Result:** ADOPTED 509-48-9
- **A favour vote means:** For keeping the words ‘Emphasises that children involved in criminal activities as a result of recruitment must be considered and treated primarily as victims, regardless of their a…
- **Text:** Adopted § 14 (quote found in the adopted text): 14. Emphasises that children involved in criminal activities as a result of recruitment must be treated in line with international standards; recalls that engagement with violent groups is often driven by gradual coercion and group dynamics rather than ideological adherence;
- **Lobbies:** EPP 136-3-1, S&D 107-0-0, PfE 23-39-1, ECR 62-1-3, Renew 59-1-0, Greens 43-0-0, Left 37-0-0, ESN 18-4-2, NI 22-0-2, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (509-48): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-06-18-DEC-194401` § 14/2: those words

- **Result:** REJECTED 262-291-15
- **A favour vote means:** For keeping the word(s) the previous part's split separated out (the label does not repeat them).
- **Lobbies:** EPP 1-140-0, S&D 108-0-0, PfE 1-57-5, ECR 2-61-3, Renew 61-1-0, Greens 43-0-0, Left 37-0-0, ESN 1-22-1, NI 7-10-5, ? 1-0-1
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

### [ ] `MTG-PL-2026-06-18-DEC-194404` § 15/2: ‘recalls that under Directive (EU) 2016/800, deprivation of a child’s liberty, in particular detention…

- **Result:** ADOPTED 409-144-11
- **A favour vote means:** For keeping the words ‘recalls that under Directive (EU) 2016/800, deprivation of a child’s liberty, in particular detention, should be imposed only as a measure of last resort and,…
- **Text:** Adopted § 16 (quote found in the adopted text): 16. Calls for child-friendly, gender-responsive and trauma-informed justice systems and tailored cross-sectoral, trauma-informed reintegration programmes, including access to education, mental health and psychosocial support and recovery and rehabilitation services, protection from retaliation, including for the families, pathways to decent employment and measures to prevent stigmatisation and repeated recruitment; recalls that under Directive (EU) 2016/800, deprivation of a child’s liberty, in particular detention, should be imposed only as a measure of last resort and, where possible, Member States’ competent authorities should have recourse 
- **Lobbies:** EPP 139-0-1, S&D 108-0-0, PfE 6-54-3, ECR 3-61-1, Renew 60-0-0, Greens 41-1-0, Left 37-0-0, ESN 0-23-1, NI 13-5-5, ? 2-0-0
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

### [ ] `MTG-PL-2026-06-18-DEC-194406` After § 15 – Am 7

- **Result:** REJECTED 176-249-140
- **A favour vote means:** For amendment 7 (inserting After § 15). Its words are not in the store.
- **Lobbies:** EPP 9-0-128, S&D 1-106-0, PfE 57-0-6, ECR 66-0-0, Renew 2-60-0, Greens 0-42-1, Left 0-35-2, ESN 24-0-0, NI 16-5-3, ? 1-1-0
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

### [ ] `MTG-PL-2026-06-18-DEC-194407` After § 15 – Am 8

- **Result:** REJECTED 167-363-36
- **A favour vote means:** For amendment 8 (inserting After § 15). Its words are not in the store.
- **Lobbies:** EPP 5-109-24, S&D 0-107-0, PfE 63-0-0, ECR 64-0-2, Renew 0-62-0, Greens 0-42-1, Left 0-37-0, ESN 22-0-2, NI 12-5-7, ? 1-1-0
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

### [ ] `MTG-PL-2026-06-18-DEC-194408` § 19 – Am 9

- **Result:** REJECTED 169-389-6
- **A favour vote means:** For amendment 9 (amending § 19). Its words are not in the store.
- **Lobbies:** EPP 5-132-3, S&D 0-105-0, PfE 63-0-0, ECR 63-0-2, Renew 0-61-0, Greens 0-43-0, Left 0-37-0, ESN 24-0-0, NI 13-10-1, ? 1-1-0
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

### [ ] `MTG-PL-2026-06-18-DEC-194544` § 14/3: ‘recalls that engagement with violent groups is often driven by gradual coercion and group dynamics ra…

- **Result:** ADOPTED 402-135-31
- **A favour vote means:** For keeping the words ‘recalls that engagement with violent groups is often driven by gradual coercion and group dynamics rather than ideological adherence;’
- **Text:** Adopted § 14 (quote found in the adopted text): 14. Emphasises that children involved in criminal activities as a result of recruitment must be treated in line with international standards; recalls that engagement with violent groups is often driven by gradual coercion and group dynamics rather than ideological adherence;
- **Lobbies:** EPP 135-3-4, S&D 107-0-0, PfE 0-63-0, ECR 2-41-22, Renew 62-0-0, Greens 41-0-1, Left 37-0-0, ESN 2-21-1, NI 15-6-3, ? 1-1-0
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

### [ ] `MTG-PL-2026-06-18-DEC-194545` After § 14 – Am 1

- **Result:** ADOPTED 372-139-58
- **A favour vote means:** For amendment 1 (inserting After § 14). Its words are not in the store.
- **Lobbies:** EPP 142-0-0, S&D 5-101-1, PfE 54-0-9, ECR 65-1-0, Renew 62-0-0, Greens 1-0-42, Left 1-34-2, ESN 23-0-1, NI 18-3-3, ? 1-0-0
- **Proposed:** evidence only, never places -- A criminal-justice text on children recruited by gangs. Its tags rest on a call for DSA enforcement to protect minors (§ 11) and 'family breakdown' as a risk factor (recital G); the votes are on youth justice.

## Media literacy strategy (2026-07-07)

### [ ] `MTG-PL-2026-07-07-DEC-195245` § 3 – Am 1

- **Result:** REJECTED 192-454-6
- **A favour vote means:** For amendment 1 (amending § 3). Its words are not in the store.
- **Lobbies:** EPP 0-173-0, S&D 1-126-0, PfE 74-0-0, ECR 71-0-2, Renew 1-70-3, Greens 1-48-0, Left 0-29-1, ESN 24-0-0, NI 19-7-0, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-07-DEC-195247` § 6 – Am 2

- **Result:** REJECTED 184-464-4
- **A favour vote means:** For amendment 2 (amending § 6). Its words are not in the store.
- **Lobbies:** EPP 1-171-2, S&D 0-128-0, PfE 71-3-0, ECR 69-1-2, Renew 0-73-0, Greens 0-49-0, Left 0-29-0, ESN 24-0-0, NI 18-9-0, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-07-DEC-195248` After § 6 – Am 3

- **Result:** REJECTED 164-461-29
- **A favour vote means:** For amendment 3 (inserting After § 6). Its words are not in the store.
- **Lobbies:** EPP 0-174-1, S&D 0-128-0, PfE 70-1-2, ECR 52-1-21, Renew 0-74-0, Greens 0-49-0, Left 0-28-0, ESN 24-0-0, NI 17-5-5, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-07-DEC-195250` § 10 – Am 4

- **Result:** REJECTED 191-455-4
- **A favour vote means:** For amendment 4 (amending § 10). Its words are not in the store.
- **Lobbies:** EPP 2-172-0, S&D 0-126-0, PfE 74-0-0, ECR 71-0-2, Renew 0-74-0, Greens 1-48-0, Left 0-29-0, ESN 24-0-0, NI 18-5-2, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-07-DEC-195254` § 16/2: the words ‘and, where appropriate, propose a clear common EU approach to age-appropriate access to onl…

- **Result:** ADOPTED 465-143-35
- **A favour vote means:** For keeping the words ‘and, where appropriate, propose a clear common EU approach to age-appropriate access to online platforms, particularly social media platforms, follo…
- **Text:** Adopted § 16 (quote found in the adopted text): 16. Calls on the Commission to assess and, where appropriate, propose a clear common EU approach to age-appropriate access to online platforms, particularly social media platforms, following an approach based on the protection of children’s well-being, a recognition of minors’ cognitive and emotional development needs, and the need to ensure a safe and age-appropriate digital environment, while fully respecting fundamental rights and differences in national approaches;
- **Lobbies:** EPP 171-0-0, S&D 122-0-1, PfE 7-56-10, ECR 5-46-22, Renew 72-0-0, Greens 49-1-0, Left 27-1-1, ESN 0-23-0, NI 11-16-0, ? 1-0-1
- **Proposed:** no direction -- The words call for 'a clear common EU approach to age-appropriate access to online platforms, particularly social media platforms'. Whether an EU-level minimum age protects children or takes the decision from parents and Member States is a policy call for you; no side drafted.
- **Flag for you:** Same question as the social media report's § 63/3 (harmonised EU minimum digital age), 17 September.

### [ ] `MTG-PL-2026-07-07-DEC-195258` After § 33 – Am 5

- **Result:** REJECTED 189-456-11
- **A favour vote means:** For amendment 5 (inserting After § 33). Its words are not in the store.
- **Lobbies:** EPP 5-170-0, S&D 1-127-0, PfE 74-0-0, ECR 72-0-2, Renew 0-74-0, Greens 0-50-0, Left 0-29-0, ESN 24-1-0, NI 12-4-9, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-07-DEC-194877` Motion for a resolution (as a whole)

- **Result:** ADOPTED 447-128-78
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 169-0-3, S&D 127-0-0, PfE 0-58-16, ECR 0-31-41, Renew 71-0-3, Greens 49-0-1, Left 28-0-2, ESN 0-25-0, NI 2-14-11, ? 1-0-1
- **Proposed:** evidence only, never places -- An education strategy. It ties media literacy to the Democracy Shield (§ 3), asks for indicators of 'resilience to disinformation' (§ 14) and DSA risk mitigation by very large platforms (§ 21), but also says media literacy must fully respect freedom of expression (§ 26). Its operative thrust is teaching, not speech regulation.
- **Flag for you:** Sign against instead if you read it as a companion to the Democracy Shield you signed against on 17 September. The lobbies are the same: Patriots, ECR and ESN against, the EPP for.

### [ ] `MTG-PL-2026-07-07-DEC-195246` § 3

- **Result:** ADOPTED 448-188-16
- **A favour vote means:** For keeping § 3 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 3 (motion numbering unchanged (checked against the nearest quoted split)): 3. Stresses that media literacy and digital learning should be reflected within broader EU initiatives aimed at safeguarding democratic processes, including in the context of the EU Democracy Shield;
- **Lobbies:** EPP 171-0-1, S&D 128-0-0, PfE 2-72-0, ECR 0-70-3, Renew 70-0-3, Greens 50-0-0, Left 21-2-7, ESN 0-24-0, NI 5-19-2, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on media literacy strategy policy, not on our issues.

### [ ] `MTG-PL-2026-07-07-DEC-195249` § 9

- **Result:** ADOPTED 461-121-74
- **A favour vote means:** For keeping § 9 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 9 (motion numbering unchanged (checked against the nearest quoted split)): 9. Underlines the importance of using all the relevant regulatory instruments available and of fostering cooperation between all relevant actors, as needed, to achieve an EU approach to media literacy and digital learning;
- **Lobbies:** EPP 175-0-0, S&D 127-1-0, PfE 0-69-5, ECR 1-15-57, Renew 70-0-3, Greens 50-0-0, Left 28-0-2, ESN 1-23-0, NI 8-12-7, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on media literacy strategy policy, not on our issues.

### [ ] `MTG-PL-2026-07-07-DEC-195251` § 14

- **Result:** ADOPTED 455-151-41
- **A favour vote means:** For keeping § 14 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 14 (motion numbering unchanged (checked against the nearest quoted split)): 14. Calls on the Commission, in cooperation with the Member States, to establish a structured monitoring and evaluation framework for national media literacy actions, including measurable indicators assessing knowledge, behavioural outcomes, the development of critical thinking, and resilience to disinformation, including through longitudinal studies and the evaluation of age-appropriate approaches and parental support programmes;
- **Lobbies:** EPP 173-0-0, S&D 124-1-0, PfE 1-72-0, ECR 2-37-34, Renew 69-3-0, Greens 49-0-0, Left 29-0-1, ESN 0-23-0, NI 7-14-6, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on media literacy strategy policy, not on our issues.

### [ ] `MTG-PL-2026-07-07-DEC-195257` § 27/2: ‘calls on the Commission to strengthen support for traditional media at European, national, regional, …

- **Result:** ADOPTED 497-138-17
- **A favour vote means:** For keeping the words ‘calls on the Commission to strengthen support for traditional media at European, national, regional, and local level, given their essential role in informing…
- **Text:** Adopted § 27 (quote found in the adopted text): 27. Stresses that media literacy depends not only on users’ ability to critically assess information, but also on the existence of strong, independent and high-quality journalism providing reliable, verified and pluralistic information; calls on the Commission to strengthen support for traditional media at European, national, regional, and local level, given their essential role in informing citizens, including by promoting fair remuneration for journalistic content and ensuring sustainable funding, notably through programmes such as the future AgoraEU programme;
- **Lobbies:** EPP 171-1-1, S&D 127-0-0, PfE 7-67-0, ECR 37-33-3, Renew 70-0-3, Greens 49-0-0, Left 30-0-0, ESN 0-25-0, NI 5-11-10, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on media literacy strategy policy, not on our issues.

### [ ] `MTG-PL-2026-07-07-DEC-195259` § 35

- **Result:** ADOPTED 473-174-7
- **A favour vote means:** For keeping § 35 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 35 (motion numbering unchanged (checked against the nearest quoted split)): 35. Calls on the Commission, in cooperation with the Member States, to provide a European guide and other educational materials on media literacy tailored to all age groups and educational levels, and to organise regular workshops, focusing on critical thinking, verification of information sources, media pluralism, responsible media participation, and the role of fact-checking organisations, journalistic self-regulatory bodies and community media, as well as guidance for parents and caregivers on age-appropriate media use, online risks and AI tools;
- **Lobbies:** EPP 172-3-0, S&D 125-2-0, PfE 4-69-0, ECR 17-53-1, Renew 70-4-0, Greens 50-0-0, Left 27-3-0, ESN 0-25-0, NI 7-14-6, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on media literacy strategy policy, not on our issues.

### [ ] `MTG-PL-2026-07-07-DEC-195262` § 43/2: the words ‘and civil society organisations’

- **Result:** ADOPTED 464-177-3
- **A favour vote means:** For keeping the words ‘and civil society organisations’
- **Lobbies:** EPP 173-0-1, S&D 127-1-0, PfE 1-69-0, ECR 1-68-2, Renew 72-0-0, Greens 50-0-0, Left 29-0-0, ESN 0-23-0, NI 10-15-0, ? 1-1-0
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on media literacy strategy policy, not on our issues.

## SDG resolution (2026 High-Level Political Forum) (2026-07-07)

### [x] `MTG-PL-2026-07-07-DEC-194870` SDG resolution (2026 High-Level Political Forum)

- **Signed side:** against

### [ ] `MTG-PL-2026-07-07-DEC-195295` paragraph 10 (SRHR in WASH)

- **Proposed:** no direction -- not read yet

## ePrivacy scanning derogation (2026-07-07)

### [x] `MTG-PL-2026-07-07-DEC-195338` fast-track request

- **Signed side:** against

## Cyprus 1974 resolution (2026-07-08)

### [x] `MTG-PL-2026-07-08-DEC-195626` the words "sexual and reproductive health and rights" in the rape-survivors paragraph (Am 1/11, part 2)

- **Signed side:** against

### [x] `MTG-PL-2026-07-08-DEC-195627` the words "safe and legal abortion" in the rape-survivors paragraph (Am 1/11, part 3)

- **Signed side:** against

### [x] `MTG-PL-2026-07-08-DEC-195637` Recital J, the Greek Orthodox Church as a societal actor

- **Signed side:** favor

### [ ] `MTG-PL-2026-07-08-DEC-195617` After § 1 – Am 15

- **Result:** REJECTED 194-445-7
- **A favour vote means:** For amendment 15 (inserting After § 1). Its words are not in the store.
- **Lobbies:** EPP 23-147-0, S&D 0-120-0, PfE 69-2-0, ECR 74-0-0, Renew 1-71-0, Greens 0-50-0, Left 4-33-0, ESN 6-16-4, NI 16-5-3, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195621` After § 2 – Am 8

- **Result:** REJECTED 243-384-27
- **A favour vote means:** For amendment 8 (inserting After § 2). Its words are not in the store.
- **Lobbies:** EPP 3-168-0, S&D 125-0-0, PfE 0-65-5, ECR 2-53-18, Renew 5-68-0, Greens 49-0-0, Left 38-0-0, ESN 0-25-1, NI 20-4-3, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195623` After § 5 – Am 9

- **Result:** REJECTED 234-367-51
- **A favour vote means:** For amendment 9 (inserting After § 5). Its words are not in the store.
- **Lobbies:** EPP 4-161-1, S&D 120-3-0, PfE 1-51-20, ECR 2-49-24, Renew 1-71-0, Greens 50-0-0, Left 39-0-0, ESN 1-25-0, NI 15-6-6, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195628` After § 9 – Am 12

- **Result:** ADOPTED 489-142-14
- **A favour vote means:** For amendment 12 (inserting After § 9). Its words are not in the store.
- **Lobbies:** EPP 160-4-3, S&D 124-0-0, PfE 29-41-1, ECR 5-66-0, Renew 71-0-3, Greens 47-0-1, Left 39-0-0, ESN 1-23-0, NI 12-7-6, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195629` After § 14 – Am 13

- **Result:** ADOPTED 348-282-26
- **A favour vote means:** For amendment 13 (inserting After § 14). Its words are not in the store.
- **Lobbies:** EPP 170-0-2, S&D 8-117-0, PfE 67-0-5, ECR 72-1-0, Renew 2-72-0, Greens 1-49-0, Left 3-25-10, ESN 6-16-3, NI 18-1-6, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195630` After § 19 – Am 14

- **Result:** ADOPTED 358-166-122
- **A favour vote means:** For amendment 14 (inserting After § 19). Its words are not in the store.
- **Lobbies:** EPP 171-0-0, S&D 7-4-112, PfE 71-0-0, ECR 73-0-0, Renew 1-72-0, Greens 0-49-0, Left 3-22-9, ESN 9-17-0, NI 22-1-1, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195631` After § 22 – Am 16

- **Result:** REJECTED 196-423-17
- **A favour vote means:** For amendment 16 (inserting After § 22). Its words are not in the store.
- **Lobbies:** EPP 24-144-0, S&D 0-117-0, PfE 72-0-0, ECR 71-0-2, Renew 1-71-0, Greens 0-49-0, Left 3-22-9, ESN 9-14-1, NI 15-6-4, ? 1-0-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195633` After recital C – Am 2

- **Result:** ADOPTED 374-233-45
- **A favour vote means:** For amendment 2 (inserting After recital C). Its words are not in the store.
- **Lobbies:** EPP 7-165-1, S&D 119-4-0, PfE 42-0-29, ECR 22-48-3, Renew 70-0-0, Greens 50-0-0, Left 40-0-0, ESN 4-14-5, NI 19-2-6, ? 1-0-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195634` After recital I – Am 4

- **Result:** ADOPTED 383-239-34
- **A favour vote means:** For amendment 4 (inserting After recital I). Its words are not in the store.
- **Lobbies:** EPP 17-153-2, S&D 123-0-0, PfE 57-3-11, ECR 7-60-8, Renew 70-0-3, Greens 48-0-0, Left 39-0-0, ESN 2-20-4, NI 19-3-5, ? 1-0-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195635` After recital I – Am 5

- **Result:** REJECTED 274-323-51
- **A favour vote means:** For amendment 5 (inserting After recital I). Its words are not in the store.
- **Lobbies:** EPP 8-158-4, S&D 117-0-6, PfE 0-61-10, ECR 0-69-5, Renew 42-5-21, Greens 50-0-0, Left 39-0-0, ESN 1-23-0, NI 16-6-5, ? 1-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195420` § 6

- **Result:** REJECTED 301-312-49
- **A favour vote means:** For keeping § 6 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 6 (motion numbering unchanged (checked against the nearest quoted split)): 6. Recognises the consequences of the forced displacement, including internal displacement, resulting from the invasion and ongoing occupation, and its enduring impact on first-, second- and third-generation Cypriots, particularly women and girls, who have been disproportionately affected; highlights that many have experienced the loss of homes, community networks and cultural continuity, as well as intergenerational trauma, identity fragmentation and persistent feelings of dislocation and non-belonging, compounded by gender inequalities and the specific social expectations placed upon women; emphasises that
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-07-08-DEC-195427` Recital E

- **Result:** ADOPTED 335-308-15
- **A favour vote means:** For keeping Recital E as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital E (adopted-text numbering assumed equal to the motion (unchecked)): E. whereas the Republic of Cyprus remains the only EU Member State of which the territory is partially under illegal military occupation by a third country, with long-lasting consequences for all Cypriots, particularly women and girls, and for the EU;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-07-08-DEC-195619` § 2/1: ‘Stresses that the Republic of Türkiye bears continuing responsibility under international law for the …

- **Result:** ADOPTED 628-18-11
- **A favour vote means:** For keeping the words ‘Stresses that the Republic of Türkiye bears continuing responsibility under international law for the violations committed during and after the 1974 invasion,…
- **Text:** Adopted § 2 (quote found in the adopted text): 2. Stresses that the Republic of Türkiye bears continuing responsibility under international law for the violations committed during and after the 1974 invasion, which include grave breaches of the Geneva Conventions, and recalls that such responsibility entails the obligation to ensure that victims are provided full reparation, including restitution, rehabilitation, satisfaction and guarantees of non-repetition; calls on the Member States to ensure the provision of effective reparation for all victims of gender-based violence, including sexual violence; recalls that such reparation should be adequate, promptly attributed, and holistic in order 
- **Lobbies:** EPP 173-0-0, S&D 126-0-0, PfE 63-0-7, ECR 73-0-0, Renew 72-0-0, Greens 50-0-0, Left 40-0-0, ESN 3-17-4, NI 26-1-0, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (628-18): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-07-08-DEC-195620` § 2/2: ‘calls on the Member States to ensure the provision of effective reparation for all victims of gender-b…

- **Result:** ADOPTED 567-41-50
- **A favour vote means:** For keeping the words ‘calls on the Member States to ensure the provision of effective reparation for all victims of gender-based violence, including sexual violence; recalls that s…
- **Text:** Adopted § 2 (quote found in the adopted text): 2. Stresses that the Republic of Türkiye bears continuing responsibility under international law for the violations committed during and after the 1974 invasion, which include grave breaches of the Geneva Conventions, and recalls that such responsibility entails the obligation to ensure that victims are provided full reparation, including restitution, rehabilitation, satisfaction and guarantees of non-repetition; calls on the Member States to ensure the provision of effective reparation for all victims of gender-based violence, including sexual violence; recalls that such reparation should be adequate, promptly attributed, and holistic in order 
- **Lobbies:** EPP 168-1-0, S&D 125-1-0, PfE 30-18-24, ECR 55-1-20, Renew 73-0-0, Greens 49-0-0, Left 40-0-0, ESN 1-19-4, NI 24-1-2, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (567-41): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-07-08-DEC-195622` § 5

- **Result:** ADOPTED 615-33-3
- **A favour vote means:** For keeping § 5 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 5 (motion numbering unchanged (checked against the nearest quoted split)): 5. Calls on Türkiye to withdraw its troops from Cyprus and refrain from any unilateral action that would entrench the permanent occupation of the island and from action altering the demographic balance;
- **Lobbies:** EPP 161-9-0, S&D 122-0-0, PfE 66-5-0, ECR 71-1-0, Renew 72-1-0, Greens 49-0-0, Left 39-0-0, ESN 8-16-2, NI 25-1-1, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (615-33): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-07-08-DEC-195625` § 9 – Am 1= 11=/1

- **Result:** ADOPTED 453-141-45
- **A favour vote means:** For amendment 1= 11=/1 (amending § 9). Its words are not in the store.
- **Lobbies:** EPP 62-100-3, S&D 122-0-0, PfE 40-12-15, ECR 44-3-22, Renew 71-0-2, Greens 50-0-0, Left 39-0-0, ESN 2-22-1, NI 21-4-2, ? 2-0-0
- **Proposed:** evidence only, never places -- Part 1 of the identical Renew and S&D amendments to § 9: the rape-survivors services list WITHOUT the SRHR and abortion words, which were put as parts 2 and 3 and are signed (195626, 195627).

### [ ] `MTG-PL-2026-07-08-DEC-195632` Recital B

- **Result:** ADOPTED 625-7-25
- **A favour vote means:** For keeping Recital B as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital B (adopted-text numbering assumed equal to the motion (unchecked)): B. whereas the occupying regime, which is a result of the 1974 Turkish invasion and is subordinate to Türkiye, is illegal and is not internationally recognised; whereas the perpetrators of the gender-based violence were predominantly members of the Turkish armed forces, who were reportedly acting at the direction of and/or under the protection of their officers;
- **Lobbies:** EPP 170-2-1, S&D 122-3-0, PfE 67-0-5, ECR 72-1-0, Renew 71-1-0, Greens 49-0-0, Left 39-0-0, ESN 9-0-17, NI 24-0-2, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (625-7): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-07-08-DEC-195636` Recital J – Am 6

- **Result:** REJECTED 292-348-10
- **A favour vote means:** For amendment 6 (amending Recital J). Its words are not in the store.
- **Lobbies:** EPP 3-168-1, S&D 117-4-0, PfE 0-71-0, ECR 0-73-0, Renew 72-0-1, Greens 50-0-0, Left 37-0-0, ESN 0-21-4, NI 12-10-4, ? 1-1-0
- **Proposed:** evidence only, never places -- The Left's amendment 6 to strike or alter recital J (the Greek Orthodox Church as a societal actor). The recital J vote itself is signed (195637, our side favour); reading this one too would count the same members twice.

### [ ] `MTG-PL-2026-07-08-DEC-195638` Motion for a resolution (as a whole)

- **Result:** ADOPTED 575-33-43
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 161-0-4, S&D 123-0-2, PfE 56-10-4, ECR 48-1-24, Renew 73-0-1, Greens 49-1-0, Left 39-0-1, ESN 3-20-2, NI 21-1-5, ? 2-0-0
- **Proposed:** evidence only, never places -- Near-unanimous (575-33): the resolution on crimes committed by Turkish forces in 1974. Its abortion and SRHR words in § 9 were voted separately and are signed (195626, 195627); the whole text tells almost no MEP apart.

## Moldova 2025 report (2026-07-08)

### [ ] `MTG-PL-2026-07-08-DEC-195407` After § 48 – Am 10

- **Result:** REJECTED 108-535-8
- **A favour vote means:** For amendment 10 (inserting After § 48). Its words are not in the store.
- **Lobbies:** EPP 2-165-1, S&D 1-122-0, PfE 56-13-1, ECR 7-69-2, Renew 1-71-0, Greens 0-49-0, Left 1-38-0, ESN 24-1-0, NI 16-5-4, ? 0-2-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195408` After § 51 – Am 11

- **Result:** REJECTED 99-545-14
- **A favour vote means:** For amendment 11 (inserting After § 51). Its words are not in the store.
- **Lobbies:** EPP 3-168-2, S&D 0-125-0, PfE 55-14-1, ECR 6-68-3, Renew 0-70-0, Greens 0-50-0, Left 0-38-0, ESN 25-1-0, NI 10-9-8, ? 0-2-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-195409` After § 52 – Am 12

- **Result:** REJECTED 102-537-8
- **A favour vote means:** For amendment 12 (inserting After § 52). Its words are not in the store.
- **Lobbies:** EPP 0-168-0, S&D 0-124-0, PfE 54-14-0, ECR 8-65-3, Renew 0-72-0, Greens 0-49-0, Left 1-36-1, ESN 24-1-0, NI 15-6-4, ? 0-2-0
- **Proposed:** no direction -- Amendment 12 sits after § 52, the paragraph on the instrumentalisation of religious structures in Moldova; its text is not in the store. Patriots and ESN for, everyone else against (102-537).
- **Flag for you:** If it defended the Moldovan Orthodox Church against the § 52 framing, it may be ours; read it first.

### [ ] `MTG-PL-2026-07-08-DEC-194906` § 2

- **Result:** ADOPTED 502-100-37
- **A favour vote means:** For keeping § 2 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 2 (adopted-text numbering assumed equal to the motion (unchecked)): 2. Welcomes the opening of accession negotiations on cluster 1 (Fundamentals) on 15 June 2026 following the successful completion of the bilateral screening process in September 2025 and the subsequent start of technical talks on the negotiation clusters; welcomes the Commission’s assessment that all six negotiation clusters are ready to be opened; urges the Council to take a merit-based approach and formally open all clusters without any further delay; reminds the Member States of the principle of sincere cooperation under Article 4(3) of the Treaty on European Union, which requires them to refrain from any measur
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-07-08-DEC-194917` Motion for a resolution (as a whole)

- **Result:** ADOPTED 505-115-45
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 169-1-3, S&D 126-0-0, PfE 7-55-10, ECR 68-6-4, Renew 74-0-0, Greens 49-0-0, Left 8-11-20, ESN 1-24-0, NI 2-18-7, ? 1-0-1
- **Proposed:** evidence only, never places -- An enlargement country report. Its only on-ground passage is § 52, on the instrumentalisation of religious structures (the Moscow-aligned church) for Russian influence; the vote was on Moldova's EU path.

## Serbia 2025 report (2026-07-08)

### [ ] `MTG-PL-2026-07-08-DEC-195342` § 20 – Am 1

- **Result:** REJECTED 113-514-22
- **A favour vote means:** For amendment 1 (amending § 20). Its words are not in the store.
- **Lobbies:** EPP 1-165-0, S&D 0-125-0, PfE 14-55-0, ECR 57-17-2, Renew 1-73-0, Greens 3-47-0, Left 19-7-9, ESN 2-22-1, NI 14-3-10, ? 2-0-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-08-DEC-194935` Motion for a resolution (as a whole)

- **Result:** ADOPTED 468-116-79
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 162-2-8, S&D 125-0-0, PfE 6-61-3, ECR 46-5-28, Renew 71-1-2, Greens 48-1-0, Left 6-3-31, ESN 1-23-2, NI 3-19-4, ? 0-1-1
- **Proposed:** evidence only, never places -- An enlargement country report; its freedom-of-religion and civil-society lines are passing. The vote was on Serbia's EU path.

## Maria Shahbaz / girls in Pakistan (2026-07-09)

### [ ] `MTG-PL-2026-07-09-DEC-195770` After § 3 – Am 1

- **Result:** ADOPTED 301-281-14
- **A favour vote means:** For amendment 1 (inserting After § 3). Its words are not in the store.
- **Lobbies:** EPP 130-17-10, S&D 0-110-0, PfE 62-0-0, ECR 67-0-0, Renew 0-68-0, Greens 0-49-0, Left 0-35-0, ESN 24-0-0, NI 18-1-4, ? 0-1-0
- **Proposed side:** FAVOR (medium confidence)
  - favour: Voted for amendment 1, which inserted what is now § 4 of the adopted text: condemning the systematic persecution of Christians in Pakistan and demanding that Pakistan repeal its blasphemy laws. Carried 301-281.
  - against: Voted against inserting the paragraph that condemns the systematic persecution of Christians in Pakistan and demands the repeal of its blasphemy laws.
- **Flag for you:** Text located by position, not read from the amendment: a carried amendment inserted after § 3 is § 4 of the adopted text. The lobbies fit (EPP 130-17, ECR, Patriots and ESN for; S&D, Renew, Greens and the Left against). Confirm against the plenary amendment if you can.

### [ ] `MTG-PL-2026-07-09-DEC-195771` § 6 – Am 5

- **Result:** ADOPTED 312-248-27
- **A favour vote means:** For amendment 5 (amending § 6). Its words are not in the store.
- **Lobbies:** EPP 3-147-8, S&D 109-0-0, PfE 29-20-9, ECR 5-56-4, Renew 67-0-0, Greens 48-0-0, Left 34-0-0, ESN 1-20-2, NI 15-5-4, ? 1-0-0
- **Proposed:** no direction -- Amendment 5 replaced § 6 (carried 312-248, S&D, Renew, Greens and the Left for, EPP and ECR against). The adopted text at that position (probably § 7, after amendment 1's insertion) calls for a complaints mechanism for families of abducted girls and for addressing root causes 'including gender inequality, poverty, social exclusion and discrimination based on caste, gender and religion'. What it replaced is not in the store, so what a vote for it changed cannot be read.

### [ ] `MTG-PL-2026-07-09-DEC-195772` § 7 – Am 6

- **Result:** ADOPTED 334-231-29
- **A favour vote means:** For amendment 6 (amending § 7). Its words are not in the store.
- **Lobbies:** EPP 2-151-5, S&D 109-0-0, PfE 55-0-6, ECR 12-52-3, Renew 67-0-0, Greens 46-0-1, Left 35-0-0, ESN 0-20-5, NI 7-8-9, ? 1-0-0
- **Proposed:** no direction -- Amendment 6 replaced § 7 (carried 334-231; EPP and ECR against). The adopted text at that position (probably § 8) asks the EU to raise forced conversions and minority protection with Pakistan and to withdraw GSP+ trade preferences if human-rights commitments are not met. What it replaced is not in the store.

### [ ] `MTG-PL-2026-07-09-DEC-195773` Recital B – Am 3

- **Result:** ADOPTED 310-261-21
- **A favour vote means:** For amendment 3 (amending Recital B). Its words are not in the store.
- **Lobbies:** EPP 6-149-3, S&D 108-0-0, PfE 29-26-6, ECR 5-61-1, Renew 67-0-1, Greens 46-1-0, Left 34-0-0, ESN 2-21-2, NI 12-3-8, ? 1-0-0
- **Proposed:** no direction -- Amendment 3 replaced recital B (carried 310-261; EPP and ECR against). The adopted recital B speaks of forced conversion and marriage of 'Hindu, Christian and other religious minorities' with UN figures (75 % Hindu, 25 % Christian). The original wording it replaced is not in the store; if it put Christians first, a vote for the amendment diluted it.

### [ ] `MTG-PL-2026-07-09-DEC-195774` After recital D – Am 4

- **Result:** ADOPTED 480-77-32
- **A favour vote means:** For amendment 4 (inserting After recital D). Its words are not in the store.
- **Lobbies:** EPP 140-6-7, S&D 108-0-0, PfE 55-0-6, ECR 12-50-5, Renew 68-0-0, Greens 47-1-0, Left 35-0-0, ESN 1-18-6, NI 13-2-8, ? 1-0-0
- **Proposed:** no direction -- Amendment 4 inserted a recital after D (carried 480-77). The adopted recital E speaks of minorities facing arbitrary detention, disappearances, harassment of journalists and the misuse of blasphemy, anti-terrorism and cybercrime laws. ECR voted 12-50 against, which does not fit that text alone; read the amendment before signing.

## Nigeria (2026-07-09)

### [x] `MTG-PL-2026-07-09-DEC-195749` persecution of Christians resolution

- **Signed side:** favor

### [ ] `MTG-PL-2026-07-09-DEC-195740` persecution of Christians: § 7 – Am 6/2: the words ‘and risk of genocide’

- **Result:** REJECTED 148-414-35
- **A favour vote means:** For amendment 6/2 (amending § 7). Its words are not in the store.
- **Lobbies:** EPP 27-129-2, S&D 0-108-0, PfE 32-1-29, ECR 54-12-1, Renew 0-68-0, Greens 0-49-0, Left 0-34-0, ESN 25-0-0, NI 10-12-3, ? 0-1-0
- **Proposed side:** FAVOR (medium confidence)
  - favour: Voted for the words 'and risk of genocide' in amendment 6 to § 7 of the Nigeria resolution, naming a risk of genocide against Nigeria's Christians.
  - against: Voted against describing the persecution of Christians in Nigeria as carrying a risk of genocide.
- **Flag for you:** Amendment 6 itself fell (part 1 rejected 194-392), so these words could not enter the text, but the vote shows who would use the genocide language. The rest of amendment 6 is not in the store. ECR 54-12, ESN 25-0, Patriots 32-1-29 (half abstaining), EPP 27-129.

### [ ] `MTG-PL-2026-07-09-DEC-195743` persecution of Christians: Recital C – Am 4/2: the words ‘and displays genocidal characteristics’

- **Result:** REJECTED 133-422-40
- **A favour vote means:** For amendment 4/2 (amending Recital C). Its words are not in the store.
- **Lobbies:** EPP 34-121-3, S&D 0-108-0, PfE 32-0-30, ECR 33-29-4, Renew 0-68-0, Greens 0-48-0, Left 0-35-0, ESN 25-0-0, NI 9-12-3, ? 0-1-0
- **Proposed side:** FAVOR (medium confidence)
  - favour: Voted for the words 'and displays genocidal characteristics' in amendment 4 to recital C of the Nigeria resolution.
  - against: Voted against saying the violence against Nigeria's Christians displays genocidal characteristics.
- **Flag for you:** As for § 7 Am 6/2: the amendment fell (part 1 rejected 207-379); the words alone were put. ECR split 33-29; ESN 25-0; Patriots 32-0-30.

### [ ] `MTG-PL-2026-07-09-DEC-195736` persecution of Christians: § 1 – Am 2/1: the text without the words ‘takes note of the communication by UN Special Rapporteurs of June 20…

- **Result:** REJECTED 177-412-8
- **A favour vote means:** For amendment 2/1 (amending § 1). Its words are not in the store.
- **Lobbies:** EPP 10-149-0, S&D 0-108-0, PfE 62-0-0, ECR 67-0-0, Renew 1-66-0, Greens 0-49-0, Left 0-35-0, ESN 24-0-0, NI 13-4-8, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-09-DEC-195739` persecution of Christians: § 7 – Am 6/1: the text without the words ‘and risk of genocide’

- **Result:** REJECTED 194-392-9
- **A favour vote means:** For amendment 6/1 (amending § 7). Its words are not in the store.
- **Lobbies:** EPP 31-128-0, S&D 0-108-0, PfE 60-0-0, ECR 67-0-0, Renew 3-65-0, Greens 0-48-0, Left 0-35-0, ESN 23-1-0, NI 10-6-9, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-09-DEC-195742` persecution of Christians: Recital C – Am 4/1: the text without the words ‘and displays genocidal characteristics’

- **Result:** REJECTED 207-379-8
- **A favour vote means:** For amendment 4/1 (amending Recital C). Its words are not in the store.
- **Lobbies:** EPP 36-122-0, S&D 0-107-0, PfE 62-0-0, ECR 67-0-0, Renew 4-63-0, Greens 0-48-0, Left 0-35-0, ESN 24-0-0, NI 14-3-8, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-09-DEC-195745` persecution of Christians: Recital E – Am 1

- **Result:** REJECTED 176-412-3
- **A favour vote means:** For amendment 1 (amending Recital E). Its words are not in the store.
- **Lobbies:** EPP 12-146-0, S&D 0-108-0, PfE 62-0-0, ECR 65-1-0, Renew 1-64-0, Greens 0-47-0, Left 0-35-0, ESN 24-0-0, NI 12-10-3, ? 0-1-0
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-09-DEC-195748` persecution of Christians: Recital E

- **Result:** REJECTED 288-308-2
- **A favour vote means:** For keeping Recital E as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital E (adopted-text numbering assumed equal to the motion (unchecked)): E. whereas Christians are the most persecuted religious group globally, and the failure to address this persecution undermines the protection of freedom of religion or belief;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

## ePrivacy derogation (2026-07-09)

### [x] `MTG-PL-2026-07-09-DEC-195775` rejection proposal (Left, Greens, ESN)

- **Signed side:** favor

### [x] `MTG-PL-2026-07-09-DEC-195778` exclude end-to-end encryption (Am 30)

- **Signed side:** favor

### [x] `MTG-PL-2026-07-09-DEC-195807` final rejection proposal (Rule 68(4))

- **Signed side:** favor

### [ ] `MTG-PL-2026-07-09-DEC-195789` Article 3, § 1, after point a – Am 27

- **Result:** REJECTED 175-408-22
- **A favour vote means:** For amendment 27 (amending Article 3, § 1, after point a). Its words are not in the store.
- **Lobbies:** EPP 2-162-0, S&D 1-105-0, PfE 56-6-6, ECR 66-0-1, Renew 3-66-0, Greens 0-49-0, Left 1-20-11, ESN 25-0-0, NI 21-0-2, ? 0-0-2
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-07-09-DEC-195791` Article 3, § 1, point d – Am 17D

- **Result:** REJECTED 86-479-41
- **A favour vote means:** For amendment 17D (amending Article 3, § 1, point d). Its words are not in the store.
- **Lobbies:** EPP 1-164-0, S&D 0-108-0, PfE 32-6-30, ECR 12-51-4, Renew 0-68-0, Greens 0-49-0, Left 0-31-0, ESN 25-0-0, NI 16-1-6, ? 0-1-1
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

## EU Youth Strategy report (2026-09-15)

### [ ] `MTG-PL-2026-09-15-DEC-196207` § 25 – Am 6

- **Result:** REJECTED 209-447-10
- **A favour vote means:** For amendment 6 (amending § 25). Its words are not in the store.
- **Lobbies:** EPP 16-158-2, S&D 2-126-0, PfE 74-0-0, ECR 77-0-0, Renew 3-70-0, Greens 0-50-0, Left 0-39-0, ESN 26-0-0, NI 11-4-8
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-15-DEC-196208` After § 35 – Am 7

- **Result:** REJECTED 159-372-136
- **A favour vote means:** For amendment 7 (inserting After § 35). Its words are not in the store.
- **Lobbies:** EPP 3-172-0, S&D 40-0-88, PfE 0-52-21, ECR 1-72-2, Renew 7-67-0, Greens 51-0-0, Left 38-1-0, ESN 0-7-18, NI 19-1-7
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-15-DEC-196209` After § 36 – Am 10

- **Result:** REJECTED 81-532-44
- **A favour vote means:** For amendment 10 (inserting After § 36). Its words are not in the store.
- **Lobbies:** EPP 1-168-3, S&D 24-96-4, PfE 0-69-6, ECR 0-61-13, Renew 4-68-0, Greens 3-42-2, Left 37-2-1, ESN 0-23-4, NI 12-3-11
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-15-DEC-196210` After § 36 – Am 12

- **Result:** REJECTED 117-439-109
- **A favour vote means:** For amendment 12 (inserting After § 36). Its words are not in the store.
- **Lobbies:** EPP 9-165-3, S&D 39-11-74, PfE 1-53-20, ECR 0-71-4, Renew 4-68-1, Greens 1-47-2, Left 40-0-0, ESN 4-21-2, NI 19-3-3
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-15-DEC-196211` After § 40 – Am 13

- **Result:** REJECTED 91-448-124
- **A favour vote means:** For amendment 13 (inserting After § 40). Its words are not in the store.
- **Lobbies:** EPP 0-175-0, S&D 2-122-3, PfE 21-10-43, ECR 9-9-55, Renew 3-70-0, Greens 1-42-4, Left 23-11-6, ESN 18-7-2, NI 14-2-11
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-15-DEC-196212` After § 49 – Am 16

- **Result:** REJECTED 217-431-20
- **A favour vote means:** For amendment 16 (inserting After § 49). Its words are not in the store.
- **Lobbies:** EPP 28-144-4, S&D 2-125-0, PfE 75-0-0, ECR 72-0-2, Renew 0-68-4, Greens 0-50-1, Left 0-39-1, ESN 27-0-0, NI 13-5-8
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-15-DEC-195884` § 62

- **Result:** REJECTED 186-463-7
- **A favour vote means:** For keeping § 62 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 62 (adopted-text numbering assumed equal to the motion (unchecked)): 62. Urges the Commission and the Member States to strengthen digital skills and media literacy education across all forms of formal, non-formal and informal learning, with a view to fostering critical thinking, combating disinformation, promoting safe, responsible and inclusive online behaviour and preventing cyberbullying, in alignment with the basic skills action plan and the EU’s efforts to strengthen democratic resilience, with particular attention to vulnerable and marginalised groups;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-15-DEC-195890` Motion for a resolution (as a whole)

- **Result:** ADOPTED 477-124-66
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 172-2-2, S&D 125-1-0, PfE 3-69-3, ECR 5-16-53, Renew 73-1-0, Greens 51-0-0, Left 38-0-1, ESN 0-25-0, NI 10-10-7
- **Proposed:** evidence only, never places -- A youth-policy implementation report; its on-ground lines are a call for consistent DSA and AVMSD enforcement to protect minors online (§ 63). The vote was on youth policy.

## European Democracy Shield (2026-09-15)

### [x] `MTG-PL-2026-09-15-DEC-195987` special committee report

- **Signed side:** against

### [ ] `MTG-PL-2026-09-15-DEC-196368` After § 53 – Am 42

- **Result:** REJECTED 197-464-4
- **A favour vote means:** For amendment 42 (inserting After § 53). Its words are not in the store.
- **Lobbies:** EPP 3-170-1, S&D 0-125-0, PfE 74-0-0, ECR 76-0-0, Renew 0-75-0, Greens 0-50-0, Left 1-39-0, ESN 25-1-0, NI 18-4-3
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

## Gender inequalities in health report (2026-09-16)

### [ ] `MTG-PL-2026-09-16-DEC-196156` Motion for a resolution (as a whole)

- **Result:** ADOPTED 390-218-29
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 69-74-12, S&D 122-0-1, PfE 33-37-4, ECR 3-70-2, Renew 71-0-0, Greens 49-0-0, Left 39-0-0, ESN 0-24-0, NI 4-13-10
- **Proposed side:** AGAINST (high confidence)
  - favour: Backed the report on gender inequalities in health, which calls for improved access to abortion throughout the EU, supports the 'My Voice, My Choice' initiative, asks for SRHR and a right to abortion in the Charter of Fundamental Rights, calls for comprehensive sexuality education in line with UNESCO standards and for access to transition-related healthcare.
  - against: Opposed the report that writes abortion access, an abortion right in the EU Charter, comprehensive sexuality education and trans-specific healthcare into EU women's-health policy.
- **Flag for you:** The EPP split 69-74-12 and the Patriots 33-37-4: the most discriminating whole-text vote in the EU backlog.

### [ ] `MTG-PL-2026-09-16-DEC-196546` § 8/3: ‘calls on the Commission to issue recommendations to the Member States on the provision of comprehensiv…

- **Result:** ADOPTED 388-169-88
- **A favour vote means:** For keeping the words ‘calls on the Commission to issue recommendations to the Member States on the provision of comprehensive sexuality education, in line with UNESCO standards;’
- **Text:** Adopted § 10 (quote found in the adopted text): 10. Calls on the Commission and the Member States to strengthen health literacy by funding targeted, evidence-based, awareness-raising and communication campaigns to ensure that women and other vulnerable groups can make informed decisions about their health; stresses the importance of reliable, evidence-based and age-appropriate health information for women and girls as well as men and boys throughout the life course, and of education on SRHR, including fertility, pregnancy, contraception, maternal health and post-natal care, consent, bodily integrity, privacy, personal autonomy, respect and the prevention of gender-based violence; calls on th
- **Lobbies:** EPP 102-20-39, S&D 120-0-0, PfE 1-43-32, ECR 4-69-3, Renew 66-1-4, Greens 50-0-0, Left 40-0-0, ESN 0-23-1, NI 5-13-9
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted for the words asking the Commission to issue recommendations to the Member States on comprehensive sexuality education 'in line with UNESCO standards'.
  - against: Voted against EU recommendations on comprehensive sexuality education, a matter for parents and Member States.

### [ ] `MTG-PL-2026-09-16-DEC-196560` § 16/3: ‘transgender and gender-diverse people,’

- **Result:** ADOPTED 330-256-57
- **A favour vote means:** For keeping the words ‘transgender and gender-diverse people,’
- **Text:** Adopted § 19 (quote found in the adopted text): 19. Highlights the fact that as a result of systemic underfunding and a lack of research, diagnostic methods and treatments remain male-centric, which can lead to substandard and higher-risk treatment for women, transgender and gender-diverse people, including through a lack of necessary, evidence-, science-based and comprehensive healthcare and the dismissal of pain and symptoms, leading to delayed diagnoses for women and transgender and intersex individuals;
- **Lobbies:** EPP 46-98-17, S&D 122-0-0, PfE 0-44-33, ECR 2-73-0, Renew 68-0-0, Greens 49-0-1, Left 39-0-0, ESN 0-24-0, NI 4-17-6
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted to keep 'transgender and gender-diverse people' among those whose treatment suffers from male-centric medicine (adopted § 19).
  - against: Voted to keep the paragraph about women's health without adding 'transgender and gender-diverse people'.
- **Flag for you:** Area 5 (sex-based rights): whether a women's-health text should be written to include gender identity. Medium: the words are inclusion language; the lobby split (EPP 46-98) shows the House read it as a gender-identity question. § 16/4 and recital J/2 are the same question.

### [ ] `MTG-PL-2026-09-16-DEC-196561` § 16/4: ‘and transgender and intersex individuals’

- **Result:** ADOPTED 353-224-63
- **A favour vote means:** For keeping the words ‘and transgender and intersex individuals’
- **Text:** Adopted § 19 (quote found in the adopted text): 19. Highlights the fact that as a result of systemic underfunding and a lack of research, diagnostic methods and treatments remain male-centric, which can lead to substandard and higher-risk treatment for women, transgender and gender-diverse people, including through a lack of necessary, evidence-, science-based and comprehensive healthcare and the dismissal of pain and symptoms, leading to delayed diagnoses for women and transgender and intersex individuals;
- **Lobbies:** EPP 66-75-15, S&D 121-0-0, PfE 0-36-40, ECR 2-74-0, Renew 70-0-1, Greens 49-0-1, Left 39-0-0, ESN 0-24-0, NI 6-15-6
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted to keep 'and transgender and intersex individuals' in § 16 of the gender-health report.
  - against: Voted to strike 'transgender and intersex individuals' from § 16.
- **Flag for you:** Same question as § 16/3.

### [ ] `MTG-PL-2026-09-16-DEC-196564` § 18/2: ‘compulsory,’

- **Result:** REJECTED 299-354-6
- **A favour vote means:** For keeping the words ‘compulsory,’
- **Lobbies:** EPP 8-158-1, S&D 131-0-0, PfE 0-77-0, ECR 0-76-0, Renew 63-1-5, Greens 50-0-0, Left 38-0-0, ESN 0-24-0, NI 9-18-0
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted to make 'compulsory' the gender-sensitive training in medical, nursing and obstetrics curricula that includes training on SRHR (rejected 299-354).
  - against: Voted against making that training, including on SRHR, compulsory.
- **Flag for you:** The word governs training whose list includes SRHR, prevention of discrimination and pain management. Medium: 'compulsory' is about the whole curriculum list, not SRHR alone.

### [ ] `MTG-PL-2026-09-16-DEC-196565` § 18/3: ‘on SRHR,’

- **Result:** ADOPTED 399-182-72
- **A favour vote means:** For keeping the words ‘on SRHR,’
- **Lobbies:** EPP 90-41-29, S&D 131-1-0, PfE 2-36-37, ECR 5-67-5, Renew 69-0-0, Greens 50-0-0, Left 40-0-0, ESN 1-22-0, NI 11-15-1
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted to keep 'on SRHR' in the list of training medical, nursing and obstetrics students should receive.
  - against: Voted to strike SRHR training from the medical curricula the paragraph asks Member States to reform.

### [ ] `MTG-PL-2026-09-16-DEC-196570` § 21/2: the words ‘the denial of abortion care, intersex genital mutilation, obstetric and gynaecological viol…

- **Result:** ADOPTED 433-135-65
- **A favour vote means:** For keeping the words ‘the denial of abortion care, intersex genital mutilation, obstetric and gynaecological violence, and malpractice in medical settings are forms of ge…
- **Text:** Adopted § 24 (quote found in the adopted text): 24. Emphasises that harmful practices such as female genital mutilation, forced abortion, forced sterilisation, the denial of abortion care, intersex genital mutilation, obstetric and gynaecological violence, and malpractice in medical settings are forms of gender-based violence; expresses concern about medically unnecessary treatments, often carried out without informed consent, which particularly affect intersex women, as well as coercive medical interventions, such as forced sterilisation, which remain a reality for women with disabilities in the EU; deplores the fact that, despite its commitment under the Gender Equality Strategy 2020-2025,
- **Lobbies:** EPP 93-45-20, S&D 127-1-2, PfE 32-20-15, ECR 12-41-16, Renew 67-0-3, Greens 50-0-0, Left 39-0-0, ESN 0-21-2, NI 13-7-7
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted to keep the words declaring 'the denial of abortion care' (with intersex genital mutilation and obstetric violence) a form of gender-based violence.
  - against: Voted to strike the words that call the denial of abortion care a form of gender-based violence.

### [ ] `MTG-PL-2026-09-16-DEC-196581` § 41

- **Result:** ADOPTED 362-214-75
- **A favour vote means:** For keeping § 41 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 44 (inferred: motion numbering +3, from the nearest quoted split): 44. Stresses that SRHR are fundamental human rights, which constitute a core component of women’s health and public health policy, and that ensuring universal access to comprehensive sexual and reproductive healthcare is a necessity for gender equality; stresses that concrete measures on SRHR are necessary for progress towards achieving the vision outlined in the Commission’s 2025 Roadmap for Women’s Rights, and for alignment with international human rights and the public health standards issued by the WHO and UNESCO; calls on the Commission to take action to advance the full spectrum of SRHR through all relevant EU
- **Lobbies:** EPP 59-74-26, S&D 131-0-0, PfE 1-42-34, ECR 7-59-10, Renew 65-0-2, Greens 50-0-0, Left 40-0-0, ESN 0-23-1, NI 9-16-2
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted for the paragraph stating that SRHR are fundamental human rights and calling on the Commission to advance 'the full spectrum of SRHR' through all EU policies and funding instruments.
  - against: Voted against declaring SRHR fundamental human rights and against pursuing them through every EU policy and fund.
- **Flag for you:** Plain paragraph vote: text located at adopted § 44 by the +3 offset. Lobbies fit (EPP 59-74-26).

### [ ] `MTG-PL-2026-09-16-DEC-196586` § 43/1: ‘Stresses the need to improve the availability of, and access to, abortion throughout the EU; strongly…

- **Result:** ADOPTED 358-210-81
- **A favour vote means:** For keeping the words ‘Stresses the need to improve the availability of, and access to, abortion throughout the EU; strongly supports the European Citizens’ Initiative entitled "My…
- **Text:** Adopted § 46 (quote found in the adopted text): 46. Stresses the need to improve the availability of, and access to, abortion throughout the EU; strongly supports the European Citizens’ Initiative entitled ‘My Voice, My Choice’, which aimed to set up a voluntary, solidarity-based, opt-in EU financial mechanism to ensure safe and accessible abortion in Europe; reiterates its call on the Commission to make full use of its competence in health policy to provide support to the Member States in guaranteeing universal access to SRHR, and to enshrine SRHR and the right to safe, legal and accessible abortion in the Charter of Fundamental Rights of the European Union;
- **Lobbies:** EPP 52-70-36, S&D 126-1-2, PfE 0-41-33, ECR 10-63-5, Renew 69-0-2, Greens 49-0-0, Left 40-0-0, ESN 0-23-0, NI 12-12-3
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted for the first part of § 43 (adopted § 46): improving the availability of and access to abortion throughout the EU and strongly supporting the 'My Voice, My Choice' initiative for an EU abortion funding mechanism.
  - against: Voted against calling for wider abortion access across the EU and against endorsing 'My Voice, My Choice'.

### [ ] `MTG-PL-2026-09-16-DEC-196587` § 43/2: ‘and to enshrine SRHR and the right to safe, legal and accessible abortion in the Charter of Fundament…

- **Result:** ADOPTED 340-285-24
- **A favour vote means:** For keeping the words ‘and to enshrine SRHR and the right to safe, legal and accessible abortion in the Charter of Fundamental Rights of the European Union;’
- **Text:** Adopted § 46 (quote found in the adopted text): 46. Stresses the need to improve the availability of, and access to, abortion throughout the EU; strongly supports the European Citizens’ Initiative entitled ‘My Voice, My Choice’, which aimed to set up a voluntary, solidarity-based, opt-in EU financial mechanism to ensure safe and accessible abortion in Europe; reiterates its call on the Commission to make full use of its competence in health policy to provide support to the Member States in guaranteeing universal access to SRHR, and to enshrine SRHR and the right to safe, legal and accessible abortion in the Charter of Fundamental Rights of the European Union;
- **Lobbies:** EPP 18-134-9, S&D 127-1-2, PfE 29-46-0, ECR 3-66-8, Renew 62-2-3, Greens 50-0-0, Left 39-0-0, ESN 0-22-1, NI 12-14-1
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted to call for SRHR and 'the right to safe, legal and accessible abortion' to be enshrined in the EU Charter of Fundamental Rights.
  - against: Voted against writing an abortion right into the EU Charter of Fundamental Rights.

### [ ] `MTG-PL-2026-09-16-DEC-196588` § 44

- **Result:** ADOPTED 349-228-79
- **A favour vote means:** For keeping § 44 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 47 (inferred: motion numbering +3, from the nearest quoted split): 47. Welcomes the positive response from the Commission to the ‘My Voice My Choice’ European Citizens’ Initiative in its February 2026 communication, acknowledging that unsafe abortion is a matter of public health, and enabling Member States, via appropriate funding within the European Social Fund Plus (ESF+) programme, to provide safe and legal abortion services, including by supporting travel and accommodation costs, to people who cannot access such services in their home country and, in general, for the most vulnerable persons, without interfering with national laws and regulations; recognises that this decision w
- **Lobbies:** EPP 48-83-31, S&D 128-1-2, PfE 0-42-34, ECR 9-64-4, Renew 66-0-4, Greens 50-0-0, Left 39-0-0, ESN 0-24-0, NI 9-14-4
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted for the paragraph welcoming the Commission's positive response to 'My Voice, My Choice', including EU funding (European Social Fund Plus) that Member States may use for abortion.
  - against: Voted against welcoming the Commission's response to 'My Voice, My Choice' and EU funding for abortion.
- **Flag for you:** Plain paragraph vote: text located at adopted § 47 by the +3 offset the quoted splits show around it. Lobbies fit the abortion votes (EPP 48-83-31).

### [ ] `MTG-PL-2026-09-16-DEC-196591` § 45/2: ‘and trans-specific healthcare, and to remove any coercive and unnecessary medical requirements, such …

- **Result:** ADOPTED 327-272-42
- **A favour vote means:** For keeping the words ‘and trans-specific healthcare, and to remove any coercive and unnecessary medical requirements, such as sterilisation, which hinder access to legal recognitio…
- **Text:** Adopted § 48 (quote found in the adopted text): 48. Calls on the Commission and the Member States to address the specific healthcare needs of LGBTIQ+ people, including by ensuring access to preventive care, treatment, and trans-specific healthcare, and to remove any coercive and unnecessary medical requirements, such as sterilisation, which hinder access to legal recognition and reproductive services, in line with the rulings of the European Court of Human Rights; recognises the commitment from the Commission, in its LGBTIQ+ equality strategy 2026-2030, to facilitate exchanges of best practices between the Member States in this respect; encourages support for community-based healthcare initi
- **Lobbies:** EPP 44-90-25, S&D 120-1-0, PfE 0-75-2, ECR 5-71-0, Renew 65-0-4, Greens 50-0-0, Left 39-0-0, ESN 0-24-0, NI 4-11-11
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted for the words calling for 'trans-specific healthcare' and the removal of medical requirements, such as sterilisation, for legal gender recognition.
  - against: Voted against the call for trans-specific healthcare and for easing the conditions of legal gender recognition.
- **Flag for you:** Areas 3 and 5. The removal of forced sterilisation is the hard part of this question: a vote against it can be read as defending sterilisation requirements. Medium.

### [ ] `MTG-PL-2026-09-16-DEC-196592` § 45/3: ‘gender identity and/or gender expression,’

- **Result:** ADOPTED 334-270-34
- **A favour vote means:** For keeping the words ‘gender identity and/or gender expression,’
- **Text:** Adopted § 48 (quote found in the adopted text): 48. Calls on the Commission and the Member States to address the specific healthcare needs of LGBTIQ+ people, including by ensuring access to preventive care, treatment, and trans-specific healthcare, and to remove any coercive and unnecessary medical requirements, such as sterilisation, which hinder access to legal recognition and reproductive services, in line with the rulings of the European Court of Human Rights; recognises the commitment from the Commission, in its LGBTIQ+ equality strategy 2026-2030, to facilitate exchanges of best practices between the Member States in this respect; encourages support for community-based healthcare initi
- **Lobbies:** EPP 48-88-23, S&D 119-1-0, PfE 1-75-0, ECR 5-70-0, Renew 69-0-1, Greens 49-0-1, Left 38-0-0, ESN 1-22-0, NI 4-14-9
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted to keep 'gender identity and/or gender expression' as a ground in § 45 of the gender-health report.
  - against: Voted to strike 'gender identity and/or gender expression' from § 45.

### [ ] `MTG-PL-2026-09-16-DEC-196595` § 46/2: ‘calls on the Commission to issue clear guidelines to the Member States on the provision of comprehens…

- **Result:** ADOPTED 406-214-29
- **A favour vote means:** For keeping the words ‘calls on the Commission to issue clear guidelines to the Member States on the provision of comprehensive age-appropriate sexuality and relationship education,…
- **Text:** Adopted § 49 (quote found in the adopted text): 49. Stresses the role of education, healthcare services and public institutions in preventing gender-based violence and promoting consent, bodily integrity, privacy, and personal autonomy and respect, and reducing gender inequalities; stresses that comprehensive, age-appropriate, science-based sexuality education, in line with UNESCO standards, is essential for promoting consent and SRHR, preventing gender-based violence, countering disinformation and stigma surrounding women’s health, and empowering individuals to make informed, autonomous choices; calls on the Commission to issue clear guidelines to the Member States on the provision of compr
- **Lobbies:** EPP 110-24-25, S&D 128-1-0, PfE 0-77-0, ECR 2-73-0, Renew 66-1-2, Greens 50-0-0, Left 40-0-0, ESN 0-23-0, NI 10-15-2
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted for the words asking the Commission to issue clear guidelines to the Member States on comprehensive age-appropriate sexuality and relationship education.
  - against: Voted against EU guidelines on comprehensive sexuality and relationship education.

### [ ] `MTG-PL-2026-09-16-DEC-196611` § 63/2: ‘and SRHR’

- **Result:** ADOPTED 429-153-69
- **A favour vote means:** For keeping the words ‘and SRHR’
- **Lobbies:** EPP 111-24-22, S&D 130-0-0, PfE 4-38-35, ECR 9-60-8, Renew 71-0-0, Greens 49-0-0, Left 40-0-0, ESN 0-23-0, NI 15-8-4
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted to keep 'and SRHR' in § 63, on the role of civil society organisations in providing healthcare services.
  - against: Voted to strike SRHR from the civil-society healthcare paragraph.

### [ ] `MTG-PL-2026-09-16-DEC-196625` Recital J/2: the words ‘transgender, non-binary and intersex people and’

- **Result:** ADOPTED 335-279-23
- **A favour vote means:** For keeping the words ‘transgender, non-binary and intersex people and’
- **Text:** Adopted recital J (quote found in the adopted text): J. whereas transgender, non-binary and intersex people and marginalised communities, such as ethnic minorities and women with disabilities, are often absent or disproportionally excluded from clinical trials and medical research, resulting in significant gaps in evidence regarding the safety and effectiveness of treatments; whereas this lack of data contributes to unequal access to appropriate, timely and high-quality healthcare;
- **Lobbies:** EPP 54-91-14, S&D 119-0-0, PfE 0-76-0, ECR 3-73-1, Renew 67-1-1, Greens 49-0-0, Left 37-0-0, ESN 0-24-0, NI 6-14-7
- **Proposed side:** AGAINST (medium confidence)
  - favour: Voted to keep 'transgender, non-binary and intersex people' in recital J on groups excluded from clinical trials.
  - against: Voted to strike 'transgender, non-binary and intersex people' from recital J.
- **Flag for you:** Same question as § 16/3.

### [ ] `MTG-PL-2026-09-16-DEC-196634` Recital Z

- **Result:** ADOPTED 431-165-50
- **A favour vote means:** For keeping Recital Z as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital Z (motion numbering unchanged (checked against the nearest quoted split)): Z. whereas full, effective and universal access to SRHR, including comprehensive, age-appropriate and science-based sexuality and relationship education, affordable and high-quality contraception, fertility care and safe and legal abortion services, is a fundamental pillar of gender equality, social justice, bodily integrity, privacy and personal autonomy, and is essential to countering disinformation and stigma and ensuring the dignity, health and equal participation of women and girls in all areas of life; whereas despite some progress, in practice, sexual and reproductive health services and access 
- **Lobbies:** EPP 91-34-30, S&D 127-1-2, PfE 34-38-3, ECR 10-60-7, Renew 70-0-0, Greens 48-0-0, Left 40-0-0, ESN 1-23-0, NI 10-9-8
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted for recital Z: universal access to SRHR, 'including comprehensive ... sexuality and relationship education, ... contraception, fertility care and safe and legal abortion services', is a fundamental pillar of gender equality.
  - against: Voted against recital Z, which makes abortion and comprehensive sexuality education a fundamental pillar of gender equality.

### [ ] `MTG-PL-2026-09-16-DEC-196635` Recital AA

- **Result:** ADOPTED 362-208-79
- **A favour vote means:** For keeping Recital AA as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital AA (motion numbering unchanged (checked against the nearest quoted split)): AA. whereas more than 20 million women in the EU still do not have access to safe and legal abortion services, as several Member States maintain harmful and discriminatory regulatory and procedural barriers; whereas the European Citizen’s Initiative entitled ‘My Voice, My Choice’ was a direct call from EU citizens for the EU to ensure access to safe and legal abortion services for all while respecting the division of competences under the Treaties; whereas the unmet need for contraception undermines bodily autonomy and global sustainable development, with unintended pregnancies accounting for approxim
- **Lobbies:** EPP 58-68-31, S&D 125-1-2, PfE 1-39-35, ECR 8-64-6, Renew 68-0-2, Greens 50-0-0, Left 40-0-0, ESN 0-23-1, NI 12-13-2
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted for recital AA: more than 20 million women in the EU lack access to safe and legal abortion because Member States keep 'harmful and discriminatory' barriers, and 'My Voice, My Choice' was a call for the EU to ensure access.
  - against: Voted against recital AA, which calls national abortion laws harmful and discriminatory barriers.

### [ ] `MTG-PL-2026-09-16-DEC-196636` Recital AB

- **Result:** ADOPTED 354-205-89
- **A favour vote means:** For keeping Recital AB as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital AB (motion numbering unchanged (checked against the nearest quoted split)): AB. whereas Parliament has voted on several occasions to strengthen and protect the right to abortion, including in texts on the European Citizens’ Initiative entitled ‘My Voice, My Choice’, the Gender Equality Strategy 2026-2030, and its recommendation to the Council concerning the EU priorities for the 69th session of the UN Commission on the Status of Women;
- **Lobbies:** EPP 57-67-33, S&D 125-1-2, PfE 1-39-35, ECR 6-64-8, Renew 68-0-2, Greens 49-0-0, Left 40-0-0, ESN 0-23-1, NI 8-11-8
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted for recital AB, recording that Parliament has repeatedly voted 'to strengthen and protect the right to abortion'.
  - against: Voted against recital AB and its claim of a right to abortion.

### [ ] `MTG-PL-2026-09-16-DEC-196639` Recital AC/2: ‘whereas many Member States provide only limited and unaffordable access to transition-related h…

- **Result:** ADOPTED 311-309-21
- **A favour vote means:** For keeping the words ‘whereas many Member States provide only limited and unaffordable access to transition-related healthcare;’
- **Text:** Adopted recital AC (quote found in the adopted text): AC. whereas 14 % of LGBTIQ+ people have reported experiencing discrimination in healthcare settings; whereas many Member States provide only limited and unaffordable access to transition-related healthcare;
- **Lobbies:** EPP 26-128-3, S&D 125-0-1, PfE 0-73-4, ECR 4-70-3, Renew 66-0-2, Greens 47-1-0, Left 37-0-1, ESN 0-24-0, NI 6-13-7
- **Proposed side:** AGAINST (high confidence)
  - favour: Voted for recital AC/2: 'many Member States provide only limited and unaffordable access to transition-related healthcare', presenting transition treatment as a service the Member States underprovide.
  - against: Voted against the recital that treats limited access to transition-related healthcare as a failing of the Member States.
- **Flag for you:** Area 3 (gender medicine). The recital does not mention children.

### [ ] `MTG-PL-2026-09-16-DEC-196538` § 6/5: ‘and social’

- **Result:** ADOPTED 342-280-30
- **A favour vote means:** For keeping the words ‘and social’
- **Lobbies:** EPP 25-125-11, S&D 131-0-0, PfE 12-56-8, ECR 6-63-6, Renew 65-4-0, Greens 50-0-0, Left 40-0-0, ESN 1-22-1, NI 12-10-4
- **Proposed:** no direction -- The words 'and social' in 'biological and social differences between' women and men: whether health policy should rest on sex alone or on sex and gender. A one-word sex-and-gender question; no side drafted.
- **Flag for you:** EPP 25-125-11, Patriots 12-56. Sign against if this is area 5 for you.

### [ ] `MTG-PL-2026-09-16-DEC-196539` After § 6 – Am 6

- **Result:** REJECTED 194-309-145
- **A favour vote means:** For amendment 6 (inserting After § 6). Its words are not in the store.
- **Lobbies:** EPP 16-7-138, S&D 6-121-2, PfE 60-15-0, ECR 76-1-0, Renew 1-71-0, Greens 0-50-0, Left 0-36-0, ESN 21-0-3, NI 14-8-2
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-16-DEC-196566` After § 19 – Am 7

- **Result:** REJECTED 278-304-69
- **A favour vote means:** For amendment 7 (inserting After § 19). Its words are not in the store.
- **Lobbies:** EPP 86-20-55, S&D 3-120-7, PfE 68-7-0, ECR 74-0-3, Renew 6-64-1, Greens 4-46-0, Left 0-36-0, ESN 23-1-0, NI 14-10-3
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-16-DEC-196567` After § 19 – Am 8

- **Result:** REJECTED 215-294-144
- **A favour vote means:** For amendment 8 (inserting After § 19). Its words are not in the store.
- **Lobbies:** EPP 24-7-130, S&D 2-120-7, PfE 76-0-0, ECR 77-0-0, Renew 0-68-3, Greens 0-50-0, Left 0-39-0, ESN 24-0-0, NI 12-10-4
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-09-16-DEC-196594` § 46/1: ‘Stresses the role of education, healthcare services and public institutions in preventing gender-base…

- **Result:** ADOPTED 470-117-63
- **A favour vote means:** For keeping the words ‘Stresses the role of education, healthcare services and public institutions in preventing gender-based violence and promoting consent, bodily integrity, priva…
- **Text:** Adopted § 49 (quote found in the adopted text): 49. Stresses the role of education, healthcare services and public institutions in preventing gender-based violence and promoting consent, bodily integrity, privacy, and personal autonomy and respect, and reducing gender inequalities; stresses that comprehensive, age-appropriate, science-based sexuality education, in line with UNESCO standards, is essential for promoting consent and SRHR, preventing gender-based violence, countering disinformation and stigma surrounding women’s health, and empowering individuals to make informed, autonomous choices; calls on the Commission to issue clear guidelines to the Member States on the provision of compr
- **Lobbies:** EPP 125-18-17, S&D 131-0-0, PfE 33-34-8, ECR 9-36-30, Renew 68-0-1, Greens 50-0-0, Left 40-0-0, ESN 0-22-1, NI 14-7-6
- **Proposed:** no direction -- The first part of § 46 (adopted § 49). The label cuts off after 'promoting consent, bodily integrity, priva…'; if this part runs on into the sentence that comprehensive sexuality education 'in line with UNESCO standards' is essential for SRHR, it is the same question as § 46/2 and the side is against. If it stops at reducing gender inequalities, it is not on our ground.
- **Flag for you:** The split's boundary is in the votes-results PDF, which the pipeline cannot read.

### [ ] `MTG-PL-2026-09-16-DEC-196604` § 60

- **Result:** ADOPTED 386-230-40
- **A favour vote means:** For keeping § 60 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 64 (inferred: motion numbering +4, from the nearest quoted split): 64. Underlines that a competitive, enterprise-driven economy is essential to sustaining high-quality healthcare and delivering better health outcomes for women; calls for policies that reward medical innovation, attract private investment and support economic growth, while removing unnecessary regulatory burdens that hold back European health businesses, researchers and the development of new treatments for women;
- **Lobbies:** EPP 104-35-25, S&D 127-2-0, PfE 0-73-3, ECR 3-73-2, Renew 52-13-3, Greens 47-3-0, Left 40-0-0, ESN 0-24-0, NI 13-7-7
- **Proposed:** no direction -- Plain paragraph vote whose text could not be located with confidence: the adopted text at the inferred position (§ 64) is a pro-enterprise paragraph, but the lobbies (S&D 127-2, Patriots and ECR against) do not fit it, so the offset is wrong here. Read the motion's § 60 first.

### [ ] `MTG-PL-2026-09-16-DEC-196612` § 63/3: ‘calls for their role to be explicitly acknowledged, in the upcoming European Competitiveness Fund and…

- **Result:** ADOPTED 351-272-28
- **A favour vote means:** For keeping the words ‘calls for their role to be explicitly acknowledged, in the upcoming European Competitiveness Fund and AgoraEU programme, through the earmarking of sufficient…
- **Text:** Adopted § 67 (quote found in the adopted text): 67. Emphasises the critical role of civil society organisations in providing needs-based, community-level and peer-to-peer healthcare services, particularly for women facing poverty, discrimination or social exclusion; stresses that these organisations act as a bridge between patients and public institutions, and also work to advance gender equality and SRHR, collect data on women’s health experiences and needs, prevent online health scams, and contribute to ensuring more gender-inclusive laws and policies in the field of healthcare; calls for their role to be explicitly acknowledged, in the upcoming European Competitiveness Fund and AgoraEU pr
- **Lobbies:** EPP 67-81-14, S&D 130-0-0, PfE 0-76-0, ECR 0-74-1, Renew 61-4-4, Greens 50-0-0, Left 39-0-0, ESN 0-23-0, NI 4-14-9
- **Proposed:** no direction -- Earmarked EU funding (European Competitiveness Fund, AgoraEU) for the civil society organisations in § 63, which part 2 extended to SRHR organisations. A funding line for NGOs that may include abortion providers; no side drafted.
- **Flag for you:** EPP 67-81-14. Sign against if you read it as EU money for SRHR NGOs.

### [ ] `MTG-PL-2026-09-16-DEC-196640` Citation 9

- **Result:** ADOPTED 353-204-79
- **A favour vote means:** For keeping Citation 9 as drafted (a separate vote on that paragraph or recital).
- **Lobbies:** EPP 59-66-31, S&D 120-1-1, PfE 1-41-33, ECR 5-62-8, Renew 69-0-2, Greens 50-0-0, Left 39-0-0, ESN 0-21-1, NI 10-13-3
- **Proposed:** no direction -- A citation (the 'having regard to' block); its text is not in the store, because the citations are dropped when the adopted text is read. The lobbies match the abortion votes (EPP 59-66-31), so it is probably a reference to an abortion or SRHR text; read it before signing.

### [ ] `MTG-PL-2026-09-16-DEC-196642` Citation 19

- **Result:** ADOPTED 359-210-81
- **A favour vote means:** For keeping Citation 19 as drafted (a separate vote on that paragraph or recital).
- **Lobbies:** EPP 60-70-29, S&D 127-1-2, PfE 1-43-30, ECR 3-62-11, Renew 68-0-2, Greens 50-0-0, Left 40-0-0, ESN 0-23-1, NI 10-11-6
- **Proposed:** no direction -- A citation; its text is not in the store. Lobbies match the abortion votes (EPP 60-70-29); read it before signing.

### [ ] `MTG-PL-2026-09-16-DEC-196148` Before § 1

- **Result:** ADOPTED 357-275-18
- **A favour vote means:** For keeping Before § 1 as drafted (a separate vote on that paragraph or recital).
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196150` After § 7

- **Result:** ADOPTED 357-274-15
- **A favour vote means:** For keeping After § 7 as drafted (a separate vote on that paragraph or recital).
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196151` After § 10

- **Result:** ADOPTED 319-317-10
- **A favour vote means:** For keeping After § 10 as drafted (a separate vote on that paragraph or recital).
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196154` After § 60

- **Result:** ADOPTED 339-300-13
- **A favour vote means:** For keeping After § 60 as drafted (a separate vote on that paragraph or recital).
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196155` Recital AE

- **Result:** ADOPTED 310-281-37
- **A favour vote means:** For keeping Recital AE as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital AE (motion numbering unchanged (checked against the nearest quoted split)): AE. whereas menstrual poverty – to be understood as insufficient access to menstrual hygiene products and facilities – affects an estimated 10 % of menstruating women, particularly women with low incomes, refugees, girls and women with disabilities;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196522` § 1

- **Result:** REJECTED 311-332-6
- **A favour vote means:** For keeping § 1 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 2 (inferred: motion numbering +1, from the nearest quoted split): 2. Stresses that gender inequalities in health are multifaceted and a violation of fundamental rights, with inequalities resulting from decades of medical research based on and designed around the male anatomy, which in turn has shaped the entire cycle of care from diagnostics to treatment; underlines that the recognition of this imbalance presents an opportunity to redesign research frameworks, clinical guidelines and care delivery; highlights that these inequalities affect both life-threatening and non-fatal chronic conditions, and have a substantial impact on the physical, mental and social well-being of women and
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196523` § 1

- **Result:** ADOPTED 336-286-28
- **A favour vote means:** For keeping § 1 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 2 (inferred: motion numbering +1, from the nearest quoted split): 2. Stresses that gender inequalities in health are multifaceted and a violation of fundamental rights, with inequalities resulting from decades of medical research based on and designed around the male anatomy, which in turn has shaped the entire cycle of care from diagnostics to treatment; underlines that the recognition of this imbalance presents an opportunity to redesign research frameworks, clinical guidelines and care delivery; highlights that these inequalities affect both life-threatening and non-fatal chronic conditions, and have a substantial impact on the physical, mental and social well-being of women and
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196526` § 2

- **Result:** ADOPTED 437-176-30
- **A favour vote means:** For keeping § 2 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 3 (inferred: motion numbering +1, from the nearest quoted split): 3. Stresses that health is a shared concern across the EU and that full respect for the principle of subsidiarity and Member States’ responsibility for organising their health systems should not prevent coordinated action; highlights that coordinated EU action strengthens resilience, ensures continuity of care during crises, reduces inequalities between Member States and guarantees that citizens’ health rights are effectively protected; underlines that women make up just over half of the population in the EU and the majority of the health and care workforce, and that EU-level cooperation is essential to ensure equita
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196528` § 3/1: ‘Highlights that inequalities in healthcare are compounded by intersectional inequalities and discrimin…

- **Result:** ADOPTED 406-200-35
- **A favour vote means:** For keeping the words ‘Highlights that inequalities in healthcare are compounded by intersectional inequalities and discrimination, including those linked to gender, age, socio-econ…
- **Text:** Adopted § 4 (quote found in the adopted text): 4. Highlights that inequalities in healthcare are compounded by intersectional inequalities and discrimination, including those linked to gender, age, socio-economic status, disability, race or geographical location and those experienced by people from ethnic minorities, refugee, migrant and LGBTIQ+ communities, survivors of gender-based violence and women deprived of their liberty; stresses that employment, housing and income insecurities, as well as unpaid care responsibilities, deepen gender inequalities in health and limit access to timely, quality and affordable care; points out that inequalities are also evident in gender-specific conditio
- **Lobbies:** EPP 114-39-11, S&D 119-0-0, PfE 0-64-9, ECR 5-63-7, Renew 71-0-0, Greens 50-0-0, Left 39-0-0, ESN 0-24-0, NI 8-10-8
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196529` § 3/2: ‘stresses that employment, housing and income insecurities, as well as unpaid care responsibilities, de…

- **Result:** ADOPTED 490-141-26
- **A favour vote means:** For keeping the words ‘stresses that employment, housing and income insecurities, as well as unpaid care responsibilities, deepen gender inequalities in health and limit access to t…
- **Text:** Adopted § 4 (quote found in the adopted text): 4. Highlights that inequalities in healthcare are compounded by intersectional inequalities and discrimination, including those linked to gender, age, socio-economic status, disability, race or geographical location and those experienced by people from ethnic minorities, refugee, migrant and LGBTIQ+ communities, survivors of gender-based violence and women deprived of their liberty; stresses that employment, housing and income insecurities, as well as unpaid care responsibilities, deepen gender inequalities in health and limit access to timely, quality and affordable care; points out that inequalities are also evident in gender-specific conditio
- **Lobbies:** EPP 131-29-5, S&D 128-0-0, PfE 50-15-12, ECR 8-64-5, Renew 67-3-0, Greens 49-0-0, Left 39-1-0, ESN 1-23-0, NI 17-6-4
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196535` § 6

- **Result:** REJECTED 308-333-12
- **A favour vote means:** For keeping § 6 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 7 (inferred: motion numbering +1, from the nearest quoted split): 7. Calls on policymakers and healthcare professionals to address inequalities, in line with the principle of subsidiarity, and to correct discrepancies with measurable targets and accountability as innovative new treatments and procedures are developed; calls for the incorporation of a sex- and gender-informed perspective in all EU health legislation and initiatives; emphasises the importance of science-based, efficient and innovation-friendly health policies that take into account biological and social differences between women and men and that address the disparities therein; reiterates that research and innovation
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196537` § 6/4: ‘emphasises the importance of science-based, efficient and innovation-friendly health policies that tak…

- **Result:** ADOPTED 601-46-9
- **A favour vote means:** For keeping the words ‘emphasises the importance of science-based, efficient and innovation-friendly health policies that take into account biological and social differences between…
- **Text:** Adopted § 7 (quote found in the adopted text): 7. Calls on policymakers and healthcare professionals to address inequalities, in line with the principle of subsidiarity, and to correct discrepancies with measurable targets and accountability as innovative new treatments and procedures are developed; calls for the incorporation of a sex- and gender-informed perspective in all EU health legislation and initiatives; emphasises the importance of science-based, efficient and innovation-friendly health policies that take into account biological and social differences between women and men and that address the disparities therein; reiterates that research and innovation models in the health sector 
- **Lobbies:** EPP 161-4-1, S&D 128-0-0, PfE 61-15-1, ECR 69-3-2, Renew 71-0-0, Greens 50-0-0, Left 38-0-1, ESN 3-21-0, NI 20-3-4
- **Proposed:** evidence only, never places -- Near-unanimous (601-46): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-09-16-DEC-196544` § 8/1: ‘Calls on the Commission and the Member States to strengthen health literacy by funding targeted, evide…

- **Result:** ADOPTED 501-61-74
- **A favour vote means:** For keeping the words ‘Calls on the Commission and the Member States to strengthen health literacy by funding targeted, evidence-based, awareness-raising and communication campaigns…
- **Lobbies:** EPP 149-3-3, S&D 127-0-0, PfE 48-21-6, ECR 8-8-58, Renew 69-0-0, Greens 50-0-0, Left 36-0-0, ESN 0-20-3, NI 14-9-4
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196545` § 8/2: ‘stresses the importance of reliable, evidence-based and age-appropriate health information for women a…

- **Result:** ADOPTED 472-133-45
- **A favour vote means:** For keeping the words ‘stresses the importance of reliable, evidence-based and age-appropriate health information for women and girls as well as men and boys throughout the life cou…
- **Text:** Adopted § 10 (quote found in the adopted text): 10. Calls on the Commission and the Member States to strengthen health literacy by funding targeted, evidence-based, awareness-raising and communication campaigns to ensure that women and other vulnerable groups can make informed decisions about their health; stresses the importance of reliable, evidence-based and age-appropriate health information for women and girls as well as men and boys throughout the life course, and of education on SRHR, including fertility, pregnancy, contraception, maternal health and post-natal care, consent, bodily integrity, privacy, personal autonomy, respect and the prevention of gender-based violence; calls on th
- **Lobbies:** EPP 112-22-27, S&D 129-0-0, PfE 46-29-1, ECR 8-56-12, Renew 69-0-0, Greens 50-0-0, Left 40-0-0, ESN 1-21-1, NI 17-5-4
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196548` § 10

- **Result:** ADOPTED 457-179-13
- **A favour vote means:** For keeping § 10 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 12 (inferred: motion numbering +2, from the nearest quoted split): 12. Expresses concern that despite improvements to inclusivity in clinical trials, the representation of women and gender-diverse people remains below that of men and should be strengthened by introducing sex-disaggregated reporting; stresses that there are no inclusivity requirements in the pretrial phase and that the majority of animal testing is still conducted on males of the species only; stresses the need for clinical trials to take into account differences in outcomes pertaining to hormonal fluctuations and life stages; recognises that pregnant women are often excluded from clinical trials; calls on the Commi
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196549` § 10

- **Result:** REJECTED 290-343-12
- **A favour vote means:** For keeping § 10 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 12 (inferred: motion numbering +2, from the nearest quoted split): 12. Expresses concern that despite improvements to inclusivity in clinical trials, the representation of women and gender-diverse people remains below that of men and should be strengthened by introducing sex-disaggregated reporting; stresses that there are no inclusivity requirements in the pretrial phase and that the majority of animal testing is still conducted on males of the species only; stresses the need for clinical trials to take into account differences in outcomes pertaining to hormonal fluctuations and life stages; recognises that pregnant women are often excluded from clinical trials; calls on the Commi
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196550` § 10

- **Result:** REJECTED 302-330-16
- **A favour vote means:** For keeping § 10 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 12 (inferred: motion numbering +2, from the nearest quoted split): 12. Expresses concern that despite improvements to inclusivity in clinical trials, the representation of women and gender-diverse people remains below that of men and should be strengthened by introducing sex-disaggregated reporting; stresses that there are no inclusivity requirements in the pretrial phase and that the majority of animal testing is still conducted on males of the species only; stresses the need for clinical trials to take into account differences in outcomes pertaining to hormonal fluctuations and life stages; recognises that pregnant women are often excluded from clinical trials; calls on the Commi
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196553` § 11

- **Result:** ADOPTED 321-286-34
- **A favour vote means:** For keeping § 11 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 13 (inferred: motion numbering +2, from the nearest quoted split): 13. Clarifies that, in the specific context of animal testing, research design should better take into account biological sex and the study of sex-based biological differences;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196556` § 13

- **Result:** REJECTED 290-361-3
- **A favour vote means:** For keeping § 13 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 16 (inferred: motion numbering +3, from the nearest quoted split): 16. Stresses that the lack of understanding of sex- and gender-based differences in health is exacerbated by the fact that the data outcomes of research are rarely disaggregated by sex and gender; calls on the Commission to promote the collection and reporting of sex- and gender-disaggregated data in all EU-funded projects so as to ensure accountability and the effective use of public resources; notes that AI could be used to identify sex or gender biases in existing or historical research to prevent the need to repeat the research; warns, however, that the use of AI must be monitored closely to ensure that it does 
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196558` § 16/1: the text without the words ‘systemic’, ‘transgender and gender-diverse people,’ and ‘and transgender a…

- **Result:** ADOPTED 539-20-88
- **A favour vote means:** For keeping the passage WITHOUT the words ‘systemic’, ‘transgender and gender-diverse people,’ and ‘and transgender and intersex individuals’; those words were put separately as the next part.
- **Lobbies:** EPP 159-4-1, S&D 124-0-2, PfE 70-2-5, ECR 7-9-58, Renew 71-0-0, Greens 50-0-0, Left 39-0-0, ESN 3-3-16, NI 16-2-6
- **Proposed:** evidence only, never places -- Near-unanimous (539-20): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-09-16-DEC-196559` § 16/2: ‘systemic’

- **Result:** ADOPTED 339-302-12
- **A favour vote means:** For keeping the words ‘systemic’
- **Lobbies:** EPP 11-154-2, S&D 124-0-2, PfE 36-38-3, ECR 0-74-0, Renew 68-0-2, Greens 50-0-0, Left 39-0-0, ESN 0-24-0, NI 11-12-3
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196563` § 18/1: the text without the words ‘compulsory,’ and ‘on SRHR,’

- **Result:** ADOPTED 435-197-22
- **A favour vote means:** For keeping the passage WITHOUT the words ‘compulsory,’ and ‘on SRHR,’; those words were put separately as the next part.
- **Lobbies:** EPP 122-34-4, S&D 132-0-0, PfE 0-70-6, ECR 6-64-5, Renew 71-0-0, Greens 49-0-0, Left 40-0-0, ESN 0-23-1, NI 15-6-6
- **Proposed:** evidence only, never places -- This part put the passage WITHOUT the contested words, which were voted as the next part; it records nothing about those words.

### [ ] `MTG-PL-2026-09-16-DEC-196569` § 21/1: the text without the words ‘the denial of abortion care, intersex genital mutilation, obstetric and gy…

- **Result:** ADOPTED 548-37-60
- **A favour vote means:** For keeping the passage WITHOUT the words ‘the denial of abortion care, intersex genital mutilation, obstetric and gynaecological violence, and malpractice in medical setting…; those words were put separately as the next part.
- **Text:** Adopted § 24 (quote found in the adopted text): 24. Emphasises that harmful practices such as female genital mutilation, forced abortion, forced sterilisation, the denial of abortion care, intersex genital mutilation, obstetric and gynaecological violence, and malpractice in medical settings are forms of gender-based violence; expresses concern about medically unnecessary treatments, often carried out without informed consent, which particularly affect intersex women, as well as coercive medical interventions, such as forced sterilisation, which remain a reality for women with disabilities in the EU; deplores the fact that, despite its commitment under the Gender Equality Strategy 2020-2025,
- **Lobbies:** EPP 154-3-3, S&D 132-0-0, PfE 48-0-18, ECR 37-5-33, Renew 71-0-0, Greens 50-0-0, Left 39-1-0, ESN 2-22-0, NI 15-6-6
- **Proposed:** evidence only, never places -- Near-unanimous (548-37): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-09-16-DEC-196572` § 24/1: the text without the words ‘compulsory,’

- **Result:** ADOPTED 532-42-82
- **A favour vote means:** For keeping the passage WITHOUT the words ‘compulsory,’; those words were put separately as the next part.
- **Lobbies:** EPP 162-3-1, S&D 130-0-0, PfE 55-8-12, ECR 13-5-56, Renew 70-0-1, Greens 50-0-0, Left 39-0-0, ESN 1-23-0, NI 12-3-12
- **Proposed:** evidence only, never places -- Near-unanimous (532-42): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-09-16-DEC-196573` § 24/2: that word

- **Result:** ADOPTED 337-303-19
- **A favour vote means:** For keeping the word(s) the previous part's split separated out (the label does not repeat them).
- **Lobbies:** EPP 8-156-0, S&D 131-0-0, PfE 32-37-8, ECR 2-71-4, Renew 68-0-2, Greens 50-0-0, Left 40-0-0, ESN 0-23-0, NI 6-16-5
- **Proposed:** evidence only, never places -- The word 'compulsory' in the paragraph calling for training of health professionals, emergency responders and police on gender-based violence including female genital mutilation (adopted § 27). Not on CitizenGO's ground.

### [ ] `MTG-PL-2026-09-16-DEC-196575` § 27

- **Result:** ADOPTED 417-150-74
- **A favour vote means:** For keeping § 27 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 30 (inferred: motion numbering +3, from the nearest quoted split): 30. Warns that women’s health medicines are not adequately prioritised in EU efforts to protect against shortages and supply disruptions, despite routine shortages of abortion medicine and contraception, among others, in Member States; calls on the Council to align with Parliament’s proposal to recognise abortifacient and contraceptive medicinal products as medicinal products of common interest in the Critical Medicines Act; calls on the Council to consider these products for inclusion in the next revision of the EU list of critical medicines; calls for the forthcoming Critical Medicines Act to integrate a gender-se
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196576` § 27

- **Result:** ADOPTED 400-180-52
- **A favour vote means:** For keeping § 27 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 30 (inferred: motion numbering +3, from the nearest quoted split): 30. Warns that women’s health medicines are not adequately prioritised in EU efforts to protect against shortages and supply disruptions, despite routine shortages of abortion medicine and contraception, among others, in Member States; calls on the Council to align with Parliament’s proposal to recognise abortifacient and contraceptive medicinal products as medicinal products of common interest in the Critical Medicines Act; calls on the Council to consider these products for inclusion in the next revision of the EU list of critical medicines; calls for the forthcoming Critical Medicines Act to integrate a gender-se
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196577` § 27

- **Result:** ADOPTED 397-156-78
- **A favour vote means:** For keeping § 27 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 30 (inferred: motion numbering +3, from the nearest quoted split): 30. Warns that women’s health medicines are not adequately prioritised in EU efforts to protect against shortages and supply disruptions, despite routine shortages of abortion medicine and contraception, among others, in Member States; calls on the Council to align with Parliament’s proposal to recognise abortifacient and contraceptive medicinal products as medicinal products of common interest in the Critical Medicines Act; calls on the Council to consider these products for inclusion in the next revision of the EU list of critical medicines; calls for the forthcoming Critical Medicines Act to integrate a gender-se
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196579` § 39

- **Result:** ADOPTED 342-206-87
- **A favour vote means:** For keeping § 39 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 42 (inferred: motion numbering +3, from the nearest quoted split): 42. Highlights that lesbian women are statistically less likely to access routine screening, often due to misconceptions or previous negative experiences with healthcare providers; underlines the need for tailored information to tackle misconceptions and ensure that lesbian women, transgender and gender-diverse people receive appropriate screening and preventive care, and, in the case of transgender people, gender-sensitive treatment; stresses that access to healthcare, including preventive care, should be based on health needs; calls on the Commission and the Member States to ensure that Europe’s Beating Cancer Pla
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196590` § 45/1: the text without the words ‘and trans-specific healthcare, and to remove any coercive and unnecessary …

- **Result:** ADOPTED 433-153-53
- **A favour vote means:** For keeping the passage WITHOUT the words ‘and trans-specific healthcare, and to remove any coercive and unnecessary medical requirements, such as sterilisation, which hinder…; those words were put separately as the next part.
- **Text:** Adopted § 48 (quote found in the adopted text): 48. Calls on the Commission and the Member States to address the specific healthcare needs of LGBTIQ+ people, including by ensuring access to preventive care, treatment, and trans-specific healthcare, and to remove any coercive and unnecessary medical requirements, such as sterilisation, which hinder access to legal recognition and reproductive services, in line with the rulings of the European Court of Human Rights; recognises the commitment from the Commission, in its LGBTIQ+ equality strategy 2026-2030, to facilitate exchanges of best practices between the Member States in this respect; encourages support for community-based healthcare initi
- **Lobbies:** EPP 110-18-27, S&D 123-0-0, PfE 31-34-11, ECR 6-70-0, Renew 69-0-2, Greens 50-0-0, Left 38-0-0, ESN 0-22-1, NI 6-9-12
- **Proposed:** evidence only, never places -- This part put the passage WITHOUT the contested words, which were voted as the next part; it records nothing about those words.

### [ ] `MTG-PL-2026-09-16-DEC-196597` § 48/1: the text without the words ‘Calls on the Commission and the Member States to ensure access for all to …

- **Result:** ADOPTED 510-78-54
- **A favour vote means:** For keeping the passage WITHOUT the words ‘Calls on the Commission and the Member States to ensure access for all to affordable, high-quality, toxin-free and environmentally…; those words were put separately as the next part.
- **Lobbies:** EPP 147-4-7, S&D 129-0-2, PfE 52-12-9, ECR 8-35-30, Renew 66-1-1, Greens 50-0-0, Left 39-0-0, ESN 0-23-0, NI 19-3-5
- **Proposed:** evidence only, never places -- This part put the passage WITHOUT the contested words, which were voted as the next part; it records nothing about those words.

### [ ] `MTG-PL-2026-09-16-DEC-196598` § 48/2: ‘Calls on the Commission and the Member States to ensure access for all to affordable, high-quality, t…

- **Result:** ADOPTED 409-150-79
- **A favour vote means:** For keeping the words ‘Calls on the Commission and the Member States to ensure access for all to affordable, high-quality, toxin-free and environmentally sustainable – particularly…
- **Lobbies:** EPP 107-9-34, S&D 127-0-2, PfE 0-41-33, ECR 2-71-4, Renew 68-2-0, Greens 50-0-0, Left 38-0-0, ESN 0-23-0, NI 17-4-6
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196599` § 48/3: ‘free or’

- **Result:** ADOPTED 322-313-19
- **A favour vote means:** For keeping the words ‘free or’
- **Lobbies:** EPP 20-134-5, S&D 129-0-2, PfE 0-73-4, ECR 2-74-2, Renew 65-2-3, Greens 49-0-0, Left 40-0-0, ESN 0-23-0, NI 17-7-3
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196602` § 58

- **Result:** ADOPTED 413-189-43
- **A favour vote means:** For keeping § 58 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 62 (inferred: motion numbering +4, from the nearest quoted split): 62. Recognises that research and innovation are driven by a balance of incentives and obligations and that EU funding can play a significant role in encouraging greater investment in research into gender-specific issues and addressing the inequalities in access to treatment across the EU, including prevention, early diagnosis and long-term management of chronic conditions affecting women throughout their lives; stresses that there is little incentive for the private sector to invest in preventive care, and that it should therefore be a priority of the Commission and the Member States to invest in specific preventive
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196603` § 58

- **Result:** REJECTED 294-339-13
- **A favour vote means:** For keeping § 58 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 62 (inferred: motion numbering +4, from the nearest quoted split): 62. Recognises that research and innovation are driven by a balance of incentives and obligations and that EU funding can play a significant role in encouraging greater investment in research into gender-specific issues and addressing the inequalities in access to treatment across the EU, including prevention, early diagnosis and long-term management of chronic conditions affecting women throughout their lives; stresses that there is little incentive for the private sector to invest in preventive care, and that it should therefore be a priority of the Commission and the Member States to invest in specific preventive
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196606` § 62/1: the text without the words ‘calls on the Commission to prioritise earmarked funding under the new Euro…

- **Result:** ADOPTED 450-168-37
- **A favour vote means:** For keeping the passage WITHOUT the words ‘calls on the Commission to prioritise earmarked funding under the new European Competitiveness Fund and Horizon Europe 2028-2034 (F…; those words were put separately as the next part.
- **Text:** Adopted § 66 (quote found in the adopted text): 66. Calls for the Commission to develop and implement a specific women’s health strategy, embedded in the European Pillar of Social Rights at EU level, to be implemented across the Member States, with the aim of reducing gender health gaps, boosting public research into gender-specific conditions and guaranteeing equal access to healthcare across the EU; stresses that the strategy should include specific indicators and reporting requirements regarding progress; calls on the Commission to prioritise earmarked funding under the new European Competitiveness Fund and Horizon Europe 2028-2034 (FP10) for research into women’s health; calls for dedica
- **Lobbies:** EPP 153-7-2, S&D 128-0-0, PfE 0-62-15, ECR 6-65-6, Renew 63-0-7, Greens 50-0-0, Left 40-0-0, ESN 0-24-0, NI 10-10-7
- **Proposed:** evidence only, never places -- This part put the passage WITHOUT the contested words, which were voted as the next part; it records nothing about those words.

### [ ] `MTG-PL-2026-09-16-DEC-196607` § 62/2: ‘calls on the Commission to prioritise earmarked funding under the new European Competitiveness Fund a…

- **Result:** ADOPTED 446-138-59
- **A favour vote means:** For keeping the words ‘calls on the Commission to prioritise earmarked funding under the new European Competitiveness Fund and Horizon Europe 2028-2034 (FP10) for research into wome…
- **Text:** Adopted § 66 (quote found in the adopted text): 66. Calls for the Commission to develop and implement a specific women’s health strategy, embedded in the European Pillar of Social Rights at EU level, to be implemented across the Member States, with the aim of reducing gender health gaps, boosting public research into gender-specific conditions and guaranteeing equal access to healthcare across the EU; stresses that the strategy should include specific indicators and reporting requirements regarding progress; calls on the Commission to prioritise earmarked funding under the new European Competitiveness Fund and Horizon Europe 2028-2034 (FP10) for research into women’s health; calls for dedica
- **Lobbies:** EPP 126-7-24, S&D 129-0-0, PfE 30-28-16, ECR 2-73-1, Renew 62-0-8, Greens 49-0-0, Left 40-0-0, ESN 0-23-0, NI 8-7-10
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196608` § 62/3: ‘ring-fenced’

- **Result:** ADOPTED 325-296-33
- **A favour vote means:** For keeping the words ‘ring-fenced’
- **Lobbies:** EPP 7-152-3, S&D 129-0-0, PfE 27-39-11, ECR 0-76-0, Renew 61-2-8, Greens 50-0-0, Left 40-0-0, ESN 0-23-0, NI 11-4-11
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196610` § 63/1: ‘Emphasises the critical role of civil society organisations in providing needs-based, community-level…

- **Result:** ADOPTED 460-129-64
- **A favour vote means:** For keeping the words ‘Emphasises the critical role of civil society organisations in providing needs-based, community-level and peer-to-peer healthcare services, particularly for w…
- **Text:** Adopted § 67 (quote found in the adopted text): 67. Emphasises the critical role of civil society organisations in providing needs-based, community-level and peer-to-peer healthcare services, particularly for women facing poverty, discrimination or social exclusion; stresses that these organisations act as a bridge between patients and public institutions, and also work to advance gender equality and SRHR, collect data on women’s health experiences and needs, prevent online health scams, and contribute to ensuring more gender-inclusive laws and policies in the field of healthcare; calls for their role to be explicitly acknowledged, in the upcoming European Competitiveness Fund and AgoraEU pr
- **Lobbies:** EPP 154-6-2, S&D 128-0-0, PfE 0-22-55, ECR 5-67-4, Renew 69-0-0, Greens 50-0-0, Left 40-0-0, ESN 0-24-0, NI 14-10-3
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196614` Recital B/1: ‘whereas multiple and intersecting barriers to accessing healthcare services, as well as complex …

- **Result:** ADOPTED 395-179-63
- **A favour vote means:** For keeping the words ‘whereas multiple and intersecting barriers to accessing healthcare services, as well as complex health needs, are encountered by refugee and ethnic minority w…
- **Text:** Adopted recital B (quote found in the adopted text): B. whereas multiple and intersecting barriers to accessing healthcare services, as well as complex health needs, are encountered by refugee and ethnic minority women, women living in poverty, unhoused women, women in precarious employment or with unpaid care responsibilities, older women, women with disabilities, women residing in rural and socio-economically disadvantaged areas and individuals from LGBTIQ+ communities in particular; whereas an intersectional approach to women’s health is therefore essential;
- **Lobbies:** EPP 97-41-20, S&D 122-0-0, PfE 4-35-34, ECR 4-70-0, Renew 69-0-1, Greens 50-0-0, Left 40-0-0, ESN 0-23-0, NI 9-10-8
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196615` Recital B/2: ‘whereas an intersectional approach to women’s health is therefore essential;’

- **Result:** ADOPTED 411-213-21
- **A favour vote means:** For keeping the words ‘whereas an intersectional approach to women’s health is therefore essential;’
- **Text:** Adopted recital B (quote found in the adopted text): B. whereas multiple and intersecting barriers to accessing healthcare services, as well as complex health needs, are encountered by refugee and ethnic minority women, women living in poverty, unhoused women, women in precarious employment or with unpaid care responsibilities, older women, women with disabilities, women residing in rural and socio-economically disadvantaged areas and individuals from LGBTIQ+ communities in particular; whereas an intersectional approach to women’s health is therefore essential;
- **Lobbies:** EPP 119-23-16, S&D 127-1-1, PfE 0-77-0, ECR 4-73-1, Renew 64-2-1, Greens 49-0-0, Left 38-0-0, ESN 0-23-0, NI 10-14-2
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on gender inequalities in health report policy, not on our issues.

### [ ] `MTG-PL-2026-09-16-DEC-196618` Recital C

- **Result:** REJECTED 302-313-31
- **A favour vote means:** For keeping Recital C as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital C (motion numbering unchanged (checked against the nearest quoted split)): C. whereas poverty and social exclusion have a significant impact on health outcomes and access to healthcare; whereas women face greater financial barriers than men in accessing health services; whereas these barriers are further exacerbated for vulnerable groups, who often face additional layers of discrimination and encounter multiple barriers to accessing inclusive, quality healthcare;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196619` Recital D

- **Result:** ADOPTED 593-37-16
- **A favour vote means:** For keeping Recital D as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital D (motion numbering unchanged (checked against the nearest quoted split)): D. whereas unequal access to healthcare services across the EU, particularly in rural, remote and mountainous areas, islands and outermost regions, constitutes a significant barrier to timely diagnosis and treatment, including for pregnant women;
- **Lobbies:** EPP 156-1-0, S&D 126-0-1, PfE 54-13-10, ECR 74-1-2, Renew 67-0-0, Greens 50-0-0, Left 40-0-0, ESN 3-21-0, NI 23-1-3
- **Proposed:** evidence only, never places -- Near-unanimous (593-37): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-09-16-DEC-196622` Recital G

- **Result:** ADOPTED 322-281-35
- **A favour vote means:** For keeping Recital G as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital G (motion numbering unchanged (checked against the nearest quoted split)): G. whereas medical research has historically been male-centric, leading to insufficient understanding of women’s health, physiology and sex-based differences; whereas this systemic inequality in medicine has an impact on the diagnosis, treatment, morbidity and mortality of under-represented sections of the population, including women and gender-diverse people;
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196624` Recital J/1: the text without the words ‘transgender, non-binary and intersex people and’

- **Result:** ADOPTED 509-115-17
- **A favour vote means:** For keeping the passage WITHOUT the words ‘transgender, non-binary and intersex people and’; those words were put separately as the next part.
- **Text:** Adopted recital J (quote found in the adopted text): J. whereas transgender, non-binary and intersex people and marginalised communities, such as ethnic minorities and women with disabilities, are often absent or disproportionally excluded from clinical trials and medical research, resulting in significant gaps in evidence regarding the safety and effectiveness of treatments; whereas this lack of data contributes to unequal access to appropriate, timely and high-quality healthcare;
- **Lobbies:** EPP 152-4-2, S&D 120-0-0, PfE 46-20-11, ECR 13-61-1, Renew 70-0-0, Greens 50-0-0, Left 40-0-0, ESN 0-24-0, NI 18-6-3
- **Proposed:** evidence only, never places -- This part put the passage WITHOUT the contested words, which were voted as the next part; it records nothing about those words.

### [ ] `MTG-PL-2026-09-16-DEC-196628` Recital O

- **Result:** ADOPTED 410-173-47
- **A favour vote means:** For keeping Recital O as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital O (motion numbering unchanged (checked against the nearest quoted split)): O. whereas obstetric and gynaecological violence, including verbal abuse, discrimination and non-consensual procedures during pregnancy, childbirth and abortion care, constitutes a violation of women’s rights and dignity, and remains a widespread yet under-recognised issue across the EU; whereas obstetric and gynaecological violence disproportionately affects women with disabilities and women from ethnic minorities, including Roma women, as well as intersex and transgender people; whereas the Commission, in its Gender Equality Strategy 2020-2025, committed to issuing a recommendation on preventing harm
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196629` Recital O

- **Result:** ADOPTED 319-261-36
- **A favour vote means:** For keeping Recital O as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital O (motion numbering unchanged (checked against the nearest quoted split)): O. whereas obstetric and gynaecological violence, including verbal abuse, discrimination and non-consensual procedures during pregnancy, childbirth and abortion care, constitutes a violation of women’s rights and dignity, and remains a widespread yet under-recognised issue across the EU; whereas obstetric and gynaecological violence disproportionately affects women with disabilities and women from ethnic minorities, including Roma women, as well as intersex and transgender people; whereas the Commission, in its Gender Equality Strategy 2020-2025, committed to issuing a recommendation on preventing harm
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196632` Recital W

- **Result:** ADOPTED 341-263-37
- **A favour vote means:** For keeping Recital W as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital W (motion numbering unchanged (checked against the nearest quoted split)): W. whereas according to the World Health Organization (WHO), global health challenges, including infectious diseases, antimicrobial resistance and climate-related health threats, have differentiated impacts on women and girls; whereas people in low- and middle-income countries face disproportionate gender inequalities in health compared to high-income countries in terms of mortality and serious morbidity, notably related to sexual and reproductive health and rights (SRHR);
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196633` Recital W

- **Result:** ADOPTED 400-163-76
- **A favour vote means:** For keeping Recital W as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital W (motion numbering unchanged (checked against the nearest quoted split)): W. whereas according to the World Health Organization (WHO), global health challenges, including infectious diseases, antimicrobial resistance and climate-related health threats, have differentiated impacts on women and girls; whereas people in low- and middle-income countries face disproportionate gender inequalities in health compared to high-income countries in terms of mortality and serious morbidity, notably related to sexual and reproductive health and rights (SRHR);
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-09-16-DEC-196638` Recital AC/1: ‘whereas 14 % of LGBTIQ+ people have reported experiencing discrimination in healthcare settings…

- **Result:** ADOPTED 466-128-40
- **A favour vote means:** For keeping the words ‘whereas 14 % of LGBTIQ+ people have reported experiencing discrimination in healthcare settings;’
- **Lobbies:** EPP 128-10-14, S&D 121-0-0, PfE 33-23-19, ECR 9-66-1, Renew 71-0-1, Greens 50-0-0, Left 39-0-0, ESN 0-23-0, NI 15-6-5
- **Proposed:** evidence only, never places -- A statistic (14 % of LGBTIQ+ people report discrimination in healthcare). It tells members apart only on their willingness to cite it; the transition-healthcare half of the recital (AC/2) carries the question.

## Global health resilience (2026-09-17)

### [ ] `MTG-PL-2026-09-17-DEC-196774` Motion for a resolution (as a whole)

- **Result:** ADOPTED 319-142-19
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 96-1-4, S&D 91-0-0, PfE 0-52-5, ECR 4-55-1, Renew 53-1-3, Greens 39-0-0, Left 34-0-0, ESN 0-21-1, NI 2-12-5
- **Proposed side:** AGAINST (medium confidence)
  - favour: Backed the resolution on global health resilience, which laments funding cuts to SRHR (recital E) and asks the EU to address women's and girls' 'need for universal access to sexual and reproductive health services' in partner countries (§ 17).
  - against: Opposed the global health resolution that puts SRHR into EU development health funding.
- **Flag for you:** The SRHR content is recital E and part of § 17 inside a broad global-health text, and § 17 adds 'while respecting partner countries' competencies'. The same frame as the SDG whole-motion vote you signed against on 1 September.

## Social media and young people (2026-09-17)

### [x] `MTG-PL-2026-09-17-DEC-196806` the words "and rights" after "sexual and reproductive health" (§ 85, part 2)

- **Signed side:** against

### [x] `MTG-PL-2026-09-17-DEC-196809` the words ", including age-appropriate sexual education," (Recital AD, part 2)

- **Signed side:** against

### [ ] `MTG-PL-2026-09-17-DEC-196147` Motion for a resolution (as a whole)

- **Result:** ADOPTED 395-136-80
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 143-3-8, S&D 115-0-0, PfE 0-24-45, ECR 3-60-10, Renew 61-6-0, Greens 45-0-4, Left 24-8-4, ESN 1-23-1, NI 3-12-8
- **Proposed side:** AGAINST (low confidence)
  - favour: Backed the report on social media and young people, which besides child-protection measures online speaks of 'sexual and reproductive health and rights' for young people (§ 85) and names age-appropriate sexual education (recital AD), and calls for a harmonised EU minimum digital age.
  - against: Opposed the social media report, whose text kept the SRHR and sexual-education words and centralises the digital age of minors at EU level.
- **Flag for you:** Low. The SRHR and sex-education words are signed separately (§ 85/2, recital AD/2) and stayed in. The rest is child protection online (age-appropriate design, parental controls, kidfluencers) that CitizenGO may welcome. Sign evidence-only if you would rather place members on the two signed splits alone.

### [ ] `MTG-PL-2026-09-17-DEC-196800` § 63/3: ‘stresses the need for a harmonised EU approach to establishing a minimum digital age and, in this con…

- **Result:** ADOPTED 401-181-29
- **A favour vote means:** For keeping the words ‘stresses the need for a harmonised EU approach to establishing a minimum digital age and, in this context, welcomes the conclusions of the Commission’s specia…
- **Text:** Adopted § 63 (quote found in the adopted text): 63. Welcomes the favourable consideration expressed by Commission President Ursula von der Leyen regarding the introduction of a harmonised, EU-wide minimum age limit for access to social media (a minimum digital age); takes note of the initiatives already undertaken by certain Member States, in this regard; stresses the need for a harmonised EU approach to establishing a minimum digital age and, in this context, welcomes the conclusions of the Commission’s special panel of experts on child safety online, which provides guidance on this matter; welcomes, furthermore, the announcement made by President von der Leyen about a legislative proposal 
- **Lobbies:** EPP 149-2-4, S&D 112-1-2, PfE 4-56-9, ECR 5-63-6, Renew 58-8-1, Greens 48-0-1, Left 21-11-4, ESN 0-25-0, NI 4-15-2
- **Proposed:** no direction -- 'Stresses the need for a harmonised EU approach to establishing a minimum digital age.' Whether an EU-wide digital age protects children or takes the decision from parents and Member States is a policy call; no side drafted.
- **Flag for you:** Same question as the media literacy report's § 16/2 (7 July).

### [ ] `MTG-PL-2026-09-17-DEC-196808` Recital AD/1: the text without the words ‘, including age-appropriate sexual education,’

- **Result:** ADOPTED 575-13-19
- **A favour vote means:** For keeping the passage WITHOUT the words ‘, including age-appropriate sexual education,’; those words were put separately as the next part.
- **Text:** Adopted recital AD (quote found in the adopted text): AD. whereas access to health education, including age-appropriate sexual education, can contribute to the well-being and autonomy of young people, while fully respecting national competences;
- **Lobbies:** EPP 152-1-1, S&D 112-0-0, PfE 67-0-2, ECR 69-4-0, Renew 66-0-0, Greens 49-0-0, Left 36-0-0, ESN 5-5-15, NI 19-3-1
- **Proposed:** evidence only, never places -- Near-unanimous (575-13): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

## EU-China recommendation (2026-10-07)

### [ ] `MTG-PL-2026-10-07-DEC-197819` § 1, après le point a – Am 12

- **Result:** REJECTED 200-420-48
- **A favour vote means:** For amendment 12 (amending § 1, after point a). Its words are not in the store.
- **Lobbies:** EPP 3-169-0, S&D 90-25-10, PfE 25-25-22, ECR 9-69-2, Renew 1-71-3, Greens 7-41-1, Left 38-1-3, ESN 9-15-2, NI 18-4-5
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197820` § 1, après le point a – Am 60

- **Result:** REJECTED 211-440-5
- **A favour vote means:** For amendment 60 (amending § 1, after point a). Its words are not in the store.
- **Lobbies:** EPP 12-152-1, S&D 1-120-1, PfE 72-0-0, ECR 79-1-1, Renew 0-74-0, Greens 0-47-0, Left 0-42-0, ESN 26-0-0, NI 21-4-2
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197821` § 1, point c – Am 13

- **Result:** REJECTED 69-569-28
- **A favour vote means:** For amendment 13 (amending § 1, point c). Its words are not in the store.
- **Lobbies:** EPP 2-169-1, S&D 4-117-3, PfE 5-57-10, ECR 6-74-0, Renew 1-74-0, Greens 0-48-0, Left 26-8-8, ESN 9-16-1, NI 16-6-5
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197823` § 1, après le point h – Am 27

- **Result:** REJECTED 206-336-119
- **A favour vote means:** For amendment 27 (amending § 1, after point h). Its words are not in the store.
- **Lobbies:** EPP 30-138-4, S&D 2-101-20, PfE 63-0-9, ECR 79-0-2, Renew 16-55-2, Greens 0-0-45, Left 2-36-4, ESN 1-0-25, NI 13-6-8
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197824` § 1, après le point i – Am 64

- **Result:** REJECTED 141-463-51
- **A favour vote means:** For amendment 64 (amending § 1, after point i). Its words are not in the store.
- **Lobbies:** EPP 5-165-2, S&D 0-113-2, PfE 53-4-15, ECR 44-15-22, Renew 0-72-0, Greens 0-50-0, Left 1-41-0, ESN 25-0-0, NI 13-3-10
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197825` § 1, après le point j – Am 29

- **Result:** ADOPTED 362-266-24
- **A favour vote means:** For amendment 29 (amending § 1, after point j). Its words are not in the store.
- **Lobbies:** EPP 168-4-1, S&D 11-102-0, PfE 63-0-9, ECR 77-2-2, Renew 16-55-1, Greens 1-49-0, Left 2-35-2, ESN 16-6-4, NI 8-13-5
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197826` § 1, point k – Am 32

- **Result:** REJECTED 181-449-33
- **A favour vote means:** For amendment 32 (amending § 1, point k). Its words are not in the store.
- **Lobbies:** EPP 9-157-3, S&D 0-124-0, PfE 63-0-8, ECR 77-2-2, Renew 0-73-2, Greens 0-50-0, Left 2-38-2, ESN 17-0-9, NI 13-5-7
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197827` § 1, après le point k – Am 33

- **Result:** REJECTED 214-437-14
- **A favour vote means:** For amendment 33 (amending § 1, after point k). Its words are not in the store.
- **Lobbies:** EPP 23-143-4, S&D 0-124-0, PfE 71-0-0, ECR 74-4-2, Renew 0-75-0, Greens 0-50-0, Left 2-38-2, ESN 25-0-1, NI 19-3-5
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197828` § 1, après le point k – Am 66

- **Result:** REJECTED 174-450-19
- **A favour vote means:** For amendment 66 (amending § 1, after point k). Its words are not in the store.
- **Lobbies:** EPP 8-160-3, S&D 1-112-1, PfE 63-0-0, ECR 72-1-6, Renew 0-75-0, Greens 0-50-0, Left 2-39-0, ESN 24-0-1, NI 4-13-8
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197829` § 1, point l – Am 16

- **Result:** REJECTED 130-491-45
- **A favour vote means:** For amendment 16 (amending § 1, point l). Its words are not in the store.
- **Lobbies:** EPP 0-171-0, S&D 84-37-3, PfE 0-57-14, ECR 1-77-2, Renew 0-75-0, Greens 0-42-8, Left 31-3-8, ESN 0-25-1, NI 14-4-9
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197831` § 1, après le point o – Am 67

- **Result:** REJECTED 195-439-23
- **A favour vote means:** For amendment 67 (amending § 1, after point o). Its words are not in the store.
- **Lobbies:** EPP 14-157-1, S&D 0-115-0, PfE 63-0-9, ECR 76-1-3, Renew 0-74-1, Greens 0-50-0, Left 0-39-1, ESN 24-0-2, NI 18-3-6
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197832` § 1, point v – Am 34

- **Result:** REJECTED 180-477-13
- **A favour vote means:** For amendment 34 (amending § 1, point v). Its words are not in the store.
- **Lobbies:** EPP 0-172-1, S&D 0-124-0, PfE 72-0-0, ECR 73-2-6, Renew 0-75-0, Greens 0-50-0, Left 0-42-0, ESN 26-0-0, NI 9-12-6
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197833` § 1, après le point y – Am 69

- **Result:** REJECTED 185-438-29
- **A favour vote means:** For amendment 69 (amending § 1, after point y). Its words are not in the store.
- **Lobbies:** EPP 10-160-1, S&D 0-112-2, PfE 61-0-9, ECR 80-1-0, Renew 1-74-0, Greens 0-49-0, Left 1-40-0, ESN 25-0-1, NI 7-2-16
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197835` § 1, point ab – Am 20

- **Result:** REJECTED 91-541-13
- **A favour vote means:** For amendment 20 (amending § 1, point ab). Its words are not in the store.
- **Lobbies:** EPP 4-167-0, S&D 3-116-0, PfE 0-57-6, ECR 6-74-0, Renew 2-71-0, Greens 0-45-1, Left 33-8-0, ESN 23-1-1, NI 20-2-5
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197836` § 1, après le point ab – Am 30

- **Result:** ADOPTED 416-153-91
- **A favour vote means:** For amendment 30 (amending § 1, after point ab). Its words are not in the store.
- **Lobbies:** EPP 171-1-1, S&D 34-85-3, PfE 57-0-14, ECR 73-4-1, Renew 72-3-0, Greens 3-1-42, Left 1-39-2, ESN 1-1-24, NI 4-19-4
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197837` § 1, point ac – Am 21S

- **Result:** REJECTED 74-559-18
- **A favour vote means:** For amendment 21S (amending § 1, point ac). Its words are not in the store.
- **Lobbies:** EPP 1-168-1, S&D 1-120-0, PfE 0-58-6, ECR 4-76-0, Renew 0-74-1, Greens 0-49-1, Left 29-9-3, ESN 21-2-0, NI 18-3-6
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197838` § 1, point ai – Am 35

- **Result:** REJECTED 187-473-9
- **A favour vote means:** For amendment 35 (amending § 1, point ai). Its words are not in the store.
- **Lobbies:** EPP 3-168-1, S&D 0-125-0, PfE 72-0-0, ECR 71-4-6, Renew 0-74-0, Greens 0-50-0, Left 0-42-0, ESN 26-0-0, NI 15-10-2
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197844` § 1, après le point aq – Am 31

- **Result:** ADOPTED 382-173-95
- **A favour vote means:** For amendment 31 (amending § 1, after point aq). Its words are not in the store.
- **Lobbies:** EPP 170-1-1, S&D 4-97-23, PfE 50-7-5, ECR 75-0-4, Renew 71-3-0, Greens 6-0-40, Left 1-39-1, ESN 1-8-16, NI 4-18-5
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197849` § 1, après le point aw – Am 22

- **Result:** REJECTED 55-482-121
- **A favour vote means:** For amendment 22 (amending § 1, after point aw). Its words are not in the store.
- **Lobbies:** EPP 1-166-1, S&D 8-25-89, PfE 0-66-5, ECR 2-76-2, Renew 0-74-0, Greens 3-44-3, Left 27-1-12, ESN 1-23-2, NI 13-7-7
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197850` Après le § 2 – Am 23

- **Result:** REJECTED 56-489-116
- **A favour vote means:** For amendment 23 (inserting After § 2). Its words are not in the store.
- **Lobbies:** EPP 0-171-1, S&D 8-38-76, PfE 0-58-14, ECR 4-74-2, Renew 1-72-0, Greens 3-45-2, Left 26-3-12, ESN 1-22-2, NI 13-6-7
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197851` § 5 – Am 36

- **Result:** REJECTED 195-457-10
- **A favour vote means:** For amendment 36 (amending § 5). Its words are not in the store.
- **Lobbies:** EPP 20-148-2, S&D 0-123-0, PfE 71-0-0, ECR 76-3-2, Renew 1-74-0, Greens 0-49-0, Left 0-42-0, ESN 24-0-2, NI 3-18-4
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197852` Après le considérant A – Am 48

- **Result:** REJECTED 159-499-8
- **A favour vote means:** For amendment 48 (inserting After recital A). Its words are not in the store.
- **Lobbies:** EPP 3-168-1, S&D 0-125-0, PfE 72-0-0, ECR 39-40-2, Renew 0-74-1, Greens 0-50-0, Left 1-37-2, ESN 26-0-0, NI 18-5-2
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197856` Après le considérant F – Am 5

- **Result:** REJECTED 133-466-66
- **A favour vote means:** For amendment 5 (inserting After recital F). Its words are not in the store.
- **Lobbies:** EPP 1-169-0, S&D 78-43-1, PfE 0-32-40, ECR 3-76-2, Renew 1-74-0, Greens 1-44-5, Left 29-8-5, ESN 2-15-9, NI 18-5-4
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197857` Après le considérant G – Am 51

- **Result:** REJECTED 105-534-25
- **A favour vote means:** For amendment 51 (inserting After recital G). Its words are not in the store.
- **Lobbies:** EPP 0-171-1, S&D 0-123-0, PfE 55-0-17, ECR 5-71-4, Renew 0-75-0, Greens 1-48-0, Left 0-40-0, ESN 26-0-0, NI 18-6-3
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197858` Considérant H – Am 25

- **Result:** ADOPTED 429-140-80
- **A favour vote means:** For amendment 25 (amending recital H). Its words are not in the store.
- **Lobbies:** EPP 170-1-1, S&D 41-76-7, PfE 57-0-5, ECR 76-2-1, Renew 72-3-0, Greens 3-0-43, Left 3-36-3, ESN 4-3-17, NI 3-19-3
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197859` Considérant I – Am 8

- **Result:** REJECTED 69-562-30
- **A favour vote means:** For amendment 8 (amending recital I). Its words are not in the store.
- **Lobbies:** EPP 1-170-1, S&D 3-120-2, PfE 5-57-9, ECR 7-73-0, Renew 1-73-0, Greens 0-43-4, Left 24-7-9, ESN 10-14-1, NI 18-5-4
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197860` Après le considérant L – Am 9

- **Result:** REJECTED 72-454-139
- **A favour vote means:** For amendment 9 (inserting After recital L). Its words are not in the store.
- **Lobbies:** EPP 0-171-0, S&D 5-29-88, PfE 0-32-40, ECR 4-75-1, Renew 1-74-0, Greens 7-41-2, Left 40-1-1, ESN 0-24-2, NI 15-7-5
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197861` Après le considérant L – Am 52

- **Result:** REJECTED 191-460-12
- **A favour vote means:** For amendment 52 (inserting After recital L). Its words are not in the store.
- **Lobbies:** EPP 0-170-1, S&D 1-124-0, PfE 65-0-7, ECR 79-1-0, Renew 0-72-1, Greens 0-49-0, Left 0-41-0, ESN 26-0-0, NI 20-3-3
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197862` Après le considérant N – Am 55

- **Result:** REJECTED 203-457-8
- **A favour vote means:** For amendment 55 (inserting After recital N). Its words are not in the store.
- **Lobbies:** EPP 9-162-1, S&D 0-125-0, PfE 72-0-0, ECR 80-1-0, Renew 0-74-0, Greens 0-50-0, Left 0-42-0, ESN 25-0-0, NI 17-3-7
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197863` Après le considérant N – Am 56

- **Result:** REJECTED 190-468-10
- **A favour vote means:** For amendment 56 (inserting After recital N). Its words are not in the store.
- **Lobbies:** EPP 1-169-2, S&D 0-124-0, PfE 68-4-0, ECR 76-1-4, Renew 0-75-0, Greens 0-50-0, Left 0-42-0, ESN 26-0-0, NI 19-3-4
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It was rejected, so its words are in no adopted text; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197866` Considérant AO – Am 40/2: ‘comprehensive strategic partnership’ and the deletion of the word ‘policy’

- **Result:** ADOPTED 357-270-36
- **A favour vote means:** For amendment 40/2 (amending recital AO). Its words are not in the store.
- **Lobbies:** EPP 138-24-8, S&D 101-22-1, PfE 7-51-14, ECR 3-74-3, Renew 47-27-0, Greens 7-42-1, Left 39-3-0, ESN 2-22-2, NI 13-5-7
- **Proposed:** no direction -- Amendment text not in the store: EP labels carry only the amendment's number, and plenary amendment documents are not reachable by any URL the pipeline can verify. It carried, so its words are in the adopted text near that position; read it before proposing a side.

### [ ] `MTG-PL-2026-10-07-DEC-197412` item not named in the label

- **Result:** ADOPTED 366-222-78
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-07-DEC-197425` item not named in the label

- **Result:** REJECTED 290-311-65
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-07-DEC-197436` item not named in the label

- **Result:** ADOPTED 466-161-35
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-07-DEC-197457` Proposition de résolution (ensemble du texte)

- **Result:** ADOPTED 454-86-110
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 150-0-9, S&D 58-3-63, PfE 55-0-17, ECR 68-5-4, Renew 73-0-1, Greens 41-0-8, Left 6-33-3, ESN 1-23-2, NI 2-22-3
- **Proposed:** evidence only, never places -- A broad foreign-policy recommendation to the Council. Its freedom-of-religion passages (Sinicisation of religion, the Dalai Lama's succession, repression of religious minorities) are uncontroversial; the lobbies split on China policy (The Left 6-33, S&D 58-3-63), not on religious freedom.
- **Flag for you:** Sign favour instead if you want the religious-freedom passages to count; it would place almost the whole House.

### [ ] `MTG-PL-2026-10-07-DEC-197822` § 1, point e – Am 1

- **Result:** ADOPTED 571-54-31
- **A favour vote means:** For amendment 1 (amending § 1, point e). Its words are not in the store.
- **Lobbies:** EPP 171-0-0, S&D 120-0-3, PfE 58-5-0, ECR 73-2-4, Renew 74-1-0, Greens 50-0-0, Left 20-19-3, ESN 2-10-14, NI 3-17-7
- **Proposed:** evidence only, never places -- Near-unanimous (571-54): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-10-07-DEC-197830` § 1, point n – Am 2

- **Result:** ADOPTED 566-40-50
- **A favour vote means:** For amendment 2 (amending § 1, point n). Its words are not in the store.
- **Lobbies:** EPP 171-1-1, S&D 121-0-1, PfE 58-5-0, ECR 74-0-6, Renew 73-1-1, Greens 50-0-0, Left 16-19-6, ESN 0-1-24, NI 3-13-11
- **Proposed:** evidence only, never places -- Near-unanimous (566-40): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-10-07-DEC-197839` § 1, point am – Am 3

- **Result:** ADOPTED 546-25-66
- **A favour vote means:** For amendment 3 (amending § 1, point am). Its words are not in the store.
- **Lobbies:** EPP 159-2-1, S&D 122-0-2, PfE 56-0-5, ECR 67-3-8, Renew 75-0-0, Greens 50-0-0, Left 13-4-17, ESN 0-2-24, NI 4-14-9
- **Proposed:** evidence only, never places -- Near-unanimous (546-25): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-10-07-DEC-197840` § 1, après le point am – Am 24

- **Result:** ADOPTED 500-43-122
- **A favour vote means:** For amendment 24 (amending § 1, after point am). Its words are not in the store.
- **Lobbies:** EPP 171-0-1, S&D 39-0-84, PfE 63-0-9, ECR 75-4-1, Renew 75-0-0, Greens 50-0-0, Left 20-17-4, ESN 1-7-17, NI 6-15-6
- **Proposed:** evidence only, never places -- Near-unanimous (500-43): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-10-07-DEC-197841` § 1, point ao – Am 4

- **Result:** ADOPTED 573-26-49
- **A favour vote means:** For amendment 4 (amending § 1, point ao). Its words are not in the store.
- **Lobbies:** EPP 170-0-1, S&D 123-0-0, PfE 58-0-5, ECR 74-5-2, Renew 74-0-0, Greens 50-0-0, Left 16-1-17, ESN 2-7-16, NI 6-13-8
- **Proposed:** evidence only, never places -- Near-unanimous (573-26): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-10-07-DEC-197842` § 1, après le point ao – Am 42

- **Result:** ADOPTED 536-40-78
- **A favour vote means:** For amendment 42 (amending § 1, after point ao). Its words are not in the store.
- **Lobbies:** EPP 167-0-1, S&D 121-0-1, PfE 11-16-43, ECR 71-4-5, Renew 74-0-0, Greens 49-0-0, Left 39-1-0, ESN 0-7-17, NI 4-12-11
- **Proposed:** evidence only, never places -- Near-unanimous (536-40): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-10-07-DEC-197843` § 1, après le point ao – Am 43

- **Result:** ADOPTED 569-37-45
- **A favour vote means:** For amendment 43 (amending § 1, after point ao). Its words are not in the store.
- **Lobbies:** EPP 160-0-6, S&D 121-0-1, PfE 48-0-23, ECR 73-4-4, Renew 74-0-0, Greens 50-0-0, Left 36-1-1, ESN 0-22-2, NI 7-10-8
- **Proposed:** evidence only, never places -- Near-unanimous (569-37): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-10-07-DEC-197847` § 1, point au/2: "et en achevant l’union européenne de la défense"

- **Result:** ADOPTED 415-218-31
- **A favour vote means:** For keeping the words "et en achevant l’union européenne de la défense"
- **Lobbies:** EPP 167-3-1, S&D 122-2-0, PfE 0-72-0, ECR 2-71-7, Renew 72-2-0, Greens 48-1-1, Left 3-20-18, ESN 0-25-0, NI 1-22-4
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on eu-china recommendation policy, not on our issues.

### [ ] `MTG-PL-2026-10-07-DEC-197848` § 1, point au/3: "ainsi qu’en mettant en œuvre une réforme institutionnelle au moyen d’une «convention d’urgen…

- **Result:** ADOPTED 379-266-19
- **A favour vote means:** For keeping the words "ainsi qu’en mettant en œuvre une réforme institutionnelle au moyen d’une «convention d’urgence»,"
- **Lobbies:** EPP 142-22-2, S&D 123-2-0, PfE 0-72-0, ECR 0-81-0, Renew 62-1-12, Greens 50-0-0, Left 1-38-3, ESN 1-25-0, NI 0-25-2
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on eu-china recommendation policy, not on our issues.

### [ ] `MTG-PL-2026-10-07-DEC-197855` Considérant F/2

- **Result:** ADOPTED 468-106-76
- **A favour vote means:** For one part of a split vote; the label does not say which words (the votes-results PDF does).
- **Lobbies:** EPP 171-0-0, S&D 48-22-52, PfE 53-0-9, ECR 74-5-2, Renew 74-1-0, Greens 42-4-1, Left 2-35-4, ESN 1-21-2, NI 3-18-6
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on eu-china recommendation policy, not on our issues.

### [ ] `MTG-PL-2026-10-07-DEC-197871` § 1, point aa

- **Result:** ADOPTED 498-76-86
- **A favour vote means:** For keeping § 1, point aa as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 1 (adopted-text numbering assumed equal to the motion (unchecked)): 1. Recommends that the Council, the Commission and the Vice-President of the Commission / High Representative of the Union for Foreign Affairs and Security Policy:
- **Lobbies:** EPP 172-0-1, S&D 51-19-53, PfE 58-0-14, ECR 77-1-2, Renew 74-0-1, Greens 50-0-0, Left 8-24-9, ESN 3-17-2, NI 5-15-4
- **Proposed:** evidence only, never places -- The words voted are not on CitizenGO's ground: the report's area tag comes from other passages, so placing members on this vote would score them on eu-china recommendation policy, not on our issues.

## Islamist entryism / Muslim Brotherhood (2026-10-08)

### [ ] `MTG-PL-2026-10-08-DEC-197939` § 1 – Am 88

- **Result:** REJECTED 173-394-18
- **A favour vote means:** For amendment 88 (amending § 1). Its words are not in the store.
- **Lobbies:** EPP 1-150-0, S&D 87-2-8, PfE 0-68-0, ECR 0-72-0, Renew 2-65-1, Greens 43-0-1, Left 37-0-0, ESN 0-26-0, NI 3-11-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197941` § 1 – Am 31/1

- **Result:** ADOPTED 352-218-9
- **A favour vote means:** For amendment 31/1 (amending § 1). Its words are not in the store.
- **Lobbies:** EPP 148-3-0, S&D 92-0-0, PfE 0-68-0, ECR 6-63-3, Renew 67-0-1, Greens 1-42-0, Left 1-34-2, ESN 25-1-0, NI 12-7-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197942` § 1 – Am 31/2

- **Result:** ADOPTED 366-178-32
- **A favour vote means:** For amendment 31/2 (amending § 1). Its words are not in the store.
- **Lobbies:** EPP 114-12-20, S&D 93-0-1, PfE 27-39-2, ECR 10-58-4, Renew 67-0-1, Greens 6-37-0, Left 37-0-0, ESN 0-25-1, NI 12-7-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197943` § 1 – Am 31/3

- **Result:** ADOPTED 348-169-41
- **A favour vote means:** For amendment 31/3 (amending § 1). Its words are not in the store.
- **Lobbies:** EPP 109-5-29, S&D 91-0-0, PfE 24-40-0, ECR 6-59-6, Renew 65-1-1, Greens 6-34-0, Left 36-0-0, ESN 1-21-4, NI 10-9-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197944` Après le § 1 – Am 58

- **Result:** REJECTED 194-374-7
- **A favour vote means:** For amendment 58 (inserting After § 1). Its words are not in the store.
- **Lobbies:** EPP 12-134-2, S&D 0-94-0, PfE 68-0-0, ECR 71-0-1, Renew 0-64-2, Greens 0-44-0, Left 1-34-0, ESN 26-0-0, NI 16-4-2
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197945` Après le § 1 – Am 59

- **Result:** REJECTED 199-363-5
- **A favour vote means:** For amendment 59 (inserting After § 1). Its words are not in the store.
- **Lobbies:** EPP 22-121-1, S&D 0-94-0, PfE 67-0-0, ECR 72-0-0, Renew 0-67-0, Greens 0-43-0, Left 0-35-0, ESN 24-0-1, NI 14-3-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197946` Après le § 1 – Am 60

- **Result:** REJECTED 189-359-23
- **A favour vote means:** For amendment 60 (inserting After § 1). Its words are not in the store.
- **Lobbies:** EPP 12-115-17, S&D 0-92-0, PfE 68-0-0, ECR 71-0-1, Renew 0-65-2, Greens 0-44-0, Left 0-37-0, ESN 25-0-0, NI 13-6-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197947` Après le § 1 – Am 61

- **Result:** REJECTED 201-351-15
- **A favour vote means:** For amendment 61 (inserting After § 1). Its words are not in the store.
- **Lobbies:** EPP 25-108-10, S&D 0-95-0, PfE 67-0-0, ECR 69-1-2, Renew 0-64-2, Greens 0-42-0, Left 0-36-0, ESN 25-1-0, NI 15-4-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197948` Après le § 1 – Am 89

- **Result:** REJECTED 191-376-11
- **A favour vote means:** For amendment 89 (inserting After § 1). Its words are not in the store.
- **Lobbies:** EPP 5-143-0, S&D 91-5-0, PfE 0-67-0, ECR 1-69-1, Renew 4-61-2, Greens 43-0-1, Left 37-0-0, ESN 0-24-2, NI 10-7-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197949` § 2 – Am 127

- **Result:** REJECTED 194-382-3
- **A favour vote means:** For amendment 127 (amending § 2). Its words are not in the store.
- **Lobbies:** EPP 5-143-0, S&D 91-1-1, PfE 0-68-0, ECR 0-72-0, Renew 4-64-0, Greens 44-0-0, Left 37-0-0, ESN 0-25-1, NI 13-9-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197950` Après le § 2 – Am 1

- **Result:** REJECTED 187-389-5
- **A favour vote means:** For amendment 1 (inserting After § 2). Its words are not in the store.
- **Lobbies:** EPP 5-144-0, S&D 0-94-0, PfE 68-0-0, ECR 69-1-2, Renew 0-68-0, Greens 3-41-0, Left 0-37-0, ESN 25-1-0, NI 17-3-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197951` § 3 – Am 128

- **Result:** REJECTED 186-381-12
- **A favour vote means:** For amendment 128 (amending § 3). Its words are not in the store.
- **Lobbies:** EPP 4-143-2, S&D 91-3-1, PfE 3-65-0, ECR 1-69-1, Renew 2-65-0, Greens 44-0-0, Left 36-1-0, ESN 0-23-2, NI 5-12-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197952` § 3 – Am 91

- **Result:** REJECTED 177-395-9
- **A favour vote means:** For amendment 91 (amending § 3). Its words are not in the store.
- **Lobbies:** EPP 1-145-2, S&D 92-3-1, PfE 0-68-0, ECR 0-71-0, Renew 2-66-0, Greens 43-0-1, Left 37-0-0, ESN 0-26-0, NI 2-16-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197957` Après le § 3 – Am 110

- **Result:** REJECTED 188-388-6
- **A favour vote means:** For amendment 110 (inserting After § 3). Its words are not in the store.
- **Lobbies:** EPP 3-148-0, S&D 89-5-1, PfE 0-68-0, ECR 2-70-0, Renew 5-62-0, Greens 42-0-1, Left 37-0-0, ESN 0-26-0, NI 10-9-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197958` Après le § 4 – Am 92

- **Result:** REJECTED 175-394-13
- **A favour vote means:** For amendment 92 (inserting After § 4). Its words are not in the store.
- **Lobbies:** EPP 1-148-0, S&D 86-4-6, PfE 0-67-0, ECR 0-73-0, Renew 3-65-0, Greens 43-0-1, Left 37-0-0, ESN 0-26-0, NI 5-11-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197959` Après le § 4 – Am 93

- **Result:** REJECTED 178-382-15
- **A favour vote means:** For amendment 93 (inserting After § 4). Its words are not in the store.
- **Lobbies:** EPP 1-146-0, S&D 93-1-1, PfE 0-68-0, ECR 0-71-0, Renew 5-61-0, Greens 43-0-1, Left 35-0-1, ESN 0-25-0, NI 1-10-12
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197961` § 5 – Am 130

- **Result:** REJECTED 173-399-7
- **A favour vote means:** For amendment 130 (amending § 5). Its words are not in the store.
- **Lobbies:** EPP 1-147-2, S&D 91-2-1, PfE 0-68-0, ECR 0-72-0, Renew 3-65-0, Greens 44-0-0, Left 33-0-1, ESN 0-26-0, NI 1-19-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197962` § 5 – Am 94

- **Result:** REJECTED 171-409-3
- **A favour vote means:** For amendment 94 (amending § 5). Its words are not in the store.
- **Lobbies:** EPP 1-148-0, S&D 85-10-0, PfE 0-68-0, ECR 0-73-0, Renew 1-66-1, Greens 43-0-1, Left 37-0-0, ESN 0-26-0, NI 4-18-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197963` § 5

- **Result:** ADOPTED 393-179-10
- **A favour vote means:** For keeping § 5 as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted § 5 (adopted-text numbering assumed equal to the motion (unchecked)): 5. Expresses its deep concern at the strategies of influence, structuring, institutional legitimisation and reconstitution implemented by networks linked to or inspired by the Muslim Brotherhood in several Member States;
- **Lobbies:** EPP 148-1-0, S&D 2-93-0, PfE 66-1-1, ECR 72-0-1, Renew 67-1-0, Greens 0-43-1, Left 1-35-0, ESN 26-0-0, NI 11-5-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted.

### [ ] `MTG-PL-2026-10-08-DEC-197964` § 6 – Am 10

- **Result:** REJECTED 184-384-11
- **A favour vote means:** For amendment 10 (amending § 6). Its words are not in the store.
- **Lobbies:** EPP 11-136-2, S&D 0-94-1, PfE 66-0-0, ECR 70-1-1, Renew 3-63-1, Greens 0-43-1, Left 0-37-0, ESN 24-1-1, NI 10-9-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197967` § 6/2: ce terme

- **Result:** REJECTED 262-309-11
- **A favour vote means:** For keeping the word(s) the previous part's split separated out (the label does not repeat them).
- **Lobbies:** EPP 147-3-0, S&D 4-90-0, PfE 1-67-0, ECR 1-71-1, Renew 66-1-1, Greens 0-42-1, Left 34-3-0, ESN 1-24-1, NI 8-8-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted.

### [ ] `MTG-PL-2026-10-08-DEC-197968` Après le § 6 – Am 2

- **Result:** REJECTED 161-395-26
- **A favour vote means:** For amendment 2 (inserting After § 6). Its words are not in the store.
- **Lobbies:** EPP 7-143-0, S&D 0-95-0, PfE 64-2-2, ECR 44-7-22, Renew 4-64-0, Greens 0-44-0, Left 0-35-0, ESN 26-0-0, NI 16-5-2
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197969` Après le § 6 – Am 11

- **Result:** ADOPTED 334-226-13
- **A favour vote means:** For amendment 11 (inserting After § 6). Its words are not in the store.
- **Lobbies:** EPP 142-3-3, S&D 3-87-5, PfE 66-0-0, ECR 69-0-1, Renew 11-55-1, Greens 1-43-0, Left 0-35-0, ESN 25-0-0, NI 17-3-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197970` Après le § 6 – Am 95

- **Result:** REJECTED 188-392-5
- **A favour vote means:** For amendment 95 (inserting After § 6). Its words are not in the store.
- **Lobbies:** EPP 2-149-0, S&D 93-2-1, PfE 1-67-0, ECR 0-73-0, Renew 5-63-0, Greens 41-1-1, Left 36-1-0, ESN 1-25-0, NI 9-11-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197971` § 7 – Am 96

- **Result:** REJECTED 173-402-4
- **A favour vote means:** For amendment 96 (amending § 7). Its words are not in the store.
- **Lobbies:** EPP 1-147-0, S&D 88-8-0, PfE 0-68-0, ECR 0-73-0, Renew 3-65-0, Greens 41-0-1, Left 37-0-0, ESN 0-25-0, NI 3-16-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197975` Après le § 7 – Am 3

- **Result:** REJECTED 191-381-3
- **A favour vote means:** For amendment 3 (inserting After § 7). Its words are not in the store.
- **Lobbies:** EPP 6-140-2, S&D 0-92-0, PfE 68-0-0, ECR 71-1-0, Renew 2-64-0, Greens 0-44-0, Left 0-36-0, ESN 26-0-0, NI 18-4-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197976` Après le § 7 – Am 18

- **Result:** ADOPTED 416-131-20
- **A favour vote means:** For amendment 18 (inserting After § 7). Its words are not in the store.
- **Lobbies:** EPP 150-0-0, S&D 3-90-0, PfE 68-0-0, ECR 73-0-0, Renew 67-0-0, Greens 4-38-2, Left 8-0-17, ESN 25-0-0, NI 18-3-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197977` § 8 – Am 97

- **Result:** REJECTED 177-390-13
- **A favour vote means:** For amendment 97 (amending § 8). Its words are not in the store.
- **Lobbies:** EPP 1-148-2, S&D 93-2-1, PfE 0-67-0, ECR 1-70-0, Renew 1-67-0, Greens 41-1-1, Left 37-0-0, ESN 0-24-0, NI 3-11-9
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197978` § 9 – Am 112

- **Result:** ADOPTED 320-193-64
- **A favour vote means:** For amendment 112 (amending § 9). Its words are not in the store.
- **Lobbies:** EPP 143-1-5, S&D 0-95-0, PfE 65-2-0, ECR 71-1-0, Renew 5-9-53, Greens 1-43-0, Left 0-36-0, ESN 24-1-0, NI 11-5-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197979` Après le § 9 – Am 39

- **Result:** REJECTED 241-272-68
- **A favour vote means:** For amendment 39 (inserting After § 9). Its words are not in the store.
- **Lobbies:** EPP 148-1-0, S&D 4-91-0, PfE 0-66-0, ECR 8-65-0, Renew 66-2-0, Greens 1-0-43, Left 9-7-21, ESN 0-25-1, NI 5-15-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197980` Après le § 9 – Am 62

- **Result:** REJECTED 257-268-52
- **A favour vote means:** For amendment 62 (inserting After § 9). Its words are not in the store.
- **Lobbies:** EPP 79-22-43, S&D 1-94-0, PfE 68-0-0, ECR 72-1-0, Renew 0-67-1, Greens 0-43-0, Left 0-37-0, ESN 25-1-0, NI 12-3-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197982` Après le § 9 – Am 132/1

- **Result:** REJECTED 245-327-7
- **A favour vote means:** For amendment 132/1 (inserting After § 9). Its words are not in the store.
- **Lobbies:** EPP 1-149-0, S&D 91-3-1, PfE 0-68-0, ECR 0-72-0, Renew 65-1-0, Greens 44-0-0, Left 36-0-0, ESN 0-25-0, NI 8-9-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197983` Après le § 9 – Am 132/2

- **Result:** REJECTED 245-323-11
- **A favour vote means:** For amendment 132/2 (inserting After § 9). Its words are not in the store.
- **Lobbies:** EPP 1-148-1, S&D 94-1-0, PfE 1-67-0, ECR 0-73-0, Renew 65-0-0, Greens 43-0-0, Left 36-0-0, ESN 0-26-0, NI 5-8-10
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197984` Après le § 9 – Am 111

- **Result:** REJECTED 241-329-8
- **A favour vote means:** For amendment 111 (inserting After § 9). Its words are not in the store.
- **Lobbies:** EPP 1-148-0, S&D 94-1-0, PfE 0-67-0, ECR 0-73-0, Renew 58-5-2, Greens 44-0-0, Left 36-0-0, ESN 0-26-0, NI 8-9-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197985` Après le § 10 – Am 98

- **Result:** REJECTED 164-400-21
- **A favour vote means:** For amendment 98 (inserting After § 10). Its words are not in the store.
- **Lobbies:** EPP 0-151-0, S&D 81-2-13, PfE 0-68-0, ECR 0-73-0, Renew 0-66-1, Greens 43-0-1, Left 37-0-0, ESN 0-26-0, NI 3-14-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197986` Après le § 10 – Am 99

- **Result:** REJECTED 166-399-16
- **A favour vote means:** For amendment 99 (inserting After § 10). Its words are not in the store.
- **Lobbies:** EPP 0-149-0, S&D 82-2-11, PfE 0-67-0, ECR 0-73-0, Renew 0-68-0, Greens 43-0-1, Left 37-0-0, ESN 0-25-0, NI 4-15-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197987` Après le § 10 – Am 100

- **Result:** REJECTED 185-389-6
- **A favour vote means:** For amendment 100 (inserting After § 10). Its words are not in the store.
- **Lobbies:** EPP 1-149-0, S&D 92-1-0, PfE 0-68-0, ECR 0-73-0, Renew 1-67-0, Greens 42-0-1, Left 36-0-0, ESN 0-25-1, NI 13-6-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197988` § 11 – Am 101

- **Result:** REJECTED 180-392-13
- **A favour vote means:** For amendment 101 (amending § 11). Its words are not in the store.
- **Lobbies:** EPP 1-150-0, S&D 93-2-1, PfE 0-68-0, ECR 0-73-0, Renew 2-64-1, Greens 43-0-1, Left 37-0-0, ESN 0-26-0, NI 4-9-10
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197989` Après le § 12 – Am 133

- **Result:** REJECTED 215-350-18
- **A favour vote means:** For amendment 133 (inserting After § 12). Its words are not in the store.
- **Lobbies:** EPP 1-150-0, S&D 95-1-0, PfE 0-68-0, ECR 0-72-0, Renew 32-25-9, Greens 44-0-0, Left 37-0-0, ESN 0-25-1, NI 6-9-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197990` § 13 – Am 4

- **Result:** REJECTED 188-389-2
- **A favour vote means:** For amendment 4 (amending § 13). Its words are not in the store.
- **Lobbies:** EPP 12-139-0, S&D 0-95-0, PfE 68-0-0, ECR 68-2-2, Renew 1-66-0, Greens 0-44-0, Left 0-35-0, ESN 26-0-0, NI 13-8-0
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197992` Après le § 13 – Am 20

- **Result:** ADOPTED 403-161-16
- **A favour vote means:** For amendment 20 (inserting After § 13). Its words are not in the store.
- **Lobbies:** EPP 147-1-2, S&D 3-90-0, PfE 68-0-0, ECR 73-0-0, Renew 65-3-0, Greens 1-32-10, Left 1-32-3, ESN 26-0-0, NI 19-3-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197993` Après le § 13 – Am 64

- **Result:** REJECTED 221-349-7
- **A favour vote means:** For amendment 64 (inserting After § 13). Its words are not in the store.
- **Lobbies:** EPP 43-101-5, S&D 0-94-0, PfE 68-0-0, ECR 71-1-0, Renew 1-64-0, Greens 0-44-0, Left 1-36-0, ESN 26-0-0, NI 11-9-2
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197994` Après le § 13 – Am 65

- **Result:** REJECTED 226-343-5
- **A favour vote means:** For amendment 65 (inserting After § 13). Its words are not in the store.
- **Lobbies:** EPP 41-102-1, S&D 0-95-1, PfE 68-0-0, ECR 71-1-0, Renew 4-60-2, Greens 0-44-0, Left 0-37-0, ESN 26-0-0, NI 16-4-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197995` § 14 – Am 5

- **Result:** REJECTED 185-389-7
- **A favour vote means:** For amendment 5 (amending § 14). Its words are not in the store.
- **Lobbies:** EPP 9-141-0, S&D 0-95-0, PfE 68-0-0, ECR 72-1-0, Renew 0-68-0, Greens 0-43-0, Left 0-37-0, ESN 26-0-0, NI 10-4-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197996` Après le § 14 – Am 103

- **Result:** REJECTED 185-386-9
- **A favour vote means:** For amendment 103 (inserting After § 14). Its words are not in the store.
- **Lobbies:** EPP 2-149-0, S&D 90-2-2, PfE 1-67-0, ECR 0-70-0, Renew 5-62-1, Greens 43-0-1, Left 36-0-0, ESN 0-26-0, NI 8-10-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197997` § 15 – Am 104

- **Result:** REJECTED 183-386-13
- **A favour vote means:** For amendment 104 (amending § 15). Its words are not in the store.
- **Lobbies:** EPP 4-147-0, S&D 91-1-1, PfE 0-68-0, ECR 0-73-0, Renew 4-63-1, Greens 43-0-1, Left 37-0-0, ESN 0-26-0, NI 4-8-10
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197998` Après le § 16 – Am 105

- **Result:** REJECTED 176-392-9
- **A favour vote means:** For amendment 105 (inserting After § 16). Its words are not in the store.
- **Lobbies:** EPP 1-148-1, S&D 91-3-0, PfE 0-67-0, ECR 0-73-0, Renew 4-62-0, Greens 41-0-1, Left 37-0-0, ESN 0-25-0, NI 2-14-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197999` Après le § 16 – Am 69

- **Result:** REJECTED 90-463-20
- **A favour vote means:** For amendment 69 (inserting After § 16). Its words are not in the store.
- **Lobbies:** EPP 0-147-0, S&D 2-77-14, PfE 0-67-0, ECR 0-72-0, Renew 0-65-0, Greens 42-1-0, Left 37-0-0, ESN 0-25-1, NI 9-9-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198000` § 19 – Am 135

- **Result:** REJECTED 186-391-4
- **A favour vote means:** For amendment 135 (amending § 19). Its words are not in the store.
- **Lobbies:** EPP 1-149-0, S&D 94-1-0, PfE 0-68-0, ECR 0-72-0, Renew 2-66-0, Greens 43-0-0, Left 35-0-1, ESN 0-26-0, NI 11-9-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198001` Après le § 19 – Am 106

- **Result:** REJECTED 181-388-9
- **A favour vote means:** For amendment 106 (inserting After § 19). Its words are not in the store.
- **Lobbies:** EPP 1-148-0, S&D 91-1-0, PfE 0-68-0, ECR 1-72-0, Renew 4-64-0, Greens 42-0-1, Left 37-0-0, ESN 0-25-0, NI 5-10-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198002` Après le § 19 – Am 134

- **Result:** REJECTED 175-387-12
- **A favour vote means:** For amendment 134 (inserting After § 19). Its words are not in the store.
- **Lobbies:** EPP 2-144-1, S&D 92-2-0, PfE 0-67-0, ECR 0-73-0, Renew 0-63-2, Greens 42-0-1, Left 37-0-0, ESN 0-25-0, NI 2-13-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198006` Après le § 20 – Am 107

- **Result:** REJECTED 181-377-21
- **A favour vote means:** For amendment 107 (inserting After § 20). Its words are not in the store.
- **Lobbies:** EPP 1-150-0, S&D 91-1-1, PfE 0-68-0, ECR 0-69-3, Renew 4-62-1, Greens 41-0-1, Left 37-0-0, ESN 0-15-11, NI 7-12-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198007` § 21 – Am 109

- **Result:** REJECTED 162-405-11
- **A favour vote means:** For amendment 109 (amending § 21). Its words are not in the store.
- **Lobbies:** EPP 1-150-0, S&D 76-7-8, PfE 0-67-0, ECR 0-73-0, Renew 3-64-0, Greens 42-0-1, Left 37-0-0, ESN 0-26-0, NI 3-18-2
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198008` Après le § 21 – Am 66

- **Result:** REJECTED 178-385-15
- **A favour vote means:** For amendment 66 (inserting After § 21). Its words are not in the store.
- **Lobbies:** EPP 10-136-4, S&D 1-93-0, PfE 67-1-0, ECR 66-1-5, Renew 0-66-0, Greens 0-42-0, Left 0-37-0, ESN 24-2-0, NI 10-7-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198009` Après le § 21 – Am 70

- **Result:** REJECTED 56-488-26
- **A favour vote means:** For amendment 70 (inserting After § 21). Its words are not in the store.
- **Lobbies:** EPP 0-148-0, S&D 7-85-1, PfE 1-61-5, ECR 1-72-0, Renew 0-65-0, Greens 2-39-0, Left 37-0-0, ESN 2-10-14, NI 6-8-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198010` Après le § 21 – Am 71

- **Result:** REJECTED 55-492-25
- **A favour vote means:** For amendment 71 (inserting After § 21). Its words are not in the store.
- **Lobbies:** EPP 0-150-0, S&D 7-83-1, PfE 0-61-7, ECR 0-71-0, Renew 0-68-0, Greens 3-38-0, Left 36-0-0, ESN 2-13-11, NI 7-8-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198012` Après le § 21 – Am 108

- **Result:** REJECTED 174-377-24
- **A favour vote means:** For amendment 108 (inserting After § 21). Its words are not in the store.
- **Lobbies:** EPP 1-148-0, S&D 87-4-1, PfE 0-61-5, ECR 1-71-1, Renew 1-66-0, Greens 42-0-1, Left 37-0-0, ESN 0-14-11, NI 5-13-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198013` § 22 – Am 136

- **Result:** REJECTED 178-396-5
- **A favour vote means:** For amendment 136 (amending § 22). Its words are not in the store.
- **Lobbies:** EPP 1-149-0, S&D 90-3-0, PfE 0-68-0, ECR 0-73-0, Renew 4-63-1, Greens 43-0-0, Left 36-0-1, ESN 0-26-0, NI 4-14-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198014` Après le § 22 – Am 6

- **Result:** REJECTED 155-391-29
- **A favour vote means:** For amendment 6 (inserting After § 22). Its words are not in the store.
- **Lobbies:** EPP 0-150-0, S&D 0-92-0, PfE 63-0-5, ECR 49-0-23, Renew 0-67-0, Greens 0-42-0, Left 0-36-0, ESN 26-0-0, NI 17-4-1
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198016` Après le § 24 – Am 7

- **Result:** REJECTED 162-388-23
- **A favour vote means:** For amendment 7 (inserting After § 24). Its words are not in the store.
- **Lobbies:** EPP 2-145-0, S&D 0-92-0, PfE 62-0-5, ECR 54-1-18, Renew 1-66-0, Greens 0-42-0, Left 0-37-0, ESN 26-0-0, NI 17-5-0
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198017` Après le § 24 – Am 67

- **Result:** REJECTED 168-377-16
- **A favour vote means:** For amendment 67 (inserting After § 24). Its words are not in the store.
- **Lobbies:** EPP 6-131-1, S&D 0-92-1, PfE 67-0-0, ECR 71-1-1, Renew 0-65-0, Greens 0-43-0, Left 0-36-0, ESN 14-0-11, NI 10-9-2
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198018` Visa 3 – Am 113

- **Result:** ADOPTED 394-157-25
- **A favour vote means:** For amendment 113 (amending Citation 3). Its words are not in the store.
- **Lobbies:** EPP 143-3-0, S&D 93-0-0, PfE 0-67-0, ECR 1-53-19, Renew 67-1-0, Greens 43-0-0, Left 37-0-0, ESN 0-25-1, NI 10-8-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198019` Après le visa 3 – Am 115

- **Result:** ADOPTED 392-171-11
- **A favour vote means:** For amendment 115 (inserting After citation 3). Its words are not in the store.
- **Lobbies:** EPP 145-2-1, S&D 92-0-0, PfE 0-67-0, ECR 1-69-2, Renew 67-0-0, Greens 43-0-0, Left 36-0-0, ESN 0-25-1, NI 8-8-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198020` Après le visa 3 – Am 114

- **Result:** REJECTED 238-322-12
- **A favour vote means:** For amendment 114 (inserting After citation 3). Its words are not in the store.
- **Lobbies:** EPP 2-144-0, S&D 88-2-0, PfE 0-67-0, ECR 0-73-0, Renew 67-0-1, Greens 43-0-0, Left 36-0-0, ESN 0-26-0, NI 2-10-11
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198021` Après le visa 3 – Am 116

- **Result:** REJECTED 247-322-6
- **A favour vote means:** For amendment 116 (inserting After citation 3). Its words are not in the store.
- **Lobbies:** EPP 2-145-0, S&D 91-2-0, PfE 0-67-0, ECR 0-72-0, Renew 68-0-0, Greens 43-0-0, Left 36-0-0, ESN 0-26-0, NI 7-10-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198022` Après le considérant A – Am 117

- **Result:** REJECTED 260-283-31
- **A favour vote means:** For amendment 117 (inserting After recital A). Its words are not in the store.
- **Lobbies:** EPP 6-139-0, S&D 91-2-0, PfE 0-67-0, ECR 4-45-23, Renew 67-0-1, Greens 43-0-0, Left 37-0-0, ESN 0-24-2, NI 12-6-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198023` Après le considérant A – Am 118

- **Result:** REJECTED 254-302-12
- **A favour vote means:** For amendment 118 (inserting After recital A). Its words are not in the store.
- **Lobbies:** EPP 6-134-2, S&D 88-2-0, PfE 0-67-0, ECR 4-68-1, Renew 68-0-0, Greens 42-0-0, Left 37-0-0, ESN 0-25-1, NI 9-6-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198024` Après le considérant B – Am 119

- **Result:** REJECTED 246-320-8
- **A favour vote means:** For amendment 119 (inserting After recital B). Its words are not in the store.
- **Lobbies:** EPP 1-145-0, S&D 91-2-0, PfE 0-67-0, ECR 0-73-0, Renew 67-0-0, Greens 42-0-0, Left 37-0-0, ESN 0-25-1, NI 8-8-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198025` Après le considérant B – Am 120

- **Result:** REJECTED 242-320-10
- **A favour vote means:** For amendment 120 (inserting After recital B). Its words are not in the store.
- **Lobbies:** EPP 5-141-1, S&D 89-2-0, PfE 0-67-0, ECR 0-73-0, Renew 63-0-2, Greens 43-0-0, Left 37-0-0, ESN 0-26-0, NI 5-11-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198026` Après le considérant B – Am 122

- **Result:** REJECTED 244-323-7
- **A favour vote means:** For amendment 122 (inserting After recital B). Its words are not in the store.
- **Lobbies:** EPP 3-144-0, S&D 90-2-0, PfE 0-67-0, ECR 0-73-0, Renew 64-0-2, Greens 43-0-0, Left 37-0-0, ESN 0-26-0, NI 7-11-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198027` Après le considérant B – Am 123

- **Result:** REJECTED 243-318-10
- **A favour vote means:** For amendment 123 (inserting After recital B). Its words are not in the store.
- **Lobbies:** EPP 2-144-0, S&D 89-2-0, PfE 0-67-0, ECR 0-72-0, Renew 65-0-3, Greens 43-0-0, Left 36-0-0, ESN 0-25-0, NI 8-8-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198028` Considérant C – Am 22

- **Result:** ADOPTED 297-258-12
- **A favour vote means:** For amendment 22 (amending recital C). Its words are not in the store.
- **Lobbies:** EPP 140-2-2, S&D 5-87-0, PfE 0-67-0, ECR 0-72-1, Renew 65-0-0, Greens 42-0-0, Left 37-0-0, ESN 0-24-1, NI 8-6-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198030` Après le considérant D – Am 81

- **Result:** REJECTED 165-392-12
- **A favour vote means:** For amendment 81 (inserting After recital D). Its words are not in the store.
- **Lobbies:** EPP 1-145-0, S&D 80-3-7, PfE 0-67-0, ECR 0-71-0, Renew 2-66-0, Greens 42-0-1, Left 37-0-0, ESN 0-25-0, NI 3-15-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198031` Considérant E – Am 82

- **Result:** REJECTED 90-469-10
- **A favour vote means:** For amendment 82 (amending recital E). Its words are not in the store.
- **Lobbies:** EPP 1-141-1, S&D 2-90-0, PfE 0-67-0, ECR 0-72-0, Renew 4-64-0, Greens 42-0-1, Left 37-0-0, ESN 0-25-0, NI 4-10-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198032` Considérant E – Am 52

- **Result:** ADOPTED 295-243-30
- **A favour vote means:** For amendment 52 (amending recital E). Its words are not in the store.
- **Lobbies:** EPP 127-1-18, S&D 1-89-0, PfE 65-2-0, ECR 68-2-3, Renew 1-67-0, Greens 1-41-0, Left 0-37-0, ESN 21-1-3, NI 11-3-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198034` Après le considérant E – Am 53

- **Result:** REJECTED 185-370-10
- **A favour vote means:** For amendment 53 (inserting After recital E). Its words are not in the store.
- **Lobbies:** EPP 10-127-3, S&D 0-91-0, PfE 66-0-0, ECR 69-2-2, Renew 1-66-0, Greens 0-43-0, Left 0-37-0, ESN 25-0-0, NI 14-4-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198035` Considérant F – Am 83

- **Result:** REJECTED 173-387-9
- **A favour vote means:** For amendment 83 (amending recital F). Its words are not in the store.
- **Lobbies:** EPP 0-145-0, S&D 87-3-1, PfE 0-67-0, ECR 0-73-0, Renew 3-64-0, Greens 41-0-1, Left 36-0-0, ESN 0-25-0, NI 6-10-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198036` Après le considérant G – Am 9

- **Result:** ADOPTED 329-181-59
- **A favour vote means:** For amendment 9 (inserting After recital G). Its words are not in the store.
- **Lobbies:** EPP 141-2-3, S&D 1-88-0, PfE 67-0-0, ECR 72-0-0, Renew 6-11-51, Greens 2-40-1, Left 0-36-1, ESN 26-0-0, NI 14-4-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198037` Considérant H

- **Result:** ADOPTED 385-169-11
- **A favour vote means:** For keeping Considérant H as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital H (adopted-text numbering assumed equal to the motion (unchecked)): H. whereas the Muslim Brotherhood constitutes the archetype of these transnational Islamist networks; whereas its method relies more on relays, associated structures, slogans, alliances and bodies of evidence than on visible formal membership; whereas this movement carries a political project based on the primacy of religious norms over common law, which is incompatible with democratic principles, the rule of law and equality between citizens;
- **Lobbies:** EPP 146-1-0, S&D 2-89-0, PfE 66-0-0, ECR 72-0-0, Renew 61-3-2, Greens 0-42-1, Left 0-30-1, ESN 26-0-0, NI 12-4-7
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted.

### [ ] `MTG-PL-2026-10-08-DEC-198038` Considérant J – Am 85

- **Result:** REJECTED 172-398-5
- **A favour vote means:** For amendment 85 (amending recital J). Its words are not in the store.
- **Lobbies:** EPP 0-147-0, S&D 86-5-1, PfE 0-67-0, ECR 0-73-0, Renew 4-64-0, Greens 42-0-1, Left 37-0-0, ESN 0-26-0, NI 3-16-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198039` Après le considérant J – Am 54

- **Result:** REJECTED 184-373-11
- **A favour vote means:** For amendment 54 (inserting After recital J). Its words are not in the store.
- **Lobbies:** EPP 9-132-0, S&D 1-90-0, PfE 67-0-0, ECR 69-1-3, Renew 0-64-3, Greens 0-43-0, Left 0-37-0, ESN 26-0-0, NI 12-6-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198040` Considérant K – Am 86

- **Result:** REJECTED 178-388-3
- **A favour vote means:** For amendment 86 (amending recital K). Its words are not in the store.
- **Lobbies:** EPP 0-145-0, S&D 89-2-0, PfE 0-67-0, ECR 0-72-0, Renew 5-62-0, Greens 42-0-1, Left 37-0-0, ESN 0-26-0, NI 5-14-2
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198041` Considérant K – Am 124

- **Result:** REJECTED 180-379-11
- **A favour vote means:** For amendment 124 (amending recital K). Its words are not in the store.
- **Lobbies:** EPP 1-146-0, S&D 88-2-0, PfE 0-67-0, ECR 1-72-0, Renew 7-58-2, Greens 43-0-0, Left 37-0-0, ESN 0-25-0, NI 3-9-9
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198042` Considérant K

- **Result:** ADOPTED 393-168-6
- **A favour vote means:** For keeping Considérant K as drafted (a separate vote on that paragraph or recital).
- **Text:** Adopted recital K (adopted-text numbering assumed equal to the motion (unchecked)): K. whereas the search for institutional respectability constitutes a central lever for these networks; whereas an invitation to a European institution, participation in a consultation, a mention in a report, a partnership with an agency or access to an EU programme may constitute a form of political label;
- **Lobbies:** EPP 142-3-0, S&D 3-87-0, PfE 65-0-0, ECR 73-0-0, Renew 68-0-0, Greens 2-40-1, Left 0-35-1, ESN 26-0-0, NI 14-3-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted.

### [ ] `MTG-PL-2026-10-08-DEC-198043` Considérant L – Am 87

- **Result:** REJECTED 178-385-8
- **A favour vote means:** For amendment 87 (amending recital L). Its words are not in the store.
- **Lobbies:** EPP 1-145-0, S&D 88-2-1, PfE 0-67-0, ECR 2-71-0, Renew 6-62-0, Greens 42-0-1, Left 35-0-0, ESN 0-26-0, NI 4-12-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198044` Après le considérant L – Am 27

- **Result:** ADOPTED 385-174-11
- **A favour vote means:** For amendment 27 (inserting After recital L). Its words are not in the store.
- **Lobbies:** EPP 143-3-0, S&D 2-88-0, PfE 67-0-0, ECR 70-1-1, Renew 66-0-1, Greens 0-42-1, Left 0-37-0, ESN 26-0-0, NI 11-3-8
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198045` Après le considérant M – Am 55

- **Result:** ADOPTED 273-256-32
- **A favour vote means:** For amendment 55 (inserting After recital M). Its words are not in the store.
- **Lobbies:** EPP 94-16-29, S&D 1-90-0, PfE 67-0-0, ECR 72-0-0, Renew 0-68-0, Greens 0-43-0, Left 0-36-0, ESN 24-0-0, NI 15-3-3
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198046` Après le considérant M – Am 56

- **Result:** REJECTED 191-362-6
- **A favour vote means:** For amendment 56 (inserting After recital M). Its words are not in the store.
- **Lobbies:** EPP 13-127-0, S&D 1-89-0, PfE 66-0-0, ECR 72-1-0, Renew 0-65-2, Greens 0-42-0, Left 0-35-0, ESN 26-0-0, NI 13-3-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198047` Après le considérant M – Am 68

- **Result:** ADOPTED 318-247-5
- **A favour vote means:** For amendment 68 (inserting After recital M). Its words are not in the store.
- **Lobbies:** EPP 144-1-0, S&D 0-91-0, PfE 66-1-0, ECR 73-0-0, Renew 0-68-0, Greens 0-42-0, Left 0-36-1, ESN 26-0-0, NI 9-8-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198048` Après le considérant N – Am 125

- **Result:** REJECTED 238-314-19
- **A favour vote means:** For amendment 125 (inserting After recital N). Its words are not in the store.
- **Lobbies:** EPP 2-143-1, S&D 87-2-0, PfE 0-67-0, ECR 0-73-0, Renew 67-1-0, Greens 43-0-0, Left 36-1-0, ESN 1-11-14, NI 2-16-4
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198049` Après le considérant N – Am 126

- **Result:** REJECTED 243-320-8
- **A favour vote means:** For amendment 126 (inserting After recital N). Its words are not in the store.
- **Lobbies:** EPP 1-144-0, S&D 89-2-0, PfE 0-67-0, ECR 0-72-0, Renew 66-2-0, Greens 42-0-1, Left 37-0-0, ESN 0-24-2, NI 8-9-5
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198050` Après le considérant S – Am 28

- **Result:** ADOPTED 428-86-46
- **A favour vote means:** For amendment 28 (inserting After recital S). Its words are not in the store.
- **Lobbies:** EPP 145-2-0, S&D 3-83-2, PfE 67-0-0, ECR 69-0-1, Renew 66-0-0, Greens 37-0-5, Left 3-0-32, ESN 25-0-0, NI 13-1-6
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-198051` Proposition de résolution (ensemble du texte)

- **Result:** ADOPTED 381-167-15
- **A favour vote means:** For adopting the text as a whole.
- **Lobbies:** EPP 143-1-0, S&D 2-84-1, PfE 67-0-0, ECR 72-0-0, Renew 62-3-2, Greens 1-40-1, Left 1-35-0, ESN 25-0-1, NI 8-4-10
- **Proposed:** no direction -- A resolution against Islamist entryism and the Muslim Brotherhood: an EU list of 'hate preachers' (§ 16), legal and funding consequences for promoting Islamist ideologies (§ 17), a 'methodology to identify signs of Islamist entryism' including 'the production of activist reports' (§ 6), denial of access and Transparency Register removal for FEMYSO and similar bodies (§ 12), support for national face-covering bans (§ 8). As amended (Am 31), § 1 also condemns 'religious ... entryism' as spearheading efforts to roll back 'sexual health and reproductive rights, LGBTIQ+ rights': language that can be turned on any faith-based group. Free speech and freedom of religion (areas 7 and 8) pull both way
- **Flag for you:** Your call, and it sets the direction for its 101 other roll calls. EPP 143-1, Patriots 67-0, ECR 72-0, ESN 25-0, Renew 62-3 for; S&D 2-84, Greens 1-40, The Left 1-35 against.

### [ ] `MTG-PL-2026-10-08-DEC-198173` § 3 – Am 32/1

- **Result:** REJECTED 204-357-19
- **A favour vote means:** For amendment 32/1 (amending § 3). Its words are not in the store.
- **Lobbies:** EPP 1-148-2, S&D 94-1-1, PfE 0-68-0, ECR 5-66-1, Renew 67-0-1, Greens 9-34-0, Left 24-8-1, ESN 0-24-2, NI 4-8-11
- **Proposed:** no direction -- Every roll call in this family follows the direction you give the whole text (198051), which is undrafted. The amendment's words are not in the store.

### [ ] `MTG-PL-2026-10-08-DEC-197692` item not named in the label

- **Result:** REJECTED 81-479-21
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-08-DEC-197694` item not named in the label

- **Result:** REJECTED 228-330-19
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-08-DEC-197699` item not named in the label

- **Result:** REJECTED 91-475-10
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-08-DEC-197754` item not named in the label

- **Result:** REJECTED 249-292-18
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-08-DEC-197778` item not named in the label

- **Result:** REJECTED 273-282-13
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-08-DEC-197956` Après le § 3 – Am 33

- **Result:** ADOPTED 501-29-49
- **A favour vote means:** For amendment 33 (inserting After § 3). Its words are not in the store.
- **Lobbies:** EPP 149-0-0, S&D 84-0-10, PfE 58-0-10, ECR 63-3-6, Renew 67-0-0, Greens 44-0-0, Left 7-13-17, ESN 19-5-1, NI 10-8-5
- **Proposed:** evidence only, never places -- Near-unanimous (501-29): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

### [ ] `MTG-PL-2026-10-08-DEC-197974` item not named in the label

- **Result:** ADOPTED 335-240-3
- **A favour vote means:** Not stated: the stored label names only the report, not the item put to the vote.
- **Lobbies:** no name lists (electronic vote)
- **Proposed:** evidence only, never places -- An electronic vote with no name lists: no MEP's position was recorded, so it can place nobody.

### [ ] `MTG-PL-2026-10-08-DEC-198011` Après le § 21 – Am 72

- **Result:** REJECTED 47-503-24
- **A favour vote means:** For amendment 72 (inserting After § 21). Its words are not in the store.
- **Lobbies:** EPP 0-149-0, S&D 1-92-0, PfE 0-62-5, ECR 0-73-0, Renew 0-68-0, Greens 3-38-0, Left 36-0-0, ESN 2-13-11, NI 5-8-8
- **Proposed:** evidence only, never places -- Near-unanimous (47-503): the losing side is under a tenth of the votes cast, so it tells almost no MEP apart (the meaning-line queue's consensus floor).

406 divisions.
