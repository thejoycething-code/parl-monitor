#!/usr/bin/env python3
"""Peru's regional governments and Lima Metropolitana: council acts (PE4).

    python3 tools/pe_regions.py                       # the weekly read
    python3 tools/pe_regions.py --since 2026-09-01    # a longer gazette window (a seed)
    python3 tools/pe_regions.py --no-gobpe            # the gazette only
    python3 tools/pe_regions.py --dry-run
    python3 tools/pe_regions.py --reclassify
    python3 tools/pe_regions.py --db /tmp/pe.db

PE4, 12 October 2026 (docs/peru-regions-scope.md). Peru's 25 regional
governments each have a Consejo Regional that passes ordenanzas regionales
(the region's laws) and acuerdos; the Municipalidad Metropolitana de Lima
holds the regional functions for Lima province, and its Concejo
Metropolitano's ordenanzas are read with them. On our ground they move
first more often than Congress: regional ordinances on "enfoque de género"
in schools, on child marriage, on adolescent pregnancy, declarations of
"provida" regions and their repeal.

TWO SOURCES, ONE ROW PER NORM.

  * EL PERUANO, Normas Legales (diariooficial.elperuano.pe/Normas/Filtro):
    the official gazette, where an ordenanza regional must be published to
    take effect. One read-only form POST returns every norm published in a
    date range (measured: 597 norms for ten days, 2,285 for September 2026,
    no cap), each with its issuer heading, number, date, sumilla and the
    dispositivo link. Rows whose heading is a regional government or the
    Municipalidad Metropolitana de Lima are kept. robots.txt disallows only
    /Normas/NLactualizada and the file folders, none of which is read. ONE
    request a week (the last LOOKBACK_DAYS days).
  * GOB.PE, each institution's normas-legales pages, by norm type (the
    council's ordenanzas and acuerdos only, config/pe-regions.yaml): the
    first page of each, 25 newest. Adds acuerdos the gazette never prints
    and a PDF link. 3 s apart; about 65 requests, three to four minutes.
    robots.txt disallows only /admin/ and ?sheet= URLs.

The key is the norm's number reduced to its first integer and its year
(src/pe_store.py), so the two sources meet on one row; `source` says which
saw it.

WHAT IS CLASSIFIED: the heading and the sumilla (the norm's own one-line
summary), never the full text, whose considerandos cite the Constitution's
family and child articles in every norm on any subject (the Canadian
lesson, tools/ca_courts.py). taxonomy-es with Peru's country tag.

SHOWN: ordenanzas, acuerdos and decretos regionales on our ground or
watched (config/watchlist-pe.yaml, section `regional`, keyed by norm_key).
Resoluciones (staff, transfers, mining concessions) are stored and never
shown.

ONE WRITER AT A TIME on data/parl-monitor.db. Exit 3: stored what it could
and recorded gaps. --budget-seconds stops the gob.pe pass early (a gap).
"""

from __future__ import annotations

import argparse
import datetime
import html as htmllib
import json
import os
import re
import sys
import time
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from src import db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "pe-regions"
GAZETTE_HOST = "diariooficial.elperuano.pe"
GAZETTE_FILTER = "https://diariooficial.elperuano.pe/Normas/Filtro"
GOBPE_HOST = "www.gob.pe"
GOBPE = "https://www.gob.pe/institucion/{0}/normas-legales/tipos/{1}"
GOBPE_ROOT = "https://www.gob.pe"
GAZETTE_DELAY_S = 5.0
GOBPE_DELAY_S = 3.0
LOOKBACK_DAYS = 14
REGIONS = os.path.join(ROOT, "config", "pe-regions.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-pe.yaml")
TABLE = "pe_regional_norms"
SHOWN = ("ordenanza", "acuerdo", "decreto")
SUMMARY_CHARS = 2000


# --- regions ------------------------------------------------------------------------

def fold(text):
    """Upper case, accents off, spaces squeezed: 'Junín' -> 'JUNIN'."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().upper()


def load_regions(path=REGIONS):
    with open(path, encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("regions", [])


def gazette_index(regions):
    """{folded heading: region key}."""
    out = {}
    for r in regions:
        for h in r.get("gazette") or []:
            out[fold(h)] = r["key"]
    return out


def region_of(heading, index):
    """The region key for a gazette heading, or None (a ministry, a
    district municipality). 'MUNICIPALIDAD METROPOLITANA DE LIMA <br />
    Publicación Digital' is Lima Metropolitana."""
    return index.get(fold(heading_name(heading)))


def heading_name(heading):
    """The issuer's name from an <h4>, the escaped '<br />Publicación
    Digital' tail dropped."""
    h = htmllib.unescape(heading or "")
    return flat(re.split(r"<br\s*/?>", h, flags=re.I)[0])


# --- numbers, kinds and keys ---------------------------------------------------------

KIND_WORDS = (
    ("ordenanza", re.compile(r"^ORDENANZA")),
    ("acuerdo", re.compile(r"^ACUERDO")),
    ("decreto", re.compile(r"^DECRETO")),
    ("resolucion", re.compile(r"^RESOLUCION")),
)


def kind_of(title):
    t = fold(title)
    for kind, pat in KIND_WORDS:
        if pat.search(t):
            return kind
    return "otro"


def number_of(title):
    """The printed number after 'N°': 'ORDENANZA  N° 000013-2026-GR.LAMB/CR
    [516296499 - 11]' -> '000013-2026-GR.LAMB/CR'."""
    t = htmllib.unescape(title or "")
    m = re.search(r"N\s*[.°º]+\s*(.+)$", t)
    num = m.group(1) if m else t
    num = re.sub(r"\s*\[[^\]]*\]\s*$", "", num)
    return re.sub(r"\s+", " ", num).strip()


def reduced(number, date):
    """'<n>-<year>' from a printed number: the first integer, and the first
    four-digit year after it (else the date's year). '000013-2026-GR.LAMB/CR'
    -> '13-2026'; 'O.R.0272.2025' -> '272-2025'; '562-AREQUIPA' (dated
    2026) -> '562-2026'; 'D9-2026-GR.CAJ/CR' -> '9-2026'."""
    t = number or ""
    m = re.search(r"\d+", t)
    if not m:
        return None
    n = int(m.group(0))
    rest = t[m.end():]
    y = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", rest)
    year = y.group(1) if y else (date or "")[:4]
    return "{0}-{1}".format(n, year) if year else str(n)


def norm_key(region, kind, number, date):
    r = reduced(number, date)
    return "{0}/{1}/{2}".format(region, kind, r) if r else None


def flat(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    text = htmllib.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def dmy(text):
    """'10/09/2026' (day first, as the gazette prints it) -> '2026-09-10'."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


# --- El Peruano -------------------------------------------------------------------------

ARTICLE = re.compile(r'<article class="edicionesoficiales_articulos(?:_dig)?">(.*?)</article>', re.S)


def parse_gazette(page_html, index):
    """Rows for the regional governments' and Lima Metropolitana's norms in
    one Normas/Filtro reply. Other issuers are skipped."""
    out = []
    for a in ARTICLE.findall(page_html or ""):
        head = re.search(r"<h4>(.*?)</h4>", a, re.S)
        if not head:
            continue
        region = region_of(head.group(1), index)
        if not region:
            continue
        link = re.search(r'<h5>\s*<a href="([^"]+)">(.*?)</a>\s*</h5>', a, re.S)
        if not link:
            continue
        title = flat(link.group(2))
        date = dmy((re.search(r"Fecha:\s*([0-9/]+)", a) or [None, ""])[1])
        paras = [flat(p) for p in re.findall(r"<p>(.*?)</p>", a, re.S)]
        summary = next((p for p in reversed(paras)
                        if re.search(r"\w", p) and not p.startswith("Fecha:")), "")
        pdf = re.search(r'href="([^"]+/pdf)"', a)
        kind = kind_of(title)
        number = number_of(title)
        key = norm_key(region, kind, number, date)
        if not key:
            continue
        out.append({"norm_key": key, "region": region,
                    "body": heading_name(head.group(1)),
                    "kind": kind, "number": number, "date": date,
                    "title": re.sub(r"\s*\[[^\]]*\]\s*$", "", title), "summary": summary,
                    "url": link.group(1), "pdf_url": pdf.group(1) if pdf else None,
                    "source": "elperuano"})
    return out


def gazette_fields(since, until):
    """The Filtro form, day first, as the page's own form sends it."""
    f = lambda d: d.strftime("%d/%m/%Y")
    return {"cddesde": f(since), "cdhasta": f(until), "btnBuscar": "Filtrar", "tipo": ""}


def gazette_url(today):
    # The page's own form action carries today's date, month first.
    return "{0}?dateparam={1}%2F{2}%2F{3}%2000%3A00%3A00".format(
        GAZETTE_FILTER, "%02d" % today.month, "%02d" % today.day, today.year)


# --- gob.pe -------------------------------------------------------------------------------

GOBPE_ITEM = re.compile(r'<li class="hover:bg-gray-70 relative">(.*?)</li>', re.S)
GOBPE_KIND = {"ordenanza": "ordenanza", "acuerdo": "acuerdo"}


def parse_gobpe(page_html, region, type_slug):
    """Rows from one gob.pe norm-type page. The kind comes from the type
    page read ('40-ordenanza-regional' -> ordenanza), not the item title."""
    kind = "ordenanza" if "ordenanza" in type_slug else "acuerdo" if "acuerdo" in type_slug \
        else kind_of(type_slug)
    out = []
    for li in GOBPE_ITEM.findall(page_html or ""):
        link = re.search(r'aria-labelledby="(p-filter-item-\d+)" href="([^"]+)">(.*?)</a>', li, re.S)
        if not link:
            continue
        title = flat(link.group(3))
        summ = re.search(r'id="{0}">(.*?)</div>'.format(link.group(1)), li, re.S)
        when = re.search(r'<time[^>]*datetime="(\d{4}-\d\d-\d\d)', li)
        pdf = re.search(r'href="(https://cdn\.www\.gob\.pe/uploads/document/file/[^"]+)"', li)
        date = when.group(1) if when else None
        number = number_of(title)
        key = norm_key(region, kind, number, date)
        if not key:
            continue
        href = link.group(2)
        out.append({"norm_key": key, "region": region, "body": None, "kind": kind,
                    "number": number, "date": date, "title": title,
                    "summary": flat(summ.group(1)) if summ else "",
                    "url": href if href.startswith("http") else GOBPE_ROOT + href,
                    "pdf_url": pdf.group(1) if pdf else None, "source": "gob.pe"})
    return out


# --- classification and the store --------------------------------------------------------

def load_taxonomy(path=None):
    from src import filter as filt
    path = path or os.path.join(ROOT, "config", "taxonomy-es.yaml")
    if not os.path.exists(path):
        return None
    return filt.load_taxonomy(path, country="pe")


def load_watch(path=WATCHLIST):
    """{norm_key: areas} from the `regional` section of watchlist-pe."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    sect = raw.get("regional") or {}
    return {str(k): list((v or {}).get("areas") or []) for k, v in sect.items()}


def classify(tax, watch, key, title, summary):
    """(areas, matched_terms, tier) over the heading and the sumilla, plus
    the watchlist's areas by key."""
    areas, terms, tier = [], [], None
    if tax is not None:
        from src import filter as filt
        res = filt.filter_item(tax, filt.Watchlist(entities=[], bill_titles=[], act_shorts=[]),
                               title or "", summary or "")
        areas, terms, tier = sorted(set(res.issue_areas or [])), list(res.matched_terms or []), res.tier
    if key in watch:
        areas = sorted(set(areas) | set(watch[key]))
        terms = terms + ["watch:" + key]
        tier = 1
    return areas, terms, tier


def clip(text, n=SUMMARY_CHARS):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rstrip()


def upsert(conn, row, tax, watch, today):
    """Insert or merge one norm. Returns (new, areas). The gazette's date,
    URL and heading win; gob.pe fills what the gazette lacks (a PDF, a
    longer sumilla) and adds itself to `source`."""
    old = conn.execute("SELECT * FROM {0} WHERE norm_key=?".format(TABLE),
                       (row["norm_key"],)).fetchone()
    if old is not None:
        old = dict(zip([d[0] for d in conn.execute(
            "SELECT * FROM {0} LIMIT 0".format(TABLE)).description], old))
        gaz = row["source"] == "elperuano"
        srcs = set((old["source"] or "").split("+")) | {row["source"]}
        merged = {
            "body": row["body"] or old["body"],
            "number": row["number"] if gaz else (old["number"] or row["number"]),
            "date": row["date"] if gaz and row["date"] else (old["date"] or row["date"]),
            "title": row["title"] if gaz else (old["title"] or row["title"]),
            "summary": max([old["summary"] or "", row["summary"] or ""], key=len),
            "url": row["url"] if gaz else (old["url"] or row["url"]),
            "pdf_url": old["pdf_url"] if (old["pdf_url"] and not gaz) else (row["pdf_url"] or old["pdf_url"]),
            "source": "+".join(s for s in ("elperuano", "gob.pe") if s in srcs),
        }
    else:
        merged = {k: row[k] for k in ("body", "number", "date", "title", "summary", "url",
                                      "pdf_url", "source")}
    areas, terms, tier = classify(tax, watch, row["norm_key"], merged["title"], merged["summary"])
    conn.execute(
        "INSERT INTO {0} (norm_key, region, body, kind, number, date, title, summary, url, "
        "pdf_url, source, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(norm_key) DO UPDATE SET "
        "body=excluded.body, number=excluded.number, date=excluded.date, title=excluded.title, "
        "summary=excluded.summary, url=excluded.url, pdf_url=excluded.pdf_url, "
        "source=excluded.source, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen".format(TABLE),
        (row["norm_key"], row["region"], merged["body"], row["kind"], merged["number"],
         merged["date"], merged["title"], clip(merged["summary"]) or None, merged["url"],
         merged["pdf_url"], merged["source"], json.dumps(areas),
         json.dumps(terms, ensure_ascii=False), tier, today, today))
    return old is None, areas


def reclassify(conn, tax, watch):
    n = 0
    for key, title, summary in conn.execute(
            "SELECT norm_key, title, summary FROM {0}".format(TABLE)).fetchall():
        areas, terms, tier = classify(tax, watch, key, title, summary)
        conn.execute("UPDATE {0} SET areas=?, matched_terms=?, tier=? WHERE norm_key=?".format(TABLE),
                     (json.dumps(areas), json.dumps(terms, ensure_ascii=False), tier, key))
        n += 1
    conn.commit()
    return n


def visible(areas):
    return [a for a in areas if a != 11]


# --- the pull ------------------------------------------------------------------------------

def pull_gazette(conn, client, today, since, tax, watch, index, log=print):
    """One Filtro request for (since, today]. Returns (read, new, ours, gaps)."""
    client.set_host_throttle(GAZETTE_HOST, GAZETTE_DELAY_S)
    url = gazette_url(today)
    try:
        page = client.post_form(url, gazette_fields(since, today), FEED,
                                "gazette-{0}-{1}".format(since.isoformat(), today.isoformat()),
                                timeout=120, archive=True)
    except FetchError as exc:
        db.record_gap(conn, FEED, "El Peruano Normas Legales unreadable for {0} to {1}: {2}".format(
            since, today, str(exc)[:120]), today.isoformat())
        conn.commit()
        return 0, 0, 0, 1
    if "edicionesoficiales_articulos" not in page:
        db.record_gap(conn, FEED, "El Peruano Normas Legales returned no norms for {0} to {1}; "
                                  "its markup may have changed".format(since, today), today.isoformat())
        conn.commit()
        return 0, 0, 0, 1
    read = new = ours = 0
    for row in parse_gazette(page, index):
        read += 1
        is_new, areas = upsert(conn, row, tax, watch, today.isoformat())
        new += is_new
        if visible(areas) and row["kind"] in SHOWN:
            ours += 1
            log("  [regional] {0} {1}: {2}".format(row["norm_key"], visible(areas),
                                                   (row["summary"] or row["title"])[:80]))
    conn.commit()
    return read, new, ours, 0


def pull_gobpe(conn, client, today, tax, watch, regions, deadline=None, log=print):
    """The first page of each region's council-act type pages. Returns
    (read, new, ours, gaps)."""
    client.set_host_throttle(GOBPE_HOST, GOBPE_DELAY_S)
    read = new = ours = gaps = 0
    for r in regions:
        for t in r.get("types") or []:
            if deadline is not None and time.monotonic() > deadline:
                db.record_gap(conn, FEED, "gob.pe pass stopped at {0} {1}: out of budget; the "
                                          "next run reads the rest".format(r["key"], t),
                              today.isoformat())
                conn.commit()
                return read, new, ours, gaps + 1
            url = GOBPE.format(r["gobpe"], t)
            try:
                page = client.get_text(url, FEED, "gobpe-{0}-{1}".format(r["gobpe"], t))
            except FetchError as exc:
                gaps += 1
                db.record_gap(conn, FEED, "gob.pe {0} {1} unreadable: {2}".format(
                    r["gobpe"], t, str(exc)[:100]), today.isoformat())
                continue
            for row in parse_gobpe(page, r["key"], t):
                read += 1
                is_new, areas = upsert(conn, row, tax, watch, today.isoformat())
                new += is_new
                if is_new and visible(areas):
                    ours += 1
                    log("  [regional] {0} {1}: {2}".format(row["norm_key"], visible(areas),
                                                           (row["summary"] or row["title"])[:80]))
        conn.commit()
    return read, new, ours, gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--since", help="ISO date: read the gazette from this day (default: "
                                    "{0} days back)".format(LOOKBACK_DAYS))
    ap.add_argument("--no-gobpe", action="store_true", help="the gazette only")
    ap.add_argument("--budget-seconds", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args(argv)
    started = time.monotonic()
    today = datetime.date.today()
    tax = load_taxonomy()
    watch = load_watch()
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    if args.reclassify:
        print("pe-regions: {0} norm(s) reclassified".format(reclassify(conn, tax, watch)))
        return 0
    regions = load_regions()
    since = (datetime.date.fromisoformat(args.since) if args.since
             else today - datetime.timedelta(days=LOOKBACK_DAYS))
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0)
    read, new, ours, gaps = pull_gazette(conn, client, today, since, tax, watch,
                                         gazette_index(regions))
    print("pe-regions: El Peruano {0} to {1}: {2} regional norm(s), {3} new, {4} shown on our "
          "ground.".format(since, today, read, new, ours))
    if not args.no_gobpe:
        deadline = started + args.budget_seconds if args.budget_seconds else None
        r2, n2, o2, g2 = pull_gobpe(conn, client, today, tax, watch, regions, deadline)
        gaps += g2
        print("pe-regions: gob.pe {0} listing row(s), {1} new, {2} new on our ground.".format(
            r2, n2, o2))
    if args.dry_run:
        print("pe-regions: dry run, nothing stored.")
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
