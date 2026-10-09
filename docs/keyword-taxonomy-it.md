# Parliamentary Monitor: Italian keyword taxonomy

**Version 0.1 | 10 October 2026 | Owner: Christopher | Status: APPROVED AS DRAFTED (X4), NOT YET READ BY A NATIVE READER**

## Purpose

The Italian list for the Italian Parliament, also run on the Swiss Federal Assembly's Italian texts (CH6). Country-only terms are tagged `[only: it]` or `[only: ch]`.

**This file is the master.** `config/taxonomy-it.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang it`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Merged on 10 October 2026 from the proposed lists in the scope documents of Italy, Switzerland (`docs/<country>-scope.md`), which Chris approved as drafted (X4) with the scope calls in `docs/country-decisions-2026-10-10.md`.
A term one country proposed as its own (a statute number, a national body, a national spelling) carries `[only: <code>]` and matches only for that country's collector; every other term is shared. Where countries proposed one term at different tiers, the shared copy takes the lower tier and the countries that asked for tier 1 get a tagged tier-1 copy, so no country is promoted past its own list.
Accents fold for matching (X3), so accented and unaccented spellings are one term.

Scope calls applied while merging:

- Italy X13: removed antisemitismo from area 8 tier 2
- Italy X11: Convenzione di Istanbul moved from area 5 tier 1 to tier 2; femminicidio, femminicidi, violenza di genere already tier 2
- Italy X12: no contraception term in the Italian list; nothing to move
- Italy IT1: list approved as drafted
- Italy Slash shorthand expanded into separate terms (e.g. di/della gravidanza, trapianto/i di organi)
- Italy Parenthetical 'with' and 'without' lists converted to [with: ...] and [without: ...] guards
- Switzerland CH6: Italian list to be run on Swiss Italian texts; no Swiss additions proposed

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** aborto; aborti; abortiv*; "interruzione volontaria di gravidanza"; "interruzione volontaria della gravidanza"; "interruzioni volontarie di gravidanza"; IVG; "legge 194" [only: it]; "legge n. 194" [only: it]; "legge 22 maggio 1978, n. 194" [only: it]; "194 del 1978" [only: it]; 194/1978 [only: it]; RU486; "RU 486"; mifepristone; "tutela della vita nascente"; "vita nascente"; "diritti del concepito"; "capacità giuridica del concepito"; "riconoscimento del concepito"; nascituro; nascituri; "Movimento per la vita" [only: it]; "centri di aiuto alla vita" [only: it]; "battito cardiaco fetale"; "vita umana"; "sepoltura dei feti"
- **Tier 2:** "obiezione di coscienza" [with: gravidanza, aborto, 194, ginecolog*, interruzione]; "consultori familiari"; "consultorio familiare"; "salute riproduttiva"; "diritti riproduttivi"; "salute sessuale e riproduttiva"; sepoltura [with: feti, "prodotti abortivi", "prodotti del concepimento"]; "diagnosi prenatale"; "aborto spontaneo"; "parto in anonimato"; "culle per la vita"
- **Notes:** Italy: Measured on the Senate and Camera records; Law 194/1978 variants are Italy-only.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** "suicidio assistito"; "suicidio medicalmente assistito"; "morte volontaria medicalmente assistita"; "morte medicalmente assistita"; "morte volontaria"; "aiuto al suicidio"; eutanasia [without: animali, animale, "animali di affezione", equini, cani, gatti]; "fine vita"; "fine della vita"; "trattamenti di fine vita"; "disposizioni anticipate di trattamento"; "testamento biologico"; "legge 219/2017" [only: it]; "legge 22 dicembre 2017, n. 219" [only: it]; "articolo 580 del codice penale" [only: it]; "art. 580 c.p." [only: it]; "sedazione palliativa profonda"; suicidio [with: assistito, medicalmente, 580, aiuto, eutanasi*]
- **Tier 2:** "cure palliative"; "terapia del dolore"; hospice; "accanimento terapeutico"; "consenso informato" [without: scolastic*, scuola, scuole, studenti, alunni]; "dignità del morente"; "prevenzione del suicidio"
- **Notes:** Italy: Eutanasia vetoed for animal euthanasia, which TESEO files under the same word; suicidio needs an assisted-suicide companion word.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** triptorelina; "bloccanti della pubertà"; "bloccanti puberali"; "blocco puberale"; "disforia di genere"; "incongruenza di genere"; "transizione di genere" [with: minori, minorenni, adolescenti, bambini, "età evolutiva"]; "percorsi di affermazione di genere" [with: minori, minorenni, adolescenti]; detransizione
- **Tier 2:** "identità di genere" [with: minori, minorenni, adolescenti, bambini, "età evolutiva", farmac*]; "terapia ormonale" [with: minori, adolescenti, genere]; "trattamenti ormonali" [with: minori, adolescenti, genere]
- **Notes:** Italy: Tier 1 triptorelina and puberty-blocker terms; transition and identity terms guarded to minors.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "terapie di conversione"; "terapia di conversione"; "terapie riparative"; "terapia riparativa"; "pratiche di conversione"; "pratiche volte a modificare l'orientamento sessuale"; "terapie volte alla conversione"; "conversione dell'orientamento sessuale"
- **Tier 2:** "orientamento sessuale" [with: conversione, riparativ*, modificare, reprimere]
- **Notes:** Italy: Draft list, measured on TESEO titles.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "identità di genere"; omotransfobia; omobitransfobia; omolesbobitransfobia; "rettificazione di attribuzione di sesso" [only: it]; "rettificazione dell'attribuzione di sesso" [only: it]; "legge 164/1982" [only: it]; "legge 14 aprile 1982, n. 164" [only: it]; "carriera alias" [only: it]; transgender; transessual*; "non binari*"; "ddl Zan" [only: it]; "atlete transgender"; "sesso biologico"; "sesso delle persone e sessualità" [only: it]
- **Tier 2:** "Convenzione di Istanbul"; femminicidio; femminicidi; "violenza di genere"; "linguaggio di genere"; "linguaggio inclusivo"; schwa; LGBT*; LGBTQ*; "orientamento sessuale"; "parità di genere"; "quote rosa"; "sport femminile"; Pride; "relazioni di genere"; "parità tra sessi"
- **Notes:** Italy: Femicide and gender-violence terms sit at tier 2 (largest single group of hits, kept in by X11).

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "educazione sessuale"; "educazione sessuo-affettiva"; "educazione all'affettività"; "educazione affettiva"; "educazione sentimentale"; "educazione alle relazioni"; "ideologia gender"; "ideologia di genere"; "teorie del gender"; "teoria del gender"; "teorie gender"; "gender nelle scuole"; "istruzione parentale"; "scuola parentale"; "scuole parentali"; homeschooling; "libertà di scelta educativa"; "libertà educativa"; "consenso informato preventivo"; "primato educativo"
- **Tier 2:** "consenso informato" [with: scuola, scuole, studenti, alunni, genitori, famiglie]; "scuole paritarie" [only: it]; "parità scolastica" [only: it]; "buono scuola"; "patto educativo di corresponsabilità" [only: it]; smartphone [with: scuola, scuole, minori, alunni, divieto]; cellulari [with: scuola, scuole, classe, studenti, alunni] [without: colture]; "social network" [with: minori, minorenni, anni, età, scuola]; "verifica dell'età" [with: minori, pornografi*, online, piattaform*]; "age verification"; "parental control"; "potestà genitoriale"; "responsabilità genitoriale"; "diritto dei genitori"; "scuole private"
- **Notes:** Italy: Consenso informato is area 6 tier 2 only with school or family company; elsewhere it belongs to area 2.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "libertà di espressione"; "libertà di manifestazione del pensiero"; "libertà di pensiero"; "libertà di stampa"; "reati di opinione"; "reato di opinione"; "Digital Services Act"; "regolamento sui servizi digitali"; "chat control"; "legge Mancino" [only: it]; "crittografia end-to-end"; "trattato pandemico"; "accordo pandemico"; "Regolamento sanitario internazionale"
- **Tier 2:** censura [with: web, internet, online, piattaform*, social, opinion*, espressione]; "hate speech"; "discorso d'odio"; "discorsi d'odio"; "incitamento all'odio"; disinformazione; "fake news"; fact-checking; "riconoscimento facciale"; "data retention"; "conservazione dei dati di traffico"; "identità digitale"; "euro digitale"; OMS [with: pandemi*, "sanitario internazionale", sovranità]; deepfake
- **Notes:** Italy: Draft list; censura guarded to online and opinion company.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "libertà religiosa"; "libertà di religione"; "libertà di culto"; "cristiani perseguitati"; "persecuzione dei cristiani"; "persecuzione religiosa"; "persecuzioni religiose"; "minoranze religiose"; "minoranze cristiane"; crocifisso; "insegnamento della religione cattolica" [only: it]; "ora di religione" [only: it]; "vilipendio della religione"; "offese a una confessione religiosa" [only: it]; "intese con le confessioni" [only: it]
- **Tier 2:** "otto per mille" [only: it]; "8 per mille" [only: it]; "luoghi di culto"; "confessioni religiose"; "Santa Sede"; Concordato [with: "Santa Sede", Chiesa, "Stato e Chiesa", Vaticano] [only: it]; "Patti lateranensi" [only: it]; moschee; moschea; islamofobia; cristianofobia; "obiezione di coscienza"; "enti ecclesiastici"; "simboli religiosi"; "velo integrale"; burqa; "macellazione rituale"; "rapporti tra Stato e Chiesa"; "minoranze etniche e religiose"; "insegnamento della religione nelle scuole"; "ecclesiastici e ministri del culto"
- **Notes:** Italy: Antisemitismo removed by X13.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "unioni civili"; "unione civile"; "legge Cirinnà" [only: it]; "matrimonio egualitario"; "matrimonio tra persone dello stesso sesso"; "matrimonio omosessuale"; "stepchild adoption"; "adozione del figlio del partner"; "famiglia naturale"; "famiglia fondata sul matrimonio"; natalità; denatalità; "inverno demografico"; "quoziente familiare"; "assegno unico universale" [only: it]; "matrimonio forzato"; "matrimoni forzati"; "matrimoni precoci"; poligamia
- **Tier 2:** "adozioni internazionali"; "adozione di minori"; "adozione dei minori"; affido [with: minori, familiare, figli, minorenni]; "affidamento di minori"; "affidamento condiviso"; "alienazione parentale"; "congedo parentale"; "congedi parentali"; "bonus bebè" [only: it]; genitorialità; "potestà dei genitori"; "diritto di famiglia"; "cessazione del matrimonio"; "matrimonio religioso"; "politiche familiari"; "politiche per la famiglia"; "genitore 1"; divorzio; "separazione personale dei coniugi"; "famiglie numerose"; "conciliazione vita-lavoro"
- **Notes:** Italy: Draft list; natalità and family-policy terms are tier 1/2 as drafted.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "maternità surrogata"; "surrogazione di maternità"; "gestazione per altri"; GPA; "utero in affitto"; "reato universale" [only: it]; "procreazione medicalmente assistita"; PMA; "legge n. 40" [only: it]; "legge 19 febbraio 2004, n. 40" [only: it]; "fecondazione eterologa"; "fecondazione assistita"; "fecondazione artificiale"; embrioni; embrione; crioconservazione; "editing genetico"; clonazione
- **Tier 2:** "legge 40" [only: it]; trascrizione [with: nascita, figli, "coppie omogenitoriali", "due madri", "due padri", estero]; "coppie omogenitoriali"; "riconoscimento dei figli"; "diagnosi preimpianto"; gameti; "donazione di ovociti"; "cellule staminali embrionali"
- **Notes:** Italy: Reato universale is the 2024 law making surrogacy abroad a universal crime.

### 11. Migration {#11_migration}

- **Tier 1:** immigrazione; "immigrazione clandestina"; "protezione internazionale"; "richiedenti asilo"; "centri di permanenza per il rimpatrio" [only: it]; "Protocollo Italia-Albania" [only: it]; "flussi migratori"; cittadinanza
- **Tier 2:** CPR [only: it]; rimpatri; sbarchi; "ius scholae"; "ius soli"; "permesso di soggiorno"; ONG
- **Notes:** Italy: Collated, never campaigned.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** prostituzione; "legge Merlin" [only: it]; "sfruttamento sessuale"; "tratta di esseri umani"; "tratta degli esseri umani"; pornografia [without: "tutela degli animali", "reati contro gli animali"]; pornografic*; pedopornografi*; "materiale pedopornografico"; "abusi sessuali su minori"; "adescamento di minori"; "revenge porn"; "diffusione illecita di immagini o video sessualmente espliciti" [only: it]; sextortion; "turismo sessuale"; "case chiuse" [only: it]; "modello nordico"
- **Tier 2:** "lavoro sessuale"; "sex worker"; "violenza sessuale"; "riduzione in schiavitù"; deepfake [with: sessual*, nud*, pornografi*]
- **Notes:** Italy: Caporalato deliberately not a term: farm-labour exploitation put two labour decrees on our ground.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** "donazione di organi"; "donazione degli organi"; "trapianto di organi"; "trapianti di organi"; "prelievo di organi"; silenzio-assenso [with: organi, donazione, trapiant*]; "silenzio assenso" [with: organi, donazione, trapiant*]; "donazione del corpo"; "commercio di organi"; "traffico di organi"
- **Tier 2:** trapianti; trapianto; "Centro nazionale trapianti" [only: it]; "morte cerebrale"; "accertamento della morte"; donatori [with: organi, tessuti, trapiant*]; "donatori di organi"
- **Notes:** Italy: Silenzio-assenso and donatori guarded: alone they are administrative law and blood donors.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** genere; famiglia; scuola; vita; salute; minori; religione

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang it`. A new term needs a measurement, written in the area's Notes.
