# robots.txt at run time: which collectors ask, and why

12 October 2026. Chris: wrap "only the scrapers" with the per-run robots.txt
guard. PR #144 listed the collectors added since 1 October that never asked
robots.txt again after they were built. This page classifies every host each
of them requests, says which requests now ask robots.txt on every run, and
lists the feeds whose robots.txt, read live from the laptop on 12 October
2026, now refuses what we fetch or does not answer.

## How it works

- `src/robots_guard.guard(client, feed)` wraps a collector's `HttpClient` in one
  line. Every request asks robots.txt first, read once per host per run, with
  the provinces' rules (`src/prov_fetch.Context`): Robots and star_rules must
  both allow the URL; a 4xx robots.txt means no rules; a 5xx or no answer at all
  means Disallow: / for the whole host (RFC 9309 2.3.1); a Crawl-delay larger
  than the client's throttle raises that host's interval and never lowers one.
  The read itself is patient and bounded: see "Patient robots.txt reads" below.
- A URL under one of `robots_guard.DOCUMENTED_APIS` (a URL prefix: host and
  path) is a documented machine API or open-data endpoint. It is fetched exactly
  as before, with no robots.txt read. A website host that also serves an API
  (www.nrsr.sk/opendata/, www.parlament.gv.at/Filter/api/) exempts only the API
  paths; its web pages are checked.
- A refused request raises `RobotsRefused`, a `FetchError`, so the collector's
  existing `except FetchError` writes a `[gap]` line and a gaps row and moves
  on. Nothing is fatal. A host whose robots.txt is unreachable is "host
  skipped" (`host_skipped=True`); `tools/hr_chamber.py` stops its walk on it,
  and `chamber_store.not_found()` never reads a refusal as a 404.
- Where several collectors share one client (the country drivers
  `tools/country_agenda.py`, `country_petitions.py`, `country_attendance.py`,
  `country_vote_briefs.py`, `country_debate_today.py`, `country_live_debate.py`,
  `member_service.py`, and `src/chamber_store.py`'s main for every
  `tools/*_chamber.py`), the shared client is wrapped once and the API list
  decides per URL.
- The three urllib scope probes (`tools/nic_probe.py`, `ve_probe.py`,
  `ve_news_crawl.py`) have no client to wrap; they call
  `robots_guard.probe_refusal(url)` before each request.
- A collector that reads only documented APIs is not wrapped at all: its
  behaviour is unchanged.

Classification rule: SCRAPER = a web page or file on a website (parliament
pages, PDF listings, search pages, a site's RSS, and the undocumented JSON
backend behind a website, such as a WordPress `wp-json` route or a single-page
app's API). DOCUMENTED API = an official, documented machine API or open-data
endpoint meant for programs. Where in doubt, the host is treated as a scraper
and asked.

## Feeds that will stop or slow on the next run

Live robots.txt read from the laptop, 12 October 2026, with the identified UA
`CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)`, one read per host,
for 80 scraper hosts and about 150 sample URLs taken from each collector's own URL
templates.

Will go dark (robots.txt refuses or does not answer):

| Collector | Host | What stops | Live answer |
|---|---|---|---|
| tools/pa_rollcalls.py | sistemas.asamblea.gob.pa | segLegis: every bill, its stage history and text (deputies and the orden del dia on www.asamblea.gob.pa still read) | robots.txt answers HTTP 500, twice: read as Disallow: / |
| tools/mx_rollcalls.py | sitl.diputados.gob.mx | SITL roll calls by group and member positions | robots.txt (and the site) timed out, three tries. The job runs on GitHub Actions (mx-weekly.yml), not the laptop: if it times out there too, the feed stops |
| tools/mx_rollcalls.py | gaceta.diputados.gob.mx | the Gaceta's iniciativas and votaciones indexes | as above |
| tools/ar_rollcalls.py | votaciones.hcdn.gob.ar | nothing new: already unreachable and not collected (docs/argentina-scope.md); the weekly knock now asks robots.txt first and logs the refusal | TLS handshake timed out |

At risk (intermittent):

| Collector | Host | Note |
|---|---|---|
| src/agendas/es.py, tools/es_rollcalls.py, src/member_service.py (es), the ES day sweep | www.congreso.es | robots.txt answered in 13 s once, allowed everything we fetch, and timed out (over 30 s) twice. Since the patient reads (below) a run waits up to 45 s per attempt, three attempts, and falls back to a copy read in the last 24 hours; only a host dead for all of that is skipped for the run |

Partly refused (a few items only):

| Collector | Host | Note |
|---|---|---|
| src/country_clips.py (at), tools/at_chamber.py, src/member_service.py (at) | www.parlament.gv.at | robots.txt disallows a few hundred single items by path (takedown tickets), among them `/aktuelles/mediathek/XXVIII/NRSITZ/19` (one Nationalrat sitting's clips) and many `/gegenstand/.../SNME/...` pages. Those items are skipped with a gap; everything else is allowed |

Slower (Crawl-delay now honoured):

| Host | Crawl-delay | Collectors |
|---|---|---|
| www.assemblee-nationale.fr | 30 s | tools/fr_chamber.py (up to 60 opendata XMLs a run: the run's budget ends sooner and the rest lands next run, disclosed), src/country_clips.py (fr), the FR day sweep (3 listing pages) |
| questions.assemblee-nationale.fr | 30 s | tools/fr_chamber.py |
| www.tc.gob.pe | 30 s | tools/pe_courts.py (up to 3 listing pages and 6 notes) |
| www.impo.com.uy | 10 s | tools/uy_rollcalls.py (law texts) |
| www.legnb.ca | 10 s | tools/review_photos.py (manual) |
| www.lachambre.be | 5 s | src/agendas/be.py, tools/be_rollcalls.py, tools/be_chamber.py (src/country_clips.py already used 5 s) |

Every other scraper host answered and allows every sample URL.

## Written permissions

13 October 2026. Some hosts whose robots.txt refuses programs answered a
written request from Chris with permission for our targeted use. Chris
approved acting on them. `src/robots_guard.PERMISSIONS` records each one: the
URL prefixes it covers (host and path, one Opendatasoft dataset each, never a
whole host or a whole `/api/`), who granted it, the date, the condition in the
grantor's words, and a pointer to this section. A URL under a listed prefix
is fetched with no robots.txt read by every `GuardedClient` (wrapped with or
without `DOCUMENTED_APIS`) and by `probe_refusal`; the guard logs the
permission once per run. Every other URL on the same host still asks
robots.txt and is refused there (tested). A permission is never inferred: a
dataset not listed is asked.

| Host | Prefixes (datasets) | Granted by | Date | Condition (their words) | Our side |
|---|---|---|---|---|---|
| data.bs.ch | `/api/explore/v2.1/catalog/datasets/` 100311 (Grosser Rat: Geschäfte), 100313 (Dokumente), 100314 (Vorgänge von Geschäften), 100186 (Live-Abstimmungsergebnisse, members' votes) | Orhan Saeedi, Statistisches Amt Basel-Stadt | 13 Oct 2026 | "Sie können sehr gerne die API benutzen unter Einhaltung der Lizenz. Das heisst sie müssen die Datenquelle irgendwie verlinken." If the API is slow, download in batches. | Licence CC BY 4.0 (Parlamentsdienst des Grossen Rates). Every Basel-Stadt item and vote in the Swiss edition carries a "Source:" link to its dataset (`ch_canton_acts.source_url`, `ch_canton_divisions.source_url`), and the Cantons coverage line links all four datasets. Exports filtered server-side; votes fetched in 14-day batches; 3 s between requests |
| data.tg.ch | `/api/explore/v2.1/catalog/datasets/` sk-stat-140 (Politische Geschäfte des Grossen Rats), sk-stat-141 (Vorstösserinnen und Vorstösser), sk-stat-136 (Abstimmungen im Grossen Rat, members' votes), sk-stat-139 (Dokumente; listed, not read yet) | Felix Lorenz, Amt für Daten und Statistik (ogd@tg.ch) | 13 Oct 2026 | robots.txt is aimed at crawlers indexing the whole portal; targeted API retrieval of individual datasets is explicitly intended; our client "CitizenGO-ParlMonitor/1.0" may retrieve the Grosser Rat datasets about weekly via the API; the licence allows commercial and non-commercial use. | Licence CC0 1.0. Read once a week by jobs/ch-weekly.sh; votes from the newest stored day on (the first read: the 2024-2028 legislature in quarterly batches). Items carry their dataset link too |
| data.bl.ch | `/api/explore/v2.1/catalog/datasets/` 13090 (Landratsgeschäfte seit 2017), 13140 (Beteiligungen von Landratsmitgliedern an Vorstössen: authors and co-signatories), 13130 (Unterlagen zu Landratsgeschäften: documents), 13080 (Abstimmungsverhalten der Landratsmitglieder seit 2018: members' votes) | Johannes Hool, Project Manager, Statistisches Amt / Office for Data and Statistics, Finance and Church Directorate, Canton of Basel-Landschaft | 13 Oct 2026 | Client "CitizenGO-ParlMonitor/1.0" is authorised to retrieve the Landrat's open data records, voting results included, via the data.bl.ch API; large-scale retrieval is fine. The robots.txt `/api/` disallow targets generic crawlers; requests to specific, deliberately selected dataset endpoints (`/api/explore/v2.1/catalog/datasets/<id>/records?...`) count as API-client usage and the rule does not apply. No robots.txt change is needed; the email is the confirmation. (Paraphrased.) | Publisher Landeskanzlei des Kantons Basel-Landschaft; licence opendata.swiss `terms_by` (free use, commercial allowed, the source must be cited): every Basel-Landschaft item and vote carries a "Source:" link to its dataset, and the Cantons coverage line links all four. Read once a week by jobs/ch-weekly.sh: exports filtered server-side, business in the last 45 days plus everything in progress, votes from the newest stored day on (the first read: the 2023-2027 legislature in quarterly batches, about 1,100 votes and 97,000 member votes, under two minutes on 13 October 2026); 3 s between requests. The other Landrat datasets (13100 interests, 13110 memberships, 13120 agendas, 13150/13160 bodies) are not listed and are still asked (refused) |

Collector: `tools/ch_cantons.py` (`fetch_baselstadt_api`, `fetch_thurgau_api`,
`fetch_baselland_api`). If an API fails, the canton is read from its
parliament's own pages as before (grosserrat.bs.ch, grgeko.tg.ch,
baselland.talus.ch) and one gap line says so. Scope:
docs/switzerland-cantons-scope.md.

**Basel-Stadt, later on 13 October 2026 (branch `bs-gribs`).** The data.bs.ch
permission above **stands** and is still used: for the votes (100186, every
member's vote) and as the business fallback (100311, 100313, 100314). The
Grand Council's business is now read first from its own raw data exports,
offered the same day by Peter Frankenbach (IT lead and webmaster,
Parlamentsdienst des Grossen Rates Basel-Stadt), who wrote that data.bs.ch's
robots.txt is outside his control:
`https://grosserrat.bs.ch/component/gribs?chosentable=<table>&view=exporter&Itemid=105&format=json`
(or `format=csv`), tables `ges`, `dok`, `vor`, `siz`. **These need no
permission entry:** grosserrat.bs.ch's robots.txt allows `/component/` to
`*` (it disallows `/administrator/`, `/api/`, system folders, and five AI
crawlers by name, none of them ours), so the run-time guard asks robots.txt
for them like any other page and would refuse them if that changed (tested:
a `Disallow: /component/` makes Basel-Stadt step down to data.bs.ch with a
gap). Collector: `fetch_baselstadt_gribs`; order: exports, then data.bs.ch,
then the Grand Council's pages.

A new permission is added by appending a `Permission(...)` to
`robots_guard.PERMISSIONS` with the same fields and a row here;
`tests/test_robots_runtime.py` (`WrittenPermissionTests`) checks that every
entry is dated, attributed, dataset-narrow and documented on this page.

## Redirects: every hop is asked (13 October 2026)

Until 13 October robots.txt was asked about the URL a collector requested,
and urllib then followed any redirect unasked. `docs.un.org/<symbol>?direct=true`
had begun answering `302` to `documents.un.org/api/symbol/access`, a path
`documents.un.org/robots.txt` disallows (docs/un-sources.md). Now:

* `src/http.HttpClient` asks its registered redirect guards about every hop
  before requesting it (`_RedirectHandler`; an opener a collector passes in has
  urllib's redirect handler wrapped the same way). A refused hop raises
  `RobotsRefused` (a `FetchError`): "robots.txt disallows <hop> (redirected
  from <first url>); not fetched". Nothing is sent to the refused URL, and it
  is never served from the day's archive.
* `GuardedClient`, `guard()` and `prov_fetch.Context` register themselves; a
  hop under `DOCUMENTED_APIS` or a written permission passes unasked, as a
  first URL does. A robots.txt file is always fetchable (redirects included).
* Collectors with their own `urllib.robotparser` check register with
  `robots_guard.check_redirects(client, feed)`: `src/member_service.fetch_at`,
  `src/agendas/at.py`, `tools/at_rollcalls.py`. The urllib probes open through
  `robots_guard.probe_urlopen` (`tools/nic_probe.py`, `ve_probe.py`,
  `ve_news_crawl.py`).
* A client nothing has registered on (a documented API's) follows redirects
  exactly as before.

A robots.txt read follows its own redirects unasked (RFC 9309): the first
live scan hung on a robots.txt that redirected to a login page, because the
guard asked robots.txt about that hop, recursively.

Tests: `tests/test_robots_redirects.py`.

**Read-only scan, 13 October 2026.** Every `https://` URL literal in `src/`,
`tools/` and `config/` (392 hosts; one URL per host and two-segment path
prefix, at most 12 per host, `{...}` templates cut at the placeholder), each
fetched once as a 1-byte ranged GET through `guard()` with the honest
User-Agent: 416 read, 209 errors (mostly the cut templates answering 404),
38 refused on the first URL (already refused before this change), and 6
refused on a redirect hop:

| URL | Redirect | Effect on collectors |
|---|---|---|
| `docs.un.org/en/<symbol>?direct=true` (scanned separately) | `documents.un.org/api/symbol/access` (`Disallow: /api`) | UN drafts and HRC session reports: could not read (docs/un-sources.md) |
| `www.ourcommons.ca/Content/House/`, `/DocumentViewer/en/`, `/petitions/en/Petition/Details?Petition=`; `www.parl.ca/legisinfo/en/bill/` | a missing page redirects to `/ErrorPage/Default.aspx?...StatusCode=404`, which robots.txt disallows | only pages that do not exist: on a guarded client (`tools/ca_committees.py`, `ca_senate_committees.py`, `ca_committee_reports.py`) such a miss is now a `RobotsRefused` gap naming the ErrorPage instead of the error page; real pages are unaffected. `tools/ca_hansard.py` (an unguarded client, which detects its frontier by a 404) is unchanged |
| `datos.hcdn.gob.ar/api/` (the bare base) | `http://datos.hcdn.gob.ar/api` (robots.txt answered 500) | none: the collectors' real paths (`/api/3/action/...`) do not redirect |
| `www.abgeordnetenwatch.de/api/v2` (no slash) | `/api/v2/`, which robots.txt **disallows** (`Disallow: /api/v2/`) | none from the redirect (the real URLs carry the slash), but note: robots.txt disallows the whole API that `tools/de_rollcalls.py` and `tools/de_profiles.py` read, unguarded. Raised with Chris. Decision 13 Oct 2026: keep reading it as a documented open API (CC0, abgeordnetenwatch.de/api) while written permission is requested from info@abgeordnetenwatch.de; requests spaced 2.5 s apart to keep within the API's published 30 requests/minute limit |

Also seen: `www.nrsr.sk` redirects some https URLs to plain `http://`; the
hop is asked of robots.txt like any other, but a downgrade is not refused as
such (outside this change).

## Patient robots.txt reads

12 October 2026, Chris: "Patient robots.txt reads". One slow robots.txt
(www.congreso.es; sitl/gaceta.diputados.gob.mx) made the guard read the host
as Disallow: / for the whole run, which cost Spain a week of agenda, roll
calls, member service and day sweep. robots.txt is now read in ONE place,
`src/prov_fetch.read_robots()`, which both `prov_fetch.Context` and
`src/robots_guard` (a Context) use:

| Answer | What happens |
|---|---|
| 2xx | rules read; the text is saved to `data/robots-cache/` with its fetch time |
| 4xx | no rules (RFC 9309 2.3.1.2), at once, no retry; saved as "no rules" |
| timeout or connection error | retried: 3 attempts in all, 45 s each, 5 s then 15 s between them |
| 5xx answered promptly | retried ONCE after 5 s (RFC 9309 lets us treat it as temporary), then unreachable |
| still unreachable | a saved copy under 24 hours old stands in (logged); otherwise Disallow: / for the host, one gap, "host skipped" |

- Bounded: at most 150 s (2.5 minutes) per host for all attempts and waits;
  a later attempt's timeout shrinks to the time left, and no attempt starts
  with under 5 s left. When the collector passes its budget (`Context(budget=)`,
  `guard(client, feed, budget=)`, a `src/drain.Budget`) the read never runs
  past it either.
- The client's own retries are switched off for the read (and restored), so
  every attempt is ours and logged: `www.congreso.es: robots.txt attempt 1
  failed (timed out); retrying in 5s`, then `read on attempt 2`, or the
  cached-copy line, or the gap.
- The result is cached per host for the run, as before: one read per host.
- The on-disk copy: `data/robots-cache/<scheme>_<host>.json` (gitignored,
  per machine), holding the host, status, fetch time and text, beside the
  client's `data/raw`. RFC 9309 2.4: a cached robots.txt is not used beyond
  24 hours, so an older copy is ignored and the host is skipped as before.
  A client whose raw directory is not called `raw` (a test double) keeps no
  disk copy.

## Counts

Of the 113 collectors in the #144 list: 76 now ask robots.txt at run time
(wrapped), 35 read only documented APIs and are unchanged, and 2 already asked
robots.txt themselves (`src/agendas/at.py`, which is now also guarded through
`tools/country_agenda.py`; `tools/fetch_portraits.py`, through
`src/portraits.Robots`). Not in the #144 list and not changed: `tools/at_rollcalls.py`
(checks robots.txt), `tools/ca_rollcalls.py`, `tools/de_rollcalls.py`,
`tools/eu_rollcalls.py`, `tools/de_courts.py`, `tools/eu_courts.py` (all
built before 1 October).

## Classification

"Wrapped": yes = the request asks robots.txt every run; API = a documented API
prefix, fetched as before; no = the collector is not wrapped (API only). "Via"
names the client that is wrapped when it is not the collector's own.

### src/agendas (via tools/country_agenda.py)

| Collector | Host | Kind | Wrapped | Note |
|---|---|---|---|---|
| ar | www.senado.gob.ar | scraper | yes | weekly agenda page; allowed |
| at | www.parlament.gv.at/Filter/api/ | API | API | Parliament Open Data filter API |
| at | www.parlament.gv.at (sitting pages) | scraper | yes | already read robots.txt itself (RobotFileParser); now both |
| be | www.lachambre.be/agenda/api/ | scraper | yes | undocumented backend of the website; Crawl-delay 5 |
| br | dadosabertos.camara.leg.br, legis.senado.leg.br/dadosabertos/ | API | API | Dados Abertos |
| ch | ws.parlament.ch/odata.svc/ | API | API | OData |
| es | www.congreso.es | scraper | yes | agenda page and its PDFs; robots.txt intermittent |
| fr | data.assemblee-nationale.fr/static/openData/ | API | API | open-data repository |
| it | www.camera.it | scraper | yes | calendar pages; allowed |
| nl | gegevensmagazijn.tweedekamer.nl/OData/ | API | API | OData |
| pl | api.sejm.gov.pl | API | API | Sejm API |
| pt | agenda.parlamento.pt | scraper | yes | the agenda site's calendar handler; allowed |
| sk | www.nrsr.sk/opendata/ | API | API | open data |

### src/petition_sources (via tools/country_petitions.py)

| Collector | Host | Kind | Wrapped | Note |
|---|---|---|---|---|
| ar | consultapublica.argentina.gob.ar/api | scraper | yes | the site's own backend; allowed |
| at | www.parlament.gv.at/Filter/api/ | API | API | |
| at | www.bmi.gv.at/411/ | scraper | yes | Volksbegehren page; allowed |
| be | dekamer.mijnopinie.belgium.be/api | scraper | yes | the site's backend; allowed |
| br | www12.senado.leg.br/ecidadania/ | scraper | yes | allowed |
| br | brasilparticipativo.presidencia.gov.br/api | scraper | yes | Decidim backend; allowed |
| ch | fedlex.data.admin.ch/sparqlendpoint, ws.parlament.ch | API | API | |
| co | www.sucop.gov.co (SharePoint REST) | scraper | yes | allowed |
| fr | petitions.assemblee-nationale.fr, petitions.senat.fr | scraper | yes | allowed |
| it | firmereferendum.giustizia.it, partecipa.gov.it/api | scraper | yes | allowed |
| nl | gegevensmagazijn.tweedekamer.nl/OData/ | API | API | |
| pl | api.sejm.gov.pl | API | API | |
| pt | www.parlamento.pt | scraper | yes | allowed |

### src

| Collector | Host | Kind | Wrapped | Note |
|---|---|---|---|---|
| attendance (via country_attendance) | dadosabertos.camara.leg.br, data.assemblee-nationale.fr, gegevensmagazijn, opendata.camara.cl | API | API | |
| attendance | www.parlamento.pt | scraper | yes | plenary attendance pages; allowed |
| chamber_store (main) | see tools/*_chamber.py | | yes | the shared client of every chamber collector |
| country_clips | www.parlament.gv.at/aktuelles/mediathek/ | scraper | yes | single sittings disallowed by path |
| country_clips | api.ausp.cloud.insysgo.com, par-pcache.simplex.tv | scraper | yes | video files; no robots.txt (404) |
| country_clips | www.assemblee-nationale.fr/dyn/opendata/, videos.assemblee-nationale.fr | scraper | yes | website host; Crawl-delay 30 |
| country_clips | media.lachambre.be/api, www1.lachambre.be | scraper | yes | allowed |
| country_clips | cdn.debatdirect.tweedekamer.nl/api, debatdirect.tweedekamer.nl | scraper | yes | Debat Direct backend; allowed |
| day_sweep_sources (via country_vote_briefs) | www.assemblee-nationale.fr/dyn/17/dossiers | scraper | yes | Crawl-delay 30 |
| day_sweep_sources | www.parlamento.pt, www.sabor.hr | scraper | yes | allowed |
| day_sweep_sources | the rollcall modules' sources | as below | as below | reuses tools/<cc>_rollcalls.py readers; same classification |
| member_intel (tools/member_intel.py) | api.sejm, dadosabertos, data.assemblee, dati.camera.it/sparql, gegevensmagazijn, ws.parlament.ch, www.parlament.gv.at/Filter/api/ | API | no | API only |
| vote_brief_sources (via country_vote_briefs) | api.sejm, dadosabertos, dati.camera.it/sparql | API | API | API only |

### tools/*_rollcalls.py

| Collector | Host | Kind | Wrapped | Note |
|---|---|---|---|---|
| ar | www.senado.gob.ar | scraper | yes | actas, detalle, verExp, DatosAbiertos export pages; allowed |
| ar | datos.hcdn.gob.ar/api/ | API | API | CKAN |
| ar | votaciones.hcdn.gob.ar | scraper | yes | unreachable (known) |
| au | data.openaustralia.org.au, handbookapi.aph.gov.au, api.prod.legislation.gov.au | API | no | API only |
| be | www.lachambre.be | scraper | yes | CRI, flwb pages; Crawl-delay 5 |
| bo | diputados.gob.bo/wp-json, apisi.senado.gob.bo | scraper | yes | WordPress and SPA backends; allowed |
| br | dadosabertos.camara.leg.br, legis.senado.leg.br/dadosabertos/ | API | no | API only |
| ch | ws.parlament.ch/odata.svc/ | API | API | |
| ch | www.parlament.ch (Council of States xlsx) | scraper | yes | allowed |
| cl | opendata.camara.cl, tramitacion.senado.cl/wspublico/ | API | API | |
| cl | www.senado.cl | scraper | yes | senators page; allowed |
| co | www.camara.gov.co (pages, admin-ajax), leyes.senado.gov.co/api | scraper | yes | allowed |
| co | www.datos.gov.co/resource/ | API | API | Socrata |
| do | www.diputadosrd.gob.do/sil/api/ | scraper | yes | SIL backend, undocumented; allowed |
| ec | datos.asambleanacional.gob.ec/ecurul/, www.asambleanacional.gob.ec | scraper | yes | allowed |
| es | www.congreso.es | scraper | yes | opendata pages and files on the website; intermittent |
| fr | data.assemblee-nationale.fr/static/openData/ | API | no | API only |
| gt | www.congreso.gob.gt | scraper | yes | allowed |
| hn | congresonacional.hn, api.congresonacional.hn, enag.gob.hn | scraper | yes | allowed |
| hr | www.sabor.hr | scraper | yes | allowed |
| ie | api.oireachtas.ie | API | no | API only |
| it | dati.camera.it/sparql, dati.senato.it/sparql, service.opdm.openpolis.io | API | no | API only |
| mx | sitl.diputados.gob.mx, gaceta.diputados.gob.mx | scraper | yes | unreachable from the laptop (see above) |
| nl | gegevensmagazijn.tweedekamer.nl/OData/ | API | no | API only |
| pa | www.asamblea.gob.pa | scraper | yes | deputies, orden del dia; allowed |
| pa | sistemas.asamblea.gob.pa | scraper | yes | robots.txt 500: GOES DARK |
| pe | api.congreso.gob.pe (spley), senado/diputados.congreso.gob.pe (wp-json, uploads) | scraper | yes | allowed |
| pl | api.sejm.gov.pl | API | no | API only |
| pt | www.parlamento.pt | scraper | yes | allowed |
| sk | www.nrsr.sk/opendata/ | API | API | |
| sk | www.nrsr.sk/web/ | scraper | yes | vote, print and document pages; allowed |
| sv | www.asamblea.gob.sv | scraper | yes | allowed |
| us | api.congress.gov, www.govinfo.gov/bulkdata/, unitedstates.github.io | API | API | |
| us | clerk.house.gov/evs/, www.senate.gov/legislative/LIS/ | scraper | yes | roll-call XML on websites; allowed |
| uy | documentos.diputados.gub.uy/docs/DA*.json | API | API | datos abiertos files |
| uy | documentos.diputados.gub.uy (PDFs), www.impo.com.uy | scraper | yes | allowed; IMPO Crawl-delay 10 |

### tools/*_chamber.py (via src/chamber_store.py; also read by country_live through country_debate_today / country_live_debate)

| Collector | Host | Kind | Wrapped | Note |
|---|---|---|---|---|
| at | www.parlament.gv.at/Filter/api/ | API | API | |
| at | www.parlament.gv.at (gegenstand ?json=TRUE, documents) | scraper | yes | single items disallowed by path |
| be | www.lachambre.be | scraper | yes | Crawl-delay 5 |
| br | dadosabertos.camara.leg.br | API | API | |
| br | www.camara.leg.br (SitCamaraWS, sitaqweb) | scraper | yes | allowed |
| ch | ws.parlament.ch/odata.svc/ | API | API | |
| ch | www.parlament.ch (Amtliches Bulletin) | scraper | yes | allowed |
| fr | data.assemblee-nationale.fr/static/openData/ | API | API | |
| fr | www.assemblee-nationale.fr/dyn/opendata/, questions.assemblee-nationale.fr | scraper | yes | Crawl-delay 30: slower |
| hr | edoc.sabor.hr | scraper | yes | allowed; a host skip ends the walk with one gap |
| nl | gegevensmagazijn.tweedekamer.nl/OData/ | API | API | API only |
| pl | api.sejm.gov.pl | API | API | API only |
| pt | www.parlamento.pt | scraper | yes | allowed |
| sk | www.nrsr.sk/web/ | scraper | yes | allowed |

### tools/*_courts.py

| Collector | Host | Kind | Wrapped | Note |
|---|---|---|---|---|
| ca | decisions.scc-csc.ca, www.scc-csc.ca, decisions.fct-cf.gc.ca | scraper | yes | RSS and item pages; allowed |
| co | www.datos.gov.co/resource/ | API | no | API only |
| ec | www.corteconstitucional.gob.ec/wp-json | scraper | yes | allowed |
| pe | www.tc.gob.pe | scraper | yes | Crawl-delay 30 |
| pt | www.tribunalconstitucional.pt | scraper | yes | allowed |
| us | www.supremecourt.gov | scraper | yes | allowed (its static ROBOTS_DISALLOW stays) |

### Other tools

| Collector | Host | Kind | Wrapped | Note |
|---|---|---|---|---|
| au_debates | www.openaustralia.org.au | scraper | yes | allowed |
| au_division_brief | data.openaustralia.org.au | API | no | API only (au_rollcalls.make_client) |
| au_schedule | handbookapi.aph.gov.au, api.prod.legislation.gov.au | API | no | |
| bo_questions | apisi.senado.gob.bo, diputados.gob.bo/wp-json | scraper | yes | allowed |
| be_regions | ws.vlpar.be/e/opendata/, www.parlement-wallonie.be/opendata/ | API | API | the Flemish Parliament's open-data web services and the Walloon Parliament's documented Open Data (13 October 2026) |
| be_regions | ws.vlpar.be/api/search/ | scraper | yes | the Flemish website's search route; robots.txt redirects to the host's access page (no rules) |
| be_regions | www.parlement.brussels, www.pfwb.be | scraper | yes | the Brussels dossier file behind the website; the PFWB pages; both allowed |
| ca_committee_reports | www.ourcommons.ca, www.parl.ca, sencanada.ca | scraper | yes | allowed (12 October 2026) |
| ca_committees | www.ourcommons.ca, www.parl.ca | scraper | yes | allowed |
| ca_senate_committees | sencanada.ca | scraper | yes | allowed (12 October 2026) |
| ca_senate_debates | sencanada.ca | scraper | yes | allowed |
| ch_cantons (CH7, 13 October 2026) | parlzhcdws.cmicloud.ch, ogd.parl.apps.be.ch, ge.ch, www.vd.ch, www4.ti.ch | scraper and open data | yes (GuardedClient, no exemptions) | all allowed on 13 October 2026 (cmicloud and ogd.parl 404, ge.ch serves a web page as robots.txt); Ticino's acts search is disallowed and not used. data.bs.ch and data.tg.ch (`/api/` disallowed): the Grand Council datasets only, read with written permission since 13 October 2026 (see "Written permissions"); data.bl.ch likewise (the Landrat datasets 13090, 13140, 13130, 13080, branch `ch-bl-ods`). Not read because robots.txt refuses: daten.sg.ch (`/api/`), www.ag.ch (`/grossrat`). Added 13 October 2026 (access-routes), all allowed: grosserrat.bs.ch (disallows `/api/`, not used; since `bs-gribs` its `/component/gribs` exports, allowed, are Basel-Stadt's primary business source), baselland.talus.ch (disallows `/*searchTerm=`, not used; Basel-Landschaft's fallback since `ch-bl-ods`), www.ratsinfo.sg.ch (serves its app page as robots.txt: no rules), grgeko.tg.ch (allows all), gesetzessammlungen.ag.ch (disallows its search paths, not used) |
| cl_senate_parties | datos.bcn.cl/sparql | API | no | |
| country_agenda, country_petitions, country_attendance, country_vote_briefs, country_debate_today, country_live_debate | (drivers) | | yes | wrapped once, see above |
| devolved_brief | parl-monitor-partner.vercel.app, github.com | own | no | our own site and repository |
| fetch_portraits | (many) | scraper | already | src/portraits.Robots reads robots.txt per run |
| fr_hatvp | www.hatvp.fr/livraison/ | API | no | HATVP open-data files |
| fr_senat | data.senat.fr/data/ | API | no | |
| hr_party_history | edoc.sabor.hr | scraper | yes | allowed |
| hu_gazette | magyarkozlony.hu | scraper | yes | feed, listing, PDFs; allowed |
| hu_karzat_backfill | api.github.com, raw.githubusercontent.com | API | no | our own repository |
| it_senato_amendments | dati.senato.it/sparql, api.github.com, raw.githubusercontent.com | API | API | the Senate's AkomaNtosoBulkData repository (12 October 2026): git trees API and raw files; github.com's robots.txt sends programs to the API, both hosts answer 404 for robots.txt |
| ie_debates, ie_questions | api.oireachtas.ie | API | no | |
| ie_division_brief | api.oireachtas.ie, data.oireachtas.ie | API | no | |
| ie_schedule | www.oireachtas.ie | scraper | yes | allowed |
| member_intel | (see src/member_intel) | API | no | |
| member_service | www.congreso.es, www.parlament.gv.at/person/ | scraper | yes | intermittent (congreso.es); AT also read robots.txt itself |
| member_service | the national APIs | API | API | |
| nic_gaceta | www.lagaceta.gob.ni | scraper | yes | robots.txt 404 |
| nic_probe | verifica.asamblea.gob.ni | scraper | yes (probe_refusal) | allowed |
| nl_eerstekamer | www.eerstekamer.nl | scraper | yes | allowed |
| party_colours | query.wikidata.org/sparql | API | no | |
| pe_ocr | senado/diputados.congreso.gob.pe uploads | scraper | yes | allowed |
| review_photos | ourcommons, sencanada, ola.org, assembly.ab.ca, legassembly.sk.ca, api.lims.leg.bc.ca, gov.mb.ca, legnb.ca | scraper | yes | allowed; legnb Crawl-delay 10 |
| uy_diario | www.diputados.gub.uy (PDFs) | scraper | yes | allowed |
| us_division_brief | www.govinfo.gov/bulkdata/ | API | API | |
| us_division_brief | clerk.house.gov, www.senate.gov | scraper | yes | allowed |
| us_federal_register | www.federalregister.gov/api/ | API | no | |
| us_record | api.govinfo.gov | API | API | |
| us_record | www.govinfo.gov (metadata, content) | scraper | yes | allowed |
| us_schedule | docs.house.gov, www.senate.gov | scraper | yes | allowed |
| us_states | v3.openstates.org, data.openstates.org | API | no | |
| us_states_legiscan | api.legiscan.com (keyed, optional) | API | no | legiscan.com itself answers a Cloudflare challenge: never bypassed |
| us_states_direct | ftp.legis.state.tx.us/bills/ | API (FTP) | no | the Council's Acceptable Use notice asks data users to use the FTP; FTP has no robots.txt |
| us_states_direct | www.kslegislature.gov/li/api/ (KLISS), downloads.leginfo.legislature.ca.gov | open data | yes | robots.txt 404 on both (no rules), 13 October 2026 |
| us_states_routes | www.palegis.us/data (LDPC bill history) | open data | yes | robots.txt has one group, for the UserWay scanner only; /data is open to all, 13 October 2026 |
| us_states_routes | documents.house.mo.gov (House XML exports) | open data | yes | allowed; Crawl-delay 20 honoured |
| us_states_routes | arkleg.state.ar.us (bill, activity and vote pages) | scraper | yes | allowed (only ChatGPT's agents are disallowed) |
| ve_news | www.asambleanacional.gob.ve | scraper | yes | allowed |
| ve_news_crawl, ve_probe | www.asambleanacional.gob.ve (and any probed URL) | scraper | yes (probe_refusal) | allowed |

## Tests

`tests/test_robots_runtime.py`: the API exemption (a documented API is never
asked about robots.txt, the website beside it is), Crawl-delay, and one
collector per family (`src/agendas/it.py`, `src/petition_sources/fr.py`,
`tools/gt_rollcalls.py`, `tools/hr_chamber.py`) for a disallowed path, a 503
robots.txt and a 404 one. `tests/robots_fakes.guarded_api()` builds a
`guard()`-wrapped fake. `PatientReadTests` (fake client and clocks): a
timeout then success is allowed, three timeouts are Disallow: / with one gap
inside 150 s, the collector's budget caps the retries, a prompt 503 gets one
retry then Disallow: /, a 404 is no rules at once, a saved copy under 24 h is
used when the host is unreachable and one over 24 h is ignored.
`WrittenPermissionTests`: a listed dataset prefix is fetched with no
robots.txt read although robots.txt disallows `/api/`; an unlisted dataset,
the catalogue and every other path on the same host are still asked and
refused; with no permissions passed, the listed prefix is asked too; every
`PERMISSIONS` entry is dated, attributed, dataset-narrow and listed here. `tests/test_sv_rollcalls.py`'s main() test now serves
robots.txt as 404.
