"""Netherlands: the amendment or motion a Tweede Kamer vote is on (src/amendtext_nl.py).

Fixtures: the Tweede Kamer's OData replies (each zaak with its documents, and
the documents' own Word files) captured live on 16 October 2026
(tests/fixtures/amendtext/nl):
  2026Z20841  motion on abortion care: "abortus" in its operative words -> ledger
  2026Z21974  amendment on the counter-terrorism law: its explanation names
              freedom of religion and of expression -> ledger
  2026Z21590  amendment on the same law: freedom of religion only deeper in the
              body -> gated
  2026Z10184  "Amendement (gewijzigd/nader/vervangend)" on model embryos: read
              (the portal's reworded kind), embryo* is tier 2 in its purpose,
              the tier-1 Embryowet only in the body -> gated
  2026Z22281  "Motie (gewijzigd/nader)" on the DSA: read, ledger (area 7)
  2021Z00103  a motion of no confidence ("zegt het vertrouwen ... op"): read,
              nothing on our ground
"""

import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import amendtext, amendtext_nl as nl, db  # noqa: E402
from amendtext_fake import FixtureClient  # noqa: E402


class NetherlandsReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = FixtureClient("nl")
        cls.reader = nl.NetherlandsReader(cls.client)
        cls.tax, cls.wl, _ = cls.reader.taxonomy()
        cls.rows = cls.client.rows()

    def read(self, key):
        row = self.rows[key]
        lk = self.reader.fetch(row, self.reader.refs(row))
        res, labels = amendtext.match(lk, self.tax, self.wl)
        return lk, res, (amendtext.ledger_ok(lk, labels, self.tax, self.wl) if labels else False)

    def test_outcomes_match_the_live_measurement(self):
        for key, want in self.client.expected().items():
            lk, res, gate = self.read(key)
            self.assertEqual(lk.status, want["status"], key)
            self.assertEqual(res.issue_areas if res else None, want["areas"], key)
            self.assertEqual(gate, want["ledger"], key)

    def test_reworded_kinds_are_read(self):
        self.assertEqual(self.read("2026Z10184")[0].status, "ok")
        self.assertEqual(self.read("2026Z22281")[0].status, "ok")

    def test_motion_parts(self):
        text = ("De Kamer,\ngehoord de beraadslaging,\noverwegende dat de euthanasiewet is geëvalueerd;\n"
                "verzoekt de regering, de huurtoeslag te verhogen,\nen gaat over tot de orde van de dag.")
        considerans, operative = nl.motion_parts(text)
        self.assertIn("euthanasiewet", considerans)
        self.assertEqual(operative, "verzoekt de regering, de huurtoeslag te verhogen,")

    def test_missing_document_fails_loud(self):
        row = dict(self.rows["2026Z20841"], key="2026Z99999")
        lk = self.reader.fetch(row, ["2026Z99999"])
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("could not read amendment text", lk.gap)

    def test_apply_updates_the_zaak_and_its_votes(self):
        conn = sqlite3.connect(":memory:")
        db.init_db(conn)
        conn.execute("INSERT INTO nl_zaken (zaak_nummer, soort, onderwerp, areas, matched_terms) VALUES "
                     "('2026Z20841', 'Motie', 'x', '[]', '[]')")
        for b in ("b1", "b2"):
            conn.execute("INSERT INTO nl_divisions (besluit_id, zaak_nummer, areas) VALUES (?, '2026Z20841', '[]')",
                         (b,))
        lk, res, gate = self.read("2026Z20841")
        self.assertTrue(self.reader.apply(conn, {"key": "2026Z20841"}, res))
        self.assertEqual(conn.execute("SELECT areas, tier FROM nl_zaken").fetchone(), ("[1]", 1))
        self.assertEqual([r[0] for r in conn.execute("SELECT areas FROM nl_divisions")], ["[1]", "[1]"])


if __name__ == "__main__":
    unittest.main()
