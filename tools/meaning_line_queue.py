"""Which unconfirmed division is worth your time next.

    python3 tools/meaning_line_queue.py            # all three legislatures
    python3 tools/meaning_line_queue.py --n 5

A division with no meaning line renders as evidence and places NOBODY. The
backlog is real -- ten at Holyrood, eleven at the Senedd as of 2026-08-24 --
but the gaps are worth wildly different amounts: some would place fifty
sitting members, some three, and one was a National Insurance vote that is
not ours at all.

So this ranks by PLACEMENT VALUE: how many members who still sit would move
off zero if a line existed. That turns an open-ended chore into a queue, and
it is deliberately blunt about the ones not worth reading -- the point is to
spend twenty minutes where they buy the most, not to clear the list.

Reads only. Confirming a line is still a human act, in the stance yaml.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, intel

HIDDEN = {11}


def _shown(raw):
    return [a for a in json.loads(raw or "[]") if a not in HIDDEN]


def holyrood(conn, entries):
    """(reference, title, dated, sitting_voters, areas) for unlined divisions."""
    out = []
    rows = conn.execute(
        "SELECT key, reference, title, dated, areas, tier FROM sp_divisions "
        "WHERE source='votesmotion' AND areas IS NOT NULL AND areas != '[]'"
    ).fetchall()
    for r in rows:
        areas = _shown(r["areas"])
        # Tier 2 is INCLUDED, marked. The monitor does not display tier-2
        # divisions, but the 5CA places on any human-confirmed line whatever
        # the tier -- so excluding them here would hide real opportunities
        # behind a display rule.
        if not areas or str(r["reference"]) in entries:
            continue
        n = conn.execute(
            "SELECT COUNT(*) FROM sp_votes v JOIN sp_members m "
            "ON m.person_id = v.person_id WHERE v.division_key = ? "
            "AND v.vote IN ('Yes','No') AND m.is_current = 1", (r["key"],)
        ).fetchone()[0]
        out.append((n, "Holyrood" + ("" if r["tier"] == 1 else " t2"),
                    r["reference"], r["title"], r["dated"], areas))
    return out


def senedd(conn, entries):
    out = []
    rows = conn.execute(
        "SELECT key, title, dated, areas FROM sd_divisions "
        "WHERE areas IS NOT NULL AND areas != '[]'").fetchall()
    current = {r[0] for r in conn.execute(
        "SELECT name FROM sd_members WHERE end_date IS NULL "
        "OR end_date >= date('now')")}
    for r in rows:
        areas = _shown(r["areas"])
        if not areas or str(r["key"]) in entries:
            continue
        n = sum(1 for v in conn.execute(
            "SELECT member_name, result FROM sd_votes WHERE division_key = ?",
            (r["key"],)) if v[1] in ("For", "Against") and v[0] in current)
        out.append((n, "Senedd", r["key"], r["title"], r["dated"], areas))
    return out


def main():
    n_show = 12
    if "--n" in sys.argv:
        n_show = int(sys.argv[sys.argv.index("--n") + 1])
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))

    import sd_5ca, sp_5ca
    rows = (holyrood(conn, sp_5ca.load_stance(section="divisions"))
            + senedd(conn, sd_5ca.load_stance()))
    rows.sort(reverse=True)

    placing = [r for r in rows if r[0] > 0]
    print("MEANING-LINE QUEUE    {0} division(s) on our ground with no line"
          .format(len(rows)))
    print("Ranked by how many SITTING members a line would place. A division")
    print("whose voters have all left places nobody now, whatever it meant.\n")
    for count, where, ref, title, dated, areas in rows[:n_show]:
        print("  {0:>3} member(s)  {1:<9} {2}  {3}".format(
            count, where, dated, str(ref)[:14]))
        print("               {0}".format((title or "")[:64]))
        print("               areas: {0}".format(
            ", ".join(names.get(a, str(a)) for a in areas)))
    if len(rows) > n_show:
        print("\n  ...and {0} more, all placing fewer than {1}."
              .format(len(rows) - n_show, rows[n_show - 1][0]))
    print("\n{0} of {1} would place at least one sitting member; the other "
          "{2} are\nrecord only -- their voters have gone.".format(
              len(placing), len(rows), len(rows) - len(placing)))
    print("Confirming a line stays a human act: read the division, then "
          "write it\ninto config/sp_stance.yaml or config/sd_stance.yaml.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
