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
| dadosabertos.almg.gov.br | `/api/v2/` (recorded with `asks_robots=True`: **not** a skip, see below) | ALMG Centro de Atendimento ao Cidadão (protocolo 126599) | 14 Oct 2026 | At our written request ALMG changed its robots.txt to `Allow: /documentacao/`, `Allow: /api/ajuda/`, `Allow: /api/v2/`, while keeping `Disallow: /api/v2/*?*p=`, `/api/v2/*?*ord=`, `/api/v2/*?*tp=`, `/api/v2/*?*ordenacao=` and `Disallow: /`. We asked whether paging is acceptable; no answer yet. | Read by `tools/br_states.py` (`fetch_mg_api`), Minas Gerais, weekly. robots.txt is still read every run and obeyed: the wildcard rules refuse every paged or sorted URL (Robots and star_rules both match `*` and take the longest rule; `tests/test_robots_runtime.py`, `AlmgRobotsTests`), and the collector's `mg_api_url()` refuses to build one. Searches narrow by publication date (a week, split to days when a week holds more than one page of 20); a day holding more than one page is completed by reading bills one by one by number, and what a run's cap leaves is a gap carried to the next run. ALMG's own limits are kept: one request at a time, 1.5 s apart (they ask for at most two at once and one second between). If ALMG confirms paging and lifts the Disallow lines, paging can replace the date splitting |

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

**Minas Gerais, 15 October 2026 (branch `almg-bs-extra`).** ALMG's answer
was a robots.txt change, not an exemption, so its `Permission` carries
`asks_robots=True`: `permission_for()` never returns it (no skip), while
`recorded_permission()` does, so the record stays with the others. A paged
or sorted URL (`p=`, `tp=`, `ord=`, `ordenacao=`) is refused by the guard
exactly as before the change.

**Basel-Stadt, daily downloads (15 October 2026).** Peter Frankenbach (IT
lead, Parlamentsdienst des Grossen Rates Basel-Stadt) wrote on 13 October
2026 offering further GRIBS exports and allowing a DAILY download (the data
are updated nightly around 03:00): `zuw` (Zuweisungen an Gremien: committee
assignments), `dok` (documents) and `adr` (Ratsmitglieder: members),
`https://grosserrat.bs.ch/component/gribs/?chosentable={zuw|dok|adr}&view=exporter&Itemid=105&format={csv|json}`.
`tools/ch_cantons.py` now reads `zuw` and `adr` beside `ges`, `dok`, `vor`
and `siz`, once a week in jobs/ch-weekly.sh (well inside the daily
allowance). Like the other GRIBS exports these need no `Permission` entry:
grosserrat.bs.ch's robots.txt allows `/component/`, and the run-time guard
still asks it. Votes stay on data.bs.ch 100186 under Orhan Saeedi's
permission above.

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
| 3xx | followed, to any host and unasked, at most 5 hops (`src/http.ROBOTS_MAX_REDIRECTS`, urllib and the curl fallback alike); the file at the end is read as if served at the first URL. A sixth hop: unavailable, so no rules (RFC 9309 2.3.1.2) |
| 2xx web page | a body that is an HTML document (opens with `<!DOCTYPE html>`/`<html>`/`<head>`/`<body>` and has no line-initial `User-agent`/`Allow`/`Disallow`) has no robots groups: no rules, logged "robots.txt answered a web page, not a robots file; no rules" |
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

**A robots.txt that ends on a web page (16 October 2026, Chris).**
`dokumente.landtag.rlp.de/robots.txt` answers 302 to
`www.landtag.rlp.de/de/startseitex/`, which answers 302 to the Landtag's home
page. RFC 9309 follows the redirects and finds no groups: no rules. Two things
had made it "unreachable" instead: the laptop's Python cannot negotiate that
host's TLS, and the curl fallback (`HttpClient._fetch_via_curl`) did not follow
redirects, so it reported "HTTP 302". The fallback now follows redirects for
robots.txt URLs only (`-L --max-redirs 5`, http/https only) and raises the
final status as an HTTP error (so a 404 is no rules and a 503 is still a
skipped host); any other URL is still not followed by curl, whose hops would
bypass the redirect guards. Unchanged: 5xx and unreachable = Disallow: /;
4xx = no rules; every hop of a fetched document's redirect chain is asked of
its own host's robots.txt. A genuine robots file reached by redirect is
honoured. Tests: `tests/test_robots_redirects.py`
(RobotsTxtRedirectToPageTests, LooksLikeHtmlTests, CurlFallbackRedirectTests).

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

### src/gov_doc_sources (via tools/country_gov_docs.py, 16 October 2026)

Government consultations and publications (src/gov_docs.py). One guarded
client (`guard()`): every URL below that is not a documented API asks
robots.txt on every run, every redirect hop included. Mirrors (AT `me`, CH
`vl`, IT `partecipa`, PL `sejm`, AR `cp`, BR `bp`, CO `sucop`, US `fr`, CA
`gazette`, HU `mk`) fetch nothing: they re-file rows a sibling collector
stored this week.

| Reader | Host | Path | Kind | Wrapped | robots.txt (16 October 2026) |
|---|---|---|---|---|---|
| ar | www.boletinoficial.gob.ar | /seccion/primera/, /detalleAviso/primera/ | scraper | yes | disallows only /seccion/segunda* and /detalleAviso/segunda/* |
| at | www.bundeskanzleramt.gv.at | /medien/ministerraete*, /bundeskanzleramt/nachrichten-der-bundesregierung/ | scraper | yes | disallows only /401 |
| at | www.sozialministerium.gv.at | /Services/Aktuelles/ | scraper | yes | /.syndication/ (its RSS), /.search/, /Portal.Node/ disallowed and not used |
| au | consultations.health.gov.au | /api/2.4/json_search_results | scraper | yes | Disallow /*view_respondent; Crawl-delay 5 honoured |
| au | api.prod.legislation.gov.au | /v1/titles/search | API | API | Federal Register of Legislation API |
| be | www.belgium.be | /fr/actualites/ | scraper | yes | Drupal defaults |
| be | www.health.belgium.be | /fr/news | scraper | yes | Disallow /*?find= (its rss.xml redirect is refused there; the listing is read) |
| be | justice.belgium.be | /fr/news/rss | scraper | yes | Drupal defaults |
| be | igvm-iefh.belgium.be | /fr/actualite | scraper | yes | Drupal defaults |
| br | legis.senado.leg.br/dadosabertos/ | /legislacao/lista.json | API | API | Senado Dados Abertos |
| ca | open.canada.ca | /static/current_consultations_open.csv | scraper | yes | Crawl-delay 20 honoured; Drupal paths disallowed |
| ca | api.io.canada.ca | /io-server/gc/news/en/v2 | scraper | yes | 404, no rules |
| ch | www.newsd.admin.ch | /newsd/feeds/rss | scraper | yes | 404, no rules |
| ch | fedlex.data.admin.ch | /sparqlendpoint | API | API | |
| cl | www.diariooficial.interior.gob.cl | /edicionelectronica/index.php | scraper | yes | Disallow /edicionelectronica/ with Allow index.php; select_edition.php refused and never requested (editions are asked by number on index.php) |
| de | www.bmjv.de (www.bmj.de redirects) | /SiteGlobals/Functions/RSSNewsfeed/, /SharedDocs/ | scraper | yes | Allow /SiteGlobals/Functions/RSSNewsfeed/; the rest of /SiteGlobals/ disallowed and not used |
| de | www.bmbfsfj.bund.de | /bmbfsfj/ministerium/gesetze, /service/rss/ | scraper | yes | Disallow: (empty) |
| de | www.bundesgesundheitsministerium.de | /service/gesetze-und-verordnungen, /pressemitteilungen.xml | scraper | yes | Allow /; ?id=, cHash, forms disallowed |
| de | www.bundesregierung.de | /service/rss/breg-de/ | scraper | yes | no * group |
| es | www.boe.es | /datosabiertos/api/boe/sumario/ | scraper | yes | nothing under /datosabiertos/ disallowed (documented API; candidate for DOCUMENTED_APIS) |
| es | www.igualdad.gob.es, www.mpr.gob.es | /servicios/participacion/ | scraper | yes | nothing disallowed |
| es | www.sanidad.gob.es | /normativa/ | scraper | yes | /buscador/ etc. disallowed |
| es | www.mjusticia.gob.es | /es/ciudadania/normas-tramitacion | scraper | yes | /_layouts/ etc. disallowed |
| es | www.educacionfpydeportes.gob.es | /servicios-al-ciudadano/informacion-publica* | scraper | yes | /*docroot/ disallowed |
| fr | echanges.dila.gouv.fr | /OPENDATA/JORF/ | scraper | yes | 404, no rules (DILA open data) |
| fr | www.consultations-publiques.developpement-durable.gouv.fr | /spip.php?page=liste-consultations | scraper | yes | Disallow /ecrire/; Crawl-delay 1 |
| fr | solidarites.gouv.fr | /rss.xml | scraper | yes | Drupal defaults |
| hr | data.gov.hr | /ckan/api/3/action/package_show, the dataset's data.json | scraper | yes | robots.txt answers the HTML app: no rules |
| hr | narodne-novine.nn.hr | /get_index_file.aspx, /api/act | scraper | yes | /clanci/oglasi/ and single articles disallowed; our paths allowed |
| hu | kormany.hu | /application/document-groups | scraper | yes | Disallow /publicapi only; the JSON the site loads, allowed |
| ie | www.irishstatutebook.ie | /eli/<year>/si/ | scraper | yes | 404, no rules |
| it | www.gazzettaufficiale.it | /30giorni/, /gazzetta/serie_generale/ | scraper | yes | 404, no rules |
| mx | sidof.segob.gob.mx | /dof/sidof/notas/ | scraper | yes | /CopiasCert? and about 100 single notes disallowed (documented keyless web service) |
| nl | gegevensmagazijn.tweedekamer.nl/OData/ | Document | API | API | |
| nl | www.officielebekendmakingen.nl, zoek.officielebekendmakingen.nl | /staatsblad, /stb-YYYY-N.html | scraper | yes | disallows only /noindex/*, /zoeken/resultaat*, /resultaten* |
| pe | diariooficial.elperuano.pe | /Normas/Filtro | scraper | yes | /NormasElperuano/, /DatosAbiertos/ etc. disallowed; the filter allowed |
| pe | busquedas.elperuano.pe | /dispositivo/ | scraper | yes | Allow / |
| pl | www.gov.pl | /web/premier/wplip-rm, /register-file/*.csv | scraper | yes | Allow / |
| pl | api.sejm.gov.pl | /eli/ | API | API | |
| pt | files.diariodarepublica.pt | /rss/ | scraper | yes | robots.txt answers the app shell: no rules |
| pt | www.consultalex.gov.pt | / | scraper | yes | 404, no rules |
| sk | api-gateway.slov-lex.sk | /internal/elegislativa/legislativne-materialy/ | scraper | yes | 404, no rules (the JSON slov-lex.sk's pages load) |

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
| sp_agenda (15 October 2026) | www.parliament.scot (`/chamber-and-committees/whats-on-and-watch-live/whats-on?dateFrom=`) | scraper | yes | allowed: robots.txt disallows only `/sitecore`, `/temp/`, `/upload/`, `/xsl/` and app folders. The old Business Bulletin paths 301 to webarchive.nrscotland.gov.uk (the new site's catch-all for unknown paths); not followed, not used |
| sp_agenda | data.parliament.scot (`/api/MotionsQuestionsAnswersMotionsBusiness?motionfilter=programme`) | open data | yes | robots.txt 404 (no rules); the Parliament's open-data API, asked anyway like the rest of the client |
| sd_agenda (15 October 2026) | business.senedd.wales (`/mgWebService.asmx/`) | API (ModernGov web service) | yes | robots.txt answers the Azure WAF's 403 page (a 4xx: no rules, RFC 9309). The web service answers the identified UA with 200 and XML; the host's web pages (calendar, agenda pages) answer that UA and every non-browser client 403, and are not read. The browser UA src/http.py keeps for this host is removed on this client |
| ve_news_crawl, ve_probe | www.asambleanacional.gob.ve (and any probed URL) | scraper | yes (probe_refusal) | allowed |
| uk_petitions (16 October 2026) | petition.parliament.uk (`/petitions.json?state=open` or `closed`, `&page=N`, `/petitions/<id>.json`) | public JSON behind the website (treated as a scraper) | yes | allowed: robots.txt disallows only admin, check, signing, sponsor and thank-you paths |
| govuk_docs (16 October 2026) | www.gov.uk (`/api/search.json`, `/api/content/<path>`) | documented API (not on DOCUMENTED_APIS, so asked) | yes | allowed: robots.txt disallows only `/*/print$` and `/search/all*` |
| govuk_docs | www.ofcom.org.uk (`/consultations-and-statements` and each consultation's page) | scraper | yes | allowed: robots.txt disallows `/episerver/`, `/utils/`, search and filter query strings; see "UK regulators" below |
| govuk_docs | www.england.nhs.uk (`/publication/feed/?paged=N` and each publication page) | scraper (a website's RSS) | yes | allowed: robots.txt disallows only `/wp-admin/` |

## UK regulators (16 October 2026)

The UK edition's regulator consultations (src/ingest/regulators.py) declared
Ofcom, GMC and EHRC as BLOCKED on 7 September 2026: all three answered 403 to
every non-browser client. Re-tried from the laptop on 16 October 2026 with the
identified UA, looking for legitimate alternative routes before keeping the
gap (never a browser UA, a proxy or a challenge bypass):

| Regulator | Tried | Result | What the edition reads now |
|---|---|---|---|
| Ofcom | www.ofcom.org.uk robots.txt, home page, `/consultations-and-statements`, a consultation page; `/rss`, `/feeds/rss` (no feed exists: 404); Ofcom's gov.uk organisation | the site answers 200 to our UA again; robots.txt allows the listing and the pages. Ofcom's gov.uk organisation holds 401 documents (statistics announcements and guidance), not its consultations | tools/govuk_docs.py reads the listing (title, description, site section) and each consultation on our ground's page for its closing date ("Consultation closes: 4 November 2026"), into govuk_docs (source 'ofcom'); its gov.uk organisation is read with the publications. Ofcom left regulators.BLOCKED |
| EHRC | equalityhumanrights.com home page, `/consultations`, `/rss.xml`, `/en/rss.xml`, `/feed`, `/sitemap.xml`; robots.txt; EHRC's gov.uk organisation | every page, feed and sitemap answers 403 (a Cloudflare check); robots.txt itself answers (a managed file that allows `User-agent: *`, disallows AI crawlers by name) but the block is the bot check, which we never pass. EHRC's gov.uk organisation holds 64 documents, among them the Equality Act 2010 Code of Practice for services (5 August 2026) | gov.uk organisation `equality-and-human-rights-commission` read by tools/govuk_docs.py with the publications. Still a declared gap (regulators.BLOCKED) for everything published only on its own site |
| GMC | www.gmc-uk.org home page, robots.txt, `/rss`, `/feed`, `/sitemap.xml`; gmc.citizenspace.com, consultations.gmc-uk.org (do not resolve); gov.uk organisation `general-medical-council` | 403 to everything, robots.txt included; no Citizen Space host; no gov.uk organisation (404) | nothing: declared gap (regulators.BLOCKED). Not yet tried: whether gmc-uk.org answers GitHub's runners (a probe workflow would say; not dispatched from the laptop) |
| NHS England | www.england.nhs.uk robots.txt, `/feed/`, `/publication/feed/` | the WordPress publication feed answers (RSS 2.0, 10 items a page, `?paged=N`), with NHS England's own topic categories; the feed's descriptions are empty, so each page's summary is read | tools/govuk_docs.py, source 'nhs-england' (first read: "Guidance on NHS staff facilities", 15 October 2026, single-sex facilities). Its statistics also reach gov.uk (organisation `nhs-england`). The Citizen Space consultations listing stays in regulators.py |

## Government documents: blocked hosts and the alternatives tried (16 October 2026)

For the gov_docs layer (src/gov_docs.py). Nothing below was bypassed: no
browser user agent, no challenge solved, no token taken from a site's code,
TLS verification never switched off. Each blocked route is a gap or was
replaced by a legitimate alternative.

| Country | Host | Refusal | Alternative |
|---|---|---|---|
| NL | www.internetconsultatie.nl | robots.txt `User-agent: * Disallow: /` | none found: repository.overheid.nl (KOOP SRU), zoekservice.overheid.nl, linkeddata.overheid.nl and open.overheid.nl are all `Disallow: /`; data.overheid.nl disallows /data/ (CKAN); zoek.officielebekendmakingen.nl/sru/Search is allowed but answers 500; the Rijksoverheid open-data API keeps only school holidays. Read instead: Kamerbrieven (Tweede Kamer OData) and the Staatsblad pages. Consultation deadlines: a gap. Route: KOOP's documented SRU if Chris lists it, or a written permission |
| PL | legislacja.gov.pl | `Disallow: /` | the Council of Ministers' register CSV on www.gov.pl (drafts, no deadlines), Dziennik Ustaw and Monitor Polski through the ELI API; isap.sejm.gov.pl, dziennikustaw.gov.pl, monitorpolski.gov.pl are `Disallow: /` (links only) |
| IE | www.gov.ie | CloudFront 403 "Request blocked", robots.txt included | irisoifigiuil.ie (robots.txt refuses us), data.gov.ie (Disallow /api/; its catalogue search finds statistics, no consultations register), merrionstreet.ie and ncca.ie (403), hse.ie (no consultations page), hiqa.ie, cnam.ie, electoralcommission.ie, lawreform.ie, citizensassembly.ie, tusla.ie (allowed, no list with closing dates), assets.gov.ie (no listing). Read instead: statutory instruments from the Irish Statute Book. Consultations: a gap. Not yet tried: GitHub's runners |
| AT | data.bka.gv.at (RIS OGD API) | robots.txt `User-agent: * Disallow: /` | none for the Bundesgesetzblatt: www.ris.bka.gv.at answers a Myra "Security Check" (503). Documented at data.bka.gv.at/ris/ogd/v2.6/Documents/Dokumentation_OGD-RIS_API.pdf: a written permission, or Chris's decision to list it, would open made law |
| BE | www.ejustice.just.fgov.be (Moniteur belge; also moniteur.be, staatsblad.be) | robots.txt disallows /cgi/, /eli/, /mopdf/, /loi/, /wet/ and the rest | no Moniteur dataset on data.gov.be; news.belgium.be, premier.be, belgiquelex.be answer 403. Read instead: belgium.be news and consultations, FPS Health, FPS Justice, IEFH. Route: a written permission from the FPS Justice |
| FR | www.vie-publique.fr; www.legifrance.gouv.fr; www.info.gouv.fr; sante.gouv.fr | a JavaScript and cookie wall; 403; Incapsula 403; an F5 bot page | the JORF from DILA's open data (echanges.dila.gouv.fr), the ecology ministry's consultations site, solidarites.gouv.fr RSS. The PISTE Legifrance API needs an account: not created |
| BR | www.in.gov.br (DOU) | `Disallow: /`; INLABS a WAF page and a login | Senado Dados Abertos legislation list (laws, MPs, decrees) |
| MX | www.dof.gob.mx; cofemersimir.gob.mx / conamer.gob.mx | certificate for another host; do not resolve or hostname mismatch | SIDOF's documented web service (sidof.segob.gob.mx); CONAMER's draft regulations: a gap |
| ES | www.juventudeinfancia.gob.es, www.dsca.gob.es | TLS failures under the laptop's LibreSSL 2.8.3 (certificate signature failure; handshake failure) | read as Disallow: / with a gap every run; a Python with a current OpenSSL may read them |
| AU | www.ag.gov.au, www.dss.gov.au, www.infrastructure.gov.au, www.esafety.gov.au | robots.txt unreachable (timeouts): Disallow: / | consultations.health.gov.au (Citizen Space API) and the Federal Register of Legislation; consult.industry/dcceew/education are JavaScript apps with no documented API |
| PT | diariodarepublica.pt | an OutSystems app whose data calls need an anti-forgery token from its scripts | the official RSS feeds on files.diariodarepublica.pt (latest issue only) |
| HR | esavjetovanja.gov.hr | a Blazor Server app, content only over a websocket | the government's open-data copy of the consultations on data.gov.hr (refreshed about monthly) |
| CO | www.diariooficial.gov.co | does not resolve | SUCOP drafts (mirrored) |

## Regional forward agendas (16 October 2026)

`tools/regional_agenda.py <cc>` (src/regional_agenda.py, one module per
country in src/regional_agendas/), a step of each regional weekly through
`tools/regional_agenda_step.sh`. Every request goes through
`src.robots_guard.guard` (robots.txt asked per host per run and on every
redirect hop; documented APIs pass unasked as everywhere else). A refused
route is a region with status `blocked`; a region with no permitted,
readable route is `no-route`, each with its note, printed every run and
kept in `regional_agenda_runs`. The per-region detail is in each regional
scope doc's "Forward agenda (regional_agenda, 16 October 2026)" section.

| Module | Host (path) | Kind | Asks robots.txt | Notes |
|---|---|---|---|---|
| regional_agendas/us | v3.openstates.org (/events) | API | no (documented API) | free key in the X-API-KEY header only; at most 30 a run, 6.5 s apart, written to the uss_api_ledger before sending (225 a UTC day shared with tools/us_states.py) |
| regional_agendas/us | wslwebservices.leg.wa.gov (/CommitteeMeetingService.asmx/) | API | yes | robots.txt 404 (no rules); the Legislature's documented web service, HTTP GET binding |
| regional_agendas/us | capitol.texas.gov (/MyTLO/RSS/RSS.aspx) | scraper | yes | allowed (/MyTLO/RSS/ not disallowed); /TLODOCS/ is disallowed, so meeting notices are linked, never fetched (each meeting a booked slot) |
| regional_agendas/es | www.parlamentodeandalucia.es (/webdinamica/portal-web-parlamento/actividadparlamentaria/agendasemanal.do, calendariodesesiones.do) | scraper | yes | allows all |
| regional_agendas/es | www.parlament.cat (/web/actualitat/agenda/, /web/actualitat/ordre-dia/, /web/composicio/ple-parlament/calendari-anual/) | scraper | yes | allows /web; /apl, /ext, /pls disallowed (never read) |
| regional_agendas/es | www.cortsvalencianes.es (/es/actividad/actualidad/agenda) | scraper | yes | Drupal default; agenda paths allowed |
| regional_agendas/es | www.ccyl.es (/Agenda/Semana, /Agenda/Evento, /Actividad/PlenosPrevistos) | scraper | yes | disallows /*agenda.do*, /*agenda.html*, /*.rss$; these paths allowed |
| regional_agendas/es | www.parcan.es (/actividad/calendario/, /reuniones/futuras.py, /reuniones/asuntos.py) | scraper | yes | Crawl-delay 3 honoured; /api/, /api2/ disallowed (never read) |
| regional_agendas/es | www.cortesaragon.es (/Semana-actual.2237.0.html, /Proxima-semana.2335.0.html, /Acto-programado.2319.0.html, /fileadmin/_DMZMedia/comunicacion/web/varios/calendario.csv) | scraper + CSV | yes | /*?id=* disallowed (index.php?id= never used; realurl paths instead) |
| regional_agendas/es | parlamento-cantabria.es (/agenda-semana) | scraper | yes | Drupal default; allowed |
| regional_agendas/es | Madrid, Galicia, Navarra, Asturias (bot walls: Sucuri, Akamai, Cloudflare, a bot test); Castilla-La Mancha, Murcia, Extremadura (robots.txt) | - | - | blocked, never bypassed; País Vasco, Illes Balears no answer from the UK; La Rioja no readable route |
| regional_agendas/at | www.wien.gv.at (/politik/rathaus-sitzungstermine, /infodat/suchergebnisse) | scraper | yes | allowed; /infodat/ergli and /infodat/sukri disallowed, never used |
| regional_agendas/at | noe-landtag.gv.at (/sitzungen, /sitzungen/XX/<date>) | scraper | yes | Allow: / |
| regional_agendas/at | www.land-oberoesterreich.gv.at (/60566.htm) | scraper | yes | allowed; landtag.ooe.gv.at (Tagesordnung) not fetched: its certificate does not verify (never bypassed) |
| regional_agendas/at | pallast2.stmk.gv.at (/pallast-p/api/pub/materials/meetings/next/, /pallast-p/pub/meeting) | API/scraper | yes | no robots.txt on the host (no rules) |
| regional_agendas/at | www.salzburg.gv.at (/pol/landtag/lt-termine) | scraper | yes | allowed; service.salzburg.gv.at (LPI) robots.txt answers 503, not used |
| regional_agendas/at | www.tirol.gv.at (/landtag/sitzungen/) | scraper | yes | allowed; lte.tirol.gv.at Disallow: / (not used) |
| regional_agendas/at | vorarlberg.at (/web/landtag/tagesordnungen) | scraper | yes | allowed (/documents/, /o/, /suche/ barred, not used) |
| regional_agendas/at | www.bgld-landtag.at (/landtagssitzungen/) | scraper | yes | allowed |
| regional_agendas/at | www.ktn.gv.at | - | yes | User-agent: * Disallow: / (Google and Bing only): Kärnten blocked |
| regional_agendas/ch | api.openparldata.ch (/v1/meetings, /v1/agendas, /v1/groups) | open data API | yes | allowed; CC BY 4.0 ("Source: OpenParlData.ch"); a third-party republisher, read for fifteen cantons (Aargau left out while its own host refuses us; question with Chris) |
| regional_agendas/ch | parlzhcdws.cmicloud.ch (/parlzh3/cdws/Index/SITZUNGENDETAIL/searchdetails) | API | yes | robots.txt 404 (no rules); the index kantonsrat.zh.ch's own calendar asks |
| regional_agendas/ch | ge.ch (/grandconseil/sessions/seances/, /grandconseil/sessions/seances-odj-lion/) | scraper | yes | no rules |
| regional_agendas/ch | www.vd.ch (/gc/seances-du-grand-conseil) | scraper | yes | allowed |
| regional_agendas/ch | www4.ti.ch (/poteri/gc/attivita/ordine-del-giorno/, /calendario-delle-sedute) | scraper | yes | allowed; the acts search stays disallowed, not used |
| regional_agendas/ch | parlement.vs.ch (/api/fe/v1/parl_sessions, /api/fe/v1/parl_session) | API (the app's JSON) | yes | empty robots.txt (no rules) |
| regional_agendas/ch | kr-geschaefte.zug.ch (/gast/traktandenlisten) | scraper | yes | allowed |
| regional_agendas/ch | www.fr.ch, www.parlinfo.fr.ch | - | yes | /fr/, /search/, ?page and /node/ disallowed (parlinfo redirects to /node/): Fribourg blocked |
| regional_agendas/be | ws.vlpar.be (/e/opendata/verg/komende, /verg/<id>/agd) | API | no (documented API) | DOCUMENTED_APIS; covers the coming week only |
| regional_agendas/be | www.parlement-wallonie.be (/opendata/agenda_od.php) | open data | no (documented API) | DOCUMENTED_APIS |
| regional_agendas/be | nautilus.parlement-wallon.be (/Archives/<ses>/ODJS, ODJC PDFs) | scraper | yes | allowed; orders of the day via pypdf |
| regional_agendas/be | www.parlement.brussels (/agenda/) | scraper | yes | only GPTBot disallowed |
| regional_agendas/be | weblex.irisnet.be (/display_pdf.php?info=convoc_fr) | scraper | yes | allowed; weblex.brussels (the linked host) has a mismatched TLS certificate, never bypassed |
| regional_agendas/be | www.pfwb.be (/agenda, /agendas/*) | scraper | yes | empty Disallow |
| regional_agendas/be | www.parlementfrancophone.brussels (/agenda, /agenda/convocations/*) | scraper | yes | empty Disallow |
| regional_agendas/be | pdg.be | - | yes | Cloudflare 403, robots.txt included: blocked |
| regional_agendas/it | www.consiglio.regione.lazio.it (/, ?vw=homeCommissioni) | scraper | yes | allowed; the Aula odg views (?vw=elencolavoriaula, tbl_lavori_aula_odg2) are disallowed and not read |
| regional_agendas/it | www.cr.campania.it (/atti-e-documenti/DG-attivita/ordine-del-giorno-prossime-sedute, /crccmsintegrationservices/...prendiDocumento) | scraper | yes | allowed; Crawl-delay 10 honoured |
| regional_agendas/it | www.ars.sicilia.it (/agenda/lavori-aula, /agenda/sedute-commissioni, /agenda/{aula,commissione}/YYYYMMDD) | scraper | yes | robots.txt 404 (no rules) |
| regional_agendas/it | www.assemblea.emr.it (/agenda/ics_view) | iCalendar | yes | allowed; only search paths disallowed |
| regional_agendas/it | www.consiglio.regione.toscana.it (/aula/prox-sedute.aspx, /default.aspx?nome=odg_seduta) | scraper | yes | robots.txt 404 (no rules) |
| regional_agendas/it | www.consiglio.marche.it (/attivita/assemblea/sedute/) | scraper | yes | robots.txt 404 (no rules) |
| regional_agendas/it | www.consiglio.provincia.tn.it (/attivita/convocazioni/Pages/Convocazioni-per-data.aspx) | scraper | yes | allowed; /opendata/ and /normattiva/ disallowed, not used |
| regional_agendas/it | www.consiglioregionale.calabria.it (/, /portale/Istituzione/Commissioni/VisualizzaOdG) | scraper | yes | allowed |
| regional_agendas/it | Lombardia, Puglia (robots.txt Disallow: /), Basilicata (/consiglio-api disallowed), Veneto (Akamai 403) | - | yes | blocked, never bypassed |
| regional_agendas/ca | www.ola.org (/en/legislative-business/house-documents/..., /en/ajax/calendar-month/<date>) | scraper | yes | only /*? disallowed; path URLs only |
| regional_agendas/ca | www.assnat.qc.ca (/fr/travaux-parlementaires/calendrier-travaux.html[?Date=]) | scraper | yes | allowed; /json/ and /scripts/ disallowed and not used (so the calendar JSON is not read) |
| regional_agendas/ca | www.leg.bc.ca (/parliamentary-business/parliamentary-calendar) | scraper | yes | Drupal standard; allowed |
| regional_agendas/ca | www.assembly.ab.ca (/assembly-business/assembly-records/order-papers, /assembly-business/committees), docs.assembly.ab.ca (/LADDAR_files/docs/houserecords/op/) | scraper | yes | sitemap line only |
| regional_agendas/ca | www.legassembly.sk.ca (/api/days, /api/documents), docs.legassembly.sk.ca (/legdocs/Assembly/Orders/) | API (the site's calendar JSON) | yes | robots.txt 404 (no rules) |
| regional_agendas/ca | www.gov.mb.ca (/legislature/business/orderpaper.pdf, sessional_order_<y>.pdf, /legislature/committees/meeting_notices.html and notice PDFs) | scraper | yes | `*` allows /legislature/; named AI crawlers refused, our UA not (as for prov_collect, 2 Oct) |
| regional_agendas/ca | www.legnb.ca (/en/calendar/<y>-<m>) | scraper | yes | Crawl-delay 10, honoured |
| regional_agendas/ca | nslegislature.ca (/get-involved/calendar/ical/legislative-assembly, /ical/committee) | iCalendar | yes | Crawl-delay 10, honoured |
| regional_agendas/ca | www.assembly.nl.ca (/HouseBusiness/OrderPapers/) | scraper | yes | allowed |
| regional_agendas/ca | www.ntassembly.ca (/file/orders, /committees/upcoming-meeting-dates) | scraper | yes | allowed |
| regional_agendas/ca | www.assembly.pe.ca (Radware CAPTCHA), yukonassembly.ca (Cloudflare 403) | - | - | blocked, never bypassed; Nunavut publishes no order paper ahead (no-route) |
| regional_agendas/au | www.parliament.vic.gov.au (/api/calendar/twelve-months) | API (the page's JSON) | yes | names only Facebook crawlers; 2 s throttle |
| regional_agendas/au | dynamic-content-api.parliament.sa.gov.au (/api/documentlibrary, /api/GetFileDownloadLink), prodinterappst.blob.core.windows.net | API | yes | robots.txt 404 (no rules) |
| regional_agendas/au | search.parliament.tas.gov.au (/search/quicksearch/<y>/sittingdays.html, the Notice Papers database search, its .docx files) | scraper (search engine) | yes | robots.txt 404 (no rules) |
| regional_agendas/au | NSW, ACT, NT (Cloudflare 403), QLD, WA (Azure WAF 403) | - | - | blocked, never bypassed; NSW's API host carries only past Hansard |
| regional_agendas/de (NW) | www.landtag.nrw.de (/cms/render/live/.../kalender/contentArea/*, /home/der-landtag/tagesordnungen/) | scraper | yes | allowed (old MM documents, the document search and videos disallowed, not used) |
| regional_agendas/de (BY) | www.bayern.landtag.de (/aktuelles/tagesordnungen/, /webangebot3/views/tagesordnungdirektanzeige/) | scraper | yes | allowed (/webangebot2/Vorgangsmappe, /service/suche, eID disallowed, not used) |
| regional_agendas/de (BW) | www.landtag-bw.de (/resource/calendar/.../terminkalender.ics, /de/aktuelles/tagesordnungen, /resource/blob/) | iCalendar + scraper | yes | allows everything |
| regional_agendas/de (NI) | www.landtag-niedersachsen.de (/fileadmin/calendar_abo/, /rss/, /parlamentsdokumente/) | iCalendar + RSS | yes | allowed |
| regional_agendas/de (HE) | hessischer-landtag.de (/termine/) | scraper | yes | allowed |
| regional_agendas/de (SN) | www.landtag.sachsen.de (/de/aktuelles/plenarsitzungen/, /ausschusssitzungen/) | scraper | yes | lists allowed; /de/aktuelles/sitzungskalender (agendas, ics) disallowed and never fetched; edas.landtag.sachsen.de disallows all: sittings only |
| regional_agendas/de (BE) | www.parlament-berlin.de (/termine/ical/) | iCalendar | yes | allowed (/opendata/, /suche/, Pari2013 disallowed, not used): sittings only |
| regional_agendas/de (BB) | www.landtag.brandenburg.de (/cms/detail.php RSS, /sixcms/detail.php) | RSS + scraper | yes | allows everything |
| regional_agendas/de (HB) | sd.bremische-buergerschaft.de (/termine/ics/, /tops/) | iCalendar + scraper | yes | allowed; *.pdf disallowed, never fetched |
| regional_agendas/de (HH) | www.hamburgische-buergerschaft.de (/aktuelles/termine/...!search, /resource/blob/) | scraper | yes | allowed |
| regional_agendas/de (MV) | www.landtag-mv.de (/plenum-und-ausschuesse/plenum/aktuelle-plenarwoche, /fileadmin/) | scraper | yes | allowed |
| regional_agendas/de (RP) | api.landtag-rlp.de (/api/meeting/filteredList) | API (the site's own) | yes | robots.txt 404 (no rules); dokumente.landtag.rlp.de's robots.txt answers 302s ending on the Landtag's HTML home page: no rules since 16 October 2026 (Chris), so the Einladung PDFs are read |
| regional_agendas/de (ST) | www.landtag.sachsen-anhalt.de (/service/terminuebersichten) | scraper | yes | allowed: plenary dates only |
| regional_agendas/de (SH) | www.landtag.ltsh.de (dayMonthKalenderGetter.jsp, /infothek/wahl20/plenum/, /export/sites/ltsh/) | JSON + scraper | yes | allowed |
| regional_agendas/de (TH) | www.thueringer-landtag.de (/fileadmin/calendar_abo/, /plenum/sitzungstermine/, /uploads/tx_tltcalendar/) | iCalendar + scraper | yes | allowed |
| regional_agendas/de (SL) | www.landtag-saar.de | - | yes | robots.txt unreachable (TCP timeout): nothing fetched (no-route) |
| regional_agendas/br | legis-api-portal-prd.al.sp.gov.br (/sessoes-plenarias/, /colegiado/) | API (the ALESP portal's own JSON) | yes | robots.txt 404 (no rules); www.al.sp.gov.br disallows only /web, /StaticFile and some repositories |
| regional_agendas/br | dadosabertos.almg.gov.br (/api/v2/comissoes/reunioes/pesquisa, /api/v2/plenario/reunioes/) | open data | yes | /api/v2/ allowed since 14 October 2026 at our request; paging and sorting (p=, tp=, ord=, ordenacao=) still disallowed and never built |
| regional_agendas/br | www2.alerj.rj.gov.br (/ordemdodia/, /ordemdodia/pauta/) | scraper | yes | robots.txt answers the home page (no rules); about 30 s a request; 5 s throttle |
| regional_agendas/br | transparencia.assembleia.pr.leg.br (/plenario/pautas/*/ajax), storage2.assembleia.pr.leg.br (PDFs) | scraper (portal JSON + PDFs) | yes | empty Disallow |
| regional_agendas/br | www.alepe.pe.gov.br (/agenda, /ordem-do-dia/ POST; /detalhe-ordem-do-dia/) | scraper | yes | empty Disallow |
| regional_agendas/br | www.al.ce.gov.br (/agenda) | scraper | yes | only /banco-de-imagens/download/ disallowed |
| regional_agendas/br | www.alepa.pa.gov.br (/Home/Page/PautasdoPlenario, /Legislativo/DetalhesPauta) | scraper | yes | allows all |
| regional_agendas/br | sapl.al.{pb,am,al,pi,ro,to,ac}.leg.br (/api/sessao/sessaoplenaria/, /api/sessao/ordemdia/) | API (SAPL REST) | yes | /api/ allowed; Crawl-delay 60 honoured (the seven houses are asked in parallel, one request at a time per house); sapl.al.rr.leg.br answers 403 to robots.txt: blocked |
| regional_agendas/mx | congresoyucatan.gob.mx (/, /gaceta/sesiones-pleno/, /storage/uploadCey/*.pdf) | scraper + PDF | yes | empty Disallow |
| regional_agendas/mx | www.congresojal.gob.mx (/agenda-parlamentaria/mes/) | scraper | yes | Crawl-delay 10 honoured; path allowed |
| regional_agendas/mx | www.congresochihuahua.gob.mx (/sesiones.php, /ordenDia.php) | scraper | yes | names search engines and AI bots only; others allowed |
| regional_agendas/mx | www.congresoqroo.gob.mx (/agenda/, /ordenesdia/) | scraper | yes | robots.txt 404 (no rules) |
| regional_agendas/mx | www.cbcs.gob.mx (/, the Orden del Día category) | scraper | yes | robots.txt 404 (no rules) |
| regional_agendas/mx | Puebla (Cloudflare), San Luis Potosí (Sucuri), Durango (Wordfence geo block), Campeche (robots.txt Disallow: /) | - | - | blocked, never bypassed; CDMX's certificate names another host (robots.txt unreadable, nothing fetched) |
| regional_agendas/pl | bip.mazovia.pl (/pl/bip/sejmik/sesje-sejmiku/, /komisje-sejmiku/planowane-posiedzenia.html) | scraper | yes | allowed |
| regional_agendas/pl | bip.slaskie.pl (/sejmik_wojewodztwa/sesje_sejmiku/projekty_uchwal/) | scraper | yes | allowed; slow host, 3 s |
| regional_agendas/pl | bip.malopolska.pl (/api/menu/437636/articles, /api/articles/<id>) | the BIP app's JSON | yes | allowed (only admin and listed article pages disallowed) |
| regional_agendas/pl | bip.pomorskie.eu (/api/articles/60421, .docx downloads) | the BIP app's JSON + DOCX | yes | allowed |
| regional_agendas/pl | bip.dolnyslask.pl (/api/articles/107616, /api/articles/99529) | the BIP app's JSON | yes | allowed |
| regional_agendas/pl | sejmik.podkarpackie.pl (/prace-sejmiku/sesje, /prace-sejmiku/posiedzenia-komisji, /images/sesje_7/*.docx) | scraper + DOCX | yes | allowed (Joomla system folders and /api/ disallowed, not used) |
| regional_agendas/pl | bip.kujawsko-pomorskie.pl, bip.lodzkie.pl, bip.warmia.mazury.pl, bip.wzp.pl (sitting notices and porządek obrad pages) | scraper | yes | allowed; *.esesja.pl stays behind a Cloudflare bot check, never bypassed |
| regional_agendas/ar | parlamentaria.legislatura.gob.ar (/webservices/Json.asmx/GetAgendasMesCurso, GetAgendasDiaById, GetSesionesMesCurso) | the site calendar's XML web service | yes | robots.txt 404 (no rules); 3 s |
| regional_agendas/ar | www.hcdiputados-ba.gov.ar (/), intranet.hcdiputados-ba.gov.ar (/reuniones/OD_*.pdf) | scraper + PDF | yes | robots.txt 404 (no rules); 5 s |
| regional_agendas/ar | legislaturacba.gob.ar (/agenda/, /wp-json/wp/v2/eventos) | scraper + WordPress REST | yes | allows all but /wp-admin/; 3 s |
| regional_agendas/pe | www.gob.pe (/institucion/<slug>/informes-publicaciones/tipos/91-agenda-de-sesion-de-consejo-regional, 93- for Lima Metropolitana) | scraper | yes | allowed (/admin/ and ?sheet= disallowed only); 3 s |

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
