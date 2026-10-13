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

  * UPR working group sessions -- YES, added 2026-08-17, from UPR Info
    rather than OHCHR. The OHCHR UPR pages are behind a Cloudflare bot
    challenge (cf-mitigated: challenge, "Just a moment..."), which is a
    thing to route around rather than defeat: the HRC branch of the same
    host is not challenged, so this is a policy on that path, not a block on
    us. UPR Info publishes the whole schedule to January 2031 in a session
    dropdown, at MONTH precision only.

  * Third Committee item-level meetings -- YES, added 2026-08-17, via the UN
    Journal's own JSON API. Found by reading the Journal web app: its runtime
    config at journal.un.org/assets/config.json names the API base, and the
    bundle names the endpoints. GlobalCalendar takes a POST of
    {locationValue, startDate, endDate, organs} with ISO DATETIMES -- plain
    dates return 400 "Incorrect parameters" -- and organ UUIDs come from
    AdvancedSearch/Organs (3,495 of them; Third Committee is
    38e3d777-d53c-e711-84fb-0050569f00b6).

    IMPORTANT LIMIT: it only serves dates already covered by a published
    Journal issue. October 2025 returns 36 Third Committee meetings with
    times; October 2026 returns 400 because that Journal does not exist yet.
    So this is a NEAR-TERM feed of days to a few weeks, not a months-ahead
    calendar, and it will fill in once the 81st session is under way.

  * General Assembly PLENARIES and high-level meetings -- YES, added
    13 October 2026, after the monitor missed the plenary vote on the
    political declaration on pandemic prevention, preparedness and response
    (12 October 2026, 18th plenary, draft A/81/L.6). The GA window above says
    only that the Assembly is sitting; the plenary is where it decides.
    GlobalCalendar asked for the General Assembly's own organ
    (9615d07d-d53c-e711-84fb-0050569f00b6) returns its plenaries, informal
    plenaries, high-level meetings and missions' informal consultations; the
    consultations are dropped (no agenda). A plenary's TITLE is only a number
    ("18th plenary meeting"), so each one's detail is read too: GET
    officials/<meeting id> (the app bundle's loadMeetingDetails) carries the
    agenda ("Global health and foreign policy - Item 129: Draft resolution
    (A/81/L.6) / Action on the draft resolution") and the programme notes
    ("Letters from the President of the General Assembly, dated 7 October
    2026 ..."). The draft symbols in the agenda are what tie a plenary to a
    draft on our ground (src/ingest/un_docs.py walks A/81/L.n).
    Horizon, measured 13 October 2026: GA rows were served to 3 November, so
    plenaries appear in the Journal about a week ahead; the same 400 marks a
    range past the last issue.

  * OHCHR NOW CHALLENGED, measured 13 October 2026: www.ohchr.org answers
    the HRC sessions page (and the calls-for-input listing) with HTTP 403,
    cf-mitigated: challenge, "Just a moment...", where on 17 August only the
    UPR paths were. Not bypassed: no browser User-Agent, no challenge
    solver, no third-party cache or proxy. The same 403 came back from the
    laptop and from the Mac Mini (a different network), so it is not one
    address being throttled.

    ALTERNATIVE ROUTES TRIED, 13 October 2026 (docs/un-sources.md keeps the
    table). The standing rule is to look for a legitimate other route before
    recording a gap:

    - HRC sessions: WORKS via the HRC's own portal. hrcmeetings.ohchr.org
      now answers 301 to hrcportal.ohchr.org (Drupal 11, the HRC extranet's
      public side). Its robots.txt allows everything but /admin, /search,
      /user and the core paths, with Crawl-delay 10 for "*" (one request per
      run here, so the delay is met by construction). /hrc-sessions-all
      lists every regular session from the 46th with "Date : 7 Sep - 7 Oct
      2026" and a /node/N link per session; parse_hrcportal_sessions reads
      it. It lists sessions once the Council has fixed them, so the 64th
      (February 2027) appears there when it is announced, not before. The
      www.ohchr.org page stays as a fallback only, should the portal fail.
    - OHCHR calls for input: NO legitimate route found. Tried:
      www.ohchr.org/en/rss.xml (200, not challenged, but it is the front-page
      node feed: ten topic pages, no calls); /en/calls-for-input,
      /en/calls-for-input-listing/rss.xml and /sitemap.xml (all challenged);
      hrcportal.ohchr.org (no calls listing, none in its 167-URL sitemap);
      spinternet.ohchr.org (Special Procedures; no calls listing);
      ReliefWeb's API (needs an approved appname, which only Chris can
      request, and it does not syndicate OHCHR calls in any case). Not used:
      the Wayback Machine or any other cache, which would be routing the
      challenged page through a third party. Whether GitHub's runners are
      challenged is answered by the backup workflow's own check log (a
      dispatched dry run prints it). Until then the check log says "could
      not read", never "0 open".
    - Treaty bodies: tbinternet.ohchr.org/robots.txt now reads
      "User-agent: * / Disallow: /" (seen 13 October 2026). The master
      calendar is therefore NOT fetched (the request goes through
      src/robots_guard, which refuses it) and the check log says why; it
      resumes by itself if the robots.txt relents.
      SESSIONS NOW COME FROM INDICO.UN (13 October 2026): UNOG's meeting
      registration system files every treaty body session under the
      committee's category, and its calendar export (events.ics) gives
      CEDAW, CRC and CCPR sessions about a year ahead, with the states under
      review where the description lists them. Sitting dates, not reporting
      deadlines: the deadlines exist only on tbinternet. The other routes
      tried (UN Journal Geneva, docs.un.org, the Digital Library, UN Geneva's
      pages) are listed above fetch_treaty_sessions.

Nothing on the original list is now missing. Recorded here rather than hidden,
so nobody mistakes near-term Journal coverage for a long-range schedule.
Announcements that come BEFORE the Journal lists a plenary are in the PGA's
letters (src/ingest/pga_letters.py).
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

from src.http import FetchError

HRC_SESSIONS = "https://www.ohchr.org/en/hr-bodies/hrc/regular-sessions"
# The HRC's own portal (hrcmeetings.ohchr.org redirects here). Not behind the
# Cloudflare challenge that www.ohchr.org put up by 13 October 2026; robots.txt
# allows it, Crawl-delay 10 (one request per run).
HRC_PORTAL = "https://hrcportal.ohchr.org"
HRC_PORTAL_SESSIONS = HRC_PORTAL + "/hrc-sessions-all"
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

UPR_SESSIONS = "https://www.upr-info.org/en/presessions"

# UN Journal API. Base from journal.un.org/assets/config.json; endpoints from
# the app bundle. See the module docstring for the POST contract.
JOURNAL_API = "https://journal-api.un.org/api/"
JOURNAL_ORGANS = JOURNAL_API + "AdvancedSearch/Organs"
JOURNAL_CALENDAR = JOURNAL_API + "GlobalCalendar"
JOURNAL_LOCATION = "New York"
# Third Committee (Social, Humanitarian & Cultural) -- the GA committee that
# takes the family, SRHR and religious-freedom resolutions.
THIRD_COMMITTEE = "38e3d777-d53c-e711-84fb-0050569f00b6"
# The General Assembly itself (AdvancedSearch/Organs, 13 October 2026). Asked
# for on its own, GlobalCalendar returns the plenaries, high-level meetings,
# informal plenaries and informal consultations held under the Assembly.
GENERAL_ASSEMBLY = "9615d07d-d53c-e711-84fb-0050569f00b6"
# One meeting's detail: the agenda (items, draft symbols, "Action on the
# draft resolution") and the programme notes (which PGA letters announced
# it). Path from the app bundle's loadMeetingDetails: base + category + id.
# GET, with the same location/language headers as GlobalCalendar.
JOURNAL_MEETING = JOURNAL_API + "officials/{0}"
JOURNAL_HEADERS = {"location": JOURNAL_LOCATION, "language": "en"}

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
    approximate: bool = False    # True when only the MONTH is published

    @property
    def name(self):
        return "{0}{1} session of the {2}".format(
            self.number, _ordinal_suffix(self.number), self.body)

    @property
    def when(self):
        """Human phrasing that does not imply precision we do not have."""
        if self.approximate:
            return self.starts.strftime("%B %Y")
        return "{0} to {1}".format(self.starts, self.ends)

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


def guarded(client, feed="uncal"):
    """`client` with every request asking robots.txt first (src/robots_guard).

    A client that is already a GuardedClient is returned as it is, so a
    caller (tools/un_forward.collect, a test) can pass its own. Nothing is
    exempt: tbinternet and Indico.UN are websites, not documented APIs.
    """
    from src.robots_guard import GuardedClient
    if isinstance(client, GuardedClient):
        return client
    return GuardedClient(client, feed)


def fetch_treaty_deadlines(client):
    """Not fetched while tbinternet's robots.txt disallows it (13 October 2026).

    The request goes through the robots guard: while robots.txt reads
    "Disallow: /" it raises RobotsRefused (a FetchError) whose reason says
    "robots.txt disallows ...; not fetched", and nothing is sent. It resumes
    by itself if the robots.txt relents.
    """
    return parse_treaty_deadlines(guarded(client).get_text(TB_CALENDAR, "uncal", "tb-calendar"))


# ---------------------------------------------------------------------------
# Treaty body SESSIONS from Indico.UN (13 October 2026).
#
# The route that replaced tbinternet's master calendar. UNOG runs Indico.UN,
# the registration system for meetings at the Palais des Nations; every
# treaty body session has an event there, filed under the committee's
# category in "OHCHR" (category 800). Indico's own calendar export,
# /category/<id>/events.ics, is plain iCalendar for calendar programs: one
# VEVENT per event with SUMMARY ("93rd session"), DTSTART/DTEND, URL, and for
# some sessions a DESCRIPTION naming the states under review. It runs about a
# year ahead (CEDAW's 94th, 3-26 February 2027, and 96th, 4-22 October 2027,
# were listed on 13 October 2026), which is further than tbinternet ever was.
#
# robots.txt: indico.un.org answers 404 for /robots.txt (no rules, RFC 9309
# 2.3.1.2); the requests still go through the robots guard, so a robots.txt
# that appears later is obeyed. One request per committee per run.
#
# What it gives is SITTING DATES, not the reporting deadlines the master
# calendar listed: the deadlines live only on tbinternet (robots.txt
# Disallow: /), so they are not read, and the check log says so.
#
# Noise handled here: the category export includes the sub-categories
# (pre-sessional working groups, optional-protocol working groups), whose
# events share the "Nth session" form and even the numbers ("96th session",
# 1-5 March 2027, is CEDAW's pre-sessional group). A committee's plenary
# session runs three to four weeks; every working group meeting seen ran a
# week or less. So a session is kept when it is not CANCELLED, its title is
# "Nth session" without a working-group word, and it spans at least
# TB_PLENARY_MIN_DAYS. Where two events still share a number, the longer wins.
#
# OTHER ROUTES TRIED for the calendar, 13 October 2026 (docs/un-sources.md):
#   - UN Journal API, location Geneva (journal-api.un.org, robots.txt 404):
#     WORKS but near-term only. GlobalCalendar with the treaty body organ
#     UUIDs (CEDAW c216d07d-..., CRC f2e3d777-..., CCPR 8d79c089-...) returns
#     every meeting with times, published to about three weeks ahead (CCPR's
#     146th to 30 October on 13 October); meeting details carry no agenda or
#     state names (closed meetings). Not wired: Indico gives the same sessions
#     a year ahead. Kept as the fallback to reach for if Indico goes.
#   - docs.un.org provisional agendas (CEDAW/C/94/1 ...): docs.un.org answers
#     302 to documents.un.org/api/symbol/access, and documents.un.org's
#     robots.txt disallows /api, /doc and /access (as do daccess-ods.un.org
#     and documents-dds-ny.un.org). Not used.
#   - UN Digital Library: /search and /rss disallowed by robots.txt; the
#     sitemap it names answers 202 with an empty body (the same block as its
#     search). Not used.
#   - www.ungeneva.org "Calendar of major meetings": robots.txt allows it,
#     but it is a hand-kept page, last updated 27 February 2026, that stops
#     in September and omits CEDAW's 93rd and CCPR's 146th. The biweekly
#     press calendar lists no treaty bodies. Not used.
#   - conf.unog.ch: robots.txt Disallow: / (bar its help and recordings).
# ---------------------------------------------------------------------------

INDICO = "https://indico.un.org"
TB_INDICO_ICS = INDICO + "/category/{0}/events.ics"
# Indico.UN categories under OHCHR (category 800), read 13 October 2026.
TB_INDICO_CATEGORIES = (
    ("CEDAW", 828, "Committee on the Elimination of Discrimination against Women"),
    ("CRC", 833, "Committee on the Rights of the Child"),
    ("CCPR", 821, "Human Rights Committee"),
)
TB_PLENARY_MIN_DAYS = 10
_ICS_EVENT = re.compile(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", re.S)
_ICS_FIELD = re.compile(r"^([A-Z][A-Z-]*)(?:;[^:\n]*)?:(.*)$", re.M)
_ICS_DATE = re.compile(r"^(\d{4})(\d{2})(\d{2})")
_TB_NUMBER = re.compile(r"\b(\d{1,3})(?:st|nd|rd|th)\s+session\b", re.I)
_TB_NOT_PLENARY = re.compile(r"cancel|working\s*group|\bWG\b|pre[- ]?sessional|"
                             r"dual chamber|annual session", re.I)
# "The Committee will consider the reports of the following States Parties:
# Austria Cameroon Jamaica Rwanda The List of issues ..."
_TB_STATES_START = re.compile(
    r"(?:reports? of the following States? Part(?:y|ies)|countries under review|"
    r"States? parties[’']? reports)\s*:?", re.I)
_TB_STATES_END = re.compile(r"(?:the\s+)?list of issues|LOIPR|once accredited|accreditation|"
                            r"for further|please|registration", re.I)


@dataclass
class TreatySession(Session):
    treaty: str = ""             # CEDAW | CRC | CCPR
    states: tuple = ()           # states whose reports it will consider, when listed

    @property
    def name(self):
        return "{0} {1}{2} session".format(self.treaty, self.number,
                                           _ordinal_suffix(self.number))

    @property
    def ours(self):
        return self.treaty.upper() in TB_OURS


def _ics_unescape(value):
    return (value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\"))


def _ics_events(text):
    """[{FIELD: value}] from an iCalendar text, folded lines joined."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]", "", text)
    out = []
    for block in _ICS_EVENT.findall(text):
        fields = {}
        for key, value in _ICS_FIELD.findall(block):
            fields.setdefault(key, _ics_unescape(value))
        out.append(fields)
    return out


def _ics_date(value):
    m = _ICS_DATE.match(value or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _states_under_review(description):
    """The states a session will review, when the Indico description lists them."""
    start = _TB_STATES_START.search(description or "")
    if not start:
        return ()
    rest = description[start.end():]
    end = _TB_STATES_END.search(rest)
    if end:
        rest = rest[:end.start()]
    states = []
    for part in re.split(r"[\n,]+|\band\b", rest):
        name = part.strip(" .:; \t").strip()
        if name and len(name) <= 60 and not re.search(r"\d|:", name) and name not in states:
            states.append(name)
    return tuple(states)


def parse_indico_sessions(text, treaty):
    """Plenary sessions of one committee from its Indico.UN category export.

    Past sessions are returned too (the export keeps events that ended in the
    last four weeks), so an empty result means the export changed, not that
    nothing is scheduled; callers filter with upcoming().
    """
    best = {}
    for ev in _ics_events(text):
        title = ev.get("SUMMARY", "").strip()
        if _TB_NOT_PLENARY.search(title):
            continue
        number = _TB_NUMBER.search(title)
        starts, ends = _ics_date(ev.get("DTSTART")), _ics_date(ev.get("DTEND"))
        if not number or not starts or not ends:
            continue
        span = (ends - starts).days + 1
        if span < TB_PLENARY_MIN_DAYS:
            continue
        n = int(number.group(1))
        url = (ev.get("URL") or "").strip() or INDICO
        session = TreatySession(body=treaty, number=n, starts=starts, ends=ends, url=url,
                                treaty=treaty,
                                states=_states_under_review(ev.get("DESCRIPTION", "")))
        held = best.get(n)
        if held is None or span > (held.ends - held.starts).days + 1:
            best[n] = session
    return sorted(best.values(), key=lambda s: s.starts)


def fetch_treaty_sessions(client, categories=TB_INDICO_CATEGORIES):
    """(sessions, failures): CEDAW, CRC and CCPR plenary sessions from Indico.UN.

    Every request asks robots.txt first (guarded). A committee whose export
    cannot be read, or parses to nothing, is named in `failures` and the
    others are still returned; when none can be read the first FetchError is
    raised, so the caller reports the source as not read.
    """
    gc = guarded(client)
    out, failures, first_error = [], [], None
    for treaty, category, _name in categories:
        url = TB_INDICO_ICS.format(category)
        try:
            got = parse_indico_sessions(
                gc.get_text(url, "uncal", "tb-indico-{0}".format(category)), treaty)
        except FetchError as exc:
            first_error = first_error or exc
            failures.append("{0}: {1}".format(treaty, getattr(exc, "cause", None) or exc))
            continue
        if not got:
            failures.append("{0}: Indico export parsed to nothing (layout change?)".format(treaty))
        out.extend(got)
    if not out and first_error is not None:
        raise FetchError(first_error.url, "uncal", "tb-indico", first_error.attempts,
                         "; ".join(failures))
    return sorted(out, key=lambda s: s.starts), failures


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


_UPR_OPTION = re.compile(
    r"Session\s+(\d{2})\s*-\s*(" + "|".join(MONTHS) + r")\s+(20\d\d)", re.I)


def parse_upr_sessions(html):
    """UPR working group sessions from UPR Info's session dropdown.

    MONTH precision only -- the dropdown says "Session 53 - November 2026"
    and no more. Sessions are dated to the first of the month and marked
    approximate, so nothing downstream can print a day the source never gave.
    """
    text = re.sub(r"\s+", " ", _TAGS.sub(" ", html or ""))
    out, seen = [], set()
    for number, month, year in _UPR_OPTION.findall(text):
        n = int(number)
        if n in seen:
            continue
        seen.add(n)
        try:
            first = _date(1, month.capitalize(), year)
        except ValueError:
            continue
        # End of month without calendar arithmetic imports.
        nxt = datetime.date(first.year + (first.month == 12),
                            1 if first.month == 12 else first.month + 1, 1)
        out.append(Session(body="UPR Working Group", number=n, starts=first,
                           ends=nxt - datetime.timedelta(days=1),
                           url=UPR_SESSIONS, approximate=True))
    return sorted(out, key=lambda s: s.starts)


def fetch_upr_sessions(client):
    return parse_upr_sessions(client.get_text(UPR_SESSIONS, "uncal", "upr-sessions"))


@dataclass
class Meeting:
    organ: str
    title: str
    starts: datetime.datetime
    kind: str                    # "Official" | "Informal"
    url: str = "https://journal.un.org/en/new-york/all"
    # Added 13 October 2026 for GA plenaries; empty for Third Committee rows.
    id: str = ""                 # the Journal's meeting UUID
    agenda: str = ""             # plain text of the meeting's agenda
    programme: str = ""          # programme notes ("Letters from the PGA ...")
    symbols: tuple = ()          # document symbols the agenda names

    @property
    def days_until(self):
        return (self.starts.date() - datetime.date.today()).days

    @property
    def match_text(self):
        """What the taxonomy reads: the title, then the agenda."""
        return " ".join(p for p in (self.title, self.agenda) if p)


def parse_journal_meetings(payload, organ_filter="Third"):
    """Meetings from a GlobalCalendar response.

    The payload nests group -> organGroup -> meetings, repeated per day, and
    a query filtered to one organ still returns its parent's plenaries, so
    rows have to be filtered rather than trusted.

    Match on relatedOrganizations as well as organ/primaryOrgan. This is not
    belt-and-braces: a committee's OFFICIAL meetings are filed under organ
    "General Assembly" with the committee only in relatedOrganizations, while
    the rows whose organ IS the committee are its informal notices. Checking
    organ alone kept 36 informal items and dropped all 55 official ones --
    precisely backwards, since the official meetings are the substantive
    ones (observed 2026-08-17).
    """
    out = []
    for group in payload or []:
        for og in group.get("organGroup", []) or []:
            for m in og.get("meetings", []) or []:
                organ = og.get("organ") or ""
                primary = m.get("primaryOrgan") or ""
                related = " ".join(
                    str(r.get("value")) for r in (m.get("relatedOrganizations") or []))
                if organ_filter and organ_filter not in (organ + primary + related):
                    continue
                raw = (m.get("startDate") or "")[:16]
                try:
                    starts = datetime.datetime.strptime(raw, "%Y-%m-%dT%H:%M")
                except ValueError:
                    continue
                title = re.sub(r"\s+", " ", _TAGS.sub(" ", m.get("title") or "")).strip()
                # Prefer the related organisation when it is the one asked
                # for: an official Third Committee meeting says organ
                # "General Assembly", which would be misleading to display.
                label = organ
                if organ_filter and organ_filter in related and organ_filter not in organ:
                    label = next((str(r.get("value")) for r in (m.get("relatedOrganizations") or [])
                                  if organ_filter in str(r.get("value"))), organ)
                out.append(Meeting(organ=label or primary, title=title,
                                   starts=starts, kind=m.get("type") or ""))
    return sorted(out, key=lambda x: x.starts)


def fetch_journal_meetings(client, organ=THIRD_COMMITTEE, start=None, days=21,
                           organ_filter="Third", parser=None, slug="journal"):
    """Near-term meetings for one organ, or ([], reason) beyond the horizon.

    A 400 means the range reaches past the last published Journal issue, not
    that the request was malformed -- so it is reported as a horizon limit
    rather than raised as an error.

    parser/slug (13 October 2026, additive): the GA plenary path passes
    parse_ga_plenaries and its own archive slug; the defaults are the Third
    Committee call, unchanged.
    """
    import json as _json
    start = start or datetime.date.today()
    end = start + datetime.timedelta(days=days)
    body = _json.dumps({"locationValue": JOURNAL_LOCATION,
                        "startDate": start.isoformat() + "T00:00:00",
                        "endDate": end.isoformat() + "T00:00:00",
                        "organs": [organ]})
    try:
        payload = client.post_json(JOURNAL_CALENDAR, body, "uncal",
                                   "{0}-{1}".format(slug, start.isoformat()),
                                   headers={"location": JOURNAL_LOCATION,
                                            "language": "en"})
    except Exception as exc:
        if "400" in str(exc):
            return [], ("Journal has no issue covering {0} to {1} yet "
                        "(near-term feed only)".format(start, end))
        raise
    if parser is not None:
        return parser(payload), None
    return parse_journal_meetings(payload, organ_filter), None


JOURNAL_MEETING_PAGE = "https://journal.un.org/en/new-york/meeting/officials/{0}/{1}"
# A document symbol as the Journal agenda writes it: A/81/L.6, A/81/387,
# A/C.3/81/L.12/Rev.1, A/81/297/Add.1.
_SYMBOL = re.compile(r"\bA/(?:C\.\d/)?\d{2}/(?:L\.\d+|\d+)(?:/(?:Rev|Add|Corr)\.\d+)*")
# Plenaries and high-level meetings. Informal consultations on a draft are
# convened by a mission, carry no agenda in the Journal, and are left out
# (the drafts themselves are read by symbol, src/ingest/un_docs.py).
_PLENARY = re.compile(r"\bplenary\b|\bhigh[- ]level\b", re.I)
_CONSULTATIONS = re.compile(r"^\s*informal consultations\b", re.I)


def _plain(html_text):
    """Tags off, entities decoded, whitespace collapsed."""
    import html as _html
    text = re.sub(r"</p>|<br\s*/?>", " ; ", html_text or "")
    text = _html.unescape(_TAGS.sub(" ", text))
    text = re.sub(r"\s+", " ", text).strip(" ;")
    return re.sub(r"(?:\s*;\s*)+", " ; ", text)


def parse_ga_plenaries(payload):
    """General Assembly plenaries and high-level meetings from GlobalCalendar.

    A query for the Assembly's own organ also returns informal consultations
    on drafts (convened by a mission, no agenda); those are dropped. What
    stays is every official plenary ("18th plenary meeting"), every informal
    plenary and every high-level meeting, with the meeting id kept so its
    agenda can be read (fetch_meeting_detail): the title alone is only a
    number, and the agenda is where "Global health and foreign policy - Item
    129: Draft resolution (A/81/L.6)" is said.
    """
    out, seen = [], set()
    for group in payload or []:
        for og in group.get("organGroup", []) or []:
            for m in og.get("meetings", []) or []:
                organ = og.get("organ") or m.get("organ") or ""
                primary = m.get("primaryOrgan") or ""
                if "General Assembly" not in (organ + " " + primary):
                    continue
                title = _plain(m.get("title"))
                if not _PLENARY.search(title) or _CONSULTATIONS.match(title):
                    continue
                if m.get("isCancelled"):
                    continue
                raw = (m.get("startDate") or "")[:16]
                try:
                    starts = datetime.datetime.strptime(raw, "%Y-%m-%dT%H:%M")
                except ValueError:
                    continue
                key = (m.get("id") or title, raw)
                if key in seen:     # the payload repeats rows per day group
                    continue
                seen.add(key)
                mid = m.get("id") or ""
                url = (JOURNAL_MEETING_PAGE.format(mid, starts.date().isoformat())
                       if mid else Meeting.url)
                out.append(Meeting(organ="General Assembly", title=title,
                                   starts=starts, kind=m.get("type") or "",
                                   url=url, id=mid))
    return sorted(out, key=lambda x: x.starts)


def parse_meeting_detail(payload):
    """(agenda, programme, symbols) from one Journal meeting record."""
    def en(field):
        value = (payload or {}).get(field) or {}
        return value.get("en") if isinstance(value, dict) else str(value)
    agenda = _plain(en("agenda"))
    programme = _plain(en("programme"))
    symbols = []
    for s in _SYMBOL.findall(agenda + " " + programme):
        if s not in symbols:
            symbols.append(s)
    return agenda, programme, tuple(symbols)


def fetch_meeting_detail(client, meeting_id):
    import json as _json
    text = client.get_text(JOURNAL_MEETING.format(meeting_id), "uncal",
                           "journal-meeting-{0}".format(meeting_id),
                           headers=JOURNAL_HEADERS)
    return parse_meeting_detail(_json.loads(text))


def fetch_ga_plenaries(client, start=None, days=21):
    """GA plenaries in the window, each with its agenda read.

    Returns (meetings, why, failures): `why` is the horizon note when the
    Journal has no issue covering the range (the same 400 as
    fetch_journal_meetings), else None. A meeting whose detail will not load
    is kept with an empty agenda and named in `failures`, so a missing agenda
    is a gap, not a quiet row.
    """
    meetings, why = fetch_journal_meetings(client, organ=GENERAL_ASSEMBLY,
                                           start=start, days=days,
                                           organ_filter=None, parser=parse_ga_plenaries,
                                           slug="journal-ga")
    failures = []
    for m in meetings:
        if not m.id:
            continue
        try:
            m.agenda, m.programme, m.symbols = fetch_meeting_detail(client, m.id)
        except Exception as exc:
            failures.append("{0} {1}: agenda not read ({2})".format(
                m.starts.date(), m.title, str(exc)[:80]))
    return meetings, why, failures


def fetch_sessions(client):
    return fetch_sessions_routed(client)[0]


def fetch_sessions_routed(client):
    """(sessions, route) with route naming the host that answered.

    hrcportal.ohchr.org first (not challenged), www.ohchr.org only when the
    portal fails or parses to nothing. Raises FetchError naming both when
    neither can be read.
    """
    why = []
    try:
        got = parse_hrcportal_sessions(
            client.get_text(HRC_PORTAL_SESSIONS, "uncal", "hrcportal-sessions"))
        if got:
            return got, "hrcportal.ohchr.org"
        why.append("hrcportal.ohchr.org parsed to nothing (layout change?)")
    except FetchError as exc:
        why.append("hrcportal.ohchr.org: {0}".format(getattr(exc, "cause", None) or exc))
    try:
        got = parse_hrc_sessions(client.get_text(HRC_SESSIONS, "uncal", "hrc-sessions"))
        if got:
            return got, "www.ohchr.org"
        why.append("www.ohchr.org parsed to nothing")
    except FetchError as exc:
        why.append("www.ohchr.org: {0}".format(getattr(exc, "cause", None) or exc))
    raise FetchError(HRC_PORTAL_SESSIONS, "uncal", "hrcportal-sessions", 1, "; ".join(why))


# One session on hrcportal.ohchr.org/hrc-sessions-all (13 October 2026):
#   <article class="node node--session ..."> <h2><a href="/node/18091">63rd
#   regular session of the Human Rights Council</a></h2> ... Location: Geneva
#   ... <div class="field_session_dates"><svg .../> Date : 7 Sep – 7 Oct 2026
# The start's year is printed only when it differs from the end's.
_PORTAL_ARTICLE = re.compile(r'<article[^>]*node--session[^>]*>(.*?)</article>', re.S)
_PORTAL_TITLE = re.compile(
    r'<h2>\s*<a href="([^"]+)">\s*(\d{1,3})(?:st|nd|rd|th)\s+regular session of the '
    r'Human Rights Council\s*</a>', re.I)
_PORTAL_DATES = re.compile(
    r"Date\s*:\s*(\d{1,2})\s+([A-Za-z]{3,9})\.?(?:\s+(20\d\d))?\s*[\u2013\u2014-]\s*"
    r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(20\d\d)")
_SVG = re.compile(r"<svg.*?</svg>", re.S)


def _month(name):
    key = name[:3].capitalize()
    return [m[:3] for m in MONTHS].index(key) + 1


def parse_hrcportal_sessions(html):
    """HRC regular sessions on hrcportal.ohchr.org, earliest first.

    Organisational meetings and special sessions are skipped (only "regular
    session" titles match). Past sessions are returned, as parse_hrc_sessions
    does, so an empty result means the page changed, not "nothing ahead".
    """
    out, seen = [], set()
    for block in _PORTAL_ARTICLE.findall(html or ""):
        title = _PORTAL_TITLE.search(block)
        if not title:
            continue
        text = re.sub(r"\s+", " ", _TAGS.sub(" ", _SVG.sub("", block)))
        dates = _PORTAL_DATES.search(text)
        if not dates:
            continue
        number = int(title.group(2))
        if number in seen:
            continue
        try:
            end_year = int(dates.group(6))
            ends = datetime.date(end_year, _month(dates.group(5)), int(dates.group(4)))
            start_month = _month(dates.group(2))
            start_year = int(dates.group(3)) if dates.group(3) else (
                end_year if start_month <= ends.month else end_year - 1)
            starts = datetime.date(start_year, start_month, int(dates.group(1)))
        except ValueError:
            continue
        seen.add(number)
        href = title.group(1)
        out.append(Session(body="Human Rights Council", number=number, starts=starts,
                           ends=ends, url=href if href.startswith("http") else HRC_PORTAL + href))
    return sorted(out, key=lambda s: s.starts)


def robots_allows(client, url, agent="CitizenGO-ParlMonitor"):
    """True when the host's robots.txt lets `agent` fetch `url`.

    Added 13 October 2026 when tbinternet.ohchr.org's robots.txt turned out to
    read "Disallow: /". A robots.txt that answers 404 allows everything (the
    standard's rule); any other failure to read it raises, so the caller
    reports the source as not read rather than guessing.
    """
    import urllib.parse
    import urllib.robotparser
    parts = urllib.parse.urlsplit(url)
    robots = "{0}://{1}/robots.txt".format(parts.scheme, parts.netloc)
    try:
        text = client.get_text(robots, "robots", parts.netloc.replace(".", "-"), archive=False)
    except FetchError as exc:
        if "404" in str(getattr(exc, "cause", "") or exc):
            return True
        raise
    parser = urllib.robotparser.RobotFileParser()
    parser.parse((text or "").splitlines())
    return parser.can_fetch(agent, url)


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
