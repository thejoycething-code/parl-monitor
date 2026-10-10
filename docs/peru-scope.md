# Peru: scoping the Congress monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (the
CitizenGO User-Agent, throttled, every response archived under
`data/raw/2026-10-09/`). Every number below was measured, not estimated.
National Congress only; the regional councils are a later decision.

## Decisions already taken (Chris, 9 October 2026)

- **Own edition**, delivered to Chris alone (Slack DM), as the US is.
- **Shared taxonomy concept, Spanish terms.** `config/taxonomy.yaml` and the
  other taxonomy files are not touched. The Spanish term list is PROPOSED
  below; a `config/taxonomy-es.yaml` is generated only after Chris approves
  it. Spain, Argentina, Mexico, Colombia and Chile are being scoped in
  parallel, so the list marks which terms are Peru-specific.
- **National Congress first**, regional councils later.
- **Mac Mini first, GitHub Actions as the backup**, as for Australia. No new
  paid services. Nothing is ever posted publicly.

## The findings that shape everything

1. **The English taxonomy is blind to Spanish.** Run over every proyecto
   title of the 2021-2026 and 2026-2031 Congresses (15,436 titles),
   `config/taxonomy.yaml` placed **one** on our ground: a sterilisation bill
   caught by the English word "coercion" (14761/2025-CR). The Germany lesson
   again: until `taxonomy-es` exists, a Peru monitor collects everything and
   sees nothing.
2. **There is an open, keyless JSON API for proyectos de ley**, the one the
   Congress's own Sistema de Proyectos de Ley front end calls. It covers
   both new chambers and the old single chamber back to 2021 at least.
3. **The signed vote records are scans, but the provisional copies are not.**
   Every signed "visto bueno" record is a Lexmark scan with no text layer.
   The provisional "copia informativa" each chamber uploads first is a
   digital export from the electronic voting system: pypdf reads it, with
   every member's position, bancada, the record's own totals and a unique
   record id. Both chambers' media libraries are open through the WordPress
   REST API, so the provisional copies stay findable after the session page
   has swapped them for the scans.
4. **Peru is bicameral again.** The 2026-2031 Congress, installed on
   27 July 2026, has a Senado of 60 and a Camara de Diputados of 130. Every
   source already reflects it: separate sites (`senado.congreso.gob.pe`,
   `diputados.congreso.gob.pe`), separate proyecto numbering
   (`00013-2026-2031-S`, `00553-2026-2031-CD`) and a third series for the
   Congress as a whole (`00006-2026-2031-CR`, budget and joint matters).
   `www.senado.gob.pe` and `www.diputados.gob.pe` do not resolve.

## Sources

### Proyectos de ley: works today, open, no key

`POST https://api.congreso.gob.pe/spley-portal-service/proyecto-ley/lista-con-filtro`
with a JSON filter body (`perParId`, `codTipoParl`, `pageSize`, `rowStart`,
everything else null). Found in the front end's bundle
(`wb2server.congreso.gob.pe/spley-portal/main-es2015...js`).

| Period, chamber code | Proyectos | Dates presented |
|---|---|---|
| 2026-2031, `D` (Diputados) | 553 | 4 Aug to 7 Oct 2026 |
| 2026-2031, `S` (Senado) | 13 | 11 Aug to 7 Oct 2026 |
| 2026-2031, `C` (Congress as a whole) | 6 | 14 Aug to 2 Oct 2026 |
| 2021-2026, `C` (old single chamber) | 14,864 | 3 Aug 2021 to 22 Jul 2026 |

- Each row: `proyectoLey` (the number string, our key), `pleyNum`,
  `desEstado` (status in the Congress's own words), `fecPresentacion`,
  `titulo`, `desProponente`, `autores` (semicolon list of names).
- **Paging is by row offset** (`rowStart`), and **1,000 rows a page is
  accepted**: the whole old Congress is 15 requests. Members, all three
  current lists and the old Congress together took 59 seconds.
- `GET .../periodo-parlamentario` lists the periods; the 2026-2031 one runs
  27 July 2026 to 26 July 2031.
- **Quirk: re-filed proyectos.** Under the new Reglamento a proyecto of the
  old Congress can be re-filed ("ACTUALIZACION DE CONFORMIDAD CON LA SEGUNDA
  DISPOSICION COMPLEMENTARIA TRANSITORIA ... (ANTES PL 01330/2021-CR)"). It
  is a new proyecto with a new number; the old number sits in its title.
- **Quirk: titles drop accents and carry typos** ("RECONOCIMEINTO"). The
  collector folds accents on both text and terms before matching.
- **Not used: the expediente (detail) endpoint.** `GET .../expediente/{a}/{b}`
  takes the period and number AES-encrypted with a key shipped in the
  public JavaScript. That is an obfuscation the Congress chose; working
  round it is Chris's call (see Waiting on Chris), so phase 1 classifies on
  titles only. The list carries no summary, committee or vote link.
- No rate-limit headers or refusals seen at the default 0.2 s throttle.

### Members: works today, open, no key

Each chamber's WordPress REST API:
`/wp-json/wp/v2/senador?per_page=100` (60 records) and
`/wp-json/wp/v2/diputado?per_page=100&page=1..2` (130; page 3 answers
HTTP 400, which is WordPress's "past the last page"). The bancada, party,
electoral district, period and status ride in each post's `class_list` as
taxonomy slugs (`grupo_parlamentario-fuerza-popular`). Measured:

| Bancada | Senado | Diputados |
|---|---|---|
| Fuerza Popular | 22 | 41 |
| Juntos por el Peru | 14 | 32 |
| Partido del Buen Gobierno | 7 | 18 |
| Renovacion Popular | 8 | 15 |
| Partido Civico Obras | 5 | 14 |
| Ahora Nacion | 4 | 10 |

Status: 55 senators and 127 deputies "en ejercicio", 2 deputies "electo",
6 with no status slug. Names are 'Surname Surname, Given' as the site prints
them; the key is `<chamber>/<slug>`.

### Plenary votes: works, PDF, with caveats

Found through `/wp-json/wp/v2/media?search=votaci` and `?search=asistencia`
on each chamber site (open, no key). Measured on 9 October 2026:

| | Senado | Diputados |
|---|---|---|
| Vote/attendance PDFs in the media library | 31 | 24 |
| with a text layer | 17 | 14 |
| printer scans (Lexmark, no text) | 14 | 10 |
| votes parsed | 34 | 17 |
| votes whose positions add up to the record's totals | 32 | 17 |

- **51 votes, 4,248 member positions**, 5 August to 7 October 2026. 4,227
  positions resolved to a member on the first pass; the bancada-scoped
  fallback added since resolves one more deputy whose site name differs
  from the record's.
- Every vote page carries a **record id** ("41010 - 58450 - 10009 - S"), the
  date and time, the Asunto (subject), each member as bancada code, name
  cut to the column ("JAUREGUI MARTINEZ DE"), and position: SI, NO, Abst.,
  AUS, SinRes, LO/LE/LP/LV (official, sick, personal, travel leave), SUS,
  and *** for the presiding member. Then the totals and a group table.
- **Validation is built in.** The collector checks the parsed positions
  against the printed totals and against the group table, and records a gap
  when neither adds up. Two Senate votes of 30 September fail: pypdf put
  one senator's name lines out of order, so 59 of 60 positions parse. The
  record itself can disagree with itself: the Diputados record of 5 August
  prints "A FAVOR 119" over a group table and 130 rows that both give 121.
- **Sessions with no digital record** (scans only): the installation
  sessions of 24 to 28 July in both chambers, the Diputados of 13 August.
  The Senate's provisional copy of 5 August uses an older layout (a numbered
  two-column table) that the parser does not read. Diputados 17 September
  and 20 August: attendance only.
- **Oral votes are missing from the provisional copy** ("SIN LOS VOTOS
  ORALES"); the signed record adds a note ("deja constancia del voto a favor
  de ..."). The collector keeps the positions as the electronic record
  gives them and strips the note from the subject.
- The Senate's media library holds at least one Diputados record; the
  record id's suffix (S or D), not the site, decides the chamber.
- **Quirk:** the session page links the scan once it exists and drops the
  provisional copy, so the media library, not the page, is the source.

### Agenda: reachable, PDF, not built

Each chamber's "Sesiones del Pleno" page links an agenda PDF per session
(`AGENDA-PLENO-SENADO-30-09-2026-V3.pdf`, `AGENDA-PLENO-DIPUTADOS-6-10-2026-1.pdf`).
Both are Word exports with a text layer (4 and 18 pages). This is the
week-ahead source; phase 2.

### datosabiertos.gob.pe: nothing for Congress

The national open data portal's CKAN API answers 404
(`/api/3/action/package_search`). Its site search for "congreso",
"votaciones pleno" and "proyectos de ley" returns election results (ONPE),
infrastructure projects and meteorology: no proyectos, no votes, no members.

### Old single-chamber votes (2021-2026): not found

`www.congreso.gob.pe` is now a WordPress front for the two chambers; the old
`/AsistenciasVotacionesPleno/` path answers 404. The old Congress's votes are
out of scope for phase 1 (its proyectos are in the API, above).

## How much touches CitizenGO's ground

With the proposed Spanish terms below (a measurement draft, not config),
over proyecto titles:

| Corpus | Titles | On our ground (not migration) | Tier 1 |
|---|---|---|---|
| 2021-2026 Congress | 14,864 | 134 (0.9%) | 77 |
| 2026-2031 so far (10 weeks) | 572 | 8 | 4 |

By area, 2021-2026: marriage and family 28, parental rights and education
20, prostitution and trafficking 18, abortion 17, free speech 14, organ
donation 13, religious freedom 10, sex-based rights 8, surrogacy and
embryology 6, assisted dying 4. Representative hits: 00785/2021-CR (Ley que
reconoce derechos al concebido, now Ley 31935), 13894/2025-CR (removes the
enfoque de genero from law and policy), 09174/2024-CR (removes "educacion
sexual integral" from the curriculum), 05819/2023-CR (matrimonio
igualitario), 02194/2021-CR (Ley de identidad de genero), 13073/2025-CR
(bans surrogacy), 07908/2023-CR (eutanasia), 12475/2025-CR (regulates
"trabajo sexual"). In the new Congress: an age floor for children's social
media accounts (00498-2026-2031-CD), a Saturday rest day for members of a
religious confession (00281-2026-2031-CD), a ban on child "uniones de hecho"
(00143-2026-2031-CD) and three trafficking bills.

**Votes: 0 of 51 on our ground.** The new Congress's first ten weeks were
commission rosters (7), states of emergency (8), special-commission motions
(25) and delegated powers (9). Thirteen votes name a proyecto, which the
collector resolves to its key (00098-2026-2031-CD five times: the
delegation of powers on security), so a vote inherits its proyecto's areas.

Noise measured and removed from the draft: "curriculo nacional" alone (29
hits, nearly all "add subject X to the national curriculum") is now a guarded
tier-2 term; "paridad", "violencia sexual", "clonacion" (licence plates),
"templos" (heritage restoration) and "enfermedad terminal" (pensions) were
dropped.

## Proposed Spanish terms (for Chris's approval)

Written unaccented because the collector folds accents on both sides;
`taxonomy-es` can carry the accents for readability. **PE** marks a term
that is Peru-specific (a Peruvian law, case, institution or movement name);
everything else is shared Spanish for the Spain, Argentina, Mexico,
Colombia and Chile scopes to reuse. `*` is the stem wildcard.

**1 Abortion.** Tier 1: aborto*, interrupcion voluntaria del embarazo,
interrupcion legal del embarazo, interrupcion del embarazo, aborto
terapeutico (PE: the 2014 national protocol; Argentina and Mexico say ILE),
concebido* (PE: Constitution art. 2.1 and Civil Code art. 1, "el concebido
es sujeto de derecho"), derechos del concebido (PE: Ley 31935), por nacer,
no nacido*, nino por nacer (PE and Argentina: 25 March, Dia del Nino por
Nacer), vida desde la concepcion, desde la concepcion, misoprostol,
mifepristona, anticoncepcion oral de emergencia (PE: the AOE litigation),
pildora del dia siguiente, objecion de conciencia. Tier 2: salud sexual y
reproductiva, derechos sexuales y reproductivos, derechos reproductivos,
embarazo adolescente, embarazo infantil, ninas madres (PE: "Ninas, no
madres"), adopcion desde el vientre materno, embarazo* no planead*,
embarazo* no desead*, duelo gestacional, madre gestante, gestantes,
planificacion familiar, anticoncepcion, anticonceptivo* (contraception is a
life issue, as decided for the US).

**2 Assisted dying.** Tier 1: eutanasia, muerte digna, muerte asistida,
suicidio asistido, suicidio medicamente asistido, homicidio piadoso (PE:
Penal Code art. 112), Ana Estrada (PE: the 2021 euthanasia ruling). Tier 2:
cuidados paliativos, voluntades anticipadas, testamento vital, limitacion
del esfuerzo terapeutico.

**3 Gender medicine and children.** Tier 1: bloqueadores de la pubertad,
bloqueadores puberales, hormonizacion, terapia hormonal cruzada, transicion
de genero, reasignacion de sexo, cambio de sexo, afirmacion de genero,
disforia de genero, menores trans. Tier 2: infancias trans, ninez trans.

**4 Conversion practices.** Tier 1: terapia* de conversion, ECOSIEG,
esfuerzos de cambio de orientacion sexual. Tier 2: terapias reparativas.

**5 Sex-based rights and gender ideology.** Tier 1: identidad de genero,
ideologia de genero, enfoque de genero (PE: the centre of the 2017-2019
curriculum and Politica Nacional de Igualdad de Genero fights), ley de
identidad de genero, personas trans, transgenero*, transexual*, lenguaje
inclusivo, LGBT*, LGTB*, LGBTI*, LGTBI*. Tier 2: igualdad de genero,
orientacion sexual, diversidad sexual, politica nacional de igualdad de
genero (PE), transversalizacion del enfoque de genero (PE). "Genero" alone
is not a term: it matches literary genres and the gender pay gap.

**6 Parental rights and education.** Tier 1: Con mis hijos no te metas
(PE: the 2016 movement, since copied in the region), educacion sexual
integral, derecho preferente de los padres, derecho de los padres, patria
potestad, educacion en casa, homeschooling, pin parental (Spain). Tier 2:
curriculo nacional only with sexual*, genero, familia, valores, religio*,
moral* or padres in the same title (PE: the Curriculo Nacional de la
Educacion Basica), padres de familia, APAFA (PE: parents' associations),
textos escolares, materiales educativos, curricul* escolar, libertad de
ensenanza, educacion sexual, lineamientos de educacion sexual.

**7 Free speech and online safety.** Tier 1: libertad de expresion, discurso
de odio, delitos de odio, incitacion al odio, censura previa. Tier 2:
libertad de prensa, libertad de informacion, desinformacion, noticias
falsas, verificacion de edad, proteccion de menores en internet, ciberacoso,
redes sociales (best guarded with ninos/menores/adolescentes).

**8 Freedom of religion.** Tier 1: libertad religiosa, libertad de
conciencia, libertad de culto, Ley de Libertad e Igualdad Religiosa (PE:
Ley 29635), igualdad religiosa, entidades religiosas, confesion* religiosa*,
educacion religiosa, simbolos religiosos. Tier 2: Iglesia Catolica, Santa
Sede, Concordato (PE: the 1980 agreement with the Holy See), lugares de
culto, capellan*.

**9 Marriage and family.** Tier 1: matrimonio igualitario, matrimonio entre
personas del mismo sexo, union civil, uniones civiles, union solidaria (PE:
the 2013 bill), patrimonio compartido (PE), adopcion homoparental,
fortalecimiento de la familia (PE: Ley 28542), Ministerio de la Familia (PE:
the proposals to rename the MIMP). Tier 2: union de hecho, uniones de hecho
(PE: Civil Code art. 326), divorcio, proteccion de la familia, familia
natural, matrimonio.

**10 Surrogacy and embryology.** Tier 1: gestacion subrogada, maternidad
subrogada, vientre* de alquiler, reproduccion humana asistida, tecnicas de
reproduccion asistida, TERAS (PE), fecundacion in vitro, clonacion humana.
Tier 2: reproduccion asistida, embrion*, banco de ovulos, donacion de
gametos.

**11 Migration (collated, never campaigned).** Tier 1: migracion,
migraciones, migrante*, extranjeros, refugiado*, Superintendencia Nacional
de Migraciones (PE). Tier 2: calidad migratoria, expulsion de extranjeros.

**12 Prostitution and trafficking.** Tier 1: trata de personas, prostitucion,
explotacion sexual, proxenetismo, pornografia*, pornografia infantil,
material de abuso sexual infantil, trabajo sexual. Tier 2: explotacion
sexual comercial, turismo sexual.

**13 Organ donation.** Tier 1: donacion de organos, trasplante de organos,
donante* de organos, trafico de organos, donacion presunta. Tier 2:
trasplante*, tejidos humanos.

## What was built (phase 1, 9 October 2026)

- `tools/pe_rollcalls.py`: members, proyectos (current period every week;
  `--period 2021` adds the old Congress), and every vote record PDF not
  read before. `--reclassify` re-derives areas offline. Exit 3 means it
  stored what it could and recorded gaps.
- `src/pe_store.py`: `pe_members`, `pe_bills`, `pe_divisions`, `pe_votes`,
  `pe_vote_files`, declared in `db.TABLES` and created by `db.init_db`.
- `config/watchlist-pe.yaml`: a three-entry draft, applied by proyecto key,
  never by title.
- Classification: `config/taxonomy-es.yaml` when it exists, otherwise the
  English `config/taxonomy.yaml` (blind, so the plumbing runs). When
  `taxonomy-es` lands, dispatch the workflow with "reclassify".
- Tests: `tests/test_pe_rollcalls.py` (25 tests) on fixtures in
  `tests/fixtures/pe/`: pypdf's own text of seven real vote pages, both
  chambers' member lists, a proyecto list page, a media listing, and a
  test-only Spanish term file (not the proposed taxonomy).
- The weekly job, Mac Mini first: `jobs/pe-weekly.sh` (the
  `jobs/au-weekly.sh` pattern, `PE_PUBLISH=false` under GitHub),
  `ops/launchd/net.citizengo.parlmonitor.pe-weekly.plist` (Saturdays 16:00
  London) and `.github/workflows/pe-weekly.yml` (Saturdays 17:00 and 20:00
  UTC, gated by `mini-check.yml` with job `PE_WEEKLY`, grace 330 minutes).
  It needs `pypdf==6.14.2`, pinned as in `prov-weekly.yml`. **It runs on
  GitHub only once merged to main**: GitHub schedules from the default
  branch.

Full suite on 9 October 2026, in this worktree: 3,310 tests, 74 failing,
every one for want of the gitignored raw archive (`data/raw/2026-08-01/` and
other day folders) or a working-copy store, neither of which a fresh worktree
has. With main's frozen 2026-08-01 fixtures linked in, all but the 10 tests
that glob other day folders pass. The Peru tests and the structural tests on
the shared files (`test_coverage`, `test_db`, `test_mini_check`,
`test_vote_tracker_display`) pass: 324 tests.

A first full run (members, both periods' proyectos, all 55 vote files) took
about six minutes from the laptop, into a scratch database, not the store.
Vote files with a text layer are archived; scans (1 to 14 MB each, nothing
to read) are not, and their URL in `pe_vote_files` is the provenance.

### Edits to shared files (for the merge of the country branches)

- `src/db.py`: five `pe_*` names in `TABLES`; two lines in `init_db` calling
  `pe_store.ensure_schema`.
- `tools/coverage.py`: "Peru weekly" in `PIPELINES`, `PIPELINE_FEEDS` and
  `AWAITING_FIRST_RUN`; three `pe_*` rows in `FEEDS`.
- `.github/workflows/alert.yml`: "Peru weekly" in the watched workflow list.

Nothing else outside Peru's own files changed. `docs/mac-mini.md` is not
edited; its job table needs a row for `pe-weekly` (Saturdays 16:00, backup
17:00/20:00 UTC, `MINI_LAST_PE_WEEKLY`, grace 330) when this merges.

## Phase plan

1. **Phase 1 (built):** members, proyectos, plenary votes from the
   provisional records, Spanish classification once approved.
2. **Phase 1b:** proyecto detail (summary, committee, status history,
   linked dictamenes) from the dictamen list (`.../dictamen/lista-con-filtro`,
   not probed). The encrypted expediente endpoint is out (PE2 reversed,
   10 October 2026).
3. **Phase 2:** the week ahead from the agenda PDFs; committee agendas;
   the Senate's older provisional layout (5 August); OCR of scan-only
   sessions only if Chris wants them (it would need a new dependency).
4. **Phase 3:** the Diario de los Debates (debate packs) and the Peru 5CA
   (votes plus authorship: `autores` names every co-signatory).
5. **Later:** the 25 regional councils, by block.

## Dates that matter

- The first ordinary legislature of 2026-2027 runs to mid-December; the
  Comision Permanente sits in the recess.
- Plenaries are Tuesday to Thursday, often into the early hours (a
  Diputados vote at 21:42 Lima time on 6 October). Hence the Saturday job.

## Waiting on Chris

1. **Approve the Spanish term list** above (and the Peru-specific flags), so
   `config/taxonomy-es.yaml` can be generated. Until then the edition is
   blind. Coordinate with the Spain, Argentina, Mexico, Colombia and Chile
   scopes: one shared `taxonomy-es` or a per-country file?
2. **The expediente endpoint.** Answered: no (PE2 reversed, 10 October
   2026). It stays unbuilt.
3. **Review `config/watchlist-pe.yaml`** (three draft entries): ideally with
   someone who campaigns in Peru.
4. **Install the Mini job**: copy the plist to `~/Library/LaunchAgents` and
   bootstrap it, after the merge to main; add the `docs/mac-mini.md` row.
5. **Merge to main** when ready: the weekly workflow is inert until then.
6. **Scan-only sessions**: accept the loss (installation week, Diputados
   13 August), or approve an OCR step later?
7. **Regional councils**: which first, and when.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (PE1) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.

Later phases and items for Chris (not built at the merge):

- Not built: the expediente endpoint (PE2, reversed on 10 October 2026). Its identifiers are AES-encrypted with a key in the public front end; Chris decided to leave it out, so bill detail stays at what the list endpoint gives.
- Phase: regional councils (PE4).
- Phase (X7): OCR for scan-only sessions. Designed and wired 10 October 2026 (`tools/pe_ocr.py`, see below); waits for Tesseract on the Mini.

## Parity work, set B (10 October 2026, branch `parity-phases-b`)

- **X8, built:** `tools/pe_courts.py`, a step in `pe-weekly`: the Tribunal
  Constitucional's press notes (www.tc.gob.pe/institucional/notas-de-prensa/,
  keyless HTML; its REST API exposes no posts), at robots.txt's
  `Crawl-delay: 30`. Weekly: the listing's first page (more only while all
  are new), and a note's own page only when its headline reports a ruling
  or a hearing or its words match our ground, at most six. Kinds: `ruling`,
  `hearing`, or `press` (lectures, book fairs, visits: stored, never shown).
  The RSS feed holds the whole archive (4,378 notes back to 2001, 15 MB): read
  once by the hand-run backfill. Measured on it: 411 ruling notes (41 on our
  ground), 683 hearing notes (14), 3,284 institutional (never shown); the
  rulings on our ground include the crucifix and Bible in courts (2011),
  the minimum-membership rule for religious bodies (2021) and the same-sex
  marriage and surrogacy hearings. The sentencias themselves are not read:
  the Tribunal's jurisprudence search was not probed for an open listing.
- **X7, wired behind a guard:** `tools/pe_ocr.py`, a step in `pe-weekly`
  after the court: with Tesseract on the Mini it reads up to three scan-only
  vote records a run (`pe_vote_files.text_layer = 0`) into `pe_vote_ocr`;
  without it, one "[skip]" line. It parses no positions (src/ocr.py).

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/pe_stance.yaml` holds 2 bill direction(s) (Claude's drafts from the watchlist) and 0 vote reading(s): 0 with proposed values, 0 procedural, 0 need reading, 0 confirmed. Guide: `docs/5ca-pe-readings.md`; confirm with `python3 tools/country_5ca.py --cc pe --sign-from-doc --by NAME`. Sheets (`data/5ca/pe-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for Peru (`config/stance_signers.yaml`). No qualifying vote in any store yet (the scans were lost; phase 1 holds few votes on our ground).
