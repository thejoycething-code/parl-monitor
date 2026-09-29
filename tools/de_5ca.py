#!/usr/bin/env python3
"""A 5CA sheet for the Bundestag: the sitting members, one issue area, CSV.

    python3 tools/de_5ca.py --area 1                       # abortion
    python3 tools/de_5ca.py --all
    python3 tools/de_5ca.py --area 1 --preview-drafts      # what the drafts would do
    python3 tools/de_5ca.py --area 1 --db /tmp/s.db --out-dir /tmp/5ca

Built 29 September 2026 from a hand-run sample Christopher reviewed. Reads the
store and two config files only; fetches nothing and posts nothing. The
collectors that feed it: tools/de_profiles.py --roster (who sits),
tools/de_rollcalls.py (votes, the Bundestag's and the Landtage's),
tools/de_speeches.py + tools/de_stance.py (speeches, model-scored),
tools/de_authorship.py (who put their name to a paper).

WHO IS ON THE SHEET: the SITTING members only (Christopher, 29 September:
"5CA sheets only pull in existing members"), from de_members.sitting. Until
the roster has been checked this refuses to run -- it never falls back to
last_seen, which is how eight departed members (Baerbock, Habeck and six
others) made a 630-seat House read 638.

WHAT PLACES A MEMBER. Five kinds of act, three tiers:
    vote, speech, bill (co-sponsoring a group bill)       tier 2
    motion (co-authoring an Antrag)                       tier 1
    question (Kleine Anfrage, written or oral question)   tier 0
A vote, a paper and a Land record item place only through a CONFIRMED line
in config/de_stance.yaml or config/de_land_record.yaml -- a draft places
nobody, exactly as in Canada and Northern Ireland. A speech places through
its model score in the stance table, as at Westminster.

WHY A VOTE DOES NOT OUTRANK EVERYTHING HERE, which is the one place this
departs from the Westminster hierarchy. German divisions are whipped. Ten SPD
members voted Nein on the 2019 § 219a opposition motions under coalition
discipline and co-sponsored decriminalisation (20/13775) in 2024; a vote-first
rule put all ten at ++. So within the strongest tier present:
  * SIDE: the side with at least two more EVENTS (same kind, same day = one
    event: the two § 219a divisions of 21 Feb 2019 are one whipped sitting),
    else the side of the most recent item (a same-day tie goes to the
    stronger statement). One speech the model scored +1 must not outvote
    seven acts the other way.
  * COLUMN: the strongest statement on that side, so thirty-five consistent
    acts do not read "-" because the latest speech happened to score -1.
Anything pointing the other way is FLAGGED, never averaged.

THE COALITION RULE for earlier parliaments. A Land coalition votes down
opposition motions whatever its members think: Tarek Al-Wazir (Greens) voted
Nein on the Linke's 2023 Hesse buffer-zone bill inside the CDU-Green
coalition. A Land vote or Land record item that would place a member against
their Bundestag party's clear line (80%+ of that party's members placed on
Bundestag evidence, at least ten of them) is shown and never placed.

Matching across parliaments is by name AND party family (src/de_names), so a
Bavarian namesake from another party cannot attach. Two sitting members
sharing a name key would both be refused -- none do in the 21st Bundestag.

Target is blank: the campaigner's call. The 0 column is a stance (a speech
scored neutral), never "on record, side unknown": those are counted apart.

Output: data/5ca/de-5ca-bundestag-<area-slug>.csv, a STABLE filename, so
reruns overwrite rather than accumulate. A preview never writes there.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, de_names, intel  # noqa: E402

STANCE_PATH = os.path.join(ROOT, "config", "de_stance.yaml")
LAND_PATH = os.path.join(ROOT, "config", "de_land_record.yaml")
OUT_DIR = os.path.join(ROOT, "data", "5ca")
CURRENT = "161"                      # abgeordnetenwatch's Bundestag 2025-2029
BUNDESTAG = "5"
COLUMNS = ("++", "+", "0", "-", "--")
HEADER = ["Decision-Maker", *COLUMNS, "Target (Y/N)", "Based on", "Confidence",
          "Evidence items", "Profile", "Comments", "Party", "Seat"]
TIER = {"vote": 2, "speech": 2, "bill": 2, "motion": 1, "question": 0}
LABEL = {"vote": "a vote", "speech": "a speech", "bill": "a bill co-sponsored",
         "motion": "a motion signed", "question": "a question"}
ART_KIND = {"Gesetzentwurf": "bill", "Antrag": "motion", "Entschließungsantrag": "motion"}
PARTY_LINE = 0.8
PARTY_LINE_MIN = 10
COMMENT_ITEMS = 8


# -- config -------------------------------------------------------------------

def load_yaml(path):
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def status(entry):
    """'confirmed', 'draft', 'unplaceable' or 'none'."""
    if not entry:
        return "none"
    if entry.get("placeable") is False:
        return "unplaceable"
    if entry.get("draft"):
        return "draft"
    return "confirmed"


def usable(entry, preview):
    """Whether an entry's value may place anyone in this run."""
    st = status(entry)
    return st == "confirmed" or (preview and st == "draft")


def column_of(value):
    return {2: "++", 1: "+", 0: "0", -1: "-", -2: "--"}[max(-2, min(2, int(value)))]


# -- who sits, and who is who ---------------------------------------------------

def roster(conn):
    """{person_id: row} of sitting members, or None if never checked."""
    rows = conn.execute("SELECT * FROM de_members WHERE legislature = ?", (CURRENT,)).fetchall()
    if not rows or all(r["sitting"] is None for r in rows):
        return None
    return {r["person_id"]: r for r in rows if r["sitting"] == 1}


class Bridge:
    """Name (and party family) to a sitting member's person_id."""

    def __init__(self, sitting):
        self.by_key = {}
        for pid, r in sitting.items():
            self.by_key.setdefault(de_names.key(r["name"]), []).append(pid)
        self.clash = {k for k, v in self.by_key.items() if len(v) > 1}
        self.family = {pid: de_names.party_family(r["party"]) for pid, r in sitting.items()}

    def find(self, name, party=None):
        k = de_names.key(name)
        if k not in self.by_key or k in self.clash:
            return None
        pid = self.by_key[k][0]
        if party is not None:
            theirs, ours = de_names.party_family(party), self.family[pid]
            if theirs and ours and theirs != ours:
                return None
        return pid


# -- evidence -----------------------------------------------------------------

def _ev(kind, date, value, line, earlier=False, free=False):
    return {"kind": kind, "date": date or "", "value": value, "line": line,
            "earlier": earlier, "free": free}


def gather(conn, area, sitting, stance_cfg, land_cfg, preview):
    """{person_id: [evidence]} for one area, and the counts behind them."""
    bridge = Bridge(sitting)
    ev = {pid: [] for pid in sitting}
    counts = {"votes": 0, "speeches": 0, "papers": 0, "land": 0, "refused": 0}
    members = {r["person_id"]: r for r in conn.execute(
        "SELECT person_id, name, party, parliament, legislature FROM de_members")}

    def resolve(person_id):
        if person_id in sitting:
            return person_id
        m = members.get(person_id)
        if not m:
            return None
        return bridge.find(m["name"], m["party"])

    # Divisions: every signed-or-drafted reading for the area.
    for d in stance_cfg.get("divisions") or []:
        if d.get("area") != area:
            continue
        div = conn.execute("SELECT * FROM de_divisions WHERE vote_id = ?", (str(d["key"]),)).fetchone()
        if not div:
            continue
        earlier = str(div["parliament"]) != BUNDESTAG
        where = div["parliament_label"] or ("Bundestag" if not earlier else "")
        for v in conn.execute("SELECT person_id, position FROM de_votes WHERE vote_id = ?",
                              (div["vote_id"],)):
            if v["position"] not in ("yes", "no"):
                continue
            pid = resolve(v["person_id"])
            if pid is None:
                continue
            side = "ja" if v["position"] == "yes" else "nein"
            value = d.get(side) if usable(d, preview) else None
            why = d.get("why_" + side) or ""
            tag = ("{0}: {1}".format(column_of(value), why) if value is not None
                   else not_placed(d))
            ev[pid].append(_ev("vote", div["date"], value,
                "{0} VOTE ({1}): Voted {2}: {3} [{4}]".format(
                    div["date"], where or "Bundestag", side.capitalize(),
                    (div["label"] or "").strip(), tag), earlier=earlier,
                free=bool(d.get("free_vote"))))
            counts["votes"] += 1

    # Speeches: model-scored, as at Westminster.
    for r in conn.execute(
            "SELECT s.person_id, s.date, s.excerpt, st.stance, st.why FROM de_speeches s "
            "JOIN stance st ON st.ref = 'de-speech:' || s.speech_id "
            "WHERE EXISTS (SELECT 1 FROM json_each(s.areas) WHERE value = ?)", (area,)):
        pid = resolve(r["person_id"])
        if pid is None:
            continue
        excerpt = " ".join((r["excerpt"] or "").split())[:220]
        ev[pid].append(_ev("speech", r["date"], r["stance"],
            "{0} DEBATE: Rede \"{1}...\" [{2}: {3}]".format(
                r["date"], excerpt, column_of(r["stance"]), r["why"] or "")))
        counts["speeches"] += 1

    # Papers: who put their name to them (de_authorship), read through
    # config/de_stance.yaml papers.
    papers = {str(p["key"]): p for p in stance_cfg.get("papers") or [] if p.get("area") == area}
    if papers:
        marks = ",".join("?" * len(papers))
        seen = set()
        for r in conn.execute(
                "SELECT * FROM de_authorship WHERE vorgang_id IN ({0})".format(marks),
                list(papers)):
            pid = bridge.find(r["author"])
            # Keyed on the Vorgang as well: two questions by one member can
            # share a Drucksache, and each is its own act.
            if pid is None or (pid, r["nummer"], r["vorgang_id"]) in seen:
                continue
            seen.add((pid, r["nummer"], r["vorgang_id"]))
            p = papers[r["vorgang_id"]]
            kind = ART_KIND.get(r["art"], "question")
            value = p.get("authored") if usable(p, preview) else None
            tag = ("{0}: {1}".format(column_of(value), p.get("why") or "") if value is not None
                   else not_placed(p))
            ev[pid].append(_ev(kind, r["datum"], value,
                "{0} {1}: {2} (Drucksache {3}) [{4}]".format(
                    r["datum"], (r["art"] or "").upper(), (r["titel"] or "")[:120],
                    r["nummer"], tag)))
            counts["papers"] += 1

    # Land records searched by hand.
    for m in land_cfg.get("members") or []:
        pid = bridge.find(m["name"])
        if pid is None:
            counts["refused"] += 1
            continue
        for it in m.get("items") or []:
            # An item belongs to one area. Every item so far was found in the
            # abortion search, so a missing area means area 1 -- never "all".
            if int(it.get("area", 1)) != area:
                continue
            value = it.get("value") if usable(it, preview) else None
            tag = ("{0}: hand-searched".format(column_of(value)) if value is not None
                   else not_placed(it))
            ev[pid].append(_ev(it.get("kind", "question"), str(it.get("date")), value,
                "{0} LAND {1} ({2}): {3} \"{4}\" [{5}; {6}]".format(
                    it.get("date"), it.get("kind", "").upper(), m.get("parliament"),
                    it.get("doc") or "", it.get("quote") or "", tag, it.get("url") or ""),
                earlier=True))
            counts["land"] += 1
    return ev, counts


def not_placed(entry):
    st = status(entry)
    if st == "unplaceable":
        return "never places: " + (entry.get("reason") or "")
    if st == "draft":
        return "reading DRAFT -- not placed"
    if st == "confirmed":
        # A confirmed reading may value only ONE lobby on purpose: every other
        # group votes down an AfD-only motion as a matter of course (the
        # Brandmauer), so that Nein tells no member apart.
        return "this side carries no value -- its lobby tells no member apart"
    return "no reading -- not placed"


# -- placement -----------------------------------------------------------------

def place(items):
    """(evidence item deciding, its column, confidence) or (None, None, why)."""
    directional = [e for e in items if e["value"] not in (None, 0)]
    if not directional:
        neutral = [e for e in items if e["kind"] == "speech" and e["value"] == 0
                   and not e["earlier"]]
        if neutral:
            return neutral[0], "0", "neutral (spoke, no stance)"
        return None, None, "on record, side not placed" if items else ""
    top = max(TIER[e["kind"]] for e in directional)
    pool = [e for e in directional if TIER[e["kind"]] == top]
    ours = [e for e in pool if e["value"] > 0]
    theirs = [e for e in pool if e["value"] < 0]
    n_ours = len({(e["kind"], e["date"]) for e in ours})
    n_theirs = len({(e["kind"], e["date"]) for e in theirs})
    if n_ours - n_theirs >= 2:
        side = ours
    elif n_theirs - n_ours >= 2:
        side = theirs
    else:
        lead = max(pool, key=lambda e: (e["date"], abs(e["value"])))
        side = ours if lead["value"] > 0 else theirs
    positive = side is ours
    strong = any(abs(e["value"]) >= 2 for e in side)
    col = ("++" if strong else "+") if positive else ("--" if strong else "-")
    best = max(side, key=lambda e: e["date"])
    against = [e for e in directional if (e["value"] > 0) != positive]
    if against:
        conf = "conflicting ({0} item{1} point the other way)".format(
            len(against), "s" if len(against) > 1 else "")
    elif best["kind"] == "vote" and not best["earlier"] and best.get("free"):
        # A conscience vote (free_vote: true in config/de_stance.yaml) is the
        # strongest personal evidence the Bundestag produces; calling it
        # "whipped" told the German team the opposite (review, 29 Sept 2026).
        conf = "strong (free vote)"
    elif best["kind"] == "vote" and not best["earlier"]:
        conf = "moderate (whipped vote)"
    elif len(directional) == 1:
        conf = "thin (only 1 evidence item on record)"
    else:
        conf = "consistent ({0} items)".format(len(directional))
    return best, col, conf


def party_lines(sitting, ev):
    """{party: 'ours' | 'theirs'} where 80%+ of a party's members placed on
    BUNDESTAG evidence sit on one side (at least ten of them)."""
    tally = {}
    for pid, items in ev.items():
        best, col, _ = place([e for e in items if not e["earlier"]])
        if best is None or col == "0":
            continue
        t = tally.setdefault(sitting[pid]["party"], [0, 0])
        t[0 if col in ("++", "+") else 1] += 1
    out = {}
    for party, (a, b) in tally.items():
        if a + b >= PARTY_LINE_MIN:
            out[party] = "ours" if a / (a + b) >= PARTY_LINE else (
                "theirs" if b / (a + b) >= PARTY_LINE else None)
    return out


def based_on(kind, date, today):
    try:
        days = (today - datetime.date.fromisoformat(date[:10])).days
    except ValueError:
        return LABEL[kind]
    if days < 60:
        age = "{0} weeks ago".format(max(1, days // 7))
    elif days < 730:
        age = "{0} months ago".format(max(2, round(days / 30.44)))
    else:
        age = "{0:.0f} years ago".format(days / 365.25)
    return "{0}, {1}".format(LABEL[kind], age)


def seat_of(r):
    text = r["constituency"] if r["mandate_won"] == "constituency" else r["electoral_list"]
    return (text or "").split(" (Bundestag")[0]


def build_rows(sitting, ev, today):
    lines = party_lines(sitting, ev)
    rows = []
    for pid, r in sitting.items():
        items = sorted(ev[pid], key=lambda e: e["date"], reverse=True)
        best, col, conf = place(items)
        if best is not None and best["earlier"]:
            line = lines.get(r["party"])
            if line and line != ("ours" if col in ("++", "+") else "theirs"):
                best, col, conf = None, None, (
                    "earlier-parliament evidence against the party line "
                    "(coalition discipline likely): check by hand")
        party = (r["party"] or "").replace("\xad", "")
        seat = seat_of(r)
        rows.append({
            "name": "{0} ({1}, {2})".format(r["name"], party, seat) if seat
                    else "{0} ({1})".format(r["name"], party),
            "column": col, "confidence": conf, "n": len(items),
            "based_on": based_on(best["kind"], best["date"], today) if best
                        else ("no placement" if items else "no evidence"),
            "profile": r["profile_url"] or "", "party": party, "seat": seat,
            "comments": " | ".join(e["line"] for e in items[:COMMENT_ITEMS]),
        })
    order = {c: i for i, c in enumerate(COLUMNS)}
    rows.sort(key=lambda x: (order.get(x["column"], 5), -x["n"], x["name"]))
    return rows


def write_sheet(path, rows):
    tally = {c: 0 for c in COLUMNS}
    unplaced = sum(1 for r in rows if r["column"] is None and r["n"])
    none = sum(1 for r in rows if not r["n"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(HEADER)
        for r in rows:
            if r["column"]:
                tally[r["column"]] += 1
            w.writerow([r["name"], *("1" if r["column"] == c else "" for c in COLUMNS), "",
                        r["based_on"], r["confidence"], r["n"], r["profile"], r["comments"],
                        r["party"], r["seat"]])
        w.writerow(["Totals - {0} sitting decision-makers".format(len(rows)),
                    *(tally[c] for c in COLUMNS), "",
                    "no evidence: {0}; on record, not placed: {1}".format(none, unplaced),
                    "", "", "", "", "", ""])
    return tally, unplaced, none


def slug_of(names, area):
    return names.get(area, "area-{0}".format(area)).lower().replace(" ", "-").replace(",", "")


def run(conn, area, stance_cfg, land_cfg, names, out_dir, preview, today, log=print):
    sitting = roster(conn)
    if sitting is None:
        log("de_5ca: the Bundestag roster has never been checked -- run "
            "tools/de_profiles.py --roster first. Nothing written.")
        return None
    ev, counts = gather(conn, area, sitting, stance_cfg, land_cfg, preview)
    if not any(ev.values()):
        return None
    rows = build_rows(sitting, ev, today)
    suffix = "-DRAFT-PREVIEW" if preview else ""
    path = os.path.join(out_dir, "de-5ca-bundestag-{0}{1}.csv".format(slug_of(names, area), suffix))
    tally, unplaced, none = write_sheet(path, rows)
    log("Bundestag {0}: {1} sitting, {2} placed, {3} on record not placed, {4} no "
        "evidence -> {5}".format(names.get(area, area), len(rows), sum(tally.values()),
                                 unplaced, none, path))
    log("    " + "  ".join("{0} x{1}".format(c, tally[c]) for c in COLUMNS))
    log("    evidence: {votes} votes, {speeches} speeches, {papers} authored papers, "
        "{land} Land-record items".format(**counts))
    by_party = {}
    for r in rows:
        t = by_party.setdefault(r["party"], {c: 0 for c in (*COLUMNS, "none")})
        t[r["column"] or "none"] += 1
    for party, t in sorted(by_party.items()):
        log("    {0:24} {1}".format(party, "  ".join("{0} {1}".format(k, v) for k, v in t.items())))
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", type=int)
    ap.add_argument("--all", action="store_true", help="every area with a reading")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--stance", default=STANCE_PATH)
    ap.add_argument("--land-record", default=LAND_PATH)
    ap.add_argument("--preview-drafts", action="store_true",
                    help="let DRAFT readings place members, into a preview file outside data/5ca")
    args = ap.parse_args()
    if not args.all and args.area is None:
        ap.error("--area N or --all")
    out_dir = args.out_dir or (tempfile.mkdtemp(prefix="de5ca-preview-")
                               if args.preview_drafts else OUT_DIR)
    if args.preview_drafts and os.path.abspath(out_dir) == os.path.abspath(OUT_DIR):
        ap.error("a draft preview never writes to data/5ca, which is in git")
    stance_cfg, land_cfg = load_yaml(args.stance), load_yaml(args.land_record)
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    excluded = {int(a) for a in (load_yaml(os.path.join(ROOT, "config", "stance_overrides.yaml"))
                                 .get("excluded_from_5ca") or [])}
    if args.area in excluded:
        print("area {0} is collated only, not a 5CA area".format(args.area))
        return 1
    areas = sorted({e.get("area") for s in ("divisions", "papers")
                    for e in stance_cfg.get(s) or [] if e.get("area")} - excluded) \
        if args.all else [args.area]
    conn = db.init_db(db.connect(args.db))
    today = datetime.date.today()
    written = [p for p in (run(conn, a, stance_cfg, land_cfg, names, out_dir,
                               args.preview_drafts, today) for a in areas) if p]
    every = [e for s in ("divisions", "papers") for e in stance_cfg.get(s) or []]
    every += [i for m in land_cfg.get("members") or [] for i in m.get("items") or []]
    counts = {k: sum(1 for e in every if status(e) == k)
              for k in ("confirmed", "draft", "unplaceable")}
    print("\n{0} sheet(s). Readings: {confirmed} confirmed, {draft} draft, {unplaceable} "
          "never-placeable.".format(len(written), **counts))
    if counts["draft"] and not args.preview_drafts:
        print("  A draft places NOBODY: its acts appear as evidence only. Confirm a reading "
              "by deleting its `draft: true` line, or see what the drafts would do with "
              "--preview-drafts.")
    if args.preview_drafts:
        print("  PREVIEW: drafts placed members. Not for circulation until confirmed.")
    print("  Target is blank: the campaigner's call. Never posted anywhere.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
