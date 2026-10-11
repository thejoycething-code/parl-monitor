"""The rest of the week ahead (11 October 2026): Belgium (the Chamber's
eMeeting agendas), Portugal (the Agenda Parlamentar), Slovakia (the
programme of a convened sitting), the Sejm's committee sittings, and the
Spanish plenary's order of the day read from its PDF. Fixtures saved from
the live sources on 11 October 2026 (tests/fixtures/agenda/)."""
import gzip
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import agenda, db  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src import noise  # noqa: E402
from src.agendas import be, es, pl, pt, sk  # noqa: E402
from tests.test_country_agenda import FakeClient  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "agenda")


def text(name):
    with gzip.open(os.path.join(FIX, name), "rt", encoding="utf-8") as fh:
        return fh.read()


def js(name):
    return json.loads(text(name))


def pdf(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


MEETING = {"id": "329669877", "organ": "plen", "date": "2026-10-08", "time": "14:15",
           "number": "1", "nl": "Plenum", "fr": "Plénière"}


class Belgium(unittest.TestCase):
    def test_calendar_lists_the_weeks_meetings(self):
        got = be.parse_calendar(text("be-week-2026-42.xml.gz"))
        self.assertEqual(len(got), 11)
        self.assertEqual(got[0]["organ"], "plen")
        self.assertEqual((got[0]["date"], got[0]["time"]), ("2026-10-13", "14:15"))
        self.assertEqual(be.weeks("2026-10-11", 21)[:2], [(2026, 41), (2026, 42)])

    def test_plenary_items_carry_dossier_keys_and_lists_split(self):
        pts = be.parse_agenda(text("be-plen-2026-10-08.xml.gz"), MEETING)
        euth = next(p for p in pts if "56/1338" in p["refs"])
        self.assertEqual(euth["kind"], "plenary")
        self.assertIn("rouwverlof", euth["title"])
        self.assertIn("euthanasie programmée", euth["detail"])      # the French beside it
        self.assertEqual(euth["status"], "Wetsontwerpen en wetsvoorstel")
        # the prises en considération: one point per dossier
        listed = [p for p in pts if p["status"] and p["status"].startswith("Inoverweging")]
        self.assertGreater(len(listed), 5)
        self.assertTrue(all(len(p["refs"]) == 1 for p in listed))

    def test_committee_meeting(self):
        m = dict(MEETING, organ="comm_K221", date="2026-10-14", nl="Commissie voor Binnenlandse Zaken")
        pts = be.parse_agenda(text("be-k221-2026-10-14.xml.gz"), m)
        self.assertEqual([p["refs"] for p in pts], [["56/1665"], ["56/1754"]])
        self.assertEqual({p["kind"] for p in pts}, {"committee"})
        self.assertIn("organ=comm_K221", pts[0]["url"])

    def test_collect_matches_the_watched_dossier_without_a_tier_column(self):
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO be_dossiers (dossier_key, legislature, number, title_nl, areas) "
                     "VALUES ('56/1338', 56, 1338, 'rouwverlof bij euthanasie', '[2]')")
        client = FakeClient({"week/2026/41/": "<calendar/>",
                             "week/2026/42/": text("be-week-2026-42.xml.gz"),
                             "week/2026/43/": "<calendar/>", "week/2026/44/": "<calendar/>",
                             "plen/final/2026-10-14": text("be-plen-2026-10-08.xml.gz"),
                             "comm_K221/final/2026-10-14": text("be-k221-2026-10-14.xml.gz"),
                             "/agenda.xml": "<meeting><agenda/></meeting>"})
        n, ours, gaps = agenda.collect(conn, "be", client, "2026-10-11", log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertFalse(any("comm_PRES" in u or "comm_BUR" in u for u in client.asked))
        r = conn.execute("SELECT * FROM country_agenda WHERE cc='be' AND refs LIKE '%56/1338%'"
                         ).fetchone()
        self.assertEqual(json.loads(r["bill_keys"]), ["56/1338"])
        self.assertIn(2, json.loads(r["areas"]))
        self.assertIn("56/1338", json.loads(r["watch_keys"]))
        self.assertEqual(agenda.latest_run(conn, "be")[4], "2026-10-13")


class Portugal(unittest.TestCase):
    def test_plenary_items_with_initiative_keys(self):
        evs = js("pt-calendar-s4.json.gz")
        pts = [p for e in evs for p in pt.parse_event(e, "plenary")]
        pma = next(p for p in pts if "XVII/J/623" in p["refs"])
        self.assertEqual(pma["date"], "2026-10-15")
        self.assertIn("Procriação Medicamente Assistida", pma["title"])
        self.assertIn("XVII/R/727", pma["refs"])
        self.assertTrue(any(r.startswith("bid:") for r in pma["refs"]))
        self.assertEqual(pma["body"], "Plenário Reunião n.º 12")
        budget = [p for p in pts if "XVII/P/110" in p["refs"]]
        self.assertTrue(budget)
        # the speaking-time tables are not kept
        self.assertFalse(any(" 6 m " in (p["detail"] or "") for p in pts))

    def test_committee_item_carries_the_watched_bill(self):
        evs = js("pt-calendar-s7.json.gz")
        pts = [p for e in evs for p in pt.parse_event(e, "committee")]
        self.assertTrue(any("XVII/J/479" in p["refs"] for p in pts))
        self.assertEqual({p["kind"] for p in pts}, {"committee"})

    def test_refs_and_resolve(self):
        self.assertEqual(pt.refs_of("Proposta de Lei n.º 110/XVII/2.ª (GOV) [[BID=377352]]"),
                         ["XVII/P/110", "bid:377352"])
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.execute("INSERT INTO pt_initiatives (ini_key, ini_id, legislature, ini_type, number) "
                     "VALUES ('XVII/J/623', 356395, 'XVII', 'J', 623)")
        self.assertEqual(pt.resolve(conn, ["bid:356395", "XVII/J/1"]), ["XVII/J/623"])

    def test_classified_on_our_ground(self):
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        client = FakeClient({"SectionId=4": js("pt-calendar-s4.json.gz"),
                             "SectionId=1": [], "SectionId=7": js("pt-calendar-s7.json.gz")})
        n, ours, gaps = agenda.collect(conn, "pt", client, "2026-10-11", log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertGreater(ours, 0)
        watched = conn.execute("SELECT * FROM country_agenda WHERE cc='pt' AND watch_keys "
                               "LIKE '%XVII/J/479%'").fetchone()
        self.assertIsNotNone(watched)
        self.assertEqual(agenda.latest_run(conn, "pt")[4], "2026-10-14")


class Slovakia(unittest.TestCase):
    def test_nothing_convened_says_so(self):
        client = FakeClient({"General/Meetings": js("sk-meetings.json.gz")})
        got = sk.fetch(client, "2026-10-11", 21)
        self.assertEqual(got.points, [])
        self.assertIn("No sitting is convened", got.note)

    def test_an_open_sitting_is_read_with_its_prints(self):
        client = FakeClient({"General/Meetings": js("sk-meetings.json.gz"),
                             "MeetingProgram": js("sk-program-61.json.gz")})
        got = sk.fetch(client, "2026-09-20", 21)
        self.assertEqual(got.next_sitting, "2026-09-20")
        bill = next(p for p in got.points if p["refs"] == ["9/1324"])
        self.assertEqual(bill["date"], "2026-09-20")
        self.assertIn("open since 2026-09-15", bill["body"])
        self.assertIn("druhé čítanie", bill["title"])
        standing = [p for p in got.points if p["status"] == "Standing item"]
        self.assertTrue(standing)


class PolandCommittees(unittest.TestCase):
    def test_committee_day_with_prints_and_names(self):
        names = pl.committee_names(js("pl-committees.json.gz"))
        self.assertEqual(names["ASW"], "Komisja Administracji i Spraw Wewnętrznych")
        pts = pl.parse_committee_day(js("pl-committees-2026-10-08.json.gz"), names)
        self.assertEqual(len(pts), 35)
        ab = next(p for p in pts if "10/223" in p["refs"])
        self.assertEqual(ab["kind"], "committee")
        self.assertTrue(ab["body"].startswith("Komisja Nadzwyczajna"))
        self.assertTrue(ab["item_id"].startswith("kom-"))

    def test_fetch_adds_committees_to_the_plenary(self):
        from tests.test_country_agenda import js as js_old
        client = FakeClient({"proceedings": js_old("pl-proceedings.json.gz"),
                             "committees/sittings/2026-10-20":
                                 js("pl-committees-2026-10-08.json.gz")[:2],
                             "committees/sittings/": [],
                             "committees": js("pl-committees.json.gz")})
        got = pl.fetch(client, "2026-10-10", 21)
        kinds = {p["kind"] for p in got.points}
        self.assertEqual(kinds, {"plenary", "committee"})
        self.assertEqual(got.gaps, [])


class SpainOrderOfTheDay(unittest.TestCase):
    def test_pdf_items_dated_and_keyed(self):
        text_ = es.pdf_text(pdf("es-pleno-197.pdf"))
        pts = es.parse_order(text_, "u", "2026-09-15")
        self.assertEqual(len(pts), 34)
        first = pts[0]
        self.assertEqual((first["date"], first["refs"]), ("2026-09-15", ["15/122/000012"]))
        self.assertTrue(first["status"].startswith("Toma en consideración"))
        self.assertTrue(any(p["date"] == "2026-09-16" for p in pts))
        self.assertTrue(any("acompañados" in p["title"] for p in pts))     # rejoined

    def test_order_replaces_the_weekly_row(self):
        from tests.test_country_agenda import text as text_old
        week = es.parse_week(text_old("es-semana-2026-09-14.html.gz"))
        rows = [p for p in week if p.get("pdf")]
        self.assertTrue(rows)
        client = FakeClient({"orden_dia": pdf("es-pleno-197.pdf")})
        got, gaps = es.read_orders(client, week)
        self.assertEqual(gaps, [])
        self.assertFalse(any(p.get("pdf") and "197" in p["pdf"] for p in got))
        self.assertTrue(any(p["item_id"] == "pleno-197-1" for p in got))


class Editions(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def test_belgian_edition_shows_the_week_ahead(self):
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        client = FakeClient({"week/2026/42/": text("be-week-2026-42.xml.gz"),
                             "week/": "<calendar/>",
                             "plen/final/2026-10-14": text("be-plen-2026-10-08.xml.gz"),
                             "/agenda.xml": "<meeting><agenda/></meeting>"})
        agenda.collect(conn, "be", client, "2026-10-11", log=lambda *a: None)
        out = ce.render(conn, ce.adapter("be"), "2026-10-12", "2026-10-05", directory=self.tmp)
        self.assertIn("## Week ahead", out)
        self.assertIn("56/1338", out)
        self.assertIn("Week ahead (the Chamber's eMeeting agenda service): read", out)
        self.assertNotIn("—", out)

    def test_adapters_carry_the_hooks(self):
        for cc in ("be", "pt", "sk"):
            a = ce.adapter(cc)
            self.assertIsNotNone(a.week_ahead, cc)
            self.assertIsNotNone(a.ahead_note, cc)


if __name__ == "__main__":
    unittest.main()
