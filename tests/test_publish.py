"""Monday publish chain: secrets handling, Slack/Asana payloads, summary build."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import run_monday
from src import publish

# The current render shape: score-driven, no editorial tags, no owners
# (the loop was retired at Christopher's decision, 2026-08-21).
EDITION = """# Parliamentary Monitor
### Week commencing Monday 2026-08-10 | Edition 2

## Top lines

- Recess: neither House sits this week. Both Houses return 2026-09-01.
- [Law Commission weddings reform closes 24 September.](https://example.gov.uk/tying) (Deadline: 2026-09-24)

## Consultations and secondary legislation

- [Child protection framework.](https://example.gov.uk/cp) (Deadline: 2026-08-20)
"""


class SummariseTests(unittest.TestCase):
    def test_summary_quotes_top_lines_untagged_and_unlinked(self):
        summary, acts, deadlines = run_monday.summarise_edition(EDITION, "2026-08-10")
        self.assertIn("*Parliamentary Monitor - week commencing 2026-08-10*", summary)
        self.assertIn("• Recess", summary)
        self.assertIn("• Law Commission weddings reform", summary)
        self.assertNotIn("[ACT]", summary)
        self.assertNotIn("](https://", summary)          # links stripped for mrkdwn
        self.assertEqual(acts, [])                       # the reading task is retired

    def test_deadlines_come_from_store_within_horizon(self):
        from src import db
        conn = db.init_db(db.connect(":memory:"))
        try:
            for i, (title, deadline, score) in enumerate([
                ("Near thing", "2026-08-20", 2),      # within 21 days
                ("Far thing", "2026-12-01", 2),       # beyond horizon
                ("Sub-digest thing", "2026-08-15", 1),  # score below the bar
            ]):
                conn.execute(
                    "INSERT INTO items (id, captured_at, source_feed, item_type, title, deadline, triage_score) "
                    "VALUES (?, '2026-08-10', 'consultation', 'consultation', ?, ?, ?)",
                    ("t:%d" % i, title, deadline, score))
            conn.commit()
            deadlines = run_monday.deadlines_from_store(conn, "2026-08-10")
            self.assertEqual(deadlines, ["Near thing (closes 2026-08-20)"])
        finally:
            conn.close()


class SlackPublishTests(unittest.TestCase):
    def test_missing_credentials_skip_not_raise(self):
        result = publish.slack_publish_edition({}, "2026-08-10", 2, "body", "summary")
        self.assertIn("skipped", result)

    def test_happy_path_calls_three_apis_in_order(self):
        calls = []

        def transport(url, payload, headers):
            calls.append((url, payload))
            if url.endswith("canvases.create"):
                return {"ok": True, "canvas_id": "F123"}
            return {"ok": True, "ts": "1.2"}

        secrets = {"slack_bot_token": "xoxb-x", "slack_channel_id": "C1", "slack_team_id": "T1"}
        result = publish.slack_publish_edition(secrets, "2026-08-10", 2, "body", "summary",
                                               transport=transport)
        self.assertEqual([u.rsplit("/", 1)[1] for u, _ in calls],
                         ["canvases.create", "canvases.access.set", "chat.postMessage"])
        self.assertEqual(result["canvas_url"], "https://citizengo.slack.com/docs/T1/F123")
        self.assertIn("Full edition: https://citizengo.slack.com/docs/T1/F123",
                      calls[2][1]["text"])

    def test_preview_canvas_is_shared_with_the_one_user_and_linked_from_the_dm(self):
        calls = []

        def transport(url, payload, headers):
            calls.append((url, payload))
            if url.endswith("canvases.create"):
                return {"ok": True, "canvas_id": "F9"}
            return {"ok": True, "ts": "1.3"}

        secrets = {"slack_bot_token": "xoxb-x", "slack_channel_id": "C1", "slack_dm_user_id": "U7", "slack_team_id": "T1"}
        result = publish.slack_preview_canvas(secrets, "PREVIEW: t", "body", "summary", transport=transport)
        self.assertEqual([u.rsplit("/", 1)[1] for u, _ in calls],
                         ["canvases.create", "canvases.access.set", "chat.postMessage"])
        self.assertEqual(calls[1][1]["user_ids"], ["U7"])
        self.assertNotIn("channel_ids", calls[1][1])          # the channel is never granted access
        self.assertEqual(calls[2][1]["channel"], "U7")
        self.assertEqual(result["canvas_url"], "https://citizengo.slack.com/docs/T1/F9")

    def test_preview_without_a_dm_recipient_skips(self):
        self.assertIn("skipped", publish.slack_preview_canvas({"slack_bot_token": "x"}, "t", "b", "s"))

    def test_api_error_surfaces(self):
        def transport(url, payload, headers):
            return {"ok": False, "error": "missing_scope"}

        secrets = {"slack_bot_token": "x", "slack_channel_id": "C1"}
        result = publish.slack_publish_edition(secrets, "w", 1, "b", "s", transport=transport)
        self.assertIn("missing_scope", result["error"])


class AsanaPublishTests(unittest.TestCase):
    def test_missing_credentials_skip_not_raise(self):
        result = publish.asana_create_reading_task({}, "2026-08-10", "url", [], [])
        self.assertIn("skipped", result)

    def test_task_payload_shape(self):
        captured = {}

        def transport(url, payload, headers):
            captured["url"] = url
            captured["payload"] = payload
            return {"data": {"gid": "42", "permalink_url": "https://app.asana.com/x"}}

        secrets = {"asana_pat": "2/x", "asana_workspace": "826"}
        result = publish.asana_create_reading_task(
            secrets, "2026-08-10", "https://canvas", ["An ACT (Owner: Z)"], ["A deadline"],
            transport=transport)
        data = captured["payload"]["data"]
        self.assertEqual(data["due_on"], "2026-08-10")
        self.assertEqual(data["assignee"], "me")
        self.assertIn("An ACT (Owner: Z)", data["html_notes"])
        self.assertIn("A deadline", data["html_notes"])
        self.assertEqual(result["task_gid"], "42")


if __name__ == "__main__":
    unittest.main()


class SlackDmTests(unittest.TestCase):
    """DM delivery for the weekly UN calls."""

    def test_posts_straight_to_the_user_id(self):
        calls = []

        def transport(url, payload, headers):
            calls.append((url, payload))
            return {"ok": True, "ts": "1.2"}

        result = publish.slack_dm(
            {"slack_bot_token": "xoxb-x", "slack_dm_user_id": "U123"},
            "hello", transport=transport)
        self.assertEqual(result["message_ts"], "1.2")
        # One call, not two: conversations.open needs im:write, which this
        # app does not have (measured 2026-08-17).
        self.assertEqual(len(calls), 1)
        self.assertIn("chat.postMessage", calls[0][0])
        self.assertEqual(calls[0][1]["channel"], "U123")

    def test_missing_recipient_is_skipped_not_raised(self):
        result = publish.slack_dm({"slack_bot_token": "xoxb-x"}, "hello",
                                  transport=lambda *a: {"ok": True})
        self.assertIn("skipped", result)

    def test_error_names_the_scope_fix(self):
        result = publish.slack_dm(
            {"slack_bot_token": "x", "slack_dm_user_id": "U1"}, "hi",
            transport=lambda *a: {"ok": False, "error": "channel_not_found"})
        self.assertIn("im:write", result["error"])
