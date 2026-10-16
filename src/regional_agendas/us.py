"""United States: the fifty state legislatures' forward business
(src/regional_agenda.py; 16 October 2026). docs/us-states-scope.md,
"Forward agenda (regional_agenda, 16 October 2026)", has the routes.

ROUTES
  * OPEN STATES /events (v3.openstates.org, a documented API; the team's free
    key, the one tools/us_states.py uses: openstates_api_key in
    config/secrets.yaml or OPENSTATES_API_KEY, sent only as the X-API-KEY
    header). Committee hearings and floor sessions with their agenda items
    and the bills each item takes, as the states' own schedule pages give
    them to Open States' scrapers. One request per state (jurisdiction is
    required: "must provide 'jurisdiction' parameter") and per page of 20
    ("invalid per_page, must be in [1, 20]").
  * WASHINGTON: the Legislature's documented web services,
    wslwebservices.leg.wa.gov CommitteeMeetingService (GetCommitteeMeetings
    for the window, GetCommitteeMeetingItems per meeting), keyless XML.
  * TEXAS: Texas Legislature Online's upcoming-meetings RSS (House, Senate,
    Joint), capitol.texas.gov/MyTLO/RSS/ (allowed). The hearing notices
    themselves sit under /tlodocs/ (robots.txt: Disallow: /TLODOCS/), so they
    are not read: each meeting is a booked slot ("to be announced") linked to
    its notice.

THE FREE KEY'S DAY IS SHARED with the weekly bills step (tools/us_states.py:
at most 150 a run, 225 a UTC day of the tier's 250). This module spends at
most OS_CALLS a run (30), 6.5 s apart (the tier's 10 a minute), and when the
collector hands it the store (`ctx.conn`) it
writes every request to the same ledger (uss_api_ledger) BEFORE sending it
and never takes the day past DAILY_CAP. A 429 ends Open States for the run.

WHICH STATES A RUN ASKS. Fifty states at one request each would be 50 of the
day's 250 and five and a half minutes of spacing, so each run asks the
PRIORITY states (the big legislatures and our ground) and a weekly rotating
slice of the rest; a state not asked this run keeps its stored rows and says
so. Washington and Texas are read directly and never cost a keyed request.
"""

from __future__ import annotations

import datetime
import html as _html
import json
import re
import time
import weakref
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from src import regional_agenda as ra
from src.http import FetchError
from src.us_states_store import STATES

CC = "us"
TAXONOMIES = (("taxonomy.yaml", "us"),)
THROTTLES = {"wslwebservices.leg.wa.gov": 1.5, "capitol.texas.gov": 1.5}

API = "https://v3.openstates.org/events"
OS_CALLS = 30                   # keyed requests a run, of the day's 250
DAILY_CAP = 225                 # tools/us_states.DAILY_CAP: the whole day, every runner
API_SPACING_S = 6.5             # the default tier's 10 a minute
PER_PAGE = 20                   # the API's cap
MAX_PAGES = 3                   # a state with more than 60 events in the window
RESERVE = 6                     # calls kept back in the plan for second pages

# Always asked, in this order (the collector reads REGIONS in insertion
# order, so these come first): the big legislatures and our ground.
PRIORITY = ("ca", "fl", "ny", "pa", "il", "oh", "ga", "nc", "mi", "nj")
DIRECT = ("wa", "tx")

WA_API = "https://wslwebservices.leg.wa.gov/CommitteeMeetingService.asmx/"
WA_NS = "{http://WSLWebServices.leg.wa.gov/}"
WA_PAGE = "https://app.leg.wa.gov/committeeschedules/Home/Agenda/{0}"
TX_RSS = "https://capitol.texas.gov/MyTLO/RSS/RSS.aspx?Type=upcomingmeetings{0}"
TX_FEEDS = (("house", "House"), ("senate", "Senate"), ("joint", "Joint"))

# Each state's capital's time zone: Open States gives a timed event in UTC.
TZ = {
    "al": "America/Chicago", "ak": "America/Anchorage", "az": "America/Phoenix",
    "ar": "America/Chicago", "ca": "America/Los_Angeles", "co": "America/Denver",
    "ct": "America/New_York", "de": "America/New_York", "fl": "America/New_York",
    "ga": "America/New_York", "hi": "Pacific/Honolulu", "id": "America/Boise",
    "il": "America/Chicago", "in": "America/Indiana/Indianapolis", "ia": "America/Chicago",
    "ks": "America/Chicago", "ky": "America/New_York", "la": "America/Chicago",
    "me": "America/New_York", "md": "America/New_York", "ma": "America/New_York",
    "mi": "America/Detroit", "mn": "America/Chicago", "ms": "America/Chicago",
    "mo": "America/Chicago", "mt": "America/Denver", "ne": "America/Chicago",
    "nv": "America/Los_Angeles", "nh": "America/New_York", "nj": "America/New_York",
    "nm": "America/Denver", "ny": "America/New_York", "nc": "America/New_York",
    "nd": "America/Chicago", "oh": "America/New_York", "ok": "America/Chicago",
    "or": "America/Los_Angeles", "pa": "America/New_York", "ri": "America/New_York",
    "sc": "America/New_York", "sd": "America/Chicago", "tn": "America/Chicago",
    "tx": "America/Chicago", "ut": "America/Denver", "vt": "America/New_York",
    "va": "America/New_York", "wa": "America/Los_Angeles", "wv": "America/New_York",
    "wi": "America/Chicago", "wy": "America/Denver",
}


# --- the key, the budget and the ledger -----------------------------------------

def openstates_key():
    """The same key and mechanism as tools/us_states.openstates_key()."""
    from src import publish
    return publish.load_secrets().get("openstates_api_key") or None


class Budget:
    """One run's keyed requests: the plan, the count, the spacing and (when
    the collector passes the store) the day's ledger."""

    def __init__(self, ctx, key, calls=None, sleep=None, clock=None):
        self.ctx, self.key = ctx, key
        self.calls = OS_CALLS if calls is None else calls
        self.sleep = sleep or time.sleep
        self.clock = clock or time.monotonic
        self.used = 0
        self.refused = None
        self.missing_told = None
        self._last = None
        self.conn = getattr(ctx, "conn", None)
        self.plan = plan_states(ctx.today_date, calls)

    def _ledger_ok(self):
        if self.conn is None:
            return True
        try:
            row = self.conn.execute("SELECT requests FROM uss_api_ledger WHERE day=?",
                                    (utc_day(),)).fetchone()
        except Exception:                                   # noqa: BLE001 - no table yet
            return True
        return (row[0] if row else 0) < DAILY_CAP

    def _ledger_add(self):
        if self.conn is None:
            return
        try:
            self.conn.execute(
                "INSERT INTO uss_api_ledger (day, requests, last_at) VALUES (?,?,?) "
                "ON CONFLICT(day) DO UPDATE SET requests=requests+excluded.requests, "
                "last_at=excluded.last_at",
                (utc_day(), 1, datetime.datetime.now(datetime.timezone.utc).isoformat(
                    timespec="seconds")))
            self.conn.commit()
        except Exception:                                   # noqa: BLE001 - no table: local cap only
            pass

    def left(self):
        if self.refused:
            return 0
        return max(0, self.calls - self.used) if self._ledger_ok() else 0

    def spend(self):
        if self._last is not None:
            gap = API_SPACING_S - (self.clock() - self._last)
            if gap > 0:
                self.sleep(gap)
        self._last = self.clock()
        self.used += 1
        self._ledger_add()


_RUNS = weakref.WeakKeyDictionary()     # ctx -> Budget: one per collector run


def budget_for(ctx):
    b = _RUNS.get(ctx)
    if b is None:
        b = Budget(ctx, openstates_key())
        _RUNS[ctx] = b
    return b


def utc_day():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def rotating_states():
    return [s for s in STATES if s not in PRIORITY and s not in DIRECT]


def plan_states(today, calls=None):
    """The states this run asks Open States for: every PRIORITY state and a
    slice of the rest that turns with the week, sized to the call budget
    (one call each, RESERVE kept for second pages)."""
    calls = OS_CALLS if calls is None else calls
    rot = rotating_states()
    n = max(0, min(len(rot), calls - len(PRIORITY) - RESERVE))
    if not n:
        return set(PRIORITY)
    week = today.toordinal() // 7
    start = (week * n) % len(rot)
    picked = [rot[(start + i) % len(rot)] for i in range(n)]
    return set(PRIORITY) | set(picked)


# --- Open States /events ------------------------------------------------------

_JUNK = re.compile(r"\s*-\s*opens in a new tab\.?", re.I)
_PLACEHOLDER = re.compile(
    r"^(?:committee agenda\b|voting meeting on and any other business|"
    r"any other business that may come before|to be announced|agenda to be announced|"
    r"bills under consideration$|(?:meeting|hearing|tbd|tba|agenda)$)", re.I)
# A description that only says a meeting takes the bills listed under it.
_GENERIC = re.compile(
    r"^(?:meeting of\b|voting meeting\b|committee agenda\b|bills? under consideration|"
    r"\(?to consider\b|executive session\b|committee meeting\b)", re.I)
_FLOOR = re.compile(r"\b(?:floor session|session day|in session|convenes?|"
                    r"organi[sz]ational session|veto session|floor)\b", re.I)
_COMMITTEE = re.compile(r"\b(?:committee|commission|council|task force|subcommittee|caucus|"
                        r"working group|work group|board|panel|conference|study|briefing|"
                        r"orientation|hearing)\b", re.I)
_NAME_PREFIX = re.compile(
    r"^(?:meeting on [A-Za-z]+ \d{1,2}, \d{4} of (?:the )?|meeting of (?:the )?)", re.I)
_GENERIC_NAME = re.compile(r"^(?:joint hearing|hearing|meeting|committee meeting|event)$", re.I)
_LEAD_TIME = re.compile(
    r"^\d{1,2}(?::\d{2})?\s*(?:[ap]\.?\s?m\.?)?\s*(?:[-\u2013\u2014]\s*\d{1,2}(?::\d{2})?"
    r"\s*(?:[ap]\.?\s?m\.?)?)?\s+(?=[A-Z])", re.I)


def tidy(text):
    t = _JUNK.sub(" ", _html.unescape(str(text or "")))
    return ra.one_line(t).strip(" .;,") if t else ""


def local_when(start, state):
    """(ISO date, 'HH:MM' or None) in the state's own time for an Open
    States start_date ('2026-10-19' or '2026-10-19T14:00:00+00:00')."""
    s = (start or "").strip()
    if len(s) <= 10:
        return s[:10] or None, None
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s[:10], None
    if dt.tzinfo is not None:
        try:
            from zoneinfo import ZoneInfo
            dt = dt.astimezone(ZoneInfo(TZ.get(state, "America/New_York")))
        except Exception:                                   # noqa: BLE001 - keep UTC
            pass
    return dt.date().isoformat(), dt.strftime("%H:%M")


def _org_name(ent):
    name = tidy(ent.get("name"))
    org = ent.get("organization") or {}
    if (not name or len(name) < 4) and org.get("name"):
        name = tidy(org["name"])
    return name


def _dedupe_words(text):
    """'Senate Senate Study Committee' -> 'Senate Study Committee'."""
    return re.sub(r"^(\w+) \1\b", r"\1", text)


def event_body(ev):
    """The meeting's body: the event's own name (it carries the
    subcommittee or working group) unless it is generic or is the
    committee's name without its chamber ('Judiciary' for 'House
    Judiciary'), when the committee participant's name is used."""
    orgs = [e for e in (ev.get("participants") or []) if e.get("entity_type") == "organization"]
    for a in ev.get("agenda") or []:
        orgs += [e for e in (a.get("related_entities") or [])
                 if e.get("entity_type") == "organization"]
    org_name = ""
    for e in orgs:
        name = _org_name(e)
        if name and name.lower() not in ("house", "senate", "assembly", "joint"):
            org_name = name
            break
    name = _NAME_PREFIX.sub("", tidy(ev.get("name")))
    if not name or _GENERIC_NAME.match(name):
        name = org_name
    elif org_name and org_name.lower().endswith(name.lower()) and len(org_name) > len(name):
        name = org_name
    return _dedupe_words(name or org_name or "Committee")


def is_floor(ev, body):
    return bool(_FLOOR.search(tidy(ev.get("name")))) and not _COMMITTEE.search(body)


def _bills(agenda_item):
    out = []
    for e in agenda_item.get("related_entities") or []:
        if e.get("entity_type") != "bill":
            continue
        b = e.get("bill") or {}
        ident = tidy(b.get("identifier") or e.get("name"))
        if ident and ident not in [x[0] for x in out]:
            out.append((ident, tidy(b.get("title"))))
    return out


_TAIL = re.compile(r"\s*(?:live-?stream:|for questions\b|to attend virtually|zoom:|https?://)",
                   re.I)


def _business(desc):
    """The subject only: a leading time range ('9:30 - 10:00') and a trailing
    stream link, meeting password or contact line are not business."""
    return _TAIL.split(_LEAD_TIME.sub("", desc), 1)[0].strip(" .;,")


def parse_os_events(data, state, ctx=None):
    """Items from one page of /events. One item per agenda point; an agenda
    point that only says the meeting takes some bills ('Meeting of the
    Assembly Labor Committee', 'Voting meeting on SB 1431 and any other
    business') is one item per bill, its title as the business. A cancelled
    event is left out (so a re-read removes it); an event with no subject is
    one booked slot."""
    items = []
    for ev in (data or {}).get("results") or []:
        if ev.get("deleted") or (ev.get("status") or "").lower() in ("cancelled", "canceled"):
            continue
        dated, at = local_when(ev.get("start_date"), state)
        if not dated or (ctx is not None and not ctx.in_window(dated)):
            continue
        body = event_body(ev)
        committee = not is_floor(ev, body)
        mid = "os:" + (ev.get("id") or "").split("/")[-1]
        url = ((ev.get("sources") or [{}])[0] or {}).get("url") or None
        loc = tidy((ev.get("location") or {}).get("name"))
        same = {body.lower(), tidy(ev.get("name")).lower()}
        out = []

        def add(business, detail=None, reference=None):
            business = _business(business)
            if not business:
                return
            out.append(ra.item(dated, business, body, item_time=at, order=len(out) + 1,
                               meeting_id=mid, detail=detail, reference=reference, url=url,
                               item_type=ra.item_type(business, committee)))

        agenda = sorted(ev.get("agenda") or [], key=lambda a: a.get("order") or 0)
        for a in agenda:
            desc = tidy(a.get("description"))
            bills = _bills(a)
            empty = not desc or bool(_PLACEHOLDER.match(desc)) or desc.lower() in same
            if bills and (empty or _GENERIC.match(desc) or len(bills) > 1
                          and not re.search(r"hearing|briefing|on [A-Z]", desc)):
                for ident, title in bills:
                    add("{0}: {1}".format(ident, title) if title else ident,
                        detail=desc if desc and not empty else None, reference=ident)
            elif bills:
                add(desc, detail="; ".join("{0}: {1}".format(i, t) if t else i
                                           for i, t in bills),
                    reference=", ".join(i for i, _ in bills))
            elif not empty:
                add(desc)
        if not out:
            desc = tidy(ev.get("description"))
            if desc and not _PLACEHOLDER.match(desc) and desc.lower() not in same:
                add(desc, detail=loc or None)
        if not out:
            out.append(ra.item(dated, "", body, item_time=at, meeting_id=mid,
                               detail=loc or None, url=url))
        items += out
    return items


def _sorted_dates(data, state):
    return [local_when(ev.get("start_date"), state)[0] or ""
            for ev in (data or {}).get("results") or []]


def events_url(state, ctx, page=1):
    """One page of a state's events from today to the horizon (the key
    goes as a header, never here)."""
    until = (ctx.until_date + datetime.timedelta(days=1)).isoformat()
    params = [("jurisdiction", state), ("after", ctx.today), ("before", until),
              ("per_page", PER_PAGE), ("page", page),
              ("include", "agenda"), ("include", "participants"), ("include", "sources")]
    return API + "?" + urlencode(params)


def os_reader(state):
    def read(client, ctx):
        b = budget_for(ctx)
        if not b.key:
            if b.missing_told is None:
                b.missing_told = state
                raise FetchError(API, ra.feed(CC), "events-" + state, 0,
                                 "no Open States key (openstates_api_key in config/secrets.yaml "
                                 "or OPENSTATES_API_KEY): the Open States states were not read")
            return ra.RegionRead(source="Open States /events",
                                 note="not read: no Open States key (gap recorded under {0})".format(
                                     b.missing_told.upper()))
        if state not in b.plan:
            return ra.RegionRead(source="Open States /events", skipped=True,
                                 note="not asked this run (weekly rotation, {0} keyed requests "
                                      "a run); stored rows kept".format(b.calls))
        items, page, last_dated, complete, gaps = [], 1, None, False, []
        while True:
            if not b.left():
                why = b.refused or "Open States budget for the run spent ({0} of {1})".format(
                    b.used, b.calls)
                if page == 1:
                    return ra.RegionRead(source="Open States /events",
                                         note="not read: {0}; stored rows kept".format(why))
                gaps.append("{0}: page {1} not read ({2})".format(state.upper(), page, why))
                break
            if ctx.out_of_time():
                gaps.append("{0}: page {1} not read (time budget)".format(state.upper(), page))
                break
            url = events_url(state, ctx, page)
            b.spend()
            try:
                raw = client.get_bytes(url, ra.feed(CC), "events-{0}-{1}".format(state, page),
                                       headers={"X-API-KEY": b.key})
            except FetchError as exc:
                code = getattr(getattr(exc, "cause", None), "code", None)
                if code == 429:
                    b.refused = "Open States refused (429) for the rest of the run"
                raise
            try:
                archive = getattr(client, "_archive", None)
                if archive and isinstance(raw, bytes):
                    archive(raw, ra.feed(CC), "events-{0}-{1}".format(state, page))
            except Exception:                               # noqa: BLE001 - provenance only
                pass
            data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            items += parse_os_events(data, state, ctx)
            dates = [d for d in _sorted_dates(data, state) if d]
            if dates:
                last_dated = dates[-1]
            max_page = ((data.get("pagination") or {}).get("max_page") or 1)
            if page >= max_page:
                complete = True
                break
            if page >= MAX_PAGES:
                gaps.append("{0}: {1} pages of events in the window, {2} read".format(
                    state.upper(), max_page, MAX_PAGES))
                break
            page += 1
        if complete:
            units = [ra.window(ctx.today, ctx.until)]
        elif last_dated and last_dated > ctx.today:
            # Events come in date order: every day before the last one seen
            # was read in full.
            end = (datetime.date.fromisoformat(last_dated) - datetime.timedelta(days=1)).isoformat()
            units = [ra.window(ctx.today, end)]
        else:
            units = []
        return ra.RegionRead(items, units, source="Open States /events", gaps=gaps,
                             note="" if complete else "partly read")
    read.__name__ = "read_" + state
    return read


# --- Washington: the Legislature's web services ----------------------------------

def _wa(el, tag):
    v = el.find(WA_NS + tag)
    return (v.text or "").strip() if v is not None and v.text else ""


def parse_wa_meetings(xml_text):
    """[{id, body, dated, time, cancelled, room}] from GetCommitteeMeetings."""
    root = ET.fromstring(xml_text.lstrip("﻿").encode("utf-8"))
    out = []
    for m in root.iter(WA_NS + "CommitteeMeeting"):
        names = []
        for c in m.iter(WA_NS + "Committee"):
            long_name = _wa(c, "LongName") or _wa(c, "Name")
            if long_name:
                names.append(_html.unescape(long_name))
        when = _wa(m, "Date")
        room = ", ".join(x for x in (_wa(m, "Room"), _wa(m, "Building")) if x)
        out.append({"id": _wa(m, "AgendaId"), "body": " / ".join(names) or "Committee",
                    "dated": when[:10], "time": when[11:16] or None,
                    "cancelled": _wa(m, "Cancelled").lower() == "true", "room": room})
    return out


def parse_wa_items(xml_text):
    """[(order, business, kind, bill)] from GetCommitteeMeetingItems, in the
    agenda's order (Agenda items first, then Public Hearing, Executive
    Session, as the service lists them)."""
    root = ET.fromstring(xml_text.lstrip("﻿").encode("utf-8"))
    out = []
    for n, it in enumerate(root.iter(WA_NS + "CommitteeMeetingItem"), 1):
        desc = _wa(it, "ItemDescription").strip(" .")
        bill = _wa(it, "BillId")
        kind = _wa(it, "HearingTypeDescription") or _wa(it, "HearingType")
        if not desc and not bill:
            continue
        business = desc or bill
        if bill and bill not in business:
            business = "{0}: {1}".format(bill, business)
        out.append((n, business, kind, bill or None))
    return out


def read_wa(client, ctx):
    url = "{0}GetCommitteeMeetings?{1}".format(
        WA_API, urlencode({"beginDate": ctx.today, "endDate": ctx.until}))
    meetings = parse_wa_meetings(client.get_text(url, ra.feed(CC), "wa-meetings"))
    items, gaps, read_ids, failed = [], [], [], []
    for m in meetings:
        if m["cancelled"] or not ctx.in_window(m["dated"]):
            continue
        mid = "wa:" + m["id"]
        page = WA_PAGE.format(m["id"])
        if ctx.out_of_time():
            failed.append(m["id"])
            gaps.append("WA meeting {0}: agenda not read (time budget)".format(m["id"]))
            continue
        try:
            got = parse_wa_items(client.get_text(
                "{0}GetCommitteeMeetingItems?agendaId={1}".format(WA_API, m["id"]),
                ra.feed(CC), "wa-items-" + m["id"]))
        except FetchError as exc:
            # Not read: its stored items stay (no unit covers it).
            failed.append(m["id"])
            gaps.append("WA meeting {0} ({1}): agenda not read: {2}".format(
                m["id"], m["body"][:60], str(exc)[:120]))
            continue
        read_ids.append(mid)
        if not got:
            items.append(ra.item(m["dated"], "", m["body"], item_time=m["time"], meeting_id=mid,
                                 detail=m["room"] or None, url=page))
            continue
        for n, business, kind, bill in got:
            it = ra.item(m["dated"], business, m["body"], item_time=m["time"], order=n,
                         meeting_id=mid, detail=kind or None, reference=bill, url=page)
            if kind and "public hearing" in kind.lower():
                it["item_type"] = "committee evidence"
            items.append(it)
    if failed:
        units = [ra.meeting(x) for x in read_ids]
    else:
        units = [ra.window(ctx.today, ctx.until)]
    return ra.RegionRead(items, units, source="WA Legislature web services (CommitteeMeetingService)",
                         gaps=gaps)


# --- Texas: TLO's upcoming-meetings RSS -------------------------------------------

_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*([AaPp])\.?\s*[Mm]\b")


def _hhmm(text):
    m = _TIME.search(text or "")
    if not m:
        return None
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return "{0:02d}:{1}".format(h, m.group(2))


def parse_tx_rss(xml_text, chamber):
    """[(dated, time, body, link)] from one TLO upcoming-meetings feed. An
    item 'No committee meetings scheduled.' is no meeting."""
    root = ET.fromstring(xml_text.lstrip("﻿").encode("utf-8"))
    out = []
    for it in root.iter("item"):
        title = ra.one_line(it.findtext("title"))
        desc = ra.clean(it.findtext("description") or "")
        if not title or title.lower().startswith("no committee meetings"):
            continue
        text = title + " " + desc
        dated = ra.find_date(text, numeric_order="mdy")
        if not dated:
            continue
        body = re.split(r"\s+-\s+|\s*\(\s*\d|\s+\d{1,2}/\d{1,2}/\d{2,4}", title)[0].strip(" -,")
        if chamber.lower() not in body.lower():
            body = "{0} {1}".format(chamber, body)
        link = ra.one_line(it.findtext("link")) or ra.one_line(it.findtext("guid")) or None
        out.append((dated, _hhmm(text), body, link))
    return out


def read_tx(client, ctx):
    items = []
    for kind, chamber in TX_FEEDS:
        xml_text = client.get_text(TX_RSS.format(kind), ra.feed(CC), "tx-rss-" + kind)
        for dated, at, body, link in parse_tx_rss(xml_text, chamber):
            if ctx.in_window(dated):
                items.append(ra.item(dated, "", body, item_time=at,
                                     meeting_id="tx:{0}:{1}:{2}".format(
                                         dated, at or "", ra.slug(body, 40)), url=link))
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="Texas Legislature Online upcoming-meetings RSS",
                         note="" if items else "no committee meetings posted")


# --- the regions ---------------------------------------------------------------

def _regions():
    order = list(PRIORITY) + [s for s in DIRECT] + [s for s in STATES
                                                   if s not in PRIORITY and s not in DIRECT]
    out = {}
    for s in order:
        if s == "wa":
            out[s] = ra.region(STATES[s], reader=read_wa)
        elif s == "tx":
            out[s] = ra.region(STATES[s], reader=read_tx)
        else:
            out[s] = ra.region(STATES[s], reader=os_reader(s))
    return out


REGIONS = _regions()
