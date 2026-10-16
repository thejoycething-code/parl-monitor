"""Draft symbols and titles from iGov (16 October 2026), the one check-log
row for the docs.un.org refusal, and check-log titles cut at a word.

Fixtures: iGov's documents-by-session JSON as its app loads it, fetched 16
October 2026 with the honest User-Agent (GA plenary and Third Committee for
session 81; the Third Committee for session 80, to see amendments)."""

import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import un_checks, un_signals  # noqa: E402
from src.http import RobotsRefused  # noqa: E402
from src.ingest import un_docs  # noqa: E402
from tests.un_fixtures import fixture_text, un_filter  # noqa: E402

import un_backtest  # noqa: E402
import un_forward  # noqa: E402

D = datetime.date


def payload(name):
    return json.loads(fixture_text(name))


class ParseTests(unittest.TestCase):
    def test_ga_plenary_drafts_with_titles(self):
        listed = un_docs.parse_igov_documents(payload("igov-docs-81-ga.json.gz"), 81,
                                              "A/{session}/L.")
        by = {l.symbol: l for l in listed}
        self.assertEqual([l.symbol for l in listed],
                         ["A/81/L.1/Rev.1", "A/81/L.2", "A/81/L.3", "A/81/L.4", "A/81/L.5",
                          "A/81/L.6"])
        self.assertEqual(by["A/81/L.3"].title, "United Nations Declaration on Sea-level Rise")
        self.assertTrue(by["A/81/L.4"].title.startswith(
            "Political declaration of the High-Level Meeting to mark the twenty-fifth"))
        self.assertEqual(by["A/81/L.4"].agenda_item, 68)
        self.assertEqual(by["A/81/L.4"].agenda_label, "68(b)")
        self.assertIn("embargo", by["A/81/L.5"].title)
        self.assertEqual(by["A/81/L.6"].title,
                         "Political declaration on pandemic prevention, preparedness and response")
        self.assertEqual(by["A/81/L.6"].kind, "Draft resolution")
        self.assertEqual(by["A/81/L.6"].body, "General Assembly")
        self.assertTrue(all(l.body == "General Assembly" for l in listed))

    def test_the_organisation_of_work_note_is_not_a_draft(self):
        listed = un_docs.parse_igov_documents(payload("igov-docs-81-c3.json.gz"), 81,
                                              "A/C.3/{session}/L.")
        self.assertEqual(listed, [], "only L.1 and L.1/Add.1 so far: neither is a draft")

    def test_third_committee_session_80_amendments_and_dates(self):
        listed = un_docs.parse_igov_documents(payload("igov-docs-80-c3.json.gz"), 80,
                                              "A/C.3/{session}/L.")
        by = {l.symbol: l for l in listed}
        self.assertEqual(len(listed), 27)
        self.assertNotIn("A/C.3/80/L.1", by)
        self.assertEqual(by["A/C.3/80/L.57"].title, "Amendment to A/C.3/80/L.3/Rev.1")
        self.assertEqual(by["A/C.3/80/L.19"].dated, D(2025, 10, 21))
        # 14/10/2024 is a year before session 80 opened: a placeholder, dropped.
        self.assertIsNone(by["A/C.3/80/L.15"].dated)
        self.assertTrue(all(l.body == "Third Committee" for l in listed))

    def test_dates_outside_the_session_are_dropped(self):
        self.assertIsNone(un_docs._igov_date("31/12/2025", 81))
        self.assertEqual(un_docs._igov_date("05/10/2026", 81), D(2026, 10, 5))
        self.assertIsNone(un_docs._igov_date("", 81))
        self.assertIsNone(un_docs._igov_date("31/02/2026", 81))


class FakeClient:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def get_json(self, url, feed, slug, **kw):
        self.asked.append(url)
        answer = self.answers.get(url.split("body=", 1)[1])
        if isinstance(answer, Exception):
            raise answer
        return answer


class FetchTests(unittest.TestCase):
    def test_one_request_a_body_and_failures_named(self):
        client = FakeClient({"GA": payload("igov-docs-81-ga.json.gz"),
                             "Third%20Committee": RuntimeError("HTTP 503")})
        listed, failures = un_docs.fetch_igov_drafts(client, 81)
        self.assertEqual(client.asked, [
            "https://igov.un.org/igov/api/meetings/getdocumentsbysession/81?body=GA",
            "https://igov.un.org/igov/api/meetings/getdocumentsbysession/81?body=Third%20Committee"])
        self.assertEqual(len(listed), 6)
        self.assertEqual(failures, ["Third Committee: HTTP 503"])

    def test_check_row(self):
        client = FakeClient({"GA": payload("igov-docs-81-ga.json.gz"),
                             "Third%20Committee": payload("igov-docs-81-c3.json.gz")})
        checks = un_checks.CheckLog()
        import src.robots_guard as rg
        real = rg.guard
        rg.guard = lambda c, feed, log=print, budget=None: c
        try:
            listed = un_forward.read_igov(client, checks, 81)
        finally:
            rg.guard = real
        self.assertEqual(len(listed), 6)
        row = checks.checks[0]
        self.assertEqual(row.source, un_forward.IGOV_SOURCE)
        self.assertEqual(row.status, un_checks.READ_OK)
        self.assertIn("GA plenary 6, Third Committee 0", row.detail)

    def test_unreadable_is_could_not_read(self):
        client = FakeClient({"GA": RuntimeError("HTTP 403"),
                             "Third%20Committee": RuntimeError("HTTP 403")})
        checks = un_checks.CheckLog()
        import src.robots_guard as rg
        real = rg.guard
        rg.guard = lambda c, feed, log=print, budget=None: c
        try:
            self.assertEqual(un_forward.read_igov(client, checks, 81), [])
        finally:
            rg.guard = real
        self.assertEqual(checks.checks[0].status, un_checks.NOT_READ)


class Refusing:
    def __init__(self):
        self.asked = []

    def get_bytes(self, url, feed, slug, **kw):
        self.asked.append(url)
        symbol = url.split("/en/", 1)[1].split("?", 1)[0]
        raise RobotsRefused(url, feed, slug,
                            "robots.txt disallows https://documents.un.org/api/symbol/access"
                            "?s={0}&l=en&t=pdf (redirected from https://docs.un.org/en/{0}"
                            "?direct=true); not fetched".format(symbol))


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tax, self.wl = un_filter()
        self.letters, self.plenaries, _c = un_backtest.load()
        self.igov = un_docs.parse_igov_documents(payload("igov-docs-81-ga.json.gz"), 81,
                                                 "A/{session}/L.")

    def run_collect(self):
        checks = un_checks.CheckLog()
        drafts, stored = un_forward.collect_drafts(
            Refusing(), checks, 81, {}, ["A/81/L.3", "A/81/L.4", "A/81/L.6"], self.tax, self.wl,
            walk=True, log=lambda *a, **k: None,
            mentions=list(self.letters) + list(self.plenaries), igov=self.igov)
        return checks, {d.symbol: d for d in drafts}, stored

    def test_every_listed_draft_has_its_title(self):
        _checks, by, stored = self.run_collect()
        self.assertEqual(stored, [])
        self.assertEqual(by["A/81/L.3"].title, "United Nations Declaration on Sea-level Rise")
        self.assertEqual(by["A/81/L.3"].named_by, "Journal agenda", "the 18th plenary named it")
        self.assertEqual(by["A/81/L.3"].title_from, "iGov")
        self.assertIn("embargo", by["A/81/L.5"].title)
        self.assertEqual(by["A/81/L.5"].named_by, "iGov listing", "named nowhere else")
        self.assertTrue(by["A/81/L.4"].title.startswith("Political declaration of the High-Level"))

    def test_a_named_draft_keeps_its_naming_and_takes_igovs_title(self):
        _checks, by, _s = self.run_collect()
        l6 = by["A/81/L.6"]
        self.assertEqual(l6.named_by, "PGA letter")
        self.assertEqual(l6.title_from, "iGov")
        self.assertEqual(l6.dated, D(2026, 10, 7))
        self.assertEqual(l6.title,
                         "Political declaration on pandemic prevention, preparedness and response")
        self.assertEqual(l6.areas, [7])

    def test_one_could_not_read_row(self):
        checks, _by, _s = self.run_collect()
        self.assertEqual(len(checks.unread()), 1)
        self.assertEqual(checks.unread()[0].source, "UN draft resolutions (docs.un.org)")


class ForwardLookTests(unittest.TestCase):
    def signal(self, due=None):
        d = un_signals.DraftInfo(symbol="A/C.3/81/L.20", title="Rights of the child",
                                 areas=[6], named_by="iGov listing")
        return un_signals.Signal(kind="DRAFT", id="draft:" + d.symbol, title=d.title,
                                 due=due, areas=[6], obj=d)

    def test_an_undated_listed_draft_on_our_ground_stays_in_the_list(self):
        today = D(2026, 10, 16)
        self.assertTrue(un_signals.in_forward_look(self.signal(), today, 180))
        self.assertFalse(un_signals.in_forward_look(self.signal(due=D(2026, 10, 12)), today, 180),
                         "taken already: out")

    def test_the_detail_says_where_the_title_came_from(self):
        tax, wl = un_filter()
        d = un_signals.DraftInfo(symbol="A/81/L.9", title="Rights of the child", areas=[6],
                                 named_by="iGov listing", agenda_item=67)
        sig = un_signals.build_signals([], [], [d], tax, wl)[0]
        self.assertEqual(sig.detail, "listed by iGov (title only, text not read), agenda item 67")


class ShortenTests(unittest.TestCase):
    def test_never_mid_word(self):
        title = ("Continuation of the President of the General Assembly Fellowship Programme "
                 "during the eighty-first session, and call for applications")
        log = un_checks.CheckLog()
        log.read("PGA letters (un.org/pga)", [1], newest=(title, D(2026, 10, 15)))
        newest = log.checks[0].newest
        self.assertTrue(newest.endswith("..."), newest)
        self.assertNotIn("durin.", newest)
        self.assertTrue(title.startswith(newest[:-3]))
        self.assertTrue(title[len(newest) - 3] == " ", "cut at a space")

    def test_short_text_untouched(self):
        self.assertEqual(un_checks.shorten("A/81/L.6 Political declaration", 90),
                         "A/81/L.6 Political declaration")


class DmTests(unittest.TestCase):
    def test_titles_from_igov_are_said(self):
        import post_un_calls
        tax, wl = un_filter()
        checks = un_checks.CheckLog()
        checks.read(un_forward.IGOV_SOURCE, [1, 2, 3, 4, 5, 6])
        checks.failed(un_forward.DOCS_SOURCE,
                      "robots.txt disallows (documents.un.org): docs.un.org redirects to "
                      "https://documents.un.org/api/symbol/access; texts not read: drafts")
        text = post_un_calls.build_message([], tax, wl, checks=checks)
        self.assertIn("Draft TEXTS could not be read (robots.txt disallows (documents.un.org)); "
                      "titles come from iGov's list (6 GA plenary and Third Committee drafts)",
                      text)
        self.assertIn("(2 sources, 1 could not be read)", text)
        self.assertNotIn("—", text)


if __name__ == "__main__":
    unittest.main()
