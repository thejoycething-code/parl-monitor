# Spain 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 86 readings waiting in `config/es_stance.yaml` (1 proposed, 4 procedural, 81 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-es-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc es --confirm congreso-15-177-12 --by Christopher

## Top 20

### 1. `congreso-15-177-12` Votación conjunta de las enmiendas a la totalidad de devolución al Proyecto de reforma del artículo 43 de la Constitución Española, presenta

- **Why first (105 points):** a motion to reject the text; the last such vote on its bill; watched bill 15/102/000001; values proposed: one tick to sign; close: 171-177; meaning line ready; this year.
- **When / result:** 2026-04-30; Congreso; Sí 171, No 177
- **On:** Debates de totalidad de iniciativas de reforma constitucional.
- **Area:** abortion
- Meaning: **Sí** = to send 15/102/000001 (the Government's bill to write abortion into the Constitution) back to the government (an amendment to the whole); **No** = against sending it back, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Sí +2, No -2
  - Voted Sí on 15/102/000001 (Proyecto de reforma del artículo 43 de la Constitución: the Government's bill to write abo): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc es --confirm congreso-15-177-12 --by Christopher`

### 2. `congreso-15-191-15` Moción consecuencia de interpelación urgente del Grupo Parlamentario Mixto (Sra. Micó Micó), sobre el apoyo a las víctimas de las pseudotera

- **Why first (78 points):** a vote on the whole text; the last such vote on its bill; tier 1; close: 174-169; meaning line quotes the source; this year.
- **When / result:** 2026-06-25; Congreso; Sí 174, No 169, Abstain 5
- **On:** Mociones consecuencia de interpelaciones urgentes.
- **Area:** sex-based rights
- Meaning: **Sí** = to adopt the motion “Moción consecuencia de interpelación urgente del Grupo Parlamentario Mixto (Sra. Micó…”; **No** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/173/000181: CitizenGO's position on 'Mociones consecuencia de interpelaciones urgentes.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-191-15` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-191-15 --by Christopher`

### 3. `congreso-15-185-42` Proposición de Ley del Parlamento de Cataluña, de modificación de algunas disposiciones normativas procesales con relación al derecho de mor

- **Why first (78 points):** a vote on the whole text; the last such vote on its bill; tier 1; close: 178-169; meaning line quotes the source; this year.
- **When / result:** 2026-06-11; Congreso; Sí 178, No 169
- **On:** Toma en consideración de Proposiciones de Ley de Comunidades y Ciudades Autónomas.
- **Area:** assisted dying
- Meaning: **Sí** = to pass the text “Proposición de Ley del Parlamento de Cataluña, de modificación de algunas disposiciones…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/125/000014: CitizenGO's position on 'Toma en consideración de Proposiciones de Ley de Comunidades y Ciudades Autónomas.' needs a human reading. Add a `bill_directions` line 
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-185-42` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-185-42 --by Christopher`

### 4. `congreso-15-107-2` Proposición de Ley del Grupo Parlamentario VOX, Orgánica de modificación de la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal, p

- **Why first (63 points):** a vote on the whole text; tier 1; close: 169-175; meaning line quotes the source.
- **When / result:** 2025-05-06; Congreso; Sí 169, No 175
- **On:** Toma en consideración de Proposiciones de Ley.
- **Area:** marriage and family, prostitution and trafficking
- Meaning: **Sí** = to pass the text “Proposición de Ley del Grupo Parlamentario VOX, Orgánica de modificación de la Ley…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/122/000164: CitizenGO's position on 'Toma en consideración de Proposiciones de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-107-2` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-107-2 --by Christopher`

### 5. `congreso-15-71-1` Proposición de Ley de los Grupos Parlamentarios Socialista, Plurinacional SUMAR, Euskal Herria Bildu y Vasco (EAJ-PNV), Orgánica de protecci

- **Why first (63 points):** a vote on the whole text; tier 1; close: 176-170; meaning line quotes the source.
- **When / result:** 2024-10-29; Congreso; Sí 176, No 170
- **On:** Toma en consideración de Proposiciones de Ley.
- **Area:** free speech and civil liberties
- Meaning: **Sí** = to pass the text “Proposición de Ley de los Grupos Parlamentarios Socialista, Plurinacional SUMAR, Euskal…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/122/000131: CitizenGO's position on 'Toma en consideración de Proposiciones de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-71-1` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-71-1 --by Christopher`

### 6. `congreso-15-13-1` Proposición de Ley del Grupo Parlamentario Plurinacional SUMAR, Orgánica de reforma de la Ley Orgánica 10/1995, de 23 de noviembre, del Códi

- **Why first (58 points):** a vote on the whole text; tier 1; close: 177-169; meaning line quotes the source.
- **When / result:** 2023-12-19; Congreso; Sí 177, No 169
- **On:** Toma en consideración de Proposiciones de Ley.
- **Area:** free speech and civil liberties
- Meaning: **Sí** = to pass the text “Proposición de Ley del Grupo Parlamentario Plurinacional SUMAR, Orgánica de reforma de la…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/122/000006: CitizenGO's position on 'Toma en consideración de Proposiciones de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-13-1` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-13-1 --by Christopher`

### 7. `congreso-15-191-21` Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal, para penalizar las terapia

- **Why first (48 points):** a vote on the whole text; tier 1; meaning line quotes the source; this year.
- **When / result:** 2026-06-25; Congreso; Sí 179, No 32, Abstain 137
- **On:** Dictámenes de Comisiones sobre iniciativas legislativas.
- **Area:** conversion practices, sex-based rights
- Meaning: **Sí** = to pass the text “Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/122/000201: CitizenGO's position on 'Dictámenes de Comisiones sobre iniciativas legislativas.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-191-21` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-191-21 --by Christopher`

### 8. `congreso-15-191-22` Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal, para penalizar las terapia

- **Why first (48 points):** a vote on the whole text; tier 1; meaning line quotes the source; this year.
- **When / result:** 2026-06-25; Congreso; Sí 178, No 32, Abstain 138
- **On:** Dictámenes de Comisiones sobre iniciativas legislativas.
- **Area:** conversion practices, sex-based rights
- Meaning: **Sí** = to pass the text “Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/122/000201: CitizenGO's position on 'Dictámenes de Comisiones sobre iniciativas legislativas.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-191-22` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-191-22 --by Christopher`

### 9. `congreso-15-174-8` Proposición no de Ley del Grupo Parlamentario Socialista, para impulsar la erradicación del matrimonio forzado a nivel global.

- **Why first (48 points):** a vote on the whole text; tier 1; meaning line quotes the source; this year.
- **When / result:** 2026-04-22; Congreso; Sí 176, No 33, Abstain 136
- **On:** Proposiciones no de Ley.
- **Area:** marriage and family, prostitution and trafficking
- Meaning: **Sí** = to adopt the motion “Proposición no de Ley del Grupo Parlamentario Socialista, para impulsar la erradicación…”; **No** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/162/000753: CitizenGO's position on 'Proposiciones no de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-174-8` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-174-8 --by Christopher`

### 10. `congreso-15-130-9` Votación de la enmienda a la totalidad de devolución al Proyecto de Ley Orgánica para la protección de las personas menores de edad en los e

- **Why first (48 points):** a motion to reject the text; the last such vote on its bill; tier 1; meaning line quotes the source.
- **When / result:** 2025-09-10; Congreso; Sí 33, No 178, Abstain 137
- **On:** Debates de totalidad de iniciativas legislativas.
- **Area:** parental rights and education, free speech and civil liberties
- Meaning: **Sí** = to send the text “Votación de la enmienda a la totalidad de devolución al Proyecto de Ley Orgánica para la…” back to the government (an amendment to the whole); **No** = against sending it back, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A motion to reject the text (the sides are swapped), but no bill direction is on file for 15/121/000052: CitizenGO's position on 'Debates de totalidad de iniciativas legislativas.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-130-9` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-130-9 --by Christopher`

### 11. `congreso-15-122-2` Proposición de Ley del Grupo Parlamentario Socialista, Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, del Códi

- **Why first (43 points):** a vote on the whole text; tier 1; meaning line quotes the source.
- **When / result:** 2025-06-24; Congreso; Sí 311, No 33, Abstain 1
- **On:** Toma en consideración de Proposiciones de Ley.
- **Area:** conversion practices, sex-based rights
- Meaning: **Sí** = to pass the text “Proposición de Ley del Grupo Parlamentario Socialista, Orgánica por la que se modifica la…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/122/000201: CitizenGO's position on 'Toma en consideración de Proposiciones de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-122-2` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-122-2 --by Christopher`

### 12. `congreso-15-121-3` Proposición no de Ley del Grupo Parlamentario Socialista, relativa a la condena de la prohibición de la marcha del orgullo LGTBI en Hungría 

- **Why first (43 points):** a vote on the whole text; tier 1; meaning line quotes the source.
- **When / result:** 2025-06-19; Congreso; Sí 176, No 33, Abstain 136
- **On:** Proposiciones no de Ley.
- **Area:** sex-based rights
- Meaning: **Sí** = to adopt the motion “Proposición no de Ley del Grupo Parlamentario Socialista, relativa a la condena de la…”; **No** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/162/000496: CitizenGO's position on 'Proposiciones no de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-121-3` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-121-3 --by Christopher`

### 13. `congreso-15-109-7` Proposición no de Ley del Grupo Parlamentario VOX, en defensa de la libertad de expresión.

- **Why first (43 points):** a vote on the whole text; tier 1; meaning line quotes the source.
- **When / result:** 2025-05-08; Congreso; Sí 32, No 180, Abstain 137
- **On:** Proposiciones no de Ley.
- **Area:** free speech and civil liberties
- Meaning: **Sí** = to adopt the motion “Proposición no de Ley del Grupo Parlamentario VOX, en defensa de la libertad de expresión.”; **No** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/162/000311: CitizenGO's position on 'Proposiciones no de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-109-7` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-109-7 --by Christopher`

### 14. `congreso-15-49-8` Proposición no de Ley del Grupo Parlamentario Socialista, sobre un Acuerdo de País contra los Discursos de Odio.

- **Why first (38 points):** a vote on the whole text; tier 1; meaning line quotes the source.
- **When / result:** 2024-06-20; Congreso; Sí 177, No 33, Abstain 138
- **On:** Proposiciones no de Ley.
- **Area:** free speech and civil liberties
- Meaning: **Sí** = to adopt the motion “Proposición no de Ley del Grupo Parlamentario Socialista, sobre un Acuerdo de País contra…”; **No** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/162/000252: CitizenGO's position on 'Proposiciones no de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-49-8` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-49-8 --by Christopher`

### 15. `congreso-15-38-2` Proposición de Ley del Grupo Parlamentario Socialista, Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, del Códi

- **Why first (38 points):** a vote on the whole text; tier 1; meaning line quotes the source.
- **When / result:** 2024-05-21; Congreso; Sí 122, No 184, Abstain 36
- **On:** Toma en consideración de Proposiciones de Ley.
- **Area:** prostitution and trafficking
- Meaning: **Sí** = to pass the text “Proposición de Ley del Grupo Parlamentario Socialista, Orgánica por la que se modifica la…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/122/000077: CitizenGO's position on 'Toma en consideración de Proposiciones de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-38-2` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-38-2 --by Christopher`

### 16. `congreso-15-192-56` Proposición de Ley Orgánica de reforma de la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal para la protección de la libertad de

- **Why first (33 points):** amendment-level (lower); tier 1; close: 171-178; meaning line quotes the source; recent.
- **When / result:** 2026-07-14; Congreso; Sí 171, No 178
- **On:** Debates de totalidad de iniciativas legislativas.
- **Area:** free speech and civil liberties
- Meaning: **Sí** = to replace the text “Proposición de Ley Orgánica de reforma de la Ley Orgánica 10/1995, de 23 de noviembre…” with an alternative text (an amendment to the whole); **No** = against the alternative text. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Proposición de Ley Orgánica de reforma de la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal para la protecci'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-192-56` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-192-56 --by Christopher`

### 17. `congreso-15-166-2` Proposición no de Ley del Grupo Parlamentario Popular en el Congreso, relativa a la defensa de los cristianos perseguidos en el mundo y la a

- **Why first (33 points):** a vote on the whole text; tier 1; near-unanimous (169-3, lower); meaning line quotes the source; this year.
- **When / result:** 2026-03-18; Congreso; Sí 169, No 3, Abstain 176
- **On:** Proposiciones no de Ley.
- **Area:** religious freedom
- Meaning: **Sí** = to adopt the motion “Proposición no de Ley del Grupo Parlamentario Popular en el Congreso, relativa a la…”; **No** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 15/162/000717: CitizenGO's position on 'Proposiciones no de Ley.' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-166-2` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-166-2 --by Christopher`

### 18. `congreso-15-191-14` Proposición no de Ley del Grupo Parlamentario Socialista, para impulsar la educación afectivo-sexual y emocional en el ámbito educativo. Se 

- **Why first (28 points):** amendment-level (lower); tier 1; close: 172-170; meaning line quotes the source; this year.
- **When / result:** 2026-06-25; Congreso; Sí 172, No 170, Abstain 7
- **On:** Proposiciones no de Ley.
- **Area:** parental rights and education
- Meaning: **Sí** = to adopt the motion “Proposición no de Ley del Grupo Parlamentario Socialista, para impulsar la educación…”, in the terms put to the vote; **No** = against adopting the motion. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Proposición no de Ley del Grupo Parlamentario Socialista, para impulsar la educación afectivo-sexual y emocional en el á'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-191-14` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-191-14 --by Christopher`

### 19. `congreso-15-191-4` Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal, para penalizar las terapia

- **Why first (28 points):** amendment-level (lower); tier 1; close: 170-179; meaning line quotes the source; this year.
- **When / result:** 2026-06-25; Congreso; Sí 170, No 179
- **On:** Dictámenes de Comisiones sobre iniciativas legislativas.
- **Area:** conversion practices, sex-based rights
- Meaning: **Sí** = to pass the text “Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal, para p'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-191-4` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-191-4 --by Christopher`

### 20. `congreso-15-191-5` Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal, para penalizar las terapia

- **Why first (28 points):** amendment-level (lower); tier 1; close: 169-172; meaning line quotes the source; this year.
- **When / result:** 2026-06-25; Congreso; Sí 169, No 172, Abstain 7
- **On:** Dictámenes de Comisiones sobre iniciativas legislativas.
- **Area:** conversion practices, sex-based rights
- Meaning: **Sí** = to pass the text “Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de…” as a whole; **No** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, del Código Penal, para p'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `congreso-15-191-5` in config/es_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc es --confirm congreso-15-191-5 --by Christopher`

## By area (rank in the whole list)

- **abortion** (2 waiting): #1 `congreso-15-177-12` 2026-04-30, 105 pts; #22 `congreso-15-164-1` 2026-02-26, 28 pts
- **assisted dying** (1 waiting): #3 `congreso-15-185-42` 2026-06-11, 78 pts
- **conversion practices** (10 waiting): #7 `congreso-15-191-21` 2026-06-25, 48 pts; #8 `congreso-15-191-22` 2026-06-25, 48 pts; #11 `congreso-15-122-2` 2025-06-24, 43 pts
- **sex-based rights** (12 waiting): #2 `congreso-15-191-15` 2026-06-25, 78 pts; #7 `congreso-15-191-21` 2026-06-25, 48 pts; #8 `congreso-15-191-22` 2026-06-25, 48 pts
- **parental rights and education** (18 waiting): #10 `congreso-15-130-9` 2025-09-10, 48 pts; #18 `congreso-15-191-14` 2026-06-25, 28 pts; #22 `congreso-15-164-1` 2026-02-26, 28 pts
- **free speech and civil liberties** (14 waiting): #5 `congreso-15-71-1` 2024-10-29, 63 pts; #6 `congreso-15-13-1` 2023-12-19, 58 pts; #10 `congreso-15-130-9` 2025-09-10, 48 pts
- **religious freedom** (1 waiting): #17 `congreso-15-166-2` 2026-03-18, 33 pts
- **marriage and family** (3 waiting): #4 `congreso-15-107-2` 2025-05-06, 63 pts; #9 `congreso-15-174-8` 2026-04-22, 48 pts; #25 `congreso-15-200-2` 2026-09-23, 13 pts
- **migration** (36 waiting): #51 `congreso-15-202-1` 2026-09-30, -26 pts; #52 `congreso-15-198-1` 2026-09-16, -27 pts; #53 `congreso-15-133-1` 2025-09-23, -27 pts
- **prostitution and trafficking** (3 waiting): #4 `congreso-15-107-2` 2025-05-06, 63 pts; #9 `congreso-15-174-8` 2026-04-22, 48 pts; #15 `congreso-15-38-2` 2024-05-21, 38 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

