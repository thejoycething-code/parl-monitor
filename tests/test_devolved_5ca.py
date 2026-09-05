"""Devolved 5CA wiring (Christopher, 2026-09-04: "Wire them").

tools/sp_5ca.py, sd_5ca.py and ni_5ca.py were finished, correct and run
NOWHERE -- no workflow, no run_monday -- so Scotland's assisted-dying
sheet, which places all 129 MSPs from recorded votes with
human-confirmed meaning lines, was only as fresh as the last time
somebody typed the command.
"""

import csv
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


d5 = _load("devolved_5ca")


def sheet(rows):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
    return path


HEADER = ["Decision-Maker", "++", "+", "0", "-", "--", "Target (Y/N)"]


class PlacementTests(unittest.TestCase):
    def test_a_sheet_that_places_nobody_is_not_kept(self):
        """Every member at 0 is the state before any act is confirmed: a
        member list with an empty grid, carrying no campaign information."""
        path = sheet([HEADER,
                      ["Ms A (Alliance) - North Down", "", "", "1", "", "", ""],
                      ["Mr B (DUP) - Strangford", "", "", "1", "", "", ""]])
        self.assertFalse(d5.places_anyone(path))
        os.unlink(path)

    def test_the_totals_row_is_not_a_placement(self):
        """THE BUG THIS EXISTS FOR. Every sheet ends with
        "Totals - 90 decision-makers, 0, 0, 90, 0, 0", and a naive
        truthiness test reads those zeroes as marks -- which kept ten NI
        sheets on which nobody was placed at all (2026-09-04)."""
        path = sheet([HEADER,
                      ["Ms A (Alliance) - North Down", "", "", "1", "", "", ""],
                      ["Totals - 90 decision-makers", "0", "0", "90", "0",
                       "0", ""]])
        self.assertFalse(d5.places_anyone(path))
        os.unlink(path)

    def test_one_real_placement_is_enough(self):
        path = sheet([HEADER,
                      ["Ms A (Alliance) - North Down", "x", "", "", "", "", ""],
                      ["Mr B (DUP) - Strangford", "", "", "1", "", "", ""],
                      ["Totals - 2 decision-makers", "1", "0", "1", "0", "0", ""]])
        self.assertTrue(d5.places_anyone(path))
        os.unlink(path)

    def test_a_placement_against_us_counts_too(self):
        path = sheet([HEADER,
                      ["Mr B (DUP) - Strangford", "", "", "", "", "x", ""],
                      ["Totals - 1 decision-makers", "0", "0", "0", "0", "1", ""]])
        self.assertTrue(d5.places_anyone(path))
        os.unlink(path)

    def test_a_missing_sheet_places_nobody(self):
        self.assertFalse(d5.places_anyone(
            os.path.join(ROOT, "tests", "fixtures", "no-such-sheet.csv")))


class WiringTests(unittest.TestCase):
    def test_each_nation_has_a_tool_and_a_stance_file(self):
        for nation, (tool, prefix, stance, _label) in d5.NATIONS.items():
            self.assertTrue(os.path.exists(os.path.join(ROOT, "tools", tool)),
                            "{0}: {1} is gone".format(nation, tool))
            self.assertTrue(os.path.exists(os.path.join(ROOT, stance)),
                            "{0}: {1} is gone".format(nation, stance))

    def test_every_weekly_refreshes_its_own_nation(self):
        """The whole point: these run in CI, not on somebody's laptop."""
        for wf, nation in ((".github/workflows/sp-weekly.yml", "scotland"),
                           (".github/workflows/sd-weekly.yml", "wales"),
                           (".github/workflows/ni-weekly.yml", "ni")):
            src = open(os.path.join(ROOT, wf), encoding="utf-8").read()
            self.assertIn("devolved_5ca.py --nation {0}".format(nation), src,
                          "{0} does not refresh its 5CA".format(wf))

    def test_the_sheets_do_not_accumulate(self):
        """Westminster writes a DATED sheet per area per run and data/5ca
        reached 109 files and 47MB in git -- the shape of the problem that
        forced the store out of the repo. The devolved sheets overwrite one
        file per nation per area instead."""
        src = open(os.path.join(ROOT, "tools", "devolved_5ca.py"),
                   encoding="utf-8").read()
        self.assertIn('"{0}-5ca-{1}.csv"', src,
                      "the filename must carry no date")
        self.assertNotIn("datetime.date.today().isoformat()", src)

    def test_the_prune_runs_where_the_dated_sheets_are_made(self):
        """tools/prune_5ca.py was written for exactly this growth and was
        wired nowhere either."""
        src = open(os.path.join(ROOT, "run_monday.py"), encoding="utf-8").read()
        self.assertIn('"prune_5ca.py")]', src,
                      "prune_5ca is mentioned but never actually run")
        self.assertIn('argv.append("--apply")', src)

    def test_a_rehearsal_deletes_nothing(self):
        """NO_PUBLISH already means "this run is a rehearsal". Removing
        31MB of tracked sheets is a larger act than deploying a site, so a
        rehearsal reports what it would free and touches nothing."""
        src = open(os.path.join(ROOT, "run_monday.py"), encoding="utf-8").read()
        block = src[src.index("rehearsal = os.environ"):]
        self.assertIn('NO_PUBLISH") == "1"', block)
        self.assertLess(block.index("if not rehearsal:"),
                        block.index('argv.append("--apply")'),
                        "--apply must be gated on the rehearsal flag")

    def test_a_nation_with_no_sheets_says_so(self):
        """Never silent: a nation whose acts place nobody is the normal
        state before anything is confirmed, and must not read as a run
        that did nothing."""
        src = open(os.path.join(ROOT, "tools", "devolved_5ca.py"),
                   encoding="utf-8").read()
        self.assertIn("no sheet published", src)


class WafToleranceTests(unittest.TestCase):
    """senedd.wales answers a laptop and 403s GitHub's runners (measured
    2026-09-05): the Azure WAF that already owned business.senedd.wales
    now reaches the committee index for datacentre IPs.

    Exiting 1 turned the Senedd weekly red EVERY week over a source
    merely refusing robots, and a weekly red run trains people to ignore
    the alert.
    """

    def test_an_unreachable_committee_list_is_a_gap_not_a_crash(self):
        src = open(os.path.join(ROOT, "tools", "sd_committees.py"),
                   encoding="utf-8").read()
        block = src[src.index("committee list unreachable"):]
        block = block[:block.index("\n    if only:")]
        self.assertIn("return 0", block,
                      "a source refusing robots must not fail the weekly")
        self.assertNotIn("return 1", block)

    def test_the_gap_is_still_recorded_and_printed(self):
        """Softening the exit code must not soften the DISCLOSURE."""
        src = open(os.path.join(ROOT, "tools", "sd_committees.py"),
                   encoding="utf-8").read()
        before = src[:src.index("committee list unreachable")]
        self.assertIn("INSERT OR IGNORE INTO gaps", before)

    def test_it_is_only_safe_because_the_staleness_is_watched(self):
        """The reason this can be a gap at all: if the committee data
        really stops refreshing, tools/coverage.py says so."""
        cov = _load("coverage")
        self.assertIn("sd_committees", {f[0] for f in cov.FEEDS})


if __name__ == "__main__":
    unittest.main()
