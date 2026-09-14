"""Flagged debate days: the tasks read the file, not Hansard."""
import datetime
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import debatewatch as dw  # noqa: E402


class WatchTests(unittest.TestCase):
    def test_add_list_today_remove_round_trip(self):
        d = tempfile.mkdtemp(); path = os.path.join(d, "w.yaml")
        open(path, "w").write("# kept comment\nwatches: []\n")
        w = dw.load(path)
        w, new = dw.add(w, "2026-09-18", "Terminally Ill Adults", "Commons", 2, "Second Reading")
        self.assertTrue(new)
        w, new = dw.add(w, "2026-09-18", "terminally ill adults", "Commons", None, "again")   # same watch, case-insensitive
        self.assertFalse(new); self.assertEqual(len(w), 1); self.assertEqual(w[0]["area"], 2); self.assertEqual(w[0]["note"], "again")
        dw.save(w, path)
        text = open(path).read()
        self.assertTrue(text.startswith("# kept comment"))
        again = dw.load(path)
        self.assertEqual(dw.for_day(again, datetime.date(2026, 9, 18))[0]["term"], "Terminally Ill Adults")
        self.assertEqual(dw.for_day(again, "2026-09-19"), [])
        self.assertEqual(dw.line(again[0]), "WATCH: Commons | Terminally Ill Adults | area 2 | again")
        again, n = dw.remove(again, "2026-09-18", "TERMINALLY ILL ADULTS")
        self.assertEqual((n, again), (1, []))

    def test_a_bad_date_is_refused(self):
        with self.assertRaises(ValueError):
            dw.add([], "18 September", "x")

    def test_suggest_keeps_only_events_on_our_ground_from_today(self):
        from src import filter as filt
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

        class E(object):
            def __init__(self, date, house, desc):
                self.start_date, self.house, self.description, self.bill_name = date, house, desc, ""
        today = datetime.date(2026, 9, 14)
        events = [E(datetime.date(2026, 9, 16), "Commons", "Health Bill: remaining stages"),
                  E(datetime.date(2026, 9, 16), "Lords", "Roads: Potholes"),
                  E(datetime.date(2026, 9, 10), "Commons", "Terminally Ill Adults (End of Life) Bill")]     # past
        rows = dw.suggest(events, tax, wl, {"Health Bill": 3, "Terminally Ill Adults": 2}, today)
        self.assertEqual([(r[0], r[1], r[3]) for r in rows], [("2026-09-16", "Commons", [3])])


if __name__ == "__main__":
    unittest.main()
