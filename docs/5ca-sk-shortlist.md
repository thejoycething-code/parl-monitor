# Slovakia 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 43 readings waiting in `config/sk_stance.yaml` (3 proposed, 10 procedural, 30 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-sk-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc sk --confirm 56965 56684 56254 --by Christopher

## Top 20

### 1. `56965` Vládny návrh ústavného zákona, ktorým sa mení a dopĺňa Ústava Slovenskej republiky č. 460/1992 Zb. v znení neskorších predpisov (tlač 733) -

- **Why first (85 points):** a vote on the whole text; the last such vote on its bill; watched bill 9/733; values proposed: one tick to sign; meaning line ready.
- **When / result:** 2025-09-26; Národná rada; Návrh prešiel; Za 90, Proti 7
- **On:** Vládny návrh ústavného zákona, ktorým sa mení a dopĺňa Ústava Slovenskej republiky č. 460/1992 Zb. v znení neskorších predpisov
- **Area:** sex-based rights, parental rights and education, marriage and family, surrogacy and embryology
- **Lobbies:** Za: SMER - SD 41, HLAS - SD 25, KDH 9, SNS 8, ? 4, SLOVENSKO 3. Proti: SaS 7
- Meaning: **Za** = to pass 9/733 (Government constitutional amendment, adopted 26 September 2025 (vote 56965: 90 for, 7 against)) as a whole; **Proti** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Proti -2
  - Voted Za on 9/733 (Government constitutional amendment, adopted 26 September 2025 (vote 56965: 90 for, 7 agai): for passing it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc sk --confirm 56965 --by Christopher`

### 2. `56684` Vládny návrh ústavného zákona, ktorým sa mení a dopĺňa Ústava Slovenskej republiky č. 460/1992 Zb. v znení neskorších predpisov (tlač 733) -

- **Why first (73 points):** a motion to reject the text; watched bill 9/733; values proposed: one tick to sign; split SaS (1 against their group); meaning line ready.
- **When / result:** 2025-06-17; Národná rada; Návrh neprešiel; Za 45, Proti 91
- **On:** Vládny návrh ústavného zákona, ktorým sa mení a dopĺňa Ústava Slovenskej republiky č. 460/1992 Zb. v znení neskorších predpisov
- **Area:** sex-based rights, parental rights and education, marriage and family, surrogacy and embryology
- **Lobbies:** Za: PS 33, SaS 11, ? 1. Proti: SMER - SD 41, HLAS - SD 25, KDH 10, SNS 8, ? 4, SLOVENSKO 2, SaS 1
- Meaning: **Za** = to reject 9/733 (Government constitutional amendment, adopted 26 September 2025 (vote 56965: 90 for, 7 against)) outright at this stage (a motion to reject); **Proti** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Proti +2
  - Voted Za on 9/733 (Government constitutional amendment, adopted 26 September 2025 (vote 56965: 90 for, 7 agai): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc sk --confirm 56684 --by Christopher`

### 3. `57935` Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA a Lucie PLAVÁKOVEJ na vydanie zákona, ktorým sa mení zákon č. 36/200

- **Why first (69 points):** a vote on the whole text; the last such vote on its bill; tier 1; close-ish: 49-41; this year.
- **When / result:** 2026-05-07; Národná rada; Návrh neprešiel; Za 49, Proti 41, Abstain 35
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA a Lucie PLAVÁKOVEJ na vydanie zákona, ktorým sa mení zákon č. 36/2005 Z. z. o rodine a o zmene a doplnení niektorých zákonov v z
- **Area:** marriage and family
- **Lobbies:** Za: PS 26, SLOVENSKO 9, KDH 6, SaS 6, ? 2. Proti: SMER - SD 38, SNS 2, ? 1. Abstain: HLAS - SD 25, SNS 5, ? 3, SMER - SD 2
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/1218: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA a Lucie PLAVÁKOVEJ na vydanie zákona, ktorým sa mení zákon č. 36/200' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `57935` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 57935 --by Christopher`

### 4. `56254` Vládny návrh ústavného zákona, ktorým sa mení a dopĺňa Ústava Slovenskej republiky č. 460/1992 Zb. v znení neskorších predpisov (tlač 733) -

- **Why first (65 points):** a vote on the whole text; watched bill 9/733; values proposed: one tick to sign.
- **When / result:** 2025-04-09; Národná rada; Návrh prešiel; Za 81, Proti 40, Abstain 22
- **On:** Vládny návrh ústavného zákona, ktorým sa mení a dopĺňa Ústava Slovenskej republiky č. 460/1992 Zb. v znení neskorších predpisov
- **Area:** sex-based rights, parental rights and education, marriage and family, surrogacy and embryology
- **Lobbies:** Za: SMER - SD 41, HLAS - SD 26, SNS 8, ? 4, SLOVENSKO 2. Proti: PS 29, SaS 10, ? 1. Abstain: KDH 11, SLOVENSKO 11
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** Za +2, Proti -2
  - Voted Za on 9/733 (Government constitutional amendment, adopted 26 September 2025 (vote 56965: 90 for, 7 agai): for passing it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc sk --confirm 56254 --by Christopher`

### 5. `55270` Návrh poslancov Národnej rady Slovenskej republiky Vladimíry MARCINKOVEJ, Vladimíra LEDECKÉHO a Ondreja DOSTÁLA na vydanie zákona, ktorým sa

- **Why first (65 points):** a vote on the whole text; the last such vote on its bill; tier 1; close: 44-44.
- **When / result:** 2024-09-24; Národná rada; Návrh neprešiel; Za 44, Proti 44, Abstain 45
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Vladimíry MARCINKOVEJ, Vladimíra LEDECKÉHO a Ondreja DOSTÁLA na vydanie zákona, ktorým sa mení zákon č. 36/2005 Z. z. o rodine a o zmene a doplnení n
- **Area:** marriage and family
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/418: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Vladimíry MARCINKOVEJ, Vladimíra LEDECKÉHO a Ondreja DOSTÁLA na vydanie zákona, ktorým sa' ne
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `55270` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 55270 --by Christopher`

### 6. `58027` Návrh poslancov Národnej rady Slovenskej republiky Milana GARAJA, Dagmar KRAMPLOVEJ, Andreja DANKA a Adama LUČANSKÉHO na vydanie zákona, kto

- **Why first (55 points):** a vote on the whole text; the last such vote on its bill; tier 1; this year.
- **When / result:** 2026-06-02; Národná rada; Návrh prešiel; Za 79, Proti 42, Abstain 8
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Milana GARAJA, Dagmar KRAMPLOVEJ, Andreja DANKA a Adama LUČANSKÉHO na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rodine a o zme
- **Area:** marriage and family
- **Lobbies:** Za: SMER - SD 41, HLAS - SD 25, SNS 8, ? 5. Proti: PS 24, KDH 12, SLOVENSKO 5, ? 1. Abstain: SaS 7, ? 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/1272: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Milana GARAJA, Dagmar KRAMPLOVEJ, Andreja DANKA a Adama LUČANSKÉHO na vydanie zákona, kto' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `58027` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 58027 --by Christopher`

### 7. `56672` Návrh poslancov Národnej rady Slovenskej republiky Anny ZÁBORSKEJ a Richarda VAŠEČKU na prijatie uznesenia Národnej rady Slovenskej republik

- **Why first (53 points):** a vote on the whole text; the last such vote on its bill; tier 1; split PS (1 against their group).
- **When / result:** 2025-06-17; Národná rada; Návrh neprešiel; Za 27, Proti 41, Abstain 74
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Anny ZÁBORSKEJ a Richarda VAŠEČKU na prijatie uznesenia Národnej rady Slovenskej republiky k odmietnutiu financovania tzv. "potratove] turistiky" a k
- **Area:** abortion
- **Lobbies:** Za: SLOVENSKO 13, KDH 8, SMER - SD 4, PS 1, ? 1. Proti: PS 31, SaS 9, ? 1. Abstain: SMER - SD 37, HLAS - SD 26, SNS 8, ? 3
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/843: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Anny ZÁBORSKEJ a Richarda VAŠEČKU na prijatie uznesenia Národnej rady Slovenskej republik' ne
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `56672` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 56672 --by Christopher`

### 8. `56356` Návrh poslancov Národnej rady Slovenskej republiky Anny ZÁBORSKEJ a Richarda VAŠEČKU na vydanie zákona, ktorým sa mení zákon č. 73/1986 Zb. 

- **Why first (53 points):** a vote on the whole text; the last such vote on its bill; tier 1; split SMER - SD (1 against their group).
- **When / result:** 2025-04-15; Národná rada; Návrh neprešiel; Za 25, Proti 41, Abstain 74
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Anny ZÁBORSKEJ a Richarda VAŠEČKU na vydanie zákona, ktorým sa mení zákon č. 73/1986 Zb. o umelom prerušení tehotenstva v znení neskorších predpisov
- **Area:** abortion
- **Lobbies:** Za: SLOVENSKO 13, KDH 11, SMER - SD 1. Proti: PS 31, SaS 9, SMER - SD 1. Abstain: SMER - SD 38, HLAS - SD 24, SNS 8, ? 4
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/593: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Anny ZÁBORSKEJ a Richarda VAŠEČKU na vydanie zákona, ktorým sa mení zákon č. 73/1986 Zb. ' ne
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `56356` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 56356 --by Christopher`

### 9. `55317` Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA, Lucie PLAVÁKOVEJ a Zory JAUROVEJ na vydanie zákona, ktorým sa mení 

- **Why first (53 points):** a vote on the whole text; the last such vote on its bill; tier 1; contested: 36-52.
- **When / result:** 2024-10-01; Národná rada; Návrh neprešiel; Za 36, Proti 52, Abstain 49
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA, Lucie PLAVÁKOVEJ a Zory JAUROVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 308/1991 Zb. o slobode náboženskej viery a
- **Area:** religious freedom
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/393: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA, Lucie PLAVÁKOVEJ a Zory JAUROVEJ na vydanie zákona, ktorým sa mení ' ne
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `55317` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 55317 --by Christopher`

### 10. `57919` Návrh poslankyne Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rod

- **Why first (52 points):** a vote on the whole text; tier 1; split PS, SMER - SD (2 against their group); this year.
- **When / result:** 2026-05-06; Národná rada; Návrh prešiel; Za 76, Proti 38, Abstain 20
- **On:** Návrh poslankyne Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rodine a o zmene a doplnení niektorých zákonov v znení neskorší
- **Area:** marriage and family
- **Lobbies:** Za: SMER - SD 39, HLAS - SD 24, SNS 8, ? 4, PS 1. Proti: PS 27, SaS 9, SMER - SD 1, ? 1. Abstain: SLOVENSKO 10, KDH 8, ? 2
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/1254: CitizenGO's position on 'Návrh poslankyne Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rod' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `57919` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 57919 --by Christopher`

### 11. `58272` Návrh poslankyne Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rod

- **Why first (45 points):** a vote on the whole text; the last such vote on its bill; tier 1; near-unanimous (106-1, lower); recent.
- **When / result:** 2026-09-16; Národná rada; Návrh prešiel; Za 106, Proti 1, Abstain 34
- **On:** Návrh poslankyne Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rodine a o zmene a doplnení niektorých zákonov v znení neskorší
- **Area:** marriage and family
- **Lobbies:** Za: SMER - SD 41, PS 27, HLAS - SD 25, SNS 9, ? 4. Proti: SLOVENSKO 1. Abstain: KDH 12, SaS 11, SLOVENSKO 8, ? 3
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/1254: CitizenGO's position on 'Návrh poslankyne Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rod' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `58272` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 58272 --by Christopher`

### 12. `58252` Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a Zdenky MAČICOVEJ na 

- **Why first (45 points):** a vote on the whole text; the last such vote on its bill; tier 1; near-unanimous (78-0, lower); recent.
- **When / result:** 2026-09-15; Národná rada; Návrh prešiel; Za 78, Proti 0, Abstain 59
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a Zdenky MAČICOVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z.
- **Area:** marriage and family
- **Lobbies:** Za: SMER - SD 40, HLAS - SD 25, SNS 9, ? 4. Abstain: PS 29, SaS 11, KDH 9, SLOVENSKO 8, ? 2
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/1252: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a Zdenky MAČICOVEJ na ' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `58252` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 58252 --by Christopher`

### 13. `57917` Návrh poslancov Národnej rady Slovenskej republiky Milana GARAJA, Dagmar KRAMPLOVEJ, Andreja DANKA a Adama LUČANSKÉHO na vydanie zákona, kto

- **Why first (45 points):** a vote on the whole text; tier 1; this year.
- **When / result:** 2026-05-05; Národná rada; Návrh prešiel; Za 77, Proti 39, Abstain 19
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Milana GARAJA, Dagmar KRAMPLOVEJ, Andreja DANKA a Adama LUČANSKÉHO na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rodine a o zme
- **Area:** marriage and family
- **Lobbies:** Za: SMER - SD 41, HLAS - SD 24, SNS 8, ? 4. Proti: PS 29, KDH 9, ? 1. Abstain: SaS 9, SLOVENSKO 7, ? 2, KDH 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/1272: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Milana GARAJA, Dagmar KRAMPLOVEJ, Andreja DANKA a Adama LUČANSKÉHO na vydanie zákona, kto' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `57917` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 57917 --by Christopher`

### 14. `55364` Návrh poslanca Narodnej rady Slovenskej republiky Rastislava KRÁTKEHO na prijatie uznesenia Národnej rady Slovenskej republiky k uzneseniu E

- **Why first (45 points):** a vote on the whole text; the last such vote on its bill; tier 1.
- **When / result:** 2024-10-03; Národná rada; Návrh neprešiel; Za 17, Proti 31, Abstain 73
- **On:** Návrh poslanca Národnej rady Slovenskej republiky Rastislava KRÁTKEHO na prijatie uznesenia Národnej rady Slovenskej republiky k uzneseniu Európskeho parlamentu z 11. aprila 2024 o začlenení práva na
- **Area:** abortion
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/266: CitizenGO's position on 'Návrh poslanca Národnej rady Slovenskej republiky Rastislava KRÁTKEHO na prijatie uznesenia Národnej rady Slovenskej republiky k uzneseniu E' ne
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `55364` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 55364 --by Christopher`

### 15. `55671` Vládny návrh zákona, ktorým sa mení a dopĺňa zákon č. 370/2019 Z. z. o finančnej podpore činnosti cirkví a náboženských spoločností (tlač 51

- **Why first (38 points):** a vote on the whole text; the last such vote on its bill; tier 1; near-unanimous (96-3, lower); meaning line quotes the source.
- **When / result:** 2024-11-27; Národná rada; Návrh prešiel; Za 96, Proti 3, Abstain 35
- **On:** Vládny návrh zákona, ktorým sa mení a dopĺňa zákon č. 370/2019 Z. z. o finančnej podpore činnosti cirkví a náboženských spoločností
- **Area:** religious freedom
- **Lobbies:** Za: SMER - SD 41, HLAS - SD 27, SLOVENSKO 11, KDH 9, SNS 8. Proti: SaS 3. Abstain: PS 30, SaS 3, ? 1, SLOVENSKO 1
- Meaning: **Za** = to pass the text “Vládny návrh zákona, ktorým sa mení a dopĺňa zákon č. 370/2019 Z. z. o finančnej podpore…” as a whole; **Proti** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/511: CitizenGO's position on 'Vládny návrh zákona, ktorým sa mení a dopĺňa zákon č. 370/2019 Z. z. o finančnej podpore činnosti cirkví a náboženských spoločností' needs a hum
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `55671` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 55671 --by Christopher`

### 16. `58250` Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a Zdenky MAČICOVEJ na 

- **Why first (30 points):** amendment-level (lower); tier 1; close: 52-50; recent.
- **When / result:** 2026-09-15; Národná rada; Návrh neprešiel; Za 52, Proti 50, Abstain 39
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a Zdenky MAČICOVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z.
- **Area:** marriage and family
- **Lobbies:** Za: PS 29, SaS 11, KDH 10, ? 2. Proti: SMER - SD 40, SNS 7, ? 3. Abstain: HLAS - SD 25, SLOVENSKO 11, SNS 2, ? 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: An amendment, an article or one point ('Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a '): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `58250` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 58250 --by Christopher`

### 17. `57870` Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a Zdenky MAČICOVEJ na 

- **Why first (30 points):** a vote on the whole text; tier 1; near-unanimous (144-0, lower); this year.
- **When / result:** 2026-05-05; Národná rada; Návrh prešiel; Za 144, Proti 0
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a Zdenky MAČICOVEJ na vydanie zákona, ktorým sa mení a dopĺňa zákon č. 36/2005 Z.
- **Area:** marriage and family
- **Lobbies:** Za: SMER - SD 41, PS 31, HLAS - SD 24, SaS 11, SLOVENSKO 11, KDH 10, SNS 8, ? 8
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/1252: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ, Ľubice LAŠŠÁKOVEJ, Aleny NOVÁKOVEJ, Jozefa CECHA a Zdenky MAČICOVEJ na ' n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `57870` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 57870 --by Christopher`

### 18. `55573` Návrh poslancov Národnej rady Slovenskej republiky Jany HANULlAKOVEJ, Veroniky VESLÁROVEJ a Richarda DUBOVICKÉHO na vydanie zákona, ktorým s

- **Why first (30 points):** tier 1; close: 47-45.
- **When / result:** 2024-11-05; Národná rada; Návrh neprešiel; Za 47, Proti 45, Abstain 47
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Jany HANULlAKOVEJ, Veroniky VESLÁROVEJ a Richarda DUBOVICKÉHO na vydanie zákona, ktorým sa dopĺňa zákon č. 36/2005 Z. z. o rodine a o zmene a doplnen
- **Area:** sex-based rights, marriage and family
- **Lobbies:** Za: PS 28, SaS 11, KDH 8. Proti: SMER - SD 40, SNS 5. Abstain: HLAS - SD 27, SLOVENSKO 12, ? 4, SNS 3, SMER - SD 1
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: The kind of vote could not be read from its wording ('Návrh poslancov Národnej rady Slovenskej republiky Jany HANULlAKOVEJ, Veroniky VESLÁROVEJ a Richarda DUBOVICKÉHO na vyda'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `55573` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 55573 --by Christopher`

### 19. `55399` Vládny návrh zákona, ktorým sa mení a dopĺňa zákon č. 370/2019 Z. z. o finančnej podpore činnosti cirkví a náboženských spoločností (tlač 51

- **Why first (28 points):** a vote on the whole text; tier 1; near-unanimous (99-1, lower); meaning line quotes the source.
- **When / result:** 2024-10-23; Národná rada; Návrh prešiel; Za 99, Proti 1, Abstain 36
- **On:** Vládny návrh zákona, ktorým sa mení a dopĺňa zákon č. 370/2019 Z. z. o finančnej podpore činnosti cirkví a náboženských spoločností
- **Area:** religious freedom
- Meaning: **Za** = to pass the text “Vládny návrh zákona, ktorým sa mení a dopĺňa zákon č. 370/2019 Z. z. o finančnej podpore…” as a whole; **Proti** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/511: CitizenGO's position on 'Vládny návrh zákona, ktorým sa mení a dopĺňa zákon č. 370/2019 Z. z. o finančnej podpore činnosti cirkví a náboženských spoločností' needs a hum
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `55399` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 55399 --by Christopher`

### 20. `56534` Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA a Lucie PLAVÁKOVEJ na vydanie zákona, ktorým sa mení zákon č. 36/200

- **Why first (25 points):** a vote on the whole text; tier 1; near-unanimous (42-0, lower).
- **When / result:** 2025-06-03; Národná rada; Návrh neprešiel; Za 42, Proti 0, Abstain 97
- **On:** Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA a Lucie PLAVÁKOVEJ na vydanie zákona, ktorým sa mení zákon č. 36/2005 Z. z. o rodine a o zmene a doplnení niektorých zákonov v z
- **Area:** marriage and family
- **Lobbies:** Za: PS 29, SaS 11, ? 1, SLOVENSKO 1. Abstain: SMER - SD 39, HLAS - SD 26, KDH 11, SLOVENSKO 9, SNS 8, ? 4
- Meaning: none yet (no line from a person, the judge or the rules).
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 9/673: CitizenGO's position on 'Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA a Lucie PLAVÁKOVEJ na vydanie zákona, ktorým sa mení zákon č. 36/200' ne
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `56534` in config/sk_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc sk --confirm 56534 --by Christopher`

## By area (rank in the whole list)

- **abortion** (4 waiting): #7 `56672` 2025-06-17, 53 pts; #8 `56356` 2025-04-15, 53 pts; #14 `55364` 2024-10-03, 45 pts
- **sex-based rights** (13 waiting): #1 `56965` 2025-09-26, 85 pts; #2 `56684` 2025-06-17, 73 pts; #4 `56254` 2025-04-09, 65 pts
- **parental rights and education** (12 waiting): #1 `56965` 2025-09-26, 85 pts; #2 `56684` 2025-06-17, 73 pts; #4 `56254` 2025-04-09, 65 pts
- **religious freedom** (6 waiting): #9 `55317` 2024-10-01, 53 pts; #15 `55671` 2024-11-27, 38 pts; #19 `55399` 2024-10-23, 28 pts
- **marriage and family** (33 waiting): #1 `56965` 2025-09-26, 85 pts; #2 `56684` 2025-06-17, 73 pts; #3 `57935` 2026-05-07, 69 pts
- **surrogacy and embryology** (12 waiting): #1 `56965` 2025-09-26, 85 pts; #2 `56684` 2025-06-17, 73 pts; #4 `56254` 2025-04-09, 65 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

