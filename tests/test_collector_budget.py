"""tools/collector_budget.sh: a collector's budget leaves room for the publish.

The Dominican Republic's first backfill on the Mini (10 October 2026) spent a
fixed 45-minute budget, then the later steps and a 15-minute store upload ran
past the hour's JOB_TIMEOUT and nothing was published.
"""

import glob
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(ROOT, "tools", "collector_budget.sh")


def budget(*args, **env):
    full = {k: v for k, v in os.environ.items() if k not in ("GITHUB_ACTIONS", "JOB_TIMEOUT")}
    full.update(env)
    out = subprocess.run(["bash", HELPER] + [str(a) for a in args], env=full,
                         capture_output=True, text=True, check=True)
    return int(out.stdout.strip())


class TestCollectorBudget(unittest.TestCase):
    def test_hour_leaves_room_for_the_publish(self):
        got = budget(2700, 5, JOB_TIMEOUT="3600")
        self.assertEqual(got, 3600 - 5 - 1500)
        self.assertLessEqual(5 + got + 1200, 3600)

    def test_default_limit_is_an_hour(self):
        self.assertEqual(budget(2700, 0), 2100)

    def test_cap_wins_when_the_limit_is_long(self):
        self.assertEqual(budget(2700, 5, JOB_TIMEOUT="10800"), 2700)
        self.assertEqual(budget(1800, 5, JOB_TIMEOUT="3600"), 1800)

    def test_later_steps_are_kept_too(self):
        self.assertEqual(budget(2700, 0, 600, JOB_TIMEOUT="3600"), 1500)

    def test_never_below_a_minute(self):
        self.assertEqual(budget(2700, 3500, JOB_TIMEOUT="3600"), 60)

    def test_github_keeps_the_cap(self):
        self.assertEqual(budget(2700, 3000, GITHUB_ACTIONS="true", JOB_TIMEOUT="3600"), 2700)


class TestWeekliesUseIt(unittest.TestCase):
    def test_no_country_collector_has_a_bare_fixed_budget(self):
        # The US weekly runs under three hours and sizes its last collector
        # (the Congressional Record) from the clock itself.
        bare = []
        for path in sorted(glob.glob(os.path.join(ROOT, "jobs", "*-weekly.sh"))):
            if path.endswith("us-weekly.sh"):
                continue
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            for line in text.splitlines():
                if line.lstrip().startswith("#"):
                    continue
                if re.search(r"_rollcalls\.py\b.*(?<!doc-)--budget-seconds [0-9]", line):
                    bare.append(os.path.basename(path))
        self.assertEqual(bare, [])

    def test_dominican_republic_uses_it(self):
        with open(os.path.join(ROOT, "jobs", "do-weekly.sh"), encoding="utf-8") as handle:
            self.assertIn('collector_budget.sh 2700 "$SECONDS"', handle.read())

    def test_mini_run_exports_the_limit(self):
        with open(os.path.join(ROOT, "tools", "mini_run.sh"), encoding="utf-8") as handle:
            self.assertIn("export JOB_TIMEOUT", handle.read())


if __name__ == "__main__":
    unittest.main()
