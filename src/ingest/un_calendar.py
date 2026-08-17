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
  * Commission on the Status of Women -- NO. The UN Women page carries only
    one dated reference and it is in the past.
  * Third Committee -- NO. The UNGA page carries no dates at all.

That is four of five bodies missing, and the gaps are recorded here rather
than hidden so nobody mistakes an HRC-only calendar for the UN's calendar.
Each needs its own solution and none of them is a scrape of a listing page.
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
