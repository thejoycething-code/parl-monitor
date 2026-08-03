"""Board state-machine tests against live-probed fixtures (Checkpoint 1).

Fixtures were captured live on 2026-08-01 into data/raw/2026-08-01/ and are the
frozen inputs here. Demonstrates the four board transitions the checkpoint asks
for: new bill and stage advance (4157), prorogation fall (3774), Royal Assent
(3938 Crime and Policing Act 2026, a real isAct fixture).
"""

import datetime
import gzip
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import board
from src.ingest import bills

RAW = os.path.join(ROOT, "data", "raw", "2026-08-01")
RUN_DATE = datetime.date(2026, 8, 1)


def _load(feed_slug):
    with gzip.open(os.path.join(RAW, feed_slug + ".json.gz"), "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def load_bill(bill_id):
    return bills.parse_bill(_load("bills_detail-%d" % bill_id), _load("bills_stages-%d" % bill_id))


class FixturePresenceTests(unittest.TestCase):
    def test_fixtures_exist(self):
        for bid in (4157, 3774, 3938, 3909):
            self.assertTrue(os.path.exists(os.path.join(RAW, "bills_detail-%d.json.gz" % bid)))
            self.assertTrue(os.path.exists(os.path.join(RAW, "bills_stages-%d.json.gz" % bid)))


class SessionTests(unittest.TestCase):
    def test_current_session_is_max_introduced(self):
        all_bills = [load_bill(b) for b in (4157, 3774, 3938, 3909)]
        # 4157 introduced in session 40; the others in 39 -> current is 40.
        self.assertEqual(board.current_session_id(all_bills), 40)


class Bill4157Tests(unittest.TestCase):
    """New bill + stage-advance transitions (acceptance 9.1)."""

    def setUp(self):
        self.bill = load_bill(4157)
        self.session = 40

    def test_next_key_date_is_2026_09_11(self):
        self.assertEqual(self.bill.next_key_date(RUN_DATE), datetime.date(2026, 9, 11))

    def test_new_bill_transition(self):
        row = board.build_row(self.bill, self.session, RUN_DATE, prior_snapshot=None)
        self.assertEqual(row.transition, board.NEW)
        self.assertEqual(row.movement, "NEW")
        self.assertEqual(row.status, "live")
        self.assertEqual(row.next_key_date, "2026-09-11")

    def test_stage_advance_transition(self):
        # Prior edition had the bill at 1st reading / 2026-06-17.
        prior = {"stage": "1st reading", "next_key_date": "2026-06-17", "status": "live"}
        row = board.build_row(self.bill, self.session, RUN_DATE, prior_snapshot=prior)
        self.assertEqual(row.transition, board.MOVED)
        self.assertEqual(row.movement, "▲ moved")

    def test_unchanged_transition(self):
        prior = {"stage": self.bill.current_stage, "next_key_date": "2026-09-11", "status": "live"}
        row = board.build_row(self.bill, self.session, RUN_DATE, prior_snapshot=prior)
        self.assertEqual(row.transition, board.UNCHANGED)
        self.assertEqual(row.movement, "no change")


class Bill3774FallTests(unittest.TestCase):
    """Prorogation fall (acceptance 9.2). The whole point: isDefeated is false."""

    def setUp(self):
        self.bill = load_bill(3774)
        self.session = 40

    def test_isdefeated_is_false_but_bill_has_fallen(self):
        self.assertFalse(self.bill.is_defeated)                 # the trap
        self.assertTrue(board.has_fallen(self.bill, self.session))

    def test_fourteen_lords_committee_sittings(self):
        sittings = self.bill.stage_sittings("Committee stage", house="Lords")
        self.assertEqual(len(sittings), 14)
        self.assertEqual(sittings[0], datetime.date(2025, 11, 14))
        self.assertEqual(sittings[-1], datetime.date(2026, 4, 24))

    def test_fallen_transition_closing_entry(self):
        row = board.build_row(self.bill, self.session, RUN_DATE, prior_snapshot=None)
        self.assertEqual(row.transition, board.FALLEN)
        self.assertEqual(row.status, "closed")
        self.assertIn("2026-04-24", row.closed_note)

    def test_a_live_bill_is_not_flagged_fallen(self):
        live = load_bill(4157)
        self.assertFalse(board.has_fallen(live, self.session))


class RoyalAssentTests(unittest.TestCase):
    """Royal Assent terminal transition (acceptance 9.2)."""

    def setUp(self):
        self.bill = load_bill(3938)  # Crime and Policing Act 2026
        self.session = 40

    def test_royal_assent_closing_entry_and_triggers(self):
        row = board.build_row(self.bill, self.session, RUN_DATE, prior_snapshot=None)
        self.assertEqual(row.transition, board.ROYAL_ASSENT)
        self.assertEqual(row.status, "closed")
        self.assertIn("acts_watch", row.triggers)
        self.assertIn("legislation_check", row.triggers)

    def test_royal_assent_date_from_feed(self):
        # DIVERGENCE (see docs/api-notes.md): live RA-stage date is 2026-04-29;
        # acceptance 9.2 expects 2026-05-11 for this Act. The board reads the
        # feed's RA-stage date; reconciliation via legislation.gov.uk is step 3.
        self.assertEqual(self.bill.royal_assent_date(), datetime.date(2026, 4, 29))


class GuardAndOrderingTests(unittest.TestCase):
    def test_closing_entry_renders_once(self):
        row = board.build_row(load_bill(3774), 40, RUN_DATE)
        self.assertTrue(board.should_render_closing(row, "closed", prior_closed_edition=None))
        self.assertFalse(board.should_render_closing(row, "closed", prior_closed_edition="2026-07-27"))

    def test_tba_when_no_future_sittings(self):
        past = bills.Bill(
            bill_id=9999, short_title="Past Bill", is_act=False, is_defeated=False,
            originating_house="Commons", current_house="Commons", current_stage="2nd reading",
            introduced_session_id=40, included_session_ids=[40], last_update="",
            sponsor_name="X", sponsor_party="Y",
            stages=[bills.Stage("2nd reading", "Commons", [datetime.date(2025, 1, 1)])],
        )
        row = board.build_row(past, 40, RUN_DATE)
        self.assertEqual(row.next_key_date, "TBA")

    def test_board_orders_tba_last(self):
        rows = [
            board.BoardRow(1, "b", "s", "Commons", "x", "TBA", "live", board.NEW),
            board.BoardRow(2, "a", "s", "Commons", "x", "2026-09-11", "live", board.NEW),
            board.BoardRow(3, "c", "s", "Commons", "x", "2026-11-27", "live", board.NEW),
        ]
        ordered = [r.bill_id for r in board.order_board(rows)]
        self.assertEqual(ordered, [2, 3, 1])


class DiscoveryClosureTests(unittest.TestCase):
    """Option B: cold-start closures discovered absolutely, fired once ever."""

    def setUp(self):
        # Candidate set as a cold first run would assemble it: the live TIA bill,
        # its fallen prior-session namesake, and the two Acts (Westminster only).
        self.candidates = [load_bill(b) for b in (4157, 3774, 3938, 3909)]
        self.session = board.current_session_id(self.candidates)  # 40

    def test_cold_start_surfaces_three_westminster_closures(self):
        rows = board.discover_closures(self.candidates, self.session, RUN_DATE, closed_bill_ids=set())
        closed_ids = sorted(r.bill_id for r in rows)
        # 3774 fell; 3938 + 3909 Royal Assent. 4157 is live -> not closed.
        self.assertEqual(closed_ids, [3774, 3909, 3938])
        by_id = {r.bill_id: r for r in rows}
        self.assertEqual(by_id[3774].transition, board.FALLEN)
        self.assertEqual(by_id[3938].transition, board.ROYAL_ASSENT)

    def test_already_closed_bills_are_not_re_emitted(self):
        rows = board.discover_closures(
            self.candidates, self.session, RUN_DATE, closed_bill_ids={3774, 3938, 3909}
        )
        self.assertEqual(rows, [])

    def test_discover_closures_respects_ids_loaded_from_db(self):
        # Regression: the orchestrator once passed a hardcoded empty set here, so
        # Westminster closures re-emitted every edition. The closed set must come
        # from bills_board (handoff 8: exactly one closing entry).
        from src import db

        conn = db.init_db(db.connect(":memory:"))
        try:
            first = board.discover_closures(self.candidates, self.session, RUN_DATE,
                                            board.load_closed_bill_ids(conn))
            self.assertEqual(len(first), 3)
            for row in first:
                board.record_closure(conn, row, edition="2026-07-06")
            second = board.discover_closures(self.candidates, self.session, RUN_DATE,
                                             board.load_closed_bill_ids(conn))
            self.assertEqual(second, [])
        finally:
            conn.close()

    def test_closure_persists_and_guards_across_editions(self):
        from src import db

        conn = db.init_db(db.connect(":memory:"))
        try:
            # Edition 1: cold board, nothing closed yet -> three closures.
            closed = board.load_closed_bill_ids(conn)
            first = board.discover_closures(self.candidates, self.session, RUN_DATE, closed)
            self.assertEqual(len(first), 3)
            for row in first:
                self.assertTrue(board.record_closure(conn, row, edition="2026-08-03"))

            # Re-render of the SAME edition: closures must still render.
            closed_same = board.load_closed_bill_ids(conn, exclude_edition="2026-08-03")
            self.assertEqual(closed_same, set())
            rerender = board.discover_closures(self.candidates, self.session, RUN_DATE, closed_same)
            self.assertEqual(len(rerender), 3)
            # Re-recording within the same edition is an idempotent success.
            self.assertTrue(board.record_closure(conn, first[0], edition="2026-08-03"))

            # A LATER edition: all guarded, zero closures, re-record refused.
            closed = board.load_closed_bill_ids(conn, exclude_edition="2026-08-10")
            self.assertEqual(closed, {3774, 3938, 3909})
            second = board.discover_closures(self.candidates, self.session, RUN_DATE, closed)
            self.assertEqual(second, [])
            self.assertFalse(board.record_closure(conn, first[0], edition="2026-08-10"))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
