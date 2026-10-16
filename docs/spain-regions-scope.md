# Spain: the seventeen autonomous-community parliaments

Probed and built on 12 October 2026 (branch `regions-es`), from the laptop,
with the honest user agent (`CitizenGO-ParlMonitor/1.0 (contact:
cjoyce@citizengo.net)`) through `src/http.py`, robots.txt read first, raw
replies archived under `data/raw/2026-10-12/` (feeds `esreg-probe` and
`es-regions`). Live runs went into a scratch database inside the worktree,
never the store. Every number below was measured unless it says otherwise.

The national edition (the Congreso, `docs/spain-scope.md`) stays as it is;
this is the regional layer that the Spanish edition now carries in a section
of its own.

## The finding that shapes everything: one platform serves all seventeen

**The BOE publishes every community's laws, in Spanish.** Each regional law
and decree-law appears in section I of the Boletín Oficial del Estado
("Disposiciones generales") under its community's department, weeks after
its own regional bulletin, and always in Spanish, including the laws of
Cataluña, the Comunitat Valenciana, Galicia, the País Vasco, Navarra and the
Illes Balears that their parliaments pass in (or alongside) a co-official
language. The BOE's open-data API serves each day's summary as JSON:

    GET https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD
    Accept: application/json

- One request per issue, keyless, no rate-limit headers; a Sunday answers
  404 (no issue). About 340 KB per issue.
- robots.txt disallows `/diario_boe/xml.php?` and the PDF mirror
  `/datos/pdfs/`, which are never read; `/datosabiertos/` is not disallowed.
- Each item carries the BOE identifier (`BOE-A-2026-20746`, the key), the
  title, the subject heading (`Derechos y prestaciones vitales`), and HTML
  and PDF links.

**Measured, 1 January to 9 October 2026 (246 issues read): 153 community acts
in section I.** By month: January 21, February 18, March 17, April 19, May
19, June 15, July 27, August 9, September 5, October (to the 9th) 3. By rank:
104 laws, 24 decree-laws, 7 decrees, 6 corrections, 12 other (traffic
resolutions, university statutes, two Corts Valencianes rules reforms). By
community: Cataluña 25, Navarra 24, Comunitat Valenciana 12, Andalucía 11,
País Vasco 11, Cantabria 10, Canarias 8, Madrid 8, Galicia 8, Asturias 7, La
Rioja 6, Extremadura 6, Aragón 5, Illes Balears 5, Castilla y León 3,
Murcia 3, Castilla-La Mancha 1.

**The lag is real:** Asturias' Ley 6/2026 of 10 September reached the BOE on
6 October; Madrid's Ley 5/2026 of 7 July on 29 August. The layer reports a
law when it is enacted and published, not while it is debated. For bills in
passage the regional parliaments' own sites are the only source, and only
some of them can be read.

## Region by region

Ranked by population (INE estimates, rounded, not measured here) and then by
what we can read. "Bills" means a machine-readable list of bills in passage.

| # | Community and parliament | Pop. (m) | Bills source | Format | robots.txt | From the laptop | Built |
|---|---|---|---|---|---|---|---|
| 1 | Andalucía, Parlamento de Andalucía | 8.6 | "Iniciativas en tramitación" RSS (`/webdinamica/portal-web-parlamento/utilidades/sindicacionrss.do?contenido=Iniciativas`) | RSS 2.0, ISO-8859-1 | allows all | 200; 3 items (the XIII legislature began in 2026) | **yes** (`an`) |
| 2 | Cataluña, Parlament de Catalunya | 8.1 | home page lists the latest bills; open-data page `/web/actualitat/dades-obertes/` | HTML, Catalan only | allows `/web` | home 200, open-data page **500** | no: open data down (the Catalan list exists since 12 October 2026) |
| 3 | Madrid, Asamblea de Madrid | 7.1 | none reachable | | 403 | **Sucuri JavaScript challenge** (307 "Javascript is required") on every path, robots.txt included | no: bot check, never bypassed |
| 4 | Comunitat Valenciana, Corts Valencianes | 5.3 | `/ca-va/activitat/iniciative` (newest first, BOC number and date) | HTML (Drupal), titles in **Valencian** only; `/es/` paths 404 | allows | 200; 10 bills on page 1 | **yes** (`vc`, lang `ca`, classified with taxonomy-ca since 12 October 2026) |
| 5 | Galicia, Parlamento de Galicia | 2.7 | none reachable | | 403 | **Akamai 403** on every path | no |
| 6 | Castilla y León, Cortes de Castilla y León | 2.4 | `/Participa/ParticipaIniciativasLegislativas` (bills open to comment) | HTML; entries are HTML comments while none are open | allows (except agendas, RSS) | 200; "no hay ningún Proyecto de Ley en tramitación" | no: no list while none are open (XII legislature new) |
| 7 | País Vasco, Parlamento Vasco (legebiltzarra.eus) | 2.2 | | bilingual site | unknown | **no answer** (connect timeout, both hosts) | no |
| 8 | Canarias, Parlamento de Canarias | 2.3 | `/leyes/` ("Leyes en tramitación"), one list per type | HTML | **Crawl-delay 3**; disallows `/api/`, `/api2/` | 200; 12 bills (1 decree-law, 4 government, 7 members') | **yes** (`cn`), 3 s apart |
| 9 | Castilla-La Mancha, Cortes de Castilla-La Mancha | 2.1 | `/index.php/iniciativas` | HTML, no bill list found | allows | 200 | no: no list to read |
| 10 | Murcia, Asamblea Regional | 1.6 | | | **`Disallow: /`** ("bloqueo total de rastreadores") | 200 | no: robots.txt |
| 11 | Aragón, Cortes de Aragón | 1.35 | `bases.cortesaragon.es/bases/tramitacion.nsf` (Domino views) | HTML | main site allows; bases host unknown | main 200, **bases host no answer** | no |
| 12 | Illes Balears, Parlament | 1.2 | | Catalan and Spanish | unknown | **no answer** | no |
| 13 | Extremadura, Asamblea | 1.05 | | | **`Disallow: /`**, Crawl-delay 60 | 200 | no: robots.txt |
| 14 | Asturias, Junta General | 1.0 | "Leyes en trámite" (rendered by script, empty in the HTML); `WSAgora.xml` (6.4 MB, members and groups only); bulletins RSS (PDFs) | | allows (blocks ClaudeBot, not us; we never use that agent) | 200 | no: no bill list in the HTML |
| 15 | Navarra, Parlamento de Navarra | 0.68 | none reachable | | 403 | **Cloudflare challenge** ("Just a moment...") | no: bot check |
| 16 | Cantabria, Parlamento de Cantabria | 0.59 | `/actividad/dossieres-legislativos` (one numbered dossier per bill, dated) | HTML (Drupal) | allows | 200; 20 dossiers on page 1 | **yes** (`cb`) |
| 17 | La Rioja, Parlamento de La Rioja | 0.32 | `/actividad-parlamentaria/proyectos-de-ley` (government bills, status and entry date) | HTML (Plone) | allows | 200; 20 bills (2 in passage); the proposiciones page is empty and `/iniciativas/ppl` is 404 | **yes** (`ri`), government bills only |

**All seventeen** get their laws and decree-laws from the BOE layer.
**Five** add bills in passage (four classified in Spanish, the Corts
Valencianes in Catalan/Valencian with `config/taxonomy-ca.yaml`). Votes: Andalucía offers a "Sentido del voto" RSS, which
answered with an HTML page, not a feed; no regional parliament reached gives
per-member roll calls in a machine-readable form. Members: Asturias'
`WSAgora.xml` and Canarias' open-data portal list deputies (not collected:
no vote to join them to).

### Canarias' open data (not read)

`datos.parcan.es` is a CKAN portal (4,621 datasets; `api/3/action/package_list`
answers, keyless): initiatives by type, year and legislature, plenary
sessions, deputies. **Every resource URL points at `www.parcan.es/api/...`,
which that host's robots.txt disallows.** The list page `/leyes/` gives what
the edition needs, so the API is not read; the portal's own contact is
opendata@parcan.es (Waiting on Chris).

### Co-official languages

- **Classified with the Spanish list:** every BOE item (Spanish for all
  seventeen) and the Andalucía, Canarias, La Rioja and Cantabria lists.
- **Classified with the Catalan/Valencian list (12 October 2026):** the
  Corts Valencianes' titles are in Valencian only on its site (`lang = 'ca'`).
  Until 12 October they were stored with `areas` NULL and counted as a gap,
  because the Spanish list is blind to Valencian ("Proposició de llei",
  "avortament", "família"). Since then `tools/es_regions.py` classifies every
  `ca` title with `config/taxonomy-ca.yaml` (master
  `docs/keyword-taxonomy-ca.md`, an unmeasured draft Chris approved), and
  Spanish titles keep `taxonomy-es`; a title in a language with no list
  (Basque, Galician) is still stored unclassified and counted. The edition
  shows a Valencian bill on our ground like any other, and its coverage says
  how many Valencian bills were classified with the draft list. Measured on
  the 10 Valencian bills stored by the build (land, forests, civil protection
  twice, budgets, fiscal measures, tourism taxes twice, a Down syndrome care
  unit, cultural heritage): all 10 classified, 0 on our ground.
- **Not reached at all:** Cataluña (Catalan; site reachable, list in Catalan
  and the open-data page failing), the País Vasco and the Illes Balears (no
  answer), Galicia (Akamai). Their laws arrive in Spanish through the BOE.
- The Catalan/Valencian term list (proposal below, applied 12 October 2026)
  will serve Cataluña's and the Illes Balears' lists too once they can be
  read.

## Relevance to CitizenGO

What the measured data already shows on our ground or close to it:

- **Cataluña, Ley 13/2025** "de los derechos de las personas LGBTI y la
  erradicación de la LGBTI-fobia" (BOE 11 April 2026): the one 2026 act the
  Spanish list puts on our ground (sex-based rights, tier 1).
- **Madrid, Ley 5/2026** "de reconocimiento del concebido en la aplicación de
  las medidas de apoyo a la familia" (BOE 29 August 2026): plainly life and
  family, and the Spanish list missed it (no term matched). Since taxonomy-es
  v0.3 (12 October 2026) it matches "del concebido", "apoyo a la familia" and
  "medidas de apoyo a la familia": areas 1 and 9, tier 1.
- **Cantabria**: a government bill creating a Consejo LGTBI (dossier 176/XI,
  11 June 2026, on our ground) and one on teachers' authority and school
  life (175/XI, education).
- **Andalucía**: a members' bill on bullying and cyberbullying in schools
  (13-26/PPL-000002, 8 September 2026, matched "ciberacoso").
- **La Rioja**: the 2024 palliative-care law (11L/PL-0008, closed; matched
  "paliativ*").
- Illes Balears repealed its democratic-memory law (Ley 1/2026); Galicia
  passed a law on minors' health and addictive behaviour (Ley 6/2025). Neither
  is on our ground under the current list; noted for Chris's judgement.

Ranking for further work, combining population, activity on our areas and
source quality: Madrid (largest blocked, most active on life and family),
Andalucía (built), Cataluña (needs a Catalan list and a working source),
Comunitat Valenciana (built, needs a Valencian list), Castilla y León
(re-check when bills open), Galicia, the País Vasco, Murcia (robots.txt).

## The Spanish taxonomy on the 153 acts

When the layer was built, `config/taxonomy-es.yaml` put **1 of the 153
acts** on our ground. Reading all 128 laws and decree-laws by hand, one more
clearly belongs (Madrid's Ley 5/2026, above). The additions below were
proposed for Chris's approval and **APPLIED on 12 October 2026** (Chris: "Add
the Spain keyword terms"), in `docs/keyword-taxonomy-es.md` v0.3, generated,
not hand-edited. As applied: `"del concebido"` (area 1, tier 1, shared; bare
`concebido` left out because it also means "designed", and `"concebido* no
nacido*"` and `nasciturus` were already there), `"apoyo a la familia"` and
`"medidas de apoyo a la familia"` (area 9, tier 2, shared). Measured: on the
local store's 54,529 national rows of the Spanish-language countries they add
no area to any row (2 Peruvian court items match "del concebido", both
already area 1); of the layer's 209 rows only Madrid's Ley 5/2026 changes, now
2 of the 153 acts on our ground. "autoridad del profesorado" was NOT added.
The proposal as it stood:

| Term | Area | Why |
|---|---|---|
| `concebido`, `concebido no nacido`, `nasciturus` (shared) | life | Madrid Ley 5/2026 |
| `apoyo a la familia`, `medidas de apoyo a la familia` (shared) | family | same law; regional family-support laws |
| `consejo LGTBI` (already matched through `LGTBI*`) | sex-based rights | no change needed |
| `autoridad del profesorado` | education | Cantabria 175/XI, Canarias 11L/PPL-0007 (if Chris wants teachers' authority laws) |

A Catalan/Valencian list (for the Corts Valencianes now and Cataluña later),
**applied on 12 October 2026** as `docs/keyword-taxonomy-ca.md` (v0.1,
unmeasured draft, Chris approved; generated to `config/taxonomy-ca.yaml`),
the proposal below plus the natural Catalan forms of the Spanish list's core
terms per area. The proposal: `avortament`, `interrupció voluntària de l'embaràs`,
`eutanàsia`, `mort digna`, `gestació subrogada`, `LGTBI*` (shared),
`identitat de gènere`, `família`, `escola concertada`, `llibertat religiosa`,
`prostitució`, `discurs d'odi`.

## What was built

- `src/es_regions_store.py`: tables `esr_laws` (key: BOE identifier),
  `esr_bills` (key: `<region>:<the parliament's expediente>`), `esr_reads`
  (one row per source: last read, status, items), declared in `db.TABLES` and
  created by `db.init_db`.
- `tools/es_regions.py`: the collector. BOE summaries from the day after the
  newest issue read (less two days, for late corrections; a first run reads
  two weeks, at most 62 days), and the five lists (`an`, `cn`, `ri`, `cb`,
  `vc`). Classification with `config/taxonomy-es.yaml` (country `es`) on the
  title plus the BOE's subject heading, and (since 12 October 2026) with
  `config/taxonomy-ca.yaml` for Catalan/Valencian titles. A list's **first read is a seed**:
  bills already in passage count as new only by their own presentation date,
  so the first edition is not a flood. A refused page, a list that parses to
  nothing (a dissolution, or the page changing shape) or a failed BOE day is
  a gaps row and a `[gap]` line; exit 3 then, and the weekly carries on.
  `--reclassify` re-derives every row offline (and so classifies the
  Valencian rows stored before taxonomy-ca; it prints how many, and how many
  are on our ground). Measured: a first run (14 days
  of BOE, five lists) in under a minute; a weekly run about 4 seconds plus
  the BOE days since the last read.
- **The Spanish edition's "Regional parliaments" section**
  (`src/editions/es.py`, through the framework's `post_render` hook): regional
  laws and decree-laws in the BOE in the edition's window on our ground, then
  new regional bills on our ground (Spanish titles only), each with its
  community and parliament, through the same noise filters
  (`config/edition-noise-es.yaml`, `config/edition-mute-es.yaml`) and stub
  ordering; then the section's coverage lines (BOE read to, lists read or
  failed, co-official-language bills counted, the regions not read and why).
  It sits after the Congreso's sections, before the Watchlist, or at the end
  of a quiet week's form, so the Congreso's counts, lead and quiet-week test
  are unchanged. The DM gets one line ("Regional parliaments: N regional
  law(s) in the BOE and M new regional bill(s) on our ground"). Watchlist
  entries can name a BOE identifier or a regional bill key in
  `config/watchlist-es.yaml` (any mapping section). The session judge and the
  review window do not read the regional items yet.
- `jobs/es-weekly.sh`: a step after the Congreso collector (budget 300 s from
  `tools/collector_budget.sh`; the Congreso collector now keeps that back);
  `ES_RECLASSIFY=true` reclassifies the regional rows too. **No new job, no
  Mini install.**
- `tools/coverage.py`: `esr_reads` and `esr_bills` (7 days, 4 grace),
  `esr_laws` (31, 31); all three excused while empty until 18 October (the
  first Saturday run).
- Tests: `tests/test_es_regions.py` (22 tests) on trimmed real replies in
  `tests/fixtures/es_regions/`.

Shared files touched: `src/db.py` (three table names and one
`ensure_schema` call), `tools/coverage.py` (entries above),
`src/editions/es.py`, `jobs/es-weekly.sh`, `docs/country-parity-handover.md`,
`docs/mac-mini.md`.

## Phase list

1. **Built**: BOE laws for all seventeen; bills in passage for Andalucía,
   Canarias, La Rioja (government bills), Cantabria; Valencian bills
   (classified with taxonomy-ca since 12 October 2026).
2. Constitutional Court items in BOE section I that name a regional law
   (recursos and cuestiones de inconstitucionalidad): same API, a filter on
   the TRIBUNAL CONSTITUCIONAL department.
3. **Done 12 October 2026**: the Catalan/Valencian term list, and `vc`
   classified with it (the stored rows by one `--reclassify` run, which
   `ES_RECLASSIFY=true` on the weekly does). Next: Cataluña's list once its
   open-data page answers, and a native reader's pass over taxonomy-ca.
4. Castilla y León's open-comment list when bills open; Asturias' bulletins
   (PDF) if a list never appears.
5. Re-probe from GitHub's runners the hosts that did not answer the laptop
   (País Vasco, Illes Balears, Aragón's tramitación base): a `probe-hosts`
   run, not a collector.

## Waiting on Chris

- Approved and applied on 12 October 2026: the Spanish terms (without
  `autoridad del profesorado`) and the Catalan/Valencian list. Open: a native
  Catalan/Valencian reader for `docs/keyword-taxonomy-ca.md`.
- **Canarias' open data:** its catalogue links files under `/api/`, which
  robots.txt disallows. Ask opendata@parcan.es whether the API may be read;
  until then the `/leyes/` list is enough.
- **Madrid, Navarra, Galicia:** bot checks (Sucuri, Cloudflare, Akamai). Never
  bypassed. Ask each parliament for an open feed or an allow-listed agent if
  bills in passage there matter before their laws reach the BOE.
- **Murcia, Extremadura:** robots.txt disallows everything; a request to each
  parliament would be needed.
- **País Vasco, Illes Balears, Aragón's base:** no answer from the laptop; a
  GitHub probe run would tell whether they refuse UK connections.

## Forward agenda (regional_agenda, 16 October 2026)

What each parliament has booked, from today as far ahead as it publishes:
`src/regional_agendas/es.py` (interface `src/regional_agenda.py`, collector
`tools/regional_agenda.py es`, tests `tests/test_regional_agenda_es.py` on
trimmed live captures in `tests/fixtures/regional_agenda/es/`). Probed and
run live from the laptop on 16 October 2026 with the honest user agent,
every request through the robots guard, into a scratch database. Region
codes are the past layer's (`an`, `ct`, ... from `src/es_regions_store.py`).
Not wired into any job yet.

**Live run (56 days asked, to 11 December): 7 of 17 read, 183 items (85
"to be announced" placeholders for booked sittings), 1 on our ground, no
gaps, 56 requests, 83 seconds** (Canarias' 3 s crawl delay is a third of it).

| Code | Parliament | Route | Format | Reaches | robots.txt | Live run |
|---|---|---|---|---|---|---|
| an | Andalucía | `agendasemanal.do` (index of weekly agendas, then `?id=N&numsemana=N`), `calendariodesesiones.do?fec=<mes> <año>` | HTML, ISO-8859-1 | agenda: the current week (next week's appears late in the week); calendar: the Mesa's programme to December | allows all | 29 items (23 placeholders), named business to 17 Nov (calendar subjects), dates to 10 Dec |
| ct | Cataluña | `/web/actualitat/agenda/index.html?p_categoria=SESSIO&p_mode=M&p_data=01MMYYYY`, each sitting's `/web/actualitat/ordre-dia/index.html?p_od0=N`, `/web/composicio/ple-parlament/calendari-anual/` ("previst" days) | HTML, ISO-8859-1, Catalan only | agenda about 10 days; planned plenaries to 17 December | allows `/web`; disallows `/apl`, `/ext` (never read) | 29 items (9), named to 26 Oct, dates to 3 Dec; classified with `taxonomy-ca.yaml` |
| vc | Comunitat Valenciana | `/es/actividad/actualidad/agenda?field_taxon_type_target_id=6` (the parliamentary calendar, Spanish version), each sitting's page (convocation with its numbered order of the day) | HTML (Drupal) | convened sittings, about a week | allows | 7 items, to 21 Oct |
| cl | Castilla y León | `/Agenda/Semana?Fecha=DD-MM-YYYY`, `/Agenda/Evento?NumeroSerieId=N` ("Orden del día"), `/Actividad/PlenosPrevistos` (red cells) | HTML | agenda: the current week; plenary calendar to December | disallows `/*agenda.do*`, `/*agenda.html*`, `/*.rss$`; these paths allowed | 13 items (8), named to 16 Oct, plenaries to 2 Dec |
| cn | Canarias | `/actividad/calendario/` (plenaries and committees for the period to 31 Dec), `/reuniones/futuras.py`, `/reuniones/asuntos.py?ID_SESION=N` | HTML | calendar to 31 December; orders of the day about two weeks | Crawl-delay 3 (honoured); disallows `/api/` | 51 items (36), named to 30 Oct, dates to 10 Dec |
| ar | Aragón | `/Semana-actual.2237.0.html`, `/Proxima-semana.2335.0.html`, `/Acto-programado.2319.0.html?...uid=N`, `/fileadmin/_DMZMedia/comunicacion/web/varios/calendario.csv` (the CSV the plenary-calendar page loads) | HTML, CSV | agenda: this and next week; plenary CSV to 18 December | disallows `/*?id=*` (so never `index.php?id=`; the realurl paths answer the same pages) | 18 items (8), named to 19 Oct, plenaries to 4 Dec |
| cb | Cantabria | `/agenda-semana?date=YYYY-MM-DD` (orders of the day inline) | HTML (Drupal) | the sittings convened, about a week | allows | 36 items (1), to 20 Oct |
| md | Madrid | none | | | Sucuri firewall on every path, robots.txt included | blocked |
| ga | Galicia | none | | | Akamai 403 on `.gal` and `.es`, robots.txt included | blocked |
| nc | Navarra | none | | | Cloudflare "Just a moment..." on parlamentodenavarra.es; parlamentonavarra.es no answer | blocked |
| as | Asturias | none | | | **new since 12 October:** every path, robots.txt included, answers a "Voight-Kampff Browser Test" bot challenge (403) | blocked |
| cm | Castilla-La Mancha | the agenda tab is an iframe of `/web2/paginas/calendario.php` | | | `Disallow: /web2/paginas/` | blocked |
| mc | Murcia | | | | `Disallow: /` | blocked |
| ex | Extremadura | | | | `Disallow: /` (Crawl-delay 60) | blocked |
| pv | País Vasco | | | | no answer (connect timeout, 12 and 16 October) | no route |
| ib | Illes Balears | | | | no answer (connect timeout, 12 and 16 October) | no route |
| ri | La Rioja | plenary calendar `.../calendario-de-sesiones-plenarias-...-2026` is an encrypted PDF; the sessions iCal export (`ics_view`) answers 500; session pages list attendance only; `/agenda/RSS` mixes past sessions and institutional events | | | allows | no route |

How the readers work. One item per point of an order of the day, with the
parliament's expediente as the reference (`13-26/PNLC-000012`,
`357-01509/15`, `PNL/000047`, `11L/AGSC-0001`, `11L/4300-0453`). A sitting
in a calendar with no order of the day yet is one placeholder (stored as
"to be announced"); when its order of the day appears the placeholder goes
(same `meeting_id`, `<date>:<body slug>`). Plenaries are stored as body
"Pleno" everywhere (Catalonia's "Ple del Parlament" too); committees keep
their published name. The Mesa, the Junta de Portavoces, press
conferences, intergroups and institutional events are left out. Point texts
drop the proponents' names and the bulletin reference into `detail` (the
business reads "Proposición No de Ley, PNL/000030, instando a la Junta
...") so a deputy's name list never becomes the headline. Units: each
reader declares `window(today, end)` up to the last page it read in full
(a later week or month that fails is a gap line and shortens the window,
it does not fail the region).

What was tried for the regions not read:

- **Madrid:** `www.asambleamadrid.es` (Sucuri 403 on robots.txt and every
  page); the regional open-data portal datos.comunidad.madrid (its CKAN API
  is disallowed by robots.txt: one search request was sent from a probe
  before that check came back; nothing further). No other official copy of
  the agenda found.
- **Galicia:** `www.parlamentodegalicia.gal` and `.es`, `/Actividade/Axenda`:
  Akamai 403.
- **Navarra:** `parlamentodenavarra.es` (Cloudflare challenge),
  `parlamentonavarra.es` and `parlamento.navarra.es` (no answer).
- **Asturias:** `www.jgpa.es` now serves a JavaScript bot test on every
  path. The 12 October build read its robots.txt; a re-probe from GitHub's
  runners would tell whether the wall is general.
- **Castilla-La Mancha:** `/index.php/actividad` loads the agenda (and the
  Mesa, plenary and committee tabs) from `/web2/paginas/calendario.php`,
  which robots.txt disallows. The BOCCLM bulletins publish convocations
  only after the fact.
- **Murcia, Extremadura:** robots.txt disallows everything.
- **País Vasco, Illes Balears:** no TCP answer from the laptop on either day,
  `www.` and bare hosts. Same re-probe from GitHub as for the past layer
  (phase list, item 5).
- **La Rioja:** routes above; worth a re-check of `ics_view` (a 500 may be
  transient) and of whether future sittings ever appear in the sessions
  list before the day.

Classification notes from the run. Only 1 of 98 named items is on our
ground (Cantabria's plenary of 19 October: a Vox PNL on repatriating people
who entered illegally, migration, area 11). The Corts Valencianes' family
committee of 21 October takes "a PNL on the role of the family" (Vox): the
Spanish list excludes bare "familia" on purpose, so it is not matched;
Andalucía's family-policy hearings and a question on an LGTBI congress sat
on 13 October, before the window. Catalan items are classified with the
draft Catalan list; the core's item types do not know Catalan words yet
("Compareixença", "Proposició de llei"), so they come out as "committee
business".
