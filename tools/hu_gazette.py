#!/usr/bin/env python3
"""Hungary, phase 0: the Magyar Közlöny (official gazette), contents by issue.

    python3 tools/hu_gazette.py                    # new issues since the last run
    python3 tools/hu_gazette.py --since 2026-05-09 # from a date (the first run's default)
    python3 tools/hu_gazette.py --reclassify       # offline, after a taxonomy-hu or
                                                   # watchlist-hu change

Chris, 10 October 2026 (HU6, "build now"; docs/hungary-scope.md, "Phase 0").
The Országgyűlés's own site answers us with a CAPTCHA, which is never solved
or worked around, so until the W-API token arrives (HU1) Hungary is watched
through what became law: every Act, resolution of the Országgyűlés,
government and ministerial decree, Constitutional Court (AB) decision and
presidential (KE) decision, as the gazette's contents page lists them.

THE SOURCE, MEASURED 9 AND 10 OCTOBER 2026 (from the laptop, CitizenGO UA):
  * https://magyarkozlony.hu/robots.txt is "Disallow:" (empty): nothing is
    disallowed. No key, no login, no challenge.
  * The RSS feed https://magyarkozlony.hu/feed holds the newest 100 issues of
    all the official journals, each with `mag:type` ("Magyar Közlöny",
    "Hivatalos Értesítő", "Indokolások Tára"), `mag:year`, `mag:serial` and
    the PDF as its enclosure. 55 of the 100 are Magyar Közlöny issues, about
    eleven weeks; only those are read.
  * The front page lists every journal's issues, newest first, ten a page
    (https://magyarkozlony.hu?page=N), with the same name, date and PDF link.
    The first run walks it back to the start of the term (9 May 2026), past
    the feed's reach; later runs need the feed alone.
  * Each issue is one PDF (InDesign; 25 KB to 2 MB a day), with a clean text
    layer and the contents (Tartalomjegyzék) on page 1, running on to the
    next pages in a long issue. Read with the stdlib reader src/sv_pdf.py.
One request every 2 seconds (src/http.py, the repo's UA). Every listing,
the feed and every PDF are archived to data/raw/<date>/hu-gazette_*.

WHAT IS KEPT. Every contents entry, on our ground or not (a few hundred rows
a month), keyed on its official designation (src/hu_store.py), classified
with config/taxonomy-hu.yaml (accent folding, X3) and the watchlist
config/watchlist-hu.yaml. HU4: an amendment to the Fundamental Law is
stored with rule 'HU4' and goes to triage whatever its words.

Exit codes: 0 clean, 3 stored with gaps (an issue whose contents could not be
read, a listing that failed): the store is still published. Separation
guarantee: writes hu_gazette_* and the shared gaps table only.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, hu_store, sv_pdf  # noqa: E402

BASE = "https://magyarkozlony.hu"
FEED_URL = BASE + "/feed"
LIST_URL = BASE + "?page={0}"
FEED = "hu-gazette"
JOURNAL = "Magyar Közlöny"
TERM_START = "2026-05-09"        # the 43rd Országgyűlés's inaugural sitting
THROTTLE_S = 2.0
MAX_LIST_PAGES = 40              # ten issues a page; the term so far is about 30 pages
MAX_CONTENTS_PAGES = 8           # contents pages read before giving up on an issue
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-hu.yaml")

ISSUE_NAME = re.compile(r"^Magyar Közlöny (\d{4})\. évi (\d+)\. szám$")


# --- the feed and the listing -----------------------------------------------

def _cdata(text):
    text = text or ""
    m = re.search(r"<!\[CDATA\[(.*?)\]\]>", text, re.S)
    return html.unescape(m.group(1) if m else text).strip()


def _rfc822_date(text):
    """'Thu, 08 Oct 2026 22:52:15 +0200' -> '2026-10-08' (the local date)."""
    try:
        return datetime.datetime.strptime(text.strip(), "%a, %d %b %Y %H:%M:%S %z").date().isoformat()
    except (ValueError, AttributeError):
        return None


def parse_feed(xml):
    """[issue] from the RSS: Magyar Közlöny issues only (mag:type), newest
    first. An issue is {year, serial, date, url, pdf_url}."""
    out = []
    for body in re.findall(r"<item>(.*?)</item>", xml or "", re.S):
        kind = re.search(r"<mag:type>(.*?)</mag:type>", body, re.S)
        if not kind or _cdata(kind.group(1)) != JOURNAL:
            continue
        year = re.search(r"<mag:year>\s*(\d{4})\s*</mag:year>", body)
        serial = re.search(r"<mag:serial>\s*(\d+)\s*</mag:serial>", body)
        enc = re.search(r'<enclosure[^>]*url="([^"]+)"', body)
        link = re.search(r"<link>(.*?)</link>", body, re.S)
        date = re.search(r"<pubDate>(.*?)</pubDate>", body, re.S)
        if not (year and serial and enc):
            continue
        out.append({"year": int(year.group(1)), "serial": int(serial.group(1)),
                    "date": _rfc822_date(date.group(1)) if date else None,
                    "url": _cdata(link.group(1)) if link else None,
                    "pdf_url": html.unescape(enc.group(1))})
    return out


def parse_listing(page_html):
    """[issue] from a front-page listing (?page=N): Magyar Közlöny rows only,
    in page order (newest first)."""
    out = []
    # Each row is a schema.org Newspaper item (split on the type's name, not
    # its URL: the markup's identifier is not a source we fetch).
    for block in re.split(r'itemtype="[^"]*/Newspaper"', page_html or "")[1:]:
        name = re.search(r'<b itemprop="name"\s*>([^<]*)</b>', block)
        m = ISSUE_NAME.match(html.unescape(name.group(1)).strip()) if name else None
        if not m:
            continue
        date = re.search(r'itemprop="datePublished" content="(\d{4}-\d{2}-\d{2})"', block)
        pdf = re.search(r'href="(https://magyarkozlony\.hu/hivatalos-lapok/[^"]+/letoltes)"', block)
        url = re.search(r'itemprop="url" content="([^"]+)"', block)
        if not pdf:
            continue
        out.append({"year": int(m.group(1)), "serial": int(m.group(2)),
                    "date": date.group(1) if date else None,
                    "url": url.group(1) if url else None, "pdf_url": pdf.group(1)})
    return out


# --- the contents page --------------------------------------------------------

# An entry starts with its designation in the left column, then a tab, then
# the title (which wraps onto lines of its own) and, on its last line, a tab
# and the page number. A wrapped title line can itself cite a designation
# ("... szóló 9/2024. (VI. 28.) HM rendelet módosításáról\t5009"), which is
# why a designation counts only when it fills the whole left cell AND a title
# follows it.
DESIGNATION = re.compile(
    r"^(?:\d{4}\. évi [IVXLCDM]+\. törvény"
    r"|\d+/\d{4}\. \([IVX]+\. ?\d{1,2}\.\) [^\t]{1,40}?"
    r"(?:rendelet|rendelete|határozat|határozata|végzés|végzése|utasítás|ítélet|közlemény)"
    r"|[A-ZÁÉÍÓÖŐÚÜŰ][^\t]{0,40}?\d{4}/\d+\. számú (?:határozat|végzés|ítélet)"
    r"|Magyarország Alaptörvényének [^\t]+)$")
PAGE_AT_END = re.compile(r"\t\s*(\d[\d ]{0,6})\s*$")
# Some issues drop the tab before the page number ("... módosításáról 4758").
# A bare trailing number is a page only after a letter or a bracket: a year
# in a title is printed with its full stop ("2026."), a date in brackets too.
BARE_PAGE_AT_END = re.compile(r"(?<=[^\W\d_]|\)) (\d{1,5})\s*$")
# The title's first letter often lands in the left cell, a kerning gap short
# of the tab: "76/2026. (V. 12.) KE határozat M<tab>iniszterek kinevezéséről".
STRAY_INITIAL = re.compile(r"^(.*\S) ([A-ZÁÉÍÓÖŐÚÜŰ])$")
# The consolidated text after an amendment: "Magyarország Alaptörvénye
# (egységes szerkezetben)". Not an amendment, so not HU4; the same heading
# recurs, so the collector keys it on the issue.
CONSOLIDATED = "Magyarország Alaptörvénye (egységes szerkezetben)"
RUNNING_HEAD = re.compile(r"MAGYAR KÖZLÖNY\s*•\s*\d{4}\. évi \d+\. szám")


def _page_number(text):
    try:
        return int(re.sub(r"\D", "", text))
    except ValueError:
        return None


def contents_entries(pages):
    """[(designation, title, page)] from an issue's pages (sv_pdf.pdf_lines).

    The contents fill page 1 under the masthead (the "Tartalomjegyzék"
    heading itself is drawn as a form and does not come through as text) and
    end at the first page that carries the gazette's running head
    ("5004 MAGYAR KÖZLÖNY • 2026. évi 148. szám"), which the contents pages
    never do. Lines before the first designation (the masthead, the date)
    are skipped. Returns [] when no entry is found (an unreadable PDF): the
    caller records the issue as a gap."""
    lines = []
    for n, page in enumerate(pages[:MAX_CONTENTS_PAGES]):
        if n and any(RUNNING_HEAD.search(ln) for ln in page[:3]):
            break
        lines.extend(page)
    out = []
    cur = None
    for ln in lines:
        ln = hu_store.norm(ln.replace("\t", "\x00")).replace("\x00", "\t")
        raw = ln.split("\t")
        head = raw[0].strip()
        rest = "\t".join(raw[1:])
        stray = STRAY_INITIAL.match(head)
        if stray and DESIGNATION.match(stray.group(1)) and rest:
            head, rest = stray.group(1), stray.group(2) + rest
        rest = rest.strip()
        starts = (DESIGNATION.match(head) and (rest and not re.fullmatch(r"[\d ]+", rest))
                  ) or head.startswith("Magyarország Alaptörvény")
        if starts:
            if cur:
                out.append(cur)
            cur = [head, "", None]
            text = rest
        elif cur is None:
            continue
        else:
            text = ln
        m = PAGE_AT_END.search(text) or BARE_PAGE_AT_END.search(text)
        if m:
            cur[2] = _page_number(m.group(1))
            text = text[:m.start()]
        text = hu_store.norm(text.replace("\t", " "))
        if text:
            cur[1] = (cur[1] + " " + text).strip()
        if cur[2] is not None:
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    got = []
    for d, t, p in out:
        d, t = hu_store.norm(d), hu_store.norm(t)
        if d == "Magyarország Alaptörvénye":
            # the consolidated text; its heading wraps oddly in some issues
            d = t = CONSOLIDATED
        elif d.startswith("Magyarország Alaptörvényének"):
            # an amendment: its "title" is the date in brackets, which is
            # also what tells one amendment's heading from another's
            d = t = hu_store.norm(d + " " + t)
        got.append((d, t, p))
    return got


# --- classification -----------------------------------------------------------

_NO_WATCH = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def load_taxonomy(path=TAXONOMY):
    return filt.load_taxonomy(path, country="hu")


# Accent folding (X3) makes a few Hungarian terms false friends: `válás*`
# (divorce) folds to "valas", which starts "választás" (election) and
# "választása" (its election of). MEASURED on the term's gazette: two of two
# `válás*` hits were elections (party funding after the general election, the
# election of lay judges), none a divorce. A term listed here stands only when
# its pattern matches the folded title; until the taxonomy carries the guard
# itself (docs/keyword-taxonomy-hu.md, for Chris), the collector applies it.
FALSE_FRIENDS = {"válás*": re.compile(r"\bvalas(?!zt)")}


def _term_areas(tax):
    """{term: {(area, tier)}} from a compiled taxonomy."""
    out = {}
    for area, tiers in tax.terms.items():
        for tier, compiled in tiers.items():
            for entry in compiled:
                out.setdefault(entry[0], set()).add((area, tier))
    return out


def classify(tax, wl, designation, title, kind):
    """(areas, terms, tier, rule, watched) for one entry, on its title alone
    (the designation names only the issuer: 'NMHH rendelet' would file every
    telecoms regulator's decree under free speech). The watchlist is applied
    by key, never by title; a watched entry takes its areas."""
    res = filt.filter_item(tax, _NO_WATCH, title or "")
    terms = list(res.matched_terms or [])
    folded = filt._fold(title or "").lower()
    dropped = [t for t in terms if t in FALSE_FRIENDS and not FALSE_FRIENDS[t].search(folded)]
    if dropped:
        terms = [t for t in terms if t not in dropped]
        by_term = _term_areas(tax)
        hits = set().union(*[by_term.get(t, set()) for t in terms]) if terms else set()
        areas = {a for a, _ in hits}
        tier = min((tr for _, tr in hits), default=None)
    else:
        areas = set(res.issue_areas or [])
        tier = res.tier
    rule = "HU4" if kind == "fundamental_law" else None
    entry = wl.get(hu_store.norm(designation))
    watched = entry is not None
    if watched:
        areas.update(int(a) for a in (entry.get("areas") or []))
        tier = tier or 2
    return sorted(areas), terms, tier, rule, watched


# --- storing --------------------------------------------------------------------

def store_entries(conn, issue, entries, tax, wl, today):
    """Classify and upsert one issue's contents entries. Returns how many
    are on our ground (areas, HU4 or watched)."""
    ikey = hu_store.issue_key(issue["year"], issue["serial"])
    ours = 0
    for designation, title, page in entries:
        if designation == CONSOLIDATED:
            designation = "{0}, Magyar Közlöny {1}".format(CONSOLIDATED, ikey)
        kind, number, issuer = hu_store.classify_designation(designation)
        areas, terms, tier, rule, watched = classify(tax, wl, designation, title, kind)
        if areas or rule or watched:
            ours += 1
        conn.execute(
            "INSERT INTO hu_gazette_entries (entry_key, issue_key, date, page, type, number, "
            "issuer, title, areas, matched_terms, tier, rule, watched, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(entry_key) DO UPDATE SET "
            "title=excluded.title, page=excluded.page, type=excluded.type, "
            "number=excluded.number, issuer=excluded.issuer, areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, tier=excluded.tier, rule=excluded.rule, "
            "watched=excluded.watched, last_seen=excluded.last_seen",
            (designation, ikey, issue["date"], page, kind, number, issuer, title,
             hu_store.dumps(areas), hu_store.dumps(terms), tier, rule, int(watched),
             today, today))
    return ours


def store_issue(conn, issue, pages, entries, today):
    ikey = hu_store.issue_key(issue["year"], issue["serial"])
    conn.execute(
        "INSERT INTO hu_gazette_issues (issue_key, year, serial, date, url, pdf_url, pages, "
        "entries, contents_ok, read_at, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(issue_key) DO UPDATE SET date=COALESCE(excluded.date, date), "
        "url=COALESCE(excluded.url, url), pdf_url=excluded.pdf_url, pages=excluded.pages, "
        "entries=excluded.entries, contents_ok=excluded.contents_ok, read_at=excluded.read_at, "
        "last_seen=excluded.last_seen",
        (ikey, issue["year"], issue["serial"], issue["date"], issue.get("url"),
         issue["pdf_url"], len(pages), len(entries), int(bool(entries)), today, today))


def reclassify(conn, tax, wl):
    """Re-derive every stored entry's areas, rule and watch flag, offline."""
    n = 0
    for key, title, kind in conn.execute(
            "SELECT entry_key, title, type FROM hu_gazette_entries").fetchall():
        kind = hu_store.classify_designation(key)[0]
        areas, terms, tier, rule, watched = classify(tax, wl, key, title, kind)
        conn.execute("UPDATE hu_gazette_entries SET type=?, areas=?, matched_terms=?, tier=?, "
                     "rule=?, watched=? WHERE entry_key=?",
                     (kind, hu_store.dumps(areas), hu_store.dumps(terms), tier, rule,
                      int(watched), key))
        n += 1
    conn.commit()
    return n


# --- collecting -----------------------------------------------------------------

def candidates(client, since, have, max_list_pages=MAX_LIST_PAGES):
    """Issues dated on or after `since`, oldest first: the feed's, then the
    front-page listing's when the feed does not reach back to `since`.
    Returns (issues, gaps)."""
    gaps = []
    found = {}
    feed = parse_feed(client.get_text(FEED_URL, FEED, "feed"))
    for it in feed:
        found[(it["year"], it["serial"])] = it
    oldest = min((it["date"] for it in feed if it["date"]), default=None)
    if oldest is None or oldest > since:
        for page in range(1, max_list_pages + 1):
            try:
                rows = parse_listing(client.get_text(LIST_URL.format(page), FEED,
                                                     "list-p{0}".format(page)))
            except Exception as exc:  # noqa: BLE001 - a failed page is a gap, not a crash
                gaps.append("listing page {0}: {1}".format(page, exc))
                break
            if not rows:
                break
            for it in rows:
                found.setdefault((it["year"], it["serial"]), it)
            if min(it["date"] or "9999" for it in rows) < since:
                break
    todo = [it for k, it in found.items() if (it["date"] or "") >= since and k not in have]
    seen = [it for k, it in found.items()]
    return sorted(todo, key=lambda i: (i["year"], i["serial"])), seen, gaps


def collect(conn, client, since, today, tax, wl, budget_s=None, clock=time.monotonic):
    """Read every unread issue since `since`. Returns a summary dict."""
    start = clock()
    have = {(r[0], r[1]) for r in conn.execute(
        "SELECT year, serial FROM hu_gazette_issues WHERE contents_ok=1")}
    todo, seen, gaps = candidates(client, since, have)
    for it in seen:
        conn.execute("UPDATE hu_gazette_issues SET last_seen=? WHERE issue_key=?",
                     (today, hu_store.issue_key(it["year"], it["serial"])))
    summary = {"issues": 0, "entries": 0, "ours": 0, "gaps": len(gaps), "left": 0}
    for g in gaps:
        db.record_gap(conn, FEED, g)
    for n, it in enumerate(todo):
        if budget_s and clock() - start > budget_s:
            summary["left"] = len(todo) - n
            db.record_gap(conn, FEED, "budget reached; {0} issue(s) left for the next run"
                          .format(summary["left"]))
            summary["gaps"] += 1
            break
        slug = "pdf-{0}-{1}".format(it["year"], it["serial"])
        try:
            data = client.get_bytes(it["pdf_url"], FEED, slug)
        except Exception as exc:  # noqa: BLE001
            db.record_gap(conn, FEED, "No. {0} of {1}: {2}".format(it["serial"], it["year"], exc))
            summary["gaps"] += 1
            continue
        pages = sv_pdf.pdf_lines(data, max_pages=MAX_CONTENTS_PAGES)
        entries = contents_entries(pages)
        if not entries:
            db.record_gap(conn, FEED, "No. {0} of {1} ({2}): contents page not read".format(
                it["serial"], it["year"], it["date"]))
            summary["gaps"] += 1
        summary["ours"] += store_entries(conn, it, entries, tax, wl, today)
        store_issue(conn, it, pages, entries, today)
        conn.commit()
        summary["issues"] += 1
        summary["entries"] += len(entries)
    conn.commit()
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--since", help="ISO date, inclusive; default: the newest stored issue "
                                    "(or the start of the term, {0}, on the first run)"
                    .format(TERM_START))
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--budget-seconds", type=int, default=0)
    args = ap.parse_args(argv)
    conn = db.connect(args.db)
    hu_store.ensure_schema(conn)
    tax = load_taxonomy()
    wl = hu_store.watchlist()
    if args.reclassify:
        print("hu-gazette: reclassified {0} entr(ies)".format(reclassify(conn, tax, wl)))
        return 0
    today = datetime.date.today().isoformat()
    newest = conn.execute("SELECT MAX(date) FROM hu_gazette_issues WHERE contents_ok=1"
                          ).fetchone()[0]
    # An issue whose contents could not be read is retried on later runs.
    failed = conn.execute("SELECT MIN(date) FROM hu_gazette_issues WHERE contents_ok=0"
                          ).fetchone()[0]
    since = args.since or min([d for d in (newest, failed) if d] or [TERM_START])
    from src.http import FetchError, HttpClient
    client = HttpClient(raw_dir=args.raw_dir, throttle=THROTTLE_S)
    try:
        s = collect(conn, client, since, today, tax, wl, args.budget_seconds or None)
    except FetchError as exc:
        conn.commit()
        db.record_gap(conn, FEED, str(exc))
        return 3
    by_type = dict(conn.execute("SELECT type, COUNT(*) FROM hu_gazette_entries GROUP BY type"
                                ).fetchall())
    on_ground = conn.execute("SELECT COUNT(*) FROM hu_gazette_entries WHERE areas != '[]' "
                             "OR rule IS NOT NULL OR watched=1").fetchone()[0]
    print("hu-gazette: {0} issue(s) read since {1}, {2} contents entr(ies), {3} on our ground; "
          "store: {4} entr(ies) ({5}), {6} on our ground".format(
              s["issues"], since, s["entries"], s["ours"], sum(by_type.values()),
              ", ".join("{0} {1}".format(v, k) for k, v in sorted(by_type.items())), on_ground))
    return 3 if s["gaps"] else 0


if __name__ == "__main__":
    sys.exit(main())
