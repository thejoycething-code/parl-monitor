"""Regional forward agendas: the shared table, store and collector
(src/regional_agenda.py, tools/regional_agenda.py). No network.

FakeClient and load_fixture are shared by the per-country tests
(tests/test_regional_agenda_<cc>.py)."""
import gzip
import json
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, regional_agenda as ra  # noqa: E402
from src.http import FetchError, RobotsRefused  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "regional_agenda")


def load_fixture(cc, name):
    """A trimmed live capture under tests/fixtures/regional_agenda/<cc>/
    (a .gz is read transparently)."""
    path = os.path.join(FIX, cc, name)
    if name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return fh.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    """URL -> text (or a dict/list for get_json, or bytes for get_bytes).
    A URL not in the map raises FetchError, as a dead host would; a value
    that is an Exception instance is raised."""

    def __init__(self, pages):
        self.pages = dict(pages)
        self.asked = []

    def _get(self, url, feed, slug):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 503: Service Unavailable")
        v = self.pages[url]
        if isinstance(v, Exception):
            raise v
        return v

    def get_text(self, url, feed, slug, **kw):
        v = self._get(url, feed, slug)
        return v.decode("utf-8") if isinstance(v, bytes) else v

    def get_bytes(self, url, feed, slug, **kw):
        v = self._get(url, feed, slug)
        return v if isinstance(v, bytes) else str(v).encode("utf-8")

    def get_json(self, url, feed, slug, **kw):
        v = self._get(url, feed, slug)
        return json.loads(v) if isinstance(v, (str, bytes)) else v

    def post_form(self, url, fields, feed, slug, **kw):
        return self.get_text(url, feed, slug)

    def post_json(self, url, body, feed, slug, **kw):
        return self.get_json(url, feed, slug)


def store():
    return db.init_db(db.connect(":memory:"))


def fake_module(regions, taxonomies=(("taxonomy-de.yaml", "de"),)):
    m = types.SimpleNamespace(CC="xx", TAXONOMIES=taxonomies, REGIONS=regions)
    return m


class CoreTest(unittest.TestCase):
    def test_tables_declared(self):
        for t in ("regional_agenda", "regional_agenda_runs"):
            self.assertIn(t, db.TABLES)

    def test_item_types(self):
        self.assertEqual(ra.item_type(""), ra.TBA)
        self.assertEqual(ra.item_type("Fragestunde"), "questions")
        self.assertEqual(ra.item_type("Zweite Lesung: Gesetz zur Änderung des Schulgesetzes"),
                         "bill stage")
        self.assertEqual(ra.item_type("Proposición no de ley sobre la familia"), "motion")
        self.assertEqual(ra.item_type("Bill 12, Second Reading"), "bill stage")
        self.assertEqual(ra.item_type("Projet de décret relatif à l'enseignement"), "bill stage")
        self.assertEqual(ra.item_type("Aprobación, si procede, del acta de la sesión anterior"),
                         "procedural")
        self.assertEqual(ra.item_type("Something else", committee=True), "committee business")
        # 16 October 2026, from the Spanish build: motion beats the
        # interpellation it follows; appearances are evidence; Catalan.
        self.assertEqual(ra.item_type("Debate y votación de la moción N.º 186, subsiguiente "
                                      "a la Interpelación"), "motion")
        self.assertEqual(ra.item_type("Comparecencia, a petición propia, del consejero"),
                         "committee evidence")
        self.assertEqual(ra.item_type("Proposició de llei de l'escola inclusiva"), "bill stage")
        self.assertEqual(ra.item_type("Pregunta al Govern sobre la sanitat"), "questions")
        self.assertEqual(ra.item_type("Petición de la asociación de familias"), "petition")

    def test_find_date(self):
        self.assertEqual(ra.find_date("Sitzung am 22.10.2026, 10 Uhr"), "2026-10-22")
        self.assertEqual(ra.find_date("jeudi 22 octobre 2026"), "2026-10-22")
        self.assertEqual(ra.find_date("martes, 20 de octubre de 2026"), "2026-10-20")
        self.assertEqual(ra.find_date("Tuesday, October 20, 2026"), "2026-10-20")
        self.assertEqual(ra.find_date("10/20/2026", numeric_order="mdy"), "2026-10-20")

    def _run(self, regions, conn=None, today="2026-10-16", client=None):
        conn = conn or store()
        logs = []
        s = ra.collect(conn, "xx", client or FakeClient({}), today, days=28,
                       mod=fake_module(regions), log=logs.append)
        return conn, s, logs

    def test_store_classify_tba_and_replace(self):
        first = [ra.item("2026-10-21", "Gesetz zur Sterbehilfe", "Plenum", meeting_id="m1",
                         reference="Drs. 19/1"),
                 ra.item("2026-10-21", "Fragestunde", "Plenum", meeting_id="m1"),
                 ra.item("2026-11-04", "", "Plenum", meeting_id="m2")]

        def reader1(client, ctx):
            return ra.RegionRead(first, [ra.window(ctx.today, ctx.until)], source="test")
        conn, s, logs = self._run({"BY": ra.region("Bayern", reader1),
                                   "HB": ra.region("Bremen", status="no-route",
                                                   note="PDF scans only")})
        rows = {r["business"]: dict(r) for r in conn.execute("SELECT * FROM regional_agenda")}
        self.assertEqual(len(rows), 3)
        self.assertTrue(json.loads(rows["Gesetz zur Sterbehilfe"]["areas"]))
        self.assertEqual(rows["Gesetz zur Sterbehilfe"]["item_type"], "bill stage")
        tba = [r for r in rows.values() if r["item_type"] == ra.TBA]
        self.assertEqual(len(tba), 1)
        self.assertEqual(s["read"], ["BY"])
        self.assertEqual(s["no-route"], ["HB"])
        runs = {r["region"]: r["status"] for r in conn.execute("SELECT * FROM regional_agenda_runs")}
        self.assertEqual(runs, {"BY": "read", "HB": "no-route"})

        # Re-read: the placeholder now has business; the question time moved off.
        second = [ra.item("2026-10-21", "Gesetz zur Sterbehilfe", "Plenum", meeting_id="m1"),
                  ra.item("2026-11-04", "Antrag: Schutz des ungeborenen Lebens", "Plenum",
                          meeting_id="m2")]

        def reader2(client, ctx):
            return ra.RegionRead(second, [ra.window(ctx.today, ctx.until)], source="test")
        conn, s, _ = self._run({"BY": ra.region("Bayern", reader2)}, conn=conn,
                               today="2026-10-17")
        rows = {r["business"]: dict(r) for r in conn.execute("SELECT * FROM regional_agenda")}
        self.assertEqual(set(rows), {"Gesetz zur Sterbehilfe",
                                     "Antrag: Schutz des ungeborenen Lebens"})
        self.assertEqual(rows["Gesetz zur Sterbehilfe"]["first_seen"], "2026-10-16")
        self.assertEqual(rows["Gesetz zur Sterbehilfe"]["last_seen"], "2026-10-17")
        self.assertEqual(s["pruned"], 2)

    def test_failed_region_keeps_rows_and_records_gap(self):
        def ok(client, ctx):
            return ra.RegionRead([ra.item("2026-10-20", "Schulgesetz", "Plenum")],
                                 [ra.window(ctx.today, ctx.until)])
        conn, _, _ = self._run({"BY": ra.region("Bayern", ok)})

        def broken(client, ctx):
            raise FetchError("https://x", "f", "s", 3, "HTTP Error 500")

        def refused(client, ctx):
            raise RobotsRefused("https://y/z", "f", "s", "robots.txt disallows /z")
        conn, s, _ = self._run({"BY": ra.region("Bayern", broken),
                                "BE": ra.region("Berlin", refused)}, conn=conn,
                               today="2026-10-17")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], 1)
        self.assertEqual(s["gap"], ["BY"])
        self.assertEqual(s["blocked"], ["BE"])
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='xx-regional-agenda'")]
        self.assertEqual(len(gaps), 2)
        self.assertTrue(any("stored rows kept" in g for g in gaps))

    def test_unreadable_robots_is_a_gap_not_a_block(self):
        def down(client, ctx):
            raise RobotsRefused("https://y/z", "f", "s", "robots.txt unreachable: timed out",
                                host_skipped=True)
        _, s, _ = self._run({"BA": ra.region("Buenos Aires", down)})
        self.assertEqual(s["gap"], ["BA"])
        self.assertEqual(s["blocked"], [])

    def test_dates_in_more_languages(self):
        self.assertEqual(ra.find_date("sesja 27 października 2026 r."), "2026-10-27")
        self.assertEqual(ra.find_date("22 de octubre del 2026"), "2026-10-22")
        self.assertEqual(ra.find_date("dijous 22 d'octubre de 2026"), "2026-10-22")

    def test_meeting_unit_only_prunes_that_meeting(self):
        def r1(client, ctx):
            return ra.RegionRead([ra.item("2026-10-20", "A item", "Ausschuss", meeting_id="a"),
                                  ra.item("2026-10-21", "B item", "Ausschuss", meeting_id="b")],
                                 [ra.meeting("a"), ra.meeting("b")])
        conn, _, _ = self._run({"BY": ra.region("Bayern", r1)})

        def r2(client, ctx):
            return ra.RegionRead([ra.item("2026-10-20", "A2 item", "Ausschuss", meeting_id="a")],
                                 [ra.meeting("a")])
        conn, _, _ = self._run({"BY": ra.region("Bayern", r2)}, conn=conn, today="2026-10-17")
        got = sorted(r[0] for r in conn.execute("SELECT business FROM regional_agenda"))
        self.assertEqual(got, ["A2 item", "B item"])

    def test_window_for_one_body(self):
        def r1(client, ctx):
            return ra.RegionRead([ra.item("2026-10-20", "Old LA item", "Assembly"),
                                  ra.item("2026-10-20", "Old LC item", "Council")],
                                 [ra.window(ctx.today, ctx.until)])
        conn, _, _ = self._run({"SA": ra.region("South Australia", r1)})

        def r2(client, ctx):
            return ra.RegionRead([ra.item("2026-10-21", "New LA item", "Assembly")],
                                 [ra.window(ctx.today, ctx.until, "Assembly")])
        conn, _, _ = self._run({"SA": ra.region("South Australia", r2)}, conn=conn,
                               today="2026-10-17")
        got = sorted(r[0] for r in conn.execute("SELECT business FROM regional_agenda"))
        self.assertEqual(got, ["New LA item", "Old LC item"])

    def test_region_language_override(self):
        def r(client, ctx):
            return ra.RegionRead([ra.item("2026-10-20", "Projet de loi sur l'aide au suicide",
                                          "Grand Conseil")], [])
        mod = fake_module({"GE": ra.region("Genève", r, langs=["taxonomy-fr.yaml"])},
                          taxonomies=(("taxonomy-atch.yaml", "ch"),))
        conn = store()
        ra.collect(conn, "xx", FakeClient({}), "2026-10-16", mod=mod, log=lambda *a: None)
        row = conn.execute("SELECT areas, lang FROM regional_agenda").fetchone()
        self.assertEqual(row["lang"], "taxonomy-fr.yaml")
        self.assertTrue(json.loads(row["areas"]))


class ModulesTest(unittest.TestCase):
    """Every country module that exists declares its regions properly."""

    def test_modules_shape(self):
        for cc in ra.COUNTRIES:
            try:
                mod = ra.module(cc)
            except ImportError:
                continue
            self.assertEqual(mod.CC, cc)
            self.assertTrue(mod.TAXONOMIES)
            for name, _ in mod.TAXONOMIES:
                self.assertTrue(os.path.exists(os.path.join(ROOT, "config", name)), name)
            self.assertTrue(mod.REGIONS)
            for code, reg in mod.REGIONS.items():
                self.assertTrue(reg.name, (cc, code))
                if reg.reader is None:
                    self.assertIn(reg.status, ("no-route", "blocked"), (cc, code))
                    self.assertTrue(reg.note, (cc, code))
                for lang in reg.langs or ():
                    name = lang if isinstance(lang, str) else lang[0]
                    self.assertTrue(os.path.exists(os.path.join(ROOT, "config", name)), name)


if __name__ == "__main__":
    unittest.main()
