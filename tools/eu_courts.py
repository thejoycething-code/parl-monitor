"""Court watch: Strasbourg judgments as upstream drivers.

    python3 tools/eu_courts.py

Courts create the consultations the monitors later catch -- JR87 created
the NI RE consultation, and ECtHR rulings set the frame member states
legislate under. This watches the EUROPEAN COURT OF HUMAN RIGHTS via
HUDOC's open JSON API (probed 2026-09-02: bare-term query grammar,
kpdate-sorted, 95k+ documents; the fulltext: field syntax silently
returns zero and is NOT used).

A curated term net nominates recent judgments; the taxonomy judges the
case NAME + conclusion text before anything is stored -- same
net-vs-judge split as the speeches collector.

LUXEMBOURG ADDED 2026-09-03. The earlier note said the CJEU was out of
reach: curia retired its RSS routes and InfoCuria is POST-driven, both
still true. What was not tried then is EUR-Lex's own public search,
which answers on a plain GET and parses cleanly -- CELEX id, court,
date and link. So Luxembourg is a BOUNDED read: the judgment's
existence, court and date, never its reasoning, which a human reads on
the page. If the page shape moves, the parse yields ids without titles
and the run records a gap rather than storing blanks.

Separation guarantee: writes eu_judgments only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import FetchError, HttpClient

QUERY = ("https://hudoc.echr.coe.int/app/query/results?query={0}"
         "&select=itemid,docname,doctype,appno,conclusion,kpdate,"
         "respondent&sort=kpdate%20Descending&start=0&length=50")
CASE = "https://hudoc.echr.coe.int/eng?i={0}"
LOOKBACK_DAYS = 90

SEARCH_TERMS = [
    "abortion", "surrogacy", "euthanasia", "assisted suicide",
    "conversion therapy", "religious freedom", "freedom of religion",
    "gender reassignment", "same-sex parenthood", "home education",
    "freedom of expression religion",
]


EURLEX = ("https://eur-lex.europa.eu/search.html?scope=EURLEX&text={0}"
          "&type=quick&lang=en&DTS_SUBDOM=EU_CASE_LAW"
          "&date0=ALL%3A{1}%7C{2}&sortOne=DD&sortOneOrder=desc")
EURLEX_DOC = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{0}"
# CELEX sector-6 document codes: 62021CJ0621 -> CJ = Court judgment.
CJEU_DOCTYPE = {"CJ": "CJEU judgment", "TJ": "General Court judgment",
                "TB": "General Court order", "CC": "AG opinion",
                "CO": "CJEU order"}


def eurlex_cases(client, term, start, end, log=print):
    """(rows, ok). Bounded parse of EUR-Lex's public case-law search."""
    import re
    url = EURLEX.format(term.replace(" ", "+"),
                        start.strftime("%d%m%Y"), end.strftime("%d%m%Y"))
    try:
        html = client.get_text(url, "eu-courts",
                               "eurlex-" + term.replace(" ", "-"),
                               archive=False)
    except FetchError as exc:
        log("  [gap] eur-lex '{0}': {1}".format(term, exc.cause))
        return [], False
    celex = []
    for cid in re.findall(r"CELEX[%:]3?A?(6\d{4}[A-Z]{2}\d+)", html):
        if cid not in celex:
            celex.append(cid)
    titles = re.findall(r'class="title"[^>]*>([^<]{10,200})', html)
    if celex and not titles:
        log("  [gap] eur-lex '{0}': {1} case id(s) but no titles -- the "
            "page shape moved; storing nothing".format(term, len(celex)))
        return [], False
    rows = []
    for i, cid in enumerate(celex):
        title = " ".join(titles[i].split()) if i < len(titles) else None
        if not title:
            continue
        date = None
        m = re.search(r"of (\d{1,2} \w+ \d{4})", title)
        if m:
            try:
                date = datetime.datetime.strptime(
                    m.group(1), "%d %B %Y").date().isoformat()
            except ValueError:
                date = None
        rows.append({"item_id": "CJEU:" + cid, "case_name": title,
                     "doc_type": CJEU_DOCTYPE.get(cid[5:7], "CJEU"),
                     "app_no": cid, "conclusion": None, "date": date,
                     "respondent": None, "url": EURLEX_DOC.format(cid)})
    return rows, True


def build_query(term, start):
    q = ('contentsitename:ECHR AND {0} AND ((languageisocode="ENG")) '
         'AND (kpdate>="{1}")').format(term, start)
    return QUERY.format(urllib.parse.quote(q, safe=""))


def pull(conn, client, today, log=print):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    start = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    known = {r[0] for r in conn.execute("SELECT item_id FROM eu_judgments")}
    seen = stored = gaps = 0
    for term in SEARCH_TERMS:
        try:
            reply = client.get_json(build_query('"{0}"'.format(term), start),
                                    "eu-courts",
                                    term.replace(" ", "-"), archive=False)
        except (FetchError, ValueError) as exc:
            log("  [gap] hudoc '{0}': {1}".format(term, exc))
            gaps += 1
            continue
        for r in reply.get("results") or []:
            c = r.get("columns") or {}
            item = c.get("itemid")
            if not item or item in known:
                continue
            seen += 1
            name = c.get("docname") or ""
            conclusion = c.get("conclusion") or ""
            res = filt.filter_item(tax, wl, "{0} {1} {2}".format(
                name, conclusion, term))
            areas = res.issue_areas or []
            if not areas:
                continue
            known.add(item)
            stored += 1
            conn.execute(
                "INSERT OR REPLACE INTO eu_judgments (item_id, case_name, "
                "doc_type, app_no, conclusion, date, respondent, url, "
                "areas, matched_terms, tier, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item, name, c.get("doctype"), c.get("appno"),
                 conclusion[:500], str(c.get("kpdate", ""))[:10],
                 c.get("respondent"), CASE.format(item),
                 json.dumps(areas), json.dumps(res.matched_terms or []),
                 res.tier, today, today))
        # Luxembourg, same term, same judge, same table.
        rows, ok = eurlex_cases(client, term,
                                datetime.date.fromisoformat(start),
                                datetime.date.fromisoformat(today), log)
        if not ok:
            gaps += 1
        for row in rows:
            if row["item_id"] in known:
                continue
            seen += 1
            # NOTE on what is actually being judged here. A CJEU
            # search-result title is boilerplate -- "Judgment of the Court
            # (Grand Chamber) of 16 July 2026" -- so the taxonomy has
            # nothing of the case to read, and the SEARCH TERM is passed
            # in with it. That means the term, not the title, supplies the
            # area: the row exists because EUR-Lex matched that phrase in
            # the judgment's full text, which is real evidence the court
            # engaged our vocabulary, but it is NOT an independent
            # judgement of the case. The stored conclusion says which term
            # found it so a reader can weigh that, and the same is true of
            # the HUDOC rows above, whose docname is equally terse.
            res = filt.filter_item(tax, wl, "{0} {1}".format(
                row["case_name"], term))
            areas = res.issue_areas or []
            known.add(row["item_id"])
            stored += 1
            conn.execute(
                "INSERT OR REPLACE INTO eu_judgments (item_id, case_name, "
                "doc_type, app_no, conclusion, date, respondent, url, "
                "areas, matched_terms, tier, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["item_id"], row["case_name"], row["doc_type"],
                 row["app_no"], "found by search term: " + term,
                 row["date"], None, row["url"], json.dumps(areas),
                 json.dumps(res.matched_terms or []), res.tier,
                 today, today))
    conn.commit()
    return seen, stored, gaps


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    seen, stored, gaps = pull(conn, client, today)
    total = conn.execute("SELECT COUNT(*) FROM eu_judgments").fetchone()[0]
    print("eu-courts: {0} new candidate(s) inside {1} days, {2} stored on "
          "our ground ({3} held); {4} gap(s).".format(
              seen, LOOKBACK_DAYS, stored, total, gaps))
    for r in conn.execute("SELECT * FROM eu_judgments ORDER BY date DESC "
                          "LIMIT 8").fetchall():
        print("  [{0}] {1} - {2}".format(
            ",".join(str(a) for a in json.loads(r["areas"])),
            r["date"], (r["case_name"] or "")[:70]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
