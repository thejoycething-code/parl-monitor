"""Treaty body sessions from Indico.UN (13 October 2026).

tbinternet.ohchr.org's robots.txt reads Disallow: /, so its master calendar
is not fetched. Indico.UN (UNOG's meeting registration system) files every
treaty body session under the committee's category, and its calendar export
(events.ics) is the route now. Fixtures: the three exports as served on
13 October 2026. No network.
"""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.http import FetchError  # noqa: E402
from src.ingest import un_calendar as uc  # noqa: E402
from src.robots_guard import RobotsRefused  # noqa: E402
from tests.robots_fakes import guarded  # noqa: E402
from tests.un_fixtures import fixture_text  # noqa: E402

CATEGORY = {t: c for t, c, _n in uc.TB_INDICO_CATEGORIES}
DISALLOW_ALL = "User-agent: *\nDisallow: /\n"


def export(treaty):
    return fixture_text("indico-category-{0}.ics".format(CATEGORY[treaty]))


class Indico:
    """Serves the three category exports; records every request sent."""

    def __init__(self, missing=()):
        self.asked = []
        self.missing = missing

    def get_text(self, url, feed, slug, *a, **k):
        self.asked.append(url)
        for treaty, category in CATEGORY.items():
            if url == uc.TB_INDICO_ICS.format(category) and treaty not in self.missing:
                return export(treaty)
        raise FetchError(url, feed, slug, 1, "HTTP Error 503")


class ParseTests(unittest.TestCase):
    def sessions(self, treaty):
        return uc.parse_indico_sessions(export(treaty), treaty)

    def test_cedaw_plenaries_only(self):
        got = self.sessions("CEDAW")
        self.assertEqual([s.number for s in got], [93, 94, 95, 96])
        s93 = got[0]
        self.assertEqual((s93.starts, s93.ends),
                         (datetime.date(2026, 10, 5), datetime.date(2026, 10, 30)))
        self.assertEqual(s93.url, "https://indico.un.org/event/1017962/")
        self.assertEqual(s93.name, "CEDAW 93rd session")
        self.assertTrue(s93.ours)

    def test_working_groups_sharing_a_number_are_dropped(self):
        """'96th session', 1-5 March 2027, is a pre-sessional group: one week.
        The plenary 96th is 4-22 October 2027."""
        s96 = [s for s in self.sessions("CEDAW") if s.number == 96]
        self.assertEqual(len(s96), 1)
        self.assertEqual(s96[0].starts, datetime.date(2027, 10, 4))
        self.assertIn("SUMMARY:96th session", export("CEDAW"))

    def test_cancelled_events_are_dropped(self):
        self.assertIn("CANCELLED - 95th session", export("CEDAW"))
        s95 = [s for s in self.sessions("CEDAW") if s.number == 95]
        self.assertEqual([s.starts for s in s95], [datetime.date(2027, 6, 16)])

    def test_crc(self):
        got = self.sessions("CRC")
        self.assertEqual([(s.number, s.starts) for s in got], [
            (101, datetime.date(2026, 8, 31)), (102, datetime.date(2027, 1, 11)),
            (103, datetime.date(2027, 5, 3)), (104, datetime.date(2027, 8, 30))])

    def test_ccpr_with_states_under_review(self):
        got = self.sessions("CCPR")
        self.assertEqual([s.number for s in got], [146, 147, 148, 149])
        s146 = got[0]
        self.assertEqual((s146.starts, s146.ends),
                         (datetime.date(2026, 10, 19), datetime.date(2026, 11, 6)))
        self.assertEqual(s146.states, ("Austria", "Cameroon", "Jamaica", "Rwanda"))
        self.assertEqual(got[1].states, ())

    def test_folded_lines_and_crlf(self):
        ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:CRC 110th se\r\n ssion\r\n"
               "DTSTART:20280110T090000Z\r\nDTEND:20280128T170000Z\r\n"
               "URL:https://indico.un.org/event/9/\r\nDESCRIPTION:Countries under review: "
               "Chile\\, Peru and Spain.\\nPlease register\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        (s,) = uc.parse_indico_sessions(ics, "CRC")
        self.assertEqual((s.number, s.starts), (110, datetime.date(2028, 1, 10)))
        self.assertEqual(s.states, ("Chile", "Peru", "Spain"))

    def test_a_changed_export_parses_to_nothing(self):
        self.assertEqual(uc.parse_indico_sessions("<html>Not found</html>", "CRC"), [])


class FetchTests(unittest.TestCase):
    def test_all_three_through_the_guard(self):
        indico = Indico()
        client, serving = guarded(indico, {}, "uncal")
        sessions, failures = uc.fetch_treaty_sessions(client)
        self.assertEqual(failures, [])
        self.assertEqual(len(sessions), 12)
        self.assertEqual(sessions, sorted(sessions, key=lambda s: s.starts))
        self.assertEqual(serving.robots_asked, ["indico.un.org"])   # read once per run
        self.assertEqual(len(indico.asked), 3)

    def test_robots_disallow_means_nothing_is_sent(self):
        indico = Indico()
        client, _ = guarded(indico, {"indico.un.org": DISALLOW_ALL}, "uncal")
        with self.assertRaises(FetchError) as ctx:
            uc.fetch_treaty_sessions(client)
        self.assertEqual(indico.asked, [])
        self.assertIn("robots.txt disallows", str(ctx.exception.cause))

    def test_one_committee_down_is_named_and_the_rest_kept(self):
        client, _ = guarded(Indico(missing=("CRC",)), {}, "uncal")
        sessions, failures = uc.fetch_treaty_sessions(client)
        self.assertEqual({s.treaty for s in sessions}, {"CEDAW", "CCPR"})
        self.assertEqual(len(failures), 1)
        self.assertIn("CRC", failures[0])

    def test_master_calendar_refused_by_robots(self):
        class Tb:
            asked = []

            def get_text(self, url, *a, **k):
                self.asked.append(url)
                return ""

        tb = Tb()
        client, _ = guarded(tb, {"tbinternet.ohchr.org": DISALLOW_ALL}, "uncal")
        with self.assertRaises(RobotsRefused) as ctx:
            uc.fetch_treaty_deadlines(client)
        self.assertEqual(tb.asked, [])
        self.assertIn("robots.txt disallows", str(ctx.exception))

    def test_upcoming_keeps_a_session_under_way(self):
        sessions, _ = uc.fetch_treaty_sessions(guarded(Indico(), {}, "uncal")[0])
        live = uc.upcoming(sessions, today=datetime.date(2026, 10, 13), horizon_days=120)
        self.assertEqual([s.name for s in live],
                         ["CEDAW 93rd session", "CCPR 146th session", "CRC 102nd session",
                          "CEDAW 94th session"])


if __name__ == "__main__":
    unittest.main()
