"""Australian member profiles and the Federal Parliament vote tracker's data,
from the store alone.

    from src import au_profiles
    data = au_profiles.build(conn, entries, area_names)

Christopher (9 October 2026) asked for member profiles and public vote pages
for Ireland and Australia once the US version was merged. This is the US
build (src/us_profiles.py) on the Australian store. tools/make_au_votes.py
renders it into partner_site/au-votes.html; nothing here fetches, posts or
writes.

WHAT A PROFILE HOLDS: identity (OpenAustralia person ID, the APH Handbook's
PHID where the store has one, party, electorate or state, chamber, current or
not) and the member's record ON OUR GROUND only:
  * every recorded Aye, No or pair on a division on our ground, with the
    question and the motion moved before it;
  * speeches, motions moved and notices given on our ground (au_speeches):
    counts by kind and the latest few, one line each with a link (never the
    text or the excerpt);
  * their 5CA placement per area, ONLY from signed readings.
The store holds no bill sponsor (au_bills has none), so there is no bills
section, as tools/au_5ca.py places nobody on one.

ON OUR GROUND. A division is listed by tools/au_5ca.listed for some visible
area (its own text matched, or the stance file reads it), exactly as on the
5CA sheets. A speech when its stored VISIBLE areas are not empty and the
judge has not scored it 0. Migration (src/partner.py HIDDEN_AREAS) is matched
and stored, never shown.

PAIRS ARE SHOWN AS PAIRS. Hansard lists who was paired but not which side each
partner took (tools/au_rollcalls.py stores 'Paired', never guessing). A pair
is shown as PAIRED, with no side, in no lobby and in no direction.

THE HARD RULE. A division's direction is a SIGNED human judgement in
config/au_stance.yaml. An entry still carrying `draft: true` is unsigned, and
an unsigned division is emitted with NO direction fields at all. Every entry
was drafted on 9 October 2026 and none is signed, so today the page labels
nobody.

COMPACT VOTES. Positions are one string per division, one character per member
in `members` order: Y Aye, N No, P Paired (side not published), O any other
recorded answer, '.' not on that division.
"""

from __future__ import annotations

import datetime
import json

from src import readings5ca as r5
from src.partner import HIDDEN_AREAS
from src.us_profiles import reading_of

POS_CODE = {"Aye": "Y", "No": "N", "Paired": "P"}
SHOWN = 3
CHAMBER = {"house": "House of Representatives", "senate": "Senate"}


def _areas(text):
    """The VISIBLE areas: migration is matched and stored, never shown."""
    try:
        return [int(a) for a in json.loads(text or "[]") if int(a) not in HIDDEN_AREAS]
    except (ValueError, TypeError):
        return []


def _clip(text, n):
    return " ".join((text or "").split())[:n]


def bill_url(bill_id):
    """The APH's page for a bill ID (as tools/au_monitor.py)."""
    return ("https://www.aph.gov.au/Parliamentary_Business/Bills_Legislation/"
            "Bills_Search_Results/Result?bId={0}".format(bill_id))


def phid_url(phid):
    return "https://www.aph.gov.au/Senators_and_Members/Parliamentarian?MPID={0}".format(phid)


def listed_areas(d, entries):
    """The visible areas on which tools/au_5ca.listed lists this division."""
    own = set(_areas(d["own_areas"]))
    return [a for a in _areas(d["areas"]) if d["division_key"] in entries or a in own]


def _table(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def build(conn, entries, area_names, placements=None, today=None):
    """The page's data (module docstring). `placements` is
    {person_id: {area: {...}}} from SIGNED readings only (tools/make_au_votes.py
    builds it with tools/au_5ca.build_rows)."""
    today = today or datetime.date.today().isoformat()
    members = {r["person_id"]: dict(r) for r in conn.execute("SELECT * FROM au_members")}
    sitting = {k for k, m in members.items() if m["current"]}

    divisions = []
    for r in conn.execute("SELECT * FROM au_divisions ORDER BY date DESC, chamber, number DESC"):
        d = dict(r)
        areas = listed_areas(d, entries)
        if areas:
            d["_areas"] = sorted(set(areas))
            divisions.append(d)
    votes = {d["division_key"]: {v["person_id"]: (v["position"], v["party"]) for v in conn.execute(
        "SELECT person_id, position, party FROM au_votes WHERE division_key=?",
        (d["division_key"],))} for d in divisions}

    with_record = set(sitting)
    for vs in votes.values():
        with_record.update(vs)
    listed = sorted(with_record, key=lambda p: (((members.get(p) or {}).get("name") or p)
                                                .split()[-1:], p))
    index = {pid: i for i, pid in enumerate(listed)}

    out_members = []
    for pid in listed:
        m = members.get(pid) or {}
        if not m:
            last = next((vs[pid] for vs in votes.values() if pid in vs), (None, None))
            m = {"name": pid, "party": last[1]}
        out_members.append({
            "id": pid, "name": m.get("name") or pid, "party": m.get("party"),
            "where": m.get("electorate"), "chamber": m.get("house"), "phid": m.get("phid"),
            "in_office": pid in sitting})

    bill_titles = {}
    for r in conn.execute("SELECT bill_id, title FROM au_bills"):
        bill_titles[r["bill_id"]] = r["title"]

    out_divs = []
    for d in divisions:
        vs = votes[d["division_key"]]
        codes = ["."] * len(listed)
        parties = {}
        for pid, (position, party) in vs.items():
            code = POS_CODE.get(position or "", "O")
            if pid in index:
                codes[index[pid]] = code
            p = parties.setdefault(party or "?", {"Y": 0, "N": 0, "P": 0, "O": 0})
            p[code] += 1
        reading, direction = reading_of(entries.get(d["division_key"]))
        try:
            bill_ids = [b for b in json.loads(d["bill_ids"] or "[]") if b]
        except ValueError:
            bill_ids = []
        item = {
            "key": d["division_key"], "chamber": d["chamber"], "date": (d["date"] or "")[:10],
            "number": d["number"],
            "title": _clip(d["minor_heading"] or d["major_heading"], 200),
            "question": _clip(d["question"], 300), "motion": _clip(d["motion"], 400),
            "bills": [{"id": b, "title": _clip(bill_titles.get(b), 160), "url": bill_url(b)}
                      for b in bill_ids[:4]],
            "ayes": d["ayes"], "noes": d["noes"], "pairs": d["pairs"],
            "areas": d["_areas"], "parties": parties, "url": d["source_url"],
            "pos": "".join(codes), "reading": reading,
        }
        # THE GATE: direction exists in the data ONLY for a signed reading.
        if direction is not None:
            item["direction"] = direction
        out_divs.append(item)

    speeches = {}
    if _table(conn, "au_speeches"):
        for s in conn.execute("SELECT person_id, date, chamber, kind, major_heading, minor_heading, "
                              "url, areas, triage_score FROM au_speeches WHERE person_id IS NOT NULL "
                              "ORDER BY date DESC, speech_key DESC"):
            if s["person_id"] not in index or s["triage_score"] == 0 or not _areas(s["areas"]):
                continue
            rec = speeches.setdefault(s["person_id"], {"count": 0, "kinds": {}, "latest": []})
            rec["count"] += 1
            kind = s["kind"] or "speech"
            rec["kinds"][kind] = rec["kinds"].get(kind, 0) + 1
            if len(rec["latest"]) < SHOWN:
                rec["latest"].append({
                    "date": (s["date"] or "")[:10], "kind": kind, "chamber": s["chamber"],
                    "title": _clip(s["minor_heading"] or s["major_heading"], 140), "url": s["url"]})

    out_place = {}
    for pid, per in (placements or {}).items():
        if pid in index and per:
            out_place[pid] = {str(a): v for a, v in per.items() if a not in HIDDEN_AREAS}

    return {
        "built": today,
        "areas": {str(k): v for k, v in sorted(area_names.items()) if k not in HIDDEN_AREAS},
        "members": out_members,
        "divisions": out_divs,
        "speeches": speeches,
        "placements": out_place,
        "readings": {"divisions_signed": sum(1 for d in out_divs if d["reading"] == "signed"),
                     "divisions_awaiting": sum(1 for d in out_divs
                                               if d["reading"] == "awaiting sign-off"),
                     "file": r5.file_counts(entries)},
    }
