#!/usr/bin/env python3
"""Slovakia: what was said in the Národná rada, speech by speech.

    python3 tools/sk_chamber.py                      # the last three weeks
    python3 tools/sk_chamber.py --since 2026-09-01 --budget-seconds 600
    python3 tools/sk_chamber.py --dry-run
    python3 tools/sk_chamber.py --reclassify

Remaining speech coverage (11 October 2026, branch gaps-speeches), on the
shared chamber layer (src/chamber_store.py). QUESTIONS are not collected
here: the Slovak edition already carries the interpellations
(sk_interpellations, tools/sk_rollcalls.py).

THE SOURCE, measured 11 October 2026: the NR SR's debate record ("Textový
prepis rozpravy"), www.nrsr.sk/web/Default.aspx?sid=schodze/rozprava/
vyhladavanie&CisObdobia=9, keyless; www.nrsr.sk has no robots.txt (404).
The search answers a plain GET with the term's speeches, NEWEST FIRST,
twenty to a page (about 150 KB, 3 seconds): for each one the time ("9. 10.
2026 15:32:21 - 15:54:29"), the meeting and day, the print debated ("Tlač
1555", linked), the speaker ("Lackovič, Marek"), their office ("- poslanec
NR SR", "- podpredseda NR SR", a minister's title), the kind of contribution
("Vystúpenie v rozprave", "Vystúpenie s faktickou poznámkou", "Vstup
predsedajúceho", ...) and the text, with a link to that speech's video
(tv.nrsr.sk/archiv/schodza/9/<meeting>?id=<n>, the speech's own id). The
next pages are ASP.NET postbacks of the same form (Page$2, Page$3, ...), a
read-only listing request: the page's own __VIEWSTATE is sent back, nothing
else. A speech printed under several prints appears once per print; the
video id is the key and the first print named is the debate.

THE TEXT LAGS. On Sunday 11 October 2026 the speeches of Friday morning
(9 October) had their text and those of Friday afternoon did not yet (the
row is listed with an empty text, "text neprešiel jazykovou úpravou"). A
row without text is not read and not counted; the three-week lookback reads
it once its text appears. Slovakia is therefore not a same-day source (no
live read).

THE CHAIR. A contribution whose kind is "Vstup predsedajúceho" or blank
(the presiding officer's interventions print with no kind) is the chair and
is never stored; a vice-president who speaks in the debate is stored.

PARTY. The record prints no party; the speaker's club comes from sk_members
(the Slovak weekly's roster, its latest club) where the name matches one
member, and person_id is the PoslanecID.

BUDGET. Pages are read newest first, about ten pages a sitting day at 5
seconds each (measured 11 October 2026: 88 pages for nine sitting days).
Each run starts again at the newest page (the postback cannot be resumed)
and stops at --since, at the time budget, or at the first day older than
SETTLE_DAYS that was read whole when no older day in the window is
part-read: so a normal week walks its own days and the days whose text was
still to come. A run stopped by the clock marks its oldest day 'partial',
and the next walks back past it.
"""

from __future__ import annotations

import datetime
import html as htmlmod
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402

CC = "sk"
FEED = "sk-chamber"
HOST = "www.nrsr.sk"
TERM = 9
SEARCH = ("https://www.nrsr.sk/web/Default.aspx?sid=schodze/rozprava/vyhladavanie"
          "&CisObdobia={0}".format(TERM))
PRINT = "https://www.nrsr.sk/web/Default.aspx?sid=zakony/cpt&ZakZborID=13&CisObdobia={0}&ID={1}"
GRID = "_sectionLayoutContainer$ctl01$_resultGrid"
MAX_PAGES = 200
SETTLE_DAYS = 4             # a day older than this, read whole, is not walked again

CHAIR_KINDS = ("", "-", "vstup predsedajúceho")
_ITEM = re.compile(r'<div class="daily_info_item">(.*?)(?=<div class="daily_info_item">|'
                   r'</table>)', re.S)
_WHEN = re.compile(r'header_left">\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\s+(\d{1,2}:\d{2}:\d{2})')
_MIDDLE = re.compile(r'<span class="daily_info_speech_header_middle">(.*?)</span>', re.S)
_PLAIN = re.compile(r'<span class="">(.*?)</span>', re.S)
_KIND = re.compile(r"<em>(.*?)</em>", re.S)
_TEXT = re.compile(r'<div class="grid_12 alpha omega">(.*?)</div>', re.S)
_VIDEO = re.compile(r"tv\.nrsr\.sk/archiv/schodza/\d+/(\d+)\?id=(\d+)")
_PRINT = re.compile(r"ID=(\d+)'>\s*(\d+)\s*</a>")


def _plain(fragment):
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def parse_page(page):
    """[{'vid', 'meeting', 'date', 'time', 'sitting', 'print', 'speaker',
    'office', 'kind', 'text'}] in page order; rows without a video id are
    skipped (nothing to key them on)."""
    out = []
    for block in _ITEM.findall(page or ""):
        vid = _VIDEO.search(block)
        when = _WHEN.search(block)
        if not vid or not when:
            continue
        middles = _MIDDLE.findall(block)
        plains = [_plain(p) for p in _PLAIN.findall(block)]
        kind = _KIND.search(block)
        text = _TEXT.search(block)
        prints = _PRINT.findall(middles[1] if len(middles) > 1 else "")
        body = re.sub(r"(?i)<br\s*/?>|</p>", "\n", text.group(1)) if text else ""
        out.append({
            "vid": vid.group(2), "meeting": vid.group(1),
            "date": "{0}-{1:02d}-{2:02d}".format(when.group(3), int(when.group(2)),
                                                 int(when.group(1))),
            "time": when.group(4),
            "sitting": _plain(middles[0]) if middles else None,
            "print": prints[0][1] if prints else None,
            "speaker": plains[0] if plains else None,
            "office": (plains[2] if len(plains) > 2 else "").lstrip("- ").strip() or None,
            "kind": _plain(kind.group(1)) if kind else "",
            "text": "\n".join(" ".join(ln.split()) for ln in htmlmod.unescape(
                re.sub(r"<[^>]+>", " ", body)).split("\n") if ln.strip()),
        })
    return out


def is_chair(row):
    return (row.get("kind") or "").strip().lower() in CHAIR_KINDS


def postback_fields(page, argument):
    """The form's own state, sent back to ask for another page of results."""
    fields = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        m = re.search(r'name="{0}" id="{0}" value="([^"]*)"'.format(name), page or "")
        if m:
            fields[name] = htmlmod.unescape(m.group(1))
    fields["__EVENTTARGET"] = GRID
    fields["__EVENTARGUMENT"] = argument
    return fields


def roster(conn):
    """{folded 'Surname, Name': (PoslanecID, club)}; a shared name maps to None."""
    from src.noise import fold
    out = {}
    try:
        rows = conn.execute("SELECT mp_id, name, club FROM sk_members").fetchall()
    except Exception:                               # noqa: BLE001
        return {}
    for mp_id, name, club in rows:
        k = " ".join(fold(name or "").lower().split())
        out[k] = None if k in out else (str(mp_id), None if club in (None, "", "-") else club)
    return out


def titles(conn):
    """{print number: title} from sk_bills (term 9)."""
    try:
        return {str(r[0]): r[1] for r in conn.execute(
            "SELECT tlac, title FROM sk_bills WHERE term = ?", (TERM,))}
    except Exception:                               # noqa: BLE001
        return {}


def role_of(office):
    o = (office or "").lower()
    if not o or "poslan" in o or "predseda nr sr" in o:
        return "member"
    return office                                   # 'minister ...', 'predseda vlády SR', ...


def debate_of(row, prints):
    if row["print"]:
        t = prints.get(row["print"])
        return ("tlač {0}".format(row["print"]),
                "Tlač {0}{1}".format(row["print"], ": " + t if t else ""))
    label = row["sitting"] or "rozprava"
    return (cs.short_id(row["meeting"], row["date"], label), label)


def done_days(run):
    """{date: status} of the days already read in the window."""
    return {r[0]: r[1] for r in run.conn.execute(
        "SELECT date, status FROM sk_record_reads WHERE feed = 'speeches' AND date >= ?",
        (run.since,)).fetchall()}


def settled(state, date, cut):
    """True when the walk can stop at this day: it is older than the text lag,
    it was read whole, and no older day in the window is part-read."""
    return (date < cut and state.get(date) == "read"
            and not any(st != "read" and d < date for d, st in state.items()))


def speeches(run):
    run.client.enable_gzip(HOST)
    members, prints = roster(run.conn), titles(run.conn)
    from src.noise import fold
    try:
        page = run.client.get_text(SEARCH, FEED, "rozprava-{0}-p1".format(run.today))
    except FetchError as exc:
        run.gap("debate record unreadable: {0}".format(str(exc)[:100]))
        return
    seen, days, n, reached, settled_stop = set(), {}, 1, False, False
    debate_titles = {}
    state = done_days(run)
    cut = (datetime.date.fromisoformat(run.today)
           - datetime.timedelta(days=SETTLE_DAYS)).isoformat()
    while True:
        rows = parse_page(page)
        if not rows:
            break
        for row in rows:
            if row["date"] < run.since:
                reached = True
                continue
            if settled(state, row["date"], cut):
                settled_stop = True
                break
            if row["vid"] in seen:
                continue
            seen.add(row["vid"])
            day = days.setdefault(row["date"], {"listed": 0, "read": 0, "pending": 0,
                                                "matched": 0, "chars": 0})
            if is_chair(row):
                continue
            day["listed"] += 1
            if not row["text"]:
                day["pending"] += 1
                continue
            day["read"] += 1
            day["chars"] += len(row["text"])
            debate_id, debate = debate_of(row, prints)
            if debate not in debate_titles:
                debate_titles[debate] = cs.classify_title(run.taxes, debate)
            m = cs.classify_speech(run.taxes, row["text"], debate_titles[debate])
            if not m:
                continue
            day["matched"] += 1
            member = members.get(" ".join(fold(row["speaker"] or "").lower().split()))
            run.speech({"speech_id": "{0}/{1}".format(row["meeting"], row["vid"]),
                        "doc_id": "{0}/{1}".format(TERM, row["date"]),
                        "date": row["date"], "chamber": None, "debate_id": debate_id,
                        "debate": debate, "speaker": row["speaker"],
                        "party": member[1] if member else None,
                        "role": role_of(row["office"]),
                        "person_id": member[0] if member else None, "text": row["text"],
                        "url": "https://tv.nrsr.sk/archiv/schodza/{0}/{1}?id={2}".format(
                            TERM, row["meeting"], row["vid"]),
                        "title_areas": debate_titles[debate].areas}, m)
        if reached or settled_stop or n >= MAX_PAGES or "Page${0}".format(n + 1) not in page:
            break
        if run.out_of_time("debate pages", n):
            break
        n += 1
        try:
            page = run.client.post_form(SEARCH, postback_fields(page, "Page${0}".format(n)),
                                        FEED, "rozprava-{0}-p{1}".format(run.today, n),
                                        timeout=90, archive=True)
        except FetchError as exc:
            run.gap("debate record page {0} unreadable: {1}".format(n, str(exc)[:100]))
            break
    # Stopped by the clock: the oldest day reached may be cut short, so it is
    # 'partial' and the next run walks back to it (and past it).
    cut_short = run.stopped and not reached and not settled_stop
    oldest = min(days) if days else None
    for date, d in sorted(days.items()):
        status = "partial" if d["pending"] or (cut_short and date == oldest) else "read"
        run.read("{0}/{1}".format(TERM, date), "speeches", date,
                 "{0} read, {1} awaiting text".format(d["read"], d["pending"]),
                 d["read"], d["matched"], d["chars"], status)
        run.log("  [rozprava] {0}: {1} speech(es) listed, {2} with text, {3} on our ground{4}"
                .format(date, d["listed"], d["read"], d["matched"],
                        "; {0} awaiting their text".format(d["pending"]) if d["pending"] else ""))
    run.log("  [rozprava] {0} page(s) read since {1}{2}".format(
        n, run.since, "; stopped at days already read" if settled_stop else ""))


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"speeches": speeches}, doc=__doc__))
