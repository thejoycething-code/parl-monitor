"""Commons divisions before 9 March 2016, from Hansard.

Every fixture is the shape of a payload measured live on 28 September 2026:
the 2015 Assisted Dying (No. 2) Bill (Hansard 1591, 118-330), the four
Health and Social Care (Re-committed) Bill divisions of 7 September 2011
(2002-2005), and the 2013 Marriage (Same Sex Couples) Bill.
"""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, trackerledger as tl  # noqa: E402
from src.ingest import hansard_divisions as hd  # noqa: E402


def _member(mid, list_as, party="Labour", teller=False):
    return {"MemberId": mid, "ListAs": list_as, "Party": party,
            "MemberFrom": None, "IsTeller": teller}


DIVISION = {
    "Id": 1591, "ExternalId": "15091126001423", "Number": 69,
    "Date": "2015-09-11T14:07:00", "DebateSection": "Assisted Dying (No. 2)  Bill",
    "DebateSectionExtId": "15091126000003", "AyesCount": 2, "NoesCount": 2,
    "TextBeforeVote": "<em>The House having divided:</em>",
    "AyeMembers": [_member(2, "Hopkins, Kelvin"), _member(3, "Marris, Rob"),
                   _member(90, "Heidi Alexander", teller=True)],
    "NoeMembers": [_member(8, "May, rh Mrs Theresa", "Conservative"),
                   _member(9, "Walker, Mr Charles", "Conservative", teller=True),
                   _member(10, "Fox, Dr Liam", "Conservative")],
}


def _item(order, value, kind="Contribution", ext=None, who=None):
    return {"OrderInSection": order, "ItemType": kind, "Value": value,
            "ExternalId": ext, "AttributedTo": who}


# Two divisions in one debate, as on 7 September 2011: an amendment moved by
# a backbencher at the start, then a clerk-recorded amendment later, then an
# amendment agreed without a vote, then Third Reading.
DEBATE = {"Items": [
    _item(1, "I beg to move amendment 1, page 6, line 8, at end insert— counselling",
          who="Nadine Dorries (Mid Bedfordshire) (Con)"),
    _item(2, "Question put, That the amendment be made."),
    _item(3, "", kind="Division", ext="D1"),
    _item(4, "I beg to move government amendment 5.", who="The Minister of State (Paul Burstow)"),
    _item(5, "Amendment proposed: 1176, page 2, line 7, leave out subsection (2) and insert—"),
    _item(6, "‘(2) the duty in subsection (1)’.—(Owen Smith.)"),
    _item(7, "Question put, That the amendment be made."),
    _item(8, "", kind="Division", ext="D2"),
    _item(9, "Amendment made: 402, page 418, line 41, at end insert—(Mr Lansley.)"),
    _item(10, "I beg to move, That the Bill be now read the Third time. The national...",
          who="Mr Lansley"),
    _item(11, "", kind="Division", ext="D3"),
    _item(12, "claimed to move the closure. Question put forthwith, That the Question "
              "be now put. Question agreed to. Question put accordingly, That the "
              "Assisted Dying (No. 2) Bill be now read a Second time."),
    _item(13, "", kind="Division", ext="D4"),
]}


class ParseTests(unittest.TestCase):
    def test_voters_match_the_counts_with_tellers_left_out(self):
        """120 names were listed for 118 Ayes in 2015: the two tellers.
        A teller's lobby is the side they count for, not a vote."""
        division, voters = hd.parse(DIVISION, "That the Bill be now read a Second time.")
        self.assertEqual(sum(v.vote == "aye" for v in voters), 2)
        self.assertEqual(sum(v.vote == "no" for v in voters), 2)
        self.assertNotIn(90, [v.member_id for v in voters])
        self.assertNotIn(9, [v.member_id for v in voters])

    def test_the_division_carries_the_question_not_just_the_title(self):
        division, _v = hd.parse(DIVISION, "That the Bill be now read a Second time.")
        self.assertEqual(division.id, 1591)
        self.assertEqual(division.title,
                         "Assisted Dying (No. 2) Bill: That the Bill be now read a Second time.")
        self.assertEqual(division.notes, "Question put: That the Bill be now read a Second time.")
        self.assertEqual(division.date.isoformat(), "2015-09-11")

    def test_without_a_question_the_line_does_not_pass_for_the_bill(self):
        """Ten 2013 divisions all titled "Marriage (Same Sex Couples) Bill":
        three had no question found. "Voted Aye: <Bill>" alone would read
        as a vote for the Bill."""
        division, _v = hd.parse(dict(DIVISION, DebateSection="Marriage (Same Sex Couples) Bill"), None)
        self.assertIn("question not recorded", division.title)
        self.assertIn("not the Bill itself", division.title)

    def test_names_come_out_in_display_order(self):
        self.assertEqual(hd.display_name("May, rh Mrs Theresa"), "Theresa May")
        self.assertEqual(hd.display_name("Walker, Mr Charles"), "Charles Walker")
        self.assertEqual(hd.display_name("Fox, Dr Liam"), "Liam Fox")
        self.assertEqual(hd.display_name("Heidi Alexander"), "Heidi Alexander")


class ContextTests(unittest.TestCase):
    """What was decided, and by whom -- from the division's OWN stretch of
    debate, never borrowed from the division before it."""

    def test_a_backbench_amendment_moved_at_the_start(self):
        ctx = hd.context_in(DEBATE, "D1")
        self.assertEqual(ctx["question"], "That the amendment be made.")
        self.assertEqual(ctx["mover"], "Nadine Dorries (Mid Bedfordshire) (Con)")
        self.assertIn("amendment 1", ctx["proposed"])

    def test_the_clerks_attribution_beats_a_nearby_i_beg_to_move(self):
        """A minister's "I beg to move" sat in the same stretch as Owen
        Smith's amendment 1176 on 7 September 2011."""
        ctx = hd.context_in(DEBATE, "D2")
        self.assertIn("1176", ctx["proposed"])
        self.assertEqual(ctx["mover"], "Owen Smith")

    def test_an_amendment_made_without_a_vote_is_not_the_question(self):
        """'Amendment made: 402' was agreed before Third Reading; the
        division is on the Third Reading."""
        ctx = hd.context_in(DEBATE, "D3")
        self.assertEqual(ctx["question"], "That the Bill be now read the Third time.")
        self.assertNotIn("402", ctx["proposed"] or "")
        self.assertEqual(ctx["mover"], "Mr Lansley")

    def test_after_a_closure_the_substantive_question_is_the_one(self):
        ctx = hd.context_in(DEBATE, "D4")
        self.assertEqual(ctx["question"],
                         "That the Assisted Dying (No. 2) Bill be now read a Second time.")

    def test_the_latest_group_is_the_one_divided_on(self):
        """23 February 2015, Serious Crime Bill report stage: the
        Solicitor-General moved the first group, government clauses were
        added without a vote, and the 201-292 division was on Fiona Bruce's
        new clause, moved last and put from the Chair at the deadline."""
        debate = {"Items": [
            _item(1, "I beg to move, That the clause be read a Second time.",
                  who="The Solicitor-General (Mr Robert Buckland)"),
            _item(2, "New Clause 9"),
            _item(3, "Brought up, read the First and Second time, and added to the Bill."),
            _item(4, "I beg to move, That the clause be read a Second time.",
                  who="Fiona Bruce (Congleton) (Con)"),
            _item(5, "New clause 1, which I wish to be put to a vote, is supported by more than 100 MPs."),
            _item(6, "The Deputy Speaker put forthwith the Question already proposed from the "
                     "Chair (Standing Order No. 83E), That the clause be read a Second time."),
            _item(7, "", kind="Division", ext="SC1"),
            _item(8, "New Clause 2"),
            _item(9, "Official Secrets Act 1989 (additional defence)"),
            _item(10, "(b) provided only to an officer of such an investigation or inquiry.\u201d\u2014 (John Mann.)"),
            _item(11, "Brought up."),
            _item(12, "Question put, That the clause be added to the Bill."),
            _item(13, "", kind="Division", ext="SC2"),
        ]}
        first = hd.context_in(debate, "SC1")
        self.assertEqual(first["question"], "That the clause be read a Second time.")
        self.assertEqual(first["mover"], "Fiona Bruce (Congleton) (Con)")
        second = hd.context_in(debate, "SC2")
        self.assertEqual(second["question"], "That the clause be added to the Bill.")
        self.assertEqual(second["mover"], "John Mann")
        self.assertEqual(second["proposed"], "New Clause 2: Official Secrets Act 1989 (additional defence)")

    def test_a_question_ending_in_a_colon_and_dash(self):
        """20 May 2013, h2186: "Question put, That the clause be read a Second
        time:—", then the division list."""
        debate = {"Items": [
            _item(1, "New Clause 5"),
            _item(2, "Registrars: conscientious objection"),
            _item(3, "(2) Expressions used in this section have the same meaning.\u2019.\u2014 (Mr Burrowes.)"),
            _item(4, "Brought up, and read the First time."),
            _item(5, "Question put, That the clause be read a Second time:\u2014"),
            _item(6, "", kind="Division", ext="M1")]}
        ctx = hd.context_in(debate, "M1")
        self.assertEqual(ctx["question"], "That the clause be read a Second time.")
        self.assertEqual(ctx["mover"], "Mr Burrowes")
        self.assertEqual(ctx["proposed"], "New Clause 5: Registrars: conscientious objection")

    def test_a_motion_split_from_its_question_line(self):
        """5 February 2013: the clerk's "Motion made, and Question put
        forthwith (Standing Order No. 52(1)( a ))" and the money motion's
        text are two items."""
        debate = {"Items": [
            _item(1, "Motion made, and Question put forthwith (Standing Order No. 52(1)( a ))"),
            _item(2, "That, for the purposes of any Act resulting from the Marriage (Same Sex "
                     "Couples) Bill, it is expedient to authorise\u2014"),
            _item(3, "(2) the payment out of the Consolidated Fund.\u2014 (Mark Lancaster .)"),
            _item(4, "", kind="Division", ext="MM")]}
        ctx = hd.context_in(debate, "MM")
        self.assertTrue(ctx["question"].startswith("That, for the purposes of any Act"))
        self.assertTrue(ctx["question"].endswith("it is expedient to authorise."))

    def test_a_division_not_in_the_debate_says_nothing(self):
        self.assertEqual(hd.context_in(DEBATE, "nope"),
                         {"question": None, "proposed": None, "mover": None})


class WindowTests(unittest.TestCase):
    def test_hansard_is_never_asked_for_the_votes_api_era(self):
        """From 9 March 2016 the Votes API is the record; asking Hansard too
        would count a division twice under two ids."""
        asked = []

        class Client:
            def get_json(self, url, feed, slug, **kw):
                asked.append(url)
                return {"Results": [], "TotalResultCount": 0}

        hd.search(Client(), "Bill", "2016-01-01", "2026-01-01")
        self.assertIn("endDate=2016-03-08", asked[0])
        self.assertEqual(hd.search(Client(), "Bill", "2016-03-09", "2026-01-01"), [])

    def test_search_pages_to_the_total(self):
        pages = [{"Results": [{"Id": i} for i in range(3)], "TotalResultCount": 5},
                 {"Results": [{"Id": 3}, {"Id": 4}], "TotalResultCount": 5}]

        class Client:
            def get_json(self, url, feed, slug, **kw):
                return pages.pop(0)

        self.assertEqual(len(hd.search(Client(), "Bill", "2010-01-01", "2012-01-01", page=3)), 5)


class OwnIdSpaceTests(unittest.TestCase):
    """Hansard's 1591 is not the Votes API's 1591."""

    def test_the_ledger_prefix(self):
        self.assertEqual(tl.prefix_for("hansard"), "h")
        self.assertEqual(tl.division_key({"id": 1591, "source": "hansard"}), "hansard")
        self.assertEqual(tl.division_key({"id": 1591}), "commons")
        self.assertEqual(tl.division_key({"id": 1885, "house": "lords"}), "lords")

    def test_a_signed_off_hansard_entry_ledgers_under_div_h(self):
        conn = db.init_db(db.connect(":memory:"))
        cfg = {"issues": [{"id": "assisted-suicide-2015", "area": 2}],
               "divisions": [{"id": 1591, "source": "hansard", "hansard_ext": "15091126001423",
                              "issue": "assisted-suicide-2015", "signed_off": True,
                              "our_side": "no", "meaning_aye": "For the Bill.",
                              "meaning_no": "Against the Bill."}]}

        class Client:
            archive_dir = raw_dir = "/nonexistent"

            def get_json(self, url, feed, slug, **kw):
                if "/debates/division/" in url:
                    return DIVISION
                return {"Items": [_item(1, "I beg to move, That the Bill be now read a "
                                           "Second time.", who="Rob Marris"),
                                  _item(2, "", kind="Division", ext="15091126001423")]}

        report = tl.ensure(conn, Client(), cfg, log=lambda *a: None)
        self.assertEqual(report[0][3], 4)
        refs = {r[0] for r in conn.execute("SELECT ref FROM mp_events WHERE kind='vote'")}
        self.assertEqual(refs, {"div:h1591:aye", "div:h1591:no"})
        excerpt = conn.execute("SELECT excerpt FROM mp_events WHERE ref='div:h1591:no'").fetchone()[0]
        self.assertIn("read a Second time", excerpt)
        # the signed stance lands on the Hansard refs, not on div:c1591
        tl.apply_signed_stances(conn, cfg, log=lambda *a: None)
        got = dict(conn.execute("SELECT ref, stance FROM stance WHERE ref LIKE 'div:%1591%'"))
        self.assertEqual(got, {"div:h1591:aye": -2, "div:h1591:no": 2})

    def test_an_entry_without_its_external_id_is_a_gap_not_a_guess(self):
        conn = db.init_db(db.connect(":memory:"))
        cfg = {"issues": [{"id": "x", "area": 2}],
               "divisions": [{"id": 1591, "source": "hansard", "issue": "x"}]}

        class Client:
            def get_json(self, *a, **k):
                raise AssertionError("must not fetch without an external id")

        notes = []
        report = tl.ensure(conn, Client(), cfg, log=notes.append)
        self.assertTrue(str(report[0][3]).startswith("gap:"))


class TrackerPageTests(unittest.TestCase):
    def _module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "make_vote_tracker", os.path.join(ROOT, "tools", "make_vote_tracker.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_payload_keys_keep_the_id_spaces_apart(self):
        mvt = self._module()
        self.assertEqual(mvt.payload_key({"id": 1591, "source": "hansard"}), "h1591")
        self.assertEqual(mvt.payload_key({"id": 1591}), 1591)

    def test_the_page_shape_matches_the_votes_api(self):
        shaped = hd.to_votes_api_shape(DIVISION)
        self.assertEqual(shaped["AyeCount"], 2)
        self.assertEqual([m["Name"] for m in shaped["Noes"]], ["Theresa May", "Liam Fox"])
        self.assertEqual([m["Name"] for m in shaped["NoTellers"]], ["Charles Walker"])
        self.assertEqual(shaped["SectionExtId"], "15091126000003")


if __name__ == "__main__":
    unittest.main()
