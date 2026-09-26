#!/usr/bin/env python3
"""A 5CA sheet for the Parliament of Canada: one chamber, one issue area, CSV.

    python3 tools/ca_5ca.py --area 2                    # House of Commons, MAID
    python3 tools/ca_5ca.py --area 8 --chamber senate
    python3 tools/ca_5ca.py --all                       # every area, both chambers
    python3 tools/ca_5ca.py --area 2 --db /tmp/ca.db --out-dir /tmp/5ca

PHASE 3 of docs/canada-scope.md (26 September 2026). Reads the store only;
fetches nothing and posts nothing.

HOW A COLUMN GETS FILLED. Exactly as in Northern Ireland (tools/ni_5ca.py):
config/ca_stance.yaml is where a HUMAN writes what a Yea on one division
meant, and this tool applies it. An entry still carrying `draft: true`
places nobody. So does one marked `placeable: false` (unanimous, or
procedure), and so does one with only `read_first:`. Every Canadian entry was
drafted by Claude on 26 September 2026, so until Christopher confirms
readings, every column is blank and the sheet is an evidence list. That is
the design, not a bug.

Two kinds of act can place a member once confirmed:
  * a recorded VOTE (weight 5): the only act with a recorded direction;
  * SPONSORING a private member's bill (weight 3): a chosen act of
    advancing a text. A minister sponsoring a government bill is office,
    not choice, and the stance file gives those no value.
Everything else is evidence and never places anyone:
  * SPEECHES from Hansard: activity, not direction. A speech's direction is
    exactly what a person must read, and the no-scoring rule forbids the tool
    guessing it.
  * PETITIONS an MP presented or authorised. The House's own disclaimer: an
    MP presenting a petition does not endorse it.
  * A PAIRED vote or a Senate ABSTENTION: no direction recorded.

THE ABSENCE RULE (the Westminster lesson of 21 September 2026). ++ means
"will vote with us", and a member who missed the latest decisive division
is the opposite: they are the contact list. So a member placed at ++ who has
no recorded Yea/Nay on the area's latest DECISIVE signed division (confirmed,
our side scoring +2), having voted elsewhere in that session, is capped at +
with the reason in Comments. The
run also prints ++ against the size of our lobby on that division: ++
exceeding the lobby is the cheap check that absences leaked through.

EVERYONE WHO VOTED IS LISTED ([[parl-monitor-everyone-who-voted]]): sitting
members, plus anyone who cast a vote on the area, labelled FORMER. Cathay
Wagantall, who sponsored C-311, is not on the House's current roster
(26 September 2026), and her seat has no member; she is listed, labelled.

Sign conflicts are FLAGGED, never averaged. Target is always blank: that is
the campaigner's call.

Output: data/5ca/ca-5ca-<chamber>-<area-slug>.csv, a STABLE filename per
sheet, so reruns overwrite rather than accumulate (data/5ca is in git; see
[[parl-monitor-5ca-surfaces]]).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, intel, stance  # noqa: E402

STANCE_PATH = os.path.join(ROOT, "config", "ca_stance.yaml")
OUT_DIR = os.path.join(ROOT, "data", "5ca")
HEADER = ["Decision-Maker", "++", "+", "0", "-", "--", "Target (Y/N)",
          "Based on", "Confidence", "Evidence items", "Profile", "Comments",
          "Party", "Province"]
KIND_WEIGHT = {"vote": 5, "bill": 3}
DIRECTIONAL = ("Yea", "Nay")


def load_stance(path=STANCE_PATH, section="divisions"):
    """{key: entry} for one section of config/ca_stance.yaml, drafts included."""
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    return {str(e["key"]): e for e in (cfg.get(section) or []) if e.get("key")}


def status(entry):
    """'confirmed', 'draft', 'unplaceable', 'unread' or 'none' for one entry."""
    if not entry:
        return "none"
    if entry.get("placeable") is False:
        return "unplaceable"
    # Unread outranks draft: a read_first entry carries no values, so deleting
    # its draft flag must not make it look confirmed -- there is nothing to apply.
    if entry.get("yea") is None and entry.get("nay") is None and entry.get("sponsored") is None:
        return "unread"
    if entry.get("draft"):
        return "draft"
    return "confirmed"


def vote_stance(entry, position):
    """(stance, why) for a vote against a CONFIRMED entry, else (None, None)."""
    if status(entry) != "confirmed":
        return None, None
    if position == "Yea":
        return entry.get("yea"), entry.get("why_yea")
    if position == "Nay":
        return entry.get("nay"), entry.get("why_nay")
    return None, None


NOT_PLACED = {"draft": "reading DRAFT -- not placed",
              # A confirmed entry may give only ONE side a value on purpose:
              # C-62's reasoned amendment (commons-44-1-640) scores the Bloc's
              # Yea, and its Nay was the rest of the House. That was a
              # KeyError, found the first time such an entry was previewed.
              "confirmed": "this side carries no value -- its lobby tells no member apart",
              "unplaceable": "never places: {reason}",
              "unread": "not read yet -- not placed",
              "none": "no reading -- not placed"}


def not_placed(entry):
    st = status(entry)
    return NOT_PLACED[st].format(reason=(entry or {}).get("reason") or "")


def place(scored):
    """(column, conflict, decided) -- the ni_5ca rule: most directional,
    then evidence weight, then recency. Never averaged."""
    real = [s for s in scored if s[0] is not None]
    if not real:
        return "0", False, None
    best = max(real, key=lambda s: (abs(s[0] or 0), KIND_WEIGHT.get(s[3], 0), s[1] or ""))
    signs = {(1 if s[0] > 0 else -1) for s in real if s[0]}
    return stance.stance_to_column(best[0]), len(signs) > 1, best


def _in_area(areas, area):
    return area in json.loads(areas or "[]")


_DATE = __import__("re").compile(r"\d{4}-\d{2}-\d{2}")


def _line_date(line):
    hit = _DATE.search(line)
    return hit.group(0) if hit else ""


def chamber_members(conn, chamber):
    """{person_id: {name, party, province, riding, sitting}}."""
    if chamber == "commons":
        return {r["person_id"]: {"name": r["name"], "party": r["party"],
                                 "province": r["province"], "riding": r["constituency"],
                                 "sitting": r["sitting"]}
                for r in conn.execute("SELECT * FROM ca_members")}
    # The details page of a Senate vote lists EVERY seated senator, so the
    # latest fetched vote is the seated list as at its date.
    latest = conn.execute(
        "SELECT division_key FROM ca_divisions WHERE chamber='senate' AND "
        "positions_fetched=1 ORDER BY date DESC, number DESC LIMIT 1").fetchone()
    seated = {r[0] for r in conn.execute(
        "SELECT person_id FROM ca_votes WHERE division_key=?", (latest[0],))} if latest else set()
    return {r["person_id"]: {"name": r["name"], "party": r["affiliation"],
                             "province": r["province"], "riding": None,
                             "sitting": 1 if r["person_id"] in seated else 0}
            for r in conn.execute("SELECT * FROM ca_senators")}


def build_rows(conn, area, chamber, entries, bill_entries, today=None):
    today = today or datetime.date.today().isoformat()
    members = chamber_members(conn, chamber)
    divisions = [dict(r) for r in conn.execute(
        "SELECT * FROM ca_divisions WHERE chamber=? AND positions_fetched=1 "
        "ORDER BY date", (chamber,)) if _in_area(r["areas"], area)]
    votes = {}
    for d in divisions:
        votes[d["division_key"]] = {r["person_id"]: (r["position"], r["party"]) for r in conn.execute(
            "SELECT person_id, position, party FROM ca_votes WHERE division_key=?",
            (d["division_key"],))}
    # Who served in which session: anyone with a row on any division of it.
    served = {}
    for r in conn.execute("SELECT v.person_id, d.parliament, d.session FROM ca_votes v "
                          "JOIN ca_divisions d USING (division_key) WHERE d.chamber=?", (chamber,)):
        served.setdefault(r[0], set()).add((r[1], r[2]))

    per = {pid: {"scored": [], "lines": [], "voted_on_area": False} for pid in members}

    def rec(pid):
        return per.setdefault(pid, {"scored": [], "lines": [], "voted_on_area": False})

    for d in divisions:
        entry = entries.get(d["division_key"])
        label_base = "{0} {1} ({2})".format((d["date"] or "?")[:10],
                                            (d["subject"] or "?")[:70], d["result"] or "?")
        for pid, (position, party) in votes[d["division_key"]].items():
            r = rec(pid)
            if position == "Did not vote":
                r["lines"].append("{0} DID NOT VOTE: {1}".format((d["date"] or "?")[:10],
                                                                  (d["subject"] or "?")[:70]))
                continue
            r["voted_on_area"] = True
            label = "VOTE {0}: {1}".format((position or "?").upper(), label_base)
            if position not in DIRECTIONAL:
                r["lines"].append(label + " [no direction recorded]")
                continue
            s, why = vote_stance(entry, position)
            if s is not None:
                r["scored"].append((s, d["date"] or "", label, "vote"))
                r["lines"].append("{0} [{1:+d}: {2}]".format(label, s, " ".join((why or "").split())[:120]))
            else:
                r["lines"].append("{0} [{1}]".format(label, not_placed(entry)))
        # A Commons division lists only those who voted or paired, so a member
        # who served that session and has no row simply did not vote.
        if chamber == "commons":
            session = (d["parliament"], d["session"])
            for pid in members:
                if pid not in votes[d["division_key"]] and session in served.get(pid, ()):
                    rec(pid)["lines"].append("{0} NO RECORDED VOTE: {1}".format(
                        (d["date"] or "?")[:10], (d["subject"] or "?")[:70]))

    if chamber == "commons":
        for b in conn.execute("SELECT * FROM ca_bills WHERE sponsor_person_id IS NOT NULL"):
            if not _in_area(b["areas"], area):
                continue
            entry = bill_entries.get(b["bill_key"])
            label = "SPONSORED {0} {1}".format(b["bill_key"], (b["long_title"] or "")[:70])
            r = rec(b["sponsor_person_id"])
            st = entry.get("sponsored") if status(entry) == "confirmed" else None
            if st is not None:
                r["scored"].append((st, b["latest_event_at"] or "", label, "bill"))
                r["lines"].append("{0} [{1:+d}: {2}]".format(
                    label, st, " ".join((entry.get("why_sponsored") or "").split())[:120]))
            else:
                r["lines"].append("{0} [{1}]".format(label, not_placed(entry)))
        for s in conn.execute("SELECT * FROM ca_speeches WHERE person_id IS NOT NULL"):
            if _in_area(s["areas"], area):
                rec(s["person_id"])["lines"].append(
                    "{0} SPEECH {1}: \"{2}\" [activity, not direction]".format(
                        s["date"] or "?", (s["subject"] or s["rubric"] or "")[:50],
                        " ".join((s["excerpt"] or "").split())[:100]))
        for p in conn.execute("SELECT * FROM ca_petitions WHERE mp_person_id IS NOT NULL"):
            if _in_area(p["areas"], area):
                rec(p["mp_person_id"])["lines"].append(
                    "{0} PETITION {1} ({2}, {3} signatures) [presenting a petition "
                    "does not imply endorsement]".format(
                        p["presented"] or p["opened"] or "?", p["presented_number"] or p["petition_id"],
                        p["category"] or "?", p["signatures"] if p["signatures"] is not None else "?"))

    # The absence rule: the latest DECISIVE signed division -- confirmed, and
    # OUR side scoring +2 (C-62's Nay scores -2, but its Yea only +1, so it is
    # not decisive for us; the abs() version of this test capped 14 anyway). Missing a +1 vote (C-62's delay) says little
    # about a member who voted for C-314; the first preview capped Chris
    # Warkentin for exactly that, and the Westminster rule was always about
    # the decisive division.
    decisive = [d for d in divisions
                if status(entries.get(d["division_key"])) == "confirmed"
                and max(entries[d["division_key"]].get("yea") or 0,
                        entries[d["division_key"]].get("nay") or 0) >= 2]
    latest = decisive[-1] if decisive else None

    rows = []
    for pid, r in per.items():
        m = members.get(pid)
        if m is None:
            continue                  # a speaker or sponsor we hold no member row for
        sitting = bool(m["sitting"])
        if not sitting and not r["voted_on_area"] and not r["scored"]:
            continue                  # a former member with nothing to show stays off
        column, conflict, decided = place(r["scored"])
        comments = sorted(r["lines"], key=_line_date, reverse=True)   # newest first
        capped = False
        if column == "++" and latest is not None:
            got = votes[latest["division_key"]].get(pid, (None,))[0]
            if got not in DIRECTIONAL and (latest["parliament"], latest["session"]) in served.get(pid, ()):
                column, capped = "+", True
                comments.insert(0, "CAPPED at +: no Yea/Nay on the latest signed division "
                                   "({0}, {1}). ++ means 'will vote with us'; a member who "
                                   "missed it is the contact list.".format(
                                       (latest["date"] or "")[:10], (latest["subject"] or "")[:50]))
        if conflict:
            comments.insert(0, "MIXED RECORD: directional evidence on both sides -- read the "
                               "acts, not the column")
        if decided:
            based = stance.based_on({"vote": "vote", "bill": "edm"}.get(decided[3], decided[3]),
                                    decided[1][:10] or today)
            confidence = ("strong (recorded vote, human-confirmed reading)" if decided[3] == "vote"
                          else "moderate (bill sponsorship, human-confirmed reading)")
        elif r["lines"]:
            based, confidence = "no confirmed reading", "n/a (evidence only)"
        else:
            based, confidence, comments = "no evidence", "", ["No recorded activity on this area"]
        who = m["name"] or pid
        where = m["riding"] or m["province"] or ""
        rows.append({
            "person_id": pid, "column": column, "conflict": conflict, "capped": capped,
            "decision_maker": "{0} ({1}){2}{3}".format(
                who, m["party"] or "?", " - " + where if where else "",
                "" if sitting else " [FORMER]"),
            "n_events": len(r["lines"]), "based_on": based, "confidence": confidence,
            "comments": comments, "party": m["party"] or "", "province": m["province"] or "",
            "sitting": sitting})
    order = {c: i for i, c in enumerate(stance.COLUMNS)}
    rows.sort(key=lambda x: (order[x["column"]], not x["sitting"], -x["n_events"], x["decision_maker"]))
    return rows, divisions, latest


def lobby_check(rows, latest, entries, votes_for):
    """(sitting ++, our lobby, our side's value) on the latest confirmed division.

    Only meaningful when our side of that division scores +2: then every
    sitting ++ should be IN our lobby, and ++ exceeding it means absences
    leaked (the Westminster check of 21 September 2026). When our side scores
    +1 -- C-9's third reading -- ++ rests on older votes and the comparison
    says nothing, so the caller reports it as such rather than raising a
    false alarm (the first preview did exactly that)."""
    if latest is None:
        return None
    entry = entries.get(latest["division_key"])
    yea, nay = entry.get("yea") or 0, entry.get("nay") or 0
    ours, value = ("Yea", yea) if yea > nay else ("Nay", nay)
    lobby = sum(1 for p, _ in votes_for.values() if p == ours)
    return sum(1 for r in rows if r["column"] == "++" and r["sitting"]), lobby, value


def write_sheet(path, rows):
    """Write the sheet. The Totals row counts SITTING members only: a former
    member is listed, labelled, because they cast the vote, but they are not a
    decision-maker any more, and counting the 44th Parliament's departed into
    today's columns would overstate every one of them."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tally = {c: 0 for c in stance.COLUMNS}
    sitting = sum(1 for r in rows if r["sitting"])
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(HEADER)
        for r in rows:
            if r["sitting"]:
                tally[r["column"]] += 1
            w.writerow([r["decision_maker"], *("1" if r["column"] == c else "" for c in stance.COLUMNS),
                        "", r["based_on"], r["confidence"], r["n_events"], "",
                        " | ".join(r["comments"]), r["party"], r["province"]])
        w.writerow(["Totals - {0} sitting decision-makers ({1} former listed, not counted)".format(
                        sitting, len(rows) - sitting),
                    *(tally[c] for c in stance.COLUMNS), "", "", "", "", "", "", "", ""])
    return tally


def run(conn, area, chamber, entries, bill_entries, names, out_dir, log=print):
    rows, divisions, latest = build_rows(conn, area, chamber, entries, bill_entries)
    evidence = sum(1 for r in rows if r["n_events"])
    if not evidence:
        return None
    slug = names.get(area, "area-{0}".format(area)).lower().replace(" ", "-").replace(",", "")
    path = os.path.join(out_dir, "ca-5ca-{0}-{1}.csv".format(chamber, slug))
    tally = write_sheet(path, rows)
    placed = sum(1 for r in rows if r["column"] != "0" and r["sitting"])
    sitting = sum(1 for r in rows if r["sitting"])
    log("{0} {1}: {2} sitting (+{3} former), {4} with evidence, {5} sitting placed, "
        "{6} division(s) -> {7}".format(
        chamber, names.get(area, area), sitting, len(rows) - sitting, evidence, placed, len(divisions),
        os.path.relpath(path, ROOT) if path.startswith(ROOT) else path))
    log("    " + "  ".join("{0} x{1}".format(c, tally[c]) for c in stance.COLUMNS))
    if latest is not None:
        votes_for = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT person_id, position, party FROM ca_votes WHERE division_key=?",
            (latest["division_key"],))}
        pp, lobby, value = lobby_check(rows, latest, entries, votes_for)
        if value >= 2:
            flag = "  <-- ++ EXCEEDS our lobby: absences leaked" if pp > lobby else ""
            log("    check: sitting ++ {0} against our lobby of {1} on {2}{3}".format(
                pp, lobby, latest["division_key"], flag))
        else:
            log("    check: not applicable -- our side of {0} scores {1:+d}, so ++ rests "
                "on older votes".format(latest["division_key"], value))
    capped = sum(1 for r in rows if r["capped"])
    if capped:
        log("    {0} capped from ++ to + for missing the latest signed division".format(capped))
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", type=int)
    ap.add_argument("--all", action="store_true", help="every 5CA area, both chambers")
    ap.add_argument("--chamber", choices=("commons", "senate"), default="commons")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--stance", default=STANCE_PATH,
                    help="a different stance file -- to preview readings without editing the real one")
    args = ap.parse_args()
    if not args.all and args.area is None:
        ap.error("--area N or --all")
    import yaml
    with open(os.path.join(ROOT, "config", "stance_overrides.yaml"), encoding="utf-8") as h:
        excluded = {int(a) for a in (yaml.safe_load(h) or {}).get("excluded_from_5ca") or []}
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    entries = load_stance(args.stance, section="divisions")
    bill_entries = load_stance(args.stance, section="bills")
    areas = sorted(a for a in names if a not in excluded) if args.all else [args.area]
    if args.area in excluded:
        print("area {0} is collated only, not a 5CA area".format(args.area))
        return 1
    chambers = ("commons", "senate") if args.all else (args.chamber,)
    written = 0
    for chamber in chambers:
        for area in areas:
            written += run(conn, area, chamber, entries, bill_entries, names, args.out_dir) is not None
    every = list(entries.values()) + list(bill_entries.values())
    counts = {k: sum(1 for e in every if status(e) == k)
              for k in ("confirmed", "draft", "unread", "unplaceable")}
    print("\n{0} sheet(s). config/ca_stance.yaml: {confirmed} confirmed, {draft} draft, "
          "{unread} unread, {unplaceable} never-placeable.".format(written, **counts))
    if counts["draft"] or counts["unread"]:
        print("  A draft or unread entry places NOBODY: its votes appear as evidence only.\n"
              "  Confirm a reading by deleting its `draft: true` line; read_first entries\n"
              "  need their text read and yea/nay values written first.")
    print("  Target is blank: the campaigner's call. Never posted anywhere.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
