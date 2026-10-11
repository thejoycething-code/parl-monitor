# France 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 13 readings waiting in `config/fr_stance.yaml` (10 proposed, 0 procedural, 3 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-fr-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc fr --confirm an-17-8280 an-17-8431 an-17-7894 an-17-5729 an-17-2107 an-17-7432 an-17-5192 an-17-5728 an-17-5156 an-17-2106 --by Christopher

## Top 13

### 1. `an-17-8280` l'ensemble de la proposition de loi relative au droit à l'aide à mourir (lecture définitive).

- **Why first (134 points):** a vote on the whole text; the last such vote on its bill; watched bill DLR5L17N51670; values proposed: one tick to sign; close-ish: 291-241; split DEM, DR, ECOS, EPR and 7 more (88 against their group); meaning line ready; recent.
- **When / result:** 2026-07-15; Assemblée nationale; adopté; Pour 291, Contre 241, Abstain 29
- **On:** Fin de vie
- **Area:** assisted dying
- **Lobbies:** Pour: EPR 64, LFI-NFP 61, SOC 57, ECOS 33, DEM 20, HOR 16, RN 12, LIOT 10, GDR 10, DR 5, NI 3. Contre: RN 106, DR 41, EPR 18, HOR 18, UDDPLR 17, DEM 16, LIOT 8, NI 7, SOC 4, LFI-NFP 2, GDR 2, ECOS 2. Abstain: EPR 9, SOC 6, LIOT 4, GDR 3, LFI-NFP 3, DR 2, HOR 1, ECOS 1
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour -2, Contre +2
  - Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-8280 --by Christopher`

### 2. `an-17-8431` l'ensemble de la proposition de loi visant à protéger les mineurs des risques auxquels les expose l'utilisation des réseaux sociaux (texte d

- **Why first (115 points):** a vote on the whole text; the last such vote on its bill; watched bill DLR5L17N53187; values proposed: one tick to sign; split DEM, ECOS, GDR, UDDPLR (16 against their group); meaning line ready; recent.
- **When / result:** 2026-07-21; Assemblée nationale; adopté; Pour 279, Contre 81, Abstain 66
- **On:** Protéger les mineurs des risques auxquels les expose l’utilisation des réseaux sociaux
- **Area:** free speech and civil liberties
- **Lobbies:** Pour: EPR 83, DR 40, HOR 33, DEM 32, SOC 30, LIOT 22, ECOS 19, UDDPLR 8, NI 6, GDR 6. Contre: LFI-NFP 63, ECOS 7, UDDPLR 5, GDR 3, RN 2, DEM 1. Abstain: SOC 28, RN 14, ECOS 7, GDR 5, UDDPLR 4, DR 3, NI 2, DEM 2, LIOT 1
- Meaning: **Pour** = to pass DLR5L17N53187 (the under-15 social media rule and age checks) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour +2, Contre -2
  - Voted Pour on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): for passing it, with CitizenGO's position.
- **Flag:** On the bill's direction: Protecting minors online (under-15 rule, age checks); confirm the age-check design raises no speech concern.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-8431 --by Christopher`

### 3. `an-17-7894` l'ensemble de la proposition de loi relative au droit à l'aide à mourir (nouvelle lecture).

- **Why first (113 points):** a vote on the whole text; watched bill DLR5L17N51670; values proposed: one tick to sign; contested: 295-232; split DEM, DR, ECOS, EPR and 7 more (87 against their group); meaning line ready; this year.
- **When / result:** 2026-06-30; Assemblée nationale; adopté; Pour 295, Contre 232, Abstain 35
- **On:** Fin de vie
- **Area:** assisted dying
- **Lobbies:** Pour: EPR 66, LFI-NFP 62, SOC 57, ECOS 34, DEM 19, HOR 16, RN 14, GDR 10, LIOT 9, DR 5, NI 3. Contre: RN 103, DR 38, HOR 18, EPR 17, UDDPLR 17, DEM 16, LIOT 7, NI 7, SOC 4, LFI-NFP 2, GDR 2, ECOS 1. Abstain: EPR 7, LIOT 6, SOC 5, RN 5, DR 3, GDR 3, LFI-NFP 3, ECOS 2, HOR 1
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour -2, Contre +2
  - Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-7894 --by Christopher`

### 4. `an-17-5729` l'ensemble de la proposition de loi relative au droit à l'aide à mourir (deuxième lecture).

- **Why first (113 points):** a vote on the whole text; watched bill DLR5L17N51670; values proposed: one tick to sign; contested: 299-226; split DEM, DR, ECOS, EPR and 7 more (79 against their group); meaning line ready; this year.
- **When / result:** 2026-02-25; Assemblée nationale; adopté; Pour 299, Contre 226, Abstain 37
- **On:** Fin de vie
- **Area:** assisted dying
- **Lobbies:** Pour: EPR 64, LFI-NFP 62, SOC 60, ECOS 35, DEM 20, RN 17, HOR 14, GDR 11, LIOT 8, DR 5, NI 3. Contre: RN 102, DR 42, HOR 18, UDDPLR 17, EPR 14, DEM 12, NI 7, LIOT 6, SOC 4, GDR 2, LFI-NFP 1, ECOS 1. Abstain: EPR 9, LIOT 8, DEM 4, GDR 4, SOC 3, RN 3, DR 2, HOR 2, ECOS 2
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour -2, Contre +2
  - Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-5729 --by Christopher`

### 5. `an-17-2107` l’ensemble de la proposition de loi relative au droit à l’aide à mourir (première lecture).

- **Why first (100 points):** a vote on the whole text; watched bill DLR5L17N51670; values proposed: one tick to sign; split DEM, DR, ECOS, EPR and 7 more (73 against their group); meaning line ready.
- **When / result:** 2025-05-27; Assemblée nationale; adopté; Pour 305, Contre 199, Abstain 57
- **On:** Fin de vie
- **Area:** assisted dying
- **Lobbies:** Pour: EPR 64, LFI-NFP 62, SOC 59, ECOS 33, DEM 20, RN 19, HOR 14, GDR 12, LIOT 11, DR 7, NI 4. Contre: RN 101, DR 34, PO847173 16, HOR 13, EPR 11, DEM 9, NI 5, SOC 4, LIOT 3, GDR 1, LFI-NFP 1, ECOS 1. Abstain: EPR 14, LIOT 9, DR 8, DEM 7, HOR 6, GDR 3, RN 3, LFI-NFP 3, SOC 2, NI 1, ECOS 1
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour -2, Contre +2
  - Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-2107 --by Christopher`

### 6. `an-17-7432` la motion de rejet péalable, déposée par M. Patrick Hetzel, de la proposition de loi relative au droit à l'aide à mourir (nouvelle lecture).

- **Why first (86 points):** a motion to reject the text; watched bill DLR5L17N51670; values proposed: one tick to sign; split EPR, HOR (10 against their group); meaning line ready; this year.
- **When / result:** 2026-06-22; Assemblée nationale; rejeté; Pour 91, Contre 139, Abstain 1
- **On:** Fin de vie
- **Area:** assisted dying
- **Lobbies:** Pour: RN 60, DR 10, UDDPLR 10, EPR 7, HOR 3, NI 1. Contre: LFI-NFP 42, SOC 33, EPR 23, ECOS 21, DEM 10, HOR 6, GDR 2, LIOT 2. Abstain: SOC 1
- Meaning: **Pour** = to reject DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) outright at this stage (a motion to reject); **Contre** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour +2, Contre -2
  - Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-7432 --by Christopher`

### 7. `an-17-5192` l'ensemble de la proposition de loi visant à protéger les mineurs des risques auxquels les expose l'utilisation des réseaux sociaux (premièr

- **Why first (84 points):** a vote on the whole text; watched bill DLR5L17N53187; values proposed: one tick to sign; split ECOS (2 against their group); meaning line ready; this year.
- **When / result:** 2026-01-26; Assemblée nationale; adopté; Pour 130, Contre 21, Abstain 6
- **On:** Protéger les mineurs des risques auxquels les expose l’utilisation des réseaux sociaux
- **Area:** free speech and civil liberties
- **Lobbies:** Pour: EPR 61, RN 22, HOR 11, SOC 10, DR 9, DEM 8, ECOS 3, NI 2, LIOT 2, UDDPLR 2. Contre: LFI-NFP 19, ECOS 2. Abstain: SOC 2, GDR 2, ECOS 2
- Meaning: **Pour** = to pass DLR5L17N53187 (the under-15 social media rule and age checks) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour +2, Contre -2
  - Voted Pour on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): for passing it, with CitizenGO's position.
- **Flag:** On the bill's direction: Protecting minors online (under-15 rule, age checks); confirm the age-check design raises no speech concern.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-5192 --by Christopher`

### 8. `an-17-5728` l'ensemble de la proposition de loi visant à garantir l'égal accès de tous à l'accompagnement et aux soins palliatifs (deuxième lecture).

- **Why first (75 points):** a vote on the whole text; the last such vote on its bill; watched bill DLR5L17N51672; values proposed: one tick to sign; near-unanimous (491-0, lower); meaning line ready; this year.
- **When / result:** 2026-02-25; Assemblée nationale; adopté; Pour 491, Contre 0, Abstain 69
- **On:** Soins palliatifs et d’accompagnement
- **Area:** assisted dying
- **Lobbies:** Pour: RN 122, EPR 88, SOC 69, DR 47, DEM 36, HOR 34, ECOS 34, LIOT 22, UDDPLR 17, GDR 11, NI 9, LFI-NFP 2. Abstain: LFI-NFP 67, ECOS 2
- Meaning: **Pour** = to pass DLR5L17N51672 (Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law; promulgated 26 May 2026) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour +2, Contre -2
  - Voted Pour on DLR5L17N51672 (Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law): for passing it, with CitizenGO's position.
- **Flag:** On the bill's direction: Palliative care is CitizenGO's alternative to assisted dying; the bill was the companion of the aide a mourir law: confirm.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-5728 --by Christopher`

### 9. `an-17-5156` sur la motion de rejet préalable, déposée par Mme Mathilde Panot, de la proposition de loi visant à protéger les mineurs des risques auxquel

- **Why first (75 points):** a motion to reject the text; watched bill DLR5L17N53187; values proposed: one tick to sign; meaning line ready; this year.
- **When / result:** 2026-01-26; Assemblée nationale; rejeté; Pour 25, Contre 109, Abstain 2
- **On:** Protéger les mineurs des risques auxquels les expose l’utilisation des réseaux sociaux
- **Area:** free speech and civil liberties
- **Lobbies:** Pour: LFI-NFP 25. Contre: EPR 55, RN 14, SOC 11, ECOS 8, HOR 7, DR 6, DEM 5, NI 2, LIOT 1. Abstain: GDR 2
- Meaning: **Pour** = to reject DLR5L17N53187 (the under-15 social media rule and age checks) outright at this stage (a motion to reject); **Contre** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour -2, Contre +2
  - Voted Pour on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): for rejecting it, against CitizenGO's position.
- **Flag:** On the bill's direction: Protecting minors online (under-15 rule, age checks); confirm the age-check design raises no speech concern.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-5156 --by Christopher`

### 10. `an-17-2106` l’ensemble de la proposition de loi visant à garantir l'égal accès de tous à l’accompagnement et aux soins palliatifs (première lecture).

- **Why first (60 points):** a vote on the whole text; watched bill DLR5L17N51672; values proposed: one tick to sign; near-unanimous (560-0, lower); meaning line ready.
- **When / result:** 2025-05-27; Assemblée nationale; adopté; Pour 560, Contre 0, Abstain 3
- **On:** Soins palliatifs et d’accompagnement
- **Area:** assisted dying
- **Lobbies:** Pour: RN 121, EPR 90, LFI-NFP 67, SOC 65, DR 49, ECOS 36, DEM 35, HOR 33, LIOT 23, PO847173 16, GDR 15, NI 10. Abstain: RN 2, DEM 1
- Meaning: **Pour** = to pass DLR5L17N51672 (Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law; promulgated 26 May 2026) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Pour +2, Contre -2
  - Voted Pour on DLR5L17N51672 (Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law): for passing it, with CitizenGO's position.
- **Flag:** On the bill's direction: Palliative care is CitizenGO's alternative to assisted dying; the bill was the companion of the aide a mourir law: confirm.
- **Sign:** `python3 tools/country_5ca.py --cc fr --confirm an-17-2106 --by Christopher`

### 11. `an-17-1725` l'ensemble de la proposition de loi visant à lutter contre la pédocriminalité (première lecture).

- **Why first (38 points):** a vote on the whole text; the last such vote on its bill; tier 1; near-unanimous (56-0, lower); meaning line quotes the source.
- **When / result:** 2025-05-15; Assemblée nationale; adopté; Pour 56, Contre 0
- **On:** Lutter contre la pédocriminalité
- **Area:** prostitution and trafficking
- **Lobbies:** Pour: LIOT 13, RN 10, DEM 7, SOC 6, LFI-NFP 5, HOR 4, GDR 3, ECOS 3, EPR 2, PO847173 2, DR 1
- Meaning: **Pour** = to pass the text “l'ensemble de la proposition de loi visant à lutter contre la pédocriminalité (première…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L17N50627: CitizenGO's position on 'Lutter contre la pédocriminalité' needs a human reading. Add a `bill_directions` line or write yea/nay here.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `an-17-1725` in config/fr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc fr --confirm an-17-1725 --by Christopher`

### 12. `an-17-4839` l'ensemble de la proposition de loi visant à reconnaître le préjudice subi par les personnes condamnées sur le fondement de la législation p

- **Why first (33 points):** a vote on the whole text; tier 1; near-unanimous (93-0, lower); meaning line quotes the source; this year.
- **When / result:** 2025-12-18; Assemblée nationale; adopté; Pour 93, Contre 0
- **Area:** abortion
- **Lobbies:** Pour: LFI-NFP 21, SOC 16, EPR 15, ECOS 11, DR 7, DEM 7, HOR 6, RN 5, UDDPLR 2, LIOT 2, NI 1
- Meaning: **Pour** = to pass the text “l'ensemble de la proposition de loi visant à reconnaître le préjudice subi par les…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for this item: CitizenGO's position on 'l'ensemble de la proposition de loi visant à reconnaître le préjudice subi par les personnes condamnées sur le fondement de la législation p
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `an-17-4839` in config/fr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc fr --confirm an-17-4839 --by Christopher`

### 13. `an-17-5244` l'ensemble de la proposition de loi visant à réparer les préjudices causés par la transplantation de mineurs de La Réunion en France hexagon

- **Why first (-57 points):** a vote on the whole text; the last such vote on its bill; tier 1; near-unanimous (72-0, lower); meaning line quotes the source; this year; collated-only area: places nobody (lowest).
- **When / result:** 2026-01-28; Assemblée nationale; adopté; Pour 72, Contre 0
- **On:** Réparer les préjudices causés par la transplantation de mineurs de La Réunion en France hexagonale de 1962 à 1984
- **Area:** organ donation
- **Lobbies:** Pour: LFI-NFP 15, SOC 12, ECOS 9, RN 8, DEM 7, HOR 6, GDR 5, DR 4, EPR 4, LIOT 1, UDDPLR 1
- Meaning: **Pour** = to pass the text “Réparer les préjudices causés par la transplantation de mineurs de La Réunion en France…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L17N51845: CitizenGO's position on 'Réparer les préjudices causés par la transplantation de mineurs de La Réunion en France hexagonale de 1962 à 1984' needs a human reading
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `an-17-5244` in config/fr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc fr --confirm an-17-5244 --by Christopher`

## By area (rank in the whole list)

- **abortion** (1 waiting): #12 `an-17-4839` 2025-12-18, 33 pts
- **assisted dying** (7 waiting): #1 `an-17-8280` 2026-07-15, 134 pts; #3 `an-17-7894` 2026-06-30, 113 pts; #4 `an-17-5729` 2026-02-25, 113 pts
- **free speech and civil liberties** (3 waiting): #2 `an-17-8431` 2026-07-21, 115 pts; #7 `an-17-5192` 2026-01-26, 84 pts; #9 `an-17-5156` 2026-01-26, 75 pts
- **prostitution and trafficking** (1 waiting): #11 `an-17-1725` 2025-05-15, 38 pts
- **organ donation** (1 waiting): #13 `an-17-5244` 2026-01-28, -57 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

