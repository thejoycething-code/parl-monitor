"""Filling directions into needs_reading readings, and what never waits for a
person (src/country5ca.py fill_directions / collated_only, src/shortlist5ca.py;
Chris's bill positions of 12 October 2026). Small temporary stores; no
network."""

import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import shortlist5ca as sl  # noqa: E402
from tests.test_country_5ca import Base, QUIET, _load  # noqa: E402

tool = _load("country_5ca")
TODAY = "2026-10-18"
DIRECTION = """  - key: "{0}"
    direction: with
    status: confirmed
    confirmed_by: "Christopher Joyce"
    confirmed_on: "2026-10-12"
    areas: [1]
    why: "A test bill CitizenGO backs."
    drafted: "Claude, 12 October 2026"
"""


def add_division(db, key, number, procs, areas, tier=1, yes=210, no=220,
                 topic="głosowanie nad całością projektu."):
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO pl_divisions (division_key, term, sitting, number, voted_at, title, "
                 "topic, process_keys, areas, tier, yes, no) VALUES (?,10,1,?,?,?,?,?,?,?,?,?)",
                 (key, number, "2026-05-29T10:00:00", "Pkt. 9", topic, json.dumps(procs),
                  json.dumps(areas), tier, yes, no))
    conn.commit()
    conn.close()


class FillBase(Base):
    def setUp(self):
        super().setUp()
        self.db = os.path.join(self.tmp.name, "store.db")
        self.path = c5.stance_path("pl", self.cfg)

    def text(self):
        with open(self.path, encoding="utf-8") as h:
            return h.read()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8") as h:
            h.write(text)

    def add_direction(self, key):
        """A direction added after the drafts, as Chris's of 12 October were."""
        text = self.text()
        i = text.index("\ndivisions:")
        self.write(text[:i] + "\n" + DIRECTION.format(key) + text[i:])

    def fill(self, dry_run=False):
        return c5.fill_directions("pl", self.cfg, dry_run=dry_run, log=QUIET)


class FillTests(FillBase):
    def test_an_untouched_needs_reading_vote_becomes_the_rules_draft(self):
        self.draft()
        self.assertEqual(self.entries()["pl-10-1-6"]["status"], "needs_reading")
        self.add_direction("10/999")
        self.assertEqual(self.fill(), ["pl-10-1-6"])
        e = self.entries()["pl-10-1-6"]
        self.assertEqual((e["status"], e["yea"], e["nay"]), ("draft", 2, -2))
        self.assertNotIn("read_first", e)
        self.assertTrue(e["drafted"].startswith(c5.DRAFTED_BY))     # still the drafter's entry
        self.assertIn("Bill direction on file for 10/999 (CONFIRMED)", e["reasoning"])
        # ... so the next --auto-confirm can confirm it.
        self.assertEqual(c5.auto_report("pl", self.cfg)["pl-10-1-6"], [])
        self.assertIn("pl-10-1-6", c5.auto_confirm("pl", self.cfg, TODAY, log=QUIET)["confirmed"])

    def test_dry_run_and_a_second_run_write_nothing(self):
        self.draft()
        self.add_direction("10/999")
        before = self.text()
        self.assertEqual(self.fill(dry_run=True), ["pl-10-1-6"])
        self.assertEqual(self.text(), before)
        self.fill()
        after = self.text()
        self.assertEqual(self.fill(), [])
        self.assertEqual(self.text(), after)

    def test_without_a_direction_nothing_changes(self):
        self.draft()
        before = self.text()
        self.assertEqual(self.fill(), [])
        self.assertEqual(self.text(), before)

    def test_an_entry_a_person_touched_is_left_alone(self):
        self.draft()
        self.add_direction("10/999")
        text = self.text()
        start = text.index('- key: "pl-10-1-6"')
        cases = {
            "read_first edited": ("needs a human reading", "needs a human reading, says Ana"),
            "a comment inside": ('    vote_kind: "final"\n', '    vote_kind: "final"\n    # Ana: wait\n'),
            "a flag": ('    vote_kind: "final"\n', '    vote_kind: "final"\n    flag: "Left for a person"\n'),
        }
        for label, (old, new) in cases.items():
            with self.subTest(label):
                self.assertIn(old, text[start:])
                self.write(text[:start] + text[start:].replace(old, new, 1))
                self.assertEqual(self.fill(), [])
                self.assertEqual(self.entries()["pl-10-1-6"]["status"], "needs_reading")
        self.write(text)

    def test_an_amendment_needing_reading_is_never_filled(self):
        self.draft()
        self.assertEqual(self.entries()["pl-10-1-2"]["status"], "needs_reading")
        self.fill()                          # 10/2110 has a direction; the amendment still needs reading
        self.assertEqual(self.entries()["pl-10-1-2"]["status"], "needs_reading")

    def test_a_vote_naming_no_bill_takes_a_direction_keyed_by_its_division(self):
        add_division(self.db, "pl-10-1-7", 7, [], [9])
        self.draft()
        e = self.entries()["pl-10-1-7"]
        self.assertIn("no bill direction is on file for this item", e["read_first"])
        self.add_direction("pl-10-1-7")
        self.assertEqual(self.fill(), ["pl-10-1-7"])
        e = self.entries()["pl-10-1-7"]
        self.assertEqual((e["status"], e["yea"]), ("draft", 2))
        self.assertTrue(e["why_yea"].startswith("Voted Za on pl-10-1-7 ("))
        self.assertEqual(c5.auto_report("pl", self.cfg)["pl-10-1-7"], [])

    def test_the_tool_flag_and_the_weekly_job(self):
        self.draft()
        self.add_direction("10/999")
        self.assertEqual(c5.fill_directions("pl", self.cfg, log=QUIET), ["pl-10-1-6"])
        with open(os.path.join(ROOT, "jobs", "editions-session-judge.sh"), encoding="utf-8") as h:
            job = h.read()
        line = next(ln for ln in job.splitlines() if "tools/country_5ca.py --all-countries" in ln)
        self.assertLess(job.index("--resync-directions"), job.index("--fill-directions"))
        self.assertLess(job.index("--fill-directions"), job.index("--auto-confirm"))
        self.assertIn("--fill-directions", line)
        self.assertIn("--fill-directions", tool.__doc__)


class LiftedHoldTests(FillBase):
    """A draft the resync turned into needs_reading when its bill went on
    hold is redrafted by the rules once the bill is with/against again (12
    October 2026: four French palliative law votes needed a one-off script)."""

    HOLD = '    direction: hold\n    read_first: "Read it first."\n'

    def setUp(self):
        super().setUp()
        self.draft()
        self.write(self.text().replace("    direction: against\n", self.HOLD, 1))
        self.assertEqual(c5.resync_directions("pl", self.cfg, log=QUIET), ["pl-10-1-1", "pl-10-1-4"])
        self.assertEqual(self.entries()["pl-10-1-1"]["status"], "needs_reading")

    def lift(self, direction="with"):
        self.write(self.text().replace(self.HOLD, "    direction: {0}\n".format(direction), 1))

    def test_a_lifted_hold_redrafts_from_the_rules(self):
        self.lift("with")
        self.assertEqual(self.fill(dry_run=True), ["pl-10-1-1", "pl-10-1-4"])
        self.assertEqual(self.entries()["pl-10-1-1"]["status"], "needs_reading")
        self.assertEqual(self.fill(), ["pl-10-1-1", "pl-10-1-4"])
        e = self.entries()
        self.assertEqual((e["pl-10-1-1"]["status"], e["pl-10-1-1"]["yea"], e["pl-10-1-1"]["nay"]),
                         ("draft", 2, -2))
        self.assertEqual((e["pl-10-1-4"]["yea"], e["pl-10-1-4"]["nay"]), (-2, 2))   # a reject vote
        self.assertNotIn("read_first", e["pl-10-1-1"])
        self.assertIn("Bill direction on file for 10/2110", e["pl-10-1-1"]["reasoning"])
        self.assertEqual(c5.auto_report("pl", self.cfg)["pl-10-1-1"], [])
        self.assertEqual(self.fill(), [])                                  # a second run: nothing

    def test_an_entry_a_person_touched_stays(self):
        self.lift("against")
        text = self.text()
        start = text.index('- key: "pl-10-1-1"')
        cases = {
            "read_first edited": ("The direction of 10/2110 is on hold: ",
                                  "Ana: the direction of 10/2110 is on hold: "),
            "reasoning edited": ("so nothing is proposed.", "so nothing is proposed. Ana: wait."),
            "a comment inside": ('    vote_kind: "final"\n', '    vote_kind: "final"\n    # Ana: wait\n'),
            "a flag": ('    vote_kind: "final"\n', '    vote_kind: "final"\n    flag: "Left for a person"\n'),
        }
        for label, (old, new) in cases.items():
            with self.subTest(label):
                self.assertIn(old, text[start:])
                self.write(text[:start] + text[start:].replace(old, new, 1))
                self.assertNotIn("pl-10-1-1", self.fill())
                self.assertEqual(self.entries()["pl-10-1-1"]["status"], "needs_reading")
        self.write(text)

    def test_a_bill_still_on_hold_stays_needs_reading(self):
        self.assertEqual(self.fill(), [])
        e = self.entries()["pl-10-1-1"]
        self.assertEqual((e["status"], e.get("yea")), ("needs_reading", None))
        self.assertIn("on hold: read it first", e["read_first"])


class NeverWaitsTests(FillBase):
    """Collated-only readings (migration) and readings Chris took out of play
    never appear as needing a person."""

    def setUp(self):
        super().setUp()
        add_division(self.db, "pl-10-1-8", 8, ["10/888"], [11])          # migration only
        self.draft()
        # Not scored (Chris, 12 October 2026): confirmed out of play.
        c5._rewrite("pl", {"pl-10-1-6": ({"status": "confirmed", "placeable": False,
                                          "reason": "No CitizenGO stake (Chris, 12 Oct 2026): test",
                                          "confirmed_by": "Christopher Joyce",
                                          "confirmed_on": "2026-10-12"}, ("read_first",))}, self.cfg)

    def test_the_migration_reading_is_collated_only(self):
        e = self.entries()["pl-10-1-8"]
        self.assertEqual((e["status"], e["areas"]), ("needs_reading", [11]))
        self.assertTrue(c5.collated_only(e))
        self.assertFalse(c5.collated_only(self.entries()["pl-10-1-1"]))
        self.assertFalse(c5.collated_only({"areas": [11, 9]}))         # a mixed vote still counts

    def test_neither_is_waiting_in_counts_checks_shortlist_or_digest(self):
        c = c5.counts("pl", self.cfg)
        self.assertEqual(c["collated"], 1)
        self.assertEqual(c["needs_reading"], 1)                        # pl-10-1-2 only
        rep = c5.auto_report("pl", self.cfg)
        self.assertNotIn("pl-10-1-8", rep)
        self.assertNotIn("pl-10-1-6", rep)
        keys = [it["key"] for it in sl.rank("pl", self.cfg, today=TODAY)]
        self.assertNotIn("pl-10-1-8", keys)
        self.assertNotIn("pl-10-1-6", keys)
        digest = c5.digest_text(TODAY, self.cfg, self.docs, countries=("pl",))
        self.assertNotIn("pl-10-1-8", digest)
        self.assertNotIn("pl-10-1-6", digest)

    def test_the_guide_shows_them_without_a_box(self):
        doc = c5.signoff_markdown("pl", self.cfg)
        self.assertIn("## Collated only", doc)
        self.assertIn("- `pl-10-1-8`", doc)
        self.assertNotIn("[ ] `pl-10-1-8`", doc)
        needs = doc.split("## Needs reading")[1].split("\n## ")[0]
        self.assertNotIn("pl-10-1-8", needs)
        self.assertNotIn("pl-10-1-6", needs)
        self.assertIn("out of play: No CitizenGO stake (Chris, 12 Oct 2026): test", doc)

    def test_left_for_a_person_is_lifted_with_its_flag(self):
        def item():
            return next(it for it in sl.rank("pl", self.cfg, today=TODAY) if it["key"] == "pl-10-1-2")
        before = item()["points"]
        c5._rewrite("pl", {"pl-10-1-2": ({"flag": c5.LEFT_FOR_PERSON + " (Chris, 12 Oct 2026): mixed"},
                                         ())}, self.cfg)
        got = item()
        self.assertEqual(got["points"], before + 40)
        self.assertIn("left for a person by Chris", got["why"])
        doc = sl.shortlist_markdown("pl", sl.rank("pl", self.cfg, today=TODAY), TODAY)
        self.assertIn("**Flag:** Left for a person (Chris, 12 Oct 2026): mixed", doc)

    def test_a_reading_taken_out_of_play_is_not_shortlisted(self):
        c5.amend("pl", "pl-10-1-2", "Christopher", take_out=True, why="Not ours.", on="2026-10-12",
                 config_dir=self.cfg, log=QUIET)
        self.assertNotIn("pl-10-1-2", [it["key"] for it in sl.rank("pl", self.cfg, today=TODAY)])


if __name__ == "__main__":
    unittest.main()
