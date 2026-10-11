# Brazil 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 13 readings waiting in `config/br_stance.yaml` (2 proposed, 5 procedural, 6 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-br-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc br --confirm camara-2351506-122 camara-2351506-104 camara-2351506-95 camara-543252-45 camara-2351506-102 camara-346155-136 camara-2351506-34 --by Christopher

## Top 13

### 1. `camara-2351506-122` Aprovada, em segundo turno, a Proposta de Emenda à Constituição n° 5, de 2023. Sim: 368; Não: 96; Abstenção: 7; Total: 471.

- **Why first (113 points):** a vote on the whole text; the last such vote on its bill; watched bill PEC 5/2023; values proposed: one tick to sign; split MDB, PCdoB, PDT, PP and 5 more (17 against their group); meaning line ready; this year.
- **When / result:** 2026-05-28; Câmara; approved; Sim 368, Não 96, Abstain 8
- **On:** Acrescenta § 4º-A ao art. 150 da Constituição Federal, para dispor sobre a imunidade tributária de que tratam as suas alíneas “b” e “c” do inciso VI.
- **Area:** religious freedom
- **Lobbies:** Sim: PL 95, UNIÃO 42, PSD 42, REPUBLICANOS 40, PP 37, MDB 30, PODE 26, PSDB 17, PSB 11, PDT 7, SOLIDARIEDADE 6, AVANTE 5, NOVO 4, PCdoB 3, PV 1, CIDADANIA 1, PRD 1. Não: PT 60, PSOL 11, PCdoB 5, PV 5, PSB 3, MDB 3, PSD 2, UNIÃO 2, PP 1, PSDB 1, REDE 1, MISSÃO 1, PDT 1. Abstain: REDE 2, PT 2, PSB 1, 
- Meaning: **Sim** = to approve PEC 5/2023 (Extends tax immunity for religious organisations (art. 150 of the Constitution)) in the second and final round; **Não** = against approving it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Sim +2, Não -2
  - Voted Sim on PEC 5/2023 (Extends tax immunity for religious organisations (art): for passing it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc br --confirm camara-2351506-122 --by Christopher`

### 2. `camara-2351506-104` Aprovada, em primeiro turno, a Proposta de Emenda à Constituição nº 5, de 2023, na forma da Emenda Aglutinativa Substitutiva nº 3. Sim: 385;

- **Why first (103 points):** a vote on the whole text; watched bill PEC 5/2023; values proposed: one tick to sign; split MDB, PCdoB, PDT, PP and 5 more (17 against their group); meaning line ready; this year.
- **When / result:** 2026-05-28; Câmara; approved; Sim 385, Não 93, Abstain 8
- **On:** Acrescenta § 4º-A ao art. 150 da Constituição Federal, para dispor sobre a imunidade tributária de que tratam as suas alíneas “b” e “c” do inciso VI.
- **Area:** religious freedom
- **Lobbies:** Sim: PL 96, PSD 46, UNIÃO 45, REPUBLICANOS 42, PP 37, MDB 31, PODE 26, PSDB 16, PSB 12, PDT 8, SOLIDARIEDADE 6, NOVO 5, AVANTE 5, PCdoB 4, CIDADANIA 2, PRD 2, PV 1, PT 1. Não: PT 58, PSOL 12, PCdoB 5, PV 5, MDB 4, PSB 3, PP 1, PSD 1, PSDB 1, REDE 1, MISSÃO 1, PDT 1. Abstain: REDE 2, PT 2, PSB 1, PCd
- Meaning: **Sim** = to approve PEC 5/2023 (Extends tax immunity for religious organisations (art. 150 of the Constitution)) in the first round; **Não** = against approving it in the first round. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Sim +2, Não -2
  - Voted Sim on PEC 5/2023 (Extends tax immunity for religious organisations (art): for passing it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc br --confirm camara-2351506-104 --by Christopher`

### 3. `camara-2351506-108` Mantido o texto. Sim: 340; Não: 110; Abstenção: 7; Total: 457.

- **Why first (50 points):** amendment-level (lower); watched bill PEC 5/2023; split CIDADANIA, MDB, PCdoB, PDT and 6 more (32 against their group); meaning line ready; this year.
- **When / result:** 2026-05-28; Câmara; Sim 340, Não 110, Abstain 8
- **On:** Acrescenta § 4º-A ao art. 150 da Constituição Federal, para dispor sobre a imunidade tributária de que tratam as suas alíneas “b” e “c” do inciso VI.
- **Area:** religious freedom
- **Lobbies:** Sim: PL 92, PSD 42, REPUBLICANOS 38, UNIÃO 37, PP 35, PODE 26, MDB 17, PSDB 15, PSB 12, PDT 7, SOLIDARIEDADE 5, AVANTE 5, NOVO 4, PCdoB 2, CIDADANIA 1, PRD 1, PV 1. Não: PT 55, MDB 14, PSOL 12, PCdoB 8, PSD 4, PV 4, PSB 3, PP 3, PSDB 2, CIDADANIA 1, REDE 1, MISSÃO 1, PDT 1, UNIÃO 1. Abstain: REDE 2,
- Meaning: **Sim** = to keep the challenged part of PEC 5/2023 (Extends tax immunity for religious organisations (art. 150 of the Constitution)) as drafted; **Não** = to strike the challenged part out. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Mantido o texto. Sim: 340; Não: 110; Abstenção: 7; Total: 457.'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-2351506-108` in config/br_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc br --confirm camara-2351506-108 --by Christopher`

### 4. `camara-2351506-112` Mantido o texto. Sim: 342; Não: 113; Abstenção: 5; Total: 460.

- **Why first (50 points):** amendment-level (lower); watched bill PEC 5/2023; split CIDADANIA, MDB, PCdoB, PDT and 5 more (32 against their group); meaning line ready; this year.
- **When / result:** 2026-05-28; Câmara; Sim 342, Não 113, Abstain 6
- **On:** Acrescenta § 4º-A ao art. 150 da Constituição Federal, para dispor sobre a imunidade tributária de que tratam as suas alíneas “b” e “c” do inciso VI.
- **Area:** religious freedom
- **Lobbies:** Sim: PL 92, PSD 41, UNIÃO 39, REPUBLICANOS 38, PP 37, PODE 26, MDB 17, PSDB 14, PSB 11, PDT 7, SOLIDARIEDADE 6, AVANTE 5, NOVO 4, PCdoB 2, PV 1, CIDADANIA 1, PRD 1. Não: PT 59, MDB 15, PSOL 12, PCdoB 6, PSD 5, PV 5, PSB 3, PP 2, PSDB 2, CIDADANIA 1, REDE 1, MISSÃO 1, PDT 1. Abstain: REDE 2, PSB 1, P
- Meaning: **Sim** = to keep the challenged part of PEC 5/2023 (Extends tax immunity for religious organisations (art. 150 of the Constitution)) as drafted; **Não** = to strike the challenged part out. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Mantido o texto. Sim: 342; Não: 113; Abstenção: 5; Total: 460.'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-2351506-112` in config/br_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc br --confirm camara-2351506-112 --by Christopher`

### 5. `camara-2351506-115` Mantido o texto. Sim: 335; Não: 117; Abstenção: 5; Total: 457.

- **Why first (50 points):** amendment-level (lower); watched bill PEC 5/2023; split MDB, PCdoB, PDT, PP and 3 more (32 against their group); meaning line ready; this year.
- **When / result:** 2026-05-28; Câmara; Sim 335, Não 117, Abstain 6
- **On:** Acrescenta § 4º-A ao art. 150 da Constituição Federal, para dispor sobre a imunidade tributária de que tratam as suas alíneas “b” e “c” do inciso VI.
- **Area:** religious freedom
- **Lobbies:** Sim: PL 92, UNIÃO 42, PSD 40, REPUBLICANOS 37, PP 35, PODE 26, MDB 15, PSDB 13, PSB 10, PDT 7, SOLIDARIEDADE 5, AVANTE 5, NOVO 4, PCdoB 2, CIDADANIA 1, PRD 1. Não: PT 60, MDB 17, PSOL 12, PCdoB 7, PSD 5, PV 5, PSB 4, PSDB 3, PP 2, REDE 1, PDT 1. Abstain: REDE 2, PSB 1, PT 1, MDB 1
- Meaning: **Sim** = to keep the challenged part of PEC 5/2023 (Extends tax immunity for religious organisations (art. 150 of the Constitution)) as drafted; **Não** = to strike the challenged part out. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Mantido o texto. Sim: 335; Não: 117; Abstenção: 5; Total: 457.'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-2351506-115` in config/br_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc br --confirm camara-2351506-115 --by Christopher`

### 6. `camara-543252-60` Aprovado o Parecer com o seguinte resultado: 35 votos "Sim", 15 votos "Não". Quórum de votação: 50 votos, apresentou voto em separado o Depu

- **Why first (34 points):** watched bill PEC 164/2012; split MDB, PSD, PT, UNIÃO (4 against their group).
- **When / result:** 2024-11-27; Câmara; approved; Sim 35, Não 15
- **On:** Dá nova redação ao caput do art. 5º da Constituição Federal.
- **Area:** abortion
- **Lobbies:** Sim: PL 12, UNIÃO 8, REPUBLICANOS 4, PSD 4, MDB 3, PODE 2, NOVO 1, PT 1. Não: PT 6, PCdoB 2, PSOL 2, UNIÃO 1, PV 1, MDB 1, PSD 1, AVANTE 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Aprovado o Parecer com o seguinte resultado: 35 votos "Sim", 15 votos "Não". Quórum de votação: 50 votos, apresentou vot'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-543252-60` in config/br_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc br --confirm camara-543252-60 --by Christopher`

### 7. `camara-2351506-95` Rejeitado o Requerimento. Sim: 102; Não: 322; Abstenção: 1; Total: 425.

- **Why first (27 points):** procedural (lower); watched bill PEC 5/2023; split MDB, PDT, PL, PP and 3 more (15 against their group); meaning line ready; this year.
- **When / result:** 2026-05-28; Câmara; rejected; Sim 102, Não 322, Abstain 2
- **On:** Acrescenta § 4º-A ao art. 150 da Constituição Federal, para dispor sobre a imunidade tributária de que tratam as suas alíneas “b” e “c” do inciso VI.
- **Area:** religious freedom
- **Lobbies:** Sim: PT 57, PSOL 12, PCdoB 10, PV 5, PSB 3, PP 3, PSD 3, REDE 2, PDT 2, MDB 2, PL 1, REPUBLICANOS 1, MISSÃO 1. Não: PL 87, PSD 39, REPUBLICANOS 38, UNIÃO 37, PP 28, MDB 25, PODE 23, PSDB 17, PSB 9, SOLIDARIEDADE 5, AVANTE 5, NOVO 4, PDT 3, CIDADANIA 1, PRD 1. Abstain: MDB 1
- Meaning: **Sim** = to approve a procedural request (requerimento) on PEC 5/2023 (Extends tax immunity for religious organisations (art. 150 of the Constitution)); **Não** = against the request. _(by rule, from the vote's wording and the bill)_
- **Proposed:** procedural: evidence only, places nobody (Procedural (Rejeitado o Requerimento. Sim: 102; Não: 322; Abstenção: 1; Total: 425.): it decides the timetable or the handling, not the substance, so neither lo)
- **Sign:** `python3 tools/country_5ca.py --cc br --confirm camara-2351506-95 --by Christopher`

### 8. `camara-2310837-8` Aprovado o Requerimento de Urgência (Art. 154 do RICD). Sim: 238; não: 192; total: 430.

- **Why first (16 points):** amendment-level (lower); watched bill PL 2630/2020; contested: 238-192; meaning line quotes the source.
- **When / result:** 2023-04-25; Câmara; approved; Sim 238, Não 192, Abstain 1
- **On:** Institui a Lei Brasileira de Liberdade, Responsabilidade e Transparência na Internet.
- **Area:** free speech and civil liberties
- Meaning: **Sim** = to adopt the amendment or part put to the vote (“Aprovado o Requerimento de Urgência (Art. 154 do RICD). Sim: 238…”) on PL 2630/2020 (platform regulation); **Não** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Aprovado o Requerimento de Urgência (Art. 154 do RICD). Sim: 238; não: 192; total: 430.'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-2310837-8` in config/br_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc br --confirm camara-2310837-8 --by Christopher`

### 9. `camara-346155-112` Aprovado o Parecer com Complementação de Voto, com Substitutivo, com o seguinte resultado: 12 votos "Sim", 5 votos "Não". Quórum de votação:

- **Why first (15 points):** watched bill PL 580/2007.
- **When / result:** 2023-10-10; Câmara; approved; Sim 12, Não 5
- **On:** Altera a Lei nº 10.406, de 10 de janeiro de 2002 - Código Civil, para dispor sobre o contrato civil de união homoafetiva.
- **Area:** marriage and family
- **Lobbies:** Sim: PL 7, REPUBLICANOS 2, AVANTE 1, UNIÃO 1, PP 1. Não: PT 2, PSOL 2, PSD 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Aprovado o Parecer com Complementação de Voto, com Substitutivo, com o seguinte resultado: 12 votos "Sim", 5 votos "Não"'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-346155-112` in config/br_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc br --confirm camara-346155-112 --by Christopher`

### 10. `camara-543252-45` Rejeitado o Requerimento de Retirada de Pauta. Resultado: 13 votos "Sim", 34 votos "Não". Quórum de votação: 47 votos e 1 obstrução.

- **Why first (7 points):** procedural (lower); watched bill PEC 164/2012; split MDB, UNIÃO (2 against their group); meaning line ready.
- **When / result:** 2024-11-13; Câmara; rejected; Sim 13, Não 34
- **On:** Dá nova redação ao caput do art. 5º da Constituição Federal.
- **Area:** abortion
- **Lobbies:** Sim: PT 5, PCdoB 2, PSOL 2, UNIÃO 1, PV 1, MDB 1, AVANTE 1. Não: PL 13, UNIÃO 7, REPUBLICANOS 4, PP 4, MDB 2, PODE 2, PSD 2
- Meaning: **Sim** = to approve a procedural request (requerimento) on PEC 164/2012 (inviolability of the right to life from conception, in the head of art. 5); **Não** = against the request. _(by rule, from the vote's wording and the bill)_
- **Proposed:** procedural: evidence only, places nobody (Procedural (Rejeitado o Requerimento de Retirada de Pauta. Resultado: 13 votos "Sim", 34 votos "Não". Quórum de votação: 47 votos e ): it decides the timetable )
- **Sign:** `python3 tools/country_5ca.py --cc br --confirm camara-543252-45 --by Christopher`

### 11. `camara-2351506-102` Aprovada a preferência. Sim: 467; Não: 4; Abstenção: 1; Total: 472.

- **Why first (0 points):** procedural (lower); watched bill PEC 5/2023; near-unanimous (467-4, lower); split PCdoB, PDT, PSB (3 against their group); meaning line ready; this year.
- **When / result:** 2026-05-28; Câmara; approved; Sim 467, Não 4, Abstain 2
- **On:** Acrescenta § 4º-A ao art. 150 da Constituição Federal, para dispor sobre a imunidade tributária de que tratam as suas alíneas “b” e “c” do inciso VI.
- **Area:** religious freedom
- **Lobbies:** Sim: PL 96, PT 56, PSD 46, UNIÃO 44, REPUBLICANOS 40, PP 37, MDB 32, PODE 26, PSDB 18, PSB 15, PSOL 12, PCdoB 10, PDT 7, SOLIDARIEDADE 6, PV 6, AVANTE 5, NOVO 4, REDE 3, CIDADANIA 2, PRD 2. Não: MISSÃO 1, PCdoB 1, PDT 1, PSB 1. Abstain: PSB 1
- Meaning: **Sim** = to agree the procedural motion (“Aprovada a preferência. Sim: 467; Não: 4; Abstenção: 1…”) on PEC 5/2023 (Extends tax immunity for religious organisations (art. 150 of the Constitution)): the handling, not the substance; **Não** = against that procedural motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** procedural: evidence only, places nobody (Procedural (Aprovada a preferência. Sim: 467; Não: 4; Abstenção: 1; Total: 472.): it decides the timetable or the handling, not the substance, so neither lobby )
- **Sign:** `python3 tools/country_5ca.py --cc br --confirm camara-2351506-102 --by Christopher`

### 12. `camara-346155-136` Rejeitado o Requerimento de Retirada de Pauta. Resultado: 2 votos "Sim", 9 votos "Não". Quórum de votação: 11 votos.

- **Why first (-5 points):** procedural (lower); watched bill PL 580/2007; meaning line ready.
- **When / result:** 2024-08-13; Câmara; rejected; Sim 2, Não 9
- **On:** Altera a Lei nº 10.406, de 10 de janeiro de 2002 - Código Civil, para dispor sobre o contrato civil de união homoafetiva.
- **Area:** marriage and family
- **Lobbies:** Sim: PL 2. Não: PT 4, PSOL 4, PCdoB 1
- Meaning: **Sim** = to approve a procedural request (requerimento) on PL 580/2007 (Civil contract of 'união homoafetiva'; PL 5167/2009 was attached to it); **Não** = against the request. _(by rule, from the vote's wording and the bill)_
- **Proposed:** procedural: evidence only, places nobody (Procedural (Rejeitado o Requerimento de Retirada de Pauta. Resultado: 2 votos "Sim", 9 votos "Não". Quórum de votação: 11 votos.): it decides the timetable or t)
- **Sign:** `python3 tools/country_5ca.py --cc br --confirm camara-346155-136 --by Christopher`

### 13. `camara-2351506-34` Rejeitado o Requerimento de Retirada de Pauta. Resultado: 1 voto "Sim", 39 votos "Não". Quórum de votação: 40 votos.

- **Why first (-17 points):** procedural (lower); watched bill PEC 5/2023; near-unanimous (1-39, lower); split PSOL (1 against their group); meaning line ready.
- **When / result:** 2023-09-19; Câmara; rejected; Sim 1, Não 39
- **On:** Acrescenta § 4º-A ao art. 150 da Constituição Federal, para dispor sobre a imunidade tributária de que tratam as suas alíneas “b” e “c” do inciso VI.
- **Area:** religious freedom
- **Lobbies:** Sim: PSOL 1. Não: PL 12, PT 6, UNIÃO 4, REPUBLICANOS 4, MDB 3, PSD 3, NOVO 2, PP 1, PSB 1, PODE 1, PSOL 1, AVANTE 1
- Meaning: **Sim** = to approve a procedural request (requerimento) on PEC 5/2023 (Extends tax immunity for religious organisations (art. 150 of the Constitution)); **Não** = against the request. _(by rule, from the vote's wording and the bill)_
- **Proposed:** procedural: evidence only, places nobody (Procedural (Rejeitado o Requerimento de Retirada de Pauta. Resultado: 1 voto "Sim", 39 votos "Não". Quórum de votação: 40 votos.): it decides the timetable or t)
- **Sign:** `python3 tools/country_5ca.py --cc br --confirm camara-2351506-34 --by Christopher`

## By area (rank in the whole list)

- **abortion** (2 waiting): #6 `camara-543252-60` 2024-11-27, 34 pts; #10 `camara-543252-45` 2024-11-13, 7 pts
- **free speech and civil liberties** (1 waiting): #8 `camara-2310837-8` 2023-04-25, 16 pts
- **religious freedom** (8 waiting): #1 `camara-2351506-122` 2026-05-28, 113 pts; #2 `camara-2351506-104` 2026-05-28, 103 pts; #3 `camara-2351506-108` 2026-05-28, 50 pts
- **marriage and family** (2 waiting): #9 `camara-346155-112` 2023-10-10, 15 pts; #12 `camara-346155-136` 2024-08-13, -5 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

