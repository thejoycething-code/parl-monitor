# Parliamentary Monitor: Croatian keyword taxonomy

**Version 0.1 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

## Purpose

The Croatian list for the Sabor.

**This file is the master.** `config/taxonomy-hr.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang hr`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of Croatia (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- Croatia HR1: list approved as drafted
- Croatia HR2: WHO sovereignty declaration brought in; added 'Svjetsk* zdravstven* organizacij*' to area 7 tier 2 (mirrors Poland and Slovakia; the doc offered no term)
- Croatia HR3: Sunday trading in area 8 via the drafted nedjelj* [with: rad*, trgovin*, neradn*]; no new term
- Croatia HR4: ombudsperson reports in; added 'pravobranitel* za ravnopravnost spolova' to area 5 tier 2 (pravobranitel* za djecu already area 6 tier 2)
- Croatia X12: kontracepcij* already area 1 tier 2
- Croatia X13: antisemitiz* already excluded in the doc
- Croatia priziv* savjesti listed in area 1 tier 2 and also area 8 tier 2 (the doc says 'also area 8')
- Croatia Guards converted from prose 'with a / b / c' to [with: ...]
- Croatia Country-only judged by me (doc has no markers): national laws, bodies and statute names

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** pobačaj*; abortus*; "prekid* trudnoće"; "prekidanj* trudnoće"; "slobodno odlučivanje o rađanju"; "slobodnom odlučivanju o rađanju"; nerođen*; "pravo na život"; "prav* na život od začeća"; "zaštit* nerođen*"; začeć*; "Hod za život"; "40 dana za život"; mifepriston*; "tablet* za pobačaj"; "pilul* za pobačaj"
- **Tier 2:** "reproduktivn* zdravlj*"; "reproduktivn* prav*"; "spoln* i reproduktivn*"; kontracepcij*; trudnic*; trudnoć*; "priziv* savjesti"; prenatal*; mrtvorođen*
- **Notes:** Croatia: Measured against the 11th Sabor's titles; 'slobodno odlučivanje o rađanju' is the 1978 law's name.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanazij*; "potpomognut* samoubojstv*"; "asistiran* samoubojstv*"; "potpomognut* umiranj*"; "usmrćenj* na zahtjev"; "dostojanstven* smrt*"; "dostojanstven* umiranj*"
- **Tier 2:** palijativ*; hospicij*; "kraj* život*"; "anticipirane naredbe"; "obvezujuć* izjav* volje"
- **Notes:** No terms proposed for this area.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "blokator* pubertet*"; "promjen* spola"; "prilagodb* spola"; "uskla* spola"; "rodn* disforij*"; "spoln* disforij*"; "rodn* nesklad*"; detranzicij*
- **Tier 2:** "hormonsk* terapij*" [with: djec*, maloljet*, spol*]; tranzicij* [with: spol*, rod*, maloljet*]
- **Notes:** Croatia: Tranzicij* is guarded because unguarded it is the economic transition of the 1990s.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "konverzijsk* terapij*"; "terapij* konverzije"; "reparativn* terapij*"; "konverzijsk* praks*"
- **Tier 2:** 
- **Notes:** No terms proposed for this area.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "rodn* ideologij*"; "rodn* identitet*"; "Istanbulsk* konvencij*"; "Konvencij* Vijeća Europe o spr*čavanju i borbi protiv nasilja nad ženama"; "rodno uvjetovan* nasilj*"; femicid*; transrodn*; transseksual*; nebinarn*; LGBT; LGBTI; LGBTIQ; LGBTQ
- **Tier 2:** "spoln* orijentacij*"; "ravnopravnost* spolova" [without: "Odbor* za izbor", "Odbor* za ravnopravnost spolova"]; "rodn* ravnopravnost*"; "rodno osjetljiv*"; "suzbijanj* diskriminacij*"; "nasilj* nad ženama"; interspoln*; "državn* maticama"; "pravobranitel* za ravnopravnost spolova"
- **Notes:** Croatia: spr*čavanju written to catch both 'sprječavanju' and the withdrawal bill's 'sprečavanju'; ravnopravnost spolova vetoed to cut committee appointments.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "zdravstven* odgoj*"; "spoln* odgoj*"; "seksualn* odgoj*"; "građansk* odgoj*"; "prav* roditelja"; "roditeljsk* prav*"; "kućn* školovanj*"; "školovanj* kod kuće"; "obrazovanj* kod kuće"; "nastav* kod kuće"; "digitaln* zaštit* djece"
- **Tier 2:** kurikul* [with: spol*, zdravstven*, građansk*, rod*, vjeronauk*]; "društven* mrež*" [with: djec*, maloljet*, škol*]; mobitel* [with: škol*, učenik*]; "zaštit* djece na internetu"; "roditeljsk* skrb*"; "osnovnoškolsk* odgoj*"; "pravobranitel* za djecu"; "odgoj* i obrazovanj* u osnovnoj i srednjoj školi"; udžbenic*; "predškolsk* odgoj*"
- **Notes:** No terms proposed for this area.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "slobod* govora"; "slobod* izražavanj*"; "slobod* mišljenja"; "govor* mržnje"; cenzur*; "Akt o digitalnim uslugama"; "Digital Services Act"; "Uredbe (EU) 2022/2065"; SLAPP; "otkrivanj* sadržaja izvida"; "sadržaja izvida"; "Lex AP"; "slobod* medija"; "Europsk* akt* o slobodi medija"; "Uredbe (EU) 2024/1083"
- **Tier 2:** dezinformacij*; "lažn* vijest*"; "elektroničkim medijima"; medijima; klevet*; uvred*; "poticanj* na nasilje i mržnju"; "zadržavanj* podataka"; "nadzor* komunikacij*"; "tajn* nadzor*"; "Svjetsk* zdravstven* organizacij*"
- **Notes:** Croatia: Lex AP is the 2024 offence of leaking investigation material, fought by journalists.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "vjersk* slobod*"; "slobod* vjeroispovijesti"; "slobod* savjesti"; vjeronauk*; "Svet* Stolic*"; "progon* kršćana"; blasfemij*; "vjersk* osjećaj*"
- **Tier 2:** "vjersk* zajednic*"; "Katoličk* Crkv*"; kršćan*; crkv*; nedjelj* [with: rad*, trgovin*, neradn*]; "pravnom položaju vjerskih zajednica"; "priziv* savjesti"
- **Notes:** No terms proposed for this area.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** brak*; bračn*; "životn* partnerstv*"; istospoln*; "osob* istog spola"; "Obiteljsk* zakon*"; "roditelj* odgojitelj*"; "obiteljsk* politik*"; pronatal*
- **Tier 2:** demograf*; rodiljn*; "roditeljsk* potpor*"; "doplat* za djecu"; posvojenj*; posvojitelj*; udomitelj*; udomljavanj*; obitelj* [without: branitelj*, "Odbor* za izbor", "Odbor* za obitelj", ministr*]; alimentacij*; "uzdržavanj* djece"
- **Notes:** Croatia: obitelj* carries vetoes: it matched 22 titles, 16 of them noise (Defenders and their Families Act, committee appointments).

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** surogat*; "zamjensk* majčinstv*"; "medicinski pomognut* oplodnj*"; "potpomognut* oplodnj*"; zametak; zametk*; embrij*; kloniranj*
- **Tier 2:** "matičn* stanic*"; neplodnost*; biomedicin*; "genetsk* testiranj*"
- **Notes:** No terms proposed for this area.

### 11. Migration {#11_migration}

- **Tier 1:** migracij*; migrant*; azil*; "međunarodn* zaštit*"; strancima; stranaca; "nezakonit* prelask*"
- **Tier 2:** "strani radnici"; "stranih radnika"; "radn* dozvol*"; granic*
- **Notes:** No terms proposed for this area.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** prostitucij*; "trgovanj* ljudima"; "trgovin* ljudima"; "trgovac ljudima"; pornograf*; "seksualn* iskorištavanj*"; "spoln* iskorištavanj*"; "spoln* zlostavljanj*"; "seksualn* zlostavljanj*"
- **Tier 2:** "zlostavljanj* djece"; "iskorištavanj* djece"; "dob* pristanka"; "provjer* dobi"; "dječj* pornograf*"
- **Notes:** No terms proposed for this area.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** presađivanj*; transplantacij*; "darivanj* organa"; "doniranj* organa"; "darivatelj* organa"
- **Tier 2:** "darivanj* krvi"; "tkiva i stanica"
- **Notes:** No terms proposed for this area.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** život; spol; zaštita

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang hr`. A new term needs a measurement, written in the area's Notes.
