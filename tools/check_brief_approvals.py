"""Read the outcome of Campaigns Brief approval tasks and act on it.

    python3 tools/check_brief_approvals.py

Runs in the Monday pipeline. Each generated brief has a native Asana
APPROVAL task (resource_subtype "approval") in the EN GB Weekly Meeting
agenda project; the verdict is the approval_status set by the Approve /
Request changes / Reject buttons.

  pending            -> nothing happens
  approved           -> status recorded; the normal Asana submission form
                        takes it forward from here
  rejected           -> files move to briefs/archive/ and the slug is
                        never regenerated (make_briefs refuses --force)
  changes_requested  -> flagged for a human conversation; nothing automatic

Legacy fallback: a plain task completed with an APPROVED/REJECTED comment
still counts (how the loop worked before tasks were approvals).

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
    """(decided, 'approved'|'rejected'|'changes_requested'|None)."""
    task = _get("https://app.asana.com/api/1.0/tasks/{0}"
                "?opt_fields=completed,resource_subtype,approval_status"
                .format(gid), secrets["asana_pat"]).get("data") or {}
    if task.get("resource_subtype") == "approval":
        status = task.get("approval_status")
        if status in ("approved", "rejected", "changes_requested"):
            return True, status
        return False, None
    # legacy comment convention
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
    for suffix in (".md", ".csv", "-5ca.csv", "-sheet.csv"):
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
        elif decision == "changes_requested":
            print("  CHANGES REQUESTED: {0} - waiting on a human conversation, "
                  "nothing automatic".format(r["slug"]))
        else:
            print("  {0}: task completed but no readable verdict - leaving "
                  "pending for a human".format(r["slug"]))
    conn.commit()
    still = conn.execute("SELECT COUNT(*) FROM brief_log WHERE status = 'pending'"
                         ).fetchone()[0]
    print("brief approvals: {0} still pending".format(still))
    return 0


if __name__ == "__main__":
    sys.exit(main())
