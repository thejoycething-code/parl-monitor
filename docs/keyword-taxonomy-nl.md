# Parliamentary Monitor: Dutch (Netherlands and Flanders) keyword taxonomy

**Version 0.2 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

## Purpose

One Dutch list for the Tweede Kamer and the Dutch texts of the Belgian Chamber. Country-only terms are tagged `[only: nl]` or `[only: be]`.

**This file is the master.** `config/taxonomy-nl.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang nl`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of Netherlands, Belgium (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
A term one country proposed as its own (a statute number, a national body, a national spelling) carries `[only: <code>]` and matches only for that country's collector; every other term is shared. Where countries proposed one term at different tiers, the shared copy takes the lower tier and the countries that asked for tier 1 get a tagged tier-1 copy, so no country is promoted past its own list. A term that one country guarded and another left bare is shared only in its guarded form; the bare copy is tagged for the countries that proposed it bare.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- Netherlands X4: list approved as drafted
- Netherlands X11: moved femicide*, Istanbul-verdrag and Verdrag van Istanbul from area 5 tier 1 to area 5 tier 2
- Netherlands X12: anticonceptie* already area 1 tier 2; no change
- Netherlands X13: removed antisemitisme* and Jodenhaat from area 8
- Netherlands Guards written from prose: bufferzone*, psychisch lijden, dementie, transitie, genderidentiteit, hormoonbehandeling*, pastora*, gebedsgenezing, vrouwenopvang, kleedkamer*, artikel 23, kerndoelen, sociale media, censuur, levensbeschouwing*, hoofddoek*
- Belgium X4: list approved as drafted
- Belgium BE3: stillborn-child terms in area 1 tier 2
- Belgium BE4: religious-symbol and laicity terms kept in area 8
- Belgium BE5: labour trafficking (mensenhandel) kept in area 12 tier 1
- Belgium X12: anticonceptie* in area 1 tier 2 (already there)
- Belgium X13: no antisemitism terms in the doc
- Belgium Area 11: no terms proposed in the doc; left empty
- Belgium Guards written from prose: belemmeringsdelict, bedenktijd, transitie, leeftijdsverificatie, neutraliteit; euthanasie veto

Noise round (v0.2, 10 October 2026, approved by Chris).

- `transitie` (area 3, tier 1) needed child company (kinderen, jongeren, minderjarigen, kind*), which a schooling debate always has. It now needs gender or medical company instead (`gender*`, `geslacht*`, `transgender*`, `hormo*`, `puberteit*`), one term in place of the two. Measured on the Tweede Kamer's verslagen of 28 September to 8 October (4,146 speeches from the raw archive): on our ground 66 to 65, the one lost the passend onderwijs debate of 30 September ("een transitie naar een nieuw systeem", noise). The Dutch and Belgian bill, vote and dossier stores are unchanged.

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** abortus*; zwangerschapsafbreking*; "afbreking van de zwangerschap"; "afbreking zwangerschap"; "Wet afbreking zwangerschap" [only: nl]; Wafz [only: nl]; abortuspil*; overtijdbehandeling* [only: nl]; abortuskliniek*; laatabortus*; "late zwangerschapsafbreking*" [only: nl]; bedenktijd [only: nl]; "ongeboren leven"; "ongeboren kind*"; levensbescherming; "Schreeuw om Leven" [only: nl]; bufferzone* [with: abortus*, kliniek*, zwangerschap*]; abortus; zwangerschapsafbreking; belemmeringsdelict [with: abortus*, zwangerschapsafbreking*] [only: be]
- **Tier 2:** ongeboren*; anticonceptie*; "prenatale screening"; NIPT [only: nl]; 20-wekenecho [only: nl]; pretecho*; "levensbeëindiging bij pasgeborenen" [only: nl]; Groningen-protocol [only: nl]; "seksuele en reproductieve gezondheid"; "reproductieve rechten"; "onbedoelde zwangerschap*"; "ongewenste zwangerschap*"; doodgeboorte*; miskraam*; vondelingenluik*; babyluik*; ongeboren; bedenktijd [with: abortus*, zwangerschapsafbreking*] [only: be]; gewetensbezwaar; doodgeboren; sterrenkind* [only: be]; "levenloos geboren" [only: be]
- **Notes:** Netherlands: Measured on titles of the current Kamer: 41 zaken; hits on point (Vliegenthart bill taking abortion out of the Criminal Code). Belgium: Measured on 1,776 dossier titles: 15 dossiers tier 1; the June 2026 rejection vote; bedenktijd unguarded caught an electricity-contracts bill.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** euthanasie*; "hulp bij zelfdoding"; "levensbeëindiging op verzoek"; "voltooid leven" [only: nl]; "Wet toetsing levensbeëindiging" [only: nl]; levenseindekliniek* [only: nl]; "Expertisecentrum Euthanasie" [only: nl]; "Toetsingscommissies Euthanasie" [only: nl]; laatstewilmiddel* [only: nl]; "Laatste Wil" [only: nl]; "schriftelijke wilsverklaring*"; euthanasieverklaring*; euthanasie [without: dier*, animal, animaux, honden, chiens, katten, chats]; wilsverklaring* [only: be]; levenseinde
- **Tier 2:** "voltooid leven"; levensbeëindiging*; "palliatieve zorg"; "palliatieve sedatie"; hospice*; suïcidepreventie; zelfdoding*; levenseinde*; "psychisch lijden" [with: euthanasie*, levenseinde*]; dementie [with: euthanasie*, levenseinde*]; palliatie*; "psychisch lijden" [only: be]
- **Notes:** Netherlands: Measured: 24 zaken; hospice* also catches hospice funding. Belgium: Measured: 6 dossiers, 2 tier 1 (56/183, 56/1338); euthanasie vetoed beside animal words.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** puberteitsremmer*; puberteitsremming*; genderdysforie*; geslachtsincongruentie*; genderzorg [only: nl]; transgenderzorg; transzorg; "geslachtsaanpassende behandeling*"; "geslachtsaanpassende operatie*"; "genderbevestigende zorg"; "genderbevestigende behandeling*"; "Dutch protocol" [only: nl]; "Nederlandse protocol" [only: nl]; detransitie* [only: nl]; genderteam* [only: nl]; transitie [with: gender*, geslacht*, transgender*, hormo*, puberteit*]; genderdysforie; "transgender minderjarige*"; transgenderjongere*
- **Tier 2:** genderzorg; detransitie*; genderidentiteit [with: kind*, jongeren, minderjarigen]; hormoonbehandeling* [with: kind*, jongeren, minderjarigen]; "transgender jongeren"; transgenderjongeren; "Kennis- en Zorgcentrum Genderdysforie" [only: nl]; transgender*; genderidentiteit [only: be]; genderkliniek* [only: be]
- **Notes:** Netherlands: Measured: 5 zaken; includes the Gezondheidsraad advice on transgender care for minors. Belgium: Measured: found 56/335, the resolution for a cautious approach and a KCE review.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** conversietherapie*; conversiehandeling* [only: nl]; conversiepraktijk*; homogenezing*; "Wet verbod op conversiehandelingen" [only: nl]; conversiebehandeling*
- **Tier 2:** pastora* [with: conversie*, verbod, gerichtheid]; gebedsgenezing [with: conversie*, verbod, gerichtheid]
- **Notes:** Netherlands: Measured: 1 zaak; the statute's own word is conversiehandeling*. Belgium: Belgium banned conversion practices in 2023; nothing matched in legislature 56, as expected after a ban.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** genderidentiteit*; geslachtsregistratie*; Transgenderwet* [only: nl]; "wijziging geslachtsregistratie"; geslachtsaanduiding*; "X in het paspoort"; "X in paspoort"; non-binair*; transgender*; transperso*; "biologisch geslacht"; genderexpressie*; geslachtskenmerken; geslachtsregistratie; "registratie van het geslacht" [only: be]; transgenderwet [only: be]; genderexpressie; X-registratie
- **Tier 2:** femicide*; "Istanbul-verdrag"; "Verdrag van Istanbul"; lhbti*; lhbtiq*; LHBTI*; LHBTIQ*; regenboogvlag*; Regenboogsteden [only: nl]; genderneutra*; vrouwenopvang [with: gender*, transgender*, geslacht*]; kleedkamer* [with: gender*, transgender*, geslacht*]; vrouwensport; genderquota; "seksuele gerichtheid"; "seksuele oriëntatie"; "Wet gelijke behandeling" [only: nl]; gendergelijkheid; seksisme
- **Notes:** Netherlands: Measured: 49 zaken; rainbow-flag terms filed here as drafted. Belgium: Sexism tier 2 is right: four 'sexism in public space' bills.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "seksuele voorlichting"; "seksuele vorming"; "relationele en seksuele vorming"; seksualiteitsonderwijs; "seksuele diversiteit"; "Week van de Lentekriebels" [only: nl]; Lentekriebels [only: nl]; "Paarse Vrijdag" [only: nl]; "vrijheid van onderwijs"; "bijzonder onderwijs" [only: nl]; huisonderwijs; thuisonderwijs; "ouderlijk gezag"; "rechten van ouders"; ouderrecht*; "artikel 23" [with: onderwijs*, Grondwet, school*] [only: nl]; "seksuele opvoeding"; lijfstraf*; "pedagogisch geweld"
- **Tier 2:** burgerschapsonderwijs [only: nl]; burgerschapsopdracht [only: nl]; kerndoelen [with: seksu*, burgerschap*, diversiteit]; leerplicht*; smartphoneverbod*; telefoonverbod*; mobieltjesverbod*; "sociale media" [with: kind*, jongeren, minderjarigen]; leeftijdsverificatie*; "leeftijdsgrens voor sociale media"; schermtijd; kinderrechten; onderwijsvrijheid [only: be]; jeugdbescherming
- **Notes:** Netherlands: Measured: 42 zaken; leerplicht* (27 hits) is mostly truancy enforcement. Belgium: EVRAS is French Community (see be-fr); education is mainly a community matter.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "vrijheid van meningsuiting"; meningsvrijheid; uitingsvrijheid; haatzaaien; groepsbelediging; "artikel 137c" [only: nl]; "artikel 137d" [only: nl]; "Digital Services Act"; DSA; chatcontrole; "trusted flagger*"; majesteitsschennis; censuur [with: internet, online, platform*, media]; haatspraak [only: be]; persvrijheid [only: be]; "aanzetten tot haat" [only: be]; negationisme [only: be]; godslastering; "digitale identiteit"; leeftijdsverificatie [with: pornogra*, "sociale media"]; "academische vrijheid"; "chat control"
- **Tier 2:** desinformatie*; "online haat"; haatspraak; "online intimidatie"; doxing; deepfake*; platformregulering; "Wet op de inlichtingen- en veiligheidsdiensten" [only: nl]; Wiv [only: nl]; gezichtsherkenning*; demonstratierecht; "Wet openbare manifestaties" [only: nl]; persvrijheid; "vrijheid van vereniging"; censuur [only: be]; desinformatie; antidiscriminatiewet* [only: be]; antiracismewet [only: be]; haatmisdrij*; pornogra*
- **Notes:** Netherlands: Measured: 41 zaken; Wet openbare manifestaties (16) is mostly policing of demonstrations. Belgium: Leeftijdsverificatie guarded by porn or social-media words.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** godsdienstvrijheid; "vrijheid van godsdienst"; geloofsvrijheid; religievrijheid; "religie- en levensbeschouwingsvrijheid"; "vrijheid van religie"; christenvervolging [only: nl]; "vervolging van christenen"; "christelijke minderhe*"; "religieuze minderhe*"; godslastering; kerkasiel; enkele-feitconstructie [only: nl]; "enkele feit" [only: nl]; "Speciaal gezant voor religie" [only: nl]; "ritueel slachten" [only: be]; "onverdoofd slachten" [only: be]; erediensten [only: be]; "bedienaren van de eredienst*" [only: be]; levensbeschouwelijke tekens [only: be]; "tekens van een geloofs- of levensovertuiging" [only: be]; hoofddoek* [only: be]; biechtgeheim [only: be]
- **Tier 2:** christenvervolging; levensbeschouwing* [with: vrijheid, onderwijs, school]; "ritueel slachten"; "onverdoofd slachten"; besnijdenis*; "gezichtsbedekkende kleding" [only: nl]; boerkaverbod; hoofddoek* [with: school, kinderen, rechter, politie]; moslimhaat; moslimdiscriminatie; kerkgebouw*; "religieuze organisatie*"; geloofsgemeenschap*; kerkgenootschap*; levensbeschouwing* [only: be]; neutraliteit [with: religie*, Staat]; eredienst; kerkfabriek* [only: be]; imam; imams; moskee*
- **Notes:** Netherlands: Measured: 61 zaken before the antisemitism terms were removed (X13). Belgium: Religious-symbol bans and laicity in scope (BE4); neutraliteit guarded because 'neutralité fiscale' matched.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** kindhuwelijk*; huwelijksdwang; "gedwongen huwelijk*"; polygamie; meerouderschap [only: nl]; meeroudergezag [only: nl]; deelgezag [only: nl]; "Staatscommissie Herijking ouderschap" [only: nl]; gezinsbeleid [only: nl]; familiebeleid; huwelijksgevangenschap; "huwelijk tussen personen van hetzelfde geslacht"; meeouderschap; afstamming; meemoeder* [only: be]
- **Tier 2:** gezinsbeleid; huwelijk*; kinderbijslag; "kindgebonden budget" [only: nl]; geboorteverlof; ouderschapsverlof; adoptie*; "interlandelijke adoptie"; eenoudergezin*; echtscheiding*; "geregistreerd partnerschap"; "gezag over kinderen"; "kinderrechten in de Grondwet"; huwelijk; echtscheiding; adoptie; "wettelijke samenwoning" [only: be]; geboortecijfer
- **Notes:** Netherlands: Measured: 31 zaken; huwelijk* catches huwelijksvermogensrecht (marital property tax). Belgium: Stillborn and family terms as drafted.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** draagmoederschap; draagmoeder*; draagouderschap; eiceldonatie; embryodonatie; Embryowet [only: nl]; embryo-onderzoek; "embryo's kweken"; kweekverbod [only: nl]; kiembaanmodificatie; kiembaan*; embryoselectie; "pre-implantatie genetische test*"; "pre-implantatie genetische diagnostiek"; PGT; kloneren; "synthetische embryo*"; "embryo-achtige structuren"; spermadonatie; zaaddonor*; spermadonor*; donorkind*; afstammingsrecht; "Wet donorgegevens" [only: nl]; embryo* [only: be]; "medisch begeleide voortplanting" [only: be]; "zwangerschap voor anderen" [only: be]; "anonimiteit van de donor"
- **Tier 2:** IVF; ivf-behandeling*; vruchtbaarheidsbehandeling*; "kunstmatige inseminatie"; "eicellen invriezen"; embryo*; stamcel*; "medisch begeleide voortplanting"; gameten; eicel*; kinderwens
- **Notes:** Netherlands: Measured: 41 zaken; Embryowet amendments are on point. Belgium: 'zwangerschap voor anderen' is the Chamber's own title for surrogacy bill 56/134; draagmoederschap alone missed it.

### 11. Migration {#11_migration}

- **Tier 1:** asielzoeker*; asielaanvraag*; gezinshereniging; nareis* [only: nl]; Asielnoodmaatregelenwet [only: nl]; Spreidingswet [only: nl]; Vreemdelingenwet* [only: nl]; tweestatusstelsel [only: nl]; statushouder* [only: nl]; "Ter Apel" [only: nl]; terugkeerbeleid; "strafbaarstelling van illegaliteit" [only: nl]; "veilig land van herkomst"
- **Tier 2:** asiel*; migratie*; vreemdeling*; naturalisatie*; COA [only: nl]; inburgering*; verblijfsvergunning*; uitzetting*; mensensmokkel*
- **Notes:** Netherlands: Collated and hidden; 526 zaken, never campaigned. Belgium: Collated, never campaigned; no terms proposed.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** prostitutie*; sekswerk*; "Wet regulering sekswerk" [only: nl]; mensenhandel*; "seksuele uitbuiting"; pooierboy*; loverboy*; "Noords model"; "Scandinavisch model"; raamprostitutie [only: nl]; "gedwongen prostitutie"; "strafbaarstelling van klanten"; pooier*; prostitutie; mensenhandel
- **Tier 2:** bordeel*; seksinrichting*; escort*; kinderporno*; "seksueel kindermisbruik"; "online seksueel misbruik"; "Wet seksuele misdrijven" [only: nl]; "seksuele intimidatie"; "afbeeldingen van seksueel kindermisbruik"; massagesalon*
- **Notes:** Netherlands: Measured: 72 zaken; mensenhandel* (50) also cross-tags surrogacy amendments, correctly. Belgium: Labour trafficking in scope (BE5): mensenhandel is mostly labour trafficking in Belgian usage.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** orgaandonatie*; orgaandonor*; Donorwet [only: nl]; donorregistratie; Donorregister [only: nl]; "Wet op de orgaandonatie" [only: nl]; hersendood; orgaanhandel; orgaantransplantatie*; orgaanuitname*; "actief donorregistratiesysteem" [only: nl]; transplantatie* [only: be]; orgaandonatie
- **Tier 2:** transplantatie*; weefseldonatie; "donatie na euthanasie" [only: nl]; lichaamsmateriaal [only: be]
- **Notes:** Netherlands: Measured: 3 zaken; Donorwet and similar found nothing in titles, as expected. Belgium: As drafted.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** huwelijk; leven; recht; kind; gezin; geslacht; onderwijs; vrijheid; geweld; migratie; prostitutie

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang nl`. A new term needs a measurement, written in the area's Notes.
