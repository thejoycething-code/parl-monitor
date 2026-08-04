"""Capture Lords isWhipped flags into the division_whip table.

    python3 tools/annotate_whips.py

The Lords votes API states explicitly whether each division was whipped;
the Commons API does not (Commons free votes are covered by the
conscience-convention list in config/stance_overrides.yaml). Reads the
archived detail payloads in data/raw -- no refetching. Idempotent.
"""

from __future__ import annotations

import glob
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, stance


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    stance.ensure_whip_table(conn)
    n = {True: 0, False: 0}
    for path in glob.glob(os.path.join(ROOT, "data", "raw", "*", "division_ldetail-*.json.gz")):
        with gzip.open(path, "rb") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
        whipped = payload.get("isWhipped")
        div_id = payload.get("divisionId")
        if whipped is None or div_id is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO division_whip (ref_base, whipped) VALUES (?, ?)",
            ("div:l{0}".format(div_id), 1 if whipped else 0))
        n[bool(whipped)] += 1
    conn.commit()
    print("division_whip: {0} whipped, {1} free (Lords)".format(n[True], n[False]))
    conn.close()


if __name__ == "__main__":
    main()
