"""Legislative Assembly of Manitoba: dated roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov mb. Scope: docs/canada-provinces-scope.md
(Manitoba: value 4, difficulty 2).

ROBOTS AND POLICY. gov.mb.ca's robots.txt gives `Disallow: /` to a list of
named AI crawlers (GPTBot, ClaudeBot, anthropic-ai, CCBot and others) and,
for `*`, disallows a few paths that do not include /legislature/.
Christopher decided on 2 October 2026 to collect Manitoba (scope,
"Decisions"): this collector is not a training crawler, it identifies itself
honestly (src/http.py), reads public parliamentary records at about one
request a second, and obeys every path disallowed for `*`. The robots file
is read on every run (src/prov_fetch.Robots); if Manitoba ever names our
agent there, every fetch becomes a gap and nothing is read. If Manitoba asks
us to stop, we stop. web2.gov.mb.ca (the bills site) answers robots.txt with
an error page: no rules.

  * LISTINGS, never constructed: business/votes_proceedings.html names each
    session's V&P calendar page (43rd/43rd_3rd.html); each calendar links a
    day's Votes and Proceedings PDF under its day number. A stray link with
    no day (42-3 prints votes_029 a second time in the 6 October cell) is
    dropped when the same file is listed under a real day. The PDF's own
    printed date ("Thursday, October 14, 2021") is the record's date.
    hansard/hansard_archive.html names each session's Hansard calendar, and
    web2.gov.mb.ca/bills/sess/index.php each session's bills page.
  * ROSTER, DATED TO THE DAY. The Assembly's member pages list only current
    MLAs. Every Hansard PDF instead prints, on its second page, the whole
    House AS AT THAT SITTING: "COX, Cathy, Hon. Kildonan-River East PC",
    "WASYLIW, Mark Fort Garry Ind.", "Vacant Fort Whyte". For every day with
    a recorded division, that day's Hansard cover is read and each member's
    term is widened to cover exactly that day (prov_store.extend_term), as
    for Saskatchewan. Party at the vote is a fact of the day: Mark Wasyliw
    is NDP in 2021 and Independent in June 2025.
  * DIVISIONS. Votes and Proceedings: "And the Question being put. It was
    negatived, on the following division:" then "YEA" (42nd Legislature) or
    "AYE" (43rd), one name per line in capitals, a riding where two members
    share a surname ("SMITH (Lagimodière)"), the printed total on the last
    name's line ("WIEBE ......... 20"), then "NAY". The totals are the tally
    check, and the count of "on the following division" phrases in the text
    is a second one: a division the parser missed is a gap. The 2010
    backfill (2 October 2026) added the older forms: the 39th's covers print
    "N.D.P."/"P.C."; a total may lack its dot leader ("WOWCHUK 49"); a list
    may have no YEA header at all; "on division." can head a full roll call;
    and a listed file that copies another listed day's record is a gap.
  * REVIEWED FACTS (config/prov_record.yaml, Christopher, 2 October 2026):
    a Hansard total replacing a misprinted one (`hansard_totals` with
    `replaces:`); days whose V&P is not served, read from Hansard's own
    division lists (`vp_not_served`, read_hansard_day); and one key per
    member (prov_store.canonical_key / merge_split_members, plus
    `same_person` across legislatures).
  * VOICE. "It was agreed to." with "The Bill was accordingly read a Second
    Time ...", "... concurred in, read a Third Time and passed", "It was
    negatived, on division" (dissent noted, no names), and the day's list of
    bills "read a First Time" are decisions without a recorded division:
    stored as kind='voice'.
  * BILLS. The session's bills page (number, sponsor, title, the HTML text
    of the bill as distributed after first reading). Each text is classified
    per passage with statute names masked (src/prov_classify.py).

Hansard speeches and the session's billstatus.pdf (stage dates) are not
read: stage dates come from the V&P themselves (scope "Built" notes).
"""

from __future__ import annotations

import datetime
import html as _html
import re
from urllib.parse import urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text, pdf_text, sessions_sorted, slug, year_span

PROV = "mb"
CURRENT_SESSION = "43-3"
BASE = "https://www.gov.mb.ca/legislature/"
VP_SESSIONS = BASE + "business/votes_proceedings.html"
HANSARD_SESSIONS = BASE + "hansard/hansard_archive.html"
BILL_SESSIONS = "https://web2.gov.mb.ca/bills/sess/index.php"

_ORD = r"(?:st|nd|rd|th)"
_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"), 1)}
_DAY_HEAD = re.compile(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
                       r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})")


def parse_session(code):
    m = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("Manitoba session must look like 43-3, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def printed_date(text):
    """The first 'Thursday, October 14, 2021' in a record, as ISO."""
    m = _DAY_HEAD.search(text or "")
    if not m or m.group(1).lower() not in _MONTHS:
        return None
    return datetime.date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()


# -- listings ---------------------------------------------------------------

def session_pages(html, base, kind):
    """{(legislature, session): url} from a listing page. kind 'vp' reads
    '43rd/43rd_3rd.html', 'hansard' '../hansard/42nd_3rd/42nd_3rd.html#top',
    'bills' '../42-3/index.php'."""
    out = {}
    if kind == "vp":
        rx = re.compile(r'href="((\d+){0}/\2{0}_(\d){0}\.html)"'.format(_ORD))
        for href, leg, sess in rx.findall(html or ""):
            out.setdefault((int(leg), int(sess)), urljoin(base, href))
    elif kind == "hansard":
        rx = re.compile(r'href="([^"#]*?/((\d+){0}_(\d){0})/\2\.html)(?:#[^"]*)?"'.format(_ORD))
        for href, _code, leg, sess in rx.findall(html or ""):
            out.setdefault((int(leg), int(sess)), urljoin(base, href))
    elif kind == "bills":
        for href, leg, sess in re.findall(r'href="((?:\.\./)?(\d+)-(\d)/index\.php)"', html or ""):
            out.setdefault((int(leg), int(sess)), urljoin(base, href))
    return out


_VP_SESSION_HREF = re.compile(r'href="((\d+){0}/\2{0}_(\d){0}\.html)"'.format(_ORD))
_YEARS = re.compile(r"(?<!\d)(\d{4})(?:\s*-\s*(\d{4}))?(?!\d)")


def parse_sessions(html):
    """Every session on the V&P sessions page, one table row each: the
    years cell ("2010 - 2011", "&nbsp;2016&nbsp;") and the session's link.
    A row without years still names its session, with no span (it is read
    by any window)."""
    out = []
    for row in re.findall(r"<tr\b(.*?)</tr>", html or "", re.S | re.I):
        link = _VP_SESSION_HREF.search(row)
        if not link:
            continue
        code = "{0}-{1}".format(int(link.group(2)), int(link.group(3)))
        years = _YEARS.search(_html.unescape(re.sub(r"<[^>]+>", " ", row[:link.start()])))
        out.append(year_span(code, years.group(1), years.group(2)) if years
                   else {"code": code, "start": None, "end": None})
    return sessions_sorted(out)


def list_sessions(ctx):
    listing = ctx.text(VP_SESSIONS, "vp-sessions")
    out = parse_sessions(listing)
    if listing and not out:
        ctx.gap("mb: no sessions parsed from {0}".format(VP_SESSIONS))
    return out


_CAL = re.compile(r'<table class="calendar">(.*?)</table>', re.S)
_CELL = re.compile(r"<td\b[^>]*>(.*?)(?=<td\b|</td>|</tr>|</tbody>|</table>|$)", re.S)
_CAL_TITLE = re.compile(r'thead_title">(?:<a[^>]*></a>)?\s*([A-Za-z]+)\s+(\d{4})')


def parse_calendar(html, base, href_rx):
    """[(date or None, url, link_text)] for every link matching href_rx in a
    session calendar page, with the date of the day cell it sits in."""
    out = []
    for table in _CAL.findall(html or ""):
        t = _CAL_TITLE.search(table)
        if not t or t.group(1).lower() not in _MONTHS:
            continue
        month, year = _MONTHS[t.group(1).lower()], int(t.group(2))
        # A cell ends where the next one starts, not at its own </td>: the
        # 40-2 Hansard calendar leaves 16 April 2013's cell unclosed, which
        # filed the 17th's Volume 24 under the 16th and left the 17th's
        # division with no roster.
        for cell in _CELL.findall(table):
            text = html_text(cell)
            day = re.match(r"(\d{1,2})\b", text)
            for href, label in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', cell, re.S):
                if not re.search(href_rx, href):
                    continue
                label = html_text(label)
                date = None
                if day:
                    try:
                        date = datetime.date(year, month, int(day.group(1))).isoformat()
                    except ValueError:
                        date = None
                out.append((date, urljoin(base, _html.unescape(href)), label))
    return out


def list_records(html, base):
    """[(date, url)] of V&P PDFs. A link whose text is not the day number is
    a stray (42-3 links votes_029 again, blank, in the 6 October cell): it
    is dropped when the same file is listed under its day, and kept with
    date None (the PDF's printed date decides) when it is not."""
    dated, undated = {}, []
    for date, url, label in parse_calendar(html, base, r"votes_\d+\w*\.pdf$"):
        if label.isdigit() and date:
            dated.setdefault(url, date)
        else:
            undated.append(url)
    out = sorted((d, u) for u, d in dated.items())
    out += [(None, u) for u in dict.fromkeys(undated) if u not in dated]
    return out


def list_hansard(html, base):
    """{date: [pdf url, ...]} in the order printed (82A before 82B)."""
    out = {}
    for date, url, _label in parse_calendar(html, base, r"hansardpdf/\w+\.pdf$"):
        if date:
            out.setdefault(date, [])
            if url not in out[date]:
                out[date].append(url)
    return out


# -- the Hansard cover roster -----------------------------------------------

# The surname in capitals, except a Scottish prefix the cover prints in
# mixed case ("McFADYEN, Hugh", "McGIFFORD, Diane"). The party as printed:
# "NDP"/"PC" from the 40th Legislature, "N.D.P."/"P.C." in the 39th's covers
# (2010-2011), which the old pattern never matched -- only the two "Lib."
# lines were read and every division of those days failed the tally.
_COVER_LINE = re.compile(r"^\s*(?P<sur>(?:Ma?c)?[A-ZÀ-Ý][A-ZÀ-Ý'’ .\-]+?),\s*(?P<rest>.+?)\s+"
                         r"(?P<party>N\.D\.P\.|P\.C\.|NDP|PC|Lib\.|Liberal|Ind\.|IND|Ind|Green"
                         r"|[A-Z][A-Za-z]{0,4}\.?)\s*$")
# One spelling per party across the years, so party at the vote compares.
_PARTY_SPELLING = {"N.D.P.": "NDP", "P.C.": "PC"}


def _title(surname):
    def word(w):
        m = re.match(r"^(Ma?c)([A-ZÀ-Ý].*)$", w)
        if m:                                  # McFADYEN -> McFadyen
            return m.group(1) + m.group(2)[:1] + m.group(2)[1:].lower()
        return w[:1] + w[1:].lower()
    return "-".join(" ".join(word(w) for w in part.split(" ")) for part in surname.split("-"))


def parse_cover(text):
    """(members, vacancies) from a Hansard PDF's member page.
    members: [{surname, given, riding, party, key, hon}]"""
    t = text or ""
    start = t.find("Political Affiliation")
    if start < 0:
        return [], 0
    members, vacant = [], 0
    for line in t[start + len("Political Affiliation"):].splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("LEGISLATIVE ASSEMBLY OF MANITOBA") or _DAY_HEAD.search(s):
            break
        if s.startswith("Vacant"):
            vacant += 1
            continue
        m = _COVER_LINE.match(s)
        if not m:
            continue
        rest = m.group("rest").strip()
        hon = False
        h = re.match(r"^(.*?),\s*Hon\.\s+(.+)$", rest)
        if h:
            given, riding, hon = h.group(1).strip(), h.group(2).strip(), True
        else:
            # One given name, then the constituency: true of every member
            # listed in the 42nd and 43rd Legislatures. A two-word given name
            # would put a word into the riding, which then fails to match a
            # "SMITH (Riding)" label -- a gap, never a wrong member.
            given, _, riding = rest.partition(" ")
        surname = _title(m.group("sur").strip())
        members.append({"surname": surname, "given": given, "riding": riding.strip() or None,
                        "party": _PARTY_SPELLING.get(m.group("party"), m.group("party")), "hon": hon,
                        "key": slug(given + " " + surname)})
    return members, vacant


COVER_MIN = 40     # fewer members than this read from a cover is a gap


def roster_for_day(ctx, legislature, date, hansard, owed=False):
    """Read the day's Hansard cover and widen every member's term to it.

    owed: the sitting is being read AGAIN because an earlier read left a gap.
    Its cover is then read again too: a cover read by an older parser can
    hold most of the House and still miss the member whose name failed the
    tally (Hugh McFadyen, 2011-2012: "McFADYEN" never matched the capitals
    pattern), and the terms it left behind would otherwise say "read"."""
    # Was THIS day's cover read already? Terms are widened to each cover
    # read, so only a term that starts or ends on the day says so; one that
    # merely spans it does not (2 October 2026, the fault Saskatchewan's
    # backfill exposed: a member on an early and a late cover but not this
    # one would be "covered", and a later member missing, so the day's
    # divisions fail the tally).
    have = ctx.conn.execute(
        "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source='hansard-cover' "
        "AND (start=? OR end=?)", (PROV, date, date)).fetchone()[0]
    # A cover that gave fewer than COVER_MIN members (the 39th Legislature's
    # "N.D.P." covers gave 2) was not read: its two terms do not count.
    if have >= COVER_MIN and not ctx.refresh and not owed:
        return have
    urls = (hansard or {}).get(date) or []
    if not urls:
        ctx.gap("mb {0}: no Hansard listed for the day, so no roster as at the day "
                "(Hansard lags the V&P; the day stays owed)".format(date))
        return 0
    raw = ctx.bytes(urls[0], "hansard-{0}".format(date))
    if not raw:
        return 0
    try:
        text = pdf_text(raw, pages=[0, 1, 2])
    except Unreadable as exc:
        ctx.gap("mb {0}: Hansard cover {1}: {2}".format(date, urls[0], exc))
        return 0
    members, _vacant = parse_cover(text)
    if len(members) < COVER_MIN:
        ctx.gap("mb {0}: only {1} member(s) parsed from the Hansard cover {2}".format(
            date, len(members), urls[0]))
        if not members:
            return 0
    newest = ctx.conn.execute("SELECT MAX(end) FROM prov_member_terms WHERE prov=? AND "
                              "source='hansard-cover'", (PROV,)).fetchone()[0]
    is_newest = newest is None or date >= newest
    if is_newest:
        ctx.conn.execute("UPDATE prov_members SET sitting=0 WHERE prov=?", (PROV,))
    # One member, one key (prov_store.canonical_key, as Ontario): a cover
    # printing "Greg DEWAR" after the store holds "Gregory DEWAR" for
    # Selkirk in the same legislature stores the term under the held key.
    seats = ps.seat_holders(ctx.conn, PROV, legislature)
    for m in members:
        key = ps.canonical_key(ctx.conn, PROV, m, seats, legislature)
        own = key == m["key"]
        ps.upsert_member(ctx.conn, PROV, key, name=m["given"] + " " + m["surname"] if own else None,
                         surname=m["surname"] if own else None, given=m["given"] if own else None,
                         riding=m["riding"] if is_newest else None,
                         party=m["party"] if is_newest else None,
                         sitting=1 if is_newest else None)
        ps.extend_term(ctx.conn, PROV, key, legislature, m["party"], m["riding"],
                       date, "hansard-cover")
    ctx.conn.commit()
    return len(members)


# -- Votes and Proceedings ----------------------------------------------------

HEADER = re.compile(r"^\s*(YEAS?|AYES?|NAYS?)\s*:?\s*$")
_LEADER = re.compile(r"^(.*?)\s*\.{4,}\s*(\d+)\s*$")
# The total without its dot leader: 3 June 2010 prints "WOWCHUK 49" and,
# for the nil NAY list, a bare "0" (a bare 0 is never a page number).
_BARE_TOTAL = re.compile(r"^([A-ZÀ-Ý][A-ZÀ-Ý'’ .\-]*?(?:\s*\([^()]*\))?)\s+(\d{1,2})$")
_NIL = re.compile(r"^\s*0\s*$")
_SEPARATOR = re.compile(r"^\s*_{6,}\s*$")
_BILL_NO = re.compile(r"Bill\s*\(No\.\s*(\d+)\)")
_TITLE = re.compile(r"\(No\.\s*(\d+)\)\s*[–—-]\s*(.+?)\s*/\s*(?:Loi|Code)\b")
_PUT = re.compile(r"And the Question being put(?: on the (amendment|sub-?amendment|main motion|motion))?\."
                  r"\s*It was (agreed to|negatived)(,\s*unanimously|,\s*on division|,\s*on the following division)?",
                  re.I)
_VOICE_BILL = re.compile(r"The Bill was accordingly (read a Second Time|concurred in, read a Third Time)", re.I)
_FIRST_LIST = re.compile(r"The following Bills? (?:was|were) read a First Time", re.I)


def _stage(text):
    """The stage named last in a block's text."""
    found = None
    for m in re.finditer(r"(be now read a Second Time|read for a Third Time|concurred in and be now read"
                         r"|Report Stage|read a First Time|be now received and read a First Time)", text, re.I):
        w = m.group(1).lower()
        found = ("Second Reading" if "second" in w else "Third Reading" if ("third" in w or "concurred" in w)
                 else "Report Stage" if "report" in w else "First Reading")
    return found


def _blocks(text):
    """The V&P split at its own '______' item rules, furniture removed."""
    blocks, cur = [], []
    for line in (text or "").splitlines():
        if _SEPARATOR.match(line):
            blocks.append(cur)
            cur = []
            continue
        if pn.is_furniture(line) and not _NIL.match(line):
            continue
        cur.append(line.rstrip())
    blocks.append(cur)
    return [b for b in blocks if any(l.strip() for l in b)]


def _take_list(lines, i):
    """(labels, total, i, problem) for one AYE/NAY list starting after its
    header at lines[i]. The total is printed on the last name's line."""
    labels, n = [], len(lines)
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        lead = _LEADER.match(s)
        if lead:
            if lead.group(1).strip():
                labels.append(lead.group(1).strip())
            return labels, int(lead.group(2)), i + 1, None
        bare = _BARE_TOTAL.match(s)
        if bare:
            labels.append(bare.group(1).strip())
            return labels, int(bare.group(2)), i + 1, None
        if _NIL.match(s) and not labels:
            return labels, 0, i + 1, None
        if HEADER.match(s):
            return labels, None, i, "a list ended without its printed total"
        if s.startswith("(") and labels and not labels[-1].endswith(")"):
            labels[-1] += " " + s        # a riding wrapped onto its own line
        elif labels and labels[-1].count("(") > labels[-1].count(")"):
            labels[-1] += " " + s        # a riding split across lines
        elif re.match(r"^[A-ZÀ-Ý][A-ZÀ-Ý'’ .\-]*(?:\s*\([^()]*\)?)?$", s):
            labels.append(s)
        else:
            return labels, None, i, "unexpected line in a name list: {0!r}".format(s[:60])
        i += 1
    return labels, None, i, "the record ended inside a name list"


def _unheaded_yea(context, line):
    """True when `line` opens a YEA list the record printed without its
    header: the name comes straight after "on the following division:"
    (24 May 2018's second division and 15 March 2019 have no "YEA" in the
    PDF at all, only the NAY header after the first list's total). The YEA
    list always comes first, so the list is the YEA list; the NAY header
    and both printed totals are still required by the tally check."""
    if not re.match(r"^[A-ZÀ-Ý][A-ZÀ-Ý'’ .\-]*(?:\s*\([^()]*\)?)?$", line.strip()) or HEADER.match(line):
        return False
    tail = [l for l in context if l.strip()][-2:]
    return re.sub(r"\s+", "", " ".join(tail)).lower().endswith(("onthefollowingdivision:",
                                                                   "onthefollowingdivision"))


def expected_divisions(text):
    """How many recorded divisions the record itself announces: every "on the
    following division", counted with page furniture and all spacing removed
    (29 April 2013 prints "on th e following division"; a page break can
    fall inside the phrase), plus every "on division." that runs straight
    into a YEA/AYE list: 19 April 2012 prints "It was agreed to, on
    division." over a full roll call with its totals."""
    lines = [l for l in (text or "").splitlines() if not pn.is_furniture(l)]
    squashed = re.sub(r"\s+", "", " ".join(lines)).lower()
    rolled = sum(1 for k, l in enumerate(lines[:-1])
                 if re.search(r"\bon\s*division\s*[.:,]?\s*$", l, re.I) and HEADER.match(lines[k + 1])
                 and HEADER.match(lines[k + 1]).group(1).upper().startswith(("YEA", "AYE")))
    # A phrase the record printed twice running is one announcement: 11 June
    # 2012, "It was negatived, on the following divisi on, on the following
    # division:" over one roll call.
    return len(re.findall(r"(?:onthefollowingdivision[,:;.]?)+", squashed)) + rolled


def parse_vp(text):
    """(divisions, voices, titles, expected) from one day's V&P text.

    divisions: [{seq, vote_on, yeas, nays, yea_labels, nay_labels, question,
                 result, stage, bill_number, problem}]
    voices:    [{bill_number, stage, result}]
    titles:    {number: English title}
    expected:  how many times the text says "on the following division"."""
    divisions, voices, titles = [], [], {}
    flat = re.sub(r"\s+", " ", text or "")
    expected = expected_divisions(text)
    for num, title in _TITLE.findall(flat):
        titles.setdefault(num, title.strip(" ,"))
    for block in _blocks(text):
        joined = re.sub(r"\s+", " ", " ".join(block)).strip()
        # "Bill (No. 226)", or a motion naming the bill only by its titled
        # number: "THAT (No. 229) – The Intoxicated Persons Detention
        # Amendment Act/Loi ..., be now read a Second Time" (24 May 2018).
        bill = (_BILL_NO.findall(joined) or [n for n, _t in _TITLE.findall(joined)] or [None])[-1]
        context, i, n = [], 0, len(block)
        block_divs = []
        while i < n:
            line = block[i]
            h = HEADER.match(line)
            if h and h.group(1).upper().startswith(("YEA", "AYE")):
                first = i + 1
            elif _unheaded_yea(context, line):
                first = i
            else:
                context.append(line)
                i += 1
                continue
            yea_labels, yeas, i, problem = _take_list(block, first)
            while i < n and not block[i].strip():
                i += 1
            nay_labels, nays = [], None
            if i < n and HEADER.match(block[i]) and HEADER.match(block[i]).group(1).upper().startswith("NAY"):
                nay_labels, nays, i, p2 = _take_list(block, i + 1)
                problem = problem or p2
            else:
                problem = problem or "no NAY list after the YEA list"
            ctx_text = re.sub(r"\s+", " ", " ".join(context)).strip()
            upto = re.sub(r"\s+", " ", " ".join(block[:i])).strip()
            puts = _PUT.findall(ctx_text)
            on = (puts[-1][0] or "motion").lower() if puts else "motion"
            d = {"seq": len(divisions) + 1,
                 "vote_on": "amendment" if on == "amendment" else
                            "subamendment" if on.startswith("sub") else "motion",
                 "yeas": yeas, "nays": nays, "yea_labels": yea_labels, "nay_labels": nay_labels,
                 "question": ctx_text[-700:] or None,
                 # the record's own words: "on division" over a roll call (19 April 2012) stays so
                 "result": "It was {0}{1}".format(puts[-1][1].lower(), re.sub(r"\s+", " ", puts[-1][2])
                                                  or ", on the following division") if puts else None,
                 "stage": _stage(upto) or "Motion",
                 "bill_number": (_BILL_NO.findall(upto) or [bill])[-1],
                 "problem": problem}
            divisions.append(d)
            block_divs.append(d)
            context = []
        # Voice decisions in this block: a question put without a recorded
        # division, on a bill stage, where no recorded division in the block
        # was on the main question.
        main_recorded = any(d["vote_on"] == "motion" for d in block_divs)
        stage = _stage(joined)
        if bill and stage in ("Second Reading", "Third Reading") and not main_recorded:
            for on, result, how in _PUT.findall(joined):
                if (on or "motion").lower() not in ("motion", "main motion"):
                    continue
                if "following division" in (how or "").lower():
                    continue
                voices.append({"bill_number": bill, "stage": stage,
                               "result": "It was {0}{1}".format(result.lower(), how or "")})
                break
            else:
                v = _VOICE_BILL.search(joined)
                if v:
                    voices.append({"bill_number": bill, "stage": stage, "result": v.group(0)})
        if _FIRST_LIST.search(joined):
            tail = joined[_FIRST_LIST.search(joined).end():]
            for num in re.findall(r"\(No\.\s*(\d+)\)", tail):
                voices.append({"bill_number": num, "stage": "First Reading",
                               "result": "read a First Time"})
    seen, unique = set(), []
    for v in voices:
        k = (v["bill_number"], v["stage"])
        if k not in seen:
            seen.add(k)
            unique.append(v)
    return divisions, unique, titles, expected


def resolve_division(raw, resolver, date, legislature):
    votes = []
    for position, labels in (("Yea", raw["yea_labels"]), ("Nay", raw["nay_labels"])):
        for k, label in enumerate(labels, 1):
            key, how = resolver.resolve(label, date, legislature)
            votes.append({"position": position, "ordinal": k, "raw_label": label, "member_key": key,
                          "how": how,
                          "party_at_vote": resolver.party_at(key, date, legislature) if key else None})
    ok, note = ps.tally({"Yea": raw["yeas"], "Nay": raw["nays"]}, votes)
    if raw.get("problem"):
        ok, note = False, "; ".join(x for x in (raw["problem"], note) if x)
    return votes, ok, note


def apply_reviewed(d, reviewed, division_key):
    """(division, notes) with the division-scoped reviewed facts of
    config/prov_record.yaml applied (pn.ReviewedDivisions): a Hansard total
    that replaces a misprinted one, or a bill the record misnumbers. Every
    applied or refused fact is a note, stored in tally_note."""
    if reviewed is None:
        return d, []
    d, notes = dict(d), []
    for position, field in (("Yea", "yeas"), ("Nay", "nays")):
        value, note = reviewed.total(division_key, position, d[field])
        if note:
            notes.append(note)
        d[field] = value
    number, note = reviewed.bill(division_key, d["bill_number"])
    if note:
        notes.append(note)
    d["bill_number"] = number
    return d, notes


# -- Hansard's own division lists, for a day whose V&P is not served ----------
#
# Christopher, 2 October 2026: where the V&P the calendar lists is not served
# (an error page, or a copy of another day's record), a REVIEWED entry in
# config/prov_record.yaml (`vp_not_served`) names the day, the failing V&P
# and the day's Hansard PDFs, and Hansard's own lists are read instead:
#
#     Division
#     A RECORDED VOTE was taken, the result being as follows:
#     Yeas
#     Bindle, Clarke, Cox, ..., Smith (Southdale), ...
#     Nays
#     Allum, Altemeyer, ...
#     Deputy Clerk (Mr. Rick Yarish): Yeas 35, Nays 17.
#
# The Clerk's counts are the printed totals the tally check holds the names
# to. Never used for a day whose V&P is served.

_HAN_FURNITURE = re.compile(r"^\s*(?:=+PAGE|\*\s*\*\s*\*|\*\s*\(\d{1,2}:\d{2}\))|LEGISLATIVE ASSEMBLY OF MANITOBA")
_HAN_DIVISION = re.compile(
    r"A\s+RECORDED\s+VOTE\s+was\s+taken,\s*the\s+result\s+being\s+as\s+follows:\s*Yeas\s*(?P<yeas>.*?)\s*Nays\s*(?P<nays>.*?)"
    r"\s*(?:Deputy\s+)?Clerk[^:]*:\s*Yeas\s*(?P<y>\d+)\s*,\s*Nays\s*(?P<n>\d+)\s*\.", re.S)
# the question runs to its full stop, not to the one in "(Mr. Friesen)"
_HAN_QUESTION = re.compile(r"The question before the House (?:now )?is\s+(.*?)"
                           r"(?:(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bHon)(?<!\bDr)\.\s|\?\s|$)", re.S)
_HAN_DECLARED = re.compile(r"\b(carried|passed|lost|defeated|negatived)\b", re.I)


def _han_labels(text):
    """'Bindle, Clarke, Smith (Southdale), Smook , Morley -Lecomte.' -> labels."""
    t = re.sub(r"\s+", " ", text or "").strip().rstrip(".")
    return [x.strip() for x in t.split(",") if x.strip()]


def parse_hansard_divisions(text):
    """(divisions, expected) from a Hansard day's text: one dict per "A
    RECORDED VOTE", shaped as parse_vp's, labels as printed (mixed case)."""
    lines = [l for l in (text or "").splitlines() if not _HAN_FURNITURE.search(l)]
    flat = re.sub(r"[ \t]+", " ", "\n".join(lines))
    expected = len(re.findall(r"A\s+RECORDED\s+VOTE\s+was\s+taken", flat))
    out = []
    for m in _HAN_DIVISION.finditer(flat):
        before = flat[max(0, m.start() - 2500):m.start()]
        qs = _HAN_QUESTION.findall(before)
        question = re.sub(r"\s+", " ", qs[-1]).strip() if qs else None
        yeas, nays = int(m.group("y")), int(m.group("n"))
        declared = _HAN_DECLARED.search(flat[m.end():m.end() + 300])
        word = declared.group(1).lower() if declared else None
        passed = word in ("carried", "passed") if word else None
        problem = None
        if passed is None:
            problem = "no result declared after the Clerk's count"
        elif passed != (yeas > nays):
            problem = "the declared result ({0}) does not follow the count {1}-{2}".format(word, yeas, nays)
        q = (question or "").lower()
        bill = re.findall(r"\bBill\s+(\d+)", question or "")
        out.append({"seq": len(out) + 1,
                    "vote_on": "subamendment" if q.startswith(("the proposed subamendment", "the subamendment"))
                               else "amendment" if q.startswith(("the proposed amendment", "the amendment"))
                               else "motion",
                    "yeas": yeas, "nays": nays,
                    "yea_labels": _han_labels(m.group("yeas")), "nay_labels": _han_labels(m.group("nays")),
                    "question": ("The question before the House is " + question)[:700] if question else None,
                    "result": "It was {0}, on a recorded vote (Hansard)".format(
                        "agreed to" if passed else "negatived") if passed is not None else None,
                    "stage": "Motion" if "adjourn" in q or not bill else
                             "Third Reading" if "third reading" in q else
                             "Second Reading" if "second reading" in q else "Motion",
                    "bill_number": bill[-1] if bill else None,
                    "problem": problem})
    return out, expected


def close_hansard_label(label, vocab):
    """'Fontai ne' -> 'Fontaine' and 'J ohnson' -> 'Johnson': pypdf splits a
    surname; it is closed up only when the joined form is a surname on the
    roster and the split form is not."""
    m = re.match(r"^(.*?)\s*(\([^()]*\))?$", label.strip())
    name, riding = m.group(1).strip(), m.group(2)
    toks = tuple(pn.fold(name).replace("-", " - ").split())
    if len(toks) > 1 and toks not in vocab and ("".join(toks),) in vocab:
        name = name.replace(" ", "")
    return name + (" " + riding if riding else "")


def read_hansard_day(ctx, legislature, session, listed_date, url, entry, hansard, wl):
    """The reviewed Hansard read for a day whose V&P is not served."""
    day = (hansard or {}).get(listed_date) or []
    missing = [u for u in entry["hansard"] if u not in day]
    if missing:
        ctx.gap("mb {0}: reviewed Hansard {1} is not in the day's Hansard listing; not read".format(
            listed_date, ", ".join(missing)))
        return 0, 1
    divisions, expected, source = [], 0, None
    for h in entry["hansard"]:
        raw = ctx.bytes(h, "hansard-{0}".format(listed_date))
        if not raw:
            return 0, 1
        try:
            found, n = parse_hansard_divisions(pdf_text(raw))
        except Unreadable as exc:
            ctx.gap("mb {0}: Hansard {1}: {2}".format(listed_date, h, exc))
            return 0, 1
        for d in found:
            d["source_url"] = h
        divisions += found
        expected += n
    for k, d in enumerate(divisions, 1):
        d["seq"] = k
    gaps = 0
    if not (expected == len(divisions) == entry["divisions"]):
        gaps += 1
        ctx.gap("mb {0}: Hansard prints {1} recorded vote(s), {2} parsed, the reviewed entry says {3}".format(
            listed_date, expected, len(divisions), entry["divisions"]))
    if divisions:
        roster_for_day(ctx, legislature, listed_date, hansard)
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    vocab = resolver.surname_vocab()
    for d in divisions:
        d["yea_labels"] = [close_hansard_label(x, vocab) for x in d["yea_labels"]]
        d["nay_labels"] = [close_hansard_label(x, vocab) for x in d["nay_labels"]]
    gaps += _store_divisions(ctx, legislature, session, listed_date, divisions, None, wl, resolver,
                             note="read from Hansard: the day's V&P is not served ({0})".format(pn.REVIEWED))
    ps.store_sitting(ctx.conn, PROV, ps.sitting_key(PROV, legislature, session, listed_date), listed_date,
                     url, divisions=len(divisions), status="gap" if gaps else "ok")
    ctx.conn.commit()
    ctx.log("  mb {0}: V&P not served; {1} division(s) read from Hansard".format(listed_date, len(divisions)))
    return len(divisions), gaps


def _not_served(ctx, listed_date, url):
    for e in getattr(ctx, "mb_not_served", None) or []:
        if e["date"] == listed_date and e["record"] == url:
            return e
    return None


def _store_divisions(ctx, legislature, session, date, divisions, url, wl, resolver, note=None):
    """Resolve, tally and store recorded divisions; returns the gaps."""
    gaps = 0
    reviewed = getattr(ctx, "mb_reviewed", None)
    for d in divisions:
        dkey = ps.division_key(PROV, legislature, session, date, d["seq"])
        d, notes = apply_reviewed(d, reviewed, dkey)
        votes, ok, tally_note = resolve_division(d, resolver, date, legislature)
        tally_note = "; ".join(x for x in [note] + notes + [tally_note] if x) or None
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["question"]], bill_key=bkey,
                          inherit=pc.Result(b_areas, b_terms, b_tier) if b_areas else None)
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, tally_note))
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": date, "seq": d["seq"], "kind": "recorded", "question": d["question"],
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "source_url": d.get("source_url") or url,
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": tally_note, "votes": votes})
    return gaps


def read_sitting(ctx, legislature, session, listed_date, url, hansard, wl):
    """Read one V&P. Returns (divisions, gaps_in_it)."""
    data = ctx.bytes(url, "vp-{0}".format(listed_date or "undated"))
    if data is None:
        return 0, 1
    try:
        text = pdf_text(data)
    except Unreadable as exc:
        entry = _not_served(ctx, listed_date, url)
        if entry and ctx.in_window(listed_date):
            return read_hansard_day(ctx, legislature, session, listed_date, url, entry, hansard, wl)
        ctx.gap("mb {0}: {1}: {2}".format(listed_date, url, exc))
        if listed_date:
            ps.store_sitting(ctx.conn, PROV, ps.sitting_key(PROV, legislature, session, listed_date),
                             listed_date, url, status="unreadable")
        return 0, 1
    date = printed_date(text) or listed_date
    if listed_date and date != listed_date:
        other = (getattr(ctx, "mb_listed", None) or {}).get(date)
        if other and other != url and ctx.in_window(listed_date):
            entry = _not_served(ctx, listed_date, url)
            if entry:
                return read_hansard_day(ctx, legislature, session, listed_date, url, entry, hansard, wl)
            # The file is a second copy of ANOTHER listed day's record, so the
            # listed day's own record is not served at all: 42-4 votes_041.pdf
            # (listed for 25 April 2022) is V&P No. 42 of the 26th, and the
            # 25th's three recorded divisions (Hansard No. 41) are in no V&P
            # the site serves. A hole, never a silent log line.
            ctx.gap("mb {0}: the record listed for the day ({1}) is a copy of {2}'s ({3}); "
                    "the day's own V&P is not served".format(listed_date, url, date, other))
            ps.store_sitting(ctx.conn, PROV, ps.sitting_key(PROV, legislature, session, listed_date),
                             listed_date, url, status="gap")
            ctx.conn.commit()
            return 0, 1
        ctx.log("  mb: {0} is listed under {1} but prints {2}; the record's own date is used".format(
            url, listed_date, date))
    if not date:
        ctx.gap("mb: {0} has no listed or printed date".format(url))
        return 0, 1
    if not ctx.in_window(date):
        return 0, 0
    skey = ps.sitting_key(PROV, legislature, session, date)
    divisions, voices, titles, expected = parse_vp(text)
    gaps = 0
    if divisions:
        before = ctx.conn.execute("SELECT status FROM prov_sittings WHERE record_url=? "
                                  "ORDER BY read_at DESC LIMIT 1", (url,)).fetchone()
        roster_for_day(ctx, legislature, date, hansard, owed=bool(before) and before[0] != "ok")
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    for number, title in titles.items():
        key = ps.bill_key(PROV, legislature, session, number)
        res = pc.classify(ctx.tax, wl, PROV, title=title, bill_key=key)
        ps.store_bill(ctx.conn, {"bill_key": key, "prov": PROV, "legislature": legislature,
                                 "session": session, "number": number, "title_en": title,
                                 "areas": res.areas, "matched_terms": res.terms, "tier": res.tier,
                                 "excerpt": res.excerpt})
    if expected != len(divisions):
        gaps += 1
        ctx.gap("{0}: the record says 'on the following division' {1} time(s) but {2} "
                "division(s) were parsed".format(skey, expected, len(divisions)))
    gaps += _store_divisions(ctx, legislature, session, date, divisions, url, wl, resolver)
    for v in voices:
        bkey = ps.bill_key(PROV, legislature, session, v["bill_number"])
        areas, terms, tier = ps.bill_areas(ctx.conn, bkey)
        ps.store_division(ctx.conn, {
            "division_key": ps.division_key(PROV, legislature, session, date, "v{0}-{1}".format(
                v["bill_number"], {"First Reading": "1r", "Second Reading": "2r",
                                   "Third Reading": "3r"}[v["stage"]])),
            "prov": PROV, "legislature": legislature, "session": session, "date": date, "seq": "v",
            "kind": "voice", "bill_key": bkey, "stage": v["stage"], "result": v["result"],
            "source_url": url, "areas": areas, "matched_terms": terms, "tier": tier})
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions), voice=len(voices),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return len(divisions), gaps


# -- bills ------------------------------------------------------------------

_BILL_ROW = re.compile(r'<tr>\s*<td class="right sm">\s*(\d+)\s*</td>\s*<td class="left sm8">(.*?)</td>(.*?)</tr>',
                       re.S)


def parse_bill_list(html, base):
    """[{number, sponsor, title, text_url, pdf_url, is_government}]"""
    out = []
    kind = None
    for m in re.finditer(r'<td class="centerbig"[^>]*>(.*?)</td>|' + _BILL_ROW.pattern, html or "", re.S):
        if m.group(1) is not None:
            kind = html_text(m.group(1))
            continue
        number, sponsor, rest = m.group(2), m.group(3), m.group(4)
        sponsor = html_text(re.split(r"<br\s*/?>", sponsor)[0]) or None
        link = re.search(r'<a href="(b\d+\w*\.php)">(.*?)</a>', rest, re.S)
        pdf = re.search(r'<a class="sm" href="(pdf/[^"]+\.pdf)"', rest)
        title = html_text(link.group(2)) if link else html_text(re.split(r"&mdash;|—", rest)[0])
        out.append({"number": number, "sponsor": sponsor, "title": title or None,
                    "text_url": urljoin(base, link.group(1)) if link else None,
                    "pdf_url": urljoin(base, pdf.group(1)) if pdf else None,
                    "is_government": 1 if (kind or "").lower().startswith("government") else 0,
                    "bill_type": kind})
    return out


def bill_text(html):
    """The bill's own text from its HTML page (from the 'chapter' heading to
    the end of the content), site chrome removed."""
    s = html or ""
    i = s.find('<p class="chapter">')
    j = s.find("<!--end content-->")
    body = s[i if i >= 0 else 0:j if j > i else len(s)]
    body = re.sub(r"</(p|tr|h\d|li|div)>", "\n\n", body, flags=re.I)
    return "\n".join(html_text(p) for p in body.split("\n\n") if html_text(p))


def fetch_bills(ctx, legislature, session, wl):
    sessions = ctx.text(BILL_SESSIONS, "bill-sessions")
    url = session_pages(sessions, BILL_SESSIONS, "bills").get((legislature, session)) if sessions else None
    if sessions and not url:
        ctx.gap("mb bills: session {0}-{1} not on the bills sessions page".format(legislature, session))
    html = ctx.text(url, "bills-{0}-{1}".format(legislature, session)) if url else None
    items = parse_bill_list(html, url) if html else []
    if html and not items:
        ctx.gap("mb bills {0}-{1}: no bills parsed from the listing".format(legislature, session))
    if ctx.dry_run:
        return {"bills": len(items)}
    texts = 0
    for it in items:
        key = ps.bill_key(PROV, legislature, session, it["number"])
        record = {"bill_key": key, "prov": PROV, "legislature": legislature, "session": session,
                  "number": it["number"], "title_en": it["title"], "sponsor": it["sponsor"],
                  "is_government": it["is_government"], "bill_type": it["bill_type"],
                  "page_url": it["text_url"], "text_url": it["text_url"] or it["pdf_url"]}
        have = ctx.conn.execute("SELECT text_read FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
        if have and have[0] and not ctx.refresh:
            ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
            continue
        body = None
        if it["text_url"]:
            if ctx.budget is not None and ctx.budget.exhausted():
                ctx.log(ctx.budget.disclose("bill texts", texts))
                break
            page = ctx.text(it["text_url"], "bill-{0}-{1}".format(session, it["number"]))
            body = bill_text(page) if page else None
            if page and not body:
                ctx.gap("{0}: bill text page {1} had no text".format(key, it["text_url"]))
        res = pc.classify(ctx.tax, wl, PROV, title=it["title"], texts=[body] if body else [], bill_key=key)
        ps.store_bill(ctx.conn, dict(record, text_read=1 if body else 0, areas=res.areas,
                                     matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
        texts += 1 if body else 0
    ctx.conn.commit()
    ctx.log("  mb bills {0}-{1}: {2} listed, {3} text(s) read".format(legislature, session, len(items), texts))
    return {"bills": len(items), "bill_texts": texts}


# -- the run ----------------------------------------------------------------

def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    """--session picks the session; --since/--until the window. The roster
    is read per division day from that day's Hansard (so --no-roster leaves
    every division without its names resolved: a gap, said out loud)."""
    legislature, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    ctx.mb_reviewed = pn.ReviewedDivisions.load(PROV)
    ctx.mb_not_served = pn.load_vp_not_served(PROV)
    stats = {}
    if bills:
        stats.update(fetch_bills(ctx, legislature, sess, wl))
    listing = ctx.text(VP_SESSIONS, "vp-sessions")
    vp_url = session_pages(listing, VP_SESSIONS, "vp").get((legislature, sess)) if listing else None
    if listing and not vp_url:
        ctx.gap("mb V&P: session {0} is not on {1}".format(session, VP_SESSIONS))
    page = ctx.text(vp_url, "vp-list-{0}".format(session)) if vp_url else None
    records = [r for r in list_records(page, vp_url) if r[0] is None or ctx.in_window(r[0])] if page else []
    # every day the session's calendar lists a record for, whatever the window
    ctx.mb_listed = {d: u for d, u in (list_records(page, vp_url) if page else []) if d}
    if page and not list_records(page, vp_url):
        ctx.gap("mb V&P {0}: no records parsed from {1}".format(session, vp_url))
    stats["records_listed"] = len(records)
    if ctx.dry_run:
        return stats
    hansard = None
    read = divs = gaps = 0
    for date, url in records:
        if not ctx.refresh and ps.sitting_done(ctx.conn, url):
            continue
        if ctx.stop():
            break
        if hansard is None and roster:
            hl = ctx.text(HANSARD_SESSIONS, "hansard-sessions")
            h_url = session_pages(hl, HANSARD_SESSIONS, "hansard").get((legislature, sess)) if hl else None
            if hl and not h_url:
                ctx.gap("mb Hansard: session {0} is not on {1}".format(session, HANSARD_SESSIONS))
            hp = ctx.text(h_url, "hansard-list-{0}".format(session)) if h_url else None
            hansard = list_hansard(hp, h_url) if hp else {}
        ctx.records_read += 1
        n, g = read_sitting(ctx, legislature, sess, date, url, hansard or {}, wl)
        read += 1
        divs += n
        gaps += g
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps})
    # One member, one key, in place, with nothing fetched: the seat rule
    # within a legislature, and the reviewed same_person entries across them.
    merged = ps.merge_split_members(ctx.conn, PROV, same_person=pn.load_same_person(PROV), log=ctx.log)
    if merged:
        stats["keys_merged"] = sum(len(m) for _k, m in merged)
    ctx.conn.commit()
    return stats
