"""config/prov_stance.yaml: Quebec's readings, drafted 8 October 2026. No network.

Christopher: "draft READINGS for Quebec's recorded divisions on our ground".
Every tagged recorded division in the store has an entry; all are drafts and
place nobody until he confirms them by deleting `draft: true`.
"""

import collections
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import prov_5ca as p5  # noqa: E402


class QuebecReadingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qc = {k: e for k, e in p5.load_stance(p5.STANCE_PATH, "divisions").items()
                  if k.startswith("qc-")}

    def test_counts(self):
        st = collections.Counter(p5.status(e) for e in self.qc.values())
        self.assertEqual(len(self.qc), 179)
        # Confirmed 8 October 2026 on delegation ("Score for me and Greg can
        # amend if necessary").
        self.assertEqual(st, {"confirmed": 21, "unplaceable": 158})

    def test_every_entry_is_confirmed_with_its_record(self):
        for k, e in self.qc.items():
            self.assertFalse(e.get("draft"), k)
            for field in ("title", "dated", "result", "lobbies", "source", "text"):
                self.assertTrue(e.get(field), (k, field))
            if p5.status(e) == "unplaceable":
                self.assertTrue(e.get("reason"), k)
            else:
                self.assertTrue(e.get("moved_by"), k)
                for side in ("yea", "nay"):
                    if e.get(side) is not None:
                        self.assertIn(e[side], (-2, -1, 1, 2), k)
                        self.assertTrue(e.get("why_" + side), k)

    def test_no_quebec_reading_is_left_in_draft(self):
        self.assertEqual([k for k, e in self.qc.items() if p5.status(e) == "draft"], [])

    def test_laicity_and_assisted_dying_directions(self):
        bill21 = self.qc["qc-42-1-2019-06-16-165"]          # Bill 21, adoption
        self.assertEqual((bill21["yea"], bill21["nay"], bill21["areas"]), (-2, 2, [8]))
        bill9 = self.qc["qc-43-2-2026-04-02-140"]           # Bill 9, adoption
        self.assertEqual((bill9["yea"], bill9["nay"]), (-2, 2))
        bill11 = self.qc["qc-43-1-2023-06-07-113"]          # Bill 11 (MAID), adoption
        self.assertEqual((bill11["yea"], bill11["nay"]), (-2, 2))
        # The constitution (Bill 1): only the Yea places; the opposition's
        # Nay was on process, not on abortion or MAID.
        bill1 = self.qc["qc-43-2-2026-04-01-139"]
        self.assertEqual((bill1["yea"], bill1.get("nay")), (-1, None))

    def test_supply_bills_are_false_positives(self):
        supply = [k for k, e in self.qc.items() if "Loi n° " in e["title"] and "crédits" in e["title"]]
        self.assertEqual(len(supply), 9)
        for k in supply:
            self.assertTrue(self.qc[k]["reason"].startswith("TAXONOMY FALSE POSITIVE"), k)
            self.assertEqual(p5.status(self.qc[k]), "unplaceable")


if __name__ == "__main__":
    unittest.main()
