# Parliamentary Monitor: French (France, Belgium, Switzerland) keyword taxonomy

**Version 0.2 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

**Extends:** qc

## Purpose

An ADDENDUM to the Quebec French master: the generated `config/taxonomy-fr.yaml` is every term of `docs/keyword-taxonomy-qc.md` plus the words below, for the Assemblée nationale, the French texts of the Belgian Chamber and the Swiss Federal Assembly. `config/taxonomy-qc.yaml`, and Quebec's matching with it, is untouched. Country-only terms are tagged `[only: fr]`, `[only: be]` or `[only: ch]`.

**This file is the master.** `config/taxonomy-fr.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang fr`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of France, Belgium, Switzerland (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
A term one country proposed as its own (a statute number, a national body, a national spelling) carries `[only: <code>]` and matches only for that country's collector; every other term is shared. Where countries proposed one term at different tiers, the shared copy takes the lower tier and the countries that asked for tier 1 get a tagged tier-1 copy, so no country is promoted past its own list. A term that one country guarded and another left bare is shared only in its guarded form; the bare copy is tagged for the countries that proposed it bare.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- France X4: list approved as drafted
- France FR2: political Islam terms in area 8 tier 2
- France X12: contraception already in taxonomy-qc area 1 tier 2; nothing to add
- France X13: no antisemitism terms in doc
- France Only additions to config/taxonomy-qc.yaml kept (accent, case and stem-insensitive comparison)
- France Guards written from prose: clause de conscience, délit d'entrave, transidentité*, réseaux sociaux, pornograph*, principes de la République, entrisme, profanation*
- Belgium X4: list approved as drafted
- Belgium Only terms absent from config/taxonomy-qc.yaml kept (accent, case and stem-insensitive comparison)
- Belgium BE3, BE4, BE5 applied as in be-nl
- Belgium X12: contracepti* area 1 tier 2
- Belgium X13: none in doc
- Belgium Guards written from prose: transition, délai de réflexion, vérification de l'âge, neutralité
- Switzerland X13: removed antisémitisme / Antisemitismus (area 8) from the Swiss additions
- Switzerland X11: domestic violence and femicide terms placed in area 5 tier 2
- Switzerland X12: no contraception term in the Swiss doc
- Switzerland CH2: individual taxation / marriage penalty added to area 9; CH3: E-ID added to area 7 tier 2 (the doc names the term E-ID without a tier); CH4: Verhüllungsverbot added to area 8 tier 1
- Switzerland Only terms absent from config/taxonomy-qc.yaml are listed

Noise round (v0.2, 10 October 2026, approved by Chris).

- `séparatisme` (area 8, France only) needs religious, Islamist, laïcité, worship, communitarianism or "principes de la République" company. Measured on the French scoping and chamber-layer stores: the five speeches of the low-emission-zones debate of 8 October ("un séparatisme territorial et social") and the dossier "Lutter contre le séparatisme social dans nos territoires" leave area 8; nothing else in the stores carried the word. Belgium, Switzerland and Quebec are untouched (the term is France-only and taxonomy-qc is unchanged).

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** "liberté garantie à la femme" [only: fr]; "clause de conscience" [with: IVG, "interruption* volontaire*", avortement*]; "délit d'entrave" [with: IVG, "interruption* volontaire*", avortement*] [only: fr]; "délit d'entrave" [only: be]
- **Tier 2:** "Planning familial" [only: fr]; "délai de réflexion" [with: avortement*, IVG, "interruption* volontaire*", "interruption* de grossesse"] [only: be]; "enfant* né* sans vie" [only: be]; contracepti*
- **Notes:** France: Measured on AN 2024-2026 data: délit d'entrave 5 written questions; clause de conscience caught DLR5L17N54992. Belgium: Measured on 1,776 dossier titles; stillborn-child bills in area 1 (BE3); délai de réflexion unguarded caught an electricity-contracts bill.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** "aide à mourir" [only: fr]; "assistance au suicide"; Claeys-Leonetti [only: fr]; "sédation profonde et continue" [only: fr]; "déclaration* anticipée*" [only: be]; "organisation* d'aide au suicide"; "capsule* de suicide"
- **Tier 2:** "soins d'accompagnement" [only: fr]; "directives anticipées" [only: fr]; "souffrance psychique" [only: be]; "vie accomplie"
- **Notes:** France: aide à mourir measured 931 scrutins, 1 dossier, 7 questions. Belgium: Eurovoc EUTHANASIE dossier 56/1338 caught by title terms. Switzerland: French titles say 'assistance au suicide' where the Quebec list has 'suicide assisté' and 'aide au suicide' (5 titles missed).

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "questionnement de genre" [only: fr]; transidentité* [with: mineur*, enfant*, jeune*, élève*]; transition [with: mineur*, enfant*]; "changement de sexe"
- **Tier 2:** transidentité* [only: fr]
- **Notes:** France: questionnement de genre caught DLR5L16N49654; transidentité* guarded at tier 1, bare at tier 2. Belgium: Only the guarded transition term is new beside taxonomy-qc. Switzerland: Counterpart of Geschlechtsumwandlung.

### 4. Conversion practices {#4_conversion_practices}

- **Notes:** No terms proposed for this area.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "reconnaissance du genre" [only: fr]; "changement de sexe à l'état civil" [only: fr]; "enregistrement du sexe"; "loi transgenre" [only: be]; non-binaire*; "sexe neutre" [only: be]; "non binaire*"
- **Tier 2:** LGBT*; "égalité de genre"; sexisme; féminicide*; "violence* domestique*"
- **Notes:** France: reconnaissance du genre and changement de sexe matched 2 dossiers. Belgium: Sexism tier 2: four 'sexism in public space' bills. Switzerland: Féminicide (11 titles, 9 missed) and violence domestique (14, all missed) at tier 2 under X11.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "instruction en famille" [only: fr]; "éducation à la vie affective" [only: fr]; EVARS [only: fr]; "établissement* hors contrat" [only: fr]; "école* hors contrat" [only: fr]; "autorité parentale" [only: be]; EVRAS [only: be]; "éducation à la vie relationnelle"; "enseignement à domicile"; "violence* éducative*"
- **Tier 2:** "autorité parentale"; "contrôle parental"; "droits de l'enfant"; "liberté d'enseignement" [only: be]; "protection de la jeunesse"; pornographie [with: mineur*, enfant*, jeune*]; "réseaux sociaux" [with: enfant*, jeune*, école*]
- **Notes:** France: instruction en famille 7 dossiers, 33 questions; EVARS 24 questions. Belgium: EVRAS is the compulsory relational and sexual education of the French Community; a community matter. Switzerland: Réseaux sociaux (14 titles, 13 missed) guarded to children, young people and school.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "majorité numérique" [only: fr]; "haine en ligne" [only: fr]; "contenus haineux" [only: fr]; "réseaux sociaux" [with: mineur*, "moins de quinze ans", "moins de 15 ans", âge]; pornograph* [with: mineur*, enfant*, âge]; "discours de haine"; "incitation à la haine" [only: be]; négationnisme [only: be]; blasphème; "norme pénale antiraciste" [only: ch]; 261bis [only: ch]
- **Tier 2:** Arcom [only: fr]; "loi* antidiscrimination" [only: be]; "loi antiracisme" [only: be]; "crime* de haine"; pornogra*; deepfake*; E-ID [only: ch]; "identité électronique" [only: ch]
- **Notes:** France: réseaux sociaux bare matched 39 scrutins, 12 dossiers, 216 questions, hence the guard. Belgium: Négationnisme is the 1995 Holocaust denial law. Switzerland: Swiss anti-racism penal norm; E-ID in by CH3 (8 and 15 titles), tier 2.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** séparatisme [with: religi*, islamis*, laïcité, laïque*, culte*, cultuel*, "principes de la République", communautaris*, entrisme, mosquée*, imam*] [only: fr]; "loi de 1905" [only: fr]; christianophobie [only: fr]; antichrétien* [only: fr]; "principes de la République" [with: culte*, religi*, association*, laïcité] [only: fr]; entrisme [with: islamis*, religi*, communautari*] [only: fr]; profanation* [with: église*, "lieu de culte", cimetière*, tombe*]; "liberté de culte"; "ministres des cultes" [only: be]; "signes convictionnels" [only: be]; foulard*; "secret de la confession" [only: be]; "abattage rituel"; "abattage sans étourdissement"; "chrétien* persécuté*"
- **Tier 2:** islamisme; islamiste* [only: fr]; prosélytisme [only: fr]; "port du voile" [only: fr]; abaya* [only: fr]; "Frères musulmans" [only: fr]; "convictions philosophiques"; neutralité [with: religi*, État]; cultes; "fabriques d'église" [only: be]; imam; imams; mosquée*; "persécution* des chrétiens"; voile [with: école*, enfant*]
- **Notes:** France: Political Islam in area 8 (FR2); entrisme 5 dossiers, 31 questions; islamisme terms tier 2 as drafted. Belgium: Religious-symbol bans and laicity (BE4); 'neutralité fiscale' matched unguarded neutralité; 'imam*' matched Imamoglu so whole words. Switzerland: Antisémitisme removed by X13; voile guarded to school and children (10 titles missed).

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "mariage pour tous" [only: fr]; coparentalité; "co-mère*" [only: be]; "imposition individuelle" [only: ch]; "pénalisation du mariage" [only: ch]
- **Tier 2:** "congé de naissance" [only: fr]; "adoption d'enfant*"; "adoption internationale"; "cohabitation légale" [only: be]; "congé parental"
- **Notes:** France: Sham-marriage bill (42 scrutins) not guarded: no guard approved. Belgium: Bare 'adoption' dropped: it is the adoption of a law; plural 'adoptions' escapes 'adoption d'enfant*'. Switzerland: Imposition individuelle: 13 titles, 12 missed; in by CH2.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "assistance médicale à la procréation" [only: fr]; PMA; GPA; bioéthique [only: fr]; "autoconservation des ovocytes"; "maternité de substitution"; "don d'ovocytes"; "anonymat du donneur"
- **Tier 2:** ovocyte*
- **Notes:** France: PMA 17 questions; bioéthique 19 questions, 1 dossier. Belgium: GPA is the common French abbreviation.

### 11. Migration {#11_migration}

- **Notes:** No terms proposed for this area.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** "système prostitutionnel" [only: fr]; "achat d'actes sexuels" [only: fr]; "achat d'un acte sexuel" [only: fr]; "traite des êtres humains"; pédocriminalité; pédopornograph*; souteneur*
- **Notes:** France: Système prostitutionnel is the 2016 law; traite des êtres humains 4 dossiers, 11 questions. Belgium: Traite des êtres humains is the Belgian legal term; mostly labour trafficking (BE5). Switzerland: Traite des êtres humains is the Swiss and French form (Quebec list has traite des personnes); 6 titles, 5 missed.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** "prélèvement* d'organes"; transplantation*
- **Tier 2:** "matériel corporel humain" [only: be]
- **Notes:** France: As drafted. Belgium: Matériel corporel humain: 2008 law on human body material.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** vida

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang fr`. A new term needs a measurement, written in the area's Notes.
