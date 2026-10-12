"""Mexico's state congresses (tools/mxs_collect.py, src/ingest/mxs_*.py,
src/mxs_store.py, src/mxs_edition.py) on trimmed real pages saved on 12
October 2026 (tests/fixtures/mxs/). No network."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_edition as ce  # noqa: E402
from src import db, mx_store, mxs_edition, mxs_store  # noqa: E402
from src.editions import mx  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import (mxs_ags, mxs_bc, mxs_cdmx, mxs_chih, mxs_chis, mxs_common,  # noqa: E402
                        mxs_mex, mxs_nay, mxs_oax, mxs_qroo, mxs_sin, mxs_tab,
                        mxs_tamps, mxs_yuc, mxs_slp_gazette, mxs_cam_gazette,
                        mxs_dgo_gazette, mxs_qro_gazette, mxs_pue_gazette)
from src.prov_fetch import Context  # noqa: E402
import mxs_collect  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "mxs")


def fixture(name, mode="r"):
    with open(os.path.join(FIX, name), mode, encoding=None if "b" in mode else "utf-8") as fh:
        return fh.read()


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    mxs_store.ensure_schema(conn)
    conn.execute("CREATE TABLE gaps (edition TEXT, feed TEXT, detail TEXT, "
                 "UNIQUE(edition, feed, detail))")
    conn.execute("CREATE TABLE source_runs (source TEXT PRIMARY KEY, last_run TEXT, "
                 "run_id TEXT, note TEXT)")
    return conn


class FakeClient:
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"

    def __init__(self, pages=None, json_pages=None, posts=None, blobs=None, forms=None):
        self.pages, self.json_pages, self.posts = pages or {}, json_pages or {}, posts or {}
        self.blobs = blobs or {}
        self.forms = forms or {}
        self.throttle = 1.5
        self.asked = []

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None, headers=None,
                 timeout=None):
        self.asked.append((url, headers))
        if url.endswith("/robots.txt"):
            return self.pages.get(url, "")
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.pages[url]

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.asked.append((url, None))
        if url not in self.json_pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.json_pages[url]

    def get_bytes(self, url, feed, slug, timeout=None, first_bytes=None, archive=True,
                  headers=None):
        self.asked.append((url, None))
        if url not in self.blobs:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.blobs[url]

    def post_form(self, url, fields, feed, slug, timeout=None, archive=False):
        self.asked.append((url, fields))
        if url not in self.forms:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.forms[url]

    def post_json(self, url, body, feed, slug, headers=None, timeout=None):
        self.asked.append((url, body))
        if url not in self.posts:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.posts[url]


def ctx_for(conn, client, state):
    return Context(conn, client, state, feed="mx-states", log=lambda *a: None)


class CommonTests(unittest.TestCase):
    def test_dates_in_every_form_the_states_print(self):
        for text, iso in (("06  octubre  2026", "2026-10-06"), ("8 de Octubre de 2026", "2026-10-08"),
                          ("23 de septiembre,\n 2026", "2026-09-23"), ("2026/10/08", "2026-10-08"),
                          ("29/sep/2026 ", "2026-09-29"), ("05/10/2026", "2026-10-05"),
                          ("29.09.2026", "2026-09-29"), ("8 oct 2026", "2026-10-08"),
                          ("2026-10-08T00:00:00", "2026-10-08"), ("15-11-2025", "2025-11-15")):
            self.assertEqual(mxs_common.date(text), iso, text)
        self.assertIsNone(mxs_common.date(""))
        self.assertIsNone(mxs_common.date("31/02/2026"))

    def test_party_only_where_printed(self):
        self.assertEqual(mxs_common.party_in("Grupo Parlamentario del PAN"), "PAN")
        self.assertEqual(mxs_common.party_in("MOVIMIENTO DE REGENERACIÓN NACIONAL"), "MORENA")
        self.assertEqual(mxs_common.party_in("Partido Verde Ecologista de México"), "PVEM")
        self.assertIsNone(mxs_common.party_in("Dip. Marisol Sánchez Navarro"))


class ReaderTests(unittest.TestCase):
    def test_sinaloa_api(self):
        items = mxs_sin.parse(json.loads(fixture("sin_iniciativas.json")))
        self.assertEqual(len(items), 5)
        first = items[0]
        self.assertEqual(first["source_id"], "1986")
        self.assertEqual(first["presented"], "2026-09-29")
        self.assertEqual(first["status"], "Dictamen: Se Aprueba")   # the later step wins a tie
        self.assertEqual(first["status_date"], "2026-09-30")
        self.assertEqual(items[1]["party"], "MORENA")

    def test_yucatan_keys_by_upload_id(self):
        items = mxs_yuc.parse("<table>" + fixture("yuc_iniciativas.html") + "</table>")
        self.assertEqual(items[0]["source_id"], "096dff")
        self.assertEqual(items[0]["turno"], "Justicia y Seguridad Pública")
        self.assertIn("%20", items[0]["url"])

    def test_tabasco(self):
        items = mxs_tab.parse(fixture("tab_iniciativas.html"))
        self.assertEqual(items[0]["source_id"], "LXV/603")
        self.assertEqual(items[0]["presented"], "2026-10-08")

    def test_chihuahua(self):
        items = mxs_chih.parse(fixture("chih_proceso.html"))
        self.assertEqual(items[1]["source_id"], "LXVIII/1760")
        self.assertEqual(items[1]["presented"], "2026-10-06")
        self.assertEqual(items[1]["status"], "Pendiente")
        self.assertEqual(items[1]["party"], "MORENA")

    def test_baja_california_leaves_positionings_out(self):
        items = mxs_bc.parse(fixture("bc_iniciativas.html"))
        self.assertEqual(items[0]["source_id"], "XXV/1366/23")
        self.assertEqual(items[0]["kind"], "punto")
        self.assertEqual(items[0]["status"], "APROBADO EN VOTACION ECONOMICA")
        self.assertFalse(any(it["title"].startswith("POSICIONAMIENTO") for it in items))

    def test_tamaulipas_periods_come_from_the_index(self):
        periods = mxs_tamps.periods(fixture("tamps_index.html"))
        self.assertEqual(periods[0][0], 121)
        self.assertIn("IdPeriodoCongreso=118&Legislatura=66", dict(periods)[118])
        items = mxs_tamps.parse(fixture("tamps_periodo.html"))
        self.assertEqual(items[0]["source_id"], "66/1783")
        self.assertEqual(items[0]["turno"],
                         "Estudios Legislativos Primera; Atención a Grupos Vulnerables")

    def test_cdmx_portal(self):
        items = mxs_cdmx.parse(fixture("cdmx_portal.html"))
        self.assertEqual(len(items), 20)
        self.assertEqual(items[0]["source_id"], "8328")
        self.assertEqual(items[0]["party"], "MORENA")
        self.assertIn("DIVERSIDAD SEXUAL Y DE GÉNERO", items[0]["title"])

    def test_cdmx_portal_json_form(self):
        items = mxs_cdmx.parse(fixture("cdmx_portal.json.html"))
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["source_id"], "8328")
        self.assertEqual(items[0]["turno"], "PRESUPUESTO Y CUENTA PÚBLICA")
        self.assertIsNone(items[0]["status"])      # 'abierto' is the consultation's, not ours

    def test_oaxaca_leaves_oficios_out(self):
        items = mxs_oax.parse(fixture("oax_segundo.html"))
        self.assertFalse(any(it["source_id"] == "LXVI/899" for it in items))   # an oficio
        it = next(i for i in items if i["source_id"] == "LXVI/910")
        self.assertEqual(it["party"], "PT")
        self.assertEqual(it["status"], "En Estudio")
        self.assertTrue(it["url"].startswith("https://docs66.congresooaxaca.gob.mx/"))

    def test_oaxaca_skips_an_older_legislatures_rows(self):
        row = ("<table><tr><td>2031</td><td></td><td>22-11-2023</td><td></td><td>ACUERDO</td><td></td>"
               "<td>JUCOPO</td><td></td><td>MORENA</td><td></td><td>Acuerdo.</td><td></td>"
               "<td><a href='../../docs65.congresooaxaca.gob.mx/iniciativasyacuerdos/2031.pdf'>x"
               "</a></td><td></td><td>APROBADO</td><td></td><td>APROBADO</td></tr></table>")
        self.assertEqual(mxs_oax.parse(row), [])
        self.assertEqual(len(mxs_oax.parse(row.replace("docs65", "docs66"))), 1)

    def test_chiapas_current_legislature_only(self):
        items = mxs_chis.parse(fixture("chis_trabajo.html"))
        self.assertEqual(items[0]["source_id"], "LXIX/1173")
        self.assertEqual(items[0]["status"], "Aprobado")
        self.assertEqual(items[0]["kind"], "decreto")

    def test_estado_de_mexico_sends_the_pages_own_header(self):
        conn = store()
        client = FakeClient({mxs_mex.URL: fixture("mex_iniciativas.html")})
        items = mxs_mex.collect(ctx_for(conn, client, "mex"), "2026-09-01")
        self.assertEqual(items[0]["source_id"], "LXII/1363")
        self.assertEqual(items[0]["turno"], "Recursos Hidráulicos; Desarrollo Urbano")
        self.assertEqual(items[0]["status"], "En estudio")
        sent = [h for u, h in client.asked if u == mxs_mex.URL]
        self.assertEqual(sent, [{"X-Requested-With": "XMLHttpRequest"}])

    def test_aguascalientes_and_nayarit_json(self):
        a = mxs_ags.parse(json.loads(fixture("ags_agenda.json")))
        self.assertEqual(a[0]["source_id"], "IN_LXVI_1231")
        self.assertEqual(a[0]["turno"], "COMISIÓN DE VIGILANCIA")
        n = mxs_nay.parse(json.loads(fixture("nay_iniciativas.json")))
        self.assertEqual(n[0]["source_id"], "XXXIV/362")
        self.assertEqual(n[0]["status"], "En estudio")

    def test_quintana_roo(self):
        items = mxs_qroo.parse(fixture("qroo_iniciativas.html"))
        self.assertEqual(items[0]["source_id"], "XVIII/1421")
        self.assertEqual(items[0]["status"], "Turnada")
        self.assertEqual(items[0]["presented"], "2026-10-08")

    def test_robots_disallow_is_a_gap_and_never_fetched(self):
        conn = store()
        client = FakeClient({"https://congresotabasco.gob.mx/robots.txt":
                             "User-agent: *\nDisallow: /iniciativas/\n"})
        self.assertEqual(mxs_tab.collect(ctx_for(conn, client, "tab"), "2025-09-01"), [])
        self.assertNotIn(mxs_tab.URL, [u for u, _ in client.asked])


class StoreTests(unittest.TestCase):
    def test_db_declares_and_creates_the_tables(self):
        self.assertIn("mxs_items", db.TABLES)
        self.assertIn("mxs_reads", db.TABLES)
        conn = db.init_db(db.connect(":memory:"))
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"mxs_items", "mxs_reads"} <= names)

    def test_a_status_change_without_a_date_is_dated_when_seen(self):
        conn = store()
        res = mxs_collect.classify(None, "x", "chis/LXIX/1")
        it = {"state": "chis", "source_id": "LXIX/1", "title": "t", "status": "Turnada"}
        self.assertTrue(mxs_store.upsert_item(conn, it, res, "2026-10-01"))
        row = conn.execute("SELECT status_date FROM mxs_items").fetchone()
        self.assertIsNone(row[0])                                  # first sighting: undated
        self.assertFalse(mxs_store.upsert_item(conn, dict(it, status="Aprobado"), res, "2026-10-12"))
        self.assertEqual(conn.execute("SELECT status, status_date FROM mxs_items").fetchone()[:],
                         ("Aprobado", "2026-10-12"))


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_run_state_classifies_stores_and_records_the_read(self):
        conn = store()
        page = fixture("cdmx_portal.html")
        client = FakeClient({mxs_cdmx.PAGE.format(1): page,
                             mxs_cdmx.PAGE.format(2): "<html></html>"})
        tax = mxs_collect.load_taxonomy()
        gaps = mxs_collect.run_state(conn, client, "cdmx", tax, "2026-10-01", None,
                                     "2026-10-12", "2026-10-12T10:00:00Z", log=lambda *a: None)
        self.assertEqual(gaps, 0)          # page 2 holds no cards: the read ends there
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM mxs_items").fetchone()[0], 20)
        read = conn.execute("SELECT status, items_listed, items_new FROM mxs_reads").fetchone()
        self.assertEqual(tuple(read), ("ok", 20, 20))

    def test_unbuilt_and_blocked_states_are_recorded_with_their_reason(self):
        conn = store()
        mxs_collect.run_state(conn, FakeClient(), "coah", None, None, None, "2026-10-12",
                              "2026-10-12T10:00:00Z", log=lambda *a: None)
        row = conn.execute("SELECT status, detail FROM mxs_reads WHERE state='coah'").fetchone()
        self.assertEqual(row[0], "not built")
        self.assertEqual(mxs_collect.NOT_READ["mich"][0], "unreachable")

    def test_jalisco_probe_asks_the_gazette_never_the_congress(self):
        conn = store()
        client = FakeClient({"https://periodicooficial.jalisco.gob.mx/": "x" * 5000})
        mxs_collect._PROBE_CLIENT[:] = [client]
        self.addCleanup(mxs_collect._PROBE_CLIENT.clear)
        mxs_collect.run_state(conn, client, "jal", None, None, None, "2026-10-12",
                              "2026-10-12T10:00:00Z", log=lambda *a: None)
        row = conn.execute("SELECT status, detail FROM mxs_reads WHERE state='jal'").fetchone()
        self.assertEqual(row[0], "not built")
        self.assertIn("Periódico Oficial's home page ANSWERS", row[1])

    def test_a_reader_that_raises_costs_only_its_state(self):
        conn = store()
        client = FakeClient(posts={mxs_sin.API + "obtenerIniciativas": {"grupo": "not a list"}})
        gaps = mxs_collect.run_state(conn, client, "sin", None, "2025-09-01", None, "2026-10-12",
                                     "2026-10-12T10:00:00Z", log=lambda *a: None)
        self.assertGreaterEqual(gaps, 1)
        self.assertEqual(conn.execute("SELECT status FROM mxs_reads").fetchone()[0],
                         "unreachable")

    def test_every_state_has_a_reader_or_a_reason(self):
        self.assertEqual(set(mxs_collect.READERS) | set(mxs_collect.NOT_READ),
                         set(mxs_store.STATES))
        self.assertFalse(set(mxs_collect.READERS) & set(mxs_collect.NOT_READ))


class GazetteTests(unittest.TestCase):
    """The alternative routes of 12 October 2026: decrees from the official
    gazettes of San Luis Potosí, Campeche, Durango and Querétaro, where the
    congress's own site is blocked to us."""

    def test_slp_gazette_search_json(self):
        items = mxs_slp_gazette.parse(json.loads(fixture("slp_gazette.json")))
        self.assertEqual(len(items), 7)
        first = items[0]
        self.assertEqual(first["source_id"], "po/20020")
        self.assertEqual(first["presented"], "2026-10-09")
        self.assertEqual(first["kind"], "decreto")
        self.assertTrue(first["title"].startswith("DECRETO 0611.- Que reforma"))
        self.assertTrue(any("Libertad Religiosa" in it["title"] for it in items))
        url = mxs_slp_gazette.search_url("2026-09-01", "2026-10-12")
        self.assertIn("autoridadId=287", url)
        self.assertIn("fechaInicio=2026-09-01", url)

    def test_slp_gazette_collect_asks_once_and_keeps_the_window(self):
        conn = store()
        url = mxs_slp_gazette.search_url("2026-10-01", "2026-10-12")
        client = FakeClient(json_pages={url: json.loads(fixture("slp_gazette.json"))})
        items = mxs_slp_gazette.collect(ctx_for(conn, client, "slp"), "2026-10-01",
                                        today="2026-10-12")
        self.assertEqual(len(items), 5)                    # the June items fall outside
        self.assertFalse([u for u, _h in client.asked if "congresosanluis" in u])

    def test_cam_gazette_search_page_and_edition_text(self):
        eds = mxs_cam_gazette.editions(fixture("cam_search.html"))
        self.assertEqual(len(eds), 12)
        self.assertEqual(eds[0], ("5858", "PO2748SS30092026", "2748", "SS", "2026-09-30"))
        items = mxs_cam_gazette.parse_edition(fixture("cam_po2731ss.txt"), "PO2731SS04092026",
                                              "2026-09-04")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source_id"], "po/LXV/decreto/285")
        self.assertTrue(items[0]["title"].startswith("Decreto número 285: Se reforman"))
        self.assertNotIn("para quedar como sigue", items[0]["title"])
        acuerdos = mxs_cam_gazette.parse_edition(fixture("cam_po2748ss.txt"),
                                                 "PO2748SS30092026", "2026-09-30")
        self.assertEqual([a["source_id"] for a in acuerdos],
                         ["po/2748SS/acuerdo/38", "po/2748SS/acuerdo/39"])
        # an administrative or judicial edition holds nothing of the Congress's
        self.assertEqual(mxs_cam_gazette.parse_edition(
            "PERIÓDICO OFICIAL DEL ESTADO\nSECCIÓN JUDICIAL\nDECRETO\nNúmero 1\nPRIMERO.- x",
            "PO1SS01012026", None), [])

    def test_cam_gazette_collect_reads_the_legislative_pdfs(self):
        conn = store()
        base = mxs_cam_gazette.BASE
        pages = {mxs_cam_gazette.search_url(q, "2026-09-01", "2026-10-05"): fixture("cam_search.html")
                 for q in mxs_cam_gazette.QUERIES}
        pages[base + "getDocumento/5858"] = '"202609\\/PO2748SS30092026.pdf"'
        blobs = {base + "periodicos/202609/PO2748SS30092026.pdf": b"%PDF-fake"}
        client = FakeClient(pages, blobs=blobs)
        texts = {b"%PDF-fake": fixture("cam_po2748ss.txt")}
        orig = mxs_cam_gazette.pdf_text
        mxs_cam_gazette.pdf_text = lambda raw, pages=None: texts[raw]
        self.addCleanup(setattr, mxs_cam_gazette, "pdf_text", orig)
        items = mxs_cam_gazette.collect(ctx_for(conn, client, "cam"), "2026-09-01",
                                        today="2026-10-05")
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]["url"].endswith("PO2748SS30092026.pdf"))
        self.assertFalse([u for u, _h in client.asked if "congresocam" in u])

    def test_dgo_gazette_home_and_edition(self):
        eds = mxs_dgo_gazette.editions(fixture("dgo_home.html"))
        self.assertEqual(eds[0][1:], ("2026-10-11", "No. 82"))
        items = mxs_dgo_gazette.parse_edition(fixture("dgo_periodico.html"),
                                              "/periodicos/4cae90a7-173d-4f8e-8652-720c874819ce")
        self.assertEqual([it["source_id"] for it in items], ["po/decreto/445", "po/decreto/446"])
        self.assertEqual(items[0]["presented"], "2026-10-08")
        self.assertIn("LEY DE INGRESOS DEL MUNICIPIO DE POANAS", items[0]["title"])
        # the live page repeats its data in <script> tags before the HTML
        noisy = ('<script>self.__next_f.push([1,"Lugar y Fecha: 1 de enero de 2020 ...'
                 '</p>"])</script>') + fixture("dgo_periodico.html")
        again = mxs_dgo_gazette.parse_edition(noisy, "/periodicos/x")
        self.assertEqual(again[0]["presented"], "2026-10-08")

    def test_dgo_gazette_collect_skips_editions_before_the_window(self):
        conn = store()
        base = mxs_dgo_gazette.BASE
        client = FakeClient({
            mxs_dgo_gazette.HOME: fixture("dgo_home.html"),
            base + "/periodicos/4cae90a7-173d-4f8e-8652-720c874819ce": fixture("dgo_periodico.html"),
            base + "/periodicos/88a22e57-3dcf-43d6-b7f8-089326fe38a7": "<html></html>",
        })
        items = mxs_dgo_gazette.collect(ctx_for(conn, client, "dgo"), "2026-10-07")
        self.assertEqual(len(items), 2)
        self.assertFalse([u for u, _h in client.asked if "89c70b7c" in u])   # 6 October

    def test_qro_gazette_index(self):
        items = mxs_qro_gazette.parse_index(fixture("qro_indice.txt"), 2026)
        self.assertEqual(len(items), 15)
        self.assertEqual(items[3]["source_id"], "po/2026/66/4")
        self.assertEqual(items[3]["title"],
                         "Ley que reforma el artículo 80 de la Ley de Salud del Estado de Querétaro.")
        self.assertEqual(items[3]["kind"], "decreto")
        self.assertEqual(items[6]["kind"], "punto")
        self.assertTrue(all(it["presented"] for it in items))
        # nothing from PODER EJECUTIVO or the municipalities
        self.assertFalse([it for it in items if "Los Alcanfores" in it["title"]])

    def test_qro_gazette_is_https(self):
        self.assertTrue(mxs_qro_gazette.INDEX.startswith("https://"))

    def test_gazette_items_store_and_classify(self):
        conn = store()
        tax = mxs_collect.load_taxonomy()
        items = mxs_slp_gazette.parse(json.loads(fixture("slp_gazette.json")))
        new, ours = mxs_collect.store_items(conn, tax, items, "2026-10-12")
        self.assertEqual(new, 7)
        row = conn.execute("SELECT areas FROM mxs_items WHERE title LIKE '%Libertad Religiosa%'"
                           ).fetchone()
        self.assertNotEqual(row[0], "[]")                  # religious freedom is our ground

    def test_gazette_readers_are_wired(self):
        for st in ("slp", "cam", "dgo", "qro", "pue"):
            self.assertIn(st, mxs_collect.GAZETTE)
            self.assertNotIn(st, mxs_collect.NOT_READ)
        self.assertNotIn("pue", mxs_collect.PROBE)

    def test_pue_scjn_rows_keep_the_congress_decrees_only(self):
        items = mxs_pue_gazette.parse(fixture("pue_scjn_reformas.html"))
        # 14 rows: 11 decrees and the constitutional declaratoria are kept; the
        # executive's reglamento decree and a municipal acuerdo are not.
        titles = [it["title"] for it in items]
        self.assertEqual(len(items), 12)
        self.assertTrue(all(it["source_id"].startswith("po/scjn/") for it in items))
        self.assertEqual(len({it["source_id"] for it in items}), len(items))
        first = items[0]
        self.assertEqual(first["presented"], "2026-08-10")
        self.assertEqual(first["status"], "Publicado en el Periódico Oficial")
        self.assertTrue(first["title"].startswith("DECRETO. UNICO. SE REFORMA"))
        self.assertIn("wfOrdenamientoDetalle.aspx?q=", first["url"])
        self.assertTrue(any("VIDA LIBRE DE VIOLENCIA" in t for t in titles))
        self.assertTrue(any(it["kind"] == "declaratoria" and "CONSTITUCION" in it["title"]
                            for it in items))
        self.assertFalse([t for t in titles if "AYUNTAMIENTO" in t or "SECRETARIA DE MEDIO" in t])
        # a decree whose operative words run long still names its law
        self.assertTrue(any(t.startswith("DECRETO (LEY DE ECONOMIA CIRCULAR") for t in titles))
        self.assertTrue(any("REGLAMENTO INTERIOR DEL HONORABLE CONGRESO" in t for t in titles))

    def test_pue_scjn_form_posts_the_puebla_search(self):
        fields = mxs_pue_gazette.form_fields(fixture("pue_scjn_form.html"))
        self.assertIn("__VIEWSTATE", fields)
        self.assertIn("__EVENTVALIDATION", fields)
        self.assertEqual(fields[mxs_pue_gazette.FORM + "ddlEntidad"], "20")    # PUEBLA
        self.assertEqual(fields[mxs_pue_gazette.FORM + "ddlAmbito"], "1")      # ESTATAL
        self.assertIsNone(mxs_pue_gazette.form_fields("<html>no form</html>"))

    def test_pue_collect_asks_the_court_never_puebla(self):
        conn = store()
        page = mxs_pue_gazette.PAGE
        client = FakeClient({page: fixture("pue_scjn_form.html")},
                            forms={page: fixture("pue_scjn_reformas.html")})
        items = mxs_pue_gazette.collect(ctx_for(conn, client, "pue"), "2026-07-28")
        self.assertTrue(items)
        self.assertTrue(all(it["presented"] >= "2026-07-28" for it in items))
        asked = [u for u, _ in client.asked if not u.endswith("/robots.txt")]
        self.assertEqual(asked, [page, page])                # the page, then its postback
        self.assertFalse([u for u, _ in client.asked if "puebla.gob.mx" in u
                          or "congresopuebla" in u])

    def test_pue_collect_records_the_courts_fault_as_a_gap(self):
        conn = store()
        page = mxs_pue_gazette.PAGE
        client = FakeClient({page: fixture("pue_scjn_form.html")},
                            forms={page: "<html>Object reference not set to an instance</html>"})
        ctx = ctx_for(conn, client, "pue")
        self.assertEqual(mxs_pue_gazette.collect(ctx, "2026-07-01"), [])
        self.assertIn("fault on the Court's side", ctx.gaps[0])


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.cfg = os.path.join(self.tmp, "config")
        self.eds = os.path.join(self.tmp, "editions")
        os.makedirs(self.cfg)
        os.makedirs(self.eds)
        for f in ("edition-noise-mx.yaml", "taxonomy-es.yaml"):
            shutil.copy(os.path.join(ROOT, "config", f), self.cfg)
        with open(os.path.join(self.cfg, "watchlist-mx.yaml"), "w") as fh:
            fh.write("iniciativas: {}\n")

    def conn(self):
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        mx_store.ensure_schema(c)
        mxs_store.ensure_schema(c)
        rows = (
            ("jal/LXIV/1578", "jal", "2026-10-02", None, None,
             "Iniciativa que adiciona un capítulo sobre la interrupción legal del embarazo", "[1]", 1),
            ("chih/LXVIII/774", "chih", "2025-04-15", "Dictaminada", "2026-10-05",
             "Reforma al Código Penal en materia de aborto", "[1]", 1),
            ("yuc/abc123", "yuc", "2025-02-05", "Turnada a comisión", "2026-10-06",
             "Despenalización del aborto", "[1]", 1),
            ("tab/LXV/1", "tab", "2026-10-03", None, None, "Ley de Hacienda", "[]", None),
        )
        for key, st, pres, status, sdate, title, areas, tier in rows:
            c.execute("INSERT INTO mxs_items (item_key, state, source_id, kind, title, presented, "
                      "status, status_date, areas, matched_terms, tier) VALUES "
                      "(?,?,?,?,?,?,?,?,?,'[\"aborto\"]',?)",
                      (key, st, key.split("/", 1)[1], "iniciativa", title, pres, status, sdate,
                       areas, tier))
        mxs_store.record_read(c, "chih", "mxs_chih", "ok", "fine", 10, 2, "2026-10-06",
                              "2026-10-12T10:00:00Z")
        mxs_store.record_read(c, "slp", None, "blocked", "Sucuri", None, None, None,
                              "2026-10-12T10:00:00Z")
        c.execute("INSERT INTO mxs_items (item_key, state, source_id, legislature, kind, title, "
                  "presented, status, status_date, areas, matched_terms, tier) VALUES "
                  "('qro/po/2026/80/9','qro','po/2026/80/9','LXI','decreto',"
                  "'Ley que reforma el Código Penal en materia de aborto.','2026-10-02',"
                  "'Publicado en La Sombra de Arteaga (P. O. No. 80)','2026-10-02','[1]',"
                  "'[\"aborto\"]',1)")
        mxs_store.record_read(c, "qro", "mxs_qro_gazette", "ok", "fine", 84, 1, "2026-10-02",
                              "2026-10-12T10:00:00Z")
        return c

    def test_gazette_items_say_so(self):
        text = ce.render(self.conn(), mx.COUNTRY, "2026-10-10", "2026-09-26",
                         config_dir=self.cfg, directory=self.eds)
        section = text.split("## State congresses", 1)[1]
        self.assertIn("qro/po/2026/80/9", section)
        self.assertIn("Querétaro state congress (LXI Legislature) (from the official gazette)",
                      section)
        self.assertIn("Querétaro (from the official gazette)", section)   # coverage line

    def test_state_section_in_the_mexican_edition(self):
        text = ce.render(self.conn(), mx.COUNTRY, "2026-10-10", "2026-09-26",
                         config_dir=self.cfg, directory=self.eds)
        self.assertIn("## State congresses", text)
        section = text.split("## State congresses", 1)[1]
        self.assertIn("Jalisco state congress", section)
        self.assertIn("interrupción legal del embarazo", section)
        self.assertIn("jal/LXIV/1578", section)
        self.assertIn("chih/LXVIII/774", section)          # a dated stage: moved
        self.assertIn("Dictaminada", section)
        self.assertNotIn("yuc/abc123", section)            # a turn to committee is no stage
        self.assertNotIn("tab/LXV/1", section)             # off our ground
        self.assertIn("Read cleanly (2 of 32", section)
        self.assertIn("Not read (San Luis Potosí)", section)
        self.assertNotIn("—", text)

    def test_section_window_follows_the_edition(self):
        text = ce.render(self.conn(), mx.COUNTRY, "2026-10-10", "2026-10-04",
                         config_dir=self.cfg, directory=self.eds)
        section = text.split("## State congresses", 1)[1]
        self.assertNotIn("jal/LXIV/1578", section)         # 2 October: before this window
        self.assertIn("chih/LXVIII/774", section)

    def test_dm_notice_counts_state_items(self):
        line = mxs_edition.notice(self.conn(), "2026-10-10", dm=True)
        self.assertIn("State congresses: 3 item(s)", line)
        self.assertIsNone(mxs_edition.notice(self.conn(), "2026-10-10", dm=False))

    def test_no_store_tables_reads_as_not_read_yet(self):
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        mx_store.ensure_schema(c)
        text = ce.render(c, mx.COUNTRY, "2026-10-10", "2026-10-03", config_dir=self.cfg,
                         directory=self.eds)
        self.assertIn("The state congresses have not been read yet", text)


if __name__ == "__main__":
    unittest.main()
