# Argentina: the 24 provincial legislatures

Built 13 October 2026 (branch `regions-ar`). Every number below was measured
on 13 October 2026 from the laptop, through `src/http.py` (honest
User-Agent, throttled) and `src/robots_guard.py` (robots.txt asked per host
before the first request). Probe pages were kept in the worktree only; the
collector's raw replies go to `data/raw/` as usual.

Argentina has 24 jurisdictions: 23 provinces and the Ciudad Autónoma de
Buenos Aires (CABA). Eight legislatures are bicameral (Buenos Aires,
Catamarca, Corrientes, Entre Ríos, Mendoza, Salta, San Luis, Santa Fe) and
sixteen unicameral. Provinces legislate on much of our ground: how ESI (Ley
26.150) is taught, protocols for the IVE/ILE service (Ley 27.610),
gender-identity procedures, conversion practices, religious education in
public schools (Salta's constitution and Ley 7.546, upheld in part by the
Supreme Court in "Castillo" 2017), and adherence to national laws, which a
province must pass a law to join.

## The finding that shapes everything: SAIJ serves all 24

SAIJ (Sistema Argentino de Información Jurídica, the Ministry of Justice's
legal database, www.saij.gob.ar) indexes every province's laws. Its search
page answers a plain GET with JSON (`/busqueda?...&f=Total|Tipo de
Documento/Legislación/Ley|Jurisdicción/Local&s=fecha-rango|DESC`): the
official title, a sumario, the province, the law's date, the Boletín
Oficial's date and SAIJ's thesaurus descriptors. robots.txt allows
`/busqueda` (it disallows only PDF and download paths).

- The newest 200 rows (four requests of 50) held **118 laws from 17
  provinces**, dated 13 August to 1 October 2026, published in the
  provinces' Boletines Oficiales between 18 August and 9 October.
- Lag: one to three weeks from the Boletín Oficial to SAIJ (Santa Fe's
  Ley 14.488 of 1 October, published 7 October, listed by 13 October).
- Quiet provinces in that window: Córdoba, Neuquén, San Juan, Santa Cruz,
  Santiago del Estero, Formosa and Tierra del Fuego had no law among the
  200. SAIJ's facet counts show all 24 are indexed (Salta 9,384 laws, San
  Juan 7,548, Córdoba 6,647, CABA 6,267 ...).

So the adopted-law layer is SAIJ for everyone, like the BOE for Spain.
Buenos Aires province's own normative system (normas.gba.gob.ar, the
Boletín Oficial's) is read too: plain GET, newest laws first, ten a page,
earlier than SAIJ for the largest province. The provincial Boletines
Oficiales were measured (below) but are not needed while SAIJ answers.

## Bills: the legislatures' own lists

| Jurisdiction | Chamber | Source | Format | robots.txt | Verdict |
|---|---|---|---|---|---|
| Buenos Aires | Diputados | hcdiputados-ba.gov.ar, search by "fecha de estado parlamentario" | read-only form POST, HTML, 200 rows a page | 404 (no rules) | **BUILT** (`ba-dip`): 566 expedientes in 14 days, with type, extracto, authors and bloc, PDF link; the Senate's bills arrive as origin HS |
| Buenos Aires | Senado | legislativa.senado-ba.gov.ar, Leyes y proyectos | ASP.NET form with a reCAPTCHA field | allowed | **BLOCKED** (CAPTCHA, never bypassed); its bills reach Diputados with half sanction |
| CABA | Legislatura | parlamentaria.legislatura.gob.ar, the expediente search's XML web service (`Json.asmx/GetExpedienteAvanzada`) | read-only POST, XML | 404 (no rules) | **BUILT** (`caba`): 1,287 expedientes started in 120 days, with authors, type, current committee and stage, sanction flag |
| Córdoba | Legislatura (unicameral) | gld.legislaturacba.gob.ar, Asuntos Entrados per session; Leyes, Resoluciones y Declaraciones | GET, HTML (2 MB a session) | an HTML page (no rules) | **BUILT** (`cba`): 195 asuntos in the session of 7 October, with number, extracto, author and committees |
| Santa Fe | Diputados | siel.diputadossantafe.gov.ar (SIEL): the expediente list (GET, 20 a page) and the search by state (read-only POST) | HTML | names AI agents (GPTBot, ClaudeBot, Claude-User ...), no `*` group | **BUILT** 13 October (`sf-dip`, Chris: "Build it"): number, type, author and bloc, entry date, state; media sanción and sanción lists. Stops if any rule ever covers our user agent (below) |
| Santa Fe | Senado | senadosantafe.gob.ar | | timed out (twice) | unreachable from the laptop |
| Mendoza | Senado | senadomendoza.gob.ar | | allowed | **403** to our requests |
| Mendoza | Diputados | hcdmza.gob.ar/site/ | HTML; projects listed in the session diaries (PDF) | Crawl-delay 60 | slow and timed out once; not built (a minute a request) |
| Tucumán | Legislatura | legislaturadetucuman.gob.ar (React app); app2.legislaturadetucuman.gob.ar/consultaexpedientes | HTML | | the expediente app timed out, then answered later the same day: **next step** |
| Entre Ríos | Senado | senadoer.gob.ar/buscador-proyectos (WordPress) | GET, HTML, ten a page | allowed (only /wp-admin/) | **BUILT** (`er-sen`): number, type, author, committee, media sanción and sanción |
| Entre Ríos | Diputados | hcder.gov.ar | | timed out (twice) | unreachable from the laptop |
| Salta | Senado | senadosalta.gob.ar, WordPress REST (`/wp-json/wp/v2/posts` by project category) | JSON | allowed (Yoast, `Disallow:` empty) | **BUILT** 13 October (`sal-sen`): expediente, entry date, subject, authors, kind, en trámite or approved. The `www.` host serves a self-signed certificate: not used |
| Salta | Diputados | www.diputadosalta.gob.ar `/web/proyectos_aprobados_por_periodo`; `/web/asuntos_entrados` (one PDF per sitting) | HTML; PDF | no rules | **BUILT** 13 October (`sal-dip`): this year's approved laws, resolutions, declarations; and (`sal-dip-ae`, same day) the intake, read from the Asuntos Entrados PDFs (newest 25 August). Its pending lists answer "0 expedientes". The bare `diputadosalta.gob.ar` fails TLS (wildcard certificate): not used |
| Río Negro | Legislatura | web.legisrn.gov.ar/legislativa/proyectos | GET, HTML, 100 a page | allowed | **BUILT** (`rn`): 1,256 projects in 2026, with type, extracto, authors (no date in the list: new by first sight) |
| Chubut | Legislatura | larus.legislaturadelchubut.gob.ar/api/public/documentos | GET, JSON | allowed | **BUILT** (`chu`): identifier, extracto, type, authors, current stage. The reply also carries staff login e-mails: never read or stored |
| Jujuy | Legislatura | legislaturajujuy.gov.ar/rest/index.php/labor/legislativa/proyectos/lista | GET, JSON, 20 newest (filters are request headers) | allowed | **BUILT** (`juj`): number, text, date; 655 projects in 2026 |
| Corrientes | Diputados | hcdcorrientes.gov.ar, `expedientes` post type (WordPress) | GET, HTML, five a page; also an RSS feed | allowed | **BUILT** (`ctes-dip`): number, type, author, entry date, committee, approval |
| Corrientes | Senado | senadoctes.gov.ar | entradas.php stale since November 2024; órdenes del día as PDFs; leyes.php HTML | allowed | partial; laws via SAIJ |
| Misiones | Cámara de Representantes | diputadosmisiones.gov.ar/nuevo/modulos/exptes.php?autor=<id> | GET, JSON, one request per member (about 40) | allowed | **next step**: number, date, subject, committees, stage (Presentado/Dictaminado/Sancionado); Executive bills missed. A "Por la Vida y los Valores" bloc files here |
| Tierra del Fuego | Legislatura | buscar.legistdf.gob.ar/sumario_completo.php (pending business); SILP | HTML (Latin-1), Crawl-delay 10 | allowed | **next step**: the sumario is current, SILP lags (328/2026 against 605/26) |
| Neuquén | Legislatura | datos.legislaturaneuquen.gob.ar (yearly CSV, newest 2025); ExpedienteLegisBusqueda (ASP.NET POST); diarios as PDFs | | CKAN API disallowed | partial; the Boletín Oficial has full-text HTML editions |
| San Juan | Cámara de Diputados | órdenes del día RSS with PDF links | RSS + PDF | allowed | partial (PDF parsing) |
| La Rioja | Legislatura | session diaries (PDF); a WordPress laws API backfilling 2005 laws | | allowed | partial |
| Chaco | Cámara de Diputados | app.chaco.gob.ar/segleg (GeneXus, AJAX POST); labor parlamentaria PDFs | | | partial |
| Catamarca | Diputados | diputadoscatamarca.gob.ar (bills as news posts); SIGPA (POST with CSRF) | | | partial |
| Catamarca | Senado | sitiosenado.catamarca.gob.ar | | | **403**; the province's digesto and portal also answered 403 |
| San Luis | Senado, Diputados | senado.sanluis.gov.ar (members only); diputados.sanluis.gov.ar | | Diputados timed out | blocked (unreachable, no bill list) |
| Formosa | Legislatura | legislaturaformosa.gob.ar php/legislaciones.php | HTML, laws only | | laws only |
| La Pampa | Cámara de Diputados | camaradediputados.lapampa.gob.ar | | timed out | unreachable (try from the Mini) |
| Santa Cruz | Cámara de Diputados | diputadosdesantacruz.gob.ar | | Disallow `/*?`, Crawl-delay 60, visit window | **BLOCKED** by robots.txt (every page is a `?page_id=` URL); SILEG needs a login. Laws in its Boletín Oficial (HTML) |
| Santiago del Estero | Cámara de Diputados | no site resolves | | | **BLOCKED**: no source |

No provincial legislature publishes roll calls in a form we read
(Chubut's session page links `votaciones.zip` files: a phase-2 look).
Members' lists exist as HTML for most chambers; they are not collected
(the edition names authors as the lists print them).

Boletines Oficiales measured: Buenos Aires (normas.gba, read), CABA (search
page), Córdoba (403), Santa Fe (daily HTML sections), Tucumán (HTML
notices), Salta (laws search, a POST), Entre Ríos (a JavaScript app),
Mendoza (the host tried does not resolve), Neuquén (full-text HTML), Santa
Cruz (laws as HTML), Río Negro and Jujuy (PDF only), Chubut (403). None is
needed while SAIJ answers; Neuquén's and Santa Cruz's are the fallbacks if
it stops.

## Relevance ranking

By population and activity on our ground, then source quality:
Buenos Aires (17.6 m), CABA (3.1 m), Córdoba (3.8 m), Santa Fe (3.5 m),
Mendoza (2.0 m), Tucumán (1.7 m), Entre Ríos (1.4 m), Salta (1.4 m),
Misiones, Chaco, Corrientes, then the rest. CABA's Legislatura is the most
active on our ground by far (below); Salta matters for religious education
(read since 13 October); Misiones has an explicitly pro-life bloc, and Santa
Fe's Diputados has "Vida y Familia" and "Somos Vida" blocs.

## What the first read found (13 October 2026, scratch store)

2,579 expedientes and 125 laws read. On our ground (taxonomy-es, Argentina
scoping): 84 expedientes (CABA 49, Buenos Aires Diputados 21, Córdoba 13,
Río Negro 1) and 5 laws. Among them, in the CABA Legislatura:
`caba:2563-D-2026` bans "terapias de conversión"; `caba:2686-E-2026` (from
the Executive) sets a floor, transparency and a designated lead for ESI in
schools; `caba:2068-D-2026` creates an IVE care programme; `caba:2498` and
`caba:2565-D-2026` welcome and repudiate Argentina's adherence to the Geneva
Consensus Declaration. In Buenos Aires: a request on compliance with the
province's adherence to the Ley Micaela, a Día del Orgullo LGTBI+ bill. These
five CABA bills seed `watchlist-ar.yaml`'s new `provincial` section.

Noise seen: commemorations and "de interés" declarations dominate every
list; the national noise rules apply unchanged (suicide-prevention days,
`culto*`), plus one new exclusion for "cultor" (a Corrientes law honouring a
musician matched `culto*`).

Taxonomy term **APPLIED 13 October 2026** (Chris, 13 October 2026: "Accept the watchlists, apply the terms after measuring";
`docs/keyword-taxonomy-es.md` v0.4): "salud sexual" for Argentina (`[only:
ar]`, area 1, tier 2). Measured on scratch reads of the provincial layer
(2,374 Buenos Aires, CABA and Córdoba expedientes, 671 Salta Diputados
projects, 117 SAIJ laws) and the national store: 3 matches, Buenos Aires
D-3281/26-27 (adhesion to World Sexual Health Day) newly on our ground,
CABA 2124-D-2026 and Salta 91-53619/26 already area 1 through "salud sexual y
reproductiva"; 0 false positives; Mexico, Chile and Spain unchanged.
"protocolo ILE" / "interrupción legal del embarazo" already exist.

## What was built

- `src/ar_regions_store.py`: `arp_laws` (key `<province>/ley/<number>`),
  `arp_bills` (key `<legislature>:<number>`, with `moved`/`prev_status` for
  stage moves), `arp_reads`; created by `db.init_db`.
- `tools/ar_regions.py`: ten sources (thirteen since 13 October: `sf-dip`,
  `sal-sen`, `sal-dip`, below) (`saij`, `normas-gba`, `ba-dip`,
  `caba`, `cba`, `er-sen`, `rn`, `chu`, `juj`, `ctes-dip`), all through
  `GuardedClient`; failures and refusals are gaps (exit 3), never fatal.
  Classified on titles and sumarios only, `taxonomy-es` with `ar`, plus
  `watchlist-ar.yaml` `provincial` by key. Measured run: about 25 requests,
  two and a half minutes.
- `src/editions/ar.py`: a "Provincial legislatures" section after the Ley
  13.640 section (provincial laws new to the store and published in the last
  45 days, new provincial bills, provincial stage moves, its own coverage
  lines), through the edition's noise filters.
- `jobs/ar-weekly.sh`: a step after the national collector with a 300 s
  budget (`tools/collector_budget.sh`); `AR_RECLASSIFY` covers it. No new
  Mini job: it rides the existing Saturday 18:30 Argentina weekly.
- `tools/coverage.py`: `arp_reads`, `arp_laws`, `arp_bills` watched (7/4),
  awaiting the first Saturday run (18 October).
- Tests: `tests/test_ar_regions.py`, fixtures `tests/fixtures/ar_regions/`
  (trimmed live replies; Chubut's staff logins scrubbed).

Shared files touched: `src/db.py` (three table names, two lines in
`init_db`), `tools/coverage.py`, `config/edition-noise-ar.yaml` (one
exclusion), `config/watchlist-ar.yaml` (new `provincial` section).

## Santa Fe Diputados and Salta (13 October 2026, branch `ar-santafe-salta`)

### Santa Fe Diputados: SIEL

Chris, 13 October: "Build it". SIEL's robots.txt (fixture
`tests/fixtures/ar_regions/siel-robots.txt`) has one `Disallow: /` group per
named AI agent (GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot,
Claude-SearchBot, Claude-User, Google-Extended, PerplexityBot, CCBot,
Bytespider and others) and no `*` group, so the collector's own user agent
(`CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)`) is not covered.
Every request, the probing included, went through `src/http.HttpClient`
with that user agent inside `GuardedClient`; no browser and no
Claude-identified fetcher touched the host. Probing was 7 requests (robots.txt,
the list's first two pages, three state searches).

- **What it reads:** the list (`index.php`, then `index.php?i=20&ord=DESC`
  ...; 20 a page, newest number first, about 20 expedientes every three
  days) until a page is older than the 14-day window (at most 8 pages),
  then the search by state (`index.php?go=le`, a read-only POST of the
  public form) for "1/2 Sanción" (state 11, current: newest 23 July 2026)
  and "Sancionado" (state 12, rarely updated). Columns are read from the
  table head: the list hides the "Pasada" column in an HTML comment, the
  search shows it. The bloc printed in asterisks at the end of each
  description goes to the author; a sanctioned expediente's law number goes
  to the stage words.
- **The robots rule (Chris):** before any SIEL request each run,
  `GuardedClient.disallows_for_us` lists every Disallow in a group that
  applies to OUR user agent (a `*` group, or one naming a token of our
  product name), by both readers. If there is any (even for a path we never
  ask), or robots.txt cannot be read, SIEL is not read that run: a gap, not
  a failure. Every page is then also checked as usual. Tests:
  `SantaFeRobots` in `tests/test_ar_regions.py` and
  `test_disallows_for_us_reads_only_groups_that_apply_to_us`.
- **Smoke read (scratch store, 13 October):** 160 expedientes (120 from the
  list, 40 from the two state lists), 7 on our ground, among them a bill to
  adhere to the national Ley Johanna (perinatal death), a bill creating a
  provincial ESI programme "with a gender and diversity perspective"
  (`sf-dip:60131`), a maternity-support plan for elite sportswomen.
- Not read: the detail page (`index.php?go=d&id=`, committee route); a
  phase-2 look if the list's state words prove too coarse.

### Salta: the TLS diagnosis

Measured with `openssl s_client -showcerts` and Python's own verifying
context (`src/http.tls_context`) on 13 October 2026:

| Host | Certificate served | Chain | Python verifies |
|---|---|---|---|
| `senadosalta.gob.ar` | CN=senadosalta.gob.ar, issuer Let's Encrypt YR1, expires 17 Dec 2026, SHA-256 E6:0B:A7:85:...:77:44 | complete: leaf, YR1, ISRG "Root YR" (cross-signed by ISRG Root X1) | **yes** |
| `www.senadosalta.gob.ar` | CN=proxy510, self-signed, expires 11 Nov 2033, SHA-256 62:EE:06:C4:...:4B:0E | none | no: self-signed |
| `www.diputadosalta.gob.ar` | CN=*.diputadosalta.gob.ar, issuer Let's Encrypt YR2, expires 20 Dec 2026, SHA-256 2B:5C:F8:65:...:04:F0 | complete: leaf, YR2, Root YR | **yes** |
| `diputadosalta.gob.ar` | the same wildcard | complete | no: hostname mismatch (a wildcard does not cover the bare domain) |

So no intermediate is missing and nothing was added to `config/tls/` or a
new `config/ca-intermediates/`: the earlier failures were the two wrong
hostnames (a self-signed proxy and a wildcard mismatch), which stay
unused. Both readers use the hostnames whose certificates verify, with
verification fully on. If either chamber's certificate changes, the
request fails and is a gap.

- **Senate (`sal-sen`):** the WordPress site files each project as a post in
  a category (measured from `/wp-json/wp/v2/categories`: en trámite 52
  declaración, 53 resolución, 54 ley; aprobados 56 ley, 57 resolución, 58
  declaración). A post keeps its entry date and moves category when
  approved, so two requests: the 100 newest by date, and the 50 approved by
  last change (`orderby=modified`). Title: "Expte. N° 90-34.699/2026 –
  08/10/26 – subject"; the excerpt opens with the authors. Approval of a
  resolution or declaration is final (sanctioned); a law's is the chamber's
  (stage words "Aprobado"). Smoke read: 123 projects, 2 on our ground
  (a suicide-prevention bill; a contest for the Senate's seat on the
  Observatorio de Violencia contra las Mujeres).
- **Diputados (`sal-dip`):** only the approved lists are readable
  (`/web/proyectos_aprobados_por_periodo?periodo=<year>&tipo=ley|resolucion|declaracion`,
  one page each: number, entry date, title). The pending lists answered
  "Resultado: 0 expedientes", the expediente search needs a number, and the
  intake (Asuntos Entrados) is PDF, newest 25 August. Every row is a stage
  row: an expediente first seen in an approved list after the first read is
  a stage move (`upsert_bill`, `stage`). Smoke read: 610 approved projects
  of 2026, 30 on our ground (a hate-crimes awareness law, a bill on minors'
  access to social networks, a change to the Observatorio de Violencia
  contra las Mujeres law).

- **Diputados' intake (`sal-dip-ae`, 13 October 2026, Chris, 13 October 2026: "Accept the watchlists, apply the terms after measuring", with the Salta step):** the
  Asuntos Entrados index (`/web/asuntos_entrados`, one row per sitting since
  2021, newest first: a PDF link and the sitting's date) and each new
  sitting's PDF (`/documentos_legislativos/<id>/download_file`, about 450 KB,
  7 or 8 pages), read with pypdf in layout mode (the plain mode splits words
  at kerning gaps: "E rradicación"). Every project of law, resolution and
  declaration becomes a bill under the same `sal-dip:<expediente>` key the
  approved lists use, with its carátula, committees, authors and the
  sitting's date; the PROYECTOS DE ... sections, the projects added during
  the sitting, the "documentación ingresada" and the Senate's bills in
  revision are read, the notes, decrees and committee reports are not. At
  most two new PDFs a run (one sitting a week), after `sal-dip`, and only for
  keys not stored yet, so an approval is never overwritten by the older
  intake line. The first read takes the newest two sittings (a seed) and
  marks the older ones read. robots.txt (comments only) is asked per run
  through `GuardedClient`, the PDFs included; a refused or unreadable PDF is
  a gap. Live read (scratch store): the sittings of 11 and 25 August, 104
  projects (40 and 64), 61 new beside the 610 approved; 43 had already been
  approved. Noise seen: `nonato*` in a declaration on San Ramón Nonato's
  feast day, now an exclusion in `config/edition-noise-ar.yaml`. Fixtures:
  `tests/fixtures/ar_regions/sal-dip-ae*.{html,txt}` (pypdf's own output),
  tests `SaltaAsuntosEntrados`.

The four readers together: about 19 requests, 95 seconds measured (the
intake about 30 s); the weekly step's 420 s budget is unchanged.

## Phase list

1. **Done:** SAIJ for all 24; bills for eight legislatures (Buenos Aires
   Diputados, CABA, Córdoba, Entre Ríos Senate, Río Negro, Chubut, Jujuy,
   Corrientes Diputados); on 13 October Santa Fe Diputados (SIEL), the Salta
   Senate and Salta Diputados (approved lists, and its Asuntos Entrados
   PDFs).
2. **Next:** Tucumán's expediente app (answered late on 13 October),
   Misiones (40 JSON requests a week), Tierra del Fuego's sumario, Córdoba's
   approved texts (to mark sanctions), Jujuy's second page (the
   `registros-actual` header).
3. **PDF routes:** San Juan's órdenes del día, Neuquén's diaries, Chaco's
   labor parlamentaria, Mendoza's session diaries.
4. **From the Mini:** retry Santa Fe's Senate, Entre Ríos' Diputados, La
   Pampa and San Luis, which timed out from the UK.

## Waiting on Chris

- ~~Review the five seeded `provincial` watchlist entries~~: accepted 13
  October 2026 ("Accept the watchlists").
- ~~Approve "salud sexual" (Argentina)~~: applied 13 October 2026
  (taxonomy-es v0.4, above).
- ~~Salta Diputados' intake~~: read from the Asuntos Entrados PDFs since 13
  October 2026 (`sal-dip-ae`, above).
