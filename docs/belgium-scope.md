# Belgium: scoping the federal Chamber monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (the
honest CitizenGO User-Agent, throttled, retried) with every raw response
archived under `data/raw/2026-10-09/` (`be_probe_*` for the probes,
`be-rollcalls_*` for the collector's own run). Every number below was
measured on that day. Federal Parliament only; the regional and community
parliaments are listed at the end for later.

## Decisions (Christopher, 9 October 2026)

- **Own edition**, delivered to Christopher alone (a Slack DM), as for the US.
- **Shared taxonomy concept, but no edits to any existing taxonomy file.**
  Belgian Dutch and French terms are PROPOSED below; Christopher approves
  before anything is generated. The Netherlands (Dutch) and France and
  Switzerland (French) are being scoped in parallel, so each proposed term
  says whether it is Belgium-specific.
- **Federal Parliament first** (Chamber, then Senate). Flemish, Walloon,
  Brussels and community parliaments later.
- **The Mac Mini is the default runtime, GitHub Actions the backup** (the
  Mini-first weekly pattern of the Australia edition). No new paid services.
  Nothing is ever posted publicly.

## The finding that shapes everything

**Belgium publishes every recorded plenary vote with every member's name, as
HTML, with no key. The English taxonomy is blind to it.**

The Chamber (Kamer / Chambre, 150 members) votes electronically on almost
everything that reaches the plenary, and the record of each sitting lists
every member's position by name. Legislature 56 (elected 9 June 2024) has
held **143 plenary sittings**; **85 of them took recorded votes**, **1,281
votes** in all, carrying **172,514 individual positions**. Every one parsed;
three votes have no name list, and the record says so itself (below).

Run over the same material, `config/taxonomy.yaml` (English, unchanged):

| Text matched (legislature 56) | English taxonomy | Proposed Dutch + French terms |
|---|---|---|
| Dossier titles, FR + NL (1,776 dossiers) | 13 (1 tier 1) | **72 (39 tier 1)** |
| Recorded votes, own heading and question (1,281) | 1 | **5** |
| Written questions, titles (13,275) | 19 (5 tier 1) | **157 (84 tier 1)** |
| Oral questions and interpellations, titles (17,505) | not run | **250 (154 tier 1)** |

The English hits are accidents of spelling: seven of the thirteen dossiers
match `contracepti*` because the French is "contraceptifs", three match
`polygam*`, one is the EU "Chat Control" resolution. The Germany precedent
holds exactly: an English term list collects almost nothing and sees less.

**Recorded votes on our ground are rare, because our ground rarely reaches
the plenary.** Of the 1,281 votes, the proposed terms find five, on four
dossiers:

- **56/143/4 and 56/143/5, 8 October 2026:** the bereavement-leave-after-
  euthanasia bill (dossier 56/1338). An amendment by Caroline Désir (PS)
  rejected 55-75-5; the bill adopted **134-0-1**.
- **56/131/27, 25 June 2026:** the Justice committee's proposal to REJECT an
  abortion bill (56/40) adopted 93-37-0. This is how the majority kills a
  bill on our ground without a vote on its substance.
- **56/95/21, 26 February 2026:** the same route for a ban on religious
  symbols for federal civil servants (56/149), rejected 92-37-3.
- 56/80/8 (housing on divorce) is noise from a tier-2 word.

Most of the 72 dossiers on our ground are private members' bills that sit
in committee: the abortion liberalisation bills (56/30, 35, 42, 44, 270,
822, 1122, 1266), the dementia extension of the euthanasia law (56/183),
surrogacy (56/134), donor anonymity (56/94, 199, 783). So the document
layer is where the weekly signal is, and the vote layer is what a 5CA is
built on when one does reach the floor. Both are built.

## What the Chamber publishes

All on `www.lachambre.be` (French) and `www.dekamer.be` (Dutch), the same
server. **No API key anywhere. `robots.txt` asks for `Crawl-delay: 5`**,
which the collector honours (`set_host_throttle`), and blocks only BLEXBot.
No bot challenge was met on any page.

### Plenary record (Integraal Verslag / Compte rendu intégral): WORKS, the core

- Listing: `kvvcr/showpage.cfm?section=/cricra&language=fr&cfm=dcricra.cfm?type=plen&cricra=cri&count=all`
  (222 KB) names every sitting of the legislature with PDF and HTML links.
- One sitting: `/doc/PCRI/html/56/ip143x.html`, a Word export in
  **windows-1252**, 50 KB to 3.1 MB (sitting 60, the July 2025 budget
  marathon, 161 votes). 143 files, **15 MB gzipped, 12 minutes** at five
  seconds apart.
- The body gives each vote's agenda heading in both languages with the
  **document number** ("(1338/6)"), the question put ("Stemming over
  amendement nr. 20 van Caroline Désir op artikel 2. (1338/9)"), the counts
  ("Ja 55 Oui Nee 75 Non Onthoudingen 5 Abstentions") and the Chamber's own
  sentence on the result ("En conséquence, l'amendement est rejeté.").
- The annex **"DETAIL VAN DE NAAMSTEMMINGEN / DETAIL DES VOTES NOMINATIFS"**
  lists, per vote, every member under Ja/Oui, Nee/Non and
  Onthoudingen/Abstentions, as "Surname Forename".
- The record of a Thursday sitting was online the same evening (sitting 143,
  8 October 2026, generated 16:53 UTC).

Quirks, each measured and handled (`tools/be_rollcalls.py`):

1. **One result, many questions.** "Mag de uitslag van de vorige stemming
   ook gelden voor deze stemming? (Ja)": the previous electronic vote is
   applied to the next amendment, and the record repeats "(Stemming/vote 2)".
   Stored as one division whose `subjects` lists every question it decided
   (sitting 140, vote 2: five amendments).
2. **Layouts changed over the legislature.** "(Stemming/ vote 4)" with a
   space in 2025; "Vote nominatif - Naamstemming: 1" with the French label
   first, and "Oui 80 Ja" order, in the first sittings of 2024; "Vote
   nominatif : 1" spaced in 2025.
3. **Counted votes.** "(Elektronische telling/comptage électronique 1)":
   a quorum or support count with no names. Eight in the legislature; stored
   as `kind = 'count'`.
4. **Annulled votes.** "(Le vote n° 43 est annulé.)" (sitting 60): stored
   with `outcome = 'annulled'`; the annex still lists it.
5. **Name lists withheld, said by the record itself.** Sitting 140, vote 4:
   "Pour des raisons techniques, le détail du vote n'est pas disponible";
   sitting 81 (10 December 2025): "Ce compte rendu n'a pas d'annexe". Three
   votes in all. Recorded as gaps, never guessed.
6. **No party in the vote lists.** Only names. The group comes from the
   member list at the time of storage (`be_votes.group_seen`), which is
   honest about being the group WHEN STORED, not at the vote. A member who
   changes group (Open VLD became "Anders." in 2025) keeps the new label.
7. **Names are not always printed the same way.** "Mutyebele Ngoi" for Lydia
   Mutyebele Ngoi in the 2024 sittings; one whole list printed forename
   first (sitting 72, vote 13). Resolved only when exactly one member fits;
   **every one of the 172,514 positions resolved** to a member key.
8. **Motions have no dossier.** Votes on motions after interpellations
   cite "MOT nr. 300/1", not a dossier: 112 of the votes, and with
   procedural votes 145 (11%) carry no dossier key.

### Dossier index (Fichier législatif / FLWB): WORKS

- `ListDocument.cfm?legislat=56` gives the ranges; `ListFromTo.cfm?legislat=56&from=1300&to=1399`
  lists a hundred dossiers a page: number, title and main Eurovoc descriptor.
  The same in Dutch with `language=nl`. **1,776 dossiers** in legislature 56,
  numbered up to 1800. 38 pages, **3 minutes**.
- The numbering covers more than bills: Council of State opinions, Myria
  reports, appointments to commissions are dossiers too (56/611 is an
  appointment to the embryo research commission).

### Dossier pages: WORKS, one request each

- `flwbn.cfm?lang=F&legislat=56&dossierID=1338` (50 KB): status ("PENDANT
  CHAMBRE"), deposit date, constitutional procedure ("74 procédure
  monocamérale"), document type, every author **with their member key and
  group**, every sub-document as PDF (`/FLWB/PDF/56/1338/56K1338001.pdf`)
  and **every Eurovoc descriptor**: 56/1338 carries "CONGE SOCIAL | DROIT
  DU TRAVAIL | TRAVAIL | EUTHANASIE | MORT".
- At five seconds each, the whole legislature is 2.5 hours, so the collector
  DRAINS them under its time budget: voted and watched dossiers first, then
  the week's recent documents, then the backlog newest first (100 a run).
- **The server resets connections after a long crawl.** In the scratch run,
  after about 520 requests in 46 minutes (143 sittings, the index and 272
  dossier pages, all five seconds apart) four dossier pages in a row failed
  with "Connection reset by peer". The run was stopped; one request a few
  minutes later was answered normally. So the drain stops after three
  refusals in a row, and the per-run cap is 100 pages: a first run is about
  285 requests, a normal week about 150.
- `LastDocument.cfm` lists the week's new documents (61 dossiers in the week
  to 8 October), which is how a status change gets re-read.

### Members: WORKS

`cvlist54.cfm` (sitting members, 150, with group) and
`cvlist54.cfm?legis=56&today=n` (all **176** who have sat in legislature
56, without group). Each carries the Chamber's member key, the key its
document authors and written questions also use. **Three sitting members'
keys begin with a capital O, not a zero** ("O1330", Dominiek Sneppe): kept
as printed. Groups now: N-VA 23, VB 19, MR 18, PS 15, PVDA-PTB 15, Les
Engagés 15, Vooruit 12, cd&v 11, Ecolo-Groen 9, Anders. 8, DéFI 1,
independent 1.

### data.lachambre.be, the Chamber's open data API: WORKS, despite its label

`https://data.lachambre.be/v0/` (Swagger at `v0/swagger.json`). The front
page dates from 8 November 2016 and calls itself a "conceptual phase" with
"test data", but the data are current:

- `/qrva?leg=56`: written questions, JSON or XML, paged by ten. 6,096 in the
  search; the bulk **`/qrva/archive?leg=56` is a 45 MB zip of 13,275
  questions, full text, deposited 22 July 2024 to 7 September 2026** (the
  site's latest printed bulletin, number 53, is dated 15 June 2026).
- `/inqo/archive?leg=56`: **17,505 oral questions and interpellations**,
  12 MB zip, discussed 27 August 2024 to 8 September 2026.
- `/actr` (7,015 political actors since 1831), `/orgn` (1,118 organs).
- **No votes and no dossiers** in the API. The plenary record above is the
  only source for votes.

### Agenda: WORKS, PDF

`agendaList.cfm` links the weekly plenary convocation and its amendments as
PDF (the week of 12 to 16 October 2026 was already posted on 9 October).
Committee agendas: `comagendaList.cfm`. Not parsed yet.

### The Senate: WORKS, PDF only, thin

`www.senate.be` (frames; Cloudflare in front; `robots.txt` allows all). Since
the 2014 reform the Senate is not a permanent chamber and votes rarely.
Legislature 8 has **18 plenary sittings** (8-1 to 8-18, the last on 10 July
2026). The annals (`/crv/8-18.pdf`, 1.3 MB) are **PDF only** ("Ce document
n'est disponible qu'en version PDF"); text extracts cleanly with `pypdf`.
Sitting 8-18 took **5 named votes**, listed by name per language group
(Dutch group 25, French group 17, the German-speaking senator), on special
laws, an information report on carpooling and two requests for reports.
Nothing on our ground. Worth a phase of its own only for completeness.

### Not available

- **Committee votes by name.** Committees vote by show of hands; the record
  gives counts only (and committee reports carry them).
- **Party at the time of the vote** (see quirk 6).

## Phase 1: built, 9 October 2026

`tools/be_rollcalls.py` into `be_members`, `be_dossiers`, `be_sittings`,
`be_divisions` and `be_votes` (schema in `src/be_store.py`, declared in
`db.TABLES`). Live run into a scratch database, not the store:

| | Read | Notes |
|---|---|---|
| Members | 176 (150 sitting) | |
| Plenary sittings | 143 | 12 minutes, 15 MB gzipped |
| Recorded votes | 1,281 | 1,273 named, 8 counted, 1 annulled; 1,136 tied to a dossier |
| Positions | 172,514 | every one resolved to a member key |
| Dossiers in the index | 1,776 | titles in French and Dutch |
| Dossier pages | 272 read, then stopped (see the connection resets) | Eurovoc, status, authors; 100 a run from now on |
| Gaps | 3 votes without names | the record's own words |

- **Keyed on document numbers, never titles.** A division is
  `56/<sitting>/<vote>`, a dossier `56/<number>`. The plenary record prints
  different titles for the same dossier on different days (56/1338 gained
  "(nieuw opschrift)" between readings).
- **No classification on text yet**, as in Germany's phase 1. Areas come
  only from `config/watchlist-be.yaml`, by dossier key: a draft of 39
  dossiers found by the proposed terms and read by title. A division takes
  its dossier's areas.
- **Scheduled Mini-first:** `jobs/be-weekly.sh`, launchd
  `ops/launchd/net.citizengo.parlmonitor.be-weekly.plist` (Saturdays 02:30
  London) and the backup `.github/workflows/be-weekly.yml` (Saturdays 02:30
  and 04:30 UTC, gated by `mini-check` with `BE_WEEKLY`, grace 200 minutes).
  Saturday, because the Chamber votes on Thursday afternoons. The first run
  is about 45 minutes (the time budget); later weeks about five. **It runs
  only once merged to main** (GitHub schedules from the default branch), and
  the Mini needs the plist installed.
- No edition yet: nothing reads these tables. That is phase 2.

## Proposed taxonomy terms (for approval; nothing generated)

Same thirteen areas and keys as the English file; only the terms differ.
`*` is a stem, as in every taxonomy here. **BE** marks a term specific to
Belgian law or institutions; **NL** a Dutch term the Netherlands scope may
share; **FR** a French term France or Switzerland may share. A term both
languages use (euthanasie) is marked NL/FR.

Measured on 9 October 2026 against the 1,776 dossier titles, 1,281 votes,
13,275 written-question titles and 17,505 oral-question titles above.

### 1 Abortion
- Tier 1: abortus (NL), abortuspil* (NL), zwangerschapsafbreking (NL; "vrijwillige zwangerschapsafbreking" is the BE statutory term), afbreking van de zwangerschap (NL), avortement* (FR), interruption* volontaire* de grossesse (FR; BE statute), IVG (FR), pilule* abortive* (FR), délit d'entrave (FR), belemmeringsdelict with abortus or zwangerschapsafbreking (BE).
- Tier 2: interruption* de grossesse, ongeboren, enfant* à naître, foetus, bedenktijd and délai de réflexion only with abortion words (BE: the six-day waiting period; unguarded, it caught an electricity-contracts bill), gewetensbezwaar / objection de conscience, doodgeboren / mort-né*, sterrenkind* (BE-NL), enfant* né* sans vie and levenloos geboren (BE: the civil-status term for stillborn children, three dossiers), contracepti* and anticonceptie* (Christopher's decision that contraception is area 1).
- Found: 15 dossiers tier 1; the June 2026 rejection vote.

### 2 Assisted dying
- Tier 1: euthanasie (NL/FR) **vetoed beside animal words** (dier*, animal, animaux, honden, chiens, katten, chats), hulp bij zelfdoding (NL), suicide assisté / assistance au suicide (FR), wilsverklaring* (BE-NL, the advance euthanasia declaration), déclaration* anticipée* (BE-FR), levenseinde (NL), fin de vie (FR).
- Tier 2: palliatie*, soins palliatifs, palliatieve zorg, psychisch lijden / souffrance psychique (BE: euthanasia for psychiatric suffering), voltooid leven / vie accomplie (NL: the Dutch "completed life" debate).
- Note: "euthanasie bij minderjarigen" (minors, legal in Belgium since 2014) needs no term of its own: euthanasie catches it. The written questions include "L'euthanasie de jeunes".
- Found: 6 dossiers, 2 tier 1 (56/183 dementia extension, 56/1338); 12 written questions.

### 3 Gender medicine and children
- Tier 1: genderdysforie (NL), dysphorie de genre (FR), puberteitsremmer* (NL), bloqueur* de puberté (FR), transgender minderjarige* / transgenderjongere* (NL), mineur* transgenre* (FR), transitie and transition only beside minors or children.
- Tier 2: transgender*, transgenre*, genderidentiteit, identité de genre, genderzorg, genderkliniek* (BE: the Ghent and Liège clinics), détransition*, detransitie*.
- Found: 56/335, the resolution for a cautious approach and a KCE review.

### 4 Conversion practices
- Tier 1: conversietherapie*, conversiepraktijk*, conversiebehandeling* (NL), thérapie* de conversion, pratique* de conversion (FR). Belgium banned conversion practices in 2023; nothing matched in legislature 56, which is the expected result after a ban.

### 5 Sex-based rights
- Tier 1: geslachtsregistratie, registratie van het geslacht (BE: the 2017 transgender law's wording), enregistrement du sexe, mention du sexe, transgenderwet / loi transgenre (BE), genderexpressie / expression de genre, non-binair* / non-binaire*, X-registratie, sexe neutre (BE: the Constitutional Court's 2019 ruling on a third option).
- Tier 2: gendergelijkheid, égalité de genre, genderneutra*, seksisme, sexisme (four "sexism in public space" bills: tier 2 is right).

### 6 Parental rights and education
- Tier 1: EVRAS (BE-FR: the compulsory relational and sexual education of the French Community, the subject of CitizenGO's 2023 campaign; a community, not federal, matter, so it will matter more for the Wallonia-Brussels parliament), relationele en seksuele vorming, seksuele opvoeding, éducation sexuelle, éducation à la vie relationnelle, thuisonderwijs / enseignement à domicile, ouderlijk gezag / autorité parentale (BE civil law terms), lijfstraf* / châtiment* corporel* / violence* éducative* / pedagogisch geweld.
- Tier 2: kinderrechten, droits de l'enfant, onderwijsvrijheid / liberté d'enseignement (BE: article 24 of the Constitution), jeugdbescherming, protection de la jeunesse.

### 7 Free speech, privacy and civil liberties
- Tier 1: vrijheid van meningsuiting, liberté d'expression, haatspraak, discours de haine, discours haineux, aanzetten tot haat / incitation à la haine (BE: the new Penal Code's offence), negationisme / négationnisme (BE: the 1995 Holocaust denial law), godslastering / blasphème, digitale identiteit / identité numérique, leeftijdsverificatie and vérification de l'âge only beside porn or social media, persvrijheid / liberté de la presse, academische vrijheid / liberté académique, chat control / chatcontrole.
- Tier 2: censuur, censure, desinformatie, désinformation, antidiscriminatiewet* / loi* antidiscrimination and antiracismewet / loi antiracisme (BE: the 2007 laws), haatmisdrij* / crime* de haine, pornogra*, deepfake*.

### 8 Freedom of religion
- Tier 1: vrijheid van godsdienst, godsdienstvrijheid, liberté de religion, liberté religieuse, liberté de culte, erediensten (BE: the recognised cults, paid by the state), ministres des cultes / bedienaren van de eredienst* (BE), levensbeschouwelijke tekens and "tekens van een geloofs- of levensovertuiging" (BE-NL), signes convictionnels (BE-FR: the Belgian legal phrase for religious and philosophical symbols), signes religieux, hoofddoek* / foulard*, biechtgeheim / secret de la confession (BE: the debate after the Church abuse inquiry), ritueel slachten / abattage rituel / onverdoofd slachten / abattage sans étourdissement.
- Tier 2: levensbeschouwing*, convictions philosophiques, neutraliteit and neutralité only beside religion or the State (unguarded, "neutralité fiscale" matched), cultes, eredienst, laïcité, kerkfabriek* / fabriques d'église (BE), imam, imams (whole words: "imam*" matched "Imamoglu"), moskee*, mosquée*, christenvervolging, persécution* des chrétiens.

### 9 Marriage and family
- Tier 1: huwelijk tussen personen van hetzelfde geslacht, mariage entre personnes de même sexe, meeouderschap / coparentalité, afstamming / filiation, meemoeder* / co-mère* (BE: co-motherhood since 2014), polygamie, gedwongen huwelijk*, mariage* forcé*.
- Tier 2: huwelijk, mariage, echtscheiding, divorce, adoptie, adoption d'enfant*, adoption internationale (bare French "adoption" is dropped: it is the adoption of a law), wettelijke samenwoning / cohabitation légale (BE), gezinsbeleid, politique familiale, geboortecijfer, natalité.

### 10 Surrogacy and embryology
- Tier 1: draagmoederschap, draagmoeder*, **zwangerschap voor anderen** (BE-NL: the Chamber's own title for the surrogacy bill 56/134; draagmoederschap alone missed it), gestation pour autrui, GPA, maternité de substitution, mère* porteuse*, medisch begeleide voortplanting / procréation médicalement assistée (BE: the 2007 law), embryo* / embryon*, eiceldonatie / don d'ovocytes, spermadonatie / don de sperme, anonimiteit van de donor / anonymat du donneur.
- Tier 2: IVF, FIV, gameten, gamètes, eicel*, ovocyte*, kinderwens.

### 11 Migration
Collated, never campaigned; no terms proposed.

### 12 Prostitution, trafficking and sexual exploitation
- Tier 1: sekswerk* (BE-NL: decriminalised in 2022, employment contracts for sex workers in 2024), travail du sexe, travailleu* du sexe, prostitutie, prostitution, mensenhandel, **traite des êtres humains** (BE-FR: the Belgian legal term; Quebec says "traite des personnes"), seksuele uitbuiting, exploitation sexuelle, souteneur*, pooier*, proxénétisme, proxénète*, loverboy* (BE-NL).
- Tier 2: escort*, massagesalon*, salon* de massage.
- Note: mensenhandel and traite des êtres humains are mostly labour trafficking in Belgian usage (the Myria reports, the Borealis case); tier 1 here, but triage should expect that.

### 13 Organ donation
- Tier 1: orgaandonatie, orgaandonor*, donorregistratie, don* d'organes, donneur* d'organes, transplantatie*, transplantation*, greffe* d'organes, orgaanhandel, trafic d'organes.
- Tier 2: weefseldonatie, don* de tissus, lichaamsmateriaal / matériel corporel humain (BE: the 2008 law on human body material).

### The Chamber's own thesaurus

Every dossier page carries Eurovoc descriptors (EUTHANASIE, AVORTEMENT,
CONTRACEPTION, PROCREATION ARTIFICIELLE). That is a controlled vocabulary
applied by the Chamber's documentalists to every dossier, independent of
any term list, and it is how recall should be checked once the dossier
pages have drained (the German taxonomy scan's method,
`tools/de_taxonomy_scan.py`).

Measured on the first 272 dossier pages read (the voted dossiers, newest
first, so a sample biased towards government bills): 613 distinct
descriptors. Only six pages carried a descriptor on our ground. The one
EUTHANASIE dossier (56/1338) was caught by the title terms; the misses were
56/461 (illegal adoptions, ADOPTION D'ENFANT: the plural "adoptions" escapes
"adoption d'enfant*", worth a term), 56/930 (Boualem Sansal, LIBERTE
D'EXPRESSION abroad), 56/1385 (sexual violence) and 56/1377 (INTEGRISME
RELIGIEUX in a migration bill). A real recall figure needs the whole drain,
about eighteen weekly runs at 100 pages.

## Phase plan

1. **Phase 1 (built):** members, dossier index, dossier pages (drained),
   every plenary vote with every position. Watchlist areas only.
2. **Phase 2: the Belgian term list** (above) once approved, as
   `docs/keyword-taxonomy-be.md` generating `config/taxonomy-be.yaml`, run
   on French text with the French terms and Dutch text with the Dutch ones;
   then a Belgian edition (`editions/be-monitor-<date>.md`) and the DM,
   following `tools/us_monitor.py`. Body matching of dossier PDFs as
   `src/eudoc.py` does, for omnibus bills ("dispositions diverses").
3. **Phase 3: questions and agenda.** The written-question and
   oral-question archives from data.lachambre.be (keyless, weekly zips), and
   the weekly plenary convocation (PDF).
4. **Phase 4: the Senate** (PDF annals with `pypdf`), and a Belgian 5CA from
   the vote positions.
5. **Later: the regional and community parliaments**, each its own source:
   - Flemish Parliament (Vlaams Parlement), `vlaamsparlement.be`;
   - Parliament of Wallonia, `parlement-wallonie.be`;
   - Brussels-Capital Parliament, `parlement.brussels`, and its Dutch and
     French community commissions (VGC, COCOF) and the joint COCOM;
   - Parliament of the Wallonia-Brussels Federation (French Community),
     `pfwb.be`: education, so EVRAS;
   - Parliament of the German-speaking Community, `pdg.be`.
   Education, youth and much of health and family policy are community
   matters, so these carry ground the Chamber does not.

## Dates that matter

- **The Chamber sits from the second Tuesday of October to late July**;
  plenary votes are on Thursday afternoons. No votes from late July to
  mid-September (none between 16 July and 17 September 2026).
- **Next federal election: June 2029** (with the European elections).
  Pending dossiers lapse at dissolution unless revived, and every watchlist
  key changes legislature.

## Shared files touched (for the 13-branch merge)

Kept to registration only:

- `src/db.py`: five table names in `TABLES` and one `be_store.ensure_schema`
  call in `init_db`.
- `tools/coverage.py`: "Belgium weekly" in `PIPELINES`, three `FEEDS` rows
  (`be_members`, `be_dossiers`, `be_divisions`), a `PIPELINE_FEEDS` entry
  and an `AWAITING_FIRST_RUN` entry.
- `.github/workflows/alert.yml`: "Belgium weekly" in the watched workflows.

Everything else is new and Belgium's own: `src/be_store.py`,
`tools/be_rollcalls.py`, `config/watchlist-be.yaml`, `tests/test_be_rollcalls.py`,
`tests/fixtures/be/`, `jobs/be-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.be-weekly.plist`,
`.github/workflows/be-weekly.yml` and this file.

## Waiting on Chris

1. **Approve, cut or correct the proposed Dutch and French terms** above
   (ideally with a Belgian reader for each language). Nothing is generated
   until then; until then the Belgian tables carry watchlist areas only.
2. **Review `config/watchlist-be.yaml`** (39 dossiers). Two entries are texts
   CitizenGO would support (56/335 on gender clinics, 56/1713 on the
   persecution of Christians); the file finds, it does not take sides.
3. **Scope calls:** are the stillborn-child recognition bills (56/153, 170,
   1080) area 1? Are the religious-symbol bans (56/149, 428, 429) and the
   laicity revision (56/594) ground CitizenGO campaigns on, and on which
   side? Is labour trafficking (most "mensenhandel") in area 12?
4. **Merge to main** when ready, so the backup schedule exists, and **install
   the plist on the Mac Mini** (`MINI_LAST_BE_WEEKLY` is then stamped by
   `tools/mini_run.sh`). The Saturday 03:00 and 05:00 UTC slots were free
   on 9 October; at the countries merge (10 October) Austria kept them and
   Belgium moved to 02:30 and 04:30.
5. **Edition and DM:** phase 2 needs the term list first. Say if a votes-only
   weekly DM (watchlist dossiers, new votes) is wanted before that.
6. Not needed: no key, no account, no paid service. The Chamber's
   `Crawl-delay: 5` makes the first run slow, not blocked.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term lists approved (BE1, BE3 stillborn-child bills area 1, BE4 religious symbols and laicity, BE5 labour trafficking area 12); Dutch terms in `config/taxonomy-nl.yaml`, French in the `config/taxonomy-fr.yaml` addendum.
- The collector now classifies dossier titles and division headings with both, for `be`, unioned with the watchlist.
- Weekly moved to Saturday 02:30/04:30 UTC (Austria holds 03:00/05:00).

Later phases and items for Chris (not built at the merge):

- A votes-only DM before the full edition (BE6): the edition phase.
- Not expressible as additions to the Quebec base: the euthanasie animal veto and the tier differences the scope proposed against taxonomy-qc. They need a Belgium-specific override if wanted.
- Member profiles (handover item 3, built 10 October 2026, branch `parity-profiles`): `profiles/be/` from the store each weekly run (`tools/member_profiles.py be`, src/member_profiles.py): party, chamber, constituency, every recorded position on a vote on our ground as the edition classifies it, verbatim, with the basis of the party at the vote; no verdicts, no DM. The vote lists print names only: the group shown is the member's group when the vote was stored, labelled "not party at the vote".

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/be_stance.yaml` holds 27 bill direction(s) (Claude's drafts from the watchlist) and 4 vote reading(s): 3 with proposed values, 0 procedural, 1 need reading, 0 confirmed. Guide: `docs/5ca-be-readings.md`; confirm with `python3 tools/country_5ca.py --cc be --sign-from-doc --by NAME`. Sheets (`data/5ca/be-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for Belgium (`config/stance_signers.yaml`).
