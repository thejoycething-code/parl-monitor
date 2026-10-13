#!/usr/bin/env python3
"""Other official routes to state legislatures Open States' free tier leaves
short (13 October 2026).

    python3 tools/us_states_routes.py --db /tmp/uss.db              # all three
    python3 tools/us_states_routes.py --only pa --db /tmp/uss.db
    python3 tools/us_states_routes.py --only mo --mo-max-files 5 --db /tmp/uss.db

Christopher, 13 October 2026: "Where states block find other routes", and
later the same day: "Legiscan needs an API for each state so look for other
methods" (LegiScan is dropped: tools/us_states_legiscan.py stays, skipping
without a key, and nothing relies on it). Each route below is the
legislature's OWN publication, on a host that answers our client from the UK
and whose robots.txt allows us (asked at run time through
src/robots_guard.GuardedClient, never exempted). No key, no account, no
bypass. Every bill goes through tools/us_states.merge_foreign exactly as
tools/us_states_direct.py's do, so nothing is stored twice: a bill Open
States has gains the actions (and votes) it lacks; a new bill on our ground
is stored as '<source>:<id>' until Open States' own file catches up and
supersedes it. uss_bill_sources holds provenance and change detection.

  * PENNSYLVANIA, pa-ldpc: the Legislative Data Processing Center's Bill
    History export, https://www.palegis.us/data ("The current session is
    updated hourly"): one ZIP (1.7 MB; 19 MB of XML) holding every bill and
    resolution of the session with its sponsors, every action, and the floor
    tally on each passage. palegis.us's robots.txt has a single group, for
    the UserWay accessibility scanner (it disallows /legislation/bills/* to
    that scanner alone); /data is open to every agent. The data page lists
    each session's last update, so an unchanged export is never downloaded.
    Same day for all of Pennsylvania (Open States' file is a day behind).
  * MISSOURI, mo-house: the Missouri House's XML exports,
    https://documents.house.mo.gov/ ("Due to increased load from scraping
    ... the Missouri House of Representatives has begun generating several
    XML files"). <yearcode>-BillList.XML lists every House bill's XML file,
    which holds the titles, sponsors, every action in both chambers and each
    roll call's totals (no member positions; Open States has none for
    Missouri either). robots.txt asks Crawl-delay: 20, which the guard
    applies, and the House asks for no more than one poll per half hour, so
    a run reads at most --mo-max-files bills (40, about 14 minutes; 15 on
    GitHub), those on our ground only: least recently read first, then
    watched, tier 1, most recent action. House bills only (Senate bills are
    Open States' alone). Missouri meets January to mid-May.
  * ARKANSAS, ar-arkleg: the Arkansas Legislature's site,
    https://arkleg.state.ar.us/ (robots.txt allows every agent but
    ChatGPT's). Its "Recent Bill Activity" page, one per day, lists every
    bill that moved; for those, the bill page gives every action with its
    time and a link to each roll call, whose page names every member's vote.
    Open States gives Arkansas NO votes, so these are kept when Open States
    supersedes the bill's row (us_states_store.OPENSTATES_VOTE_GAPS). Days
    since the last read (at most --ar-days, 8), then the moved bills: stored
    ones first, then unknown ones (whose page gives the title to classify
    on), at most --ar-max-bills a run. Arkansas meets in odd years from
    January (regular) and even years in April (fiscal).

Measured from the UK on 13 October 2026 and NOT built (the scope doc's
per-state table, docs/us-states-scope.md, "Other routes"): New Jersey,
Massachusetts, Ohio, Tennessee, Georgia's web services and New York's Senate
API time out or refuse this network; Michigan's whole site answers 403
(robots.txt included, which src/robots_guard reads as no rules, but the
pages are refused too); data.michigan.gov's robots.txt disallows / to every
agent. tools/us_states_probe.py (and the read-only workflow
.github/workflows/us-states-probe.yml) measures those hosts from GitHub's
US runners.

Every request goes through src/http.py (UA "CitizenGO-ParlMonitor/1.0
(contact: cjoyce@citizengo.net)", throttled) wrapped by
src/robots_guard.GuardedClient (no exemptions). A refused or failed source
is a [gap] and the others go on. Exit 1 when a gap was recorded. Writes
uss_* tables, source_runs and gaps only.
"""

from __future__ import annotations

import argparse
import datetime
import html
import io
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_states_store as uss  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import GuardedClient  # noqa: E402
from tools import us_states as ust  # noqa: E402
from tools.us_states_direct import Counts, _hash, file_seen, note_file  # noqa: E402

FEED = "us-states-routes"
HEARTBEAT = "US states routes"
BUDGET_S = 900.0
LIVE_DAYS = 30

PA_DATA = "https://www.palegis.us/data"
PA_FILE = "https://www.palegis.us/data/file?documentType=BillHistoryData&session={0}"
MO_BASE = "https://documents.house.mo.gov/"
MO_MAX_FILES = 40
MO_THROTTLE = 20.0          # robots.txt: Crawl-delay: 20
AR_BASE = "https://arkleg.state.ar.us"
AR_DAYS = 8
AR_MAX_BILLS = 120
AR_THROTTLE = 2.0


def _text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def _gap(conn, today, detail):
    ust._gap(conn, today, detail)


def _why(exc):
    return getattr(exc, "reason", None) or getattr(getattr(exc, "cause", None), "code", None) \
        or getattr(exc, "cause", None) or exc


# --- Pennsylvania -------------------------------------------------------------------

PA_LINK = re.compile(r'documentType=BillHistoryData&(?:amp;)?session=(\d{4}_\d+)"\s+'
                     r'data-last-updated="([^"]+)"')


def pa_listing(page):
    """{'2025_0': '10/12/2026 07:31 PM', ...} from the data page: each
    session's export link carries its last update (data-last-updated)."""
    return dict(PA_LINK.findall(page))


def pa_stamp_iso(stamp):
    m = re.match(r"(\d+)/(\d+)/(\d{4})", stamp or "")
    return "{0}-{1:02d}-{2:02d}".format(m.group(3), int(m.group(1)), int(m.group(2))) if m else ""


def pa_date(text):
    m = re.match(r"(\d\d)/(\d\d)/(\d\d)$", (text or "").strip())
    return "20{0}-{1}-{2}".format(m.group(3), m.group(1), m.group(2)) if m else None


PA_TALLY = re.compile(r"\((\d+)-(\d+)\)")


def pa_action(a, first):
    verb = " ".join((a.findtext("verb") or "").split())
    full = " ".join((a.findtext("fullAction") or "").split())
    low = verb.lower()
    chamber = {"H": "lower", "S": "upper"}.get(a.get("actionChamber"))
    cls = []
    if first or low.startswith("introduced") or "noncontroversial resolution" in low:
        cls.append("introduction")
    if low.startswith(("third consideration and final passage", "final passage",
                       "adopted", "introduced and adopted")):
        cls.append("passage")
    if "defeated on final passage" in low:
        cls.append("failure")
    if low.startswith("approved by the governor"):
        cls.append("executive-signature")
        chamber = "executive"
    elif low.startswith("vetoed by the governor"):
        cls.append("executive-veto")
        chamber = "executive"
    elif "without the governor" in low or low.startswith("became law"):
        cls.append("became-law")
        chamber = "executive"
    return {"date": pa_date(a.findtext("date")), "description": full or verb,
            "classification": cls, "chamber": chamber}


def pa_bills(xml_bytes):
    """[(source_id, lastUpdate, bill)] from one Bill History export."""
    root = ET.fromstring(xml_bytes)
    out = []
    for s in root.findall("session"):
        year, num = s.get("year"), s.get("session")
        for b in s.findall("bill"):
            body = b.findtext("body") or ""
            typ = b.findtext("type") or ""
            number = str(int(b.findtext("number") or "0"))
            ident = "{0}{1} {2}".format(body, typ, number)
            acts, votes = [], []
            for i, a in enumerate(b.findall("./actionHistory/action")):
                verb = (a.findtext("verb") or "").strip()
                if verb.startswith("(Remarks see"):
                    continue    # a journal cross-reference, dated when it was keyed
                act = pa_action(a, not acts)
                act["ord"] = i
                acts.append(act)
                tally = PA_TALLY.search(a.findtext("rollCallVote") or "")
                if tally and act["chamber"] in ("lower", "upper") and act["date"]:
                    yes, no = int(tally.group(1)), int(tally.group(2))
                    votes.append({"id": "pa-ldpc:{0}_{1}/{2}/{3}".format(
                        year, num, uss.norm_ident(ident), a.get("sequence")),
                        "date": act["date"], "motion": verb.rstrip(","),
                        "motion_classification": ["passage"] if "passage" in act["classification"]
                        else [], "result": "pass" if yes > no else "fail",
                        "chamber": act["chamber"], "counts": {"yes": yes, "no": no},
                        "url": None, "people": []})
            sponsors = [_text(sp.text) for sp in b.findall("./sponsors/sponsor") if sp.text]
            out.append(("{0}_{1}/{2}".format(year, num, uss.norm_ident(ident)), b.get("lastUpdate"), {
                "id": None, "state": "pa", "session": None, "identifier": ident,
                "title": " ".join((b.findtext("shortTitle") or "").split()),
                "classification": ["resolution" if typ == "R" else "bill"],
                "subjects": [], "abstracts": [], "other_titles": [],
                "chamber": "upper" if body == "S" else "lower",
                "url": "https://www.palegis.us/legislation/bills/{0}/{1}{2}".format(
                    year, (body + typ).lower(), number) if num == "0" else None,
                "actions": acts,
                "sponsors": [{"name": n, "person_id": None, "primary": i == 0,
                              "classification": "primary" if i == 0 else "cosponsor"}
                             for i, n in enumerate(sponsors)],
                "votes": votes}))
    return out


def pa_session(conn, code):
    year, num = code.split("_")
    y0 = int(year)
    return uss.session_for(conn, "pa", y0, y0 + 1, special=num != "0")


def read_pennsylvania(conn, client, tax, wl, today, log=print):
    c = Counts("Pennsylvania (LDPC bill history)")
    try:
        listing = pa_listing(client.get_text(PA_DATA, FEED, "pa-data", archive=False))
    except FetchError as exc:
        _gap(conn, today, "Pennsylvania LDPC data page refused ({0})".format(_why(exc)))
        c.note = "[gap] refused"
        return c
    recent = (datetime.date.fromisoformat(today) - datetime.timedelta(days=45)).isoformat()
    todo = [(code, stamp) for code, stamp in sorted(listing.items())
            if pa_stamp_iso(stamp) >= recent]
    done = []
    for code, stamp in todo:
        if file_seen(conn, "pa-ldpc", code) == stamp:
            done.append("{0} unchanged".format(code))
            continue
        session = pa_session(conn, code)
        if not session:
            done.append("{0}: no Open States session yet".format(code))
            continue
        try:
            raw = client.get_bytes(PA_FILE.format(code), FEED, "pa-" + code, archive=False,
                                   timeout=180)
            z = zipfile.ZipFile(io.BytesIO(raw))
            xml_bytes = z.read([n for n in z.namelist() if n.lower().endswith(".xml")][0])
            bills = pa_bills(xml_bytes)
        except (FetchError, zipfile.BadZipFile, IndexError, ET.ParseError) as exc:
            _gap(conn, today, "Pennsylvania LDPC {0}: {1}".format(code, _why(exc)))
            continue
        index = ust.session_index(conn, "pa", session)
        for sid, updated, b in bills:
            c.read += 1
            b["session"] = session
            h = _hash(updated, b["actions"], b["title"])
            if ust.source_unchanged(conn, "pa-ldpc", sid, h):
                continue
            c.changed += 1
            what, _bid, _res = ust.merge_foreign(conn, tax, wl, "pa-ldpc", sid, b, today,
                                                 change_hash=h, url=b["url"], index=index)
            c.add(what)
            if what != "skipped":
                c.votes += len(b["votes"])
        note_file(conn, "pa-ldpc", code, stamp, "pa", today, PA_FILE.format(code))
        conn.commit()
        done.append("{0} ({1}) exported {2}".format(code, session, stamp))
    c.note = "; ".join(done) or "no session updated in 45 days"
    return c


# --- Missouri -----------------------------------------------------------------------

def mo_codes(js):
    """[(year code, base URL)] from the export page's SessionSet.js: the
    regular session, and the special ones when the page shows them."""
    out = []
    m = re.search(r"var baseURL = '([^']+)'", js)
    if m:
        out.append(m.group(1))
    if re.search(r"var showSpec = 'true'", js):
        out += re.findall(r"var specbaseURL\d* = '([^']+)'", js)
    return out


def mo_list(xml_bytes):
    """[(type, number, year, code, link)] from a BillList.XML."""
    root = ET.fromstring(xml_bytes)
    return [(b.findtext("BillType") or "", b.findtext("BillNumber") or "",
             b.findtext("SessionYear") or "", b.findtext("SessionCode") or "",
             (b.findtext("BillXMLLink") or "").strip()) for b in root.iter("BillXML")]


MO_FLOOR = re.compile(r"third read and passed|^passed|truly agreed|adopted \((h|s)\)|"
                      r"third read and failed|^failed", re.I)


def mo_action(desc, date, ordinal):
    low = desc.lower()
    chamber = "lower" if re.search(r"\(H\)\s*$", desc) else "upper" if re.search(
        r"\(S\)\s*$", desc) else None
    cls = []
    if low.startswith(("prefiled", "introduced")) or low.startswith("read first time (h)"):
        cls.append("introduction")
    if re.search(r"third read and passed|^passed|^adopted \((h|s)\)", low):
        cls.append("passage")
    if "signed by governor" in low or "approved by governor" in low:
        cls.append("executive-signature")
        chamber = "executive"
    elif "vetoed by governor" in low:
        cls.append("executive-veto")
        chamber = "executive"
    if "failed" in low:
        cls.append("failure")
    return {"date": date, "description": desc, "classification": cls, "chamber": chamber,
            "ord": ordinal}


def mo_bill(xml_bytes, session, year, code):
    root = ET.fromstring(xml_bytes)
    info = root.find("BillInformation")
    if info is None:
        info = root
    billno = info.findtext("BillNumber") or ""
    m = re.match(r"([A-Z]+)(\d+)", billno)
    ident = "{0} {1}".format(m.group(1), m.group(2)) if m else billno
    acts, votes = [], []
    seen_cls = set()
    actions = sorted(info.findall("Action"),
                     key=lambda a: int(a.findtext("ActivitySequence") or 0))
    for i, a in enumerate(actions):
        desc = " ".join((a.findtext("Description") or "").split())
        date = (a.findtext("PubDate") or "")[:10] or None
        act = mo_action(desc, date, i)
        if "introduction" in act["classification"]:
            if "introduction" in seen_cls:
                act["classification"].remove("introduction")
            seen_cls.add("introduction")
        acts.append(act)
        rc = a.find("RollCall")
        if rc is not None and MO_FLOOR.search(desc) and act["chamber"] in ("lower", "upper"):
            yes, no = int(rc.findtext("TotalYes") or 0), int(rc.findtext("TotalNo") or 0)
            votes.append({"id": "mo-house:{0}{1}/{2}/{3}".format(
                year, code, billno, a.findtext("Guid")), "date": date,
                "motion": re.sub(r"\s*\((H|S)\)\s*$", "", desc),
                "motion_classification": ["passage"] if "passage" in act["classification"]
                else [], "result": "pass" if yes > no else "fail", "chamber": act["chamber"],
                "counts": {"yes": yes, "no": no, "other": int(rc.findtext("TotalPresent") or 0)},
                "url": None, "people": []})
    sponsors = [(s.findtext("FullName") or "").strip() for s in info.findall("Sponsor")
                if (s.findtext("SponsorType") or "") == "Sponsor"]
    cosp = [(s.findtext("FullName") or "").strip() for s in info.findall("Sponsor")
            if (s.findtext("SponsorType") or "") != "Sponsor"]
    title = " ".join((info.findtext("./Title/LongTitle") or info.findtext("./Title/ShortTitle")
                      or "").split())
    short = " ".join((info.findtext("./Title/ShortTitle") or "").split())
    t = m.group(1) if m else ""
    return {
        "id": None, "state": "mo", "session": session, "identifier": ident, "title": title,
        "classification": ["resolution" if t.endswith("R") else "bill"],
        "subjects": [short] if short else [], "abstracts": [], "other_titles": [],
        "chamber": "upper" if t.startswith("S") else "lower",
        "url": "https://house.mo.gov/Bill.aspx?bill={0}&year={1}&code={2}".format(billno, year,
                                                                                 code),
        "actions": acts,
        "sponsors": [{"name": n, "person_id": None, "primary": True, "classification": "primary"}
                     for n in sponsors if n] + [{"name": n, "person_id": None, "primary": False,
                                                 "classification": "cosponsor"}
                                                for n in cosp if n],
        "votes": votes,
    }


def mo_session(conn, year, code):
    y = int(year)
    if code == "R":
        return uss.session_for(conn, "mo", y)
    rows = [r[0] for r in conn.execute(
        "SELECT session FROM uss_sessions WHERE state='mo' AND session=?",
        ("{0}S{1}".format(y, code[1:] or "1"),))]
    return rows[0] if rows else uss.session_for(conn, "mo", y, special=True)


def read_missouri(conn, client, tax, wl, today, budget, max_files=MO_MAX_FILES, log=print):
    c = Counts("Missouri (House XML exports)")
    try:
        bases = mo_codes(client.get_text(MO_BASE + "SessionSet.js", FEED, "mo-sessionset",
                                         archive=False))
    except FetchError as exc:
        _gap(conn, today, "Missouri House XML exports refused ({0})".format(_why(exc)))
        c.note = "[gap] refused"
        return c
    week_ago = (datetime.date.fromisoformat(today) - datetime.timedelta(days=7)).isoformat()
    cands = []
    for base in bases:
        if budget.exhausted():
            break
        try:
            listed = mo_list(client.get_bytes(base + "BillList.XML", FEED,
                                              "mo-" + base.rsplit("/", 1)[1] + "billlist",
                                              archive=False, timeout=120))
        except (FetchError, ET.ParseError) as exc:
            _gap(conn, today, "Missouri House {0}BillList.XML: {1}".format(base, _why(exc)))
            continue
        for typ, num, year, code, link in listed:
            session = mo_session(conn, year, code)
            if not session:
                continue
            ident = "{0}{1}".format(typ, num)
            row = conn.execute(
                "SELECT b.tier, b.matched_terms, b.latest_action_at, s.fetched_at FROM uss_bills b "
                "LEFT JOIN uss_bill_sources s ON s.source='mo-house' AND s.source_id=? "
                "WHERE b.state='mo' AND b.session=? AND REPLACE(b.identifier,' ','')=?",
                ("{0}{1}/{2}".format(year, code, ident), session, ident)).fetchone()
            if not row:
                continue    # only bills on our ground: the list gives no title to classify on
            tier, terms, latest, fetched = row
            cands.append(((fetched or "") >= week_ago, "watch:" not in (terms or ""), tier != 1,
                          ust._neg(latest), fetched or "", session, year, code, ident, link))
    cands.sort(key=lambda x: x[:5])
    c.read = len(cands)
    fetched = 0
    for (_r, _w, _t, _l, _f, session, year, code, ident, link) in cands:
        if fetched >= max_files or budget.exhausted():
            c.note = "stopped at {0} of {1} bill(s) on our ground; the rest next run".format(
                fetched, len(cands))
            break
        sid = "{0}{1}/{2}".format(year, code, ident)
        try:
            b = mo_bill(client.get_bytes(link, FEED, "mo-" + sid.replace("/", "-"),
                                         archive=False), session, year, code)
        except (FetchError, ET.ParseError) as exc:
            _gap(conn, today, "Missouri House {0}: {1}".format(sid, _why(exc)))
            continue
        fetched += 1
        h = _hash(b["actions"], b["votes"], b["title"])
        if ust.source_unchanged(conn, "mo-house", sid, h):
            conn.execute("UPDATE uss_bill_sources SET fetched_at=?, last_seen=? WHERE "
                         "source='mo-house' AND source_id=?", (today, today, sid))
            continue
        c.changed += 1
        what, _bid, _res = ust.merge_foreign(conn, tax, wl, "mo-house", sid, b, today,
                                             change_hash=h, url=b["url"])
        c.add(what)
        if what != "skipped":
            c.votes += len(b["votes"])
        conn.commit()
    conn.commit()
    if not c.note:
        c.note = "{0} of {1} bill(s) on our ground read".format(fetched, len(cands))
    return c


# --- Arkansas -----------------------------------------------------------------------

def ar_session_code(page):
    m = re.search(r'id="ddBienniumSession" name="ddBienniumSession" value="([^"]+)"', page)
    return m.group(1) if m else None


def ar_os_session(conn, code):
    """'2025/2025R' -> '2025'; '2025/2026F' -> '2026F'; '2025/2026S1' -> '2026S1'
    (Open States' identifiers), when the store has it."""
    part = (code or "").split("/")[-1]
    want = part[:-1] if part.endswith("R") else part
    row = conn.execute("SELECT session FROM uss_sessions WHERE state='ar' AND session=?",
                       (want,)).fetchone()
    return row[0] if row else None


def ar_recent(page):
    """[(bill id, its ddBienniumSession code)] from a Recent Bill Activity page."""
    out = []
    for bid, code in re.findall(r'aria-label="Bill Number (\w+)" href="/Bills/Detail\?id=\w+'
                                r'(?:&amp;|&)chamber=\w+(?:&amp;|&)ddBienniumSession=([^"]+)"',
                                page):
        item = (bid, html.unescape(code).replace("%2F", "/"))
        if item not in out:
            out.append(item)
    return out


AR_ROW = re.compile(r'<div class="row tableRow(?:Alt)?" data-fixed="true" aria-rowindex="\d+" '
                    r'role="row">\s*<div class="col-md-2" aria-colindex="1" role="gridcell">'
                    r'(.*?)</div>\s*<div class="col-md-3" aria-colindex="2" role="gridcell">'
                    r'(.*?)</div>\s*<div class="col-md-5" aria-colindex="3" role="gridcell">'
                    r'(.*?)</div>\s*<div class="col-md-2"[^>]*aria-colindex="4" role="gridcell">'
                    r'(.*?)</div>', re.S)


def ar_when(text):
    m = re.match(r"(\d+)/(\d+)/(\d{4})", _text(text))
    return "{0}-{1:02d}-{2:02d}".format(m.group(3), int(m.group(1)), int(m.group(2))) if m else None


def ar_action(chamber_text, when, desc, ordinal):
    low = desc.lower()
    chamber = {"house": "lower", "senate": "upper"}.get(chamber_text.lower())
    cls = []
    if low == "filed" or low.startswith("filed"):
        cls.append("introduction")
    if re.search(r"read the third time and passed|^passed|adopted\.?$|resolution adopted|"
                 r"read and adopted", low) and "amendment" not in low:
        cls.append("passage")
    if re.search(r"is now act \d+", low):
        cls.append("became-law")
        chamber = "executive"
    if "vetoed by the governor" in low:
        cls.append("executive-veto")
        chamber = "executive"
    if "failed" in low:
        cls.append("failure")
    return {"date": when, "description": desc, "classification": cls, "chamber": chamber,
            "ord": ordinal}


def ar_detail(page, session, code):
    """(bill, [(vote URL, action)]) from a bill page."""
    head = re.search(r"<h1[^>]*>\s*([A-Z]+\d+) - (.*?)</h1>", page, re.S)
    billno = head.group(1) if head else ""
    m = re.match(r"([A-Z]+)(\d+)", billno)
    ident = "{0} {1}".format(m.group(1), m.group(2)) if m else billno
    hist = page[page.find("Bill Status History"):] if "Bill Status History" in page else ""
    rows = AR_ROW.findall(hist)
    acts, vote_links = [], []
    for i, (ch, when, desc, vote) in enumerate(reversed(rows)):     # the page lists newest first
        a = ar_action(_text(ch), ar_when(when), _text(desc), i)
        acts.append(a)
        link = re.search(r'href="(/Bills/Votes\?[^"]+)"', vote)
        if link:
            vote_links.append((AR_BASE + html.unescape(link.group(1)), a))
    def names(label):
        cell = re.search(r">" + label + r":</div>\s*<div[^>]*>(.*?)</div>", page, re.S)
        return [_text(n) for n in re.findall(r"<a [^>]*>(.*?)</a>", cell.group(1), re.S)] \
            if cell else []
    lead = names("Lead Sponsor") + names("Other Primary Sponsor")
    cosp = names("CoSponsors")
    t = m.group(1) if m else ""
    return {
        "id": None, "state": "ar", "session": session, "identifier": ident,
        "title": _text(head.group(2)) if head else "",
        "classification": ["resolution" if t.endswith("R") else "bill"],
        "subjects": [], "abstracts": [], "other_titles": [],
        "chamber": "upper" if t.startswith("S") else "lower",
        "url": "{0}/Bills/Detail?id={1}&ddBienniumSession={2}".format(
            AR_BASE, billno, code.replace("/", "%2F")),
        "actions": acts,
        "sponsors": [{"name": n, "person_id": None, "primary": True, "classification": "primary"}
                     for n in lead] + [{"name": n, "person_id": None, "primary": False,
                                        "classification": "cosponsor"} for n in cosp],
        "votes": [],
    }, vote_links


AR_OPTIONS = {"Yeas": "yes", "Nays": "no", "Non Voting": "not voting", "Present": "other",
              "Excused": "excused"}


def ar_vote(page, url, action):
    """One roll call: counts and every member's vote, by name."""
    counts, people = {}, []
    heads = list(re.finditer(r'<b style="font-size:23px;">(Yeas|Nays|Non Voting|Present|Excused):'
                             r'\s*(\d+)</b>', page))
    for i, h in enumerate(heads):
        label, n = h.group(1), int(h.group(2))
        key = {"Yeas": "yes", "Nays": "no"}.get(label, "other")
        counts[key] = counts.get(key, 0) + n
        end = heads[i + 1].start() if i + 1 < len(heads) else len(page)
        for name in re.findall(r'role="gridcell">\s*<a [^>]*>(.*?)</a>', page[h.end():end], re.S):
            people.append({"name": _text(name), "person_id": None,
                           "option": AR_OPTIONS[label]})
    yes, no = counts.get("yes", 0), counts.get("no", 0)
    return {"id": "ar-arkleg:{0}".format(re.sub(r"^.*\?", "", url)), "date": action["date"],
            "motion": action["description"], "motion_classification":
            ["passage"] if "passage" in action["classification"] else [],
            "result": "pass" if yes > no else "fail", "chamber": action["chamber"],
            "counts": counts, "url": url, "people": people}


def read_arkansas(conn, client, tax, wl, today, budget, days=AR_DAYS, max_bills=AR_MAX_BILLS,
                  log=print):
    c = Counts("Arkansas (arkleg bill pages)")
    try:
        first = client.get_text(AR_BASE + "/Bills/RecentActivities", FEED, "ar-recent",
                                archive=False)
    except FetchError as exc:
        _gap(conn, today, "Arkansas arkleg refused ({0})".format(_why(exc)))
        c.note = "[gap] refused"
        return c
    code = ar_session_code(first)
    moved = []
    t0 = datetime.date.fromisoformat(today)
    for back in range(days, -1, -1):
        day = (t0 - datetime.timedelta(days=back)).isoformat()
        if back and file_seen(conn, "ar-arkleg", "recent:" + day):
            continue
        if budget.exhausted():
            break
        if back == 0:
            page = first
        else:
            try:
                page = client.get_text("{0}/Bills/RecentActivities?ddBienniumSession={1}&date={2}"
                                       .format(AR_BASE, (code or "").replace("/", "%2F"), day),
                                       FEED, "ar-recent-" + day, archive=False)
            except FetchError as exc:
                _gap(conn, today, "Arkansas recent activity {0}: {1}".format(day, _why(exc)))
                continue
        for item in ar_recent(page):
            if item not in moved:
                moved.append(item)
        if back:
            note_file(conn, "ar-arkleg", "recent:" + day, "read", "ar", today)
    conn.commit()
    ranked = []
    for bid, bcode in moved:
        session = ar_os_session(conn, bcode)
        if not session:
            continue
        stored = conn.execute("SELECT 1 FROM uss_bills WHERE state='ar' AND session=? AND "
                              "REPLACE(identifier,' ','')=?", (session, bid)).fetchone()
        ranked.append((not stored, bid, bcode, session))
    ranked.sort()
    c.read = len(ranked)
    live = (t0 - datetime.timedelta(days=LIVE_DAYS)).isoformat()
    fetched = 0
    for _new, bid, bcode, session in ranked:
        if fetched >= max_bills or budget.exhausted():
            c.note = "stopped at {0} of {1} moved bill(s); the rest next run".format(
                fetched, len(ranked))
            break
        url = "{0}/Bills/Detail?id={1}&ddBienniumSession={2}".format(AR_BASE, bid,
                                                                      bcode.replace("/", "%2F"))
        try:
            b, vote_links = ar_detail(client.get_text(url, FEED, "ar-" + bid, archive=False),
                                      session, bcode)
        except FetchError as exc:
            _gap(conn, today, "Arkansas {0} {1}: {2}".format(bcode, bid, _why(exc)))
            continue
        fetched += 1
        if not b["title"]:
            continue
        sid = "{0}/{1}".format(bcode, bid)
        h = _hash(b["actions"], b["title"])
        if ust.source_unchanged(conn, "ar-arkleg", sid, h):
            continue
        res = ust.classify(tax, wl, b)
        stored = not _new
        if stored or res.issue_areas:
            # Roll calls only for a bill we keep, and only recent ones.
            for vurl, act in vote_links:
                if (act["date"] or "") < live or budget.exhausted():
                    continue
                try:
                    b["votes"].append(ar_vote(client.get_text(vurl, FEED, "ar-vote-" + bid,
                                                              archive=False), vurl, act))
                except FetchError as exc:
                    _gap(conn, today, "Arkansas vote {0}: {1}".format(vurl, _why(exc)))
        c.changed += 1
        what, _bid, _res = ust.merge_foreign(conn, tax, wl, "ar-arkleg", sid, b, today,
                                             change_hash=h, url=url)
        c.add(what)
        if what != "skipped":
            c.votes += len(b["votes"])
        conn.commit()
    if not c.note:
        c.note = "session {0}; {1} of {2} moved bill(s) read".format(code, fetched, len(ranked))
    return c


# --- the run ----------------------------------------------------------------------

def stamp_heartbeat(conn, today):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/us_states_routes.py"))
    conn.commit()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="pa,mo,ar", help="which readers: pa, mo, ar")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--mo-max-files", type=int, default=MO_MAX_FILES)
    ap.add_argument("--ar-days", type=int, default=AR_DAYS)
    ap.add_argument("--ar-max-bills", type=int, default=AR_MAX_BILLS)
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    only = {s.strip().lower() for s in args.only.split(",") if s.strip()}
    conn = db.init_db(db.connect(args.db))
    http = HttpClient(raw_dir=args.raw_dir)
    http.set_host_throttle("documents.house.mo.gov", MO_THROTTLE)
    http.set_host_throttle("arkleg.state.ar.us", AR_THROTTLE)
    budget = drain.Budget(args.budget_seconds)
    # No exemptions: robots.txt is asked for every host, every run, and a
    # Crawl-delay (Missouri's 20 s, palegis.us none) raises that host's throttle.
    client = GuardedClient(http, FEED, budget=budget)
    tax = filt.load_taxonomy(ust.TAXONOMY)
    wl = ust.empty_watchlist()
    print("us-states-routes: {0}".format(", ".join(sorted(only))))
    if "pa" in only:
        print("  " + read_pennsylvania(conn, client, tax, wl, today).line())
    if "mo" in only:
        print("  " + read_missouri(conn, client, tax, wl, today, budget,
                                   max_files=args.mo_max_files).line())
    if "ar" in only:
        print("  " + read_arkansas(conn, client, tax, wl, today, budget, days=args.ar_days,
                                   max_bills=args.ar_max_bills).line())
    stamp_heartbeat(conn, today)
    gaps = conn.execute("SELECT COUNT(*) FROM gaps WHERE edition=? AND (detail LIKE "
                        "'Pennsylvania%' OR detail LIKE 'Missouri%' OR detail LIKE 'Arkansas%')",
                        (today,)).fetchone()[0]
    print("us-states-routes: done in {0:.0f}s; {1} gap(s)".format(budget.spent(), gaps))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
