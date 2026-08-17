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
  * Treaty bodies (CEDAW, CRC) -- NO. The sessions list renders its dates
    client-side; the served HTML carries none.
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
