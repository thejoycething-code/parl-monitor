# Parliamentary Monitor: Quebec French keyword taxonomy

**Version 0.3 | 2 October 2026 | Owner: Christopher | Status: AI DRAFT, MEASURED AGAINST ASSNAT, NOT YET VERIFIED BY A QUEBEC READER**

## Purpose

The French-language filter layer for the Assemblée nationale du Québec
(`src/ingest/prov_qc.py`). The **areas are identical to the English taxonomy**
and carry the same keys: they are CitizenGO's positions, not anyone's
vocabulary. Only the terms differ.

**This file is the master.** `config/taxonomy-qc.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang qc`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

It is used by `src/prov_classify.py` for `prov = 'qc'` on FRENCH text only:
bill titles in French, the text of every bill (Quebec publishes bills in
French only), and the procès-verbal's own words for each vote. English
titles from the English bill pages are matched against the English taxonomy,
unchanged. The two are never run over each other's text.

## Status: draft, measured, not reviewed

Drafted by Claude on 2 October 2026 at Christopher's instruction ("all
provinces approved"). Every term below was measured against Quebec's own
texts before it was kept (see "How it was measured"); none has been read by
someone who campaigns in Quebec. Two kinds of error remain likely, as with
the German file: terms that are good French but not the words the
Assemblée actually uses, and terms that name the wrong side of a debate.

## How it was measured

- **Titles:** all 2,317 bill titles of the 36th to 43rd legislatures
  (sessions 36-1 to 43-3, 1,776 distinct), taken from each session's own
  bill listing on assnat.qc.ca on 2 October 2026.
- **Texts:** the presentation text (PDF) of 25 bills chosen because they are
  on our ground or look as if they might be, matched per passage with cited
  statutes masked, as the collector does: Bills 21 (42-1), 94 (43-1),
  9 (43-2), 52 (40-1 and its 41-1 reinstatement), 11 (43-1), 70 (42-1),
  103 (41-1), 2 (42-2), 62 (41-1), 60 (40-1), 12 (43-1), 73 (42-1), 595
  (41-1), 194 (43-1), 56 (43-1), 32 (42-2), 599 (42-1), 1 (43-2), 82
  (43-1), 125 (39-1), 26 (39-1), 84 (36-2), 1194 (41-1) and, as a plain
  control, Bill 9 of 43-3 (energy drinks).
- **Procès-verbaux:** every named vote read in the live smoke runs (June
  2019, October 2013, April-June 2023, October 2025, March-April 2026).
- A term that matched nothing is kept only where the reason is written down.

### Measured hit list (titles, 2 October 2026)

Tier-1 title hits by term, with the bills (session/number of the listing)
they hit. Every hit was read; none is a false positive by the standard of
"is this bill on CitizenGO's ground".

| Area | Term | Titles | Bills |
|---|---|---|---|
| 1 | `interruption* volontaire* de grossesse` | 2 | 41-1/595 (access buffer), 41-1/92 (RAMQ powers "et protéger l'accès aux services d'interruption volontaire de grossesse") |
| 2 | `soins de fin de vie` | 3 | 43-1/11, 41-1/52, 42-1/83 (amends the end-of-life care Act) |
| 3 | `mineur* transgenre*`, `enfant* transgenre*` | 2 | 41-1/103, 41-1/598 |
| 4 | `thérapie* de conversion` | 1 | 42-1/70 |
| 5 | `mention du sexe` | 2 | 41-1/598, 41-1/895 |
| 7 | `liberté d'expression`, `liberté académique`, `identité numérique` | 3 | 39-1/9 (anti-SLAPP), 42-2/32, 43-2/82 |
| 8 | `laïcité` | 7 | 42-1/21, 43-2/94, 43-2/9, 43-1/52 (notwithstanding renewal for Bill 21), 40-1/60, 40-1/398, 40-1/492 |
| 8 | `neutralité religieuse`, `accommodement* pour un motif religieux` | 3 | 41-1/62, 40-1/491, 40-1/60 |
| 9 | `union parentale`, `droit de la famille`, `filiation` | 5 | 36-2/84, 43-1/56, 43-1/12, 42-2/2, 41-1/797 |
| 10 | `grossesse pour autrui`, `mère* porteuse*`, `procréation assistée`, `embryon*` | 7 | 43-1/12, 42-1/73, 41-1/1196, 41-1/20 (ended IVF coverage), 39-1/26, 37-2/89, 38-1/95 |
| 12 | `exploitation sexuelle`, `traite des personnes` | 1 | 41-1/1194 |
| 13 | `don* d'organes`, `présomption de consentement` | 3 | 43-1/194, 39-1/125, 37-2/197 |

Tier 1 hit **36 distinct titles** of 1,776; the English taxonomy, run over
the same French titles, hits **none**. Tier-1 terms that hit no title
(`avortement*`, `aide médicale à mourir`, `signe* religieux`, `éducation à
la sexualité`, ...) are body-text vocabulary: each hit in the texts below.

### Measured on the 25 texts (areas from tier-1 passages)

| Bill | Areas | Terms that carried it |
|---|---|---|
| 21 (42-1) laïcité de l'État | 8 | laïcité, signe* religieux, neutralité religieuse, visage découvert, liberté de religion |
| 94 (43-1) laïcité in education | 6, 8 | laïcité, signe* religieux, **enseignement à la maison** |
| 9 (43-2) renforcement de la laïcité | 7, 8 | laïcité, signe* religieux, lieu* de culte, liberté académique |
| 60 (40-1) Charte des valeurs; 62 (41-1) neutralité | 8 | laïcité / neutralité religieuse, visage découvert |
| 52 (40-1, 41-1); 11 (43-1) | 2 | aide médicale à mourir, soins de fin de vie, sédation palliative continue |
| 70 (42-1); 599 (42-1) conversion therapies | 3, 4 | thérapie* de conversion (3 via identité de genre in the same passage) |
| 103 (41-1) transgender minors | 3, 5, 9 | mineur* transgenre*, mention du sexe, filiation |
| 2 (42-2) family law and civil status | 1, 3, 5, 9, 10 | mention du sexe, gestation pour autrui, filiation (area 1: the surrogate's right to end the pregnancy) |
| 12 (43-1) filiation and surrogacy | 1, 9, 10 | grossesse pour autrui, mère* porteuse*, filiation |
| 73 (42-1), 26 (39-1) assisted procreation | 10 (+1, 9 for 26) | procréation assistée, fécondation in vitro, embryon* |
| 84 (36-2) civil union; 56 (43-1) union parentale | 9 (+10 for 84) | union civile, union parentale, filiation |
| 595 (41-1) | 1 | interruption* volontaire* de grossesse |
| 1 (43-2) Quebec constitution | 1, 2, 8 | laïcité, interruption* volontaire* de grossesse, soins de fin de vie -- the draft constitution enshrines all three |
| 32 (42-2), 82 (43-1) | 7 | liberté académique, identité numérique |
| 125 (39-1), 194 (43-1) | 13 | don* d'organes, présomption de consentement |
| 1194 (41-1) | 12 | exploitation sexuelle, traite des personnes |
| **Control:** 9 (43-3) energy drinks | none | (`vérification de l'âge` matched until its guard was narrowed -- see area 7) |

Changes made BECAUSE of the measurement: `égalité entre les femmes et les
hommes` and `parité` left area 5 (they are the laicity bills' own preamble:
every laicity bill became "sex-based rights"); `protection de la jeunesse`
and `autorité parentale` left area 6 (the Youth Protection Act and the
organ-donation consent of minors); `censure` went to tier 2 (Bill 1 and the
"motion de censure"); bare `immigration` left area 11 (the minister's
title); `vérification de l'âge` is guarded by pornography and social-media
words, not "en ligne" (Bill 9 of 43-3 sells energy drinks online). After the full 42-1 bill sweep (182 texts): bare `interruption* de grossesse` and `union civile` went to tier 2 (parental-insurance benefits; the statutory definition of a spouse), and the collector now masks the capitalised heading an omnibus bill gives each Act it amends.

## Quebec-specific matching traps

- **`genre` means "kind".** "de tout genre", "ce genre de mesures". The bare
  word is never a term; `identité de genre` and `dysphorie de genre` are.
- **`trans` opens hundreds of words.** transport, transition, transmission,
  transaction. Never a stem; `transgenre*` and `personne* trans` only.
- **`conversion` is an insurance word here too.** Bill 222 (2016) is the
  "conversion" of two mutual insurers. Only `thérapie* de conversion` and
  `pratique* de conversion`.
- **`sexe` is mostly equality law.** "égalité des sexes", "parité". Only the
  civil-status phrases (`mention du sexe`) are terms.
- **`famille` and `enfant` are in a fifth of all titles** (garde éducatifs à
  l'enfance, conciliation famille-travail, pensions alimentaires). Never
  bare.
- **Statute names.** An amending bill cites every Act it touches with its
  chapter number: "Loi concernant les soins de fin de vie (chapitre
  S-32.0001)". The collector masks a cited statute that carries its chapter
  number before body passages are matched (the Alberta Bill 26 lesson in
  English); the bill's own title is matched unmasked.
- **Elision and apostrophes.** "l'avortement", "d’organes": the filter folds
  the typographic apostrophe and the left word boundary is the apostrophe,
  so `avortement*` matches "l'avortement".
- **Accents are kept.** Quebec's legislative French is consistently accented,
  and the collector normalises PDF text to composed characters (NFC) before
  matching, so `laïcité` matches a PDF's decomposed "laı̈cite".
- **Ligatures.** "fœtus" and "foetus", "œuvre" and "oeuvre": both spellings
  occur, so both are listed where it matters.
- **All-caps acronyms match case-sensitively** (`IVG`, `FIV`), so "ivg"
  inside a word cannot fire.

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** avortement*; "interruption* volontaire* de grossesse"; IVG; "pilule* abortive*"; mifépristone; "zone* tampon*" [with: avortement*, IVG, grossesse*, clinique*]
- **Tier 2:** "interruption* de grossesse"; "santé reproductive"; "droits reproductifs"; "santé sexuelle et reproductive"; "enfant* à naître"; fœtus; foetus; "mort-né*"; "objection de conscience"; contraception
- **Notes:** Measured: Bill 595 (2016), "accès aux établissements où se pratiquent des interruptions volontaires de grossesse", the only Quebec abortion bill in 2,317 titles; the stems take the plural of its title. `avortement*` matched nothing in titles and is the plain word of debate and of motions. `zone* tampon*` is guarded because it is also a farming and planning term. Bare `interruption* de grossesse` moved to tier 2 after the 42-1 sweep: it is also the parental-insurance benefit after a pregnancy ends (Bill 51, 2020), and a miscarriage is not our ground.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** "aide médicale à mourir"; "soins de fin de vie"; euthanasie; "suicide assisté"; "aide au suicide"; "mourir dans la dignité"; "sédation palliative continue"
- **Tier 2:** "soins palliatifs"; "fin de vie"; "directives médicales anticipées"; "maison* de soins palliatifs"
- **Notes:** Measured: Bill 52 (2013, reinstated 2014) "Loi concernant les soins de fin de vie" and Bill 11 (2023) "Loi modifiant la Loi concernant les soins de fin de vie", both in titles and in every passage of their texts that grants "l'aide médicale à mourir". The English taxonomy carries "end of life care" at tier 2 only; in Quebec "soins de fin de vie" is the name of the regime, so it is tier 1 here. `mourir dans la dignité` is the 2009-2012 select committee's name.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "dysphorie de genre"; "bloqueur* de puberté"; "bloqueur* d'hormones"; "inhibiteur* de puberté"; "mineur* transgenre*"; "enfant* transgenre*"; "transition de genre" [with: mineur*, enfant*, jeune*, élève*]; "Comité de sages sur l'identité de genre"
- **Tier 2:** transgenre*; "identité de genre"; "affirmation de genre"; "personne* trans"; détransition*; "réassignation sexuelle"
- **Notes:** Measured: Bill 103 (2016) "améliorer notamment la situation des mineurs transgenres" is the only title. `identité de genre` is tier 2 on purpose: it is a Charter ground cited in many texts that are not about medicine or children (Bill 70, Bill 2), and tier 2 sends it to the judge.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "thérapie* de conversion"; "pratique* de conversion"; "thérapie* réparatrice*"
- **Tier 2:** "orientation sexuelle" [with: changer, modifier, réprimer]
- **Notes:** Measured: Bill 70 (2020) "Loi visant à protéger les personnes contre les thérapies de conversion", title and text. Bare `conversion` is excluded: Bill 222 (2016) converts two mutual insurers.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "mention du sexe"; "mention de sexe"; "expression de genre"; "sexe biologique"; "non-mixité"; "espace* non mixte*"; toilettes [with: genre, sexe, trans*, mixte*]; vestiaire* [with: genre, sexe, trans*, mixte*]; "sport* féminin*" [with: trans*, genre, sexe, admissib*]; "athlète* trans*"
- **Tier 2:** "violence* faite* aux femmes"; "violence* conjugale*"
- **Notes:** v0.2 (Christopher, 2026-10-03: "Add 'gender expression' to the taxonomy, for all parliaments"). "identité ou expression de genre" is widened to "expression de genre", which catches both that title form and the text's "identité ou l'expression de genre". Measured: Bill 2 (2021) family-law reform, which rewrote the civil-status rules on "la mention du sexe"; Bill 103 (2016), which added "l'identité ou l'expression de genre" to the Charter -- so the phrase is stemmed in the text as "identité ou l'expression de genre" and the term needs the article-free form the titles use; private members' Bills 895 and 598 (2016) on "la mention du sexe". `égalité entre les femmes et les hommes` is tier 2: it is the laicity bills' own justification and on its own is equality law.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "éducation à la sexualité"; "éducation sexuelle"; "droits parentaux"; "droit* des parents"; "consentement parental"; "consentement des parents"; "enseignement à la maison"; "scolarisation à la maison"; "école à la maison"; "éthique et culture religieuse"; "culture et citoyenneté québécoise"; pronom* [with: élève*, école*, enseignant*, parent*]; "châtiment* corporel*"
- **Tier 2:** "école* privée* confessionnelle*"; "cellulaire* à l'école"
- **Notes:** Measured: Bill 898 (2016) "permettre aux parents d'inscrire leur enfant dans l'école de leur choix" is caught by nothing here and is left to the judge: school choice is not our ground. `éthique et culture religieuse` (ECR) and `culture et citoyenneté québécoise` (CCQ, which replaced ECR from 2023) are the compulsory course that carries religion and sexuality content. `protection de la jeunesse` is in dozens of titles and stays tier 2.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "liberté d'expression"; "liberté académique"; "discours haineux"; "propos haineux"; "identité numérique"; "vérification de l'âge" [with: pornograph*, "réseaux sociaux", "contenu* sexuel*", "site* pornographique*"]; islamophobie; "monnaie numérique de banque centrale"
- **Tier 2:** censure; "liberté de la presse"; "crime* haineux"; désinformation; "poursuite* abusive*"; "carte d'identité"
- **Notes:** Measured: Bill 32 (2022) "Loi sur la liberté académique dans le milieu universitaire"; Bill 9 (2009, 39-1) "favoriser le respect de la liberté d'expression" (the anti-SLAPP law); Bill 82 (2025) "Loi concernant l'identité numérique nationale", the analogue of the English tier-1 "digital identity". `censure` is tier 2: in the Assemblée it is also the "motion de censure", and it tagged the draft constitution (Bill 1, 43-2) at tier 1. `vérification de l'âge` is guarded by pornography and social-media words: its first guard, "en ligne", let through Bill 9 of 43-3 (no energy drinks to under-16s, online included).

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** laïcité; "liberté de religion"; "liberté de conscience et de religion"; "liberté religieuse"; "neutralité religieuse"; "signe* religieux"; "symbole* religieux"; "visage découvert"; "accommodement* pour un motif religieux"; "prière* de rue"; "prière* dans l'espace public"; "Charte des valeurs"; "persécution* religieuse*"
- **Tier 2:** laïque*; "lieu* de culte"; "intégrisme religieux"; "patrimoine religieux"; "accommodement* raisonnable*"; "motif religieux"
- **Notes:** Measured: Bill 21 (2019) "Loi sur la laïcité de l'État", Bill 94 (2025), Bill 52 (2024, renewing the notwithstanding clause for Bill 21), Bill 9 (2025) "Loi sur le renforcement de la laïcité au Québec", Bill 60 (2013) the Charter of values, private members' Bills 398 and 492 (2013), Bill 62 (2017) "neutralité religieuse de l'État" and its "visage découvert" rule. The English "laicity" was the only English term that would have found Bill 21, and only on its English title. CitizenGO's position on the laicity bills is a stance for Christopher; this file only finds them.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "union parentale"; "droit de la famille"; filiation; "mariage* entre personnes de même sexe"; "mariage* entre conjoints de même sexe"
- **Tier 2:** "union civile"; mariage; mariages; divorce; polygamie; "mariage* forcé*"; natalité; "politique familiale"
- **Notes:** `union civile` moved to tier 2 after the 42-1 sweep: every statute that defines a spouse says "lié par un mariage ou une union civile" (Bill 84, 2021, victims of crime). Measured: Bill 84 (2002) "instituant l'union civile et établissant de nouvelles règles de filiation" (Quebec's civil unions, open to same-sex couples, three years before federal marriage); Bill 2 (2021) and Bill 12 (2023) on filiation; Bill 56 (2024) "instituant le régime d'union parentale"; Bill 797 (2016). `filiation` is tier 1 because every Quebec bill that redefines who a parent is says it, and it is never used for anything else.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "gestation pour autrui"; "grossesse pour autrui"; "mère* porteuse*"; "procréation assistée"; "procréation médicalement assistée"; "fécondation in vitro"; embryon*; "don* de gamètes"; "don* d'ovules"; "don* de sperme"
- **Tier 2:** FIV; "projet parental"; gamète*
- **Notes:** Measured: Bill 12 (2023), whose text regulates "un projet parental impliquant une grossesse pour autrui" (the Quebec legal term; "mère porteuse" is the press word and both are listed); Bill 26 (39-1) and Bill 89 (37-2) "activités cliniques et de recherche en matière de procréation assistée"; Bill 73 (2021); Bill 95 (38-1) on "la conservation des organes, des tissus, des gamètes et des embryons", which `embryon*` takes into area 10 and `don* d'organes` does not take into 13 (it says "conservation des organes").

### 11. Migration {#11_migration}

- **Tier 1:** "immigration irrégulière"; "migrant* irrégulier*"; "passage* irrégulier*"; "chemin Roxham"; "seuil* d'immigration"
- **Tier 2:** "politique* d'immigration"; "demandeur* d'asile"; réfugié*; asile
- **Notes:** Collated, never campaigned (src/partner.py HIDDEN_AREAS). Listed so the area has the same keys as English. Bare `immigration` was dropped after the first live run: it is in the title of the minister who moved Bill 21 ("ministre de l'Immigration, de la Diversité et de l'Inclusion"), so it tagged the Bill 21 vote as area 11.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** "exploitation sexuelle"; "traite des personnes"; "traite de personnes"; proxénétisme; proxénète*; "achat de services sexuels"; "modèle nordique" [with: prostitution, "exploitation sexuelle", proxénète*, achat]
- **Tier 2:** prostitution; "travail du sexe"; "travailleu* du sexe"; "salon* de massage*"
- **Notes:** Measured: Bill 1194 (2017) "afin d'inclure les notions d'exploitation sexuelle et de traite des personnes". Quebec's 2019-2020 special committee was on "l'exploitation sexuelle des mineurs"; the phrase is how the Assemblée names this ground.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** "don* d'organes" [without: "normes du travail", "Code du travail", "s'absenter"]; "donneur* d'organes" [without: "normes du travail", "Code du travail", "s'absenter"]; "transplantation* d'organes"; "greffe* d'organes"; "consentement présumé" [with: organe*, don*, greffe*]; "présomption de consentement" [with: organe*, don*, greffe*]; "trafic d'organes"; "Transplant Québec"
- **Tier 2:** "don* de tissus"
- **Notes:** v0.3 (2026-10-02), the mirror of the English v1.16 veto (Christopher: "guard both taxonomy terms"): "don* d'organes" and "donneur* d'organes" do not match beside "normes du travail", "Code du travail" or "s'absenter". Quebec's Act respecting labour standards lets an employee be absent for organ or tissue donation, which is employment law, as Manitoba's and Newfoundland and Labrador's organ-donor leave are. "absence" is deliberately NOT a veto: a presumed-consent Bill speaks of "l'absence de refus". Measured: Bill 125 (2010) "Loi facilitant les dons d'organes et de tissus", Bill 197 (37-2) "facilitant les dons d'organes", and Bill 194 (43-1, still listed in 43-3) "instaurant une présomption de consentement au don d'organes ou de tissus après le décès" -- the Quebec form of deemed consent, which says "présomption de consentement", not "consentement présumé"; both are listed and both are guarded.

## Global exclusions

The bare words that must never be promoted to a term on their own, recorded here so the reason survives (advisory prose, not a filter input).

- **Terms:** genre; sexe; trans; conversion; transition; famille; enfant; parent; religion; liberté; égalité; éducation; vie; culte
- **Notes:** `genre` means "kind"; `trans` opens transport and transmission; `conversion` is an insurance word (Bill 222, 2016); `sexe` is equality law; `famille`, `enfant` and `parent` are in a fifth of all titles (childcare, family allowances, parental insurance); `religion`, `liberté` and `égalité` occur in every Charter amendment; `vie` is in "milieu de vie", "qualité de vie"; `culte` is also "culte de la personnalité".

## Maintenance

Corrections from a Quebec reader come in here, then `python3 tools/generate_taxonomy.py --lang qc`. A new term needs a measurement: the title or passage that justified it, written in the area's Notes.
