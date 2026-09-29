# German 5CA readings review (areas 2-10, 12, claude-delegated)

29 September 2026. Read-only. What I did:
- checked all 18 delegated division readings against `de_divisions` and `de_votes`, broken down by party
- read the abgeordnetenwatch poll intro for 14 of them, which says what was put to the vote
- went through all 304 confirmed delegated papers that have a sitting author, by title, initiative and "why", and read two Drucksachen in full (19/19755 and 21/6347)
- ran `tools/de_5ca.py --all` against a copy of the store, into a scratch directory, to see which evidence item decides each member's column
- re-ran it with the changes below in a modified copy of the stance file (`scratchpad/rev/stance_mod.yaml`) to measure their effect

The Land-record file holds no delegated items: all nine are area 1.

**Direction inversion: none found.** Every delegated division was a vote on the bill or motion itself, not on a Beschlussempfehlung to reject it. The partisan check holds every time:
- 4119: the three sponsoring Fraktionen voted Ja.
- 4146: the Greens voted 61 Ja.
- 4215 and 6391: the AfD voted Ja.
- 929: the Greens voted Ja.
- 5098 and 5091: the bills' own camps voted Ja.

4119 did have a committee recommendation to reject, but abgeordnetenwatch records the vote as being on the Gesetzentwurf, and the tallies agree. The real problems are whipped votes and readings that sit outside the area's ground.

## Summary of recommended changes (in priority order)

| # | Reading | Area | Change | Confidence |
|---|---|---|---|---|
| 1 | div 1145 Vorratsdatenspeicherung 2015 | 7 | `placeable: false` | high |
| 2 | div 4146 Greens SBGG bill 2021 | 3 and 5 | drop `nein:` (one-sided, Ja -2 only) | high |
| 3 | div 4119 Ablösung der Staatsleistungen | 8 | `placeable: false` | medium-high |
| 3b | paper 333506 AfD Ablösung bill | 8 | `placeable: false` (for consistency with 3) | medium-high |
| 4 | div 1568 Religionsfreiheit (coalition motion) | 8 | `placeable: false` | medium |
| 5 | papers 309408, 330644 NIPT motions | 10 | `placeable: false` in area 10 (keep in area 1) | medium |
| 6 | paper 336173 Greens anti-trafficking motion | 12 | `placeable: false` | medium |
| 7 | paper 332037 AfD Epstein-files motion | 12 | `placeable: false` | medium |
| 8 | chat-control motions 326555, 326556, 288770, 329373, 326902 | 7 | authored +2 to +1 | medium-low |
| 9 | div 5091 Castellucci bill | 2 | drop `nein:` (one-sided, Ja +1 only) | medium-low |
| 10 | minor consistency: 285690 (+2 to +1), 322480 (-2 to -1), gender-language motions 294432, 296376, 300956, 333722 (+2 to +1) | 2, 4, 5 | as stated | low |
| 11 | div 4146 title says "(Greens/FDP bills)" | 3, 5 | should be "(Greens bill 19/19755; FDP abstained)" | cosmetic |

Effect of changes 1-10 together (measured on the store copy):
- **Area 7:** CDU/CSU goes from 79 at "-" to 25; SPD from 39 at "-" to 18; Linke from 16 at "++" to 1.
- **Area 3:** SPD goes from 6 at "++" to 0.
- **Area 5:** SPD goes from 5 at "++" to 0.
- **Area 8:** 89 CDU, 44 SPD and 25 AfD placements that rested on the church-payments vote come off, as do the 19 Greens and 8 Linke it put at "-".
- **Area 10:** "+" drops from 133 to 25; SPD from 31 at "+" to 2.
- **Area 12:** Greens go from 16 at "+" to 3.

---

## Per area

### Area 2, assisted dying: sound (one optional change)
Directions verified:
- 1142 (2015, Ja = the § 217 ban, passed 370-232) is correct.
- 5098 (the merged Helling-Plahr/Künast liberal bill, Ja = liberalise) is correct. CDU voted 180 Nein to 3 Ja.
- 5091 (Castellucci, Ja = restrictive) is correct.

All three were free votes. Fraktion totals (CDU ++132, AfD ++49, SPD split 33 ++ / 66 --, Greens split 19 ++ / 41 --) match a conscience vote.

| Reading | Says | Should say | Evidence | Confidence |
|---|---|---|---|---|
| div 5091 | Ja +1, Nein -1 | Ja +1 only (drop `nein`) | The Nein lobby is mixed: liberals, plus hard-liners who reject any legal route (the reading's own note says so). 60 sitting members voted Nein on both bills (39 AfD, 16 CDU, 4 SPD, 1 Green); all now read "conflicting". Four members (Brandl, Oster CDU; König, Kotré AfD) sit at "-" on this Nein alone. | medium-low |
| paper 285690 (Castellucci suicide-prevention motion) | +2 | +1, or unplaceable like its twin 301514 and vote 5099 | Suicide prevention was backed by both camps (5099 passed 687-1, and is correctly unplaceable). No placement changes: its signers are the Castellucci bill's signers, and the bill is the higher tier. | low |

### Area 3, gender medicine and children: needs changes
The fit of 4146 to this area is confirmed. The Greens' bill 19/19755 contained an SGB V entitlement to "geschlechtsangleichende Maßnahmen einschließlich Hormontherapie", and let a family court override parents on surgery from age 14. Source: https://dserver.bundestag.de/btd/19/197/1919755.pdf

| Reading | Says | Should say | Evidence | Confidence |
|---|---|---|---|---|
| div 4146 | Ja -2, Nein +2 | Ja -2 only (drop `nein`) | This is the whipped-vote trap. The SPD voted 138 Nein as the CDU/CSU's coalition partner in May 2021, then 178-0 Ja on the SBGG in 2024. Six SPD members who were absent in 2024 sit at **++** on this Nein alone: **Lars Klingbeil, Rolf Mützenich, Kerstin Griese, Martin Gerster, Stefan Zierke, Josephine Ortleb** (confidence reads "moderate (whipped vote)"). abgeordnetenwatch poll 4146 intro: "Die Fraktionen B90/GRÜNE und DIE LINKE stimmten für den Gesetzesentwurf, während die SPD, die CDU und die AfD dagegen stimmten." Cost of the fix: 14 CDU and 11 AfD lose a ++ that rested only on this vote. | high |
| div 5496 (area 3 copy) | Ja -2, Nein +2 | optional: ±1 in area 3 (keep ±2 in area 5) | The SBGG regulates legal sex only; it expressly leaves medical measures alone. At ±2 it decides 127 CDU, 94 SPD and 62 Greens, which makes the area 3 sheet a copy of area 5. ±1 would keep the sides and reserve ++/-- for medical-transition acts. This is the German team's call. | low |
| div 4146 title | "(Greens/FDP bills)" | "(Greens bill 19/19755; FDP abstained)" | Same intro: "Die Fraktion FDP enthielt sich" (FDP abstained 74-0). The FDP bill was a separate poll. | cosmetic |

The area 3 papers are sound: AfD motions and bills on minors are +2, and CDU/AfD critical questions are +1.

### Area 4, conversion practices: sound (tiny sheet, 7 placed)
| Reading | Says | Should say | Evidence | Confidence |
|---|---|---|---|---|
| paper 322480 (Linke written question) | -2 | -1 | Every other question in every area is ±1. At -2 a single written question reads "--". | low |

### Area 5, sex-based rights: needs changes (same as area 3)
| Reading | Says | Should say | Evidence | Confidence |
|---|---|---|---|---|
| div 4146 (area 5 copy) | Ja -2, Nein +2 | Ja -2 only | The same whipped SPD Nein puts Klingbeil, Gerster, Griese, Zierke and Mützenich at ++. | high |
| papers 294432, 296376, 300956, 333722 (AfD gender-language motions) | +2 | +1 | Vote 4215 on the same subject is +1 (correct: gender-neutral language is peripheral to sex-based rights). Keep 304830 ("Genderideologie", binary sex) at +2. Only moves AfD members between ++ and +. | low |

Everything else is sound:
- 4215 is correctly one-sided under the Brandmauer rule.
- 986 is correctly unplaceable.
- The Meldewesen / data-transfer questions at -1 are right.
- Fraktion totals (CDU ++143, SPD --97, Greens --68, AfD ++66) are as expected.

### Area 6, parental rights and education: sound
There are no divisions. The papers read correctly: AfD against early sex education is +; Linke queer-youth-work inquiries are -. Linke at -24 is expected. One weak item, low confidence: 338588 (a Greens written question on school refusal, -1) draws its direction from its framing, and could be unplaceable.

### Area 7, free speech, privacy and civil liberties: needs changes
The surprise to explain is CDU/CSU at **79 "-"** and SPD at 39 "-", against Greens at 20 "+" and Linke at 16 "++".
- **53 CDU and 22 SPD** are decided solely by div 1145: a whipped Union-SPD coalition bill passed in "Eilverfahren", with CDU 275-0 Ja.
- **12 Linke sit at ++** on their chat-control motion (Vorgang 326556, +2).
- The "Nein" on § 188 abolition (6391) correctly carries no value, because it was an AfD bill. So CDU is penalised for data retention but, correctly, not for § 188, and privacy ends up outweighing speech.

| Reading | Says | Should say | Evidence | Confidence |
|---|---|---|---|---|
| div 1145 | Ja -1, Nein +1 | `placeable: false` | A whipped coalition bill (Union and SPD for, Linke and Grüne against). It is on surveillance, not speech, and it is the only tier-2 item for 53 CDU members. It is the Brandmauer mirror: a coalition lobby tells no member apart. abgeordnetenwatch intro: "Union und SPD haben im Eilverfahren die Wiedereinführung ... beschlossen. Linke und Grüne stimmten gegen den Antrag." | high |
| papers 326555 (Greens), 326556 and 288770 (Linke), 329373 and 326902 (AfD): chat-control motions | +2 | +1 | Privacy is in scope (chat control is tier 1 in the taxonomy), but +2 makes the Linke "strong allies" on a free-speech sheet, while their Fraktion backs DSA enforcement (330490) and HateAid (331591), and the Greens tabled the "Demokratieschild" (336629, correctly -2). The AfD stays ++ via § 188. | medium-low |

Sound: 6391 (one-sided, AfD bill, AfD 132 Ja); the § 188 and DSA papers; the Democracy Shield at -2; the CDU pro-retention questions at -1 (personal acts, fine as tier 0).

### Area 8, freedom of religion or belief: needs changes
Surprise: CDU +101, SPD +55 and AfD +74 rest mainly on **Nein to ending the church state payments** (4119 decides 89 CDU, 44 SPD and 25 AfD), with Greens -19 and Linke -8 on the same vote.

| Reading | Says | Should say | Evidence | Confidence |
|---|---|---|---|---|
| div 4119 | Ja -1, Nein +1 | `placeable: false` | Not a FoRB question: redeeming the 1803 payments is a constitutional mandate (Art. 140 GG with Art. 138 WRV), and the bill was a Grundsätzegesetz with compensation. It is also the whipped trap: in May 2021 the SPD voted Nein as the Union's partner, then signed the Ampel coalition agreement (Nov. 2021) that promised this very Grundsätzegesetz. poll 4119 intro: "abgelehnt ... Zustimmung erhält der Entwurf nur von den antragstellenden Fraktionen". | medium-high |
| paper 333506 (AfD Ablösung bill 2026) | -1 | `placeable: false` | Consistency with 4119. The related Ablösung questions are already unplaceable. | medium-high |
| div 1568 | Ja +1 only | `placeable: false` | A coalition motion passed by CDU/CSU and SPD alone: Greens, Linke and FDP abstained, AfD voted 80 Nein. Its Ja is the government whip, not conviction, so it is the one-sided reading applied to the wrong lobby. It decides few members today, but would become the deciding item once 4119 goes. | medium |

After these changes, area 8 is decided by circumcision (963, sound: Ja = keep it lawful, 433-100, mixed parties), persecution-abroad papers and speeches. Two further surprises need explaining:
- **AfD at 16-17 "-":** the tier-2 AfD bill 317644 extends Art. 18 GG forfeiture to Art. 4(2) religious practice, read -1. As a bill it outranks the AfD's many +2 Christian-persecution motions (tier 1). The direction is defensible, because a forfeiture tool on religious practice could be turned on any faith. Flag it for the German team; I would not change it.
- **Greens (+22) and Linke (+23) after the fix:** these come from Syria-minorities inquiries and motions (327515, 329387). That is FoRB ground but a low-cost consensus signal.

### Area 9, marriage and family: sound
- 1232 (Ehe für alle, free vote) and 929 (2012 Greens motion, Ja = open marriage) are correct.
- 1096 and 1571 are correctly unplaceable.
- The splitting papers (keeping spousal splitting +, abolishing it -) are consistently read.

Fraktion totals are as expected. CDU at 18 "--" is the 2017 CDU Ja voters, which is genuine for a free vote.

### Area 10, surrogacy and embryology: needs changes
- 879 (PGD 2011, free vote, Ja = permit, -2) is correct.

The surprise is **SPD +31 and Greens +17** on surrogacy. Almost all of it comes from the cross-party NIPT monitoring motion (20/10515, 21/3873), which decides 97 of the 194 "+" placements.

| Reading | Says | Should say | Evidence | Confidence |
|---|---|---|---|---|
| papers 309408, 330644 (area 10 copies) | +1 | `placeable: false` in area 10 | NIPT is a prenatal blood test (area 1 ground), not surrogacy or embryos. The same Vorgänge are already on the Christopher-confirmed abortion sheet. Area 10's taxonomy terms (surrogacy, HFEA, embryo research, gamete and egg donation, embryo screening) do not include prenatal testing. | medium |

The AfD surrogacy-ban motion 303093 (+2) and the surrogacy questions are sound.

### Area 12, prostitution, trafficking and sexual exploitation: needs changes
The surprise is **Greens +16**. CitizenGO backs the Nordic model; the Greens oppose it.

| Reading | Says | Should say | Evidence | Confidence |
|---|---|---|---|---|
| paper 336173 (Greens, 21/6347 "Menschenhandel und Zwangsprostitution bekämpfen") | +1 | `placeable: false` | Read in full. It is an anti-trafficking and victims'-rights motion with no position on demand or a Sexkaufverbot, and it uses the "Sexarbeit" framing ("Arbeitsrecht, einschließlich zur Sexarbeit"). Everyone opposes trafficking, so it tells no member apart on our ground. It decides 14 Greens. https://dserver.bundestag.de/btd/21/063/2106347.pdf | medium |
| paper 332037 (AfD, 21/4462 Epstein files) | +1 | `placeable: false` | A political investigation motion, not a prostitution or trafficking policy position. It decides 33 AfD. | medium |

The remaining generic anti-trafficking questions (286779, 286198, 313629, 325621, 336221) are the same kind of consensus item. I would treat them the same way, at low confidence. The "sex-worker seat on the commission" questions at -1 are sound.

---

## Tool observation (not a reading)
`place()` labels every Bundestag vote "moderate (whipped vote)", including the free votes 1142, 5098, 5091, 1232, 879 and probably 963. The German team will read "whipped" in the Confidence column on exactly the conscience votes that are the strongest personal evidence. A `free_vote: true` flag on those readings, read by `place()`, would fix it.

## Could not verify
- Whether 963 (circumcision, 2012) was formally a free vote. The mixed party splits suggest it was.
- I did not read the text of the Art. 18 AfD bill 317644; its reading rests on the title and "why".
- Paper directions were checked against title, initiative and "why" only, except 19/19755 and 21/6347, which I read in full.
- The 60 confirmed delegated papers with no sitting author, and the ~300 unplaceable delegated papers, were only skimmed (a scan of the unplaceable Anträge and Gesetzentwürfe found nothing wrongly held out). None of them place anyone today.
- Model-scored speeches (e.g. the SPD and CDU "-" speech placements on area 7) are outside the readings and were not reviewed.
- The DIP API was not needed and was not called.

Scratch artefacts: `scratchpad/rev/` holds `papers.txt` (every delegated paper with sitting-author counts by party), `out/` (current sheets), `out_mod/` and `run_mod.txt` (sheets with changes 1-10), and `stance_mod.yaml`.

## What was applied (29 September 2026)

Christopher delegated this review ("review 2 for me. The German team will
feedback later if something is wrong"). Applied in config/de_stance.yaml:
- 1145, 1568, 4119 and paper 333506: `placeable: false`, with the reasons above.
- 4146 (areas 3 and 5): Ja side only. The title is corrected to the Greens' bill.
- 5091: Ja side only.
- Papers 309408 and 330644 (area 10), 332037 and 336173 (area 12): `placeable: false`.
- The free-vote label: `free_vote: true` on 1142, 5098, 5091, 1232 and 879. tools/de_5ca.py
  now reads "strong (free vote)" for them.

Not applied, as matters of degree or questions for the German team:
- the +2 to +1 downgrades on the chat-control, gender-language, 285690 and 322480 papers;
- ±1 for the 2024 SBGG on area 3;
- the AfD Art. 18 bill in area 8.

The abortion sheet, which Christopher confirmed, is byte-identical.
