"""Schema creation tests (handoff section 5)."""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db


class InitDbTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def tearDown(self):
        self.conn.close()

    def _table_names(self):
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return {r["name"] for r in rows}

    def test_creates_every_table(self):
        db.init_db(self.conn)
        self.assertEqual(set(db.TABLES), self._table_names())

    def test_init_is_idempotent(self):
        db.init_db(self.conn)
        db.init_db(self.conn)  # must not raise
        self.assertEqual(set(db.TABLES), self._table_names())

    def test_items_has_date_tabled_column(self):
        # Required for PQ deep links (handoff section 4.2 / pilot gap #4).
        db.init_db(self.conn)
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(items)")}
        self.assertIn("date_tabled", cols)
        self.assertIn("raw_path", cols)

    def test_bills_board_has_snapshot_and_session_columns(self):
        db.init_db(self.conn)
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(bills_board)")}
        self.assertIn("board_snapshot", cols)  # movement marker
        self.assertIn("session_ids", cols)     # prorogation-fall detection
        self.assertIn("closed_edition", cols)  # one-closing-entry guard

    def test_edm_signatures_composite_key(self):
        db.init_db(self.conn)
        self.conn.execute(
            "INSERT INTO edm_signatures (edm_id, edition, count) VALUES (603, '2026-08-03', 6)"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO edm_signatures (edm_id, edition, count) VALUES (603, '2026-08-03', 7)"
            )


if __name__ == "__main__":
    unittest.main()


class GapPersistenceTests(unittest.TestCase):
    """A gap must be queryable afterwards, and countable correctly.

    Christopher, 2026-08-29. The Senedd tools wrote gaps to the table, the
    Holyrood tools kept a private copy of the same helper, and the NI tools
    collected gaps in a list and only PRINTED them -- so a run log was the
    only record NI ever left. All three now write through src.db.

    And the write is idempotent per day. It was not: on 2026-08-28 the
    Senedd weekly ran five times against a WAF-blocked host, and 11 real
    gaps became 50 rows, so the table answered "how bad was that day" five
    times worse than the truth.
    """

    def _conn(self):
        conn = db.init_db(db.connect(":memory:"))
        return conn

    def test_a_gap_is_stored_and_printed(self):
        conn = self._conn()
        db.record_gap(conn, "test-feed", "the source did not answer")
        rows = conn.execute("SELECT feed, detail FROM gaps").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(tuple(rows[0]), ("test-feed", "the source did not answer"))

    def test_the_same_gap_twice_in_a_day_is_one_row(self):
        conn = self._conn()
        for _ in range(4):
            db.record_gap(conn, "test-feed", "identical failure")
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 1)

    def test_the_same_gap_on_another_day_is_its_own_row(self):
        """Idempotency must not hide a failure that recurs next week."""
        conn = self._conn()
        db.record_gap(conn, "test-feed", "identical failure", edition="2026-08-28")
        db.record_gap(conn, "test-feed", "identical failure", edition="2026-09-04")
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 2)

    def test_a_collected_list_persists_whole(self):
        conn = self._conn()
        n = db.record_gaps(conn, "ni-classify", ["one", "two", "three"])
        self.assertEqual(n, 3)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 3)

    def test_every_nation_persists_its_gaps(self):
        """NI printed and stored nothing; that is the fault being fixed."""
        import glob
        for tool in ("ni_pull", "ni_divisions", "ni_classify",
                     "sp_pull", "sp_divisions", "sp_committees",
                     "sd_pull", "sd_divisions", "sd_committees", "sd_bills"):
            path = os.path.join(ROOT, "tools", tool + ".py")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            self.assertTrue(
                "record_gap" in src or "INTO gaps" in src,
                "{0} reports gaps without persisting them".format(tool))

    def test_no_writer_can_duplicate(self):
        import glob
        for path in glob.glob(os.path.join(ROOT, "tools", "*.py")) + \
                [os.path.join(ROOT, "src", "digest.py")]:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            self.assertNotIn(
                "INSERT INTO gaps", src,
                "{0}: use INSERT OR IGNORE, the index forbids duplicates"
                .format(os.path.basename(path)))


class GapMigrationTests(unittest.TestCase):
    """init_db must open a store that already holds duplicate gaps.

    I put the UNIQUE index in the schema script, having deduplicated my own
    copy first. Every OTHER store still held duplicates, so CREATE UNIQUE
    INDEX threw inside executescript, init_db raised, and every tool that
    opens the store died. Green locally, broken in CI, on the first run.
    """

    def _store_with_duplicates(self, path):
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE gaps (edition TEXT, feed TEXT, detail TEXT)")
        for _ in range(5):
            conn.execute("INSERT INTO gaps VALUES ('2026-08-28','sd-bills','403')")
        conn.execute("INSERT INTO gaps VALUES ('2026-08-28','sd-bills','404')")
        conn.commit()
        conn.close()

    def test_init_survives_a_store_full_of_duplicates(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dup.db")
            self._store_with_duplicates(path)
            conn = db.init_db(db.connect(path))          # must not raise
            rows = conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0]
            self.assertEqual(rows, 2, "duplicates were not collapsed")

    def test_the_index_exists_afterwards(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dup.db")
            self._store_with_duplicates(path)
            conn = db.init_db(db.connect(path))
            self.assertTrue(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' "
                "AND name='gaps_once'").fetchone())

    def test_opening_twice_is_safe(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dup.db")
            self._store_with_duplicates(path)
            db.init_db(db.connect(path))
            conn = db.init_db(db.connect(path))          # must not raise
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 2)

    def test_the_index_is_not_in_the_schema_script(self):
        """Where it was, and why that broke every store but mine."""
        self.assertNotIn("CREATE UNIQUE INDEX IF NOT EXISTS gaps_once", db.SCHEMA)


class NiCommitteeRegisterTests(unittest.TestCase):
    """The NI committee register, added 2026-08-29.

    Wales held 19 committees and Scotland harvests 6,965 committee
    contributions; Northern Ireland held none, so the store could not answer
    which NI committees exist. organisations.asmx had never been called.
    """

    FIXTURES = os.path.join(ROOT, "tests", "fixtures")

    def _fx(self, name):
        import json
        with open(os.path.join(self.FIXTURES, name), encoding="utf-8") as fh:
            return json.load(fh)

    def test_the_statutory_committees_are_the_ones_that_matter(self):
        from src.ingest import niassembly
        rows = niassembly.parse_committees(
            self._fx("ni_committees_statutory.json"), "Statutory")
        names = [n for _i, n, _a, _k in rows]
        self.assertEqual(len(rows), 9)
        for want in ("Committee for Health", "Committee for Education",
                     "Committee for Justice"):
            self.assertIn(want, names)

    def test_a_single_committee_is_not_collapsed_away(self):
        """The API returns a bare object rather than a list of one, which
        bites anything that indexes straight in."""
        from src.ingest import niassembly
        rows = niassembly.parse_committees(self._fx("ni_committees_one.json"),
                                           "Statutory")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:3], ("10", "Committee for Health", "HEA"))

    def test_all_four_kinds_are_read(self):
        """A register that silently omits three of its four kinds is worse
        than no register."""
        from src.ingest import niassembly
        self.assertEqual(set(niassembly.COMMITTEE_KINDS),
                         {"Statutory", "Standing", "AdHoc", "Other"})

    def test_the_kind_is_stored_so_procedural_ones_can_be_told_apart(self):
        conn = db.init_db(db.connect(":memory:"))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ni_committees)")}
        self.assertIn("kind", cols)
        self.assertIn("abbreviation", cols)

    def test_the_weekly_runs_it(self):
        path = os.path.join(ROOT, ".github", "workflows", "ni-weekly.yml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("tools/ni_committees.py", text)
        self.assertIn("committees", text.split("for f in pull")[1][:60])


class HolyroodCommitteeRegisterTests(unittest.TestCase):
    """Scotland harvested 6,965 committee contributions while holding no
    list of its own committees -- the exact mirror of Northern Ireland,
    which had the list and none of the contributions. Both are now
    registers, so all three nations answer the same question."""

    FIXTURES = os.path.join(ROOT, "tests", "fixtures")

    def _fx(self):
        import json
        with open(os.path.join(self.FIXTURES, "sp_committees.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)

    def test_only_the_committees_still_sitting_are_kept(self):
        """/Committees returns all 169 the Parliament has ever had. A
        register listing 169 when 16 are sitting answers the wrong
        question."""
        from src.ingest import holyrood
        current = holyrood.parse_committees(self._fx())
        every = holyrood.parse_committees(self._fx(), current_only=False)
        self.assertLess(len(current), len(every))
        for _cid, _n, _s, _f, until in current:
            self.assertIsNone(until, "a closed committee is in the register")

    def test_the_history_is_still_reachable(self):
        from src.ingest import holyrood
        every = holyrood.parse_committees(self._fx(), current_only=False)
        self.assertTrue(any(u for _c, _n, _s, _f, u in every))

    def test_all_three_nations_have_a_register_table(self):
        conn = db.init_db(db.connect(":memory:"))
        for table in ("sd_committees", "sp_committees", "ni_committees"):
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(%s)" % table)}
            self.assertIn("name", cols, table)
            self.assertIn("committee_id", cols, table)


class DerivedStateSurvivesADeployTests(unittest.TestCase):
    """A table a TOOL creates exists only where that tool has run.

    2026-08-29. tools/sp_score.py made sp_scored with CREATE TABLE IF NOT
    EXISTS. I ran it, wrote 386 rows, reported them -- and the next deploy
    pulled the CI store, which had never heard of the table, and published
    that back over the top. The rows were written and gone inside the hour.

    Two rules follow, and both are checked here: every table the pipeline
    depends on is created by the SCHEMA, and every tool that writes derived
    state is run by a workflow. State that only exists where a human ran
    something is not published state.
    """

    def test_the_scored_table_is_in_the_schema(self):
        conn = db.init_db(db.connect(":memory:"))
        self.assertTrue(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='sp_scored'").fetchone())
        self.assertIn("sp_scored", db.TABLES)

    # Four tools created their own tables before this rule existed. They have
    # not been bitten because each is created in the same JOB that reads it --
    # the fragility is real but latent, and rewriting them was not part of
    # what was asked. They are named so a FIFTH cannot appear quietly.
    LEGACY_SELF_CREATORS = {"load_looker_campaigns.py",
                            "log_campaign_performance.py",
                            "make_briefs.py"}

    def test_no_new_tool_creates_its_own_table(self):
        """The schema is the single source. A tool that creates a table
        hides it from every machine that has not run that tool -- which is
        how 386 scored votes were written, reported and lost in an hour."""
        import glob
        import re
        offenders = []
        for path in glob.glob(os.path.join(ROOT, "tools", "*.py")):
            name = os.path.basename(path)
            if name in self.LEGACY_SELF_CREATORS:
                continue
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if re.search(r"CREATE TABLE", src, re.I):
                offenders.append(name)
        self.assertEqual(offenders, [],
                         "these create tables outside the schema: {0}".format(offenders))

    def test_every_derived_state_tool_is_run_by_a_workflow(self):
        import glob
        wf = ""
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            with open(path, encoding="utf-8") as fh:
                wf += fh.read()
        for tool in ("sp_score.py", "pull_devolved_profiles.py",
                     "ni_committees.py", "backfill_pq_links.py"):
            self.assertIn(tool, wf,
                          "{0} writes state no workflow ever produces".format(tool))
