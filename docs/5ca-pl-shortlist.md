# Poland 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 185 readings waiting in `config/pl_stance.yaml` (24 proposed, 4 procedural, 157 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-pl-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc pl --confirm pl-10-65-10 pl-10-65-11 pl-10-21-38 pl-10-58-103 pl-10-58-62 pl-10-45-80 pl-10-15-9 pl-10-61-40 pl-10-58-54 pl-10-58-63 pl-10-51-72 pl-10-51-73 pl-10-30-16 pl-10-41-30 pl-10-45-47 pl-10-43-70 pl-10-15-8 pl-10-30-12 pl-10-6-15 pl-10-6-16 --by Christopher

## Top 20

### 1. `pl-10-65-10` głosowanie nad ponownym uchwaleniem ustawy

- **Why first (119 points):** a vote on the whole text; the last such vote on its bill; watched bill 10/2110; values proposed: one tick to sign; close-ish: 232-199; meaning line ready; feeds brief pl-rzadowy-projekt-ustawy-o-statusie-osoby-najblizs-10-2110 (NOT READY until signed); recent.
- **When / result:** 2026-09-17; Sejm; Za 232, Przeciw 199
- **On:** Pkt. 27 Sprawozdanie Komisji o wniosku Prezydenta Rzeczypospolitej Polskiej o ponowne rozpatrzenie ustawy z dnia 29 maja 2026 r. o statusie osoby najbliższej w związku i umowie o wspólnym pożyciu (dru
- **Area:** marriage and family
- Meaning: **Za** = to pass 10/2110 (registered cohabitation contracts) again, overriding the President's veto; **Przeciw** = against passing it again, so the veto stands. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/2110 (O statusie osoby najbliższej (government): registered cohabitation contracts): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-65-10 --by Christopher`

### 2. `pl-10-65-11` głosowanie nad ponownym uchwaleniem ustawy

- **Why first (119 points):** a vote on the whole text; the last such vote on its bill; watched bill 10/2111; values proposed: one tick to sign; close-ish: 232-200; meaning line ready; feeds brief pl-rzadowy-projekt-ustawy-przepisy-wprowadzajace-us-10-2111 (NOT READY until signed); recent.
- **When / result:** 2026-09-17; Sejm; Za 232, Przeciw 200
- **On:** Pkt. 28 Sprawozdanie Komisji o wniosku Prezydenta Rzeczypospolitej Polskiej o ponowne rozpatrzenie ustawy z dnia 29 maja 2026 r. - Przepisy wprowadzające ustawę o statusie osoby najbliższej w związku
- **Area:** marriage and family
- Meaning: **Za** = to pass 10/2111 (Implementing act for 10/2110) again, overriding the President's veto; **Przeciw** = against passing it again, so the veto stands. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/2111 (Implementing act for 10/2110): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-65-11 --by Christopher`

### 3. `pl-10-21-38` wniosek o odrzucenie projektu w pierwszym czytaniu.

- **Why first (110 points):** a motion to reject the text; the last such vote on its bill; watched bill 10/611; values proposed: one tick to sign; close: 216-232; meaning line ready; feeds brief pl-poselski-projekt-ustawy-o-zmianie-ustawy-kodeks-10-611 (NOT READY until signed).
- **When / result:** 2024-11-08; Sejm; Za 216, Przeciw 232, Abstain 4
- **On:** Pkt. 7 Pierwsze czytanie poselskiego projektu ustawy o zmianie ustawy - Kodeks karny (druk nr 611)
- **Area:** abortion
- Meaning: **Za** = to reject 10/611 (partial decriminalisation of abortion and of helping a woman to one) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/611 (Kodeks karny: partial decriminalisation of abortion and of helping a woman to one): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-21-38 --by Christopher`

### 4. `pl-10-58-103` głosowanie nad całością projektu.

- **Why first (104 points):** a vote on the whole text; watched bill 10/2111; values proposed: one tick to sign; close-ish: 230-200; meaning line ready; feeds brief pl-rzadowy-projekt-ustawy-przepisy-wprowadzajace-us-10-2111 (NOT READY until signed); this year.
- **When / result:** 2026-05-29; Sejm; Za 230, Przeciw 200, Abstain 1
- **On:** Pkt. 6 Sprawozdanie Komisji o rządowym projekcie ustawy - Przepisy wprowadzające ustawę o statusie osoby najbliższej w związku i umowie o wspólnym pożyciu (druki nr 2111, 2594 i 2594-A)
- **Area:** marriage and family
- Meaning: **Za** = to pass 10/2111 (Implementing act for 10/2110) as a whole; **Przeciw** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/2111 (Implementing act for 10/2110): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-58-103 --by Christopher`

### 5. `pl-10-58-62` głosowanie nad całością projektu.

- **Why first (104 points):** a vote on the whole text; watched bill 10/2110; values proposed: one tick to sign; close-ish: 230-198; meaning line ready; feeds brief pl-rzadowy-projekt-ustawy-o-statusie-osoby-najblizs-10-2110 (NOT READY until signed); this year.
- **When / result:** 2026-05-29; Sejm; Za 230, Przeciw 198, Abstain 1
- **On:** Pkt. 5 Sprawozdanie Komisji o rządowym projekcie ustawy o statusie osoby najbliższej w związku i umowie o wspólnym pożyciu (druki nr 2110, 2593 i 2593-A)
- **Area:** marriage and family
- Meaning: **Za** = to pass 10/2110 (registered cohabitation contracts) as a whole; **Przeciw** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/2110 (O statusie osoby najbliższej (government): registered cohabitation contracts): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-58-62 --by Christopher`

### 6. `pl-10-45-80` głosowanie nad całością projektu.

- **Why first (104 points):** a vote on the whole text; the last such vote on its bill; watched bill 10/1757; values proposed: one tick to sign; close-ish: 237-200; meaning line ready; this year.
- **When / result:** 2025-11-21; Sejm; Za 237, Przeciw 200, Abstain 5
- **On:** Pkt. 14 Sprawozdanie Komisji o rządowym projekcie ustawy o zmianie ustawy o świadczeniu usług drogą elektroniczną oraz niektórych innych ustaw (druki nr 1757, 1922 i 1922-A)
- **Area:** free speech and civil liberties
- Meaning: **Za** = to pass 10/1757 (takedown orders for illegal content, the free-speech fight of 2025-26) as a whole; **Przeciw** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/1757 (DSA implementation (usługi drogą elektroniczną): takedown orders for illegal content, the ): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-45-80 --by Christopher`

### 7. `pl-10-15-9` głosowanie nad całością projektu.

- **Why first (100 points):** a vote on the whole text; the last such vote on its bill; watched bill 10/176; values proposed: one tick to sign; close: 215-218; meaning line ready.
- **When / result:** 2024-07-12; Sejm; Za 215, Przeciw 218, Abstain 2
- **On:** Pkt. 1 Sprawozdanie Komisji o poselskim projekcie ustawy o zmianie ustawy - Kodeks karny (druki nr 176 i 477)
- **Area:** abortion
- Meaning: **Za** = to pass 10/176 (decriminalises abortion up to 12 weeks with the woman's consent) as a whole; **Przeciw** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/176 (Kodeks karny: decriminalises abortion up to 12 weeks with the woman's consent): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-15-9 --by Christopher`

### 8. `pl-10-61-40` wniosek o odrzucenie projektu w pierwszym czytaniu.

- **Why first (99 points):** a motion to reject the text; the last such vote on its bill; watched bill 10/2623; values proposed: one tick to sign; close-ish: 237-195; meaning line ready; this year.
- **When / result:** 2026-07-03; Sejm; Za 237, Przeciw 195
- **On:** Pkt. 14 Pierwsze czytanie poselskiego projektu ustawy o zmianie ustawy - Kodeks pracy (druk nr 2623) - kontynuacja
- **Area:** sex-based rights
- Meaning: **Za** = to reject 10/2623 (repeals the duty to use gender-neutral job titles in job adverts) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/2623 (Kodeks pracy: repeals the duty to use gender-neutral job titles in job adverts): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-61-40 --by Christopher`

### 9. `pl-10-58-54` wniosek o odrzucenie w całości projektu.

- **Why first (99 points):** a motion to reject the text; watched bill 10/2110; values proposed: one tick to sign; close-ish: 197-230; meaning line ready; feeds brief pl-rzadowy-projekt-ustawy-o-statusie-osoby-najblizs-10-2110 (NOT READY until signed); this year.
- **When / result:** 2026-05-29; Sejm; Za 197, Przeciw 230, Abstain 1
- **On:** Pkt. 5 Sprawozdanie Komisji o rządowym projekcie ustawy o statusie osoby najbliższej w związku i umowie o wspólnym pożyciu (druki nr 2110, 2593 i 2593-A)
- **Area:** marriage and family
- Meaning: **Za** = to reject 10/2110 (registered cohabitation contracts) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/2110 (O statusie osoby najbliższej (government): registered cohabitation contracts): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-58-54 --by Christopher`

### 10. `pl-10-58-63` wniosek o odrzucenie w całości projektu.

- **Why first (99 points):** a motion to reject the text; watched bill 10/2111; values proposed: one tick to sign; close-ish: 193-228; meaning line ready; feeds brief pl-rzadowy-projekt-ustawy-przepisy-wprowadzajace-us-10-2111 (NOT READY until signed); this year.
- **When / result:** 2026-05-29; Sejm; Za 193, Przeciw 228, Abstain 1
- **On:** Pkt. 6 Sprawozdanie Komisji o rządowym projekcie ustawy - Przepisy wprowadzające ustawę o statusie osoby najbliższej w związku i umowie o wspólnym pożyciu (druki nr 2111, 2594 i 2594-A)
- **Area:** marriage and family
- Meaning: **Za** = to reject 10/2111 (Implementing act for 10/2110) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/2111 (Implementing act for 10/2110): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-58-63 --by Christopher`

### 11. `pl-10-51-72` wniosek o odrzucenie projektu w pierwszym czytaniu.

- **Why first (99 points):** a motion to reject the text; watched bill 10/2110; values proposed: one tick to sign; close-ish: 199-233; meaning line ready; feeds brief pl-rzadowy-projekt-ustawy-o-statusie-osoby-najblizs-10-2110 (NOT READY until signed); this year.
- **When / result:** 2026-02-13; Sejm; Za 199, Przeciw 233, Abstain 3
- **On:** Pkt. 24 Pierwsze czytanie rządowego projektu ustawy o statusie osoby najbliższej w związku i umowie o wspólnym pożyciu (druk nr 2110)
- **Area:** marriage and family
- Meaning: **Za** = to reject 10/2110 (registered cohabitation contracts) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/2110 (O statusie osoby najbliższej (government): registered cohabitation contracts): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-51-72 --by Christopher`

### 12. `pl-10-51-73` wniosek o odrzucenie projektu w pierwszym czytaniu.

- **Why first (99 points):** a motion to reject the text; watched bill 10/2111; values proposed: one tick to sign; close-ish: 202-232; meaning line ready; feeds brief pl-rzadowy-projekt-ustawy-przepisy-wprowadzajace-us-10-2111 (NOT READY until signed); this year.
- **When / result:** 2026-02-13; Sejm; Za 202, Przeciw 232, Abstain 2
- **On:** Pkt. 25 Pierwsze czytanie rządowego projektu ustawy - Przepisy wprowadzające ustawę o statusie osoby najbliższej w związku i umowie o wspólnym pożyciu (druk nr 2111)
- **Area:** marriage and family
- Meaning: **Za** = to reject 10/2111 (Implementing act for 10/2110) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/2111 (Implementing act for 10/2110): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-51-73 --by Christopher`

### 13. `pl-10-30-16` głosowanie nad całością projektu.

- **Why first (99 points):** a vote on the whole text; the last such vote on its bill; watched bill 10/876; values proposed: one tick to sign; close-ish: 238-201; meaning line ready.
- **When / result:** 2025-03-06; Sejm; Za 238, Przeciw 201
- **On:** Pkt. 2 Sprawozdanie Komisji o rządowym projekcie ustawy o zmianie ustawy - Kodeks karny (druki nr 876, 984 i 984-A)
- **Area:** conversion practices, sex-based rights, free speech and civil liberties
- Meaning: **Za** = to pass 10/876 (extends hate-speech and hate-crime protection to disability, age, sex and sexual orientation) as a whole; **Przeciw** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/876 (Kodeks karny (government, passed): extends hate-speech and hate-crime protection to disabi): for passing it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-30-16 --by Christopher`

### 14. `pl-10-41-30` wniosek o odrzucenie projektu w pierwszym czytaniu.

- **Why first (94 points):** a motion to reject the text; the last such vote on its bill; watched bill 10/1603; values proposed: one tick to sign; close-ish: 191-231; meaning line ready.
- **When / result:** 2025-09-26; Sejm; Za 191, Przeciw 231, Abstain 4
- **On:** Pkt. 41 Pierwsze czytanie obywatelskiego projektu ustawy o zmianie ustawy o systemie oświaty oraz ustawy - Prawo oświatowe (druk nr 1603)
- **Area:** parental rights and education, religious freedom
- Meaning: **Za** = to reject 10/1603 (compulsory religion or ethics, two hours a week, in every school; reverses the 2024-25 cuts to religion…) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/1603 (Citizens' bill: compulsory religion or ethics, two hours a week, in every school): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-41-30 --by Christopher`

### 15. `pl-10-45-47` wniosek o odrzucenie w całości projektu.

- **Why first (89 points):** a motion to reject the text; watched bill 10/1757; values proposed: one tick to sign; close-ish: 199-240; meaning line ready; this year.
- **When / result:** 2025-11-21; Sejm; Za 199, Przeciw 240
- **On:** Pkt. 14 Sprawozdanie Komisji o rządowym projekcie ustawy o zmianie ustawy o świadczeniu usług drogą elektroniczną oraz niektórych innych ustaw (druki nr 1757, 1922 i 1922-A)
- **Area:** free speech and civil liberties
- Meaning: **Za** = to reject 10/1757 (takedown orders for illegal content, the free-speech fight of 2025-26) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/1757 (DSA implementation (usługi drogą elektroniczną): takedown orders for illegal content, the ): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-45-47 --by Christopher`

### 16. `pl-10-43-70` wniosek o odrzucenie projektu w pierwszym czytaniu.

- **Why first (89 points):** a motion to reject the text; watched bill 10/1757; values proposed: one tick to sign; close-ish: 204-241; meaning line ready; this year.
- **When / result:** 2025-10-17; Sejm; Za 204, Przeciw 241
- **On:** Pkt. 20 Pierwsze czytanie rządowego projektu ustawy o zmianie ustawy o świadczeniu usług drogą elektroniczną oraz niektórych innych ustaw (druk nr 1757)
- **Area:** free speech and civil liberties
- Meaning: **Za** = to reject 10/1757 (takedown orders for illegal content, the free-speech fight of 2025-26) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/1757 (DSA implementation (usługi drogą elektroniczną): takedown orders for illegal content, the ): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-43-70 --by Christopher`

### 17. `pl-10-15-8` wniosek o odrzucenie w całości projektu.

- **Why first (85 points):** a motion to reject the text; watched bill 10/176; values proposed: one tick to sign; close: 215-216; meaning line ready.
- **When / result:** 2024-07-12; Sejm; Za 215, Przeciw 216, Abstain 2
- **On:** Pkt. 1 Sprawozdanie Komisji o poselskim projekcie ustawy o zmianie ustawy - Kodeks karny (druki nr 176 i 477)
- **Area:** abortion
- Meaning: **Za** = to reject 10/176 (decriminalises abortion up to 12 weeks with the woman's consent) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/176 (Kodeks karny: decriminalises abortion up to 12 weeks with the woman's consent): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-15-8 --by Christopher`

### 18. `pl-10-30-12` wniosek o odrzucenie w całości projektu.

- **Why first (84 points):** a motion to reject the text; watched bill 10/876; values proposed: one tick to sign; close-ish: 199-240; meaning line ready.
- **When / result:** 2025-03-06; Sejm; Za 199, Przeciw 240, Abstain 1
- **On:** Pkt. 2 Sprawozdanie Komisji o rządowym projekcie ustawy o zmianie ustawy - Kodeks karny (druki nr 876, 984 i 984-A)
- **Area:** conversion practices, sex-based rights, free speech and civil liberties
- Meaning: **Za** = to reject 10/876 (extends hate-speech and hate-crime protection to disability, age, sex and sexual orientation) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za +2, Przeciw -2
  - Voted Za on 10/876 (Kodeks karny (government, passed): extends hate-speech and hate-crime protection to disabi): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-30-12 --by Christopher`

### 19. `pl-10-6-15` wniosek o odrzucenie projektu w pierwszym czytaniu.

- **Why first (83 points):** a motion to reject the text; the last such vote on its bill; watched bill 10/25; values proposed: one tick to sign; contested: 234-189; meaning line ready.
- **When / result:** 2024-02-22; Sejm; Za 234, Przeciw 189
- **On:** Pkt. 7 Pierwsze czytanie obywatelskiego projektu ustawy Tak dla rodziny, nie dla gender (druk nr 25) - kontynuacja
- **Area:** sex-based rights, marriage and family
- Meaning: **Za** = to reject 10/25 (withdraw from the Istanbul Convention and draft a family-rights convention) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/25 (Citizens' bill 'Tak dla rodziny, nie dla gender': withdraw from the Istanbul Convention an): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-6-15 --by Christopher`

### 20. `pl-10-6-16` wniosek o odrzucenie projektu w pierwszym czytaniu.

- **Why first (83 points):** a motion to reject the text; the last such vote on its bill; watched bill 10/26; values proposed: one tick to sign; contested: 233-189; meaning line ready.
- **When / result:** 2024-02-22; Sejm; Za 233, Przeciw 189
- **On:** Pkt. 8 Pierwsze czytanie obywatelskiego projektu ustawy o zmianie ustawy z dnia 24 lipca 2015 r. - Prawo o zgromadzeniach oraz niektórych innych ustaw (druk nr 26) - kontynuacja
- **Area:** sex-based rights
- Meaning: **Za** = to reject 10/26 (bans assemblies promoting same-sex relations or gender change) outright at this stage (a motion to reject); **Przeciw** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Za -2, Przeciw +2
  - Voted Za on 10/26 (Citizens' bill 'Stop LGBT': bans assemblies promoting same-sex relations or gender change): for rejecting it, against CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc pl --confirm pl-10-6-16 --by Christopher`

## By area (rank in the whole list)

- **abortion** (12 waiting): #3 `pl-10-21-38` 2024-11-08, 110 pts; #7 `pl-10-15-9` 2024-07-12, 100 pts; #17 `pl-10-15-8` 2024-07-12, 85 pts
- **conversion practices** (6 waiting): #13 `pl-10-30-16` 2025-03-06, 99 pts; #18 `pl-10-30-12` 2025-03-06, 84 pts; #23 `pl-10-25-12` 2024-12-20, 78 pts
- **sex-based rights** (9 waiting): #8 `pl-10-61-40` 2026-07-03, 99 pts; #13 `pl-10-30-16` 2025-03-06, 99 pts; #18 `pl-10-30-12` 2025-03-06, 84 pts
- **parental rights and education** (1 waiting): #14 `pl-10-41-30` 2025-09-26, 94 pts
- **free speech and civil liberties** (95 waiting): #6 `pl-10-45-80` 2025-11-21, 104 pts; #13 `pl-10-30-16` 2025-03-06, 99 pts; #15 `pl-10-45-47` 2025-11-21, 89 pts
- **religious freedom** (1 waiting): #14 `pl-10-41-30` 2025-09-26, 94 pts
- **marriage and family** (67 waiting): #1 `pl-10-65-10` 2026-09-17, 119 pts; #2 `pl-10-65-11` 2026-09-17, 119 pts; #4 `pl-10-58-103` 2026-05-29, 104 pts
- **surrogacy and embryology** (6 waiting): #22 `pl-10-1-40` 2023-11-29, 80 pts; #28 `pl-10-1-31` 2023-11-28, 65 pts; #119 `pl-10-1-36` 2023-11-29, 23 pts
- **migration** (8 waiting): #178 `pl-10-63-44` 2026-07-31, -17 pts; #179 `pl-10-38-40` 2025-07-09, -30 pts; #180 `pl-10-38-37` 2025-07-09, -66 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

