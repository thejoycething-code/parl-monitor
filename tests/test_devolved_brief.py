"""Same-day devolved vote briefs (Christopher, 2026-10-09).

Small real fixtures in tests/fixtures/devolved_watch, captured 9 October 2026:
Holyrood's votesmotion rows and motions-dump rows for two September
divisions, the Senedd's 16 September grooming gangs divisions, and the
Assembly's 28 September Conversion Practices Bill Second Stage. A fake client
serves them; a fake transport stands in for Slack, so nothing is ever sent.
"""

import datetime
import gzip
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FX = os.path.join(ROOT, "tests", "fixtures", "devolved_watch")

from src.http import FetchError  # noqa: E402

spec = importlib.util.spec_from_file_location("devolved_brief", os.path.join(ROOT, "tools", "devolved_brief.py"))
brief = importlib.util.module_from_spec(spec)
sys.modules["devolved_brief"] = brief
spec.loader.exec_module(brief)


def fx(name):
    with gzip.open(os.path.join(FX, name), "rt", encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    """Routes a URL to a fixture by substring; anything else is a FetchError,
    which is what an unpublished source looks like to the tool."""

    def __init__(self, routes):
        self.routes = routes
        self.asked = []

    def _find(self, url):
        self.asked.append(url)
        for part, body in self.routes:
            if part in url:
                return body
        raise FetchError(url, "test", "test", 1, "not published (test)")

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        body = self._find(url)
        return json.loads(body) if isinstance(body, str) else body

    def get_text(self, url, feed, slug, timeout=None, archive=True, fallback_encoding=None):
        return self._find(url)


class Transport:
    def __init__(self):
        self.sent = []

    def __call__(self, url, payload, headers):
        self.sent.append(payload)
        return {"ok": True, "ts": "1"}


SECRETS = {"slack_bot_token": "xoxb-test", "slack_dm_user_id": "USOMEONEELSE"}


def ni_routes():
    return [("GetVotesOnDivision_JSON", fx("ni_divisions.json.gz")),
            ("GetDivisionMemberVoting_JSON?documentId=496429", fx("ni_mv_496429.json.gz")),
            ("GetDivisionResult_JSON?documentId=496429", fx("ni_dr_496429.json.gz")),
            ("GetAllMembersByGivenDate_JSON", fx("ni_members_at_2026-09-28.json.gz"))]


def run(nations, routes, out, **kw):
    lines = []
    kw.setdefault("since", datetime.date(2026, 9, 14))
    kw.setdefault("until", datetime.date(2026, 9, 30))
    brief.run(nations, out_dir=out, client=FakeClient(routes), secrets=SECRETS,
              log=lines.append, now=datetime.datetime(2026, 9, 30, 20, 30), **kw)
    return lines


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.tx = Transport()
        self.lines = run(("ni",), ni_routes(), self.out, transport=self.tx)
        self.path = os.path.join(self.out, "ni-division-496429.md")

    def test_one_brief_one_dm_to_christopher_alone(self):
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual(len(self.tx.sent), 1)
        self.assertEqual(self.tx.sent[0]["channel"], "U05LJP0BT61")

    def test_the_brief_carries_result_tally_split_match_link_and_reading(self):
        text = open(self.path, encoding="utf-8").read()
        self.assertIn("**Result: The Motion Was Carried. Aye 46, No 29.**", text)
        self.assertIn("| Democratic Unionist Party | 0 | 22 | 0 | 0 |", text)
        self.assertIn("| Unionist | 1 | 29 | 0 |", text)
        self.assertIn("Conversion practices, from the division title", text)
        self.assertIn("Conversion Practices (Criminalisation) Bill (config/ni_watch.yaml)", text)
        self.assertIn("GetDivisionResult?documentId=496429", text)
        self.assertIn("Awaiting sign-off: no reading in config/ni_stance.yaml", text)
        self.assertIn("Hansard for the day was not yet published", text)
        self.assertIn("Divided at Monday 28 September 2026 21:40", text)

    def test_no_verdict_and_house_style(self):
        text = open(self.path, encoding="utf-8").read().lower()
        for word in ("good vote", "bad vote", "with us", "against us", "—"):
            self.assertNotIn(word, text)

    def test_speaks_once(self):
        tx = Transport()
        lines = run(("ni",), ni_routes(), self.out, transport=tx)
        self.assertEqual(tx.sent, [])
        self.assertIn("0 brief(s) written.", lines)

    def test_off_ground_divisions_wait_for_hansard(self):
        self.assertTrue(any("497923" in ln and "Hansard not published yet" in ln for ln in self.lines))
        self.assertFalse(os.path.exists(os.path.join(self.out, "ni-division-497923.md")))


class SeneddTests(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.tx = Transport()
        self._parties = brief.wales_parties
        brief.wales_parties = lambda client, log=print: (
            {"darren millar": "p1", "vikki howells": "p2"},
            {"p1": [("Welsh Conservative", "Clwyd", "2026-05-08", "9999")],
             "p2": [("Welsh Labour", "Cynon Valley", "2026-05-08", "9999")]})
        routes = [("XMLExport/?committee=", fx("senedd_index.html.gz")),
                  ("meetingID=16261&xmlDownloadType=Votes", fx("senedd_votes_16261.xml.gz"))]
        self.lines = run(("wales",), routes, self.out, transport=self.tx)

    def tearDown(self):
        brief.wales_parties = self._parties

    def test_briefs_both_divisions_in_one_dm(self):
        names = sorted(os.listdir(self.out))
        self.assertEqual(names, ["wales-division-769727.md", "wales-division-769733.md"])
        self.assertEqual(len(self.tx.sent), 1)
        self.assertIn("2 devolved divisions on our ground", self.tx.sent[0]["text"])

    def test_parties_from_the_roster_and_the_rest_named(self):
        text = open(os.path.join(self.out, "wales-division-769727.md"), encoding="utf-8").read()
        self.assertIn("| Welsh Conservative |", text)
        self.assertIn("Not in the roster, so shown without a party", text)
        self.assertIn("https://record.senedd.wales/Plenary/16261", text)
        self.assertIn("grooming gang", text)


class HolyroodTests(unittest.TestCase):
    def routes(self, dump=True):
        r = [("votesmotion?year=2026", fx("holyrood_votes_2026-09-24.json.gz"))]
        if dump:
            r.append(("Motionsquestionsanswersmotions", fx("holyrood_motions_rows.json.gz")))
        r.append(("votes-and-motions/S7M-01304", fx("holyrood_motion_S7M-01304.html.gz")))
        return r

    def test_an_amendment_is_classified_on_its_own_wording(self):
        """S7M-01304.4 is tier 1 on its own words ("freedom of expression");
        the motion it amends, S7M-01304, is tier 2 only and stays unbriefed --
        exactly the store's classification of the two."""
        out = tempfile.mkdtemp()
        lines = run(("scotland",), self.routes(), out, transport=Transport(),
                    since=datetime.date(2026, 9, 20), until=datetime.date(2026, 9, 26))
        self.assertEqual(os.listdir(out), ["scotland-division-m9374.md"])
        self.assertTrue(any("S7M-01304 " in ln and "tier-2 only" in ln for ln in lines))
        text = open(os.path.join(out, "scotland-division-m9374.md"), encoding="utf-8").read()
        self.assertIn("**Result: Defeated. Yes 40, No 65, abstained 7 (17 recorded no vote).**", text)
        self.assertIn("Free speech, privacy and civil liberties, from the amendment's own wording "
                      "(terms: freedom of expression)", text)
        self.assertIn("| Scottish National Party | 0 | 52 | 0 | 5 |", text)
        self.assertIn("votes-and-motions/S7M-01304)", text)

    def test_a_signed_reading_briefs_with_its_direction(self):
        """A reading in sp_stance.yaml puts a division on our ground whatever
        the taxonomy says, and the brief gives the SIGNED direction per lobby."""
        out = tempfile.mkdtemp()
        real = brief.stance_entries
        brief.stance_entries = lambda nation: {"S7M-01304.4": {
            "aye": 1, "why_aye": "Test reading.", "no": -1, "why_no": "Test reading."}}
        try:
            tx = Transport()
            run(("scotland",), self.routes(), out, transport=tx,
                since=datetime.date(2026, 9, 20), until=datetime.date(2026, 9, 26))
        finally:
            brief.stance_entries = real
        text = open(os.path.join(out, "scotland-division-m9374.md"), encoding="utf-8").read()
        self.assertIn("Yes: signed 5CA reading +1. Test reading.", text)
        self.assertIn("Published by the Parliament Thursday 24 September 2026 17:44", text)
        self.assertIn("From the amendment's own wording:", text)
        self.assertIn("5CA reading: signed (Yes +1; No -1).", tx.sent[0]["text"])

    def test_without_the_dump_the_base_motion_is_marked_as_such(self):
        out = tempfile.mkdtemp()
        real = brief.stance_entries
        brief.stance_entries = lambda nation: {"S7M-01304.4": {"draft": True}}
        try:
            run(("scotland",), self.routes(dump=False), out, transport=Transport(),
                since=datetime.date(2026, 9, 20), until=datetime.date(2026, 9, 26))
        finally:
            brief.stance_entries = real
        text = open(os.path.join(out, "scotland-division-m9374.md"), encoding="utf-8").read()
        self.assertIn("the base motion's text (S7M-01304); the amendment's own wording was "
                      "not available", text)
        self.assertIn("Awaiting sign-off: a draft reading in config/sp_stance.yaml", text)


class NationFailureTests(unittest.TestCase):
    def test_one_nation_failing_never_sinks_the_rest(self):
        out = tempfile.mkdtemp()
        real = brief.COLLECT["wales"]
        brief.COLLECT["wales"] = lambda *a, **k: 1 / 0
        try:
            lines = run(("wales", "ni"), ni_routes(), out, dm=False)
        finally:
            brief.COLLECT["wales"] = real
        self.assertTrue(any("Senedd: failed" in ln for ln in lines))
        self.assertTrue(os.path.exists(os.path.join(out, "ni-division-496429.md")))


if __name__ == "__main__":
    unittest.main()
