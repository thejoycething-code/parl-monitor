"""Spain: the enmiendas a Congreso vote names (src/amendtext_es.py).

Fixture: tests/fixtures/amendtext/es/BOCG-15-B-240-4.excerpt.txt, the text
layer of the live BOCG-15-B-240-4.PDF (16 October 2026: the amendments to the
conversion-therapy bill, 122/000201), its first page and amendments 25 to 31,
as src/prov_fetch.pdf_text reads them. Votes of 25 June 2026 (store sha
12dfcd342515): congreso-15-191-3 is the PP's amendment 26, congreso-15-191-6
its amendment 31 (a new disposition: a bill to replace Ley 4/2023 on LGTBI
rights, area 5 in its proposed text).
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import amendtext, amendtext_es as es  # noqa: E402

EXCERPT = os.path.join(ROOT, "tests", "fixtures", "amendtext", "es", "BOCG-15-B-240-4.excerpt.txt")
URL = "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/B/BOCG-15-B-240-4.PDF"
ROW = {"key": "congreso-15-191-6", "date": "2026-06-25", "initiative_key": "15/122/000201",
       "subgroup": "Enmiendas presentadas por el Grupo Parlamentario Popular en el Congreso Enmienda 31.",
       "bocg": "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/B/BOCG-15-B-240-1.PDF#page=1"}


class SpainReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(EXCERPT, encoding="utf-8") as fh:
            blocks = es.split_amendments(fh.read())
        cls.reader = es.SpainReader(client=None)
        # the BOCG publications of 122/000201 as read: only the amendments one matters here
        base = "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/B/BOCG-15-B-240-{0}.PDF"
        cls.reader._pubs[base] = [(URL, blocks)]
        cls.tax, cls.wl, _ = cls.reader.taxonomy()

    def test_refs(self):
        self.assertEqual(es.refs_of(ROW), ["15/122/000201", "Grupo Parlamentario Popular en el Congreso", "31"])
        self.assertEqual(es.refs_of(dict(ROW, subgroup="Enmiendas presentadas por el Grupo Parlamentario Popular "
                                                       "en el Congreso Enmiendas 25, 26 y 30.")),
                         ["15/122/000201", "Grupo Parlamentario Popular en el Congreso", "25", "26", "30"])
        self.assertEqual(es.refs_of(dict(ROW, subgroup="Enmiendas presentadas por el Grupo Parlamentario VOX. "
                                                       "Resto de las enmiendas.")), [])

    def test_amendment_read_and_gated_on_its_purpose(self):
        lk = self.reader.fetch(ROW, self.reader.refs(ROW))
        self.assertEqual(lk.status, "ok")
        self.assertEqual(lk.texts[0]["url"], URL)
        res, labels = amendtext.match(lk, self.tax, self.wl)
        self.assertIn(5, res.issue_areas)
        self.assertTrue(amendtext.ledger_ok(lk, labels, self.tax, self.wl))

    def test_wrong_group_or_missing_number_fails_loud(self):
        row = dict(ROW, subgroup="Enmiendas presentadas por el Grupo Parlamentario VOX. Enmienda 31.")
        lk = self.reader.fetch(row, self.reader.refs(row))
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("1 printed, 0 by the Grupo Parlamentario VOX", lk.gap)
        row = dict(ROW, subgroup="Enmiendas presentadas por el Grupo Parlamentario Popular en el Congreso "
                                 "Enmiendas 31 y 99.")
        lk = self.reader.fetch(row, self.reader.refs(row))
        self.assertEqual(lk.status, "ok")
        self.assertIn("partly read; missing 99", lk.gap)

    def test_no_bocg_is_a_gap(self):
        lk = self.reader.fetch(dict(ROW, bocg=None), self.reader.refs(ROW))
        self.assertEqual(lk.status, "unreadable")


if __name__ == "__main__":
    unittest.main()
