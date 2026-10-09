# Parliamentary Monitor: Hungarian keyword taxonomy

**Version 0.2 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

## Purpose

The Hungarian list for the Országgyűlés.

**This file is the master.** `config/taxonomy-hu.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang hu`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of Hungary (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- Hungary HU3: list approved as drafted
- Hungary X13: removed antiszemitizmus* from area 8 tier 2
- Hungary X12: the doc has no contraception term; nothing to move
- Hungary HU4 and HU5 concern triage rules and votes, not terms; ignored
- Hungary [HU]-marked terms put in 'only'
- Hungary Guards: prose 'guarded to children/school' converted to [with: ...] using my own guard words

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** abortusz*; terhességmegszakítás*; terhesség-megszakítás*; "magzati élet*"; magzatvédel*; "magzati szívhang*"; fogantatás*; abortusztablett*; abortuszpirul*; Mifegyne; mifepriszton*; életvédő*
- **Tier 2:** magzat*; "reproduktív jog*"; "reproduktív egészség*"; "babamentő inkubátor*"; inkubátor*; koraszülött*; várandósgondoz*; "születendő gyermek*"; "méhen belül*"; prenatális*; magzatdiagnosztik*
- **Notes:** Hungary: Measured on karzat's derived data and the probe corpora; terms need trailing * because Hungarian is agglutinative.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanázi*; "asszisztált öngyilkosság*"; "asszisztált halál*"; "orvosi segítséggel történő"; "méltó halál*"; "önrendelkezés az élet végén"; "életvégi döntés*"; "Karsai Dániel*"
- **Tier 2:** palliatív*; hospice*; "életfenntartó kezelés*"; "ellátás visszautasítás*"; öngyilkosság-megelőzés*; öngyilkosságmegelőzés*; "élet végén"; haldokló*
- **Notes:** No terms proposed for this area.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** nemátalakító*; "nemváltó műtét*"; "nemi átalakít*"; pubertásblokkol*; pubertásgátl*; "nemi diszfóri*"; "nemi inkongruenci*"; detranzíci*
- **Tier 2:** hormonterápi* [with: gyermek*, gyerek*, kiskorú*, fiatalkorú*]; "nemi identitás*" [with: gyermek*, gyerek*, kiskorú*, fiatalkorú*]; tranzíci* [with: gyermek*, gyerek*, kiskorú*, fiatalkorú*]
- **Notes:** No terms proposed for this area.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "konverziós terápi*"; "konverziós gyakorlat*"; "konverziós kezelés*"; "reparatív terápi*"; "átnevelő terápi*"
- **Tier 2:** lelkigondoz* [with: konverziós, tilalom*, "szexuális irányultság*"]
- **Notes:** No terms proposed for this area.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "születési nem*"; "nem megváltoztatás*"; nemváltoztatás*; "nem módosítás*"; "nemi hovatartozás*"; "biológiai nem*"; transznemű*; "transz személy*"; interszex*; nembinár*; "nem binár*"; genderideológi*; gender-ideológi*; "társadalmi nem*"; "isztambuli egyezmény*"; "férfi vagy nő"; LMBT*
- **Tier 2:** homoszexualit*; homoszexuális*; "szexuális irányultság*"; "nemi irányultság*"; irányultság* [with: szexuális, nemi, LMBT*, homoszexu*]; "nemi identitás*"; "egyenlő bánásmód*"; "Egyenlő Bánásmód Hatóság*"; "nők elleni erőszak*"; "kapcsolati erőszak*"; femicid*; nőgyilkosság*; "női sport*" [with: transz*, "biológiai nem*", "születési nem*", LMBT*]
- **Notes:** No terms proposed for this area.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "gyermekvédelmi törvény*"; "gyermekvédelmi népszavazás*"; pedofilellenes*; "pedofil bűnelkövető*"; "szexuális nevelés*"; "szexuális felvilágosítás*"; érzékenyítő*; érzékenyítés*; "szülői jog*"; "szülők joga*"; "nevelési jog*"; otthonoktatás*; magántanuló*; "egyéni munkarend*"; "testi, szellemi és erkölcsi fejlődés*"; "megfelelő testi, szellemi"; Pride*
- **Tier 2:** gyermekvédel*; "Nemzeti alaptanterv*"; NAT; tankönyv*; "hit- és erkölcstan*"; köznevelés*; "közösségi média*" [with: gyermek*, gyerek*, kiskorú*, fiatalkorú*]; mobiltelefon* [with: iskol*, tanuló*, diák*]; "digitális eszköz*" [with: gyermek*, gyerek*, kiskorú*, fiatalkorú*]; korhatár-ellenőrzés*; életkor-ellenőrzés*; életkor-ellenőrző*; "kiskorúak védel*"; "gyermekek védel*"; gyermekjog*; tankötelezettség*
- **Notes:** Hungary: Pride* sits in area 6 as drafted (children); the Assembly Act terms are in area 7.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** szólásszabadság*; "véleménynyilvánítás szabadság*"; "véleménynyilvánítási szabadság*"; sajtószabadság*; gyűlöletbeszéd*; gyűlöletkelt*; "közösség elleni uszítás*"; rémhírterjesztés*; "Szuverenitásvédelmi Hivatal*"; szuverenitásvédel*; "közélet átláthatóság*"; "külföldről támogatott szervezet*"; cenzúr*; Pegasus*; kémprogram*; "gyülekezési jog*"; "gyülekezési törvény*"; "gyülekezési szabadság*"; arcfelismer*; "digitális szolgáltatásokról szóló"; DSA
- **Tier 2:** dezinformáci*; álhír*; gyűlöletbűncselekmény*; gyűlölet-bűncselekmény*; megfigyel*; adatvédel*; "titkos információgyűjtés*"; médiaszabályoz*; médiaszolgáltatás*; közmédia*; "Médiatanács*"; NMHH; "politikai reklám*"; platformszolgáltató*; "online platform*"; chatkontroll*; "külföldi befolyás*"; "külföldi támogatás*"; "civil szervezet*"
- **Notes:** Hungary: Sovereignty Protection Office, 2025 transparency bill and foreign-funding terms in area 7 as drafted.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** vallásszabadság*; "lelkiismereti és vallásszabadság*"; "lelkiismereti szabadság*"; "egyházi törvény*"; egyháztörvény*; "bevett egyház*"; "elismert egyház*"; "nyilvántartásba vett egyház*"; keresztényüldözés*; "üldözött keresztény*"; "keresztények üldözés*"; "Hungary Helps"; istenkáromlás*; "vallási közösség*"; "vallási kisebbség*"; "keresztény kisebbség*"
- **Tier 2:** egyházi*; egyház*; hitoktatás*; hitélet*; "vallási jelkép*"; "keresztény kultúr*"; "zsidó közösség*"; iszlám*; muszlim*; lelkész*
- **Notes:** Hungary: antiszemitizmus* removed under X13.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** házasság*; "egy férfi és egy nő"; "anya nő, az apa férfi"; "élettársi kapcsolat*"; "bejegyzett élettárs*"; "azonos nemű*"; örökbefogad*; családtámogatás*; családpolitik*; családvédel*; "Családvédelmi Akcióterv*"; babaváró*; CSOK; "családi otthonteremtési kedvezmény*"; "családi adókedvezmény*"; "gyermekgondozási díj*"; GYED; GYES; "gyermeknevelési támogatás*"; "családi pótlék*"
- **Tier 2:** családok*; családi*; családügy*; családbarát*; sokgyermekes*; nagycsalád*; demográfi*; népességfogy*; gyermekvállalás*; édesanyá*; anyák*; "szülési szabadság*"; "apasági szabadság*"; gyermekgondozás*; gyermektartás*; "szülői felügyelet*"; válás; válást; válási*; válásá*; válások*; válásuk*; válásr*; válásb*; válásn*; válásh*; válással; válásig; válásért; válástól; váláskor; kapcsolattartás*
- **Notes:** Hungary: Family benefits (CSOK, babaváró, GYED, GYES) at tier 1 as drafted. Divorce (v0.2, 10 October 2026): `válás*` is replaced by its explicit forms, because accents fold (X3) and the stem then matched "választás" (election) and "válasz"/"választ" (answer, the word in every vote on accepting a minister's reply to an interpellation, HU5). Measured on the term's gazette: 2 of 2 `válás*` hits were elections, none a divorce; on karzat's term-43 votes, every interpellation-answer vote. The forms cover the case endings and the possessive (válása, válásának) and none folds to "valasz".

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** béranyaság*; dajkaterhesség*; "helyettesítő anyaság*"; embrió*; lombik*; "mesterséges megtermékenyítés*"; "asszisztált reprodukci*"; "reprodukciós eljárás*"; "humán reprodukci*"; petesejt*; ivarsejt*; spermadonáci*; őssejt*; klónoz*; génszerkeszt*; "méhen kívüli megtermékenyítés*"; IVF
- **Tier 2:** meddőség*; termékenység*; reprodukciós*; "Humánreprodukciós*"
- **Notes:** No terms proposed for this area.

### 11. Migration {#11_migration}

- **Tier 1:** migráci*; migráns*; bevándorl*; menedékjog*; menekült*; határzár*; tranzitzón*; "illegális határátlép*"; "migrációs paktum*"; embercsempész*; kitoloncol*; kiutasít*
- **Tier 2:** vendégmunkás*; "harmadik országbeli*"; idegenrendészet*; "Országos Idegenrendészeti*"; "tartózkodási engedély*"; letelepedés*; határvédel*; határőrizet*; kvót* [with: menekült*, migráns*, bevándorl*, menedékjog*, áttelepít*]; áttelepítés*
- **Notes:** No terms proposed for this area.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** prostitúci*; prostituált*; emberkereskedelem*; emberkereskedő*; kéjelgés*; szexmunk*; "szexuális kizsákmányol*"; gyermekpornográf*; "gyermekek szexuális*"; "szexuális bántalmaz*"
- **Tier 2:** pornográf*; pedofil*; "szexuális visszaélés*"; "szexuális erőszak*"; "szexuális zaklatás*"; kényszermunk*; "Nemzeti Koordinátor az emberkereskedelem*"
- **Notes:** No terms proposed for this area.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** szervadományoz*; szervátültet*; szervdonáci*; szervdonor*; transzplantáci*; "feltételezett beleegyezés*"; agyhalál*; szervkereskedelem*; "szerv- és szövetátültet*"
- **Tier 2:** szövetadományoz*; donor*; "halott ember szerv*"
- **Notes:** No terms proposed for this area.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** nem; meleg; élet; család; gyermek; jog; egyház; védelem

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang hu`. A new term needs a measurement, written in the area's Notes.
