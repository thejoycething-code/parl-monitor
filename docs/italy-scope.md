# Italy: scoping the Parliament monitor

Probed live on 9 October 2026, from the laptop, with the repo's honest UA
and throttle (`src/http.py`); raw responses are in `data/raw/2026-10-09/`
(feeds `it_probe_*` and `it-rollcalls`). Every number below was measured,
not estimated. National Parliament first: the Senato della Repubblica and
the Camera dei Deputati, 19th legislature (from 13 October 2022; it must end
by October 2027). The twenty regional councils are listed at the end, not
probed.

## Decisions (Christopher, 9 October 2026, applied here)

- **Own edition**, to Christopher alone (Slack DM), as the US.
- **Shared taxonomy concept, native terms.** No existing taxonomy file is
  touched. The Italian term list is PROPOSED below; `config/taxonomy-it.yaml`
  is generated only after Christopher approves it. Switzerland is being
  scoped in parallel and shares the language: the list marks which terms are
  Italy-only.
- **National Parliament first**, regions later.
- **Mac Mini first, GitHub Actions as backup.** No new paid services. Nothing
  is ever posted publicly.

## Phase 1: built, 9 October 2026

`tools/it_rollcalls.py` into `it_members`, `it_bills`, `it_divisions` and
`it_votes` (schema in `src/it_store.py`, declared in `db.TABLES`). Both
sources are open and keyless. A full live run into a scratch database, not
the store:

| | Read | On our ground: English taxonomy + watchlist (as shipped) | On our ground: proposed Italian terms + watchlist |
|---|---|---|---|
| Bill readings, both chambers | 5,251 | 23 | 299 |
| Senate votes | 8,338 | 40 | 80 (on 8 bills) |
| Camera votes | 19,812 | 88 | 281 (on 12 bills) |
| Senators (with group spells) | 212 | | |

Bills and votes took **86 seconds**. Positions are a second pass, only for
the votes on our ground: a test pass fetched **377 votes' positions in 17
minutes** (127,175 positions, one gap: an Openpolis TLS timeout), about 2.7
seconds a vote. The weekly job's 45-minute budget stops the first run
cleanly and the next one carries on.

- **Positions only for votes on our ground.** The 19th legislature holds
  about 1.57 million Senate positions (counted by SPARQL) and 9.57 million
  Camera positions (Openpolis's own count). Storing them all would add tens
  of MB to an 895 MB store for votes nobody reads. A division on our ground
  with `positions_fetched = 0` is fetched on the next run, so when the
  Italian terms land and `--reclassify` brings older votes onto our ground,
  their positions follow by themselves.
- **Group per vote.** Italian members change group often; `it_votes.grp` is
  the group at the vote (Senate: from dated group spells; Camera: as
  Openpolis gives it on the vote).
- **Keyed on the chambers' own numbers.** Bills by reading (`19/C.887`,
  `19/S.824`; one bill, two readings, linked by the Senate's `id_ddl`),
  votes by the chambers' own IDs (`senato-19-232-24`,
  `camera-vs19_147_041`). Never titles: a dozen bills are titled "Modifica
  all'articolo 12 della legge 19 febbraio 2004, n. 40".
- **Scheduled Mini-first** (see "The weekly job"). Not yet running: GitHub
  schedules only from main, and the Mini records its slot only for main.

## The finding that shapes everything

**The English taxonomy is blind to Italian, exactly as it was to German.**
`config/taxonomy.yaml` v1.17, unchanged, over the whole 19th legislature:

| Text | Items | English matches |
|---|---|---|
| Bill titles, both chambers | 8,411 (3,160 Camera + 5,251 Senate records) | **0** |
| Bill titles + TESEO subject terms | 5,251 readings | 6, every one a false cognate: "Islamis*" matching the TESEO term ISLAMISMO, which means Islam |
| Senate votes (with their bill) | 8,338 | **0** |
| Camera votes (with their bill) | 19,812 | **0** |

So nothing reaches our ground today except through
`config/watchlist-it.yaml`, which carries 17 flagship bill readings by key
until the Italian terms are approved (it is what the 23 bills and 128 votes
in the "as shipped" column are).

**The proposed Italian terms** (below), run over the same data:

- **Bills: 299 of 5,251 readings** on titles + TESEO general terms. By
  area: abortion 18, assisted dying 21, gender medicine 1, conversion
  practices 1, sex-based rights 92, parental rights 27, free speech 10,
  religion 35, marriage and family 66, surrogacy and embryology 30,
  prostitution and trafficking 23, organ donation 5. The terms alone catch
  every one of the 17 watchlist bills.
- **Votes: 281 Camera votes on 12 bills and 80 Senate votes on 8 bills.**
  The voted bills on our ground are the surrogacy universal-crime law
  (C.887 voted 26 July 2023; S.824 with S.163, S.245 and S.475, voted
  16 October 2024), parents' consent to sex education in schools (C.2423,
  S.1735), violence against women and the femicide offence (C.1294,
  C.2528, S.92, S.1433), the femicide inquiry (C.640, S.93), minors in
  care (C.1866), three Church agreements (C.2307, C.2759, C.2775) and the
  Romanian Orthodox intesa (C.2396), the sexual-violence offence
  (article 609-bis, C.1693), the antisemitism bills (S.1004 and six examined with it), one
  assisted-dying vote (S.104) and a maternity and paternity bill (C.2228).
- **Precision**, a random sample of 40 bill hits read by hand: about 30 are
  plainly ours. The misses come from omnibus decrees and loose words, and
  four were fixed in the draft before these counts: "edifici di culto" (a
  reconstruction law), "scuole autorizzate" (a school decree), "cellulari"
  (it means cell cultures too: it put the lab-grown meat ban, 111 votes,
  on our ground) and "caporalato" (farm-labour exploitation, 152 votes on
  two decrees). Triage sees every tier-2 hit, as everywhere else.
- **One honest miss found and fixed in the draft**: "teorie del gender"
  (C.1885) and "aiuto medico alla morte volontaria" (S.1597) matched nothing
  in the first cut.

### Why TESEO matters, and why only half of it

The Senate's library indexes every bill of BOTH chambers with TESEO, a
controlled thesaurus, at two levels: the bill as a whole ("Generale", 15,574
terms in the 19th) and article by article ("Articoli", 61,104). The general
terms add real recall: ABORTO, EUTANASIA, FECONDAZIONE ARTIFICIALE, SESSO
DELLE PERSONE E SESSUALITA', EDUCAZIONE SESSUALE, LIBERTA' RELIGIOSA,
PORNOGRAFIA, TRAPIANTI E PRELIEVI DI ORGANI. **The article terms are the
omnibus trap**: with them, a single budget law (C.1627) put 243 Camera votes
on our ground, and decree after decree followed on "confessioni religiose"
or "Santa Sede" in one article. Phase 1 reads the general level only. The
same lesson as the US NDAA: the vote that matters is the amendment, not the
bill.

## What Italy publishes

### Senato: dati.senato.it/sparql. Works today, open, no key

- **Virtuoso SPARQL endpoint**, JSON results, answers in 1 to 4 seconds.
  No rate-limit headers seen; we throttle to one request per 0.2 s as
  everywhere. The data is current: the newest sitting is 8 October 2026,
  the newest vote 7 October.
- **Bills (osr:Ddl): every reading of the legislature in both chambers**,
  5,251 records (3,159 Camera "C." readings, 2,092 Senate "S." readings),
  with title, short title, nature, presenters, status and date, law number,
  and the bill's ID across readings (`idDdl`: C.887 and S.824 are 52307).
  This is the bill layer for the Camera too.
- **Votes (osr:Votazione): 8,338** in the 19th, each with result, totals,
  sitting and date, the bill it was on (`osr:oggetto` to `osr:relativoA`,
  7,753 votes; 504 have no object: procedure), and **every senator's
  position** as separate predicates (favorevole, contrario, astenuto,
  presenteNonVotante, richiedenteNonVotante, inCongedoMissione). Absent
  senators are on no list. 5,522 of the votes are amendments ("Em. 1.1").
- **Senators**: 212 in the 19th, with dated group spells and the group's
  short name.
- **Questions (osr:SindacatoIspettivo)**: 6,840 in the 19th, the newest
  8 October 2026; each record has type, number, date, presenters and a
  link to the text on senato.it, no text itself. Not built.
- **Speeches (osr:Intervento)**: 304,487 across all legislatures, linked
  from each senator. Not built.
- **Quirks**: a result is capped at **10,000 rows**, and an ORDER BY with an
  OFFSET past that cap returns **HTTP 500**, so the collector cuts every
  large query into ranges of a numeric field (bill ID, sitting number) and
  treats a full answer as a gap. Some titles carry raw control characters
  that strict JSON refuses. The same resource is often typed twice, which
  doubles any non-DISTINCT join. TESEO writes accents as apostrophes
  (LIBERTA'), which the collector folds back (libertà) before matching.
- **www.senato.it** itself answered **HTTP 202 with an empty body**: a bot
  challenge. Not used, and not needed.

### Camera: dati.camera.it/sparql. Official, but unreliable today

- **HTTP 502 from 03:54 to at least 05:00** London time, on every query
  including the trivial one, with our UA, with curl's default and by POST.
  The linked-data pages (LodView) returned 500 in the same window. It was
  **back at 05:59**.
- When up, it has **19,673 votes** in the 19th (DISTINCT; 40,091 without,
  because every resource is typed twice), newest **6 October 2026**, two
  days behind Openpolis. Each vote has totals, final or not, secret or
  not, a link to the act voted (`rif_aic`, so an order of the day points at
  its bill), and per-member votes as `ocd:voto` records with the deputy's
  persistent Camera ID (`d302422_19`), group and position.
- **The download portal** (`dati.camera.it/it/download`) sits behind a
  **reCAPTCHA** ("One More Step"). We do not pass bot checks.
  `documenti.camera.it` answered 403.

### Openpolis: the Camera's votes. Works today, open, no key

- `service.opdm.openpolis.io/api-openparlamento/v1/19/`, the API behind
  parlamento19.openpolis.it (Fondazione Openpolis, a civic-tech
  foundation). Found in the site's own JavaScript; not advertised as a
  public API, no key, no rate-limit headers.
- `votings/?branch=C`: **19,812 Camera votes**, newest 8 October 2026,
  500 a page in 0.7 s. Identifiers are the Camera's own (`vs19_723_001`),
  so a later switch to dati.camera.it re-keys nothing.
- `votings/<id>/`: one vote with **every deputy's position** (AYE, NO,
  ABST, ABSE, MIS, PRES, SEC), group per vote, totals; 2 to 4 s a call.
- Also bills (5,252, titles only, 500 a page in 17 s), memberships (627),
  persons (682), government decrees (146), key-vote events (888).
- **Quirks**: a vote is listed the next morning with its totals but every
  member at "SEC" (secret) until the Camera's record arrives (vs19_723_001,
  a public final vote): the collector holds those back and retries.
  Member slugs carry the birth date and read "...-none" when it is unknown,
  so members are keyed on the numeric membership ID. A bill's
  `date_presenting` differs between the list and the detail (C.2628).
  Openpolis's Senate votes (8,034) are fewer than the Senate's own 8,338;
  the Senate is read from its own endpoint.
- **Since 2025 the Camera's amendment titles name no bill** ("EM 19.7 -
  Votazione"). The collector takes the bill from the nearest titled vote
  of the same sitting (forward for amendments and articles, backward for a
  final vote) and flags it `bill_inferred`: 12,670 Camera votes name their
  bill, 3,963 are inferred, 3,179 (motions, resolutions) have none.

### Not probed or not available

- **Agenda**: neither SPARQL endpoint carries the forward agenda.
  Openpolis has `events` (key votes, after the fact). The chambers'
  weekly calendars are HTML on camera.it and senato.it (senato.it refuses
  us). Phase 2.
- **Petitions**: Parliament receives petitions (Senate "petizioni"), and
  citizens' initiative bills are in the bill data (S.1597 is one);
  no e-petition system to probe.
- **Committees**: Senate committee sittings are in SPARQL (74,944
  SedutaCommissione). Not built.

## Proposed Italian terms (awaiting Christopher)

A first draft by Claude, measured above, not read by an Italian campaigner.
Convention as in the other files: tier 1 auto-includes, tier 2 goes to
triage; `*` is a stem; all-caps terms match case-sensitively; "with" needs
company in the same text, "without" is a veto. **[IT]** marks an
Italy-only term (a statute, institution or Italian label); unmarked terms
are plain Italian and should merge with a Swiss Italian list. Area 11 is
collated, never campaigned.

Italian matching traps: elisions ("dell'aborto", "l'eutanasia") are
handled by the filter's word boundaries; accented endings must be spelled
with the accent (identità, libertà); bare numbers ("194", "40") are never
terms, only "legge 194" and the full citation; the verb "si tratta" means
"tratta" alone can never be a trafficking term; "adozione" alone means
adoption of a measure; "concordato preventivo" is insolvency law, so
"Concordato" needs church company.

**1. Abortion.** Tier 1: aborto, aborti, abortiv\*, interruzione volontaria
di/della gravidanza, interruzioni volontarie di gravidanza, IVG, legge 194
[IT], legge n. 194 [IT], legge 22 maggio 1978, n. 194 [IT], 194 del 1978
[IT], 194/1978 [IT], RU486, RU 486, mifepristone, tutela della vita
nascente, vita nascente, diritti del concepito, capacità giuridica del
concepito, riconoscimento del concepito, nascituro, nascituri, Movimento
per la vita [IT], centri di aiuto alla vita [IT], battito cardiaco fetale,
vita umana, sepoltura dei feti. Tier 2: obiezione di coscienza (with
gravidanza, aborto, 194, ginecolog\*, interruzione), consultori familiari,
consultorio familiare, salute riproduttiva, diritti riproduttivi, salute
sessuale e riproduttiva, sepoltura (with feti, prodotti abortivi, prodotti
del concepimento), diagnosi prenatale, aborto spontaneo, parto in
anonimato, culle per la vita.

**2. Assisted dying.** Tier 1: suicidio assistito, suicidio medicalmente
assistito, morte volontaria medicalmente assistita, morte medicalmente
assistita, morte volontaria, aiuto al suicidio, eutanasia (without
animali, animale, animali di affezione, equini, cani, gatti: TESEO files
animal euthanasia under the same word), fine vita, fine della vita,
trattamenti di fine vita, disposizioni anticipate di trattamento,
testamento biologico, legge 219/2017 [IT], legge 22 dicembre 2017, n. 219
[IT], articolo 580 del codice penale [IT], art. 580 c.p. [IT], sedazione
palliativa profonda, suicidio (with assistito, medicalmente, 580, aiuto,
eutanasi\*). Tier 2: cure palliative, terapia del dolore, hospice,
accanimento terapeutico, consenso informato (without scolastic\*, scuola,
scuole, studenti, alunni), dignità del morente, prevenzione del suicidio.

**3. Gender medicine and children.** Tier 1: triptorelina, bloccanti della
pubertà, bloccanti puberali, blocco puberale, disforia di genere,
incongruenza di genere, transizione di genere (with minori, minorenni,
adolescenti, bambini, età evolutiva), percorsi di affermazione di genere
(with minori, minorenni, adolescenti), detransizione. Tier 2: identità di
genere (with minori, minorenni, adolescenti, bambini, età evolutiva,
farmac\*), terapia ormonale and trattamenti ormonali (with minori,
adolescenti, genere).

**4. Conversion practices.** Tier 1: terapie/terapia di conversione,
terapie/terapia riparativa/e, pratiche di conversione, pratiche volte a
modificare l'orientamento sessuale, terapie volte alla conversione,
conversione dell'orientamento sessuale. Tier 2: orientamento sessuale
(with conversione, riparativ\*, modificare, reprimere).

**5. Sex-based rights.** Tier 1: identità di genere, omotransfobia,
omobitransfobia, omolesbobitransfobia, rettificazione di/dell'attribuzione
di sesso [IT], legge 164/1982 [IT], legge 14 aprile 1982, n. 164 [IT],
carriera alias [IT], transgender, transessual\*, non binari\*, Convenzione
di Istanbul, ddl Zan [IT], atlete transgender, sesso biologico, sesso delle
persone e sessualità [IT, TESEO]. Tier 2: femminicidio, femminicidi,
violenza di genere, linguaggio di genere, linguaggio inclusivo, schwa,
LGBT\*, LGBTQ\*, orientamento sessuale, parità di genere, quote rosa, sport
femminile, Pride, relazioni di genere [TESEO], parità tra sessi [TESEO].

**6. Parental rights and education.** Tier 1: educazione sessuale,
educazione sessuo-affettiva, educazione all'affettività, educazione
affettiva, educazione sentimentale, educazione alle relazioni, ideologia
gender, ideologia di genere, teorie del gender, teoria del gender, teorie
gender, gender nelle scuole, istruzione parentale, scuola parentale,
scuole parentali, homeschooling, libertà di scelta educativa, libertà
educativa, consenso informato preventivo, primato educativo. Tier 2:
consenso informato (with scuola, scuole, studenti, alunni, genitori,
famiglie), scuole paritarie [IT], parità scolastica [IT], buono scuola,
patto educativo di corresponsabilità [IT], smartphone (with scuola, scuole,
minori, alunni, divieto), cellulari (with scuola, scuole, classe, studenti,
alunni; without colture),
social network (with minori, minorenni, anni, età, scuola), verifica
dell'età (with minori, pornografi\*, online, piattaform\*), age
verification, parental control, potestà genitoriale, responsabilità
genitoriale, diritto dei genitori, scuole private.

**7. Free speech, privacy and civil liberties.** Tier 1: libertà di
espressione, libertà di manifestazione del pensiero, libertà di pensiero,
libertà di stampa, reati/reato di opinione, Digital Services Act,
regolamento sui servizi digitali, chat control, legge Mancino [IT],
crittografia end-to-end, trattato pandemico, accordo pandemico,
Regolamento sanitario internazionale. Tier 2: censura (with web, internet,
online, piattaform\*, social, opinion\*, espressione), hate speech,
discorso/discorsi d'odio, incitamento all'odio, disinformazione, fake news,
fact-checking, riconoscimento facciale, data retention, conservazione dei
dati di traffico, identità digitale, euro digitale, OMS (with pandemi\*,
sanitario internazionale, sovranità), deepfake.

**8. Freedom of religion.** Tier 1: libertà religiosa, libertà di
religione, libertà di culto, cristiani perseguitati, persecuzione dei
cristiani, persecuzione/i religiosa/e, minoranze religiose, minoranze
cristiane, crocifisso, insegnamento della religione cattolica [IT], ora di
religione [IT], vilipendio della religione, offese a una confessione
religiosa [IT], intese con le confessioni [IT]. Tier 2: otto per mille
[IT], 8 per mille [IT], luoghi di culto, confessioni religiose, Santa Sede,
Concordato (with Santa Sede, Chiesa, Stato e Chiesa, Vaticano) [IT], Patti
lateranensi [IT], moschee, moschea, antisemitismo, islamofobia,
cristianofobia, obiezione di coscienza, enti ecclesiastici, simboli
religiosi, velo integrale, burqa, macellazione rituale, rapporti tra Stato
e Chiesa, minoranze etniche e religiose [TESEO], insegnamento della
religione nelle scuole [TESEO], ecclesiastici e ministri del culto
[TESEO]. (Antisemitism is tier 2 pending the US scope decision: seven
Senate antisemitism bills are examined together.)

**9. Marriage and family.** Tier 1: unioni civili, unione civile, legge
Cirinnà [IT], matrimonio egualitario, matrimonio tra persone dello stesso
sesso, matrimonio omosessuale, stepchild adoption, adozione del figlio del
partner, famiglia naturale, famiglia fondata sul matrimonio, natalità,
denatalità, inverno demografico, quoziente familiare, assegno unico
universale [IT], matrimoni/o forzati/o, matrimoni precoci, poligamia.
Tier 2: adozioni internazionali, adozione di/dei minori, affido (with
minori, familiare, figli, minorenni), affidamento di minori, affidamento
condiviso, alienazione parentale, congedo/i parentale/i, bonus bebè [IT],
genitorialità, potestà dei genitori, diritto di famiglia, cessazione del
matrimonio, matrimonio religioso, politiche familiari, politiche per la
famiglia, genitore 1, divorzio, separazione personale dei coniugi,
famiglie numerose, conciliazione vita-lavoro.

**10. Surrogacy and embryology.** Tier 1: maternità surrogata,
surrogazione di maternità, gestazione per altri, GPA, utero in affitto,
reato universale [IT], procreazione medicalmente assistita, PMA, legge n.
40 [IT], legge 19 febbraio 2004, n. 40 [IT], fecondazione eterologa,
fecondazione assistita, fecondazione artificiale, embrioni, embrione,
crioconservazione, editing genetico, clonazione. Tier 2: legge 40 [IT],
trascrizione (with nascita, figli, coppie omogenitoriali, due madri, due
padri, estero), coppie omogenitoriali, riconoscimento dei figli, diagnosi
preimpianto, gameti, donazione di ovociti, cellule staminali embrionali.

**11. Migration (collated).** Tier 1: immigrazione, immigrazione
clandestina, protezione internazionale, richiedenti asilo, centri di
permanenza per il rimpatrio [IT], Protocollo Italia-Albania [IT], flussi
migratori, cittadinanza. Tier 2: CPR [IT], rimpatri, sbarchi, ius scholae,
ius soli, permesso di soggiorno, ONG.

**12. Prostitution, trafficking and sexual exploitation.** Tier 1:
prostituzione, legge Merlin [IT], sfruttamento sessuale, tratta di/degli
esseri umani, pornografia (without tutela degli animali, reati contro gli
animali), pornografic\*, pedopornografi\*, materiale pedopornografico, abusi
sessuali su minori, adescamento di minori, revenge porn, diffusione
illecita di immagini o video sessualmente espliciti [IT, art. 612-ter],
sextortion, turismo sessuale, case chiuse [IT], modello nordico. Tier 2:
lavoro sessuale, sex worker, violenza sessuale, riduzione in schiavitù,
deepfake (with sessual\*, nud\*, pornografi\*). Not "caporalato": it is
farm-labour exploitation, and it put two labour decrees on our ground.

**13. Organ donation.** Tier 1: donazione di/degli organi, trapianto/i di
organi, prelievo di organi, silenzio-assenso and silenzio assenso (with
organi, donazione, trapiant\*: alone it is administrative law), donazione
del corpo, commercio di organi, traffico di organi. Tier 2: trapianti,
trapianto, Centro nazionale trapianti [IT], morte cerebrale, accertamento
della morte, donatori (with organi, tessuti, trapiant\*: alone it is blood
donors), donatori di organi.

**Global exclusions** (never terms alone): genere, famiglia, scuola, vita,
salute, minori, religione.

**For the Swiss Italian list**: the unmarked terms carry over; the Swiss
statutes differ (abortion is article 119 of the Swiss Criminal Code, not
Law 194; same-sex marriage passed by referendum in 2021, "matrimonio per
tutti"; registered partnership is "unione domestica registrata"; assisted
suicide is article 115 CP), so every [IT] term needs a Swiss counterpart,
not a copy.

## Phase plan

1. **Phase 1 (built, this branch)**: bills of both chambers with TESEO
   general terms, Senate votes and Camera votes, positions on our ground,
   senators with group spells, watchlist by key. Runs with the English
   taxonomy plus the watchlist until the Italian file exists.
2. **Phase 1b (after Christopher's yes)**: generate `config/taxonomy-it.yaml`
   from the approved list (a `docs/keyword-taxonomy-it.md` source and
   `tools/generate_taxonomy.py --lang it`, as Germany), dispatch the weekly
   with reclassify, prune the watchlist. Then the **Italy edition**
   (`tools/it_monitor.py --edition --dm`, as the US and Australia) and the
   judge (spend needs a yes).
3. **Phase 1c: amendments and orders of the day.** 5,522 Senate votes and
   most Camera votes are amendments or orders of the day whose text says
   what they do; the Senate's osr:Emendamento (770,950 across all
   legislatures) and the Camera's `rif_aic` acts are where a vote's own
   subject lives. This, not the bill title, separates the abortion amendment
   from the rest of a decree (the omnibus problem above).
4. **Phase 2**: questions (6,840 Senate questions in the 19th; Camera via
   SPARQL when it answers), committee sittings, the agenda.
5. **Phase 3**: the Italian 5CA (positions are already stored per group per
   vote; first signers and co-signers are in both sources).
6. **Phase 4: the twenty regional councils** (below).

## The weekly job

`jobs/it-weekly.sh` runs `tools/it_rollcalls.py --budget-seconds 2700`
(exit 3 means "stored what it could, with gaps": still published). Two
callers:

- **Mac Mini, first**: Saturdays 01:00 London,
  `ops/launchd/net.citizengo.parlmonitor.it-weekly.plist` calling
  `tools/mini_run.sh it-weekly`; the script publishes the raw archive and
  the store itself, as `mini_run.sh` requires. Install after merge to main:
  `cp ops/launchd/net.citizengo.parlmonitor.it-weekly.plist ~/Library/LaunchAgents/`
  then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.it-weekly.plist`.
- **GitHub Actions, backup**: `.github/workflows/it-weekly.yml`, Saturdays
  01:00 and 02:00 UTC, behind `mini-check` with `job: IT_WEEKLY` and a
  200-minute grace (01:00 London is 00:00 UTC in summer), then the
  same-day retry gate. There the script runs with `IT_PUBLISH=false` and
  the workflow publishes in its own "Publish the raw archive" and "Publish
  the store" steps, as the repo's guard tests require. A hand dispatch can
  reclassify first (`IT_RECLASSIFY`).
- Watched by the failure alert (`alert.yml`) and `tools/coverage.py`: bills
  and members weekly (both are re-read whole), divisions a month plus a
  month's grace (recesses).

## Shared files touched (for the merge of the 13 country branches)

- `src/db.py`: four names added to `TABLES` (`it_members`, `it_bills`,
  `it_divisions`, `it_votes`) and two lines in `init_db` calling
  `it_store.ensure_schema`.
- `tools/coverage.py`: one `PIPELINES` entry ("Italy weekly"), three `FEEDS`
  rows, one `PIPELINE_FEEDS` entry, one `AWAITING_FIRST_RUN` entry.
- `.github/workflows/alert.yml`: one line, `"Italy weekly"`.
- `tests/test_db_state.py`: the plain-HTTP lint now also skips a URL
  inside SPARQL's angle brackets (`<http://dati.senato.it/osr/>`), as it
  already skipped XML namespaces in braces. The Senate's IRIs are
  identifiers in the http scheme; the endpoint itself is fetched over
  https.

Everything else is Italy's own: `src/it_store.py`, `tools/it_rollcalls.py`,
`config/watchlist-it.yaml`, `tests/test_it_rollcalls.py`,
`tests/fixtures/it/`, `jobs/it-weekly.sh`, the plist,
`.github/workflows/it-weekly.yml` and this file. `docs/mac-mini.md` is not
edited; the job table there can take its line at merge time.

## Regions (later, not probed)

Twenty regional councils (consigli regionali), five with special statute:
Abruzzo, Basilicata, Calabria, Campania, Emilia-Romagna, Friuli Venezia
Giulia (special), Lazio, Liguria, Lombardia, Marche, Molise, Piemonte,
Puglia, Sardegna (special), Sicilia (special: the Assemblea regionale
siciliana), Toscana, Trentino-Alto Adige/Südtirol (special: the regional
council plus the two provincial councils of Trento and Bolzano, the latter
partly in German), Umbria, Valle d'Aosta (special, partly French), Veneto.
Regional law matters on our ground (background, not probed): assisted
dying (Toscana's 2025 regional law), the consultori and the pro-life
associations admitted to them, school and family policy. Each council publishes its
own way; no aggregator was probed.

## Waiting on Chris

1. **Approve, cut or correct the Italian term list** above (ideally with an
   Italian campaigner's eye on the [IT] terms and the guards). Nothing is
   generated until then; the collector reads `config/taxonomy-it.yaml` the
   moment it exists.
2. **Openpolis as the Camera source.** It is a third party's undocumented
   API (the one its own site uses), keyless and current, but with no
   published terms of use for automated reading. Options: keep it, ask
   Openpolis, or switch the Camera to dati.camera.it/sparql, which was down
   for at least an hour this morning, runs two days behind, but is official
   and carries the deputies' persistent IDs. A switch keeps every vote key;
   Camera member keys would change.
3. **Scope questions carried over from the US**: antisemitism (seven
   Senate bills examined together), and whether the femicide and gender-violence bills
   (area 5, tier 2, the largest single group of hits) belong on our ground.
4. **Merge to main** when ready (this branch is pushed, not merged), then
   install the plist on the Mini.
5. **The edition and the judge** (phase 1b): the judge spends money, so it
   needs your yes as the US one did.
6. **Regions**: when, and in what order.
