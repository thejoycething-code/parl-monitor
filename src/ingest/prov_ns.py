"""Nova Scotia House of Assembly: roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov ns. Scope: docs/canada-provinces-scope.md
(Nova Scotia). The scoping probe's TCP reset was the laptop's VPN exit: from
a GitHub runner nslegislature.ca answers 200 to the honest UA, so every
fixture here was fetched from CI (.github/workflows/probe-hosts.yml,
2 October 2026). robots.txt disallows only Drupal's admin paths and sets
`Crawl-delay: 10`, which prov_fetch honours per host: ten seconds between
requests to nslegislature.ca.

THE RECORD IS HANSARD. The Journals stop at the 63rd Assembly's third
session (2021). Hansard is posted as HTML, one page per sitting, for every
session from the 56th Assembly on, and prints each recorded division in
full: "There has been a request for a recorded vote" ... the Clerk calls the
roll ... the names in two columns, YEAS and NAYS ... "THE CLERK: For, 39.
Against, 11." The Clerk's count is the printed total the tally check needs.

  * SESSIONS. The Hansard index lists every session it holds
    ("assembly-61-session-2"); the dates of each are the Assembly's own
    "Dates of Assemblies, Sessions and Sittings" page ("House Opened: March
    25, 2010 ... House Prorogued: March 31, 2011"). Only the Assemblies a
    window can touch are asked for their dates (newest first, stopping at
    the first that opened before --since): the rest ended before it.
  * LISTING. /legislative-business/hansard-debates/assembly-<leg>-session-<n>,
    forty-five sittings a page (?page=1, ...). Each row gives the sitting,
    the date ("2011-Mar-31") and the sitting's page, linked as listed --
    some 2011 sittings are linked under the French path
    ("61e-assemblee-2e-session/house_11mar31"), and file names carry a part
    letter ("house_24feb27a"). Nothing is constructed.
  * DIVISIONS. An HTML table, one row a pair, the header row "YEAS | NAYS",
    continued after a page break (in 2012 a column may be ONE cell, a name
    a line, with the header in it); or paragraphs, "YEAS NAYS" and one
    printed line each (2010-2014, and again 2021-2026). The paragraph lines
    are placed by the Clerk's count: the first min(YEAS, NAYS) lines hold
    two names and the rest the longer column's; a line is cut at each
    title, else only where it leaves two full names (7 October 2026: the
    run of spaces that once marked the columns falls inside names as often,
    and from 2023 the columns run together with one space). A third column
    of ABSTENTIONS, a list with no header between the roll call and the
    count, and a Clerk's count that follows no list read (a gap, never
    'ok') are handled too. The tally check still runs on the whole.
  * ROSTER. /members/profiles-table/<assembly> lists every Member of that
    Assembly, including those who left it, with the profile slug (the
    member_key: the House's own id), district and party. That party is the
    Member's LATEST in the Assembly (Trevor Zinck, elected NDP in 2009, is
    "IND" for the 61st), so it is stored undated and never written on a
    vote.
  * PARTY AT THE VOTE, DATED BY YEAR. Each Member's profile prints a
    "Constituency / Party / Start Date" history ("PC 2017 - 2021",
    "Independent 2021"). Those rows are stored as party-only terms
    (source 'party-profile') from 1 January of the first year to 31
    December of the last. In the year a Member changed party two rows cover
    the day, so that year's votes carry no party (prov_names.party_at:
    unique-or-nothing). Profiles are read once per Member and again only
    when the Assembly's table shows a different party.
  * BILLS. /legislative-business/bills-statutes/bills/assembly-<leg>-session-<n>
    lists every bill with its type, its text (the first-reading HTML, linked
    from the number) and its latest status. Each text is read and the bill
    classified per passage. The bill's own page (stage dates, sponsor) is
    read only for a bill on our ground, a watched bill, or one a recorded
    division names: at ten seconds a request, reading every page would cost
    a session's backfill an hour.
  * VOICE. "The motion is for third reading of Bill No. 48." with "All
    those in favour?" and "The motion is carried." and no recorded vote:
    stored as kind='voice', "passed on voice, no member record".
  * CROSS-CHECK. Every "Second Reading Passed" or "Third Reading Passed" a
    bill page dates to a day whose Hansard was read must be found in it,
    divided or on voice. A miss is a gap.

Hansard speeches are not stored.
"""

from __future__ import annotations

import datetime
import html as _html
import itertools
import json
import re
from urllib.parse import urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text, join_fragments, pdf_rows, sessions_sorted

PROV = "ns"
CURRENT_SESSION = "65-1"
BASE = "https://nslegislature.ca"
HANSARD_INDEX = BASE + "/legislative-business/hansard-debates"
HANSARD = BASE + "/legislative-business/hansard-debates/assembly-{0}-session-{1}"
BILLS = BASE + "/legislative-business/bills-statutes/bills/assembly-{0}-session-{1}"
ROSTER = BASE + "/members/profiles-table/{0}"
DATES = BASE + "/legislative-business/bills-statutes/assembly-dates/{0}"
PROFILE_SOURCE = "party-profile"
MAX_LISTING_PAGES = 12

STAGE_CODE = {"Second Reading": "2r", "Third Reading": "3r"}


def parse_session(code):
    m = re.match(r"^(\d{2})-(\d{1,2})$", (code or "").strip())
    if not m:
        raise ValueError("Nova Scotia session must look like 65-1, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def _date(text, fmts=("%B %d, %Y", "%Y-%b-%d")):
    t = re.sub(r"\s+", " ", (text or "").replace("\xa0", " ").strip()).rstrip(".")
    for f in fmts:
        try:
            return datetime.datetime.strptime(t, f).date().isoformat()
        except ValueError:
            continue
    return None


# -- sessions -----------------------------------------------------------------

_SESSION_LINK = re.compile(r'href="(?:https://nslegislature\.ca)?/legislative-business/hansard-debates/'
                           r'assembly-(\d+)-session-(\d+)"')


def index_sessions(html):
    """[(leg, sess)] the Hansard index links, newest first, de-duplicated."""
    out = []
    for leg, sess in _SESSION_LINK.findall(html or ""):
        k = (int(leg), int(sess))
        if k not in out:
            out.append(k)
    return sorted(out, reverse=True)


_DATES_SESSION = re.compile(r"Session\s+(\d+)\s*\|(.*?)(?=\|\s*Session\s+\d+\s*\||\|\s*Previous Assembly|$)", re.S)
_DATES_EVENT = re.compile(r"(General Election|House Opened|House Adjourned|House Resumed|House Reconvened|"
                          r"House Prorogued|House Dissolved)\s*:\s*([A-Z][a-z]+\s+\d{1,2},\s*\d{4})")


def parse_assembly_dates(html, legislature):
    """{session: {'start', 'end'}} from one Assembly's dates page: a session
    starts the day the House first opened and ends when it was prorogued
    or dissolved (None while it runs)."""
    i = (html or "").find("<h1")
    j = (html or "").find("More Information", i)
    text = _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", (html or "")[i:j])))
    out = {}
    for m in _DATES_SESSION.finditer(text):
        events = [(k, _date(v)) for k, v in _DATES_EVENT.findall(m.group(2))]
        opened = [d for k, d in events if k == "House Opened" and d]
        closed = [d for k, d in events if k in ("House Prorogued", "House Dissolved") and d]
        out[int(m.group(1))] = {"start": min(opened) if opened else None,
                                "end": max(closed) if closed else None}
    return out


def assembly_span(html):
    """(general election, dissolution|None) of the Assembly a dates page is for."""
    i = (html or "").find("<h1")
    j = (html or "").find("More Information", i)
    seg = (html or "")[i:j]
    text = _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", seg)))
    events = [(k, _date(v)) for k, v in _DATES_EVENT.findall(text)]
    elected = [d for k, d in events if k == "General Election" and d]
    dissolved = [d for k, d in events if k == "House Dissolved" and d]
    return (min(elected) if elected else None, max(dissolved) if dissolved else None)


def list_sessions(ctx):
    """Every session of the Hansard index, oldest first, each with the dates
    its Assembly's page gives. Assemblies are asked newest first; the first
    whose opening day is before the window's start is the last asked, since
    every older one ended before it opened."""
    html = ctx.text(HANSARD_INDEX, "hansard-index")
    pairs = index_sessions(html)
    if html and not pairs:
        ctx.gap("ns: no sessions parsed from the Hansard index {0}".format(HANSARD_INDEX))
        return []
    out, skipped = [], []
    legs = sorted({leg for leg, _ in pairs}, reverse=True)
    stop = False
    for leg in legs:
        if stop:
            skipped.append(leg)
            continue
        page = ctx.text(DATES.format(leg), "assembly-dates-{0}".format(leg))
        dates = parse_assembly_dates(page, leg) if page else {}
        if page and not dates:
            ctx.gap("ns: no session dates parsed from {0}".format(DATES.format(leg)))
        for l2, sess in pairs:
            if l2 == leg:
                d = dates.get(sess) or {}
                out.append({"code": "{0}-{1}".format(leg, sess), "start": d.get("start"), "end": d.get("end")})
        starts = [d["start"] for d in dates.values() if d.get("start")]
        if not ctx.since or (starts and min(starts) <= ctx.since):
            stop = True
    if skipped:
        ctx.log("  ns: Assemblies {0} end before the window opens; their dates were not asked".format(
            " ".join(str(x) for x in sorted(skipped))))
    return sessions_sorted(out)


# -- the Hansard listing --------------------------------------------------------

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_SITTING_LINK = re.compile(r'<a href="([^"]*/house_[0-9a-z]+)"[^>]*>([^<]+)</a>', re.I)


def list_records(html, base_url):
    """[{date, url, sitting, part}] from one page of a session's Hansard listing."""
    out = []
    for row in _ROW.findall(html or ""):
        m = _SITTING_LINK.search(row)
        if not m:
            continue
        date = _date(html_text(m.group(2)))
        if not date:
            continue
        cells = [html_text(c) for c in _CELL.findall(row)]
        url = urljoin(base_url, _html.unescape(m.group(1)))
        part = re.search(r"house_\d\d[a-z]{3}\d\d([a-z]?)$", url)
        out.append({"date": date, "url": url, "sitting": cells[0] if cells else None,
                    "part": (part.group(1) or None) if part else None})
    return out


def listing_pages(html):
    """The highest ?page=N the listing links to (0 when there is no pager)."""
    pages = [int(p) for p in re.findall(r'[?&]page=(\d+)"', html or "")]
    return max(pages) if pages else 0


def fetch_listing(ctx, legislature, session):
    """Every sitting of the session, across the listing's pages, oldest first."""
    url = HANSARD.format(legislature, session)
    html = ctx.text(url, "hansard-{0}-{1}".format(legislature, session))
    if html is None:
        return None
    records = list_records(html, url)
    last = listing_pages(html)
    if last >= MAX_LISTING_PAGES:
        ctx.gap("ns {0}-{1}: the Hansard listing has {2} pages, more than the {3} read".format(
            legislature, session, last + 1, MAX_LISTING_PAGES))
        last = MAX_LISTING_PAGES - 1
    for n in range(1, last + 1):
        page = ctx.text("{0}?page={1}".format(url, n), "hansard-{0}-{1}-p{2}".format(legislature, session, n))
        if page is None:
            continue
        got = list_records(page, url)
        if not got:
            ctx.gap("ns {0}-{1}: Hansard listing page {2} lists no sittings".format(legislature, session, n))
        records.extend(got)
        last = max(last, min(listing_pages(page), MAX_LISTING_PAGES - 1))
    seen, out = set(), []
    for r in sorted(records, key=lambda r: (r["date"], r["url"])):
        if r["url"] not in seen:
            seen.add(r["url"])
            out.append(r)
    return out


# -- roster -----------------------------------------------------------------------

# The table links each Member's historical biography
# ("/members/profiles/jamie-baillie/history"); the slug is the key. The
# party history is printed on the Member's profile, /members/profiles/<slug>
# -- the page Hansard links every speaker to, and the page that links the
# biography ("Please view his historical biography at .../gordon-l-wilson/
# history", on a former Member's profile).
_PROFILE_LINK = re.compile(r'href="(/members/profiles/([^"/]+)(?:/history)?)"[^>]*>([^<]+)</a>')


def parse_roster_table(html):
    """[{key, surname, given, name, party, riding}] from /members/profiles-table/<assembly>."""
    out = []
    for row in _ROW.findall(html or ""):
        cells = _CELL.findall(row)
        if len(cells) < 3:
            continue
        m = _PROFILE_LINK.search(cells[0])
        if not m:
            continue
        surname, _, given = html_text(m.group(3)).partition(",")
        gtoks = pn._strip_honorifics(given.split())
        given = " ".join(gtoks)
        out.append({"key": m.group(2), "page": BASE + "/members/profiles/" + m.group(2),
                    "surname": surname.strip(), "given": given,
                    "name": (given + " " + surname.strip()).strip(),
                    "party": canon_party(html_text(cells[1])) or None, "riding": html_text(cells[2]) or None})
    return out


def roster_assembly(html):
    """The Assembly a roster page is for ('Standings: 61 st Assembly'), or None."""
    m = re.search(r"Standings:\s*(\d+)\s*(?:<sup>)?\s*(?:st|nd|rd|th)", html or "")
    return int(m.group(1)) if m else None


_PARTIES = {"pc": "Progressive Conservative", "progressive conservative": "Progressive Conservative",
            "ndp": "New Democratic", "new democratic": "New Democratic", "new democratic party": "New Democratic",
            "lib": "Liberal", "liberal": "Liberal", "ind": "Independent", "independent": "Independent",
            "i": "Independent", "green": "Green"}


def canon_party(text):
    t = re.sub(r"\s+", " ", (text or "").strip()).lower()
    return _PARTIES.get(t, (text or "").strip() or None)


def parse_profile_parties(html):
    """[(party, first_year, last_year|None)] from a Member's profile."""
    out = []
    i = (html or "").find("views-field-field-time-period")
    if i < 0:
        return out
    block = html[html.rfind("<table", 0, i):html.find("</table>", i)]
    for row in _ROW.findall(block):
        cells = [html_text(c) for c in _CELL.findall(row)]
        if len(cells) < 3:
            continue
        years = re.match(r"^\s*(\d{4})\s*(?:-\s*(\d{4}))?\s*$", cells[2])
        if not years or not cells[1]:
            continue
        out.append((canon_party(cells[1]), int(years.group(1)), int(years.group(2)) if years.group(2) else None))
    return out


def profile_party_terms(rows):
    """Party-only terms from a profile's history: whole years, as printed."""
    return [{"legislature": None, "party": p, "riding": None, "start": "{0}-01-01".format(a),
             "end": "{0}-12-31".format(b) if b else None, "party_dated": 1} for p, a, b in rows]


def membership_terms(history, span, legislature, riding):
    """A Member's terms in one session: each year range of the profile's
    party history, cut to the session's span. With no history, the whole
    span.

    Why: the Assembly's table lists everyone who sat in it, and "Mr.
    Wilson" in April 2019 is Gordon Wilson only because Dave Wilson's
    profile ends in 2018. A year range is as close as the profile dates;
    in the year two such Members overlap, a surname alone stays ambiguous
    (a gap), and a full name still resolves."""
    first, last = span
    out = []
    for t in history:
        starts = [x for x in (t.get("start"), first) if x]
        ends = [x for x in (t.get("end"), last) if x]
        a = max(starts) if starts else None
        b = min(ends) if ends else None
        if a and b and a > b:
            continue
        out.append({"legislature": legislature, "party": None, "riding": riding,
                    "start": a, "end": b, "party_dated": 0})
    out.sort(key=lambda t: t["start"] or "")
    merged = []
    for t in out:
        if merged and (merged[-1]["end"] is None or (t["start"] or "") <= _next_day(merged[-1]["end"])):
            if merged[-1]["end"] is not None and (t["end"] is None or t["end"] > merged[-1]["end"]):
                merged[-1]["end"] = t["end"]
            continue
        merged.append(dict(t))
    if not history:
        merged = [{"legislature": legislature, "party": None, "riding": riding,
                   "start": first, "end": last, "party_dated": 0}]
    return merged


def _next_day(iso):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=1)).isoformat()


def stored_history(conn, key):
    return [dict(zip(("party", "start", "end"), r)) for r in conn.execute(
        "SELECT party, start, end FROM prov_member_terms WHERE prov=? AND member_key=? AND source=? "
        "ORDER BY start", (PROV, key, PROFILE_SOURCE))]


# -- the session's own list of Members (the Journals, to the 63rd Assembly) ------
#
# Each session's compiled Journal opens with "MEMBERS OF THE LEGISLATIVE
# ASSEMBLY / Second Session of the Sixty-First General Assembly": every
# constituency's Member with a party code, and footnotes for the changes
# ("Murray Scott resigned his seat on September 8, 2010 ... Jamie Baillie
# won the by-election"). A Member of the Assembly whom the session's list
# does not name, printed or in a footnote, did not sit in that session: the
# 61st Assembly had two David Wilsons, and only David A. Wilson sat after the
# 2010 Glace Bay vacancy, so "Mr. Wilson" in 2010 is his. Sessions with no
# list (the Journals stop at 63-3) keep every Member of the Assembly.

JOURNALS = BASE + "/legislative-business/journals"
_MEMBER_CELL = re.compile(r"^(?:Hon\.\s+|The Honourable\s+)?(?P<name>[^()]*?)\s*\((?P<party>[A-Z]{1,4})\)\s*(?P<mark>\d*)\s*$")
_NOTE = re.compile(r"^(\d{1,2})\.\s+(.*)$")
_FOOTNOTE_NAME = re.compile(
    r"([A-Z][\w'’.\-]*(?:\s+(?:[A-Z][\w'’.\-]*|d['’][\w\-]+)){1,3})\s+"
    r"(?=resigned|won\b|became|passed away|died|was elected|was sworn|crossed|joined|left)")


def journal_member_lists(html, legislature, session):
    """The session's member-list PDFs as the Journals page links them."""
    pat = re.compile(r'href="([^"]*/journals/{0}-{1}/[^"]*[Mm]ember[^"]*\.pdf)"'.format(legislature, session))
    out = []
    for href in pat.findall(html or ""):
        u = urljoin(JOURNALS, _html.unescape(href))
        if u not in out:
            out.append(u)
    return out


def parse_member_list(pages):
    """{'session': (leg, sess)|None, 'rows': [{riding, name, party, mark}],
    'notes': {mark: text}, 'problems': [...]} from a member list's
    positioned rows (prov_fetch.pdf_rows): constituency on the left, the
    Member with a party code and a footnote mark on the right. A wrapped
    constituency ("...-Salmon" / "River") or a party code wrapped under its
    name ("Hon. Derek Mombourquette" / "(LIB)") is joined to the row above."""
    out = {"session": None, "rows": [], "notes": {}, "problems": []}
    cut = None
    in_rows = False
    note = None
    for page in pages:
        for _y, frags in page:
            line = join_fragments(frags)
            if out["session"] is None:
                h = _LIST_HEAD.search(line)
                if h:
                    out["session"] = (ordinal_value(h.group(2)), ordinal_value(h.group(1)))
            if cut is None:
                heads = {f[2].strip(): f[0] for f in frags}
                if "Constituency" in heads and "Member" in heads:
                    cut = (heads["Constituency"] + heads["Member"]) / 2.0
                    in_rows = True
                continue
            if line.startswith("Key:") or line.startswith("OFFICERS OF"):
                in_rows = False
                continue
            n = _NOTE.match(line)
            if n and not in_rows:
                note = n.group(1)
                out["notes"][note] = n.group(2)
                continue
            if not in_rows:
                if note and line and not line.startswith(("Key", "LIB", "NDP", "PC", "I ")):
                    out["notes"][note] += " " + line
                continue
            left = join_fragments([f for f in frags if f[0] < cut])
            right = join_fragments([f for f in frags if f[0] >= cut])
            if left and not right and out["rows"]:
                out["rows"][-1]["riding"] += " " + left
                continue
            if right and re.fullmatch(r"\([A-Z]{1,4}\)\s*\d*", right) and out["rows"] \
                    and out["rows"][-1].get("pending"):
                last = out["rows"].pop()
                right = last["pending"] + " " + right
                left = left or last["riding"]
            if not right:
                continue
            vacant = re.fullmatch(r"Vacant\s*(\d*)", right)
            if vacant:
                # "Vacant1": no Member, but footnote 1 names the by-election
                # winner, and this row gives the constituency.
                out["rows"].append({"riding": left, "name": None, "party": None,
                                    "mark": vacant.group(1) or None, "vacant": True})
                continue
            m = _MEMBER_CELL.match(right)
            if not m:
                # a name whose party code wraps to the next line
                out["rows"].append({"riding": left, "name": None, "party": None, "mark": None,
                                    "pending": right})
                continue
            out["rows"].append({"riding": left, "name": re.sub(r"\s+", " ", m.group("name")).strip(),
                                "party": m.group("party"), "mark": m.group("mark") or None})
    out["rows"] = [r for r in out["rows"] if r.get("name") or r.get("vacant")]
    if not out["rows"]:
        out["problems"].append("no Members read from the list")
    return out


def match_members(parsed, rows):
    """(keys, problems): the roster Members a session's list names. A row
    is matched by its constituency AND surname (the 61st Assembly's two
    David Wilsons sat for Sackville-Cobequid and Glace Bay), a footnote's
    by-election winner by the constituency of the row its mark is on."""
    keys, problems = set(), []

    def find(riding, name):
        sur = pn.fold(name.split()[-1]) if name else ""
        hits = [r["key"] for r in rows if pn.squash(r["riding"]) == pn.squash(riding or "")
                and pn.fold(r["surname"]).split()[-1:] == [sur]]
        return hits

    by_mark = {}
    for row in parsed["rows"]:
        if row.get("vacant"):
            if row["mark"]:
                by_mark[row["mark"]] = row["riding"]
            continue
        hits = find(row["riding"], row["name"])
        if len(hits) == 1:
            keys.add(hits[0])
        else:
            problems.append("{0!r} ({1}) fits {2}".format(row["name"], row["riding"], hits or "nobody"))
        if row["mark"]:
            by_mark[row["mark"]] = row["riding"]
    for mark, text in parsed["notes"].items():
        riding = by_mark.get(mark)
        if not riding:
            continue
        for m in _FOOTNOTE_NAME.finditer(text):
            hits = find(riding, m.group(1))
            if len(hits) == 1:
                keys.add(hits[0])
    return keys, problems


_ORD_UNITS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
              "seventh": 7, "eighth": 8, "ninth": 9}
_ORD_TENS = {"fiftieth": 50, "sixtieth": 60, "seventieth": 70}
_TENS = {"fifty": 50, "sixty": 60, "seventy": 70}


def ordinal_value(word):
    """'Sixty-First' -> 61, 'Second' -> 2."""
    w = (word or "").lower().strip()
    if w in _ORD_UNITS:
        return _ORD_UNITS[w]
    if w in _ORD_TENS:
        return _ORD_TENS[w]
    head, _, tail = w.partition("-")
    if head in _TENS and tail in _ORD_UNITS:
        return _TENS[head] + _ORD_UNITS[tail]
    return None


_LIST_HEAD = re.compile(r"([A-Z][a-z]+) Session of the ([A-Z][a-z]+(?:-[A-Z][a-z]+)?) General Assembly")


def session_members(ctx, legislature, session, rows):
    """The keys of the Members the session's own list names, or None when
    the Journals print no list for the session (or it cannot be used)."""
    html = ctx.text(JOURNALS, "journals")
    urls = journal_member_lists(html, legislature, session) if html else []
    if not urls:
        return None
    keys = set()
    for u in urls:
        raw = ctx.bytes(u, "memberlist-{0}-{1}".format(legislature, session))
        if raw is None:
            return None
        try:
            parsed = parse_member_list(pdf_rows(raw))
        except Unreadable as exc:
            ctx.gap("ns {0}-{1}: member list {2}: {3}".format(legislature, session, u, exc))
            return None
        if parsed["session"] != (legislature, session):
            ctx.gap("ns {0}-{1}: the member list {2} is for session {3}; not used".format(
                legislature, session, u, parsed["session"]))
            return None
        got, problems = match_members(parsed, rows)
        for p_ in parsed["problems"] + problems:
            ctx.gap("ns {0}-{1}: member list {2}: {3}".format(legislature, session, u, p_))
        if parsed["problems"]:
            return None
        keys |= got
    return keys


def fetch_roster(ctx, legislature, session, span=(None, None)):
    """The session's Members: the Assembly's table, cut to the Members the
    session's own Journal list names (where there is one), each dated by
    the profile's party history; that history is stored as party-only
    terms. Returns the number of Members given a term in the session."""
    url = ROSTER.format(legislature)
    html = ctx.text(url, "roster-{0}".format(legislature))
    rows = parse_roster_table(html) if html else []
    if html and not rows:
        ctx.gap("ns: no Members parsed from {0}".format(url))
    if html and rows and roster_assembly(html) not in (None, legislature):
        ctx.gap("ns: {0} shows the {1}th Assembly, not the {2}th; not used".format(
            url, roster_assembly(html), legislature))
        return 0
    if ctx.dry_run or not rows:
        return len(rows)
    current = legislature == parse_session(CURRENT_SESSION)[0]
    if current:
        ctx.conn.execute("UPDATE prov_members SET sitting=0 WHERE prov=?", (PROV,))
    for r in rows:
        ps.upsert_member(ctx.conn, PROV, r["key"], name=r["name"], surname=r["surname"], given=r["given"],
                         riding=r["riding"], party=r["party"] if current else None,
                         sitting=1 if current else None,
                         page_url=r["page"] if current else None)
    ctx.conn.commit()
    for r in rows:
        r["current"] = current
    named = session_members(ctx, legislature, session, rows)
    sitting = [r for r in rows if named is None or r["key"] in named]
    profiles = fetch_profiles(ctx, sitting)
    source = "roster-{0}-{1}".format(legislature, session)
    for r in rows:
        if r not in sitting:
            ps.replace_terms(ctx.conn, PROV, r["key"], [], source)
            continue
        # The table's party is the Member's LATEST in the Assembly: kept on
        # the term for the reader, never dated, never written on a vote.
        terms = membership_terms(stored_history(ctx.conn, r["key"]), span, legislature, r["riding"])
        for t in terms:
            t["party"] = r["party"]
        ps.replace_terms(ctx.conn, PROV, r["key"], terms, source)
    ctx.conn.commit()
    ctx.log("  ns roster {0}-{1}: {2} Member(s) of the Assembly, {3} in the session{4}; {5} profile(s) "
            "read for party history".format(
                legislature, session, len(rows), len(sitting),
                " (by its Journal's list of Members)" if named is not None else " (no Journal list: all)",
                profiles))
    return len(sitting)


def fetch_profiles(ctx, rows):
    """Read the party history of each Member who has none stored, or whose
    latest stored party differs from the Assembly table's."""
    read = 0
    for r in rows:
        have = ctx.conn.execute(
            "SELECT party, start FROM prov_member_terms WHERE prov=? AND member_key=? AND source=? "
            "ORDER BY start DESC", (PROV, r["key"], PROFILE_SOURCE)).fetchall()
        # Read when there is no history yet; in the CURRENT Assembly, also
        # when the table's party is not the history's latest (a Member who
        # crossed the floor this week). A past Assembly's table shows the
        # party at its end, which a later change makes differ for ever.
        if have and not ctx.refresh and (not r.get("current") or r["party"] is None
                                         or have[0][0] == r["party"]):
            continue
        if ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("profiles", read))
            break
        url = r["page"]
        page = ctx.text(url, "profile-" + r["key"])
        if page is None:
            continue
        read += 1
        hist = parse_profile_parties(page)
        if not hist:
            ctx.gap("ns: the profile {0} prints no party history; that Member's votes carry no party".format(url))
            continue
        ps.replace_terms(ctx.conn, PROV, r["key"], profile_party_terms(hist), PROFILE_SOURCE)
        ctx.conn.commit()
    return read


# -- the Hansard: blocks ------------------------------------------------------------

# A paragraph ends at its </p>, or, where the record never closes it, at the
# next <p>, <table> or </div>: the Hansards of late 2011 close no paragraph
# at all ('<p class="hsd_general">'), and 14, 25 and 28 November 2011 were
# read as ten paragraphs each, nothing found and the sitting stored 'ok'. A
# paragraph never runs over a table: 11 May 2015 leaves a page marker's <p>
# open across the second half of a division list ("<p>[Page 5245]</td></tr>
# <table class="vote">...</table><p>THE CLERK ...</p>").
_BLOCK = re.compile(r"(?is)<table\b.*?</table>|<p\b[^>]*>(?:(?!<table\b|<p\b|</div>).)*?"
                    r"(?:</p>|(?=<table\b|<p\b|</div>)|$)")
_ROW_EDGE = re.compile(r"(?is)</tr\s*>|<tr\b[^>]*>")
_TD = re.compile(r"(?is)<t[dh]\b[^>]*>(.*?)(?=<t[dh]\b|</tr>|$)")


def _cell_text(fragment):
    """A cell's text, whitespace squashed, with each <br> kept as a newline:
    in 2012 a whole column of names is ONE cell, a name a line ("Mr.
    Landry<br />Ms. More<br />...", 27 April 2012)."""
    s = re.sub(r"(?is)<br\s*/?>", "\n", fragment or "")
    s = re.sub(r"(?is)<[^>]+>", "", s)
    s = _html.unescape(s).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", x).strip() for x in s.split("\n")]
    return "\n".join(x for x in lines if x)


def _para_text(fragment):
    """A paragraph's text with its source line breaks as single spaces and
    its runs of spaces KEPT: before about 2015 the two columns of a
    division list are separated only by them."""
    s = re.sub(r"(?is)<br\s*/?>", "  ", fragment or "")
    s = re.sub(r"(?is)<[^>]+>", "", s)
    s = _html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]*\r?\n[ \t]*", " ", s)
    return s.strip()


def blocks(page):
    """[('p', text) | ('table', [[cell, ...], ...])] in document order."""
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page or "")
    out = []
    for m in _BLOCK.finditer(body):
        frag = m.group(0)
        if frag[:6].lower() == "<table":
            # Rows are cut at every <tr> AND every </tr>: the 4 April 2024
            # list opens its rows with no <tr> at all ("<td>Hon. Brad
            # Johns</td><td></td></tr> <td>..."), and the 25 March 2025
            # continuation closes no <td>.
            rows = []
            for chunk in _ROW_EDGE.split(frag):
                cells = [_cell_text(td) for td in _TD.findall(chunk)]
                if cells:
                    rows.append(cells)
            out.append(("table", rows))
        else:
            inner = re.sub(r"(?is)^<p\b[^>]*>|</p>$", "", frag)
            out.append(("p", _para_text(inner)))
    return out


def flat(text):
    return re.sub(r"\s+", " ", text or "").strip()


# -- the Hansard: divisions ---------------------------------------------------------

_HEADER = re.compile(r"^\s*YEAS?\s+NAYS?(?:\s+ABSTENTIONS?)?\s*$", re.I)
_FURNITURE = re.compile(r"^\s*(?:\[\s*Page\s*\d+\s*\]|\[\s*\d{1,2}:\d{2}\s*[ap]\.?\s*m\.?\]|)\s*$", re.I)
# The Clerk's count, in every form met 2010-2026: "For, 39. Against, 11.",
# "For, 28, Against 12." (2010), "For, 23. Against. 23. (Applause)" (2013),
# "Those in favour of the motion, 31; those against, 17." (2014-2017), "in
# favour of Resolution No. 35, 33; against, 13 - meeting the two-thirds
# threshold" (2016), "Yays, 47. Nays, 0." (2023), "For, 28. Nay, 17.
# Abstentions, 1." (17 October 2022).
_NUM = r"(?:\d+|[A-Za-z][A-Za-z\-]*(?: [A-Za-z\-]+)?)"
_COUNT = re.compile(
    r"(?:\bFor|\bYeas?|\bYays|\bin favour(?: of [^,;]*?)?)\s*,?\s*(?P<yea>" + _NUM + r")\s*[.,;:]?\s*"
    r"(?:those\s+)?(?:Against|Nays?)\s*[.,]?\s*(?P<nay>" + _NUM + r")\s*[.,;]?"
    r"(?:\s*Abstentions?\s*,?\s*(?P<abs>" + _NUM + r")\s*[.,;]?)?"
    r"\s*(?:\([^)]*\)\s*\.?)?\s*(?:-\s.*)?$", re.I)
_RESULT = re.compile(r"((?:The|That)\s+(?:main\s+)?(?:motion|amendment|sub-?amendment|bill)\s+"
                     r"(?:as amended\s+)?(?:is|was|has been)\s+(?:carried|defeated|negatived|lost|passed)"
                     r"|motion (?:is )?(?:carried|defeated))", re.I)
_SPEAKER = re.compile(r"^\s*(?:THE\s+(?:DEPUTY\s+)?SPEAKER|M[RS]\.?\s+(?:DEPUTY\s+)?SPEAKER|MADAM\s+SPEAKER|"
                      r"THE\s+CHAIR|(?:MR\.|MADAM)\s+CHAIR(?:MAN)?)\b\s*:?", re.I)
_CLERK = re.compile(r"^\s*THE\s+CLERK\s*:?", re.I)
# The question as the Chair puts it: "The motion is for third reading of
# Bill No. 6.", "The motion is that the House concur in the report ...".
_PUT = re.compile(r"\bThe (?:main )?(?:motion|question|amendment|sub-?amendment)(?: before the House)?"
                  r"(?: as amended)? is (?!(?:carried|defeated|negatived|lost|passed|in order|out of order|"
                  r"not|put|now (?:before|on))\b)[a-z]", re.I)
_REQUEST = re.compile(r"request for a recorded vote|recorded vote (?:has been|is being) (?:called|requested)|"
                      r"call(?:ed)? for a recorded vote|recorded vote,? please|recorded vote has been called", re.I)
_LABEL_PREFIX = re.compile(r"^[A-Z][A-Z .'\-]+?(?:\s*«\s*»|\s*«|\s*»)?\s*:\s*")
_PROCEDURE = re.compile(r"^(?:All those in favour|Contrary minded|Are the Whips|The Whips|Ring the bells|"
                        r"Order|Before we proceed|Two members|Is it agreed|Some Honourable|I would ask|I'll (?:just )?remind|Please remain|The Clerk|"
                        r"\[|\(|The honourable|We will ring|We will now)", re.I)
_RECORDED = re.compile(r"recorded vote|recorded division|The Clerk call", re.I)
# "Bill No. 6", and "Bill 49" / "Bill 204" without the No. (2014, 2022).
_BILL = re.compile(r"\bBill(?: No\.)?\s*(\d{1,3})\b")
_READING = re.compile(r"\b(second|third)\s+reading(?:\s+debate)?\s+(?:of|on)\s+Bill(?: No\.)?\s*(\d{1,3})\b", re.I)
# "be now read a third time", "be read a third time" (2 April 2026), "now be
# read a second time", "be read for a second time".
_MOVE_READ = re.compile(r"Bill(?: No\.)?\s*(\d{1,3})\b[^.]{0,160}?\b(?:now\s+)?be\s+(?:now\s+)?read\s+(?:for\s+)?"
                        r"a\s+(second|third)\s+time", re.I)
# The Chair names the reading but not the bill: "The motion is for second
# reading." (17 October 2019). The stage is still the question's; the bill
# is the one whose reading was moved.
_STAGE_ONLY = re.compile(r"\bThe motion is (?:for|to close|to move) (?:the )?(second|third) reading\s*\.?$", re.I)
_VOTE_ON_BILL = re.compile(r"\b(?:recorded )?vote on Bill(?: No\.)?\s*(\d{1,3})\b", re.I)
_BILL_HEADING = re.compile(r"^\s*Bill No\.\s*(\d+)\s*[-–—]")
_WORDS = {"nil": 0, "none": 0, "zero": 0, "no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
          "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
          "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
          "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}


def count_value(text):
    t = (text or "").strip().lower()
    if t.isdigit():
        return int(t)
    total = 0
    for w in re.split(r"[\s\-]+", t):
        if w not in _WORDS:
            return None
        total += _WORDS[w]
    return total if t else None


def clerk_count(text):
    """(yeas, nays, abstentions) from the Clerk's count, or None. A total
    that is not a number (a word the count misreads) is None in its place,
    and the division is then a gap."""
    c = _COUNT.search(_CLERK.sub("", flat(text)))
    if not c:
        return None
    out = (count_value(c.group("yea")), count_value(c.group("nay")),
           count_value(c.group("abs")) if c.group("abs") else None)
    return out if out[0] is not None or out[1] is not None else None


def _label_ok(text):
    """True when the text could be a member's name as a list prints it."""
    t = flat(text)
    if not t or len(t) > 60 or re.search(r"[\d:;!?\[\]]", t):
        return False
    words = t.replace("’", "'").split()
    return all(w[0].isupper() or w.lower() in ("de", "d'", "van", "von", "jr.", "le") or w[:2].lower() == "d'"
               for w in words)


def _is_header_row(cells):
    """The YEAS | NAYS row; in 2012 a cell may hold its header AND its
    column's names, a line each ("YEAS<br>Mr. Landry<br>...", 5 November
    2012), so only each cell's first line is the header."""
    return bool(_HEADER.match(" ".join(c.split("\n")[0] for c in cells if c)))


def _header_rest(cells):
    """The names a header row's cells carry under their header line."""
    rest = ["\n".join(c.split("\n")[1:]) for c in cells]
    return [rest] if any(rest) else []


def _skip_furniture(bl, k):
    while k < len(bl) and bl[k][0] == "p" and _FURNITURE.match(bl[k][1]):
        k += 1
    return k


def _cell_names(cell):
    """The names in one cell: one a line (a <br> between), page furniture
    left out ("[Page 6013]" inside the YEAS cell, 12 April 2023), and an
    entity split around the name closed ("&Mr. Rankinnbsp;", 7 November
    2014, is "Mr. Rankin&nbsp;" typeset wrongly)."""
    out = []
    for x in (cell or "").split("\n"):
        x = re.sub(r"^&(\S.*?)nbsp;$", r"\1", flat(x))
        if x and not _FURNITURE.match(x):
            out.append(x)
    return out


def _read_table_names(bl, k, rows):
    """Two-column table rows, continued by further tables after a page
    marker, until anything else. Returns (yeas, nays, next_index)."""
    yeas, nays = [], []
    while True:
        for cells in rows:
            cells = list(cells) + [""] * (2 - len(cells))
            if not any(c for c in cells[1:]) and len(_segments(cells[0])) == 2 and "\n" not in cells[0]:
                # One cell holding a YEA and a NAY, the cell break lost:
                # ['Mr. Churchill Mr. Dunn'] (6 May 2016). Two titles, two names.
                cells = _segments(cells[0])
            yeas.extend(_cell_names(cells[0]))
            nays.extend(_cell_names(cells[1]))
        # A continuation table after a page marker: it may repeat the header
        # row (November 2023). A new division always has the Clerk's count
        # between, so a table straight after the names is the same list. So
        # is one after the Chair breaks into the roll call ("Can the
        # honourable member for Halifax Chebucto please stand with his
        # vote?", 5 May 2015; the gallery cleared and "We will now continue
        # with the recorded vote", the header printed again, 18 December
        # 2015): a few paragraphs with no count and no result between.
        n = _skip_furniture(bl, k)
        m = n
        while m < min(len(bl), n + 6) and bl[m][0] == "p" and not _interrupts_list(bl[m][1]):
            m += 1
        if m > n and m < len(bl) and bl[m][0] == "table" and bl[m][1]:
            n = m
        if n < len(bl) and bl[n][0] == "table" and bl[n][1]:
            more = bl[n][1][1:] if _is_header_row(bl[n][1][0]) else bl[n][1]
            if all(_label_ok(x) for r in more for c in r[:2] for x in _cell_names(c)):
                rows = more
                k = n + 1
                continue
        return yeas, nays, k


def _interrupts_list(text):
    """True when a paragraph inside a roll call ENDS the list: the Clerk's
    count, a result, or a new request for a vote."""
    t = flat(text)
    return bool(_CLERK.match(t) and clerk_count(t)) or bool(_RESULT.search(t)) or bool(_REQUEST.search(t))


def _line_ok(text):
    """A paragraph-era line that could hold one or two members' names."""
    t = flat(text)
    return 0 < len(t) <= 120 and all(_label_ok(s) for s in _segments(t))


def _read_names(bl, i):
    """Read a division's names from the header block i. Returns (yeas,
    nays, lines, next_index): the two columns as a table prints them, or,
    in the paragraph layouts, the printed LINES (lines is None for a
    table), which are placed only once the Clerk's count is known
    (_place_lines).

    Three layouts are met: a table whose first row is the header (2012 on;
    <td> or <th>; in 2012 a column is one cell, a name a line); a "YEAS
    NAYS" paragraph followed by such a table, with its own "Yeas | Nay"
    header row (October 2019); and a paragraph per printed line (2010-2014,
    and again in 2021-2026)."""
    kind, val = bl[i]
    if kind == "table":
        yeas, nays, j = _read_table_names(bl, i + 1, _header_rest(val[0]) + val[1:])
        lines, j = _name_lines(bl, j)
        return yeas, nays, lines, j
    n = _skip_furniture(bl, i + 1)
    if n < len(bl) and bl[n][0] == "table" and bl[n][1]:
        rows = _header_rest(bl[n][1][0]) + bl[n][1][1:] if _is_header_row(bl[n][1][0]) else bl[n][1]
        yeas, nays, j = _read_table_names(bl, n + 1, rows)
        lines, j = _name_lines(bl, j)
        return yeas, nays, lines, j
    lines, j = _name_lines(bl, i + 1)
    return [], [], lines, j


def _name_lines(bl, j):
    """The paragraph lines of names from block j: ([line, ...], next_index).
    They follow a header paragraph, or finish a list a table began (13
    March 2026: the YEAS run on after the table, a name a paragraph)."""
    lines = []
    while j < len(bl):
        k, text = bl[j]
        if k == "table":
            break
        if _FURNITURE.match(text):
            j += 1
            continue
        if not _line_ok(text):
            break
        lines.append(text)
        j += 1
    return lines, j


_HON_TOKEN = re.compile(r"^(?:Hon|Mr|Mrs|Ms|Miss|Dr|Honourable)\.?$")


def _segments(line):
    """A printed line cut before every title but the first: 'Mr. Landry
    Mr.  Belliveau'; 'Ms. Maureen  MacDonald  Mr. Samson' (6 December 2012:
    the double space is no column mark, it falls inside a name as often as
    between two); 'Ronnie LeBlanc Hon. Greg Morrow'."""
    # A title run into the name is two words: "Mr.Scott", 22 April 2010.
    line = re.sub(r"\b(Hon|Mr|Mrs|Ms|Dr)\.(?=[A-Z])", r"\1. ", flat(line))
    out = []
    for w in line.split():
        if _HON_TOKEN.match(w) and not (out and all(_HON_TOKEN.match(x) for x in out[-1])):
            out.append([w])
        elif not out:
            out.append([w])
        else:
            out[-1].append(w)
    return [" ".join(x) for x in out]


def _bare(words):
    return [w for w in words if not _HON_TOKEN.match(w)]


def _full_name(words):
    """Two or more words besides any title, the last not an initial."""
    b = _bare(words)
    return len(b) >= 2 and not re.fullmatch(r"[A-Z]\.?", b[-1])


def _ends_in_surname(words, vocab):
    toks = tuple(pn.fold(w) for w in words)
    return any(toks[-len(v):] == tuple(v) for v in vocab if 0 < len(v) <= len(toks))


def _split_n(line, n, vocab=None):
    """`n` names from one printed line, or None. Where no title marks a name
    ('Elizabeth Smith-McCrossin Larry Harrison', 18 October 2023; 'Hon.
    Nolan Young Claudia Chender', 25 March 2026: the columns run together
    with ONE space) every cut must leave full names, a title only ever at a
    name's start; if more than one set of cuts does, only cuts with a known
    surname before each count. Anything else is None, never a guess."""
    words = flat(line).split()
    if n == 1:
        return [" ".join(words)] if words else None
    found = []
    for cuts in itertools.combinations(range(1, len(words)), n - 1):
        bounds = (0,) + cuts + (len(words),)
        parts = [words[bounds[k]:bounds[k + 1]] for k in range(n)]
        if all(_clean_part(p) for p in parts):
            found.append(parts)
    if len(found) > 1 and vocab:
        found = [parts for parts in found if all(_ends_in_surname(p, vocab) for p in parts)]
    if len(found) != 1:
        return None
    return [" ".join(p) for p in found[0]]


def _clean_part(words):
    """A full name with its titles, if any, all at the start."""
    k = 0
    while k < len(words) and _HON_TOKEN.match(words[k]):
        k += 1
    rest = words[k:]
    return _full_name(rest) and not any(_HON_TOKEN.match(w) for w in rest)


def _place_lines(lines, count, vocab=None):
    """(yeas, nays, abstentions, note, problem) from the printed lines of a
    paragraph-era list. The columns fill side by side and the shorter runs
    out first, so with the Clerk's count of Y and N the first min(Y, N)
    lines hold two names (YEA, NAY) and every line after holds the longer
    column's; a one-column list (N or Y nil) is a name a line, cut only at
    each title it carries ('Mr. MacDonell Ms. Zann', one line of a 38-0
    list, 3 December 2010). Abstentions are a third column, so the first A
    lines hold three names (17 October 2022). Without a count the lines
    cannot be placed."""
    if count is None or None in count[:2]:
        return [x for l in lines for x in _segments(l)], [], [], None, None
    y, n = count[0], count[1]
    a = count[2] or 0
    paired = min(y, n)
    if len(lines) < paired or a > paired:
        return [], [], [], None, "{0} line(s) of names for {1} paired".format(len(lines), paired)
    yeas, nays, abst = [], [], []
    for k, line in enumerate(lines[:paired]):
        width = 3 if k < a else 2
        segs = _segments(line)
        names = segs if len(segs) == width else _split_n(line, width, vocab)
        if names is None:
            return [], [], [], None, "a line of the paired columns that is not {0} names ({1!r})".format(
                width, flat(line))
        yeas.append(names[0])
        nays.append(names[1])
        abst.extend(names[2:])
    rest = [x for l in lines[paired:] for x in _segments(l)]
    note = None
    if rest:
        if y > n:
            yeas += rest
        elif n > y:
            nays += rest
        else:
            return yeas, nays, abst, None, "{0} name(s) after the paired lines of a {1}-{2} list".format(
                len(rest), y, n)
        if paired:
            note = "{0} one-name line(s) read as {1} (the longer column by the Clerk's count)".format(
                len(lines) - paired, "YEAS" if y > n else "NAYS")
    return yeas, nays, abst, note, None


def parse_hansard(page, vocab=None, strays=None):
    """(divisions, voices) from one sitting's Hansard page, names unresolved.

    divisions: [{seq, yeas, nays, yea_labels, nay_labels, question, item, result,
                 vote_on, stage, bill_number, problem, note}]
    voices:    [{bill_number, stage, result}]

    `vocab` (Resolver.surname_vocab()) only settles where a printed line of
    two full names is cut. `strays`, when a list, receives every Clerk's
    count that follows no list of names the parser read: a division the
    record holds and the parser missed (read_sitting makes it a gap)."""
    bl = blocks(page)
    divisions, voices = [], []
    used = set()
    last_end = 0
    heading_bill = None
    i = 0
    while i < len(bl):
        kind, val = bl[i]
        is_header = (kind == "table" and val and _is_header_row(val[0])) or \
                    (kind == "p" and _HEADER.match(val))
        if kind == "p":
            h = _BILL_HEADING.match(flat(val))
            if h:
                heading_bill = h.group(1)
            if not is_header and _CLERK.match(flat(val)) and clerk_count(val):
                d = _headerless(bl, i, last_end, vocab, heading_bill, len(divisions) + 1)
                if d is not None:
                    used.add(i)
                    divisions.append(d)
                    last_end = i + 1
        if not is_header:
            i += 1
            continue
        yeas, nays, lines, j = _read_names(bl, i)
        # The Clerk's count, within the few blocks after the names.
        count, result, k = None, None, j
        while k < min(len(bl), j + 8):
            if bl[k][0] == "p":
                t = flat(bl[k][1])
                if count is None and (_CLERK.match(t) or re.match(r"For\b", t)):
                    count = clerk_count(t)
                    if count:
                        used.add(k)
                elif count is not None:
                    r = _RESULT.search(t)
                    if r:
                        result = r.group(1)
                        k += 1
                        break
                    if _SPEAKER.match(t) and not r:
                        break
            k += 1
        note = problem = None
        printed_y = count[0] if count else None
        printed_n = count[1] if count else None
        printed_a = count[2] if count else None
        abst = []
        if lines:
            # Lines after a table finish its list: they are placed by what
            # the Clerk's count leaves once the table's names are counted.
            rest = count
            if count and (yeas or nays):
                rest = tuple(None if c is None else c - len(got)
                             for c, got in zip(count, (yeas, nays, [])))
                if any(c is not None and c < 0 for c in rest[:2]):
                    problem, rest = "more names in the table than the Clerk counted", None
            ry, rn, abst, note, placed = _place_lines(lines, rest, vocab)
            yeas, nays = yeas + ry, nays + rn
            problem = problem or placed
        elif printed_a:
            problem = "abstentions counted in a table layout, which no record has shown yet"
        if count is None:
            problem = "no Clerk's count ('For, N. Against, M.') after the names"
        context = [flat(t) for kd, t in bl[last_end:i] if kd == "p" and flat(t)]
        d = _division(context, len(divisions) + 1, printed_y, printed_n, yeas, nays,
                      result, problem, note, heading_bill)
        if printed_a or abst:
            d["abstentions"], d["abs_labels"] = printed_a, abst
        divisions.append(d)
        last_end = k
        i = k
    if strays is not None:
        for k, (kd, v) in enumerate(bl):
            if kd == "p" and k not in used:
                t = flat(v)
                if _CLERK.match(t) and clerk_count(t):
                    strays.append(t[:120])
    voices = _voices(bl)
    return divisions, voices


_ROLL_CALL = re.compile(r"^\[?\s*The\s+Clerks?\s+call(?:s|ed)\s+the\s+roll\.?\s*\]?$", re.I)


def _headerless(bl, k, last_end, vocab, heading_bill, seq):
    """A division printed with no YEAS NAYS header: the lines of names
    between "[The Clerk called the roll.]" and the Clerk's count at block
    k (9 March 2026, the second division: Hansard goes straight from the
    roll call to "Hon. Brian Comer Claudia Chender"). Only between those
    two marks; anything else is left to the stray-count gap."""
    j = k - 1
    lines = []
    while j >= last_end:
        kd, v = bl[j]
        if kd != "p":
            return None
        if _FURNITURE.match(v):
            j -= 1
            continue
        if not _line_ok(v) or _ROLL_CALL.match(flat(v)):
            break
        lines.insert(0, v)
        j -= 1
    if not lines or j < last_end or not _ROLL_CALL.match(flat(bl[j][1])):
        return None
    count = clerk_count(bl[k][1])
    yeas, nays, abst, note, problem = _place_lines(lines, count, vocab)
    result = None
    for kd, v in bl[k + 1:k + 4]:
        r = _RESULT.search(flat(v)) if kd == "p" else None
        if r:
            result = r.group(1)
            break
    context = [flat(t) for kd, t in bl[last_end:j] if kd == "p" and flat(t)]
    note = "; ".join(x for x in ("no YEAS NAYS header printed: the names between the roll call and the "
                                 "Clerk's count", note) if x)
    d = _division(context, seq, count[0], count[1], yeas, nays, result, problem, note, heading_bill)
    if count[2] or abst:
        d["abstentions"], d["abs_labels"] = count[2], abst
    return d


def _division(context, seq, yeas, nays, yea_labels, nay_labels, result, problem, note, heading_bill):
    # The question: the last thing the Chair put before the bells.
    # The question: what the Chair put before the bells. The request for a
    # recorded vote is found first; the question is the Chair's "The motion
    # is ..." shortly before it, else the last paragraph before it that is
    # not procedure ("We have a dilatory motion on the floor for the bill to
    # recommit.", 5 April 2024).
    question = None
    tail = context[-15:]
    for t in reversed(tail):
        m = _PUT.search(t)
        if m:
            question = t[m.start():].strip()
            break
    reqs = [n for n, t in enumerate(context) if _REQUEST.search(t)]
    if question is None and reqs and _READING.search(context[reqs[-1]]):
        question = _LABEL_PREFIX.sub("", context[reqs[-1]]).strip()
    if question is None and reqs:
        for t in reversed(context[max(0, reqs[-1] - 4):reqs[-1]]):
            body = _LABEL_PREFIX.sub("", t).strip()
            if body and not _PROCEDURE.match(body):
                question = body
                break
    window = context[-40:]
    item = " ".join(window)
    q = question or ""
    bill = stage = None
    # The stage comes from the QUESTION only: a dilatory motion to recommit
    # a bill at third reading is a motion on that bill, not its third
    # reading (5 April 2024, Bill 419: defeated 21-28, then third reading
    # carried 28-17).
    rd = [(m.group(1), m.group(2)) for m in _READING.finditer(q)] + \
         [(m.group(2), m.group(1)) for m in _MOVE_READ.finditer(q)]
    only = _STAGE_ONLY.search(q)
    if rd:
        stage = rd[-1][0].title() + " Reading"
        bill = rd[-1][1]
    elif only:
        stage = only.group(1).title() + " Reading"
        bill = _bill_moved(window[-15:], only.group(1).lower()) or heading_bill
    else:
        stage = "Motion"
        b = _BILL.findall(q)
        if b:
            bill = b[-1]
        elif re.search(r"\bbill\b", q, re.I):
            # "the bill to recommit": the bill under debate
            near = [m.group(2) for m in _READING.finditer(" ".join(window[-15:]))]
            bill = near[-1] if near else heading_bill
        else:
            # "The Clerk will conduct a recorded vote on Bill No. 247." (25
            # March 2026: the question was put the day before): the bill,
            # never a stage.
            near = [m.group(1) for t in window[-6:] for m in _VOTE_ON_BILL.finditer(t)]
            bill = near[-1] if near else None
    low = q.lower()
    vote_on = ("subamendment" if "subamendment" in low or "sub-amendment" in low
               else "amendment" if "amendment" in low else "motion")
    return {"seq": seq, "yeas": yeas, "nays": nays, "yea_labels": yea_labels, "nay_labels": nay_labels,
            "question": (question or item[-1500:] or None), "item": item, "result": result,
            "vote_on": vote_on, "stage": stage, "bill_number": bill, "problem": problem, "note": note}


def _bill_moved(paras, stage_word):
    """The bill whose `stage_word` ('second'/'third') reading the nearest
    paragraph moved or named, from the end; None if none does."""
    for t in reversed(paras):
        hits = [m.group(2) for m in _READING.finditer(t) if m.group(1).lower() == stage_word] + \
               [m.group(1) for m in _MOVE_READ.finditer(t) if m.group(2).lower() == stage_word]
        if hits:
            return hits[-1]
    return None


# The Chair puts a reading: "The motion is for third reading of Bill No.
# 133.", "... to close third reading of Bill No. 348" (2023), "... to move
# second reading of Bill No. 419" (2024), "... for second reading on Bill No.
# 203" (2026), "The motion is that Bill No. 198 be read a third time".
_VOICE_Q = re.compile(r"The motion is (?:for|to close|to move)\s+(?:the\s+)?(second|third)\s+reading\s+(?:of|on)\s+"
                      r"Bill(?: No\.)?\s*(\d{1,3})\b", re.I)
_VOICE_Q2 = re.compile(r"The motion is that Bill(?: No\.)?\s*(\d{1,3})\b[^.]{0,120}?\bbe\s+(?:now\s+)?read\s+"
                       r"a\s+(second|third)\s+time", re.I)
# The mover's own words when the Chair puts it at once without restating it
# ("I move second reading of Bill No. 1." / "Would all those in favour ...",
# 7 May 2010).
_MOVER = re.compile(r"\bI (?:now )?move (?:the )?(second|third) reading of Bill(?: No\.)?\s*(\d{1,3})\b", re.I)
_IN_FAVOUR = re.compile(r"(?:all those in favour|those in favour|in favour of the motion)", re.I)
# Carried in so many words, or by the order that follows a carried reading
# ("Ordered that the bill be referred to Standing Committee on Public
# Bills.", 6 March 2025, with no "The motion is carried." printed).
_CARRIED = re.compile(r"The motion is (carried|defeated)|Ordered that (?:this|the) bill (?:be referred|do pass)", re.I)


def _voices(bl):
    """Second and third readings put and decided without a recorded vote."""
    paras = [flat(v) if k == "p" else "YEAS" if any(_is_header_row(r) for r in v[:1]) else ""
             for k, v in bl]
    out, seen = [], set()
    for idx, t in enumerate(paras):
        found = [(m.group(0), m.group(2), m.group(1)) for m in _VOICE_Q.finditer(t)] + \
                [(m.group(0), m.group(1), m.group(2)) for m in _VOICE_Q2.finditer(t)]
        if not found:
            m = _MOVER.search(t)
            nxt = next((x for x in paras[idx + 1:idx + 3] if x), "")
            if m and _IN_FAVOUR.search(nxt):
                found = [(m.group(0), m.group(2), m.group(1))]
        if not found:
            continue
        text, number, stage = found[-1]
        window = " ".join(paras[idx:idx + 6])
        after = window[window.find(text):]
        if _RECORDED.search(after.split("The motion is carried")[0]) or "YEAS" in after:
            continue
        if not _IN_FAVOUR.search(after):
            continue
        c = _CARRIED.search(after)
        if not c:
            continue
        key = (number, stage.lower())
        if key in seen:
            continue
        seen.add(key)
        outcome = (c.group(1) or "carried").lower()
        out.append({"bill_number": number, "stage": stage.title() + " Reading",
                    "result": "The motion is {0} (no recorded vote)".format(outcome)})
    # Bills called together and read at once: "Bill No. 84 - Animal
    # Protection Act." "Bill No. 85 - ..." then "The motions are carried."
    # and "Ordered that these bills do pass." (28 November 2011, 4 May 2012).
    # The order names the stage: "do pass" a third reading, "be referred"
    # a second.
    for idx, t in enumerate(paras):
        if not _BATCH_CARRIED.search(t):
            continue
        order = next((x for x in paras[idx + 1:idx + 3] if x), "")
        o = _BATCH_ORDER.search(order)
        if not o:
            continue
        stage = "Third Reading" if o.group(1).lower() == "do pass" else "Second Reading"
        k = idx - 1
        numbers = []
        while k >= 0 and (not paras[k] or _FURNITURE.match(paras[k]) or _BILL_HEADING.match(paras[k])):
            h = _BILL_HEADING.match(paras[k])
            if h:
                numbers.insert(0, h.group(1))
            k -= 1
        for number in numbers:
            key = (number, stage.split()[0].lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({"bill_number": number, "stage": stage,
                        "result": "The motions are carried (bills read together, no recorded vote)"})
    return out


_BATCH_CARRIED = re.compile(r"^(?:M[RS]\.?\s+SPEAKER|THE\s+SPEAKER|MADAM\s+SPEAKER)[^:]*:\s*The motions are carried\.?$", re.I)
_BATCH_ORDER = re.compile(r"^Ordered that these bills (do pass|be referred)", re.I)


# -- names ------------------------------------------------------------------------

def make_resolver(conn):
    """The run's resolver: Nova Scotia's NameResolver, with the reviewed
    label aliases of config/prov_record.yaml consulted after it fails."""
    return pn.Aliased(NameResolver(pn.Resolver.from_conn(conn, PROV)), pn.load_aliases(PROV))


class NameResolver:
    """prov_names.Resolver with Nova Scotia's three allowances, all still
    unique-or-nothing on the day, and the tally check still runs:

      * where the folded surname is ambiguous, the surname AS PRINTED, case
        and all, may decide it: the House prints Susan Leblanc and Colton
        LeBlanc ("Ms. Leblanc", "Mr. LeBlanc"), and so does the roster. Only
        an exact match on one candidate's printed surname counts;
      * a middle initial the roster does not carry is dropped ("John A.
        MacDonald");
      * a full name whose GIVEN name the roster does not know is tried as the
        surname alone. Hansard misprints given names ("Diane Timmins", "Suzie
        Hansen", 24 March 2025; "Hon. Alan MacMaster", 26 March 2024), and
        a reviewed alias for each would be a list without end; a misprinted
        SURNAME ("Hon. Timothy Hallman") still needs one."""

    def __init__(self, resolver):
        self.r = resolver

    def party_at(self, key, date, legislature=None):
        return self.r.party_at(key, date, legislature)

    def term_for(self, key, date, legislature=None):
        return self.r.term_for(key, date, legislature)

    def _try(self, raw, date, legislature):
        key, how = self.r.resolve(raw, date, legislature)
        if key or not how.startswith("ambiguous"):
            return key, how
        cands = [c.strip() for c in how.split(":", 1)[1].split(",")]
        tokens = re.sub(r"[^\w'’\- ]", " ", raw or "").split()
        exact = [c for c in cands if (self.r.members.get(c) or {}).get("surname")
                 and self.r.members[c]["surname"].split()[-1] in tokens]
        if len(exact) == 1:
            return exact[0], "surname (as printed, case and all)"
        return None, how

    def resolve(self, raw, date, legislature=None, document=None):
        key, how = self._resolve(raw, date, legislature)
        if key or not how.startswith("unknown"):
            return key, how
        # Two typesetting slips that are not names (the raw label keeps
        # them): an honorific run into the surname, "Mr.Whynott" and
        # "Mr.Scott" (22 April 2010), and a full stop after the surname,
        # "Mr. Ince." (10 April 2018).
        clean = re.sub(r"^((?:Hon|Mr|Mrs|Ms|Dr)\.)(?=[A-Z])", r"\1 ", (raw or "").strip())
        clean = re.sub(r"(?<=[a-z]{2})\.$", "", clean)
        if clean != (raw or "").strip():
            key2, how2 = self._resolve(clean, date, legislature)
            if key2:
                return key2, how2 + " (typesetting slip closed)"
        return key, how

    def _resolve(self, raw, date, legislature=None):
        key, how = self._try(raw, date, legislature)
        if key or how.startswith("ambiguous"):
            return key, how
        bare = re.sub(r"(?<=\s)[A-Z]\.\s+(?=\S)", "", raw or "")
        if bare != raw:
            key2, how2 = self._try(bare, date, legislature)
            if key2:
                return key2, how2 + " (middle initial dropped)"
        lab = pn.parse_label(raw)
        if len(lab.tokens) >= 2 and not lab.initials:
            words = pn._strip_honorifics((raw or "").split())
            for n in (1, 2):
                if len(words) <= n:
                    break
                key3, how3 = self._try(" ".join(words[-n:]), date, legislature)
                if key3:
                    return key3, "surname only (the given name as printed is not the roster's)"
                if how3.startswith("ambiguous"):
                    # Two members share the surname: the printed given name
                    # still names one of them by its INITIAL, as "Ms. K.
                    # Regan" would. Hansard prints "Mr. David Wilson" for
                    # Dave Wilson (the roster's name) beside "Mr. Gordon
                    # Wilson", 2013-2018: "D. Wilson" is one member.
                    initial = words[:-n][0][:1]
                    if initial.isalpha() and initial.isupper():
                        key4, _how4 = self._try("{0}. {1}".format(initial, " ".join(words[-n:])),
                                                date, legislature)
                        if key4:
                            return key4, "initial of the printed given name (the given name as printed " \
                                         "is not the roster's)"
                    return None, how3
        return key, how


def resolve_division(raw, resolver, date, legislature, document=None, division_key=None, reviewed=None):
    """(votes, ok, note). With `reviewed` (pn.ReviewedDivisions) and the
    division's key, a bare ambiguous label a reviewed hansard_labels entry
    names is settled first (config/prov_record.yaml); then British
    Columbia's elimination; then the tally check, as ever."""
    votes = []
    for position, labels in (("Yea", raw["yea_labels"]), ("Nay", raw["nay_labels"]),
                             ("Abstain", raw.get("abs_labels") or [])):
        for k, label in enumerate(labels, 1):
            key, how = resolver.resolve(label, date, legislature, document=document)
            votes.append({"position": position, "ordinal": k, "raw_label": label, "member_key": key,
                          "how": how,
                          "party_at_vote": resolver.party_at(key, date, legislature) if key else None})
    # British Columbia's rule (prov_bc.settle_by_elimination): an ambiguous
    # bare surname whose other candidate is placed in the same division is
    # the one left ("Mr. Wilson" beside "Mr. Gordon Wilson", 4 April 2014).
    from src.ingest.prov_bc import settle_by_elimination
    notes = []
    if reviewed is not None and division_key:
        notes += reviewed.settle(division_key, votes, getattr(resolver, "base", resolver), date, legislature)
    settle_by_elimination(votes, resolver, date, legislature)
    ok, note = ps.tally({"Yea": raw["yeas"], "Nay": raw["nays"], "Abstain": raw.get("abstentions")}, votes)
    if raw.get("problem"):
        ok, note = False, "; ".join(x for x in (raw["problem"], note) if x)
    if notes:
        note = "; ".join(x for x in [note] + notes if x)
    return votes, ok, note


# -- bills ------------------------------------------------------------------------

def parse_bill_list(html, base_url):
    """[{number, title, href, bill_type, text_url, status, last_activity, party}]"""
    out = []
    for row in _ROW.findall(html or ""):
        cells = _CELL.findall(row)
        if len(cells) < 4:
            continue
        link = re.search(r'<a href="([^"]*/bill-(\d+))"[^>]*>(.*?)</a>(.*)', cells[0], re.S)
        if not link:
            continue
        num = html_text(cells[1])
        text = re.search(r'href="([^"]+)"', cells[1])
        out.append({"number": num or link.group(2), "title": html_text(link.group(3)),
                    "href": urljoin(base_url, _html.unescape(link.group(1))),
                    "bill_type": html_text(link.group(4)) or None,
                    "text_url": urljoin(base_url, _html.unescape(text.group(1))) if text else None,
                    "status": html_text(cells[2]) or None, "last_activity": _date(html_text(cells[3])),
                    "party": html_text(cells[4]) if len(cells) > 4 else None})
    return out


_STAGE_ROWS = {"first reading": "First Reading", "second reading passed": "Second Reading",
               "third reading passed": "Third Reading", "royal assent": "Royal Assent",
               "committee of the whole house": "Committee of the Whole House",
               "reported to the house": "Committee Report"}


def parse_bill_page(html):
    """{sponsor, sponsor_key, bill_type, stages: [{stage, date, status}], texts}"""
    out = {"sponsor": None, "sponsor_key": None, "bill_type": None, "stages": [], "texts": []}
    i = (html or "").find("<h1")
    j = (html or "").find("pane-ns-leg-learn-more-links", i)
    body = (html or "")[i:j if j > 0 else None]
    sp = re.search(r'Introduced by[^<]*<a href="/members/profiles/([^"/]+)">([^<]+)</a>', body)
    if sp:
        out["sponsor_key"], out["sponsor"] = sp.group(1), html_text(sp.group(2))
    else:
        # "Introduced by Honourable Stephen McNeil, President of the
        # Executive Council" (Bill 133, 2019): a name with no link, so no key.
        nm = re.search(r"Introduced by\s+(?:the\s+)?(?:Honourable\s+|Hon\.\s+)?([^,<]+)", body)
        if nm:
            out["sponsor"] = html_text(nm.group(1))
    meta = re.search(r"<th>Bill No\.</th>.*?<tbody>\s*<tr[^>]*>(.*?)</tr>", body, re.S)
    if meta:
        cells = [html_text(c) for c in _CELL.findall(meta.group(1))]
        if len(cells) > 1:
            out["bill_type"] = cells[1] or None
    for row in _ROW.findall(body):
        cells = _CELL.findall(row)
        if len(cells) < 2:
            continue
        name = html_text(cells[0]).lower().strip()
        stage = _STAGE_ROWS.get(name)
        if stage:
            dates = [d for d in (_date(x) for x in re.findall(r"([A-Z][a-z]+ \d{1,2}, \d{4})",
                                                               html_text(cells[1]))) if d]
            if dates:
                out["stages"].append({"stage": stage, "date": dates[-1],
                                      "status": "passed" if stage != "First Reading" else "introduced"})
        for href in re.findall(r'href="(/legc/bills/[^"]+\.htm)"', cells[1]):
            out["texts"].append(urljoin(BASE, href))
    return out


def bill_text(ctx, url, slug_):
    raw = ctx.text(url, slug_, encoding="cp1252")
    if raw is None:
        return None
    return bill_body(raw)


def bill_body(raw):
    """The bill's own text from its page: <h1> to </main>, one passage a
    paragraph."""
    i = raw.find("<h1")
    j = raw.find("</main>", i)
    body = raw[i if i >= 0 else 0:j if j > 0 else None]
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", body)
    body = re.sub(r"(?i)</(p|h\d|div|tr|li)>|<br[^>]*>", "\n\n", body)
    return "\n".join(html_text(l) for l in body.split("\n\n") if html_text(l)) or None


def fetch_bills(ctx, legislature, session, tax, wl, want_pages=()):
    """Every bill of the session, classified on its TEXT. The bill's own
    page (stage dates, sponsor) only for a bill on our ground, a watched
    bill, or one in `want_pages` (named by a recorded division)."""
    url = BILLS.format(legislature, session)
    html = ctx.text(url, "bills-{0}-{1}".format(legislature, session))
    items = parse_bill_list(html, url) if html else []
    if html and not items:
        ctx.gap("ns bills {0}-{1}: no bills parsed from the listing".format(legislature, session))
    if ctx.dry_run:
        return {"bills": len(items)}
    texts = pages = 0
    out_of_time = False
    for it in items:
        key = ps.bill_key(PROV, legislature, session, it["number"])
        have = ctx.conn.execute("SELECT text_read, stages FROM prov_bills WHERE bill_key=?",
                                (key,)).fetchone()
        record = {"bill_key": key, "prov": PROV, "legislature": legislature, "session": session,
                  "number": it["number"], "title_en": it["title"], "bill_type": it["bill_type"],
                  "is_government": 1 if (it["bill_type"] or "").startswith("Government") else
                  (0 if it["bill_type"] else None), "page_url": it["href"],
                  "latest_stage": it["status"]}
        watched = pc.watched_bill(PROV, key) is not None
        # A bill whose listing shows activity since the window opened (or
        # any bill, without a window) is read; others keep what is stored.
        recent = not ctx.since or not it["last_activity"] or it["last_activity"] >= ctx.since
        if not out_of_time and ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("bill texts", texts))
            out_of_time = True
        text_read = bool(have and have[0])
        body = None
        if (not text_read or ctx.refresh) and (recent or watched or not have) and not out_of_time \
                and it["text_url"]:
            body = bill_text(ctx, it["text_url"], "billtext-{0}-{1}-{2}".format(
                legislature, session, it["number"]))
            texts += 1 if body else 0
            if not body:
                ctx.gap("{0}: the bill text {1} gave no text; classified on its title".format(
                    key, it["text_url"]))
        if body or not text_read:
            res = pc.classify(tax, wl, PROV, title=it["title"], texts=[body] if body else [], bill_key=key)
            ps.store_bill(ctx.conn, dict(record, text_url=it["text_url"], text_read=1 if body else 0,
                                         areas=res.areas, matched_terms=res.terms, tier=res.tier,
                                         excerpt=res.excerpt))
        else:
            ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
        areas, a_terms, a_tier = ps.bill_areas(ctx.conn, key)
        a_excerpt = (ctx.conn.execute("SELECT excerpt FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
                     or (None,))[0]
        need_page = watched or pc.on_our_ground(areas) or it["number"] in want_pages
        page_fresh = bool(have and have[1] and have[1] != "[]") and not (recent and ctx.since)
        if need_page and not page_fresh and not out_of_time:
            page_html = ctx.text(it["href"], "bill-{0}-{1}-{2}".format(legislature, session, it["number"]))
            if page_html:
                pages += 1
                page = parse_bill_page(page_html)
                if not page["stages"]:
                    ctx.gap("{0}: no stages parsed from the bill page {1}".format(key, it["href"]))
                latest = [x for x in page["stages"] if x["date"]]
                ps.store_bill(ctx.conn, dict(
                    record, sponsor=page["sponsor"], sponsor_key=page["sponsor_key"],
                    bill_type=page["bill_type"] or it["bill_type"], stages=page["stages"],
                    latest_stage=latest[-1]["stage"] if latest else it["status"],
                    royal_assent=next((x["date"] for x in page["stages"] if x["stage"] == "Royal Assent"),
                                      None),
                    # the classification already stored is passed back, so a
                    # title-only one is not wiped by this page-only write
                    text_read=1 if (body or text_read) else 0, areas=areas, matched_terms=a_terms,
                    tier=a_tier, excerpt=a_excerpt))
    ctx.conn.commit()
    ctx.log("  ns bills {0}-{1}: {2} listed, {3} text(s) read, {4} bill page(s) read".format(
        legislature, session, len(items), texts, pages))
    return {"bills": len(items), "bill_texts": texts, "bill_pages": pages}


# -- a sitting --------------------------------------------------------------------

def clear_record(conn, url):
    """Delete the divisions, voice decisions and votes stored from one
    Hansard page."""
    keys = [r[0] for r in conn.execute(
        "SELECT division_key FROM prov_divisions WHERE prov=? AND source_url=?", (PROV, url))]
    for k in keys:
        conn.execute("DELETE FROM prov_votes WHERE division_key=?", (k,))
        conn.execute("DELETE FROM prov_division_bills WHERE division_key=?", (k,))
        conn.execute("DELETE FROM prov_divisions WHERE division_key=?", (k,))
    return len(keys)


def read_sitting(ctx, legislature, session, rec, resolver, wl, reviewed=None):
    """Read one sitting's Hansard. Returns (divisions, gaps_in_it)."""
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
    strays = []
    base = getattr(resolver, "base", resolver)
    divisions, voices = parse_hansard(raw, vocab=base.surname_vocab() if hasattr(base, "surname_vocab") else None,
                                      strays=strays)
    gaps = 0
    seq_prefix = "{0}.".format(rec["part"]) if rec.get("part") else ""
    # A record read again replaces everything stored from it: a division an
    # older parser stored under another seq, or split in two, must not
    # outlive the re-read.
    clear_record(ctx.conn, url)
    for t in strays:
        # The record says a division happened that the parser did not read:
        # a gap, never 'ok' (12 November 2012's "YEAS" inside its cell;
        # 17 October 2022's three-column list with abstentions).
        gaps += 1
        ctx.gap("{0}: the Clerk's count {1!r} follows no list of names read; a recorded division "
                "was not parsed".format(skey, t[:80]))
    if reviewed is None:
        reviewed = pn.ReviewedDivisions.load(PROV)
    recorded = set()
    for d in divisions:
        seq = seq_prefix + str(d["seq"])
        dkey = ps.division_key(PROV, legislature, session, date, seq)
        votes, ok, note = resolve_division(d, resolver, date, legislature, document=url,
                                           division_key=dkey, reviewed=reviewed)
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        if bkey and d["stage"] in STAGE_CODE:
            recorded.add((bkey, d["stage"]))
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        inherit = pc.Result(b_areas, b_terms, b_tier) if b_areas else None
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["question"]], bill_key=bkey, inherit=inherit)
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": date, "seq": seq, "kind": "recorded", "question": d["question"],
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "abstentions": d.get("abstentions"), "source_url": url,
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0,
            "tally_note": "; ".join(x for x in (note, d.get("note")) if x) or None, "votes": votes})
    nvoice = 0
    for v in voices:
        bkey = ps.bill_key(PROV, legislature, session, v["bill_number"])
        if (bkey, v["stage"]) in recorded:
            continue
        nvoice += 1
        areas, terms, tier = ps.bill_areas(ctx.conn, bkey)
        ps.store_division(ctx.conn, {
            "division_key": ps.division_key(PROV, legislature, session, date, "{0}v{1}-{2}".format(
                seq_prefix, v["bill_number"], STAGE_CODE[v["stage"]])),
            "prov": PROV, "legislature": legislature, "session": session, "date": date,
            "seq": "v", "kind": "voice", "bill_key": bkey, "stage": v["stage"],
            "result": v["result"], "source_url": url, "areas": areas, "matched_terms": terms,
            "tier": tier})
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions), voice=nvoice,
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return len(divisions), gaps


def check_listing_stages(ctx, legislature, session, read_dates):
    """Every second or third reading a bill page dates to a day whose
    Hansard was read must be in that Hansard, divided or on voice."""
    misses = 0
    for key, stages in ctx.conn.execute(
            "SELECT bill_key, stages FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
            (PROV, legislature, session)).fetchall():
        for st in json.loads(stages or "[]"):
            if st.get("stage") not in STAGE_CODE or st.get("date") not in read_dates:
                continue
            hit = ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? AND stage=?",
                (key, st["date"], st["stage"])).fetchone()[0]
            if not hit:
                misses += 1
                ctx.gap("{0}: the bill page says {1} passed on {2}; that day's Hansard gave neither a "
                        "recorded division nor a voice decision for it".format(key, st["stage"], st["date"]))
    return misses


# -- owed sittings ------------------------------------------------------------------

# Every sitting stored 'ok' by a parser older than this date is read once more.
# The 2010 backfill (CI runs 37076568654 and 37108083021, 3 October 2026) read
# with the parser of 2 October, which closed no paragraph the record left
# open (late 2011: 14, 25 and 28 November stored 'ok' and EMPTY), missed a
# header inside its cell (5 November 2012, Bill 94's second reading), a list
# printed with no header (9 March 2026) and a three-column list (17 October
# 2022), and knew one form of the Clerk's count. Neither a gap nor the bills
# cross-check points at all of them, so the repair is by date.
REREAD_BEFORE = "2026-10-08"


def owe_stale(ctx, legislature, session, records):
    """Make OWED every sitting of the window stored 'ok' before
    REREAD_BEFORE. Returns how many."""
    owed = 0
    for rec in records:
        owed += ctx.conn.execute(
            "UPDATE prov_sittings SET status='owed' WHERE sitting_key=? AND status='ok' AND read_at < ?",
            (ps.sitting_key(PROV, legislature, session, rec["date"], rec.get("part")), REREAD_BEFORE)).rowcount
    ctx.conn.commit()
    if owed:
        ctx.log("  ns {0}-{1}: {2} sitting(s) stored 'ok' by the parser before {3}; read again".format(
            legislature, session, owed, REREAD_BEFORE))
    return owed


def owe_listed(ctx, legislature, session, records):
    """The lasting, targeted repair: a sitting stored 'ok' on whose day a
    bill page dates a second or third reading the store holds neither as a
    division nor on voice is made OWED, so the run reads it again (the
    cross-check after the bills makes it a gap if it is still missing).
    Returns how many."""
    days = set()
    for key, stages in ctx.conn.execute(
            "SELECT bill_key, stages FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
            (PROV, legislature, session)).fetchall():
        for st in json.loads(stages or "[]"):
            if st.get("stage") not in STAGE_CODE or not st.get("date"):
                continue
            hit = ctx.conn.execute("SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? AND stage=?",
                                   (key, st["date"], st["stage"])).fetchone()[0]
            if not hit:
                days.add(st["date"])
    owed = 0
    for rec in records:
        if rec["date"] in days:
            owed += ctx.conn.execute(
                "UPDATE prov_sittings SET status='owed' WHERE sitting_key=? AND status='ok'",
                (ps.sitting_key(PROV, legislature, session, rec["date"], rec.get("part")),)).rowcount
    ctx.conn.commit()
    if owed:
        ctx.log("  ns {0}-{1}: {2} sitting(s) 'ok' but missing a reading their bill pages date to them; "
                "read again".format(legislature, session, owed))
    return owed


# -- the run ------------------------------------------------------------------------

def inherit_bill_areas(conn, legislature, session):
    """Give every stored division of the session its bill's TEXT
    classification (merged, never replaced): the sittings are read before
    the bills, so the clock goes on the divisions first. Returns the number
    of divisions updated."""
    n = 0
    for dkey, bkey, areas, terms, tier in conn.execute(
            "SELECT division_key, bill_key, areas, matched_terms, tier FROM prov_divisions "
            "WHERE prov=? AND legislature=? AND session=? AND bill_key IS NOT NULL",
            (PROV, legislature, session)).fetchall():
        b_areas, b_terms, b_tier = ps.bill_areas(conn, bkey)
        if not b_areas:
            continue
        have = pc.Result(json.loads(areas or "[]"), json.loads(terms or "[]"), tier)
        got = have.merge(pc.Result(b_areas, b_terms, b_tier))
        if got.areas != have.areas or got.terms != have.terms:
            conn.execute("UPDATE prov_divisions SET areas=?, matched_terms=?, tier=? WHERE division_key=?",
                         (json.dumps(got.areas), json.dumps(got.terms), got.tier, dkey))
            n += 1
    return n


CRAWL_DELAY = 10.0


def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    """Roster, then the sittings (the divisions are what the clock is
    spent on first), then the bills, whose text classification the
    divisions then inherit, then the cross-check and party at the vote."""
    legislature, sess = parse_session(session)
    # robots.txt asks for 10 s and prov_fetch honours it; if robots.txt does
    # not answer, the 10 s it has always asked for still stand.
    if hasattr(ctx.client, "set_host_throttle"):
        ctx.client.set_host_throttle("nslegislature.ca", CRAWL_DELAY)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    records = fetch_listing(ctx, legislature, sess)
    if records is None:
        return {"records_listed": 0}
    if not records:
        ctx.gap("ns Hansard {0}: no sittings parsed from the listing".format(session))
    records = [r for r in records if ctx.in_window(r["date"])]
    stats = {"records_listed": len(records)}
    if roster:
        page = ctx.text(DATES.format(legislature), "assembly-dates-{0}".format(legislature))
        dates = (parse_assembly_dates(page, legislature) if page else {}).get(sess) or {}
        if page and not dates.get("start"):
            ctx.gap("ns {0}: no dates for the session on {1}".format(session, DATES.format(legislature)))
        stats["members"] = fetch_roster(ctx, legislature, sess, (dates.get("start"), dates.get("end")))
    if ctx.dry_run:
        if bills:
            stats.update(fetch_bills(ctx, legislature, sess, ctx.tax, wl))
        return stats
    resolver = make_resolver(ctx.conn)
    reviewed = pn.ReviewedDivisions.load(PROV)
    stats["owed_stale"] = owe_stale(ctx, legislature, sess, records)
    stats["owed_listed"] = owe_listed(ctx, legislature, sess, records)
    read = divs = gaps = 0
    read_dates = set()
    for rec in records:
        if not ctx.refresh and ps.sitting_done(ctx.conn, rec["url"]):
            read_dates.add(rec["date"])
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        n, g = read_sitting(ctx, legislature, sess, rec, resolver, wl, reviewed=reviewed)
        read += 1
        divs += n
        gaps += g
        status = ctx.conn.execute("SELECT status FROM prov_sittings WHERE record_url=?",
                                  (rec["url"],)).fetchone()
        if status and status[0] != "unreadable":
            read_dates.add(rec["date"])
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps})
    if bills and not records:
        # A bill is introduced, read and assented to on a sitting day: a
        # window with no sitting (a recess week; 61-1, prorogued in March 2010
        # after its last sitting in November 2009) has no bill news, and a
        # session's bills cost a request each at ten seconds.
        ctx.log("  ns {0}: no sitting in the window; the bills are not read".format(session))
        bills = False
    if bills:
        # The pages of the bills a recorded division named are read too,
        # for the cross-check and the sponsor.
        named = {k.rsplit("/", 1)[1] for (k,) in ctx.conn.execute(
            "SELECT DISTINCT bill_key FROM prov_divisions WHERE prov=? AND legislature=? AND session=? "
            "AND kind='recorded' AND bill_key IS NOT NULL", (PROV, legislature, sess))}
        stats.update(fetch_bills(ctx, legislature, sess, ctx.tax, wl, want_pages=named))
        stats["inherited"] = inherit_bill_areas(ctx.conn, legislature, sess)
        stats["listing_misses"] = check_listing_stages(ctx, legislature, sess, read_dates)
    n, with_party = ps.refresh_party(ctx.conn, PROV, pn.Resolver.from_conn(ctx.conn, PROV), legislature, sess)
    stats["votes_with_party"] = "{0}/{1}".format(with_party, n)
    ctx.conn.commit()
    return stats
