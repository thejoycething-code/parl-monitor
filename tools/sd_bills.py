"""Senedd bill register -> sd_bills. Name, latest stage, our-areas match.

    python3 tools/sd_bills.py

RE-SOURCED 2026-08-28, with sd_committees, after business.senedd.wales went
behind an Azure WAF answering 403 to every non-browser client. This tool
fetched one tracking page PER BILL from that host, so every bill became a
gap: 11 in the last run.

Everything now comes from the register table on senedd.wales, which carries
per bill exactly what the tracking page did -- the ModernGov IId, the title,
a stage column and a progress sentence -- and carries it fresher: it had
46599 at Royal Assent while the store, last filled from the tracking pages,
still said Stage 4. One page replaces one fetch per bill.

WHAT WAS LOST. mgWhatsNew, also on the blocked host, was how a brand-new
bill was caught the week it started moving. Discovery is now the register
plus the rejected/withdrawn page, both of which list a bill once the Senedd
publishes it there. The register is headed "Progress of Senedd Bills", so it
should carry a bill from introduction -- but every row reads "Act" today,
the Seventh Senedd having introduced none, and the archive page no longer
renders its table, so that cannot be observed until the first live bill.
Worth a look when one appears rather than a trust.

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

def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    # Discovery AND status in one pass: each register page carries both.
    register = {}
    gaps = 0
    for name, url in (("legislation", senedd.LEGISLATION_URL),
                      ("rejected", senedd.REJECTED_URL)):
        try:
            page = client.get_text(url, "senedd", "bills-" + name,
                                   archive=False)
        except FetchError as exc:
            conn.execute("INSERT INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                         (datetime.date.today().isoformat(), "sd-bills",
                          "{0} page: {1}".format(name, exc.cause)))
            conn.commit()
            print("  [gap] {0}: {1}".format(name, exc.cause))
            gaps += 1
            continue
        for iid, title, column, progress in senedd.parse_bill_register(page):
            stage, date = senedd.bill_status_from_register(column, progress)
            register[iid] = (title, stage, date)
        # The rejected page lists its bills in prose rather than a table, so
        # the link reader still earns its place -- and a bill listed there
        # is withdrawn or rejected by definition, which is its stage.
        for iid, title in senedd.parse_bill_links(page):
            if iid in register:
                continue
            register[iid] = (title,
                             "Withdrawn or rejected" if name == "rejected"
                             else "Introduced", None)

    # A bill already known but absent from both pages keeps what it had:
    # dropping to "Introduced" would rewrite history backwards.
    for iid, title, stage, date in conn.execute(
            "SELECT iid, title, latest_stage, stage_date FROM sd_bills"):
        register.setdefault(iid, (title, stage, date))

    stored = ours = 0
    for iid in sorted(register):
        title, stage, date = register[iid]
        title = title or ""
        # Every row now comes from a legislation page rather than from
        # mgWhatsNew, which surfaced EVERY ModernGov issue type -- petitions
        # (P-07-...), cross-party group papers, consultations. The name
        # check stays anyway: it costs nothing and the register is not ours
        # to assume about.
        if not re.search(r"\b(Bill|Act)\b", title):
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
