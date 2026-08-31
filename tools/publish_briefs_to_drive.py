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
reach is exactly one folder.

The folder MUST live in a Shared Drive. A service account has no Drive
storage quota of its own, so creating a file in a My Drive folder fails with
"The user's Drive storage quota has been exceeded" no matter how much space
the human owner has (observed 2026-08-15). In a Shared Drive the files are
owned by the drive, not the account, and the quota question disappears. The key is read from, in order:
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
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

BRIEFS_DIR = os.path.join(ROOT, "briefs")
KEY_PATH = os.path.join(ROOT, "config", "google-service-account.json")
FOLDER_ID = "0AD06aVPwSAYYUk9PVA"      # Automated Briefs SHARED DRIVE
TEMPLATE_ID = "1tllzaKWVeCSLKJiqTRaKmzKk3HePcKDij2CTkBbSZSY"  # styled master, in the shared drive
OWNER_EMAIL = "cjoyce@citizengo.net"
SCOPES = ["https://www.googleapis.com/auth/drive",
          "https://www.googleapis.com/auth/spreadsheets"]

# Which generated file feeds which tab. Tab matching is by substring against
# the template's real tab names, discovered at run time -- never by index,
# because a template edit that reorders tabs would then silently write the
# 5CA into the brief.
TAB_SOURCES = [
    # The brief itself lives on the template's FIRST tab, named for the email
    # series it plans ("AA Classical Series" = audience acquisition). Matched
    # by name with a first-tab fallback, so renaming it does not silently
    # write the brief nowhere.
    (("aa classical series", "default brief"), "{slug}.csv"),
    (("five column", "5ca", "column analysis"), "{slug}-5ca.csv"),
    (("campaign narrative", "narrative"), "{slug}-narrative.csv"),
]

# Tabs kept in a generated brief. Everything else in the template is a
# relaunch or fundraising variant belonging to a later campaign stage, and
# Christopher asked for the brief plus 5CA and narrative only. "Values" is
# kept deliberately though unasked: it backs the dropdown validation on the
# brief tab, and deleting it turns Type of Campaign and Topic into free text.
KEEP_TAB_HINTS = ("aa classical series", "default brief", "five column",
                  "campaign narrative", "values")


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
        from google.auth import crypt, jwt
    except ImportError:
        return None, "google-auth is not installed (pip install google-auth)"
    # The secret may arrive base64-encoded: multiline JSON secrets are
    # often stored that way, and that is exactly how CI's copy failed on
    # 2026-08-31 -- "Expecting value: line 1 column 1" from a non-empty
    # value that was not JSON. Accept either form, and when neither
    # parses, say WHAT was wrong rather than re-raising json's riddle.
    raw = raw.strip()
    if not raw.startswith("{"):
        import base64
        try:
            decoded = base64.b64decode(raw, validate=True).decode("utf-8")
            if decoded.strip().startswith("{"):
                raw = decoded.strip()
        except Exception:
            pass
    if not raw.startswith("{"):
        return None, ("service account key is neither JSON nor base64 JSON "
                      "(starts {0!r}): re-set the secret from "
                      "config/google-service-account.json".format(raw[:8]))
    try:
        # The JWT-bearer flow by hand: google-auth's own transports pull in
        # requests or urllib3, and the rest of this project speaks urllib.
        # Signing is the only part that genuinely needs a crypto library.
        import time
        import urllib.parse
        info = json.loads(raw)
        now = int(time.time())
        signer = crypt.RSASigner.from_service_account_info(info)
        assertion = jwt.encode(signer, {
            "iss": info["client_email"], "scope": " ".join(SCOPES),
            "aud": info["token_uri"], "iat": now, "exp": now + 3600,
        })
        body = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion.decode() if isinstance(assertion, bytes) else assertion,
        }).encode()
        request = urllib.request.Request(
            info["token_uri"], data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())["access_token"], None
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode()[:300]
        except Exception:
            pass
        return None, "token request failed: HTTP {0} {1}".format(exc.code, detail)
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


def a1(tab_title, cell="A1"):
    """Quote a tab name for an A1 range (tab names contain spaces)."""
    return "'{0}'!{1}".format(tab_title.replace("'", "''"), cell)


def parse_brief_csv(rows):
    """The generated brief CSV as (header_values, {label: value}, rf4, timeline).

    Values are placed against the TEMPLATE's own labels rather than written
    as a block from A1: the template merges cells in the Red Fox Four block,
    so a block write lands a row out and separates each RF number from its
    question (seen live, 2026-08-15).
    """
    header, fields, rf4, timeline = [], {}, {}, []
    section = None
    for row in rows:
        if not row or not row[0]:
            continue
        key = row[0].strip()
        if key == "Campaign Name":
            section = "header"
            continue
        if section == "header" and not header:
            header = row
            section = None
            continue
        if key.startswith("RF#"):
            rf4[key] = row[3] if len(row) > 3 else ""
            continue
        if key in ("TIMELINE OF MAJOR ACTIONS", "Date"):
            section = "timeline" if key == "Date" else section
            continue
        if key in ("EVALUATE DASHBOARD", "RED FOX FOUR", "PLAN STAGE"):
            section = None
            continue
        if section == "timeline":
            timeline.append(row[:3])
            continue
        if len(row) > 1 and row[1]:
            fields[key] = row[1]
    return header, fields, rf4, timeline


def norm_label(text):
    return " ".join((text or "").lower().replace("\u20ac", "").split())[:40]


# 5CA columns, zero-based: A Decision-Maker, B # Seats, C-G gradient,
# H Target, I Comments, J Vote, K Comments.
COMMENTS_COLS = (8, 10)


def polish_5ca(token, file_id, tab_title, sheet_id, last_row):
    """Clip the Comments columns and carry the row formatting to the bottom.

    Two problems a plain values write leaves behind: the evidence in Comments
    is long enough to spill across the sheet unless the column clips it, and
    the template only styles its handful of sample rows, so a 650-member 5CA
    runs off the end of the banding (Christopher, 2026-08-16).
    """
    requests = [{
        # Take the first data row's formatting and carry it down.
        "copyPaste": {
            "source": {"sheetId": sheet_id, "startRowIndex": 3,
                       "endRowIndex": 4, "startColumnIndex": 0,
                       "endColumnIndex": 11},
            "destination": {"sheetId": sheet_id, "startRowIndex": 3,
                            "endRowIndex": last_row, "startColumnIndex": 0,
                            "endColumnIndex": 11},
            "pasteType": "PASTE_FORMAT",
        }
    }]
    for col in COMMENTS_COLS:
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 2,
                      "endRowIndex": last_row, "startColumnIndex": col,
                      "endColumnIndex": col + 1},
            "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}},
            "fields": "userEnteredFormat.wrapStrategy",
        }})
    api(token, "https://sheets.googleapis.com/v4/spreadsheets/{0}:batchUpdate"
               .format(file_id), {"requests": requests})


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

    # Drop the relaunch/fundraising variants: a new brief needs the brief,
    # the 5CA and the narrative, nothing else.
    props = {s["properties"]["title"]: s["properties"]["sheetId"]
             for s in meta.get("sheets", [])}
    doomed = [sid for title, sid in props.items()
              if not any(h in title.lower() for h in KEEP_TAB_HINTS)]
    if doomed:
        api(token, "https://sheets.googleapis.com/v4/spreadsheets/{0}"
                   ":batchUpdate".format(file_id),
            {"requests": [{"deleteSheet": {"sheetId": sid}} for sid in doomed]})
        tabs = [t for t in tabs if props[t] not in doomed]

    updates, filled, unmatched = [], [], []
    for keys, rows in sources.items():
        match = next((t for t in tabs
                      if any(k in t.lower() for k in keys)), None)
        if not match and keys[0] == "aa classical series" and tabs:
            match = tabs[0]  # the brief tab, whatever it has been renamed to
        if not match:
            unmatched.append(keys[0])
            continue

        if keys[0] == "aa classical series":
            # Label-driven: read the template's own rows and write each value
            # beside its label, never as a block.
            got = api(token, "https://sheets.googleapis.com/v4/spreadsheets/{0}"
                             "/values/{1}".format(
                                 file_id, urllib.parse.quote(a1(match, "A1:A80"))))
            labels = {norm_label(r[0]): i + 1
                      for i, r in enumerate(got.get("values", [])) if r and r[0]}
            header, fields, rf4, timeline = parse_brief_csv(rows)
            if header:
                updates.append({"range": a1(match, "A2"), "values": [header]})
            for label, value in fields.items():
                row_no = labels.get(norm_label(label))
                if row_no:
                    updates.append({"range": a1(match, "B{0}".format(row_no)),
                                    "values": [[value]]})
                else:
                    unmatched.append("field: " + label[:38])
            for code, hint in rf4.items():          # hint belongs in Comments
                row_no = labels.get(norm_label(code))
                if row_no:
                    updates.append({"range": a1(match, "D{0}".format(row_no)),
                                    "values": [[hint]]})
            start = labels.get("date")
            if start and timeline:
                updates.append({"range": a1(match, "A{0}".format(start + 1)),
                                "values": [r + [""] * (3 - len(r)) for r in timeline]})
            filled.append(match)
            continue

        # 5CA and narrative are tables: write below the template's header row
        # rather than over it.
        anchor = 4 if keys[0] == "five column" else 1
        body = [r for r in rows if r and r[0] not in
                ("FIVE COLUMNS ANALYSIS (ONLY IF APPROPRIATE)", "PLAN STAGE",
                 "Decision-Maker", "CAMPAIGN NARRATIVE")]
        if not body:
            continue
        width = max(len(r) for r in body)
        updates.append({"range": a1(match, "A{0}".format(anchor)),
                        "values": [r + [""] * (width - len(r)) for r in body]})
        filled.append(match)
    if updates:
        api(token, "https://sheets.googleapis.com/v4/spreadsheets/{0}/values"
                   ":batchUpdate".format(file_id),
            {"valueInputOption": "RAW", "data": updates})

    fca_tab = next((t for t in tabs if "five column" in t.lower()), None)
    if fca_tab:
        rows_written = len(sources.get(("five column", "5ca", "column analysis"), []))
        polish_5ca(token, file_id, fca_tab, props[fca_tab],
                   max(rows_written + 4, 12))

    # A service account owns what it creates; without this the team cannot
    # edit its own brief.
    api(token, "https://www.googleapis.com/drive/v3/files/{0}/permissions"
               "?sendNotificationEmail=false&supportsAllDrives=true".format(file_id),
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
                        "WHERE status IN ('pending','generated') "
                        "AND drive_file_id IS NULL"
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
