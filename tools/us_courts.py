#!/usr/bin/env python3
"""The Supreme Court of the United States: opinions, and certiorari grants.

    python3 tools/us_courts.py                       # this term and the last (from OT2024 when empty)
    python3 tools/us_courts.py --terms 24,25,26      # named terms
    python3 tools/us_courts.py --reclassify          # re-derive areas, offline
    python3 tools/us_courts.py --db /tmp/us.db       # anywhere but the store

Christopher, 9 October 2026: yes to a Supreme Court section in the US
edition. Dobbs, Skrmetti, 303 Creative, Chiles v. Salazar: on our ground the
Court has moved the law more than Congress has.

THE SOURCES (supremecourt.gov, probed 9 October 2026, keyless, honest UA):
  * opinions/slipopinion/<term>: every opinion of an October Term, one row
    each, with the Court's own one-sentence HOLDING in the link's title
    attribute. The case name alone matches nothing (party names), so the
    holding is what is classified, with the name as the title passage.
    Re-read whole every run, so last_seen moves weekly in term time.
  * orders/ordersofthecourt/<term>: the order lists and miscellaneous
    orders, one PDF each. Every PDF is read ONCE (us_court_orders) and the
    plenary CERTIORARI GRANTS are taken out of it: the cases the Court will
    decide, a term ahead. Grant-vacate-remand orders ("granted ... vacated
    ... remanded") are not plenary grants and are skipped.
  * docket/docketfiles/html/public/<docket>.html for each grant: the full
    caption, and the link to the QUESTIONS PRESENTED (a PDF), which is what
    a grant is classified on. A grant whose question cannot be read keeps
    its caption, and the miss is a gap.

ROBOTS (read 9 October 2026): Crawl-delay 1; /images/, /rss/ and /cdn/
are disallowed, and none of them is used (the docket JSON lives under
/RSS/ and is left alone for that reason). Requests go one a second.

BOT DETECTION is never worked around. A refused or challenged fetch stops
that part of the run with one gap; nothing unread is marked read, so the
next run carries on.

Separation guarantee: writes us_court_cases, us_court_orders, the shared
gaps table and its own source_runs heartbeat only. ONE WRITER AT A TIME.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import io
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "us-courts"
HEARTBEAT = "US Supreme Court"
BASE = "https://www.supremecourt.gov"
SLIP = BASE + "/opinions/slipopinion/{term}"
ORDERS = BASE + "/orders/ordersofthecourt/{term}"
DOCKET = BASE + "/docket/docketfiles/html/public/{docket}.html"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
THROTTLE_S = 1.0          # robots.txt: Crawl-delay: 1
ROBOTS_DISALLOW = ("/images/", "/rss/", "/cdn/")
ORDER_KINDS = ("Order List", "Miscellaneous Order")
HIDDEN_AREAS = (11,)
QP_CHARS = 3000
# The first run (an empty table) reads from October Term 2024, so the edition
# starts with Skrmetti and Mahmoud v. Taylor on the record; later runs read
# the current term and the last.
FIRST_TERM = "24"


def current_term(today):
    """October Term, two digits: OT2026 opens on the first Monday of October."""
    d = datetime.date.fromisoformat(today) if isinstance(today, str) else today
    return "{0:02d}".format((d.year if d.month >= 10 else d.year - 1) % 100)


def allowed(url):
    path = urllib.parse.urlparse(url).path.lower()
    return not any(path.startswith(p) for p in ROBOTS_DISALLOW)


def _clean(fragment):
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split()) or None


def us_date(text):
    """'9/25/26' -> '2026-09-25'."""
    try:
        return datetime.datetime.strptime((text or "").strip(), "%m/%d/%y").date().isoformat()
    except ValueError:
        return None


# --- opinions ----------------------------------------------------------------

_ROW = re.compile(
    r"<tr>\s*<td[^>]*>\s*(\d+)\s*</td>\s*<td[^>]*>\s*([\d/]+)\s*</td>\s*"
    r"<td[^>]*>\s*([^<]*?)\s*</td>\s*<td[^>]*>\s*<a\s+([^>]*)>(.*?)</a>.*?</td>\s*"
    r"<td[^>]*>\s*([^<]*?)\s*</td>\s*<td[^>]*>(.*?)</td>", re.S)


def _attr(attrs, name):
    m = re.search(r"\b{0}\s*=\s*(?:\"([^\"]*)\"|'([^']*)')".format(name), attrs or "")
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else None


def parse_slip_page(page, term):
    """The term's opinions, one dict per R-number. The page splits the term
    across two tables (the newest above, the rest below); an R-number seen
    twice is kept once."""
    out = {}
    for m in _ROW.finditer(page or ""):
        rno = int(m.group(1))
        if rno in out:
            continue
        attrs = m.group(4)
        out[rno] = {"term": term, "rno": rno, "decided": us_date(m.group(2)),
                    "docket": _clean(m.group(3)),
                    "url": urllib.parse.urljoin(BASE, _attr(attrs, "href") or ""),
                    "summary": _clean(_attr(attrs, "title")), "case_name": _clean(m.group(5)),
                    "justice": _clean(m.group(6)), "citation": _clean(m.group(7))}
    return [out[k] for k in sorted(out)]


# --- orders ------------------------------------------------------------------

def parse_orders_page(page):
    """[(absolute url, kind)] for the order PDFs worth reading."""
    out, seen = [], set()
    for href, label in re.findall(r"href=['\"](/orders/courtorders/[^'\"]+\.pdf)['\"][^>]*>(.*?)</a>",
                                  page or ""):
        kind = _clean(label)
        url = BASE + href
        if kind in ORDER_KINDS and url not in seen:
            seen.add(url)
            out.append((url, kind))
    return out


def order_date(url):
    """'.../100526zor_2a34.pdf' -> '2026-10-05'."""
    m = re.search(r"/(\d{6})z", url)
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%m%d%y").date().isoformat()
    except ValueError:
        return None


def pdf_text(data):
    import logging
    import pypdf
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


# A docket line: '24-539  CHILES, KALEY V. SALAZAR, PATTY, ET AL.' The order
# lists draw consolidation brackets as ')' columns, which pypdf reads as text.
_DOCKET_LINE = re.compile(r"^\s*(\d{2}-\d{1,5}|\d{2}A\d{1,5})(?:\s+(.*?))?\s*$")
_BRACKET = re.compile(r"^[\s)]*$")
_HEADING = re.compile(r"^\s*([A-Z][A-Z ,\-\.']{6,})\s*$")
# "The petition for a writ of certiorari is granted", "the petitions for
# writs of certiorari are granted", "... before judgment is granted". Not
# "In the event certiorari is granted", which is a stay's condition.
_GRANTED = re.compile(r"petitions? for (?:a )?writs? of certiorari(?: before judgment)? "
                      r"(?:is|are) granted", re.I)
_PETITION = re.compile(r"^\d{2}-\d{1,5}$")
_GVR = re.compile(r"\bvacated\b|\bremanded\b", re.I)


def parse_grants(text):
    """[(docket, CASE NAME)] of the plenary certiorari grants in an order PDF.

    An entry is a docket line and the text under it, up to the next docket
    line or section heading. Consecutive docket lines with nothing between
    them are one group (consolidated cases) and share the text that follows.
    A grant is any entry under the CERTIORARI GRANTED heading, or whose text
    grants certiorari without vacating and remanding (GVRs are summary
    dispositions, not cases the Court will hear)."""
    groups, section, current = [], None, None
    for line in (text or "").splitlines():
        if _BRACKET.match(line):
            continue
        dm = _DOCKET_LINE.match(line)
        if dm:
            if current is None or current["body"].strip():
                current = {"cases": [], "body": "", "section": section}
                groups.append(current)
            # A bracketed group can print its names below the dockets
            # (TikTok v. Garland, 18 December 2024): the name is then empty
            # here and the docket page's caption stands in.
            name = re.sub(r"^[\s)]+|\(\d{2}A\d+\)\)?", "", dm.group(2) or "").strip(" )")
            current["cases"].append((dm.group(1), " ".join(name.split())))
            continue
        hm = _HEADING.match(line)
        if hm and not re.search(r"\d", line):
            section = " ".join(hm.group(1).split())
            current = None
            continue
        if current is not None:
            current["body"] += " " + line.strip()
    grants = []
    for g in groups:
        body = " ".join(g["body"].split())
        if (g["section"] or "").startswith("CERTIORARI GRANTED") or (
                _GRANTED.search(body) and not _GVR.search(body)):
            # Applications (25A312) are stays and injunctions, never a case
            # set down for argument.
            grants.extend(c for c in g["cases"] if _PETITION.match(c[0]))
    return grants


_SMALL = {"v.": "v.", "et": "et", "al.": "al.", "of": "of", "and": "and", "the": "the",
          "for": "for", "in": "in", "on": "on", "to": "to"}
_UPPER = {"EPA", "FCC", "FTC", "NLRB", "FDA", "DHS", "HHS", "USA", "US", "LLC", "TX",
          "CA", "NY", "FL", "WA", "DC", "TPS", "FBI", "IRS", "CIA", "ATF", "DOJ", "LP", "II",
          "III", "NJ", "DCJ", "BP"} | {
    # State abbreviations as the Clerk prints them ('ATT'Y GEN. OF OK'),
    # less the four that are also English words (IN, OR, ME, HI).
    "AL", "AK", "AZ", "AR", "CO", "CT", "DE", "GA", "ID", "IL", "IA", "KS", "KY", "LA",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NM", "NC", "ND", "OH",
    "OK", "PA", "RI", "SC", "SD", "TN", "UT", "VT", "VA", "WV", "WI", "WY"}


def case_name(caps):
    """'OKLAHOMA, ET AL. V. EPA, ET AL.' -> 'Oklahoma, et al. v. EPA, et al.'."""
    words = []
    for i, w in enumerate((caps or "").split()):
        bare = w.strip(",.;:()")
        low = w.lower()
        if i and low in _SMALL:
            words.append(_SMALL[low])
        elif bare.upper() in _UPPER or "&" in bare:
            words.append(w.upper())
        else:
            words.append(w[:1].upper() + w[1:].lower())
    return " ".join(words)


def short_caption(title):
    """'Kaley Chiles, Petitioner v. Patty Salazar, in Her Official Capacity...'
    -> 'Kaley Chiles v. Patty Salazar'."""
    parts = re.split(r"\s+v\.\s+", re.sub(r",?\s*\b(?:Petitioners?|Applicants?)\b", "",
                                              title or ""), maxsplit=1)
    return " v. ".join(p.split(",")[0].strip() for p in parts if p.strip()) or None


def parse_docket(page):
    """{'title': caption, 'qp_url': url or None} from a docket page."""
    title = None
    m = re.search(r"Title:\s*</span>\s*</td>\s*<td[^>]*>(.*?)</td>", page or "", re.S)
    if m:
        title = _clean(m.group(1))
    if not title:
        text = _clean(re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", page or "")) or ""
        m = re.search(r"Title:\s*(.*?)\s*(?:Docketed:|Lower Ct:)", text)
        title = m.group(1).strip() if m else None
    qp = re.search(r"href=['\"]([^'\"]*qp[^'\"]*\.pdf)['\"]", page or "", re.I)
    return {"title": title, "qp_url": qp.group(1) if qp else None}


def question_presented(text):
    """The question(s) from a QP PDF: from the heading on, clipped."""
    flat = " ".join((text or "").split())
    m = re.search(r"QUESTIONS? PRESENTED:?", flat, re.I)
    return (flat[m.end():] if m else flat).strip()[:QP_CHARS] or None


# --- classification and storage ---------------------------------------------

def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify_case(tax, wl, row):
    """The case name (and caption) as the title passage, then the holding or
    the question presented. Names alone are party names and match nothing."""
    name = row.get("case_name") or ""
    return filt.filter_item(tax, wl, name, row.get("title") or "", row.get("summary") or "",
                            title=name)


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def store_case(conn, key, kind, row, res, today):
    conn.execute(
        "INSERT INTO us_court_cases (case_key, kind, term, docket, case_name, title, decided, "
        "summary, justice, citation, url, order_url, areas, matched_terms, tier, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(case_key) DO UPDATE SET docket=excluded.docket, "
        "case_name=excluded.case_name, title=COALESCE(excluded.title, us_court_cases.title), "
        "decided=excluded.decided, summary=COALESCE(excluded.summary, us_court_cases.summary), "
        "justice=excluded.justice, citation=excluded.citation, url=excluded.url, "
        "order_url=COALESCE(excluded.order_url, us_court_cases.order_url), "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (key, kind, row.get("term"), row.get("docket"), row.get("case_name"), row.get("title"),
         row.get("decided"), row.get("summary"), row.get("justice"), row.get("citation"),
         row.get("url"), row.get("order_url"), us_store.dumps(res.issue_areas),
         us_store.dumps(res.matched_terms), res.tier, today, today))


class Refused(Exception):
    """The site refused or challenged us: stop this part of the run."""


def _get_text(client, url, slug):
    if not allowed(url):
        raise Refused("robots.txt disallows " + url)
    try:
        page = client.get_text(url, FEED, slug)
    except FetchError as exc:
        raise Refused(str(exc))
    if re.search(r"captcha|are you a robot|access denied", page[:5000], re.I):
        raise Refused("challenge page at " + url)
    return page


def _get_bytes(client, url, slug):
    if not allowed(url):
        raise Refused("robots.txt disallows " + url)
    try:
        data = client.get_bytes(url, FEED, slug)
    except FetchError as exc:
        raise Refused(str(exc))
    if not data.startswith(b"%PDF"):
        raise Refused("not a PDF at " + url)
    return data


def pull_opinions(conn, client, today, terms, tax, wl, log=print):
    read = ours = gaps = 0
    for term in terms:
        try:
            page = _get_text(client, SLIP.format(term=term), "slipopinion-" + term)
        except Refused as exc:
            db.record_gap(conn, FEED, "slip opinions OT20{0}: {1}".format(term, exc), today)
            gaps += 1
            continue
        for row in parse_slip_page(page, term):
            res = classify_case(tax, wl, row)
            store_case(conn, "opinion/{0}/{1}".format(term, row["rno"]), "opinion", row, res, today)
            read += 1
            ours += on_our_ground(res.issue_areas)
        conn.commit()
    log("us-courts: {0} opinion(s) read, {1} on our ground".format(read, ours))
    return read, ours, gaps


def read_grant(conn, client, docket, name, term, decided, order_url, tax, wl, today):
    """Store one grant, its caption and question presented. Returns (areas, gap)."""
    row = {"term": term, "docket": docket, "case_name": case_name(name) if name.isupper() else name,
           "decided": decided, "order_url": order_url, "url": DOCKET.format(docket=docket.lower())}
    gap = None
    try:
        info = parse_docket(_get_text(client, row["url"], "docket-" + docket))
        row["title"] = info["title"]
        if not row["case_name"] and info["title"]:
            row["case_name"] = short_caption(info["title"])
        if info["qp_url"]:
            qp = urllib.parse.urljoin(row["url"], info["qp_url"])
            row["summary"] = question_presented(pdf_text(_get_bytes(client, qp, "qp-" + docket)))
        else:
            gap = "grant {0}: the docket links no question presented".format(docket)
    except Refused as exc:
        gap = "grant {0}: {1}".format(docket, exc)
    except Exception as exc:                                  # noqa: BLE001 (a broken PDF)
        gap = "grant {0}: question presented unreadable ({1})".format(docket, str(exc)[:60])
    res = classify_case(tax, wl, row)
    store_case(conn, "grant/" + docket, "grant", row, res, today)
    if gap:
        db.record_gap(conn, FEED, gap, today)
    return res.issue_areas, gap


def pull_grants(conn, client, today, terms, tax, wl, log=print, limit=None, budget=None):
    """Every unread order PDF of the terms, and the grants in it."""
    try:
        import pypdf  # noqa: F401
    except ImportError:
        db.record_gap(conn, FEED, "pypdf is not installed: order lists and questions "
                                  "presented cannot be read; grants skipped", today)
        return 0, 0, 0, 1
    held = {u for (u,) in conn.execute("SELECT url FROM us_court_orders")}
    known = {d for (d,) in conn.execute("SELECT docket FROM us_court_cases WHERE kind='grant'")}
    pdfs = grants = ours = gaps = 0
    for term in terms:
        try:
            listing = parse_orders_page(_get_text(client, ORDERS.format(term=term),
                                                  "orders-" + term))
        except Refused as exc:
            db.record_gap(conn, FEED, "orders OT20{0}: {1}".format(term, exc), today)
            gaps += 1
            continue
        for url, kind in sorted((x for x in listing if x[0] not in held),
                                key=lambda x: order_date(x[0]) or ""):
            if budget is not None and budget.exhausted():
                log("  " + budget.disclose("Supreme Court order PDFs", pdfs))
                return pdfs, grants, ours, gaps
            if limit is not None and pdfs >= limit:
                log("  order PDF cap ({0}) reached; the rest are read next run "
                    "-- disclosed, not silent".format(limit))
                return pdfs, grants, ours, gaps
            try:
                text = pdf_text(_get_bytes(client, url, "order-" + os.path.basename(url)[:-4]))
            except Refused as exc:
                db.record_gap(conn, FEED, "order {0}: {1}".format(url, exc), today)
                log("  stopped at a refused order PDF; the next run carries on")
                return pdfs, grants, ours, gaps + 1
            except Exception as exc:                          # noqa: BLE001
                # Unreadable, not refused: recorded, left unread, and the run
                # goes on to the next file.
                db.record_gap(conn, FEED, "order {0}: unreadable ({1})".format(
                    url, str(exc)[:60]), today)
                continue
            found = [(d, n) for d, n in parse_grants(text) if d not in known]
            for docket, name in found:
                areas, gap = read_grant(conn, client, docket, name, term, order_date(url), url,
                                        tax, wl, today)
                known.add(docket)
                grants += 1
                ours += on_our_ground(areas)
                # A grant whose question could not be read is a gap on the
                # record, not a failed run: its caption is stored and the
                # edition still shows it.
            conn.execute("INSERT OR REPLACE INTO us_court_orders (url, term, order_date, kind, "
                         "grants, read_at) VALUES (?,?,?,?,?,?)",
                         (url, term, order_date(url), kind, len(found), today))
            conn.commit()
            pdfs += 1
    log("us-courts: {0} order PDF(s) read, {1} new grant(s), {2} on our ground".format(
        pdfs, grants, ours))
    return pdfs, grants, ours, gaps


def reclassify(conn, tax=None, log=print):
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    changed = 0
    for key, name, title, summary, areas in conn.execute(
            "SELECT case_key, case_name, title, summary, areas FROM us_court_cases").fetchall():
        res = classify_case(tax, wl, {"case_name": name, "title": title, "summary": summary})
        new = us_store.dumps(res.issue_areas)
        changed += new != (areas or "[]")
        conn.execute("UPDATE us_court_cases SET areas=?, matched_terms=?, tier=? WHERE case_key=?",
                     (new, us_store.dumps(res.matched_terms), res.tier, key))
    conn.commit()
    log("us-courts: reclassified; {0} case(s) changed area".format(changed))
    return changed


def stamp(conn, today):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/us_courts.py"))
    conn.commit()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--terms", help="October Terms, two digits, comma-separated "
                                    "(default: the current term and the last)")
    ap.add_argument("--limit", type=int, help="read at most this many order PDFs")
    ap.add_argument("--no-orders", action="store_true", help="opinions only")
    ap.add_argument("--budget-seconds", type=float, default=None,
                    help="stop reading order PDFs after this long; the rest wait for the "
                         "next run (the first backfill is about 18 minutes)")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    today = datetime.date.today().isoformat()
    if args.reclassify:
        reclassify(conn)
        conn.close()
        return 0
    now = current_term(today)
    first = not conn.execute("SELECT 1 FROM us_court_cases LIMIT 1").fetchone()
    start = int(FIRST_TERM) if first else int(now) - 1
    terms = ([t.strip() for t in args.terms.split(",") if t.strip()] if args.terms else
             ["{0:02d}".format(t) for t in range(start, int(now) + 1)])
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S,
                        host_concurrency=1)
    tax = filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    _r, _o, gaps = pull_opinions(conn, client, today, terms, tax, wl)
    if not args.no_orders:
        budget = drain.Budget(args.budget_seconds) if args.budget_seconds else None
        _p, _g, _o2, g2 = pull_grants(conn, client, today, terms, tax, wl, limit=args.limit,
                                      budget=budget)
        gaps += g2
    stamp(conn, today)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
