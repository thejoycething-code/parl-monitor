"""Mexico's state congresses' forward agendas (src/regional_agendas/mx.py).
Fixtures are live replies of 16 October 2026, trimmed (Quintana Roo's
attendance lists dropped); Yucatán's orden del día PDF is kept as the text
pypdf extracts. No network."""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import mx  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402

TODAY = "2026-10-16"
CTX = ra.Ctx(TODAY, "2026-12-11")
PAST = ra.Ctx("2026-10-01", "2026-12-11")


def fx(name):
    return load_fixture("mx", name)


class OrdenPointsTest(unittest.TestCase):
    def test_roman_with_letters(self):
        pts = mx.orden_points(["I.- LECTURA DEL ORDEN DEL DÍA.", "III.- ASUNTOS EN CARTERA:",
                               "A) INICIATIVA CON PROYECTO DE DECRETO", "QUE REFORMA LA LEY.",
                               "B) DICTAMEN.", "IV.- CLAUSURA."])
        self.assertEqual(pts, [("I", "LECTURA DEL ORDEN DEL DÍA.", None),
                               ("III.A", "INICIATIVA CON PROYECTO DE DECRETO QUE REFORMA LA LEY.",
                                "ASUNTOS EN CARTERA"),
                               ("III.B", "DICTAMEN.", "ASUNTOS EN CARTERA"),
                               ("IV", "CLAUSURA.", None)])

    def test_routine_only_is_a_booked_slot(self):
        pts = mx.parse_chih_orden(fx("chih_orden.html"))
        self.assertEqual(len(pts), 7)
        self.assertIsNone(mx.point_items(pts, "2026-10-20", "Pleno", "chih-2026-10-20"))

    def test_es_date(self):
        self.assertEqual(mx.es_date("JUEVES 15 DE OCTUBRE DEL AÑO 2026"), "2026-10-15")
        self.assertEqual(mx.es_date("20 octubre 2026 - 11:00"), "2026-10-20")
        self.assertEqual(mx.es_date("13 de Octubre de 2026"), "2026-10-13")


class YucatanTest(unittest.TestCase):
    def test_agenda_and_session(self):
        rows = mx.parse_yuc_agenda(fx("yuc_home.html"))
        self.assertEqual(len(rows), 15)
        self.assertEqual(mx.yuc_body(rows[0]), "Pleno")
        self.assertEqual(mx.yuc_body(rows[1]), "Comisión de Justicia y Seguridad Pública")
        self.assertTrue(mx.parse_yuc_session(fx("yuc_sesion_2598.html")).endswith(
            "ORDEN%20LINK%2015%20DE%20OCTUBRE%20DE%202026-def.pdf"))

    def test_orden_pdf(self):
        pts = mx.parse_yuc_orden(fx("yuc_orden_20261015.txt"))
        items = mx.point_items(pts, "2026-10-15", "Pleno", "yuc-2598")
        mariposa = [i for i in items if "CÓDIGO MARIPOSA" in i["business"]]
        self.assertTrue(mariposa)
        self.assertEqual(mariposa[0]["detail"], "ASUNTOS EN CARTERA")
        self.assertFalse(any("LIBRE Y SOBERANO" in i["business"] for i in items))   # the masthead

    def test_read_yuc_end_to_end(self):
        rows = mx.parse_yuc_agenda(fx("yuc_home.html"))
        pages = {mx.YUC + "/": fx("yuc_home.html"), rows[0]["url"]: fx("yuc_sesion_2598.html")}
        pdf = mx.parse_yuc_session(fx("yuc_sesion_2598.html"))
        pages[pdf] = b"%PDF"
        conn = store()
        with mock.patch.object(mx, "pdf_text", return_value=fx("yuc_orden_20261015.txt")):
            s = ra.collect(conn, "mx", FakeClient(pages), "2026-10-15", regions=["yuc"],
                           log=lambda *a: None)
        self.assertEqual(s["read"], ["yuc"])
        rows = conn.execute("SELECT business, areas, item_type FROM regional_agenda").fetchall()
        self.assertGreater(len(rows), 10)
        self.assertTrue(any("MARIPOSA" in r[0] and r[1] != "[]" for r in rows))


class JaliscoChihuahuaTest(unittest.TestCase):
    def test_jalisco_calendar(self):
        entries = mx.parse_jal_month(fx("jal_mes_202610.html"))
        self.assertEqual(len(entries), 32)
        items = mx.jal_items(entries, PAST)
        bodies = [i["body"] for i in items]
        self.assertIn("Comisión de Participación Ciudadana", bodies)    # '(TELEMATICA)' dropped
        self.assertIn("Pleno", bodies)
        self.assertFalse(any("Prensa" in b or "Adquisiciones" in b for b in bodies))
        self.assertTrue(all(i["business"] == "" for i in items))

    def test_read_jal_asks_each_month(self):
        pages = {mx.JAL_MONTH.format(m): fx("jal_mes_202610.html") if m == "2026-10" else "<table/>"
                 for m in ("2026-10", "2026-11", "2026-12")}
        client = FakeClient(pages)
        read = mx.read_jal(client, CTX)
        self.assertEqual(len(client.asked), 3)
        self.assertEqual([i["dated"] for i in read.items], [])      # nothing after 16 October
        self.assertEqual(read.units, [ra.window(TODAY, CTX.until)])

    def test_chihuahua_next_session(self):
        nxt = mx.parse_chih_next(fx("chih_sesiones.html"))
        self.assertEqual(nxt[:2], ("2026-10-20", "11:00"))
        read = mx.read_chih(FakeClient({mx.CHIH + "sesiones.php": fx("chih_sesiones.html"),
                                        mx.CHIH + "ordenDia.php": fx("chih_orden.html")}), CTX)
        self.assertEqual([(i["dated"], i["business"], i["body"]) for i in read.items],
                         [("2026-10-20", "", "Pleno")])


class QuintanaRooBcsTest(unittest.TestCase):
    def test_qroo_agenda(self):
        rows = mx.parse_qroo_agenda(fx("qroo_agenda.html"))
        self.assertEqual(rows[0]["dated"], "2026-10-13")
        self.assertEqual(rows[0]["bodies"],
                         ["Comisión de Desarrollo Familiar y Grupos en Situación de Vulnerabilidad"])
        self.assertTrue(rows[0]["subjects"][0].startswith("Presentación del Plan de Trabajo"))
        items = mx.qroo_agenda_items(rows, PAST)
        self.assertTrue(any("Economía Circular" in i["business"] for i in items))

    def test_qroo_orden(self):
        dated, time, title, pts = mx.parse_qroo_orden(fx("qroo_orden_1321.html"))
        self.assertEqual((dated, time), ("2026-10-13", "15:30"))
        self.assertTrue(title.startswith("Sesión Número 13"))
        self.assertEqual(pts[0], ("1", "Verificación del quórum.", None))
        self.assertTrue(pts[3][1].startswith("Lectura de la Iniciativa de Decreto"))

    def test_read_qroo(self):
        pages = {mx.QROO + "/agenda/": fx("qroo_agenda.html"), mx.QROO + "/": fx("qroo_home.html"),
                 mx.QROO + "/ordenesdia/1321": fx("qroo_orden_1321.html")}
        read = mx.read_qroo(FakeClient(pages), ra.Ctx("2026-10-13", "2026-12-08"))
        bodies = {i["body"] for i in read.items}
        self.assertIn("Pleno", bodies)
        self.assertEqual(read.units, [ra.window("2026-10-13", "2026-12-08")])

    def test_bcs(self):
        url = mx.parse_bcs_category_url(fx("bcs_home.html"))
        self.assertTrue(url.endswith("/orden-del-dia"))
        rows = mx.parse_bcs_category(fx("bcs_ordenes.html"))
        self.assertEqual(rows[0][0], "2026-10-15")
        time, pts = mx.parse_bcs_article(fx("bcs_orden_9407.html"))
        self.assertEqual(time, "11:00")
        self.assertEqual(len(pts), 14)
        self.assertTrue(pts[5][1].startswith("INICIATIVA CON PROYECTO DE DECRETO"))
        self.assertTrue(mx.is_routine(pts[-1][1]))                  # CLAUSURA.

    def test_read_bcs(self):
        url = mx.parse_bcs_category_url(fx("bcs_home.html"))
        rows = mx.parse_bcs_category(fx("bcs_ordenes.html"))
        pages = {mx.BCS + "/": fx("bcs_home.html"), url: fx("bcs_ordenes.html"),
                 rows[0][2]: fx("bcs_orden_9407.html")}
        read = mx.read_bcs(FakeClient(pages), ra.Ctx("2026-10-15", "2026-12-10"))
        self.assertEqual(len(read.items), 14)
        self.assertEqual(read.items[0]["meeting_id"], "bcs-9407")


class FailureTest(unittest.TestCase):
    def test_dead_host_keeps_rows(self):
        pages = {mx.BCS + "/": fx("bcs_home.html"),
                 mx.parse_bcs_category_url(fx("bcs_home.html")): fx("bcs_ordenes.html"),
                 mx.parse_bcs_category(fx("bcs_ordenes.html"))[0][2]: fx("bcs_orden_9407.html")}
        conn = store()
        ra.collect(conn, "mx", FakeClient(pages), "2026-10-15", regions=["bcs"], log=lambda *a: None)
        n = conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0]
        self.assertEqual(n, 14)
        s = ra.collect(conn, "mx", FakeClient({}), "2026-10-15", regions=["bcs"], log=lambda *a: None)
        self.assertEqual(s["gap"], ["bcs"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], n)

    def test_every_state_declared(self):
        from src import mxs_store
        self.assertEqual(set(mx.REGIONS), set(mxs_store.STATES))


if __name__ == "__main__":
    unittest.main()
