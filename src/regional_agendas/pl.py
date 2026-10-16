"""Poland: the sixteen sejmiki's forward business (regional_agenda, 16 October
2026; src/regional_agenda.py is the interface, docs/poland-regions-scope.md
"Forward agenda" has every measurement).

The past half (tools/pl_regions.py) reads adopted resolutions; this module
reads what each sejmik has BOOKED. The chairman must send the councillors
the date and the proposed order of business (porządek obrad) at least seven
days before a sitting (art. 21 of the voivodeship self-government act), and
most sejmiki put it in their BIP the same day. Region codes are
tools/pl_regions.py's (src/pl_regions_store), so the renderer can join.

Read (ten), robots.txt asked for every request, honest user agent:

  mz  Mazowieckie: the term's sitting timetable (Harmonogram sesji, a table
      of dates to December), the year's sitting folders and, once a
      sitting's folder exists, its 'Porządek obrad' page (an HTML list);
      the committees' 'Planowane posiedzenia' page (each planned meeting
      with its date, hour and porządek obrad, inline).
  sl  Śląskie: the draft-resolution list by month (projekty uchwał 'na sesję
      nr XXXI z dnia 2026-10-19'): a booked sitting; the drafts are one large
      PDF, so each sitting is 'to be announced'.
  ma  Małopolskie: the BIP's JSON API (Madkom, /api/): the committees'
      meeting timetable (menu 437636: date, hour, place, committee) and each
      invitation article with its 'proponowany porządek posiedzenia'.
      Plenary sittings are run on eSesja (Cloudflare bot check): not read.
  pm  Pomorskie: the same JSON API: the 'Materiały na sesję' article lists
      each sitting with its porządek obrad as a .docx, read with zipfile.
  ds  Dolnośląskie: the same JSON API: the year's sitting dates article and
      the standing committees' dates table (agendas only as .doc/.pdf
      attachments: 'to be announced').
  pk  Podkarpackie: sejmik.podkarpackie.pl (Joomla): the sittings list, each
      sitting's materials page with its porządek obrad .docx, and the
      committees' 'Posiedzenia komisji' blog (date, hour and numbered
      agenda inline).
  kp  Kujawsko-Pomorskie: the BIP's index of sittings and each 'Porządek
      obrad' page (an HTML list), posted about a week ahead.
  ld  Łódzkie: the BIP's 'Sesje Sejmiku' notices (K2): each 'Porządek obrad'
      notice with its numbered points (4.1, 4.2 ... under 'Rozpatrzenie
      projektów uchwał').
  wn  Warmińsko-Mazurskie: the BIP categories 'Porządek obrad sesji' (one
      article per sitting, the agenda a PDF) and 'Porządek obrad komisji'
      (one article a month, each meeting a PDF named 'Porządek posiedzenia
      KSR 21.10.2026'): booked sittings, 'to be announced'.
  zp  Zachodniopomorskie: the BIP's sitting articles (the agenda a scanned
      PDF): booked sittings, 'to be announced'.

Not read (each says why on every run): Wielkopolskie, Lubelskie and
Świętokrzyskie (no forward list in the BIP: sittings and agendas appear
only as protocols, or a PDF list that stops in September 2025), Lubuskie
(only a live-stream page), Opolskie (bip.opolskie.pl does not answer),
Podlaskie (its new BIP, bip.podlaskie.eu, lists draft resolutions by
sitting with the month only). eSesja (*.esesja.pl, where several sejmiki
keep sittings and materials) answers our client with a Cloudflare bot
check: never bypassed.
"""

from __future__ import annotations

import datetime
import html
import io
import re
import urllib.parse
import zipfile

from src import regional_agenda as ra
from src.http import FetchError

CC = "pl"
TAXONOMIES = (("taxonomy-pl.yaml", "pl"),)
THROTTLES = {"bip.slaskie.pl": 3.0, "sejmik.podkarpackie.pl": 3.0, "bip.podkarpackie.pl": 3.0,
             "bip.mazovia.pl": 1.5, "bip.malopolska.pl": 1.5}
FEED = ra.feed(CC)
PLENARY = "Plenary"

MONTHS_GEN = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
              "sierpnia", "września", "października", "listopada", "grudnia")
MONTHS_NOM = ("styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec",
              "sierpień", "wrzesień", "październik", "listopad", "grudzień")


# --- shared helpers --------------------------------------------------------------

def _fold(s):
    s = (s or "").lower()
    return s.translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))


_MONTH_FOLD = {_fold(m): i + 1 for i, m in enumerate(MONTHS_GEN)}
_MONTH_FOLD.update({_fold(m): i + 1 for i, m in enumerate(MONTHS_NOM)})


def pl_month(word):
    w = _fold(word).strip(". ")
    if w in _MONTH_FOLD:
        return _MONTH_FOLD[w]
    for k, v in _MONTH_FOLD.items():
        if len(w) >= 4 and k.startswith(w[:4]):
            return v
    return None


_PL_NAME = re.compile(r"\b(\d{1,2})\s*([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{4,})\s*(\d{4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_NUM = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_SLUG = re.compile(r"\b(\d{1,2})-([a-z]{4,})-(\d{4})\b")


def pl_date(text):
    """The first date in Polish text: 2026-10-26, 26.10.2026, '26 października
    2026', 'października2026', a URL slug '26-pazdziernika-2026'."""
    t = ra.one_line(html.unescape(text or ""))
    found = []
    for m in _ISO.finditer(t):
        found.append((m.start(), ra.iso(m.group(3), m.group(2), m.group(1))))
    for m in _NUM.finditer(t):
        found.append((m.start(), ra.iso(m.group(1), m.group(2), m.group(3))))
    for rx in (_PL_NAME, _SLUG):
        for m in rx.finditer(t):
            mo = pl_month(m.group(2))
            if mo:
                found.append((m.start(), ra.iso(m.group(1), mo, m.group(3))))
    found = [f for f in found if f[1]]
    return min(found)[1] if found else None


def pl_time(text):
    m = re.search(r"\bgodz(?:\.|ina|inie|in[ay])?\s*(\d{1,2})[:.]?(\d{2})", text or "", re.I)
    if not m:
        m = re.search(r"\b(\d{1,2}):(\d{2})\b", text or "")
    return "{0:02d}:{1}".format(int(m.group(1)), m.group(2)) if m else None


def _text(fragment):
    return ra.one_line(ra.clean(fragment))


def top_level_lis(ol_html):
    """The top-level <li> fragments of one list, nested lists kept inside
    their parent."""
    out, depth, start = [], 0, None
    for m in re.finditer(r"<(/?)(ol|ul|li)\b[^>]*>", ol_html or "", re.I):
        closing, tag = m.group(1) == "/", m.group(2).lower()
        if tag in ("ol", "ul"):
            depth += -1 if closing else 1
        elif tag == "li" and depth == 1:
            if not closing:
                start = m.end()
            elif start is not None:
                out.append(ol_html[start:m.start()])
                start = None
    return out


def first_list(fragment):
    """The first <ol> (or <ul>) of a fragment, nested lists included."""
    m = re.search(r"<(ol|ul)\b[^>]*>", fragment or "", re.I)
    if not m:
        return ""
    depth, i = 0, m.start()
    for t in re.finditer(r"<(/?)(?:ol|ul)\b[^>]*>", fragment[m.start():], re.I):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return fragment[m.start():m.start() + t.end()]
    return fragment[m.start():]


_DRUK = re.compile(r"\(?\bdruk(?:u)?\s+nr\.?\s*([\w./-]+?)\)?[;.,*]*$", re.I)
_PRESENTER = re.compile(r"\s*[–-]\s*(?:projekt uchwały przedstawia|przedstawia)\b.*?(?=;?\s*druk\b|$)", re.I)


def agenda_point(text):
    """(business, reference) of one agenda point: the presenter's name
    dropped, the print number (druk nr 473) as the reference."""
    t = ra.one_line(text).strip(" ;")
    t = _PRESENTER.sub("", t)
    ref = None
    m = _DRUK.search(t)
    if m:
        ref = "druk nr " + m.group(1).rstrip(".;*)")
        t = t[:m.start()].rstrip(" ;,–-(")
    t = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", t).strip(" ;")
    return t, ref


def points_items(points, dated, body, meeting_id, url, item_time=None):
    """Items for a list of agenda point texts. A point ending in ':' heads
    the points under it ('Przyjęcie uchwał:' + 'w sprawie ...')."""
    out, parent, order = [], None, 0
    for raw in points:
        text = ra.one_line(raw)
        if not text:
            continue
        sub = bool(re.match(r"^\d+\.\d+\.?\s", text)) or (parent and text[:1].islower())
        business, ref = agenda_point(text)
        if not business:
            continue
        if business.endswith(":") and not sub:
            parent = business.rstrip(":")
            continue
        if sub and parent:
            business = "{0}: {1}".format(parent, business)
        else:
            parent = None
        order += 1
        out.append(ra.item(dated, business, body, item_time=item_time, order=order,
                           meeting_id=meeting_id, reference=ref, url=url))
    return out


def li_points(list_html):
    """Agenda points of an HTML list: one per top-level <li>, a nested list
    flattened into its parent ('Sprawy proceduralne: stwierdzenie quorum,
    ...')."""
    return [_text(li) for li in top_level_lis(list_html)]


def docx_paragraphs(data):
    """[(numbered, text)] of a .docx's paragraphs (zipfile, no dependency)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError):
        return []
    out = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)))
        text = ra.one_line(text)
        if text:
            out.append(("<w:numPr>" in p, text))
    return out


def docx_time(data):
    """The sitting's hour from a .docx's unnumbered header ('o godz. 11.00',
    'o godzinie 1300')."""
    for numbered, t in docx_paragraphs(data):
        if not numbered:
            m = re.search(r"\bgodz(?:\.|inie|ina)?\s*(\d{1,2})[:.]?(\d{2})\b", t, re.I)
            if m:
                return "{0:02d}:{1}".format(int(m.group(1)), m.group(2))
    return None


def docx_points(data):
    """The numbered points of a porządek obrad .docx (numbered paragraphs, or
    paragraphs typed '1. ...')."""
    paras = docx_paragraphs(data)
    pts = [t for numbered, t in paras if numbered]
    if not pts:
        pts = [t for _, t in paras if re.match(r"^\d+(?:\.\d+)*\.\s+\S", t)]
    return pts


def _units(ctx, failed, read_meetings):
    """The whole window when every sitting's agenda was read, else only the
    meetings that were (a failed agenda keeps its stored rows)."""
    if not failed:
        return [ra.window(ctx.today, ctx.until)]
    return [ra.meeting(m) for m in read_meetings]


def _mid(code, dated, body):
    return "{0}:{1}:{2}".format(code, dated, ra.slug(body, 40))


# --- Mazowieckie ------------------------------------------------------------------

MZ = "https://bip.mazovia.pl"
MZ_TERM = MZ + "/pl/bip/sejmik/sesje-sejmiku/vii-kadencja-2024-2029/"
MZ_YEAR = MZ_TERM + "{0}/"
MZ_PLANNED = MZ + "/pl/bip/sejmik/komisje-sejmiku/planowane-posiedzenia.html"


def parse_mz_timetable(page):
    """The term's sitting timetable: [(date, note)]; a sitting that 'nie
    odbyła się' is left out."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page or "", re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) < 2:
            continue
        d = _ISO.search(_text(cells[1]))
        if not d:
            continue
        note = _text(cells[2]) if len(cells) > 2 else ""
        if re.search(r"nie odbył", note + _text(cells[1]), re.I):
            continue
        place = _text(cells[1]).replace(d.group(0), "").strip()
        out.append((d.group(0), place or None))
    return out


def parse_mz_year(page, base=MZ):
    """{date: sitting folder URL} from a year page ('xxix-sesja-22-wrzesnia-2026-r/')."""
    out = {}
    for href in re.findall(r'href="([^"]*/sesje-sejmiku/vii-kadencja-2024-2029/\d{4}/[a-z]+-sesja-[^"/]+/)"',
                           page or ""):
        d = pl_date(href.rstrip("/").rsplit("/", 1)[-1])
        if d:
            out.setdefault(d, urllib.parse.urljoin(base, href))
    return out


def parse_mz_folder(page, base=MZ):
    m = re.search(r'href="([^"]*porzadek-obrad[^"]*\.html)"', page or "")
    return urllib.parse.urljoin(base, m.group(1)) if m else None


def parse_mz_agenda(page):
    """The points of a 'Porządek obrad' page (the first list of the content)."""
    i = (page or "").find("component-content-wysiwyg")
    return li_points(first_list(page[i:] if i >= 0 else page or ""))


def parse_mz_planned(page, base=MZ):
    """The committees' planned meetings: [(committee, date, time, url, points)]."""
    out = []
    blocks = re.split(r'<div class="component-item">', page or "")[1:]
    for b in blocks:
        title = re.search(r'<a href="([^"]+)"[^>]*class="component-item-title"[^>]*>(.*?)</a>', b, re.S)
        date = re.search(r'fn-date-handler">\s*([\d-]+)', b)
        if not (title and date):
            continue
        tm = re.search(r'fn-time-handler">\s*([\d:.]+)', b)
        agenda = b.split("Porządek obrad:", 1)
        pts = li_points(first_list(agenda[1])) if len(agenda) > 1 else []
        out.append((_text(title.group(2)), date.group(1), tm.group(1) if tm else None,
                    urllib.parse.urljoin(base, title.group(1)), pts))
    return out


def read_mz(client, ctx):
    items, gaps, failed, read_ids = [], [], False, []
    timetable = parse_mz_timetable(client.get_text(MZ_TERM, FEED, "mz-term"))
    sittings = [(d, n) for d, n in timetable if ctx.in_window(d)]
    folders = {}
    if sittings:
        years = sorted({d[:4] for d, _ in sittings})
        for y in years:
            try:
                folders.update(parse_mz_year(client.get_text(MZ_YEAR.format(y), FEED, "mz-year-" + y)))
            except FetchError as exc:
                gaps.append("Mazowieckie sitting folders {0}: {1}".format(y, str(exc)[:160]))
    for dated, place in sittings:
        mid = _mid("mz", dated, PLENARY)
        pts, url = [], folders.get(dated)
        if url and not ctx.out_of_time():
            try:
                agenda_url = parse_mz_folder(client.get_text(url, FEED, "mz-folder"))
                if agenda_url:
                    pts = parse_mz_agenda(client.get_text(agenda_url, FEED, "mz-agenda"))
                    url = agenda_url
            except FetchError as exc:
                failed = True
                gaps.append("Mazowieckie sitting {0}: {1}".format(dated, str(exc)[:160]))
                continue
        got = points_items(pts, dated, PLENARY, mid, url or MZ_TERM)
        items += got or [ra.item(dated, "", PLENARY, meeting_id=mid, detail=place,
                                 url=url or MZ_TERM)]
        read_ids.append(mid)
    try:
        planned = parse_mz_planned(client.get_text(MZ_PLANNED, FEED, "mz-committees"))
        for body, dated, tm, url, pts in planned:
            if not ctx.in_window(dated):
                continue
            mid = _mid("mz", dated, body)
            got = points_items(pts, dated, body, mid, url, item_time=tm)
            items += got or [ra.item(dated, "", body, item_time=tm, meeting_id=mid, url=url)]
            read_ids.append(mid)
    except FetchError as exc:
        failed = True
        gaps.append("Mazowieckie committees: {0}".format(str(exc)[:160]))
    return ra.RegionRead(items, _units(ctx, failed, read_ids),
                         source="bip.mazovia.pl (timetable, porządek obrad, planned committee meetings)",
                         gaps=gaps)


# --- Śląskie ----------------------------------------------------------------------

SL_DRAFTS = "https://bip.slaskie.pl/sejmik_wojewodztwa/sesje_sejmiku/projekty_uchwal/"


def sl_month_url(year, month):
    return SL_DRAFTS + "?p=" + urllib.parse.quote("{0}^{1}".format(year, MONTHS_NOM[month - 1]))


def parse_sl_drafts(page, base="https://bip.slaskie.pl"):
    """[(date, sitting number, url)] of a month's 'Projekty uchwał na sesję
    nr XXXI z dnia 2026-10-19' entries."""
    out = []
    for href in re.findall(r'href="([^"]*projekty-uchwal-na-sesje-nr-([ivxlc]+)-z-dnia-(\d{4}-\d{2}-\d{2})[^"]*\.html)"',
                           page or "", re.I):
        url, num, d = href
        row = (d, num.upper(), urllib.parse.urljoin(base, url))
        if row not in out:
            out.append(row)
    return out


def read_sl(client, ctx):
    today = ctx.today_date
    months, seen = [], set()
    d = today.replace(day=1)
    while d <= ctx.until_date and len(months) < 3:
        months.append((d.year, d.month))
        d = (d + datetime.timedelta(days=32)).replace(day=1)
    items = []
    for y, m in months:
        for dated, num, url in parse_sl_drafts(client.get_text(sl_month_url(y, m), FEED,
                                                               "sl-drafts-{0}-{1}".format(y, m))):
            if not ctx.in_window(dated) or (dated, num) in seen:
                continue
            seen.add((dated, num))
            items.append(ra.item(dated, "", PLENARY, meeting_id=_mid("sl", dated, PLENARY),
                                 detail="{0} sesja Sejmiku Województwa Śląskiego; projekty uchwał "
                                        "(one PDF)".format(num), url=url))
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="bip.slaskie.pl (projekty uchwał by sitting)",
                         note="drafts published as one PDF per sitting: sittings to be announced")


# --- Madkom JSON API (Małopolskie, Pomorskie, Dolnośląskie) -----------------------------

def madkom_list_url(site, menu, limit=30):
    return "{0}api/menu/{1}/articles?limit={2}&offset=0".format(site, menu, limit)


def madkom_article_url(site, article):
    return "{0}api/articles/{1}".format(site, article)


MA = "https://bip.malopolska.pl/"
MA_COMMITTEES = 437636


def parse_ma_committees(reply):
    """[(article id, date, time, committee, place)] of the committees'
    meeting timetable."""
    out = []
    for a in (reply or {}).get("articles") or []:
        vals = [ra.one_line(html.unescape(re.sub(r"<[^>]+>", " ", str(f.get("value") or ""))))
                for f in a.get("columnFields") or []]
        date = next((v for v in vals if _ISO.fullmatch(v or "")), None)
        tm = next((v for v in vals if re.fullmatch(r"\d{1,2}[:.]\d{2}", v or "")), None)
        body = next((v for v in vals if re.match(r"(?i)komisj", v or "")), None)
        place = next((v for v in vals if v and v not in (date, tm, body)), None)
        if date and body:
            out.append((str(a.get("id")), date, tm, body, place))
    return out


def parse_madkom_agenda(content):
    """The numbered points after 'porządek' in an invitation article
    ('1. Otwarcie posiedzenia.' paragraphs and <li> items mixed)."""
    c = content or ""
    i = re.search(r"porz[aą]d(?:ek|ku)|porz&#261;d", c, re.I)
    c = c[i.end():] if i else c
    c = re.sub(r"<li[^>]*>", "\n• ", c, flags=re.I)
    pts = []
    for line in ra.clean(c).splitlines():
        line = line.strip()
        m = re.match(r"^(?:\d+\.\s*|•\s*)(\S.*)$", line)
        if m:
            pts.append(m.group(1))
    return pts


def read_ma(client, ctx):
    rows = parse_ma_committees(client.get_json(madkom_list_url(MA, MA_COMMITTEES), FEED, "ma-committees"))
    items, gaps, failed, read_ids = [], [], False, []
    for art, dated, tm, body, place in rows:
        if not ctx.in_window(dated) or ctx.out_of_time():
            continue
        mid = "ma:{0}".format(art)
        url = "{0}umwm,a,{1},.html".format(MA, art)
        try:
            reply = client.get_json(madkom_article_url(MA, art), FEED, "ma-article")
        except FetchError as exc:
            failed = True
            gaps.append("Małopolskie committee meeting {0} {1}: {2}".format(dated, body, str(exc)[:120]))
            continue
        pts = parse_madkom_agenda((reply or {}).get("content"))
        got = points_items(pts, dated, body, mid, url, item_time=tm)
        items += got or [ra.item(dated, "", body, item_time=tm, meeting_id=mid, detail=place, url=url)]
        read_ids.append(mid)
    return ra.RegionRead(items, _units(ctx, failed, read_ids),
                         source="bip.malopolska.pl JSON API (committee timetable, invitations)",
                         note="committees only: plenary sittings are on eSesja (bot check)", gaps=gaps)


PM = "https://bip.pomorskie.eu/"
PM_MATERIALS = 60421


def parse_pm_sessions(content):
    """[(date, sitting label, porządek obrad URL or None)] of the 'Materiały
    na sesję' article: 'Sesja XXXI - 26 października 2026' + its list."""
    out = []
    parts = re.split(r"<p[^>]*>\s*(Sesja\s+[IVXLC]+[^<]*)</p>", content or "")
    for k in range(1, len(parts) - 1, 2):
        label = ra.one_line(html.unescape(parts[k]))
        d = pl_date(label)
        link = None
        for href, text in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', first_list(parts[k + 1]), re.S):
            if re.search(r"porz[aą]dek obrad|porz&#261;dek", text + href, re.I):
                link = html.unescape(href)
                break
        if d:
            out.append((d, label, link))
    return out


def read_pm(client, ctx):
    reply = client.get_json(madkom_article_url(PM, PM_MATERIALS), FEED, "pm-materials")
    items, gaps, failed, read_ids = [], [], False, []
    for dated, label, link in parse_pm_sessions((reply or {}).get("content")):
        if not ctx.in_window(dated):
            continue
        mid = _mid("pm", dated, PLENARY)
        pts, tm = [], None
        if link and ".docx" in link.lower():
            try:
                data = client.get_bytes(link, FEED, "pm-agenda", archive=False)
                pts, tm = docx_points(data), docx_time(data)
            except FetchError as exc:
                failed = True
                gaps.append("Pomorskie {0}: {1}".format(label, str(exc)[:160]))
                continue
        got = points_items(pts, dated, PLENARY, mid, link or PM, item_time=tm)
        items += got or [ra.item(dated, "", PLENARY, meeting_id=mid, detail=label, url=link or PM)]
        read_ids.append(mid)
    return ra.RegionRead(items, _units(ctx, failed, read_ids),
                         source="bip.pomorskie.eu JSON API (materiały na sesję, porządek obrad .docx)",
                         gaps=gaps)


DS = "https://bip.dolnyslask.pl/"
DS_SITTINGS = 107616
DS_COMMITTEES = 99529


def parse_ds_sittings(content):
    """[(date, sitting number, time)] of the year's 'Terminy sesji' table."""
    lines = ra.clean(content or "").splitlines()
    out, num = [], None
    for k, line in enumerate(lines):
        line = line.strip()
        if re.fullmatch(r"[IVXLC]+", line):
            num = line
            continue
        d = pl_date(line)
        if d and num:
            nxt = lines[k + 1] if k + 1 < len(lines) else ""
            out.append((d, num, pl_time(nxt)))
            num = None
    return out


def parse_ds_committees(content):
    """[(committee, date, time, room, agenda link)] of the standing committees'
    table (the second cell: date, hour and room, each linking the agenda
    document)."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", content or "", re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        if len(cells) < 2 or not re.match(r"(?i)komisj", _text(cells[0])):
            continue
        lines = [l.strip() for l in ra.clean(cells[1]).splitlines() if l.strip()]
        d = pl_date(lines[0]) if lines else None
        if not d:
            continue
        link = re.search(r'href="([^"]+)"', cells[1])
        room = next((l for l in lines[1:] if not re.match(r"(?i)godz", l)), None)
        out.append((_text(cells[0]), d, pl_time(" ".join(lines[1:2])), room,
                    urllib.parse.urljoin(DS, link.group(1)) if link else None))
    return out


def read_ds(client, ctx):
    items, gaps = [], []
    reply = client.get_json(madkom_article_url(DS, DS_SITTINGS), FEED, "ds-sittings")
    url = "{0}a,{1},.html".format(DS, DS_SITTINGS)
    for dated, num, tm in parse_ds_sittings((reply or {}).get("content")):
        if ctx.in_window(dated):
            items.append(ra.item(dated, "", PLENARY, item_time=tm, meeting_id=_mid("ds", dated, PLENARY),
                                 detail="{0} sesja Sejmiku Województwa Dolnośląskiego".format(num), url=url))
    units = [ra.window(ctx.today, ctx.until)]
    try:
        reply = client.get_json(madkom_article_url(DS, DS_COMMITTEES), FEED, "ds-committees")
        curl = "{0}a,{1},.html".format(DS, DS_COMMITTEES)
        for body, dated, tm, room, link in parse_ds_committees((reply or {}).get("content")):
            if ctx.in_window(dated):
                items.append(ra.item(dated, "", body, item_time=tm, meeting_id=_mid("ds", dated, body),
                                     detail=room, url=link or curl))
    except FetchError as exc:
        units = [ra.day(i["dated"], PLENARY) for i in items]
        gaps.append("Dolnośląskie committee dates: {0}".format(str(exc)[:160]))
    return ra.RegionRead(items, units, source="bip.dolnyslask.pl JSON API (sitting and committee dates)",
                         note="dates only: agendas are .doc/.pdf attachments", gaps=gaps)


# --- Podkarpackie -------------------------------------------------------------------

PK = "https://sejmik.podkarpackie.pl"
PK_SITTINGS = PK + "/prace-sejmiku/sesje"
PK_COMMITTEES = PK + "/prace-sejmiku/posiedzenia-komisji"


def parse_pk_sittings(page, base=PK):
    """[(date, label, url)] of the sittings list ('XXXIII-26 października2026 r.')."""
    out = []
    for href, label in re.findall(r'<a href="(/prace-sejmiku/sesje/[^"]+)"[^>]*class="lead_title"[^>]*>(.*?)</a>',
                                  page or "", re.S):
        label = _text(label)
        d = pl_date(label)
        if d:
            out.append((d, label, urllib.parse.urljoin(base, href)))
    return out


def parse_pk_materials(page, base=PK):
    """The porządek obrad .docx link of a sitting's materials page."""
    for href, text in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', page or "", re.S):
        if re.search(r"porz", urllib.parse.unquote(href) + text, re.I) and re.search(r"\.docx?\b", href, re.I):
            return urllib.parse.urljoin(base, href)
    return None


def parse_pk_committees(page, base=PK):
    """[(body, date, time, url, points)] of the committees' blog."""
    out = []
    for block in re.split(r'itemprop="blogPost"', page or "")[1:]:
        title = re.search(r'<h2[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        body_m = re.search(r"</dl>(.*?)</div>", block, re.S)
        if not (title and body_m):
            continue
        text = ra.clean(body_m.group(1))
        d = pl_date(text)
        if not d:
            continue
        pts = [re.sub(r"^\d+\.\s*", "", line.strip()) for line in text.splitlines()
               if re.match(r"^\s*\d+\.\s+\S", line)]
        body = re.sub(r"^(?:Wspólne\s+)?Posiedzenie\s+", "", _text(title.group(2)), flags=re.I)
        out.append((body, d, pl_time(text), urllib.parse.urljoin(base, title.group(1)), pts))
    return out


def read_pk(client, ctx):
    items, gaps, failed, read_ids = [], [], False, []
    for dated, label, url in parse_pk_sittings(client.get_text(PK_SITTINGS, FEED, "pk-sittings")):
        if not ctx.in_window(dated) or ctx.out_of_time():
            continue
        mid = _mid("pk", dated, PLENARY)
        pts, link, tm = [], None, None
        try:
            link = parse_pk_materials(client.get_text(url, FEED, "pk-sitting"))
            if link and link.lower().endswith(".docx"):
                data = client.get_bytes(link, FEED, "pk-agenda", archive=False)
                pts, tm = docx_points(data), docx_time(data)
        except FetchError as exc:
            failed = True
            gaps.append("Podkarpackie {0}: {1}".format(label, str(exc)[:160]))
            continue
        got = points_items(pts, dated, PLENARY, mid, link or url, item_time=tm)
        items += got or [ra.item(dated, "", PLENARY, meeting_id=mid, detail=label, url=url)]
        read_ids.append(mid)
    try:
        for body, dated, tm, url, pts in parse_pk_committees(client.get_text(PK_COMMITTEES, FEED,
                                                                             "pk-committees")):
            if not ctx.in_window(dated):
                continue
            mid = _mid("pk", dated, body)
            got = points_items(pts, dated, body, mid, url, item_time=tm)
            items += got or [ra.item(dated, "", body, item_time=tm, meeting_id=mid, url=url)]
            read_ids.append(mid)
    except FetchError as exc:
        failed = True
        gaps.append("Podkarpackie committees: {0}".format(str(exc)[:160]))
    return ra.RegionRead(items, _units(ctx, failed, read_ids),
                         source="sejmik.podkarpackie.pl (sittings, porządek obrad .docx, committee notices)",
                         gaps=gaps)


# --- Kujawsko-Pomorskie --------------------------------------------------------------

KP_INDEX = "https://bip.kujawsko-pomorskie.pl/12537/sesje-sejmiku-wojewodztwa-vii-kadencji.html"


def parse_kp_index(page):
    """[(date, label, url)] of the sittings' 'Porządek obrad' pages."""
    out = []
    for href, label in re.findall(r'<a [^>]*href="(https://bip\.kujawsko-pomorskie\.pl/\d+/porzadek-obrad-[^"]+)"'
                                  r'[^>]*>(.*?)</a>', page or "", re.S):
        label = _text(label)
        d = pl_date(label)
        if d and href not in [u for _, _, u in out]:
            out.append((d, label, href))
    return out


def parse_kp_agenda(page):
    i = (page or "").find("bip-page__content")
    return li_points(first_list(page[i:] if i >= 0 else page or ""))


def read_kp(client, ctx):
    items, gaps, failed, read_ids = [], [], False, []
    for dated, label, url in parse_kp_index(client.get_text(KP_INDEX, FEED, "kp-index")):
        if not ctx.in_window(dated) or ctx.out_of_time():
            continue
        mid = _mid("kp", dated, PLENARY)
        try:
            page = client.get_text(url, FEED, "kp-agenda")
        except FetchError as exc:
            failed = True
            gaps.append("Kujawsko-Pomorskie {0}: {1}".format(label, str(exc)[:160]))
            continue
        tm = pl_time(page[page.find("bip-page__content"):][:3000]) if "bip-page__content" in page else None
        got = points_items(parse_kp_agenda(page), dated, PLENARY, mid, url, item_time=tm)
        items += got or [ra.item(dated, "", PLENARY, meeting_id=mid, detail=label, url=url)]
        read_ids.append(mid)
    return ra.RegionRead(items, _units(ctx, failed, read_ids),
                         source="bip.kujawsko-pomorskie.pl (porządek obrad pages)", gaps=gaps)


# --- Łódzkie ---------------------------------------------------------------------------

LD = "https://bip.lodzkie.pl"
LD_SITTINGS = LD + "/sejmik-wojewodztwa/plan-pracy/sesje-sejmiku"


def parse_ld_list(page, base=LD):
    """[(date, label, url)] of the 'Porządek obrad ... sesji' notices."""
    out = []
    for href, label in re.findall(r'<a[^>]*href="(/sejmik-wojewodztwa/plan-pracy/sesje-sejmiku/item/[^"]+)"[^>]*>'
                                  r'(.*?)</a>', page or "", re.S):
        label = _text(label)
        if not re.search(r"porz[aą]dek obrad", label, re.I):
            continue
        url = urllib.parse.urljoin(base, urllib.parse.quote(html.unescape(href), safe="/:%-_."))
        if url in [u for _, _, u in out]:
            continue
        # the date is in the notice's lead text, after the link
        i = page.find(href)
        d = pl_date(re.sub(r"<[^>]+>", " ", page[i:i + 2500]).split("Czytaj dalej")[0]) if i >= 0 else None
        out.append((d, label, url))
    return out


def parse_ld_item(page):
    """(time, points) of one notice: the numbered lines of its full text."""
    i = (page or "").find("itemFullText")
    body = page[i:] if i >= 0 else page or ""
    j = body.find("itemAttachmentsBlock")
    body = body[:j] if j > 0 else body
    lines = ra.clean(body).splitlines()
    pts = [line.strip() for line in lines if re.match(r"^\s*\d+(?:\.\d+)*\.\s+\S", line)]
    head = page[max(0, i - 3000):i] if i >= 0 else ""
    return pl_time(ra.clean(head)), pts


def read_ld(client, ctx):
    items, gaps, failed, read_ids = [], [], False, []
    for dated, label, url in parse_ld_list(client.get_text(LD_SITTINGS, FEED, "ld-sittings")):
        if not ctx.in_window(dated) or ctx.out_of_time():
            continue
        mid = _mid("ld", dated, PLENARY)
        try:
            tm, pts = parse_ld_item(client.get_text(url, FEED, "ld-agenda"))
        except FetchError as exc:
            failed = True
            gaps.append("Łódzkie {0}: {1}".format(label, str(exc)[:160]))
            continue
        got = points_items(pts, dated, PLENARY, mid, url, item_time=tm)
        items += got or [ra.item(dated, "", PLENARY, meeting_id=mid, detail=label, url=url)]
        read_ids.append(mid)
    return ra.RegionRead(items, _units(ctx, failed, read_ids),
                         source="bip.lodzkie.pl (porządek obrad notices)",
                         note="plenary only: committee materials are on eSesja (bot check)", gaps=gaps)


# --- Warmińsko-Mazurskie ----------------------------------------------------------------

WN = "https://bip.warmia.mazury.pl"
WN_SITTINGS = WN + "/kategoria/135/porzadek-obrad-sesji-sejmiku-wraz-z-materialami.html"
WN_COMMITTEES = WN + "/kategoria/9/porzadek-obrad-komisji-sejmiku.html"


def parse_wn_category(page, base=WN):
    """[(url, title)] of a BIP category's article list, newest first."""
    out = []
    for href, title in re.findall(r'<a href="(/\d+/[^"]+\.html)"[^>]*data-pjax="0"[^>]*>(.*?)</a>', page or "", re.S):
        title = _text(title)
        url = urllib.parse.urljoin(base, href)
        if title and url not in [u for u, _ in out]:
            out.append((url, title))
    return out


def parse_wn_attachments(page):
    """[(committee abbreviation, date)] of a month's committee agendas
    ('Porządek posiedzenia KSR 21.10.2026'; an 'aktualizacja' is the same
    meeting)."""
    out = []
    for abbr, d in re.findall(r"Porządek posiedzenia\s+([A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż.]+)\s+(\d{1,2}\.\d{1,2}\.\d{4})",
                              ra.clean(page or "")):
        row = (abbr, pl_date(d))
        if row[1] and row not in out:
            out.append(row)
    return out


def read_wn(client, ctx):
    items, gaps = [], []
    for url, title in parse_wn_category(client.get_text(WN_SITTINGS, FEED, "wn-sittings"))[:6]:
        dated = pl_date(title)
        if ctx.in_window(dated):
            items.append(ra.item(dated, "", PLENARY, meeting_id=_mid("wn", dated, PLENARY),
                                 detail=title, url=url))
    units = [ra.window(ctx.today, ctx.until)]
    try:
        months = parse_wn_category(client.get_text(WN_COMMITTEES, FEED, "wn-committees"))[:2]
        for url, title in months:
            if ctx.out_of_time():
                break
            for abbr, dated in parse_wn_attachments(client.get_text(url, FEED, "wn-committee-month")):
                if ctx.in_window(dated):
                    body = "Komisja ({0})".format(abbr)
                    items.append(ra.item(dated, "", body, meeting_id=_mid("wn", dated, body),
                                         detail="agenda as PDF: Porządek posiedzenia {0}".format(abbr), url=url))
    except FetchError as exc:
        units = [ra.day(i["dated"], PLENARY) for i in items]
        gaps.append("Warmińsko-Mazurskie committees: {0}".format(str(exc)[:160]))
    return ra.RegionRead(items, units, source="bip.warmia.mazury.pl (sitting and committee agenda articles)",
                         note="agendas are PDF attachments: sittings to be announced", gaps=gaps)


# --- Zachodniopomorskie -------------------------------------------------------------------

ZP = "https://bip.wzp.pl"
ZP_SITTINGS = ZP + "/tabela/artykuly/771/2328"


def parse_zp_sittings(page, base=ZP):
    out = []
    for href, title in re.findall(r'<a href="(/artykul/[^"]*sesja-sejmiku[^"]*)"[^>]*>(.*?)</a>', page or "", re.S):
        title = _text(title)
        d = pl_date(title)
        if d:
            out.append((d, title, urllib.parse.urljoin(base, href)))
    return out


def read_zp(client, ctx):
    items = []
    for dated, title, url in parse_zp_sittings(client.get_text(ZP_SITTINGS, FEED, "zp-sittings")):
        if ctx.in_window(dated):
            items.append(ra.item(dated, "", PLENARY, item_time=None, meeting_id=_mid("zp", dated, PLENARY),
                                 detail=title, url=url))
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="bip.wzp.pl (sitting articles)",
                         note="the porządek obrad is a scanned PDF: sittings to be announced")


REGIONS = {
    "mz": ra.region("Mazowieckie", reader=read_mz),
    "sl": ra.region("Śląskie", reader=read_sl),
    "wp": ra.region("Wielkopolskie", status="no-route",
                    note="bip.umww.pl has resolutions, protocols and roll calls by sitting, no forward "
                         "list or porządek obrad; sittings are streamed, not announced in the BIP"),
    "ma": ra.region("Małopolskie", reader=read_ma),
    "ds": ra.region("Dolnośląskie", reader=read_ds),
    "ld": ra.region("Łódzkie", reader=read_ld),
    "pm": ra.region("Pomorskie", reader=read_pm),
    "pk": ra.region("Podkarpackie", reader=read_pk),
    "lu": ra.region("Lubelskie", status="no-route",
                    note="umwl.bip.lubelskie.pl lists sittings only with their protocols (menus by "
                         "sitting, newest 2020); no porządek obrad or timetable found in the BIP"),
    "kp": ra.region("Kujawsko-Pomorskie", reader=read_kp),
    "zp": ra.region("Zachodniopomorskie", reader=read_zp),
    "wn": ra.region("Warmińsko-Mazurskie", reader=read_wn),
    "sk": ra.region("Świętokrzyskie", status="no-route",
                    note="bip.sejmik.kielce.pl 'Terminy i porządek obrad' is one PDF per sitting and "
                         "the list stops at 29 September 2025; committee pages are protocols"),
    "pd": ra.region("Podlaskie", status="no-route",
                    note="new BIP bip.podlaskie.eu: draft resolutions by sitting with the month only "
                         "(no date, no porządek obrad); bip.wrotapodlasia.pl no longer resolves"),
    "lb": ra.region("Lubuskie", status="no-route",
                    note="bip.lubuskie.pl has only a live-stream page for sittings; no timetable or "
                         "porządek obrad found"),
    "op": ra.region("Opolskie", status="no-route",
                    note="bip.opolskie.pl does not answer (robots.txt timed out three times, 13 and "
                         "16 October 2026)"),
}
