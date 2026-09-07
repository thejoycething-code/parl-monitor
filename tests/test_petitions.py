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


class CompanionPageTests(unittest.TestCase):
    """Christopher, 2026-09-07: "Build the petitions companion page." Where the
    collated record surfaces, since the report does not carry it."""

    def _conn(self):
        from src import db
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        def pet(pid, action, sigs, areas, first, last, milestone="x"):
            conn.execute("INSERT INTO petitions (id, action, url, state, signatures, areas, matched, tier, "
                         "milestone, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (pid, action, "https://petition.parliament.uk/petitions/{0}".format(pid), "open",
                          sigs, areas, "[]", 1, milestone, first, last))
        pet(763161, "Change surrogacy law", 113045, "[10]", "2026-08-30", "2026-09-06", "Debate scheduled for 2026-09-07")
        pet(5, "Digital ID referendum", 5656, "[7]", "2026-09-06", "2026-09-06", "4,344 to a Government response")
        pet(9, "Deport everyone", 11032, "[11]", "2026-08-30", "2026-09-06")
        pet(4, "Stale petition", 999, "[1]", "2026-08-23", "2026-08-30")   # not in the latest sweep
        conn.executemany("INSERT INTO petition_snapshots VALUES (?,?,?)", [
            (763161, "2026-08-30", 110000), (763161, "2026-09-06", 113045), (5, "2026-09-06", 5656),
            (9, "2026-08-30", 10000), (9, "2026-09-06", 11032)])
        return conn

    def test_rows_carry_movement_and_hide_migration_and_stale(self):
        from src import partner
        latest, rows = partner.petition_rows(self._conn())
        self.assertEqual(latest, "2026-09-06")
        self.assertEqual([r["id"] for r in rows], [763161, 5])
        self.assertEqual(rows[0]["delta"], 3045)
        self.assertIsNone(rows[1]["delta"])
        self.assertTrue(rows[1]["new"])

    def test_the_page_renders_both_tables_and_is_linked_from_the_nav(self):
        import tempfile
        from src import partner
        out = tempfile.mkdtemp()
        path = partner.build_petitions_page(out, self._conn(), {10: "Surrogacy and embryology", 7: "Free speech"})
        html = open(path, encoding="utf-8").read()
        self.assertIn("Moving fastest this week", html)
        self.assertIn("All petitions on our ground (2)", html)
        self.assertIn('href="https://petition.parliament.uk/petitions/763161"', html)
        self.assertIn("+3,045", html)
        self.assertIn("new to the monitor", html)
        self.assertIn("Surrogacy and embryology", html)
        self.assertNotIn("Deport everyone", html)
        self.assertNotIn("Stale petition", html)
        partner.build_site(out, "2026-09-07", "# Parliamentary Monitor\n\n## Top lines\n\n- x\n", ["2026-09-07"])
        self.assertIn('<a href="/petitions.html">E-petitions on our ground</a>',
                      open(os.path.join(out, "index.html"), encoding="utf-8").read())

    def test_no_petitions_means_no_page_not_a_crash(self):
        import tempfile
        from src import db, partner
        conn = db.init_db(sqlite3.connect(":memory:")); conn.row_factory = sqlite3.Row
        self.assertIsNone(partner.build_petitions_page(tempfile.mkdtemp(), conn))

    def test_the_monday_publish_builds_it(self):
        src = open(os.path.join(ROOT, "run_monday.py"), encoding="utf-8").read()
        self.assertIn("partner.build_petitions_page(", src)
        self.assertLess(src.index("partner.build_petitions_page("), src.index("pq_conn.close()"))


class ExclusionTests(unittest.TestCase):
    """Christopher, 2026-09-07: "Add the exclusion list for those two petitions." """

    def test_the_two_named_petitions_are_excluded_with_reasons(self):
        import yaml
        settings = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8"))
        ex = petitions.exclusions(settings)
        self.assertEqual(ex, {771833, 772026})
        for e in settings["petition_exclusions"]:
            self.assertGreater(len(e["reason"]), 20)

    def test_an_exclusion_without_a_reason_is_refused(self):
        with self.assertRaises(ValueError):
            petitions.exclusions({"petition_exclusions": [{"id": 1}]})

    def test_the_sweep_skips_them_and_the_page_hides_already_collated_rows(self):
        import run_weekly, tempfile
        from src import filter as filt, partner, db
        conn = db.init_db(sqlite3.connect(":memory:")); conn.row_factory = sqlite3.Row
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

        class Client:
            def get_json(self, url, feed, slug, archive=True):
                if "state=open" in url:
                    return {"data": [row(771833, "General election now", 16545, background="rape gangs and small boats"),
                                     row(2, "Reverse the ban on puberty blockers", 5000)], "links": {"next": None}}
                return {"data": [], "links": {"next": None}}
        run_weekly.sweep_petitions(Client(), conn, tax, wl, datetime.date(2026, 9, 6), "2026-09-07", log=lambda *_: None)
        self.assertEqual([r[0] for r in conn.execute("SELECT id FROM petitions")], [2])
        # a row collated BEFORE it was excluded still leaves the page
        conn.execute("INSERT INTO petitions (id, action, url, state, signatures, areas, matched, tier, milestone, first_seen, last_seen) "
                     "VALUES (772026, 'Kashmir', 'u', 'open', 20427, '[7]', '[]', 1, 'm', '2026-09-06', '2026-09-06')")
        _, rows = partner.petition_rows(conn)
        self.assertEqual([r["id"] for r in rows], [2])


if __name__ == "__main__":
    unittest.main()
