"""Unattended publishing: Slack (message + canvas) and Asana (reading task).

Credentials come from config/secrets.yaml (gitignored):

    anthropic_api_key: sk-ant-...        # live triage (used by triage.py)
    slack_bot_token: xoxb-...            # chat:write + canvases:write + canvases:read
    slack_channel_id: C9RH217PZ          # #campaigns-en-gb
    asana_pat: 2/...                     # personal access token
    asana_workspace: "826488630492934"

Every function takes an injectable `transport` so tests never touch the
network. A missing credential makes the step report itself skipped rather
than raise: the Monday run must always produce the edition, and disclose
what it could not publish.
"""

from __future__ import annotations

import json
import os
import urllib.request

SECRETS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "secrets.yaml")


def load_secrets(path=None):
    import yaml
    path = path or SECRETS_PATH
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _post_json(url, payload, headers, timeout=30):  # pragma: no cover - network
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8", **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


# -- Slack --------------------------------------------------------------------

def slack_publish_edition(secrets, week, edition_number, canvas_markdown, summary_mrkdwn,
                          transport=None):
    """Create a canvas holding the full edition, grant the channel access,
    and post the summary message linking it. Returns a status dict."""
    token = secrets.get("slack_bot_token")
    channel = secrets.get("slack_channel_id")
    if not token or not channel:
        return {"skipped": "slack_bot_token/slack_channel_id missing from config/secrets.yaml"}
    transport = transport or _post_json
    auth = {"Authorization": "Bearer {0}".format(token)}

    canvas = transport("https://slack.com/api/canvases.create", {
        "title": "Parliamentary Monitor - week commencing {0} (Edition {1})".format(week, edition_number),
        "document_content": {"type": "markdown", "markdown": canvas_markdown},
    }, auth)
    if not canvas.get("ok"):
        return {"error": "canvases.create failed: {0}".format(canvas.get("error"))}
    canvas_id = canvas["canvas_id"]

    access = transport("https://slack.com/api/canvases.access.set", {
        "canvas_id": canvas_id, "access_level": "read", "channel_ids": [channel],
    }, auth)
    if not access.get("ok"):
        return {"error": "canvases.access.set failed: {0}".format(access.get("error"))}

    team = secrets.get("slack_team_id", "T066M0LAJ")
    canvas_url = "https://citizengo.slack.com/docs/{0}/{1}".format(team, canvas_id)
    message = transport("https://slack.com/api/chat.postMessage", {
        "channel": channel,
        "text": summary_mrkdwn + "\n\nFull edition: " + canvas_url,
        "unfurl_links": False,
    }, auth)
    if not message.get("ok"):
        return {"error": "chat.postMessage failed: {0}".format(message.get("error"))}
    return {"canvas_id": canvas_id, "canvas_url": canvas_url, "message_ts": message.get("ts")}


def slack_publish_canvas(secrets, title, canvas_markdown, summary_mrkdwn,
                         transport=None):
    """Post any canvas to the channel: 5CA sheets, briefings, one-offs.

    Same three-step dance as the weekly edition (create, grant channel read,
    post the linking message), without the edition-specific titling.
    """
    token = secrets.get("slack_bot_token")
    channel = secrets.get("slack_channel_id")
    if not token or not channel:
        return {"skipped": "slack_bot_token/slack_channel_id missing from config/secrets.yaml"}
    transport = transport or _post_json
    auth = {"Authorization": "Bearer {0}".format(token)}

    canvas = transport("https://slack.com/api/canvases.create", {
        "title": title,
        "document_content": {"type": "markdown", "markdown": canvas_markdown},
    }, auth)
    if not canvas.get("ok"):
        return {"error": "canvases.create failed: {0}".format(canvas.get("error"))}
    canvas_id = canvas["canvas_id"]

    access = transport("https://slack.com/api/canvases.access.set", {
        "canvas_id": canvas_id, "access_level": "read", "channel_ids": [channel],
    }, auth)
    if not access.get("ok"):
        return {"error": "canvases.access.set failed: {0}".format(access.get("error"))}

    team = secrets.get("slack_team_id", "T066M0LAJ")
    canvas_url = "https://citizengo.slack.com/docs/{0}/{1}".format(team, canvas_id)
    message = transport("https://slack.com/api/chat.postMessage", {
        "channel": channel,
        "text": summary_mrkdwn + "\n\n" + canvas_url,
        "unfurl_links": False,
    }, auth)
    if not message.get("ok"):
        return {"error": "chat.postMessage failed: {0}".format(message.get("error"))}
    return {"canvas_id": canvas_id, "canvas_url": canvas_url, "message_ts": message.get("ts")}


# -- Asana --------------------------------------------------------------------

BRIEF_APPROVAL_PROJECT = "1211423235936092"  # EN GB Weekly Meeting agenda


def asana_create_brief_approval(secrets, subject, slug, deadline=None,
                                transport=None):
    """Approval task for a generated Campaigns Brief draft.

    Convention stated in the task itself: complete WITH A COMMENT saying
    "approved" to take it forward or "rejected" to archive it; the Monday
    run reads the outcome (tools/check_brief_approvals.py) and a rejected
    brief is archived and never touched again.
    """
    transport = transport or _post_json
    notes = ("An automated Campaigns Brief draft is ready for review.\n\n"
             "Subject: {0}\n"
             "Files: briefs/{1}.md (readable), briefs/{1}.csv (Brief tab "
             "paste-in), briefs/{1}-5ca.csv (Five Columns Analysis tab)\n\n"
             "Use the approval buttons: Approve takes it forward via the "
             "normal Asana submission form; Reject archives the draft and it "
             "is never regenerated. 'Request changes' pauses it for a human "
             "conversation - nothing automatic happens."
             ).format(subject, slug)
    payload = {"data": {
        "name": "Review Campaigns Brief draft: {0}".format(subject[:120]),
        "notes": notes,
        "resource_subtype": "approval",
        "projects": [BRIEF_APPROVAL_PROJECT],
        "assignee": "cjoyce@citizengo.net",
    }}
    if deadline:
        payload["data"]["due_on"] = deadline
    reply = transport("https://app.asana.com/api/1.0/tasks", payload,
                      {"Authorization": "Bearer " + secrets["asana_pat"],
                       "Content-Type": "application/json"})
    data = reply.get("data") or {}
    if not data.get("gid"):
        return {"error": "task create failed: {0}".format(reply.get("errors"))}
    return {"task_gid": data["gid"],
            "permalink": data.get("permalink_url", "")}


def asana_create_reading_task(secrets, week, canvas_url, act_lines, deadline_lines,
                              transport=None):
    """Create the week's reading task in My Tasks. Returns a status dict."""
    pat = secrets.get("asana_pat")
    workspace = secrets.get("asana_workspace")
    if not pat or not workspace:
        return {"skipped": "asana_pat/asana_workspace missing from config/secrets.yaml"}
    transport = transport or _post_json

    acts = "".join("<li>{0}</li>".format(a) for a in act_lines) or "<li>None this week.</li>"
    deadlines = "".join("<li>{0}</li>".format(d) for d in deadline_lines) or "<li>None within three weeks.</li>"
    notes = ("<body>Weekly parliamentary briefing for the UK campaigns.\n\n"
             "<strong>This week's edition:</strong> <a href=\"{url}\">Parliamentary Monitor, w/c {week}</a> "
             "(also posted in #campaigns-en-gb).\n\n"
             "<strong>ACT items:</strong>\n<ul>{acts}</ul>\n"
             "<strong>Deadlines within 3 weeks:</strong>\n<ul>{deadlines}</ul>\n"
             "<strong>Reading checklist:</strong>\n<ul>"
             "<li>Scan the Movement column on the bills board for anything marked ▲ moved or NEW</li>"
             "<li>Check every [ACT] item has an owner and is progressing</li>"
             "<li>Review consultation deadlines within the next 3 weeks</li>"
             "<li>Decide any held-at-NOTE items</li></ul>\n"
             "<em>Created automatically by the Monday publish run.</em></body>").format(
                 url=canvas_url, week=week, acts=acts, deadlines=deadlines)

    reply = transport("https://app.asana.com/api/1.0/tasks", {"data": {
        "name": "Read the Parliamentary Monitor - w/c {0}".format(week),
        "assignee": "me",
        "workspace": workspace,
        "due_on": week,
        "html_notes": notes,
    }}, {"Authorization": "Bearer {0}".format(pat)})
    data = reply.get("data") or {}
    if not data.get("gid"):
        return {"error": "asana task creation failed: {0}".format(reply.get("errors"))}
    return {"task_gid": data["gid"], "permalink": data.get("permalink_url")}
