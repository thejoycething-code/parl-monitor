# Ecuador 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 7 readings waiting in `config/ec_stance.yaml` (0 proposed, 0 procedural, 7 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-ec-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

## Top 7

### 1. `ec-1004205` Conocer el Informe para Primer Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica contra la trata de personas y el tráfico i

- **Why first (0 points):** tier 1; near-unanimous (0-67, lower); this year.
- **When / result:** 2025-12-09; asamblea; Sí 0, No 67, Abstain 80
- **On:** Conocer el Informe para Primer Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica contra la trata de personas y el tráfico ilícito de migrantes
- **Area:** migration, prostitution and trafficking
- **Lobbies:** No: Revolución Ciudadana 50, ? 13, Pachakutik 3, 16 1. Abstain: Acción Democrática Nacional (ADN) 51, ? 17, 26 4, Pachakutik 4, 15 3, 16 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Conocer el Informe para Primer Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica contra la trata de per'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `ec-1004205` in config/ec_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ec --confirm ec-1004205 --by Christopher`

### 2. `ec-1004126` Proyecto de Resolución para reconocer y destacar la reducción, entre los años 2023 y 2025, de más del 90% de la migración irregular de ciuda

- **Why first (-66 points):** tier 1; contested: 76-55; split 16, Pachakutik (4 against their group); meaning line quotes the source; this year; collated-only area: places nobody (lowest).
- **When / result:** 2025-10-28; asamblea; Sí 76, No 55, Abstain 7
- **On:** Proyecto de Resolución para reconocer y destacar la reducción, entre los años 2023 y 2025, de más del 90% de la migración irregular de ciudadanos ecuatorianos, gracias a la implementación de políticas
- **Area:** migration
- **Lobbies:** Sí: Acción Democrática Nacional (ADN) 48, ? 19, 15 3, Pachakutik 3, 26 2, 16 1. No: Revolución Ciudadana 41, ? 10, Pachakutik 3, 16 1. Abstain: Pachakutik 2, 26 2, ? 2, Partido Social Cristiano 1
- Meaning: **Sí** = to adopt the resolution or decision “Proyecto de Resolución para reconocer y destacar la reducción, entre los años 2023 y…”; **No** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Proyecto de Resolución para reconocer y destacar la reducción, entre los años 2023 y 2025, de más del 90% de la migració'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `ec-1004126` in config/ec_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ec --confirm ec-1004126 --by Christopher`

### 3. `ec-1004054` Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica de Donación y Traspl

- **Why first (-68 points):** tier 1; contested: 78-54; split 16, Pachakutik, Revolución Ciudadana (4 against their group); meaning line quotes the source; collated-only area: places nobody (lowest).
- **When / result:** 2025-09-10; asamblea; Sí 78, No 54, Abstain 4
- **On:** Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica de Donación y Trasplante de Órganos, Tejidos y Células
- **Area:** organ donation
- **Lobbies:** Sí: Acción Democrática Nacional (ADN) 43, ? 24, Pachakutik 5, 15 2, 26 2, Revolución Ciudadana 1, 16 1. No: Revolución Ciudadana 45, ? 6, Pachakutik 2, 16 1. Abstain: ? 2, 26 1, Partido Social Cristiano 1
- Meaning: **Sí** = to approve the text “Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica…” at its second debate (the Assembly's final vote); **No** = against approving it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica '): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `ec-1004054` in config/ec_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ec --confirm ec-1004054 --by Christopher`

### 4. `ec-1004055` Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica de Donación y Traspl

- **Why first (-68 points):** tier 1; contested: 54-80; split 16, Pachakutik, Revolución Ciudadana (4 against their group); meaning line quotes the source; collated-only area: places nobody (lowest).
- **When / result:** 2025-09-10; asamblea; Sí 54, No 80, Abstain 2
- **On:** Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica de Donación y Trasplante de Órganos, Tejidos y Células
- **Area:** organ donation
- **Lobbies:** Sí: Revolución Ciudadana 45, ? 6, Pachakutik 2, 16 1. No: Acción Democrática Nacional (ADN) 43, ? 25, Pachakutik 5, 26 3, 15 2, Revolución Ciudadana 1, 16 1. Abstain: Partido Social Cristiano 1, ? 1
- Meaning: **Sí** = to approve the text “Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica…” at its second debate (the Assembly's final vote); **No** = against approving it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica '): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `ec-1004055` in config/ec_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ec --confirm ec-1004055 --by Christopher`

### 5. `ec-1004116` Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica de Movilidad Humana,

- **Why first (-71 points):** tier 1; contested: 60-88; split 16 (1 against their group); meaning line quotes the source; this year; collated-only area: places nobody (lowest).
- **When / result:** 2025-10-22; asamblea; Sí 60, No 88
- **On:** Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica de Movilidad Humana, Unificado
- **Area:** migration
- **Lobbies:** Sí: Revolución Ciudadana 49, ? 10, 16 1. No: Acción Democrática Nacional (ADN) 48, ? 23, Pachakutik 8, 26 4, 15 3, Partido Social Cristiano 1, 16 1
- Meaning: **Sí** = to approve the text “Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica…” at its second debate (the Assembly's final vote); **No** = against approving it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica '): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `ec-1004116` in config/ec_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ec --confirm ec-1004116 --by Christopher`

### 6. `ec-1004115` Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica de Movilidad Humana,

- **Why first (-79 points):** tier 1; split 16 (1 against their group); meaning line quotes the source; this year; collated-only area: places nobody (lowest).
- **When / result:** 2025-10-22; asamblea; Sí 88, No 58, Abstain 2
- **On:** Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica de Movilidad Humana, Unificado
- **Area:** migration
- **Lobbies:** Sí: Acción Democrática Nacional (ADN) 47, ? 24, Pachakutik 8, 26 4, 15 3, Partido Social Cristiano 1, 16 1. No: Revolución Ciudadana 48, ? 9, 16 1. Abstain: Revolución Ciudadana 1, ? 1
- Meaning: **Sí** = to approve the text “Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica…” at its second debate (the Assembly's final vote); **No** = against approving it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Conocer y resolver respecto del Informe para Segundo Debate del Proyecto de Ley Orgánica Reformatoria a la Ley Orgánica '): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `ec-1004115` in config/ec_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ec --confirm ec-1004115 --by Christopher`

### 7. `ec-1004767` Conocer el Informe del Proceso de Fiscalización sobre las actuaciones institucionales y administrativas relacionadas con los procesos de con

- **Why first (-81 points):** tier 1; split Pachakutik (2 against their group); this year; collated-only area: places nobody (lowest).
- **When / result:** 2026-06-23; asamblea; Sí 83, No 54, Abstain 4
- **On:** Conocer el Informe del Proceso de Fiscalización sobre las actuaciones institucionales y administrativas relacionadas con los procesos de contratación pública y gestión administrativa vinculados a la a
- **Area:** migration
- **Lobbies:** Sí: Acción Democrática Nacional (ADN) 42, ? 29, Pachakutik 5, 26 4, 15 2, 16 1. No: Revolución Ciudadana 39, ? 13, Pachakutik 2. Abstain: ? 2, 16 1, Partido Social Cristiano 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Conocer el Informe del Proceso de Fiscalización sobre las actuaciones institucionales y administrativas relacionadas con'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `ec-1004767` in config/ec_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ec --confirm ec-1004767 --by Christopher`

## By area (rank in the whole list)

- **migration** (5 waiting): #1 `ec-1004205` 2025-12-09, 0 pts; #2 `ec-1004126` 2025-10-28, -66 pts; #5 `ec-1004116` 2025-10-22, -71 pts
- **prostitution and trafficking** (1 waiting): #1 `ec-1004205` 2025-12-09, 0 pts
- **organ donation** (2 waiting): #3 `ec-1004054` 2025-09-10, -68 pts; #4 `ec-1004055` 2025-09-10, -68 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

