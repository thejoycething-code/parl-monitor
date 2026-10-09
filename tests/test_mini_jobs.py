"""Every Mac Mini job that publishes the store names the pipeline its heartbeat
stamps (9 October 2026: Day sweep, EU day sweep and US weekly stamped "local",
so tools/coverage.py would have called them dead once GitHub's backup skipped)."""
import glob
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import coverage  # noqa: E402


class HeartbeatNameTests(unittest.TestCase):
    def test_every_store_publishing_job_names_a_watched_pipeline(self):
        jobs = glob.glob(os.path.join(ROOT, "jobs", "*.sh"))
        self.assertTrue(jobs)
        for path in jobs:
            src = open(path, encoding="utf-8").read()
            push = re.search(r"^[^#\n]*python3 tools/db_state\.py --push", src, re.M)
            if not push:
                continue
            m = re.search(r'GITHUB_WORKFLOW="\$\{GITHUB_WORKFLOW:-([^}]+)\}"', src)
            self.assertIsNotNone(m, os.path.basename(path) + " publishes the store but names no pipeline")
            self.assertIn(m.group(1), coverage.PIPELINES, os.path.basename(path))
            self.assertLess(m.start(), push.start(), path)


def _commands(text):
    """The python3 tools/run_* invocations, in order, ignoring the fetches
    (each caller fetches the store its own way) and comments."""
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        for m in re.finditer(r"python3 ((?:tools/)?[\w]+\.py(?: -{0,2}[\w-]+)?)", line):
            cmd = m.group(1)
            if cmd in ("tools/db_state.py --pull", "tools/raw_state.py --pull"):
                continue
            out.append(cmd)
    return out


def _scheduled_commands(workflow_text):
    """The commands a SCHEDULED run of the workflow executes, in order. A step
    whose condition depends on dispatch inputs runs on a schedule only when it
    says so (`github.event_name == 'schedule' || ...`); the rest are hand-only
    backfills and repairs, which stay on GitHub or are run by hand."""
    import yaml
    doc = yaml.safe_load(workflow_text)
    out = []
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            cond = " ".join(str(step.get("if") or "").split())
            if "inputs." in cond and "github.event_name == 'schedule' ||" not in cond:
                continue
            out += _commands(str(step.get("run") or ""))
    return out


class SameStepsAsTheWorkflowTests(unittest.TestCase):
    """Sunday pull and Monday publish run on the Mac Mini from jobs/*.sh while
    GitHub keeps its own steps as the backup (9 October 2026). Two copies are
    safe only while they agree: same commands, same order, same commit."""

    PAIRS = (("sunday-pull.yml", "sunday-pull.sh"), ("monday-publish.yml", "monday-publish.sh"),
             ("sp-weekly.yml", "sp-weekly.sh"), ("sd-weekly.yml", "sd-weekly.sh"),
             ("ni-weekly.yml", "ni-weekly.sh"), ("eu-weekly.yml", "eu-weekly.sh"),
             ("de-weekly.yml", "de-weekly.sh"), ("ca-weekly.yml", "ca-weekly.sh"),
             ("prov-weekly.yml", "prov-weekly.sh"), ("upr-monthly.yml", "upr-monthly.sh"),
             ("member-profiles.yml", "member-profiles.sh"))

    def _read(self, wf, job):
        return (open(os.path.join(ROOT, ".github", "workflows", wf), encoding="utf-8").read(),
                open(os.path.join(ROOT, "jobs", job), encoding="utf-8").read())

    def test_same_commands_in_the_same_order(self):
        for wf, job in self.PAIRS:
            flow, script = self._read(wf, job)
            self.assertTrue(_scheduled_commands(flow), wf)
            self.assertEqual(_scheduled_commands(flow), _commands(script), "{0} and {1} disagree".format(wf, job))

    def test_same_things_committed(self):
        for wf, job in self.PAIRS:
            flow, script = self._read(wf, job)
            add = next(ln for ln in flow.splitlines() if ln.strip().startswith("git add "))
            want = {p.rstrip("/") for p in add.split()[2:]
                    if p.rstrip("/") != "data" and not p.startswith("data/")}
            m = re.search(r"^# mini_run: commit (.+)$", script, re.M)
            got = set(m.group(1).split()) if m else set()
            self.assertEqual(want, got, "{0} commits {1}, {2} commits {3}".format(wf, sorted(want), job, sorted(got)))

    def test_triage_spends_on_both(self):
        flow, script = self._read("sunday-pull.yml", "sunday-pull.sh")
        for text in (flow, script):
            self.assertIn("TRIAGE=auto python3 run_weekly.py --pull", text)

    def test_monday_on_the_mini_deploys_through_github(self):
        after = open(os.path.join(ROOT, "jobs", "monday-publish.after.sh"), encoding="utf-8").read()
        self.assertIn("gh workflow run deploy-tracker.yml", after)
        self.assertIn("workflow_dispatch:", open(os.path.join(
            ROOT, ".github", "workflows", "deploy-tracker.yml"), encoding="utf-8").read())

    def test_both_workflows_are_gated_with_cover_hours(self):
        for wf, _job in self.PAIRS:
            flow, _ = self._read(wf, _job)
            self.assertIn("uses: ./.github/workflows/mini-check.yml", flow, wf)
            self.assertIn("needs.mini-check.outputs.run == 'true'", flow, wf)
            self.assertRegex(flow, r"cover-hours: [1-9]\d*", wf)


class HardenedPushLoopTests(unittest.TestCase):
    """docs/mac-mini-runner.md, step 4 (9 October 2026). The old loop was
    `pull --rebase || true` then three pushes 5-15 s apart: a rebase conflict
    left the tree mid-rebase, every retry then failed, and 372 human commits
    in three weeks kept winning the race. Every workflow that pushes now
    aborts a failed rebase, waits longer, and fails the step loudly."""

    def test_no_workflow_keeps_the_old_loop(self):
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            text = open(path, encoding="utf-8").read()
            if "git push" not in text or "for attempt in" not in text:
                continue
            name = os.path.basename(path)
            self.assertNotRegex(text, r"git pull --rebase[^\n]*\|\| true", name + ": retries while mid-rebase")
            self.assertIn("git rebase --abort", text, name)
            self.assertIn("for attempt in 1 2 3 4 5 6", text, name)
            self.assertTrue("never reached origin" in text or 'echo "push failed six times"; exit 1' in text,
                            name + ": a loop that falls out must fail the step")


if __name__ == "__main__":
    unittest.main()
