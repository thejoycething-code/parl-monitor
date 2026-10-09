# Spain: scoping the Cortes Generales monitor

Probed live on 9 October 2026, from the laptop (and, for the Senado, from a
GitHub runner). Every number below was measured, not estimated. Raw
responses are archived under `data/raw/2026-10-09/` (`es-probe_*` and
`es-rollcalls_*`); the probes went through `src/http.py` with the honest
CitizenGO User-Agent and a one-second throttle. National parliament first;
the seventeen autonomous parliaments are listed at the end for later.

## Decisions already taken (Christopher)

- **Own edition**, delivered to Christopher alone (a Slack DM), as the US.
- **Shared taxonomy concept, own language file.** `config/taxonomy.yaml` and
  every existing taxonomy file are untouched. The Spanish terms are
  PROPOSED below; `config/taxonomy-es.yaml` is generated only after
  Christopher approves them. Argentina and Mexico are being scoped in
  parallel and will share the language, so the list marks which terms are
  Spain-only.
- **Congreso and Senado first**; regions later.
- **Mac Mini first, GitHub Actions as the backup** (the Australia pattern).
  No new paid services. Nothing posts publicly anywhere.

## The two findings that shape everything

### 1. The Cortes were dissolved three days ago

**Real Decreto 806/2026, of 5 October, dissolved the Congreso and the Senado**
(BOE of 6 October 2026, BOE-A-2026-20742). Elections are on **Sunday
29 November 2026**; the campaign runs 13 to 27 November; **the XVI legislature
convenes on 23 December 2026.**

What that means for the monitor, all measured on 9 October:

- **The XV legislature is complete.** 146 voting days, 19 September 2023 to
  30 September 2026. Nothing will be added to it, which makes it an ideal
  backfill and a fixed corpus for the taxonomy.
- **Every pending initiative has lapsed** ("caducado"). The open data is
  catching up: 89 of 115 proyectos de ley already read "Concluido -
  (Caducado)", but 109 proposiciones de ley still read "Pleno, Toma en
  consideración". A board must read the legislature, never the status line
  (`src/es_store.py` says so).
- **213 deputies left on 6 October** (`DiputadosDeBaja`, all dated
  06/10/2026). The 137 still "active" are the Diputación Permanente and its
  substitutes, which sits between legislatures and can still vote, chiefly
  to convalidate decree-laws.
- **The weekly will find almost nothing until January 2027.** The XVI sits
  from 23 December, an investiture follows, and ordinary plenary votes are
  unlikely before mid-January. Whether Diputación Permanente votes appear
  on the same votes page is not yet known; the first one will tell.

So the quiet months are the right time to agree the Spanish terms, and the
collector is ready for the XVI with no edit: it reads the current
legislature off the Congreso's own page.

### 2. The English taxonomy is blind to Spanish

As in Germany. `config/taxonomy.yaml`, unchanged, over everything the XV
Congreso voted on and every legislative initiative it received:

| Text matched | Rows | Any area | On our ground |
|---|---|---|---|
| Plenary votes (2,179, item title + sub-heading) | 2,179 | 1 | 1 |
| Proyectos and proposiciones de ley (title) | 484 | 0 | 0 |

The one hit is a PSOE motion "sobre el impulso de la Agenda 2030", matched on
the English term `Agenda 2030`. **One match in 2,663 rows, and not a useful
one.** A Spanish monitor that reused the English list would collect
everything and see nothing.

**With the Spanish list proposed below** (draft v0.1, 190 tier-1 and 125
tier-2 terms, plus the watchlist):

| | Rows | Any area | On our ground (area 11 hidden) | Tier 1 |
|---|---|---|---|---|
| Plenary votes, XV | 2,179 | 118 | **86** (on 40 distinct items) | 50 |
| Legislative initiatives, XV | 484 | 44 | **34** | |

Votes on our ground by area: abortion 3, assisted dying 2, conversion
practices 10, sex-based rights and gender identity 35, parental rights and
education 18, free speech 14, religion 1, marriage and family 8,
prostitution and trafficking 4, organ donation 2. Migration (collated,
hidden) matched 32 votes on its own. In the last twelve months: 34 of 900
votes.

Read honestly:

- **21 of the 35 area-5 votes match only on "violencia de género" /
  "violencia sexual"** (seven items: the Pacto de Estado subcommittee
  report and its particular votes, and PP and VOX motions on the failures
  of the electronic tagging of restraining orders). Whether Spain's gender-violence law is our ground
  is a scope question for Christopher (see the end). Without it, area 5
  is 14 votes.
- **Abortion barely reached the plenary floor in three years**: three
  votes. The largest was the Government's bill to write abortion into the
  Constitution, `Proyecto de reforma del artículo 43`, whose totality
  amendments failed 171 to 177 on 30 April 2026. Its title names only the
  article, so it is on `config/watchlist-es.yaml` by key (15/102/000001) and
  the draft carries `"reforma del artículo 43" [with: Constitución]`.
- **Most of what Spain's parties do on our ground is not a bill.** 29 of the
  86 votes are proposiciones no de ley (non-binding motions), 11 are
  motions following urgent interpellations; only 19 are bills or their
  amendments. The open-data initiative files carry bills only (see below).
- **Surrogacy, pornography and the Valle de los Caídos produced no plenary
  vote at all in the XV**, religion one, and the Congreso's own title search
  finds no initiative of any kind titled with "gestación subrogada",
  "maternidad subrogada" or "vientres de alquiler" in the XV (0 each).

## What Spain publishes

### Congreso de los Diputados: open data, no key, WORKS TODAY

Everything at `www.congreso.es/es/opendata/*`. No account, no key, no rate
limit published or met: about 250 requests over the day, at one a second,
were all answered, with the honest UA. Each data page links files regenerated
daily (about 05:00 Madrid) under **timestamped names**
(`DiputadosActivos__20261009050006.json`), so a collector reads the page
first and follows the link; nothing can be guessed.

**Votes (votaciones)** -- the spine of phase 1.

- The landing page `/es/opendata/votaciones` embeds `diasVotaciones`, every
  voting day of the legislature as a JavaScript array (146 for the XV), and
  marks the legislature shown in its selector.
- `?p_p_id=votaciones&...&targetLegislatura=XV&targetDate=DD/MM/YYYY` shows
  one day: about 100 to 160 KB of HTML listing every vote under its section
  (h4), item (h5) and point (h6), with the item's **expediente number**
  (`162/000814`), the yes / no / abstention totals, and links to PDF, XML,
  JSON and a chart PNG per vote, plus a ZIP of the day (2.5 MB, mostly PDFs;
  not used).
- **One JSON per vote, about 32 KB**: totals (present, for, against,
  abstentions, not voting, assent) and **all 350 positions**, each
  `{asiento, diputado, grupo, voto}`, `voto` one of `Sí`, `No`,
  `Abstención`, `No vota`, `grupo` the group code at the vote (`GP`, `GS`,
  `GVOX`, `GSUMAR`, `GR`, `GJxCAT`, `GEH Bildu`, `GV (EAJ-PNV)`, `GMx`).
- XV totals: **2,179 votes on 676 distinct expedientes, 142 days with a vote
  file**. 2,175 have a JSON; 4 do not (below).
- Measured timings from the laptop: a day page in 0.15 to 0.5 s, a vote file
  in 0.24 s. The 145 day pages took about five minutes at the one-second
  throttle; 42 vote files with positions took under a minute.

Quirks, each handled in `tools/es_rollcalls.py` and tested:

1. **The vote JSON carries no expediente number.** Only the day page joins
   a vote to its initiative, which is why the page is archived and parsed.
2. **A deputy has no published ID.** Names only, "Surname Surname,
   Forename", identical in the vote files and the members files: on the
   sample of 42 votes (14,350 positions), **351 distinct names, 351 matched
   the members list**. The store keys members on (legislature, name).
3. **Public roll-call votes are image-only.** The investitures of
   27 and 29 September 2023 (Feijóo) and 16 November 2023 (Sánchez), and
   the article 49 reform of 18 January 2024, are "pública por
   llamamiento" and are published as a chart PNG with totals and no JSON:
   no positions in the open data. Stored with `json_url` NULL.
4. **Secret ballots have a JSON with no names** (the suplicatorio of
   30 September 2026: totals 340-0-0, empty `votaciones`).
5. The JSON date is unpadded (`30/9/2026`); the page dates are padded.
6. Votes by points share an item; the point label ("Votación separada por
   puntos. Punto 1.a") comes from the page, an amendment block's label
   ("Enmiendas presentadas por el Grupo Parlamentario Popular... Enmiendas
   25, 26 y 30") from the JSON.

**Legislative initiatives (iniciativas)**: `ProyectosDeLey` (115 in the XV,
365 KB) and `ProposicionesDeLey` (369, 727 KB; types 122 groups, 123 Senate,
124 and 125 autonomous parliaments), plus `IniciativasLegislativasAprobadas`
(161 laws, 78 KB) and `PropuestasDeReforma` (statutes of autonomy). Each
record: type, title (`OBJETO`), expediente, author, dates, procedure, current
status, committee, rapporteurs, the full procedural history and BOCG links.
**Not in the files**: proposiciones no de ley (161/162), motions (173),
written and oral questions (184, 180), interpellations, constitutional
reforms (100/102), popular legislative initiatives (120). Those exist in the
votes (by title and expediente) and in the search below.

**Initiative search, all types**: the "búsqueda de iniciativas" page posts
to a JSON endpoint
(`/es/busqueda-de-iniciativas?p_p_id=iniciativas&p_p_lifecycle=2&p_p_resource_id=filtrarListado`)
with legislature, title, text, author, type, dates and page fields. It
answers our UA. Its text search appears to match titles only, and its counts
look low for written questions, so recall is unverified. XV counts, all
initiative types, measured: `inmigración` 237, `Ley Trans` 35, `interrupción
voluntaria del embarazo` 30, `prostitución` 30, `libertad de expresión` 28,
`cuidados paliativos` 28, `trata de seres humanos` 22, `identidad de género`
17, `aborto` 15, `libertad religiosa` 13, `eutanasia` 11, `pornografía` 11,
`Valle de los Caídos` 10, `objeción de conciencia` 6, `terapias de
conversión` 3, `gestación subrogada` 0, `pin parental` 0 (control:
`vivienda` 1,351). Phase 2 material for PNLs and questions, not phase 1.

**Deputies (diputados)**: `DiputadosActivos` (137 today, 85 KB) and
`DiputadosDeBaja` (275, 185 KB): name, constituency, electoral list,
parliamentary group, dates of taking and leaving the seat and of group
membership, a short biography. Also `Diputadas`, `Diput` and
declarations of economic activities (`docacteco`).

**Speeches (intervenciones)**: one file for the whole legislature,
`IntervencionesCronologicamente` (**56 MB JSON, 42,448 interventions**,
25 s to fetch) and `IntervencionesIniciativa`: speaker, office, organ,
initiative and phase, start and end times, and links to the video, the
full text (Diario de Sesiones) and the PDF page. That is the Hansard
equivalent for debate packs, with timecodes, which the Bundestag lacks.

**Agenda**: `/es/agenda` (HTML, the week's schedule) and the plenary
calendar. No structured feed; a scraper if the week-ahead section is wanted.

### Senado: BLOCKED from the laptop and from GitHub's runners

`www.senado.es` answered **403 Access Denied (Akamai) on every URL**,
homepage included, from the laptop (honest UA and curl's default alike) and
from a GitHub runner (one-off probe workflow, run 37881517334, then
removed). Fifteen URLs from the runner: the homepage, the open-data
catalogue, the open-data servlet (`ficopendataservlet?tipoFich=1..12&legis=15`)
and the plenary sessions page. It is not a laptop or VPN problem, unlike senate.gov.
A browser User-Agent was NOT tried: the house rule is that a per-host UA
exception is Christopher's decision (as for business.senedd.wales and
www.gov.wales), and probing with one would be working around the block
before anyone has agreed to.

How much it matters: the Senado's decisions reach the Congreso floor. The
XV Congreso voted **249 times on "Enmiendas del Senado"**, and a Senate veto
must be lifted in the Congreso, so the outcome of every bill is visible from
the Congreso alone. What is lost is how each senator voted (the PP held an
absolute majority there) and Senate-only business (motions, questions).

### Also open and keyless

- **BOE open data** (`www.boe.es/datosabiertos/api/boe/sumario/<yyyymmdd>`,
  JSON, about 300 KB a day): every act published, which is how the
  dissolution decree was found. Laws in force and royal decree-laws for a
  later phase.

## Phase 1: built, 9 October 2026

`tools/es_rollcalls.py` into `es_members`, `es_initiatives`, `es_divisions`,
`es_votes` and `es_vote_days` (schema in `src/es_store.py`, declared in
`db.TABLES`). Live run into a scratch database (not the store), whole XV:

| | Read | Notes |
|---|---|---|
| Voting days | 146 | 142 with vote files, 4 image-only |
| Plenary votes | 2,179 | titles, expedientes, page totals |
| Votes with positions read | 42 | the two most recent full days, to prove the path |
| Positions | 14,350 | 350 per vote, secret ballot 0 |
| Legislative initiatives | 484 | |
| Member records | 412 | 137 sitting, 275 departed |

- **Keys**: an initiative is `<legislature>/<type>/<number>`
  (`15/122/000072`); a division `congreso-<legislature>-<session>-<vote>`
  (`congreso-15-196-1`). Never a title.
- **Areas stay NULL until the Spanish taxonomy exists.** NULL is
  "unclassified", `[]` is "classified, nothing found". Only
  `config/watchlist-es.yaml`, applied by initiative key, lends areas now.
  `--taxonomy <file>` classifies with a draft; `--reclassify` re-derives
  offline.
- **A vote inherits its initiative's areas** (`own_areas` keeps its own),
  as in the US; here it matters less, because every vote prints its item's
  full title.
- **Re-reads**: voting days not yet stored, and every day of the last
  fortnight; then every vote file whose positions are missing. A run cut
  short by the budget resumes from the store.
- **Exit codes**: 0 clean, 3 stored what it could and recorded gaps (the
  job still publishes), 1 otherwise.

**The weekly** (`jobs/es-weekly.sh`, shared by both runners): Saturdays
08:30 London on the Mac Mini (`ops/launchd/net.citizengo.parlmonitor.es-weekly.plist`);
`.github/workflows/es-weekly.yml` at 08:30 and 11:30 UTC (half an hour later than first built, Switzerland holding 11:00) is the backup,
gated by `mini-check` with job `ES_WEEKLY` (grace 260 minutes, because the
Mini's summer run stamps 07:00 UTC, four hours before the retry slot). The
plenary sits Tuesday to Thursday; Saturday reads the whole week. **It runs
only once merged to main**: GitHub schedules from the default branch.

**The first run is a backfill and is announced here** (the Germany rule):
about 2,170 vote files plus 146 day pages, one request a second. At the
measured timings that is roughly 50 minutes; the job's 45-minute budget
stops it cleanly and the second Saturday finishes it. It should run on the
Mini, not the laptop.

Tests: `tests/test_es_rollcalls.py`, 33 tests on real responses saved on
9 October (`tests/fixtures/es/`, 132 KB): the calendar, a day page, an
investiture page, three vote files (amendments, points, secret ballot),
members and initiatives subsets.

## Proposed Spanish taxonomy (v0.1, FOR APPROVAL)

Drafted by Claude on 9 October 2026, measured against the XV corpus above
(2,179 votes, 484 bills), **not yet read by a Spanish speaker who
campaigns**. Written in the generator's format, so once approved it lifts
straight into `docs/keyword-taxonomy-es.md` and `python3
tools/generate_taxonomy.py --lang es` produces `config/taxonomy-es.yaml`
(that also needs `"es"` added to `MASTERS` in `tools/generate_taxonomy.py`,
a one-line shared edit not made yet).

**For the merge with Argentina and Mexico**: each area has a `Spain only`
line naming the terms that are Spanish law or Spanish usage (statute
numbers, `Ley Trans`, `pin parental`, `LOMLOE`, `Valle de los Caídos`,
`inmatriculaciones`, `Ley Mordaza`, `artículo 510`, `tercería locativa`).
Everything else is ordinary Spanish legal and political vocabulary and
should be shared. The generator ignores the `Spain only` lines, so a merged
file can keep them as provenance or split them into country addenda.
`ILE` / `interrupción legal del embarazo` are Mexico's words and `IVE` is
Argentina's as well as Spain's; both are in the shared list.

Spanish matching traps that shaped the list:

- **Plurals and gender inflect the end of the word**: `aborto` /
  `abortos`, `objetor` / `objetoras`, `trasplante` / `trasplantes`. A term
  without `*` is anchored on both sides, so nouns carry a trailing `*`, and
  inflecting words inside a phrase carry an internal one (`"terapia* de
  conversión"`).
- **Accents are part of the word.** Official text is fully accented, and
  `embrion*` does not match `embrión`; both are listed.
- **Short words never stand alone**: `vida` ("calidad de vida", "vida
  laboral"), `familia`, `género`
  ("géneros alimenticios"), `sexo`, `menores`, `matrimonio`, `libertad`,
  `religión`, `educación`, `odio`, `trans`. They appear only inside phrases
  or with guards.
- **`crianza` was dropped**: it is also a wine classification.
- **Acronyms are case-sensitive** under the filter convention (`IVE`,
  `LORE`, `LOMLOE`, `LOLR`, `LGTBI`, `FIV`), which is correct: lower case
  `ive` or `fiv` would match inside other words.

### 1. Abortion {#1_abortion}

- **Tier 1:** aborto*; abortiv*; "interrupción voluntaria del embarazo"; "interrupción legal del embarazo"; "interrupción del embarazo"; IVE; ILE; "Ley Orgánica 2/2010"; "172 quater"; objetor* [with: aborto, interrupción, embarazo, sanitari]; "registro de objetores"; "píldora abortiva"; mifepristona; misoprostol; provida; "pro vida"; "no nacido*"; nasciturus; "derecho a la vida" [with: concebido, nacer, embarazo, aborto, gestación]; "síndrome post aborto"; "síndrome postaborto"; "reforma del artículo 43" [with: Constitución]
- **Tier 2:** "salud sexual y reproductiva"; "derechos sexuales y reproductivos"; "salud reproductiva"; anticoncepci*; anticonceptiv*; "píldora del día después"; "anticoncepción de emergencia"; "acoso" [with: clínica, aborto, interrupción del embarazo]; "diagnóstico prenatal"; "vida prenatal"; "duelo gestacional"; "muerte perinatal"; "maternidad vulnerable"; "mujeres embarazadas" [with: ayuda, apoyo, vulnerab]
- **Spain only:** "Ley Orgánica 2/2010"; "172 quater"; "registro de objetores"; "síndrome post aborto"; "síndrome postaborto"; "reforma del artículo 43"
- **Notes:** `aborto` and `interrupción voluntaria del embarazo` (IVE) are the political and the legal names; both at tier 1. `Ley Orgánica 2/2010` is the abortion law; `172 quater` is the Penal Code article (2022) that made harassment near clinics an offence, Spain's buffer zone; the `registro de objetores` is the conscientious-objector register the 2023 reform created. `síndrome post aborto` names the 2025 Madrid fight over information given to women. MEASURED: 3 XV votes (the article 43 reform, two PNLs). Contraception at tier 2 follows the US decision; confirm for Spain.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanasia*; eutanási*; "suicidio asistido"; "suicidio médicamente asistido"; "ayuda para morir"; "prestación de ayuda para morir"; "muerte digna"; "morir dignamente"; "Ley Orgánica 3/2021"; LORE; "Comisión de Garantía y Evaluación"; "donación tras eutanasia"
- **Tier 2:** "cuidados paliativos"; paliativ*; "sedación paliativa"; "testamento vital"; "instrucciones previas"; "voluntades anticipadas"; "final de la vida"; "fin de la vida"; "prevención del suicidio"
- **Spain only:** "Ley Orgánica 3/2021"; LORE; "Comisión de Garantía y Evaluación"; "instrucciones previas"
- **Notes:** `eutanasia` is the plain term; the LORE (Ley Orgánica 3/2021) calls the act `prestación de ayuda para morir`, and the regional `Comisión de Garantía y Evaluación` approves each case. `morir dignamente` joined on measurement: a Catalan parliament bill (15/125/000014) used it and nothing else. `instrucciones previas` is the statutory name of the living will; palliative care is the positive flank, tier 2, as in English.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "bloqueador* de la pubertad"; "bloqueador* puberal*"; "bloqueo puberal"; "hormonación cruzada"; "hormonas cruzadas"; "disforia de género"; "incongruencia de género"; "menores trans"; "infancia trans"; "niños trans"; "niñas trans"; "adolescentes trans"; "reasignación de sexo"; "reasignación sexual"; "cirugía de reasignación"; detransici*; destransici*
- **Tier 2:** "transición de género" [with: menor, niño, niña, adolescente, infancia]; "tratamiento hormonal" [with: menor, niño, niña, adolescente, género, trans]; "afirmación de género"; "unidades de identidad de género"; "identidad de género" [with: menor, niño, niña, adolescente, infancia, escuela, colegio]
- **Spain only:** "unidades de identidad de género"
- **Notes:** The Spanish debate names `bloqueadores de la pubertad`, `menores trans` and the regional `unidades de identidad de género` (hospital gender units). `identidad de género` is guarded here to children and schools; it is unguarded in area 5. MEASURED: no XV plenary vote matched; this ground has been regional in Spain.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "terapia* de conversión"; "terapia* de aversión"; "terapias de conversión, aversión o contracondicionamiento"; contracondicionamiento; "prácticas de conversión"
- **Tier 2:** "acompañamiento espiritual" [with: conversión, orientación, identidad]; "asesoramiento" [with: conversión, orientación sexual, identidad de género]
- **Spain only:** "terapias de conversión, aversión o contracondicionamiento"; contracondicionamiento
- **Notes:** `terapias de conversión, aversión o contracondicionamiento` is the wording of Ley 4/2023, kept verbatim. MEASURED: 10 votes, all on the PSOE bill to make conversion therapy a criminal offence: taken into consideration on 24 June 2025, amendments and the final vote of the whole (an organic law) on 25 June 2026.

### 5. Sex-based rights and gender identity {#5_sex_based_rights}

- **Tier 1:** "Ley Trans"; "Ley 4/2023"; "igualdad real y efectiva de las personas trans"; "autodeterminación de género"; "autodeterminación de sexo"; "autodeterminación del sexo"; "autodeterminación de la identidad"; "rectificación registral"; "mención registral relativa al sexo"; "cambio de sexo registral"; "identidad de género"; "expresión de género"; "ideología de género"; "personas trans"; transexual*; transgénero*; "no binari*"; LGTBI*; LGBTI*; LGTB; LGBT; "Ley Zerolo"; "Ley 15/2022"; "igualdad de trato y la no discriminación"; "Convenio de Estambul"
- **Tier 2:** "perspectiva de género" [with: educación, escuela, menores, currículo, infancia]; "violencia de género"; "violencia machista"; "violencia sexual"; "libertad sexual"; "solo sí es sí"; "Ley Orgánica 10/2022"; feminicidio*; femicidio*; "categoría femenina"; "deporte femenino" [with: trans, sexo, identidad]; "espacios seguros" [with: mujeres, sexo]; "lenguaje inclusivo"; "orientación sexual"; "diversidad sexual"; "Ministerio de Igualdad"
- **Spain only:** "Ley Trans"; "Ley 4/2023"; "igualdad real y efectiva de las personas trans"; "mención registral relativa al sexo"; "Ley Zerolo"; "Ley 15/2022"; "solo sí es sí"; "Ley Orgánica 10/2022"
- **Notes:** `Ley Trans` (Ley 4/2023) and `autodeterminación de género` are the centre of this area in Spain; `rectificación registral` and `mención registral relativa al sexo` are the administrative words for a change of registered sex. `Ley Zerolo` (Ley 15/2022, equal treatment) carries its speech and religion consequences here. The gender-violence terms are tier 2 and are a scope question (see Waiting on Chris): they are 21 of this area's 35 votes.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "pin parental"; "veto parental"; "derecho de los padres"; "derechos de los padres"; "derecho preferente de los padres"; "libertad de enseñanza"; "libertad educativa"; "educación afectivo-sexual"; "educación afectivo sexual"; "educación afectivosexual"; "educación sexual integral"; "educación sexual"; homeschooling; "educación en casa"; "educación en el hogar"; "educación diferenciada"; "protección de las personas menores de edad en los entornos digitales"; "entorno* digital*" [with: menores, infancia, niños, niñas, adolescentes]
- **Tier 2:** "consentimiento parental"; "consentimiento de los padres"; "patria potestad"; LOMLOE; "Ley Celaá"; "enseñanza concertada"; "escuela concertada"; "conciertos educativos"; "escolarización obligatoria"; "redes sociales" [with: menores, edad, "16 años", niños, adolescentes, escuela]; "teléfono* móvil*" [with: aula, colegio, centros educativos, escuela, menores]; "control parental"; "adoctrinamiento"
- **Spain only:** "pin parental"; "veto parental"; LOMLOE; "Ley Celaá"; "enseñanza concertada"; "escuela concertada"; "conciertos educativos"; "protección de las personas menores de edad en los entornos digitales"
- **Notes:** `pin parental` (and `veto parental`) names the parental-consent fight over school talks, Spanish and specifically Murcian in origin. `libertad de enseñanza` and the parents' right in art. 27.3 of the Constitution are the legal frame. `entorno* digital*` guarded to children joined on measurement: the PP motion on minors online (15 point votes) and the Government's bill on minors in digital environments both used it. `LOMLOE` / `Ley Celaá` is the 2020 education law, tier 2 because it is cited in all education traffic.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Tier 1:** "libertad de expresión"; "delito* de odio"; "discurso* de odio"; "incitación al odio"; "artículo 510"; "510 del Código Penal"; "Ley Mordaza"; "Ley Orgánica 4/2015"; "seguridad ciudadana" [with: libertad*, expresión, reforma, derogación]; pornograf*; "verificación de edad"; "Reglamento de Servicios Digitales"; "Ley de Servicios Digitales"; "Digital Services Act"; "apología del franquismo"
- **Tier 2:** desinformaci*; bulo*; "libertad de prensa"; "libertad de información"; censura [with: expresión, redes, prensa, internet, libros]; "cifrado de extremo a extremo"; "secreto de las comunicaciones"; "reconocimiento facial"; "euro digital"; islamofobia
- **Spain only:** "artículo 510"; "510 del Código Penal"; "Ley Mordaza"; "Ley Orgánica 4/2015"; "apología del franquismo"
- **Notes:** `artículo 510` of the Penal Code is the hate-speech offence; `Ley Mordaza` is the opponents' name for the public-security law (LO 4/2015), guarded when written out because `seguridad ciudadana` is also policing. `apología del franquismo` is the proposed offence. Democratic Memory moved to area 8, guarded, after measurement: unguarded it tagged general motions on the Government.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "libertad religiosa"; "Ley Orgánica de Libertad Religiosa"; LOLR; "libertad de conciencia"; "objeción de conciencia"; "sentimientos religiosos"; escarnio; blasfemia*; "Acuerdos con la Santa Sede"; "Santa Sede"; "Valle de los Caídos"; Cuelgamuros; inmatricula*; cristianofobia; "persecución de cristianos"; "cristianos perseguidos"; "minorías religiosas"; "minoría religiosa"; "asistencia religiosa"; capellan*
- **Tier 2:** "Iglesia católica"; "Conferencia Episcopal"; "asignación tributaria"; "casilla de la Iglesia"; "lugares de culto"; "confesiones religiosas"; "entidades religiosas"; "asignatura de Religión"; "clase de Religión"; "enseñanza de la religión"; "símbolos religiosos"; crucifijo*; "abusos" [with: Iglesia, clero, religios]; "Memoria Democrática" [with: Valle de los Caídos, Cuelgamuros, basílica, Iglesia, religios]
- **Spain only:** LOLR; "Acuerdos con la Santa Sede"; "Valle de los Caídos"; Cuelgamuros; inmatricula*; "asignación tributaria"; "casilla de la Iglesia"; "Conferencia Episcopal"; "Memoria Democrática"
- **Notes:** `sentimientos religiosos` and `escarnio` are the Penal Code's offence against religious feelings (art. 525), whose repeal has been proposed. `inmatriculaciones` are the Church's property registrations; `Valle de los Caídos` / `Cuelgamuros` the basilica's resignification under the Democratic Memory law. MEASURED: 1 XV vote (a PP non-binding motion on persecuted Christians).

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "matrimonio entre personas del mismo sexo"; "matrimonio homosexual"; "Ley de Familias"; "Ley de familias"; "diversidad familiar"; "protección a la familia"; "protección de la familia"; "matrimonio infantil"; poligamia; "perspectiva de familia"
- **Tier 2:** "familias numerosas"; natalidad; "invierno demográfico"; "permiso por nacimiento"; "permiso de maternidad"; "permiso de paternidad"; "custodia compartida"; divorcio*; "familias monoparentales"; "parejas de hecho"; adopción [with: menores, familia, parejas]; "conciliación de la vida familiar"; "corresponsabilidad familiar"
- **Spain only:** "Ley de Familias"; "Ley de familias"
- **Notes:** `Ley de Familias` is the lapsed Government family bill (15/121/000011) and two group bills. `perspectiva de familia` and `corresponsabilidad familiar` joined on measurement: both name pro-family bills the first draft missed. `matrimonio` never stands alone. Birth and parental leave sit at tier 2: they match labour decree-laws, which triage should read and mostly drop.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "gestación subrogada"; "gestación por sustitución"; "maternidad subrogada"; "vientre* de alquiler"; "reproducción asistida"; "reproducción humana asistida"; "Ley 14/2006"; embrion*; embrión; "fecundación in vitro"; "diagnóstico genético preimplantacional"; clonación; "edición genética"; "células madre embrionarias"
- **Tier 2:** "donación de óvulos"; "donación de gametos"; "donación de semen"; FIV; "investigación biomédica"; "Ley 14/2007"; filiación [with: gestación, subrogada, sustitución, extranjero]; "preservación de la fertilidad"; "congelación de óvulos"
- **Spain only:** "Ley 14/2006"; "Ley 14/2007"
- **Notes:** `gestación por sustitución` is the legal term (Ley 14/2006, art. 10, which voids surrogacy contracts); `vientres de alquiler` is the term both feminist and conservative critics use. MEASURED: nothing in the XV plenary, and no initiative of any type titled with any surrogacy term.

### 11. Migration {#11_migration}

- **Tier 1:** inmigración; inmigrante*; migrante*; extranjería; "Ley de Extranjería"; "protección internacional"; asilo; refugiad*; "regularización extraordinaria"; "menores extranjeros no acompañados"; "menores migrantes no acompañados"; "devoluciones en caliente"; "centros de internamiento de extranjeros"; "Pacto Europeo sobre Migración y Asilo"
- **Tier 2:** migración; migratori*; cayuco*; patera*; "nacionalidad española" [with: concesión, adquisición]; deportaci*
- **Spain only:** "Ley de Extranjería"; "devoluciones en caliente"; "centros de internamiento de extranjeros"; cayuco*; patera*
- **Notes:** Collated, never campaigned, hidden on every surface (`HIDDEN_AREAS = (11,)`). Drafted briefly, to file items rather than raise them. 32 XV votes matched area 11 alone.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Tier 1:** prostituci*; proxenetismo; proxeneta*; "tercería locativa"; "trata de seres humanos"; "trata de personas"; "trata con fines de explotación sexual"; "explotación sexual"; "abolición de la prostitución"; abolicionis* [with: prostitución, trata, explotación]; "compra de sexo"; "matrimonio* forzado*"
- **Tier 2:** "trabajo sexual"; "trabajadoras sexuales"; "trabajadores sexuales"; prostíbulo*; "abuso sexual infantil"; "explotación sexual infantil"; "agresión sexual" [with: menores, infancia]; "material de abuso sexual infantil"; "indemnidad sexual*"
- **Spain only:** "tercería locativa"
- **Notes:** `tercería locativa` is the Spanish offence of profiting from premises used for prostitution, the centre of the abolitionist bills. `matrimonio forzado` sits here, as `Zwangsheirat` does in German. MEASURED: 4 votes, including the PSOE bill to prohibit proxenetismo in all its forms.

### 13. Organ donation {#13_organ_donation}

- **Tier 1:** "donación de órganos"; "trasplante* de órganos"; "tráfico de órganos"; "turismo de trasplantes"; "Organización Nacional de Trasplantes"; "donación tras eutanasia"
- **Tier 2:** trasplante*; "donante* de órganos"; "donación en asistolia"; "muerte encefálica"; "consentimiento presunto"
- **Spain only:** "Organización Nacional de Trasplantes"
- **Notes:** Spain has had presumed consent since 1979 and leads the world in donation rates through the `Organización Nacional de Trasplantes`, so the live questions are donation after euthanasia and living donors. `trasplante*` at tier 2 is the positive flank. MEASURED: 2 votes (living-donor protection).

### Global exclusions (advisory)

vida; familia; género; sexo; menores; matrimonio; libertad; religión;
educación; odio; mujer; igualdad; trans. These bare words must never become
terms on their own; where the concept is needed it appears above as a
phrase, a compound or guarded.

## Proposed phasing

1. **Phase 1 (built, this branch).** Congreso votes with every position,
   legislative initiatives, deputies; Mini-first weekly; unclassified until
   the taxonomy is approved.
2. **Phase 1b (after approval).** Generate `config/taxonomy-es.yaml`, then
   dispatch `es-weekly` with "reclassify". The numbers above become the
   store's.
3. **Phase 2.** PNLs, motions and written questions through the initiative
   search endpoint (or per-initiative pages); the week-ahead agenda; laws
   in force from the BOE. This is where most of Spain's activity on our
   ground lives.
4. **Phase 3.** The Spanish edition and DM (`tools/es_monitor.py`, the
   `us_monitor.py` pattern), debate packs from `intervenciones` (timecoded
   text and video), and a Spanish 5CA: per-deputy positions are complete
   for every recorded vote, keyed by name.
5. **Phase 4.** The Senado once access is settled, then the autonomous
   parliaments.

No edition exists yet and nothing is sent anywhere. With the Cortes
dissolved, the sensible order is taxonomy review now, the edition for the
XVI's first votes in January 2027.

## Regions (later, not probed)

Seventeen autonomous community parliaments, plus the assemblies of the two
autonomous cities:

Parlamento de Andalucía; Cortes de Aragón; Junta General del Principado de
Asturias; Parlament de les Illes Balears; Parlamento de Canarias;
Parlamento de Cantabria; Cortes de Castilla-La Mancha; Cortes de Castilla y
León; Parlament de Catalunya; Corts Valencianes; Asamblea de Extremadura;
Parlamento de Galicia; Asamblea de Madrid; Asamblea Regional de Murcia;
Parlamento de Navarra; Parlamento Vasco (Eusko Legebiltzarra); Parlamento de
La Rioja; Asamblea de Ceuta; Asamblea de Melilla.

Two things to know before choosing: much of our ground is regional in Spain
(education curricula and the pin parental fight in Murcia, regional trans
and LGTBI laws in Madrid, Andalucía and Valencia, abortion provision through
regional health services); and Catalonia, the Basque Country, Galicia, the
Balearics and Valencia publish in co-official languages as well as Spanish,
which the Spanish taxonomy will not read.

## Shared files touched (for the merge of the country branches)

- `src/db.py`: five `es_*` names added to `TABLES`, and `es_store.ensure_schema`
  called from `init_db` (9 lines).
- `tools/coverage.py`: `Spain weekly` in `PIPELINES`, `PIPELINE_FEEDS` and
  `AWAITING_FIRST_RUN`; `es_members`, `es_initiatives` (7 + 4 days) and
  `es_divisions` (31 + 92 days, because of the dissolution: tighten to
  31 + 31 once the XVI votes) in `FEEDS`.
- `.github/workflows/alert.yml`: `"Spain weekly"` added to the watched
  workflows (1 line).

Not touched: any taxonomy file, `tools/generate_taxonomy.py`,
`tools/mini_run.sh`, `.github/workflows/mini-check.yml`. New files only
otherwise: `src/es_store.py`, `tools/es_rollcalls.py`,
`config/watchlist-es.yaml`, `jobs/es-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.es-weekly.plist`,
`.github/workflows/es-weekly.yml`, `tests/test_es_rollcalls.py`,
`tests/fixtures/es/`, this document.

## Waiting on Chris

1. **Approve or amend the Spanish terms above**, ideally after a read by
   someone in the Spanish team. Then: lift them into
   `docs/keyword-taxonomy-es.md`, add `es` to the generator, generate,
   reclassify.
2. **Scope questions the corpus raised:**
   - **Gender-violence law** (`violencia de género`, LO 1/2004, the Pacto de
     Estado): in or out? It is the largest single term (21 votes, 7 items)
     and drafted at tier 2 so triage reads it.
   - **Democratic Memory** (Ley 20/2022): drafted only where it touches the
     Valle de los Caídos / Cuelgamuros basilica or the Church. Wider?
   - **Contraception** is in area 1 at tier 2, following the US decision.
     The same for Spain?
   - **Sexual-offences law** ("solo sí es sí", LO 10/2022, "indemnidad
     sexual"): drafted at tier 2 in areas 5 and 12. Right home, or out?
   - **VOX's bill on "la dignidad de las mujeres y la seguridad ciudadana
     en el espacio público"** (15/122/000237, read as a face-covering ban
     but not verified): religious-freedom ground or not?
3. **Senado access.** Options: (a) write to the Senado's open-data contact
   asking for our UA to be let through; (b) authorise a per-host UA
   exception for www.senado.es as for the Senedd and gov.wales; (c) go
   without the Senado and rely on the Congreso's votes on Senate amendments
   and vetoes.
4. **Merge and install.** Merge `spain` to main when ready (the workflow
   schedules only from main); copy the plist to the Mini and bootstrap it.
   `MINI_LAST_ES_WEEKLY` is written by `mini_run.sh` on the first clean
   run; no secret or key is needed.
5. **The first-run backfill** (about 2,300 requests over two Saturdays, on
   the Mini): announced here; say if it should run differently.
6. **The edition**: build it now, or for the XVI's first votes in January
   2027 (recommended, given the dissolution)?
