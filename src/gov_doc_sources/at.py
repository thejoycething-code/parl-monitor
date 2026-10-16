"""Austria: Ministerialentwürfe in Begutachtung (mirrored), the Council of
Ministers' papers, and the Federal Chancellery's and the social and health
ministry's news (16 October 2026).

The edition adapter (src/editions/at.py) supplies the taxonomy (taxonomy-atch).

BEGUTACHTUNG (mirror). src/petition_sources/at.py already reads the
Parliament's Filter list 81 (a documented Open Data API) into
country_petitions (cc 'at', source 'me', kind 'consultation') every week:
each government draft in Begutachtung, with its ministry and its
Begutachtungsfrist (the deadline for statements). The rows are re-filed here,
not fetched twice: a draft law is a 'bill_draft', a draft Verordnung a
'regulation_draft', closing_date the Frist, body the ministry.

MINISTERRAT (www.bundeskanzleramt.gv.at/medien/ministerraete.html). The
current government's index of Council of Ministers sittings and circular
resolutions (Umlaufbeschlüsse), each page listing the Ministerratsvorträge
(the ministers' papers the government adopted, "Titel; 66/5") as PDFs. Each
paper is a 'publication', body "Bundesregierung (Ministerrat)", dated by the
sitting. Pages of the sittings in the window are read (at most SITTING_CAP).

NEWS. The Federal Chancellery's 'Nachrichten der Bundesregierung' (the
government's news, including the family, youth and integration minister's)
and the social and health ministry's 'Aktuelles' (BMASGPK), both card
listings of the federal CMS with a date, a title and a teaser, a page per
year. 'press_release'.

robots.txt (read 16 October 2026): www.bundeskanzleramt.gv.at disallows only
/401 and /401.html for every agent; www.sozialministerium.gv.at disallows
/.search/, /Portal.Node/, test folders and /.syndication/ (its RSS route,
which is therefore not used) and allows /Services/Aktuelles/.

NOT READ. The RIS OGD API (data.bka.gv.at/ris/api/v2.6/, the documented
open-data API of the Bundesgesetzblatt) is refused by robots.txt as things
stand: data.bka.gv.at/robots.txt is "User-agent: * / Disallow: /". The RIS
website (www.ris.bka.gv.at) answers 503 with a "Security Check" page (a WAF
challenge), never bypassed. Made law therefore waits on the lead's decision
about the API (docs/austria-scope.md).
"""

from __future__ import annotations

import datetime
import re
import time

from src import gov_docs as G

CC = "at"
BKA = "https://www.bundeskanzleramt.gv.at"
MR_INDEX = BKA + "/medien/ministerraete.html"
BKA_NEWS = BKA + "/bundeskanzleramt/nachrichten-der-bundesregierung/{year}.html?currentPage={page}"
SOZ = "https://www.sozialministerium.gv.at"
SOZ_NEWS = SOZ + "/Services/Aktuelles/archiv-{year}.html"
PARL = "https://www.parlament.gv.at"
FEED = "at-govdocs"
SITTING_CAP = 16
NEWS_PAGES = 3
SOURCE_BUDGET = 150


# --- Begutachtung mirror -----------------------------------------------------------

def draft_kind(title):
    t = (title or "").lower()
    if "gesetz" in t:
        return "bill_draft"
    return "regulation_draft" if "verordnung" in t else "bill_draft"


def mirror_me(conn, cc, today):
    start = G.window_start(today)
    try:
        rows = conn.execute(
            "SELECT item_id, title, status, opened, closes, body, url, summary, last_seen "
            "FROM country_petitions WHERE cc = ? AND source = 'me' AND kind = 'consultation' "
            "AND (closes >= ? OR opened >= ?)", (cc, start, start)).fetchall()
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["country_petitions unreadable: {0}".format(str(exc)[:160])])
    out = []
    for r in rows:
        key = r[0].split(":", 1)[-1]
        out.append(G.entry("me", key, r[1], draft_kind(r[1]), body=r[5], published=r[3],
                           closing_date=r[4], url=r[6], summary=r[7], status=r[2],
                           refs=[key]))
    ever = conn.execute("SELECT COUNT(*), MAX(last_seen) FROM country_petitions WHERE cc = ? "
                        "AND source = 'me'", (cc,)).fetchone()
    last = ever[1] if ever else None
    gaps = [] if ever and ever[0] else ["country_petitions holds no Ministerialentwurf at all "
                                        "(has the petitions step run?)"]
    return G.fetched(out, note="mirrored from country_petitions source 'me' (last read {0})"
                     .format(last), gaps=gaps)


# --- Ministerrat -------------------------------------------------------------------

def parse_mr_index(page):
    """The current government's sittings index: the first ministerraete-seit link."""
    m = re.search(r'href="(/medien/ministerraete/ministerraete-[^"/]+\.html)"', page or "")
    return BKA + m.group(1) if m else None


def parse_sittings(page):
    """[{url, label, date}] from a government's sittings index, newest first."""
    out = []
    for href, label in re.findall(
            r'<a [^>]*href="(/medien/ministerraete/ministerraete-[^"/]+/[^"]+\.html)"[^>]*>(.*?)</a>',
            page or "", re.S):
        label = G.text(label)
        out.append({"url": BKA + href, "label": label, "date": G.long_date(label)})
    return out


_MRV = re.compile(r";\s*(\d+[a-z]?/\d+)\s*$")


def parse_sitting(page):
    """[(number, title, pdf url)] for the Ministerratsvorträge on a sitting's page
    (annexes, Vorblätter and Erläuterungen are left out)."""
    out = []
    for href, inner in re.findall(r'<a href="(/dam/[^"]+\.pdf)"[^>]*>(.*?)</a>', page or "", re.S):
        inner = re.sub(r'<span class="fileinfo">.*?</span>', "", inner, flags=re.S)
        title = G.text(inner)
        m = _MRV.search(title)
        if not m:
            continue
        out.append((m.group(1), _MRV.sub("", title).rstrip(" ;"), BKA + href))
    return out


def fetch_mr(client, today, log=print):
    start = G.window_start(today)
    gaps, out = [], []
    try:
        index = parse_mr_index(client.get_text(MR_INDEX, FEED, "bka-ministerraete"))
        if not index:
            return G.fetched([], gaps=["Ministerrat index has no government link (layout changed?)"])
        sittings = parse_sittings(client.get_text(index, FEED, "bka-ministerraete-regierung"))
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["Ministerrat index unreadable: {0}".format(str(exc)[:160])])
    until = time.monotonic() + SOURCE_BUDGET
    read = 0
    for s in sittings:
        if not s["date"] or s["date"] < start:
            continue
        if read >= SITTING_CAP or time.monotonic() > until:
            gaps.append("Ministerrat: stopped at {0} sitting pages; older ones in the window not read"
                        .format(read))
            break
        read += 1
        try:
            papers = parse_sitting(client.get_text(s["url"], FEED, "bka-mr-" + s["url"].rsplit("/", 1)[-1]))
        except Exception as exc:                            # noqa: BLE001
            gaps.append("Ministerrat page {0} unreadable: {1}".format(s["label"], str(exc)[:100]))
            continue
        for num, title, pdf in papers:
            out.append(G.entry("mr", num, title, "publication", body="Bundesregierung (Ministerrat)",
                               published=s["date"], url=pdf, status=s["label"],
                               summary="Ministerratsvortrag {0}, {1}".format(num, s["label"])))
    return G.fetched(out, note="{0} sittings listed, {1} read in the window".format(len(sittings), read),
                     gaps=gaps)


# --- news card listings ------------------------------------------------------------

def parse_cards(page, base):
    """[{url, date, title, teaser}] from a federal CMS card listing."""
    out = []
    for block in re.findall(r'<a href="([^"]+)" class="card-link"\s*>(.*?)</a>', page or "", re.S):
        href, inner = block
        d = re.search(r'<small class="card-date">([^<]+)</small>', inner)
        h = re.search(r'<h2 class="card-title-heading">(.*?)</h2>', inner, re.S)
        p = re.search(r'<p class="card-text">(.*?)</p>', inner, re.S)
        if not h:
            continue
        out.append({"url": href if href.startswith("http") else base + href,
                    "date": G.long_date(d.group(1)) if d else None, "title": G.text(h.group(1)),
                    "teaser": G.text(p.group(1)) if p else ""})
    return out


def _years(today):
    t = datetime.date.fromisoformat(today)
    first = datetime.date.fromisoformat(G.window_start(today)).year
    return list(range(t.year, first - 1, -1))


def _card_entries(cards, source, body):
    out = []
    for c in cards:
        key = re.sub(r"\.html$", "", c["url"].split("?", 1)[0]).rsplit("/", 1)[-1]
        ym = re.search(r"/(\d{4})/(\d{2})/", c["url"])
        if ym:
            key = "{0}-{1}/{2}".format(ym.group(1), ym.group(2), key)
        out.append(G.entry(source, key, c["title"], "press_release", body=body, published=c["date"],
                           url=c["url"], summary=c["teaser"]))
    return out


def fetch_bka_news(client, today, log=print):
    start = G.window_start(today)
    gaps, cards = [], []
    for year in _years(today):
        for page in range(NEWS_PAGES):
            url = BKA_NEWS.format(year=year, page=page)
            try:
                got = parse_cards(client.get_text(url, FEED, "bka-news-{0}-{1}".format(year, page)), BKA)
            except Exception as exc:                        # noqa: BLE001
                gaps.append("BKA news {0} page {1} unreadable: {2}".format(year, page, str(exc)[:100]))
                break
            cards += got
            if not got or min((c["date"] or "9999") for c in got) < start:
                break
    return G.fetched(_card_entries(cards, "bka", "Bundeskanzleramt"),
                     note="{0} news items read".format(len(cards)), gaps=gaps)


def fetch_soz_news(client, today, log=print):
    gaps, cards = [], []
    for year in _years(today):
        url = SOZ_NEWS.format(year=year)
        try:
            cards += parse_cards(client.get_text(url, FEED, "soz-news-{0}".format(year)), SOZ)
        except Exception as exc:                            # noqa: BLE001
            gaps.append("Sozialministerium news {0} unreadable: {1}".format(year, str(exc)[:100]))
    return G.fetched(_card_entries(cards, "soz", "Bundesministerium für Arbeit, Soziales, Gesundheit, "
                                   "Pflege und Konsumentenschutz"),
                     note="{0} news items read".format(len(cards)), gaps=gaps)


SOURCES = (
    G.Source(code="me", name="Ministerialentwürfe in Begutachtung (mirrored)", mirror=mirror_me,
             url=PARL + "/Filter/api/filter/data/81"),
    G.Source(code="mr", name="Ministerrat papers (Bundeskanzleramt)", fetch=fetch_mr, url=MR_INDEX),
    G.Source(code="bka", name="Nachrichten der Bundesregierung (Bundeskanzleramt)", fetch=fetch_bka_news,
             url=BKA + "/bundeskanzleramt/nachrichten-der-bundesregierung.html"),
    G.Source(code="soz", name="Sozialministerium news", fetch=fetch_soz_news,
             url=SOZ + "/Services/Aktuelles.html"),
)
