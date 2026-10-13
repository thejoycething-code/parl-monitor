"""robots.txt checked at RUN time, for collectors that do not run inside
src/prov_fetch.Context.

The regional collectors added on 12 October 2026 (tools/es_regions.py,
tools/pe_regions.py, tools/it_regions.py) read each site's robots.txt when
they were built, and then fetched on every run without asking again: a site
that later disallowed us would have gone on being crawled. This wraps their
HttpClient so every request asks robots.txt first, read once per host per
run, with the provinces' reader and rules (src/prov_fetch.Context):

  * both readers must allow the URL: Robots (the RFC 9309 matcher) and
    star_rules (every '*' group, literal paths);
  * a robots.txt answering 4xx means no rules; a 5xx or no answer at all
    means "unreachable", read as Disallow: / for the whole host (RFC 9309
    2.3.1; #142). The read is patient (src/prov_fetch.read_robots, 12
    October 2026): 45 s per attempt, timeouts and dropped connections
    retried (3 attempts), a 5xx retried once, at most 150 s per host and
    never past a budget passed in, and a copy read in the last 24 hours
    (data/robots-cache/) stands in for an unreachable host;
  * a Crawl-delay larger than the client's throttle raises THAT host's
    interval (HttpClient.set_host_throttle never lowers one already set, so a
    collector's own per-host delay stands).

A refused request raises RobotsRefused, a FetchError, so the collectors'
existing `except FetchError` paths turn it into a [gap] line and a gaps row
and move on: never fatal, never a silent skip. `host_skipped` is True when
the whole host is refused (robots.txt unreachable), so a collector looping
over one host's pages can stop asking it.

12 October 2026 (additive, "only the scrapers"): the other collectors
listed in #144 wrap their client with `guard()`, which is GuardedClient with
`exempt=DOCUMENTED_APIS`. A URL under one of those prefixes is an official,
documented machine API or open-data endpoint meant for programs (the Sejm
API, Tweede Kamer OData, congress.gov ...): it is fetched exactly as before,
with no robots.txt read. Every other URL (parliament web pages, PDF
listings, search pages, a website's RSS, an undocumented JSON backend behind
a website) asks robots.txt first. The classification, collector by collector,
is docs/robots-runtime.md. GuardedClient's default (exempt nothing) is what
the regional collectors of #144 use, unchanged.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from src.http import FetchError
from src.prov_fetch import Context


# URL prefixes of documented machine APIs and open-data endpoints, exempt
# from the run-time robots.txt check under guard(). A prefix names a host and
# a path, so a website host that also serves an API (www.nrsr.sk/opendata/)
# exempts only the API paths. docs/robots-runtime.md says why each is here.
DOCUMENTED_APIS = (
    # Poland, Netherlands, Switzerland, EU
    "https://api.sejm.gov.pl/",
    "https://gegevensmagazijn.tweedekamer.nl/OData/",
    "https://ws.parlament.ch/odata.svc/",
    # Austria: the Parliament's documented Open Data filter API (the
    # gegenstand/person pages on the same host are web pages: checked)
    "https://www.parlament.gv.at/Filter/api/",
    "https://fedlex.data.admin.ch/sparqlendpoint",
    "https://data.europarl.europa.eu/api/",
    # France: the Assemblee's open-data repository (bulk zips) and the
    # Senat's open-data files
    "https://data.assemblee-nationale.fr/static/openData/",
    "https://data.senat.fr/data/",
    "https://www.hatvp.fr/livraison/",
    # Italy: the two chambers' SPARQL endpoints and the Openpolis API
    "https://dati.camera.it/sparql",
    "https://dati.senato.it/sparql",
    "https://service.opdm.openpolis.io/api-openparlamento/",
    # Slovakia: the National Council's open-data files
    "https://www.nrsr.sk/opendata/",
    # Brazil: Camara Dados Abertos (API and bulk files), Senado Dados Abertos
    "https://dadosabertos.camara.leg.br/",
    "https://legis.senado.leg.br/dadosabertos/",
    # Argentina HCDN CKAN, Colombia Socrata (datos.gov.co), Chile
    "https://datos.hcdn.gob.ar/api/",
    "https://www.datos.gov.co/resource/",
    "https://opendata.camara.cl/camaradiputados/WServices/",
    "https://tramitacion.senado.cl/wspublico/",
    # Uruguay: the Camara's datos abiertos JSON files (DA*.json); the PDFs
    # beside them are documents: checked
    "https://documentos.diputados.gub.uy/docs/DA",
    "https://datos.bcn.cl/sparql",
    # Ireland
    "https://api.oireachtas.ie/",
    "https://data.oireachtas.ie/",
    # United States
    "https://api.congress.gov/",
    "https://api.govinfo.gov/",
    "https://www.govinfo.gov/bulkdata/",
    "https://www.federalregister.gov/api/",
    "https://v3.openstates.org/",
    "https://data.openstates.org/",
    "https://unitedstates.github.io/congress-legislators/",
    # US states, alternative sources (13 October 2026): LegiScan's documented
    # Pull API (keyed; legiscan.com itself sits behind a Cloudflare challenge
    # we never bypass). Kansas KLISS and California's leginfo downloads are
    # NOT listed: robots.txt is asked for them every run. The Texas FTP (no
    # robots.txt exists for FTP) is exempted in tools/us_states_direct.py.
    "https://api.legiscan.com/",
    # Australia
    "https://api.prod.legislation.gov.au/",
    "https://handbookapi.aph.gov.au/api/",
    "https://data.openaustralia.org.au/",
    # Belgium's regional parliaments (tools/be_regions.py, 13 October 2026):
    # the Flemish Parliament's open-data web services (the search route
    # ws.vlpar.be/api/search/ behind its website is not listed: checked), and
    # the Walloon Parliament's documented Open Data (JSON/CSV, /opendata/)
    "https://ws.vlpar.be/e/opendata/",
    "https://www.parlement-wallonie.be/opendata/",
    # Wikidata, GitHub (our own repository, and since 12 October 2026 the
    # Italian Senate's AkomaNtosoBulkData repository read by
    # tools/it_senato_amendments.py: the git trees API and raw files;
    # github.com's robots.txt sends programs to the API, and both hosts
    # answer 404 for robots.txt), our own partner site
    "https://query.wikidata.org/sparql",
    "https://api.github.com/",
    "https://raw.githubusercontent.com/",
    "https://parl-monitor-partner.vercel.app/",
)


def is_documented_api(url, exempt=DOCUMENTED_APIS):
    return any(url.startswith(p) for p in exempt)


class RobotsRefused(FetchError):
    """A request robots.txt does not allow; it was never sent."""

    def __init__(self, url, feed, slug, reason, host_skipped=False):
        super().__init__(url, feed, slug, 0, reason)
        self.reason = reason
        self.host_skipped = host_skipped

    def __str__(self):
        return self.reason


class RobotsGuard(Context):
    """Context's robots.txt reader without the rest of Context: no store, no
    budget. Gaps are the caller's to record (refusal() returns the reason)."""

    def __init__(self, client, feed, log=print, budget=None, **robots_kwargs):
        keep = getattr(client, "throttle", None)
        # budget (optional, src/drain.Budget): a robots.txt read never runs
        # past it. robots_kwargs: Context's read_robots knobs (cache dir,
        # clocks), for tests.
        super().__init__(None, client, feed, feed=feed, log=log, budget=budget,
                         **robots_kwargs)
        if keep is not None:
            # Context raises a client's throttle to 1.1 s for the provinces;
            # here the collector's own throttle stands.
            client.throttle = keep

    def gap(self, detail):
        # The caller records the gap (it owns the store and the feed); the
        # unreachable reason comes back through refusal().
        self.gaps.append(detail)

    def refusal(self, url):
        """None when robots.txt allows `url`, else (reason, host_skipped)."""
        rp = self._parser(url)
        unreachable = getattr(rp, "unreachable", None)
        if unreachable:
            return unreachable, True
        if self.allowed(url):
            return None
        return "robots.txt disallows {0}; not fetched".format(url), False

    def crawl_delay(self, host, scheme="https"):
        """The Crawl-delay robots.txt asks of us on `host` (None if none)."""
        rp = self._parser("{0}://{1}/".format(scheme, host))
        return rp.crawl_delay(self.client.user_agent)

    def disallows_for_us(self, url):
        """Every Disallow pattern on `url`'s host whose group applies to OUR
        user agent: a group naming us (a token of our product name) or '*',
        read by both readers (Robots and star_rules). [] when none does.

        For hosts whose robots.txt singles out other agents (13 October
        2026: Santa Fe's SIEL names AI crawlers, ClaudeBot among them, and
        has no '*' group): a collector can stop the moment any rule covers
        us, not only when the URL it asks for is disallowed."""
        rp = self._parser(url)
        ua = self.client.user_agent
        found = [p for allow, p in getattr(rp, "star_rules", []) if not allow and p]
        for _agents, rules, _delay in rp._groups_for(ua):
            found += [p for allow, p in rules if not allow and p]
        return sorted(set(found))


class GuardedClient:
    """An HttpClient whose every request asks robots.txt first. Everything
    else (throttles, user_agent, raw_dir) passes through to the client."""

    def __init__(self, client, feed, log=print, exempt=(), budget=None, **robots_kwargs):
        self._client = client
        self.robots = RobotsGuard(client, feed, log=log, budget=budget, **robots_kwargs)
        # URL prefixes fetched with no robots.txt read (documented APIs).
        self.exempt = tuple(exempt or ())

    def __getattr__(self, name):
        return getattr(self._client, name)

    def check(self, url, feed=None, slug=""):
        if self.exempt and is_documented_api(url, self.exempt):
            return
        refused = self.robots.refusal(url)
        if refused:
            reason, host_skipped = refused
            raise RobotsRefused(url, feed or self.robots.feed, slug, reason, host_skipped)

    def allowed(self, url):
        if self.exempt and is_documented_api(url, self.exempt):
            return True
        return self.robots.refusal(url) is None

    def disallows_for_us(self, url):
        """RobotsGuard.disallows_for_us, or ['unreachable: <reason>'] when
        robots.txt could not be read (read as Disallow: / for the host)."""
        refused = self.robots.refusal(url)
        if refused and refused[1]:
            return ["unreachable: " + refused[0]]
        return self.robots.disallows_for_us(url)

    def crawl_delay(self, host):
        return self.robots.crawl_delay(host)

    def get_text(self, url, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.get_text(url, feed, slug, *args, **kwargs)

    def get_bytes(self, url, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.get_bytes(url, feed, slug, *args, **kwargs)

    def get_json(self, url, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.get_json(url, feed, slug, *args, **kwargs)

    def post_form(self, url, fields, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.post_form(url, fields, feed, slug, *args, **kwargs)

    def post_json(self, url, body, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.post_json(url, body, feed, slug, *args, **kwargs)




def guard(client, feed, log=print, budget=None):
    """The one-line wrap for the #144 collectors: every scraper request asks
    robots.txt, documented APIs (DOCUMENTED_APIS) pass straight through. A
    client that is already guarded is returned as it is."""
    if isinstance(client, GuardedClient):
        return client
    return GuardedClient(client, feed, log=log, exempt=DOCUMENTED_APIS, budget=budget)


_PROBE_GUARDS = {}


def probe_refusal(url, feed="robots-probe"):
    """For the urllib one-off scope probes (tools/nic_probe.py, ve_probe.py,
    ve_news_crawl.py), which have no HttpClient to wrap: None when robots.txt
    allows `url`, else the reason. robots.txt is read once per host per run,
    through an HttpClient (same UA), with the same rules as guard()."""
    if is_documented_api(url):
        return None
    if feed not in _PROBE_GUARDS:
        import os
        from src.http import HttpClient
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _PROBE_GUARDS[feed] = RobotsGuard(HttpClient(raw_dir=os.path.join(root, "data", "raw")),
                                          feed, log=lambda *a, **k: None)
    refused = _PROBE_GUARDS[feed].refusal(url)
    return refused[0] if refused else None
