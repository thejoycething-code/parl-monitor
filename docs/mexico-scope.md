# Mexico: scoping the Congress monitor

Probed live on 9 October 2026, from the laptop in London and from GitHub's
runners. Every number below was measured, not estimated; where something
was not measured, it says so. Federal Congress first; the 32 state
congresses are listed at the end for later.

Raw responses: `data/raw/2026-10-09/mx-probe_*.json.gz` (126 files,
gitignored like the rest of the raw archive; the same files were uploaded
as the probe workflow's artifacts). The probes ran through `src/http.py`
(honest UA, retries, throttle), with robots.txt read first and at least two
seconds between requests to a host (`tools/mx_probe.py`).

## Decisions already taken (Christopher, 9 October 2026)

- **Own edition**, delivered to Christopher alone (Slack DM), as the US.
- **Shared taxonomy concept**, but no existing taxonomy file is edited. The
  Spanish terms below are a PROPOSAL; Christopher approves before a
  `config/taxonomy-es.yaml` is generated. Spain and Argentina are scoped in
  parallel in Spanish, so each term is marked Mexico-only or general.
- **Federal Congress first** (Cámara de Diputados and Senado); the state
  congresses later.
- **Mac Mini is the default runtime, GitHub Actions the backup.** No new
  paid services. Nothing is ever posted publicly.

## The three findings that shape everything

### 1. Mexico's federal hosts refuse the UK

| Host | From the laptop (BT, London) | From a GitHub runner |
|---|---|---|
| gaceta.diputados.gob.mx | TCP timeout | **200** |
| sitl.diputados.gob.mx | TCP timeout | **200** once the TLS chain is completed (below) |
| www/web.diputados.gob.mx | TCP timeout | 200 (web needs the same TLS fix) |
| www.senado.gob.mx | **403, Imperva/Incapsula challenge** | not requested: robots.txt (below) |
| sil.gobernacion.gob.mx | 200, but a stub portal | 200 with the TLS fix; still the stub |
| nsil.gobernacion.gob.mx (the new SIL) | connection refused | **connection refused** |
| datos.gob.mx (national open data) | 403 (Akamai) | **403** |
| gaceta.diputados.gob.mx:8080 (eXist XML database linked from SITL) | not tried | timed out |

All of diputados.gob.mx sits on one block (201.147.98.x) that drops UK
connections; it answers US addresses. **The Mac Mini is on Christopher's UK
network, so it almost certainly cannot reach the Chamber either** (not
measured from the Mini itself: the laptop cannot reach the Mini). Hence the
runtime decision below: the Mini keeps the clock and dispatches the job;
a GitHub runner does the work.

### 2. The English taxonomy is blind to Spanish, as it was to German

`config/taxonomy.yaml`, unchanged, run over the LXVI Legislature:

| Corpus | Items | Matched on our ground (not area 11) |
|---|---|---|
| Iniciativa titles (Gaceta lists) | 8,247 | **3** (two "LGBTIQ", one "Agenda 2030") |
| Recorded-vote titles (SITL) | 285 | **0** |

### 3. Votes are rarely on our ground; iniciativas are where it is

The draft Spanish terms below, run over the same corpora:

| Corpus | Items | Tier-1 on our ground | Any tier on our ground |
|---|---|---|---|
| Iniciativas, LXVI (since 29 Aug 2024) | 8,247 | **161** | 426 |
| Iniciativas presented since 1 Sep 2026 | 912 | **22** (about four a week) | |
| Recorded votes, LXVI | 285 | **0** | 4 |

The four votes are two on trafficking (Ley General de Turismo, 3 March
2026; Código Penal Federal articles 199 Octies and Nonies, 29 April 2026),
one on femicide (constitutional article 73, 21 April 2026) and one on
children's online protection (29 April 2026). None is abortion, euthanasia, marriage, gender or
religion. This is the German shape again: the Chamber votes on what the
majority has agreed, and our issues live in iniciativas that are presented,
sent to committee and given extensions ("prórroga": 3,628 of 8,247 entries)
without ever reaching the floor. **A monitor built on votes alone would be
accurate and almost always empty.** Votes are still collected in full,
because the day one of these reaches the floor is the day the 5CA matters.

Iniciativas on our ground found by the draft terms, by area (tier 1 / any
tier): abortion 8 / 18, assisted dying 16 / 20, gender medicine 0 / 1,
conversion practices 0 / 0, sex-based rights 13 / 129, parental rights and
education 6 / 61, free speech 8 / 76, religious freedom 12 / 13, marriage
and family 9 / 30, surrogacy and embryology 11 / 11, prostitution and
trafficking 65 / 67, organ donation 15 / 15. The tier-2 totals for areas 5,
6 and 7 are mostly noise from "feminicidio" (47), "redes sociales" (32),
"paridad de género" (22), "lenguaje incluyente" (21) and "violencia
política" (16); see the term notes.

Examples, read by hand: 66/1130 and 66/1244 (interrupción legal del
embarazo, Código Penal Federal articles 329 to 332, both PT), 66/1956
(decriminalisation of abortion, Morena), 66/6709 (euthanasia, Morena),
66/3543 (muerte asistida), 66/774 (conscientious objection, PAN), 66/7722
and 66/7629 (surrogacy, for and against), 66/3273 (child marriage, PAN).
They seed `config/watchlist-mx.yaml`.

## What the Chamber of Deputies publishes

### Gaceta Parlamentaria (gaceta.diputados.gob.mx): works from a runner, open, no key

Static HTML, ISO-8859-1, one Apache server, no robots.txt (404).

- **Iniciativas, one list per period**:
  `/Gaceta/Iniciativas/66/gp66_a<year><period>.html`, period one of
  `primero`, `segundo`, `perma1`, `perma2` (the Comisión Permanente in
  recess), `extra1`. Indexed from `/gp_iniciativas.html`. Nine lists exist
  for the LXVI (19 KB to 1.17 MB, about 4.9 MB in all); the rest 404 until
  their period starts. **8,247 entries.** Each entry carries the title, the
  presenter and party ("Presentada por la diputada ..., Morena."), the
  committee ("Turnada a la Comisión de Justicia."), every later step
  (prórroga, dictaminada, aprobada with the vote counts, desechada,
  retirada, publicado en el DOF), a link to the Gaceta issue, and the
  entry's **sequence number** in brackets: "(7223)". That number is the
  key. Origin, measured: deputies 7,664, Senate 296 (121 of them minutas),
  state congresses 197, the Executive 59, citizens 1. Statuses: prórroga
  3,628, turnada 3,515, retirada 270, publicada 212, aprobada 173,
  desechada 48, none yet 401.
- **Quirk: provisional numbers.** The newest 410 entries carry "(783X)"
  style placeholders until the Gaceta numbers them. Stored under
  `66/p/<gaceta anchor>` and re-keyed in place when the number appears.
- **Quirk: the list's own dates can be wrong.** The LXVI's first vote is
  printed "el jueves 29 de agosto de 2021" under the session heading 29 de
  agosto de 2024. The session heading is used.
- **387 "Votación" links** inside iniciativa entries point at the vote that
  decided them: this is the only machine link between an iniciativa and a
  vote anywhere in Mexico's federal data.
- **Votes, one list per period**: `/Gaceta/Votaciones/66/vot66_a<year><period>.html`
  (7 lists, **307 vote tables** in the LXVI). Each table,
  `/Gaceta/Votaciones/66/tabla<y>or<p>-<n>.php3` (about 5.7 KB), gives
  totals by group (Favor, Contra, Abstención, Quórum, Ausente). 73 of the
  307 list entries (votes "en lo particular") print no counts; the table has
  them. Per-deputy names come from a POST form on the table
  (`/voto66/ordi22/lanordi22.php3`, `evento`, `lola[<group><sense>]`):
  names only, no ids, inconsistent capitals ("AGUILERA CLARO ZARIA").
  SITL is better for positions.
- **The iniciativas search** (`base/inis/66/gp66_b_encuentra.php3`) returns
  nothing: its database says "actualizada el 31 de julio de 2024".
- Quirk: page titles are stale templates ("segundo periodo ordinario del
  primer año" on the second year's page).

### SITL / INFOPAL (sitl.diputados.gob.mx/LXVI_leg/): works from a runner, open, no key

The Chamber's information system. HTML, UTF-8, robots.txt answers 403 (no
rules served; RFC 9309 treats an unavailable robots.txt as no restriction).

- `votaciones_por_periodonplxvi.php`: the periods with votes. Seven:
  pert 1, 3, 5, 6, 8, 10, 11.
- `votacionesxperiodonplxvi.php?pert=<n>`: the votes of a period, under
  date headings. **285 votes in the LXVI to 7 October 2026**: 52, 47, 21,
  77, 72, 5 and 11 by period. Vote ids (`votaciont`) run 2 to 307 with gaps.
- `estadistico_votacionnplxvi.php?votaciont=<n>`: totals by group (a
  favor, en contra, abstención, solo asistencia, ausente, total) and a link
  per group.
- `listados_votacionesnplxvi.php?partidot=<g>&votaciont=<n>`: every
  deputy of that group with **their SITL id (`iddipt`) and position**. One
  page per group per vote, so about nine pages a vote. Party at the vote
  comes from the group the list is filed under.
- `listado_diputados_gpnp.php?tipot=TOTAL`: the 500 sitting deputies with
  SITL id, state and district or list seat (Morena 254, PAN 69, PVEM 61,
  PT 49, PRI 37, MC 29, independent 1). The group is named only by a logo.
- `condiciones_iniminpropolxvi.php`: a POST query form over iniciativas,
  minutas and proposiciones ("Con datos al 02 de octubre 2026"). Not used:
  the Gaceta lists carry the same entries with their progress.
- **Quirk: TLS.** sitl and web send only their leaf certificate, so urllib
  and curl both refuse them (`unable to get local issuer certificate`).
  The missing intermediate (DigiCert's RapidSSL TLS RSA CA G1, the same one
  gaceta sends) is in `config/mx-ca-intermediates.pem` with its SHA-256;
  verification stays on. It expires 2 November 2027.
- **Quirk: mixed encodings.** The vote lists are UTF-8 with one Latin-1
  byte in a CSS comment, so a whole-page fallback garbles every name. The
  collector decodes line by line.

**Matching SITL to the Gaceta.** A SITL vote finds its Gaceta table by
date and counts (favor, contra, abstención). On the 14 votes probed, 10
matched from the list alone; the other four were "en lo particular" votes,
whose counts come from the table page. In the live run, 228 of 250 votes
matched (91%); SITL lists 285 votes and the Gaceta 307 tables, so some
tables have no SITL vote (the Mesa Directiva election, for one).

### Rate limits

None published, none met. The probes and the live run ran at one request
a second per host (`HOST_DELAY`): 2,105 requests in 35 minutes without a
single 429, 5xx or timeout. Not measured: whether a faster rate is
tolerated. Do not test it.

## What the Senate publishes: blocked

- **www.senado.gob.mx sits behind Imperva (Incapsula)** and served the
  laptop a bot challenge on every page, homepage included. Per the Canada
  rule, a challenge is recorded, never solved.
- **Its robots.txt reads `User-agent: *` / `Disallow: /#test`.** Under the
  robots standard `#` starts a comment, so this is `Disallow: /`, the whole
  site. It is probably a mistake for a harmless test path, but read as
  written it forbids everything, so nothing on senado.gob.mx was requested
  from the runner. Christopher's call (Waiting on Chris).
- What the Senate's activity looks like from the Chamber's side: 296
  iniciativas by senators or the Senate (121 minutas) are in the Gaceta
  lists with their progress, because they reach the Chamber. **Senate votes
  and per-senator positions are not available from any open source
  measured.**
- **SIL (Secretaría de Gobernación)**, which historically compiled both
  chambers (iniciativas, votes, legislators): the old portal
  (sil.gobernacion.gob.mx) is now a shell pointing to nsil.gobernacion.gob.mx,
  which **refuses connections from the UK and from GitHub's runners**
  alike. Its robots.txt disallows only the legislator-profile scripts.

## Keys (never titles)

- Deputy: `66/<SITL dipt>`, per legislature.
- Iniciativa: `66/<Gaceta number>`; provisional entries `66/p/<anchor>`.
  Titles are formulaic ("Que reforma el artículo 4o. de la Constitución
  ..."): hundreds share their first twenty words.
- Vote: `dip-66-<votaciont>`.
- `config/watchlist-mx.yaml` is keyed by iniciativa number. A vote has no
  iniciativa number, so a watchlist entry may list the SITL votes that
  decided it (`votaciones: [...]`); matched Gaceta tables do the same
  automatically.

## Proposed Spanish terms (NOT APPROVED; for Christopher)

The areas are the English taxonomy's, unchanged. Only the words differ.
**MX** = Mexico-specific (legal or political vocabulary of Mexico); **ES** =
general Spanish, likely shared with Spain and Argentina. Counts are LXVI
iniciativa titles (of 8,247) and vote titles (of 285), measured with the
terms accent-folded. A term with 0 is still proposed where its absence is
the news (conversion practices: the federal ban passed in the LXV, in 2024).

**Matching notes for whoever generates `taxonomy-es`:**
- SITL prints titles in capitals, often unaccented ("INTERRUPCION"). The
  shared filter does not fold accents, so the collector matches the text
  and an accent-free copy against accent-free terms, without touching
  `src/filter.py`. Guard words (`with:`/`without:`) are not folded: write
  accented guard words twice.
- Spanish inflects for gender and number: use stems (`abort*`, `no nacid*`).
- `matrimonio`, `iglesia`, `religios*`, `familia` are far too common bare.

| Area | Tier 1 | Tier 2 |
|---|---|---|
| 1 Abortion | aborto* (5/0) ES; abortiv* ES; **interrupción legal del embarazo** (2) MX (the CDMX and federal legal term, "ILE"); interrupción voluntaria del embarazo ES (Spain, Argentina); interrupción del embarazo (1) ES; ILE MX (capitals only); despenalización del aborto (1) ES; no nacid* ES; desde la concepción ES (the state constitutional "protección de la vida desde la concepción" clauses); misoprostol, mifepristona ES; **NOM-046** MX (the federal health norm on sexual violence that obliges abortion after rape) | derechos sexuales y reproductivos (2), derechos reproductivos (3), salud sexual y reproductiva (1) ES; embarazo adolescente/infantil (4) ES; derecho a decidir (1) ES; provida, pro vida ES; muerte materna ES |
| 2 Assisted dying | eutanasia* (11) ES; muerte digna (10) ES; muerte asistida (2) ES; suicidio asistido ES; muerte médicamente asistida ES | **voluntad anticipada** (1) MX (the Ley de Voluntad Anticipada of CDMX and other states); cuidados paliativos (4) ES; obstinación terapéutica, ensañamiento terapéutico ES |
| 3 Gender medicine (children) | bloqueadores de la pubertad / puberales ES; reasignación de sexo ES; **infancias trans**, **adolescencias trans** MX (the Mexican and Argentine activist terms); niñez trans ES; disforia de género ES; detransición ES | hormonización ES; tratamientos hormonales (1) ES; transición de género ES |
| 4 Conversion practices | terapias de conversión (0) ES; **ECOSIG** (0) MX ("esfuerzos para corregir la orientación sexual y la identidad de género", the statutory name in the 2024 federal reform and in state codes); esfuerzos para corregir la orientación sexual MX; terapias reparativas ES | |
| 5 Sex-based rights | identidad de género (11) ES; identidad autopercibida, autopercepción ES (Argentina's Ley de Identidad de Género vocabulary); personas trans (3), mujeres trans ES; no binari* ES; transgénero*, transexual* ES; **Ley Agnes** MX (gender-identity recognition, Puebla and copies); rectificación de sexo, sexo registral ES | lenguaje incluyente (21) MX / lenguaje inclusivo (14) ES; diversidad sexual (7), orientación sexual (11), LGBT* (4) ES; crímenes de odio ES. **Proposed OUT, measured:** feminicidio (47 titles; violence against women, not the sex-based-rights fight) and paridad de género (22, MX: electoral gender parity). Germany carries Femizid; Christopher decides whether Mexico does. |
| 6 Parental rights, education | ideología de género ES; educación sexual (5) ES; educación sexual integral ES (Argentina's ESI); **educación integral en sexualidad** (1) MX (the SEP's term); pin parental ES (Spain); **derecho preferente de los padres** MX (the phrase in Mexican family law and treaties); derechos de los padres ES; educación en casa, homeschooling ES | **libros de texto gratuitos** (2) MX (the 2023 textbook fight); **Nueva Escuela Mexicana** (1) MX; patria potestad (13) ES; padres de familia (2) ES; control parental (7) ES; redes sociales (32) ES, which needs a guard (menores, niñas, niños, adolescentes) as English "social media" did |
| 7 Free speech, online safety | libertad de expresión (6) ES; censura ES (guard); **bloqueo de plataformas** MX (the 2025 telecoms-law fight over the power to block platforms); moderación de contenido* ES; verificación de edad (2) ES | discurso de odio (3), desinformación (2), noticias falsas ES; **violencia digital** (38) MX and **Ley Olimpia** MX (online sexual violence: mostly area 12 or out); **violencia política** (16) MX (used to sanction speech about women politicians; contested, read by triage); pornografía (6) ES; ciberacoso (7) ES |
| 8 Freedom of religion | libertad religiosa, libertad de culto*, libertad de creencia* ES; **asociaciones religiosas** (9), **culto público** (8), **ministros de culto** (2) MX (the Ley de Asociaciones Religiosas y Culto Público and article 130); objeción de conciencia (1) ES; intolerancia religiosa ES (MX: expulsions in Chiapas and Oaxaca); persecución religiosa ES | Estado laico (1), laicidad (1) ES; símbolos religiosos ES. Not bare: iglesia, religioso |
| 9 Marriage, family | matrimonio igualitario (1) ES; matrimonio entre personas del mismo sexo ES; matrimonio infantil (8) ES; matrimonio forzado ES; adopción homoparental ES | **sociedades de convivencia** MX (CDMX civil unions); concubinato (15) ES (mostly pensions: guard or drop); familias diversas ES; licencias parentales, licencia de paternidad (1) ES |
| 10 Surrogacy, embryology | gestación subrogada (2), maternidad subrogada (1) ES; vientre* de alquiler ES; gestación por sustitución ES (Spain, Argentina); reproducción asistida (6), reproducción humana asistida (2) ES; fecundación in vitro ES; embrión*, clonación ES; donación de óvulos/gametos ES | edición genética, células madre ES |
| 11 Migration (collated, never campaigned) | **Ley de Migración** (76) MX; **estaciones migratorias** (4) MX; condición de refugiado ES | migrante*, migración, asilo, refugiad* ES |
| 12 Prostitution, trafficking | trata de personas (55; 2 votes) ES; explotación sexual (10) ES; prostitución, lenocinio ES; trabajo sexual (1) ES; pornografía infantil (3) ES; turismo sexual ES | abuso sexual infantil (2) ES; abolicionis* ES |
| 13 Organ donation | donación de órganos (10) ES; trasplante* (6) ES; consentimiento presunto ES; donantes de órganos ES; tráfico de órganos ES | |

Mexico-specific terms carried 14 of the 161 tier-1 hits on their own; the
rest would be found by a shared Spanish list. The Mexico-only words that do
real work are **interrupción legal del embarazo**, **asociaciones
religiosas / culto público / ministros de culto** and, for state work,
**ECOSIG** and **Ley Agnes**.

## Phase 1: built, 9 October 2026

`tools/mx_rollcalls.py` into `mx_members`, `mx_iniciativas`,
`mx_divisions` and `mx_votes` (schema in `src/mx_store.py`, declared in
`db.TABLES`). Each run:

1. the 500 sitting deputies (1 page);
2. every Gaceta iniciativas list of the LXVI, re-read whole (10 pages,
   about 5 MB), because old entries gain their dictamen, vote and
   publication lines in place;
3. every Gaceta vote list (8 pages), plus each vote table whose counts the
   list does not print and that no stored vote has matched yet;
4. every SITL period page, then totals and every group's list for each
   vote that has no positions yet, oldest first, under a 40-minute budget.
   A vote whose lists do not add up to its totals is a gap, kept without
   positions, and retried next week.

**Classification waits for Christopher.** Until `config/taxonomy-es.yaml`
exists, areas come only from `config/watchlist-mx.yaml` (12 iniciativas,
groundwork draft). A vote takes the areas of its iniciativas (via the
matched Gaceta table) and of any watchlist entry naming it.
`--reclassify` fills everything in once the file lands.

**Live run on a GitHub runner, 9 October 2026** (into a scratch store,
never the real one; the one-off probe workflow, run 37885974449):

| | Read | Notes |
|---|---|---|
| Deputies | 560 | 500 sitting, plus 60 former deputies and substitutes met in vote lists |
| Iniciativas, LXVI | 8,247 | 410 provisional; 385 link a vote table; 12 on our ground (the watchlist, as designed) |
| Votes indexed | 285 | every vote SITL lists |
| Votes read with every position | 250 | the 35-minute budget stopped it; the other 35 drain next run |
| Positions | 124,949 | equal to the sum of the votes' own totals: nothing lost |
| Votes matched to a Gaceta table | 228 of 250 (91%) | 139 of them tie to at least one iniciativa |
| Gaps | 0 | 2,105 requests, no 429, no 5xx, no timeout |

Positions: a favor 99,195, en contra 12,703, ausente 12,181, abstención
870. Raw archive for a first run: 2,105 files, 11.7 MB gzipped; a later
week re-reads the Gaceta lists (0.7 MB gzipped) and only the new votes.
Speed: about one vote every 8.4 seconds at one request a second.

Tests: `tests/test_mx_rollcalls.py`, 32 tests on real pages saved by the
probe (`tests/fixtures/mx/`, trimmed; the trimming is described at the top
of the test file).

## Runtime: the Mini is the clock, a GitHub runner does the work

The Chamber refuses UK addresses, so "Mini first" cannot mean "the Mini
collects". It means the Mini keeps time:

- `ops/launchd/net.citizengo.parlmonitor.mx-weekly.plist`: Saturdays 15:30
  London, `tools/mini_run.sh mx-weekly` (moved from 04:00 at the countries
  merge of 10 October 2026, when Austria kept Saturday 03:00 and 05:00 UTC).
- `jobs/mx-weekly.sh` (`# mini_run: no-store`, so the Mini skips the
  895 MB store pull): asks the Gaceta once and logs whether this host can
  reach it (if the answer ever becomes yes, that is worth knowing), checks
  nothing already ran today, then `gh workflow run mx-weekly.yml`. mini_run
  then stamps `MINI_LAST_MX_WEEKLY`.
- `.github/workflows/mx-weekly.yml` ("Mexico weekly"): crons Saturday
  14:30 and 16:30 UTC as the backup, gated by `mini-check` with
  `job: MX_WEEKLY` and 150 minutes' grace; a dispatch always runs. Fetches
  the store and raw archive, runs `jobs/mx-collect.sh`, publishes the raw
  archive then the store, commits the sidecars. Timeout 75 minutes.
- **It runs only once merged to main** (GitHub schedules from the default
  branch, and `gh workflow run` needs the file on the ref). The Mini needs
  the plist installed by hand (copy to `~/Library/LaunchAgents`, then
  `launchctl bootstrap`).

- **Fortnightly (X9, Chris, 10 October 2026)**: Guatemala and Mexico run on
  GitHub Actions every second week to save Actions minutes. Mexico takes the
  odd ISO weeks: the workflow's gate passes a scheduled run only in an odd
  week, and `jobs/mx-weekly.sh` dispatches only in an odd week
  (`MX_FORCE=true` overrides). The coverage watch expects a 14-day cadence.
  Backfill budgets are unchanged.

## Files touched outside Mexico's own

Kept to the minimum, for the merge of the country branches:

| File | Change |
|---|---|
| `src/db.py` | 4 table names in `TABLES`; 2 lines in `init_db` calling `mx_store.ensure_schema` |
| `tools/coverage.py` | `PIPELINES` "Mexico weekly"; 3 `FEEDS` rows; `PIPELINE_FEEDS` and `AWAITING_FIRST_RUN` entries |
| `.github/workflows/alert.yml` | "Mexico weekly" in the watched list |

Everything else is new and Mexico's own: `tools/mx_rollcalls.py`,
`tools/mx_probe.py`, `src/mx_store.py`, `config/watchlist-mx.yaml`,
`config/mx-ca-intermediates.pem`, `tests/test_mx_rollcalls.py`,
`tests/fixtures/mx/`, `jobs/mx-weekly.sh`, `jobs/mx-collect.sh`, the plist,
`.github/workflows/mx-weekly.yml` and this document. The one-off probe
workflow (`mx-probe.yml`) was removed once the collector had run live on a
runner, as the US Senate probe was.

## Phase plan

1. **Phase 1 (built):** deputies, iniciativas with progress, every vote
   with every position, linked to iniciativas through the Gaceta.
2. **Phase 1b (needs Christopher):** `taxonomy-es` from the table above;
   then `--reclassify`, an edition (the US renderer is the model) and the
   DM to Christopher.
3. **Phase 2: the Senate**, if Christopher accepts the robots.txt reading
   or the Senate gives permission: its votes, its iniciativas and its
   Gaceta. Until then the Senate is visible only where it reaches the
   Chamber.
4. **Phase 3: debates and committee work.** The Diario de los Debates
   (cronica.diputados.gob.mx, also UK-blocked; not probed from a runner)
   and committee dictámenes; the Gaceta's daily issue (`/Gaceta/66/<yyyy>/
   <mon>/<yyyymmdd>-<part>.html`) carries the full text of each iniciativa,
   which body matching could read as `src/eudoc.py` does.
5. **Phase 4: the Supreme Court (SCJN) and the states** (below).

## The 32 state congresses (later; not probed)

Aguascalientes, Baja California, Baja California Sur, Campeche, Chiapas,
Chihuahua, Ciudad de México, Coahuila, Colima, Durango, Estado de México,
Guanajuato, Guerrero, Hidalgo, Jalisco, Michoacán, Morelos, Nayarit, Nuevo
León, Oaxaca, Puebla, Querétaro, Quintana Roo, San Luis Potosí, Sinaloa,
Sonora, Tabasco, Tamaulipas, Tlaxcala, Veracruz, Yucatán, Zacatecas.

Much of our ground moves there, not in Congress: abortion is a state
criminal-law matter, decriminalised state by state since Mexico City in
2007, and pushed along by the Supreme Court (its 2021 ruling against
Coahuila's ban, and its 2023 ruling against the federal penal code's,
which is why federal iniciativas 66/1130 and 66/1244 now rewrite Código
Penal Federal articles 329 to 332). Gender-identity recognition (the Ley
Agnes family), conversion-practice bans (ECOSIG) and civil unions are state
laws too. Which states have done what was not measured here; that is the
first job of a state phase, together with whether any state congress
publishes votes per member at all, and whether their hosts answer a runner.
Each of the 32 has its own site; there is no Open States for Mexico.

## Waiting on Chris

1. **Approve, cut or change the Spanish terms** above, and decide two
   scope questions inside them: is **feminicidio** ours (Germany carries
   Femizid) and is **violencia política en razón de género** area 7? Then
   `taxonomy-es` is generated and `--reclassify` run. Coordinate with the
   Spain and Argentina lists: one shared `taxonomy-es` plus country notes,
   or one file each?
2. **The Senate's robots.txt** (`Disallow: /#test`, which reads as
   "disallow everything"): treat it as written (Senate stays out), ask the
   Senate (comunicación social) for permission, or decide it is a typo for a
   test path. Separately, it serves a bot challenge to UK addresses, which
   we never work around.
3. **Runtime.** Accept that Mexico runs on GitHub with the Mini as clock,
   since the Chamber refuses UK addresses. No paid proxy is proposed. If you
   want the Mini's own reachability confirmed, run
   `curl -m 20 -sI https://gaceta.diputados.gob.mx/` on it once
   (`jobs/mx-weekly.sh` logs the answer every week anyway).
4. **Merge and install**: merge `mexico` to main when happy (the workflow
   only runs from main), then install the plist on the Mini.
5. **Review `config/watchlist-mx.yaml`** (12 entries, groundwork draft).
6. **A Mexican reader.** As with German, terms that are correct Spanish but
   not the words the Chamber uses will only be caught by someone who reads
   Mexican legislation; CitizenGO Mexico is the obvious reviewer.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (MX1, MX2 feminicide, MX3 political gender violence area 7) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.
- X9: fortnightly on GitHub Actions, odd ISO weeks; moved to Saturday 14:30/16:30 UTC.

Later phases and items for Chris (not built at the merge):

- The Senate stays out per its robots.txt (MX4).
- Member profiles (handover item 3, built 10 October 2026, branch `parity-profiles`): `profiles/mx/` from the store each weekly run (`tools/member_profiles.py mx`, src/member_profiles.py): party, chamber, constituency, every recorded position on a vote on our ground as the edition classifies it, verbatim, with the basis of the party at the vote; no verdicts, no DM. Initiatives name their presenter in a sentence, not linked to a member, so authorship is not shown.

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/mx_stance.yaml` holds 11 bill direction(s) (Claude's drafts from the watchlist) and 3 vote reading(s): 0 with proposed values, 0 procedural, 3 need reading, 0 confirmed. Guide: `docs/5ca-mx-readings.md`; confirm with `python3 tools/country_5ca.py --cc mx --sign-from-doc --by NAME`. Sheets (`data/5ca/mx-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for Mexico (`config/stance_signers.yaml`).
