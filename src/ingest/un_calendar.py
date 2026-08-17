"""What the UN is about to do: the forward calendar.

The UPR tracker records positions already taken and trails the live calendar
by nine months. Calls for input are doors already open. This is the third
thing a monitor needs: when the bodies that decide are next sitting, so a
campaign can be planned against a date rather than reacting to a communique.

WHAT IS AND IS NOT HERE, measured 2026-08-17. Only the Human Rights Council
is covered, because it is the only body whose calendar could be read:

  * HRC regular sessions -- YES. ohchr.org/en/hr-bodies/hrc/regular-sessions
    lists every session with its date range in a stable, parseable form.
  * UPR working group sessions -- NO. Every OHCHR UPR calendar URL tried
    returns HTTP 403 to a non-browser client.
  * Treaty bodies (CEDAW, CRC, CRPD...) -- YES, via the master calendar,
    added 2026-08-17. An earlier note here said the dates rendered
    client-side; that was wrong. SessionsList.aspx is a Telerik postback grid
    that stays empty without a treaty selected, but MasterCalendar.aspx
    serves 50 dated rows in plain HTML. What it lists is REPORTING
    DEADLINES -- when each state's report or list of issues is due to each
    committee -- which is more actionable than sitting dates: a deadline is
    when a shadow submission can land.
  * Commission on the Status of Women -- YES, added 2026-08-17. The landing
    page carries almost no dates, which is why it was first written off, but
    it LINKS to per-session pages (cswNN-YYYY) and those carry the range:
    CSW71 is 8-19 March 2027.
  * UN General Assembly, as the Third Committee's anchor -- PARTLY. The GA
    session page gives the session window (the 81st opens 8 September 2026,
    closes 7 September 2027). The Third Committee's own schedule is not
    published as data anywhere found: it exists as a programme-of-work
    document (A/C.3/NN/L.1), and undocs.org serves only a redirect shell for
    it. So the calendar can say when the GA is sitting, not when the Third
    Committee takes a given item.

Still missing: UPR working group sessions (every OHCHR UPR URL returns 403
to a non-browser client) and the Third Committee's item-level schedule.
Recorded here rather than hidden, so nobody mistakes this for the whole UN.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

HRC_SESSIONS = "https://www.ohchr.org/en/hr-bodies/hrc/regular-sessions"
TB_CALENDAR = ("https://tbinternet.ohchr.org/_layouts/15/TreatyBodyExternal/"
               "MasterCalendar.aspx?Lang=en")

# The committees whose work touches our areas. CEDAW and CRC are where
# abortion and sexuality education get read into treaties; CCPR is where
# conscience, religion and (via General Comment 36) abortion sit.
# CRPD was included at first and REMOVED after looking at the output: the
# disability-selective abortion angle is real but rare, while the committee's
# calendar is dominated by general disability reporting, and it supplied most
# of the "ours" rows in the first run. Same judgement as dropping "migrant
# workers" from the UN taxonomy -- a flag that fires on everything is not a
# flag. CAT, CED, CERD, CMW and CESCR are listed but never flagged.
TB_OURS = ("CEDAW", "CRC", "CCPR")

CSW_INDEX = ("https://www.unwomen.org/en/how-we-work/"
             "commission-on-the-status-of-women")
GA_SESSION_URL = "https://www.un.org/en/ga/{0}/"
# GA sessions are numbered from 1946, so the session opening in September of
# year Y is Y - 1945. Derived rather than hardcoded so this does not quietly
# rot in September.
GA_EPOCH = 1945

MONTHS = ("January February March April May June July August September "
          "October November December").split()

# "63rd session of the Human Rights Council 07 September 2026 to 09 October 2026"
_SESSION = re.compile(
    r"(\d{1,3})(?:st|nd|rd|th)\s+session of the Human Rights Council\s+"
    r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d\d)\s+to\s+"
    r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d\d)", re.I)
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class Session:
    body: str                    # "Human Rights Council"
    number: int
    starts: datetime.date
    ends: datetime.date
    url: str

    @property
    def name(self):
        return "{0}{1} session of the {2}".format(
            self.number, _ordinal_suffix(self.number), self.body)

    @property
    def days_until(self):
        return (self.starts - datetime.date.today()).days

    @property
    def sitting_now(self):
        today = datetime.date.today()
        return self.starts <= today <= self.ends


def _ordinal_suffix(n):
    """61st, 62nd, 63rd, 64th -- and 11th/12th/13th, which are the exceptions."""
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _date(day, month, year):
    return datetime.date(int(year), MONTHS.index(month.capitalize()) + 1, int(day))


def parse_hrc_sessions(html):
    """HRC regular sessions on the page, earliest first.

    Matches sessions written as "Nth session of the Human Rights Council
    <date> to <date>", which covers 33 of the 63 listed: the earliest ones
    (2006-2008) are written differently and are not parsed. That costs
    nothing for a forward calendar and is recorded rather than papered over.

    Past sessions ARE parsed and returned; callers filter. That is deliberate
    -- it is how "no future sessions announced yet" can be told apart from
    "the page changed and nothing parsed", which look identical if only
    future ones are ever kept.
    """
    text = re.sub(r"\s+", " ", _TAGS.sub(" ", html or ""))
    out, seen = [], set()
    for m in _SESSION.finditer(text):
        number = int(m.group(1))
        if number in seen:
            continue
        seen.add(number)
        try:
            starts = _date(m.group(2), m.group(3), m.group(4))
            ends = _date(m.group(5), m.group(6), m.group(7))
        except ValueError:
            continue
        out.append(Session(body="Human Rights Council", number=number,
                           starts=starts, ends=ends,
                           url=HRC_SESSIONS))
    return sorted(out, key=lambda s: s.starts)


@dataclass
class TreatyDeadline:
    country: str
    region: str
    treaty: str                  # CEDAW | CRC | CRPD | CCPR | ...
    document: str                # "State party's report", "List of issues"
    due: datetime.date
    url: str = TB_CALENDAR

    @property
    def days_until(self):
        return (self.due - datetime.date.today()).days

    @property
    def ours(self):
        return self.treaty.upper() in TB_OURS


_TB_DATE = re.compile(r"^(\d{1,2})\s+(\w{3})\s+(20\d\d)$")
_MONTH3 = [m[:3] for m in MONTHS]


def parse_treaty_deadlines(html):
    """Reporting deadlines from the treaty body master calendar.

    One row per country/treaty/document, with the date the report or list of
    issues is due. Rows without a parseable date are skipped -- as with calls
    for input, an undated row would sit in a deadline feed forever.
    """
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html or "", re.S)
    out = []
    for row in rows:
        cells = [re.sub(r"\s+", " ", _TAGS.sub("", c)).replace("\xa0", " ").strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) < 5:
            continue
        due = None
        for cell in cells:
            m = _TB_DATE.match(cell)
            if m and m.group(2).capitalize() in _MONTH3:
                due = datetime.date(int(m.group(3)),
                                    _MONTH3.index(m.group(2).capitalize()) + 1,
                                    int(m.group(1)))
                break
        if not due or not cells[1] or cells[1] == "&nbsp;":
            continue
        out.append(TreatyDeadline(region=cells[0], country=cells[1],
                                  treaty=cells[2], document=cells[3], due=due))
    return sorted(out, key=lambda d: d.due)


def fetch_treaty_deadlines(client):
    return parse_treaty_deadlines(client.get_text(TB_CALENDAR, "uncal", "tb-calendar"))


# UN Women writes it in prose: "from 8 to 19 March 2027". Hyphen and en-dash
# forms are accepted too, but "to" is the one actually used -- the first
# version matched only dashes and silently found nothing.
_RANGE = re.compile(
    r"(\d{1,2})\s*(?:to|[-\u2013])\s*(\d{1,2})\s+("
    + "|".join(MONTHS) + r")\s+(20\d\d)", re.I)
_CSW_LINK = re.compile(r'href="([^"]*csw(\d{2})-(20\d\d)[^"]*)"', re.I)


def parse_csw_range(html, number):
    """The sitting dates for one CSW session page, or None.

    The page is a long article; the first day-range with a month and year is
    the session itself. Returns None rather than guessing when no range is
    found -- a session with invented dates is worse than an absent one.
    """
    text = re.sub(r"\s+", " ", _TAGS.sub(" ", html or ""))
    m = _RANGE.search(text)
    if not m:
        return None
    first, last, month, year = m.groups()
    try:
        starts = _date(first, month, year)
        ends = _date(last, month, year)
    except ValueError:
        return None
    if ends < starts:
        return None
    return Session(body="Commission on the Status of Women", number=number,
                   starts=starts, ends=ends, url=CSW_INDEX)


def fetch_csw_sessions(client, today=None):
    """CSW sessions from the index page's per-session links.

    The landing page carries almost no dates itself, which is why it was
    first written off; the session pages it links to carry the range.
    Only sessions in the current year or later are fetched, so this costs
    one or two extra requests rather than one per session ever held.
    """
    today = today or datetime.date.today()
    index = client.get_text(CSW_INDEX, "uncal", "csw-index")
    wanted = {}
    for href, number, year in _CSW_LINK.findall(index):
        if int(year) >= today.year:
            url = href if href.startswith("http") else "https://www.unwomen.org" + href
            wanted.setdefault(int(number), url)
    out, failures = [], []
    for number, url in sorted(wanted.items()):
        try:
            page = client.get_text(url, "uncal", "csw-{0}".format(number))
        except Exception as exc:
            # Not a silent skip: a session page that will not load is a gap
            # in the calendar, and the caller decides what to do about it.
            failures.append("CSW{0}: {1}".format(number, str(exc)[:80]))
            continue
        session = parse_csw_range(page, number)
        if session:
            out.append(session)
        else:
            failures.append("CSW{0}: page loaded but no date range found".format(number))
    return sorted(out, key=lambda s: s.starts), failures


def parse_ga_session(html, number):
    """The General Assembly session window: "will open on X and close on Y".

    This is the Third Committee's anchor, not its schedule. The committee's
    own programme of work is a document (A/C.3/NN/L.1) that is not served as
    data, so the calendar can say the GA is sitting and no more.
    """
    text = re.sub(r"\s+", " ", _TAGS.sub(" ", html or ""))
    m = re.search(r"will open on (\d{1,2}\s+\w+\s+20\d\d) and close on "
                  r"(\d{1,2}\s+\w+\s+20\d\d)", text, re.I)
    if not m:
        return None
    def parse(value):
        day, month, year = value.split()
        return _date(day, month, year)
    try:
        return Session(body="General Assembly", number=number,
                       starts=parse(m.group(1)), ends=parse(m.group(2)),
                       url=GA_SESSION_URL.format(number))
    except ValueError:
        return None


def fetch_ga_session(client, today=None):
    today = today or datetime.date.today()
    number = today.year - GA_EPOCH
    html = client.get_text(GA_SESSION_URL.format(number), "uncal",
                           "ga-{0}".format(number))
    return parse_ga_session(html, number)


def fetch_sessions(client):
    return parse_hrc_sessions(client.get_text(HRC_SESSIONS, "uncal", "hrc-sessions"))


def upcoming(sessions, today=None, horizon_days=None):
    """Sessions not yet finished, optionally starting within a horizon.

    A session already under way counts as upcoming: it is the most actionable
    thing on the calendar, not the least.
    """
    today = today or datetime.date.today()
    live = [s for s in sessions if s.ends >= today]
    if horizon_days is not None:
        cutoff = today + datetime.timedelta(days=horizon_days)
        live = [s for s in live if s.starts <= cutoff]
    return live
