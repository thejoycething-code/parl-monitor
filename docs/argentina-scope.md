# Argentina: scoping the National Congress monitor

Probed live on 9 October 2026 from the laptop (BT broadband, London), with
two checks from a GitHub runner (the read-only `probe-hosts.yml`). Every
number below was measured, not estimated. Raw responses are archived under
`data/raw/2026-10-09/` (`ar-rollcalls_*` from the collector, `ar-probe_*`
from the hand probes). National Congress only; the provincial legislatures
are listed at the end for later.

## Decisions already taken (Christopher)

- **Own edition**, delivered to Christopher alone (Slack DM), as the US is.
- **Shared taxonomy concept, separate Spanish file.** `config/taxonomy.yaml`
  and every existing taxonomy file stay untouched. The Spanish term list is
  PROPOSED below; `config/taxonomy-es.yaml` is generated only after
  Christopher approves it. Spain and Mexico are being scoped in parallel, so
  the list marks which terms are Argentina's own.
- **Congress first** (Diputados and Senado); provincial legislatures later.
- **Mac Mini first**, GitHub Actions as the backup. No new paid services.
  Nothing is posted publicly anywhere.

## The finding that shapes everything

**Two things are true at once, and both point the same way as Germany.**

1. **The English taxonomy is blind to Argentine Spanish.** Run unchanged over
   every Senate roll call of 2024, 2025 and 2026 (327 actas, each with the
   extracto of the expediente it voted on), `config/taxonomy.yaml` matched
   **0**. Over the 2,000 most recent Diputados expedientes (5 June to
   6 October 2026) it matched **3**, every one on the acronym `LGBTIQ`.
2. **Roll calls are almost never on our ground.** With the proposed Spanish
   terms, 2 of the 327 Senate actas matched at tier 1, both on one bill (the
   Penal Code offence of abducting or selling children, July and August
   2024, area 12). Read by hand, the 165 distinct subjects voted on in three
   years are the economy (Ley de Bases, the labour reform, the budget),
   decrees, nominations, treaties, the juvenile justice regime and university
   funding. **Nothing on abortion, gender, euthanasia, ESI or religious
   freedom reached a recorded Senate vote in 2024-2026.**

So, as in the Bundestag, the issues we campaign on move through the
**expedientes** (bills, resolutions and declarations filed by members, most
of which never reach the floor), not through the roll calls. The register is
where the Spanish terms find things: **32 of those 2,000 Diputados
expedientes matched a tier-1 term (59 at any tier)**, and read by hand about
29 of the 32 are on our ground: two euthanasia bills, six expedientes on
Argentina's adherence to the Geneva Consensus Declaration, ESI, conversion
therapy, trafficking and the sex-work fight, children on social media.
Roll calls still matter for the 5CA (who voted how, when something does
reach the floor), and the Senate's are complete and free.

## What Argentina publishes

### Senate roll calls: works today, open, no key

- `www.senado.gob.ar/votaciones/actas`: every roll call of a calendar year on
  one page. The default is the current year; a plain form POST
  (`busqueda_actas[anio]=2025`, no token, no cookie) picks another. Measured:
  **2024: 91 actas over 9 sitting days; 2025: 97 (95 with a detail page)
  over 10; 2026: 139 over 13 sitting days, the last on 24 September.** Each
  row gives the date, the acta number (it restarts every session), the title,
  the expedientes and Orden del Día voted on (as links), the vote type (`EN
  GENERAL`, `EN PARTICULAR`, ...), the result in the Senate's own words
  (`AFIRMATIVO` 281, `NEGATIVO` 35, `EMPATE` 5, `CANCELADA LEV.VOT.` 4,
  `CANCELADA` 2 across the three years), the majority required, a PDF and a
  video link. The page is 0.5 to 0.9 MB and takes 7 to 21 seconds.
- `/votaciones/detalleActa/<id>`: **every senator's position on one page**:
  name, bloc, province and `AFIRMATIVO` / `NEGATIVO` / `ABSTENCIÓN` /
  `AUSENTE`, plus the four totals and the time of the vote. 147 to 167 KB,
  2 to 6 seconds. 23,400 positions stored for the 327 actas (72 each; 262 of
  them blank, 261 on cancelled votes and one on an ordinary one, stored
  as NULL rather than invented).
- **Sitting senators carry a link with the Senate's own ID**
  (`/senadores/senador/540`); **former senators are printed without one**
  (21 of 72 on a June 2024 acta). They are resolved by exact name, accents
  folded, against the Senate's historic roster
  (`/micrositios/DatosAbiertos/ExportarListadoSenadoresHistorico/json`,
  1,380 terms back to 1924, 960 KB, the same IDs), narrowed by the term that
  covers the vote's date when a name has several IDs. **All 94 senators who
  voted in 2024-2026 resolved; none was dropped.** A name that matches no
  single ID would be dropped and recorded as a gap, never stored under a
  guess.
- **The two rows without a detail page** (28 November 2025, the swearing-in
  of the senators elected in October) are stored with their totals unknown
  and `has_detail = 0`, pointing at the PDF.
- Quirk: **the Senate resets connections now and then.** 10 of about 450
  requests in the backfill got `Connection reset by peer` (4 detail pages, 6
  expediente pages); every one answered on the next run. The collector
  records a gap, stores nothing for a refused acta, and re-reads it next time.
- `www.senado.gob.ar/robots.txt` disallows only the archive.org bots.

### Senate expedientes: the voted ones work; the full list needs phase 2

- `/parlamentario/comisiones/verExp/<n>.<yy>/<origin>/<type>`, linked from
  every acta: the extracto (the summary), the origin, the type, the
  **Diputados number when the bill came from there** (`Exp. HCD: 10-PE-24`),
  committees, the Orden del Día and **the law number once sanctioned**.
  102 expedientes behind the 327 actas: 40 `PE/AC` (executive nominations),
  27 `S/PL` (senators' bills), 9 `CD/PL` (bills from Diputados), 8 `PE/PL`,
  8 `PE/DC` (decrees), and 10 others; 9 carry the Diputados crosswalk and 19
  a law number. The page's summary table never closes its cells.
- **The full list of Senate expedientes is a session-bound search.**
  `/parlamentario/parlamentaria/fechaMesa` (POST with a Symfony CSRF token
  and a session cookie, 10 rows a page, paged by `?page=N` within the
  session) answered for September 2026: the newest senators' expediente
  on 30 September 2026 was **S-1725/26**, so about 1,700 had entered in
  2026 by then. Each row: number, type (PL, PC, PR, PD ...),
  origin, entry date and the extracto with the author's name. It works with
  curl and a cookie jar; `src/http.py` has no cookie support, so it is phase
  2 (a small cookie-aware POST, not a workaround: the form is public and
  the token is in the page).
- The Senate's open-data page (`/micrositios/DatosAbiertos/`) has **no votes
  and no expedientes dataset**: senators (current, 72, JSON; historic),
  committees, the asuntos entrados (one PDF link per session), the bulletin
  (whose JSON has trailing commas and does not parse) and administrative
  data.

### Diputados register of expedientes: works today, open, no key, rationed

- `datos.hcdn.gob.ar` is a CKAN portal with 31 datasets. **"Proyectos
  Parlamentarios"** is updated daily (last on 7 October 2026): **114,869
  expedientes from 2008 to the Trámite Parlamentario of 6 October 2026**
  (period 144, TP no. 150), each with HCDN's own ID, the title (a full
  sentence that IS the summary), the date, the Diputados number
  (`5346-D-2026`), the Senate number when it came from there, the type (LEY,
  RESOLUCION, DECLARACION, MENSAJE) and the first author. September 2026
  alone: 652 (320 resolutions, 164 bills, 163 declarations, 5 executive
  messages).
- Read through CKAN's datastore SQL endpoint
  (`/api/3/action/datastore_search_sql`), JSON, no key. The resource
  downloads (`.../download/proyectos_parlamentarios2.6.csv`) timed out four
  times out of four and are not used.
- **The host turns clients away.** It stopped accepting connections from
  the laptop five times on 9 October (04:11-04:21, 04:23-04:40, 04:55 to
  about 05:55, 06:00 to about 06:50, and again at 06:53 UTC) while a GitHub
  runner was answered.
  The first four blocks came straight after a request that hung past a
  minute: the CSV download, two aggregate queries, a sorted query over two
  and a half years, and a 2,000-row page with an OFFSET. But between blocks
  fewer and fewer requests got through (four, then two, then one each time),
  and the fifth came on the SECOND request of a retest at 06:50: October 2026
  (73 rows) answered, then September 2026 hung, the same one-month query
  that had answered in 2.9 seconds at 04:09. So it is not query weight alone:
  after a morning of probing, the laptop's address got about one request
  per block. A fresh address got about twenty-five before its first block.
  None of this is documented anywhere.
- So the collector reads the register **one calendar month per request, no
  ORDER BY, no OFFSET, at most 7 months a run (8 requests with the members),
  one every 20 seconds, newest month first, and stops at the first
  refusal**. The weekly re-reads the last 45 days (three months) and then
  walks the backfill a month further back with each spare request: March
  2024 is reached after about eight Saturdays. Measured: 2,000 expedientes
  (5 June to 6 October 2026) read in the one page that answered before the
  fourth block, and October 2026 (73) by the month query before the fifth.
  The month-window code is tested offline; live it has read one month. The
  first Saturday's run, from the Mini's address, is the real test: it asks
  for up to seven months and then the roster, and a normal week afterwards
  needs four requests (three months and the roster). The register is
  asked before the Diputados roster, and a refused register skips the
  roster.
- Members: dataset "Legisladores", resource "Diputados": 2,168 rows, one per
  bloc spell, with HCDN's ID (`HCDN3166`), district, mandate and bloc dates.
  **257 sitting diputados** (one open bloc spell each), in one request.
  Quirk: **the datastore drops accented capitals from bloc names**
  ("UNIN POR LA PATRIA", "INNOVACIN FEDERAL"); the "Composición Actual"
  resource spells them right but carries no ID. Stored as served; a bloc
  name is display text, never a key.
- No `robots.txt` (CKAN answers 500).

### Diputados roll calls: BLOCKED

- **`votaciones.hcdn.gob.ar`**, the only place HCDN has published nominal
  votes since 2019, **never completed a TLS handshake**: from the laptop
  (TCP connects, then nothing for 60 seconds, on 443 and on 80) and from a
  GitHub runner (`_ssl.c:999: The handshake operation timed out`, twice).
  `www.hcdn.gob.ar`, on the same network, answers at once. Whether it is a
  geographic restriction or simply down is not known from here.
- The CKAN datasets "Votaciones Nominales" stop at **período 137 (2019)**;
  a third ("votaciones-nominales") refuses anonymous reads
  (`Authorization Error`).
- The collector knocks once a run (20 seconds) and logs the result in one
  line. A refusal is the known state and **not a gap**, so the weekly does
  not go red every Saturday for a block we already know of. If it ever
  answers, the log says so in capitals.

### Agendas: work, plain HTML (phase 3)

- Senate: `/parlamentario/Agenda/AgendaWeb/<d>,<m>,<yyyy>`, one day per page
  (113 KB), every event (committee meetings, sessions, cultural events).
- Diputados: `www.hcdn.gob.ar/comisiones/agenda/` lists the week's committee
  meetings (11 on 9 October), each with a page giving the room, the
  committee and the subject ("Presupuesto e Inversión destinada a Familias,
  Niñez y Juventudes proyectado para el año 2027").
- **`www.hcdn.gob.ar/robots.txt` disallows a long list of AI crawlers by
  name, including `Claude-Code`, `ClaudeBot` and `anthropic-ai`.** Our
  User-Agent (`CitizenGO-ParlMonitor/1.0`) is not on it and `*` is allowed,
  so reading the agenda would be within the rules as written. Phase 1 does
  not touch that host. Flagged for Christopher (see the list at the end).

## Phase 1: built, 9 October 2026

`tools/ar_rollcalls.py` into `ar_members`, `ar_bills`, `ar_divisions` and
`ar_votes` (schema in `src/ar_store.py`, declared in `db.TABLES`), with
`config/watchlist-ar.yaml` keyed by expediente. Live runs into a scratch
database, not the store:

| | Read | On our ground (watchlist only) |
|---|---|---|
| Senate actas, 2024 to 24 Sept 2026 | 327 | 0 |
| Senate positions | 23,400 | |
| Senate expedientes behind those actas | 102 | |
| Diputados expedientes, 5 June to 6 October 2026 (the rest of the window was refused) | 2,000 | 14 |
| Members: sitting senators / diputados | 72 / 257 | |
| Senators who voted in 2024-2026 (current and former) | 94 | |

The Senate backfill took three runs (a ten-minute time budget stopped the
first after 111 actas; the second read 212 and recorded 10 resets; the third
read the 4 refused actas and nothing else, in 92 seconds; a fourth re-read
the 4 expediente pages still missing a title). A run with nothing new reads
the year's listing, knocks on votaciones and stops.

- **Keys.** An expediente is `<chamber>/<number>-<origin>-<year>` in that
  chamber's own numbering (`dip/5346-D-2026`, `sen/159-PE-2025`). The prefix
  matters: each chamber numbers incoming items itself, so the executive's
  message 159/25 in the Senate and 159/25 in Diputados are different
  documents, and a bill that passes one chamber gets a new number in the
  other. A Senate division is `sen-acta-<id>`, the Senate's own acta ID. A
  member is `sen/<Senate ID>` or `dip/<HCDN ID>`. Titles are never keys.
- **Bloc is stored per vote**, as party is in Canada and the US: 14 blocs in
  the current Senate, and they split and rename often.
- **Classification.** Until `config/taxonomy-es.yaml` exists, the only areas
  stored are the watchlist's. When the file appears it is used
  automatically, and `--reclassify` re-derives every stored row. Text is
  folded (accents and ñ removed) before matching, because HCDN prints older
  titles in capitals without accents ("IDENTIDAD DE GENERO") and newer ones
  with them; the Spanish terms are therefore written unaccented.
- **Votes inherit their expedientes' areas**; `own_areas` keeps the acta
  title's own match apart.
- **Scheduled Mini-first, not yet installed.** `jobs/ar-weekly.sh` (one
  script, two callers), `ops/launchd/net.citizengo.parlmonitor.ar-weekly.plist`
  (Saturdays 03:00 London) and `.github/workflows/ar-weekly.yml` (Saturdays
  03:00 and 05:00 UTC, gated by `mini-check.yml` with job `AR_WEEKLY` and a
  200-minute grace, as Australia's). Saturday 03:00 UTC is midnight in
  Buenos Aires, after the Wednesday and Thursday sessions. The 2024-2025
  Senate backfill is a one-off (`--years 2024 2025 2026`), not part of the
  weekly.
- **Tests:** `tests/test_ar_rollcalls.py`, 28 tests on trimmed real
  fixtures in `tests/fixtures/ar/`, no network.

## Proposed Spanish terms (for approval; NOT generated)

Measured as a scratch list over the data above. Written unaccented and
lower-case (the collector folds the text); all-caps acronyms match
case-sensitively, as in every taxonomy file here. **AR** marks a term that is
Argentina's own (a law number, an Argentine institution or an Argentine
usage) and does not belong in a list shared with Spain and Mexico. Unmarked
terms are general Spanish and should serve all three, subject to a native
reader in each country.

### 1 Abortion
- Tier 1: `aborto*`, `interrupcion voluntaria del embarazo`, `interrupcion
  legal del embarazo`, `IVE` (also Spain), `ILE` (also Mexico), `ley 27.610`
  / `27.610` **AR** (the 2020 abortion law), `por nacer`, `nino por nacer`,
  `persona por nacer`, `derecho a la vida`, `misoprostol`, `mifepristona`,
  `objecion de conciencia`, `consenso de ginebra` (the 2020 Geneva Consensus
  Declaration, which Argentina joined in 2026; six expedientes in four
  months), `provida`, `pro vida`, `dos vidas` and
  `salvemos las dos vidas` **AR** (the movement's own slogan),
  `ley de los 1000 dias`, `plan 1000 dias`, `ley 27.611` **AR**.
- Tier 2: `salud sexual y reproductiva`, `derechos sexuales y reproductivos`,
  `salud reproductiva`, `embarazo no intencional`, `embarazo adolescente`,
  `anticoncep*`, `procreacion responsable`, `muerte perinatal`,
  `duelo perinatal`, `gestante*`.

### 2 Assisted dying
- Tier 1: `eutanasia*`, `suicidio asistido`, `muerte digna`,
  `muerte voluntaria`, `asistencia medica para morir`,
  `prestacion de ayuda para morir` (Spain's statutory phrase), `buena muerte`,
  `terminar con la propia vida` (the title of a 2026 bill).
- Tier 2: `cuidados paliativos`, `directivas anticipadas`, `final de la vida`,
  `fin de vida`, `prevencion del suicidio` (the positive flank, as
  `Suizidprävention` is in German), `derechos del paciente` guarded by morir /
  muerte / eutanasia / propia vida (unguarded it matched the "Día del
  paciente trasplantado").
- Measured and dropped: `paliativ*` (16 false hits, every one the 2024
  "Medidas Fiscales Paliativas" tax package).

### 3 Gender medicine and children
- Tier 1: `bloqueadores de la pubertad`, `bloqueador* puberal*`,
  `bloqueo puberal`, `hormonizacion`, `cirugia* de reasignacion`,
  `reasignacion de sexo`, `reasignacion genital`, `disforia de genero`,
  `destransicion`, `transicion de genero`, `infancias trans`, `ninez trans`,
  `ninas trans`, `ninos trans`, `adolescencias trans`, `decreto 62/2025` **AR**
  (the February 2025 decree restricting treatment of minors under the
  gender identity law).
- Tier 2: `identidad de genero` guarded by menor / nino / infancia /
  adolescent; `tratamiento* hormonal*` guarded the same way.

### 4 Conversion practices
- Tier 1: `terapia* de conversion`, `terapias de reconversion`,
  `practicas de conversion`, `ECOSIEG`.
- Tier 2: `orientacion sexual` guarded by conversion / corregir / terapia.

### 5 Sex-based rights
- Tier 1: `identidad de genero`, `ley 26.743` **AR** (gender identity, 2012),
  `cupo laboral trans`, `cupo travesti` and `travesti*` **AR** (an
  Argentine legal and political usage: Ley 27.636 is the "cupo laboral
  travesti trans"), `transgenero*`, `ley micaela` / `ley 27.499` **AR**
  (compulsory gender training for officials), `lenguaje inclusivo`,
  `lenguaje no sexista`, `lenguaje no binario`, `no binari*`,
  `dni no binario` **AR**, `perspectiva de genero`, `ideologia de genero`,
  `diversidad sexual`, `lgbt*`, `lgtb*`, `disidencias sexuales`.
- Tier 2: `violencia de genero`, `femicidio*`, `feminicidio*` (Mexico's
  usual form), `ley brisa` **AR**, `paridad de genero`,
  `ministerio de las mujeres` **AR**, `igualdad de genero`,
  `transfemicidio*`, `travesticidio*` **AR**, `razones de genero`, `crimen de odio`,
  `crimenes de odio`, `orientacion sexual`, `diversidades`.

### 6 Parental rights and education
- Tier 1: `educacion sexual integral`, `ESI` **AR** (Ley 26.150, the
  compulsory sex-education programme: the single most important Argentine
  term in this area), `ley 26.150` **AR**, `educacion sexual`,
  `patria potestad` (Spain and Mexico; Argentina replaced it in 2015 with)
  `responsabilidad parental` **AR**, `derecho de los padres`,
  `derechos de los padres`, `libertad de ensenanza`,
  `educacion en el hogar`, `homeschooling`, `adoctrinamiento`.
- Tier 2: `contenidos curriculares` guarded by genero / sexual / padres;
  `consentimiento informado`; `redes sociales` guarded by menores / ninos /
  adolescentes / edad; `grooming`; `celulares en las escuelas`;
  `uso de celulares`; `verificacion de edad`; `mayoria digital` (the
  proposed minimum age for social media); `entornos digitales` guarded by
  ninos / adolescentes / menores.

### 7 Free speech and online safety
- Tier 1: `libertad de expresion`, `libertad de prensa`, `censura*` with a
  veto on `mocion de censura` (a no-confidence motion),
  `discurso de odio`, `discursos de odio`, `desinformacion`,
  `noticias falsas`, `fake news`, `negacionismo`, `nodio` **AR** (the 2020
  state disinformation observatory).
- Tier 2: `delitos de odio`, `plataformas digitales` guarded by contenidos /
  menores / odio / desinformacion / moderacion / censura, `ciberpatrullaje`,
  `INADI` **AR** (the anti-discrimination institute, dissolved in 2024),
  `moderacion de contenidos`. Measured and dropped: `inteligencia
  artificial` (12 register hits) and `datos personales` (5), none ours.

### 8 Freedom of religion
- Tier 1: `libertad religiosa`, `libertad de culto`, `libertad de cultos`,
  `libertad de conciencia`, `objecion de conciencia`, `ley de cultos`,
  `registro nacional de cultos` **AR**, `sostenimiento del culto` and
  `ley 21.950` **AR**, `iglesia catolica`, `culto catolico`,
  `persecucion religiosa`, `cristianos perseguidos`.
- Tier 2: `entidades religiosas`, `confesiones religiosas`, `iglesia`,
  `iglesias evangelicas`, `iglesias cristianas`, `evangelic*`,
  `antisemitismo`, `islamofobia`, `interreligios*`, `capellan*`, `laicidad`, `estado laico`.
- Measured and changed: `iglesia*` as a stem matched **Fernando Iglesias**,
  a deputy nominated as ambassador to the EU (acta of 2026). `Iglesias` is a
  common surname; the stem is out, the singular and two phrases are in.

### 9 Marriage and family
- Tier 1: `matrimonio igualitario`, `matrimonio entre personas del mismo
  sexo`, `ley 26.618` **AR**, `union convivencial` and
  `uniones convivenciales` **AR** (the 2015 Civil Code's cohabitation
  status), `ley de familia`, `politica familiar`, `proteccion de la familia`,
  `familia numerosa`, `familias numerosas`, `matrimonio infantil`,
  `matrimonio de menores`.
- Tier 2: `asignacion universal por hijo` **AR**, `licencia por maternidad`,
  `licencia por paternidad`, `licencias parentales`, `adopcion` guarded by
  nino / menores / hijos / adoptantes / guarda (unguarded it is "adopción de
  medidas"), `divorcio`, `cuota alimentaria` **AR**, `impedimento de
  contacto`, `falsas denuncias`.

### 10 Surrogacy and embryology
- Tier 1: `gestacion por sustitucion`, `gestacion subrogada`,
  `maternidad subrogada`, `subrogacion de vientre`, `alquiler de vientre*`,
  `vientre de alquiler`, `vientres de alquiler`,
  `reproduccion medicamente asistida`, `fertilizacion asistida`,
  `ley 26.862` **AR**, `embrion*`, `criopreserv*`, `clonacion`.
- Tier 2: `fertilizacion in vitro`, `reproduccion asistida`,
  `donacion de gametos`, `donacion de ovulos`, `banco de semen`,
  `edicion genetica`, `celulas madre`.

### 11 Migration (collated, never campaigned)
- Tier 1: `ley de migraciones`, `ley 25.871` **AR**, `decreto 366/2025` **AR**,
  `expulsion de extranjeros`. Tier 2: `migrante*`, `inmigra*`, `refugiad*`,
  `asilo`.

### 12 Prostitution and trafficking
- Tier 1: `trata de personas`, `explotacion sexual`, `prostitucion`,
  `proxenetismo`, `trabajo sexual`, `trabajadoras sexuales`,
  `abolicion de la prostitucion`, `ley 26.364` / `ley 26.842` **AR**,
  `pornografia*`, `abuso sexual infantil`, `comercializacion de menores`,
  `venta de ninos`, `compraventa de ninos`, `compraventa de ninas`,
  `trata de ninos`, `grooming`.
- Tier 2: `oferta sexual`, `rufianismo`, `integridad sexual` (the Penal
  Code's chapter on sexual offences), `acoso sexual`, `abuso sexual`,
  `violencia sexual`, `contenido sexual`.
- Measured and added: `comercializacion de menores`, the only tier-1 match
  in three years of Senate roll calls (the 2024 Penal Code offence of
  abducting or selling children). Measured and dropped: bare `trata` ("se
  trata de", in every other title).

### 13 Organ donation
- Tier 1: `donacion de organos`, `trasplante de organos`, `ley justina` /
  `ley 27.447` **AR**, `INCUCAI` **AR**, `donante presunto`,
  `donante presunta`. Tier 2: `trasplante*`, `ablacion de organos`,
  `donacion de sangre`, `donacion de medula`.

### What the terms found in the Diputados register

The 2,000 most recent Diputados expedientes (5 June to 6 October 2026: 959
resolutions, 621 bills, 408 declarations, 12 executive messages), with the
list as printed above:

| Area | Any tier | Tier 1 | What it found |
|---|---|---|---|
| 1 Abortion | 8 | 8 | 6 on the Geneva Consensus Declaration (5 against, 1 for); 2 on adoption declared during pregnancy |
| 2 Assisted dying | 8 | 2 | 2 euthanasia bills (2721 and 2907-D-2026); 6 on suicide prevention (tier 2, the positive flank) |
| 4 Conversion practices | 1 | 1 | an ecumenical statement against conversion therapy |
| 5 Sex-based rights | 8 | 5 | LGBTIQ+ pride and violence, gender-violence plans |
| 6 Parental rights, education | 11 | 4 | ESI (3), responsabilidad parental, children on social media and "entornos digitales" (6) |
| 7 Free speech | 5 | 5 | press freedom at the Casa Rosada (3), a researcher's censorship, the free-expression committee |
| 8 Religion | 5 | 0 | antisemitism (3), Evangelical holidays, the Vatican's interreligious envoy |
| 9 Marriage, family | 1 | 1 | the anniversary of the same-sex marriage law |
| 12 Trafficking, prostitution | 13 | 7 | trafficking penalties, the sale of children, banning sexual-exploitation venues, a sex-workers' day; sexual-offence prescription (tier 2) |
| **Expedientes on our ground** | **59** | **32** | |

Bills (LEY) only: 28 of 621 at any tier, 11 at tier 1. The English taxonomy
found 3 of the 2,000 (all `LGBTIQ`), and 0 of the 621 bills.

Measured and changed on the register: `moción de censura` (a no-confidence
motion against the Chief of Cabinet, three expedientes) is vetoed from
`censura*`; `inteligencia artificial` and `datos personales` (12 and 5 hits,
none ours) are out of area 7, and `plataformas digitales` is guarded;
`derechos del paciente` is guarded (it matched the "Día del paciente
trasplantado"); `consenso de ginebra`, `terminar con la propia vida`,
`compraventa de ninos/ninas`, `mayoria digital`, `entornos digitales` and
`razones de genero` were added after reading what the list missed. Some
register titles carry HTML entities (`20&deg; ANIVERSARIO`); the collector
unescapes them.

## Phase plan

1. **Phase 1 (built, this branch).** Senate roll calls and positions,
   the Senate expedientes they name, the Diputados register, both rosters.
   Watchlist-only areas until the Spanish file is approved.
2. **Phase 2 (after approval).** Generate `config/taxonomy-es.yaml` from an
   approved `docs/keyword-taxonomy-es.md`, shared with Spain and Mexico
   (Argentine terms in their own marked block), and `--reclassify`. Add the
   full Senate register through the `fechaMesa` search (cookie-aware POST).
   A US-style judge (`ar_triage`) once there is something to score.
3. **Phase 3.** Agendas of both chambers (the What's On equivalent), the
   Diputados movimientos and dictámenes datasets (committee stage, already
   on CKAN), and an edition, `tools/ar_monitor.py`, DMed to Christopher.
4. **Diputados roll calls** whenever `votaciones.hcdn.gob.ar` can be reached
   (see the list below). Until then Diputados has a register but no 5CA.
5. **Provincial legislatures, later.** 24 jurisdictions: 8 bicameral
   (Buenos Aires, Catamarca, Corrientes, Entre Ríos, Mendoza, Salta,
   San Luis, Santa Fe) and 16 unicameral (Ciudad Autónoma de Buenos Aires,
   Chaco, Chubut, Córdoba, Formosa, Jujuy, La Pampa, La Rioja, Misiones,
   Neuquén, Río Negro, San Juan, Santa Cruz, Santiago del Estero,
   Tierra del Fuego, Tucumán). Not probed.

## Shared files touched (for the merge of the 13 country branches)

- `src/db.py`: four `ar_*` names in `TABLES` and two lines in `init_db`
  calling `ar_store.ensure_schema` (8 lines).
- `tools/coverage.py`: `Argentina weekly` in `PIPELINES`, three `ar_*` rows in
  `FEEDS`, one `PIPELINE_FEEDS` entry and one `AWAITING_FIRST_RUN` entry.
- `.github/workflows/alert.yml`: one line, `"Argentina weekly"`.
- Nothing else shared. `config/taxonomy.yaml`, `src/http.py`,
  `src/filter.py` and `docs/mac-mini.md` are untouched (the Mini job is
  recorded here instead; move it into the runner's job list when the
  branches meet).

## Waiting on Chris

1. **Approve, cut or extend the proposed Spanish terms** above, ideally with
   an Argentine reader, and say whether the unaccented convention suits
   Spain and Mexico too. Nothing is generated until then.
2. **Diputados roll calls.** `votaciones.hcdn.gob.ar` refuses London and
   GitHub alike. Options, your call: (a) try it once from the Mac Mini;
   (b) ask a CitizenGO contact in Argentina to open it, which tells us
   whether it is geographic; (c) write to HCDN's open-data office asking
   them to resume the "Votaciones Nominales" dataset (it stopped in 2019).
   Nothing has been routed through another country's network.
3. **datos.hcdn.gob.ar turns clients away** after a hanging query (or past
   some undocumented rate). The collector is built to ask little and stop at
   the first refusal. If you would rather ask HCDN for a documented limit or
   a working bulk file, that is a letter, not code.
4. **The `www.hcdn.gob.ar` robots.txt** names AI crawlers (including
   Claude-Code) and disallows them. Our monitor's UA is not on the list and
   phase 1 does not use that host; phase 3's Diputados agenda would. Say
   whether you are content for the monitor to read it.
5. **The watchlist** (`config/watchlist-ar.yaml`) carries 14 Diputados
   expedientes found while scoping (euthanasia, the Geneva Consensus,
   conversion therapy, ESI, children online, trafficking and sex work);
   please check them. Until the Spanish list is approved they are the only
   areas the Argentine store holds.
6. **The slot** (Saturdays 03:00 London on the Mini, 03:00 and 05:00 UTC on
   GitHub) and, after the merge, installing the plist on the Mini; set no
   `MINI_LAST_AR_WEEKLY` until then.
7. **The first run's Senate window.** The weekly reads the current year. The
   2024 and 2025 actas (188, none on our ground) are a one-off; say if you
   want them in the store.
8. **Ley 13.640 lapse rule** (bills lapse after two parliamentary years):
   to be confirmed by an Argentine contact before any board relies on it.
