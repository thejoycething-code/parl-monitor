"""The new countries' section of the daily health summary (src/country_health.py)."""
import datetime
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import health_summary as hs  # noqa: E402
from src import country_health as ch  # noqa: E402

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 11, 6, 30, tzinfo=UTC)

LOG = """2026-10-03T03:00:04Z mini_run pl-weekly (ref main)
2026-10-03T04:00:00Z mini_run pl-weekly done
2026-10-10T03:00:04Z mini_run pl-weekly (ref main)
  [gap] the week-ahead agenda step failed
  [gap] positions 1: fetch failed after 1 attempt(s) for pl-rollcalls/x: https://example/agenda
  [gap] pl-chamber exited 3 (see the gaps table); the store and edition go on
  [gap] vote briefs failed for pl; the next run retries
2026-10-10T04:02:30Z mini_run pl-weekly done
2026-10-10T14:00:03Z mini_run pt-weekly (ref main)
  FAILED at commit state: the job changed the store but did not publish it
2026-09-20T07:00:04Z mini_run ch-weekly (ref main)
2026-09-20T07:58:25Z mini_run ch-weekly done
2026-10-10T07:00:04Z mini_run ch-weekly (ref main)
  FAILED at lock: lock held by eu-weekly for 7200s
2026-09-25T07:00:04Z mini_run it-weekly (ref main)
2026-09-25T07:58:25Z mini_run it-weekly done
2026-10-10T05:40:04Z mini_run vote-briefs-daily (ref main)
2026-10-10T05:41:40Z mini_run vote-briefs-daily done
2026-10-10T01:40:11Z mini_run latam-courts-backfill (ref main)
  [gap] pe-courts recorded gaps or failed
2026-10-10T03:22:58Z mini_run latam-courts-backfill done
""".splitlines()


def runs():
    return sorted(hs.mini_runs_full(LOG), key=lambda r: r[1])


def when(ts):
    return ts.strftime("%a %H:%M")


class ParseTests(unittest.TestCase):
    def test_gap_lines_belong_to_their_run(self):
        pl = [r for r in runs() if r[0] == "pl-weekly"]
        self.assertEqual(len(pl), 2)
        self.assertEqual(pl[0][3], [])
        self.assertEqual(len(pl[1][3]), 4)

    def test_old_mini_runs_unchanged(self):
        since = datetime.datetime(2026, 10, 10, 0, 0, tzinfo=UTC)
        self.assertEqual([(j, o) for j, _s, o in hs.mini_runs(LOG, since)][:2],
                         [("pl-weekly", "ok"), ("pt-weekly", "FAILED at commit state: the job "
                                                            "changed the store but did not publish it")])

    def test_steps(self):
        self.assertEqual(ch.step_of("[gap] the week-ahead agenda step failed"), "agenda")
        self.assertEqual(ch.step_of("[gap] the edition or its DM failed"), "edition")
        self.assertEqual(ch.step_of("[gap] the judge left items unscored"), "judge")
        self.assertEqual(ch.step_of("[gap] pe-courts recorded gaps or failed"), "courts")
        self.assertEqual(ch.step_of("[gap] be-chamber exited 3"), "chamber")
        self.assertEqual(ch.step_of("[gap] vote briefs failed for pl"), "vote briefs")
        self.assertEqual(ch.step_of("[gap] country-drive: Drive failed"), "drive")
        self.assertEqual(ch.step_of("[gap] x: fetch failed for pa-rollcalls/agenda-list"), "source")
        self.assertEqual(ch.step_of("[gap] anything", "latam-courts-backfill"), "backfill")


class CadenceTests(unittest.TestCase):
    def test_plists(self):
        self.assertEqual(ch.plist_cadence("pl-weekly"), 7)
        self.assertEqual(ch.plist_cadence("latam-monthly"), 31)
        self.assertEqual(ch.plist_cadence("editions-session-judge"), 7)
        self.assertLessEqual(ch.plist_cadence("vote-briefs-daily"), 3)
        self.assertIsNone(ch.plist_cadence("no-such-job"))

    def test_coverage_knows_the_fortnightly_ones(self):
        import coverage
        self.assertEqual(ch.cadence("mx-weekly", coverage.PIPELINES)[0], 14)
        self.assertEqual(ch.cadence("pl-weekly", coverage.PIPELINES), (7, 2))


class StateTests(unittest.TestCase):
    def setUp(self):
        self.states = ch.job_states(runs(), ch.all_jobs(), NOW)

    def test_ok_failed_stale_none(self):
        self.assertEqual(self.states["pl-weekly"]["status"], "ok")
        self.assertEqual(self.states["pt-weekly"]["status"], "failed")
        self.assertFalse(self.states["pt-weekly"].get("stale"))     # its first night
        self.assertTrue(self.states["ch-weekly"].get("stale"))      # last ok 20 Sept
        self.assertTrue(self.states["it-weekly"].get("stale"))      # ok, but 16 days ago
        self.assertEqual(self.states["nl-weekly"]["status"], "none")
        self.assertFalse(self.states["latam-courts-backfill"].get("stale"))


class OverdueTests(unittest.TestCase):
    def test_keys_go_to_their_country(self):
        wf = ch.workflow_ccs()
        self.assertEqual(ch.cc_of_key("pipeline:Poland weekly", wf), "pl")
        self.assertEqual(ch.cc_of_key("feed:pl_divisions", wf), "pl")
        self.assertEqual(ch.cc_of_key("empty:ve_news", wf), "latam")
        self.assertEqual(ch.cc_of_key("lost:Peru weekly:pe_rulings", wf), "pe")
        self.assertEqual(ch.cc_of_key("feed:country_agenda", wf), "shared")
        self.assertIsNone(ch.cc_of_key("pipeline:Sunday pull", wf))
        self.assertIsNone(ch.cc_of_key("feed:eu_divisions", wf))
        self.assertIsNone(ch.cc_of_key("lost:US weekly:us_bills", wf))
        self.assertIsNone(ch.cc_of_key("feed:ni_items", wf))      # Northern Ireland, not Nicaragua


class SectionTests(unittest.TestCase):
    def test_problems_first_and_overdue_moved(self):
        found = [("feed:pl_divisions", 40, "pl_divisions last saw data 40 days ago", True),
                 ("pipeline:Sunday pull", 9, "Sunday pull last published 9 days ago", False)]
        lines, rest = ch.section(runs(), found, NOW, when)
        text = "\n".join(lines)
        self.assertEqual(rest, [("Sunday pull last published 9 days ago", False)])
        europe = text.split("*Latam*")[0]
        self.assertIn(":x: pt-weekly", europe)
        self.assertIn(":x: ch-weekly", europe)
        self.assertIn("stale", europe)
        self.assertIn("stale: it-weekly", europe)
        self.assertIn("*NEW* overdue: pl_divisions", europe)
        self.assertIn("pl agenda 1, chamber 1, vote briefs 1", europe)
        self.assertIn("pl 1", europe.split("source gaps")[1])
        self.assertIn("no Mini run yet: ", europe)
        # the failed line comes before the gap lines
        self.assertLess(europe.index(":x:"), europe.index("step gaps in the last run"))
        self.assertIn("vote-briefs-daily ok", text)
        self.assertIn("editions-session-judge not run on the Mini yet", text)

    def test_a_clean_region_is_one_line(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "editions"))
        for cc in ch.EDITION_CCS:
            open(os.path.join(root, "editions", "{0}-monitor-2026-10-10.md".format(cc)), "w").close()
        clean = []
        for cc in ch.LATAM + ("latam",):
            clean.append((ch.job_of(cc), NOW - datetime.timedelta(days=1), "ok", []))
        states = ch.job_states(clean, ch.all_jobs(), NOW, root=ROOT)
        eds = ch.edition_ages(NOW.date(), root)
        lines = ch.region_lines("Latam", ch.LATAM + ("latam",), ("latam-courts-backfill",),
                                states, eds, {}, NOW, when)
        self.assertEqual(len(lines), 1)
        self.assertIn("all 15 jobs ok", lines[0])
        self.assertIn("editions 4/4 current", lines[0])

    def test_no_logs_and_no_store_say_so(self):
        lines, rest = ch.section(None, None, NOW, when)
        text = "\n".join(lines)
        self.assertIn("no Mini logs found", text)
        self.assertIn("could not be read", text)
        self.assertIsNone(rest)
        self.assertNotIn("all 12 jobs ok", text)

    def test_render_does_not_name_country_failures_twice(self):
        mini = [(j, s, o) for j, s, o, _g in runs()]
        lines, _rest = ch.section(runs(), [], NOW, when)
        text = hs.render(NOW, mini, [], [], None, countries=lines, moved=1,
                         country_jobs=ch.all_jobs())
        self.assertEqual(text.count("pt-weekly"), 1)
        self.assertIn("more on the new countries' jobs", text)
        self.assertIn("are under Country editions", text)



if __name__ == "__main__":
    unittest.main()
