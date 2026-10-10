#!/usr/bin/env python3
"""Colombia's Corte Constitucional: its exhortations to Congress (X8, CO4).

    python3 tools/co_courts.py                    # the weekly read, one request
    python3 tools/co_courts.py --dry-run          # read and report, store nothing
    python3 tools/co_courts.py --reclassify       # offline, after a taxonomy change
    python3 tools/co_courts.py --db /tmp/co.db    # anywhere but the store

Chris, 10 October 2026: "Colombia: no votes for now (CO3); Court section yes
(CO4)", and constitutional courts as a later phase (X8). In Colombia the
Court is the channel that moves our issues: abortion (C-355 of 2006, C-055
of 2022), euthanasia (C-239 of 1997 to C-164 of 2022), surrogacy (T-968 of
2009, T-127 of 2024) and gender identity (T-033 of 2022) were decided by it,
and each time it then EXHORTED Congress to legislate. docs/colombia-scope.md,
"The Constitutional Court".

THE SOURCE. datos.gov.co `fbtr-7k2r` (attribution: Corte Constitucional),
Socrata, keyless: every judgment carrying an exhortation, one row each, with
the order's text and a link to the judgment's HTML in /relatoria/ (which
robots.txt allows). 203 rows on 10 October 2026, newest SU-313/26 of 23
September 2026. The whole file is one request, read whole every week;
SoQL orders it newest first.

CLASSIFIED ON THE EXHORTATION'S OWN TEXT, the Court's order to the
legislature: never the judgment, which cites every precedent it leans on.
Key: the judgment's number ('C-055/22'). Kind 'exhortation'.

THE PRESS RELEASES (comunicados) ARE NOT READ, AND WHY. The Court's site is
an Angular application: its communiqué list comes from an API that wants a
key embedded in the site's own code (`X-APIWEB-KEY`; /API/ is also
disallowed in robots.txt). Using a key found in a site's code is against
our rules, so that list is out. The PDFs themselves sit under /comunicados/
(allowed), but their names carry the sitting dates in prose
("comunicado-28-septiembre-9-y-10-de-2026.pdf"), so they cannot be found
without the list, and guessing addresses is not reading a source. Recorded
as a gap in docs/colombia-scope.md; the route is to ask the Court for the
list as open data (a request from Chris, not from Claude).

ONE WRITER AT A TIME on data/parl-monitor.db. Exit 3: stored what it could
and recorded gaps.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import courts, db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

CC = "co"
FEED = "co-courts"
COURT = "Corte Constitucional"
SOURCE = "datos.gov.co fbtr-7k2r"
URL = ("https://www.datos.gov.co/resource/fbtr-7k2r.json"
       "?$limit=5000&$order=fecha_sentencia%20DESC")


def parse(records):
    """Socrata rows -> ruling rows (src/courts.py's shape)."""
    out, seen = [], set()
    for r in records or []:
        key = (r.get("sentencia") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        link = r.get("enlace") or {}
        exhorto = courts.flat(r.get("exhorto"))
        out.append({
            "ruling_key": key, "court": COURT, "kind": "exhortation", "case_no": key,
            "date": (r.get("fecha_sentencia") or "")[:10] or None,
            "title": courts.clip(exhorto, 300),
            "summary": exhorto,
            "decision": None,
            "formation": "Addressed to: {0}".format(courts.flat(r.get("entidad")).title())
            if r.get("entidad") else None,
            "url": link.get("url") if isinstance(link, dict) else None,
            "source": SOURCE,
        })
    return out


def pull(conn, client, today, tax, log=print):
    """Returns (read, new, ours, gaps)."""
    try:
        records = client.get_json(URL, FEED, "exhortos")
    except (FetchError, ValueError) as exc:
        db.record_gap(conn, FEED, "exhortations file unreadable: {0}".format(str(exc)[:120]), today)
        return 0, 0, 0, 1
    rows = parse(records)
    if not rows:
        db.record_gap(conn, FEED, "exhortations file parsed to zero rows; its columns may "
                                  "have changed", today)
        return 0, 0, 0, 1
    new = ours = 0
    for row in rows:
        is_new, areas = courts.upsert(conn, CC, row, tax, today)
        new += is_new
        if courts.on_ground(areas):
            ours += 1
            if is_new:
                log("  [court] {0} {1}: {2}".format(row["ruling_key"], areas, row["title"][:70]))
    conn.commit()
    return len(rows), new, ours, 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    tax = courts.load_taxonomy(CC)
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    if args.reclassify:
        print("co-courts: {0} ruling(s) reclassified".format(courts.reclassify(conn, CC, tax)))
        return 0
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0)
    read, new, ours, gaps = pull(conn, client, today, tax)
    print("co-courts: {0} exhortation(s) read, {1} new, {2} on our ground{3}.".format(
        read, new, ours, " (dry run, nothing stored)" if args.dry_run else ""))
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
