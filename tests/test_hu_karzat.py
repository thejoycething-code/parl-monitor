"""Hungary HU7: karzat's open data loaded into the hu_* tables
(tools/hu_karzat_backfill.py, src/hu_store.py) and shown by the Hungarian
edition (src/editions/hu.py).

Fixtures under tests/fixtures/hu/karzat/ are karzat's own derived files at
commit 4f932a3a0513 (3 September 2026, CC BY 4.0), trimmed on 10 October
2026 to nine votes (the quorum call and a secret ballot of 9 May, the
sixteenth amendment T/51 and its summary amendment, the seventeenth
amendment T/324's urgency motion and final vote, and the votes on the
ministers' answers to interpellations I/49, I/133 and I/308), nine papers
and thirteen members, with each vote's positions for those members only.
No network."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import hu_gazette as hg  # noqa: E402
import hu_karzat_backfill as kb  # noqa: E402
from src import country_edition as ce, db, hu_store, sv_pdf  # noqa: E402
from src.editions import hu  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "hu", "karzat")
COMMIT = "4f932a3a0513b67fc4b2adf31aa9536ae928ae16"
SOURCE = "karzat@4f932a3a0513"
T51_FINAL = "2026.06.15.17:20:04"
T324_FINAL = "2026.07.13.18:19:08"


class FakeClient:
    """Serves the GitHub API's commit list and the four files; records URLs."""

    def __init__(self):
        self.asked = []

    def get_json(self, url, feed, slug, **kw):
        self.asked.append(url)
        if "/commits?" in url:
            return [{"sha": COMMIT}]
        return kb.read_dir(FIX)[url.rsplit("/", 1)[1]]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "t.db")
        self.conn = db.connect(self.path)
        db.init_db(self.conn)
        self.tax = kb.load_taxonomy()
        self.wl = hu_store.watchlist()
        self.summary = kb.load(self.conn, kb.read_dir(FIX), COMMIT, "2026-10-10", self.tax,
                               self.wl)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.dir)

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()


class Loading(Base):
    def test_tables_are_declared(self):
        for t in ("hu_members", "hu_papers", "hu_divisions", "hu_votes", "hu_sources"):
            self.assertIn(t, db.TABLES)

    def test_counts_and_range(self):
        s = self.summary
        self.assertEqual((s["members"], s["papers"], s["divisions"]), (13, 9, 9))
        self.assertEqual((s["from"], s["to"], s["as_of"]), ("2026-05-09", "2026-07-20",
                                                            "2026-08-28"))
        self.assertEqual(s["positions"], self.one("SELECT COUNT(*) FROM hu_votes")[0])
        self.assertEqual((s["unplaced_members"], s["unjoined_motions"]), ([], []))

    def test_a_member_code_mps_lacks_is_placed_by_name_or_reported(self):
        data = kb.read_dir(FIX)
        pos = data["votes_positions.json"]
        pos["members"]["zz99"] = dict(pos["members"]["g053"])        # Gulyás, by name
        pos["members"]["zz98"] = {"faction": "TISZA", "name": "Nobody Known"}
        pos["positions"][T51_FINAL] += [["zz99", 1, "n"], ["zz98", 0, "i"]]
        s = kb.load(self.conn, data, COMMIT, "2026-10-10", self.tax, self.wl)
        self.assertEqual(s["unplaced_members"], ["karzat:zz98"])

    def test_keys_are_the_parliaments_own(self):
        r = self.one("SELECT * FROM hu_divisions WHERE vote_ts = ?", (T324_FINAL,))
        # '324/14' (the consolidated text) is joined to its paper by number, not title
        self.assertEqual((r["motion"], r["paper_key"]), ("324/14", "T/324"))
        self.assertEqual((r["yes"], r["no"], r["majority"]), (139, 6, "ketharmad_osszes"))
        ids = {x[0] for x in self.conn.execute("SELECT member_id FROM hu_votes")}
        self.assertIn("g053", {x[0] for x in self.conn.execute(
            "SELECT member_id FROM hu_members WHERE name = 'Gulyás Gergely'")})
        self.assertTrue(ids <= {x[0] for x in self.conn.execute("SELECT member_id FROM hu_members")})

    def test_every_row_says_where_it_came_from(self):
        for t in ("hu_members", "hu_papers", "hu_divisions", "hu_votes"):
            self.assertEqual({x[0] for x in self.conn.execute("SELECT DISTINCT source FROM " + t)},
                             {SOURCE}, t)
        src = self.one("SELECT * FROM hu_sources")
        self.assertEqual((src["source"], src["licence"], src["data_to"], src["commit_sha"]),
                         (SOURCE, "CC BY 4.0", "2026-08-28", COMMIT))
        self.assertIn("github.com/abognar-git/karzat", src["attribution"])

    def test_positions_carry_the_group_at_the_vote(self):
        got = self.one("SELECT v.faction, v.position FROM hu_votes v JOIN hu_members m USING "
                       "(member_id) WHERE m.name = 'Gulyás Gergely' AND vote_ts = "
                       "'2026.07.20.16:09:34'")
        self.assertEqual(tuple(got), ("Fidesz", "igen"))

    def test_secret_ballot_has_no_positions(self):
        r = self.one("SELECT * FROM hu_divisions WHERE vote_ts = '2026.05.09.11:50:00'")
        self.assertEqual((r["secret"], r["paper_key"]), (1, "S/3"))
        self.assertEqual(self.one("SELECT COUNT(*) FROM hu_votes WHERE vote_ts = ?",
                                  (r["vote_ts"],))[0], 0)


class Rules(Base):
    def test_hu4_amendments_whatever_their_words(self):
        for key in ("T/51", "T/324", "T/9"):
            self.assertEqual(self.one("SELECT rule FROM hu_papers WHERE paper_key = ?",
                                      (key,))[0], "HU4", key)
        self.assertEqual({x[0] for x in self.conn.execute(
            "SELECT rule FROM hu_divisions WHERE paper_key IN ('T/51', 'T/324')")}, {"HU4"})

    def test_hu5_interpellation_answers(self):
        got = dict(self.conn.execute("SELECT paper_key, rule FROM hu_divisions WHERE "
                                     "motion_kind = 'I'").fetchall())
        self.assertEqual(got, {"I/49": "HU5", "I/133": "HU5", "I/308": "HU5"})
        # on our ground only when the interpellation is
        self.assertEqual(self.one("SELECT areas FROM hu_divisions WHERE paper_key = 'I/133'")[0],
                         "[9]")
        self.assertEqual(self.one("SELECT areas FROM hu_divisions WHERE paper_key = 'I/49'")[0],
                         "[]")

    def test_answers_and_elections_are_not_divorce(self):
        # "az interpellációs választ elfogadta", B/1's "Választási Bizottság"
        for key in ("I/49", "B/1"):
            self.assertNotIn("9", self.one("SELECT areas FROM hu_papers WHERE paper_key = ?",
                                           (key,))[0], key)

    def test_watchlist_by_paper_number(self):
        r = self.one("SELECT watched, areas FROM hu_papers WHERE paper_key = 'H/179'")
        self.assertEqual(r["watched"], 1)


class Rerunning(Base):
    def test_idempotent(self):
        before = [self.one("SELECT COUNT(*) FROM " + t)[0]
                  for t in ("hu_members", "hu_papers", "hu_divisions", "hu_votes", "hu_sources")]
        kb.load(self.conn, kb.read_dir(FIX), COMMIT, "2026-11-01", self.tax, self.wl)
        after = [self.one("SELECT COUNT(*) FROM " + t)[0]
                 for t in ("hu_members", "hu_papers", "hu_divisions", "hu_votes", "hu_sources")]
        self.assertEqual(before, after)
        r = self.one("SELECT first_seen, last_seen FROM hu_papers WHERE paper_key = 'T/51'")
        self.assertEqual(tuple(r), ("2026-10-10", "2026-11-01"))

    def test_the_houses_own_record_wins(self):
        self.conn.execute("UPDATE hu_divisions SET source = 'w-api', yes = 999 WHERE vote_ts = ?",
                          (T51_FINAL,))
        self.conn.execute("UPDATE hu_votes SET source = 'w-api' WHERE vote_ts = ?", (T51_FINAL,))
        self.conn.execute("UPDATE hu_papers SET source = 'w-api', title = 'kept' "
                          "WHERE paper_key = 'T/51'")
        self.conn.commit()
        n = self.one("SELECT COUNT(*) FROM hu_votes WHERE vote_ts = ?", (T51_FINAL,))[0]
        s = kb.load(self.conn, kb.read_dir(FIX), COMMIT, "2026-11-01", self.tax, self.wl)
        self.assertEqual(s["kept_house_rows"], 1)
        self.assertEqual(self.one("SELECT yes, source FROM hu_divisions WHERE vote_ts = ?",
                                  (T51_FINAL,))[:], (999, "w-api"))
        self.assertEqual(self.one("SELECT title FROM hu_papers WHERE paper_key = 'T/51'")[0],
                         "kept")
        self.assertEqual(self.one("SELECT COUNT(*) FROM hu_votes WHERE vote_ts = ? AND source "
                                  "= 'w-api'", (T51_FINAL,))[0], n)

    def test_reclassify_offline(self):
        self.conn.execute("UPDATE hu_divisions SET areas = '[]', rule = NULL")
        self.conn.commit()
        self.assertEqual(kb.reclassify(self.conn, self.tax, self.wl), 18)
        self.assertEqual(self.one("SELECT rule FROM hu_divisions WHERE vote_ts = ?",
                                  (T324_FINAL,))[0], "HU4")


class Fetching(unittest.TestCase):
    def test_reads_only_karzats_files_on_github(self):
        c = FakeClient()
        sha = kb.latest_commit(c)
        data = kb.fetch(c, sha)
        self.assertEqual(sorted(data), sorted(kb.FILES))
        for url in c.asked:
            self.assertTrue(url.startswith(("https://api.github.com/repos/abognar-git/karzat/",
                                            "https://raw.githubusercontent.com/abognar-git/karzat/"
                                            + COMMIT + "/data/derived/")), url)
            self.assertNotIn("parlament.hu", url)

    def test_main_skips_a_commit_already_loaded(self):
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "t.db")
            self.assertEqual(kb.main(["--db", path, "--from-dir", FIX, "--commit", COMMIT]), 0)
            conn = sqlite3.connect(path)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM hu_divisions").fetchone()[0], 9)
            conn.close()
        finally:
            shutil.rmtree(d)


class GazetteCrossCheck(Base):
    def test_the_seventeenth_amendment_agrees_with_the_gazette(self):
        import gzip
        with open(os.path.join(ROOT, "tests", "fixtures", "hu", "mk-2026-092.pdf.gz"), "rb") as fh:
            pages = sv_pdf.pdf_lines(gzip.decompress(fh.read()), max_pages=hg.MAX_CONTENTS_PAGES)
        issue = {"year": 2026, "serial": 92, "date": "2026-07-18", "url": None, "pdf_url": "x"}
        entries = hg.contents_entries(pages)
        hg.store_entries(self.conn, issue, entries, hg.load_taxonomy(), {}, "2026-10-10")
        hg.store_issue(self.conn, issue, pages, entries, "2026-10-10")
        got = {k: v for k, _, v in kb.cross_check(self.conn)}
        self.assertEqual(got["T/324"], "agrees")
        self.assertEqual(got["T/51"], "issue not in the gazette store")
        # and the amendment's heading carries the day of the final vote
        heading = self.one("SELECT entry_key FROM hu_gazette_entries WHERE type = "
                           "'fundamental_law'")[0]
        self.assertIn("2026. július 13.", heading)
        self.assertEqual(self.one("SELECT date FROM hu_divisions WHERE vote_ts = ?",
                                  (T324_FINAL,))[0], "2026-07-13")


class Edition(Base):
    def render(self, today, since):
        self.conn.row_factory = sqlite3.Row
        return ce.render(self.conn, hu.COUNTRY, today, since, directory=self.dir)

    def test_a_week_with_votes(self):
        text = self.render("2026-06-16", "2026-06-09")
        self.assertIn("## Recorded votes", text)
        self.assertIn("Tally: 135 for, 50 against, 6 abstaining (needing two-thirds of all MPs)",
                      text)
        self.assertIn("By group at the vote", text)
        self.assertIn("The final vote on T/51", text)
        self.assertIn(hu.KARZAT_ITEM, text)
        self.assertIn("- **Attribution.** " + hu_store.KARZAT_ATTRIBUTION, text)
        self.assertIn("karzat's open data", text.split("## ")[0])      # the notice
        self.assertNotIn("—", text)

    def test_against_their_group(self):
        text = self.render("2026-07-21", "2026-07-14")
        self.assertIn("Against their group's majority: Gulyás Gergely (Fidesz)", text)

    def test_historical_only_in_its_own_week(self):
        text = self.render("2026-10-09", "2026-10-02")
        self.assertNotIn("## Recorded votes", text)
        self.assertNotIn("**Attribution.**", text)
        self.assertIn("karzat", text)             # the standing notice still credits it

    def test_procedural_vote_left_out_unless_watched(self):
        it = {"cc": "hu", "kind": "vote", "title": "sürgősségi javaslat elfogadva",
              "watched": False, "key": "x", "terms": [], "areas": [7]}
        self.assertEqual(ce.noise_for(hu.COUNTRY).drop_reason(it), "procedural vote")

    def test_the_since_9_may_summary(self):
        text = hu.backfill_summary(self.conn)
        self.assertIn("# Hungary: the karzat backfill, 9 May 2026 to 28 August 2026", text)
        self.assertIn("9 papers", text)
        self.assertIn(hu_store.KARZAT_ATTRIBUTION, text)
        self.assertIn("Magyarország Alaptörvényének tizenhetedik módosítása", text)
        self.assertNotIn("—", text)

    def test_no_karzat_no_change(self):
        conn = db.connect(os.path.join(self.dir, "empty.db"))
        db.init_db(conn)
        self.assertEqual(hu.notice(conn, "2026-10-09", False), "> " + hu.STANDING)
        self.assertIn("Nothing loaded", hu.backfill_summary(conn))
        conn.close()


if __name__ == "__main__":
    unittest.main()
