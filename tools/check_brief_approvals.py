"""Read the outcome of Campaigns Brief approval tasks and act on it.

    python3 tools/check_brief_approvals.py

Runs in the Monday pipeline. Each generated brief has an Asana approval
task (EN GB Weekly Meeting agenda project) whose convention is stated in
the task: complete it with a comment saying APPROVED or REJECTED.

  pending   task not completed yet -> nothing happens
  approved  completed, latest substantive comment contains "approv"
            -> status recorded; the brief stays where it is (the normal
               Asana submission form takes it forward from here)
  rejected  completed, latest substantive comment contains "reject"
            -> the brief's files move to briefs/archive/ and the slug is
               never regenerated (make_briefs refuses --force on it)
  unclear   completed with no readable verdict -> flagged in the log for
            a human, nothing destructive happens

Archiving moves files, never deletes them.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, publish

BRIEFS_DIR = os.path.join(ROOT, "briefs")
ARCHIVE_DIR = os.path.join(BRIEFS_DIR, "archive")


def _get(url, pat):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + pat})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def verdict(secrets, gid):
    """(completed, 'approved'|'rejected'|None) from the task and its stories."""
    task = _get("https://app.asana.com/api/1.0/tasks/{0}?opt_fields=completed"
                .format(gid), secrets["asana_pat"]).get("data") or {}
    if not task.get("completed"):
        return False, None
    stories = _get("https://app.asana.com/api/1.0/tasks/{0}/stories"
                   "?opt_fields=type,text&limit=100".format(gid),
                   secrets["asana_pat"]).get("data") or []
    comments = [s.get("text", "") for s in stories if s.get("type") == "comment"]
    for text in reversed(comments):  # latest verdict wins
        low = text.lower()
        if "reject" in low:
            return True, "rejected"
        if "approv" in low:
            return True, "approved"
    return True, None


def archive(slug):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    moved = 0
    for suffix in (".md", ".csv", "-5ca.csv"):
        src = os.path.join(BRIEFS_DIR, slug + suffix)
        if os.path.exists(src):
            shutil.move(src, os.path.join(ARCHIVE_DIR, slug + suffix))
            moved += 1
    return moved


def main():
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    secrets = publish.load_secrets()
    rows = conn.execute("SELECT slug, subject, asana_gid FROM brief_log "
                        "WHERE status = 'pending' AND asana_gid IS NOT NULL").fetchall()
    if not rows:
        print("brief approvals: none pending")
        return 0
    for r in rows:
        try:
            completed, decision = verdict(secrets, r["asana_gid"])
        except Exception as exc:
            print("  {0}: check failed ({1})".format(r["slug"], exc))
            continue
        if not completed:
            continue
        if decision == "rejected":
            moved = archive(r["slug"])
            conn.execute("UPDATE brief_log SET status = 'rejected' WHERE slug = ?",
                         (r["slug"],))
            print("  REJECTED: {0} - {1} file(s) archived, never regenerated"
                  .format(r["slug"], moved))
        elif decision == "approved":
            conn.execute("UPDATE brief_log SET status = 'approved' WHERE slug = ?",
                         (r["slug"],))
            print("  approved: {0}".format(r["slug"]))
        else:
            print("  {0}: task completed but no APPROVED/REJECTED comment found "
                  "- leaving pending for a human".format(r["slug"]))
    conn.commit()
    still = conn.execute("SELECT COUNT(*) FROM brief_log WHERE status = 'pending'"
                         ).fetchone()[0]
    print("brief approvals: {0} still pending".format(still))
    return 0


if __name__ == "__main__":
    sys.exit(main())
