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


class NotInTheReportTests(unittest.TestCase):
    """Christopher, 2026-09-07: "I'd like petitions not to be included in
    the weekly report." Collated, never judged, never rendered."""

    def test_the_edition_has_no_petitions_section_or_field(self):
        src = open(os.path.join(ROOT, "src", "digest.py"), encoding="utf-8").read()
        self.assertNotIn("E-petitions on our ground", src)
        self.assertNotIn("render_petitions", src)
        self.assertFalse(hasattr(digest.Edition(week_commencing="2026-09-07", number=1, mode="normal"), "petitions"))

    def test_the_sweep_never_writes_items(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        block = src[src.index("def sweep_petitions("):src.index("def sweep_edms(")]
        self.assertNotIn("store_item(", block)
        self.assertNotIn('"petition"', src[src.index("window_days = {"):src.index("window_days = {") + 80])
        self.assertIn('"Early day motions"', open(os.path.join(ROOT, "src", "digest.py"), encoding="utf-8").read())


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
        ids = [r[0] for r in conn.execute("SELECT id FROM petitions")]
        self.assertEqual(ids, [763161])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)   # never an item
        # a week later: the snapshots give the movement
        run_weekly.sweep_petitions(self._client(101234), conn, tax, wl, datetime.date(2026, 9, 6), "2026-09-07", log=lambda *_: None)
        snaps = conn.execute("SELECT captured_at, signatures FROM petition_snapshots ORDER BY captured_at").fetchall()
        self.assertEqual([tuple(s) for s in snaps], [("2026-08-30", 98000), ("2026-09-06", 101234)])
        row_ = conn.execute("SELECT signatures, first_seen, last_seen FROM petitions WHERE id=763161").fetchone()
        self.assertEqual(tuple(row_), (101234, "2026-08-30", "2026-09-06"))

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
        ids = [r[0] for r in conn.execute("SELECT id FROM petitions")]
        self.assertEqual(ids, [2])

    def test_a_tier_two_match_past_ten_thousand_is_admitted(self):
        """The misogyny hate-crime petition: 114,927 signatures, a debate the
        same day, and nothing but tier-2 "hate crime" in its text."""
        import run_weekly
        from src import filter as filt
        conn = self._conn()
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

        class Client:
            def get_json(self, url, feed, slug, archive=True):
                if "state=open" in url:
                    return {"data": [row(746640, "Legislate that crimes motivated by misogyny are hate crimes", 114927,
                                         background="Make misogyny a hate crime."),
                                     row(9, "Small petition using the same words", 900,
                                         background="Make misogyny a hate crime.")],
                            "links": {"next": None}}
                return {"data": [], "links": {"next": None}}
        run_weekly.sweep_petitions(Client(), conn, tax, wl, datetime.date(2026, 9, 6), "2026-09-07", log=lambda *_: None)
        ids = [r[0] for r in conn.execute("SELECT id FROM petitions")]
        self.assertEqual(ids, [746640])

    def test_the_weekly_runs_it_and_coverage_watches_it(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        self.assertIn("sweep_petitions(client, conn, tax, wl, datetime.date.today(), edition)", src)
        cov = open(os.path.join(ROOT, "tools", "coverage.py"), encoding="utf-8").read()
        self.assertIn('("petition_snapshots", "captured_at"', cov)
        self.assertIn('("petitions", "last_seen"', cov)


if __name__ == "__main__":
    unittest.main()
