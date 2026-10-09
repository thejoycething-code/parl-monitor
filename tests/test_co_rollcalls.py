"""Colombia's Congress: bills, attendance, Senate roll calls (tools/co_rollcalls.py).

No network. The fixtures under tests/fixtures/co are REAL, trimmed: whole
records cut from the answers the collector archived on 9 October 2026,
nothing edited inside a record. Two counters were edited to match the trim:
`total` and `total_pages` in camara_ajax_2026-2027.json, and `total_results`
in the two senado_*.json files. camara_page_excerpt.html is the one
<script> block of the Cámara register page that carries the nonce.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import co_store, db  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "co")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cor = _load("co_rollcalls")
TODAY = "2026-10-09"
WL = os.path.join(ROOT, "config", "watchlist-co.yaml")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def fjson(name):
    return json.loads(fixture(name))


class FakeClient:
    """Serves fixtures: GETs by URL prefix, POSTs by (url, a distinguishing
    field). Anything else raises FetchError, as the real client does."""

    def __init__(self, gets=None, posts=None, fail_posts=0):
        self.gets = dict(gets or {})
        self.posts = dict(posts or {})
        self.fail_posts = fail_posts
        self.asked = []

    def _find_get(self, url):
        self.asked.append(url)
        for prefix, body in self.gets.items():
            if url.startswith(prefix):
                return body
        raise FetchError(url, "co", "x", 1, "404")

    def get_text(self, url, feed, slug, **kw):
        return self._find_get(url)

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._find_get(url))

    def post_form(self, url, fields, feed, slug, **kw):
        self.asked.append((url, dict(fields)))
        if self.fail_posts:
            self.fail_posts -= 1
            raise FetchError(url, feed, slug, 1, "Remote end closed connection without response")
        tag = fields.get("legislatura")
        if (url, tag) in self.posts:
            return self.posts[(url, tag)]
        raise FetchError(url, feed, slug, 1, "404")


def full_client(**kw):
    ajax = fixture("camara_ajax_2026-2027.json")
    empty = json.dumps({"success": True, "data": {"items": [], "total": 0, "total_pages": 0}})
    nothing = json.dumps({"success": True, "data": [], "message": "", "total_results": 0})
    return FakeClient(
        gets={cor.CAMARA_PAGE: fixture("camara_page_excerpt.html"),
              cor.DATOS.format(cor.CAMARA_DATASET): fixture("datos_kcxp-nxum.json"),
              cor.DATOS.format(cor.ATTENDANCE_DATASET): fixture("datos_48i3-vuny.json"),
              cor.DATOS.format(cor.SENATE_VOTES_DATASET): fixture("datos_ucmr-52df.json")},
        posts={(cor.CAMARA_AJAX, "20"): ajax, (cor.CAMARA_AJAX, "13"): empty,
               (cor.SENADO_SEARCH.format("pdly"), "2026-2027"): fixture("senado_pdly_2026-2027.json"),
               (cor.SENADO_SEARCH.format("pal"), "2026-2027"): fixture("senado_pal_2026-2027.json"),
               (cor.SENADO_SEARCH.format("pdly"), "2025-2026"): nothing,
               (cor.SENADO_SEARCH.format("pal"), "2025-2026"): nothing},
        **kw)


def store():
    return db.init_db(db.connect(":memory:"))


def quiet(*_a, **_k):
    return None


class KeyTests(unittest.TestCase):
    def test_camara_numbers(self):
        self.assertEqual(cor.bill_key("426/2026C", "camara"), "camara/2026/426")
        # The trap: a two-digit alternative tried first read '2026' as '20'.
        self.assertEqual(cor.bill_key("114/2026C", "camara"), "camara/2026/114")
        self.assertEqual(cor.bill_key("058/2026C", "camara"), "camara/2026/58")

    def test_senate_numbers(self):
        self.assertEqual(cor.bill_key("289/26", "senado"), "senado/2026/289")
        self.assertEqual(cor.bill_key("068/2025S", "camara"), "senado/2025/68")
        self.assertEqual(cor.bill_key("152/26 Acum 157/26", "senado"), "senado/2026/152")

    def test_senate_actos_have_their_own_series(self):
        self.assertEqual(cor.bill_key("001/26", "senado", acto=True), "senado/2026/AL1")
        self.assertEqual(cor.bill_key("001/26", "senado"), "senado/2026/1")
        # The Cámara numbers both kinds in one series: no prefix.
        self.assertEqual(cor.bill_key("114/2026C", "camara", acto=True), "camara/2026/114")
        self.assertEqual(cor.split_key("senado/2026/AL1"), ("senado", 2026, 1))

    def test_no_number(self):
        for raw in ("No aplica", "", None, "S/N"):
            self.assertIsNone(cor.bill_key(raw, "camara"))

    def test_question_names_a_bill(self):
        self.assertEqual(cor.question_bill(
            "Ponencia Para Segundo Debate al Proyecto de Ley Orgánica 002 de 2016 Senado, "
            "004 de 2016 Cámara."), "senado/2016/2")
        self.assertEqual(cor.question_bill(
            "FAST TRACK - Ponencia para Segundo debate al Proyecto de Acto Legislativo número "
            "02 de 2017 Senado, 002 de 2016 Cámara (acumulado)"), "senado/2017/AL2")
        self.assertEqual(cor.question_bill(
            "Aprobación del título y la continuidad del trámite para segundo debate del Acto "
            "Legislativo 38 de 2019 Senado."), "senado/2019/AL38")
        self.assertIsNone(cor.question_bill("Aprobación sesión permanente."))

    def test_dates(self):
        self.assertEqual(cor._date("2026 Sep 11 12:00:00 AM"), "2026-09-11")
        self.assertEqual(cor._date("2026/10/06"), "2026-10-06")
        self.assertEqual(cor._date("1/10/2026"), "2026-10-01")
        self.assertIsNone(cor._date("No Aplica"))

    def test_member_keys_fold_accents_and_case(self):
        self.assertEqual(cor.name_key("senado", "Asthon Giraldo Álvaro Antonio"),
                         "senado/asthon giraldo alvaro antonio")
        self.assertEqual(cor.name_key("camara", "  ABDALLA  OLIVERA JOSÉ LUIS"),
                         "camara/abdalla olivera jose luis")


class ParseTests(unittest.TestCase):
    def test_camara_listing(self):
        bills = {b["bill_key"]: b for b in cor.parse_camara_items(
            fjson("camara_ajax_2026-2027.json")["data"]["items"])}
        self.assertEqual(len(bills), 5)
        b = bills["camara/2026/423"]
        self.assertEqual(b["other_key"], "senado/2025/68")
        self.assertEqual(b["nickname"], "LEY MARUJA VIERA")
        self.assertIn("Andrés Felipe Jiménez Vargas", b["authors"])
        self.assertEqual(b["committee"], "Comisión Primera Constitucional Permanente")
        self.assertEqual(b["url"], "https://www.camara.gov.co/ley-maruja-viera/")
        # Two bills, one nickname: the key keeps them apart.
        self.assertEqual(bills["camara/2026/361"]["nickname"], bills["camara/2026/58"]["nickname"])
        self.assertEqual(bills["camara/2026/58"]["status"], "Retirado")
        # A non-member author (otros_autores) is kept.
        self.assertIn("Judicatura", bills["camara/2026/426"]["authors"])

    def test_camara_open_data(self):
        rows = cor.parse_camara_datos(fjson("datos_kcxp-nxum.json"))
        b = rows["camara/2026/114"]
        self.assertEqual(b["kind"], "Acto Legislativo")
        self.assertEqual(b["filed_at"], "2026-07-28")
        self.assertIn("vida", b["objeto"].lower())
        self.assertIsNone(b["other_key"])          # 'No aplica'
        self.assertTrue(b["url"].startswith("https://www.camara.gov.co/"))

    def test_nonce(self):
        self.assertEqual(cor.camara_nonce(fixture("camara_page_excerpt.html")), "e2ce7480b0")
        self.assertIsNone(cor.camara_nonce("<html>no config</html>"))

    def test_senate_register(self):
        pdly = cor.parse_senado(fjson("senado_pdly_2026-2027.json"), "2026-2027", "pdly")
        pal = cor.parse_senado(fjson("senado_pal_2026-2027.json"), "2026-2027", "pal")
        keys = {b["bill_key"] for b in pdly + pal}
        self.assertEqual(keys, {"senado/2026/211", "senado/2026/152", "senado/2026/1",
                                "senado/2026/AL1"})
        self.assertEqual([b["kind"] for b in pal], ["Acto Legislativo"])

    def test_attendance(self):
        members, marks = cor.parse_attendance(fjson("datos_48i3-vuny.json"))
        self.assertEqual(len(members), 2)
        self.assertEqual(members[1]["party"], "CAMBIO RADICAL")
        # Nine sittings, two of them joint sittings on the same day (20 July).
        self.assertEqual(len([m for m in marks if m["member_key"] == members[1]["member_key"]]), 9)
        same_day = [m for m in marks if m["date"] == "2026-07-20"
                    and m["member_key"] == members[1]["member_key"]]
        self.assertEqual(len(same_day), 2)
        self.assertTrue(all(m["joint"] == 1 for m in same_day))

    def test_senate_votes(self):
        divisions = cor.parse_senate_votes(fjson("datos_ucmr-52df.json"))
        self.assertEqual(len(divisions), 2)
        jep = next(d for d in divisions.values() if d["date"] == "2017-03-17")
        self.assertEqual(jep["bill_key"], "senado/2017/AL2")
        self.assertEqual(sorted(jep["votes"].values()), ["no", "yes", "yes"])
        self.assertEqual(jep["votes"]["senado/merheg marun juan samy"], "no")


class ClassifyTests(unittest.TestCase):
    def test_without_a_spanish_taxonomy_only_the_watchlist_counts(self):
        self.assertIsNone(cor.load_taxonomy_es(os.path.join(FIX, "no-such-taxonomy.yaml")))
        areas, terms, tier = cor.classify(None, "camara/2026/114", "aborto eutanasia", wl_path=WL)
        self.assertEqual(areas, [1])
        self.assertEqual(terms, ["watchlist-co:camara/2026/114"])
        self.assertEqual(tier, 1)
        self.assertEqual(cor.classify(None, "camara/2026/426", "aborto", wl_path=WL), ([], [], None))

    def test_watchlist_is_keyed_never_by_title(self):
        wl = co_store.watchlist(WL)
        self.assertIn("camara/2026/361", wl)
        self.assertNotIn("camara/2026/58", wl)      # the withdrawn twin of 361
        for key in wl:
            self.assertRegex(key, r"^(camara|senado)/\d{4}/(AL)?\d+$")

    def test_spanish_terms_match_with_accents_folded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "taxonomy-es.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('version: test\nareas:\n  1_abortion:\n    tier1: ["vida en gestación", IVE]\n'
                         '    tier2: []\n  5_sex_based_rights:\n    tier1: ["identidad de género"]\n'
                         '    tier2: []\nexclusions_global: []\n')
            tax = cor.load_taxonomy_es(path)
            # Accentless capitals, as the Senate register writes them.
            self.assertEqual(cor.classify(tax, "senado/2026/9", "PROTECCION DE LA VIDA EN GESTACION",
                                          wl_path=WL)[0], [1])
            self.assertEqual(cor.classify(tax, "senado/2026/9", "la identidad de genero",
                                          wl_path=WL)[0], [5])
            # IVE is an acronym: matched with its case, not inside a word.
            self.assertEqual(cor.classify(tax, "senado/2026/9", "Archive the IVE file", wl_path=WL)[0], [1])
            self.assertEqual(cor.classify(tax, "senado/2026/9", "una ive temprana", wl_path=WL)[0], [])


class RunTests(unittest.TestCase):
    def test_full_run_stores_everything(self):
        conn = store()
        gaps = cor.run(conn, full_client(), TODAY, log=quiet, sleep=quiet)
        self.assertEqual(gaps, 0)
        n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        # Five Cámara bills from the site, plus 581/2026C that only the open
        # data carries; four Senate bills.
        self.assertEqual(n("SELECT COUNT(*) FROM co_bills WHERE chamber='camara'"), 6)
        self.assertEqual(n("SELECT COUNT(*) FROM co_bills WHERE chamber='senado'"), 4)
        row = conn.execute("SELECT objeto, filed_at, source, areas FROM co_bills "
                           "WHERE bill_key='camara/2026/114'").fetchone()
        self.assertIn("vida", row["objeto"].lower())       # merged from the open data
        self.assertEqual(row["filed_at"], "2026-07-28")
        self.assertEqual(row["source"], "camara.gov.co")
        self.assertEqual(json.loads(row["areas"]), [1])     # watchlist-co
        self.assertEqual(json.loads(conn.execute(
            "SELECT areas FROM co_bills WHERE bill_key='senado/2026/211'").fetchone()[0]), [3])
        self.assertEqual(n("SELECT COUNT(*) FROM co_members WHERE chamber='camara'"), 2)
        self.assertEqual(n("SELECT COUNT(*) FROM co_attendance"), 18)
        self.assertEqual(n("SELECT COUNT(*) FROM co_divisions"), 2)
        self.assertEqual(n("SELECT COUNT(*) FROM co_votes"), 6)
        self.assertEqual(n("SELECT yes FROM co_divisions WHERE date='2017-03-17'"), 2)
        self.assertEqual(n("SELECT COUNT(*) FROM co_members WHERE chamber='senado'"), 5)

    def test_rerun_is_idempotent_and_keeps_first_seen(self):
        conn = store()
        cor.run(conn, full_client(), "2026-10-01", log=quiet, sleep=quiet)
        before = [conn.execute("SELECT COUNT(*) FROM {0}".format(t)).fetchone()[0]
                  for t in ("co_bills", "co_members", "co_attendance", "co_divisions", "co_votes")]
        cor.run(conn, full_client(), TODAY, log=quiet, sleep=quiet)
        after = [conn.execute("SELECT COUNT(*) FROM {0}".format(t)).fetchone()[0]
                 for t in ("co_bills", "co_members", "co_attendance", "co_divisions", "co_votes")]
        self.assertEqual(before, after)
        self.assertEqual(tuple(conn.execute("SELECT first_seen, last_seen FROM co_bills "
                                            "WHERE bill_key='camara/2026/426'").fetchone()),
                         ("2026-10-01", TODAY))

    def test_a_dropped_connection_is_retried(self):
        conn = store()
        client = full_client(fail_posts=2)
        self.assertEqual(cor.run(conn, client, TODAY, log=quiet, sleep=quiet), 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM co_bills").fetchone()[0], 10)

    def test_a_dead_source_is_a_gap_not_a_crash(self):
        conn = store()
        client = full_client()
        del client.gets[cor.DATOS.format(cor.SENATE_VOTES_DATASET)]
        client.posts.pop((cor.SENADO_SEARCH.format("pal"), "2026-2027"))
        gaps = cor.run(conn, client, TODAY, log=quiet, sleep=quiet)
        self.assertEqual(gaps, 2)
        details = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed=?", (cor.FEED,))]
        self.assertTrue(any("senate votes" in d for d in details))
        self.assertTrue(any("senado register pal 2026-2027" in d for d in details))
        # Everything else still landed.
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM co_bills WHERE chamber='camara'")
                         .fetchone()[0], 6)

    def test_no_nonce_falls_back_to_the_open_data(self):
        conn = store()
        client = full_client()
        client.gets[cor.CAMARA_PAGE] = "<html>redesigned</html>"
        gaps = cor.run(conn, client, TODAY, log=quiet, sleep=quiet, do_attendance=False,
                       do_votes=False)
        self.assertEqual(gaps, 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM co_bills WHERE chamber='camara'")
                         .fetchone()[0], 3)

    def test_reclassify_lets_divisions_inherit_from_their_bill(self):
        conn = store()
        cor.run(conn, full_client(), TODAY, log=quiet, sleep=quiet)
        with tempfile.TemporaryDirectory() as tmp:
            wl = os.path.join(tmp, "wl.yaml")
            with open(wl, "w", encoding="utf-8") as fh:
                fh.write('bills:\n  "senado/2017/AL2": {areas: [8], why: test}\n')
            conn.execute("INSERT INTO co_bills (bill_key, chamber, year, number, first_seen, "
                         "last_seen) VALUES ('senado/2017/AL2','senado',2017,2,?,?)", (TODAY, TODAY))
            cor.reclassify(conn, tax=None, wl_path=wl, log=quiet)
        areas = conn.execute("SELECT areas FROM co_divisions WHERE bill_key='senado/2017/AL2'").fetchone()[0]
        self.assertEqual(json.loads(areas), [8])


class SchemaTests(unittest.TestCase):
    def test_tables_declared_and_created(self):
        conn = store()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("co_bills", "co_members", "co_attendance", "co_divisions", "co_votes"):
            self.assertIn(t, db.TABLES)
            self.assertIn(t, names)


if __name__ == "__main__":
    unittest.main()
