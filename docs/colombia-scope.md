# Colombia: scoping the Congress monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (the
CitizenGO User-Agent, one request a second per host). Every number below was
measured, not estimated. Raw responses are archived under
`data/raw/2026-10-09/` (`co_*`, `co-rollcalls_*`; the probe-only ones are
`co_probe_*`). Congress first, both chambers; the Constitutional Court is
scoped as a channel; departmental assemblies are later.

## Decisions (Chris, 9 October 2026)

- **Own edition**, delivered to Chris alone (Slack DM), like the US.
- **Shared taxonomy concept, Spanish terms proposed here.** No existing
  taxonomy file is edited. `config/taxonomy-es.yaml` is generated only after
  Chris approves the list below. Spain, Argentina, Mexico, Chile and Peru are
  being scoped in parallel in Spanish, so Colombia-specific terms are marked.
- **National Congress first** (Cámara de Representantes and Senado). The
  Constitutional Court is a major channel. Departmental assemblies later.
- **Mac Mini first, GitHub Actions as backup.** No new paid services. Never
  post publicly anywhere.

## The two findings that shape everything

**1. The English taxonomy is blind to Colombia.** `config/taxonomy.yaml`,
unchanged, over every bill of the last five legislaturas (2022-2023 to
2026-2027):

| Corpus | Bills | English: any area | English: useful |
|---|---|---|---|
| Cámara open data (title + nickname + objeto) | 2,405 | 2 | 0 |
| Senate register (titles) | 1,919 | 0 | 0 |
| Cámara register, 2026-2027 | 402 | 0 | 0 |

The two hits are "Agenda 2030" in two sustainability bills. As in Germany:
nothing else matters until there is a Spanish term list.

**2. There are no structured roll calls for the current Congress.** Neither
chamber publishes per-member votes of the 2026-2030 Congress in any
machine-readable form. The only public record is the plenary *acta* in the
Gaceta del Congreso, published months later, and there the electronic vote
register is printed **as an image**. Details under "Votes" below. A 5CA for
Colombia cannot be built on votes today; it can be built on authorship
(every bill names its authors) and, for the Cámara, plenary attendance.

## Phase 1: built, 9 October 2026

`tools/co_rollcalls.py` into `co_bills`, `co_members`, `co_attendance`,
`co_divisions` and `co_votes` (schema in `src/co_store.py`, declared in
`db.TABLES`). Live run into a scratch database, not the store:

| | Read | On our ground (watchlist-co only) |
|---|---|---|
| Cámara bills, 2025-2026 and 2026-2027 | 981 | 7 |
| Senate bills and actos legislativos, same | 702 | 3 |
| Cámara representatives (attendance roster) | 181 | |
| Cámara plenary sittings with attendance | 9 (1,629 marks) | |
| Senate roll calls, 2017-2024 (the published file) | 241 divisions | 0 |
| Senate positions | 16,587 | |

28 requests, about 40 seconds, no gaps. Exit 3 when a source fails (stored
what it could, gap recorded), as the other collectors do.

- **Keys are chamber numbers, never titles:** `camara/2026/426`,
  `senado/2026/289`. The Cámara register holds two bills called "TARIFA
  ESPECIAL PARA ENTIDADES RELIGIOSAS" (058/2026C withdrawn, 361/2026C live).
  A bill that crosses chambers has a number in each; `other_key` links them.
- **The Senate numbers actos legislativos in a series of its own.** In
  2026-2027 its proyecto de ley 01/26 and its acto legislativo 01/26 are
  different bills, so a Senate acto is keyed `senado/2026/AL1`. The Cámara
  numbers both kinds in one series (402 numbers, 402 bills), so no prefix.
- **Two legislaturas are read, not one.** A proyecto may be considered in at
  most two legislaturas (Constitution, art. 162), so the live set is the
  current one and the one before.
- **Areas are empty until taxonomy-es exists**, except what
  `config/watchlist-co.yaml` gives by key (ten bills, all found by reading
  every 2026-2027 title in both registers). The classifier already folds
  accents on both sides and switches on by itself when the file appears;
  `--reclassify` (or the workflow's reclassify input) applies it to the store.
- **Scheduled** as `co-weekly` (Thursday; details under "The weekly
  schedule"). It runs only once merged to main.

## What Colombia publishes

### Cámara: bill register, works today, open, no key

- `POST www.camara.gov.co/wp-admin/admin-ajax.php`,
  `action=get_proyectos_ley_page`, with the nonce printed in the
  `/proyectos-de-ley/` page (`PL_NONCE`). The nonce is the same for every
  anonymous visitor and is read fresh each run. JSON: number in each chamber,
  title, nickname ("LEY LOS PADRES EDUCAN"), type, status, origin,
  committee, authors, legislatura, page slug.
- **6,708 bills** all time; **402** in 2026-2027 (newest 426/2026C, filed
  1 October 2026, listed on the 9th); 579 in 2025-2026.
- `per_page` is capped at **100** (asked for 500, got 100).
- The page per bill (`camara.gov.co/<slug>/`) adds the *objeto* and filing
  dates as HTML. Not needed: the open data below carries the objeto.
- An XLSX download exists (`download_proyectos_ley_xlsx`); not used.
- `robots.txt` disallows only `/wp-admin/` but **explicitly allows
  `admin-ajax.php`**.

### Cámara: open data on datos.gov.co, works today, open, no key

Socrata (`www.datos.gov.co/resource/<id>.json`, SoQL filters):

- **`kcxp-nxum` Proyectos de Ley** (attribution: Cámara): 6,606 rows,
  refreshed 17 September 2026. Adds `objeto_del_proyecto`, which the
  register lacks. **Lags the site by about three weeks**: 302 rows for
  2026-2027 against the site's 402. The collector lists from the site and
  merges the objeto in (881 of 981 bills got one).
- **`48i3-vuny` Asistencia plenarias** (Cámara): 181 representatives, one
  column per sitting, nine sittings 20 July to 25 August 2026, refreshed
  18 September. Party and department per member. Two joint sittings on
  20 July have separate columns (`..._cp_20_07_2026` and `..._1`).
- `7w3p-s9ve` (UTL staff, refreshed 18 September) and `5pt5-nxdp`
  (representatives 2024-2025, stale) exist; not used.
- **Rate limits:** without an app token Socrata throttles by IP from a
  shared pool; a free app token raises it but needs an account. Not needed
  at this volume (four requests a week).

### Senate: bill register, works today, open, no key

- `POST leyes.senado.gov.co/api/search_pdly.php` (proyectos de ley) and
  `search_pal.php` (actos legislativos), form field `legislatura=2026-2027`.
  JSON: id, Senate and Cámara numbers, title, authors, committee, status.
  No summary. `get_detalle_pdly.php?id=` returns an HTML fragment with dates,
  ponentes and publication links.
- 2026-2027: **289** proyectos (newest 289/26, filed 6 October 2026) and
  **20** actos legislativos. 2025-2026: 380 and 14. Earlier legislaturas
  back to 2013-2014 are selectable.
- **Quirk:** the server dropped the connection on one of eleven POSTs on
  9 October; the collector tries each POST four times.
- **Quirk:** titles are in capitals and often without accents ("GENERO",
  "PROTECCION"); matching must fold accents.
- `feim-cysj` on datos.gov.co (Senate bills) is stale (December 2023).

### Votes: the gap

What exists, measured:

| Source | Coverage | Per member? | Current? |
|---|---|---|---|
| datos.gov.co `ucmr-52df` (Senate plenary) | 16,733 rows, 14 Feb 2017 to **25 Sep 2024**, 111 sitting days, 233 questions | yes: Sí 16,096, No 637, nothing else | **no**, refreshed 29 Oct 2024 |
| Congreso Visible `getVotaciones` | 4,846 votes, 2006 to **14 Dec 2022**; 18 since 2018 | **no**: `votacion_congresista` is empty on all 4,846 | no |
| Gaceta del Congreso, plenary *actas* | every recorded vote | yes, but **as an image** | months late |
| Cámara or Senate website | nothing found | | |

- **The Senate file is stored** (241 divisions, 16,587 positions, every
  senator of 2017-2024 by name) because it is the only per-member record
  there is, it costs one request, and reading it weekly is how we notice if
  the Senate resumes publishing. Its quirks: no abstentions or absences;
  146 rows repeat a senator on the same question and day (folded to one
  position); members are names only, no IDs. 233 of 241 questions name a
  bill (`senado/2016/2`, `senado/2017/AL2`); 0 are on our ground under
  the watchlist, as expected for 2017-2024 bills.
- **The Gaceta:** the Cámara's plenary of **20 May 2026** (Acta 316) was
  published in **Gaceta 1200 on 4 September 2026**, 107 days later. Its
  "PUBLICACIÓN REGISTRO DE VOTACIÓN" pages are embedded pictures; only
  members who voted by hand appear as text ("Por el SÍ han votado
  manualmente: ..."). Reading it would need OCR of a screenshot table,
  months after the vote. Not proposed for now.
- **"Mi Senado"**, the Senate's app, shows live attendance and votes during
  a plenary. No public API is documented; not probed (it would mean
  reverse-engineering an app).

### Gaceta del Congreso: reachable, keyless, awkward

- `svrpubindc.imprenta.gov.co/senado/index.xhtml` (Imprenta Nacional): a
  JSF/PrimeFaces table of **31,765** gacetas, newest **1508 of 8 October
  2026**. Number, chamber, date; the "Documento" column is empty, so the
  index does not say what a gaceta contains.
- A PDF comes only from a form postback with the page's `ViewState` and a
  session cookie (no stable link). Measured: 0.3 MB to 32 MB each; one of
  the ten newest (1475) is a 20 MB scan with no text layer. Text extracts
  cleanly from the rest, but some editions carry a second, stale text layer
  (Gaceta 1508's first page also reads as a 2016 issue).
- Filtering by number works through the table's AJAX filter.
- This is the source for ponencias, approved texts and actas. A phase 2
  "document layer" (body matching, as `src/eudoc.py` does) would read the
  gacetas that Congreso Visible or the Senate detail page links to a watched
  bill, rather than the whole stream.

### Congreso Visible (Universidad de los Andes): open API, use with care

- `apicongresovisible.uniandes.edu.co/apicliente/` (Laravel, keyless,
  JSON), found in the site's JavaScript. `proyectoley?cuatrienio=10&...`
  lists bills with *sinopsis*, themes, authors as member records, and
  `proyecto_ley_estado` (every step with its Gaceta number and a PDF link
  on their own server).
- 15,549 bills; 3,018 in 2022-2026; **691 in 2026-2030, the newest filed
  8 September 2026**: about a month behind the chambers.
- **Heavy:** about 130 KB per bill (each author's full biography is
  embedded): 500 bills were 65 MB and took 45 s.
- **The API runs in debug mode**: a malformed query returns the full
  Laravel stack trace and the SQL. The member listing returned 0 rows with
  the filter values the site uses and an SQL error with empty values. We did
  not probe further. Chris may want to tell Uniandes; either way it is not a
  source to build on until it is maintained.
- Useful later for its themes (a recall check for taxonomy-es, as the CRS
  subjects were for the US) and its Gaceta links per bill.

### Agenda (orden del día): reachable, HTML

- Cámara: `camara.gov.co/agenda-consolidada/` (754 KB, WordPress) and
  `/secretaria-general/orden-del-dia-secretaria-general/`.
- Senate: `secretariasenado.gov.co/index.php/orden-del-dia-senado`
  (100 KB, Joomla). Both answered; neither was parsed. Phase 2.

### Members

No source shared by both chambers carries a stable member ID. The Cámara
roster comes from the attendance file (181 names with party and
department); senators come from the 2017-2024 roll-call file (by name).
Congreso Visible has member IDs on every bill author, which is the best
crosswalk once its API is trustworthy. `sjwx-dr6n` (senators) is 2018-2022.

### The Constitutional Court: the channel that moves our issues

Abortion (C-355 of 2006, **C-055 of 2022**: decriminalised to 24 weeks),
euthanasia (C-239 of 1997, T-970 of 2014, C-233 of 2021, C-164 of 2022:
assisted suicide), surrogacy (T-968 of 2009, T-127 of 2024) and gender
identity (T-099 of 2015, T-033 of 2022) were all decided by the Court, which
then **exhorts Congress to legislate**.

- **datos.gov.co `fbtr-7k2r`** (attribution: Corte Constitucional): every
  judgment containing an exhortation to Congress. **203 rows, newest
  SU-313/26 of 23 September 2026**, each with the order's text and a link
  to the judgment. With the proposed Spanish terms, **37 of 203 are on our
  ground**: C-055/22, SU-096/18 (IVE), eleven euthanasia judgments
  reiterating the call to regulate *muerte digna* (the latest T-438/25),
  T-127/24 and T-232/24 (surrogacy), T-033/22 and its reiterations to 2025
  (non-binary identity), T-241/26 (free expression and social media).
- Judgments are open HTML at `corteconstitucional.gov.co/relatoria/<year>/`
  (C-055-22.htm is 4.8 MB); `robots.txt` allows `/relatoria/` and
  `/comunicados/`. One fetch timed out at 45 s, the retry took 3 s.
- **Proposed for phase 2:** the exhortations file weekly (one request), and
  the Court's press releases (*comunicados*) for new rulings.

## How much touches CitizenGO's ground (proposed Spanish terms)

The proposed list below, run over the same corpora (accents folded, area 11
left out):

| Corpus | Bills | On our ground | Share |
|---|---|---|---|
| Cámara open data, 2022-2027 (title + objeto) | 2,405 | 115 | 4.8% |
| Senate register, 2022-2027 (titles only) | 1,919 | 61 | 3.2% |
| **Both registers, 2026-2027** | **711** | **23 (12 with a tier-1 term)** | 3.2% |
| Court exhortations to Congress | 203 | 37 | 18% |

The 23 bills of 2026-2027 include, besides the ten in the watchlist: the
social-media bills for minors (Niños sin redes, 184/26, 180/26, 054/26),
commercial sexual exploitation of children (163/26), and noise from tier-2
terms (*divorcio*, *unión marital de hecho* in a gender-violence bill,
*redes sociales* in an AI-in-schools bill). Triage is what separates them.

**What the titles do not say.** No bill in four legislaturas has *aborto* in
its title or objeto, in either chamber. The pro-life bills of 2026-2027
speak of *vida desde la fecundación* and *vida en gestación* (114/2026C,
053/2026C); the euthanasia bills of *muerte digna* and *muerte médicamente
asistida*. 120 of the 202 terms measured matched nothing in any bill title
or objeto of four years (107 matched nothing in the Court's file either);
most will matter in body text (Gaceta, Court). The Court's file alone hit
13 terms the bills never use (IVE, *morir dignamente*, *componente sexo*,
*parejas del mismo sexo*). C-164 was added to the list after the
measurement.

### Proposed term list (for approval; not yet a file)

`[CO]` marks a Colombia-specific term (a ruling, statute, institution or
local usage); unmarked terms are general Spanish and could be shared with
the Spain, Argentina, Mexico, Chile and Peru editions. `*` is a stem
wildcard. All matching folds accents on both sides. Acronyms in capitals
match case-sensitively. Global exclusions proposed: *vida, familia, género,
mujer, niños, salud, educación, libertad* (never terms on their own).

**1. Abortion.** Tier 1: aborto\*, interrupción voluntaria del embarazo,
interrupción del embarazo, IVE, C-055 `[CO]`, C-355 `[CO]`, no nacido\*, por
nacer, nasciturus, vida desde la concepción, desde la concepción, desde la
fecundación, vida en gestación, vida humana desde, provida, pro vida,
misoprostol, mifepristona, feticidio, causales de aborto `[CO]`, escucha su
latido `[CO]`, latido fetal, latido del corazón fetal. Tier 2: salud sexual
y reproductiva, derechos sexuales y reproductivos, derechos reproductivos,
embarazo no deseado, embarazo adolescente, anticoncep\* (contraception is a
life issue, as decided for the US), gestante\*, mujer gestante, maternidad,
muerte fetal, duelo gestacional, duelo perinatal.

**2. Assisted dying.** Tier 1: eutanasia\*, muerte digna, morir dignamente,
muerte médicamente asistida `[CO]`, suicidio asistido, suicidio médicamente
asistido, T-970 `[CO]`, C-239 `[CO]`, C-233 `[CO]`, C-164 `[CO]`. Tier 2:
cuidados paliativos, voluntad anticipada, documento de voluntad anticipada,
adecuación del esfuerzo terapéutico, enfermo terminal, enfermedad terminal.

**3. Gender medicine and children.** Tier 1: bloqueador\* de la pubertad,
bloqueador\* puberal\*, bloqueo puberal, tránsito de género, transición de
género, reasignación de sexo, afirmación de género, hormonización, menores
trans, niñez trans, infancias trans, niños trans, disforia de género.
Tier 2: cambio de sexo, terapia hormonal, cirugía de reasignación.

**4. Conversion practices.** Tier 1: terapia\* de conversión, terapias de
conversión, ECOSIEG, esfuerzos de cambio de orientación sexual, esfuerzos
para corregir, Inconvertibles `[CO]`, Nada que curar `[CO]` (both names
used for Colombian bills; to verify). Tier 2: cura gay, terapias
reparativas.

**5. Sex-based rights.** Tier 1: identidad de género, ideología de género,
enfoque de género, personas trans, transgénero\*, no binari\*, LGBTI\*,
LGBTIQ\*, LGTBI\*, ley integral trans `[CO]`, componente sexo `[CO]` (the
civil-registry field), marcador de sexo, mujer\* trans. Tier 2: perspectiva
de género, orientación sexual, diversidad sexual, orientaciones sexuales,
expresión de género, sexo biológico, deporte femenino, categoría femenina.
*Enfoque de género* is in tier 1 at Chris's suggestion; measured, it is
frequent (6 Cámara bills) and often incidental, so it may belong in tier 2.

**6. Parental rights and education.** Tier 1: educación sexual, educación
sexual integral, derecho preferente de los padres, derechos de los padres,
derechos parentales, los padres educan `[CO]`, manuales de convivencia
`[CO]`, manual de convivencia `[CO]`, cartillas `[CO]` (the 2016 schools
guidance dispute), educación en casa, homeschooling. Tier 2: patria
potestad, padres de familia, consentimiento de los padres, convivencia
escolar, Ley 1620 `[CO]` (school coexistence), objeción de conciencia
educativa.

**7. Free speech and online safety.** Tier 1: libertad de expresión,
discurso\* de odio, pornografía\*, material de abuso sexual infantil,
explotación sexual en línea, verificación de edad, libertad de prensa.
Tier 2: entornos digitales, plataformas digitales, noticias falsas,
desinformación, censura, ciberacoso, grooming, redes sociales, difamación,
injuria y calumnia.

**8. Freedom of religion and conscience.** Tier 1: libertad religiosa,
libertad de cultos, libertad de conciencia, objeción de conciencia,
entidades religiosas, confesiones religiosas, Ley 133 de 1994 `[CO]`,
persecución religiosa, Concordato `[CO]`, sector religioso `[CO]`, hecho
religioso. Tier 2: iglesia\*, culto\*, capellan\*, comunidades de fe,
organizaciones basadas en la fe.

**9. Marriage and family.** Tier 1: matrimonio igualitario, matrimonio
entre personas del mismo sexo, parejas del mismo sexo, matrimonio infantil,
matrimonio de menores, uniones tempranas, Son niñas, no esposas `[CO]`,
adopción por parejas del mismo sexo, núcleo fundamental de la sociedad
`[CO]` (art. 42 of the Constitution). Tier 2: unión marital de hecho
`[CO]`, divorcio, custodia, familia diversa, familias diversas, poliamor.

**10. Surrogacy and embryology.** Tier 1: gestación subrogada, maternidad
subrogada, alquiler de vientre\*, vientre\* de alquiler, gestación por
sustitución, subrogación uterina, T-968 `[CO]`, T-127 `[CO]`. Tier 2:
reproducción asistida, fecundación in vitro, embrion\*, células madre,
clonación, edición genética.

**11. Migration** (collated, never campaigned). Tier 1: migrante\*,
refugiad\*, Estatuto Temporal de Protección `[CO]`, apatrid\*. Tier 2:
migratori\*, venezolan\* `[CO]`.

**12. Prostitution and trafficking.** Tier 1: trata de personas,
explotación sexual, prostitución, trabajo sexual, proxenetismo, ESCNNA
`[CO]`, turismo sexual, matrimonio servil. Tier 2: matrimonio forzado,
abolicionis\*, edad de consentimiento, consentimiento sexual.

**13. Organ donation.** Tier 1: donación de órganos, trasplante\* de
órganos, donante\* de órganos, Ley 1805 `[CO]` (presumed consent, 2016),
presunción legal de donación `[CO]`, tráfico de órganos. Tier 2: donación
de tejidos, trasplante\*.

Noise found and already removed from the draft: *Semana Santa* (8 Senate
and 9 Cámara bills, all heritage declarations) and *Ley 115 de 1994* (the
general education law, cited by most school bills).

**Shared-code note for the taxonomy-es file.** `src/filter.py` matches
accents literally. The Colombian collector folds accents itself (on the
text and on each term) so no shared file changed; the other Spanish
editions will need the same, and it may be worth doing once in
`src/filter.py` when the branches meet.

## Proposed phasing

1. **Phase 1 (built, keyless):** both chambers' bill registers, Cámara
   attendance, the Senate's 2017-2024 roll calls; watchlist-co by key.
2. **Phase 1b (needs only Chris's yes):** generate `config/taxonomy-es.yaml`
   from the approved list (through a `docs/keyword-taxonomy-es.md` master
   and `tools/generate_taxonomy.py --lang es`, as for German), then
   `--reclassify`. Recall check against Congreso Visible's themes.
3. **Phase 2 (keyless):** the Court's exhortations file and press releases;
   the two chambers' agendas; Senate detail pages for bills on our ground
   (ponentes, dates, Gaceta numbers).
4. **Phase 3:** a document layer: the Gacetas (ponencias, approved texts)
   for bills on our ground, body-matched. The Imprenta portal needs a
   postback per PDF and some PDFs are scans.
5. **Phase 4:** an edition and a Colombian 5CA built on authorship,
   ponencias and attendance, with votes only where a source appears.
   Departmental assemblies after that.

## The weekly schedule

`.github/workflows/co-weekly.yml`: Thursday 09:30 UTC, retry 11:30 UTC (half an hour later than first built; Chile holds 09:00 and 11:00)
(04:00 in Bogotá, after the Tuesday and Wednesday plenaries), gated by
`mini-check` with `job: CO_WEEKLY` (repo variable `MINI_LAST_CO_WEEKLY`,
grace 200 minutes). The Mini runs `jobs/co-weekly.sh` from
`ops/launchd/net.citizengo.parlmonitor.co-weekly.plist` at 09:30 London on
Thursdays. Watched by the failure alert and `tools/coverage.py` (bills,
members and divisions weekly; all three are re-read whole each run, so they
move in recess too). Other country branches may choose the same slot:
check the crons when they meet. It runs only once merged to main.

## Shared files touched (for the merge of the country branches)

| File | Change |
|---|---|
| `src/db.py` | five `co_*` names in `TABLES`; `co_store.ensure_schema` in `init_db` (9 lines) |
| `tools/coverage.py` | "Colombia weekly" in `PIPELINES`, `PIPELINE_FEEDS` and `AWAITING_FIRST_RUN`; three `FEEDS` rows |
| `.github/workflows/alert.yml` | "Colombia weekly" in the watched list (1 line) |
| `docs/mac-mini.md` | a "Colombia weekly" section (the runner's job list is not on this branch) |

Everything else is new and Colombia's own: `src/co_store.py`,
`tools/co_rollcalls.py`, `config/watchlist-co.yaml`, `tests/test_co_rollcalls.py`,
`tests/fixtures/co/`, `jobs/co-weekly.sh`, the plist, `co-weekly.yml` and
this document. `config/taxonomy.yaml` and every other taxonomy file are
untouched.

## Waiting on Chris

1. **Approve, edit or cut the Spanish term list** above, in particular:
   tier for *enfoque de género*; whether contraception (*anticoncep\**)
   belongs in area 1 here as in the US; the two conversion-bill names to
   verify; and which unmarked terms the other Spanish editions should share.
   Only then is `config/taxonomy-es.yaml` generated.
2. **Review `config/watchlist-co.yaml`** (ten bills of 2026-2027). It is
   the only thing giving Colombian bills an area until item 1 is done.
3. **Votes:** accept that the 2026-2030 Congress has no per-member vote
   source, and that the edition will say so; or approve one of: OCR of the
   Gaceta vote images (months late), or asking the Senate and Cámara
   (Secretaría General, or the transparency office under Ley 1712 of 2014)
   for their electronic vote exports. A request should come from Chris or
   the Colombia team, not from Claude.
4. **The Court as a section:** yes or no to the exhortations file and
   press releases in phase 2.
5. **Congreso Visible's API runs in debug mode** (stack traces and SQL in
   error replies). Whether to tell Uniandes is Chris's call.
6. **Install on the Mini** after merge: copy the plist and bootstrap it
   (`docs/mac-mini.md`). Merging is Chris's decision; nothing here was
   pushed to main.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (CO1, CO2 enfoque de genero tier 1) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.
- Weekly moved to Thursday 09:30/11:30 UTC (Chile holds 09:00/11:00).

Later phases and items for Chris (not built at the merge):

- No votes for now (CO3).
- Phase (X8): the Constitutional Court section (CO4).
- Phase (X7): OCR for scanned records.
- Member profiles (handover item 3, built 10 October 2026, branch `parity-profiles`): `profiles/co/` from the store each weekly run (`tools/member_profiles.py co`, src/member_profiles.py): party, chamber, constituency, every recorded position on a vote on our ground as the edition classifies it, verbatim, with the basis of the party at the vote; no verdicts, no DM. The vote files print no party: the party shown is the member list's latest, labelled; bills by author are listed.
