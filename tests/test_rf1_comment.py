"""RF#1's comment and Plan score (Christopher, 12 October 2026).

He scores every RF4 question at Plan, so RF#1 carries labelled lines --
expected figures, definitions, comparables, the EN GB benchmark, the score
arithmetic, channels -- and a Plan score when the numbers allow one. The
lifetime basis (the store) and the email-series basis (Bluebook) are never
mixed, and the cell names the one it uses. Fixture names are invented.
"""

from __future__ import annotations

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db
import make_briefs as mb
from tests.test_rf1_expectation import CREATE_PERF

LOOKER = ("CREATE TABLE looker_campaigns (program TEXT PRIMARY KEY, "
          "list_name TEXT, campaign_name TEXT, bound TEXT, looker_topic TEXT, "
          "start_date TEXT, signatures INTEGER, new_members INTEGER, "
          "otd_eur REAL, md_eur REAL, sent_emails INTEGER, areas TEXT, "
          "logged_at TEXT, area_source TEXT)")
TODAY = datetime.date(2026, 10, 12)


def store(perf, looker=()):
    """perf: (pid, launch, sigs, new, reactivated, areas);
    looker: (pid, start, sigs, otd, md)."""
    conn = db.init_db(db.connect(":memory:"))
    conn.execute(CREATE_PERF)
    conn.execute(LOOKER)
    for pid, launch, sig, new, rea, areas in perf:
        conn.execute("INSERT INTO campaign_performance (petition_id, name, "
                     "launch_date, signatures, new_members, reactivated, "
                     "areas) VALUES (?,?,?,?,?,?,?)",
                     (pid, "Campaign %d" % pid, launch, sig, new, rea, areas))
    for pid, start, sig, otd, md in looker:
        conn.execute("INSERT INTO looker_campaigns (program, list_name, "
                     "start_date, signatures, otd_eur, md_eur, area_source, "
                     "logged_at) VALUES (?, 'EN_GB', ?, ?, ?, ?, ?, "
                     "'2026-10-12')", ("p%d" % pid, start, sig, otd, md,
                                       "petition-id join (%d)" % pid))
    conn.commit()
    return conn


class BandTests(unittest.TestCase):
    NET = {50: 1692, 75: 3117, 90: 6578, "n": 102}
    MONEY = {25: 605, 50: 1417, 75: 2035, 90: 3249, "n": 89}

    def test_audience_bands(self):
        band = lambda v: mb.rf1_band(v, self.NET, mb.AUDIENCE_STEPS)[0]
        self.assertEqual([band(0), band(100), band(1692), band(3117),
                          band(6578), band(13156), band(26312)],
                         [0, 1, 2, 3, 4, 5, 6])

    def test_money_bands(self):
        band = lambda v: mb.rf1_band(v, self.MONEY, mb.MONEY_STEPS)[0]
        self.assertEqual([band(100), band(605), band(1417), band(2035),
                          band(3249), band(6498)], [1, 2, 3, 4, 5, 6])

    def test_never_above_ten(self):
        self.assertEqual(mb.rf1_band(10 ** 9, self.NET,
                                     mb.AUDIENCE_STEPS)[0], 10)

    def test_reason_names_the_interval(self):
        _, why = mb.rf1_band(2841, self.NET, mb.AUDIENCE_STEPS)
        self.assertEqual(why, "2,841 is between the median (1,692) and p75 "
                              "(3,117) = 2")


class CommentTests(unittest.TestCase):

    def _comps(self):
        perf = [(100 + i, "2026-0%d-01" % (i + 1), 20000 + i, 2000 + 100 * i,
                 500, "[6]") for i in range(4)]
        # Money only where attribution is complete (before February 2026).
        perf.append((200, "2025-11-01", 30000, 3000, 600, "[6]"))
        looker = [(100 + i, "2025-12-01", 20000, 1000.0 + 100 * i, 100.0)
                  for i in range(3)]
        return store(perf, looker)

    def test_lines_in_order_with_a_score(self):
        conn = self._comps()
        text, score = mb.rf1_comment(conn, [6], "Acquisition", TODAY)
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith(
            "Expected by the end of the classical series: "))
        self.assertIn("unsubscribes NOT HELD", lines[0])
        self.assertTrue(lines[1].startswith("Net audience = new members + "
                                            "reactivated - unsubscribes."))
        self.assertIn("€ raised = one-time + first monthly", lines[1])
        self.assertTrue(lines[2].startswith("Basis: lifetime petition totals"))
        self.assertTrue(lines[3].startswith("Why these numbers"))
        self.assertRegex(lines[4], r"^Campaign \d+ \(\d+, [A-Z][a-z]+ 2026\): "
                                   r"[\d,]+ signatures \| [\d,]+ new \| "
                                   r"[\d,]+ reactivated \| net [\d,]+ \| ")
        bench = next(ln for ln in lines if ln.startswith("EN GB benchmark"))
        self.assertIn("(lifetime,", bench)
        score_line = next(ln for ln in lines if ln.startswith("Score:"))
        self.assertIn("RF#1 = 85% x", score_line)
        self.assertIn("rounded to {0}".format(score), score_line)
        self.assertIsNotNone(score)
        self.assertTrue(any(ln.startswith("Channels:") for ln in lines))
        self.assertFalse(any(ln.startswith("* ") for ln in lines))

    def test_purpose_sets_the_weights(self):
        text, _ = mb.rf1_comment(self._comps(), [6], "Fundraising", TODAY)
        self.assertIn("RF#1 = 30% x", text)

    def test_new_ask_type_gets_an_asterisk_and_no_score(self):
        conn = store([(1, "2026-05-01", 20000, 2000, 500, "[6]")])
        text, score = mb.rf1_comment(conn, [6], "Acquisition", TODAY)
        self.assertIsNone(score)
        self.assertIn("series*:", text)
        self.assertIn("* New ask type", text)
        self.assertIn("[CAMPAIGNER", text)

    def test_benchmark_windows(self):
        """Net audience: launched in the last 24 months, >= 3,000 sigs.
        Money: the 24 months before MONEY_COMPLETE_BEFORE."""
        conn = store([(1, "2024-11-01", 5000, 100, 0, "[1]"),
                      (2, "2024-09-01", 5000, 999, 0, "[1]"),
                      (3, "2026-01-01", 2000, 999, 0, "[1]")],
                     [(1, "2024-03-01", 5000, 100.0, 10.0),
                      (2, "2024-01-01", 5000, 999.0, 0.0),
                      (3, "2026-03-01", 5000, 999.0, 0.0)])
        b = mb.rf1_benchmark(conn, TODAY)
        self.assertEqual(b["net"]["n"], 1)
        self.assertEqual(b["net"][50], 100)
        self.assertEqual(b["money"]["n"], 1)
        self.assertEqual(b["money"][50], 110.0)

    def test_series_basis_is_labelled_and_never_mixed(self):
        conn = self._comps()
        text, score = mb.rf1_comment(
            conn, [6], "Acquisition", TODAY,
            series={"new": 1200, "reactivated": 300, "unsubscribes": 150,
                    "eur": 1000})
        self.assertIn("150 unsubscribes", text)
        self.assertIn("1,350 net audience", text)
        self.assertIn("signatures are lifetime petition totals", text)
        self.assertIn("(email series,", text)
        self.assertNotIn("(lifetime,", text)
        self.assertIn("median 578", text)
        self.assertEqual(score, 2)


class PlanScoreInCsvTests(unittest.TestCase):
    def test_rf1_plan_score_written_others_blank(self):
        import csv
        import tempfile
        subject = {"title": "Example", "slug": "example", "nation": None}
        fields = {"general": [], "plan": [], "prepare": [],
                  "urgency": "Non-Urgent"}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "b.csv")
            mb.write_csv(path, subject, fields, ["a\nb", "", "", "", ""], [],
                         [], TODAY, rf4_scores={"RF#1": 3})
            with open(path, encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
        rf = {r[0]: r for r in rows if r and r[0] in dict(mb.RF4)}
        self.assertEqual(rf["RF#1"][2], "3")
        self.assertEqual(rf["RF#2"][2], "")
        total = [r for r in rows if r and r[0] == "TOTAL IF WE WIN"][0]
        self.assertEqual(total[2], "0")


if __name__ == "__main__":
    unittest.main()
