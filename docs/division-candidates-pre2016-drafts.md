# Pre-2016 Commons divisions - draft recommendations

*Drafted 29 September 2026 for Christopher's sign-off, from the Hansard record of each division: the question put, the amendment or clause text, its mover, and the mover's own vote as the direction check. **Nothing here is applied.** Every entry is `signed_off: false`; `config/vote_tracker.yaml` is untouched.*

| | Count |
|---|---|
| Recommend including (from the 74) | 11 |
| Also recommended for the tracker: already ledgered by title | 7 |
| Your check needed | 8 (6 from the 74, 2 already ledgered) |
| Recommend excluding | 57 |

**Direction check.** In every recommended division moved by a member, the mover voted in their own lobby (Aye), so the question is theirs and the reading of Aye is theirs.

**How to sign off.** For each entry you accept, correct the wording if needed, set `signed_off: true`, and paste it under `divisions:` in `config/vote_tracker.yaml` (new issues under `issues:`). The next tracker build records the voters (`div:h<id>`) and the signed stance outranks the model's.

## Proposed new issues

```yaml
  - id: abortion-counselling-2011
    name: Independent abortion counselling (2011)
    area: 1
    bill: Health and Social Care Bill - Amendment 1
  - id: sex-selective-abortion-2015
    name: Sex-selective abortion
    area: 1
    bill: Serious Crime Bill - New Clause 1; Abortion (Sex-Selection) Bill
  - id: assisted-dying-2015
    name: Assisted suicide (the 2015 Bill)
    area: 2
    bill: Assisted Dying (No. 2) Bill
  - id: same-sex-marriage-2013
    name: Redefining marriage (2013)
    area: 9
    bill: Marriage (Same Sex Couples) Bill
  - id: marriage-tax-2011-14
    name: Recognising marriage in the tax system
    area: 9
    bill: Finance Bills 2011 and 2014
  - id: third-party-campaigning-2013
    name: Restrictions on campaigning groups (2013)
    area: 7
    bill: Transparency of Lobbying, Non-Party Campaigning and Trade Union Administration Bill
```

Existing issue used: `parental-rights` (area 6).

## Recommended: from the review queue (11)

### h2002 - Independent abortion counselling - Amendment 1221
- 2011-09-07, 118-368. Question put: That the amendment be made. Moved by Nadine Dorries (voted Aye in the division). [Hansard](https://hansard.parliament.uk/Commons/2011-09-07/debates/11090754000002/)

```yaml
  - id: 2002
    source: hansard
    hansard_ext: "11090754001456"
    issue: abortion-counselling-2011
    stage: Report stage
    stage_group: Report stage
    landmark: true
    signed_off: false
    our_side: "aye"
    short: "Independent abortion counselling - Amendment 1221"
    context: >-
      Nadine Dorries moved amendment 1221 to the Health and Social Care Bill, debated with her amendment 1: local authorities must offer women requesting a termination independent information, advice and counselling, independent meaning from a body that does not itself refer for, provide or profit from abortions, or a statutory body. Defeated 118 to 368.
    meaning_aye: >-
      Supported Nadine Dorries's amendment: women requesting an abortion should be offered counselling from a provider with no stake in abortion.
    meaning_no: >-
      Voted against offering women requesting an abortion independent counselling.
```

### h1970 - Recognising marriage in the tax system - Edward Leigh's new clause
- 2011-06-28, 23-473. Question put: That the clause be read a Second time. Moved by Mr Leigh (Edward Leigh voted Aye). [Hansard](https://hansard.parliament.uk/Commons/2011-06-28/debates/11062856000002/)

```yaml
  - id: 1970
    source: hansard
    hansard_ext: "1106297000623"
    issue: marriage-tax-2011-14
    stage: Report stage
    stage_group: Report stage
    landmark: false
    signed_off: false
    our_side: "aye"
    short: "Recognising marriage in the tax system - Edward Leigh's new clause"
    context: >-
      Edward Leigh moved a new clause to the Finance Bill to recognise marriage in the tax system, citing the Prime Minister's own commitments. Defeated 23 to 473.
    meaning_aye: >-
      Supported Edward Leigh's new clause to recognise marriage in the tax system.
    meaning_no: >-
      Voted against Edward Leigh's new clause to recognise marriage in the tax system.
```

### h1306 - Marriage tax allowance - clause 11 stand part
- 2014-04-09, 279-214. Question put: That the clause stand part of the Bill. Moved by - (a Government clause; no mover named for the stand part question). [Hansard](https://hansard.parliament.uk/Commons/2014-04-09/debates/14040933000002/)

```yaml
  - id: 1306
    source: hansard
    hansard_ext: "14040952002773"
    issue: marriage-tax-2011-14
    stage: Committee (whole House)
    stage_group: Committee (whole House)
    landmark: true
    signed_off: false
    our_side: "aye"
    short: "Marriage tax allowance - clause 11 stand part"
    context: >-
      Clause 11 of the Finance (No. 2) Bill introduced a transferable tax allowance for married couples and civil partners. The House agreed that it stand part of the Bill, 279 to 214.
    meaning_aye: >-
      Voted to keep the transferable tax allowance for married couples in the Bill.
    meaning_no: >-
      Voted to remove the married couples' tax allowance from the Bill.
```

### h20439 - Children, Schools and Families Bill 2010 - Second Reading
- 2010-01-11, 287-206. Question put: That the Bill be now read a Second time. Moved by - (Ed Balls, the Secretary of State, voted Aye). [Hansard](https://hansard.parliament.uk/Commons/2010-01-11/debates/1001119000001/)

```yaml
  - id: 20439
    source: hansard
    hansard_ext: "1001126000505"
    issue: parental-rights
    stage: Second Reading
    stage_group: Second Reading
    landmark: true
    signed_off: false
    our_side: "no"
    short: "Children, Schools and Families Bill 2010 - Second Reading"
    context: >-
      The debate centred on the Bill's home-education provisions and its plan for compulsory personal, social, health and economic education, including sex and relationships education. Carried 287 to 206.
    meaning_aye: >-
      Supported the Bill at Second Reading, with its home-education powers and compulsory PSHE including sex and relationships education.
    meaning_no: >-
      Voted against the Bill at Second Reading.
```

### h20438 - Children, Schools and Families Bill 2010 - reasoned amendment
- 2010-01-11, 211-288. Question put: That the amendment be made. Moved by Mr. David Laws (Yeovil) (LD) (voted Aye in the division). [Hansard](https://hansard.parliament.uk/Commons/2010-01-11/debates/1001119000001/)

```yaml
  - id: 20438
    source: hansard
    hansard_ext: "1001125000546"
    issue: parental-rights
    stage: Second Reading
    stage_group: Second Reading
    landmark: false
    signed_off: false
    our_side: "aye"
    short: "Children, Schools and Families Bill 2010 - reasoned amendment"
    context: >-
      David Laws moved a reasoned amendment declining a Second Reading, citing among other reasons that the Bill's home-education powers were excessive and risked undermining home educators' freedoms. Defeated 211 to 288.
    meaning_aye: >-
      Supported declining the Bill a Second Reading, including because its home-education powers were excessive.
    meaning_no: >-
      Voted against the reasoned amendment, allowing the Bill to proceed.
```

### h20599 - Children, Schools and Families Bill 2010 - Third Reading
- 2010-02-23, 268-177. Question put: That the Bill be now read the Third time. Moved by Mr. Coaker (Vernon Coaker, the minister moving it, voted Aye). [Hansard](https://hansard.parliament.uk/Commons/2010-02-23/debates/10022358000002/)

```yaml
  - id: 20599
    source: hansard
    hansard_ext: "1002244001717"
    issue: parental-rights
    stage: Third Reading
    stage_group: Third Reading
    landmark: true
    signed_off: false
    our_side: "no"
    short: "Children, Schools and Families Bill 2010 - Third Reading"
    context: >-
      Third Reading of the Bill carrying home-education powers and compulsory PSHE including sex and relationships education. Carried 268 to 177.
    meaning_aye: >-
      Supported the Bill at Third Reading.
    meaning_no: >-
      Voted against the Bill at Third Reading.
```

### h1097 - Statutory PSHE - Lisa Nandy's New Clause 20
- 2013-06-11, 219-303. Question put: That the clause be read a Second time. Moved by Lisa Nandy (voted Aye in the division). [Hansard](https://hansard.parliament.uk/Commons/2013-06-11/debates/13061171000001/)

```yaml
  - id: 1097
    source: hansard
    hansard_ext: "13061192001460"
    issue: parental-rights
    stage: Report stage
    stage_group: Report stage
    landmark: false
    signed_off: false
    our_side: "no"
    short: "Statutory PSHE - Lisa Nandy's New Clause 20"
    context: >-
      Lisa Nandy moved new clause 20 to the Children and Families Bill, making personal, social and health education a statutory foundation subject in maintained schools. Defeated 219 to 303.
    meaning_aye: >-
      Supported making personal, social and health education a compulsory subject in maintained schools.
    meaning_no: >-
      Voted against making PSHE a compulsory subject, leaving it to schools.
```

### h1491 - Sex-selective abortion - New Clause 1
- 2015-02-23, 201-292. Question put: That the clause be read a Second time. Moved by Fiona Bruce (Congleton) (Con) (voted Aye in the division). [Hansard](https://hansard.parliament.uk/Commons/2015-02-23/debates/15022317000001/)

```yaml
  - id: 1491
    source: hansard
    hansard_ext: "1502243002124"
    issue: sex-selective-abortion-2015
    stage: Report stage
    stage_group: Report stage
    landmark: true
    signed_off: false
    our_side: "aye"
    short: "Sex-selective abortion - New Clause 1"
    context: >-
      Fiona Bruce moved new clause 1 to the Serious Crime Bill, to make explicit that terminating a pregnancy on the grounds of the sex of the unborn child is illegal. Defeated 201 to 292.
    meaning_aye: >-
      Supported Fiona Bruce's new clause stating plainly in law that abortion on the grounds of the baby's sex is illegal.
    meaning_no: >-
      Voted against stating plainly in law that sex-selective abortion is illegal.
```

### h1144 - Lobbying Bill 2013 - Second Reading
- 2013-09-03, 309-247. Question put: That the Bill be now read a Second time. Moved by - (Andrew Lansley voted Aye). [Hansard](https://hansard.parliament.uk/Commons/2013-09-03/debates/13090336000002/)

```yaml
  - id: 1144
    source: hansard
    hansard_ext: "13090354001864"
    issue: third-party-campaigning-2013
    stage: Second Reading
    stage_group: Second Reading
    landmark: true
    signed_off: false
    our_side: "no"
    short: "Lobbying Bill 2013 - Second Reading"
    context: >-
      The Transparency of Lobbying, Non-Party Campaigning and Trade Union Administration Bill, which tightened the rules on campaigning by charities and other non-party organisations before elections. Carried 309 to 247.
    meaning_aye: >-
      Supported the Bill that restricted non-party campaigning before elections.
    meaning_no: >-
      Voted against the Bill.
```

### h2194 - Lobbying Bill 2013 - Third Reading
- 2013-10-09, 304-260. Question put: That the Bill be now read the Third time. Moved by Mr Lansley (Andrew Lansley, moving it, voted Aye). [Hansard](https://hansard.parliament.uk/Commons/2013-10-09/debates/13100960000002/)

```yaml
  - id: 2194
    source: hansard
    hansard_ext: "13100979000726"
    issue: third-party-campaigning-2013
    stage: Third Reading
    stage_group: Third Reading
    landmark: true
    signed_off: false
    our_side: "no"
    short: "Lobbying Bill 2013 - Third Reading"
    context: >-
      Third Reading of the Bill tightening the rules on non-party campaigning before elections. Carried 304 to 260.
    meaning_aye: >-
      Supported the Bill at Third Reading.
    meaning_no: >-
      Voted against the Bill at Third Reading.
```

### h2193 - Third-party spending limits - leave out clause 27
- 2013-10-09, 261-312. Question put: That the amendment be made. Moved by Mr Allen (Graham Allen voted Aye). [Hansard](https://hansard.parliament.uk/Commons/2013-10-09/debates/13100960000002/)

```yaml
  - id: 2193
    source: hansard
    hansard_ext: "13100960002025"
    issue: third-party-campaigning-2013
    stage: Report stage
    stage_group: Report stage
    landmark: false
    signed_off: false
    our_side: "aye"
    short: "Third-party spending limits - leave out clause 27"
    context: >-
      Graham Allen moved amendment 102 to leave out clause 27, which lowered the spending limits for non-party campaigners at UK parliamentary elections. Defeated 261 to 312.
    meaning_aye: >-
      Supported removing the clause that cut the spending limits for charities and other non-party campaigners.
    meaning_no: >-
      Voted to keep the lower spending limits on non-party campaigners.
```

## Recommended: already in the ledger, proposed for the tracker too (7)

Recorded automatically by title on 29 September; adding them here puts them on the public tracker with a signed verdict.

### h1591 - Assisted Dying (No. 2) Bill - Second Reading
- 2015-09-11, 118-330. Question put: That the Bill be now read a Second time. Moved by Rob Marris (Wolverhampton South West) (Lab). [Hansard](https://hansard.parliament.uk/Commons/2015-09-11/debates/15091126000003/)

```yaml
  - id: 1591
    source: hansard
    hansard_ext: "15091126001423"
    issue: assisted-dying-2015
    stage: Second Reading
    stage_group: Second Reading
    landmark: true
    signed_off: false
    our_side: "no"
    short: "Assisted Dying (No. 2) Bill - Second Reading"
    context: >-
      Rob Marris's Private Member's Bill to legalise assisted suicide for terminally ill adults. Defeated 118 to 330 on a free vote.
    meaning_aye: >-
      Supported the Bill at Second Reading (in favour of legalising assisted suicide).
    meaning_no: >-
      Voted to stop the Bill at Second Reading.
```

### h1015 - Marriage (Same Sex Couples) Bill - Second Reading
- 2013-02-05, 400-175. Question put: That the Bill be now read a Second time. Moved by The Minister for Women and Equalities (Maria Miller). [Hansard](https://hansard.parliament.uk/Commons/2013-02-05/debates/13020551000002/)

```yaml
  - id: 1015
    source: hansard
    hansard_ext: "13020569002422"
    issue: same-sex-marriage-2013
    stage: Second Reading
    stage_group: Second Reading
    landmark: true
    signed_off: false
    our_side: "no"
    short: "Marriage (Same Sex Couples) Bill - Second Reading"
    context: >-
      The Government Bill to redefine marriage in England and Wales to include same-sex couples, moved by Maria Miller. Carried 400 to 175 on a free vote.
    meaning_aye: >-
      Supported redefining marriage to include same-sex couples.
    meaning_no: >-
      Voted against the Bill at Second Reading.
```

### h2184 - Registrars' conscientious objection - New Clause 3
- 2013-05-20, 150-340. Question put: That the clause be read a Second time. Moved by Mr Burrowes. [Hansard](https://hansard.parliament.uk/Commons/2013-05-20/debates/13052013000002/)

```yaml
  - id: 2184
    source: hansard
    hansard_ext: "13052045001031"
    issue: same-sex-marriage-2013
    stage: Report stage
    stage_group: Report stage
    landmark: false
    signed_off: false
    our_side: "aye"
    short: "Registrars' conscientious objection - New Clause 3"
    context: >-
      David Burrowes moved new clause 3: no registrar in post when the Act came into force could be required to conduct a same-sex marriage to which they had a sincerely held religious or belief objection. Defeated 150 to 340.
    meaning_aye: >-
      Supported protecting serving registrars who object in conscience from having to conduct same-sex marriages.
    meaning_no: >-
      Voted against conscience protection for serving registrars.
```

### h2185 - Belief in traditional marriage protected - New Clause 6
- 2013-05-20, 148-339. Question put: That the clause be read a Second time. Moved by Mr Burrowes. [Hansard](https://hansard.parliament.uk/Commons/2013-05-20/debates/13052013000002/)

```yaml
  - id: 2185
    source: hansard
    hansard_ext: "13052045001032"
    issue: same-sex-marriage-2013
    stage: Report stage
    stage_group: Report stage
    landmark: false
    signed_off: false
    our_side: "aye"
    short: "Belief in traditional marriage protected - New Clause 6"
    context: >-
      David Burrowes moved new clause 6, adding to the Equality Act 2010 that the protected characteristic of religion or belief may include the belief that marriage is between a man and a woman. Defeated 148 to 339.
    meaning_aye: >-
      Supported protecting in equality law the belief that marriage is between a man and a woman.
    meaning_no: >-
      Voted against protecting that belief in equality law.
```

### h2186 - Protection from compulsion - New Clause 8
- 2013-05-20, 163-321. Question put: That the clause be read a Second time. Moved by Mr Burrowes. [Hansard](https://hansard.parliament.uk/Commons/2013-05-20/debates/13052013000002/)

```yaml
  - id: 2186
    source: hansard
    hansard_ext: "13052052000554"
    issue: same-sex-marriage-2013
    stage: Report stage
    stage_group: Report stage
    landmark: false
    signed_off: false
    our_side: "aye"
    short: "Protection from compulsion - New Clause 8"
    context: >-
      David Burrowes moved new clause 8, defining 'compelled' to include less favourable treatment by a public authority, penalties and legal proceedings, so the Bill's protections against being compelled to take part in same-sex marriages were wider. Defeated 163 to 321.
    meaning_aye: >-
      Supported wider protection from being penalised for declining to take part in same-sex marriages.
    meaning_no: >-
      Voted against widening that protection.
```

### h2189 - Marriage (Same Sex Couples) Bill - Third Reading
- 2013-05-21, 366-161. Question put: That the Bill be now read the Third time. Moved by Maria Miller. [Hansard](https://hansard.parliament.uk/Commons/2013-05-21/debates/13052156000001/)

```yaml
  - id: 2189
    source: hansard
    hansard_ext: "13052186000682"
    issue: same-sex-marriage-2013
    stage: Third Reading
    stage_group: Third Reading
    landmark: true
    signed_off: false
    our_side: "no"
    short: "Marriage (Same Sex Couples) Bill - Third Reading"
    context: >-
      Third Reading of the Bill redefining marriage. Carried 366 to 161.
    meaning_aye: >-
      Supported the Bill at Third Reading.
    meaning_no: >-
      Voted against the Bill at Third Reading.
```

### h1403 - Abortion (Sex-Selection) Bill 2014 - leave to bring in
- 2014-11-04, 181-1. Question put: That leave be given to bring in a Bill to clarify the law relating to abortion on the basis of sex-selection; and for connected purposes. Moved by Fiona Bruce (Congleton) (Con). [Hansard](https://hansard.parliament.uk/Commons/2014-11-04/debates/14110444000001/)

```yaml
  - id: 1403
    source: hansard
    hansard_ext: "14110444000290"
    issue: sex-selective-abortion-2015
    stage: Ten Minute Rule
    stage_group: Ten Minute Rule
    landmark: false
    signed_off: false
    our_side: "aye"
    short: "Abortion (Sex-Selection) Bill 2014 - leave to bring in"
    context: >-
      Fiona Bruce's ten minute rule motion for leave to bring in a Bill to clarify the law on sex-selective abortion. Agreed 181 to 1.
    meaning_aye: >-
      Supported leave to bring in a Bill clarifying that sex-selective abortion is illegal.
    meaning_no: >-
      Voted against leave to bring in the Bill.
```

## Your check needed (8)

- **h20596** 2010-02-23 - Children, Schools and Families Bill. Tim Loughton's new clause 1 to the Children, Schools and Families Bill (172-277). Grouped with new clause 10 (reasonable punishment); the record here does not give new clause 1's text. [Hansard](https://hansard.parliament.uk/Commons/2010-02-23/debates/10022358000002/)
- **h1911** 2011-03-31 - Police Reform and Social Responsibility Bill. John McDonnell's amendment on the Parliament Square protest powers (8-280). Protest freedom, not our core free-speech ground; optional. [Hansard](https://hansard.parliament.uk/Commons/2011-03-31/debates/11033156000002/)
- **h1912** 2011-03-31 - Police Reform and Social Responsibility Bill. John McDonnell's amendment 185 on the Parliament Square powers (158-276). As above; optional. [Hansard](https://hansard.parliament.uk/Commons/2011-03-31/debates/11033156000002/)
- **h2187** 2013-05-20 - Marriage (Same Sex Couples) Bill. Marriage (Same Sex Couples) Bill, 20 May 2013 (391-57): a Government new clause moved by Maria Miller; the record here does not name it. [Hansard](https://hansard.parliament.uk/Commons/2013-05-20/debates/13052013000002/)
- **h2188** 2013-05-20 - Marriage (Same Sex Couples) Bill. Tim Loughton's new clause 10 (70-375): opening civil partnerships to opposite-sex couples. On our ground, but which side is ours is a judgement call; suggest record only, no verdict. [Hansard](https://hansard.parliament.uk/Commons/2013-05-20/debates/13052013000002/)
- **h2192** 2013-10-09 - Transparency of Lobbying, Non-Party Campaigning and Trade Union Administration Bill. Lobbying Bill, 9 Oct 2013 (261-298). The division was on Mr Allen's amendment (the clerk's attribution sits inside the last speech), not Tom Brake's amendment 32. Direction needs the amendment's text. [Hansard](https://hansard.parliament.uk/Commons/2013-10-09/debates/13100960000002/)
- **h1305** 2014-04-09 - Finance (No. 2) Bill. Catherine McKinnell's amendment 3 (217-276): a six-month review of the new married couples' tax allowance. Weak signal; suggest record only or exclude. [Hansard](https://hansard.parliament.uk/Commons/2014-04-09/debates/14040933000002/)
- **h1495** 2015-02-23 - Serious Crime Bill [Lords]. Ann Coffey's new clause 25 (491-2): an assessment of sex-selective abortion and a strategic plan, the alternative to Fiona Bruce's clause. Near-unanimous, so little signal; suggest record only. [Hansard](https://hansard.parliament.uk/Commons/2015-02-23/debates/15022317000001/)

## Recommended to exclude (57)

| id | date | debate | votes | why not |
|---|---|---|---|---|
| h1711 | 2010-07-21 | Academies Bill [Lords] | 213-317 | Academy consultation. |
| h1710 | 2010-07-21 | Academies Bill [Lords] | 213-322 | Academies Bill amendment. |
| h1709 | 2010-07-21 | Academies Bill [Lords] | 213-327 | Academy exclusions duties. |
| h1708 | 2010-07-21 | Academies Bill [Lords] | 118-321 | Academy admissions code. |
| h1707 | 2010-07-21 | Academies Bill [Lords] | 200-314 | Academies and the National Curriculum. |
| h1706 | 2010-07-21 | Academies Bill [Lords] | 202-312 | Additional academy capacity. |
| h1705 | 2010-07-21 | Academies Bill [Lords] | 226-319 | Academies Bill amendment. |
| h2198 | 2013-10-15 | Anti-social Behaviour, Crime and Policing Bill | 236-315 | Anti-social behaviour (dogs). |
| h2197 | 2013-10-15 | Anti-social Behaviour, Crime and Policing Bill | 229-296 | Anti-social behaviour amendment. |
| h1096 | 2013-06-11 | Children and Families Bill | 222-303 | Childminder staff ratios. |
| h20440 | 2010-01-11 | Children, Schools and Families Bill | 282-206 | Programme motion. |
| h20598 | 2010-02-23 | Children, Schools and Families Bill | 386-41 | Bulk Government amendments. |
| h20597 | 2010-02-23 | Children, Schools and Families Bill | 173-280 | Publication of family court information. |
| h1455 | 2014-12-16 | Counter-Terrorism and Security Bill | 217-296 | Deradicalisation review. |
| h1454 | 2014-12-16 | Counter-Terrorism and Security Bill | 216-299 | Prevent: countering extremism messages; direction unclear. |
| h1726 | 2010-09-08 | Crime and Policing | 324-230 | Opposition day on police funding. |
| h956 | 2012-09-12 | Defamation Bill | 202-276 | Defamation Bill technical amendment; direction on free speech unclear. |
| h955 | 2012-09-12 | Defamation Bill | 204-276 | Defamation Bill: Robert Flello's amendment 7, leaving out clause 5 (website operators); direction on free speech unclear. |
| h954 | 2012-09-12 | Defamation Bill | 198-273 | Defamation Bill new clause; direction unclear. |
| h1858 | 2011-02-08 | Education Bill | 324-244 | Education Bill 2011 Second Reading: broad schools Bill. |
| h2034 | 2011-10-21 | Equality and Diversity (Reform) Bill | 0-0 | Positive action by public authorities; division records 0-0. |
| h1309 | 2014-04-09 | Finance (No. 2) Bill | 9-254 | Air passenger duty. |
| h1308 | 2014-04-09 | Finance (No. 2) Bill | 217-286 | Bank levy report. |
| h1307 | 2014-04-09 | Finance (No. 2) Bill | 219-293 | Bank levy. |
| h1972 | 2011-06-28 | Finance Bill | 159-295 | VAT report. |
| h1971 | 2011-06-28 | Finance Bill | 10-293 | VAT rate. |
| h2005 | 2011-09-07 | Health and Social Care (Re-committed) Bill | 316-251 | Health and Social Care Bill Third Reading: NHS reform, not our ground (the abortion speeches were about amendment 1). |
| h2004 | 2011-09-07 | Health and Social Care (Re-committed) Bill | 240-318 | Owen Smith amendment on NHS workforce training. |
| h2003 | 2011-09-07 | Health and Social Care (Re-committed) Bill | 255-304 | Owen Smith amendment on the Secretary of State's duty to provide services. |
| h1389 | 2014-09-26 | Iraq: Coalition Against ISIL | 524-43 | Military action against ISIL. |
| h1218 | 2013-12-17 | Local Audit and Accountability Bill [Lords] | 222-284 | Local authority audit (publicity code). |
| h1217 | 2013-12-17 | Local Audit and Accountability Bill [Lords] | 226-287 | Local authority audit. |
| h1140 | 2013-07-17 | Organ Transplants | 300-202 | Business before the Organ Transplants adjournment debate, not about transplants. |
| h1139 | 2013-07-17 | Organ Transplants | 301-203 | As 1140. |
| h1138 | 2013-07-17 | Organ Transplants | 299-205 | As 1140. |
| h1137 | 2013-07-17 | Organ Transplants | 300-204 | As 1140. |
| h1913 | 2011-03-31 | Police Reform and Social Responsibility Bill | 274-161 | Police Reform Bill Third Reading. |
| h1098 | 2013-06-12 | Protecting Children Online | 227-280 | Whipped Opposition day motion on child abuse images online; direction on our issues unclear. |
| h1399 | 2014-10-27 | Recall of MPs Bill | 166-340 | Recall of MPs. |
| h1562 | 2015-07-06 | Scotland Bill | 253-315 | Scotland Bill amendment; no proposal recorded. |
| h1561 | 2015-07-06 | Scotland Bill | 193-313 | Gender balance on Scottish public boards. |
| h1560 | 2015-07-06 | Scotland Bill | 249-312 | Equal opportunities in Scottish public appointments. |
| h1638 | 2015-11-09 | Scotland Bill | 242-287 | Gender quotas in Scotland. |
| h1637 | 2015-11-09 | Scotland Bill | 61-288 | Devolving equal opportunities. |
| h1636 | 2015-11-09 | Scotland Bill | 56-477 | Devolving tax credits. |
| h1635 | 2015-11-09 | Scotland Bill | 350-183 | Lead Government clause of the group; not new clause 15 (abortion). |
| h1634 | 2015-11-09 | Scotland Bill | 56-269 | Scottish independence referendum. |
| h1633 | 2015-11-09 | Scotland Bill | 245-287 | Consent of the Scottish Parliament to Westminster Acts. |
| h1632 | 2015-11-09 | Scotland Bill | 191-341 | Scotland Bill Government clause (elections group). |
| h1496 | 2015-02-23 | Serious Crime Bill [Lords] | 227-282 | William Cash amendment 20, a drafting change elsewhere in the Bill. |
| h1494 | 2015-02-23 | Serious Crime Bill [Lords] | 212-305 | Child abduction warning notices. |
| h1493 | 2015-02-23 | Serious Crime Bill [Lords] | 212-305 | Mandatory reporting of child abuse. |
| h1492 | 2015-02-23 | Serious Crime Bill [Lords] | 233-296 | Official Secrets Act defence for historic child abuse inquiries. |
| h1145 | 2013-09-03 | Transparency of Lobbying, Non-Party Campaigning  | 0-0 | Programme motion. |
| h1143 | 2013-09-03 | Transparency of Lobbying, Non-Party Campaigning  | 243-313 | Whipped reasoned amendment; the Second Reading vote carries the signal. |
| h2191 | 2013-10-08 | Transparency of Lobbying, Non-Party Campaigning  | 224-292 | Lobbying register. |
| h2190 | 2013-10-08 | Transparency of Lobbying, Non-Party Campaigning  | 317-249 | Programme motion. |
