"""Peru gov_docs reader (src/gov_doc_sources/pe.py): El Peruano's Normas
Legales, national issuers. Fixtures captured live on 16 October 2026 and
trimmed (tests/fixtures/gov_docs/pe/): nine articles of two Normas/Filtro
replies (16 July to 16 October), and one draft norm's own page cut to its text."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import pe  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "pe")
TODAY = "2026-10-16"


def text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    def __init__(self):
        self.posts, self.gets = [], []

    def post_form(self, url, fields, feed, slug, **kw):
        self.posts.append((url, fields))
        return text("filtro.html")

    def get_text(self, url, feed, slug, **kw):
        self.gets.append(url)
        if url.endswith("/EX/2563534-1"):
            return text("dispositivo-2563534-1.html")
        raise RuntimeError("HTTP Error 404: Not Found")


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.got = {e["doc_id"]: e for e in pe.parse_filter(text("filtro.html"))}

    def test_national_issuers_only(self):
        self.assertFalse([e for e in self.got.values() if e["body"].startswith(("Municipalidad",
                                                                                "Gobierno Regional"))])
        self.assertEqual(len(self.got), 7)

    def test_fields_and_types(self):
        d = self.got["nl:2563534-1"]
        self.assertEqual(d["doc_type"], "regulation_draft")
        self.assertEqual(d["body"], "Educación")
        self.assertEqual(d["published"], "2026-10-12")
        self.assertIn("disciplina escolar", d["title"])
        self.assertIn("edición extraordinaria", d["status"])
        self.assertEqual(self.got["nl:2535573-1"]["doc_type"], "regulation_draft")   # consulta pública del proyecto
        self.assertEqual(self.got["nl:2554062-1"]["doc_type"], "regulation")
        self.assertEqual(self.got["nl:2554042-4"]["doc_type"], "regulation")      # a decreto supremo
        self.assertEqual(pe.doc_type("LEY N° 32600", "Ley que ..."), "law")

    def test_comment_period(self):
        self.assertEqual(pe.closing_from_page(text("dispositivo-2563534-1.html"), "2026-10-12"),
                         ("2026-10-27", "15 días calendario para comentarios"))
        sbs = ("<p>El plazo para que el público en general pueda remitir a la Superintendencia sus "
               "comentarios y observaciones sobre el proyecto es de dieciocho (18) días calendario, "
               "contados desde el día siguiente de la fecha de publicación</p>")
        self.assertEqual(pe.closing_from_page(sbs, "2026-10-05")[0], "2026-10-23")
        self.assertEqual(pe.closing_from_page("<p>plazo de treinta (30) días hábiles</p>", "2026-10-14"),
                         (None, "30 días hábiles para comentarios (no fecha calculada)"))

    def test_form(self):
        self.assertEqual(pe.filter_fields("2026-09-26", "2026-10-16"),
                         {"cddesde": "26/09/2026", "cdhasta": "16/10/2026", "btnBuscar": "Filtrar",
                          "tipo": ""})
        self.assertTrue(pe.filter_url(TODAY).endswith("dateparam=10%2F16%2F2026%2000%3A00%3A00"))


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "pe", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertEqual(len(client.posts), 1)
        # every draft's own page is asked for (three answer 404 here: kept without a date)
        self.assertEqual(len(client.gets), 4)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='pe'")}
        # on our ground (tier 1, area 8): the Director General of Justice and Religious Freedom,
        # published 14 September, inside the 92-day window
        self.assertEqual(set(rows), {"nl:2554062-1"})
        self.assertEqual(json.loads(rows["nl:2554062-1"]["areas"]), [8])
        self.assertEqual(rows["nl:2554062-1"]["body"], "Justicia y Derechos Humanos")

    def test_a_draft_on_our_ground_carries_its_deadline(self):
        """Synthetic: the captured MINEDU draft with a title our taxonomy knows,
        to show the deadline path end to end (the live week had no draft on our ground)."""
        page = text("filtro.html").replace("disciplina escolar", "educaci&#243;n sexual integral")
        client = FakeClient()
        client.post_form = lambda *a, **k: page
        conn = db.init_db(db.connect(":memory:"))
        G.collect(conn, "pe", client, TODAY, log=lambda *a: None)
        due = G.deadline_rows(conn, "pe", TODAY, "2026-12-31")
        self.assertEqual([(r["doc_id"], r["closing_date"]) for r in due], [("nl:2563534-1", "2026-10-27")])


if __name__ == "__main__":
    unittest.main()
