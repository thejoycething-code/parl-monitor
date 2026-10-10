# Dominican Republic: scoping the Congress monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (the
CitizenGO User-Agent, throttled, every response archived under
`data/raw/2026-10-09/`). Every number below was measured, not estimated.
The National Congress only: the country is unitary, so there are no
regional legislatures to add later (municipal councils are out of scope).

## Decisions already taken (Chris, 9 October 2026)

- **Own edition**, delivered to Chris alone (Slack DM), as the US is.
- **Shared taxonomy concept, Spanish terms.** `config/taxonomy.yaml` and the
  other taxonomy files are not touched. The Spanish term list is PROPOSED
  below; a `taxonomy-es` file is generated only after Chris approves it.
  Spain, Argentina, Mexico, Colombia, Chile, Peru and the Central American
  countries are being scoped in parallel, so the list marks which terms are
  Dominican-specific (**DO**).
- **National Congress first.** Mac Mini first, GitHub Actions as the
  backup. No new paid services. Nothing is ever posted publicly.

## The findings that shape everything

1. **The English taxonomy is blind to Spanish.** Over every iniciativa
   title of the 2024-2028 and 2020-2024 periods (17,962 titles),
   `config/taxonomy.yaml` placed **two** on any area, both by accident of
   spelling: a bill against "la sharía" and mosque building (area 9, via
   "sharia") and a victims' protection system caught by "coercion" (area
   2). Zero in 2020-2024. The Germany lesson again: until a Spanish list
   exists, a Dominican monitor collects everything and sees nothing.
2. **The Chamber of Deputies has an open, keyless JSON API** behind its
   "SIL Ciudadano" (Sistema de Informacion Legislativa) front end, with
   iniciativas, sessions, **every recorded vote and every deputy's
   position**, back to the 2020-2024 period. Phase 1 is built on it.
3. **The Senate publishes no per-senator votes.** Its "Votaciones
   Electronicas" page is an empty file category; its actas (session
   minutes, PDF with a text layer) give each electronic vote's totals only
   ("20 votos a favor, 20 senadores presentes") and say the vote sheet is
   annexed, but the annex is not in the published file. The newest acta is
   of 18 December 2025, posted 16 March 2026. Its iniciativas live in a
   2006 login-fronted application (below) that phase 1 does not use.
4. **One party holds a supermajority in the Chamber.** On the 18 June 2026
   fiscal votes, the 190 positions break down PRM 140, Fuerza del Pueblo
   28, PLD 12, and 10 across five small parties and one independent. The
   Congress is a real, freely elected legislature, and contested votes do
   happen (515 of 2,634 votes had at least one No), but the outcome of a
   whipped vote is rarely in doubt. Monitoring is still worth it: the
   value is in what is tabled, which deputies break ranks, and the
   long-running causales fight, which is decided in recorded votes.

## Sources

### Camara de Diputados SIL: works today, open, no key

Base `https://www.diputadosrd.gob.do/sil/api/` (an Angular front end on
Azure; the endpoints are in its bundle, `/sil/Script/Bundles`). Every
request carries `periodoId`, which the front end adds in an interceptor:
`api/periodolegislativo/all` lists **2761 = 2024-2028** (current) and
**2760 = 2020-2024**. **Pages are ten rows and the size cannot be
changed** (`pageSize=200` is ignored). Some list endpoints answer 400 to an
empty or zero filter (`iniciativa/iniciativas?grupo=&tipo=`); the ones below
do not. No robots.txt (404), no rate-limit headers, no refusals at one
request a second; median reply about a second.

| Endpoint | What | Measured |
|---|---|---|
| `iniciativa/getIniciativas?page=N&keyword=` | every iniciativa, newest number first | 6,462 in 2024-2028 (647 pages); 11,500 in 2020-2024 |
| `iniciativa/iniciativa/{id}` | one iniciativa | same fields as the list |
| `iniciativa/historicos?page=1&id={id}` | status history with dates | 4 steps on 06342-2024-2028-CD |
| `sesion/sesiones?page=N&keyword=` | plenary sessions, newest first | 203 in 2024-2028 (137 ordinary, 61 extraordinary, 5 constitutional) |
| `sesion/votaciones?page=N&id={sesionId}` | a session's votes: motion text, Si/No/abstention counts, present, members | 2,634 votes, 16 August 2024 to 7 October 2026, in 201 sessions |
| `votacion/iniciativas/?page=1&id={votacion}` | the iniciativas a vote is linked to | see "votes and bills" |
| `votacion/legisladores/?page=N&id={votacion}` | every deputy's position, with party at the vote | 190 rows, 19 pages, 19 s per vote |
| `legislador/legisladores?page=N&keyword=a` | legislators (and the institutions that may propose laws) | 224 rows under 'a' |
| `sesion/ordenes?page=1` | the next session's order of the day (PDF) | 1: the 7 October 2026 session, posted 6 October |
| `sesion/documentos?page=1&id={sesionId}` | the session's documents: debates transcript, verified votes, order of the day (PDF) | 4 for the 7 October session |

- **Iniciativas.** Each row: `numero` ('06342-2024-2028-CD', our key),
  `id` (the SIL's own), `tipo`, `camaraInicio` (Camara de Diputados 4,441,
  **Senado 2,021**: the Chamber registers every iniciativa that reaches it,
  so Senate bills appear here once sent over), `descripcion` (the title),
  `materia` and `grupo` (the SIL's own subject headings), `estado`
  (Plazo vencido 1,623, Aprobado en unica lectura 1,483, Perimido 1,158,
  Promulgado 221, ...), `condicion`, deposit and taking-up dates, and the
  law number once promulgated ('Ley num.74-25'). Of the 6,462: 3,083
  internal resolutions, 1,852 bicameral resolutions, 1,527 bills.
- **Quirk: `tipo` is unreliable.** 06465-2024-2028-CD is typed "Resolucion
  Interna" with a title that begins "Proyecto de ley". The collector stores
  `tipo` as given and never filters on it.
- **Quirk: carried-over iniciativas are renumbered.** The 2024-2028 list
  includes deposits back to 2003 under new 2024-2028 numbers. The 2020-2024
  Penal Code bill is 11466-2020-2024-CD; the one that became law is
  04557-2024-2028-CD.
- **Quirk: two counts.** `iniciativa/CountIniciativas` says 6,466 for
  2024-2028 while the list's `total` says 6,462.
- **Votes.** Each vote: `id` (our key), session, number within the session,
  date, `titulo`, `mocion` (the motion as the clerk recorded it), counts
  and attendance. Positions are **SI, NO, AU** ("Ausente para esta
  votacion") and **SV** ("No Voto": present, did not vote). **No vote of
  the 2,634 records an abstention**: the system has none. Party rides on
  each position (PRM, FP, PLD, DXC-ALPAIS, PLR-PCR, PRSC, PRD-PQDC, INDEP).
- **Votes and bills.** The motion rarely names its bill ("Sometido a
  votacion el proyecto de ley, en segunda discusion"): only 76 of the
  first 1,021 motions read carry an iniciativa number. The SIL's own link
  (`votacion/iniciativas`) is what ties a vote to its bill, one request per
  vote. In the measurement backfill, 2,207 of 2,634 votes came
  back linked to at least one iniciativa; the other 427 are procedure
  (orders of the day, minutes, leaving items on the table).
- **Members.** The legislator list needs a keyword; under 'a' it returns
  224 rows: deputies, senators who have proposed iniciativas, and the
  Poder Ejecutivo, Suprema Corte de Justicia and Junta Central Electoral
  (which may propose laws). The collector keeps deputies and senators and
  skips the institutions, and also records every deputy a vote names.
  Detail (`legislador/legislador/{id}`) adds province, constituency,
  profession and office contact.

### Camara de Diputados website: works, WordPress, not needed

`camaradediputados.gob.do` (WordPress, WP File Download) carries the same
session PDFs (orders of the day, actas, debates, attendance) and news. Its
REST API is open (`/wp-json/`) but exposes only posts and media. Its
"Lista de Iniciativas" page is an empty shell. It timed out four times in a
row on the first morning (45 s each), then answered normally: phase 1 does
not depend on it.

### Senate: reachable, but no per-senator votes and a closed bill system

- **Site.** `www.senadord.gob.do` (WordPress, rebuilt 2026). **robots.txt
  asks every crawler for a 120-second Crawl-delay** and blocks named AI
  crawlers (ClaudeBot, GPTBot and others) outright. The probe made about fifteen
  requests there over the morning, faster than that delay asks;
  any Senate collector must space requests two minutes apart. Its REST
  routes for senators and media answer **401** (closed by a security
  plugin).
- **Votes.** "Votaciones Electronicas": an empty category ("no cuenta con
  archivos"). The actas (`/elaboracion-de-actas/actas-de-sesiones/`, 2024
  to 2026, PDF with a text layer) record each electronic vote's subject and
  totals; acta 0095 of 18 December 2025 (66 pages) holds 18 votes and the
  final roll call (present, absent with and without excuse). No
  per-senator positions anywhere. Attendance PDFs are current (session 137
  of 29 September 2026, posted 1 October).
- **Iniciativas.** "Iniciativas Legislativas" links to
  `www.senado.gov.do/wfilemaster/consultante.aspx`, a 2006 document system
  (WFileMaster 3.0.4). It opens on a login form with a public
  "ingresar consultante" button; every list URL redirects to it.
  **The login page publishes, in its own HTML, the database connection
  string for each period, including a SQL Server user name and password.**
  The public button works by posting that string back. I did not press it,
  did not use the credentials, and deleted the archived copies of that page
  so they cannot reach the published raw archive. Chris may want the
  Senate told; either way, phase 1 does not go through it, and Senate
  iniciativas reach us through the Chamber's SIL once they are sent over.

### National open data: nothing for Congress

`datos.gob.do` (CKAN, open): a search for "congreso" returns four Ministry
of Finance datasets and nothing from either chamber.

### Courts and other channels

The **Tribunal Constitucional** is a major channel: its TC/0599/15 (2015)
annulled the 2014 Penal Code, which had included exceptions to the abortion
ban, on procedural grounds, and challenges to Ley 74-25 can be expected
there. The Constitution's article 37 (life "inviolable desde la concepcion
hasta la muerte") and article 55 (marriage between a man and a woman) frame
both chambers' debates. Not in phase 1; listed for phase 3.

## How much touches CitizenGO's ground

With the proposed Spanish terms below (a measurement draft kept in
`probe/terms-do.yaml`, not config), over iniciativa titles and the SIL's
`materia`:

| Corpus | Titles | On our ground (not migration only) | Tier 1 |
|---|---|---|---|
| 2024-2028 (to 8 October 2026) | 6,462 | 77 (1.2%) | 25 |
| 2020-2024 | 11,500 | 53 (0.5%) | 13 |

By area, 2024-2028: abortion 26 (21 of them the Penal Code and its
amendments), marriage and family 20, religious freedom 7, free speech 6,
parental rights and education 5, organ donation 5, prostitution and
trafficking 4, sex-based rights 3, surrogacy 2, assisted dying 1.
Representative hits: **04557-2024-2028-CD** (the Penal Code, now Ley
74-25), **06038-2024-2028-CD** (its amendment, Ley 44-26), **06115-2024-
2028-CD** (parents' prior right in sex education; bans comprehensive
sexuality education and gender ideology in schools), **06417-2024-2028-CD**
(religious freedom and a register of religious bodies), 04858-2024-2028-CD
(an equality and non-discrimination law, withdrawn), 00677-2024-2028-CD
(asks the executive to sign the Geneva Consensus Declaration), 06359-2024-
2028-CD (assisted human reproduction), 04960-2024-2028-CD (against "la
sharia" and mosque building). In 2020-2024: 04697 and 09072-2020-2024-CD
(abortion "por causas excepcionales": the causales bills), 04497-2020-2024-
CD (sexual and reproductive health), 05117-2020-2024-CD (the Geneva
Consensus again), 04751-2020-2024-CD (the marriage age, promulgated).

**Cross-check against the SIL's own subject group.** Of the 107 iniciativas
the SIL files under "Genero / Familia" in 2024-2028, the terms place 14 on
our ground; the rest are perinatal care, child benefit, women's economic
empowerment and violence prevention, which is right. Reading the 107 by
hand added "adopcion", "codigo de la familia", "orientacion parental",
"corresponsabilidad familiar" and "muerte perinatal" to the list.

**Votes.** In the measurement backfill (2,634 votes, classified on the
motion plus the linked iniciativas): **144 on our ground**, 59 of them on
the 2025 Penal Code (23 to 31 July 2025, article-by-article amendments)
and 40 on its 2026 amendment (8 to 20 July 2026), 20 on trafficking
(mostly the reform of Ley 137-03), and 25 on moral and civic education,
organ donation, religious freedom, the children's code, the Geneva
Consensus resolution, the Civil Code and other Penal Code amendment
bills. A vote linked to a batch of resolutions inherits the areas of any
one of them, so a few of the 25 are batches of mostly unrelated
resolutions; the edition's triage has to read the motion. Positions were read for all 144 and for
one recent contested vote: 27,546 positions, 191 deputies. The vote that
matters most is there: **cd/21544, 30 July 2025**, an amendment to article
111 of the Penal Code that would have allowed ending a pregnancy to save
the mother's life once every other means was exhausted. Rejected 21 to
102 (155 present): Fuerza del Pueblo 19 for, PRM 95 against and one for,
PLD 4 against and one for. Its own motion text names no causal and no
bill: it was caught because the SIL links it to 04557-2024-2028-CD, and
"terminacion del embarazo" is now in the proposed list so the motion
alone would catch it too.

**Noise measured and removed from the draft:** "pastor*" (11 hits: honours
for named pastors, and the Divina Pastora procession), "capellan*" and
"mezquita*" (surnames Capellan and Amezquita), "templo*" (a sports
building), "Ministerio de la Mujer" (8, all resolutions asking for offices
or services), "medios de comunicacion" (a broadcasters' guild), and
"embarazada*" alone (alcohol in pregnancy; kept only with adolescente,
nina, violacion, incesto or riesgo in the title). "Causales" and "tres
causales" never appear in a title: the fight is fought inside Penal Code
bills, which is why "Codigo Penal" is a tier-2 term and the codes are on
the watchlist.

## Proposed Spanish terms (for Chris's approval)

Written unaccented because the collector folds accents on both sides.
**DO** marks a Dominican-specific term (a Dominican law, institution or
case); everything else is shared Spanish, for the other Spanish-language
scopes to merge. `*` is the stem wildcard; "with" means the term needs one
of the listed words in the same text.

**1 Abortion.** Tier 1: aborto*, interrupcion voluntaria del embarazo,
interrupcion del embarazo, terminacion del embarazo (the wording of the
2025 life-of-the-mother amendment), tres causales (DO in use, shared in form),
causales, no nacido*, por nacer, desde la concepcion, vida desde la
concepcion (DO: Constitution art. 37), misoprostol, mifepristona, pildora
del dia despues, anticoncepcion de emergencia, objecion de conciencia.
Tier 2: Codigo Penal (DO in effect: the abortion articles live in it; Ley
74-25), salud sexual y reproductiva (DO: the long-pending Ley de Salud
Sexual y Reproductiva), derechos sexuales y reproductivos, derechos
reproductivos, embarazo* en adolescentes, embarazo adolescente, embarazo
infantil, mortalidad materna, planificacion familiar, anticoncepcion,
anticonceptivo*, duelo gestacional, muerte perinatal, madre* gestante*,
embarazada* (with adolescente*, nina*, violacion, incesto, riesgo).

**2 Assisted dying.** Tier 1: eutanasia, muerte digna, muerte asistida,
suicidio asistido, suicidio medicamente asistido, homicidio piadoso. Tier
2: cuidados paliativos, voluntad anticipada, voluntades anticipadas,
testamento vital, limitacion del esfuerzo terapeutico.

**3 Gender medicine and children.** Tier 1: bloqueadores de la pubertad,
bloqueadores puberales, hormonizacion, transicion de genero, reasignacion
de sexo, cambio de sexo, afirmacion de genero, disforia de genero, menores
trans. Tier 2: infancias trans, ninez trans.

**4 Conversion practices.** Tier 1: terapia* de conversion, ECOSIEG,
esfuerzos de cambio de orientacion sexual. Tier 2: terapias reparativas.

**5 Sex-based rights and gender ideology.** Tier 1: identidad de genero,
ideologia de genero, enfoque de genero, perspectiva de genero, personas
trans, transgenero*, transexual*, lenguaje inclusivo, LGBT*, LGTB*,
LGBTI*, LGTBI*, orientacion sexual, igualdad y no discriminacion, no
discriminacion (DO: the Ley Organica de Igualdad y No Discriminacion
fight). Tier 2: igualdad de genero, equidad de genero, diversidad sexual,
politica de genero (DO: the 2019 MINERD gender policy dispute). "Genero"
alone is not a term: "violencia de genero" titles are many and off our
ground.

**6 Parental rights and education.** Tier 1: educacion sexual integral,
educacion integral en sexualidad, derecho preferente de los padres,
derecho de los padres, patria potestad, autoridad parental (DO: Ley
136-03's term), educacion en el hogar, educacion en casa, homeschooling,
pin parental, Con mis hijos no te metas, Biblia en las escuelas, lectura
de la Biblia (DO: Ley 44-00 on Bible reading in schools). Tier 2: curricul*
(with sexual*, genero, familia, valores, religio*, moral*, padres, biblia),
padres de familia, Asociacion de Padres, textos escolares, libertad de
ensenanza, educacion sexual, educacion moral, educacion en valores,
orientacion y psicologia.

**7 Free speech and online safety.** Tier 1: libertad de expresion,
discurso de odio, delitos de odio, incitacion al odio, censura previa,
difamacion, injuria*. Tier 2: libertad de prensa, libertad de
informacion, desinformacion, noticias falsas, verificacion de edad,
ciberacoso, ciberdelito*, delitos de alta tecnologia (DO: Ley 53-07), redes
sociales (with nino*, menor*, adolescente*), ley de expresion (DO: the
"Ley de expresion y medios de comunicacion" bills).

**8 Freedom of religion.** Tier 1: libertad religiosa, libertad de
conciencia, libertad de culto*, igualdad religiosa, entidades religiosas,
confesion* religiosa*, educacion religiosa, simbolos religiosos, iglesias
evangelicas, Concordato (DO: the 1954 Concordat with the Holy See),
asociaciones religiosas, extremismo religioso, sharia, mezquitas. Tier 2:
Iglesia Catolica, Santa Sede, lugares de culto, Dia de la Biblia, Dia
Nacional de la Biblia (DO), iglesia* evangelica*, iglesia* cristiana*.

**9 Marriage and family.** Tier 1: matrimonio igualitario, matrimonio entre
personas del mismo sexo, union civil, uniones civiles, parejas del mismo
sexo, adopcion homoparental, matrimonio infantil, uniones tempranas (DO:
Ley 1-21), union* libre*, union* de hecho, Consenso de Ginebra. Tier 2:
divorcio, proteccion de la familia, fortalecimiento de la familia, Codigo
Civil (DO: the pending Civil Code), Codigo de Familia, codigo de la
familia, Ley de Familia, adopcion, orientacion parental, corresponsabilidad
familiar, matrimonio*, pension* alimentaria*, Codigo para el Sistema de
Proteccion (DO: Ley 136-03, the children's code).

**10 Surrogacy and embryology.** Tier 1: gestacion subrogada, maternidad
subrogada, vientre* de alquiler, reproduccion humana asistida, tecnicas de
reproduccion asistida, fecundacion in vitro, clonacion humana. Tier 2:
reproduccion asistida, embrion*, banco de ovulos, donacion de gametos.

**11 Migration (collated, never campaigned).** Tier 1: migracion,
migraciones, migrante*, extranjeros, refugiado*, Direccion General de
Migracion (DO), haitian* (DO), indocumentad*, naturalizacion,
nacionalidad. Tier 2: frontera, regularizacion migratoria, Ley General de
Migracion (DO: Ley 285-04).

**12 Prostitution and trafficking.** Tier 1: trata de personas, trafico de
personas, trafico ilicito de migrantes (DO: Ley 137-03), prostitucion,
explotacion sexual, proxenetismo, pornografia*, abuso sexual infantil,
trabajo sexual. Tier 2: explotacion sexual comercial, turismo sexual.

**13 Organ donation.** Tier 1: donacion de organos, trasplante de organos,
donante* de organos, trafico de organos, donacion y trasplante. Tier 2:
trasplante*, tejidos humanos, INCORT (DO: the national transplant
institute).

## What was built (phase 1, 9 October 2026)

- `tools/do_rollcalls.py`: the 2024-2028 iniciativa list, re-read whole
  every week (`--period 2020-2024` adds the last period); sessions not yet
  read plus the last 21 days' again; every vote's header and its linked
  iniciativas; positions for votes on our ground, on a watched iniciativa,
  or contested (any No) within the last 30 days (`--contested-days`); the
  legislator list. `--reclassify` re-derives areas offline. Exit 3 means
  it stored what it could and recorded gaps. Host throttle one request a
  second.
- `src/do_store.py`: `do_members`, `do_bills`, `do_sessions`,
  `do_divisions`, `do_votes`, declared in `db.TABLES` and created by
  `db.init_db`.
- `config/watchlist-do.yaml`: a five-entry draft (the Penal Code, its
  amendment, the 2020-2024 Penal Code bill, the parents' right bill, the
  religious freedom bill), applied by iniciativa number, never by title.
- Classification: `config/taxonomy-es.yaml` when it exists, otherwise the
  English `config/taxonomy.yaml` (blind, so the plumbing runs). When
  `taxonomy-es` lands, dispatch the workflow with "reclassify".
- Tests: `tests/test_do_rollcalls.py` (21 tests) on real SIL replies
  trimmed to a few rows (`tests/fixtures/do/`) and a test-only term file
  (not the proposed taxonomy).
- The weekly job, Mac Mini first: `jobs/do-weekly.sh` (the Spain pattern:
  collect, then `tools/raw_state.py --push` before `tools/db_state.py
  --push`), `ops/launchd/net.citizengo.parlmonitor.do-weekly.plist`
  (Sundays 09:00 London) and `.github/workflows/do-weekly.yml` (Sundays
  09:00 and 12:00 UTC, gated by `mini-check.yml` with job `DO_WEEKLY`,
  grace 260 minutes). **It runs on GitHub only once merged to main.**
- Probe scripts (`probe/get.py`, `probe/pull_all.py`, `probe/measure.py`,
  `probe/backfill.py`) and the measurement term draft
  (`probe/terms-do.yaml`) are committed for reproducibility; their output
  is not.

**Cost, measured.** The whole 2024-2028 iniciativa list took 647 requests
and about eleven minutes. The measurement backfill of every 2024-2028 vote
(a session list, 2,634 vote headers, one link request per vote, and the
positions it chose) took 1 hour 41 minutes into a scratch database (06:17 to 07:58, with no
gaps; the first 25 minutes shared the host with the iniciativa pull). So the
first scheduled run will not finish the backfill: the 45-minute budget
stops it cleanly, oldest sessions first, and the following Sundays
complete it. Later weeks: the iniciativa list plus one or two sessions,
about fifteen minutes.

**Full suite** on 9 October 2026, in this worktree: 3,313 tests, 74
failing, every one for want of the gitignored raw archive
(`data/raw/2026-08-01/` and other day folders) or a working-copy store,
neither of which a fresh worktree has. With main's frozen 2026-08-01
fixtures linked in, all but the 10 tests that glob other day folders pass.
The Dominican tests and the structural tests on the shared files
(`test_coverage`, `test_db`, `test_mini_check`, `test_raw_state`) pass.

### Edits to shared files (for the merge of the country branches)

- `src/db.py`: five `do_*` names in `TABLES`; two lines in `init_db` calling
  `do_store.ensure_schema`.
- `tools/coverage.py`: "Dominican Republic weekly" in `PIPELINES`,
  `PIPELINE_FEEDS` and `AWAITING_FIRST_RUN`; four `do_*` rows in `FEEDS`.
- `.github/workflows/alert.yml`: "Dominican Republic weekly" in the watched
  workflow list.

Nothing else outside the Dominican Republic's own files changed.
`docs/mac-mini.md` is not edited; its job table needs a row for
`do-weekly` (Sundays 09:00, backup 09:00/12:00 UTC, `MINI_LAST_DO_WEEKLY`,
grace 260) when this merges.

## Phase plan

1. **Phase 1 (built):** Chamber iniciativas (both chambers' bills once in
   the Chamber), sessions, votes, positions where they matter, legislators,
   Spanish classification once approved.
2. **Phase 1b:** status history (`iniciativa/historicos`) and proponents
   (`iniciativa/proponentes`) for iniciativas on our ground, for the
   edition's "what moved" line and the 5CA authorship layer; the
   2020-2024 votes (same API, `periodoId=2760`) if Chris wants the last
   period's causales record.
3. **Phase 2:** the week ahead from `sesion/ordenes` (the next order of the
   day, PDF with a text layer, posted the day before); committee agendas;
   Senate actas for vote totals and Senate attendance, at the 120-second
   crawl delay.
4. **Phase 3:** debate transcripts (`sesion/documentos`, "Debates de la
   sesion", PDF) for debate packs; the Tribunal Constitucional; a
   Dominican 5CA.

## Dates that matter

- Two ordinary legislatures a year, from 27 February and 16 August, of 150
  days each; the 2026 second legislature ("2026-SLO") opened in August.
  Extraordinary sessions fill the gaps (61 of 203 sessions).
- The Chamber sits in plenary on Tuesdays and Wednesdays; votes appear in
  the SIL within a day (the 7 October votes' verified record was uploaded
  at 16:38 that day).
- The 2024-2028 period ends on 15 August 2028; the next general election
  is in May 2028.

## Waiting on Chris

1. **Approve the Spanish term list** above (and the DO flags), so a
   `taxonomy-es` file can be generated. One shared Spanish file or one per
   country is a decision across the Spanish-language scopes.
2. **The Senate's leaked credentials.** Its public iniciativas page
   publishes a database user name and password in its HTML. Tell the
   Senate (and through whom)? Phase 1 does not use that system either way.
3. **Senate votes.** There are no per-senator positions to collect. Accept
   Chamber-only votes, or ask the Senate (Departamento Elaboracion de
   Actas) whether the annexed vote sheets can be published?
4. **Review `config/watchlist-do.yaml`** (five draft entries), ideally with
   someone who campaigns in the Dominican Republic.
5. **The 2020-2024 period**: backfill its votes too (about 3,000 more link
   requests, spread over a few runs)?
6. **Install the Mini job** after the merge to main: copy the plist to
   `~/Library/LaunchAgents`, bootstrap it, and add the `docs/mac-mini.md`
   row. **Merge to main** when ready: the weekly workflow is inert until
   then.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (DO1) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code; X11 brings the gender-violence and femicide terms in at tier 2.
- DO4: the weekly now also backfills the 2020-2024 period, after the current period, within the budget.

Later phases and items for Chris (not built at the merge):

- Chamber-only votes (DO2).
- The Senate credentials in its front end stay unused (S2).

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/do_stance.yaml` holds 1 bill direction(s) (Claude's drafts from the watchlist) and 94 vote reading(s): 0 with proposed values, 12 procedural, 82 need reading, 0 confirmed. Guide: `docs/5ca-do-readings.md`; confirm with `python3 tools/country_5ca.py --cc do --sign-from-doc --by NAME`. Sheets (`data/5ca/do-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for Dominican Republic (`config/stance_signers.yaml`).

## Same-day vote briefs (built 10 October 2026, branch `parity-vote-briefs`)

Handover item 1: a brief for each watched or tier-1 vote, naming the members who voted against their group's majority, one DM to Chris per run, de-duplicated in `data/vote-briefs/do.json` (`src/country_vote_brief.py`, step in `jobs/do-weekly.sh`). Briefed after each weekly collection. See docs/mac-mini.md, "Vote briefs for the new countries".
