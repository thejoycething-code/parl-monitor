"""Belgium: the federal portal's news and public consultations (belgium.be)
and the FPS Health's news (health.belgium.be).

Built 16 October 2026 (Chris: "UK parity for government consultations and
publications"); docs/belgium-scope.md, "Government consultations and
publications (gov_docs, 16 October 2026)", has every route tried.

BELGIUM.BE (code 'portal'): www.belgium.be/fr/actualites/overview, the
federal portal's news, newest first, ten a page. Its federal public
consultations ("Donnez votre avis sur ...", "Consultation publique sur ...",
from the FPS Health and Environment, the North Sea, ONDRAF) are read for
their period: the item page's description says "Du 17 août au 15 octobre
2026 inclus, une consultation publique est organisée par le SPF ...", which
gives the closing date and the body. A consultation's results item is a
'consultation_outcome'; other news a 'publication'. robots.txt (Drupal
defaults) disallows /search/, /admin/ and the like, not /fr/actualites/.

FPS HEALTH (code 'health'): www.health.belgium.be/fr/news?page=N, the FPS
Public Health, Food Chain Safety and Environment's news (twelve a page):
health law, end of life, reproductive health and drug policy announcements
are its business. A 'press_release' each; the precision gate keeps tier 1
only. robots.txt disallows "/*?find=" and the search pages; /fr/rss.xml
redirects to a ?find= URL, so the listing is read instead.

Not read, and why (docs/belgium-scope.md): the Moniteur belge / Belgisch
Staatsblad (www.ejustice.just.fgov.be) disallows /cgi/, /eli/, /mopdf/,
/sum_a/ and every other path its pages and PDFs live under, and no open-data
copy was found (data.gov.be has none); news.belgium.be (the federal press
releases, the Council of Ministers' decisions), www.premier.be and
www.belgiquelex.be answer 403 to our user agent, robots.txt included;
justice.belgium.be/fr/rss.xml last moved in February 2018.

Titles are French; the edition adapter classifies them with taxonomy-fr and
taxonomy-nl (src/editions/be.py).
"""

from __future__ import annotations

import html as htmlmod
import re

from src import gov_docs as G

CC = "be"

PORTAL = "https://www.belgium.be"
PORTAL_LIST = PORTAL + "/fr/actualites/overview"
PORTAL_MAX_PAGES = 6
PORTAL_BODY = "Portail fédéral belgium.be"
ITEM_PAGES = 40

HEALTH = "https://www.health.belgium.be"
HEALTH_LIST = HEALTH + "/fr/news"
HEALTH_MAX_PAGES = 8
HEALTH_BODY = "SPF Santé publique, Sécurité de la chaîne alimentaire et Environnement"

JUSTICE_RSS = "https://justice.belgium.be/fr/news/rss"
JUSTICE_BODY = "SPF Justice"

IEFH = "https://igvm-iefh.belgium.be"
IEFH_LIST = IEFH + "/fr/actualite"
IEFH_BODY = "Institut pour l'égalité des femmes et des hommes"

_CONSULT = re.compile(r"(?i)\bdonnez votre avis\b|\bconsultation publique\b")
_OUTCOME = re.compile(r"(?i)\br[ée]sultats?\b")


def _page_url(base, n):
    return base if n == 0 else "{0}?page={1}".format(base, n)


# --- belgium.be ----------------------------------------------------------------------

_PORTAL_ROW = re.compile(
    r'<time class="node__date" datetime="([^"]+)"[^>]*>.*?<a href="(/fr/actualites/[^"]+)"[^>]*>(.*?)</a>',
    re.S)


def portal_kind(title):
    if _CONSULT.search(title):
        return "consultation_outcome" if _OUTCOME.search(title) else "consultation"
    return "publication"


def parse_portal(page):
    """[entry] from one page of the belgium.be news overview (no closing dates yet)."""
    out, seen = [], set()
    for when, href, title in _PORTAL_ROW.findall(page):
        if href in seen:
            continue
        seen.add(href)
        title = G.text(title)
        slug = href.rstrip("/").rsplit("/", 1)[-1]
        out.append(G.entry("portal", slug, title, portal_kind(title), body=PORTAL_BODY,
                           published=when, url=PORTAL + href))
    return out


_PERIOD = re.compile(
    r"(?i)\bdu\s+(\d{1,2})(?:er)?\s+([^\W\d_]+)(?:\s+(\d{4}))?\s+au\s+(\d{1,2})(?:er)?\s+([^\W\d_]+)\s+(\d{4})")
_BY = re.compile(r"(?i)organis[ée]e?\s+par\s+(?:le|la|l['’])\s*(.+?)(?:\s+sur\s+|\s+concernant\s+|[.;])")


def parse_portal_item(page):
    """(opened, closes, body, description) from a belgium.be news item page."""
    m = re.search(r'<meta name="description" content="([^"]*)"', page)
    desc = G.one_line(htmlmod.unescape(m.group(1))) if m else ""
    if not desc:
        art = page.split('class="page__title"', 1)[-1]
        desc = G.text(re.sub(r"(?s)<(script|style).*?</\1>", "", art))[:1500]
    opened = closes = body = None
    p = _PERIOD.search(desc)
    if p:
        d1, m1, y1, d2, m2, y2 = p.groups()
        closes = G.long_date("{0} {1} {2}".format(d2, m2, y2))
        opened = G.long_date("{0} {1} {2}".format(d1, m1, y1 or y2))
    b = _BY.search(desc)
    if b:
        body = G.one_line(b.group(1))[:160]
    return opened, closes, body, desc


def fetch_portal(client, today, log):
    start = G.window_start(today)
    out, gaps, reads = [], [], 0
    for n in range(PORTAL_MAX_PAGES):
        page = client.get_text(_page_url(PORTAL_LIST, n), "be-govdocs-portal", "list-{0}".format(n),
                               archive=n == 0)
        got = parse_portal(page)
        fresh = [e for e in got if (e["published"] or "") >= start]
        out += got
        if len(fresh) < len(got) or not got:
            break
    for e in out:
        # a federal consultation runs about two months: one announced before the
        # window has closed
        if e["doc_type"] != "consultation" or (e["published"] or "") < start:
            continue
        if reads >= ITEM_PAGES:
            gaps.append("item-page budget ({0}) spent; some closing dates unread".format(ITEM_PAGES))
            break
        reads += 1
        try:
            page = client.get_text(e["url"], "be-govdocs-portal", e["doc_id"].split(":", 1)[1][:80],
                                   archive=False)
        except Exception as exc:                        # noqa: BLE001
            gaps.append("{0}: {1}".format(e["url"], str(exc)[:120]))
            continue
        opened, closes, body, desc = parse_portal_item(page)
        e["closing_date"] = closes
        e["summary"] = desc[:G.SUMMARY_CAP] or None
        if body:
            e["body"] = body
        if opened:
            e["status"] = "consultation du {0} au {1}".format(opened, closes)
    return G.fetched(out, note="{0} news items listed, {1} item page(s) read".format(len(out), reads),
                     gaps=gaps)


# --- FPS Health ------------------------------------------------------------------------

def parse_health(page):
    """[entry] from one page of the FPS Health news listing."""
    out = []
    for card in page.split('<section class="node type__news')[1:]:
        href = re.search(r'<a href="(/fr/[^"]+)"', card)
        title = re.search(r"<h3[^>]*>(.*?)</h3>", card, re.S)
        when = re.search(r'<time[^>]*datetime="([^"]+)"', card)
        if not href or not title:
            continue
        props = [G.text(x) for x in re.findall(r"<span>(.*?)</span>",
                 card.split('search-result__props', 1)[-1].split("</div>", 1)[0], re.S)]
        slug = href.group(1).rstrip("/").rsplit("/", 1)[-1]
        out.append(G.entry("health", slug, G.text(title.group(1)), "press_release", body=HEALTH_BODY,
                           published=when.group(1) if when else None, url=HEALTH + href.group(1),
                           status=" / ".join(p for p in props if p) or None))
    return out


def fetch_health(client, today, log):
    start = G.window_start(today)
    out, gaps = [], []
    for n in range(HEALTH_MAX_PAGES):
        page = client.get_text(_page_url(HEALTH_LIST, n), "be-govdocs-health", "list-{0}".format(n),
                               archive=n == 0)
        got = parse_health(page)
        out += got
        if not got or any((e["published"] or "") < start for e in got):
            break
    else:
        gaps.append("stopped after {0} pages before reaching {1}".format(HEALTH_MAX_PAGES, start))
    return G.fetched(out, note="{0} news items listed".format(len(out)), gaps=gaps)


# --- FPS Justice (RSS) ------------------------------------------------------------------

def parse_justice_rss(xml_text):
    """[entry] from justice.belgium.be/fr/news/rss (dates are French words)."""
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml_text, re.S):
        title = re.search(r"<title>(.*?)</title>", item, re.S)
        link = re.search(r"<link>(.*?)</link>", item, re.S)
        if not title or not link:
            continue
        link = G.one_line(link.group(1)).replace("http://", "https://", 1)
        when = re.search(r'datetime="([^"]+)"', htmlmod.unescape(item))
        pub = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)
        published = G.iso(when.group(1)) if when else G.long_date(pub.group(1) if pub else "")
        slug = link.rstrip("/").rsplit("/", 1)[-1][:120]
        out.append(G.entry("justice", slug, G.text(title.group(1)), "press_release", body=JUSTICE_BODY,
                           published=published, url=link))
    return out


def fetch_justice(client, today, log):
    return G.fetched(parse_justice_rss(client.get_text(JUSTICE_RSS, "be-govdocs-justice", "rss")))


# --- Institute for the Equality of Women and Men ------------------------------------------

def parse_iefh(page):
    """[entry] from the IEFH news page (press releases and news, newest first)."""
    out, seen = [], set()
    for card in page.split('<article class="node node--type-')[1:]:
        card = card.split("</article>", 1)[0]
        kind = re.match(r"([\w-]+)", card)
        a = re.search(r'<a href="(/fr/[^"]+)"[^>]*>(.*?)</a>', card, re.S)
        when = re.search(r'<time class="node__date" datetime="([^"]+)"', card)
        if not a or not when or a.group(1) in seen:
            continue
        seen.add(a.group(1))
        press = kind and kind.group(1) == "press-release"
        slug = a.group(1).rstrip("/").rsplit("/", 1)[-1][:120]
        out.append(G.entry("iefh", slug, G.text(a.group(2)), "press_release" if press else "publication",
                           body=IEFH_BODY, published=when.group(1), url=IEFH + a.group(1),
                           status="Communiqué de presse" if press else "Actualité"))
    return out


def fetch_iefh(client, today, log):
    return G.fetched(parse_iefh(client.get_text(IEFH_LIST, "be-govdocs-iefh", "list")))


SOURCES = (
    G.Source(code="portal", name="belgium.be (federal news and public consultations)",
             fetch=fetch_portal, url=PORTAL_LIST),
    G.Source(code="health", name="SPF Santé publique (news)", fetch=fetch_health, url=HEALTH_LIST),
    G.Source(code="justice", name="SPF Justice (news, RSS)", fetch=fetch_justice, url=JUSTICE_RSS),
    G.Source(code="iefh", name="Institut pour l'égalité des femmes et des hommes (news)",
             fetch=fetch_iefh, url=IEFH_LIST),
)
