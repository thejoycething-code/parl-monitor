"""Croatian Sabor members, agenda items and recorded votes (tools/hr_rollcalls.py).

No network: every page is a real sabor.hr response saved on 9 October 2026
(tests/fixtures/hr/).
"""

import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, hr_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "hr")


def _load():
    spec = importlib.util.spec_from_file_location(
        "hr_rollcalls", os.path.join(ROOT, "tools", "hr_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hrr = _load()


def fixture(name):
    path = os.path.join(FIX, name)
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return fh.read()


AGENDA = fixture("agenda_11_161305.html.gz")
INDEX = fixture("agenda_index_11.html.gz")
MEMBERS_P4 = fixture("members_11_p4.html.gz")
VOTE = json.loads(fixture("vote_214596.json.gz"))
NO_VOTE = json.loads(fixture("vote_214605_none.json"))
ITEM_REJECTED = fixture("item_214147_rejected.html.gz")
ITEM_PASSED = fixture("item_214596_passed.html.gz")

# A Croatian test taxonomy: NOT the proposed list, just enough to drive the
# classification path (inflected stems, an internal-star phrase, diacritics).
TEST_TAXONOMY = """
version: test
areas:
  1_abortion:
    tier1: ["pobačaj*", "prekid* trudnoće"]
  5_sex_based_rights:
    tier1: ["Istanbulsk* konvencij*", "rodn* ideologij*"]
  11_migration:
    tier2: ["strancima"]
"""


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


class FakeClient:
    """Serves URLs from a dict; a missing URL raises FetchError."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def _get(self, url):
        self.calls.append(url)
        if url not in self.pages:
            raise FetchError(url, "hr", "x", 4, "HTTP Error 503")
        return self.pages[url]

    def get_text(self, url, feed, slug, timeout=None, archive=True, **kw):
        return self._get(url)

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        return self._get(url)


class ParseTests(unittest.TestCase):
    def test_sessions_from_the_search_form(self):
        sessions = hrr.parse_sessions(INDEX)
        self.assertEqual(len(sessions), 12)
        self.assertEqual(sessions[0], (161305, "12", "12. sjednica Hrvatskoga sabora"))
        self.assertEqual(sessions[1][1], "11-izvanredna")
        self.assertEqual(sessions[-1][1], "1")

    def test_agenda_parses_every_declared_item(self):
        items, declared = hrr.parse_agenda(AGENDA)
        self.assertEqual(declared, 209)
        self.assertEqual(len(items), 209)
        self.assertEqual(len({i["tid"] for i in items}), 209)
        self.assertEqual(sum(1 for i in items if i["status_id"] == 8), 48)
        first = items[0]
        self.assertEqual(first["tid"], 214595)
        self.assertEqual(first["tocka"], 161307)
        self.assertIsNone(first["parent"])
        self.assertTrue(first["url"].startswith("https://www.sabor.hr/hr/sjednice-sabora/"))
        self.assertIn("P.Z.E. br. 329", first["title"])
        self.assertTrue(any(i["parent"] for i in items))

    def test_bill_key_is_saziv_and_number_never_title(self):
        self.assertEqual(hrr.parse_bill("..., P.Z.E. br. 328 - predlagateljica: Vlada"), ("11/328", "PZE"))
        self.assertEqual(hrr.parse_bill("prvo čitanje, P.Z. br. 280"), ("11/280", "PZ"))
        # As printed on 9 October 2026: no full stop after the E.
        self.assertEqual(hrr.parse_bill("prvo čitanje, P.Z.E br. 344 "), ("11/344", "PZE"))
        self.assertEqual(hrr.parse_bill("PRIJEDLOG ODLUKE O IZBORU"), (None, None))
        self.assertEqual(hrr.parse_bill("P.Z. br. 7", saziv=10), ("10/7", "PZ"))

    def test_members_page(self):
        rows, declared = hrr.parse_members(MEMBERS_P4)
        self.assertEqual(declared, 209)
        self.assertEqual(len(rows), 9)
        r = rows[0]
        self.assertTrue(r["slug"].endswith("saziv") or "saziv" in r["slug"])
        self.assertIn(", ", r["name"])
        self.assertIn(r["mandate"], ("Aktivan", "U mirovanju", "Završen"))

    def test_vote_record(self):
        v = hrr.parse_vote(VOTE)
        self.assertEqual((v["yes"], v["no"], v["abstain"], v["total"]), (81, 2, 41, 124))
        self.assertEqual(v["voted_at"], "2026-09-25T12:22")
        self.assertEqual(len(v["positions"]), 124)
        self.assertEqual(v["positions"][0], ("ackar-kresimir-11-saziv", "Ačkar, Krešimir", "for"))
        self.assertEqual({p for _s, _n, p in v["positions"]}, {"for", "against", "abstained"})
        self.assertIn("12. sjednica", v["session"])
        self.assertEqual(hrr.vote_problems(v), [])

    def test_a_zeroed_record_is_no_vote(self):
        # The service answers 200 with a zeroed record for an item never voted.
        self.assertEqual(NO_VOTE["total_count"], 0)
        self.assertIsNone(hrr.parse_vote(NO_VOTE))
        self.assertIsNone(hrr.iso_time("01.01.0001. 00:00"))

    def test_za_on_a_conclusion_not_to_accept_is_against_the_bill(self):
        # Digital Protection of Children Act, 6 March 2026: 76 Za killed it.
        sentence, reject = hrr.parse_outcome(ITEM_REJECTED)
        self.assertIn("zaključak da se ne prihvaća", sentence)
        self.assertEqual(reject, 1)
        sentence, reject = hrr.parse_outcome(ITEM_PASSED)
        self.assertIn("Zakon je donesen", sentence)
        self.assertEqual(reject, 0)
        self.assertEqual(hrr.parse_outcome("<html></html>"), (None, None))

    def test_inconsistent_vote_is_reported(self):
        v = hrr.parse_vote(dict(VOTE, total_count=125))
        problems = hrr.vote_problems(v)
        self.assertEqual(len(problems), 2)


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        fd, self.tax_path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(TEST_TAXONOMY)
        self.tax = filt.load_taxonomy(self.tax_path)
        fd, self.wl = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write('bills:\n  "11/77": {areas: [9], why: "test"}\nitems:\n  214604: {areas: [6]}\n')
        hr_store._WATCH.clear()

    def tearDown(self):
        os.unlink(self.tax_path)
        os.unlink(self.wl)
        hr_store._WATCH.clear()

    def test_no_taxonomy_means_not_classified(self):
        self.assertEqual(hrr.classify(None, "PRIJEDLOG ZAKONA O POBAČAJU", 1, None, self.wl),
                         (None, None, None))

    def test_inflected_upper_case_titles_match(self):
        areas, terms, tier = hrr.classify(
            self.tax, "PRIJEDLOG DEKLARACIJE O ODBACIVANJU ISTANBULSKE KONVENCIJE I RODNE IDEOLOGIJE",
            1, None, self.wl)
        self.assertEqual(json.loads(areas), [5])
        self.assertEqual(tier, 1)
        areas, _t, _tier = hrr.classify(self.tax, "ZAKON O PREKIDU TRUDNOĆE", 1, None, self.wl)
        self.assertEqual(json.loads(areas), [1])

    def test_watchlist_by_key_with_or_without_taxonomy(self):
        areas, terms, tier = hrr.classify(None, "PRIJEDLOG ZAKONA O NEČEMU", 5, "11/77", self.wl)
        self.assertEqual(json.loads(areas), [9])
        self.assertEqual(json.loads(terms), ["watch:11/77"])
        self.assertEqual(tier, 2)
        areas, _t, _tier = hrr.classify(self.tax, "PRIJEDLOG ODLUKE", 214604, None, self.wl)
        self.assertEqual(json.loads(areas), [6])
        # The same title under another key gets nothing: keys, never titles.
        self.assertEqual(json.loads(hrr.classify(self.tax, "PRIJEDLOG ODLUKE", 9, None, self.wl)[0]), [])


class CollectTests(unittest.TestCase):
    def setUp(self):
        hr_store._WATCH.clear()
        self.conn = store()
        node = hrr.SAZIV_NODE[11]
        self.pages = {
            hrr.AGENDA_INDEX.format(node): INDEX,
            hrr.AGENDA.format(node, 161305): AGENDA,
            hrr.VOTE.format(214596): VOTE,
            hrr.MEMBERS.format(node, 0): MEMBERS_P4,
        }
        for tid in (214595, 214599, 214603, 214604):
            self.pages[hrr.VOTE.format(tid)] = NO_VOTE

    def tearDown(self):
        hr_store._WATCH.clear()

    def test_schema_is_declared(self):
        for t in hr_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_first_run_reads_every_session_and_records_the_misses(self):
        client = FakeClient(self.pages)
        n, read, gaps = hrr.pull_agendas(self.conn, client, "2026-10-09", log=lambda *a: None)
        self.assertEqual(n, 209)
        self.assertEqual(read, [161305])
        # The other eleven sessions are not in the fake: one gap each, kept.
        self.assertEqual(gaps, 11)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 11)
        row = self.conn.execute("SELECT bill_key, bill_marker, session_no, status_id, areas "
                                "FROM hr_items WHERE tid=214596").fetchone()
        self.assertEqual(row[:4], ("11/328", "PZE", "12", 8))
        self.assertIsNone(row[4])   # no taxonomy-hr: not classified

    def test_later_runs_read_only_recent_sessions(self):
        client = FakeClient(self.pages)
        hrr.pull_agendas(self.conn, client, "2026-10-09", log=lambda *a: None)
        client = FakeClient(self.pages)
        n, read, gaps = hrr.pull_agendas(self.conn, client, "2026-10-16", recent=1,
                                         log=lambda *a: None)
        self.assertEqual((n, read, gaps), (209, [161305], 0))
        self.assertEqual(len(client.calls), 2)

    def test_votes_stored_with_every_position(self):
        client = FakeClient(self.pages)
        hrr.pull_members(self.conn, client, "2026-10-09", log=lambda *a: None)
        hrr.pull_agendas(self.conn, client, "2026-10-09", log=lambda *a: None)
        stored, none, gaps = hrr.pull_votes(self.conn, client, "2026-10-09",
                                            sessions_read=[161305], log=lambda *a: None)
        self.assertEqual(stored, 1)
        self.assertEqual(none, 4)
        # 48 voted items, 5 served: 43 fetch failures, each a gap.
        self.assertEqual(gaps, 43)
        d = self.conn.execute("SELECT division_key, bill_key, yes, no, abstain, total, voted_at "
                              "FROM hr_divisions").fetchall()
        self.assertEqual(d, [("hr-11-214596", "11/328", 81, 2, 41, 124, "2026-09-25T12:22")])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM hr_votes").fetchone()[0], 124)
        # Members the single page did not list are kept under their own slug.
        self.assertEqual(self.conn.execute(
            "SELECT name FROM hr_members WHERE slug='ackar-kresimir-11-saziv'").fetchone()[0],
            "Ačkar, Krešimir")
        states = dict(self.conn.execute("SELECT tid, vote_state FROM hr_items WHERE tid IN "
                                        "(214596, 214604)"))
        self.assertEqual(states, {214596: "stored", 214604: "none"})

    def test_held_votes_are_not_fetched_again(self):
        client = FakeClient(self.pages)
        hrr.pull_agendas(self.conn, client, "2026-10-09", log=lambda *a: None)
        hrr.pull_votes(self.conn, client, "2026-10-09", sessions_read=[], log=lambda *a: None)
        client = FakeClient(self.pages)
        hrr.pull_votes(self.conn, client, "2026-10-16", sessions_read=[], log=lambda *a: None)
        self.assertNotIn(hrr.VOTE.format(214596), client.calls)
        # 'none' is re-asked only while its session is one read this run.
        self.assertNotIn(hrr.VOTE.format(214604), client.calls)
        client = FakeClient(self.pages)
        hrr.pull_votes(self.conn, client, "2026-10-16", sessions_read=[161305], log=lambda *a: None)
        self.assertIn(hrr.VOTE.format(214604), client.calls)

    def test_outcomes_are_read_for_votes_on_our_ground_only(self):
        client = FakeClient(self.pages)
        hrr.pull_agendas(self.conn, client, "2026-10-09", log=lambda *a: None)
        hrr.pull_votes(self.conn, client, "2026-10-09", sessions_read=[], log=lambda *a: None)
        url = self.conn.execute("SELECT url FROM hr_items WHERE tid=214596").fetchone()[0]
        self.pages[url] = ITEM_PASSED
        # Not classified, so not read by default.
        self.assertEqual(hrr.pull_outcomes(self.conn, FakeClient(self.pages), "2026-10-09",
                                           log=lambda *a: None), (0, 0))
        self.conn.execute("UPDATE hr_divisions SET areas='[7]' WHERE tid=214596")
        client = FakeClient(self.pages)
        self.assertEqual(hrr.pull_outcomes(self.conn, client, "2026-10-09", log=lambda *a: None), (1, 0))
        row = self.conn.execute("SELECT outcome, yes_means_reject FROM hr_divisions "
                                "WHERE tid=214596").fetchone()
        self.assertTrue(row[0].endswith('41 "suzdržan").'))
        self.assertEqual(row[1], 0)
        # Read once: a held outcome is not fetched again.
        client = FakeClient(self.pages)
        hrr.pull_outcomes(self.conn, client, "2026-10-16", log=lambda *a: None)
        self.assertEqual(client.calls, [])

    def test_members_short_read_is_a_gap(self):
        client = FakeClient(self.pages)
        stored, gaps = hrr.pull_members(self.conn, client, "2026-10-09", log=lambda *a: None)
        # Page 0 of the fake is the real page 4 (9 rows); page 1 is missing.
        self.assertEqual(stored, 9)
        self.assertEqual(gaps, 1)

    def test_reclassify_fills_items_and_divisions(self):
        client = FakeClient(self.pages)
        hrr.pull_agendas(self.conn, client, "2026-10-09", log=lambda *a: None)
        hrr.pull_votes(self.conn, client, "2026-10-09", sessions_read=[], log=lambda *a: None)
        fd, path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(TEST_TAXONOMY.replace('"strancima"', '"električne energije"'))
        try:
            hrr.reclassify(self.conn, tax=filt.load_taxonomy(path), log=lambda *a: None)
        finally:
            os.unlink(path)
        self.assertEqual(self.conn.execute(
            "SELECT areas FROM hr_divisions WHERE tid=214596").fetchone()[0], "[11]")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM hr_items WHERE areas IS NULL").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
