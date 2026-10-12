"""Parity phases, set B (10 October 2026): UY5 Diario vote totals, BO4
Bolivian written questions, X7 OCR guard. Fixtures only, no network."""

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import courts, db, latam, ocr  # noqa: E402

TODAY = "2026-10-10"


def tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fixture(*parts):
    with open(os.path.join(ROOT, "tests", "fixtures", *parts), encoding="utf-8") as fh:
        return fh.read()


class NumberWordsTests(unittest.TestCase):
    def setUp(self):
        self.w = tool("uy_diario").words_to_int

    def test_words(self):
        for text, n in (("noventa y tres", 93), ("Sesenta y cuatro", 64), ("veintinueve", 29),
                        ("treinta y un", 31), ("cero", 0), ("cien", 100), ("Cincuenta", 50),
                        ("cincu enta y dos", 52), ("ochenta y cuarto", 84)):
            self.assertEqual(self.w(text), n, text)
        self.assertIsNone(self.w("El resultado es"))


class DiarioTests(unittest.TestCase):
    def setUp(self):
        self.mod = tool("uy_diario")
        self.text = fixture("uy", "diario-4578-excerpt.txt")

    def test_results(self):
        p = self.mod.parse_result
        self.assertEqual(p("Sesenta y cuatro votos afirmativos y veintinueve votos negativos en "
                           "noventa y tres presentes: AFIRMATIVA"),
                         {"yes": 64, "no": 29, "present": 93, "result": "AFIRMATIVA",
                          "electronic": 1})
        self.assertEqual(p("Ochenta y seis votos afirmativos y cero votos neg ativos en ochenta y "
                           "seis presentes: AFIRMATIVA")["no"], 0)
        self.assertEqual(p("Setenta y cuatro en setenta y cinco: AFIRMATIVA")["present"], 75)
        self.assertEqual(p("Setenta y tres por la afirmativa: AFIRMATIVA")["yes"], 73)
        self.assertEqual(p("Setenta votos afirmativos en setenta presentes: AFIRMATIVA")["present"], 70)
        self.assertIsNone(p("El resultado es: AFIRMATIVA")["yes"])

    def test_euthanasia_sitting(self):
        votes = self.mod.parse_diario(self.text)
        ours = [v for v in votes if v["section_no"] == 43]
        self.assertEqual(len(ours), 10)
        self.assertTrue(all(v["carpeta"] == "133/2025" for v in ours))   # from the Sumario
        general = ours[0]
        self.assertEqual((general["yes"], general["no"], general["present"], general["result"]),
                         (64, 29, 93, "AFIRMATIVA"))
        self.assertIn("discusión particular", general["question"])
        additive = [v for v in ours if v["result"] == "NEGATIVA"][0]
        self.assertEqual((additive["yes"], additive["no"]), (30, 63))
        self.assertIn("votación n.º 7", additive["question"])
        self.assertNotIn("Sumario", " ".join(v["section_title"] for v in votes))

    def test_store_and_latam(self):
        conn = db.init_db(db.connect(":memory:"))
        votes = self.mod.parse_diario(self.text)
        n = self.mod.store(conn, 4578, "2026-09-20", 272, self.text, votes,
                           courts.load_taxonomy("uy"), TODAY)
        self.assertEqual(n, 1)                 # Muerte digna, area 2
        items = latam.items_uy_diario(conn, "2026-09-10", "2026-10-10", {})
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual((it["kind"], it["key"], it["areas"]), ("vote", "Diario 4578 section 43", [2]))
        self.assertIn("totals only", it["lines"][0])
        self.assertIn("64 for, 29 against, 93 present", " ".join(it["lines"]))
        # Read again: replaced, not doubled.
        self.mod.store(conn, 4578, "2026-09-20", 272, self.text, votes, None, TODAY)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM uy_diario_votes").fetchone()[0],
                         len(votes))

    def test_pending_is_newest_first_l_only(self):
        conn = db.init_db(db.connect(":memory:"))
        for d, leg, date in ((4578, "L", "2025-08-12"), (4636, "L", "2026-07-14"),
                             (4400, "XLIX", "2024-01-01")):
            conn.execute("INSERT INTO uy_sittings (chamber, diario, legislature, date, url) "
                         "VALUES ('representantes',?,?,?,?)", (d, leg, date, "http://x/d%d.pdf" % d))
        self.assertEqual([r[0] for r in self.mod.pending(conn, 10)], [4636, 4578])
        self.assertEqual(len(self.mod.pending(conn, 10, True)), 3)


class BoliviaQuestionTests(unittest.TestCase):
    def setUp(self):
        self.mod = tool("bo_questions")
        self.conn = db.init_db(db.connect(":memory:"))
        self.conn.execute("INSERT INTO bo_members (member_key, chamber, name) VALUES "
                          "('senado/101', 'senado', 'Wanda Ximena Medrano Hervas'), "
                          "('diputados/santos-mamani-espinoza', 'diputados', 'Santos Mamani Espinoza')")

    def test_number(self):
        self.assertEqual(self.mod.number_of("P.I.E. N°1039/2025-2026 RESPUESTA"),
                         ("PIE", 1039, "2025-2026"))
        self.assertEqual(self.mod.number_of("P.I.E. N° 0957/2024-2025"), ("PIE", 957, "2024-2025"))

    def test_senado(self):
        known, _ = self.mod.members(self.conn)
        recs = json.loads(fixture("bo", "sen_pie.json"))["data"]["data"]
        got = self.mod.parse_senado(recs, known)
        first = got[0]
        self.assertEqual(first["question_key"], "senado/PIE 1039/2025-2026")
        self.assertEqual(first["askers"], ["Wanda Ximena Medrano Hervas"])
        self.assertEqual(first["asker_keys"], ["senado/101"])
        self.assertEqual(first["answered"], "2026-06-25")
        self.assertTrue(first["answer_url"].startswith("https://apisi.senado.gob.bo/images/"))
        multi = [q for q in got if len(q["askers"]) > 1][0]
        self.assertTrue(any(k is None for k in multi["asker_keys"]) or all(multi["asker_keys"]))

    def test_diputados_and_store(self):
        _, by_name = self.mod.members(self.conn)
        posts = json.loads(fixture("bo", "dip_pie.json"))
        got = self.mod.parse_diputados(posts, by_name)
        q = got[0]
        self.assertEqual(q["question_key"], "diputados/PIE 957/2024-2025")
        self.assertEqual(q["date"], "2025-08-08")
        self.assertEqual(q["asker_keys"], ["diputados/santos-mamani-espinoza"])
        tax = courts.load_taxonomy("bo")
        for one in got:
            self.mod.upsert(self.conn, one, tax, TODAY)
        # The same printed number under another record id is kept apart.
        twin = dict(got[0], source_id=999999)
        self.mod.upsert(self.conn, twin, tax, TODAY)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM bo_questions").fetchone()[0],
                         len(got) + 1)

    def test_latam_item(self):
        self.conn.execute(
            "INSERT INTO bo_questions (question_key, chamber, date, addressee, summary, askers, "
            "areas, tier, answered) VALUES ('senado/PIE 887/2025-2026', 'senado', '2026-09-29', "
            "'Ministerio de Gobierno', 'Informe sobre la denuncia contra la Iglesia', "
            "'[\"Judith Rosario Garcia Coca\", \"senado/7\"]', '[8]', 2, '2026-10-01')")
        items = latam.items_bo_questions(self.conn, "2026-09-10", "2026-10-10", {})
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual((it["kind"], it["status"]), ("question", "answered on 2026-10-01"))
        self.assertIn("by Judith Rosario Garcia Coca (Senado)", it["lines"][0])


class OcrGuardTests(unittest.TestCase):
    def test_skips_cleanly_without_tesseract(self):
        with mock.patch.object(ocr, "command", return_value=None):
            self.assertFalse(ocr.available("spa"))
            self.assertIn("not installed", ocr.why_not("spa"))
            self.assertIsNone(ocr.pdf_text(b"%PDF-1.4", "spa"))

    def test_needs_language_data(self):
        def run(args, **kw):
            return subprocess.CompletedProcess(args, 0, stdout="List of available languages (2):\neng\nosd\n")
        with mock.patch.object(ocr, "command", return_value="/x/tesseract"):
            self.assertFalse(ocr.available("spa", run=run))
            self.assertIn("tesseract-lang", ocr.why_not("spa", run=run))

    def test_reads_when_available(self):
        def run(args, **kw):
            if "--list-langs" in args:
                return subprocess.CompletedProcess(args, 0, stdout="List of available languages (2):\nspa\nhrv\n")
            return subprocess.CompletedProcess(args, 0, stdout="SI 64 NO 29")
        with mock.patch.object(ocr, "command", return_value="/x/tesseract"), \
                mock.patch.object(ocr, "page_images", return_value=[(1, [("p1.jpg", b"jpg")])]):
            self.assertEqual(ocr.pdf_text(b"%PDF", "spa", run=run), [(1, "SI 64 NO 29")])

    def test_peru_step_skips(self):
        mod = tool("pe_ocr")
        conn = db.init_db(db.connect(":memory:"))
        lines = []
        with mock.patch.object(ocr, "command", return_value=None):
            self.assertIsNone(mod.run(conn, None, TODAY, log=lines.append))
        self.assertTrue(lines[0].startswith("[skip] pe-ocr"))


if __name__ == "__main__":
    unittest.main()
