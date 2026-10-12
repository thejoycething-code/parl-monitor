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


class GitHubMinutesTests(unittest.TestCase):
    """The minutes line counts as billing does and tracks the going-private bar."""

    def test_each_job_rounds_up_and_skipped_jobs_are_free(self):
        jobs = [{"conclusion": "success", "started_at": "2026-10-09T10:00:00Z", "completed_at": "2026-10-09T10:00:05Z"},
                {"conclusion": "success", "started_at": "2026-10-09T10:00:00Z", "completed_at": "2026-10-09T10:02:01Z"},
                {"conclusion": "skipped", "started_at": "2026-10-09T10:00:00Z", "completed_at": "2026-10-09T10:09:00Z"},
                {"conclusion": None, "started_at": "2026-10-09T10:00:00Z", "completed_at": None}]
        self.assertEqual(hs.job_minutes(jobs), 1 + 3)

    def _rows(self, per_day, today_minutes=0):
        now = datetime.datetime(2026, 10, 20, 6, 30, tzinfo=UTC)
        rows = [(now - datetime.timedelta(hours=1), "workflow_dispatch", today_minutes)]
        for back, mins in enumerate(per_day, 1):      # back=1 is yesterday
            rows.append((now - datetime.timedelta(days=back, hours=1), "schedule", mins))
        return now, rows

    def test_streak_counts_whole_days_back_from_yesterday(self):
        now, rows = self._rows([20, 30, 59, 61, 10, 10, 10, 10], today_minutes=500)
        m = hs.minutes_summary(rows, now)
        self.assertEqual(m["streak"], 3)           # 20, 30, 59 -- then 61 breaks it
        self.assertEqual(m["week"], 20 + 30 + 59 + 61 + 10 + 10 + 10)

    def test_seven_quiet_days_say_ready(self):
        now, rows = self._rows([25] * 8)
        m = hs.minutes_summary(rows, now)
        self.assertEqual(m["streak"], 7)
        self.assertIn("ready to make the repo private", hs.render(now, [], [], [], None, m))

    def test_last_24h_is_split_by_trigger(self):
        now, rows = self._rows([25] * 8, today_minutes=40)
        text = hs.render(now, [], [], [], None, hs.minutes_summary(rows, now))
        self.assertIn("last 24h: 40 (hand-started 40)", text)
        self.assertIn("7 needed before going private", hs.render(now, [], [], [], None,
                      hs.minutes_summary(self._rows([25, 80] + [25] * 6)[1], now)))

    def test_unreadable_minutes_say_so(self):
        self.assertIn("could not count GitHub's minutes", hs.render(NOW, [], [], [], None, None))


if __name__ == "__main__":
    unittest.main()
