#!/usr/bin/env python3
"""Canada Gazette: proposed regulations, made regulations and notices.

    python3 tools/ca_gazette.py                    # unread issues of the last 60 days
    python3 tools/ca_gazette.py --since 2026-01-01
    python3 tools/ca_gazette.py --part 2
    python3 tools/ca_gazette.py --db /tmp/ca.db

GROUNDWORK, phase 2 (26 September 2026). Nothing schedules this.

WHY. The Gazette is Canada's statutory-instrument layer: much of what we
campaign on moves by regulation, not bill. Part I (weekly, Saturdays) carries
government notices and PROPOSED regulations with a comment period -- the
point at which a consultation response can still change the text. Part II
(every second Wednesday) carries made regulations (SOR) and statutory
instruments (SI).

THE SOURCE. gazette.gc.ca/rss/p1-eng.xml and p2-eng.xml list ISSUES (436
and 232 back to December 2019), not items. Each issue's index page lists its
items under section (h2) and department (h3) headings, so the collector reads
the index, then:
  * a REGULATION (its own page: reg<N>, sor-dors<N>, si-tr<N>) is fetched and
    matched PER PASSAGE with its title as a passage, because a Regulatory
    Impact Analysis Statement runs to 80,000 characters of boilerplate, and
    whole-document matching would tag it with every area it brushes;
  * a NOTICE is an anchor on a page it shares with its neighbours
    (commis-eng.html#cs9). Each shared page is fetched ONCE and cut at the
    item anchors, and the notice's own text is matched per passage. This
    was title-only at first, and a title never names the organisation: the
    Canada Revenue Agency's "Revocation of registration of charities" says
    which charities only in its text -- and CRA revocations are exactly
    where the charitable-status fight would first surface. A notice whose
    anchor is not on the page falls back to its title, and says so
    (matched_on='title');
  * an EXTRA edition's feed link is the document itself, so it is one item
    (kind='extra'), read whole like a regulation; so is any other item with
    a page of its own and no anchor -- an order in council, a supplement
    (kind='document').

The RSS host answered 503 for an hour on 26 September 2026 and normally the
next. A 503 here is a gap that stops the run, never an empty week.

Every issue READ gets a ca_gazette_issues row; every item is stored, ours or
not. For a Part I proposed regulation the comment period is read from its
text ("within 30 days after the date of publication") and comment_until is
worked out, because that date is the whole point of watching Part I.

ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import email.utils
import html as htmlmod
import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ca-gazette"
RSS = "https://gazette.gc.ca/rss/p{0}-eng.xml"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")
LOOKBACK_DAYS = 60
HIDDEN_AREAS = (11,)

TAG = re.compile(r"<[^>]+>")
REGULATION = re.compile(r"/(?:reg\d+|sor-dors\d+|si-tr\d+)-eng\.html$")
REGISTRATION = re.compile(r"Registration\s+((?:SOR|SI)/\d{4}-\d+)")
COMMENT = re.compile(r"within (\d+) days after the date of publication")
# The Gazette's own index pages carry the odd typo'd anchor, found by the
# backfill to 2020: "commis-eng.html@cs7" (2020-01-25) and
# "commis-eng.htmlcs10" (2022-10-29). Read literally each is a page that does
# not exist, so the notice was a gap. Both are repaired to "#<anchor>".
BAD_ANCHOR = re.compile(r"(-eng\.html)(?:@|(?=[a-z]{2,4}\d+$))")
# An index that SAYS nothing was published is a real zero, not a parse
# failure: Part II of 15 September 2021 reads "No regulatory text was
# registered for publication in this issue."
NOTHING_PUBLISHED = re.compile(r"No regulatory text was registered for publication", re.I)
TOKEN = re.compile(r"<(h2|h3)\b[^>]*>(.*?)</\1>|<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.S)


def _clean(fragment):
    return " ".join(htmlmod.unescape(TAG.sub(" ", fragment or "")).split())


def _main(page):
    """The <main> element's inner HTML: the site chrome carries hundreds of
    links that are not Gazette items."""
    start = page.find("<main")
    end = page.find("</main>", start)
    return page[start:end] if start >= 0 and end > start else ""


def parse_rss(xml_text, part):
    """[{issue_key, part, date, title, url}] for the feed's ISSUES."""
    out = []
    for item in ET.fromstring(xml_text).findall("channel/item"):
        url = (item.findtext("link") or "").strip()
        # The issue folder names the issue, and tells an extra edition
        # ('2026-09-28-x1') from the regular one on a shared date.
        folder = re.search(r"/rp-pr/p\d/\d{4}/([^/]+)/html/", url)
        if not folder:
            continue            # the quarterly index and other non-issue entries
        try:
            when = email.utils.parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
        except (TypeError, ValueError):
            when = folder.group(1)[:10]
        out.append({"issue_key": "p{0}-{1}".format(part, folder.group(1)), "part": part,
                    "date": when, "title": (item.findtext("title") or "").strip(), "url": url})
    return out


def parse_index(page, base_url):
    """[{url, title, section, department, kind}] in the index's own order."""
    main = _main(page)
    section = department = None
    headings, items, seen = set(), [], set()
    for h, htext, href, atext in TOKEN.findall(main):
        if h == "h2":
            section, department = _clean(htext) or None, None
            headings.add(section)
            continue
        if h == "h3":
            department = _clean(htext) or None
            continue
        title = _clean(atext)
        if not href or href.startswith("#") or not title:
            continue            # footnotes and empty anchors
        href = BAD_ANCHOR.sub(r"\1#", href)
        if title in headings:
            continue            # the link to a whole section's page, not an item
        url = urllib.parse.urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        items.append({"url": url, "title": title, "section": section,
                      "department": department,
                      "kind": ("regulation" if REGULATION.search(url.split("#")[0])
                               else "notice" if "#" in url
                               else "document")})     # an order or supplement on its own page
    return items


def read_regulation(page):
    """(body text, registration, comment_days) from a regulation's page."""
    text = _clean(_main(page))
    reg = REGISTRATION.search(text)
    days = COMMENT.search(text)
    return text, (reg.group(1) if reg else None), (int(days.group(1)) if days else None)


def notice_texts(page, anchors):
    """{anchor: text} for the notices on one shared page, each cut from its
    own id= to the next item's. Anchors not found on the page are absent."""
    found = sorted((m.start(), m.group(1)) for m in re.finditer(r'\bid="([^"]+)"', page)
                   if m.group(1) in anchors)
    out = {}
    for (start, anchor), (end, _) in zip(found, found[1:] + [(page.find("</main>", found[-1][0])
                                                              if found else len(page), None)]):
        chunk = page[start:end if end and end > start else len(page)]
        # The chunk opens mid-tag ('id="cs9">'); drop the rest of that tag.
        out[anchor] = _clean(chunk[chunk.find(">") + 1:])
    return out


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def read_issue(conn, client, issue, tax, wl, today, log=print):
    """Store one issue's items. Returns (items, ours, gaps)."""
    index = client.get_text(issue["url"], FEED, "index-" + issue["issue_key"], archive=False)
    pages = {}
    if issue["url"].endswith("/index-eng.html"):
        items = parse_index(index, issue["url"])
    else:
        # An EXTRA edition's feed link is the document itself
        # (2026-07-31-x6/html/extra6-eng.html), not an index: the first
        # version of this collector read it as an index, found no items, and
        # (rightly) called two extra editions gaps. It is one item, read whole.
        items = [{"url": issue["url"], "title": issue["title"], "section": "Extra edition",
                  "department": None, "kind": "extra"}]
        pages[issue["url"]] = index
    if not items and NOTHING_PUBLISHED.search(_clean(_main(index))):
        conn.execute("INSERT OR REPLACE INTO ca_gazette_issues (issue_key, part, date, "
                     "title, url, items, ours, read_at) VALUES (?,?,?,?,?,?,?,?)",
                     (issue["issue_key"], issue["part"], issue["date"], issue["title"],
                      issue["url"], 0, 0, today))
        conn.commit()
        log("  {0}: the index says nothing was published".format(issue["issue_key"]))
        return 0, 0, 0
    if not items:
        _gap(conn, today, "{0}: index listed no items (markup changed?)".format(issue["issue_key"]))
        log("  [gap] {0}: the index parsed to nothing".format(issue["issue_key"]))
        return 0, 0, 1
    ours = gaps = 0
    # Fetch each shared notice page once and cut it at its items' anchors.
    notices = {}
    for it in items:
        if it["kind"] == "notice" and "#" in it["url"]:
            base, anchor = it["url"].split("#", 1)
            notices.setdefault(base, set()).add(anchor)
    texts = {}
    for base, anchors in notices.items():
        try:
            page = client.get_text(base, FEED, "notices-" + os.path.basename(base), archive=False)
        except FetchError as exc:
            _gap(conn, today, "{0}: {1}".format(base, exc))
            log("  [gap] {0}: {1}".format(os.path.basename(base), str(exc)[:60]))
            gaps += 1
            continue
        for anchor, text in notice_texts(page, anchors).items():
            texts[base + "#" + anchor] = text
    for it in items:
        registration = days = until = excerpt = text = None
        matched_on = "body"
        if it["kind"] in ("regulation", "extra", "document"):
            try:
                body, registration, days = read_regulation(
                    pages.get(it["url"]) or
                    client.get_text(it["url"], FEED, "item-" + os.path.basename(it["url"]),
                                    archive=False))
            except FetchError as exc:
                _gap(conn, today, "{0}: {1}".format(it["url"], exc))
                log("  [gap] {0}: {1}".format(os.path.basename(it["url"]), str(exc)[:60]))
                gaps += 1
                continue
            matches = filt.match_passages(tax, wl, body, title=it["title"])
            areas, terms, excerpt = filt.aggregate_passages(matches)
            tier = (1 if any(m.result.tier == 1 for m in matches)
                    else 2 if matches else None)
            if days and issue["part"] == 1:
                until = (datetime.date.fromisoformat(issue["date"])
                         + datetime.timedelta(days=days)).isoformat()
        elif it["url"] in texts:
            text = texts[it["url"]]
            matches = filt.match_passages(tax, wl, text, title=it["title"])
            areas, terms, excerpt = filt.aggregate_passages(matches)
            tier = (1 if any(m.result.tier == 1 for m in matches)
                    else 2 if matches else None)
        else:
            matched_on = "title"
            res = filt.filter_item(tax, wl, it["title"], it["department"] or "")
            areas, terms, tier = res.issue_areas or [], (res.matched_terms or []) + (res.watchlist_hits or []), res.tier
        ours += on_our_ground(areas)
        conn.execute(
            "INSERT INTO ca_gazette_items (item_key, issue_key, part, date, section, "
            "department, title, url, kind, registration, comment_days, comment_until, "
            "areas, matched_terms, tier, excerpt, matched_on, text, first_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(item_key) DO UPDATE SET title=excluded.title, "
            "section=excluded.section, department=excluded.department, "
            "registration=excluded.registration, comment_days=excluded.comment_days, "
            "comment_until=excluded.comment_until, areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, tier=excluded.tier, excerpt=excluded.excerpt, "
            "matched_on=excluded.matched_on, text=excluded.text",
            (it["url"], issue["issue_key"], issue["part"], issue["date"], it["section"],
             it["department"], it["title"], it["url"], it["kind"], registration, days, until,
             json.dumps(areas), json.dumps(terms), tier, excerpt, matched_on, text, today))
    if not gaps:
        # An issue with a failed item is NOT marked read, so the next run
        # tries it again whole rather than leaving a hole behind a tick.
        conn.execute("INSERT OR REPLACE INTO ca_gazette_issues (issue_key, part, date, "
                     "title, url, items, ours, read_at) VALUES (?,?,?,?,?,?,?,?)",
                     (issue["issue_key"], issue["part"], issue["date"], issue["title"],
                      issue["url"], len(items), ours, today))
    conn.commit()
    return len(items), ours, gaps


def pull(conn, client, today, parts=(1, 2), since=None, tax=None, wl=None, log=print,
         limit=None, budget=None):
    """Read every unread issue since `since`, oldest first. Returns (issues, items, ours, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    since = since or (datetime.date.fromisoformat(today)
                      - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    done = {r[0] for r in conn.execute("SELECT issue_key FROM ca_gazette_issues")}
    todo = []
    for part in parts:
        try:
            feed = client.get_text(RSS.format(part), FEED, "rss-p{0}".format(part), archive=False)
            todo += [i for i in parse_rss(feed, part)
                     if i["date"] >= since and i["issue_key"] not in done]
        except (FetchError, ET.ParseError) as exc:
            _gap(conn, today, "rss p{0}: {1}".format(part, exc))
            conn.commit()
            log("  [gap] Part {0} feed: {1}".format(part, str(exc)[:70]))
            return 0, 0, 0, 1
    issues = items = ours = gaps = 0
    for issue in sorted(todo, key=lambda i: (i["date"], i["issue_key"])):
        if limit is not None and issues >= limit:
            log("  issue cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("Gazette issues", issues))
            break
        try:
            n, o, g = read_issue(conn, client, issue, tax, wl, today, log)
        except FetchError as exc:
            _gap(conn, today, "{0}: {1}".format(issue["issue_key"], exc))
            conn.commit()
            log("  [gap] {0}: {1}".format(issue["issue_key"], str(exc)[:70]))
            gaps += 1
            continue
        log("  {0}: {1} item(s), {2} on our ground{3}".format(
            issue["issue_key"], n, o, ", {0} gap(s)".format(g) if g else ""))
        issues, items, ours, gaps = issues + 1, items + n, ours + o, gaps + g
    return issues, items, ours, gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--part", type=int, choices=(1, 2), help="one Part only")
    ap.add_argument("--since", help="ISO date; default {0} days back".format(LOOKBACK_DAYS))
    ap.add_argument("--limit", type=int, help="issues per run")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    issues, items, ours, gaps = pull(conn, client, today,
                                     parts=(args.part,) if args.part else (1, 2),
                                     since=args.since, limit=args.limit,
                                     budget=drain.Budget(args.budget_seconds))
    print("ca-gazette: {0} issue(s) read, {1} item(s), {2} on our ground, {3} gap(s).".format(
        issues, items, ours, gaps))
    open_now = conn.execute(
        "SELECT COUNT(*) FROM ca_gazette_items WHERE comment_until >= ? "
        "AND areas NOT IN ('[]','[11]')", (today,)).fetchone()[0]
    print("  {0} proposed regulation(s) on our ground still open for comment.".format(open_now))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
