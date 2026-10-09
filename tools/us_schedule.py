#!/usr/bin/env python3
"""US Congress, the week ahead: what is SCHEDULED, keyed on bill keys.

    python3 tools/us_schedule.py                        # today to the Sunday after next Monday
    python3 tools/us_schedule.py --from 2026-09-14 --days 5   # a past week
    python3 tools/us_schedule.py --dry-run              # fetch and parse, store nothing
    python3 tools/us_schedule.py --no-senate            # senate.gov refuses this machine
    python3 tools/us_schedule.py --senate-only          # the half GitHub runs for the Mini
    python3 tools/us_schedule.py --db /tmp/us.db        # anywhere but the store

Built 9 October 2026, in the election recess, against the week of 14
September (tests/fixtures/us_schedule). Every source is open and keyless:

  * docs.house.gov/billsthisweek/<yyyymmdd>/<yyyymmdd>.xml -- the Majority
    Leader's floor list for the week beginning that Monday, with bill
    numbers and links to the text. A week the House is out answers 404:
    that is "no list", not a failure. The list is by WEEK; it never says
    which day a bill comes up. docs.house.gov/floor/ names the latest week
    posted, which is read every run so a recess edition can say when the
    last list was.
  * docs.house.gov/Committee/Calendar/ByDay.aspx?DayID=<mmddyyyy> -- every
    House committee meeting on a day (the week view leaves some out: 14 of
    the week of 14 September against 17 on the 16th alone), then each
    meeting's own page, ByEvent.aspx?EventID=<n>, for its kind (hearing or
    markup), its status (a cancelled meeting stays listed) and the "Text
    of Legislation" it names. The page offers a "Meeting XML" too, but only
    through an ASP.NET postback; its <legis-num> drops the bill type on
    half the bills of the markup it was tried on ("10355" for H.R. 10355),
    so the plain GET of the page is read instead.
  * senate.gov/general/committee_schedules/hearings.xml -- every Senate
    committee meeting scheduled, with the bills it will take as
    <AssociatedDocument document_prefix="SN" document_num="5045"/>.
  * senate.gov/legislative/schedule/floor_schedule.htm -- the Senate's next
    sitting ("Convene at 3:00 p.m."), rarely with a bill.

SENATE.GOV REFUSES SOME NETWORKS (403 on every page from the laptop on 9
October 2026, as for tools/us_rollcalls.py) and answers GitHub's runners.
So the Senate half runs where senate.gov answers; elsewhere it records ONE
[gap] and a 'refused' week, and the edition says the Senate was not read.
The fixtures of the week of 14 September are senate.gov's own files as the
Internet Archive saved them that morning; the recess ones came from the
probe-hosts workflow on 9 October.

KEYS, NEVER TITLES. A row of us_schedule is one bill at one event, keyed
'<congress>/<type>/<number>' exactly as us_bills is, so it carries the
bill's areas and score by join. The line's own text is classified too
(own_areas), so a bill the BILLSTATUS pull has not reached yet still shows
when its floor line names our ground.

Separation guarantee: writes us_schedule, us_meetings, us_schedule_weeks and
the shared gaps table only. ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "us-schedule"
CURRENT_CONGRESS = 119
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
HOUSE_FLOOR = "https://docs.house.gov/billsthisweek/{0}/{0}.xml"
HOUSE_FLOOR_INDEX = "https://docs.house.gov/floor/"
HOUSE_DAY = "https://docs.house.gov/Committee/Calendar/ByDay.aspx?DayID={0}"
HOUSE_EVENT = "https://docs.house.gov/Committee/Calendar/ByEvent.aspx?EventID={0}"
SENATE_HEARINGS = "https://www.senate.gov/general/committee_schedules/hearings.xml"
SENATE_FLOOR = "https://www.senate.gov/legislative/schedule/floor_schedule.htm"
HIDDEN_AREAS = (11,)
# A step heartbeat, as tools/prov_speeches.py stamps one: tools/coverage.py
# excuses the three empty tables only until this is first stamped.
HEARTBEAT = "US schedule"

# A bill reference in running text: 'H.R. 309', 'S.790', 'H. Con. Res. 93',
# 'H.J. Res. 210', 'Senate amendments to H.R. 5334'. Longest forms first,
# and never after a letter or a full stop, so 'U.S.C. 5' is not S. 5.
_REF = re.compile(
    r"(?<![A-Za-z.])("
    r"H\.?\s?J\.?\s?Res\.?|H\.?\s?Con\.?\s?Res\.?|H\.?\s?Res\.?|H\.?\s?R\.?|"
    r"S\.?\s?J\.?\s?Res\.?|S\.?\s?Con\.?\s?Res\.?|S\.?\s?Res\.?|S\.?"
    r")\s?(\d{1,5})\b")
_REF_TYPE = {"HJRES": "hjres", "HCONRES": "hconres", "HRES": "hres", "HR": "hr",
             "SJRES": "sjres", "SCONRES": "sconres", "SRES": "sres", "S": "s"}
# The Senate's <AssociatedDocument document_prefix>. PN is a nomination,
# not a bill, and is left out on purpose.
_SENATE_PREFIX = {"SN": "s", "S": "s", "HR": "hr", "SRES": "sres", "HRES": "hres",
                  "SJRES": "sjres", "HJRES": "hjres", "SCONRES": "sconres",
                  "HCONRES": "hconres"}


def bill_key(congress, bill_type, number):
    return "{0}/{1}/{2}".format(int(congress), bill_type, int(number))


def bill_refs(text, congress=CURRENT_CONGRESS):
    """Every bill KEY named in a line of text, in order, once each."""
    out = []
    for m in _REF.finditer(text or ""):
        kind = _REF_TYPE.get(re.sub(r"[^A-Z]", "", m.group(1).upper()))
        if kind:
            key = bill_key(congress, kind, m.group(2))
            if key not in out:
                out.append(key)
    return out


def monday(day):
    return day - datetime.timedelta(days=day.weekday())


def window(today):
    """(first, last) day of the week ahead: today to the Sunday after the
    coming Monday. A Friday run covers the next ten days; a Monday run, the
    week it starts."""
    nxt = today if today.weekday() == 0 else today + datetime.timedelta(days=7 - today.weekday())
    return today, nxt + datetime.timedelta(days=6)


def oneline(text):
    return " ".join(html.unescape(text or "").replace("—", " - ").split())


def strip_tags(markup):
    return oneline(re.sub(r"<[^>]+>", " ", markup or ""))


# --- House floor -------------------------------------------------------------

def floor_category(label):
    low = (label or "").lower()
    if "suspension" in low:
        return "suspension"
    if "pursuant to a rule" in low:
        return "rule"
    return "may be considered"


def parse_house_floor(raw):
    """The Majority Leader's weekly list -> {week_of, congress, items}, or
    None for anything that is not a <floorschedule>. Each item carries its
    bill KEYS; an item naming no bill (a report, a motion) has none."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    if root.tag != "floorschedule":
        return None
    congress = int(root.get("congress-num") or CURRENT_CONGRESS)
    items = []
    for cat in root.findall("category"):
        category = floor_category(cat.get("type"))
        for it in cat.findall("floor-items/floor-item"):
            legis = oneline(it.findtext("legis-num"))
            text = oneline(it.findtext("floor-text"))
            # 'HR 7834 Suspension Text.pdf': the House leaves spaces in some.
            urls = [f.get("doc-url").strip().replace(" ", "%20")
                    for f in it.findall("files/file") if f.get("doc-url")]
            items.append({
                "id": it.get("id"), "category": category, "legis_num": legis or None,
                "text": text or None, "doc_url": urls[0] if urls else None,
                "removed": bool((it.get("remove-date") or "").strip()),
                "bills": bill_refs(legis, congress) or bill_refs(text, congress),
            })
    return {"week_of": root.get("week-date"), "congress": congress, "items": items}


def latest_floor_week(page):
    """The latest week docs.house.gov/floor/ links to, ISO, or None."""
    weeks = sorted(set(re.findall(r"billsthisweek/(\d{8})", page or "")))
    if not weeks:
        return None
    w = weeks[-1]
    return "{0}-{1}-{2}".format(w[:4], w[4:6], w[6:])


# --- House committees --------------------------------------------------------

_DAY_ROW = re.compile(
    r'<a href="ByEvent\.aspx\?EventID=(\d+)"\s+title="(.*?)">.*?'
    r'<span class="text-tiny" title="(.*?)">.*?'
    r'<span class="text-small">(.*?)</span>.*?<span class="text-small">(.*?)</span>', re.S)


def parse_house_day(page):
    """One day of the House committee calendar -> [{event_id, title,
    committee, time, location}]. A day with no meetings ("No meetings
    found.") gives []; a page without the meetings grid at all gives None,
    so a redesign reads as a gap and never as a quiet day."""
    if 'id="MainContent_GridViewMeetings"' not in (page or ""):
        return None
    out = []
    for m in _DAY_ROW.finditer(page or ""):
        out.append({"event_id": m.group(1), "title": oneline(m.group(2)) or None,
                    "committee": oneline(m.group(3)) or None,
                    "time": clock(m.group(4)),
                    "location": oneline(m.group(5)) or None})
    return out


def clock(text):
    """'9:45 AM' or '09:30:00' -> '09:45' / '09:30'; anything else as given."""
    text = oneline(text)
    for fmt in ("%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.datetime.strptime(text, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return text or None


def meeting_kind(text):
    low = (text or "").lower()
    if "markup" in low or "business meeting" in low or "mark up" in low:
        return "markup"
    if "hearing" in low:
        return "hearing"
    return "meeting"


def _section(page, heading):
    m = re.search(r"<h2>\s*{0}\s*</h2>(.*?)(?=<h2>|<div class=\"divider\"|$)".format(
        re.escape(heading)), page or "", re.S)
    return m.group(1) if m else ""


def parse_house_event(page, congress=CURRENT_CONGRESS):
    """One meeting's page -> {kind, title, committee, date, status, bills,
    legislation}, or None if it has no meeting panel."""
    panel = re.search(r'<div id="previewPanel".*', page or "", re.S)
    if not panel:
        return None
    panel = panel.group(0)
    h1 = re.search(r"<h1>(.*?)<small", panel, re.S)
    head = strip_tags(h1.group(1)) if h1 else ""
    # 'Markup of Various Measures', 'Field Hearing: "Examining ..."'.
    hm = re.match(r"^(.*?(?:Markup of|Hearing:|Meeting:|Hearing|Markup))\s*(.*)$", head)
    kind_text, title = (hm.group(1), hm.group(2)) if hm else ("", head)
    cm = re.search(r"<blockquote>\s*<p>(.*?)<br", panel, re.S)
    when = re.search(r'<p class="meetingTime">(.*?)</p>', panel, re.S)
    date = None
    if when:
        dm = re.search(r"([A-Z][a-z]+day, [A-Z][a-z]+ \d{1,2}, \d{4})", strip_tags(when.group(1)))
        if dm:
            date = datetime.datetime.strptime(dm.group(1), "%A, %B %d, %Y").date().isoformat()
    alert = re.search(r'<strong class="status-alert">(.*?)</strong>', panel, re.S)
    alert = strip_tags(alert.group(1)).lower() if alert else ""
    # 'Meeting was rescheduled to the time and date listed above.' (119549)
    status = ("cancelled" if "cancel" in alert else "postponed" if "postpone" in alert
              else "rescheduled" if "reschedul" in alert else "scheduled")
    legislation = [strip_tags(re.sub(r"\[.*", "", li, flags=re.S))
                   for li in re.findall(r"<li>(.*?)</li>", _section(panel, "Text of Legislation"),
                                        re.S)]
    bills, lines = [], {}
    for line in [title] + legislation:
        for key in bill_refs(line, congress):
            if key not in bills:
                bills.append(key)
    # A bill's OWN line is its entry in the legislation list ("H.R. 10329 -
    # Combating Foreign Threats..."), never the meeting's title, which would
    # lend every bill the other bills' words.
    for line in legislation:
        for key in bill_refs(line, congress):
            lines.setdefault(key, line)
    return {"kind": meeting_kind(kind_text or head), "title": oneline(title.strip('"“” '))
            or None, "committee": strip_tags(cm.group(1)) if cm else None, "date": date,
            "status": status, "legislation": legislation, "bills": bills, "lines": lines}


# --- Senate ------------------------------------------------------------------

def parse_senate_hearings(raw, congress=CURRENT_CONGRESS):
    """hearings.xml -> [meeting dict]. The 'No committee hearings scheduled'
    placeholder, with no committee, is not a meeting."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    if root.tag != "css_meetings_scheduled":
        return None
    out = []
    for m in root.findall("meeting"):
        committee = oneline(m.findtext("committee"))
        if not committee:
            continue
        matter = oneline(m.findtext("matter"))
        bills, lines = [], {}
        for d in m.iter("AssociatedDocument"):
            kind = _SENATE_PREFIX.get((d.get("document_prefix") or "").upper())
            if kind and (d.get("document_num") or "").isdigit():
                key = bill_key(d.get("congress") or congress, kind, d.get("document_num"))
                if key not in bills:
                    bills.append(key)
                    lines[key] = oneline(d.get("document_description")) or None
        for key in bill_refs(matter, congress):
            if key not in bills:
                bills.append(key)
        date = oneline(m.findtext("date_iso_8601")) or None
        time = clock(m.findtext("time_iso_8601")) or clock(m.findtext("time"))
        out.append({"identifier": oneline(m.findtext("identifier")) or None,
                    "code": oneline(m.findtext("cmte_code")) or None,
                    "committee": committee, "type": oneline(m.findtext("type")) or None,
                    "kind": meeting_kind(oneline(m.findtext("type")) + " " + matter),
                    "date": date, "time": time, "location": oneline(m.findtext("room")) or None,
                    "title": matter or None, "bills": bills, "lines": lines,
                    "status": "scheduled"})
    return out


def parse_senate_floor(page, congress=CURRENT_CONGRESS):
    """floor_schedule.htm -> {date, note, bills} for the NEXT sitting, or
    None if the page carries no schedule article."""
    art = re.search(r'<article id="proceedings_schedule"[^>]*>(.*?)</article>', page or "", re.S)
    if not art:
        return None
    h3 = re.search(r"<h3>(.*?)</h3>", art.group(1), re.S)
    note = re.search(r'<span class="floor-schedule">(.*?)</span>', art.group(1), re.S)
    date = None
    if h3:
        try:
            date = datetime.datetime.strptime(strip_tags(h3.group(1)), "%A, %b %d, %Y").date().isoformat()
        except ValueError:
            date = None
    note = strip_tags(note.group(1)) if note else None
    return {"date": date, "note": note, "bills": bill_refs(note, congress)}


# --- storing -----------------------------------------------------------------

def _classify(tax, wl, *texts):
    res = filt.filter_item(tax, wl, *[t for t in texts if t])
    return res


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def store_week(conn, chamber, source, week_of, status, items, note, today):
    conn.execute(
        "INSERT INTO us_schedule_weeks (chamber, source, week_of, status, items, note, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(chamber, source, week_of) DO UPDATE SET "
        # A refusal never overwrites what an earlier run READ: "refused" is
        # about this machine, not about the week.
        "status=CASE WHEN excluded.status='refused' AND us_schedule_weeks.status "
        "IN ('listed','none') THEN us_schedule_weeks.status ELSE excluded.status END, "
        "items=CASE WHEN excluded.status='refused' THEN us_schedule_weeks.items "
        "ELSE excluded.items END, "
        "note=COALESCE(excluded.note, us_schedule_weeks.note), last_seen=excluded.last_seen",
        (chamber, source, week_of, status, items, note, today, today))


def store_row(conn, row, tax, wl, today):
    res = _classify(tax, wl, row.get("text"), row.get("legis_num"))
    conn.execute(
        "INSERT INTO us_schedule (sched_key, bill_key, chamber, kind, week_of, date, "
        "meeting_key, category, legis_num, text, doc_url, status, own_areas, matched_terms, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(sched_key) DO UPDATE SET kind=excluded.kind, date=excluded.date, "
        "category=excluded.category, legis_num=excluded.legis_num, text=excluded.text, "
        "doc_url=excluded.doc_url, status=excluded.status, own_areas=excluded.own_areas, "
        "matched_terms=excluded.matched_terms, last_seen=excluded.last_seen",
        (row["sched_key"], row["bill_key"], row["chamber"], row["kind"], row["week_of"],
         row.get("date"), row.get("meeting_key"), row.get("category"), row.get("legis_num"),
         row.get("text"), row.get("doc_url"), row.get("status"),
         us_store.dumps(res.issue_areas), us_store.dumps(res.matched_terms), today, today))
    return res.issue_areas


def store_meeting(conn, m, tax, wl, today):
    res = _classify(tax, wl, m.get("title"), *(m.get("legislation") or []))
    conn.execute(
        "INSERT INTO us_meetings (meeting_key, chamber, event_id, committee, kind, title, date, "
        "time, location, status, url, bills, own_areas, matched_terms, tier, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(meeting_key) DO UPDATE SET committee=excluded.committee, "
        "kind=excluded.kind, title=excluded.title, date=excluded.date, time=excluded.time, "
        "location=excluded.location, status=excluded.status, bills=excluded.bills, "
        "own_areas=excluded.own_areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (m["meeting_key"], m["chamber"], m.get("event_id"), m.get("committee"), m.get("kind"),
         m.get("title"), m.get("date"), m.get("time"), m.get("location"), m.get("status"),
         m.get("url"), us_store.dumps(m.get("bills")), us_store.dumps(res.issue_areas),
         us_store.dumps(res.matched_terms), res.tier, today, today))
    # A meeting with no date cannot be placed in a week; it stays in
    # us_meetings, and its bills wait for a page that dates it.
    for key in (m.get("bills") or []) if m.get("date") else []:
        store_row(conn, {"sched_key": "{0}/{1}".format(m["meeting_key"].replace(
            m["chamber"] + "-", m["chamber"] + "-cmte-", 1), key),
            "bill_key": key, "chamber": m["chamber"], "kind": m.get("kind") or "meeting",
            "week_of": monday(datetime.date.fromisoformat(m["date"])).isoformat(),
            "date": m.get("date"),
            "meeting_key": m["meeting_key"], "legis_num": None,
            "text": (m.get("lines") or {}).get(key), "doc_url": m.get("url"),
            "status": m.get("status")},
            tax, wl, today)
    return res.issue_areas


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


# --- the pulls ---------------------------------------------------------------

class Tally:
    def __init__(self):
        self.rows = self.ours = self.meetings = self.gaps = 0
        self.latest = None        # the latest House floor week posted, when read


def pull_house_floor(conn, client, weeks, today, tax, wl, log=print, dry=False, t=None):
    """Each week's list; then, if none of them is posted, the latest that is,
    so the store (and a recess edition) keeps the last thing the House
    scheduled. Returns the Tally."""
    t = t or Tally()
    listed = False
    for week in weeks:
        stamp = week.replace("-", "")
        try:
            raw = client.get_bytes(HOUSE_FLOOR.format(stamp), FEED, "house-floor-" + stamp)
        except FetchError as exc:
            if getattr(exc.cause, "code", None) == 404 or "HTTP Error 404" in str(exc):
                log("  House floor, week of {0}: no list posted (the House is not sitting)".format(week))
                if not dry:
                    store_week(conn, "house", "floor", week, "none", 0, None, today)
                continue
            if not dry:
                _gap(conn, today, "house floor {0}: {1}".format(week, exc))
                store_week(conn, "house", "floor", week, "refused", None, str(exc)[:200], today)
            log("  [gap] House floor {0}: {1}".format(week, str(exc)[:80]))
            t.gaps += 1
            continue
        if _store_floor(conn, raw, week, today, tax, wl, log, dry, t):
            listed = True
    if not listed:
        try:
            latest = latest_floor_week(client.get_text(HOUSE_FLOOR_INDEX, FEED, "house-floor-index"))
        except FetchError as exc:
            latest = None
            log("  [gap] House floor index: {0}".format(str(exc)[:80]))
            if not dry:
                _gap(conn, today, "house floor index: {0}".format(exc))
            t.gaps += 1
        t.latest = latest
        if latest and latest not in weeks:
            stamp = latest.replace("-", "")
            try:
                raw = client.get_bytes(HOUSE_FLOOR.format(stamp), FEED, "house-floor-" + stamp)
            except FetchError as exc:
                log("  [gap] House floor, latest week {0}: {1}".format(latest, str(exc)[:80]))
                if not dry:
                    _gap(conn, today, "house floor {0}: {1}".format(latest, exc))
                t.gaps += 1
            else:
                log("  House floor: the latest list posted is for the week of {0}".format(latest))
                _store_floor(conn, raw, latest, today, tax, wl, log, dry, t)
    return t


def _store_floor(conn, raw, week, today, tax, wl, log, dry, t):
    parsed = parse_house_floor(raw)
    if parsed is None:
        log("  [gap] House floor {0}: not a floor schedule".format(week))
        if not dry:
            _gap(conn, today, "house floor {0}: not a floor schedule".format(week))
        t.gaps += 1
        return False
    week = parsed["week_of"] or week
    live = [i for i in parsed["items"] if not i["removed"]]
    keyed = ours = 0
    for it in parsed["items"]:
        for key in it["bills"]:
            keyed += 1
            row = {"sched_key": "house-floor-{0}/{1}".format(week, key), "bill_key": key,
                   "chamber": "house", "kind": "floor", "week_of": week, "date": None,
                   "category": it["category"], "legis_num": it["legis_num"], "text": it["text"],
                   "doc_url": it["doc_url"], "status": "removed" if it["removed"] else "listed"}
            if dry:
                continue
            own = store_row(conn, row, tax, wl, today)
            areas = set(own) | set(_bill_areas(conn, key))
            ours += on_our_ground(areas)
    if not dry:
        store_week(conn, "house", "floor", week, "listed", len(live), None, today)
        conn.commit()
    t.rows += keyed
    t.ours += ours
    unkeyed = sum(1 for i in parsed["items"] if not i["bills"])
    log("  House floor, week of {0}: {1} item(s), {2} bill row(s), {3} on our ground{4}".format(
        week, len(live), keyed, ours,
        "; {0} item(s) name no bill".format(unkeyed) if unkeyed else ""))
    return True


def _bill_areas(conn, key):
    row = conn.execute("SELECT areas FROM us_bills WHERE bill_key=?", (key,)).fetchone()
    try:
        return json.loads(row[0] or "[]") if row else []
    except ValueError:
        return []


def pull_house_committees(conn, client, days, today, tax, wl, log=print, dry=False, t=None,
                          budget=None):
    """Every committee meeting on each day, and each meeting's own page."""
    t = t or Tally()
    weeks = {}
    for day in days:
        if budget is not None and budget.exhausted():
            log(budget.disclose("House committee days", t.meetings))
            break
        stamp = day.strftime("%m%d%Y")
        week = monday(day).isoformat()
        weeks.setdefault(week, 0)
        try:
            listing = parse_house_day(client.get_text(HOUSE_DAY.format(stamp), FEED,
                                                      "house-cmte-day-" + stamp))
            if listing is None:
                raise FetchError(HOUSE_DAY.format(stamp), FEED, stamp, 1,
                                 ValueError("no meetings grid on the page"))
        except FetchError as exc:
            log("  [gap] House committees {0}: {1}".format(day, str(exc)[:80]))
            if not dry:
                _gap(conn, today, "house committees {0}: {1}".format(day, exc))
            t.gaps += 1
            weeks[week] = None
            continue
        for ev in listing:
            try:
                page = client.get_text(HOUSE_EVENT.format(ev["event_id"]), FEED,
                                       "house-cmte-event-" + ev["event_id"])
                detail = parse_house_event(page)
            except FetchError as exc:
                detail = None
                log("  [gap] House meeting {0}: {1}".format(ev["event_id"], str(exc)[:80]))
            if detail is None:
                if not dry:
                    _gap(conn, today, "house meeting {0}: no detail page".format(ev["event_id"]))
                t.gaps += 1
                detail = {"kind": meeting_kind(ev["title"]), "title": ev["title"],
                          "committee": ev["committee"], "date": day.isoformat(),
                          "status": "scheduled", "legislation": [],
                          "bills": bill_refs(ev["title"]), "lines": {}}
            m = {"meeting_key": "house-" + ev["event_id"], "chamber": "house",
                 "event_id": ev["event_id"], "committee": ev["committee"] or detail["committee"],
                 "kind": detail["kind"], "title": detail["title"] or ev["title"],
                 "date": detail["date"] or day.isoformat(), "time": ev["time"],
                 "location": ev["location"], "status": detail["status"],
                 "url": HOUSE_EVENT.format(ev["event_id"]), "bills": detail["bills"],
                 "lines": detail["lines"], "legislation": detail["legislation"]}
            t.meetings += 1
            if weeks[week] is not None:
                weeks[week] += 1
            t.rows += len(m["bills"])
            if dry:
                continue
            own = store_meeting(conn, m, tax, wl, today)
            ground = on_our_ground(own) or any(on_our_ground(_bill_areas(conn, k))
                                                for k in m["bills"])
            t.ours += ground
        if not dry:
            conn.commit()
    if not dry:
        for week, n in weeks.items():
            if n is not None:
                store_week(conn, "house", "committees", week, "listed" if n else "none", n,
                           None, today)
        conn.commit()
    log("  House committees: {0} meeting(s) over {1} day(s), {2} bill row(s), "
        "{3} on our ground".format(t.meetings, len(days), t.rows, t.ours))
    return t


def pull_senate(conn, client, first, last, today, tax, wl, log=print, dry=False, t=None):
    """Senate committee meetings and the next sitting, or one [gap] when
    senate.gov refuses this machine."""
    t = t or Tally()
    weeks = sorted({monday(first).isoformat(), monday(last).isoformat()})
    try:
        meetings = parse_senate_hearings(client.get_bytes(SENATE_HEARINGS, FEED, "senate-hearings"))
        floor = parse_senate_floor(client.get_text(SENATE_FLOOR, FEED, "senate-floor-schedule"))
    except FetchError as exc:
        log("  [gap] senate.gov: {0} (it refuses some networks and answers CI; the Senate "
            "schedule runs from GitHub)".format(str(exc)[:70]))
        if not dry:
            _gap(conn, today, "senate schedule: {0}".format(exc))
            for week in weeks:
                for source in ("floor", "committees"):
                    store_week(conn, "senate", source, week, "refused", None,
                               "senate.gov refused this machine", today)
            conn.commit()
        t.gaps += 1
        return t
    if meetings is None:
        log("  [gap] Senate hearings: not a meetings file")
        if not dry:
            _gap(conn, today, "senate hearings: not a meetings file")
        t.gaps += 1
        meetings = []
    per_week = {w: 0 for w in weeks}
    for m in meetings:
        m["chamber"] = "senate"
        m["meeting_key"] = "senate-{0}".format(m["identifier"] or "{0}-{1}-{2}".format(
            m["code"], m["date"], m["time"]))
        m["event_id"] = m["identifier"]
        m["url"] = "https://www.senate.gov/committees/hearings_meetings.htm"
        if m["date"]:
            per_week[monday(datetime.date.fromisoformat(m["date"])).isoformat()] = \
                per_week.get(monday(datetime.date.fromisoformat(m["date"])).isoformat(), 0) + 1
        t.meetings += 1
        t.rows += len(m["bills"])
        if dry:
            continue
        own = store_meeting(conn, m, tax, wl, today)
        t.ours += on_our_ground(own) or any(on_our_ground(_bill_areas(conn, k)) for k in m["bills"])
    if floor and floor["date"]:
        week = monday(datetime.date.fromisoformat(floor["date"])).isoformat()
        for key in floor["bills"]:
            t.rows += 1
            if not dry:
                store_row(conn, {"sched_key": "senate-floor-{0}/{1}".format(floor["date"], key),
                                 "bill_key": key, "chamber": "senate", "kind": "floor",
                                 "week_of": week, "date": floor["date"], "text": floor["note"],
                                 "doc_url": SENATE_FLOOR, "status": "listed"}, tax, wl, today)
        if not dry:
            store_week(conn, "senate", "floor", week, "listed", len(floor["bills"]),
                       "{0}: {1}".format(floor["date"], floor["note"]), today)
    if not dry:
        for week, n in per_week.items():
            store_week(conn, "senate", "committees", week, "listed" if n else "none", n, None, today)
        conn.commit()
    log("  Senate: {0} committee meeting(s), {1} on our ground; next sitting {2}: {3}".format(
        t.meetings, t.ours, (floor or {}).get("date") or "?", (floor or {}).get("note") or "?"))
    return t


def stamp_heartbeat(conn, today):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/us_schedule.py"))
    conn.commit()


def seed_days(conn, latest):
    """The sitting days of the latest floor week, when the store holds no
    House meeting at all: a first run in recess (9 October 2026) would
    otherwise leave us_meetings empty for weeks, which the coverage watch
    rightly reads as a wipe. Once, never again: the next run finds rows."""
    if not latest or conn.execute("SELECT 1 FROM us_meetings WHERE chamber='house' "
                                  "LIMIT 1").fetchone():
        return []
    start = datetime.date.fromisoformat(latest)
    return [start + datetime.timedelta(days=i) for i in range(5)]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--from", dest="start", help="first day, ISO (default: today)")
    ap.add_argument("--days", type=int, help="days to read (default: to the Sunday after "
                                             "the coming Monday)")
    ap.add_argument("--no-senate", action="store_true")
    ap.add_argument("--senate-only", action="store_true")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true", help="fetch and parse, store nothing")
    args = ap.parse_args()
    today = datetime.date.today()
    first = datetime.date.fromisoformat(args.start) if args.start else today
    last = (first + datetime.timedelta(days=args.days - 1)) if args.days else window(first)[1]
    days = [first + datetime.timedelta(days=i) for i in range((last - first).days + 1)]
    weeks = sorted({monday(d).isoformat() for d in days})
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    tax = filt.load_taxonomy(TAXONOMY)
    wl = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])
    budget = drain.Budget(args.budget_seconds)
    stamp = today.isoformat()
    print("us-schedule: {0} to {1}{2}".format(first, last, " (dry run)" if args.dry_run else ""))
    gaps = 0
    if not args.senate_only:
        floor = pull_house_floor(conn, client, weeks, stamp, tax, wl, dry=args.dry_run)
        gaps += floor.gaps
        gaps += pull_house_committees(conn, client, days, stamp, tax, wl, dry=args.dry_run,
                                      budget=budget).gaps
        seed = [] if args.dry_run else seed_days(conn, floor.latest)
        if seed:
            print("  no House meeting stored yet: reading the week of {0} once, the "
                  "last the House sat".format(floor.latest))
            gaps += pull_house_committees(conn, client, seed, stamp, tax, wl, budget=budget).gaps
    if not args.no_senate:
        gaps += pull_senate(conn, client, first, last, stamp, tax, wl, dry=args.dry_run).gaps
    if not args.dry_run:
        stamp_heartbeat(conn, stamp)
        n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        print("  store: {0} scheduled bill row(s), {1} meeting(s), {2} week(s) asked".format(
            n("SELECT COUNT(*) FROM us_schedule"), n("SELECT COUNT(*) FROM us_meetings"),
            n("SELECT COUNT(*) FROM us_schedule_weeks")))
    conn.close()
    # Non-zero on a gap, as tools/us_rollcalls.py: the job carries on and
    # says so, the gap is in the store, and the run is not silently green.
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
