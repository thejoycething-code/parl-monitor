"""Monday publish run (unattended): render the edition, post to Slack, create
the Asana reading task. Companion to the Sunday pull; handoff section 8 cron
design, extended with publishing.

  python3 run_monday.py               # this week's Monday
  python3 run_monday.py 2026-08-10    # explicit week

Human review remains available, not blocking: decisions saved into
reviews/review-<week>.md before this runs are applied (merge-preserved). If
nobody reviewed, the edition ships WATCH/NOTE-only; the ACT-owner validation
makes ownerless urgency structurally impossible in an unattended run.
"""

from __future__ import annotations

import datetime
import os
import re
import sys

import run_weekly
from src import publish

ROOT = os.path.dirname(os.path.abspath(__file__))


def summarise_edition(markdown, week):
    """Build the Slack mrkdwn summary + supporting lists from the edition."""
    top = re.findall(r"^- \*\*\[(ACT|WATCH|NOTE)\]\*\* (.+)$", markdown, re.M)
    acts = [text for tag, text in top if tag == "ACT"]
    # ACT lines can appear in any section; collect all, deduped, tag stripped.
    all_acts = []
    for line in re.findall(r"^- \*\*\[ACT\]\*\* (.+)$", markdown, re.M):
        clean = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", line)  # unlink
        if clean not in all_acts:
            all_acts.append(clean)

    deadlines = []
    horizon = datetime.date.fromisoformat(week) + datetime.timedelta(days=21)
    for m in re.finditer(r"Deadline: (\d{4}-\d{2}-\d{2})", markdown):
        d = datetime.date.fromisoformat(m.group(1))
        if d <= horizon:
            line_start = markdown.rfind("\n", 0, m.start()) + 1
            line = markdown[line_start:markdown.find("\n", m.start())]
            clean = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", line).lstrip("- *")
            deadlines.append(clean[:160])

    bullet_lines = []
    for tag, text in top[:4]:
        clean = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
        bullet_lines.append("• *[{0}]* {1}".format(tag, clean))
    for act in all_acts:
        line = "• *[ACT]* {0}".format(act)
        if line not in bullet_lines:
            bullet_lines.append(line)

    summary = ("*Parliamentary Monitor - week commencing {0}*\n\n"
               "The weekly briefing on everything moving in Westminster that touches "
               "our campaigns.\n\n{1}").format(week, "\n".join(bullet_lines))
    return summary, all_acts, deadlines


def edition_number(conn):
    return conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0]


def main():
    week = sys.argv[1] if len(sys.argv) > 1 else (
        datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    ).isoformat()

    path = run_weekly.render_edition(week, run_weekly._db_name(week))
    with open(path, "r", encoding="utf-8") as handle:
        markdown = handle.read()

    from src import db
    conn = db.connect(os.path.join(ROOT, "data", run_weekly._db_name(week)))
    number = edition_number(conn)
    conn.close()

    secrets = publish.load_secrets()
    summary, acts, deadlines = summarise_edition(markdown, week)

    # Canvas carries the edition body (strip the file's H1; canvas has a title).
    canvas_md = re.sub(r"^# Parliamentary Monitor\n", "", markdown, count=1)

    slack = publish.slack_publish_edition(secrets, week, number, canvas_md, summary)
    print("slack: {0}".format(slack))

    canvas_url = slack.get("canvas_url", "(not posted to Slack)")
    asana = publish.asana_create_reading_task(secrets, week, canvas_url, acts, deadlines)
    print("asana: {0}".format(asana))

    print("edition: {0}".format(path))
    failures = [s for s in (slack, asana) if "error" in s]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
