"""EU adopted texts: what the Parliament just resolved, taxonomy-matched.

    python3 tools/eu_texts.py

Phase 2c of the EU monitor. EP resolutions are non-binding but set the
promotion agenda -- the "items of concern the EU are promoting" in
Christopher's words -- and each adopted text names the procedure it
decides, which makes this feed double as the dossier watchlist's
AUTO-PROPOSAL source: a taxonomy-matched text whose procedure resolves in
the procedures API and is not yet watched is printed as a candidate. A
human confirms by editing config/eu_watchlist.yaml; nothing is added
automatically, matching the Westminster watchlist rule.

Volume, measured 2026-09-01: 272 adopted texts in 2026; the year listing
is one ~12MB call (multilingual titles), fetched weekly and filtered to a
60-day window. Public TA pages sit behind europarl.eu's bot-wall (202 to
curl), so rows ship without links rather than with unverified ones.

Separation guarantee: writes eu_texts only.
ONE WRITER AT A TIME on data/parl-monitor.db.
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

TEXTS = ("https://data.europarl.europa.eu/api/v2/adopted-texts"
         "?year={0}&limit=500&format=application%2Fld%2Bjson")
PROC = ("https://data.europarl.europa.eu/api/v2/procedures/{0}"
        "?format=application%2Fld%2Bjson")
WINDOW_DAYS = 60

# 'eli/dl/event/2025-2028-DEC-DCPL-2026-01-20' -> '2025-2028'
EVENT_PROC = re.compile(r"eli/dl/event/(\d{4}-\d{4})-")


def procedure_ref(item):
    for ev in item.get("inverse_decided_on_a_realization_of") or []:
        m = EVENT_PROC.search(str(ev))
        if m:
            return m.group(1)
    return None


def pull(conn, client, today, log=print, days=None, on_day=None):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    t = datetime.date.fromisoformat(today)
    cutoff = on_day if on_day else (t - datetime.timedelta(days=days or WINDOW_DAYS)).isoformat()
    years = sorted({int(cutoff[:4]), t.year})
    items = []
    for y in years:
        try:
            reply = client.get_json(TEXTS.format(y), "eu-texts",
                                    "year-{0}".format(y), archive=False)
        except (FetchError, ValueError) as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)", (today, "eu-texts", str(exc)))
            conn.commit()
            log("  [gap] eu-texts {0}: {1}".format(y, exc))
            return 0, 0
        items.extend(reply.get("data") or [])
    total = ours = 0
    for a in items:
        date = a.get("document_date")
        # on_day narrows to ONE sitting day (the per-day sweep); otherwise the
        # window runs from cutoff to today as before.
        if not date or (date != on_day if on_day else (date < cutoff or date > today)):
            continue
        title = (a.get("title_dcterms") or {}).get("en")
        if not title:
            continue
        total += 1
        res = filt.filter_item(tax, wl, title)
        areas = res.issue_areas or []
        if areas:
            ours += 1
        conn.execute(
            "INSERT INTO eu_texts (identifier, date, title, procedure, "
            "areas, matched_terms, tier, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(identifier) DO UPDATE SET title=excluded.title, "
            "date=excluded.date, procedure=excluded.procedure, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "tier=excluded.tier, last_seen=excluded.last_seen",
            (a.get("identifier"), date, title, procedure_ref(a),
             json.dumps(areas), json.dumps(res.matched_terms or []),
             res.tier, today, today))
    conn.commit()
    return total, ours


def watchlist_candidates(conn, client, log=print, watched=None):
    """Matched texts whose procedure is real and not yet watched.

    Verification before proposal: the extracted id must resolve in the
    procedures API, so a parsing slip can never propose a phantom dossier.
    Nothing is ADDED here -- a human edits config/eu_watchlist.yaml.
    """
    if watched is None:
        # The real watchlist by default; a test injects its own set so a
        # unit test does not fail the day a human adds a real dossier --
        # which is exactly what happened on 2026-09-06.
        import yaml
        with open(os.path.join(ROOT, "config", "eu_watchlist.yaml"),
                  encoding="utf-8") as fh:
            watched = {d["process_id"] for d in
                       (yaml.safe_load(fh) or {}).get("dossiers") or []}
    rows = conn.execute(
        "SELECT identifier, title, procedure FROM eu_texts "
        "WHERE areas != '[]' AND procedure IS NOT NULL").fetchall()
    out = []
    for r in rows:
        if r["procedure"] in watched:
            continue
        try:
            reply = client.get_json(PROC.format(r["procedure"]), "eu-texts",
                                    "verify-" + r["procedure"],
                                    archive=False)
        except (FetchError, ValueError):
            log("  candidate {0} did not verify; not proposed".format(
                r["procedure"]))
            continue
        data = (reply.get("data") or [{}])[0]
        out.append({"process_id": r["procedure"],
                    "label": data.get("label"),
                    "title": r["title"], "from_text": r["identifier"]})
    return out


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    # --days widens the window (17 Sept 2026). These collectors had a fixed
    # 60-day lookback, so when the 9 Sept store rebuild emptied their tables
    # the July plenary was already out of reach and a plain re-run could not
    # recover it. A gap needs a wider window, the way the Westminster
    # backfills do.
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else WINDOW_DAYS
    total, ours = pull(conn, client, today, days=days)
    print("eu-texts: {0} adopted in the last {1} days, {2} on our ground."
          .format(total, days, ours))
    for r in conn.execute("SELECT * FROM eu_texts WHERE areas != '[]' "
                          "ORDER BY date DESC").fetchall():
        print("  [{0}] {1} - {2}".format(
            ",".join(str(a) for a in json.loads(r["areas"])),
            r["date"], r["title"][:80]))
    cands = watchlist_candidates(conn, client)
    for c in cands:
        print("  WATCHLIST CANDIDATE: {0} ({1}) via {2} - add to "
              "config/eu_watchlist.yaml to track".format(
                  c["process_id"], c["label"], c["from_text"]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
