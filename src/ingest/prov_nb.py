"""Legislative Assembly of New Brunswick: roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov nb. Scope: docs/canada-provinces-scope.md
(New Brunswick: value 4, difficulty 3). robots.txt disallows nothing but
sets `crawl-delay: 10`: prov_fetch reads it and the client waits 10 seconds
between requests to legnb.ca (HttpClient.set_host_throttle), so a session
of ~50 journals plus its bill pages takes the best part of half an hour.
No WAF.

BILINGUAL. Every record exists in English and French ("e" and "f" file
suffixes; bill texts "-e.htm"). Only the English files are read: English is
the text matched against the taxonomy, and reading both would count every
division twice.

  * LISTING. /en/house-business/journals/<leg>/<sess> lists each sitting's
    Journal with its date, and the session's "Journals (Compiled)". File
    names are taken from it, never constructed: they carry the sitting
    number, YYMMDD and sometimes a revision suffix ("47230615e2.pdf"), and
    the hrefs use Windows backslashes.
  * ROSTER, DATED BY SESSION. The site publishes only the CURRENT members
    (/en/members/current, with party). For a past session the dated roster
    is the compiled Journal's own "MEMBERS OF THE LEGISLATIVE ASSEMBLY"
    page: constituency and member for that session, with footnotes for
    by-elections ("By-election April 24, 2023, vice Denis Landry resigned
    November 30, 2022"). A term runs from the session's first sitting (or
    the by-election) to its last sitting (or the resignation). The page
    prints NO PARTY. The compiled Journal's header names its session and is
    checked: the 60-3 listing links a file named for 2022-2023.
  * PARTY AT THE VOTE, DATED TO THE SITTING. Each daily Hansard prints a
    "LIST OF MEMBERS BY CONSTITUENCY" with party codes and a legend
    ("Fredericton West-Hanwell (I) Dominic Cardy", 15 June 2023). For every
    day with a recorded division that list is read (fetch_party_lists) and
    stored as party-only terms spanning the sittings seen; party_at_vote is
    then written from them (prov_store.refresh_party). Today's party from
    /en/members/current is never used for a vote: it would misattribute
    every floor-crosser (Cardy left the PC caucus in October 2022).
  * PARTY BEFORE HANSARD (Christopher, 7 October 2026). The 58th
    Legislature's votes before its first Hansard member list (58-1, 58-2)
    take the party each member was elected under, from the Chief Electoral
    Officer's reports tabled in the House: the general election of 22
    September 2014 (58/1/tabled_documents/3/GeneralElectionGenerale2014.pdf)
    and the by-elections of Saint John East, 17 November 2014 (58/1/
    tabled_documents/3/SaintJohnEastByElectionPartielleSaintJohnEst2014.pdf)
    and Carleton, 5 October 2015 (58/2/tabled_documents/1/
    ByElectionPartielle-Carleton.pdf), carried only to the first Hansard list
    that agrees (fetch_election_results, carry_election_party). The 57th
    stays NULL: its 2010 report is not tabled on legnb.ca and Elections NB
    answers 403.
  * LABEL ALIASES. A typo in a division list ("Mr. Russel", 20 November
    2025) is cleared only by a reviewed entry in config/prov_record.yaml,
    after the normal resolver fails, on that day and in that Journal.
  * BILLS. /en/legislation/bills/<leg>/<sess> gives every bill with its
    stage dates ("2nd Reading Passed: 5/11/2023"); each bill page gives the
    type, sponsor and the bill-text documents, the English HTML preferred.
    Bills are classified on that TEXT, per passage (src/prov_classify.py).
  * DIVISIONS. "on the following recorded division: YEAS - 26", then three
    columns of "Hon. Mr. Holder", "Ms. Holt", "Mr. J. LeBlanc" (pypdf reads
    them row by row), then "NAYS - 20". The printed totals are the tally
    check.
  * VOICE. "the question being put that Bill 52 be now read a third time,
    it was resolved in the affirmative." with no division, and "The
    following Bills were read a third time: Bill 42, ...". Stored as
    kind='voice': "passed on voice, no member record".
  * CROSS-CHECK. Every second or third reading the bills listing dates to a
    day whose Journal was read must be found in that Journal, as a division
    or as a voice decision. A miss is a gap, said out loud.

Hansard (the bilingual "b" PDFs, two interleaved columns) is not read; one of
them, 20 November 2025, is served truncated. Any record that is truncated or
not a PDF is a gap with status 'unreadable', never an empty day.
"""

from __future__ import annotations

import datetime
import html as _html
import json
import re
from urllib.parse import quote, urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import (Unreadable, html_text, join_fragments, pdf_rows, pdf_text, sessions_sorted, slug,
                            split_columns, year_span)

PROV = "nb"
CURRENT_SESSION = "61-2"
BASE = "https://www.legnb.ca"
JOURNALS = BASE + "/en/house-business/journals/{0}/{1}"
BILLS = BASE + "/en/legislation/bills/{0}/{1}"
MEMBERS = BASE + "/en/members/current"

STAGE_CODE = {"First Reading": "1r", "Second Reading": "2r", "Third Reading": "3r"}


def parse_session(code):
    m = re.match(r"^(\d{2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("New Brunswick session must look like 60-2, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def _current_legislature():
    return parse_session(CURRENT_SESSION)[0]


def _date(text, fmts=("%B %d, %Y", "%m/%d/%Y")):
    t = re.sub(r"\s+", " ", (text or "").strip())
    for f in fmts:
        try:
            return datetime.datetime.strptime(t, f).date().isoformat()
        except ValueError:
            continue
    return None


def _ascii_url(path):
    """Percent-encode only what is not printable ASCII ('é' -> '%C3%A9'), so
    every other URL stays exactly as before."""
    return re.sub(r"[^\x21-\x7e]", lambda m: quote(m.group(0)), path)


def _url(href):
    """A listing href as a URL: backslashes turned, spaces quoted, nothing
    else touched."""
    path = _html.unescape(href).replace("\\", "/")
    return urljoin(BASE, quote(path, safe="/:%?=&#"))


# -- the journals listing ---------------------------------------------------

_LINK = re.compile(r'<a[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', re.S | re.I)
# '47230615e2.pdf' (sitting 47, 15 June 2023, revision 2); before the 57th
# Legislature's second session the file carries no sitting number:
# '100416e.pdf' (56-4, 16 April 2010), '110610e.pdf' (57-1).
_DAILY = re.compile(r"/(\d{1,3})?(\d{6})([ef])(\d*)\.pdf$", re.I)
# The compiled Journal is labelled "Journals (Compiled)" from 58-4 on and
# "Journals 2011 - 2012" before it (57-2 to 58-3); 56-4 and 57-1 list none.
_COMPILED = re.compile(r"^journals?\s*(?:\(compiled\)|\d{4}\s*[-–]\s*\d{4})\s*$", re.I)


def list_records(html):
    """{'daily': [{date, url, sitting, revision}], 'compiled': url|None,
    'french_only': [{date, url}]} from one session's journals listing.
    English files only; where a date is listed twice the highest revision is
    kept. A date the English listing links ONLY to a French file ('f') is
    returned in french_only: it is never read (English is the record we
    classify), and the caller says so as a gap. A link outside the
    session's journals folder (60-1 lists "October 4, 2022" as
    qp_transcripts/87221003e.pdf) is returned in not_journal, never read
    as a Journal."""
    daily, compiled, french, other = {}, None, {}, []
    section = (html or "")
    start = section.find('class="file-list"')
    if start >= 0:
        section = section[start:]
    for href, inner in _LINK.findall(section):
        label = html_text(inner)
        url = _url(href)
        if _COMPILED.match(label):
            compiled = url
            continue
        m = _DAILY.search(url)
        if not m:
            continue
        date = _date(label)
        if not date:
            ymd = m.group(2)
            date = "20{0}-{1}-{2}".format(ymd[:2], ymd[2:4], ymd[4:])
        if "/journals/" not in url.lower():
            other.append({"date": date, "url": url})
            continue
        if m.group(3).lower() == "f":
            french.setdefault(date, {"date": date, "url": url})
            continue
        rev = int(m.group(4) or 1)
        have = daily.get(date)
        if have is None or rev > have["revision"]:
            daily[date] = {"date": date, "url": url, "sitting": int(m.group(1)) if m.group(1) else None,
                           "revision": rev}
    return {"daily": sorted(daily.values(), key=lambda r: r["date"]), "compiled": compiled,
            "french_only": sorted((v for d, v in french.items() if d not in daily), key=lambda r: r["date"]),
            "not_journal": sorted((v for v in other if v["date"] not in daily), key=lambda r: r["date"])}


# The journals page's own session selector: one block per legislature
# ('id="leg_60"'), each session a link ("journals/57/1" ... "(2010-2011)")
# except the page's own, printed as <span class="selected">.
_SEL_TOKEN = re.compile(
    r'id="leg_(?P<leg>\d+)"'
    r'|journals/(?P<lleg>\d+)/(?P<lsess>\d)"\s*>\s*<span>[^(<]*(?:<sup>[^<]*</sup>)?[^(<]*\((?P<lyears>[^)]*)\)'
    r'|class="selected">\s*(?P<ssess>\d)\s*(?:<sup>[^<]*</sup>)?[^(<]*\((?P<syears>[^)]*)\)')
_SPAN = re.compile(r"^\s*(\d{4})\s*(-)?\s*(\d{4})?\s*$")


def _years(code, text):
    """'2010-2011', '2018' (one year) or '2025-' (still open)."""
    m = _SPAN.match(text or "")
    if not m:
        return {"code": code, "start": None, "end": None}
    return year_span(code, m.group(1), m.group(3), open_ended=bool(m.group(2)) and not m.group(3))


def parse_sessions(html):
    """Every session in the journals page's selector, back to the 53rd
    Legislature (1995), oldest first."""
    out, leg = [], None
    for m in _SEL_TOKEN.finditer(html or ""):
        if m.group("leg"):
            leg = int(m.group("leg"))
        elif m.group("lleg"):
            out.append(_years("{0}-{1}".format(int(m.group("lleg")), int(m.group("lsess"))), m.group("lyears")))
        elif m.group("ssess") and leg:
            out.append(_years("{0}-{1}".format(leg, int(m.group("ssess"))), m.group("syears")))
    return sessions_sorted(out)


def list_sessions(ctx):
    legislature, session = parse_session(CURRENT_SESSION)
    url = JOURNALS.format(legislature, session)
    html = ctx.text(url, "journals-sessions-{0}-{1}".format(legislature, session))
    out = parse_sessions(html)
    if html and not out:
        ctx.gap("nb: no session selector parsed from {0}".format(url))
    return out


# -- rosters ----------------------------------------------------------------

_CARD = re.compile(
    r'<div class="member-card[^"]*"[^>]*>.*?<li class="member-card-description-name">\s*'
    r'(?:<a href="([^"]*)">)?\s*<h3>(.*?)</h3>.*?'
    r'<li class="member-card-description-party">(.*?)</li>.*?'
    r'<li class="member-card-description-riding">(.*?)</li>', re.S)


def clean_given(given):
    """'Jean-Claude (JC)' -> 'Jean-Claude'; 'William (Bill)' -> 'William'."""
    return re.sub(r"\s+", " ", re.sub(r"\([^()]*\)", " ", given or "")).strip()


def member_key(given, surname):
    """slug of the first given name that is not an initial, plus the surname:
    'K. Dorothy Shephard' -> 'dorothy-shephard', 'Mary E. Wilson' and
    'Wilson, Mary' -> 'mary-wilson', so the current page and a compiled
    roster agree on one person."""
    toks = [t for t in re.split(r"\s+", clean_given(given)) if t]
    first = next((t for t in toks if not pn._INITIALS.match(t)), toks[0] if toks else "")
    return slug(first + " " + surname)


def parse_current_members(html):
    """[{key, surname, given, name, party, riding, href}] from /en/members/current."""
    out = []
    for href, name, party, riding in _CARD.findall(html or ""):
        name = html_text(name)
        surname, _, given = name.partition(",")
        surname, given = surname.strip(), clean_given(given)
        out.append({"key": member_key(given, surname), "surname": surname, "given": given,
                    "name": (given + " " + surname).strip(), "party": html_text(party) or None,
                    "riding": html_text(riding) or None, "href": urljoin(BASE, href) if href else None})
    return out


_ORD_UNITS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
              "seventh": 7, "eighth": 8, "ninth": 9}
_ORD_TENS = {"fiftieth": 50, "sixtieth": 60, "seventieth": 70, "fortieth": 40}
_TENS = {"fifty": 50, "sixty": 60, "seventy": 70, "forty": 40}


def ordinal_value(word):
    """'Sixtieth' -> 60, 'Sixty-First' -> 61, 'Second' -> 2."""
    w = (word or "").lower().replace("–", "-").strip()
    if w in _ORD_UNITS:
        return _ORD_UNITS[w]
    if w in _ORD_TENS:
        return _ORD_TENS[w]
    head, _, tail = w.partition("-")
    if head in _TENS and tail in _ORD_UNITS:
        return _TENS[head] + _ORD_UNITS[tail]
    return None


_SESSION_HEAD = re.compile(r"\b([A-Za-z]+)\s+Session\s+of\s+the\s+([A-Za-z\-–]+)\s+Legislative\s+Assembly", re.I)
_DATE_TXT = r"(\w+\s+\d{1,2},\s*\d{4})"
# The footnotes under the members page, every form printed 2011-2023:
#   "* By-election June 25, 2012, vice Hon. Margaret-Ann Blaney resigned May 25, 2012."
#   "* Donald Arseneault resigned December 1, 2017."           (58-4: the seat is "Vacant")
#   "*Hon. Gregory Thompson, P.C.deceased September 10, 2019."  (59-2: after the session)
#   "* Lisa Harris resigned August 16, 2021."   (60-1: marked on Réjean Savoie's row, her successor)
#   "*Charlotte-Campobello named Saint Croix, October 31, 2016" (58-3: a riding renamed)
_FOOTNOTE = re.compile(
    r"^(\*+)\s*By-election\s+" + _DATE_TXT + r",\s*vice\s+(.+?),?\s+"
    r"(resigned|deceased|died|appointed[^,]*?)\s*(?:on\s+)?" + _DATE_TXT + r"\.?\s*$", re.I)
_FOOT_LEFT = re.compile(
    r"^(\*+)\s*(.+?),?\s*(resigned|deceased|died)\s*(?:on\s+)?" + _DATE_TXT + r"\.?\s*$", re.I)
_FOOT_RENAMED = re.compile(r"^(\*+)\s*(.+?)\s+named\s+(.+?),?\s+" + _DATE_TXT + r"\.?\s*$", re.I)
_HEADS = ("Constituency", "Member", "Residence")
_HONORIFIC = re.compile(r"^(?:Hon\.|The Honourable|Dr\.)\s+")
_POSTNOMINAL = re.compile(r",?\s*(?:K\.C\.|Q\.C\.|P\.C\.)\s*$")
# A member as the page prints one: words that start with a capital
# ("Hédard Albert", "John W. Betts", "Marie-Claude Blais"). Anything else
# ("0DGHODLQH'XEp", a font the PDF cannot map) is not a name, and the row
# is a problem unless a reviewed `roster_rows` entry reads it.
_NAME = re.compile(r"^[A-ZÀ-Þ][\w’'.\-]*(?:\s+[A-ZÀ-Þ][\w’'.\-]*)+$")


def clean_member(text):
    """'Hon. Marie-Claude Blais, Q.C.' -> 'Marie-Claude Blais'; 'Dr. Jim
    Parrott' -> 'Jim Parrott'; spaced hyphens closed ('Belle -Baie')."""
    m = re.sub(r"\s*-\s*", "-", (text or "").strip())
    m = _POSTNOMINAL.sub("", m).strip()
    while _HONORIFIC.match(m):
        m = _HONORIFIC.sub("", m).strip()
    return _POSTNOMINAL.sub("", m).strip()


def _row_text(frags):
    return re.sub(r"\s+", " ", " ".join(f[2] for f in frags)).strip()


def _space_columns(frags):
    """The 2011-2016 members pages draw each row as ONE fragment with the
    columns padded by runs of spaces ('Albert      Wayne Steeves      Lower
    Coverdale'). Returns the cells, or None for a row that is not one
    fragment."""
    if len(frags) != 1:
        return None
    return [c.strip() for c in re.split(r"\s{2,}", frags[0][2].strip()) if c.strip()]


def load_roster_rows(path=None):
    """`roster_rows:` (nb) -- one printed row of one compiled Journal's
    members page, read by a person: a row drawn with no gap between
    constituency and member, in a font the PDF cannot map, or with a
    misprinted name. Needs document, printed, member, verified_against and
    why; a member row needs `riding` too, and may quote the row's own
    `footnote` (which binds it where the page prints one mark twice). An
    entry whose `printed` is a FOOTNOTE ("*** By-election ..., vice Daniel
    Guitar resigned ...") gives the member the footnote misprints. A row may
    carry `elected:`, the by-election date of a successor whose footnote
    names only the vacancy; it can only move the term's start later."""
    out = pn._reviewed(PROV, "roster_rows", ("printed", "document", "member", "verified_against", "why"), path)
    for a in out:
        if not str(a["printed"]).lstrip().startswith("*") and not a.get("riding"):
            raise ValueError("nb roster_rows entry {0!r} lacks riding".format(a["printed"]))
    return out


def roster_rows(raw):
    """The rows of the compiled Journal's members page, or [] when there is
    none in its first five pages."""
    for page in pdf_rows(raw, pages=range(5)):
        if any("MEMBERS OF THE LEGISLATIVE ASSEMBLY" in join_fragments(fr) for _, fr in page):
            return [[list(f) for f in fr] for _, fr in page]
    return []


def parse_compiled_roster(rows, reviewed=None, document=None):
    """{'session': (leg, sess)|None, 'members': [...], 'vacant': [...],
    'notes': [...], 'problems': [...]}

    rows: one page as [[(x0, x1, text), ...], ...] lines (roster_rows).
    reviewed: `roster_rows` entries (load_roster_rows). An entry applies
    only to its own document and only while the row is printed exactly as
    it quotes it.

    Two layouts: columns by x-position (the heading's three fragments give
    the edges; 2017 on) and columns padded by spaces (one fragment a row;
    2011-2016). A row neither reads is a problem, never a guess."""
    out = {"session": None, "members": [], "notes": [], "problems": [], "vacant": []}
    by_row = {}
    for a in reviewed or []:
        if document is not None and a["document"] == document:
            by_row[re.sub(r"\s+", " ", str(a["printed"])).strip()] = a
    edges = None
    carry = ""          # a constituency wrapped onto the next row ("Bathurst East-Nepisiguit-", 58-2)
    for frags in rows:
        frags = [tuple(f) for f in frags]
        line = join_fragments(frags)
        if out["session"] is None:
            m = _SESSION_HEAD.search(line)
            if m:
                sess, leg = ordinal_value(m.group(1)), ordinal_value(m.group(2))
                if sess and leg:
                    out["session"] = (leg, sess)
        if edges is None:
            heads = [f for f in frags if f[2].strip() in _HEADS]
            if len(heads) == 3:
                edges = [heads[0][0], heads[1][0], heads[2][0]]
            elif _space_columns(frags) == list(_HEADS):
                edges = "spaces"
            continue
        if line.startswith("OFFICERS OF THE ASSEMBLY"):
            edges = False
            continue
        if edges is False:
            if line.startswith("*"):
                note = _footnote(line)
                fix = by_row.get(_row_text(frags)) or by_row.get(line)
                if note and fix and note["kind"] in ("by-election", "left"):
                    # a misprinted name in the footnote itself (60-2: "vice
                    # Daniel Guitar"): the reviewed reading of who left
                    note["vice" if note["kind"] == "by-election" else "who"] = clean_member(str(fix["member"]))
                    note["reviewed"] = True
                if note:
                    out["notes"].append(note)
                else:
                    out["problems"].append("footnote not understood: {0!r}".format(line))
            continue
        text = _row_text(frags)
        fact = by_row.get(text)
        if fact:
            riding, member = str(fact["riding"]), str(fact["member"])
            marks = re.findall(r"\*+", text)
            mark = marks[0] if marks else None
        else:
            if edges == "spaces":
                cells = _space_columns(frags) or []
                if len(cells) == 1 and cells[0].endswith("-") and not carry:
                    carry = cells[0]
                    continue
                if carry and len(cells) == 3:
                    cells[0] = carry + cells[0]
                carry = ""
                if len(cells) == 2 and " Hon. " in cells[0]:
                    # 'Grand Falls–Drummond–Saint-André Hon. Danny Soucy' (57-3): one
                    # space where the columns meet, but "Hon." only ever opens a member
                    cells = cells[0].split(" Hon. ", 1) + cells[1:]
                    cells[1] = "Hon. " + cells[1]
                if len(cells) != 3:
                    out["problems"].append("members page row not read (not three cells: constituency, "
                                           "member, residence): {0!r}".format(text))
                    continue
                riding, member, _residence = cells
            else:
                riding, member, _residence = split_columns(frags, edges)
            if not riding or not member:
                continue
            marks = re.findall(r"\*+", riding + " " + member)
            mark = marks[0] if marks else None
            riding = re.sub(r"\s*\*+\s*", "", riding)
            member = re.sub(r"\s*\*+\s*", " ", member).strip()
        # 'S h e d i a c-B e a u b a s s i n-C a p-P e l é' (58-4): drawn one
        # glyph at a time
        toks = riding.split()
        if len(toks) >= 6 and all(len(t) <= 3 for t in toks):
            riding = "".join(toks)
        riding = re.sub(r"\s*-\s*", "-", riding).strip()
        if member.strip().lower() == "vacant":
            out["vacant"].append({"riding": riding, "mark": mark})
            continue
        member = clean_member(member)
        if not _NAME.match(clean_given(member)):
            out["problems"].append("members page row: {0!r} is not a name ({1!r})".format(member, text))
            continue
        given, surname = _split_name(member)
        out["members"].append({"riding": riding, "given": given, "surname": surname,
                               "name": clean_given(given) + " " + surname,
                               "key": member_key(given, surname), "mark": mark,
                               "reviewed": bool(fact),
                               "footnote": str(fact["footnote"]) if fact and fact.get("footnote") else None,
                               "elected": str(fact["elected"]) if fact and fact.get("elected") else None})
    if not out["members"]:
        out["problems"].append("no members read from the compiled Journal's members page")
    _bind_notes(out)
    return out


def _bind_notes(out):
    """Give each marked row its footnote. A mark printed on exactly one row
    and over exactly one footnote binds them. A mark the page uses twice
    (58-1 prints "*" on Fairgrieve and on Savoie, and "*" over both
    by-election notes, in the opposite order) binds only through a
    reviewed `roster_rows` entry quoting the row's footnote; without one
    those rows get NO term (their votes are gaps), never the wrong date."""
    rows = out["members"] + out["vacant"]
    for r in rows:
        r["note"], r["unbound"] = None, False
    printed = {re.sub(r"\s+", " ", n["line"]).lstrip("* ") for n in out["notes"]}
    for r in rows:
        if r.get("footnote"):
            quoted = re.sub(r"\s+", " ", r["footnote"]).lstrip("* ")
            note = _footnote("* " + quoted)
            if note is None or quoted not in printed:
                out["problems"].append("reviewed footnote {0!r} {1}".format(
                    r["footnote"], "not understood" if note is None else "is not printed on the page"))
                r["unbound"] = True
            else:
                note["mark"] = r["mark"]
                r["note"] = note
    for mark in sorted({r["mark"] for r in rows if r["mark"]}):
        marked = [r for r in rows if r["mark"] == mark and r["note"] is None and not r["unbound"]]
        notes = [n for n in out["notes"] if n["mark"] == mark]
        if not marked:
            continue
        if len(marked) == 1 and len(notes) == 1 and len([r for r in rows if r["mark"] == mark]) == 1:
            marked[0]["note"] = notes[0]
            continue
        for r in marked:
            r["unbound"] = True
            out["problems"].append("the mark {0!r} on {1} ({2}) has {3} footnote(s) and {4} row(s): not bound "
                                   "without a reviewed roster_rows entry; no term stored for it".format(
                                       mark, r.get("name") or "a vacant seat", r["riding"], len(notes),
                                       len([x for x in rows if x["mark"] == mark])))


def _footnote(line):
    line = re.sub(r"\s+", " ", line or "").strip()
    fn = _FOOTNOTE.match(line)
    if fn:
        return {"mark": fn.group(1), "kind": "by-election", "elected": _date(fn.group(2)),
                "vice": clean_member(fn.group(3)), "why": fn.group(4).lower(), "left": _date(fn.group(5)),
                "line": line}
    fn = _FOOT_RENAMED.match(line)
    if fn and _date(fn.group(4)):
        return {"mark": fn.group(1), "kind": "renamed", "riding": fn.group(2).strip(),
                "renamed": re.sub(r"\s*-\s*", "-", fn.group(3)).strip(), "date": _date(fn.group(4)),
                "line": line}
    fn = _FOOT_LEFT.match(line)
    if fn and _date(fn.group(4)):
        return {"mark": fn.group(1), "kind": "left", "who": clean_member(fn.group(2)),
                "why": fn.group(3).lower(), "left": _date(fn.group(4)), "line": line}
    return None


def _split_name(full):
    toks = clean_given(full).split()
    if len(toks) < 2:
        return "", full.strip()
    return " ".join(toks[:-1]), toks[-1]


def _same_surname(a, b):
    return pn.fold(_split_name(a)[1]) == pn.fold(_split_name(b)[1])


def _day_after(date):
    return (datetime.date.fromisoformat(date) + datetime.timedelta(days=1)).isoformat()


def terms_from_compiled(parsed, legislature, first, last):
    """[(member dict, term dict)] for one session: first/last are its first
    and last sitting dates (last None while the session runs).

    A footnote dates the marked row. A by-election starts its member's term
    and ends the predecessor's ("vice ... resigned"). "X resigned/deceased
    DATE" ends X's term: X is the row's own member when the surnames agree;
    otherwise X is the PREDECESSOR of the row's member (60-1: "* Lisa Harris
    resigned August 16, 2021" under Réjean Savoie), whose term then starts
    no earlier than the day after the vacancy -- the footnote gives no
    by-election date, so that is the bound the seat itself sets, never a
    guess at the polling day -- or of a seat printed "Vacant" (58-4). A
    riding renamed is only a note: the page prints the new name. A term
    wholly outside the session's sittings is not stored."""
    out = []

    def add(member, start, end):
        if first and end and end < first:
            return
        if last and start and start > last:
            return
        out.append((member, {"legislature": legislature, "party": None, "riding": member["riding"],
                             "start": start, "end": end, "party_dated": 0}))

    def predecessor(name, riding, left):
        given, surname = _split_name(name)
        add({"given": given, "surname": surname, "name": clean_given(given) + " " + surname,
             "key": member_key(given, surname), "riding": riding}, first, left)

    for m in parsed["members"]:
        if m.get("unbound"):
            continue
        start, end = first, last
        note = m.get("note")
        kind = note["kind"] if note else None
        if kind == "by-election":
            if note["elected"] and (not first or note["elected"] > first):
                start = note["elected"]
            if note["vice"] and note["left"]:
                predecessor(note["vice"], m["riding"], note["left"])
        elif kind == "left" and note["left"]:
            if _same_surname(note["who"], m["name"]):
                if not last or note["left"] < last:
                    end = note["left"]
            else:
                predecessor(note["who"], m["riding"], note["left"])
                after = _day_after(note["left"])
                start = after if not first or after > first else first
        if m.get("elected") and (not start or m["elected"] > start):
            # a reviewed by-election date for a successor the footnote dates
            # only by the vacancy (60-1: Savoie and Dawson, elected 20 June 2022)
            start = m["elected"]
        add(m, start, end)
    for v in parsed.get("vacant", []):
        note = v.get("note")
        if note and note["kind"] == "left" and note["left"]:
            predecessor(note["who"], v["riding"], note["left"])
    return out


def fetch_roster(ctx, legislature, session, listing):
    """The dated roster for one session. Returns the number of members."""
    daily = listing["daily"]
    first = daily[0]["date"] if daily else None
    last = daily[-1]["date"] if daily and (legislature, session) != parse_session(CURRENT_SESSION) else None
    if listing["compiled"]:
        have = ctx.conn.execute(
            "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND legislature=? AND source=?",
            (PROV, legislature, "journal-{0}-{1}".format(legislature, session))).fetchone()[0]
        if have and not ctx.refresh:
            return have
        raw = ctx.bytes(listing["compiled"], "compiled-{0}-{1}".format(legislature, session))
        if raw:
            try:
                parsed = parse_compiled_roster(roster_rows(raw), reviewed=load_roster_rows(),
                                               document=listing["compiled"])
            except Unreadable as exc:
                ctx.gap("nb {0}-{1}: compiled Journal {2}: {3}".format(legislature, session, listing["compiled"], exc))
                parsed = None
            if parsed:
                for p in parsed["problems"]:
                    ctx.gap("nb {0}-{1}: compiled Journal: {2}".format(legislature, session, p))
                if parsed["session"] != (legislature, session):
                    ctx.gap("nb {0}-{1}: the compiled Journal {2} is for session {3}, not this one; "
                            "its members page is not used".format(legislature, session,
                                                                  listing["compiled"], parsed["session"]))
                elif parsed["members"]:
                    return _store_compiled(ctx, legislature, session, parsed, first, last)
    if legislature == _current_legislature():
        return fetch_current(ctx, legislature)
    bridge = next((b for b in load_roster_bridges() if b["session"] == "{0}-{1}".format(legislature, session)),
                  None)
    if bridge and not listing["compiled"]:
        have = ctx.conn.execute(
            "SELECT COUNT(DISTINCT member_key) FROM prov_member_terms WHERE prov=? AND legislature=? AND source=?",
            (PROV, legislature, "journal-{0}-{1}-bridge".format(legislature, session))).fetchone()[0]
        if have and not ctx.refresh:
            return have
        n = _store_bridge(ctx, legislature, session, bridge, first, last)
        if n:
            return n
    ctx.gap("nb {0}-{1}: no roster for the session (no usable compiled Journal, and the site lists "
            "only current members); its divisions cannot be resolved".format(legislature, session))
    return 0


def load_roster_bridges(path=None):
    """`roster_bridges:` (nb) -- a session that lists no compiled Journal,
    whose roster is the members page of the NEXT session of the same
    Legislature as it stood on that session's first sitting. Reviewed: an
    entry names the session, the compiled Journal it is read from (which
    must still be the one that session's listing links), the date
    (`as_of`, the next session's first sitting), the evidence that nobody
    entered or left the House between the two (`verified_against`) and why.
    The terms are stored under their own source ('journal-<s>-bridge') and
    the run checks them: every division of the session must resolve and
    tally, or it is a gap like any other."""
    return pn._reviewed(PROV, "roster_bridges", ("session", "document", "from_session", "as_of",
                                                 "verified_against", "why"), path)


def _store_bridge(ctx, legislature, session, bridge, first, last):
    src = str(bridge["from_session"])
    fleg, fsess = parse_session(src)
    if fleg != legislature:
        ctx.gap("nb {0}-{1}: roster bridge from {2} crosses a Legislature; not used".format(
            legislature, session, src))
        return 0
    html = ctx.text(JOURNALS.format(fleg, fsess), "journals-{0}-{1}".format(fleg, fsess))
    other = list_records(html or "")
    if other["compiled"] != bridge["document"]:
        ctx.gap("nb {0}-{1}: roster bridge: the {2} listing now links {3!r}, not the reviewed {4}; "
                "not used".format(legislature, session, src, other["compiled"], bridge["document"]))
        return 0
    as_of = str(bridge["as_of"])
    if not other["daily"] or other["daily"][0]["date"] != as_of:
        ctx.gap("nb {0}-{1}: roster bridge: {2}'s first sitting is not {3}; not used".format(
            legislature, session, src, as_of))
        return 0
    raw = ctx.bytes(bridge["document"], "compiled-{0}-{1}".format(fleg, fsess))
    try:
        parsed = parse_compiled_roster(roster_rows(raw), reviewed=load_roster_rows(),
                                       document=bridge["document"]) if raw else None
    except Unreadable as exc:
        ctx.gap("nb {0}-{1}: roster bridge: {2}: {3}".format(legislature, session, bridge["document"], exc))
        return 0
    if not parsed or parsed["session"] != (fleg, fsess) or parsed["problems"]:
        ctx.gap("nb {0}-{1}: roster bridge: {2}'s members page did not read cleanly ({3}); not used".format(
            legislature, session, src, "; ".join((parsed or {}).get("problems") or ["unreadable"])))
        return 0
    # who sat on the next session's first sitting, as that page dates them
    sat = [m for m, t in terms_from_compiled(parsed, fleg, as_of, other["daily"][-1]["date"])
           if (not t["start"] or t["start"] <= as_of) and (not t["end"] or t["end"] >= as_of)]
    if ctx.dry_run:
        return len(sat)
    source = "journal-{0}-{1}-bridge".format(legislature, session)
    for m in sat:
        ps.upsert_member(ctx.conn, PROV, m["key"], name=m["name"], surname=m["surname"],
                         given=clean_given(m["given"]))
        ps.replace_terms(ctx.conn, PROV, m["key"], [{
            "legislature": legislature, "party": None, "riding": m["riding"], "start": first,
            "end": last, "party_dated": 0}], source)
    ctx.conn.commit()
    ctx.log("  nb roster {0}-{1}: {2} member(s) from the {3} members page as of {4} (reviewed bridge)".format(
        legislature, session, len(sat), src, as_of))
    return len(sat)


def _store_compiled(ctx, legislature, session, parsed, first, last):
    source = "journal-{0}-{1}".format(legislature, session)
    rows = terms_from_compiled(parsed, legislature, first, last)
    if ctx.dry_run:
        return len(rows)
    by_key = {}
    for m, t in rows:
        by_key.setdefault(m["key"], (m, []))[1].append(t)
    for key, (m, terms) in by_key.items():
        ps.upsert_member(ctx.conn, PROV, key, name=m["name"], surname=m["surname"],
                         given=clean_given(m["given"]))
        ps.replace_terms(ctx.conn, PROV, key, terms, source)
    ctx.conn.commit()
    ctx.log("  nb roster {0}-{1}: {2} member(s) from the compiled Journal".format(
        legislature, session, len(by_key)))
    return len(by_key)


def fetch_current(ctx, legislature):
    html = ctx.text(MEMBERS, "members-current")
    rows = parse_current_members(html) if html else []
    if html and not rows:
        ctx.gap("nb: no members parsed from {0}".format(MEMBERS))
    if ctx.dry_run or not rows:
        return len(rows)
    ctx.conn.execute("UPDATE prov_members SET sitting=0 WHERE prov=?", (PROV,))
    for r in rows:
        ps.upsert_member(ctx.conn, PROV, r["key"], name=r["name"], surname=r["surname"],
                         given=r["given"], riding=r["riding"], party=r["party"], sitting=1)
        # The page dates nothing: the party is today's, so party_dated=0 and
        # it is never written as party_at_vote.
        ps.replace_terms(ctx.conn, PROV, r["key"], [{
            "legislature": legislature, "party": r["party"], "riding": r["riding"],
            "start": None, "end": None, "party_dated": 0}], "roster")
    ctx.conn.commit()
    ctx.log("  nb roster: {0} current member(s) (legislature {1}; party undated)".format(
        len(rows), legislature))
    return len(rows)


# -- party at the vote: the Hansard's list of members -------------------------
#
# Each daily Hansard (the bilingual "b"/"bil" PDF) prints, a few pages in,
# "LIST OF MEMBERS BY CONSTITUENCY" for that sitting: constituency, party
# code and member ("Fredericton West-Hanwell (I) Dominic Cardy", 15 June
# 2023), with a legend ("(I) Independent"). It is the only source on
# legnb.ca that dates a party, and it dates it to the sitting. For every day
# with a recorded division the list is read and each member's party is
# stored as a PARTY-ONLY term (source 'party-hansard', prov_names: it never
# makes anyone a member) spanning exactly the sittings it was seen on, as
# for Saskatchewan's and Manitoba's cover lists. A day whose Hansard is not
# listed or cannot be read gets no party, and a member whose party changed
# between two read days has none for the days between: NULL, never a guess.

HANSARD = BASE + "/en/house-business/hansard/{0}/{1}"
PARTY_SOURCE = "party-hansard"
_LIST_ROW = re.compile(
    r"^\s*(?P<riding>\S.*?)\s+\(?(?P<code>PC|L|G|I|PA|NDP|IND)\)?\s+(?P<name>\S.*?)\s*$")
_LEGEND = re.compile(r"^\s*\((?P<code>[A-Z]{1,4})\)\s+(?P<party>\S.*?)\s*$")


def list_hansards(html):
    """{date: url} from one session's Hansard listing. File names as listed
    ('49 2023-10-17bil.pdf'), backslashes turned; never constructed."""
    out = {}
    for href, inner in _LINK.findall(html or ""):
        date = _date(html_text(inner))
        if date and date not in out:
            out[date] = _url(href)
    return out


def parse_member_list(text):
    """{'session', 'legend': {code: party}, 'rows': [{riding, code, name}]}
    from a Hansard's text, or None when it prints no member list."""
    start = text.find("LIST OF MEMBERS BY CONSTITUENCY")
    if start < 0:
        return None
    end = text.find("=====PAGE", start)
    block = text[start:end if end > 0 else None]
    out = {"session": None, "legend": {}, "rows": []}
    m = re.search(r"(\w+) Session of the (\d+)\w* Legislative Assembly", block)
    if m:
        out["session"] = (int(m.group(2)), ordinal_value(m.group(1)))
    for line in block.splitlines():
        lg = _LEGEND.match(line)
        if lg:
            out["legend"][lg.group("code")] = lg.group("party")
            continue
        if re.match(r"^\s*(?:Constituencies|LIST OF|Speaker|Deputy|Second|First|Third|Fourth)\b", line):
            continue
        r = _LIST_ROW.match(normalise(line))
        if r and not r.group("name").lower().startswith("vacant"):
            out["rows"].append({"riding": r.group("riding"), "code": r.group("code"),
                                "name": r.group("name")})
    return out


def _list_label(name):
    """'Hon. Rob McKee, K.C.' -> 'Hon. Rob McKee'."""
    return re.sub(r",?\s*(?:K\.C\.|Q\.C\.)\s*$", "", name or "").strip()


def resolve_member_list(parsed, resolver, date, legislature):
    """([(member_key, party)], problems): each row's member, by full name
    and then surname alone, against the roster terms valid that day --
    unique-or-nothing, as for a vote."""
    out, problems = [], []
    for r in parsed["rows"]:
        party = parsed["legend"].get(r["code"]) or r["code"]
        label = _list_label(r["name"])
        # as printed; without a middle initial ('Mary E. Wilson' against a
        # roster 'Mary Wilson'); then the surname alone
        bare = re.sub(r"(?<=\s)[A-Z]\.\s+(?=\S)", "", label)
        tokens = pn.parse_label(label).tokens
        key = how = None
        for attempt in (label, bare, tokens[-1] if tokens else ""):
            if not attempt:
                continue
            key, how = resolver.resolve(attempt, date, legislature)
            if key:
                break
        if key:
            out.append((key, party))
        else:
            problems.append("{0!r} ({1}): {2}".format(r["name"], r["riding"], how))
    keys = [k for k, _ in out]
    for k in {k for k in keys if keys.count(k) > 1}:
        problems.append("{0} matched more than one row; no party stored for them".format(k))
        out = [(x, p) for x, p in out if x != k]
    return out, problems


def fetch_party_lists(ctx, legislature, session, resolver, dates):
    """Read the Hansard member list of each date in `dates` not already
    covered, and store the parties as party-only terms. Returns days read.

    A division day whose own Hansard is missing or unreadable (20 November
    2025 is served truncated) is covered only from the listed sittings
    either side of it: if a member's party is the same on both, the term
    spans the day, as every list-built term spans the sittings it was seen
    on; if it differs, or a side cannot be read, the day has no party."""
    state = {"listing": None}
    read = 0

    def covered(date):
        return bool(ctx.conn.execute(
            "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source=? AND legislature=? "
            "AND start<=? AND end>=?", (PROV, PARTY_SOURCE, legislature, date, date)).fetchone()[0])

    def listing():
        if state["listing"] is None:
            html = ctx.text(HANSARD.format(legislature, session), "hansards-{0}-{1}".format(legislature, session))
            state["listing"] = list_hansards(html) if html else {}
        return state["listing"]

    def read_list(date, url):
        raw = ctx.bytes(url, "hansard-{0}".format(date))
        if raw is None:
            return False
        try:
            parsed = parse_member_list(pdf_text(raw, pages=range(10)))
        except Unreadable as exc:
            ctx.gap("nb {0}: Hansard {1}: {2}; no member list read".format(date, url, exc))
            return False
        if not parsed or not parsed["rows"]:
            ctx.gap("nb {0}: Hansard {1} prints no list of members".format(date, url))
            return False
        if parsed["session"] and parsed["session"] != (legislature, session):
            ctx.gap("nb {0}: Hansard {1} lists members for session {2}; not used".format(date, url, parsed["session"]))
            return False
        pairs, problems = resolve_member_list(parsed, resolver, date, legislature)
        for p in problems:
            ctx.gap("nb {0}: Hansard member list: {1}".format(date, p))
        if not ctx.dry_run:
            for key, party in pairs:
                ps.extend_term(ctx.conn, PROV, key, legislature, party, None, date, PARTY_SOURCE, party_dated=True)
            ctx.conn.commit()
        return True

    todo = [d for d in sorted(dates) if ctx.refresh or not covered(d)]
    if todo and not listing():
        # Hansard is published from the 58th Legislature's third session
        # (November 2016) on; earlier transcripts are "available upon
        # request" from the Legislative Library. One gap for the session,
        # not two for every division day.
        ctx.gap("nb {0}-{1}: the Hansard listing names no transcript for the session, so no party at "
                "the vote from Hansard for its {2} division day(s)".format(legislature, session, len(todo)))
        return 0
    for date in todo:
        if not ctx.refresh and covered(date):
            continue
        url = listing().get(date)
        if url and read_list(date, url):
            read += 1
            continue
        if not url:
            ctx.gap("nb {0}: no Hansard listed for the day".format(date))
        days = sorted(listing())
        before = [d for d in days if d < date][-1:]
        after = [d for d in days if d > date][:1]
        for d in before + after:
            if covered(d) and not ctx.refresh:
                continue
            read += 1 if read_list(d, listing()[d]) else 0
        if covered(date):
            ctx.log("  nb {0}: own Hansard unread; party taken from lists read either side of it".format(date))
        else:
            ctx.gap("nb {0}: no party at the vote that day (its own Hansard unread and no lists read either "
                    "side cover it)".format(date))
    return read


# -- party at the vote before Hansard: the Chief Electoral Officer's reports --
#
# Christopher, 7 October 2026: before the Hansard member lists (58-3 on),
# take the party a member was ELECTED under from the Chief Electoral Officer's
# report tabled in the House, and carry it only to the first Hansard list
# that agrees. The reports, as legnb.ca's tabled-documents listings name them
# (never constructed):
#   * 58th Legislature: "Report of the Chief Electoral Officer on the General
#     Election of the Thirty-Eighth Legislative Assembly" (22 September 2014),
#     58/1/tabled_documents/3/GeneralElectionGenerale2014.pdf; the Saint John
#     East by-election of 17 November 2014 (58/1/tabled_documents/3/...
#     SaintJohnEstByElection...2014.pdf, Glen Savoie, PC, oath 2 December 2014);
#     the Carleton by-election of 5 October 2015 (58/2/tabled_documents/1/
#     ByElectionPartielle-Carleton.pdf, Stewart Fairgrieve, PC, oath 29
#     October 2015). Each by-election report also prints the seat distribution
#     on the oath date ("L 26, PC 22, PVNBGP 1"): the standings check below.
#   * 57th Legislature (27 September 2010): the report is NOT tabled on
#     legnb.ca (the 57-1 to 57-4 listings hold only the 2013 Kent by-election
#     report), and Elections NB (electionsnb.ca, and its gnb.ca pages) answers
#     our honest client 403. Not worked around: the 57th stays NULL.
# A party on election day is stored as a 'party-election-result' term
# (party_dated 0: never itself written onto a vote). It is CARRIED, as a
# dated 'party-election' term, from the election (or the by-election oath)
# to the member's first Hansard list only when that list prints the same
# party. A member with no Hansard list in the Legislature (Alward resigned
# in May 2015) is carried to the end of his roster term only when every
# seat distribution the by-election reports print within it reconciles with
# the election parties of the members then sitting; otherwise, and for a
# member whose first Hansard party differs (a floor-crosser), nothing is
# carried: no party in the uncertain window, as for Nova Scotia.

TABLED = BASE + "/en/house-business/tabled-documents/{0}/{1}"
ELECTION_RESULT = "party-election-result"
ELECTION_SOURCE = "party-election"
# The legislatures whose earlier sessions have no Hansard member lists.
ELECTION_REPORT_LEGISLATURES = (57, 58)
# Report codes, in the Hansard legend's own names, so one party is one string.
PARTY_CODES = {"PC": "Progressive Conservative Party of New Brunswick", "L": "Liberal Party of New Brunswick",
               "PVNBGP": "Green Party of New Brunswick", "PANB": "People’s Alliance of New Brunswick",
               "NDP": "New Democratic Party", "IND": "Independent"}
_CEO = re.compile(r"^Report of the Chief Electoral Officer", re.I)
_RESULT_CODE = re.compile(r"\b(PC|L|NDP/ ?NPD|NBNDP/ ?NPDNB|PVNBGP|PANB(?:/AGNB)?|IND)\s+([\d,]+)(\s+E)?\b")
_LONG_PARTY = re.compile(r"(Progressive Conservative Party|Liberal Party|Green Party|People’s Alliance|"
                         r"New Democratic Party|Independent)")


def _code(word):
    w = re.sub(r"\s+", "", word or "")
    return {"NDP/NPD": "NDP", "NBNDP/NPDNB": "NDP", "PANB/AGNB": "PANB"}.get(w, w)


def list_election_reports(html):
    """[(label, url)] of the Chief Electoral Officer's reports a session's
    tabled-documents listing links."""
    out = []
    for href, inner in re.findall(r'<a[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', html or "", re.S | re.I):
        label = html_text(inner)
        if _CEO.match(label):
            out.append((label, _url(href)))
    return out


def parse_general_report(text):
    """{'date', 'elected': [(record text, party code)]} from a general
    election report's "Summary of Votes Received by Candidate" pages: one
    record per candidate, starting with the district number; an elected
    candidate's party code and votes are followed by "E"."""
    m = re.search(r"(" + _MONTHS + r" \d{1,2}, \d{4}) NB General Election", text or "")
    out = {"date": _date(m.group(1)) if m else None, "elected": []}
    for page in (text or "").split("=====PAGE"):
        if "Summary of Votes Received by Candidate" not in page:
            continue
        for chunk in re.split(r"(?m)^(?=\d{1,2} \S)", page):
            flat = re.sub(r"\s+", " ", chunk).strip()
            r = _RESULT_CODE.search(flat)
            if r and r.group(3) and re.match(r"\d{1,2} ", flat):
                out["elected"].append((flat, _code(r.group(1))))
    return out


def parse_by_election_report(text):
    """{'name', 'party', 'oath', 'seats': {code: n}} from a by-election
    report: the elected candidate's block (name, district, party affiliation)
    and the "Distribution of seats in the Legislative Assembly as of <oath
    date>" (note (**): the date of the elected candidate's oath)."""
    flat = re.sub(r"\s+", " ", text or "")
    out = {"name": None, "party": None, "oath": None, "seats": {}}
    m = re.search(r"Adresse de résidence ([A-ZÀ-Þ][\w’'\-]+(?: [A-ZÀ-Þ]\.)?(?: [A-ZÀ-Þ][\w’'\-]+)+?) "
                  r".{0,80}?" + _LONG_PARTY.pattern, flat)
    if m:
        out["name"], long_name = m.group(1), m.group(2)
        out["party"] = {"Progressive Conservative Party": "PC", "Liberal Party": "L", "Green Party": "PVNBGP",
                        "People’s Alliance": "PANB", "New Democratic Party": "NDP",
                        "Independent": "IND"}[long_name]
    s = re.search(r"Distribution of seats in the Legislative Assembly as of (" + _MONTHS + r" \d{1,2}, \d{4})", flat)
    if s:
        out["oath"] = _date(s.group(1))
        # the table prints after the heading (Saint John East, 2014) or, in
        # the text pypdf gives, before it (Carleton, 2015)
        seat = r"\b(L|PC|NBNDP/NPDNB|NDP/NPD|PANB/AGNB|PVNBGP|IND) (\d+)\b"
        found = re.findall(seat, flat[s.end():s.end() + 600])
        if len(found) < 3:
            found = re.findall(seat, flat[max(0, s.start() - 700):s.start()])
        for code, n in found:
            out["seats"].setdefault(_code(code), int(n))
    return out


def _roster_members(conn, legislature):
    return conn.execute(
        "SELECT DISTINCT m.member_key, m.given, m.surname FROM prov_members m JOIN prov_member_terms t "
        "ON t.prov=m.prov AND t.member_key=m.member_key WHERE m.prov=? AND t.legislature=? "
        "AND t.source LIKE 'journal-%'", (PROV, legislature)).fetchall()


def match_elected(records, members):
    """{member_key: party code}: a member is the ONE elected record carrying
    their surname as a word (and, when several do, their first given name
    too). Unique-or-nothing."""
    out, problems = {}, []
    for key, given, surname in members:
        sur = r"\b" + re.escape(pn.fold(surname)) + r"\b"
        hits = [r for r in records if re.search(sur, pn.fold(r[0]))]
        if len(hits) > 1 and given:
            first = pn.fold(clean_given(given)).split()[0]
            hits = [r for r in hits if re.search(r"\b" + re.escape(first) + r"\b", pn.fold(r[0]))]
        if len(hits) == 1:
            out[key] = hits[0][1]
        else:
            problems.append("{0}: {1} elected record(s)".format(key, len(hits)))
    return out, problems


def fetch_election_results(ctx, legislature):
    """Read the Chief Electoral Officer's reports tabled in the Legislature's
    first two sessions and store each member's party on election day
    (ELECTION_RESULT terms). Once per Legislature; returns members stored."""
    have = ctx.conn.execute("SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND legislature=? AND source=?",
                            (PROV, legislature, ELECTION_RESULT)).fetchone()[0]
    if have and not ctx.refresh:
        return have
    reports = []
    for sess in (1, 2):
        html = ctx.text(TABLED.format(legislature, sess), "tabled-{0}-{1}".format(legislature, sess))
        reports += list_election_reports(html or "")
    general = [u for l, u in reports if "general election" in l.lower()]
    byes = [u for l, u in reports if "by-election" in l.lower()]
    if not general:
        ctx.gap("nb {0}: no report of the Chief Electoral Officer on the general election is tabled on legnb.ca "
                "(tabled documents of {0}-1 and {0}-2), and Elections NB answers 403; votes before the first "
                "Hansard member list carry no party".format(legislature))
        return 0
    members = _roster_members(ctx.conn, legislature)
    results = {}
    try:
        raw = ctx.bytes(general[0], "ceo-general-{0}".format(legislature))
        rep = parse_general_report(pdf_text(raw)) if raw else None
    except Unreadable as exc:
        ctx.gap("nb {0}: election report {1}: {2}".format(legislature, general[0], exc))
        rep = None
    if rep:
        got, problems = match_elected(rep["elected"], members)
        for key, code in got.items():
            results[key] = (code, rep["date"], general[0])
    checkpoints = []
    for url in byes:
        try:
            raw = ctx.bytes(url, "ceo-bye-{0}".format(legislature))
            b = parse_by_election_report(pdf_text(raw)) if raw else None
        except Unreadable as exc:
            ctx.gap("nb {0}: by-election report {1}: {2}".format(legislature, url, exc))
            continue
        if not b or not b["name"] or not b["party"] or not b["oath"]:
            ctx.gap("nb {0}: by-election report {1} not read (elected candidate, party or oath date)".format(
                legislature, url))
            continue
        got, _p = match_elected([(b["name"], b["party"])], [m for m in members if m[0] not in results])
        if len(got) == 1:
            key = next(iter(got))
            results[key] = (b["party"], b["oath"], url)
        else:
            ctx.gap("nb {0}: by-election report {1}: {2!r} matches no single member".format(legislature, url, b["name"]))
        if b["seats"]:
            checkpoints.append((b["oath"], b["seats"], url))
    unmatched = [m[0] for m in members if m[0] not in results]
    for key in unmatched:
        ctx.gap("nb {0}: {1} not found among the elected in the Chief Electoral Officer's reports; no party "
                "before the first Hansard list".format(legislature, key))
    if ctx.dry_run:
        return len(results)
    for key, (code, date, url) in results.items():
        ps.replace_terms(ctx.conn, PROV, key, [{"legislature": legislature, "party": PARTY_CODES.get(code, code),
                                                "riding": None, "start": date, "end": None, "party_dated": 0}],
                         ELECTION_RESULT, legislature=legislature)
    ctx.conn.execute("DELETE FROM prov_member_terms WHERE prov=? AND legislature=? AND source=?",
                     (PROV, legislature, ELECTION_RESULT + "-standings"))
    for date, seats, url in checkpoints:
        ctx.conn.execute(
            "INSERT INTO prov_member_terms (prov, member_key, legislature, party, riding, start, end, party_dated, "
            "source) VALUES (?,?,?,?,?,?,?,0,?)",
            (PROV, "_standings", legislature, json.dumps(seats, sort_keys=True), url, date, date,
             ELECTION_RESULT + "-standings"))
    ctx.conn.commit()
    ctx.log("  nb {0}: party on election day for {1} member(s) from the Chief Electoral Officer's report(s); "
            "{2} seat distribution(s)".format(legislature, len(results), len(checkpoints)))
    return len(results)


def carry_election_party(conn, legislature, log=print):
    """Derive the dated ELECTION_SOURCE terms (see the block comment above).
    Returns (carried, withheld)."""
    rows = conn.execute("SELECT member_key, party, start FROM prov_member_terms WHERE prov=? AND legislature=? "
                        "AND source=?", (PROV, legislature, ELECTION_RESULT)).fetchall()
    if not rows:
        return 0, 0
    elected = {k: (p, s) for k, p, s in rows}
    roster = {}
    for k, s, e in conn.execute("SELECT member_key, start, end FROM prov_member_terms WHERE prov=? AND "
                                "legislature=? AND source LIKE 'journal-%'", (PROV, legislature)):
        roster.setdefault(k, []).append((s, e))
    # standings: every seat distribution must equal the count of election
    # parties among the members whose roster terms cover its date
    reconciled = True
    for seats, date in conn.execute("SELECT party, start FROM prov_member_terms WHERE prov=? AND legislature=? "
                                    "AND source=?", (PROV, legislature, ELECTION_RESULT + "-standings")):
        want = {c: n for c, n in json.loads(seats).items() if n}
        have = {}
        for k, terms in roster.items():
            # sitting on the date: from the earlier of the election (or oath) and
            # the first roster term to the last roster term's end, so the days
            # between two sessions count (Carleton's oath, 29 October 2015)
            starts = [s for s, e in terms if s] + ([elected[k][1]] if k in elected and elected[k][1] else [])
            ends = [e for s, e in terms]
            last = None if None in ends else max(ends)
            if k in elected and starts and min(starts) <= date and (last is None or last >= date):
                code = next((c for c, name in PARTY_CODES.items() if name == elected[k][0]), elected[k][0])
                have[code] = have.get(code, 0) + 1
        if have != want:
            reconciled = False
            log("  nb {0}: the seat distribution of {1} ({2}) does not reconcile with the election parties of the "
                "members then sitting ({3})".format(legislature, date, want, have))
    carried = withheld = 0
    for key, (party, start) in elected.items():
        first = conn.execute("SELECT party, start FROM prov_member_terms WHERE prov=? AND member_key=? AND "
                             "legislature=? AND source=? ORDER BY start LIMIT 1",
                             (PROV, key, legislature, PARTY_SOURCE)).fetchone()
        if first:
            end = first[1] if first[0] == party else None
        else:
            ends = [e for s, e in roster.get(key, [])]
            end = (max(ends) if ends and None not in ends else None) if reconciled else None
        if end and start and end >= start:
            ps.replace_terms(conn, PROV, key, [{"legislature": legislature, "party": party, "riding": None,
                                                "start": start, "end": end, "party_dated": 1}],
                             ELECTION_SOURCE, legislature=legislature)
            carried += 1
        else:
            conn.execute("DELETE FROM prov_member_terms WHERE prov=? AND member_key=? AND legislature=? AND source=?",
                         (PROV, key, legislature, ELECTION_SOURCE))
            withheld += 1
            log("  nb {0}: {1}'s election party ({2}) not carried ({3})".format(
                legislature, key, party, "first Hansard list prints " + first[0] if first else
                "no Hansard list, standings not reconciled"))
    conn.commit()
    return carried, withheld


def make_resolver(conn):
    """The run's resolver, with the reviewed label aliases of
    config/prov_record.yaml consulted after it fails, and the Journal's own
    capitals telling two surnames apart (CaseExact)."""
    return CaseExact(pn.Aliased(pn.Resolver.from_conn(conn, PROV), pn.load_aliases(PROV)))


class CaseExact:
    """The 57th Legislature seated Kirk MacDonald (York North) and Brian
    Macdonald (Fredericton-Silverwood); every Journal prints them "Mr.
    MacDonald" and "Mr. Macdonald", in the same list. The shared resolver
    folds case, so both labels come back ambiguous between the two. Here an
    AMBIGUOUS label is settled only when its surname, exactly as printed
    (capitals included), is the surname of exactly one of the candidates;
    or, failing that, when reviewed titles (`titles:`, load_titles) rule out
    all candidates but one ("Hon. Ms. Landry" beside "Hon. Mr. Landry",
    58-1). Anything else stays ambiguous. Still unique-or-nothing, and the
    tally check runs on the result."""

    def __init__(self, inner, titles=None):
        self.inner = inner
        self.base = getattr(inner, "base", inner)
        self.titles = {}
        for a in (load_titles() if titles is None else titles):
            self.titles[str(a["member"])] = _title_class(a["title"])

    def party_at(self, member_key, date, legislature=None):
        return self.inner.party_at(member_key, date, legislature)

    def term_for(self, member_key, date, legislature=None):
        return self.base.term_for(member_key, date, legislature)

    def resolve(self, raw, date, legislature=None, document=None):
        key, how = self.inner.resolve(raw, date, legislature, document=document)
        if key or not str(how).startswith("ambiguous:"):
            return key, how
        candidates = [k.strip() for k in str(how).partition(":")[2].split(",") if k.strip()]
        words = re.sub(r"\(.*?\)", " ", raw or "").replace(",", " ").split()
        printed = words[-1] if words else ""
        exact = [k for k in candidates
                 if (self.base.members.get(k) or {}).get("surname") == printed]
        if len(exact) == 1 and printed != printed.lower() and printed != printed.upper():
            return exact[0], "surname, as capitalised ({0})".format(how)
        # The title as printed ("Hon. Ms. Landry" and "Hon. Mr. Landry" in one
        # list, 58-1: Francine and Denis Landry), against reviewed titles: a
        # candidate whose reviewed title is the other one is ruled out, and
        # the label is settled only when exactly one candidate is left.
        cls = _title_class(next((w for w in words if _title_class(w)), None))
        if cls and candidates:
            left = [k for k in candidates if self.titles.get(k, cls) == cls]
            if len(left) == 1 and len(left) < len(candidates):
                return left[0], "title (reviewed, config/prov_record.yaml; {0})".format(how)
        return key, how


_TITLES = {"mr": "m", "ms": "f", "mrs": "f", "miss": "f", "mme": "f", "m": None}


def _title_class(word):
    return _TITLES.get(re.sub(r"[^a-z]", "", (word or "").lower())) if word else None


def load_titles(path=None):
    """`titles:` (nb) -- the title the record prints for a member ("Ms.",
    "Mr."), read where the record joins it to the member's full name: a bill
    the Journal says was introduced "By Hon. Ms. Landry" whose bill page
    names its sponsor "Hon. Francine LANDRY", or "Mr. Bernard LeBlanc,
    Member for Memramcook-Tantramar". Needs member, title, document, quoted,
    verified_against and why. Read by CaseExact, and only for a label the
    resolver found AMBIGUOUS."""
    return pn._reviewed(PROV, "titles", ("member", "title", "document", "quoted", "verified_against", "why"),
                        path)


# -- bills ------------------------------------------------------------------

_BILL_ITEM = re.compile(r'<li class="bill-item">(.*?)</li>\s*(?=<li class="bill-item">|</ul>)', re.S)
_STEP = re.compile(r'<div class="step[^"]*">\s*<span>(.*?)</span>\s*<span>(.*?)</span', re.S)
_STAGE_NAME = {"1st reading": "First Reading", "2nd reading": "Second Reading",
               "3rd reading": "Third Reading", "committee": "Committee", "royal assent": "Royal Assent"}


def parse_bill_list(html):
    """[{number, title, href, amended, stages: [{stage, status, date}]}]"""
    out = []
    for item in _BILL_ITEM.findall(html or ""):
        num = re.search(r'<div class="bill-item-number">\s*([^<]+?)\s*</div>', item)
        link = re.search(r'<div class="bill-item-title">\s*<a href="([^"]+)">(.*?)</a>', item, re.S)
        if not num or not link:
            continue
        stages = []
        for name, status in _STEP.findall(item):
            stage = _STAGE_NAME.get(html_text(name).lower())
            st = html_text(status)
            word, _, when = st.partition(":")
            if stage:
                stages.append({"stage": stage, "status": word.strip() or None,
                               "date": _date(when) if when.strip() else None})
        out.append({"number": num.group(1).strip(), "title": html_text(link.group(2)),
                    # quoted: 58-2's bill pages are named by their titles,
                    # accents and all ("...-Société-..."), and an unquoted é
                    # crashed the request (urllib sends ASCII only)
                    "href": urljoin(BASE, _ascii_url(_html.unescape(link.group(1)))),
                    "amended": "bill-amendment-count" in item, "stages": stages})
    return out


_DOC = re.compile(r'<a class="bill-document"[^>]*href="([^"]+)"[^>]*>\s*<span>(.*?)</span>', re.S)


def parse_bill_page(html):
    """{bill_type, sponsor, sponsor_party, docs: [(label, url)], text_url}"""
    def prop(label):
        m = re.search(r'<span class="property-label">{0}</span>(.*?)</div>'.format(label), html or "", re.S)
        return html_text(m.group(1)) if m else None
    spons = re.search(r'<span class="property-label">Sponsored by</span>(.*?)</section>', html or "", re.S)
    sponsor = party = None
    if spons:
        n = re.search(r"<h3>(.*?)</h3>", spons.group(1), re.S)
        p = re.search(r'member-card-description-party">(.*?)</li>', spons.group(1), re.S)
        sponsor = html_text(n.group(1)) if n else None
        party = html_text(p.group(1)) if p else None
    docs = [(html_text(label), _url(href)) for href, label in _DOC.findall(html or "")]
    reading = [d for d in docs if "reading" in d[0].lower()]
    # The latest reading's text, English HTML first and its PDF as the
    # fallback: Bill-57-e.htm (60-2) is served as an empty document.
    texts = [u for l, u in reversed(reading) if u.lower().endswith((".htm", ".html"))][:1] + \
        [u for l, u in reversed(reading) if u.lower().endswith(".pdf")][:1]
    return {"bill_type": prop("Bill Type"), "sponsor": sponsor, "sponsor_party": party,
            "docs": docs, "texts": texts, "text_url": texts[0] if texts else None}


def bill_text(ctx, url, slug_):
    """English text of one bill document, or None. An empty document is
    reported back as None so the caller can try the next one."""
    if url.lower().endswith(".pdf"):
        raw = ctx.bytes(url, slug_)
        if raw is None:
            return None
        try:
            return pdf_text(raw).strip() or None
        except Unreadable as exc:
            ctx.gap("nb bill text {0}: {1}".format(url, exc))
            return None
    raw = ctx.text(url, slug_, encoding="cp1252")
    if raw is None:
        return None
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    # paragraphs and headings to line breaks, so passages stay passages
    body = re.sub(r"(?i)</(p|h\d|div|tr|li)>|<br[^>]*>", "\n\n", body)
    return "\n".join(html_text(l) for l in body.split("\n\n") if html_text(l)) or None


def _stage_dates_in_window(ctx, stages):
    return any(s.get("date") and ctx.in_window(s["date"]) for s in stages)


def fetch_bills(ctx, legislature, session, tax, wl):
    html = ctx.text(BILLS.format(legislature, session), "bills-{0}-{1}".format(legislature, session))
    items = parse_bill_list(html) if html else []
    if html and not items:
        ctx.gap("nb bills {0}-{1}: no bills parsed from the listing".format(legislature, session))
    if ctx.dry_run:
        return {"bills": len(items)}
    pages = texts = 0
    windowed = bool(ctx.since or ctx.until)
    out_of_time = False
    for it in items:
        key = ps.bill_key(PROV, legislature, session, it["number"])
        latest = [s for s in it["stages"] if s["date"]]
        record = {"bill_key": key, "prov": PROV, "legislature": legislature, "session": session,
                  "number": it["number"], "title_en": it["title"], "stages": it["stages"],
                  "page_url": it["href"], "latest_stage": latest[-1]["stage"] if latest else None,
                  "royal_assent": next((s["date"] for s in it["stages"]
                                        if s["stage"] == "Royal Assent" and s["date"]), None)}
        have = ctx.conn.execute("SELECT text_read FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
        wanted = (not windowed or _stage_dates_in_window(ctx, it["stages"])
                  or pc.watched_bill(PROV, key) is not None)
        if not out_of_time and ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("bill pages", pages))
            out_of_time = True
        if (have and have[0] and not ctx.refresh) or not wanted or out_of_time:
            # Listed only: stages kept fresh, a text classification kept.
            if have and have[0]:
                ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
            else:
                res = pc.classify(tax, wl, PROV, title=it["title"], bill_key=key)
                ps.store_bill(ctx.conn, dict(record, text_read=0, areas=res.areas,
                                             matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
            continue
        page_html = ctx.text(it["href"], "bill-{0}-{1}-{2}".format(legislature, session, it["number"]))
        page = parse_bill_page(page_html) if page_html else {"docs": [], "text_url": None}
        pages += 1 if page_html else 0
        body = None
        text_url = None
        for k, url in enumerate(page.get("texts") or []):
            body = bill_text(ctx, url, "billtext-{0}-{1}-{2}-{3}".format(
                legislature, session, it["number"], k))
            if body:
                text_url = url
                texts += 1
                break
        if page_html and not page.get("texts"):
            ctx.gap("{0}: the bill page lists no bill-text document".format(key))
        elif page_html and not body:
            ctx.gap("{0}: no bill-text document gave any text ({1}); classified on its title".format(
                key, ", ".join(page["texts"])))
        res = pc.classify(tax, wl, PROV, title=it["title"], texts=[body] if body else [], bill_key=key)
        ps.store_bill(ctx.conn, dict(
            record, sponsor=page.get("sponsor"), bill_type=page.get("bill_type"),
            is_government=1 if (page.get("bill_type") or "").startswith("Government") else
            (0 if page.get("bill_type") else None),
            text_url=text_url or page.get("text_url"), text_read=1 if body else 0, areas=res.areas,
            matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
    ctx.conn.commit()
    ctx.log("  nb bills {0}-{1}: {2} listed, {3} page(s) read, {4} text(s) read".format(
        legislature, session, len(items), pages, texts))
    return {"bills": len(items), "bill_pages": pages, "bill_texts": texts}


# -- the Journal --------------------------------------------------------------

# "YAYS" is the record's own spelling in 57-2 and 57-3 (20 December 2011, 29 May 2013).
HEADER = re.compile(r"^\s*(YEAS|YAYS|NAYS)\s*[-–—]+\s*(\d+|Nil)\s*$", re.I)
_COW_Q = re.compile(r"the Chair put the question on the motion that Bill (\d+)\b", re.I)
_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
# Running heads. 2011 on: "236 60-61 Elizabeth II, 2011-2012 June 8" and
# "June 8 Journal of Assembly 237". The 56th Legislature and 57-1 draw the
# page number against the words: "218 March 2458-59 Elizabeth II,
# 2009-2010" (page 218, 24 March, 58-59 Elizabeth II) and "March 26
# 225Journal of Assembly" -- a name list or a bill list running over the
# page must not end at them (26 March 2010).
_FURNITURE = re.compile(
    r"^\s*(?:=====PAGE|\d+\s+[\d\-–]+\s+(?:Elizabeth|Charles)\s+(?:II|III)\b.*"
    r"|\d+\s+" + _MONTHS + r"\s+\d{1,2}\s*\d{2}\s*[-–]\s*\d{2}\s+(?:Elizabeth|Charles)\s+(?:II|III)\b.*"
    # 58-3: "April 26 65-66 Elizabeth II, 2016-2017 157" and "152 Journal of
    # Assembly April 25"
    r"|\d+\s+Journal of Assembly\s+" + _MONTHS + r"\s+\d{1,2}"
    r"|" + _MONTHS + r"\s+\d{1,2}\s+\d{2}\s*[-–]\s*\d{2}\s+(?:Elizabeth|Charles)\s+(?:II|III)\b.*"
    r"|" + _MONTHS + r"\s+\d{1,2}\s+(?:\d+\s*)?Journal of Assembly(?:\s+\d+)?)\s*$")
# "Hon. Mr. Holder", "Ms. M. Wilson"; and, in the 56th Legislature's
# Journals, a minister with no Mr./Ms.: "Hon. S. Graham", "Hon. V. Boudreau"
# (4 February 2010).
_LABEL = re.compile(
    r"(?:Hon\.\s*(?:(?:Mr|Mrs|Ms|Miss|Dr|Mme)\.\s+)?|(?:Mr|Mrs|Ms|Miss|Dr|Mme)\.\s+)"
    r"(?:[A-Z]\.\s*)*[A-ZÀ-Þ][\w’'\-]*"
    r"(?:\s+(?!(?:Hon|Mr|Mrs|Ms|Miss|Dr|Mme)\.)[A-ZÀ-Þ][\w’'\-]*)*")


def normalise(line):
    """Undo pypdf's stray spaces: 'M s.' -> 'Ms.', 'sub -amendment' ->
    'sub-amendment', runs of spaces -> one."""
    s = (line or "").replace("\xa0", " ")
    s = re.sub(r"\bM\s+(s|rs|r)\.", r"M\1.", s)
    s = re.sub(r"(\w)\s+-(\w)", r"\1-\2", s)
    s = re.sub(r"\bHon\.\s+Mr\s*,", "Hon. Mr.", s)
    s = re.sub(r"\bBil l\b", "Bill", s)          # "Bil l 17" (17 November 2016)
    return re.sub(r"[ \t]+", " ", s).strip()


def is_furniture(line):
    return not (line or "").strip() or bool(_FURNITURE.match(line))


def labels_in_line(line):
    """The member labels on one name-list line, or None if anything else is on it."""
    s = normalise(line)
    if not s:
        return None
    out, pos = [], 0
    for m in _LABEL.finditer(s):
        if s[pos:m.start()].strip():
            return None
        out.append(m.group(0).strip())
        pos = m.end()
    if s[pos:].strip():
        return None
    return out or None


_RESULT = re.compile(r"([^.;:]*?)\s+on the following\s+recorded\s+division", re.I)
_RESULT_HEAD = re.compile(
    r"((?:it|the (?:amendment|sub\s*-?\s*amendment|motion)|Motion \d+(?: as amended)?|Bill \d+)"
    r"\s+was\s+.+)$", re.I)
_READ_Q = re.compile(r"question being put that Bill (\d+) be now read a (first|second|third) time", re.I)
_READ_DEBATE = re.compile(r"the motion that Bill (\d+),[^.]*?be now read a (second|third) time", re.I)
_ORDER_READ = re.compile(r"The Order being read for (second|third) reading of Bill (\d+)", re.I)
_MOTION = re.compile(r"\bMotion (\d+)\b")
_ITEM_START = re.compile(
    r"(?:Pursuant to Notice of Motion \d+|Debate resumed|The Order being read|"
    r"(?:Mr\.|Madam) (?:Deputy )?Speaker put the question on Motion|The House resumed the adjourned debate)")
_VOICE_Q = re.compile(
    r"question being put that Bill (\d+) be now read a (first|second|third) time,\s*"
    r"it was (resolved in the affirmative|resolved in the negative|defeated|carried|negatived)\s*\.", re.I)
# "where" is the record's own typo (30 May 2012: "The following Bills where
# read a third time:").
_VOICE_LIST = re.compile(r"^The following (?:Private )?Bills? (?:was|were|where) (?:introduced and )?read a (first|second|third) "
                         r"time(?: and passed)?\s*[:.]?\s*$", re.I)
_LIST_SPONSOR = re.compile(r"^By (?:the )?(?:Hon(?:ourable)?\.?\s+)?(?:(?:Mr|Mrs|Ms|Miss|Dr|Mme)\.?\s+)?\S.{0,80},\s*$")
_LIST_ITEM = re.compile(r"^(?:By [^,]{1,80},\s*)?Bill (\d+),")


def parse_journal(text):
    """(divisions, voices) from one day's English Journal text, names unresolved.

    divisions: [{seq, yeas, nays, yea_labels, nay_labels, question, item,
                 result, vote_on, stage, bill_number, motion, problem}]
    voices:    [{bill_number, stage, result}]"""
    lines = [normalise(l) for l in (text or "").splitlines()]
    divisions, prose, context = [], [], []
    i, n = 0, len(lines)

    def take(i):
        got = []
        while i < n:
            l = lines[i]
            if is_furniture(l):
                i += 1
                continue
            if HEADER.match(l):
                break
            labs = labels_in_line(l)
            if labs is None:
                break
            got.extend(labs)
            i += 1
        return got, i

    while i < n:
        line = lines[i]
        h = HEADER.match(line)
        if h and h.group(1).upper() in ("YEAS", "YAYS"):
            yeas = 0 if h.group(2).lower() == "nil" else int(h.group(2))
            yea_labels, i = take(i + 1)
            while i < n and is_furniture(lines[i]):
                i += 1
            h2 = HEADER.match(lines[i]) if i < n else None
            nays, nay_labels, problem, note = None, [], None, None
            if h2 and h2.group(1).upper() == "NAYS":
                nays = 0 if h2.group(2).lower() == "nil" else int(h2.group(2))
                nay_labels, i = take(i + 1)
            elif i < n and lines[i].strip():
                # A unanimous recorded division prints YEAS only (Motion 36
                # as amended, 8 June 2023: YEAS - 44 and then the next
                # item). No NAYS total is printed, so none is checked; the
                # YEAS still must account for every name.
                note = "no NAYS list printed (unanimous)"
            else:
                problem = "no NAYS list after 'YEAS - {0}'".format(yeas)
            divisions.append(_division(context, len(divisions) + 1, yeas, nays,
                                       yea_labels, nay_labels, problem))
            divisions[-1]["note"] = note
            prose.append("")
            context = []
            continue
        if not is_furniture(line):
            context.append(line)
            prose.append(line)
        elif not line.strip():
            prose.append("")
            context.append("")
        i += 1
    # a reading decided by a recorded division is never also a voice decision
    # ("Accordingly, Bill 46 ... was read a second time" follows its division)
    divided = {(d["bill_number"], d["stage"]) for d in divisions if d["bill_number"] and d["vote_on"] == "motion"}
    return divisions, [v for v in _voices(prose) if (v["bill_number"], v["stage"]) not in divided]


def _division(context, seq, yeas, nays, yea_labels, nay_labels, problem):
    text = re.sub(r"\s+", " ", " ".join(context)).strip()
    starts = list(_ITEM_START.finditer(text))
    item = text[starts[-1].start():] if starts else text
    tail = text[-700:]
    res = _RESULT.findall(tail)
    result = None
    if res:
        head = _RESULT_HEAD.search(res[-1])
        result = (head.group(1) if head else res[-1]).strip(" ,")
    low = tail.lower()
    vote_on = ("subamendment" if re.search(r"sub\s*-?\s*amendment", low[-400:]) else
               "amendment" if re.search(r"(?:on the (?:proposed )?amendment|the amendment was|amendment,? it was)", low[-400:])
               else "motion")
    bill = stage = motion = None
    # The bill and stage come from the ITEM the division closes, the last
    # mention there winning: on 16 June 2023 the context of Bill 37's
    # third-reading division also held Bill 32's third reading, carried on
    # voice just before it.
    reads = [(m.start(), m.group(1), m.group(2)) for m in _READ_Q.finditer(item)]
    reads += [(m.start(), m.group(2), m.group(1)) for m in _ORDER_READ.finditer(item)]
    reads += [(m.start(), m.group(1), m.group(2)) for m in _READ_DEBATE.finditer(item)]
    # Committee of the Whole: "the Chair put the question on the motion that
    # Bill 19, ..., be reported as agreed to" (20 December 2011)
    reads += [(m.start(), m.group(1), "committee") for m in _COW_Q.finditer(tail)]
    if reads:
        _, bill, word = max(reads)
        stage = "Committee of the Whole" if word == "committee" else word.title() + " Reading"
    else:
        ms = _MOTION.findall(tail) or _MOTION.findall(item)
        motion = ms[-1] if ms else None
        stage = "Motion"
    return {"seq": seq, "yeas": yeas, "nays": nays, "yea_labels": yea_labels,
            "nay_labels": nay_labels, "question": item[-1500:] or None, "item": item,
            "result": result, "vote_on": vote_on, "stage": stage, "bill_number": bill,
            "motion": motion, "problem": problem}


def _voices(prose):
    paras, buf = [], []
    for l in prose:
        if l.strip():
            buf.append(l)
        elif buf:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    out, seen = [], set()

    def add(number, stage, result):
        k = (number, stage)
        if k not in seen:
            seen.add(k)
            out.append({"bill_number": number, "stage": stage, "result": result})

    text = re.sub(r"\s+", " ", " ".join(paras))
    for m in _VOICE_Q.finditer(text):
        add(m.group(1), m.group(2).title() + " Reading", re.sub(r"\s+", " ", m.group(0)))
    for m in _VOICE_MOTION.finditer(text):
        add(m.group(2), m.group(1).title() + " Reading", m.group(0))
    for m in _ACCORDINGLY.finditer(text):
        add(m.group(1), m.group(2).title() + " Reading", re.sub(r"\s+", " ", m.group(0)))
    for number, stage, result in voice_items(text):
        add(number, stage, result)
    for num, stage, word in voice_lists(prose):
        add(num, stage, "read a {0} time (listed; no recorded division)".format(word))
    return out


# 56-4: "the question being put, the motion for second reading of Bill 57
# was defeated." (8 April 2010)
# The record of the outcome itself: "Accordingly, Bill 5, An Act to Amend
# the Executive Council Act, was read a second time and ordered referred
# ..." (27 November 2019, where pypdf printed the question as "the ques tion
# being put").
_ACCORDINGLY = re.compile(r"\bAccordingly,\s+Bill (\d+),.{0,240}?\bwas\s+read\s+a\s+(second|third)\s+time\b", re.I)
_VOICE_MOTION = re.compile(
    r"the motion for (second|third) reading of Bill (\d+),?\s+(?:was|is)\s+"
    r"(?:defeated|carried|negatived|resolved in the (?:affirmative|negative))\s*\.", re.I)
_READ_ITEM = re.compile(
    r"(?:The Order being read for|Debate resumed on the motion for) (second|third) reading of Bill (\d+)\b", re.I)
_ITEM_END = re.compile(r"The Order being read|Debate resumed|Pursuant to Notice of Motion|"
                       r"The House resolved itself|And then,? \d", re.I)
_ITEM_RESULT = re.compile(
    r"question being put,?\s+the motion (?:was|is)\s+"
    r"(defeated|carried|negatived|resolved in the (?:affirmative|negative))\s*\.", re.I)


def voice_items(text):
    """[(bill_number, stage, result)] for a reading decided on voice where
    the decision names only "the motion": "Debate resumed on the motion for
    second reading of Bill 23, No One Left Behind Act. ... And the debate
    being ended and the question being put, the motion was defeated." (14
    January 2010). The item runs from its own opening to the next item; an
    item with a recorded division in it is the division's, never a voice
    decision."""
    out = []
    starts = list(_READ_ITEM.finditer(text))
    for m in starts:
        rest = text[m.end():]
        nxt = _ITEM_END.search(rest)
        seg = rest[:nxt.start()] if nxt else rest
        if re.search(r"recorded\s+division", seg, re.I):
            continue
        r = _ITEM_RESULT.search(seg)
        if r:
            out.append((m.group(2), m.group(1).title() + " Reading", re.sub(r"\s+", " ", r.group(0))))
    return out


def voice_lists(lines):
    """[(bill_number, stage, word)] from "The following Bills were read a
    third time:" lists, read LINE BY LINE. The Journals before 2016 come out
    of pypdf with no blank lines at all (8 June 2012, 30 May 2012), so a
    list cannot be found by paragraphs: the header is a line (or two lines
    joined, when it wraps), then each item starts its own line with
    "Bill N," (a "By Hon. Mr. Fitch," sponsor line may come before it), and
    a title that wraps continues on the next line until it ends with a full
    stop. The first other line ends the list."""
    lines = [l.strip() for l in lines]
    out = []
    i, n = 0, len(lines)
    while i < n:
        head = _VOICE_LIST.match(lines[i])
        used = 1
        if not head and i + 1 < n and lines[i] and lines[i + 1] and lines[i].lower().startswith(("the following bill", "the following private bill")):
            head = _VOICE_LIST.match(lines[i] + " " + lines[i + 1])
            used = 2
        if not head:
            i += 1
            continue
        stage = head.group(1).title() + " Reading"
        word = head.group(1).lower()
        j, open_title = i + used, False
        while j < n:
            line = lines[j]
            if not line:
                j += 1
                continue
            item = _LIST_ITEM.match(line)
            if item:
                out.append((item.group(1), stage, word))
                open_title = not line.endswith((".", ";"))
            elif _LIST_SPONSOR.match(line) and not open_title:
                pass
            elif open_title and not _VOICE_LIST.match(line):
                open_title = not line.endswith((".", ";"))
            else:
                break
            j += 1
        i = j
    return out


def resolve_division(raw, resolver, date, legislature, document=None):
    votes = []
    for position, labels in (("Yea", raw["yea_labels"]), ("Nay", raw["nay_labels"])):
        for k, label in enumerate(labels, 1):
            key, how = resolver.resolve(label, date, legislature, document=document)
            votes.append({"position": position, "ordinal": k, "raw_label": label, "member_key": key,
                          "how": how,
                          "party_at_vote": resolver.party_at(key, date, legislature) if key else None})
    # British Columbia's rule (prov_bc.settle_by_elimination): an ambiguous
    # label whose other candidate is already placed in the same division is
    # the one left. 59-2 prints "Ms. LeBlanc" and "Mr. LeBlanc" (Monique,
    # Jacques); the reviewed title places "Mr. LeBlanc", and Jacques cannot
    # vote twice.
    from src.ingest.prov_bc import settle_by_elimination
    settle_by_elimination(votes, resolver, date, legislature)
    ok, note = ps.tally({"Yea": raw["yeas"], "Nay": raw["nays"]}, votes)
    if raw.get("problem"):
        ok, note = False, "; ".join(x for x in (raw["problem"], note) if x)
    return votes, ok, note


_PRINTED_DIVISION = re.compile(r"\bon\s+the\s+following\s+recorded\s+division", re.I)
# A weekday as pypdf may break it ("Thursd ay", 7 December 2017).
_WEEKDAY = "(?:" + "|".join(r"\s?".join(d) for d in
                            ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")) + ")"
_DAY_TAIL = _WEEKDAY + r",?\s+(" + _MONTHS + r")\s+(\d{1,2}),?\s+(\d{4})\b"
# "Daily sitting 19 Thursday, December 7, 2017" (57-2 on)
_OWN_SITTING = re.compile(r"Daily\s+sitting\s+\d+\s+" + _DAY_TAIL)
# a line that is only the day: "Wednesday, October 27, 2010" (56-4, 57-1)
_OWN_LINE = re.compile(r"^\s*" + _DAY_TAIL + r"\.?\s*$", re.M)


def is_french(text):
    """True when a Journal listed as English is the French one: its first
    page says "Jour de séance" or "Journaux de l'Assemblée" and nowhere
    "Journal of Assembly" or "Daily sitting"."""
    head = re.sub(r"\s+", " ", (text or "")[:4000])
    return (("Jour de séance" in head or "Journaux de l" in head)
            and "Journal of Assembly" not in head and "Daily sitting" not in head)


def journal_date(text):
    """The sitting day a Journal names for itself ("Daily sitting 52 Friday,
    June 8, 2012"; "Wednesday, October 27, 2010"), from its first page, or
    None. The listing's label is not always the file's day: 57-4 links "May
    20, 2014" to 69140521e.pdf, the Journal of 21 May, and 60-1 links "October
    4, 2022" to a Question Period transcript."""
    head = (text or "")[:4000]
    m = _OWN_SITTING.search(re.sub(r"\s+", " ", head)) or _OWN_LINE.search(head)
    return _date("{0} {1}, {2}".format(m.group(1), m.group(2), m.group(3))) if m else None


def printed_divisions(text):
    """How many recorded divisions the Journal's own words announce: the
    phrase "on the following recorded division", or a YEAS header, whichever
    is counted more often (a header the parser does not know still has its
    phrase, and the reverse)."""
    lines = [normalise(l) for l in (text or "").splitlines()]
    flat = re.sub(r"\s+", " ", " ".join(lines))
    heads = sum(1 for l in lines if re.match(r"^\s*Y[EA]AS\b\s*[-–—]", l, re.I))
    return max(len(_PRINTED_DIVISION.findall(flat)), heads)


def resolver_has_roster(resolver, date, legislature):
    base = getattr(resolver, "base", resolver)
    return bool(base.valid_terms(date, legislature))


def clear_sitting(conn, legislature, session, date):
    """Delete the divisions, voice decisions and votes stored for one sitting."""
    keys = [r[0] for r in conn.execute(
        "SELECT division_key FROM prov_divisions WHERE prov=? AND legislature=? AND session=? AND date=?",
        (PROV, legislature, session, date))]
    for k in keys:
        conn.execute("DELETE FROM prov_votes WHERE division_key=?", (k,))
        conn.execute("DELETE FROM prov_division_bills WHERE division_key=?", (k,))
        conn.execute("DELETE FROM prov_divisions WHERE division_key=?", (k,))
    return len(keys)


def read_sitting(ctx, legislature, session, rec, resolver, wl):
    """Read one day's Journal. Returns (divisions, gaps_in_it)."""
    date, url = rec["date"], rec["url"]
    skey = ps.sitting_key(PROV, legislature, session, date)
    raw = ctx.bytes(url, "journal-{0}".format(date))
    if raw is None:
        return 0, 1
    try:
        text = pdf_text(raw)
    except Unreadable as exc:
        ctx.gap("{0}: {1}: {2}".format(skey, url, exc))
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
        ctx.conn.commit()
        return 0, 1
    # A Journal read again replaces everything stored from it before: an
    # earlier parser's rows (a division stored under the wrong day, a seq
    # that has moved) must not outlive the re-read.
    clear_sitting(ctx.conn, legislature, session, date)
    if is_french(text):
        # 58-1 links "March 11, 2015" to 22150311e.pdf, and the file is the
        # FRENCH Journal ("Jour de séance 22 le mercredi 11 mars 2015"). French
        # is never classified, and its readings are not cross-checked.
        ctx.gap("{0}: the English Journal {1} is the French text; not read".format(skey, url))
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
        ctx.conn.commit()
        return 0, 1
    own = journal_date(text)
    m = _DAILY.search(url)
    named = "20{0}-{1}-{2}".format(m.group(2)[:2], m.group(2)[2:4], m.group(2)[4:]) if m else None
    if own and own != date and own == named and own not in (rec.get("listed") or ()):
        # The LABEL is wrong and nothing is lost: 59-1 lists "November 3, 2018"
        # (a Saturday) for 09181120e.pdf, "Daily sitting 9 Tuesday, November 20,
        # 2018", a day the listing names nowhere else. Read under its own day;
        # the label's day is stored 'ok' and empty so it is not read again.
        ctx.log("  {0}: the listing labels the Journal of {1} as {2}; read under {1}".format(skey, own, date))
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="ok")
        date, skey = own, ps.sitting_key(PROV, legislature, session, own)
        clear_sitting(ctx.conn, legislature, session, date)
    elif own and own != date:
        # The listing files another day's Journal under this date (57-4: "May
        # 20, 2014" is 69140521e.pdf, the Journal of 21 May). Nothing is stored
        # for the day: its own record is not served.
        ctx.gap("{0}: the listing files the Journal of {1} under {2} ({3}); nothing stored for the day".format(
            skey, own, date, url))
        # 'unreadable': the day's own record is not what is served, so its
        # listed readings are not cross-checked against it, and it stays owed
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
        ctx.conn.commit()
        return 0, 1
    divisions, voices = parse_journal(text)
    gaps = 0
    printed = printed_divisions(text)
    if len(divisions) < printed:
        # The Journal says a recorded division happened and fewer were
        # read: a layout we do not know. Never 'ok': the sitting stays owed.
        gaps += 1
        ctx.gap("{0}: the Journal prints {1} recorded division(s) ('on the following recorded division'), "
                "{2} parsed; the sitting stays owed".format(skey, printed, len(divisions)))
    no_roster = not resolver_has_roster(resolver, date, legislature)
    for d in divisions:
        votes, ok, note = resolve_division(d, resolver, date, legislature, document=url)
        if no_roster and not ok:
            note = "no roster for {0}-{1}; {2}".format(legislature, session, note)
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        inherit = pc.Result(b_areas, b_terms, b_tier) if b_areas else None
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["item"]], bill_key=bkey, inherit=inherit)
        dkey = ps.division_key(PROV, legislature, session, date, d["seq"])
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        question = d["question"]
        if d["motion"] and question and not question.startswith("Motion"):
            question = "[Motion {0}] {1}".format(d["motion"], question)
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": date, "seq": d["seq"], "kind": "recorded", "question": question,
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "abstentions": None, "source_url": url,
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": note or d.get("note"), "votes": votes})
    divided = {(d["bill_number"], d["stage"]) for d in divisions if d["bill_number"] and d["vote_on"] == "motion"}
    voices = [v for v in voices if (v["bill_number"], v["stage"]) not in divided]
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
    """Every second or third reading the bills listing dates to a day whose
    Journal was read must be in that Journal, divided or on voice."""
    misses = 0
    for key, stages in ctx.conn.execute(
            "SELECT bill_key, stages FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
            (PROV, legislature, session)).fetchall():
        for s in json.loads(stages or "[]"):
            if s.get("stage") not in ("Second Reading", "Third Reading") or s.get("date") not in read_dates \
                    or (s.get("status") or "").lower() not in ("passed", "defeated"):
                continue
            hit = ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? AND stage=?",
                (key, s["date"], s["stage"])).fetchone()[0]
            if not hit:
                misses += 1
                ctx.gap("{0}: the bills listing says {1} {2} on {3}; that day's Journal gave neither "
                        "a recorded division nor a voice decision for it".format(
                            key, s["stage"], s["status"].lower(), s["date"]))
    return misses


def _listed_misses(ctx, legislature, session):
    """{date: [(bill_key, stage), ...]}: the second and third readings the
    bills listing dates to a day, passed or defeated, for which the store
    holds no division and no voice decision on that bill, stage and day."""
    out = {}
    for key, stages in ctx.conn.execute(
            "SELECT bill_key, stages FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
            (PROV, legislature, session)).fetchall():
        for s in json.loads(stages or "[]"):
            if s.get("stage") not in ("Second Reading", "Third Reading") or not s.get("date") \
                    or (s.get("status") or "").lower() not in ("passed", "defeated"):
                continue
            hit = ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? AND stage=?",
                (key, s["date"], s["stage"])).fetchone()[0]
            if not hit:
                out.setdefault(s["date"], []).append((key, s["stage"]))
    return out


def sitting_done(conn, skey):
    """True when this SITTING was read cleanly. Keyed by the sitting, not the
    file: a listing can link one file under two days (57-4, 58-2, 59-2)."""
    row = conn.execute("SELECT status FROM prov_sittings WHERE sitting_key=?", (skey,)).fetchone()
    return bool(row) and row[0] == "ok"


# Every sitting stored by a parser older than this date is read once more:
# the 2010 backfill (CI run 37026741496, 2 October 2026) stored 181 sittings
# of 57-2 to 57-4 with the old reader, 110 of them 'ok' and EMPTY although
# their Journals list readings (no blank lines), print "YAYS", or are another
# day's Journal (57-3 "May 7, 2013" is the Journal of 8 May). Neither the
# bills listing nor a gap points at all of them, so the repair is by date.
REREAD_BEFORE = "2026-10-03"


def owe_stale(ctx, legislature, session, records):
    """Make OWED every sitting of the window read before REREAD_BEFORE and
    stored 'ok'. Returns how many."""
    owed = 0
    for rec in records:
        owed += ctx.conn.execute(
            "UPDATE prov_sittings SET status='owed' WHERE sitting_key=? AND status='ok' AND read_at < ?",
            (ps.sitting_key(PROV, legislature, session, rec["date"]), REREAD_BEFORE)).rowcount
    ctx.conn.commit()
    if owed:
        ctx.log("  nb {0}-{1}: {2} sitting(s) stored 'ok' by the parser before {3}; read again".format(
            legislature, session, owed, REREAD_BEFORE))
    return owed


def owe_listed(ctx, legislature, session, records):
    """The targeted repair for sittings stored 'ok' by an older parser. A
    sitting 'ok' on whose day the bills listing dates a second or third
    reading the store has neither as a division nor on voice is made OWED,
    so this run reads it again (the 2010 backfill stored 2012-06-08 'ok'
    with nothing, though the Journal lists Bill 69 read a second and a
    third time: the old reader looked for the lists by paragraph, and the
    Journals before 2016 have no blank lines). A sitting still missing a
    listed reading after the re-read is a gap (check_listing_stages).
    Returns how many were made owed."""
    misses = _listed_misses(ctx, legislature, session)
    owed = 0
    for rec in records:
        if rec["date"] in misses:
            owed += ctx.conn.execute(
                "UPDATE prov_sittings SET status='owed' WHERE sitting_key=? AND status='ok'",
                (ps.sitting_key(PROV, legislature, session, rec["date"]),)).rowcount
    ctx.conn.commit()
    if owed:
        ctx.log("  nb {0}-{1}: {2} sitting(s) stored 'ok' miss a reading the bills listing dates to them; "
                "read again".format(legislature, session, owed))
    return owed


def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True, party=True):
    legislature, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    html = ctx.text(JOURNALS.format(legislature, sess), "journals-{0}-{1}".format(legislature, sess))
    listing = list_records(html or "")
    if html and not listing["daily"]:
        ctx.gap("nb journals {0}: no daily Journals parsed from the listing".format(session))
    records = [r for r in listing["daily"] if ctx.in_window(r["date"])]
    for f in listing.get("not_journal") or []:
        if ctx.in_window(f["date"]):
            ctx.gap("nb {0}: the journals listing links {1} for {2}, which is not a Journal; the day's Journal "
                    "is not listed".format(session, f["url"], f["date"]))
    for f in listing.get("french_only") or []:
        if ctx.in_window(f["date"]):
            ctx.gap("nb {0}: the English journals listing links only the French Journal for {1} ({2}); "
                    "not read".format(session, f["date"], f["url"]))
    stats = {"records_listed": len(records)}
    if roster:
        stats["members"] = fetch_roster(ctx, legislature, sess, listing)
    if bills:
        stats.update(fetch_bills(ctx, legislature, sess, ctx.tax, wl))
    if ctx.dry_run:
        return stats
    if not ctx.refresh:
        stats["owed_stale"] = owe_stale(ctx, legislature, sess, records)
    if bills and not ctx.refresh:
        stats["owed_listed"] = owe_listed(ctx, legislature, sess, records)
    resolver = make_resolver(ctx.conn)
    read = divs = gaps = 0
    read_dates = set()
    listed = {r["date"] for r in listing["daily"]}
    for rec in records:
        if not ctx.refresh and sitting_done(ctx.conn, ps.sitting_key(PROV, legislature, sess, rec["date"])):
            read_dates.add(rec["date"])
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        n, g = read_sitting(ctx, legislature, sess, dict(rec, listed=listed), resolver, wl)
        read += 1
        divs += n
        gaps += g
        status = ctx.conn.execute("SELECT status FROM prov_sittings WHERE sitting_key=?",
                                  (ps.sitting_key(PROV, legislature, sess, rec["date"]),)).fetchone()
        if status and status[0] != "unreadable":
            read_dates.add(rec["date"])
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps,
                  "listing_misses": check_listing_stages(ctx, legislature, sess, read_dates) if bills else 0})
    # Party at the vote, from each division day's Hansard member list, then
    # written onto every stored vote of the session the dated terms cover.
    days = {r[0] for r in ctx.conn.execute(
        "SELECT DISTINCT date FROM prov_divisions WHERE prov=? AND legislature=? AND session=? "
        "AND kind='recorded'", (PROV, legislature, sess)) if ctx.in_window(r[0])}
    if party and days:
        stats["party_lists"] = fetch_party_lists(ctx, legislature, sess, pn.Resolver.from_conn(ctx.conn, PROV),
                                                 days)
    if party and legislature in ELECTION_REPORT_LEGISLATURES:
        # Before Hansard: the Chief Electoral Officer's reports, carried to the
        # first agreeing Hansard list; derived again on every run, so a later
        # session's lists reach the earlier sessions' votes, and the whole
        # Legislature's stored votes are refreshed without re-reading a Journal.
        stats["election_results"] = fetch_election_results(ctx, legislature)
        stats["election_carried"], stats["election_withheld"] = carry_election_party(ctx.conn, legislature,
                                                                                     log=ctx.log)
        ps.refresh_party(ctx.conn, PROV, pn.Resolver.from_conn(ctx.conn, PROV), legislature)
    n, with_party = ps.refresh_party(ctx.conn, PROV, pn.Resolver.from_conn(ctx.conn, PROV), legislature, sess)
    stats["votes_with_party"] = "{0}/{1}".format(with_party, n)
    ctx.conn.commit()
    return stats
