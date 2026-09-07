"""Rewrite an already-published edition's Slack canvas in place.

    python3 tools/republish_canvas.py 2026-09-07

Christopher, 2026-09-07: "Redo today's publish under the new format."
The Monday publish creates a NEW canvas and a NEW channel message every
time (run_monday --force), and leaves the old ones standing -- so a
redo that way puts two editions in #campaigns-en-gb on one morning.
This replaces the body of the canvas the publish_log already records
for the week, so the link people have opens the new rendering and the
channel is not posted to again. The channel message is left alone: it
carries the summary and the canvas link, and both still hold.

Reads the edition file in editions/ exactly as run_monday would (H1
stripped; the canvas has a title). Uses config/secrets.yaml locally.
"""

import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import publish


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    week = argv[0]
    conn = sqlite3.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    row = conn.execute("SELECT canvas_id, published_at FROM publish_log WHERE week = ?",
                       (week,)).fetchone()
    if not row or not row[0]:
        print("no canvas recorded for w/c {0}; nothing to rewrite".format(week))
        return 1
    canvas_id, published_at = row
    path = os.path.join(ROOT, "editions", "parliamentary-monitor-{0}.md".format(week))
    with open(path, encoding="utf-8") as handle:
        markdown = handle.read()
    canvas_md = re.sub(r"^# Parliamentary Monitor\n", "", markdown, count=1)

    secrets = publish.load_secrets()
    token = secrets.get("slack_bot_token")
    if not token:
        print("slack_bot_token missing from config/secrets.yaml")
        return 1
    auth = {"Authorization": "Bearer {0}".format(token)}
    result = publish._post_json("https://slack.com/api/canvases.edit", {
        "canvas_id": canvas_id,
        "changes": [{"operation": "replace",
                     "document_content": {"type": "markdown", "markdown": canvas_md}}],
    }, auth)
    if not result.get("ok"):
        print("canvases.edit failed: {0}".format(result.get("error")))
        return 1
    team = secrets.get("slack_team_id", "T066M0LAJ")
    print("canvas {0} (first published {1}) rewritten from {2}: {3} words\n"
          "https://citizengo.slack.com/docs/{4}/{0}".format(
              canvas_id, published_at, os.path.relpath(path, ROOT),
              len(canvas_md.split()), team))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
