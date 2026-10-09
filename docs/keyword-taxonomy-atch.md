# Parliamentary Monitor: German additions (Austria and Switzerland) keyword taxonomy

**Version 0.1 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

**Extends:** de

## Purpose

An ADDENDUM to the German master: the generated `config/taxonomy-atch.yaml` is every term of `docs/keyword-taxonomy-de.md` plus the Austrian and Swiss words below, for the Austrian Parliament and the German texts of the Swiss Federal Assembly. `config/taxonomy-de.yaml`, and the Bundestag's matching with it, is untouched. Country-only terms are tagged `[only: at]` or `[only: ch]`.

**This file is the master.** `config/taxonomy-atch.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang atch`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of Austria, Switzerland (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
A term one country proposed as its own (a statute number, a national body, a national spelling) carries `[only: <code>]` and matches only for that country's collector; every other term is shared. Where countries proposed one term at different tiers, the shared copy takes the lower tier and the countries that asked for tier 1 get a tagged tier-1 copy, so no country is promoted past its own list. A term that one country guarded and another left bare is shared only in its guarded form; the bare copy is tagged for the countries that proposed it bare.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- Austria AT1: additions approved as drafted
- Austria AT2: Kinderbetreuungsgeld*, Familienbeihilfe*, Familienbonus* in area 9 tier 2
- Austria AT3: Pride* (guarded) and queer* in area 5 tier 2
- Austria X13: Antisemitismus* already in taxonomy-de, not an addition
- Austria Guard words in intergeschlechtlich*, Pride*, Kinderschutz*, Regenbogen* written as stems
- Switzerland X13: removed antisémitisme / Antisemitismus (area 8) from the Swiss additions
- Switzerland X11: domestic violence and femicide terms placed in area 5 tier 2
- Switzerland X12: no contraception term in the Swiss doc
- Switzerland CH2: individual taxation / marriage penalty added to area 9; CH3: E-ID added to area 7 tier 2 (the doc names the term E-ID without a tier); CH4: Verhüllungsverbot added to area 8 tier 1
- Switzerland Only terms absent from config/taxonomy-de.yaml are listed

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** Fristenlösung* [only: at]; Fristenlösung [only: ch]; "Art. 118 StGB" [only: ch]; "Art. 119 StGB" [only: ch]
- **Notes:** Austria: Fristenlösung measured 0 in titles; kept as the statutory name, expected in speeches and long titles. Switzerland: Swiss name Fristenlösung plus the Swiss Criminal Code sections 118 and 119; Abtreibung* already catches the titles.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** Sterbeverfügung* [only: at]; StVfG [only: at]; "assistiert* Suizid*"; Sarco; Suizidkapsel*; Sterbekapsel*; Suizidhilfeorganisation*; "geschäftsmässige Förderung der Selbsttötung" [only: ch]
- **Tier 2:** "Palliative Care"
- **Notes:** Austria: Sterbeverfügung: 6 of 6 items missed by taxonomy-de; StVfG is its abbreviation, case-sensitive. Switzerland: Stem replaces the nominative 'assistierter Suizid' that missed Mo. 25.3944; Swiss ss spelling of geschäftsmässig added because the base term has ß.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** Geschlechtsumwandlung*; Gender-Ideologie
- **Tier 2:** intergeschlechtlich* [with: Kind*, Jugendliche*, Behandlung*, medizinisch*]; Transgender
- **Notes:** Switzerland: Mo. 23.4408 'Stopp der Gender-Ideologie ... Geschlechtsumwandlung' had no term in either list.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** Konversionsmassnahme* [only: ch]
- **Notes:** Switzerland: Swiss ss spelling of the base term Konversionsmaßnahme*.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** Genderideologie*; Gender-Ideologie*; "biologische* Geschlecht*"; Transgender*; nonbinär*; non-binär*
- **Tier 2:** LGBTIQ*; LGBTQ*; intergeschlechtlich*; queer*; Pride* [with: Parade*, Flagge*, LGBT*, queer*, Kosten, Förderung*]; Binnen-I; Regenbogen* [with: Flagge*, Parade*, Fahne*]; LGBT*; "häusliche Gewalt"
- **Notes:** Austria: LGBTIQ*/LGBTQ* added because taxonomy-de has LSBTIQ only; Pride and queer funding in (AT3), tier 2. Switzerland: LGBTIQ is the Swiss acronym (base has LSBTIQ); häusliche Gewalt at tier 2 under X11 (9 titles, all missed).

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** Altersverifikation
- **Tier 2:** Kinderschutz* [with: digital*, online, Internet, "Social Media", Plattform*]; Ethikunterricht*; Altersverifikation*; Pornografie [with: Kinder, Jugendliche, Minderjährige]; "Jugendschutz in den Bereichen Film und Videospiele" [only: ch]; Smartphone [with: Kinder, Jugendliche, Schule]; "Social Media" [with: Kinder, Jugendliche, Schule]; "Lehrplan 21" [with: Sexual*, Gender*] [only: ch]
- **Notes:** Switzerland: Guarded to minors and schools; Jugendschutz (10 titles, 9 missed).

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "Hass im Netz" [only: at]; Kommunikationsplattformen-Gesetz* [only: at]; KoPl-G [only: at]; Bundestrojaner*; Messenger-Überwachung*; "Art. 261bis" [only: ch]; Diskriminierungsstrafnorm [only: ch]; Rassismusstrafnorm [only: ch]
- **Tier 2:** Verhetzung* [only: at]; E-ID [only: ch]
- **Notes:** Austria: Hass im Netz is Austria's 2021 online-hate package; KoPl-G is the platform law. Switzerland: Art. 261bis is the Swiss anti-racism penal norm; E-ID (22 titles, 21 missed) in by CH3 at tier 2.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** Gesichtsverhüllung*; Islamgesetz* [only: at]; "verfolgte* Christen"; "Christen in Nigeria"; Verhüllungsverbot
- **Tier 2:** "politische* Islam*"; "Dokumentationsstelle Politischer Islam" [only: at]; Zwangsverschleierung*; Kopftuchtrend*; Moschee*; Imam*; Landeskirche* [only: ch]
- **Notes:** Switzerland: Verhüllungsverbot (3 titles) in by CH4; Moschee (8 titles, 8 missed).

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** Individualbesteuerung [only: ch]; Heiratsstrafe [only: ch]; Ehepaarbesteuerung [only: ch]
- **Tier 2:** "eingetragene* Partnerschaft*" [only: at]; Obsorge* [only: at]; Kinderbetreuungsgeld* [only: at]; Familienbeihilfe* [only: at]; Familienbonus* [only: at]; Elternurlaub; Familienzulage* [only: ch]; Kinderbetreuung
- **Notes:** Austria: Family benefits in area 9 tier 2 (AT2); noisy benefit administration. Switzerland: Individual taxation (12 titles, 12 missed) in by CH2; Familienzulage 11 titles, all missed.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "medizinisch unterstützte Fortpflanzung" [only: ch]; Embryonenforschung
- **Notes:** Switzerland: Medizinisch unterstützte Fortpflanzung is the Swiss legal term (Fortpflanzungsmedizingesetz); 8 titles missed by German list, caught only by the French.

### 11. Migration {#11_migration}

- **Notes:** No terms proposed for this area.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** Pädokriminalität
- **Notes:** Switzerland: Pädokriminalität: 4 titles, 3 missed.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Notes:** No terms proposed for this area.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** vida

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang atch`. A new term needs a measurement, written in the area's Notes.
