# Triage queue for the edition of 2026-07-06

Score each item using the rubric below, then run the render step
(`python3 run_weekly.py --render 2026-07-06`), which applies these scores.

SCORE: 0 = irrelevant to every area. 1 = background only. 2 = belongs in the
weekly digest. 3 = likely campaign or lobbying trigger. Score on relevance
regardless of whether an item helps or hurts the campaign position.
WHY: maximum 35 words, CitizenGO voice: direct, concrete, no hedging, British
spelling, no em dashes. State the implication, not a summary.

Do not edit the `### item:` id lines.

<!-- scoring context (verbatim from handoff section 7):
You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns
on: abortion (pro-life), assisted dying (opposed), youth gender medicine (opposed to
paediatric transition), conversion practices bans (concerned re therapy/parental/religious
freedom), single-sex spaces (sex-based rights), parental rights in education, free speech
and online safety overreach, freedom of religion or belief, marriage and family, surrogacy
(opposed to commercial surrogacy).

For each item, return JSON: {"id": ..., "score": 0-3, "areas": [..],
"why_it_matters": "..."}.
Score 0 = irrelevant to every area. 1 = background only. 2 = belongs in the weekly
digest. 3 = likely campaign or lobbying trigger.
why_it_matters: maximum 35 words, CitizenGO voice: direct, concrete, no hedging,
British spelling, no em dashes. State the implication, not a summary.
Score on relevance to the areas above regardless of whether an item helps or hurts
the campaign position: opposition activity scores as highly as friendly activity.
Return only the JSON array.
-->

---

### item: consultation:/government/consultations/tying-the-knot-reforming-weddings-law-in-england-and-wales
- tier: 1 | candidate areas: 9 | watchlist hit: yes
- title: Consultation: Tying the Knot: Reforming weddings law in England and Wales
SCORE: 3
WHY: Law Commission weddings reform is open for responses. Celebrant-led and outdoor weddings risk detaching marriage from its legal safeguards. Response needed before 24 September.

### item: consultation:/government/consultations/updating-foster-care-standards-and-guidance
- tier: 2 | candidate areas: 6 | watchlist hit: no
- title: Consultation: Updating foster care standards and guidance
SCORE: 2
WHY: Foster care standards rewrite shapes who may care for children and on what terms. Watch for faith-based carers' position and parental contact rules.

### item: consultation:/government/consultations/send-reform-education-otherwise-than-at-school
- tier: 1 | candidate areas: 6 | watchlist hit: no
- title: Consultation: SEND reform: education otherwise than at school
SCORE: 3
WHY: Government plans to reshape education outside school. Direct bearing on home-educating families and parental choice. Supporter response campaign viable before 18 September.

### item: consultation:/government/consultations/improving-help-and-child-protection-revised-framework
- tier: 2 | candidate areas: 6 | watchlist hit: no
- title: Consultation: Improving help and child protection: revised framework
SCORE: 2
WHY: Revised child protection framework redraws the state-family boundary. Watch thresholds for intervention and any drift toward monitoring lawful home education.

### item: si:G6pPGK1m
- tier: 2 | candidate areas: 6 | watchlist hit: yes
- title: SI: Children's Wellbeing and Schools Act 2026 (Establishment of Schools) (Consequential Amendments) Regulations 2026, Draft affirmative, laid 2026-05-20; approved by Commons division #51 (369-102 on 2026-07-08)
SCORE: 2
WHY: First implementing regulations under the Children's Wellbeing and Schools Act. The Act's school-establishment machinery is now moving; register procedure and commencement dates.

### item: whatson:2026-07-09:71389195
- tier: 2 | candidate areas: - | watchlist hit: yes
- title: after other business, Lords Short debate. Modern Service Framework for Dementia and Frailty will improve dementia diagnosis, ensure robust and acceptable clinical data and performance metrics and enable access to innovative treatments
SCORE: 1
WHY: Dementia service framework debate. No tracked issue engaged; watchlist term match is incidental.

### item: whatson:2026-07-08:60666158
- tier: 2 | candidate areas: 2 | watchlist hit: no
- title: after other business, Commons Ten Minute Rule Motion. Mental capacity (duty to assess)
SCORE: 2
WHY: Ten Minute Rule Motion to create a duty to assess mental capacity. Capacity assessment is the load-bearing safeguard in the assisted dying bill; note sponsor and support.

### item: whatson:2026-07-07:50150959
- tier: 2 | candidate areas: 7 | watchlist hit: no
- title: after other business, Lords Orders and regulations. Wireless Telegraphy Act 2006 (Directions to OFCOM) (Revocation) Order 2026
SCORE: 0
WHY: 

### item: whatson:2026-07-07:25107813
- tier: 2 | candidate areas: 6 | watchlist hit: yes
- title: after other business, Lords Orders and regulations. Children’s Wellbeing and Schools Act 2026 (Establishment of Schools) (Consequential Amendments) Regulations 2026
SCORE: 2
WHY: Lords considers the schools regulations two days before the Commons vote. Any critical motion signals peer unease worth logging.

### item: division:2402
- tier: 2 | candidate areas: 6 | watchlist hit: yes
- title: Division #51 (369-102): Draft Children’s Wellbeing and Schools Act 2026 (Establishment of Schools) (Consequential Amendments) Regulations 2026
SCORE: 2
WHY: Commons approved the schools regulations 369 to 102. Implementation of the Act proceeds; division list feeds MP profiles.
