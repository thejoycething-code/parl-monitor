"""Who sits this week: the one-line sitting-days summary at the top of the UK
weekly (round 3 of the countdown, Chris, 16 October 2026: "Holyrood in
recess until 26 Oct · Commons and Lords sitting · Senedd sitting").

ONLY WHAT A SOURCE SAYS. Each legislature's line comes from its own
published calendar, read by a machine route, and a legislature whose source
could not be read is left out of the line (and named in the coverage notes),
never guessed:

  * Westminster: the UK Parliament What's On API, /calendar/events/
    nonsitting.json (the Commons and Lords recesses, non-sitting Fridays and
    bank holidays; the same keyless API the diary is read from;
    whatson-api.parliament.uk has no robots.txt rules).
  * Holyrood: the Parliamentary Bureau's "Parliamentary Recess Dates"
    motions in data.parliament.scot's open-data API (motionfilter=recess),
    e.g. S7M-00153 "10 to 25 October 2026 (inclusive)". The newest motion
    covering a date wins.
  * Senedd: its published recess dates sit on HTML pages its WAF refuses us
    (403, 16 October 2026), so the Senedd line says what the Senedd's own
    calendar web service (business.senedd.wales mgWebService, the route
    sd_agenda already reads) lists: the Plenary meetings booked this week,
    or that none is, with the next one.
  * NI Assembly: the Assembly's "Recess Dates" page (niassembly.gov.uk,
    robots.txt allows it): the Business Committee's agreed recesses.

Stored in sitting_calendar (one row per published period or Plenary day,
replaced per source on each successful read; a failed read keeps the last
good rows and records a gap), read by sitting_line() at render.
"""

from __future__ import annotations

import datetime
import html as _html
import json
import re

FEED = "sitting-days"

WESTMINSTER_URL = ("https://whatson-api.parliament.uk/calendar/events/nonsitting.json"
                   "?queryParameters.startDate={0}&queryParameters.endDate={1}")
HOLYROOD_URL = "https://data.parliament.scot/api/MotionsQuestionsAnswersMotionsBusiness?motionfilter=recess"
HOLYROOD_MOTION = "https://www.parliament.scot/chamber-and-committees/votes-and-motions/{0}"
SENEDD_COMMITTEES = "https://business.senedd.wales/mgWebService.asmx/GetCommittees"
SENEDD_MEETINGS = ("https://business.senedd.wales/mgWebService.asmx/GetMeetings"
                   "?lCommitteeId={0}&sFromDate={1}&sToDate={2}")
SENEDD_PLENARY_ID = 908          # "Plenary", the Seventh Senedd (GetCommittees, 16 October 2026)
NI_URL = "https://www.niassembly.gov.uk/about-the-assembly/general-information/"

COMMONS, LORDS, HOLYROOD, SENEDD, NI = "Commons", "Lords", "Holyrood", "Senedd", "NI Assembly"
ORDER = (COMMONS, LORDS, HOLYROOD, SENEDD, NI)

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def ensure_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS sitting_calendar ("
                 "legislature TEXT NOT NULL, kind TEXT NOT NULL, "   # recess | non-sitting | plenary
                 "start TEXT NOT NULL, end TEXT NOT NULL, label TEXT, source TEXT, "
                 "fetched_at TEXT NOT NULL, PRIMARY KEY (legislature, kind, start))")
    conn.commit()


# -- parsing (pure) ------------------------------------------------------------

def parse_westminster(events):
    """nonsitting.json -> [(legislature, kind, start, end, label)]."""
    out = []
    for e in events or []:
        house = (e.get("House") or "").strip()
        if house not in (COMMONS, LORDS):
            continue
        cat = (e.get("Category") or "").strip()
        start, end = (e.get("StartDate") or "")[:10], (e.get("EndDate") or "")[:10]
        if not start or not end:
            continue
        kind = "recess" if cat.lower().startswith("recess") else "non-sitting"
        out.append((house, kind, start, end, e.get("Description") or cat))
    return out


def _date_in(text, default_year=None):
    m = re.match(r"\s*(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?", text or "")
    if not m or m.group(2).lower() not in _MONTHS:
        return None, None
    return int(m.group(1)), (_MONTHS[m.group(2).lower()], int(m.group(3)) if m.group(3) else default_year)


_RANGE = re.compile(r"(\d{1,2})(?:\s+([A-Za-z]+))?(?:\s+(\d{4}))?(?:\s*\((?:am|pm)\))?\s*(?:to|–|-)\s*"
                    r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")


def parse_ranges(text):
    """'27 June to 30 August 2026 (inclusive), 10 to 25 October 2026
    (inclusive), 19 December 2026 to 3 January 2027' -> [(start, end) ISO]."""
    out = []
    for m in _RANGE.finditer(text or ""):
        d1, mon1, y1, d2, mon2, y2 = m.groups()
        if mon2.lower() not in _MONTHS or (mon1 and mon1.lower() not in _MONTHS):
            continue
        end = datetime.date(int(y2), _MONTHS[mon2.lower()], int(d2))
        month1 = _MONTHS[(mon1 or mon2).lower()]
        year1 = int(y1) if y1 else (end.year if month1 <= end.month else end.year - 1)
        try:
            start = datetime.date(year1, month1, int(d1))
        except ValueError:
            continue
        if start <= end:
            out.append((start.isoformat(), end.isoformat()))
    return out


def parse_holyrood(motions):
    """Bureau recess motions -> [(HOLYROOD, 'recess', start, end, label)],
    newest motion first wins where two cover the same dates."""
    picked = []
    for m in sorted(motions or [], key=lambda m: m.get("SubmissionDateTime") or "", reverse=True):
        title = (m.get("Title") or "").lower()
        text = m.get("ItemText") or ""
        if "recess" not in title or "agrees" not in text.lower():
            continue
        for start, end in parse_ranges(text):
            if any(s <= start <= e or s <= end <= e for s, e, _ in picked):
                continue
            picked.append((start, end, m.get("EventID") or ""))
    return [(HOLYROOD, "recess", s, e, ref) for s, e, ref in picked]


def parse_senedd_meetings(xml_text):
    """GetMeetings XML -> [(SENEDD, 'plenary', day, day, meeting id)] for
    meetings not cancelled."""
    out = []
    for block in re.findall(r"<meeting>(.*?)</meeting>", xml_text or "", re.S):
        date = re.search(r"<meetingdate>(\d{2})/(\d{2})/(\d{4})</meetingdate>", block)
        status = re.search(r"<meetingstatus>([^<]*)</meetingstatus>", block)
        mid = re.search(r"<meetingid>(\d+)</meetingid>", block)
        if not date or (status and "cancel" in status.group(1).lower()):
            continue
        day = "{0}-{1}-{2}".format(date.group(3), date.group(2), date.group(1))
        out.append((SENEDD, "plenary", day, day, mid.group(1) if mid else ""))
    return out


def parse_ni(page):
    """The NI Assembly Recess Dates page -> [(NI, 'recess', start, end, name)].
    Reads 'Halloween 2026 24 October 2026 to 1 November 2026 ...'."""
    text = _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page or "")))
    i = text.lower().find("agreed the following recess dates")
    if i < 0:
        return []
    out = []
    for m in re.finditer(r"([A-Z][A-Za-z ]{2,30}?)\s+(\d{4})\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+to\s+"
                         r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}|dissolution)", text[i:]):
        name = m.group(1).strip()
        s = parse_ranges("{0} to {0}".format(m.group(3)))
        if not s:
            continue
        start = s[0][0]
        if m.group(4).lower() == "dissolution":
            continue                       # open-ended: nothing to state as a date
        e = parse_ranges("{0} to {0}".format(m.group(4)))
        if e and start <= e[0][0]:
            out.append((NI, "recess", start, e[0][0], "{0} {1}".format(name, m.group(2))))
    return out


# -- collecting (network, through the robots guard) ----------------------------

def make_client(raw_dir, log=print):
    """A robots-guarded client for the four sources. The Senedd's web
    service answers our own UA, not the browser UA src/http.py keeps for
    that host's blocked web pages (tools/sd_agenda.py does the same)."""
    from src import robots_guard
    from src.http import HttpClient
    raw = HttpClient(raw_dir=raw_dir)
    raw.host_user_agents.pop("business.senedd.wales", None)
    return robots_guard.guard(raw, FEED, log=log)


def _store(conn, legislature, rows, fetched_at, kinds):
    q = ",".join("?" * len(kinds))
    conn.execute("DELETE FROM sitting_calendar WHERE legislature = ? AND kind IN ({0})".format(q),
                 [legislature] + list(kinds))
    for leg, kind, start, end, label in rows:
        conn.execute("INSERT OR REPLACE INTO sitting_calendar (legislature, kind, start, end, label, source, "
                     "fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (leg, kind, start, end, label, {COMMONS: "whatson-api", LORDS: "whatson-api",
                                                     HOLYROOD: "data.parliament.scot", SENEDD: "senedd-ws",
                                                     NI: "niassembly"}[leg], fetched_at))


def collect(client, conn, today, horizon_days=70, log=print, gap=None):
    """Read every source; a source that fails keeps its last good rows and is
    a gap. Returns {legislature: rows stored or None for a failure}."""
    ensure_table(conn)
    gap = gap or (lambda detail: log("  [gap] {0}: {1}".format(FEED, detail)))
    start = today - datetime.timedelta(days=60)
    end = today + datetime.timedelta(days=horizon_days)
    stamp = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    got = {}

    def attempt(label, fn):
        try:
            got[label] = fn()
        except Exception as exc:                              # noqa: BLE001
            got[label] = None
            gap("{0}: {1}".format(label, str(getattr(exc, "cause", exc))[:160]))

    def westminster():
        rows = parse_westminster(client.get_json(
            WESTMINSTER_URL.format(start.isoformat(), end.isoformat()), "whatson", "nonsitting"))
        for house in (COMMONS, LORDS):
            _store(conn, house, [r for r in rows if r[0] == house], stamp, ("recess", "non-sitting"))
        return len(rows)

    def holyrood():
        rows = [r for r in parse_holyrood(client.get_json(HOLYROOD_URL, "holyrood", "recess-motions",
                                                          timeout=120, archive=False))
                if r[3] >= start.isoformat()]
        if not rows:
            raise ValueError("the recess motions answered but no recess date parsed")
        _store(conn, HOLYROOD, rows, stamp, ("recess",))
        return len(rows)

    def senedd():
        xml = client.get_text(SENEDD_MEETINGS.format(SENEDD_PLENARY_ID, start.strftime("%d/%m/%Y"),
                                                     end.strftime("%d/%m/%Y")),
                              "senedd", "plenary-meetings", archive=False)
        if "<meetings" not in xml and "<meeting>" not in xml:
            raise ValueError("the calendar web service answered in a shape this reader does not know")
        rows = parse_senedd_meetings(xml)
        _store(conn, SENEDD, rows, stamp, ("plenary",))
        return len(rows)

    def ni():
        rows = parse_ni(client.get_text(NI_URL, "niassembly", "recess-dates", archive=False))
        if not rows:
            raise ValueError("the Recess Dates page answered but no recess parsed")
        _store(conn, NI, rows, stamp, ("recess",))
        return len(rows)

    for label, fn in (("Westminster", westminster), (HOLYROOD, holyrood), (SENEDD, senedd), (NI, ni)):
        attempt(label, fn)
    conn.commit()
    return got


# -- the line ------------------------------------------------------------------

def _d(iso):
    return datetime.date.fromisoformat(iso[:10])


def _day(d, with_day=True):
    return ("{0} ".format(_DAYS[d.weekday()]) if with_day else "") + "{0} {1}".format(d.day, _MON[d.month])


def _status(rows, ws, we):
    """For a recess-list legislature: ('recess', start, end) covering the
    working week, ('part', start, end) for a recess starting or ending inside
    it, else ('sitting', None, None)."""
    workdays = [ws + datetime.timedelta(days=i) for i in range(5)]
    for r in sorted(rows, key=lambda r: r["start"]):
        if r["kind"] != "recess":
            continue
        s, e = _d(r["start"]), _d(r["end"])
        covered = [d for d in workdays if s <= d <= e]
        if len(covered) == len(workdays):
            return "recess", s, e
        if covered or ws <= s <= we:
            return "part", s, e
    return "sitting", None, None


def _recess_phrase(name, status, s, e, ws, we):
    if status == "recess":
        return "{0} in recess until {1}".format(name, _day(e))
    if s and s > ws:
        return "{0} sitting, in recess from {1}".format(name, _day(s))
    return "{0} in recess until {1}".format(name, _day(e))


def sitting_line(conn, week_commencing):
    """(line, missing): the one-line summary for the week, and the
    legislatures no source could speak for (for the coverage notes)."""
    ws = _d(week_commencing)
    we = ws + datetime.timedelta(days=6)
    try:
        rows = conn.execute("SELECT legislature, kind, start, end, label FROM sitting_calendar").fetchall()
    except Exception:                                         # noqa: BLE001 - table absent
        rows = []
    by = {}
    for r in rows:
        by.setdefault(r["legislature"], []).append(r)
    parts, missing = [], []

    # Westminster: the two Houses together when they agree.
    if COMMONS in by or LORDS in by:
        st = {h: _status(by.get(h, []), ws, we) for h in (COMMONS, LORDS) if h in by}
        c, l = st.get(COMMONS), st.get(LORDS)
        if c and l and c[0] == l[0] == "sitting":
            parts.append("Commons and Lords sitting")
        elif c and l and c[0] == l[0] and (c[0] == "recess" and c[2] == l[2] or
                                            c[0] == "part" and c[1] == l[1] and c[1] > ws):
            parts.append(_recess_phrase("Commons and Lords", *c, ws, we))
        else:
            for h, (status, s, e) in st.items():
                parts.append("{0} sitting".format(h) if status == "sitting"
                             else _recess_phrase(h, status, s, e, ws, we))
    else:
        missing.append("Westminster")

    if HOLYROOD in by:
        status, s, e = _status(by[HOLYROOD], ws, we)
        parts.append("Holyrood sitting" if status == "sitting" else _recess_phrase("Holyrood", status, s, e, ws, we))
    else:
        missing.append(HOLYROOD)

    if SENEDD in by:
        days = sorted({_d(r["start"]) for r in by[SENEDD] if r["kind"] == "plenary"})
        this = [d for d in days if ws <= d <= we]
        if this:
            parts.append("Senedd sitting (Plenary {0})".format(
                " and ".join(_day(d) if i == len(this) - 1 else "{0} {1}".format(_DAYS[d.weekday()], d.day)
                             for i, d in enumerate(this))))
        else:
            nxt = next((d for d in days if d > we), None)
            parts.append("Senedd: no Plenary this week" + (", next {0}".format(_day(nxt)) if nxt else ""))
    else:
        missing.append(SENEDD)

    if NI in by:
        status, s, e = _status(by[NI], ws, we)
        parts.append("NI Assembly sitting" if status == "sitting" else _recess_phrase("NI Assembly", status, s, e, ws, we))
    else:
        missing.append(NI)

    return (" · ".join(parts) if parts else None), missing
