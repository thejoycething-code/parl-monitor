"""Panama, Asamblea Nacional: bills, stage histories, orden del dia, deputies
(tools/pa_rollcalls.py). No network: real responses saved on 9 October 2026
under tests/fixtures/pa/ (the deputies file with each deputy's e-mail and CV
link removed; the orden del dia as the text pypdf extracted from its PDF)."""

import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, pa_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "pa")


def _load():
    spec = importlib.util.spec_from_file_location(
        "pa_rollcalls", os.path.join(ROOT, "tools", "pa_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


par = _load()


def text(name):
    path = os.path.join(FIX, name)
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return fh.read().decode("utf-8")


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


TINY_TAXONOMY = """version: test
areas:
  6_parental_rights_education:
    tier1: ["educación sexual", "patria potestad"]
    tier2: []
  9_marriage_family:
    tier1: ["Código de la Familia"]
    tier2: ["Ley 46 de 2013"]
  11_migration:
    tier1: ["migrante*"]
    tier2: []
exclusions_global: [familia]
"""


def tiny_taxonomy():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(TINY_TAXONOMY)
    try:
        return par.load_taxonomy(path)
    finally:
        os.unlink(path)


def watchlist_file(body):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


class FakeSeg:
    """Stands in for the segLegis postback conversation: page n of a list,
    and stage histories by ficha. Records every call."""

    def __init__(self, pages, stages=None, fail_page=None, fail_first=False):
        self.pages, self.stages_by, self.calls = pages, stages or {}, []
        self.fail_page, self.fail_first = fail_page, fail_first

    def first(self):
        self.calls.append("first")
        if self.fail_first:
            raise FetchError("seg", "pa", "form", 4, OSError("handshake timed out"))
        return "form"

    def show_all(self, page):
        self.calls.append("show_all")
        return self.pages[1]

    def page(self, page, n):
        self.calls.append(("page", n))
        if n == self.fail_page:
            raise FetchError("seg", "pa", "page", 4, OSError("read timed out"))
        return self.pages[n]

    def stages(self, page, row):
        self.calls.append(("stages", row["ficha"]))
        return self.stages_by[row["ficha"]]


def last_page_of(page):
    """The same rows with the pager cut to nothing: what the final page looks
    like to next_page_number (no link beyond itself)."""
    import re
    return re.sub(r"__doPostBack\(&#39;dataTable&#39;,&#39;Page\$\d+&#39;\)", "", page)


class HelperTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(par.iso_dmy("08-10-2026"), "2026-10-08")
        self.assertIsNone(par.iso_dmy("3"))
        self.assertEqual(par.iso_spanish("24-noviembre-2025"), "2025-11-24")
        self.assertEqual(par.iso_spanish("ORDEN DEL DÍA JUEVES 8 DE OCTUBRE DE 2026"), "2026-10-08")
        self.assertEqual(par.iso_spanish("ORDEN DEL DÍA MIÉRCOLES 7 DE OCTUBRE DE 2026"), "2026-10-07")
        self.assertIsNone(par.iso_spanish("ORDEN DEL DÍA"))

    def test_terms_start_on_1_july_every_five_years(self):
        self.assertEqual(par.term_for("2024-07-01"), "2024-2029")
        self.assertEqual(par.term_for("2024-06-30"), "2019-2024")
        self.assertEqual(par.term_for("2026-10-08"), "2024-2029")
        self.assertEqual(par.term_for("2029-07-01"), "2029-2034")
        self.assertEqual(par.term_for("2014-07-01"), "2014-2019")

    def test_deaccent(self):
        self.assertEqual(par.deaccent("ORGÁNICA DE EDUCACIÓN, NIÑEZ"), "ORGANICA DE EDUCACION, NINEZ")


class SegLegisParseTests(unittest.TestCase):
    def test_the_bare_form_lists_nothing(self):
        """A GET shows the empty form: 'Buscar todo' has to be pressed."""
        self.assertEqual(par.parse_rows(text("seglegis-form.html.gz")), [])

    def test_page_one(self):
        page = text("seglegis-page-1.html.gz")
        rows = par.parse_rows(page)
        self.assertEqual(len(rows), 20)                       # the pager row is not a bill
        first = rows[0]
        self.assertEqual(first["ficha"], 8633)
        self.assertEqual(first["presented"], "2026-10-08")
        self.assertIsNone(first["proyecto"])                  # still an anteproyecto
        self.assertEqual(first["anteproyecto"], 203)
        self.assertEqual(first["stage"], "Preliminar")
        self.assertEqual(first["proponent"], "H.D ALAIN ALBENIS CEDEÑO HERRERA")
        self.assertEqual(first["has_document"], 0)
        self.assertEqual(first["stages_button"], "dataTable$ctl02$Button3")
        treaty = [r for r in rows if r["ficha"] == 8621][0]
        self.assertEqual((treaty["proyecto"], treaty["anteproyecto"]), (732, 100))
        self.assertEqual(treaty["stage"], "Primer Debate")
        two = [r for r in rows if r["ficha"] == 8625][0]
        self.assertEqual(two["proponent"],
                         "H.D ROGELIO RICARDO REVELLO TEM, H.D AUGUSTO EFRAÍN PALACIOS MUÑOZ")
        self.assertEqual(par.next_page_number(page, 1), 2)
        self.assertIsNone(par.next_page_number(last_page_of(page), 1))

    def test_the_real_last_page(self):
        """Page 47 of 47 on 9 October 2026: eleven bills, the oldest of the
        term (ficha 7403), and a pager that links back but not on."""
        page = text("seglegis-page-47.html.gz")
        rows = par.parse_rows(page)
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[0]["ficha"], 7403)
        self.assertIsNone(par.next_page_number(page, 47))
        self.assertTrue(all(par.term_for(r["presented"]) == "2024-2029" for r in rows))

    def test_stage_history_oldest_first(self):
        stages = par.parse_stages(text("seglegis-stages-7653.html.gz"))
        self.assertEqual(len(stages), 10)
        self.assertEqual(stages[0], (1, "2024-09-24", "Preliminar", "PRELIMINAR"))
        self.assertEqual(stages[-1], (10, "2025-11-24", "Ley", "SANCIONADO POR EL ORGANO EJECUTIVO"))
        self.assertIn((8, "2025-10-02", "Tercer Debate", "APROBADO EN III DEBATE"), stages)
        self.assertEqual(par.parse_stages(text("seglegis-page-1.html.gz")), [])

    def test_postback_fields_carry_the_page_state(self):
        page = text("seglegis-page-1.html.gz")
        f = par.form_fields(page, "dataTable", "Page$2")
        self.assertTrue(f["__VIEWSTATE"])
        self.assertTrue(f["__EVENTVALIDATION"])
        self.assertEqual((f["__EVENTTARGET"], f["__EVENTARGUMENT"]), ("dataTable", "Page$2"))
        self.assertEqual(f["txtTitulo"], "")


class PullBillsTests(unittest.TestCase):
    def setUp(self):
        page = text("seglegis-page-1.html.gz")
        self.pages = {1: page, 2: last_page_of(page)}   # page 2 repeats the rows; its pager ends
        self.stages = {r["ficha"]: text("seglegis-stages-7653.html.gz")
                       for r in par.parse_rows(page)}

    def test_walks_to_the_last_page_and_stores_unclassified(self):
        conn = store()
        seg = FakeSeg(self.pages, self.stages)
        pages, bills, ours, hist, gaps = par.pull_bills(conn, None, "2026-10-09", seg=seg,
                                                        log=lambda *a: None)
        self.assertEqual((pages, bills, ours, hist, gaps), (2, 40, 0, 0, 0))
        self.assertEqual(seg.calls, ["first", "show_all", ("page", 2)])
        row = conn.execute("SELECT term, proyecto, anteproyecto, title, stage, areas, doc_url, "
                           "stage_seen FROM pa_bills WHERE ficha=8629").fetchone()
        self.assertEqual(row[0], "2024-2029")
        self.assertEqual(row[1:3], (None, 199))
        self.assertTrue(row[3].startswith("QUE MODIFICA Y ADICIONA ARTICULOS A LA LEY 8 DE 2000"))
        self.assertEqual(row[4], "Preliminar")
        self.assertIsNone(row[5])                    # no taxonomy: unclassified, not empty
        self.assertEqual(row[6], "https://sistemas.asamblea.gob.pa/segLegis/Documents/8629.pdf")
        self.assertEqual(row[7], "2026-10-09")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pa_bills").fetchone()[0], 20)

    def test_a_moved_stage_reads_the_history(self):
        conn = store()
        par.pull_bills(conn, None, "2026-10-02", seg=FakeSeg(self.pages), log=lambda *a: None)
        conn.execute("UPDATE pa_bills SET stage='Preliminar' WHERE ficha=8613")
        seg = FakeSeg(self.pages, self.stages)
        _p, _b, _o, hist, gaps = par.pull_bills(conn, None, "2026-10-09", seg=seg,
                                                log=lambda *a: None)
        self.assertEqual((hist, gaps), (1, 0))
        self.assertIn(("stages", 8613), seg.calls)
        self.assertEqual(conn.execute("SELECT stage, stage_seen, stages_read FROM pa_bills "
                                      "WHERE ficha=8613").fetchone(),
                         ("Segundo Debate", "2026-10-09", "2026-10-09"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pa_bill_stages WHERE ficha=8613")
                         .fetchone()[0], 10)
        # an unmoved bill keeps the date its stage was first seen
        self.assertEqual(conn.execute("SELECT stage_seen FROM pa_bills WHERE ficha=8633")
                         .fetchone()[0], "2026-10-02")

    def test_a_watched_bill_gets_its_history_once(self):
        path = watchlist_file('bills:\n  8616: {areas: [12], why: "test"}\n')
        old = pa_store.WATCHLIST
        pa_store.WATCHLIST, pa_store._WATCH = path, {}
        try:
            conn = store()
            seg = FakeSeg(self.pages, self.stages)
            _p, _b, ours, hist, _g = par.pull_bills(conn, None, "2026-10-09", seg=seg,
                                                    log=lambda *a: None)
            # page 2 repeats the row: the history is read once, on page 1
            self.assertEqual((ours, hist), (2, 1))
            self.assertEqual(seg.calls.count(("stages", 8616)), 1)
            self.assertEqual(conn.execute("SELECT areas, matched_terms FROM pa_bills "
                                          "WHERE ficha=8616").fetchone(),
                             ("[12]", '["watch:8616"]'))
        finally:
            pa_store.WATCHLIST, pa_store._WATCH = old, {}
            os.unlink(path)

    def test_the_stage_cap_holds(self):
        conn = store()
        par.pull_bills(conn, None, "2026-10-02", seg=FakeSeg(self.pages), log=lambda *a: None)
        conn.execute("UPDATE pa_bills SET stage='x'")
        seg = FakeSeg(self.pages, self.stages)
        _p, _b, _o, hist, _g = par.pull_bills(conn, None, "2026-10-09", seg=seg, max_stages=3,
                                              log=lambda *a: None)
        self.assertEqual(hist, 3)

    def test_a_failed_page_is_a_gap_and_keeps_what_was_read(self):
        conn = store()
        seg = FakeSeg(self.pages, fail_page=2)
        pages, bills, _o, _h, gaps = par.pull_bills(conn, None, "2026-10-09", seg=seg,
                                                    log=lambda *a: None)
        self.assertEqual((pages, bills, gaps), (1, 20, 1))
        self.assertIn("segLegis page 2", conn.execute("SELECT detail FROM gaps").fetchone()[0])

    def test_an_unreachable_site_is_one_gap(self):
        conn = store()
        result = par.pull_bills(conn, None, "2026-10-09", seg=FakeSeg(self.pages, fail_first=True),
                                log=lambda *a: None)
        self.assertEqual(result, (0, 0, 0, 0, 1))


class SegLegisRetryTests(unittest.TestCase):
    def test_a_postback_is_retried_then_given_up(self):
        class Client:
            def __init__(self, fails):
                self.fails, self.calls = fails, 0

            def post_form(self, url, fields, feed, slug, archive=False):
                self.calls += 1
                if self.calls <= self.fails:
                    raise FetchError(url, feed, slug, 1, OSError("handshake timed out"))
                return "ok"
        waits = []
        ok = par.SegLegis(Client(2), sleep=waits.append, waits=(1, 2, 3))
        self.assertEqual(ok.post("p", "s"), "ok")
        self.assertEqual(waits, [1, 2])
        bad = par.SegLegis(Client(9), sleep=lambda s: None, waits=(1, 2, 3))
        with self.assertRaises(FetchError):
            bad.post("p", "s")


class ClassifyTests(unittest.TestCase):
    def test_accents_are_folded_on_both_sides(self):
        """segLegis types titles with or without accents; the terms carry
        them. 'EDUCACION SEXUAL' must still meet 'educación sexual'."""
        tax = tiny_taxonomy()
        areas, terms, tier = par.classify(tax, 1, "QUE REGULA LA EDUCACION SEXUAL EN LAS ESCUELAS")
        self.assertEqual((areas, tier), ([6], 1))
        areas, _t, _tier = par.classify(tax, 2, "QUE MODIFICA ARTICULOS AL CODIGO DE LA FAMILIA")
        self.assertEqual(areas, [9])
        areas, _t, _tier = par.classify(tax, 3, "QUE MODIFICA EL CÓDIGO DE LA FAMILIA")
        self.assertEqual(areas, [9])
        areas, _t, _tier = par.classify(tax, 4, "QUE CREA EL FESTIVAL DEL MANGO")
        self.assertEqual(areas, [])

    def test_no_taxonomy_means_null(self):
        self.assertEqual(par.classify(None, 99999999, "EDUCACION SEXUAL"), (None, [], None))

    def test_reclassify_offline(self):
        conn = store()
        page = text("seglegis-page-1.html.gz")
        par.pull_bills(conn, None, "2026-10-09", seg=FakeSeg({1: last_page_of(page)}),
                       log=lambda *a: None)
        conn.execute("UPDATE pa_bills SET title='QUE MODIFICA LA LEY 46 DE 2013, GENERAL DE "
                     "ADOPCIONES' WHERE ficha=8633")
        changed = par.reclassify(conn, tiny_taxonomy(), log=lambda *a: None)
        self.assertEqual(changed, 20)                       # NULL -> '[]' counts as a change
        self.assertEqual(conn.execute("SELECT areas FROM pa_bills WHERE ficha=8633").fetchone()[0],
                         "[9]")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pa_bills WHERE areas='[]'")
                         .fetchone()[0], 19)


class MembersTests(unittest.TestCase):
    class Client:
        def __init__(self, payload):
            self.payload = payload

        def get_json(self, url, feed, slug):
            return self.payload

    def test_all_71_deputies(self):
        payload = json.loads(text("members.json"))
        conn = store()
        n, gaps = par.pull_members(conn, self.Client(payload), "2026-10-09", log=lambda *a: None)
        self.assertEqual((n, gaps), (71, 0))
        row = conn.execute("SELECT name, party, province, circuit FROM pa_members "
                           "WHERE member_id=1").fetchone()
        self.assertEqual(row, ("MARCOS ENRIQUE CASTILLERO BARAHONA",
                               "Partido Revolucionario Democrático", "Herrera", "6-3"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pa_members WHERE party="
                                      "'Libre Postulación'").fetchone()[0], 20)

    def test_a_short_list_is_a_gap(self):
        payload = json.loads(text("members.json"))
        payload["data"] = payload["data"][:6]
        conn = store()
        n, gaps = par.pull_members(conn, self.Client(payload), "2026-10-09", log=lambda *a: None)
        self.assertEqual((n, gaps), (6, 1))


class AgendaTests(unittest.TestCase):
    def test_list(self):
        docs = par.parse_agenda_list(json.loads(text("agenda-list.json")))
        self.assertEqual(len(docs), 5)
        self.assertEqual(docs[0]["doc_id"], 512)
        self.assertEqual(docs[0]["date"], "2026-10-08")
        self.assertTrue(docs[0]["url"].startswith("https://www.asamblea.gob.pa/Uploads/OrdenDia/512/"))
        self.assertEqual(docs[4]["date"], "2026-10-01")      # 'JUEVES1 DE OCTUBRE' still reads

    def test_a_mistyped_year_takes_the_publication_year(self):
        """Doc 483 as listed on 9 October 2026, published the morning of
        Monday 31 August 2026 under a name dated 2025."""
        self.assertEqual(par.agenda_date("ORDEN DEL DÍA LUNES 31 DE AGOSTO DE 2025",
                                         "2026-08-31T05:45"), "2026-08-31")
        # published the day after, named correctly: the name wins
        self.assertEqual(par.agenda_date("ORDEN DEL DÍA MIÉRCOLES 8 DE SEPTIEMBRE DE 2026",
                                         "2026-09-09T05:34"), "2026-09-08")
        self.assertEqual(par.agenda_date("ORDEN DEL DÍA", "2026-09-09T05:34"), "2026-09-09")

    def test_items_of_8_october(self):
        items = par.parse_agenda_text(text("agenda-512.txt.gz"))
        self.assertEqual(len(items), 170)                     # every bill item; acta etc. skipped
        self.assertEqual(items[0]["item_no"], 4)
        self.assertEqual((items[0]["debate"], items[0]["kind"], items[0]["number"]),
                         ("Segundo", "Proyecto", 724))
        self.assertTrue(items[0]["title"].startswith("Que aprueba la Adenda No.1"))
        susp = [i for i in items if i["item_no"] == 5][0]
        self.assertEqual((susp["number"], susp["suspended"]), (425, 1))
        loose = {i["item_no"]: i["number"] for i in items if i["item_no"] in (80, 159, 173)}
        self.assertEqual(loose, {80: 387, 159: 583, 173: 705})   # 'Ley. No.' and 'Ley 583'
        self.assertEqual(sum(i["suspended"] for i in items), 7)
        self.assertFalse(any("Orden de Día" in (i["title"] or "") for i in items))

    def test_items_join_bills_on_term_and_proyecto(self):
        conn = store()
        page = text("seglegis-page-1.html.gz")
        par.pull_bills(conn, None, "2026-10-09", seg=FakeSeg({1: last_page_of(page)}),
                       log=lambda *a: None)
        conn.execute("INSERT INTO pa_agenda (doc_id, date, name, url) VALUES "
                     "(512, '2026-10-08', 'x', 'u')")
        items = par.parse_agenda_text(text("agenda-512.txt.gz"))
        par.store_agenda_items(conn, 512, "2026-10-08", items)
        self.assertEqual(conn.execute("SELECT ficha FROM pa_agenda_items WHERE number=724")
                         .fetchone()[0], 8613)               # Proyecto 724 is ficha 8613
        self.assertEqual(conn.execute("SELECT items FROM pa_agenda WHERE doc_id=512").fetchone()[0],
                         170)

    def test_a_bad_pdf_is_no_text(self):
        self.assertIsNone(par.pdf_text(b"not a pdf"))


class SchemaTests(unittest.TestCase):
    def test_tables_declared_and_created(self):
        conn = store()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in pa_store.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertIn(t, have)

    def test_the_shipped_watchlist_loads(self):
        pa_store._WATCH = {}
        self.assertEqual(pa_store.watchlist(), {})
        self.assertEqual(pa_store.watch_areas("not a ficha"), [])


if __name__ == "__main__":
    unittest.main()
