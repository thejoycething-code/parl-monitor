"""House of Assembly of Newfoundland and Labrador: roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov nl. Scope: docs/canada-provinces-scope.md
(Newfoundland and Labrador: value 2, difficulty 3). robots.txt disallows
only /search. No WAF.

THE RECORD IS HANSARD, NOT THE JOURNAL. The scope proposed the Journals
(PDF, AYES/NAYS in two columns of initial-and-surname). Read live, they
print NO TOTALS ("Ayes Nayes", then names), so the tally check would have
nothing to check against, and they lag: the 51st General Assembly's are not
posted. Hansard (Word-exported HTML, one file per sitting, from the 1990s)
prints every recorded division in full: the Clerk reads each member's name
standing ("CLERK: Steve Crocker, Lisa Dempster, ...") and then the count
("Speaker, the ayes: 21; the nays: 14"). The Clerk's count is the printed
total and the tally check runs against it.

  * LISTING. /HouseBusiness/Hansard/ga<G>session<S>/ is a calendar whose
    links are the sitting files ("22-11-01.htm"); taken from it, never
    constructed.
  * ROSTER. The site lists only the CURRENT members (js/members-index.js,
    referenced from /Members/members.aspx: "Surname, Given", district,
    party, undated). Past members are listed nowhere with dates of service;
    the nearest official list is the annual Members' Attendance summary
    (/Members/Attendance/, one PDF per calendar year), which names "all
    Members ... including those who resigned or were elected during the
    reporting period", with district. A term from it is that calendar year,
    no party: precise only to the year, so resolution leans on the name.
    Party at the vote is never stored for Newfoundland and Labrador.
  * NAMES. Hansard reads familiar names ("Eddie Joyce", "Pam Parsons",
    "Sherry Gambin-Walsh"); the attendance summary prints formal ones
    ("Joyce, Edward", "Parsons, Pamela", "Gambin-Walsh, Sheryl"). A full
    name that does not resolve is retried as initial plus surname -- the
    Journal's own form ("E. Joyce") -- still unique-or-nothing, so the two
    Parsons and the two Dinns are told apart by initial and a nickname
    with another initial stays unresolved. Hyphens and spaces in surnames
    are the same thing ("Gambin Walsh" in the 2016 summary).
  * ROSTER_CORRECTIONS: a source typo checked against Hansard and the
    Journal, corrected by hand with the reason; never an inference.
  * BILLS. /HouseBusiness/Bills/ga<G>session<S>/ is the progress-of-bills
    table (stage dates) with a link to each bill's text (HTML), classified
    per passage.
  * VOICE. Hansard's formal record line "On motion, a bill, '...', read a
    third time, ordered passed ... (Bill 43)" (sometimes without "On
    motion") with no division on that bill and stage that day is a voice
    decision.
  * CROSS-CHECK. Every second or third reading the progress table dates to a
    day whose Hansard was read must be found in it, divided or on voice; and
    every "please rise" call must have its count. A miss is a gap.
"""

from __future__ import annotations

import datetime
import html as _html
import json
import re
from collections import Counter
from urllib.parse import urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text, join_fragments, pdf_rows, sessions_sorted, slug, year_span

PROV = "nl"
CURRENT_SESSION = "51-1"
BASE = "https://www.assembly.nl.ca"
HANSARD = BASE + "/HouseBusiness/Hansard/ga{0}session{1}/"
BILLS = BASE + "/HouseBusiness/Bills/ga{0}session{1}/"
MEMBERS = BASE + "/Members/members.aspx"
ATTENDANCE = BASE + "/Members/Attendance/"

STAGE_CODE = {"First Reading": "1r", "Second Reading": "2r", "Third Reading": "3r"}

# (surname, given) as printed in an attendance summary -> (surname, given)
# as the member is named in Hansard and the Journal. Each entry is a typo
# in the source, read against both.
ROSTER_CORRECTIONS = {
    ("Dempter", "Lisa"): ("Dempster", "Lisa"),   # 2022 summary; Hansard and Journal print Dempster
}


def parse_session(code):
    m = re.match(r"^(\d{2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("Newfoundland and Labrador session must look like 50-2, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def _current_legislature():
    return parse_session(CURRENT_SESSION)[0]


_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def table_date(text):
    """'Nov. 15/2016', 'June 6/2016', 'Apr. 13.2016', 'Decd. 14/2016',
    'October 5, 2022' -> ISO date, or None."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    m = re.match(r"^([A-Za-z]+)\.?\s*(\d{1,2})\s*[/.,]\s*(\d{4})$", t)
    if not m:
        return None
    mon = _MONTHS.get(m.group(1)[:3].lower())
    if not mon:
        return None
    try:
        return datetime.date(int(m.group(3)), mon, int(m.group(2))).isoformat()
    except ValueError:
        return None


# -- listing ----------------------------------------------------------------

_SITTING_HREF = re.compile(r'href="((\d{2})-(\d{2})-(\d{2})([A-Za-z0-9_\-]*)\.html?)"', re.I)


def list_records(html, base_url):
    """[{date, url, part}] from a session's Hansard calendar."""
    out, seen = [], set()
    for href, yy, mm, dd, part in _SITTING_HREF.findall(html or ""):
        url = urljoin(base_url, _html.unescape(href))
        if url in seen:
            continue
        seen.add(url)
        year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        try:
            date = datetime.date(year, int(mm), int(dd)).isoformat()
        except ValueError:
            continue
        out.append({"date": date, "url": url, "part": slug(part) if part else None})
    return sorted(out, key=lambda r: (r["date"], r["part"] or ""))


# -- sessions ---------------------------------------------------------------

HANSARD_INDEX = BASE + "/HouseBusiness/Hansard/"
_SESSION_ITEM = re.compile(
    r'href="(?:[^"]*/)?ga(\d+)session(\d)/"[^>]*>\s*\d+(?:st|nd|rd|th)\s+Session\s*[–—-]\s*'
    r'(\d{4})(?:\s*(-)\s*(\d{4})?)?', re.I)


def parse_sessions(html):
    """Every session on the Hansard index ("3rd Session – 2010-2011", "4th
    Session – 2011", and the open "1st Session – 2025--"), oldest first. The
    swearing-in links under each General Assembly are not sessions."""
    return sessions_sorted(
        year_span("{0}-{1}".format(int(ga), int(sess)), y1, y2, open_ended=bool(dash) and not y2)
        for ga, sess, y1, dash, y2 in _SESSION_ITEM.findall(html or ""))


def list_sessions(ctx):
    html = ctx.text(HANSARD_INDEX, "hansard-index")
    out = parse_sessions(html)
    if html and not out:
        ctx.gap("nl: no sessions parsed from {0}".format(HANSARD_INDEX))
    return out


# -- rosters ----------------------------------------------------------------

_JS_ENTRY = re.compile(r"name:\s*'(.*?)',\s*district:\s*'((?:[^'\\]|\\.)*)',\s*party:\s*'((?:[^'\\]|\\.)*)'",
                       re.S)


def member_key(given, surname):
    toks = [t for t in re.split(r"\s+", given or "") if t and not pn._INITIALS.match(t)]
    return slug((toks[0] if toks else (given or "")) + " " + surname)


def parse_members_js(js):
    """[{key, surname, given, name, district, party}] from members-index.js."""
    out = []
    for name, district, party in _JS_ENTRY.findall(js or ""):
        name = html_text(name.replace("\\'", "'"))
        surname, _, given = name.partition(",")
        surname, given = surname.strip(), given.strip()
        out.append({"key": member_key(given, surname), "surname": surname, "given": given,
                    "name": (given + " " + surname).strip(),
                    "district": district.replace("\\'", "'").strip(),
                    "party": party.replace("\\'", "'").strip() or None})
    return out


def members_js_url(html):
    m = re.search(r'<script[^>]*src="([^"]*members-index\.js[^"]*)"', html or "")
    return urljoin(MEMBERS, m.group(1)) if m else None


def attendance_reports(html):
    """{year: url} from the attendance listing."""
    out = {}
    for href, year in re.findall(r'href="([^"]*SummaryMembersAttendance(\d{4})\.pdf)"', html or "", re.I):
        out[int(year)] = urljoin(ATTENDANCE, _html.unescape(href))
    return out


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").replace("\t", " ").replace("‐", "-")).strip()


# An absence count, or a leave of absence ("LOA": Derrick Bragg, 2023 summary).
_DIGITS = re.compile(r"^\s*(?:\d+|LOA|N\/A)\s*$")


def _is_header(fr):
    words = [_clean(f[2]) for f in fr]
    return "Member" in words and "District" in words


def parse_attendance(pages, year):
    """[{surname, given, district}] from the attendance summary's rows.

    pages: pdf_rows() output. A data row is a name, a district and the two
    absence counts (digits). The column headings are centred, so the
    district column's left edge is measured from the data: the commonest
    fragment start between 100 and 330 pt. A line with only a district
    fragment is a wrapped district. The 2025 summary is set upside down
    (its rows come out last name first, the heading BELOW them): a page
    whose heading follows most of its data rows is read in reverse."""
    rows = []
    found = False
    for page in pages:
        lines = [fr for _, fr in page]
        head = next((k for k, fr in enumerate(lines) if _is_header(fr)), None)
        if head is not None:
            found = True
            data_before = sum(1 for fr in lines[:head] if any(_DIGITS.match(f[2]) for f in fr))
            data_after = sum(1 for fr in lines[head + 1:] if any(_DIGITS.match(f[2]) for f in fr))
            if data_before > data_after:
                lines = lines[::-1]
        rows.extend(lines)
    if not found:
        return []
    edges = Counter(round(f[0]) for fr in rows for f in fr
                    if 100 <= f[0] <= 330 and any(_DIGITS.match(g[2]) for g in fr))
    if not edges:
        return []
    edge = edges.most_common(1)[0][0] - 2
    out = []
    for fr in rows:
        if _is_header(fr):
            continue
        parts = re.split(r"\s{3,}", fr[0][2].strip()) if len(fr) == 1 else []
        if len(parts) >= 3 and _DIGITS.match(parts[-1]):
            # one fragment padded with spaces ('Parsons, Jim     Corner Brook
            # 0     0', the 2025 summary)
            nums = [p for p in parts[1:] if _DIGITS.match(p)]
            name = _clean(parts[0])
            district = _clean(" ".join(p for p in parts[1:] if not _DIGITS.match(p)))
        else:
            nums = [f for f in fr if f[0] >= edge and _DIGITS.match(f[2])]
            name = _clean(join_fragments([f for f in fr if f[0] < edge]))
            district = _clean(join_fragments([f for f in fr if f[0] >= edge and not _DIGITS.match(f[2])]))
        if not name and district and out and not nums and out[-1].get("open"):
            out[-1]["district"] = _clean(out[-1]["district"] + " " + district)
            continue
        if out:
            out[-1].pop("open", None)
        if not name or re.search(r"\d", name) or not nums:
            continue
        name = re.sub(r"\s*-\s*", "-", name)
        if "," in name:
            surname, _, given = name.partition(",")
        else:
            # Given name first (the 2016 summary). The LAST word is
            # taken as the surname and the rest as given names: 'Carol Anne
            # Haley' -> Haley, and 'Sherry Gambin Walsh' -> Walsh with
            # 'Sherry Gambin', which the resolver still matches to 'Ms.
            # Gambin-Walsh' because a label's leading words may be given names.
            toks = name.split()
            given, surname = " ".join(toks[:-1]), toks[-1]
        surname, given = surname.strip(), given.strip()
        surname, given = ROSTER_CORRECTIONS.get((surname, given), (surname, given))
        out.append({"surname": surname, "given": given, "district": district, "year": year, "open": True})
    for r in out:
        r.pop("open", None)
        r["district"] = re.sub(r"\s*[-\u2013]\s*", " - ", r["district"])
    return out


def fetch_roster(ctx, legislature, years):
    """The current members (for the current General Assembly) and the
    attendance summaries for the calendar years the window touches."""
    n = 0
    if legislature == _current_legislature():
        page = ctx.text(MEMBERS, "members")
        url = members_js_url(page) if page else None
        if page and not url:
            ctx.gap("nl: {0} names no members-index.js".format(MEMBERS))
        js = ctx.text(url, "members-js") if url else None
        rows = parse_members_js(js) if js else []
        if js and not rows:
            ctx.gap("nl: no members parsed from {0}".format(url))
        if rows and not ctx.dry_run:
            ctx.conn.execute("UPDATE prov_members SET sitting=0 WHERE prov=?", (PROV,))
            for r in rows:
                ps.upsert_member(ctx.conn, PROV, r["key"], name=r["name"], surname=r["surname"],
                                 given=r["given"], riding=r["district"], party=r["party"], sitting=1)
                ps.replace_terms(ctx.conn, PROV, r["key"], [{
                    "legislature": legislature, "party": r["party"], "riding": r["district"],
                    "start": None, "end": None, "party_dated": 0}], "roster")
            ctx.conn.commit()
            ctx.log("  nl roster: {0} current member(s) (General Assembly {1}; party undated)".format(
                len(rows), legislature))
        n += len(rows)
    if not years:
        return n
    listing = ctx.text(ATTENDANCE, "attendance")
    reports = attendance_reports(listing) if listing else {}
    for year in sorted(years):
        source = "attendance-{0}".format(year)
        if not ctx.refresh and ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source=?",
                (PROV, source)).fetchone()[0]:
            continue
        url = reports.get(year)
        if not url:
            if year < datetime.date.today().year:
                ctx.gap("nl: no Members' Attendance summary listed for {0}; that year's divisions "
                        "resolve only against the current roster".format(year))
            continue
        raw = ctx.bytes(url, "attendance-{0}".format(year))
        if raw is None:
            continue
        try:
            rows = parse_attendance(pdf_rows(raw), year)
        except Unreadable as exc:
            ctx.gap("nl attendance {0}: {1}: {2}".format(year, url, exc))
            continue
        if not rows:
            ctx.gap("nl attendance {0}: no members parsed from {1}".format(year, url))
            continue
        if ctx.dry_run:
            n += len(rows)
            continue
        for r in rows:
            key = member_key(r["given"], r["surname"])
            ps.upsert_member(ctx.conn, PROV, key, name=r["given"] + " " + r["surname"],
                             surname=r["surname"], given=r["given"])
            ps.replace_terms(ctx.conn, PROV, key, [{
                "legislature": None, "party": None, "riding": r["district"],
                "start": "{0}-01-01".format(year), "end": "{0}-12-31".format(year),
                "party_dated": 0}], source)
        ctx.conn.commit()
        ctx.log("  nl roster {0}: {1} member(s) from the attendance summary".format(year, len(rows)))
        n += len(rows)
    return n


class NameResolver:
    """prov_names.Resolver with Newfoundland's two allowances: hyphen equals
    space in a surname, and a full name that does not resolve is retried as
    initial plus surname (still unique-or-nothing)."""

    def __init__(self, resolver):
        members = {k: dict(m, surname=(m.get("surname") or "").replace("-", " "))
                   for k, m in resolver.members.items()}
        self.r = pn.Resolver(members, resolver.terms)

    def party_at(self, key, date, legislature=None):
        return self.r.party_at(key, date, legislature)

    def resolve(self, raw, date, legislature=None):
        label = re.sub(r"(\w)-(\w)", r"\1 \2", raw or "")
        key, how = self.r.resolve(label, date, legislature)
        if key or not how.startswith("unknown"):
            return key, how
        lab = pn.parse_label(label)
        if len(lab.tokens) >= 2 and not lab.initials:
            key2, how2 = self.r.resolve("{0}. {1}".format(lab.tokens[0][0].upper(), " ".join(lab.tokens[1:])),
                                        date, legislature)
            if key2:
                return key2, "initial (given name as printed differs)"
            return None, how2 if how2.startswith("ambiguous") else how
        return key, how


# -- bills ------------------------------------------------------------------

_ROW = re.compile(r"<tr>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_COLUMNS = ("First Reading", "Second Reading", "Committee", "Amendments", "Third Reading", "Royal Assent")


def parse_bill_list(html, base_url):
    """[{number, title, href, stages: [{stage, date}], amendments, chapter}]"""
    out = []
    for row in _ROW.findall(html or ""):
        cells = _CELL.findall(row)
        if len(cells) < 8:
            continue
        num = re.match(r"^\s*(\d+)\.?\s*$", html_text(cells[0]))
        if not num:
            continue
        link = re.search(r'href="([^"]+)"', cells[1])
        stages = []
        for name, cell in zip(_COLUMNS, cells[2:8]):
            if name == "Amendments":
                continue
            d = table_date(html_text(cell))
            if d:
                stages.append({"stage": name, "date": d, "status": "passed"})
        out.append({"number": num.group(1), "title": html_text(cells[1]),
                    "href": urljoin(base_url, _html.unescape(link.group(1))) if link else None,
                    "amendments": html_text(cells[5]) or None,
                    "chapter": html_text(cells[8]) if len(cells) > 8 else None, "stages": stages})
    return out


def bill_text(ctx, url, slug_):
    raw = ctx.text(url, slug_, encoding="cp1252")
    if raw is None:
        return None
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    body = re.sub(r"(?i)</(p|h\d|div|tr|li)>|<br[^>]*>", "\n\n", body)
    return "\n".join(html_text(l) for l in body.split("\n\n") if html_text(l))


def fetch_bills(ctx, legislature, session, tax, wl):
    url = BILLS.format(legislature, session)
    html = ctx.text(url, "bills-{0}-{1}".format(legislature, session))
    items = parse_bill_list(html, url) if html else []
    if html and not items:
        ctx.gap("nl bills {0}-{1}: no bills parsed from the progress table".format(legislature, session))
    if ctx.dry_run:
        return {"bills": len(items)}
    texts = 0
    windowed = bool(ctx.since or ctx.until)
    out_of_time = False
    for it in items:
        key = ps.bill_key(PROV, legislature, session, it["number"])
        record = {"bill_key": key, "prov": PROV, "legislature": legislature, "session": session,
                  "number": it["number"], "title_en": it["title"], "stages": it["stages"],
                  "page_url": url, "text_url": it["href"],
                  "latest_stage": it["stages"][-1]["stage"] if it["stages"] else None,
                  "royal_assent": next((s["date"] for s in it["stages"] if s["stage"] == "Royal Assent"), None)}
        have = ctx.conn.execute("SELECT text_read FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
        wanted = (not windowed or any(ctx.in_window(s["date"]) for s in it["stages"])
                  or pc.watched_bill(PROV, key) is not None)
        if not out_of_time and ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("bill texts", texts))
            out_of_time = True
        if (have and have[0] and not ctx.refresh) or not wanted or out_of_time or not it["href"]:
            if have and have[0]:
                ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
            else:
                res = pc.classify(tax, wl, PROV, title=it["title"], bill_key=key)
                ps.store_bill(ctx.conn, dict(record, text_read=0, areas=res.areas,
                                             matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
            continue
        body = bill_text(ctx, it["href"], "billtext-{0}-{1}-{2}".format(legislature, session, it["number"]))
        texts += 1 if body else 0
        res = pc.classify(tax, wl, PROV, title=it["title"], texts=[body] if body else [], bill_key=key)
        ps.store_bill(ctx.conn, dict(record, text_read=1 if body else 0, areas=res.areas,
                                     matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
    ctx.conn.commit()
    ctx.log("  nl bills {0}-{1}: {2} listed, {3} text(s) read".format(legislature, session, len(items), texts))
    return {"bills": len(items), "bill_texts": texts}


# -- Hansard ----------------------------------------------------------------

_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
_WORDS.update({"twenty": 20, "thirty": 30, "forty": 40, "nil": 0, "none": 0})
_NUM = r"(\d+|[A-Za-z]+(?:[\s\-][A-Za-z]+)?)"
TOTALS = re.compile(r"(?:the\s+)?ayes[:,]?\s*" + _NUM + r"\s*[;,.]?\s*(?:and\s+)?the\s+nays[:,]?\s*" + _NUM, re.I)
_FAVOUR = re.compile(r"(?:All\s+)?(?:those\s+)?in\s+favour(?:\s+of\s+the\s+([\w\-]+))?[^.?!:]{0,60}?,?\s*"
                     r"please\s+(?:rise|stand)", re.I)
_AGAINST = re.compile(r"(?:All\s+)?(?:those\s+)?(?:against|opposed)\b[^.?!:]{0,60}?(?:please\s+(?:rise|stand)|[.?])",
                      re.I)
# A speaker label ends a list of names: 'SOME HON. MEMBERS:', 'MR. SPEAKER:',
# 'CLERK (Barnes):'. Names are read in mixed case, so they never match.
_SPEAKER_LABEL = re.compile(r"\b(?:[A-Z][A-Z.'’\-]*\s+){0,4}[A-Z][A-Z.'’\-]+(?:\s*\([^)]*\))?\s*:")


def count_value(text):
    """'21' -> 21, 'nine' -> 9, 'twenty-one' -> 21, 'nil' -> 0; None if not a count."""
    t = (text or "").strip().lower()
    if t.isdigit():
        return int(t)
    parts = re.split(r"[\s\-]+", t)
    if len(parts) == 1:
        return _WORDS.get(parts[0])
    if len(parts) == 2 and parts[0] in ("twenty", "thirty", "forty") and _WORDS.get(parts[1], 99) < 10:
        return _WORDS[parts[0]] + _WORDS[parts[1]]
    return None
# The names are read by the Clerk or, since 2023, a Table Officer.
_CLERK = re.compile(r"(?:CLERK|TABLE\s+OFFICER|Table\s+Officer)(?:\s*\([^)]*\))?\s*:\s*")
_HON_MEMBERS = re.compile(r"(?:SOME|AN)\s+HON\.\s+MEMBERS?\s*:")
_TAG = re.compile(r"\b(?:(?:MR|MS|MRS)\.\s+|MADAM\s+)?(?:DEPUTY\s+)?(?:SPEAKER|CHAIR)(?:\s*\([^)]*\))?\s*:")
_LEAD = re.compile(r"(?:(?:Mr\.|Madam|Mister)\s+)?(?:Speaker|Chair)\s*,?\s*$", re.I)
_DECLARE = re.compile(r"I\s+declare\s+the\s+[\w\-]+(?:\s+as\s+amended)?\s+\w+(?:\s+and\s+said\s+bill\s+passed)?|"
                      r"The\s+[\w\s]{3,30}?\s+is\s+(?:carried|defeated|lost|negatived)", re.I)
_BILL_READ_AFTER = re.compile(r"\(Bill\s+(\d+)\)", re.I)
_STAGE_AFTER = re.compile(r"read\s+a\s+(first|second|third)\s+time", re.I)
_READ_BEFORE = re.compile(
    r"(?:Bill\s+(\d+)[^.]{0,250}?be\s+now\s+read\s+a\s+(first|second|third)\s+time|"
    r"(first|second|third)\s+reading\s+of\s+(?:a\s+bill,?\s+)?Bill\s+(\d+))", re.I)
_QUESTION = re.compile(r"(It is moved and seconded that\s.{10,700}?[.?])(?=\s|$)", re.I | re.S)
_FORMAL = re.compile(
    r"(?:On\s+motion,?\s+)?(?:a\s+bill,?\s*[“\"](?P<title>.{0,320}?)[”\"],?|Bill\s+(?P<num>\d+))\s+"
    r"read\s+an?\s+(?P<stage>first|fist|second|third)\s+time", re.I | re.S)


def hansard_text(html):
    body = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", html or "")
    return html_text(body)


_SENTENCE_END = re.compile(r"(?<![A-Z])(?<!Mr)(?<!Ms)(?<!Mrs)(?<!Dr)(?<!Hon)\.\s+(?=[A-Z])")


def _names(segment):
    """The Clerk's names, comma-separated. The list ends at the first full
    stop that closes a sentence ('Ms. Michael. On motion, that the Committee
    rise ...'), not at an initial's or an honorific's."""
    s = _LEAD.sub("", segment.strip()).strip()
    end = _SENTENCE_END.search(s)
    if end:
        s = s[:end.start()]
    s = s.rstrip(".").strip()
    if not s or re.fullmatch(r"(?i)nil|none", s):
        return []
    return [n.strip().rstrip(".").strip() for n in s.split(",") if n.strip().rstrip(".").strip()]


def _answered_calls(text):
    """The 'in favour ... please rise' calls the Clerk answers with names:
    the next speaker label after the call is the CLERK's, an aside of the
    Chair's in between allowed. 'All those in favour of the motion, please
    rise. Sorry.' (1 June 2016, the Speaker misspoke before the voice vote)
    is not one."""
    out = []
    for f in _FAVOUR.finditer(text or ""):
        pos, end = f.end(), f.end() + 400
        while True:
            clerk = _CLERK.search(text, pos, end)
            label = _SPEAKER_LABEL.search(text, pos, end)
            if label and _HON_MEMBERS.match(text, label.start()):
                # 'please rise. SOME HON. MEMBERS: Hear, hear! CLERK: ...'
                pos = label.end()
                continue
            if clerk and (not label or clerk.start() <= label.start()):
                out.append(f)
            break
    return out


_RESUME = re.compile("(?:CLERK|TABLE\\s+OFFICER)(?:\\s*\\([^)]*\\))?\\s*:\\s*[\u2013\u2014-]\\s*")


def _read_list(window, start, limit=None):
    """(names, end) of one list read from `start`. The list ends at the next
    speaker label or the Clerk's count. A list broken off with a dash and
    resumed after the interruption ('Jeff Dwyer \u2013 SOME HON. MEMBERS: Oh,
    oh! SPEAKER: Order, please! CLERK: \u2013 Pleaman Forsey, ...', 24 May
    2023) is followed to its end; one the Clerk starts again from the top
    ("Barry Petten \u2013 ... CHAIR: Okay, please continue. CLERK: Barry Petten,
    Helen Conway Ottenheimer, ...", 12 October 2022) is read from the restart."""
    limit = len(window) if limit is None else limit
    names, pos = [], start
    while True:
        stop = _SPEAKER_LABEL.search(window, pos, limit)
        count = TOTALS.search(window, pos, limit)
        end = min([x.start() for x in (stop, count) if x] or [limit])
        seg = window[pos:end]
        broken = seg.rstrip().endswith(("\u2013", "\u2014", "-"))
        names.extend(_names(seg.rstrip().rstrip("\u2013\u2014-")))
        if broken and stop and end == stop.start():
            again = _CLERK.search(window, stop.start(), min(limit, stop.start() + 600))
            if again:
                resumed = _RESUME.match(window, again.start())
                if resumed:                    # '– Pleaman Forsey, ...': carry on
                    pos = resumed.end()
                else:                          # the Clerk starts the list again
                    names, pos = [], again.end()   # (12 October 2022)
                continue
        return names, end


def parse_hansard(text):
    """(divisions, voices, problems) from one sitting's Hansard text.

    One division per answered 'please rise' call: the Clerk's two lists of
    names, then the Clerk's count. A division whose count is not read is
    still returned, with NULL totals and a problem, so the tally check makes
    it a gap instead of it vanishing (Committee of the Whole on 12 May and
    6 December 2016: names read, no count)."""
    text = text or ""
    divisions, problems = [], []
    calls = _answered_calls(text)
    counted = 0
    for k, fav in enumerate(calls):
        end = calls[k + 1].start() if k + 1 < len(calls) else min(len(text), fav.end() + 12000)
        window = text[fav.end():end]
        problem = None
        yea_names = nay_names = []
        ag = _AGAINST.search(window)
        c1 = _CLERK.search(window)
        nays_end = None
        count = TOTALS.search(window, c1.end()) if c1 else None
        if c1 and count and (not ag or ag.start() > count.start()):
            # No call for those against before the count: the House was
            # unanimous ('the ayes: 33; the nays: 0', 21 May 2025). Only a
            # count of no nays is accepted that way.
            yea_names, nays_end = _read_list(window, c1.end())
            if count_value(count.group(2)) != 0:
                problem = "no list of those against, yet the count gives nays"
        elif not ag or not c1 or c1.start() > ag.start():
            problem = "the Clerk's list of those in favour was not found"
        else:
            yea_names, _ = _read_list(window, c1.end(), ag.start())
            c2 = _CLERK.search(window, ag.end())
            if not c2 or c2.start() - ag.end() > 200:
                problem = "the Clerk's list of those against was not found"
            else:
                nay_names, nays_end = _read_list(window, c2.end())
        tot = TOTALS.search(window, nays_end) if nays_end is not None else None
        if tot and tot.start() - nays_end > 300:
            tot = None
        n_y = n_n = None
        if tot:
            counted += 1
            n_y, n_n = count_value(tot.group(1)), count_value(tot.group(2))
            if n_y is None or n_n is None:
                problem = problem or "the Clerk's count {0!r} could not be read".format(tot.group(0))
        elif not problem:
            problem = "no Clerk's count read after the names"
        before = text[max(0, fav.start() - 6000):fav.start()]
        a0 = fav.end() + (tot.end() if tot else (nays_end or 0))
        after = text[a0:a0 + 700]
        cut = re.search(r"I call from the Order Paper", after)
        if cut:
            after = after[:cut.start()]
        call = fav.group(0).lower()
        vote_on = ("subamendment" if re.search(r"sub-?amendment", call) else
                   "amendment" if "amendment" in call else "motion")
        bill = stage = None
        in_committee = bool(re.search(r"CHAIR(?:\s*\([^)]*\))?\s*:[^:]{0,80}$", before[-120:]))
        if in_committee:
            cites = re.findall(r"\(Bill\s+(\d+)\)", before)
            bill, stage = (cites[-1] if cites else None), "Committee of the Whole"
        else:
            if vote_on == "motion":
                b = _BILL_READ_AFTER.search(after)
                st = _STAGE_AFTER.search(after)
                if b and st:
                    bill, stage = b.group(1), st.group(1).title() + " Reading"
            if not bill:
                reads = list(_READ_BEFORE.finditer(before[-3500:]))
                if reads:
                    r = reads[-1]
                    bill = r.group(1) or r.group(4)
                    stage = (r.group(2) or r.group(3)).title() + " Reading"
            if not bill:
                stage = "Motion"
        q = list(_QUESTION.finditer(before[-5000:]))
        question = re.sub(r"\s+", " ", q[-1].group(1)) if q else re.sub(r"\s+", " ", before[-600:]).strip()
        dec = _DECLARE.search(after)
        divisions.append({
            "seq": len(divisions) + 1, "yeas": n_y, "nays": n_n,
            "yea_labels": yea_names, "nay_labels": nay_names, "question": question[-1500:],
            "result": re.sub(r"\s+", " ", dec.group(0)) if dec else None, "vote_on": vote_on,
            "stage": stage, "bill_number": bill, "problem": problem})
    stray = len(TOTALS.findall(text)) - counted
    if stray > 0:
        problems.append("{0} Clerk's count(s) with no division read before them".format(stray))
    voices, seen = [], set()
    divided = {(d["bill_number"], d["stage"]) for d in divisions if d["bill_number"]}
    for f in _FORMAL.finditer(text or ""):
        num = f.group("num")
        if not num:
            b = _BILL_READ_AFTER.search(text[f.end():f.end() + 260])
            num = b.group(1) if b else None
        if not num:
            continue
        stage = {"fist": "First"}.get(f.group("stage").lower(), f.group("stage").title()) + " Reading"
        if (num, stage) in divided or (num, stage) in seen:
            continue
        seen.add((num, stage))
        voices.append({"bill_number": num, "stage": stage,
                       "result": re.sub(r"\s+", " ", f.group(0))[:300]})
    return divisions, voices, problems


def resolve_division(raw, resolver, date, legislature):
    votes = []
    for position, labels in (("Yea", raw["yea_labels"]), ("Nay", raw["nay_labels"])):
        for k, label in enumerate(labels, 1):
            key, how = resolver.resolve(label, date, legislature)
            votes.append({"position": position, "ordinal": k, "raw_label": label, "member_key": key,
                          "how": how, "party_at_vote": None})
    ok, note = ps.tally({"Yea": raw["yeas"], "Nay": raw["nays"]}, votes)
    if raw.get("problem"):
        ok, note = False, "; ".join(x for x in (raw["problem"], note) if x)
    return votes, ok, note


def read_sitting(ctx, legislature, session, rec, resolver, wl):
    date, url = rec["date"], rec["url"]
    skey = ps.sitting_key(PROV, legislature, session, date, rec.get("part"))
    raw = ctx.text(url, "hansard-{0}{1}".format(date, rec.get("part") or ""), encoding="cp1252")
    if raw is None:
        return 0, 1
    if "</html>" not in raw[-4000:].lower():
        ctx.gap("{0}: {1}: truncated Hansard (no closing </html>)".format(skey, url))
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
        ctx.conn.commit()
        return 0, 1
    text = hansard_text(raw)
    divisions, voices, problems = parse_hansard(text)
    gaps = 0
    for p in problems:
        gaps += 1
        ctx.gap("{0}: {1}".format(skey, p))
    seq_prefix = "{0}.".format(rec["part"]) if rec.get("part") else ""
    for d in divisions:
        votes, ok, note = resolve_division(d, resolver, date, legislature)
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        inherit = pc.Result(b_areas, b_terms, b_tier) if b_areas else None
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["question"]], bill_key=bkey, inherit=inherit)
        seq = seq_prefix + str(d["seq"])
        dkey = ps.division_key(PROV, legislature, session, date, seq)
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": date, "seq": seq, "kind": "recorded", "question": d["question"],
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "abstentions": None, "source_url": url,
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": note, "votes": votes})
    for v in voices:
        bkey = ps.bill_key(PROV, legislature, session, v["bill_number"])
        areas, terms, tier = ps.bill_areas(ctx.conn, bkey)
        ps.store_division(ctx.conn, {
            "division_key": ps.division_key(PROV, legislature, session, date, "v{0}-{1}".format(
                v["bill_number"], STAGE_CODE[v["stage"]])),
            "prov": PROV, "legislature": legislature, "session": session, "date": date,
            "seq": "v", "kind": "voice", "bill_key": bkey, "stage": v["stage"],
            "result": v["result"], "source_url": url, "areas": areas, "matched_terms": terms,
            "tier": tier})
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions), voice=len(voices),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return len(divisions), gaps


def check_listing_stages(ctx, legislature, session, read_dates):
    misses = 0
    for key, stages in ctx.conn.execute(
            "SELECT bill_key, stages FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
            (PROV, legislature, session)).fetchall():
        for s in json.loads(stages or "[]"):
            if s.get("stage") not in ("Second Reading", "Third Reading") or s.get("date") not in read_dates:
                continue
            hit = ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? AND stage=?",
                (key, s["date"], s["stage"])).fetchone()[0]
            if not hit:
                misses += 1
                ctx.gap("{0}: the progress table dates {1} to {2}; that day's Hansard gave neither a "
                        "recorded division nor a formal record of it".format(key, s["stage"], s["date"]))
    return misses


def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    legislature, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    listing_url = HANSARD.format(legislature, sess)
    html = ctx.text(listing_url, "hansard-{0}-{1}".format(legislature, sess))
    all_records = list_records(html or "", listing_url)
    if html and not all_records:
        ctx.gap("nl Hansard {0}: no sittings parsed from the listing".format(session))
    records = [r for r in all_records if ctx.in_window(r["date"])]
    stats = {"records_listed": len(records)}
    if roster:
        stats["members"] = fetch_roster(ctx, legislature, {int(r["date"][:4]) for r in records})
    if bills:
        stats.update(fetch_bills(ctx, legislature, sess, ctx.tax, wl))
    if ctx.dry_run:
        return stats
    resolver = NameResolver(pn.Resolver.from_conn(ctx.conn, PROV))
    read = divs = gaps = 0
    read_dates = set()
    for rec in records:
        if not ctx.refresh and ps.sitting_done(ctx.conn, rec["url"]):
            read_dates.add(rec["date"])
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        n, g = read_sitting(ctx, legislature, sess, rec, resolver, wl)
        read += 1
        divs += n
        gaps += g
        status = ctx.conn.execute("SELECT status FROM prov_sittings WHERE record_url=?",
                                  (rec["url"],)).fetchone()
        if status and status[0] != "unreadable":
            read_dates.add(rec["date"])
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps,
                  "listing_misses": check_listing_stages(ctx, legislature, sess, read_dates) if bills else 0})
    ctx.conn.commit()
    return stats
