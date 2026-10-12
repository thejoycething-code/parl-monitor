"""The store as a release asset (Christopher's decision, 2026-08-24).

The store hit 88MB against GitHub's 100MB HARD push limit, growing ~15MB
per build sprint. It is derived state, so it moved out of git into a
release asset. These tests pin the properties that make that safe.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import db_state

WORKFLOWS = os.path.join(ROOT, ".github", "workflows")


def workflow(name):
    with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as fh:
        return fh.read()


class WorkflowWiringTests(unittest.TestCase):
    STATEFUL = ("ni-weekly.yml", "sp-weekly.yml", "sd-weekly.yml",
                "sunday-pull.yml", "monday-publish.yml", "upr-monthly.yml",
                "backfill.yml", "score-stance.yml", "member-profiles.yml",
                "de-weekly.yml", "prov-weekly.yml")

    def test_every_stateful_workflow_pulls_and_pushes(self):
        for name in self.STATEFUL:
            text = workflow(name)
            self.assertIn("db_state.py --pull", text, name + " must pull")
            self.assertIn("db_state.py --push", text, name + " must push")

    def test_pull_precedes_push(self):
        for name in self.STATEFUL:
            text = workflow(name)
            self.assertLess(text.index("--pull"), text.index("--push"), name)

    def test_no_workflow_stages_the_store_itself(self):
        """`git add data/` is fine once the store is ignored, but naming the
        file explicitly would re-track it. sp-weekly used to."""
        for name in self.STATEFUL:
            text = workflow(name)
            self.assertNotIn("git add data/parl-monitor.db\n", text, name)
            self.assertNotIn("data/parl-monitor.db data/raw", text, name)

    def test_one_writer_at_a_time_is_enforced_repo_wide(self):
        """The release asset has no locking of its own; the shared
        concurrency group IS the lock. Without it two weeklies could
        interleave pull/push and silently lose a week's work."""
        for name in self.STATEFUL:
            text = workflow(name)
            self.assertIn("group: parl-monitor-state", text, name)
            self.assertIn("cancel-in-progress: false", text, name)

    def test_the_stateless_workflow_is_left_alone(self):
        """un-calls-weekly reads a page and sends a message; it never opens
        the store, so wiring it in would be noise."""
        self.assertNotIn("db_state.py", workflow("un-calls-weekly.yml"))


class BootstrapGuardTests(unittest.TestCase):
    def test_no_asset_with_a_working_copy_is_a_bootstrap(self):
        # Its own working copy, not the real store: data/parl-monitor.db is
        # gitignored and lives only on machines that have pulled it, so in
        # a fresh clone the test failed for want of a file it never meant
        # to test (found 2026-10-12).
        import tempfile
        real = db_state.DB
        with tempfile.TemporaryDirectory() as tmp:
            try:
                db_state.DB = os.path.join(tmp, "parl-monitor.db")
                with open(db_state.DB, "wb") as fh:
                    fh.write(b"SQLite format 3\x00")
                self.assertEqual(db_state._no_asset_yet(), 0,
                                 "the working copy exists, so the first run "
                                 "should proceed and publish it")
            finally:
                db_state.DB = real

    def test_no_asset_and_no_working_copy_is_fatal(self):
        real = db_state.DB
        try:
            db_state.DB = os.path.join(ROOT, "data", "does-not-exist.db")
            self.assertEqual(db_state._no_asset_yet(), 1,
                             "untracking before an asset exists must fail "
                             "loudly, never build an empty store")
        finally:
            db_state.DB = real


class SidecarTests(unittest.TestCase):
    """The sidecar is what keeps provenance after the bytes leave git."""

    def test_sidecar_records_size_and_digest_when_present(self):
        if not os.path.exists(db_state.SIDECAR):
            self.skipTest("no store published yet")
        with open(db_state.SIDECAR, encoding="utf-8") as fh:
            meta = json.load(fh)
        self.assertIn("sha256", meta)
        self.assertIn("bytes", meta)
        self.assertEqual(len(meta["sha256"]), 64)

    def test_sidecar_is_not_ignored(self):
        """Check the RULES, not the file text: .gitignore's comment names the
        sidecar precisely to say it must never be ignored, and a naive
        substring search reads that explanation as a violation."""
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            rules = [l.strip() for l in fh
                     if l.strip() and not l.lstrip().startswith("#")]
        for rule in rules:
            self.assertNotIn("parl-monitor.db.json", rule,
                             "the sidecar is the provenance record and MUST "
                             "be committed")



class TableCountTests(unittest.TestCase):
    """A rebuilt store that lost a whole table (pq_link, 2026-09-09) must not publish
    quietly again. The sidecar carries per-table counts; the push compares."""

    def test_a_table_at_zero_that_had_rows_is_lost(self):
        lost, shrunk = db_state.compare_counts({"pq_link": 5117, "mp_events": 100}, {"pq_link": 0, "mp_events": 120})
        self.assertEqual(lost, [("pq_link", 5117)])
        self.assertEqual(shrunk, [])

    def test_a_dropped_table_is_lost_too(self):
        lost, _ = db_state.compare_counts({"pq_link": 5117}, {})
        self.assertEqual(lost, [("pq_link", 5117)])

    def test_halving_a_real_table_warns_and_a_tiny_one_does_not(self):
        lost, shrunk = db_state.compare_counts({"big": 1000, "tiny": 4}, {"big": 400, "tiny": 1})
        self.assertEqual(lost, [])
        self.assertEqual(shrunk, [("big", 1000, 400)])

    def test_new_and_grown_tables_are_nobodys_business(self):
        self.assertEqual(db_state.compare_counts({"a": 10}, {"a": 11, "b": 5}), ([], []))
        self.assertEqual(db_state.compare_counts({"a": 0}, {"a": 0}), ([], []))

    def test_table_counts_reads_every_table_read_only(self):
        import sqlite3
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.db")
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE x (a)"); conn.execute("CREATE TABLE y (a)")
            conn.executemany("INSERT INTO x VALUES (?)", [(1,), (2,)])
            conn.commit(); conn.close()
            self.assertEqual(db_state.table_counts(path), {"x": 2, "y": 0})

    def test_check_counts_refuses_a_loss_unless_accepted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db_path, side = os.path.join(tmp, "s.db"), os.path.join(tmp, "s.db.json")
            import sqlite3
            conn = sqlite3.connect(db_path); conn.execute("CREATE TABLE gone (a)"); conn.commit(); conn.close()
            with open(side, "w") as fh:
                json.dump({"tables": {"gone": 9}}, fh)
            old = db_state.DB, db_state.SIDECAR
            db_state.DB, db_state.SIDECAR = db_path, side
            try:
                lines = []
                ok, counts = db_state.check_counts(log=lines.append)
                self.assertFalse(ok)
                self.assertTrue(any("TABLES EMPTIED" in l for l in lines))
                ok, _ = db_state.check_counts(accept_loss=True, log=lambda *_a: None)
                self.assertTrue(ok)
                with open(side, "w") as fh:
                    json.dump({"sha256": "x"}, fh)             # no counts yet: bootstrap, never refuse
                ok, counts = db_state.check_counts(log=lambda *_a: None)
                self.assertTrue(ok)
                self.assertEqual(counts, {"gone": 0})
            finally:
                db_state.DB, db_state.SIDECAR = old

    def test_the_push_checks_counts_after_lineage_and_before_upload(self):
        with open(os.path.join(ROOT, "tools", "db_state.py"), encoding="utf-8") as fh:
            src = fh.read()
        body = src[src.index("def push():"):src.index("def main():")]
        self.assertLess(body.index("check_lineage()"), body.index("check_counts("))
        self.assertLess(body.index("check_counts("), body.index("swap_in_asset("))
        self.assertIn('"tables": counts', body)


class CommitLabelTests(unittest.TestCase):
    """Each workflow must label its own commits.

    sd-weekly was sed-derived from ni-weekly and kept its commit message, so
    Senedd run 32721990336 -- the very run that bootstrapped the release
    asset -- landed as "NI weekly: 2026-08-24T11:30Z". Harmless to the data,
    corrosive to the audit trail: the history said NI touched the store when
    Wales did. The derivation shortcut is still right (it fixed sp-weekly's
    day-one double miss); this is the guard that makes it safe.
    """

    EXPECTED = {
        "ni-weekly.yml": "NI weekly",
        "sd-weekly.yml": "Senedd weekly",
        "sp-weekly.yml": "Holyrood weekly",
        "sunday-pull.yml": "Sunday pull",
        "monday-publish.yml": "Monday publish",
        "upr-monthly.yml": "UPR monthly",
        "backfill.yml": "Historic backfill",
        "score-stance.yml": "Stance scoring",
        "member-profiles.yml": "Member profiles",
    }

    def test_each_workflow_names_itself_in_its_commit_message(self):
        for name, label in self.EXPECTED.items():
            text = workflow(name)
            line = next((l for l in text.splitlines()
                         if "git commit -m" in l), None)
            self.assertIsNotNone(line, name + " has no commit step")
            self.assertIn(label, line,
                          "{0} commits as something else: {1}".format(
                              name, line.strip()))

    def test_no_workflow_borrows_another_legislature_label(self):
        others = {"ni-weekly.yml": ("Senedd", "Holyrood"),
                  "sd-weekly.yml": ("NI weekly", "Holyrood"),
                  "sp-weekly.yml": ("NI weekly", "Senedd")}
        for name, wrong in others.items():
            line = next(l for l in workflow(name).splitlines()
                        if "git commit -m" in l)
            for label in wrong:
                self.assertNotIn(label, line, name)

class BackfillWorkflowTests(unittest.TestCase):
    """The backfill re-sweeps a term across years. It must stay MANUAL: on a
    schedule it would re-walk the whole corpus weekly for nothing, and it
    holds the state lock while doing it."""

    def test_manual_only(self):
        text = workflow("backfill.yml")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("cron:", text)

    def test_it_does_not_score_stance(self):
        """Scoring costs money and is Christopher's call; a dispatchable
        workflow must not be able to spend it."""
        text = workflow("backfill.yml")
        self.assertNotIn("score_stance", text)
        self.assertNotIn("run_weekly.py", text)


class ScoreStanceWorkflowTests(unittest.TestCase):
    """Scoring spends money, so the workflow that does it must be manual,
    must not leave the key on disk, and must not publish a store it did not
    change (a dry run spends nothing and should write nothing)."""

    def test_manual_only(self):
        text = workflow("score-stance.yml")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("cron:", text)

    def test_the_key_is_removed_afterwards(self):
        text = workflow("score-stance.yml")
        self.assertIn("rm -f config/secrets.yaml", text)
        self.assertIn("if: always()", text)

    def test_a_dry_run_publishes_nothing(self):
        text = workflow("score-stance.yml")
        self.assertIn("inputs.dry_run != true", text)



class PipefailTests(unittest.TestCase):
    """A tool that crashes must fail its step.

    Every workflow pipes its tools through `tee` for the health summary, and
    a pipeline's exit status is the LAST command's -- so `python3 x.py | tee
    log` went GREEN when x.py died. That is how the 2026-08-24 backfill run
    reported success while its questions sweep had crashed on a bad argument.
    """

    def test_every_piping_workflow_sets_pipefail(self):
        import glob
        for path in sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml"))):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if "| tee" not in text:
                continue
            self.assertIn("pipefail", text,
                          os.path.basename(path) + " pipes through tee, so a "
                          "crashed tool would report success")




class PipefailTests(unittest.TestCase):
    """A tool that crashes must fail its step.

    Every workflow pipes its tools through `tee` for the health summary, and
    a pipeline's exit status is the LAST command's -- so `python3 x.py | tee
    log` went GREEN when x.py died. That is how the 2026-08-24 backfill run
    reported success while its questions sweep had crashed on a bad argument.
    """

    def test_every_piping_workflow_sets_pipefail(self):
        import glob
        for path in sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml"))):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if "| tee" not in text:
                continue
            self.assertIn("pipefail", text,
                          os.path.basename(path) + " pipes through tee, so a "
                          "crashed tool would report success")


class FailureAlertTests(unittest.TestCase):
    """Until 2026-08-24 nothing told anyone a workflow had failed: a broken
    Sunday pull would have produced a stale Monday edition in silence.

    The alert is ONE watcher (alert.yml, workflow_run) rather than a step in
    each workflow, and that is the point. A per-workflow step would have put
    a Slack token into the devolved weeklies -- whose separation rule is
    structural precisely because they hold no Slack credential at all.
    """

    WATCHED = ("Sunday pull", "Monday publish", "NI Assembly weekly",
               "Holyrood weekly", "Senedd weekly", "UPR monthly",
               "Historic backfill", "Score stance", "Germany weekly",
               "Provinces weekly")

    def test_the_watcher_exists_and_fires_on_failure_and_cancellation(self):
        """A job that hits timeout-minutes is reported as 'cancelled' (19 Sept
        2026: the EU weekly twice); a watcher keyed on 'failure' alone slept."""
        text = workflow("alert.yml")
        self.assertIn("workflow_run:", text)
        self.assertIn("conclusion == 'failure'", text)
        self.assertIn("conclusion == 'cancelled'", text)
        self.assertIn("FAILED_CONCLUSION", text)
        self.assertIn("alert_failure.py", text)

    def test_a_cancelled_run_is_named_as_such_in_the_dm(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "alert_failure", os.path.join(ROOT, "tools", "alert_failure.py"))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        text = mod.message({"FAILED_WORKFLOW": "EU weekly", "FAILED_CONCLUSION": "cancelled",
                            "FAILED_RUN_URL": "https://example/run/1"})
        self.assertIn("*EU weekly* was cancelled", text)
        self.assertIn("every later step was skipped", text)
        plain = mod.message({"FAILED_WORKFLOW": "EU weekly", "FAILED_CONCLUSION": "failure"})
        self.assertIn("*EU weekly* failed.", plain)

    def test_it_watches_every_stateful_workflow(self):
        text = workflow("alert.yml")
        for name in self.WATCHED:
            self.assertIn('"{0}"'.format(name), text,
                          name + " unwatched: its failures would be silent")

    # Workflows that must hold NO Slack credential. The Westminster
    # publishing chain (sunday-pull, monday-publish) legitimately does --
    # sunday-pull writes a full secrets file, monday-publish posts the
    # edition -- and un-calls-weekly exists to send a message. The rule
    # protects the DEVOLVED watching briefs, whose separation is structural,
    # and the manual state tools, which have no reason to speak.
    NO_SLACK = ("ni-weekly.yml", "sp-weekly.yml", "sd-weekly.yml",
                "backfill.yml", "score-stance.yml", "upr-monthly.yml",
                "member-profiles.yml")
    # prov-weekly.yml left this list on 9 October 2026: it now writes the
    # provinces edition and DMs it to Christopher, as ie-weekly.yml does
    # (tests/test_prov_schedule.py keeps the token to that one step). Its
    # failure alert is still the watcher's, never a step of its own.

    def test_the_watching_briefs_hold_no_slack_credential(self):
        """The property the watcher exists to preserve: had the alert been a
        step in each workflow, all three devolved weeklies would now carry a
        Slack token, and the separation would stop being structural."""
        for name in self.NO_SLACK:
            text = workflow(name)
            for banned in ("SLACK_BOT_TOKEN", "slack_bot_token"):
                self.assertNotIn(banned, text, name)

    def test_the_alert_never_fails_the_job(self):
        with open(os.path.join(ROOT, "tools", "alert_failure.py"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("except Exception", text)
        self.assertIn("return 0", text)

    def test_message_names_the_FAILED_run_not_the_watcher(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import alert_failure
        msg = alert_failure.message({
            "GITHUB_WORKFLOW": "Failure alert",
            "FAILED_WORKFLOW": "Sunday pull",
            "FAILED_RUN_URL": "https://github.com/o/r/actions/runs/42"})
        self.assertIn("Sunday pull", msg)
        self.assertNotIn("Failure alert", msg)
        self.assertIn("runs/42", msg)

    def test_message_does_not_promise_the_store_was_withheld(self):
        """The publish step runs with if: always(), so partial progress IS
        published. An alert claiming otherwise sends someone looking for a
        rollback that never happened."""
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import alert_failure
        msg = alert_failure.message({"FAILED_WORKFLOW": "x"})
        self.assertNotIn("was not published", msg)
        self.assertIn("upsert", msg)



class LiveAssetTests(unittest.TestCase):
    """Two machines publish the store without a shared lock (the Mac Mini
    runner and GitHub): the release's own digest must be one we have seen."""

    def assets(self, *pairs):
        return [{"name": n, "digest": d} for n, d in pairs]

    def test_our_store_on_the_release_passes(self):
        self.assertTrue(db_state.live_asset_is_ours(["aaa", "bbb"], self.assets((db_state.ASSET, "bbb"))))

    def test_an_uploaded_store_we_never_saw_is_refused(self):
        self.assertFalse(db_state.live_asset_is_ours(["aaa"], self.assets((db_state.ASSET, "ccc"))))

    def test_a_push_part_way_through_is_refused(self):
        self.assertFalse(db_state.live_asset_is_ours(["aaa"], self.assets((db_state.PREV, "aaa"))))
        self.assertFalse(db_state.live_asset_is_ours(
            ["aaa"], self.assets((db_state.ASSET, "aaa"), (db_state.PREV, "zzz"))))

    def test_an_unreadable_release_or_no_asset_does_not_block(self):
        self.assertTrue(db_state.live_asset_is_ours(["aaa"], []))
        with mock.patch.object(db_state, "_release_assets", return_value=None):
            self.assertTrue(db_state.live_asset_is_ours(["aaa"]))

    def test_lineage_checks_the_live_asset_after_the_pointer(self):
        with mock.patch.object(db_state, "published_sha", return_value="aaa"), \
             mock.patch.object(db_state, "held_shas", return_value=["aaa"]), \
             mock.patch.object(db_state, "_release_assets",
                               return_value=self.assets((db_state.ASSET, "ccc"))):
            self.assertFalse(db_state.check_lineage())

if __name__ == "__main__":
    unittest.main()


class CriticalPathTests(unittest.TestCase):
    """Reference-data fetches must stay OFF the Sunday pull.

    Christopher asked directly whether the profile work could break the
    Sunday pull (2026-08-26). It could have, in two ways:

      * sunday-pull's steps are guarded `if: env.SKIP != '1'`, which does
        NOT run after a failure. An enrichment step placed before "Pull for
        the coming week" would have blocked the weekly gather outright the
        first time the Members API hiccupped.
      * the job budget is 60 minutes against a cold pull already measured
        at 40m05s, and the Monday 02:00 retry slot has to finish before the
        03:00 publish. The profile fetch alone measured ~29 minutes.

    So it lives in member-profiles.yml on a free day. These tests keep it
    there.
    """

    REFERENCE_TOOLS = ("pull_service.py", "pull_profiles.py")

    def test_the_sunday_pull_fetches_no_reference_data(self):
        text = workflow("sunday-pull.yml")
        for tool in self.REFERENCE_TOOLS:
            self.assertNotIn(tool, text,
                             tool + " is on the critical path: a failure "
                             "there stops the weekly gather")

    def test_the_publish_fetches_no_reference_data(self):
        """The publish has a Slack post and an Asana task behind it; it must
        not spend its budget on a roster refresh either."""
        text = workflow("monday-publish.yml")
        for tool in self.REFERENCE_TOOLS:
            self.assertNotIn(tool, text)

    def test_the_profiles_workflow_owns_them(self):
        text = workflow("member-profiles.yml")
        for tool in self.REFERENCE_TOOLS:
            self.assertIn(tool, text)

    def test_it_runs_on_a_day_nothing_else_uses(self):
        """Wednesday. Monday has the publish, Thursday the Senedd and UN
        calls, Friday Holyrood, Saturday NI, Sunday the pull."""
        import glob
        import re as _re
        mine = _re.findall(r'cron: "([^"]+)"', workflow("member-profiles.yml"))
        self.assertTrue(mine)
        my_days = {c.split()[-1] for c in mine}
        for path in sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml"))):
            name = os.path.basename(path)
            if name == "member-profiles.yml":
                continue
            with open(path, encoding="utf-8") as fh:
                other = _re.findall(r'cron: "([^"]+)"', fh.read())
            for c in other:
                day = c.split()[-1]
                if day == "*":
                    continue          # monthly, keyed on day-of-month
                self.assertNotIn(day, my_days,
                                 "{0} also runs on day {1}".format(name, day))

    def test_its_timeout_covers_the_measured_duration(self):
        """100 members took 4.5 minutes, so the House is about 29. A
        30-minute cap would have been cut off mid-run."""
        import re as _re
        text = workflow("member-profiles.yml")
        hit = _re.search(r"timeout-minutes:\s*(\d+)", text)
        self.assertIsNotNone(hit)
        self.assertGreaterEqual(int(hit.group(1)), 40)

    def test_a_member_fetch_failure_is_not_fatal(self):
        with open(os.path.join(ROOT, "tools", "pull_profiles.py"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("except Exception", text)
        self.assertIn("previous values retained", text)
        self.assertIn("return 0", text)

    def test_profiles_are_not_archived_into_data_raw(self):
        """~1,950 payloads a week into a git-tracked tree already at 212MB,
        for data that is re-fetchable and quoted nowhere."""
        with open(os.path.join(ROOT, "tools", "pull_profiles.py"),
                  encoding="utf-8") as fh:
            self.assertIn("archive=False", fh.read())


class HealthSummaryTests(unittest.TestCase):
    """The health summary must survive a healthy week.

    The gap tally is `TOTAL=$(grep -ho "N gap(s)" /tmp/*.log | awk ...)`.
    Under `bash -eo pipefail` -- which is what GitHub gives every step --
    that grep exits 1 when NOTHING matches, the pipeline inherits it, the
    assignment inherits that, and -e kills the step.

    Which means the summary failed precisely when every feed reported "no
    gaps". It only ever passed because something was broken: the Senedd
    weekly had 11 bill gaps a run until they were fixed on 2026-08-28, and
    fixing the last one is what turned the step red.
    """

    WORKFLOWS = os.path.join(ROOT, ".github", "workflows")

    def _tallies(self):
        import glob
        out = []
        for path in glob.glob(os.path.join(self.WORKFLOWS, "*.yml")):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if "TOTAL=$(" in text:
                out.append((os.path.basename(path), text))
        return out

    def test_the_gap_tally_survives_a_clean_run(self):
        found = self._tallies()
        self.assertTrue(found, "no gap tally found to check")
        for name, text in found:
            block = text[text.index("TOTAL=$("):]
            block = block[:block.index("\n\n")] if "\n\n" in block else block[:400]
            self.assertIn("|| true", block,
                          "{0}: a week with no gaps kills the step".format(name))

    def test_the_shape_is_right_in_both_directions(self):
        """Guarding it must not also swallow a real gap count."""
        import subprocess
        import tempfile
        script = (
            'set -eo pipefail\n'
            'TOTAL=$({ grep -ho "[0-9]\\+ gap(s)" %s/*.log 2>/dev/null'
            ' || true; } | awk \'{s+=$1} END {print s+0}\')\n'
            'echo "$TOTAL"\n')
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.log"), "w") as fh:
                fh.write("no gaps.\n")
            clean = subprocess.run(["bash", "-c", script % d],
                                   capture_output=True, text=True)
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertEqual(clean.stdout.strip(), "0")
            with open(os.path.join(d, "b.log"), "w") as fh:
                fh.write("3 gap(s) -- printed above.\n")
            dirty = subprocess.run(["bash", "-c", script % d],
                                   capture_output=True, text=True)
            self.assertEqual(dirty.returncode, 0, dirty.stderr)
            self.assertEqual(dirty.stdout.strip(), "3")


class SidecarMustLandTests(unittest.TestCase):
    """A published store whose sidecar never lands is a divergence.

    The publish/commit pairing stopped the commit being SKIPPED. It cannot
    stop it FAILING: on 2026-08-28 the bot's push lost a race with a human
    push, was rejected, and the next run refused the store -- the same
    divergence by another route, after the guard was already in.

    The store is published BEFORE this step, so by the time the push runs
    there is no backing out: it has to land.
    """

    WORKFLOWS = os.path.join(ROOT, ".github", "workflows")

    def _committers(self):
        import glob
        out = []
        for path in glob.glob(os.path.join(self.WORKFLOWS, "*.yml")):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if "db_state.py --push" in text:
                out.append((os.path.basename(path), text))
        return out

    def test_every_sidecar_push_retries(self):
        found = self._committers()
        self.assertGreaterEqual(len(found), 8)
        for name, text in found:
            block = text[text.index("- name: Commit state"):]
            self.assertIn("for attempt in 1 2 3", block,
                          "{0}: a lost push race strands the sidecar".format(name))

    def test_every_sidecar_push_rebases_first(self):
        for name, text in self._committers():
            block = text[text.index("- name: Commit state"):]
            self.assertIn("git pull --rebase", block, name)
            self.assertIn("--autostash", block,
                          "{0}: a dirty tree makes rebase refuse".format(name))


class PlainHttpTests(unittest.TestCase):
    """Nothing this pipeline ingests should arrive in the clear.

    Audited 2026-08-29 at Christopher's request. Every source was already
    https EXCEPT the two Northern Ireland hosts, which had been plain HTTP
    since the feed was written. Both serve the same responses over TLS --
    checked with a real API call, not a root request -- and
    aims.niassembly.gov.uk was already 301-ing to https, so the first
    request went out in the clear for nothing.

    A monitor that reads what a legislature said is exactly the sort of
    traffic where an unencrypted hop lets a network alter the answer.
    """

    def test_no_source_is_fetched_over_plain_http(self):
        import glob
        import re
        offenders = []
        for root in ("src", "tools"):
            for path in glob.glob(os.path.join(ROOT, root, "**", "*.py"),
                                  recursive=True):
                with open(path, encoding="utf-8") as fh:
                    for n, line in enumerate(fh, 1):
                        for m in re.finditer(r"http://[a-z0-9._-]+", line):
                            # An XML NAMESPACE is an identifier, not an
                            # address: ElementTree's Clark notation
                            # "{http://purl.org/dc/elements/1.1/}date" is
                            # matched against tag names and never fetched, so
                            # flagging it would train people to ignore this
                            # check. The brace is what distinguishes it, and
                            # nothing else in this repo fetches a braced URL.
                            # So is an IRI in SPARQL's angle brackets
                            # ("<http://dati.senato.it/osr/>", Italy, 9 October
                            # 2026): the endpoint is fetched over https and the
                            # dataset's own identifiers are http.
                            if line[max(0, m.start() - 1)] in "{<":
                                continue
                            offenders.append("{0}:{1} {2}".format(
                                os.path.relpath(path, ROOT), n, m.group(0)))
        self.assertEqual(offenders, [], "plain-HTTP sources: {0}".format(offenders))

    def test_the_ni_endpoints_are_https(self):
        from src.ingest import niassembly
        self.assertTrue(niassembly.BASE.startswith("https://"))
        self.assertTrue(niassembly.QUESTION_PAGE.startswith("https://"))


class AssetSwapTests(unittest.TestCase):
    """`gh release upload --clobber` deletes then uploads. On 2026-09-09 the upload
    failed and the release was left with NO store, so every workflow died at
    'Fetch the store: no assets to download'. The swap must never leave it empty."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import db_state
        self.ds = db_state
        self.calls = []
        self.assets = {db_state.ASSET: 1}
        self._real = (db_state._rename_asset, db_state._delete_asset, db_state._asset_records,
                      db_state._sleep)
        db_state._sleep = lambda _s: None
        db_state._asset_records = lambda tok=None: [
            {"name": n, "id": i, "state": "uploaded", "digest": ""} for n, i in self.assets.items()]

        def rename(a, b, tok=None):
            self.calls.append(("rename", a, b))
            if a not in self.assets:
                return False
            self.assets[b] = self.assets.pop(a)
            return True

        def delete(name, tok=None):
            self.calls.append(("delete", name))
            self.assets.pop(name, None)
        db_state._rename_asset, db_state._delete_asset = rename, delete

    def tearDown(self):
        (self.ds._rename_asset, self.ds._delete_asset, self.ds._asset_records,
         self.ds._sleep) = self._real

    def test_a_good_upload_leaves_exactly_the_new_store(self):
        def upload():
            self.calls.append(("upload",))
            self.assets[self.ds.ASSET] = 2
        self.assertTrue(self.ds.swap_in_asset(upload, log=lambda *_a: None))
        self.assertEqual(list(self.assets), [self.ds.ASSET])
        self.assertEqual([c[0] for c in self.calls], ["rename", "upload", "delete"])

    def test_a_failed_upload_puts_the_published_store_back(self):
        def upload():
            self.calls.append(("upload",))
            raise RuntimeError("gh upload failed: content length")
        self.assertFalse(self.ds.swap_in_asset(upload, log=lambda *_a: None))
        self.assertEqual(list(self.assets), [self.ds.ASSET], "the release must still hold a store")
        self.assertIn(("rename", self.ds.PREV, self.ds.ASSET), self.calls)

    def test_the_release_is_never_without_a_store_at_any_point(self):
        seen = []

        def upload():
            seen.append(sorted(self.assets))          # what exists mid-upload
            raise RuntimeError("boom")
        self.ds.swap_in_asset(upload, log=lambda *_a: None)
        self.assertEqual(seen, [[self.ds.PREV]] * 3, "a copy must exist during every attempt")
        self.assertEqual(list(self.assets), [self.ds.ASSET])

    def test_a_first_ever_publish_has_nothing_to_keep_aside(self):
        self.assets.clear()

        def upload():
            self.calls.append(("upload",))
            self.assets[self.ds.ASSET] = 1
        self.assertTrue(self.ds.swap_in_asset(upload, log=lambda *_a: None))
        self.assertEqual([c[0] for c in self.calls], ["rename", "upload"])   # no delete


class PublishRaceTests(unittest.TestCase):
    """14 Sept 2026: a laptop push raced the Monday publish; the failure path deleted
    the publish's fresh asset as "a partial upload" and restored the old copy over it."""

    def _run(self, holder_state):
        calls, assets = [], {db_state.ASSET: 1}
        orig = (db_state._rename_asset, db_state._delete_asset, db_state._asset_records)
        sleep, db_state._sleep = db_state._sleep, (lambda _s: None)

        def rename(a, b, tok=None):
            calls.append(("rename", a, b))
            if a not in assets or b in assets:          # GitHub: 422 on a name clash
                return False
            assets[b] = assets.pop(a); return True

        def delete(n, tok=None):
            calls.append(("delete", n)); assets.pop(n, None)

        def upload():
            assets[db_state.ASSET] = 99                  # the name is taken when we fail
            raise RuntimeError("gh upload failed: HTTP 404")
        db_state._rename_asset, db_state._delete_asset = rename, delete
        db_state._asset_records = lambda tok=None: [{"name": n, "id": i, "state": holder_state if n == db_state.ASSET else "uploaded"} for n, i in assets.items()]
        try:
            ok = db_state.swap_in_asset(upload, log=lambda *_a: None)
        finally:
            db_state._rename_asset, db_state._delete_asset, db_state._asset_records = orig
            db_state._sleep = sleep
        return ok, calls, assets

    def test_a_rivals_finished_publish_is_left_standing(self):
        ok, calls, assets = self._run("uploaded")
        self.assertFalse(ok)
        self.assertNotIn(("delete", db_state.ASSET), calls)
        self.assertEqual(assets[db_state.ASSET], 99, "the rival's store stands")
        self.assertIn(db_state.PREV, assets, "ours stays aside for a person")

    def test_our_own_partial_upload_is_cleared_and_the_old_store_restored(self):
        ok, calls, assets = self._run("open")
        self.assertFalse(ok)
        self.assertIn(("delete", db_state.ASSET), calls)
        self.assertEqual(list(assets), [db_state.ASSET])
        self.assertEqual(assets[db_state.ASSET], 1, "the previous copy is back under its name")


class TransientUploadFailureTests(unittest.TestCase):
    """10 and 11 October 2026: an upload 404 on the Mini read as "ANOTHER PUBLISH
    LANDED" although nobody else had published. A failed upload is now retried
    while the release and origin/main show nothing unseen; a store we never
    held under the name is still a race and still refuses at once."""

    OLD, NEW, RIVAL = "old-gz-sha", "new-gz-sha", "rival-gz-sha"

    def _swap(self, uploads, origin="store-sha", before_upload=None, verify=None):
        """uploads: one entry per attempt, "ok" or "404". before_upload(assets,
        attempt) may change the release first (a rival, a lagging listing)."""
        A, P = db_state.GZ_ASSET, db_state.GZ_PREV
        assets = {A: {"digest": self.OLD, "state": "uploaded"}}
        calls, logs, slept, attempt = [], [], [], [0]
        listing = {"stale": None}

        def rename(a, b, tok=None):
            calls.append(("rename", a, b))
            view = listing["stale"] or assets
            if a not in view or b in assets:
                return False
            assets[b] = assets.pop(a); return True

        def delete(n, tok=None):
            calls.append(("delete", n)); assets.pop(n, None)

        def records(tok=None):
            view = listing["stale"] or assets
            return [dict(v, name=n, id=1) for n, v in view.items()]

        def upload():
            attempt[0] += 1
            calls.append(("upload",))
            if before_upload:
                before_upload(assets, attempt[0], listing)
            if uploads[attempt[0] - 1] == "ok":
                assets[A] = {"digest": self.NEW, "state": "uploaded"}
                return
            raise RuntimeError("gh upload failed: HTTP 404: Not Found (https://uploads.github.com/...)")
        with mock.patch.multiple(db_state, _rename_asset=rename, _delete_asset=delete,
                                 _asset_records=records, _sleep=slept.append,
                                 published_sha=lambda: origin):
            ok = db_state.swap_in_asset(upload, log=logs.append, asset=A, prev=P, verify=verify,
                                        held=["store-sha", self.OLD], ours=self.NEW)
        return ok, assets, calls, "\n".join(logs), slept

    def test_a_transient_404_then_success_publishes(self):
        ok, assets, calls, log, slept = self._swap(["404", "ok"])
        self.assertTrue(ok)
        self.assertEqual(assets, {db_state.GZ_ASSET: {"digest": self.NEW, "state": "uploaded"}})
        self.assertEqual(slept, [db_state.UPLOAD_RETRY_DELAYS[0]])
        self.assertIn("upload failed, no other publish seen", log)
        self.assertNotIn("ANOTHER PUBLISH LANDED", log)

    def test_a_persistent_404_fails_cleanly_and_restores_the_keep_aside(self):
        ok, assets, calls, log, slept = self._swap(["404", "404", "404"])
        self.assertFalse(ok)
        self.assertEqual(assets, {db_state.GZ_ASSET: {"digest": self.OLD, "state": "uploaded"}},
                         "the previous store is back under its name, nothing aside")
        self.assertEqual(calls.count(("upload",)), 3)
        self.assertEqual(slept, list(db_state.UPLOAD_RETRY_DELAYS))
        self.assertIn("UPLOAD FAILED, no other publish seen", log)
        self.assertIn("RESTORED", log)
        self.assertNotIn("ANOTHER PUBLISH LANDED", log)

    def test_a_real_race_still_refuses_at_once(self):
        def rival(assets, attempt, _listing):
            assets[db_state.GZ_ASSET] = {"digest": self.RIVAL, "state": "uploaded"}
        ok, assets, calls, log, slept = self._swap(["404"], before_upload=rival)
        self.assertFalse(ok)
        self.assertEqual(calls.count(("upload",)), 1, "no retry over a rival")
        self.assertEqual(slept, [])
        self.assertEqual(assets[db_state.GZ_ASSET]["digest"], self.RIVAL, "the rival's store stands")
        self.assertIn(db_state.GZ_PREV, assets, "ours stays aside for a person")
        self.assertNotIn(("delete", db_state.GZ_ASSET), calls)
        self.assertIn("ANOTHER PUBLISH LANDED", log)
        self.assertIn("never seen here", log)

    def test_an_unseen_sidecar_on_origin_is_a_race(self):
        ok, assets, calls, log, slept = self._swap(["404", "ok"], origin="someone-elses-store")
        self.assertFalse(ok)
        self.assertEqual(calls.count(("upload",)), 1)
        self.assertIn("ANOTHER PUBLISH LANDED", log)
        self.assertIn("origin/main's sidecar", log)

    def test_our_own_old_store_back_under_the_name_is_not_a_rival(self):
        """What happened on the Mini: a GitHub run's pull renamed our .prev back
        (or the listing lagged the rename), so the name held OUR old store."""
        def put_back(assets, attempt, _listing):
            if attempt == 1:
                assets[db_state.GZ_ASSET] = assets.pop(db_state.GZ_PREV)
        ok, assets, calls, log, slept = self._swap(["404", "ok"], before_upload=put_back)
        self.assertTrue(ok)
        self.assertNotIn("ANOTHER PUBLISH LANDED", log)
        self.assertEqual(assets, {db_state.GZ_ASSET: {"digest": self.NEW, "state": "uploaded"}})

    def test_an_upload_that_landed_despite_the_error_is_verified_not_retried(self):
        def lands(assets, attempt, _listing):
            assets[db_state.GZ_ASSET] = {"digest": self.NEW, "state": "uploaded"}
        verified = []
        ok, assets, calls, log, slept = self._swap(["404"], before_upload=lands,
                                                   verify=lambda: verified.append(1) or True)
        self.assertTrue(ok)
        self.assertEqual(verified, [1])
        self.assertEqual(calls.count(("upload",)), 1)
        self.assertNotIn(db_state.GZ_PREV, assets)

    def test_push_passes_the_lineage_to_the_swap(self):
        body = open(os.path.join(ROOT, "tools", "db_state.py"), encoding="utf-8").read()
        self.assertIn("held=held_shas(), ours=gz_digest", body)


class FreshPrevPullTests(unittest.TestCase):
    """9-11 October 2026: a GitHub run's pull renamed .prev back while the Mini
    was uploading. A .prev set aside under 30 minutes ago is read, never renamed."""

    def _pull(self, updated_at):
        assets = {db_state.GZ_PREV: {"name": db_state.GZ_PREV, "updated_at": updated_at,
                                     "url": "u"}}
        renamed, logs = [], []
        def run(cmd, **_kw):             # gh: the release listing, then the download
            out = json.dumps({"assets": list(assets.values())}) if cmd[1] == "api" else ""
            return mock.Mock(returncode=0, stdout=out, stderr="")
        with mock.patch.multiple(db_state, install_merge_driver=lambda: None, have_gh=lambda: True,
                                 token=lambda: None, prefers_gz=lambda: True,
                                 _rename_asset=lambda a, b, tok=None: renamed.append((a, b)) or True,
                                 install_compressed=lambda *a, **k: 0), \
             mock.patch.object(db_state.subprocess, "run", run), \
             mock.patch("builtins.print", logs.append):
            rc = db_state.pull()
        return rc, renamed, "\n".join(map(str, logs))

    def stamp(self, minutes_ago):
        import datetime
        when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
        return when.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_a_fresh_prev_is_taken_read_only(self):
        rc, renamed, log = self._pull(self.stamp(5))
        self.assertEqual(rc, 0)
        self.assertEqual(renamed, [])
        self.assertIn("read-only", log)

    def test_an_old_prev_is_still_recovered(self):
        rc, renamed, log = self._pull(self.stamp(45))
        self.assertEqual(rc, 0)
        self.assertEqual(renamed, [(db_state.GZ_PREV, db_state.GZ_ASSET)])
        self.assertIn("failed part-way", log)

    def test_a_prev_with_no_time_is_taken_read_only(self):
        rc, renamed, _log = self._pull(None)
        self.assertEqual(renamed, [])

    def test_asset_age_reads_updated_at(self):
        import datetime
        now = datetime.datetime(2026, 10, 11, 18, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(db_state.asset_age({"updated_at": "2026-10-11T17:30:00Z"}, now), 1800)
        self.assertIsNone(db_state.asset_age({}, now))


class RefusedDownloadTests(unittest.TestCase):
    """A refused download must never replace the working store (14 Sept 2026: it
    did, and a live re-score had to be paid for twice)."""

    def test_mismatch_leaves_the_working_store_untouched(self):
        import tempfile, hashlib
        d = tempfile.mkdtemp()
        db, got, side, pulled = [os.path.join(d, n) for n in ("s.db", "s.db.download", "s.db.json", ".pulled")]
        open(db, "wb").write(b"working copy"); open(got, "wb").write(b"downloaded bytes")
        json.dump({"sha256": "0" * 64}, open(side, "w"))
        rc = db_state.install_download(got, db=db, sidecar=side, pulled=pulled, log=lambda *_a: None)
        self.assertEqual(rc, 1)
        self.assertEqual(open(db, "rb").read(), b"working copy")
        self.assertTrue(os.path.exists(got))
        self.assertFalse(os.path.exists(pulled))

    def test_a_verified_download_is_installed_and_recorded(self):
        import tempfile, hashlib
        d = tempfile.mkdtemp()
        db, got, side, pulled = [os.path.join(d, n) for n in ("s.db", "s.db.download", "s.db.json", ".pulled")]
        open(db, "wb").write(b"old"); open(got, "wb").write(b"new bytes")
        json.dump({"sha256": hashlib.sha256(b"new bytes").hexdigest()}, open(side, "w"))
        rc = db_state.install_download(got, db=db, sidecar=side, pulled=pulled, log=lambda *_a: None)
        self.assertEqual(rc, 0)
        self.assertEqual(open(db, "rb").read(), b"new bytes")
        self.assertFalse(os.path.exists(got))
        self.assertIn(hashlib.sha256(b"new bytes").hexdigest(), open(pulled).read())


class RetrySlotsAreGuardedTests(unittest.TestCase):
    """A workflow with two or more cron slots must not do the job twice.

    22 September 2026: the four weeklies carried a second slot so a dropped or
    drifted cron still got the week done, and nothing stopped it repeating the
    whole job -- about 250 minutes a month re-collecting. The Monday publish
    and the Sunday pull decide by which cron fired; these four use a gate job
    that skips the work whole, which bills nothing.
    """

    # Two slots that are two different passes, not a retry: the Day sweep runs
    # in the evening and again next morning for text Hansard publishes late,
    # and the Division watch polls the House through a sitting day; the
    # Devolved watch looks back a week in an evening pass and a next-day pass.
    # The US, Ireland and Australia division watches (9 October 2026) poll
    # the same way: each slot looks for divisions the last one could not see.
    DIFFERENT_PASSES = ("day-sweep.yml", "division-watch.yml", "devolved-watch.yml",
                        "us-division-watch.yml", "ie-division-watch.yml",
                        "au-division-watch.yml")

    def _scheduled(self):
        import glob
        import yaml
        out = {}
        for path in sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))):
            doc = yaml.safe_load(open(path, encoding="utf-8"))
            on = doc.get("on", doc.get(True)) or {}
            crons = [c["cron"] for c in (on.get("schedule") or [])] if isinstance(on, dict) else []
            if len(crons) > 1:
                out[os.path.basename(path)] = (doc, len(crons))
        return out

    def test_every_multi_slot_workflow_guards_its_retry(self):
        found = self._scheduled()
        self.assertTrue(found, "no multi-slot workflows found; the glob is wrong")
        for name, (doc, slots) in found.items():
            if name in self.DIFFERENT_PASSES:
                continue
            text = workflow(name)
            gated = "gate:" in text and "needs: gate" in text
            by_cron = "github.event.schedule" in text
            self.assertTrue(gated or by_cron,
                            "{0} has {1} cron slots and no guard: the later slot "
                            "would repeat the whole job".format(name, slots))

    def test_the_gated_weeklies_use_the_gate_job(self):
        # FIVE since 22 September 2026: de-weekly.yml was written with the
        # gate already in it rather than acquiring one after it had billed a
        # month of duplicate collection, which is what the other four did.
        # SIX since 3 October 2026: prov-weekly.yml, gated from the start.
        for name in ("eu-weekly.yml", "sp-weekly.yml", "sd-weekly.yml",
                     "ni-weekly.yml", "de-weekly.yml", "prov-weekly.yml"):
            text = workflow(name)
            self.assertIn("needs: gate", text, name)
            self.assertIn("needs.gate.outputs.go == 'true'", text, name)
            self.assertIn("actions: read", text,
                          name + ": the gate reads this workflow's own runs")
            self.assertIn(name + "/runs", text,
                          name + ": the gate must ask about ITS OWN workflow")
            self.assertIn('select(.id != ${{ github.run_id }})', text,
                          name + ": the gate must not count itself as busy")


class MondayRetrySlotTests(unittest.TestCase):
    """The Monday publish has FOUR crons by design, as retry slots. When the
    primary succeeds, a later slot holds a store that is now stale and the
    lineage guard correctly refuses its push -- which was surfacing as a
    failed run and a real alert every Monday (6, 7, 14 and 21 September all
    have one).

    That noise is not cosmetic. It is how a team learns to ignore alerts, and
    a genuinely failing coverage watch then ran five days unread over 1,218
    UPR recommendations missing since 3 September.
    """

    def _workflow(self):
        return open(os.path.join(ROOT, ".github", "workflows",
                                 "monday-publish.yml"), encoding="utf-8").read()

    def test_run_monday_tells_the_workflow_it_is_a_duplicate(self):
        import tempfile
        import run_monday
        path = os.path.join(tempfile.mkdtemp(), "out")
        self.assertTrue(run_monday.mark_duplicate(path))
        with open(path) as fh:
            self.assertEqual(fh.read().strip(), "duplicate=1")

    def test_it_is_silent_outside_actions(self):
        """A local run must be unaffected. GITHUB_OUTPUT is cleared first:
        this suite also runs INSIDE Actions (the Deploy tracker test gate),
        where it is set, and the test went red there on 29 Sept 2026."""
        import run_monday
        from unittest import mock
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_OUTPUT"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(run_monday.mark_duplicate(None))

    def test_a_duplicate_slot_does_not_attempt_the_store_push(self):
        src = self._workflow()
        step = src[src.index("name: Publish the store"):]
        step = step[:step.index("- name:", 10)]
        self.assertIn("steps.publish.outputs.duplicate != '1'", step)

    def test_the_guard_itself_is_not_softened(self):
        """Nothing in the STORE PUBLISH path may tolerate a refusal: the run
        simply does not attempt a push it already knows cannot succeed.

        Scoped to that step rather than the file. The commit step below has a
        legitimate `git pull --rebase ... || true` in its push-race retry,
        and a file-wide assertion failed on it -- a test that reads as "the
        guard is softened" when it is not is worse than no test."""
        src = self._workflow()
        step = src[src.index("name: Publish the store"):]
        step = step[:step.index("- name:", 10)]
        for weakening in ("continue-on-error", "--force", "|| true"):
            self.assertNotIn(weakening, step,
                             "the lineage guard must not be worked around")

    def test_the_render_step_carries_the_id_the_guard_reads(self):
        """Without the id the expression is always empty, which silently
        passes and restores the old behaviour."""
        import yaml
        spec = yaml.safe_load(self._workflow())
        steps = [s for j in spec["jobs"].values() for s in j.get("steps", [])]
        render = [s for s in steps if s.get("name") == "Render and publish"]
        self.assertEqual([s.get("id") for s in render], ["publish"])

    def test_the_evaluation_is_skipped_on_a_duplicate_too(self):
        """Its store is stale and its push is skipped, so its sample and
        report would be written from an older store and committed over the
        real run's."""
        src = self._workflow()
        step = src[src.index("name: Judge evaluation"):]
        step = step[:step.index("- name:", 10)]
        self.assertIn("steps.publish.outputs.duplicate != '1'", step)


class CompressedStoreTests(unittest.TestCase):
    """11 October 2026: the store reached 1.76GB against GitHub's 2 GiB limit per
    release asset, so it is published gzipped. The sidecar keeps the
    UNCOMPRESSED sha and size (what a pull verifies) beside the asset's own."""

    def setUp(self):
        import sqlite3
        import tempfile
        self.d = tempfile.mkdtemp()
        self.store = os.path.join(self.d, "store.db")
        conn = sqlite3.connect(self.store)
        conn.execute("CREATE TABLE speeches (id INTEGER PRIMARY KEY, body TEXT)")
        conn.executemany("INSERT INTO speeches (body) VALUES (?)",
                         [("the bill was read a second time %d" % i,) for i in range(5000)])
        conn.commit(); conn.close()
        self.db, self.side, self.pulled = [os.path.join(self.d, n) for n in
                                           ("work.db", "work.db.json", ".pulled")]
        with open(self.db, "wb") as fh:
            fh.write(b"working copy")

    def _sidecar(self, **kw):
        with open(self.side, "w") as fh:
            json.dump(kw, fh)

    def test_round_trip_restores_the_exact_store(self):
        gz = os.path.join(self.d, "store.db.gz")
        sha, size, gz_sha, gz_size = db_state.compress(self.store, gz)
        self.assertEqual(sha, db_state.sha256(self.store))
        self.assertEqual(size, os.path.getsize(self.store))
        self.assertEqual(gz_sha, db_state.sha256(gz))
        self.assertEqual(gz_size, os.path.getsize(gz))
        self.assertLess(gz_size, size)
        with open(gz, "rb") as fh:
            self.assertEqual(fh.read(2), b"\x1f\x8b", "a gzip file")
        self._sidecar(sha256=sha, gz_sha256=gz_sha)
        rc = db_state.install_compressed(gz, os.path.join(self.d, "work.db.download"), db=self.db,
                                         sidecar=self.side, pulled=self.pulled, log=lambda *_a: None)
        self.assertEqual(rc, 0)
        self.assertEqual(db_state.sha256(self.db), sha)
        self.assertEqual(db_state.table_counts(self.db), {"speeches": 5000})
        held = open(self.pulled).read().split()
        self.assertEqual(held, [gz_sha, sha], "the store's own sha must be the last line")
        self.assertFalse(os.path.exists(gz), "the downloaded .gz is cleared once installed")

    def test_compression_is_deterministic(self):
        a, b = os.path.join(self.d, "a.gz"), os.path.join(self.d, "b.gz")
        self.assertEqual(db_state.compress(self.store, a)[2], db_state.compress(self.store, b)[2])

    def test_a_sha_mismatch_after_decompressing_is_refused(self):
        gz = os.path.join(self.d, "store.db.gz")
        db_state.compress(self.store, gz)
        self._sidecar(sha256="0" * 64, gz_sha256="1" * 64)
        lines = []
        rc = db_state.install_compressed(gz, os.path.join(self.d, "work.db.download"), db=self.db,
                                         sidecar=self.side, pulled=self.pulled, log=lines.append)
        self.assertEqual(rc, 1)
        self.assertTrue(any("SHA MISMATCH" in l for l in lines))
        self.assertEqual(open(self.db, "rb").read(), b"working copy")
        self.assertFalse(os.path.exists(self.pulled))

    def test_a_truncated_download_is_refused(self):
        gz = os.path.join(self.d, "store.db.gz")
        db_state.compress(self.store, gz)
        data = open(gz, "rb").read()
        with open(gz, "wb") as fh:
            fh.write(data[:len(data) // 2])
        lines = []
        rc = db_state.install_compressed(gz, os.path.join(self.d, "work.db.download"), db=self.db,
                                         sidecar=self.side, pulled=self.pulled, log=lines.append)
        self.assertEqual(rc, 1)
        self.assertTrue(any("CORRUPT DOWNLOAD" in l for l in lines))
        self.assertEqual(open(self.db, "rb").read(), b"working copy")


class PullPlanTests(unittest.TestCase):
    """Which asset a pull takes: the form the sidecar names, the other as a
    fallback (the switch), then a .prev a failed push left aside."""

    def test_a_compressed_sidecar_takes_the_gz_and_falls_back_to_raw(self):
        P = db_state.plan_pull
        self.assertEqual(P([db_state.GZ_ASSET, db_state.ASSET], True), (db_state.GZ_ASSET, None))
        self.assertEqual(P([db_state.ASSET], True), (db_state.ASSET, None))

    def test_a_raw_sidecar_takes_the_raw_asset_first(self):
        """A run still on the old code may publish raw after a compressed push;
        its sidecar has no gz_sha256, and the raw asset is the one it names."""
        P = db_state.plan_pull
        self.assertEqual(P([db_state.GZ_ASSET, db_state.ASSET], False), (db_state.ASSET, None))
        self.assertEqual(P([db_state.GZ_ASSET], False), (db_state.GZ_ASSET, None))

    def test_a_prev_is_recovered_and_nothing_is_nothing(self):
        P = db_state.plan_pull
        self.assertEqual(P([db_state.GZ_PREV], True), (db_state.GZ_PREV, db_state.GZ_ASSET))
        self.assertEqual(P([db_state.PREV], True), (db_state.PREV, db_state.ASSET))
        self.assertEqual(P(["raw-2026-10-09.tar"], True), (None, None))

    def test_prefers_gz_reads_the_sidecar(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "s.json")
        self.assertTrue(db_state.prefers_gz(path), "no sidecar: the current form")
        json.dump({"sha256": "a" * 64}, open(path, "w"))
        self.assertFalse(db_state.prefers_gz(path))
        json.dump({"sha256": "a" * 64, "gz_sha256": "b" * 64}, open(path, "w"))
        self.assertTrue(db_state.prefers_gz(path))

    def _pull(self, assets, payloads, sidecar):
        """Run pull() on the token path against a fake release."""
        import tempfile
        d = tempfile.mkdtemp()
        paths = {"DB": os.path.join(d, "s.db"), "SIDECAR": os.path.join(d, "s.db.json"),
                 "PULLED": os.path.join(d, ".pulled")}
        open(paths["DB"], "wb").write(b"old working copy")
        json.dump(sidecar, open(paths["SIDECAR"], "w"))
        fetched = []

        def download(url, tok, dest):
            fetched.append(url)
            open(dest, "wb").write(payloads[url])
        with mock.patch.multiple(db_state, have_gh=lambda: False, token=lambda: "t",
                                 install_merge_driver=lambda: None,
                                 release=lambda tok: {"assets": [{"name": n, "url": n} for n in assets]},
                                 _api_download=download, **paths):
            rc = db_state.pull()
        return rc, open(paths["DB"], "rb").read(), fetched

    def test_pull_falls_back_to_the_raw_asset(self):
        import hashlib
        raw = b"raw store bytes"
        rc, got, fetched = self._pull([db_state.ASSET], {db_state.ASSET: raw},
                                      {"sha256": hashlib.sha256(raw).hexdigest(), "gz_sha256": "x"})
        self.assertEqual((rc, got, fetched), (0, raw, [db_state.ASSET]))

    def test_pull_takes_the_compressed_asset_when_both_exist(self):
        import gzip
        import hashlib
        store = b"current store bytes" * 100
        rc, got, fetched = self._pull(
            [db_state.ASSET, db_state.GZ_ASSET],
            {db_state.ASSET: b"stale raw", db_state.GZ_ASSET: gzip.compress(store)},
            {"sha256": hashlib.sha256(store).hexdigest(), "gz_sha256": "x"})
        self.assertEqual((rc, got, fetched), (0, store, [db_state.GZ_ASSET]))

    def test_pull_refuses_a_compressed_store_the_sidecar_does_not_name(self):
        import gzip
        rc, got, _f = self._pull([db_state.GZ_ASSET], {db_state.GZ_ASSET: gzip.compress(b"other")},
                                 {"sha256": "0" * 64, "gz_sha256": "x"})
        self.assertEqual((rc, got), (1, b"old working copy"))


class CompressedRaceTests(unittest.TestCase):
    """The live-asset check must stay as strong with the compressed asset: an
    unseen upload, or a push part-way (either .prev), refuses."""

    def assets(self, *rows):
        return [dict(zip(("name", "digest", "created_at"), r)) for r in rows]

    def test_an_unseen_compressed_upload_is_refused(self):
        self.assertFalse(db_state.live_asset_is_ours(["aaa"], self.assets((db_state.GZ_ASSET, "ccc"))))
        self.assertTrue(db_state.live_asset_is_ours(["aaa", "ggg"], self.assets((db_state.GZ_ASSET, "ggg"))))

    def test_a_compressed_push_part_way_is_refused(self):
        self.assertFalse(db_state.live_asset_is_ours(
            ["ggg"], self.assets((db_state.GZ_ASSET, "ggg"), (db_state.GZ_PREV, "zzz"))))

    def test_the_newer_of_two_store_assets_is_the_live_one(self):
        both = lambda raw_t, gz_t: self.assets((db_state.ASSET, "rrr", raw_t), (db_state.GZ_ASSET, "ggg", gz_t))
        # a stale raw asset beside our newer compressed one: ours
        self.assertTrue(db_state.live_asset_is_ours(["ggg"], both("2026-10-10T00:00:00Z", "2026-10-11T00:00:00Z")))
        # a raw asset uploaded AFTER it (old code mid-switch), never seen: refused
        self.assertFalse(db_state.live_asset_is_ours(["ggg"], both("2026-10-12T00:00:00Z", "2026-10-11T00:00:00Z")))

    def test_lineage_still_refuses_through_the_compressed_asset(self):
        with mock.patch.object(db_state, "published_sha", return_value="aaa"), \
             mock.patch.object(db_state, "held_shas", return_value=["aaa"]), \
             mock.patch.object(db_state, "_release_assets",
                               return_value=self.assets((db_state.GZ_ASSET, "ccc"))):
            self.assertFalse(db_state.check_lineage())

    def _swap(self, holder_state=None, verify=None):
        calls, assets = [], {db_state.GZ_ASSET: 1, db_state.ASSET: 0}
        orig = (db_state._rename_asset, db_state._delete_asset, db_state._asset_records)
        sleep, db_state._sleep = db_state._sleep, (lambda _s: None)

        def rename(a, b, tok=None):
            calls.append(("rename", a, b))
            if a not in assets or b in assets:
                return False
            assets[b] = assets.pop(a); return True

        def delete(n, tok=None):
            calls.append(("delete", n)); assets.pop(n, None)

        def upload():
            assets[db_state.GZ_ASSET] = 99
            if holder_state:
                raise RuntimeError("gh upload failed: HTTP 404")
        db_state._rename_asset, db_state._delete_asset = rename, delete
        db_state._asset_records = lambda tok=None: [{"name": n, "id": i, "state": holder_state or "uploaded"}
                                                    for n, i in assets.items()]
        try:
            ok = db_state.swap_in_asset(upload, log=lambda *_a: None, asset=db_state.GZ_ASSET,
                                        prev=db_state.GZ_PREV, verify=verify)
        finally:
            db_state._rename_asset, db_state._delete_asset, db_state._asset_records = orig
            db_state._sleep = sleep
        return ok, calls, assets

    def test_another_publish_landing_on_the_gz_name_stands(self):
        ok, calls, assets = self._swap("uploaded")
        self.assertFalse(ok)
        self.assertNotIn(("delete", db_state.GZ_ASSET), calls)
        self.assertEqual(assets[db_state.GZ_ASSET], 99)
        self.assertIn(db_state.GZ_PREV, assets)
        self.assertEqual(assets[db_state.ASSET], 0, "the swap never touches the raw asset")

    def test_a_good_compressed_swap(self):
        ok, calls, assets = self._swap(verify=lambda: True)
        self.assertTrue(ok)
        self.assertEqual(sorted(assets), sorted([db_state.GZ_ASSET, db_state.ASSET]))
        self.assertEqual(assets[db_state.GZ_ASSET], 99)

    def test_an_upload_that_fails_verification_is_taken_down(self):
        ok, calls, assets = self._swap(verify=lambda: False)
        self.assertFalse(ok)
        self.assertEqual(assets[db_state.GZ_ASSET], 1, "the previous store is back under its name")
        self.assertNotIn(db_state.GZ_PREV, assets)

    def test_an_unverifiable_upload_stands(self):
        ok, _calls, assets = self._swap(verify=lambda: None)
        self.assertTrue(ok)
        self.assertEqual(assets[db_state.GZ_ASSET], 99)


class CompressedPushTests(unittest.TestCase):
    """push() publishes the .gz, writes both shas, and retires the raw asset
    only once the upload is verified."""

    def _push(self, verified):
        import sqlite3
        import tempfile
        d = tempfile.mkdtemp()
        paths = {"DB": os.path.join(d, "s.db"), "SIDECAR": os.path.join(d, "s.db.json"),
                 "PULLED": os.path.join(d, ".pulled")}
        conn = sqlite3.connect(paths["DB"]); conn.execute("CREATE TABLE t (a)")
        conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(1000)])
        conn.commit(); conn.close()
        sent, deleted = [], []

        def api(url, tok, data=None, headers=None, method=None):
            sent.append((url, data.read() if hasattr(data, "read") else data, headers))
            return b"{}"

        def swap(upload, api_tok=None, log=print, asset=None, prev=None, verify=None,
                 held=None, ours=None):
            upload()
            self.assertEqual((asset, prev), (db_state.GZ_ASSET, db_state.GZ_PREV))
            verify()
            return True
        with mock.patch.multiple(db_state, have_gh=lambda: False, token=lambda: "t",
                                 check_lineage=lambda: True, stamp_heartbeat=lambda: None,
                                 held_shas=lambda: [],
                                 release=lambda tok: {"upload_url": "https://up/x{?name}"},
                                 _api=api, swap_in_asset=swap,
                                 check_upload=lambda *a, **k: verified,
                                 _assets=lambda tok=None: [(db_state.ASSET, 1), (db_state.GZ_ASSET, 2)],
                                 _delete_asset=lambda n, tok=None: deleted.append(n), **paths), \
             mock.patch.object(db_state.sys, "argv", ["db_state.py", "--push"]):
            rc = db_state.push()
        side = json.load(open(paths["SIDECAR"]))
        return rc, side, sent, deleted, paths

    def test_push_uploads_the_gz_and_records_both_shas(self):
        import gzip
        import hashlib
        rc, side, sent, deleted, paths = self._push(True)
        self.assertEqual(rc, 0)
        url, body, headers = sent[0]
        self.assertTrue(url.endswith("?name=" + db_state.GZ_ASSET))
        self.assertEqual(headers["Content-Length"], str(len(body)))
        store = open(paths["DB"], "rb").read()
        self.assertEqual(gzip.decompress(body), store)
        self.assertEqual(side["sha256"], hashlib.sha256(store).hexdigest())
        self.assertEqual(side["bytes"], len(store))
        self.assertEqual(side["gz_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(side["gz_bytes"], len(body))
        self.assertEqual(open(paths["PULLED"]).read().split(), [side["gz_sha256"], side["sha256"]])
        self.assertEqual(deleted, [db_state.ASSET], "verified: the raw asset is retired")
        self.assertFalse(os.path.exists(paths["DB"] + ".gz"), "the .gz is not left in data/")

    def test_an_unverified_push_keeps_the_raw_asset(self):
        rc, _side, _sent, deleted, _p = self._push(None)
        self.assertEqual(rc, 0)
        self.assertEqual(deleted, [])


class VacuumTests(unittest.TestCase):
    """A push vacuums the store before the sha (12 October 2026), bounded and never fatal."""

    def setUp(self):
        import sqlite3
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "parl-monitor.db")
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE t (k INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("CREATE INDEX t_v ON t (v)")
        conn.executemany("INSERT INTO t (v) VALUES (?)", [("x" * 200,)] * 3000)
        conn.commit()
        conn.execute("DELETE FROM t WHERE k % 2 = 0")       # leaves empty space
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _count(self):
        import sqlite3
        conn = sqlite3.connect(self.path)
        try:
            return conn.execute("SELECT count(*) FROM t").fetchone()[0]
        finally:
            conn.close()

    def test_vacuums_in_place_and_keeps_the_rows(self):
        size = os.path.getsize(self.path)
        lines = []
        self.assertTrue(db_state.vacuum_store(self.path, log=lines.append))
        self.assertLess(os.path.getsize(self.path), size)
        self.assertEqual(self._count(), 1500)
        self.assertFalse(os.path.exists(self.path + ".vacuum"))
        self.assertTrue(any("vacuumed" in ln for ln in lines))

    def test_skipped_when_the_disk_is_short(self):
        with open(self.path, "rb") as handle:
            raw = handle.read()
        lines = []
        self.assertFalse(db_state.vacuum_store(self.path, log=lines.append, free_bytes=1000))
        self.assertTrue(any("VACUUM skipped" in ln for ln in lines))
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), raw)

    def test_stops_at_its_bound_and_leaves_the_store(self):
        with open(self.path, "rb") as handle:
            raw = handle.read()
        lines = []
        with mock.patch.object(db_state, "VACUUM_CHECK_EVERY", 1):
            self.assertFalse(db_state.vacuum_store(self.path, log=lines.append, max_s=-1))
        self.assertTrue(any("bound" in ln for ln in lines), lines)
        self.assertFalse(os.path.exists(self.path + ".vacuum"))
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), raw)

    def test_not_a_database_is_not_fatal(self):
        with open(self.path, "wb") as handle:
            handle.write(b"not sqlite" * 100)
        lines = []
        self.assertFalse(db_state.vacuum_store(self.path, log=lines.append))
        self.assertTrue(any("unvacuumed" in ln for ln in lines))

    def test_env_switch(self):
        with mock.patch.dict(os.environ, {"DB_STATE_NO_VACUUM": "1"}):
            self.assertFalse(db_state.vacuum_store(self.path, log=lambda _l: None))

    def test_push_vacuums_after_the_heartbeat_and_before_the_sha(self):
        src = open(os.path.join(ROOT, "tools", "db_state.py"), encoding="utf-8").read()
        body = src[src.index("def push():"):src.index("def _publish(")]
        self.assertLess(body.index("stamp_heartbeat()"), body.index("vacuum_store()"))
        self.assertLess(body.index("vacuum_store()"), body.index("sha256(DB)"))


class SizeGuardTests(unittest.TestCase):
    """The next step after compression is splitting the store; these raise it early."""

    def test_thresholds(self):
        # On the COMPRESSED asset only (12 October 2026): the raw size of
        # today's store (1.85 GB, 454 MB compressed) warns about nothing.
        self.assertEqual(db_state.size_warnings(1_850_000_000, 454_000_000), [])
        self.assertEqual(db_state.size_warnings(5_000_000_000, None), [])
        self.assertEqual(db_state.size_warnings(3_000_000_000, 749_999_999), [])
        w = db_state.size_warnings(3_100_000_000, 750_000_000)
        self.assertEqual(len(w), 1)
        self.assertIn("Plan the split", w[0])
        self.assertIn("0.75 GB", w[0])
        w = db_state.size_warnings(4_300_000_000, 1024 ** 3 - 1)
        self.assertEqual(len(w), 1)
        self.assertIn("Plan the split", w[0])
        w = db_state.size_warnings(4_300_000_000, 1024 ** 3)
        self.assertEqual(len(w), 1)
        self.assertIn("Split the store now", w[0])
        self.assertIn("1.07 GB", w[0])
        w = db_state.size_warnings(5_000_000_000, 1_600_000_000)
        self.assertEqual(len(w), 1)
        self.assertIn("Split the store now", w[0])

    def test_the_raw_warning_is_gone(self):
        self.assertFalse(hasattr(db_state, "STORE_WARN_BYTES"))
        self.assertEqual(db_state.GZ_PLAN_BYTES, 750_000_000)
        self.assertEqual(db_state.GZ_WARN_BYTES, 1024 ** 3)

    def test_a_push_warns_and_refuses_over_the_asset_limit(self):
        src = open(os.path.join(ROOT, "tools", "db_state.py"), encoding="utf-8").read()
        body = src[src.index("def _publish("):src.index("def main():")]
        self.assertIn("size_warnings(size, gz_size)", body)
        self.assertLess(body.index("gz_size >= ASSET_LIMIT"), body.index("swap_in_asset("))

    def test_warn_annotates_on_actions(self):
        lines = []
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            db_state.warn("x", log=lines.append)
        self.assertEqual(lines, ["::warning::x"])

    def test_the_health_summary_shows_the_store_size(self):
        import tempfile
        import health_summary as hs
        path = os.path.join(tempfile.mkdtemp(), "s.json")
        json.dump({"bytes": 1_760_000_000, "gz_bytes": 410_000_000}, open(path, "w"))
        lines = hs.store_size(path)
        self.assertIn("1.76 GB", lines[0])
        self.assertEqual(len(lines), 1, "410 MB compressed warns about nothing")
        json.dump({"bytes": 3_300_000_000, "gz_bytes": 800_000_000}, open(path, "w"))
        lines = hs.store_size(path)
        self.assertTrue(any(":warning:" in l and "plan the split" in l.lower() for l in lines))
        json.dump({"bytes": 900_000_000}, open(path, "w"))
        self.assertEqual(len(hs.store_size(path)), 1)
        self.assertIsNone(hs.store_size(path + ".missing"))
