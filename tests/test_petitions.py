"""E-petitions early warning (Christopher, 2026-09-07)."""

import datetime
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import digest  # noqa: E402
from src.ingest import petitions  # noqa: E402


def row(pid, action, sigs, **attrs):
    a = {"action": action, "background": "bg", "additional_details": "det", "state": "open",
         "signature_count": sigs, "opened_at": "2026-03-12T17:01:57.173Z", "closing_date": "2026-09-12T23:59:59.999Z",
         "departments": [{"name": "Department for Education"}], "topics": []}
    a.update(attrs)
    return {"type": "petition", "id": pid, "links": {}, "attributes": a}


class ParseTests(unittest.TestCase):
    def test_a_row_becomes_a_petition_with_dates_as_days(self):
        p = petitions.parse_petition(row(763161, "Reform surrogacy law", 101234,
                                         debate_threshold_reached_at="2026-04-03T22:06:10.000Z",
                                         scheduled_debate_date="2026-09-07"))
        self.assertEqual(p.url, "https://petition.parliament.uk/petitions/763161")
        self.assertEqual(p.debate_reached, "2026-04-03")
        self.assertEqual(p.scheduled_debate_date, "2026-09-07")
        self.assertEqual(p.departments, ["Department for Education"])
        self.assertIn("Reform surrogacy law bg det", p.text)

    def test_paging_follows_next_and_dedupes_across_states(self):
        class Client:
            def __init__(self):
                self.calls = []

            def get_json(self, url, feed, slug, archive=True):
                self.calls.append((url, archive))
                if "state=open" in url and "page=2" not in url:
                    return {"data": [row(1, "A", 5), row(2, "B", 6)],
                            "links": {"next": petitions.API + "?page=2&state=open"}}
                if "page=2" in url:
                    return {"data": [row(3, "C", 7)], "links": {"next": None}}
                return {"data": [row(3, "C", 7)], "links": {"next": None}}   # awaiting_* repeat id 3
        c = Client()
        out = petitions.fetch_all(c)
        self.assertEqual(sorted(p.id for p in out), [1, 2, 3])
        self.assertTrue(all(not archive for _, archive in c.calls), "listing pages must not be archived")
        self.assertEqual(len(c.calls), 4)      # 2 open pages + 2 single-page states


class MilestoneTests(unittest.TestCase):
    today = datetime.date(2026, 9, 7)

    def _p(self, sigs, **attrs):
        return petitions.parse_petition(row(1, "X", sigs, **attrs))

    def test_the_ladder(self):
        self.assertEqual(petitions.milestone(self._p(4200), self.today),
                         "5,800 to a Government response; closes 2026-09-12")
        self.assertEqual(petitions.milestone(self._p(12000, response_threshold_reached_at="2026-08-30T00:00:00Z"), self.today),
                         "Passed 10,000 on 2026-08-30; Government response due")
        self.assertEqual(petitions.milestone(self._p(30000, response_threshold_reached_at="2026-08-01T00:00:00Z",
                                                     government_response_at="2026-08-20T00:00:00Z"), self.today),
                         "Government responded 2026-08-20; 70,000 more to a debate")
        self.assertEqual(petitions.milestone(self._p(120000, debate_threshold_reached_at="2026-09-01T00:00:00Z"), self.today),
                         "Passed 100,000 on 2026-09-01; debate to be scheduled")
        self.assertEqual(petitions.milestone(self._p(120000, debate_threshold_reached_at="2026-09-01T00:00:00Z",
                                                     scheduled_debate_date="2026-10-12"), self.today),
                         "Debate scheduled for 2026-10-12")


class RenderTests(unittest.TestCase):
    def _row(self, **kw):
        base = {"id": "763161", "title": "e-petition 763161: Reform surrogacy law", "url": "https://petition.parliament.uk/petitions/763161",
                "why": "Commercial surrogacy is the ground.", "signatures": 101234, "prev_signatures": 98000,
                "milestone": "Debate scheduled for 2026-09-07"}
        base.update(kw)
        return base

    def test_table_with_level_velocity_and_stage(self):
        out = digest.render_petitions([self._row()])
        self.assertIn("## E-petitions on our ground", out)
        self.assertIn("| [Reform surrogacy law](https://petition.parliament.uk/petitions/763161) | 101,234 (+3,234 this week) "
                      "| Debate scheduled for 2026-09-07 | Commercial surrogacy is the ground. |", out)

    def test_a_first_sighting_says_so(self):
        out = digest.render_petitions([self._row(prev_signatures=None)])
        self.assertIn("101,234 (new to the monitor)", out)

    def test_sorted_by_signatures_and_capped(self):
        rows = [self._row(id=str(i), title="e-petition {0}: P{0}".format(i), signatures=i * 1000) for i in range(1, 20)]
        out = digest.render_petitions(rows, cap=5)
        self.assertLess(out.index("P19"), out.index("P15"))
        self.assertNotIn("[P1]", out)
        self.assertIn("...and 14 more, in the store.", out)

    def test_empty_is_none_and_the_edm_heading_lost_petitions(self):
        self.assertIsNone(digest.render_petitions([]))
        src = open(os.path.join(ROOT, "src", "digest.py"), encoding="utf-8").read()
        self.assertNotIn('"EDMs and petitions"', src)
        self.assertIn('"Early day motions"', src)


class SweepTests(unittest.TestCase):
    def _conn(self):
        from src import db
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        return conn

    def _client(self, sigs):
        class Client:
            def get_json(self, url, feed, slug, archive=True):
                if "state=open" in url:
                    return {"data": [row(763161, "Reform surrogacy law and legal parenthood", sigs),
                                     row(5, "Lower the price of beer", 900)], "links": {"next": None}}
                return {"data": [], "links": {"next": None}}
        return Client()

    def test_only_petitions_on_our_ground_are_stored_with_a_snapshot(self):
        import run_weekly
        from src import filter as filt
        conn = self._conn()
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        n = run_weekly.sweep_petitions(self._client(98000), conn, tax, wl, datetime.date(2026, 8, 30), "2026-08-31", log=lambda *_: None)
        self.assertEqual(n, 1)
        ids = [r[0] for r in conn.execute("SELECT id FROM items WHERE source_feed='petition'")]
        self.assertEqual(ids, ["petition:763161"])
        # a week later: the snapshot gives the movement
        run_weekly.sweep_petitions(self._client(101234), conn, tax, wl, datetime.date(2026, 9, 6), "2026-09-07", log=lambda *_: None)
        import json
        extra = json.loads(conn.execute("SELECT extra FROM items WHERE id='petition:763161'").fetchone()[0])
        self.assertEqual((extra["prev_signatures"], extra["signatures"]), (98000, 101234))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM petition_snapshots").fetchone()[0], 2)

    def test_tier_two_vocabulary_alone_does_not_admit_a_petition(self):
        """168 of the first sweep's 269 came in on tier-2 words: "birth rate"
        in a student-loan petition, "coercion" in one about China."""
        import run_weekly
        from src import filter as filt
        conn = self._conn()
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

        class Client:
            def get_json(self, url, feed, slug, archive=True):
                if "state=open" in url:
                    return {"data": [row(1, "Scrap RPI interest on student loans", 5000,
                                         background="It depresses the birth rate."),
                                     row(2, "Reverse the ban on puberty blockers", 5000)],
                            "links": {"next": None}}
                return {"data": [], "links": {"next": None}}
        run_weekly.sweep_petitions(Client(), conn, tax, wl, datetime.date(2026, 9, 6), "2026-09-07", log=lambda *_: None)
        ids = [r[0] for r in conn.execute("SELECT id FROM items WHERE source_feed='petition'")]
        self.assertEqual(ids, ["petition:2"])

    def test_migration_only_petitions_stay_out_of_the_section(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        block = src[src.index('if feed == "petition":'):src.index('if feed == "si":')]
        self.assertIn("if a != 11]", block)
        self.assertLess(block.index("if a != 11]"), block.index("edition.petitions.append"))

    def test_the_weekly_runs_it_and_coverage_watches_it(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        self.assertIn("sweep_petitions(client, conn, tax, wl, datetime.date.today(), edition)", src)
        self.assertIn('"petition": 7', src)                       # renders in the week it was seen
        cov = open(os.path.join(ROOT, "tools", "coverage.py"), encoding="utf-8").read()
        self.assertIn('("petition_snapshots", "captured_at"', cov)


if __name__ == "__main__":
    unittest.main()
