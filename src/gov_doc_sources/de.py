"""Germany: the federal ministries' draft laws (Referentenentwürfe) out to the
Länder and associations (Verbändebeteiligung), the ministries' and the
Federal Government's press releases and articles (16 October 2026).

Germany has no edition adapter in src/editions/, so the German taxonomy is
named here (TAXONOMIES).

Probed 16 October 2026; every host below asks robots.txt at run time (none is
a documented API):

  * BMJV (www.bmjv.de; www.bmj.de redirects there): the ministry's own RSS
    feed of its legislative procedures (RSSNewsfeedGesetzgebungsverfahren,
    80 items, every procedure of the period, newest change first) and its
    press releases feed (100 items). robots.txt disallows /SiteGlobals/ but
    allows /SiteGlobals/Functions/RSSNewsfeed/, so the feeds are allowed and
    the search forms under /SiteGlobals/Forms/ are not used. Each procedure
    page (/SharedDocs/Gesetzgebungsverfahren/DE/...) carries its status
    ('Entwurf' or 'Gesetz'), its stages (Referentenentwurf, Regierungsentwurf,
    parlamentarisches Verfahren, Gesetz beschlossen) and a summary; it does
    NOT carry the deadline for statements. The press release announcing a
    Referentenentwurf does ("Die interessierten Kreise haben nun Gelegenheit,
    bis zum 06.11.2026 Stellung zu nehmen") and links the procedure page, so
    the deadline is read there and attached to the procedure.
  * BMBFSFJ (www.bmbfsfj.bund.de, the family ministry since May 2025;
    www.bmfsfj.de redirects): its 'Gesetze' listing, newest first (tagline
    Gesetzgebungsvorhaben / Gesetzgebungsvorgang / Gesetz, no dates), each
    page read for its date; and two of its RSS feeds (Pressemitteilungen,
    Aktuelle Meldungen). robots.txt: "Disallow:" (empty) for every agent.
  * BMG (www.bundesgesundheitsministerium.de): its 'Gesetze und
    Verordnungen' listing (the latest ten procedures with dates), each
    detail page read for its category ('Laufendes Verfahren', 'Gesetz',
    'Verordnung') and latest stage; and its press releases RSS feed.
    robots.txt allows these paths (it disallows ?id=, cHash, forms, search).
  * Bundesregierung (www.bundesregierung.de): the RSS feeds 'Artikel'
    (explanations of cabinet decisions) and 'Pressemitteilungen' (20 items
    each, about three weeks). robots.txt has no group for our agent (only
    named crawlers are disallowed).

DOC TYPES. A procedure whose page says 'Entwurf' / 'Laufendes Verfahren' /
'Gesetzgebungsvorhaben' is a 'bill_draft' ('regulation_draft' when it is a
Verordnung), its stage in status; once the page says it is a Gesetz or a
Verordnung in force, 'law' / 'regulation'. Press releases are
'press_release', the Bundesregierung's articles and the BMBFSFJ's Meldungen
'publication'. A deadline for statements is set only where the ministry
prints one (BMJV press releases, or any page read that says "bis zum ...
Stellung"); the other ministries publish none on their pages.
"""

from __future__ import annotations

import re
import time

from src import gov_docs as G

CC = "de"
TAXONOMIES = (("taxonomy-de.yaml", "de"),)

BMJ = "https://www.bmjv.de"
BMJ_GV_RSS = BMJ + "/SiteGlobals/Functions/RSSNewsfeed/DE/RSSNewsfeed/RSSNewsfeedGesetzgebungsverfahren.xml?nn=149890"
BMJ_PM_RSS = BMJ + "/SiteGlobals/Functions/RSSNewsfeed/DE/RSSNewsfeed/RSSNewsfeedPressemitteilungen.xml?nn=149890"
BMFSFJ = "https://www.bmbfsfj.bund.de"
BMFSFJ_LAWS = BMFSFJ + "/bmbfsfj/ministerium/gesetze"
BMFSFJ_RSS = ((BMFSFJ + "/service/rss/bmbfsfj/111102/feed.rss", "press_release"),
              (BMFSFJ + "/service/rss/bmbfsfj/108854/feed.rss", "publication"))
BMG = "https://www.bundesgesundheitsministerium.de"
BMG_LAWS = BMG + "/service/gesetze-und-verordnungen"
BMG_PM_RSS = BMG + "/pressemitteilungen.xml"
BREG_RSS = (("https://www.bundesregierung.de/service/rss/breg-de/1151246/feed.xml", "publication"),
            ("https://www.bundesregierung.de/service/rss/breg-de/1151244/feed.xml", "press_release"))

PAGE_CAP = 30            # procedure pages read per source per run
PM_PAGE_CAP = 15         # BMJV press releases read for a deadline
SOURCE_BUDGET = 150      # seconds of page reads per source

FEED = "de-govdocs"
BODY_BMJ = "Bundesministerium der Justiz und für Verbraucherschutz"
BODY_BMFSFJ = "Bundesministerium für Bildung, Familie, Senioren, Frauen und Jugend"
BODY_BMG = "Bundesministerium für Gesundheit"
BODY_BREG = "Bundesregierung"

_MON = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12}


# --- shared parsing --------------------------------------------------------------

def rss_date(value):
    """ISO date from an RSS pubDate ('Mon, 12 Oct 2026 09:43:00 +0200', with any
    zone name) or an ISO date, as printed (no zone conversion)."""
    s = str(value or "")
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", s)
    if m and m.group(2).lower() in _MON:
        return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), _MON[m.group(2).lower()], int(m.group(1)))
    return G.iso(s)


def _tag(block, name):
    m = re.search(r"<{0}(?:\s[^>]*)?>(.*?)</{0}>".format(name), block, re.S)
    if not m:
        return ""
    v = m.group(1).strip()
    c = re.match(r"<!\[CDATA\[(.*?)\]\]>$", v, re.S)
    return c.group(1) if c else v


def rss_items(xml):
    """[{title, link, description, published, author}] from an RSS 2.0 feed."""
    out = []
    for block in re.findall(r"<item(?:\s[^>]*)?>(.*?)</item>", xml or "", re.S):
        link = G.text(_tag(block, "link")) or G.text(_tag(block, "guid"))
        out.append({"title": G.text(_tag(block, "title")), "link": link,
                    "description": G.text(_tag(block, "description")),
                    "published": rss_date(_tag(block, "pubDate")),
                    "author": G.text(_tag(block, "author"))})
    return out


_DEADLINE = re.compile(
    r"bis\s+(?:zum|spätestens\s+zum|spätestens|einschließlich)?\s*"
    r"(\d{1,2}\.\s?\d{1,2}\.\s?\d{4}|\d{1,2}\.\s*[A-Za-zäÄ]+\s+\d{4})"
    r"[^.]{0,120}?Stellung", re.I)


def deadline(page_text):
    """The deadline for statements a page prints ("bis zum 06.11.2026 Stellung zu
    nehmen", "bis 6. November 2026 ... Stellungnahmen"); else None."""
    m = _DEADLINE.search(page_text or "")
    if not m:
        return None
    return G.iso(m.group(1)) or G.long_date(m.group(1))


def is_regulation(title):
    """A Verordnung by its title: it opens with one ('Verordnung zur ...',
    'Dritte Verordnung ...', 'Entwurf einer Verordnung ...'), or names one
    and no Gesetz."""
    t = G.one_line(title).lower()
    if re.match(r"^(?:entwurf einer\s+)?(?:\w+\s+)?verordnung\b", t):
        return True
    return "verordnung" in t and "gesetz" not in t


def draft_type(title):
    return "regulation_draft" if is_regulation(title) else "bill_draft"


def made_type(title):
    return "regulation" if is_regulation(title) else "law"


def page_text(page):
    """Visible text of a page's main part (scripts dropped)."""
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page or "", flags=re.S | re.I)
    i = page.find("<main")
    return G.text(page[i:] if i >= 0 else page)


def _slug(url):
    return re.sub(r"\.html?$", "", (url or "").split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1])


class _Budget:
    def __init__(self, cap, seconds=SOURCE_BUDGET):
        self.cap, self.left, self.until = cap, cap, time.monotonic() + seconds

    def take(self):
        if self.left <= 0 or time.monotonic() > self.until:
            return False
        self.left -= 1
        return True


# --- BMJV ------------------------------------------------------------------------

def parse_bmj_procedure(page):
    """{status, stage, published, summary, closing_date} from a procedure page."""
    st = re.search(r'c-meta-info__status[^"]*">([^<]*)<', page or "")
    heads = [G.text(h).split(":")[-1].strip() for h in
             re.findall(r'class="c-law-list__headline"[^>]*>(.*?)</h2>', page or "", re.S)]
    pub = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})', page or "")
    rich = re.search(r'<div class="s-richtext">(.*?)</div>', page or "", re.S)
    return {"status": G.one_line(st.group(1)) if st else None,
            "stage": heads[-1] if heads else None,
            "published": pub.group(1) if pub else None,
            "summary": re.split(r"\s*Weitere Details \(zu ", G.text(rich.group(1)))[0] if rich else None,
            "closing_date": deadline(page_text(page))}


def bmj_entry(item, detail=None, closing=None):
    title, url = item["title"], item["link"].split("?", 1)[0]
    d = detail or {}
    st = (d.get("status") or "").lower()
    reg = is_regulation(title) or st == "verordnung" or "verordnung" in (d.get("stage") or "").lower()
    if st in ("gesetz", "verordnung", "in kraft", "verkündet"):
        kind = "regulation" if reg else "law"
    else:
        kind = "regulation_draft" if reg else "bill_draft"
    status = d.get("status")
    if d.get("stage"):
        status = "{0}; {1}".format(status, d["stage"]) if status else d["stage"]
    return G.entry("bmj", _slug(url), title, kind, body=BODY_BMJ,
                   published=item["published"], closing_date=closing or d.get("closing_date"),
                   url=url, summary=d.get("summary") or item.get("description"), status=status)


def parse_bmj_press(page):
    """(deadline, [procedure urls]) from a BMJV press release page."""
    procs = sorted({u.split("?", 1)[0] for u in re.findall(
        r'href="(https://www\.bmjv?\.de/SharedDocs/Gesetzgebungsverfahren/DE/[^"]+)"', page or "")})
    procs = [u.replace("://www.bmj.de/", "://www.bmjv.de/") for u in procs]
    return deadline(page_text(page)), procs


_PM_DRAFT = re.compile(r"entwurf|verordnung|stellung|vorgelegt|verbände", re.I)


def fetch_bmj(client, today, log=print):
    start = G.window_start(today)
    gaps, out = [], []
    try:
        procs = rss_items(client.get_text(BMJ_GV_RSS, FEED, "bmj-gesetzgebung"))
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["BMJV procedures feed unreadable: {0}".format(str(exc)[:160])])
    try:
        press = rss_items(client.get_text(BMJ_PM_RSS, FEED, "bmj-presse"))
    except Exception as exc:                                # noqa: BLE001
        press = []
        gaps.append("BMJV press feed unreadable: {0}".format(str(exc)[:160]))
    closes = {}
    budget = _Budget(PM_PAGE_CAP)
    for p in press:
        if (p["published"] or "") < start:
            continue
        out.append(G.entry("bmj", "pm-" + "/".join(p["link"].split("?", 1)[0].split("/")[-2:])
                           .replace(".html", ""), p["title"], "press_release", body=BODY_BMJ,
                           published=p["published"], url=p["link"], summary=p["description"]))
        if not _PM_DRAFT.search(p["title"] + " " + p["description"]) or not budget.take():
            continue
        try:
            when, linked = parse_bmj_press(client.get_text(p["link"], FEED, "bmj-pm-" + _slug(p["link"])))
        except Exception as exc:                            # noqa: BLE001
            gaps.append("BMJV press release {0} unreadable: {1}".format(_slug(p["link"]), str(exc)[:100]))
            continue
        if when:
            for u in linked:
                closes.setdefault(u, when)
    budget = _Budget(PAGE_CAP)
    for item in procs:
        url = item["link"].split("?", 1)[0]
        detail = None
        if (item["published"] or "") >= start and budget.take():
            try:
                detail = parse_bmj_procedure(client.get_text(url, FEED, "bmj-" + _slug(url)))
            except Exception as exc:                        # noqa: BLE001
                gaps.append("BMJV procedure {0} unreadable: {1}".format(_slug(url), str(exc)[:100]))
        out.append(bmj_entry(item, detail, closes.get(url)))
    return G.fetched(out, note="{0} procedures in the feed, {1} press releases; {2} deadline(s) "
                     "from press releases".format(len(procs), len(press), len(closes)), gaps=gaps)


# --- BMBFSFJ ---------------------------------------------------------------------

def parse_bmfsfj_laws(page):
    """[{tagline, title, url, teaser}] from the Gesetze listing."""
    out = []
    for li in re.findall(r'<li class="teaser-list-item"\s*>(.*?)</li>', page or "", re.S):
        a = re.search(r'<a href="([^"]+)" class="text-link">(.*?)</a>', li, re.S)
        if not a:
            continue
        tag = re.search(r'<span class="teaser-tagline"\s*>(.*?)</span>', li, re.S)
        teaser = re.search(r'<p class="teaser-text">(.*?)</p>', li, re.S)
        href = a.group(1)
        out.append({"tagline": G.text(tag.group(1)) if tag else "", "title": G.text(a.group(2)),
                    "url": href if href.startswith("http") else BMFSFJ + href,
                    "teaser": G.text(teaser.group(1)) if teaser else ""})
    return out


def parse_bmfsfj_page(page):
    """{published, closing_date} from a BMBFSFJ article page."""
    m = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})', page or "")
    return {"published": m.group(1) if m else None, "closing_date": deadline(page_text(page))}


def bmfsfj_law_entry(item, detail=None):
    d = detail or {}
    kind = made_type(item["title"]) if item["tagline"] == "Gesetz" else draft_type(item["title"])
    num = re.search(r"-(\d+)$", _slug(item["url"]))
    return G.entry("bmfsfj", "gesetz-" + (num.group(1) if num else _slug(item["url"])), item["title"],
                   kind, body=BODY_BMFSFJ, published=d.get("published"),
                   closing_date=d.get("closing_date"), url=item["url"], summary=item["teaser"],
                   status=item["tagline"] or None)


def bmfsfj_news_entries(items, kind):
    out = []
    for it in items:
        num = re.search(r"-(\d+)$", _slug(it["link"]))
        out.append(G.entry("bmfsfj", (num.group(1) if num else _slug(it["link"])), it["title"], kind,
                           body=BODY_BMFSFJ, published=it["published"], url=it["link"],
                           summary=it["description"]))
    return out


def fetch_bmfsfj(client, today, log=print):
    gaps, out, seen = [], [], set()
    try:
        laws = parse_bmfsfj_laws(client.get_text(BMFSFJ_LAWS, FEED, "bmfsfj-gesetze"))
    except Exception as exc:                                # noqa: BLE001
        laws = []
        gaps.append("BMBFSFJ law listing unreadable: {0}".format(str(exc)[:160]))
    if not laws and not gaps:
        gaps.append("BMBFSFJ law listing parsed nothing (layout changed?)")
    budget = _Budget(PAGE_CAP)
    for item in laws:
        detail = None
        if budget.take():
            try:
                detail = parse_bmfsfj_page(client.get_text(item["url"], FEED, "bmfsfj-" + _slug(item["url"])))
            except Exception as exc:                        # noqa: BLE001
                gaps.append("BMBFSFJ page {0} unreadable: {1}".format(_slug(item["url"]), str(exc)[:100]))
        out.append(bmfsfj_law_entry(item, detail))
    for url, kind in BMFSFJ_RSS:
        try:
            items = rss_items(client.get_text(url, FEED, "bmfsfj-rss-" + url.split("/")[-2]))
        except Exception as exc:                            # noqa: BLE001
            gaps.append("BMBFSFJ feed {0} unreadable: {1}".format(url.split("/")[-2], str(exc)[:120]))
            continue
        for e in bmfsfj_news_entries(items, kind):
            if e["doc_id"] not in seen:
                seen.add(e["doc_id"])
                out.append(e)
    return G.fetched(out, note="{0} law pages listed, {1} news items".format(len(laws), len(seen)),
                     gaps=gaps)


# --- BMG -------------------------------------------------------------------------

def parse_bmg_laws(page):
    """[{date, title, url}] from the Gesetze und Verordnungen listing."""
    out = []
    for block in re.findall(r'<div data-module-identifier="ce-teaser"(.*?)</li>', page or "", re.S):
        d = re.search(r'c-teaser__date-left[^"]*">([^<]+)<', block)
        a = re.search(r'<a href="(/service/gesetze-und-verordnungen/detail/[^"]+)" title="([^"]*)"', block)
        if a:
            out.append({"date": G.iso(d.group(1)) if d else None, "title": G.text(a.group(2)),
                        "url": BMG + a.group(1)})
    return out


def parse_bmg_detail(page):
    """{category, stage, long_title, closing_date} from a BMG detail page."""
    i = (page or "").find("c-banner-category__content")
    block = page[i:i + 4000] if i >= 0 else ""
    cat = re.search(r'c-category-title[^"]*">([^<]*)<', block)
    h2 = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
    para = re.search(r"<p>(.*?)</p>", block, re.S)
    stage = None
    if para:
        first = re.split(r"<br\s*/?>", para.group(1))[0]
        stage = G.text(first) or None
    return {"category": G.one_line(cat.group(1)) if cat else None,
            "long_title": G.text(h2.group(1)) if h2 else None, "stage": stage,
            "closing_date": deadline(page_text(page))}


def bmg_law_entry(item, detail=None):
    d = detail or {}
    cat = (d.get("category") or "").lower()
    if cat in ("gesetz", "verordnung"):
        kind = "regulation" if cat == "verordnung" else "law"
    else:
        kind = draft_type(item["title"] + " " + (d.get("long_title") or ""))
    status = "; ".join(x for x in (d.get("category"), d.get("stage")) if x) or None
    return G.entry("bmg", _slug(item["url"]), item["title"], kind, body=BODY_BMG,
                   published=item["date"], closing_date=d.get("closing_date"), url=item["url"],
                   summary=d.get("long_title"), status=status)


def fetch_bmg(client, today, log=print):
    start = G.window_start(today)
    gaps, out = [], []
    try:
        laws = parse_bmg_laws(client.get_text(BMG_LAWS, FEED, "bmg-gesetze"))
    except Exception as exc:                                # noqa: BLE001
        laws = []
        gaps.append("BMG law listing unreadable: {0}".format(str(exc)[:160]))
    if not laws and not gaps:
        gaps.append("BMG law listing parsed nothing (layout changed?)")
    budget = _Budget(PAGE_CAP)
    for item in laws:
        detail = None
        if (item["date"] or "") >= start and budget.take():
            try:
                detail = parse_bmg_detail(client.get_text(item["url"], FEED, "bmg-" + _slug(item["url"])))
            except Exception as exc:                        # noqa: BLE001
                gaps.append("BMG page {0} unreadable: {1}".format(_slug(item["url"]), str(exc)[:100]))
        out.append(bmg_law_entry(item, detail))
    try:
        press = rss_items(client.get_text(BMG_PM_RSS, FEED, "bmg-presse"))
    except Exception as exc:                                # noqa: BLE001
        press = []
        gaps.append("BMG press feed unreadable: {0}".format(str(exc)[:160]))
    for p in press:
        if (p["published"] or "") < start:
            continue
        out.append(G.entry("bmg", "pm-" + _slug(p["link"]), p["title"], "press_release", body=BODY_BMG,
                           published=p["published"], url=p["link"], summary=p["description"]))
    return G.fetched(out, note="{0} procedures listed, {1} press releases in the feed".format(
        len(laws), len(press)), gaps=gaps)


# --- Bundesregierung -------------------------------------------------------------

def breg_entries(items, kind):
    out = []
    for it in items:
        if "/aktuelles/" not in it["link"]:
            continue
        num = re.search(r"-(\d+)$", _slug(it["link"]))
        out.append(G.entry("breg", num.group(1) if num else _slug(it["link"]), it["title"], kind,
                           body=BODY_BREG, published=it["published"], url=it["link"],
                           summary=it["description"]))
    return out


def fetch_breg(client, today, log=print):
    gaps, out, seen = [], [], set()
    for url, kind in BREG_RSS:
        try:
            items = rss_items(client.get_text(url, FEED, "breg-rss-" + url.split("/")[-2]))
        except Exception as exc:                            # noqa: BLE001
            gaps.append("Bundesregierung feed {0} unreadable: {1}".format(url.split("/")[-2], str(exc)[:120]))
            continue
        for e in breg_entries(items, kind):
            if e["doc_id"] not in seen:
                seen.add(e["doc_id"])
                out.append(e)
    return G.fetched(out, note="{0} items from two feeds (about three weeks)".format(len(out)), gaps=gaps)


SOURCES = (
    G.Source(code="bmj", name="BMJV legislative procedures and press releases", fetch=fetch_bmj,
             url=BMJ_GV_RSS),
    G.Source(code="bmfsfj", name="BMBFSFJ laws, press releases and news", fetch=fetch_bmfsfj,
             url=BMFSFJ_LAWS),
    G.Source(code="bmg", name="BMG laws and regulations, press releases", fetch=fetch_bmg,
             url=BMG_LAWS),
    G.Source(code="breg", name="Bundesregierung articles and press releases", fetch=fetch_breg,
             url="https://www.bundesregierung.de/breg-de/service/newsletter-und-abos/rss-newsfeed"),
)
