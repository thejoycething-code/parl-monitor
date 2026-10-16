"""Austria: the Landtage's forward business (regional_agenda, 16 October 2026).

Nine Land parliaments and Vienna's Gemeinderat (the pseudo-Land 'wien-gr'
of src/atl_store.py: the same codes as tools/at_landtage.py, so the edition
can join). No two Landtage share a platform (docs/austria-regions-scope.md),
so each has its own small reader; every route was probed live on 16 October
2026 with robots.txt read first (docs/austria-regions-scope.md, "Forward
agenda").

  wien     the sitting dates (www.wien.gv.at/politik/rathaus-sitzungstermine,
           Landtag list) and INFODAT's documents assigned to those sittings
           (committees=L, a sitting-day window): motions, bills, Aktuelle
           Stunde. Written answers, which are only tabled at a sitting, are
           left out. A sitting with nothing assigned yet is 'to be announced'.
  wien-gr  the same for the Gemeinderat (committees=G, the Gemeinderat list).
  noe      the TYPO3 site: /sitzungen lists the next sitting days and each
           day's page /sitzungen/XX/<date> carries the Tagesordnung once
           published (about a week ahead; 404 before that).
  ooe      the published sitting dates (60566.htm). The Tagesordnung is
           published shortly before each sitting on landtag.ooe.gv.at,
           whose certificate does not verify: never fetched, so every
           sitting is 'to be announced'.
  stmk     PALLAST's own JSON of the next meetings (plenary sittings and
           committee days) and, for each meeting whose invitation is out,
           its meeting page with the Tagesordnung (plenary) or each
           committee's agenda (committee day).
  sbg      the Landtag's published calendar (Haussitzungen and
           Ausschusssitzungen). LPI, where the documents live, answered 503
           to robots.txt: sitting dates only.
  tir      www.tirol.gv.at's sitting pages: the next plenary sitting and the
           next committee days (lte.tirol.gv.at, the materials, disallows
           every robot).
  vbg      the Landtag's agenda page (vorarlberg.at/web/landtag/tagesordnungen):
           the next sitting and committee days; the agenda itself is posted
           the Thursday before and is not parsed yet (no live example).
  bgld     the year's sitting calendar (Landtag and committees) and the
           Tagesordnungen index: a sitting whose agenda page is listed is read
           item by item.
  ktn      blocked: www.ktn.gv.at disallows every robot but Google and Bing.
"""

from __future__ import annotations

import datetime
import re
import urllib.parse

from src import regional_agenda as ra
from src.http import FetchError

CC = "at"
TAXONOMIES = (("taxonomy-atch.yaml", "at"),)
THROTTLES = {"www.wien.gv.at": 1.5, "pallast2.stmk.gv.at": 1.5, "noe-landtag.gv.at": 1.5}
FEED = ra.feed(CC)

WIEN = "https://www.wien.gv.at"
WIEN_DATES = WIEN + "/politik/rathaus-sitzungstermine"
WIEN_INFODAT = WIEN + "/infodat/suchergebnisse?"
WIEN_MAX_PAGES = 10
NOE = "https://noe-landtag.gv.at"
NOE_GP = "XX"
OOE_DATES = "https://www.land-oberoesterreich.gv.at/60566.htm"
STMK = "https://pallast2.stmk.gv.at/pallast-p/"
STMK_NEXT = STMK + "api/pub/materials/meetings/next/30"
STMK_MEETING = STMK + "pub/meeting?ref={0}"
STMK_PUBLISHED = ("APPROVED", "IN_PROGRESS", "PROTOCOLLING", "CLOSED")
SBG_DATES = "https://www.salzburg.gv.at/pol/landtag/lt-termine"
TIR = "https://www.tirol.gv.at/landtag/sitzungen/"
TIR_PLENARY = TIR + "landtagssitzungen/"
TIR_COMMITTEES = TIR + "ausschusssitzungen/"
VBG_AGENDA = "https://vorarlberg.at/web/landtag/tagesordnungen"
BGLD = "https://www.bgld-landtag.at"
BGLD_DATES = BGLD + "/landtagssitzungen/termine-landtagssitzungen-{0}/"
BGLD_INDEX = BGLD + "/landtagssitzungen/xxiii-gp-tagesordnungen/"

_DATE_WORDS = re.compile(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})")


def de_date(text):
    """'Donnerstag, 22. Oktober 2026' / '22.10.2026' / 'Feber' -> ISO."""
    return ra.find_date(ra.one_line(text))


def _status_404(exc):
    return "404" in str(getattr(exc, "cause", "") or exc)


def _units(ctx, all_read, read_meetings):
    """The whole window when every sitting was read, else only the meetings
    that were (a failed sitting keeps its stored rows)."""
    if all_read:
        return [ra.window(ctx.today, ctx.until)]
    return [ra.meeting(m) for m in read_meetings]


# --- Wien: sitting dates + INFODAT ---------------------------------------------

def parse_wien_dates(page, house):
    """The sitting days under the 'Wiener Landtag' or 'Wiener Gemeinderat'
    heading: [(date, note)]."""
    m = re.search(r"<h2>\s*Wiener " + house + r"\s*</h2>\s*<ul[^>]*>(.*?)</ul>", page or "", re.S)
    out = []
    for li in re.findall(r"<li>(.*?)</li>", m.group(1) if m else "", re.S):
        text = ra.clean(li).replace("\n", " ")
        d = de_date(text)
        if d:
            note = re.search(r"\(([^)]*)\)", text)
            out.append((d, note.group(1) if note else None))
    return out


def parse_infodat(page):
    """INFODAT result rows -> [(type, sitting date, id, Aktenzahl, title)]
    and the last page number."""
    rows = []
    for m in re.finditer(r'<tr><td>([^<]*)</td><td>(\d{2}\.\d{2}\.\d{4})</td><td><a[^>]*'
                         r'href="/infodat/ergdt\?detvid=(\d+)"[^>]*>([^<]*)</a></td><td>(.*?)</td>',
                         page or "", re.S):
        kind, date, detvid, akt, title = m.groups()
        rows.append((ra.one_line(kind), de_date(date), detvid, ra.one_line(akt),
                     ra.one_line(ra.clean(title))))
    last = re.search(r'aria-label="Letzte Seite"[^>]*href="[^"]*page=(\d+)"', page or "")
    return rows, int(last.group(1)) if last else 1


SKIP_INFODAT = re.compile(r"^(Antwort|Anfragebeantwortung)", re.I)


def wien_items(dates, rows, body, ctx):
    """Items for the sittings in the window: INFODAT rows grouped by their
    sitting, a 'to be announced' row for a sitting with none."""
    out, seen = [], set()
    for order, (kind, dated, detvid, akt, title) in enumerate(rows, 1):
        if not ctx.in_window(dated) or SKIP_INFODAT.match(kind) or not title:
            continue
        seen.add(dated)
        out.append(ra.item(dated, "{0}: {1}".format(kind, title) if kind else title, body,
                           meeting_id="wien-{0}-{1}".format(body.lower(), dated),
                           reference=akt or None, key="infodat-" + detvid,
                           url="{0}/infodat/ergdt?detvid={1}".format(WIEN, detvid)))
    for dated, note in dates:
        if ctx.in_window(dated) and dated not in seen:
            out.append(ra.item(dated, "", body, item_time="09:00",
                               meeting_id="wien-{0}-{1}".format(body.lower(), dated),
                               detail=note, url=WIEN_DATES))
    return out


def _read_wien(client, ctx, house, committees, body, slug):
    page = client.get_text(WIEN_DATES, FEED, "wien-dates")
    dates = parse_wien_dates(page, house)
    rows, page_no, last, gaps, done = [], 1, 1, [], False
    while page_no <= WIEN_MAX_PAGES and not ctx.out_of_time():
        q = {"committees": committees, "sessionDayFrom": ctx.today, "sessionDayTo": ctx.until,
             "page": page_no}
        got, last = parse_infodat(client.get_text(WIEN_INFODAT + urllib.parse.urlencode(q), FEED,
                                                  "{0}-infodat-{1}".format(slug, page_no),
                                                  archive=False))
        rows += got
        if not got or page_no >= last:
            done = True
            break
        page_no += 1
    if not done:
        gaps.append("{0}: INFODAT has {1} pages in the window; the first {2} were read".format(
            slug, last, page_no - 1))
    items = wien_items(dates, rows, body, ctx)
    complete = done
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)] if complete else [],
                         source="wien.gv.at sitting dates + INFODAT (committees={0})".format(
                             committees), gaps=gaps)


def read_wien(client, ctx):
    return _read_wien(client, ctx, "Landtag", "L", "Landtag", "wien")


def read_wien_gr(client, ctx):
    return _read_wien(client, ctx, "Gemeinderat", "G", "Gemeinderat", "wien-gr")


# --- Niederösterreich -------------------------------------------------------------

def parse_noe_dates(page):
    """'Termine der nächsten Landtagssitzungen' -> [date]."""
    m = re.search(r'<ul class="upcoming-meetings[^"]*">(.*?)</ul>', page or "", re.S)
    out = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", m.group(1) if m else "", re.S):
        d = de_date(ra.clean(li))
        if d:
            out.append(d)
    return out


def parse_noe_sitting(page, dated, url=None):
    """A sitting day's Tagesordnung: one item per Tagesordnungspunkt, with
    the Verhandlungsgegenstand (Ltg.-number and short title) and the
    committee's motion as detail."""
    time = re.search(r'<time datetime="\d{4}-\d{2}-\d{2} (\d{2}:\d{2})"', page or "")
    out = []
    blocks = re.split(r'<div id="top(\d+)">', page or "")
    for i in range(1, len(blocks) - 1, 2):
        num, block = blocks[i], blocks[i + 1]
        title = re.search(r'<span class="mt-2 d-block">(.*?)</span>', block, re.S)
        if not title:
            continue
        refs = re.findall(r'<a href="/gegenstaende/[^"]*"><span class="sr-only">[^<]*</span>'
                          r'<span>([^<]*)</span></a><span>([^<]*)</span>', block)
        motion = re.search(r'<div class="ce-bodytext mb-3"><p>(.*?)</p>', block, re.S)
        detail = "; ".join(x for x in [ra.clean(motion.group(1)) if motion else ""] +
                           ["{0}{1}".format(a, b) for a, b in refs] if x)
        link = re.search(r'<a href="(/sitzungen/[^"]*/top-[^"]*)"', block)
        out.append(ra.item(dated, ra.clean(title.group(1)), "Landtag",
                           item_time=time.group(1) if time else None, order=int(num),
                           meeting_id="noe-" + dated, detail=detail or None,
                           reference=refs[0][0] if refs else None,
                           url=NOE + link.group(1) if link else url))
    return out


def read_noe(client, ctx):
    dates = [d for d in parse_noe_dates(client.get_text(NOE + "/sitzungen", FEED, "noe-dates"))
             if ctx.in_window(d)]
    items, gaps, read, ok = [], [], [], True
    for d in dates:
        if ctx.out_of_time():
            ok = False
            break
        url = "{0}/sitzungen/{1}/{2}".format(NOE, NOE_GP, d)
        try:
            got = parse_noe_sitting(client.get_text(url, FEED, "noe-" + d), d, url)
        except FetchError as exc:
            if not _status_404(exc):
                gaps.append("noe sitting {0}: {1}".format(d, str(exc)[:160]))
                ok = False
                continue
            got = []
        items += got or [ra.item(d, "", "Landtag", meeting_id="noe-" + d,
                                 url=NOE + "/sitzungen")]
        read.append("noe-" + d)
    return ra.RegionRead(items, _units(ctx, ok, read), source="noe-landtag.gv.at /sitzungen",
                         gaps=gaps)


# --- Oberösterreich ------------------------------------------------------------------

def parse_ooe_dates(page):
    """Every 'Donnerstag, 12. November 2026 (Budgetlandtag)' on the dates
    page -> [(date, note)]."""
    out = []
    for m in re.finditer(r"(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag),\s*(\d{1,2}\.\s*"
                         r"[A-Za-zäÄ]+\s+\d{4})(?:\s*\(([^)]*)\))?", ra.clean(page)):
        d = de_date(m.group(1))
        if d and (d, m.group(2)) not in out:
            out.append((d, m.group(2)))
    return out


def read_ooe(client, ctx):
    items = [ra.item(d, "", "Landtag", item_time="10:00", meeting_id="ooe-" + d, detail=note,
                     url=OOE_DATES)
             for d, note in parse_ooe_dates(client.get_text(OOE_DATES, FEED, "ooe-dates"))
             if ctx.in_window(d)]
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="land-oberoesterreich.gv.at Sitzungstermine",
                         note="sitting dates only: the Tagesordnung host's certificate does not verify")


# --- Steiermark (PALLAST) ---------------------------------------------------------------

def stmk_meetings(data):
    """PALLAST's next meetings -> [(uuid, date, time, kind, label, status)]."""
    out = []
    for m in data or []:
        ts = (m.get("tsStart") or "").split(" ")
        d = de_date(ts[0]) if ts else None
        if not d:
            continue
        kind = (m.get("type") or {}).get("value")
        label = (m.get("type") or {}).get("text") or ""
        if m.get("number"):
            label = "{0}. {1}".format(m["number"], label)
        out.append((m.get("uuid"), d, ts[1][:5] if len(ts) > 1 else None, kind, label,
                    (m.get("status") or {}).get("value")))
    return out


def _stmk_text(fragment):
    return ra.one_line(ra.clean(fragment))


def parse_stmk_meeting(page, uuid, dated, kind):
    """A meeting page's Tagesordnung. Plenary: each point (A, B1, D1, 1 ...)
    with its Einl.Zahl, kind and Betreff. Committee day: the same under
    each committee's heading (its date and start time in brackets)."""
    i = (page or "").find("Tagesordnung</h2>")
    if i < 0:
        return []
    body_default = "Landtag" if kind == "PARLIAMENT" else "Ausschuss"
    out, body, time = [], body_default, None
    when = re.search(r"um\s*(?:<b>)?\s*(\d{1,2}:\d{2})\s*Uhr", page)
    if kind == "PARLIAMENT" and when:
        time = when.group(1)
    parts = re.split(r'(<h3 class="center-text">.*?</h3>(?:\s*<div class="center-text">.*?</div>)*'
                     r'|<div class="text"><b>[^<]*</b>\.)', page[i:], flags=re.S)
    current = None
    order = 0
    for part in parts:
        if part.startswith('<h3 class="center-text">'):
            body = _stmk_text(re.search(r"<h3[^>]*>(.*?)</h3>", part, re.S).group(1))
            t = re.search(r"Beginn um (\d{1,2}:\d{2})", part)
            time = t.group(1) if t else time
            continue
        m = re.match(r'<div class="text"><b>([^<]*)</b>\.', part)
        if m:
            current = m.group(1).strip()
            continue
        if current is None:
            continue
        num, current = current, None
        zahl = re.search(r"Einl\.Zahl\s*<b>(?:<a [^>]*>)?([^<]+)", part)
        withdrawn = "Zurückgezogen" in part[:400]
        divs = [_stmk_text(x) for x in re.findall(r'<div class="text">(.*?)</div>', part, re.S)]
        kind_text = divs[0] if divs else ""
        subject = next((d[len("Betreff:"):].strip() for d in divs if d.startswith("Betreff:")), "")
        refs = [_stmk_text(x) for x in re.findall(r'<div class="tab">(.*?)</div>', part, re.S)]
        if not subject and not kind_text:
            continue
        business = subject or kind_text
        if kind_text and subject and not re.match(r"Bericht \(", kind_text):
            business = "{0}: {1}".format(re.sub(r"\s*\([^)]*\)$", "", kind_text), subject)
        if withdrawn:
            business += " (zurückgezogen)"
        order += 1
        link = re.search(r'href="(document\?ref=[^"&]+)', part)
        out.append(ra.item(dated, business, body, item_time=time, order=order,
                           meeting_id=uuid, detail="; ".join([kind_text] + refs) or None,
                           reference=("EZ " + zahl.group(1).strip()) if zahl else num,
                           url=STMK + "pub/" + link.group(1) if link else
                           STMK_MEETING.format(uuid)))
    return out


def read_stmk(client, ctx):
    meetings = [m for m in stmk_meetings(client.get_json(STMK_NEXT, FEED, "stmk-next"))
                if ctx.in_window(m[1])]
    items, gaps, read, ok = [], [], [], True
    for uuid, d, time, kind, label, status in meetings:
        body = "Landtag" if kind == "PARLIAMENT" else "Ausschüsse"
        got = []
        if status in STMK_PUBLISHED:
            if ctx.out_of_time():
                ok = False
                break
            try:
                got = parse_stmk_meeting(client.get_text(STMK_MEETING.format(uuid), FEED,
                                                         "stmk-" + uuid[:8]), uuid, d, kind)
            except FetchError as exc:
                gaps.append("stmk meeting {0} ({1}): {2}".format(d, label, str(exc)[:160]))
                ok = False
                continue
        items += got or [ra.item(d, "", body, item_time=time, meeting_id=uuid, detail=label,
                                 url=STMK_MEETING.format(uuid))]
        read.append(uuid)
    return ra.RegionRead(items, _units(ctx, ok, read), source="PALLAST meetings API + meeting pages",
                         gaps=gaps)


# --- Salzburg ----------------------------------------------------------------------------

def parse_sbg_dates(page):
    """The calendar table: first column Ausschusssitzungen, second
    Haussitzungen -> [(date, body, note)]."""
    out = []
    table = re.search(r"<table[^>]*>(.*?)</table>", page or "", re.S)
    for row in re.findall(r"<tr>(.*?)</tr>", table.group(1) if table else "", re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) != 2:
            continue
        for cell, body in zip(cells, ("Ausschüsse", "Landtag")):
            text = ra.clean(cell).replace("\n", " ")
            d = de_date(text)
            if d:
                note = re.search(r"\(([^)]*)\)", text)
                out.append((d, body, note.group(1) if note else None))
    return out


def read_sbg(client, ctx):
    items = [ra.item(d, "", body, meeting_id="sbg-{0}-{1}".format(ra.slug(body, 12), d),
                     detail=note, url=SBG_DATES)
             for d, body, note in parse_sbg_dates(client.get_text(SBG_DATES, FEED, "sbg-dates"))
             if ctx.in_window(d)]
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="salzburg.gv.at Landtagstermine",
                         note="sitting dates only: LPI's robots.txt answers 503")


# --- Tirol --------------------------------------------------------------------------------

_RANGE = re.compile(r"(?:vom|am)\s*(\d{1,2})\.(?:\s*(?!bis\b|und\b)([A-Za-zÄÖÜäöü]+))?\s*(?:(?:bis|und|-)\s*"
                    r"(\d{1,2})\.)?\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})")


def tir_days(sentence):
    """'vom 4. bis 6. November 2026 statt (6. November - Reservetag)' ->
    ['2026-11-04', '2026-11-05'] (the reserve day is left out)."""
    text = ra.one_line(ra.clean(sentence))
    m = _RANGE.search(text)
    if not m:
        return []
    d1, m1, d2, m2, year = m.groups()
    start = ra.iso(d1, m1 or m2, year)
    end = ra.iso(d2, m2, year) if d2 else start
    if not start or not end:
        return []
    reserve = re.search(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s*-\s*Reservetag", text)
    reserve = ra.iso(reserve.group(1), reserve.group(2), year) if reserve else None
    out, day = [], datetime.date.fromisoformat(start)
    while day.isoformat() <= end:
        if day.isoformat() != reserve:
            out.append(day.isoformat())
        day += datetime.timedelta(days=1)
    return out


def parse_tir_next(page, marker):
    """The sentence after `marker` ('nächste Landtagssitzung' / 'nächsten
    Ausschusssitzungen') -> its days."""
    text = ra.clean(page)
    i = text.find(marker)
    return tir_days(text[i:i + 200]) if i >= 0 else []


def read_tir(client, ctx):
    items = []
    plenary = parse_tir_next(client.get_text(TIR_PLENARY, FEED, "tir-plenary"),
                             "chste Landtagssitzung")
    for d in plenary:
        if ctx.in_window(d):
            items.append(ra.item(d, "", "Landtag", meeting_id="tir-landtag-" + d, url=TIR_PLENARY))
    committees = parse_tir_next(client.get_text(TIR_COMMITTEES, FEED, "tir-committees"),
                                "chsten Ausschusssitzungen")
    for d in committees:
        if ctx.in_window(d):
            items.append(ra.item(d, "", "Ausschüsse", meeting_id="tir-ausschuesse-" + d,
                                 url=TIR_COMMITTEES))
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="tirol.gv.at sitting pages",
                         note="next sitting and committee days only: the materials host "
                              "(lte.tirol.gv.at) disallows every robot")


# --- Vorarlberg ----------------------------------------------------------------------------

def parse_vbg(page):
    """The agenda page's headings: 'LANDTAGSSITZUNG am 18.11.2026',
    'AUSSCHUSSSITZUNGEN am 4.11. und 11.11.2026' -> [(date, body)]."""
    out = []
    for h in re.findall(r"<h3>(.*?)</h3>", page or "", re.S):
        text = ra.one_line(ra.clean(h))
        body = ("Landtag" if re.search(r"LANDTAGSSITZUNG", text, re.I) else
                "Ausschüsse" if re.search(r"AUSSCHUSS", text, re.I) else None)
        if not body:
            continue
        year = re.findall(r"\d{1,2}\.\d{1,2}\.(\d{4})", text)
        for dd, mm, yy in re.findall(r"(\d{1,2})\.(\d{1,2})\.(\d{4})?", text):
            d = ra.iso(dd, mm, yy or (year[-1] if year else ""))
            if d:
                out.append((d, body))
    return out


def read_vbg(client, ctx):
    items = [ra.item(d, "", body, meeting_id="vbg-{0}-{1}".format(ra.slug(body, 12), d),
                     url=VBG_AGENDA)
             for d, body in parse_vbg(client.get_text(VBG_AGENDA, FEED, "vbg-agenda"))
             if ctx.in_window(d)]
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="vorarlberg.at Tagesordnungen page",
                         note="sitting and committee days; the agenda (posted the Thursday "
                              "before) is not parsed yet")


# --- Burgenland ------------------------------------------------------------------------------

def parse_bgld_dates(page):
    """The year's calendar table: date, time, 'Landtag' / 'Ausschüsse'."""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", page or "", re.S):
        cells = [ra.one_line(ra.clean(c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 3:
            continue
        d = de_date(cells[0])
        if d and cells[2] in ("Landtag", "Ausschüsse"):
            out.append((d, cells[1].replace(".", ":"), cells[2]))
    return out


def parse_bgld_index(page):
    """The Tagesordnungen index -> [(date, url)] for each listed sitting."""
    out = []
    for p in re.findall(r"<p>(.*?)</p>", page or "", re.S):
        link = re.search(r'<a href="(/landtagssitzungen/[^"]*tagesordnung[^"]*)"', p)
        text = ra.one_line(ra.clean(p))
        m = re.search(r"Landtagssitzung am (\d{1,2})\.(?:\s*und\s*\d{1,2}\.)?\s*([A-Za-zäÄ]+)\s+(\d{4})",
                      text)
        if link and m:
            d = ra.iso(m.group(1), m.group(2), m.group(3))
            if d:
                out.append((d, BGLD + link.group(1)))
    return out


def parse_bgld_agenda(page, dated, url=None):
    """An agenda page: the <ol> of points, each point's first line as the
    business, 'Zahl' and 'Beilage' as reference."""
    lst = re.search(r"<ol>(.*?)</ol>", page or "", re.S)
    out = []
    for order, li in enumerate(re.findall(r"<li>(.*?)</li>", lst.group(1) if lst else "", re.S), 1):
        head = re.split(r"<br\s*/?>\s*<br\s*/?>|<strong>", li)[0]
        text = ra.one_line(ra.clean(head))
        if not text:
            continue
        zahl = re.search(r"\(Zahl\s*([\d-]+)\)", text)
        out.append(ra.item(dated, text, "Landtag", order=order, meeting_id="bgld-" + dated,
                           reference=("Zahl " + zahl.group(1)) if zahl else None, url=url))
    return out


def read_bgld(client, ctx):
    years = sorted({ctx.today[:4], ctx.until[:4]})
    slots, gaps = [], []
    for y in years:
        try:
            slots += parse_bgld_dates(client.get_text(BGLD_DATES.format(y), FEED, "bgld-dates-" + y))
        except FetchError as exc:
            if y == ctx.today[:4]:
                raise
            gaps.append("bgld calendar {0} not published yet ({1})".format(y, str(exc)[:80]))
    agendas = dict(parse_bgld_index(client.get_text(BGLD_INDEX, FEED, "bgld-index")))
    items, ok, read = [], True, []
    for d, time, body in slots:
        if not ctx.in_window(d):
            continue
        mid = "bgld-{0}-{1}".format(ra.slug(body, 12), d) if body != "Landtag" else "bgld-" + d
        got = []
        if body == "Landtag" and d in agendas:
            try:
                got = parse_bgld_agenda(client.get_text(agendas[d], FEED, "bgld-to-" + d), d,
                                        agendas[d])
            except FetchError as exc:
                gaps.append("bgld agenda {0}: {1}".format(d, str(exc)[:160]))
                ok = False
                continue
        for it in got:
            it["item_time"] = time
        items += got or [ra.item(d, "", body, item_time=time, meeting_id=mid,
                                 url=BGLD_DATES.format(d[:4]))]
        read.append(mid)
    return ra.RegionRead(items, _units(ctx, ok, read),
                         source="bgld-landtag.at calendar + Tagesordnungen", gaps=gaps)


REGIONS = {
    "wien": ra.region("Wien", reader=read_wien),
    "wien-gr": ra.region("Wien Gemeinderat", reader=read_wien_gr),
    "noe": ra.region("Niederösterreich", reader=read_noe),
    "ooe": ra.region("Oberösterreich", reader=read_ooe),
    "stmk": ra.region("Steiermark", reader=read_stmk),
    "tir": ra.region("Tirol", reader=read_tir),
    "ktn": ra.region("Kärnten", status="blocked",
                     note="www.ktn.gv.at robots.txt: User-agent: * Disallow: / (only Google and "
                          "Bing allowed); landtag.ktn.gv.at, landtag-ktn.gv.at and "
                          "www.kaernten.gv.at do not resolve"),
    "sbg": ra.region("Salzburg", reader=read_sbg),
    "vbg": ra.region("Vorarlberg", reader=read_vbg),
    "bgld": ra.region("Burgenland", reader=read_bgld),
}
