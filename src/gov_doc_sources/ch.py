"""Switzerland: Vernehmlassungen (mirrored), the federal administration's news
(News Service Bund) and the federal acts and ordinances published in the
Official Compilation (AS) (16 October 2026).

The edition adapter (src/editions/ch.py) supplies the taxonomies
(taxonomy-atch for German, taxonomy-fr for French).

VERNEHMLASSUNGEN (mirror). src/petition_sources/ch.py already reads the
running consultations from the fedlex SPARQL endpoint into country_petitions
(cc 'ch', source 'vl', kind 'consultation') every week, each with its
consultation phase's end date (the deadline for responses). The rows are
re-filed here, not fetched twice: a draft Verordnung is a 'regulation_draft',
anything else (a law, a constitutional amendment, a treaty) a 'bill_draft';
closing_date is the deadline.

NEWS SERVICE BUND (www.newsd.admin.ch/newsd/feeds/rss, the federal
administration's own RSS of its press releases, German, about 500 items or
two months; robots.txt answers 404, so no rules). Each item names its office
(<author>): 'press_release', or 'statistics' for the Federal Statistical
Office. Items about Vernehmlassungen are kept as press releases too; the
consultation itself comes from the mirror.

OFFICIAL COMPILATION (fedlex.data.admin.ch/sparqlendpoint, the documented
keyless SPARQL endpoint already in src/robots_guard.DOCUMENTED_APIS): every
act published in the AS in the window (eli/oc/...), with its type: a
Bundesgesetz or a Bundesbeschluss is a 'law' (body: the Federal Assembly), a
Verordnung des Bundesrates, a Departementsverordnung or an Amtsverordnung a
'regulation'. Corrections, treaty texts and scope notices are left out.
"""

from __future__ import annotations

import re
import urllib.parse

from src import gov_docs as G

CC = "ch"
NSB = "https://www.newsd.admin.ch/newsd/feeds/rss?lang=de&org-nr=1&offer-nr="
SPARQL = ("https://fedlex.data.admin.ch/sparqlendpoint?query={0}"
          "&format=application%2Fsparql-results%2Bjson")
FEED = "ch-govdocs"
RT = "https://fedlex.data.admin.ch/vocabulary/resource-type/"
AS_TYPES = {
    "21": ("law", "Bundesgesetz", "Bundesversammlung"),
    "36": ("law", "Bundesbeschluss (fakultatives Referendum, Verträge)", "Bundesversammlung"),
    "29": ("regulation", "Verordnung des Bundesrates", "Bundesrat"),
    "26": ("regulation", "Departementsverordnung", "Departement"),
    "27": ("regulation", "Amtsverordnung", "Bundesamt"),
}

Q_AS = """PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?act ?date ?type ?title WHERE {
  ?act jolux:publicationDate ?date ; jolux:typeDocument ?type ; jolux:isRealizedBy ?e .
  ?e jolux:language <http://publications.europa.eu/resource/authority/language/DEU> ;
     jolux:title ?title .
  FILTER(?date >= "%s"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER(STRSTARTS(STR(?act), "https://fedlex.data.admin.ch/eli/oc/"))
} ORDER BY DESC(?date)"""


# --- Vernehmlassungen mirror --------------------------------------------------------

def draft_kind(title):
    t = (title or "").lower()
    if "verordnung" in t and "gesetz" not in t:
        return "regulation_draft"
    return "bill_draft"


def mirror_vl(conn, cc, today):
    start = G.window_start(today)
    try:
        rows = conn.execute(
            "SELECT item_id, title, status, opened, closes, body, url, summary, last_seen "
            "FROM country_petitions WHERE cc = ? AND source = 'vl' AND kind = 'consultation' "
            "AND (closes >= ? OR opened >= ?)", (cc, start, start)).fetchall()
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["country_petitions unreadable: {0}".format(str(exc)[:160])])
    out = []
    for r in rows:
        key = r[0].split(":", 1)[-1]
        out.append(G.entry("vl", key, r[1], draft_kind(r[1]), body=r[5], published=r[3],
                           closing_date=r[4], url=r[6], summary=r[7], status=r[2]))
    ever = conn.execute("SELECT COUNT(*), MAX(last_seen) FROM country_petitions WHERE cc = ? "
                        "AND source = 'vl'", (cc,)).fetchone()
    last = ever[1] if ever else None
    gaps = [] if ever and ever[0] else ["country_petitions holds no Vernehmlassung at all "
                                        "(has the petitions step run?)"]
    return G.fetched(out, note="mirrored from country_petitions source 'vl' (last read {0})"
                     .format(last), gaps=gaps)


# --- News Service Bund --------------------------------------------------------------

def parse_nsb(xml):
    """[entry] from the News Service Bund RSS."""
    out = []
    for attrs, block in re.findall(r"<item([^>]*)>(.*?)</item>", xml or "", re.S):
        def tag(name):
            m = re.search(r"<{0}>(.*?)</{0}>".format(name), block, re.S)
            return G.text(m.group(1)) if m else ""
        nid = re.search(r'nsb:id="([^"]+)"', attrs)
        link = tag("link")
        key = nid.group(1) if nid else link.rsplit("/", 1)[-1]
        author = tag("author") or None
        kind = "statistics" if author and "Statistik" in author else "press_release"
        out.append(G.entry("nsb", key, tag("title"), kind, body=author, published=tag("pubDate"),
                           url=link, summary=tag("description")))
    return out


def fetch_nsb(client, today, log=print):
    try:
        xml = client.get_text(NSB, FEED, "nsb-rss")
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["News Service Bund feed unreadable: {0}".format(str(exc)[:160])])
    got = parse_nsb(xml)
    dates = sorted(e["published"] for e in got if e["published"])
    return G.fetched(got, note="{0} items, {1} to {2}".format(
        len(got), dates[0] if dates else "?", dates[-1] if dates else "?"))


# --- Official Compilation (AS) ------------------------------------------------------

def parse_as(reply):
    out = []
    for b in (reply or {}).get("results", {}).get("bindings", []):
        act = (b.get("act") or {}).get("value") or ""
        code = ((b.get("type") or {}).get("value") or "").replace(RT, "")
        if code not in AS_TYPES or "/eli/oc/" not in act:
            continue
        kind, label, body = AS_TYPES[code]
        key = act.split("/eli/", 1)[-1]
        out.append(G.entry("as", key, (b.get("title") or {}).get("value"), kind, body=body,
                           published=(b.get("date") or {}).get("value"), url=act + "/de",
                           status=label, summary="AS {0}: {1}".format(key[3:], label)))
    return out


def fetch_as(client, today, log=print):
    url = SPARQL.format(urllib.parse.quote(Q_AS % G.window_start(today)))
    try:
        reply = client.get_json(url, FEED, "fedlex-as")
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["fedlex AS query failed: {0}".format(str(exc)[:160])])
    got = parse_as(reply)
    n = len((reply or {}).get("results", {}).get("bindings", []))
    return G.fetched(got, note="{0} AS publications in the window, {1} acts and ordinances".format(n, len(got)))


SOURCES = (
    G.Source(code="vl", name="Vernehmlassungen (mirrored from fedlex)", mirror=mirror_vl,
             url="https://fedlex.data.admin.ch/sparqlendpoint"),
    G.Source(code="nsb", name="News Service Bund (federal press releases)", fetch=fetch_nsb, url=NSB),
    G.Source(code="as", name="Official Compilation (AS): acts and ordinances", fetch=fetch_as,
             url="https://fedlex.data.admin.ch/sparqlendpoint"),
)
