#!/usr/bin/env python3
"""Three state legislatures read from their OWN free feeds, the same day,
with no key (13 October 2026).

    python3 tools/us_states_direct.py --db /tmp/uss.db          # all three
    python3 tools/us_states_direct.py --only ks,ca --db /tmp/uss.db
    python3 tools/us_states_direct.py --only tx --tx-max-files 20 --since 2025-06-01

Christopher, 13 October 2026: "We can't pay for Open States access so may
need to explore alternatives whilst keeping the current tier we have." Open
States (tools/us_states.py) stays the record for all fifty; these readers
add, for three states, what its free key cannot: the last day, and (Kansas)
the votes Open States does not give. Every bill goes through
tools/us_states.merge_foreign, so nothing is stored twice: a bill Open
States has gains the actions it lacks; a new one on our ground is stored
under '<source>:<id>' until Open States' own file catches up and supersedes
it. uss_bill_sources holds the provenance and what was last read.

  * KANSAS, ks-kliss: the Legislature's KLISS API,
    https://www.kslegislature.gov/li/api/v13/rev-1/bill_status/ . One JSON
    reply (about 8 MB) holds every bill of the biennium with its titles,
    sponsors and full history; robots.txt answers 404 (no rules), checked
    every run. Open States gives Kansas NO votes: the history's final-action
    lines carry the tally ('Final Action - Passed; Yea: 120 Nay: 0'), stored
    as vote totals (no positions; the API has none). Unchanged revno, nothing
    read.
  * CALIFORNIA, ca-leginfo: the Legislative Counsel's public downloads,
    https://downloads.leginfo.legislature.ca.gov/ (an open index; robots.txt
    404, checked). Beside the 1.2 GB session file it publishes a small
    daily change file for each weekday, pubinfo_Mon.zip to pubinfo_Sat.zip
    (300 bytes to 1.2 MB, written about 21:20 Pacific and overwritten a week
    later), in the MySQL load format: tab-separated, text in backticks. A
    changed bill's whole history is in the file (measured: pubinfo_Mon of 5
    October 2026, 31 bills, 771 history rows). Each run reads the files
    stamped since it last read them; floor votes (location codes ending
    FLOOR) are stored with each member's vote by name.
  * TEXAS, tx-ftp: the Texas Legislative Council's anonymous FTP,
    ftp://ftp.legis.state.tx.us/bills/<session>/billhistory/, one XML per
    bill (caption, authors, subjects, every action), rewritten nightly in
    session. The Council's Acceptable Use notice asks data users to use the
    FTP rather than the website; FTP has no robots.txt, so the prefix is in
    src/robots_guard.DOCUMENTED_APIS with that reason. The listings give
    each file's time, so only files written since the last read are
    fetched: stored bills first (watched, tier 1, the rest), then new
    numbers, at most --tx-max-files a run. No floor roll calls (the files
    give committee tallies only). Texas meets in odd years: the 90th
    Legislature's pre-filing opens in November 2026.

Every request goes through src/http.py (UA "CitizenGO-ParlMonitor/1.0
(contact: cjoyce@citizengo.net)", throttled) wrapped by
src/robots_guard.guard(), so robots.txt is asked at run time. A refused or
failed source is a [gap] and the others go on. Exit 1 when a gap was
recorded. Writes uss_* tables and gaps only.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_states_store as uss  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import DOCUMENTED_APIS, GuardedClient  # noqa: E402
from tools import us_states as ust  # noqa: E402

FEED = "us-states-direct"
HEARTBEAT = "US states direct"
LIVE_DAYS = 30
BUDGET_S = 900.0

KS_STATUS = "https://www.kslegislature.gov/li/api/v13/rev-1/bill_status/"
CA_BASE = "https://downloads.leginfo.legislature.ca.gov/"
CA_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
TX_FTP = "ftp://ftp.legis.state.tx.us/bills/"
TX_TYPES = ("house_bills", "senate_bills", "house_joint_resolutions", "senate_joint_resolutions",
            "house_concurrent_resolutions", "senate_concurrent_resolutions",
            "house_resolutions", "senate_resolutions")
TX_MAX_FILES = 600
TX_THROTTLE = 1.0


def _hash(*parts):
    return hashlib.md5(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


class Counts:
    def __init__(self, source):
        self.source = source
        self.read = self.changed = 0
        self.result = {"merged": 0, "stored": 0, "replaced": 0, "skipped": 0}
        self.votes = 0
        self.note = ""

    def add(self, what):
        self.result[what] += 1

    def line(self):
        r = self.result
        return ("{0}: {1} bill(s) read, {2} changed: {3} merged into stored rows, {4} stored new, "
                "{5} refreshed, {6} off our ground; {7} vote(s){8}".format(
                    self.source, self.read, self.changed, r["merged"], r["stored"], r["replaced"],
                    r["skipped"], self.votes, "; " + self.note if self.note else ""))


def file_seen(conn, source, name):
    row = conn.execute("SELECT change_hash FROM uss_bill_sources WHERE source=? AND source_id=?",
                       (source, "file:" + name)).fetchone()
    return row[0] if row else None


def note_file(conn, source, name, stamp, state, today, url=None):
    conn.execute(
        "INSERT INTO uss_bill_sources (source, source_id, state, change_hash, url, fetched_at, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(source, source_id) DO UPDATE "
        "SET change_hash=excluded.change_hash, fetched_at=excluded.fetched_at, "
        "last_seen=excluded.last_seen",
        (source, "file:" + name, state, stamp, url, today, today, today))


def biennium(today, odd_start=True):
    y = int(today[:4])
    start = y if (y % 2 == 1) == odd_start else y - 1
    return start, start + 1


# --- Kansas -----------------------------------------------------------------------

KS_PASS = re.compile(r"(final action|consent calendar)[^;]*passed|adopted without roll call|"
                     r"conference committee report was adopted", re.I)
KS_TALLY = re.compile(r"Yea:\s*(\d+)\s*Nay:\s*(\d+)", re.I)


def ks_action(h):
    status = " ".join((h.get("status") or "").split())
    code = h.get("action_code") or ""
    low = status.lower()
    cls = []
    if code.startswith("intro_") and "introduced" in low:
        cls.append("introduction")
    if KS_PASS.search(status) and "not passed" not in low:
        cls.append("passage")
    if "approved by governor" in low:
        cls.append("executive-signature")
    elif "vetoed by governor" in low:
        cls.append("executive-veto")
    elif "override veto prevailed" in low:
        cls.append("veto-override-passage")
    elif "became law without" in low:
        cls.append("became-law")
    if "died" in low or "not passed" in low:
        cls.append("failure")
    chamber = {"house": "lower", "senate": "upper"}.get((h.get("chamber") or "").lower(),
                                                       "executive" if code.startswith("gov_")
                                                       else None)
    names = h.get("committee_names") or []
    desc = status + (" " + "; ".join(names) if names and status.endswith("to") else "")
    return {"date": h.get("session_date") or (h.get("occurred_datetime") or "")[:10] or None,
            "description": desc, "classification": cls, "chamber": chamber,
            "occurred": h.get("occurred_datetime")}


def ks_bill(rec, session, url_session):
    hist = sorted(rec.get("HISTORY") or [], key=lambda h: h.get("occurred_datetime") or "")
    acts = []
    votes = []
    for i, h in enumerate(hist):
        a = ks_action(h)
        a["ord"] = i
        acts.append(a)
        tally = KS_TALLY.search(h.get("status") or "")
        if tally and a["chamber"] in ("lower", "upper"):
            yes, no = int(tally.group(1)), int(tally.group(2))
            votes.append({"id": "ks-kliss:{0}/{1}/{2}".format(session, rec.get("BILLNO"),
                                                              h.get("occurred_datetime")),
                          "date": a["date"], "motion": a["description"].split(";")[0].strip(),
                          "motion_classification": ["passage"] if "passage" in a["classification"]
                          else [], "result": "pass" if yes > no else "fail",
                          "chamber": a["chamber"], "counts": {"yes": yes, "no": no},
                          "url": None, "people": []})
    # A veto overridden in both chambers is law (Kansas Constitution, art. 2,
    # s. 14): the second override is marked as becoming law, so the edition
    # does not leave the bill at "vetoed".
    overrides = [a for a in acts if "veto-override-passage" in a["classification"]]
    if {a["chamber"] for a in overrides} >= {"lower", "upper"} or len(overrides) >= 2:
        overrides[-1]["classification"].append("became-law")
    billno = rec.get("BILLNO") or rec.get("NAME") or ""
    m = re.match(r"([A-Z]+)(\d+)", billno)
    ident = "{0} {1}".format(m.group(1), m.group(2)) if m else billno
    sponsors = rec.get("SPONSOR_NAMES") or rec.get("ORIGINAL_SPONSOR") or []
    return {
        "id": None, "state": "ks", "session": session, "identifier": ident,
        "title": rec.get("SHORTTITLE") or rec.get("LONGTITLE") or "",
        "classification": ["resolution" if "R" in (m.group(1) if m else "") else "bill"],
        "subjects": [], "abstracts": [rec["LONGTITLE"]] if rec.get("LONGTITLE") else [],
        "other_titles": [], "chamber": "upper" if billno.startswith("S") else "lower",
        "url": "https://www.kslegislature.gov/li/{0}/measures/{1}/".format(url_session,
                                                                          billno.lower()),
        "actions": acts,
        "sponsors": [{"name": n, "person_id": None, "primary": i == 0,
                      "classification": "primary" if i == 0 else "cosponsor"}
                     for i, n in enumerate(sponsors)],
        "votes": votes,
    }


def read_kansas(conn, client, tax, wl, today, since, log=print):
    c = Counts("Kansas (KLISS)")
    try:
        raw = client.get_bytes(KS_STATUS, FEED, "ks-bill-status", archive=False, timeout=120)
        d = json.loads(raw.decode("utf-8"))
    except (FetchError, ValueError) as exc:
        ust._gap(conn, today, "Kansas KLISS bill_status refused ({0})".format(
            getattr(getattr(exc, "cause", None), "code", None) or exc))
        c.note = "[gap] refused"
        return c
    revno = str(d.get("revno") or "")
    y0, y1 = biennium(today)
    session = uss.session_for(conn, "ks", y0, y1) or "{0}-{1}".format(y0, y1)
    url_session = "b{0}_{1}".format(y0, str(y1)[2:])
    if revno and file_seen(conn, "ks-kliss", "bill_status") == revno:
        c.note = "revision {0} unchanged since the last read".format(revno)
        return c
    index = ust.session_index(conn, "ks", session)
    for rec in d.get("content") or []:
        c.read += 1
        b = ks_bill(rec, session, url_session)
        sid = "{0}/{1}".format(session, rec.get("BILLNO"))
        h = _hash(rec.get("HISTORY"), rec.get("SHORTTITLE"), rec.get("SPONSOR_NAMES"))
        if ust.source_unchanged(conn, "ks-kliss", sid, h):
            continue
        c.changed += 1
        what, _bid, _res = ust.merge_foreign(conn, tax, wl, "ks-kliss", sid, b, today,
                                             change_hash=h, url=b["url"], index=index)
        c.add(what)
        if what != "skipped":
            c.votes += len(b["votes"])
    note_file(conn, "ks-kliss", "bill_status", revno, "ks", today, KS_STATUS)
    conn.commit()
    c.note = "session {0}, revision {1}".format(session, revno)
    return c


# --- California ---------------------------------------------------------------------

def dat_rows(text):
    """Rows of a pubinfo .dat file: tab-separated, text fields in backticks
    (which may hold tabs and newlines), NULL bare."""
    rows, row, field, quoted, i, n = [], [], [], False, 0, len(text)
    started = False
    while i < n:
        ch = text[i]
        if quoted:
            if ch == "`":
                quoted = False
            else:
                field.append(ch)
        elif ch == "`":
            quoted = True
            started = True
        elif ch == "\t":
            row.append("".join(field))
            field = []
        elif ch in "\r\n":
            if field or row or started:
                row.append("".join(field))
                rows.append([None if v == "NULL" else v for v in row])
            row, field, started = [], [], False
            if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
        else:
            field.append(ch)
            started = True
        i += 1
    if field or row:
        row.append("".join(field))
        rows.append([None if v == "NULL" else v for v in row])
    return rows


def ca_index(text):
    """{file name: 'YYYY-MM-DD HH:MM'} for the daily change files, from the
    downloads index page."""
    out = {}
    for name, stamp in re.findall(r'href="(pubinfo_(?:%s)\.zip)".*?(\d{4}-\d{2}-\d{2} \d{2}:\d{2})'
                                  % "|".join(CA_DAYS), text, re.S):
        out[name] = stamp
    return out


def _table(z, name):
    for n in z.namelist():
        if n.upper() == name.upper() + ".DAT":
            return dat_rows(z.read(n).decode("utf-8", "replace"))
    return []


CA_PASSED = re.compile(r"read third time[^.]*\.\s*passed|^passed\b|adopted\.", re.I)


def ca_action(r):
    # bill_id, history_id, action_date, action, trans_uid, trans_update_dt,
    # action_sequence, action_code, action_status, primary_location, ...
    desc = " ".join((r[3] or "").split())
    low = desc.lower()
    loc = (r[9] or "") if len(r) > 9 else ""
    chamber = {"assembly": "lower", "senate": "upper"}.get(loc.lower(), "executive"
                                                           if loc.lower() == "governor" else None)
    cls = []
    if low.startswith("introduced") or "read first time. to print" in low:
        cls.append("introduction")
    if CA_PASSED.search(desc):
        cls.append("passage")
    if "approved by the governor" in low or "approved by governor" in low:
        cls.append("executive-signature")
        chamber = "executive"
    if "vetoed by" in low and "governor" in low:
        cls.append("executive-veto")
        chamber = "executive"
    if "chaptered by secretary of state" in low:
        cls.append("became-law")
        chamber = "executive"
    return {"date": (r[2] or "")[:10] or None, "description": desc, "classification": cls,
            "chamber": chamber, "ord": int(r[6] or 0) if (r[6] or "").isdigit() else 0}


def ca_bills(raw):
    """{leginfo bill_id: partial bill} from one daily change file."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    bills = {}

    def get(bid):
        if bid not in bills:
            m = re.match(r"(\d{8})(\d)([A-Z]+)(\d+)$", bid or "")
            if not m:
                return None
            bills[bid] = {"session_year": m.group(1), "session_num": m.group(2),
                          "identifier": "{0} {1}".format(m.group(3), int(m.group(4))),
                          "title": None, "version": -1, "actions": [], "votes": {},
                          "status": None}
        return bills[bid]
    for r in _table(z, "BILL_TBL"):
        b = get(r[0])
        if b:
            b["status"] = r[17] if len(r) > 17 else None
    for r in _table(z, "BILL_VERSION_TBL"):
        b = get(r[1])
        if b and r[6] and int(r[2] or 0) >= b["version"]:
            b["title"], b["version"] = " ".join(r[6].split()), int(r[2] or 0)
    for r in _table(z, "BILL_HISTORY_TBL"):
        b = get(r[0])
        if b:
            b["actions"].append(ca_action(r))
    motions = {r[0]: r[1] for r in _table(z, "BILL_MOTION_TBL")}
    for r in _table(z, "BILL_SUMMARY_VOTE_TBL"):
        # bill_id, location_code, vote_date_time, vote_date_seq, motion_id,
        # ayes, noes, abstain, vote_result, ...
        b = get(r[0])
        if not b or "FLOOR" not in (r[1] or "").upper():
            continue
        vid = "ca-leginfo:{0}:{1}:{2}:{3}:{4}".format(r[0], r[1], r[2], r[3], r[4])
        b["votes"][(r[1], r[2], r[3], r[4])] = {
            "id": vid, "date": (r[2] or "")[:10], "motion": motions.get(r[4]),
            "motion_classification": [], "result": "pass" if (r[8] or "").upper() == "PASS"
            else "fail", "chamber": "upper" if (r[1] or "").upper().startswith("S") else "lower",
            "counts": {"yes": int(r[5] or 0), "no": int(r[6] or 0), "other": int(r[7] or 0)},
            "url": None, "people": []}
    for r in _table(z, "BILL_DETAIL_VOTE_TBL"):
        # bill_id, location_code, legislator_name, vote_date_time,
        # vote_date_seq, vote_code, motion_id, ...
        b = bills.get(r[0])
        v = b and b["votes"].get((r[1], r[3], r[4], r[6]))
        if v:
            v["people"].append({"name": r[2], "person_id": None,
                                "option": {"AYE": "yes", "NOE": "no"}.get((r[5] or "").upper(),
                                                                         "other")})
    return bills


def read_california(conn, client, tax, wl, today, log=print):
    c = Counts("California (leginfo daily files)")
    try:
        listing = ca_index(client.get_text(CA_BASE, FEED, "ca-index", archive=False))
    except FetchError as exc:
        ust._gap(conn, today, "California leginfo downloads refused ({0})".format(
            getattr(exc, "reason", None) or getattr(exc.cause, "code", exc.cause)))
        c.note = "[gap] refused"
        return c
    week_ago = (datetime.date.fromisoformat(today) - datetime.timedelta(days=8)).isoformat()
    todo = sorted((stamp, name) for name, stamp in listing.items()
                  if stamp[:10] >= week_ago and stamp != file_seen(conn, "ca-leginfo", name))
    titles = {}
    files = 0
    for stamp, name in todo:
        try:
            raw = client.get_bytes(CA_BASE + name, FEED, "ca-" + name, archive=False, timeout=120)
            bills = ca_bills(raw)
        except (FetchError, zipfile.BadZipFile) as exc:
            ust._gap(conn, today, "California {0}: {1}".format(name, exc))
            continue
        files += 1
        for bid, p in sorted(bills.items()):
            c.read += 1
            if p["session_num"] != "0":
                continue        # a special session: Open States' file carries it
            session = p["session_year"]
            index = titles.setdefault(session, ust.session_index(conn, "ca", session))
            hit = index.get(uss.norm_ident(p["identifier"]))
            title = p["title"]
            if not title and hit:
                title = conn.execute("SELECT title FROM uss_bills WHERE bill_id=?",
                                     (hit[0],)).fetchone()[0]
            if not title:
                continue        # nothing to classify on, and not stored: the bulk file has it
            b = {"id": None, "state": "ca", "session": session, "identifier": p["identifier"],
                 "title": title, "classification": [
                     "resolution" if re.match(r"^(A|S)?[CJH]?R ", p["identifier"]) else "bill"],
                 "subjects": [], "abstracts": [], "other_titles": [],
                 "chamber": "upper" if p["identifier"].startswith("S") else "lower",
                 "url": "https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id="
                        + bid, "actions": p["actions"], "sponsors": [],
                 "votes": list(p["votes"].values())}
            h = _hash(p["actions"], b["votes"], title)
            if ust.source_unchanged(conn, "ca-leginfo", bid, h):
                continue
            c.changed += 1
            what, _bid, _res = ust.merge_foreign(conn, tax, wl, "ca-leginfo", bid, b, today,
                                                 change_hash=h, url=b["url"], index=index)
            c.add(what)
            if what != "skipped":
                c.votes += len(b["votes"])
        note_file(conn, "ca-leginfo", name, stamp, "ca", today, CA_BASE + name)
        conn.commit()
    c.note = "{0} daily file(s) read of {1} listed".format(files, len(listing))
    return c


# --- Texas -----------------------------------------------------------------------

LISTING = re.compile(r"^(\d\d)-(\d\d)-(\d\d)\s+(\d\d):(\d\d)(AM|PM)\s+(<DIR>|\d+)\s+(.+?)\s*$")


def ftp_listing(text):
    """[(name, is_dir, 'YYYY-MM-DD HH:MM')] from an IIS FTP directory listing."""
    out = []
    for line in text.splitlines():
        m = LISTING.match(line.strip())
        if not m:
            continue
        mo, dd, yy, hh, mi, ap, size, name = m.groups()
        h = int(hh) % 12 + (12 if ap == "PM" else 0)
        out.append((name, size == "<DIR>", "20{0}-{1}-{2} {3:02d}:{4}".format(yy, mo, dd, h, mi)))
    return out


def tx_date(text):
    m = re.match(r"(\d+)/(\d+)/(\d{4})", text or "")
    return "{0}-{1:02d}-{2:02d}".format(m.group(3), int(m.group(1)), int(m.group(2))) if m else None


def tx_bill(xml_bytes, session):
    root = ET.fromstring(xml_bytes.decode("utf-8-sig"))
    m = re.search(r"\)\s*(.+)$", root.get("bill") or "")
    ident = (m.group(1) if m else "").strip()
    acts = []
    for i, a in enumerate(root.findall("./actions/action")):
        num = a.findtext("actionNumber") or ""
        desc = " ".join((a.findtext("description") or "").split())
        comment = (a.findtext("comment") or "").strip()
        low = desc.lower()
        chamber = {"H": "lower", "S": "upper", "E": "executive"}.get(num[:1])
        cls = []
        if low == "filed" and num[:1] in "HS":
            cls.append("introduction")
        if low.startswith("passed") and not low.startswith("passed to") or low in (
                "adopted", "reported adopted"):
            cls.append("passage")
        if low.startswith("signed by the governor"):
            cls.append("executive-signature")
        elif low.startswith("vetoed by the governor"):
            cls.append("executive-veto")
        elif "without the governor's signature" in low:
            cls.append("became-law")
        acts.append({"date": tx_date(a.findtext("date")),
                     "description": desc + (" ({0})".format(comment) if comment else ""),
                     "classification": cls, "chamber": chamber, "ord": i})
    authors = [n.strip() for n in (root.findtext("authors") or "").split("|") if n.strip()]
    coauth = [n.strip() for n in (root.findtext("coauthors") or "").split("|") if n.strip()]
    kind = re.match(r"([A-Z]+)", ident.replace(" ", ""))
    t = kind.group(1) if kind else ""
    return {
        "id": None, "state": "tx", "session": session, "identifier": ident,
        "title": " ".join((root.findtext("caption") or "").split()),
        "classification": ["resolution" if t.endswith("R") else "bill"],
        "subjects": [re.sub(r"\s*\([A-Z]\d+\)$", "", s.text or "").strip()
                     for s in root.findall("./subjects/subject")],
        "abstracts": [], "other_titles": [], "chamber": "upper" if t.startswith("S") else "lower",
        "url": "https://capitol.texas.gov/BillLookup/History.aspx?LegSess={0}&Bill={1}".format(
            session, ident.replace(" ", "")),
        "actions": acts,
        "sponsors": [{"name": n, "person_id": None, "primary": True, "classification": "primary"}
                     for n in authors] + [{"name": n, "person_id": None, "primary": False,
                                           "classification": "cosponsor"} for n in coauth],
        "votes": [],
    }


def tx_sessions(conn, client, today):
    """The sessions to read: Open States' current Texas sessions in the
    store, and the latest regular session on the FTP."""
    out = set()
    rows = conn.execute("SELECT session, start_date, end_date, zip_updated FROM uss_sessions "
                        "WHERE state='tx'").fetchall()
    year_ago = (datetime.date.fromisoformat(today) - datetime.timedelta(days=200)).isoformat()
    for session, start, end, stamp in rows:
        if max(start or "", end or "", (stamp or "")[:10]) >= year_ago:
            out.add(session)
    listing = ftp_listing(client.get_text(TX_FTP, FEED, "tx-sessions", archive=False))
    regular = sorted((n for n, d, _ in listing if d and re.match(r"^\d+R$", n)),
                     key=lambda n: int(n[:-1]))
    if regular:
        out.add(regular[-1])
    names = {n for n, d, _ in listing if d}
    return sorted(s for s in out if s in names)


def read_texas(conn, client, tax, wl, today, since, budget, max_files=TX_MAX_FILES, log=print):
    c = Counts("Texas (TLC FTP)")
    try:
        sessions = tx_sessions(conn, client, today)
    except FetchError as exc:
        ust._gap(conn, today, "Texas FTP refused ({0})".format(getattr(exc, "reason", exc)))
        c.note = "[gap] refused"
        return c
    fetched = 0
    for session in sessions:
        index = ust.session_index(conn, "tx", session)
        tiers = {uss.norm_ident(i): (t, "watch:" in (m or "")) for i, t, m in conn.execute(
            "SELECT identifier, tier, matched_terms FROM uss_bills WHERE state='tx' AND session=?",
            (session,))}
        seen = {r[0] for r in conn.execute(
            "SELECT source_id FROM uss_bill_sources WHERE source='tx-ftp' AND source_id LIKE ?",
            (session + "/%",))}
        base = "{0}{1}/billhistory/".format(TX_FTP, session)
        changed = []
        for kind in TX_TYPES:
            if budget.exhausted():
                break
            try:
                ranges = ftp_listing(client.get_text(base + kind + "/", FEED,
                                                     "tx-{0}-{1}".format(session, kind),
                                                     archive=False))
            except FetchError:
                continue        # a type with no bills yet (pre-filing)
            for rng, is_dir, _ in ranges:
                if not is_dir or budget.exhausted():
                    continue
                try:
                    files = ftp_listing(client.get_text(base + kind + "/" + rng + "/", FEED,
                                                        "tx-{0}-{1}".format(session, rng),
                                                        archive=False))
                except FetchError as exc:
                    ust._gap(conn, today, "Texas FTP {0} {1}: {2}".format(session, rng, exc))
                    continue
                for name, is_file_dir, stamp in files:
                    if is_file_dir or not name.endswith(".xml") or stamp[:10] < since:
                        continue
                    ident = name[:-4]
                    sid = "{0}/{1}".format(session, uss.norm_ident(ident))
                    key = uss.norm_ident(ident)
                    if key in index:
                        tier, watched = tiers.get(key, (None, False))
                        rank = (0, not watched, tier != 1)
                    elif sid not in seen:
                        rank = (1, True, True)
                    else:
                        continue        # read before, off our ground: its caption is known
                    changed.append((rank, stamp, ident, sid,
                                    base + kind + "/" + rng + "/" + quote(name)))
        c.read += len(changed)
        for rank, stamp, ident, sid, url in sorted(changed, key=lambda x: (x[0], x[2])):
            if fetched >= max_files or budget.exhausted():
                c.note = "stopped at {0} file(s); the rest next run".format(fetched)
                break
            if ust.source_unchanged(conn, "tx-ftp", sid, stamp):
                continue
            try:
                b = tx_bill(client.get_bytes(url, FEED, "tx-" + sid.replace("/", "-"),
                                             archive=False), session)
            except (FetchError, ET.ParseError) as exc:
                ust._gap(conn, today, "Texas FTP {0}: {1}".format(sid, exc))
                continue
            fetched += 1
            c.changed += 1
            what, _bid, _res = ust.merge_foreign(conn, tax, wl, "tx-ftp", sid, b, today,
                                                 change_hash=stamp, url=b["url"], index=index)
            c.add(what)
            if fetched % 50 == 0:
                conn.commit()
        conn.commit()
    if not c.note:
        c.note = "session(s) {0}; {1} file(s) fetched".format(", ".join(sessions) or "none", fetched)
    return c


# --- the run ----------------------------------------------------------------------

def stamp_heartbeat(conn, today):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/us_states_direct.py"))
    conn.commit()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="ks,ca,tx", help="which readers: ks, ca, tx")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--since", help="ISO date: Texas files written since (default: the last "
                                    "--live-days)")
    ap.add_argument("--live-days", type=int, default=LIVE_DAYS)
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--tx-max-files", type=int, default=TX_MAX_FILES)
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    since = args.since or (datetime.date.fromisoformat(today)
                           - datetime.timedelta(days=args.live_days)).isoformat()
    only = {s.strip().lower() for s in args.only.split(",") if s.strip()}
    conn = db.init_db(db.connect(args.db))
    http = HttpClient(raw_dir=args.raw_dir)
    http.set_host_throttle("ftp.legis.state.tx.us", TX_THROTTLE)
    # guard()'s exemptions plus the Texas FTP: the Council's Acceptable Use
    # notice names it as the channel for data users, and FTP has no
    # robots.txt to ask (asking would read as "unreachable" and refuse all).
    client = GuardedClient(http, FEED, exempt=DOCUMENTED_APIS + (TX_FTP,))
    tax = filt.load_taxonomy(ust.TAXONOMY)
    wl = ust.empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    print("us-states-direct: {0}".format(", ".join(sorted(only))))
    if "ks" in only:
        print("  " + read_kansas(conn, client, tax, wl, today, since).line())
    if "ca" in only:
        print("  " + read_california(conn, client, tax, wl, today).line())
    if "tx" in only:
        print("  " + read_texas(conn, client, tax, wl, today, since, budget,
                                max_files=args.tx_max_files).line())
    stamp_heartbeat(conn, today)
    gaps = conn.execute("SELECT COUNT(*) FROM gaps WHERE edition=? AND (detail LIKE 'Kansas%' "
                        "OR detail LIKE 'California%' OR detail LIKE 'Texas%')",
                        (today,)).fetchone()[0]
    print("us-states-direct: done in {0:.0f}s; {1} gap(s)".format(budget.spent(), gaps))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
