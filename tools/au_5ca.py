#!/usr/bin/env python3
"""A 5CA sheet for the Federal Parliament of Australia: one chamber, one area, CSV.

    python3 tools/au_5ca.py --area 5                    # House of Representatives
    python3 tools/au_5ca.py --area 5 --chamber senate
    python3 tools/au_5ca.py --all                       # every 5CA area, both chambers
    python3 tools/au_5ca.py --all --db /tmp/au.db --out-dir /tmp/5ca
    python3 tools/au_5ca.py --signoff-doc               # write docs/5ca-au-readings.md
    python3 tools/au_5ca.py --sign-from-doc             # apply its ticked boxes

Reads the store only; fetches nothing and posts nothing. The Australian
mirror of tools/ca_5ca.py, with the shared parts in src/readings5ca.py.

HOW A COLUMN GETS FILLED. config/au_stance.yaml is where a HUMAN writes what
an Aye on one division meant (`yea:`) and a No (`nay:`). An entry carrying
`draft: true` places NOBODY. Every entry was drafted by Claude on 9 October
2026 and none is signed, so every column is 0 and each sheet ends with a row
saying so.

What can place a member, once a reading is signed: a recorded VOTE, Aye or
No (weight 5). Nothing else: au_bills carries no sponsor, and the store holds
no speeches by member.

PAIRS ARE NOT A POSITION. Hansard lists who was paired but not which side
each partner was on (tools/au_rollcalls.py stores both as 'Paired', never
guessing), and the rest of the repo treats a pair as no direction recorded
(tools/ca_5ca.py). So a pair is listed in Comments and places nobody; a member
at ++ who was paired on the latest decisive signed division is capped at +,
like any member with no Aye or No on it. In the Senate pairs are common (11 a
side on some sex-discrimination votes), so this matters.

WHICH DIVISIONS ARE LISTED: those whose own text matched the area, and any the
stance file reads.

THE ABSENCE RULE: a member at ++ who held the seat on the date of the area's
latest DECISIVE signed division (our side +2) but recorded no Aye or No on it
is capped at +. Hansard lists only those who voted or paired.

Output: <out-dir>/au-5ca-<house|senate>-<area-slug>.csv, a stable name per sheet.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_store, db, intel  # noqa: E402
from src import readings5ca as r5  # noqa: E402

STANCE_PATH = os.path.join(ROOT, "config", "au_stance.yaml")
DOC_PATH = os.path.join(ROOT, "docs", "5ca-au-readings.md")
OUT_DIR = os.path.join(ROOT, "data", "5ca")
WEIGHTS = {"vote": 5}
SIDE = {"Aye": "yea", "No": "nay"}
LABELS = {"yea": "Aye", "nay": "No"}


def _areas(text):
    return json.loads(text or "[]")


def listed(d, area, entries):
    if area not in _areas(d["areas"]):
        return False
    return d["division_key"] in entries or area in _areas(d["own_areas"])


def offices(conn, chamber):
    """{person_id: [(from, to)]} in this chamber."""
    out = {}
    for o in conn.execute("SELECT person_id, from_date, to_date FROM au_offices WHERE house=?",
                          (chamber,)):
        out.setdefault(o["person_id"], []).append((o["from_date"] or "", o["to_date"] or "9999"))
    return out


def held_seat(spells, date):
    return any(f <= date <= t for f, t in spells or ())


def build_rows(conn, area, chamber, entries, today=None):
    today = today or datetime.date.today().isoformat()
    members = {r["person_id"]: dict(r) for r in conn.execute("SELECT * FROM au_members")}
    sitting = {k for k, m in members.items() if m["house"] == chamber and m["current"]}
    spells = offices(conn, chamber)
    divisions = [dict(r) for r in conn.execute(
        "SELECT * FROM au_divisions WHERE chamber=? ORDER BY date, number", (chamber,))]
    divisions = [d for d in divisions if listed(d, area, entries)]
    votes = {d["division_key"]: {r["person_id"]: (r["position"], r["party"]) for r in conn.execute(
        "SELECT person_id, position, party FROM au_votes WHERE division_key=?", (d["division_key"],))}
        for d in divisions}

    per = {}

    def rec(pid):
        return per.setdefault(pid, {"scored": [], "lines": [], "voted": False})

    for pid in sitting:
        rec(pid)
    for d in divisions:
        entry = entries.get(d["division_key"])
        base = "{0} {1}: {2} (Ayes {3}, Noes {4})".format(
            d["date"], r5.clip(d["minor_heading"] or d["major_heading"], 80),
            r5.clip(d["question"] or d["motion"], 90),
            d["ayes"] if d["ayes"] is not None else "?", d["noes"] if d["noes"] is not None else "?")
        for pid, (position, party) in votes[d["division_key"]].items():
            r = rec(pid)
            label = "VOTE {0} ({1}): {2}".format((position or "?").upper(), party or "?", base)
            if position not in SIDE:
                r["lines"].append(label + " [paired: side not published, no direction]")
                continue
            r["voted"] = True
            s, why = r5.value(entry, SIDE[position])
            if s is not None:
                r["scored"].append((s, d["date"] or "", label, "vote"))
                r["lines"].append("{0} [{1:+d}: {2}]".format(label, s, r5.clip(why, 120)))
            else:
                r["lines"].append("{0} [{1}]".format(label, r5.not_placed(entry)))
        for pid in sitting:
            if pid not in votes[d["division_key"]] and held_seat(spells.get(pid), d["date"]):
                rec(pid)["lines"].append("{0} NO RECORDED VOTE: {1}".format(
                    d["date"], r5.clip(d["minor_heading"], 70)))

    decisive = r5.decisive(divisions, entries)
    latest = decisive[-1] if decisive else None
    rows = []
    for pid, r in per.items():
        m = members.get(pid) or {}
        is_sitting = pid in sitting
        if not is_sitting and not r["voted"]:
            continue
        cap = None
        if latest is not None:
            got = votes[latest["division_key"]].get(pid, (None,))[0]
            if got not in SIDE and (got == "Paired" or held_seat(spells.get(pid), latest["date"])):
                cap = ("CAPPED at +: no Aye/No on the latest signed decisive division ({0}, {1}){2}. "
                       "++ means 'will vote with us'; a member who missed it is the contact "
                       "list.".format(latest["date"], r5.clip(latest["minor_heading"], 60),
                                      " -- paired" if got == "Paired" else ""))
        rows.append(r5.finish_row(pid, r["lines"], r["scored"], WEIGHTS, m.get("name"),
                                  m.get("party"), m.get("electorate"), is_sitting,
                                  cap_note=cap, today=today))
    return r5.sort_rows(rows), divisions, latest


def run(conn, area, chamber, entries, names, out_dir, log=print):
    rows, divisions, latest = build_rows(conn, area, chamber, entries)
    if not any(r["n_events"] for r in rows):
        return None
    name = names.get(area, "area {0}".format(area))
    path = os.path.join(out_dir, "au-5ca-{0}-{1}.csv".format(chamber, r5.slug(name)))
    signed, unsigned = r5.area_counts(divisions, entries)
    tally = r5.write_sheet(path, rows, r5.readings_line(signed, unsigned, name))
    sitting = [r for r in rows if r["sitting"]]
    log("{0} {1}: {2} sitting (+{3} former), {4} with evidence, {5} placed; {6} division(s), "
        "readings {7} signed / {8} unsigned -> {9}".format(
            chamber, name, len(sitting), len(rows) - len(sitting),
            sum(1 for r in rows if r["n_events"]), sum(1 for r in sitting if r["column"] != "0"),
            len(divisions), signed, unsigned,
            os.path.relpath(path, ROOT) if path.startswith(ROOT) else path))
    log("    " + "  ".join("{0} x{1}".format(c, tally[c]) for c in r5.COLUMNS))
    if latest is not None:
        e = entries[latest["division_key"]]
        ours = "Aye" if (e.get("yea") or 0) > (e.get("nay") or 0) else "No"
        lobby = conn.execute("SELECT COUNT(*) FROM au_votes WHERE division_key=? AND position=?",
                             (latest["division_key"], ours)).fetchone()[0]
        pp = sum(1 for r in sitting if r["column"] == "++")
        log("    check: sitting ++ {0} against our lobby of {1} on {2}{3}".format(
            pp, lobby, latest["division_key"], "  <-- ++ EXCEEDS our lobby" if pp > lobby else ""))
    return path


INTRO = """Every reading below was DRAFTED by Claude on 9 October 2026 from the store
(au_divisions, au_votes) and the motion text Hansard printed before each
division. None is signed, so `tools/au_5ca.py` places nobody yet: every
sheet in data/5ca/au-5ca-*.csv is an evidence list ending "NO SIGNED
READINGS".

Aye is written `yea:`, No `nay:`. A PAIR places nobody: Hansard does not say
which side each partner was on. Most Senate divisions on our ground are on
whether a private senator's bill may be introduced or restored to the Notice
Paper, not on its merits; those are drafted at +/-1."""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", type=int)
    ap.add_argument("--all", action="store_true", help="every 5CA area, both chambers")
    ap.add_argument("--chamber", choices=("house", "senate"), default="house")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--stance", default=STANCE_PATH)
    ap.add_argument("--signoff-doc", nargs="?", const=DOC_PATH, metavar="PATH")
    ap.add_argument("--sign-from-doc", nargs="?", const=DOC_PATH, metavar="PATH")
    args = ap.parse_args()
    entries = r5.load_stance(args.stance, "divisions")
    if args.sign_from_doc:
        r5.sign_from_doc(args.stance, args.sign_from_doc)
        return 0
    if args.signoff_doc:
        with open(args.signoff_doc, "w", encoding="utf-8") as h:
            h.write(r5.signoff_markdown("Australian Parliament 5CA: readings to sign", INTRO,
                                        LABELS, entries, {}, "config/au_stance.yaml"))
        print("wrote {0}: {1} division readings".format(args.signoff_doc, len(entries)))
        return 0
    if not args.all and args.area is None:
        ap.error("--area N, --all, --signoff-doc or --sign-from-doc")
    excluded = r5.excluded_areas(ROOT)
    if args.area in excluded:
        print("area {0} is collated only, not a 5CA area".format(args.area))
        return 1
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    conn = au_store.ensure_schema(db.init_db(db.connect(args.db)))
    areas = sorted(a for a in names if a not in excluded) if args.all else [args.area]
    chambers = ("house", "senate") if args.all else (args.chamber,)
    written = 0
    for chamber in chambers:
        for area in areas:
            written += run(conn, area, chamber, entries, names, args.out_dir) is not None
    counts = r5.file_counts(entries)
    print("\n{0} sheet(s). config/au_stance.yaml: {confirmed} signed, {unplaceable} signed "
          "evidence-only, {draft} DRAFT (unsigned), {unread} unread.".format(written, **counts))
    if not counts["confirmed"]:
        print("  NO SIGNED READINGS: nobody is placed; every sheet is an evidence list.\n"
              "  Sign in docs/5ca-au-readings.md, then --sign-from-doc.")
    print("  Target is blank: the campaigner's call. Never posted anywhere.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
