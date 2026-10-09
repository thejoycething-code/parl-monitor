"""The Mini check gate: GitHub's scheduled run skips only when the Mini covered its slot."""
import datetime as dt
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mini_check as mc  # noqa: E402

UTC = dt.timezone.utc


def at(text):
    return dt.datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


COVERAGE = "30 5 * * *"
DIVISION_WEEK = "0 18,21 * * 1-4"
DIVISION_FRI = "0 13,15,17 * * 5"


class SlotTests(unittest.TestCase):
    def test_latest_hour_today(self):
        self.assertEqual(mc.slot_for(DIVISION_WEEK, at("2026-10-06 22:40")), at("2026-10-06 21:00"))
        self.assertEqual(mc.slot_for(DIVISION_WEEK, at("2026-10-06 19:10")), at("2026-10-06 18:00"))

    def test_late_run_after_midnight_is_yesterdays_slot(self):
        self.assertEqual(mc.slot_for(DIVISION_FRI, at("2026-10-10 01:30")), at("2026-10-09 17:00"))

    def test_ranges(self):
        self.assertEqual(mc.slot_for("0 9-11 * * *", at("2026-10-09 10:30")), at("2026-10-09 10:00"))

    def test_unreadable_cron(self):
        self.assertIsNone(mc.slot_for("*/15 * * * *", at("2026-10-09 10:30")))
        self.assertIsNone(mc.slot_for("", at("2026-10-09 10:30")))


class DecideTests(unittest.TestCase):
    def test_dispatch_always_runs(self):
        run, why = mc.decide("workflow_dispatch", "", "2026-10-09T02:43:23Z", at("2026-10-09 02:46"))
        self.assertTrue(run)
        self.assertIn("2 min ago", why)

    def test_missing_or_bad_stamp_runs(self):
        self.assertTrue(mc.decide("schedule", COVERAGE, "", at("2026-10-09 12:00"))[0])
        self.assertTrue(mc.decide("schedule", COVERAGE, "yesterday", at("2026-10-09 12:00"))[0])

    def test_coverage_summer_mini_an_hour_early_skips(self):
        # 05:30 London in BST is 04:30 UTC; GitHub's 05:30 UTC run starts at 12:09.
        self.assertFalse(mc.decide("schedule", COVERAGE, "2026-10-09T04:30:01Z", at("2026-10-09 12:09"))[0])

    def test_coverage_winter_same_minute_skips(self):
        self.assertFalse(mc.decide("schedule", COVERAGE, "2026-11-09T05:30:01Z", at("2026-11-09 11:00"))[0])

    def test_coverage_mini_missed_today_rescues(self):
        run, why = mc.decide("schedule", COVERAGE, "2026-10-08T04:30:01Z", at("2026-10-09 12:09"))
        self.assertTrue(run)
        self.assertIn("rescuing", why)

    def test_division_mini_ran_slot_skips(self):
        self.assertFalse(mc.decide("schedule", DIVISION_WEEK, "2026-10-06T21:00:02Z", at("2026-10-06 23:05"))[0])

    def test_division_earlier_slot_does_not_cover_later(self):
        # The Mini ran 18:00 but missed 21:00: the 21:00 backup must run.
        self.assertTrue(mc.decide("schedule", DIVISION_WEEK, "2026-10-06T18:00:02Z", at("2026-10-06 23:05"))[0])

    def test_friday_two_hour_slots_stay_apart(self):
        # Ran 13:00 (summer: 14:00 London), GitHub's 15:00 slot is not covered.
        self.assertTrue(mc.decide("schedule", DIVISION_FRI, "2026-10-09T13:00:02Z", at("2026-10-09 16:00"))[0])

    def test_unreadable_cron_falls_back_to_window(self):
        self.assertFalse(mc.decide("schedule", "*/30 * * * *", "2026-10-09T10:00:00Z", at("2026-10-09 12:00"))[0])
        self.assertTrue(mc.decide("schedule", "*/30 * * * *", "2026-10-08T10:00:00Z", at("2026-10-09 12:00"))[0])


if __name__ == "__main__":
    unittest.main()
