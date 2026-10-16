"""Australia: the state and territory parliaments' forward business
(src/regional_agenda.py; 16 October 2026).

Region codes are the state layer's (tools/au_states.py, src/au_states_store.py):
nsw, vic, qld, wa, sa, tas, act, nt. Six of the eight parliaments' own
websites answer our honest user agent with a bot challenge (Cloudflare or
Azure WAF), which is never solved or bypassed (docs/australia-states-scope.md).
What answers, and is read here:

  vic  www.parliament.vic.gov.au/api/calendar/twelve-months?year=<y> (the
       JSON the Parliament's own sitting-calendar page loads): sitting days
       per House ('Both Houses', 'Assembly Only', 'Council Only') and
       committee hearings with their inquiry. Sittings are 'to be announced'
       (no notice paper route on this host); hearings carry the inquiry.
  sa   the Parliament's document library backend
       (dynamic-content-api.parliament.sa.gov.au/api/documentlibrary, POST;
       robots.txt 404), the same backend tools/au_states.py reads for the
       Votes and Proceedings: library 6 holds the House of Assembly's current
       Notice Paper.pdf, library 1 the Legislative Council's LCNP.pdf. Each is
       fetched through the short-lived read-only link the library hands every
       visitor. One item per order of the day and notice of motion, dated by
       the day heading it stands under (the paper runs weeks ahead).
  tas  the Parliament's own search engine (search.parliament.tas.gov.au,
       robots.txt 404): the year's sitting days per House
       (/search/quicksearch/<year>/sittingdays.html), and for the next sitting
       days the House of Assembly's Notice Paper (Word, 'NP<no><ddmmyyyy>.docx')
       found in its 'Notice Papers' database by the day's date.

Not read (blocked): NSW (www.parliament.nsw.gov.au, Cloudflare; the Hansard
API on api.parliament.nsw.gov.au has no forward business), Queensland and
Western Australia (Azure WAF), the ACT and the Northern Territory
(Cloudflare).
"""

from __future__ import annotations

import datetime
import json
import re
import urllib.parse

from src import regional_agenda as ra

CC = "au"
TAXONOMIES = (("taxonomy.yaml", "au"),)
FEED = ra.feed(CC)
THROTTLES = {"www.parliament.vic.gov.au": 2.0}

DAYS = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")


def cut(text, limit=400):
    t = ra.one_line(text)
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + " ..."


def tba_for(items, sittings, prefix):
    """One 'to be announced' item per (date, House) with no item of its own."""
    have = {(it["dated"], it["body"]) for it in items}
    return [ra.item(d, "", body, meeting_id="{0}-{1}-{2}".format(prefix, ra.slug(body, 20), d))
            for d, body in sorted(sittings) if (d, body) not in have]


# --- Victoria ------------------------------------------------------------------

VIC_CAL = "https://www.parliament.vic.gov.au/api/calendar/twelve-months?year={0}"
VIC_PAGE = "https://www.parliament.vic.gov.au/parliamentary-activity/sitting-calendar/"
VIC_SITTINGS = {50: ("Legislative Assembly", "Legislative Council"), 60: ("Legislative Assembly",),
                70: ("Legislative Council",)}


def _vic_dates(value):
    out = []
    for v in value if isinstance(value, list) else [value]:
        if isinstance(v, dict):
            s, e = (v.get("start") or "")[:10], (v.get("end") or v.get("start") or "")[:10]
            if s:
                d = datetime.date.fromisoformat(s)
                while d.isoformat() <= max(s, e):
                    out.append(d.isoformat())
                    d += datetime.timedelta(days=1)
        elif isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v):
            out.append(v[:10])
    return out


def parse_vic_calendar(data):
    """([(date, House)] sittings, [(date, inquiry)] hearings) of one year."""
    sittings, hearings = [], []
    for e in (data or {}).get("result") or []:
        kind = e.get("type")
        if kind in VIC_SITTINGS:
            for d in _vic_dates(e.get("dates")):
                for house in VIC_SITTINGS[kind]:
                    sittings.append((d, house))
        elif kind == 30:
            what = re.sub(r"^Hearing for\s+", "", ra.one_line(e.get("details")))
            for d in _vic_dates(e.get("dates")):
                hearings.append((d, what))
    return sorted(set(sittings)), hearings


def read_vic(client, ctx):
    years = sorted({ctx.today[:4], ctx.until[:4]})
    sittings, hearings = [], []
    for y in years:
        data = client.get_json(VIC_CAL.format(y), FEED, "vic-cal-" + y, archive=False)
        if (data or {}).get("result") is None and (data or {}).get("error"):
            continue       # 'no events found in the selected year': next year not out yet
        s, h = parse_vic_calendar(data)
        sittings += s
        hearings += h
    items = []
    for n, (d, what) in enumerate(hearings):
        if ctx.in_window(d):
            items.append(ra.item(d, "Hearing: " + what, "Parliamentary committee", order=n,
                                 meeting_id="vic-hearing-{0}-{1}".format(d, ra.slug(what, 40)),
                                 url=VIC_PAGE, item_type="committee evidence"))
    items += tba_for(items, [(d, h) for d, h in sittings if ctx.in_window(d)], "vic")
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="parliament.vic.gov.au sitting calendar (api/calendar)",
                         note="" if any(ctx.in_window(d) for d, _ in sittings) else
                         "no sitting day in the window (the Parliament expires before the "
                         "28 November 2026 election)")


# --- South Australia ---------------------------------------------------------------

SA_LIB = "https://dynamic-content-api.parliament.sa.gov.au/api/documentlibrary"
SA_LINK = ("https://dynamic-content-api.parliament.sa.gov.au/api/GetFileDownloadLink?"
           "controlId={0}&fileId={1}")
SA_PAPERS = (("6", "House of Assembly", "Notice Paper.pdf"),
             ("1", "Legislative Council", "LCNP.pdf"))
SA_STOP = ("QUESTION ON NOTICE", "QUESTIONS ON NOTICE", "LEGISLATIVE INSTRUMENTS",
           "SUBORDINATE LEGISLATION", "INDEX TO BILLS", "PARLIAMENTARY COMMITTEES")
SA_DAY = re.compile(r"^(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY)\s+(\d{1,2})\s+([A-Z]+)\s+(\d{4})$")


def parse_sa_notice_paper(text, body, url=None):
    """Items of a South Australian Notice Paper: each numbered order of the
    day or notice of motion, dated by the day heading above it, with the
    section heading it stands under."""
    items, dated, section, cur, last = [], None, "", None, 0
    for raw in (text or "").splitlines():
        line = ra.one_line(raw)
        if not line or line == "=====PAGE" or re.match(r"^[.\s\d]+$", line):
            continue
        if line in SA_STOP or line.startswith(SA_STOP):
            break
        d = SA_DAY.match(line)
        if d:
            if cur:
                items.append(cur)
                cur = None
            dated, last = ra.iso(d.group(2), d.group(3), d.group(4)), 0
            continue
        m = re.match(r"^[■\*]?\s*(\d{1,3})\.?\s+(\D.*)$", line)
        if m and dated and (int(m.group(1)) == last + 1 or int(m.group(1)) == 1):
            if cur:
                items.append(cur)
            last = int(m.group(1))
            cur = {"dated": dated, "section": section, "no": m.group(1), "text": m.group(2)}
            continue
        if len(line) < 70 and (line.isupper() or re.match(
                r"^(Orders? of the Day|Notices? of Motion|Bills|Other Motions|Bills & Motions)", line)):
            if cur:
                items.append(cur)
                cur = None
            section = line.rstrip(" -").strip()
            last = 0
            continue
        if cur:
            cur["text"] += " " + line
    if cur:
        items.append(cur)
    out = []
    for n, c in enumerate(items, 1):
        text = ra.one_line(c["text"])
        business = re.split(r"\s+[–-]\s+\(\d", text)[0]
        bill = re.search(r"\bBill\b.*?\(No\.?\s*(\d+)\)", text)
        motion = re.search(r"\bto move\b", text)
        ref = ("Bill No {0}".format(bill.group(1)) if bill else
               "{0} {1}".format("Notice of Motion" if motion else "Order of the Day", c["no"]))
        out.append(ra.item(c["dated"], cut(business), body, order=n,
                           meeting_id="sa-{0}-{1}".format(ra.slug(body, 20), c["dated"]),
                           detail="{0}: {1}".format(c["section"], text) if c["section"] else text,
                           reference=ref, url=url))
    return out


def _sa_listing(client, ctrl):
    body = json.dumps({"controlId": ctrl, "folderRelativeUrl": "", "pageInfo": "", "pageSize": "100",
                       "sortFolders": "asc", "sortFiles": "desc"})
    return client.post_json(SA_LIB, body, FEED, "sa-lib-" + ctrl)


def read_sa(client, ctx):
    from src.prov_fetch import pdf_text
    items, units, gaps, read = [], [], [], []
    for ctrl, body, name in SA_PAPERS:
        try:
            files = (_sa_listing(client, ctrl) or {}).get("files") or []
            f = next((x for x in files if x.get("fileName") == name), None)
            if not f:
                raise ValueError("no {0} in library {1}".format(name, ctrl))
            link = (client.get_json(SA_LINK.format(ctrl, f["id"]), FEED, "sa-link-" + ctrl,
                                    archive=False) or {}).get("downloadLink")
            if not link:
                raise ValueError("no download link for {0}".format(name))
            got = parse_sa_notice_paper(pdf_text(client.get_bytes(link, FEED, "sa-np-" + ctrl,
                                                                  archive=False)), body,
                                        "https://www.parliament.sa.gov.au/")
        except Exception as exc:                  # noqa: BLE001 - one House: a partial gap
            gaps.append("South Australia {0} Notice Paper: {1}".format(body, str(exc)[:160]))
            continue
        got = [it for it in got if ctx.in_window(it["dated"])]
        items += got
        read.append(body)
        for d in sorted({it["dated"] for it in got}):
            units.append(ra.day(d, body))
    if not read:
        raise ValueError("; ".join(gaps))
    return ra.RegionRead(items, units, source="parliament.sa.gov.au document library (Notice Papers)",
                         note="Notice Papers read: {0}".format(", ".join(read)), gaps=gaps)


# --- Tasmania ---------------------------------------------------------------------

TAS_BASE = "https://search.parliament.tas.gov.au"
TAS_SITTINGS = TAS_BASE + "/search/quicksearch/{0}/sittingdays.html"
TAS_SEARCH = (TAS_BASE + "/Search/search/search?IW_FIELD_ADVANCE_PHRASE={0}"
              "&IW_DATABASE=Notice%20Papers&IW_SORT=-9")
TAS_HOUSES = {"HA": ("House of Assembly",), "LC": ("Legislative Council",),
              "Both": ("House of Assembly", "Legislative Council")}
TAS_NOTICE_DAYS = 3


def parse_tas_sittings(page):
    """[(date, House)] of a year's sitting days: each table is a month (its
    caption), each linked cell a day whose class names the House(s). The
    link's own phrase is not trusted: it can name another day."""
    out = []
    for cap, table in re.findall(r"<caption>\s*([A-Z][a-z]+ \d{4})\s*</caption>(.*?)</table>",
                                 page or "", re.S):
        mon, year = cap.split()
        for cls, day in re.findall(r'<td [Cc]lass="(HA|LC|Both)"[^>]*>\s*<a [^>]*>\s*(\d{1,2})\s*</a>',
                                   table):
            d = ra.iso(day, mon, year)
            if d:
                out.extend((d, h) for h in TAS_HOUSES[cls])
    return sorted(set(out))


def tas_notice_links(page, dated):
    """Absolute URLs of the House of Assembly Notice Papers for `dated`
    ('NP52' + '27102026' + '.docx') in a search result page."""
    ddmmyyyy = dated[8:10] + dated[5:7] + dated[:4]
    out = []
    for href in re.findall(r'href="([^"]+?\.docx)"', page or ""):
        name = urllib.parse.unquote(href.rsplit("/", 1)[-1])
        if re.match(r"^NP\d+" + ddmmyyyy + r"\.docx$", name):
            out.append(urllib.parse.urljoin(TAS_BASE + "/", href))
    return out


TAS_DATE = re.compile(r"^(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY),\s+(\d{1,2})\s+([A-Z]+)\s+(\d{4})$")


def parse_tas_notice_paper(paragraphs, body="House of Assembly", url=None):
    """Items of a Tasmanian Notice Paper (Word paragraphs): each numbered
    notice of motion and order of the day, dated by the day heading."""
    items, dated, section, cur = [], None, "Notices of Motion", None
    for p in paragraphs or []:
        line = ra.one_line(p)
        if not line:
            continue
        if line == "PAPERS ISSUED" or re.search(r", Clerk of the (?:House|Council)$", line):
            break
        d = TAS_DATE.match(line)
        if d:
            if cur:
                items.append(cur)
                cur = None
            dated = ra.iso(d.group(2), d.group(3), d.group(4))
            section = "Notices of Motion"
            continue
        if line in ("Orders of the Day", "Notices of Motion", "Government Business",
                    "Private Members' Business", "Private Members’ Business"):
            if cur:
                items.append(cur)
                cur = None
            section = line
            continue
        m = re.match(r"^(\d{1,3})\s+(\S.*)$", line)
        if m and dated:
            if cur:
                items.append(cur)
            cur = {"dated": dated, "section": section, "no": m.group(1), "text": m.group(2)}
        elif cur:
            cur["text"] += " " + line
        elif dated and section == "Orders of the Day" and len(line) > 30:
            items.append({"dated": dated, "section": section, "no": "", "text": line})
    if cur:
        items.append(cur)
    out = []
    for n, c in enumerate(items, 1):
        text = ra.one_line(c["text"])
        move = re.match(r"^(.+?) to move\s*[—–-]\s*(.*)$", text)
        if move:
            business = "Notice of motion {0}: {1}".format(c["no"], move.group(2))
            ref = "Notice of Motion {0}".format(c["no"])
        else:
            business = re.sub(r"\s*\((?:The |Mr |Mrs |Ms |Dr |Minister |Next Speaker)[^()]*\)\s*$", "",
                              text.split(" (Next Speaker")[0])
            bill = re.search(r"\bBill\b[^()]*?\((?:No\.\s*)(\d+)\)", text)
            ref = "Bill No. {0}".format(bill.group(1)) if bill else (
                "Order of the Day {0}".format(c["no"]) if c["no"] else None)
        out.append(ra.item(c["dated"], cut(business), body, order=n,
                           meeting_id="tas-{0}-{1}".format(ra.slug(body, 20), c["dated"]),
                           detail="{0}: {1}".format(c["section"], text), reference=ref, url=url))
    return out


def read_tas(client, ctx):
    from src.au_states_votes import docx_paragraphs
    sittings = []
    for y in sorted({ctx.today[:4], ctx.until[:4]}):
        try:
            sittings += parse_tas_sittings(client.get_text(TAS_SITTINGS.format(y), FEED,
                                                           "tas-sittings-" + y, archive=False))
        except Exception:                         # noqa: BLE001
            if y == ctx.today[:4]:
                raise
    sittings = [(d, h) for d, h in sittings if ctx.in_window(d)]
    items, gaps, papers = [], [], []
    ha_days = sorted({d for d, h in sittings if h == "House of Assembly"})[:TAS_NOTICE_DAYS]
    for d in ha_days:
        if ctx.out_of_time():
            break
        dt = datetime.date.fromisoformat(d)
        phrase = urllib.parse.quote("{0} {1} {2}".format(dt.day, dt.strftime("%B"), dt.year))
        try:
            links = tas_notice_links(client.get_text(TAS_SEARCH.format(phrase), FEED, "tas-np-search-" + d,
                                                     archive=False), d)
            if not links:
                continue
            raw = client.get_bytes(links[0], FEED, "tas-np-" + d, archive=False)
            got = [it for it in parse_tas_notice_paper(docx_paragraphs(raw), url=links[0])
                   if ctx.in_window(it["dated"])]
            items += got
            papers.append(d)
        except Exception as exc:                  # noqa: BLE001
            gaps.append("Tasmania Notice Paper {0}: {1}".format(d, str(exc)[:160]))
    items += tba_for(items, sittings, "tas")
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="search.parliament.tas.gov.au sitting days and Notice Papers",
                         note=("House of Assembly Notice Paper for {0}".format(", ".join(papers))
                               if papers else "no Notice Paper found for the next sitting days"),
                         gaps=gaps)


# --- the regions ---------------------------------------------------------------------

REGIONS = {
    "nsw": ra.region("New South Wales", status="blocked",
                     note="www.parliament.nsw.gov.au (notice and business papers, sitting calendar) answers "
                          "a Cloudflare challenge (403, 16 October 2026; GitHub's runners too), never "
                          "bypassed. The Parliament's API (api.parliament.nsw.gov.au) answers but serves "
                          "the Hansard only: past sitting days, no forward business"),
    "vic": ra.region("Victoria", reader=read_vic),
    "qld": ra.region("Queensland", status="blocked",
                     note="www.parliament.qld.gov.au (notice paper, sitting calendar) answers an Azure WAF "
                          "challenge (403, 16 October 2026); documents.parliament.qld.gov.au serves files "
                          "only by exact name (no listing) and no forward-business file name is published "
                          "anywhere reachable"),
    "wa": ra.region("Western Australia", status="blocked",
                    note="www.parliament.wa.gov.au answers an Azure WAF challenge (403, 16 October 2026) on "
                         "every page and on robots.txt itself; legislation.wa.gov.au carries Acts only"),
    "sa": ra.region("South Australia", reader=read_sa),
    "tas": ra.region("Tasmania", reader=read_tas),
    "act": ra.region("Australian Capital Territory", status="blocked",
                     note="www.parliament.act.gov.au (Notice Paper, Daily Program, sitting calendar) "
                          "answers a Cloudflare challenge (403, 16 October 2026); hansard.act.gov.au "
                          "answers but carries past debates only"),
    "nt": ra.region("Northern Territory", status="blocked",
                    note="parliament.nt.gov.au answers a Cloudflare challenge (403, 16 October 2026); "
                         "legislation.nt.gov.au lists bills by session (no sitting dates or notice "
                         "paper); territorystories.nt.gov.au disallows /search/, /documents/ and PDFs"),
}
