"""Spain's regional forward agendas (src/regional_agendas/es.py) on trimmed
live captures of 16 October 2026 (tests/fixtures/regional_agenda/es/,
gzipped original bytes: several pages are ISO-8859-1). No network."""
import gzip
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import es  # noqa: E402
from tests.test_regional_agenda import FIX, FakeClient, store  # noqa: E402

TODAY = "2026-10-16"


def raw(name):
    """A fixture's original bytes (the page's own charset)."""
    with gzip.open(os.path.join(FIX, "es", name + ".gz"), "rb") as fh:
        return fh.read()


def page(name):
    return es.decode(raw(name))


def ctx(days=56):
    import datetime
    until = (datetime.date.fromisoformat(TODAY) + datetime.timedelta(days=days)).isoformat()
    return ra.Ctx(TODAY, until, log=lambda *a: None)


class HelpersTest(unittest.TestCase):
    def test_bodies(self):
        self.assertEqual(es.body_name("COMISIÓN DE SERVICIOS SOCIALES, FAMILIAS E IGUALDAD"),
                         "Comisión de Servicios Sociales, Familias e Igualdad")
        self.assertEqual(es.body_name("Pleno del Parlamento de Andalucía"), "Pleno")
        self.assertEqual(es.body_name("Ple del Parlament"), "Pleno")
        for name in ("Mesa del Parlament", "Junta de Portavoces", "Intergrup del Sàhara",
                     "Mesa de la Comisión de Economía", "Rueda de prensa del G. P. Popular"):
            self.assertFalse(es.is_business_body(name), name)
        for name in ("Comissió de Salut", "Ponència: Projecte de llei del patrimoni",
                     "Comisión de Educación", "Pleno del Parlamento"):
            self.assertTrue(es.is_business_body(name), name)

    def test_short_drops_names_and_bulletin(self):
        t = ("Proposición No de Ley, PNL/000030, presentada por los Procuradores D. A y D. B, "
             "instando a la Junta a desbloquear el convenio, publicada en el Boletín Oficial de las "
             "Cortes de Castilla y León, n.º 21, de 9 de julio de 2026.")
        self.assertEqual(es.short(t), "Proposición No de Ley, PNL/000030, instando a la Junta a "
                                      "desbloquear el convenio")
        self.assertEqual(es.short("Toma en consideración de la proposición no de ley sobre el papel "
                                  "de la familia, presentada por el Grupo Parlamentario Vox (RE "
                                  "número 64.822, BOCV número 203)."),
                         "Toma en consideración de la proposición no de ley sobre el papel de la "
                         "familia")

    def test_merge_drops_placeholder_with_agenda(self):
        d = [ra.item("2026-10-20", "Moción 1", "Pleno")]
        p = [ra.item("2026-10-20", "", "Pleno"), ra.item("2026-10-21", "", "Pleno"),
             ra.item("2026-10-21", "", "Pleno")]
        got = es.merge(d, p)
        self.assertEqual([(i["dated"], i["business"]) for i in got],
                         [("2026-10-20", "Moción 1"), ("2026-10-21", "")])


class AndaluciaTest(unittest.TestCase):
    def test_index_keeps_current_week(self):
        self.assertEqual(es.parse_an_index(page("an-agenda-index"), TODAY),
                         [("205834", "AGENDA DEL 12 AL 16 DE OCTUBRE")])
        self.assertEqual(es.parse_an_index(page("an-agenda-index"), "2026-10-17"), [])

    def test_week(self):
        items = es.parse_an_week(page("an-agenda-205834"))
        bodies = {i["body"] for i in items}
        self.assertIn("Comisión de Servicios Sociales, Familias e Igualdad", bodies)
        self.assertFalse(any(b.startswith(("Mesa", "Junta", "La presidenta", "Ruedas"))
                             for b in bodies))
        first = items[0]
        self.assertEqual((first["dated"], first["item_time"], first["reference"]),
                         ("2026-10-13", "10:00", "13-26/APC-000727"))
        self.assertTrue(first["business"].startswith("Comparecencias de la consejera"))
        lgtbi = [i for i in items if i["reference"] == "13-26/POC-000537"][0]
        self.assertIn("VI Congreso Internacional LGTBI", lgtbi["business"])
        self.assertNotIn("A propuesta", lgtbi["business"])
        self.assertIn("A propuesta", lgtbi["detail"])
        self.assertEqual(lgtbi["meeting_id"],
                         "2026-10-13:comision-de-servicios-sociales-familias")

    def test_calendar(self):
        self.assertIn((2026, 12), es.parse_an_calendar_months(page("an-calendar")))
        items = es.parse_an_calendar(page("an-calendar-2026-11"), 2026, 11)
        pleno = [i for i in items if i["body"] == "Pleno"]
        self.assertEqual([i["dated"] for i in pleno],
                         ["2026-11-11", "2026-11-12", "2026-11-25", "2026-11-26"])
        self.assertEqual(pleno[0]["business"], "Debate de totalidad PL Presupuestos")
        self.assertEqual(pleno[1]["business"], "")          # booked, agenda to come
        self.assertFalse(any(i["body"].startswith("Mesa") for i in items))
        self.assertEqual(len(items), 16)


class CataluniaTest(unittest.TestCase):
    def test_month(self):
        evs = es.parse_ct_month(page("ct-agenda-2026-10"))
        mh = [e for e in evs if e["dated"] == "2026-10-16"]
        self.assertEqual(mh[0]["name"], "Comissió d'Estudi sobre la Salut Mental i les Addiccions")
        self.assertEqual(mh[0]["time"], "10:00")
        self.assertTrue(mh[0]["od_url"].endswith("p_od0=0111215007"))
        self.assertTrue(any(e["cancelled"] for e in evs))
        self.assertEqual(es.parse_ct_month(page("ct-agenda-2026-11")), [])

    def test_order_and_annual(self):
        pts = es.parse_ct_order(page("ct-ordre-0111215007"))
        self.assertEqual(len(pts), 4)
        self.assertEqual(pts[0][2], "357-01509/15")
        self.assertTrue(pts[0][1].startswith("Compareixença de "))
        self.assertNotIn("Tram.", pts[0][1])
        self.assertEqual(es.parse_ct_annual(page("ct-calendari-anual")),
                         ["2026-10-20", "2026-10-21", "2026-10-22", "2026-11-03", "2026-11-04",
                          "2026-11-05", "2026-12-01", "2026-12-02", "2026-12-03", "2026-12-15",
                          "2026-12-16", "2026-12-17"])


class ValenciaTest(unittest.TestCase):
    def test_list_and_detail(self):
        rows = es.parse_vc_list(page("vc-agenda-list-0"))
        self.assertEqual(rows[0]["dated"], "2026-10-21")
        self.assertEqual(rows[0]["name"], "Comisión de Familia, Política Social e Igualdad")
        self.assertTrue(rows[0]["url"].startswith(es.VC + "/es/"))
        pts = es.parse_vc_detail(page("vc-comision-de-familia-politica-social-e-igualdad-1"))
        self.assertEqual([n for n, _ in pts], [1, 2, 3, 4, 5])
        self.assertEqual(es.short(pts[3][1]),
                         "Toma en consideración de la proposición no de ley sobre el papel de la "
                         "familia")


class CastillaLeonTest(unittest.TestCase):
    def test_week_event_plenos(self):
        evs = es.parse_cl_week(page("cl-semana-2026-10-12"))
        edu = [e for e in evs if e["name"] == "Comisión de Educación"][0]
        self.assertEqual((edu["dated"], edu["time"]), ("2026-10-16", "10:00"))
        self.assertTrue(edu["url"].endswith("NumeroSerieId=15436"))
        nxt = es.parse_cl_week(page("cl-semana-2026-10-19"))
        self.assertFalse(any(es.is_business_body(e["name"]) for e in nxt))   # Mesa, Junta only
        pts = es.parse_cl_event(page("cl-evento-15436"))
        self.assertTrue(pts and pts[0][0] == 1 and pts[0][2].startswith("PNL/"))
        self.assertIn("2026-10-20", es.parse_cl_plenos(page("cl-plenos-previstos")))
        self.assertIn("2026-12-01", es.parse_cl_plenos(page("cl-plenos-previstos")))


class CanariasTest(unittest.TestCase):
    def test_calendar_future_session(self):
        rows, end = es.parse_cn_calendar(page("cn-calendario"))
        self.assertEqual(end, "2026-12-31")
        self.assertIn(("2026-10-20", "10:30", "Pleno del Parlamento"), rows)
        self.assertTrue(all(":" in tm for _, tm, _ in rows))
        self.assertIn("11030100065", es.parse_cn_future(page("cn-futuras")))
        dated, tm, name, pts = es.parse_cn_session(page("cn-asuntos-11030100065"))
        self.assertEqual((dated, tm, name),
                         ("2026-10-22", "10:00", "Gobernación, Desarrollo Autonómico y Justicia"))
        self.assertEqual(pts[0][2], "11L/AGSC-0001")
        self.assertTrue(pts[0][1].startswith("Subcomisiones: "))
        self.assertEqual(es.cn_body(name), "Comisión de Gobernación, Desarrollo Autonómico y Justicia")
        self.assertEqual(es.cn_body("De Control de Radiotelevisión Canaria"),
                         "Comisión de Control de Radiotelevisión Canaria")


class AragonTest(unittest.TestCase):
    def test_week_acto_csv(self):
        evs = es.parse_ar_week(page("ar-semana-1"))
        ma = [e for e in evs if e["name"] == "Comisión de Medio Ambiente y Turismo"][0]
        self.assertEqual((ma["dated"], ma["time"]), ("2026-10-19", "15:00"))
        self.assertIn("uid%5D=16562", ma["url"])
        pts = es.parse_ar_event(page("ar-acto-16562"))
        self.assertEqual([n for n, _ in pts], [1, 2, 3, 4])
        self.assertIn("Proposición no de Ley núm. 378/26", pts[2][1])
        self.assertIn("A petición de G. P. Chunta Aragonesista", pts[1][1])
        days = es.parse_ar_csv(page("ar-calendario-plenos"))
        self.assertIn("2026-10-22", days)
        self.assertIn("2026-12-18", days)


class CantabriaTest(unittest.TestCase):
    def test_week(self):
        items = es.parse_cb_week(page("cb-semana-2026-10-19"))
        pleno = [i for i in items if i["body"] == "Pleno"]
        self.assertEqual(pleno[0]["dated"], "2026-10-19")
        self.assertEqual(pleno[0]["item_time"], "11:30")
        self.assertEqual(pleno[0]["reference"], "11L/4200-0186")
        self.assertNotIn(" E [", pleno[0]["business"])
        self.assertNotIn("presentada por", pleno[0]["business"])
        vox = [i for i in pleno if i["reference"] == "11L/4300-0453"][0]
        self.assertIn("repatriación", vox["business"])
        com = [i for i in items if i["body"].startswith("Comisión de Presidencia")]
        self.assertEqual(len(com), 3)
        self.assertFalse(any(i["body"].startswith("Conferencia") for i in items))


def pages():
    """URL -> page for an end-to-end read of five regions, 10 days ahead."""
    p = {
        es.AN_INDEX: raw("an-agenda-index"),
        es.AN_WEEK.format("205834"): raw("an-agenda-205834"),
        es.AN_CAL: raw("an-calendar"),
        es.AN_CAL_MONTH.format("octubre", 2026): raw("an-calendar-2026-10"),
        es.CT_MONTH.format(1, 10, 2026): raw("ct-agenda-2026-10"),
        "https://www.parlament.cat/web/actualitat/ordre-dia/index.html?p_od0=0111215007":
            raw("ct-ordre-0111215007"),
        es.CT_ANNUAL: raw("ct-calendari-anual"),
        es.CB_WEEK.format("2026-10-12"): raw("cb-semana-2026-10-12"),
        es.CB_WEEK.format("2026-10-19"): raw("cb-semana-2026-10-19"),
        es.CB_WEEK.format("2026-10-26"): raw("cb-semana-2026-10-26"),
        es.CL_WEEK.format(es.monday("2026-10-12")): raw("cl-semana-2026-10-12"),
        es.CL_WEEK.format(es.monday("2026-10-19")): raw("cl-semana-2026-10-19"),
        es.CL + "/Agenda/Evento?NumeroSerieId=15436": raw("cl-evento-15436"),
        es.CL_PLENOS: raw("cl-plenos-previstos"),
        es.AR_WEEKS[0]: raw("ar-semana-0"),
        es.AR_WEEKS[1]: raw("ar-semana-1"),
        "https://www.cortesaragon.es/Acto-programado.2319.0.html?&no_cache=1&tx_caagenda_pi4%5Buid%5D=16562&no_cache=1":
            raw("ar-acto-16562"),
        es.AR_CSV: raw("ar-calendario-plenos"),
    }
    return p


class CollectTest(unittest.TestCase):
    REGIONS = ["an", "ct", "cb", "cl", "ar", "md", "ri"]

    def run_once(self, conn, client):
        logs = []
        s = ra.collect(conn, "es", client, TODAY, days=10, regions=self.REGIONS, log=logs.append)
        return s, logs

    def test_end_to_end_then_dead_host(self):
        conn = store()
        s, logs = self.run_once(conn, FakeClient(pages()))
        self.assertEqual(sorted(s["read"]), ["an", "ar", "cb", "cl", "ct"])
        self.assertEqual(s["blocked"], ["md"])
        self.assertEqual(s["no-route"], ["ri"])
        rows = conn.execute("SELECT region, dated, body, business, item_type, lang, reference "
                            "FROM regional_agenda").fetchall()
        by = {}
        for r in rows:
            by.setdefault(r[0], []).append(r)
        # Cantabria: the plenary of 19 October, point by point.
        cb = [r for r in by["cb"] if r[2] == "Pleno"]
        self.assertTrue(any(r[6] == "11L/4300-0453" for r in cb))
        # Catalonia: classified with the Catalan list.
        ct = [r for r in by["ct"] if r[3] != "Sitting booked; agenda to be announced"]
        self.assertTrue(ct and all(r[5] == "taxonomy-ca.yaml" for r in ct))
        # Planned plenaries: placeholders.
        self.assertTrue(any(r[1] == "2026-10-20" and r[2] == "Pleno" and r[4] == ra.TBA
                            for r in by["ct"]))
        self.assertTrue(any(r[1] == "2026-10-20" and r[2] == "Pleno" and r[4] == ra.TBA
                            for r in by["cl"]))
        self.assertTrue(any(r[1] == "2026-10-22" and r[2] == "Pleno" and r[4] == ra.TBA
                            for r in by["ar"]))
        # Aragón 19 October committee read from its 'Acto programado' page.
        self.assertTrue(any(r[2] == "Comisión de Medio Ambiente y Turismo" and "378/26" in r[3]
                            for r in by["ar"]))
        # Missing pages are partial gaps, not whole-region failures.
        gaps = [g[0] for g in conn.execute("SELECT detail FROM gaps").fetchall()]
        self.assertTrue(any("Castilla y León week of 2026-10-26" in g for g in gaps))
        self.assertTrue(any("Cataluña order of the day" in g for g in gaps))
        n_cb = len(by["cb"])

        # Cantabria's host dies: a gap, its rows kept.
        dead = pages()
        for k in list(dead):
            if k.startswith(es.CB):
                del dead[k]
        s2, _ = self.run_once(conn, FakeClient(dead))
        self.assertIn("cb", s2["gap"])
        kept = conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='cb'").fetchone()[0]
        self.assertEqual(kept, n_cb)
        status = conn.execute("SELECT status FROM regional_agenda_runs WHERE region='cb' AND "
                              "run_date=?", (TODAY,)).fetchone()[0]
        self.assertEqual(status, "gap")

    def test_every_region_declared(self):
        from src import es_regions_store as esr
        self.assertEqual(set(es.REGIONS), set(esr.PARLIAMENTS))
        for code, reg in es.REGIONS.items():
            if reg.reader is None:
                self.assertIn(reg.status, ("blocked", "no-route"))
                self.assertTrue(reg.note, code)


if __name__ == "__main__":
    unittest.main()
