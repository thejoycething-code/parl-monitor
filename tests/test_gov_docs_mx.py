"""Mexico gov_docs reader (src/gov_doc_sources/mx.py): the DOF through SIDOF's
documented web service. Fixtures captured live on 16 October 2026 and trimmed
(tests/fixtures/gov_docs/mx/): two days' notes cut to the notes the tests
use plus a few others, and one note's text cut to its first 9,000 characters."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import mx  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "mx")
TODAY = "2026-10-16"
EMPTY = {"messageCode": 200, "response": "OK", "NotasMatutinas": [], "NotasVespertinas": [],
         "NotasExtraordinarias": []}


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


class FakeClient:
    def __init__(self):
        self.urls = []

    def get_json(self, url, feed, slug, **kw):
        self.urls.append(url)
        if url == mx.DAY.format("01-10-2026"):
            return load("notas-01-10-2026.json")
        if url == mx.DAY.format("14-10-2026"):
            return load("notas-14-10-2026.json")
        if url == mx.NOTE.format(5800053):
            return load("nota-5800053.json")
        if "/notas/nota/" in url:
            raise AssertionError("unexpected note read " + url)
        return EMPTY


class ParseTests(unittest.TestCase):
    def test_day_keeps_titled_government_notes_only(self):
        got = mx.parse_day(load("notas-01-10-2026.json"))
        self.assertTrue(got)
        self.assertTrue(all(e["doc_id"].startswith("dof:") for e in got))
        self.assertFalse([e for e in got if "REF:" in e["title"]])          # CV notices left out
        draft = [e for e in got if e["doc_id"] == "dof:5800053"][0]
        self.assertEqual(draft["doc_type"], "regulation_draft")
        self.assertEqual(draft["published"], "2026-10-01")
        self.assertEqual(draft["body"], "Secretaria de Salud")
        self.assertEqual(draft["url"], "https://sidof.segob.gob.mx/notas/5800053")

    def test_doc_types(self):
        self.assertEqual(mx.doc_type("Decreto por el que se reforman diversas disposiciones de la "
                                     "Ley General de Salud"), "law")
        self.assertEqual(mx.doc_type("Decreto de entornos digitales seguros para niñas, niños y "
                                     "adolescentes."), "regulation")
        self.assertEqual(mx.doc_type("PROYECTO de Norma Oficial Mexicana PROY-NOM-001"), "regulation_draft")
        self.assertEqual(mx.doc_type("Convenio de Coordinación que celebran ..."), "publication")

    def test_comment_period_from_the_note(self):
        text = mx.note_text(load("nota-5800053.json"))
        self.assertEqual(mx.closing_from_text(text, "2026-10-01"),
                         ("2026-11-29", "60 días naturales para comentarios"))
        self.assertTrue(mx.summary_from_text(text, "Aviso de consulta pública del Proyecto de Norma "
                                             "Oficial Mexicana PROY-NOM-027-SSA-2026, Para la "
                                             "prevención, control y eliminación de la lepra.")
                        .startswith("RAFAEL RICARDO"))
        self.assertEqual(mx.closing_from_text("dentro de los 60 días naturales contados a partir del "
                                              "día siguiente de su publicación", "2026-10-01")[0],
                         "2026-11-30")
        self.assertEqual(mx.closing_from_text("en un plazo de 10 días hábiles", "2026-10-01")[0], None)


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "mx", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertEqual(len([u for u in client.urls if "/notas/nota/" not in u]), mx.DAYS)
        self.assertIn(mx.NOTE.format(5800053), client.urls)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='mx'")}
        # on our ground: the decree on safe digital environments for children (areas 6, 7)
        dec = rows["dof:5801237"]
        self.assertEqual(dec["doc_type"], "regulation")
        self.assertEqual(dec["tier"], 1)
        self.assertIn(7, json.loads(dec["areas"]))
        # the leprosy NOM draft is a deadline type but not on our ground: not stored
        self.assertNotIn("dof:5800053", rows)
        run = conn.execute("SELECT ok, listed, kept FROM gov_doc_runs WHERE cc='mx'").fetchone()
        self.assertEqual(tuple(run), (1, listed, kept))


if __name__ == "__main__":
    unittest.main()
