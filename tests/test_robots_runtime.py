"""robots.txt asked at run time by the collectors #144 listed ("only the
scrapers", 12 October 2026): src/robots_guard.guard() and one representative
of each family (an agenda, a petition source, a roll-call collector, a
chamber collector), each for a disallowed path, a robots.txt answering 503
(host skipped) and one answering 404 (no rules). Documented APIs
(robots_guard.DOCUMENTED_APIS) pass straight through, robots.txt unread.
docs/robots-runtime.md has the classification."""

import gzip
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import chamber_store as cs  # noqa: E402
from src import db, drain  # noqa: E402
from src import robots_guard as rg  # noqa: E402
from src.agendas import it as it_agenda  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.petition_sources import fr as fr_petitions  # noqa: E402
from tests.robots_fakes import guarded_api  # noqa: E402

import gt_rollcalls as gtr  # noqa: E402
import hr_chamber  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")


def fixture(*parts):
    path = os.path.join(FIX, *parts)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return fh.read().decode("utf-8")


def quiet(*_a, **_k):
    return None


class Routes:
    """Serves fixtures by URL substring, records every URL asked; anything
    unknown is a 404."""

    def __init__(self, routes):
        self.routes = routes
        self.asked = []

    def _find(self, url, feed, slug):
        self.asked.append(url)
        for part in sorted(self.routes, key=len, reverse=True):
            if part in url:
                return self.routes[part]
        raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")

    def get_text(self, url, feed, slug, **kw):
        return self._find(url, feed, slug)

    def get_json(self, url, feed, slug, **kw):
        body = self._find(url, feed, slug)
        return json.loads(body) if isinstance(body, str) else body

    def get_bytes(self, url, feed, slug, **kw):
        return self._find(url, feed, slug)

    def enable_gzip(self, host):
        pass


class WrittenPermissionTests(unittest.TestCase):
    """robots_guard.PERMISSIONS (13 October 2026): a host's owner wrote that
    our targeted use of what its robots.txt refuses is welcome. Only the
    listed prefixes skip the robots.txt read; the rest of the host is asked."""

    REFUSE = "User-agent: *\nDisallow: /api/\n"
    BS = "https://data.bs.ch/api/explore/v2.1/catalog/datasets/"
    TG = "https://data.tg.ch/api/explore/v2.1/catalog/datasets/"

    def client(self, permissions=None):
        from tests.robots_fakes import RobotsServing
        serving = RobotsServing(Routes({"data.bs.ch": "[]", "data.tg.ch": "[]"}),
                                {"data.bs.ch": self.REFUSE, "data.tg.ch": self.REFUSE})
        return rg.GuardedClient(serving, "ch-cantons", log=quiet, permissions=permissions), serving

    def test_listed_prefixes_skip_the_robots_read(self):
        client, serving = self.client()
        self.assertEqual(client.get_json(self.BS + "100186/exports/json?where=x", "ch-cantons", "v"), [])
        self.assertEqual(client.get_json(self.TG + "sk-stat-136/exports/json?where=x", "ch-cantons",
                                         "v"), [])
        self.assertEqual(serving.robots_asked, [])
        self.assertTrue(client.allowed(self.BS + "100311/records"))

    def test_the_rest_of_the_host_is_still_asked_and_refused(self):
        client, serving = self.client()
        for url in (self.BS + "100307/exports/json", self.TG + "sk-stat-51/records",
                    "https://data.bs.ch/api/explore/v2.1/catalog/datasets"):
            with self.assertRaises(rg.RobotsRefused):
                client.get_json(url, "ch-cantons", "x")
        self.assertEqual(sorted(set(serving.robots_asked)), ["data.bs.ch", "data.tg.ch"])
        self.assertEqual(len(serving.inner.asked), 0, "a refused URL is never requested")

    def test_no_permission_no_skip(self):
        client, serving = self.client(permissions=())
        with self.assertRaises(rg.RobotsRefused):
            client.get_json(self.BS + "100186/exports/json", "ch-cantons", "v")
        self.assertEqual(serving.robots_asked, ["data.bs.ch"])

    def test_every_permission_is_dated_attributed_and_documented(self):
        doc = open(os.path.join(ROOT, "docs", "robots-runtime.md"), encoding="utf-8").read()
        self.assertIn("## Written permissions", doc)
        hosts = set()
        for p in rg.PERMISSIONS:
            self.assertRegex(p.date, r"^\d{4}-\d\d-\d\d$")
            self.assertTrue(p.granted_by and p.condition)
            self.assertTrue(p.docs.startswith("docs/robots-runtime.md#written-permissions"))
            for prefix in p.prefixes:
                # host and a dataset path: never a whole host or a whole /api/
                self.assertRegex(prefix, r"^https://[^/]+/api/explore/v2\.1/catalog/datasets/[^/]+/$")
                hosts.add(prefix.split("/")[2])
                self.assertIn(prefix.split("/datasets/")[1].rstrip("/"), doc)
        self.assertEqual(hosts, {"data.bs.ch", "data.tg.ch"})
        self.assertIn("Sie können sehr gerne die API benutzen", rg.PERMISSIONS[0].condition)
        self.assertIsNone(rg.probe_refusal(self.BS + "100311/records"))
        self.assertIsNotNone(rg.permission_for(self.TG + "sk-stat-140/exports/json"))
        self.assertIsNone(rg.permission_for(self.TG + "sk-stat-1400/exports/json"))


class GuardTests(unittest.TestCase):

    def test_a_documented_api_is_fetched_with_no_robots_read(self):
        inner = Routes({"api.sejm.gov.pl": "[]", "www.sejm.gov.pl": "<html/>"})
        client, serving = guarded_api(inner, {"api.sejm.gov.pl": 503, "www.sejm.gov.pl": 503},
                                      "pl-agenda")
        self.assertEqual(client.get_json("https://api.sejm.gov.pl/sejm/term10/proceedings",
                                         "pl-agenda", "p"), [])
        self.assertEqual(serving.robots_asked, [])
        # The website beside it is a scraper: asked, and here refused.
        with self.assertRaises(rg.RobotsRefused) as caught:
            client.get_text("https://www.sejm.gov.pl/sejm10.nsf/porzadek.xsp", "pl-agenda", "w")
        self.assertTrue(caught.exception.host_skipped)
        # A prompt 503 is asked twice (one retry, read_robots), then refused.
        self.assertEqual(serving.robots_asked, ["www.sejm.gov.pl", "www.sejm.gov.pl"])

    def test_an_api_prefix_exempts_only_its_paths(self):
        inner = Routes({"nrsr.sk": "{}"})
        client, serving = guarded_api(inner, {"www.nrsr.sk": "User-agent: *\nDisallow: /web/\n"},
                                      "sk-rollcalls")
        client.get_json("https://www.nrsr.sk/opendata/1/sk/MP", "sk-rollcalls", "mp")
        self.assertEqual(serving.robots_asked, [])
        with self.assertRaises(rg.RobotsRefused) as caught:
            client.get_text("https://www.nrsr.sk/web/Default.aspx?sid=schodze", "sk-rollcalls", "w")
        self.assertFalse(caught.exception.host_skipped)
        self.assertEqual(len(inner.asked), 1, "the refused page was never requested")

    def test_guard_is_idempotent_and_api_list_is_prefixes(self):
        client, _ = guarded_api(Routes({}), {}, "f")
        self.assertIs(rg.guard(client, "f"), client)
        for p in rg.DOCUMENTED_APIS:
            self.assertTrue(p.startswith("https://") and "/" in p[len("https://"):], p)
        self.assertTrue(rg.is_documented_api("https://ws.parlament.ch/odata.svc/Business"))
        self.assertFalse(rg.is_documented_api("https://www.parlament.ch/de/ratsbetrieb"))
        self.assertIsNone(rg.probe_refusal("https://api.sejm.gov.pl/sejm/term10"))

    def test_crawl_delay_raises_the_scraper_host_throttle(self):
        client, serving = guarded_api(Routes({"lachambre": "<html/>"}),
                                      {"www.lachambre.be": "User-agent: *\nCrawl-delay: 5\n"},
                                      "be-rollcalls")
        client.get_text("https://www.lachambre.be/kvvcr/index.cfm", "be-rollcalls", "x")
        self.assertEqual(serving.host_throttles.get("www.lachambre.be"), 5.0)

    def test_disallows_for_us_reads_only_groups_that_apply_to_us(self):
        # Santa Fe's SIEL (13 October 2026): groups for named AI agents only
        named = "User-agent: ClaudeBot\nDisallow: /\n\nUser-agent: GPTBot\nDisallow: /\n"
        cases = {named: [],
                 named + "\nUser-agent: *\nDisallow: /privado/\n": ["/privado/"],
                 named + "\nUser-agent: CitizenGO-ParlMonitor\nDisallow: /\n": ["/"],
                 "User-agent: *\nDisallow:\n": []}
        for text, want in cases.items():
            client, _ = guarded_api(Routes({}), {"siel.example.ar": text}, "f")
            self.assertEqual(client.disallows_for_us("https://siel.example.ar/"), want, text)
        client, _ = guarded_api(Routes({}), {"siel.example.ar": 503}, "f")
        self.assertTrue(client.disallows_for_us("https://siel.example.ar/")[0].startswith("unreachable"))


class AgendaTests(unittest.TestCase):
    """src/agendas/it.py: the Camera's calendar (camera.it, a website)."""

    def client(self, robots):
        inner = Routes({"/leg19/76": fixture("agenda", "it-index.html.gz"),
                        "calendari_assemblea": fixture("agenda", "it-calendario.html.gz")})
        client, serving = guarded_api(inner, {"www.camera.it": robots}, "country-agenda")
        return client, inner

    def test_disallowed_is_a_gap_and_never_fetched(self):
        client, inner = self.client("User-agent: *\nDisallow: /leg19/\n")
        got = it_agenda.fetch(client, "2026-10-12", 14, log=quiet)
        self.assertEqual(got.points, [])
        self.assertEqual(len(got.gaps), 1)
        self.assertIn("robots.txt disallows", got.gaps[0])
        self.assertEqual(inner.asked, [])

    def test_unreachable_robots_skips_the_host(self):
        client, inner = self.client(503)
        got = it_agenda.fetch(client, "2026-10-12", 14, log=quiet)
        self.assertEqual(got.points, [])
        self.assertIn("unreachable (503); host skipped", got.gaps[0])
        self.assertEqual(inner.asked, [])

    def test_no_robots_txt_reads_as_before(self):
        client, inner = self.client(404)
        got = it_agenda.fetch(client, "2026-10-12", 14, log=quiet)
        self.assertFalse(got.gaps)
        self.assertTrue(got.points)
        self.assertEqual(len(inner.asked), 2)


class PetitionTests(unittest.TestCase):
    """src/petition_sources/fr.py: the Assemblee's e-petition site."""

    HOST = "petitions.assemblee-nationale.fr"

    def run_with(self, robots):
        inner = Routes({self.HOST: fixture("petitions", "fr_an_list.html")})
        client, _ = guarded_api(inner, {self.HOST: robots}, "country-petitions")
        return fr_petitions.SOURCES[0].fetch(client, "2026-10-11"), inner

    def test_disallowed(self):
        got, inner = self.run_with("User-agent: *\nDisallow: /initiatives\n")
        self.assertEqual(got.entries, [])
        self.assertEqual(len(got.gaps), 1)
        self.assertIn("robots.txt disallows", got.gaps[0])
        self.assertEqual(inner.asked, [])

    def test_unreachable(self):
        got, inner = self.run_with(503)
        self.assertEqual(got.entries, [])
        self.assertIn("host skipped", got.gaps[0])
        self.assertEqual(inner.asked, [])

    def test_no_rules(self):
        got, inner = self.run_with(404)
        self.assertFalse(got.gaps)
        self.assertEqual(len(got.entries), 120)
        self.assertEqual(len(inner.asked), 20)


class RollcallTests(unittest.TestCase):
    """tools/gt_rollcalls.py: congreso.gob.gt's vote pages."""

    HOST = "www.congreso.gob.gt"

    def run_with(self, robots):
        conn = sqlite3.connect(":memory:")
        db.init_db(conn)
        inner = Routes({"votaciones_pleno": fixture("gt", "sessions.html.gz"),
                        "eventos_votaciones/41385": fixture("gt", "session-41385.html.gz"),
                        "detalle_de_votacion/51365/": fixture("gt", "vote-51365.html.gz")})
        client, _ = guarded_api(inner, {self.HOST: robots}, gtr.FEED)
        got = gtr.pull_votes(conn, client, "2026-09-09", since="2026-09-08", log=quiet)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='gt-rollcalls'")]
        return got, gaps, inner

    def test_disallowed(self):
        got, gaps, inner = self.run_with(
            "User-agent: *\nDisallow: /seccion_informacion_legislativa/\n")
        self.assertEqual(got, (0, 0, 0, 1))
        self.assertEqual(len(gaps), 1)
        self.assertIn("robots.txt disallows", gaps[0])
        self.assertEqual(inner.asked, [])

    def test_unreachable(self):
        got, gaps, inner = self.run_with(503)
        self.assertEqual(got, (0, 0, 0, 1))
        self.assertIn("unreachable (503); host skipped", gaps[0])
        self.assertEqual(inner.asked, [])

    def test_a_disallowed_vote_page_is_one_gap_the_rest_read(self):
        got, gaps, inner = self.run_with("User-agent: *\nDisallow: /detalle_de_votacion/51365/\n")
        read, stored, pages, n = got
        self.assertEqual((read, stored, pages), (1, 11, 0))
        self.assertTrue(any("robots.txt disallows" in g and "51365" in g for g in gaps))
        self.assertFalse(any("detalle_de_votacion/51365/" in u for u in inner.asked))

    def test_no_rules(self):
        got, gaps, inner = self.run_with(404)
        self.assertEqual(got[:3], (1, 11, 1))
        self.assertFalse(any("robots" in g for g in gaps))


class ChamberTests(unittest.TestCase):
    """tools/hr_chamber.py on the shared chamber layer: edoc.sabor.hr."""

    HOST = "edoc.sabor.hr"

    def run_with(self, robots):
        conn = db.init_db(db.connect(":memory:"))
        inner = Routes({"Fonogrami.aspx": "",
                        "FonogramView.aspx": fixture("hr", "fonogram-2017609-branitelji.html.gz")})
        client, _ = guarded_api(inner, {self.HOST: robots}, "chamber-store")
        run = cs.Run("hr", conn, client, "2026-10-11", "2026-09-01", drain.Budget(600),
                     cs.load_taxonomies("hr"), log=quiet)
        hr_chamber.speeches(run)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='hr-chamber'")]
        return run, gaps, inner

    def test_unreachable_is_one_gap_and_no_walk(self):
        run, gaps, inner = self.run_with(503)
        self.assertEqual(run.gaps, 1)
        self.assertIn("host skipped", gaps[0])
        self.assertEqual(inner.asked, [])

    def test_disallowed_transcripts_are_gaps_never_404s(self):
        run, gaps, inner = self.run_with("User-agent: *\nDisallow: /Views/\n")
        self.assertGreater(run.gaps, 0)
        self.assertTrue(all("robots.txt disallows" in g for g in gaps))
        self.assertFalse(any("FonogramView" in u for u in inner.asked))
        self.assertEqual(run.speeches, 0)

    def test_no_rules(self):
        run, gaps, inner = self.run_with(404)
        self.assertEqual(run.gaps, 0)
        self.assertTrue(any("FonogramView" in u for u in inner.asked))


class PatientReadTests(unittest.TestCase):
    """src/prov_fetch.read_robots ("patient robots.txt reads", 12 October
    2026): a slow robots.txt is waited for and retried, bounded per host,
    and a copy read in the last 24 hours stands in for an unreachable one.
    Fake client, fake clocks: no network, no real waits."""

    HOST = "www.congreso.es"
    PAGE = "https://www.congreso.es/es/agenda"

    class Clock:
        def __init__(self):
            self.t = 1000.0
            self.wall = 1_800_000_000.0

        def mono(self):
            return self.t

        def now(self):
            return self.wall

        def sleep(self, s):
            self.t += s

    class Script:
        """robots.txt answers from a script: text, an int status, or
        'timeout' (the fake clock moves on by the timeout asked)."""

        user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
        throttle = 1.0

        def __init__(self, clock, answers):
            self.clock = clock
            self.answers = list(answers)
            self.asked = []
            self.max_retries = 3
            self.retries_seen = []

        def get_text(self, url, feed, slug, timeout=None, **kw):
            import socket
            import urllib.error
            self.asked.append((url, timeout))
            self.retries_seen.append(self.max_retries)
            got = self.answers.pop(0) if self.answers else "timeout"
            if got == "timeout":
                self.clock.t += timeout
                raise FetchError(url, feed, slug, 1, socket.timeout("timed out"))
            self.clock.t += 0.5
            if isinstance(got, int):
                raise FetchError(url, feed, slug, 1,
                                 urllib.error.HTTPError(url, got, "status", {}, None))
            return got

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = os.path.join(self.tmp.name, "robots-cache")
        self.clock = self.Clock()
        self.logs = []

    def tearDown(self):
        self.tmp.cleanup()

    def guard(self, answers, budget=None):
        client = self.Script(self.clock, answers)
        g = rg.RobotsGuard(client, "es-agenda", log=self.logs.append, budget=budget,
                           robots_cache_dir=self.cache, robots_sleep=self.clock.sleep,
                           robots_clock=self.clock.mono, robots_now=self.clock.now)
        return g, client

    def test_timeout_then_success_on_retry_is_allowed(self):
        g, client = self.guard(["timeout", "User-agent: *\nDisallow: /private/\n"])
        self.assertIsNone(g.refusal(self.PAGE))
        self.assertEqual(len(client.asked), 2)
        self.assertEqual(client.asked[0][1], 45.0)
        self.assertEqual(client.retries_seen, [0, 0], "the client's own retries are off")
        self.assertEqual(client.max_retries, 3, "and restored after")
        self.assertEqual(g.gaps, [])
        self.assertTrue(any("retrying in 5s" in l for l in self.logs))
        self.assertTrue(any("read on attempt 2" in l for l in self.logs))
        # cached for the run: a second URL on the host asks nothing more
        self.assertIsNotNone(g.refusal("https://www.congreso.es/private/x"))
        self.assertEqual(len(client.asked), 2)

    def test_three_timeouts_disallow_with_a_gap_bounded(self):
        start = self.clock.t
        g, client = self.guard(["timeout"] * 5)
        reason, skipped = g.refusal(self.PAGE)
        self.assertTrue(skipped)
        self.assertIn("unreachable", reason)
        self.assertEqual(len(client.asked), 3)
        self.assertEqual(len(g.gaps), 1)
        self.assertLessEqual(self.clock.t - start, 150.0 + 1e-6)
        # third attempt's timeout shrank to the time left in the host budget
        self.assertLess(client.asked[2][1], 45.0)

    def test_collector_budget_is_respected(self):
        from src import drain
        budget = drain.Budget(50, clock=self.clock.mono)
        g, client = self.guard(["timeout"] * 5, budget=budget)
        self.assertTrue(g.refusal(self.PAGE)[1])
        self.assertLessEqual(budget.spent(), 50.0 + 1e-6)
        self.assertEqual(len(client.asked), 1, "no room for a retry inside 50 s")

    def test_prompt_503_disallows_after_one_retry(self):
        g, client = self.guard([503, 503, "User-agent: *\nAllow: /\n"])
        reason, skipped = g.refusal(self.PAGE)
        self.assertTrue(skipped)
        self.assertIn("503", reason)
        self.assertEqual(len(client.asked), 2, "a 5xx gets one retry, no more")

    def test_503_then_answer_is_allowed(self):
        g, client = self.guard([503, ""])
        self.assertIsNone(g.refusal(self.PAGE))

    def test_404_means_no_rules_at_once(self):
        g, client = self.guard([404])
        self.assertIsNone(g.refusal(self.PAGE))
        self.assertEqual(len(client.asked), 1)
        self.assertEqual(g.gaps, [])

    def _seed_cache(self, text, age_hours):
        from src import prov_fetch
        prov_fetch._save_cache(self.cache, "https", self.HOST, text, 200,
                               self.clock.wall - age_hours * 3600)

    def test_cached_copy_under_24h_used_when_unreachable(self):
        self._seed_cache("User-agent: *\nDisallow: /secret/\n", 23)
        g, client = self.guard(["timeout"] * 3)
        self.assertIsNone(g.refusal(self.PAGE))
        self.assertIsNotNone(g.refusal("https://www.congreso.es/secret/a"))
        self.assertEqual(g.gaps, [])
        self.assertTrue(any("using the copy read 23.0 h ago" in l for l in self.logs))

    def test_cached_copy_used_for_a_5xx_too(self):
        self._seed_cache("", 2)
        g, client = self.guard([503, 503])
        self.assertIsNone(g.refusal(self.PAGE))

    def test_cached_copy_over_24h_ignored(self):
        self._seed_cache("", 25)
        g, client = self.guard(["timeout"] * 3)
        self.assertTrue(g.refusal(self.PAGE)[1])
        self.assertEqual(len(g.gaps), 1)

    def test_a_good_read_is_saved_with_its_time(self):
        from src import prov_fetch
        g, client = self.guard(["User-agent: *\nDisallow: /x/\n"])
        g.refusal(self.PAGE)
        with open(prov_fetch.robots_cache_path(self.cache, "https", self.HOST)) as fh:
            saved = json.load(fh)
        self.assertEqual(saved["fetched_at"], self.clock.wall)
        self.assertIn("Disallow: /x/", saved["text"])

    def test_cache_dir_sits_beside_data_raw_only(self):
        from src import prov_fetch

        class C:
            raw_dir = "/srv/pm/data/raw"
        self.assertEqual(prov_fetch._cache_dir_for(C(), prov_fetch.AUTO),
                         "/srv/pm/data/robots-cache")
        self.assertIsNone(prov_fetch._cache_dir_for(object(), prov_fetch.AUTO))


if __name__ == "__main__":
    unittest.main()
