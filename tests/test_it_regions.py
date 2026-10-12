"""Italy's regional councils (IT3): tools/it_regions.py and the "Regional
councils" section of the Italian edition (src/editions/it.py).

Fixtures under tests/fixtures/it_regions/ are trimmed copies of the live
sources read on 12 October 2026: four rows of Lombardia's "CRL - Elenco PDL"
(dati.lombardia.it), entries of Trento's open-data XML (DDL, MOZ, ODG),
rows of Campania's list of proposte di legge and of the Marche council's
PdL index (Latin-1 bytes, as served). The legislature-XI row in
campania_p1.html is a copy of the XII row above it with its legislature and
id changed, to test the stop. No network.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce  # noqa: E402
from src import db, filter as filt, it_store  # noqa: E402
from src.editions import it as it_ed  # noqa: E402
from tools import it_regions as R  # noqa: E402
from tests.robots_fakes import RobotsServing  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "it_regions")
TAX = os.path.join(ROOT, "config", "taxonomy-it.yaml")


def fixture(name, mode="r"):
    with open(os.path.join(FIX, name), mode) as fh:
        return fh.read()


class FakeClient:
    """get_json / get_bytes / get_text from fixtures, by URL."""

    user_agent = "citizengo-parlmonitor/1.0 (+test)"
    throttle = 1.0

    def __init__(self, pages):
        self.pages = pages
        self.urls = []

    def _get(self, url):
        if url.endswith("/robots.txt"):
            # main() asks robots.txt first (src/robots_guard): none here.
            raise R.FetchError(url, "it-regions", "robots", 1,
                               urllib.error.HTTPError(url, 404, "Not Found", {}, None))
        self.urls.append(url)
        for prefix, body in self.pages:
            if url == prefix:
                return body
        raise R.FetchError(url, "it-regions", "test", 1, "no fixture")

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._get(url))

    def get_bytes(self, url, feed, slug, **kw):
        return self._get(url)

    def get_text(self, url, feed, slug, fallback_encoding=None, headers=None, **kw):
        body = self._get(url)
        if isinstance(body, bytes):
            try:
                return body.decode("utf-8")
            except UnicodeDecodeError:
                return body.decode(fallback_encoding or "latin-1")
        return body


def lombardia():
    return R.parse_lombardia(json.loads(fixture("lombardia.json")))


def by_key(acts):
    return {a["key"]: a for a in acts}


class LombardiaTests(unittest.TestCase):
    def test_keeps_bills_and_drops_reports(self):
        acts = by_key(lombardia())
        self.assertEqual(sorted(acts), ["lom/XII/pdl-127", "lom/XII/pdl-212", "lom/XII/plp-2"])

    def test_a_new_bill(self):
        a = by_key(lombardia())["lom/XII/pdl-212"]
        self.assertEqual(a["title"], "Disposizioni regionali per la preservazione della fertilità "
                                     "e per l’accesso alla crioconservazione delle cellule "
                                     "riproduttive")
        self.assertEqual(a["presented"], "2026-10-02")
        self.assertEqual(a["label"], "Progetto di legge n. 212/XII")
        self.assertEqual(a["initiative"], "Nicola DI MARCO and 2 other(s)")
        self.assertEqual(a["committee"], "III Commissione permanente - Sanità")
        # The latest dated stage: assigned to committee on 6 October.
        self.assertEqual(a["status_date"], "2026-10-06")
        self.assertEqual(a["status"], "Preso in carico da Commissioni")
        self.assertIsNone(a["law"])

    def test_an_enacted_bill_carries_its_law_and_vote(self):
        a = by_key(lombardia())["lom/XII/pdl-127"]
        self.assertEqual(a["law"], "l.r. 23/2026")
        self.assertEqual(a["status_date"], "2026-10-01")
        self.assertIn("Aula: approvato", a["status"])

    def test_the_query_names_the_legislature_and_the_kinds(self):
        url = R.lom_url()
        self.assertIn("legislatura%3D%27XII%27", url)
        for kind in ("Pdl", "Plp", "Pda", "Inp"):
            self.assertIn("%27{0}%27".format(kind), url)


class TrentoTests(unittest.TestCase):
    def test_bills_keyed_on_the_document_id(self):
        acts = R.parse_trento(fixture("trento_ddl.xml", "rb"), "DDL")
        self.assertEqual(len(acts), 3)
        a = acts[0]
        self.assertEqual(a["key"], "tn/XVII/at3009929")
        self.assertEqual(a["label"], "Disegno di legge n. 94/XVII di iniziativa consiliare")
        self.assertEqual(a["presented"], "2026-10-01")
        self.assertEqual(a["status"], "Presso la commissione competente")
        self.assertEqual(a["initiative"], "Biada Daniele")
        self.assertEqual(a["subject"], "Commercio")
        self.assertIn("attività commerciali", a["title"])

    def test_an_unnumbered_motion_is_kept(self):
        acts = R.parse_trento(fixture("trento_moz.xml", "rb"), "MOZ")
        first = acts[0]
        self.assertIsNone(first["number"])
        self.assertEqual(first["title"], "")
        self.assertTrue(first["key"].startswith("tn/XVII/at"))
        self.assertTrue(any("culle per la vita" in a["title"] for a in acts))

    def test_an_order_of_the_day_names_its_bill(self):
        acts = R.parse_trento(fixture("trento_odg.xml", "rb"), "ODG")
        self.assertTrue(acts)
        self.assertTrue(all("; on ddl n." in (a["subject"] or "") for a in acts))


class CampaniaTests(unittest.TestCase):
    def test_rows(self):
        acts = R.parse_campania(fixture("campania_p0.html"))
        self.assertEqual(len(acts), 3)
        a = acts[1]
        self.assertEqual(a["key"], "cam/XII/36028")
        self.assertEqual(a["presented"], "2026-09-30")
        self.assertEqual(a["number"], "76")
        self.assertEqual(a["title"], "Misure di prevenzione e contrasto al sovraindebitamento")
        self.assertEqual(a["initiative"], "LUCIA FORTINI, LUCA CASCONE, GENNARO OLIVIERO, "
                                          "GIOVANNI PORCELLI")
        self.assertEqual(a["url"], "https://www.cr.campania.it/leggi-progetti/proposte/"
                                   "dettaglio-documento?id=36028")

    def test_reading_stops_at_the_previous_legislature(self):
        client = FakeClient([(R.CAM_LIST, fixture("campania_p0.html")),
                             (R.CAM_LIST + "?page=1", fixture("campania_p1.html"))])
        acts, gaps = R.fetch_campania(client)
        self.assertEqual(gaps, 0)
        self.assertEqual(len(acts), 4)
        self.assertTrue(all(a["legislature"] == "XII" for a in acts))
        self.assertEqual(len(client.urls), 2)


def marche_page():
    """The fixture decoded as the collector's client decodes it (Latin-1 bytes)."""
    return FakeClient([("x", fixture("marche_p0.html", "rb"))]).get_text(
        "x", "f", "s", fallback_encoding="cp1252")


class MarcheTests(unittest.TestCase):
    def page(self):
        return marche_page()

    def test_rows(self):
        acts = by_key(R.parse_marche(self.page()))
        self.assertEqual(sorted(acts), ["mar/XII/pdl-30", "mar/XII/pdl-65", "mar/XII/pdl-72"])
        a = acts["mar/XII/pdl-72"]
        self.assertEqual(a["presented"], "2026-10-08")
        self.assertIn("sensibilità chimica", a["title"])
        self.assertIsNone(a["status"])

    def test_a_statutory_bill(self):
        a = by_key(R.parse_marche(self.page()))["mar/XII/pdl-65"]
        self.assertEqual(a["kind"], "PDLS")
        self.assertEqual(a["label"], "Proposta di legge statutaria n. 65/XII")
        self.assertEqual(a["presented"], "2026-07-01")

    def test_an_enacted_bill(self):
        a = by_key(R.parse_marche(self.page()))["mar/XII/pdl-30"]
        self.assertEqual(a["status"], "Legge n. 6 del 22/06/2026")
        self.assertEqual(a["law"], "l.r. 6/2026")

    def test_a_short_page_is_the_last(self):
        client = FakeClient([(R.MAR_LIST, fixture("marche_p0.html", "rb"))])
        acts, gaps = R.fetch_marche(client)
        self.assertEqual((len(acts), gaps), (3, 0))
        self.assertEqual(client.urls, [R.MAR_LIST])


def store():
    conn = sqlite3.connect(":memory:")
    it_store.ensure_schema(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS gaps (edition TEXT, feed TEXT, detail TEXT, "
                 "UNIQUE (edition, feed, detail))")
    return conn


@unittest.skipUnless(os.path.exists(TAX), "config/taxonomy-it.yaml is missing")
class StoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAX, country="it")
        cls.wl = R.empty_watchlist()

    def test_classified_by_the_italian_taxonomy(self):
        conn = store()
        R.store_all(conn, lombardia(), self.tax, self.wl, "2026-10-12")
        areas = json.loads(conn.execute("SELECT areas FROM it_reg_acts WHERE "
                                        "act_key='lom/XII/pdl-212'").fetchone()[0])
        self.assertIn(10, areas)
        acts = R.parse_trento(fixture("trento_ddl.xml", "rb"), "DDL")
        R.store_all(conn, acts, self.tax, self.wl, "2026-10-12")
        row = conn.execute("SELECT areas FROM it_reg_acts WHERE title LIKE "
                           "'%suicidio medicalmente assistito%'").fetchone()
        self.assertIn(2, json.loads(row[0]))

    def test_the_first_sighting_is_never_a_change(self):
        conn = store()
        acts = R.parse_trento(fixture("trento_ddl.xml", "rb"), "DDL")
        n, ours, new, moved = R.store_all(conn, acts, self.tax, self.wl, "2026-10-05")
        self.assertEqual((new, moved), (3, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM it_reg_acts WHERE status_date IS "
                                      "NOT NULL").fetchone()[0], 0)
        # Unchanged a week later: nothing moved.
        self.assertEqual(R.store_all(conn, acts, self.tax, self.wl, "2026-10-12")[3], 0)

    def test_a_changed_status_is_stamped_with_the_run_that_saw_it(self):
        conn = store()
        acts = R.parse_trento(fixture("trento_ddl.xml", "rb"), "DDL")
        R.store_all(conn, acts, self.tax, self.wl, "2026-10-05")
        acts[0]["status"] = "Approvato"
        self.assertEqual(R.store_all(conn, acts, self.tax, self.wl, "2026-10-12")[3], 1)
        row = conn.execute("SELECT status, status_date, status_seen, first_seen, last_seen FROM "
                           "it_reg_acts WHERE act_key=?", (acts[0]["key"],)).fetchone()
        self.assertEqual(row, ("Approvato", "2026-10-12", 1, "2026-10-05", "2026-10-12"))
        # The week after, unchanged: the stamp stays.
        R.store_all(conn, acts, self.tax, self.wl, "2026-10-19")
        self.assertEqual(conn.execute("SELECT status_date, status_seen FROM it_reg_acts WHERE "
                                      "act_key=?", (acts[0]["key"],)).fetchone(),
                         ("2026-10-12", 1))

    def test_a_dated_source_keeps_its_own_dates(self):
        conn = store()
        acts = lombardia()
        R.store_all(conn, acts, self.tax, self.wl, "2026-10-05")
        a = by_key(acts)["lom/XII/pdl-212"]
        a["status_date"], a["status"] = "2026-10-09", "Nominato Relatore"
        self.assertEqual(R.store_all(conn, acts, self.tax, self.wl, "2026-10-12")[3], 1)
        self.assertEqual(conn.execute("SELECT status_date, status_seen FROM it_reg_acts WHERE "
                                      "act_key='lom/XII/pdl-212'").fetchone(), ("2026-10-09", 0))

    def test_watched_by_key_in_the_regional_section(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "watchlist-it.yaml")
            with open(path, "w") as fh:
                fh.write('bills: {}\nregional:\n  "mar/XII/pdl-72": {areas: [9], why: "test"}\n')
            a = by_key(R.parse_marche(marche_page()))["mar/XII/pdl-72"]
            res = R.classify(self.tax, self.wl, a, watch_path=path)
        self.assertIn(9, res.issue_areas)
        self.assertIn("watch:mar/XII/pdl-72", res.watchlist_hits)

    def test_reclassify_is_offline(self):
        conn = store()
        R.store_all(conn, lombardia(), self.tax, self.wl, "2026-10-12")
        conn.execute("UPDATE it_reg_acts SET areas='[]', tier=NULL")
        R.reclassify(conn, self.tax)
        self.assertIn(10, json.loads(conn.execute(
            "SELECT areas FROM it_reg_acts WHERE act_key='lom/XII/pdl-212'").fetchone()[0]))


@unittest.skipUnless(os.path.exists(TAX), "config/taxonomy-it.yaml is missing")
class MainTests(unittest.TestCase):
    def test_a_council_that_fails_is_a_gap_not_the_run(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            client = FakeClient([(R.lom_url(), fixture("lombardia.json"))])
            orig = R.HttpClient
            R.HttpClient = lambda **kw: client
            try:
                rc = R.main(["--db", path, "--region", "lom", "mar"])
            finally:
                R.HttpClient = orig
            conn = sqlite3.connect(path)
            self.assertEqual(rc, 3)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM it_reg_acts").fetchone()[0], 3)
            gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='it-regions'")]
            self.assertEqual(len(gaps), 1)
            self.assertIn("Marche: not read", gaps[0])
            conn.close()


@unittest.skipUnless(os.path.exists(TAX), "config/taxonomy-it.yaml is missing")
class RobotsAtRunTime(unittest.TestCase):
    """robots.txt is asked on every run, before any request (src/robots_guard)."""

    def run_main(self, robots, regions=("lom", "cam")):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            inner = FakeClient([(R.lom_url(), fixture("lombardia.json")),
                                (R.CAM_LIST, fixture("campania_p0.html")),
                                (R.CAM_LIST + "?page=1", fixture("campania_p1.html"))])
            serving = RobotsServing(inner, robots)
            orig = R.HttpClient
            R.HttpClient = lambda **kw: serving
            try:
                rc = R.main(["--db", path, "--region"] + list(regions))
            finally:
                R.HttpClient = orig
            conn = sqlite3.connect(path)
            gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='it-regions'")]
            regions_stored = {r[0] for r in conn.execute("SELECT DISTINCT region FROM it_reg_acts")}
            conn.close()
            return rc, gaps, regions_stored, inner, serving

    def test_a_disallowed_path_is_skipped_with_a_gap(self):
        rc, gaps, stored, inner, _ = self.run_main(
            {"www.cr.campania.it": fixture("../robots/campania-disallow-leggi.txt")})
        self.assertEqual(rc, 3)
        self.assertEqual(stored, {"lom"})
        self.assertFalse(any("campania" in u for u in inner.urls))
        self.assertEqual(len(gaps), 1)
        self.assertIn("Campania: not read", gaps[0])
        self.assertIn("robots.txt disallows", gaps[0])

    def test_a_503_robots_txt_skips_the_host(self):
        rc, gaps, stored, inner, _ = self.run_main({"www.dati.lombardia.it": 503})
        self.assertEqual(rc, 3)
        self.assertEqual(stored, {"cam"})
        self.assertFalse(any("lombardia" in u for u in inner.urls))
        self.assertEqual(len(gaps), 1)
        self.assertIn("Lombardia: not read", gaps[0])
        self.assertIn("unreachable", gaps[0])

    def test_a_404_robots_txt_allows(self):
        rc, gaps, stored, inner, serving = self.run_main({})
        self.assertEqual((rc, gaps), (0, []))
        self.assertEqual(stored, {"lom", "cam"})
        self.assertEqual(sorted(set(serving.robots_asked)),
                         ["www.cr.campania.it", "www.dati.lombardia.it"])

    def test_robots_is_read_once_per_host_per_run(self):
        _, _, _, _, serving = self.run_main({"www.cr.campania.it": fixture("../robots/allow-us.txt")},
                                            regions=("cam",))
        self.assertEqual(serving.robots_asked, ["www.cr.campania.it"])


class SchemaTests(unittest.TestCase):
    def test_declared_and_created(self):
        self.assertIn("it_reg_acts", db.TABLES)
        self.assertIn("it_reg_acts", it_store.TABLES)
        conn = db.init_db(sqlite3.connect(":memory:"))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(it_reg_acts)")}
        self.assertTrue({"act_key", "region", "status_seen", "last_seen", "areas"} <= cols)
        it_store.ensure_schema(conn)   # idempotent


ACT = ("INSERT INTO it_reg_acts (act_key, region, kind, legislature, number, label, title, "
       "presented, status, status_date, status_seen, initiative, committee, law, url, areas, "
       "matched_terms, tier) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.conn.execute(ACT, ("lom/XII/pdl-212", "lom", "Pdl", "XII", "212",
                                "Progetto di legge n. 212/XII",
                                "Disposizioni regionali per la preservazione della fertilità e "
                                "per l'accesso alla crioconservazione delle cellule riproduttive",
                                "2026-10-02", "Preso in carico da Commissioni", "2026-10-06", 0,
                                "Nicola DI MARCO and 2 other(s)",
                                "III Commissione permanente - Sanità", None,
                                "https://example.org/212", "[10]", '["crioconservazione"]', 1))
        self.conn.execute(ACT, ("mar/XII/pdl-8", "mar", "PDL", "XII", "8",
                                "Proposta di legge n. 8/XII",
                                "Procedure e tempi per l'assistenza sanitaria regionale al "
                                "suicidio medicalmente assistito", "2025-11-21", "Respinta",
                                "2026-10-12", 1, "Mangialardi", None, None, None, "[2]",
                                '["suicidio medicalmente assistito"]', 1))
        self.conn.execute(ACT, ("cam/XII/1", "cam", "PDL", "XII", "1",
                                "Proposta di legge n. 1/XII", "Norme sul commercio",
                                "2026-10-08", None, None, 0, None, None, None, None, "[]", "[]",
                                None))
        self.conn.execute(ACT, ("tn/XVII/at1", "tn", "MOZ", "XVII", None, "Mozione n. /XVII",
                                "Culle per la vita", "2024-06-06", "Approvata", None, 0, None,
                                None, None, None, "[1]", '["culle per la vita"]', 2))
        self.dir = tempfile.mkdtemp()

    def render(self, since="2026-10-05"):
        return ce.render(self.conn, it_ed.COUNTRY, "2026-10-12", since=since, directory=self.dir)

    def test_the_section_shows_new_and_moved_acts_on_our_ground(self):
        text = self.render()
        self.assertIn("## Regional councils", text)
        section = text.split("## Regional councils", 1)[1]
        self.assertIn("### Lombardia", section)
        self.assertIn("lom/XII/pdl-212", section)
        self.assertIn("Progetto di legge n. 212/XII, Consiglio regionale, Lombardia", section)
        self.assertIn("### Marche", section)
        self.assertIn("**Stage move** · mar/XII/pdl-8", section)
        self.assertIn("status change seen by the weekly run of 12 October 2026", section)
        self.assertIn("Status: “Respinta”", section)
        # Off our ground, and outside the window.
        self.assertNotIn("cam/XII/1", section)
        self.assertNotIn("tn/XVII/at1", section)
        self.assertIn("2 regional item(s) on our ground", section)

    def test_quiet_national_week_still_gets_the_section_at_the_end(self):
        text = self.render()
        self.assertIn("A quiet week", text)
        self.assertNotIn("## Watchlist", text)
        self.assertGreater(text.index("## Regional councils"), text.index("A quiet week"))

    def test_the_window_is_the_editions_own(self):
        text = self.render(since="2026-10-10")
        section = text.split("## Regional councils", 1)[1]
        self.assertNotIn("lom/XII/pdl-212", section)   # presented 2 Oct, moved 6 Oct
        self.assertIn("mar/XII/pdl-8", section)

    def test_nothing_in_the_window(self):
        self.conn.execute("DELETE FROM it_reg_acts WHERE act_key IN ('lom/XII/pdl-212', "
                          "'mar/XII/pdl-8')")
        section = self.render().split("## Regional councils", 1)[1]
        self.assertIn("Nothing on our ground in the councils read", section)

    def test_before_the_watchlist_when_there_is_one(self):
        text = it_ed.post_render(self.conn, it_ed.COUNTRY, "2026-10-12",
                                 "_x. Edition 2, covering 6 October 2026 to 12 October 2026. "
                                 "Weekly._\n\n## Watchlist\n\nNone.\n", {})
        self.assertLess(text.index("## Regional councils"), text.index("## Watchlist"))

    def test_no_section_without_regional_acts(self):
        conn = sqlite3.connect(":memory:")
        it_store.ensure_schema(conn)
        self.assertEqual(it_ed.post_render(conn, it_ed.COUNTRY, "2026-10-12", "text", {}), "text")
        bare = sqlite3.connect(":memory:")
        self.assertEqual(it_ed.post_render(bare, it_ed.COUNTRY, "2026-10-12", "text", {}), "text")

    def test_coverage_names_the_councils(self):
        line = next(c for c in it_ed.COUNTRY.coverage if "IT3" in c)
        for name in ("Lombardia", "Campania", "Marche", "Trento"):
            self.assertIn(name, line)


if __name__ == "__main__":
    unittest.main()
