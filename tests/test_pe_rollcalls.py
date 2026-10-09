"""Peru's Congress: members, proyectos de ley and plenary votes
(tools/pe_rollcalls.py). No network: the vote texts are pypdf's own
extraction of real records archived on 9 October 2026."""

import importlib.util
import io
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, pe_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "pe")


def _load():
    spec = importlib.util.spec_from_file_location(
        "pe_rollcalls", os.path.join(ROOT, "tools", "pe_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


per = _load()
TAX = per.load_taxonomy(os.path.join(FIX, "taxonomy-es-test.yaml"))
WL = per.empty_watchlist()
TODAY = "2026-10-09"


def text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as handle:
        return handle.read()


def fixture_json(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as handle:
        return json.load(handle)


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def load_members(conn):
    for chamber, name in (("senado", "members_senado.json"),
                          ("diputados", "members_diputados.json")):
        for rec in fixture_json(name):
            per.store_member(conn, per.parse_member(chamber, rec), TODAY)


class FakeClient:
    """get_json / post_json / get_bytes from a dict of url -> payload; a
    payload that is an Exception is raised."""

    def __init__(self, routes=None, posts=None):
        self.routes = routes or {}
        self.posts = posts or []
        self.calls = []
        self.archived = []

    def _answer(self, url):
        self.calls.append(url)
        for prefix, payload in self.routes.items():
            if url.startswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise FetchError(url, "t", "t", 1, Exception("HTTP Error 400: Bad Request"))

    def get_json(self, url, feed, slug, **kw):
        return self._answer(url)

    def get_bytes(self, url, feed, slug, **kw):
        return self._answer(url)

    def post_json(self, url, body, feed, slug, **kw):
        self.calls.append(body)
        return self.posts.pop(0)

    def _archive(self, raw, feed, slug):
        self.archived.append(slug)


class SchemaTest(unittest.TestCase):
    def test_tables_declared_and_created(self):
        conn = store()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in pe_store.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertIn(t, have)


class FoldTest(unittest.TestCase):
    def test_accents_fold_on_both_sides(self):
        # The Congress's own titles drop accents; the terms carry them.
        res = per.classify_bill(TAX, WL, {"bill_key": "x", "title": "LEY DEL ABORTO TERAPEUTICO"},
                                watch={})
        self.assertEqual(res.issue_areas, [1])
        res = per.classify_bill(TAX, WL, {"bill_key": "x", "title":
                                          "LEY QUE PROMUEVE LA DONACIÓN DE ÓRGANOS"}, watch={})
        self.assertEqual(res.issue_areas, [13])

    def test_guarded_term_needs_company(self):
        noise = {"bill_key": "x", "title": "INCORPORA LA EDUCACIÓN FINANCIERA EN EL CURRÍCULO NACIONAL"}
        ours = {"bill_key": "x", "title": "RETIRA EL ENFOQUE DE GÉNERO DEL CURRÍCULO NACIONAL"}
        self.assertEqual(per.classify_bill(TAX, WL, noise, watch={}).issue_areas, [])
        self.assertEqual(per.classify_bill(TAX, WL, ours, watch={}).issue_areas, [6])

    def test_english_taxonomy_is_blind(self):
        # The fallback until taxonomy-es exists: measured blind on 15,436 titles.
        en = per.load_taxonomy(per.TAXONOMY_EN)
        res = per.classify_bill(en, WL, {"bill_key": "x", "title":
                                         "LEY QUE RECONOCE DERECHOS AL CONCEBIDO"}, watch={})
        self.assertEqual(res.issue_areas, [])


class WatchlistTest(unittest.TestCase):
    def test_watchlist_applies_by_key_never_title(self):
        watch = {"00785/2021-CR": ([1], "Ley que reconoce derechos al concebido")}
        b = {"bill_key": "00785/2021-CR", "title": "TITULO SIN TERMINOS"}
        res = per.classify_bill(TAX, WL, b, watch=watch)
        self.assertEqual(res.issue_areas, [1])
        self.assertIn("watch:00785/2021-CR", res.watchlist_hits)
        other = {"bill_key": "00786/2021-CR", "title": "TITULO SIN TERMINOS"}
        self.assertEqual(per.classify_bill(TAX, WL, other, watch=watch).issue_areas, [])

    def test_repo_watchlist_parses_and_is_keyed_by_number(self):
        watch = pe_store.watchlist()
        self.assertTrue(watch)
        for key, (areas, why) in watch.items():
            self.assertRegex(key, r"^\d{5}(-\d{4}-\d{4}-(S|CD|CR)|/\d{4}-[A-Z]+)$")
            self.assertTrue(areas)
            self.assertTrue(why)


class MembersTest(unittest.TestCase):
    def test_parse_member_from_class_list(self):
        m = per.parse_member("senado", fixture_json("members_senado.json")[0])
        self.assertEqual(m["member_key"], "senado/velasquez-garcia-miguel-angel")
        self.assertEqual(m["bancada"], "renovacion-popular")
        self.assertEqual(m["period"], "2026-2031")
        self.assertEqual(m["status"], "en-ejercicio")
        self.assertEqual(m["name"], "Velásquez García, Miguel Angel")

    def test_pull_members_pages_until_short_page(self):
        conn = store()
        sen = fixture_json("members_senado.json")
        dip = fixture_json("members_diputados.json")
        client = FakeClient({
            "https://senado.congreso.gob.pe/wp-json/wp/v2/senador?per_page=100&page=1": sen,
            "https://diputados.congreso.gob.pe/wp-json/wp/v2/diputado?per_page=100&page=1": dip[:100],
            "https://diputados.congreso.gob.pe/wp-json/wp/v2/diputado?per_page=100&page=2": dip[100:],
        })
        stored, gaps = per.pull_members(conn, client, TODAY, log=lambda *_: None)
        self.assertEqual((stored, gaps), (190, 0))
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM pe_members WHERE chamber='senado'").fetchone()[0], 60)


class BillsTest(unittest.TestCase):
    def test_parse_bill_keys_on_number_string(self):
        rec = fixture_json("spley_2026_S_page.json")["data"]["proyectos"][3]
        b = per.parse_bill(rec)
        self.assertEqual(b["bill_key"], "00010-2026-2031-S")
        self.assertEqual((b["chamber"], b["number"], b["period"]), ("senado", 10, 2026))
        self.assertEqual(b["presented"], "2026-09-30")
        self.assertEqual(len(b["authors"]), 8)
        self.assertNotIn("\n", b["title"])

    def test_pull_bills_pages_by_offset(self):
        conn = store()
        page = fixture_json("spley_2026_S_page.json")
        rest = json.loads(json.dumps(page))
        rest["data"]["proyectos"] = []      # the server's answer past the end
        client = FakeClient(posts=[page, rest])
        read, ours, gaps = per.pull_bills(conn, client, TODAY, codes=("S",), tax=TAX, wl=WL,
                                          watch={}, log=lambda *_: None)
        self.assertEqual((read, gaps), (5, 0))
        bodies = [json.loads(c) for c in client.calls]
        self.assertEqual([b["rowStart"] for b in bodies], [0, 5])
        self.assertEqual(bodies[0]["codTipoParl"], "S")

    def test_numbers_restart_per_chamber(self):
        conn = store()
        for code, key in (("S", "00012-2026-2031-S"), ("D", "00012-2026-2031-CD")):
            per.store_bill(conn, per.parse_bill({
                "perParId": 2026, "pleyNum": 12, "proyectoLey": key, "titulo": "T",
                "codTipoParl": code}), per.classify_bill(TAX, WL, {"bill_key": key, "title": "T"},
                                                         watch={}), TODAY)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pe_bills WHERE number=12").fetchone()[0], 2)
        self.assertEqual(per.resolve_bills(conn, "senado", "PROYECTO DE RESOLUCIÓN LEGISLATIVA 12, QUE"),
                         ["00012-2026-2031-S"])
        self.assertEqual(per.resolve_bills(conn, "diputados", "PROPOSICIÓN LEGISLATIVA 12, QUE"),
                         ["00012-2026-2031-CD"])


class VoteParseTest(unittest.TestCase):
    def test_senate_vote_subject_before_positions(self):
        [d] = per.parse_vote_page(text("senado_20261007_vote_10009.txt"), "senado")
        self.assertEqual(d["record"], "41010-58450-10009")
        self.assertEqual((d["date"], d["time"]), ("2026-10-07", "01:06 PM"))
        self.assertTrue(d["subject"].startswith("PROYECTO DE RESOLUCIÓN LEGISLATIVA 12,"))
        self.assertEqual((d["yes"], d["no"], d["abstain"], d["no_answer"], d["absent"]),
                         (37, 11, 1, 1, 4))
        self.assertEqual(len(d["positions"]), 60)
        self.assertEqual(d["counts_match"], 1)
        self.assertEqual(d["provisional"], 1)
        self.assertEqual(per.bill_numbers(d["subject"]), [12])
        first = d["positions"][0]
        self.assertEqual(first, {"bancada": "FP", "name_raw": "AGUINAGA RECUENCO,", "position": "SI"})
        pres = [p for p in d["positions"] if p["position"] == "PRES"]
        self.assertEqual([p["name_raw"] for p in pres], ["TORRES MORALES, MIGUEL"])

    def test_senate_vote_subject_printed_at_the_foot(self):
        [d] = per.parse_vote_page(text("senado_20261007_vote_10010.txt"), "senado")
        self.assertTrue(d["subject"].startswith("RECONSIDERACIÓN A LA VOTACIÓN"))
        self.assertNotIn("COPIA INFORMATIVA", d["subject"])
        self.assertEqual((d["yes"], d["no"]), (20, 28))
        self.assertEqual(d["counts_match"], 1)

    def test_attendance_record_is_not_a_vote(self):
        self.assertEqual(per.parse_vote_page(text("senado_20261007_attendance.txt"), "senado"), [])

    def test_attendance_and_vote_on_one_page(self):
        ds = per.parse_vote_page(text("senado_20260909_attendance_and_vote_09932.txt"), "senado")
        self.assertEqual([d["record"] for d in ds], ["40992-58350-09932"])
        d = ds[0]
        self.assertEqual(d["time"], "03:30 PM")
        self.assertTrue(d["subject"].startswith("PROYECTO DE RESOLUCIÓN LEGISLATIVA 7,"))
        self.assertEqual(d["counts_match"], 1)
        self.assertIn("SR", {p["position"] for p in d["positions"]})

    def test_diputados_cell_per_line_layout(self):
        [d] = per.parse_vote_page(text("diputados_20261006_vote_10002.txt"), "diputados")
        self.assertEqual(d["record"], "41007-58440-10002")
        self.assertEqual(len(d["positions"]), 130)
        self.assertEqual(d["counts_match"], 1)
        self.assertEqual(d["subject"], "CUESTIÓN PREVIA PARA QUE SE SOMETA A VOTACIÓN EL "
                                       "PRIMER DICTAMEN PRESENTADO EN MINORÍA")
        self.assertIn("PCO", d["bancadas"])

    def test_signed_diputados_record_drops_the_oral_vote_note(self):
        [d] = per.parse_vote_page(text("diputados_20261006_signed_vote_10003.txt"), "diputados")
        self.assertEqual(d["provisional"], 0)
        self.assertNotIn("deja constancia", d["subject"])
        self.assertIn("PROPOSICIÓN LEGISLATIVA 98", d["subject"])
        self.assertEqual(per.bill_numbers(d["subject"]), [98])

    def test_broken_layout_is_flagged_not_hidden(self):
        # pypdf put one senator's name lines out of order on this page: one
        # position is lost, and the record says its totals no longer add up.
        [d] = per.parse_vote_page(text("senado_20260930_vote_09990_broken_layout.txt"), "senado")
        self.assertEqual(len(d["positions"]), 59)
        self.assertEqual(d["counts_match"], 0)

    def test_scan_has_no_text_layer(self):
        import pypdf
        w = pypdf.PdfWriter()
        w.add_blank_page(width=595, height=842)
        buf = io.BytesIO()
        w.write(buf)
        self.assertEqual(per.parse_vote_pdf(buf.getvalue(), "senado"), (False, []))


class MemberResolveTest(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        load_members(self.conn)
        self.sen = per.member_index(self.conn, "senado")

    def test_cut_names_resolve(self):
        self.assertEqual(per.resolve_member(self.sen, "JÁUREGUI MARTÍNEZ DE"),
                         "senado/jauregui-martinez-maria-de-los-milagros")
        self.assertEqual(per.resolve_member(self.sen, "AGUINAGA RECUENCO,"),
                         "senado/aguinaga-recuenco-alejandro-aurelio")

    def test_ambiguous_surname_stays_unresolved(self):
        # Two Velasquez senators; the record cuts Fuerza Popular's to one word.
        self.assertIsNone(per.resolve_member(self.sen, "VELÁSQUEZ"))
        # The bancada breaks the tie when the groups differ.
        self.assertEqual(per.resolve_member(self.sen, "VELÁSQUEZ", "RENOVACIÓN POPULAR"),
                         "senado/velasquez-garcia-miguel-angel")
        self.assertTrue(per.resolve_member(self.sen, "VELÁSQUEZ", "FUERZA POPULAR")
                        .startswith("senado/velasquez-portocarrero"))

    def test_first_surname_inside_the_bancada_is_the_last_resort(self):
        dip = per.member_index(self.conn, "diputados")
        self.assertEqual(per.resolve_member(dip, "DUARTE PATIÑO DE PEZET,", "PARTIDO DEL BUEN GOBIERNO"),
                         "diputados/duarte-georgina")
        self.assertIsNone(per.resolve_member(dip, "DUARTE PATIÑO DE PEZET,", "FUERZA POPULAR"))

    def test_store_division_resolves_every_senator(self):
        [d] = per.parse_vote_page(text("senado_20261007_vote_10009.txt"), "senado")
        key, _areas = per.store_division(self.conn, d, "u", TAX, WL, TODAY)
        self.assertEqual(key, "senado/41010-58450-10009")
        unresolved = [r[0] for r in self.conn.execute(
            "SELECT name_raw FROM pe_votes WHERE member_key IS NULL")]
        self.assertEqual(unresolved, [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM pe_votes").fetchone()[0], 60)


class PullVotesTest(unittest.TestCase):
    def test_reads_each_file_once_and_records_scans(self):
        import pypdf
        w = pypdf.PdfWriter()
        w.add_blank_page(width=595, height=842)
        buf = io.BytesIO()
        w.write(buf)
        scan = buf.getvalue()
        media = [{"id": 1, "date": "2026-10-01T10:00:00",
                  "source_url": "https://senado.congreso.gob.pe/wp-content/uploads/2026/10/"
                                "Asistencias_y_votaciones_sesion_30_09_2026_vbo.pdf",
                  "mime_type": "application/pdf"},
                 {"id": 2, "date": "2026-10-01T10:00:00",
                  "source_url": "https://senado.congreso.gob.pe/wp-content/uploads/2026/10/agenda.pdf",
                  "mime_type": "application/pdf"}]
        client = FakeClient({
            "https://senado.congreso.gob.pe/wp-json/wp/v2/media?search=votaci&per_page=100&page=1": media,
            "https://senado.congreso.gob.pe/wp-json/wp/v2/media?search=asistencia&per_page=100&page=1": [],
            "https://diputados.congreso.gob.pe/wp-json/wp/v2/media": [],
            "https://senado.congreso.gob.pe/wp-content/uploads/2026/10/Asistencias": scan,
        })
        conn = store()
        stored, ours, gaps = per.pull_votes(conn, client, TODAY, tax=TAX, wl=WL,
                                            log=lambda *_: None)
        self.assertEqual((stored, gaps), (0, 0))
        row = conn.execute("SELECT text_layer, divisions FROM pe_vote_files").fetchall()
        self.assertEqual(row, [(0, 0)])            # the agenda is not a vote file
        self.assertEqual(client.archived, [])      # a scan is not archived
        fetched = [c for c in client.calls if c.endswith(".pdf")]
        per.pull_votes(conn, client, TODAY, tax=TAX, wl=WL, log=lambda *_: None)
        self.assertEqual([c for c in client.calls if c.endswith(".pdf")], fetched)


class ReclassifyTest(unittest.TestCase):
    def test_vote_inherits_named_bill_areas(self):
        conn = store()
        b = per.parse_bill({"perParId": 2026, "pleyNum": 98, "proyectoLey": "00098-2026-2031-CD",
                            "titulo": "LEY CON MIS HIJOS NO TE METAS", "codTipoParl": "D"})
        per.store_bill(conn, b, per.classify_bill(TAX, WL, b, watch={}), TODAY)
        [d] = per.parse_vote_page(text("diputados_20261006_signed_vote_10003.txt"), "diputados")
        _key, areas = per.store_division(conn, d, "u", TAX, WL, TODAY)
        self.assertEqual(areas, [6])
        refs = json.loads(conn.execute("SELECT bill_refs FROM pe_divisions").fetchone()[0])
        self.assertEqual(refs, ["00098-2026-2031-CD"])
        own = json.loads(conn.execute("SELECT own_areas FROM pe_divisions").fetchone()[0])
        self.assertEqual(own, [])


if __name__ == "__main__":
    unittest.main()
