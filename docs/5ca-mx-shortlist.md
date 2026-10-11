# Mexico 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 3 readings waiting in `config/mx_stance.yaml` (0 proposed, 0 procedural, 3 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-mx-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

## Top 3

### 1. `dip-66-234` DECRETO POR EL QUE SE ADICIONAN DIVERSAS DISPOSICIONES DE LA LEY GENERAL DE TURISMO, EN MATERIA DE TRATA DE PERSONAS (EN LO GENERAL Y EN LO 

- **Why first (33 points):** a vote on the whole text; tier 1; near-unanimous (463-0, lower); meaning line quotes the source; this year.
- **When / result:** 2026-03-03; Cámara de Diputados; A favor 463, En contra 0
- **Area:** prostitution and trafficking
- **Lobbies:** A favor: MORENA 233, PAN 67, PVEM 59, PT 42, PRI 34, MC 27, IND 1
- Meaning: **A favor** = to approve the text “DECRETO POR EL QUE SE ADICIONAN DIVERSAS DISPOSICIONES DE LA LEY GENERAL DE TURISMO, EN…” in general and in its articles, in one vote; **En contra** = against approving it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 66/1952, 66/2199, 66/2615, 66/2786: CitizenGO's position on 'DECRETO POR EL QUE SE ADICIONAN DIVERSAS DISPOSICIONES DE LA LEY GENERAL DE TURISMO, EN MATERIA DE TRATA DE PERSONA
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `dip-66-234` in config/mx_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc mx --confirm dip-66-234 --by Christopher`

### 2. `dip-66-200` DECRETO POR EL QUE SE REFORMAN, ADICIONAN Y DEROGAN DIVERSAS DISPOSICIONES DE LA LEY GENERAL PARA LA IGUALDAD ENTRE MUJERES Y HOMBRES; DE LA

- **Why first (18 points):** tier 1; split PRI (1 against their group); this year.
- **When / result:** 2025-12-02; Cámara de Diputados; A favor 333, En contra 70, Abstain 22
- **Area:** sex-based rights, migration
- **Lobbies:** A favor: MORENA 211, PVEM 54, PT 41, MC 25, IND 1, PRI 1. En contra: PAN 61, PRI 9. Abstain: PRI 21, MC 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('DECRETO POR EL QUE SE REFORMAN, ADICIONAN Y DEROGAN DIVERSAS DISPOSICIONES DE LA LEY GENERAL PARA LA IGUALDAD ENTRE MUJE'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `dip-66-200` in config/mx_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc mx --confirm dip-66-200 --by Christopher`

### 3. `dip-66-199` DECRETO POR EL QUE SE REFORMAN, ADICIONAN Y DEROGAN DIVERSAS DISPOSICIONES DE LA LEY GENERAL PARA LA IGUALDAD ENTRE MUJERES Y HOMBRES; DE LA

- **Why first (0 points):** tier 1; near-unanimous (442-0, lower); this year.
- **When / result:** 2025-12-02; Cámara de Diputados; A favor 442, En contra 0
- **Area:** sex-based rights, migration
- **Lobbies:** A favor: MORENA 219, PAN 64, PVEM 56, PT 45, PRI 31, MC 26, IND 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('DECRETO POR EL QUE SE REFORMAN, ADICIONAN Y DEROGAN DIVERSAS DISPOSICIONES DE LA LEY GENERAL PARA LA IGUALDAD ENTRE MUJE'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `dip-66-199` in config/mx_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc mx --confirm dip-66-199 --by Christopher`

## By area (rank in the whole list)

- **sex-based rights** (2 waiting): #2 `dip-66-200` 2025-12-02, 18 pts; #3 `dip-66-199` 2025-12-02, 0 pts
- **migration** (2 waiting): #2 `dip-66-200` 2025-12-02, 18 pts; #3 `dip-66-199` 2025-12-02, 0 pts
- **prostitution and trafficking** (1 waiting): #1 `dip-66-234` 2026-03-03, 33 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

