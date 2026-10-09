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


class SameStepsAsTheWorkflowTests(unittest.TestCase):
    """Sunday pull and Monday publish run on the Mac Mini from jobs/*.sh while
    GitHub keeps its own steps as the backup (9 October 2026). Two copies are
    safe only while they agree: same commands, same order, same commit."""

    PAIRS = (("sunday-pull.yml", "sunday-pull.sh"), ("monday-publish.yml", "monday-publish.sh"),
             ("sp-weekly.yml", "sp-weekly.sh"))

    def _read(self, wf, job):
        return (open(os.path.join(ROOT, ".github", "workflows", wf), encoding="utf-8").read(),
                open(os.path.join(ROOT, "jobs", job), encoding="utf-8").read())

    def test_same_commands_in_the_same_order(self):
        for wf, job in self.PAIRS:
            flow, script = self._read(wf, job)
            self.assertTrue(_commands(flow), wf)
            self.assertEqual(_commands(flow), _commands(script), "{0} and {1} disagree".format(wf, job))

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


if __name__ == "__main__":
    unittest.main()
