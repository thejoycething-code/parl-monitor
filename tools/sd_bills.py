"""Senedd bill register -> sd_bills. Name, latest stage, our-areas match.

    python3 tools/sd_bills.py

Discovery is the union of three link sources: the legislation page and the
rejected/withdrawn page on senedd.wales (honest UA), plus any tracking page
surfacing in business.senedd.wales/mgWhatsNew.aspx -- which is how a NEW bill
is caught the week it starts moving, since the legislation landing page lists
completed Acts. Stage is parsed from prose (see src/ingest/senedd.py).

Same rules as every watching-brief tool: sd_* tables only; gaps printed.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import FetchError, HttpClient
from src.ingest import senedd

WHATSNEW = "https://business.senedd.wales/mgWhatsNew.aspx"


def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    iids = {}
    gaps = 0
    for name, url in (("legislation", senedd.LEGISLATION_URL),
                      ("rejected", senedd.REJECTED_URL)):
        try:
            page = client.get_text(url, "senedd", "bills-" + name,
                                   archive=False)
            for iid, title in senedd.parse_bill_links(page):
                iids[iid] = title
        except FetchError as exc:
            print("  [gap] {0}: {1}".format(name, exc.cause))
            gaps += 1
    try:
        page = client.get_text(WHATSNEW, "senedd", "whatsnew", archive=False)
        for iid in re.findall(r"mgIssueHistoryHome\.aspx\?IId=(\d+)", page):
            iids.setdefault(int(iid), None)
    except FetchError as exc:
        print("  [gap] whatsnew: {0}".format(exc.cause))
        gaps += 1
    known = {r[0] for r in conn.execute("SELECT iid FROM sd_bills")}
    iids.update({k: None for k in known if k not in iids})

    stored = ours = 0
    for iid in sorted(iids):
        try:
            title, stage, date = senedd.fetch_bill(client, iid)
        except FetchError as exc:
            conn.execute("INSERT INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                         (datetime.date.today().isoformat(), "sd-bills",
                          "IId {0}: {1}".format(iid, exc.cause)))
            conn.commit()
            print("  [gap] IId {0}: {1}".format(iid, exc.cause))
            gaps += 1
            continue
        title = title or iids.get(iid) or ""
        # mgWhatsNew surfaces EVERY ModernGov issue type -- petitions
        # (P-07-...), cross-party group papers, consultations. Discovery-
        # sourced items must look like legislation; items from the
        # legislation pages themselves are trusted as listed.
        if iids.get(iid) is None and not re.search(
                r"\b(Bill|Act)\b", title):
            continue
        res = filt.filter_item(tax, wl, title)
        areas = res.issue_areas or []
        if areas:
            ours += 1
        conn.execute(
            "INSERT INTO sd_bills (iid, title, latest_stage, stage_date, "
            "areas, matched_terms, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(iid) DO UPDATE SET title=excluded.title, "
            "latest_stage=excluded.latest_stage, "
            "stage_date=excluded.stage_date, areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, "
            "last_seen=excluded.last_seen",
            (iid, title, stage, date, json.dumps(areas),
             json.dumps(res.matched_terms or []), now, now))
        stored += 1
    conn.commit()
    print("{0} bill(s) in the register, {1} on our ground by title.".format(
        stored, ours))
    for r in conn.execute("SELECT iid, title, latest_stage, stage_date, areas "
                          "FROM sd_bills ORDER BY last_seen DESC, iid DESC"):
        mark = "  OURS" if r["areas"] and r["areas"] != "[]" else "      "
        print("{0} IId {1}  {2:<58} {3}{4}".format(
            mark, r["iid"], (r["title"] or "?")[:57], r["latest_stage"],
            " ({0})".format(r["stage_date"]) if r["stage_date"] else ""))
    print("no gaps." if not gaps else "{0} gap(s) -- printed above.".format(gaps))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
