#!/usr/bin/env python3
"""A 5CA sheet for the US Congress: one chamber, one issue area, CSV.

    python3 tools/us_5ca.py --area 1                    # House, abortion
    python3 tools/us_5ca.py --area 5 --chamber senate
    python3 tools/us_5ca.py --all                       # every 5CA area, both chambers
    python3 tools/us_5ca.py --all --db /tmp/us.db --out-dir /tmp/5ca
    python3 tools/us_5ca.py --signoff-doc               # write docs/5ca-us-readings.md
    python3 tools/us_5ca.py --sign-from-doc             # apply its ticked boxes

Reads the store only; fetches nothing and posts nothing. The US mirror of
tools/ca_5ca.py (Christopher, 9 October 2026: "5CA parity for the US
Congress"), with the shared parts in src/readings5ca.py.

HOW A COLUMN GETS FILLED. config/us_stance.yaml is where a HUMAN writes what a
Yea on one roll call meant, and this tool applies it. An entry carrying
`draft: true` places NOBODY. Every entry was drafted by Claude on 9 October
2026 and none is signed, so until Christopher signs readings every column is
0 and each sheet ends with a row saying so: an evidence list, not a guess.

What can place a member, once a reading is signed:
  * a recorded VOTE, Yea or Nay (weight 5), in the House or the Senate;
  * SPONSORING a bill (weight 3): introducing a text is a chosen act;
  * COSPONSORING a bill (weight 2): a public, recorded position, just under a
    vote in the evidence hierarchy (docs/us-scope.md). A withdrawn
    cosponsorship is listed as a public reversal and never places anyone.
What never places anyone:
  * PRESENT and NOT VOTING: no direction recorded;
  * floor SPEECHES from the Congressional Record (us_record_speeches): activity,
    not direction, counted per member.

WHICH ROLL CALLS ARE LISTED. A roll call is evidence on an area when its OWN
text (the amendment purpose, for a House amendment vote) matched the area, or
the stance file reads it, or it is a passage-type vote (passage, suspension,
concurrence) on a bill the stance file reads. A roll call that only BORROWS
the area from its bill is otherwise left off: the procedural tail of an
omnibus (47 Senate votes on H.R. 1, every appropriations passage) would bury
the votes that matter. Reading a bill in the stance file brings its passage
votes onto the sheet.

THE ABSENCE RULE (Westminster, 21 September 2026): a member at ++ who was in
the chamber for the area's latest DECISIVE signed roll call (our side +2) but
cast no Yea or Nay on it is capped at +, with the reason in Comments.

Party: the column is the member's latest; each vote line carries the party AT
THE VOTE. Everyone who voted on the area is listed; members no longer in the
chamber are labelled FORMER and not counted in the totals. Sitting means on
the chamber's latest roll call (the Clerk and the Senate list every member,
Not Voting included).

Output: <out-dir>/us-5ca-<chamber>-<area-slug>.csv, a stable name per sheet.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, us_store  # noqa: E402
from src import readings5ca as r5  # noqa: E402

STANCE_PATH = os.path.join(ROOT, "config", "us_stance.yaml")
DOC_PATH = os.path.join(ROOT, "docs", "5ca-us-readings.md")
OUT_DIR = os.path.join(ROOT, "data", "5ca")
WEIGHTS = {"vote": 5, "sponsored": 3, "cosponsored": 2}
DIRECTIONAL = ("Yea", "Nay")
PASSAGE = ("passage", "suspend the rules and pass", "concur", "suspend the rules and agree")
LABELS = {"yea": "Yea", "nay": "Nay"}


def _areas(text):
    return json.loads(text or "[]")


def listed(d, area, entries, bill_entries=None):
    """Is this roll call evidence on the area? (module docstring)."""
    if area not in _areas(d["areas"]):
        return False
    if d["division_key"] in entries:
        return True
    if area in _areas(d["own_areas"]):
        return True
    q = (d["question"] or "").lower()
    return d["bill_key"] in (bill_entries or {}) and any(p in q for p in PASSAGE)


def bill_label(key):
    """'119/hr/21' -> 'H.R. 21'."""
    try:
        _c, kind, num = key.split("/")
    except ValueError:
        return key or ""
    names = {"hr": "H.R.", "s": "S.", "hres": "H.Res.", "sres": "S.Res.", "hjres": "H.J.Res.",
             "sjres": "S.J.Res.", "hconres": "H.Con.Res.", "sconres": "S.Con.Res."}
    return "{0} {1}".format(names.get(kind, kind.upper()), num)


def chamber_roster(conn, chamber):
    """({bioguide: member row}, sitting set): sitting = on the latest roll call."""
    latest = conn.execute("SELECT division_key FROM us_divisions WHERE chamber=? "
                          "ORDER BY date DESC, roll DESC LIMIT 1", (chamber,)).fetchone()
    sitting = {r[0] for r in conn.execute("SELECT bioguide FROM us_votes WHERE division_key=?",
                                          (latest[0],))} if latest else set()
    members = {r["bioguide"]: dict(r) for r in conn.execute("SELECT * FROM us_members")}
    return members, sitting


def build_rows(conn, area, chamber, entries, bill_entries, today=None):
    today = today or datetime.date.today().isoformat()
    members, sitting = chamber_roster(conn, chamber)
    divisions = [dict(r) for r in conn.execute(
        "SELECT * FROM us_divisions WHERE chamber=? ORDER BY date, roll", (chamber,))]
    divisions = [d for d in divisions if listed(d, area, entries, bill_entries)]
    votes = {d["division_key"]: {r["bioguide"]: (r["position"], r["party"]) for r in conn.execute(
        "SELECT bioguide, position, party FROM us_votes WHERE division_key=?", (d["division_key"],))}
        for d in divisions}

    per = {}

    def rec(pid):
        return per.setdefault(pid, {"scored": [], "lines": [], "voted": False, "cosponsored": 0})

    for pid in sitting:
        rec(pid)

    for d in divisions:
        entry = entries.get(d["division_key"])
        what = d["amendment_author"] or bill_label(d["bill_key"])
        base = "{0} {1} {2}: {3} ({4} {5}-{6})".format(
            (d["date"] or "?")[:10], what, r5.clip(d["question"], 50),
            r5.clip(d["amendment_text"] or d["description"], 90), r5.clip(d["result"], 30),
            d["yeas"] if d["yeas"] is not None else "?", d["nays"] if d["nays"] is not None else "?")
        for pid, (position, party) in votes[d["division_key"]].items():
            r = rec(pid)
            if position not in DIRECTIONAL:
                r["lines"].append("{0} {1}: {2} [no direction recorded]".format(
                    (d["date"] or "?")[:10], (position or "?").upper(), base[11:]))
                continue
            r["voted"] = True
            label = "VOTE {0} ({1}): {2}".format(position.upper(), party or "?", base)
            side = "yea" if position == "Yea" else "nay"
            s, why = r5.value(entry, side)
            if s is not None:
                r["scored"].append((s, d["date"] or "", label, "vote"))
                r["lines"].append("{0} [{1:+d}: {2}]".format(label, s, r5.clip(why, 120)))
            else:
                r["lines"].append("{0} [{1}]".format(label, r5.not_placed(entry)))

    # Sponsorship and cosponsorship of bills on the area.
    bills = {r["bill_key"]: dict(r) for r in conn.execute(
        "SELECT bill_key, title, sponsor, introduced, areas, triage_score, cosponsors FROM us_bills")
        if area in _areas(r["areas"])}
    unread = {}
    for key, b in bills.items():
        entry = bill_entries.get(key)
        acts = []
        if b["sponsor"]:
            acts.append((b["sponsor"], "sponsored", b["introduced"], None))
        for c in conn.execute("SELECT bioguide, sponsored_at, withdrawn_at FROM us_cosponsors "
                              "WHERE bill_key=?", (key,)):
            acts.append((c["bioguide"], "cosponsored", c["sponsored_at"], c["withdrawn_at"]))
        for pid, kind, when, withdrawn in acts:
            if pid not in per and pid not in sitting:
                continue          # a former member of either chamber with no vote here
            r = rec(pid)
            if kind == "cosponsored" and not withdrawn:
                r["cosponsored"] += 1
            label = "{0} {1} {2} {3}".format((when or "?")[:10], kind.upper(), bill_label(key),
                                             r5.clip(b["title"], 70))
            if withdrawn:
                r["lines"].append("{0} WITHDREW cosponsorship of {1} {2} (cosponsored {3}) "
                                  "[a public reversal; never places]".format(
                                      withdrawn[:10], bill_label(key), r5.clip(b["title"], 60),
                                      (when or "?")[:10]))
                continue
            if entry is None:
                unread.setdefault(pid, []).append((b, kind, when))
                continue
            s, why = r5.value(entry, kind)
            if s is not None:
                r["scored"].append((s, when or "", label, kind))
                r["lines"].append("{0} [{1:+d}: {2}]".format(label, s, r5.clip(why, 120)))
            else:
                r["lines"].append("{0} [{1}]".format(label, r5.not_placed(entry)))
    # Bills nobody has read yet: one line per member, the judge's strongest first.
    for pid, items in unread.items():
        items.sort(key=lambda x: (-(x[0]["triage_score"] or 0), -(x[0]["cosponsors"] or 0)))
        shown = "; ".join("{0} {1}{2}".format(
            bill_label(b["bill_key"]), r5.clip(b["title"], 45),
            " (sponsor)" if kind == "sponsored" else "") for b, kind, _w in items[:6])
        more = len(items) - 6
        latest = max((w or "" for _b, _k, w in items), default="")
        rec(pid)["lines"].append("{0} (CO)SPONSORED {1} bill(s) on the area with no reading: {2}{3} "
                                 "[no reading -- not placed]".format(
                                     latest[:10] or "?", len(items), shown,
                                     "; and {0} more".format(more) if more > 0 else ""))

    # Floor speeches: activity, never direction. One line per member.
    speeches = {}
    for s in conn.execute("SELECT bioguide, date, title, areas FROM us_record_speeches WHERE "
                          "bioguide IS NOT NULL AND chamber=?", (chamber,)):
        if area in _areas(s["areas"]):
            speeches.setdefault(s["bioguide"], []).append(s)
    for pid, rows in speeches.items():
        if pid not in per and pid not in sitting:
            continue
        rows.sort(key=lambda s: s["date"] or "")
        last = rows[-1]
        rec(pid)["lines"].append("{0} SPEECHES x{1} on the area in the Congressional Record, latest: "
                                 "\"{2}\" [activity, not direction]".format(
                                     (last["date"] or "?")[:10], len(rows), r5.clip(last["title"], 70)))

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
            got = votes[latest["division_key"]].get(pid)
            if got is not None and got[0] not in DIRECTIONAL:
                cap = ("CAPPED at +: no Yea/Nay on the latest signed decisive roll call ({0}, {1}). "
                       "++ means 'will vote with us'; a member who missed it is the contact "
                       "list.".format(latest["date"], latest["division_key"]))
        where = m.get("state") or ""
        if chamber == "house" and m.get("district"):
            where = "{0}-{1}".format(where, m["district"])
        row = r5.finish_row(pid, r["lines"], r["scored"], WEIGHTS, m.get("name"), m.get("party"),
                            where, is_sitting, cap_note=cap, today=today)
        row["cosponsored"] = r["cosponsored"]
        rows.append(row)
    return r5.sort_rows(rows), divisions, latest


def run(conn, area, chamber, entries, bill_entries, names, out_dir, log=print):
    rows, divisions, latest = build_rows(conn, area, chamber, entries, bill_entries)
    if not any(r["n_events"] for r in rows):
        return None
    name = names.get(area, "area {0}".format(area))
    path = os.path.join(out_dir, "us-5ca-{0}-{1}.csv".format(chamber, r5.slug(name)))
    signed, unsigned = r5.area_counts(divisions, entries)
    tally = r5.write_sheet(path, rows, r5.readings_line(signed, unsigned, name))
    sitting = [r for r in rows if r["sitting"]]
    log("{0} {1}: {2} sitting (+{3} former), {4} with evidence, {5} cosponsoring, {6} placed; "
        "{7} roll call(s), readings {8} signed / {9} unsigned -> {10}".format(
            chamber, name, len(sitting), len(rows) - len(sitting),
            sum(1 for r in rows if r["n_events"]), sum(1 for r in sitting if r["cosponsored"]),
            sum(1 for r in sitting if r["column"] != "0"), len(divisions), signed, unsigned,
            os.path.relpath(path, ROOT) if path.startswith(ROOT) else path))
    log("    " + "  ".join("{0} x{1}".format(c, tally[c]) for c in r5.COLUMNS))
    if latest is not None:
        e = entries[latest["division_key"]]
        ours = "Yea" if (e.get("yea") or 0) > (e.get("nay") or 0) else "Nay"
        lobby = conn.execute("SELECT COUNT(*) FROM us_votes WHERE division_key=? AND position=?",
                             (latest["division_key"], ours)).fetchone()[0]
        pp = sum(1 for r in sitting if r["column"] == "++")
        log("    check: sitting ++ {0} against our lobby of {1} on {2}{3}".format(
            pp, lobby, latest["division_key"], "  <-- ++ EXCEEDS our lobby" if pp > lobby else ""))
    return path


INTRO = """Every reading below was DRAFTED by Claude on 9 October 2026 from the store
(us_divisions, us_votes, us_bills, us_cosponsors) and the amendment purposes
the House printed. None is signed, so `tools/us_5ca.py` places nobody yet:
every sheet in data/5ca/us-5ca-*.csv is an evidence list ending "NO SIGNED
READINGS". The direction of a vote is your judgement, never the tool's.

Scale: +2 / -2 a vote or bill squarely on our ground; +1 / -1 a weaker or
procedural signal (a cloture vote, a motion to proceed, a cosponsorship);
"no value" on a side means its lobby tells no member apart. A motion to
recommit in the 119th House carries no instructions: it is the minority's
last procedural vote against the bill, so it is drafted as evidence only."""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", type=int)
    ap.add_argument("--all", action="store_true", help="every 5CA area, both chambers")
    ap.add_argument("--chamber", choices=("house", "senate"), default="house")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--stance", default=STANCE_PATH)
    ap.add_argument("--signoff-doc", nargs="?", const=DOC_PATH, metavar="PATH",
                    help="write the sign-off guide (default docs/5ca-us-readings.md) and stop")
    ap.add_argument("--sign-from-doc", nargs="?", const=DOC_PATH, metavar="PATH",
                    help="sign the readings ticked in the sign-off guide, then stop")
    args = ap.parse_args()
    entries = r5.load_stance(args.stance, "divisions")
    bill_entries = r5.load_stance(args.stance, "bills")
    if args.sign_from_doc:
        r5.sign_from_doc(args.stance, args.sign_from_doc)
        return 0
    if args.signoff_doc:
        with open(args.signoff_doc, "w", encoding="utf-8") as h:
            h.write(r5.signoff_markdown("US Congress 5CA: readings to sign", INTRO, LABELS,
                                        entries, bill_entries, "config/us_stance.yaml"))
        print("wrote {0}: {1} division and {2} bill readings".format(
            args.signoff_doc, len(entries), len(bill_entries)))
        return 0
    if not args.all and args.area is None:
        ap.error("--area N, --all, --signoff-doc or --sign-from-doc")
    excluded = r5.excluded_areas(ROOT)
    if args.area in excluded:
        print("area {0} is collated only, not a 5CA area".format(args.area))
        return 1
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    conn = us_store.ensure_schema(db.init_db(db.connect(args.db)))
    areas = sorted(a for a in names if a not in excluded) if args.all else [args.area]
    chambers = ("house", "senate") if args.all else (args.chamber,)
    written = 0
    for chamber in chambers:
        for area in areas:
            written += run(conn, area, chamber, entries, bill_entries, names, args.out_dir) is not None
    counts = r5.file_counts(entries, bill_entries)
    print("\n{0} sheet(s). config/us_stance.yaml: {confirmed} signed, {unplaceable} signed "
          "evidence-only, {draft} DRAFT (unsigned), {unread} unread.".format(written, **counts))
    if not counts["confirmed"]:
        print("  NO SIGNED READINGS: nobody is placed; every sheet is an evidence list.\n"
              "  Sign in docs/5ca-us-readings.md, then --sign-from-doc.")
    print("  Target is blank: the campaigner's call. Never posted anywhere.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
