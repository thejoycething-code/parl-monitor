"""Germany: the sixteen Landtage's forward business (regional_agenda,
16 October 2026; docs/germany-laender-scope.md has every route measured).

Until now the Länder were covered votes-only (abgeordnetenwatch, see
docs/germany-scope.md item 3). Each Landtag publishes its own calendar and
its own Tagesordnungen, on its own platform, so each has its own reader;
what they share is here: an iCal reader, an RSS reader, and ONE splitter
for a German order of business ("1. ...", "2. ...") that works on PDF text
(pypdf, via src.de_btp.extract_text) and on HTML alike.

THE SHAPE OF EVERY READER: a calendar of booked sittings (iCal, RSS, a
JSON calendar or an HTML list) gives every plenary sitting and committee
meeting in the window; a sitting whose Tagesordnung is published (usually
about a week ahead) becomes one item per agenda point, every other sitting
ONE 'to be announced' row. A Tagesordnung that cannot be fetched is a
partial gap: its day is then not declared read, so its stored rows stay.

PRIVATE PERSONS: election objections and petitions name private people
("Einspruch des Herrn Dr. D. K. G., Greven"): those names are cut from the
business and detail text (`unname`), the title is kept.
"""

from __future__ import annotations

import base64
import datetime
import gzip
import html as _html
import json
import re
from urllib.parse import urljoin

from src import regional_agenda as ra
from src.http import FetchError

CC = "de"
TAXONOMIES = (("taxonomy-de.yaml", "de"),)
FEED = ra.feed(CC)
THROTTLES = {"www.landtag.nrw.de": 1.2, "sd.bremische-buergerschaft.de": 1.5}

MAX_DOCS = 24          # agenda documents fetched per Landtag per run
DETAIL_DAYS = 21       # how far ahead a per-meeting page is worth asking for

WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
_WD = "|".join(WEEKDAYS)


# --- shared helpers ------------------------------------------------------------

def pdf_text(data):
    from src.de_btp import extract_text
    return extract_text(data or b"")


def despace(line):
    """'D i e n s t a g , 20. Oktober' -> 'Dienstag, 20. Oktober' (letter-
    spaced headings in Bayern's and Thüringen's PDFs)."""
    def join(m):
        return m.group(0).replace(" ", "")
    return re.sub(r"(?<![\w])(?:[A-Za-zÄÖÜäöüß] ){2,}[A-Za-zÄÖÜäöüß](?![\w])", join, line)


_DAY_HEAD = re.compile(r"\b(?:%s)\s*,?\s*(?:den|dem)?\s*(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+|\d{1,2}\.)\s*(\d{4})" % _WD)


def day_heading(line):
    m = _DAY_HEAD.search(despace(line))
    if not m:
        return None
    return ra.iso(m.group(1), m.group(2).rstrip("."), m.group(3))


_TOP = re.compile(r"^\s*(?:\d{1,2}[.:]\d{2}\s*-\s*\d{1,2}[.:]\d{2}\s+)?(?:TOP\s*)?(\d{1,2})\s*\.(?!\d)"
                  r"\s*(.*)$")
_LINE_HEAD = re.compile(r"^(?:am\s+|(?:Erster|Zweiter|Dritter|Vierter|Fünfter) Sitzungstag[^,]{0,30}?\bam\s+)?"
                        r"(?:%s)\b" % "|".join(WEEKDAYS))
_NOT_TOP = re.compile(r"^(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|"
                      r"November|Dezember|Wahlperiode|Sitzung|Tagung|Plenarsitzung|Lesung)\b")
_NOISE = re.compile(
    r"^(?:-\s*\d+\s*-|Seite \d+|.*\bSeite \d+\s*$|Beginn(?: ca\.)?\b.*|anschließend$|"
    r"\d{1,2}[:.]\d{2}(?: bis \d{1,2}[:.]\d{2})? Uhr$|Beratungszeit:.*|Begründung:.*|"
    r"Aussprache:?.*|Allgemeine Aussprache.*|Gesamtredezeit.*|Fraktionen: \d+.*|\d+ Min\..*|"
    r"ohne Aussprache$|Berichterstatt\w*:.*|Mitberichterstatt\w*:.*|Berichterstattung:.*|"
    r"Beratungsverfahren$|Block [IVX]+$|direkte Abstimmung$|Nummer$|Buchstabe$|"
    r"Verhandlungsgegenstand$|Hinweis(?:e)?:$|Drucksachen?$|Mittagspause:?.*|\(Meldefrist:.*\)$|"
    r"Abstimmungsergebnis.*|Redezeiten.*|(?:Zustimmung|Ablehnung|Enthaltung)\b.*|"
    r"[^\n]*?[ \t]\d:\d{2}$|Möglicher Ablauf.*|in Minuten$|_{5,})",
    re.I)
_CAPS = re.compile(r"^[A-ZÄÖÜ]{2,}(?:[ \t]+[A-ZÄÖÜ]{2,})+[ \t]*$")   # 'SPD CDU GRÜNE AfD'
_INLINE = re.compile(r"\s*(?:Beginn(?: ca\.)? \d{1,2}[:.]\d{2} Uhr|\banschließend\b|[.…]{3,}|"
                     r"\d{1,2}[:.]\d{2} bis \d{1,2}[:.]\d{2} Uhr)\s*")
_REF = re.compile(r"(?:Drucksache|Drucks\.|Drs\.)\s*(\d{1,2}/\s?\d+)")
_BARE_REF = re.compile(r"(?<![\d/.])(\d{1,2}/\d{3,5})(?![\d/])")
_PRIVATE = re.compile(
    r"\b(?:des|der|dem|den)\s+(?:Herrn|Frau)\s+(?:Dr\.\s+|Prof\.\s+)*(?:[A-ZÄÖÜ]\.\s*){1,4}"
    r"(?:\s*[A-ZÄÖÜ][\w.-]*)?(?:,\s*[A-ZÄÖÜ][\w-]+)?")
_SUB = re.compile(r"\s(?:[a-z]{2})\)\s")


def unname(text):
    """Private persons out of an agenda line (initials of election
    objectors, petitioners); MPs and ministers named in full stay."""
    t = _PRIVATE.sub("", text or "")
    t = _SUB.sub(" ", t)
    return " ".join(t.split())


def business_of(text, limit=300):
    """The business of one agenda point: its text up to the first
    Drucksache number (inclusive), at most `limit` characters."""
    t = " ".join(_INLINE.sub(" ", unname(text)).split())
    m = _REF.search(t)
    if m and m.start() >= 15 and m.end() <= limit + 40:
        t = t[:m.end()]
    t = t.strip(" –-;,")
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + " …"
    return t


def ref_of(text):
    m = _REF.search(text or "") or _BARE_REF.search(text or "")
    return "Drs. " + m.group(1).replace(" ", "") if m else None


def split_tops(text, default_date=None, start_marker=r"tagesordnung", stop_marker=None):
    """[(date, order, block_text)] for every numbered agenda point in a
    German order of business. Points must count up from 1 (a '19.
    Wahlperiode' or '69. Sitzung' is never a point); a line naming a
    weekday and a date after the start switches the day (a multi-day
    plenary agenda); before the start, the first such line is the
    sitting's own date."""
    raw = [despace(l).strip() for l in (text or "").splitlines()]
    lines = []
    for l in raw:
        if lines and re.match(r"^(?:%s),?$" % "|".join(WEEKDAYS), lines[-1]) and re.match(r"^\d", l):
            lines[-1] = lines[-1].rstrip(",") + ", " + l
        else:
            lines.append(l)
    start = 0
    if start_marker:
        for i, l in enumerate(lines):
            if re.search(start_marker, l, re.I):
                start = i + 1
                break
    date = default_date
    for l in lines[:start]:
        d = day_heading(l)
        if d:
            date = d
            break
    out, cur, expect = [], None, 1
    for l in lines[start:]:
        if not l:
            continue
        if stop_marker and re.search(stop_marker, l, re.I):
            break
        d = day_heading(l) if len(l) < 90 and _LINE_HEAD.match(l) else None
        if d and not _TOP.match(l):
            date = d
            if cur:
                out.append(cur)
                cur = None
            continue
        m = _TOP.match(l)
        if m and not _NOT_TOP.match(m.group(2)) and int(m.group(1)) in (expect, 1):
            n = int(m.group(1))
            if cur:
                out.append(cur)
            first = re.sub(r"\s+\d{1,3}$", "", m.group(2)).strip()
            cur = [date, str(n), [first] if first else []]
            expect = n + 1
            continue
        if cur is not None and not _NOISE.match(l) and not _CAPS.match(l):
            cur[2].append(l)
    if cur:
        out.append(cur)
    return [(d, o, " ".join(" ".join(parts).split())) for d, o, parts in out
            if " ".join(parts).strip()]


def items_from_tops(tops, body, meeting_id, url, item_time=None, lang=None, limit=None):
    out = []
    for dated, order, block in tops[:limit] if limit else tops:
        business = business_of(block)
        if not business:
            continue
        out.append(ra.item(dated, business, body, item_time=item_time, order=order,
                           meeting_id=meeting_id, detail=unname(block)[:1500],
                           reference=ref_of(block), url=url, lang=lang))
    return out


def ics_events(text):
    """[{date, time, summary, description, uid, url, location}] from an
    iCalendar file (folded lines unfolded, escapes undone)."""
    raw = re.sub(r"\r?\n[ \t]", "", text or "")
    out = []
    for block in re.findall(r"(?s)BEGIN:VEVENT(.*?)END:VEVENT", raw):
        ev = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            name = key.split(";")[0].upper()
            val = val.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").strip()
            if name == "DTSTART":
                m = re.match(r"(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?", val)
                if m:
                    ev["date"] = "{0}-{1}-{2}".format(*m.groups()[:3])
                    ev["time"] = "{0}:{1}".format(m.group(4), m.group(5)) if m.group(4) else None
            elif name in ("SUMMARY", "DESCRIPTION", "UID", "URL", "LOCATION"):
                ev[name.lower()] = val
        if ev.get("date"):
            out.append(ev)
    return out


def rss_items(text):
    out = []
    for block in re.findall(r"(?s)<item>(.*?)</item>", text or ""):
        def tag(name):
            m = re.search(r"(?s)<{0}>(.*?)</{0}>".format(name), block)
            v = m.group(1) if m else ""
            v = re.sub(r"(?s)^\s*<!\[CDATA\[(.*)\]\]>\s*$", r"\1", v)
            return v.strip()
        out.append({"title": _html.unescape(tag("title")), "link": tag("link"),
                    "description": tag("description"), "pubDate": tag("pubDate")})
    return out


def rss_date(value):
    import email.utils
    try:
        d = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None, None
    return d.date().isoformat(), d.strftime("%H:%M")


def tba(dated, body, meeting_id=None, item_time=None, url=None):
    return ra.item(dated, "", body, item_time=item_time, meeting_id=meeting_id, url=url)


def merge(items, tbas):
    """The agenda items plus the booked sittings that have none: a 'to be
    announced' row is dropped when an item already covers its date and
    body (or, for the plenary, its date)."""
    have = {(i["dated"], _norm(i["body"])) for i in items}
    plen = {i["dated"] for i in items if not ra.is_committee(i["body"])}
    out = list(items)
    seen = set()
    for t in tbas:
        k = (t["dated"], _norm(t["body"]))
        if k in have or k in seen or (not ra.is_committee(t["body"]) and t["dated"] in plen):
            continue
        seen.add(k)
        out.append(t)
    return out


def _norm(body):
    return ra.slug(body or "", 80)


def read_units(ctx, failed_dates=()):
    """The whole window when every agenda was read, else each day of the
    window except the days whose agenda failed (their rows are kept)."""
    if not failed_dates:
        return [ra.window(ctx.today, ctx.until)]
    out, d = [], ctx.today_date
    while d <= ctx.until_date:
        if d.isoformat() not in failed_dates:
            out.append(ra.day(d.isoformat()))
        d += datetime.timedelta(days=1)
    return out


def _text_lines(fragment):
    return ra.clean(fragment)


def _fetch_pdf_tops(client, url, slug, default_date):
    data = client.get_bytes(url, FEED, slug, archive=False)
    return split_tops(pdf_text(data), default_date=default_date)


# --- Nordrhein-Westfalen ------------------------------------------------------------

NW_HOST = "https://www.landtag.nrw.de"
NW_CAL = (NW_HOST + "/cms/render/live/de/sites/landtag-r20/home/aktuelles/termine-und-veranstaltungen/"
          "kalender/contentArea/")
NW_MONTH = NW_CAL + "kalender.R20.xhr?jahr={0}&monat={1}&datum=&filtern="
NW_DAY = (NW_CAL + "terminanzeige-fur-den-kalender.html.ajax?view=ajax&von_datum={0}&bis_datum={0}"
          "&filtern=")


def parse_nw_month(text):
    """{'2026-11-24': 'Plenar', ...}: the days of a month with sittings."""
    out = {}
    for m in re.finditer(r'data-datum="(\d{4})(\d{2})(\d{2})">(.*?)</a>', text or "", re.S):
        ind = re.search(r"TerminIndikator(\w+)", m.group(4))
        if ind and ind.group(1) != "Veranstaltungen":
            out["{0}-{1}-{2}".format(*m.groups()[:3])] = ind.group(1)
    return out


def parse_nw_day(text):
    """[{date, time, body, kind, to_url}] for one day of the calendar."""
    out = []
    for g in re.findall(r'(?s)<div class="e-event-group">(.*?)(?=<div class="e-event-group">|\Z)',
                        text or ""):
        tm = re.search(r'datetime="(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})"', g)
        if not tm:
            continue
        kind = ra.one_line(ra.clean(_first(r'(?s)class="e-event-timeline__subtitle">(.*?)</p>', g)))
        body = ra.one_line(ra.clean(_first(r'(?s)class="e-event-timeline__title">(.*?)</h3>', g)))
        to = re.search(r'href="(/home/der-landtag/tagesordnungen/[^"]+\.html)"', g)
        if not body or "Veranstaltung" in kind:
            continue
        out.append({"date": tm.group(1), "time": tm.group(2), "body": body, "kind": kind,
                    "to_url": NW_HOST + to.group(1) if to else None})
    return out


def _first(pattern, text):
    m = re.search(pattern, text or "")
    return m.group(1) if m else ""


def parse_nw_to(text):
    """[(order, block)] of an NRW Tagesordnung page (Word HTML: a table row
    per point, the number in the first cell)."""
    i = (text or "").find('class="WordSection1"')
    seg = text[i:] if i >= 0 else (text or "")
    out = []
    for tr in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", seg):
        tds = [ra.clean(x) for x in re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)]
        tds = [t for t in tds]
        if len(tds) < 2:
            continue
        m = re.match(r"^(\d{1,3})\.?$", tds[0].strip())
        if not m or not tds[1].strip():
            continue
        lines = [l for l in tds[1].splitlines() if not _NOISE.match(l.strip())]
        out.append((m.group(1), " ".join(" ".join(lines).split())))
    return out


def read_nw(client, ctx):
    days = {}
    d = ctx.today_date.replace(day=1)
    while d <= ctx.until_date:
        reply = client.get_text(NW_MONTH.format(d.year, d.month), FEED,
                                "nw-month-{0}-{1:02d}".format(d.year, d.month), archive=False)
        days.update(parse_nw_month(reply))
        d = (d + datetime.timedelta(days=32)).replace(day=1)
    items, tbas, gaps, failed, docs = [], [], [], set(), 0
    for day_ in sorted(x for x in days if ctx.in_window(x)):
        if ctx.out_of_time():
            failed.add(day_)
            continue
        try:
            events = parse_nw_day(client.get_text(NW_DAY.format(day_.replace("-", "")), FEED,
                                                  "nw-day-" + day_, archive=False))
        except FetchError as exc:
            gaps.append("NRW calendar day {0}: {1}".format(day_, str(exc)[:120]))
            failed.add(day_)
            continue
        for ev in events:
            body = "Plenum" if ev["body"] == "Plenum" else ev["body"]
            mid = "nw:{0}:{1}".format(ev["date"], ra.slug(body, 40))
            if ev["to_url"] and docs < MAX_DOCS:
                docs += 1
                try:
                    tops = parse_nw_to(client.get_text(ev["to_url"], FEED,
                                                       "nw-to-" + ev["to_url"].rsplit("/", 1)[-1],
                                                       archive=False))
                except FetchError as exc:
                    gaps.append("NRW agenda {0}: {1}".format(ev["to_url"], str(exc)[:120]))
                    failed.add(ev["date"])
                    continue
                got = items_from_tops([(ev["date"], o, b) for o, b in tops], body, mid,
                                      ev["to_url"], item_time=ev["time"])
                if got:
                    items += got
                    continue
            tbas.append(tba(ev["date"], body, mid, ev["time"]))
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="landtag.nrw.de Kalender + Tagesordnungen (HTML)", gaps=gaps)


# --- Bayern --------------------------------------------------------------------

BY_HOST = "https://www.bayern.landtag.de"
BY_LIST = BY_HOST + "/aktuelles/tagesordnungen/"
BY_PDF = (BY_HOST + "/webangebot3/views/tagesordnungdirektanzeige/tagesordnungdirektanzeige.xhtml"
          "?gremium={code}&sitzungsdatum={date}&sitzungsnr={nr}&nachtragsnr={nt}&typ=pdf&wp={wp}")


def parse_by_list(text):
    """[{body, code, nr, nachtrag, date}] from the Tagesordnungen page; the
    Gremium codes come from the page's own select box."""
    codes = {ra.one_line(_html.unescape(n)): v for v, n in
             re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)', text or "") if v}
    wp = _first(r"wp=(\d+)", text) or "19"
    out = []
    for g in re.findall(r'(?s)data-nodetype="gremium"(.*?)(?=data-nodetype="gremium"|\Z)', text or ""):
        name = ra.one_line(ra.clean(_first(r'(?s)<span class="ui-treenode-label[^"]*">(.*?)</span>', g)))
        code = codes.get(name)
        for m in re.finditer(r"(?:(\d+)\.\s*Nachtrags)?[Tt]agesordnung zur (\d+)\. Sitzung vom "
                             r"(\d{2})\.(\d{2})\.(\d{4})", g):
            out.append({"body": name, "code": code, "nr": m.group(2), "nachtrag": m.group(1) or "0",
                        "date": "{0}-{1}-{2}".format(m.group(5), m.group(4), m.group(3)),
                        "wp": wp})
    return out


def read_by(client, ctx):
    listing = parse_by_list(client.get_text(BY_LIST, FEED, "by-list", archive=False))
    items, gaps, failed, docs = [], [], set(), 0
    for to in sorted(listing, key=lambda x: (x["date"], x["body"], x["nachtrag"])):
        if not ctx.in_window(to["date"]) or not to["code"]:
            continue
        body = "Plenum" if to["code"] == "PL" else to["body"]
        if docs >= MAX_DOCS or ctx.out_of_time():
            failed.add(to["date"])
            continue
        docs += 1
        d, m, y = to["date"][8:], to["date"][5:7], to["date"][:4]
        url = BY_PDF.format(code=to["code"], date="{0}.{1}.{2}".format(d, m, y), nr=to["nr"],
                            nt=to["nachtrag"], wp=to["wp"])
        mid = "by:{0}:{1}:{2}".format(to["wp"], to["code"], to["nr"])
        try:
            tops = _fetch_pdf_tops(client, url, "by-{0}-{1}-{2}".format(to["code"], to["nr"],
                                                                         to["nachtrag"]), to["date"])
        except FetchError as exc:
            gaps.append("Bayern agenda {0} {1}: {2}".format(body, to["date"], str(exc)[:120]))
            failed.add(to["date"])
            continue
        got = items_from_tops(tops, body, mid, url)
        if to["nachtrag"] != "0":
            for it in got:
                it["key"] = "n{0}-{1}".format(to["nachtrag"], ra.slug(it["business"]))
        items += got or [tba(to["date"], body, mid, url=url)]
    return ra.RegionRead(items, read_units(ctx, failed),
                         source="bayern.landtag.de Tagesordnungen (PDF)", gaps=gaps,
                         note="agendas published about a week ahead; no machine-readable "
                              "calendar of later sittings")


# --- Baden-Württemberg -------------------------------------------------------

BW_HOST = "https://www.landtag-bw.de"
BW_ICS = BW_HOST + "/resource/calendar/501552/download/terminkalender.ics"
BW_TO = BW_HOST + "/de/aktuelles/tagesordnungen"


BW_BODIES = {"FinA": "Ausschuss für Finanzen"}


def bw_calendar(events):
    out = []
    for ev in events:
        s = ev.get("summary") or ""
        kind, _, rest = s.partition(":")
        rest = rest.strip()
        if kind.startswith("Plenarsitzung"):
            out.append((ev["date"], ev.get("time"), "Plenum"))
        elif kind.startswith("Fraktions- und Ausschusssitzungen") and rest and rest != "Fraktionen":
            out.append((ev["date"], ev.get("time"), BW_BODIES.get(rest, rest)))
    return out


def parse_bw_to_page(text):
    """[(url, label)] of the agenda PDFs on the Tagesordnungen page."""
    out = []
    for href, label in re.findall(r'href="(/resource/blob/[^"]+\.pdf)"[^>]*>(.*?)</a>', text or "", re.S):
        label = ra.one_line(ra.clean(label))
        if re.search(r"Willkommen", href):
            continue
        if all(BW_HOST + href != u for u, _ in out):
            out.append((BW_HOST + href, label))
    return out


def bw_body(label, text):
    if re.search(r"Plenarsitzung", label) or re.search(r"Sitzung\s+des\s+Landtags", text[:800]):
        return "Plenum"
    m = re.search(r"(?m)^\s*((?:Ausschuss|Untersuchungsausschuss|Enquetekommission)\b[^\n]{3,100}|"
                  r"[^\n]{0,40}(?:ausschuss|[Kk]ommission)[^\n]{0,60})\s*$", text[:2000])
    return ra.one_line(m.group(1)) if m else label


def read_bw(client, ctx):
    gaps, failed, items, tbas, docs = [], set(), [], [], 0
    for dated, tm, body in bw_calendar(ics_events(client.get_text(BW_ICS, FEED, "bw-ics",
                                                                  archive=False))):
        if ctx.in_window(dated):
            tbas.append(tba(dated, body, "bw:{0}:{1}".format(dated, ra.slug(body, 30)), tm))
    try:
        pdfs = parse_bw_to_page(client.get_text(BW_TO, FEED, "bw-to", archive=False))
    except FetchError as exc:
        pdfs = []
        gaps.append("Baden-Württemberg Tagesordnungen page: {0}".format(str(exc)[:120]))
        failed.update(t["dated"] for t in tbas)
    for url, label in pdfs:
        if docs >= MAX_DOCS:
            break
        docs += 1
        guess = ra.find_date(label.replace("_", " ")) or ra.find_date(url.rsplit("/", 1)[-1])
        try:
            text = pdf_text(client.get_bytes(url, FEED, "bw-" + ra.slug(label, 40), archive=False))
        except FetchError as exc:
            gaps.append("Baden-Württemberg agenda {0}: {1}".format(label, str(exc)[:120]))
            if guess:
                failed.add(guess)
            continue
        tops = split_tops(text, default_date=guess)
        body = bw_body(label, text)
        dates = sorted({d for d, _, _ in tops if d})
        mid = "bw:{0}:{1}".format(dates[0] if dates else guess, ra.slug(body, 30))
        items += [i for i in items_from_tops(tops, body, mid, url) if ctx.in_window(i["dated"])]
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="landtag-bw.de terminkalender.ics + Tagesordnungen (PDF)", gaps=gaps)


# --- Niedersachsen -----------------------------------------------------------

NI_HOST = "https://www.landtag-niedersachsen.de"
NI_ICS = NI_HOST + "/fileadmin/calendar_abo/jahrestermine-{0}.ics"
NI_RSS_PL = NI_HOST + "/rss/tagesordnungen_plenarsitzungen.xml"
NI_RSS_A = NI_HOST + "/rss/tagesordnungen_ausschuesse.xml"
NI_BODIES = {
    "26. PUA": "26. Parlamentarischer Untersuchungsausschuss",
    "AArt55": "Ausschuss zur Vorbereitung der Wahl der Mitglieder des Staatsgerichtshofs",
    "AfBuEuR": "Ausschuss für Bundes- und Europaangelegenheiten und Regionale Entwicklung",
    "AfELuV": "Ausschuss für Ernährung, Landwirtschaft und Verbraucherschutz",
    "AfHuF": "Ausschuss für Haushalt und Finanzen",
    "AfIuS": "Ausschuss für Inneres und Sport",
    "AfRuV": "Ausschuss für Rechts- und Verfassungsfragen",
    "AfSAGuG": "Ausschuss für Soziales, Arbeit, Gesundheit und Gleichstellung",
    "AfUEuK": "Ausschuss für Umwelt, Energie und Klimaschutz",
    "AfWuK": "Ausschuss für Wissenschaft und Kultur",
    "AfWVBuD": "Ausschuss für Wirtschaft, Verkehr, Bauen und Digitalisierung",
    "KultA": "Kultusausschuss",
    "MiguTeilhK": "Kommission zu Fragen der Migration und Teilhabe",
    "PetA": "Petitionsausschuss",
    "Plenum": "Plenum",
    "UAHuSch": 'Unterausschuss "Häfen und Schifffahrt"',
    "UAJustV": 'Unterausschuss "Justizvollzug und Straffälligenhilfe"',
    "UAMedien": 'Unterausschuss "Medien"',
    "UAPrüfHR": 'Unterausschuss "Prüfung der Haushaltsrechnungen"',
    "UATourismus": 'Unterausschuss "Tourismus"',
    "UAVerbrSch": 'Unterausschuss "Verbraucherschutz"',
}
NI_SKIP = re.compile(r"ÄltR|Ältestenrat|Präsidium")


def read_ni(client, ctx):
    gaps, failed, items, tbas, docs = [], set(), [], [], 0
    for year in sorted({ctx.today[:4], ctx.until[:4]}):
        try:
            events = ics_events(client.get_text(NI_ICS.format(year), FEED, "ni-ics-" + year,
                                                archive=False))
        except FetchError as exc:
            if year == ctx.today[:4]:
                raise
            gaps.append("Niedersachsen calendar {0}: {1}".format(year, str(exc)[:100]))
            continue
        for ev in events:
            s = (ev.get("summary") or "").strip()
            if not ctx.in_window(ev["date"]) or NI_SKIP.search(s) or not s:
                continue
            body = NI_BODIES.get(s, s)
            tbas.append(tba(ev["date"], body, "ni:{0}:{1}".format(ev["date"], ra.slug(body, 30)),
                            ev.get("time")))
    for feed_url, slug, plenary in ((NI_RSS_PL, "ni-rss-pl", True), (NI_RSS_A, "ni-rss-a", False)):
        try:
            entries = rss_items(client.get_text(feed_url, FEED, slug, archive=False))
        except FetchError as exc:
            gaps.append("Niedersachsen agenda feed {0}: {1}".format(slug, str(exc)[:100]))
            failed.update(t["dated"] for t in tbas if ra.is_committee(t["body"]) != plenary)
            continue
        for e in entries:
            link = e["link"]
            when = ra.find_date(link.rsplit("/", 1)[-1].replace("_", " ")) or ra.find_date(e["title"])
            if plenary:
                when = ra.find_date(re.sub(r"(\d{1,2})\. (?:und|bis) \d{1,2}\.", r"\1.", e["title"]))
            if not when or not (ctx.today <= when <= ctx.until) or docs >= MAX_DOCS:
                continue
            docs += 1
            body = "Plenum" if plenary else e["title"]
            try:
                tops = _fetch_pdf_tops(client, link, "ni-" + ra.slug(link.rsplit("/", 1)[-1], 50), when)
            except FetchError as exc:
                gaps.append("Niedersachsen agenda {0}: {1}".format(link, str(exc)[:100]))
                failed.add(when)
                continue
            mid = "ni:{0}:{1}".format(when, ra.slug(body, 30))
            items += [i for i in items_from_tops(tops, body, mid, link) if ctx.in_window(i["dated"])]
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="landtag-niedersachsen.de jahrestermine.ics + Tagesordnungen RSS (PDF)",
                         gaps=gaps)


# --- Hessen ------------------------------------------------------------------

HE_HOST = "https://hessischer-landtag.de"
HE_LISTS = (("plenarsitzungen-7", True), ("ausschusssitzungen-10", False))
HE_LIST = HE_HOST + "/termine/veranstaltungs_kategorie/{0}?page={1}"


def parse_he_list(text):
    """[(date, title, path, time)] of one page of a Termine category list:
    each teaser links its Termin page, carries the sitting's datetime, the
    committee (field-group-ref) and a title."""
    out = []
    for m in re.finditer(r'(?s)<article[^>]*node--type-event[^>]*>.*?<a href="(/termine/[a-z0-9-]+)"(.*?)</article>',
                         text or ""):
        path, blk = m.group(1), m.group(2)
        dated = _first(r'datetime="(\d{4}-\d{2}-\d{2})T', blk)
        if not dated:
            prev = text[:m.start()]
            ds = re.findall(r'datetime="(\d{4}-\d{2}-\d{2})T', prev)
            dated = ds[-1] if ds else None
        tm = _first(r'class="datetime">(\d{1,2}:\d{2}) Uhr<', blk) or None
        group = ra.one_line(ra.clean(_first(r'(?s)field--name-field-group-ref.*?field__item">(.*?)</div>', blk)))
        title = ra.one_line(ra.clean(_first(r'(?s)field--name-field-teaser-title[^>]*>(.*?)</div>', blk)))
        if dated:
            out.append((dated, group or title, path, tm))
    return out


def parse_he_termin(text):
    """[(order, block)] of the 'Tagesordnung' on one Termin page."""
    t = ra.clean(text or "")
    i = t.find("\nTagesordnung\n")
    if i < 0:
        return []
    seg = t[i + 14:]
    for stop in ("\nDownloads", "\nFraktionen\n", "\nKalender\n"):
        j = seg.find(stop)
        if j >= 0:
            seg = seg[:j]
    return [(o, b) for _, o, b in split_tops(seg, start_marker=None)]


def read_he(client, ctx):
    gaps, failed, items, tbas, docs = [], set(), [], [], 0
    rows = []
    for cat, plenary in HE_LISTS:
        for page in range(0, 12):
            got = parse_he_list(client.get_text(HE_LIST.format(cat, page), FEED,
                                                "he-{0}-{1}".format(cat[:5], page), archive=False))
            rows += [(d, t, p, tm, plenary) for d, t, p, tm in got]
            if not got or max(r[0] for r in got) > ctx.until:
                break
    near = (ctx.today_date + datetime.timedelta(days=DETAIL_DAYS)).isoformat()
    for dated, title, path, tm, plenary in rows:
        if not ctx.in_window(dated):
            continue
        body = "Plenum" if plenary else re.sub(r"\s*-\s*\d+\.\s*Sitzung$", "", title)
        mid = "he:" + path.rsplit("/", 1)[-1]
        if dated <= near and docs < MAX_DOCS and not ctx.out_of_time():
            docs += 1
            try:
                tops = parse_he_termin(client.get_text(HE_HOST + path, FEED, "he-" + mid[3:50],
                                                       archive=False))
            except FetchError as exc:
                gaps.append("Hessen Termin {0}: {1}".format(path, str(exc)[:100]))
                failed.add(dated)
                continue
            got = items_from_tops([(dated, o, b) for o, b in tops], body, mid, HE_HOST + path,
                                  item_time=tm)
            if got:
                items += got
                continue
        tbas.append(tba(dated, body, mid, tm, url=HE_HOST + path))
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="hessischer-landtag.de Termine (HTML)", gaps=gaps,
                         note="agenda pages read for sittings within {0} days".format(DETAIL_DAYS))


# --- Sachsen -------------------------------------------------------------------

SN_HOST = "https://www.landtag.sachsen.de"
SN_LISTS = (("/de/aktuelles/plenarsitzungen/index.cshtml", True),
            ("/de/aktuelles/ausschusssitzungen/index.cshtml", False))


def parse_sn_list(text, plenary):
    """[(date, body, sitzung_id)]: every sitting on a Sachsen list page."""
    out = []
    body = "Plenum"
    for m in re.finditer(r'(?s)<h2 class="xm_agenda">(.*?)</h2>|xm_agenda__title">(.*?)</h3>\s*'
                         r'<div class="xm_agenda__subtitle">(.*?)</div>(.*?)(?=xm_agenda__title|'
                         r'<h2 class="xm_agenda">|\Z)', text or ""):
        if m.group(1) is not None:
            body = "Plenum" if plenary else ra.one_line(ra.clean(m.group(1)))
            continue
        dated = ra.find_date(ra.clean(m.group(3)))
        sid = _first(r"sitzungskalender/sitzung/(\d+)", m.group(4))
        if dated:
            out.append((dated, body, sid))
    return out


def read_sn(client, ctx):
    tbas = []
    for path, plenary in SN_LISTS:
        for dated, body, sid in parse_sn_list(client.get_text(SN_HOST + path, FEED,
                                                              "sn-" + ("pl" if plenary else "a"),
                                                              archive=False), plenary):
            if ctx.in_window(dated):
                tbas.append(tba(dated, body, "sn:" + (sid or "{0}:{1}".format(dated, ra.slug(body, 30)))))
    return ra.RegionRead(merge([], tbas), [ra.window(ctx.today, ctx.until)],
                         source="landtag.sachsen.de Plenar-/Ausschusssitzungen (HTML lists)",
                         note="sittings only: the agendas sit under /de/aktuelles/sitzungskalender/, "
                              "which robots.txt disallows, and EDAS disallows every robot")


# --- Berlin ------------------------------------------------------------------

BE_HOST = "https://www.parlament-berlin.de"
BE_ICS = BE_HOST + "/termine/ical/{0}"


def read_be(client, ctx):
    tbas = []
    for cal, plenary in (("appointmentsOfPlenar", True), ("appointmentsOfCommittees", False)):
        for ev in ics_events(client.get_text(BE_ICS.format(cal), FEED, "be-" + cal[14:], archive=False)):
            if not ctx.in_window(ev["date"]):
                continue
            s = ev.get("summary") or ""
            if plenary and "Plenar" not in s:
                continue
            body = "Plenum" if plenary else s
            nr = _first(r"Sitzungs-Nr\.\s*(\d+)", ev.get("description") or "")
            tbas.append(tba(ev["date"], body, "be:{0}:{1}:{2}".format(ev["date"], ra.slug(body, 30), nr),
                            ev.get("time")))
    return ra.RegionRead(merge([], tbas), [ra.window(ctx.today, ctx.until)],
                         source="parlament-berlin.de termine/ical (Plenar + Ausschüsse)",
                         note="sittings only: the agendas (Einladungen) are loaded by a JavaScript "
                              "app whose data service is not documented")


# --- Brandenburg --------------------------------------------------------------

BB_HOST = "https://www.landtag.brandenburg.de"
BB_RSS = ((BB_HOST + "/cms/detail.php?template=lt_rss_tagesordnung_d", True),
          (BB_HOST + "/cms/detail.php?template=lt_rss_tagesordnung_ausschuss_d", False))


def bb_body(title, plenary):
    if plenary:
        return "Plenum"
    t = re.sub(r"^\d+\.\s*(?:\((?:nicht )?öffentliche\)\s*)?", "", title)
    t = re.sub(r"^Sitzung (?:des|der)\s+", "", t)
    return ra.one_line(t)


def parse_bb_detail(text):
    t = ra.clean(text or "")
    i = t.find("Tagesordnung")
    if i < 0:
        return []
    return [(o, b) for _, o, b in split_tops(t[i:], start_marker=r"Tagesordnung",
                                              stop_marker=r"^Terminkalender")]


def read_bb(client, ctx):
    gaps, failed, items, tbas, docs = [], set(), [], [], 0
    for url, plenary in BB_RSS:
        for e in rss_items(client.get_text(url, FEED, "bb-rss-" + ("pl" if plenary else "a"),
                                           archive=False)):
            dated, tm = rss_date(e["pubDate"])
            if not dated or not ctx.in_window(dated):
                continue
            body = bb_body(e["title"], plenary)
            mid = "bb:" + (_first(r"\.c\.(\d+)", e["link"]) or dated)
            has_to = len(re.sub(r"\.\.\.$", "", ra.clean(e["description"])).strip()) > 3
            if has_to and docs < MAX_DOCS and not ctx.out_of_time():
                docs += 1
                try:
                    tops = parse_bb_detail(client.get_text(e["link"], FEED, mid.replace(":", "-"),
                                                           archive=False))
                except FetchError as exc:
                    gaps.append("Brandenburg Termin {0}: {1}".format(e["link"], str(exc)[:100]))
                    failed.add(dated)
                    continue
                got = items_from_tops([(dated, o, b) for o, b in tops], body, mid, e["link"],
                                      item_time=tm)
                if got:
                    items += got
                    continue
            tbas.append(tba(dated, body, mid, tm, url=e["link"]))
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="landtag.brandenburg.de Termine RSS + Termin pages (HTML)", gaps=gaps)


# --- Bremen ------------------------------------------------------------------

HB_SD = "https://sd.bremische-buergerschaft.de"
HB_ICS = HB_SD + "/termine/ics/SD.NET_RIM.ics"
HB_SKIP = re.compile(r"Städtische|Stadtbürgerschaft|\(Stadt\)|Vorstand|Interfraktionelle|Beirat", re.I)


def parse_hb_tops(text):
    """[(order, block)] of an SD.NET Tagesordnung (the 'tops' page)."""
    out = []
    for tr in re.findall(r'(?s)<tr class="[^"]*top-[a-z]+-data[^"]*"[^>]*>(.*?)</tr>', text or ""):
        nr = ra.one_line(ra.clean(_first(r'(?s)<td class="column-topnrtext">(.*?)</td>', tr)))
        what = ra.one_line(ra.clean(_first(r'(?s)<td class="column-bezeichnung">(.*?)</td>', tr)))
        num = ra.one_line(ra.clean(_first(r'(?s)<td class="column-nummer">(.*?)</td>', tr)))
        if what:
            out.append((nr.rstrip(".") or None, what + (" (Drs. {0})".format(num)
                                                        if re.match(r"\d+/\d+", num) else "")))
    return out


def read_hb(client, ctx):
    gaps, failed, items, tbas, docs = [], set(), [], [], 0
    near = (ctx.today_date + datetime.timedelta(days=DETAIL_DAYS)).isoformat()
    for ev in ics_events(client.get_text(HB_ICS, FEED, "hb-ics", archive=False)):
        s = (ev.get("summary") or "").strip()
        if not ctx.in_window(ev["date"]) or not s or HB_SKIP.search(s):
            continue
        body = "Plenum" if "Bürgerschaft (Landtag)" in s else s
        url = _first(r"(https://sd\.bremische-buergerschaft\.de/tops/\?__=[\w-]+)",
                     ev.get("description") or "")
        mid = "hb:" + (ev.get("uid") or "{0}:{1}".format(ev["date"], ra.slug(body, 30)))
        if url and ev["date"] <= near and docs < MAX_DOCS and not ctx.out_of_time():
            docs += 1
            try:
                tops = parse_hb_tops(client.get_text(url, FEED, "hb-tops-" + mid[3:], archive=False))
            except FetchError as exc:
                gaps.append("Bremen agenda {0}: {1}".format(s, str(exc)[:100]))
                failed.add(ev["date"])
                continue
            got = items_from_tops([(ev["date"], o, b) for o, b in tops], body, mid, url,
                                  item_time=ev.get("time"))
            if got:
                items += got
                continue
        tbas.append(tba(ev["date"], body, mid, ev.get("time"), url=url or None))
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="sd.bremische-buergerschaft.de (SD.NET) ics + tops (HTML)", gaps=gaps,
                         note="Land bodies only (Landtag, Land committees, staatliche Deputationen); "
                              "agendas read for sittings within {0} days".format(DETAIL_DAYS))


# --- Hamburg -------------------------------------------------------------------

HH_HOST = "https://www.hamburgische-buergerschaft.de"
HH_SEARCH = HH_HOST + "/aktuelles/termine/1042880!search?hitsPerPage={0}&state={1}"


def hh_state(hits):
    """The listing's own state parameter (gzip+base64 JSON, sorted by date)."""
    raw = json.dumps({"dateFrom": None, "dateTo": None, "facets": {}, "hitsPerPage": hits,
                      "query": "", "sort": "externallydisplayeddate asc",
                      "useDateConstraint": False}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(gzip.compress(raw, mtime=0)).decode().rstrip("=")


def parse_hh_list(text, today):
    """[{date, body, kind, time, to_url, id}] from the Termine listing; the
    teaser prints day and month only, so the year is the next one on or
    after today's month."""
    out = []
    t0 = datetime.date.fromisoformat(today)
    for blk in re.findall(r'(?s)<div class="bkhh-teaser bkhh-teaser--events"\s*>(.*?)'
                          r'(?=<div class="bkhh-teaser bkhh-teaser--events"|</ul>)', text or ""):
        dm = re.search(r'aria-label="(\d{2})\. (\w+)"', blk)
        if not dm:
            continue
        mon = ra.month(dm.group(2))
        if not mon:
            continue
        year = t0.year + (1 if mon < t0.month - 1 else 0)
        dated = ra.iso(dm.group(1), mon, year)
        body = ra.one_line(ra.clean(_first(r'teaser__headline-inner">(.*?)</span>', blk)))
        kind = ra.one_line(ra.clean(_first(r'(?s)bkhh-teaser__text"\s*>(.*?)</p>', blk)))
        tm = _first(r'bkhh-icon-label__label">(\d{1,2}:\d{2})</span>', blk) or None
        to = re.search(r'href="(/resource/blob/[^"]+\.pdf)"[^>]*>\s*<span class="bkhh-link__text">'
                       r'Tagesordnung', blk)
        eid = _first(r"/termine/(\d+)!ical", blk)
        out.append({"date": dated, "body": body, "kind": kind, "time": tm, "id": eid,
                    "to_url": HH_HOST + to.group(1) if to else None})
    return out


def read_hh(client, ctx):
    gaps, failed, items, tbas, docs = [], set(), [], [], 0
    rows = parse_hh_list(client.get_text(HH_SEARCH.format(100, hh_state(100)), FEED, "hh-list",
                                         archive=False), ctx.today)
    for r in rows:
        if not r["date"] or not ctx.in_window(r["date"]):
            continue
        if re.search(r"entf[äa]llt|nicht öffentlich", r["kind"], re.I):
            continue
        if not re.search(r"Ausschuss|Bürgerschaft|Kommission", r["kind"] + " " + r["body"]):
            continue
        body = "Plenum" if r["body"].startswith("Bürgerschaftssitzung") else r["body"]
        mid = "hh:" + (r["id"] or "{0}:{1}".format(r["date"], ra.slug(body, 30)))
        if r["to_url"] and docs < MAX_DOCS:
            docs += 1
            try:
                tops = _fetch_pdf_tops(client, r["to_url"], "hh-" + mid[3:], r["date"])
            except FetchError as exc:
                gaps.append("Hamburg agenda {0} {1}: {2}".format(body, r["date"], str(exc)[:100]))
                failed.add(r["date"])
                continue
            got = items_from_tops([(r["date"], o, b) for _, o, b in tops], body, mid, r["to_url"],
                                  item_time=r["time"])
            if got:
                items += got
                continue
        tbas.append(tba(r["date"], body, mid, r["time"], url=r["to_url"]))
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="hamburgische-buergerschaft.de Termine (HTML) + Tagesordnungen (PDF)",
                         gaps=gaps, note="public sittings only")


# --- Mecklenburg-Vorpommern ------------------------------------------------------

MV_HOST = "https://www.landtag-mv.de"
MV_WEEK = MV_HOST + "/plenum-und-ausschuesse/plenum/aktuelle-plenarwoche"


def read_mv(client, ctx):
    text = client.get_text(MV_WEEK, FEED, "mv-week", archive=False)
    links = sorted(set(re.findall(r'href="(/fileadmin/[^"]*/Tagesordnung/[^"]+\.pdf)"', text)))
    gaps, failed, items = [], set(), []
    for href in links[:MAX_DOCS]:
        url = MV_HOST + href
        try:
            tops = _fetch_pdf_tops(client, url, "mv-" + ra.slug(href.rsplit("/", 1)[-1], 40), None)
        except FetchError as exc:
            gaps.append("Mecklenburg-Vorpommern agenda {0}: {1}".format(href, str(exc)[:100]))
            continue
        dates = sorted({d for d, _, _ in tops if d})
        mid = "mv:" + ra.slug(href.rsplit("/", 1)[-1], 50)
        items += [i for i in items_from_tops(tops, "Plenum", mid, url) if ctx.in_window(i["dated"])]
        if not dates:
            gaps.append("Mecklenburg-Vorpommern agenda {0}: no sitting date found".format(href))
    units = [ra.window(ctx.today, ctx.until)] if not gaps else \
        [ra.meeting(i["meeting_id"]) for i in items]
    return ra.RegionRead(items, units, source="landtag-mv.de Aktuelle Plenarwoche (PDF)", gaps=gaps,
                         note="the current plenary week's agenda only; committee dates are not "
                              "published in a readable calendar")


# --- Rheinland-Pfalz -----------------------------------------------------------

try:
    from zoneinfo import ZoneInfo
    BERLIN = ZoneInfo("Europe/Berlin")
except Exception:                                     # pragma: no cover - no tz database
    BERLIN = datetime.timezone(datetime.timedelta(hours=1))

RP_API = "https://api.landtag-rlp.de/api/meeting/filteredList?from={0}&to={1}&useOR=true&sortOrder=asc&amount=10000"


def _ms(iso_date, end=False):
    d = datetime.datetime.fromisoformat(iso_date + ("T23:59:59" if end else "T00:00:00"))
    return int(d.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)


def parse_rp(reply):
    """[{date, time, body, private, agenda_url, id}] from the meeting API."""
    out = []
    for x in (reply or {}).get("content") or []:
        topics = " ".join(t.get("name", "") for t in x.get("topics") or [])
        if not re.search(r"Plenum|Ausschüsse", topics):
            continue
        start = x.get("eventStart") or ""
        try:
            local = datetime.datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(BERLIN)
        except ValueError:
            continue
        body = "Plenum" if "Plenum" in topics else (x.get("subheadline") or x.get("headline") or "")
        link = re.search(r'href="(https://dokumente\.landtag\.rlp\.de/[^"]+\.pdf)"', x.get("content") or "")
        out.append({"date": local.date().isoformat(), "time": local.strftime("%H:%M"), "body": body,
                    "private": bool(x.get("isPrivate")), "agenda_url": link.group(1) if link else None,
                    "id": x.get("urlKey")})
    return out


def read_rp(client, ctx):
    rows = parse_rp(client.get_json(RP_API.format(_ms(ctx.today), _ms(ctx.until, True)), FEED,
                                    "rp-meetings", archive=False))
    gaps, failed, items, tbas, docs = [], set(), [], [], 0
    for r in rows:
        if not ctx.in_window(r["date"]) or r["body"] in ("Ältestenrat",):
            continue
        mid = "rp:" + (r["id"] or r["date"])
        if r["agenda_url"] and not r["private"] and docs < MAX_DOCS:
            docs += 1
            try:
                tops = _fetch_pdf_tops(client, r["agenda_url"], "rp-" + mid[3:], r["date"])
                got = items_from_tops([(r["date"], o, b) for _, o, b in tops], r["body"], mid,
                                      r["agenda_url"], item_time=r["time"])
                if got:
                    items += got
                    continue
            except FetchError as exc:
                gaps.append("Rheinland-Pfalz agenda {0} {1}: {2}".format(r["body"], r["date"],
                                                                         str(exc)[:120]))
        tbas.append(tba(r["date"], r["body"], mid, r["time"], url=r["agenda_url"]))
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="api.landtag-rlp.de meeting/filteredList (JSON) + Einladungen (PDF)",
                         gaps=gaps)


# --- Sachsen-Anhalt ---------------------------------------------------------------

ST_HOST = "https://www.landtag.sachsen-anhalt.de"
ST_DATES = ST_HOST + "/service/terminuebersichten"


def parse_st_dates(text):
    """Every plenary day in 'Landtagssitzungstermine' ('18./19.11.2026',
    '24./25./26.06.2026', '06.10.2026')."""
    t = ra.clean(text or "")
    i = t.find("Landtagssitzungstermine")
    seg = t[i:i + 1500] if i >= 0 else ""
    out = []
    for m in re.finditer(r"((?:\d{1,2}\./)*\d{1,2})\.(\d{1,2})\.(\d{4})", seg):
        for dd in m.group(1).split("./"):
            d = ra.iso(dd.strip("."), m.group(2), m.group(3))
            if d:
                out.append(d)
    return sorted(set(out))


def read_st(client, ctx):
    tbas = [tba(d, "Plenum", "st:" + d) for d in parse_st_dates(
        client.get_text(ST_DATES, FEED, "st-dates", archive=False)) if ctx.in_window(d)]
    return ra.RegionRead(tbas, [ra.window(ctx.today, ctx.until)],
                         source="landtag.sachsen-anhalt.de Terminübersichten (HTML)",
                         note="plenary dates only: agendas are PDFs announced in news articles, "
                              "committees only in weekly PDF overviews")


# --- Schleswig-Holstein ------------------------------------------------------------

SH_HOST = "https://www.landtag.ltsh.de"
SH_CAL = (SH_HOST + "/system/modules/de.planetic.opencms.contentelements.kalender/templates/"
          "dayMonthKalenderGetter.jsp?locale=de")
SH_TO = SH_HOST + "/infothek/wahl20/plenum/tagesordnung_seite/"


def parse_sh_cal(reply):
    """[(date, time, body, path)] of plenary and committee entries."""
    labels = (reply or {}).get("categoryLabels") or {}
    out = []
    for x in (reply or {}).get("items") or []:
        cat = x.get("kategorie") or ""
        title = x.get("title") or ""
        if "/kalender-kategorien/11/" in cat or "/kalender-kategorien/plenarsitzung/" in cat or \
                cat.endswith("/kalender-kategorien/2/") or (not cat and title.startswith("Sitzung ")):
            try:
                dt = datetime.datetime.fromtimestamp(int(x.get("startdatum")) / 1000, tz=BERLIN)
            except (TypeError, ValueError):
                continue
            plenary = "/11/" not in cat and not title.startswith("Sitzung ")
            body = "Plenum" if plenary else re.sub(r"^Sitzung\s+(?:des|der)?\s*", "", title)
            if not plenary and "/11/" in cat and labels.get(cat):
                body = labels[cat] if labels[cat] != "Ausschüsse" else body
            out.append((dt.date().isoformat(), dt.strftime("%H:%M"), body, x.get("detailansicht")))
    return out


def parse_sh_to_list(text):
    """[(tagung, date, pdf_url)] from the plenary Tagesordnung page."""
    out = []
    for m in re.finditer(r'(?s)<div class="meeting">(\d+)</div>\s*<div class="date_daily">\s*([^<]+?)\s*</div>'
                         r'.*?href="([^"]+\.pdf)"', text or ""):
        d = ra.find_date(m.group(2))
        if d:
            out.append((m.group(1), d, urljoin(SH_HOST, m.group(3))))
    return out


def read_sh(client, ctx):
    gaps, failed, items, tbas = [], set(), [], []
    for dated, tm, body, path in parse_sh_cal(client.get_json(SH_CAL, FEED, "sh-cal", archive=False)):
        if ctx.in_window(dated):
            tbas.append(tba(dated, body, "sh:{0}:{1}".format(dated, ra.slug(body, 30)), tm,
                            url=urljoin(SH_HOST, path) if path else None))
    try:
        tos = parse_sh_to_list(client.get_text(SH_TO, FEED, "sh-to", archive=False))
    except FetchError as exc:
        tos = []
        gaps.append("Schleswig-Holstein Tagesordnungen page: {0}".format(str(exc)[:100]))
    for tagung, dated, url in tos[:6]:
        if not (ctx.today <= dated <= ctx.until):
            continue
        try:
            tops = _fetch_pdf_tops(client, url, "sh-to-" + tagung, dated)
        except FetchError as exc:
            gaps.append("Schleswig-Holstein agenda Tagung {0}: {1}".format(tagung, str(exc)[:100]))
            failed.add(dated)
            continue
        items += [i for i in items_from_tops(tops, "Plenum", "sh:tagung:" + tagung, url)
                  if ctx.in_window(i["dated"])]
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="landtag.ltsh.de Kalender (JSON) + Tagesordnungen (PDF)", gaps=gaps,
                         note="committee sittings as dates only (their agendas are not linked)")


# --- Thüringen -------------------------------------------------------------------

TH_HOST = "https://www.thueringer-landtag.de"
TH_ICS = TH_HOST + "/fileadmin/calendar_abo/Thueringer-Landtag-Terminkalender.ics"
TH_DATES = TH_HOST + "/plenum/sitzungstermine/"
TH_BODY = re.compile(r"Plenarsitzung|Ausschuss|Kommission|Enquete|PetA|Untersuchungsausschuss", re.I)


def parse_th_invitations(text):
    """[(first_date, pdf_url, label)] of the plenary invitations listed."""
    out = []
    for m in re.finditer(r'(?s)<a[^>]+href="(/uploads/tx_tltcalendar/invitations/[^"]+\.pdf)"[^>]*>(.*?)</a>',
                         text or ""):
        label = ra.one_line(ra.clean(m.group(2)))
        dates = [ra.find_date(x) for x in re.findall(r"\d{1,2}\.\d{1,2}\.\d{4}", label)]
        d = dates[0] if dates else None
        # "vom 07.10. bis 09.10.2026": the first day takes the year of the last
        mm = re.search(r"vom (\d{1,2})\.(\d{1,2})\. bis \d{1,2}\.\d{1,2}\.(\d{4})", label)
        if mm:
            d = ra.iso(mm.group(1), mm.group(2), mm.group(3))
        if d:
            out.append((d, urljoin(TH_HOST, m.group(1)), label))
    return out


def read_th(client, ctx):
    gaps, failed, items, tbas = [], set(), [], []
    for ev in ics_events(client.get_text(TH_ICS, FEED, "th-ics", archive=False)):
        s = (ev.get("summary") or "").strip()
        if not ctx.in_window(ev["date"]) or not TH_BODY.search(s):
            continue
        body = "Plenum" if s.startswith("Plenarsitzung") else re.sub(r"\s*\(außerplanmäßig\)", "", s)
        body = "Petitionsausschuss" if body == "PetA" else body
        tbas.append(tba(ev["date"], body, "th:{0}:{1}".format(ev["date"], ra.slug(body, 30)), ev.get("time")))
    try:
        invites = parse_th_invitations(client.get_text(TH_DATES, FEED, "th-dates", archive=False))
    except FetchError as exc:
        invites = []
        gaps.append("Thüringen Sitzungstermine page: {0}".format(str(exc)[:100]))
    for first, url, label in invites[:6]:
        if not (ctx.today <= first <= ctx.until):
            continue
        try:
            tops = _fetch_pdf_tops(client, url, "th-" + ra.slug(url.rsplit("/", 1)[-1], 30), first)
        except FetchError as exc:
            gaps.append("Thüringen invitation {0}: {1}".format(label[:60], str(exc)[:100]))
            failed.add(first)
            continue
        items += items_from_tops([(first, o, b) for _, o, b in tops], "Plenum",
                                 "th:pl:" + first, url)
    return ra.RegionRead(merge(items, tbas), read_units(ctx, failed),
                         source="thueringer-landtag.de Terminkalender.ics + Einladungen (PDF)", gaps=gaps)


# --- the regions ---------------------------------------------------------------------

REGIONS = {
    "BW": ra.region("Baden-Württemberg", reader=read_bw),
    "BY": ra.region("Bayern", reader=read_by),
    "BE": ra.region("Berlin", reader=read_be),
    "BB": ra.region("Brandenburg", reader=read_bb),
    "HB": ra.region("Bremen", reader=read_hb),
    "HH": ra.region("Hamburg", reader=read_hh),
    "HE": ra.region("Hessen", reader=read_he),
    "MV": ra.region("Mecklenburg-Vorpommern", reader=read_mv),
    "NI": ra.region("Niedersachsen", reader=read_ni),
    "NW": ra.region("Nordrhein-Westfalen", reader=read_nw),
    "RP": ra.region("Rheinland-Pfalz", reader=read_rp),
    "SL": ra.region("Saarland", status="no-route",
                    note="www.landtag-saar.de did not answer at all from here on 16 October 2026 "
                         "(robots.txt and every page timed out, three tries); no other official "
                         "host publishes the Landtag's calendar or agendas"),
    "SN": ra.region("Sachsen", reader=read_sn),
    "ST": ra.region("Sachsen-Anhalt", reader=read_st),
    "SH": ra.region("Schleswig-Holstein", reader=read_sh),
    "TH": ra.region("Thüringen", reader=read_th),
}
