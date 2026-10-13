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
| ca_committee_reports | www.ourcommons.ca, www.parl.ca, sencanada.ca | scraper | yes | allowed (12 October 2026) |
| ca_committees | www.ourcommons.ca, www.parl.ca | scraper | yes | allowed |
| ca_senate_committees | sencanada.ca | scraper | yes | allowed (12 October 2026) |
| ca_senate_debates | sencanada.ca | scraper | yes | allowed |
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
used when the host is unreachable and one over 24 h is ignored. `tests/test_sv_rollcalls.py`'s main() test now serves
robots.txt as 404.
