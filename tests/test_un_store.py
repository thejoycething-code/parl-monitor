"""UN forward-calendar storage and change detection."""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, un_store

TODAY = datetime.date(2026, 8, 17)


def item(ident, starts, kind="call", title="A call", areas=None):
    return {"id": ident, "kind": kind, "title": title, "body": "OHCHR",
            "starts": starts, "ends": starts, "approximate": False,
            "areas": areas or [], "url": "https://example.test/" + ident}


class UnStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))

    def tearDown(self):
        self.conn.close()

    def test_first_run_is_all_new_second_run_is_none(self):
        items = [item("call:a", "2026-09-01"), item("call:b", "2026-09-10")]
        new, moved = un_store.record(self.conn, items, today=TODAY)
        self.assertEqual(len(new), 2)
        self.assertEqual(moved, [])
        new2, moved2 = un_store.record(self.conn, items,
                                       today=TODAY + datetime.timedelta(days=7))
        self.assertEqual(new2, set())
        self.assertEqual(moved2, [])

    def test_new_is_a_set_difference_not_a_date_test(self):
        """first_seen equals today for every row on the day a backfill runs,
        so testing first_seen would report the whole store as new -- which is
        exactly what happened to brief_log (2026-08-17)."""
        un_store.record(self.conn, [item("call:a", "2026-09-01")], today=TODAY)
        # Same day, second run, one extra item: only the extra is new.
        new, _ = un_store.record(
            self.conn, [item("call:a", "2026-09-01"), item("call:b", "2026-09-02")],
            today=TODAY)
        self.assertEqual(new, {"call:b"})

    def test_a_slipping_deadline_is_a_move_not_a_replacement(self):
        """Ids exclude the date on purpose."""
        un_store.record(self.conn, [item("call:a", "2026-09-01")], today=TODAY)
        new, moved = un_store.record(self.conn, [item("call:a", "2026-09-20")],
                                     today=TODAY)
        self.assertEqual(new, set())
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0][2:], ("2026-09-01", "2026-09-20"))

    def test_disappearance_is_only_claimed_inside_the_fetched_window(self):
        """A 2029 session is absent from a 180-day query because it was never
        asked for. Calling that a cancellation would fire every time the
        horizon shortened."""
        un_store.record(self.conn, [item("call:soon", "2026-09-01"),
                                    item("session:hrc:70", "2029-03-01", "session")],
                        today=TODAY)
        later = TODAY + datetime.timedelta(days=1)
        # A short-horizon run that sees neither item.
        gone = un_store.mark_gone(self.conn, TODAY + datetime.timedelta(days=30),
                                  today=later, seen_ids=set())
        ids = [g["id"] for g in gone]
        self.assertIn("call:soon", ids)
        self.assertNotIn("session:hrc:70", ids)

    def test_past_items_are_not_reported_as_disappeared(self):
        un_store.record(self.conn, [item("call:old", "2026-08-01")], today=TODAY)
        gone = un_store.mark_gone(self.conn, TODAY + datetime.timedelta(days=30),
                                  today=TODAY + datetime.timedelta(days=1),
                                  seen_ids=set())
        self.assertEqual(gone, [])

    def test_a_reappearing_item_clears_its_gone_flag(self):
        un_store.record(self.conn, [item("call:a", "2026-09-01")], today=TODAY)
        un_store.mark_gone(self.conn, TODAY + datetime.timedelta(days=30),
                           today=TODAY + datetime.timedelta(days=1), seen_ids=set())
        un_store.record(self.conn, [item("call:a", "2026-09-01")],
                        today=TODAY + datetime.timedelta(days=2))
        row = self.conn.execute("SELECT gone_at FROM un_calendar WHERE id='call:a'").fetchone()
        self.assertIsNone(row["gone_at"])

    def test_summarise_is_silent_when_nothing_changed(self):
        """A weekly message that always has content trains people not to read it."""
        un_store.record(self.conn, [item("call:a", "2026-09-01")], today=TODAY)
        self.assertEqual(un_store.summarise(self.conn, set(), [], []), [])

    def test_summarise_names_areas_when_present(self):
        new, _ = un_store.record(
            self.conn, [item("call:a", "2026-09-01", areas=[7, 8])], today=TODAY)
        text = "\n".join(un_store.summarise(self.conn, new, [], []))
        self.assertIn("areas 7,8", text)


if __name__ == "__main__":
    unittest.main()
