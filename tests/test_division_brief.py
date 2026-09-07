"""The same-day division brief (Christopher, 2026-09-07: "Build the division brief")."""

import datetime
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest.divisions import Division, Voter  # noqa: E402

spec = importlib.util.spec_from_file_location("division_brief", os.path.join(ROOT, "tools", "division_brief.py"))
brief = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brief)


def V(mid, name, party, vote, seat="Seat"):
    return Voter(member_id=mid, name=name, party=party, seat=seat, vote=vote)


def D(div_id=9001, title="Terminally Ill Adults (End of Life) Bill: Second Reading", ayes=3, noes=2):
    return Division(id=div_id, house="Commons", number=12, title=title,
                    date=datetime.date(2026, 9, 11), aye_count=ayes, no_count=noes)


VOTERS = [V(4858, "Danny Kruger", "Conservative", "no", "East Wiltshire"),
          V(4923, "Kim Leadbeater", "Labour", "aye", "Spen Valley"),
          V(5298, "Lauren Edwards", "Labour (Co-op)", "aye", "Rochester"),
          V(7, "A Liberal", "Liberal Democrat", "aye"),
          V(8, "B Tory", "Conservative", "no")]


class TallyTests(unittest.TestCase):
    def test_party_splits_merge_coop_and_order_by_size(self):
        splits = brief.party_splits(VOTERS)
        self.assertEqual(splits[0], ("Conservative", 0, 2))
        self.assertEqual(splits[1], ("Labour", 2, 0))
        self.assertNotIn("Labour (Co-op)", [p for p, _, _ in splits])

    def test_anchors_report_lobbies_not_verdicts(self):
        rows = dict(brief.anchor_lobbies("Terminally Ill Adults (End of Life) Bill: Second Reading", VOTERS))
        self.assertEqual(rows, {"Danny Kruger": "no", "Kim Leadbeater": "aye", "Lauren Edwards": "aye"})
        self.assertEqual(brief.anchor_lobbies("Crime and Policing Bill: New Clause 1", VOTERS), [])

    def test_an_absent_anchor_is_said_to_be_absent(self):
        rows = dict(brief.anchor_lobbies("Terminally Ill Adults", VOTERS[:2]))
        self.assertEqual(rows["Lauren Edwards"], "did not vote")

    def test_lobby_changes_name_the_switchers_only(self):
        previous = [V(4858, "Danny Kruger", "Conservative", "no"),
                    V(7, "A Liberal", "Liberal Democrat", "no"),      # now aye
                    V(99, "Gone Member", "Labour", "aye")]           # absent today
        changes = brief.lobby_changes(VOTERS, previous)
        self.assertEqual([(c[0], c[3], c[4]) for c in changes], [("A Liberal", "no", "aye")])

    def test_a_member_in_both_lobbies_abstained_and_is_not_a_switcher(self):
        """THE BUG THIS CAUGHT. Wendy Chamberlain was recorded Aye and No on
        the 2025 Third Reading (a deliberate abstention); comparing the
        division with itself reported her as changing lobby."""
        voters = VOTERS + [V(55, "Both Ways", "Liberal Democrat", "aye"), V(55, "Both Ways", "Liberal Democrat", "no")]
        self.assertEqual([v.name for v in brief.both_lobbies(voters)], ["Both Ways"])
        self.assertEqual(brief.lobby_changes(voters, voters), [])


class BriefTests(unittest.TestCase):
    def test_the_brief_carries_result_party_table_anchors_and_lists(self):
        md = brief.brief_markdown(D(), VOTERS, generated="now")
        self.assertIn("**Result: Ayes 3, Noes 2 — passed by 1.**", md)
        self.assertIn("| Conservative | 0 | 2 | 2 |", md)
        self.assertIn("- Danny Kruger: **No**", md)
        self.assertIn("## Ayes (3)", md)
        self.assertIn("**Labour** (2): Kim Leadbeater (Spen Valley); Lauren Edwards (Rochester)", md)
        self.assertIn("https://votes.parliament.uk/Votes/Commons/Division/9001", md)
        self.assertIn("prep_division.py --date 2026-09-11 --our-side aye|no --division 9001", md)

    def test_the_brief_names_no_vote_good_or_bad(self):
        """Meaning is signed by a human through prep_division; this is the record."""
        md = brief.brief_markdown(D(), VOTERS, generated="now")
        for word in ("GOOD", "BAD", "our side", "Verdict:"):
            self.assertNotIn(word, md)

    def test_lobby_changes_render_when_a_comparison_exists(self):
        previous = [V(7, "A Liberal", "Liberal Democrat", "no")]
        md = brief.brief_markdown(D(), VOTERS, previous, "the 2025 Third Reading", generated="now")
        self.assertIn("## Changed lobby since the 2025 Third Reading", md)
        self.assertIn("| A Liberal | Liberal Democrat | Seat | No | Aye |", md)
        self.assertIn("4 of today's voters had no vote in the comparison division", md)

    def test_the_dm_is_short_and_links_the_brief(self):
        text = brief.dm_text(D(), VOTERS, "https://github.com/x/brief.md")
        self.assertIn("Ayes 3, Noes 2 — passed by 1.", text)
        self.assertIn("By party: Conservative 0–2; Labour 2–0; Liberal Democrat 1–0.", text)
        self.assertIn("Anchors: Danny Kruger No; Kim Leadbeater Aye; Lauren Edwards Aye.", text)
        self.assertIn("https://github.com/x/brief.md", text)
        self.assertIn("No meaning is attached", text)


class FakeClient:
    """Answers the two list URLs and one detail URL; counts detail fetches."""

    def __init__(self, divisions, voters):
        self.divisions, self.voters, self.detail_calls = divisions, voters, 0

    def get_json(self, url, feed, slug):
        if "commonsvotes" in url and "search" in url:
            return [{"DivisionId": d.id, "Number": d.number, "Title": d.title,
                     "Date": d.date.isoformat() + "T00:00:00", "AyeCount": d.aye_count,
                     "NoCount": d.no_count} for d in self.divisions]
        if "lordsvotes" in url:
            return []
        self.detail_calls += 1
        d = self.divisions[0]
        return {"DivisionId": d.id, "Number": d.number, "Title": d.title,
                "Date": d.date.isoformat() + "T00:00:00", "AyeCount": d.aye_count, "NoCount": d.no_count,
                "Ayes": [{"MemberId": v.member_id, "Name": v.name, "Party": v.party, "MemberFrom": v.seat}
                         for v in self.voters if v.vote == "aye"],
                "Noes": [{"MemberId": v.member_id, "Name": v.name, "Party": v.party, "MemberFrom": v.seat}
                         for v in self.voters if v.vote == "no"]}


class RunTests(unittest.TestCase):
    def test_a_division_on_our_ground_is_briefed_once(self):
        out = tempfile.mkdtemp()
        client = FakeClient([D()], VOTERS)
        sent = []
        logs = []
        from unittest import mock
        fake = lambda secrets, text, transport=None: sent.append(text) or {"ok": True, "message_ts": "1"}
        with mock.patch.object(brief.publish, "slack_dm", fake):
            brief.run("2026-09-11", out_dir=out, client=client, secrets={}, log=logs.append)
            self.assertTrue(os.path.exists(os.path.join(out, "division-c9001.md")))
            self.assertEqual(len(sent), 1)
            # second run the same afternoon: nothing rewritten, nothing resent
            brief.run("2026-09-11", out_dir=out, client=client, secrets={}, log=logs.append)
        self.assertEqual(len(sent), 1)
        self.assertEqual(client.detail_calls, 1)
        self.assertTrue(any("already briefed" in l for l in logs))

    def test_a_division_off_our_ground_is_ignored(self):
        out = tempfile.mkdtemp()
        client = FakeClient([D(title="Finance Bill: Clause 12")], VOTERS)
        logs = []
        brief.run("2026-09-11", out_dir=out, client=client, dm=False, log=logs.append)
        self.assertEqual(os.listdir(out), [])
        self.assertTrue(any("0 on our ground" in l for l in logs))


class OneMessageTests(unittest.TestCase):
    def test_several_divisions_make_one_dm(self):
        """The rehearsal on the six divisions of 20 June 2025 sent six DMs."""
        out = tempfile.mkdtemp()
        divs = [D(9001, "Terminally Ill Adults (End of Life) Bill: Second Reading"),
                D(9002, "Terminally Ill Adults (End of Life) Bill: Amendment 1")]
        client = FakeClient(divs, VOTERS)
        sent = []
        from unittest import mock
        with mock.patch.object(brief.publish, "slack_dm",
                               lambda s, text, transport=None: sent.append(text) or {"ok": True}):
            brief.run("2026-09-11", out_dir=out, client=client, secrets={}, log=lambda *_: None)
        self.assertEqual(len(sent), 1)
        self.assertIn("*2 divisions on our ground today.*", sent[0])
        self.assertEqual(sent[0].count("Ayes 3, Noes 2"), 2)


class WiringTests(unittest.TestCase):
    def test_the_watch_runs_on_sitting_days_and_holds_no_store(self):
        src = open(os.path.join(ROOT, ".github", "workflows", "division-watch.yml"), encoding="utf-8").read()
        self.assertIn("* * 5", src)                 # Fridays: Private Members' Bills
        self.assertIn("* * 1-4", src)
        self.assertIn("tools/division_brief.py", src)
        self.assertNotIn("db_state.py", src)        # touches no store, so no pull/push to get wrong

    def test_a_failure_is_reported(self):
        alert = open(os.path.join(ROOT, ".github", "workflows", "alert.yml"), encoding="utf-8").read()
        self.assertIn('"Division watch"', alert)


if __name__ == "__main__":
    unittest.main()
