# Mexico: the 32 state congresses

Probed and built on 12 October 2026, from the laptop in London, at low
volume (curl and `src/http.py`, the honest CitizenGO User-Agent with contact,
at least 1.5 s between requests to a host, robots.txt read first). No
CAPTCHA, Cloudflare, Sucuri, Wordfence or Imperva check was solved or
bypassed, no browser User-Agent was used, and no credential found in any
site's code was used. Live runs went into a scratch store, never
`data/parl-monitor.db`. "Measured" means fetched and parsed today;
"reported" means press or search results, not verified on the official site.

Built: `src/mxs_store.py` (tables `mxs_items`, `mxs_reads`, declared in
`db.TABLES`), `tools/mxs_collect.py` (the runner), one reader per state in
`src/ingest/mxs_<state>.py` with shared helpers in `src/ingest/mxs_common.py`,
`src/mxs_edition.py` (a **State congresses** section in the Mexican
edition, through `Country.post_render`, and a DM line through
`Country.notice`), `config/watchlist-mx-states.yaml` (by item key), a step
in `jobs/mx-collect.sh` (the Mexican edition's GitHub job), entries in
`tools/coverage.py`, and `tests/test_mxs.py` on trimmed real pages
(`tests/fixtures/mxs/`).

## Why the states matter

Most of CitizenGO's ground in Mexico moves in the states, not in Congress:
abortion is state criminal law, decriminalised state by state since Mexico
City in 2007 and pushed along by the Supreme Court (2021, Coahuila; 2023,
the federal code); gender-identity recognition, conversion-practice (ECOSIG)
bans, civil unions and equal marriage, advance directives (voluntad
anticipada, the door to euthanasia bills) are state laws. Items found on
our ground in the probe, 2024 to 2026 (measured unless marked):

| State | Items on our ground found in the probe |
|---|---|
| Ciudad de México | abortion decriminalisation and ILE access (Sep, Oct 2024); sex education and pupils' gender identity (Mar, May 2025); hormone treatment in prison (Apr 2025); diversidad sexual budget annex (8 Oct 2026) |
| Jalisco | ILE chapter (11 Sep 2025); repeal of Código Penal arts. 228 ter, 229 (25 Sep 2025); a Ley de Eutanasia y de Muerte Asistida (4 Jun 2026) |
| Chiapas | Ley de ILE de Niñas y Adolescentes (28 Oct 2025); conversion-therapy offence (28 May 2025); self-perceived gender identity (9 Jun 2026); voluntad anticipada (20 Aug 2025) |
| Chihuahua | ECOSIG penal chapter (5 Nov 2024); "Ley para Prevenir el Aborto" and aborto articles (PAN, Apr 2025); voluntad anticipada (Oct 2025) |
| Querétaro | ILE in Código Penal and Ley de Salud; LGBTTTIQ+ law; self-perceived gender identity and the Governor's veto of it |
| Yucatán | two abortion decriminalisation bills (5 Feb 2025); gender identity (Feb 2026); diversidad sexual law (Oct 2025) |
| Sinaloa | Ley de los Derechos de las Personas Trans (6 Mar 2026); voluntad anticipada (Jun 2025); LGBTTTI law approved (May 2025) |
| Oaxaca | hate crimes on gender identity (Aug 2026); ILE punto de acuerdo (Oct 2025); libertad religiosa (Nov 2025) |
| Baja California | voluntad anticipada with Código Penal art. 154 (May 2025); LGBTTTQ+ recognition law (Aug 2026) |
| Tamaulipas | LGBTTTI+ recognition law (Feb 2025, reformed Mar 2026); voluntad anticipada (Feb 2025, Apr 2026) |
| Nayarit | Código Penal on interrupción del embarazo (Jan 2025) |
| Estado de México | voluntad anticipada (Oct 2025); Día de la Libertad Religiosa (Jul 2026) |
| Guanajuato (reported) | abortion decriminalisation rejected again (Jun 2025); equal marriage and an ECOSIG ban approved (4 Dec 2025); bishops' warning on removing "derecho a la vida" from the constitution (Mar 2026) |
| Nuevo León (reported) | Código Penal: abortion not punishable (1 Oct 2025) |
| Puebla (reported) | surrogacy bill (Jul 2025); Supreme Court order on trans minors (Jun 2026) |
| San Luis Potosí, Michoacán (reported) | abortion decriminalised to 12 weeks (Nov 2024; Michoacán's date conflicts) |
| Durango (reported) | abortion decriminalisation pending (Mar 2025); equal marriage sent back to committee |

## The finding that shapes everything: 32 sites, no shared feed

There is no Open States for Mexico. Each congress has its own site, built
by its own contractor: JSON APIs behind JavaScript apps (Sinaloa,
Aguascalientes, Nayarit, Sonora), one big HTML table (Baja California,
Yucatán, Tabasco, Chiapas, Oaxaca, Estado de México, Querétaro), paged
listings (Chihuahua, Quintana Roo, Ciudad de México), JSF or ASP.NET
postbacks (Coahuila, Colima), or PDFs only (Durango, Morelos, Guerrero's
tracker). So the layer is one small reader per state on a shared runner,
store and edition section, as for the Canadian provinces.

**The shared national sources do not replace them** (measured):

- **SIL (sil.gobernacion.gob.mx, Segob).** robots.txt disallows only three
  legislator-profile scripts. The new portal (nsil.gobernacion.gob.mx)
  refuses connections from the UK; the legacy search works (current to 7
  October 2026) but needs a session and SID, and holds only what state
  congresses send to the federal Congress (iniciativas, notifications) and
  federal constitutional declaratorias. No state bills, no per-state count
  of constitutional ratifications. Not read.
- **Orden Jurídico Nacional (ordenjuridico.gob.mx).** Per-state law lists
  with publication and last-reform dates (`despliegaedo2.php?edo=<n>`), but
  stale: the newest last-reform dates were October 2024 (Quintana Roo,
  Nayarit) and January 2025 (Aguascalientes). Not usable weekly.
- **SCJN legislation (legislacion.scjn.gob.mx).** The 403 at the root is
  an IIS directory refusal, not a bot block. The "50 most recent reforms"
  list (`buscador/paginas/wfReformasResultados.aspx`) covers federal and
  state reforms published in the periódicos oficiales, current to 8-9
  October 2026, with decree numbers and extracts; ten to a page, more only
  by ASP.NET postback. **The best cross-state source for ENACTED reforms**;
  not built (phase 2 below). bj.scjn.gob.mx (the Buscador Jurídico) loops
  through an Imperva JavaScript check: blocked, not bypassed, and no
  documented public API was found.
- **State periódicos oficiales**: 32 separate gazettes; reached through the
  SCJN list above rather than one by one.
- **datos.gob.mx**: Akamai refuses our User-Agent (403, even robots.txt).
  No dataset of state legislative activity was found by search.
- **Civil society**: GIRE's state abortion tracker sits behind a Cloudflare
  challenge (not bypassed); no live cross-state bill tracker (IMCO,
  Congreso Abierto, Intersecta) was found. INEGI's Censo Nacional de
  Poderes Legislativos Estatales is annual.

**Reachability.** Five hosts do not answer UK addresses at all (Veracruz,
Nuevo León, Guanajuato, Zacatecas, and Michoacán's https site), like the
federal Chamber's. Durango's Wordfence answers "access from your area has
been limited". The Mexican edition already runs on GitHub's (US) runners for
that reason, so the state step runs there too, and asks each unreachable
host's home page once a run (one try, 20 s, robots.txt honoured): the day a
runner reaches one, the edition's coverage line says so and a reader can be
written. **Whether GitHub's runners reach these five is not yet known**
(the store-writing workflow was not dispatched from here).

## State by state

Ranked by CitizenGO relevance (population and activity on our ground) and
source quality. Status: **read** (a reader is built and runs in the job),
**not built** (feasible, deferred, with why), **unreachable** (from the UK;
asked from the runner each run), **blocked** (robots.txt or a bot check).

| # | State | Pop. (m) | Source read (or found) | Format | Fields | Votes per member | robots.txt | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Estado de México | 17.0 | legislacion.congresoedomex.gob.mx/asuntosparlamentarios/iniciativas, the page's own XHR reply | one HTML list, 4.7 MB, 1,363 items | No., author and group, title, date, committees, status | HTML per decree (votaciondecretos), not read | none (404); legislacion host allows all | **read** |
| 2 | Ciudad de México | 9.2 | ciudadana.congresocdmx.gob.mx/Iniciativa/iniciativas?page=N (the official list stopped 7 Nov 2025) | paged cards, 20 a page; JSON to our Accept header | id, date, title, author, group, committee | none current (one XLSX for 2018-20) | portal: none (404) | **read** |
| 3 | Jalisco | 8.3 | infolej.congresojal.gob.mx: a two-step session search (result_busqueda.php, paginados.php) | HTML fragments | INFOLEJ number, title, date; detail with every step | "Cédula de votación" PDFs (reported) | www: Crawl-delay 10; infolej: none | not built: about 77 s a results page, 17 pages a fortnight |
| 4 | Veracruz | 8.1 | www.legisver.gob.mx | unknown | | | could not be read | unreachable |
| 5 | Puebla | 6.6 | congresopuebla.gob.mx | Cloudflare managed challenge on every HTML page | | | none | blocked |
| 6 | Guanajuato | 6.2 | www.congresogto.gob.mx | unknown | | | could not be read | unreachable |
| 7 | Nuevo León | 5.8 | www.hcnl.gob.mx (lists per filer, from search) | HTML lists, gaceta PDFs (reported) | Exp., subject, committee, date, status (reported) | totals in actas (reported) | could not be read | unreachable |
| 8 | Chiapas | 5.5 | web.congresochiapas.gob.mx/trabajo-legislativo/trabajo-legislativo | one HTML page, 1.8 MB, a table per legislature | file number, title (author inside), date, stage documents, "Aprobado" | per-sitting PDFs, not read | Joomla system paths only | **read** |
| 9 | Michoacán | 4.7 | congresomich.gob.mx (https times out; the http copy stopped June 2025) | WordPress lists | date, summary, gaceta PDF | | /cem/wp-admin/ only | unreachable |
| 10 | Oaxaca | 4.1 | congresooaxaca.gob.mx/iniciativas-acuerdos/segundo.html (a table per year) | HTML table, 1.4 MB | No., date, type, proponent, party, text, committee, status | none found | none (404) | **read** |
| 11 | Chihuahua | 3.7 | www.congresochihuahua.gob.mx/biblioteca/procesoLegislativo.php?pag=N | paged HTML, 10 a page, newest first | Asunto, text, promoventes (party), date, committee, status | none found | names AI and SEO bots only | **read** |
| 12 | Guerrero | 3.5 | sialgro.dcrsoft.com.mx gacetas; a 420-page tracker PDF | HTML per sitting (third-party host) | type, description with author | none found | none / empty | not built |
| 13 | Tamaulipas | 3.5 | congresotamaulipas.gob.mx Iniciativas.asp, then ListadoIniciativas.asp per period | HTML table per period | folio, date, title, promoventes (party), committees, status | per-member PDFs per session, not read | Cloudflare preamble, no rules, no signal set | **read** |
| 14 | Baja California | 3.8 | www.congresobc.gob.mx/TrabajoLegislativo/Iniciativas | one HTML table, 3.9 MB | session and doc number, group, type, presenter, outcome, date, text | **HTML per member** (Edocvotacion.aspx, ASP.NET session), not read | none (404) | **read** |
| 15 | Coahuila | 3.1 | /estadistica/iniciativa (PrimeFaces JSF) | 5 rows a page, stateful postbacks | date, origin, ponente (party), subject | per-member PDFs by date (votaciones/dd_mm_yyyy.pdf) | none (404) | not built |
| 16 | Sonora | 2.9 | votacion-electronica.api.congresoson.gob.mx/publico/iniciativa | JSON | folio inside the text; no committee or status; only 413 items | no public endpoint | APIs allow all | not built: thin, nothing on our ground found |
| 17 | Hidalgo | 3.1 | congresohidalgo.gob.mx/acervo/public/gaceta/<n> | HTML per sitting | label, date, title; author and committee only in PDFs | attendance only | Yoast defaults | not built |
| 18 | San Luis Potosí | 2.8 | congresosanluis.gob.mx | Sucuri JavaScript challenge | | | Drupal, Crawl-delay 10 | blocked |
| 19 | Sinaloa | 3.0 | gaceta.congresosinaloa.gob.mx/api/obtenerIniciativas (POST, the page's own JSON) | JSON, one reply, 3.2 MB | id, date, author, committee, both resolutions, approval and publication dates, totals | totals only | gaceta host: none | **read** |
| 20 | Querétaro | 2.4 | legislaturaqueretaro.gob.mx/iniciativas/ over plain HTTP only (the https port refuses connections) | one HTML table | No., title, presenter, PDF; **no date, committee or status** | none found | /wp/wp-admin/ only | not built: the pipeline reads nothing in the clear (tests/test_db_state.py) |
| 21 | Yucatán | 2.3 | congresoyucatan.gob.mx/gaceta/iniciativas | one HTML table since 2015, 1.5 MB | date, presenter (group), turn date, committee; no number | none (acta PDFs) | allows all | **read** |
| 22 | Morelos | 2.0 | congresomorelos.gob.mx documentos-legislativos | Gaceta DOCX/PDF, about four months late | | | /wp-admin/ only | not built |
| 23 | Quintana Roo | 1.9 | congresoqroo.gob.mx/iniciativas/?legislatura=XVIII&page=N | paged HTML, newest first | sitting date, status, title, committee, promoters | per-item PDFs, not read | none (404) | **read** |
| 24 | Durango | 1.8 | congresodurango.gob.mx | Wordfence geo block (503); PDFs only (reported) | | | CONTRALORIA paths only | blocked (from the UK) |
| 25 | Tabasco | 2.4 | congresotabasco.gob.mx/iniciativas/ | one WordPress table | number, title, committee, presenter, date | per-member PDFs (monthly VOTACIONES files), not read | /wp-admin/ and a cache path | **read** |
| 26 | Aguascalientes | 1.4 | congresoags.gob.mx/LegislativeAgenda/GetPagedData | JSON, paged | agenda number, text, date, committees, resolution | none found | none (404) | **read** |
| 27 | Zacatecas | 1.6 | www.congresozac.gob.mx | unknown | | | could not be read | unreachable |
| 28 | Tlaxcala | 1.3 | wp-json/wp/v2/pages?slug=trabajo-legislativo65 | one 1.5 MB WordPress page of tabbed tables | Núm., date, asunto, proponente, expediente | session PDFs | REST allowed | not built |
| 29 | Nayarit | 1.2 | utics.congresonayarit.gob.mx/iniciativas/tabla/XXXIV (the app's own JSON) | JSON, one reply | number, text, date, author, committee, status, updated | per-decree PDFs | none (404) | **read** |
| 30 | Campeche | 0.9 | www.congresocam.gob.mx | robots.txt: `User-agent: *` `Disallow: /` | | | everything disallowed | blocked |
| 31 | Colima | 0.7 | /web/www/gaceta/plantilla_datos.php?v=tiniciativas (POST) | HTML fragment | number, text, author (party), committee, status; no date | none found | none (404) | not built |
| 32 | Baja California Sur | 0.8 | orden del día RSS only | RSS | | none found | none (404) | not built |

**Read: 13 states** (Estado de México, Ciudad de México, Chiapas, Oaxaca,
Chihuahua, Tamaulipas, Baja California, Sinaloa, Yucatán, Quintana Roo,
Tabasco, Aguascalientes, Nayarit), about 47% of Mexico's population (59 of 126 million). **Unreachable from the UK: 5** (Veracruz, Guanajuato, Nuevo
León, Michoacán, Zacatecas). **Blocked: 4** (Puebla and San Luis Potosí by
bot checks, Campeche by robots.txt, Durango by a geo block). **Not built:
10** (Jalisco, Querétaro, Guerrero, Coahuila, Sonora, Hidalgo, Morelos,
Tlaxcala, Colima, Baja California Sur).

Notes on particular readers:

- **Sinaloa, Nayarit, Aguascalientes, Estado de México** read the JSON or
  HTML that each site's own page asks for, with no key; Estado de México's
  page asks with `X-Requested-With: XMLHttpRequest` and we send the same.
  Sinaloa's page loads a reCAPTCHA v3 script, but its API answered without
  any token: nothing was solved or bypassed. If any of them ever demands a
  token, the reader records a gap and stops.
- **Ciudad de México**: the portal answers our client's JSON-first Accept
  header with its own JSON view (behind a CakePHP deprecation notice),
  which also names the committee; the reader reads JSON or HTML.
- **Querétaro** answers only over plain HTTP (its https port refuses
  connections, measured 12 October 2026), and the pipeline fetches nothing
  in the clear (Christopher's audit of 29 August 2026, enforced by
  tests/test_db_state.py). A reader was written and dropped; if the
  Legislature turns https on, it is a one-table reader (with no dates: new
  items would be dated the day first listed).
- **Oaxaca**: on 12 October 2026 `tercero.html` still held the LXV's third
  year (2023); rows whose document is on another legislature's host are
  skipped.
- **Statuses** are the source's own words. Where a source prints a status
  without a date (Chiapas, Tamaulipas, Chihuahua, Oaxaca), a change is dated
  the day a run first sees it. Routine handling (a turn to committee, "se
  toma en consideración") is not shown as a stage move.

## Votes per member

No state reader stores member positions yet. Five states publish them:
**Baja California** (HTML per vote, behind an ASP.NET session cookie),
**Estado de México** (HTML per decree), **Tamaulipas** (per-session PDFs,
page 2 per deputy by party), **Coahuila** (per-session PDFs by date) and
**Tabasco** (monthly VOTACIONES PDFs; the ticks may be glyphs). Chiapas,
Quintana Roo, Tlaxcala and Nayarit publish vote PDFs whose per-member
content was not checked. That is phase 2.

## Taxonomy

The readers classify with the existing `config/taxonomy-es.yaml` for
country `mx` (the federal collector's accent fold, `tools/mx_rollcalls.
classify`), on the title plus the committee. The build itself added no
terms (the terms of 12 October 2026 are below). State titles are mostly descriptive Spanish
("en materia de interrupción legal del embarazo", "identidad de género
autopercibida", "Ley de Voluntad Anticipada"), so the federal list catches
them; **voluntad anticipada** is already there (area 2) and catches the
advance-directive bills. Terms worth proposing for state work: **ECOSIG**
and **esfuerzos para corregir la orientación sexual**, **personas trans**,
**infancias trans**, **diversidad sexual y de género**, **Ley Agnes**,
**crímenes de odio**, **violencia vicaria**. **Applied 12 October 2026**
(Chris: "Add the Mexico and Italy keyword terms too", then "violencia
vicaria" after all) in `docs/keyword-taxonomy-es.md` v0.3: ECOSIG, the
"esfuerzos para corregir" forms, "personas trans", "infancias trans" and
"Ley Agnes" were already in the list (tagged mx or shared), so nothing was
duplicated; "diversidad sexual y de género" is already filed at tier 2 by the
shared "diversidad sexual" (all 9 state items carrying it) and was not
promoted; "crímenes de odio" and "crimen de odio" joined area 7 at tier 2
(2 state items gain area 7) and "violencia vicaria" area 9 at tier 2 (11
state items gain area 9, 0 false positives), both shared on measurement.
`tools/mxs_collect.py` reads `config/taxonomy-es.yaml` through
`tools/mx_rollcalls.classify` (the accent fold), so it picks the terms up
with no code change; `--reclassify` re-derives stored rows offline.

## Edition

The Mexican edition (fortnightly, `src/editions/mx.py`) gains a **State
congresses** section before the Watchlist: items on our ground new in the
fortnight, older items with a dated stage, and decrees, each headed with its
state and key, with the source's status in its own words, under the same
noise rules (`config/edition-noise-mx.yaml`). A line under it says which
states were read cleanly, which with gaps, and which not and why. The DM
gains one line when there are state items. A watched item is keyed in
`config/watchlist-mx-states.yaml` ('<state>/<source id>').

## Shared files touched

`src/db.py` (two names in `TABLES`, one `ensure_schema` call),
`src/editions/mx.py` (post_render, notice, coverage line),
`jobs/mx-collect.sh` (one step), `jobs/mx-weekly.sh` (a comment),
`.github/workflows/mx-weekly.yml` (timeout 75 to 95 minutes, summary grep),
`tools/coverage.py` (two feeds, one step heartbeat "MX states"),
`docs/country-parity-handover.md` (the regional row).

## Phase plan

1. **Done (12 October 2026):** 13 readers, the store, the edition section,
   the job step, tests.
2. **Next:** the SCJN "recent reforms" list for enacted state reforms across
   all 32 (postback paging, polite); Baja California's and Estado de
   México's per-member HTML votes; Chihuahua's full export for stage moves;
   Jalisco (INFOLEJ, run on its own clock, perhaps every fourth week).
3. **Then:** the vote PDFs (Tamaulipas, Coahuila, Tabasco), Tlaxcala and
   Colima, Guerrero's gacetas.
4. **If a runner reaches them:** Veracruz, Guanajuato, Nuevo León,
   Michoacán, Zacatecas, Durango (the step asks each run and says so).

## Waiting on Chris

1. **Blocked states.** Puebla (Cloudflare) and San Luis Potosí (Sucuri)
   answer bot checks; Campeche's robots.txt forbids every crawler. The only
   honest routes are to ask each congress to allow our User-Agent, or leave
   them. Durango's block is by region and may lift from a runner.
2. **Whether to run from a Mexican address** (a VPN exit on the Mini) for
   the five unreachable states, if GitHub's runners cannot reach them
   either. Not done: a decision for Christopher.
3. **The proposed state terms** above, especially whether **crímenes de
   odio** and **violencia vicaria** are ours.
4. **Tamaulipas' robots.txt** carries Cloudflare's content-signal preamble
   reserving "ai-input" where a signal says no; no signal is set today.
   Our use is a keyword filter, with the free session judge reading titles
   later; flagging it in case a signal is ever set.
