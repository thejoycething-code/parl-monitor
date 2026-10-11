# Italy 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 137 readings waiting in `config/it_stance.yaml` (9 proposed, 1 procedural, 127 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-it-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc it --confirm senato-19-423-1 senato-19-232-24 camera-vs19_563_004 senato-19-424-16 camera-vs19_147_042 camera-vs19_563_003 senato-19-232-1 camera-vs19_141_013 senato-19-424-1 --by Christopher

## Top 20

### 1. `senato-19-423-1` Votazione questione sospensiva

- **Why first (93 points):** a motion to reject the text; the last such vote on its bill; watched bill 19/S.104; values proposed: one tick to sign; contested: 88-59; meaning line ready; this year.
- **When / result:** 2026-06-03; Senato; approvato; Favorevole 88, Contrario 59
- **On:** Disposizioni in materia di morte volontaria medicalmente assistita
- **Area:** assisted dying
- **Lobbies:** Favorevole: FdI 49, LSP-PSd'Az 19, FI-BP-PPE 13, Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP 7. Contrario: PD-IDP 27, M5S 20, IV-CR 6, Aut (SVP-PATT, Cb) 4, Misto 2
- Meaning: **Favorevole** = to reject 19/S.104 (Morte volontaria medicalmente assistita (Bazoli and others), in committee since the start of the legislature) outright at this stage (a motion to reject); **Contrario** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Favorevole +2, Contrario -2
  - Voted Favorevole on 19/S.104 (Morte volontaria medicalmente assistita (Bazoli and others), in committee since the start ): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm senato-19-423-1 --by Christopher`

### 2. `senato-19-232-24` Votazione finale

- **Why first (89 points):** a vote on the whole text; the last such vote on its bill; watched bill 19/S.824; values proposed: one tick to sign; contested: 84-58; split Misto (1 against their group); meaning line quotes the source.
- **When / result:** 2024-10-16; Senato; approvato; Favorevole 84, Contrario 58
- **On:** Modifica alla legge 19 febbraio 2004, n. 40, in materia di reato di surrogazione di maternità commesso all'estero
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: FdI 52, LSP-PSd'Az 16, FI-BP-PPE 11, Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP 4, Misto 1. Contrario: PD-IDP 23, M5S 20, Misto 5, IV-CR 5, Aut (SVP-PATT, Cb) 5
- Meaning: **Favorevole** = to pass the text “Modifica alla legge 19 febbraio 2004, n. 40, in materia di reato di surrogazione di…” as a whole; **Contrario** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Favorevole +2, Contrario -2
  - Voted Favorevole on 19/S.824 (The same bill at the Senate): for passing it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm senato-19-232-24 --by Christopher`

### 3. `camera-vs19_563_004` DDL 2423-A E AB - Q PREG MERITO N 1 - Votazione

- **Why first (85 points):** a motion to reject the text; the last such vote on its bill; watched bill 19/C.2423; values proposed: one tick to sign; meaning line ready; this year.
- **When / result:** 2025-11-11; Camera; Respinta
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- Meaning: **Favorevole** = to reject 19/C.2423 (parents' prior consent to sex and relationships education in schools, the government bill (Valditara)) outright at this stage (a motion to reject); **Contrario** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Favorevole -2, Contrario +2
  - Voted Favorevole on 19/C.2423 (Consenso informato in ambito scolastico: parents' prior consent to sex and relationships e): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm camera-vs19_563_004 --by Christopher`

### 4. `senato-19-424-16` Votazione finale

- **Why first (83 points):** a vote on the whole text; the last such vote on its bill; watched bill 19/S.1735; values proposed: one tick to sign; meaning line quotes the source; this year.
- **When / result:** 2026-06-04; Senato; approvato; Favorevole 78, Contrario 38
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- **Lobbies:** Favorevole: FdI 49, LSP-PSd'Az 15, FI-BP-PPE 12, Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP 2. Contrario: PD-IDP 18, M5S 13, Misto 3, IV-CR 3, Aut (SVP-PATT, Cb) 1
- Meaning: **Favorevole** = to pass the text “Disposizioni in materia di consenso informato in ambito scolastico” as a whole; **Contrario** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Favorevole +2, Contrario -2
  - Voted Favorevole on 19/S.1735 (The same bill at the Senate, presented 4 December 2025; the Senate's record says 'appr): for passing it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm senato-19-424-16 --by Christopher`

### 5. `camera-vs19_147_042` Maternità surrogata reato universale

- **Why first (79 points):** a vote on the whole text; the last such vote on its bill; watched bill 19/C.887; values proposed: one tick to sign; split AZ-PER-RE, MISTO (6 against their group).
- **When / result:** 2023-07-26; Camera; Approvata; Favorevole 166, Contrario 109, Abstain 4
- **On:** Modifica all'articolo 12 della legge 19 febbraio 2004, n. 40, in materia di perseguibilità del reato di surrogazione di maternità commesso all'estero da cittadino italiano
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: FDI 92, LEGA 37, FI-PPE 24, NM(N-C-U-I)-M 7, AZ-PER-RE 5, MISTO 1. Contrario: PD-IDP 51, M5S 33, AVS 10, MISTO 8, AZ-PER-RE 7. Abstain: AZ-PER-RE 4
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** Favorevole +2, Contrario -2
  - Voted Favorevole on 19/C.887 (Surrogacy as a universal crime (reato universale), Camera reading, voted 26 July 2023. Its): for passing it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm camera-vs19_147_042 --by Christopher`

### 6. `camera-vs19_563_003` DDL 2423-A E AB - Q PREG COST 1,2,3 - Votazione

- **Why first (75 points):** a motion to reject the text; watched bill 19/C.2423; values proposed: one tick to sign; meaning line ready; this year.
- **When / result:** 2025-11-11; Camera; Respinta
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- Meaning: **Favorevole** = to reject 19/C.2423 (parents' prior consent to sex and relationships education in schools, the government bill (Valditara)) outright at this stage (a motion to reject); **Contrario** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Favorevole -2, Contrario +2
  - Voted Favorevole on 19/C.2423 (Consenso informato in ambito scolastico: parents' prior consent to sex and relationships e): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm camera-vs19_563_003 --by Christopher`

### 7. `senato-19-232-1` Votazione questione pregiudiziale

- **Why first (74 points):** a motion to reject the text; watched bill 19/S.824; values proposed: one tick to sign; contested: 65-87; split Misto (1 against their group); meaning line quotes the source.
- **When / result:** 2024-10-16; Senato; respinto; Favorevole 65, Contrario 87
- **On:** Modifica alla legge 19 febbraio 2004, n. 40, in materia di reato di surrogazione di maternità commesso all'estero
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: PD-IDP 30, M5S 23, IV-CR 5, Misto 4, Aut (SVP-PATT, Cb) 3. Contrario: FdI 50, LSP-PSd'Az 18, FI-BP-PPE 13, Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP 5, Misto 1
- Meaning: **Favorevole** = to reject the text “Modifica alla legge 19 febbraio 2004, n. 40, in materia di reato di surrogazione di…” outright at this stage (a motion to reject); **Contrario** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Favorevole -2, Contrario +2
  - Voted Favorevole on 19/S.824 (The same bill at the Senate): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm senato-19-232-1 --by Christopher`

### 8. `camera-vs19_141_013` Questioni pregiudiziali di costituzionalità n. 1 GIANASSI FEDERICO (PD-IDP) ed altri e n. 2 MAGI RICCARDO (MISTO) e DELLA VEDOVA BENEDETTO (

- **Why first (73 points):** a motion to reject the text; watched bill 19/C.887; values proposed: one tick to sign; split AZ-PER-RE, MISTO (5 against their group); meaning line ready.
- **When / result:** 2023-07-18; Camera; Respinta; Favorevole 124, Contrario 187, Abstain 8
- **On:** Modifica all'articolo 12 della legge 19 febbraio 2004, n. 40, in materia di perseguibilità del reato di surrogazione di maternità commesso all'estero da cittadino italiano
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: PD-IDP 60, M5S 40, AZ-PER-RE 9, AVS 9, MISTO 6. Contrario: FDI 97, LEGA 48, FI-PPE 28, NM(N-C-U-I)-M 9, AZ-PER-RE 3, MISTO 2. Abstain: AZ-PER-RE 7, MISTO 1
- Meaning: **Favorevole** = to reject 19/C.887 (Surrogacy as a universal crime (reato universale), Camera reading, voted 26 July 2023) outright at this stage (a motion to reject); **Contrario** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Favorevole -2, Contrario +2
  - Voted Favorevole on 19/C.887 (Surrogacy as a universal crime (reato universale), Camera reading, voted 26 July 2023. Its): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm camera-vs19_141_013 --by Christopher`

### 9. `senato-19-424-1` Votazione questione pregiudiziale

- **Why first (68 points):** a motion to reject the text; watched bill 19/S.1735; values proposed: one tick to sign; meaning line quotes the source; this year.
- **When / result:** 2026-06-04; Senato; respinto; Favorevole 45, Contrario 74, Abstain 4
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- **Lobbies:** Favorevole: PD-IDP 23, M5S 18, Misto 2, Aut (SVP-PATT, Cb) 2. Contrario: FdI 47, LSP-PSd'Az 17, FI-BP-PPE 7, Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP 3. Abstain: IV-CR 4
- Meaning: **Favorevole** = to reject the text “Disposizioni in materia di consenso informato in ambito scolastico” outright at this stage (a motion to reject); **Contrario** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Favorevole -2, Contrario +2
  - Voted Favorevole on 19/S.1735 (The same bill at the Senate, presented 4 December 2025; the Senate's record says 'appr): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc it --confirm senato-19-424-1 --by Christopher`

### 10. `senato-19-232-5` Em. 1.9, Castellone e altri

- **Why first (28 points):** amendment-level (lower); watched bill 19/S.824; contested: 57-83; split FdI, Misto (2 against their group); meaning line quotes the source.
- **When / result:** 2024-10-16; Senato; respinto; Favorevole 57, Contrario 83, Abstain 5
- **On:** Modifica alla legge 19 febbraio 2004, n. 40, in materia di reato di surrogazione di maternità commesso all'estero
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: PD-IDP 23, M5S 22, IV-CR 4, Aut (SVP-PATT, Cb) 4, Misto 3, FdI 1. Contrario: FdI 49, LSP-PSd'Az 17, FI-BP-PPE 12, Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP 4, Misto 1. Abstain: Misto 3, PD-IDP 1, Aut (SVP-PATT, Cb) 1
- Meaning: **Favorevole** = to adopt amendment 1.9 to the text “Modifica alla legge 19 febbraio 2004, n. 40, in materia di reato di surrogazione di…”; **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Em. 1.9, Castellone e altri'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `senato-19-232-5` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm senato-19-232-5 --by Christopher`

### 11. `camera-vs19_147_031` Ordine del giorno n. 9/887 E ABB./6 RICCIARDI MARIANNA (M5S) - Votazione Ordine del giorno 9/887 E ABB./6 PDL n. 0887

- **Why first (27 points):** amendment-level (lower); watched bill 19/C.887; contested: 108-162; split AZ-PER-RE (2 against their group); meaning line ready.
- **When / result:** 2023-07-26; Camera; Respinta; Favorevole 108, Contrario 162, Abstain 11
- **On:** Modifica all'articolo 12 della legge 19 febbraio 2004, n. 40, in materia di perseguibilità del reato di surrogazione di maternità commesso all'estero da cittadino italiano
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: PD-IDP 51, M5S 40, AVS 9, MISTO 5, AZ-PER-RE 3. Contrario: FDI 89, LEGA 42, FI-PPE 23, NM(N-C-U-I)-M 6, AZ-PER-RE 2. Abstain: AZ-PER-RE 8, MISTO 3
- Meaning: **Favorevole** = to adopt the order of the day 9 (a non-binding motion) on 19/C.887 (Surrogacy as a universal crime (reato universale), Camera reading, voted 26 July 2023); **Contrario** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Ordine del giorno n. 9/887 E ABB./6 RICCIARDI MARIANNA (M5S) - Votazione Ordine del giorno 9/887 E ABB./6 PDL n. 0887'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_147_031` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_147_031 --by Christopher`

### 12. `camera-vs19_147_004` Emendamento 1.1025 ZAN ALESSANDRO (PD-IDP) - Votazione Emendamento 1.1025 PDL n. 0887

- **Why first (26 points):** amendment-level (lower); watched bill 19/C.887; split AVS, AZ-PER-RE (11 against their group); meaning line ready.
- **When / result:** 2023-07-26; Camera; Respinta; Favorevole 109, Contrario 184, Abstain 4
- **On:** Modifica all'articolo 12 della legge 19 febbraio 2004, n. 40, in materia di perseguibilità del reato di surrogazione di maternità commesso all'estero da cittadino italiano
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: PD-IDP 51, M5S 40, AZ-PER-RE 7, MISTO 6, AVS 5. Contrario: FDI 92, LEGA 46, FI-PPE 27, AZ-PER-RE 9, NM(N-C-U-I)-M 6, AVS 4. Abstain: MISTO 3, AZ-PER-RE 1
- Meaning: **Favorevole** = to adopt amendment 1.1025 to 19/C.887 (Surrogacy as a universal crime (reato universale), Camera reading, voted 26 July 2023); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Emendamento 1.1025 ZAN ALESSANDRO (PD-IDP) - Votazione Emendamento 1.1025 PDL n. 0887'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_147_004` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_147_004 --by Christopher`

### 13. `camera-vs19_147_012` Emendamento 1.1010 MAGI RICCARDO (MISTO) - Votazione Emendamento 1.1010 PDL n. 0887

- **Why first (26 points):** amendment-level (lower); watched bill 19/C.887; split AVS, AZ-PER-RE (10 against their group); meaning line ready.
- **When / result:** 2023-07-26; Camera; Respinta; Favorevole 104, Contrario 175, Abstain 12
- **On:** Modifica all'articolo 12 della legge 19 febbraio 2004, n. 40, in materia di perseguibilità del reato di surrogazione di maternità commesso all'estero da cittadino italiano
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: PD-IDP 51, M5S 39, AZ-PER-RE 5, AVS 5, MISTO 4. Contrario: FDI 91, LEGA 43, FI-PPE 25, NM(N-C-U-I)-M 6, AVS 5, AZ-PER-RE 5. Abstain: AZ-PER-RE 8, MISTO 4
- Meaning: **Favorevole** = to adopt amendment 1.1010 to 19/C.887 (Surrogacy as a universal crime (reato universale), Camera reading, voted 26 July 2023); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Emendamento 1.1010 MAGI RICCARDO (MISTO) - Votazione Emendamento 1.1010 PDL n. 0887'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_147_012` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_147_012 --by Christopher`

### 14. `camera-vs19_147_014` Emendamento 1.15 D'ORSO VALENTINA (M5S) - Votazione Emendamento 1.15 PDL n. 0887

- **Why first (26 points):** amendment-level (lower); watched bill 19/C.887; contested: 118-162; split FI-PPE (1 against their group); meaning line ready.
- **When / result:** 2023-07-26; Camera; Respinta; Favorevole 118, Contrario 162, Abstain 7
- **On:** Modifica all'articolo 12 della legge 19 febbraio 2004, n. 40, in materia di perseguibilità del reato di surrogazione di maternità commesso all'estero da cittadino italiano
- **Area:** surrogacy and embryology
- **Lobbies:** Favorevole: PD-IDP 49, M5S 39, AZ-PER-RE 18, MISTO 6, AVS 5, FI-PPE 1. Contrario: FDI 87, LEGA 45, FI-PPE 24, NM(N-C-U-I)-M 6. Abstain: AVS 5, MISTO 2
- Meaning: **Favorevole** = to adopt amendment 1.15 to 19/C.887 (Surrogacy as a universal crime (reato universale), Camera reading, voted 26 July 2023); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Emendamento 1.15 D'ORSO VALENTINA (M5S) - Votazione Emendamento 1.15 PDL n. 0887'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_147_014` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_147_014 --by Christopher`

### 15. `camera-vs19_576_001` DDL 2423-A E ABB - EM 1.144 - Votazione

- **Why first (25 points):** amendment-level (lower); watched bill 19/C.2423; meaning line ready; this year.
- **When / result:** 2025-12-02; Camera; Respinta
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- Meaning: **Favorevole** = to adopt amendment 1 to 19/C.2423 (parents' prior consent to sex and relationships education in schools, the government bill (Valditara)); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('DDL 2423-A E ABB - EM 1.144 - Votazione'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_576_001` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_576_001 --by Christopher`

### 16. `camera-vs19_576_002` EM 1.1006 - Votazione

- **Why first (25 points):** amendment-level (lower); watched bill 19/C.2423; meaning line ready; this year.
- **When / result:** 2025-12-02; Camera; Respinta
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- Meaning: **Favorevole** = to adopt amendment 1 to 19/C.2423 (parents' prior consent to sex and relationships education in schools, the government bill (Valditara)); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('EM 1.1006 - Votazione'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_576_002` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_576_002 --by Christopher`

### 17. `camera-vs19_576_003` EM 1.145 - Votazione

- **Why first (25 points):** amendment-level (lower); watched bill 19/C.2423; meaning line ready; this year.
- **When / result:** 2025-12-02; Camera; Respinta
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- Meaning: **Favorevole** = to adopt amendment 1 to 19/C.2423 (parents' prior consent to sex and relationships education in schools, the government bill (Valditara)); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('EM 1.145 - Votazione'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_576_003` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_576_003 --by Christopher`

### 18. `camera-vs19_576_004` EM 1.149 - Votazione

- **Why first (25 points):** amendment-level (lower); watched bill 19/C.2423; meaning line ready; this year.
- **When / result:** 2025-12-02; Camera; Respinta
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- Meaning: **Favorevole** = to adopt amendment 1 to 19/C.2423 (parents' prior consent to sex and relationships education in schools, the government bill (Valditara)); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('EM 1.149 - Votazione'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_576_004` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_576_004 --by Christopher`

### 19. `camera-vs19_576_005` EM 1.158 - Votazione

- **Why first (25 points):** amendment-level (lower); watched bill 19/C.2423; meaning line ready; this year.
- **When / result:** 2025-12-02; Camera; Respinta
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- Meaning: **Favorevole** = to adopt amendment 1 to 19/C.2423 (parents' prior consent to sex and relationships education in schools, the government bill (Valditara)); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('EM 1.158 - Votazione'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_576_005` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_576_005 --by Christopher`

### 20. `camera-vs19_576_006` EM 1.164 - Votazione

- **Why first (25 points):** amendment-level (lower); watched bill 19/C.2423; meaning line ready; this year.
- **When / result:** 2025-12-02; Camera; Respinta
- **On:** Disposizioni in materia di consenso informato in ambito scolastico
- **Area:** parental rights and education
- Meaning: **Favorevole** = to adopt amendment 1 to 19/C.2423 (parents' prior consent to sex and relationships education in schools, the government bill (Valditara)); **Contrario** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('EM 1.164 - Votazione'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camera-vs19_576_006` in config/it_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc it --confirm camera-vs19_576_006 --by Christopher`

## By area (rank in the whole list)

- **assisted dying** (1 waiting): #1 `senato-19-423-1` 2026-06-03, 93 pts
- **parental rights and education** (61 waiting): #3 `camera-vs19_563_004` 2025-11-11, 85 pts; #4 `senato-19-424-16` 2026-06-04, 83 pts; #6 `camera-vs19_563_003` 2025-11-11, 75 pts
- **surrogacy and embryology** (66 waiting): #2 `senato-19-232-24` 2024-10-16, 89 pts; #5 `camera-vs19_147_042` 2023-07-26, 79 pts; #7 `senato-19-232-1` 2024-10-16, 74 pts
- **migration** (9 waiting): #129 `camera-vs19_702_053` 2026-08-03, -40 pts; #130 `camera-vs19_388_001` 2024-11-27, -49 pts; #131 `camera-vs19_482_086` 2025-05-20, -50 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

