"""Argentina's National Congress: Senate actas, expedientes and members
(tools/ar_rollcalls.py). No network: every page is a trimmed real fixture
from tests/fixtures/ar/, fetched 9 October 2026."""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ar_store, db  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "ar")


def _load():
    spec = importlib.util.spec_from_file_location(
        "ar_rollcalls", os.path.join(ROOT, "tools", "ar_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


arr = _load()
TODAY = "2026-10-09"


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def store():
    return db.init_db(sqlite3.connect(":memory:"))


class FakeClient:
    """Serves fixtures by URL fragment and records what was asked."""

    def __init__(self, pages=None, fail=()):
        self.pages = pages or {}
        self.fail = tuple(fail)
        self.calls = []
        self.user_agent = "test"

    def _find(self, url):
        self.calls.append(url)
        for frag in self.fail:
            if frag in url:
                raise FetchError(url, "t", "t", 1, "refused")
        for frag, body in self.pages.items():
            if frag in url:
                return body
        raise FetchError(url, "t", "t", 1, "no fixture for " + url)

    def get_text(self, url, feed, slug, **kw):
        return self._find(url)

    def get_bytes(self, url, feed, slug, **kw):
        return self._find(url).encode("utf-8")

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._find(url))

    def post_form(self, url, fields, feed, slug, **kw):
        return self._find(url + "?anio=" + fields["busqueda_actas[anio]"])


def senate_pages(**extra):
    pages = {"actas?anio=2026": fixture("actas_2026.html"),
             "actas?anio=2025": fixture("actas_2025.html"),
             "detalleActa/2623": fixture("acta_2623.html"),
             "detalleActa/2624": fixture("acta_2623.html"),
             "detalleActa/2847": fixture("acta_2473.html"),
             "verExp/": fixture("verexp_33-CD-2025.html"),
             "SenadoresHistorico": fixture("senadores_historico.json")}
    pages.update(extra)
    return pages


class KeyTests(unittest.TestCase):
    def test_diputados_key_drops_padding_and_widens_the_year(self):
        self.assertEqual(arr.dip_key("0001-D-2008"), "dip/1-D-2008")
        self.assertEqual(arr.dip_key("5346-D-2026"), "dip/5346-D-2026")
        self.assertEqual(arr.dip_key("10-PE-24"), "dip/10-PE-2024")
        self.assertIsNone(arr.dip_key(""))

    def test_senate_link_becomes_a_chamber_scoped_key(self):
        self.assertEqual(arr.parse_ver_exp_href("/parlamentario/comisiones/verExp/159.25/PE/PL"),
                         ("sen/159-PE-2025", 159, "PE", 2025, "PL"))

    def test_the_two_chambers_never_share_a_key(self):
        # The executive's message 159/25 exists in both chambers as different documents.
        self.assertNotEqual(arr.sen_key(159, "PE", 25), arr.dip_key("159-PE-2025"))


class ListingTests(unittest.TestCase):
    def test_2026_listing(self):
        actas = arr.parse_actas(fixture("actas_2026.html"))
        self.assertEqual([a["key"] for a in actas], ["sen-acta-2623", "sen-acta-2624", "sen-acta-2847"])
        first = actas[0]
        self.assertEqual(first["date"], "2026-02-11")
        self.assertEqual(first["number"], 1)
        self.assertEqual(first["title"], "Modernización Laboral.")
        self.assertEqual([e[0] for e in first["exps"]], ["sen/159-PE-2025"])
        self.assertEqual(first["orders"], ["OD-699/2025"])
        self.assertEqual((first["vote_type"], first["result"], first["majority"]),
                         ("EN GENERAL", "AFIRMATIVO", "SIMPLE"))
        self.assertTrue(first["has_detail"])
        # An article vote that names only the Orden del Día.
        self.assertEqual(actas[2]["exps"], [])
        self.assertEqual(actas[2]["orders"], ["OD-367/2026"])

    def test_a_row_published_as_pdf_only_keeps_the_acta_id(self):
        (row,) = arr.parse_actas(fixture("actas_2025.html"))
        self.assertFalse(row["has_detail"])
        self.assertEqual(row["key"], "sen-acta-2603")


class DetailTests(unittest.TestCase):
    def test_counts_time_and_positions(self):
        d = arr.parse_acta_detail(fixture("acta_2623.html"))
        self.assertEqual(d["time"], "01:21")
        self.assertEqual(d["counts"], {"ayes": 42, "noes": 30, "abstentions": 0, "absent": 0})
        self.assertEqual(len(d["votes"]), 6)
        self.assertEqual(d["votes"][0], {"id": "540", "name": "MENDOZA, SANDRA MARIELA",
                                         "bloc": "CONVICCIÓN FEDERAL", "province": "TUCUMÁN",
                                         "position": "NEGATIVO"})

    def test_former_senators_come_without_an_id(self):
        d = arr.parse_acta_detail(fixture("acta_2473.html"))
        unlinked = [v for v in d["votes"] if v["id"] is None]
        self.assertEqual([v["name"] for v in unlinked],
                         ["ROMERO, JUAN CARLOS", "RODAS, ANTONIO JOSÉ", "PILATTI VERGARA, MARÍA INÉS"])
        # A cancelled vote prints a blank position: kept as NULL, not invented.
        self.assertIsNone(unlinked[1]["position"])

    def test_historic_roster_resolves_by_exact_name_only(self):
        roster = arr.HistoricRoster(raw=fixture("senadores_historico.json"))
        self.assertEqual(roster("ROMERO, JUAN CARLOS", "2024-06-12"), "35")
        self.assertEqual(roster("RODAS, ANTONIO JOSE", "2024-06-12"), "500")   # accent-blind
        self.assertIsNone(roster("ROMERO, JUAN", "2024-06-12"))                # never a guess
        self.assertIsNone(roster("NOBODY, AT ALL", "2024-06-12"))


class ExpedienteTests(unittest.TestCase):
    def test_ver_exp(self):
        e = arr.parse_ver_exp(fixture("verexp_33-CD-2025.html"))
        self.assertEqual(e["title"], "PROYECTO DE LEY EN REVISION DE REGIMEN PENAL JUVENIL.")
        self.assertEqual(e["exp_other"], "dip/10-PE-2024")
        self.assertEqual(e["law"], "Ley 27801")

    def test_register_row(self):
        rows = json.loads(fixture("hcdn_proyectos.json"))["result"]["records"]
        rec = arr.proyecto_record(rows[0])
        self.assertEqual(rec["exp_key"], "dip/4399-D-2026")
        self.assertEqual((rec["chamber"], rec["tipo"], rec["year"], rec["published"]),
                         ("diputados", "LEY", 2026, "2026-09-01"))
        self.assertEqual(rec["publication"], "HCDN144TP124")


class EntityTests(unittest.TestCase):
    def test_register_titles_are_unescaped(self):
        rec = arr.proyecto_record({"EXP_DIPUTADOS": "5270-D-2026", "TIPO": "RESOLUCION",
                                   "TITULO": "EXPRESAR BENEPLACITO POR EL 20&deg; ANIVERSARIO DE LA LEY 26150",
                                   "PUBLICACION_FECHA": "2026-10-05T00:00:00"})
        self.assertEqual(rec["title"], "EXPRESAR BENEPLACITO POR EL 20° ANIVERSARIO DE LA LEY 26150")


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wl = os.path.join(self.tmp, "watchlist-ar.yaml")
        with open(self.wl, "w", encoding="utf-8") as fh:
            fh.write('expedientes:\n  "dip/4399-D-2026": {areas: [1], why: "test"}\n')

    def test_without_a_spanish_file_nothing_is_classified(self):
        tax = arr.load_terms(os.path.join(self.tmp, "absent.yaml"))
        res = arr.classify_bill(tax, arr.empty_watchlist(), "dip/1-D-2026",
                                "DEROGACION DE LA LEY 27.610 DE ACCESO A LA INTERRUPCION VOLUNTARIA "
                                "DEL EMBARAZO", wl_path=self.wl)
        self.assertEqual(res.issue_areas, [])

    def test_watchlist_applies_by_key_not_title(self):
        tax = arr.load_terms(os.path.join(self.tmp, "absent.yaml"))
        title = "PRESUPUESTOS MINIMOS PARA LA PREVENCION DE INCENDIOS FORESTALES"
        hit = arr.classify_bill(tax, arr.empty_watchlist(), "dip/4399-D-2026", title, wl_path=self.wl)
        miss = arr.classify_bill(tax, arr.empty_watchlist(), "dip/4400-D-2026", title, wl_path=self.wl)
        self.assertEqual(hit.issue_areas, [1])
        self.assertIn("watch:dip/4399-D-2026", hit.watchlist_hits)
        self.assertEqual(miss.issue_areas, [])

    def test_spanish_terms_match_accented_and_capitalised_text_alike(self):
        path = os.path.join(self.tmp, "taxonomy-es.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('version: t\nareas:\n  1_abortion:\n    tier1: ["interrupcion voluntaria del embarazo", IVE]\n'
                     '    tier2: []\n  5_sex_based_rights:\n    tier1: ["identidad de genero"]\n    tier2: []\n')
        tax = arr.load_terms(path)
        wl = arr.empty_watchlist()
        for title in ("DEROGACION DE LA LEY DE INTERRUPCION VOLUNTARIA DEL EMBARAZO",
                      "Derogación de la ley de interrupción voluntaria del embarazo",
                      "Modificación de la ley de IVE"):
            self.assertEqual(arr.classify_bill(tax, wl, "dip/9-D-2026", title, wl_path=self.wl).issue_areas,
                             [1], title)
        self.assertEqual(arr.classify_bill(tax, wl, "dip/9-D-2026", "Ley de identidad de género",
                                           wl_path=self.wl).issue_areas, [5])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tax = arr.load_terms(os.path.join(ROOT, "config", "no-such-taxonomy.yaml"))
        self.wl = arr.empty_watchlist()

    def test_ar_tables_are_declared(self):
        for t in ar_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_division_and_positions(self):
        a = arr.parse_actas(fixture("actas_2026.html"))[0]
        d = arr.parse_acta_detail(fixture("acta_2623.html"))
        areas, dropped = arr.store_division(self.conn, a, d, self.tax, self.wl, TODAY)
        self.assertEqual(dropped, [])
        row = self.conn.execute("SELECT date, time, ayes, noes, exp_keys, has_detail, source_url "
                                "FROM ar_divisions WHERE division_key='sen-acta-2623'").fetchone()
        self.assertEqual(row[:4], ("2026-02-11", "01:21", 42, 30))
        self.assertEqual(json.loads(row[4]), ["sen/159-PE-2025"])
        self.assertEqual(row[5], 1)
        self.assertTrue(row[6].endswith("/votaciones/detalleActa/2623"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ar_votes").fetchone()[0], 6)
        self.assertEqual(self.conn.execute(
            "SELECT position, bloc FROM ar_votes WHERE member_key='sen/540'").fetchone(),
            ("NEGATIVO", "CONVICCIÓN FEDERAL"))

    def test_unidentifiable_senator_is_dropped_not_guessed(self):
        a = dict(arr.parse_actas(fixture("actas_2026.html"))[0], key="sen-acta-2473", date="2024-06-12")
        d = arr.parse_acta_detail(fixture("acta_2473.html"))
        roster = arr.HistoricRoster(raw=json.dumps({"table": {"rows": [
            {"ID": "35", "SENADOR": "ROMERO, JUAN CARLOS", "INICIO PERIODO REAL": "2019-12-10",
             "CESE PERIODO REAL": "2025-12-09"}]}}))
        _areas, dropped = arr.store_division(self.conn, a, d, self.tax, self.wl, TODAY, resolve=roster)
        self.assertEqual(dropped, ["RODAS, ANTONIO JOSÉ", "PILATTI VERGARA, MARÍA INÉS"])
        self.assertEqual(self.conn.execute(
            "SELECT position FROM ar_votes WHERE member_key='sen/35'").fetchone(), ("AFIRMATIVO",))

    def test_an_old_acta_does_not_overwrite_a_newer_bloc(self):
        arr.store_member(self.conn, "sen/1", "senado", TODAY, name="X, Y", bloc="NEW BLOC",
                         as_of="2026-02-11")
        arr.store_member(self.conn, "sen/1", "senado", TODAY, name="X, Y", bloc="OLD BLOC",
                         as_of="2024-06-12")
        self.assertEqual(self.conn.execute("SELECT bloc FROM ar_members").fetchone(), ("NEW BLOC",))


class PullTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tax = arr.load_terms(os.path.join(ROOT, "config", "no-such-taxonomy.yaml"))
        self.wl = arr.empty_watchlist()
        self.log = []

    def pull(self, client, years=(2026,)):
        return arr.pull_senate(self.conn, client, TODAY, list(years), self.tax, self.wl,
                               log=self.log.append)

    def test_a_vote_is_read_once(self):
        client = FakeClient(senate_pages())
        s = self.pull(client)
        self.assertEqual((s["listed"], s["new"]), (3, 3))
        self.assertEqual(self.conn.execute("SELECT title, exp_other FROM ar_bills "
                                           "WHERE exp_key='sen/159-PE-2025'").fetchone(),
                         ("PROYECTO DE LEY EN REVISION DE REGIMEN PENAL JUVENIL.", "dip/10-PE-2024"))
        client.calls.clear()
        s = self.pull(client)
        self.assertEqual(s["new"], 0)
        self.assertEqual([c for c in client.calls if "detalleActa" in c or "verExp" in c], [])

    def test_a_refused_detail_page_is_a_gap_and_is_retried_next_run(self):
        s = self.pull(FakeClient(senate_pages(), fail=("detalleActa/2624",)))
        self.assertEqual((s["new"], s["gaps"]), (2, 1))
        self.assertIsNone(self.conn.execute(
            "SELECT 1 FROM ar_divisions WHERE division_key='sen-acta-2624'").fetchone())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='ar-rollcalls'")
                         .fetchone()[0], 1)
        s = self.pull(FakeClient(senate_pages()))
        self.assertEqual(s["new"], 1)

    def test_a_refused_expediente_page_is_repaired_on_a_later_run(self):
        s = self.pull(FakeClient(senate_pages(), fail=("verExp/",)))
        self.assertEqual(s["gaps"], 1)
        self.assertEqual(self.conn.execute("SELECT title FROM ar_bills WHERE exp_key='sen/159-PE-2025'")
                         .fetchone(), (None,))
        client = FakeClient(senate_pages())
        self.pull(client)
        self.assertEqual(len([c for c in client.calls if "verExp/" in c]), 1)
        self.assertIsNotNone(self.conn.execute(
            "SELECT title FROM ar_bills WHERE exp_key='sen/159-PE-2025'").fetchone()[0])

    def test_pdf_only_row_is_stored_without_positions(self):
        s = self.pull(FakeClient(senate_pages()), years=(2025,))
        self.assertEqual((s["new"], s["gaps"]), (1, 0))
        self.assertEqual(self.conn.execute("SELECT has_detail, source_url FROM ar_divisions").fetchone(),
                         (0, arr.ACTA_PDF.format(2603)))

    def test_register_first_run_walks_back_newest_first_within_the_ration(self):
        client = FakeClient({"datastore_search_sql": fixture("hcdn_proyectos.json")})
        rows, ours, gaps = arr.pull_proyectos(self.conn, client, TODAY, self.tax, self.wl,
                                              log=self.log.append, max_requests=3)
        self.assertEqual((ours, gaps), (0, 0))
        self.assertEqual(len(client.calls), 3)
        self.assertIn("2026-10-01", client.calls[0])      # this month first
        self.assertNotIn("ORDER", client.calls[0])        # no sort, no offset: see the docstring
        self.assertNotIn("OFFSET", client.calls[0])
        self.assertIn("the host's ration", self.log[-1])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ar_bills").fetchone()[0], 4)

    def test_register_windows(self):
        # Nothing stored: every month back to the floor, newest first.
        w = arr.register_windows("2026-10-09")
        self.assertEqual((len(w), w[0], w[-1]), (32, ("2026-10-01", "2026-11-01"),
                                                 ("2024-03-01", "2024-04-01")))
        # Refresh 45 days, then re-read the oldest month whole and keep going back.
        w = arr.register_windows("2026-10-09", newest="2026-10-06", oldest="2026-06-05")
        self.assertEqual(w[:4], [("2026-10-01", "2026-11-01"), ("2026-09-01", "2026-10-01"),
                                 ("2026-08-22", "2026-09-01"), ("2026-06-01", "2026-07-01")])
        # Backfill done: only the refresh.
        self.assertEqual(len(arr.register_windows("2026-10-09", newest="2026-10-06",
                                                  oldest="2024-03-04")), 3)

    def test_register_refusal_is_one_gap(self):
        client = FakeClient(fail=("datos.hcdn",))
        rows, ours, gaps = arr.pull_proyectos(self.conn, client, TODAY, self.tax, self.wl,
                                              log=self.log.append)
        self.assertEqual((rows, gaps), (0, 1))
        self.assertEqual(len(client.calls), 1)     # the host turns away persistence

    def test_a_short_senate_roster_is_refused(self):
        client = FakeClient({"ExportarListadoSenadores/json": fixture("senadores.json")})
        with self.assertRaises(ValueError):
            arr.pull_senators(self.conn, client, TODAY)
        s = arr.parse_senators(fixture("senadores.json"))
        self.assertEqual(s[0]["id"], "546")
        self.assertEqual(s[0]["name"], "ABAD, MAXIMILIANO")

    def test_votaciones_refusal_is_not_a_gap(self):
        class Opener:
            def open(self, *a, **k):
                raise TimeoutError("handshake")
        client = FakeClient()
        client._opener = Opener()
        self.assertFalse(arr.knock_votaciones(client, log=self.log.append))
        self.assertIn("still unreachable", self.log[-1])


class WiringTests(unittest.TestCase):
    def test_weekly_is_mini_first_and_watched(self):
        with open(os.path.join(ROOT, ".github", "workflows", "ar-weekly.yml"), encoding="utf-8") as fh:
            wf = fh.read()
        self.assertIn("job: AR_WEEKLY", wf)
        self.assertIn("bash jobs/ar-weekly.sh", wf)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "jobs", "ar-weekly.sh")))
        with open(os.path.join(ROOT, ".github", "workflows", "alert.yml"), encoding="utf-8") as fh:
            self.assertIn('"Argentina weekly"', fh.read())


if __name__ == "__main__":
    unittest.main()
