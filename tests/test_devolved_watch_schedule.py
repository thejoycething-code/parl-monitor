"""The devolved watch's runner wiring and its schedule (2026-10-09).

One shared job for Holyrood, the Senedd and the Assembly: jobs/devolved-watch.sh,
a launchd plist in London time, and a mini-check-gated GitHub backup. Its
slots must stay clear of the Westminster division watch on the runner lock,
and its crons must collide with no other workflow's.
"""

import glob
import os
import plistlib
import re
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")
PLISTS = os.path.join(ROOT, "ops", "launchd")


def plist_slots(name):
    with open(os.path.join(PLISTS, "net.citizengo.parlmonitor.{0}.plist".format(name)), "rb") as fh:
        doc = plistlib.load(fh)
    slots = doc["StartCalendarInterval"]
    slots = slots if isinstance(slots, list) else [slots]
    return doc, [(s.get("Weekday"), s.get("Hour", 0), s.get("Minute", 0)) for s in slots]


def crons(name):
    doc = yaml.safe_load(open(os.path.join(WF, name), encoding="utf-8"))
    on = doc.get("on", doc.get(True))
    return [c["cron"] for c in on.get("schedule") or []]


def expand(cron):
    """[(weekday 0-6 Sun=0, hour, minute)] for a simple cron."""
    minute, hour, _dom, _mon, dow = cron.split()
    days = []
    for part in dow.split(","):
        if "-" in part:
            a, b = part.split("-")
            days += list(range(int(a), int(b) + 1))
        elif part == "*":
            days += list(range(7))
        else:
            days.append(int(part))
    return [(d % 7, int(h), int(minute)) for d in days for h in hour.split(",")]


def minutes_apart(a, b):
    if a[0] != b[0]:
        return 24 * 60
    return abs((a[1] * 60 + a[2]) - (b[1] * 60 + b[2]))


class WiringTests(unittest.TestCase):
    def test_job_script_runs_the_tool_without_a_store_and_publishes_the_archive(self):
        src = open(os.path.join(ROOT, "jobs", "devolved-watch.sh"), encoding="utf-8").read()
        self.assertRegex(src, r"(?m)^# mini_run: no-store")
        self.assertIn("python3 tools/devolved_brief.py", src)
        self.assertLess(src.index("tools/devolved_brief.py"), src.index("raw_state.py --push"))
        self.assertNotIn("db_state.py", src)

    def test_plist_calls_the_runner_for_this_job(self):
        doc, _slots = plist_slots("devolved-watch")
        self.assertEqual(doc["ProgramArguments"][-2:],
                         ["/Users/christopherjoyce/runner/parl-monitor/tools/mini_run.sh", "devolved-watch"])

    def test_workflow_is_gated_and_shares_the_script(self):
        text = open(os.path.join(WF, "devolved-watch.yml"), encoding="utf-8").read()
        self.assertIn("uses: ./.github/workflows/mini-check.yml", text)
        self.assertIn("job: DEVOLVED_WATCH", text)
        self.assertIn("needs.mini-check.outputs.run == 'true'", text)
        self.assertIn("bash jobs/devolved-watch.sh", text)
        self.assertIn("SLACK_DM_USER_ID: U05LJP0BT61", text)
        self.assertIn("git add data/raw.json data/briefs", text)


class ScheduleTests(unittest.TestCase):
    def test_github_crons_are_the_plist_slots_in_bst(self):
        _doc, slots = plist_slots("devolved-watch")
        london = sorted((d % 7, h, m) for d, h, m in slots)
        utc = sorted((d, h + 1, m) for c in crons("devolved-watch.yml") for d, h, m in expand(c))
        self.assertEqual(london, utc)

    def test_no_other_workflow_shares_a_cron(self):
        mine = set(crons("devolved-watch.yml"))
        for path in glob.glob(os.path.join(WF, "*.yml")):
            if path.endswith("devolved-watch.yml"):
                continue
            others = set(re.findall(r'^\s*-\s*cron:\s*"([^"]+)"', open(path, encoding="utf-8").read(), re.M))
            self.assertFalse(mine & others, os.path.basename(path))

    def test_clear_of_the_westminster_division_watch_on_the_runner_lock(self):
        """An hour either side of every Westminster slot: the devolved run
        takes a minute or two, so it never holds the lock when the Commons
        brief wants it (19:00/22:00 Mon-Thu, 14:00/16:00/18:00 Fri)."""
        _doc, mine = plist_slots("devolved-watch")
        _doc, uk = plist_slots("division-watch")
        for a in mine:
            for b in uk:
                self.assertGreaterEqual(minutes_apart(a, b), 60, (a, b))

    def test_no_slot_starts_with_another_mini_job(self):
        _doc, mine = plist_slots("devolved-watch")
        for path in glob.glob(os.path.join(PLISTS, "*.plist")):
            name = os.path.basename(path).split(".")[-2]
            if name == "devolved-watch":
                continue
            with open(path, "rb") as fh:
                slots = plistlib.load(fh).get("StartCalendarInterval") or []
            slots = slots if isinstance(slots, list) else [slots]
            for s in slots:
                theirs = (s.get("Hour", 0), s.get("Minute", 0))
                for d, h, m in mine:
                    if s.get("Weekday") in (None, d):
                        self.assertNotEqual(theirs, (h, m), name)

    def test_the_evening_pass_follows_holyrood_publication(self):
        """Measured: the latest same-evening Holyrood publication was 19:00
        London; the latest next-morning one 12:22."""
        _doc, mine = plist_slots("devolved-watch")
        evening = [(h, m) for _d, h, m in mine if h >= 18]
        morning = [(h, m) for _d, h, m in mine if h < 18]
        self.assertTrue(evening and all((h, m) > (19, 0) for h, m in evening))
        self.assertTrue(morning and all((h, m) > (12, 22) for h, m in morning))


if __name__ == "__main__":
    unittest.main()
