"""Should GitHub's scheduled run go ahead, or did the Mac Mini already run it?

    python3 tools/mini_check.py --job COVERAGE --event schedule \\
        --schedule "30 5 * * *" --last 2026-10-09T04:30:02Z

Called by .github/workflows/mini-check.yml, the gate in front of every
scheduled workflow (docs/mac-mini-runner.md, step 3). The Mini runs each job
at the slot's time and records MINI_LAST_<JOB> after a clean run
(tools/mini_run.sh). GitHub's cron starts hours late or not at all, so its
run is the backup: it goes ahead only when the Mini has not run since the
slot it was scheduled for.

The slot is the latest time the cron names, at or before now, today or
yesterday (a late Friday 17:00 run that starts after midnight is still the
Friday 17:00 slot). Day-of-week fields are ignored: the run would not exist
on a day the cron excludes.

GRACE. launchd keeps London time and the crons are UTC, so in summer the
Mini fires an hour BEFORE the UTC slot it covers (05:30 London is 04:30
UTC). A Mini run up to grace minutes before the slot still counts. Keep it
under the gap between a job's slots.

When in doubt the backup runs: a hand dispatch, a missing or unreadable
stamp, or a cron this cannot read (then a stamp within window hours counts).

THE MINI IS RUNNING IT NOW (MINI_RUN_<JOB>, set by mini_run.sh when it
starts and cleared when it ends). Then EVERY trigger skips, a hand dispatch
included: two runs at once is the one thing the publish log cannot stop --
both read "not yet published" and both post (Monday publish, 9 October 2026).
A marker older than running-max minutes is a Mini that died mid-run and is
ignored.

COVER HOURS. A workflow with retry slots (Sunday pull, Monday publish) has
later crons that exist only to rescue the primary. A Mini run within
cover-hours covers them all, whichever slot fired.

A PUSH is a clock too: the cloud routine starts Monday publish by pushing a
trigger branch. It is judged like a schedule, by cover-hours.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

UTC = dt.timezone.utc


def parse_stamp(text):
    try:
        return dt.datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


def _hours(field):
    hours = []
    for part in field.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            hours.extend(range(int(lo), int(hi) + 1))
        else:
            hours.append(int(part))
    return hours


def slot_for(cron, now):
    """The latest time `cron` names at or before `now`, or None if unreadable."""
    try:
        minute_f, hour_f = cron.split()[:2]
        minute, hours = int(minute_f), _hours(hour_f)
    except (ValueError, AttributeError):
        return None                      # "*", "*/15", or no cron at all
    candidates = []
    for back in (0, 1):
        day = (now - dt.timedelta(days=back)).date()
        for hour in hours:
            at = dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)
            if at <= now:
                candidates.append(at)
    return max(candidates) if candidates else None


def decide(event, cron, last_text, now, grace_minutes=75, window_hours=20,
           cover_hours=0, running_text="", running_max_minutes=180):
    """(run, why): run is False only when the Mini already covered this slot,
    or is running the job right now."""
    running = parse_stamp(running_text) if running_text else None
    if running is not None and dt.timedelta(0) <= now - running < dt.timedelta(minutes=running_max_minutes):
        return False, "the Mini is running this job now (started {0}, {1} min ago): skipping".format(
            running_text, int((now - running).total_seconds() // 60))
    last = parse_stamp(last_text) if last_text else None
    ago = "" if last is None else ", {0} min ago".format(int((now - last).total_seconds() // 60))
    if event not in ("schedule", "push"):
        return True, "{0}: always runs (Mini last ran {1}{2})".format(
            event, last_text or "never", ago)
    if not last_text:
        return True, "no Mini run recorded: running as backup"
    if last is None:
        return True, "Mini stamp {0!r} is unreadable: running as backup".format(last_text)
    if cover_hours and now - last < dt.timedelta(hours=cover_hours):
        return False, "the Mini ran at {0}{1}, within {2}h, which covers every slot: skipping".format(
            last_text, ago, cover_hours)
    if event == "push":
        return True, "a push, and the Mini last ran at {0}{1}: running as backup".format(last_text, ago)
    slot = slot_for(cron, now)
    if slot is None:
        if now - last < dt.timedelta(hours=window_hours):
            return False, "the Mini ran at {0}{1}, within {2}h: skipping".format(
                last_text, ago, window_hours)
        return True, "the Mini last ran at {0}{1}, over {2}h: rescuing the slot".format(
            last_text, ago, window_hours)
    slot_text = slot.strftime("%Y-%m-%d %H:%M UTC")
    if last >= slot - dt.timedelta(minutes=grace_minutes):
        return False, "the Mini ran at {0}{1}, covering the {2} slot: skipping".format(
            last_text, ago, slot_text)
    return True, "the Mini last ran at {0}{1}, before the {2} slot: rescuing it".format(
        last_text, ago, slot_text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--job", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--schedule", default="")
    ap.add_argument("--last", default="")
    ap.add_argument("--grace-minutes", type=int, default=75)
    ap.add_argument("--window-hours", type=int, default=20)
    ap.add_argument("--cover-hours", type=int, default=0)
    ap.add_argument("--running", default="")
    ap.add_argument("--running-max-minutes", type=int, default=180)
    args = ap.parse_args(argv)
    run, why = decide(args.event, args.schedule, args.last, dt.datetime.now(UTC),
                      args.grace_minutes, args.window_hours, args.cover_hours,
                      args.running, args.running_max_minutes)
    print(why)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write("run={0}\n".format("true" if run else "false"))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write("**Mini check ({0}):** {1}\n".format(args.job, why))
    return 0


if __name__ == "__main__":
    sys.exit(main())
