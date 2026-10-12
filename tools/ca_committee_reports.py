#!/usr/bin/env python3
"""Committee reports, House of Commons (with joint committees) and Senate, on
our issues -- and the government's response when one is published.

    python3 tools/ca_committee_reports.py                    # key committees, 45-1, both chambers
    python3 tools/ca_committee_reports.py --session 44-1 --committee JUST,SOCI
    python3 tools/ca_committee_reports.py --chamber senate --limit 5
    python3 tools/ca_committee_reports.py --dry-run          # read and count, store nothing

Built 12 October 2026 (Christopher: "Build both"). One table,
ca_committee_reports, one row per report READ, ours or not, so a report is
never fetched twice. Scope: docs/canada-federal-sources-scope.md, section (4).

THE HOUSE (and AMAD, BILI, REGS on parl.ca). The committee's Work page,
/Committees/en/<ACR>/Work?parl=P&session=S, lists each study with its
reports -- 'Report 4 - Preventing Harm in the Canadian Sex Industry', the
date it was presented to the House (or concurred in), the DocumentViewer
link -- and, under a report, its Government Response with the date that was
presented. For a NEW report two more fetches: its table of contents
(<report>/page-ToC) and, when the ToC links one, the LIST OF RECOMMENDATIONS
page, parsed into its numbered recommendations (Rhead/R1 paragraphs). A bill
report ('Report 3', the bill reported back) has no list: recommendations
NULL, matched on its study title (the bill and its long title).

THE SENATE. The committee's reports partial,
/umbraco/surface/CommitteesAjax/GetCommitteeReports?committeeId=<id>&
selectedSession=<P-S>&Lang=en, lists SUBSTANTIVE reports ('Eleventh
Report: Fuelled by Technology, Powered by Humanity ...'), each with its PDF,
web page and Government Response links where they exist; administrative
reports (budgets, travel) are left out. The partial can list a report of an
earlier session whose response came in this one; the report's own session,
from its link, keys it. For a NEW report one more fetch: the report page,
which carries the date and the report itself (a bill report's text and
observations, or a study report's summary), matched per passage.

MATCHING. The English taxonomy plus config/watchlist-ca.yaml, per passage
(src/filter.match_passages): the text is the recommendations (House) or the
report body (Senate), the title passage the study plus the report's title,
as tools/ca_committees.py passes the study titles. Areas and tier are
stored on every row; the edition shows those on our ground.

GOVERNMENT RESPONSES arrive months later. The list pages are re-read on
every run (one fetch per committee), and a response that has appeared since
is written to the row in place -- response_url, and response_date where the
page prints one (the House does; the Senate's partial does not, so a Senate
row's response_date stays NULL). last_seen is the last run that listed it.

WHICH COMMITTEES. The House collector's key nine (tools/ca_committees.py)
and the Senate's three on our ground (tools/ca_senate_committees.py: SOCI,
LCJC, RIDR). --committee names others. robots.txt asked every run
(src/robots_guard); one request a second; gaps recorded, never fatal; the
first run is the baseline (every report of the session, up to --limit and
the clock), the weeks after read only what is new.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import importlib.util
import json
import os
import re
import sys
from urllib.parse import urljoin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import guard  # noqa: E402


def _load(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cm = _load("ca_committees")
scm = _load("ca_senate_committees")
sd = scm.sd
han = cm.han

FEED = "ca-committee-reports"
CURRENT_SESSION = cm.CURRENT_SESSION
WORK = "{0}/Committees/en/{1}/Work?parl={2}&session={3}"
SENATE_REPORTS = (scm.BASE + "/umbraco/surface/CommitteesAjax/GetCommitteeReports?committeeId={0}"
                  "&selectedSession={1}&Lang=en")
HOUSE_COMMITTEES = cm.KEY_COMMITTEES
SENATE_COMMITTEES = scm.KEY_COMMITTEES
DEFAULT_LIMIT = 60          # new reports read in full per run
MAX_FAILING = 5
TEXT_CLIP = 60000           # characters of a report kept for the retag

LEVEL1 = re.compile(r'<div class="level1-item">')
FIRST_LINK = re.compile(r"<a\b[^>]*>(.*?)</a>", re.S)
HOUSE_REPORT = re.compile(
    r'<a href="([^"]*/DocumentViewer/en/(\d{1,2})-(\d)/([A-Z]{4})/report-(\d+)/)"[^>]*>(.*?)</a>\s*'
    r'<div class="additional-info">([^<]*)</div>', re.S)
HOUSE_RESPONSE = re.compile(
    r'<a href="([^"]*/report-(\d+)/response-[^"]+)"[^>]*>[^<]*</a>\s*'
    r'<div class="additional-info">([^<]*)</div>', re.S)
WHEN = re.compile(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
                  r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})")
TOC_RECS = re.compile(r'href="([^"]+)"[^>]*>\s*LIST OF RECOMMENDATIONS\s*<', re.I)
REC = re.compile(r'<p class="Rhead">\s*(Recommendation(?:\s|&nbsp;|&#160;)+\d+)\s*</p>\s*'
                 r'((?:<p class="R\d[^"]*">.*?</p>\s*)+)', re.S | re.I)
PUBLICATION = re.compile(r'class="[^"]*publication-container-content[^"]*">(.*?)'
                         r'(?:<div id="publicationBottom"|$)', re.S)
SENATE_ITEM = re.compile(
    r'<li class="cmt-li-list-report"><a href="(/en/committees/([A-Za-z]{4})/report/(\d+)/(\d{1,2})-(\d))">'
    r"<strong>([^<]*)</strong></a>\s*:?\s*(.*?)</li>(\s*<li class=\"cmt-ul-list-report-2\">.*?</ul></li>)?",
    re.S | re.I)
SUB_LINK = re.compile(r"<a href=['\"]([^'\"]+)['\"][^>]*>([^<]*)</a>", re.S)
SENATE_BODY = re.compile(r"Report of the committee\s*</h3>", re.I)

ORDINALS = {w: i for i, w in enumerate((
    "zeroth first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth "
    "thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth").split())}
TENS = {"twentieth": 20, "thirtieth": 30, "fortieth": 40, "fiftieth": 50, "sixtieth": 60,
        "seventieth": 70, "eightieth": 80, "ninetieth": 90}
TENS_PREFIX = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
               "seventy": 70, "eighty": 80, "ninety": 90}


def ordinal(text):
    """'Twelfth Report' -> 12, 'Twenty-first Report' -> 21; None if not one."""
    word = (text or "").strip().split(" ")[0].lower().replace("‑", "-")
    if word in ORDINALS:
        return ORDINALS[word]
    if word in TENS:
        return TENS[word]
    head, _, tail = word.partition("-")
    if head in TENS_PREFIX and tail in ORDINALS:
        return TENS_PREFIX[head] + ORDINALS[tail]
    return None


def _when(text):
    hit = WHEN.search(text or "")
    return scm._date(hit.group(1), hit.group(2), hit.group(3)) if hit else None


def _abs(href, base):
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base, href)


def report_key(chamber, parl, sess, acr, ident):
    return "{0}-{1}-{2}-{3}-{4}".format(chamber, parl, sess, acr, ident)


# ------------------------------------------------------------------ House

def work_url(acr, parl, sess):
    return WORK.format(cm.committee_base(acr), acr, parl, sess)


def parse_work(text, acr, parl, sess, page_url=None):
    """[report dict] from a House committee's Work page, each with its study,
    title, date and government response (or None)."""
    page_url = page_url or work_url(acr, parl, sess)
    starts = [m.start() for m in LEVEL1.finditer(text or "")]
    out, seen = [], set()
    for i, s in enumerate(starts):
        chunk = text[s: starts[i + 1] if i + 1 < len(starts) else len(text)]
        first = FIRST_LINK.search(chunk)
        study = sd._clean(first.group(1)) if first else None
        responses = {int(n): (_abs(htmlmod.unescape(u), page_url), _when(info))
                     for u, n, info in HOUSE_RESPONSE.findall(chunk)}
        for url, p, ss, racr, n, label, info in HOUSE_REPORT.findall(chunk):
            number = int(n)
            key = report_key("commons", int(p), int(ss), racr, number)
            if key in seen:
                continue
            seen.add(key)
            label = sd._clean(label)
            title = label.split(" - ", 1)[1].strip() if " - " in label else None
            resp = responses.get(number)
            out.append({"key": key, "chamber": "commons", "committee": racr,
                        "parliament": int(p), "session": int(ss), "number": number,
                        "title": title, "study": study, "date": _when(info),
                        "url": _abs(htmlmod.unescape(url), page_url), "pdf_url": None,
                        "response_url": resp[0] if resp else None,
                        "response_date": resp[1] if resp else None})
    return out


def parse_recommendations(text):
    """['Recommendation 1: That the Government of Canada ...', ...]."""
    out = []
    for head, body in REC.findall(text or ""):
        out.append("{0}: {1}".format(sd._clean(head), sd._clean(body)))
    return out


def read_house_report(client, r):
    """Fill recommendations_url, recommendations and text from the ToC and
    the LIST OF RECOMMENDATIONS page. Returns a gap detail or None."""
    toc_url = r["url"].rstrip("/") + "/page-ToC"
    try:
        toc = client.get_text(toc_url, FEED, "toc-" + r["key"], archive=False)
    except FetchError as exc:
        return "{0}: table of contents: {1}".format(r["key"], exc)
    pdf = re.search(r'href="([^"]+\.pdf)"', toc or "", re.I)
    r["pdf_url"] = _abs(htmlmod.unescape(pdf.group(1)), toc_url) if pdf else None
    link = TOC_RECS.search(toc or "")
    if not link:
        # A one-page report (a bill reported back, a report re-adopted from
        # an earlier session) is served whole at its ToC address: its text
        # is what is matched, and it has no list of recommendations.
        body = PUBLICATION.search(toc or "")
        r["recommendations_url"], r["recommendations"] = None, None
        r["text"] = sd._clean(body.group(1)) if body else ""
        return None
    url = _abs(htmlmod.unescape(link.group(1)), toc_url).split("#")[0]
    try:
        page = client.get_text(url, FEED, "recs-" + r["key"])
    except FetchError as exc:
        return "{0}: list of recommendations: {1}".format(r["key"], exc)
    recs = parse_recommendations(page)
    if not recs:
        return "{0}: LIST OF RECOMMENDATIONS parsed to nothing ({1})".format(r["key"], url)
    r["recommendations_url"], r["recommendations"], r["text"] = url, len(recs), "\n".join(recs)
    return None


# ----------------------------------------------------------------- Senate

def parse_senate_reports(text, acr):
    """[report dict] from a Senate committee's reports partial: substantive
    reports only, each with its PDF and government response links."""
    text = (text or "").split("Administrative Reports", 1)[0]
    out = []
    for path, racr, rid, p, ss, ordtext, desc, subs in SENATE_ITEM.findall(text):
        pdf = resp = None
        for href, label in SUB_LINK.findall(subs or ""):
            label = sd._clean(label)
            href = _abs(htmlmod.unescape(href), scm.BASE + "/")
            if label.lower().startswith("government response"):
                resp = resp or href
            elif href.lower().endswith(".pdf") and not pdf:
                pdf = href
        out.append({"key": report_key("senate", int(p), int(ss), racr.upper(), rid),
                    "chamber": "senate", "committee": racr.upper(), "parliament": int(p),
                    "session": int(ss), "number": ordinal(ordtext),
                    "title": sd._clean(desc) or None, "study": None, "date": None,
                    "url": scm.BASE + path, "pdf_url": pdf, "response_url": resp,
                    "response_date": None, "site_id": rid})
    return out


def read_senate_report(client, r):
    """Fill date and text from the Senate report page. Gap detail or None."""
    try:
        page = client.get_text(r["url"], FEED, "report-" + r["key"])
    except FetchError as exc:
        return "{0}: report page: {1}".format(r["key"], exc)
    start = SENATE_BODY.search(page or "")
    if not start:
        return "{0}: no 'Report of the committee' on the page (markup changed?)".format(r["key"])
    end = sd.CONTENT_END.search(page, start.end())
    region = page[start.end(): end.start() if end else len(page)]
    paras = [sd._clean(m.group(2)) for m in sd.TOKEN.finditer(region)]
    paras = [p for p in paras if p]
    r["date"] = next((d for d in (_when(p) for p in paras[:3]) if d), None)
    r["text"] = "\n".join(paras)
    if not r["text"]:
        return "{0}: the report page holds no text ({1})".format(r["key"], r["url"])
    return None


# ---------------------------------------------------------------- storing

def classify(tax, wl, r):
    """(areas, terms, excerpt, tier) for one report."""
    title = " — ".join(x for x in (r.get("study"), r.get("title")) if x) or None
    matches = filt.match_passages(tax, wl, r.get("text") or "", title=title)
    areas, terms, excerpt = filt.aggregate_passages(matches)
    tier = 1 if any(m.result.tier == 1 for m in matches) else 2 if matches else None
    return areas, terms, excerpt, tier


def store_report(conn, r, tax, wl, today):
    areas, terms, excerpt, tier = classify(tax, wl, r)
    conn.execute(
        "INSERT OR REPLACE INTO ca_committee_reports (report_key, chamber, committee, parliament, "
        "session, number, title, study, date, url, pdf_url, recommendations_url, recommendations, "
        "text, excerpt, areas, matched_terms, tier, response_url, response_date, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (r["key"], r["chamber"], r["committee"], r["parliament"], r["session"], r["number"],
         r["title"], r["study"], r["date"], r["url"], r.get("pdf_url"),
         r.get("recommendations_url"), r.get("recommendations"),
         (r.get("text") or "")[:TEXT_CLIP] or None, excerpt, json.dumps(areas),
         json.dumps(terms, ensure_ascii=False), tier, r["response_url"], r["response_date"],
         today, today))
    return han.on_our_ground(areas)


def refresh(conn, r, today):
    """A report already held: stamp last_seen, and link a government response
    that has appeared since. Returns 1 if a response was newly linked."""
    conn.execute("UPDATE ca_committee_reports SET last_seen=? WHERE report_key=?",
                 (today, r["key"]))
    if not r["response_url"]:
        return 0
    return conn.execute(
        "UPDATE ca_committee_reports SET response_url=?, response_date=? "
        "WHERE report_key=? AND response_url IS NULL",
        (r["response_url"], r["response_date"], r["key"])).rowcount


def held(conn):
    return {r[0] for r in conn.execute("SELECT report_key FROM ca_committee_reports")}


def pull(conn, client, today, session=CURRENT_SESSION, house=HOUSE_COMMITTEES,
         senate=SENATE_COMMITTEES, limit=DEFAULT_LIMIT, tax=None, wl=None, log=print,
         budget=None):
    """Read each committee's report list and every report not yet held."""
    tax = tax if tax is not None else filt.load_taxonomy(cm.TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(cm.WATCHLIST)
    parl, sess = han.parse_session(session)
    have = held(conn)
    s = {"listed": 0, "attempted": 0, "read": 0, "ours": 0, "responses": 0, "skipped": 0,
         "stopped": None}
    gaps, failing = [], 0
    jobs = [("commons", a) for a in house] + [("senate", a) for a in senate]
    for chamber, acr in jobs:
        try:
            if chamber == "commons":
                url = work_url(acr, parl, sess)
                listing = parse_work(client.get_text(url, FEED, "work-{0}-{1}".format(acr, session),
                                                     archive=False), acr, parl, sess, url)
            else:
                cid = scm.committee_id(client, acr, session)
                listing = parse_senate_reports(client.get_text(
                    SENATE_REPORTS.format(cid, session), FEED,
                    "reports-{0}-{1}".format(acr, session), archive=False), acr)
        except (FetchError, ValueError) as exc:
            gaps.append("{0} {1} {2}: report list: {3}".format(chamber, acr, session, exc))
            continue
        s["listed"] += len(listing)
        for r in listing:
            if r["key"] in have:
                s["skipped"] += 1
                s["responses"] += refresh(conn, r, today)
                continue
            if s["stopped"]:
                continue
            if limit is not None and s["attempted"] >= limit:
                s["stopped"] = "limit"
                continue
            if failing >= MAX_FAILING:
                s["stopped"] = "failing"
                continue
            if budget is not None and budget.exhausted():
                log(budget.disclose("committee reports", s["read"]))
                s["stopped"] = "budget"
                continue
            s["attempted"] += 1
            gap = (read_house_report if chamber == "commons" else read_senate_report)(client, r)
            if gap:
                gaps.append(gap)
                failing += 1
                continue
            failing = 0
            ours = store_report(conn, r, tax, wl, today)
            have.add(r["key"])
            s["read"] += 1
            s["ours"] += ours
            log("  {0} {1}: {2}{3}{4}".format(
                r["key"], r["date"] or "date ?", (r["title"] or r["study"] or "")[:80],
                ", {0} recommendation(s)".format(r["recommendations"])
                if r.get("recommendations") else "", " -- ON OUR GROUND" if ours else ""))
        conn.commit()
        log("  {0} {1} {2}: {3} report(s) listed".format(chamber, acr, session, len(listing)))
    if s["stopped"] == "limit":
        log("  report cap ({0}) reached; the rest are read on later runs".format(limit))
    s["gaps"] = db.record_gaps(conn, FEED, gaps, edition=today)
    for g in gaps:
        log("  [gap] " + g[:160])
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=CURRENT_SESSION, help="P-S, e.g. 45-1")
    ap.add_argument("--committee", help="acronyms, comma-separated; House or Senate by name")
    ap.add_argument("--chamber", choices=("both", "commons", "senate"), default="both")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="read and count into an in-memory store; nothing is kept")
    args = ap.parse_args()
    client = guard(HttpClient(raw_dir=args.raw_dir, throttle=1.0), FEED)
    today = datetime.date.today().isoformat()
    conn = ca_store.ensure_schema(db.init_db(db.connect(":memory:" if args.dry_run else args.db)))
    house, senate = HOUSE_COMMITTEES, SENATE_COMMITTEES
    if args.committee:
        names = [c.strip().upper() for c in args.committee.split(",") if c.strip()]
        senate_names = set(scm.COMMITTEE_IDS) | set(scm.GATED)
        senate = tuple(c for c in names if c in senate_names)
        house = tuple(c for c in names if c not in senate_names)
    if args.chamber == "commons":
        senate = ()
    if args.chamber == "senate":
        house = ()
    print("ca-committee-reports: {0}, {1} House and {2} Senate committee(s)".format(
        args.session, len(house), len(senate)))
    s = pull(conn, client, today, session=args.session, house=house, senate=senate,
             limit=args.limit, budget=drain.Budget(args.budget_seconds))
    print("ca-committee-reports: {0} listed, {1} read now ({2} on our ground), {3} already "
          "held, {4} government response(s) newly linked; {5} gap(s){6}.".format(
              s["listed"], s["read"], s["ours"], s["skipped"], s["responses"], s["gaps"],
              " (dry run: nothing kept)" if args.dry_run else ""))
    if not args.dry_run:
        n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        print("  store: {0} committee report(s) held, {1} with a government response".format(
            n("SELECT COUNT(*) FROM ca_committee_reports"),
            n("SELECT COUNT(*) FROM ca_committee_reports WHERE response_url IS NOT NULL")))
    conn.close()
    return 1 if s["gaps"] else 0


if __name__ == "__main__":
    sys.exit(main())
