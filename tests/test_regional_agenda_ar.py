"""Argentina's regional forward agendas (src/regional_agendas/ar.py) on trimmed
live captures of 16 October 2026 (tests/fixtures/regional_agenda/ar/; the
Buenos Aires orden del día PDFs as the text pypdf extracts, addressees
omitted). No network, no pypdf needed."""
import datetime
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import ar  # noqa: E402
from tests.test_regional_agenda import FIX, FakeClient, load_fixture, store  # noqa: E402

TODAY = "2026-10-16"


def fx(name):
    path = os.path.join(FIX, "ar", name)
    return load_fixture("ar", name + ".gz" if os.path.exists(path + ".gz") else name)


def ctx(today=TODAY, days=56):
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    return ra.Ctx(today, until, log=lambda *a: None)


class FormClient(FakeClient):
    """A POST is keyed by its URL and its fields ('url?idAgenda=4831')."""

    def post_form(self, url, fields, feed, slug, **kw):
        key = url + "?" + "&".join("{0}={1}".format(k, v) for k, v in sorted(fields.items()))
        return self.get_text(key if key in self.pages else url, feed, slug)


BA_OD = {
    "https://intranet.hcdiputados-ba.gov.ar/reuniones/OD_SERVICIOS_PUBLICOS_10749.pdf?x=441794671":
        "ba-od-servicios-publicos.txt",
    "https://intranet.hcdiputados-ba.gov.ar/reuniones/OD_JUEGOS_DE_AZAR,_LOTERIA_Y_PREVENCION_DE_LA_LUDOPATIA_"
    "10759.pdf?x=1603476560": "ba-od-juegos-de-azar.txt",
}


class ParsersTest(unittest.TestCase):
    def test_caba(self):
        self.assertEqual(ar.parse_caba_agendas(fx("caba-agendas.xml")),
                         [("4831", "2026-10-19"), ("4830", "2026-10-16")])
        meetings = ar.parse_caba_day(fx("caba-day-4831.xml"))
        bodies = [m[3] for m in meetings]
        self.assertIn("Comisión de Tránsito y Transporte", bodies)
        self.assertIn("Junta de Ética, Acuerdos y Organismos de Control", bodies)
        self.assertFalse(any("Protocolo" in b for b in bodies))       # protocol events left out
        items = ar.caba_items(meetings, ctx())
        self.assertTrue(all(i["dated"] == "2026-10-19" for i in items))
        self.assertTrue(any(i["detail"].startswith("Reunión de Audiencia Pública") for i in items))
        sessions = ar.parse_caba_sessions(fx("caba-sessions.xml"))
        self.assertIn(("1154", "2026-10-06", "ESPECIAL"), sessions)

    def test_ba(self):
        rows = ar.parse_ba_home(fx("ba-home.html"))
        self.assertEqual(rows[0][:5], ("2026-10-16", "12:00", "COMISIÓN DE SERVICIOS PÚBLICOS",
                                       "Reunión ordinaria.", "Salas 5 y 6 del Anexo"))
        self.assertIn("OD_SERVICIOS_PUBLICOS_10749.pdf", rows[0][5])
        self.assertFalse(any("VISITA" in r[2] for r in rows))
        self.assertEqual(ar.ba_body("COMISIÓN DE JUEGOS DE AZAR, LOTERÍA Y PREVENCIÓN DE LA LUDOPATÍA"),
                         "Comisión de Juegos de Azar, Lotería y Prevención de la Ludopatía")
        pts = ar.parse_ba_od(fx("ba-od-servicios-publicos.txt"))
        self.assertEqual(len(pts), 6)
        self.assertEqual(pts[0], ("D-2521/25-26", "Proyecto de ley: Creando el registro provincial del servicio "
                                                  "de transporte para personas con discapacidad"))
        self.assertTrue(pts[3][1].startswith("Proyecto de declaración: Solicitando"))
        self.assertFalse(any("RECALDE" in p[1].upper() for p in pts))    # authors dropped
        info = ar.parse_ba_od(fx("ba-od-juegos-de-azar.txt"))
        self.assertEqual(len(info), 1)
        self.assertTrue(info[0][1].startswith("Reunión informativa con el presidente del Instituto"))

    def test_cba(self):
        month, cells = ar.parse_cba_calendar(fx("cba-agenda.html"))
        self.assertEqual(month, "2026-10-01")
        self.assertIn(("2026-10-14", "142146"), cells)
        self.assertIn(("2026-10-01", "141294"), cells)
        posts = {str(p["id"]): p for p in json.loads(fx("cba-events.json"))}
        body, pts = ar.parse_cba_event(posts["141327"])
        self.assertEqual(body, "Comisión de Educación")
        self.assertEqual(pts[0][0], "43863/R/25")
        self.assertTrue(len(pts) >= 2)
        body, pts = ar.parse_cba_event(posts["142146"])
        self.assertEqual(pts[0][0], "48064/L/26")
        self.assertIn("Proyecto de Ley 48064/L/26", pts[0][1])
        self.assertFalse(any("Sibilla" in p[1] for p in pts))           # the visitors' list cut


class CollectTest(unittest.TestCase):
    def pages(self):
        start, end = ar._epoch(TODAY), ar._epoch("2026-12-11") + 86399
        p = {
            ar.CABA_AGENDAS + "?end={0}&start={1}".format(end, start): fx("caba-agendas.xml"),
            ar.CABA_DAY + "?idAgenda=4831": fx("caba-day-4831.xml"),
            ar.CABA_DAY + "?idAgenda=4830": '<?xml version="1.0"?><ArrayOfEventsDay xmlns="http://tempuri.org/"/>',
            ar.CABA_SESSIONS: fx("caba-sessions.xml"),
            ar.BA: fx("ba-home.html"),
            ar.CBA_AGENDA: fx("cba-agenda.html"),
        }
        for url in BA_OD:
            p[url] = b"%PDF-fixture"
        return p

    def fake_pdf(self, data):
        return None

    def test_end_to_end_then_dead_host(self):
        texts = {k: fx(v) for k, v in BA_OD.items()}
        conn = store()
        client = FormClient(self.pages())
        calls = []

        def pdf_text(data):
            url = client.asked[-1]
            calls.append(url)
            return texts.get(url, "")

        with mock.patch.object(ar, "pdf_text", pdf_text):
            s = ra.collect(conn, "ar", client, TODAY, regions=["caba", "ba", "cba", "sc"], log=lambda *a: None)
        self.assertEqual(sorted(s["read"]), ["ba", "caba", "cba"])
        self.assertEqual(s["blocked"], ["sc"])
        per = s["per_region"]
        self.assertEqual(per["caba"]["rows"], 7)
        self.assertEqual(per["cba"]["rows"], 0)            # nothing booked after 14 October yet
        ba_rows = conn.execute("SELECT business, reference, item_time FROM regional_agenda WHERE region='ba' "
                               "AND body='Comisión de Servicios Públicos' ORDER BY item_order").fetchall()
        self.assertEqual(len(ba_rows), 6)
        self.assertEqual(tuple(ba_rows[0])[1:], ("D-2521/25-26", "12:00"))
        n_ba = conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='ba'").fetchone()[0]

        pages = self.pages()
        del pages[ar.BA]
        with mock.patch.object(ar, "pdf_text", self.fake_pdf):
            s2 = ra.collect(conn, "ar", FormClient(pages), "2026-10-17", regions=["ba"], log=lambda *a: None)
        self.assertEqual(s2["gap"], ["ba"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='ba'").fetchone()[0], n_ba)

    def test_without_pypdf_meetings_are_tba(self):
        conn = store()
        with mock.patch.object(ar, "pdf_text", self.fake_pdf):
            s = ra.collect(conn, "ar", FormClient(self.pages()), TODAY, regions=["ba"], log=lambda *a: None)
        self.assertEqual(s["per_region"]["ba"]["rows"], s["tba"])
        self.assertIn("pypdf", s["per_region"]["ba"]["note"])

    def test_every_region_declared(self):
        self.assertEqual(len(ar.REGIONS), 24)
        self.assertEqual(sorted(c for c, r in ar.REGIONS.items() if r.reader), ["ba", "caba", "cba"])


if __name__ == "__main__":
    unittest.main()
