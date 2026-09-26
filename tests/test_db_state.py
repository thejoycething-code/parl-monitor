"""The store as a release asset (Christopher's decision, 2026-08-24).

The store hit 88MB against GitHub's 100MB HARD push limit, growing ~15MB
per build sprint. It is derived state, so it moved out of git into a
release asset. These tests pin the properties that make that safe.
"""

import json
import os
import sys
import unittest

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
                "de-weekly.yml")

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
        self.assertEqual(db_state._no_asset_yet(), 0,
                         "the working copy exists, so the first run should "
                         "proceed and publish it")

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
               "Historic backfill", "Score stance", "Germany weekly")

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
                            if line[max(0, m.start() - 1)] == "{":
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
        self._real = (db_state._rename_asset, db_state._delete_asset)

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
        self.ds._rename_asset, self.ds._delete_asset = self._real

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
        self.assertEqual(seen, [[self.ds.PREV]], "a copy must exist while uploading")
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
    # and the Division watch polls the House through a sitting day.
    DIFFERENT_PASSES = ("day-sweep.yml", "division-watch.yml")

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
        for name in ("eu-weekly.yml", "sp-weekly.yml", "sd-weekly.yml",
                     "ni-weekly.yml", "de-weekly.yml"):
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
        """A local run must be unaffected."""
        import run_monday
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
