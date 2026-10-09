"""Irish member profiles and the Oireachtas vote tracker's data, from the store alone.

    from src import ie_profiles
    data = ie_profiles.build(conn, entries, bill_entries, area_names)

Christopher (9 October 2026) asked for member profiles and public vote pages
for Ireland and Australia once the US version was merged. This is the US
build (src/us_profiles.py) on the Oireachtas store. tools/make_ie_votes.py
renders it into partner_site/ie-votes.html; nothing here fetches, posts or
writes.

WHAT A PROFILE HOLDS: identity (memberCode, party, constituency or Seanad
panel, House, sitting or not) and the member's record ON OUR GROUND only:
  * every recorded Ta, Nil or Staon on a division on our ground, with the
    question and, for an amendment vote, the amendment text phase 1b read
    from the transcript (clipped);
  * Private Members' bills on our ground they sponsored (a Government bill is
    sponsored by an office, never by a member, and is not listed);
  * parliamentary questions on our ground: a count and the latest few, one
    line each (the heading, the office asked, the stored ONE-SENTENCE
    takeaway) with a link. Never the question's text, never the answer;
  * speeches on our ground: a count and the latest few, one line each with a
    link (never the text or the excerpt);
  * their 5CA placement per area, ONLY from signed readings.

ON OUR GROUND. A division is listed by tools/ie_5ca.listed for some visible
taxonomy area (its own text matched, the stance file reads it, or it is a
stage question on a bill the stance file reads), exactly as on the 5CA
sheets. A bill, question or speech when its stored VISIBLE areas are not empty
and the judge has not scored it 0 (a bill the stance file reads always is).
Migration (src/partner.py HIDDEN_AREAS) is matched and stored, never shown.

COMMITTEE DIVISIONS ARE FLAGGED, AND KEPT APART. A committee division is
taken among that committee's members only, usually on an amendment at
committee stage. A TD with no position on one was not on the committee, not
absent. So each division carries `committee` (the committee's name, or null in
plenary); the page tags it, filters on it, and lists a member's committee
votes in their own section. They still count for 5CA, as tools/ie_5ca.py
counts them (a recorded vote in a committee of that House).

THE HARD RULE. A division's direction is a SIGNED human judgement in
config/ie_stance.yaml. An entry still carrying `draft: true` is unsigned, and
an unsigned division is emitted with NO direction fields at all (the
EU/US tracker's gate). Every entry was drafted on 9 October 2026 and none is
signed, so today the page labels nobody.

COMPACT VOTES. Positions are one string per division, one character per member
in `members` order: Y Ta, N Nil, A Staon (a recorded abstention), O any other
recorded answer, '.' not on that division.
"""

from __future__ import annotations

import datetime
import json

from src import readings5ca as r5
from src.partner import HIDDEN_AREAS
from src.us_profiles import reading_of

POS_CODE = {"Yes": "Y", "No": "N", "Abstain": "A"}
SHOWN = 3            # speeches: count + the latest three
QUESTIONS_SHOWN = 5  # questions: count + the latest five
HOUSE = {"dail": "Dáil", "seanad": "Seanad"}


def _areas(text):
    """The VISIBLE areas: migration is matched and stored, never shown."""
    try:
        return [int(a) for a in json.loads(text or "[]") if int(a) not in HIDDEN_AREAS]
    except (ValueError, TypeError):
        return []


def _clip(text, n):
    return " ".join((text or "").split())[:n]


def bill_url(key):
    try:
        year, number = (key or "").split("/")
    except ValueError:
        return None
    return "https://www.oireachtas.ie/en/bills/bill/{0}/{1}/".format(year, number)


def bill_label(key):
    try:
        year, number = (key or "").split("/")
    except ValueError:
        return key or ""
    return "Bill {0} of {1}".format(number, year)


def division_url(d):
    """The Oireachtas page for a plenary division (as tools/ie_monitor.py).
    Committee divisions have no page we could confirm: the day's record."""
    if d["chamber"] in ("dail", "seanad"):
        return "https://www.oireachtas.ie/en/debates/vote/{0}/{1}/{2}/".format(
            d["house_key"], d["date"], (d["vote_id"] or "").replace("vote_", ""))
    return (d["debate_uri"] or "").replace("/debate/main", "/debate/mul@/main.xml") or None


def listed_areas(d, entries, bill_entries):
    """The visible areas on which tools/ie_5ca.listed lists this division."""
    own = set(_areas(d["own_areas"]))
    amendment = "amendment" in (d["subject"] or "").lower()
    out = []
    for area in _areas(d["areas"]):
        if d["division_key"] in entries or area in own:
            out.append(area)
        elif not amendment and d["bill_key"] in bill_entries:
            out.append(area)
    return out


def _table(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def build(conn, entries, bill_entries, area_names, placements=None, today=None):
    """The page's data (module docstring). `placements` is
    {member_code: {area: {"column", "based_on", "chamber", ...}}} from SIGNED
    readings only (tools/make_ie_votes.py builds it with tools/ie_5ca.build_rows)."""
    today = today or datetime.date.today().isoformat()
    members = {r["member_code"]: dict(r) for r in conn.execute("SELECT * FROM ie_members")}
    sitting = {k for k, m in members.items() if not m["end_date"]}

    # --- divisions on our ground ---------------------------------------------
    divisions = []
    for r in conn.execute("SELECT * FROM ie_divisions ORDER BY date DESC, division_key DESC"):
        d = dict(r)
        areas = listed_areas(d, entries, bill_entries)
        if areas:
            d["_areas"] = sorted(set(areas))
            divisions.append(d)
    votes = {d["division_key"]: {v["member_code"]: (v["position"], v["party"]) for v in conn.execute(
        "SELECT member_code, position, party FROM ie_votes WHERE division_key=?",
        (d["division_key"],))} for d in divisions}
    bill_titles = {}
    for k in {d["bill_key"] for d in divisions if d["bill_key"]}:
        row = conn.execute("SELECT title FROM ie_bills WHERE bill_key=?", (k,)).fetchone()
        bill_titles[k] = row["title"] if row else None

    # Listed: everyone sitting, plus anyone who voted on a division here.
    with_record = set(sitting)
    for vs in votes.values():
        with_record.update(vs)
    listed = sorted(with_record, key=lambda p: ((members.get(p) or {}).get("last_name") or
                                                (members.get(p) or {}).get("name") or p, p))
    index = {pid: i for i, pid in enumerate(listed)}

    out_members = []
    for pid in listed:
        m = members.get(pid) or {}
        if not m:
            last = next((vs[pid] for vs in votes.values() if pid in vs), (None, None))
            m = {"name": pid, "party": last[1]}
        out_members.append({
            "id": pid, "name": m.get("name") or pid, "party": m.get("party"),
            "where": m.get("represents"), "house": m.get("house"),
            "in_office": pid in sitting})

    # --- divisions, with tallies, party splits and positions ------------------
    out_divs = []
    for d in divisions:
        vs = votes[d["division_key"]]
        codes = ["."] * len(listed)
        parties = {}
        for pid, (position, party) in vs.items():
            code = POS_CODE.get(position or "", "O")
            if pid in index:
                codes[index[pid]] = code
            p = parties.setdefault(party or "?", {"Y": 0, "N": 0, "A": 0, "O": 0})
            p[code] += 1
        reading, direction = reading_of(entries.get(d["division_key"]))
        amendment = None
        if d.get("amendment_text"):
            text, ref = d["amendment_text"], d.get("amendment_ref")
            # The transcript usually names its own ref ("I move amendment No. 1").
            amendment = _clip("{0}: {1}".format(ref, text) if ref and ref.lower() not in
                              text.lower() else text, 400)
        item = {
            "key": d["division_key"], "chamber": d["chamber"],
            "house": (d["house_key"] or "/").split("/")[0], "committee": d["committee"],
            "date": (d["date"] or "")[:10], "title": _clip(d["debate_title"], 200),
            "subject": _clip(d["subject"], 200), "amendment": amendment,
            "bill": d["bill_key"], "bill_label": bill_label(d["bill_key"]) if d["bill_key"] else "",
            "bill_title": bill_titles.get(d["bill_key"]), "bill_url": bill_url(d["bill_key"])
            if d["bill_key"] else None,
            "outcome": d["outcome"], "ta": d["ta"], "nil": d["nil"], "staon": d["staon"],
            "areas": d["_areas"], "parties": parties, "url": division_url(d),
            "pos": "".join(codes), "reading": reading,
        }
        # THE GATE: direction exists in the data ONLY for a signed reading.
        if direction is not None:
            item["direction"] = direction
        out_divs.append(item)

    # --- Private Members' bills on our ground, by sponsor ----------------------
    bills = {}
    for b in conn.execute("SELECT bill_key, title, areas, introduced, last_stage, act, "
                          "triage_score, source FROM ie_bills WHERE source = 'Private Member'"):
        if b["triage_score"] == 0 and b["bill_key"] not in bill_entries:
            continue
        if _areas(b["areas"]):
            bills[b["bill_key"]] = dict(b)
    out_bills, bill_index, member_bills = [], {}, {}
    for s in conn.execute("SELECT bill_key, member_code, is_primary FROM ie_sponsors "
                          "WHERE member_code IS NOT NULL ORDER BY bill_key"):
        key, pid = s["bill_key"], s["member_code"]
        if key not in bills or pid not in index:
            continue
        if key not in bill_index:
            b = bills[key]
            item = {"key": key, "label": bill_label(key), "title": _clip(b["title"], 200),
                    "url": bill_url(key), "areas": _areas(b["areas"]), "stage": b["last_stage"],
                    "act": b["act"], "reading": None}
            entry = bill_entries.get(key)
            st = r5.status(entry)
            if st == "confirmed":
                # THE GATE again: a bill reading's direction only when signed.
                item["reading"] = "signed"
                item["direction"] = {"sponsored": entry.get("sponsored"),
                                     "why_sponsored": (entry.get("why_sponsored") or "").strip()}
            elif st == "unplaceable":
                item["reading"] = "signed: evidence only"
            elif entry:
                item["reading"] = "awaiting sign-off"
            bill_index[key] = len(out_bills)
            out_bills.append(item)
        member_bills.setdefault(pid, []).append(
            [bill_index[key], "P" if s["is_primary"] else "S", (bills[key]["introduced"] or "")[:10]])
    for rows in member_bills.values():
        rows.sort(key=lambda r: r[2], reverse=True)

    # --- questions and speeches: counts and the latest few, one line each -----
    questions = {}
    if _table(conn, "ie_questions"):
        for q in conn.execute("SELECT member_code, date, ref, qtype, minister, department, heading, "
                              "answer_takeaway, url, areas, triage_score FROM ie_questions "
                              "WHERE member_code IS NOT NULL ORDER BY date DESC, question_key DESC"):
            if q["member_code"] not in index or q["triage_score"] == 0 or not _areas(q["areas"]):
                continue
            rec = questions.setdefault(q["member_code"], {"count": 0, "latest": []})
            rec["count"] += 1
            if len(rec["latest"]) < QUESTIONS_SHOWN:
                # The heading and the one-sentence takeaway: never the answer.
                rec["latest"].append({
                    "date": (q["date"] or "")[:10], "ref": q["ref"], "type": q["qtype"],
                    "to": _clip(q["minister"] or q["department"], 80),
                    "heading": _clip(q["heading"], 140),
                    "takeaway": _clip(q["answer_takeaway"], 200), "url": q["url"]})
    speeches = {}
    if _table(conn, "ie_speeches"):
        for s in conn.execute("SELECT member_code, date, chamber, committee, section_title, url, "
                              "areas, triage_score FROM ie_speeches WHERE member_code IS NOT NULL "
                              "ORDER BY date DESC, speech_key DESC"):
            if s["member_code"] not in index or s["triage_score"] == 0 or not _areas(s["areas"]):
                continue
            rec = speeches.setdefault(s["member_code"], {"count": 0, "latest": []})
            rec["count"] += 1
            if len(rec["latest"]) < SHOWN:
                rec["latest"].append({
                    "date": (s["date"] or "")[:10],
                    "where": s["committee"] or HOUSE.get(s["chamber"], s["chamber"]),
                    "title": _clip(s["section_title"], 140), "url": s["url"]})

    out_place = {}
    for pid, per in (placements or {}).items():
        if pid in index and per:
            out_place[pid] = {str(a): v for a, v in per.items() if a not in HIDDEN_AREAS}

    return {
        "built": today,
        "areas": {str(k): v for k, v in sorted(area_names.items()) if k not in HIDDEN_AREAS},
        "members": out_members,
        "divisions": out_divs,
        "bills": out_bills,
        "member_bills": member_bills,
        "questions": questions,
        "speeches": speeches,
        "placements": out_place,
        "readings": {"divisions_signed": sum(1 for d in out_divs if d["reading"] == "signed"),
                     "divisions_awaiting": sum(1 for d in out_divs
                                               if d["reading"] == "awaiting sign-off"),
                     "file": r5.file_counts(entries, bill_entries)},
    }
