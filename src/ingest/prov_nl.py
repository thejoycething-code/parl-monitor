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
    A summary with no text (2024 is a scan) is BRIDGED (bridge_year) from
    the summaries either side and the Elections NL by-election reports in
    config/prov_record.yaml; anyone the bridge cannot account for gets no
    term, so their divisions fail the tally check instead of guessing.
    A readable year is DATED inside the year (date_terms) from the same
    by-election reports and the general election dates: Bernard Davis
    from 30 November 2015, Paul Davis to 2 November 2018 (7 October 2026,
    the 2010 backfill's tally gaps). 2009 and 2010 are scans and 2010 has
    no summary either side to bridge from: 2010 has no roster.
  * PARTY AT THE VOTE: dated for the CURRENT General Assembly only, from the
    House's History of the Standings and the members page (see
    "party at the vote" below). Earlier Assemblies have no official dated
    party record and their votes carry none.
  * LABEL ALIASES: a typo in Hansard's division list ("Lloyd Parrot", 19
    October 2022) is cleared only by a reviewed entry in
    config/prov_record.yaml, checked against the same day's Journal. The
    same file holds NL's other reviewed facts: an other surname (Joan Shea,
    'Ms Burke' in 2012), titles that tell two Bennetts or two Osbornes
    apart (Titled), a division's label settled from the Journal
    (hansard_labels) and a count the Clerk corrected (hansard_totals).
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
# A district name misprinted in a summary, keyed by its squashed form. Read
# against the other summaries and the Roll of Members, never inferred.
DISTRICT_CORRECTIONS = {
    # The 2022 and 2023 summaries print 'St. Barb - L'Anse aux Meadows'; the
    # 2025 summary, the 2024 scan and the 50th Assembly's Roll of Members
    # print St. Barbe. Without it Krista Lynn Howell could not be bridged
    # into 2024 (same district on both sides is the bridge's condition).
    "stbarblanseauxmeadows": "St. Barbe - L’Anse aux Meadows",
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
# Half days too ('Cathy Bennett  Windsor Lake  5.5  0', 2018).
_DIGITS = re.compile(r"^\s*(?:\d+(?:\.\d+)?|LOA|N\/A)\s*$")


def _is_header(fr):
    words = [_clean(f[2]) for f in fr]
    return "Member" in words and "District" in words


def _is_subheader(fr):
    """The heading's second line ('Absences  Absences'), which otherwise
    joins the district of the row above it ('Bonavista North Absences
    Absences', 2011)."""
    words = [w for f in fr for w in _clean(f[2]).split()]
    return bool(words) and all(w in ("Absences", "Approved", "Other") for w in words)


# A credential printed after the name ('Kennedy, Jerome' is printed 'Jerome
# Kennedy, Q.C.' and 'Darin King, Ph.D' in the 2012-2014 summaries): not a
# given name. Without this the comma made 'Jerome Kennedy' the surname, and
# 'Mr. Kennedy' and 'Mr. King' resolved to nobody in 2012-2014.
_CREDENTIAL = re.compile(r",?\s*(?:Q\.\s?C\.?|K\.\s?C\.?|Ph\.\s?D\.?|M\.\s?D\.?)\s*$")


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
            # The text above the heading is the summary's preamble, not
            # members ('period. The Summary of Members' Attendance includes
            # ...', 2017, which a stray digit had made a member).
            lines = lines[next(k for k, fr in enumerate(lines) if _is_header(fr)):]
        rows.extend(lines)
    if not found:
        return []
    edges = Counter(round(f[0]) for fr in rows for f in fr
                    if 100 <= f[0] <= 330 and any(_DIGITS.match(g[2]) for g in fr))
    if not edges:
        return []
    edge = edges.most_common(1)[0][0] - 2
    out = []
    held = None
    for fr in rows:
        if _is_header(fr) or _is_subheader(fr):
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
        if held and name and not nums and not district:
            # The row set the other way up: district and counts on one line,
            # the name on the next ('Grand Falls-Windsor - Green Bay' 3 0 /
            # 'Ray Hunter' / 'South', 2012).
            district, nums, held = held[0], held[1], None
        elif not name and district and nums:
            held = (district, nums)
            continue
        else:
            held = None
        if not name and district and out and not nums and out[-1].get("open"):
            out[-1]["district"] = _clean(out[-1]["district"] + " " + district)
            continue
        if out:
            out[-1].pop("open", None)
        if not name or re.search(r"\d", name) or not nums:
            continue
        name = _CREDENTIAL.sub("", re.sub(r"\s*-\s*", "-", name)).strip()
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
        r["district"] = DISTRICT_CORRECTIONS.get(pn.squash(r["district"]), r["district"])
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
            ctx.log("  nl roster: {0} current member(s) (General Assembly {1})".format(len(rows), legislature))
            _store_standings_party(ctx, legislature, rows)
        n += len(rows)
    else:
        ctx.log("  nl: party at the vote is dated only for the current General Assembly (the House's "
                "History of the Standings); General Assembly {0} has no official dated party record, "
                "so its votes carry none".format(legislature))
    if not years:
        return n
    listing = ctx.text(ATTENDANCE, "attendance")
    reports = attendance_reports(listing) if listing else {}
    record = pn.load_record(PROV)
    for year in sorted(years):
        if not ctx.refresh and ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source IN (?, ?)",
                (PROV, SOURCE.format(year), SOURCE.format(year) + "-bridged")).fetchone()[0]:
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
            got = _bridge(ctx, reports, year, url)
            n += got
            continue
        nxt = _attendance_rows(ctx, reports, year + 1)
        if nxt is None and _is_current_election_year(year, record):
            nxt = _current_members(ctx) or None
        members, notes = date_terms(rows, year, _attendance_rows(ctx, reports, year - 1), nxt,
                                    record.get("by_elections"), load_general_elections(record),
                                    _other_surnames(record))
        for note in notes:
            ctx.log("  nl roster {0}: {1}".format(year, note))
        if ctx.dry_run:
            n += len(members)
            continue
        _store_year(ctx, year, members, SOURCE.format(year))
        dated = sum(1 for m in members if (m["start"], m["end"]) != ("{0}-01-01".format(year), "{0}-12-31".format(year)))
        ctx.log("  nl roster {0}: {1} member(s) from the attendance summary, {2} dated inside the year".format(
            year, len(members), dated))
        n += len(members)
    return n


# Roster terms are stored under SOURCE ('summary-2012'); the first build
# stored them under 'attendance-2012', calendar-wide and with the summary's
# credentials read as names ('Darin King, Ph.D' became the member 'Ph.D Darin
# King'). A year whose terms are still under the old source is read again
# (the skip above looks only for the new one), and storing a year removes
# both.
SOURCE = "summary-{0}"


def _store_year(ctx, year, members, source):
    ctx.conn.execute("DELETE FROM prov_member_terms WHERE prov=? AND (source=? OR source=? OR source=? OR source=?)",
                     (PROV, "attendance-{0}".format(year), "attendance-{0}-bridged".format(year),
                      SOURCE.format(year), SOURCE.format(year) + "-bridged"))
    by_key = {}
    for m in members:
        by_key.setdefault(member_key(m["given"], m["surname"]), (m, []))[1].append({
            "legislature": None, "party": None, "riding": m["district"], "start": m["start"],
            "end": m["end"], "party_dated": 0})
    for key, (m, terms) in by_key.items():
        ps.upsert_member(ctx.conn, PROV, key, name=m["given"] + " " + m["surname"],
                         surname=m["surname"], given=m["given"])
        ps.replace_terms(ctx.conn, PROV, key, terms, source)
    drop_orphans(ctx.conn)
    ctx.conn.commit()
    return len(by_key)


def drop_orphans(conn):
    """Members no term, vote, speech or bill names any more (the old
    parser's 'Ph.D Darin King', 'Q.C. Jerome Kennedy' and the 2017
    preamble's 'period. The Summary of Members' Atte'). Returns how many."""
    return conn.execute(
        "DELETE FROM prov_members WHERE prov=? AND member_key NOT IN "
        "(SELECT member_key FROM prov_member_terms WHERE prov=?) "
        "AND member_key NOT IN (SELECT member_key FROM prov_votes WHERE member_key IS NOT NULL "
        "AND division_key LIKE 'nl-%') "
        "AND member_key NOT IN (SELECT member_key FROM prov_speeches WHERE prov=? AND member_key IS NOT NULL) "
        "AND member_key NOT IN (SELECT sponsor_key FROM prov_bills WHERE prov=? AND sponsor_key IS NOT NULL)",
        (PROV, PROV, PROV, PROV)).rowcount


# -- dating the summary's calendar-year terms -------------------------------
#
# A summary names everyone who sat in the year, so a term from it is the whole
# year. In a year with a general election or a by-election that over-states
# who could have voted on a day: in 2015 Paul Davis (Topsail) and Bernard
# Davis (elected 30 November) are both 'Mr. Davis' all year, and every
# division of January to June 2015 with 'Mr. Davis' in it was a tally gap.
# date_terms narrows a term ONLY from two official records:
#   * a by-election in config/prov_record.yaml `by_elections` (the Elections
#     NL report): the member who left sat to the vacancy, the member elected
#     from the day sworn in (or polling day where the report gives no
#     swearing-in);
#   * a general election in `general_elections` (the Elections NL report's
#     date), read against the summaries either side: a member absent from
#     the next year's summary sat to election day; one absent from the
#     previous year's summary, and elected at no by-election, from it.
# The summaries leave out members who resigned during the year (2013: Yvonne
# Jones, resigned 8 April; Jerome Kennedy, resigned 2 October), although they
# say they include them. Such a member, found in the previous year's summary
# for the district the by-election report names, is added to the year up to
# the vacancy. Nothing else is inferred: a member the records do not date
# keeps the calendar year.

def load_general_elections(record):
    """`general_elections:` -- [{date, source}], each read in the Elections NL
    general election report."""
    out = []
    for e in record.get("general_elections") or []:
        if not e.get("date") or not e.get("source"):
            raise ValueError("nl general_elections entry {0!r} lacks date or source".format(e))
        out.append(str(e["date"]))
    return sorted(out)


def _surname_key(r):
    return pn.fold(r.get("surname") or "").replace("-", " ")


def _surnames_of(r, other_surnames):
    """r's surname, and any reviewed other surname of the member it names
    (`other_surnames`: Joan Shea, 'Burke' in 2011)."""
    out = {_surname_key(r)}
    for extra in (other_surnames or {}).get(member_key(r.get("given"), r.get("surname")), []):
        out.add(pn.fold(extra).replace("-", " "))
    return out


def _person_in(r, rows, other_surnames=None, own=()):
    """The row of `rows` that is the same person as r: the same full name
    however split, or the same surname (hyphen and space alike, or a
    reviewed other surname of either) and the same given name; or, failing
    that, the same first initial when only one row of that surname has it in
    either summary (`own` is r's own): Kelvin and Kevin Parsons are both 'K'
    in 2011, so neither stands for the other, while 'Osborne, Tom' (2018)
    and 'Osborne, Thomas' (2019) are one."""
    whole = pn.squash((r.get("given") or "") + (r.get("surname") or ""))
    for x in rows:
        # the full name split differently: 'Gambin-Walsh, Sherry' (2019) and
        # 'Sherry Gambin Walsh' read given name first (2016-2018)
        if pn.squash((x.get("given") or "") + (x.get("surname") or "")) == whole:
            return x
    names = _surnames_of(r, other_surnames)
    same = [x for x in rows if _surnames_of(x, other_surnames) & names]
    exact = [x for x in same if pn.fold(x.get("given")) == pn.fold(r.get("given"))]
    if exact:
        return exact[0]
    ini = pn.initials_of(r.get("given"))[:1]
    if not ini:
        return None
    theirs = [x for x in same if pn.initials_of(x.get("given"))[:1] == ini]
    mine = [x for x in own if _surnames_of(x, other_surnames) & names and pn.initials_of(x.get("given"))[:1] == ini]
    return theirs[0] if len(theirs) == 1 and len(mine) <= 1 else None


def date_terms(rows, year, prev_rows, next_rows, by_elections, general_elections, other_surnames=None):
    """(members, notes): the year's summary rows with start and end dates.
    prev_rows / next_rows: the summaries either side (None when unreadable);
    next_rows may be the current members list for the current Assembly's
    election year. other_surnames: {member_key: [surname]} (reviewed)."""
    y0, y1 = "{0}-01-01".format(year), "{0}-12-31".format(year)
    out = [dict(r, start=y0, end=y1, how=[]) for r in rows]
    notes = []
    events = [e for e in by_elections or []
              if y0 <= str(e.get("left") or "") <= y1 or y0 <= str(e.get("sworn") or e.get("polling") or "") <= y1]
    fixed_start, fixed_end = set(), set()
    for e in events:
        left, sworn = str(e.get("left") or ""), str(e.get("sworn") or e.get("polling") or "")
        gone, new = e.get("vacated_by") or {}, e.get("elected") or {}
        if y0 <= left <= y1:
            hit = [m for m in out if _same_district(m["district"], e["district"]) and _same_person(m, gone)]
            if len(hit) == 1:
                hit[0]["end"] = left
                hit[0]["how"].append("left {0} ({1})".format(left, e.get("why_left") or "vacancy"))
                fixed_end.add(id(hit[0]))
            elif not hit:
                was = [r for r in prev_rows or [] if _same_district(r["district"], e["district"])
                       and _same_person(r, gone)]
                if len(was) == 1:
                    m = dict(was[0], year=year, start=y0, end=left,
                             how=["not in the {0} summary; in the {1} one, and left {2} ({3})".format(
                                 year, year - 1, left, e.get("why_left") or "vacancy")])
                    out.append(m)
                    fixed_end.add(id(m))
                    notes.append("{0} {1} ({2}) added to {3} up to {4}: the summary leaves out a member who "
                                 "left during the year".format(gone.get("given"), gone.get("surname"),
                                                               e["district"], year, left))
                else:
                    notes.append("{0} {1}, who left {2} on {3}, is in neither the {4} nor the {5} summary".format(
                        gone.get("given"), gone.get("surname"), e["district"], left, year, year - 1))
        if y0 <= sworn <= y1:
            hit = [m for m in out if _same_district(m["district"], e["district"]) and _same_person(m, new)]
            if len(hit) == 1:
                hit[0]["start"] = sworn
                hit[0]["how"].append("by-election {0}, sworn {1}".format(e.get("polling"), sworn))
                fixed_start.add(id(hit[0]))
    for ge in general_elections or []:
        if not (y0 <= ge <= y1):
            continue
        for m in out:
            if next_rows is not None and id(m) not in fixed_end and \
                    _person_in(m, next_rows, other_surnames, out) is None:
                m["end"] = min(m["end"], ge)
                m["how"].append("not in the {0} list: sat to the general election of {1}".format(year + 1, ge))
            if prev_rows is not None and id(m) not in fixed_start and \
                    _person_in(m, prev_rows, other_surnames, out) is None:
                m["start"] = max(m["start"], ge)
                m["how"].append("not in the {0} summary and elected at no by-election: from the general "
                                "election of {1}".format(year - 1, ge))
    for m in out:
        if m["start"] > m["end"]:
            notes.append("{0} {1}: the records give no day in {2} ({3}); kept for the whole year".format(
                m["given"], m["surname"], year, "; ".join(m["how"])))
            m["start"], m["end"] = y0, y1
        m["how"] = "; ".join(m["how"]) or "the {0} summary".format(year)
    return out, notes


def _other_surnames(record):
    out = {}
    for a in record.get("other_surnames") or []:
        out.setdefault(str(a["member"]), []).append(str(a["surname"]))
    return out


def _is_current_election_year(year, record):
    ges = load_general_elections(record)
    return bool(ges) and ges[-1][:4] == str(year)


def _current_members(ctx):
    cache = ctx.__dict__.setdefault("_nl_current", {})
    if "rows" not in cache:
        page = ctx.text(MEMBERS, "members")
        url = members_js_url(page) if page else None
        js = ctx.text(url, "members-js") if url else None
        cache["rows"] = [{"surname": r["surname"], "given": r["given"], "district": r["district"]}
                         for r in (parse_members_js(js) if js else [])]
    return cache["rows"]


# -- party at the vote: the House's History of the Standings -------------------
#
# The only official record that DATES a Newfoundland and Labrador member's
# party is the House's "History of the Standings" page, which covers the
# CURRENT General Assembly only: the parties returned at the general
# election, then every change with its date ("On September 14, 2026, it was
# announced MHA Keith Russell would sit as an Independent/Non-Affiliated
# Member."). With the members page (each member's party today) it dates
# everyone's party from the election to the day of reading:
#   * a member the page never names has had today's party since the election;
#   * a member it names has the new party from the change's date; the party
#     BEFORE the change is not printed, and is taken only when the election
#     counts leave exactly one answer (21 PC returned, 20 PC today, one
#     change: Russell was PC). Otherwise it is NULL;
#   * if the counts do not reconcile, or a sentence on the page is not
#     understood, no party is stored for the Assembly at all.
# Earlier Assemblies have no such page. Elections NL's reports give a label
# only on election day, and for the 50th Assembly they disagree with the
# Chief Electoral Officer's own later seat counts (docs/canada-provinces-
# scope.md), so their votes carry no party: NULL, never a guess.

STANDINGS = BASE + "/Members/HistoricalStandings.aspx"
STANDINGS_SOURCE = "party-standings"
_LONG_DATE = r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})"


def canon_party(name):
    """'Progressive Conservative Members' / 'PC' -> 'pc'; 'Independent/Non-affiliated' -> 'ind'."""
    f = pn.fold(name)
    if "conservative" in f or f in ("pc", "p.c."):
        return "pc"
    if "liberal" in f or f == "lib":
        return "lib"
    if "new democrat" in f or f == "ndp":
        return "ndp"
    if "independent" in f or "affiliated" in f or f in ("ind", "na"):
        return "ind"
    return f or None


def _iso(text):
    try:
        return datetime.datetime.strptime(re.sub(r"\s+", " ", text.strip()), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def parse_standings(html):
    """{'assembly', 'election', 'counts': {canon: n}, 'events': [{date, name, party}], 'unknown': [...]}"""
    body = re.sub(r"(?is)<(script|style|head|nav|header|footer)\b.*?</\1>", " ", html or "")
    m = re.search(r"<h1[^>]*>\s*History of the Standings in the (\d+)\w*\s+General Assembly\s*</h1>(.*?)"
                  r"(?:<footer|<!--\s*Footer|$)", body, re.S | re.I)
    out = {"assembly": None, "election": None, "counts": {}, "events": [], "unknown": []}
    if not m:
        return out
    out["assembly"] = int(m.group(1))
    text = html_text(m.group(2))
    for sentence in re.split(r"(?<=\.)\s+(?=[A-Z])", text):
        s = sentence.strip()
        if not s:
            continue
        e = re.match(r"After the General Election of " + _LONG_DATE + r", there were (.+?) returned to the House", s)
        if e:
            out["election"] = _iso(e.group(1))
            for n, party in re.findall(r"(\d+)\s+([A-Z][\w/\-]*(?:\s+[A-Z][\w/\-]*)*?)\s+Members?", e.group(2)):
                out["counts"][canon_party(party)] = out["counts"].get(canon_party(party), 0) + int(n)
            continue
        c = re.match(r"On " + _LONG_DATE + r", it was announced (?:that )?(?:MHA |the Member for [^,]+, )?"
                     r"(.+?) would (?:now )?sit as (?:an? )?(.+?)(?: Member)?\.$", s)
        if c:
            out["events"].append({"date": _iso(c.group(1)), "name": c.group(2).strip(), "party": c.group(3).strip()})
            continue
        if re.search(r"\b(?:sworn|affirmed|recount)", s, re.I) and not re.search(
                r"\b(?:resign|vacan|by-election|died|passed away|sit as|joined|left)\b", s, re.I):
            continue                     # who took a seat when: no party in it
        out["unknown"].append(s)
    return out


def standings_party_terms(members, standings, today):
    """({member_key: [term]}, problems). members: the members page's rows
    ({key, surname, given, party}); every term is party-only and dated."""
    problems = list("sentence not understood: {0!r}".format(u) for u in standings["unknown"])
    election, counts = standings["election"], dict(standings["counts"])
    if not election or not counts:
        problems.append("no election and counts read from the page")
    if sum(counts.values()) != len(members):
        problems.append("{0} returned at the election, {1} members today: a seat changed hands, which "
                        "this reading does not follow".format(sum(counts.values()), len(members)))
    by_event = {}
    for ev in standings["events"]:
        hits = [m for m in members if pn.fold(m["given"] + " " + m["surname"]) == pn.fold(ev["name"])
                or (pn.fold(ev["name"]).endswith(" " + pn.fold(m["surname"]))
                    and pn.initials_of(m["given"])[:1] == pn.fold(ev["name"])[:1])]
        if len(hits) != 1:
            problems.append("{0!r} ({1}) matches {2} current member(s)".format(ev["name"], ev["date"], len(hits)))
            continue
        by_event.setdefault(hits[0]["key"], []).append(ev)
    if problems:
        return {}, problems
    changed = {m["key"] for m in members if m["key"] in by_event}
    # The election counts, less the members who never changed, must leave
    # exactly one returned party per member who did.
    before = Counter(counts)
    before.subtract(Counter(canon_party(m["party"]) for m in members if m["key"] not in changed))
    if any(v < 0 for v in before.values()) or sum(before.values()) != len(changed):
        return {}, problems + ["the election counts {0} do not reconcile with today's parties and the "
                               "page's changes".format(dict(counts))]
    returned = sorted(+before)          # the parties the changers were returned under
    one_answer = len(returned) == 1 or len(changed) == 1
    terms = {}
    for m in members:
        party = m["party"]
        evs = sorted(by_event.get(m["key"], []), key=lambda e: e["date"])
        if not evs:
            terms[m["key"]] = [(election, today, party)]
            continue
        if canon_party(evs[-1]["party"]) != canon_party(party):
            problems.append("{0}: the page's last change says {1}, the members page says {2}; no party "
                            "stored for them".format(m["key"], evs[-1]["party"], party))
            continue
        spans = []
        for k, ev in enumerate(evs):
            end = evs[k + 1]["date"] if k + 1 < len(evs) else None
            last = (datetime.date.fromisoformat(end) - datetime.timedelta(days=1)).isoformat() if end else today
            spans.append((ev["date"], last, ev["party"] if end else party))
        if one_answer and len(evs) == 1:
            first = (datetime.date.fromisoformat(evs[0]["date"]) - datetime.timedelta(days=1)).isoformat()
            spans.insert(0, (election, first, _party_name(returned[0], members)))
        terms[m["key"]] = spans
    return terms, problems


def _party_name(canon, members):
    """The members page's own spelling of a party ('pc' -> 'Progressive Conservative')."""
    for m in members:
        if canon_party(m["party"]) == canon:
            return m["party"]
    return canon


def _store_standings_party(ctx, legislature, rows):
    html = ctx.text(STANDINGS, "standings")
    if not html:
        return
    st = parse_standings(html)
    if st["assembly"] != legislature:
        ctx.gap("nl: {0} describes General Assembly {1}, not {2}; no party at the vote".format(
            STANDINGS, st["assembly"], legislature))
        return
    terms, problems = standings_party_terms(rows, st, datetime.date.today().isoformat())
    for p in problems:
        ctx.gap("nl standings: {0}".format(p))
    if ctx.dry_run:
        return
    for r in rows:
        ps.replace_terms(ctx.conn, PROV, r["key"], [
            {"legislature": legislature, "party": party, "riding": None, "start": a, "end": b, "party_dated": 1}
            for a, b, party in terms.get(r["key"], [])], STANDINGS_SOURCE)
    ctx.conn.commit()
    ctx.log("  nl party: {0} of {1} current member(s) dated from the History of the Standings".format(
        len(terms), len(rows)))


def _same_person(a, b):
    """Two summary rows name the same person: the same surname (hyphen and
    space alike, accents folded) and the same first initial. The summaries
    print 'Dinn, James' (2023) and 'Dinn, Jim' (2025), 'Gambin-Walsh,
    Sheryl' and 'Sherry'; the two Dinns (James, Paul) and the two Parsons
    (Andrew, Pamela) differ by initial."""
    sa, sb = (pn.fold(x["surname"]).replace("-", " ") for x in (a, b))
    ga, gb = (pn.initials_of(x["given"])[:1] for x in (a, b))
    return sa == sb and ga and ga == gb


def _same_district(a, b):
    return pn.squash(a) == pn.squash(b)


def bridge_year(prev_rows, next_rows, year, by_elections):
    """(members, problems): the roster of a year whose own summary cannot be
    read, from the summaries either side of it and the official by-election
    record. Nothing else is assumed.

      * A member in BOTH summaries for the same district, where no vacancy
        or by-election in that district touches the year, sat all year.
      * Around a by-election (config/prov_record.yaml `by_elections`, read
        from the Elections NL reports): the member who left sat from 1
        January to the vacancy date; the member elected sat from the day
        they were sworn in to 31 December. Each must be found in the
        summary on their side, under that district.
      * Anyone in the earlier summary but not the later one, with no
        official record of leaving, gets NO term and is a problem (a gap):
        the year's divisions they voted in will then fail the tally check
        rather than be resolved on a guess.

    members: [{surname, given, district, start, end, how}]."""
    y0, y1 = "{0}-01-01".format(year), "{0}-12-31".format(year)
    events = [e for e in by_elections or []
              if str(e.get("left") or "9999") <= y1 and str(e.get("sworn") or e.get("polling") or "0000") >= y0]
    touched = {pn.squash(e["district"]): e for e in events}
    out, problems, used_prev = [], [], set()
    for e in events:
        d = e["district"]
        left, sworn = str(e.get("left") or ""), str(e.get("sworn") or e.get("polling") or "")
        gone = e.get("vacated_by") or {}
        prev = [k for k, r in enumerate(prev_rows) if _same_district(r["district"], d) and _same_person(r, gone)]
        if len(prev) == 1:
            used_prev.add(prev[0])
            if left >= y0:
                r = prev_rows[prev[0]]
                out.append(dict(r, start=y0, end=min(left, y1),
                                how="left {0} ({1}); {2}".format(left, e.get("why_left") or "vacancy", e.get("source"))))
        elif left >= y0:
            problems.append("{0} {1} ({2}), who left on {3}, is not in the {4} summary".format(
                gone.get("given"), gone.get("surname"), d, left, year - 1))
        new = e.get("elected") or {}
        nxt = [r for r in next_rows if _same_district(r["district"], d) and _same_person(r, new)]
        if len(nxt) == 1 and sworn <= y1:
            out.append(dict(nxt[0], start=max(sworn, y0), end=y1,
                            how="by-election {0}, sworn {1}; {2}".format(e.get("polling"), sworn, e.get("source"))))
        elif sworn <= y1:
            problems.append("{0} {1}, elected for {2} on {3}, is not in the {4} summary".format(
                new.get("given"), new.get("surname"), d, e.get("polling"), year + 1))
    for k, r in enumerate(prev_rows):
        if k in used_prev:
            continue
        later = [x for x in next_rows if _same_district(x["district"], r["district"]) and _same_person(x, r)]
        if pn.squash(r["district"]) in touched:
            problems.append("{0} {1} ({2}) sat in a district with a by-election in {3} but is not the "
                            "member it names".format(r["given"], r["surname"], r["district"], year))
        elif len(later) == 1:
            out.append(dict(r, start=y0, end=y1, how="in the {0} and {1} summaries, same district".format(
                year - 1, year + 1)))
        else:
            problems.append("{0} {1} ({2}) is in the {3} summary but not the {4} one, and no official record "
                            "says when they left: no {5} term".format(r["given"], r["surname"], r["district"],
                                                                     year - 1, year + 1, year))
    return out, problems


def _attendance_rows(ctx, reports, year):
    """A summary's rows (None when not listed or not readable), read once a run."""
    cache = ctx.__dict__.setdefault("_nl_attendance", {})
    if year in cache:
        return cache[year]
    url = reports.get(year)
    rows = None
    raw = ctx.bytes(url, "attendance-{0}".format(year)) if url else None
    if raw is not None:
        try:
            rows = parse_attendance(pdf_rows(raw), year) or None
        except Unreadable:
            rows = None
    cache[year] = rows
    return rows


def _bridge(ctx, reports, year, url):
    """A summary with no text (2024 is a scan): bridge the year, or say why not."""
    prev, nxt = _attendance_rows(ctx, reports, year - 1), _attendance_rows(ctx, reports, year + 1)
    if not prev or not nxt:
        ctx.gap("nl attendance {0}: no members parsed from {1} (a scan with no text), and the {2} and {3} "
                "summaries needed to bridge it are not both readable".format(year, url, year - 1, year + 1))
        return 0
    members, problems = bridge_year(prev, nxt, year, pn.load_record(PROV).get("by_elections"))
    for p in problems:
        ctx.gap("nl roster {0} (bridged): {1}".format(year, p))
    if ctx.dry_run or not members:
        return len(members)
    n = _store_year(ctx, year, members, SOURCE.format(year) + "-bridged")
    ctx.log("  nl roster {0}: the summary {1} is a scan with no text; {2} member(s) bridged from the {3} and "
            "{4} summaries and the by-election record ({5} problem(s))".format(
                year, url, n, year - 1, year + 1, len(problems)))
    return n


def make_resolver(conn):
    """The run's resolver: Newfoundland's NameResolver (with the reviewed
    other_surnames of config/prov_record.yaml: Joan Shea, 'Ms Burke' in 2012),
    the reviewed label aliases consulted after it finds nobody, and the
    reviewed titles after it finds two (Titled)."""
    return Titled(pn.Aliased(NameResolver(pn.Resolver.from_conn(conn, PROV).with_record(PROV)),
                             pn.load_aliases(PROV)))


_TITLE_CLASS = {"mr": "m", "mister": "m", "ms": "f", "mrs": "f", "miss": "f", "madam": "f"}


def _title_class(word):
    return _TITLE_CLASS.get(re.sub(r"[^a-z]", "", (word or "").lower())) if word else None


def load_titles(path=None):
    """`titles:` (nl) -- the title Hansard prints for a member, read where it
    joins the title to the member's full name ('Ms Cathy Bennett, Mr. Jim
    Bennett', 27 May 2015). Needs member, title, document, quoted,
    verified_against and why. Read by Titled, only for an AMBIGUOUS label
    (as New Brunswick's CaseExact reads its `titles:`)."""
    return pn._reviewed(PROV, "titles", ("member", "title", "document", "quoted", "verified_against", "why"),
                        path)


class Titled:
    """'Mr. Bennett' and 'Ms Bennett' in one 2014 list are Jim and Cathy
    Bennett; the shared resolver ignores titles, so both came back ambiguous.
    An AMBIGUOUS label is settled only when reviewed titles rule out every
    candidate but one (a candidate with no reviewed title is never ruled
    out). Still unique-or-nothing; the tally check runs on the result."""

    def __init__(self, inner, titles=None):
        self.inner = inner
        self.base = getattr(inner, "base", inner)
        self.titles = {str(a["member"]): _title_class(a["title"])
                       for a in (load_titles() if titles is None else titles)}

    def party_at(self, member_key, date, legislature=None):
        return self.inner.party_at(member_key, date, legislature)

    def term_for(self, member_key, date, legislature=None):
        return self.base.term_for(member_key, date, legislature)

    def resolve(self, raw, date, legislature=None, document=None):
        key, how = self.inner.resolve(raw, date, legislature, document=document)
        if key or not str(how).startswith("ambiguous:"):
            return key, how
        candidates = [k.strip() for k in str(how).partition(":")[2].split(",") if k.strip()]
        cls = _title_class((raw or "").split()[0] if (raw or "").split() else None)
        if cls and candidates:
            left = [k for k in candidates if self.titles.get(k, cls) == cls]
            if len(left) == 1 and len(left) < len(candidates):
                return left[0], "title (reviewed, config/prov_record.yaml; {0})".format(how)
        return key, how


class NameResolver:
    """prov_names.Resolver with Newfoundland's two allowances: hyphen equals
    space in a surname, and a full name that does not resolve is retried as
    initial plus surname (still unique-or-nothing)."""

    def __init__(self, resolver):
        members = {k: dict(m, surname=(m.get("surname") or "").replace("-", " "))
                   for k, m in resolver.members.items()}
        self.r = pn.Resolver(members, resolver.terms)
        self.r.other_surnames = {k: [x.replace("-", " ") for x in v]
                                 for k, v in getattr(resolver, "other_surnames", {}).items()}
        self.r.riding_aliases = dict(getattr(resolver, "riding_aliases", {}))

    def party_at(self, key, date, legislature=None):
        return self.r.party_at(key, date, legislature)

    def term_for(self, key, date, legislature=None):
        return self.r.term_for(key, date, legislature)

    def resolve(self, raw, date, legislature=None, document=None):
        # 'Ms. Gambin- Walsh' (3 May 2017) and "Loyola O' Driscoll" (12 May
        # 2022): a space the record set inside one name.
        label = re.sub(r"\s*-\s*", "-", raw or "")
        label = re.sub(r"\b(O|D|Mc|Mac)['\u2019]\s+(?=[A-Z])", r"\1'", label)
        label = re.sub(r"(\w)-(\w)", r"\1 \2", label)
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
_Q = "['‘’\"]?"
# The Clerk's count: 'the ayes: 21; the nays: 14', 'the ayes four, the nays
# thirty-three' (2010), "the 'ayes' thirty-one; the 'nays' fourteen" and 'the
# ayes; forty; the nays: three' (3 June 2014).
TOTALS = re.compile(r"(?:the\s+)?" + _Q + r"ayes" + _Q + r"[:;,]?\s*" + _NUM + r"\s*[;,.]?\s*(?:and\s+)?the\s+" +
                    _Q + r"nays" + _Q + r"[:;,]?\s*" + _NUM, re.I)
# 'Mr. Speaker, it is unanimous, thirty-nine ayes.' (27 May 2015): no nays.
# 'it is unanimous: the ayes thirty-four' (9 April 2014).
# 'The ayes: 31; there are no nays.' (1 June 2022).
UNANIMOUS = re.compile(r"(?:it\s+is\s+)?unanimous[,:]?\s+(?:(?:the\s+)?" + _Q + r"ayes" + _Q + r"[:;,]?\s*" + _NUM +
                       r"|" + _NUM + r"\s+ayes\b)|(?:the\s+)?ayes[:;,]?\s*" + _NUM +
                       r"\s*[;,.]?\s*there\s+(?:are|were)\s+no\s+nays", re.I)
# A Speaker's call for one side's names. 'All those in favour of the motion,
# please rise' and 'Those against the motion, please rise' (2016 on); 'All
# those in favour of the motion as put forward by the hon. the Member for the
# District of Burgeo & La Poile, please stand' (2010); 'All those in favour
# of the motion?' with no 'please rise' (14 March 2012); 'All of those
# against the motion' (14 June 2012); and 'All those for the motion, please
# rise', the Nays called FIRST (27 November 2013); 'all those Members against
# the motion' (17 April 2019), 'in favor' (5 April 2017) and 'All those not
# in favour or against the resolution' (30 May 2022); 'All in favour of the
# motion, please stand' and 'All opposed?' (27 October 2011); 'All those in
# support of the motion' (2 April 2014); 'All those please signify by
# standing' for the Ayes (20 March 2019). The words after the side
# do not matter: a call is a division call only when the Clerk answers it
# with names (_answer).
_CALL = re.compile(r"\b(?:All\s+(?:of\s+)?)?those\s+(?:Members\s+)?"
                   r"(?:(?P<ag>not\s+in\s+favou?r(?:\s+or\s+against)?|against|opposed)|"
                   r"(?P<fav>in\s+favou?r|in\s+support|please\s+signify\s+by\s+standing))\b|"
                   r"\bAll\s+(?:of\s+)?those\s+(?P<for>for)\b|"
                   r"\bAll\s+(?:(?P<fav2>in\s+favou?r)|(?P<ag2>opposed|against))\b", re.I)
# What the chair may say between a call and the Clerk, or inside a list,
# without ending it: 'Order, please!', 'The Clerk is calling the names.'
# (2 April 2014), 'Okay, please continue.' (12 October 2022).
_INTERJECTION = re.compile(r"(?i)^\s*(?:(?:order,?\s+please|order|okay,?\s+please\s+continue|please\s+continue)"
                           r"\s*[.!]?\s*|the\s+clerk\s+is\s+calling\s+the\s+names\s*\.?\s*)+$")
# The Clerk reading something other than names after a call.
_NOT_NAMES = re.compile(r"\s*(?:A\s+bill|An\s+Act|Bill\s+\d|Clauses?\b|Be\s+it\s+enacted|Motion\b|Title\b|"
                        r"(?:The\s+)?Schedule|Subheads?\b|Heads?\b|The\s+total|WHEREAS|Resolution\b|That\b|[\"\u201c]|"
                        r"(?:The\s+)?(?:first|second|third)\s+reading)", re.I)
_RISE = re.compile(r"please\s+(?:rise|stand)|signify\s+by\s+standing", re.I)
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
# The formal record line. Also 'read a third, ordered passed' (14 May and 14
# November 2013, 28 October 2020), 'read third time' (29 May 2014) and 'On
# motion, Bill 26, as amended, read a second time' (12 March 2020).
_FORMAL = re.compile(
    r"(?:On\s+motion,?\s+)?(?:a\s+bill,?\s*[“\"](?P<title>.{0,320}?)[”\"],?|"
    r"Bill\s+(?P<num>\d+)(?:,\s*as\s+amended,?)?)\s+"
    r"read\s+(?:an?\s+|the\s+)?(?P<stage>first|fist|second|third)(?:\s+time\b|(?=,\s*ordered))", re.I | re.S)
# The Speaker's own words after the Clerk reads the bill's title, where the
# formal line names no bill: 'CLERK: A bill, An Act To Amend The Canada-
# Newfoundland And Labrador Atlantic Accord Implementation Newfoundland And
# Labrador Act. (Bill 1) MR. SPEAKER: This bill has now been read a second
# time.' (7 May 2013), 'Bill 68 has now been read a third time' (7 March 2017).
_SPEAKER_READ = re.compile(
    r"\(Bill\s+(?P<num>\d+)\)\.?\s*(?:(?:MR\.|MADAM)\s+)?SPEAKER(?:\s*\([^)]*\))?\s*:\s*"
    r"(?:(?:This|The)\s+bill|Bill\s+(?P<num2>\d+))\s+(?:has\s+(?:now\s+)?been|is\s+now)\s+(?:read\s+)?(?:a|the)\s+"
    r"(?P<stage>second|third)\s+time", re.I)
# The Clerk naming the stage: 'CLERK: The second reading of Bill 23.' (5 June
# 2014, whose formal line then prints 'Bill 2').
_CLERK_READ = re.compile(r"CLERK(?:\s*\([^)]*\))?\s*:\s*(?:The\s+)?(?P<stage>second|third)\s+reading\s+of\s+"
                         r"Bill\s+(?P<num>\d+)\.", re.I)
# The question put on a named bill, carried, and the Clerk reading that
# bill's title, with no formal line after it: 'that Bill 10 be now read a
# second time ... The motion is carried. CLERK: A bill, An Act To Amend The
# Revenue Administration Act. (Bill 10) MR. SPEAKER: The hon. the Government
# House Leader.' (22 June 2010; 12 March 2025, Bill 90).
_PUT = re.compile(r"that\s+Bill\s+(?P<num>\d+)(?:,[^.]{0,300}?,)?\s+be\s+now\s+read\s+a\s+(?P<stage>second|third)\s+time",
                  re.I)
_CARRIED_READ = re.compile(r"\bcarried\.\s+CLERK(?:\s*\([^)]*\))?\s*:\s*(?:A\s+bill,?\s*)?[^()]{0,300}?"
                           r"\(Bill\s+(?P<num>\d+)\)", re.I)
# What the Clerk read just before a formal line: '(Bill 6) On motion, Bill 14
# read a second time' (30 April 2018) is the record contradicting itself.
_JUST_READ = re.compile(r"(?:\(Bill\s+(\d+)\)\.?|reading\s+of\s+Bill\s+(\d+)\.)\s*$", re.I)


def hansard_text(html):
    body = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", html or "")
    return html_text(body)


# Not before an honorific: 'Mr. Byrne. Ms. Dempster, ...' (9 June 2020) is a
# full stop typed for a comma inside the list.
_SENTENCE_END = re.compile(r"(?<![A-Z])(?<!Mr)(?<!Ms)(?<!Mrs)(?<!Dr)(?<!Hon)\.\s+(?=[A-Z])"
                           r"(?!(?:Mr|Ms|Mrs|Dr|Hon|Premier)\b\.?\s+(?!Speaker|Chair))")


def _names(segment):
    """The Clerk's names, comma-separated. The list ends at the first full
    stop that closes a sentence ('Ms. Michael. On motion, that the Committee
    rise ...'), not at an initial's or an honorific's."""
    s = _LEAD.sub("", segment.strip()).strip()
    end = _SENTENCE_END.search(s)
    if end:
        s = s[:end.start()]
    s = s.rstrip(".…").strip()
    if not s or re.fullmatch(r"(?i)nil|none", s):
        return []
    # 'Scott Reid, Lucy Stoyles and Perry Trimper' (2 May 2024): the last two
    # names joined by 'and'; 'Mr. Dinn, and Mr. Russell' (3 June 2014); 'Ms.
    # Michael; Ms. Rogers' (6 March 2018); 'Mr. Byrne. Ms. Dempster' (9 June
    # 2020). No member's name contains the word.
    parts = [p for n in re.split(r"[,;]|(?<=[a-z])\.\s+(?=(?:Mr|Ms|Mrs|Dr|Hon|Premier)\b)", s)
             for p in re.split(r"(?:^|\s+)and\s+", n.strip())]
    return [n.strip().rstrip(".…").strip() for n in parts if n.strip().rstrip(".…").strip()]


def _said(text, label, end):
    """What a speaker label says, up to the next label (or `end`)."""
    nxt = _SPEAKER_LABEL.search(text, label.end(), end)
    return text[label.end():nxt.start() if nxt else end]


def _next_clerk(text, pos, end, anyone=False):
    """The next CLERK (or Table Officer) label from `pos`, passing over the
    members' interjections ('SOME HON. MEMBERS: Hear, hear!') and the
    chair's 'Order, please!' (30 March 2011, 2 April 2014); with `anyone`,
    over any label at all. None when someone else speaks first, or a count
    or a new call comes first."""
    while True:
        label = _SPEAKER_LABEL.search(text, pos, end)
        clerk = _CLERK.search(text, pos, end)
        if clerk and (not label or clerk.start() <= label.start()):
            if _count(text, pos, clerk.start()) or _CALL.search(text, pos, clerk.start()):
                return None
            return clerk
        if not label:
            return None
        said = _said(text, label, end)
        if anyone or _HON_MEMBERS.match(text, label.start()) or (
                _TAG.match(text, label.start()) and _INTERJECTION.match(said)):
            pos = label.end()
            continue
        return None


def _answer(text, call):
    """The Clerk's label answering a call. A call that asks members to rise
    ('please rise', 'please stand') is answered by the next Clerk's label
    within 400 characters, whoever speaks between ('All those in favour,
    please rise. MS. COADY: Of the sub-amendment? MR. SPEAKER: Of the
    sub-amendment, yes. CLERK (Barnes): ...', 5 December 2019). Any other
    call only by a Clerk who answers it straight away or after interjections
    ('All those in favour of the motion? CLERK: Mr. Kennedy, ...', 14 March
    2012; 'All those in favour? SOME HON. MEMBERS: Oh, oh! CHAIR: Order,
    please! CLERK (Barnes): ...', 15 September 2020). Never a voice call: "All
    those against, 'nay.' Carried. On motion, subhead 1.1.01 carried. CLERK:
    Office of the Executive Council, ..." (12 May 2016), or one the members
    answer 'Aye'. 'All those in favour of the motion, please rise. Sorry.'
    (1 June 2016, the Speaker misspoke before the voice vote) is answered by
    no Clerk before the next call, so it is not a division either."""
    end = min(len(text), call.end() + 400)
    label = _SPEAKER_LABEL.search(text, call.end(), end)
    own = text[call.end():label.start() if label else end]
    rise = bool(_RISE.search(own))
    clerk = _next_clerk(text, call.end(), end, anyone=rise)
    if not clerk or _NOT_NAMES.match(text, clerk.end()):
        return None
    if rise:
        return clerk
    between = text[call.end():clerk.start()]
    if len(own) > 100 or re.search(r"(?i)\b(?:carried|on\s+motion|defeated)\b", between) or \
            re.search(r"(?i)MEMBERS?\s*:\s*['\u2018\u2019]?\s*(?:aye|nay)\b", between):
        return None
    return clerk


def _count(text, start, end):
    """(match, ayes, nays) of the first Clerk's count in text[start:end], or None."""
    hits = [m for m in (TOTALS.search(text, start, end), UNANIMOUS.search(text, start, end)) if m]
    if not hits:
        return None
    m = min(hits, key=lambda x: x.start())
    if m.re is UNANIMOUS:
        return m, count_value(m.group(1) or m.group(2) or m.group(3)), 0
    return m, count_value(m.group(1)), count_value(m.group(2))


def _all_counts(text):
    out, pos = [], 0
    while True:
        c = _count(text, pos, len(text))
        if not c:
            return out
        out.append(c)
        pos = c[0].end()


_RESUME = re.compile("(?:CLERK|TABLE\\s+OFFICER)(?:\\s*\\([^)]*\\))?\\s*:\\s*[–—-]\\s*")
_DASHES_END = ("–", "—", "-")


def _read_list(window, start, limit=None):
    """(names, end) of one list read from `start`. The list ends at the next
    speaker label or the Clerk's count, unless the Clerk takes it up again
    after an interruption:
      * broken off with a dash and resumed ('Jeff Dwyer – SOME HON. MEMBERS:
        Oh, oh! SPEAKER: Order, please! CLERK: – Pleaman Forsey, ...', 24 May
        2023; 'Ms Burke – SOME HON. MEMBERS: Hear, hear! CLERK: Mr. King,
        ...', 27 March 2012), followed to its end;
      * stopped at a full stop and resumed after the chair's 'Order, please!'
        ('Mr. Dinn. SOME HON. MEMBERS: Oh, oh! MR. SPEAKER: Order, please!
        CLERK: Mr. Davis, ...', 23 June 2010), followed to its end; one broken
        off with an ellipsis ('Mr. Harding\u2026 SOME HON. MEMBERS: Oh, oh! MR.
        SPEAKER: Order, please! I ask the hon. members for their
        co-operation ... CLERK: Mr. Dalley, ...', 20 April 2011) as a dash;
      * started again from the top ("Barry Petten – ... CHAIR: Okay, please
        continue. CLERK: Barry Petten, Helen Conway Ottenheimer, ...", 12
        October 2022): read from the restart. A list is started again when
        the Clerk's first name after the interruption is the list's first.
    A count or a new call between the two ends the list there."""
    limit = len(window) if limit is None else limit
    stop = _SPEAKER_LABEL.search(window, start, limit)
    count = _count(window, start, limit)
    end = min([x for x in (stop.start() if stop else None, count[0].start() if count else None)
               if x is not None] or [limit])
    seg = window[start:end]
    broken = seg.rstrip().endswith(_DASHES_END + ("\u2026", "..."))
    names = _names(seg.rstrip().rstrip("".join(_DASHES_END)))
    if not (stop and end == stop.start()):
        return names, end
    again = _next_clerk(window, stop.start(), min(limit, stop.start() + 600), anyone=broken)
    if not again:
        return names, end
    resumed = _RESUME.match(window, again.start())
    more, more_end = _read_list(window, resumed.end() if resumed else again.end(), limit)
    if not more:
        return names, more_end            # the Clerk went on to read the count
    if names and pn.fold(more[0]) == pn.fold(names[0]):
        return more, more_end             # started again from the top
    return names + more, more_end


def _calls(text):
    """[(call, side, clerk)] for every call the Clerk answers with names;
    side is 'Yea' or 'Nay'. Two calls answered by the same label keep the
    later one."""
    out = []
    for m in _CALL.finditer(text or ""):
        clerk = _answer(text, m)
        if not clerk:
            continue
        side = "Nay" if (m.group("ag") or m.group("ag2")) else "Yea"
        if out and out[-1][2].start() == clerk.start():
            out.pop()
        out.append((m, side, clerk))
    return out


def parse_hansard(text):
    """(divisions, voices, problems) from one sitting's Hansard text.

    One division per pair of answered calls (the Ayes and the Nays, either
    first: 27 November 2013 calls the Nays first), or one call alone when
    the House was unanimous; then the Clerk's count. A division whose count
    is not read is still returned, with NULL totals and a problem, so the
    tally check makes it a gap instead of it vanishing (Committee of the
    Whole on 12 May and 6 December 2016: names read, no count)."""
    text = text or ""
    divisions, problems = [], []
    calls = _calls(text)
    counted = 0
    k = 0
    while k < len(calls):
        first = calls[k]
        horizon = lambda j: calls[j][0].start() if j < len(calls) else min(len(text), first[0].end() + 12000)  # noqa: E731
        lists = {"Yea": [], "Nay": []}
        heard = {first[1]}
        problem = None
        second = calls[k + 1] if k + 1 < len(calls) else None
        if second and second[1] != first[1] and not _count(text, first[2].end(), second[0].start()):
            lists[first[1]], _ = _read_list(text, first[2].end(), second[0].start())
            lists[second[1]], list_end = _read_list(text, second[2].end(), horizon(k + 2))
            heard.add(second[1])
            k += 2
        else:
            lists[first[1]], list_end = _read_list(text, first[2].end(), horizon(k + 1))
            k += 1
        count = _count(text, list_end, horizon(k))
        late = None
        if count and count[0].start() - list_end > 300:
            # A count read after an interruption ('Now I ask for a report from
            # the Clerk. CLERK: Mr. Speaker, the ayes 32, the nays zero', 7
            # November 2017, after a call for those against that no one
            # answered): taken only before the next answered call, and
            # within 3,000 characters.
            if count[0].start() - list_end <= 3000:
                late = "the Clerk's count was read {0} characters after the names".format(count[0].start() - list_end)
            else:
                count = None
        n_y = n_n = None
        if count:
            counted += 1
            tot, n_y, n_n = count
            if n_y is None or n_n is None:
                problem = "the Clerk's count {0!r} could not be read".format(tot.group(0))
            elif len(heard) == 1:
                # No call answered for the other side before the count: the
                # House was unanimous ('the ayes: 33; the nays: 0', 21 May
                # 2025). Only a count of none on that side is accepted so.
                other = n_n if "Yea" in heard else n_y
                if other != 0:
                    problem = "no list of those {0}, yet the count gives {1}".format(
                        "against" if "Yea" in heard else "in favour", "nays" if "Yea" in heard else "ayes")
        else:
            problem = "no Clerk's count read after the names"
            tot = None
        call0 = first[0]
        before = text[max(0, call0.start() - 6000):call0.start()]
        a0 = tot.end() if tot else list_end
        after = text[a0:a0 + 700]
        cut = re.search(r"I call from the Order Paper", after)
        if cut:
            after = after[:cut.start()]
        yea_call = first if first[1] == "Yea" else (calls[k - 1] if len(heard) == 2 else first)
        call = text[yea_call[0].start():yea_call[2].start()][:300].lower()
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
            "yea_labels": lists["Yea"], "nay_labels": lists["Nay"], "question": question[-1500:],
            "result": re.sub(r"\s+", " ", dec.group(0)) if dec else None, "vote_on": vote_on,
            "stage": stage, "bill_number": bill, "problem": problem, "count_note": late,
            "count_at": tot.start() if tot else None})
    # The Speaker repeating the Clerk's count straight after ('The ayes: 8;
    # the nays: 20. MR. SPEAKER: The ayes: 8, and the nays: 20', 25 October
    # 2018) is not another count.
    used = {d["count_at"] for d in divisions if d["count_at"] is not None}
    every = _all_counts(text)
    repeats = sum(1 for a, b in zip(every, every[1:]) if a[0].start() in used and b[0].start() not in used
                  and b[0].start() - a[0].end() < 120 and (a[1], a[2]) == (b[1], b[2]))
    stray = len(every) - counted - repeats
    if stray > 0:
        problems.append("{0} Clerk's count(s) with no division read before them".format(stray))
    voices, seen = [], set()
    divided = {(d["bill_number"], d["stage"]) for d in divisions if d["bill_number"]}
    conflicts = []
    for f in _FORMAL.finditer(text or ""):
        num = f.group("num")
        if num:
            before = _JUST_READ.search(text, max(0, f.start() - 80), f.start())
            read = before and (before.group(1) or before.group(2))
            if read and read != num:
                # Nothing is recorded from a line that contradicts the Clerk
                # just before it; the bill the Clerk read must be recorded
                # by its own words (the Speaker's, the question put), or it
                # is a gap below.
                conflicts.append((read, num, f))
                continue
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
    for f in _PUT.finditer(text or ""):
        after = text[f.end():f.end() + 2500]
        c = _CARRIED_READ.search(after)
        if not c or c.group("num") != f.group("num") or re.search(r"(?i)defeated|lost|negatived", after[:c.start()]) \
                or _PUT.search(after, 0, c.start()):
            continue
        num, stage = f.group("num"), f.group("stage").title() + " Reading"
        if (num, stage) in divided or (num, stage) in seen:
            continue
        seen.add((num, stage))
        voices.append({"bill_number": num, "stage": stage,
                       "result": re.sub(r"\s+", " ", after[c.start():c.end()])[:300]})
    for f in list(_SPEAKER_READ.finditer(text or "")) + list(_CLERK_READ.finditer(text or "")):
        num = f.group("num")
        if f.re is _SPEAKER_READ and f.group("num2") and f.group("num2") != num:
            continue
        stage = f.group("stage").title() + " Reading"
        if (num, stage) in divided or (num, stage) in seen:
            continue
        seen.add((num, stage))
        voices.append({"bill_number": num, "stage": stage, "result": re.sub(r"\s+", " ", f.group(0))[:300]})
    for read, num, f in conflicts:
        stage = {"fist": "First"}.get(f.group("stage").lower(), f.group("stage").title()) + " Reading"
        line = re.sub(r"\s+", " ", f.group(0))[:80]
        hit = next((v for v in voices if (v["bill_number"], v["stage"]) == (read, stage)), None)
        if hit:
            hit["result"] = (hit["result"] + " (the formal line prints {0!r})".format(line))[:400]
        elif stage != "First Reading" and (read, stage) not in divided:
            problems.append("the formal record names Bill {0} just after the Clerk reads Bill {1} ({2!r}): "
                            "neither is recorded from it".format(num, read, line))
    return divisions, voices, problems


def apply_reviewed(d, reviewed, division_key):
    """(division, notes): the division-scoped reviewed facts of
    config/prov_record.yaml (pn.ReviewedDivisions) applied -- a count the
    Clerk read again and corrected (`hansard_totals` with `replaces:`, 14
    June and 12 December 2012), or a bill the record misnumbers. Every
    applied or refused fact is a note."""
    if reviewed is None:
        return d, []
    d, notes = dict(d), []
    for position, field in (("Yea", "yeas"), ("Nay", "nays")):
        value, note = reviewed.total(division_key, position, d[field])
        if note:
            notes.append(note)
        d[field] = value
    if d.get("bill_number"):
        number, note = reviewed.bill(division_key, d["bill_number"])
        if note:
            notes.append(note)
        d["bill_number"] = number
    return d, notes


def resolve_division(raw, resolver, date, legislature, document=None, reviewed=None, division_key=None):
    votes = []
    for position, labels in (("Yea", raw["yea_labels"]), ("Nay", raw["nay_labels"])):
        for k, label in enumerate(labels, 1):
            key, how = resolver.resolve(label, date, legislature, document=document)
            votes.append({"position": position, "ordinal": k, "raw_label": label, "member_key": key,
                          "how": how,
                          "party_at_vote": resolver.party_at(key, date, legislature) if key else None})
    notes = []
    if reviewed is not None and division_key:
        notes = reviewed.settle(division_key, votes, resolver, date, legislature)
    ok, note = ps.tally({"Yea": raw["yeas"], "Nay": raw["nays"]}, votes)
    if raw.get("problem"):
        ok = False
    note = "; ".join(x for x in [raw.get("problem")] + notes + [note] if x) or None
    return votes, ok, note


def clear_sitting(conn, url, date):
    """Delete what an earlier read stored from this Hansard file: a re-read
    replaces it (the first parser found divisions the second does not, and
    numbers them differently)."""
    keys = [r[0] for r in conn.execute(
        "SELECT division_key FROM prov_divisions WHERE prov=? AND source_url=? AND date=?", (PROV, url, date))]
    for k in keys:
        conn.execute("DELETE FROM prov_votes WHERE division_key=?", (k,))
        conn.execute("DELETE FROM prov_divisions WHERE division_key=?", (k,))
    return len(keys)


_STRAY = re.compile(r"^(\d+) Clerk's count\(s\) with no division read before them$")


def _recounts(reviewed, text, keys):
    """Counts the record reads again, accounted for by a reviewed total
    whose quoted words are in this Hansard: the Clerk's corrected count is
    not a division of its own."""
    flat = re.sub(r"\s+", " ", text or "")
    n = 0
    for k in keys:
        for a in (reviewed.facts(k).get("hansard_totals", []) if reviewed else []):
            if a.get("replaces") is not None and " ".join(str(a["quoted"]).split()) in flat:
                n += 1
    return n


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
    reviewed = getattr(ctx, "nl_reviewed", None)
    seq_prefix = "{0}.".format(rec["part"]) if rec.get("part") else ""
    keys = [ps.division_key(PROV, legislature, session, date, seq_prefix + str(d["seq"])) for d in divisions]
    gaps = 0
    for p in problems:
        m = _STRAY.match(p)
        if m:
            left = int(m.group(1)) - _recounts(reviewed, text, keys)
            if left <= 0:
                continue
            p = "{0} Clerk's count(s) with no division read before them".format(left)
        gaps += 1
        ctx.gap("{0}: {1}".format(skey, p))
    clear_sitting(ctx.conn, url, date)
    for d in divisions:
        dkey = ps.division_key(PROV, legislature, session, date, seq_prefix + str(d["seq"]))
        d, rnotes = apply_reviewed(d, reviewed, dkey)
        votes, ok, note = resolve_division(d, resolver, date, legislature, document=url, reviewed=reviewed,
                                           division_key=dkey)
        note = "; ".join(x for x in rnotes + [d.get("count_note"), note] if x) or None
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        inherit = pc.Result(b_areas, b_terms, b_tier) if b_areas else None
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["question"]], bill_key=bkey, inherit=inherit)
        seq = seq_prefix + str(d["seq"])
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


# Every sitting stored 'ok' by a parser older than this date is read once
# more. The 2010 backfill (CI run 37044556156, 2 October 2026) stored 710
# sittings 'ok'; the parser since finds divisions and voice readings that one
# could not see at all (a call worded 'All those in support', a count written
# 'it is unanimous, thirty-nine ayes', 'read a third, ordered passed'), so no
# gap points at the days that need it, and the roster fixes change who a
# label resolves to. The repair is by date, as New Brunswick's was.
REREAD_BEFORE = "2026-10-08"


def owe_stale(ctx, records):
    """Make OWED every listed sitting stored 'ok' before REREAD_BEFORE. Returns how many."""
    owed = 0
    for rec in records:
        owed += ctx.conn.execute(
            "UPDATE prov_sittings SET status='owed' WHERE prov=? AND record_url=? AND status='ok' AND read_at < ?",
            (PROV, rec["url"], REREAD_BEFORE)).rowcount
    ctx.conn.commit()
    if owed:
        ctx.log("  nl: {0} sitting(s) stored 'ok' by the parser before {1}; read again".format(owed, REREAD_BEFORE))
    return owed


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
    ctx.nl_reviewed = pn.ReviewedDivisions.load(PROV)
    if not ctx.refresh:
        stats["owed_stale"] = owe_stale(ctx, records)
    resolver = make_resolver(ctx.conn)
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
    n, with_party = ps.refresh_party(ctx.conn, PROV, pn.Resolver.from_conn(ctx.conn, PROV), legislature, sess)
    stats["votes_with_party"] = "{0}/{1}".format(with_party, n)
    ctx.conn.commit()
    return stats
