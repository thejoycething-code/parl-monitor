#!/usr/bin/env python3
"""Austria's Landtage (AT6, 12 October 2026): the documents of seven of the
nine Land parliaments, into atl_items (src/atl_store.py).

    python3 tools/at_landtage.py                       # the weekly: every Land read
    python3 tools/at_landtage.py --land noe --land wien
    python3 tools/at_landtage.py --since 2026-09-01    # widen the dated searches
    python3 tools/at_landtage.py --reclassify          # re-derive areas, offline
    python3 tools/at_landtage.py --db /tmp/atl.db      # anywhere but the store
    python3 tools/at_landtage.py --ris                 # also try RIS Landesrecht

SCHEDULED as a step of jobs/at-weekly.sh (after the national collector,
before the edition): time-boxed, never fatal, its gaps are [gap] lines.

NO TWO LANDTAGE SHARE A PLATFORM (docs/austria-regions-scope.md, every
number measured on 12 October 2026), so each Land has its own reader here:

  wien  INFODAT (Next.js, server-rendered): /infodat/suchergebnisse with
        committees=L and a sitting-day window; 20 rows a page, dated by the
        sitting. /infodat/ergli and /infodat/sukri are disallowed in
        robots.txt and are never asked for.
  wien-gr  the same INFODAT, committees=G: Vienna's Gemeinderat (the city
        council: the same people as the Landtag, deciding the city's
        funding, schools as their owner and its ordinances). About 450
        rows (23 pages) in a three-week-back, two-month-ahead window on 12
        October 2026, most of them the Stadtsenat's routine proposals; read
        up to 40 pages. Its first read is a baseline in full (dated rows
        included), so the old business never floods the edition.
  noe   TYPO3 'parliament' extension: /gegenstaende/XX/suche?page=N, 25 a
        page, newest number first, undated; the document's own page gives
        the dated Historie and the status (read for rows on our ground).
  ooe   LIS (JSP): Start.jsp for a SessionID, then a search by Eingangsdatum,
        up to 500 rows a page; the Beilage's own page gives the Eingang date
        and, for laws, the decision with the Klubs for and against.
  stmk  PALLAST (JSF/PrimeFaces): the document list sorted by submission,
        then the table's own paging call (rows=100) with the page's
        ViewState and cookie. Undated; the document's page gives
        'eingebracht am' and the introducers.
  sbg   LPI (Spring MVC): /lpi/searchExtern by date, every hit on one page,
        dated ("Meldung vom").
  vbg   LIS (Lotus Domino): the materials view as XML (?ReadViewEntries),
        the current Landtagsperiode in two requests; undated, the document's
        page gives 'Eingelangt in der Landtagsdirektion' (MM/DD/YYYY).
  bgld  Vorlagen (Domino XPages): the newest 30 by Zahl, undated; a later
        page needs a postback, so a week with more than 30 new Vorlagen is
        a gap, never a silent cut.

NOT READ: Kärnten (www.ktn.gv.at disallows every robot but Google's and
Bing's) and Tirol (lte.tirol.gv.at disallows every robot). RIS Landesrecht,
the adopted Land laws of all nine: data.bka.gv.at disallows every robot and
www.ris.bka.gv.at answers a bot check, so --ris asks robots.txt first and
records the refusal as a gap; the parser (parse_ris) is tested on the one
reply read while probing, before robots.txt was read.

POLITENESS: the honest CitizenGO UA, at least 1.1 s between requests to a
host (src/prov_fetch.Context), robots.txt read once per host and honoured
(a disallowed URL is a gap, never fetched), lists archived to data/raw.

CLASSIFICATION: titles only, with config/taxonomy-atch.yaml for 'at' (the
same list as the national edition), plus the `landtage` section of
config/watchlist-at.yaml by key. Every row is stored (the areas can be
re-derived offline with --reclassify); only rows on our ground get their
own page read.

Exit 3 when anything was stored and gaps were recorded (jobs/at-weekly.sh
treats it as a [gap] line), 1 when nothing could be read at all.
Separation guarantee: writes atl_* and the shared gaps table only.
"""

from __future__ import annotations

import argparse
import datetime
import html
import http.cookiejar
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import atl_store, db, drain, filter as filt  # noqa: E402
from src.http import HttpClient  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FEED = "at-landtage"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-atch.yaml")
TAXONOMY_COUNTRY = "at"
HIDDEN_AREAS = (11,)        # migration is collated, never campaigned
GAPS_EXIT = 3
LOOKBACK_DAYS = 21          # the dated searches re-read three weeks: upserts are idempotent
DETAIL_REFRESH_DAYS = 7     # an open item on our ground has its page re-read weekly
DETAIL_MAX_AGE_DAYS = 120   # ...while it was listed in the last four months
MAX_DETAILS = 60            # per Land per run; the clock is the real bound
WIEN_MAX_PAGES = {"wien": 25, "wien-gr": 40}    # INFODAT's 20-row pages per run
WIEN_COMMITTEE = {"wien": "L", "wien-gr": "G"}  # Landtag, Gemeinderat

# The current Gesetzgebungsperioden (each Land counts its own).
NOE_GP = "XX"               # since 23 March 2023
OOE_GP = "XXIX"             # since 23 October 2021
STMK_GP = "XIX"             # since 18 December 2024
SBG_GP = "17"               # since 2023
VBG_PERIOD = "32. Landtagsperiode"    # 6 November 2024 to 5 November 2029
BGLD_GP = "XXIII"           # since 2025

NOE = "https://noe-landtag.gv.at"
OOE = "https://www2.land-oberoesterreich.gv.at/internetltgbeilagen/"
STMK = "https://pallast2.stmk.gv.at"
STMK_LIST = STMK + "/pallast-p/pub/documents?type=LANDTAGSDOKUMENTE&sort=tssubmit&order=desc"
WIEN = "https://www.wien.gv.at"
SBG = "https://service.salzburg.gv.at/lpi/"
VBG = "https://suche.vorarlberg.at/VLR/vlr_gov.nsf/"
VBG_VIEW = VBG + "8327314e714a8813c1257cb3004d46bb"
BGLD = "https://ltmobil.bgld-landtag.at/vorlagen.nsf/VorlZahl_GP{0}.xsp".format(BGLD_GP)
RIS = ("https://data.bka.gv.at/ris/api/v2.6/Landesrecht?Applikation=LgblAuth"
       "&Kundmachungsdatum.Periode=ZweiWochen&DokumenteProSeite=OneHundred"
       + "".join("&Bundesland.SucheIn{0}=true".format(b) for b in (
           "Burgenland", "Kaernten", "Niederoesterreich", "Oberoesterreich", "Salzburg",
           "Steiermark", "Tirol", "Vorarlberg", "Wien")))
RIS_LAND = {"Burgenland": "bgld", "Kärnten": "ktn", "Niederösterreich": "noe",
            "Oberösterreich": "ooe", "Salzburg": "sbg", "Steiermark": "stmk", "Tirol": "tir",
            "Vorarlberg": "vbg", "Wien": "wien"}


# -- small helpers -------------------------------------------------------------

def text_of(fragment):
    """Tags out, entities decoded, spaces squashed."""
    s = re.sub(r"<br\s*/?>", " ", fragment or "", flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()


def page_text(page):
    return text_of(re.sub(r"<script.*?</script>|<style.*?</style>", " ", page or "", flags=re.S))


def de_date(text):
    """'05.10.2026' -> '2026-10-05'; None when there is none."""
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text or "")
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    try:
        return datetime.date(y, mth, d).isoformat()
    except ValueError:
        return None


def us_date(text):
    """Vorarlberg's Domino prints MM/DD/YYYY: '10/02/2026' -> '2026-10-02'."""
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text or "")
    if not m:
        return None
    mth, d, y = (int(x) for x in m.groups())
    try:
        return datetime.date(y, mth, d).isoformat()
    except ValueError:
        return None


def kind_of(doc_type, title=""):
    """Our kind from the source's own type, title as a fallback:
    bill, motion, question, answer, report, decision, law, consultation, other."""
    t = (doc_type or "").lower()
    ti = (title or "").lower()
    if re.search(r"begutachtung", t):
        return "consultation"
    if re.search(r"kundmachung|landesgesetz$|^gesetz$", t):
        return "law"
    if re.search(r"beantwortung|^antwort", t) or (not t and ti.startswith("beantwortung")):
        return "answer"
    if re.search(r"anfrage|befragung", t):
        return "question"
    if t == "beschluss":
        return "decision"
    if re.search(r"regierungsvorlage|gesetzentwurf|gesetzesentwurf|ausschussvorlage", t):
        return "bill"
    if re.search(r"antrag|anträge|entschließung|petition|eingabe|klubvorlage", t):
        return "motion"
    if re.search(r"bericht|rechnungshof|untersuchungsaussch", t):
        return "report"
    if not t:
        if re.match(r"(dringliche |mündliche )?anfrage", ti):
            return "question"
        if re.match(r"(dringlicher )?antrag", ti):
            return "motion"
        if re.match(r"(vorlage der landesregierung|regierungsvorlage)", ti):
            return "bill"
        if re.match(r"bericht", ti):
            return "report"
    return "other"


OOE_ART = {
    "IA": "motion", "A": "motion", "ABA": "motion", "ZA": "motion", "GA": "other",
    "RV": "bill", "AB": "report", "SAFR": "question", "MAFR": "question", "DAFR": "question",
    "SAAN": "answer", "PET": "motion", "PETAT": "answer", "BE": "consultation",
    "BBG": "consultation", "FE": "consultation", "KULGBL": "law", "LRHF": "report",
    "LRHI": "report", "LRHS": "report", "LRHT": "report", "BRH": "report", "VA": "report",
    "PDK": "report",
}


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def empty_watchlist():
    """Landtag documents are watched by key (atl_store.add_watch_areas)."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, wl, key, title, wl_path=None):
    res = filt.filter_item(tax, wl, title or "", title=title or "")
    return atl_store.add_watch_areas(res, key, wl_path)


def row(land, key, title, doc_type=None, kind=None, number=None, period=None, date=None,
        date_basis=None, by_whom=None, status=None, outcome=None, url=None, detail=None,
        source="landtag"):
    return {"item_key": key, "land": land, "source": source, "period": period,
            "number": number, "doc_type": doc_type, "kind": kind or kind_of(doc_type, title),
            "title": (title or "").strip() or None, "by_whom": by_whom, "date": date,
            "date_basis": date_basis if date else None, "status": status, "outcome": outcome,
            "url": url, "detail": detail}


# -- the parsers (pure; tests/test_at_landtage.py) ------------------------------

def parse_noe_list(page):
    """noe-landtag.gv.at result list -> rows (undated)."""
    out = []
    for block in re.split(r'<div class="result [^"]*" data-document-url=', page or "")[1:]:
        m = re.match(r'"/gegenstaende/([^/"]+)/([^"]+)"', block)
        if not m:
            continue
        gp, slug = m.groups()
        title = text_of((re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S) or [None, ""])[1])
        number = text_of((re.search(r'title="Geschäftszahl">(.*?)</span>\s*</?span',
                                    block, re.S) or [None, ""])[1]).replace("Geschäftszahl: ", "")
        spans = re.findall(r'<span aria-hidden="true"> – </span><span>([^<]+)</span>', block)
        doc_type = spans[0].strip() if spans else None
        short = re.search(r'title="Kürzel: ([^"]+)"', block)
        by = re.search(r"<span>Eingebracht von: </span><span>([^<]+)</span>", block)
        num = slug.split("-")[-1]
        out.append(row("noe", "noe/{0}/{1}".format(gp, num), title,
                       doc_type=doc_type + (" ({0})".format(short.group(1)) if short and doc_type
                                            else ""),
                       kind=kind_of(doc_type, title) if doc_type != "Anfrage und Anfragebeantwortung"
                       else "question",
                       number=number or None, period=gp, by_whom=by.group(1).strip() if by else None,
                       url="{0}/gegenstaende/{1}/{2}".format(NOE, gp, slug),
                       detail="{0}/gegenstaende/{1}/{2}".format(NOE, gp, slug)))
    return out


def parse_noe_detail(page):
    """A Verhandlungsgegenstand's page -> {date, latest, status, by_whom}."""
    steps = re.findall(r'<time datetime="(\d{4}-\d{2}-\d{2})">.*?</time>.*?'
                       r'<span class="h3 my-0">([^<]+)</span>', page or "", re.S)
    status = re.search(r"<strong>Status: </strong><span>([^<]+)</span>", page or "")
    by = re.search(r"<strong>Eingebracht von: </strong>(.*?)</div>", page or "", re.S)
    out = {"status": status.group(1).strip() if status else None,
           "by_whom": text_of(by.group(1)) if by else None}
    if steps:
        out["date"] = min(d for d, _ in steps)
        last = max(steps)
        out["latest"] = "{0} on {1}".format(last[1].strip(), last[0])
    return out


def parse_stmk_rows(page):
    """PALLAST's table (the page or the paging call's XML) -> rows (undated)."""
    out = []
    for m in re.finditer(
            r'<a href="(/pallast-p/pub/document[^"]*?ref=([0-9a-f-]+)[^"]*)"[^>]*>(.*?)</a>'
            r'\s*<br\s*/>\s*Typ:\s*([^<]*)</td><td[^>]*>([^<]*)</td><td[^>]*>(.*?)</td>',
            page or "", re.S):
        _href, ref, title, doc_type, ezoz, klub = m.groups()
        ezoz = ezoz.strip()
        if not re.match(r"^\d+/\d+$", ezoz):
            continue
        doc_type = text_of(doc_type)
        doc_type = re.sub(r"\s*\(§.*\)$", "", doc_type)
        out.append(row("stmk", "stmk/{0}/{1}".format(STMK_GP, ezoz), text_of(title),
                       doc_type=doc_type, number="EZ/OZ " + ezoz, period=STMK_GP,
                       by_whom=text_of(klub) or None,
                       url="{0}/pallast-p/pub/document?ref={1}&inner=false".format(STMK, ref),
                       detail="{0}/pallast-p/pub/document?ref={1}&inner=false".format(STMK, ref)))
    return out


def parse_stmk_detail(page):
    s = page_text(page)
    out = {}
    m = re.search(r"eingebracht am (\d{2}\.\d{2}\.\d{4})", s)
    if m:
        out["date"] = de_date(m.group(1))
    m = re.search(r"Landtagsabgeordnete\(r\): (.*?) Fraktion\(en\):", s)
    if m:
        out["by_whom"] = m.group(1).strip()
    # A Landtagsbeschluss: the sitting's date and the decision with its Klubs.
    m = re.search(r"(Landtagsbeschluss Nr\. \d+) (\d+\. Landtagssitzung)[^0-9]*?"
                  r"(\d{2}\.\d{2}\.\d{4})", s)
    if m:
        out["date"] = de_date(m.group(3))
        out["status"] = "{0}, {1}".format(m.group(1), m.group(2))
        out["basis"] = "decided"
    m = re.search(r"(Der Beschluss wurde [^.]*?(?:angenommen|abgelehnt))\.", s)
    if m:
        out["outcome"] = re.sub(r"\s+\)", ")", m.group(1))
    return out


def parse_ooe_list(page):
    """LIS search results -> rows (undated; the search window bounds them)."""
    out = []
    for m in re.finditer(
            r"form\.nummer\.value='(\d+)';form\.jahr\.value='(\d{4})'.*?"
            r'data-label="Art">([^<]*)</td><td data-label="Gegenstand">(.*?)</td>',
            page or "", re.S):
        nummer, jahr, art, title = m.groups()
        art = art.strip()
        url = "{0}InternetLtgBeilagenAnzeige.jsp?jahr={1}&nummer={2}&gp={3}".format(
            OOE, jahr, nummer, OOE_GP)
        out.append(row("ooe", "ooe/{0}/{1}/{2}".format(OOE_GP, nummer, jahr), text_of(title),
                       doc_type=art, kind=OOE_ART.get(art, "other"),
                       number="Beilage {0}/{1}".format(nummer, jahr), period=OOE_GP,
                       url=url, detail=url))
    return out


def parse_ooe_detail(page):
    s = page_text(page)
    out = {}
    m = re.search(r"Eingang (?:am|in der [^0-9]{0,80}?am) (\d{2}\.\d{2}\.\d{4})", s)
    if m:
        out["date"] = de_date(m.group(1))
    m = re.search(r"Status: (\d+% abgeschlossen)", s)
    if m:
        out["status"] = m.group(1)
    m = re.search(r"\d{2}\.\d{2}\.\d{4} (Antrag (?:angenommen|abgelehnt)[^\d]*?)"
                  r"(?= \d{2}\.\d{2}\.\d{4}| Impressum|$)", s)
    if m:
        out["outcome"] = m.group(1).strip()
    return out


def parse_wien_list(page, land="wien"):
    """INFODAT results -> (rows dated by the sitting, last page number).
    `land` is 'wien' (committees=L) or 'wien-gr' (committees=G, the
    Gemeinderat): the same table, a different key prefix."""
    out = []
    for m in re.finditer(r'<tr><td>([^<]*)</td><td>(\d{2}\.\d{2}\.\d{4})</td><td><a[^>]*'
                         r'href="/infodat/ergdt\?detvid=(\d+)"[^>]*>([^<]*)</a></td><td>(.*?)</td>',
                         page or "", re.S):
        doc_type, date, detvid, akt, title = m.groups()
        # The Aktenzahl as printed ('PGL-1310313-2026-KFP/GAT'), else the Id.
        out.append(row(land, land + "/" + detvid, text_of(title), doc_type=doc_type.strip(),
                       number=akt.strip() or "Id({0})".format(detvid), date=de_date(date),
                       date_basis="sitting",
                       url="{0}/infodat/ergdt?detvid={1}".format(WIEN, detvid)))
    last = re.search(r'aria-label="Letzte Seite"[^>]*href="[^"]*page=(\d+)"', page or "")
    return out, int(last.group(1)) if last else 1


def parse_sbg_list(page):
    """LPI results -> rows dated by the Meldung (the main hit of each row only;
    the 'Referenz Meldung' beneath an answer is the question, read on its own)."""
    out = []
    body = (page or "").split('id="mySearchTable"', 1)[-1]
    for tr in re.split(r"<tr>", body)[1:]:
        main = tr.split("Referenz Meldung", 1)[0]
        date = re.search(r"vom (\d{2}\.\d{2}\.\d{4})", main)
        title = re.search(r'<p class="h6">(.*?)</p>', main, re.S)
        beilage = re.search(r"Beilagennummer: ([^<]+)</p>", main)
        view = re.search(r'href="viewExtern\?id=(\d+)"', main)
        pdf = re.search(r'href="([^"]*/(\d+)Gesetzgebungsperiode/(\d+)Session/[^"]+\.pdf)"', main)
        if not (title and (beilage or view)):
            continue
        title = text_of(title.group(1))
        nr = beilage.group(1).strip() if beilage else None
        if pdf and nr:
            key = "sbg/{0}/{1}/{2}".format(pdf.group(2), pdf.group(3), nr)
        else:
            key = "sbg/id/{0}".format(view.group(1))
        doc_type = {"ANF": "Anfrage", "BEA": "Anfragebeantwortung"}.get(
            (nr or "").rsplit("-", 1)[-1] if "-" in (nr or "") else "", None)
        out.append(row("sbg", key, title, doc_type=doc_type, kind=kind_of(doc_type, title),
                       number="Nr. {0} der Beilagen".format(nr) if nr else None,
                       period=pdf.group(2) if pdf else SBG_GP,
                       date=de_date(date.group(1)) if date else None, date_basis="reported",
                       url=(SBG + "viewExtern?id=" + view.group(1)) if view else
                       (pdf.group(1) if pdf else None)))
    return out


def parse_vbg_top(xml):
    """The view's top level -> {category text: position}."""
    return {html.unescape(t): p for p, t in re.findall(
        r'<viewentry position="(\d+)"[^>]*>\s*<entrydata[^>]*category="true"[^>]*>\s*'
        r'<text>([^<]*)</text>', xml or "")}


def parse_vbg_view(xml):
    """One Landtagsperiode, expanded -> rows (undated; year and type from the
    categories above each document)."""
    out, year, doc_type = [], None, None
    for m in re.finditer(r"<viewentry ([^>]*)>(.*?)</viewentry>", xml or "", re.S):
        attrs, body = m.groups()
        cat = re.search(r'name="(fd_YearNU|fd_TypeOfDocumentTX)" category="true">\s*'
                        r"<(?:number|text)>([^<]*)<", body)
        if cat:
            if cat.group(1) == "fd_YearNU":
                year, doc_type = cat.group(2), None
            else:
                doc_type = html.unescape(cat.group(2))
            continue
        unid = re.search(r'unid="([0-9A-F]{32})"', attrs)
        title = re.search(r'name="fd_TitleTX">\s*<text>([^<]*)</text>', body)
        if not (unid and title):
            continue
        out.append(row("vbg", "vbg/" + unid.group(1).lower(), html.unescape(title.group(1)),
                       doc_type=doc_type, period="32", number=None,
                       url="{0}{1}/{2}?OpenDocument".format(VBG, VBG_VIEW.rsplit("/", 1)[-1],
                                                            unid.group(1).lower()),
                       detail="{0}{1}/{2}?OpenDocument".format(VBG, VBG_VIEW.rsplit("/", 1)[-1],
                                                               unid.group(1).lower())))
        out[-1]["year"] = year
    return out


def parse_vbg_detail(page):
    s = page_text(page)
    out = {}
    m = re.search(r"Eingelangt in der Landtagsdirektion (\d{1,2}/\d{1,2}/\d{4})", s)
    if m:
        out["date"] = us_date(m.group(1))
    m = re.search(r"Behandelt im Landtag (\d{1,2}/\d{1,2}/\d{4})", s)
    if m:
        out["status"] = "dealt with in the Landtag on {0}".format(us_date(m.group(1)))
    m = re.search(r"Status: ([^:]*?) Thema:", s)
    if m and m.group(1).strip(" -"):
        out["status"] = m.group(1).strip()
    return out


def parse_bgld_list(page):
    """The Vorlagen list -> rows (undated)."""
    out = []
    for m in re.finditer(
            r'viewColumn1:_internalViewText"[^>]*>([^<]+)</span>.*?'
            r'viewColumn2:_internalViewText"[^>]*>([^<]*)</span>.*?'
            r'viewColumn3:_internalViewText"[^>]*>(.*?)</span>', page or "", re.S):
        zahl, doc_type, title = (html.unescape(x).strip() for x in m.groups())
        if not re.match(r"^\d+-\d+$", zahl):
            continue
        out.append(row("bgld", "bgld/{0}/{1}".format(BGLD_GP, zahl), text_of(title),
                       doc_type=doc_type, number="Zahl " + zahl, period=BGLD_GP,
                       url=BGLD))
    return out


def parse_ris(reply):
    """RIS Landesrecht (LgblAuth) JSON -> rows, one per Landesgesetzblatt."""
    res = ((reply or {}).get("OgdSearchResult") or {}).get("OgdDocumentResults") or {}
    docs = res.get("OgdDocumentReference") or []
    if isinstance(docs, dict):
        docs = [docs]
    out = []
    for d in docs:
        meta = ((d.get("Data") or {}).get("Metadaten") or {})
        tech, lr = meta.get("Technisch") or {}, meta.get("Landesrecht") or {}
        auth = lr.get("LgblAuth") or {}
        land = RIS_LAND.get(lr.get("Bundesland"), (lr.get("Bundesland") or "?").lower())
        title = (lr.get("Kurztitel") or "").strip()
        long_title = (lr.get("Titel") or "").strip()
        r = row(land, "ris/" + tech.get("ID", ""), long_title or title,
                doc_type=auth.get("Typ") or "Landesgesetzblatt",
                kind="law" if (auth.get("Typ") or "") == "Landesgesetz" else "other",
                number=auth.get("Lgblnummer"), period=auth.get("Gesetzgebungsperiode"),
                date=lr.get("Kundmachungsdatum"), date_basis="published",
                outcome=("Beschlossen am {0}".format(auth["BeschlussDatum"])
                         if auth.get("BeschlussDatum") else None),
                url=auth.get("EuropeanLegislationIdentifier") or
                (meta.get("Allgemein") or {}).get("DokumentUrl"), source="ris")
        if tech.get("ID"):
            out.append(r)
    return out


# -- the readers (network) --------------------------------------------------------

def read_noe(ctx, st):
    rows, known = [], st["known"]
    first = not known
    for page in range(1, 3 if first else 9):
        got = parse_noe_list(ctx.text("{0}/gegenstaende/{1}/suche?page={2}".format(NOE, NOE_GP, page),
                                      "noe-list-{0}".format(page), archive=True))
        if not got:
            if page == 1:
                ctx.gap("noe: the Verhandlungsgegenstände list returned no rows")
            break
        rows += got
        if not first and all(r["item_key"] in known for r in got):
            break
        if ctx.stop():
            break
    return rows


def _pallast_view_state(page):
    vs = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', page or "")
    act = re.search(r'<form id="contentForm"[^>]*action="([^"]+)"', page or "")
    return (vs.group(1), html.unescape(act.group(1))) if vs and act else (None, None)


def read_stmk(ctx, st):
    known = st["known"]
    first = ctx.text(STMK_LIST, "stmk-list", archive=True)
    rows = parse_stmk_rows(first)
    vs, action = _pallast_view_state(first)
    if not rows or not vs:
        ctx.gap("stmk: PALLAST's document list has no rows or no ViewState")
        return rows
    for start in (0, 100, 200):
        if ctx.stop():
            break
        reply = ctx.post_form(STMK + action, {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "contentForm:documentsTable",
            "javax.faces.partial.execute": "contentForm:documentsTable",
            "javax.faces.partial.render": "contentForm:documentsTable",
            "contentForm:documentsTable": "contentForm:documentsTable",
            "contentForm:documentsTable_pagination": "true",
            "contentForm:documentsTable_first": str(start),
            "contentForm:documentsTable_rows": "100",
            "contentForm:documentsTable_encodeFeature": "true",
            "contentForm": "contentForm", "javax.faces.ViewState": vs},
            "stmk-page-{0}".format(start))
        got = parse_stmk_rows(reply)
        if not got:
            ctx.gap("stmk: PALLAST's paging call returned no rows (first={0})".format(start))
            break
        rows += got
        if not known or all(r["item_key"] in known for r in got):
            break
    return rows


def read_ooe(ctx, st):
    start = ctx.text(OOE + "Start.jsp", "ooe-start")
    sid = re.search(r"SessionID=(SID-[0-9A-F-]+)", start or "")
    if not sid:
        ctx.gap("ooe: no SessionID on the LIS start page")
        return []
    since = datetime.date.fromisoformat(st["since"])
    q = {"SessionID": sid.group(1), "such_gesetzgebungsperiode": OOE_GP,
         "such_eingangsdatumVon": since.strftime("%d.%m.%Y"),
         "such_eingangsdatumBis": datetime.date.fromisoformat(st["until"]).strftime("%d.%m.%Y"),
         "rowCount": "500", "cmdSucheStarten": "Suche starten"}
    page = ctx.text(OOE + "InternetLtgBeilagenSuche.jsp?" + urllib.parse.urlencode(q),
                    "ooe-search", archive=True)
    rows = parse_ooe_list(page)
    if page and "SessionLost" in page:
        ctx.gap("ooe: the LIS session was lost before the search")
    if len(rows) >= 500:
        ctx.gap("ooe: 500 rows or more in the window; the rest are not read this run")
    return rows


def read_wien(ctx, st, land="wien"):
    rows, page_no, last = [], 1, 1
    cap = WIEN_MAX_PAGES[land]
    until = (datetime.date.fromisoformat(st["until"]) + datetime.timedelta(days=60)).isoformat()
    while page_no <= min(last, cap):
        q = {"committees": WIEN_COMMITTEE[land], "sessionDayFrom": st["since"],
             "sessionDayTo": until, "page": page_no}
        got, last = parse_wien_list(ctx.text(
            WIEN + "/infodat/suchergebnisse?" + urllib.parse.urlencode(q),
            "{0}-list-{1}".format(land, page_no), archive=True), land)
        rows += got
        if not got or ctx.stop():
            break
        page_no += 1
    if last > cap:
        ctx.gap("{0}: {1} pages in the window; the first {2} were read".format(land, last, cap))
    return rows


def read_wien_gr(ctx, st):
    """Vienna's Gemeinderat: the Landtag's reader with committees=G."""
    return read_wien(ctx, st, "wien-gr")


def read_sbg(ctx, st):
    q = {"periode": SBG_GP,
         "datumVon": datetime.date.fromisoformat(st["since"]).strftime("%d.%m.%Y"),
         "datumBis": datetime.date.fromisoformat(st["until"]).strftime("%d.%m.%Y"),
         "search": ""}
    return parse_sbg_list(ctx.text(SBG + "searchExtern?" + urllib.parse.urlencode(q),
                                   "sbg-search", archive=True))


def read_vbg(ctx, st):
    top = parse_vbg_top(ctx.text(VBG_VIEW + "?ReadViewEntries&CollapseView&Count=10",
                                 "vbg-top", archive=True))
    cat = next((t for t in top if t.startswith(VBG_PERIOD)), None)
    if not cat:
        ctx.gap("vbg: no '{0}' category in the materials view".format(VBG_PERIOD))
        return []
    url = (VBG_VIEW + "?ReadViewEntries&RestrictToCategory=" + urllib.parse.quote(cat)
           + "&ExpandView&Count=2000")
    return parse_vbg_view(ctx.text(url, "vbg-period", archive=True))


def read_bgld(ctx, st):
    rows = parse_bgld_list(ctx.text(BGLD, "bgld-list", archive=True))
    known = st["known"]
    if known and rows and not any(r["item_key"] in known for r in rows):
        ctx.gap("bgld: every Vorlage on the first page is new; older new ones are not read")
    return rows


def read_ris(ctx, st):
    raw = ctx.text(RIS, "ris-landesrecht", archive=True)
    if raw is None:
        return []
    try:
        return parse_ris(json.loads(raw))
    except ValueError:
        ctx.gap("ris: the reply was not JSON")
        return []


READERS = {"wien": read_wien, "wien-gr": read_wien_gr, "noe": read_noe, "ooe": read_ooe, "stmk": read_stmk,
           "sbg": read_sbg, "vbg": read_vbg, "bgld": read_bgld, "ris": read_ris}
DETAILS = {"noe": parse_noe_detail, "stmk": parse_stmk_detail, "ooe": parse_ooe_detail,
           "vbg": parse_vbg_detail}


# -- the store ---------------------------------------------------------------------

def known_keys(conn, land):
    prefix = ("ris/%" if land == "ris" else land + "/%")
    return {k for (k,) in conn.execute("SELECT item_key FROM atl_items WHERE item_key LIKE ?",
                                       (prefix,))}


def store_rows(conn, rows, tax, wl, today, first_read, wl_path=None):
    """Upsert; returns the number on our ground. A row without a date seen on
    the Land's first read is a baseline row (never shown as new); for the
    bodies in atl_store.BASELINE_ALL (Vienna's Gemeinderat) every row of the
    first read is, dated or not. An upsert never changes `baseline`."""
    ours = 0
    d = atl_store.dumps
    for r in rows:
        res = classify(tax, wl, r["item_key"], r["title"], wl_path)
        ours += on_our_ground(res.issue_areas) or bool(res.watchlist_hits)
        conn.execute(
            "INSERT INTO atl_items (item_key, land, source, period, number, doc_type, kind, "
            "title, by_whom, date, date_basis, status, outcome, url, baseline, areas, "
            "matched_terms, tier, first_seen, last_seen) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(item_key) DO UPDATE SET "
            "land=excluded.land, source=excluded.source, period=excluded.period, "
            "number=COALESCE(excluded.number, atl_items.number), "
            "doc_type=COALESCE(excluded.doc_type, atl_items.doc_type), kind=excluded.kind, "
            "title=COALESCE(excluded.title, atl_items.title), "
            "by_whom=COALESCE(excluded.by_whom, atl_items.by_whom), "
            "date=COALESCE(excluded.date, atl_items.date), "
            "date_basis=COALESCE(excluded.date_basis, atl_items.date_basis), "
            "status=COALESCE(excluded.status, atl_items.status), "
            "outcome=COALESCE(excluded.outcome, atl_items.outcome), "
            "url=COALESCE(excluded.url, atl_items.url), areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, tier=excluded.tier, "
            "last_seen=excluded.last_seen",
            (r["item_key"], r["land"], r["source"], r["period"], r["number"], r["doc_type"],
             r["kind"], r["title"], r["by_whom"], r["date"], r["date_basis"], r["status"],
             r["outcome"], r["url"],
             1 if first_read and (not r["date"] or r["land"] in atl_store.BASELINE_ALL) else 0,
             d(res.issue_areas), d((res.matched_terms or []) + (res.watchlist_hits or [])),
             res.tier, today, today))
    return ours


def due_details(conn, land, rows, today):
    """Rows on our ground whose own page is due: never read, or open and
    listed lately and last read a week ago or more."""
    detail_url = {r["item_key"]: r.get("detail") for r in rows if r.get("detail")}
    if not detail_url:
        return []
    week = (datetime.date.fromisoformat(today) - datetime.timedelta(days=DETAIL_REFRESH_DAYS)).isoformat()
    out = []
    for key, areas, read, kind, status in conn.execute(
            "SELECT item_key, areas, detail_read, kind, status FROM atl_items WHERE land=? "
            "AND source='landtag'", (land,)):
        if key not in detail_url:
            continue
        if not (on_our_ground(json.loads(areas or "[]")) or key in atl_store.watchlist()):
            continue
        # Only bills and motions move; a question, an answer, a report or a
        # decision is read once. An item the source calls done is not re-read.
        closed = kind not in ("bill", "motion") or bool(re.search(
            r"abgeschlossen|erledigt|100%|Landtagsbeschluss|dealt with", status or "", re.I))
        if read is None or (not closed and read <= week):
            out.append((key, detail_url[key]))
    return out[:MAX_DETAILS]


def read_details(ctx, conn, land, rows, today):
    n = 0
    for key, url in due_details(conn, land, rows, today):
        if ctx.stop():
            break
        page = ctx.text(url, "{0}-detail-{1}".format(land, key.rsplit("/", 1)[-1][:40]))
        if page is None:
            continue
        got = DETAILS[land](page)
        conn.execute(
            "UPDATE atl_items SET date=COALESCE(?, date), "
            "date_basis=CASE WHEN ? IS NOT NULL THEN ? ELSE date_basis END, "
            "status=COALESCE(?, status), outcome=COALESCE(?, outcome), "
            "by_whom=COALESCE(?, by_whom), detail_read=? WHERE item_key=?",
            (got.get("date"), got.get("date"), got.get("basis") or "introduced",
             got.get("latest") or got.get("status"),
             got.get("outcome"), got.get("by_whom"), today, key))
        n += 1
    return n


def note_read(conn, land, today, seen, ours, gaps):
    conn.execute(
        "INSERT INTO atl_reads (land, last_read, last_ok, rows_seen, rows_ours, note) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(land) DO UPDATE SET last_read=excluded.last_read, "
        "last_ok=COALESCE(excluded.last_ok, atl_reads.last_ok), rows_seen=excluded.rows_seen, "
        "rows_ours=excluded.rows_ours, note=excluded.note",
        (land, today, None if gaps else today, seen, ours, gaps[-1][:300] if gaps else None))


def note_blocked(conn, today):
    for land, why in sorted(atl_store.BLOCKED.items()):
        conn.execute("INSERT INTO atl_reads (land, last_read, note) VALUES (?,?,?) "
                     "ON CONFLICT(land) DO UPDATE SET last_read=excluded.last_read, "
                     "note=excluded.note", (land, today, "not read: " + why))


def run_land(conn, client, land, today, since, until, tax, wl, budget=None, log=print,
             wl_path=None):
    """Read one Land (or 'ris'): list, store, own pages. Returns (seen, ours, gaps)."""
    ctx = Context(conn, client, land, feed=FEED, budget=budget, log=log)
    known = known_keys(conn, land)
    st = {"since": since, "until": until, "known": known}
    rows = READERS[land](ctx, st)
    ours = store_rows(conn, rows, tax, wl, today, first_read=not known, wl_path=wl_path)
    details = read_details(ctx, conn, land, rows, today) if land in DETAILS else 0
    for g in ctx.gaps:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                     (today, FEED, "{0}: {1}".format(land, g)[:500]))
    note_read(conn, land, today, len(rows), ours, ctx.gaps)
    conn.commit()
    log("at-landtage: {0}: {1} row(s), {2} new, {3} on our ground, {4} page(s) of their "
        "own read; {5} gap(s)".format(land, len(rows),
                                      sum(1 for r in rows if r["item_key"] not in known), ours,
                                      details, len(ctx.gaps)))
    return len(rows), ours, ctx.gaps


def reclassify(conn, tax=None, log=print, wl_path=None):
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY, country=TAXONOMY_COUNTRY)
    wl = empty_watchlist()
    changed = 0
    for key, title, areas in conn.execute(
            "SELECT item_key, title, areas FROM atl_items").fetchall():
        res = classify(tax, wl, key, title, wl_path)
        new = atl_store.dumps(res.issue_areas)
        if new != (areas or "[]"):
            changed += 1
        conn.execute("UPDATE atl_items SET areas=?, matched_terms=?, tier=? WHERE item_key=?",
                     (new, atl_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    conn.commit()
    log("at-landtage: reclassified; {0} row(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    for land, n, ours in conn.execute(
            "SELECT land, COUNT(*), SUM(CASE WHEN areas NOT IN ('[]', '[11]') THEN 1 ELSE 0 END) "
            "FROM atl_items GROUP BY land ORDER BY land"):
        log("  store: {0}: {1} row(s), {2} on our ground".format(land, n, ours or 0))


def make_client(raw_dir=None):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return HttpClient(raw_dir=raw_dir or os.path.join(ROOT, "data", "raw"), opener=opener)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", help="raw archive (default data/raw)")
    ap.add_argument("--land", action="append", choices=atl_store.READ,
                    help="read only these Länder (repeatable; 'wien-gr' is Vienna's "
                         "Gemeinderat); default all")
    ap.add_argument("--ris", action="store_true",
                    help="also ask RIS Landesrecht (robots.txt is asked first and honoured)")
    ap.add_argument("--since", help="ISO date: the dated searches start here "
                                    "(default {0} days ago)".format(LOOKBACK_DAYS))
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive every stored row's areas, offline")
    ap.add_argument("--budget-seconds", type=float, default=900.0)
    args = ap.parse_args(argv)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        return 0
    today = datetime.date.today().isoformat()
    since = args.since or (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    tax = filt.load_taxonomy(TAXONOMY, country=TAXONOMY_COUNTRY)
    wl = empty_watchlist()
    client = make_client(args.raw_dir)
    budget = drain.Budget(args.budget_seconds)
    lands = list(args.land or atl_store.READ) + (["ris"] if args.ris else [])
    stored, gaps = 0, 0
    note_blocked(conn, today)
    for land in lands:
        if budget.exhausted():
            print(budget.disclose("Länder", stored))
            gaps += 1
            break
        try:
            seen, _ours, g = run_land(conn, client, land, today, since, today, tax, wl,
                                      budget=budget)
        except Exception as exc:                    # one Land's failure never costs the others
            conn.rollback()
            print("  [gap] {0}: {1}: {2}".format(land, type(exc).__name__, exc))
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                         (today, FEED, "{0}: {1}".format(land, exc)[:500]))
            note_read(conn, land, today, 0, 0, [str(exc)])
            conn.commit()
            gaps += 1
            continue
        stored += seen
        gaps += len(g)
    summary(conn)
    conn.close()
    if not stored:
        return 1
    return GAPS_EXIT if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
