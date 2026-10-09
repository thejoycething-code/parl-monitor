#!/usr/bin/env python3
"""Ireland, the week ahead: what the Dáil, the Seanad and committees have scheduled.

    python3 tools/ie_schedule.py                        # read the schedule, store it
    python3 tools/ie_schedule.py --dry-run              # fetch and parse, store nothing
    python3 tools/ie_schedule.py --file page.html       # parse a saved page (tests, repairs)
    python3 tools/ie_schedule.py --db /tmp/ie.db --raw-dir /tmp/ie-raw   # a scratch run

PHASE 2 (9 October 2026); see docs/ireland-scope.md.

THE SOURCE. The Oireachtas Open Data API has no schedule: /debates and
/questions return nothing for a future date (measured), and its swagger
lists no order paper. The keyless official source is the Oireachtas's own
"Detailed schedule" page, www.oireachtas.ie/en/detailed-schedule/, one
HTML page with a tab each for the Dáil, the Seanad and committees, from
about two weeks back to as far ahead as anything is scheduled. Its
robots.txt disallows only URLs with a query string ('/*?') and search, so
the page is read without one, once a run, through src/http.py. (The rest of
oireachtas.ie's debate and question pages answer an AWS WAF CAPTCHA, 405;
they are not used. dailbusiness.oir.ie, the Dáil's order paper app, has a
keyless JSON API at dailbusinessapi.oir.ie/api/v1/dailbusiness/items, but
on 9 October 2026 it held no business for the coming week, so there was
nothing to build a parser against: docs/ireland-scope.md lists it.)

WHEN IT IS PUBLISHED. The Seanad and committee schedules for the coming
week were up on Friday morning (9 October 2026: the Seanad's Media
Regulation Bill Committee Stage on 14 October, 27 committee meetings from
13 to 16 October). The Dáil's arrives with its Business Committee report,
later: that morning the Dáil tab said only "No business is currently
scheduled. Dáil Éireann resumes on Tuesday, 13 October 2026". The edition
says which, plainly.

KEYED ON BILL IDS. A line that links a bill ('/en/bills/bill/2026/19/')
stores that bill's key, so the line carries the bill's areas and score by
join. A line that only NAMES a bill (the Dáil tab and most committee
agendas print the title without a link) keeps the printed name in
`bill_named`, as text, and no key: nothing is joined on a title
(CLAUDE.md). Every line's own text is classified too (own_areas).

Separation guarantee: writes ie_schedule, ie_schedule_days, the shared gaps
table and its own source_runs heartbeat ('IE schedule'). ONE WRITER AT A
TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, filter as filt, ie_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
import ie_rollcalls as roll  # noqa: E402

FEED = "ie-schedule"
HEARTBEAT = "IE schedule"
PAGE_URL = "https://www.oireachtas.ie/en/detailed-schedule/"
SITE = "https://www.oireachtas.ie"
TAXONOMY = roll.TAXONOMY
TABS = ("dail", "seanad", "committee")
TEXT_CHARS = 400
TZ = "Europe/Dublin"

_TAB = re.compile(r'<div id="(dail|seanad|committee|tv)" class="tab[^"]*"')
_DAY = re.compile(r'<div class="schedule-day js-day[^"]*"[^>]*data-day="(\d+)"')
_EVENT = re.compile(r'<div class="event">')
_TIME = re.compile(r'<div class="event-time"[^>]*>\s*([0-9]{1,2}[:.][0-9]{2})', re.S)
_BILL_LINK = re.compile(r'href="(?:https://www\.oireachtas\.ie)?/en/bills/bill/(\d{4})/(\d+)/?"')
_COMMITTEE = re.compile(r'<div class="committee-heading">.*?<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_AGENDA = re.compile(r'<div class="agenda-title"[^>]*>(.*?)</div>', re.S)
_ROOM = re.compile(r'<div class="room-name[^"]*">.*?</div>', re.S)
_WATCH = re.compile(r'<div class="c-schedule-item__watch-live">.*?</div>', re.S)
_RESUMES = re.compile(r"((?:Dáil Éireann|Seanad Éireann|The Dáil|The Seanad)[^<]{0,40}?resumes on [^<]{5,60})")
_NAMED = re.compile(r"([A-Z][\w’'(),\- ]*?\bBill,? \d{4})")
# What a committee agenda puts before a bill's name.
_NAME_LEAD = re.compile(r"^.*?(?:General Scheme of(?: the)?|Scrutiny of(?: the)?|Consideration:|: )\s*")


def text_of(markup):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", markup or "", flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return " ".join(t.replace("—", " - ").split())


def day_of(epoch):
    """The schedule's data-day (local midnight, Irish time) -> 'YYYY-MM-DD'."""
    from zoneinfo import ZoneInfo
    return datetime.datetime.fromtimestamp(int(epoch), ZoneInfo(TZ)).date().isoformat()


def _split(markup, pattern):
    """[(match, segment up to the next match)]."""
    hits = list(pattern.finditer(markup))
    return [(m, markup[m.end():hits[i + 1].start() if i + 1 < len(hits) else len(markup)])
            for i, m in enumerate(hits)]


def parse_event(chamber, seg):
    """One scheduled item: time, text, committee, bill keys, bills named."""
    time = _TIME.search(seg)
    clean = _WATCH.sub(" ", _ROOM.sub(" ", seg))
    committee = url = None
    if chamber == "committee":
        head = _COMMITTEE.search(clean)
        if head:
            url = head.group(1) if head.group(1).startswith("http") else SITE + head.group(1)
            committee = text_of(head.group(2))
        # The whole meeting: its topics, witnesses and bills, not only the
        # agenda lines (a topic often sits in the item's title instead).
        body = clean.split('<div class="event-body-committee">', 1)[-1]
        body = re.sub(r'<div class="committee-heading">.*?</div>', " ", body, count=1, flags=re.S)
        text = text_of(body)
        text = re.sub(r"\s*(?:Members View Members|View Members|Contact Contact Details|"
                      r"Contact Details)\b", " ", text)
        text = " ".join(re.sub(r"(?<![\w.])\d{1,2}[:.]\d{2}(?![\w.])", " ", text).split()) or "Meeting"
    else:
        body = clean.split('<div class="event-time"', 1)[-1]
        body = body.split(">", 1)[-1] if ">" in body else body
        text = text_of(re.sub(r"^\s*[0-9]{1,2}[:.][0-9]{2}", "", body))
    keys = []
    for y, n in _BILL_LINK.findall(seg):
        k = roll.bill_key(y, n)
        if k not in keys:
            keys.append(k)
    named = [] if keys else list(dict.fromkeys(
        _NAME_LEAD.sub("", m).strip(" -") for m in _NAMED.findall(text)))
    return {"time": time.group(1).replace(".", ":") if time else None,
            "text": text[:TEXT_CHARS], "committee": committee, "url": url,
            "bill_keys": keys, "bill_named": named}


def parse_page(markup):
    """{chamber: {date: {"items": [...], "note": str or None}}}.

    Each tab lists its days more than once (a desktop and a mobile list);
    the copy with the most items wins."""
    out = {c: {} for c in TABS}
    for tab, seg in _split(markup, _TAB):
        chamber = tab.group(1)
        if chamber not in TABS:
            continue
        for day, dseg in _split(seg, _DAY):
            date = day_of(day.group(1))
            items = [parse_event(chamber, e) for _m, e in _split(dseg, _EVENT)]
            items = [i for i in items if i["time"] or i["text"]]
            note = _RESUMES.search(dseg)
            have = out[chamber].get(date)
            if have is None or len(items) > len(have["items"]):
                out[chamber][date] = {"items": items,
                                      "note": " ".join(note.group(1).split()) if note else
                                      (have or {}).get("note")}
            elif note and not have.get("note"):
                have["note"] = " ".join(note.group(1).split())
    return out


def store(conn, parsed, today, tax=None, wl=None):
    """Upsert every line and day; lines no longer listed for a day re-read
    now are dropped (a schedule changes). Returns (days, items, ours)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else roll.empty_watchlist()
    days = items = ours = 0
    for chamber, by_date in parsed.items():
        for date, day in sorted(by_date.items()):
            keep = []
            for n, it in enumerate(day["items"], 1):
                res = filt.filter_item(tax, wl, roll.strip_offices(it["text"]),
                                       title=roll.strip_offices(it["text"]))
                for b, bkey in enumerate(it["bill_keys"] or [None]):
                    key = "{0}/{1}/{2}/{3}{4}".format(chamber, date, it["time"] or "--:--", n,
                                                     "" if b == 0 else "." + str(b))
                    keep.append(key)
                    url = it["url"] or ("{0}/en/bills/bill/{1}/".format(SITE, bkey) if bkey else None)
                    conn.execute(
                        "INSERT INTO ie_schedule (item_key, chamber, date, time, committee, text, "
                        "bill_key, bill_named, own_areas, matched_terms, url, first_seen, last_seen) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(item_key) DO UPDATE SET "
                        "time=excluded.time, committee=excluded.committee, text=excluded.text, "
                        "bill_key=excluded.bill_key, bill_named=excluded.bill_named, "
                        "own_areas=excluded.own_areas, matched_terms=excluded.matched_terms, "
                        "url=excluded.url, last_seen=excluded.last_seen",
                        (key, chamber, date, it["time"], it["committee"], it["text"], bkey,
                         "; ".join(it["bill_named"]) or None, ie_store.dumps(res.issue_areas),
                         ie_store.dumps(res.matched_terms), url or None, today, today))
                    items += 1
                    ours += roll.on_our_ground(res.issue_areas)
            marks = ",".join("?" * len(keep)) or "''"
            conn.execute("DELETE FROM ie_schedule WHERE chamber=? AND date=? AND item_key NOT IN "
                         "({0})".format(marks), (chamber, date, *keep))
            conn.execute(
                "INSERT INTO ie_schedule_days (chamber, date, status, items, note, first_seen, "
                "last_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(chamber, date) DO UPDATE SET "
                "status=excluded.status, items=excluded.items, note=excluded.note, "
                "last_seen=excluded.last_seen",
                (chamber, date, "listed" if day["items"] else "none", len(day["items"]),
                 day["note"], today, today))
            days += 1
    conn.commit()
    return days, items, ours


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--file", help="parse this saved page instead of fetching")
    ap.add_argument("--dry-run", action="store_true", help="fetch and parse; store nothing")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()
    conn = None if args.dry_run else db.init_db(db.connect(args.db))
    try:
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                markup = fh.read()
        else:
            markup = HttpClient(raw_dir=args.raw_dir).get_text(PAGE_URL, FEED, "detailed-schedule",
                                                               archive=not args.dry_run)
    except (FetchError, OSError) as exc:
        print("  [gap] the Oireachtas schedule: {0}".format(str(exc)[:90]))
        if conn is not None:
            roll._gap(conn, today, "ie-schedule: {0}".format(str(exc)[:200]))
            conn.commit()
        return 1
    parsed = parse_page(markup)
    found = sum(len(v) for v in parsed.values())
    if not found:
        # The page answered but held no day at all: a changed page, not a recess
        # (a recess still lists the days, each "No business is currently scheduled").
        print("  [gap] the Oireachtas schedule: no day found on the page (has it changed?)")
        if conn is not None:
            roll._gap(conn, today, "ie-schedule: no day found on the page")
            conn.commit()
        return 1
    for chamber in TABS:
        ahead = {d: v for d, v in parsed[chamber].items() if d > today}
        print("ie-schedule: {0}: {1} day(s) on the page, {2} ahead with {3} item(s){4}".format(
            chamber, len(parsed[chamber]), len(ahead), sum(len(v["items"]) for v in ahead.values()),
            "; " + next((v["note"] for v in parsed[chamber].values() if v["note"]), "")
            if any(v["note"] for v in parsed[chamber].values()) else ""))
    if args.dry_run:
        return 0
    days, items, ours = store(conn, parsed, today)
    ie_store.stamp(conn, HEARTBEAT, today, "step heartbeat: tools/ie_schedule.py")
    conn.commit()
    print("ie-schedule: {0} day(s), {1} line(s) stored, {2} on our ground by their own text; "
          "{3} line(s) carry a bill key".format(
              days, items, ours,
              conn.execute("SELECT COUNT(*) FROM ie_schedule WHERE bill_key IS NOT NULL").fetchone()[0]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
