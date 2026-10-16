"""Canada: the provincial and territorial legislatures' forward business
(src/regional_agenda.py; 16 October 2026).

Region codes are the provincial collector's (src/ingest/prov_<code>.py,
tools/prov_collect.py): on, qc, bc, ab, sk, mb, nb, ns, nl, plus pe, yt, nt
and nu for the legislatures it does not read. Each reader takes what the
legislature itself publishes ahead of the sitting, and only by a route its
robots.txt allows (docs/canada-provinces-scope.md, "Forward agenda"):

  on  ola.org: the next sitting day's Orders and Notices Paper (one item per
      bill or government order standing on it, reference = the bill), the
      private members' ballot list (dated items weeks ahead) and the
      Assembly calendar's day view (/en/ajax/calendar-month/<date>: House
      sittings and committee meetings with their business). robots.txt
      disallows /*? only; every URL here is a path.
  qc  assnat.qc.ca: the weekly calendar of the Assembly's and committees'
      sittings (calendrier-travaux.html, then each "Semaine suivante" link
      while one is printed). French text: taxonomy-qc plus taxonomy.yaml.
  bc  leg.bc.ca: the parliamentary calendar's events (In Session, Speech
      from the Throne, Budget Day); the Orders of the Day load in the
      browser from LIMS and are not read (the House is dissolved for the
      24 October 2026 election).
  ab  assembly.ab.ca: the Order Paper PDFs listed for coming sitting days
      (docs.assembly.ab.ca) and the committees' Upcoming Meeting Dates.
  sk  legassembly.sk.ca: the Assembly records calendar's own JSON
      (/api/days: sitting and committee days; /api/documents: Orders of the
      Day and meeting notices for a date range), each Orders of the Day in
      its HTML edition (docs.legassembly.sk.ca, windows-1252).
  mb  gov.mb.ca/legislature: the current Order Paper PDF, the Sessional
      Order (dated business for the rest of the sitting) and the committee
      meeting notices (a calendar page; each notice PDF lists the bills).
  nb  legnb.ca: the legislative calendar by month (House sittings and
      committee meetings); robots.txt asks a 10-second crawl-delay.
  ns  nslegislature.ca: the Legislature's own iCal feeds (House sittings,
      committee meetings with their topic); crawl-delay 10.
  nl  assembly.nl.ca: the newest session's Order Papers dated today or later.
  nt  ntassembly.ca: the next sitting day's Orders of the Day (PDF) and the
      committees' upcoming meetings.

Not read: Prince Edward Island (every page, the home page included, answers
a Radware CAPTCHA), Yukon (Cloudflare challenge, robots.txt included), and
Nunavut (no order paper or agenda is published ahead; the sitting calendar
is a colour-coded PDF with no text for the days).
"""

from __future__ import annotations

import datetime
import html
import json
import re
from urllib.parse import urljoin

from src import regional_agenda as ra

CC = "ca"
TAXONOMIES = (("taxonomy.yaml", "ca"),)
FEED = ra.feed(CC)
THROTTLES = {"www.legnb.ca": 10.0, "nslegislature.ca": 10.0}

MONTHS_EN = ("january", "february", "march", "april", "may", "june", "july", "august",
             "september", "october", "november", "december")


# --- shared helpers ----------------------------------------------------------

def _text(client, url, slug):
    return client.get_text(url, FEED, slug, archive=False)


def _cp1252(client, url, slug):
    raw = client.get_bytes(url, FEED, slug, archive=False)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _pdf(client, url, slug):
    from src.prov_fetch import pdf_text
    return pdf_text(client.get_bytes(url, FEED, slug, archive=False))


def en_date(text):
    """ISO date of 'October 27, 2026' / 'Oct 27, 2026' / 'Tuesday, October 27, 2026'."""
    m = re.search(r"\b([A-Z][a-z]{2,8})\.?\s+(\d{1,2})\s*,?\s+(\d{4})\b", text or "")
    return ra.iso(m.group(2), m.group(1), m.group(3)) if m and ra.month(m.group(1)) else None


def weekdays(start, end, days=(0, 1, 2, 3, 4)):
    d = datetime.date.fromisoformat(start)
    stop = datetime.date.fromisoformat(end)
    while d <= stop:
        if d.weekday() in days:
            yield d.isoformat()
        d += datetime.timedelta(days=1)


def cut(text, limit=400):
    t = ra.one_line(text)
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + " ..."


def lines_of(text):
    return [ra.one_line(x) for x in (text or "").splitlines() if ra.one_line(x)]


def tba_for(items, sittings, body, prefix):
    """One 'to be announced' item for each sitting date with no item for body."""
    have = {it["dated"] for it in items if it["body"] == body}
    return [ra.item(d, "", body, item_time=t, meeting_id="{0}-{1}".format(prefix, d))
            for d, t in sorted(sittings.items()) if d not in have]


# --- Ontario -------------------------------------------------------------------

ON_BASE = "https://www.ola.org"
ON_HOUSE_DOCS = ON_BASE + "/en/legislative-business/house-documents"
ON_DAY = ON_BASE + "/en/ajax/calendar-month/{0}"
ON_BODY = "Legislative Assembly"
ON_OP_LINK = re.compile(
    r'href="(/en/legislative-business/house-documents/parliament-\d+/session-\d+/'
    r'(\d{4}-\d{2}-\d{2})/orders-notices)"')
ON_ORDER = re.compile(r"^((?:G|M|D|Pr)\d+)\.\s+(.+)$")
ON_BILL = re.compile(r"^(?P<stage>.+?) of Bill (?P<no>\S+?)\s*,\s*(?P<title>.+?)\.\s+(?P<rest>.*)$")


def on_order_papers(session_html, today, until):
    """[(date, url)] of the Orders and Notices Papers the session page links
    for today or later."""
    out = {}
    for path, d in ON_OP_LINK.findall(session_html or ""):
        if today <= d <= until:
            out[d] = urljoin(ON_BASE, path)
    return sorted(out.items())


def on_english(page):
    """The order paper's English column: every lang="fr" cell dropped."""
    return re.sub(r'<td[^>]*lang="fr".*?</td>', "", page or "", flags=re.S)


def _on_section(lines, start, stops):
    out, on = [], False
    for line in lines:
        if line == start:
            on = True
            continue
        if on and line in stops:
            break
        if on:
            out.append(line)
    return out


ON_HEADS = {"PRIVATE BILLS", "GOVERNMENT ORDERS", "PRIVATE MEMBERS’ PUBLIC BUSINESS", "NOTICES",
            "PRIVATE MEMBERS' PUBLIC BUSINESS", "BUSINESS IN STANDING COMMITTEES",
            "WRITTEN QUESTIONS", "BALLOT LIST", "PRIVATE MEMBERS’ NOTICES OF MOTION"}


def parse_on_orders(page, dated, url=None):
    """Items of one Orders and Notices Paper: each bill standing on the
    Orders (G/M/D/Pr), each government order, and each private members'
    ballot item with its 'To be debated' date (weeks ahead)."""
    lines = lines_of(ra.clean(on_english(page)))
    items, order = [], 0
    bills = _on_section(lines, "LEGISLATION (BILLS)", ON_HEADS - {"PRIVATE BILLS"})
    seen_bills = set()
    for line in bills:
        m = ON_ORDER.match(line)
        if not m:
            continue
        b = ON_BILL.match(m.group(2))
        order += 1
        if b:
            no = b.group("no")
            business = "{0}: Bill {1}, {2}".format(b.group("stage"), no, b.group("title"))
            detail, ref = b.group("rest"), "Bill {0}".format(no)
            seen_bills.add(no)
        else:
            business, detail, ref = m.group(2), None, m.group(1)
        items.append(ra.item(dated, cut(business), ON_BODY, order=order,
                             meeting_id="on-op-{0}".format(dated), detail=detail,
                             reference=ref, url=url))
    gov = _on_section(lines, "GOVERNMENT ORDERS", ON_HEADS - {"GOVERNMENT ORDERS"})
    for line in gov:
        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if not m:
            continue
        order += 1
        items.append(ra.item(dated, cut("Government Order {0}: {1}".format(m.group(1), m.group(2))),
                             ON_BODY, order=order, meeting_id="on-op-{0}".format(dated),
                             detail=m.group(2), reference="Government Order {0}".format(m.group(1)),
                             url=url))
    # The private members' ballot list: "To be debated <date>" then the item.
    pm, on = [], False
    for line in lines:
        if line.startswith("(Precedence in accordance with Standing Order"):
            on = True
            continue
        if on and line in ("NOTICES", "PRIVATE MEMBERS’ NOTICES OF MOTION"):
            break
        if on:
            pm.append(line)
    i = 0
    while i < len(pm):
        m = re.match(r"^To be debated (today|.+?)\.", pm[i])
        if not m:
            i += 1
            continue
        when = dated if m.group(1) == "today" else en_date(m.group(1))
        body_lines = []
        j = i + 1
        while j < len(pm) and not re.match(r"^To be debated ", pm[j]) and not re.match(r"^\d+$", pm[j]):
            body_lines.append(pm[j])
            j += 1
        i = j
        if not when or not body_lines:
            continue
        first = body_lines[0]
        bm = ON_ORDER.match(first)
        if bm:
            text = bm.group(2).split(" / ")[0]
            b = ON_BILL.match(text + " x")
            no = b.group("no") if b else None
            if when == dated and no in seen_bills:
                continue       # already standing on today's Orders
            business = "Private members' public business: " + (
                "{0}: Bill {1}, {2}".format(b.group("stage"), no, b.group("title")) if b else text)
            ref = "Bill {0}".format(no) if no else bm.group(1)
            detail = None
        else:
            mm = re.search(r"Notice of Motion No\.\s*(\d+)", first)
            motion = " ".join(body_lines[1:])
            text = motion.split(" — ", 1)[-1] if " — " in motion else motion
            business = "Private members' public business: motion {0}: {1}".format(
                mm.group(1) if mm else "", text)
            ref = "Motion {0}".format(mm.group(1)) if mm else None
            detail = motion
        order += 1
        items.append(ra.item(when, cut(business), ON_BODY, order=order,
                             meeting_id=("on-op-{0}".format(dated) if when == dated
                                         else "on-pmb-{0}".format(when)),
                             detail=detail, reference=ref, url=url))
    return items


ON_CARD = re.compile(r'class="calendar-event-filter-item" data-event-type="([a-z-]+)"')


def parse_on_day(page, dated):
    """The calendar's day view: [('house'|'committee', time, body, business,
    detail)] (tours and events are left out)."""
    out = []
    parts = ON_CARD.split(page or "")
    for kind, chunk in zip(parts[1::2], parts[2::2]):
        if kind not in ("house-sitting", "committee-meetings"):
            continue
        t = re.search(r'class="col-sm-12 col-md-12 col-lg-12 time">\s*(.*?)</div>', chunk, re.S)
        loc = re.search(r'class="col location">(.*?)</div>', chunk, re.S)
        head = re.search(r'class="event-headline">(.*?)</div>', chunk, re.S)
        agenda = re.search(r'class="agenda-link">(.*?)</div>', chunk, re.S)
        proc = re.search(r'class="committee-proceeding">(.*?)</div>', chunk, re.S)
        g = (lambda m: ra.one_line(ra.clean(m.group(1))) if m else "")
        business = re.sub(r"^Business:\s*", "", g(agenda))
        if kind == "house-sitting":
            out.append(("house", g(t), ON_BODY, "", None))
        else:
            detail = "; ".join(x for x in (g(proc), g(loc)) if x) or None
            out.append(("committee", g(t), g(head) or "Committee", business, detail))
    return out


def read_on(client, ctx):
    from src.ingest.prov_on import parse_sessions
    sessions = parse_sessions(_text(client, ON_HOUSE_DOCS, "on-sessions"))
    if not sessions:
        raise ValueError("no session on {0}".format(ON_HOUSE_DOCS))
    leg, sess = sessions[-1]["code"].split("-")
    session_url = "{0}/parliament-{1}/session-{2}".format(ON_HOUSE_DOCS, leg, sess)
    items, units, gaps = [], [], []
    papers = on_order_papers(_text(client, session_url, "on-session"), ctx.today, ctx.until)
    for d, url in papers:
        items += parse_on_orders(_text(client, url, "on-op-" + d), d, url)
    sittings, last = {}, None
    for d in weekdays(ctx.today, ctx.until):
        if ctx.out_of_time():
            gaps.append("Ontario calendar read to {0} only: time budget".format(last or "-"))
            break
        try:
            events = parse_on_day(_text(client, ON_DAY.format(d), "on-day-" + d), d)
        except Exception as exc:                  # noqa: BLE001 - one day: a partial gap
            gaps.append("Ontario calendar day {0}: {1}".format(d, str(exc)[:160]))
            break
        last = d
        for n, (kind, t, body, business, detail) in enumerate(events):
            if kind == "house":
                sittings[d] = t or None
            else:
                items.append(ra.item(d, business, body, item_time=t, order=n,
                                     meeting_id="on-cmte-{0}-{1}-{2}".format(
                                         d, ra.slug(body, 30), ra.slug(t, 10)),
                                     detail=detail, url=ON_DAY.format(d)))
    items += tba_for(items, sittings, ON_BODY, "on-house")
    items = [it for it in items if ctx.in_window(it["dated"])]
    if last:
        units.append(ra.window(ctx.today, last))
    note = "Orders and Notices for {0}".format(", ".join(d for d, _ in papers)) if papers else \
        "no Orders and Notices Paper for a coming sitting day yet"
    return ra.RegionRead(items, units, source="ola.org Orders and Notices, ballot list and calendar",
                         note=note, gaps=gaps)


# --- Quebec --------------------------------------------------------------------

QC_BASE = "https://www.assnat.qc.ca"
QC_WEEK = QC_BASE + "/fr/travaux-parlementaires/calendrier-travaux.html"
QC_BODY = "Assemblée nationale"
QC_NEXT = re.compile(r'id="[^"]*lnkSemaineSuivante[^"]*"\s+href="([^"]+)"')


def parse_qc_week(page):
    """(week start, end, [(date, slot, kind, body, business, time, detail, url)],
    next-week URL or None) of one weekly calendar page."""
    m = re.search(r"<h2>\s*Semaine du (\d{1,2}) (\S+) (\d{4}) au (\d{1,2}) (\S+) (\d{4})\s*</h2>",
                  page or "")
    if not m:
        raise ValueError("no week heading on the Quebec calendar")
    start = ra.iso(m.group(1), m.group(2), m.group(3))
    end = ra.iso(m.group(4), m.group(5), m.group(6))
    year, mon0 = int(m.group(3)), ra.month(m.group(2))
    out = []
    for row in re.findall(r"<tr>\s*<th scope=\"row\">(.*?)</tr>", page, re.S):
        day = re.match(r"\s*(?:\w+)\s+(\d{1,2})\s+(\S+?)\s*</th>(.*)", row, re.S)
        if not day:
            continue
        mon = ra.month(day.group(2))
        y = year + 1 if mon and mon0 and mon < mon0 else year
        dated = ra.iso(day.group(1), day.group(2), y)
        for slot, td in enumerate(re.findall(r"<td>(.*?)</td>", day.group(3), re.S)):
            for p in re.findall(r'<p(?:\s+class="[^"]*")?\s*>(.*?)</p>', td, re.S):
                lines = lines_of(ra.clean(p))
                if not lines:
                    continue
                times = [x for x in lines if re.search(r"\d\s*h\b|\bh\s*\d", x)]
                t = times[-1] if times else None
                link = re.search(r'href="([^"]+)"', p)
                url = None
                if link:
                    href = re.sub(r"^/web/\d+/", "", link.group(1))
                    url = urljoin(QC_BASE, href)
                if lines[0].startswith("Séance de l'Assemblée"):
                    out.append((dated, slot, "sitting", QC_BODY, "", t, None, url))
                else:
                    body = lines[0]
                    private = "(Activité privée)" in body
                    body = body.replace("(Activité privée)", "").strip()
                    rest = [x for x in lines[1:] if x != t]
                    business = rest[0] if rest else ""
                    detail = "; ".join(rest[1:] + (["activité privée"] if private else [])) or None
                    out.append((dated, slot, "committee", body, business, t, detail, url))
    nxt = QC_NEXT.search(page)
    return start, end, out, (urljoin(QC_BASE, re.sub(r"^/web/\d+/", "", html.unescape(nxt.group(1))))
                             if nxt else None)


def read_qc(client, ctx):
    items, url, ends, weeks = [], QC_WEEK, [], 0
    seen = set()
    while url and weeks < 9 and not ctx.out_of_time():
        start, end, rows, nxt = parse_qc_week(_text(client, url, "qc-week-{0}".format(weeks)))
        weeks += 1
        if start in seen:
            break
        seen.add(start)
        ends.append(end)
        sitting_days = set()
        for n, (d, slot, kind, body, business, t, detail, link) in enumerate(rows):
            if kind == "sitting":
                if d in sitting_days:
                    continue
                sitting_days.add(d)
                items.append(ra.item(d, "", body, item_time=t, meeting_id="qc-an-" + d, url=link))
            else:
                items.append(ra.item(d, business, body, item_time=t, order=n, detail=detail,
                                     meeting_id="qc-{0}-{1}-{2}".format(
                                         d, ra.slug(body, 30), ra.slug(t or str(slot), 12)),
                                     url=link))
        if end >= ctx.until:
            break
        url = nxt
    items = [it for it in items if ctx.in_window(it["dated"])]
    last = min(max(ends), ctx.until) if ends else None
    units = [ra.window(ctx.today, last)] if last and last >= ctx.today else []
    return ra.RegionRead(items, units, source="assnat.qc.ca calendrier hebdomadaire des travaux",
                         note="calendar read to {0} ({1} week(s))".format(last, weeks))


# --- British Columbia ------------------------------------------------------------

BC_CAL = "https://www.leg.bc.ca/parliamentary-business/parliamentary-calendar"
BC_BODY = "Legislative Assembly"


def parse_bc_calendar(page):
    """[(date, title)] of the calendar's sitting events (In Session ranges
    expanded to their weekdays, Speech from the Throne, Budget Day), and the
    page's ELECTION INFO line if any."""
    m = re.search(r'<script type="application/json" data-drupal-selector="drupal-settings-json">'
                  r'(.*?)</script>', page or "", re.S)
    if not m:
        raise ValueError("no calendar settings on the BC calendar page")
    events = []
    for fc in json.loads(m.group(1)).get("fullCalendarView") or []:
        events += json.loads(fc.get("calendar_options") or "{}").get("events") or []
    out = []
    for e in events:
        title = ra.one_line(e.get("title"))
        low = title.lower()
        if not (low == "in session" or "throne" in low or "budget" in low):
            continue
        start = (e.get("start") or "")[:10]
        end = (e.get("end") or e.get("start") or "")[:10]
        if not start:
            continue
        for d in weekdays(start, max(start, end)):
            out.append((d, "In Session" if low == "in session" else title))
    info = re.search(r"ELECTION INFO\s*</[^>]+>\s*(.*?)</", page, re.S)
    note = ra.one_line(ra.clean(info.group(1))) if info else ""
    if not note:
        c = ra.clean(page)
        k = c.find("ELECTION INFO")
        note = lines_of(c[k:])[1] if k >= 0 and len(lines_of(c[k:])) > 1 else ""
    return sorted(set(out)), note


def read_bc(client, ctx):
    days, note = parse_bc_calendar(_text(client, BC_CAL, "bc-calendar"))
    items = []
    for d, title in days:
        if not ctx.in_window(d):
            continue
        if title == "In Session":
            items.append(ra.item(d, "", BC_BODY, meeting_id="bc-house-" + d, url=BC_CAL))
        else:
            items.append(ra.item(d, title, BC_BODY, meeting_id="bc-house-" + d, url=BC_CAL,
                                 item_type="statement"))
    year_end = "{0}-12-31".format(ctx.today[:4])
    return ra.RegionRead(items, [ra.window(ctx.today, min(ctx.until, year_end))],
                         source="leg.bc.ca parliamentary calendar", note=note)


# --- Alberta ---------------------------------------------------------------------

AB_BASE = "https://www.assembly.ab.ca"
AB_OPS = AB_BASE + "/assembly-business/assembly-records/order-papers"
AB_CMTE = AB_BASE + "/assembly-business/committees"
AB_BODY = "Legislative Assembly"
AB_OP_LINK = re.compile(r'href="(https://docs\.assembly\.ab\.ca/LADDAR_files[^"]*?\\op\\[^"]*?'
                        r'(\d{8})_\d{4}_\d{2}_op\.pdf)"')


def ab_order_papers(listing, today, until):
    out = {}
    for href, ymd in AB_OP_LINK.findall(listing or ""):
        d = "{0}-{1}-{2}".format(ymd[:4], ymd[4:6], ymd[6:])
        if today <= d <= until:
            out[d] = href.replace("\\", "/")
    return sorted(out.items())


AB_HEADS = ("Government Motions", "Government Bills and Orders", "Second Reading",
            "Committee of the Whole", "Third Reading", "Motions Other Than Government Motions",
            "Public Bills and Orders Other Than", "Government Bills and Orders Other Than")


def parse_ab_order_paper(text, dated, url=None):
    """Orders of the Day of an Alberta Order Paper: each motion (numbered)
    and each bill line ('Bill 205 Non-Disclosure Agreements Act — Mrs.
    Johnson'), with the heading it stands under."""
    t = text or ""
    i = t.find("ORDERS OF THE DAY")
    if i < 0:
        return []
    j = min([k for k in (t.find("Written Questions", i), t.find("Motions for Returns", i)) if k > 0]
            or [len(t)])
    raw = [ra.one_line(x) for x in t[i + len("ORDERS OF THE DAY"):j].splitlines()]
    raw = [x for x in raw if x and x != "=====PAGE" and not re.match(r"^\d{1,3}$", x)]
    items, heading, kind, cur = [], "", None, None

    def flush():
        if cur:
            items.append(cur)

    for line in raw:
        if re.match(r"^(?:Referred to the .+|" + "|".join(re.escape(h) for h in AB_HEADS) + r")", line) \
                and not re.match(r"^\d", line) and len(line) < 120:
            flush()
            cur = None
            if line.startswith("Public Bills and Orders Other Than"):
                kind = "pmb"
                heading = "Second Reading"
                continue
            if line.startswith("Government Bills and Orders Other Than"):
                continue
            heading = line
            continue
        mb = re.match(r"^Bill (\d+) (.+)$", line)
        mm = re.match(r"^(\d{1,3})\. (.+)$", line)
        if mb:
            flush()
            cur = {"kind": "bill", "no": mb.group(1), "text": mb.group(2), "heading": heading}
        elif mm:
            flush()
            cur = {"kind": "motion", "no": mm.group(1), "text": mm.group(2), "heading": heading}
        elif cur is not None:
            cur["text"] += " " + line
    flush()
    out = []
    for n, c in enumerate(items, 1):
        text = ra.one_line(c["text"])
        if c["kind"] == "bill":
            title = re.split(r"\s+—\s+", text)[0]
            business = "{0}: Bill {1} {2}".format(c["heading"] or "Bill", c["no"], title)
            ref, detail = "Bill {0}".format(c["no"]), text
        else:
            res = re.search(r"Be it resolved that (.+)", text, re.I)
            label = "Government Motion" if c["heading"] == "Government Motions" else "Motion"
            business = "{0} {1}: {2}".format(label, c["no"], res.group(1) if res else text)
            ref, detail = "Motion {0}".format(c["no"]), text
        out.append(ra.item(dated, cut(business), AB_BODY, order=n, meeting_id="ab-op-" + dated,
                           detail=detail, reference=ref, url=url))
    return out


def parse_ab_committees(page):
    """[(date, time, committee, business, agenda url)] of Upcoming Meeting Dates."""
    out = []
    for date_td, loc_td in re.findall(
            r'<td headers="[^"]*meet-date"[^>]*>(.*?)</td>\s*<td headers="[^"]*meet-loc"[^>]*>(.*?)</td>',
            page or "", re.S):
        d = en_date(ra.clean(date_td))
        tm = re.search(r"<small[^>]*>(.*?)</small>", date_td, re.S)
        t = ra.one_line(ra.clean(tm.group(1))) if tm else None
        name = re.search(r"<a [^>]*>(.*?)</a>", loc_td, re.S)
        small = re.search(r"<small[^>]*>(.*?)</small>", loc_td, re.S)
        lines = lines_of(ra.clean(small.group(1))) if small else []
        lines = [x for x in lines if x not in ("Agenda", "Video")]
        business = "; ".join(lines[1:]) if len(lines) > 1 else ""
        agenda = re.search(r'href="([^"]+agenda\.pdf)"', loc_td)
        if d and name:
            out.append((d, t, ra.one_line(ra.clean(name.group(1))), business,
                        agenda.group(1) if agenda else None))
    return out


def read_ab(client, ctx):
    items, units, gaps = [], [], []
    papers = ab_order_papers(_text(client, AB_OPS, "ab-order-papers"), ctx.today, ctx.until)
    for d, url in papers:
        try:
            items += parse_ab_order_paper(_pdf(client, url, "ab-op-" + d), d, url)
            units.append(ra.day(d, AB_BODY))
        except Exception as exc:                  # noqa: BLE001 - one paper: a partial gap
            gaps.append("Alberta Order Paper {0}: {1}".format(d, str(exc)[:160]))
    try:
        for n, (d, t, body, business, agenda) in enumerate(
                parse_ab_committees(_text(client, AB_CMTE, "ab-committees"))):
            if ctx.in_window(d):
                items.append(ra.item(d, business, body, item_time=t, order=n, url=agenda or AB_CMTE,
                                     meeting_id="ab-cmte-{0}-{1}".format(d, ra.slug(body, 40))))
        cmte_ok = True      # every meeting in the window is on that one page
    except Exception as exc:                      # noqa: BLE001
        gaps.append("Alberta committees' upcoming meetings: {0}".format(str(exc)[:160]))
        cmte_ok = False
    if cmte_ok and not gaps:
        units = [ra.window(ctx.today, ctx.until)]
    items = [it for it in items if ctx.in_window(it["dated"])]
    note = ("Order Paper for {0}".format(", ".join(d for d, _ in papers)) if papers
            else "no Order Paper for a coming sitting day yet")
    return ra.RegionRead(items, units, source="assembly.ab.ca Order Papers and committee meetings",
                         note=note, gaps=gaps)


# --- Saskatchewan ------------------------------------------------------------------

SK_BASE = "https://www.legassembly.sk.ca"
SK_DAYS = SK_BASE + "/api/days"
SK_DOCS = SK_BASE + "/api/documents?start={0}&end={1}&committee=&type=&sort=committee"
SK_BODY = "Legislative Assembly"


def parse_sk_days(data, today, until):
    """({date: kind}) of sitting (1), committee (2) and both (3) days in the window."""
    out = {}
    for d in data or []:
        dated = (d.get("date") or "")[:10]
        if today <= dated <= until and d.get("dayType") in (1, 2, 3):
            out[dated] = d["dayType"]
    return out


def parse_sk_orders(page, dated, url=None):
    """Items of one Routine Proceedings and Orders of the Day (HTML edition):
    each numbered item under its heading (the headings are the edition's own
    table of contents)."""
    text = ra.clean(page or "")
    lines = lines_of(text)
    try:
        toc0 = next(i for i, x in enumerate(lines) if "TOC" in x)
        body0 = next(i for i, x in enumerate(lines) if i > toc0 and x.startswith("SECOND SESSION")
                     or i > toc0 and re.match(r"^[A-Z]+ SESSION", x))
    except StopIteration:
        toc0, body0 = 0, 0
    heads = set(lines[toc0 + 1:body0]) | {"ROUTINE PROCEEDINGS", "ORDERS OF THE DAY"}
    heads.add(re.sub(r"^.*?ROUTINE PROCEEDINGS$", "ROUTINE PROCEEDINGS", lines[toc0]) if lines else "")
    try:
        start = next(i for i, x in enumerate(lines) if i > body0 and x == "PRAYERS")
    except StopIteration:
        start = body0
    items, heading, cur = [], "", None
    for line in lines[start + 1:]:
        if line.startswith("Disclaimer:"):
            break
        if line in heads:
            if cur:
                items.append(cur)
                cur = None
            heading = line
            continue
        m = re.match(r"^(\d{1,3})\.\s*(.*)$", line)
        if m:
            if cur:
                items.append(cur)
            cur = {"heading": heading, "text": m.group(2)}
        elif cur is not None:
            cur["text"] += "\n" + line
    if cur:
        items.append(cur)
    out = []
    for n, c in enumerate(items, 1):
        head = c["heading"].split(" / ")[0]
        txt = ra.one_line(c["text"])
        bill = re.search(r"Bill No\.\s*(\d+)\s*[–—\-]?\s*(.*)", txt)
        motion = re.search(r"motion no\.\s*(\d+)", txt, re.I)
        if bill:
            title = re.split(r"\s+/\s+", bill.group(2))[0]
            title = re.sub(r"\s*\([^()]*\)\s*(?:PRINTED|IMPRIM).*$", "", title).strip(" –—-\ufffd")
            stage = head
            if "first reading" in txt.lower():
                stage = "First reading"
            business = "{0}: Bill No. {1} – {2}".format(stage, bill.group(1), title)
            ref = "Bill No. {0}".format(bill.group(1))
        elif motion:
            body = c["text"].split("\n")
            that = next((x for x in body if x.startswith("That ")), txt)
            business = "{0}: motion no. {1}: {2}".format(head, motion.group(1), that)
            ref = "Motion No. {0}".format(motion.group(1))
        else:
            business, ref = "{0}: {1}".format(head, txt), None
        out.append(ra.item(dated, cut(business), SK_BODY, order=n, meeting_id="sk-od-" + dated,
                           detail=txt, reference=ref, url=url))
    return out


def read_sk(client, ctx):
    days = parse_sk_days(client.get_json(SK_DAYS, FEED, "sk-days", archive=False), ctx.today, ctx.until)
    docs = client.get_json(SK_DOCS.format(ctx.today, ctx.until), FEED, "sk-docs", archive=False) or []
    items, gaps, read_days = [], [], set()
    for doc in docs:
        dated = (doc.get("start") or "")[:10]
        kind = doc.get("documentType") or doc.get("title") or ""
        if not ctx.in_window(dated):
            continue
        if kind == "Orders of the Day" and doc.get("htmlUrl"):
            try:
                items += parse_sk_orders(_cp1252(client, doc["htmlUrl"], "sk-od-" + dated), dated,
                                         doc["htmlUrl"])
                read_days.add(dated)
            except Exception as exc:              # noqa: BLE001
                gaps.append("Saskatchewan Orders of the Day {0}: {1}".format(dated, str(exc)[:160]))
        elif "notice" in kind.lower() or "meeting" in kind.lower():
            body = doc.get("committee") or "Committee"
            items.append(ra.item(dated, "", body, item_time=doc.get("timeOfDay"),
                                 meeting_id="sk-cmte-{0}-{1}".format(dated, ra.slug(body, 30)),
                                 url=doc.get("mainUrl")))
    sittings = {d: None for d, k in days.items() if k in (1, 3)}
    items += tba_for(items, sittings, SK_BODY, "sk-house")
    have_cmte = {it["dated"] for it in items if it["body"] != SK_BODY}
    for d, k in sorted(days.items()):
        if k in (2, 3) and d not in have_cmte:
            items.append(ra.item(d, "", "Committee meeting (committee not yet named)",
                                 meeting_id="sk-cmte-" + d))
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="legassembly.sk.ca records calendar (api/days, api/documents)",
                         note="Orders of the Day for {0}".format(", ".join(sorted(read_days)))
                         if read_days else "no Orders of the Day for a coming sitting day yet",
                         gaps=gaps)


# --- Manitoba ------------------------------------------------------------------------

MB_BASE = "https://www.gov.mb.ca/legislature"
MB_OP = MB_BASE + "/business/orderpaper.pdf"
MB_CAL = MB_BASE + "/business/calendar.html"
MB_NOTICES = MB_BASE + "/committees/meeting_notices.html"
MB_BODY = "Legislative Assembly"
MB_BILL = re.compile(r"\(No\.\s*(\d+)\)\s*[–-]\s*(.+?)(?:/\s*Loi\b|$)", re.S)


def parse_mb_order_paper(text):
    """(date, [(heading, kind, number, title)]) of the Order Paper."""
    head = re.search(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}",
                     text or "")
    dated = en_date(head.group(0)) if head else None
    out, heading = [], ""
    blocks = re.split(r"\n\s*\n", (text or "").replace("=====PAGE", "\n\n"))
    for b in blocks:
        one = ra.one_line(b)
        if re.match(r"^[A-Z0-9 ,’'()–\-]{6,}:$", one):
            heading = one.rstrip(":").title()
            continue
        if re.match(r"^[A-Z][A-Z ’'–\-]{5,}$", one) and "ORDER PAPER" not in one:
            heading = one.title() if len(one) < 60 else heading
        m = MB_BILL.match(one)
        if m:
            kind = "Resolution" if "resolution" in heading.lower() else "Bill"
            title = m.group(2).strip()
            out.append((heading, kind, m.group(1), title))
    return dated, out


def parse_mb_sessional_order(text):
    """[(date, block text, [(bill no, title)])] of the Sessional Order's dated blocks."""
    t = re.sub(r"Sessional Order \d{4} – .+? Page \d+", " ", text or "")
    t = t.replace("=====PAGE", " ")
    out = []
    parts = re.split(r"\n\s*(\d{1,2})\.\s+On\s+", t)
    for k in range(1, len(parts) - 1, 2):
        block = parts[k + 1]
        d = en_date(block[:60])
        if not d:
            continue
        body = re.split(r"\n\s*\d{1,2}\.\s+(?!On\b)[A-Z]", block)[0]
        bills = [(n, ra.one_line(title)) for n, title in re.findall(
            r"(?:\(No\.\s*(\d+)\)|Bill\s+(\d+))\s*[–-]\s*([^\n]+)", body) and
            [((a or b), c) for a, b, c in re.findall(
                r"(?:\(No\.\s*(\d+)\)|Bill\s+(\d+))\s*[–-]\s*([^\n]+)", body)]]
        bills = [(n, re.split(r",\s+(?:if|and|as|when)\b", t)[0]) for n, t in bills]
        out.append((d, ra.one_line(body), bills))
    return out


def parse_mb_notices_calendar(page):
    """[(date, committee, time, notice href)] of the meeting-notices calendar."""
    out = []
    for cap, table in re.findall(r'<strong class="thead_title">\s*([A-Z][a-z]+ \d{4})\s*</strong>(.*?)</table>',
                                 page or "", re.S):
        mon, year = cap.split()
        for td in re.findall(r"<td>(.*?)</td>", table, re.S):
            dm = re.match(r"\s*(\d{1,2})", td)
            if not dm:
                continue
            d = ra.iso(dm.group(1), mon, year)
            for href, name, after in re.findall(
                    r'<a href="([^"]+\.pdf)">(.*?)</a>\s*</strong>(.*?)(?=<strong>|$)', td, re.S):
                tm = re.search(r"(\d{1,2}:\d{2}\s*[ap]\.?m\.?)", ra.clean(name + " " + after))
                out.append((d, ra.one_line(ra.clean(name)), tm.group(1) if tm else None,
                            urljoin(MB_BASE + "/committees/", href)))
    return out


def parse_mb_notice(text):
    """[(bill no, title)] under MATTERS UNDER CONSIDERATION of a notice."""
    i = (text or "").find("MATTERS UNDER CONSIDERATION")
    if i < 0:
        return []
    out = []
    lines = lines_of(text[i:])
    for k, line in enumerate(lines):
        m = re.match(r"^Bill (\d+)\b\s*[–-]?\s*(.*)$", line)
        if m:
            title = m.group(2) or (lines[k + 1] if k + 1 < len(lines) else "")
            title = re.split(r"\s{2,}|QUESTIONS", title)[0].strip()
            out.append((m.group(1), title))
    return out


def read_mb(client, ctx):
    items, gaps = [], []
    sessional = []
    try:
        cal = _text(client, MB_CAL, "mb-calendar")
        so = re.search(r'href="(sessional_order_\d{4}\.pdf)"', cal)
        if so:
            so_url = urljoin(MB_BASE + "/business/", so.group(1))
            sessional = parse_mb_sessional_order(_pdf(client, so_url, "mb-sessional-order"))
            for d, block, bills in sessional:
                if not ctx.in_window(d):
                    continue
                if bills:
                    for n, (no, title) in enumerate(bills, 1):
                        items.append(ra.item(d, "Bill {0} – {1}".format(no, title), MB_BODY, order=n,
                                             meeting_id="mb-house-" + d, detail=cut(block, 1500),
                                             reference="Bill {0}".format(no), url=so_url))
                else:
                    items.append(ra.item(d, cut(block, 300), MB_BODY, meeting_id="mb-house-" + d,
                                         detail=block, url=so_url))
    except Exception as exc:                      # noqa: BLE001
        gaps.append("Manitoba Sessional Order: {0}".format(str(exc)[:160]))
    future = sorted(d for d, _b, _l in sessional if d >= ctx.today)
    paper_date, orders = parse_mb_order_paper(_pdf(client, MB_OP, "mb-order-paper"))
    note = ""
    when = paper_date if paper_date and paper_date >= ctx.today else (future[0] if future else None)
    if paper_date and when and when != paper_date:
        note = "Order Paper of {0}; its orders dated to the next sitting day, {1}".format(paper_date, when)
    elif not when:
        note = "Order Paper of {0} is past and no coming sitting day is known".format(paper_date)
    if when and ctx.in_window(when):
        for n, (heading, kind, no, title) in enumerate(orders, 100):
            items.append(ra.item(when, "{0}: {1} {2} – {3}".format(heading or "Orders", kind, no, title),
                                 MB_BODY, order=n, meeting_id="mb-house-" + when,
                                 reference="{0} {1}".format(kind, no), url=MB_OP,
                                 detail="As on the Order Paper of {0}".format(paper_date)))
    try:
        for d, name, t, href in parse_mb_notices_calendar(_text(client, MB_NOTICES, "mb-notices")):
            if not ctx.in_window(d):
                continue
            mid = "mb-cmte-{0}-{1}".format(d, ra.slug(name, 30))
            bills = []
            try:
                bills = parse_mb_notice(_pdf(client, href, "mb-notice-" + ra.slug(href[-20:])))
            except Exception as exc:              # noqa: BLE001
                gaps.append("Manitoba notice {0}: {1}".format(href, str(exc)[:120]))
            if bills:
                for n, (no, title) in enumerate(bills, 1):
                    items.append(ra.item(d, "Bill {0} – {1}".format(no, title), name, item_time=t,
                                         order=n, meeting_id=mid, reference="Bill {0}".format(no),
                                         url=href))
            else:
                items.append(ra.item(d, "", name, item_time=t, meeting_id=mid, url=href))
    except Exception as exc:                      # noqa: BLE001
        gaps.append("Manitoba committee meeting notices: {0}".format(str(exc)[:160]))
    items = [it for it in items if ctx.in_window(it["dated"])]
    units = [ra.window(ctx.today, ctx.until)] if not gaps else []
    return ra.RegionRead(items, units, source="gov.mb.ca/legislature Order Paper, Sessional Order, "
                         "committee notices", note=note, gaps=gaps)


# --- New Brunswick -----------------------------------------------------------------

NB_CAL = "https://www.legnb.ca/en/calendar/{0}-{1}"
NB_BODY = "Legislative Assembly"


def parse_nb_month(page):
    """[(date, kind, title, time, event url)] of one month's calendar."""
    out = []
    parts = re.split(r'<span class="full-date"><span>', page or "")
    for chunk in parts[1:]:
        d = en_date(chunk[:40])
        if not d:
            continue
        chunk = chunk.split('<span class="full-date">')[0]
        for cls, href, title, t in re.findall(
                r'<li class="calendar-event ([a-z-]+)">\s*<a href="([^"]+)">\s*'
                r'<span class="calendar-event-title">(.*?)</span>\s*'
                r'(?:<span class="calendar-event-time">(.*?)</span>)?', chunk, re.S):
            out.append((d, "house" if "house" in cls else "committee", ra.one_line(ra.clean(title)),
                        ra.one_line(t) or None, urljoin("https://www.legnb.ca", href)))
    return out


def months_between(start, end):
    d = datetime.date.fromisoformat(start).replace(day=1)
    stop = datetime.date.fromisoformat(end)
    while d <= stop:
        yield d.year, d.month
        d = (d + datetime.timedelta(days=32)).replace(day=1)


def read_nb(client, ctx):
    items, seen = [], set()
    for y, m in months_between(ctx.today, ctx.until):
        for d, kind, title, t, url in parse_nb_month(_text(client, NB_CAL.format(y, m),
                                                           "nb-cal-{0}-{1}".format(y, m))):
            if not ctx.in_window(d) or (d, title, t) in seen:
                continue
            seen.add((d, title, t))
            mid = "nb-event-" + url.rstrip("/").rsplit("/", 1)[-1]
            if kind == "house":
                items.append(ra.item(d, "", NB_BODY, item_time=t, meeting_id=mid, url=url,
                                     detail=title))
            else:
                items.append(ra.item(d, "", title, item_time=t, meeting_id=mid, url=url))
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="legnb.ca legislative calendar")


# --- Nova Scotia -------------------------------------------------------------------

NS_ICAL = "https://nslegislature.ca/get-involved/calendar/ical/{0}"
NS_BODY = "House of Assembly"


def parse_ics(text):
    """[{FIELD: value}] of an iCalendar file (lines unfolded, escapes undone)."""
    raw = re.sub(r"\r?\n[ \t]", "", (text or "").replace("\r\n", "\n"))
    out, cur = [], None
    for line in raw.split("\n"):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur is not None:
                out.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            k, v = line.split(":", 1)
            k = k.split(";")[0]
            cur[k] = v.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
    return out


def ics_local(value, tz):
    """(ISO date, 'h:mm AM') of a DTSTART in tz ('20261020T160000Z' or local)."""
    from zoneinfo import ZoneInfo
    m = re.match(r"(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})(Z)?)?", value or "")
    if not m:
        return None, None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not m.group(4):
        return datetime.date(y, mo, d).isoformat(), None
    dt = datetime.datetime(y, mo, d, int(m.group(4)), int(m.group(5)))
    if m.group(7):
        dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone(ZoneInfo(tz))
    return dt.date().isoformat(), dt.strftime("%I:%M %p").lstrip("0")


def parse_ns(ics, house):
    """Items of one Nova Scotia feed: a House sitting is 'to be announced';
    a committee meeting carries its topic (the first line of Witness/Agenda)."""
    out = []
    for e in parse_ics(ics):
        d, t = ics_local(e.get("DTSTART"), "America/Halifax")
        if not d:
            continue
        summary = ra.one_line(e.get("SUMMARY"))
        if house:
            out.append(ra.item(d, "", NS_BODY, item_time=t, meeting_id="ns-house-" + d,
                               detail=ra.one_line(e.get("DESCRIPTION")) or summary))
            continue
        desc = (e.get("DESCRIPTION") or "").split("Witness/Agenda:", 1)[-1]
        paras = [ra.one_line(p) for p in re.split(r"\n\s*\n", desc) if ra.one_line(p)]
        topic = paras[0] if paras else ""
        orgs = [p for p in paras[1:] if not p.startswith("-")]
        out.append(ra.item(d, topic, summary or "Committee", item_time=t,
                           meeting_id="ns-cmte-{0}-{1}".format(d, ra.slug(summary, 40)),
                           detail="; ".join(orgs) or None,
                           url="https://nslegislature.ca/get-involved/calendar"))
    return out


def read_ns(client, ctx):
    items = parse_ns(_text(client, NS_ICAL.format("legislative-assembly"), "ns-ical-house"), True)
    items += parse_ns(_text(client, NS_ICAL.format("committee"), "ns-ical-committee"), False)
    items = [it for it in items if ctx.in_window(it["dated"])]
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="nslegislature.ca iCal feeds (House, committees)")


# --- Newfoundland and Labrador -------------------------------------------------------

NL_OPS = "https://www.assembly.nl.ca/HouseBusiness/OrderPapers/"
NL_BODY = "House of Assembly"


def nl_order_papers(index, listing_url, listing, today, until):
    out = []
    for name in re.findall(r'href="(\d{2}-\d{2}-\d{2})\.pdf"', listing or ""):
        d = "20" + name
        if today <= d <= until:
            out.append((d, urljoin(listing_url, name + ".pdf")))
    return sorted(set(out))


def parse_numbered_paper(text, dated, body, prefix, url=None, start="ORDERS OF THE DAY",
                         stop=("Published under the authority",)):
    """A generic order paper: each numbered item after `start`, with the
    heading line it stands under."""
    t = text or ""
    i = t.find(start)
    if i < 0:
        return []
    j = min([k for k in (t.find(s, i) for s in stop) if k > 0] or [len(t)])
    items, heading, cur = [], "Orders of the Day", None
    for line in t[i + len(start):j].splitlines():
        line = ra.one_line(line)
        if not line or line == "=====PAGE" or re.match(r"^[\d_ ]+$", line):
            continue
        m = re.match(r"^(\d{1,3})\.\s+(.+)$", line)
        if m:
            if cur:
                items.append(cur)
            cur = [heading, m.group(1), m.group(2)]
        elif len(line) < 60 and re.match(r"^[A-Z][A-Za-z ’'&-]+$", line) and (
                line.istitle() or line.isupper()):
            if cur:
                items.append(cur)
                cur = None
            heading = line.title() if line.isupper() else line
        elif cur:
            cur[2] += " " + line
    if cur:
        items.append(cur)
    out = []
    for n, (head, no, text_) in enumerate(items, 1):
        res = re.search(r"(?:BE IT RESOLVED|Be it resolved) that (.+)", text_)
        business = "{0} {1}: {2}".format(head, no, res.group(1) if res else text_)
        bill = re.search(r"\bBill\s+(?:No\.\s*)?(\d+)", text_)
        out.append(ra.item(dated, cut(business), body, order=n, meeting_id=prefix + dated,
                           detail=text_, reference="Bill {0}".format(bill.group(1)) if bill else None,
                           url=url))
    return out


def read_nl(client, ctx):
    index = _text(client, NL_OPS, "nl-order-papers")
    folders = re.findall(r'href="(ga(\d+)Session(\d+)/)"', index)
    if not folders:
        raise ValueError("no session folder on {0}".format(NL_OPS))
    folder = max(folders, key=lambda f: (int(f[1]), int(f[2])))[0]
    listing_url = urljoin(NL_OPS, folder)
    papers = nl_order_papers(index, listing_url, _text(client, listing_url, "nl-session"),
                             ctx.today, ctx.until)
    items, units, gaps = [], [], []
    for d, url in papers:
        try:
            items += parse_numbered_paper(_pdf(client, url, "nl-op-" + d), d, NL_BODY, "nl-op-", url)
            units.append(ra.day(d, NL_BODY))
        except Exception as exc:                  # noqa: BLE001
            gaps.append("Newfoundland and Labrador Order Paper {0}: {1}".format(d, str(exc)[:160]))
    return ra.RegionRead(items, units, source="assembly.nl.ca Order Papers",
                         note=("Order Paper for {0}".format(", ".join(d for d, _ in papers)) if papers
                               else "no Order Paper for a coming sitting day ({0})".format(
                                   folder.rstrip("/"))), gaps=gaps)


# --- Northwest Territories -------------------------------------------------------------

NT_BASE = "https://www.ntassembly.ca"
NT_ORDERS = NT_BASE + "/file/orders"
NT_CMTE = NT_BASE + "/committees/upcoming-meeting-dates"
NT_BODY = "Legislative Assembly"
NT_WANTED = ("Motions", "First Reading of Bills", "Second Reading of Bills",
             "Consideration in Committee of the Whole of Bills and Other Matters",
             "Third Reading of Bills", "Notices of Motion for First Reading of Bills")


def parse_nt_orders(text, url=NT_ORDERS):
    """(date, items) of the Orders of the Day: each motion, bill and tabled
    document under the business headings (16 to 22)."""
    m = re.search(r"(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY),\s+([A-Z]+)\s+(\d{1,2}),\s+(\d{4})",
                  text or "")
    if not m:
        raise ValueError("no date on the NWT Orders of the Day")
    dated = ra.iso(m.group(2), m.group(1), m.group(3))
    items, heading, cur = [], None, None
    stop = (text or "").find("Items Before Standing Committee")
    body = (text or "")[:stop if stop > 0 else None]
    for line in body.splitlines():
        line = ra.one_line(line)
        if not line or line == "=====PAGE":
            continue
        h = re.match(r"^(\d{1,2})\.\s+(.+)$", line)
        if h and int(h.group(1)) <= 30:
            if cur:
                items.append(cur)
                cur = None
            heading = h.group(2).strip()
            continue
        if heading not in NT_WANTED:
            continue
        mi = re.match(r"^((?:Motion|Bill|TD)\s+[\d\-()]+)\s+(.+)$", line)
        if mi:
            if cur:
                items.append(cur)
            cur = [heading, mi.group(1), mi.group(2)]
        elif cur:
            cur[2] += " " + line
    if cur:
        items.append(cur)
    out = []
    for n, (head, ref, title) in enumerate(items, 1):
        out.append(ra.item(dated, "{0}: {1} {2}".format(head, ref, title), NT_BODY, order=n,
                           meeting_id="nt-od-" + dated, reference=ref, url=url))
    return dated, out


def parse_nt_committees(page):
    """[(date, time, committee, business, url)] of the upcoming meetings list."""
    out = []
    for row in re.findall(r'<div class="views-row">(.*?)(?=<div class="views-row">|</div>\s*</div>\s*</div>\s*</div>)',
                          page or "", re.S):
        title = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
        when = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})', row)
        body = re.search(r'views-field-body"><div class="field-content">(.*?)</div>', row, re.S)
        if not (title and when):
            continue
        text = ra.one_line(ra.clean(body.group(1))) if body else ""
        cm = re.search(r"\b(?:The|the)\s+((?:[A-Z][\w&’']*\s+)+?(?:&\s+)?(?:[A-Z][\w&’']*\s+)*Committee)\b",
                       text)
        out.append((when.group(1), when.group(2), cm.group(1) if cm else "Standing committee",
                    ra.one_line(ra.clean(title.group(2))), urljoin(NT_BASE, title.group(1))))
    return out


def read_nt(client, ctx):
    items, gaps = [], []
    dated, orders = parse_nt_orders(_pdf(client, NT_ORDERS, "nt-orders"))
    units = []
    if ctx.in_window(dated):
        items += orders
        units.append(ra.day(dated, NT_BODY))
    try:
        for n, (d, t, body, business, url) in enumerate(parse_nt_committees(
                _text(client, NT_CMTE, "nt-committees"))):
            if ctx.in_window(d):
                items.append(ra.item(d, business, body, item_time=t, order=n, url=url,
                                     meeting_id="nt-cmte-{0}-{1}".format(d, ra.slug(business, 40))))
        units.append(ra.window(ctx.today, ctx.until))
    except Exception as exc:                      # noqa: BLE001
        gaps.append("NWT upcoming committee meetings: {0}".format(str(exc)[:160]))
    return ra.RegionRead(items, units, source="ntassembly.ca Orders of the Day and committee meetings",
                         note="Orders of the Day of {0}".format(dated), gaps=gaps)


# --- the regions ------------------------------------------------------------------------

REGIONS = {
    "on": ra.region("Ontario", reader=read_on),
    "qc": ra.region("Quebec", reader=read_qc, langs=["taxonomy-qc.yaml", "taxonomy.yaml"]),
    "bc": ra.region("British Columbia", reader=read_bc),
    "ab": ra.region("Alberta", reader=read_ab),
    "sk": ra.region("Saskatchewan", reader=read_sk),
    "mb": ra.region("Manitoba", reader=read_mb),
    "nb": ra.region("New Brunswick", reader=read_nb),
    "ns": ra.region("Nova Scotia", reader=read_ns),
    "nl": ra.region("Newfoundland and Labrador", reader=read_nl),
    "nt": ra.region("Northwest Territories", reader=read_nt),
    "pe": ra.region("Prince Edward Island", status="blocked",
                    note="assembly.pe.ca answers every page, the home page included, with a Radware "
                         "CAPTCHA (validate.perfdrive.com), from the laptop and from GitHub's runners; "
                         "never solved. Order papers and the calendar sit behind it"),
    "yt": ra.region("Yukon", status="blocked",
                    note="yukonassembly.ca answers a Cloudflare challenge (403) on every path, robots.txt "
                         "included, from the laptop and from CI; no other host publishes the Order Paper"),
    "nu": ra.region("Nunavut", status="no-route",
                    note="assembly.nu.ca publishes no order paper or agenda ahead of a sitting; the 2026 "
                         "sitting calendar is a colour-coded PDF whose days carry no text, and the site "
                         "calendar lists no sittings"),
}
