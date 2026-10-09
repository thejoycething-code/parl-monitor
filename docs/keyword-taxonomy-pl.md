# Parliamentary Monitor: Polish keyword taxonomy

**Version 0.2 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

## Purpose

The Polish list for the Sejm.

**This file is the master.** `config/taxonomy-pl.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang pl`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of Poland (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- Poland PL1: list approved as drafted
- Poland X12: antykoncepcj*, pigułk* dzień po and ellaOne already sit in area 1 tier 2; no move needed
- Poland X11: przemoc* wobec kobiet / ze względu na płeć / domow* already area 5 tier 2
- Poland X13: no antisemitism terms in the Polish list
- Poland Converted 'płe* kulturow* and płc* kulturow*' (and the biologiczn* and metrykaln* pairs) into separate terms
- Poland Converted [PL]-marked terms to 'only'
- Poland Guards written as [with: ...] from the doc's braces; 'Kodeks* karn*' quoted as a phrase guard

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** aborcj*; aborcyjn*; "przerywani* ciąży"; "przerwani* ciąży"; "przerywaniu ciąży"; "dopuszczalnoś* przerywania ciąży"; "ochron* płodu"; "ochron* życia poczętego"; "dzieci* poczęt*"; "dziecka poczętego"; "życi* poczęt*"; "pigułk* poronn*"; "planowaniu rodziny, ochronie płodu ludzkiego"; "kompromis* aborcyjn*"; "Trybunał* Konstytucyjn* z 22 października 2020"
- **Tier 2:** "praw* reprodukcyjn*"; "zdrowi* reprodukcyjn*"; "zdrowi* prokreacyjn*"; "klauzul* sumienia"; antykoncepcj*; "pigułk* dzień po"; ellaOne; "badani* prenataln*"; "diagnostyk* prenataln*"; "wad* letaln*"; "letalnie chor*"; poronieni*; "martw* urodzeni*"; "hospicj* perinataln*"; "okienk* życia"
- **Notes:** Poland: Polish terms measured against Sejm prints; bare ciąż* dropped after it tagged a pregnant workers' benefit bill and two unrelated bills.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanazj*; "wspomagan* samobójstw*"; "samobójstw* wspomagan*"; "pomoc* w samobójstwie"; "pomoc* w umieraniu"; "zabójstw* eutanatyczn*"
- **Tier 2:** "opiek* paliatywn*"; hospicj*; "uporczyw* terapi*"; "oświadczeni* pro futuro"; "testament* biologiczn*"; "medycyn* paliatywn*"
- **Notes:** No terms proposed for this area.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "bloker* dojrzewania"; "blokowani* dojrzewania"; "hormon* płciow*"; tranzycj*; "dysfori* płciow*"; "zmian* płci"; "korekt* płci"; "uzgodnieni* płci"; "uzgadnianiu płci"; "terapi* afirmując*"; "chirurgi* zmiany płci"
- **Tier 2:** detranzycj*; transpłciow*; niebinarn*; "tożsamoś* płciow*"
- **Notes:** No terms proposed for this area.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "terapi* konwersyjn*"; "praktyk* konwersyjn*"; "terapi* reparatywn*"
- **Tier 2:** "orientacj* seksualn*" [with: terapi*, zakaz*, zmian*]
- **Notes:** No terms proposed for this area.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "ideologi* gender"; "ideologi* LGBT"; gender; LGBT*; "konwencj* stambulsk*"; "Konwencj* Rady Europy o zapobieganiu i zwalczaniu przemocy wobec kobiet"; "tożsamoś* płciow*"; "ekspresj* płciow*"; "płe* kulturow*"; "płc* kulturow*"; "płe* biologiczn*"; "płc* biologiczn*"; "płe* metrykaln*"; "płc* metrykaln*"; "strefy wolne od LGBT"; "kobiet* trans*"; "sport* kobiet*"; "neutralnoś* pod względem płci"; feminatyw*
- **Tier 2:** "orientacj* seksualn*"; "osob* LGBT*"; "mniejszoś* seksualn*"; "równoś* płci"; "równego traktowania"; "przemoc* ze względu na płeć"; "przemoc* wobec kobiet"; "przemoc* domow*"; parytet*; homofobi*; transfobi*; "pełnomocni* rządu do spraw równego traktowania"; "pełnomocni* rządu do spraw równości"
- **Notes:** Poland: Bare 'gender' kept at tier 1: in Polish political usage the English word is the ideology debate.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "edukacj* seksualn*"; "edukacj* zdrowotn*"; "wychowani* do życia w rodzinie"; "religi* w szkol*"; "lekcj* religii"; "nauczani* religii"; "nauk* religii"; katechez*; katechet*; "etyk* w szkol*"; "praw* rodziców"; "prawa rodziców do wychowania"; "władz* rodzicielsk*"; "edukacj* domow*"; "lex Czarnek"
- **Tier 2:** "podstaw* programow*"; "organizacj* w szkole"; "zgod* rodzica"; "zgod* rodziców"; "wykorzystani* seksualn* małoletnich"; "wykorzystaniu seksualnemu małoletnich"; "Rzecznik* Praw Dziecka"; "praw* dziecka"; "pieczy zastępcz*"; "piecz* zastępcz*"; "kurator* oświaty"; "prawo oświatowe"; "system* oświaty"; "szkoł* niepubliczn*"; "ochron* małoletnich"; "ochronie małoletnich"; "Standard* Ochrony Małoletnich"; "smartfon* w szkoł*"; "telefon* komórkow* w szkoł*"; "wychowani* patriotyczn*"
- **Notes:** Poland: prawo oświatowe is the noisiest tier-2 term (15 bills, many amending the education act in passing); kept at tier 2 for triage.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "mow* nienawiści"; "przestępstw* z nienawiści"; "przestępstw* motywowan* uprzedzeniami"; "wolnoś* słowa"; "wolnoś* wypowiedzi"; "swobod* wypowiedzi"; cenzur*; "akt* o usługach cyfrowych"; "usługach cyfrowych"; "weryfikacj* wieku" [with: internecie, internetu, online, pornograf*, "platform* internetow*", "platform* cyfrow*", "stron* internetow*", "serwis* internetow*", "usług* cyfrow*"]; "art. 256" [with: "kodeks* karn*"]; "art. 257" [with: "kodeks* karn*"]; "znieważeni* grupy"; "nawoływani* do nienawiści"; "pandemi* traktat*"; "porozumieni* pandemiczn*"; "Międzynarodow* Przepis* Zdrowotn*"
- **Tier 2:** dezinformacj*; pornograf*; "treści szkodliw*"; "treści nielegaln*"; "platform* internetow*"; "platform* cyfrow*"; "media społecznościow*"; "mediów społecznościowych"; szyfrowani*; inwigilacj*; Pegasus*; "kontrol* operacyjn*"; "radiofonii i telewizji" [without: "wychowaniu w trzeźwości"]; "Krajow* Rad* Radiofonii"; zniesławieni*; "Światow* Organizacj* Zdrowia"; "Europejsk* Konwencj* Praw Człowieka"
- **Notes:** v0.2: "weryfikacj* wieku" needs an online, platform or pornography context and "radiofonii i telewizji" is vetoed by "wychowaniu w trzeźwości": on the 9 October scoping store the alcohol bills (druki 2007 and 2010: age checks at the till, a ban on alcohol advertising in broadcasting) matched area 7 through them, 24 votes; the online age-verification bill (10/1006) still matches.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "obraz* uczuć religijnych"; "obrażani* uczuć religijnych"; "art. 196" [with: "kodeks* karn*"]; "wolnoś* religi*"; "wolnoś* sumienia"; "wolnoś* wyznania"; "prześladowa* chrześcijan"; "prześladowa* religijn*"; "Fundusz* Kościeln*"; konkordat*; "symbol* religijn*"; "krzyż* w urzęd*"; "krzyż* w szkol*"; "krzyż* w Sejmie"; bluźnierstw*; "złośliwe przeszkadzanie"; "aktów religijnych"; "wyznawan* religi*"
- **Tier 2:** Kościół; Kościoł*; Kościel*; "związk* wyznaniow*"; "związków wyznaniowych"; "stosunku Państwa do"; duchown*; kapelan*; "miejsc* kultu"; chrześcijan*; katolick*; religijn*; "niedziel* wolne od handlu"; "zakaz* handlu w niedziel*"; "handlu w niedziele"; "klauzul* sumienia"
- **Notes:** Poland: Kości* is avoided because it also means bones; Kościół, Kościoł* and Kościel* are listed separately.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "małżeństw* jednopłciow*"; "związ* jednopłciow*"; "pary jednopłciow*"; "par* jednopłciow*"; "związ* partnersk*"; "status* osoby najbliższej"; "osob* najbliższ*"; "umow* o wspólnym pożyciu"; "równoś* małżeńsk*"; "art. 18 Konstytucji"; "definicj* małżeństwa"; "rozwod* pozasądow*"; "rozwiązani* małżeństwa"
- **Tier 2:** rozwod*; "Kodeks* rodzinn*"; "utrudniani* kontaktu"; babciow*; "Aktywn* rodzic*"; małżeńst*; małżeńsk*; "rodzin* wielodzietn*"; "Karta Dużej Rodziny"; "Karty Dużej Rodziny"; "świadczeni* wychowawcz*"; "800 plus"; 800+; "Rodzin* 800"; rodzicielstw*; macierzyńsk*; ojcostw*; dzietnoś*; demograf*; "polityk* rodzinn*"; alimen*; "urlop* rodzicielsk*"; becikow*; "przemoc* ekonomiczn*"
- **Notes:** No terms proposed for this area.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "macierzyństw* zastępcz*"; surogac*; "matk* zastępcz*"; "in vitro"; "zapłodnieni* pozaustrojow*"; "leczeni* niepłodności"; "leczeniu niepłodności"; embrion*; zarodk*; zarodek; "adopcj* zarodków"; "dawstw* komórek rozrodczych"; "komórek rozrodczych"
- **Tier 2:** niepłodnoś*; naprotechnologi*; "medycznie wspomagan* prokreacj*"; "wspomagan* rozrod*"; "edycj* genom*"; "substancj* pochodzenia ludzkiego"; "badani* genetyczn*"
- **Notes:** No terms proposed for this area.

### 11. Migration {#11_migration}

- **Tier 1:** "pakt* o migracji"; "pakt* migracyjn*"; "polityk* migracyjn*"; "zabezpieczeni* granicy"; "zakaz* wjazdu"; "relokacj* migrant*"; "nielegaln* migracj*"; "nielegaln* imigrac*"; "przekraczani* granicy"; "granic* z Białorusią"; "zawieszeni* prawa do azylu"; "prawa do azylu"; "strefy buforowej"; "stref* buforow*"; "zobowiązani* do powrotu"; pushback*
- **Tier 2:** deportac*; migrac*; "obywateli państw trzecich"; migrant*; imigra*; cudzoziem*; azyl* [without: zwierząt]; uchodźc*; "ochron* międzynarodow*"; "Straż* Granicz*" [with: migra*, cudzoziem*, azyl*, Białoru*, nielegaln*, uchodźc*, "granic* państwow*"]; Frontex; obywatelstw*; repatria*; wizow*; "zezwoleni* na pobyt"; "integracj* cudzoziemców"
- **Notes:** Poland: Straż Graniczna is guarded because unguarded it tagged every uniformed-services pension bill; azyl* vetoed by zwierząt (Central Animal Shelter).

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** prostytucj*; nierząd*; "kupowani* usług seksualnych"; "zakup* usług seksualnych"; sutener*; stręczyc*; kuplerstw*; "domów publicznych"; "dom* publiczn*"; "handl* ludźmi w celu wykorzystania seksualnego"; "model* nordyck*"
- **Tier 2:** "handl* ludźmi"; "handlu ludźmi"; "praca seksualn*"; "pracy seksualnej"; "prac* przymusow*"; niewolnictw*
- **Notes:** No terms proposed for this area.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** przeszczep*; transplantac*; transplantolog*; "pobierani* narządów"; "pobieraniu, przechowywaniu i przeszczepianiu"; "pobranie narządów"; "dawc* narządów"; "dawstw* narządów"; "sprzeciw* na pobranie"; "Centraln* Rejestr* Sprzeciwów"; "śmier* mózg*"; "handl* narządami"
- **Tier 2:** "komórek, tkanek i narządów"; "tkanek i narządów"; krwiodawstw*; "dawc* szpiku"
- **Notes:** No terms proposed for this area.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** rodzina; życie; prawo; dziecko; płeć; szkoła; ochrona; edukacja; przemoc; wolność; migracja; kościół

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang pl`. A new term needs a measurement, written in the area's Notes.
