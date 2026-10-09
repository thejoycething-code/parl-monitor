"""The daily health summary reads the Mini's logs right and says what failed."""
import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import health_summary as hs  # noqa: E402

UTC = datetime.timezone.utc
SINCE = datetime.datetime(2026, 10, 9, 0, 0, tzinfo=UTC)
NOW = datetime.datetime(2026, 10, 10, 6, 30, tzinfo=UTC)

LOG = """2026-10-08T20:00:01Z mini_run division-watch (ref main)
2026-10-08T20:02:00Z mini_run division-watch done
2026-10-09T03:16:05Z mini_run division-watch (ref main)
  the wrapper changed; re-running the new one
2026-10-09T03:16:05Z mini_run division-watch (ref main)
  no store needed
2026-10-09T03:18:57Z mini_run division-watch done
2026-10-09T03:42:28Z mini_run day-sweep (ref main)
THE STORE MOVED UNDER YOU. Refusing to publish.
  FAILED at jobs/day-sweep.sh: exit 1
failure alert sent.
2026-10-09T23:00:01Z mini_run eu-day-sweep (ref main)
store pulled and verified
""".splitlines()


class MiniLogTests(unittest.TestCase):
    def test_runs_and_outcomes(self):
        runs = hs.mini_runs(LOG, SINCE)
        self.assertEqual([(j, o) for j, _s, o in runs], [
            ("division-watch", "ok"),
            ("day-sweep", "FAILED at jobs/day-sweep.sh: exit 1"),
            ("eu-day-sweep", "running"),
        ])

    def test_a_wrapper_rerun_is_one_run(self):
        runs = hs.mini_runs(LOG, SINCE)
        self.assertEqual(sum(1 for j, _s, _o in runs if j == "division-watch"), 1)

    def test_runs_before_the_window_are_left_out(self):
        later = datetime.datetime(2026, 10, 9, 4, 0, tzinfo=UTC)
        self.assertEqual([j for j, _s, _o in hs.mini_runs(LOG, later)], ["eu-day-sweep"])


class RenderTests(unittest.TestCase):
    def test_failures_unfinished_runs_and_new_sources_are_named(self):
        mini = hs.mini_runs(LOG, SINCE)
        github = [("Sunday pull", NOW, "completed", "failure"),
                  ("Provinces weekly", NOW, "completed", "failure"),
                  ("Provinces weekly", NOW - datetime.timedelta(hours=2), "completed", "failure"),
                  ("Holyrood weekly", NOW, "queued", ""),
                  ("Coverage watch", NOW, "completed", "success")]
        overdue = [("NI Assembly weekly last published 12 days ago", False),
                   ("eu_divisions holds NO ROWS AT ALL", True)]
        text = hs.render(NOW, mini, github, overdue, running_job=None)
        self.assertIn(":x: day-sweep", text)
        self.assertIn("eu-day-sweep", text)
        self.assertIn("never finished", text)
        self.assertIn(":x: Sunday pull", text)
        self.assertEqual(text.count("Provinces weekly"), 1)
        self.assertIn("Provinces weekly: failure x2", text)
        self.assertIn("Holyrood weekly: queued", text)
        self.assertIn("2 overdue, 1 new", text)
        self.assertLess(text.index("*NEW* eu_divisions"), text.index("NI Assembly"))

    def test_the_job_holding_the_lock_is_running_not_unfinished(self):
        mini = hs.mini_runs(LOG, SINCE)
        text = hs.render(NOW, mini, [], [], running_job="eu-day-sweep")
        self.assertNotIn("never finished", text)
        self.assertIn("running now: eu-day-sweep", text)

    def test_what_it_cannot_read_it_says(self):
        text = hs.render(NOW, None, None, None, None)
        self.assertIn("no Mini logs found", text)
        self.assertIn("could not read GitHub", text)
        self.assertIn("coverage is unknown", text)


if __name__ == "__main__":
    unittest.main()
