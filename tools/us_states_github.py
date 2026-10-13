#!/usr/bin/env python3
"""The GitHub-side states step (13 October 2026): New Jersey, Massachusetts
and Michigan, whose legislatures answer GitHub's US runners but not the Mac
Mini or anything else on a UK network.

    python3 tools/us_states_github.py --db /tmp/uss.db            # all three
    python3 tools/us_states_github.py --only nj --db /tmp/uss.db
    python3 tools/us_states_github.py --only ma --ma-max-bills 20 --db /tmp/uss.db

Christopher, 13 October 2026: "Add the GitHub step, skip NY". New York stays
on Open States (no key). The step runs only where these hosts answer, which
is GitHub (jobs/us-weekly.sh): inline in GitHub's own US weekly, and, when
the Mini runs the week, in the run the Mini asks GitHub for at the start of
its week while it holds its lock (us-weekly.yml input states_github, the
senate_only pattern), so there is one store writer at a time.

Each route is the legislature's OWN publication, asked through
src/robots_guard.GuardedClient (robots.txt read every run, no exemptions) and
src/http.py (UA "CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)",
throttled). No key, no account, no bypass. Every bill goes through
tools/us_states.merge_foreign as tools/us_states_routes.py's do, so nothing
is stored twice: a bill Open States has gains the actions (and votes) it
lacks; a new bill on our ground is stored as '<source>:<id>' until Open
States' own file catches up and supersedes it. uss_bill_sources holds the
provenance and the change detection; the edition says "(via ...)".

  * NEW JERSEY, nj-leg: the Legislature's nightly downloads on
    pub.njleg.gov. The brief named the Access database (DB2026.zip, 175 MB
    zipped, 910 MB unzipped, needing mdbtools); a lighter official feed sits
    beside it: DB2026_TEXT.zip (1.4 MB), the SAME tables as comma-delimited
    text (MAINBILL, BILLHIST, BILLSPON, BILLSUBJ, ...), rebuilt at the same
    hour. The Access file holds no vote tables (its catalogue was read on 13
    October 2026), so it would add nothing: it is not downloaded and no
    mdbtools is needed. Floor votes, with every member's vote, come from
    pub.njleg.gov/votes/: A<year>.zip and S<year>.zip (111 KB and 52 KB on
    13 October 2026; "_Readme.txt" documents the columns). The directory
    listings give each file's stamp, so an unchanged file is never fetched.
    Open States has no New Jersey votes (us_states_store.OPENSTATES_VOTE_GAPS),
    so these are kept when Open States supersedes a row. Budget: at most
    about 1.6 MB a run, nothing when the stamps are unchanged.
  * MASSACHUSETTS, ma-api: the Legislature's documented API,
    malegislature.gov/api (Swagger at /api/swagger/v1/swagger.json; robots.txt
    "Disallow:" empty). /GeneralCourts/{n}/Documents lists every filed
    document with its title and sponsors (12.5 MB, one request a run); for
    the bills on our ground (or already stored), least recently read first
    and those that moved lately first, the history
    (/Documents/{bill}/DocumentHistoryActions) and, when it changed, the
    document's roll calls (/RollCalls/{n}: every member's vote by member
    code; names from the sponsors in the list). A roll call is stored only
    when the history dates it ("Roll Call #n" or "Yea and Nay No. n");
    never guessed. At most --ma-max-bills bills a run (80 on GitHub).
  * MICHIGAN, mi-leg: legislature.mi.gov, under its Automated Data Collection
    Policy ("Automated collection of data ... is permitted", at most one
    request a second: we keep 1.5 s; robots.txt answers 404, no rules). Its
    search for bills with activity since a date (one page, every bill that
    moved, with its description) finds the moved bills; for those on our
    ground (or stored), the bill page gives every action, the sponsors and
    each roll call's totals (no member positions on the page; Open States
    has Michigan's). At most --mi-max-bills bill pages a run (60).

Exit 1 when a gap was recorded. Writes uss_* tables, source_runs and gaps.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import html
import io
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_states_store as uss  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import GuardedClient  # noqa: E402
from tools import us_states as ust  # noqa: E402
from tools.us_states_direct import Counts, _hash, file_seen, note_file  # noqa: E402

FEED = "us-states-github"
HEARTBEAT = "US states GitHub"
BUDGET_S = 600.0
LIVE_DAYS = 30
# The three hosts the step reads; jobs/us-weekly.sh asks each robots.txt to
# decide whether this machine can run the step itself.
HOSTS = ("https://pub.njleg.gov/", "https://malegislature.gov/",
         "https://www.legislature.mi.gov/")

NJ_PUB = "https://pub.njleg.gov"
NJ_DB_DIR = NJ_PUB + "/leg-databases/{0}data/"
NJ_TEXT = NJ_PUB + "/leg-databases/{0}data/DB{0}_TEXT.zip"
NJ_VOTES_DIR = NJ_PUB + "/votes/"
NJ_THROTTLE = 2.0

MA_API = "https://malegislature.gov/api"
MA_MAX_BILLS = 80
MA_MAX_ROLLS = 60
MA_THROTTLE = 1.0

MI_BASE = "https://www.legislature.mi.gov"
MI_MAX_BILLS = 60
MI_THROTTLE = 1.5            # the policy allows one a second
MI_FIRST_DAYS = 8            # the first run looks this far back


def _text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def _why(exc):
    return getattr(exc, "reason", None) or getattr(getattr(exc, "cause", None), "code", None) \
        or getattr(exc, "cause", None) or exc


def _mdy(text):
    """'5/18/2026 0:00:00' or '05/18/2026' -> '2026-05-18'."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    return "{0}-{1:02d}-{2:02d}".format(m.group(3), int(m.group(1)), int(m.group(2))) if m else None


def _bill(state, ident, title, chamber, url, actions, sponsors, subjects=(), abstracts=(),
          classification="bill"):
    return {"id": None, "state": state, "session": None, "identifier": ident, "title": title,
            "classification": [classification], "subjects": list(subjects),
            "abstracts": [a for a in abstracts if a], "other_titles": [], "chamber": chamber,
            "url": url, "actions": actions, "sponsors": sponsors, "votes": []}


def listing_stamps(page):
    """{'DB2026_TEXT.zip': '10/12/2026 8:02 PM', ...} from an IIS directory listing."""
    return {name: "{0} {1}".format(d, t) for d, t, name in re.findall(
        r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d\d [AP]M)\s+(?:\d+\s+)?<A HREF=\"[^\"]*/([^\"/]+)\">",
        page, re.I)}


# --- New Jersey ---------------------------------------------------------------------

NJ_TYPES = {"A": ("lower", "bill"), "S": ("upper", "bill"), "AR": ("lower", "resolution"),
            "SR": ("upper", "resolution"), "ACR": ("lower", "concurrent resolution"),
            "SCR": ("upper", "concurrent resolution"), "AJR": ("lower", "joint resolution"),
            "SJR": ("upper", "joint resolution")}
# The action codes of BILLHIST (the Legislature's own abbreviations; the
# words in brackets are what the edition shows beside the code).
NJ_WORDS = (
    (r"^INT 1R[AS]", "Introduced, first reading"),
    (r"^REP/[AS]C[AS]", "Reported with committee amendments"),
    (r"^REP\b", "Reported from committee"),
    (r"^PA PBH\b", "Passed by the Assembly, passed both houses"),
    (r"^PS PBH\b", "Passed by the Senate, passed both houses"),
    (r"^PA\b", "Passed by the Assembly"),
    (r"^PS\b", "Passed by the Senate"),
    (r"^APP\b", "Approved by the Governor"),
    (r"^AV\b", "Absolute veto"),
    (r"^CV\b", "Conditional veto"),
    (r"^LIV\b", "Line-item veto"),
    (r"^W\b|^WITHDRAWN\b", "Withdrawn from consideration"),
    (r"^SUB FOR\b", "Substituted for"),
    (r"^SUB BY\b", "Substituted by"),
    (r"^AA\b", "Assembly floor amendments"),
    (r"^SA\b", "Senate floor amendments"),
    (r"^R/A\b", "Received in the Assembly"),
    (r"^R/S\b", "Received in the Senate"),
    (r"^TRANS\b", "Transferred to committee"),
    (r"^RCM\b", "Recommitted to committee"),
    (r"^FSS\b", "Filed with the Secretary of State"),
    (r"^MOTION\b", "Motion"),
)


def nj_action(row, first, committees):
    code = " ".join((row.get("Action") or "").split())
    comment = " ".join((row.get("Comment") or "").split())
    words = next((w for pat, w in NJ_WORDS if re.match(pat, code)), "")
    ref = re.search(r"\bREF ([A-Z]{3})\b", code)
    if ref and ref.group(1) in committees:
        words = (words + ", referred to " if words else "Referred to ") + committees[ref.group(1)]
    desc = "{0} ({1})".format(words, code) if words else code
    if comment:
        desc += " " + comment
    head = code.split(" ")[0] if code else ""
    chamber = {"A": "lower", "S": "upper", "G": "executive"}.get((row.get("House") or "").strip())
    cls = []
    if first or head == "INT":
        cls.append("introduction")
    if head in ("PA", "PS"):
        cls.append("passage")
        chamber = "lower" if head == "PA" else "upper"
    if head == "APP":
        cls.append("executive-signature")
        chamber = "executive"
    elif head in ("AV", "CV"):
        cls.append("executive-veto")
        chamber = "executive"
    return {"date": _mdy(row.get("DateAction")), "description": desc, "classification": cls,
            "chamber": chamber}


def _csv(z, name):
    hit = [n for n in z.namelist() if n.upper() == name.upper()]
    if not hit:
        return []
    return list(csv.DictReader(io.StringIO(z.read(hit[0]).decode("latin-1"))))


def nj_key(btype, number):
    return "{0}{1}".format((btype or "").strip().upper(), int(str(number).strip() or 0))


def nj_bills(zip_bytes):
    """{'A101': (source row hash parts, bill)} from DB<year>_TEXT.zip."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    committees = {r["Code"].strip(): "the {0} {1} Committee".format(
        "Assembly" if (r.get("House") or "").strip() == "A" else "Senate",
        " ".join((r.get("Description") or "").split()))
        for r in _csv(z, "COMMITTEE.TXT") if r.get("Code")}
    hist, spon, subj = {}, {}, {}
    for r in _csv(z, "BILLHIST.TXT"):
        hist.setdefault(nj_key(r["BillType"], r["BillNumber"]), []).append(r)
    for r in _csv(z, "BILLSPON.TXT"):
        if (r.get("Status") or "").strip() != "W":          # withdrawn sponsors left out
            spon.setdefault(nj_key(r["BillType"], r["BillNumber"]), []).append(r)
    for r in _csv(z, "BILLSUBJ.TXT"):
        subj.setdefault(nj_key(r["BillType"], r["BillNumber"]), []).append(
            " ".join((r.get("SubjectKey") or "").split()))
    out = {}
    for m in _csv(z, "MAINBILL.TXT"):
        btype = (m.get("BillType") or "").strip().upper()
        if btype not in NJ_TYPES:
            continue
        key = nj_key(btype, m["BillNumber"])
        chamber, kind = NJ_TYPES[btype]
        rows = sorted(hist.get(key, []), key=lambda r: int(r.get("Sequence") or 0))
        acts = []
        for i, r in enumerate(rows):
            a = nj_action(r, not acts, committees)
            if not a["date"]:
                continue
            a["ord"] = i
            acts.append(a)
        sps = sorted(spon.get(key, []), key=lambda r: int(r.get("Sequence") or 0))
        sponsors = [{"name": " ".join(r["Sponsor"].split()), "person_id": None,
                     "primary": (r.get("Type") or "").strip() == "P",
                     "classification": "primary" if (r.get("Type") or "").strip() == "P"
                     else "cosponsor"} for r in sps if (r.get("Sponsor") or "").strip()]
        ident = "{0} {1}".format(btype, int(m["BillNumber"]))
        b = _bill("nj", ident, " ".join((m.get("Synopsis") or "").split()), chamber, None, acts,
                  sponsors, subjects=subj.get(key, []),
                  abstracts=[" ".join((m.get("Abstract") or "").split())],
                  classification=kind)
        out[key] = ((m.get("CurrentStatus"), m.get("ModDate"), m.get("GovernorAction"),
                     [(r.get("Sequence"), r.get("Action"), r.get("DateAction")) for r in rows],
                     len(sponsors)), b)
    return out


NJ_OPTIONS = {"Y": "yes", "N": "no", "A": "abstain", "": "not voting"}


def nj_votes(zip_bytes, chamber, prefix):
    """{'A101': [vote]} from A<year>.zip or S<year>.zip: one row a member a
    vote; a vote is a bill, a day and an action."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    groups = {}
    for name in z.namelist():
        if not name.lower().endswith(".txt"):
            continue
        for r in csv.DictReader(io.StringIO(z.read(name).decode("latin-1"))):
            bill = re.sub(r"\s+", "", r.get("Bill") or "").upper()
            m = re.match(r"([A-Z]+)0*(\d+)$", bill)
            date = _mdy(r.get("Session_Date"))
            if not m or not date:
                continue
            key = "{0}{1}".format(m.group(1), m.group(2))
            action = " ".join((r.get("Action") or "").split())
            groups.setdefault((key, date, action), []).append(
                (" ".join((r.get("Full_Name") or "").split()),
                 (r.get("Legislator_Vote") or "").strip().upper()))
    out = {}
    seq = {}
    for (key, date, action), people in sorted(groups.items()):
        counts = {}
        plist = []
        for name, opt in people:
            option = NJ_OPTIONS.get(opt, "other")
            counts[option] = counts.get(option, 0) + 1
            plist.append({"name": name, "person_id": None, "option": option})
        yes, no = counts.get("yes", 0), counts.get("no", 0)
        n = seq.get((key, date), 0)
        seq[(key, date)] = n + 1
        out.setdefault(key, []).append({
            "id": "nj-leg:{0}/{1}/{2}/{3}".format(prefix, key, date, n),
            "date": date, "motion": action.title() if action.isupper() else action,
            "motion_classification": ["passage"] if "FINAL PASSAGE" in action.upper() else [],
            "result": "pass" if yes > no else "fail", "chamber": chamber,
            "counts": counts, "url": None, "people": plist})
    return out


def nj_years(today):
    """(legislature start year, [calendar years of vote files]) for a date:
    a Legislature sits two years from January of an even year; its last
    January days fall in the next one, so January reads last year's too."""
    y = int(today[:4])
    start = y if y % 2 == 0 else y - 1
    years = [y - 1, y] if today[5:7] == "01" else [y]
    return start, years


def read_new_jersey(conn, client, tax, wl, today, log=print):
    c = Counts("New Jersey (Legislature's downloads)")
    start, years = nj_years(today)
    session = uss.session_for(conn, "nj", start, start + 1)
    if not session:
        c.note = "no Open States session for {0}-{1} yet".format(start, start + 1)
        return c
    notes = []
    # Votes first: they ride on the bills read below.
    votes = {}
    try:
        vstamps = listing_stamps(client.get_text(NJ_VOTES_DIR, FEED, "nj-votes", archive=False))
    except FetchError as exc:
        _gap(conn, today, "New Jersey votes listing refused ({0})".format(_why(exc)))
        vstamps = {}
    for y in years:
        for prefix, chamber in (("A", "lower"), ("S", "upper")):
            name = "{0}{1}.zip".format(prefix, y)
            if name not in vstamps:
                continue
            try:
                raw = client.get_bytes(NJ_VOTES_DIR + name, FEED, "nj-" + name, archive=False,
                                       timeout=120)
                for key, vs in nj_votes(raw, chamber, "{0}{1}".format(prefix, y)).items():
                    votes.setdefault(key, []).extend(vs)
            except (FetchError, zipfile.BadZipFile) as exc:
                _gap(conn, today, "New Jersey votes {0}: {1}".format(name, _why(exc)))
                continue
    # The bills: read when the text export's stamp, or a vote file's, changed.
    try:
        stamps = listing_stamps(client.get_text(NJ_DB_DIR.format(start), FEED, "nj-db",
                                                archive=False))
    except FetchError as exc:
        _gap(conn, today, "New Jersey database listing refused ({0})".format(_why(exc)))
        c.note = "[gap] refused"
        return c
    text_name = "DB{0}_TEXT.zip".format(start)
    stamp = stamps.get(text_name)
    if not stamp:
        _gap(conn, today, "New Jersey {0} not listed".format(text_name))
        c.note = "[gap] {0} not listed".format(text_name)
        return c
    vote_stamp = ";".join("{0}={1}".format(n, vstamps[n]) for n in sorted(vstamps)
                          if any(n == "{0}{1}.zip".format(p, y) for p in "AS" for y in years))
    whole = "{0}|{1}".format(stamp, vote_stamp)
    if file_seen(conn, "nj-leg", text_name) == whole:
        c.note = "{0} unchanged ({1})".format(text_name, stamp)
        return c
    try:
        bills = nj_bills(client.get_bytes(NJ_TEXT.format(start), FEED, "nj-" + text_name,
                                          archive=False, timeout=180))
    except (FetchError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        _gap(conn, today, "New Jersey {0}: {1}".format(text_name, _why(exc)))
        c.note = "[gap] export unreadable"
        return c
    index = ust.session_index(conn, "nj", session)
    for key, (parts, b) in bills.items():
        c.read += 1
        b["session"] = session
        b["votes"] = votes.get(key, [])
        b["url"] = "https://www.njleg.gov/bill-search/{0}/{1}".format(start, key)
        h = _hash(parts, [(v["id"], v["counts"]) for v in b["votes"]])
        sid = "{0}/{1}".format(start, key)
        if ust.source_unchanged(conn, "nj-leg", sid, h):
            continue
        c.changed += 1
        what, _bid, _res = ust.merge_foreign(conn, tax, wl, "nj-leg", sid, b, today,
                                             change_hash=h, url=b["url"], index=index)
        c.add(what)
        if what != "skipped":
            c.votes += len(b["votes"])
    note_file(conn, "nj-leg", text_name, whole, "nj", today, NJ_TEXT.format(start))
    conn.commit()
    notes.append("session {0} ({1}); export of {2}".format(session, start, stamp))
    c.note = "; ".join(notes)
    return c


# --- Massachusetts ------------------------------------------------------------------

def ma_court(today):
    """The General Court sitting on a date: the 194th for 2025-2026."""
    y = int(today[:4])
    first = y if y % 2 == 1 else y - 1
    return 194 + (first - 2025) // 2, first


def ma_ident(number):
    m = re.match(r"([A-Z]+)0*(\d+)$", (number or "").strip().upper())
    return "{0} {1}".format(m.group(1), m.group(2)) if m else None


def ma_names(docs):
    """{member code: name} from the sponsors in the documents list."""
    names = {}
    for d in docs:
        for s in [d.get("PrimarySponsor")] + list(d.get("Cosponsors") or []):
            if s and s.get("Id") and s.get("Name"):
                names[s["Id"]] = " ".join(s["Name"].split())
    return names


MA_ROLL = re.compile(r"(?:roll call\s*#?\s*|yea and nay no\.?\s*)(\d+)", re.I)


def ma_action(a, first):
    desc = _text(a.get("Action"))
    low = desc.lower()
    branch = (a.get("Branch") or "").lower()
    chamber = {"house": "lower", "senate": "upper", "executive": "executive"}.get(branch)
    cls = []
    if first:
        cls.append("introduction")
    if low.startswith("passed to be engrossed"):
        cls.append("passage")
    if re.match(r"(signed|approved) by the governor", low):
        cls.append("executive-signature")
        chamber = "executive"
    elif low.startswith("vetoed by the governor"):
        cls.append("executive-veto")
        chamber = "executive"
    return {"date": (a.get("Date") or "")[:10] or None, "description": desc,
            "classification": cls, "chamber": chamber}


def ma_bill(doc, history):
    ident = ma_ident(doc.get("BillNumber")) or (doc.get("BillNumber") or "")
    acts = []
    for i, a in enumerate(history or []):
        if a.get("IsStricken"):
            continue
        act = ma_action(a, not acts)
        if not act["date"]:
            continue
        act["ord"] = i
        acts.append(act)
    sponsors = []
    seen = set()
    for i, s in enumerate([doc.get("PrimarySponsor")] + list(doc.get("Cosponsors") or [])):
        if not s or not s.get("Name") or s.get("Id") in seen:
            continue
        seen.add(s.get("Id"))
        sponsors.append({"name": " ".join(s["Name"].split()), "person_id": None,
                         "primary": i == 0, "classification": "primary" if i == 0 else "cosponsor"})
    court = doc.get("GeneralCourtNumber")
    return _bill("ma", ident, " ".join((doc.get("Title") or "").split()),
                 "upper" if ident.startswith("S") else "lower",
                 "https://malegislature.gov/Bills/{0}/{1}".format(court, doc["BillNumber"]),
                 acts, sponsors)


MA_COUNTS = re.compile(r"(\d+)\s*YEAS?\s*(?:to|-)\s*(\d+)\s*NAYS?", re.I)


def ma_history_votes(history, court, bill):
    """Votes the history records with their totals ("25 YEAS to 132 NAYS
    (See YEA and NAY No. 30)"): the House's roll calls are not in the API's
    roll-call lists, so their totals come from here; a Senate roll call the
    document lists is given its members afterwards (ma_vote). Dated by the
    history line itself, never guessed."""
    out = []
    for i, a in enumerate(history or []):
        if a.get("IsStricken") or not a.get("Date"):
            continue
        desc = _text(a.get("Action"))
        cm = MA_COUNTS.search(desc)
        if not cm:
            continue
        branch = (a.get("Branch") or "").lower()
        if branch not in ("house", "senate"):
            continue
        num = MA_ROLL.search(desc)
        yes, no = int(cm.group(1)), int(cm.group(2))
        motion = re.split(r"\s+-\s+\d+\s*YEAS?", desc, flags=re.I)[0].strip(" -") or desc
        out.append({"id": "ma-api:{0}/{1}/{2}".format(
            court, branch, num.group(1) if num else "{0}-{1}".format(bill, i)),
            "number": int(num.group(1)) if num else None,
            "date": a["Date"][:10], "motion": motion,
            "motion_classification": ["passage"] if re.search(r"engross|enact", motion, re.I)
            else [], "result": "pass" if yes > no else "fail",
            "chamber": "upper" if branch == "senate" else "lower",
            "counts": {"yes": yes, "no": no}, "url": None, "people": []})
    return out


def ma_vote(roll, names):
    """(counts, people) of a roll call from the API (members by code)."""
    people = []
    counts = {}
    for key, option in (("Yeas", "yes"), ("Nays", "no"), ("Absent", "absent")):
        for p in roll.get(key) or []:
            code = p.get("MemberCode")
            people.append({"name": names.get(code, code), "person_id": None, "option": option})
            counts[option] = counts.get(option, 0) + 1
    return counts, people


def _get_json(client, url, slug, timeout=None):
    kw = {"archive": False}
    if timeout:
        kw["timeout"] = timeout
    return json.loads(client.get_text(url, FEED, slug, **kw))


def ma_plan(conn, docs, tax, wl, session, today, court, max_bills):
    """[(doc, bill)] to read this run: on our ground or stored; bills that
    moved in the last LIVE_DAYS (by the store) first, then least recently
    read (never read first), then tier."""
    index = ust.session_index(conn, "ma", session)
    live = (datetime.date.fromisoformat(today) - datetime.timedelta(days=LIVE_DAYS)).isoformat()
    moved = {r[0]: r[1] for r in conn.execute(
        "SELECT identifier, latest_action_at FROM uss_bills WHERE state='ma' AND session=?",
        (session,))}
    moved = {uss.norm_ident(k): v for k, v in moved.items()}
    fetched = {r[0]: r[1] for r in conn.execute(
        "SELECT source_id, fetched_at FROM uss_bill_sources WHERE source='ma-api'")}
    ranked = []
    for d in docs:
        ident = ma_ident(d.get("BillNumber"))
        if not ident:
            continue
        b = ma_bill(d, [])
        b["session"] = session
        res = ust.classify(tax, wl, b)
        norm = uss.norm_ident(ident)
        if not (res.issue_areas or norm in index):
            continue
        sid = "{0}/{1}".format(court, d["BillNumber"])
        ranked.append(((moved.get(norm) or "") < live, fetched.get(sid) or "",
                       -(1 if res.tier == 1 else 0), d["BillNumber"], d))
    ranked.sort(key=lambda r: r[:4])
    return [r[4] for r in ranked[:max_bills]], len(ranked)


def read_massachusetts(conn, client, tax, wl, today, budget, max_bills=MA_MAX_BILLS,
                       max_rolls=MA_MAX_ROLLS, log=print):
    c = Counts("Massachusetts (Legislature's API)")
    court, first = ma_court(today)
    session = uss.session_for(conn, "ma", first, first + 1)
    if not session:
        c.note = "no Open States session for the {0}th General Court yet".format(court)
        return c
    try:
        docs = _get_json(client, "{0}/GeneralCourts/{1}/Documents".format(MA_API, court),
                         "ma-documents", timeout=240)
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "Massachusetts documents list refused ({0})".format(_why(exc)))
        c.note = "[gap] refused"
        return c
    names = ma_names(docs)
    todo, eligible = ma_plan(conn, docs, tax, wl, session, today, court, max_bills)
    c.read = len(todo)
    index = ust.session_index(conn, "ma", session)
    rolls = 0
    done = 0
    for d in todo:
        if budget.exhausted():
            c.note = "stopped at {0} of {1} bill(s) by the time budget".format(done, len(todo))
            break
        sid = "{0}/{1}".format(court, d["BillNumber"])
        try:
            history = _get_json(client, "{0}/GeneralCourts/{1}/Documents/{2}/DocumentHistoryActions"
                                .format(MA_API, court, d["BillNumber"]), "ma-hist-" + d["BillNumber"])
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "Massachusetts {0}: {1}".format(d["BillNumber"], _why(exc)))
            continue
        done += 1
        b = ma_bill(d, history)
        b["session"] = session
        h = _hash(history, b["title"])
        if ust.source_unchanged(conn, "ma-api", sid, h):
            conn.execute("UPDATE uss_bill_sources SET fetched_at=?, last_seen=? WHERE "
                         "source='ma-api' AND source_id=?", (today, today, sid))
            continue
        # The votes the history records, with their totals; a Senate roll
        # call the document lists then gets its members from the API.
        b["votes"] = ma_history_votes(history, court, d["BillNumber"])
        senate = {v["number"]: v for v in b["votes"] if v["chamber"] == "upper" and v["number"]}
        if senate and rolls < max_rolls and not budget.exhausted():
            try:
                detail = _get_json(client, "{0}/GeneralCourts/{1}/Documents/{2}".format(
                    MA_API, court, d["BillNumber"]), "ma-doc-" + d["BillNumber"])
            except (FetchError, ValueError) as exc:
                _gap(conn, today, "Massachusetts {0} detail: {1}".format(d["BillNumber"], _why(exc)))
                detail = {}
            for rc in detail.get("RollCalls") or []:
                v = senate.get(rc.get("RollCallNumber"))
                if (rc.get("Branch") or "").lower() != "senate" or not v:
                    continue
                if rolls >= max_rolls or budget.exhausted():
                    break
                try:
                    roll = _get_json(client, "{0}/GeneralCourts/{1}/Branches/Senate/RollCalls/{2}"
                                     .format(MA_API, court, rc["RollCallNumber"]),
                                     "ma-roll-senate-{0}".format(rc["RollCallNumber"]))
                except (FetchError, ValueError) as exc:
                    _gap(conn, today, "Massachusetts Senate roll call {0}: {1}".format(
                        rc["RollCallNumber"], _why(exc)))
                    continue
                rolls += 1
                v["counts"], v["people"] = ma_vote(roll, names)
                v["url"] = roll.get("DownloadUrl")
        for v in b["votes"]:
            v.pop("number", None)
        c.changed += 1
        what, _bid, _res = ust.merge_foreign(conn, tax, wl, "ma-api", sid, b, today,
                                             change_hash=h, url=b["url"], index=index)
        c.add(what)
        if what != "skipped":
            c.votes += len(b["votes"])
        conn.commit()
    conn.commit()
    if not c.note:
        c.note = "{0}th General Court; {1} of {2} bill(s) on our ground or stored read".format(
            court, done, eligible)
    return c


# --- Michigan -----------------------------------------------------------------------

MI_ROW = re.compile(r'(?s)<a href="/Home/GetObject\?objectName=(\d{4})-([A-Z]+)-(\d+)">.*?</a>\s*</td>'
                    r'\s*<td[^>]*>([^<]*)</td>\s*<td>(.*?)</td>', re.I)
MI_KINDS = {"HB": ("lower", "bill"), "SB": ("upper", "bill"), "HR": ("lower", "resolution"),
            "SR": ("upper", "resolution"), "HCR": ("lower", "concurrent resolution"),
            "SCR": ("upper", "concurrent resolution"), "HJR": ("lower", "joint resolution"),
            "SJR": ("upper", "joint resolution")}


def mi_search(page):
    """[(object name, kind, title, last action)] from the activity search."""
    out = []
    for year, kind, num, _type, desc in MI_ROW.findall(page):
        text = re.split(r"<br\s*/?>\s*Last Action:", desc, flags=re.I)
        out.append(("{0}-{1}-{2}".format(year, kind, num), kind.upper(), _text(text[0]),
                    _text(text[1]) if len(text) > 1 else ""))
    return out


MI_RC = re.compile(r"roll call\s*#\s*(\d+)\s+yeas\s+(\d+)\s+nays\s+(\d+)\s+excused\s+(\d+)\s+"
                   r"not voting\s+(\d+)", re.I)


def mi_action(desc, date, ordinal, first):
    low = desc.lower()
    letters = re.sub(r"[^A-Za-z]", "", desc)
    # The bill page: "House actions in lowercase, Senate actions in UPPERCASE".
    chamber = "upper" if letters and letters.isupper() else "lower"
    cls = []
    if first or low.startswith("introduced by"):
        cls.append("introduction")
    # "PASSED BY HOUSE ..." on the Senate's side is the message received, not a vote.
    if re.match(r"passed\b(?! by (the )?(house|senate))", low):
        cls.append("passage")
    if low.startswith("approved by the governor") or low.startswith("approved by governor"):
        cls.append("executive-signature")
        chamber = "executive"
    elif low.startswith("vetoed by the governor") or low.startswith("vetoed by governor"):
        cls.append("executive-veto")
        chamber = "executive"
    return {"date": date, "description": desc, "classification": cls, "chamber": chamber,
            "ord": ordinal}


def mi_bill(page, name):
    """The bill from its page (/Bills/Bill?ObjectName=2025-HB-4135)."""
    year, kind, num = name.split("-")
    chamber, cls_kind = MI_KINDS.get(kind, ("lower", "bill"))
    subj = re.search(r'(?s)<div id="ObjectSubject"[^>]*>(.*?)</div>', page)
    title = _text(subj.group(1)) if subj else ""
    spons = re.search(r'(?s)<div id="SponsorList".*?<ul>(.*?)</ul>', page)
    sponsors = []
    if spons:
        for attrs, who in re.findall(r"(?s)<a\b([^>]*)>(.*?)</a>", spons.group(1)):
            n = re.sub(r"\s*\(District \d+\)\s*$", "", _text(who))
            if not n:
                continue
            primary = "primarysponsor" in attrs.lower()
            sponsors.append({"name": n, "person_id": None, "primary": primary,
                             "classification": "primary" if primary else "cosponsor"})
    hist = re.search(r'(?s)<div id="History">(.*?)</table>', page)
    acts, votes = [], []
    rows = re.findall(r"(?s)<tr>\s*<td>([\d/]+)</td>\s*<td>.*?</td>\s*<td>(.*?)</td>\s*</tr>",
                      hist.group(1)) if hist else []
    for i, (d, a) in enumerate(rows):
        date = _mdy(d)
        desc = _text(a)
        if not date or not desc:
            continue
        act = mi_action(desc, date, i, not acts)
        acts.append(act)
        rc = MI_RC.search(desc)
        if rc and act["chamber"] in ("lower", "upper"):
            yes, no, exc, nv = (int(x) for x in rc.groups()[1:])
            votes.append({"id": "mi-leg:{0}/{1}/{2}".format(name, act["chamber"], rc.group(1)),
                          "date": date, "motion": re.sub(r"\s*roll call\s*#.*$", "", desc,
                                                         flags=re.I) or desc,
                          "motion_classification": ["passage"] if "passage" in act["classification"]
                          else [], "result": "pass" if yes > no else "fail",
                          "chamber": act["chamber"],
                          "counts": {"yes": yes, "no": no, "excused": exc, "not voting": nv},
                          "url": None, "people": []})
    ident = "{0} {1}".format(kind, int(num))
    b = _bill("mi", ident, title, chamber,
              "{0}/Bills/Bill?ObjectName={1}".format(MI_BASE, name), acts, sponsors,
              classification=cls_kind)
    b["votes"] = votes
    return b


def mi_session(conn, year):
    y = int(year)
    first = y if y % 2 == 1 else y - 1
    return uss.session_for(conn, "mi", first, first + 1)


def read_michigan(conn, client, tax, wl, today, budget, max_bills=MI_MAX_BILLS, log=print):
    c = Counts("Michigan (Legislature's website)")
    last = file_seen(conn, "mi-leg", "search")
    t0 = datetime.date.fromisoformat(today)
    since = (datetime.date.fromisoformat(last) - datetime.timedelta(days=1)).isoformat() if last \
        else (t0 - datetime.timedelta(days=MI_FIRST_DAYS)).isoformat()
    url = ("{0}/Search/ExecuteSearch?dateFromStr={1}&docTypes=Bills&dailyReport=todaysbillactivity"
           .format(MI_BASE, since))
    try:
        moved = mi_search(client.get_text(url, FEED, "mi-search-" + since, archive=False,
                                          timeout=120))
    except FetchError as exc:
        _gap(conn, today, "Michigan activity search refused ({0})".format(_why(exc)))
        c.note = "[gap] refused"
        return c
    ranked = []
    for name, kind, title, _last in moved:
        session = mi_session(conn, name[:4])
        if not session or kind not in MI_KINDS:
            continue
        b = _bill("mi", "{0} {1}".format(kind, int(name.split("-")[2])), title,
                  MI_KINDS[kind][0], None, [], [])
        b["session"] = session
        res = ust.classify(tax, wl, b)
        stored = conn.execute("SELECT 1 FROM uss_bills WHERE state='mi' AND session=? AND "
                              "REPLACE(identifier,' ','')=?",
                              (session, uss.norm_ident(b["identifier"]))).fetchone()
        if res.issue_areas or stored:
            ranked.append((not stored, -(1 if res.tier == 1 else 0), name, session))
    ranked.sort()
    c.read = len(moved)
    fetched = 0
    for _new, _tier, name, session in ranked:
        if fetched >= max_bills or budget.exhausted():
            c.note = "stopped at {0} of {1} moved bill(s) on our ground; the rest next run".format(
                fetched, len(ranked))
            break
        burl = "{0}/Bills/Bill?ObjectName={1}".format(MI_BASE, name)
        try:
            b = mi_bill(client.get_text(burl, FEED, "mi-" + name, archive=False), name)
        except FetchError as exc:
            _gap(conn, today, "Michigan {0}: {1}".format(name, _why(exc)))
            continue
        fetched += 1
        if not b["title"]:
            continue
        b["session"] = session
        h = _hash(b["actions"], b["title"])
        if ust.source_unchanged(conn, "mi-leg", name, h):
            continue
        c.changed += 1
        what, _bid, _res = ust.merge_foreign(conn, tax, wl, "mi-leg", name, b, today,
                                             change_hash=h, url=burl)
        c.add(what)
        if what != "skipped":
            c.votes += len(b["votes"])
        conn.commit()
    if fetched >= len(ranked) or not ranked:
        # Next run starts the day before today; a run cut short keeps its start.
        note_file(conn, "mi-leg", "search", today, "mi", today)
    conn.commit()
    if not c.note:
        c.note = "since {0}: {1} moved, {2} on our ground or stored, {3} read".format(
            since, len(moved), len(ranked), fetched)
    return c


# --- the run ----------------------------------------------------------------------

def stamp_heartbeat(conn, today):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/us_states_github.py"))
    conn.commit()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="nj,ma,mi", help="which readers: nj, ma, mi")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--ma-max-bills", type=int, default=MA_MAX_BILLS)
    ap.add_argument("--ma-max-rolls", type=int, default=MA_MAX_ROLLS)
    ap.add_argument("--mi-max-bills", type=int, default=MI_MAX_BILLS)
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    only = {s.strip().lower() for s in args.only.split(",") if s.strip()}
    conn = db.init_db(db.connect(args.db))
    http = HttpClient(raw_dir=args.raw_dir)
    http.set_host_throttle("pub.njleg.gov", NJ_THROTTLE)
    http.set_host_throttle("malegislature.gov", MA_THROTTLE)
    http.set_host_throttle("www.legislature.mi.gov", MI_THROTTLE)
    budget = drain.Budget(args.budget_seconds)
    # No exemptions: robots.txt is asked for every host, every run.
    client = GuardedClient(http, FEED, budget=budget)
    tax = filt.load_taxonomy(ust.TAXONOMY)
    wl = ust.empty_watchlist()
    print("us-states-github: {0}".format(", ".join(sorted(only))))
    if "nj" in only:
        print("  " + read_new_jersey(conn, client, tax, wl, today).line())
    if "ma" in only:
        print("  " + read_massachusetts(conn, client, tax, wl, today, budget,
                                        max_bills=args.ma_max_bills,
                                        max_rolls=args.ma_max_rolls).line())
    if "mi" in only:
        print("  " + read_michigan(conn, client, tax, wl, today, budget,
                                   max_bills=args.mi_max_bills).line())
    stamp_heartbeat(conn, today)
    gaps = conn.execute("SELECT COUNT(*) FROM gaps WHERE edition=? AND feed=?",
                        (today, FEED)).fetchone()[0]
    print("us-states-github: done in {0:.0f}s; {1} gap(s)".format(budget.spent(), gaps))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
