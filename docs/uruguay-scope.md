# Uruguay: scoping the Parlamento del Uruguay monitor

Probed live on 9 October 2026, from the laptop and (for parlamento.gub.uy)
from a GitHub runner. Every number below was measured, not estimated. Raw
responses are archived under `data/raw/2026-10-09/` (`uy-probe_*` for the
scoping probes, `uy-rollcalls_*` for the collector's own first run). All
requests carried the honest CitizenGO User-Agent, one second apart, and ten
seconds apart on IMPO, whose robots.txt asks for that. National parliament
first; the departmental bodies are listed at the end for later.

## Decisions already taken (Christopher)

- **Own edition**, delivered to Christopher alone (a Slack DM), as the US.
- **Shared taxonomy concept, own language file.** `config/taxonomy.yaml` and
  every existing taxonomy file are untouched. The Spanish terms are PROPOSED
  below, built on the Spain branch's draft so the Spanish-speaking countries
  can share one list; `config/taxonomy-uy.yaml` is generated only after
  Christopher approves them.
- **Both chambers first** (Cámara de Representantes, 99 seats; Cámara de
  Senadores, 30 plus the Vice-President); departmental bodies later.
- **Mac Mini first, GitHub Actions as the backup** (the Australia and Spain
  pattern). No new paid services. Nothing posts publicly anywhere.

## The three findings that shape everything

### 1. parlamento.gub.uy refuses us, everywhere

The Parliament's own site, which holds everything the brief asks for (bills
as asuntos with their full procedural record, both chambers' agendas and
votes as published, the Senate, committees, legislators), answers
**403 Forbidden (nginx) to every path, robots.txt included**:

| From | User-Agent | Result |
|---|---|---|
| Laptop | CitizenGO honest UA | 403 on `/`, `/robots.txt`, `/transparencia/datos-abiertos` and the open-data JSON endpoints |
| Laptop | curl's own default UA | 403, same paths |
| GitHub runner (probe-hosts.yml, run 37884467042) | CitizenGO honest UA | 403 on `robots.txt`, so `tools/probe_hosts.py` stopped the host, as it must |

`infolegislativa.parlamento.gub.uy` (an IIS server) also answers 403 at its
root, from both, although four of its metadata CSVs answer the laptop. A
browser User-Agent was **not** tried: by rule we never spoof one. Whether the
block is by country, by data-centre range or by anything that is not a
browser cannot be told from here. Two honest routes remain and are on the
Waiting-on-Chris list: ask the Parliament, or try from the Mac Mini's own
connection.

This is the same open-data catalogue the Parliament advertises on
catalogodatos.gub.uy: 13 of its 24 datasets point at parlamento.gub.uy and
are, to us, dead links.

### 2. Uruguay does not record votes by name

Not a data gap but a practice. Both chambers vote by show of hands or by an
anonymous electronic register, and the Diario de Sesiones prints totals only.
Measured on the Diario of the euthanasia sitting (Cámara de Representantes,
12-13 August 2025, Diario 4578, 272 pages): **36 vote results, every one a
total**, for example

> Sesenta y cuatro votos afirmativos y veintinueve votos negativos en noventa
> y tres presentes: AFIRMATIVA.

That was the general vote on the euthanasia bill, taken by electronic
register ("Se abre el registro para proceder a la votación"), and still no
name is printed. A deputy's position is on the record only when they speak
to it ("fundar el voto"), in prose. A *votación nominal* can be requested,
but none appears in that Diario, and none is published as data anywhere we
can reach. The national open-government plans (5th and 6th) list
"votaciones nominales y no nominales" as an aspiration, not a dataset.

So **there is no Uruguayan roll-call collector to build**, and a Uruguayan
5CA could only ever be built from speeches. Totals per item can be read from
the Diario PDFs (Phase 1b below).

### 3. The English taxonomy is blind to Spanish (as in Germany and Spain)

`config/taxonomy.yaml`, unchanged, over what we can read:

| Text matched | Rows | On our ground |
|---|---|---|
| Pedidos de informes (subject line), L legislature | 2,526 | 11 (9 "Agenda 2030", 2 "Planned Parenthood") |
| Bill titles, L legislature (catalogue snapshot) | 402 | 0 |
| Bill titles, XLIX legislature (catalogue snapshot) | 923 | 0 |

**With the draft below** (Spain's shared terms plus Uruguay's), accents
folded on both sides (see "Quirks"):

| | Rows | On our ground (area 11 hidden) | Tier 1 |
|---|---|---|---|
| Pedidos de informes, L | 2,526 | **48** (29 in the last twelve months, of 1,675) | 13 |
| Bill titles, L snapshot (to 3 June 2026) | 402 | **19** | 7 |
| Bill titles, XLIX | 923 | **29** | 10 |
| Laws promulgated (IMPO), 20.380 to 20.530 | 148 | **8** | 3 |

Pedidos on our ground by area: abortion 7 (2 on IPPF), assisted dying 5,
gender medicine 1, sex-based rights 9, education 4, free speech 11 (9 on
Agenda 2030), religion 3, family 5, surrogacy 1, organ donation 2. They go mostly to the
Ministry of Public Health (18) and of Education and Culture (10), and come
mostly from the two Identidad Soberana deputies (Nicolle Salle 16, Gustavo
Salle Lorier 8): read the pedidos as a map of who works our ground, not of
how much ground there is.

Read honestly:

- **Of the 8 laws, two are substantive**: Ley 20.431 (muerte digna) and
  Ley 20.443 (raising the minimum age of marriage in the Civil Code). Two
  more are employment programmes that cite the trans job quota of Ley
  19.684 (tier 1, as they should be found, but not campaigns), and four are
  tier-2 incidentals (pregnancy screening, a missing-children alert, a
  Mercosur protection-orders treaty, a jobs programme). Laws are outcomes:
  by the time one is in IMPO the fight is over.
- **Without accent folding the bills lose a fifth**: 15 of 19 in the L
  snapshot and 21 of 29 in the XLIX, because titles are in capitals and
  often unaccented ("ADOPCION PRENATAL", "LEY DE GENERO").
- **Ley 19.580 (violence against women based on gender)** and "violencia de
  género" are 6 of the 10 bill matches in area 5. It is drafted at tier 2 and is the same scope
  question as Spain's gender-violence law.
- **The euthanasia fight is over in Parliament and now about
  implementation**: Ley 20.431, promulgated 24 October 2025, regulated by
  Decreto 76/026 of 15 April 2026. The pedidos already ask about its
  application. A referendum against a law (Constitution, art. 79) must be
  sought within a year of promulgation; for this law that window closes on
  24 October 2026. Whether anyone is collecting signatures was not checked.

## What Uruguay publishes, and what we can read

### Reachable today, keyless (built into Phase 1)

Both hosts below answer the laptop **and a GitHub runner** (probe-hosts.yml,
run 37887688765: four files, all 200, IMPO's robots.txt read and honoured), so
the backup workflow can do what the Mini does.

**Cámara de Representantes open data, `https://documentos.diputados.gub.uy/docs/`**
(Apache; plain GETs; files regenerated every evening, Last-Modified 18:34 UTC
on 8 October; UTF-8 JSON arrays):

| File | Size, time | Content (measured) |
|---|---|---|
| `DAdiputadosNomina2.json` | 65 KB, 6 s | 348 names: titulares and suplentes, NOT told apart. `Nombre` (padded with spaces), `Genero`, `Edad`, `PartidoPolitico`, `Departamento`, `HojaVotacion` (the ballot elected on). Parties: Frente Amplio 156, Nacional 108, Colorado 65, Cabildo Abierto 9, Identidad Soberana 7, Independiente 3. No member ID. Last-Modified 15 September 2026. |
| `DApedidosInformes.json` | 1.09 MB, 24 s | 2,526 pedidos de informe, 17 February 2025 to 7 October 2026 (about 130 a month): `Organismo`, `Fecha` (YYYY/MM/DD), `Autores`, `Tema`, `Estado` (CONTESTADO 1,713, VENCIDO 468, SIN CONTESTAR 304, NO ENTREGADO 41), PDF links to the request and the answer. The oficio number in the link is unique in all 2,526 rows: it is the key. |
| `DAdiarioSesiones.json` | 166 KB, 6 s | 668 Diarios de Sesiones since 2014 with their PDF links (81 for the L legislature: 52 ordinary, 14 extraordinary, 9 special). Dates are YYYY/MM/DD or, in older rows, epoch milliseconds. **Lags by months**: the newest sitting listed is 14 July 2026, although the file was regenerated on 8 October. |
| `DAbalanceLegislativo.json` | 840 KB, 32 s | Monthly activity counts (sittings, committee meetings, bills approved: 100 in the L to March 2026). Last-Modified 27 March 2026. Not collected. |
| `integracion.csv` | 28 KB | The 99 sitting deputies with e-mail addresses, but malformed (names containing commas are not quoted) and dated 2024. Not collected. |

The Diario PDFs themselves are on `http://www.diputados.gub.uy/wp-content/uploads/`
(6.2 MB, 12 s for Diario 4578) and have a text layer: `pypdf` reads them.
That host answers on **http only** (its https certificate does not name it),
and its WordPress REST API answers 403.

**IMPO, the official gazette, `https://www.impo.com.uy/bases/leyes/<n>-<year>?json=true`**:
each law as JSON (ISO-8859-1, raw line breaks inside strings, so parsed with
`strict=False`): number, year, name, promulgation and publication dates,
every article's text, signatories, references (Ley 20.431's points to its
regulating decree). 1-13 KB. Quirks, all measured:

- the year is part of the address and **a wrong year answers 200 with an HTML
  page**, not a 404; without the year it is a real 404. A hit is a JSON body.
- laws are numbered in one series: 20.380 was promulgated 25 September 2024,
  20.405 on 17 April 2025, 20.431 (muerte digna) on 24 October 2025, and
  20.530, the newest on 9 October 2026, on 23 September 2026 (published
  1 October). About 100 laws a year, about two a week.
- robots.txt: `Crawl-delay: 10`, `/bases/leyes` allowed. Honoured with a
  per-host throttle.
- IMPO reset the connection now and then (twice in eight requests during
  one scoping probe); the client's retries absorb it.

**The national catalogue, catalogodatos.gub.uy (CKAN, API keyless)**: 24
Parliament datasets. Its DataStore holds **frozen copies** of some
parlamento.gub.uy files, including the bills entered in the L legislature
(402 rows, `Fecha`, `Asunto`, `Carpetas`, `Titulo`, 18 February 2025 to
3 June 2026, harvested 5 June 2026, `update_frequency: 0`) and the XLIX
(923 rows). They are the only bill data we can reach, good for measuring the
taxonomy (above) and for knowing bills by their asunto number, but they do
not move and cannot feed a weekly. The asunto number is the key a bill would
have on parlamento.gub.uy (`/documentosyleyes/ficha-asunto/<asunto>`).

### Not reachable

- **parlamento.gub.uy**: all of it (finding 1). That includes the Senate's
  only data, the bills' procedural record (fichas), the agenda (*orden del
  día*), committees and the legislators' pages.
- **The Senate**: no source on any other host. The Senate passed the
  euthanasia law with 20 of 31 present on 15 October 2025 (news reports; the
  Senate's Diario could not be read).
- **Votes by name**: do not exist (finding 2).

## Phase 1: built, 9 October 2026

`tools/uy_rollcalls.py` (named for the country-branch convention; there are
no roll calls), `src/uy_store.py`, `config/watchlist-uy.yaml`,
`tests/test_uy_rollcalls.py` with `tests/fixtures/uy/`, and the Mini-first
weekly (`jobs/uy-weekly.sh`, `ops/launchd/net.citizengo.parlmonitor.uy-weekly.plist`,
`.github/workflows/uy-weekly.yml` gated by `mini-check` with `UY_WEEKLY`).

| Table | Key | From | Weekly cost |
|---|---|---|---|
| `uy_members` | (chamber, name as printed) | DAdiputadosNomina2.json | 1 request |
| `uy_questions` | 'L50/01105' (the oficio number) | DApedidosInformes.json | 1 request, 1 MB |
| `uy_sittings` | (chamber, Diario number) | DAdiarioSesiones.json | 1 request |
| `uy_laws` | law number | IMPO, walking from the newest stored law | about 2 hits and 3 misses, two addresses each, 10 s apart |

- **The first run** walks the laws from 20.380 (September 2024), covering the
  whole L legislature. Measured on the laptop: 148 laws in 31
  minutes (05:56 to 06:27 BST), with three numbers (20.520, 20.521,
  20.523) not yet in IMPO although 20.530 is: holes, re-asked next run. The 45-minute budget stops a slow run cleanly and the next run
  resumes from the store.
- **Holes** (a number IMPO skipped and published later) are re-asked on each
  run, up to ten.
- **Areas stay NULL** until `config/taxonomy-uy.yaml` exists; only the
  watchlist lends areas (Ley 20.431 to area 2 today). Then
  `UY_RECLASSIFY=true` (or the workflow's "reclassify" input) re-derives
  everything offline.
- **Accent folding** happens in `tools/uy_rollcalls.py` on both the terms and
  the text, so `src/filter.py` stays untouched.
- **Run live on 9 October** into a scratch store: 348 members, 2,526
  pedidos, 668 sittings, 148 laws (131 of them promulgated in the L
  legislature), no gaps, exit 0.

Tests: `tests/test_uy_rollcalls.py`, 20 tests on real responses (the euthanasia
law, a 2026 law, IMPO's wrong-year page, trimmed Cámara files), all passing.
The full suite: see "Test results" at the end.

## Quirks (observed, all of them)

- Titles and subjects are in **capitals and often unaccented**; the shared
  filter matches accents exactly. Folded on both sides in the UY collector.
  Spain's text is fully accented, so a shared Spanish file still works there;
  Argentina, Mexico and the others should check their own sources.
- Member names are padded with trailing spaces in the JSON, and there is no
  member ID anywhere we can read; the key is the printed name.
- The roll mixes titulares and suplentes (348 names for 99 seats), with no
  flag between them.
- The Diario index runs about three months behind the sittings.
- IMPO's wrong-year page is a 200; IMPO occasionally resets connections.
- www.diputados.gub.uy works on http only.

## Proposed Uruguayan Spanish taxonomy (v0.1, FOR APPROVAL)

Drafted by Claude on 9 October 2026 on top of **the Spain branch's v0.1
(docs/spain-scope.md on branch `spain`)**: every Spanish term not marked
"Spain only" is kept, Spain's own statute names are dropped (listed per area),
and Uruguay's are added (the "Uruguay only" lines). Measured against the
corpus above (183 tier-1 and 155 tier-2 terms), **not yet read by a
Uruguayan who campaigns**. Written in the
generator's format, so once approved it lifts into
`docs/keyword-taxonomy-uy.md` and `python3 tools/generate_taxonomy.py --lang uy`
produces `config/taxonomy-uy.yaml` (that needs `"uy"` added to `MASTERS` in
`tools/generate_taxonomy.py`, a one-line shared edit not made yet). If
Christopher prefers ONE shared Spanish file for every country, the
"Uruguay only" lines are this country's addendum and the shared terms are
exactly Spain's.

Changes to the shared Spanish terms that Uruguay's corpus asked for, and
which Spain may want too: a veto on `eutanasia*` for animals (a pedido about
a stranded orca matched), `IPPF` / `Planned Parenthood` and `Agenda 2030`
(asked about by name, caught by the English list only).

### 1. Abortion {#1_abortion}

- **Tier 1:** aborto*; abortiv*; "interrupción voluntaria del embarazo"; "interrupción legal del embarazo"; "interrupción del embarazo"; IVE; ILE; objetor* [with: aborto, interrupción, embarazo, sanitari]; "píldora abortiva"; mifepristona; misoprostol; provida; "pro vida"; "no nacido*"; nasciturus; "derecho a la vida" [with: concebido, nacer, embarazo, aborto, gestación]; "Ley 18.987"; "Ley N° 18.987"; "Ley Nº 18.987"; "18.987"; "derecho a nacer"; "adopción prenatal"
- **Tier 2:** "salud sexual y reproductiva"; "derechos sexuales y reproductivos"; "salud reproductiva"; anticoncepci*; anticonceptiv*; "píldora del día después"; "anticoncepción de emergencia"; "acoso" [with: clínica, aborto, interrupción del embarazo]; "diagnóstico prenatal"; "vida prenatal"; "duelo gestacional"; "muerte perinatal"; "maternidad vulnerable"; "mujeres embarazadas" [with: ayuda, apoyo, vulnerab]; IPPF; "Planned Parenthood"; "Federación Internacional de Planificación Familiar"; "Ley 18.426"; "18.426"; "nacidos sin vida"; "nacido sin vida"; "controles de embarazo"
- **Uruguay only:** "Ley 18.987"; "Ley N° 18.987"; "Ley Nº 18.987"; "18.987"; "derecho a nacer"; "adopción prenatal"; IPPF; "Planned Parenthood"; "Federación Internacional de Planificación Familiar"; "Ley 18.426"; "18.426"; "nacidos sin vida"; "nacido sin vida"; "controles de embarazo"
- **Dropped as Spain only:** "172 quater"; "Ley Orgánica 2/2010"; "reforma del artículo 43"; "registro de objetores"; "síndrome post aborto"; "síndrome postaborto"
- **Notes:** Abortion has been legal on request to 12 weeks since Ley 18.987 (2012); the live ground is its application (objection, the 2024 figures, questions to the MSP) and the pro-life flank: `adopción prenatal` (asunto 171125, re-filed in March 2026) and `nacidos sin vida` (Ley 20.377, recognition of stillborn children). `IVE` is the official abbreviation. IPPF and Agenda 2030 were added because Identidad Soberana deputies ask about both by name (the English list caught them; the Spanish draft did not). MEASURED: 7 pedidos (2 on IPPF), 2 L50 bills, 4 L49 bills.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanasia* [without: animal*, orca*, mascota*, perro*, canin*, felin*, veterinari*]; eutanási* [without: animal*, orca*, mascota*, perro*, canin*, felin*, veterinari*]; "suicidio asistido"; "suicidio médicamente asistido"; "ayuda para morir"; "prestación de ayuda para morir"; "muerte digna"; "morir dignamente"; "donación tras eutanasia"; "Ley 20.431"; "Ley N° 20.431"; "20.431"; "Comisión Honoraria de Revisión"
- **Tier 2:** "cuidados paliativos"; paliativ*; "sedación paliativa"; "testamento vital"; "voluntades anticipadas"; "final de la vida"; "fin de la vida"; "prevención del suicidio"; "Ley 18.473"; "voluntad anticipada"; "Ley 20.179"
- **Uruguay only:** "Ley 20.431"; "Ley N° 20.431"; "20.431"; "Comisión Honoraria de Revisión"; "Ley 18.473"; "voluntad anticipada"; "Ley 20.179"
- **Dropped as Spain only:** "Comisión de Garantía y Evaluación"; "Ley Orgánica 3/2021"; "instrucciones previas"; LORE
- **Notes:** Ley 20.431 (muerte digna, 2025) is now the law; its `Comisión Honoraria de Revisión` and Decreto 76/026 are the implementation ground. Animal euthanasia is vetoed (a pedido on a stranded orca matched otherwise). Palliative care (Ley 20.179) at tier 2. MEASURED: 5 pedidos, the bill itself (asunto 165490), and the 2022 Pasquet bill in L49.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "bloqueador* de la pubertad"; "bloqueador* puberal*"; "bloqueo puberal"; "hormonación cruzada"; "hormonas cruzadas"; "disforia de género"; "incongruencia de género"; "menores trans"; "infancia trans"; "niños trans"; "niñas trans"; "adolescentes trans"; "reasignación de sexo"; "reasignación sexual"; "cirugía de reasignación"; detransici*; destransici*
- **Tier 2:** "transición de género" [with: menor, niño, niña, adolescente, infancia]; "tratamiento hormonal" [with: menor, niño, niña, adolescente, género, trans]; "afirmación de género"; "identidad de género" [with: menor, niño, niña, adolescente, infancia, escuela, colegio]
- **Uruguay only:** (none)
- **Dropped as Spain only:** "unidades de identidad de género"
- **Notes:** Shared Spanish terms only. MEASURED: one pedido (bloqueo puberal and hormones for minors, to the MSP).

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "terapia* de conversión"; "terapia* de aversión"; "prácticas de conversión"
- **Tier 2:** "acompañamiento espiritual" [with: conversión, orientación, identidad]; "asesoramiento" [with: conversión, orientación sexual, identidad de género]
- **Uruguay only:** (none)
- **Dropped as Spain only:** "terapias de conversión, aversión o contracondicionamiento"; contracondicionamiento
- **Notes:** Shared Spanish terms only. MEASURED: nothing in the corpus.

### 5. Sex-based rights and gender identity {#5_sex_based_rights}

- **Tier 1:** "autodeterminación de género"; "autodeterminación de sexo"; "autodeterminación del sexo"; "autodeterminación de la identidad"; "rectificación registral"; "cambio de sexo registral"; "identidad de género"; "expresión de género"; "ideología de género"; "personas trans"; transexual*; transgénero*; "no binari*"; LGTBI*; LGBTI*; LGTB; LGBT; "igualdad de trato y la no discriminación"; "Convenio de Estambul"; "Ley 19.684"; "Ley N° 19.684"; "19.684"; "Ley integral para personas trans"; "cupo trans"
- **Tier 2:** "perspectiva de género" [with: educación, escuela, menores, currículo, infancia]; "violencia de género"; "violencia machista"; "violencia sexual"; "libertad sexual"; feminicidio*; femicidio*; "categoría femenina"; "deporte femenino" [with: trans, sexo, identidad]; "espacios seguros" [with: mujeres, sexo]; "lenguaje inclusivo"; "orientación sexual"; "diversidad sexual"; "Ministerio de Igualdad"; "Ley 19.580"; "Ley N° 19.580"; "Ley Nº 19580"; "19.580"; "violencia basada en género"; "violencia hacia las mujeres basada en género"; "Ley de género"; "equidad y género"
- **Uruguay only:** "Ley 19.684"; "Ley N° 19.684"; "19.684"; "Ley integral para personas trans"; "personas trans"; "cupo trans"; "Ley 19.580"; "Ley N° 19.580"; "Ley Nº 19580"; "19.580"; "violencia basada en género"; "violencia hacia las mujeres basada en género"; "Ley de género"; "equidad y género"
- **Dropped as Spain only:** "Ley 15/2022"; "Ley 4/2023"; "Ley Orgánica 10/2022"; "Ley Trans"; "Ley Zerolo"; "igualdad real y efectiva de las personas trans"; "mención registral relativa al sexo"; "solo sí es sí"
- **Notes:** Ley 19.684 (Ley integral para personas trans, 2018, with its job quota, `cupo trans`) is the centre. Ley 19.580 (violence against women based on gender) is tier 2 and is the same scope question as Spain's gender-violence law: 6 of this area's bill matches are 19.580 amendments. MEASURED: 9 pedidos (pride flags on public buildings, gender ideology in schools), 5 bills in each legislature.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "derecho de los padres"; "derechos de los padres"; "derecho preferente de los padres"; "libertad de enseñanza"; "libertad educativa"; "educación afectivo-sexual"; "educación afectivo sexual"; "educación afectivosexual"; "educación sexual integral"; "educación sexual"; homeschooling; "educación en casa"; "educación en el hogar"; "educación diferenciada"; "entorno* digital*" [with: menores, infancia, niños, niñas, adolescentes]; "ESI"
- **Tier 2:** "consentimiento parental"; "consentimiento de los padres"; "patria potestad"; "escolarización obligatoria"; "redes sociales" [with: menores, edad, "16 años", niños, adolescentes, escuela]; "teléfono* móvil*" [with: aula, colegio, centros educativos, escuela, menores]; "control parental"; "adoctrinamiento"; "Código de la Niñez y la Adolescencia"; "Código de la Niñez y Adolescencia"; "Código de la Niñez"; "Ley General de Educación"; "Ley 18.437"; ANEP [with: sexual, género, padres, laicidad]; "Comisionado Parlamentario para la Niñez"
- **Uruguay only:** "educación sexual"; "ESI"; "Código de la Niñez y la Adolescencia"; "Código de la Niñez y Adolescencia"; "Código de la Niñez"; "Ley General de Educación"; "Ley 18.437"; ANEP [with: sexual, género, padres, laicidad]; "Comisionado Parlamentario para la Niñez"
- **Dropped as Spain only:** "Ley Celaá"; "conciertos educativos"; "enseñanza concertada"; "escuela concertada"; "pin parental"; "protección de las personas menores de edad en los entornos digitales"; "veto parental"; LOMLOE
- **Notes:** `educación sexual` is unguarded in Uruguay (ESI is the official programme). ANEP (the public education administration) is guarded to sex, gender and laicidad. The Código de la Niñez y la Adolescencia is tier 2: cited in all child-law traffic. MEASURED: 4 pedidos, 4 L50 bills.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Tier 1:** "libertad de expresión"; "delito* de odio"; "discurso* de odio"; "incitación al odio"; "seguridad ciudadana" [with: libertad*, expresión, reforma, derogación]; pornograf*; "verificación de edad"; "Reglamento de Servicios Digitales"; "Ley de Servicios Digitales"; "Digital Services Act"
- **Tier 2:** desinformaci*; bulo*; "libertad de prensa"; "libertad de información"; censura [with: expresión, redes, prensa, internet, libros]; "cifrado de extremo a extremo"; "secreto de las comunicaciones"; "reconocimiento facial"; "euro digital"; islamofobia; "Agenda 2030"; "Ley 19.307"; "servicios de comunicación audiovisual"
- **Uruguay only:** "Agenda 2030"; "Ley 19.307"; "servicios de comunicación audiovisual"
- **Dropped as Spain only:** "510 del Código Penal"; "Ley Mordaza"; "Ley Orgánica 4/2015"; "apología del franquismo"; "artículo 510"
- **Notes:** Shared terms plus `Agenda 2030` (tier 2, as in English) and the media law (Ley 19.307). MEASURED: 11 pedidos (9 on Agenda 2030, 2 on facial recognition in a liceo).

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "libertad religiosa"; "Ley Orgánica de Libertad Religiosa"; "libertad de conciencia"; "objeción de conciencia"; "sentimientos religiosos"; escarnio; blasfemia*; "Santa Sede"; cristianofobia; "persecución de cristianos"; "cristianos perseguidos"; "minorías religiosas"; "minoría religiosa"; "asistencia religiosa"; capellan*; laicidad; "laicidad positiva"; "Estado laico"; "festividades religiosas"; "matrimonio religioso"
- **Tier 2:** "Iglesia católica"; "lugares de culto"; "confesiones religiosas"; "entidades religiosas"; "asignatura de Religión"; "clase de Religión"; "enseñanza de la religión"; "símbolos religiosos"; crucifijo*; "abusos" [with: Iglesia, clero, religios]; "Conferencia Episcopal del Uruguay"; "Conferencia Episcopal"; "Iglesia Católica"
- **Uruguay only:** laicidad; "laicidad positiva"; "Estado laico"; "minorías religiosas"; "festividades religiosas"; "matrimonio religioso"; "Conferencia Episcopal del Uruguay"; "Conferencia Episcopal"; "Iglesia Católica"; "Iglesia católica"
- **Dropped as Spain only:** "Acuerdos con la Santa Sede"; "Conferencia Episcopal"; "Memoria Democrática"; "Valle de los Caídos"; "asignación tributaria"; "casilla de la Iglesia"; Cuelgamuros; LOLR; inmatricula*
- **Notes:** `laicidad` is Uruguay's own frame (art. 5 of the Constitution); `laicidad positiva` is the term of those who want religion recognised in public life. MEASURED: 3 pedidos (laicidad in public education and in the Presidency), 2 L49 bills (religious minorities' holidays; religious marriage without prior civil marriage).

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "matrimonio entre personas del mismo sexo"; "matrimonio homosexual"; "diversidad familiar"; "protección a la familia"; "protección de la familia"; "matrimonio infantil"; poligamia; "perspectiva de familia"; "matrimonio igualitario"; "Ley 19.075"; "19.075"; homoparental*; "tenencia compartida"; "corresponsabilidad en la crianza"; "Ley 20.141"
- **Tier 2:** "familias numerosas"; natalidad; "invierno demográfico"; "permiso por nacimiento"; "permiso de maternidad"; "permiso de paternidad"; "custodia compartida"; divorcio*; "familias monoparentales"; "parejas de hecho"; adopción [with: menores, familia, parejas]; "conciliación de la vida familiar"; "corresponsabilidad familiar"; INAU [with: adopci*, sexual*, género, identidad]; "edad mínima" [with: matrimonio]; "adopciones monoparentales"; adopci* [with: menor*, niñ*, familia*, pareja*, prenatal, neonatal, hijo*]; "derecho de identidad"; "investigación de paternidad"; "subsidio* por maternidad"; "licencia* por maternidad"
- **Uruguay only:** "matrimonio igualitario"; "Ley 19.075"; "19.075"; homoparental*; "tenencia compartida"; "corresponsabilidad en la crianza"; "Ley 20.141"; INAU [with: adopci*, sexual*, género, identidad]; "edad mínima" [with: matrimonio]; "adopciones monoparentales"; adopci* [with: menor*, niñ*, familia*, pareja*, prenatal, neonatal, hijo*]; "derecho de identidad"; "investigación de paternidad"; "subsidio* por maternidad"; "licencia* por maternidad"
- **Dropped as Spain only:** "Ley de Familias"; "Ley de familias"
- **Notes:** `matrimonio igualitario` (Ley 19.075, 2013) and `homoparental*` are tier 1; `tenencia compartida` and `corresponsabilidad en la crianza` (Ley 20.141, 2023) name the shared-parenting fight. INAU (the child-protection institute) is guarded: unguarded it matched 36 pedidos about institutions. MEASURED: 5 pedidos, 4 L50 bills.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "gestación subrogada"; "gestación por sustitución"; "maternidad subrogada"; "vientre* de alquiler"; "reproducción asistida"; "reproducción humana asistida"; embrion*; embrión; "fecundación in vitro"; "diagnóstico genético preimplantacional"; clonación; "edición genética"; "células madre embrionarias"; "Ley 19.167"; "19.167"; "técnicas de reproducción humana asistida"
- **Tier 2:** "donación de óvulos"; "donación de gametos"; "donación de semen"; FIV; "investigación biomédica"; filiación [with: gestación, subrogada, sustitución, extranjero]; "preservación de la fertilidad"; "congelación de óvulos"; "subrogación de vientre"
- **Uruguay only:** "Ley 19.167"; "19.167"; "técnicas de reproducción humana asistida"; "subrogación de vientre"
- **Dropped as Spain only:** "Ley 14/2006"; "Ley 14/2007"
- **Notes:** Ley 19.167 (assisted reproduction, 2013) permits gestational surrogacy in narrow cases, so `subrogación de vientre` is its wording. MEASURED: 1 pedido, 2 L50 and 3 L49 bills, all amendments to 19.167.

### 11. Migration {#11_migration}

- **Tier 1:** inmigración; inmigrante*; migrante*; extranjería; "protección internacional"; asilo; refugiad*; "regularización extraordinaria"; "menores extranjeros no acompañados"; "menores migrantes no acompañados"; "Pacto Europeo sobre Migración y Asilo"
- **Tier 2:** migración; migratori*; "nacionalidad española" [with: concesión, adquisición]; deportaci*
- **Uruguay only:** (none)
- **Dropped as Spain only:** "Ley de Extranjería"; "centros de internamiento de extranjeros"; "devoluciones en caliente"; cayuco*; patera*
- **Notes:** Collated, never campaigned, hidden on every surface (`HIDDEN_AREAS = (11,)`). Spain's statute names dropped.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Tier 1:** prostituci*; proxenetismo; proxeneta*; "trata de seres humanos"; "trata de personas"; "trata con fines de explotación sexual"; "explotación sexual"; "abolición de la prostitución"; abolicionis* [with: prostitución, trata, explotación]; "compra de sexo"; "matrimonio* forzado*"
- **Tier 2:** "trabajo sexual"; "trabajadoras sexuales"; "trabajadores sexuales"; prostíbulo*; "abuso sexual infantil"; "explotación sexual infantil"; "agresión sexual" [with: menores, infancia]; "material de abuso sexual infantil"; "indemnidad sexual*"; "Ley 17.515"
- **Uruguay only:** "Ley 17.515"; "trabajo sexual"
- **Dropped as Spain only:** "tercería locativa"
- **Notes:** Ley 17.515 (2002) regulates sex work, so `trabajo sexual` is the legal term here, tier 2. MEASURED: 1 L49 bill.

### 13. Organ donation {#13_organ_donation}

- **Tier 1:** "donación de órganos"; "trasplante* de órganos"; "tráfico de órganos"; "turismo de trasplantes"; "donación tras eutanasia"
- **Tier 2:** trasplante*; "donante* de órganos"; "donación en asistolia"; "muerte encefálica"; "consentimiento presunto"; "Ley 18.968"; INDT; "Instituto Nacional de Donación y Trasplante"; "donante presunto"
- **Uruguay only:** "Ley 18.968"; INDT; "Instituto Nacional de Donación y Trasplante"; "donante presunto"
- **Dropped as Spain only:** "Organización Nacional de Trasplantes"
- **Notes:** Ley 18.968 (2012) made every adult a presumed donor; the Instituto Nacional de Donación y Trasplante (INDT) runs it. MEASURED: 2 pedidos, 1 L50 bill.

### Global exclusions (advisory)

vida; familia; género; sexo; menores; matrimonio; libertad; religión;
educación; odio; mujer; igualdad; trans. As for Spain: never terms on their
own.

## Proposed phasing

1. **Phase 1 (built, this branch).** Cámara roll, pedidos de informes, Diario
   index, laws from IMPO; Mini-first weekly; unclassified until the taxonomy
   is approved.
2. **Phase 1b (after approval).** Generate `config/taxonomy-uy.yaml`,
   reclassify. Then, optionally, **vote totals from the Diario PDFs**: each
   numbered item ("43.- Muerte digna (Regulación)") followed by its "X en Y:
   AFIRMATIVA" or "X votos afirmativos y Z negativos en Y presentes" lines,
   for the sittings whose items are on our ground. Totals only, months late,
   Cámara only; useful for the record, not for alerts.
3. **Phase 2, only if parlamento.gub.uy opens to us.** Bills (asuntos) with
   their full record in both chambers, the Senate, the agendas, committees:
   everything the weekly really needs. The open-data endpoints are already
   listed in the national catalogue (`asuntos-entrados`, `repartidos`,
   `actividad`, `leyes-promulgadas`, `pedidos-informe` for the Senate), so
   the collector would be short.
4. **Phase 3.** The edition and DM (`tools/uy_monitor.py`, the US pattern).
   No 5CA: there are no recorded positions to score.

No edition exists yet and nothing is sent anywhere.

### Is an edition worth it?

Uruguay's Parliament is independent and freely elected, and it legislates on
our ground (euthanasia in 2025, abortion in 2012, trans law in 2018,
same-sex marriage in 2013). The obstacle is access, not politics. **With
today's access an edition would carry new laws and the deputies' pedidos
only**: about two laws and 30 pedidos a week, perhaps one or two on our ground.
That is a thin weekly. **Recommendation: keep the Phase 1 collector running
(it costs a minute a week and builds the record), hold the edition until
parlamento.gub.uy answers us, and make that request now.**

## Departmental bodies (later, not probed)

Nineteen Juntas Departamentales (Artigas, Canelones, Cerro Largo, Colonia,
Durazno, Flores, Florida, Lavalleja, Maldonado, Montevideo, Paysandú, Río
Negro, Rivera, Rocha, Salto, San José, Soriano, Tacuarembó, Treinta y Tres).
They legislate locally (decretos departamentales) and rarely touch our
ground. Two other channels matter more: the **referendum against a law**
(art. 79, 25 per cent of the electorate within a year of promulgation; the
route tried against the abortion law in 2013) and the **Suprema Corte de
Justicia**, which rules on the constitutionality of laws.

## Shared files touched (for the merge of the country branches)

- `src/db.py`: four `uy_*` names added to `TABLES`, and
  `uy_store.ensure_schema` called from `init_db` (8 lines).
- `tools/coverage.py`: `Uruguay weekly` in `PIPELINES`, `PIPELINE_FEEDS` and
  `AWAITING_FIRST_RUN`; `uy_members`, `uy_questions`, `uy_sittings`
  (7 + 4 days) and `uy_laws` (31 + 31) in `FEEDS` (14 lines).
- `.github/workflows/alert.yml`: `"Uruguay weekly"` added to the watched
  workflows (1 line).

Not touched: any taxonomy file, `tools/generate_taxonomy.py`,
`src/filter.py`, `src/http.py`, `tools/mini_run.sh`,
`.github/workflows/mini-check.yml`. The one-off runner probe used the
existing `probe-hosts.yml` on main by dispatch; nothing was added for it.
New files only otherwise: `src/uy_store.py`, `tools/uy_rollcalls.py`,
`config/watchlist-uy.yaml`, `jobs/uy-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.uy-weekly.plist`,
`.github/workflows/uy-weekly.yml`, `tests/test_uy_rollcalls.py`,
`tests/fixtures/uy/`, this document.

## Test results

`python3 -m unittest discover -s tests -t .` on this branch: 3,311 tests,
2 failures and 72 errors, **exactly the same 74 as a pristine checkout of
origin/main in a scratch worktree**, and none in any Uruguay test. All 74
read gitignored data that a fresh worktree lacks: the frozen
`data/raw/2026-08-01/` fixtures, other dated raw fixtures, and a pulled
store (`test_db_state`). With main's `data/raw/2026-08-01/` linked in
temporarily, 64 of the 74 pass; the other 10 glob for later raw dates.
`tests/test_uy_rollcalls.py` (20 tests), `tests/test_coverage.py` and
`tests/test_raw_state.py` pass in full. Run on Python 3.9.6, the laptop's.

## Waiting on Chris

1. **Access to parlamento.gub.uy.** Options, not exclusive: (a) write to the
   Parliament's open-data team (the catalogue lists the datasets under the
   organisation "parlamento-uruguayo") asking for our User-Agent to be let
   through, naming the endpoints above; (b) run one probe from the Mac Mini's
   own connection, not over a VPN (`python3 tools/probe_hosts.py --out
   /tmp/uy-probe https://parlamento.gub.uy/`), since the laptop's probe may have gone out
   over the VPN; (c) go without, and accept a laws-and-questions monitor. A
   browser User-Agent exception, as for the Senedd, is NOT recommended
   before (a): the block may not be about the UA at all.
2. **Approve or amend the Uruguayan terms above**, ideally after a read by
   someone in the Latin America team; and say whether Uruguay gets its own
   file (`taxonomy-uy`) or an addendum to one shared Spanish file.
3. **Scope questions the corpus raised:**
   - **Ley 19.580** (violence against women based on gender): in or out? The
     same question as Spain's gender-violence law.
   - **Pedidos de informes as an edition item**: they are questions, not
     legislation, and half of ours come from one party's two deputies. Report them, or
     use them only as a who-works-our-ground signal?
   - **INAU** (child protection) is guarded to adoption, sex, gender and
     identity; unguarded it pulled in 36 institutional pedidos. Right?
4. **Ley 20.431's referendum window** closes on 24 October 2026. Worth a look
   by the team if a signature campaign is live.
5. **Merge and install.** Merge `uruguay` to main when ready (the workflow
   schedules only from main); copy the plist to the Mini and bootstrap it.
   `MINI_LAST_UY_WEEKLY` is written by `mini_run.sh` on the first clean run;
   no secret or key is needed.
6. **Vote totals from the Diario PDFs (Phase 1b)**: build, or wait for access
   to parlamento.gub.uy?
