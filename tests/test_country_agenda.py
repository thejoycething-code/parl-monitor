"""The week ahead for the country editions (src/agenda.py, src/agendas/,
tools/country_agenda.py): each source's parser on replies saved on 9 and
10 October 2026 (tests/fixtures/agenda/), matching to bills by key, the
store, and the edition's week-ahead section and Coverage line."""
import gzip
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import agenda, db  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src import noise  # noqa: E402
from src.agendas import ar, at, br, ch, es, fr, it, nl, pl  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "agenda")


def text(name):
    with gzip.open(os.path.join(FIX, name), "rt", encoding="utf-8") as fh:
        return fh.read()


def js(name):
    return json.loads(text(name))


class FakeClient:
    """Serves fixtures by URL substring; records what was asked."""

    def __init__(self, routes, raw_dir=None):
        self.routes = routes
        self.asked = []
        self.raw_dir = raw_dir or tempfile.mkdtemp()
        self.archive_date = None
        self.user_agent = "test"

    def _find(self, url):
        self.asked.append(url)
        for part, value in self.routes.items():
            if part in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError("unexpected URL " + url)

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        return self._find(url)

    def get_text(self, url, feed, slug, timeout=None, archive=True, fallback_encoding=None,
                 headers=None):
        return self._find(url)

    def get_bytes(self, url, feed, slug, timeout=None, **kw):
        return self._find(url)

    def post_json(self, url, body, feed, slug, headers=None, timeout=None):
        return self._find(url)


class Parsers(unittest.TestCase):
    def test_nl_points_carry_zaak_and_dossier_keys(self):
        pts = nl.parse(js("nl-activiteit.json.gz"))
        self.assertTrue(pts)
        # the petition sessions were moved ('Verplaatst'): left out, as cancelled ones are
        self.assertFalse(any("Zwanger voor een Ander" in p["title"] for p in pts))
        visit = next(p for p in pts if "femicide" in p["title"])
        self.assertEqual((visit["date"], visit["kind"]), ("2026-10-19", "committee"))
        self.assertTrue(visit["item_id"].startswith("2026"))      # the portal's Nummer
        donor = next(p for p in pts if "spermadonor" in p["title"])
        self.assertEqual(donor["refs"], ["2026Z20082"])
        self.assertTrue(any(q["kind"] == "plenary" and q["body"] == "Plenary" for q in pts))
        for q in pts:
            self.assertIn(q["kind"], ("plenary", "committee", "hearing"))

    def test_nl_dossier_key(self):
        self.assertEqual(nl.dossier_key({"Nummer": 36800, "Toevoeging": "XVI"}), "36800-XVI")
        self.assertEqual(nl.dossier_key({"Nummer": 36390, "Toevoeging": None}), "36390")

    def test_pl_agenda_points_prints_and_planned_sittings(self):
        reply = js("pl-proceedings.json.gz")
        pts, nxt = pl.parse(reply, "2026-10-10")
        self.assertEqual(nxt, "2026-10-20")
        self.assertEqual(len(pts), 41)
        first = pts[0]
        self.assertEqual(first["date"], "2026-10-20")
        self.assertEqual(first["refs"], ["10/3086", "10/3183"])
        self.assertNotIn("sprawozdawca", first["title"])
        abortion = next(p for p in pts if "10/223" in p["refs"])
        self.assertIn("przerywania ciąży", abortion["title"])
        self.assertEqual(abortion["status"], "May be added to the agenda")
        # planned sittings (number 0) carry no agenda, only a date
        _, later = pl.parse(reply, "2026-10-24")
        self.assertEqual(later, "2026-11-05")

    def test_ch_subjects_and_business_numbers(self):
        pts = ch.parse(js("ch-meetings.json.gz"))
        self.assertTrue(pts)
        p = next(p for p in pts if p["refs"] == ["19.320"])
        self.assertEqual((p["date"], p["time"]), ("2026-10-02", "08:00"))
        self.assertEqual(p["body"], "Nationalrat, Herbstsession 2026")
        self.assertEqual(p["status"], "Abschreibung - Classement")
        self.assertEqual(ch.odata_date("/Date(1790899200000)/"), "2026-10-02")

    def test_br_camara_pauta_and_senado(self):
        events = br.parse_events(js("br-eventos.json.gz"))
        ev = next(e for e in events if e["id"] == 83037)
        self.assertTrue(br.deliberative(ev))
        pts = br.parse_pauta(ev, js("br-pauta-83037.json.gz"))
        self.assertTrue(pts)
        self.assertIn("PL 2665/2022", pts[0]["refs"])
        self.assertEqual(pts[0]["kind"], "committee")
        sen, sittings = br.parse_senado(js("br-senado.json.gz"), "2026-10-13")
        self.assertIn("2026-10-13", sittings)
        self.assertIn("PEC 221/2019", [r for p in sen for r in p["refs"]])
        # a Câmara-initiated matéria keeps the shared number
        self.assertIn("PDS 240/2011", [r for p in sen for r in p["refs"]])
        self.assertEqual(br.key("PDS", "00240", "2011", senado=True), "SF PDS 240/2011")
        self.assertEqual(br.key("PL", "1904", "2024"), "PL 1904/2024")

    def test_it_calendar(self):
        cals = it.calendars(text("it-index.html.gz"))
        self.assertEqual(cals[0][0], "comunicazioni.principale.20261001")
        pts = it.parse(text("it-calendario.html.gz"), cals[0][0])
        days = {p["date"] for p in pts}
        self.assertIn("2026-10-12", days)
        p = next(p for p in pts if "19/C.2830" in p["refs"])
        self.assertEqual(p["date"], "2026-10-13")
        self.assertEqual(it.heading_date("Martedì 13 (ore 9-13,30) e mercoledì 14 ottobre", 2026),
                         "2026-10-13")

    def test_fr_points_dossier_refs_and_cancelled(self):
        with open(os.path.join(FIX, "fr-agenda.zip"), "rb") as fh:
            zf = zipfile.ZipFile(io.BytesIO(fh.read()))
        pts = fr.parse_zip(zf, "2026-10-10", "2026-10-31", {"PO420120": "Commission des affaires sociales"})
        refs = {r for p in pts for r in p["refs"]}
        self.assertIn("DLR5L17N54445", refs)
        plen = [p for p in pts if p["kind"] == "plenary"]
        self.assertEqual(plen[0]["body"], "Séance publique")
        self.assertTrue(any(p["body"] == "Commission des affaires sociales" for p in pts))
        # the cancelled NATO visit is left out
        self.assertFalse(any("Canberra" in (p["title"] or "") for p in pts))
        hearing = [p for p in pts if "HUNQZ" in (p["title"] or "")]
        self.assertEqual(len(hearing), 1)

    def test_at_termine_and_tagesordnung(self):
        entries = at.parse_termine(js("at-termine.json.gz"))
        self.assertTrue(entries)
        e = next(x for x in entries if x["to_path"] and "NRSITZ/101" in x["to_path"])
        self.assertEqual((e["date"], e["time"], e["gp"]), ("2026-10-14", "09:00", "XXVIII"))
        pts = at.parse_to(text("at-to-nrsitz-101.html.gz"), e)
        self.assertTrue(pts)
        self.assertEqual(pts[0]["refs"], ["XXVIII/I/625", "XXVIII/I/638"])
        self.assertEqual(pts[0]["item_id"], "NRSITZ/101 TOP 1")
        self.assertNotIn("Berichterstatter", pts[0]["title"])
        self.assertEqual(at.refs_of("Antrag 985/A(E) ... (646 d.B.) III-393", "XXVIII"),
                         ["XXVIII/I/646", "XXVIII/A/985", "XXVIII/III/393"])

    def test_es_week_page(self):
        pts = es.parse_week(text("es-semana-2026-09-14.html.gz"))
        self.assertTrue(pts)
        self.assertEqual(min(p["date"] for p in pts), "2026-09-14")
        plen = [p for p in pts if p["kind"] == "plenary"]
        self.assertTrue(plen)
        for p in pts:
            self.assertNotIn("Ver directo", p["title"])
            self.assertFalse(p["title"].lower().startswith("sin convocatoria"))
        self.assertEqual(es.legislature("2026-12-29", ""), 16)
        self.assertEqual(len(es.weeks("2026-10-10", 21)), 4)

    def test_ar_senate_week(self):
        pts = ar.parse_week(text("ar-semana-2026-10-12.html.gz"), 2026)
        # guided visits and concerts are not business
        self.assertFalse(any("Concierto" in p["title"] or "Visita" in p["title"] for p in pts))
        self.assertTrue(all(p["kind"] in ("committee", "plenary") for p in pts))
        cttee = next(p for p in pts if p["item_id"] == "34373")
        self.assertEqual((cttee["date"], cttee["time"], cttee["kind"]),
                         ("2026-10-15", "14:00", "committee"))
        self.assertIn("sen/854-PE-1997", cttee["refs"])
        self.assertTrue(any(p["date"] == "2026-10-14" for p in pts))
        # a committee is classified on its Temario, never its name ('... y Culto')
        self.assertTrue(cttee["text"].startswith("Temario"))
        conn = db.init_db(sqlite3.connect(":memory:"))
        got = agenda.classify(conn, ar, [cttee], agenda.taxonomies(ce.adapter("ar")), {})
        self.assertEqual(got[0]["areas"], [])
        self.assertEqual(ar.refs_of("S-1234/26 y 4139-D-2026"),
                         ["sen/1234-S-2026", "dip/4139-D-2026"])


def store_with_bills():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO pl_processes (process_key, term, number, title, areas, tier) "
                 "VALUES ('10/223', 10, '223', 'Projekt ustawy o planowaniu rodziny', '[1]', 1)")
    conn.execute("INSERT INTO pl_prints (print_key, term, number, process_key) "
                 "VALUES ('10/3183', 10, '3183', '10/3086')")
    conn.execute("INSERT INTO pl_processes (process_key, term, number, title, areas, tier) "
                 "VALUES ('10/3086', 10, '3086', 'Projekt o służbie zagranicznej', '[]', NULL)")
    conn.commit()
    return conn


class Pipeline(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.eds = os.path.join(self.tmp, "editions")
        os.makedirs(self.eds)

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def collect_pl(self, conn, today="2026-10-10", reply=None):
        client = FakeClient({"proceedings": reply if reply is not None
                             else js("pl-proceedings.json.gz")})
        return agenda.collect(conn, "pl", client, today, log=lambda *a: None)

    def test_bills_by_key_watched_and_tier(self):
        conn = store_with_bills()
        n, ours, gaps = self.collect_pl(conn)
        self.assertEqual((n, gaps), (41, 0))
        r = conn.execute("SELECT * FROM country_agenda WHERE cc='pl' AND item_id='67-14'").fetchone()
        self.assertEqual(json.loads(r["bill_keys"]), ["10/223"])
        self.assertIn(1, json.loads(r["areas"]))
        self.assertEqual(r["tier"], 1)
        self.assertIn("10/223", json.loads(r["watch_keys"]))
        # a print resolves to its process through pl_prints
        r1 = conn.execute("SELECT refs FROM country_agenda WHERE item_id='67-1'").fetchone()
        self.assertIn("10/3086", json.loads(r1["refs"]))
        run = agenda.latest_run(conn, "pl")
        self.assertEqual(run[0], "2026-10-10")
        self.assertEqual(run[3], "2026-10-23")      # the sitting's last day
        self.assertEqual(run[4], "2026-10-20")

    def test_ahead_items_one_per_bill_and_latest_run_only(self):
        conn = store_with_bills()
        self.collect_pl(conn)
        wl = ce.watchlist_of(ce.adapter("pl"))
        got = agenda.ahead_items(conn, "pl", "2026-10-12", wl)
        keys = [it["watch_key"] for it in got if it["watched"]]
        self.assertEqual(len(keys), len(set(keys)))
        ab = next(it for it in got if it["watch_key"] == "10/223")
        self.assertEqual(ab["kind"], "agenda")
        self.assertEqual(ab["tier"], 1)
        self.assertIn("Plenary, sitting 67", ab["takeaway"])
        self.assertIn("10/223", ab["takeaway"])
        # outside the fortnight: nothing
        self.assertEqual(agenda.ahead_items(conn, "pl", "2026-11-20", wl), [])
        # a later run that no longer carries the sitting hides it
        self.collect_pl(conn, today="2026-10-11", reply=[])
        self.assertEqual(agenda.ahead_items(conn, "pl", "2026-10-12", wl), [])

    def test_a_same_day_rerun_drops_what_it_no_longer_carries(self):
        conn = store_with_bills()
        self.collect_pl(conn)
        self.collect_pl(conn, reply=[])
        wl = ce.watchlist_of(ce.adapter("pl"))
        self.assertEqual(agenda.ahead_items(conn, "pl", "2026-10-12", wl), [])

    def test_gap_is_recorded_and_nothing_stored(self):
        conn = store_with_bills()
        from src.http import FetchError
        client = FakeClient({"proceedings": FetchError("u", "f", "s", 1, OSError("timeout"))})
        n, ours, gaps = agenda.collect(conn, "pl", client, "2026-10-10", log=lambda *a: None)
        self.assertEqual((n, ours, gaps), (0, 0, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='pl-agenda'")
                         .fetchone()[0], 1)
        self.assertIsNone(agenda.latest_run(conn, "pl"))
        # after a good read, a failed one leaves it standing
        self.collect_pl(conn)
        agenda.collect(conn, "pl", client, "2026-10-17", log=lambda *a: None)
        self.assertEqual(agenda.latest_run(conn, "pl")[0], "2026-10-10")

    def test_edition_week_ahead_section_and_coverage_line(self):
        conn = store_with_bills()
        self.collect_pl(conn)
        text_ = ce.render(conn, ce.adapter("pl"), "2026-10-12", "2026-10-05",
                          directory=self.eds)
        self.assertIn("## Week ahead", text_)
        self.assertIn("przerywania ciąży", text_)
        self.assertIn("Watched", text_)
        self.assertIn("Week ahead (the Sejm API's proceedings, with planned sittings): read "
                      "10 October 2026", text_)
        self.assertIn("next sitting 20 October 2026", text_)
        self.assertNotIn("No agenda is collected yet", text_)
        self.assertNotIn("—", text_)

    def test_quiet_week_still_says_how_far_the_agenda_reaches(self):
        conn = store_with_bills()
        self.collect_pl(conn, reply=[])
        text_ = ce.render(conn, ce.adapter("pl"), "2026-10-12", "2026-10-05",
                          directory=self.eds)
        self.assertIn("A quiet week", text_)
        self.assertIn("No agenda is published yet for the next sitting", text_)

    def test_never_read_says_so(self):
        conn = db.init_db(sqlite3.connect(":memory:"))
        self.assertIn("has not been read yet", agenda.ahead_note(conn, "nl", "2026-10-12"))

    def test_every_adapter_named_has_the_hooks(self):
        for cc in ("nl", "pl", "ch", "br", "it", "fr", "at", "es", "ar"):
            c = ce.adapter(cc)
            self.assertIsNotNone(c.week_ahead, cc)
            self.assertIsNotNone(c.ahead_note, cc)
            mod = agenda.module(cc)
            self.assertEqual(mod.CC, cc)
            self.assertTrue(callable(mod.fetch))

    def test_fr_week_ahead_keeps_the_decrees_note(self):
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        from src.editions import fr as fr_ed
        got = fr_ed.week_ahead(conn, "2026-10-12", ce.watchlist_of(ce.adapter("fr")))
        self.assertTrue(any(it["key"] == "aide-a-mourir-decrees" for it in got))

    def test_jobs_run_the_step_before_the_edition(self):
        for cc in ("nl", "pl", "ch", "br", "it", "fr", "at", "es", "ar"):
            with open(os.path.join(ROOT, "jobs", "{0}-weekly.sh".format(cc))) as fh:
                job = fh.read()
            step = job.find("tools/country_agenda.py {0}".format(cc))
            self.assertGreater(step, job.find("tools/{0}_rollcalls.py --".format(cc))
                               if cc != "fr" else job.find("tools/fr_rollcalls.py ||"), cc)
            self.assertLess(step, job.find("tools/{0}_monitor.py --edition".format(cc)), cc)
            self.assertLess(step, job.find("tools/db_state.py --push"), cc)


class Http(unittest.TestCase):
    def test_get_text_passes_extra_headers(self):
        from src.http import HttpClient
        seen = {}

        class Resp:
            headers = {}

            def read(self):
                return b"<html></html>"

        class Opener:
            def open(self, request, timeout=None):
                seen.update({k.lower(): v for k, v in request.header_items()})
                return Resp()

        tmp = tempfile.mkdtemp()
        try:
            c = HttpClient(raw_dir=tmp, opener=Opener(), sleep=lambda s: None, throttle=0)
            c.get_text("https://www.camera.it/x", "f", "s", headers={"Accept": "text/html"})
            self.assertEqual(seen.get("accept"), "text/html")
            c.get_text("https://www.camera.it/y", "f", "s2")
            self.assertTrue(seen.get("accept").startswith("application/json"))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
