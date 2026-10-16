"""Peru's regional forward agendas (src/regional_agendas/pe.py) on trimmed live
captures of 16 October 2026 (tests/fixtures/regional_agenda/pe/: gob.pe's
'Agenda de Sesión de Consejo Regional' lists). No network."""
import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import pe  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402


def fx(name):
    return load_fixture("pe", name + ".gz")


def ctx(today, days=56):
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    return ra.Ctx(today, until, log=lambda *a: None)


class ParsersTest(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(pe.es_date("del pleno del Consejo Regional del 15 de Octubre del 2026."), "2026-10-15")
        self.assertEqual(pe.es_date("realizada el viernes 11 de setiembre de 2026"), "2026-09-11")
        self.assertEqual(pe.sitting_date("Convocatoria a Sesión Ordinaria: lunes 17 agosto 2026", ""),
                         "2026-08-17")

    def test_lima_region_uploads_ahead(self):
        rows = pe.parse_gobpe_list(fx("pe-lima.html"))
        self.assertEqual(len(rows), 25)
        eid, title, summary, published, url = rows[0]
        self.assertEqual(title, "Agenda de Sesión de Consejo Regional N° 32-2026-CR/GRL")
        self.assertEqual(published, "2026-10-07")
        self.assertTrue(url.startswith("https://www.gob.pe/institucion/regionlima/informes-publicaciones/"))
        items = pe.items_from_list(rows, ctx("2026-10-07"), "lima", "Consejo Regional")
        self.assertEqual(items[0]["dated"], "2026-10-15")
        self.assertEqual(items[0]["business"], "")
        self.assertEqual(items[0]["meeting_id"], "lima:2026-10-15:sesion-ordinaria")

    def test_ica_reprogrammed(self):
        rows = pe.parse_gobpe_list(fx("pe-ica.html"))
        items = pe.items_from_list(rows, ctx("2026-08-27", days=10), "ica", "Consejo Regional")
        self.assertEqual([i["dated"] for i in items], ["2026-09-02"])     # the moved 3 September dropped

    def test_piura_after_the_fact(self):
        rows = pe.parse_gobpe_list(fx("pe-piura.html"))
        self.assertEqual(pe.items_from_list(rows, ctx("2026-10-16"), "piura", "Consejo Regional"), [])


class CollectTest(unittest.TestCase):
    def test_end_to_end_then_dead_host(self):
        lima = pe.TYPE_URL.format("regionlima", pe.COUNCIL_TYPE)
        conn = store()
        s = ra.collect(conn, "pe", FakeClient({lima: fx("pe-lima.html")}), "2026-10-07",
                       regions=["lima", "puno"], log=lambda *a: None)
        self.assertEqual(s["read"], ["lima"])
        self.assertEqual(s["no-route"], ["puno"])
        self.assertEqual((s["rows"], s["tba"]), (1, 1))
        row = conn.execute("SELECT dated, business, item_type, url FROM regional_agenda").fetchone()
        self.assertEqual(tuple(row)[:3], ("2026-10-15", "Sitting booked; agenda to be announced",
                                          "to be announced"))
        s2 = ra.collect(conn, "pe", FakeClient({}), "2026-10-08", regions=["lima"], log=lambda *a: None)
        self.assertEqual(s2["gap"], ["lima"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], 1)

    def test_every_region_declared(self):
        self.assertEqual(len(pe.REGIONS), 26)
        self.assertEqual(len([r for r in pe.REGIONS.values() if r.reader]), 13)


if __name__ == "__main__":
    unittest.main()
