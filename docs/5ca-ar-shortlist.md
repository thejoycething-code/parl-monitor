# Argentina 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 2 readings waiting in `config/ar_stance.yaml` (0 proposed, 0 procedural, 2 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-ar-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

## Top 2

### 1. `sen-acta-2486` EN GENERAL Y EN PARTICULAR: Modificación del Código Penal de la Nación sobre la sustracción y/o comercialización de menores de edad.

- **Why first (33 points):** a vote on the whole text; the last such vote on its bill; tier 1; near-unanimous (67-0, lower); meaning line quotes the source.
- **When / result:** 2024-08-22; Senado; AFIRMATIVO; Afirmativo 67, Negativo 0
- **On:** Modificación del Código Penal de la Nación sobre la sustracción y/o comercialización de menores de edad.
- **Area:** prostitution and trafficking
- **Lobbies:** Afirmativo: JUSTICIALISTA 14, UCR - UNIÓN CÍVICA RADICAL 12, LA LIBERTAD AVANZA 9, UNIDAD CIUDADANA 5, FRENTE NACIONAL Y POPULAR 4, FRENTE PRO 4, CONVICCIÓN FEDERAL 3, SIN ESPECIFICAR 2, JUSTICIA SOCIAL FEDERAL 2, MOVIMIENTO POR MISIONES 2, MOVERE SANTA CRUZ 2, CAMBIO FEDERAL 1, MOVIMIENTO NEUQUINO 
- Meaning: **Afirmativo** = to approve the text “Modificación del Código Penal de la Nación sobre la sustracción y/o comercialización de…” in general and in its articles, in one vote; **Negativo** = against approving it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for this item: CitizenGO's position on 'Modificación del Código Penal de la Nación sobre la sustracción y/o comercialización de menores de edad.' needs a human reading. Add a `bill
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sen-acta-2486` in config/ar_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ar --confirm sen-acta-2486 --by Christopher`

### 2. `sen-acta-2480` EN GENERAL: Modificación del art. 139 del Código Penal tipificando la sustracción y/o comercialización de menores de edad.

- **Why first (-17 points):** amendment-level (lower); tier 1; near-unanimous (63-0, lower); meaning line quotes the source.
- **When / result:** 2024-07-04; Senado; AFIRMATIVO; Afirmativo 63, Negativo 0
- **On:** Modificación del art. 139 del Código Penal tipificando la sustracción y/o comercialización de menores de edad.
- **Area:** prostitution and trafficking
- **Lobbies:** Afirmativo: UCR - UNIÓN CÍVICA RADICAL 13, JUSTICIALISTA 10, LA LIBERTAD AVANZA 9, UNIDAD CIUDADANA 5, FRENTE PRO 5, FRENTE NACIONAL Y POPULAR 3, CONVICCIÓN FEDERAL 3, PROVINCIAS UNIDAS 2, JUSTICIA SOCIAL FEDERAL 2, MOVIMIENTO POR MISIONES 2, MOVERE SANTA CRUZ 2, CAMBIO FEDERAL 1, MOVIMIENTO NEUQUIN
- Meaning: **Afirmativo** = to adopt the amendment or part put to the vote (“EN GENERAL: Modificación del art. 139 del Código Penal tipificando la…”) on the text “Modificación del art. 139 del Código Penal tipificando la sustracción y/o…”; **Negativo** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('EN GENERAL: Modificación del art. 139 del Código Penal tipificando la sustracción y/o comercialización de menores de eda'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `sen-acta-2480` in config/ar_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc ar --confirm sen-acta-2480 --by Christopher`

## By area (rank in the whole list)

- **prostitution and trafficking** (2 waiting): #1 `sen-acta-2486` 2024-08-22, 33 pts; #2 `sen-acta-2480` 2024-07-04, -17 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

