"""UN drafts after docs.un.org's redirect to a robots.txt-disallowed path
(13 October 2026): refused, reported as "could not read", and replaced by
the drafts that readable sources name."""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import un_checks, un_signals  # noqa: E402
from src.http import RobotsRefused  # noqa: E402
from src.ingest import un_calendar, un_docs  # noqa: E402
from tests.un_fixtures import fixture_json, un_filter  # noqa: E402

import un_backtest  # noqa: E402
import un_forward  # noqa: E402

D = datetime.date
REASON = ("robots.txt disallows https://documents.un.org/api/symbol/access?s={0}&l=en&t=pdf "
          "(redirected from https://docs.un.org/en/{0}?direct=true); not fetched")


class RefusingClient:
    """Every docs.un.org symbol refused the way the guarded client refuses
    it; counts the requests."""

    def __init__(self):
        self.asked = []

    def get_bytes(self, url, feed, slug, **kw):
        self.asked.append(url)
        symbol = url.split("/en/", 1)[1].split("?", 1)[0]
        raise RobotsRefused(url, feed, slug, REASON.format(symbol))


class WalkTests(unittest.TestCase):
    def test_the_walk_stops_at_the_first_refusal(self):
        client = RefusingClient()
        with self.assertRaises(RobotsRefused):
            un_docs.walk_drafts(client, un_docs.GA_PLENARY_DRAFTS, 81)
        self.assertEqual(len(client.asked), 1, "every symbol goes the same way: ask once")

    def test_the_note_names_the_refusing_host(self):
        exc = RobotsRefused("u", "undocs", "s", REASON.format("A/81/L.1"))
        self.assertEqual(un_docs.refusal_note(exc), "robots.txt disallows (documents.un.org)")
        self.assertEqual(un_docs.ROBOTS_NOTE, "robots.txt disallows (documents.un.org)")

    def test_a_real_client_is_guarded(self):
        from src.http import HttpClient
        from src.robots_guard import GuardedClient
        c = HttpClient(raw_dir="/nonexistent-never-written")
        g = un_docs._guarded(c)
        self.assertIsInstance(g, GuardedClient)
        self.assertIs(un_docs._guarded(c), g, "wrapped once per client")
        self.assertIs(un_docs._guarded(g), g)


class CheckLogTests(unittest.TestCase):
    def setUp(self):
        self.tax, self.wl = un_filter()
        self.letters, self.plenaries, _c = un_backtest.load()

    def run_collect(self, named):
        checks = un_checks.CheckLog()
        client = RefusingClient()
        drafts, stored = un_forward.collect_drafts(
            client, checks, 81, {}, named, self.tax, self.wl, walk=True,
            log=lambda *a, **k: None, mentions=list(self.letters) + list(self.plenaries))
        return checks, drafts, stored, client

    def test_one_docs_un_org_row_for_one_cause(self):
        # 16 October 2026: three rows (two walks, the named drafts) for one
        # robots.txt refusal were counted three times in "N of M sources
        # could not be read". Now one row, naming the unread symbols.
        checks, _d, stored, client = self.run_collect(["A/81/L.6", "A/81/L.3"])
        docs_rows = [c for c in checks.checks if "docs.un.org" in c.source]
        self.assertEqual([c.source for c in docs_rows], [un_forward.DOCS_SOURCE])
        row = docs_rows[0]
        self.assertEqual(row.status, un_checks.NOT_READ)
        self.assertTrue(row.detail.startswith("robots.txt disallows (documents.un.org)"), row.detail)
        self.assertIn("GA plenary and Third Committee walks", row.detail)
        self.assertIn("named drafts A/81/L.6, A/81/L.3", row.detail)
        self.assertEqual(len(checks.unread()), 1)
        self.assertEqual(len(client.asked), 1, "one refusal ends the run's docs.un.org reads")
        self.assertEqual(stored, [], "nothing unread is stored in un_documents")
        lines = "\n".join(checks.lines())
        self.assertRegex(lines, r"COULD NOT READ\s+robots.txt disallows \(documents.un.org\): "
                                r"docs.un.org redirects to https://documents.un.org/api/symbol/access")
        self.assertIn("NOT 'nothing new': 1 of", checks.nothing_new())

    def test_named_drafts_stand_in(self):
        checks, drafts, _s, _c = self.run_collect(["A/81/L.6"])
        by = {d.symbol: d for d in drafts}
        self.assertIn("A/81/L.6", by)
        self.assertEqual(by["A/81/L.6"].areas, [7])
        self.assertEqual(by["A/81/L.6"].named_by, "PGA letter")
        row = [c for c in checks.checks
               if c.source == "Drafts named by PGA letters and Journal agendas"][0]
        self.assertEqual(row.status, un_checks.READ_OK)
        self.assertIn("text is not read", row.detail)


class DmTests(unittest.TestCase):
    def test_the_dm_says_unknown_not_zero(self):
        import post_un_calls
        tax, wl = un_filter()
        checks = un_checks.CheckLog()
        checks.failed("docs.un.org GA plenary drafts",
                      "robots.txt disallows (documents.un.org): docs.un.org redirects to "
                      "https://documents.un.org/api/symbol/access")
        text = post_un_calls.build_message([], tax, wl, checks=checks)
        self.assertIn("COULD NOT READ docs.un.org this run (robots.txt disallows "
                      "(documents.un.org)), so new drafts are unknown, not zero", text)
        self.assertIn("NOT 'nothing new'", text)
        self.assertNotIn("\u2014", text)


class ConsultationTests(unittest.TestCase):
    def test_consultations_come_from_the_same_payload(self):
        cons = un_calendar.parse_ga_consultations(fixture_json("journal-ga-2026-10-01.json"))
        first = cons[0]
        self.assertTrue(first.draft_title.startswith("Extension of the preparatory period"))
        self.assertEqual(first.agenda_item, 9)
        self.assertEqual(first.convened_by, "Permanent Mission of Qatar")
        plen = un_calendar.parse_ga_plenaries(fixture_json("journal-ga-2026-10-01.json"))
        self.assertFalse({c.id for c in cons} & {m.id for m in plen})

    def test_a_consultation_on_our_ground_is_a_first_sign(self):
        tax, wl = un_filter()
        c = un_calendar.Consultation(
            title="Informal consultations on the draft resolution entitled “Political "
                  "declaration on pandemic prevention, preparedness and response”",
            draft_title="Political declaration on pandemic prevention, preparedness and response",
            starts=datetime.datetime(2026, 10, 9, 10, 0), id="abc", agenda_item=129)
        signals = un_signals.build_signals([], [], [], tax, wl, consultations=[c])
        self.assertEqual([s.kind for s in signals], ["CONSULT"])
        self.assertEqual(signals[0].areas, [7])
        first = un_signals.first_signs(signals, D(2026, 10, 7))
        self.assertEqual([s.id for s in first], ["consult:abc"])
        self.assertEqual(un_signals.first_signs(signals, D(2026, 10, 30)), [])

    def test_off_our_ground_is_not_a_signal(self):
        tax, wl = un_filter()
        cons = un_calendar.parse_ga_consultations(fixture_json("journal-ga-2026-10-01.json"))
        self.assertEqual(un_signals.build_signals([], [], [], tax, wl, consultations=cons), [])


class CommitteeAgendaTests(unittest.TestCase):
    def test_a_committee_agenda_names_and_dates_its_drafts(self):
        tax, wl = un_filter()
        m = un_calendar.Meeting(
            organ="Third Committee", title="30th plenary meeting",
            starts=datetime.datetime(2026, 11, 5, 10, 0), kind="Official", id="x",
            agenda="Promotion and protection of the rights of children - Item 66: Draft "
                   "resolution ( A/C.3/81/L.20 ) ; Action on the draft resolution",
            symbols=("A/C.3/81/L.20",))
        drafts = un_signals.drafts_named([], [m], tax, wl)
        self.assertEqual(drafts[0].symbol, "A/C.3/81/L.20")
        self.assertEqual(drafts[0].agenda_item, 66)
        self.assertEqual(drafts[0].title, "Promotion and protection of the rights of children")
        signals = un_signals.build_signals([], [], drafts, tax, wl, committee_meetings=[m])
        for s in signals:
            if s.id == "draft:A/C.3/81/L.20":
                self.assertEqual(s.due, D(2026, 11, 5))

    def test_only_numbered_meetings_in_the_window_are_read(self):
        class Client:
            asked = []

            def get_text(self, url, feed, slug, headers=None, **kw):
                self.asked.append(url)
                return '{"agenda": {"en": "X - Item 66: Draft resolution ( A/C.3/81/L.5 )"}}'
        mk = lambda t, d, i: un_calendar.Meeting(  # noqa: E731
            organ="Third Committee", title=t, starts=datetime.datetime(2026, 10, d, 10),
            kind="Official", id=i)
        ms = [mk("13th plenary meeting", 14, "a"), mk("Information on the schedule", 14, "b"),
              mk("14th plenary meeting", 30, "c")]
        read, failures = un_calendar.fetch_committee_drafts(Client(), ms, D(2026, 10, 13),
                                                            D(2026, 10, 27))
        self.assertEqual([m.id for m in read], ["a"])
        self.assertEqual(read[0].symbols, ("A/C.3/81/L.5",))
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
