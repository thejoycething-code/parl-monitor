# Canadian Provinces Monitor
### Week ending 2026-10-14 | Edition 1 | 8 October 2026 to 14 October 2026

_Weekly, after the Provinces weekly collection; to Christopher by DM._

> **How to read this edition.** Areas come from the shared taxonomy (v1.25) and the provincial watchlist, matched on each bill's TEXT passage by passage (provincial titles name a statute, not a subject), on each division's question and debate, and on each speech's own words; Quebec is read in French (taxonomy-qc). A division takes its bill's areas, so a procedural vote on a bill on our ground is listed under it. Results and tallies are the legislature's own; party splits are the party at the vote where the source dates it. **Whether a vote helped or hurt is a human call**: a direction is printed only where a signed reading in config/prov_stance.yaml covers that division, and the 5CA lines count members placed by signed readings alone. Scores [0-3] and the italic why-lines come from the provincial judge (tools/prov_triage.py, provincial frame): the session judge, Claude Code on the Mac Mini on the plan allowance, or the paid API judge (PROV_JUDGE). Migration is matched and stored but not shown.

## Top lines

- **Activity on our ground in 1 of 9 provinces**: Manitoba (4 speaker-debates in Hansard).

**Quiet this week** (nothing on our ground): Alberta, Saskatchewan, British Columbia, Ontario, Quebec, New Brunswick, Newfoundland and Labrador, Nova Scotia.

**Out of reach:** Prince Edward Island (every page behind a CAPTCHA, from CI too); the territories are not collected.

## Manitoba

_Legislative Assembly of Manitoba. 4 speaker-debates in Hansard. Latest division in the store 8 Oct; latest Hansard day read 13 Oct._

**Hansard on our ground (4 speaker-debate(s); one line each, never the speech)**

- **Diljeet Brar** (NDP) · 13 Oct · Res. 16-Standing Against Anti-Sikh Hate: “Today, all of us in this Chamber are working together to call this hatred and negativity out with one voice-a loud voice-and we say: anti-Sikh hatred has no pl…” (Free speech, privacy and civil liberties) [Hansard](https://www.gov.mb.ca/legislature/hansard/43rd_3rd/vol_71a/h71a.html)
- **Jodie Byram** (PC) · 13 Oct · Res. 16-Standing Against Anti-Sikh Hate - Debate: “It's important to recognize that hate is not always expressed through physical violence. It appears in hateful comments, racist stereotypes, intimidation, hara…” (Freedom of religion) [Hansard](https://www.gov.mb.ca/legislature/hansard/43rd_3rd/vol_71a/h71a.html)
- **Wayne Ewasko** (PC) · 13 Oct · Res. 16-Standing Against Anti-Sikh Hate - Debate: “I did want to say, quickly, that this isn't just a New Democrat political stripe endeavour. Back in 2019, we, the Progressive Conservatives, led Manitoba's for…” (Freedom of religion) [Hansard](https://www.gov.mb.ca/legislature/hansard/43rd_3rd/vol_71a/h71a.html)
- **[1]** **Mike Moroz** (NDP) · 7 Oct · Third Anniversary of Hamas Attack in Israel: “We must also recognize the rise in Islamophobia and the terrible suffering and killing of Palestinians over the past three years in Gaza and the West Bank. We'…” (Free speech, privacy and civil liberties) [Hansard](https://www.gov.mb.ca/legislature/hansard/43rd_3rd/vol_69/h69.html) _(collected late)_
  _A members' statement on the Gaza conflict and Islamophobia. Background on community tension and religious belief in Manitoba, with no bill, vote or policy proposal attached._

**5CA, signed readings only:** 6 confirmed division reading(s).
- Abortion: ++ 18 · + 0 · 0 (not placed) 8 · - 0 · -- 31 (of 57 sitting)
- Gender medicine children: ++ 0 · + 4 · 0 (not placed) 16 · - 37 · -- 0 (of 57 sitting)
- Sex based rights: ++ 16 · + 0 · 0 (not placed) 4 · - 5 · -- 32 (of 57 sitting)

## Coverage

- **Alberta:** store last read 14 October 2026; latest division 13 May 2026, latest Hansard day 14 May 2026.
- **Saskatchewan:** store last read 9 October 2026; latest division 12 May 2026, latest Hansard day 14 May 2026.
- **British Columbia:** store last read 14 October 2026; latest division 28 May 2026, latest Hansard day 28 May 2026.
- **Manitoba:** store last read 14 October 2026; latest division 8 October 2026, latest Hansard day 13 October 2026.
- **Ontario:** store last read 9 October 2026; latest division 2 June 2026, latest Hansard day 2 June 2026.
- **Quebec:** store last read 14 October 2026; latest division 12 June 2026, latest Hansard day 12 June 2026.
- **New Brunswick:** store last read 14 October 2026; latest division 11 June 2026, latest Hansard day 12 June 2026.
- **Newfoundland and Labrador:** store last read 14 October 2026; latest division 17 September 2026, latest Hansard day 17 September 2026.
- **Nova Scotia:** store last read 14 October 2026; latest division 18 September 2026, latest Hansard day none (no Hansard reader).
- **Prince Edward Island:** not collected (Radware CAPTCHA on every inner page, from CI too). Yukon, the Northwest Territories and Nunavut are not collected.
- **Bill stages:** Manitoba, Ontario and Saskatchewan bill pages give the store no dated stages, so their bills show here only through a division; Nova Scotia's are dated for the bills read since its build.
- **Nova Scotia** has divisions and bills but no Hansard speeches reader.
- **Fallen bills** are shown the week a province's next session first appears in the store; a dissolution with no new session yet (Quebec's, for the 5 October 2026 election) shows when the new legislature's first session is collected.
- **Judge:** 100 item(s) scored so far (tools/prov_triage.py; the session judge, jobs/prov-session-judge.sh, is the free default).
- **Noise filter** (config/prov-noise.yaml): nothing muted this week. It takes measured false positives off an item's areas, never a watched item or one a signed reading covers.
- **5CA sheets** are rebuilt every week (data/5ca/prov-5ca-*.csv); only confirmed readings in config/prov_stance.yaml place anyone.
- **Migration** is matched and stored but not shown, as in every edition here.
- Specification and decisions: [docs/canada-provinces-scope.md](https://github.com/thejoycething-code/parl-monitor/blob/main/docs/canada-provinces-scope.md).

