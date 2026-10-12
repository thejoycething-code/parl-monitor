"""The German vote page (tools/make_de_votes.py) and the weekly wiring of the
German 5CA (9 October 2026).

The rule the page shares with the 5CA sheet: which lobby is ours comes only
from a SIGNED reading in config/de_stance.yaml. A draft, unread or
unplaceable division ships with no ja/nein values at all, so the page cannot
colour it.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


votes = _load("make_de_votes")
NAMES = {1: "Abortion", 2: "Assisted dying", 9: "Marriage family", 11: "Migration"}


def _member(conn, pid, name, party, legislature="161", parliament="5", sitting=None):
    conn.execute("INSERT INTO de_members (person_id, name, party, parliament, legislature, "
                 "sitting, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?)",
                 (pid, name, party, parliament, legislature, sitting, "x", "x"))


def _division(conn, vid, areas, score=3, parliament="5", legislature="132", label=None):
    conn.execute("INSERT INTO de_divisions (vote_id, parliament, legislature, date, label, "
                 "yes, no, abstain, absent, accepted, areas, triage_score, first_seen, last_seen) "
                 "VALUES (?,?,?,?,?,1,1,0,0,1,?,?,'x','x')",
                 (vid, parliament, legislature, "2024-07-0" + vid[-1], label or "Div " + vid,
                  areas, score))


def _vote(conn, vid, pid, pos):
    conn.execute("INSERT INTO de_votes (vote_id, person_id, position) VALUES (?,?,?)",
                 (vid, pid, pos))


def _db():
    conn = db.init_db(db.connect(":memory:"))
    _member(conn, "s1", "Anna Beispiel", "SPD", sitting=1)
    _member(conn, "c1", "Carl Muster", "CDU/CSU", sitting=1)
    _member(conn, "gone", "Departed Member", "SPD", sitting=0)
    # Anna's mandate in the 20th Bundestag: a different person_id.
    _member(conn, "s1-old", "Anna Beispiel", "SPD", legislature="132")
    _member(conn, "c1-old", "Carl Muster", "CDU/CSU", legislature="132")
    _member(conn, "land", "Carl Muster", "CDU", legislature="99", parliament="13")
    _division(conn, "1", "[1]")                     # signed
    _division(conn, "2", "[2]")                     # draft
    _division(conn, "3", "[9]")                     # unplaceable
    _division(conn, "4", "[9]", score=2)            # unread, at the bar
    _division(conn, "5", "[9]", score=1)            # unread, below the bar
    _division(conn, "6", "[11]")                    # migration only
    _division(conn, "7", "[1]", parliament="13", legislature="99")  # a Landtag
    for vid in "1234567":
        _vote(conn, vid, "s1-old", "yes")
        _vote(conn, vid, "c1-old", "no")
        _vote(conn, vid, "gone", "abstain")
    _vote(conn, "7", "land", "no")
    return conn


STANCE = {"divisions": [
    {"key": "1", "area": 1, "title": "Buffer zones", "ja": -2, "nein": 2,
     "why_ja": "for buffer zones", "why_nein": "against buffer zones", "free_vote": True},
    {"key": "2", "area": 2, "draft": True, "ja": 2, "nein": -2,
     "why_ja": "draft ja", "why_nein": "draft nein"},
    {"key": "3", "area": 9, "placeable": False, "reason": "neither lobby is ours"},
    {"key": "7", "area": 1, "ja": -2, "nein": 2},
]}


class VotePageTests(unittest.TestCase):
    def setUp(self):
        self.data = votes.build_data(_db(), STANCE, NAMES)
        self.divs = {d["id"]: d for d in self.data["divisions"]}

    def test_no_roster_check_no_page(self):
        conn = db.init_db(db.connect(":memory:"))
        _member(conn, "x", "Someone", "SPD")
        self.assertIsNone(votes.build_data(conn, STANCE, NAMES))

    def test_bundestag_divisions_on_our_ground_only(self):
        # 5 is below the triage bar with no reading; 6 is migration; 7 is a Landtag.
        self.assertEqual(sorted(self.divs), ["1", "2", "3", "4"])

    def test_a_signed_reading_carries_its_direction(self):
        (r,) = self.divs["1"]["readings"]
        self.assertEqual((r["status"], r["ja"], r["nein"], r["free_vote"]),
                         ("confirmed", -2, 2, True))
        self.assertEqual(self.divs["1"]["title"], "Buffer zones")

    def test_a_draft_ships_no_direction_at_all(self):
        (r,) = self.divs["2"]["readings"]
        self.assertEqual(r["status"], "draft")
        for key in ("ja", "nein", "why_ja", "why_nein"):
            self.assertNotIn(key, r)
        self.assertNotIn("draft ja", votes.render(self.data))

    def test_unplaceable_and_unread_ship_no_direction(self):
        (r,) = self.divs["3"]["readings"]
        self.assertEqual(r, {"area": 9, "area_name": "Marriage family",
                             "status": "unplaceable", "reason": "neither lobby is ours"})
        self.assertEqual(self.divs["4"]["readings"], [])
        self.assertEqual(self.data["counts"],
                         {"signed": 1, "unplaceable": 1, "draft": 1, "unread": 1})

    def test_earlier_mandates_attach_to_sitting_members(self):
        self.assertEqual(self.data["votes"]["s1"]["1"], "J")
        self.assertEqual(self.data["votes"]["c1"]["1"], "N")
        self.assertNotIn("gone", self.data["votes"])
        self.assertEqual({m["id"] for m in self.data["members"]}, {"s1", "c1"})

    def test_the_fraktion_split_counts_everyone_who_sat(self):
        split = {s["p"]: s for s in self.divs["1"]["split"]}
        self.assertEqual((split["SPD"]["J"], split["SPD"]["E"]), (1, 1))
        self.assertEqual(split["CDU/CSU"]["N"], 1)

    def test_the_page_embeds_its_data_safely(self):
        data = dict(self.data, divisions=[dict(self.divs["1"], label="</script><b>")])
        page = votes.render(data)
        self.assertNotIn("/*__DATA__*/{}", page)
        self.assertNotIn("</script><b>", page)

    def test_the_real_config_builds_a_page_with_only_signed_directions(self):
        stance = votes.de_5ca.load_yaml(votes.de_5ca.STANCE_PATH)
        data = votes.build_data(_db(), stance, NAMES)
        for d in data["divisions"]:
            for r in d["readings"]:
                self.assertEqual("ja" in r, r["status"] == "confirmed", (d["id"], r))


class WeeklyWiringTests(unittest.TestCase):
    """Both callers of the Germany weekly build the sheets and the page, and a
    failure in either is a [gap], never a stop."""

    def _text(self, *parts):
        return open(os.path.join(ROOT, *parts), encoding="utf-8").read()

    def test_both_callers_build_and_commit(self):
        for text in (self._text("jobs", "de-weekly.sh"),
                     self._text(".github", "workflows", "de-weekly.yml")):
            for cmd in ("python3 tools/de_5ca.py --all", "python3 tools/make_de_votes.py"):
                i = text.index(cmd)
                self.assertIn("[gap]", text[i:i + 220], cmd)
            self.assertIn("partner_site/de-votes.html", text)

    def test_the_mini_runs_them_outside_the_stop_at_first_failure_block(self):
        script = self._text("jobs", "de-weekly.sh")
        self.assertGreater(script.index("tools/de_5ca.py"), script.index(") || rc=1"))
        self.assertLess(script.index("tools/de_5ca.py"), script.index("db_state.py --push"))

    def test_the_workflow_runs_them_whatever_the_collectors_did(self):
        import yaml
        doc = yaml.safe_load(self._text(".github", "workflows", "de-weekly.yml"))
        steps = doc["jobs"]["pull"]["steps"]
        for name in ("Build the 5CA sheets", "Build the vote page"):
            step = next(s for s in steps if s.get("name") == name)
            self.assertIn("always()", step["if"])
        names = [s.get("name") for s in steps]
        self.assertLess(names.index("Build the vote page"), names.index("Publish the store"))


if __name__ == "__main__":
    unittest.main()
