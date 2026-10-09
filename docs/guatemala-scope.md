# Guatemala: scoping the Congreso de la República monitor

Probed on 9 October 2026. Every number below was measured, not estimated.
The raw replies are archived under `data/raw/2026-10-09/gt_probe/` (local;
the five runner probes are also GitHub workflow artifacts, kept 7 days) and
the fixtures cut from them are in `tests/fixtures/gt/`.

## Decisions already taken (Christopher)

- Own edition, delivered to Chris alone (Slack DM), like the US.
- Shared taxonomy concept; no existing taxonomy file is edited. Spanish terms
  are PROPOSED here as a Guatemalan addendum to the shared Spanish list drafted
  on the Spain branch, for approval before any `taxonomy-es` file exists.
- National parliament first. Mac Mini first, GitHub Actions as backup. No paid
  services. Nothing posted publicly.

## The three findings that shape everything

### 1. The site refuses the laptop and answers GitHub

`www.congreso.gob.gt` sits behind Imperva Incapsula. From the scoping laptop
**every request was refused**: home page, `robots.txt`, listings, PDFs, all
`403` with an Incapsula challenge page (incident ID, `_Incapsula_Resource`
script), with the repo's honest User-Agent and with curl's own. The same
happened on the Guatemalan gazette (`dca.gob.gt`), the Constitutional Court
(`cc.gob.gt`) and the electoral tribunal (`tse.org.gt`), all three behind
Cloudflare ("Sorry, you have been blocked").

The challenge was **not solved or worked around**: no browser User-Agent, no
headless browser. Instead the repo's existing read-only probe
(`.github/workflows/probe-hosts.yml`, which stops a host at the first
challenge) was dispatched five times from a GitHub runner, with the same
honest User-Agent, robots.txt read first:

| Host | From the laptop | From a GitHub runner |
|---|---|---|
| www.congreso.gob.gt | 403 Incapsula challenge | **200, every page (246 requests over 5 runs)** |
| dca.gob.gt (Diario de Centro América) | 403 Cloudflare block | 200 |
| cc.gob.gt (Corte de Constitucionalidad) | 403 Cloudflare block | 403 challenge, host stopped |

So the block is on the client's address, not on automated access as such.
**The collector is built for the runner, where it works.** Whether the Mac
Mini is refused like the laptop is unknown; one curl from the Mini settles it
(Waiting on Chris). The collector treats a challenge as a hard stop: it
records a gap, exits 1 and publishes nothing, so on a refused Mini the GitHub
backup simply runs at its slot.

### 2. The data is good: every deputy's vote, in HTML, back to 2009

The Congreso publishes an electronic vote record for every plenary question
since 2009, each with all 160 deputies' positions, as plain server-rendered
HTML. No key, no API, no JavaScript needed. Measured below.

### 3. The English taxonomy is blind to Guatemala, and the votes carry no subject

`config/taxonomy.yaml` run over the 500 initiative summaries the Congreso
lists matched **0 of 500**. And a vote's own label never names its subject:
every vote on a bill reads "... DEL PROYECTO DE DECRETO QUE DISPONE APROBAR LA
INICIATIVA DE LEY 6844". A vote is classified only through its initiative,
joined on the number. The German precedent applies in full: nothing is
classified until a Spanish term list is approved.

## Political context, and whether an edition is worth it

Unicameral, 160 deputies elected for four years by list (district lists plus
a national list). The X legislature was installed on 14 January 2024 and
runs to 14 January 2028; the next general election is due in mid-2027. The
Congreso is a genuinely independent and often adversarial chamber: it is not
controlled by the executive, it votes in public and on the record, and its
electronic board has published every deputy's vote since 2011 (sessions back
to 2009 are listed). Blocs are fluid. On 9 October 2026 the 160 cards read:
VAMOS 38, Independiente 38, UNE 22, CABAL 18, VALOR 10, VIVA 8, TODOS 6, CREO,
VOS and BIEN 3 each, ELEFANTE, PU, VICTORIA and AZUL 2 each, NOSOTROS,
WINAQ-URNG-MAIZ and CAMBIO 1 each.

Our ground is real and contested here: the 2022 fight over iniciativa 5272
is the clearest example in the region of a values bill passing a plenary and
being shelved a week later. **An edition is worth it**, on the condition that
it runs where the site answers.

## What Guatemala publishes (www.congreso.gob.gt)

All pages are HTML, served with no key, measured from a runner. robots.txt
disallows `/assets/uploads/`, `/application/`, `/system/` and `*.pdf` for every
agent, and some AI crawlers entirely; it sets no crawl-delay. Nothing the
collector reads is disallowed.

### Plenary votes: WORKS (from a runner)

- `/seccion_informacion_legislativa/votaciones_pleno` -- every session with
  electronic votes in one page (839 KB, 33 KB gzipped): **1,089 sessions,
  12 March 2009 to 8 October 2026**, each with type (Ordinaria 818,
  Extraordinaria 190, Solemne 79, Prueba Sistema 2), number and timestamp,
  linking `eventos_votaciones/<session id>`. Since the X legislature began:
  **190 sessions** (154 ordinary, 24 extraordinary, 12 solemn), 59 of them in
  2026 so far. Per year since 2016: 53, 98, 85, 100, 71, 90, 89, 40, 68, 64, 59.
- `/eventos_votaciones/<session>` -- the session's questions (66 to 109 KB):
  text, number in the session, timestamp, and two links,
  `detalle_de_votacion/<question>/<session>` (HTML) and
  `pdf_resultado_votacion/<question>/<session>` (PDF). **2,660 questions since
  14 January 2024** (1,358 in 2024, 644 in 2025, 658 in 2026 to 8 October);
  179 of the 190 sessions had votes, and one session carried 470.
- `/detalle_de_votacion/<question>/<session>` -- about 190 KB (15 KB gzipped),
  four tabs, `favor`, `contra`, `ausencia`, `licencia`, a row per deputy:
  name (surname first), presence (`PRESENTE` / `AUSENTE` /
  `LICENCIA / EXCUSA`) and vote. All 160 deputies. Checked against the PDF of
  the same vote (6844, 8 September 2026): 136 / 10 / 8 / 6 in both.
- The PDF (76 KB, 10 pages, text extractable) adds one thing the HTML lacks:
  **each deputy's bloc at the vote**. It is not fetched: the URL does not end
  in `.pdf`, but the reply is one, and robots.txt says `Disallow: *.pdf`. The
  deputy's current bloc comes from the member cards instead (Waiting on Chris).

There is no abstention: a deputy present who does not vote is recorded as
absent. 1,248 of the 2,660 questions (47%) name an initiative; they cover
**106 distinct initiatives**. The rest are procedural (approving the agenda
145, the previous minutes 148, privileged motions to alter the agenda 159,
agenda proposals 71, "proyecto de acuerdo" 37+, elections of magistrates).
Procedural votes are kept with positions, because one can matter: the vote of
15 March 2022 that shelved Decreto 18-2022 is labelled only "APROBACIÓN DE
PROYECTO DE ACUERDO".

Quirks:

- Session times are on a 12-hour clock without AM or PM ("01:09:43" for a
  sitting that began at 13:09). Dates are reliable; times are stored as printed.
- Session numbers restart every legislative year (14 January); the session id
  is the key, never the number.
- One header on the session pages is mis-encoded (`N?MERO PREGUNTA`); the
  data cells are clean UTF-8.

### Initiatives: WORKS (from a runner)

- `/seccion_informacion_legislativa/iniciativas` -- one page (2.97 MB, 83 KB
  gzipped) with **the 500 most recent initiatives the plenary took notice
  of**: number, date ("Conoció Pleno"), summary, a `detalle_pdf/iniciativas/
  <internal id>` link and the text's PDF under `/assets/uploads/` (disallowed,
  not fetched). Measured span: 15 March 2023 to 6 October 2026, 159 in 2024,
  155 in 2025, 144 in 2026. Numbers run 5790 to 6859. 22 summaries are cut
  short with "...".
- Initiative numbers form **one sequence across legislatures** (5272 in 2017,
  6859 in 2026), so the number alone is the key.
- `/buscador_iniciativas/<number>` -- the same card for one initiative, any
  year: 5272 (27 April 2017, "Ley para la Protección de la Vida y la
  Familia"), 5395 (22 February 2018, "Ley de Identidad de Género"). 28 of the
  106 initiatives voted on since January 2024 predate the listing and are read
  this way. A word works too (`/buscador_iniciativas/familia`, 410 KB).
- `/detalle_pdf/iniciativas/<internal id>` (100 KB) -- the sponsoring
  deputies (11 for 6844), the proposing institution, and the procedural steps
  with dates ("Dirección legislativa", "Presentación pleno", ...). Phase 2.

### Deputies: WORKS (from a runner)

The home page (and `/diputados`, which serves the same page, 943 KB) carries a
card per sitting deputy: `perfil_diputado/<id>`, name (forename first), bloc,
district. **160 cards, 160 distinct ids.** `/perfil_diputado/<id>` adds date
of birth, e-mail, office, and tabs for political history, initiatives,
committees and travel (Phase 2). The vote pages carry no id, and print the
name surname first; `gt_store.name_key` (folded words, sorted) joins them.

### Also published, not yet read

`seccion_informacion_legislativa/` holds `decretos` (one page, 24.4 MB),
`dictamenes_emitidos`, `orden_del_dia` (3.4 MB), `acuerdos`,
`puntos_resolutivos`, `resoluciones`, `diario_de_sesiones`, `actas_sesiones`
and `asistencias_pleno`. The agenda and committee reports are the obvious
Phase 2 sources (a bill reported out of committee is the early warning).

### Elsewhere

- **Diario de Centro América** (`dca.gob.gt`), the official gazette: answers a
  runner, WordPress with sitemaps; where decrees take effect. Phase 2 at most.
- **Corte de Constitucionalidad** (`cc.gob.gt`): **a major channel** in
  Guatemala (amparos and unconstitutionality actions against decrees are
  routine), but it challenges even a runner. BLOCKED; not worked around.
- **Wayback Machine**: holds about 1% of the vote pages (10 genuine
  `pdf_resultado_votacion` and 13 genuine `detalle_de_votacion` captures since
  2022, most others being Incapsula pages). Not a source.
- Regional bodies: none. Guatemala is unitary; its 340 municipal councils are
  out of scope.

## How much touches our ground

Measured with the draft terms below over the 500 initiative summaries (March
2023 to October 2026). Term hits, by area:

| Area | Hits | Of which real | Examples |
|---|---|---|---|
| 1 Abortion | 0 | 0 | |
| 2 Assisted dying | 1 | 1 (tier 2) | 6754 Ley de Cuidados Paliativos |
| 3/5 Gender | 2 | 2 (tier 2) | 6090 Ley Angelina, 6280 violencia sexual digital |
| 6 Parents and education | 2 | 2 | **6453 Ley de Educación Sexual para la Protección de la Niñez**, 6599 reform of the PINA law |
| 7 Speech | 1 | 1 (tier 2) | 6771 ciberseguridad y ciberdelitos |
| 8 Religion | 3 | 3 | **6607 Día de la Biblia**, 6244/6245 IVA exemption (churches) |
| 9 Family | 7 | 4 | **6278 reform of Decreto 9-2022 (Día por la Vida y la Familia)**, 6518 matrimonial property, 6777 adoption |
| 10 Surrogacy, 4 Conversion, 13 Organs | 0 | 0 | |
| 11 Migration (hidden) | 5 | 5 | 6634 deported and returned migrants |
| 12 Trafficking | 1 | 1 | 6011 reform of Decreto 9-2009 |

**About 14 initiatives in three and a half years are on our ground, three at
tier 1.** Of the 106 initiatives voted on since January 2024, two are: 6607
(six votes, 12 August 2025) and 6518 (one vote, 25 August 2026). **7 of
2,660 votes.** Like the Bundestag, the plenary is not where most of our fights
move week to week; unlike it, when one reaches the floor every deputy's
position is public in one page, which is exactly what a 5CA needs. The
history makes the point: 5272 (2017-2022, 15 recorded votes on 8 March 2022
alone), 5395 (gender identity, 2018) and 5376 (girls who are victims of
sexual violence, contested as an abortion route) never left the agenda for
long.

## Phase 1: built, 9 October 2026

`tools/gt_rollcalls.py`, `src/gt_store.py`, `config/watchlist-gt.yaml`,
fixtures in `tests/fixtures/gt/` (212 KB), `tests/test_gt_rollcalls.py`
(25 tests, offline).

- **Tables**: `gt_members` (by profile id), `gt_initiatives` (by number),
  `gt_sessions` (by session id), `gt_divisions` (`gt-<question id>`, with the
  initiative number parsed from the label, totals and a `procedural` flag) and
  `gt_votes` (every position, name as printed plus `name_key`).
- **Order of a run**: the initiative listing; the session list and every
  session page not yet read (plus the last fortnight's); older initiatives a
  vote names, by number; then vote pages without positions; then the member
  cards. Two seconds between requests. A 45-minute budget per run, so the
  first runs backfill the X legislature (190 session pages, about 2,660 vote
  pages, roughly 40 MB of gzipped raw) over three runs or so.
- **Classification**: none until `config/taxonomy-es.yaml` exists. Areas stay
  NULL (unclassified), except what `config/watchlist-gt.yaml` lends by
  initiative number: 5272, 5395, 5376, 6453, 6607, 6278. A division inherits
  its initiative's areas.
- **Challenge handling**: a 403 or a challenge body raises `Challenged`; the
  run records a gap, exits 1 and publishes nothing.
- **Weekly job**: `jobs/gt-weekly.sh`, `ops/launchd/net.citizengo.parlmonitor.gt-weekly.plist`
  (Saturdays 09:00 London; **do not install until the Mini curl check
  passes**), `.github/workflows/gt-weekly.yml` (Saturdays 09:00 and 12:00 UTC,
  gated by mini-check with `GT_WEEKLY`, grace 260 minutes). Registered with the
  failure alert and the coverage watch.
- Verified offline end to end against the archived runner pages: 500
  initiatives, 12 sessions, 83 divisions, 7 vote pages, 160 deputies, 1,120
  positions; the 5272 votes of 8 March 2022 carry areas [1, 5, 6, 9] from the
  watchlist.

Not yet run live: the workflow can only be dispatched from main once merged
(GitHub requires a workflow on the default branch), and the laptop is refused.

## Proposed Spanish terms: the Guatemalan addendum (v0.1, FOR APPROVAL)

Drafted by Claude on 9 October 2026, **not yet read by a Guatemalan who
campaigns**. It assumes the shared Spanish list proposed in
`docs/spain-scope.md` on the Spain branch (whose `Spain only` lines are
dropped for Guatemala) and adds only what is Guatemalan law or usage. Format
as there: `*` for an inflected ending, `[with: ...]` for a guard, accents as
printed. Lines marked **shared** are ordinary Spanish that the merged list
should carry for every country; lines marked **Guatemala only** are local.

1. **Abortion.** Guatemala only, tier 1: "Ley para la Protección de la Vida y
   la Familia"; "Decreto 18-2022"; "iniciativa 5272"; "aborto terapéutico";
   "artículo 137" [with: Código Penal, aborto]; "Día por la Vida y la
   Familia"; "Decreto 9-2022"; "capital provida". Shared, tier 1: "desde su
   concepción"; "desde la concepción". Shared, tier 2: "planificación familiar";
   "Ley de Acceso Universal y Equitativo de Servicios de Planificación
   Familiar" (Guatemala only); "Decreto 87-2005" (Guatemala only); "OSAR"
   (Guatemala only). Note: art. 3 of the Constitution protects life "desde su
   concepción"; art. 137 of the Penal Code is the only lawful exception.
2. **Assisted dying.** Nothing local; the shared list stands. 6754 (cuidados
   paliativos) is tier 2.
3. **Gender medicine and children** and 5. **Sex-based rights.** Guatemala
   only, tier 1: "Ley de Identidad de Género"; "iniciativa 5395". Shared,
   tier 2: "enfoque de género"; "violencia contra la mujer". Guatemala only,
   tier 2: "Ley contra el Femicidio"; "Decreto 22-2008"; "Ley Angelina".
4. **Conversion practices.** Nothing local.
6. **Parental rights and education.** Guatemala only, tier 1: "Ley de
   Educación Sexual para la Protección de la Niñez y Adolescencia";
   "Prevenir con Educación". Shared, tier 1: "educación integral en
   sexualidad"; EIS (case-sensitive). Guatemala only, tier 2: "Ley de
   Protección Integral de la Niñez y Adolescencia"; "Ley PINA"; "Decreto
   27-2003"; "Ley de Desarrollo Social"; "Decreto 42-2001"; "Currículo
   Nacional Base"; CNB (case-sensitive); Mineduc.
7. **Free speech.** Guatemala only, tier 1: "Ley de Emisión del Pensamiento";
   "libre emisión del pensamiento". Shared, tier 2: ciberdelit*;
   ciberdelincuencia. Guatemala only, tier 2: "Ley de ONG"; "Decreto 4-2020"
   (registration of NGOs and churches).
8. **Religion.** Shared, tier 1: "libertad de culto". Guatemala only, tier 1:
   "Día de la Biblia"; "Día Nacional de la Biblia". Shared, tier 2: "iglesias
   evangélicas"; "entidades religiosas" (already shared); "exención" [with:
   iglesia*, religios*, culto].
9. **Marriage and family.** Shared, tier 1: "matrimonio entre un hombre y una
   mujer"; "institucionalidad de la familia". Guatemala only, tier 1: "Política
   Pública de Protección a la Vida y la Institucionalidad de la Familia".
   Shared, tier 2: "unión de hecho"; "paternidad responsable"; "régimen
   económico del matrimonio"; adopción (already shared, guarded). Guatemala
   only, tier 2: "Código Civil" [with: matrimonio, familia, unión de hecho];
   "Consejo Nacional de Adopciones"; "Ley Max".
10. **Surrogacy.** Nothing local; Guatemala has no statute.
11. **Migration (hidden).** Guatemala only: "Código de Migración"; "Decreto
    44-2016"; "Instituto Guatemalteco de Migración"; "tercer país seguro";
    retornad*; deportad*.
12. **Trafficking.** Guatemala only, tier 1: "Ley contra la Violencia Sexual,
    Explotación y Trata de Personas"; "Decreto 9-2009"; SVET (case-sensitive).
13. **Organ donation.** Guatemala only, tier 1: "Ley para la Disposición de
    Órganos y Tejidos Humanos"; "Decreto 91-96".

Guatemalan matching traps:

- **The summary is short and formulaic.** "Iniciativa que dispone aprobar Ley
  ..." opens every one; the subject is in the law's name. Terms that are law
  names earn their place here more than anywhere.
- **Bare `familia` is useless**: the Congreso's own search for it returns 42
  initiatives, most about household economy ("economía familiar", "bono familiar"). Guarded phrases
  only, as in the shared list.
- **`oración` matches inside words once accents are folded** (incorporación,
  conmemoración): never fold accents for matching, and never use it bare.
- **Votes carry no subject.** A division is matched only through its
  initiative; the taxonomy is run over initiatives, never over vote labels.

## Proposed phasing

1. **Phase 1 (built, this branch).** Votes with every position since January
   2024, initiatives, deputies; weekly on a runner (and on the Mini if it is
   not refused). Unclassified until the Spanish list is approved; watchlist by
   number meanwhile.
2. **Phase 2.** The Spanish list with this addendum (`taxonomy-es`), then
   `--reclassify`. Initiative detail pages for sponsors and procedural steps,
   and the agenda (`orden_del_dia`) and committee reports
   (`dictamenes_emitidos`) as the early-warning layer.
3. **Phase 3.** An edition (`tools/gt_monitor.py`) and the DM, as for the US,
   and a Guatemalan 5CA once a division's meaning is signed by hand.
4. Optional backfill to 2016 (`--since`), for 5272's full record: about 1,000
   sessions more, spread over runs by the budget.

## Shared files touched (for the merge of the country branches)

- `src/db.py`: five `gt_*` names in `TABLES`, and `gt_store.ensure_schema` in
  `init_db` (9 lines).
- `tools/coverage.py`: "Guatemala weekly" in `PIPELINES`, four `gt_*` feeds in
  `FEEDS`, an entry in `PIPELINE_FEEDS` and in `AWAITING_FIRST_RUN`.
- `.github/workflows/alert.yml`: "Guatemala weekly" added to the watched
  workflows.
- No edit to `src/http.py`, `tools/mini_run.sh` or any taxonomy file.
- Not a file edit, but recorded: `probe-hosts.yml` was dispatched five times on
  main (read-only by design: no store, no commit, artifacts only).

## Waiting on Chris

1. **Run one curl from the Mac Mini** (in the plist's comment). 200: install
   the launchd job. 403: leave it uninstalled; GitHub runs the weekly.
2. **Approve the Spanish terms**: the shared list on the Spain branch plus the
   Guatemalan addendum above, ideally read by a Guatemalan campaigner; then
   `taxonomy-es` can be generated and the store reclassified.
3. **Confirm the watchlist**: 5272, 5395, 5376, 6453, 6607, 6278. 5376's
   number and subject come from press reports; 6278's day name is inferred from
   a truncated summary.
4. **Bloc at the vote**: the per-vote PDF carries each deputy's bloc, but
   robots.txt disallows `*.pdf`. Options: (a) keep current bloc only (as built);
   (b) ask the Congreso (unidadaccesolibre@congreso.gob.gt) for permission or a
   data export under the Ley de Acceso a la Información Pública; (c) treat the
   extension-less URL as allowed. Recommendation: (a) now, (b) when convenient.
5. **The Constitutional Court** challenges even a runner. Accept the gap, or
   ask the Court for access; it is a major channel for our issues here.
6. **Merge order**: the workflow can only be dispatched or scheduled once this
   branch reaches main.
