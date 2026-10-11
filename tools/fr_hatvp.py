#!/usr/bin/env python3
"""France: the HATVP's declarations of interests and activities of sitting
députés and sénateurs, the declarant's own items only (src/fr_hatvp.py).

    python3 tools/fr_hatvp.py                    # the monthly step of jobs/fr-weekly.sh
    python3 tools/fr_hatvp.py --force            # check now, whatever the date
    python3 tools/fr_hatvp.py --xml F --csv F    # parse local copies (no request)
    python3 tools/fr_hatvp.py --db /tmp/fr.db    # a scratch store

At most every four weeks (src/fr_hatvp.STALE_DAYS) it asks the HATVP whether
declarations.xml changed (If-Modified-Since); only when it did does it
download the 80 MB file and the CSV index, stream-parse the XML, and replace
the 'fr-hatvp' rows of mi_interests, which the member profiles show as
"Declared interests" with the declaration date and the HATVP page. The XML
is never archived (it holds spouses' data); spouses' and collaborators'
sections are skipped at parse time and never logged. Nothing is posted or
DMed.

Exit 0 when read, unchanged or not due; 3 on a gap (its [gap] line printed,
last run's rows kept): the weekly job treats it as a gap, never a failure.
"""

from __future__ import annotations

import argparse
import datetime
import io
import os
import sqlite3
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import fr_hatvp as hv  # noqa: E402
from src import member_intel as mi  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402


def load(conn, xml_stream, csv_text, today, log=print):
    """Parse and replace the rows. Returns the stats."""
    members = hv.sitting(conn)
    if not members:
        raise ValueError("no sitting French members in the store (fr_members); nothing matched")
    index = hv.parse_index(csv_text)
    rows, stats = hv.interests(hv.parse_declarations(xml_stream), index, members)
    note = ("{members} sitting member(s) from {declarations} parliamentary declaration(s): "
            "{by_id} by HATVP id, {by_name} by name and mandate; {unmatched} not sitting "
            "or not matched".format(**stats))
    mi.replace(conn, "fr", hv.SOURCE, today, interests=rows, full=True, note=note)
    log("fr-hatvp: {0} interest(s) kept; {1}. Spouses', collaborators' and asset "
        "sections skipped at parse time.".format(stats["interests"], note))
    return stats


def run(conn, client, today, force=False, log=print):
    ok, why = hv.due(conn, today)
    if not ok and not force:
        log("fr-hatvp: not due ({0})".format(why))
        return 0
    headers = hv.conditional_headers(conn)
    try:
        if headers:
            raw = client.get_bytes(hv.XML_URL, hv.FEED, "declarations", headers=headers,
                                   timeout=600)
        else:
            raw = client.get_bytes(hv.XML_URL, hv.FEED, "declarations", archive=False,
                                   timeout=600)
    except FetchError as exc:
        if getattr(exc.cause, "code", None) == 304:
            hv.record(conn, today)
            log("fr-hatvp: declarations.xml unchanged since {0}; nothing read".format(
                headers.get("If-Modified-Since") or "the last download"))
            return 0
        raise
    got_headers = dict(client.last_headers or {})
    csv_raw = client.get_bytes(hv.CSV_URL, hv.FEED, "liste", archive=False, timeout=120)
    csv_text = csv_raw.decode("utf-8", errors="replace")
    # The archive keeps the CSV's parliamentary rows only (declarants' own
    # names, mandates, dates, links); never the XML.
    client.archive(hv.parliamentary_rows(csv_text).encode("utf-8"), hv.FEED, "liste-parlement")
    load(conn, io.BytesIO(raw), csv_text, today, log=log)
    del raw
    hv.record(conn, today, got_headers, fetched=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--force", action="store_true", help="check now, whatever the date")
    ap.add_argument("--xml", help="a local declarations.xml (no request)")
    ap.add_argument("--csv", help="a local liste.csv (with --xml)")
    args = ap.parse_args(argv)
    conn = mi.ensure(sqlite3.connect(args.db))
    try:
        if args.xml:
            if not args.csv:
                ap.error("--xml needs --csv")
            with open(args.csv, encoding="utf-8") as fh:
                csv_text = fh.read()
            with open(args.xml, "rb") as fh:
                load(conn, fh, csv_text, args.date)
            return 0
        return run(conn, HttpClient(raw_dir=args.raw), args.date, force=args.force)
    except (FetchError, ValueError, KeyError, sqlite3.Error) as exc:
        print("  [gap] fr-hatvp: {0}; last run's rows kept".format(str(exc)[:200]))
        return 3
    except Exception:  # never the weekly's failure
        traceback.print_exc()
        print("  [gap] fr-hatvp: failed; last run's rows kept")
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
