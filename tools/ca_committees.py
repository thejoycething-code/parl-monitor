#!/usr/bin/env python3
"""Who said what in House of Commons (and joint) committees, on our issues --
and which witnesses told them.

    python3 tools/ca_committees.py                         # key eight, current session
    python3 tools/ca_committees.py --session 44-1 --committee AMAD --limit 3
    python3 tools/ca_committees.py --all-committees        # + title-gated others
    python3 tools/ca_committees.py --dry-run               # read and count, store nothing
    python3 tools/ca_committees.py --db /tmp/ca.db --raw-dir /tmp/raw

GROUNDWORK (2 October 2026). Nothing schedules this; the orchestrator wires
it. Scope: scratchpad canada-federal-sources-scope.md, section (4).

THE SOURCE. Three hops per committee and session, no search (robots.txt
disallows /Search/ on ourcommons.ca, so the meeting lists are the only way in):
  1. the meeting list, ourcommons.ca/Committees/en/<ACR>/Meetings?parl=P&session=S
     -- joint committees (AMAD, REGS, BILI) live on parl.ca, and the
     ourcommons URL 404s for them. One page holds the whole session: each
     meeting's date, number, study titles, an In Camera lock, and an
     Evidence link when there is a public transcript;
  2. the Evidence page, .../DocumentViewer/en/<P-S>/<ACR>/meeting-<N>/evidence,
     ~700 KB of HTML whose only use is the link to the XML (the EV id is a
     publication id, not the meeting id, so it cannot be built). Fetched
     with archive=False;
  3. the XML, /Content/Committee/<PS>/<ACR>/Evidence/EV<id>/<ACR>EV<NN>-E.XML,
     House Hansard's own schema, parsed by ca_hansard.parse_sitting unchanged.
     Archived: it is the provenance. Committee files leave the debate title
     empty, so the meeting's STUDY TITLES are passed as the title passage.

WHO IS WHO -- THE XML SAYS SO. Each <Affiliation> carries a Type (observed,
not documented, so a test pins it):
  * 28 is a WITNESS: a physician, an RCMP officer, an NGO director. A
    witness NEVER gets a person_id and NEVER enters ca_speeches; their words
    on our ground go to ca_testimony, a witness index that is never part of
    any member's record;
  * 35/36 is the Chair / Joint Chair, 26 a committee researcher, 27 the
    clerk, and any label starting "The " is an officer (Chair, Vice-Chair,
    Clerk): COUNTED, NOT STORED, as the chair is on the floor;
  * everything else is a member. An MP resolves by RIDING, then by a unique
    name, against ca_members; a senator on a joint committee ("Hon. Stan
    Kutcher (Senator, Nova Scotia, ISG)") by unique name against
    ca_senators. NULL when neither resolves uniquely -- never guessed, never
    minted from a name.
  * A committee DbId is NOT a Hansard DbId (none of seven matched
    ca_speaker_roles) and is not one per person even within a file (Mégie
    spoke as 228785 and 288386 in AMAD 10). So identity is learned PER
    DOCUMENT -- DbId and name from the labels that carry a riding or
    "Senator" -- and ca_speaker_roles is never read or written here.

WHAT IS STORED. Members' and witnesses' interventions ON OUR GROUND only
(per passage, src/filter.match_passages, the study titles counting as a
passage, exactly as ca_hansard). Speeches go to ca_speeches with
forum='committee', committee=<ACR>, chamber 'commons' or 'senate', and a
speech_id 'cmte-<PS>-<ACR>-<NN>-<intervention id>' that can never collide
with a Hansard id. Every meeting READ gets a ca_committee_meetings row with
its totals whatever it held, so "never read" differs from "quiet":
  * status 'read'       -- evidence parsed; skipped on later runs (resume);
  * status 'in_camera'  -- locked, no evidence link: NOT a gap, never fetched;
  * status 'no_evidence'-- public but no transcript linked yet (a recent
    meeting): re-checked every run from the list, costs nothing.

WHICH COMMITTEES. The key eight (JUST, HESA, FEWO, ETHI, AMAD, SECU, HUMA,
CHPC): every public meeting. With --all-committees, every other committee
on the House's committee home page, plus the human-rights subcommittee
SDIR, but only meetings whose STUDY TITLE matches the taxonomy -- the title
gate, so 26 committees' worth of Estimates and fisheries is never fetched.

GAPS are printed and recorded (db.record_gaps), never swallowed: a meeting
list that will not load, an Evidence page with no XML link, an XML that does
not parse or is for another meeting. A gapped meeting gets no row, so the
next run retries it. Meetings are independent, so one gap never stops the
run; MAX_FAILING in a row does (a host that is down), and says so. --limit
counts meetings ATTEMPTED, so a failing host cannot cost more than the cap.

ONE WRITER AT A TIME on the store. A backfill (~3,400 key-eight meetings
since 2010, ~3 GB at two fetches each) runs from CI, paced, and announced.
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
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402


def _load_hansard():
    """tools/ca_hansard.py, whose parser and member roster this reuses."""
    name = "ca_hansard"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", "ca_hansard.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


han = _load_hansard()

FEED = "ca-committees"
CURRENT_SESSION = han.CURRENT_SESSION
TAXONOMY = han.TAXONOMY
WATCHLIST = han.WATCHLIST
COMMONS = "https://www.ourcommons.ca"
PARL = "https://www.parl.ca"
MEETINGS = "{0}/Committees/en/{1}/Meetings?parl={2}&session={3}"
HOME = COMMONS + "/Committees/en/Home"
KEY_EIGHT = ("JUST", "HESA", "FEWO", "ETHI", "AMAD", "SECU", "HUMA", "CHPC")
# Joint committees are served from parl.ca; the ourcommons URL 404s.
JOINT = frozenset(("AMAD", "REGS", "BILI"))
# Subcommittees the home page does not list, read under --all-committees.
EXTRA = ("SDIR",)
DEFAULT_LIMIT = 40          # meetings whose evidence is fetched per run
MAX_FAILING = 5             # consecutive gapped meetings before the run stops: a host down
WITNESS_TYPES = frozenset(("28",))
CHAIR_TYPES = frozenset(("35", "36"))
# 26 is a committee researcher (Library of Parliament), 27 the clerk: officers
# of the committee, neither members nor witnesses (AMAD 44-1/1-3).
OFFICER_TYPES = frozenset(("26", "27"))

BLOCK = re.compile(r'<div class="accordion-item meeting-item-(\d{4}-\d{2}-\d{2})\s*"\s+'
                   r'id="meeting-item-(\d+)"')
NUMBER = re.compile(r'class="meeting-number">\s*Meeting\s+(\d+)\s*<')
STUDY = re.compile(r'class="studies-activities-item">([^<]*)<')
EVIDENCE = re.compile(r'class="btn[^"]*btn-meeting-evidence"\s+href="([^"]+)"')
EV_PATH = re.compile(r"/DocumentViewer/en/(\d{1,2})-(\d)/([A-Z]{4})/meeting-(\d+)/evidence")
XML_LINK = re.compile(r'href="([^"]*/Content/Committee/[^"]*/Evidence/[^"]*\.XML)"', re.I)
EXTRACTED = re.compile(r'<ExtractedItem Name="([A-Za-z]+)">([^<]*)</ExtractedItem>')
HOME_LINK = re.compile(r'href="((?:https?:)?//www\.parl\.ca)?/Committees/en/([A-Z]{4})"')


def committee_base(acr):
    return PARL if acr in JOINT else COMMONS


def meetings_url(acr, parl, sess, base=None):
    return MEETINGS.format(base or committee_base(acr), acr, parl, sess)


def _absolute(href, page_url):
    if href.startswith("//"):
        return "https:" + href
    return urljoin(page_url, href)


def parse_meeting_list(text, acr, parl, sess, page_url=None):
    """[meeting dict] from one committee's meeting list, in number order.

    Each block holds its date (in the class), the site's meeting id, the
    number, the study titles (printed twice, for two screen sizes; deduped in
    order), an In Camera lock icon, and an Evidence link when there is a
    public transcript. A block with no number is markup we do not know --
    returned with number None so the caller gaps it rather than skipping it."""
    page_url = page_url or meetings_url(acr, parl, sess)
    starts = [m for m in BLOCK.finditer(text)]
    out = []
    for i, m in enumerate(starts):
        chunk = text[m.start(): starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        num = NUMBER.search(chunk)
        studies = []
        for s in STUDY.findall(chunk):
            s = " ".join(htmlmod.unescape(s).split())
            if s and s not in studies:
                studies.append(s)
        ev = EVIDENCE.search(chunk)
        evidence = _absolute(htmlmod.unescape(ev.group(1)), page_url) if ev else None
        # A joint meeting's Evidence can be another committee's transcript;
        # the key follows the transcript, so the two never read it twice.
        key_acr, key_parl, key_sess, number = acr, parl, sess, int(num.group(1)) if num else None
        if evidence:
            path = EV_PATH.search(evidence)
            if path:
                key_parl, key_sess = int(path.group(1)), int(path.group(2))
                key_acr, number = path.group(3), int(path.group(4))
        out.append({
            "committee": key_acr, "listed_under": acr, "parliament": key_parl,
            "session": key_sess, "number": number, "date": m.group(1),
            "site_id": m.group(2), "studies": studies,
            "in_camera": 'title="In Camera"' in chunk, "evidence_url": evidence,
            "key": meeting_key(key_parl, key_sess, key_acr, number) if number else None})
    out.sort(key=lambda r: (r["number"] is None, r["number"] or 0))
    return out


def meeting_key(parl, sess, acr, number):
    return "{0}-{1}-{2}-{3}".format(parl, sess, acr, number)


def speech_id(parl, sess, acr, number, intervention):
    """'cmte-441-AMAD-10-11717363': never a Hansard Intervention id."""
    return "cmte-{0}{1}-{2}-{3}-{4}".format(parl, sess, acr, number, intervention)


def xml_link(page_text, page_url):
    hit = XML_LINK.search(page_text or "")
    return _absolute(htmlmod.unescape(hit.group(1)), page_url) if hit else None


def xml_identity(xml_text):
    """{Acronyme, MetaNumberNumber, ParliamentNumber, SessionNumber} as printed."""
    return {k: v.strip() for k, v in EXTRACTED.findall(xml_text[:20000])}


def title_passage(studies):
    return "; ".join(studies) if studies else None


def on_our_ground_title(tax, wl, studies):
    """The title gate for committees outside the key eight."""
    t = title_passage(studies)
    if not t:
        return False
    areas, _, _ = filt.aggregate_passages(filt.match_passages(tax, wl, "", title=t))
    return han.on_our_ground(areas)


def bill_of(studies):
    """The bill a meeting studies, when its titles name exactly one."""
    bills = {"{0}-{1}".format(m.group(1), m.group(2))
             for s in studies for m in han.BILL.finditer(s)}
    return next(iter(bills)) if len(bills) == 1 else None


class Senators:
    """Senators by name, from ca_senators ('Martin, Yonah'). A label prints
    'Hon. Yonah Martin', so both 'yonah martin' and first-token + surname
    are keys. Only a UNIQUE hit resolves. Filled by tools/ca_senate.py from
    the Senate's votes: a senator who has never voted on record there is
    not known, and stays NULL here."""

    def __init__(self, conn):
        self.by_name, self.by_surname = {}, {}
        for pid, name in conn.execute("SELECT person_id, name FROM ca_senators"):
            last, _, first = (name or "").partition(",")
            if not first.strip():
                continue
            for key in self._keys(first.strip() + " " + last.strip()):
                self.by_name.setdefault(key, set()).add(pid)
            toks = han.fold(first.strip() + " " + last.strip()).split()
            self.by_surname.setdefault(toks[-1], []).append((toks[0], pid))

    @staticmethod
    def _keys(name):
        toks = han.fold(name).split()
        if not toks:
            return []
        return list(dict.fromkeys([" ".join(toks), toks[0] + " " + toks[-1]]))

    def resolve(self, name, known_senator=False):
        """A unique exact hit; or, for a speaker the document itself calls a
        senator, a unique same-surname senator whose first name is the
        label's or its short form -- 'Stan Kutcher' is 'Hon. Stanley Kutcher'
        three lines later in AMAD 44-1/2."""
        for key in self._keys(name or ""):
            hits = self.by_name.get(key) or set()
            if len(hits) == 1:
                return next(iter(hits))
        toks = han.fold(name or "").split()
        if not known_senator or len(toks) < 2:
            return None
        hits = {pid for first, pid in self.by_surname.get(toks[-1], ())
                if first.startswith(toks[0]) or toks[0].startswith(first)}
        return next(iter(hits)) if len(hits) == 1 else None


def role(iv):
    """'chair', 'witness' or 'member' -- the Affiliation Type decides first."""
    t = iv.get("aff_type")
    label = (iv.get("label") or "").strip()
    if t in WITNESS_TYPES:
        return "witness"
    if t in CHAIR_TYPES or t in OFFICER_TYPES or not label or label.startswith("The "):
        return "chair"
    return "member"


def _senator_label(riding):
    """'Senator, Nova Scotia, ISG' -- and 'senator, Québec (Rougement), ISG',
    as AMAD 44-1/3 printed it."""
    return bool(riding) and riding.split(",")[0].strip().casefold() == "senator"


class Attribution:
    """Who each member intervention in ONE document is.

    Learned from the labels that identify: a riding ('Mr. Michael Cooper
    (St. Albert—Edmonton, CPC)') or 'Senator' ('Hon. Stan Kutcher (Senator,
    Nova Scotia, ISG)'). The DbId and the folded name are both remembered,
    because a DbId is not one per person even within a file. A bare label
    is then resolved by its DbId, its name in this document, and only then
    by a unique name in ca_members -- or ca_senators on a joint committee,
    where a name found in BOTH is left NULL rather than guessed."""

    def __init__(self, ivs, roster, senators, joint):
        self.roster, self.senators, self.joint = roster, senators, joint
        self.by_db, self.by_name, self.senate_db, self.senate_names = {}, {}, set(), set()
        for iv in ivs:
            if role(iv) != "member":
                continue
            name, riding, party = han.parse_label(iv["label"])
            if _senator_label(riding):
                group = riding.rsplit(",", 1)[-1].strip() if "," in riding else None
                self.senate_db.add(iv["db_id"])
                self.senate_names.add(han.fold(name))
                pid = senators.resolve(name, known_senator=True)
                hit = (pid, "senate", group)
            elif riding:
                pid, _ = roster.resolve(name, riding)
                hit = (pid, "commons", party)
            else:
                continue
            if pid:
                if iv["db_id"]:
                    self.by_db.setdefault(iv["db_id"], hit)
                self.by_name.setdefault(han.fold(name), hit)

    def resolve(self, iv):
        """(person_id or None, chamber, party or group as printed)."""
        name, riding, party = han.parse_label(iv["label"])
        if iv["db_id"] in self.by_db:
            return self.by_db[iv["db_id"]]
        if han.fold(name) in self.by_name:
            return self.by_name[han.fold(name)]
        if iv["db_id"] in self.senate_db or han.fold(name) in self.senate_names \
                or _senator_label(riding):
            return self.senators.resolve(name, known_senator=True), "senate", None
        pid, _ = self.roster.resolve(name, riding)
        sen = self.senators.resolve(name) if self.joint else None
        if pid and sen:
            return None, "commons", party       # both rosters claim the name: never guessed
        if sen:
            return sen, "senate", None
        return pid, "commons", party


def witness_labels(ivs):
    """{DbId: (name as printed, affiliation)} from each witness's FIRST
    labelled intervention: 'Dr. Ramona Coelho (Physician, As an Individual)'."""
    out = {}
    for iv in ivs:
        if role(iv) != "witness":
            continue
        label = " ".join((iv["label"] or "").replace(":", " ").split())
        hit = han.LABEL.match(label)
        if hit and iv["db_id"] not in out:
            out[iv["db_id"]] = (hit.group("name").strip(), hit.group("inner").strip())
    return out


def organisation(affiliation):
    """The organisation is the last part of the affiliation: 'Co-Chair, Board
    of Directors, Disability Without Poverty' -> 'Disability Without Poverty';
    'Physician, As an Individual' -> 'As an Individual'."""
    if not affiliation:
        return None
    return affiliation.rsplit(",", 1)[-1].strip() or None


def store_meeting(conn, m, date, ivs, tax, wl, today, roster=None, senators=None):
    """Store one meeting's interventions on our ground and its totals row."""
    roster = roster or han.Roster(conn)
    senators = senators or Senators(conn)
    parl, sess, acr, number = m["parliament"], m["session"], m["committee"], m["number"]
    key = meeting_key(parl, sess, acr, number)
    title = title_passage(m["studies"])
    bill = bill_of(m["studies"])
    who = Attribution(ivs, roster, senators, acr in JOINT)
    wit = witness_labels(ivs)
    t = {"interventions": len(ivs), "chair": 0, "members": 0, "witnesses": 0,
         "speeches": 0, "testimony": 0, "unresolved": 0, "chars": 0}
    for iv in ivs:
        t["chars"] += len(iv["text"] or "")
        kind = role(iv)
        if kind == "chair":
            t["chair"] += 1
            continue
        t["members" if kind == "member" else "witnesses"] += 1
        matches = filt.match_passages(tax, wl, iv["text"] or "", title=title)
        areas, terms, excerpt = filt.aggregate_passages(matches)
        if not han.on_our_ground(areas):
            continue
        sid = speech_id(parl, sess, acr, number, iv["id"])
        if kind == "witness":
            # NEVER a person_id, NEVER ca_speeches: Type 28 is testimony.
            name, affiliation = wit.get(iv["db_id"]) or (
                han.HONORIFICS.sub("", iv["label"] or "").strip() or None, None)
            conn.execute(
                "INSERT INTO ca_testimony (testimony_id, intervention_id, meeting_key, "
                "committee, date, time, subject, db_id, label, witness, affiliation, "
                "organisation, text, excerpt, areas, matched_terms, first_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(testimony_id) DO UPDATE SET text=excluded.text, "
                "areas=excluded.areas, matched_terms=excluded.matched_terms, "
                "excerpt=excluded.excerpt",
                (sid, iv["id"], key, acr, date, iv["time"], title, iv["db_id"], iv["label"],
                 name, affiliation, organisation(affiliation), iv["text"], excerpt,
                 json.dumps(areas), json.dumps(terms), today))
            t["testimony"] += 1
            continue
        pid, chamber, party = who.resolve(iv)
        if pid is None:
            t["unresolved"] += 1
        conn.execute(
            "INSERT INTO ca_speeches (speech_id, sitting_key, date, time, rubric, "
            "subject, bill_number, kind, db_id, person_id, speaker, party, text, "
            "areas, matched_terms, excerpt, first_seen, chamber, forum, committee) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(speech_id) DO UPDATE SET text=excluded.text, "
            "person_id=COALESCE(excluded.person_id, ca_speeches.person_id), "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "excerpt=excluded.excerpt",
            (sid, key, date, iv["time"], "Committee evidence", title, bill, iv["kind"],
             iv["db_id"], pid, iv["label"], party, iv["text"], json.dumps(areas),
             json.dumps(terms), excerpt, today, chamber, "committee", acr))
        t["speeches"] += 1
    record_meeting(conn, m, "read", today, date=date, totals=t)
    conn.commit()
    return t


def record_meeting(conn, m, status, today, date=None, totals=None, xml_url=None):
    t = totals or {}
    conn.execute(
        "INSERT OR REPLACE INTO ca_committee_meetings (meeting_key, committee, parliament, "
        "session, number, date, studies, in_camera, status, site_meeting_id, evidence_url, "
        "xml_url, interventions, chair, members, witnesses, speeches, testimony, unresolved, "
        "chars, read_on) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (m["key"], m["committee"], m["parliament"], m["session"], m["number"],
         date or m["date"], json.dumps(m["studies"], ensure_ascii=False),
         1 if m["in_camera"] else 0, status, m["site_id"], m["evidence_url"],
         xml_url or m.get("xml_url"), t.get("interventions"), t.get("chair"),
         t.get("members"), t.get("witnesses"), t.get("speeches"), t.get("testimony"),
         t.get("unresolved"), t.get("chars"), today))


def already_read(conn):
    """Meeting keys never to fetch again: read, or in camera."""
    return {r[0] for r in conn.execute(
        "SELECT meeting_key FROM ca_committee_meetings WHERE status IN ('read', 'in_camera')")}


def home_committees(client):
    """{ACR: base} from the House's committee home page. It lists the
    CURRENT committees only (it ignores ?parl=), so a special committee of
    an older Parliament is missed unless named with --committee."""
    text = client.get_text(HOME, FEED, "home", archive=False)
    out = {}
    for host, acr in HOME_LINK.findall(text):
        out.setdefault(acr, PARL if host else COMMONS)
    return out


def read_meeting(conn, client, m, tax, wl, today, roster, senators, log):
    """Fetch, parse and store one meeting with evidence. Returns
    (totals, None) or (None, gap detail)."""
    try:
        page = client.get_text(m["evidence_url"], FEED, "evidence-" + m["key"], archive=False)
    except FetchError as exc:
        return None, "{0}: evidence page: {1}".format(m["key"], exc)
    url = xml_link(page, m["evidence_url"])
    if not url:
        return None, "{0}: evidence page links no XML ({1})".format(m["key"], m["evidence_url"])
    m["xml_url"] = url
    try:
        text = client.get_text(url, FEED, "xml-" + m["key"])
        date, ivs = han.parse_sitting(text)
    except FetchError as exc:
        return None, "{0}: XML: {1}".format(m["key"], exc)
    except ET.ParseError as exc:
        return None, "{0}: XML did not parse ({1})".format(m["key"], exc)
    ident = xml_identity(text)
    printed = (ident.get("Acronyme"), ident.get("MetaNumberNumber"))
    if printed[0] and (printed[0] != m["committee"] or
                       (printed[1] and printed[1].lstrip("0") != str(m["number"]))):
        return None, "{0}: XML is {1} meeting {2}, not this one ({3})".format(
            m["key"], printed[0], printed[1], url)
    if not ivs:
        return None, "{0}: XML has no interventions ({1})".format(m["key"], url)
    return store_meeting(conn, m, date, ivs, tax, wl, today, roster, senators), None


def pull(conn, client, today, session=CURRENT_SESSION, committees=KEY_EIGHT,
         gated=(), limit=DEFAULT_LIMIT, tax=None, wl=None, log=print, budget=None,
         bases=None):
    """Walk each committee's meeting list for one session and read every
    unread public meeting (title-gated for `gated` committees).
    Returns a summary dict; gaps are recorded in the store."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    parl, sess = han.parse_session(session)
    roster, senators = han.Roster(conn), Senators(conn)
    done = already_read(conn)
    failing = 0
    s = {"attempted": 0, "read": 0, "speeches": 0, "testimony": 0, "in_camera": 0, "no_evidence": 0,
         "skipped": 0, "title_gated": 0, "listed": 0, "unresolved": 0, "stopped": None}
    gaps = []
    for acr in list(committees) + [g for g in gated if g not in committees]:
        if s["stopped"]:
            break
        is_gated = acr not in committees
        url = meetings_url(acr, parl, sess, (bases or {}).get(acr))
        try:
            listing = parse_meeting_list(
                client.get_text(url, FEED, "meetings-{0}-{1}-{2}".format(acr, parl, sess),
                                archive=False), acr, parl, sess, url)
        except FetchError as exc:
            gaps.append("{0} {1}: meeting list: {2}".format(acr, session, exc))
            continue
        s["listed"] += len(listing)
        counts = {"read": 0, "camera": 0, "pending": 0, "gated": 0}
        for m in listing:
            if m["number"] is None:
                gaps.append("{0} {1}: a meeting block ({2}) with no number -- markup "
                            "changed?".format(acr, session, m["site_id"]))
                continue
            if m["key"] in done:
                s["skipped"] += 1
                continue
            if is_gated and not on_our_ground_title(tax, wl, m["studies"]):
                s["title_gated"] += 1
                counts["gated"] += 1
                continue
            if not m["evidence_url"]:
                status = "in_camera" if m["in_camera"] else "no_evidence"
                record_meeting(conn, m, status, today)
                s["in_camera" if m["in_camera"] else "no_evidence"] += 1
                counts["camera" if m["in_camera"] else "pending"] += 1
                if m["in_camera"]:
                    done.add(m["key"])
                continue
            # Past the cap or the clock, the rest of THIS list is still walked:
            # recording an in-camera meeting costs no fetch.
            if s["stopped"]:
                continue
            if limit is not None and s["attempted"] >= limit:
                s["stopped"] = "limit"
                continue
            if failing >= MAX_FAILING:
                s["stopped"] = "failing"
                continue
            if budget is not None and budget.exhausted():
                log(budget.disclose("committee meetings", s["read"]))
                s["stopped"] = "budget"
                continue
            s["attempted"] += 1
            totals, gap = read_meeting(conn, client, m, tax, wl, today, roster, senators, log)
            if gap:
                gaps.append(gap)
                failing += 1
                continue
            failing = 0
            done.add(m["key"])
            s["read"] += 1
            counts["read"] += 1
            s["speeches"] += totals["speeches"]
            s["testimony"] += totals["testimony"]
            s["unresolved"] += totals["unresolved"]
            log("  {0} {1}: {2} interventions ({3} member, {4} witness, {5} chair); "
                "{6} speech(es) + {7} testimony on our ground{8}".format(
                    m["key"], m["date"], totals["interventions"], totals["members"],
                    totals["witnesses"], totals["chair"], totals["speeches"],
                    totals["testimony"], ", {0} unattributed".format(totals["unresolved"])
                    if totals["unresolved"] else ""))
        conn.commit()
        log("  {0} {1}: {2} listed, {3} read now, {4} in camera, {5} awaiting evidence{6}".format(
            acr, session, len(listing), counts["read"], counts["camera"], counts["pending"],
            ", {0} off our ground by title".format(counts["gated"]) if is_gated else ""))
    if s["stopped"] == "limit":
        log("  meeting cap ({0}) reached; the rest are read on later runs".format(limit))
    if s["stopped"] == "failing":
        log("  {0} meetings in a row failed: stopped, the rest are retried on the next "
            "run".format(MAX_FAILING))
    s["gaps"] = db.record_gaps(conn, FEED, gaps, edition=today)
    for g in gaps:
        log("  [gap] " + g[:160])
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=CURRENT_SESSION, help="P-S, e.g. 44-1")
    ap.add_argument("--committee", help="one acronym, or several comma-separated (JUST,AMAD)")
    ap.add_argument("--all-committees", action="store_true",
                    help="also every other committee, title-gated to our ground")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="meetings whose evidence is fetched (or attempted) per run")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="read and count into an in-memory store; nothing is kept")
    args = ap.parse_args()
    parl, _ = han.parse_session(args.session)
    # One request a second: two of the three hops are heavy pages.
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0)
    today = datetime.date.today().isoformat()
    conn = ca_store.ensure_schema(db.init_db(db.connect(":memory:" if args.dry_run else args.db)))
    committees = tuple(c.strip().upper() for c in args.committee.split(",")) \
        if args.committee else KEY_EIGHT
    gated, bases = (), {}
    if args.all_committees:
        try:
            bases = home_committees(client)
        except FetchError as exc:
            db.record_gaps(conn, FEED, ["committee home page: {0}".format(exc)], edition=today)
            print("  [gap] committee home page: {0}".format(exc))
        gated = tuple(sorted(set(bases) | set(EXTRA)))
    members = han.load_roster(conn, client, parl, today)
    print("ca-committees: {0}, {1} committee(s){2}, roster of {3} member(s), {4} senator(s) "
          "known".format(args.session, len(committees),
                         " + {0} title-gated".format(len([g for g in gated if g not in committees]))
                         if gated else "", members,
                         conn.execute("SELECT COUNT(*) FROM ca_senators").fetchone()[0]))
    s = pull(conn, client, today, session=args.session, committees=committees, gated=gated,
             limit=args.limit, budget=drain.Budget(args.budget_seconds), bases=bases)
    print("ca-committees: {0} meeting(s) read, {1} speech(es) and {2} testimony on our ground, "
          "{3} unattributed; {4} in camera, {5} awaiting evidence, {6} already read{7}; "
          "{8} gap(s){9}.".format(
              s["read"], s["speeches"], s["testimony"], s["unresolved"], s["in_camera"],
              s["no_evidence"], s["skipped"],
              ", {0} off our ground by title".format(s["title_gated"]) if gated else "",
              s["gaps"], " (dry run: nothing kept)" if args.dry_run else ""))
    if s["listed"] == 0 and not s["gaps"]:
        # A redesign that empties every list must not read as a quiet week.
        db.record_gaps(conn, FEED, ["{0}: every meeting list parsed to nothing".format(
            args.session)], edition=today)
        print("  [gap] every meeting list parsed to nothing -- markup changed, or no "
              "committee sat in {0}".format(args.session))
        s["gaps"] = 1
    if not args.dry_run:
        n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        print("  store: {0} meeting(s) held ({1} read), {2} committee speech(es), {3} testimony, "
              "{4} unattributed".format(
                  n("SELECT COUNT(*) FROM ca_committee_meetings"),
                  n("SELECT COUNT(*) FROM ca_committee_meetings WHERE status='read'"),
                  n("SELECT COUNT(*) FROM ca_speeches WHERE forum='committee'"),
                  n("SELECT COUNT(*) FROM ca_testimony"),
                  n("SELECT COUNT(*) FROM ca_speeches WHERE forum='committee' "
                    "AND person_id IS NULL")))
    conn.close()
    return 1 if s["gaps"] else 0


if __name__ == "__main__":
    sys.exit(main())
