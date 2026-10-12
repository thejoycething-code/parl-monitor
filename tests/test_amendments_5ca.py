"""Amendment readings for the new countries (Chris, 12 October 2026: "score
all amendments and reverse France's decision"): src/country5ca.py
amendment_values / amendment_checks / fill_amendments / apply_amendments and
tools/country_5ca.py --apply-amendments. Small temporary stores and stance
files; no network."""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from tests.test_country_5ca import Base, QUIET, _load  # noqa: E402

tool = _load("country_5ca")
TODAY = "2026-10-12"
KEY = "pl-10-1-2"                  # "poprawka 1", 200 to 220, drafted needs_reading
SRC = "https://www.sejm.gov.pl/Sejm10.nsf/druk.xsp?nr=2594-A"


def decision(direction, key=KEY, **kw):
    d = {"cc": "pl", "key": key, "direction": direction, "why": "Strikes the registration clause.",
         "source": SRC, "flag": ""}
    d.update(kw)
    return d


class AmendBase(Base):
    def setUp(self):
        super().setUp()
        self.draft()
        self.path = c5.stance_path("pl", self.cfg)

    def apply(self, *decisions, dry_run=False):
        return c5.apply_amendments(list(decisions), self.cfg, TODAY, dry_run=dry_run, log=QUIET)

    def entry(self, key=KEY):
        return self.entries()[key]

    def checks(self, key=KEY):
        _, bills, _ = c5.load("pl", self.cfg)
        return [c for c, _ in c5.auto_check("pl", key, self.entry(key), bills)]

    def text(self):
        with open(self.path, encoding="utf-8") as h:
            return h.read()


class ValuesTests(unittest.TestCase):
    def test_adopting_with_or_against_and_inverted_questions(self):
        spec = c5.SPECS["pl"]
        w = c5.amendment_values(spec, "k", "with", "Protects parents.", "Area 9.")
        self.assertEqual((w["yea"], w["nay"]), (2, -2))
        self.assertIn("for adopting it, with CitizenGO", w["why_yea"])
        self.assertIn("for rejecting it, against CitizenGO", w["why_nay"])
        a = c5.amendment_values(spec, "k", "against", "Widens access.", "Area 2.")
        self.assertEqual((a["yea"], a["nay"]), (-2, 2))
        # A Yes that keeps the text (rejects the amendment): the sides swap.
        inv = c5.amendment_values(spec, "k", "with", "Protects parents.", "Area 9.", yes_adopts=False)
        self.assertEqual((inv["yea"], inv["nay"]), (-2, 2))
        self.assertIn("for rejecting it", inv["why_yea"])
        self.assertIn("rejects", inv["reasoning"])


class ApplyTests(AmendBase):
    def test_with_drafts_the_values_and_passes_every_check(self):
        got = self.apply(decision("with"))
        self.assertEqual(got, {"applied": [("pl", KEY, "with")], "refused": []})
        e = self.entry()
        self.assertEqual((e["status"], e["yea"], e["nay"], e["amendment_direction"], e["amendment_source"]),
                         ("draft", 2, -2, "with", SRC))
        self.assertNotIn("read_first", e)
        self.assertNotIn("amendment_flag", e)
        self.assertEqual(self.checks(), [])
        conf = c5.auto_confirm("pl", self.cfg, TODAY, log=QUIET)
        self.assertIn(KEY, conf["confirmed"])
        self.assertEqual(self.entry()["confirmed_by"], c5.AUTO_BY)
        # Confirmed: a later decision is refused (a signer amends instead).
        again = self.apply(decision("against"))
        self.assertEqual(again["refused"][0][:2], ("pl", KEY))
        self.assertIn("already confirmed", again["refused"][0][2])

    def test_against_and_yes_not_adopting(self):
        self.apply(decision("against"))
        self.assertEqual((self.entry()["yea"], self.entry()["nay"]), (-2, 2))
        self.apply(decision("against", yes_adopts=False))
        e = self.entry()
        self.assertEqual((e["yea"], e["nay"], e["amendment_yes_adopts"]), (2, -2, False))
        self.assertEqual(self.checks(), [])
        self.apply(decision("against"))                      # back to a Yes that adopts
        self.assertNotIn("amendment_yes_adopts", self.entry())

    def test_a_flag_blocks_the_automatic_sign_off(self):
        self.apply(decision("with", flag="The text read was the committee's, check the plenary one."))
        e = self.entry()
        self.assertEqual((e["status"], e["yea"]), ("draft", 2))
        self.assertIn("direction", self.checks())
        self.assertEqual(c5.auto_confirm("pl", self.cfg, TODAY, log=QUIET)["confirmed"],
                         ["pl-10-1-1", "pl-10-1-4"])
        doc = c5.signoff_markdown("pl", self.cfg)
        self.assertIn("**Amendment flag:** The text read was the committee's", doc)
        self.assertIn("**Amendment reading:** adopting it is with CitizenGO", doc)

    def test_unclear_stays_needs_reading_with_the_flag_shown(self):
        self.apply(decision("unclear", flag="Two versions of poprawka 1; which was voted?"))
        e = self.entry()
        self.assertEqual(e["status"], "needs_reading")
        self.assertIsNone(e.get("yea"))
        self.assertIn("read_first", e)
        self.assertEqual(e["amendment_flag"], "Two versions of poprawka 1; which was voted?")
        _, bills, _ = c5.load("pl", self.cfg)
        fails = c5.auto_check("pl", KEY, e, bills)
        self.assertEqual(fails[0][0], "reading")
        self.assertIn("side unclear: Two versions", fails[0][1])
        self.assertIn("**Read, side unclear:** Two versions", c5.signoff_markdown("pl", self.cfg))
        self.assertIsNotNone(c5.hand_edited(e))              # never pruned as untouched

    def test_with_then_unclear_takes_the_values_away(self):
        self.apply(decision("with"))
        self.apply(decision("unclear", flag=""))
        e = self.entry()
        self.assertEqual(e["status"], "needs_reading")
        for k in ("yea", "nay", "why_yea", "why_nay", "amendment_direction"):
            self.assertNotIn(k, e)
        self.assertEqual(e["amendment_flag"], "Strikes the registration clause.")
        self.assertTrue(e["read_first"].startswith("An amendment, an article or one point"))

    def test_not_scored_strikes_it_with_the_reason(self):
        self.apply(decision("not_scored", why="A drafting fix: no stake.", source=""))
        e = self.entry()
        self.assertEqual((e["status"], e["placeable"]), ("draft", False))
        self.assertEqual(e["reason"], "Not scored (amendment reading, 2026-10-12): A drafting fix: no stake.")
        self.assertNotIn("read_first", e)
        self.assertIn("placeable", self.checks())
        self.assertEqual(c5.hand_edited(e), "has amendment_why")
        # A later reading may still score it.
        self.apply(decision("with"))
        e = self.entry()
        self.assertEqual((e["status"], e["yea"]), ("draft", 2))
        self.assertNotIn("placeable", e)
        self.assertNotIn("reason", e)

    def test_refusals(self):
        got = self.apply(
            decision("with", key="pl-10-1-9"),                     # no such entry
            decision("with", key="pl-10-1-1"),                     # a final vote, not an amendment
            decision("with", source=""),                           # no source
            decision("maybe"),                                     # not a decision
            decision("with", yes_adopts="no"),                     # not a boolean
            dict(decision("with"), cc="zz"),                       # no such country
            decision("not_scored", why=""))                        # no reason
        self.assertEqual(got["applied"], [])
        why = [r[2] for r in got["refused"]]
        self.assertEqual(len(why), 7)
        self.assertTrue(any("unknown country" in w for w in why))
        self.assertTrue(any("no such entry" in w for w in why))
        self.assertTrue(any("vote_kind is final" in w for w in why))
        self.assertTrue(any("needs both" in w for w in why))
        self.assertTrue(any("must be one of" in w for w in why))
        self.assertTrue(any("yes_adopts" in w for w in why))
        self.assertTrue(any("not_scored needs" in w for w in why))
        self.assertEqual(self.entry()["status"], "needs_reading")

    def test_values_a_person_wrote_are_never_replaced(self):
        text = self.text()
        start = text.index('- key: "{0}"'.format(KEY))
        text = text[:start] + text[start:].replace("status: needs_reading", "status: draft\n    yea: 1\n"
                                                   "    nay: -1", 1)
        with open(self.path, "w", encoding="utf-8") as h:
            h.write(text)
        got = self.apply(decision("against"))
        self.assertIn("values a person wrote", got["refused"][0][2])
        self.assertEqual(self.entry()["yea"], 1)

    def test_dry_run_writes_nothing(self):
        before = self.text()
        got = self.apply(decision("with"), dry_run=True)
        self.assertEqual(len(got["applied"]), 1)
        self.assertEqual(self.text(), before)

    def test_a_hand_edit_after_the_reading_fails_the_values_check(self):
        self.apply(decision("with"))
        text = self.text().replace("Strikes the registration clause.", "Strikes the clause.", 1)
        with open(self.path, "w", encoding="utf-8") as h:
            h.write(text)
        self.assertIn("values", self.checks())

    def test_an_article_vote_drafted_as_other_is_taken_as_an_amendment(self):
        text = self.text()
        start = text.index('- key: "{0}"'.format(KEY))
        end = text.index("\n\n", start)
        block = text[start:end].replace('vote_kind: "amendment"', 'vote_kind: "other"')
        block = block.replace('title: "poprawka 1"', 'title: "sur l\'article 4 de la proposition de loi"')
        with open(self.path, "w", encoding="utf-8") as h:
            h.write(text[:start] + block + text[end:])
        self.assertTrue(c5.is_amendment_entry(self.entry()))
        self.assertEqual(self.apply(decision("with"))["refused"], [])
        e = self.entry()
        self.assertEqual((e["vote_kind"], e["yea"]), ("amendment", 2))
        self.assertEqual(self.checks(), [])

    def test_other_entries_are_untouched(self):
        before = {k: v for k, v in self.entries().items() if k != KEY}
        self.apply(decision("with"))
        self.assertEqual({k: v for k, v in self.entries().items() if k != KEY}, before)


class FillTests(AmendBase):
    def _hand_direction(self, extra=""):
        text = self.text()
        start = text.index('- key: "{0}"'.format(KEY))
        text = text[:start] + text[start:].replace(
            "status: needs_reading", "status: needs_reading\n    amendment_direction: against\n"
            "    amendment_why: \"Widens the scheme.\"\n    amendment_source: \"{0}\"{1}".format(SRC, extra), 1)
        with open(self.path, "w", encoding="utf-8") as h:
            h.write(text)

    def test_a_direction_written_by_hand_is_drafted_by_the_fill(self):
        self._hand_direction()
        got = c5.fill_amendments("pl", self.cfg, log=QUIET)
        self.assertEqual(got, [KEY])
        e = self.entry()
        self.assertEqual((e["status"], e["yea"], e["nay"]), ("draft", -2, 2))
        self.assertNotIn("read_first", e)
        self.assertEqual(self.checks(), [])
        self.assertEqual(c5.fill_amendments("pl", self.cfg, log=QUIET), [])      # idempotent

    def test_values_written_by_hand_are_not_filled(self):
        self._hand_direction("\n    yea: 1")
        self.assertEqual(c5.fill_amendments("pl", self.cfg, log=QUIET), [])
        self.assertEqual(self.entry()["status"], "needs_reading")

    def test_dry_run(self):
        self._hand_direction()
        before = self.text()
        self.assertEqual(c5.fill_amendments("pl", self.cfg, dry_run=True, log=QUIET), [KEY])
        self.assertEqual(self.text(), before)


class ToolTests(AmendBase):
    def run_tool(self, *argv):
        orig = c5.CONFIG
        c5.CONFIG = self.cfg
        try:
            return tool.main(list(argv))
        finally:
            c5.CONFIG = orig

    def test_apply_amendments_from_a_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as h:
            json.dump({"decisions": [decision("with")]}, h)
        try:
            self.assertEqual(self.run_tool("--apply-amendments", h.name, "--dry-run"), 0)
            self.assertEqual(self.entry()["status"], "needs_reading")
            self.assertEqual(self.run_tool("--apply-amendments", h.name), 0)
            self.assertEqual(self.entry()["amendment_direction"], "with")
        finally:
            os.unlink(h.name)

    def test_a_refusal_exits_non_zero_and_a_bad_file_is_refused(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as h:
            json.dump([decision("with", key="nope")], h)
        try:
            self.assertEqual(self.run_tool("--apply-amendments", h.name), 1)
        finally:
            os.unlink(h.name)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as h:
            json.dump({"cc": "pl"}, h)
        try:
            with self.assertRaises(SystemExit):
                c5.read_decisions(h.name)
        finally:
            os.unlink(h.name)

    def test_fill_directions_flag_also_fills_amendments(self):
        FillTests._hand_direction(self)
        self.run_tool("--cc", "pl", "--fill-directions", "--db", os.path.join(self.tmp.name, "none.db"))
        self.assertEqual(self.entry()["status"], "draft")


class PruneTests(AmendBase):
    def test_a_read_amendment_is_never_pruned(self):
        self.apply(decision("with"))
        got = c5.prune_off_ground(self.conn, "pl", self.cfg, wl={}, log=QUIET)
        self.assertNotIn(KEY, got["removed"])
        self.assertIn(KEY, self.entries())


if __name__ == "__main__":
    unittest.main()
