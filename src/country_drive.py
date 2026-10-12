"""The new countries' campaign briefs and debate packs on Google Drive
(11 October 2026).

The UK puts each campaign brief into the Automated Briefs shared drive as a
styled Sheet copied from the brief template (tools/publish_briefs_to_drive.py)
and each debate pack's files into a folder of its own under "Debate footage"
in the same drive (src/drivepack.py). This does both for the new countries,
reusing that code, in one folder per country:

    Automated Briefs (shared drive)
      Country editions/
        Poland/
          Campaign briefs/   one Sheet per brief, from the template
          Debate packs/
            2026-10-20 <title>/   README.md, pack.md, checklist.md, members.csv

WHAT IS PUBLISHED. Only what exists in the repo: briefs/<cc>-<slug>.csv (and
its -5ca.csv once readings are confirmed) written by tools/country_briefs.py,
and data/packs/<cc>-<date>-<slug>/ written by tools/country_debate_pack.py.
A pack built as a SAMPLE (pack.json "sample": true) is never published. A
brief brief_log marks `rejected` is never published, and a sheet already made
for it goes to Drive's bin (recoverable for 30 days), as the UK's rejected
briefs do. Every brief is a DRAFT: the title says NOT READY until
tools/country_briefs.py says READY (the stance sign-off), and the sheet's Five
Column Analysis tab says "awaiting sign-off" rather than keeping the
template's sample rows.

NO DUPLICATES ON A RERUN. data/country-drive.json records each brief's sheet
and the fingerprint of the files it was filled from: an unchanged brief is
left alone, a refreshed one (tools/country_briefs.py rewrites unedited briefs
weekly) is rewritten in place, and a title that changes (NOT READY to READY)
is renamed, never copied again. Each sheet also carries its slug as a Drive
appProperty, so a lost ledger finds the sheets already made instead of making
new ones. Pack files are matched by name and MD5 in their folder, as
drivepack matches by size: unchanged files are skipped, a changed one is
binned and uploaded afresh.

Folders are found or created only through src/drivepack.find_or_create_folder
with the service account's own key (config/google-service-account.json or
GOOGLE_SERVICE_ACCOUNT_JSON), whose reach is the one shared drive. Each new
sheet is shared back to the owner as writer, as the UK's are. Nothing else is
shared, sent or posted.
"""

from __future__ import annotations

import datetime
import glob
import hashlib
import json
import os
import re
import sqlite3
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFS_DIR = os.path.join(ROOT, "briefs")
PACKS_DIR = os.path.join(ROOT, "data", "packs")
LEDGER = os.path.join(ROOT, "data", "country-drive.json")
ROOT_NAME = "Country editions"
BRIEFS_SUB = "Campaign briefs"
PACKS_SUB = "Debate packs"
PROP = "pm_country_brief"         # the appProperty that names a sheet's slug
MAX_NEW = 30                      # new sheets per run; the rest wait a week
PACK_SKIP = ("pack.json",)
FCA_NOTE = ("Awaiting sign-off: nobody is placed until CitizenGO's readings of "
            "these votes are confirmed by a named person (config/{cc}_stance.yaml). "
            "The brief tab says what waits.")
FOLDER_MIME = "application/vnd.google-apps.folder"


def countries():
    from src import country_debatepack as dp
    return dp.COUNTRIES


def country_name(cc):
    from src import country_debatepack as dp
    return dp.name_of(cc)


def sha_of(paths):
    h = hashlib.sha256()
    for p in paths:
        with open(p, "rb") as handle:
            h.update(os.path.basename(p).encode() + b"\0" + handle.read())
    return h.hexdigest()[:16]


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --- what exists locally ---------------------------------------------------

SUBJECT = re.compile(r"^#\s*Campaigns Brief[^:]*:\s*(.+?)\s*$")


def local_briefs(ccs=None, briefs_dir=BRIEFS_DIR):
    """[{slug, cc, csv, fca, subject, ready, sha}] for the new countries'
    briefs on disk, by country then slug."""
    ccs = set(ccs or countries())
    out = []
    for path in sorted(glob.glob(os.path.join(briefs_dir, "*.csv"))):
        slug = os.path.basename(path)[:-4]
        cc = slug.split("-", 1)[0]
        if cc not in ccs or slug.endswith(("-5ca", "-narrative", "-sheet")):
            continue
        md = os.path.join(briefs_dir, slug + ".md")
        subject, ready = slug, False
        if os.path.exists(md):
            with open(md, encoding="utf-8") as handle:
                text = handle.read()
            for line in text.splitlines()[:5]:
                m = SUBJECT.match(line)
                if m:
                    subject = m.group(1)
                    break
            ready = "NOT READY" not in text
        fca = os.path.join(briefs_dir, slug + "-5ca.csv")
        files = [path] + ([fca] if os.path.exists(fca) else [])
        out.append({"slug": slug, "cc": cc, "csv": path,
                    "fca": fca if os.path.exists(fca) else None,
                    "subject": subject, "ready": ready, "sha": sha_of(files)})
    return out


def local_packs(ccs=None, packs_dir=PACKS_DIR):
    """[{dir, cc, date, title, files: [(path, name)]}] for the new countries'
    packs on disk, samples left out."""
    ccs = set(ccs or countries())
    out = []
    for folder in sorted(glob.glob(os.path.join(packs_dir, "*"))):
        name = os.path.basename(folder)
        cc = name.split("-", 1)[0]
        state_path = os.path.join(folder, "pack.json")
        if cc not in ccs or not os.path.exists(state_path):
            continue
        try:
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
        except ValueError:
            continue
        if state.get("sample") or state.get("cc") != cc:
            continue
        files = [(os.path.join(folder, f), f) for f in sorted(os.listdir(folder))
                 if f not in PACK_SKIP and os.path.isfile(os.path.join(folder, f))
                 and not f.startswith(".")]
        out.append({"dir": name, "cc": cc, "date": state.get("date") or "",
                    "title": (state.get("title") or name)[:150], "files": files})
    return out


def rejected_slugs(db_path):
    """Slugs brief_log marks rejected, or an empty set when the store is absent."""
    if not db_path or not os.path.exists(db_path):
        return set()
    try:
        conn = sqlite3.connect("file:{0}?mode=ro".format(db_path), uri=True)
        try:
            return {r[0] for r in conn.execute(
                "SELECT slug FROM brief_log WHERE status = 'rejected'")}
        finally:
            conn.close()
    except sqlite3.Error:
        return set()


def brief_title(b, month):
    return "{0} {1} Brief DRAFT{2}: {3}".format(
        month, b["cc"].upper(), "" if b["ready"] else " (NOT READY)", b["subject"])[:180]


def load_ledger(path=LEDGER):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        data = {}
    data.setdefault("briefs", {})
    data.setdefault("packs", {})
    return data


def save_ledger(data, path=LEDGER):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")


# --- Drive ---------------------------------------------------------------------

class Drive:
    """The few calls this needs, over publish_briefs_to_drive's api() and
    src/drivepack's folder and upload helpers. dry=True never writes."""

    def __init__(self, token, api, drive_id, dry=False, log=print):
        self.token, self.api, self.drive_id, self.dry, self.log = token, api, drive_id, dry, log

    def _list(self, q, fields):
        params = urllib.parse.urlencode({
            "q": q, "corpora": "drive", "driveId": self.drive_id,
            "includeItemsFromAllDrives": "true", "supportsAllDrives": "true",
            "fields": "files({0})".format(fields), "pageSize": "200"})
        return self.api(self.token, "https://www.googleapis.com/drive/v3/files?" + params).get("files", [])

    def folder(self, parent, name):
        """(id or None, created). Dry: found only, never made."""
        if parent is None:
            return None, False
        if self.dry:
            got = self._list("name = '{0}' and '{1}' in parents and mimeType = '{2}' and trashed = false"
                             .format(name.replace("\\", "\\\\").replace("'", "\\'"), parent, FOLDER_MIME), "id")
            return (got[0]["id"] if got else None), False
        from src import drivepack
        return drivepack.find_or_create_folder(self.api, self.token, parent, name, self.drive_id)

    def by_slug(self, slug):
        got = self._list("appProperties has {{ key='{0}' and value='{1}' }} and trashed = false"
                         .format(PROP, slug[:100]), "id,name")
        return got[0]["id"] if got else None

    def tag(self, file_id, slug, name=None):
        body = {"appProperties": {PROP: slug[:100]}}
        if name:
            body["name"] = name
        self.api(self.token, "https://www.googleapis.com/drive/v3/files/{0}?supportsAllDrives=true"
                 .format(file_id), body, method="PATCH")

    def files(self, folder_id):
        if folder_id is None:
            return {}
        return {f["name"]: f for f in self._list("'{0}' in parents and trashed = false".format(folder_id),
                                                  "id,name,md5Checksum,size")}

    def trash(self, file_id):
        from src import drivepack
        return drivepack.trash(self.api, self.token, file_id)

    def upload(self, folder_id, path, name):
        from src import drivepack
        return drivepack.upload_resumable(self.token, folder_id, path, name, log=self.log)

    def fca_note(self, file_id, cc):
        """Replace the template's sample rows on the 5CA tab with one line."""
        meta = self.api(self.token, "https://sheets.googleapis.com/v4/spreadsheets/{0}"
                                    "?fields=sheets.properties".format(file_id))
        tab = next((s["properties"]["title"] for s in meta.get("sheets", [])
                    if "five column" in s["properties"]["title"].lower()), None)
        if not tab:
            return False
        import publish_briefs_to_drive as pbd
        self.api(self.token, "https://sheets.googleapis.com/v4/spreadsheets/{0}/values:batchClear"
                 .format(file_id), {"ranges": [pbd.a1(tab, "A4:K8")]})
        self.api(self.token, "https://sheets.googleapis.com/v4/spreadsheets/{0}/values:batchUpdate"
                 .format(file_id), {"valueInputOption": "RAW",
                                    "data": [{"range": pbd.a1(tab, "A4"),
                                              "values": [[FCA_NOTE.format(cc=cc)]]}]})
        return True


# --- the run -------------------------------------------------------------------

def run(drive, briefs, packs, ledger, rejected=(), today=None, max_new=MAX_NEW,
        publish_one=None, log=print, ready_only=False):
    """Publish what is new or changed. Returns a counts dict; updates `ledger`
    in place (the caller saves it, never in a dry run)."""
    today = today or datetime.date.today()
    month = today.strftime("%Y-%m")
    n = {"new": 0, "rewritten": 0, "renamed": 0, "unchanged": 0, "binned": 0, "waiting": 0,
         "skipped": 0, "failed": 0, "pack_up": 0, "pack_same": 0, "pack_folders": 0}
    dry = drive is None or drive.dry
    folders = {}

    def country_folder(cc, sub):
        key = (cc, sub)
        if key in folders:
            return folders[key]
        if drive is None:
            folders[key] = None
            return None
        root = folders.get("root")
        if "root" not in folders:
            root, made = drive.folder(drive.drive_id, ROOT_NAME)
            folders["root"] = root
            if made:
                log("  created the folder '{0}' in the shared drive".format(ROOT_NAME))
        top, made = drive.folder(root, country_name(cc))
        if made:
            log("  created the folder '{0}/{1}'".format(ROOT_NAME, country_name(cc)))
        fid, made = drive.folder(top, sub)
        if made:
            log("  created the folder '{0}/{1}/{2}'".format(ROOT_NAME, country_name(cc), sub))
        folders[key] = fid
        return fid

    for b in briefs:
        slug = b["slug"]
        entry = ledger["briefs"].get(slug)
        if slug in rejected:
            if entry and entry.get("id"):
                if dry:
                    log("  would bin {0} (rejected)".format(slug))
                else:
                    drive.trash(entry["id"])
                    log("  binned {0} (rejected in brief_log)".format(slug))
                    ledger["briefs"].pop(slug, None)
                n["binned"] += 1
            continue
        if ready_only and not b["ready"]:
            n["skipped"] += 1
            continue
        if entry is None and drive is not None:
            found = drive.by_slug(slug)
            if found:
                entry = {"id": found, "sha": None, "month": month, "title": None}
                log("  found {0}'s sheet already on Drive ({1}); adopting it".format(slug, found))
                if not dry:
                    ledger["briefs"][slug] = entry
        title = brief_title(b, (entry or {}).get("month") or month)
        if entry and entry.get("sha") == b["sha"] and entry.get("title") == title:
            n["unchanged"] += 1
            continue
        try:
            if entry:
                if entry.get("sha") != b["sha"]:
                    if dry:
                        log("  would rewrite {0} in place".format(slug))
                    else:
                        _fid, detail = publish_one(drive.token, slug, b["subject"], into=entry["id"])
                        log("  rewrote {0}: {1}".format(slug, detail))
                    n["rewritten"] += 1
                if entry.get("title") != title:
                    if not dry:
                        drive.tag(entry["id"], slug, title)
                    if entry.get("title"):
                        n["renamed"] += 1
                        log("  {0}renamed {1} to '{2}'".format("would have " if dry else "", slug, title))
                if not dry:
                    entry.update(sha=b["sha"], title=title)
                continue
            if n["new"] >= max_new:
                n["waiting"] += 1
                continue
            parent = country_folder(b["cc"], BRIEFS_SUB)
            if dry:
                log("  would create '{0}' in {1}/{2}/{3}{4}".format(
                    title, ROOT_NAME, country_name(b["cc"]), BRIEFS_SUB,
                    "" if parent or drive is None else " (folders made on the live run)"))
                n["new"] += 1
                continue
            fid, detail = publish_one(drive.token, slug, b["subject"], parent=parent, title=title)
            if not fid:
                log("  {0}: not published: {1}".format(slug, detail))
                n["failed"] += 1
                continue
            drive.tag(fid, slug)
            if not b["fca"]:
                drive.fca_note(fid, b["cc"])
            ledger["briefs"][slug] = {"id": fid, "sha": b["sha"], "month": month, "title": title,
                                      "cc": b["cc"]}
            log("  new {0}: {1}".format(slug, detail))
            n["new"] += 1
        except Exception as exc:                              # noqa: BLE001
            log("  {0}: FAILED {1}".format(slug, str(exc)[:200]))
            n["failed"] += 1

    for p in packs:
        try:
            parent = country_folder(p["cc"], PACKS_SUB)
            name = "{0} {1}".format(p["date"], p["title"]).strip()
            fid, made = (drive.folder(parent, name) if drive is not None else (None, False))
            if made:
                n["pack_folders"] += 1
            have = drive.files(fid) if (drive is not None and fid) else {}
            done = {}
            for path, fname in p["files"]:
                md5 = md5_of(path)
                if fname in have and have[fname].get("md5Checksum") == md5:
                    n["pack_same"] += 1
                    done[fname] = md5
                    continue
                if dry:
                    log("  would {0} {1}/{2}".format("replace" if fname in have else "upload", p["dir"], fname))
                    n["pack_up"] += 1
                    continue
                if fname in have:
                    drive.trash(have[fname]["id"])
                drive.upload(fid, path, fname)
                done[fname] = md5
                n["pack_up"] += 1
            if not dry:
                ledger["packs"][p["dir"]] = {"folder_id": fid, "files": done, "cc": p["cc"],
                                             "url": "https://drive.google.com/drive/folders/{0}".format(fid)}
        except Exception as exc:                              # noqa: BLE001
            log("  pack {0}: FAILED {1}".format(p["dir"], str(exc)[:200]))
            n["failed"] += 1
    return n


def summary(n, dry):
    pre = "would publish" if dry else "published"
    text = ("country-drive: {0} {1} new brief sheet(s), {2} rewritten, {3} renamed, {4} unchanged, "
            "{5} binned; {6} pack file(s) {7}, {8} unchanged".format(
                pre, n["new"], n["rewritten"], n["renamed"], n["unchanged"], n["binned"],
                n["pack_up"], "to upload" if dry else "uploaded", n["pack_same"]))
    if n["waiting"]:
        text += "; {0} new brief(s) wait for next week (at most {1} a run)".format(n["waiting"], MAX_NEW)
    if n["skipped"]:
        text += "; {0} not-ready brief(s) left out (--ready-only)".format(n["skipped"])
    if n["failed"]:
        text += "; {0} FAILED".format(n["failed"])
    return text
