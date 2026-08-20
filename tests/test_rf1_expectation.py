"""RF#1's numerical expectation block.

Antonio, #campaigns 2026-08-19: record what a campaign is EXPECTED to achieve
numerically at Planning, so Evaluate compares a number with a number rather
than with narrative. The tool supplies the BASELINE; the expectation stays the
campaigner's, for the same reason RF4 scores stay empty.
"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db
import make_briefs as mb


# campaign_performance is created by tools/log_campaign_performance.py, not by
# db.SCHEMA, so an in-memory store does not have it. Mirrored verbatim from the
# live table rather than approximated, so a column rename upstream fails here.
CREATE_PERF = (
    "CREATE TABLE campaign_performance (petition_id INTEGER PRIMARY KEY, "
    "name TEXT, launch_date TEXT, last_activity TEXT, new_members INTEGER, "
    "reactivated INTEGER, signatures INTEGER, areas TEXT, source TEXT, "
    "logged_at TEXT, raised_eur REAL, donations_once INTEGER, "
    "donations_monthly INTEGER, monthly_12mo_eur REAL, final INTEGER)")


def fresh():
    conn = db.init_db(db.connect(":memory:"))
    conn.execute(CREATE_PERF)
    return conn


def seed(conn, rows):
    """rows: (signatures, new_members, raised_eur, areas_json)."""
    start = conn.execute(
        "SELECT COALESCE(MAX(petition_id), 0) FROM campaign_performance"
    ).fetchone()[0]
    for n, (sig, new, eur, areas) in enumerate(rows, start=start + 1):
        conn.execute(
            "INSERT INTO campaign_performance (petition_id, name, signatures, "
            "new_members, raised_eur, areas, logged_at) VALUES "
            "(?,?,?,?,?,?,'2026-08-20')", (n, "c", sig, new, eur, areas))
    conn.commit()


class ThresholdTests(unittest.TestCase):
    """The sub-100 exclusion is the whole reason this is usable."""

    def setUp(self):
        self.conn = fresh()

    def tearDown(self):
        self.conn.close()

    def test_templates_and_dormant_petitions_are_excluded(self):
        """Measured on the live store: 129 of 366 rows have FEWER THAN TEN
        signatures, one named "Petition template EN-GB", and the all-rows
        median for area 1 was 3 signatures against a p75 of 5,689. Quoting
        that median into a Brief would be worse than quoting nothing."""
        seed(self.conn, [(1, 0, None, "[1]"), (2, 0, None, "[1]"),
                         (3, 0, None, "[1]"), (20000, 900, None, "[1]"),
                         (30000, 1100, None, "[1]")])
        sigs = dict(mb.rf1_expectation(self.conn, [1]))["Expected signatures"]
        self.assertIn("n=2", sigs, "only the two real campaigns should count")
        self.assertIn("3 sub-100-signature row(s) excluded", sigs)
        self.assertNotIn("median 3 ", sigs)

    def test_thin_evidence_is_labelled_thin(self):
        seed(self.conn, [(20000, 900, None, "[5]")])
        sigs = dict(mb.rf1_expectation(self.conn, [5]))["Expected signatures"]
        self.assertIn("THIN", sigs)
        self.assertIn("n=1", sigs)

    def test_no_comparable_says_so_rather_than_inventing_one(self):
        seed(self.conn, [(5, 0, None, "[1]")])
        sigs = dict(mb.rf1_expectation(self.conn, [1]))["Expected signatures"]
        self.assertIn("baseline unavailable", sigs)

    def test_an_empty_store_does_not_raise(self):
        rows = mb.rf1_expectation(self.conn, [1])
        self.assertEqual(len(rows), 3)


class BaselineShapeTests(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()
        seed(self.conn, [(a, a // 20, None, "[6]")
                         for a in range(1000, 41000, 1000)])

    def tearDown(self):
        self.conn.close()

    def test_a_distribution_is_offered_not_a_point_forecast(self):
        """"median X (p25 Y, p75 Z, n=N)" is evidence a campaigner can argue
        with; a single number reads as a prediction the tool cannot make."""
        sigs = dict(mb.rf1_expectation(self.conn, [6]))["Expected signatures"]
        for token in ("median", "p25", "p75", "n="):
            self.assertIn(token, sigs)

    def test_three_metrics_always_returned_in_order(self):
        rows = mb.rf1_expectation(self.conn, [6])
        self.assertEqual([m for m, _b in rows],
                         ["Expected signatures", "Expected new members",
                          "Expected EUR raised"])

    def test_money_is_reported_as_not_held_when_unpopulated(self):
        """raised_eur is null on all 366 live rows. Saying so beats an empty
        cell that reads as though a baseline existed."""
        money = dict(mb.rf1_expectation(self.conn, [6]))["Expected EUR raised"]
        self.assertIn("NOT HELD", money)

    def test_money_is_used_when_it_is_populated(self):
        seed(self.conn, [(20000, 900, 5000.0, "[7]"),
                         (25000, 950, 7000.0, "[7]")])
        money = dict(mb.rf1_expectation(self.conn, [7]))["Expected EUR raised"]
        self.assertIn("EUR", money)
        self.assertNotIn("NOT HELD", money)


class LookerSourceTests(unittest.TestCase):
    """The two sources are different METRICS and must never be pooled."""

    LOOKER = ("CREATE TABLE IF NOT EXISTS looker_campaigns (program TEXT "
              "PRIMARY KEY, list_name TEXT, campaign_name TEXT, bound TEXT, "
              "looker_topic TEXT, start_date TEXT, signatures INTEGER, "
              "new_members INTEGER, otd_eur REAL, md_eur REAL, "
              "sent_emails INTEGER, areas TEXT, logged_at TEXT)")

    def setUp(self):
        self.conn = fresh()
        self.conn.execute(self.LOOKER)

    def tearDown(self):
        self.conn.close()

    def _looker(self, rows, area="[1]", list_name="EN_GB"):
        for n, (sig, new, otd) in enumerate(rows):
            self.conn.execute(
                "INSERT INTO looker_campaigns (program, list_name, "
                "campaign_name, signatures, new_members, otd_eur, areas, "
                "logged_at) VALUES (?,?,?,?,?,?,?,'2026-08-20')",
                ("p%d" % n, list_name, "c", sig, new, otd, area))
        self.conn.commit()

    def test_money_comes_from_looker_because_local_has_none(self):
        """raised_eur is null on all 366 live rows; Looker carries otd_eur."""
        seed(self.conn, [(20000, 900, None, "[1]")])
        self._looker([(20000, 900, 1332.0)])
        money = dict(mb.rf1_expectation(self.conn, [1]))["Expected EUR raised"]
        self.assertIn("Looker", money)
        self.assertIn("1,332", money)

    def test_money_says_not_held_when_neither_source_has_it(self):
        seed(self.conn, [(20000, 900, None, "[1]")])
        money = dict(mb.rf1_expectation(self.conn, [1]))["Expected EUR raised"]
        self.assertIn("NOT HELD", money)

    def test_the_source_with_more_comparables_wins_and_is_named(self):
        """13 local rows against 1 Looker row must not silently become 14: they
        are lifetime petition totals versus email-campaign attribution, and the
        same campaign appears in both with different numbers."""
        seed(self.conn, [(20000 + n, 900, None, "[1]") for n in range(6)])
        self._looker([(50000, 5000, 100.0)])
        sigs = dict(mb.rf1_expectation(self.conn, [1]))["Expected signatures"]
        self.assertIn("n=6", sigs, "the six local rows should win on count")
        self.assertIn("Looker holds 1 on a different basis", sigs)
        self.assertNotIn("n=7", sigs, "the sources must never be pooled")

    def test_looker_wins_when_it_has_more(self):
        seed(self.conn, [(20000, 900, None, "[1]")])
        self._looker([(30000 + n, 800, 100.0) for n in range(5)])
        sigs = dict(mb.rf1_expectation(self.conn, [1]))["Expected signatures"]
        self.assertIn("Looker (email-campaign attributed)", sigs)
        self.assertIn("n=5", sigs)

    def test_only_en_gb_looker_rows_are_used(self):
        """A UK brief benchmarked against German campaigns would mislead: list
        sizes and response rates differ."""
        seed(self.conn, [(20000, 900, None, "[1]")])
        self._looker([(90000, 9000, 5000.0)], list_name="DE")
        money = dict(mb.rf1_expectation(self.conn, [1]))["Expected EUR raised"]
        self.assertIn("NOT HELD", money)

    def test_a_missing_looker_table_does_not_break_the_brief(self):
        conn = fresh()          # no looker_campaigns at all
        seed(conn, [(20000, 900, None, "[1]")])
        rows = mb.rf1_expectation(conn, [1])
        self.assertEqual(len(rows), 3)
        conn.close()


class RenderTests(unittest.TestCase):
    """The expected cell must ship BLANK, and the CSV shape must not change."""

    SUBJECT = {"title": "T", "kind": "bill", "slug": "s", "areas": [1],
               "url": "", "next_key_date": None}
    FIELDS = {"general": [("a", "b")], "plan": [("c", "d")],
              "prepare": [("e", "f")], "urgency": "ROUTINE"}
    HINTS = ["h1", "h2", "h3", "h4", "h5"]
    EXPECT = [("Expected signatures", "median 100 (n=3)"),
              ("Expected new members", "median 5 (n=3)"),
              ("Expected EUR raised", "NOT HELD")]

    def test_markdown_leaves_expected_and_actual_blank(self):
        import datetime
        out = mb.render_markdown(self.SUBJECT, self.FIELDS, self.HINTS,
                                 self.EXPECT, "", [], datetime.date(2026, 8, 20))
        self.assertIn("## RF#1 numerical expectation", out)
        row = [l for l in out.splitlines()
               if l.startswith("| Expected signatures")][0]
        # metric | expected | actual | delta | baseline -> the three middle
        # cells are empty because the campaigner fills them.
        cells = [c.strip() for c in row.split("|")[1:-1]]
        self.assertEqual(cells[1], "")
        self.assertEqual(cells[2], "")
        self.assertEqual(cells[3], "")
        self.assertIn("median 100", cells[4])

    def test_csv_block_keeps_the_seven_column_shape(self):
        """The CSV is pasted into the Brief template, so a different column
        count in this block would break the paste. RF#1's expected/actual/delta
        reuses the existing Plan/Evaluate/Delta geometry exactly."""
        import csv as csvmod
        import datetime
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "b.csv")
        mb.write_csv(path, self.SUBJECT, self.FIELDS, self.HINTS, self.EXPECT,
                     [], datetime.date(2026, 8, 20))
        rows = list(csvmod.reader(open(path)))
        start = [n for n, r in enumerate(rows)
                 if r and r[0] == "RF#1 NUMERICAL EXPECTATION"][0]
        header = rows[start + 1]
        self.assertEqual(len(header), 7)
        for r in rows[start + 2:start + 5]:
            self.assertEqual(len(r), 7)
            self.assertEqual(r[2], "", "Expected (Plan) must ship blank")
            self.assertEqual(r[4], "", "Actual (Evaluate) must ship blank")

    def test_rf4_scores_are_still_never_filled(self):
        """The new block must not have loosened the older rule."""
        import csv as csvmod
        import datetime
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "b.csv")
        mb.write_csv(path, self.SUBJECT, self.FIELDS, self.HINTS, self.EXPECT,
                     [], datetime.date(2026, 8, 20))
        rows = list(csvmod.reader(open(path)))
        # Only the RF4 QUESTION rows: the new block's section header is also a
        # single cell beginning "RF#1", which the first version of this guard
        # tripped over.
        checked = 0
        for r in rows:
            if len(r) == 7 and r[0].startswith("RF#") and r[1]:
                self.assertEqual(r[2], "", "RF4 scores are the campaigner's")
                checked += 1
        self.assertEqual(checked, len(mb.RF4),
                         "every RF4 row must have been checked")


if __name__ == "__main__":
    unittest.main()
