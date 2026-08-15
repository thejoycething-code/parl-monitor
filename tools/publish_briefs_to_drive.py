"""Publish generated Campaigns Briefs into Drive as properly styled Sheets.

    python3 tools/publish_briefs_to_drive.py            # pending briefs
    python3 tools/publish_briefs_to_drive.py --dry-run  # show what would happen

Copies the styled brief TEMPLATE (formatting, merges, colour conventions and
tabs intact) once per brief, then writes the generated values into its tabs.
A CSV upload cannot do this: it produces a populated but unstyled sheet, and
duplicating the template alone produces a styled but empty one. Only the
Sheets API gives both.

Auth: a Google service account with the Sheets and Drive APIs enabled, and
EDITOR access to the target folder only -- no project-level roles, so its
reach is exactly one folder. The key is read from, in order:
  * GOOGLE_SERVICE_ACCOUNT_JSON (env, the whole JSON) -- how CI supplies it
  * config/google-service-account.json (git-ignored) -- how a laptop does

Each new sheet is shared back to OWNER_EMAIL as writer immediately: files
created by a service account are owned by the service account, and a brief
nobody in the team can edit is worse than no brief.

Idempotent: brief_log.drive_file_id records what has been published, so a
re-run publishes only what is new. A brief rejected at approval has its
sheet trashed (recoverable from Drive's bin) alongside the local archive.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

BRIEFS_DIR = os.path.join(ROOT, "briefs")
KEY_PATH = os.path.join(ROOT, "config", "google-service-account.json")
FOLDER_ID = "17fzLEauzkVhanrIRNZkq09IkKlwFzeL3"          # Automated Briefs
TEMPLATE_ID = "116QJt2pTnY3YRUaE2sGp3N6rOHHYCBhQY0jmCnSwUlQ"  # styled master
OWNER_EMAIL = "cjoyce@citizengo.net"
SCOPES = ["https://www.googleapis.com/auth/drive",
          "https://www.googleapis.com/auth/spreadsheets"]

# Which generated file feeds which tab. Tab matching is by substring against
# the template's real tab names, discovered at run time -- never by index,
# because a template edit that reorders tabs would then silently write the
# 5CA into the brief.
TAB_SOURCES = [
    (("default brief", "brief"), "{slug}.csv"),
    (("five column", "5ca", "column analysis"), "{slug}-5ca.csv"),
    (("narrative",), "{slug}-narrative.csv"),
]


def load_credentials():
    """Access token from the service account key, or None with a reason."""
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw and os.path.exists(KEY_PATH):
        with open(KEY_PATH, encoding="utf-8") as handle:
            raw = handle.read()
    if not raw:
        return None, ("no service account key: set GOOGLE_SERVICE_ACCOUNT_JSON "
                      "or place config/google-service-account.json")
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests
    except ImportError:
        return None, "google-auth is not installed (pip install google-auth)"
    try:
        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES)
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token, None
    except Exception as exc:
        return None, "could not authenticate: {0}".format(exc)


def api(token, url, payload=None, method=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=data, method=method or ("POST" if data else "GET"),
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:400]
        except Exception:
            pass
        raise RuntimeError("HTTP {0}: {1}".format(exc.code, detail)) from exc


def read_csv_rows(path):
    import csv
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", newline="") as handle:
        return [row for row in csv.reader(handle)]


def a1(tab_title):
    """Quote a tab name for an A1 range (tab names contain spaces)."""
    return "'{0}'!A1".format(tab_title.replace("'", "''"))


def publish_one(token, slug, subject, dry_run=False):
    """Copy the template, fill its tabs, share it back. Returns (id, url)."""
    title = "{0} EN GB Brief DRAFT: {1}".format(
        __import__("datetime").date.today().strftime("%Y-%m"), subject)[:180]
    sources = {}
    for keys, pattern in TAB_SOURCES:
        rows = read_csv_rows(os.path.join(BRIEFS_DIR, pattern.format(slug=slug)))
        if rows:
            sources[keys] = rows
    if not sources:
        return None, "no generated files for {0}".format(slug)
    if dry_run:
        return None, "would create '{0}' with {1} tab(s) filled".format(
            title, len(sources))

    copied = api(token, "https://www.googleapis.com/drive/v3/files/{0}/copy"
                        "?supportsAllDrives=true".format(TEMPLATE_ID),
                 {"name": title, "parents": [FOLDER_ID]})
    file_id = copied["id"]

    meta = api(token, "https://sheets.googleapis.com/v4/spreadsheets/{0}"
                      "?fields=sheets.properties".format(file_id))
    tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]

    updates, filled, unmatched = [], [], []
    for keys, rows in sources.items():
        match = next((t for t in tabs
                      if any(k in t.lower() for k in keys)), None)
        if not match:
            unmatched.append(keys[0])
            continue
        width = max(len(r) for r in rows)
        updates.append({"range": a1(match),
                        "values": [r + [""] * (width - len(r)) for r in rows]})
        filled.append(match)
    if updates:
        api(token, "https://sheets.googleapis.com/v4/spreadsheets/{0}/values"
                   ":batchUpdate".format(file_id),
            {"valueInputOption": "RAW", "data": updates})

    # A service account owns what it creates; without this the team cannot
    # edit its own brief.
    api(token, "https://www.googleapis.com/drive/v3/files/{0}/permissions"
               "?sendNotificationEmail=false".format(file_id),
        {"type": "user", "role": "writer", "emailAddress": OWNER_EMAIL})

    url = "https://docs.google.com/spreadsheets/d/{0}/edit".format(file_id)
    note = ""
    if unmatched:
        note = "  (no tab matched: {0} - content NOT written)".format(
            ", ".join(unmatched))
    return file_id, "{0}  tabs filled: {1}{2}".format(url, ", ".join(filled), note)


def main():
    dry_run = "--dry-run" in sys.argv
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    cols = [c[1] for c in conn.execute("PRAGMA table_info(brief_log)")]
    if "drive_file_id" not in cols:
        conn.execute("ALTER TABLE brief_log ADD COLUMN drive_file_id TEXT")
        conn.commit()

    token, why = (None, "dry run") if dry_run else load_credentials()
    if not dry_run and not token:
        print("drive publish skipped: {0}".format(why))
        return 0  # never fail the weekly run over a Drive credential

    rows = conn.execute("SELECT slug, subject, asana_gid FROM brief_log "
                        "WHERE status = 'pending' AND drive_file_id IS NULL"
                        ).fetchall()
    if not rows:
        print("drive publish: nothing new")
        return 0
    for r in rows:
        try:
            file_id, detail = publish_one(token, r["slug"], r["subject"], dry_run)
        except Exception as exc:
            print("  {0}: FAILED {1}".format(r["slug"], exc))
            continue
        print("  {0}: {1}".format(r["slug"][:46], detail))
        if file_id:
            conn.execute("UPDATE brief_log SET drive_file_id = ? WHERE slug = ?",
                         (file_id, r["slug"]))
            conn.commit()
            if r["asana_gid"]:
                try:
                    from src import publish as pub
                    secrets = pub.load_secrets()
                    pub._post_json(
                        "https://app.asana.com/api/1.0/tasks/{0}/stories".format(
                            r["asana_gid"]),
                        {"data": {"text": "Brief draft, formatted as a Campaigns "
                                          "Brief: https://docs.google.com/"
                                          "spreadsheets/d/{0}/edit\n\nDecide with "
                                          "the approval buttons on this task."
                                          .format(file_id)}},
                        {"Authorization": "Bearer " + secrets["asana_pat"],
                         "Content-Type": "application/json"})
                except Exception as exc:
                    print("    (could not link the Asana task: {0})".format(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
