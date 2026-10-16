"""Germany: the Drucksache a Bundestag roll call is on (src/amendtext_de.py).

Fixtures: DIP replies captured live on 16 October 2026
(tests/fixtures/amendtext/de, key removed), for four stored polls:
  6727  "Bisherigen Umfang der NIPT-Kassenleistung erhalten (Änderungsantrag)":
        abgeordnetenwatch links the Antrag 21/3873; the House's record of 8
        October names the Änderungsantrag 21/8475 put to the roll call. Its DIP
        title names the prenatal test -> area 1, through the gate
  6540  EUFOR ALTHEA mandate: "Menschenhandel" in the body only -> gated
  1758  2020 organ donation (opt-out) bill: no paper linked; found in the
        House's record of 16 January 2020 by its tally -> area 13, gate passes
  4770  an Entschließungsantrag poll the record does not resolve -> a gap
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import amendtext, amendtext_de as de  # noqa: E402
from amendtext_fake import FixtureClient  # noqa: E402


class GermanyReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = FixtureClient("de")
        cls.reader = de.GermanyReader(cls.client, key="test-key")
        cls.tax, cls.wl, _ = cls.reader.taxonomy()
        cls.rows = cls.client.rows()

    def read(self, key):
        row = self.rows[key]
        lk = self.reader.fetch(row, self.reader.refs(row))
        res, labels = amendtext.match(lk, self.tax, self.wl)
        return lk, res, labels, amendtext.ledger_ok(lk, labels, self.tax, self.wl) if labels else False

    def test_refs(self):
        self.assertEqual(de.drucksache_of("https://dserver.bundestag.de/btd/21/038/2103873.pdf"), "21/3873")
        self.assertEqual(de.drucksache_of("http://dip.bundestag.de/btd/19/013/1901302.pdf"), "19/1302")
        self.assertEqual(self.reader.refs(self.rows["6727"]), ["21/3873", "Änderungsantrag"])
        self.assertEqual(self.reader.refs(self.rows["1758"]), ["tally 292:379:3"])

    def test_amendment_from_the_houses_record(self):
        lk, res, labels, gate = self.read("6727")
        self.assertEqual(lk.status, "ok")
        self.assertIn("21/8475", lk.refs)
        self.assertEqual(res.issue_areas, [1])
        self.assertTrue(gate)

    def test_body_only_is_gated(self):
        lk, res, labels, gate = self.read("6540")
        self.assertEqual((lk.status, res.issue_areas, gate), ("ok", [12], False))

    def test_tally_link(self):
        lk, res, labels, gate = self.read("1758")
        self.assertEqual(lk.status, "ok")
        self.assertIn(13, res.issue_areas)
        self.assertTrue(gate)

    def test_unresolved_is_a_gap(self):
        lk, res, labels, gate = self.read("4770")
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("could not read amendment text", lk.gap)

    def test_vorabfassung_banner_removed(self):
        self.assertEqual(de.clean("a V\norabfassung – w\nird durch die lektorierte Fassung ersetzt. b").split(), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
