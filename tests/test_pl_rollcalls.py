"""Polish Sejm deputies, prints, processes and recorded votes (tools/pl_rollcalls.py).

No network: every reply is a real api.sejm.gov.pl response saved on 9 October
2026 (tests/fixtures/pl/), trimmed to a handful of records where the whole
reply is large (the print list is 1.8 MB, the MP list 250 KB).
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, pl_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "pl")


def _load():
    spec = importlib.util.spec_from_file_location(
        "pl_rollcalls", os.path.join(ROOT, "tools", "pl_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plr = _load()


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


TERMS = fixture("terms.json")
MPS = fixture("mp_10_trimmed.json")
PRINTS = fixture("prints_10_trimmed.json")
PROCESSES = fixture("processes_10_trimmed.json")
PROCESS_3030 = fixture("process_10_3030.json")
INDEX = fixture("votings_index_10_trimmed.json")
SITTING_58 = fixture("sitting_10_58.json")
VOTE_65_1 = fixture("vote_10_65_1.json")
VOTE_ONLIST = fixture("vote_10_1_1_onlist.json")

# A Polish TEST taxonomy: NOT the proposed list, just enough to drive the
# classification path (inflected stems, an internal-star phrase, diacritics).
TEST_TAXONOMY = """
version: test
areas:
  1_abortion:
    tier1: ["aborcj*", "przerywani* ciąży"]
  5_sex_based_rights:
    tier1: ["gender", "konwencj* stambulsk*"]
  9_marriage_family:
    tier1: ["status* osoby najbliższej"]
"""


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


def test_taxonomy():
    fh = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    fh.write(TEST_TAXONOMY)
    fh.close()
    try:
        return filt.load_taxonomy(fh.name)
    finally:
        os.unlink(fh.name)


def empty_watch():
    fh = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    fh.write("processes: {}\n")
    fh.close()
    return fh.name


class FakeClient:
    """Serves URLs from a dict; a missing URL raises FetchError."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.calls.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.pages[url]


T = 10
PAGES = {
    plr.TERMS: TERMS,
    plr.MEMBERS.format(T): MPS,
    plr.PRINTS.format(T): PRINTS,
    plr.PROCESSES.format(T, plr.PAGE, 0): PROCESSES,
    plr.PROCESS.format(T, "3030"): PROCESS_3030,
    plr.VOTE_INDEX.format(T): INDEX,
    plr.SITTING.format(T, 58): SITTING_58,
    plr.VOTE.format(T, 65, 1): VOTE_65_1,
}


def quiet(*_a, **_k):
    pass


class ParsingTests(unittest.TestCase):
    def test_current_term_and_its_print_count(self):
        self.assertEqual(plr.current_term(TERMS), (10, 3415))
        self.assertEqual(plr.current_term([]), (None, None))

    def test_print_numbers_from_every_wording(self):
        self.assertEqual(plr.print_numbers("Pkt. 2 Sprawozdanie (druki nr 3030, 3080 i 3080-A)"),
                         ["3030", "3080", "3080-A"])
        self.assertEqual(plr.print_numbers("Głosowanie proceduralne dotyczące druku 3156"), ["3156"])
        self.assertEqual(plr.print_numbers("dotyczące druku nr 3187", "z druku nr 3187"), ["3187"])
        self.assertEqual(plr.print_numbers("(druki nr 258, 1387, 1661 i 1661-A) - trzecie czytanie"),
                         ["258", "1387", "1661", "1661-A"])
        self.assertEqual(plr.print_numbers("Wniosek o przerwę", None), [])

    def test_article_and_item_numbers_are_not_prints(self):
        # "Pkt. 34" and "art. 44 ust. 3" are not prints.
        self.assertEqual(plr.print_numbers(
            "wniosek o skrócenie terminu, o którym mowa w art. 44 ust. 3 regulaminu Sejmu "
            "w sprawie sprawozdania z druku nr 3151"), ["3151"])

    def test_member_row(self):
        r = plr.member_row(MPS[0], 10)
        self.assertEqual((r["mp_key"], r["name"], r["club"], r["district"], r["active"]),
                         ("10/1", "Andrzej Adamczyk", "PiS", "Kraków (13)", 1))
        gone = [m for m in MPS if not m["active"]][0]
        self.assertEqual(plr.member_row(gone, 10)["inactive_cause"], gone["inactiveCause"])

    def test_last_stage_is_the_latest_dated(self):
        self.assertEqual(plr.last_stage(PROCESS_3030["stages"]),
                         ("Praca w komisjach po II czytaniu", "2026-10-07"))

    def test_vote_problems_clean_on_a_real_vote(self):
        self.assertEqual(plr.vote_problems(VOTE_65_1), [])
        self.assertEqual(len(VOTE_65_1["votes"]), 460)

    def test_vote_problems_catch_a_count_that_does_not_add_up(self):
        bad = dict(VOTE_65_1, yes=VOTE_65_1["yes"] + 1)
        self.assertEqual(plr.vote_problems(bad), ["yes 257 declared, 256 listed"])
        self.assertEqual(plr.vote_problems(dict(VOTE_65_1, votes=[])), ["no positions in the reply"])

    def test_on_list_votes_are_not_tallied_as_yes_no(self):
        # Elections of persons: every valid ballot is 'VOTE_VALID' with listVotes.
        self.assertEqual(VOTE_ONLIST["kind"], "ON_LIST")
        self.assertEqual(plr.vote_problems(VOTE_ONLIST), [])


class ClassificationTests(unittest.TestCase):
    def test_no_taxonomy_and_no_watch_means_not_classified(self):
        w = empty_watch()
        try:
            self.assertEqual(plr.classify_process(None, "Rządowy projekt ustawy", "", "10/1", w),
                             (None, None, None))
        finally:
            os.unlink(w)

    def test_the_real_watchlist_classifies_by_key_without_a_taxonomy(self):
        areas, matched, tier = plr.classify_process(None, "Poselski projekt ustawy o zmianie ustawy - "
                                                    "Kodeks karny", "", "10/176")
        self.assertEqual(json.loads(areas), [1])
        self.assertIn("watch:10/176", json.loads(matched))
        self.assertEqual(tier, 2)

    def test_inflected_polish_matches_through_stems(self):
        tax = test_taxonomy()
        w = empty_watch()
        try:
            areas, matched, tier = plr.classify_process(
                tax, "Poselski projekt ustawy o bezpiecznym przerywaniu ciąży", "", "10/999", w)
            self.assertEqual((json.loads(areas), tier), ([1], 1))
            areas, _m, _t = plr.classify_process(
                tax, "Rządowy projekt ustawy o statusie osoby najbliższej w związku", "", "10/998", w)
            self.assertEqual(json.loads(areas), [9])
        finally:
            os.unlink(w)

    def test_division_takes_its_processes_areas(self):
        own, areas, matched, tier = plr.classify_division(
            None, ("Pkt. 5 Sprawozdanie Komisji", "głosowanie nad całością projektu.", ""),
            [('[9]', '["watch:10/2110"]', 2)])
        self.assertIsNone(own)
        self.assertEqual((json.loads(areas), tier), ([9], 2))
        self.assertEqual(plr.classify_division(None, ("Wniosek o przerwę",), []), (None, None, None, None))


class CollectTests(unittest.TestCase):
    def run_all(self, conn, pages=PAGES, tax=None):
        """The run order of main(). Returns (client, gaps of the vote-header step)."""
        client = FakeClient(dict(pages))
        plr.pull_members(conn, client, T, "2026-10-09", log=quiet)
        plr.pull_prints(conn, client, T, "2026-10-09", declared=len(PRINTS), log=quiet)
        plr.pull_processes(conn, client, T, tax, "2026-10-09", log=quiet)
        plr.pull_stages(conn, client, T, "2026-10-09", log=quiet)
        return client, plr.pull_divisions(conn, client, T, tax, "2026-10-09", log=quiet)[2]

    def test_members_prints_processes(self):
        conn = store()
        self.run_all(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pl_members").fetchone()[0], len(MPS))
        self.assertEqual(conn.execute("SELECT process_key FROM pl_prints WHERE print_key='10/3080-A'")
                         .fetchone()[0], "10/3030")
        row = conn.execute("SELECT title, document_type_enum, areas FROM pl_processes "
                           "WHERE process_key='10/2110'").fetchone()
        self.assertTrue(row[0].startswith("Rządowy projekt ustawy o statusie osoby najbliższej"))
        self.assertEqual(row[1], "BILL")
        self.assertEqual(json.loads(row[2]), [9])          # watchlist-pl, by key
        self.assertIsNone(conn.execute("SELECT areas FROM pl_processes WHERE process_key='10/3030'")
                          .fetchone()[0])                    # not classified, not "none"

    def test_a_vote_reaches_its_process_through_its_prints(self):
        conn = store()
        self.run_all(conn)
        prints, procs, areas, yes, no = conn.execute(
            "SELECT print_numbers, process_keys, areas, yes, no FROM pl_divisions "
            "WHERE division_key='pl-10-58-62'").fetchone()
        self.assertEqual(json.loads(prints)[:2], ["2110", "2593"])
        self.assertEqual(json.loads(procs), ["10/2110"])
        self.assertEqual(json.loads(areas), [9])
        self.assertEqual((yes, no), (230, 198))

    def test_every_vote_of_the_sitting_is_stored_once(self):
        conn = store()
        self.run_all(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pl_divisions WHERE sitting=58").fetchone()[0],
                         len(SITTING_58))
        # A second run re-reads the recent sittings without duplicating.
        self.run_all(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pl_divisions").fetchone()[0], len(SITTING_58))

    def test_missing_sittings_are_gaps_not_silence(self):
        conn = store()
        _client, gaps = self.run_all(conn)
        # The trimmed index names sittings 65 and 66 too; the fake serves only 58.
        self.assertEqual(gaps, 2)
        details = [d for (d,) in conn.execute("SELECT detail FROM gaps WHERE feed='pl-rollcalls'")]
        self.assertTrue(any(d.startswith("sitting 66:") for d in details))

    def test_print_count_shortfall_is_a_gap(self):
        conn = store()
        client = FakeClient(PAGES)
        _n, gaps = plr.pull_prints(conn, client, T, "2026-10-09", declared=3415, log=quiet)
        self.assertEqual(gaps, 1)

    def test_stages_read_only_for_classified_processes_and_only_once(self):
        conn = store()
        w = empty_watch()
        try:
            client = FakeClient(PAGES)
            plr.pull_processes(conn, client, T, None, "2026-10-09", log=quiet, watch_path=w)
            # Nothing classified: no detail is fetched at all.
            self.assertEqual(plr.pull_stages(conn, client, T, "2026-10-09", log=quiet), (0, 0))
            conn.execute("UPDATE pl_processes SET areas='[11]' WHERE process_key='10/3030'")
            self.assertEqual(plr.pull_stages(conn, client, T, "2026-10-09", log=quiet), (1, 0))
            self.assertEqual(conn.execute("SELECT last_stage_date FROM pl_processes "
                                          "WHERE process_key='10/3030'").fetchone()[0], "2026-10-07")
            self.assertEqual(plr.pull_stages(conn, client, T, "2026-10-09", log=quiet), (0, 0))
        finally:
            os.unlink(w)

    def test_positions_with_the_club_at_the_vote(self):
        conn = store()
        conn.execute("INSERT INTO pl_divisions (division_key, term, sitting, number) "
                     "VALUES ('pl-10-65-1', 10, 65, 1)")
        stored, gaps = plr.pull_positions(conn, FakeClient(PAGES), T, "2026-10-09", log=quiet)
        self.assertEqual((stored, gaps), (1, 0))
        self.assertEqual(conn.execute("SELECT positions FROM pl_divisions").fetchone()[0], 460)
        self.assertEqual(conn.execute("SELECT position, club FROM pl_votes WHERE mp_key='10/1'")
                         .fetchone(), ("NO", "PiS"))
        counts = dict(conn.execute("SELECT position, COUNT(*) FROM pl_votes GROUP BY position"))
        self.assertEqual(counts, {"YES": 256, "NO": 131, "ABSTAIN": 16, "ABSENT": 57})
        # Held now: a second pass fetches nothing.
        client = FakeClient(PAGES)
        self.assertEqual(plr.pull_positions(conn, client, T, "2026-10-09", log=quiet), (0, 0))
        self.assertEqual(client.calls, [])

    def test_on_list_positions_keep_the_ballot(self):
        conn = store()
        conn.execute("INSERT INTO pl_divisions (division_key, term, sitting, number) "
                     "VALUES ('pl-10-1-1', 10, 1, 1)")
        pages = dict(PAGES)
        pages[plr.VOTE.format(T, 1, 1)] = VOTE_ONLIST
        plr.pull_positions(conn, FakeClient(pages), T, "2026-10-09", log=quiet)
        pos, lv = conn.execute("SELECT position, list_votes FROM pl_votes WHERE mp_key='10/1'").fetchone()
        self.assertEqual((pos, json.loads(lv)), ("VOTE_VALID", {"1": "NO", "2": "YES"}))

    def test_a_failed_vote_detail_is_a_gap_and_retried_next_run(self):
        conn = store()
        conn.execute("INSERT INTO pl_divisions (division_key, term, sitting, number) "
                     "VALUES ('pl-10-66-9', 10, 66, 9)")
        self.assertEqual(plr.pull_positions(conn, FakeClient(PAGES), T, "2026-10-09", log=quiet), (0, 1))
        self.assertIsNone(conn.execute("SELECT positions FROM pl_divisions").fetchone()[0])

    def test_reclassify_fills_areas_offline_when_the_taxonomy_lands(self):
        conn = store()
        w = empty_watch()
        try:
            client = FakeClient(PAGES)
            plr.pull_prints(conn, client, T, "2026-10-09", log=quiet)
            plr.pull_processes(conn, client, T, None, "2026-10-09", log=quiet, watch_path=w)
            plr.pull_divisions(conn, client, T, None, "2026-10-09", log=quiet)
            self.assertIsNone(conn.execute("SELECT areas FROM pl_processes WHERE process_key='10/176'")
                              .fetchone()[0])
            plr.reclassify(conn, tax=test_taxonomy(), log=quiet, watch_path=w)
            self.assertEqual(json.loads(conn.execute(
                "SELECT areas FROM pl_processes WHERE process_key='10/176'").fetchone()[0]), [1])
            self.assertEqual(json.loads(conn.execute(
                "SELECT areas FROM pl_divisions WHERE division_key='pl-10-58-62'").fetchone()[0]), [9])
        finally:
            os.unlink(w)

    def test_tables_are_declared(self):
        for t in pl_store.TABLES:
            self.assertIn(t, db.TABLES)


class WatchlistTests(unittest.TestCase):
    def test_keys_are_term_and_number_never_titles(self):
        for key in pl_store.watchlist():
            self.assertRegex(key, r"^\d+/\d+$")

    def test_every_entry_has_areas_and_a_reason(self):
        for key, (areas, why) in pl_store.watchlist().items():
            self.assertTrue(areas, key)
            self.assertTrue(all(1 <= a <= 13 for a in areas), key)
            self.assertTrue(why, key)


if __name__ == "__main__":
    unittest.main()
