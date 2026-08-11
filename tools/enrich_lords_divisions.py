"""Backfill Lords division motion notes into the ledger and reset their scores.

    python3 tools/enrich_lords_divisions.py           # dry run: report only
    python3 tools/enrich_lords_divisions.py --apply   # write + clear stance rows

Lords division titles name the bill, not the question: "Online Safety Bill"
was really Baroness Kidron's amendment 35, and an Aye there meant widening
the Act. The stance classifier only ever saw the title, so amendment votes
were read as verdicts on the bill (found 2026-08-11 preparing the OSA
committee briefing: the engine had inverted several peers).

This tool reads the cached division detail files (data/raw/*/division_
ldetail-*.json.gz -- no network), writes each division's cleaned motion
notes into mp_events.excerpt for both direction refs, and deletes the
stance rows of every ref whose evidence just changed, so the next scoring
pass re-classifies them with the actual question in front of it.

Divisions with no motion notes (straight bill votes) are left alone: their
titles were the question, and their scores stand.
"""

from __future__ import annotations

import glob
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.ingest.divisions import clean_motion_notes


def cached_notes():
    """{division_id: notes} from every cached Lords detail file, newest wins."""
    notes = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*",
                                              "division_ldetail-*.json.gz"))):
        try:
            payload = json.load(gzip.open(path))
        except Exception:
            continue
        did = payload.get("divisionId") or payload.get("DivisionId")
        if not did:
            continue
        cleaned = clean_motion_notes(payload.get("amendmentMotionNotes")
                                     or payload.get("AmendmentMotionNotes"))
        notes[int(did)] = cleaned
    return notes


def main():
    apply = "--apply" in sys.argv
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    ledger_ids = sorted({int(r["ref"].split(":")[1][1:]) for r in conn.execute(
        "SELECT DISTINCT ref FROM mp_events WHERE ref LIKE 'div:l%'").fetchall()})
    notes = cached_notes()

    with_notes, without, missing = [], [], []
    for did in ledger_ids:
        if did not in notes:
            missing.append(did)
        elif notes[did]:
            with_notes.append(did)
        else:
            without.append(did)

    print("ledger Lords divisions: {0}".format(len(ledger_ids)))
    print("  with motion notes:    {0}  (excerpts written, scores reset)".format(len(with_notes)))
    print("  without notes:        {0}  (straight votes; untouched)".format(len(without)))
    if missing:
        print("  NO CACHED DETAIL:     {0}  {1}".format(len(missing), missing))

    if not apply:
        print("\ndry run; use --apply to write")
        return

    events = refs = 0
    for did in with_notes:
        for side in ("aye", "no"):
            ref = "div:l{0}:{1}".format(did, side)
            cur = conn.execute("UPDATE mp_events SET excerpt = ? WHERE ref = ?",
                               (notes[did], ref))
            events += cur.rowcount
            refs += conn.execute("DELETE FROM stance WHERE ref = ?", (ref,)).rowcount
    conn.commit()
    print("\nexcerpts written on {0} events; {1} stance rows cleared for "
          "re-scoring".format(events, refs))
    print("run the scoring pass next (run_stance_pass, or the weekly pull "
          "picks them up)")


if __name__ == "__main__":
    main()
