"""The UN check log: read OK, read but empty, could not read (13 October 2026).

"Could not read" must never render as "nothing new". Before this, a source
that failed and a source with nothing new both ended as silence.
"""

import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import un_checks  # noqa: E402
from src.http import FetchError  # noqa: E402
from tests.un_fixtures import fixture_json, fixture_text, un_filter  # noqa: E402

import un_forward  # noqa: E402


class CheckLogTests(unittest.TestCase):
    def test_three_statuses(self):
        log = un_checks.CheckLog()
        log.read("A", [1, 2], newest=("item two", datetime.date(2026, 10, 7)))
        log.read("B", [])
        log.failed("C", "HTTP Error 403: Forbidden")
        self.assertEqual([c.status for c in log.checks],
                         [un_checks.READ_OK, un_checks.READ_EMPTY, un_checks.NOT_READ])
        lines = log.lines()
        self.assertIn("READ OK", lines[0])
        self.assertIn("newest 2026-10-07: item two", lines[0])
        self.assertIn("READ BUT EMPTY", lines[1])
        self.assertIn("COULD NOT READ", lines[2])
        self.assertIn("403", lines[2])

    def test_newest_is_picked_by_key(self):
        log = un_checks.CheckLog()
        log.read("letters", [("old", datetime.date(2026, 9, 1)), ("new", datetime.date(2026, 10, 9))],
                 key=lambda x: x[1], title=lambda x: x[0])
        self.assertEqual((log.checks[0].newest, log.checks[0].newest_date), ("new", "2026-10-09"))

    def test_nothing_new_refuses_while_a_source_is_unread(self):
        log = un_checks.CheckLog()
        log.read("A", [1])
        self.assertTrue(log.nothing_new().startswith("No changes"))
        log.failed("PGA letters", "challenge")
        said = log.nothing_new()
        self.assertNotIn("No changes", said)
        self.assertIn("NOT 'nothing new'", said)
        self.assertIn("PGA letters", said)

    def test_no_em_dashes(self):
        log = un_checks.CheckLog()
        log.read("A", [1], newest=("x", None))
        log.failed("B", "y")
        text = "\n".join(log.lines()) + log.nothing_new()
        self.assertNotIn("—", text)


class Unreachable:
    """Every request fails, as on a day the network is down."""

    def get_text(self, url, feed, slug, *a, **k):
        raise FetchError(url, feed, slug, 1, "HTTP Error 503")

    def get_bytes(self, url, feed, slug, *a, **k):
        raise FetchError(url, feed, slug, 1, "HTTP Error 503")

    def get_json(self, url, feed, slug, *a, **k):
        raise FetchError(url, feed, slug, 1, "HTTP Error 503")

    def post_json(self, url, body, feed, slug, *a, **k):
        raise FetchError(url, feed, slug, 1, "HTTP Error 503")

    def set_host_throttle(self, host, seconds):
        pass


def quiet_guard(client):
    """The robots-guarded client the treaty body sources use (13 October
    2026), with every robots.txt answering 404 (no rules), so what the test
    sees is the client's own answers, with no robots.txt read on the wire."""
    from tests.robots_fakes import guarded
    return guarded(client, {}, "uncal")[0]


class ForwardLookFailsLoudTests(unittest.TestCase):
    """Every UN source unreadable: every one says so, nothing says 'nothing new'."""

    def setUp(self):
        tax, wl = un_filter()
        self.today = datetime.date(2026, 10, 8)
        client = Unreachable()
        self.got = un_forward.collect(client, self.today, 180, tax, wl, conn=None,
                                      walk=True, pga_client=client, log=lambda *a: None,
                                      tb_client=quiet_guard(client))

    def test_every_source_is_could_not_read(self):
        statuses = {c.source: c.status for c in self.got.checks.checks}
        for source in ("HRC sessions (OHCHR)", "CSW sessions (UN Women)",
                       "UN Journal: Third Committee", "UN Journal: GA plenaries",
                       "PGA letters (un.org/pga)", "docs.un.org GA plenary drafts",
                       "docs.un.org Third Committee drafts", "UPR sessions (UPR Info)",
                       "GA session window (un.org)", un_forward.TB_SOURCE,
                       "OHCHR calls for input"):
            self.assertEqual(statuses.get(source), un_checks.NOT_READ, source)

    def test_the_render_never_says_nothing_new(self):
        text = "\n".join(un_forward.render(
            self.got.rows, self.today, 180, self.got.signals, self.got.checks, self.got.gaps,
            changes=[], stored=True, new_ids=set()))
        self.assertNotIn("No changes since the last run", text)
        self.assertIn("NOT 'nothing new'", text)
        self.assertIn("CHECK LOG (", text)
        self.assertIn("COULD NOT READ", text)
        self.assertNotIn("—", text)


class ReadButEmptyTests(unittest.TestCase):
    def test_a_journal_past_its_horizon_is_read_but_empty(self):
        """A 400 past the last Journal issue is the source answering 'none
        that far ahead': read, empty, with the reason, not a failure."""
        tax, wl = un_filter()

        class Client(Unreachable):
            def post_json(self, *a, **k):
                raise RuntimeError("HTTP 400: Incorrect parameters")

        got = un_forward.collect(Client(), datetime.date(2026, 10, 8), 180, tax, wl,
                                 walk=False, pga_client=Client(), log=lambda *a: None,
                                 tb_client=quiet_guard(Client()))
        statuses = {c.source: c for c in got.checks.checks}
        self.assertEqual(statuses["UN Journal: Third Committee"].status, un_checks.READ_EMPTY)
        self.assertIn("near-term", statuses["UN Journal: Third Committee"].detail)
        self.assertEqual(statuses["UN Journal: GA plenaries"].status, un_checks.READ_EMPTY)


class ReadOkTests(unittest.TestCase):
    def test_journal_and_letters_read_ok_with_newest(self):
        tax, wl = un_filter()
        payload = fixture_json("journal-ga-2026-10-01.json")
        detail = json.dumps(fixture_json("journal-meeting-18th-plenary.json"))
        listing = fixture_text("pga-letters-81.html.gz")

        class Client(Unreachable):
            def post_json(self, url, body, feed, slug, *a, **k):
                if "9615d07d" in body:
                    return payload
                return []

            def get_text(self, url, feed, slug, *a, **k):
                if "journal-api" in url:
                    return detail
                if url.endswith("/documents/letters/"):
                    return listing
                raise FetchError(url, feed, slug, 1, "HTTP Error 503")

        got = un_forward.collect(Client(), datetime.date(2026, 10, 13), 180, tax, wl,
                                 walk=False, pga_client=Client(), log=lambda *a: None,
                                 tb_client=quiet_guard(Client()))
        by = {c.source: c for c in got.checks.checks}
        self.assertEqual(by["UN Journal: GA plenaries"].status, un_checks.READ_OK)
        self.assertEqual(by["UN Journal: GA plenaries"].newest_date, "2026-10-13")
        self.assertEqual(by["UN Journal: Third Committee"].status, un_checks.READ_EMPTY)
        self.assertEqual(by["PGA letters (un.org/pga)"].status, un_checks.READ_OK)
        self.assertEqual(by["PGA letters (un.org/pga)"].newest_date, "2026-10-09")
        self.assertIn("letter page(s) not read", by["PGA letters (un.org/pga)"].detail)


if __name__ == "__main__":
    unittest.main()
