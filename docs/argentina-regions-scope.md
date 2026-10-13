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
| Santa Fe | Diputados | siel.diputadossantafe.gov.ar (SIEL) | POST search | names AI agents (GPTBot, ClaudeBot, Claude-User ...), no `*` group | **NOT BUILT, Chris to decide**: our collector's user agent is allowed, but the agent that built this layer is a Claude agent and did not probe past the home page |
| Santa Fe | Senado | senadosantafe.gob.ar | | timed out (twice) | unreachable from the laptop |
| Mendoza | Senado | senadomendoza.gob.ar | | allowed | **403** to our requests |
| Mendoza | Diputados | hcdmza.gob.ar/site/ | HTML; projects listed in the session diaries (PDF) | Crawl-delay 60 | slow and timed out once; not built (a minute a request) |
| Tucumán | Legislatura | legislaturadetucuman.gob.ar (React app); app2.legislaturadetucuman.gob.ar/consultaexpedientes | HTML | | the expediente app timed out, then answered later the same day: **next step** |
| Entre Ríos | Senado | senadoer.gob.ar/buscador-proyectos (WordPress) | GET, HTML, ten a page | allowed (only /wp-admin/) | **BUILT** (`er-sen`): number, type, author, committee, media sanción and sanción |
| Entre Ríos | Diputados | hcder.gov.ar | | timed out (twice) | unreachable from the laptop |
| Salta | Senado, Diputados | senadosalta.gob.ar, diputadosalta.gob.ar | | TLS fails (self-signed; hostname mismatch) | **BLOCKED** (TLS verification is not turned off) |
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
and is blocked by TLS; Misiones has an explicitly pro-life bloc.

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

Proposed taxonomy terms (NOT added; `config/taxonomy-es.yaml` is generated
and never hand-edited): "salud sexual" for Argentina (Buenos Aires' "Día
Mundial de la Salud Sexual" declaration and CABA's requests on "salud sexual
y reproductiva" matched only through other words); "protocolo ILE" /
"interrupción legal del embarazo" already exist.

## What was built

- `src/ar_regions_store.py`: `arp_laws` (key `<province>/ley/<number>`),
  `arp_bills` (key `<legislature>:<number>`, with `moved`/`prev_status` for
  stage moves), `arp_reads`; created by `db.init_db`.
- `tools/ar_regions.py`: ten sources (`saij`, `normas-gba`, `ba-dip`,
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

## Phase list

1. **Done:** SAIJ for all 24; bills for eight legislatures (Buenos Aires
   Diputados, CABA, Córdoba, Entre Ríos Senate, Río Negro, Chubut, Jujuy,
   Corrientes Diputados).
2. **Next:** Tucumán's expediente app (answered late on 13 October),
   Misiones (40 JSON requests a week), Tierra del Fuego's sumario, Córdoba's
   approved texts (to mark sanctions), Jujuy's second page (the
   `registros-actual` header).
3. **PDF routes:** San Juan's órdenes del día, Neuquén's diaries, Chaco's
   labor parlamentaria, Mendoza's session diaries.
4. **From the Mini:** retry Santa Fe's Senate, Entre Ríos' Diputados, La
   Pampa and San Luis, which timed out from the UK.

## Waiting on Chris

- Santa Fe Diputados' SIEL: its robots.txt names AI agents (ClaudeBot,
  Claude-User and others) but has no rule for other agents, so our
  collector's own user agent is allowed. Build it or not?
- Review the five seeded `provincial` watchlist entries.
- Approve "salud sexual" (Argentina) for the next taxonomy generation.
- Salta: both chambers fail TLS verification; we do not turn verification
  off. A pinned certificate (as for Mexico, `config/mx-ca-intermediates.pem`)
  would need someone to vouch for it.
