# Switzerland 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 82 readings waiting in `config/ch_stance.yaml` (1 proposed, 0 procedural, 81 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-ch-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc ch --confirm nr-36076 --by Christopher

## Top 20

### 1. `nr-36076` Adopter le postulat

- **Why first (90 points):** a vote on the whole text; the last such vote on its bill; watched bill 25.4892; values proposed: one tick to sign; meaning line ready; this year.
- **When / result:** 2026-04-29; Nationalrat; Ja 129, Nein 57, Abstain 8
- **On:** Besserer Schutz Minderjähriger vor Online-Pornografie mittels verbindlicher Altersverifikation (z. B. durch E-ID)
- **Area:** parental rights and education, free speech and civil liberties
- **Lobbies:** Ja: S 40, M-E 30, RL 26, G 22, GL 11. Nein: V 57. Abstain: V 6, RL 1, M-E 1
- Meaning: **Ja** = to adopt the motion 25.4892 (Po. 25.4892 binding age verification against online pornography for minors); **Nein** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Ja +2, Nein -2
  - Voted Ja on 25.4892 (Po): for passing it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc ch --confirm nr-36076 --by Christopher`

### 2. `sr-7555` Schlussabstimmung

- **Why first (90 points):** a vote on the whole text; the last such vote on its bill; watched bill 24.026; close: 22-21; meaning line ready.
- **When / result:** 2025-06-20; Ständerat; Ja; Ja 22, Nein 21
- **On:** «Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bundesgesetz über die Individualbesteuerung)
- **Area:** marriage and family
- **Lobbies:** Ja: RL 10, S 8, G 3, GL 1. Nein: M-E 14, V 7
- Meaning: **Ja** = to pass 24.026 (BRG 24.026, the federal message on the popular initiative for marital-status-independent individual taxation…) as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.026: CitizenGO's position on '«Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bu' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7555` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7555 --by Christopher`

### 3. `sr-7645` Abstimmung über die Motion

- **Why first (89 points):** a vote on the whole text; the last such vote on its bill; watched bill 25.3944; contested: 16-22; split M-E, S, V (5 against their group); meaning line ready.
- **When / result:** 2025-09-11; Ständerat; nein; Ja 16, Nein 22, Abstain 6
- **On:** Rahmenregulierung im Bereich des assistierten Suizids
- **Area:** assisted dying
- **Lobbies:** Ja: M-E 11, S 4, V 1. Nein: RL 8, V 6, G 3, S 3, GL 1, M-E 1. Abstain: M-E 3, RL 3
- Meaning: **Ja** = to adopt the motion 25.3944 (Mo. 25.3944 Rahmenregulierung im Bereich des assistierten Suizids); **Nein** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 25.3944: CitizenGO's position on 'Rahmenregulierung im Bereich des assistierten Suizids' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7645` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7645 --by Christopher`

### 4. `nr-34676` Schlussabstimmung

- **Why first (80 points):** a vote on the whole text; watched bill 24.026; close: 101-93; meaning line ready.
- **When / result:** 2025-06-20; Nationalrat; Ja 101, Nein 93
- **On:** «Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bundesgesetz über die Individualbesteuerung)
- **Area:** marriage and family
- **Lobbies:** Ja: S 41, RL 26, G 23, GL 11. Nein: V 63, M-E 30
- Meaning: **Ja** = to pass 24.026 (BRG 24.026, the federal message on the popular initiative for marital-status-independent individual taxation…) as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.026: CitizenGO's position on '«Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bu' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-34676` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-34676 --by Christopher`

### 5. `nr-34677` Schlussabstimmung

- **Why first (80 points):** a vote on the whole text; watched bill 24.026; close: 101-93; meaning line ready.
- **When / result:** 2025-06-20; Nationalrat; Ja 101, Nein 93
- **On:** «Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bundesgesetz über die Individualbesteuerung)
- **Area:** marriage and family
- **Lobbies:** Ja: S 41, RL 26, G 23, GL 11. Nein: V 63, M-E 30
- Meaning: **Ja** = to pass 24.026 (BRG 24.026, the federal message on the popular initiative for marital-status-independent individual taxation…) as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.026: CitizenGO's position on '«Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bu' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-34677` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-34677 --by Christopher`

### 6. `sr-7554` Schlussabstimmung

- **Why first (80 points):** a vote on the whole text; watched bill 24.026; close: 22-21; meaning line ready.
- **When / result:** 2025-06-20; Ständerat; Ja; Ja 22, Nein 21
- **On:** «Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bundesgesetz über die Individualbesteuerung)
- **Area:** marriage and family
- **Lobbies:** Ja: RL 10, S 8, G 3, GL 1. Nein: M-E 14, V 7
- Meaning: **Ja** = to pass 24.026 (BRG 24.026, the federal message on the popular initiative for marital-status-independent individual taxation…) as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.026: CitizenGO's position on '«Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bu' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7554` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7554 --by Christopher`

### 7. `sr-7283` Gesamtabstimmung

- **Why first (80 points):** a vote on the whole text; watched bill 24.026; close: 23-21; meaning line ready.
- **When / result:** 2025-03-10; Ständerat; Ja; Ja 23, Nein 21
- **On:** «Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bundesgesetz über die Individualbesteuerung)
- **Area:** marriage and family
- **Lobbies:** Ja: RL 10, S 9, G 3, GL 1. Nein: M-E 14, V 7
- Meaning: **Ja** = to pass 24.026 (BRG 24.026, the federal message on the popular initiative for marital-status-independent individual taxation…) as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.026: CitizenGO's position on '«Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bu' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7283` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7283 --by Christopher`

### 8. `sr-7253` Abstimmung über das Eintreten

- **Why first (80 points):** a vote on the whole text; watched bill 24.026; close: 23-22; meaning line ready.
- **When / result:** 2025-03-04; Ständerat; Ja; Ja 23, Nein 22
- **On:** «Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bundesgesetz über die Individualbesteuerung)
- **Area:** marriage and family
- **Lobbies:** Ja: RL 10, S 9, G 3, GL 1. Nein: M-E 15, V 7
- Meaning: **Ja** = to enter into the matter on 24.026 (BRG 24.026, the federal message on the popular initiative for marital-status-independent individual taxation…), opening its detailed reading; **Nein** = against entering into it, which rejects it at this stage. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.026: CitizenGO's position on '«Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bu' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7253` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7253 --by Christopher`

### 9. `sr-7302` Abstimmung über die Motion

- **Why first (79 points):** a vote on the whole text; the last such vote on its bill; tier 1; close: 20-21; split M-E (6 against their group); meaning line quotes the source.
- **When / result:** 2025-03-13; Ständerat; Nein; Ja 20, Nein 21, Abstain 1
- **On:** Von Dänemark und Schweden lernen. Familiennachzug auf die Interessen der Schweiz ausrichten
- **Area:** marriage and family, migration
- **Lobbies:** Ja: RL 9, M-E 6, V 5. Nein: S 9, M-E 9, G 2, GL 1. Abstain: V 1
- Meaning: **Ja** = to adopt the motion “Von Dänemark und Schweden lernen. Familiennachzug auf die Interessen der Schweiz…”; **Nein** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.4444: CitizenGO's position on 'Von Dänemark und Schweden lernen. Familiennachzug auf die Interessen der Schweiz ausrichten' needs a human reading. Add a `bill_directions` li
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7302` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7302 --by Christopher`

### 10. `nr-35087` Antrag der Mehrheit und des Bundesrates (Ablehnung der Motion)

- **Why first (78 points):** a motion to reject the text; the last such vote on its bill; watched bill 25.3945; split M-E, V (4 against their group); meaning line ready; this year.
- **When / result:** 2025-12-01; Nationalrat; Ja 127, Nein 59, Abstain 5
- **On:** Durch ein Monitoring Klarheit im Bereich des assistierten Suizids schaffen
- **Area:** assisted dying
- **Lobbies:** Ja: V 60, S 39, RL 25, M-E 3. Nein: M-E 25, G 22, GL 11, V 1. Abstain: V 4, G 1
- Meaning: **Ja** = to reject 25.3945 (Mo. 25.3945 monitoring of assisted suicide; same two misses as 25.3944) outright at this stage (a motion to reject); **Nein** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A motion to reject the text (the sides are swapped), but no bill direction is on file for 25.3945: CitizenGO's position on 'Durch ein Monitoring Klarheit im Bereich des assistierten Suizids schaffen' needs a human reading. Add a `bill_directions` line or write
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-35087` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-35087 --by Christopher`

### 11. `nr-33375` Eintreten

- **Why first (78 points):** a vote on the whole text; watched bill 24.026; close: 99-90; split V (1 against their group); meaning line ready.
- **When / result:** 2024-09-25; Nationalrat; Ja 99, Nein 90, Abstain 4
- **On:** «Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bundesgesetz über die Individualbesteuerung)
- **Area:** marriage and family
- **Lobbies:** Ja: S 39, RL 28, G 22, GL 9, V 1. Nein: V 59, M-E 31. Abstain: V 4
- Meaning: **Ja** = to enter into the matter on 24.026 (BRG 24.026, the federal message on the popular initiative for marital-status-independent individual taxation…), opening its detailed reading; **Nein** = against entering into it, which rejects it at this stage. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.026: CitizenGO's position on '«Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bu' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-33375` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-33375 --by Christopher`

### 12. `sr-7646` Abstimmung über die Motion

- **Why first (75 points):** a vote on the whole text; watched bill 25.3945; contested: 24-17; split M-E, V (2 against their group); meaning line ready.
- **When / result:** 2025-09-11; Ständerat; ja; Ja 24, Nein 17, Abstain 3
- **On:** Durch ein Monitoring Klarheit im Bereich des assistierten Suizids schaffen
- **Area:** assisted dying
- **Lobbies:** Ja: M-E 12, S 7, G 3, GL 1, V 1. Nein: RL 10, V 6, M-E 1. Abstain: M-E 2, RL 1
- Meaning: **Ja** = to adopt the motion 25.3945 (Mo. 25.3945 monitoring of assisted suicide; same two misses as 25.3944); **Nein** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 25.3945: CitizenGO's position on 'Durch ein Monitoring Klarheit im Bereich des assistierten Suizids schaffen' needs a human reading. Add a `bill_directions` line or write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7646` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7646 --by Christopher`

### 13. `nr-33383` Gesamtabstimmung

- **Why first (75 points):** a vote on the whole text; watched bill 24.026; close: 98-93; meaning line ready.
- **When / result:** 2024-09-25; Nationalrat; Ja 98, Nein 93, Abstain 1
- **On:** «Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bundesgesetz über die Individualbesteuerung)
- **Area:** marriage and family
- **Lobbies:** Ja: S 39, RL 28, G 22, GL 9. Nein: V 63, M-E 30. Abstain: V 1
- Meaning: **Ja** = to pass 24.026 (BRG 24.026, the federal message on the popular initiative for marital-status-independent individual taxation…) as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.026: CitizenGO's position on '«Für eine zivilstandsunabhängige Individualbesteuerung (Steuergerechtigkeits-Initiative)». Volksinitiative und indirekter Gegenvorschlag (Bu' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-33383` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-33383 --by Christopher`

### 14. `sr-7917` Abstimmung über die Motion

- **Why first (58 points):** a vote on the whole text; the last such vote on its bill; tier 1; meaning line quotes the source; this year.
- **When / result:** 2025-12-10; Ständerat; ja; Ja 27, Nein 12, Abstain 1
- **On:** Kein Familiennachzug bei Stellvertreterehen
- **Area:** marriage and family, migration
- **Lobbies:** Ja: RL 11, M-E 10, V 6. Nein: S 8, G 3, GL 1. Abstain: M-E 1
- Meaning: **Ja** = to adopt the motion “Abstimmung über die Motion”; **Nein** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 25.4039: CitizenGO's position on 'Kein Familiennachzug bei Stellvertreterehen' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7917` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7917 --by Christopher`

### 15. `nr-32789` Gesamtabstimmung

- **Why first (51 points):** a vote on the whole text; tier 1; split M-E, V (15 against their group); meaning line quotes the source.
- **When / result:** 2024-06-06; Nationalrat; Ja 139, Nein 46, Abstain 7
- **On:** Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)
- **Area:** marriage and family
- **Lobbies:** Ja: S 40, M-E 28, RL 26, G 22, V 14, GL 9. Nein: V 45, M-E 1. Abstain: V 6, M-E 1
- Meaning: **Ja** = to pass the text “Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)” as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 17.523: CitizenGO's position on 'Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)' needs a human reading. Add a `bill_directions` line or write yea/nay here
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-32789` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-32789 --by Christopher`

### 16. `nr-33655` Gesamtabstimmung

- **Why first (48 points):** a vote on the whole text; tier 1; split V (5 against their group); meaning line quotes the source.
- **When / result:** 2024-12-09; Nationalrat; Ja 130, Nein 54
- **On:** Bundesgesetz über die Invalidenversicherung IVG (Intensive Frühintervention bei Autismus-Spektrum-Störungen, IFI). Änderung
- **Area:** abortion
- **Lobbies:** Ja: S 39, RL 27, M-E 27, G 23, GL 9, V 5. Nein: V 54
- Meaning: **Ja** = to pass the text “Bundesgesetz über die Invalidenversicherung IVG (Intensive Frühintervention bei…” as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.066: CitizenGO's position on 'Bundesgesetz über die Invalidenversicherung IVG (Intensive Frühintervention bei Autismus-Spektrum-Störungen, IFI). Änderung' needs a human read
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-33655` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-33655 --by Christopher`

### 17. `nr-32238` Eintreten

- **Why first (48 points):** a vote on the whole text; tier 1; split V (15 against their group); meaning line quotes the source.
- **When / result:** 2024-03-14; Nationalrat; Ja 138, Nein 47, Abstain 3
- **On:** Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)
- **Area:** marriage and family
- **Lobbies:** Ja: S 39, M-E 29, RL 25, G 22, V 15, GL 8. Nein: V 47. Abstain: V 3
- Meaning: **Ja** = to enter into the matter on the text “Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)”, opening its detailed reading; **Nein** = against entering into it, which rejects it at this stage. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 17.523: CitizenGO's position on 'Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)' needs a human reading. Add a `bill_directions` line or write yea/nay here
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-32238` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-32238 --by Christopher`

### 18. `nr-34216` Schlussabstimmung

- **Why first (47 points):** a vote on the whole text; tier 1; split V (3 against their group); meaning line quotes the source.
- **When / result:** 2025-03-21; Nationalrat; Ja 128, Nein 58, Abstain 5
- **On:** Bundesgesetz über die Invalidenversicherung IVG (Intensive Frühintervention bei Autismus-Spektrum-Störungen, IFI). Änderung
- **Area:** abortion
- **Lobbies:** Ja: S 38, M-E 29, RL 25, G 23, GL 10, V 3. Nein: V 58. Abstain: V 5
- Meaning: **Ja** = to pass the text “Bundesgesetz über die Invalidenversicherung IVG (Intensive Frühintervention bei…” as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 24.066: CitizenGO's position on 'Bundesgesetz über die Invalidenversicherung IVG (Intensive Frühintervention bei Autismus-Spektrum-Störungen, IFI). Änderung' needs a human read
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `nr-34216` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm nr-34216 --by Christopher`

### 19. `sr-8204` Schlussabstimmung

- **Why first (46 points):** a vote on the whole text; the last such vote on its bill; tier 1; near-unanimous (41-1, lower); split V (1 against their group); meaning line quotes the source; this year.
- **When / result:** 2026-03-20; Ständerat; ja; Ja 41, Nein 1, Abstain 1
- **On:** Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)
- **Area:** marriage and family
- **Lobbies:** Ja: M-E 14, RL 12, S 7, V 4, G 3, GL 1. Nein: V 1. Abstain: V 1
- Meaning: **Ja** = to pass the text “Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)” as a whole; **Nein** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 17.523: CitizenGO's position on 'Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)' needs a human reading. Add a `bill_directions` line or write yea/nay here
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-8204` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-8204 --by Christopher`

### 20. `sr-7705` Abstimmung über das Eintreten

- **Why first (43 points):** a vote on the whole text; tier 1; meaning line quotes the source.
- **When / result:** 2025-09-23; Ständerat; ja; Ja 35, Nein 7, Abstain 1
- **On:** Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)
- **Area:** marriage and family
- **Lobbies:** Ja: M-E 13, RL 10, S 8, G 3, GL 1. Nein: V 7. Abstain: M-E 1
- Meaning: **Ja** = to enter into the matter on the text “Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)”, opening its detailed reading; **Nein** = against entering into it, which rejects it at this stage. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 17.523: CitizenGO's position on 'Schweizerisches Zivilgesetzbuch (Doppelnamen bei der Eheschliessung)' needs a human reading. Add a `bill_directions` line or write yea/nay here
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sr-7705` in config/ch_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ch --confirm sr-7705 --by Christopher`

## By area (rank in the whole list)

- **abortion** (14 waiting): #16 `nr-33655` 2024-12-09, 48 pts; #18 `nr-34216` 2025-03-21, 47 pts; #29 `sr-7374` 2025-03-21, 38 pts
- **assisted dying** (3 waiting): #3 `sr-7645` 2025-09-11, 89 pts; #10 `nr-35087` 2025-12-01, 78 pts; #12 `sr-7646` 2025-09-11, 75 pts
- **parental rights and education** (1 waiting): #1 `nr-36076` 2026-04-29, 90 pts
- **free speech and civil liberties** (1 waiting): #1 `nr-36076` 2026-04-29, 90 pts
- **marriage and family** (55 waiting): #2 `sr-7555` 2025-06-20, 90 pts; #4 `nr-34676` 2025-06-20, 80 pts; #5 `nr-34677` 2025-06-20, 80 pts
- **migration** (11 waiting): #9 `sr-7302` 2025-03-13, 79 pts; #14 `sr-7917` 2025-12-10, 58 pts; #74 `sr-7166` 2024-12-18, -27 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

