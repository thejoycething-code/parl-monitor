"""EU committee watch: meetings ahead, and the documents in the pipeline.

    python3 tools/eu_committees.py

The committee-agenda gap, closed sideways (2026-09-02). Per-item agendas
stay unreachable -- eMeeting's agenda route defeated discovery and the
open-data committee-documents endpoint has no OJ work-type -- but two
sources cover what a campaigner actually needs:

1. MEETINGS: eMeeting's backend answers plain HTTP once you know the
   route (found via the SPA's own network traffic):
   /emeeting/plmrep/meeting/events/eventsByMonth?organ=LIBE&year=&month=
   One call per watched committee per month, three months ahead.
2. PIPELINE: draft reports and opinions are where legislation lives for
   MONTHS before plenary -- the deepest forward look there is. The
   committee-documents listing returns id-only stubs, but the identifier
   encodes the committee (LIBE-PR-..., FEMM-AD-...), so stubs are
   filtered free and only watched committees' NEW documents cost a
   detail fetch for the EN title, which the taxonomy then judges.

Watched: LIBE, FEMM, JURI, EMPL, CULT, DROI -- the committees whose
remits carry our areas.

Separation guarantee: writes eu_cmte_meetings / eu_cmte_docs only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import time

from src import db, drain, eulabel, filter as filt
from src.http import FetchError, HttpClient

COMMITTEES = ("LIBE", "FEMM", "JURI", "EMPL", "CULT", "DROI")
EVENTS = ("https://emeeting.europarl.europa.eu/emeeting/plmrep/meeting/"
          "events/eventsByMonth?language=EN&year={0}&month={1}&organ={2}")
DOCS = ("https://data.europarl.europa.eu/api/v2/committee-documents"
        "?year={0}&limit=1000&offset={1}&format=application%2Fld%2Bjson")
DOC = ("https://data.europarl.europa.eu/api/v2/committee-documents/{0}"
       "?format=application%2Fld%2Bjson")
MONTHS_AHEAD = 3
DOC_FETCH_CAP = 300    # 585 watched-committee docs outstanding on 2026-09-03: two runs, not four. 300 x 0.65s = 3.3 min, inside the 30-min job and under the 500/5min API budget shared with the other steps.
THROTTLE_S = 0.65
BUDGET_S = drain.DEFAULT_S   # the clock that the count cap is not (19 Sept 2026)


def pull_meetings(conn, client, today, log=print):
    t = datetime.date.fromisoformat(today)
    months = []
    y, mo = t.year, t.month
    for _ in range(MONTHS_AHEAD):
        months.append((y, mo))
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    n = gaps = 0
    for cmte in COMMITTEES:
        for y, mo in months:
            try:
                reply = client.get_json(EVENTS.format(y, mo, cmte),
                                        "eu-committees",
                                        "{0}-{1}-{2}".format(cmte, y, mo),
                                        archive=False)
            except (FetchError, ValueError) as exc:
                log("  [gap] {0} {1}-{2}: {3}".format(cmte, y, mo, exc))
                gaps += 1
                continue
            for e in reply if isinstance(reply, list) else []:
                start = e.get("start")
                date = (datetime.datetime.utcfromtimestamp(start / 1000)
                        .date().isoformat() if start else None)
                conn.execute(
                    "INSERT INTO eu_cmte_meetings (uid, committee, "
                    "reference, date, title, venue, first_seen, last_seen) "
                    "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(uid) DO UPDATE "
                    "SET date=excluded.date, title=excluded.title, "
                    "last_seen=excluded.last_seen",
                    (e.get("uid"), cmte, e.get("meetingReference"), date,
                     e.get("title"), e.get("venue"), today, today))
                n += 1
    conn.commit()
    return n, gaps


def pull_docs(conn, client, today, log=print, budget_s=BUDGET_S):
    budget = drain.Budget(budget_s)
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    known = {r[0] for r in conn.execute("SELECT identifier FROM eu_cmte_docs")}
    stubs, offset = [], 0
    while True:
        try:
            reply = client.get_json(DOCS.format(today[:4], offset),
                                    "eu-committees",
                                    "docs-{0}".format(offset), archive=False)
        except (FetchError, ValueError) as exc:
            log("  [gap] committee-documents: {0}".format(exc))
            return 0, 0, 1
        batch = reply.get("data") or []
        stubs.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    ours = new = 0
    for s in stubs:
        ident = s.get("identifier") or ""
        cmte = ident.split("-", 1)[0]
        if cmte not in COMMITTEES or ident in known:
            continue
        if new >= DOC_FETCH_CAP:
            log("  fetch cap ({0}) reached; the rest drains on later runs "
                "-- disclosed, not silent".format(DOC_FETCH_CAP))
            break
        if budget.exhausted():
            log(budget.disclose("document fetches", new))
            break
        new += 1
        time.sleep(THROTTLE_S)
        try:
            det = client.get_json(DOC.format(ident), "eu-committees", ident,
                                  archive=False)
            d = (det.get("data") or [{}])[0]
        except (FetchError, ValueError) as exc:
            log("  [gap] doc {0}: {1}".format(ident, exc))
            continue
        title = eulabel.english(d.get("title_dcterms"))
        if not title:
            continue
        res = filt.filter_item(tax, wl, title)
        areas = res.issue_areas or []
        if areas:
            ours += 1
        conn.execute(
            "INSERT INTO eu_cmte_docs (identifier, committee, work_type, "
            "date, title, areas, matched_terms, tier, first_seen, "
            "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(identifier) DO UPDATE SET title=excluded.title, "
            "areas=excluded.areas, last_seen=excluded.last_seen",
            (ident, cmte,
             (d.get("work_type") or "").rsplit("/", 1)[-1],
             d.get("document_date"), title, json.dumps(areas),
             json.dumps(res.matched_terms or []), res.tier, today, today))
    conn.commit()
    return new, ours, 0


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    meetings, mgaps = pull_meetings(conn, client, today)
    new, ours, dgaps = pull_docs(conn, client, today)
    print("eu-committees: {0} meeting(s) inside {1} months; {2} new "
          "document(s), {3} on our ground; {4} gap(s).".format(
              meetings, MONTHS_AHEAD, new, ours, mgaps + dgaps))
    for r in conn.execute("SELECT * FROM eu_cmte_docs WHERE areas != '[]' "
                          "ORDER BY date DESC LIMIT 8").fetchall():
        print("  [{0}] {1} {2} - {3}".format(
            ",".join(str(a) for a in json.loads(r["areas"])),
            r["committee"], r["date"], (r["title"] or "")[:75]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
