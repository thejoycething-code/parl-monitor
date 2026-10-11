# Croatia 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 12 readings waiting in `config/hr_stance.yaml` (0 proposed, 0 procedural, 12 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-hr-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

## Top 12

### 1. `hr-11-213747` PRIJEDLOG ZAKONA O IZMJENI I DOPUNI ZAKONA O RAVNOPRAVNOSTI SPOLOVA, prvo čitanje, P.Z. br. 169 - predlagateljice: zastupnice Anka Mrak-Tari

- **Why first (77 points):** a vote whose Yes rejects the text; the last such vote on its bill; watched bill 11/169; split HDZ, SDP (2 against their group); meaning line ready; this year.
- **When / result:** 2025-10-24; Sabor; Na 7. sjednici, 24. listopada 2025. donesen je zaključak da se ne prihvaća Prijedlog zakona (77 glasova "za", 43 "protiv; Za 77, Protiv 43
- **Area:** sex-based rights
- **Lobbies:** Za: HDZ 54, NZ 9, DP 7, HSLS 2, HSU 1, SDP 1, stranka Nezavisni 1, HNS 1, HDS 1. Protiv: SDP 29, Možemo! 9, NPS 1, HDZ 1, GLAS 1, DO i SIP 1, IDS 1
- Meaning: **Za** = to accept 11/169 (Amendment to the Gender Equality Act (Zakon o ravnopravnosti spolova), Mrak-Taritas and Oreskovic) at first reading; **Protiv** = against accepting it at first reading. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote whose Yes rejects the text (the record says so), but no bill direction is on file for 11/169, item:213747: CitizenGO's position on 'PRIJEDLOG ZAKONA O IZMJENI I DOPUNI ZAKONA O RAVNOPRAVNOSTI SPOLOVA, prvo čitanje, P.Z. br. 169 - predlagateljice: zastup
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-213747` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-213747 --by Christopher`

### 2. `hr-11-214348` PRIJEDLOG ZAKONA O DOPUNI OBITELJSKOG ZAKONA, prvo čitanje, P.Z. br. 244 - predlagatelj: Klub zastupnika SDP-a

- **Why first (70 points):** a vote whose Yes rejects the text; the last such vote on its bill; watched bill 11/244; meaning line ready; this year.
- **When / result:** 2026-04-30; Sabor; Na 10. sjednici, 30. travnja 2026. donesen je zaključak da se ne prihvaća Prijedlog zakona (78 glasova "za", 42 "protiv"; Za 78, Protiv 42, 
- **Area:** marriage and family
- **Lobbies:** Za: HDZ 55, NZ 8, DP 7, HSLS 2, HSU 1, stranka Nezavisni 1, HNS 1, HSS 1, HDS 1, Dario Zurovec - NL 1. Protiv: SDP 26, Možemo! 10, Centar 2, IDS 2, GLAS 1, DO i SIP 1. Abstain: Most 2
- Meaning: **Za** = to accept 11/244 (Amendment to the Family Act (Obiteljski zakon), SDP club) at first reading; **Protiv** = against accepting it at first reading. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote whose Yes rejects the text (the record says so), but no bill direction is on file for 11/244, item:214348: CitizenGO's position on 'PRIJEDLOG ZAKONA O DOPUNI OBITELJSKOG ZAKONA, prvo čitanje, P.Z. br. 244 - predlagatelj: Klub zastupnika SDP-a' needs a h
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-214348` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-214348 --by Christopher`

### 3. `hr-11-214147` PRIJEDLOG ZAKONA O DIGITALNOJ ZAŠTITI DJECE, prvo čitanje, P.Z. br. 213 - predlagatelj: Klub zastupnika Možemo!

- **Why first (70 points):** a vote whose Yes rejects the text; the last such vote on its bill; watched bill 11/213; meaning line ready; this year.
- **When / result:** 2026-03-06; Sabor; Na 9. sjednici, 6. ožujka 2026. donesen je zaključak da se ne prihvaća Prijedlog zakona (76 glasova "za", 44 "protiv", 4; Za 76, Protiv 44, 
- **Area:** parental rights and education, free speech and civil liberties
- **Lobbies:** Za: HDZ 55, NZ 8, DP 7, HSLS 2, HSU 1, stranka Nezavisni 1, HNS 1, HDS 1. Protiv: SDP 28, Možemo! 10, Centar 2, NPS 1, GLAS 1, DO i SIP 1, Drito 1. Abstain: DOMINO 3, Hrvatski suverenisti 1
- Meaning: **Za** = to accept 11/213 (Digital Protection of Children Act (Zakon o digitalnoj zastiti djece), Mozemo! club) at first reading; **Protiv** = against accepting it at first reading. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote whose Yes rejects the text (the record says so), but no bill direction is on file for 11/213, item:214147: CitizenGO's position on 'PRIJEDLOG ZAKONA O DIGITALNOJ ZAŠTITI DJECE, prvo čitanje, P.Z. br. 213 - predlagatelj: Klub zastupnika Možemo!' needs a 
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-214147` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-214147 --by Christopher`

### 4. `hr-11-214304` KONAČNI PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2024/1083 O USPOSTAVI ZAJEDNIČKOG OKVIRA ZA MEDIJSKE USLUGE NA UNUTARNJEM TRŽIŠTU I IZMJENI 

- **Why first (59 points):** a vote on the whole text; tier 1; contested: 78-57; split NZ (1 against their group); meaning line quotes the source; this year.
- **When / result:** 2026-03-06; Sabor; Zakon je donesen na 9. sjednici, 6. ožujka 2026. (78 glasova "za", 57 "protiv").; Za 78, Protiv 57
- **Area:** free speech and civil liberties
- **Lobbies:** Za: HDZ 55, NZ 9, DP 7, HSLS 2, HSU 1, stranka Nezavisni 1, HNS 1, HDS 1, Dario Zurovec - NL 1. Protiv: SDP 31, Možemo! 10, DOMINO 3, Most 3, Centar 2, Drito 2, NZ 1, Hrvatski suverenisti 1, IDS 1, GLAS 1, DO i SIP 1, SDSS 1
- Meaning: **Za** = to pass the text “KONAČNI PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2024/1083 O USPOSTAVI ZAJEDNIČKOG OKVIRA…” at second (final) reading; **Protiv** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 11/228, item:214304: CitizenGO's position on 'KONAČNI PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2024/1083 O USPOSTAVI ZAJEDNIČKOG OKVIRA ZA MEDIJSKE USLUGE NA UNUTARNJEM TRŽIŠTU 
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-214304` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-214304 --by Christopher`

### 5. `hr-11-214089` PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2024/1083 O USPOSTAVI ZAJEDNIČKOG OKVIRA ZA MEDIJSKE USLUGE NA UNUTARNJEM TRŽIŠTU I IZMJENI DIREKTIV

- **Why first (51 points):** a vote on the whole text; tier 1; split NZ (1 against their group); meaning line quotes the source; this year.
- **When / result:** 2025-12-05; Sabor; Na 8. sjednici, 5. prosinca 2025. donesen je zaključak da se prihvaća Prijedlog zakona. Sve primjedbe, prijedlozi i mišl; Za 76, Protiv 31, 
- **Area:** free speech and civil liberties
- **Lobbies:** Za: HDZ 54, NZ 9, DP 7, HSLS 2, HSU 1, stranka Nezavisni 1, HNS 1, HDS 1. Protiv: SDP 26, Most 3, NZ 1, GLAS 1. Abstain: Možemo! 6, Centar 2
- Meaning: **Za** = to accept the text “PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2024/1083 O USPOSTAVI ZAJEDNIČKOG OKVIRA ZA…” at first reading; **Protiv** = against accepting it at first reading. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 11/228, item:214089: CitizenGO's position on 'PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2024/1083 O USPOSTAVI ZAJEDNIČKOG OKVIRA ZA MEDIJSKE USLUGE NA UNUTARNJEM TRŽIŠTU I IZMJEN
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-214089` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-214089 --by Christopher`

### 6. `hr-11-214240` PRIJEDLOG ODLUKE O OSNIVANJU ISTRAŽNOG POVJERENSTVA ZA UTVRĐIVANJE INSTITUCIONALNIH PROPUSTA U SUSTAVU ZAŠTITE OD NASILJA NAD ŽENAMA KOJI RE

- **Why first (35 points):** watched bill item:214240; meaning line ready; this year.
- **When / result:** 2026-03-27; Sabor; Odluka nije donesena na 9. sjednici, 27. ožujka 2026. (44 glasa "za", 81 "protiv").; Za 44, Protiv 81
- **Area:** sex-based rights
- **Lobbies:** Za: SDP 28, Možemo! 10, Centar 1, NPS 1, GLAS 1, DO i SIP 1, IDS 1, SDSS 1. Protiv: HDZ 55, NZ 8, DP 7, DOMINO 3, HSLS 2, HSU 1, Hrvatski suverenisti 1, stranka Nezavisni 1, HNS 1, HDS 1, Dario Zurovec - NL 1
- Meaning: **Za** = to adopt the resolution or decision item 214240 (Proposal to set up an inquiry into institutional failures in protecting women from violence, 'resulting in a…); **Protiv** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: The kind of vote could not be read from its wording ('PRIJEDLOG ODLUKE O OSNIVANJU ISTRAŽNOG POVJERENSTVA ZA UTVRĐIVANJE INSTITUCIONALNIH PROPUSTA U SUSTAVU ZAŠTITE OD NASILJ'): read the question put, then write yea/nay.
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-214240` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-214240 --by Christopher`

### 7. `hr-11-213442` KONAČNI PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2022/2065 EUROPSKOG PARLAMENTA I VIJEĆA OD 19. LISTOPADA 2022. O JEDINSTVENOM TRŽIŠTU DIGITA

- **Why first (28 points):** a vote on the whole text; tier 1; near-unanimous (107-0, lower); meaning line quotes the source.
- **When / result:** 2025-03-28; Sabor; Zakon je donesen na 5. sjednici, 28. ožujka 2025. (107 glasova "za", 9 "suzdržanih").; Za 107, Protiv 0, Abstain 9
- **Area:** free speech and civil liberties
- **Lobbies:** Za: HDZ 56, SDP 22, NZ 9, DP 7, Možemo! 2, HSLS 2, NPS 1, HSU 1, stranka Nezavisni 1, GLAS 1, DO i SIP 1, Centar 1, SDSS 1, HNS 1, HDS 1. Abstain: Možemo! 7, NZ 1, Most 1
- Meaning: **Za** = to pass the text “KONAČNI PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2022/2065 EUROPSKOG PARLAMENTA I VIJEĆA…” at second (final) reading; **Protiv** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 11/53, item:213442: CitizenGO's position on 'KONAČNI PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2022/2065 EUROPSKOG PARLAMENTA I VIJEĆA OD 19. LISTOPADA 2022. O JEDINSTVENOM TRŽIŠ
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-213442` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-213442 --by Christopher`

### 8. `hr-11-212876` PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2022/2065 EUROPSKOG PARLAMENTA I VIJEĆA OD 19. LISTOPADA 2022. O JEDINSTVENOM TRŽIŠTU DIGITALNIH USL

- **Why first (28 points):** a vote on the whole text; tier 1; near-unanimous (116-0, lower); meaning line quotes the source.
- **When / result:** 2024-10-11; Sabor; Na 3. sjednici, 11. listopada 2024. donesen je zaključak da se prihvaća Prijedlog zakona. Sve primjedbe, prijedlozi i mi; Za 116, Protiv 0, 
- **Area:** free speech and civil liberties
- **Lobbies:** Za: HDZ 56, SDP 27, NZ 8, DP 8, NPS 2, DOMINO 2, HSLS 2, Centar 2, Drito 2, HSU 1, stranka Nezavisni 1, GLAS 1, DO i SIP 1, IDS 1, HNS 1, HDS 1. Abstain: Možemo! 10, Most 3, NZ 1
- Meaning: **Za** = to accept the text “PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2022/2065 EUROPSKOG PARLAMENTA I VIJEĆA OD 19.…” at first reading; **Protiv** = against accepting it at first reading. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 11/53, item:212876: CitizenGO's position on 'PRIJEDLOG ZAKONA O PROVEDBI UREDBE (EU) 2022/2065 EUROPSKOG PARLAMENTA I VIJEĆA OD 19. LISTOPADA 2022. O JEDINSTVENOM TRŽIŠTU DIGIT
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-212876` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-212876 --by Christopher`

### 9. `hr-11-214280` PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, prvo čitanje, P.Z.E. br. 262 - predlagateljica: Vlada Republike Hrvatske

- **Why first (-49 points):** a vote on the whole text; tier 1; split NZ (1 against their group); meaning line quotes the source; this year; collated-only area: places nobody (lowest).
- **When / result:** 2026-02-20; Sabor; Za 77, Protiv 7, Abstain 46
- **Area:** migration
- **Lobbies:** Za: HDZ 54, NZ 9, DP 7, HSLS 2, NPS 1, HSU 1, stranka Nezavisni 1, HNS 1, HDS 1. Protiv: Most 3, DOMINO 2, NZ 1, Drito 1. Abstain: SDP 30, Možemo! 10, Centar 2, IDS 1, GLAS 1, DO i SIP 1, SDSS 1
- Meaning: **Za** = to accept the text “PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, prvo čitanje, P.Z.E. br. 262…” at first reading; **Protiv** = against accepting it at first reading. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 11/262, item:214280: CitizenGO's position on 'PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, prvo čitanje, P.Z.E. br. 262 - predlagateljica: Vlada Republike Hrvats
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-214280` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-214280 --by Christopher`

### 10. `hr-11-213382` KONAČNI PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, drugo čitanje, P.Z.E. br. 63 - predlagateljica: Vlada Republike Hrvatske

- **Why first (-53 points):** a vote on the whole text; tier 1; split NZ (2 against their group); meaning line quotes the source; collated-only area: places nobody (lowest).
- **When / result:** 2025-02-21; Sabor; Za 76, Protiv 37, Abstain 5
- **Area:** migration
- **Lobbies:** Za: HDZ 55, NZ 8, DP 7, HSLS 2, HSU 1, stranka Nezavisni 1, HNS 1, HDS 1. Protiv: SDP 24, Možemo! 4, DOMINO 3, NZ 2, Most 1, GLAS 1, DO i SIP 1, Drito 1. Abstain: Možemo! 4, Centar 1
- Meaning: **Za** = to pass the text “KONAČNI PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, drugo čitanje, P.Z.E.…” at second (final) reading; **Protiv** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 11/63, item:213382: CitizenGO's position on 'KONAČNI PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, drugo čitanje, P.Z.E. br. 63 - predlagateljica: Vlada Republike
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-213382` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-213382 --by Christopher`

### 11. `hr-11-213008` PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, prvo čitanje, P.Z.E. br. 63 - predlagateljica: Vlada Republike Hrvatske

- **Why first (-57 points):** a vote on the whole text; tier 1; meaning line quotes the source; collated-only area: places nobody (lowest).
- **When / result:** 2024-10-25; Sabor; Za 85, Protiv 5, Abstain 39
- **Area:** migration
- **Lobbies:** Za: HDZ 55, NZ 8, DP 8, SDSS 3, DOMINO 2, IDS 2, NPS 1, HSU 1, HSLS 1, stranka Nezavisni 1, Centar 1, HNS 1, HDS 1. Protiv: Most 5. Abstain: SDP 24, Možemo! 10, Drito 2, NZ 1, GLAS 1, DO i SIP 1
- Meaning: **Za** = to accept the text “PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, prvo čitanje, P.Z.E. br. 63 -…” at first reading; **Protiv** = against accepting it at first reading. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 11/63, item:213008: CitizenGO's position on 'PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, prvo čitanje, P.Z.E. br. 63 - predlagateljica: Vlada Republike Hrvatske
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-213008` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-213008 --by Christopher`

### 12. `hr-11-214487` KONAČNI PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, drugo čitanje, P.Z.E. br. 262 - predlagateljica: Vlada Republike Hrvatsk

- **Why first (-67 points):** a vote on the whole text; tier 1; near-unanimous (80-0, lower); meaning line quotes the source; this year; collated-only area: places nobody (lowest).
- **When / result:** 2026-05-15; Sabor; Za 80, Protiv 0, Abstain 37
- **Area:** migration
- **Lobbies:** Za: HDZ 54, NZ 9, DP 6, HSLS 2, IDS 2, HSU 1, stranka Nezavisni 1, SDSS 1, HNS 1, HSS 1, HDS 1, Dario Zurovec - NL 1. Abstain: SDP 23, Možemo! 9, Centar 2, NZ 1, GLAS 1, DO i SIP 1
- Meaning: **Za** = to pass the text “KONAČNI PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, drugo čitanje, P.Z.E.…” at second (final) reading; **Protiv** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: A vote on the whole text or the motion itself, but no bill direction is on file for 11/262, item:214487: CitizenGO's position on 'KONAČNI PRIJEDLOG ZAKONA O IZMJENAMA I DOPUNAMA ZAKONA O STRANCIMA, drugo čitanje, P.Z.E. br. 262 - predlagateljica: Vlada Republi
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `hr-11-214487` in config/hr_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc hr --confirm hr-11-214487 --by Christopher`

## By area (rank in the whole list)

- **sex-based rights** (2 waiting): #1 `hr-11-213747` 2025-10-24, 77 pts; #6 `hr-11-214240` 2026-03-27, 35 pts
- **parental rights and education** (1 waiting): #3 `hr-11-214147` 2026-03-06, 70 pts
- **free speech and civil liberties** (5 waiting): #3 `hr-11-214147` 2026-03-06, 70 pts; #4 `hr-11-214304` 2026-03-06, 59 pts; #5 `hr-11-214089` 2025-12-05, 51 pts
- **marriage and family** (1 waiting): #2 `hr-11-214348` 2026-04-30, 70 pts
- **migration** (4 waiting): #9 `hr-11-214280` 2026-02-20, -49 pts; #10 `hr-11-213382` 2025-02-21, -53 pts; #11 `hr-11-213008` 2024-10-25, -57 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

