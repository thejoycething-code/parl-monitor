# Parliamentary Monitor: Slovak keyword taxonomy

**Version 0.1 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

## Purpose

The Slovak list for the Národná rada.

**This file is the master.** `config/taxonomy-sk.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang sk`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of Slovakia (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- Slovakia SK1: list approved as drafted
- Slovakia SK2: NGO Act 213/1997 in, area 7 tier 2
- Slovakia SK3: Education Act net kept (školsk* zákon*, 245/2008)
- Slovakia SK4: parental allowance and pension kept in area 9 tier 2
- Slovakia X12: antikoncepci* already area 1 tier 2
- Slovakia X11: násili* na ženách and rodovo podmienen* násili* already area 5 tier 2
- Slovakia X13: no antisemitism terms
- Slovakia Law numbers marked country-only

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** potrat*; "umel* preruš* tehotenstva"; 73/1986; interrupci*; nenaroden*; "ochran* nenaroden*"; "počat* život*"; "od počatia"; "potratov* tabletk*"; mifepriston*; Medabon; "ochran* života od počatia"; "Pochod za život"
- **Tier 2:** "reprodukčn* zdravi*"; "reprodukčn* práv*"; "výhrad* vo svedomí"; "výhrad* svedomia"; antikoncepci*; "mŕtvo naroden*"; "Down* syndróm*"; "tehotn* žen*"; "prenatáln* diagnosti*"; "anonymn* pôrod*"; "hniezd* záchrany"
- **Notes:** Slovakia: Run over NR SR prints, votes and interpellations; 73/1986 is the Abortion Act.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanázi*; "asistovan* samovražd*"; "asistovan* smr*"; "asistovan* umieran*"; "dôstojn* smr*"
- **Tier 2:** paliatív*; hospic*; "nevyliečiteľn* chor*"; "konc* život*"
- **Notes:** No terms proposed for this area.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "blokátor* puberty"; "zmen* pohlav*"; "rodov* dysfóri*"; "pohlavn* dysfóri*"; "prechod* pohlav*"; "tranzíci* pohlav*"
- **Tier 2:** "hormonáln* liečb*"; tranzíci*; detranzíci*; "rodov* tranzíci*"
- **Notes:** No terms proposed for this area.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "konverzn* terapi*"; "konverzn* praktik*"; "reparatívn* terapi*"
- **Tier 2:** 
- **Notes:** No terms proposed for this area.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "rodov* ideológi*"; "genderov* ideológi*"; "Istanbulsk* dohovor*"; "rodov* identit*"; "biologick* pohlav*"; "dv* pohlav*"; "mužské a ženské"; LGBT*; "Stratégi* rovnosti LGBTIQ"
- **Tier 2:** "rodov* rovnos*"; "rodov* stereotyp*"; transrodov*; transsexu*; "násili* na ženách"; "rodovo podmienen* násili*"; genderov*; "sexuáln* orientáci*"; homosex*; "antidiskriminačn* zákon*"; "rovnak* zaobchádzan*"; 154/1994; 301/1995; 365/2004
- **Notes:** Slovakia: dv* pohlav* is the 2025 constitutional amendment's 'two sexes'; LGBT* is case-sensitive.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "sexuáln* výchov*"; "výchov* k manželstvu a rodičovstvu"; "práv* rodičov"; "informovan* súhlas* rodič*"; "súhlas* zákonn* zástupc*"; "domác* vzdelávan*"; "nábožensk* výchov*"; "telesn* tresta*"
- **Tier 2:** "individuáln* vzdelávan*"; "etick* výchov*"; "školsk* zákon*"; "obsah* vzdelávania"; "vzdelávac* program*"; "ochran* detí"; "ochran* maloletých"; "sociáln* siet*"; "sexuáln* zneužívan*"; "mimoškolsk* vzdelávan*"; "cirkevn* škol*"; "sociálnoprávn* ochran*"; 245/2008; 305/2005
- **Notes:** Slovakia: školsk* zákon* and 245/2008 kept as a net for triage (SK3): it brings in 14 prints.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "slobod* prejavu"; cenzúr*; "nenávistn* prejav*"; "overovan* veku"; "overeni* veku"; "pandemick* zmluv*"; "pandemick* dohod*"; "Medzinárodn* zdravotn* predpis*"; "digitáln* identit*"; "digitáln* eur*"; "zahraničn* agent*"
- **Tier 2:** dezinformáci*; hoax*; extrémizm*; "digitáln* služb*"; pornografi*; "Svetov* zdravotníck* organizáci*"; WHO; "mimovládn* neziskov* organizáci*"; "slobod* zhromažďovania"; hanobeni*; 213/1997
- **Notes:** Slovakia: 213/1997 (NGO Act) kept at tier 2 (SK2); its 2025 amendment brought 54 votes into the area.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "slobod* náboženstva"; "slobod* vierovyznania"; "nábožensk* slobod*"; "prenasledovan* kresťanov"; "registráci* cirkví"; "financovan* cirkví"; "Svät* stolic*"; "slobod* svedomia"; "postaveni* cirkví"; 308/1991; 370/2019
- **Tier 2:** cirkv*; cirkevn*; "nábožensk* spoločnos*"; "duchovn* služb*"; náboženstv*; vierovyznan*; kresťan*
- **Notes:** No terms proposed for this area.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "zväz* muža a ženy"; "zväzok medzi mužom a ženou"; "registrovan* partnerstv*"; "životn* partnerstv*"; "partnersk* zväz*"; "36/2005 Z. z."; "rovnakého pohlavia"; "spolužitie osôb"
- **Tier 2:** manželstv*; osvojeni*; rozvod*; "rodinn* politik*"; demografi*; pôrodnos*; natalit*; "rodičovsk* dôchod*"; "rodičovsk* príspev*"; "náhradn* starostlivos*"; pestúnsk*; "o rodine"
- **Notes:** Slovakia: rodičovsk* príspev* and rodičovsk* dôchod* kept in area 9 tier 2 (SK4).

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "náhradn* materstv*"; surogát*; "umel* oplodn*"; "asistovan* reprodukci*"; "ľudsk* embry*"; "embryonáln* kmeňov*"; "výskum* na embryách"
- **Tier 2:** embry*; "darcovstv* vajíčok"; "darcovstv* spermi*"; IVF; neplodnos*; "reprodukčn* medicín*"
- **Notes:** No terms proposed for this area.

### 11. Migration {#11_migration}

- **Tier 1:** "nelegáln* migráci*"; "migračn* pakt*"; "Pakt o migrácii"; "nelegáln* prisťahovalectv*"
- **Tier 2:** migráci*; azyl*; utečen*; "pobyt* cudzincov"; "štátn* občianstv*"; prisťahovalectv*
- **Notes:** No terms proposed for this area.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** kupliarstv*; nevestin*; "sexuáln* vykorisťovan*"; "kúp* sexuáln* služ*"; "nákup* sexuáln* služ*"; "obchodovan* so ženami"
- **Tier 2:** prostitúci*; "obchodovan* s ľuďmi"; "sexuáln* služ*"
- **Notes:** No terms proposed for this area.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** "darcovstv* orgánov"; transplantáci*; "darc* orgánov"; "obchodovan* s orgánmi"; "odber* orgánov"
- **Tier 2:** "predpokladan* súhlas*"; "ľudsk* tkan*"
- **Notes:** No terms proposed for this area.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** vida

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang sk`. A new term needs a measurement, written in the area's Notes.
