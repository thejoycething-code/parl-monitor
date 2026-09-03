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
net-vs-judge split as the speeches collector. The CJEU is NOT here:
curia.europa.eu retired its RSS routes (404, probed) and InfoCuria is
POST-driven; scoped in docs/eu-monitor-spec.md for a later session.

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
