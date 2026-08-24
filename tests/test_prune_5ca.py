"""The 5CA prune rule (Christopher, 2026-08-24).

data/5ca reached 41MB of dated snapshots that nothing reads. The rule keeps
the newest set, the baseline, and a monthly spine -- and it must never drop
a kind's newest sheet, which is the live 5CA.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import prune_5ca


class PlanTests(unittest.TestCase):
    NAMES = [
        # one kind across three months, several per month
        "5ca-abortion-2026-06-01.csv",
        "5ca-abortion-2026-06-15.csv",
        "5ca-abortion-2026-07-06.csv",
        "5ca-abortion-2026-07-27.csv",
        "5ca-abortion-2026-08-16.csv",
        "5ca-abortion-2026-08-24.csv",
        # a devolved kind with one file
        "sd-5ca-assisted-dying-2026-08-22.csv",
    ]

    def test_newest_baseline_and_monthly_spine_survive(self):
        keep, drop = prune_5ca.plan(self.NAMES)
        self.assertIn("5ca-abortion-2026-08-24.csv", keep, "newest")
        self.assertIn("5ca-abortion-2026-06-01.csv", keep, "baseline")
        self.assertIn("5ca-abortion-2026-06-15.csv", keep, "last of June")
        self.assertIn("5ca-abortion-2026-07-27.csv", keep, "last of July")
        self.assertEqual(drop, ["5ca-abortion-2026-07-06.csv",
                                "5ca-abortion-2026-08-16.csv"],
                         "only mid-month duplicates go")

    def test_a_lone_sheet_is_never_dropped(self):
        keep, drop = prune_5ca.plan(self.NAMES)
        self.assertIn("sd-5ca-assisted-dying-2026-08-22.csv", keep)

    def test_every_kinds_newest_always_survives(self):
        """The live 5CA. If this ever fails the prune is destroying the
        current sheet, not a duplicate."""
        keep, _drop = prune_5ca.plan(self.NAMES)
        newest = {}
        for name in self.NAMES:
            m = prune_5ca.DATED.match(name)
            kind, date = m.group("kind"), m.group("date")
            if date >= newest.get(kind, ("", ""))[0]:
                newest[kind] = (date, name)
        for _kind, (_date, name) in newest.items():
            self.assertIn(name, keep)

    def test_undated_files_are_kept_never_guessed(self):
        keep, drop = prune_5ca.plan(["notes.csv", "5ca-abortion-2026-08-24.csv"])
        self.assertIn("notes.csv", keep)
        self.assertEqual(drop, [])

    def test_keep_and_drop_partition_the_input(self):
        keep, drop = prune_5ca.plan(self.NAMES)
        self.assertEqual(set(keep) | set(drop), set(self.NAMES))
        self.assertEqual(set(keep) & set(drop), set())

    def test_dry_run_is_the_default(self):
        with open(os.path.join(ROOT, "tools", "prune_5ca.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('apply = "--apply" in sys.argv', src)
        self.assertIn("dry run", src)


if __name__ == "__main__":
    unittest.main()
