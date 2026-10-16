"""Italy: the regional councils' forward agendas (16 October 2026; the past
business is tools/it_regions.py, whose codes these reuse: lom, cam, mar,
tn; the others follow the same three-letter pattern).

Routes read (each probed live on 16 October 2026, robots.txt asked):

    laz  Lazio: the home page's agenda (next week's committee meetings,
         ?vw=homeCommissioni&cid=N links) and each committee's home page,
         which prints its next sittings with the full 'ordine del giorno'.
         The Aula's agendas (?vw=elencolavoriaula, tbl_lavori_aula_odg2)
         are disallowed by robots.txt: an Aula sitting on the home agenda
         is kept as a booked slot only.
    cam  Campania: 'Ordine del giorno prossime sedute' (Drupal view) lists
         the convened Council sittings with the convocation (a PDF from
         the council's document service, read with pypdf when installed).
         robots.txt asks a crawl delay of 10 s (THROTTLES).
    sic  Sicilia (ARS): the agenda pages' calendar (the dates with events
         are in the page's Drupal settings) and the per-day listing the
         page loads (/agenda/aula/YYYYMMDD, /agenda/commissione/YYYYMMDD,
         JSON with an HTML fragment): Aula sittings and committee meetings
         (cancelled ones dropped) as booked slots; the order of the day is
         a PDF 'foglio notizie', not read.
    emr  Emilia-Romagna: the Assembly's Plone agenda as iCalendar
         (/agenda/ics_view): every Aula and committee event with a subject
         line written as its summary ('Progetti di legge su celiachia e
         interrogazioni in Commissione Salute').
    tos  Toscana: 'Prossime sedute del Consiglio' (the Council's calendar,
         about three months ahead) and 'Ordine del giorno di seduta' (the
         next sitting's full order of the day, one table per section).
    mar  Marche: the index of sittings and the convened sitting's order of
         the day (odg.php?convocazione=N, Latin-1 HTML).
    tn   Provincia autonoma di Trento: 'Convocazioni per data' (the
         Council's and committees' convocations, two weeks or more ahead)
         as booked slots; the order of the day is loaded by script.
    cal  Calabria: the home page links each committee's next sitting
         (VisualizzaOdG?Comm=...&DataSeduta=...), whose page prints the
         numbered order of the day.

Every other council is declared with what was tried (status no-route or
blocked). Classification: taxonomy-it for it; Bolzano would need German.
"""

from __future__ import annotations

import datetime
import html as _html
import json
import re

from src import regional_agenda as ra
from src.http import FetchError

CC = "it"
TAXONOMIES = (("taxonomy-it.yaml", "it"),)
THROTTLES = {"www.cr.campania.it": 10.0, "www.consiglio.regione.lazio.it": 1.5,
             "www.ars.sicilia.it": 1.5, "www.assemblea.emr.it": 1.5,
             "www.consiglio.regione.toscana.it": 1.5, "www.consiglio.marche.it": 1.5,
             "www.consiglio.provincia.tn.it": 1.5, "www.consiglioregionale.calabria.it": 1.5}
HTML = {"Accept": "text/html"}
MAX_MEETINGS = 30


def _feed():
    return ra.feed(CC)


def pdf_text(blob):
    """The text layer of a PDF; None without pypdf."""
    try:
        import io
        import pypdf
    except ImportError:
        return None
    try:
        reader = pypdf.PdfReader(io.BytesIO(blob))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:                                   # noqa: BLE001 - a bad PDF is a gap
        return None


def _year_for(day, mon, today):
    """ISO date for a day and month printed without a year: this year, or
    the next when the month is well behind today's."""
    t = datetime.date.fromisoformat(today)
    m = ra.month(mon) if not str(mon).isdigit() else int(mon)
    if not m:
        return None
    year = t.year + (1 if m < t.month - 6 else 0)
    return ra.iso(day, m, year)


def _units(ctx, ok, meeting_ids, horizon):
    if ok and horizon:
        return [ra.window(ctx.today, horizon)]
    return [ra.meeting(m) for m in meeting_ids]


def _text(client, url, slug, latin1=False):
    if latin1:
        return client.get_text(url, _feed(), slug, headers=HTML, fallback_encoding="cp1252")
    return client.get_text(url, _feed(), slug, headers=HTML)


# --- Lazio ------------------------------------------------------------------------

LAZ = "https://www.consiglio.regione.lazio.it/"
LAZ_COMM = LAZ + "?vw=homeCommissioni&cid={0}"
_LAZ_DAY = re.compile(r"<h5>\s*\w+\S*\s+(\d{1,2})\s+([a-z]+)\s*</h5>(.*?)(?=<h5>|</div>\s*</div>|$)",
                      re.S | re.I)
_LAZ_ENTRY = re.compile(r'<a href="([^"]*)"[^>]*>\s*<strong>\s*Alle\s+(\d{1,2}[:.]\d\d)\s*</strong>'
                        r'\s*-\s*(.*?)</a>', re.S)


def parse_laz_home(page, today):
    """[{date, time, body, cid}] from the home page's agenda box."""
    i = (page or "").find('id="box_agenda"')
    if i < 0:
        return []
    box = page[i:i + 20000]
    out = []
    for day, mon, block in _LAZ_DAY.findall(box):
        date = _year_for(day, mon, today)
        for href, time, body in _LAZ_ENTRY.findall(block):
            cid = re.search(r"cid=(\d+)", href)
            out.append({"date": date, "time": time.replace(".", ":"),
                        "body": ra.one_line(ra.clean(body)).rstrip(" ."),
                        "cid": cid.group(1) if cid else None,
                        "href": href})
    return out


_LAZ_SEDUTA = re.compile(r'<div class="post-title"><h4>(.*?)</h4></div>\s*<div class="post-meta">'
                         r'<span>(?:<i[^>]*></i>)?(.*?)</span></div>\s*'
                         r'<div class="post-description">(.*?)</div>', re.S)


def parse_laz_committee(page, body, today, cid):
    """{(date, time): [items]} of the sittings a committee's page prints."""
    out = {}
    for title, meta, desc in _LAZ_SEDUTA.findall(page or ""):
        m = re.search(r"(\d{1,2})\s+([a-zA-Z]+)(?:\s+(\d{4}))?\s*-\s*ore\s*(\d{1,2}[:.]\d\d)",
                      ra.one_line(_html.unescape(meta)))
        if not m:
            continue
        date = ra.iso(m.group(1), m.group(2), m.group(3)) if m.group(3) else \
            _year_for(m.group(1), m.group(2), today)
        time = m.group(4).replace(".", ":")
        num = re.search(r"(\d+)", ra.clean(title))
        mid = "laz-{0}-{1}-{2}".format(cid, date, num.group(1) if num else time.replace(":", ""))
        text = ra.one_line(ra.clean(desc))
        points = re.split(r"\s(?=\d{1,2}\)\s)", " " + text)
        items = []
        for p in points:
            p = ra.one_line(p)
            pm = re.match(r"^(\d{1,2})\)\s*(.+)$", p)
            if not pm:
                continue
            items.append(ra.item(date, pm.group(2).rstrip(";. "), body, time, int(pm.group(1)),
                                 mid, None, None, LAZ_COMM.format(cid)))
        out[(date, time)] = items or [ra.item(date, "", body, time, 1, mid,
                                              url=LAZ_COMM.format(cid))]
    return out


def read_laz(client, ctx):
    entries = [e for e in parse_laz_home(_text(client, LAZ, "laz-home", latin1=True), ctx.today)
               if ctx.in_window(e["date"])]
    pages, items, read, ok, gaps = {}, [], [], True, []
    for e in entries[:MAX_MEETINGS]:
        if not e["cid"]:
            mid = "laz-{0}-{1}".format(e["date"], ra.slug(e["body"], 30))
            items.append(ra.item(e["date"], "", e["body"], e["time"], 1, mid, url=LAZ))
            read.append(mid)
            continue
        if e["cid"] not in pages:
            try:
                pages[e["cid"]] = parse_laz_committee(
                    _text(client, LAZ_COMM.format(e["cid"]), "laz-comm-" + e["cid"], latin1=True),
                    e["body"], ctx.today, e["cid"])
            except FetchError as exc:
                ok = False
                pages[e["cid"]] = None
                gaps.append("Lazio committee {0} page not read: {1}".format(e["cid"], str(exc)[:120]))
        sittings = pages[e["cid"]]
        if sittings is None:
            continue
        got = sittings.get((e["date"], e["time"]))
        if got is None:
            mid = "laz-{0}-{1}-{2}".format(e["cid"], e["date"], e["time"].replace(":", ""))
            got = [ra.item(e["date"], "", e["body"], e["time"], 1, mid,
                           url=LAZ_COMM.format(e["cid"]))]
        if got[0]["meeting_id"] not in read:
            items += got
            read.append(got[0]["meeting_id"])
    horizon = max([e["date"] for e in entries], default=None)
    return ra.RegionRead(items, _units(ctx, ok, read, horizon) if entries else
                         [ra.window(ctx.today, ctx.until)],
                         source="consiglio.regione.lazio.it agenda + committee pages",
                         note="{0} meeting(s) on the agenda; Aula orders of the day not read "
                              "(robots.txt)".format(len(entries)), gaps=gaps)


# --- Campania ------------------------------------------------------------------------

CAM = "https://www.cr.campania.it"
CAM_ODG = CAM + "/atti-e-documenti/DG-attivita/ordine-del-giorno-prossime-sedute"


def parse_cam_list(page):
    """[{date, title, url, id}] of the convened sittings."""
    out = []
    for row in re.findall(r'<li class="views-row[^"]*">(.*?)</li>', page or "", re.S):
        title = re.search(r'views-field-value">\s*<span class="field-content">(.*?)</span>', row, re.S)
        link = re.search(r'href="([^"]+)"[^>]*id="(\d+)"', row) or \
            re.search(r'href="([^"]+prendiDocumento[^"]*)"()', row)
        if not title:
            continue
        t = ra.one_line(ra.clean(title.group(1)))
        date = ra.find_date(t)
        if not date:
            continue
        label = t.split(":", 1)[1].strip() if ":" in t else ""
        out.append({"date": date, "title": label, "url": _html.unescape(link.group(1)) if link else None,
                    "id": (link.group(2) if link and link.group(2) else date)})
    return out


def parse_cam_convocation(text, sitting):
    """The points after 'con il seguente ordine del giorno:' ('a) ...',
    '1) ...', '1. ...')."""
    t = text or ""
    i = t.lower().rfind("seguente ordine del giorno")
    if i < 0:
        return []
    body = t[i:].split(":", 1)[1] if ":" in t[i:i + 80] else t[i:]
    tm = re.search(r"ore\s+(\d{1,2})[.:](\d\d)", t[max(0, i - 400):i])
    time = "{0}:{1}".format(tm.group(1), tm.group(2)) if tm else None
    parts = re.split(r"\n\s*(?=(?:\d{1,2}|[a-z])[\)\.]\s)", "\n" + body)
    items = []
    for p in parts:
        p = ra.one_line(p)
        m = re.match(r"^(?:\d{1,2}|[a-z])[\)\.]\s+(.+)$", p)
        if not m:
            continue
        what = re.split(r"\s+(?:Il Presidente|Massimiliano Manfredi)\b", m.group(1))[0]
        what = what.strip(" ;.")
        if len(what) > 8:
            items.append(ra.item(sitting["date"], what, "Consiglio regionale", time,
                                 len(items) + 1, "cam-" + sitting["id"], sitting["title"] or None,
                                 None, sitting["url"]))
    if not items:
        lead = ra.one_line(body)[:600].strip(" ;.")
        if len(lead) > 8:
            items.append(ra.item(sitting["date"], lead, "Consiglio regionale", time, 1,
                                 "cam-" + sitting["id"], sitting["title"] or None, None,
                                 sitting["url"]))
    return items


def read_cam(client, ctx):
    sittings = [s for s in parse_cam_list(_text(client, CAM_ODG, "cam-odg"))
                if ctx.in_window(s["date"])]
    items, read, ok, gaps, nopdf = [], [], True, [], False
    for s in sittings[:MAX_MEETINGS]:
        got = []
        if s["url"] and not ctx.out_of_time():
            try:
                text = pdf_text(client.get_bytes(s["url"], _feed(), "cam-conv-" + s["id"]))
            except FetchError as e:
                ok = False
                gaps.append("Campania convocation {0} not read: {1}".format(s["date"], str(e)[:120]))
                continue
            if text is None:
                nopdf = True
            else:
                got = parse_cam_convocation(text, s)
        if not got:
            got = [ra.item(s["date"], s["title"] if s["title"] and
                           not re.match(r"^seduta( ordinaria)?$", s["title"], re.I) else "",
                           "Consiglio regionale", None, 1, "cam-" + s["id"], url=s["url"])]
        items += got
        read.append("cam-" + s["id"])
    note = "{0} sitting(s) convened".format(len(sittings))
    if nopdf:
        note += "; pypdf not installed, convocations not read"
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)] if ok else
                         [ra.meeting(m) for m in read],
                         source="cr.campania.it ordine del giorno prossime sedute",
                         note=note, gaps=gaps)


# --- Sicilia (ARS) ---------------------------------------------------------------------

ARS = "https://www.ars.sicilia.it"
ARS_PAGES = {"aula": ARS + "/agenda/lavori-aula", "commissione": ARS + "/agenda/sedute-commissioni"}
ARS_DAY = ARS + "/agenda/{0}/{1}"


def parse_ars_dates(page):
    """ISO dates with events, from the agenda page's Drupal settings."""
    m = re.search(r'drupal-settings-json">(.*?)</script>', page or "", re.S)
    if not m:
        return []
    try:
        ev = json.loads(json.loads(m.group(1))["agenda"]["eventi"])
    except (ValueError, KeyError, TypeError):
        return []
    out = []
    for e in ev:
        p = str(e.get("Date") or "").split(",")
        if len(p) == 3:
            d = ra.iso(p[2], p[1], p[0])
            if d:
                out.append(d)
    return sorted(set(out))


def parse_ars_day(fragment, date, kind):
    """The meetings of one day (the JSON's HTML fragment); cancelled ones
    ('disdetta', 'annullata', 'rinviata') are dropped."""
    out = []
    for li in re.findall(r'<li class="([a-z]+)">(.*?)</li>', fragment or "", re.S):
        cls, block = li
        stit = re.search(r'elenco_lavori_stit">(.*?)</span>', block, re.S)
        tit = re.search(r'elenco_lavori_tit">(.*?)</span>', block, re.S)
        ora = re.search(r'elenco_lavori_ora">\s*(?:ore\s*)?(\d{1,2}[:.]\d\d)?', block)
        label = re.search(r'elenco_lavori_label[^"]*">(.*?)</span>', block, re.S)
        link = re.search(r'href="([^"]+)"', block)
        state = ra.clean(label.group(1)).lower() if label else ""
        if re.search(r"disdett|annullat|rinviat|sconvocat", state):
            continue
        name = ra.one_line(ra.clean(tit.group(1))) if tit else ""
        if kind == "aula" or cls == "assemblea":
            body = "Assemblea (Aula)"
        else:
            body = name or (ra.clean(stit.group(1)) if stit else "Commissione")
        mid = "sic-" + (link.group(1).rstrip("/").rsplit("/", 1)[-1] if link else
                        "{0}-{1}".format(date, ra.slug(body, 30)))
        out.append(ra.item(date, "", body, ora.group(1).replace(".", ":") if ora and ora.group(1)
                           else None, 1, mid, detail=name if kind == "aula" else None,
                           url=link.group(1) if link else ARS_PAGES[kind]))
    return out


def read_sic(client, ctx):
    items, ok, gaps, days = [], True, [], 0
    for kind, url in ARS_PAGES.items():
        dates = [d for d in parse_ars_dates(_text(client, url, "sic-" + kind))
                 if ctx.in_window(d)]
        for d in dates[:20]:
            if ctx.out_of_time():
                ok = False
                break
            try:
                data = client.get_json(ARS_DAY.format(kind, d.replace("-", "")), _feed(),
                                       "sic-{0}-{1}".format(kind, d))
            except FetchError as e:
                ok = False
                gaps.append("ARS {0} {1} not read: {2}".format(kind, d, str(e)[:120]))
                continue
            days += 1
            items += parse_ars_day((data or {}).get("html") if isinstance(data, dict) else "",
                                   d, kind)
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)] if ok else
                         [ra.meeting(i["meeting_id"]) for i in items],
                         source="ars.sicilia.it agenda calendar (per-day listings)",
                         note="{0} day(s) with meetings; orders of the day (PDF) not read".format(days),
                         gaps=gaps)


# --- Emilia-Romagna -----------------------------------------------------------------------

EMR_ICS = "https://www.assemblea.emr.it/agenda/ics_view"


def parse_ics(text):
    """[{summary, start, end, url, uid, description}] from an iCalendar
    file (folded lines unfolded)."""
    unfolded = re.sub(r"\r?\n[ \t]", "", text or "")
    out, cur = [], None
    for line in unfolded.splitlines():
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur is not None:
                out.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            k, v = line.split(":", 1)
            k = k.split(";", 1)[0].upper()
            v = v.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\N", "\n")
            cur[{"SUMMARY": "summary", "DTSTART": "start", "DTEND": "end", "URL": "url",
                 "UID": "uid", "DESCRIPTION": "description"}.get(k, k.lower())] = v
    return out


_EMR_COMM = re.compile(r"\b((?:Commission[ei]|Commissioni congiunte|congiunta)[^,:;.]*?)"
                       r"(?:\s+in\s+|\s*[:,;.]|$)", re.I)


def emr_body(summary):
    """'Aula' for the Assembly's sittings, else the committee the summary
    names ('in Commissione Salute' -> 'Commissione Salute')."""
    s = summary or ""
    if re.search(r"\b(Aula|in Assemblea|seduta assembleare|Assemblea legislativa)\b", s, re.I) and \
            not re.search(r"\bCommission", s, re.I):
        return "Aula"
    m = re.search(r"\bCommission[ei]\s+(?:congiunt[ae]\s+)?([A-Za-zÀ-ÿ']{3,})", s)
    if m and m.group(1).lower() not in ("per", "della", "del", "di", "in"):
        return "Commissione " + m.group(1)[0].upper() + m.group(1)[1:]
    if re.search(r"commission", s, re.I):
        return "Commissione"
    return "Assemblea legislativa"


def read_emr(client, ctx):
    events = parse_ics(client.get_text(EMR_ICS, _feed(), "emr-ics", headers={"Accept": "text/calendar"}))
    items = []
    for e in events:
        start = e.get("start") or ""
        if len(start) < 8:
            continue
        date = ra.iso(start[6:8], start[4:6], start[:4])
        if not ctx.in_window(date):
            continue
        time = "{0}:{1}".format(start[9:11], start[11:13]) if len(start) >= 13 else None
        summary = ra.one_line(e.get("summary"))
        uid = (e.get("uid") or "").split("@")[0] or ra.slug(summary, 40)
        items.append(ra.item(date, summary, emr_body(summary), time, 1, "emr-" + uid,
                             ra.one_line(e.get("description")) or None, None, e.get("url")))
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="assemblea.emr.it agenda (iCalendar)",
                         note="one item per agenda event; the summary names its business")


# --- Toscana --------------------------------------------------------------------------------

TOS = "https://www.consiglio.regione.toscana.it"
TOS_PROX = TOS + "/aula/prox-sedute.aspx"
TOS_ODG = TOS + "/default.aspx?nome=odg_seduta"


def parse_tos_calendar(page):
    """[(date, label)] of the programmed sittings."""
    out = []
    for line in ra.clean(page or "").splitlines():
        m = re.match(r"^(\d{1,2})\s+([a-zà-ù]+)\s+(\d{4})\s+(seduta\b.*)$", line.strip(), re.I)
        if m:
            d = ra.iso(m.group(1), m.group(2), m.group(3))
            if d:
                out.append((d, m.group(4)))
    return out


_TOS_KIND = re.compile(r"(?:^|\s)(Pd[a-z]|Prs|Mozione|Ris|Odg|Res)$")


def parse_tos_odg(page):
    """(date, time, [items]) of the next sitting's order of the day: one
    item per table row, the section heading (the committee that reports
    it, or 'Interrogazione a risposta immediata') as its detail."""
    p = page or ""
    head = re.search(r"<strong>\s*(\d{1,2}\s+[a-zà-ù]+\s+\d{4})\s*</strong>([^<]{0,120})", p, re.I)
    if not head:
        return None, None, []
    date = ra.find_date(head.group(1))
    tm = re.search(r"ore\s+(\d{1,2})[:.](\d\d)", head.group(2))
    time = "{0}:{1}".format(tm.group(1), tm.group(2)) if tm else None
    items = []
    for table in re.findall(r"<table[^>]*border=\"1\"[^>]*>(.*?)</table>", p[head.end():], re.S):
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)
        section, cols = None, None
        for r in rows:
            cells = [ra.one_line(ra.clean(c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            if not cells:
                continue
            if len(cells) == 1 or 'colspan' in r and not cols:
                section = cells[0]
                continue
            low = [c.lower() for c in cells]
            if "titolo" in low or "oggetto" in low:
                cols = low
                continue
            if not cols:
                continue
            # rows carry an extra leading cell (the date of the committee
            # vote) the header does not: read the cells by what they hold
            kind = next((_TOS_KIND.search(c).group(1) for c in cells if _TOS_KIND.search(c)), "")
            numi = next((i for i, c in enumerate(cells) if re.match(r"^\d{1,4}$", c)), None)
            num = cells[numi] if numi is not None else ""
            title = cells[numi + 1] if numi is not None and numi + 1 < len(cells) else ""
            if len(title) < 12:
                long_ = [c for c in cells if len(c) >= 12 and not _TOS_KIND.search(c)]
                title = long_[0] if long_ else ""
            if len(title) < 12:
                continue
            ref = " ".join(x for x in (kind, num) if x) or None
            business = title
            if section and re.match(r"^INTERROGAZION|^INTERPELLANZ|^MOZION|^RISOLUZION", section):
                business = "{0} n. {1}: {2}".format(section.split()[0].capitalize(), num, title) \
                    if num else title
            elif kind:
                business = "{0}: {1}".format(" ".join(x for x in (kind, num) if x), title)
            items.append(ra.item(date, business, "Consiglio regionale", time, len(items) + 1,
                                 "tos-" + (date or ""), section, ref, TOS_ODG))
    return date, time, items


def read_tos(client, ctx):
    cal = [c for c in parse_tos_calendar(_text(client, TOS_PROX, "tos-prox")) if ctx.in_window(c[0])]
    gaps = []
    try:
        odg_date, odg_time, odg = parse_tos_odg(_text(client, TOS_ODG, "tos-odg"))
    except FetchError as e:
        odg_date, odg = None, []
        gaps.append("Toscana order of the day not read: {0}".format(str(e)[:120]))
    items, seen = [], set()
    if odg_date and ctx.in_window(odg_date) and odg:
        items += odg
        seen.add(odg_date)
    for d, label in cal:
        if d in seen:
            continue
        seen.add(d)
        items.append(ra.item(d, "", "Consiglio regionale", None, 1, "tos-" + d, label, None, TOS_PROX))
    units = [ra.window(ctx.today, ctx.until)] if not gaps else [ra.meeting(i["meeting_id"])
                                                               for i in items if i["business"] == ""]
    return ra.RegionRead(items, units, source="consiglio.regione.toscana.it prossime sedute + odg",
                         note="{0} sitting(s) programmed".format(len(cal)), gaps=gaps)


# --- Marche ---------------------------------------------------------------------------------

MAR = "https://www.consiglio.marche.it/attivita/assemblea/sedute/"
MAR_INDEX = MAR + "index.php"
MAR_ODG = MAR + "odg.php?convocazione={0}"


def parse_mar_index(page):
    """[(convocazione id, date)] of the sittings on the index page."""
    out = []
    # the index prints 'NN del DD/MM/YYYY ... odg.php?convocazione=N' per sitting
    for m in re.finditer(r"(\d{1,2}/\d{1,2}/\d{4})(.{0,1500}?)odg\.php\?convocazione=(\d+)",
                         page or "", re.S):
        d = ra.find_date(m.group(1))
        if d and m.group(3) not in [c for c, _ in out] and d not in [x for _, x in out]:
            out.append((m.group(3), d))
    return out


_MAR_ACT = re.compile(r"^(?:n\.\s*\d|Propost|Mozion|Interrogazion|Interpellanz|Risoluzion|"
                      r"Relazion|Elezion|Nomin|Deliberazion|Comunicazion|Petizion|Parere|Atto|"
                      r"Question|Programma|Piano|Rendiconto|Bilancio|Assestamento|Ordine)", re.I)


def parse_mar_odg(page, cid):
    """Items of a convened sitting: one per act ('n. 472 a iniziativa del
    Consigliere ... «title»'), its section ('Interrogazioni', 'Proposte di
    legge') as detail."""
    text = ra.clean(re.sub(r"<script.*?</script>", "", page or "", flags=re.S))
    i = text.find("con il seguente ordine del giorno")
    if i < 0:
        return None, None, []
    lead = text[max(0, i - 400):i]
    date = ra.find_date(lead) or ra.find_date(text)
    tm = re.search(r"ore\s+(\d{1,2})[:.](\d\d)", lead)
    time = "{0}:{1}".format(tm.group(1), tm.group(2)) if tm else None
    body = text[i:].split(":", 1)[1] if ":" in text[i:i + 60] else text[i:]
    stop = re.search(r"\n(?:IL PRESIDENTE|Assemblea legislativa delle Marche\s*\n|Piazza Cavour|"
                     r"Via Tiziano 44)", body)
    if stop:
        body = body[:stop.start()]
    items, section = [], None
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.endswith(":") and not re.match(r"^n\.\s*\d", line) and len(line) < 120:
            section = line.rstrip(":").strip()
            continue
        for seg in re.split(r";\s*(?=n\.\s*\d)", line):
            seg = ra.one_line(seg).strip(" ;")
            if len(seg) < 12 or not re.match(_MAR_ACT, seg):
                continue
            ref = re.match(r"^((?:[A-Z][a-z]+\s+)?n\.\s*\d+)", seg)
            items.append(ra.item(date, seg, "Assemblea legislativa", time, len(items) + 1,
                                 "mar-" + cid, section, ref.group(1) if ref else None,
                                 MAR_ODG.format(cid)))
    return date, time, items


def read_mar(client, ctx):
    index = parse_mar_index(_text(client, MAR_INDEX, "mar-index", latin1=True))
    future = [(c, d) for c, d in index if ctx.in_window(d)]
    items, read, ok, gaps = [], [], True, []
    for cid, d in future[:6]:
        try:
            _, _, got = parse_mar_odg(_text(client, MAR_ODG.format(cid), "mar-odg-" + cid,
                                            latin1=True), cid)
        except FetchError as e:
            ok = False
            gaps.append("Marche order of the day {0} not read: {1}".format(cid, str(e)[:120]))
            continue
        items += [dict(i, dated=d) for i in got] or [
            ra.item(d, "", "Assemblea legislativa", None, 1, "mar-" + cid, url=MAR_ODG.format(cid))]
        read.append("mar-" + cid)
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)] if ok else
                         [ra.meeting(m) for m in read],
                         source="consiglio.marche.it sedute (odg.php)",
                         note="{0} sitting(s) convened".format(len(future)), gaps=gaps)


# --- Provincia autonoma di Trento ------------------------------------------------------------

TN = "https://www.consiglio.provincia.tn.it"
TN_CONV = TN + "/attivita/convocazioni/Pages/Convocazioni-per-data.aspx"
_TN_ITEM = re.compile(r"<a href='(/_layouts/15/dispatcher/doc_dispatcher\.aspx\?app=conv&(?:amp;)?"
                      r"at_id=(\d+))' class='item convocazione-item[^']*'>(.*?)</a>", re.S)


def parse_tn(page):
    """[{date, time, body, at_id, url}] of the convocations listed."""
    out, seen = [], set()
    for path, at_id, block in _TN_ITEM.findall(page or ""):
        date = re.search(r"<span class='data'>(\d{1,2}/\d{1,2}/\d{4})</span>", block)
        body = re.search(r"<div class='h3'>(.*?)</div>", block, re.S)
        when = re.search(r"ore\s+(\d{1,2}[:.]\d\d)", block)
        if not date or not body:
            continue
        d = ra.find_date(date.group(1))
        t = when.group(1).replace(".", ":") if when else None
        b = re.sub(r"^XVII\s+", "", ra.one_line(ra.clean(body.group(1))))
        k = (d, t, b)
        if k in seen:
            continue
        seen.add(k)
        out.append({"date": d, "time": t, "body": b, "at_id": at_id,
                    "url": TN + _html.unescape(path)})
    return out


def read_tn(client, ctx):
    convs = [c for c in parse_tn(_text(client, TN_CONV, "tn-conv")) if ctx.in_window(c["date"])]
    items = [ra.item(c["date"], "", c["body"], c["time"], 1,
                     "tn-{0}-{1}".format(c["at_id"], (c["time"] or "").replace(":", "")),
                     url=c["url"]) for c in convs]
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="consiglio.provincia.tn.it convocazioni per data",
                         note="{0} convocation(s); orders of the day loaded by script, "
                              "kept as booked slots".format(len(convs)))


# --- Calabria ----------------------------------------------------------------------------------

CAL = "https://www.consiglioregionale.calabria.it"
CAL_HOME = CAL + "/"


def parse_cal_home(page):
    """[url] of the committees' next sittings (VisualizzaOdG)."""
    out = []
    for href in re.findall(r'href="(/portale/Istituzione/[^"]*VisualizzaOdG\?[^"]+)"', page or ""):
        u = CAL + _html.unescape(href)
        if u not in out:
            out.append(u)
    return out


def parse_cal_odg(page, url):
    """Items of one sitting: '1) Proposta di Legge n.81/13^ ... recante:
    "..."'."""
    q = dict(re.findall(r"[?&]([A-Za-z]+)=([^&]*)", url))
    date = ra.find_date(q.get("DataSeduta", ""))
    time = q.get("OraSeduta") or None
    text = ra.clean(re.sub(r"<script.*?</script>", "", page or "", flags=re.S))
    head = re.search(r"(?:^|\n)([^\n]*(?:Commissione|Consiglio)[^\n]*)\nSeduta\s+del", text)
    body = head.group(1).strip() if head else ("Commissione " + q.get("Comm", "")).strip()
    body = body.split(" - ")[0] if " - " in body and len(body) > 80 else body
    i = text.find("Ordine del giorno")
    rest = text[i:] if i >= 0 else ""
    mid = "cal-{0}-{1}-{2}".format(ra.slug(q.get("Comm", "x"), 20), date, (time or "").replace(":", ""))
    items = []
    for m in re.finditer(r"\n(\d{1,2})\)\s*(.+)", rest):
        what = ra.one_line(m.group(2))
        what = re.sub(r"\s*-\s*Relatore:.*$", "", what)
        ref = re.search(r"\b(Proposta di (?:Legge|Provvedimento amministrativo|Deliberazione)"
                        r"[^\d]{0,6}n\.?\s*[\d/^]+)", what, re.I)
        items.append(ra.item(date, what, body, time, int(m.group(1)), mid, None,
                             ref.group(1) if ref else None, url))
    if not items and date:
        items = [ra.item(date, "", body, time, 1, mid, url=url)]
    return items


def read_cal(client, ctx):
    urls = parse_cal_home(_text(client, CAL_HOME, "cal-home"))
    items, read, ok, gaps = [], [], True, []
    for u in urls[:MAX_MEETINGS]:
        q = dict(re.findall(r"[?&]([A-Za-z]+)=([^&]*)", u))
        if not ctx.in_window(ra.find_date(q.get("DataSeduta", "")) or ""):
            continue
        try:
            got = parse_cal_odg(_text(client, u, "cal-odg-{0}-{1}".format(
                q.get("Comm", "x"), (q.get("DataSeduta") or "").replace("/", ""))), u)
        except FetchError as e:
            ok = False
            gaps.append("Calabria sitting {0} not read: {1}".format(u, str(e)[:120]))
            continue
        if got and got[0]["meeting_id"] not in read:
            items += got
            read.append(got[0]["meeting_id"])
    return ra.RegionRead(items, [ra.meeting(m) for m in read] if not ok else
                         [ra.window(ctx.today, max([i["dated"] for i in items], default=ctx.today))],
                         source="consiglioregionale.calabria.it committees' next sittings",
                         note="{0} sitting(s) linked; the Council's own sittings are not "
                              "listed there".format(len(read)), gaps=gaps)


REGIONS = {
    "lom": ra.region("Lombardia", status="blocked",
                     note="consiglio.regione.lombardia.it robots.txt: 'User-agent: *' "
                          "'Disallow: /' (agendas, sedute and odg all under it); the "
                          "council's open data on dati.lombardia.it has acts, members and "
                          "laws but no sittings or agenda dataset (catalogue searched)"),
    "laz": ra.region("Lazio", reader=read_laz),
    "cam": ra.region("Campania", reader=read_cam),
    "sic": ra.region("Sicilia (ARS)", reader=read_sic),
    "ven": ra.region("Veneto", status="blocked",
                     note="consiglioveneto.it answers 403 (Akamai) to every request, "
                          "robots.txt included (16 October 2026); never bypassed"),
    "emr": ra.region("Emilia-Romagna", reader=read_emr),
    "pie": ra.region("Piemonte", status="no-route",
                     note="cr.piemonte.it did not answer from the UK (timeout, 16 October "
                          "2026, as on 12 October)"),
    "pug": ra.region("Puglia", status="blocked",
                     note="consiglio.puglia.it robots.txt: 'User-agent: *' 'Disallow: /'"),
    "tos": ra.region("Toscana", reader=read_tos),
    "cal": ra.region("Calabria", reader=read_cal),
    "sar": ra.region("Sardegna", status="no-route",
                     note="consiglio.regione.sardegna.it refused the connection / timed out "
                          "from the UK (16 October 2026)"),
    "lig": ra.region("Liguria", status="no-route",
                     note="consiglio.liguria.it did not answer (connection failed, 16 October "
                          "2026); the council's pages inside regione.liguria.it carry news, "
                          "no agenda list"),
    "mar": ra.region("Marche", reader=read_mar),
    "abr": ra.region("Abruzzo", status="no-route",
                     note="consiglio.regione.abruzzo.it timed out from the UK (16 October 2026)"),
    "fvg": ra.region("Friuli Venezia Giulia", status="no-route",
                     note="consiglio.regione.fvg.it home redirects to a 404 for our client; "
                          "its acts are an ASP.NET postback form and robots.txt disallows "
                          "/pagine/attivita/; no agenda feed found"),
    "tn": ra.region("Provincia autonoma di Trento", reader=read_tn),
    "bz": ra.region("Provincia autonoma di Bolzano (Südtiroler Landtag)", status="no-route",
                    note="consiglio-bz.org serves a JavaScript shell (3.6 KB) with no agenda "
                         "in the page; the data API behind it was not probed"),
    "taa": ra.region("Trentino-Alto Adige (Consiglio regionale)", status="no-route",
                     note="consiglio.regione.taa.it: few sittings, robots.txt disallows "
                          "/api/; no agenda page found"),
    "umb": ra.region("Umbria", status="no-route",
                     note="alumbria.it now answers (it timed out on 12 October); its "
                          "'odg-assemblea' and 'convocazioni-assemblea' are an Angular app "
                          "(acta.alumbria.it) with no server-rendered list; the home page "
                          "shows only the next four days' events"),
    "bas": ra.region("Basilicata", status="blocked",
                     note="consiglio.basilicata.it is a JavaScript shell over /consiglio-api, "
                          "which robots.txt disallows"),
    "mol": ra.region("Molise", status="no-route",
                     note="consiglio.regione.molise.it answers HTTP 500 (16 October 2026; a "
                          "self-signed certificate on 12 October)"),
    "vda": ra.region("Valle d'Aosta", status="no-route",
                     note="consiglio.vda.it timed out from the UK (16 October 2026)"),
}
