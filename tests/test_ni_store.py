"""Party-as-at-a-date resolution for the NI Assembly.

The bug this guards against is specific and was live: Doug Beattie tabled
questions as leader of the Ulster Unionist Party and now sits as an
Independent, so a join to the CURRENT roster filed those questions under
Independent. Fixtures use his real person id and real party history.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, ni_store
from src.ingest.niassembly import Member

BEATTIE = "5786"   # verified against the live roster 2026-08-19
OTHER = "5797"


def roster(party):
    return [Member(person_id=BEATTIE, name="Beattie, Doug MC",
                   display_name="Mr Doug Beattie MC", party=party,
                   constituency="Upper Bann")]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))

    def tearDown(self):
        self.conn.close()

    def test_store_and_read_back(self):
        ni_store.store_roster_at(self.conn, "2025-09-19",
                                 roster("Ulster Unionist Party"), "2026-08-18")
        self.assertEqual(ni_store.dates_present(self.conn), {"2025-09-19"})
        self.assertEqual(
            ni_store.affiliation_map(self.conn)[(BEATTIE, "2025-09-19")],
            ("Ulster Unionist Party", "Upper Bann"))

    def test_two_dates_hold_different_parties(self):
        """The whole point: one member, two dates, two parties."""
        ni_store.store_roster_at(self.conn, "2025-09-19",
                                 roster("Ulster Unionist Party"), "2026-08-18")
        ni_store.store_roster_at(self.conn, "2026-08-18",
                                 roster("Independent"), "2026-08-18")
        m = ni_store.affiliation_map(self.conn)
        self.assertEqual(m[(BEATTIE, "2025-09-19")][0], "Ulster Unionist Party")
        self.assertEqual(m[(BEATTIE, "2026-08-18")][0], "Independent")

    def test_restore_is_idempotent(self):
        for _ in range(2):
            ni_store.store_roster_at(self.conn, "2025-09-19",
                                     roster("Ulster Unionist Party"), "2026-08-18")
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM ni_affiliations").fetchone()[0], 1)


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        self.asked = []

    def tearDown(self):
        self.conn.close()

    def _fetch(self, _client, day):
        self.asked.append(day)
        return roster("Ulster Unionist Party"), None

    def test_fetches_each_date_once(self):
        fetched, gaps = ni_store.resolve_dates(
            self.conn, None, ["2025-09-19", "2026-02-26"], "2026-08-18",
            self._fetch)
        self.assertEqual((fetched, gaps), (2, []))
        self.assertEqual(sorted(self.asked), ["2025-09-19", "2026-02-26"])

    def test_second_run_fetches_nothing(self):
        """A re-run must not re-pay for dates already held."""
        ni_store.resolve_dates(self.conn, None, ["2025-09-19"], "2026-08-18",
                               self._fetch)
        self.asked.clear()
        fetched, _ = ni_store.resolve_dates(
            self.conn, None, ["2025-09-19"], "2026-08-18", self._fetch)
        self.assertEqual((fetched, self.asked), (0, []))

    def test_none_and_duplicate_dates_ignored(self):
        ni_store.resolve_dates(self.conn, None,
                               ["2025-09-19", "2025-09-19", None, ""],
                               "2026-08-18", self._fetch)
        self.assertEqual(self.asked, ["2025-09-19"])

    def test_one_failed_date_does_not_lose_the_others(self):
        def flaky(_client, day):
            if day == "2025-09-19":
                return [], "HTTPError: 500"
            return roster("Alliance Party"), None
        fetched, gaps = ni_store.resolve_dates(
            self.conn, None, ["2025-09-19", "2026-02-26"], "2026-08-18", flaky)
        self.assertEqual(fetched, 1)
        self.assertEqual(len(gaps), 1)
        self.assertIn("2025-09-19", gaps[0])
        self.assertIn("500", gaps[0])

    def test_empty_response_is_a_gap_not_a_stored_blank(self):
        fetched, gaps = ni_store.resolve_dates(
            self.conn, None, ["2025-09-19"], "2026-08-18",
            lambda _c, _d: ([], None))
        self.assertEqual(fetched, 0)
        self.assertIn("no members", gaps[0])
        self.assertEqual(ni_store.dates_present(self.conn), set())


class ResolveSittingsTests(unittest.TestCase):
    """Hansard archiving, so classification is free to re-run."""

    class _Sitting:
        def __init__(self, n=10, divs=2):
            self.components = list(range(n))
            self._divs = divs

        def anchors(self):
            return {str(i): i for i in range(self._divs)}

    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        self.asked = []

    def tearDown(self):
        self.conn.close()

    def _fetch(self, _client, day):
        self.asked.append(day)
        return self._Sitting(), None

    def test_records_component_and_division_counts(self):
        fetched, gaps = ni_store.resolve_sittings(
            self.conn, None, ["2026-06-30"], "2026-08-18", self._fetch)
        self.assertEqual((fetched, gaps), (1, []))
        row = self.conn.execute("SELECT * FROM ni_sittings").fetchone()
        self.assertEqual((row["components"], row["divisions"]), (10, 2))

    def test_second_run_fetches_nothing(self):
        ni_store.resolve_sittings(self.conn, None, ["2026-06-30"],
                                  "2026-08-18", self._fetch)
        self.asked.clear()
        fetched, _ = ni_store.resolve_sittings(
            self.conn, None, ["2026-06-30"], "2026-08-18", self._fetch)
        self.assertEqual((fetched, self.asked), (0, []))

    def test_one_failed_date_does_not_lose_the_others(self):
        def flaky(_c, day):
            return (None, "HTTPError: 500") if day == "a" else (self._Sitting(), None)
        fetched, gaps = ni_store.resolve_sittings(
            self.conn, None, ["a", "2026-06-30"], "2026-08-18", flaky)
        self.assertEqual(fetched, 1)
        self.assertIn("500", gaps[0])

    def test_empty_sitting_is_a_gap_not_a_stored_blank(self):
        fetched, gaps = ni_store.resolve_sittings(
            self.conn, None, ["2026-06-30"], "2026-08-18",
            lambda _c, _d: (self._Sitting(n=0), None))
        self.assertEqual(fetched, 0)
        self.assertIn("no components", gaps[0])
        self.assertEqual(ni_store.sittings_present(self.conn), set())


class PartyAtTests(unittest.TestCase):
    AS_AT = {(BEATTIE, "2025-09-19"): ("Ulster Unionist Party", "Upper Bann")}
    CURRENT = {BEATTIE: ("Independent", "Upper Bann"),
               OTHER: ("Ulster Unionist Party", "South Antrim")}

    def test_dated_party_beats_current(self):
        party, seat, source = ni_store.party_at(
            BEATTIE, "2025-09-19", self.AS_AT, self.CURRENT)
        self.assertEqual(party, "Ulster Unionist Party")
        self.assertEqual(seat, "Upper Bann")
        self.assertEqual(source, ni_store.AS_AT)

    def test_unresolved_date_falls_back_and_says_so(self):
        party, _seat, source = ni_store.party_at(
            BEATTIE, "2024-01-01", self.AS_AT, self.CURRENT)
        self.assertEqual(party, "Independent")
        self.assertEqual(source, ni_store.CURRENT,
                         "a fallback must be reported, never passed off as dated")

    def test_unknown_member(self):
        party, seat, source = ni_store.party_at(
            "99999", "2025-09-19", self.AS_AT, self.CURRENT)
        self.assertEqual((party, seat, source), ("", "", ni_store.UNKNOWN))

    def test_missing_date_falls_back(self):
        _p, _s, source = ni_store.party_at(
            BEATTIE, None, self.AS_AT, self.CURRENT)
        self.assertEqual(source, ni_store.CURRENT)


class LabelTests(unittest.TestCase):
    def test_dated_party_reads_plainly(self):
        self.assertEqual(
            ni_store.label("Ulster Unionist Party", ni_store.AS_AT),
            "Ulster Unionist Party")

    def test_fallback_is_marked(self):
        """An unmarked fallback is the original bug, so this is the assertion
        that matters most in this file."""
        self.assertEqual(ni_store.label("Independent", ni_store.CURRENT),
                         "Independent (party today)")

    def test_unknown_reads_as_unknown(self):
        self.assertEqual(ni_store.label("", ni_store.UNKNOWN), "party unknown")


class WiringTests(unittest.TestCase):
    """The resolver has to be called, not merely written."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _source(self, name):
        with open(os.path.join(self.ROOT, "tools", name), encoding="utf-8") as fh:
            return fh.read()

    def test_both_harvesters_resolve_dates(self):
        for name in ("ni_pull.py", "ni_divisions.py"):
            source = self._source(name)
            self.assertIn("ni_store.resolve_dates", source, name)
            self.assertIn("fetch_members_at", source, name)

    def test_the_division_harvester_archives_hansard(self):
        """Without this the classifier has nothing offline to read."""
        source = self._source("ni_divisions.py")
        self.assertIn("ni_store.resolve_sittings", source)
        self.assertIn("ni_hansard.fetch_sitting", source)

    def test_monitor_does_not_join_current_roster_for_party(self):
        """Joining ni_members for a party is exactly the bug. The monitor must
        go through party_at so the fallback is labelled."""
        source = self._source("ni_monitor.py")
        self.assertIn("ni_store.party_at", source)
        self.assertNotIn("JOIN ni_members", source)


if __name__ == "__main__":
    unittest.main()
