"""The automatic sign-off on delegation and the signers' amendments for the
new countries (src/country5ca.py auto_check / auto_confirm / amend /
resync_directions, tools/country_5ca.py --auto-confirm / --amend; Chris, 11
October 2026). Small temporary stores and stance files; no network."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import readings5ca as r5  # noqa: E402
from tests.test_country_5ca import Base, QUIET, _load  # noqa: E402

tool = _load("country_5ca")
TODAY = "2026-10-18"


class AutoBase(Base):
    def setUp(self):
        super().setUp()
        self.draft()
        self.path = c5.stance_path("pl", self.cfg)

    def text(self):
        with open(self.path, encoding="utf-8") as h:
            return h.read()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8") as h:
            h.write(text)

    def edit_entry(self, key, old, new):
        """Replace `old` with `new` inside one entry's block only."""
        text = self.text()
        start = text.index('- key: "{0}"'.format(key))
        end = text.find("\n\n", start)
        end = len(text) if end < 0 else end
        block = text[start:end]
        self.assertIn(old, block)
        self.write(text[:start] + block.replace(old, new, 1) + text[end:])

    def checks(self):
        return c5.auto_report("pl", self.cfg)

    def failed(self, key):
        return [c for c, _ in self.checks()[key]]

    def auto(self, dry_run=False):
        return c5.auto_confirm("pl", self.cfg, TODAY, dry_run=dry_run, log=QUIET)


class ConfirmTests(AutoBase):
    def test_passing_drafts_are_confirmed_and_stamped(self):
        got = self.auto()
        self.assertEqual(sorted(got["confirmed"]), ["pl-10-1-1", "pl-10-1-4"])
        e = self.entries()["pl-10-1-1"]
        self.assertEqual((e["status"], e["confirmed_by"], e["confirmed_on"], e["auto_checks"]),
                         ("confirmed", c5.AUTO_BY, TODAY, c5.AUTO_CHECKS_VERSION))
        self.assertEqual((e["yea"], e["nay"]), (-2, 2))          # the values are left as drafted
        self.assertEqual(r5.status(e), "confirmed")
        self.assertEqual(sorted(got["left"]), ["pl-10-1-2", "pl-10-1-3", "pl-10-1-6"])
        self.assertEqual(self.entries()["pl-10-1-2"]["status"], "needs_reading")

    def test_dry_run_writes_nothing(self):
        before = self.text()
        got = self.auto(dry_run=True)
        self.assertEqual(sorted(got["confirmed"]), ["pl-10-1-1", "pl-10-1-4"])
        self.assertEqual(self.text(), before)

    def test_a_second_run_changes_nothing(self):
        self.auto()
        after = self.text()
        self.assertEqual(self.auto()["confirmed"], [])
        self.assertEqual(self.text(), after)

    def test_confirmed_entries_are_never_touched(self):
        c5.confirm("pl", ["pl-10-1-1"], "Christopher", "2026-10-11", self.cfg, log=QUIET)
        before = self.entries()["pl-10-1-1"]
        self.auto()
        self.assertEqual(self.entries()["pl-10-1-1"], before)
        self.assertEqual(before["confirmed_by"], "Christopher")


class CheckTests(AutoBase):
    def test_needs_reading_is_left(self):
        self.assertEqual(self.failed("pl-10-1-2"), ["reading"])
        self.assertEqual(self.failed("pl-10-1-6"), ["reading"])

    def test_procedural_is_not_placeable(self):
        self.assertEqual(self.failed("pl-10-1-3"), ["placeable"])

    def test_direction_must_be_settled(self):
        text = self.text().replace('    why: "Registered cohabitation contracts."\n',
                                   '    why: "Registered cohabitation contracts."\n'
                                   '    flag: "check this"\n', 1)
        self.write(text)
        self.assertIn("direction", self.failed("pl-10-1-1"))
        self.write(text.replace("    direction: against\n", "    direction: hold\n", 1))
        self.assertIn("direction", self.failed("pl-10-1-1"))
        self.assertEqual(self.auto()["confirmed"], [])

    def test_a_flag_of_its_own_is_left_but_a_cleared_bill_flag_copy_is_not(self):
        self.edit_entry("pl-10-1-1", "    vote_kind:", '    flag: "check the question"\n    vote_kind:')
        self.assertIn("direction", self.failed("pl-10-1-1"))
        self.edit_entry("pl-10-1-4", "    vote_kind:",
                        '    flag: "On the bill\'s direction: now settled."\n    vote_kind:')
        self.assertEqual(self.failed("pl-10-1-4"), [])

    def test_kind_must_be_final_or_reject(self):
        self.edit_entry("pl-10-1-1", 'vote_kind: "final"', 'vote_kind: "inverted"')
        self.assertIn("kind", self.failed("pl-10-1-1"))

    def test_values_must_equal_the_rules(self):
        self.edit_entry("pl-10-1-1", "yea: -2", "yea: -1")
        self.assertEqual(self.failed("pl-10-1-1"), ["values"])
        self.assertEqual(self.auto()["confirmed"], ["pl-10-1-4"])
        self.assertEqual(self.entries()["pl-10-1-1"]["status"], "draft")

    def test_why_lines_must_equal_the_rules(self):
        self.edit_entry("pl-10-1-4", "for rejecting it", "for throwing it out")
        self.assertEqual(self.failed("pl-10-1-4"), ["values"])

    def test_unanimous_or_untallied_votes_are_not_placeable(self):
        self.edit_entry("pl-10-1-1", "Przeciw 198", "Przeciw 0")
        self.assertEqual(self.failed("pl-10-1-1"), ["placeable"])
        text = self.text()
        start = text.index('- key: "pl-10-1-4"')
        block = text[start:text.find("\n\n", start)]
        bare = "\n".join(ln for ln in block.split("\n")
                         if not ln.lstrip().startswith(("result:", "lobbies:")))
        self.write(text.replace(block, bare))
        self.assertEqual(self.failed("pl-10-1-4"), ["placeable"])
        self.assertIn("no recorded tally", self.checks()["pl-10-1-4"][0][1])

    def test_store_positions_give_a_tally_the_file_lacks(self):
        e = dict(self.entries()["pl-10-1-4"])
        e.pop("result"), e.pop("lobbies")
        _, bills, _ = c5.load("pl", self.cfg)
        self.assertEqual([c for c, _ in c5.auto_check("pl", e["key"], e, bills, conn=self.conn)], [])

    def test_hand_edits_and_comments_are_left(self):
        self.edit_entry("pl-10-1-1", "    vote_kind:", "    # Ania: check the club split\n    vote_kind:")
        self.assertEqual(self.failed("pl-10-1-1"), ["drafted"])
        self.edit_entry("pl-10-1-4", 'drafted: "tools/country_5ca.py', 'drafted: "Claude, by hand; tools')
        self.assertEqual(self.failed("pl-10-1-4"), ["drafted"])
        self.assertEqual(self.auto()["confirmed"], [])

    def test_scope_and_watched_amendments(self):
        spec = c5.SPECS["fr"]
        bill = {"direction": "against", "why": "Droit a l'aide a mourir."}
        base = {"status": "draft", "drafted": c5.DRAFTED_BY + ", 2026-10-10", "areas": [2],
                "watched": "DLR5L17N51670", "result": "Pour 300, Contre 200"}
        amend = dict(base, key="an-17-3", vote_kind="amendment",
                     title="l'amendement n° 3 de M. Sitzenstuhl de suppression de l'article premier.")
        wl = {"DLR5L17N51670": {"areas": [2], "amendments": ["n° 3"]}}
        # Watched, but without a direction of its own: still a person's call.
        got = [c for c, _ in c5.auto_check("fr", "an-17-3", amend, {"DLR5L17N51670": bill}, wl)]
        self.assertIn("kind", got)
        # With its own direction, values as the rules give them: passes.
        own = {"direction": "with", "why": "Strikes article 1 (the right to assisted dying)."}
        bills = {"DLR5L17N51670": bill, "an-17-3": own}
        amend.update(c5.rule_values(spec, "final", "an-17-3", own, c5._area_line(amend)))
        self.assertEqual(c5.auto_check("fr", "an-17-3", amend, bills, wl), [])
        # Not watched: since 12 October 2026 France has no scope, so it passes too.
        self.assertEqual(c5.auto_check("fr", "an-17-3", amend, bills, {"DLR5L17N51670": {}}), [])
        # The scope machinery, put back for this check only, still fails it.
        orig, spec.scope = spec.scope, c5.final_or_watched()
        try:
            got = [c for c, _ in c5.auto_check("fr", "an-17-3", amend, bills, {"DLR5L17N51670": {}})]
        finally:
            spec.scope = orig
        self.assertIn("scope", got)


class AmendTests(AutoBase):
    def test_amended_entries_are_never_touched(self):
        self.auto()
        c5.amend("pl", "pl-10-1-1", "Christopher", -1, 1, "The club split was about the timing.",
                 on="2026-10-19", config_dir=self.cfg, log=QUIET)
        e = self.entries()["pl-10-1-1"]
        self.assertEqual((e["yea"], e["nay"], e["status"], e["confirmed_by"], e["amended_by"],
                          e["amended_on"]), (-1, 1, "confirmed", "Christopher", "Christopher",
                                             "2026-10-19"))
        self.assertNotIn("auto_checks", e)
        self.assertIn("timing", e["why_yea"])
        before = self.text()
        c5.resync_directions("pl", self.cfg, log=QUIET)
        self.auto()
        self.assertEqual(self.text(), before)

    def test_an_amended_draft_is_never_auto_confirmed(self):
        c5.amend("pl", "pl-10-1-4", "Christopher", take_out=True, why="Wrong bill.",
                 on="2026-10-19", config_dir=self.cfg, log=QUIET)
        e = self.entries()["pl-10-1-4"]
        self.assertEqual((e["draft"], e["status"], e["amended_why"]), (True, "draft", "Wrong bill."))
        self.assertEqual(r5.status(e), "draft")
        self.assertIn("drafted", self.failed("pl-10-1-4"))
        self.assertEqual(self.auto()["confirmed"], ["pl-10-1-1"])
        self.assertEqual(self.entries()["pl-10-1-4"]["status"], "draft")
        self.assertEqual(c5.counts("pl", self.cfg)["out"], 1)

    def test_a_taken_out_confirmed_reading_places_nobody(self):
        self.auto()
        c5.amend("pl", "pl-10-1-1", "Christopher", take_out=True, why="Not our ground.",
                 config_dir=self.cfg, log=QUIET)
        self.assertEqual(r5.status(self.entries()["pl-10-1-1"]), "draft")

    def test_amend_needs_a_signer_a_reason_and_a_stance(self):
        with self.assertRaises(SystemExit):
            c5.amend("pl", "pl-10-1-1", "Somebody Else", -1, 1, "x", config_dir=self.cfg, log=QUIET)
        with self.assertRaises(SystemExit):
            c5.amend("pl", "pl-10-1-1", "Christopher", -1, 1, "", config_dir=self.cfg, log=QUIET)
        with self.assertRaises(SystemExit):
            c5.amend("pl", "pl-10-1-1", "Christopher", -3, 1, "x", config_dir=self.cfg, log=QUIET)
        with self.assertRaises(SystemExit):
            c5.amend("pl", "nope", "Christopher", -1, 1, "x", config_dir=self.cfg, log=QUIET)

    def test_amend_a_needs_reading_entry(self):
        c5.amend("pl", "pl-10-1-2", "Christopher", 1, -1, "Amendments 1 and 4 restore the ban.",
                 config_dir=self.cfg, log=QUIET)
        e = self.entries()["pl-10-1-2"]
        self.assertEqual((e["status"], e["yea"], r5.status(e)), ("confirmed", 1, "confirmed"))
        self.assertNotIn("read_first", e)


class ResyncTests(AutoBase):
    def test_a_changed_direction_redrafts_untouched_drafts_only(self):
        self.edit_entry("pl-10-1-4", "yea: 2", "yea: 1")              # a person's edit
        self.write(self.text().replace("    direction: against\n", "    direction: with\n", 1))
        self.assertEqual(c5.resync_directions("pl", self.cfg, log=QUIET), ["pl-10-1-1"])
        e = self.entries()
        self.assertEqual((e["pl-10-1-1"]["yea"], e["pl-10-1-1"]["nay"]), (2, -2))
        self.assertEqual(e["pl-10-1-4"]["yea"], 1)
        self.assertEqual(self.failed("pl-10-1-1"), [])

    def test_a_direction_on_hold_takes_the_values_away(self):
        self.write(self.text().replace("    direction: against\n", "    direction: hold\n"
                                       '    read_first: "Read it first."\n', 1))
        self.assertEqual(sorted(c5.resync_directions("pl", self.cfg, log=QUIET)),
                         ["pl-10-1-1", "pl-10-1-4"])
        e = self.entries()["pl-10-1-1"]
        self.assertEqual((e["status"], e.get("yea")), ("needs_reading", None))
        self.assertIn("on hold: read it first", e["read_first"])
        self.assertEqual(c5.confirm("pl", ["pl-10-1-1"], "Christopher", config_dir=self.cfg,
                                    log=QUIET), [])


class ReportTests(AutoBase):
    def test_the_guide_and_the_digest_say_what_was_left_and_why(self):
        self.edit_entry("pl-10-1-1", "yea: -2", "yea: -1")
        self.auto()
        c5.write_signoff_doc("pl", self.cfg, self.docs, QUIET)
        with open(c5.doc_path("pl", self.docs), encoding="utf-8") as h:
            doc = h.read()
        self.assertIn("**Auto-check:** left for a person: values differ from the rules", doc)
        self.assertIn("1 confirmed (1 automatically)", doc)
        self.assertIn("--amend KEY", doc)
        text = c5.digest_text(TODAY, self.cfg, self.docs, countries=("pl",))
        self.assertIn("1 confirmed automatically this week", text)
        self.assertIn("Auto-confirmed this week: 1. Still needs a person:", text)
        self.assertIn("1 values differ from the rules", text)

    def test_the_cli_dry_run_and_amend(self):
        orig = c5.CONFIG
        c5.CONFIG = self.cfg
        try:
            before = self.text()
            self.assertEqual(tool.main(["--cc", "pl", "--auto-confirm", "--dry-run"]), 0)
            self.assertEqual(self.text(), before)
            tool.main(["--cc", "pl", "--amend", "pl-10-1-1", "--yea", "-1", "--nay", "1",
                       "--by", "Christopher", "--why", "Too strong."])
            self.assertEqual(self.entries()["pl-10-1-1"]["amended_why"], "Too strong.")
        finally:
            c5.CONFIG = orig


if __name__ == "__main__":
    unittest.main()
