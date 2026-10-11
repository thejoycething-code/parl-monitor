# France 5CA: readings to sign

Drafted by `tools/country_5ca.py` (src/country5ca.py) from the store's watched and tier-1 votes, by rules, never by a model. **Nothing here places anyone until it is confirmed**: automatically on Chris's delegation when every check passes (11 October 2026, `--auto-confirm`), otherwise by a named person. Sign-off is limited to final votes, motions to reject and the amendment or article votes watched in config/watchlist-fr.yaml (Chris, 10 October 2026).

**To amend any reading** (a signer for fr in `config/stance_signers.yaml`): `python3 tools/country_5ca.py --cc fr --amend KEY --yea N --nay N --by NAME --why "..."`, or `--take-out` instead of the values to put it out of play. An amended reading is never touched by the automation again.

**How to sign.** Tick `[x]` on each reading you accept as drafted, then run `python3 tools/country_5ca.py --cc fr --sign-from-doc --by NAME` (it sets `status: confirmed` with `confirmed_by` and `confirmed_on` in `config/fr_stance.yaml`). To change a value, edit the stance file first. A reading that needs reading has no box: write `yea:`/`nay:` in the stance file, set `status: draft`, then confirm it.

Counts: 10 proposed, 0 procedural (evidence only), 13 need reading, 0 confirmed (0 automatically).

## Proposed readings

### [ ] `senat-2025-337` sur l'ensemble de la proposition de loi visant à protéger les mineurs des risques auxquels les expose l'utilisation des réseaux sociaux

- **When / result:** 2026-07-21; senat; Pour 243, Contre 2, Abstain 100
- **On:** Protéger les mineurs des risques auxquels les expose l’utilisation des réseaux sociaux
- **Lobbies:** Pour: Les Républicains 129, UCI 58, Les Indépendants 20, RDPI 19, RDSE 17. Contre: NI 1, GEST 1. Abstain: SER 64, CRCE-K 18, GEST 15, NI 3
- Meaning: **Pour** = to pass DLR5L17N53187 (the under-15 social media rule and age checks) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour -2 (Voted Pour on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): for passing it, against CitizenGO's position.); Contre +2 (Voted Contre on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): against passing it, with CitizenGO's position.)
- **Reasoning:** Area 7 (free speech and civil liberties). Bill direction on file for DLR5L17N53187 (CONFIRMED): passing it is AGAINST us -- Protect minors from the risks of social networks (ppl25-304): the under-15 social media rule and age checks. Passed the Senat on 21 July 2026. Matched nothing. This vote is a vote on the whole text or the motion itself, so Pour is against us.

### [ ] `an-17-8431` l'ensemble de la proposition de loi visant à protéger les mineurs des risques auxquels les expose l'utilisation des réseaux sociaux (texte de la commission mixt

- **When / result:** 2026-07-21; Assemblée nationale; adopté; Pour 279, Contre 81, Abstain 66
- **On:** Protéger les mineurs des risques auxquels les expose l’utilisation des réseaux sociaux
- **Lobbies:** Pour: EPR 83, DR 40, HOR 33, DEM 32, SOC 30, LIOT 22, ECOS 19, UDDPLR 8, NI 6, GDR 6. Contre: LFI-NFP 63, ECOS 7, UDDPLR 5, GDR 3, RN 2, DEM 1. Abstain: SOC 28, RN 14, ECOS 7, GDR 5, UDDPLR 4, DR 3, NI 2, DEM 2, LIOT 1
- Meaning: **Pour** = to pass DLR5L17N53187 (the under-15 social media rule and age checks) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour -2 (Voted Pour on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): for passing it, against CitizenGO's position.); Contre +2 (Voted Contre on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): against passing it, with CitizenGO's position.)
- **Reasoning:** Area 7 (free speech and civil liberties). Bill direction on file for DLR5L17N53187 (CONFIRMED): passing it is AGAINST us -- Protect minors from the risks of social networks (ppl25-304): the under-15 social media rule and age checks. Passed the Senat on 21 July 2026. Matched nothing. This vote is a vote on the whole text or the motion itself, so Pour is against us.

### [ ] `an-17-8280` l'ensemble de la proposition de loi relative au droit à l'aide à mourir (lecture définitive).

- **When / result:** 2026-07-15; Assemblée nationale; adopté; Pour 291, Contre 241, Abstain 29
- **On:** Fin de vie
- **Lobbies:** Pour: EPR 64, LFI-NFP 61, SOC 57, ECOS 33, DEM 20, HOR 16, RN 12, LIOT 10, GDR 10, DR 5, NI 3. Contre: RN 106, DR 41, EPR 18, HOR 18, UDDPLR 17, DEM 16, LIOT 8, NI 7, SOC 4, LFI-NFP 2, GDR 2, ECOS 2. Abstain: EPR 9, SOC 6, LIOT 4, GDR 3, LFI-NFP 3, DR 2, HOR 1, ECOS 1
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour -2 (Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.); Contre +2 (Voted Contre on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): against passing it, with CitizenGO's position.)
- **Reasoning:** Area 2 (assisted dying). Bill direction on file for DLR5L17N51670 (a draft): passing it is AGAINST us -- Droit a l'aide a mourir (dossier 'Fin de vie'). Adopted in lecture definitive 15 July 2026, Conseil constitutionnel conforme 14 August, promulgated 18 August 2026. 380 scrutins name the dossier; 931 s. This vote is a vote on the whole text or the motion itself, so Pour is against us.

### [ ] `an-17-7894` l'ensemble de la proposition de loi relative au droit à l'aide à mourir (nouvelle lecture).

- **When / result:** 2026-06-30; Assemblée nationale; adopté; Pour 295, Contre 232, Abstain 35
- **On:** Fin de vie
- **Lobbies:** Pour: EPR 66, LFI-NFP 62, SOC 57, ECOS 34, DEM 19, HOR 16, RN 14, GDR 10, LIOT 9, DR 5, NI 3. Contre: RN 103, DR 38, HOR 18, EPR 17, UDDPLR 17, DEM 16, LIOT 7, NI 7, SOC 4, LFI-NFP 2, GDR 2, ECOS 1. Abstain: EPR 7, LIOT 6, SOC 5, RN 5, DR 3, GDR 3, LFI-NFP 3, ECOS 2, HOR 1
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour -2 (Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.); Contre +2 (Voted Contre on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): against passing it, with CitizenGO's position.)
- **Reasoning:** Area 2 (assisted dying). Bill direction on file for DLR5L17N51670 (a draft): passing it is AGAINST us -- Droit a l'aide a mourir (dossier 'Fin de vie'). Adopted in lecture definitive 15 July 2026, Conseil constitutionnel conforme 14 August, promulgated 18 August 2026. 380 scrutins name the dossier; 931 s. This vote is a vote on the whole text or the motion itself, so Pour is against us.

### [ ] `an-17-7432` la motion de rejet péalable, déposée par M. Patrick Hetzel, de la proposition de loi relative au droit à l'aide à mourir (nouvelle lecture).

- **When / result:** 2026-06-22; Assemblée nationale; rejeté; Pour 91, Contre 139, Abstain 1
- **On:** Fin de vie
- **Lobbies:** Pour: RN 60, DR 10, UDDPLR 10, EPR 7, HOR 3, NI 1. Contre: LFI-NFP 42, SOC 33, EPR 23, ECOS 21, DEM 10, HOR 6, GDR 2, LIOT 2. Abstain: SOC 1
- Meaning: **Pour** = to reject DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) outright at this stage (a motion to reject); **Contre** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour +2 (Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for rejecting it, with CitizenGO's position.); Contre -2 (Voted Contre on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): against rejecting it, against CitizenGO's position.)
- **Reasoning:** Area 2 (assisted dying). Bill direction on file for DLR5L17N51670 (a draft): passing it is AGAINST us -- Droit a l'aide a mourir (dossier 'Fin de vie'). Adopted in lecture definitive 15 July 2026, Conseil constitutionnel conforme 14 August, promulgated 18 August 2026. 380 scrutins name the dossier; 931 s. This vote is a motion to reject the text (the sides are swapped), so Pour is with us.

### [ ] `an-17-5729` l'ensemble de la proposition de loi relative au droit à l'aide à mourir (deuxième lecture).

- **When / result:** 2026-02-25; Assemblée nationale; adopté; Pour 299, Contre 226, Abstain 37
- **On:** Fin de vie
- **Lobbies:** Pour: EPR 64, LFI-NFP 62, SOC 60, ECOS 35, DEM 20, RN 17, HOR 14, GDR 11, LIOT 8, DR 5, NI 3. Contre: RN 102, DR 42, HOR 18, UDDPLR 17, EPR 14, DEM 12, NI 7, LIOT 6, SOC 4, GDR 2, LFI-NFP 1, ECOS 1. Abstain: EPR 9, LIOT 8, DEM 4, GDR 4, SOC 3, RN 3, DR 2, HOR 2, ECOS 2
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour -2 (Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.); Contre +2 (Voted Contre on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): against passing it, with CitizenGO's position.)
- **Reasoning:** Area 2 (assisted dying). Bill direction on file for DLR5L17N51670 (a draft): passing it is AGAINST us -- Droit a l'aide a mourir (dossier 'Fin de vie'). Adopted in lecture definitive 15 July 2026, Conseil constitutionnel conforme 14 August, promulgated 18 August 2026. 380 scrutins name the dossier; 931 s. This vote is a vote on the whole text or the motion itself, so Pour is against us.

### [ ] `senat-2025-169` sur l'ensemble de la proposition de loi relative au droit à l'aide à mourir

- **When / result:** 2026-01-28; senat; Pour 122, Contre 181, Abstain 38
- **On:** Fin de vie
- **Lobbies:** Pour: Les Républicains 82, UCI 24, Les Indépendants 8, NI 4, CRCE-K 2, RDPI 2. Contre: SER 60, Les Républicains 36, UCI 24, GEST 16, RDSE 16, CRCE-K 15, RDPI 12, Les Indépendants 2. Abstain: Les Républicains 11, UCI 11, Les Indépendants 10, RDPI 5, CRCE-K 1
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour -2 (Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.); Contre +2 (Voted Contre on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): against passing it, with CitizenGO's position.)
- **Reasoning:** Area 2 (assisted dying). Bill direction on file for DLR5L17N51670 (a draft): passing it is AGAINST us -- Droit a l'aide a mourir (dossier 'Fin de vie'). Adopted in lecture definitive 15 July 2026, Conseil constitutionnel conforme 14 August, promulgated 18 August 2026. 380 scrutins name the dossier; 931 s. This vote is a vote on the whole text or the motion itself, so Pour is against us.

### [ ] `an-17-5192` l'ensemble de la proposition de loi visant à protéger les mineurs des risques auxquels les expose l'utilisation des réseaux sociaux (première lecture).

- **When / result:** 2026-01-26; Assemblée nationale; adopté; Pour 130, Contre 21, Abstain 6
- **On:** Protéger les mineurs des risques auxquels les expose l’utilisation des réseaux sociaux
- **Lobbies:** Pour: EPR 61, RN 22, HOR 11, SOC 10, DR 9, DEM 8, ECOS 3, NI 2, LIOT 2, UDDPLR 2. Contre: LFI-NFP 19, ECOS 2. Abstain: SOC 2, GDR 2, ECOS 2
- Meaning: **Pour** = to pass DLR5L17N53187 (the under-15 social media rule and age checks) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour -2 (Voted Pour on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): for passing it, against CitizenGO's position.); Contre +2 (Voted Contre on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): against passing it, with CitizenGO's position.)
- **Reasoning:** Area 7 (free speech and civil liberties). Bill direction on file for DLR5L17N53187 (CONFIRMED): passing it is AGAINST us -- Protect minors from the risks of social networks (ppl25-304): the under-15 social media rule and age checks. Passed the Senat on 21 July 2026. Matched nothing. This vote is a vote on the whole text or the motion itself, so Pour is against us.

### [ ] `an-17-5156` sur la motion de rejet préalable, déposée par Mme Mathilde Panot, de la proposition de loi visant à protéger les mineurs des risques auxquels les expose l'utili

- **When / result:** 2026-01-26; Assemblée nationale; rejeté; Pour 25, Contre 109, Abstain 2
- **On:** Protéger les mineurs des risques auxquels les expose l’utilisation des réseaux sociaux
- **Lobbies:** Pour: LFI-NFP 25. Contre: EPR 55, RN 14, SOC 11, ECOS 8, HOR 7, DR 6, DEM 5, NI 2, LIOT 1. Abstain: GDR 2
- Meaning: **Pour** = to reject DLR5L17N53187 (the under-15 social media rule and age checks) outright at this stage (a motion to reject); **Contre** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour +2 (Voted Pour on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): for rejecting it, with CitizenGO's position.); Contre -2 (Voted Contre on DLR5L17N53187 (Protect minors from the risks of social networks (ppl25-304): the under-15 social media ru): against rejecting it, against CitizenGO's position.)
- **Reasoning:** Area 7 (free speech and civil liberties). Bill direction on file for DLR5L17N53187 (CONFIRMED): passing it is AGAINST us -- Protect minors from the risks of social networks (ppl25-304): the under-15 social media rule and age checks. Passed the Senat on 21 July 2026. Matched nothing. This vote is a motion to reject the text (the sides are swapped), so Pour is with us.

### [ ] `an-17-2107` l’ensemble de la proposition de loi relative au droit à l’aide à mourir (première lecture).

- **When / result:** 2025-05-27; Assemblée nationale; adopté; Pour 305, Contre 199, Abstain 57
- **On:** Fin de vie
- **Lobbies:** Pour: EPR 64, LFI-NFP 62, SOC 59, ECOS 33, DEM 20, RN 19, HOR 14, GDR 12, LIOT 11, DR 7, NI 4. Contre: RN 101, DR 34, PO847173 16, HOR 13, EPR 11, DEM 9, NI 5, SOC 4, LIOT 3, GDR 1, LFI-NFP 1, ECOS 1. Abstain: EPR 14, LIOT 9, DR 8, DEM 7, HOR 6, GDR 3, RN 3, LFI-NFP 3, SOC 2, NI 1, ECOS 1
- Meaning: **Pour** = to pass DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed direction:** Pour -2 (Voted Pour on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): for passing it, against CitizenGO's position.); Contre +2 (Voted Contre on DLR5L17N51670 (Droit a l'aide a mourir (dossier 'Fin de vie')): against passing it, with CitizenGO's position.)
- **Reasoning:** Area 2 (assisted dying). Bill direction on file for DLR5L17N51670 (a draft): passing it is AGAINST us -- Droit a l'aide a mourir (dossier 'Fin de vie'). Adopted in lecture definitive 15 July 2026, Conseil constitutionnel conforme 14 August, promulgated 18 August 2026. 380 scrutins name the dossier; 931 s. This vote is a vote on the whole text or the motion itself, so Pour is against us.

## Needs reading (no box: write the values first)

- `senat-2025-313` 2026-06-16 sur l'ensemble de la proposition de loi visant à réparer les préjudices causés par la transplantation de mineu [final]: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L17N51845: CitizenGO's position on 'Réparer les préjudices causés par la transplantation de mineurs de La Réunion en France hexagona
  - Meaning: **Pour** = to pass the text “Réparer les préjudices causés par la transplantation de mineurs de La Réunion en France…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `senat-2025-294` 2026-06-09 sur l'ensemble de la proposition de loi visant à garantir la neutralité financière du don d'organes et d'autre [final]: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L17N53976: CitizenGO's position on 'Proposition de loi visant à garantir la neutralité financière du don d'organes par les vivants' 
  - Meaning: **Pour** = to pass the text “Proposition de loi visant à garantir la neutralité financière du don d'organes par les…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `senat-2025-251` 2026-05-11 sur l'ensemble de la proposition de loi visant à garantir l'égal accès de tous à l'accompagnement et aux soins [final]: The direction of DLR5L17N51672 is on hold: read the promulgated text first: if it legitimises assisted dying, passing it is against us. Nothing is drafted or confirmed from this bill until then.
  - Meaning: **Pour** = to pass DLR5L17N51672 (Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law; promulgated 26 May 2026) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `senat-2025-238` 2026-05-05 sur l'ensemble de la proposition de loi visant à lutter contre l'entrisme islamiste en France [final]: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L17N53936: CitizenGO's position on 'Proposition de loi visant à lutter contre l’entrisme islamiste en France' needs a human reading.
  - Meaning: **Pour** = to pass the text “Proposition de loi visant à lutter contre l’entrisme islamiste en France” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `an-17-5728` 2026-02-25 l'ensemble de la proposition de loi visant à garantir l'égal accès de tous à l'accompagnement et aux soins pal [final]: The direction of DLR5L17N51672 is on hold: read the promulgated text first: if it legitimises assisted dying, passing it is against us. Nothing is drafted or confirmed from this bill until then.
  - Meaning: **Pour** = to pass DLR5L17N51672 (Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law; promulgated 26 May 2026) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `senat-2025-185` 2026-02-10 sur l'ensemble de la proposition de loi visant à prohiber l'achat de services sexuels virtuels personnalisés e [final]: A vote on the whole text or the motion itself, but no bill direction is on file for this item: CitizenGO's position on 'sur l'ensemble de la proposition de loi visant à prohiber l'achat de services sexuels virtuels perso
  - Meaning: **Pour** = to pass the text “sur l'ensemble de la proposition de loi visant à prohiber l'achat de services sexuels…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `senat-2025-170` 2026-01-28 sur l'ensemble de la proposition de loi visant à garantir l'égal accès de tous à l'accompagnement et aux soins [final]: The direction of DLR5L17N51672 is on hold: read the promulgated text first: if it legitimises assisted dying, passing it is against us. Nothing is drafted or confirmed from this bill until then.
  - Meaning: **Pour** = to pass DLR5L17N51672 (Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law; promulgated 26 May 2026) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `an-17-5244` 2026-01-28 l'ensemble de la proposition de loi visant à réparer les préjudices causés par la transplantation de mineurs d [final]: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L17N51845: CitizenGO's position on 'Réparer les préjudices causés par la transplantation de mineurs de La Réunion en France hexagona
  - Meaning: **Pour** = to pass the text “Réparer les préjudices causés par la transplantation de mineurs de La Réunion en France…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `an-17-4839` 2025-12-18 l'ensemble de la proposition de loi visant à reconnaître le préjudice subi par les personnes condamnées sur le [final]: A vote on the whole text or the motion itself, but no bill direction is on file for this item: CitizenGO's position on 'l'ensemble de la proposition de loi visant à reconnaître le préjudice subi par les personnes condamn
  - Meaning: **Pour** = to pass the text “l'ensemble de la proposition de loi visant à reconnaître le préjudice subi par les…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `an-17-2106` 2025-05-27 l’ensemble de la proposition de loi visant à garantir l'égal accès de tous à l’accompagnement et aux soins pal [final]: The direction of DLR5L17N51672 is on hold: read the promulgated text first: if it legitimises assisted dying, passing it is against us. Nothing is drafted or confirmed from this bill until then.
  - Meaning: **Pour** = to pass DLR5L17N51672 (Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law; promulgated 26 May 2026) as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `an-17-1725` 2025-05-15 l'ensemble de la proposition de loi visant à lutter contre la pédocriminalité (première lecture). [final]: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L17N50627: CitizenGO's position on 'Lutter contre la pédocriminalité' needs a human reading. Add a `bill_directions` line or write y
  - Meaning: **Pour** = to pass the text “l'ensemble de la proposition de loi visant à lutter contre la pédocriminalité (première…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `senat-2024-237` 2025-03-20 sur l'ensemble de la proposition de loi visant à reconnaître le préjudice subi par les personnes condamnées su [final]: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L17N51351: CitizenGO's position on 'Proposition de loi visant à reconnaître le préjudice subi par les personnes condamnées sur le fo
  - Meaning: **Pour** = to pass the text “Proposition de loi visant à reconnaître le préjudice subi par les personnes condamnées…” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_
- `senat-2024-199` 2025-02-18 sur l'ensemble de la proposition de loi visant à assurer le respect du principe de laïcité dans le sport [final]: A vote on the whole text or the motion itself, but no bill direction is on file for DLR5L16N49619: CitizenGO's position on 'Proposition de loi visant à assurer le respect du principe de laïcité dans le sport' needs a hum
  - Meaning: **Pour** = to pass the text “Proposition de loi visant à assurer le respect du principe de laïcité dans le sport” as a whole; **Contre** = against passing it. _(by rule, from the vote's wording and the bill)_

## Bill directions on file (inputs to the drafts; they place nobody)

- `DLR5L17N51670` against: Droit a l'aide a mourir (dossier 'Fin de vie'). Adopted in lecture definitive 15 July 2026, Conseil constitutionnel conforme 14 August, promulgated 18 August 2026. 380 scrutins name the dossier; 931 s (draft)
- `DLR5L17N51672` hold: Soins palliatifs et d'accompagnement, the companion bill to the aide a mourir law; promulgated 26 May 2026. Quebec has 'soins palliatifs' at tier 2 only. (needs_reading)
- `DLR5L16N49654` with: Senate bill to regulate medical practices for minors 'en questionnement de genre' (ppl23-435), adopted by the Senat and pending at the Assemblee since the 16th legislature. No Quebec term matches 'que (draft)
- `DLR5L17N53037` against: Universaliser l'assistance medicale a la procreation. France's legal term is 'assistance medicale a la procreation' (AMP); Quebec's list has 'procreation medicalement assistee'. (draft)
- `DLR5L17N51004` against: Faciliter la reconnaissance du genre a l'etat civil: self-identification at the civil register. Matched nothing. (draft)
- `DLR5L17N53403` against: Droits des personnes LGBTQIA+, intersex children and 'reconnaissance du genre a l'etat civil'. Matched nothing. (draft)
- `DLR5L17N53187` against: Protect minors from the risks of social networks (ppl25-304): the under-15 social media rule and age checks. Passed the Senat on 21 July 2026. Matched nothing. (confirmed)

