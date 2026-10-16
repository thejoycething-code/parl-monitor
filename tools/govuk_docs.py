"""GOV.UK consultations and key publications on our ground -> govuk_docs
(16 October 2026).

    python3 tools/govuk_docs.py [--db PATH] [--since-days N] [--today YYYY-MM-DD]

Run by the Sunday pull (jobs/sunday-pull.sh) after run_weekly.py, so the
Monday edition can list the consultations on our issues with their closing
dates, and the week's notable publications.

GOV.UK, through its documented public APIs (docs.publishing.service.gov.uk:
the Search API www.gov.uk/api/search.json and the Content API
www.gov.uk/api/content/<path>). www.gov.uk/robots.txt (read 16 October 2026)
disallows only /*/print$ and /search/all*; every request still asks it at
run time (src/robots_guard.guard). Four reads:

  1. every open consultation, any department (43 on 16 October 2026);
  2. consultations that closed in the last WINDOW_DAYS, any department
     (filter_end_date), and consultation outcomes published in that window;
  3. publications of the organisations in ORGANISATIONS, of the types in
     PUBLICATION_TYPES, published in the last --since-days (14; 35 on a
     store with no row yet);
  4. the Content API for a consultation on our ground whose search record
     has no closing date.

Two regulator routes land in the same table (source says which), for the
regulators the older feed (src/ingest/regulators.py) declared 403:

  * Ofcom: www.ofcom.org.uk answers our identified UA again (16 October
    2026; robots.txt allows the listing). Its consultations-and-statements
    listing is read, and each item on our ground's page for its closing date.
  * NHS England: its WordPress publication feed (/publication/feed/, paged
    with ?paged=N; robots.txt disallows only /wp-admin/), back to the window,
    and each item's page for its summary (the feed's descriptions are empty).
    NHS England's statistics also reach gov.uk (organisation nhs-england).
  * EHRC: equalityhumanrights.com answers 403 to every request (a Cloudflare
    check, including its RSS and sitemap); its gov.uk organisation page is
    read in (3). GMC: gmc-uk.org answers 403 to everything, robots.txt too,
    and has no gov.uk organisation. Both stay declared in
    regulators.BLOCKED, so the edition's footer says so every week.

ON OUR GROUND. The English taxonomy (src/filter.filter_item) over title +
description (+ NHS England's own categories). Precision gate: a consultation
is kept on any match; a publication needs tier 1 or a watchlist name, as
tier-2 vocabulary in descriptions ("children", "schools") would otherwise
admit much of the Department for Education's output.

FAILING LOUD. Every read that failed is a [gap] line and a gaps row for the
coming edition, and the exit status is 1.
"""

from __future__ import annotations

import argparse
import datetime
import email.utils
import html
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, robots_guard, uk_civic_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "govuk_docs"
SEARCH = "https://www.gov.uk/api/search.json"
CONTENT = "https://www.gov.uk/api/content{0}"
FIELDS = ("title", "link", "description", "end_date", "start_date", "public_timestamp", "organisations",
          "content_store_document_type")
WINDOW_DAYS = 92
SINCE_DAYS = 14
FIRST_RUN_DAYS = 35
PAGE = 500
MAX_RESULTS = 5000

# The departments and bodies whose publications we read (consultations are
# read from every department). Slugs checked against www.gov.uk/api/
# organisations/<slug> on 16 October 2026.
ORGANISATIONS = (
    "department-of-health-and-social-care",
    "department-for-education",
    "home-office",
    "ministry-of-justice",
    "government-equalities-office",
    "office-for-equality-and-opportunity",
    "department-for-science-innovation-and-technology",
    "cabinet-office",
    "nhs-england",
    "northern-ireland-office",
    "office-of-the-secretary-of-state-for-scotland",
    "office-of-the-secretary-of-state-for-wales",
    "scotland-office",
    "wales-office",
    # Regulators' gov.uk pages (the alternative route for the 403 hosts)
    "equality-and-human-rights-commission",
    "ofcom",
    "human-fertilisation-and-embryology-authority",
)
PUBLICATION_TYPES = (
    "policy_paper", "guidance", "statutory_guidance", "detailed_guide", "official_statistics",
    "national_statistics", "research", "independent_report", "impact_assessment", "corporate_report",
    "press_release", "news_story", "speech", "correspondence", "decision", "notice",
    "closed_consultation", "consultation_outcome", "open_consultation",
)
CONSULTATION_TYPES = ("open_consultation", "closed_consultation", "consultation_outcome")

OFCOM_LIST = "https://www.ofcom.org.uk/consultations-and-statements"
OFCOM_PREFIXES = ("consultation", "call for", "statement")
OFCOM_SELF = re.compile(r"\bOfcom(?:'s|\u2019s)?\b", re.I)
NHSE_FEED = "https://www.england.nhs.uk/publication/feed/"
NHSE_MAX_PAGES = 10

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                       "august", "september", "october", "november", "december"], 1)}
_TAG = re.compile(r"<[^>]+>")


def edition_week(today):
    if today.weekday() == 6:
        return (today + datetime.timedelta(days=1)).isoformat()
    return (today - datetime.timedelta(days=today.weekday())).isoformat()


def write_gaps(conn, today, gaps):
    """The run's gaps, as rows for the edition the Sunday pull feeds (its
    footer prints them). run_weekly.py --pull clears that edition's gaps when
    it starts; this runs after it, so these stand."""
    edition = edition_week(today)
    for detail in gaps:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)", (edition, FEED, detail))
    conn.commit()
    return edition


def _text(fragment):
    return html.unescape(" ".join(_TAG.sub(" ", fragment or "").split()))


def _long_date(text):
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text or "")
    if not m or m.group(2).lower() not in MONTHS:
        return None
    try:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
    except ValueError:
        return None


class Doc:
    __slots__ = ("base_path", "title", "doc_type", "organisation", "public_updated_at", "closing_date", "url",
                 "description", "source", "opening_date", "extra_text")

    def __init__(self, base_path, title, doc_type, organisation, public_updated_at, url, description="",
                 closing_date=None, source="govuk", opening_date=None, extra_text=""):
        self.base_path, self.title, self.doc_type = base_path, title, doc_type
        self.organisation, self.public_updated_at, self.url = organisation, public_updated_at, url
        self.description, self.closing_date, self.source = description or "", closing_date, source
        self.opening_date, self.extra_text = opening_date, extra_text or ""

    @property
    def is_consultation(self):
        return self.doc_type in CONSULTATION_TYPES or self.doc_type == "consultation"


# --- GOV.UK ---------------------------------------------------------------

def search_url(params, start=0, count=PAGE):
    q = list(params) + [("count", str(count)), ("start", str(start)), ("order", "-public_timestamp")]
    q += [("fields", f) for f in FIELDS]
    return SEARCH + "?" + urllib.parse.urlencode(q)


def parse_search(payload):
    out = []
    for r in payload.get("results") or []:
        link = r.get("link") or ""
        if not link.startswith("/"):
            continue                              # external links: not a gov.uk page
        orgs = [o.get("title") for o in (r.get("organisations") or []) if isinstance(o, dict) and o.get("title")]
        out.append(Doc(base_path=link, title=(r.get("title") or "").strip(),
                       doc_type=r.get("content_store_document_type") or "",
                       organisation="; ".join(orgs), public_updated_at=(r.get("public_timestamp") or "")[:10] or None,
                       url="https://www.gov.uk" + link, description=(r.get("description") or "").strip(),
                       closing_date=(r.get("end_date") or "")[:10] or None,
                       opening_date=(r.get("start_date") or "")[:10] or None))
    return out, payload.get("total") or 0


def parse_content(payload):
    """(closing_date, opening_date) from a Content API consultation."""
    d = payload.get("details") or {}
    return (d.get("closing_date") or "")[:10] or None, (d.get("opening_date") or "")[:10] or None


# --- Ofcom ------------------------------------------------------------------

def parse_ofcom_listing(page):
    """Each card: <a href=URL><div class="info-card"> <h3 class="info-card-header">TITLE</h3> ...
    Published: D Month YYYY / Last updated: ... <p>DESCRIPTION</p>. PDFs and Welsh copies are skipped;
    only consultations, calls for evidence/input and statements are kept."""
    out, seen = [], set()
    for m in re.finditer(r'<a href="([^"]+)">\s*<div class="info-card">(.*?)</a>', page or "", re.S):
        url, body = m.group(1), m.group(2)
        if url.startswith("/"):
            url = "https://www.ofcom.org.uk" + url
        if "ofcom.org.uk" not in url or "/siteassets/" in url or "/cy/" in url or url in seen:
            continue
        t = re.search(r'info-card-header">(.*?)</h3>', body, re.S)
        title = _text(t.group(1)) if t else ""
        low = title.lower()
        if not low.startswith(OFCOM_PREFIXES) and "call for" not in low:
            continue
        # 'consultation' (calls for evidence and input too) is the word the
        # edition reads as a deadline (src/countdown.govuk_from_store); a
        # statement is a publication. source='ofcom' keeps the origin.
        kind = "ofcom_statement" if low.startswith("statement") else "consultation"
        pub = re.search(r"Published:\s*([^<]+)", body)
        upd = re.search(r"Last updated:\s*([^<]+)", body)
        desc = re.findall(r"<p>(.*?)</p>", body, re.S)
        seen.add(url)
        # The page's section is Ofcom's own subject label ('online-safety',
        # 'spectrum', 'tv-radio-and-on-demand'): matched with the title.
        section = urllib.parse.urlsplit(url).path.strip("/").split("/")[0].replace("-", " ")
        out.append(Doc(base_path=url, title=title, doc_type=kind, organisation="Ofcom", extra_text=section,
                       public_updated_at=_long_date(upd.group(1) if upd else "") or _long_date(pub.group(1) if pub else ""),
                       url=url, description=_text(desc[-1]) if desc else "", source="ofcom",
                       opening_date=_long_date(pub.group(1)) if pub else None))
    return out


def parse_ofcom_page(page):
    """(closing_date, status) from an Ofcom consultation page:
    'Consultation closes: 4 November 2026 Status: Open'."""
    text = _text(page)
    m = re.search(r"(?:Consultation|Call for \w+|Submission)\s+closes:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", text, re.I)
    s = re.search(r"Status:\s*(\w+)", text)
    return (_long_date(m.group(1)) if m else None), (s.group(1) if s else None)


# --- NHS England ----------------------------------------------------------

def parse_rss(xml_text):
    """[(title, link, pub_date ISO, categories, description)] from a WordPress RSS 2.0 feed."""
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml_text or "", re.S):
        def tag(name):
            m = re.search(r"<{0}>(.*?)</{0}>".format(name), item, re.S)
            v = m.group(1) if m else ""
            v = re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", v.strip(), flags=re.S)
            return _text(v)
        cats = [_text(re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", c.strip(), flags=re.S))
                for c in re.findall(r"<category>(.*?)</category>", item, re.S)]
        pub = None
        try:
            pub = email.utils.parsedate_to_datetime(tag("pubDate")).date().isoformat()
        except (TypeError, ValueError):
            pass
        out.append((tag("title"), tag("link"), pub, cats, tag("description")))
    return out


def parse_nhse_page(page):
    """The summary of an NHS England publication page: the text of <main>
    up to the footer links, at most 800 characters."""
    page = page or ""
    i = page.find("<main")
    body = page[i:] if i >= 0 else page
    j = body.find("</main>")
    body = body[:j] if j >= 0 else body
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S)
    return _text(body)[:800]


# --- the sweep --------------------------------------------------------------

class Sweep:
    def __init__(self, client, conn, tax, wl, today, log=print, since_days=None):
        self.client, self.conn, self.tax, self.wl = client, conn, tax, wl
        self.today, self.today_iso = today, today.isoformat()
        self.log = log
        if since_days is None:
            have = conn.execute("SELECT COUNT(*) FROM govuk_docs WHERE source = 'govuk'").fetchone()[0]
            since_days = SINCE_DAYS if have else FIRST_RUN_DAYS
        self.since = (today - datetime.timedelta(days=since_days)).isoformat()
        self.window = (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
        self.gaps = []
        self.stats = {}

    def gap(self, detail):
        self.gaps.append(detail)
        self.log("  [gap] {0}: {1}".format(FEED, detail))

    def search(self, label, params):
        """Every result of one search, paged. -> [Doc] (partial on failure, with a gap)."""
        out, start = [], 0
        while start < MAX_RESULTS:
            try:
                payload = self.client.get_json(search_url(params, start), FEED,
                                               "{0}-{1}".format(label, start))
            except FetchError as exc:
                self.gap("GOV.UK search '{0}' failed at {1}: {2}".format(label, start, str(exc)[:160]))
                break
            docs, total = parse_search(payload)
            out.extend(docs)
            start += PAGE
            if not docs or start >= total:
                break
        self.stats[label] = len(out)
        return out

    def govuk(self):
        docs = {}
        reads = [
            ("open-consultations", [("filter_content_store_document_type", "open_consultation")]),
            ("closed-consultations", [("filter_content_store_document_type", "closed_consultation"),
                                      ("filter_end_date", "from:" + self.window)]),
            ("consultation-outcomes", [("filter_content_store_document_type", "consultation_outcome"),
                                       ("filter_public_timestamp", "from:" + self.window)]),
            ("publications", [("filter_organisations", o) for o in ORGANISATIONS]
             + [("filter_content_store_document_type", t) for t in PUBLICATION_TYPES]
             + [("filter_public_timestamp", "from:" + self.since)]),
        ]
        for label, params in reads:
            for d in self.search(label, params):
                docs.setdefault(d.base_path, d)
        return list(docs.values())

    def ofcom(self):
        try:
            page = self.client.get_text(OFCOM_LIST, FEED, "ofcom-consultations")
        except FetchError as exc:
            self.gap("Ofcom consultations listing unreadable: {0}".format(str(exc)[:160]))
            return []
        docs = parse_ofcom_listing(page)
        if not docs:
            self.gap("Ofcom listing answered but nothing parsed (layout changed?)")
        self.stats["ofcom"] = len(docs)
        return docs

    def nhs_england(self):
        out = []
        for n in range(1, NHSE_MAX_PAGES + 1):
            url = NHSE_FEED if n == 1 else NHSE_FEED + "?paged={0}".format(n)
            try:
                items = parse_rss(self.client.get_text(url, FEED, "nhse-publications-{0}".format(n)))
            except FetchError as exc:
                self.gap("NHS England publication feed page {0} unreadable: {1}".format(n, str(exc)[:160]))
                break
            if not items and n == 1:
                self.gap("NHS England publication feed answered but held no items")
            for title, link, pub, cats, desc in items:
                if not link:
                    continue
                out.append(Doc(base_path=link, title=title, doc_type="nhs_england_publication",
                               organisation="NHS England", public_updated_at=pub, url=link, description=desc,
                               source="nhs-england", extra_text=" ".join(cats)))
            if not items or all((pub or "") < self.since for _t, _l, pub, _c, _d in items):
                break
        out = [d for d in out if (d.public_updated_at or "") >= self.since]
        # The feed's descriptions are empty: the page's own summary (topic,
        # type, the paragraph under them) is what the taxonomy reads.
        for d in out:
            try:
                d.description = parse_nhse_page(self.client.get_text(
                    d.url, FEED, "nhse-" + d.url.rstrip("/").rsplit("/", 1)[-1][:60]))
            except FetchError as exc:
                self.gap("NHS England page {0} unreadable: {1}".format(d.url, str(exc)[:120]))
                continue
            # "Publication type: Guidance" -> doc_type 'guidance', the label
            # the edition prints; source='nhs-england' keeps the origin.
            m = re.search(r"Publication type:\s*([A-Za-z][A-Za-z ,&-]{1,40}?)\s+(?:This|The|These|A|An|Link|Summary)\b",
                          d.description)
            if m:
                d.doc_type = m.group(1).strip().lower().replace(" ", "_")
        self.stats["nhs-england"] = len(out)
        return out

    def on_our_ground(self, d):
        title, desc, extra = d.title, d.description, d.extra_text
        if d.source == "ofcom":
            # "Ofcom" is itself a taxonomy term: on Ofcom's own pages it says
            # nothing, so it is taken out before matching (it matched all 17
            # listed items on 16 October 2026, spectrum auctions included).
            title, desc, extra = (OFCOM_SELF.sub(" ", x) for x in (title, desc, extra))
        r = filt.filter_item(self.tax, self.wl, title, desc, extra)
        if not r.matched():
            return None
        if d.is_consultation or r.tier == 1 or r.watchlist_hits:
            return r
        return None

    def enrich(self, d):
        """Closing dates the listing lacks: Content API (gov.uk), the page (Ofcom)."""
        try:
            if d.source == "govuk" and d.doc_type in CONSULTATION_TYPES and not d.closing_date:
                d.closing_date, opening = parse_content(self.client.get_json(
                    CONTENT.format(d.base_path), FEED, "content-" + d.base_path.strip("/").replace("/", "-")[:60]))
                d.opening_date = d.opening_date or opening
            elif d.source == "ofcom" and d.doc_type != "ofcom_statement":
                d.closing_date, _status = parse_ofcom_page(self.client.get_text(
                    d.url, FEED, "ofcom-" + d.url.rstrip("/").rsplit("/", 1)[-1][:60]))
        except FetchError as exc:
            self.gap("closing date for {0} unreadable: {1}".format(d.url, str(exc)[:120]))

    def store(self, d, r):
        self.conn.execute(
            "INSERT INTO govuk_docs (base_path, title, doc_type, organisation, public_updated_at, closing_date, url, "
            "areas, matched_terms, first_seen, last_seen, description, source, tier, opening_date) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(base_path) DO UPDATE SET title=excluded.title, "
            "doc_type=excluded.doc_type, organisation=excluded.organisation, "
            "public_updated_at=excluded.public_updated_at, "
            "closing_date=COALESCE(excluded.closing_date, govuk_docs.closing_date), url=excluded.url, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, last_seen=excluded.last_seen, "
            "description=excluded.description, source=excluded.source, tier=excluded.tier, "
            "opening_date=COALESCE(excluded.opening_date, govuk_docs.opening_date)",
            (d.base_path, d.title, d.doc_type, d.organisation, d.public_updated_at, d.closing_date, d.url,
             json.dumps(r.issue_areas), json.dumps(r.matched_terms + r.watchlist_hits), self.today_iso,
             self.today_iso, d.description[:1000], d.source, r.tier, d.opening_date))

    def run(self):
        docs = self.govuk() + self.ofcom() + self.nhs_england()
        kept = []
        for d in docs:
            r = self.on_our_ground(d)
            if r is not None:
                kept.append((d, r))
        for d, r in kept:
            self.enrich(d)
            self.store(d, r)
        self.conn.commit()
        self.stats["fetched"], self.stats["matched"] = len(docs), len(kept)
        uk_civic_store.record_run(self.conn, FEED, self.today_iso, not self.gaps, len(docs), len(kept),
                                  "; ".join(self.gaps)[:500] or None)
        return kept


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--since-days", type=int, help="publications window (default 14; 35 on an empty table)")
    ap.add_argument("--today", help="YYYY-MM-DD (tests and replays)")
    args = ap.parse_args(argv)
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    conn = db.init_db(db.connect(args.db))
    client = robots_guard.guard(HttpClient(raw_dir=os.path.join(ROOT, "data", "raw")), FEED)
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    sweep = Sweep(client, conn, tax, wl, today, since_days=args.since_days)
    try:
        sweep.run()
    except Exception as exc:                                # noqa: BLE001
        sweep.gap("sweep failed: {0}".format(str(exc)[:200]))
    write_gaps(conn, today, sweep.gaps)
    s = sweep.stats
    print("govuk_docs: {0} read ({1}), {2} on our ground; {3} gap(s)".format(
        s.get("fetched", 0), ", ".join("{0} {1}".format(k, v) for k, v in s.items()
                                       if k not in ("fetched", "matched")),
        s.get("matched", 0), len(sweep.gaps)))
    return 1 if sweep.gaps else 0


if __name__ == "__main__":
    sys.exit(main())
