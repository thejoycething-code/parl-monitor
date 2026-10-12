# Hungary 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 24 readings waiting in `config/hu_stance.yaml` (2 proposed, 1 procedural, 21 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-hu-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:44:38 2026.06.23.10:44:01 --by Christopher

## Top 20

### 1. `2026.06.23.10:44:38` önálló indítvány egyszerű többséget igénylő része elfogadva

- **Why first (90 points):** a vote on the whole text; the last such vote on its bill; watched bill T/122; values proposed: one tick to sign; meaning line ready; this year.
- **When / result:** 2026-06-23; Országgyűlés; Elfogadva; Igen 145, Nem 39
- **On:** A gyűlöletkeltésre alkalmas politikai reklámok visszaszorításáról, a gazdasági reklámok településképi illeszkedésének biztosításáról, valamint egyes beruházási szabályok módosításáról
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 139, Mi Hazánk 6. Nem: Fidesz 35, KDNP 4
- Meaning: **Igen** = to pass T/122 (Hate-inciting political advertising; enacted as Act XX of 2026) as a whole; **Nem** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Igen -2, Nem +2
  - Voted Igen on T/122 (Hate-inciting political advertising): for passing it, against CitizenGO's position.
- **Flag:** On the bill's direction: A speech law: who decides what incites hatred; confirm.
- **Sign:** `python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:44:38 --by Christopher`

### 2. `2026.06.23.10:44:01` önálló indítvány minősített többséget igénylő része elfogadva

- **Why first (80 points):** a vote on the whole text; watched bill T/122; values proposed: one tick to sign; meaning line ready; this year.
- **When / result:** 2026-06-23; Országgyűlés; Elfogadva; Igen 145, Nem 39
- **On:** A gyűlöletkeltésre alkalmas politikai reklámok visszaszorításáról, a gazdasági reklámok településképi illeszkedésének biztosításáról, valamint egyes beruházási szabályok módosításáról
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 139, Mi Hazánk 6. Nem: Fidesz 35, KDNP 4
- Meaning: **Igen** = to pass T/122 (Hate-inciting political advertising; enacted as Act XX of 2026) as a whole; **Nem** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Igen -2, Nem +2
  - Voted Igen on T/122 (Hate-inciting political advertising): for passing it, against CitizenGO's position.
- **Flag:** On the bill's direction: A speech law: who decides what incites hatred; confirm.
- **Sign:** `python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:44:01 --by Christopher`

### 3. `2026.06.30.10:45:32` önálló indítvány egyszerű többséget igénylő része elfogadva

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill T/123; meaning line ready; this year.
- **When / result:** 2026-06-30; Országgyűlés; Elfogadva; Igen 135, Nem 44, Abstain 6
- **On:** A Szuverenitásvédelmi Hivatal megszüntetéséről
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 135. Nem: Fidesz 37, KDNP 7. Abstain: Mi Hazánk 6
- Meaning: **Igen** = to pass T/123 (Abolishes the Sovereignty Protection Office; enacted as Act XXIV of 2026) as a whole; **Nem** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for T/123: CitizenGO's position on 'A Szuverenitásvédelmi Hivatal megszüntetéséről' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.30.10:45:32` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.30.10:45:32 --by Christopher`

### 4. `2026.06.15.17:20:04` önálló indítvány minősített többséget igénylő része elfogadva

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill T/51; meaning line ready; this year.
- **When / result:** 2026-06-15; Országgyűlés; Elfogadva; Igen 135, Nem 50, Abstain 6
- **On:** Magyarország Alaptörvényének tizenhatodik módosítása
- **Lobbies:** Igen: TISZA 135. Nem: Fidesz 42, KDNP 8. Abstain: Mi Hazánk 6
- Meaning: **Igen** = to pass T/51 (Sixteenth amendment to the Fundamental Law; passed 15 June 2026 (135-50-6, two-thirds of all MPs needed)…) as a whole; **Nem** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for T/51: CitizenGO's position on 'Magyarország Alaptörvényének tizenhatodik módosítása' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.15.17:20:04` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.15.17:20:04 --by Christopher`

### 5. `2026.07.13.18:19:08` önálló indítvány minősített többséget igénylő része elfogadva

- **Why first (65 points):** a vote on the whole text; the last such vote on its bill; watched bill T/324; near-unanimous (139-6, lower); meaning line ready; recent.
- **When / result:** 2026-07-13; Országgyűlés; Elfogadva; Igen 139, Nem 6
- **On:** Magyarország Alaptörvényének tizenhetedik módosítása
- **Lobbies:** Igen: TISZA 139. Nem: Mi Hazánk 6
- Meaning: **Igen** = to pass T/324 (Seventeenth amendment to the Fundamental Law; passed 13 July 2026 (139-6, two-thirds of all MPs needed)…) as a whole; **Nem** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for T/324: CitizenGO's position on 'Magyarország Alaptörvényének tizenhetedik módosítása' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.07.13.18:19:08` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.07.13.18:19:08 --by Christopher`

### 6. `2026.06.30.10:44:57` önálló indítvány minősített többséget igénylő része elfogadva

- **Why first (65 points):** a vote on the whole text; watched bill T/123; meaning line ready; this year.
- **When / result:** 2026-06-30; Országgyűlés; Elfogadva; Igen 135, Nem 44, Abstain 6
- **On:** A Szuverenitásvédelmi Hivatal megszüntetéséről
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 135. Nem: Fidesz 37, KDNP 7. Abstain: Mi Hazánk 6
- Meaning: **Igen** = to pass T/123 (Abolishes the Sovereignty Protection Office; enacted as Act XXIV of 2026) as a whole; **Nem** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for T/123: CitizenGO's position on 'A Szuverenitásvédelmi Hivatal megszüntetéséről' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.30.10:44:57` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.30.10:44:57 --by Christopher`

### 7. `2026.06.23.10:41:26` módosító javaslat fenntartása elutasítva

- **Why first (28 points):** amendment-level (lower); watched bill T/122; split TISZA (1 against their group); meaning line ready; this year.
- **When / result:** 2026-06-23; Országgyűlés; Elutasítva; Igen 46, Nem 138
- **On:** A gyűlöletkeltésre alkalmas politikai reklámok visszaszorításáról, a gazdasági reklámok településképi illeszkedésének biztosításáról, valamint egyes beruházási szabályok módosításáról
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: Fidesz 35, Mi Hazánk 6, KDNP 4, TISZA 1. Nem: TISZA 138
- Meaning: **Igen** = to adopt a minority amendment (rejected in committee, kept to a vote by its author) to T/122 (Hate-inciting political advertising; enacted as Act XX of 2026); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('módosító javaslat fenntartása elutasítva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.23.10:41:26` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:41:26 --by Christopher`

### 8. `2026.06.30.10:43:59` összegző módosító javaslat elfogadva

- **Why first (25 points):** amendment-level (lower); watched bill T/123; meaning line ready; this year.
- **When / result:** 2026-06-30; Országgyűlés; Elfogadva; Igen 135, Nem 45, Abstain 6
- **On:** A Szuverenitásvédelmi Hivatal megszüntetéséről
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 135. Nem: Fidesz 38, KDNP 7. Abstain: Mi Hazánk 6
- Meaning: **Igen** = to adopt the Legislative Committee's consolidated amendments to T/123 (Abolishes the Sovereignty Protection Office; enacted as Act XXIV of 2026); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('összegző módosító javaslat elfogadva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.30.10:43:59` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.30.10:43:59 --by Christopher`

### 9. `2026.06.23.10:42:16` összegző módosító javaslat minősített többséget igénylő része elfogadva

- **Why first (25 points):** amendment-level (lower); watched bill T/122; meaning line ready; this year.
- **When / result:** 2026-06-23; Országgyűlés; Elfogadva; Igen 139, Nem 39, Abstain 6
- **On:** A gyűlöletkeltésre alkalmas politikai reklámok visszaszorításáról, a gazdasági reklámok településképi illeszkedésének biztosításáról, valamint egyes beruházási szabályok módosításáról
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 139. Nem: Fidesz 35, KDNP 4. Abstain: Mi Hazánk 6
- Meaning: **Igen** = to adopt the Legislative Committee's consolidated amendments (the part needing a two-thirds majority) to T/122 (Hate-inciting political advertising; enacted as Act XX of 2026); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('összegző módosító javaslat minősített többséget igénylő része elfogadva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.23.10:42:16` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:42:16 --by Christopher`

### 10. `2026.06.23.10:42:51` összegző módosító javaslat egyszerű többséget igénylő része elfogadva

- **Why first (25 points):** amendment-level (lower); watched bill T/122; meaning line ready; this year.
- **When / result:** 2026-06-23; Országgyűlés; Elfogadva; Igen 139, Nem 39, Abstain 6
- **On:** A gyűlöletkeltésre alkalmas politikai reklámok visszaszorításáról, a gazdasági reklámok településképi illeszkedésének biztosításáról, valamint egyes beruházási szabályok módosításáról
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 139. Nem: Fidesz 35, KDNP 4. Abstain: Mi Hazánk 6
- Meaning: **Igen** = to adopt the Legislative Committee's consolidated amendments to T/122 (Hate-inciting political advertising; enacted as Act XX of 2026); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('összegző módosító javaslat egyszerű többséget igénylő része elfogadva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.23.10:42:51` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:42:51 --by Christopher`

### 11. `2026.06.15.17:19:04` összegző módosító javaslat minősített többséget igénylő része elfogadva

- **Why first (25 points):** amendment-level (lower); watched bill T/51; meaning line ready; this year.
- **When / result:** 2026-06-15; Országgyűlés; Elfogadva; Igen 134, Nem 50, Abstain 6
- **On:** Magyarország Alaptörvényének tizenhatodik módosítása
- **Lobbies:** Igen: TISZA 134. Nem: Fidesz 42, KDNP 8. Abstain: Mi Hazánk 6
- Meaning: **Igen** = to adopt the Legislative Committee's consolidated amendments (the part needing a two-thirds majority) to T/51 (Sixteenth amendment to the Fundamental Law; passed 15 June 2026 (135-50-6, two-thirds of all MPs needed)…); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('összegző módosító javaslat minősített többséget igénylő része elfogadva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.15.17:19:04` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.15.17:19:04 --by Christopher`

### 12. `2026.06.23.10:39:06` túlterjeszkedő módosító javaslat szabályszerű

- **Why first (18 points):** amendment-level (lower); watched bill T/122; meaning line quotes the source; this year.
- **When / result:** 2026-06-23; Országgyűlés; Elfogadva; Igen 139, Nem 45
- **On:** A gyűlöletkeltésre alkalmas politikai reklámok visszaszorításáról, a gazdasági reklámok településképi illeszkedésének biztosításáról, valamint egyes beruházási szabályok módosításáról
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 139. Nem: Fidesz 35, Mi Hazánk 6, KDNP 4
- Meaning: **Igen** = to adopt the amendment or part put to the vote (“túlterjeszkedő módosító javaslat szabályszerű”) on T/122 (Hate-inciting political advertising; enacted as Act XX of 2026); **Nem** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('túlterjeszkedő módosító javaslat szabályszerű'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.23.10:39:06` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:39:06 --by Christopher`

### 13. `2026.06.23.10:40:01` bizottsági javaslat túlterjeszkedő módosító javaslat tárgyalására elfogadva

- **Why first (18 points):** amendment-level (lower); watched bill T/122; meaning line quotes the source; this year.
- **When / result:** 2026-06-23; Országgyűlés; Elfogadva; Igen 139, Nem 45
- **On:** A gyűlöletkeltésre alkalmas politikai reklámok visszaszorításáról, a gazdasági reklámok településképi illeszkedésének biztosításáról, valamint egyes beruházási szabályok módosításáról
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 139. Nem: Fidesz 35, Mi Hazánk 6, KDNP 4
- Meaning: **Igen** = to adopt the amendment or part put to the vote (“bizottsági javaslat túlterjeszkedő módosító javaslat tárgyalására…”) on T/122 (Hate-inciting political advertising; enacted as Act XX of 2026); **Nem** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('bizottsági javaslat túlterjeszkedő módosító javaslat tárgyalására elfogadva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.23.10:40:01` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:40:01 --by Christopher`

### 14. `2026.06.23.10:40:39` túlterjeszkedő módosító javaslat elfogadva

- **Why first (18 points):** amendment-level (lower); watched bill T/122; meaning line quotes the source; this year.
- **When / result:** 2026-06-23; Országgyűlés; Elfogadva; Igen 139, Nem 39, Abstain 6
- **On:** A gyűlöletkeltésre alkalmas politikai reklámok visszaszorításáról, a gazdasági reklámok településképi illeszkedésének biztosításáról, valamint egyes beruházási szabályok módosításáról
- **Area:** free speech and civil liberties
- **Lobbies:** Igen: TISZA 139. Nem: Fidesz 35, KDNP 4. Abstain: Mi Hazánk 6
- Meaning: **Igen** = to adopt the amendment or part put to the vote (“túlterjeszkedő módosító javaslat elfogadva”) on T/122 (Hate-inciting political advertising; enacted as Act XX of 2026); **Nem** = against adopting it, leaving the text as it stood. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('túlterjeszkedő módosító javaslat elfogadva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.23.10:40:39` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.23.10:40:39 --by Christopher`

### 15. `2026.07.13.18:16:02` módosító javaslat fenntartása elutasítva

- **Why first (15 points):** amendment-level (lower); watched bill T/324; near-unanimous (6-139, lower); meaning line ready; recent.
- **When / result:** 2026-07-13; Országgyűlés; Elutasítva; Igen 6, Nem 139
- **On:** Magyarország Alaptörvényének tizenhetedik módosítása
- **Lobbies:** Igen: Mi Hazánk 6. Nem: TISZA 139
- Meaning: **Igen** = to adopt a minority amendment (rejected in committee, kept to a vote by its author) to T/324 (Seventeenth amendment to the Fundamental Law; passed 13 July 2026 (139-6, two-thirds of all MPs needed)…); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('módosító javaslat fenntartása elutasítva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.07.13.18:16:02` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.07.13.18:16:02 --by Christopher`

### 16. `2026.07.13.18:16:48` módosító javaslat fenntartása elutasítva

- **Why first (15 points):** amendment-level (lower); watched bill T/324; near-unanimous (6-139, lower); meaning line ready; recent.
- **When / result:** 2026-07-13; Országgyűlés; Elutasítva; Igen 6, Nem 139
- **On:** Magyarország Alaptörvényének tizenhetedik módosítása
- **Lobbies:** Igen: Mi Hazánk 6. Nem: TISZA 139
- Meaning: **Igen** = to adopt a minority amendment (rejected in committee, kept to a vote by its author) to T/324 (Seventeenth amendment to the Fundamental Law; passed 13 July 2026 (139-6, two-thirds of all MPs needed)…); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('módosító javaslat fenntartása elutasítva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.07.13.18:16:48` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.07.13.18:16:48 --by Christopher`

### 17. `2026.07.13.18:17:32` módosító javaslat fenntartása elutasítva

- **Why first (15 points):** amendment-level (lower); watched bill T/324; near-unanimous (6-139, lower); meaning line ready; recent.
- **When / result:** 2026-07-13; Országgyűlés; Elutasítva; Igen 6, Nem 139
- **On:** Magyarország Alaptörvényének tizenhetedik módosítása
- **Lobbies:** Igen: Mi Hazánk 6. Nem: TISZA 139
- Meaning: **Igen** = to adopt a minority amendment (rejected in committee, kept to a vote by its author) to T/324 (Seventeenth amendment to the Fundamental Law; passed 13 July 2026 (139-6, two-thirds of all MPs needed)…); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('módosító javaslat fenntartása elutasítva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.07.13.18:17:32` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.07.13.18:17:32 --by Christopher`

### 18. `2026.07.13.18:18:22` összegző módosító javaslat minősített többséget igénylő része elfogadva

- **Why first (15 points):** amendment-level (lower); watched bill T/324; near-unanimous (145-0, lower); meaning line ready; recent.
- **When / result:** 2026-07-13; Országgyűlés; Elfogadva; Igen 145, Nem 0
- **On:** Magyarország Alaptörvényének tizenhetedik módosítása
- **Lobbies:** Igen: TISZA 139, Mi Hazánk 6
- Meaning: **Igen** = to adopt the Legislative Committee's consolidated amendments (the part needing a two-thirds majority) to T/324 (Seventeenth amendment to the Fundamental Law; passed 13 July 2026 (139-6, two-thirds of all MPs needed)…); **Nem** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('összegző módosító javaslat minősített többséget igénylő része elfogadva'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.07.13.18:18:22` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.07.13.18:18:22 --by Christopher`

### 19. `2026.06.22.16:07:12` Országgyűlés az interpellációs választ elfogadta

- **Why first (15 points):** tier 1; this year.
- **When / result:** 2026-06-22; Országgyűlés; Elfogadva; Igen 115, Nem 45, Abstain 2
- **On:** Hozzáférhetővé teszi-e a kormány az abortusztablettát?
- **Area:** abortion
- **Lobbies:** Igen: TISZA 115. Nem: Fidesz 33, KDNP 7, Mi Hazánk 5. Abstain: TISZA 2
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Országgyűlés az interpellációs választ elfogadta'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.22.16:07:12` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.22.16:07:12 --by Christopher`

### 20. `2026.06.08.16:04:34` Országgyűlés az interpellációs választ elfogadta

- **Why first (15 points):** tier 1; this year.
- **When / result:** 2026-06-08; Országgyűlés; Elfogadva; Igen 132, Nem 47
- **On:** Két igen és két nem? A Tisza-kormány mit gondol az azonos neműek házasságáról?
- **Area:** marriage and family
- **Lobbies:** Igen: TISZA 132. Nem: Fidesz 34, KDNP 8, Mi Hazánk 5
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Országgyűlés az interpellációs választ elfogadta'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `2026.06.08.16:04:34` in config/hu_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hu --confirm 2026.06.08.16:04:34 --by Christopher`

## By area (rank in the whole list)

- **abortion** (1 waiting): #19 `2026.06.22.16:07:12` 2026-06-22, 15 pts
- **parental rights and education** (1 waiting): #21 `2026.06.01.16:02:22` 2026-06-01, 15 pts
- **free speech and civil liberties** (11 waiting): #1 `2026.06.23.10:44:38` 2026-06-23, 90 pts; #2 `2026.06.23.10:44:01` 2026-06-23, 80 pts; #3 `2026.06.30.10:45:32` 2026-06-30, 75 pts
- **marriage and family** (1 waiting): #20 `2026.06.08.16:04:34` 2026-06-08, 15 pts
- **migration** (2 waiting): #23 `2026.06.22.16:43:58` 2026-06-22, -85 pts; #24 `2026.05.26.15:52:39` 2026-05-26, -85 pts
- **prostitution and trafficking** (1 waiting): #21 `2026.06.01.16:02:22` 2026-06-01, 15 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

