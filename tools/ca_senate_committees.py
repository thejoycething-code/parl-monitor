#!/usr/bin/env python3
"""Who said what in Senate of Canada committees, on our issues -- and which
witnesses told them.

    python3 tools/ca_senate_committees.py                       # SOCI, LCJC, RIDR (+ SECD by title), 45-1
    python3 tools/ca_senate_committees.py --committee LCJC --limit 3
    python3 tools/ca_senate_committees.py --all-committees      # + every other Senate committee, by title
    python3 tools/ca_senate_committees.py --dry-run             # read and count, store nothing
    python3 tools/ca_senate_committees.py --db /tmp/ca.db --raw-dir /tmp/raw

Built 12 October 2026 (Christopher: "Build both", Senate committee transcripts
and committee reports). The House and joint committees are
tools/ca_committees.py; this is its Senate sibling and writes the SAME tables
(ca_committee_meetings, ca_testimony, ca_speeches forum='committee') with
chamber='senate'. Scope: docs/canada-federal-sources-scope.md, section (4).

THE SOURCE. Two hops per committee and session, sencanada.ca, robots.txt
asked on every run (src/robots_guard), one request a second:
  1. the committee's Studies table, an HTML partial,
     /umbraco/surface/CommitteesAjax/GetTablePartialView?tableName=Studies&
     committeeId=<id>&selectedSession=<P-S>&isCommitteeSpecific=true&Lang=en&
     p=<page>&PageSize=250. Each study (a bill or an order of reference) lists
     its meetings: the date, the WITNESS LIST (name and role, organisation in
     <em>), and links -- the transcript /en/content/sen/committee/<PS>/<acr>/
     <NN>ev-<id>-e and the minutes <NN>mn-<id>-e, NN being the meeting number.
     A meeting held for two studies is listed under both; it is merged here
     and its study titles kept together. Pages are read until one holds no
     study (LCJC 45-1 fits on one; 43-2 needed two in the scope's probe);
  2. the transcript, one HTML page per meeting, archived as the provenance.
The committee id is not in the URL a reader sees: SOCI 1047, LCJC 1011 and
RIDR 1077 are pinned; any other is read from the committee's own page
(CommitteeId in its ajax data), one fetch, once a run.

WHO IS WHO -- THE LABELS SAY SO. The transcript prints bold labels, as the
Debates do:
  * "Senator Batters:" / "Senator K. Wells:" is a SENATOR. Committee labels
    carry the surname only, so a senator resolves by a UNIQUE surname (and
    initial, where printed) among ca_senators, or the chair's full name in
    the opening line ("Senator David M. Arnot (Chair) in the chair"). Two
    candidates resolve nothing: person_id and speaker_key stay NULL, never
    guessed, never minted from a name;
  * "The Chair:", "The Deputy Chair:", "Hon. Senators:" -- officers and
    collective labels -- are COUNTED, NOT STORED, as on the floor;
  * "Vincent Labrosse, Clerk of the Committee:" and "..., analyst, Library of
    Parliament:" are officers of the committee: counted, not stored, and so
    are their later short labels ("Mr. Labrosse:");
  * EVERYTHING ELSE IS A WITNESS -- a professor, an official, a minister
    appearing before the committee ("Hon. X, P.C., M.P., Minister of ...").
    A witness NEVER gets a person_id and NEVER enters ca_speeches; their
    words on our ground go to ca_testimony with the name, the role and the
    organisation AS PRINTED, nothing more. The first labelled intervention
    is the full one ("Sheila Wildeman, Professor, Schulich School of Law,
    Dalhousie University:"), later ones short ("Ms. Wildeman:"), resolved to
    it by surname within the transcript. The organisation is the Studies
    table's <em> for that witness where the names match, else the label's
    last part (tools/ca_committees.organisation).

WHAT IS STORED. Senators' and witnesses' interventions ON OUR GROUND only,
matched per passage exactly as tools/ca_committees.py matches the House's:
the English taxonomy plus config/watchlist-ca.yaml, the meeting's study
titles as the title passage (a bill study's title carries the bill's long
title). Ids are 'scmte-<PS>-<ACR>-<NN>-<seq>', seq the intervention's place
in the transcript, chair included, so it is stable and never collides with a
House 'cmte-' id. Every meeting READ gets a ca_committee_meetings row with
chamber='senate' and its totals, whatever it held:
  * status 'read'        -- transcript parsed; never fetched again;
  * status 'no_evidence' -- listed, no transcript linked (in camera, or not
    yet published): re-checked from the table every run, costs nothing. The
    Senate's table prints no in-camera lock, so the two are not told apart.
A meeting with neither a transcript nor minutes link has no number and is
counted, not stored.

JOINT COMMITTEES (AMAD, BCAN, BILI, REGS) are left to tools/ca_committees.py,
which reads their evidence from parl.ca: reading them here too would store
every senator's words twice.

GAPS are recorded (db.record_gaps), never fatal: a Studies table that will not
load, a transcript that will not load or parses to nothing. A gapped meeting
gets no row and is retried next run; MAX_FAILING in a row stops the run (a
host that is down). --limit counts transcripts ATTEMPTED. THE FIRST RUN IS
THE BASELINE: it reads the session from its first meeting, up to the limit
and the clock, and the weeks after drain the rest.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import guard  # noqa: E402


def _load(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cm = _load("ca_committees")        # the House collector: matching, organisation, title gate
sd = _load("ca_senate_debates")    # the Debates parser: labels, tokens, name folding
han = cm.han

FEED = "ca-senate-committees"
CURRENT_SESSION = cm.CURRENT_SESSION
BASE = "https://sencanada.ca"
STUDIES = (BASE + "/umbraco/surface/CommitteesAjax/GetTablePartialView?tableName=Studies"
           "&committeeId={0}&selectedSession={1}&isCommitteeSpecific=true&Lang=en&p={2}"
           "&PageSize=250")
COMMITTEE_PAGE = BASE + "/en/committees/{0}/{1}"
LIST = BASE + "/umbraco/surface/CommitteesAjax/GetCommitteeListPartialView?Lang=en"
# On our ground (Christopher, 12 October 2026): Social Affairs, Legal and
# Constitutional Affairs, Human Rights -- every meeting with a transcript.
KEY_COMMITTEES = ("SOCI", "LCJC", "RIDR")
# The Senate's match for a House key committee (SECU, public safety): read
# by study title, as the House's non-key committees are.
GATED = ("SECD",)
COMMITTEE_IDS = {"SOCI": 1047, "LCJC": 1011, "RIDR": 1077}
JOINT = frozenset(("AMAD", "BCAN", "BILI", "REGS"))
DEFAULT_LIMIT = 40          # transcripts fetched per run
MAX_FAILING = 5
MAX_PAGES = 10              # Studies pages per committee and session

STUDY_ITEM = re.compile(r'<div class="cmt-site_v2-studybills-table-study-item[\s"]')
STUDY_NAME = re.compile(r'study-item-name[^>]*>(.*?)</h3>', re.S)
ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
NOTICE = re.compile(r'href="/en/committees/[A-Za-z]{4}/noticeofmeeting/(\d+)/[^"]*">\s*'
                    r'([A-Z][a-z]{2,4})\.?\s+(\d{1,2}),\s+(\d{4})', re.S)
DOC_LINK = re.compile(r'href="(/en/content/sen/committee/(\d{2,3})/([a-z]{4})/(\d+)(ev|mn)-(\d+)-e)"',
                      re.I)
WITNESS_LI = re.compile(r"<li>\s*([^<]+?)\s*(?:<em[^>]*>([^<]*)</em>)?\s*</li>", re.S)
COMMITTEE_ID = re.compile(r"CommitteeId&quot;:(\d+)", re.I)
LIST_LINK = re.compile(r'href="/en/committees/([a-z]{4})/\d{2}-\d"', re.I)
DOC_START = re.compile(r'id="content-viewer-document"', re.I)
EVIDENCE_HEAD = re.compile(r"<b>\s*EVIDENCE\s*</b>", re.I)
DATELINE = re.compile(r"^[A-Z][A-Za-z .'\-]+, (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|"
                      r"Sunday), ([A-Z][a-z]+) (\d{1,2}), (\d{4})$")
MET_AT = re.compile(r"this day at (\d{1,2})(?::(\d{2}))?\s*([ap])\.m\.", re.I)
IN_THE_CHAIR = re.compile(r"^\(?\s*(?:Deputy |Acting )?Chair\s*\)?\s*,?\s*in the chair", re.I)
OFFICER = re.compile(r"Clerk of the Committee|Committee Clerk|Library of Parliament|"
                     r"Legislative Clerk|Procedural Clerk", re.I)
MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def studies_url(cid, session, page=1):
    return STUDIES.format(cid, session, page)


def _date(month, day, year):
    m = MONTHS.get((month or "")[:3].lower())
    if not m:
        return None
    try:
        return datetime.date(int(year), m, int(day)).isoformat()
    except ValueError:
        return None


def parse_studies(text, acr, parl, sess):
    """{number: meeting dict} from one page of a committee's Studies table.

    A meeting is identified by the number in its transcript or minutes link;
    one with neither is counted under None (it cannot be keyed). A meeting
    listed under two studies is merged: both titles, one witness list."""
    out, unkeyed = {}, 0
    starts = [m.start() for m in STUDY_ITEM.finditer(text or "")]
    for i, s in enumerate(starts):
        chunk = text[s: starts[i + 1] if i + 1 < len(starts) else len(text)]
        name = STUDY_NAME.search(chunk)
        study = sd._clean(name.group(1)) if name else None
        if study:
            # 'Bill C-25 , An Act ...' -- the link leaves a space before the comma.
            study = re.sub(r"\s+,", ",", study)
        for row in ROW.findall(chunk):
            notice = NOTICE.search(row)
            if not notice:
                continue                # a header row
            number, transcript = None, None
            for path, ps, _, nn, kind, _ in DOC_LINK.findall(row):
                if ps != "{0}{1}".format(parl, sess):
                    continue
                number = int(nn)
                if kind.lower() == "ev":
                    transcript = BASE + path
            if number is None:
                unkeyed += 1
                continue
            witnesses = []
            cell = row.split('studies-render-witness', 1)[1] if 'studies-render-witness' in row else ""
            cell = cell.split("</td>", 1)[0]
            for who, org in WITNESS_LI.findall(cell):
                who = " ".join(htmlmod.unescape(who).split())
                name_part, _, role_part = who.partition(",")
                witnesses.append({"name": name_part.strip(), "role": role_part.strip() or None,
                                  "organisation": " ".join(htmlmod.unescape(org or "").split()) or None})
            m = out.get(number)
            if m is None:
                m = out[number] = {
                    "committee": acr, "parliament": parl, "session": sess, "number": number,
                    "date": _date(notice.group(2), notice.group(3), notice.group(4)),
                    "site_id": notice.group(1), "studies": [], "witnesses": [],
                    "in_camera": False, "evidence_url": None,
                    "key": cm.meeting_key(parl, sess, acr, number)}
            if study and study not in m["studies"]:
                m["studies"].append(study)
            if transcript and not m["evidence_url"]:
                m["evidence_url"] = transcript
            for w in witnesses:
                if w not in m["witnesses"]:
                    m["witnesses"].append(w)
    return out, unkeyed, len(starts)


def speech_id(parl, sess, acr, number, seq):
    """'scmte-451-LCJC-52-14': never a House 'cmte-' id or a floor 'sen-' one."""
    return "scmte-{0}{1}-{2}-{3}-{4}".format(parl, sess, acr, number, seq)


def parse_transcript(page):
    """(problem, info, [intervention dicts]). problem is None for a readable
    transcript, else why it is a gap. info: {date, chair, time}."""
    page = page or ""
    title = re.search(r"<title[^>]*>(.*?)</title\s*>", page, re.S | re.I)
    if not title or not sd._clean(title.group(1)):
        return "empty <title> (a soft-404?)", {}, []
    start = DOC_START.search(page)
    if not start or not EVIDENCE_HEAD.search(page, start.end()):
        return "no EVIDENCE heading (markup changed?)", {}, []
    end = sd.CONTENT_END.search(page, start.end())
    region = page[start.end(): end.start() if end else len(page)]
    info = {"date": None, "chair": None, "time": None}
    ivs, cur = [], None
    for m in sd.TOKEN.finditer(region):
        body = m.group(2)
        text = sd._clean(body)
        if not text or sd.NOT_TEXT.match(text):
            continue
        tm = sd.TIME_MARK.match(text)
        if tm:
            info["time"] = "{0}:{1}".format(tm.group(1), tm.group(2))
            continue
        if not ivs:
            dl = DATELINE.match(text)
            if dl and not info["date"]:
                info["date"] = _date(dl.group(1), dl.group(2), dl.group(3))
                continue
            met = MET_AT.search(text)
            if met and not info["time"]:
                hour = int(met.group(1)) % 12 + (12 if met.group(3).lower() == "p" else 0)
                info["time"] = "{0:02d}:{1}".format(hour, met.group(2) or "00")
        lab = sd.split_label(body)
        if lab and not lab[2]:
            # No colon: the opening "Senator X (Chair) in the chair", or bold
            # in running text. Neither is an intervention.
            label, rest, _ = lab
            if IN_THE_CHAIR.match(sd._clean(rest)):
                info["chair"] = re.sub(r"^Senator\s+", "", label).strip() or None
                continue
            lab = None
        if lab:
            label, rest, _ = lab
            rest_text = sd._clean(rest)
            cur = {"seq": len(ivs) + 1, "label": label, "time": info["time"],
                   "paras": [rest_text] if rest_text else []}
            ivs.append(cur)
            continue
        if cur is not None:
            cur["paras"].append(text)
    for iv in ivs:
        iv["text"] = "\n".join(iv.pop("paras"))
    if not ivs:
        return "no interventions parsed (markup changed?)", info, []
    return None, info, ivs


MINISTER = re.compile(r"\bM\.P\.|\bMinister\b|\bSecretary\b")


def label_kind(label):
    """'chair' (officers and collective labels), 'senator', or 'other'.

    A senator is 'Senator Batters', or 'Hon. Julie Miville-Dechêne, sponsor
    of the bill' (a senator appearing on her own bill, LCJC 45-1/4); an
    'Hon.' who is an M.P. or a minister appears as a witness."""
    if label.startswith("The ") or sd.COLLECTIVE.match(label):
        return "chair"
    if sd.SENATOR_LABEL.match(label.split(",")[0]):
        return "senator"
    if label.startswith("Hon.") and not MINISTER.search(label):
        return "senator"
    return "other"


def _surname(name):
    toks = sd.namefold(han.HONORIFICS.sub("", name or "")).split()
    return toks[-1] if toks else None


class SenatorSurnames:
    """ca_senators by folded surname ('Martin, Yonah' -> 'martin'). Committee
    labels carry the surname only, so only a UNIQUE surname (narrowed by the
    printed initial) resolves. ca_senators is built from recorded votes
    (tools/ca_senate.py, from 42-1), so a senator appointed since the last
    vote read is unknown until they vote, and stays NULL here."""

    def __init__(self, conn):
        self.by = {}
        self.full = sd.Senators(conn)       # 'Hon. First Last' labels, as on the floor
        for pid, name in conn.execute("SELECT person_id, name FROM ca_senators"):
            last, _, first = (name or "").partition(",")
            if not last.strip():
                continue
            full = " ".join((first.strip() + " " + last.strip()).split())
            self.by.setdefault(sd.namefold(last), []).append((sd.namefold(first), pid, full))

    def resolve(self, surname, initial=None, chair=None):
        """(person_id, speaker_key) or (None, None)."""
        key = sd.namefold(surname)
        cands = self.by.get(key, [])
        if initial:
            cands = [c for c in cands if c[0].startswith(initial.lower())]
        if len(cands) > 1 and chair and sd.namefold(chair).endswith(key):
            # The opening line names the chair in full: 'David M. Arnot'.
            given = sd.namefold(chair).split()[0]
            cands = [c for c in cands if c[0].split() and c[0].split()[0] == given]
        if len(cands) == 1:
            return cands[0][1], sd.namefold(cands[0][2])
        return None, None


def attribute(ivs, senators, chair=None, listed=()):
    """Set kind, person_id, speaker_key, witness, affiliation and organisation
    on every intervention, in place. Pass 1 learns each full label: a
    senator's 'Hon. First Last' and a witness's 'Name, role, organisation';
    pass 2 resolves the short ones ('Senator Last', 'Ms. Last') by surname
    within the transcript first."""
    full = {}                       # surname -> (name, affiliation, officer)
    hon = {}                        # surname -> {(person_id, speaker_key)}
    for iv in ivs:
        iv["kind"] = label_kind(iv["label"])
        if iv["kind"] == "senator" and iv["label"].startswith("Hon."):
            name = sd.hon_name(iv["label"])
            if name:
                pid = senators.full.resolve(name)
                iv["hon"] = (pid, sd.namefold(name)) if pid else (None, None)
                toks = sd.namefold(name).split()
                for k in range(1, len(toks)):
                    hon.setdefault(" ".join(toks[k:]), set()).add(iv["hon"])
            continue
        if iv["kind"] != "other" or "," not in iv["label"]:
            continue
        name, _, affiliation = iv["label"].partition(",")
        name = han.HONORIFICS.sub("", name).strip()
        affiliation = affiliation.strip() or None
        sn = _surname(name)
        if sn and sn not in full:
            full[sn] = (name, affiliation, bool(OFFICER.search(affiliation or "")))
    table = {}
    for w in listed or ():
        sn = _surname(w.get("name"))
        if sn:
            table.setdefault(sn, []).append(w)
    for iv in ivs:
        iv["person_id"] = iv["speaker_key"] = None
        iv["witness"] = iv["affiliation"] = iv["organisation"] = None
        if iv["kind"] == "senator":
            if "hon" in iv:
                iv["person_id"], iv["speaker_key"] = iv.pop("hon")
                continue
            hit = sd.SENATOR_LABEL.match(iv["label"].split(",")[0])
            if not hit:
                continue
            seen = hon.get(sd.namefold(hit.group("surname")))
            if seen and len(seen) == 1 and not hit.group("initial") and next(iter(seen))[0]:
                iv["person_id"], iv["speaker_key"] = next(iter(seen))
                continue
            iv["person_id"], iv["speaker_key"] = senators.resolve(
                hit.group("surname"), hit.group("initial"), chair)
            continue
        if iv["kind"] != "other":
            continue
        head = iv["label"].split(",")[0]
        sn = _surname(head)
        learned = full.get(sn)
        if learned and learned[2]:
            iv["kind"] = "chair"            # an officer of the committee
            continue
        if learned:
            iv["witness"], iv["affiliation"] = learned[0], learned[1]
        else:
            iv["witness"] = han.HONORIFICS.sub("", head).strip() or None
        rows = table.get(sn) or []
        if len(rows) == 1 and rows[0].get("organisation"):
            iv["organisation"] = rows[0]["organisation"]
        else:
            iv["organisation"] = cm.organisation(iv["affiliation"])
        iv["kind"] = "witness"
    return ivs


def store_meeting(conn, m, info, ivs, tax, wl, today, senators=None, write=True):
    """Store one meeting's interventions on our ground and its totals row."""
    senators = senators or SenatorSurnames(conn)
    parl, sess, acr, number = m["parliament"], m["session"], m["committee"], m["number"]
    key = m["key"]
    date = info.get("date") or m["date"]
    title = cm.title_passage(m["studies"])
    bill = cm.bill_of(m["studies"])
    attribute(ivs, senators, info.get("chair"), m.get("witnesses"))
    t = {"interventions": len(ivs), "chair": 0, "members": 0, "witnesses": 0,
         "speeches": 0, "testimony": 0, "unresolved": 0, "chars": 0}
    for iv in ivs:
        t["chars"] += len(iv["text"] or "")
        if iv["kind"] == "chair":
            t["chair"] += 1
            continue
        t["members" if iv["kind"] == "senator" else "witnesses"] += 1
        areas, terms, excerpt = filt.aggregate_passages(
            filt.match_passages(tax, wl, iv["text"] or "", title=title))
        if not han.on_our_ground(areas):
            continue
        sid = speech_id(parl, sess, acr, number, iv["seq"])
        if iv["kind"] == "witness":
            # NEVER a person_id, NEVER ca_speeches: a witness is testimony.
            t["testimony"] += 1
            if write:
                conn.execute(
                    "INSERT INTO ca_testimony (testimony_id, intervention_id, meeting_key, "
                    "committee, date, time, subject, db_id, label, witness, affiliation, "
                    "organisation, text, excerpt, areas, matched_terms, first_seen, chamber) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(testimony_id) DO UPDATE SET text=excluded.text, "
                    "areas=excluded.areas, matched_terms=excluded.matched_terms, "
                    "excerpt=excluded.excerpt",
                    (sid, str(iv["seq"]), key, acr, date, iv["time"], title, None, iv["label"],
                     iv["witness"], iv["affiliation"], iv["organisation"], iv["text"], excerpt,
                     json.dumps(areas), json.dumps(terms), today, "senate"))
            continue
        t["speeches"] += 1
        t["unresolved"] += iv["person_id"] is None
        if write:
            conn.execute(
                "INSERT INTO ca_speeches (speech_id, sitting_key, date, time, rubric, subject, "
                "bill_number, kind, db_id, person_id, speaker, party, text, areas, matched_terms, "
                "excerpt, first_seen, chamber, forum, committee, speaker_key) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(speech_id) DO UPDATE SET text=excluded.text, "
                "person_id=COALESCE(excluded.person_id, ca_speeches.person_id), "
                "speaker_key=COALESCE(excluded.speaker_key, ca_speeches.speaker_key), "
                "areas=excluded.areas, matched_terms=excluded.matched_terms, "
                "excerpt=excluded.excerpt",
                (sid, key, date, iv["time"], "Committee evidence", title, bill, None, None,
                 iv["person_id"], iv["label"], None, iv["text"], json.dumps(areas),
                 json.dumps(terms), excerpt, today, "senate", "committee", acr, iv["speaker_key"]))
    if write:
        record_meeting(conn, m, "read", today, date=date, totals=t)
        conn.commit()
    return t


def record_meeting(conn, m, status, today, date=None, totals=None):
    t = totals or {}
    conn.execute(
        "INSERT OR REPLACE INTO ca_committee_meetings (meeting_key, committee, parliament, "
        "session, number, date, studies, in_camera, status, site_meeting_id, evidence_url, "
        "xml_url, interventions, chair, members, witnesses, speeches, testimony, unresolved, "
        "chars, read_on, chamber) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (m["key"], m["committee"], m["parliament"], m["session"], m["number"],
         date or m["date"], json.dumps(m["studies"], ensure_ascii=False), 0, status,
         m["site_id"], m["evidence_url"], None, t.get("interventions"), t.get("chair"),
         t.get("members"), t.get("witnesses"), t.get("speeches"), t.get("testimony"),
         t.get("unresolved"), t.get("chars"), today, "senate"))


def already_read(conn):
    return {r[0] for r in conn.execute(
        "SELECT meeting_key FROM ca_committee_meetings WHERE chamber='senate' AND status='read'")}


def committee_id(client, acr, session):
    """The Senate's numeric id for a committee: pinned, else read off its page."""
    if acr in COMMITTEE_IDS:
        return COMMITTEE_IDS[acr]
    page = client.get_text(COMMITTEE_PAGE.format(acr.lower(), session), FEED,
                           "committee-" + acr, archive=False)
    hit = COMMITTEE_ID.search(page or "")
    if not hit:
        raise ValueError("no CommitteeId on the {0} page (markup changed?)".format(acr))
    return int(hit.group(1))


def list_committees(client):
    """Every committee acronym on the Senate's committee list, joint ones out."""
    text = client.get_text(LIST, FEED, "list", archive=False)
    return sorted({a.upper() for a in LIST_LINK.findall(text or "")} - JOINT)


def read_listing(client, acr, cid, session, parl, sess):
    """{number: meeting} across every Studies page, plus meetings with no number."""
    meetings, unkeyed = {}, 0
    for page in range(1, MAX_PAGES + 1):
        text = client.get_text(studies_url(cid, session, page), FEED,
                               "studies-{0}-{1}-p{2}".format(acr, session, page), archive=False)
        got, lost, items = parse_studies(text, acr, parl, sess)
        unkeyed += lost
        for n, m in got.items():
            if n in meetings:
                for s in m["studies"]:
                    if s not in meetings[n]["studies"]:
                        meetings[n]["studies"].append(s)
                meetings[n]["evidence_url"] = meetings[n]["evidence_url"] or m["evidence_url"]
                for w in m["witnesses"]:
                    if w not in meetings[n]["witnesses"]:
                        meetings[n]["witnesses"].append(w)
            else:
                meetings[n] = m
        if not items:
            break
    return meetings, unkeyed


def read_meeting(conn, client, m, tax, wl, today, senators):
    try:
        page = client.get_text(m["evidence_url"], FEED, "transcript-" + m["key"])
    except FetchError as exc:
        return None, "{0}: transcript: {1}".format(m["key"], exc)
    problem, info, ivs = parse_transcript(page)
    if problem:
        return None, "{0}: {1} ({2})".format(m["key"], problem, m["evidence_url"])
    return store_meeting(conn, m, info, ivs, tax, wl, today, senators), None


def pull(conn, client, today, session=CURRENT_SESSION, committees=KEY_COMMITTEES,
         gated=GATED, limit=DEFAULT_LIMIT, tax=None, wl=None, log=print, budget=None):
    """Walk each committee's Studies table for one session and read every
    unread transcript (title-gated for `gated` committees). Returns a summary."""
    tax = tax if tax is not None else filt.load_taxonomy(cm.TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(cm.WATCHLIST)
    parl, sess = han.parse_session(session)
    senators = SenatorSurnames(conn)
    done = already_read(conn)
    failing = 0
    s = {"attempted": 0, "read": 0, "speeches": 0, "testimony": 0, "no_evidence": 0,
         "skipped": 0, "title_gated": 0, "listed": 0, "unkeyed": 0, "unresolved": 0,
         "stopped": None}
    gaps = []
    for acr in list(committees) + [g for g in gated if g not in committees]:
        if acr in JOINT:
            continue
        is_gated = acr not in committees
        try:
            cid = committee_id(client, acr, session)
            listing, unkeyed = read_listing(client, acr, cid, session, parl, sess)
        except (FetchError, ValueError) as exc:
            gaps.append("{0} {1}: Studies table: {2}".format(acr, session, exc))
            continue
        s["listed"] += len(listing)
        s["unkeyed"] += unkeyed
        counts = {"read": 0, "pending": 0, "gated": 0}
        for number in sorted(listing):
            m = listing[number]
            if m["key"] in done:
                s["skipped"] += 1
                continue
            if is_gated and not cm.on_our_ground_title(tax, wl, m["studies"]):
                s["title_gated"] += 1
                counts["gated"] += 1
                continue
            if not m["evidence_url"]:
                record_meeting(conn, m, "no_evidence", today)
                s["no_evidence"] += 1
                counts["pending"] += 1
                continue
            if s["stopped"]:
                continue
            if limit is not None and s["attempted"] >= limit:
                s["stopped"] = "limit"
                continue
            if failing >= MAX_FAILING:
                s["stopped"] = "failing"
                continue
            if budget is not None and budget.exhausted():
                log(budget.disclose("Senate committee meetings", s["read"]))
                s["stopped"] = "budget"
                continue
            s["attempted"] += 1
            totals, gap = read_meeting(conn, client, m, tax, wl, today, senators)
            if gap:
                gaps.append(gap)
                failing += 1
                continue
            failing = 0
            done.add(m["key"])
            s["read"] += 1
            counts["read"] += 1
            for k in ("speeches", "testimony", "unresolved"):
                s[k] += totals[k]
            log("  {0} {1}: {2} interventions ({3} senator, {4} witness, {5} chair/officer); "
                "{6} speech(es) + {7} testimony on our ground{8}".format(
                    m["key"], m["date"], totals["interventions"], totals["members"],
                    totals["witnesses"], totals["chair"], totals["speeches"], totals["testimony"],
                    ", {0} unattributed".format(totals["unresolved"]) if totals["unresolved"] else ""))
        conn.commit()
        log("  {0} {1}: {2} listed, {3} read now, {4} with no transcript{5}".format(
            acr, session, len(listing), counts["read"], counts["pending"],
            ", {0} off our ground by title".format(counts["gated"]) if is_gated else ""))
    if s["stopped"] == "limit":
        log("  transcript cap ({0}) reached; the rest are read on later runs".format(limit))
    if s["stopped"] == "failing":
        log("  {0} transcripts in a row failed: stopped, retried next run".format(MAX_FAILING))
    s["gaps"] = db.record_gaps(conn, FEED, gaps, edition=today)
    for g in gaps:
        log("  [gap] " + g[:160])
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=CURRENT_SESSION, help="P-S, e.g. 45-1")
    ap.add_argument("--committee", help="one acronym, or several comma-separated (LCJC,SOCI)")
    ap.add_argument("--all-committees", action="store_true",
                    help="also every other Senate committee, title-gated to our ground")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="read and count into an in-memory store; nothing is kept")
    args = ap.parse_args()
    client = guard(HttpClient(raw_dir=args.raw_dir, throttle=1.0), FEED)
    today = datetime.date.today().isoformat()
    conn = ca_store.ensure_schema(db.init_db(db.connect(":memory:" if args.dry_run else args.db)))
    committees = tuple(c.strip().upper() for c in args.committee.split(",")) \
        if args.committee else KEY_COMMITTEES
    gated = () if args.committee else GATED
    if args.all_committees:
        try:
            gated = tuple(c for c in list_committees(client) if c not in committees)
        except FetchError as exc:
            db.record_gaps(conn, FEED, ["committee list: {0}".format(exc)], edition=today)
            print("  [gap] committee list: {0}".format(exc))
    print("ca-senate-committees: {0}, {1} committee(s){2}, {3} senator(s) known".format(
        args.session, len(committees), " + {0} title-gated".format(len(gated)) if gated else "",
        conn.execute("SELECT COUNT(*) FROM ca_senators").fetchone()[0]))
    s = pull(conn, client, today, session=args.session, committees=committees, gated=gated,
             limit=args.limit, budget=drain.Budget(args.budget_seconds))
    print("ca-senate-committees: {0} meeting(s) read, {1} speech(es) and {2} testimony on our "
          "ground, {3} unattributed; {4} with no transcript, {5} already read{6}; {7} gap(s){8}.".format(
              s["read"], s["speeches"], s["testimony"], s["unresolved"], s["no_evidence"],
              s["skipped"], ", {0} off our ground by title".format(s["title_gated"])
              if gated else "", s["gaps"], " (dry run: nothing kept)" if args.dry_run else ""))
    if s["listed"] == 0 and not s["gaps"]:
        db.record_gaps(conn, FEED, ["{0}: every Studies table parsed to nothing".format(
            args.session)], edition=today)
        print("  [gap] every Studies table parsed to nothing -- markup changed, or no "
              "committee sat in {0}".format(args.session))
        s["gaps"] = 1
    conn.close()
    return 1 if s["gaps"] else 0


if __name__ == "__main__":
    sys.exit(main())
