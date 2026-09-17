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

    def test_suggest_names_a_bill_committee_sitting_from_the_committee(self):
        from src import filter as filt
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

        class E(object):
            def __init__(self, date, house, desc, committee=None, category="Debate"):
                self.start_date, self.house, self.description, self.bill_name = date, house, desc, ""
                self.committee, self.category = committee, category
        today = datetime.date(2026, 9, 17)
        # The Immigration and Asylum Bill's sittings, as the week-ahead gave them on 17 Sept 2026:
        # an empty description and the bill's name on the committee.
        events = [E(datetime.date(2026, 10, 13), "Commons", "", {"Description": "Immigration and Asylum Bill"}, "Debate")]
        rows = dw.suggest(events, tax, wl, {}, today)
        self.assertEqual([(r[0], r[2], r[3], r[5]) for r in rows], [("2026-10-13", "Immigration and Asylum Bill", [11], "Debate")])

    def test_auto_flag_takes_debates_and_leaves_statements(self):
        today = datetime.date(2026, 9, 17)
        rows = [("2026-09-21", "Commons", "Health Bill: remaining stages", [3], ["Health Bill"], "Legislation"),
                ("2026-09-21", "Commons", "Abortion services", [1], ["abortion"], "Ministerial statement"),
                ("2026-09-22", "Lords", "Roads: Potholes", [], [], "Debate"),
                ("2026-09-10", "Commons", "Old debate", [2], ["x"], "Debate")]           # past
        watches, new = dw.add([], "2026-09-21", "Health Bill", "Commons", 3, "Christopher's note")
        watches, written = dw.auto_flag(watches, rows, today)
        # the hand watch already covers the Health Bill row; the statement is not debate-shaped;
        # the pothole debate earns nothing but IS a debate, and auto_flag trusts suggest's gate
        self.assertEqual(written, [("2026-09-22", "Lords", "Roads: Potholes")])
        self.assertEqual(watches[0]["note"], "Christopher's note")            # a person's watch is untouched
        self.assertEqual(watches[1]["source"], "auto")
        self.assertTrue(watches[1]["note"].startswith("auto: Debate"))

    def test_bill_watches_take_future_sittings_with_a_committee_floor(self):
        detail = {"billId": 4254, "shortTitle": "Immigration and Asylum Bill"}
        stages = {"items": [
            {"description": "2nd reading", "house": "Commons", "stageSittings": [{"date": "2026-07-13T00:00:00"}]},
            {"description": "Committee stage", "house": "Commons",
             "stageSittings": [{"date": "2026-09-15T00:00:00"}, {"date": "2026-10-13T00:00:00"}, {"date": "2026-10-15T00:00:00"}]},
            {"description": "Report stage", "house": "Commons", "stageSittings": [{"date": "2026-11-10T00:00:00"}]},
            {"description": "2nd reading", "house": "Lords", "stageSittings": [{"date": "2026-12-01T00:00:00"}]}]}
        rows = dw.bill_watches(detail, stages, datetime.date(2026, 9, 17), area=11, note="immigration")
        self.assertEqual([(r[0], r[1], r[4]) for r in rows],
                         [("2026-10-13", "Commons", 8), ("2026-10-15", "Commons", 8), ("2026-11-10", "Commons", None), ("2026-12-01", "Lords", None)])
        self.assertEqual(rows[0][2], "Immigration and Asylum Bill")
        self.assertEqual(rows[0][3], "immigration: Committee stage (bill 4254)")
        watches, added, kept = dw.expand_bill([], detail, stages, datetime.date(2026, 9, 17), 11, "immigration")
        self.assertEqual((len(added), kept), (4, 0))
        self.assertEqual(dw.line(watches[0]), "WATCH: Commons | Immigration and Asylum Bill | area 11 | immigration: Committee stage (bill 4254) | min 8")
        # a second expansion adds nothing; a refresh with a new sitting adds one
        watches, added, kept = dw.expand_bill(watches, detail, stages, datetime.date(2026, 9, 17), 11, "immigration")
        self.assertEqual((len(added), kept), (0, 4))
        stages["items"][1]["stageSittings"].append({"date": "2026-10-20T00:00:00"})
        watches, added = dw.refresh_bills(watches, lambda bill_id: (detail, stages), datetime.date(2026, 9, 17))
        self.assertEqual(added, [("2026-10-20", "Commons", "Immigration and Asylum Bill")])
        self.assertEqual(watches[2]["area"], 11)                              # the refresh carries the bill's area
        self.assertEqual(watches[2]["note"], "immigration: Committee stage (bill 4254)")   # and the note's prefix
        self.assertEqual(watches[0]["note"], "immigration: Committee stage (bill 4254)")   # existing watches untouched (17 Sept: a refresh once stripped every note)
        d = tempfile.mkdtemp(); path = os.path.join(d, "w.yaml")
        dw.save(watches, path)
        self.assertEqual(dw.load(path)[0]["bill"], 4254)                       # the new fields survive the file

    def test_net_flags_the_grown_debate_once(self):
        rows = [{"house": "Commons", "title": "Urgent Question: Abortion Clinics", "speakers": 11, "areas": [1], "reasons": ["abortion"]},
                {"house": "Lords", "title": "Surrogacy", "speakers": 4, "areas": [10], "reasons": ["surrogacy"]}]
        watches, flagged = dw.net([], rows, "2026-09-17", minimum=8)
        self.assertEqual(flagged, [("Commons", "Urgent Question: Abortion Clinics", 11)])
        self.assertEqual((watches[0]["source"], watches[0]["min_speakers"], watches[0]["area"]), ("same-day", 8, 1))
        watches, flagged = dw.net(watches, rows, "2026-09-17", minimum=8)
        self.assertEqual(flagged, [])                                          # the second pass is silent


if __name__ == "__main__":
    unittest.main()
