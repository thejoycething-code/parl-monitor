"""NL4 (Chris, 10 October 2026): the Eerste Kamer via its web pages
(tools/nl_eerstekamer.py, the nl_ek_* tables, the Dutch edition). No
network: ek_stemmingen_p1.html and _p3.html are the first and third pages of
eerstekamer.nl's "Stemmingen per vergaderdag" as read on 10 October 2026."""

import datetime
import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce, db, nl_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "nl")


def _load():
    spec = importlib.util.spec_from_file_location(
        "nl_eerstekamer", os.path.join(ROOT, "tools", "nl_eerstekamer.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ek = _load()
TAX = ek.load_taxonomy()
QUIET = dict(log=lambda *_: None)


def page(n):
    with open(os.path.join(FIX, "ek_stemmingen_p{0}.html".format(n)), encoding="utf-8") as fh:
        return fh.read()


def store():
    return db.init_db(sqlite3.connect(":memory:"))


class FakeClient:
    def __init__(self, pages):
        self.pages = pages          # list of html, or None for a refusal
        self.asked = []

    def get_text(self, url, feed, slug, **kw):
        self.asked.append(url)
        i = len(self.asked) - 1
        if i >= len(self.pages) or self.pages[i] is None:
            raise FetchError(url, feed, slug, 1, "HTTP Error 503")
        return self.pages[i]


class ParseTests(unittest.TestCase):
    def test_a_page_has_25_votes_and_a_polite_next_link(self):
        votes, nxt = ek.parse_page(page(1))
        self.assertEqual(len(votes), 25)
        self.assertEqual(nxt, "/stemmingen_per_vergaderdag?start_006=25&dlastinprev=2026-09-22")
        self.assertEqual(votes[0]["date"], "2026-10-06")
        self.assertEqual(votes[-1]["date"], "2026-09-22")

    def test_a_show_of_hands_names_fracties(self):
        votes, _ = ek.parse_page(page(1))
        v = [x for x in votes if x["ref"] == "37020-H"][0]
        self.assertEqual(v["kind"], "motion")
        self.assertEqual(v["dossier"], "37020")
        self.assertEqual((v["method"], v["result"]), ("Stemming bij zitten en opstaan",
                                                      "verworpen"))
        self.assertEqual(v["voor"], ["PVV"])
        self.assertEqual(len(v["tegen"]), 18)
        self.assertIn("Fractie-Visseren-Hamakers", v["tegen"])
        self.assertTrue(v["title"].startswith("Motie-Van Hattem (PVV) c.s. over hoofddoekjesverbod"))

    def test_a_hamerstuk_with_recorded_dissent(self):
        votes, _ = ek.parse_page(page(1))
        v = [x for x in votes if x["ref"] == "36745"][0]
        self.assertEqual((v["method"], v["result"]), ("Hamerstuk", "aangenomen"))
        self.assertEqual(v["aantekening"], ["SGP", "FVD", "JA21"])
        self.assertEqual((v["voor"], v["tegen"]), ([], []))

    def test_a_roll_call_names_every_senator(self):
        votes, _ = ek.parse_page(page(3))
        v = [x for x in votes if x["ref"] == "CLXXVII"][0]
        self.assertTrue(v["roll_call"])
        self.assertEqual((len(v["voor"]), len(v["tegen"])), (55, 5))
        self.assertEqual(ek.member_side(v["tegen"][0]), ("Alexander van Hattem", "PVV"))
        amendment = [x for x in votes if x["ref"] == "CLXXVII-F"][0]
        self.assertEqual((amendment["kind"], amendment["result"]), ("amendment", "verworpen"))

    def test_unanimous_without_sides(self):
        votes, _ = ek.parse_page(page(3))
        v = [x for x in votes if x["ref"] == "36886"][0]
        self.assertEqual((v["method"], v["result"]), ("Algemene stemmen", "aangenomen"))

    def test_references(self):
        self.assertEqual(ek.reference("37.020, M"), ("37020", "37020-M"))
        self.assertEqual(ek.reference("36.791"), ("36791", "36791"))
        self.assertEqual(ek.reference("36.945 I"), ("36945-I", "36945-I"))
        self.assertEqual(ek.reference("36.800 M, F"), ("36800-M", "36800-M-F"))
        self.assertEqual(ek.reference("36.455 (R2188)"), ("36455", "36455"))
        self.assertEqual(ek.reference("EK CLXXVII  F"), ("CLXXVII", "CLXXVII-F"))

    def test_lists(self):
        self.assertEqual(ek.split_list("BBB, PVV en SGP"), ["BBB", "PVV", "SGP"])
        self.assertEqual(ek.split_list("PVV"), ["PVV"])
        self.assertEqual(ek.split_list(""), [])

    def test_keys_are_date_and_reference_with_a_repeat_numbered(self):
        votes = [{"date": "2026-10-06", "ref": "36791"}, {"date": "2026-10-06", "ref": "36791"},
                 {"date": "2026-10-07", "ref": "36791"}]
        ek.assign_keys(votes)
        self.assertEqual([v["key"] for v in votes],
                         ["ek-20261006-36791", "ek-20261006-36791-2", "ek-20261007-36791"])


class PullTests(unittest.TestCase):
    def test_the_pull_stops_at_since_and_stores_sides(self):
        conn = store()
        client = FakeClient([page(1), page(3)])
        read, ours, gaps = ek.pull(conn, client, "2026-10-10", since="2026-09-29", tax=TAX,
                                   **QUIET)
        self.assertEqual(len(client.asked), 1)          # page 1 already reaches back past since
        self.assertEqual(gaps, 0)
        self.assertEqual(read, 19)
        self.assertEqual(conn.execute("SELECT MIN(date) FROM nl_ek_divisions").fetchone()[0],
                         "2026-09-29")
        sides = dict(conn.execute("SELECT position, COUNT(*) FROM nl_ek_votes WHERE "
                                  "division_key='ek-20261006-37020-H' GROUP BY position"))
        self.assertEqual(sides, {"voor": 1, "tegen": 18})
        self.assertEqual(conn.execute("SELECT last_result FROM nl_ek_bills WHERE dossier='36791'"
                                      ).fetchone()[0], "aangenomen")

    def test_the_trafficking_bill_is_on_our_ground(self):
        conn = store()
        ek.pull(conn, FakeClient([page(1)]), "2026-10-10", since="2026-09-22", tax=TAX,
                max_pages=1, **QUIET)
        areas = json.loads(conn.execute("SELECT areas FROM nl_ek_divisions WHERE "
                                        "division_key='ek-20260929-36547'").fetchone()[0])
        self.assertIn(12, areas)        # 'mensenhandel'

    def test_a_watched_dossier_by_key(self):
        conn = store()
        wl_path = os.path.join(ROOT, "config", "watchlist-nl.yaml")
        res = ek.classify(TAX, ek.empty_watchlist(), "Wet zonder treffers", "37027", wl_path)
        self.assertEqual(res.issue_areas, [1])
        self.assertIn("watch:dossier:37027", res.watchlist_hits)
        res = ek.classify(TAX, ek.empty_watchlist(), "Wet zonder treffers", "37027-A", wl_path)
        self.assertEqual(res.issue_areas, [1])
        del conn

    def test_a_refused_first_page_is_a_gap(self):
        conn = store()
        read, ours, gaps = ek.pull(conn, FakeClient([None]), "2026-10-10", tax=TAX, **QUIET)
        self.assertEqual((read, gaps), (0, 1))

    def test_a_second_run_rewrites_nothing_new(self):
        conn = store()
        for _ in range(2):
            ek.pull(conn, FakeClient([page(1)]), "2026-10-10", since="2026-09-22", tax=TAX,
                    max_pages=1, **QUIET)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM nl_ek_divisions").fetchone()[0], 25)

    def test_reclassify_is_offline_and_idempotent(self):
        conn = store()
        ek.pull(conn, FakeClient([page(1)]), "2026-10-10", since="2026-09-22", tax=TAX,
                max_pages=1, **QUIET)
        self.assertEqual(ek.reclassify(conn, TAX, **QUIET), 0)


class EditionTests(unittest.TestCase):
    def test_eerste_kamer_votes_in_the_dutch_edition(self):
        conn = store()
        ek.pull(conn, FakeClient([page(1), page(3)]), "2026-10-10", since="2026-09-08", tax=TAX,
                max_pages=2, **QUIET)
        conn.execute("UPDATE nl_ek_divisions SET areas='[5]' WHERE division_key IN "
                     "('ek-20260908-CLXXVII', 'ek-20260929-36745')")
        conn.row_factory = sqlite3.Row
        from src.editions import nl
        got = {it["key"]: it for it in nl.eerste_kamer(conn, "2026-09-01", "2026-10-10", {})}
        self.assertIn("ek-20260929-36547", got)          # trafficking, its own words
        roll = got["ek-20260908-CLXXVII"]
        self.assertIn("55 for, 5 against", roll["lines"][0])
        self.assertIn("60 member positions stored", " ".join(roll["lines"]))
        hamer = got["ek-20260929-36745"]
        self.assertIn("hamerstuk", hamer["lines"][0])
        self.assertIn("FVD, JA21, SGP", hamer["lines"][1])
        hands = got["ek-20260929-36547"]
        self.assertTrue(any(ln.startswith("By fractie: for ") for ln in hands["lines"]))
        self.assertTrue(hands["takeaway"].startswith("Eerste Kamer: Bill 36547"))
        self.assertNotIn("ek-20261006-37020-M", got)      # off our ground


class SchemaTests(unittest.TestCase):
    def test_tables_declared(self):
        conn = store()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("nl_ek_bills", "nl_ek_divisions", "nl_ek_votes"):
            self.assertIn(t, nl_store.TABLES)
            self.assertIn(t, db.TABLES)
            self.assertIn(t, have)

    def test_the_job_runs_it_after_the_tweede_kamer(self):
        with open(os.path.join(ROOT, "jobs", "nl-weekly.sh"), encoding="utf-8") as fh:
            job = fh.read()
        self.assertLess(job.index("tools/nl_rollcalls.py --budget-seconds"),
                        job.index("tools/nl_eerstekamer.py --budget-seconds"))
        self.assertLess(job.index("tools/nl_eerstekamer.py --budget-seconds"),
                        job.rindex("tools/nl_monitor.py"))


if __name__ == "__main__":
    unittest.main()
