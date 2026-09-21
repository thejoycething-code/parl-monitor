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
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, eugate, intel

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


CONSENSUS_FLOOR = 0.10   # losing side below this share of votes cast: record only


def band(withs, againsts):
    """The 5CA column, exactly as tools/make_eu_5ca.py draws it."""
    if withs and not againsts:
        return "++" if withs >= 2 else "+"
    if againsts and not withs:
        return "--"
    if withs and againsts:
        return "-"
    return "0"


def european(conn, n_show=6):
    """The EU arm, ranked by MOVEMENT (20 September 2026).

    The first cut (17 September) ranked by marginal placement: how many MEPs a
    line would move off zero. Nine sign-offs later every voting MEP is placed
    by at least one signed division, so that number is 0 for all 216 groups
    and the order had fallen back to turnout, which put a migration text on
    top. What varies now is how many members a sign-off would move BETWEEN
    5CA bands: 0 -> +, + -> ++, + -> - (an ally shown against us), -- -> -.
    The direction is not known before the human signs, so both sides are
    simulated and the larger movement leads, with the side named.

    One report still generates dozens of roll calls, so near-identical labels
    are grouped and the member of each family that moves the most is shown;
    that is the vote on the text as a whole only when no split says more.

    Returns ([((moves, turnout, vote_id, label, date, areas, tally, side,
    detail), splits_hidden), ...], total_unsigned_on_ground).
    """
    import yaml
    path = os.path.join(ROOT, "config", "eu_divisions.yaml")
    cfg = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get(
        "divisions") or {} if os.path.exists(path) else {}
    signed = {v: c["our_side"] for v, c in cfg.items()
              if c.get("signed_off") and c.get("our_side")}
    votes = {}
    for r in conn.execute("SELECT vote_id, person_id, position FROM eu_votes"):
        votes.setdefault(r[0], {})[r[1]] = r[2]
    base = {}
    for vote_id, side in signed.items():
        for pid, pos in (votes.get(vote_id) or {}).items():
            if pos == "abstention":
                continue
            w, a = base.get(pid, (0, 0))
            if (pos == "favor") == (side == "favor"):
                base[pid] = (w + 1, a)
            else:
                base[pid] = (w, a + 1)
    groups = {}
    for r in conn.execute(
            "SELECT vote_id, date, label, favor, against, abstention, areas "
            "FROM eu_divisions WHERE areas IS NOT NULL AND areas != '[]' AND "
            + eugate.SHOWN_SQL):
        if r["vote_id"] in signed:
            continue
        areas = _shown(r["areas"])
        if not areas:
            continue
        turnout = (r["favor"] or 0) + (r["against"] or 0) + (r["abstention"] or 0)
        # A consensus vote discriminates nobody (20 Sept 2026): 601-46 on the
        # gender-and-health text led the queue because signing it would turn
        # every placed opponent who voted with the House into "mixed", which
        # is a band change with nothing in it. Under a tenth on the losing
        # side and the vote is record only, whatever it meant.
        cast = (r["favor"] or 0) + (r["against"] or 0)
        if cast and min(r["favor"] or 0, r["against"] or 0) < cast * CONSENSUS_FLOOR:
            continue
        # Both sides simulated. The side that leads is the one CONSISTENT with
        # the placements already made -- fewer members pulled from a pure band
        # (++, +, --) into "-" -- because the other side's count is not
        # information, it is the coalition being shredded: the first cut ranked
        # on the larger movement and every line at the top read "++ -> - 100".
        # The contradictions on the consistent side are reported too; a vote
        # that contradicts heavily either way is cross-cutting, and the reader
        # should know that before signing it.
        sides = []
        for side in ("favor", "against"):
            trans = {}
            for pid, pos in (votes.get(r["vote_id"]) or {}).items():
                if pos == "abstention":
                    continue
                w, a = base.get(pid, (0, 0))
                before = band(w, a)
                if (pos == "favor") == (side == "favor"):
                    after = band(w + 1, a)
                else:
                    after = band(w, a + 1)
                if after != before:
                    k = before + "\u2192" + after
                    trans[k] = trans.get(k, 0) + 1
            contradict = sum(n for k, n in trans.items()
                             if k.endswith("\u2192-") and not k.startswith("0"))
            detail = ", ".join("{0} {1}".format(k, n) for k, n in
                               sorted(trans.items(), key=lambda x: -x[1])[:3])
            sides.append((contradict, side != "favor", sum(trans.values()), side, detail))
        sides.sort()
        contradict, _, moves, side, detail = sides[0]
        if contradict:
            detail += "; {0} would contradict their placement".format(contradict)
        best = (moves, side, detail)
        stem = re.split(r"\s+[-\u2013\u2014]\s+", r["label"] or "")[0][:70]
        entry = (best[0], turnout, r["vote_id"], r["label"] or "", r["date"], areas,
                 "%s-%s-%s" % (r["favor"], r["against"], r["abstention"]), best[1], best[2])
        groups.setdefault((r["date"], stem), []).append(entry)
    out = []
    for (date, stem), entries in groups.items():
        # The family's STRONGEST vote leads, not its biggest (20 Sept 2026):
        # the Cyprus resolution's abortion words moved far more members than
        # its 575-33 vote on the text as a whole, and sat hidden under it.
        entries.sort(key=lambda e: (-e[0], -e[1]))
        out.append((entries[0], len(entries) - 1))
    out.sort(key=lambda x: (-x[0][0], -x[0][1]))
    return out[:n_show], sum(len(v) for v in groups.values())


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

    try:
        eu_rows, eu_total = european(conn)
    except sqlite3.Error:
        eu_rows, eu_total = [], 0
    if eu_total:
        print("\n\nEUROPEAN PARLIAMENT    {0} roll call(s) on our ground with no "
              "verdict".format(eu_total))
        print("Ranked by MEPs a sign-off would move between 5CA bands (both sides")
        print("simulated; the larger movement leads). Splits of one report are grouped.\n")
        for (n, turnout, vote_id, label, date, areas, tally, side, detail), rest in eu_rows:
            print("  {0:>3} MEP(s) move  {1}  {2}".format(n, date, vote_id))
            print("              {0}".format(label[:64]))
            print("              {0} favor-against-abstention, areas: {1}{2}".format(
                tally, ", ".join(names.get(a, str(a)) for a in areas),
                "" if not rest else "; {0} more split(s) of the same text".format(rest)))
            if n:
                print("              if our side is {0}: {1}".format(side, detail))
        print("\n  Sign one into config/eu_divisions.yaml with our_side and both "
              "meaning\n  lines, read from the decision event, never the list title.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
