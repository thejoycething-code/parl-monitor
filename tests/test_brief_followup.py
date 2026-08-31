"""Approval is not the finish line (Christopher, 2026-08-31).

An APPROVED verdict used to record a status and stop -- the brief could
silently die at 'approved'. Now it raises a follow-up task urging the
approver to refine the draft and submit it into CitizenGO's PPAE flow.
Once per brief: followup_gid guards repeats, and the sweep retries
failures on the next run rather than losing them.
"""

import importlib.util
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import publish


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "cba", os.path.join(ROOT, "tools", "check_brief_approvals.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cba = _load_checker()

SECRETS = {"asana_pat": "pat"}


def log_conn(rows):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE brief_log (slug TEXT PRIMARY KEY, subject TEXT,"
                 " generated_at TEXT, path TEXT, status TEXT, asana_gid TEXT,"
                 " drive_file_id TEXT, followup_gid TEXT)")
    conn.executemany(
        "INSERT INTO brief_log (slug, subject, status, asana_gid, "
        "drive_file_id, followup_gid) VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    return conn


class FollowupTaskTests(unittest.TestCase):
    """The task itself, via an injected transport."""

    def _create(self, **kwargs):
        calls = []

        def transport(url, payload, headers):
            calls.append((url, payload, headers))
            return {"data": {"gid": "42", "permalink_url": "https://asana/42"}}

        reply = publish.asana_create_ppae_followup(
            SECRETS, "Consultation on the RE Core Syllabus", "slug-re",
            transport=transport, **kwargs)
        return reply, calls[0][1]["data"]

    def test_the_task_urges_refine_then_ppae_submission(self):
        reply, data = self._create(deadline="2026-09-30",
                                   drive_url="https://sheets/x")
        self.assertEqual(reply["task_gid"], "42")
        self.assertEqual(
            data["name"],
            "Refine and submit to PPAE: Consultation on the RE Core Syllabus")
        self.assertEqual(data["projects"], [publish.BRIEF_APPROVAL_PROJECT])
        self.assertEqual(data["due_on"], "2026-09-30")
        self.assertIn("REFINE the draft", data["notes"])
        self.assertIn("SUBMIT the refined brief into the PPAE flow",
                      data["notes"])
        self.assertIn("https://sheets/x", data["notes"])

    def test_no_deadline_means_no_due_on_not_a_fabricated_one(self):
        _, data = self._create()
        self.assertNotIn("due_on", data)

    def test_a_failed_create_reports_an_error(self):
        reply = publish.asana_create_ppae_followup(
            SECRETS, "S", "s",
            transport=lambda *a: {"errors": [{"message": "boom"}]})
        self.assertIn("error", reply)


class FollowupSweepTests(unittest.TestCase):
    """The sweep: who gets a follow-up, and exactly once."""

    def _sweep(self, rows, create_reply=None):
        conn = log_conn(rows)
        created = []

        def create(secrets, subject, slug, deadline=None, drive_url=None):
            created.append({"slug": slug, "deadline": deadline,
                            "drive_url": drive_url})
            return create_reply or {"task_gid": "T-" + slug}

        def get(url, pat):
            return {"data": {"due_on": "2026-09-30"}}

        made = cba.followup_sweep(conn, SECRETS, create=create, get=get)
        return conn, created, made

    def test_an_approved_brief_gets_one_followup_with_the_sheet_linked(self):
        conn, created, made = self._sweep(
            [("re", "RE Syllabus", "approved", "A1", "FILE123", None)])
        self.assertEqual(made, 1)
        self.assertEqual(created[0]["deadline"], "2026-09-30")
        self.assertEqual(created[0]["drive_url"],
                         "https://docs.google.com/spreadsheets/d/FILE123/edit")
        gid = conn.execute("SELECT followup_gid FROM brief_log "
                           "WHERE slug = 're'").fetchone()[0]
        self.assertEqual(gid, "T-re")

    def test_a_brief_that_already_has_one_is_never_asked_twice(self):
        _, created, made = self._sweep(
            [("re", "RE", "approved", "A1", None, "T-existing")])
        self.assertEqual((created, made), ([], 0))

    def test_pending_and_rejected_briefs_get_nothing(self):
        _, created, _ = self._sweep(
            [("p", "P", "pending", "A1", None, None),
             ("r", "R", "rejected", "A2", None, None)])
        self.assertEqual(created, [])

    def test_a_failed_create_leaves_the_row_for_the_next_run(self):
        conn, _, made = self._sweep(
            [("re", "RE", "approved", "A1", None, None)],
            create_reply={"error": "asana down"})
        self.assertEqual(made, 0)
        gid = conn.execute("SELECT followup_gid FROM brief_log "
                           "WHERE slug = 're'").fetchone()[0]
        self.assertIsNone(gid)

    def test_pre_reinstatement_approvals_without_a_task_are_left_alone(self):
        # Briefs approved before the Asana loop existed have no approval
        # task to read a deadline from -- and no approver to nudge.
        _, created, _ = self._sweep(
            [("old", "Old", "approved", None, None, None)])
        self.assertEqual(created, [])


class TrashSheetTests(unittest.TestCase):
    def test_the_bin_call_supports_shared_drives(self):
        # Without supportsAllDrives the Drive API 404s on shared-drive
        # files as if they did not exist; the swallowed error left every
        # rejected brief's sheet live in Drive until 2026-08-31, when all
        # eleven were found unbinned and binned by hand.
        import inspect
        src = inspect.getsource(cba.trash_drive_sheet)
        self.assertIn("supportsAllDrives=true", src)


class ApprovalNotesTests(unittest.TestCase):
    def test_the_approval_task_now_promises_the_ppae_followup(self):
        calls = []

        def transport(url, payload, headers):
            calls.append(payload)
            return {"data": {"gid": "1"}}

        publish.asana_create_brief_approval(SECRETS, "S", "s",
                                            transport=transport)
        notes = calls[0]["data"]["notes"]
        self.assertIn("Approve raises a follow-up task to refine the brief "
                      "and submit it into the PPAE flow", notes)
        self.assertNotIn("normal Asana submission form", notes)


if __name__ == "__main__":
    unittest.main()
