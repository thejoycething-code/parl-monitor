"""Portugal: the proposta de alteração a plenary vote puts (src/amendtext_pt.py).

Fixtures (tests/fixtures/amendtext/pt), captured live on 16 October 2026:
initiatives.json holds four records of the Assembleia's Iniciativas dump
(XVII/J/41, P/30, J/276, J/556), trimmed to the events with votes or annexes
and the fields the reader uses; the other files are the annexes it read. The
PS's first proposals paper on J/556 is a scanned PDF (353 KB, no text layer):
it is replaced here by a one-page blank PDF, which reads the same (no text).
  XVII/182707  P/30, PS proposal on article 54: printed in the PS's request to
               call it up ("Requerimento de Avocação do PS") -> read
  XVII/182718  J/41, voted jointly with P/30: the paper is filed under P/30
               (IniciativasConjuntas) -> read
  XVII/182740  J/556, article 1: in the PS's "(aditamento)" paper -> read
  XVII/182743  J/556, article 3: only in the scanned paper -> a gap
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import amendtext_pt as pt  # noqa: E402
from amendtext_fake import FixtureClient  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "amendtext", "pt")


class PortugalReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = FixtureClient("pt")
        with open(os.path.join(FIX, "initiatives.json"), encoding="utf-8") as fh:
            records = json.load(fh)
        cls.reader = pt.PortugalReader(cls.client, records=records)
        cls.rows = cls.client.rows()

    def test_refs(self):
        self.assertEqual(pt.refs_of({"ini_key": "XVII/J/556", "vote_id": 182740, "description":
                                     "Proposta de alteração, apresentada pelo PS, que substitui o artigo 1.º do "
                                     "texto final"}), ["XVII/J/556", "vote 182740", "PS", "1"])
        self.assertEqual(pt.refs_of({"ini_key": "XVII/J/61", "vote_id": 1, "description":
                                     "Artigo 6.º - Proposta de alteração do PSD - Substituição do artigo 6.º"}),
                         ["XVII/J/61", "vote 1", "PSD", "6"])
        self.assertEqual(pt.refs_of({"ini_key": "XVII/P/4", "vote_id": 2, "description": "Artigo 1.º do texto final"}),
                         [])

    def test_outcomes_match_the_live_measurement(self):
        for key, want in self.client.expected().items():
            row = self.rows[key]
            lk = self.reader.fetch(row, self.reader.refs(row))
            self.assertEqual(lk.status, want["status"], key)
            if lk.status == "ok":
                self.assertEqual(lk.texts[0]["label"], want["label"], key)
                self.assertTrue(lk.texts[0]["purpose"], key)
            else:
                self.assertIn("image-only", lk.gap)

    def test_article_passage(self):
        text = "Artigo 1.º\nObjeto\nA lei ...\nArtigo 2.º-A\nNovo\nArtigo 2.º\nAlargamento"
        self.assertTrue(pt.article_passage(text, "2").startswith("Artigo 2.º Alargamento"))
        self.assertTrue(pt.article_passage(text, "2-A").startswith("Artigo 2.º-A"))
        self.assertEqual(pt.article_passage(text, "9"), "")


if __name__ == "__main__":
    unittest.main()
