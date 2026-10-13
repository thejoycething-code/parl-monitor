#!/usr/bin/env python3
"""Australia's states and territories: bills with their stage, Acts, and
divisions with every member's vote (New South Wales, Victoria, South
Australia, Tasmania, the ACT), for the Australian edition.

    python3 tools/au_states.py                        # every source
    python3 tools/au_states.py --sources nsw,sa       # some of them
    python3 tools/au_states.py --sources vic-votes    # one records source
    python3 tools/au_states.py --nsw-years 2023,2024  # read NSW further back
    python3 tools/au_states.py --reclassify           # re-derive areas, offline
    python3 tools/au_states.py --db /tmp/aus.db       # anywhere but the store

13 October 2026; docs/australia-states-scope.md has every measurement.

THE SOURCES, all keyless, all probed live from the laptop:

  nsw  api.parliament.nsw.gov.au, the Parliament's Hansard API (JSON and
       XML): /api/hansard/search/year/YYYY lists the sitting days with each
       House's contents document; /search/daily/tableofcontents/<id> gives
       every topic of the day with its bills (by the Parliament's bill ID),
       each stage taken ('First Reading', 'Second Reading Debate', 'Assent'),
       every speaker (member ID, name, electorate) and EVERY DIVISION with
       each member's ID under ayes, noes and pairs. The division's question
       and result are in the topic's fragment (/search/daily/fragment/<uid>),
       read only for divisions on our ground. www.parliament.nsw.gov.au
       itself is behind a Cloudflare challenge and is never asked.
  vic  www.legislation.vic.gov.au (the Parliamentary Counsel's register,
       where the Parliament's own site sends its readers for bills): the
       search listing's backend, POST /api/tide/elasticsearch/<index>/_search,
       one request for every bill of the current and last year and every
       bill still before Parliament, each with its stage in the register's
       words ('Council - second reading (passed Assembly)'), its introducer
       and its node ID. The listing's PDF attachments are excluded.
  qld  www.legislation.qld.gov.au (the Queensland PCO's register):
       /projectdata, the browse pages' JSON backend, for every bill of the
       current Parliament as introduced (government or private member's) and
       every Act as passed. The Parliament's own site is behind an Azure WAF
       challenge, so a Queensland bill's stage is 'introduced' until an Act
       of its name appears.
  sa   the Parliament of South Australia's Legislative Tracking system
       (salt.parliament.sa.gov.au), whose backend
       (prod-internet-salt-functionapp.azurewebsites.net/api/) answers the
       session's every bill AND motion with its status, house and introducer
       in one request, and the session's members in another.
  wa   www.legislation.wa.gov.au, the 'as passed' Atom feed: Acts only. The
       Parliament's bill progress (parliament.wa.gov.au) is behind an Azure
       WAF challenge.
  tas  search.parliament.tas.gov.au, the Parliament's own search engine,
       /search/quicksearch/<year>/Bills: the titles of every bill named in
       the Hansard that year, with no stage or ID; and
       www.legislation.tas.gov.au/feed?id=act-year, the year's royal assents.
       www.parliament.tas.gov.au is behind a Cloudflare challenge.
  act  www.legislation.act.gov.au/WhatsNew/Index, the register's last seven
       days (robots.txt: Crawl-delay 10, and /results, where the bill lists
       live, disallowed): Acts notified and bills presented when there are
       any. www.parliament.act.gov.au is behind a Cloudflare challenge.
  nt   legislation.nt.gov.au, Bills by session: the current Assembly's every
       bill with its serial number, introduced and passed dates and remarks.
       parliament.nt.gov.au is behind a Cloudflare challenge.

DIVISIONS BEYOND NSW (13 October 2026, src/au_states_votes.py parses them):

  vic-votes  www.parliament.vic.gov.au (the Parliament's own site answers
       us): the House documents listing's JSON (/api/search/house-papers/,
       what its page loads), then each sitting day's Votes and Proceedings
       (Assembly) and Minutes of the Proceedings (Council) as Word files:
       every division with every member's name.
  sa-votes  the Parliament's document library backend
       (dynamic-content-api.parliament.sa.gov.au, which its Votes and
       Proceedings and Minutes pages embed): the latest Parliament's session
       folder, then each day's PDF through the short-lived read-only link the
       library hands every visitor. The Council's 56th-Parliament minutes
       are not in the library yet; its latest folder (the 55th) is read.
  tas-votes  search.parliament.tas.gov.au: the year's sitting days, then
       the Hansard search for each day and each House's Word file, whose
       divisions are tables (Ayes left, Noes right, pairs below).
  act-votes  www.hansard.act.gov.au (the Assembly's Hansard site; robots.txt
       allows everything): each sitting day's Hansard PDF; the pages with
       'The Assembly voted' are read with their x positions (names in
       columns).

  Each record is read once (aus_hansard_days), newest first, a few a run;
  members are keyed by the printed name ('vic:name:moira-deeming'), the
  records carrying no IDs. Big files are not archived (archive=False).

Not read, and why: every parliament site behind a challenge (NSW, Queensland,
Western Australia, Tasmania, the ACT, the Northern Territory), from GitHub's
runners too (probe of 13 October 2026), South Australia's Hansard search
(Azure WAF challenge), the NSW and South Australian legislation registers
(Cloudflare and a 403). No divisions for Queensland, Western Australia or the
Northern Territory: every record of them is behind the challenges, and
Territory Stories (the NT Library's archive) disallows its PDFs in
robots.txt. Every route tried is in the scope doc.

CLASSIFICATION. The shared English taxonomy (config/taxonomy.yaml) on every
title, plus config/watchlist-au-states.yaml applied by bill key, never by
title. A division takes its bills' areas; `own_areas` keeps its own words'
match apart. Area 11 (migration) is stored and never shown.

ROBOTS.TXT AT RUN TIME: every request goes through
src/robots_guard.GuardedClient (no exemptions), which reads each host's
robots.txt once per run before the first request. A disallowed URL, or a host
whose robots.txt answers 5xx or not at all, is a [gap] line and a gaps row,
never fetched and never fatal; a 4xx robots.txt means no rules; a Crawl-delay
raises that host's interval (legislation.act.gov.au asks 10 seconds,
legislation.vic.gov.au 2).

Separation guarantee: writes aus_* tables and the shared gaps table only. ONE
WRITER AT A TIME on the store.

Exit codes: 0 clean, 3 stored what it could and recorded gaps, 1 otherwise.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_states_store as aus, au_states_votes as votes, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import GuardedClient, RobotsRefused  # noqa: E402

FEED = "au-states"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-au-states.yaml")
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)
BUDGET_S = drain.DEFAULT_S

SOURCE_ORDER = ("nsw", "vic", "qld", "sa", "wa", "tas", "act", "nt")
# Divisions beyond NSW (13 October 2026, src/au_states_votes.py): the official
# records with each member's vote, on hosts that answer us.
VOTES_ORDER = ("vic-votes", "sa-votes", "tas-votes", "act-votes")
# A plain run reads the list sources, then the votes records, then NSW, whose
# first backfill is the slow part and drains under the budget over weeks.
DEFAULT_ORDER = ("vic", "qld", "sa", "wa", "tas", "act", "nt") + VOTES_ORDER + ("nsw",)

# --- New South Wales ---
NSW_API = "https://api.parliament.nsw.gov.au/api/hansard/search/"
NSW_YEAR = NSW_API + "year/{year}"
NSW_TOC = NSW_API + "daily/tableofcontents/{id}"
NSW_FRAGMENT = NSW_API + "daily/fragment/{id}"
# A human reader's links (the site refuses our collectors, not people).
NSW_BILL_URL = "https://www.parliament.nsw.gov.au/bills/Pages/bill-details.aspx?pk={id}"
NSW_HANSARD_URL = "https://www.parliament.nsw.gov.au/Hansard/Pages/HansardResult.aspx#/docid/{id}"
NSW_CHAMBERS = {"Legislative Assembly": "la", "Legislative Council": "lc"}
# Fragments read per run for divisions on our ground (about 140 KB each).
NSW_FRAGMENTS_PER_RUN = 40

# --- Victoria ---
VIC_SEARCH = ("https://www.legislation.vic.gov.au/api/tide/elasticsearch/"
              "content-legislation-vic-gov-au__production__sapi_node/_search")
VIC_BASE = "https://www.legislation.vic.gov.au"

# --- Queensland ---
QLD_DATA = "https://www.legislation.qld.gov.au/projectdata"
QLD_BASE = "https://www.legislation.qld.gov.au"
QLD_PARLIAMENT = 58   # elected 26 October 2024; the next election is due October 2028

# --- South Australia ---
SA_API = "https://prod-internet-salt-functionapp.azurewebsites.net/api/"
SA_APP = "https://salt.parliament.sa.gov.au/"

# --- Western Australia, Tasmania, the ACT, the Northern Territory ---
WA_ASPASSED = "https://www.legislation.wa.gov.au/legislation/statutes.nsf/aspassed.atom"
TAS_BILLS = "https://search.parliament.tas.gov.au/search/quicksearch/{year}/Bills"
TAS_ACTS = "https://www.legislation.tas.gov.au/feed?id=act-year"
ACT_WHATSNEW = "https://www.legislation.act.gov.au/WhatsNew/Index"
ACT_BASE = "https://www.legislation.act.gov.au"
NT_SESSIONS = "https://legislation.nt.gov.au/en/LegislationPortal/Bills/By-Session"
NT_BASE = "https://legislation.nt.gov.au/"

# --- Divisions beyond NSW: the official records (src/au_states_votes.py) ---
# Victoria: the House documents database's listing (the JSON its page loads;
# 865788 is the 'Minutes of the Houses' listing's page ID), then each day's
# Votes and Proceedings (Assembly) and Minutes of the Proceedings (Council)
# as Word files on the same host.
VIC_PARL = "https://www.parliament.vic.gov.au"
VIC_PAPERS = VIC_PARL + "/api/search/house-papers/865788?page={page}&pageSize=50&sortType=2"
VIC_PAPER_KINDS = (("Votes and Proceedings", "Legislative Assembly"),
                   ("Minutes of the Proceedings", "Legislative Council"))
# South Australia: the Parliament's document library (the backend of the
# library its Votes and Proceedings and Minutes pages embed): folders by
# Parliament and session, each file a sitting day's PDF; a file's download
# link is a short-lived read-only link the library hands every visitor.
SA_DOCLIB = "https://dynamic-content-api.parliament.sa.gov.au/api/documentlibrary"
SA_DOCLINK = ("https://dynamic-content-api.parliament.sa.gov.au/api/GetFileDownloadLink?"
              "controlId={ctrl}&fileId={id}")
SA_LIBRARIES = (("7", "House of Assembly"), ("2", "Legislative Council"))
# Tasmania: each sitting day's Hansard (Word) for each House, found by the
# Parliament's own search engine from the year's sitting days.
TAS_SEARCH_BASE = "https://search.parliament.tas.gov.au"
TAS_SITTINGS = TAS_SEARCH_BASE + "/search/quicksearch/{year}/sittingdays.html"
TAS_SEARCH = TAS_SEARCH_BASE + "/Search/search/search?IW_FIELD_ADVANCE_PHRASE={phrase}&IW_DATABASE=Hansard&IW_SORT=-9"
TAS_HOUSES = (("HA", "House of Assembly"), ("LC", "Legislative Council"))
# The ACT: the Assembly's Hansard site, each sitting day's PDF.
ACT_HANSARD = "https://www.hansard.act.gov.au/hansard/{assembly}/{year}/debates(PDF).htm"
ACT_ASSEMBLY = "11th-assembly"   # elected 19 October 2024; the next election is October 2028
# Records read per run, newest first; the backlog drains over weekly runs.
VIC_VOTES_PER_RUN = 30
SA_VOTES_PER_RUN = 8             # per House
TAS_VOTES_PER_RUN = 8            # Word files of about 3 MB
ACT_VOTES_PER_RUN = 4            # PDFs of about 1 MB
VOTES_WINDOW_DAYS = 400          # how far back a first read goes
TAS_WINDOW_DAYS = 180
TAS_GIVE_UP_DAYS = 21            # a House with no Hansard this long after a sitting day did not sit
CHAMBER_CODE = {"Legislative Assembly": "la", "Legislative Council": "lc", "House of Assembly": "ha"}

# robots.txt Crawl-delays raise these where higher (src/robots_guard).
HOST_THROTTLE = {"api.parliament.nsw.gov.au": 1.5, "www.legislation.act.gov.au": 10.0,
                 "www.legislation.vic.gov.au": 2.0, "www.parliament.vic.gov.au": 2.0,
                 "dynamic-content-api.parliament.sa.gov.au": 2.0,
                 "search.parliament.tas.gov.au": 3.0, "www.hansard.act.gov.au": 2.0}


# --- small helpers ------------------------------------------------------------


# Most pages of a bill list read in one run (a cap, not the 11 issue areas).
MAX_LIST_PAGES = 10

def fold(text):
    """Strip tags, unescape, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:120]


def iso_dmy(text):
    """'26/08/2026' -> '2026-08-26'; anything else -> None."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    if not m:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def iso10(text):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", text or "")
    return m.group(1) if m else None


def first(value):
    """The register's single-valued lists: ['x'] -> 'x'."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def bill_name(title):
    """A title folded for matching a Bill to its Act: lower case, 'act' read
    as 'bill', the year and punctuation dropped."""
    t = (title or "").lower().replace("’", "'")
    t = re.sub(r"\b(act|bill)\b", "bill", t)
    t = re.sub(r"\b(19|20)\d\d\b", " ", t)
    t = re.sub(r"\(no\.? ?\d+\)", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    print("  [gap] " + detail)


def _read(conn, source, now, items, status):
    conn.execute(
        "INSERT INTO aus_reads (source, last_seen, items, status) VALUES (?,?,?,?) "
        "ON CONFLICT(source) DO UPDATE SET last_seen=excluded.last_seen, items=excluded.items, "
        "status=excluded.status", (source, now, items, status))


def _cause(e):
    return getattr(e, "reason", None) or str(getattr(e, "cause", e))[:120]


# --- classification -------------------------------------------------------------

def load_taxonomy(path=None):
    path = path or TAXONOMY
    return filt.load_taxonomy(path) if os.path.exists(path) else None


_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-au-states.yaml."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        raw = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


def classify(tax, key, *texts, watch_path=None):
    """(areas or None, terms, tier). None when there is no taxonomy."""
    if tax is None:
        return None, [], None
    res = filt.filter_item(tax, filt.Watchlist(entities=[], bill_titles=[], act_shorts=[]),
                           *[t for t in texts if t])
    areas = set(res.issue_areas or [])
    terms = list(res.matched_terms or [])
    tier = res.tier
    hit = watchlist(watch_path).get(key) if key else None
    if hit:
        areas |= set(hit[0])
        terms.append("watch:" + key)
        tier = tier or 2
    return sorted(areas), terms, tier


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


def _areas_sql(areas):
    return None if areas is None else aus.dumps(areas)


# --- storing ---------------------------------------------------------------------

def store_bill(conn, tax, b, today, seed):
    """Upsert one bill; record a stage event when its stage changed. Returns
    (areas, changed)."""
    key = "{0}:{1}".format(b["state"], b["ext_id"])
    areas, terms, tier = classify(tax, key, b["title"])
    old = conn.execute("SELECT stage, status FROM aus_bills WHERE bill_key=?", (key,)).fetchone()
    stage_date = b.get("stage_date")
    conn.execute(
        "INSERT INTO aus_bills (bill_key, state, ext_id, kind, title, chamber, introduced, "
        "introduced_by, stage, stage_date, status, url, areas, matched_terms, tier, first_seen, "
        "last_seen, seed) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET kind=excluded.kind, title=excluded.title, "
        "chamber=COALESCE(excluded.chamber, aus_bills.chamber), "
        "introduced=COALESCE(excluded.introduced, aus_bills.introduced), "
        "introduced_by=COALESCE(excluded.introduced_by, aus_bills.introduced_by), "
        "stage=COALESCE(excluded.stage, aus_bills.stage), "
        "stage_date=COALESCE(excluded.stage_date, aus_bills.stage_date), "
        "status=CASE WHEN aus_bills.act_key IS NOT NULL THEN aus_bills.status "
        "ELSE COALESCE(excluded.status, aus_bills.status) END, "
        "url=COALESCE(excluded.url, aus_bills.url), areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, b["state"], str(b["ext_id"]), b.get("kind") or "bill", b["title"], b.get("chamber"),
         b.get("introduced"), b.get("introduced_by"), b.get("stage"), stage_date,
         b.get("status") or "before", b.get("url"), _areas_sql(areas), aus.dumps(terms), tier,
         today, today, 1 if seed else 0))
    changed = bool(b.get("stage")) and (old is None or old[0] != b.get("stage"))
    if changed and not (old is None and seed):
        # A stage first seen on a later read is dated by the source when it
        # dates it (Victoria's `changed`), else by this read.
        event_date = stage_date if (stage_date and old is not None) else (
            b.get("introduced") if old is None else today) or today
        conn.execute("INSERT OR IGNORE INTO aus_bill_events (bill_key, date, chamber, stage, source) "
                     "VALUES (?,?,?,?,?)", (key, event_date, b.get("chamber") or "",
                                            b["stage"], "list"))
    return areas, changed


def store_act(conn, tax, a, today, seed):
    key = "{0}:{1}".format(a["state"], a["ext_id"])
    areas, terms, tier = classify(tax, key, a["title"])
    conn.execute(
        "INSERT INTO aus_acts (act_key, state, title, made, number, url, areas, matched_terms, "
        "tier, first_seen, last_seen, seed) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(act_key) DO UPDATE SET title=excluded.title, "
        "made=COALESCE(excluded.made, aus_acts.made), number=COALESCE(excluded.number, aus_acts.number), "
        "url=COALESCE(excluded.url, aus_acts.url), areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, a["state"], a["title"], a.get("made"), a.get("number"), a.get("url"),
         _areas_sql(areas), aus.dumps(terms), tier, today, today, 1 if seed else 0))
    return areas


def settle_acts(conn, state, today):
    """Mark each stored bill of `state` that an Act of its name settles:
    status 'assented', act_key, and an 'Assent' event on the Act's date.
    Matches the folded title (bill_name); when two bills share a name the
    latest introduced wins. Returns the bills newly settled."""
    bills = {}
    for key, title, introduced in conn.execute(
            "SELECT bill_key, title, introduced FROM aus_bills WHERE state=? AND kind != 'motion'",
            (state,)).fetchall():
        name = bill_name(title)
        if name and (name not in bills or (introduced or "") > (bills[name][1] or "")):
            bills[name] = (key, introduced)
    n = 0
    for act_key, title, made, bill_key in conn.execute(
            "SELECT act_key, title, made, bill_key FROM aus_acts WHERE state=?", (state,)).fetchall():
        hit = bills.get(bill_name(title))
        if not hit:
            continue
        key = hit[0]
        row = conn.execute("SELECT act_key FROM aus_bills WHERE bill_key=?", (key,)).fetchone()
        if row and row[0] == act_key:
            continue
        conn.execute("UPDATE aus_bills SET act_key=?, status='assented', "
                     "stage=CASE WHEN stage IS NULL OR stage IN ('introduced', 'named in the Hansard') "
                     "THEN 'Act' ELSE stage END, stage_date=COALESCE(?, stage_date) WHERE bill_key=?",
                     (act_key, made, key))
        conn.execute("UPDATE aus_acts SET bill_key=? WHERE act_key=?", (key, act_key))
        conn.execute("INSERT OR IGNORE INTO aus_bill_events (bill_key, date, chamber, stage, source) "
                     "VALUES (?,?,?,?,?)", (key, made or today, "", "Assent", "act"))
        n += 1
    return n


def first_read(conn, source):
    return conn.execute("SELECT 1 FROM aus_reads WHERE source=? AND status='ok'",
                        (source,)).fetchone() is None


# --- New South Wales: the Hansard API ------------------------------------------------

def parse_nsw_year(data):
    """[(date, chamber, toc_id, pdf_id, draft)] from a year's sitting days."""
    out = []
    for day in data or []:
        for ev in day.get("Events") or []:
            if ev.get("TocDocId") and ev.get("Chamber") in NSW_CHAMBERS:
                out.append((day.get("date"), ev["Chamber"], ev["TocDocId"], ev.get("PdfDocId"),
                            1 if ev.get("Uncorrected") else 0))
    return out


def _texts(block, tag):
    m = re.search(r"<{0}>(.*?)</{0}>".format(tag), block, re.S)
    return m.group(1) if m else ""


def _division(block):
    """{ayes, noes, pairs, votes: [(member_id, vote)]} from a <division>."""
    out = {"votes": []}
    for side, member, vote in (("ayes", "aye", "aye"), ("noes", "noe", "no")):
        part = _texts(block, side)
        count = re.search(r"<count>(\d+)</count>", part)
        ids = re.findall(r"<{0}>\s*<id>(\d+)</id>".format(member), part)
        out[side] = int(count.group(1)) if count else len(ids)
        out["votes"] += [(i, vote) for i in ids]
    pairs = re.findall(r"<pair>\s*<id>(\d+)</id>", _texts(block, "pairs"))
    out["pairs"] = len(pairs) // 2
    out["votes"] += [(i, "pair") for i in pairs]
    return out


def parse_nsw_toc(text):
    """One House's sitting day: {date, chamber, topics: [{uid, proceeding,
    heading, bills: [(id, title)], stages: [name], divisions: [{stage, ...}]}],
    talkers: {id: (name, electorate)}}."""
    date = iso10(_texts(text, "date"))
    chamber = fold(_texts(text, "chamber"))
    talkers = {}
    for m in re.finditer(r"<talker>(.*?)</talker>", text, re.S):
        t = m.group(1)
        mid = fold(_texts(t, "id"))
        name = fold(_texts(t, "name"))
        if mid and name:
            talkers[mid] = (name, fold(_texts(t, "electorate")) or None)
    topics = []
    for proc in re.findall(r"<proceeding>(.*?)</proceeding>", text, re.S):
        pname = fold(_texts(_texts(proc, "proceedinginfo"), "text"))
        for m in re.finditer(r'<topic uid="([^"]+)"[^>]*>(.*?)</topic>', proc, re.S):
            uid, body = m.group(1), m.group(2)
            info = _texts(body, "topicinfo")
            bills = [(i, fold(t)) for i, t in re.findall(
                r'<text id="(\d+)" type="Bill">(.*?)</text>', info, re.S)]
            heads = [fold(t) for t in re.findall(r'<text[^>]*type="(?!Bill)[^"]*"[^>]*>(.*?)</text>',
                                                 info, re.S)]
            heads += [fold(t) for t in re.findall(r"<text>(.*?)</text>", info, re.S)]
            stages, divisions = [], []
            for sp in re.findall(r"<subproceeding>(.*?)</subproceeding>", body, re.S):
                sname = fold(_texts(_texts(sp, "subproceedinginfo"), "text"))
                if sname:
                    stages.append(sname)
                for d in re.findall(r"<division>(.*?)</division>", sp, re.S):
                    divisions.append(dict(_division(d), stage=sname or None))
            # A division straight under the topic (no subproceeding).
            rest = re.sub(r"<subproceeding>.*?</subproceeding>", "", body, flags=re.S)
            for d in re.findall(r"<division>(.*?)</division>", rest, re.S):
                divisions.append(dict(_division(d), stage=None))
            topics.append({"uid": uid, "proceeding": pname, "bills": bills,
                           "heading": "; ".join(h for h in heads if h) or None,
                           "stages": stages, "divisions": divisions})
    return {"date": date, "chamber": chamber, "topics": topics, "talkers": talkers}


def nsw_stage_status(stage):
    s = (stage or "").lower()
    if "assent" in s:
        return "assented"
    if "negatived" in s or "defeated" in s:
        return "defeated"
    if "withdrawn" in s or "discharged" in s:
        return "withdrawn"
    return "before"


def store_nsw_day(conn, tax, toc, today, toc_id):
    """Store one House's day; returns (bills touched, divisions, on our ground)."""
    date, chamber = toc["date"], toc["chamber"]
    ch = NSW_CHAMBERS.get(chamber, slug(chamber))
    for mid, (name, electorate) in toc["talkers"].items():
        conn.execute(
            "INSERT INTO aus_members (member_key, state, name, electorate, chamber, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET name=excluded.name, "
            "electorate=COALESCE(excluded.electorate, aus_members.electorate), "
            "chamber=excluded.chamber, last_seen=MAX(aus_members.last_seen, excluded.last_seen)",
            ("nsw:" + mid, "nsw", name, electorate, chamber, date, date))
    touched, ndiv, ours = set(), 0, 0
    for t in toc["topics"]:
        keys = []
        for bid, title in t["bills"]:
            key = "nsw:" + bid
            keys.append(key)
            row = conn.execute("SELECT stage_date FROM aus_bills WHERE bill_key=?", (key,)).fetchone()
            last = t["stages"][-1] if t["stages"] else None
            newer = row is None or (row[0] or "") <= date
            b = {"state": "nsw", "ext_id": bid, "title": title, "kind": "bill",
                 "url": NSW_BILL_URL.format(id=bid)}
            # Introduced: the earliest sitting day with a first reading (the
            # backfill reads newest first, so any day may be the one).
            if any("first reading" in s.lower() or "introduc" in s.lower() for s in t["stages"]):
                b["introduced"] = date
                b["chamber"] = chamber
            areas, _ = _store_nsw_bill(conn, tax, b, today, last if newer else None,
                                       date if newer else None, chamber, sitting=date)
            for s in t["stages"]:
                conn.execute("INSERT OR IGNORE INTO aus_bill_events (bill_key, date, chamber, stage, "
                             "source) VALUES (?,?,?,?,?)", (key, date, chamber, s, "hansard"))
            touched.add(key)
        bill_areas = set()
        for key in keys:
            r = conn.execute("SELECT areas FROM aus_bills WHERE bill_key=?", (key,)).fetchone()
            bill_areas |= set(json.loads(r[0] or "[]")) if r and r[0] else set()
        own, terms, _tier = classify(tax, None, t["heading"] if not keys else "")
        for d in t["divisions"]:
            ndiv += 1
            dkey = "nsw:{0}:{1}:{2}".format(date, ch, ndiv)
            areas = sorted(set(own or []) | bill_areas) if own is not None else None
            conn.execute(
                "INSERT INTO aus_divisions (division_key, state, chamber, date, topic_uid, heading, "
                "stage, bill_keys, ayes, noes, pairs, url, areas, own_areas, matched_terms, first_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(division_key) DO UPDATE SET "
                "topic_uid=excluded.topic_uid, heading=excluded.heading, stage=excluded.stage, "
                "bill_keys=excluded.bill_keys, ayes=excluded.ayes, noes=excluded.noes, "
                "pairs=excluded.pairs, url=excluded.url, areas=excluded.areas, "
                "own_areas=excluded.own_areas, matched_terms=excluded.matched_terms",
                (dkey, "nsw", chamber, date, t["uid"],
                 "; ".join(title for _b, title in t["bills"]) or t["heading"], d["stage"],
                 aus.dumps(keys), d["ayes"], d["noes"], d["pairs"],
                 NSW_HANSARD_URL.format(id=t["uid"]), _areas_sql(areas), _areas_sql(own),
                 aus.dumps(terms), today))
            conn.execute("DELETE FROM aus_votes WHERE division_key=?", (dkey,))
            conn.executemany("INSERT OR IGNORE INTO aus_votes (division_key, member_key, vote) "
                             "VALUES (?,?,?)", [(dkey, "nsw:" + m, v) for m, v in d["votes"]])
            ours += on_our_ground(areas)
    conn.execute("INSERT INTO aus_hansard_days (state, date, chamber, toc_id, draft, read_on, topics) "
                 "VALUES (?,?,?,?,?,?,?) ON CONFLICT(state, date, chamber) DO UPDATE SET "
                 "toc_id=excluded.toc_id, read_on=excluded.read_on, topics=excluded.topics",
                 ("nsw", date, chamber, toc_id, None, today, len(toc["topics"])))
    return len(touched), ndiv, ours


def _store_nsw_bill(conn, tax, b, today, stage, stage_date, chamber, sitting=None):
    """A bill first met on a sitting day more than a week before the run
    (the backfill) is a seed: new in the edition only by its introduction."""
    key = "nsw:" + b["ext_id"]
    week_ago = (datetime.date.fromisoformat(today) - datetime.timedelta(days=7)).isoformat()
    backfill = bool(sitting) and sitting <= week_ago
    areas, terms, tier = classify(tax, key, b["title"])
    conn.execute(
        "INSERT INTO aus_bills (bill_key, state, ext_id, kind, title, chamber, introduced, stage, "
        "stage_date, status, url, areas, matched_terms, tier, first_seen, last_seen, seed) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(bill_key) DO UPDATE SET "
        "title=excluded.title, introduced=CASE WHEN aus_bills.introduced IS NULL THEN "
        "excluded.introduced WHEN excluded.introduced IS NULL THEN aus_bills.introduced "
        "ELSE MIN(aus_bills.introduced, excluded.introduced) END, "
        "chamber=CASE WHEN excluded.introduced IS NOT NULL AND (aus_bills.introduced IS NULL OR "
        "excluded.introduced < aus_bills.introduced) THEN excluded.chamber ELSE aus_bills.chamber END, "
        "stage=COALESCE(excluded.stage, aus_bills.stage), "
        "stage_date=COALESCE(excluded.stage_date, aus_bills.stage_date), "
        "status=CASE WHEN excluded.stage IS NULL THEN aus_bills.status ELSE excluded.status END, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (key, "nsw", b["ext_id"], "bill", b["title"], b.get("chamber"), b.get("introduced"),
         stage, stage_date, nsw_stage_status(stage), b["url"], _areas_sql(areas), aus.dumps(terms),
         tier, today, today, 1 if backfill else 0))
    return areas, True


# 'The question is that ...', running past the full stops of honorifics
# ('the amendment of the Hon. Rod Roberts be agreed to').
QUESTION = (r"((?:The )?question is (?:that|whether)(?:[^.]|\.(?=\S)|(?<=\bHon)\.|(?<=\bMr)\."
            r"|(?<=\bMs)\.|(?<=\bMrs)\.|(?<=\bDr)\.|(?<=\bNo)\.|(?<=\bSt)\.)*\.)")
# A bill whose second or third reading is negatived on division is defeated.
READING = re.compile(r"bill be now read a (second|third) time", re.I)


def parse_nsw_fragment(text):
    """[(question, result)] for each division in a topic's fragment, in order:
    the last 'question is ...' sentence before 'divided', and the first
    'agreed to' / 'negatived' sentence after the tally."""
    body = text[text.find("<fragment.text"):] if "<fragment.text" in text else text
    plain = fold(body)
    out = []
    pos = 0
    for m in re.finditer(r"The (House|Committee|Council) divided\.", plain):
        before = plain[pos:m.start()]
        qs = re.findall(QUESTION, before, re.I)
        after = plain[m.end():m.end() + 6000]
        res = re.search(r"((?:Motion|Question|Amendment|Amendments|Bill|Clause|Clauses|Schedule|"
                        r"Schedules|Original question|Third reading)[^.]{0,80}?"
                        r"(?:agreed to|negatived|resolved in the (?:affirmative|negative))\.)", after)
        out.append((qs[-1].strip() if qs else None, res.group(1).strip() if res else None))
        pos = m.end()
    return out


def nsw_years(today, years=None):
    if years:
        return [int(y) for y in years]
    # This year and last: a bill introduced last year and still moving needs
    # its earlier stages, and the backlog drains newest first under the budget.
    return [int(today[:4]) - 1, int(today[:4])]


def pull_nsw(conn, client, today, tax, budget, years=None):
    """(days read, bills touched, divisions, on our ground, gaps)."""
    days = []
    gaps = 0
    for year in nsw_years(today, years):
        try:
            data = client.get_json(NSW_YEAR.format(year=year), FEED, "nsw-year-{0}".format(year))
        except FetchError as e:
            _gap(conn, today, "NSW Hansard: the {0} sitting days: {1}".format(year, _cause(e)))
            _read(conn, "nsw", today, 0, "failed: " + _cause(e)[:80])
            conn.commit()
            return 0, 0, 0, 0, 1
        days += parse_nsw_year(data)
    done = {(d, c) for d, c in conn.execute(
        "SELECT date, chamber FROM aus_hansard_days WHERE state='nsw'").fetchall()}
    todo = sorted([d for d in days if (d[0], d[1]) not in done], reverse=True)
    read = touched = ndiv = ours = 0
    for date, chamber, toc_id, _pdf, _draft in todo:
        if budget.exhausted():
            print(budget.disclose("NSW sitting day(s)", read))
            _gap(conn, today, "NSW Hansard: time budget reached with {0} House sitting day(s) "
                              "unread (read next run)".format(len(todo) - read))
            gaps += 1
            break
        try:
            text = client.get_text(NSW_TOC.format(id=toc_id), FEED, "nsw-toc-" + toc_id)
        except FetchError as e:
            _gap(conn, today, "NSW Hansard {0} {1}: {2}".format(date, chamber, _cause(e)))
            gaps += 1
            if getattr(e, "host_skipped", False):
                break
            continue
        toc = parse_nsw_toc(text)
        if not toc["date"]:
            toc["date"], toc["chamber"] = date, chamber
        t, n, o = store_nsw_day(conn, tax, toc, today, toc_id)
        read += 1
        touched += t
        ndiv += n
        ours += o
        conn.commit()
    gaps += pull_nsw_fragments(conn, client, today, budget)
    _read(conn, "nsw", today, read, "ok" if not gaps else "gaps")
    conn.commit()
    return read, touched, ndiv, ours, gaps


def pull_nsw_fragments(conn, client, today, budget, limit=NSW_FRAGMENTS_PER_RUN):
    """Read the question and result of divisions on our ground, newest first."""
    rows = conn.execute(
        "SELECT topic_uid, MIN(date) FROM aus_divisions WHERE state='nsw' AND fragment_read IS NULL "
        "AND areas IS NOT NULL AND areas NOT IN ('[]', '[11]') GROUP BY topic_uid "
        "ORDER BY MIN(date) DESC LIMIT ?", (limit,)).fetchall()
    gaps = 0
    for uid, _date in rows:
        if budget.exhausted():
            break
        try:
            text = client.get_text(NSW_FRAGMENT.format(id=uid), FEED, "nsw-fragment-" + uid)
        except FetchError as e:
            _gap(conn, today, "NSW Hansard fragment {0}: {1}".format(uid, _cause(e)))
            gaps += 1
            continue
        found = parse_nsw_fragment(text)
        divs = _topic_divisions(conn, uid)
        for i, dkey in enumerate(divs):
            q, r = found[i] if i < len(found) else (None, None)
            conn.execute("UPDATE aus_divisions SET question=?, result=?, fragment_read=? "
                         "WHERE division_key=?", (q, r, today, dkey))
            if q and r and READING.search(q) and "negatived" in r.lower():
                defeat_bills(conn, dkey, READING.search(q).group(1))
        conn.commit()
    return gaps


def defeat_bills(conn, dkey, reading):
    """The division's bills are defeated: their second or third reading was
    negatived. A later stage read from a later sitting day overrides this
    (store_nsw_day sets status from the newest stage)."""
    date, chamber, keys = conn.execute("SELECT date, chamber, bill_keys FROM aus_divisions "
                                       "WHERE division_key=?", (dkey,)).fetchone()
    stage = "{0} reading negatived".format(reading.title())
    for key in json.loads(keys or "[]"):
        conn.execute("UPDATE aus_bills SET status='defeated', stage=?, stage_date=? "
                     "WHERE bill_key=? AND (stage_date IS NULL OR stage_date <= ?)",
                     (stage, date, key, date))
        conn.execute("INSERT OR IGNORE INTO aus_bill_events (bill_key, date, chamber, stage, source) "
                     "VALUES (?,?,?,?,?)", (key, date, chamber, stage, "hansard"))


def _topic_divisions(conn, uid):
    """A topic's divisions in the order the day numbered them."""
    keys = [r[0] for r in conn.execute("SELECT division_key FROM aus_divisions WHERE topic_uid=?",
                                       (uid,)).fetchall()]
    return sorted(keys, key=lambda k: int(k.rsplit(":", 1)[1]))


# --- Victoria: the register's search backend -------------------------------------------

def vic_query(today):
    year = int(today[:4])
    return json.dumps({
        "_source": {"excludes": ["es_attachment", "rendered_item", "body"]},
        "size": 500,
        "query": {"bool": {
            "filter": [{"terms": {"type": ["bill"]}}],
            "should": [{"terms": {"field_bill_parliament_current": [True]}},
                       {"terms": {"field_bill_introduced_year": [str(year - 1), str(year)]}}],
            "minimum_should_match": 1}},
        "sort": [{"nid": "desc"}],
    })


VIC_STATUS = (("assent", "assented"), ("defeated", "defeated"), ("negatived", "defeated"),
              ("withdrawn", "withdrawn"), ("lapsed", "lapsed"), ("passed both", "passed"),
              ("awaiting", "passed"))


def parse_vic(data):
    out = []
    for h in ((data or {}).get("hits") or {}).get("hits") or []:
        s = h.get("_source") or {}
        nid, title = first(s.get("nid")), first(s.get("title"))
        if not nid or not title:
            continue
        stage = first(s.get("field_legislation_status"))
        low = (stage or "").lower()
        status = next((v for k, v in VIC_STATUS if k in low), "before")
        url = first(s.get("url")) or ""
        url = re.sub(r"^/site-\d+", "", url)
        assembly = first(s.get("bill_assembly_section_introduced_by"))
        council = first(s.get("bill_council_section_introduced_by"))
        out.append({"state": "vic", "ext_id": str(nid), "title": fold(title), "kind": "bill",
                    "chamber": "Legislative Assembly" if assembly else (
                        "Legislative Council" if council else None),
                    "introduced": iso10(first(s.get("created"))),
                    "introduced_by": fold(assembly or council) or None,
                    "stage": stage, "stage_date": iso10(first(s.get("changed"))),
                    "status": status, "url": VIC_BASE + url if url.startswith("/") else (url or None)})
    return out


def pull_vic(conn, client, today, tax):
    seed = first_read(conn, "vic")
    try:
        data = client.post_json(VIC_SEARCH, vic_query(today), FEED, "vic-bills")
    except FetchError as e:
        _gap(conn, today, "Victoria (legislation.vic.gov.au): {0}".format(_cause(e)))
        _read(conn, "vic", today, 0, "failed: " + _cause(e)[:80])
        conn.commit()
        return 0, 0, 1
    bills = parse_vic(data)
    if not bills:
        _gap(conn, today, "Victoria: the register answered no bills (its search changed shape?)")
        _read(conn, "vic", today, 0, "empty")
        conn.commit()
        return 0, 0, 1
    ours = sum(on_our_ground(store_bill(conn, tax, b, today, seed)[0]) for b in bills)
    _read(conn, "vic", today, len(bills), "ok")
    conn.commit()
    return len(bills), ours, 0


# --- Queensland: the register's browse backend ------------------------------------------

def qld_url(expression, start=1, count=500):
    return QLD_DATA + "?" + urllib.parse.urlencode({
        "ds": "OQPC-BrowseDataSource", "start": start, "count": count, "sortField": "year",
        "sortDirection": "desc", "expression": expression, "subset": "browse"})


def qld_value(rec, key):
    v = rec.get(key)
    if isinstance(v, dict):
        return v.get("__value__")
    return v


def parse_qld(data, acts=False):
    out = []
    for rec in (data or {}).get("data") or []:
        ident, title = qld_value(rec, "id"), qld_value(rec, "title")
        if not ident or not title:
            continue
        ptype = qld_value(rec, "print.type") or ""
        made = iso10(qld_value(rec, "publication.date"))
        if acts:
            out.append({"state": "qld", "ext_id": ident, "title": fold(title), "made": made,
                        "number": "No. {0} of {1}".format(qld_value(rec, "no"), qld_value(rec, "year"))
                        if qld_value(rec, "no") else None,
                        "url": "{0}/view/html/asmade/{1}".format(QLD_BASE, ident)})
        else:
            out.append({"state": "qld", "ext_id": ident, "title": fold(title),
                        "kind": "private bill" if ptype == "bill.firstnongovintro" else "bill",
                        "chamber": "Legislative Assembly", "introduced": made,
                        "stage": "introduced", "status": "before",
                        "url": "{0}/view/html/{1}/{2}".format(QLD_BASE, ptype or "bill.first", ident)})
    return out


QLD_PASSED = "passed (third reading, as amended)"


def pass_qld_bill(conn, b, today):
    """A bill the register prints as passed: stage, status 'passed' (unless an
    Act already settled it) and a dated event. Returns True when it moved."""
    key = "qld:" + b["ext_id"]
    row = conn.execute("SELECT stage, act_key FROM aus_bills WHERE bill_key=?", (key,)).fetchone()
    if not row or row[0] == QLD_PASSED:
        return False
    date = b.get("introduced") or today
    conn.execute("UPDATE aus_bills SET stage=?, stage_date=?, status=CASE WHEN act_key IS NULL "
                 "THEN 'passed' ELSE status END WHERE bill_key=?", (QLD_PASSED, date, key))
    conn.execute("INSERT OR IGNORE INTO aus_bill_events (bill_key, date, chamber, stage, source) "
                 "VALUES (?,?,?,?,?)", (key, date, "Legislative Assembly", QLD_PASSED, "list"))
    return True


def qld_total(data):
    t = (data or {}).get("totalCount")
    return int(t.get("__value__") if isinstance(t, dict) else (t or 0))


def _qld_fetch(client, expression, slug_):
    """Every record of an expression, 500 a page."""
    out, start = [], 1
    while True:
        data = client.get_json(qld_url(expression, start), FEED, "{0}-{1}".format(slug_, start))
        recs = (data or {}).get("data") or []
        out.append(data)
        start += len(recs)
        if not recs or start > qld_total(data) or start > 5000:
            return out


def pull_qld(conn, client, today, tax):
    year = int(today[:4])
    seed_b, seed_a = first_read(conn, "qld-bills"), first_read(conn, "qld-acts")
    bills, acts, gaps = [], [], 0
    for y in (year - 1, year):
        expr = ('Repealed=N AND PrintType=("bill.first" OR "bill.firstnongovintro") AND '
                'ParliamentNo={0} AND Year={1}?'.format(QLD_PARLIAMENT, y))
        try:
            for data in _qld_fetch(client, expr, "qld-bills-{0}".format(y)):
                bills += parse_qld(data)
        except FetchError as e:
            _gap(conn, today, "Queensland bills {0}: {1}".format(y, _cause(e)))
            gaps += 1
        try:
            for data in _qld_fetch(client, "Repealed=N AND PrintType=act.new AND Year={0}?".format(y),
                                   "qld-acts-{0}".format(y)):
                acts += parse_qld(data, acts=True)
        except FetchError as e:
            _gap(conn, today, "Queensland Acts {0}: {1}".format(y, _cause(e)))
            gaps += 1
    ours = sum(on_our_ground(store_bill(conn, tax, b, today, seed_b)[0]) for b in bills)
    for a in acts:
        store_act(conn, tax, a, today, seed_a)
    # Bills as passed (the register's third-reading print, published when the
    # Assembly amended a bill): passage dated before the Act appears.
    for y in (year - 1, year):
        try:
            for data in _qld_fetch(client, 'Repealed=N AND PrintType="bill.third" AND ParliamentNo={0} '
                                           'AND Year={1}?'.format(QLD_PARLIAMENT, y),
                                   "qld-third-{0}".format(y)):
                for b in parse_qld(data):
                    pass_qld_bill(conn, b, today)
        except FetchError as e:
            _gap(conn, today, "Queensland bills as passed {0}: {1}".format(y, _cause(e)))
            gaps += 1
    settled = settle_acts(conn, "qld", today)
    _read(conn, "qld-bills", today, len(bills), "ok" if bills else "empty")
    _read(conn, "qld-acts", today, len(acts), "ok" if acts else "empty")
    if not bills and not gaps:
        _gap(conn, today, "Queensland: the register listed no bills of the {0}th Parliament".format(
            QLD_PARLIAMENT))
        gaps += 1
    conn.commit()
    return len(bills), len(acts), settled, ours, gaps


# --- South Australia: the Legislative Tracking system ------------------------------------

SA_STATUS = (("assented", "assented"), ("awaiting assent", "passed"), ("negatived", "defeated"),
             ("defeated", "defeated"), ("withdrawn", "withdrawn"), ("discharged", "withdrawn"),
             ("lapsed", "lapsed"), ("laid aside", "defeated"))


def sa_session(sessions):
    """The open session (no end date), else the latest."""
    open_ = [s for s in sessions or [] if not s.get("endDate")]
    pool = open_ or list(sessions or [])
    return max(pool, key=lambda s: s.get("startDate") or "") if pool else None


def parse_sa(results):
    out = []
    for r in results or []:
        rid, title = r.get("resultId"), r.get("title")
        if not rid or not title:
            continue
        kind = "motion" if (r.get("type") or "").lower() == "motion" else "bill"
        status = r.get("status")
        low = (status or "").lower()
        mapped = next((v for k, v in SA_STATUS if k in low), "before")
        out.append({"state": "sa", "ext_id": str(rid), "title": fold(title), "kind": kind,
                    "chamber": r.get("fullHouse"), "introduced": iso10(r.get("dateIntroduced")),
                    "introduced_by": fold(r.get("introducedBy")) or None, "stage": status,
                    "status": mapped,
                    "url": "{0}{1}/{2}".format(SA_APP, kind, rid)})
    return out


def pull_sa(conn, client, today, tax):
    try:
        session = sa_session(client.get_json(SA_API + "GetSessions", FEED, "sa-sessions"))
    except FetchError as e:
        _gap(conn, today, "South Australia (Legislative Tracking): {0}".format(_cause(e)))
        _read(conn, "sa", today, 0, "failed: " + _cause(e)[:80])
        conn.commit()
        return 0, 0, 0, 1
    if not session:
        _gap(conn, today, "South Australia: no session listed")
        _read(conn, "sa", today, 0, "empty")
        conn.commit()
        return 0, 0, 0, 1
    seed = first_read(conn, "sa")
    gaps = 0
    try:
        items = parse_sa(client.get_json(
            SA_API + "Search/?" + urllib.parse.urlencode(
                {"resultsPerPage": 4000, "parliamentSession": session["abbreviation"]}),
            FEED, "sa-search"))
    except FetchError as e:
        _gap(conn, today, "South Australia bills and motions: {0}".format(_cause(e)))
        items, gaps = [], gaps + 1
    ours = sum(on_our_ground(store_bill(conn, tax, b, today, seed)[0]) for b in items)
    members = 0
    try:
        for m in client.get_json(SA_API + "GetMembersforSession?sessionId={0}".format(
                session["sessionId"]), FEED, "sa-members") or []:
            if not m.get("memberId"):
                continue
            name = " ".join(x for x in (m.get("title"), m.get("preferredName") or m.get("firstName"),
                                        m.get("lastName")) if x)
            conn.execute(
                "INSERT INTO aus_members (member_key, state, name, electorate, chamber, first_seen, "
                "last_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET "
                "name=excluded.name, last_seen=excluded.last_seen",
                ("sa:{0}".format(m["memberId"]), "sa", fold(name), None, None, today, today))
            members += 1
    except FetchError as e:
        _gap(conn, today, "South Australia members: {0}".format(_cause(e)))
        gaps += 1
    if not items and not gaps:
        _gap(conn, today, "South Australia: the {0} session listed nothing".format(
            session.get("abbreviation")))
        gaps += 1
    _read(conn, "sa", today, len(items), "ok" if items and not gaps else ("gaps" if items else "empty"))
    conn.commit()
    return len(items), members, ours, gaps


# --- Western Australia, Tasmania: Acts from the registers' feeds ----------------------------

def parse_atom_entries(text):
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", text or "", re.S):
        title = re.search(r"<title[^>]*>(.*?)</title>", e, re.S)
        ident = re.search(r"<id>(.*?)</id>", e, re.S)
        link = re.search(r"<link[^>]*href=['\"]([^'\"]+)['\"]", e)
        upd = re.search(r"<updated>(.*?)</updated>", e, re.S)
        out.append({"title": fold(title.group(1)) if title else "",
                    "id": fold(ident.group(1)) if ident else "",
                    "url": html.unescape(link.group(1)) if link else None,
                    "updated": iso10(fold(upd.group(1))) if upd else None})
    return out


def parse_wa(text):
    out = []
    for e in parse_atom_entries(text):
        ident = e["id"].split(":", 1)[0]
        if not ident or not e["title"]:
            continue
        out.append({"state": "wa", "ext_id": ident, "title": e["title"], "made": e["updated"],
                    "url": e["url"]})
    return out


def parse_tas_acts(text):
    out = []
    for e in parse_atom_entries(text):
        if not e["id"].startswith("act-") or not e["title"]:
            continue
        m = re.match(r"act-(\d{4})-0*(\d+)", e["id"])
        out.append({"state": "tas", "ext_id": e["id"], "title": e["title"], "made": e["updated"],
                    "number": "No. {0} of {1}".format(m.group(2), m.group(1)) if m else None,
                    "url": e["url"]})
    return out


def parse_tas_bills(text, year):
    """The year's bill titles from the quick-search page's Hansard links."""
    out, seen = [], set()
    for q in re.findall(r"IW_FIELD_NATURAL_LANGUAGE=([^&\"']+)&(?:amp;)?IW_DATABASE=Hansard", text or ""):
        title = fold(urllib.parse.unquote_plus(html.unescape(q)))
        half = title[:len(title) // 2]
        if len(title) % 2 == 1 and title == half + " " + half:
            title = half   # the page repeats a few titles twice in one link
        if not title or title in seen:
            continue
        seen.add(title)
        out.append({"state": "tas", "ext_id": "{0}:{1}".format(year, slug(title)), "title": title,
                    "kind": "bill", "stage": "named in the Hansard", "status": "unknown",
                    "url": TAS_BILLS.format(year=year)})
    return out


def pull_acts_feed(conn, client, today, tax, state, url, parser, source):
    seed = first_read(conn, source)
    try:
        text = client.get_text(url, FEED, source)
    except FetchError as e:
        _gap(conn, today, "{0} Acts: {1}".format(aus.STATES[state], _cause(e)))
        _read(conn, source, today, 0, "failed: " + _cause(e)[:80])
        conn.commit()
        return 0, 0, 1
    acts = parser(text)
    if not acts:
        _gap(conn, today, "{0}: the Acts feed parsed to nothing (changed shape?)".format(
            aus.STATES[state]))
        _read(conn, source, today, 0, "empty")
        conn.commit()
        return 0, 0, 1
    ours = sum(on_our_ground(store_act(conn, tax, a, today, seed)) for a in acts)
    _read(conn, source, today, len(acts), "ok")
    conn.commit()
    return len(acts), ours, 0


def pull_tas(conn, client, today, tax):
    year = int(today[:4])
    seed = first_read(conn, "tas-bills")
    bills, gaps = [], 0
    for y in (year - 1, year):
        try:
            bills += parse_tas_bills(client.get_text(TAS_BILLS.format(year=y), FEED,
                                                     "tas-bills-{0}".format(y)), y)
        except FetchError as e:
            _gap(conn, today, "Tasmania bills {0}: {1}".format(y, _cause(e)))
            gaps += 1
    ours = sum(on_our_ground(store_bill(conn, tax, b, today, seed)[0]) for b in bills)
    _read(conn, "tas-bills", today, len(bills), "ok" if bills else "empty")
    n_acts, _o, g = pull_acts_feed(conn, client, today, tax, "tas", TAS_ACTS, parse_tas_acts, "tas-acts")
    gaps += g
    settled = settle_acts(conn, "tas", today)
    conn.commit()
    return len(bills), n_acts, settled, ours, gaps


# --- the ACT: the register's last seven days -----------------------------------------------

def parse_act(text):
    """(acts, bills) from What's new: every table whose rows link an Act
    ('/a/2026-12/') or a bill ('/b/db_12345/')."""
    acts, bills = [], []
    for table in re.findall(r"<table[^>]*>(.*?)</table>", text or "", re.S):
        heads = [fold(h).lower() for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if not cells:
                continue
            values = dict(zip(heads, [fold(c) for c in cells]))
            link = re.search(r'href="(/(a|b)/([^"/]+)/?)"', row)
            if not link:
                continue
            name = values.get("name") or fold(cells[1] if len(cells) > 1 else cells[0])
            date = next((iso_act(v) for k, v in values.items() if "date" in k and iso_act(v)), None)
            if link.group(2) == "a":
                typ = values.get("type", "").lower()
                if typ and typ != "act":
                    continue
                acts.append({"state": "act", "ext_id": "A" + link.group(3), "title": name,
                             "made": date, "number": values.get("year and no") or None,
                             "url": ACT_BASE + link.group(1)})
            else:
                bills.append({"state": "act", "ext_id": link.group(3), "title": name, "kind": "bill",
                              "chamber": "Legislative Assembly", "introduced": date,
                              "stage": "presented", "status": "before", "url": ACT_BASE + link.group(1)})
    return acts, bills


ACT_MONTHS = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"))}


def iso_act(text):
    """'8 October 2026' -> '2026-10-08'."""
    m = re.search(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", text or "")
    if not m or m.group(2).lower() not in ACT_MONTHS:
        return iso_dmy(text)
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), ACT_MONTHS[m.group(2).lower()], int(m.group(1)))


def pull_act(conn, client, today, tax):
    seed_a, seed_b = first_read(conn, "act-acts"), first_read(conn, "act-bills")
    try:
        text = client.get_text(ACT_WHATSNEW, FEED, "act-whatsnew")
    except FetchError as e:
        _gap(conn, today, "ACT (legislation register, What's new): {0}".format(_cause(e)))
        _read(conn, "act-acts", today, 0, "failed: " + _cause(e)[:80])
        conn.commit()
        return 0, 0, 0, 1
    if "What's new" not in html.unescape(text) and "What&#39;s new" not in text:
        _gap(conn, today, "ACT: What's new did not render (page changed shape?)")
        _read(conn, "act-acts", today, 0, "empty")
        conn.commit()
        return 0, 0, 0, 1
    acts, bills = parse_act(text)
    ours = sum(on_our_ground(store_act(conn, tax, a, today, seed_a)) for a in acts)
    ours += sum(on_our_ground(store_bill(conn, tax, b, today, seed_b)[0]) for b in bills)
    settle_acts(conn, "act", today)
    # An empty week is not a gap: the register lists what changed in seven days.
    _read(conn, "act-acts", today, len(acts), "ok")
    _read(conn, "act-bills", today, len(bills), "ok")
    conn.commit()
    return len(acts), len(bills), ours, 0


# --- the Northern Territory: bills by session ----------------------------------------------

def parse_nt(text):
    """The current Assembly's bills: the first table on the page."""
    m = re.search(r"<table[^>]*>(.*?)</table>", text or "", re.S)
    if not m:
        return []
    assembly = re.search(r"bill_acc_([A-Z][a-z]+)", text[:m.start()] + text[m.start():m.start() + 3000])
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        link = re.search(r'link\.aspx\?_id=([A-F0-9]{32})', row)
        if len(cells) < 6 or not link:
            continue
        serial, title, intro, passed, amended, remarks = [fold(c) for c in cells[1:7]] + [""] * max(
            0, 7 - len(cells))
        intro_d, passed_d = iso_dmy(intro), iso_dmy(passed)
        low = remarks.lower()
        if passed_d:
            stage, status = "passed", "passed"
        elif "lapse" in low:
            stage, status = remarks, "lapsed"
        elif "negativ" in low or "defeat" in low:
            stage, status = remarks, "defeated"
        elif "withdraw" in low or "discharg" in low:
            stage, status = remarks, "withdrawn"
        else:
            stage, status = "introduced", "before"
        out.append({"state": "nt", "ext_id": link.group(1), "title": title, "kind": "bill",
                    "chamber": "Legislative Assembly", "introduced": intro_d,
                    "stage": stage + (" (amended)" if amended.lower().startswith("yes") and passed_d
                                      else ""),
                    "stage_date": passed_d or intro_d, "status": status,
                    "serial": serial, "assembly": assembly.group(1) if assembly else None,
                    "url": NT_BASE + "~/link.aspx?_id={0}&_z=z".format(link.group(1))})
    return out


def pull_nt(conn, client, today, tax):
    seed = first_read(conn, "nt")
    try:
        text = client.get_text(NT_SESSIONS, FEED, "nt-by-session")
    except FetchError as e:
        _gap(conn, today, "Northern Territory (legislation.nt.gov.au): {0}".format(_cause(e)))
        _read(conn, "nt", today, 0, "failed: " + _cause(e)[:80])
        conn.commit()
        return 0, 0, 1
    bills = parse_nt(text)
    if not bills:
        _gap(conn, today, "Northern Territory: Bills by session parsed to nothing (changed shape?)")
        _read(conn, "nt", today, 0, "empty")
        conn.commit()
        return 0, 0, 1
    ours = sum(on_our_ground(store_bill(conn, tax, b, today, seed)[0]) for b in bills)
    _read(conn, "nt", today, len(bills), "ok")
    conn.commit()
    return len(bills), ours, 0


# --- Divisions beyond NSW: the official records ---------------------------------------
#
# Each record is a sitting day of one House: Victoria's Votes and Proceedings
# and Minutes, South Australia's Votes and Proceedings and Minutes, Tasmania's
# Hansard, the ACT's Hansard. Each is read once (aus_hansard_days keeps the
# record's ID per state, date and House) and its divisions stored like NSW's,
# with every member's vote keyed by the name as printed
# ('vic:name:brad-battin'): these records carry no member IDs.

def _window_start(today, days=VOTES_WINDOW_DAYS):
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()


def _days_read(conn, state):
    return {(d, c): t for d, c, t in conn.execute(
        "SELECT date, chamber, toc_id FROM aus_hansard_days WHERE state=?", (state,)).fetchall()}


def _mark_day(conn, state, date, chamber, doc_id, today, n):
    conn.execute("INSERT INTO aus_hansard_days (state, date, chamber, toc_id, draft, read_on, topics) "
                 "VALUES (?,?,?,?,?,?,?) ON CONFLICT(state, date, chamber) DO UPDATE SET "
                 "toc_id=excluded.toc_id, read_on=excluded.read_on, topics=excluded.topics",
                 (state, date, chamber, doc_id, None, today, n))


def bill_index(conn, state):
    """{folded bill name: bill_key} for matching a division's heading."""
    out = {}
    for key, title, introduced in conn.execute(
            "SELECT bill_key, title, introduced FROM aus_bills WHERE state=? AND kind != 'motion' "
            "ORDER BY COALESCE(introduced, '')", (state,)).fetchall():
        name = bill_name(title)
        if name:
            out[name] = key
    return out


def store_vote_division(conn, tax, state, date, chamber, n, d, url, today, bills=None):
    """Store one division parsed from an official record; returns 1 when it
    is on our ground. The key is '<state>:<date>:<house>:<n>', n the
    division's place in that day's record."""
    ch = CHAMBER_CODE.get(chamber, slug(chamber))
    dkey = "{0}:{1}:{2}:{3}".format(state, date, ch, n)
    bills = bill_index(conn, state) if bills is None else bills
    hit = bills.get(bill_name(d.get("heading"))) if d.get("heading") else None
    keys = [hit] if hit else []
    bill_areas = set()
    for key in keys:
        r = conn.execute("SELECT areas FROM aus_bills WHERE bill_key=?", (key,)).fetchone()
        bill_areas |= set(json.loads(r[0] or "[]")) if r and r[0] else set()
    own, terms, _tier = classify(tax, None, "" if keys else (d.get("heading") or ""),
                                 d.get("question") or "")
    areas = sorted(set(own or []) | bill_areas) if own is not None else None
    heading = d.get("heading")
    if hit:
        heading = conn.execute("SELECT title FROM aus_bills WHERE bill_key=?", (hit,)).fetchone()[0]
    conn.execute(
        "INSERT INTO aus_divisions (division_key, state, chamber, date, topic_uid, heading, stage, "
        "bill_keys, question, result, ayes, noes, pairs, url, areas, own_areas, matched_terms, "
        "fragment_read, first_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET heading=excluded.heading, bill_keys=excluded.bill_keys, "
        "question=excluded.question, result=excluded.result, ayes=excluded.ayes, noes=excluded.noes, "
        "pairs=excluded.pairs, url=excluded.url, areas=excluded.areas, own_areas=excluded.own_areas, "
        "matched_terms=excluded.matched_terms, fragment_read=excluded.fragment_read",
        (dkey, state, chamber, date, None, heading, None, aus.dumps(keys), d.get("question"),
         d.get("result"), d.get("ayes"), d.get("noes"), d.get("pairs") or 0, url, _areas_sql(areas),
         _areas_sql(own), aus.dumps(terms), today, today))
    conn.execute("DELETE FROM aus_votes WHERE division_key=?", (dkey,))
    for name, vote, teller in d.get("votes") or []:
        mkey = "{0}:name:{1}".format(state, votes.name_key(name))
        conn.execute("INSERT OR IGNORE INTO aus_votes (division_key, member_key, vote, teller) "
                     "VALUES (?,?,?,?)", (dkey, mkey, vote, 1 if teller else 0))
        conn.execute(
            "INSERT INTO aus_members (member_key, state, name, electorate, chamber, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET "
            "chamber=excluded.chamber, first_seen=MIN(aus_members.first_seen, excluded.first_seen), "
            "last_seen=MAX(aus_members.last_seen, excluded.last_seen)",
            (mkey, state, name, None, chamber, date, date))
    q = d.get("question") or ""
    if keys and READING.search(q) and votes.outcome_from_result(d.get("result")) == "negatived":
        defeat_bills(conn, dkey, READING.search(q).group(1))
    return 1 if on_our_ground(areas) else 0


def _store_record(conn, tax, state, date, chamber, divisions, url, today, doc_id):
    bills = bill_index(conn, state)
    ours = sum(store_vote_division(conn, tax, state, date, chamber, n, d, url, today, bills)
               for n, d in enumerate(divisions, 1))
    _mark_day(conn, state, date, chamber, doc_id, today, len(divisions))
    conn.commit()
    return ours


def _votes_read(conn, source, today, n, gaps):
    _read(conn, source, today, n, "ok" if not gaps else ("gaps" if n else "failed: see gaps"))
    conn.commit()


# Victoria

def parse_vic_papers(data, since):
    """[(date, chamber, paper_id, docx url, title)] of the Votes and
    Proceedings and Minutes in one listing page, dated on or after `since`;
    and whether the page reached back past `since`."""
    out, older = [], False
    for h in ((data or {}).get("result") or {}).get("hits") or []:
        title, cat = h.get("title") or "", h.get("category") or ""
        date = votes.iso_dmy_words(h.get("meta"))
        if not date:
            continue
        if date < since:
            older = True
            continue
        chamber = next((c for k, c in VIC_PAPER_KINDS if title.startswith(k) and c == cat), None)
        if not chamber:
            continue
        doc = next((b.get("href") for b in h.get("buttons") or [] if b.get("suffix") == "doc"), None)
        if not doc:
            continue
        m = re.search(r"house-paper-(\d+)", doc)
        out.append((date, chamber, "paper-" + (m.group(1) if m else slug(doc)),
                    VIC_PARL + doc if doc.startswith("/") else doc, title))
    return out, older


def pull_vic_votes(conn, client, today, tax, budget):
    """(records read, divisions, on our ground, gaps)."""
    since, done = _window_start(today), _days_read(conn, "vic")
    todo, gaps = [], 0
    for page in range(1, MAX_LIST_PAGES + 1):
        try:
            data = client.get_json(VIC_PAPERS.format(page=page), FEED, "vic-papers-{0}".format(page))
        except FetchError as e:
            _gap(conn, today, "Victoria Votes and Proceedings listing: {0}".format(_cause(e)))
            gaps += 1
            break
        got, older = parse_vic_papers(data, since)
        todo += [g for g in got if (g[0], g[1]) not in done]
        if older or not got and not ((data or {}).get("result") or {}).get("hits"):
            break
    read = ndiv = ours = 0
    for date, chamber, pid, url, title in sorted(todo, reverse=True)[:VIC_VOTES_PER_RUN]:
        if budget.exhausted():
            _gap(conn, today, "Victoria: time budget reached with {0} record(s) unread (read next "
                              "run)".format(len(todo) - read))
            gaps += 1
            break
        try:
            raw = client.get_bytes(url, FEED, "vic-" + pid, archive=False)
            divs = votes.parse_vic(votes.docx_paragraphs(raw))
        except FetchError as e:
            _gap(conn, today, "Victoria {0} {1}: {2}".format(chamber, date, _cause(e)))
            gaps += 1
            continue
        except Exception as e:  # a damaged Word file
            _gap(conn, today, "Victoria {0} {1}: unreadable ({2})".format(chamber, date, str(e)[:80]))
            gaps += 1
            continue
        ours += _store_record(conn, tax, "vic", date, chamber, divs, url, today, pid)
        read += 1
        ndiv += len(divs)
    if len(todo) > VIC_VOTES_PER_RUN:
        print("  vic-votes: {0} record(s) wait for the next run".format(len(todo) - VIC_VOTES_PER_RUN))
    _votes_read(conn, "vic-votes", today, read, gaps)
    return read, ndiv, ours, gaps


# South Australia

def _sa_library(client, ctrl, folder, slug_):
    body = json.dumps({"controlId": ctrl, "folderRelativeUrl": folder, "pageInfo": "",
                       "pageSize": "100", "sortFolders": "asc", "sortFiles": "desc"})
    return client.post_json(SA_DOCLIB, body, FEED, slug_)


def sa_latest_folder(listing, word):
    """The folder with the highest number after `word` ('Parliament 56
    (2026-)', 'Session 1 (2026-)'), else None."""
    best = None
    for f in (listing or {}).get("folders") or []:
        m = re.search(word + r"\s*0*(\d+)", f.get("folderName") or "")
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), f.get("serverRelativeUrl"))
    return best[1] if best else None


def sa_files(listing, since):
    """[(date, file id, file name)] of a session folder's PDFs on or after `since`."""
    out = []
    for f in (listing or {}).get("files") or []:
        date = votes.iso_dmy_words(f.get("fileName"))
        if date and date >= since and (f.get("fileExtension") or "").lower() == ".pdf" and f.get("id"):
            out.append((date, f["id"], f.get("fileName")))
    return sorted(out, reverse=True)


def pull_sa_votes(conn, client, today, tax, budget):
    from src.prov_fetch import pdf_text
    since, done = _window_start(today), _days_read(conn, "sa")
    read = ndiv = ours = gaps = 0
    for ctrl, chamber in SA_LIBRARIES:
        try:
            root = _sa_library(client, ctrl, "", "sa-lib-{0}".format(ctrl))
            folder = sa_latest_folder(root, "Parliament")
            listing = _sa_library(client, ctrl, folder, "sa-lib-{0}-p".format(ctrl)) if folder else None
            session = sa_latest_folder(listing, "Session")
            if session:
                listing = _sa_library(client, ctrl, session, "sa-lib-{0}-s".format(ctrl))
        except FetchError as e:
            _gap(conn, today, "South Australia {0} records (document library): {1}".format(
                chamber, _cause(e)))
            gaps += 1
            continue
        files = [f for f in sa_files(listing, since) if (f[0], chamber) not in done]
        for date, fid, name in files[:SA_VOTES_PER_RUN]:
            if budget.exhausted():
                _gap(conn, today, "South Australia {0}: time budget reached (read next run)".format(chamber))
                gaps += 1
                break
            try:
                link = client.get_json(SA_DOCLINK.format(ctrl=ctrl, id=fid), FEED, "sa-link-" + fid)
                url = (link or {}).get("downloadLink")
                if not url:
                    raise ValueError("no download link")
                divs = votes.parse_sa(pdf_text(client.get_bytes(url, FEED, "sa-" + fid, archive=False)))
            except FetchError as e:
                _gap(conn, today, "South Australia {0} {1}: {2}".format(chamber, date, _cause(e)))
                gaps += 1
                continue
            except Exception as e:  # an unreadable PDF
                _gap(conn, today, "South Australia {0} {1}: unreadable ({2})".format(
                    chamber, date, str(e)[:80]))
                gaps += 1
                continue
            # The stored link is the library's page, not the short-lived file link.
            page = ("https://www.parliament.sa.gov.au/en/House-of-Assembly/Votes-and-Proceedings"
                    if ctrl == "7" else
                    "https://www.parliament.sa.gov.au/en/Legislative-Council/Minutes-of-the-Proceedings")
            ours += _store_record(conn, tax, "sa", date, chamber, divs, page, today, fid)
            read += 1
            ndiv += len(divs)
    _votes_read(conn, "sa-votes", today, read, gaps)
    return read, ndiv, ours, gaps


# Tasmania

TAS_PHRASE = re.compile(r"IW_FIELD_ADVANCE_PHRASE=((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|"
                        r"Sunday)(?: |%20|\+)\d{1,2}(?: |%20|\+)[A-Za-z]+(?: |%20|\+)\d{4})")


def parse_tas_sittings(text):
    """{iso date: 'Thursday 10 September 2026'} from a year's sitting days."""
    out = {}
    for m in TAS_PHRASE.findall(text or ""):
        phrase = urllib.parse.unquote_plus(m)
        date = votes.iso_dmy_words(phrase)
        if date:
            out[date] = phrase
    return out


def parse_tas_results(text, phrase):
    """{'HA' | 'LC': docx URL} for the day's Hansard of each House."""
    out = {}
    for href in re.findall(r'href="([^"]+?\.docx)"', text or ""):
        href = html.unescape(href)
        name = urllib.parse.unquote(href.rsplit("/", 1)[-1])[:-5]
        for code, _c in TAS_HOUSES:
            if name == "{0} {1}".format(code, phrase) and code not in out:
                out[code] = urllib.parse.urljoin(TAS_SEARCH_BASE + "/", href)
    return out


def pull_tas_votes(conn, client, today, tax, budget):
    since, done = _window_start(today, TAS_WINDOW_DAYS), _days_read(conn, "tas")
    give_up = _window_start(today, TAS_GIVE_UP_DAYS)
    days, gaps = {}, 0
    for year in sorted({int(since[:4]), int(today[:4])}):
        try:
            days.update(parse_tas_sittings(client.get_text(TAS_SITTINGS.format(year=year), FEED,
                                                           "tas-sittings-{0}".format(year))))
        except FetchError as e:
            _gap(conn, today, "Tasmania sitting days {0}: {1}".format(year, _cause(e)))
            gaps += 1
    read = ndiv = ours = 0
    for date in sorted((d for d in days if since <= d < today), reverse=True):
        want = [(code, ch) for code, ch in TAS_HOUSES if (date, ch) not in done]
        if not want:
            continue
        if read >= TAS_VOTES_PER_RUN or budget.exhausted():
            break
        phrase = days[date]
        try:
            found = parse_tas_results(client.get_text(
                TAS_SEARCH.format(phrase=urllib.parse.quote(phrase)), FEED, "tas-search-" + date), phrase)
        except FetchError as e:
            _gap(conn, today, "Tasmania Hansard search {0}: {1}".format(date, _cause(e)))
            gaps += 1
            continue
        for code, chamber in want:
            url = found.get(code)
            if not url:
                if date < give_up:   # that House did not sit, or never published the day
                    _mark_day(conn, "tas", date, chamber, None, today, 0)
                continue
            try:
                divs = votes.parse_tas(votes.docx_body(client.get_bytes(url, FEED, "tas-{0}-{1}".format(
                    code, date), archive=False)))
            except FetchError as e:
                _gap(conn, today, "Tasmania {0} {1}: {2}".format(chamber, date, _cause(e)))
                gaps += 1
                continue
            except Exception as e:
                _gap(conn, today, "Tasmania {0} {1}: unreadable ({2})".format(chamber, date, str(e)[:80]))
                gaps += 1
                continue
            # The search result's link carries a session ID; the stored link is the day's search.
            ours += _store_record(conn, tax, "tas", date, chamber, divs,
                                  TAS_SEARCH.format(phrase=urllib.parse.quote(phrase)), today,
                                  "{0} {1}".format(code, phrase))
            read += 1
            ndiv += len(divs)
        conn.commit()
    _votes_read(conn, "tas-votes", today, read, gaps)
    return read, ndiv, ours, gaps


# The ACT

def parse_act_list(text):
    """[(iso date, pdf url)] from a year's Hansard (PDF) page."""
    out = {}
    for href, ymd in re.findall(r'href="([^"]*/PDF/t[A-Za-z]?(\d{6})\.pdf)"', text or ""):
        date = "20{0}-{1}-{2}".format(ymd[:2], ymd[2:4], ymd[4:6])
        out[date] = urllib.parse.urljoin("https://www.hansard.act.gov.au/", html.unescape(href))
    return sorted(out.items(), reverse=True)


def pull_act_votes(conn, client, today, tax, budget):
    from src.prov_fetch import pdf_rows, pdf_text
    since, done = _window_start(today), _days_read(conn, "act")
    chamber, todo, gaps = "Legislative Assembly", [], 0
    for year in sorted({int(since[:4]), int(today[:4])}, reverse=True):
        try:
            todo += [(d, u) for d, u in parse_act_list(client.get_text(
                ACT_HANSARD.format(assembly=ACT_ASSEMBLY, year=year), FEED, "act-hansard-{0}".format(year)))
                if since <= d <= today and (d, chamber) not in done]
        except FetchError as e:
            if "404" not in _cause(e):   # a year the Assembly has no page for yet
                _gap(conn, today, "ACT Hansard list {0}: {1}".format(year, _cause(e)))
                gaps += 1
    read = ndiv = ours = 0
    for date, url in sorted(todo, reverse=True)[:ACT_VOTES_PER_RUN]:
        if budget.exhausted():
            _gap(conn, today, "ACT Hansard: time budget reached (read next run)")
            gaps += 1
            break
        try:
            raw = client.get_bytes(url, FEED, "act-hansard-" + date, archive=False)
            pages = pdf_text(raw).split("\n=====PAGE\n")
            sel = votes.act_vote_pages(pages)
            divs = votes.parse_act(pdf_rows(raw, pages=sel), sel) if sel else []
        except FetchError as e:
            _gap(conn, today, "ACT Hansard {0}: {1}".format(date, _cause(e)))
            gaps += 1
            continue
        except Exception as e:
            _gap(conn, today, "ACT Hansard {0}: unreadable ({1})".format(date, str(e)[:80]))
            gaps += 1
            continue
        ours += _store_record(conn, tax, "act", date, chamber, divs, url, today, url.rsplit("/", 1)[-1])
        read += 1
        ndiv += len(divs)
    _votes_read(conn, "act-votes", today, read, gaps)
    return read, ndiv, ours, gaps


VOTES_PULL = {"vic-votes": pull_vic_votes, "sa-votes": pull_sa_votes, "tas-votes": pull_tas_votes,
              "act-votes": pull_act_votes}


# --- reclassify ------------------------------------------------------------------------

def reclassify(conn, tax, watch_path=None):
    """Re-derive every stored row's areas, offline. Returns rows touched."""
    n = 0
    for key, title in conn.execute("SELECT bill_key, title FROM aus_bills").fetchall():
        areas, terms, tier = classify(tax, key, title, watch_path=watch_path)
        conn.execute("UPDATE aus_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (_areas_sql(areas), aus.dumps(terms), tier, key))
        n += 1
    for key, title in conn.execute("SELECT act_key, title FROM aus_acts").fetchall():
        areas, terms, tier = classify(tax, key, title, watch_path=watch_path)
        conn.execute("UPDATE aus_acts SET areas=?, matched_terms=?, tier=? WHERE act_key=?",
                     (_areas_sql(areas), aus.dumps(terms), tier, key))
        n += 1
    for dkey, heading, question, bill_keys in conn.execute(
            "SELECT division_key, heading, question, bill_keys FROM aus_divisions").fetchall():
        keys = json.loads(bill_keys or "[]")
        own, terms, _t = classify(tax, None, "" if keys else heading, question or "")
        bill_areas = set()
        for k in keys:
            r = conn.execute("SELECT areas FROM aus_bills WHERE bill_key=?", (k,)).fetchone()
            bill_areas |= set(json.loads(r[0])) if r and r[0] else set()
        areas = None if own is None else sorted(set(own) | bill_areas)
        conn.execute("UPDATE aus_divisions SET areas=?, own_areas=?, matched_terms=? "
                     "WHERE division_key=?", (_areas_sql(areas), _areas_sql(own), aus.dumps(terms), dkey))
        n += 1
    conn.commit()
    print("au-states: {0} row(s) reclassified".format(n))
    return n


def summary(conn):
    c = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    print("au-states store: {0} bill(s) and motion(s), {1} Act(s), {2} division(s), "
          "{3} member(s)".format(c("SELECT COUNT(*) FROM aus_bills"), c("SELECT COUNT(*) FROM aus_acts"),
                                 c("SELECT COUNT(*) FROM aus_divisions"),
                                 c("SELECT COUNT(*) FROM aus_members")))


def make_client(raw_dir=None):
    client = HttpClient(raw_dir=raw_dir or os.path.join(ROOT, "data", "raw"), throttle=1.0)
    for host, s in HOST_THROTTLE.items():
        client.set_host_throttle(host, s)
    # robots.txt is asked on THIS run, per host, before any request; no
    # exemptions (none of these is a documented API).
    return GuardedClient(client, FEED)


def run(conn, client, today, tax, budget, wanted, nsw_years_=None):
    """Read each wanted source; returns the gap count."""
    gaps = 0
    for src in wanted:
        if budget.exhausted():
            print(budget.disclose("source(s)", wanted.index(src)))
            _gap(conn, today, "time budget reached before {0}".format(src))
            return gaps + 1
        try:
            if src == "nsw":
                r, t, d, o, g = pull_nsw(conn, client, today, tax, budget, nsw_years_)
                print("au-states nsw: {0} House sitting day(s) read, {1} bill(s) touched, {2} "
                      "division(s), {3} on our ground, {4} gap(s)".format(r, t, d, o, g))
            elif src == "vic":
                n, o, g = pull_vic(conn, client, today, tax)
                print("au-states vic: {0} bill(s), {1} on our ground, {2} gap(s)".format(n, o, g))
            elif src == "qld":
                b, a, s, o, g = pull_qld(conn, client, today, tax)
                print("au-states qld: {0} bill(s), {1} Act(s), {2} bill(s) settled by an Act, {3} on "
                      "our ground, {4} gap(s)".format(b, a, s, o, g))
            elif src == "sa":
                n, m, o, g = pull_sa(conn, client, today, tax)
                print("au-states sa: {0} bill(s) and motion(s), {1} member(s), {2} on our ground, "
                      "{3} gap(s)".format(n, m, o, g))
            elif src == "wa":
                n, o, g = pull_acts_feed(conn, client, today, tax, "wa", WA_ASPASSED, parse_wa, "wa-acts")
                print("au-states wa: {0} Act(s) as passed, {1} on our ground, {2} gap(s)".format(n, o, g))
            elif src == "tas":
                b, a, s, o, g = pull_tas(conn, client, today, tax)
                print("au-states tas: {0} bill title(s), {1} Act(s), {2} settled, {3} on our ground, "
                      "{4} gap(s)".format(b, a, s, o, g))
            elif src == "act":
                a, b, o, g = pull_act(conn, client, today, tax)
                print("au-states act: {0} Act(s), {1} bill(s) this week, {2} on our ground, {3} "
                      "gap(s)".format(a, b, o, g))
            elif src == "nt":
                n, o, g = pull_nt(conn, client, today, tax)
                print("au-states nt: {0} bill(s), {1} on our ground, {2} gap(s)".format(n, o, g))
            elif src in VOTES_PULL:
                r, d, o, g = VOTES_PULL[src](conn, client, today, tax, budget)
                print("au-states {0}: {1} record(s) read, {2} division(s), {3} on our ground, {4} "
                      "gap(s)".format(src, r, d, o, g))
        except RobotsRefused as e:
            _gap(conn, today, "{0}: {1}".format(src, e.reason))
            g = 1
        gaps += g
    return gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"),
                    help="store path (default: the shared store)")
    ap.add_argument("--sources", help="comma-separated: " + ",".join(SOURCE_ORDER + VOTES_ORDER))
    ap.add_argument("--nsw-years", help="NSW Hansard years to read (default: this year and last)")
    ap.add_argument("--taxonomy", help="a taxonomy file (default config/taxonomy.yaml)")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive every stored row's areas, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--raw-dir", help="raw archive directory (default data/raw)")
    ap.add_argument("--date", help="ISO date to stamp the run with (tests)")
    args = ap.parse_args(argv)
    tax = load_taxonomy(args.taxonomy)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    wanted = [s.strip() for s in args.sources.split(",")] if args.sources else list(DEFAULT_ORDER)
    for src in wanted:
        if src not in SOURCE_ORDER + VOTES_ORDER:
            print("au-states: unknown source {0!r}".format(src))
            return 1
    today = args.date or datetime.date.today().isoformat()
    gaps = run(conn, make_client(args.raw_dir), today, tax, drain.Budget(args.budget_seconds), wanted,
               args.nsw_years.split(",") if args.nsw_years else None)
    conn.commit()
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
