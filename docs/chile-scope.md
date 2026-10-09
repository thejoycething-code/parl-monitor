# Chile: scoping the National Congress monitor

Probed live on 9 October 2026, from the laptop, with the honest CitizenGO UA
and `src/http.py`'s throttle. Every number below was measured, not
estimated. Raw responses are archived under `data/raw/2026-10-09/`
(`cl-rollcalls_*`), which is gitignored and travels with the raw archive
release like every other feed. National Congress only (the Cámara de
Diputadas y Diputados and the Senado); the regional councils are a later
decision.

## Decisions (Christopher, before this probe)

- **Own edition**, delivered to Christopher alone (Slack DM), like the US.
- **Shared taxonomy concept, Spanish terms proposed here.** No existing
  taxonomy file is edited. A `config/taxonomy-es.yaml` is generated only
  after Christopher approves the list below. Spain, Argentina, Mexico,
  Colombia and Peru are being scoped in parallel in Spanish, so the list
  marks which terms are Chile-specific.
- **National Congress first**; regional councils later.
- **Mac Mini first, GitHub Actions as backup**; no new paid services; never
  post publicly.

## Headline

**Everything phase 1 needs is open, keyless and machine-readable, and it is
built.** Both chambers publish recorded votes with every member's position,
bills keyed by boletín, and member lists with parties. No key, no account,
no rate limit observed.

**The English taxonomy is completely blind to Chile.** Run over the 1,399
bills introduced in 2025 and 2026, `config/taxonomy.yaml` matched **0**.
The proposed Spanish list matched **77** (59 on our
ground, migration aside). Until Christopher approves the Spanish list, the
collector stores everything but classifies with the English list, says so
on every run, and a `--reclassify` puts it right offline the day the
Spanish file lands.

## Phase 1: built, 9 October 2026

`tools/cl_rollcalls.py` into `cl_members`, `cl_party_spells`, `cl_bills`,
`cl_divisions` and `cl_votes` (schema in `src/cl_store.py`, declared in
`db.TABLES`). Live run into a scratch database (not the store), with the
PROPOSED Spanish terms passed by `--taxonomy`:

| | Read | On our ground (proposed terms, migration aside) |
|---|---|---|
| Bills (boletines) | 1,471 | 64 |
| of which introduced 2025-2026 | 1,399 | 59 |
| Cámara votes since 11 March 2026 | 716 | 4 |
| Senate votes (bills with movement since 25 September, watched bills, backfill) | 44 | 1 |
| Member positions | 112,330 | |
| Members (155 deputies, 50 senators, 20 former senators by printed name) | 225 | |

Fifty-three minutes in all: the first pass stopped itself after 489 Cámara
votes when one detail call timed out four times (a gap, logged), and the
second pass resumed from the store and finished the other 227 with no gap.
Of 110,980 Cámara positions, 716 (0.6%) carry no party: the deputy's
militancias do not cover that date. Every Senate position since 11 March
2026 (919 of 919) resolved to a sitting senator; the 178 unresolved are
2023-2025 votes by senators who left in March 2026, kept by printed name.

- **Every position is stored.** The Cámara needs one detail call per vote
  (2-7 s each, measured); the Senate's positions come inside the bill
  record. The first run reads the whole period since 11 March 2026
  (53 minutes from the laptop); later weeks read 20-60 votes.
- **Votes inherit their bill's areas**; `own_areas` keeps the vote's own
  match apart, as in the US. The Cámara vote list says only "Boletín N°
  15805-07"; the text put to the vote ("Articulo") comes from the bill
  record, one call per boletín.
- **Party at the vote.** The Cámara gives each deputy's dated party spells
  (militancias), so `cl_votes.party` is the party on the day. The Senate
  gives only the current party, so a Senate vote carries the party at
  collection. Weaker; said here so nobody reads it as more.
- **Watched bills are read every run** from the Senate's per-bill record,
  because a watched bill can sit for years without appearing in any weekly
  window (the euthanasia bill has waited in the Senate since 2021).
- **Tests:** `tests/test_cl_rollcalls.py`, 29 tests on real responses
  trimmed into `tests/fixtures/cl/`, no network.
- **Not scheduled until merged.** `jobs/cl-weekly.sh`, the launchd plist and
  `.github/workflows/cl-weekly.yml` exist on the branch; GitHub schedules
  only from main.

## What Chile publishes

### Cámara de Diputadas y Diputados: works today, open, no key

`opendata.camara.cl` hosts ASMX web services (`WSLegislativo`,
`WSDiputado`, `WSComision`, and the older `wscamaradiputados.asmx`). They
are documented as SOAP, but **every operation also answers plain HTTP GET**
(`/WSLegislativo.asmx/retornarVotacionesXAnno?prmAnno=2026`), returning
XML. No SOAP envelope is needed.

| Operation | What it gives | Measured |
|---|---|---|
| `retornarVotacionesXAnno?prmAnno=` | every vote of a year: date, counts, quorum, result, type | 2026: 1,028 votes to 7 October (632 on bills, 163 resolutions, 33 agreements, 200 other), 431 KB, 13 s. 2025: 1,340 votes |
| `retornarVotacionDetalle?prmVotacionId=` | one vote with every deputy's position, by Cámara deputy Id | 155 positions, 43 KB, 2-7 s |
| `retornarProyectoLey?prmNumeroBoletin=` | a bill and every Cámara vote on it, with the text voted and the trámite | 39 KB to 148 KB, 5-7 s |
| `retornarMocionesXAnno` / `retornarMensajesXAnno` | every bill introduced in a year, titled | 2025: 642 motions + 65 messages; 2026: 627 + 65. 300 KB, 24-44 s |
| `WSDiputado.asmx/retornarDiputadosPeriodoActual` | the 155 deputies, with dated party spells | 180 KB, 8 s |
| `wscamaradiputados.asmx/getSesiones?prmLegislaturaID=58` | sessions of the current legislatura | 81 (80 held, 1 called for 19 October) |
| `retornarLegislaturaActual` | legislatura 374, 11 March 2026 to 10 March 2030 | |

Of the 1,028 votes in 2026, 716 fall since the new period began on
11 March 2026, on 155 distinct boletines; 67 of those boletines were
introduced before 2025, so the bill record is fetched per boletín rather
than taken from the yearly lists.

Quirks, each handled in the parser:

- **"Not found" is HTTP 200.** An unknown boletín or vote returns an element
  with `xsi:nil="true"` (219 bytes). Parsers validate the root and nil flag.
- **Vote IDs are not contiguous** (89687, 89689, 89690 exist; 88800-88803 do
  not), so the collector walks the yearly list, never the ID range.
- **"Unánime" on a split vote.** Vote 82260 (12 May 2025, 59-67-4) carries
  `Resultado Valor="2">Unánime`. The result is stored in the source's words
  and must never be read without the counts.
- **Period dates are mislabelled**: every current deputy's `FechaInicio` is
  2030-03-10 (the period's end). The militancia dates are right and are
  what the collector uses.
- **Bill subjects are empty**: `Materias` is blank on every bill probed.
  The Senate's record carries them (below).
- **No districts, no attendance**: `retornarDiputadosPeriodoActual` has no
  district; `getSesionDetalle` returns an empty `Asistencia`;
  `getSesionBoletinXML` returned nothing for held sessions.
- `WSSesion.asmx` and `WSCamara.asmx` redirect to a maintenance page.
- **www.camara.cl refuses the laptop** (Cloudflare challenge, 403). Not
  worked around (bot detection is never worked around in this repo). The
  Cámara's tabla (order paper) lives only there.

### Senado: works today, open, no key

`tramitacion.senado.cl/wspublico/` serves XML over plain GET:

| Endpoint | What it gives | Measured |
|---|---|---|
| `tramitacion.php?fecha=dd%2Fmm%2Fyyyy` | every bill with movement since the date, both chambers: title, stage, status, urgency, authors, Senate subject terms (materias), full tramitación, AND every Senate vote with each senator's position | since 1 October: 121 bills, 1.5 MB, 18 s. Since 25 September: 177, 1.9 MB, 20 s. Since 15 September: 234, 2.5 MB, 30 s |
| `tramitacion.php?boletin=7736` | one bill, same record | under 1 s |
| `votaciones.php?boletin=15805` | the Senate votes on one bill, with positions | 4 votes, 16 KB, 0.7 s |
| `senadores_vigentes.php` | senators with PARLID and party | **31 of 50** (stale) |
| `sesiones.php?legislatura=374` | Senate sittings with the IDs of their tabla, cuenta and diario | 72 sittings, 69 with a tabla ID; next sitting 20 October |

Quirks:

- **The date must be percent-encoded** (`01%2F10%2F2026`). Raw slashes get
  an HTML "No existe el número de boletín" page at 200.
- **A month at most**: a date over a month back gets "La fecha no puede
  exceder de un mes"; 8 September (31 days) timed out into the "No existe"
  page after 31 s. The collector reads 14 days (capped at 28).
- **The boletín is the number only**: `votaciones.php?boletin=15805-07` gets
  "No existe el boletín solicitado"; an unknown number gets an empty
  `<votaciones>`.
- **No vote ID.** A Senate vote is identified by session, date, stage, kind
  and text; the collector hashes those into `senado-<number>-<12 hex>`.
- **Senators are named, not numbered**, in vote records: "Gatica B., María
  José" (first surname, second-surname initial, given names). The collector
  resolves them against the senator list and requires every printed part to
  agree; a former senator who shares a surname with a sitting one ("Castro
  P., Juan" against "Castro G., Juan Luis") is kept as printed, never
  guessed.
- **`senadores_vigentes.php` is stale**: 31 senators, none of those who took
  their seats in March 2026 (Cicardini, Flores, Celis ...). The senado.cl
  listing page (`/senadoras-y-senadores/listado-de-senadoras-y-senadores`)
  embeds all **50** with PARLID and party in its page JSON; the collector
  reads that and falls back to the stale service, recording a gap.
- `diariosesion.php` returned a JPEG labelled `application/xml`; the tabla
  document link (`getDocto`) returned 0 bytes. The Senate tabla needs
  another route (phase 2).
- Merged bills (refundidos) are named in each record ("9644-11 / 11745-11 /
  11577-11 / 7736-11 *matriz*"). Not stored in phase 1.

### BCN (Biblioteca del Congreso Nacional): reachable, reference only

- `datos.bcn.cl/sparql` answers SPARQL with JSON: 19,458 `ProyectoDeLey`
  resources. Linked-data descriptions of bills, laws and members; useful
  later for history and for laws in force, not needed for weekly votes.
- LeyChile (`leychile.cl/Consulta/obtxml?opt=7&idNorma=`) returns enacted
  law text as XML (2.8 KB header probed). Useful for "the law as amended"
  (Ley 21.030 on abortion, 21.120 gender identity, 21.400 equal marriage).

### Rate limits and politeness

No rate-limit headers, no 429s, no blocks on any open-data host over the
whole probe and the live run (about 1,000 requests). Responses are slow
rather than limited (1-30 s); the collector runs one request at a time with
the shared throttle. robots.txt: opendata.camara.cl serves an HTML page
(no rules); tramitacion.senado.cl redirects; www.senado.cl allows all but
`/proyecto-365`.

## How much touches CitizenGO ground

**Bills: plenty. Floor votes: almost none, this year.** With the proposed
terms, 64 of 1,471 bills are on our ground (27 at tier 1, 13 by watchlist),
by area: abortion 9, assisted dying 5, gender medicine and children 4,
sex-based rights 5, parental rights and education 15, free speech 5,
religion 3, marriage and family 6, surrogacy and embryology 5, prostitution
and trafficking 8, organ donation 3. Migration (hidden) 25. The English
taxonomy, run over the same store, matched **no bill on its terms at all**:
its 9 hits were all watchlist entries.

What is live, by name: an elective abortion bill (17564-11, "interrupción
voluntaria del embarazo en el plazo que indica", first trámite in the
Cámara), a bill removing the rape ground from the 2017 three-grounds law
(17728-11), a constitutional amendment protecting "la vida del ser humano
en gestación" (17494-07), "eutanasia en tres causales" (17732-11, 2025),
the euthanasia matrix 7736-11 (passed the Cámara in 2021, waiting in the
Senate), four bills against gender interventions for minors, three on the
parents' preferential right to educate, five banning social media under 14
or 16, a ban on surrogacy (17337-07) and a bill to regulate altruistic
surrogacy (18546-34), and a negationism offence
(17708-17, free speech).

The floor is another matter. Of 716 Cámara votes since 11 March, **4** touch
our ground: an amendment by Emilia Schneider on school demand estimates
(16743-04, matched on "tasa de natalidad", a false positive), a vote on
16709-11 (amends Ley 20.418 on fertility information, to promote education
about infertility: on our ground only loosely), an amendment exempting
protest and "libertad de expresión" from a new offence of blocking
transport (18584-25), and an amendment on smuggling migrants (16948-07,
area 12 beside 11). The Senate's one is 16709-11 in January
2025. The 2026 floor has been dominated by the reconstruction omnibus
(18216-05, 117 votes alone), school discipline and energy prices. Two
cautions: **171 votes carry no boletín** (resolutions, agreements,
procedure), and the open data gives no text for them, so a resolution on
our ground would pass unseen; and **the omnibus problem** the US found
applies to 18216-05, whose amendment texts are stored and matched on their
own words.

## Proposed Spanish terms (for Christopher's approval)

Written **without accents**: the Chile collector folds accents out of the
text before matching (the Senate writes "Abstencion", titles drop accents
inconsistently, materias are upper case). `src/filter.py` itself does not
fold accents, so **every Spanish-language collector must fold the same way
or the terms must carry accents**; this is a cross-country decision (see
Waiting on Chris). Areas and keys are identical to the English taxonomy.
Terms marked **(CL)** are Chilean law numbers, programmes or phrasing; the
rest should hold across the Spanish-speaking editions, subject to each
country's own probe.

**1. Abortion** `{#1_abortion}`

- Tier 1: "aborto*"; "interrupcion voluntaria del embarazo"; "interrupcion del embarazo"; "tres causales" **(CL)**; "21.030" **(CL)**; "aborto libre"; "objecion de conciencia"; "Ley Dominga" **(CL)**; misoprostol; mifepristona; "ser humano en gestacion" **(CL)**; "vida del que esta por nacer" **(CL)**
- Tier 2: "derechos sexuales y reproductivos"; "derechos reproductivos"; "salud reproductiva"; "salud sexual y reproductiva"; "planificacion familiar"; "nonato*"; "no nacido*"; "que esta por nacer" **(CL)**; nasciturus; "pildora del dia despues"; "anticoncep*"; "muerte gestacional"; "perdida gestacional"; "duelo gestacional"; "mortinato*"; "embarazo no deseado"; "despenaliz*" [with: aborto*, embarazo]

**2. Assisted dying** `{#2_assisted_dying}`

- Tier 1: eutanasia; "muerte digna"; "muerte medicamente asistida"; "muerte asistida"; "suicidio asistido"; "asistencia medica para morir"; "ayuda medica para morir"; "buen morir" **(CL)**
- Tier 2: "cuidados paliativos"; "enfermedad terminal"; "enfermo* terminal*"; "voluntad anticipada"; "directrices anticipadas"; "21.375" **(CL)**; "fin de vida"; "final de la vida"

**3. Gender medicine and children** `{#3_gender_medicine_children}`

- Tier 1: "bloqueadores de la pubertad"; "bloqueadores puberales"; "bloqueo puberal"; "hormonas cruzadas"; "disforia de genero"; "infancias trans"; "ninez trans"; "ninos trans"; "ninas trans"; "menores trans"; PAIG **(CL)**; "acompanamiento para la identidad de genero" **(CL)**; "Crece con Orgullo" **(CL)**; "transicion de genero"; "reasignacion de sexo"; "reasignacion de genero"; "cambio de sexo" [with: menores, ninos, ninas, adolescentes]
- Tier 2: "afirmacion de genero"; "detransicion*"; hormonizacion; "terapia hormonal" [with: menores, ninos, ninas, adolescentes]

**4. Conversion practices** `{#4_conversion_practices}`

- Tier 1: "terapias de conversion"; "terapia de conversion"; "terapias de reconversion"; "terapias reparativas"; ECOSIEG; "esfuerzos de cambio de orientacion sexual"

**5. Sex-based rights** `{#5_sex_based_rights}`

- Tier 1: "identidad de genero"; "expresion de genero"; "21.120" **(CL)**; "Ley Zamudio" **(CL)**; "20.609" **(CL)**; "ley antidiscriminacion"; "rectificacion de sexo"; "sexo registral"; "cambio de sexo"; "deporte femenino"; "categoria femenina"; "Belem do Para"
- Tier 2: transgenero; "transexual*"; "personas trans"; "no binari*"; "diversidad sexual"; "diversidades sexuales"; "disidencias sexuales"; "LGBT*"; "orientacion sexual"; "perspectiva de genero"; "enfoque de genero"; "violencia de genero"; "igualdad de genero"; "lenguaje inclusivo"

**6. Parental rights and education** `{#6_parental_rights_education}`

- Tier 1: "educacion sexual integral"; "educacion sexual"; "educacion en sexualidad"; "sexualidad, afectividad y genero" **(CL)**; "afectividad y genero" **(CL)**; "20.418" **(CL)**; "derecho preferente de los padres" **(CL)**; "derecho preferente" **(CL)**; "deber preferente" **(CL)**; "derechos de los padres"; "libertad de ensenanza"; "educacion en el hogar"; homeschooling; "clases de religion"; "educacion religiosa"; "ensenanza religiosa"
- Tier 2: "ESI" [with: educacion, sexual*, escuela*, colegio*]; "control parental"; "consentimiento de los padres"; "autorizacion de los padres"; "padres y apoderados" [with: sexual*, genero, afectividad]; "redes sociales" [with: menores, ninos, ninas, adolescentes]; "telefonos celulares" [with: establecimientos educacionales, colegio*, escuela*]; "dispositivos moviles" [with: establecimientos educacionales, colegio*, escuela*]

**7. Free speech and online safety** `{#7_free_speech_online_safety}`

- Tier 1: "libertad de expresion"; "discurso de odio"; "discursos de odio"; "incitacion al odio"; "incitacion publica al odio"; "delitos de odio"; censura; "verificacion de edad"; "tratado de pandemias"; "acuerdo sobre pandemias"; "Reglamento Sanitario Internacional"
- Tier 2: "pornograf*"; desinformacion; "noticias falsas"; negacionismo; "libertad de prensa"; "contenido danino"; "contenidos daninos"; "plataformas digitales" [with: contenido*, menores, odio]; "Organizacion Mundial de la Salud" [with: pandemia*, tratado, reglamento]

**8. Freedom of religion** `{#8_freedom_of_religion}`

- Tier 1: "libertad religiosa"; "libertad de culto"; "libertad de cultos"; "libertad de conciencia"; "libertades de conciencia"; "religiosa y de culto"; "ley de cultos" **(CL)**; "19.638" **(CL)**; "entidades religiosas"; "secreto de confesion"; "sigilo sacramental"; "persecucion religiosa"; "quema de iglesias" **(CL)**; "ataques a iglesias"; "lugares de culto"
- Tier 2: "capellan*"; iglesia; "iglesias" [with: religios*, culto*, evangelic*, catolic*, templo*]; laicidad; "Estado laico"; "confesiones religiosas"; "culto religioso"; "templo*"

**9. Marriage and family** `{#9_marriage_family}`

- Tier 1: "matrimonio igualitario"; "matrimonio entre personas del mismo sexo"; "21.400" **(CL)**; "acuerdo de union civil" **(CL)**; "invierno demografico"; "crisis demografica"; "tasa de natalidad"; natalidad; "matrimonio infantil"; poligamia
- Tier 2: "union civil"; divorcio; filiacion; "proteccion de la familia"; fecundidad; "corresponsabilidad parental"; "homoparental*"; copaternidad; comaternidad

**10. Surrogacy and embryology** `{#10_surrogacy_embryology}`

- Tier 1: "maternidad subrogada"; "gestacion subrogada"; "vientre de alquiler"; "vientres de alquiler"; "subrogacion gestacional"; "gestacion por subrogacion"; "subrogacion altruista"; "gestora subrogante" **(CL)**; "embrion*"; "donacion de gametos"; "donacion de ovulos"
- Tier 2: "reproduccion asistida"; "reproduccion humana asistida"; "fecundacion in vitro"; "criopreserv*"; "edicion genetica"; TRHA

**11. Migration (hidden, as in the US)** `{#11_migration}`

- Tier 1: "ley de migraciones"; "expulsion de extranjeros"; "ingreso clandestino"; "migracion irregular"; "migrantes irregulares"
- Tier 2: migracion; "migrante*"; inmigracion; "inmigrante*"; "refugiado*"; asilo; extranjeros

**12. Prostitution and trafficking** `{#12_prostitution}`

- Tier 1: prostitucion; "comercio sexual"; "explotacion sexual comercial"; ESCNNA **(CL)**; "proxeneti*"; "favorecimiento de la prostitucion"; "trabajo sexual"; "trabajadoras sexuales"; "servicios sexuales"
- Tier 2: "explotacion sexual"; "trata de personas"; "trafico de personas"; "trafico de migrantes"

**13. Organ donation** `{#13_organ_donation}`

- Tier 1: "donacion de organos"; "donante* de organos"; "trasplante* de organos"; "donante universal" **(CL)**; "19.451" **(CL)**; "20.413" **(CL)**; "trafico de organos"
- Tier 2: "trasplante*"; "procuramiento de organos"

### What the list deliberately leaves out, or keeps guarded

- **"iglesia*"** matched a surname ("Alejandra Iglesias", 17803-06), so the
  plural needs company (religious words) and the singular has no stem.
- **"subrogacion"** alone is a civil-law term (substitution of a creditor);
  only the surrogacy phrases are listed.
- **"cambio de sexo"** is area 5 on its own and area 3 only with minors in
  the same text.
- **"redes sociales"** is area 6 only with minors in the text; five
  2025-2026 bills ban social media under 14 or 16.
- **"union civil"** (tier 2) pulls in migration-fraud bills (sham marriages
  and civil unions for residence). Triage should score them low; said here
  so it is not a surprise.
- **"violencia de genero"** (tier 2) is common and mostly about domestic
  violence. Kept at tier 2 for the gender-ideology framing it sometimes
  carries; Christopher may prefer to drop it.

### Watched by boletín (`config/watchlist-cl.yaml`)

Bills whose titles hide their subject, found in the probe: the euthanasia
matrix 7736-11 and the three bills merged into it (9644-11, 11745-11,
11577-11; passed by the Cámara in 2021, in the Senate since); four bills on
gender interventions for minors (17571-18, 17586-18, 17636-18, 17798-11);
the elective abortion bill 17564-11, the constitutional protection of the
unborn 17494-07 and the removal of the rape ground 17728-11; parental rights
17930-04; the religious-freedom amparo 17967-07.

## Phase plan

1. **Phase 1 (built): votes, bills, members.** Both chambers, positions,
   party at the vote, bills by boletín, weekly. Needs only the taxonomy
   decision to become useful.
2. **Phase 1b: the Spanish taxonomy.** Generate `config/taxonomy-es.yaml`
   from an approved `docs/keyword-taxonomy-es.md` (the German pattern:
   `tools/generate_taxonomy.py --lang es`), then dispatch Chile weekly with
   "reclassify". Shared with the other Spanish-speaking editions.
3. **Phase 2: the agenda and urgencies.** Senate sittings and their tabla,
   Cámara sessions (dates only today), and the executive's urgencies
   ("Suma", "Discusión inmediata"), which are the Chilean signal that a
   bill is about to move. Urgency history is already in the Senate record.
4. **Phase 3: triage, edition and 5CA.** A Chile judge (Spanish), the
   edition to Christopher's DM, and deputies' and senators' records from
   `cl_votes` and bill authorship (authors are in the Senate record).
5. **Phase 4: the regional councils (consejos regionales)**, then the BCN
   history if wanted.

## Files touched outside Chile's own

Kept minimal for the merge of 16 country branches:

- `src/db.py`: five table names added to `TABLES` and two lines in
  `init_db` calling `cl_store.ensure_schema` (9 lines).
- `tools/coverage.py`: "Chile weekly" in `PIPELINES`, three `FEEDS` rows
  (`cl_members`, `cl_bills`, `cl_divisions`), one `PIPELINE_FEEDS` entry,
  one `AWAITING_FIRST_RUN` entry.
- `.github/workflows/alert.yml`: one line, `"Chile weekly"`.

Chile's own files: `src/cl_store.py`, `tools/cl_rollcalls.py`,
`config/watchlist-cl.yaml`, `tests/test_cl_rollcalls.py`,
`tests/fixtures/cl/`, `jobs/cl-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.cl-weekly.plist`,
`.github/workflows/cl-weekly.yml`, and this file.

## Waiting on Chris

1. **Approve (or edit) the Spanish terms above.** Nothing is generated until
   you do. Then `docs/keyword-taxonomy-es.md` and `config/taxonomy-es.yaml`,
   shared with Spain, Argentina, Mexico, Colombia and Peru.
2. **Accents, across all Spanish editions:** fold the text in each collector
   and write terms without accents (what Chile does now), or teach
   `src/filter.py` to fold accents for everyone (a shared change, which
   would also touch French and German matching).
3. **Merge to main** when you are happy: only then do the Thursday crons
   exist. Then on the Mini: copy the plist to `~/Library/LaunchAgents` and
   `launchctl bootstrap`, and optionally create `HC_CL_WEEKLY` (healthchecks)
   as for the other Mini jobs.
4. **Scope calls:** is area 11 (migration) watched but hidden for Chile, as
   in the US? Chile's 2025-2026 bills are heavy with migration (25
   titles). And is "violencia de genero" in or out?
5. **The Senate's party at the vote** is the party at collection. Acceptable
   for phase 1, or should senators' party history be sourced (the BCN has
   it) before any 5CA?

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (CL1; CL2 migration watched but hidden, as area 11 is everywhere) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.

Later phases and items for Chris (not built at the merge):

- X6: source party history before relying on party at the vote.
- The Senate-vote backfill still reads bills on our ground only; X15 would widen it.
