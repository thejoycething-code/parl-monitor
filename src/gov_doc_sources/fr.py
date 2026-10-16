"""France: the Journal officiel (DILA open data), the environment ministry's
public consultations, and the social affairs ministries' news feed.

Built 16 October 2026 (Chris: "UK parity for government consultations and
publications"); docs/france-scope.md, "Government consultations and
publications (gov_docs, 16 October 2026)", has the routes tried.

JORF (code 'jorf'): DILA's documented open data, the JORF increments on
echanges.dila.gouv.fr/OPENDATA/JORF/ (Licence Ouverte; robots.txt answers
404, so no rules). Each night's small increment (about 60 to 220 KB, written
around 00:30) carries that day's Journal officiel; its 'conteneur' XML is the
sommaire: every text's id, title, section and ministry. The large evening
increments (2 to 6 MB) re-deliver consolidated older texts and are skipped
by size. Only the sommaire is read, from memory (nothing is extracted to
disk). Kept: the LOIS section ('law'), the 'Textes généraux' of 'Décrets,
arrêtés, circulaires' and the Présidence de la République (ordonnances,
décrets and arrêtés: 'regulation'; an ordonnance has the force of law but is
made by the government, so it is filed as a regulation), and the opinions of
the CNCDH and the CESE ('publication'). Nominations, collective agreements,
competition notices and the independent authorities' decisions are left out.
The reader asks for the increments of the last JORF_DAYS days: the weekly
job keeps the table current, and a first run backfills three weeks.

The PISTE Legifrance API is documented but needs an account and an OAuth
key (not signed up for, by rule); www.legifrance.gouv.fr answers 403 to our
user agent, robots.txt included.

CONSULTATIONS (code 'dd'): www.consultations-publiques.developpement-
durable.gouv.fr, the environment ministry's statutory consultations (Code de
l'environnement L. 123-19-1). The paged listing (11 a page, newest first)
prints each consultation's opening and closing dates ("Consultation du
16/10/2026 au 06/11/2026"), so no item page is read. A draft décret or arrêté
is a 'regulation_draft', a draft ordonnance or law a 'bill_draft', anything
else a 'consultation'. robots.txt: "Disallow: /ecrire/", Crawl-delay 1.

SOCIAL AFFAIRS (code 'solidarites'): solidarites.gouv.fr/rss.xml, the
official RSS of the ministries for solidarity, families, children and
disability (50 items). A 'press_release' each, except a "consultation
citoyenne" ('consultation', no closing date published in the feed). The
precision gate keeps only tier 1 press releases.

Not read, and why (docs/france-scope.md): vie-publique.fr answers a
JavaScript and cookie challenge to every URL including robots.txt;
info.gouv.fr, education.gouv.fr and www.legifrance.gouv.fr answer 403;
sante.gouv.fr serves a bot-check page (F5) in place of robots.txt;
justice.gouv.fr was in maintenance.
"""

from __future__ import annotations

import io
import re
import tarfile
import xml.etree.ElementTree as ET

from src import gov_docs as G

CC = "fr"

DILA = "https://echanges.dila.gouv.fr/OPENDATA/JORF/"
JORF_DAYS = 21
JORF_MAX_BYTES = 1500 * 1024        # the day-edition increments; larger ones are re-deliveries
LEGIFRANCE = "https://www.legifrance.gouv.fr/jorf/id/"

DD = "https://www.consultations-publiques.developpement-durable.gouv.fr/"
DD_LIST = DD + "spip.php?page=liste-consultations&lang=fr"
DD_PAGE = 11
DD_MAX_PAGES = 25
DD_BODY = "Ministère chargé de la transition écologique"

SOL_RSS = "https://solidarites.gouv.fr/rss.xml"
SOL_BODY = "Ministères chargés des solidarités et des familles"


# --- JORF ---------------------------------------------------------------------------

_INDEX_ROW = re.compile(r'href="(JORF_(\d{8})-(\d{6})\.tar\.gz)".*?\s(\d+(?:\.\d+)?)([KMG]?)\s*$', re.M)


def _size(num, unit):
    return float(num) * {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}[unit]


def parse_index(page, today, days=JORF_DAYS, max_bytes=JORF_MAX_BYTES):
    """[(file name, ISO date)] of the day-edition increments in the last `days` days."""
    start = G.window_start(today, days)
    out = []
    for name, day, _time, num, unit in _INDEX_ROW.findall(page):
        iso = "{0}-{1}-{2}".format(day[:4], day[4:6], day[6:])
        if iso < start or _size(num, unit) > max_bytes:
            continue
        out.append((name, iso))
    return sorted(set(out))


KEEP_SECTIONS = {
    "lois": "law",
    "présidence de la république": "regulation",
    "textes généraux": "regulation",
    "commission nationale consultative des droits de l'homme": "publication",
    "conseil économique, social et environnemental": "publication",
}
REG_NATURES = ("ordonnance", "décret", "arrêté", "circulaire", "instruction", "loi")
SKIP_TITLES = re.compile(r"(?i)d[ée]l[ée]gation de signature|portant nomination|\bnomm[ée]e?s?\b")
PUB_NATURES = ("avis", "rapport", "déclaration", "résolution", "étude")


def _doc_type(section_type, title):
    first = title.split(" ", 1)[0].lower().rstrip(",")
    if section_type == "law":
        return "law" if first == "loi" else None
    if section_type == "regulation":
        if first == "loi":
            return "law"
        return "regulation" if first in REG_NATURES else None
    return "publication" if first in PUB_NATURES else None


def parse_container(raw, since=None):
    """[entry] from one JORF sommaire (a 'conteneur' XML), or [] when the issue
    was published before `since`."""
    root = ET.fromstring(raw)
    published = root.findtext(".//META_CONTENEUR/DATE_PUBLI") or root.findtext(".//DATE_PUBLI")
    if since and (published or "") < since:
        return []
    issue = G.one_line(root.findtext(".//META_CONTENEUR/TITRE"))
    out = []

    def walk(el, path):
        for child in el:
            if child.tag == "TM":
                walk(child, path + [G.one_line(child.findtext("TITRE_TM"))])
            elif child.tag == "LIEN_TXT":
                keep = None
                for level in path:
                    keep = KEEP_SECTIONS.get(level.lower(), keep)
                if keep is None:
                    continue
                title = G.one_line(child.get("titretxt"))
                kind = _doc_type(keep, title)
                tid = child.get("idtxt")
                if not kind or not tid or SKIP_TITLES.search(title):
                    continue
                if keep == "regulation" and "textes généraux" in [p.lower() for p in path]:
                    i = [p.lower() for p in path].index("textes généraux")
                    body = path[i + 1] if len(path) > i + 1 else None
                elif keep == "law":
                    body = "Parlement"
                else:
                    body = path[-1] if path else None
                out.append(G.entry("jorf", tid, title, kind, body=body, published=published,
                                   url=LEGIFRANCE + tid, status=issue))

    struct = root.find("STRUCTURE_TXT")
    if struct is not None:
        walk(struct, [])
    return out


def containers_from_tar(blob):
    """The sommaire XMLs inside one increment, read from memory."""
    out = []
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for m in tf:
            if m.isfile() and "/conteneur/" in m.name and m.name.endswith(".xml"):
                fh = tf.extractfile(m)
                if fh is not None:
                    out.append(fh.read())
    return out


def fetch_jorf(client, today, log):
    page = client.get_text(DILA, "fr-govdocs-jorf", "index", archive=False)
    files = parse_index(page, today)
    if not files:
        return G.fetched([], gaps=["no JORF increment of the last {0} days in the DILA index".format(
            JORF_DAYS)])
    since = G.window_start(today)
    seen, out, gaps = set(), [], []
    for name, _day in files:
        try:
            blob = client.get_bytes(DILA + name, "fr-govdocs-jorf", name[:-7], archive=False)
            xmls = containers_from_tar(blob)
        except Exception as exc:                        # noqa: BLE001
            gaps.append("{0}: {1}".format(name, str(exc)[:120]))
            continue
        for raw in xmls:
            try:
                got = parse_container(raw, since)
            except ET.ParseError as exc:
                gaps.append("{0}: sommaire unparsable: {1}".format(name, exc))
                continue
            for e in got:
                if e["doc_id"] not in seen:
                    seen.add(e["doc_id"])
                    out.append(e)
    return G.fetched(out, note="{0} JORF increment(s) read".format(len(files)), gaps=gaps)


# --- environment ministry consultations ------------------------------------------------

_DD_CARD = re.compile(
    r'<a href="([^"]+)" class="fr-card__link">(.*?)</a>.*?class="dateart"><p>\s*Consultation\s+du\s+'
    r'(\d{2}/\d{2}/\d{4})(?:\s+au\s+(\d{2}/\d{2}/\d{4}))?(.*?)</div>(.*?)(?=<div class="item-liste-articles|'
    r'<nav role="navigation"|$)', re.S)


def dd_kind(title):
    t = title.lower().replace("\u2019", "'")
    if t.startswith(("synthèse", "synthese", "bilan", "résultats")):
        return "consultation_outcome"
    if re.match(r"projets? d'ordonnance|projets? de loi", t):
        return "bill_draft"
    if re.match(r"projets? de d[ée]cret|projets? d'arr[êe]t[ée]|d[ée]cret|arr[êe]t[ée]", t):
        return "regulation_draft"
    return "consultation"


def parse_dd(page):
    """[entry] from one page of the consultations listing."""
    out = []
    for href, title, opened, closes, rest, tail in _DD_CARD.findall(page):
        title = G.text(title)
        m = re.search(r"-a(\d+)\.html", href)
        doc = m.group(1) if m else href
        contrib = G.text(rest).strip(" -")
        tag = re.search(r'class="tag_active[^"]*">(.*?)</p>', tail, re.S)
        status = "; ".join(x for x in (G.text(tag.group(1)) if tag else None, contrib) if x)
        kind = dd_kind(title)
        out.append(G.entry("dd", doc, title, kind, body=DD_BODY, published=opened,
                           closing_date=closes if kind != "consultation_outcome" else None,
                           url=href if href.startswith("http") else DD + href,
                           status=status))
    return out


def fetch_dd(client, today, log):
    start = G.window_start(today)
    out, gaps, old_pages = [], [], 0
    for n in range(DD_MAX_PAGES):
        url = DD_LIST if n == 0 else "{0}&debut_listearticles={1}".format(DD_LIST, n * DD_PAGE)
        page = client.get_text(url, "fr-govdocs-dd", "list-{0}".format(n), archive=n == 0)
        got = parse_dd(page)
        out += got
        # the listing is ordered by last change, not strictly by opening date:
        # stop after two pages in a row with nothing in the window
        stale = all((e["published"] or "") < start and (e["closing_date"] or "") < today for e in got)
        old_pages = old_pages + 1 if stale else 0
        if not got or old_pages >= 2:
            break
    else:
        gaps.append("stopped after {0} pages before reaching {1}".format(DD_MAX_PAGES, start))
    return G.fetched(out, note="{0} consultations listed".format(len(out)), gaps=gaps)


# --- social affairs RSS -----------------------------------------------------------------

def _rss_date(value):
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\w*\s+(\d{4})", value or "")
    if not m:
        return G.iso(value)
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
              "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    mo = months.get(m.group(2).lower())
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), mo, int(m.group(1))) if mo else None


def parse_rss(xml_text, source, body):
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml_text, re.S):
        def tag(name):
            m = re.search(r"<{0}>(.*?)</{0}>".format(name), item, re.S)
            return m.group(1) if m else ""
        title = G.text(re.sub(r"^<!\[CDATA\[|\]\]>$", "", tag("title").strip()))
        link = G.text(tag("link"))
        if not title or not link:
            continue
        kind = "consultation" if re.search(r"(?i)\bconsultation (citoyenne|publique)\b", title) \
            and not re.search(r"(?i)r[ée]sultats?", title) else "press_release"
        slug = link.rstrip("/").rsplit("/", 1)[-1][:120]
        out.append(G.entry(source, slug, title, kind, body=body, published=_rss_date(tag("pubDate")),
                           url=link, summary=G.text(tag("description"))))
    return out


def fetch_solidarites(client, today, log):
    xml_text = client.get_text(SOL_RSS, "fr-govdocs-solidarites", "rss")
    return G.fetched(parse_rss(xml_text, "solidarites", SOL_BODY))


SOURCES = (
    G.Source(code="jorf", name="Journal officiel (DILA open data: lois, décrets, arrêtés)",
             fetch=fetch_jorf, url=DILA),
    G.Source(code="dd", name="Consultations publiques du ministère de la Transition écologique",
             fetch=fetch_dd, url=DD_LIST),
    G.Source(code="solidarites", name="Ministères des solidarités (RSS)",
             fetch=fetch_solidarites, url=SOL_RSS),
)
