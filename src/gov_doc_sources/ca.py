"""Canada: Consulting with Canadians, the Canada Gazette and the News Centre.

Probed 16 October 2026. Three sources, all keyless:

CONSULTING WITH CANADIANS (code 'cwc'). The federal government's register
of public consultations is an open-data dataset on open.canada.ca
("Government of Canada - Consultations", CKAN id
7c03f039-3753-4093-af60-74b0f7b2385d, Open Government Licence - Canada).
Its resource "Consultations - Last two years" is one CSV,
open.canada.ca/static/current_consultations_open.csv, regenerated daily
(877 rows on 16 October 2026, about 1.3 MB): registration number, owning
department, English and French title and description, start_date,
end_date (the closing date), status (O open, P planned, C closed) and the
consultation's own page. The canada.ca "Consulting with Canadians" pages
are built from the same register. robots.txt on open.canada.ca disallows
only Drupal paths and /search/; it sets Crawl-delay: 20, which the guarded
client honours (one request per run).

CANADA GAZETTE (code 'gazette', a MIRROR). tools/ca_gazette.py (in
jobs/ca-weekly.sh) already reads every Part I and Part II issue into
ca_gazette_items, so nothing is fetched twice:
  * a Part I PROPOSED REGULATION is a 'regulation_draft' whose closing date
    is comment_until (publication date plus the "within N days after the
    date of publication" the collector reads from its text);
  * a Part I GOVERNMENT NOTICE is a 'consultation' when its own text asks
    for comments within N days (the closing date worked out the same way),
    else a 'publication';
  * a Part I order in council, and every Part II item (made regulations,
    SOR, and statutory instruments, SI), is a 'regulation'.
Commission, Parliament and miscellaneous notices and supplements are left
out: not government decrees or consultations.

NEWS CENTRE (code 'news'). canada.ca's news releases from the Government
of Canada's documented web feed (api.io.canada.ca/io-server/gc/news,
listed on canada.ca's "News feeds" page), Atom, the window in one request
(847 releases in 92 days). Each is a 'press_release'; the precision gate
keeps only tier-1 matches. Media advisories, speeches and statements are
not asked for.

CLASSIFICATION. The English shared taxonomy (config/taxonomy.yaml), as
every Canadian federal tool (tools/ca_monitor.py, tools/ca_gazette.py)
classifies. config/taxonomy-qc.yaml is the Quebec French list used for the
National Assembly; the French text of these sources is not read.
"""

from __future__ import annotations

import csv
import datetime
import io
import re
import xml.etree.ElementTree as ET

from src import gov_docs as G

CC = "ca"
TAXONOMIES = (("taxonomy.yaml", None),)

CWC_CSV = "https://open.canada.ca/static/current_consultations_open.csv"
CWC_DATASET = "https://open.canada.ca/data/en/dataset/7c03f039-3753-4093-af60-74b0f7b2385d"
CWC_STATUS = {"O": "Open", "P": "Planned", "C": "Closed"}
NEWS = ("https://api.io.canada.ca/io-server/gc/news/en/v2?type=newsreleases&sort=publishedDate"
        "&orderBy=desc&publishedDate%3E={0}&pick=1000&format=atom&atomtitle=Canada.ca")
ATOM = "{http://www.w3.org/2005/Atom}"
COMMENT = re.compile(r"within (\d+) days (?:after|of) (?:the date of )?(?:its )?publication", re.I)
ASKS_COMMENT = re.compile(r"\b(comments?|representations?|submissions?|views)\b", re.I)


# --- Consulting with Canadians ----------------------------------------------------

def english(value):
    """'Health Canada | Santé Canada' -> 'Health Canada'."""
    return (value or "").split(" | ")[0].strip() or None


def parse_cwc(raw):
    """[entry] from the register's CSV."""
    out = []
    reader = csv.DictReader(io.StringIO(raw.lstrip("﻿")))
    for r in reader:
        reg = (r.get("registration_number") or "").strip()
        title = (r.get("title_en") or "").strip()
        if not reg or not title:
            continue
        page = (r.get("profile_page_en") or "").strip()
        if not page.startswith("http") or "safelinks.protection.outlook.com" in page:
            page = CWC_DATASET
        # Some rows link canada.ca's authoring preview host; the page is on canada.ca.
        page = page.replace("://canada-preview.adobecqms.net/", "://www.canada.ca/")
        org = (r.get("owner_org") or "").strip()
        out.append(G.entry(
            "cwc", "{0}/{1}".format(org, reg) if org else reg, title, "consultation",
            body=english(r.get("owner_org_title")), published=r.get("start_date"),
            closing_date=r.get("end_date"), url=page, summary=r.get("description_en"),
            status=CWC_STATUS.get((r.get("status") or "").strip(), r.get("status")),
            refs=[reg]))
    return out


def fetch_cwc(client, today, log):
    raw = client.get_text(CWC_CSV, "ca-govdocs", "cwc-{0}".format(today))
    got = parse_cwc(raw)
    return G.fetched(got, note="{0} consultations in the register's last two years".format(len(got)))


# --- the Canada Gazette, mirrored ---------------------------------------------------

def demojibake(value):
    """'Companiesâ€™' (UTF-8 read as Windows-1252, as some Gazette rows were) -> 'Companies’'."""
    s = value or ""
    if "â€" in s or "Ã" in s:
        try:
            return s.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s


def _plus_days(date, days):
    try:
        return (datetime.date.fromisoformat(date) + datetime.timedelta(days=int(days))).isoformat()
    except (TypeError, ValueError):
        return None


def gazette_entry(r):
    """One ca_gazette_items row (a dict) as an entry, or None when out of scope."""
    part, section = r.get("part"), (r.get("section") or "").strip().lower()
    title = demojibake(r.get("title"))
    text = demojibake(r.get("text") or "")
    closing = None
    if part == 1 and section.startswith("proposed regulation"):
        kind, closing = "regulation_draft", r.get("comment_until")
    elif part == 1 and section.startswith("government notice"):
        m = COMMENT.search(text)
        if m and ASKS_COMMENT.search(text):
            kind, closing = "consultation", _plus_days(r.get("date"), m.group(1))
        else:
            kind = "publication"
    elif part == 1 and section.startswith("orders in council"):
        kind = "regulation"
    elif part == 2:
        kind = "regulation"
    else:
        return None
    summary = demojibake(r.get("excerpt") or "") or text[:G.SUMMARY_CAP]
    terms = [t.rstrip("*") for t in G.loads(r.get("matched_terms")) if t]
    if terms:
        # The collector matched the whole regulation PER PASSAGE; its excerpt
        # is one passage. Its matched terms carry the rest of that reading.
        summary = "Terms matched in the text: {0}. {1}".format("; ".join(terms), summary)
    return G.entry("gazette", r["item_key"].split("gazette.gc.ca/", 1)[-1], title, kind,
                   body=demojibake(r.get("department")), published=r.get("date"),
                   closing_date=closing, url=r.get("url"), summary=summary,
                   status=" ".join(x for x in ("Canada Gazette Part {0}".format(part),
                                               r.get("registration") or "") if x),
                   refs=[r.get("registration")] if r.get("registration") else ())


def mirror_gazette(conn, cc, today):
    start = G.window_start(today)
    try:
        cur = conn.execute(
            "SELECT item_key, part, date, section, department, title, url, registration, "
            "comment_until, excerpt, text, matched_terms FROM ca_gazette_items WHERE date >= ? OR "
            "comment_until >= ?", (start, today))
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        last = conn.execute("SELECT MAX(date), MAX(read_at) FROM ca_gazette_issues").fetchone()
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["ca_gazette_items unreadable: {0}".format(str(exc)[:160])])
    out = [e for e in (gazette_entry(r) for r in rows) if e]
    gaps = []
    if not rows:
        gaps.append("ca_gazette_items holds nothing in the window (has tools/ca_gazette.py run?)")
    return G.fetched(out, note="mirrored from ca_gazette_items (latest issue {0}, read {1})".format(
        last[0], last[1]), gaps=gaps)


# --- the News Centre ------------------------------------------------------------------

def parse_news(raw):
    out = []
    root = ET.fromstring(raw.encode("utf-8") if isinstance(raw, str) else raw)
    for e in root.findall(ATOM + "entry"):
        link = e.find(ATOM + "link")
        url = (link.get("href") if link is not None else None) or e.findtext(ATOM + "id")
        if not url:
            continue
        key = url.split("canada.ca/en/", 1)[-1].rsplit(".html", 1)[0]
        out.append(G.entry("news", key, e.findtext(ATOM + "title"), "press_release",
                           body=e.findtext(ATOM + "author/" + ATOM + "name"),
                           published=e.findtext(ATOM + "updated"), url=url,
                           summary=G.text(e.findtext(ATOM + "summary")),
                           status="News release"))
    return out


def fetch_news(client, today, log):
    raw = client.get_text(NEWS.format(G.window_start(today)), "ca-govdocs", "news-{0}".format(today))
    got = parse_news(raw)
    return G.fetched(got, note="{0} news releases".format(len(got)))


SOURCES = (
    G.Source(code="cwc", name="Consulting with Canadians (open.canada.ca register)",
             url=CWC_CSV, fetch=fetch_cwc),
    G.Source(code="gazette", name="Canada Gazette (proposed and made regulations, government notices)",
             url="https://gazette.gc.ca/rss/p1-eng.xml", mirror=mirror_gazette),
    G.Source(code="news", name="Canada.ca News Centre (news releases)",
             url="https://api.io.canada.ca/io-server/gc/news/en/v2", fetch=fetch_news),
)
