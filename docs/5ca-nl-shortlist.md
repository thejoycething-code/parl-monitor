# Netherlands 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 212 readings waiting in `config/nl_stance.yaml` (2 proposed, 0 procedural, 210 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-nl-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc nl --confirm 6e41ea31-2a9d-43d6-bf62-95abf4300314 65d66131-e28d-4817-bdc7-5c651e761f98 --by Christopher

## Top 20

### 1. `6e41ea31-2a9d-43d6-bf62-95abf4300314` Initiatiefwetgeving: Voorstel van wet van de leden Paternotte en Bevers tot wijziging van de Embryowet in verband met de afschaffing van het

- **Why first (101 points):** a vote on the whole text; the last such vote on its bill; watched bill 36416; values proposed: one tick to sign; split CDA, JA21 (10 against their group); meaning line ready; this year.
- **When / result:** 2025-12-16; Tweede Kamer; Aangenomen (90-59).; Voor 90, Tegen 59
- **On:** ["Voorstel van wet van de leden Paternotte en Bevers tot wijziging van de Embryowet in verband met de afschaffing van het tijdelijk verbod op het doen ontstaan van embryo’s voor wetenschappelijk onder
- **Area:** surrogacy and embryology
- **Lobbies:** Voor: D66 26, VVD 21, GroenLinks-PvdA 20, CDA 12, JA21 4, PvdD 3, SP 3, Volt 1. Tegen: PVV 26, FVD 7, CDA 6, JA21 5, BBB 4, ChristenUnie 3, DENK 3, SGP 3, 50PLUS 2
- Meaning: **Voor** = to pass 36416 (Initiative bill (Paternotte, Bevers) lifting the temporary ban on creating embryos for research) as a whole; **Tegen** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Voor -2, Tegen +2
  - Voted Voor on 36416 (Initiative bill (Paternotte, Bevers) lifting the temporary ban on creating embryos for res): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc nl --confirm 6e41ea31-2a9d-43d6-bf62-95abf4300314 --by Christopher`

### 2. `65d66131-e28d-4817-bdc7-5c651e761f98` Motie: Motie van het lid Piri c.s. over aanstaande zondag de regenboogvlag boven het Kamergebouw hijsen

- **Why first (95 points):** a vote on the whole text; the last such vote on its bill; watched bill 2026Z21728; values proposed: one tick to sign; meaning line ready; recent.
- **When / result:** 2026-10-08; Tweede Kamer; Aangenomen (90-36).; Voor 90, Tegen 36
- **On:** ["Raad Algemene Zaken en Raad Buitenlandse Zaken"]
- **Area:** sex-based rights
- Meaning: **Voor** = to adopt the motion 2026Z21728 (Motion (Piri c.s.) to fly the rainbow flag over the Kamer building; roll-call vote of 8 October 2026, adopted…); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Voor -2, Tegen +2
  - Voted Voor on 2026Z21728 (Motion (Piri c.s.) to fly the rainbow flag over the Kamer building): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc nl --confirm 65d66131-e28d-4817-bdc7-5c651e761f98 --by Christopher`

### 3. `1f870bad-d142-455d-8fb2-7e99a5db09e3` Motie: Motie van de leden Bikker en Diederik van Dijk over voorkomen dat Nederlandse kennis en technologie over kiembaanmodificatie worden i

- **Why first (95 points):** a vote on the whole text; the last such vote on its bill; watched bill 36416; close: 72-70; meaning line ready; this year.
- **When / result:** 2025-12-09; Tweede Kamer; Aangenomen. (72-70); Voor 72, Tegen 70
- **On:** ["Voorstel van wet van de leden Paternotte en Bevers tot wijziging van de Embryowet in verband met de afschaffing van het tijdelijk verbod op het doen ontstaan van embryo’s voor wetenschappelijk onder
- **Area:** surrogacy and embryology
- **Lobbies:** Voor: PVV 25, CDA 17, JA21 9, FVD 7, BBB 4, ChristenUnie 3, DENK 3, 50PLUS 2, SGP 2. Tegen: D66 25, VVD 20, GroenLinks-PvdA 19, SP 3, PvdD 2, Volt 1
- Meaning: **Voor** = to adopt the motion 36416 (Initiative bill (Paternotte, Bevers) lifting the temporary ban on creating embryos for research); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A motion tabled in the dossier of 36416 (against): its own text decides which side is ours, not the bill's direction. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `1f870bad-d142-455d-8fb2-7e99a5db09e3` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 1f870bad-d142-455d-8fb2-7e99a5db09e3 --by Christopher`

### 4. `99306983-cd0d-4e47-83e6-99699d4cf2be` Wetgeving: Wijziging van de Embryowet naar aanleiding van de derde wetsevaluatie

- **Why first (80 points):** a vote on the whole text; the last such vote on its bill; watched bill 36677; split JA21 (4 against their group); meaning line ready; this year.
- **When / result:** 2026-06-02; Tweede Kamer; Aangenomen. (95-48); Voor 95, Tegen 48
- **On:** ["Wijziging van de Embryowet naar aanleiding van de derde wetsevaluatie"]
- **Area:** surrogacy and embryology
- **Lobbies:** Voor: D66 25, VVD 21, GroenLinks-PvdA 20, CDA 18, JA21 5, SP 3, PvdD 2, Volt 1. Tegen: PVV 19, Groep Markuszower 7, FVD 5, JA21 4, ChristenUnie 3, DENK 3, 50PLUS 2, BBB 2, SGP 2, Keijzer 1
- Meaning: **Voor** = to pass 36677 (the vehicle for amendments on creating embryos and on IVG gametes (17 matched items this Kamer)) as a whole; **Tegen** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2025Z00250, 36677: CitizenGO's position on '["Wijziging van de Embryowet naar aanleiding van de derde wetsevaluatie"]' needs a human reading. Add a `bill_directions` line or wr
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `99306983-cd0d-4e47-83e6-99699d4cf2be` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 99306983-cd0d-4e47-83e6-99699d4cf2be --by Christopher`

### 5. `2f39fc12-c53b-42f8-bc88-a8a4ca292781` Motie: Motie van de leden Boomsma en Bikker over ook voor klanten van prostitutie een wettelijke minimumleeftijd van in ieder geval 18 jaar 

- **Why first (77 points):** a vote on the whole text; the last such vote on its bill; tier 1; close-ish: 71-79; meaning line quotes the source; recent.
- **When / result:** 2026-09-22; Tweede Kamer; Verworpen.; Voor 71, Tegen 79
- **On:** ["Mensenhandel"]
- **Area:** prostitution and trafficking
- **Lobbies:** Voor: VVD 31, CDA 20, JA21 9, Groep Markuszower 7, BBB 3, ChristenUnie 3, DENK 3, SGP 3, 50PLUS 2. Tegen: D66 29, PRO 20, PVV 19, FVD 10, PvdD 3, SP 3, Volt 1 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion “Motie: Motie van de leden Boomsma en Bikker over ook voor klanten van prostitutie een…”; **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z18344, 28638: CitizenGO's position on '["Mensenhandel"]' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2f39fc12-c53b-42f8-bc88-a8a4ca292781` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 2f39fc12-c53b-42f8-bc88-a8a4ca292781 --by Christopher`

### 6. `c0f3ac8d-d325-4023-aee6-bdefdc7d1089` Motie: Motie van het lid Bikker over de CCMO laten rapporteren over het aantal en de aard van de onderzoeken met intacte ELS

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36677; meaning line ready; this year.
- **When / result:** 2026-06-02; Tweede Kamer; Aangenomen.; Voor 127, Tegen 23
- **On:** ["Wijziging van de Embryowet naar aanleiding van de derde wetsevaluatie"]
- **Area:** surrogacy and embryology
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, PVV 19, FVD 10, JA21 9, Groep Markuszower 7, BBB 3, ChristenUnie 3, DENK 3, SGP 3, SP 3, 50PLUS 2, Volt 1. Tegen: PvdD 3, GroenLinks-PvdA 1 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36677 (the vehicle for amendments on creating embryos and on IVG gametes (17 matched items this Kamer)); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z10358, 36677: CitizenGO's position on '["Wijziging van de Embryowet naar aanleiding van de derde wetsevaluatie"]' needs a human reading. Add a `bill_directions` line or wr
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `c0f3ac8d-d325-4023-aee6-bdefdc7d1089` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm c0f3ac8d-d325-4023-aee6-bdefdc7d1089 --by Christopher`

### 7. `f7a92313-659d-4066-9fdf-86c2a9862fb4` Motie: Motie van het lid Vliegenthart over de Embryowet binnen twee jaar evalueren en daarbij expliciet de toekomstbestendigheid meenemen

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36677; meaning line ready; this year.
- **When / result:** 2026-06-02; Tweede Kamer; Aangenomen.; Voor 117, Tegen 33
- **On:** ["Wijziging van de Embryowet naar aanleiding van de derde wetsevaluatie"]
- **Area:** surrogacy and embryology
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, FVD 10, JA21 9, BBB 3, DENK 3, PvdD 3, SP 3, 50PLUS 2, GroenLinks-PvdA 1, Volt 1. Tegen: PVV 19, Groep Markuszower 7, ChristenUnie 3, SGP 3 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36677 (the vehicle for amendments on creating embryos and on IVG gametes (17 matched items this Kamer)); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z10363, 36677: CitizenGO's position on '["Wijziging van de Embryowet naar aanleiding van de derde wetsevaluatie"]' needs a human reading. Add a `bill_directions` line or wr
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `f7a92313-659d-4066-9fdf-86c2a9862fb4` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm f7a92313-659d-4066-9fdf-86c2a9862fb4 --by Christopher`

### 8. `46085a3e-ec40-488f-8dec-a2c33ee7180a` Motie: Motie van de leden Westerveld en Ceder over in de route naar inclusief onderwijs specifiek de rol en functie van samenwerkingsverband

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36663; meaning line ready; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Aangenomen.; Voor 132, Tegen 18
- **On:** ["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim in het funderend onderwijs en het beroepsonderwijs (Wet terugdringen
- **Area:** parental rights and education
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, PVV 19, JA21 9, BBB 3, ChristenUnie 3, DENK 3, PvdD 3, SP 3, 50PLUS 2, GroenLinks-PvdA 1, Volt 1. Tegen: FVD 10, Groep Markuszower 7, SGP 3 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36663 (enforcement of compulsory schooling, watched for its reach into exemptions and home education. 22 matched…); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z06358, 36663: CitizenGO's position on '["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim i
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `46085a3e-ec40-488f-8dec-a2c33ee7180a` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 46085a3e-ec40-488f-8dec-a2c33ee7180a --by Christopher`

### 9. `7fda9159-0202-48b9-959e-b1a256dfce72` Motie: Motie van het lid Beckerman over borgen dat het geld voor leerlingen die aan het begin van het schooljaar veel afwezig zijn ook aan d

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36663; meaning line ready; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Verworpen.; Voor 58, Tegen 92
- **On:** ["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim in het funderend onderwijs en het beroepsonderwijs (Wet terugdringen
- **Area:** parental rights and education
- **Lobbies:** Voor: PVV 19, FVD 10, DENK 3, PvdD 3, SP 3, 50PLUS 2, GroenLinks-PvdA 1, Volt 1. Tegen: VVD 31, D66 29, CDA 20, JA21 9, Groep Markuszower 7, BBB 3, ChristenUnie 3, SGP 3 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36663 (enforcement of compulsory schooling, watched for its reach into exemptions and home education. 22 matched…); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z06360, 36663: CitizenGO's position on '["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim i
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `7fda9159-0202-48b9-959e-b1a256dfce72` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 7fda9159-0202-48b9-959e-b1a256dfce72 --by Christopher`

### 10. `85b66610-96c3-4a17-861b-5496a98a6799` Motie: Motie van het lid Ceder over beter borgen dat er effectief actie wordt ondernomen bij geoorloofd verzuim door ziekte

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36663; meaning line ready; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Verworpen.; Voor 40, Tegen 110
- **On:** ["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim in het funderend onderwijs en het beroepsonderwijs (Wet terugdringen
- **Area:** parental rights and education
- **Lobbies:** Voor: Groep Markuszower 7, ChristenUnie 3, DENK 3, PvdD 3, SP 3, GroenLinks-PvdA 1, Volt 1. Tegen: VVD 31, D66 29, CDA 20, PVV 19, FVD 10, JA21 9, BBB 3, SGP 3, 50PLUS 2 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36663 (enforcement of compulsory schooling, watched for its reach into exemptions and home education. 22 matched…); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z06355, 36663: CitizenGO's position on '["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim i
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `85b66610-96c3-4a17-861b-5496a98a6799` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 85b66610-96c3-4a17-861b-5496a98a6799 --by Christopher`

### 11. `9f1782a6-f2bc-4bc6-939b-475a402d16e0` Motie: Motie van het lid Rooderkerk c.s. over leerplichtambtenaren actief ondersteunen bij hun preventieve taak

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36663; meaning line ready; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Aangenomen.; Voor 131, Tegen 19
- **On:** ["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim in het funderend onderwijs en het beroepsonderwijs (Wet terugdringen
- **Area:** parental rights and education
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, FVD 10, JA21 9, Groep Markuszower 7, BBB 3, ChristenUnie 3, DENK 3, PvdD 3, SGP 3, SP 3, 50PLUS 2, GroenLinks-PvdA 1, Volt 1. Tegen: PVV 19 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36663 (enforcement of compulsory schooling, watched for its reach into exemptions and home education. 22 matched…); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z06359, 36663: CitizenGO's position on '["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim i
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `9f1782a6-f2bc-4bc6-939b-475a402d16e0` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 9f1782a6-f2bc-4bc6-939b-475a402d16e0 --by Christopher`

### 12. `a3d50515-5f11-4a42-8a34-7a5c8c7b3e25` Motie: Motie van de leden Westerveld en Ceder over wetgeving en een uitvoeringsagenda om passend onderwijs te garanderen voor alle thuiszitt

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36663; meaning line ready; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Aangenomen.; Voor 111, Tegen 39
- **On:** ["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim in het funderend onderwijs en het beroepsonderwijs (Wet terugdringen
- **Area:** parental rights and education
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, FVD 10, BBB 3, ChristenUnie 3, DENK 3, PvdD 3, SP 3, 50PLUS 2, GroenLinks-PvdA 1, Volt 1. Tegen: PVV 19, JA21 9, Groep Markuszower 7, SGP 3 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36663 (enforcement of compulsory schooling, watched for its reach into exemptions and home education. 22 matched…); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z06357, 36663: CitizenGO's position on '["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim i
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `a3d50515-5f11-4a42-8a34-7a5c8c7b3e25` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm a3d50515-5f11-4a42-8a34-7a5c8c7b3e25 --by Christopher`

### 13. `ac610554-dfd6-498c-aaf9-709b1b693300` Wetgeving: Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim 

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36663; meaning line ready; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Aangenomen.; Voor 137, Tegen 13
- **On:** ["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim in het funderend onderwijs en het beroepsonderwijs (Wet terugdringen
- **Area:** parental rights and education
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, PVV 19, JA21 9, Groep Markuszower 7, BBB 3, ChristenUnie 3, DENK 3, PvdD 3, 50PLUS 2, GroenLinks-PvdA 1, Volt 1. Tegen: FVD 10, SGP 3, SP 3 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to pass 36663 (enforcement of compulsory schooling, watched for its reach into exemptions and home education. 22 matched…) as a whole; **Tegen** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2024Z19631, 36663: CitizenGO's position on '["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim i
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `ac610554-dfd6-498c-aaf9-709b1b693300` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm ac610554-dfd6-498c-aaf9-709b1b693300 --by Christopher`

### 14. `af4418a8-5524-4f69-ae39-296c81e4ab36` Motie: Gewijzigde motie van het lid Claassen over in wet- en regelgeving verduidelijken dat vrijstellingen op lichamelijke of psychische gro

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36663; meaning line ready; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Aangenomen.; Voor 103, Tegen 47
- **On:** ["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim in het funderend onderwijs en het beroepsonderwijs (Wet terugdringen
- **Area:** parental rights and education
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, PVV 19, Groep Markuszower 7, BBB 3, ChristenUnie 3, DENK 3, 50PLUS 2. Tegen: FVD 10, JA21 9, PvdD 3, SGP 3, SP 3, GroenLinks-PvdA 1, Volt 1 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36663 (enforcement of compulsory schooling, watched for its reach into exemptions and home education. 22 matched…); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z06410, 36663: CitizenGO's position on '["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim i
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `af4418a8-5524-4f69-ae39-296c81e4ab36` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm af4418a8-5524-4f69-ae39-296c81e4ab36 --by Christopher`

### 15. `c0087829-a008-41cf-91b0-8c4dfc3e12e5` Motie: Motie van het lid Ceder over jaarlijks in beeld brengen hoeveel kinderen en jongeren geen of geen volwaardig onderwijs krijgen

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36663; meaning line ready; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Verworpen.; Voor 59, Tegen 91
- **On:** ["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim in het funderend onderwijs en het beroepsonderwijs (Wet terugdringen
- **Area:** parental rights and education
- **Lobbies:** Voor: PVV 19, Groep Markuszower 7, ChristenUnie 3, DENK 3, PvdD 3, SP 3, GroenLinks-PvdA 1, Volt 1. Tegen: VVD 31, D66 29, CDA 20, FVD 10, JA21 9, BBB 3, SGP 3, 50PLUS 2 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36663 (enforcement of compulsory schooling, watched for its reach into exemptions and home education. 22 matched…); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z06356, 36663: CitizenGO's position on '["Wijziging van de Leerplichtwet 1969 en enige andere onderwijswetten in verband met het voorkomen en het terugdringen van verzuim i
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `c0087829-a008-41cf-91b0-8c4dfc3e12e5` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm c0087829-a008-41cf-91b0-8c4dfc3e12e5 --by Christopher`

### 16. `308c6fcb-4a64-424f-9e9f-eb6f13eae1d5` Motie: Motie van het lid Diederik van Dijk over de maatschappelijke dialoog over (on)vruchtbaarheid bevorderen

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36416; meaning line ready; this year.
- **When / result:** 2025-12-09; Tweede Kamer; Verworpen.; Voor 43, Tegen 107
- **On:** ["Voorstel van wet van de leden Paternotte en Bevers tot wijziging van de Embryowet in verband met de afschaffing van het tijdelijk verbod op het doen ontstaan van embryo’s voor wetenschappelijk onder
- **Area:** surrogacy and embryology
- **Lobbies:** Voor: PVV 19, FVD 10, BBB 3, ChristenUnie 3, SGP 3. Tegen: VVD 31, D66 29, CDA 20, JA21 9, DENK 3, PvdD 3, SP 3, 50PLUS 2, GroenLinks-PvdA 1, Volt 1 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36416 (Initiative bill (Paternotte, Bevers) lifting the temporary ban on creating embryos for research); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A motion tabled in the dossier of 36416 (against): its own text decides which side is ours, not the bill's direction. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `308c6fcb-4a64-424f-9e9f-eb6f13eae1d5` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 308c6fcb-4a64-424f-9e9f-eb6f13eae1d5 --by Christopher`

### 17. `450c9b10-7f4f-45a0-80b2-23889bdffe3a` Motie: Motie van het lid Krul c.s. over onderzoek naar alternatieven van onderzoek met speciaal daarvoor gekweekte embryo's langjarig door l

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill 36416; meaning line ready; this year.
- **When / result:** 2025-12-09; Tweede Kamer; Aangenomen.; Voor 127, Tegen 23
- **On:** ["Voorstel van wet van de leden Paternotte en Bevers tot wijziging van de Embryowet in verband met de afschaffing van het tijdelijk verbod op het doen ontstaan van embryo’s voor wetenschappelijk onder
- **Area:** surrogacy and embryology
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, PVV 19, FVD 10, JA21 9, BBB 3, ChristenUnie 3, DENK 3, SGP 3, SP 3, 50PLUS 2, Volt 1. Tegen: PvdD 3, GroenLinks-PvdA 1 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion 36416 (Initiative bill (Paternotte, Bevers) lifting the temporary ban on creating embryos for research); **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A motion tabled in the dossier of 36416 (against): its own text decides which side is ours, not the bill's direction. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `450c9b10-7f4f-45a0-80b2-23889bdffe3a` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 450c9b10-7f4f-45a0-80b2-23889bdffe3a --by Christopher`

### 18. `9a875c28-9d55-43ea-b17c-e8f8a4aa4967` Motie: Motie van de leden Ceder en Stoffer over een ambitieuze invulling van de rol van de speciaal gezant voor godsdienstvrijheid

- **Why first (72 points):** a vote on the whole text; the last such vote on its bill; tier 1; close-ish: 79-71; meaning line quotes the source; this year.
- **When / result:** 2026-04-07; Tweede Kamer; Aangenomen.; Voor 79, Tegen 71
- **On:** ["Vaststelling van de begrotingsstaat van het Ministerie van Buitenlandse Zaken (V) voor het jaar 2026"]
- **Area:** religious freedom
- **Lobbies:** Voor: VVD 31, D66 29, CDA 20, BBB 3, ChristenUnie 3, SGP 3, 50PLUS 2, Volt 1. Tegen: PVV 19, FVD 10, JA21 9, Groep Markuszower 7, DENK 3, PvdD 3, SP 3, GroenLinks-PvdA 1 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion “Motie: Motie van de leden Ceder en Stoffer over een ambitieuze invulling van de rol van…”; **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z06858, 36800-V: CitizenGO's position on '["Vaststelling van de begrotingsstaat van het Ministerie van Buitenlandse Zaken (V) voor het jaar 2026"]' needs a human reading. A
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `9a875c28-9d55-43ea-b17c-e8f8a4aa4967` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 9a875c28-9d55-43ea-b17c-e8f8a4aa4967 --by Christopher`

### 19. `54eb8375-3cf8-4da8-b6df-67a3ea0aa3e8` Motie: Motie van het lid Tijs van den Brink over de minimumleeftijd ook voor sekswerk verhogen naar 21 jaar

- **Why first (71 points):** a vote on the whole text; the last such vote on its bill; tier 1; contested: 89-61; meaning line quotes the source; recent.
- **When / result:** 2026-09-22; Tweede Kamer; Aangenomen.; Voor 89, Tegen 61
- **On:** ["Mensenhandel"]
- **Area:** prostitution and trafficking
- **Lobbies:** Voor: VVD 31, CDA 20, PVV 19, JA21 9, Groep Markuszower 7, BBB 3, ChristenUnie 3, DENK 3, SGP 3, 50PLUS 2. Tegen: D66 29, PRO 20, FVD 10, PvdD 3, SP 3, Volt 1 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion “Motie: Motie van het lid Tijs van den Brink over de minimumleeftijd ook voor sekswerk…”; **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z18349, 28638: CitizenGO's position on '["Mensenhandel"]' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `54eb8375-3cf8-4da8-b6df-67a3ea0aa3e8` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 54eb8375-3cf8-4da8-b6df-67a3ea0aa3e8 --by Christopher`

### 20. `80790582-ded3-450a-ba38-5c2db40d7382` Motie: Gewijzigde motie van het lid Ceder over inventariseren welke aanvullende maatregelen nodig zijn om de signalering, registratie, besch

- **Why first (71 points):** a vote on the whole text; the last such vote on its bill; tier 1; contested: 87-63; meaning line quotes the source; recent.
- **When / result:** 2026-09-22; Tweede Kamer; Aangenomen.; Voor 87, Tegen 63
- **On:** ["Rechtsstaat en Rechtsorde"]
- **Area:** prostitution and trafficking
- **Lobbies:** Voor: VVD 31, PRO 20, FVD 10, JA21 9, Groep Markuszower 7, BBB 3, ChristenUnie 3, DENK 3, PvdD 3, SGP 3, SP 3, 50PLUS 2, Volt 1. Tegen: D66 29, CDA 20, PVV 19 (counts include members DERIVED from their group's vote, X5)
- Meaning: **Voor** = to adopt the motion “Motie: Gewijzigde motie van het lid Ceder over inventariseren welke aanvullende…”; **Tegen** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 2026Z19475, 29279: CitizenGO's position on '["Rechtsstaat en Rechtsorde"]' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `80790582-ded3-450a-ba38-5c2db40d7382` in config/nl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc nl --confirm 80790582-ded3-450a-ba38-5c2db40d7382 --by Christopher`

## By area (rank in the whole list)

- **abortion** (3 waiting): #27 `9e23d9da-8587-4356-9717-452bd456a227` 2026-10-06, 63 pts; #44 `fd44bdac-3416-4671-b83e-5c7e3cf10451` 2026-06-02, 58 pts; #64 `8da3cb4b-a267-496a-a815-0269bd896dfc` 2026-06-02, 30 pts
- **gender medicine and children** (2 waiting): #51 `f7f12681-e8da-47a9-80a4-dd96ee6bb78b` 2026-04-07, 58 pts; #52 `95432988-c1b4-4bca-b10c-394a05c78b5a` 2026-03-10, 58 pts
- **sex-based rights** (4 waiting): #2 `65d66131-e28d-4817-bdc7-5c651e761f98` 2026-10-08, 95 pts; #41 `506b27d1-a7de-4ecd-b615-5802d9b3ae37` 2026-06-16, 58 pts; #51 `f7f12681-e8da-47a9-80a4-dd96ee6bb78b` 2026-04-07, 58 pts
- **parental rights and education** (18 waiting): #8 `46085a3e-ec40-488f-8dec-a2c33ee7180a` 2026-04-07, 75 pts; #9 `7fda9159-0202-48b9-959e-b1a256dfce72` 2026-04-07, 75 pts; #10 `85b66610-96c3-4a17-861b-5496a98a6799` 2026-04-07, 75 pts
- **free speech and civil liberties** (5 waiting): #41 `506b27d1-a7de-4ecd-b615-5802d9b3ae37` 2026-06-16, 58 pts; #45 `42e7902b-cea5-4fca-abb4-efce6b2c36ae` 2026-05-12, 58 pts; #46 `1e80a454-c86b-47a3-ba42-b3011cbf3462` 2026-04-21, 58 pts
- **religious freedom** (9 waiting): #18 `9a875c28-9d55-43ea-b17c-e8f8a4aa4967` 2026-04-07, 72 pts; #23 `554deeee-73fc-4ade-8444-bc1f8e94d870` 2026-02-04, 66 pts; #43 `0d48a664-8d9d-49ff-b7cd-7509faf14ef1` 2026-06-11, 58 pts
- **marriage and family** (2 waiting): #22 `3d482c1d-5a9c-4b42-9bab-09988f57997d` 2026-06-02, 66 pts; #42 `98b7ea91-7600-4791-a8d2-7b1544cccd03` 2026-06-16, 58 pts
- **surrogacy and embryology** (27 waiting): #1 `6e41ea31-2a9d-43d6-bf62-95abf4300314` 2025-12-16, 101 pts; #3 `1f870bad-d142-455d-8fb2-7e99a5db09e3` 2025-12-09, 95 pts; #4 `99306983-cd0d-4e47-83e6-99699d4cf2be` 2026-06-02, 80 pts
- **migration** (122 waiting): #82 `3d25b030-97a4-470f-b995-995a515f73a4` 2026-10-06, 13 pts; #86 `a77a8f88-5161-436c-b882-108589699648` 2026-10-06, 13 pts; #93 `7f81ed35-6d06-438a-9c2f-8903f6c1ca3f` 2026-06-30, -22 pts
- **prostitution and trafficking** (30 waiting): #5 `2f39fc12-c53b-42f8-bc88-a8a4ca292781` 2026-09-22, 77 pts; #19 `54eb8375-3cf8-4da8-b6df-67a3ea0aa3e8` 2026-09-22, 71 pts; #20 `80790582-ded3-450a-ba38-5c2db40d7382` 2026-09-22, 71 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

