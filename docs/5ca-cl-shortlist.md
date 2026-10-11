# Chile 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 5 readings waiting in `config/cl_stance.yaml` (0 proposed, 0 procedural, 5 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-cl-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

## Top 5

### 1. `camara-88946` Boletín N° 18216-05 Renovación de una indicación de la diputada Ana María Gazmuri para agregar un artículo nuevo permanente, de cuyo tenor d

- **Why first (40 points):** amendment-level (lower); tier 1; close-ish: 80-69; split IND, PDG, PSC, RN (12 against their group); meaning line quotes the source; this year.
- **When / result:** 2026-05-20; Cámara; Aprobado; Afirmativo 80, En contra 69, Abstain 4
- **On:** Para la reconstrucción nacional y el desarrollo económico y social
- **Area:** abortion
- **Lobbies:** Afirmativo: IND 17, FA 14, PDG 12, PS 10, PC 8, DC 7, PPD 4, PL 2, RN 2, PSC 1, PAH 1, ? 1, PR 1. En contra: PREP 28, UDI 12, RN 8, PNL 8, IND 8, PSC 2, EVOP 2, PDG 1. Abstain: DEM 1, PDG 1, RN 1, FRVS 1
- Meaning: **Afirmativo** = to adopt the amendment or part put to the vote (“Boletín N° 18216-05 Renovación de una indicación de la diputada Ana…”) on the text “Para la reconstrucción nacional y el desarrollo económico y social”; **En contra** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Boletín N° 18216-05 Renovación de una indicación de la diputada Ana María Gazmuri para agregar un artículo nuevo permane'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-88946` in config/cl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc cl --confirm camara-88946 --by Christopher`

### 2. `camara-90141` Boletín N° 18584-25 Indicación renovada de la diputada Schneider y los diputados Salinas, Pinilla y Araya, Jaime, para agregar un inciso fin

- **Why first (38 points):** amendment-level (lower); tier 1; close-ish: 63-70; split IND, PDG (11 against their group); meaning line quotes the source; recent.
- **When / result:** 2026-09-23; Cámara; Rechazado; Afirmativo 63, En contra 70, Abstain 1
- **On:** Modifica el Código Penal para ampliar el ámbito de aplicación del delito de interrupción u obstaculización de la libre circulación y del funcionamiento de los servicios de transporte
- **Area:** free speech and civil liberties
- **Lobbies:** Afirmativo: IND 13, FA 11, PDG 11, PS 8, DC 6, PC 6, PPD 3, PL 2, PAH 1, ? 1, PR 1. En contra: PREP 24, UDI 12, RN 10, IND 9, PNL 8, PCCH 2, EVOP 2, PDG 2, DEM 1. Abstain: IND 1
- Meaning: **Afirmativo** = to adopt the amendment or part put to the vote (“Boletín N° 18584-25 Indicación renovada de la diputada Schneider y…”) on the text “Modifica el Código Penal para ampliar el ámbito de aplicación del delito de interrupción…”; **En contra** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Boletín N° 18584-25 Indicación renovada de la diputada Schneider y los diputados Salinas, Pinilla y Araya, Jaime, para a'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-90141` in config/cl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc cl --confirm camara-90141 --by Christopher`

### 3. `senado-16709-f5b00dd9443e` Proyecto de ley, iniciado en Moción de los Honorables Senadores señoras Núñez y Órdenes, y señores Castro González, Gahona y Macaya, en prim

- **Why first (38 points):** a vote on the whole text; the last such vote on its bill; tier 1; near-unanimous (17-0, lower); meaning line quotes the source.
- **When / result:** 2025-01-29; Senado; Afirmativo 17, En contra 0
- **On:** Modifica la ley N° 20.418, que fija normas sobre información, orientación y prestaciones en materia de regulación de la fertilidad, para promover la información y educación sobre la infertilidad
- **Area:** parental rights and education, surrogacy and embryology
- **Lobbies:** Afirmativo: ? 6, U.D.I. 2, P.D.C. 2, Independiente 2, P.S. 1, R.N. 1, P.C 1, F.R.E.V.S. 1, Demócratas 1
- Meaning: **Afirmativo** = to pass the text “Modifica la ley N° 20.418, que fija normas sobre información, orientación y prestaciones…” as a whole; **En contra** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 16709-11: CitizenGO's position on 'Modifica la ley N° 20.418, que fija normas sobre información, orientación y prestaciones en materia de regulación de la fertilidad, para pro'
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `senado-16709-f5b00dd9443e` in config/cl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc cl --confirm senado-16709-f5b00dd9443e --by Christopher`

### 4. `camara-89307` Boletín N° 16743-04 Indicación renovada, de la diputada Emilia Schneider, que agrega el siguiente número 4 nuevo al artículo primero del pro

- **Why first (24 points):** amendment-level (lower); tier 1; contested: 59-85; split IND (10 against their group); meaning line quotes the source; this year.
- **When / result:** 2026-07-07; Cámara; Rechazado; Afirmativo 59, En contra 85
- **On:** Modifica diversos cuerpos legales, con el objeto de facilitar la creación de nuevos establecimientos educacionales
- **Area:** marriage and family, migration
- **Lobbies:** Afirmativo: IND 14, FA 12, PS 9, PC 8, DC 6, PPD 4, PL 2, PAH 1, ? 1, FRVS 1, PR 1. En contra: PREP 27, UDI 12, PDG 12, RN 11, IND 10, PNL 8, PSC 2, EVOP 2, DEM 1
- Meaning: **Afirmativo** = to adopt the amendment or part put to the vote (“Boletín N° 16743-04 Indicación renovada, de la diputada Emilia…”) on the text “Modifica diversos cuerpos legales, con el objeto de facilitar la creación de nuevos…”; **En contra** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Boletín N° 16743-04 Indicación renovada, de la diputada Emilia Schneider, que agrega el siguiente número 4 nuevo al artí'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-89307` in config/cl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc cl --confirm camara-89307 --by Christopher`

### 5. `camara-89383` Boletín N° 18399-06 Artículo único del proyecto, en los términos propuestos por la Comisión de Gobierno Interior, Nacionalidad, Ciudadanía y

- **Why first (-95 points):** tier 1; near-unanimous (103-0, lower); recent; collated-only area: places nobody (lowest).
- **When / result:** 2026-07-13; Cámara; Aprobado; Afirmativo 103, En contra 0, Abstain 34
- **On:** Declara feriado regional el 10 de agosto de los años 2026 y 2027 en reemplazo de los feriados que indica
- **Area:** migration
- **Lobbies:** Afirmativo: IND 19, PDG 13, FA 12, PS 10, RN 9, UDI 9, DC 7, PC 6, PNL 6, PPD 3, PL 2, EVOP 2, DEM 1, PAH 1, ? 1, FRVS 1, PR 1. Abstain: PREP 27, PSC 3, IND 3, UDI 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Boletín N° 18399-06 Artículo único del proyecto, en los términos propuestos por la Comisión de Gobierno Interior, Nacion'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `camara-89383` in config/cl_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc cl --confirm camara-89383 --by Christopher`

## By area (rank in the whole list)

- **abortion** (1 waiting): #1 `camara-88946` 2026-05-20, 40 pts
- **parental rights and education** (1 waiting): #3 `senado-16709-f5b00dd9443e` 2025-01-29, 38 pts
- **free speech and civil liberties** (1 waiting): #2 `camara-90141` 2026-09-23, 38 pts
- **marriage and family** (1 waiting): #4 `camara-89307` 2026-07-07, 24 pts
- **surrogacy and embryology** (1 waiting): #3 `senado-16709-f5b00dd9443e` 2025-01-29, 38 pts
- **migration** (2 waiting): #4 `camara-89307` 2026-07-07, 24 pts; #5 `camara-89383` 2026-07-13, -95 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

