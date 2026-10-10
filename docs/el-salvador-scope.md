# El Salvador: scoping the Asamblea Legislativa monitor

Probed live on 9 October 2026 from the laptop. Every number below was
measured, not estimated. Raw JSON and HTML responses are archived under
`data/raw/2026-10-09/` (61 `sv-probe_*` files from the exploration, 896
`sv-rollcalls_*` files from the collector's own runs; vote PDFs are not
archived, see below). Every request went through `src/http.py` with the
honest CitizenGO User-Agent and a one- to three-second throttle: about
2,700 requests over the day, all answered except one 404 and two gateway
timeouts. No CAPTCHA, bot challenge or block was met anywhere. The
Asamblea is unicameral and there are no regional legislatures (the 44
municipal councils are not legislatures), so "national first" is the job.

## Decisions already taken (Christopher)

- **Own edition**, delivered to Christopher alone (a Slack DM), as the US.
- **Shared taxonomy concept, shared Spanish file.** `config/taxonomy.yaml`
  and every existing taxonomy file are untouched. The El Salvador terms are
  PROPOSED below as additions to the shared Spanish list drafted on the
  Spain branch (`docs/spain-scope.md`); `config/taxonomy-es.yaml` is
  generated only after Christopher approves them.
- **National parliament first.** There is nothing else at that level.
- **Mac Mini first, GitHub Actions as the backup.** No new paid services.
  Nothing posts publicly anywhere.

## The finding that shapes everything: a one-party Asamblea

All of this is read off the Asamblea's own pages and its 783 readable vote
PDFs of the 2024-2027 legislature (46,391 individual positions):

- **60 deputies: Nuevas Ideas 54, ARENA 2, PCN 2, PDC 1, VAMOS 1.** Nuevas
  Ideas alone holds 90 per cent of the seats, more than the three-quarters
  (45) a same-legislature constitutional amendment now needs. The
  legislature runs from 1 May 2024 to 30 April 2027.
- **No vote has been close.** Of the 783 recorded votes, **546 had no vote
  against, and none had more than three**; 88 had any abstention. The
  smallest majority was 44 in favour, the median 57. **Not one of the
  46,391 positions is a Nuevas Ideas deputy voting against the rest of
  Nuevas Ideas.** Every vote against came from VAMOS (220) or ARENA (169);
  PCN and PDC never voted against anything.
- **The executive writes the agenda.** Of the 749 pieces of
  correspondence (piezas) read to the plenary, **571 came from the
  President, the Vice-President or a minister** and 122 from Nuevas Ideas
  deputies; 4 named an opposition deputy, all requests for a public
  pronouncement. None of the 527 committee reports (dictámenes) is on an
  opposition initiative. Every unfavourable report (8) is a refused pardon
  or an old file closed.
- **About a third of the decisions skip committee.** The vote list labels a piece
  voted the day it arrives: "PIEZA nA DT" is the vote for *dispensa de
  trámite* (no committee stage), "PIEZA nA FS" the vote on the substance a
  minute later. Of the 784 recorded votes, **190 are DT and 184 FS votes**,
  against 404 on dictámenes. The summary of session 129 (7 October 2026)
  shows pieza 1-A read, dispensed and approved within the hour, and an
  opposition request to add an item failing with 3 votes.
- **Only eight standing committees**, and Hacienda (budget and loans)
  produced 263 of the 527 dictámenes.
- **The Constitution is amended in a day.** The Asamblea's list of
  constitutional reform agreements shows the outgoing Assembly agreeing on
  29 April 2024 that an amendment may be ratified by the same legislature
  with three-quarters of the votes (article 248), and the current one
  ratifying that rule (session 41) and then **eight amendments between
  February 2025 and April 2026**: article 210 (repealed); articles 80 and
  133; articles 75, 80, 152 and 154 (the presidential term, re-election and
  the run-off); article 208 twice; 172; 27; 79. The presidential reform was
  agreed and ratified **the same day, 31 July 2025, in sessions 66 and 67,
  each step by dispensa de trámite, 57 to 3**. Before 2024 an amendment
  needed the next legislature, and 42 agreements lapsed unratified.
- **Our ground in that record**: a reform of **articles 32, 33 and 34 so
  that marriage and adoption cannot be between persons of the same sex was
  agreed four times (2006, 2009, 2012, 2015) and never ratified.** Under the
  2024 article 248 rule the current Asamblea could agree and ratify it in
  one sitting.
- **The published vote record has a hole.** Sessions **41 to 64 (29
  January to 16 July 2025) and 98 have no recorded vote in the vote list at
  all**, yet the session archive holds their dictámenes and piezas. That
  window includes the ratification of the article 248 rule and the **Ley de
  Agentes Extranjeros** (pieza 1-A of session 56, 20 May 2025), the one
  item of the legislature most clearly on CitizenGO ground (foreign funding
  of NGOs, charities and churches). How each deputy voted on it is not
  published.
- **Context, not measured here**: the Asamblea elected in 2021 removed the
  Constitutional Chamber and the Attorney General on its first day; the
  state of exception declared in March 2022 is renewed roughly monthly (27
  renewals were read to this legislature, the latest the "(54°)
  Prolongación" of 26 August 2026). Abortion is banned without exception
  (Penal Code; article 1 of the Constitution recognises the human person
  from conception), and the governing party's public line on abortion,
  same-sex marriage and "gender ideology" in schools is close to
  CitizenGO's.

**What this means for the monitor.** The Asamblea ratifies what the
executive sends. Votes say almost nothing about individual deputies, and
there is no advance warning, because dispensed items join the agenda in
the sitting itself. A monitor can still **record within a week anything the
Asamblea passes on our ground**, with its extract, its expediente and the
few deputies who dissented, and notice when the vote record is missing.

## What El Salvador publishes

### Asamblea Legislativa (www.asamblea.gob.sv): keyless, WORKS TODAY

A Drupal site. No account, no key, no published rate limit; `robots.txt`
disallows only admin and search paths. The public pages draw their tables
from JSON endpoints, which are what the collector reads. There is **no
open-data portal**: `transparencia.asamblea.gob.sv` (the access-to-
information unit) links back to the same pages for votes, decrees and
attendance and offers no files.

**Recorded votes (votaciones)**: the spine.

- `GET /sesion-plenaria/votaciones-ajax?draw=1&start=N&length=M` (DataTables
  server-side; `length=1000` honoured): **6,710 votes, 18 May 2012 to
  7 October 2026**, newest first, each `{documentofk, fecha, no_sesion,
  legislatura, leyenda}`. By legislature: 2012-2015 1,165; 2015-2018 1,426;
  2018-2021 1,762; 2021-2024 1,572; **2024-2027 784** (106 days, 104
  sessions); one stray 2009-2012 row. The whole list is seven calls, 14 s.
- The `leyenda` is the vote's only label and **names no subject**: "COMISION
  DE HACIENDA DICTAMEN # 267 FAVORABLE", "PIEZA 2A FS", "NOTIFICACIONES
  CSJ". Spellings vary ("COM. DE SALUD ... DICT#13", "DICTAMEN No148",
  "PIEZA 1 A DT", "...FAVORABLE.pdf").
- **One PDF per vote**, `/sites/default/files/documents/votaciones/<GUID>.pdf`
  (345 to 545 KB, mostly a logo and embedded fonts): a voting-system export
  saved from Word, real text. Meeting, vote name, times, totals (SI, NO,
  ABST., No Votado), totals by party and **every deputy's position by name
  and party**. 2 to 10 s each (busier in the morning).
- **Three PDF layouts in this legislature alone**, all parsed: to mid-2025,
  Spanish labels, positions grouped by party then position, names in mixed
  case ("Francisco Lira"), and the totals page an image; from about July
  2025, Spanish labels with positions grouped by position and the party on
  each line, names in capitals; from 2026, the same in English labels. So
  the same deputy is printed two ways (239 name strings, 162 once case is
  folded, substitutes included). The
  2012-2015 PDFs are a fourth, CSV-like layout with seat numbers, not read.
- One vote PDF of the 784 is missing (404: Hacienda dictamen 221,
  27 May 2026).

**The session archive**: what a vote was about.

- `POST /sesion-plenaria/historico-sesion-ajax` with `desde`, `hasta`
  (ISO dates): the day's sessions (`codigo` GUID, type, number, date) and
  **the first session's documents**: `dicta` (committee id and name,
  `numero_dictamen`, `tipo_resultado`, **`expediente`**, the extract), `piezas`
  (order, short title, the full extract read to the plenary), and GUIDs of
  the agenda, convocation, session summary (`resum`), notices, committee
  reports and attendance, each a PDF under
  `/sites/default/files/documents/<folder>/<GUID>.pdf`.
- **One day at a time.** A day with a sitting took 1 to 45 s (about 37 s
  typically), a day without one about 1 s; a five-week range timed out at
  40 s and a two-week range was dropped after 74 s. Two single days gave a
  504 (2024-06-11, 2025-06-05).
- **The whole legislature, every calendar day** (890 days): 134 sessions
  (126 ordinary, 4 extraordinary, 3 solemn, 1 inaugural), 527 dictámenes
  (525 with an expediente), 749 piezas. 30 of the 134 sessions have no
  recorded vote; two days with recorded votes (2024-11-22, 2026-02-12) were
  never filed in the archive.
- **Filing lags the sitting.** 29 September was in the archive on
  9 October; 7 October was not. The archive answers an unfiled day exactly
  as a day with no sitting (`validar: false`), so the collector re-asks for
  21 days and only then concludes.
- `POST /sesion-plenaria/get-archivos-ajax` with `sesion=<GUID>`: one
  session's documents (40 s), needed only for the second session of a day.
  `get-por-sesion-ajax` took 89 s and returned nothing for session 129.
- **The expediente is the bill's own ID** ("755-9-2026-1",
  number-month-year-sequence, assigned on entry), printed on every
  dictamen. A pieza approved with dispensa de trámite never shows one; its
  number in its session is the only key it has.

**Other sources probed**

- `/asamblea/diputados`: the 60 sitting deputies as HTML cards with GUID,
  full name, party (resolved through the page's filter list) and
  department. Vote PDFs print short names, so any join is by name.
- `/sesion-plenaria/correspondencia/piezas`: the latest session's piezas as
  HTML (9 on 9 October, session 129), before the archive files them.
- `/sesion-plenaria/resumen-plenaria`: the latest session summary PDF, text
  readable by `src/sv_pdf.py`: each dictamen with its expediente, the vote
  count and **the decree number it became** ("Decreto Legislativo
  No. 683"), and agenda changes refused.
- `/leyes-y-decretos/acuerdos-reforma-constitucion-ajax?estado=R|P|N`:
  every constitutional reform agreement, ratified (25), pending (0) and not
  ratified (42), with dates and summaries. Small and high-signal; phase 2.
- `/leyes-y-decretos/decretos-por-anios/<year>/0`, `busqueda-decretos`:
  decrees by year back to 1860, PDFs. Phase 2 if decree text is wanted.
- `/asamblea/comisiones/view/<id>`: committee membership; no agendas or
  minutes online. No plenary transcripts online either (TV and radio only).
- `app.asamblea.gob.sv` (linked from the homepage) does not resolve.

## Phase 1: built, 9 October 2026

`tools/sv_rollcalls.py` into `sv_members`, `sv_sessions`, `sv_dictamenes`,
`sv_piezas`, `sv_divisions`, `sv_votes` and `sv_vote_days` (schema in
`src/sv_store.py`, declared in `db.TABLES`). PDFs are read by
`src/sv_pdf.py`, a small stdlib reader (FlateDecode streams, WinAnsi fonts
with their widths, Identity-H fonts through ToUnicode), so no new
dependency. Live run into a scratch database (not the store), the whole
2024-2027 legislature:

| | Read | Notes |
|---|---|---|
| Recorded votes listed | 784 | 404 dictamen, 374 pieza (190 DT, 184 FS), 6 other |
| Days asked of the archive | 890 | every day since 1 May 2024; 134 sessions |
| Dictámenes | 527 | 525 with an expediente |
| Piezas | 749 | |
| Vote PDFs read | 783 | 1 missing on the site (404) |
| Positions | 46,391 | |
| Votes linked to their dictamen or pieza | 750 of 778 | see below |
| Deputies | 60 | NI 54, ARENA 2, PCN 2, PDC 1, VAMOS 1 |

The 28 unlinked votes: 4 from 7 October (not filed yet), 6 on the two days
never filed, 4 on the day the archive gave a 504, and 14 whose label number
is not among that session's dictámenes or piezas.

- **Keys, never titles**: a dictamen is `<legislature>/<committee id>/<number>`
  (`2024-2027/97/266`) and carries its expediente; a pieza is
  `<legislature>/<session>/<order>A` (`2024-2027/128/2A`); a vote is
  `sv-<GUID>`. The watchlist (`config/watchlist-sv.yaml`, empty) is keyed by
  expediente, or by pieza key for dispensed items.
- **Linking**: "DICTAMEN # 267" in session 128 is the dictamen numbered 267
  among that session's dictámenes (committee words break a tie); "PIEZA 2A
  FS" and "PIEZA 2A DT" are pieza 2A of the session. A vote's areas are its
  item's, because its label names nothing.
- **Areas stay NULL until the Spanish taxonomy exists.** NULL is
  "unclassified", `[]` "classified, nothing found". `--taxonomy <file>`
  classifies with a draft; `--reclassify` re-derives offline.
- **Vote PDFs are not archived** to `data/raw/` (about 400 KB each, mostly
  logo and fonts; about 15 a week): the GUID URL is the provenance and the
  parsed positions are stored. The JSON (vote list, archive days, members
  page) is archived as usual. A decision for Christopher (below).
- **Re-reads**: every day of the legislature not yet answered by the
  archive, the last 21 days (the filing grace), and every vote whose PDF is
  unread. The archive gets at most half of a run's clock so the PDFs are
  never starved. A run cut short resumes from the store.
- **Exit codes**: 0 clean, 3 stored what it could and recorded gaps (the
  job still publishes), 1 otherwise.

**The weekly** (`jobs/sv-weekly.sh`, shared by both runners): Sundays 10:00
London on the Mac Mini (`ops/launchd/net.citizengo.parlmonitor.sv-weekly.plist`);
`.github/workflows/sv-weekly.yml` at 10:00 and 13:00 UTC (an hour later than first built; the Dominican Republic holds 09:00 and 12:00) is the backup,
gated by `mini-check` with job `SV_WEEKLY` (grace 260 minutes, as Spain).
The plenary sits about once a week. **It runs only once merged to main.**
After the backfill a week is about 22 archive calls (mostly 1 s) and 15
PDFs: a few minutes.

**The first run is a backfill and is announced here**: 890 archive days
(about 134 x 37 s plus 756 x 3 s, two hours) and 784 vote PDFs (one to two
hours). With the 45-minute budget, half of it for the archive, that is
about **six Sundays**. Faster: run it once by hand on the Mini with
`python3 tools/sv_rollcalls.py --budget-seconds 14400`, then publish as the
job does. Either way it should run on the Mini.

Tests: `tests/test_sv_rollcalls.py`, 21 tests on real responses saved on
9 October (`tests/fixtures/sv/`, about 380 KB; the five vote PDFs had
images, metadata and font programs emptied, and their extracted text was
checked identical before and after): labels, the vote list and the
legislature boundary, all three PDF layouts, a pieza with a vote against,
split name cells, a synthetic two-font PDF for the reader, an archive day,
the members page, an end-to-end weekly with a fake client, the day sweep,
the filing grace, and the watchlist.

## How much touches CitizenGO ground

Corpus: the 527 dictámenes and 749 piezas of the 2024-2027 legislature
(extract text, plus the pieza's short title): 1,276 items.

| Taxonomy | Items matching any area | Excluding migration-only and state-of-exception-only |
|---|---|---|
| `config/taxonomy.yaml` (English, unchanged) | 0 | 0 |
| Spain's proposed Spanish list, unchanged | 17 | 6 |
| Spain's list plus the El Salvador additions below | 67 | 27 |

What the 27 are: the **Ley de Agentes Extranjeros** (May 2025); the **Ley
del Registro del Estado Familiar** (the civil-status register: filed 2024,
returned with presidential observations, re-filed 2026; 4 items); reforms
of the women's violence law (LEIV) and of ISDEMU's law (3); the personal
data protection law and the cybercrime law (5); tax exemptions for the
Catholic Church (altar wine) and a Baptist mission, and the pronouncement
for the Día Nacional del Pastor Evangélico (3); the transplant law (2);
the Ley Amor Convertido en Alimento and its regulator (4, breastfeeding);
the Nacer con Cariño maternity hospital loan (2); two suicide-prevention
pronouncements (opposition deputies); one permission for a citizen to
accept an honour from the Holy See (noise). The state of exception alone
accounts for 27 more (one per renewal).

**Nothing in two and a half years touched abortion, marriage, gender
identity, sex education or parental rights.** The English list is blind to
Spanish, as it was to German; the low count with a Spanish list is not a
blind spot, it is what this Asamblea does: loans, budget transfers, tax
exemptions, ministers' annual reports, emergency decrees and the monthly
state of exception.

## Proposed Spanish terms for El Salvador (v0.1, FOR APPROVAL)

**Start from the shared Spanish list in `docs/spain-scope.md`** (Spain
branch). Everything there not marked "Spain only" is ordinary Spanish legal
vocabulary and applies here. The terms below are additions; each is **El
Salvador only** unless marked "shared". Drafted by Claude and measured
against the corpus above; not yet read by a Salvadoran campaigner. The
counts are items in the 1,276.

- **1. Abortion.** Tier 1: "artículo 133" [with: Código Penal, aborto];
  "aborto terapéutico" (shared); "aborto eugenésico" (shared);
  "emergencia* obstétrica*" (shared); "desde el instante de la concepción"
  (article 1 of the Constitution); "homicidio agravado" [with: parto,
  embarazo, aborto, recién nacido] (how obstetric cases are prosecuted);
  "Las 17"; "Caso Beatriz"; "Beatriz y otros" (the Inter-American Court
  case). Tier 2: "Ley Nacer con Cariño", "Nacer con Cariño" (the 2022
  maternity-care law and hospital); "materno infantil", "materno-infantil",
  "atención prenatal" (shared); "vida desde la concepción" (shared).
  MEASURED: 2, both the maternity-hospital loan.
- **5. Sex-based rights and gender identity.** Tier 1: "Ley de Identidad de
  Género" (bills filed 2018-2021, archived). Tier 2: "Ley Especial Integral
  para una Vida Libre de Violencia para las Mujeres"; LEIV; "Ley de
  Igualdad, Equidad y Erradicación de la Discriminación contra las
  Mujeres"; ISDEMU; "Ciudad Mujer". MEASURED: 3 (LEIV twice, ISDEMU).
- **6. Parental rights and education.** Tier 1: "educación integral de la
  sexualidad" (shared). Tier 2: "Ley Crecer Juntos", "Crecer Juntos" (the
  2022 child-protection law that replaced LEPINA); LEPINA; "Ley de
  Protección Integral de la Niñez y Adolescencia"; "Ley General de
  Educación"; "Ley de la Carrera Docente"; "moral, urbanidad y cívica".
  MEASURED: 0. ("primera infancia" was tried and dropped: 3 hits, all loans
  and pronouncements.)
- **7. Free speech, privacy and civil liberties.** Tier 1: "Ley de Agentes
  Extranjeros"; "agentes extranjeros" (shared). Tier 2: "régimen de
  excepción" (shared; see Waiting on Chris); "Ley Especial contra los
  Delitos Informáticos"; "delitos informáticos" (shared); "protección de
  datos personales" (shared); "Ley de Acceso a la Información Pública";
  "Ley de Asociaciones y Fundaciones sin Fines de Lucro" (the NGO and
  church register). MEASURED: 33 (27 state-of-exception renewals, the
  agents law, 3 data protection, 2 cybercrime).
- **8. Freedom of religion or belief.** Tier 1: "libertad de culto"
  (shared). Tier 2: iglesia* [with: personalidad jurídica, reconocimiento,
  registro, exención, exoneración] (shared); "entidades religiosas"
  (shared); "Día Nacional de la Biblia", "Pastor Evangélico" (commemorative
  pronouncements, a recurring Salvadoran genre). MEASURED: 4 with Spain's
  `Iglesia católica` and `Santa Sede`.
- **9. Marriage and family.** Tier 1: "hombre y mujer" [with: matrimonio,
  unión] (shared); "artículo 32", "artículo 34" [with: Constitución,
  matrimonio, familia]; "protección integral de la familia" (shared).
  Tier 2: "Registro del Estado Familiar" (also area 5: it is where a name
  or sex marker would be changed); "Código de Familia" (shared with Central
  America); "unión no matrimonial"; "Ley Especial de Adopciones"; "cuota
  alimenticia", "pensión alimenticia" (shared); "Ley Amor Convertido en
  Alimento". MEASURED: 8 (register 4, breastfeeding law 4). Bare
  "adopción" was tried and dropped: it matched the adoption of transport
  measures.
- **11. Migration** (collated, hidden). Tier 1: "Ley Especial de Migración
  y Extranjería"; retornad* [with: migra, deportad, connacional];
  deportad* (shared). Tier 2: connacionales (shared); "salvadoreños en el
  exterior" (also a committee's name, so noisy). MEASURED: 13.
- **12. Prostitution and trafficking.** Tier 1: "Ley Especial contra la
  Trata de Personas". MEASURED: 0.
- Areas 2, 3, 4, 10 and 13 need nothing Salvadoran; the shared list
  already caught the transplant law (13) and the suicide pronouncements (2).

Matching traps in this corpus: short titles drop accents ("Regimen de
Excepcion", "Exoneracion"), so an accented term misses the title and is
saved only by the accented extract; committee names recur ("Salvadoreños
en el Exterior", "Niñez e Integración Social") and must never be terms;
extracts are long government sentences ("en el sentido se reforme..."), so
phrases work well.

## Recommendation: is an edition worth it?

**Yes, but a thin one: collect weekly, tell Christopher only when something
lands on our ground, and say so once a month when nothing has.** Reasons:

1. **It is cheap and already built.** One keyless source; after the
   backfill a week is a few minutes of requests, with every position kept.
2. **The risk is sudden, not gradual.** With dispensa de trámite and the
   2024 article 248 rule, a law or a constitutional amendment on our ground
   (the marriage reform agreed four times, an education or "gender
   ideology" law, another foreign-funding rule) can be filed, passed and
   ratified in one sitting. A weekly collector is the earliest anyone
   outside the room will know.
3. **The volume is tiny**: 27 items in two and a half years with the
   drafted terms, few of them central. A weekly edition would be empty
   almost every week.
4. **What it cannot give**: meaningful per-deputy scorecards (54 deputies
   vote as one), debate (no transcripts), advance warning, or the votes of
   the 24 sessions the Asamblea did not publish. A 5CA-style record would
   show six opposition deputies and nothing else.
5. **The calendar**: this legislature ends on 30 April 2027; the next
   Asamblea is elected in early 2027 (date not verified here). A change in
   composition would change this recommendation.

## Proposed phasing

1. **Phase 1 (built, this branch).** Recorded votes with every position,
   dictámenes and piezas with their extracts and expedientes, deputies;
   Mini-first weekly; unclassified until the taxonomy is approved.
2. **Phase 1b (after approval).** Generate `config/taxonomy-es.yaml` (shared
   with Spain and the other Spanish-language editions), dispatch
   `sv-weekly` with "reclassify".
3. **Phase 2.** The constitutional reform agreements (three small JSON
   calls); the decree number each item became, from the session summary
   PDF; the latest session's piezas from the HTML page, so an item is seen
   before the archive files it.
4. **Phase 3.** The alert-only DM and monthly line (the `us_monitor.py`
   pattern, gated, Christopher alone). Older legislatures (2012-2024, 5,925
   votes; the 2015 layout needs its own parser) only if a historical record
   is wanted.

Courts: the Supreme Court's Constitutional Chamber (csj.gob.sv) decided the
past fights on our ground (the 2013 Beatriz amparo); its 2021 replacement
is not an independent check on the Asamblea. Not probed. Referendums are
not a channel here.

## Shared files touched (for the merge of the country branches)

- `src/db.py`: seven `sv_*` names added to `TABLES`, and
  `sv_store.ensure_schema` called from `init_db` (11 lines).
- `tools/coverage.py`: `El Salvador weekly` in `PIPELINES`,
  `PIPELINE_FEEDS` and `AWAITING_FIRST_RUN`; `sv_members` (7 + 4 days),
  `sv_divisions` and `sv_dictamenes` (31 + 31) in `FEEDS`; `sv_sessions`
  and `sv_piezas` in `ONCE_EVER` (quiet in recess).
- `.github/workflows/alert.yml`: `"El Salvador weekly"` added (1 line).

Not touched: any taxonomy file, `tools/generate_taxonomy.py`,
`src/http.py`, `tools/mini_run.sh`, `.github/workflows/mini-check.yml`.
New files only otherwise: `src/sv_store.py`, `src/sv_pdf.py`,
`tools/sv_rollcalls.py`, `config/watchlist-sv.yaml`, `jobs/sv-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.sv-weekly.plist`,
`.github/workflows/sv-weekly.yml`, `tests/test_sv_rollcalls.py`,
`tests/fixtures/sv/`, this document.

## Waiting on Chris

1. **Is an edition worth it?** Recommended: yes, alert-only plus a monthly
   line (above). Or collect only, with no DM, until the 2027 election.
2. **Approve or amend the El Salvador terms**, as additions to the shared
   Spanish list, ideally after a read by someone who campaigns in El
   Salvador. Scope questions:
   - **The state of exception** ("régimen de excepción"): a civil-liberties
     item renewed about monthly since 2022, 27 renewals this legislature.
     Drafted at tier 2 in area 7; in, it is a monthly hit. In or out?
   - **Commemorative pronouncements and tax exemptions for churches**
     (Día del Pastor Evangélico, altar wine): drafted at tier 2 in area 8.
     Worth seeing?
   - **The Ley del Registro del Estado Familiar**: area 9 or area 5, and
     should someone read what it says on name and sex markers?
3. **Vote PDFs not archived** (about 400 KB each, about 15 a week): agree,
   or archive them (about 300 MB for the backfill, 6 MB a week)?
4. **The missing votes of sessions 41-64 and 98** (including the Ley de
   Agentes Extranjeros): ask the Asamblea's access-to-information unit for
   them, or note the gap and move on?
5. **Merge and install.** Merge `el-salvador` to main when ready (the
   workflow schedules only from main); copy the plist to the Mini and
   bootstrap it. No secret or key is needed.
6. **The first-run backfill** (about four hours of slow requests, six
   Sundays at the job's budget, or one manual four-hour run on the Mini):
   say which, or whether to limit it to the last twelve months.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (SV2, SV3 state of exception, SV4 church items) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.
- SV5: vote PDFs are now archived to data/raw.
- SV7: the backfill runs over six Sundays at the job's budget, as built.
- Weekly moved to Sunday 10:00/13:00 UTC (the Dominican Republic holds 09:00/12:00).

Later phases and items for Chris (not built at the merge):

- The unpublished votes (SV6): a request in Chris's name.

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/sv_stance.yaml` holds 0 bill direction(s) (Claude's drafts from the watchlist) and 0 vote reading(s): 0 with proposed values, 0 procedural, 0 need reading, 0 confirmed. Guide: `docs/5ca-sv-readings.md`; confirm with `python3 tools/country_5ca.py --cc sv --sign-from-doc --by NAME`. Sheets (`data/5ca/sv-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for El Salvador (`config/stance_signers.yaml`). No qualifying vote in the store yet (the 784 votes read carry no area).
