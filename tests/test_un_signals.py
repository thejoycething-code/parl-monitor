"""First-sign alerts on our ground, and the UN DM that carries them
(13 October 2026)."""

import datetime
import os
import sqlite3
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, un_checks, un_signals, un_store  # noqa: E402
from tests.un_fixtures import un_filter  # noqa: E402

import post_un_calls  # noqa: E402
import un_backtest  # noqa: E402
import un_forward  # noqa: E402

D = datetime.date


class LinkingTests(unittest.TestCase):
    def setUp(self):
        self.tax, self.wl = un_filter()
        self.letters, self.plenaries, self.drafts = un_backtest.load()

    def signals(self, day):
        return un_signals.build_signals(self.letters, self.plenaries, self.drafts,
                                        self.tax, self.wl, as_of=day)

    def test_the_plenary_is_ours_through_the_draft_it_acts_on(self):
        p = [s for s in self.signals(D(2026, 10, 9)) if s.id.startswith("plenary:f0bd129c")][0]
        self.assertEqual(p.areas, [7])
        self.assertEqual(p.due, D(2026, 10, 12))
        self.assertIn("acts on A/81/L.6", p.detail)

    def test_a_plenary_not_on_our_ground_is_not_listed(self):
        ids = [s.id for s in self.signals(D(2026, 10, 9))]
        # The 13 October plenary (Human Rights Council elections, UN reform)
        # and the 1 October veto debate are not ours.
        self.assertFalse(any(i.startswith("plenary:ccc8f174") for i in ids))
        self.assertFalse(any(i.startswith("plenary:8eeacf10") for i in ids))

    def test_the_drafts_due_date_comes_from_the_plenary_or_the_letter(self):
        d = [s for s in self.signals(D(2026, 10, 7)) if s.id == "draft:A/81/L.6"][0]
        self.assertEqual(d.due, D(2026, 10, 12), "from the 7 October letter")

    def test_a_flagged_letter_off_our_ground_is_kept_unmarked(self):
        sea = [s for s in self.signals(D(2026, 10, 9)) if "sea-level-rise-declaration" in s.id][0]
        self.assertEqual(sea.areas, [])
        self.assertFalse(sea.ours)

    def test_as_of_hides_what_did_not_exist_yet(self):
        ids = [s.id for s in self.signals(D(2026, 10, 6))]
        self.assertNotIn("letter:letter-pandemic-prevention-declaration-7-october-2026", ids)
        self.assertIn("draft:A/81/L.6", ids)


class AlertTests(unittest.TestCase):
    def setUp(self):
        tax, wl = un_filter()
        letters, plenaries, drafts = un_backtest.load()
        self.day = D(2026, 10, 8)
        self.signals = un_signals.build_signals(letters, plenaries, drafts, tax, wl, as_of=self.day)

    def test_due_within_14_days(self):
        due = un_signals.due_soon(self.signals, self.day)
        self.assertTrue(due)
        self.assertTrue(all(s.ours and 0 <= (s.due - self.day).days <= 14 for s in due))

    def test_stateless_first_signs_are_the_last_seven_days(self):
        first = un_signals.first_signs(self.signals, self.day)
        kinds = {s.kind for s in first}
        self.assertEqual(kinds, {"DRAFT", "LETTER", "PLENARY"})

    def test_with_a_store_first_means_first_seen(self):
        first = un_signals.first_signs(self.signals, self.day, new_ids={"draft:A/81/L.6"})
        self.assertEqual([s.id for s in first], ["draft:A/81/L.6"])
        self.assertEqual(un_signals.first_signs(self.signals, self.day, new_ids=set()), [])

    def test_the_top_block_reads_plainly(self):
        lines = un_signals.render_top(un_signals.due_soon(self.signals, self.day),
                                      un_signals.first_signs(self.signals, self.day), self.day)
        text = "\n".join(lines)
        self.assertTrue(lines[0].startswith("ON OUR GROUND, DUE WITHIN 14 DAYS"))
        self.assertIn("FIRST SIGNS ON OUR GROUND", text)
        self.assertIn("Mon 12 Oct 2026  in 4d", text)
        self.assertNotIn("—", text)

    def test_signals_round_trip_through_the_store(self):
        """Second run: nothing new, so nothing is a first sign twice."""
        conn = db.init_db(db.connect(":memory:"))
        rows = []
        for s in self.signals:
            if un_signals.in_forward_look(s, self.day, 180):
                when = s.due if (s.due and s.due >= self.day) else (s.sign_date or self.day)
                rows.append((when, s.kind, s.title, s.detail,
                             ",".join(str(a) for a in s.areas), s.url, s.id, s))
        items = [un_forward.to_item(r) for r in rows]
        new_ids, _ = un_store.record(conn, items, today=self.day)
        self.assertIn("draft:A/81/L.6", new_ids)
        again, _ = un_store.record(conn, items, today=self.day)
        self.assertEqual(again, set())
        self.assertEqual(un_signals.first_signs(self.signals, self.day, new_ids=again), [])
        conn.close()


class DmTests(unittest.TestCase):
    def collected(self):
        tax, wl = un_filter()
        letters, plenaries, drafts = un_backtest.load()
        day = D(2026, 10, 8)
        signals = un_signals.build_signals(letters, plenaries, drafts, tax, wl, as_of=day)
        checks = un_checks.CheckLog()
        checks.read("PGA letters (un.org/pga)", letters, key=lambda l: l.dated,
                    title=lambda l: l.title)
        checks.failed("Treaty bodies (OHCHR)", "HTTP Error 503")
        return un_forward.Collected([], [], checks, signals, [], [])

    def test_the_dm_leads_with_first_signs_and_ends_with_the_check_log(self):
        tax, wl = un_filter()
        got = self.collected()
        day = D(2026, 10, 8)
        top = un_signals.render_top(un_signals.due_soon(got.signals, day),
                                    un_signals.first_signs(got.signals, day), day)
        text = post_un_calls.build_message([], tax, wl, top=top, checks=got.checks)
        self.assertLess(text.index("ON OUR GROUND"), text.index("*Calls for input*"))
        self.assertLess(text.index("*Calls for input*"), text.index("*Check log*"))
        self.assertIn("A/81/L.6", text)
        self.assertIn("COULD NOT READ", text)
        self.assertIn("NOT 'nothing new'", text)
        self.assertNotIn("—", text)

    def test_the_dm_goes_to_chris_alone(self):
        got = self.collected()
        sent = {}

        def fake_dm(secrets, text):
            sent["user"] = secrets.get("slack_dm_user_id")
            sent["channel"] = secrets.get("slack_channel_id")
            return {"channel": secrets["slack_dm_user_id"], "message_ts": "1"}

        with mock.patch.object(un_forward, "collect", return_value=got), \
                mock.patch.object(post_un_calls.publish, "load_secrets",
                                  return_value={"slack_dm_user_id": "USOMEONEELSE",
                                                "slack_channel_id": "C9RH217PZ"}), \
                mock.patch.object(post_un_calls.publish, "slack_dm", side_effect=fake_dm), \
                mock.patch.object(sys, "argv", ["post_un_calls.py"]):
            code = post_un_calls.main()
        self.assertEqual(sent["user"], "U05LJP0BT61")
        self.assertEqual(code, 1, "a source that could not be read makes the run fail loudly")


if __name__ == "__main__":
    unittest.main()
