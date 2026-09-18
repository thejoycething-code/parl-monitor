"""DM Christopher when a workflow fails.

    python3 tools/alert_failure.py            # reads the GitHub run from env

Silent failure is the worst class for an unattended pipeline, and this repo
had NO failure handler at all until 2026-08-24: a failed Sunday pull would
have produced a stale or empty Monday edition with nobody told. The same day
proved it is not theoretical -- a `tee` pipeline reported SUCCESS while the
tool inside it had crashed, and only an empty block in a run summary gave it
away.

Deliberately a DM, not the campaigns channel: a broken cron is an
operational fact for one person, not news for the team.

Never fails the job it is reporting on. If Slack is unreachable the message
is printed instead, because an alerter that breaks the build turns one
failure into two.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import publish


def message(env=None):
    env = env if env is not None else os.environ
    # The failed run, not this one: this alerter runs in a SEPARATE
    # workflow triggered by workflow_run, so that the watching-brief
    # workflows never hold a Slack credential of their own.
    name = (env.get("FAILED_WORKFLOW") or env.get("GITHUB_WORKFLOW")
            or "a workflow")
    repo = env.get("GITHUB_REPOSITORY") or "thejoycething-code/parl-monitor"
    url = env.get("FAILED_RUN_URL") or (
        "https://github.com/{0}/actions/runs/{1}".format(
            repo, env.get("GITHUB_RUN_ID"))
        if env.get("GITHUB_RUN_ID")
        else "https://github.com/{0}/actions".format(repo))
    step = env.get("FAILED_STEP")
    lines = [":rotating_light: *{0}* failed.".format(name)]
    if step:
        lines.append("Step: {0}".format(step))
    lines.append(url)
    lines.append("_Whatever the run completed WAS published (the publish "
                 "step runs on failure too, so partial progress is not "
                 "lost). Every write is an upsert, so re-running after the "
                 "fix completes the job rather than duplicating it._")
    return "\n".join(lines)


def main():
    secrets = publish.load_secrets()
    text = message()
    try:
        result = publish.slack_dm(secrets, text)
    except Exception as exc:                                # noqa: BLE001
        print("alert could not be sent ({0}); the message was:\n{1}"
              .format(exc, text))
        return 0                                            # never fail the job
    if result.get("skipped") or result.get("error"):
        print("alert not sent ({0}); the message was:\n{1}"
              .format(result.get("skipped") or result.get("error"), text))
    else:
        print("failure alert sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
