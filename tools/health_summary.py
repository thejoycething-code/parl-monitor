"""The daily health summary: one DM at 07:30 London (docs/mac-mini-runner.md, step 5).

    python3 tools/health_summary.py              # print it
    python3 tools/health_summary.py --dm         # and DM it

Jobs now run in two places, the Mac Mini first and GitHub as the backup, and
neither one's failure alerts say what the other did. This says it all at once:

  * what ran in the last 24 hours on the Mini (from its own logs) and on
    GitHub, what failed, and what is running or queued now;
  * every overdue source from tools/coverage.py, EVERY day, with the ones
    first seen in the last day marked NEW. The coverage watch itself now
    alerts only on new or worsening problems (coverage.py --state), so this
    is where a known one stays visible.

Never fails the job: a summary that cannot reach GitHub or the store says so
in its own text, because silence would read as "all well".
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

REPO = "thejoycething-code/parl-monitor"
LOGS = os.path.join(os.path.expanduser("~"), "runner", "logs")
STATE = os.path.join(ROOT, "data", "coverage-state.json")
LOCK_JOB = os.path.join(os.path.expanduser("~"), "runner", "locks", "state", "job")
SELF = "health"
# Runs of these say nothing about the pipeline: the alerter fires on every
# completed run and skips itself unless one failed.
GITHUB_IGNORE = {"Failure alert"}

START = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) mini_run (\S+) \(ref ")
DONE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) mini_run (\S+) done")
FAILED = re.compile(r"^\s+FAILED at (.+)$")


def _ts(text):
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)


def mini_runs(lines, since):
    """[(job, started, outcome)] from one mini_run log, newest last.

    outcome: "ok", "FAILED at <stage>: <why>", or "running" when the log
    ends inside a run (it may still be going, or it died without a word).
    """
    runs, cur, rerun = [], None, False
    for line in lines:
        m = START.match(line)
        if m:
            # After "re-running the new one" the wrapper starts over in the
            # same process: one run, not an unfinished one and a second.
            if cur and not (rerun and cur[0] == m.group(2)):
                runs.append(cur)
            cur, rerun = [m.group(2), _ts(m.group(1)), "running"], False
            continue
        if cur is None:
            continue
        if "re-running the new one" in line:
            rerun = True
            continue
        if DONE.match(line):
            cur[2] = "ok"
            runs.append(cur)
            cur = None
            continue
        f = FAILED.match(line)
        if f:
            cur[2] = "FAILED at " + f.group(1).strip()
            runs.append(cur)
            cur = None
    if cur:
        runs.append(cur)
    return [tuple(r) for r in runs if r[1] >= since]


def read_mini(logs, since):
    runs = []
    if not os.path.isdir(logs):
        return None
    for name in sorted(os.listdir(logs)):
        if not name.endswith(".log") or name.startswith("test-"):
            continue
        path = os.path.join(logs, name)
        with open(path, encoding="utf-8", errors="replace") as handle:
            handle.seek(max(0, os.path.getsize(path) - 400_000))
            runs.extend(mini_runs(handle.read().splitlines(), since))
    return sorted((r for r in runs if r[0] != SELF), key=lambda r: r[1])


def read_github(since):
    """[(workflow, created, status, conclusion)] since `since`, or None."""
    out = subprocess.run(
        ["gh", "run", "list", "-R", REPO, "-L", "200", "--json",
         "workflowName,createdAt,status,conclusion"],
        capture_output=True, text=True)
    if out.returncode:
        return None
    try:
        rows = json.loads(out.stdout)
    except ValueError:
        return None
    return [(r["workflowName"], _ts(r["createdAt"]), r["status"], r.get("conclusion") or "")
            for r in rows
            if r["workflowName"] not in GITHUB_IGNORE and _ts(r["createdAt"]) >= since]


def overdue_sources(db_path, state_path, today):
    """[(text, is_new)] from coverage.check, or None if the store is unreadable."""
    import coverage
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    found = []
    try:
        lines = coverage.check(conn, today=today, log=lambda *a: None, quiet=True, found=found)
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    state = coverage.load_state(state_path)
    fresh = {(today - datetime.timedelta(days=1)).isoformat(), today.isoformat()}
    return [(text, state.get(key, {}).get("first", today.isoformat()) in fresh)
            for (key, _age), text in zip(found, lines)]


def london(when):
    try:
        from zoneinfo import ZoneInfo
        return when.astimezone(ZoneInfo("Europe/London")).strftime("%a %H:%M")
    except Exception:                                        # noqa: BLE001
        return when.strftime("%a %H:%MZ")


def render(now, mini, github, overdue, running_job):
    out = ["*parl-monitor health, {0} London*".format(london(now))]

    out.append("\n*Mac Mini, last 24h*")
    if mini is None:
        out.append("• no Mini logs found (is this running on the Mini?)")
    elif not mini:
        out.append("• nothing ran")
    else:
        failed = [r for r in mini if r[2].startswith("FAILED")]
        ok = [r for r in mini if r[2] == "ok"]
        out.append("• {0} run(s): {1} ok, {2} failed".format(len(mini), len(ok), len(failed)))
        for job, started, outcome in failed:
            out.append("• :x: {0} at {1}: {2}".format(job, london(started), outcome[10:][:160]))
        for job, started, outcome in mini:
            if outcome == "running" and job != running_job:
                out.append("• :warning: {0} at {1} never finished".format(job, london(started)))
    if running_job:
        out.append("• running now: {0}".format(running_job))

    out.append("\n*GitHub, last 24h*")
    if github is None:
        out.append("• could not read GitHub's runs")
    elif not github:
        out.append("• nothing ran")
    else:
        bad = [r for r in github if r[3] in ("failure", "cancelled", "timed_out", "startup_failure")]
        live = [r for r in github if r[2] in ("queued", "in_progress", "waiting", "pending")]
        out.append("• {0} run(s), {1} failed, {2} running or queued (backup runs the "
                   "Mini covered count as ok)".format(len(github), len(bad), len(live)))
        # One line per workflow: a job retried eight times by hand is one
        # problem, and eight lines of it bury the one-off below it.
        by_name = {}
        for name, created, _s, concl in bad:
            by_name.setdefault(name, []).append((created, concl))
        for name, fails in sorted(by_name.items(), key=lambda kv: -max(c for c, _x in kv[1]).timestamp()):
            latest, concl = max(fails)
            out.append("• :x: {0}: {1}{2}, latest {3}".format(
                name, concl, " x{0}".format(len(fails)) if len(fails) > 1 else "", london(latest)))
        for name, created, status, _c in live:
            out.append("• :hourglass: {0}: {1} since {2}".format(name, status, london(created)))

    out.append("\n*Overdue sources*")
    if overdue is None:
        out.append("• could not read the store, so coverage is unknown")
    elif not overdue:
        out.append("• none: every pipeline and feed is within its cadence")
    else:
        new = sum(1 for _t, n in overdue if n)
        out.append("• {0} overdue, {1} new".format(len(overdue), new))
        for text, is_new in sorted(overdue, key=lambda x: not x[1]):
            out.append("• {0}{1}".format("*NEW* " if is_new else "", text))
    return "\n".join(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    now = datetime.datetime.now(datetime.timezone.utc)
    since = now - datetime.timedelta(hours=24)
    running = None
    try:
        with open(LOCK_JOB, encoding="utf-8") as handle:
            running = handle.read().strip() or None
    except OSError:
        pass
    if running == SELF:
        running = None
    text = render(now, read_mini(LOGS, since), read_github(since),
                  overdue_sources(os.path.join(ROOT, "data", "parl-monitor.db"), STATE,
                                  now.date()),
                  running)
    print(text)
    if "--dm" in argv:
        from src import publish
        try:
            result = publish.slack_dm(publish.load_secrets(), text)
        except Exception as exc:                            # noqa: BLE001
            result = {"error": str(exc)}
        print("\nDM: {0}".format(result.get("error") or result.get("skipped") or "sent"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
