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
        self.assertEqual(serving.robots_asked, ["www.sejm.gov.pl"])

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


if __name__ == "__main__":
    unittest.main()
