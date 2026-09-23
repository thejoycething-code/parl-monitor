"""Coverage watch and store lineage (Christopher, 2026-09-04: "What else
needs building to ensure we're properly tracking").

Both tools here exist because of one incident. On 2026-09-03 the UPR
monthly harvested 1,218 new recommendations, published them and
committed its sidecar; three hours later a hand push from a laptop whose
store predated that run overwrote the asset and the pointer. Both runs
were green, nothing was alerted, and the loss was found a day later only
because someone measured how stale each source was.

tools/db_state.py refuses that push now. tools/coverage.py notices when
it happens anyway.
"""

import datetime
import importlib.util
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cov = _load("coverage")
TODAY = datetime.date(2026, 9, 4)


def store(pipelines=(), feeds=()):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE source_runs (source TEXT PRIMARY KEY, "
                 "last_run TEXT NOT NULL, run_id TEXT, note TEXT)")
    for name, last in pipelines:
        conn.execute("INSERT INTO source_runs (source, last_run) VALUES (?,?)",
                     (name, last))
    for table, col, last in feeds:
        conn.execute("CREATE TABLE {0} (x TEXT, {1} TEXT)".format(table, col))
        conn.execute("INSERT INTO {0} (x, {1}) VALUES ('r', ?)".format(
            table, col), (last,))
    conn.commit()
    return conn


class PipelineTests(unittest.TestCase):
    def test_a_pipeline_that_stopped_running_is_overdue(self):
        conn = store(pipelines=[("Holyrood weekly", "2026-08-01")])
        overdue = cov.check(conn, today=TODAY, log=lambda *a: None)
        self.assertTrue(any("Holyrood weekly" in o for o in overdue))

    def test_a_pipeline_inside_its_cadence_is_not(self):
        conn = store(pipelines=[("Holyrood weekly", "2026-09-01")])
        overdue = cov.check(conn, today=TODAY, log=lambda *a: None)
        self.assertEqual([o for o in overdue if "Holyrood weekly" in o], [])

    def test_a_paused_pipeline_is_never_reported_as_broken(self):
        """UN was paused on purpose on 2026-08-17. A pause that reads as a
        failure trains people to ignore the alert; a pause nobody records
        reads as health."""
        conn = store()
        lines = []
        cov.check(conn, today=TODAY, log=lines.append)
        self.assertNotIn("UN calls weekly", cov.PIPELINES)
        self.assertIn("UN calls weekly", cov.PAUSED)
        self.assertTrue(any("PAUSED" in ln for ln in lines))

    def test_the_monthly_cadence_is_not_judged_weekly(self):
        conn = store(pipelines=[("UPR monthly", "2026-08-20")])
        overdue = cov.check(conn, today=TODAY, log=lambda *a: None)
        self.assertEqual([o for o in overdue if "UPR monthly" in o], [])


class ClobberTests(unittest.TestCase):
    """The check that would have caught 3 September.

    Cadence alone cannot: the UPR pipeline had run 24 hours earlier, and
    its data was 19 days old. Each signal on its own looked fine.
    """

    def test_a_fresh_run_over_stale_data_is_flagged_as_lost_work(self):
        conn = store(pipelines=[("UPR monthly", "2026-09-03")],
                     feeds=[("upr_recommendations", "captured_at",
                             "2026-08-16")])
        overdue = cov.check(conn, today=TODAY, log=lambda *a: None)
        self.assertTrue(any("stored nothing, or its store was overwritten" in o
                            for o in overdue),
                        "a green run over 19-day-old data must be flagged")

    def test_a_fresh_run_with_fresh_data_is_not_flagged(self):
        conn = store(pipelines=[("UPR monthly", "2026-09-03")],
                     feeds=[("upr_recommendations", "captured_at",
                             "2026-09-03")])
        overdue = cov.check(conn, today=TODAY, log=lambda *a: None)
        self.assertEqual(overdue, [])

    def test_a_few_quiet_days_inside_a_running_pipeline_are_fine(self):
        """Feeds go quiet for ordinary reasons -- recess, no new items. The
        flag is for data OLDER than the run by a week, not for a feed that
        simply had nothing to say on the day."""
        conn = store(pipelines=[("Holyrood weekly", "2026-09-03")],
                     feeds=[("sp_items", "last_seen", "2026-09-01"),
                            ("sp_divisions", "last_seen", "2026-08-30")])
        overdue = cov.check(conn, today=TODAY, log=lambda *a: None)
        self.assertEqual(overdue, [])

    def test_an_overdue_pipeline_is_not_double_reported_as_a_clobber(self):
        conn = store(pipelines=[("EU weekly", "2026-07-01")],
                     feeds=[("eu_texts", "last_seen", "2026-07-01")])
        overdue = cov.check(conn, today=TODAY, log=lambda *a: None)
        self.assertEqual(len([o for o in overdue if "overwritten" in o]), 0)


class RecessTests(unittest.TestCase):
    def test_freshness_never_reads_the_date_of_the_business(self):
        """A chamber in recess holds no divisions. Judging coverage by the
        date of the last division would call every summer a failure, so
        every column here records when we last SAW the source."""
        for _table, col, _days, _grace, _why in cov.FEEDS:
            self.assertIn(col, ("last_seen", "captured_at"),
                          "{0} is a business date, not a sighting".format(col))

    def test_write_once_feeds_are_listed_but_never_fail_the_run(self):
        named = set(cov.ONCE_EVER)
        self.assertIn("ni_sittings", named)
        self.assertEqual(named & {f[0] for f in cov.FEEDS}, set(),
                         "a feed cannot be both cadence-checked and "
                         "write-once")


class ScopeTests(unittest.TestCase):
    """WHO WATCHES THE WATCHER'S OWN SCOPE.

    coverage.py only knows about sources somebody remembered to list in
    it, which is the same failure it exists to catch: EU weekly was
    missing from the failure alert from the day it was written, and
    Member profiles -- service history, party spells, contacts for every
    chamber -- was missing from coverage.py itself. A new collector added
    without a line here would be invisible all over again.

    Modelled on the EU triage coverage test, which catches the same class
    of omission for the judge.
    """

    @staticmethod
    def sighting_tables():
        from src import db as schema
        conn = sqlite3.connect(":memory:")
        schema.init_db(conn)
        out = []
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE "
                                    "type='table' ORDER BY name"):
            cols = {c[1] for c in conn.execute(
                "PRAGMA table_info({0})".format(name))}
            if cols & {"last_seen", "captured_at"}:
                out.append(name)
        conn.close()
        return out

    def test_every_source_table_is_watched_or_explained(self):
        known = ({f[0] for f in cov.FEEDS} | set(cov.ONCE_EVER)
                 | set(cov.EXEMPT))
        missing = sorted(set(self.sighting_tables()) - known)
        self.assertEqual(missing, [],
                         "these carry a sighting column but are neither "
                         "watched nor explained: {0}".format(missing))

    def test_every_exemption_states_a_reason(self):
        for table, reason in cov.EXEMPT.items():
            self.assertGreater(len(reason), 40,
                               "{0} is exempt without a real reason".format(
                                   table))
            self.assertNotIn(table, {f[0] for f in cov.FEEDS},
                             "{0} cannot be both watched and exempt".format(
                                 table))

    def test_every_workflow_that_publishes_is_a_watched_pipeline(self):
        """A workflow that writes the store but is not a pipeline here has
        no heartbeat expectation, so it can stop dead unnoticed."""
        import glob
        import os as _os
        writers = []
        for path in glob.glob(_os.path.join(ROOT, ".github", "workflows",
                                            "*.yml")):
            src = open(path, encoding="utf-8").read()
            if "db_state.py --push" not in src:
                continue
            name = src.split("name:", 1)[1].split("\n", 1)[0].strip()
            writers.append(name)
        unwatched = sorted(set(writers) - set(cov.PIPELINES)
                           - set(cov.PAUSED) - set(cov.ON_DEMAND))
        self.assertEqual(unwatched, [],
                         "these publish the store but no one expects a "
                         "heartbeat from them: {0}".format(unwatched))

    def test_an_on_demand_workflow_states_why_it_has_no_cadence(self):
        for name, why in cov.ON_DEMAND.items():
            self.assertGreater(len(why), 40, name)
            self.assertNotIn(name, cov.PIPELINES,
                             "{0} cannot be both scheduled and on-demand"
                             .format(name))

    def test_every_watched_pipeline_is_alerted_on(self):
        """coverage.py noticing is no use if nobody is told."""
        alert = open(os.path.join(ROOT, ".github", "workflows", "alert.yml"),
                     encoding="utf-8").read()
        for name in list(cov.PIPELINES) + ["Coverage watch"]:
            self.assertIn('"{0}"'.format(name), alert,
                          "{0} is not watched by the failure alert".format(
                              name))


class LineageGuardTests(unittest.TestCase):
    """db_state.py --push refuses to publish over a store it did not pull."""

    def setUp(self):
        self.db = _load("db_state")

    def test_no_record_of_a_pull_refuses(self):
        self.db.published_sha = lambda: "beef" * 16
        self.db.PULLED = os.path.join(ROOT, "tests", "fixtures",
                                      "no-such-marker")
        self.db.sys.argv = ["db_state.py", "--push"]
        self.assertFalse(self.db.check_lineage())

    def test_a_moved_store_refuses(self):
        import tempfile
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as handle:
            handle.write("aaaa" * 16 + "\n")
        self.db.PULLED = path
        self.db.published_sha = lambda: "bbbb" * 16
        self.db.sys.argv = ["db_state.py", "--push"]
        self.assertFalse(self.db.check_lineage())
        os.unlink(path)

    def test_a_sha_this_copy_published_earlier_is_still_in_lineage(self):
        """A push writes the new sha locally, but the sidecar reaches
        origin only when the commit lands. Comparing against the single
        latest sha refused an ordinary push-then-push-again."""
        import tempfile
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as handle:
            handle.write("dddd" * 16 + "\n" + "eeee" * 16 + "\n")
        self.db.PULLED = path
        self.db.published_sha = lambda: "dddd" * 16   # origin still behind
        self.db.sys.argv = ["db_state.py", "--push"]
        self.assertTrue(self.db.check_lineage())
        os.unlink(path)

    def test_in_step_publishes(self):
        import tempfile
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as handle:
            handle.write("cccc" * 16 + "\n")
        self.db.PULLED = path
        self.db.published_sha = lambda: "cccc" * 16
        self.db.sys.argv = ["db_state.py", "--push"]
        self.assertTrue(self.db.check_lineage())
        os.unlink(path)

    def test_force_overrides_but_says_what_it_discards(self):
        self.db.published_sha = lambda: "bbbb" * 16
        self.db.sys.argv = ["db_state.py", "--push", "--force"]
        self.assertTrue(self.db.check_lineage())
        src = open(os.path.join(ROOT, "tools", "db_state.py"),
                   encoding="utf-8").read()
        self.assertIn("DISCARDS", src)

    def test_a_git_failure_warns_rather_than_blocking_every_workflow(self):
        """The guard must not become a single point of failure: if git
        cannot answer, say so loudly and let the run publish."""
        self.db.published_sha = lambda: None
        self.db.sys.argv = ["db_state.py", "--push"]
        self.assertTrue(self.db.check_lineage())

    def test_the_heartbeat_is_stamped_before_the_sha_is_taken(self):
        """It travels with the bytes it describes, or it describes a store
        that was never published."""
        src = open(os.path.join(ROOT, "tools", "db_state.py"),
                   encoding="utf-8").read()
        body = src[src.index("def push():"):]
        self.assertLess(body.index("stamp_heartbeat()"),
                        body.index("sha256(DB)"))


class OnceEverIsMeasuredNotAssumedTests(unittest.TestCase):
    """Whether a table is a heartbeat or once-ever depends on ONE thing: does
    its writer re-stamp a sighting column on every run. Guessing produces a
    permanent false alarm, and a permanent false alarm is worse than none --
    people learn to scroll past it.

    eu_judgments spent eleven days reporting LOST WORK while nothing was lost.
    tools/eu_courts.py builds `known` from the stored item ids and skips
    anything it already holds, so last_seen can never move for a judgment
    already in the table.
    """

    def test_eu_judgments_is_once_ever_and_not_a_feed(self):
        self.assertIn("eu_judgments", cov.ONCE_EVER)
        self.assertNotIn("eu_judgments", [f[0] for f in cov.FEEDS])

    def test_it_is_out_of_the_clobber_check_too(self):
        """PIPELINE_FEEDS drives "ran but did not land". A table written once
        per item cannot pass that during a quiet month."""
        for pipeline, tables in cov.PIPELINE_FEEDS.items():
            self.assertNotIn("eu_judgments", tables, pipeline)

    def test_no_table_is_both_a_feed_and_once_ever(self):
        """The two lists mean opposite things; a table in both would be
        alarmed on and excused at the same time."""
        feeds = {f[0] for f in cov.FEEDS}
        self.assertEqual(feeds & set(cov.ONCE_EVER), set())

    def test_no_once_ever_table_drives_the_clobber_check(self):
        """The general form of the eu_judgments bug, so the next one is
        caught by a red test rather than by eleven days of crying wolf."""
        for pipeline, tables in cov.PIPELINE_FEEDS.items():
            for table in tables:
                self.assertNotIn(
                    table, cov.ONCE_EVER,
                    "{0} is once-ever and cannot support the clobber check "
                    "for {1}".format(table, pipeline))


if __name__ == "__main__":
    unittest.main()


class EmptyFeedTests(unittest.TestCase):
    """17 Sept 2026: five EU tables were emptied by the 9 Sept store rebuild and
    the watch printed "NO DATA" for eight days without ever calling it overdue.
    An empty watched feed is now a fault unless a human has excused it."""

    def _conn(self, rows):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE source_runs (source TEXT PRIMARY KEY, "
                     "last_run TEXT NOT NULL, run_id TEXT, note TEXT)")
        conn.execute("CREATE TABLE eu_texts (x TEXT, last_seen TEXT)")
        for r in rows:
            conn.execute("INSERT INTO eu_texts (x, last_seen) VALUES ('r', ?)", (r,))
        conn.commit()
        return conn

    def _check(self, conn, allowed=None):
        feeds, empt = cov.FEEDS, cov.ALLOWED_EMPTY
        cov.FEEDS = [("eu_texts", "last_seen", 7, 3, "EP adopted texts")]
        cov.ALLOWED_EMPTY = allowed if allowed is not None else {}
        lines = []
        try:
            return cov.check(conn, today=TODAY, log=lines.append), lines
        finally:
            cov.FEEDS, cov.ALLOWED_EMPTY = feeds, empt

    def test_a_watched_feed_with_no_rows_is_overdue(self):
        overdue, lines = self._check(self._conn([]))
        self.assertTrue(any("eu_texts" in o and "NO ROWS" in o for o in overdue), overdue)
        self.assertTrue(any("NO ROWS AT ALL" in ln and "OVERDUE" in ln for ln in lines), lines)

    def test_a_feed_excused_by_a_human_stays_quiet(self):
        overdue, lines = self._check(self._conn([]), allowed={"eu_texts": "no plenary since July"})
        self.assertEqual([o for o in overdue if "eu_texts" in o], [])
        self.assertTrue(any("EMPTY BY DESIGN" in ln for ln in lines), lines)

    def test_a_populated_feed_is_judged_on_age_as_before(self):
        overdue, _ = self._check(self._conn(["2026-09-03"]))
        self.assertEqual([o for o in overdue if "eu_texts" in o], [])
        overdue, _ = self._check(self._conn(["2026-07-01"]))
        self.assertTrue(any("eu_texts" in o and "last saw data" in o for o in overdue), overdue)


class WriteOnceEmptyTests(unittest.TestCase):
    """A write-once feed cannot be judged on cadence: a quiet plenary month is
    not a fault. An EMPTY one can be, and must be -- eu_divisions lost 21 roll
    calls in the 9 Sept rebuild and this section printed "? days ago"."""

    def _conn(self, tables):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE source_runs (source TEXT PRIMARY KEY, "
                     "last_run TEXT NOT NULL, run_id TEXT, note TEXT)")
        for name, rows in tables.items():
            conn.execute("CREATE TABLE {0} (x TEXT, last_seen TEXT)".format(name))
            for r in rows:
                conn.execute("INSERT INTO {0} (x, last_seen) VALUES ('r', ?)".format(name), (r,))
        conn.commit()
        return conn

    def _check(self, conn, once, allowed=None):
        feeds, oe, empt = cov.FEEDS, cov.ONCE_EVER, cov.ALLOWED_EMPTY
        cov.FEEDS, cov.ONCE_EVER = [], once
        cov.ALLOWED_EMPTY = allowed or {}
        lines = []
        try:
            return cov.check(conn, today=TODAY, log=lines.append), lines
        finally:
            cov.FEEDS, cov.ONCE_EVER, cov.ALLOWED_EMPTY = feeds, oe, empt

    def test_an_emptied_write_once_feed_is_overdue(self):
        conn = self._conn({"eu_divisions": []})
        overdue, lines = self._check(conn, {"eu_divisions": "one row per roll call"})
        self.assertTrue(any("eu_divisions" in o and "NO ROWS" in o for o in overdue), overdue)

    def test_a_quiet_but_populated_write_once_feed_never_fails(self):
        conn = self._conn({"eu_divisions": ["2026-01-05"]})       # eight months old
        overdue, _ = self._check(conn, {"eu_divisions": "one row per roll call"})
        self.assertEqual([o for o in overdue if "eu_divisions" in o], [], "a quiet month is not a fault")

    def test_the_paused_un_pipeline_is_not_reported_as_wiped(self):
        conn = self._conn({"un_votes": []})
        overdue, _ = self._check(conn, {"un_votes": "UN pipeline is paused"})
        self.assertEqual(overdue, [])

    def test_the_wipe_is_reported_even_in_quiet_mode(self):
        conn = self._conn({"eu_divisions": []})
        feeds, oe = cov.FEEDS, cov.ONCE_EVER
        cov.FEEDS, cov.ONCE_EVER = [], {"eu_divisions": "one row per roll call"}
        lines = []
        try:
            overdue = cov.check(conn, today=TODAY, log=lines.append, quiet=True)
        finally:
            cov.FEEDS, cov.ONCE_EVER = feeds, oe
        self.assertTrue(any("eu_divisions" in o for o in overdue), overdue)
