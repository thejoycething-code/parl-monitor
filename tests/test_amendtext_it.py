"""Italy (Camera): the amendment, order of the day or motion a vote names
(src/amendtext_it.py).

Fixtures: the Allegato A pages of sittings 9, 16, 72 and 251 of the 19th
legislature, captured live from documenti.camera.it on 16 October 2026 and
trimmed to the items the tests read (tests/fixtures/amendtext/it; each file
names its page). Votes of the store (sha 12dfcd342515):
  camera-vs19_072_012  "Emendamento 1.4 QUARTINI ..." to A.C. 977: civil unions
                       in its text -> area 9, through the gate
  camera-vs19_009_071  ODG 9/5/33: citizenship in its "impegna il Governo" -> ledger
  camera-vs19_251_099  motion 1-00245 "sul capoverso settimo della parte
                       dispositiva": only commitment 7 is the purpose; the
                       press-freedom words elsewhere are gated
  camera-vs19_016_017  motion 1-00031 "limitatamente alla premessa": a vote on
                       the premises has no purpose -> gated
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import amendtext, amendtext_it as it  # noqa: E402
from amendtext_fake import FixtureClient  # noqa: E402


class ItalyReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = FixtureClient("it")
        cls.reader = it.ItalyReader(cls.client)
        cls.tax, cls.wl, _ = cls.reader.taxonomy()
        cls.rows = cls.client.rows()

    def read(self, key):
        row = self.rows[key]
        lk = self.reader.fetch(row, self.reader.refs(row))
        res, labels = amendtext.match(lk, self.tax, self.wl)
        return lk, res, (amendtext.ledger_ok(lk, labels, self.tax, self.wl) if labels else False)

    def test_refs(self):
        self.assertEqual(it.refs_of("Emendamento 7-bis.1 ORRICO ANNA LAURA (M5S) - Votazione Emendamento 7-bis.1 "
                                    "DDL n. 2662", "camera-vs19_554_061"), ["seduta 554", "eme 7-bis.1 ac 2662"])
        self.assertEqual(it.refs_of("Ordine del giorno n. 9/1866/11 BONETTI ELENA (APERRE) - Votazione",
                                    "camera-vs19_551_078"), ["seduta 551", "odg 9/1866/11"])
        self.assertEqual(it.refs_of("RIS 6-285, PREMESSA - Votazione Risoluzione 6_00285", "camera-vs19_600_001"),
                         ["seduta 600", "risoluzione 6-00285"])
        self.assertEqual(it.refs_of("Articolo 1 - Votazione Articolo 1 DDL n. 2345", "camera-vs19_600_002"), [])

    def test_vote_parts(self):
        self.assertEqual(it.vote_part("Mozione n. 1-00245, sul capoverso settimo della parte dispositiva X"),
                         ("items", [7]))
        self.assertEqual(it.vote_part("RIS 6-254 NO IMP 3, 4 E PREMESSE - Votazione"), ("except", [3, 4]))
        self.assertEqual(it.vote_part("Mozione n. 1-00244, sul capoverso trentesimo delle premesse X"),
                         ("premise", []))
        self.assertEqual(it.vote_part("Mozione n. 1-00517 BOSCHI MARIA ELENA (IVICRE) ed altri"), ("whole", []))

    def test_outcomes_match_the_live_measurement(self):
        for key, want in self.client.expected().items():
            lk, res, gate = self.read(key)
            self.assertEqual(lk.status, want["status"], key)
            self.assertEqual(res.issue_areas if res else None, want["areas"], key)
            self.assertEqual(gate, want["ledger"], key)

    def test_premise_vote_has_no_purpose(self):
        lk, res, gate = self.read("camera-vs19_016_017")
        self.assertEqual(lk.texts[0]["purpose"], "")
        self.assertIn("vote on the premises", lk.texts[0]["label"])

    def test_not_printed_fails_loud(self):
        row = dict(self.rows["camera-vs19_072_012"], title="Emendamento 9.999 X - Votazione Emendamento 9.999 DDL n. 977")
        lk = self.reader.fetch(row, self.reader.refs(row))
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("eme 9.999 ac 977 not printed in the Allegato A", lk.gap)


if __name__ == "__main__":
    unittest.main()
