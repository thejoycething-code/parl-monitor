"""OHCHR's alternative routes (13 October 2026).

www.ohchr.org put the HRC sessions page and the calls-for-input listing behind
a Cloudflare challenge. HRC sessions now come from the HRC's own portal
(hrcportal.ohchr.org, where hrcmeetings.ohchr.org redirects); the treaty body
master calendar is not fetched while tbinternet's robots.txt disallows it (the
request goes through src/robots_guard) and treaty body SESSIONS come from
Indico.UN instead; calls for input have no legitimate alternative yet and say
so. Fixtures only.
"""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import un_checks  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import un_calendar  # noqa: E402
from tests.robots_fakes import guarded  # noqa: E402
from tests.test_un_checks import Unreachable  # noqa: E402
from tests.un_fixtures import fixture_text, un_filter  # noqa: E402

import un_forward  # noqa: E402

PORTAL = fixture_text("hrcportal-sessions-all.html.gz")
INDICO = {un_calendar.TB_INDICO_ICS.format(c): fixture_text("indico-category-{0}.ics".format(c))
          for _t, c, _n in un_calendar.TB_INDICO_CATEGORIES}
DISALLOW_ALL = "User-agent: *\nDisallow: /\n"
CHALLENGE = "HTTP Error 403: Forbidden (cf-mitigated: challenge)"


class PortalParseTests(unittest.TestCase):
    def setUp(self):
        self.sessions = un_calendar.parse_hrcportal_sessions(PORTAL)

    def test_every_regular_session_listed(self):
        self.assertEqual([s.number for s in self.sessions], list(range(46, 64)))

    def test_the_63rd(self):
        s63 = self.sessions[-1]
        self.assertEqual((s63.starts, s63.ends),
                         (datetime.date(2026, 9, 7), datetime.date(2026, 10, 7)))
        self.assertEqual(s63.url, "https://hrcportal.ohchr.org/node/18091")
        self.assertEqual(s63.name, "63rd session of the Human Rights Council")

    def test_organisational_meetings_are_not_sessions(self):
        self.assertIn("Organizational meeting", PORTAL)
        self.assertEqual(len(self.sessions), 18)

    def test_a_session_across_new_year(self):
        html = ('<article class="node node--session x"><h2><a href="/node/9">64th regular '
                'session of the Human Rights Council</a></h2><div class="field_session_dates">'
                '<svg/> Date : 14 Dec – 10 Jan 2027</div></article>')
        (s,) = un_calendar.parse_hrcportal_sessions(html)
        self.assertEqual((s.starts, s.ends), (datetime.date(2026, 12, 14), datetime.date(2027, 1, 10)))

    def test_a_changed_page_parses_to_nothing(self):
        self.assertEqual(un_calendar.parse_hrcportal_sessions("<html>Just a moment...</html>"), [])


class Client(Unreachable):
    """hrcportal answers; www.ohchr.org is challenged; Indico.UN serves the
    treaty body exports; tbinternet's robots.txt says Disallow: /. Every
    request that is actually sent is recorded (robots.txt reads are served by
    tests/robots_fakes and recorded there)."""

    tb_robots = DISALLOW_ALL
    indico = INDICO

    def __init__(self):
        self.asked = []

    def get_text(self, url, feed, slug, *a, **k):
        self.asked.append(url)
        if url == un_calendar.HRC_PORTAL_SESSIONS:
            return PORTAL
        if url in self.indico:
            return self.indico[url]
        if "www.ohchr.org" in url:
            raise FetchError(url, feed, slug, 1, CHALLENGE)
        raise FetchError(url, feed, slug, 1, "HTTP Error 503")


def collect(client, robots=None):
    tax, wl = un_filter()
    tb_client, _serving = guarded(
        client, robots if robots is not None else {"tbinternet.ohchr.org": client.tb_robots},
        "uncal")
    return un_forward.collect(client, datetime.date(2026, 10, 13), 180, tax, wl,
                              walk=False, pga_client=client, log=lambda *a: None,
                              tb_client=tb_client)


class CheckLogWiringTests(unittest.TestCase):
    def test_hrc_sessions_read_ok_via_the_portal(self):
        client = Client()
        by = {c.source: c for c in collect(client).checks.checks}
        hrc = by["HRC sessions (OHCHR)"]
        self.assertEqual(hrc.status, un_checks.READ_OK)
        self.assertEqual(hrc.count, 18)
        self.assertEqual(hrc.newest_date, "2026-09-07")
        self.assertIn("via hrcportal.ohchr.org", hrc.detail)
        # The challenged page is the fallback only: not asked when the portal answers.
        self.assertNotIn(un_calendar.HRC_SESSIONS, client.asked)

    def test_portal_down_falls_back_and_names_both(self):
        class Down(Client):
            def get_text(self, url, feed, slug, *a, **k):
                if url == un_calendar.HRC_PORTAL_SESSIONS:
                    self.asked.append(url)
                    raise FetchError(url, feed, slug, 1, "HTTP Error 502")
                return Client.get_text(self, url, feed, slug, *a, **k)

        client = Down()
        hrc = {c.source: c for c in collect(client).checks.checks}["HRC sessions (OHCHR)"]
        self.assertEqual(hrc.status, un_checks.NOT_READ)
        self.assertIn(un_calendar.HRC_SESSIONS, client.asked)
        self.assertIn("hrcportal.ohchr.org: HTTP Error 502", hrc.detail)
        self.assertIn("www.ohchr.org: HTTP Error 403", hrc.detail)

    def test_treaty_bodies_read_ok_via_indico_deadlines_refused_by_robots(self):
        client = Client()
        got = collect(client)
        tb = {c.source: c for c in got.checks.checks}[un_forward.TB_SOURCE]
        self.assertEqual(tb.status, un_checks.READ_OK)
        self.assertEqual(tb.count, 12)
        self.assertIn("sessions via indico.un.org", tb.detail)
        self.assertIn("robots.txt disallows", tb.detail)
        # The master calendar was never requested: robots.txt refused it.
        self.assertNotIn(un_calendar.TB_CALENDAR, client.asked)
        sessions = [r for r in got.rows if r[1] == "SESSION" and r[2].startswith(
            ("CEDAW", "CRC", "CCPR"))]
        names = [r[2] for r in sessions]
        self.assertIn("CEDAW 93rd session", names)       # sitting now
        self.assertIn("CCPR 146th session", names)
        self.assertIn("CRC 102nd session", names)
        self.assertNotIn("CRC 101st session", names)     # ended 28 September
        ccpr = next(r for r in sessions if r[2] == "CCPR 146th session")
        self.assertEqual(ccpr[4], "committee")
        self.assertIn("reviews Austria, Cameroon, Jamaica, Rwanda", ccpr[3])
        self.assertEqual(ccpr[6], "session:ccpr:146")

    def test_treaty_bodies_fetched_when_robots_txt_allows(self):
        class Allowed(Client):
            tb_robots = "User-agent: *\nDisallow: /admin/\n"

        client = Allowed()
        collect(client)
        self.assertIn(un_calendar.TB_CALENDAR, client.asked)

    def test_indico_refused_by_robots_is_not_read_and_says_why(self):
        client = Client()
        got = collect(client, robots={"tbinternet.ohchr.org": DISALLOW_ALL,
                                      "indico.un.org": DISALLOW_ALL})
        tb = {c.source: c for c in got.checks.checks}[un_forward.TB_SOURCE]
        self.assertEqual(tb.status, un_checks.NOT_READ)
        self.assertIn("indico.un.org", tb.detail)
        self.assertIn("robots.txt disallows", tb.detail)
        self.assertFalse([u for u in client.asked if "indico.un.org" in u])

    def test_calls_for_input_say_no_alternative_was_found(self):
        calls = {c.source: c for c in collect(Client()).checks.checks}["OHCHR calls for input"]
        self.assertEqual(calls.status, un_checks.NOT_READ)
        self.assertIn("Cloudflare", calls.detail)
        self.assertIn("no unchallenged alternative", calls.detail)


class RobotsTests(unittest.TestCase):
    def test_a_missing_robots_txt_allows(self):
        class NoRobots(Unreachable):
            def get_text(self, url, feed, slug, *a, **k):
                raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")

        self.assertTrue(un_calendar.robots_allows(NoRobots(), "https://example.org/x"))

    def test_an_unreadable_robots_txt_raises(self):
        with self.assertRaises(FetchError):
            un_calendar.robots_allows(Unreachable(), "https://example.org/x")

    def test_hrcportal_robots_allows_the_sessions_page(self):
        robots = ("User-agent: *\nDisallow: /admin/\nDisallow: /search/\nDisallow: /user/login\n"
                  "Crawl-delay: 10\n\nUser-agent: Claude-SearchBot\nCrawl-delay: 30\n"
                  "Disallow: /admin/\n")

        class Portal(Unreachable):
            def get_text(self, url, feed, slug, *a, **k):
                return robots

        self.assertTrue(un_calendar.robots_allows(Portal(), un_calendar.HRC_PORTAL_SESSIONS))
        self.assertFalse(un_calendar.robots_allows(Portal(), un_calendar.HRC_PORTAL + "/admin/x"))


if __name__ == "__main__":
    unittest.main()
