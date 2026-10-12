#!/usr/bin/env python3
"""A 5CA sheet for the Oireachtas: one House, one issue area, CSV.

    python3 tools/ie_5ca.py --area 1                    # Dail, abortion
    python3 tools/ie_5ca.py --area 1 --chamber seanad
    python3 tools/ie_5ca.py --all                       # every 5CA area, both Houses
    python3 tools/ie_5ca.py --all --db /tmp/ie.db --out-dir /tmp/5ca
    python3 tools/ie_5ca.py --signoff-doc               # write docs/5ca-ie-readings.md
    python3 tools/ie_5ca.py --sign-from-doc             # apply its ticked boxes

Reads the store only; fetches nothing and posts nothing. The Irish mirror of
tools/ca_5ca.py, with the shared parts in src/readings5ca.py.

HOW A COLUMN GETS FILLED. config/ie_stance.yaml is where a HUMAN writes what a
Ta (stored 'Yes') on one division meant, as `yea:`, and a Nil ('No') as
`nay:`. An entry carrying `draft: true` places NOBODY. Every entry was drafted
by Claude on 9 October 2026 and none is signed, so every column is 0 and each
sheet ends with a row saying so.

What can place a member, once a reading is signed:
  * a recorded VOTE, Ta or Nil (weight 5), in plenary or in a committee of
    that House;
  * SPONSORING a Private Member's bill (weight 3). A Government bill is
    sponsored by an office, never placed.
What never places anyone: STAON (a recorded abstention: no direction).

WHICH DIVISIONS ARE LISTED. A division is evidence on an area when its own
text matched the area, or the stance file reads it, or it is a stage question
(not an amendment) on a bill the stance file reads. Amendment votes that only
borrow the area from their bill (thirty-odd Mental Health Bill amendments) are
left off; the amendment text read in phase 1b is what lets one stand on its
own.

THE ABSENCE RULE: a member at ++ who held the seat on the date of the area's
latest DECISIVE signed division (our side +2) but recorded no Ta or Nil on it
is capped at +. The Oireachtas lists only those who voted, so a member with no
row who held the seat that day did not vote.

Output: <out-dir>/ie-5ca-<dail|seanad>-<area-slug>.csv, a stable name per sheet.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, ie_store, intel  # noqa: E402
from src import readings5ca as r5  # noqa: E402

STANCE_PATH = os.path.join(ROOT, "config", "ie_stance.yaml")
DOC_PATH = os.path.join(ROOT, "docs", "5ca-ie-readings.md")
OUT_DIR = os.path.join(ROOT, "data", "5ca")
WEIGHTS = {"vote": 5, "sponsored": 3}
SIDE = {"Yes": "yea", "No": "nay"}
SAID = {"Yes": "TA", "No": "NIL", "Abstain": "STAON"}
LABELS = {"yea": "Ta (Yes)", "nay": "Nil (No)"}


def _areas(text):
    return json.loads(text or "[]")


def listed(d, area, entries, bill_entries):
    if area not in _areas(d["areas"]):
        return False
    if d["division_key"] in entries or area in _areas(d["own_areas"]):
        return True
    amendment = "amendment" in (d["subject"] or "").lower()
    return not amendment and d["bill_key"] in bill_entries


def held_seat(m, date):
    """Did this member hold the seat on that date? (latest membership only)."""
    if not m or not date:
        return False
    return (m["start_date"] or "") <= date and (not m["end_date"] or m["end_date"] >= date)


def build_rows(conn, area, chamber, entries, bill_entries, today=None):
    today = today or datetime.date.today().isoformat()
    members = {r["member_code"]: dict(r) for r in conn.execute("SELECT * FROM ie_members")}
    sitting = {k for k, m in members.items() if m["house"] == chamber and not m["end_date"]}
    divisions = [dict(r) for r in conn.execute(
        "SELECT * FROM ie_divisions WHERE house_key LIKE ? ORDER BY date, division_key",
        (chamber + "/%",))]
    divisions = [d for d in divisions if listed(d, area, entries, bill_entries)]
    votes = {d["division_key"]: {r["member_code"]: (r["position"], r["party"]) for r in conn.execute(
        "SELECT member_code, position, party FROM ie_votes WHERE division_key=?", (d["division_key"],))}
        for d in divisions}

    per = {}

    def rec(pid):
        return per.setdefault(pid, {"scored": [], "lines": [], "voted": False})

    for pid in sitting:
        rec(pid)
    for d in divisions:
        entry = entries.get(d["division_key"])
        where = "COMMITTEE {0}: ".format(r5.clip(d["committee"], 40)) if d["committee"] else ""
        base = "{0} {1}{2} -- {3} ({4} {5}-{6})".format(
            d["date"] or "?", where, r5.clip(d["debate_title"], 80),
            r5.clip(d["amendment_text"] or d["subject"], 90), d["outcome"] or "?",
            d["ta"] if d["ta"] is not None else "?", d["nil"] if d["nil"] is not None else "?")
        for pid, (position, party) in votes[d["division_key"]].items():
            r = rec(pid)
            label = "VOTE {0} ({1}): {2}".format(SAID.get(position, position or "?"), party or "?", base)
            if position not in SIDE:
                r["lines"].append(label + " [abstention recorded: no direction]")
                continue
            r["voted"] = True
            s, why = r5.value(entry, SIDE[position])
            if s is not None:
                r["scored"].append((s, d["date"] or "", label, "vote"))
                r["lines"].append("{0} [{1:+d}: {2}]".format(label, s, r5.clip(why, 120)))
            else:
                r["lines"].append("{0} [{1}]".format(label, r5.not_placed(entry)))
        for pid in sitting:
            if pid not in votes[d["division_key"]] and held_seat(members.get(pid), d["date"]) \
                    and not d["committee"]:
                rec(pid)["lines"].append("{0} NO RECORDED VOTE: {1}".format(
                    d["date"] or "?", r5.clip(d["debate_title"], 70)))

    for s in conn.execute(
            "SELECT s.bill_key, s.member_code, b.title, b.areas, b.introduced, b.last_stage_at "
            "FROM ie_sponsors s JOIN ie_bills b USING (bill_key) WHERE s.member_code IS NOT NULL "
            "AND b.source = 'Private Member'"):
        if area not in _areas(s["areas"]) or (s["member_code"] not in sitting
                                               and s["member_code"] not in per):
            continue
        entry = bill_entries.get(s["bill_key"])
        when = s["introduced"] or s["last_stage_at"] or ""
        label = "{0} SPONSORED {1} {2}".format(when[:10] or "?", s["bill_key"], r5.clip(s["title"], 80))
        r = rec(s["member_code"])
        v, why = r5.value(entry, "sponsored")
        if v is not None:
            r["scored"].append((v, when, label, "sponsored"))
            r["lines"].append("{0} [{1:+d}: {2}]".format(label, v, r5.clip(why, 120)))
        else:
            r["lines"].append("{0} [{1}]".format(label, r5.not_placed(entry)))

    decisive = r5.decisive([d for d in divisions if not d["committee"]], entries)
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
            if got not in SIDE and held_seat(m, latest["date"]):
                cap = ("CAPPED at +: no Ta/Nil on the latest signed decisive division ({0}, {1}). "
                       "++ means 'will vote with us'; a member who missed it is the contact "
                       "list.".format(latest["date"], r5.clip(latest["debate_title"], 60)))
        rows.append(r5.finish_row(pid, r["lines"], r["scored"], WEIGHTS, m.get("name"),
                                  m.get("party"), m.get("represents"), is_sitting,
                                  cap_note=cap, today=today))
    return r5.sort_rows(rows), divisions, latest


def run(conn, area, chamber, entries, bill_entries, names, out_dir, log=print):
    rows, divisions, latest = build_rows(conn, area, chamber, entries, bill_entries)
    if not any(r["n_events"] for r in rows):
        return None
    name = names.get(area, "area {0}".format(area))
    path = os.path.join(out_dir, "ie-5ca-{0}-{1}.csv".format(chamber, r5.slug(name)))
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
        ours = "Yes" if (e.get("yea") or 0) > (e.get("nay") or 0) else "No"
        lobby = conn.execute("SELECT COUNT(*) FROM ie_votes WHERE division_key=? AND position=?",
                             (latest["division_key"], ours)).fetchone()[0]
        pp = sum(1 for r in sitting if r["column"] == "++")
        log("    check: sitting ++ {0} against our lobby of {1} on {2}{3}".format(
            pp, lobby, latest["division_key"], "  <-- ++ EXCEEDS our lobby" if pp > lobby else ""))
    return path


INTRO = """Every reading below was DRAFTED by Claude on 9 October 2026 from the store
(ie_divisions, ie_votes, ie_sponsors) and the Dail debate records of the day,
read for the question put and the tellers. None is signed, so
`tools/ie_5ca.py` places nobody yet: every sheet in data/5ca/ie-5ca-*.csv is
an evidence list ending "NO SIGNED READINGS".

Ta is stored as 'Yes' and written `yea:`; Nil as 'No', `nay:`. Staon (a
recorded abstention) never places anyone. The store holds the 34th Dail and
the 27th Seanad only (from December 2024 and February 2025): the safe access
zones Act and the hate offences votes were in the 33rd Dail and are not in it,
so they cannot be read here."""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", type=int)
    ap.add_argument("--all", action="store_true", help="every 5CA area, both Houses")
    ap.add_argument("--chamber", choices=("dail", "seanad"), default="dail")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--stance", default=STANCE_PATH)
    ap.add_argument("--signoff-doc", nargs="?", const=DOC_PATH, metavar="PATH")
    ap.add_argument("--sign-from-doc", nargs="?", const=DOC_PATH, metavar="PATH")
    args = ap.parse_args()
    entries = r5.load_stance(args.stance, "divisions")
    bill_entries = r5.load_stance(args.stance, "bills")
    if args.sign_from_doc:
        r5.sign_from_doc(args.stance, args.sign_from_doc)
        return 0
    if args.signoff_doc:
        with open(args.signoff_doc, "w", encoding="utf-8") as h:
            h.write(r5.signoff_markdown("Oireachtas 5CA: readings to sign", INTRO, LABELS,
                                        entries, bill_entries, "config/ie_stance.yaml"))
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
    conn = ie_store.ensure_schema(db.init_db(db.connect(args.db)))
    areas = sorted(a for a in names if a not in excluded) if args.all else [args.area]
    chambers = ("dail", "seanad") if args.all else (args.chamber,)
    written = 0
    for chamber in chambers:
        for area in areas:
            written += run(conn, area, chamber, entries, bill_entries, names, args.out_dir) is not None
    counts = r5.file_counts(entries, bill_entries)
    print("\n{0} sheet(s). config/ie_stance.yaml: {confirmed} signed, {unplaceable} signed "
          "evidence-only, {draft} DRAFT (unsigned), {unread} unread.".format(written, **counts))
    if not counts["confirmed"]:
        print("  NO SIGNED READINGS: nobody is placed; every sheet is an evidence list.\n"
              "  Sign in docs/5ca-ie-readings.md, then --sign-from-doc.")
    print("  Target is blank: the campaigner's call. Never posted anywhere.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
