"""Germany: the Bundestag's plenary agenda for the coming sitting week and
its committees' Tagesordnungen, in the shared agenda table (src/agenda.py).

Added 16 October 2026 (branch de-ca-gaps) so the daily sweep
(src/country_day_sweep.py) can read the Bundestag's agenda the way it reads
the other countries'. The German edition's own committee table (de_agenda,
tools/de_agenda.py) is left as it is; this module writes only
country_agenda rows with cc 'de'.

TWO SOURCES, both on www.bundestag.de and both allowed by its robots.txt
(checked 16 October 2026: /xml/, /includes/, /apps/ and one blob are
disallowed; /resource/blob/ and /static/appdata/includes/rss/ are not), asked
at run time through the robots guard:

  * PLENARY: "Tagesordnung komplett kommende Woche", a PDF at a fixed address
    (/resource/blob/473450/Tagesordnung-komplett-kommende-Woche.pdf, 550 KB,
    21 pages for the sitting week of 14 to 16 October 2026). Its header names
    each sitting and its day ("101. Sitzung des Deutschen Bundestages am
    Mittwoch, dem 14. Oktober 2026"); each point carries a day marker in the
    left column ("Mi.", "Do.", "Fr."), its number ("4.", "11. a)", "ZP 3"),
    its words and the Drucksachen it takes ("Drucksache 21/8412"). Points
    marked "wird abgesetzt" keep that word as their status. The PDF is real
    text (pypdf); the parser is a pure function over that text.
  * THE FOLLOWING WEEK: the Tagesordnungen RSS lists the next sitting week's
    full plenary agenda too ("Parlament: Tagesordnung komplett (104. - 106.
    Sitzung)"), a PDF of the same shape, read the same way.
  * COMMITTEES: the Tagesordnungen RSS (the feed tools/de_agenda.py reads),
    one point per committee sitting, dated by the SITTING DATE printed in its
    title ("31. Sitzung am Mittwoch, den 14. Oktober 2026, 9.30 Uhr"), not
    the feed's publication stamp; classified on the agenda PDF's text, read
    for the sittings inside the window only (at most MAX_PDFS).

Refs are BT-Drucksache numbers ('21/8412'). No store table is keyed by them
(de_vorgaenge is keyed by DIP's Vorgang id), so BILLS is None and a point is
on our ground by its own words; config/watchlist-de.yaml is empty.
"""

from __future__ import annotations

import datetime
import io
import re

from src import agenda
from src.http import FetchError

CC = "de"
SOURCE = "the Bundestag's plenary Tagesordnung and its committees' Tagesordnungen"
BILLS = None
FEED = "de-agenda"
PLENARY = "https://www.bundestag.de/resource/blob/473450/Tagesordnung-komplett-kommende-Woche.pdf"
RSS = "https://www.bundestag.de/static/appdata/includes/rss/tagesordnungen.rss"
MAX_PDFS = 20

MONTHS = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
          "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
          "dezember": 12}
DAYS = {"montag": "Mo", "dienstag": "Di", "mittwoch": "Mi", "donnerstag": "Do",
        "freitag": "Fr", "samstag": "Sa", "sonntag": "So"}

SITTING = re.compile(r"(\d{1,3})\.\s*Sitzung des Deutschen Bundestages\s+am\s+(\w+),\s+de[nm]\s+"
                     r"(\d{1,2})\.\s*(\w+)\s+(\d{4})(?:,\s*(\d{1,2})(?:[.:](\d{2}))?\s*Uhr)?")
TERM = re.compile(r"(\d{1,2})\.\s*Wahlperiode")
DAY_MARK = re.compile(r"^(Mo|Di|Mi|Do|Fr|Sa)\.(?:\s+(.*))?$")
POINT = re.compile(r"^(ZP\s*\d{1,3}|\d{1,3}\.)\s+(?:([a-z])\)\s+)?(\S.*)$")
SUB = re.compile(r"^([a-z])\)\s+(\S.*)$")
DRUCKSACHE = re.compile(r"\b(\d{1,2}/\d{1,6})\b")
NOISE_LINE = re.compile(r"Sitzung des Deutschen Bundestages|Wahlperiode|^Seite \d+ von \d+|"
                        r"^Stand:|^Tagesordnung\s*$")
STOP = re.compile(r"^(Überweisungsvorschlag|mitberatend|Federführung)")
COMMITTEE_DATE = re.compile(r"am\s+\w+,\s+de[nm]\s+(\d{1,2})\.\s*(\w+)\s+(\d{4})"
                            r"(?:,\s*(\d{1,2})(?:[.:](\d{2}))?)?")


def _date(day, month, year):
    m = MONTHS.get((month or "").lower())
    if not m:
        return None
    try:
        return datetime.date(int(year), m, int(day)).isoformat()
    except ValueError:
        return None


def sittings(text):
    """{day abbreviation: (date, sitting number, 'HH:MM' or None)} from the
    PDF's header, and the term ('21')."""
    out = {}
    for m in SITTING.finditer(text or ""):
        abbr = DAYS.get(m.group(2).lower())
        date = _date(m.group(3), m.group(4), m.group(5))
        if abbr and date and abbr not in out:
            hhmm = "{0:02d}:{1}".format(int(m.group(6)), m.group(7) or "00") if m.group(6) else None
            out[abbr] = (date, m.group(1), hhmm)
    t = TERM.search(text or "")
    return out, (t.group(1) if t else None)


def _backwards(num, parent):
    """True when a numbered line inside an open point counts backwards from it
    (a TOP 26 whose words say "16. Bericht der Bundesregierung"): words, not
    a new point. Additional points (ZP) are numbered on their own."""
    if not parent or num.startswith("ZP") or parent.startswith("ZP"):
        return False
    try:
        return int(num.rstrip(".")) < int(parent.rstrip("."))
    except ValueError:
        return False


def _label(num, sub):
    num = num.strip()
    if num.startswith("ZP"):
        base = "ZP " + num[2:].strip()
    else:
        base = "TOP " + num.rstrip(".")
    return base + (" " + sub if sub else "")


def parse_plenary(text, url=PLENARY):
    """agenda.point()s for every point of the plenary Tagesordnung. A point's
    title is its own words up to the Drucksache line; `detail` keeps the
    first words after it when the title is only who moved it."""
    days, term = sittings(text)
    if not days:
        return []
    points, cur, day, status, parent, seen = [], None, None, None, None, set()

    def close():
        if cur and cur["title"]:
            d = days.get(cur["day"]) or (None, None, None)
            label = cur["label"]
            pid = "plenary:{0}/{1}:{2}".format(term or "?", d[1] or "?", label)
            n = 2
            while pid in seen:
                pid = "plenary:{0}/{1}:{2}#{3}".format(term or "?", d[1] or "?", label, n)
                n += 1
            seen.add(pid)
            title = " ".join(cur["title"])
            points.append(agenda.point(
                pid, d[0], "{0}: {1}".format(label, title), body="Plenum", kind="plenary",
                time=None, refs=cur["refs"], url=url, status=cur["status"], text=title))

    for raw in (text or "").splitlines():
        line = " ".join(raw.replace(" ", " ").split())
        if not line or NOISE_LINE.search(line):
            continue
        m = DAY_MARK.match(line)
        if m:
            day = m.group(1)
            if cur is not None:
                cur["open"] = False        # the left column: timings, never words
            line = (m.group(2) or "").strip()
            if not line:
                continue
        if "abgesetzt" in line.lower() and not POINT.match(line):
            status = "abgesetzt"
            continue
        pm = POINT.match(line)
        if pm and cur is not None and cur["open"] and _backwards(pm.group(1), parent):
            pm = None                      # "16. Bericht der Bundesregierung": words, not a point
        sm = SUB.match(line) if not pm else None
        if pm:
            close()
            num, sub, rest = pm.group(1), pm.group(2), pm.group(3)
            parent = num
            cur = {"label": _label(num, sub), "day": day, "title": [rest], "refs": [],
                   "status": status, "open": True}
            status = None
            continue
        if sm and parent:
            close()
            cur = {"label": _label(parent, sm.group(1)), "day": day, "title": [sm.group(2)],
                   "refs": [], "status": status, "open": True}
            status = None
            continue
        if cur is None:
            continue
        if line.startswith("Drucksache"):
            cur["refs"] += [r for r in DRUCKSACHE.findall(line) if r not in cur["refs"]]
            cur["open"] = False
            continue
        if STOP.match(line):
            cur["open"] = False
            continue
        if cur["open"] and not re.match(r"^\(?\d+ Min\.\)?|^Beratung$|^verbundene$|^\(ohne$|"
                                        r"^Debatte\)$|^TOP \d", line):
            cur["title"].append(line)
    close()
    # A point with sub-points keeps only its heading ("12. Wahlen zu Gremien"):
    # the sub-points carry the words, so the heading alone is dropped when
    # it names no Drucksache.
    subs = {p["item_id"].rsplit(" ", 1)[0] for p in points if re.search(r" [a-z]$", p["item_id"])}
    return [p for p in points if p["item_id"] not in subs or p["refs"]]


def is_plenary(committee, title):
    """The feed's plenary entries ('Parlament: ...'): the plenary is never a
    committee sitting. Only a full agenda ('Tagesordnung komplett') is read;
    a day's agenda and the planned running order repeat the week's."""
    return (committee or "").strip().lower() == "parlament"


def full_plenary(title):
    return "tagesordnung komplett" in (title or "").lower()


def committee_date(title):
    """(date, 'HH:MM') of a committee sitting, from the feed title's own words."""
    m = COMMITTEE_DATE.search(title or "")
    if not m:
        return None, None
    hhmm = "{0:02d}:{1}".format(int(m.group(4)), m.group(5) or "00") if m.group(4) else None
    return _date(m.group(1), m.group(2), m.group(3)), hhmm


def parse_committees(xml_text):
    """[(guid, committee, title, sitting date, time, openness, pdf url)] from
    the Tagesordnungen RSS (tools/de_agenda.parse_feed), each dated by the
    sitting date in its title; the feed's own stamp only when the title
    prints none."""
    import de_agenda
    out = []
    for guid, cttee, title, date, time, open_, url in de_agenda.parse_feed(xml_text):
        sat, hhmm = committee_date(title)
        out.append((guid, cttee, title, sat or date, hhmm or (None if sat else time), open_, url))
    return out


def pdf_text(client, url, slug):
    import pypdf
    blob = client.get_bytes(url, FEED, slug)
    reader = pypdf.PdfReader(io.BytesIO(blob))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def fetch(client, today, days, log=print):
    import sys
    import os
    tools = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    points, gaps, notes = [], [], []
    try:
        text = pdf_text(client, PLENARY, "plenary-kommende-woche")
        got = [p for p in parse_plenary(text) if p["date"] and today <= p["date"] <= until]
        points += got
        if not got:
            notes.append("the plenary Tagesordnung names no sitting ahead (a week without "
                         "plenary sittings)")
    except (FetchError, ValueError) as exc:
        gaps.append("plenary Tagesordnung: {0}".format(str(exc)[:120]))
    except Exception as exc:                       # noqa: BLE001 - pypdf's own errors
        gaps.append("plenary Tagesordnung unreadable: {0}".format(str(exc)[:120]))
    try:
        feed = parse_committees(client.get_text(RSS, FEED, "tagesordnungen-rss"))
    except Exception as exc:                       # noqa: BLE001 - FetchError or bad XML
        feed = []
        gaps.append("committee Tagesordnungen feed: {0}".format(str(exc)[:120]))
    read = 0
    seen = {p["item_id"] for p in points}
    for guid, cttee, title, date, hhmm, open_, url in feed:
        if is_plenary(cttee, title):
            if not full_plenary(title):
                continue
            # The plenary agenda of a later sitting week, listed in the same
            # feed ("Parlament: Tagesordnung komplett (104. - 106. Sitzung)"):
            # read as the plenary PDF is, its points dated by its own header.
            try:
                got = parse_plenary(pdf_text(client, url, "plenary-" + url.rsplit("/", 1)[-1][:50]),
                                    url=url)
            except Exception as exc:               # noqa: BLE001
                gaps.append("{0}: plenary agenda unreadable ({1})".format(title[:60],
                                                                          str(exc)[:80]))
                continue
            for p in got:
                if p["item_id"] not in seen and p["date"] and today <= p["date"] <= until:
                    seen.add(p["item_id"])
                    points.append(p)
            continue
        if not date or not (today <= date <= until):
            continue
        text = None
        if read < MAX_PDFS:
            read += 1
            try:
                text = pdf_text(client, url, "to-" + url.rsplit("/", 1)[-1][:60])
            except Exception as exc:               # noqa: BLE001
                gaps.append("{0}: agenda unreadable ({1})".format(cttee, str(exc)[:80]))
        refs = sorted(set(DRUCKSACHE.findall(text or ""))) if text else []
        kind = "hearing" if "anhörung" in (title or "").lower() else "committee"
        points.append(agenda.point(guid, date, title, body=cttee, kind=kind, time=hhmm,
                                   refs=refs, url=url, status=open_,
                                   text=" ".join((text or "").split())[:20000] or title))
    plenary = sorted(p["date"] for p in points if p["kind"] == "plenary")
    next_sitting = plenary[0] if plenary else None
    log("de-agenda: {0} plenary point(s), {1} committee sitting(s) in the window".format(
        sum(1 for p in points if p["kind"] == "plenary"),
        sum(1 for p in points if p["kind"] != "plenary")))
    return agenda.fetched(points, next_sitting=next_sitting, note="; ".join(notes) or None,
                          gaps=gaps)
