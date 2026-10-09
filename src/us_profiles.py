"""US member profiles and the US vote tracker's data, from the store alone.

    from src import us_profiles
    data = us_profiles.build(conn, entries, bill_entries, area_names)

Christopher (9 October 2026) asked for member profiles and vote pages with
parity to the UK, starting with the US. tools/make_us_votes.py renders this
into partner_site/us-votes.html; nothing here fetches, posts or writes.

WHAT A PROFILE HOLDS: identity (Bioguide, party, state and district, chamber,
in office or not) and the member's record ON OUR GROUND only:
  * every recorded position on a roll call on our ground, with the motion;
  * bills on our ground they sponsored or cosponsored, and withdrawals;
  * floor speeches on our ground: a count and the latest few, one line each
    with a link (never the text);
  * their 5CA placement per area, ONLY from signed readings.

ON OUR GROUND. A roll call is listed by tools/us_5ca.listed for some taxonomy
area: its own text matched the area, or config/us_stance.yaml reads it, or it
is a passage-type vote on a bill the stance file reads. The procedural tail of
an omnibus that only borrows its bill's area is left off, as on the 5CA sheets.
A bill is on our ground when its stored areas are not empty and the judge has
not scored it 0 (a bill the stance file reads always is); a speech when its
stored areas are not empty.

THE HARD RULE. A vote's direction (for or against our side) is a SIGNED human
judgement in config/us_stance.yaml. An entry still carrying `draft: true` is
unsigned, and an unsigned division is emitted with NO direction fields at all:
the page cannot colour what was never signed, structurally (the EU tracker's
gate). Unsigned divisions carry `reading: "awaiting sign-off"` and nothing
from the drafted entry, not even its drafted wording of what a Yea meant.

COMPACT VOTES. Positions are one string per division, one character per
member in `members` order: Y Yea, N Nay, P Present, V Not Voting, O any other
recorded answer, '.' not on
that roll call (a different chamber, or not yet or no longer a member).
"""

from __future__ import annotations

import datetime
import json

from src import readings5ca as r5

POS_CODE = {"Yea": "Y", "Nay": "N", "Present": "P", "Not Voting": "V"}
# Anything else (a name in a Speaker election) is 'O', shown as recorded: never
# read as a Yea or a Nay.
PASSAGE = ("passage", "suspend the rules and pass", "concur", "suspend the rules and agree")
SPEECHES_SHOWN = 3
DELEGATE_DAYS = 120
BILL_TYPES = {"hr": "H.R.", "s": "S.", "hres": "H.Res.", "sres": "S.Res.", "hjres": "H.J.Res.",
              "sjres": "S.J.Res.", "hconres": "H.Con.Res.", "sconres": "S.Con.Res."}


def _areas(text):
    try:
        return [int(a) for a in json.loads(text or "[]")]
    except (ValueError, TypeError):
        return []


def bill_label(key):
    """'119/hr/21' -> 'H.R. 21'."""
    try:
        _c, kind, num = (key or "").split("/")
    except ValueError:
        return key or ""
    return "{0} {1}".format(BILL_TYPES.get(kind, kind.upper()), num)


def bill_url(key):
    """Congress.gov's page for a bill key."""
    try:
        congress, kind, num = (key or "").split("/")
    except ValueError:
        return None
    words = {"hr": "house-bill", "s": "senate-bill", "hres": "house-resolution",
             "sres": "senate-resolution", "hjres": "house-joint-resolution",
             "sjres": "senate-joint-resolution", "hconres": "house-concurrent-resolution",
             "sconres": "senate-concurrent-resolution"}
    if kind not in words:
        return None
    return "https://www.congress.gov/bill/{0}th-congress/{1}/{2}".format(congress, words[kind], num)


def division_url(d):
    """The Clerk's or the Senate's own page for a roll call."""
    if d["chamber"] == "house":
        year = (d["date"] or "")[:4]
        return "https://clerk.house.gov/Votes/{0}{1}".format(year, d["roll"]) if year else None
    return ("https://www.senate.gov/legislative/LIS/roll_call_votes/vote{0}{1}/"
            "vote_{0}_{1}_{2:05d}.htm".format(d["congress"], d["session"], int(d["roll"])))


def listed_areas(d, entries, bill_entries):
    """The taxonomy areas on which this roll call is evidence (module docstring)."""
    out = []
    own = set(_areas(d["own_areas"]))
    q = (d["question"] or "").lower()
    for area in _areas(d["areas"]):
        if d["division_key"] in entries or area in own:
            out.append(area)
        elif d["bill_key"] in bill_entries and any(p in q for p in PASSAGE):
            out.append(area)
    return out


def reading_of(entry):
    """What the page may say about a division's direction.

    Returns (reading, direction): reading is 'signed', 'signed: evidence only'
    or 'awaiting sign-off'; direction is a dict ONLY for a signed reading with
    values, else None."""
    st = r5.status(entry)
    if st == "confirmed":
        yea, nay = entry.get("yea"), entry.get("nay")
        ours = None
        if (yea or 0) > (nay or 0):
            ours = "Yea"
        elif (nay or 0) > (yea or 0):
            ours = "Nay"
        return "signed", {"yea": yea, "nay": nay, "ours": ours,
                          "why_yea": (entry.get("why_yea") or "").strip(),
                          "why_nay": (entry.get("why_nay") or "").strip(),
                          "aye_means": (entry.get("aye_means") or "").strip(),
                          "signed": str(entry.get("signed") or "")}
    if st == "unplaceable":
        return "signed: evidence only", None
    return "awaiting sign-off", None


def roster(conn):
    """{bioguide: row} and {chamber: sitting set}; sitting = on that chamber's
    latest roll call (the Clerk and the Senate list every member, Not Voting
    included), as tools/us_5ca.chamber_roster has it."""
    members = {r["bioguide"]: dict(r) for r in conn.execute("SELECT * FROM us_members")}
    sitting = {}
    for chamber in ("house", "senate"):
        latest = conn.execute("SELECT division_key FROM us_divisions WHERE chamber=? "
                              "ORDER BY date DESC, roll DESC LIMIT 1", (chamber,)).fetchone()
        sitting[chamber] = {r[0] for r in conn.execute(
            "SELECT bioguide FROM us_votes WHERE division_key=?", (latest[0],))} if latest else set()
    return members, sitting


def build(conn, entries, bill_entries, area_names, placements=None, today=None):
    """The page's data (module docstring). `placements` is
    {bioguide: {area: {"column", "based_on", "chamber"}}} from SIGNED readings
    only (tools/make_us_votes.py builds it with tools/us_5ca.build_rows)."""
    today = today or datetime.date.today().isoformat()
    members, sitting = roster(conn)

    # --- divisions on our ground ---------------------------------------------
    divisions = []
    for r in conn.execute("SELECT * FROM us_divisions ORDER BY date DESC, chamber, roll DESC"):
        d = dict(r)
        areas = listed_areas(d, entries, bill_entries)
        if not areas:
            continue
        d["_areas"] = sorted(set(areas))
        divisions.append(d)
    bill_titles = {}
    keys = {d["bill_key"] for d in divisions if d["bill_key"]}
    for k in keys:
        row = conn.execute("SELECT title FROM us_bills WHERE bill_key=?", (k,)).fetchone()
        bill_titles[k] = row["title"] if row else None

    # --- who is listed: sitting, plus anyone with a record on our ground -----
    votes = {}
    for d in divisions:
        votes[d["division_key"]] = {
            v["bioguide"]: (v["position"], v["party"], v["state"]) for v in conn.execute(
                "SELECT bioguide, position, party, state FROM us_votes WHERE division_key=?",
                (d["division_key"],))}
    with_record = set(sitting["house"]) | set(sitting["senate"])
    for vs in votes.values():
        with_record.update(vs)

    bills = {}
    for b in conn.execute("SELECT bill_key, title, sponsor, introduced, areas, law, "
                          "latest_action, latest_action_at, cosponsors, triage_score FROM us_bills "
                          "WHERE areas IS NOT NULL AND areas NOT IN ('', '[]')"):
        # The judge's 0 ("not ours", tools/us_triage.py) drops a keyword match,
        # unless a human reads the bill in the stance file.
        if b["triage_score"] == 0 and b["bill_key"] not in bill_entries:
            continue
        if _areas(b["areas"]):
            bills[b["bill_key"]] = dict(b)
    acts = {}
    for key, b in bills.items():
        if b["sponsor"]:
            acts.setdefault(b["sponsor"], []).append(
                {"bill": key, "kind": "sponsored", "date": (b["introduced"] or "")[:10]})
    for c in conn.execute("SELECT bill_key, bioguide, sponsored_at, withdrawn_at, original "
                          "FROM us_cosponsors"):
        if c["bill_key"] not in bills:
            continue
        a = {"bill": c["bill_key"], "kind": "cosponsored", "date": (c["sponsored_at"] or "")[:10]}
        if c["withdrawn_at"]:
            a["withdrawn"] = c["withdrawn_at"][:10]
        acts.setdefault(c["bioguide"], []).append(a)

    speeches = {}
    for s in conn.execute("SELECT bioguide, date, title, url, areas, chamber FROM "
                          "us_record_speeches WHERE bioguide IS NOT NULL "
                          "ORDER BY date DESC, speech_key"):
        if not _areas(s["areas"]):
            continue
        rec = speeches.setdefault(s["bioguide"], {"count": 0, "latest": []})
        rec["count"] += 1
        if len(rec["latest"]) < SPEECHES_SHOWN:
            rec["latest"].append({"date": (s["date"] or "")[:10],
                                  "title": " ".join((s["title"] or "").split())[:140],
                                  "url": s["url"]})

    # Listed: everyone sitting, plus anyone who voted on a roll call here
    # (labelled not in office). A sponsor or speaker who is neither is not.
    listed = sorted(with_record, key=lambda p: ((members.get(p) or {}).get("name") or p, p))
    index = {pid: i for i, pid in enumerate(listed)}

    row = conn.execute("SELECT MAX(date) FROM us_divisions WHERE chamber='house'").fetchone()
    latest_house = row[0] if row else None
    out_members = []
    for pid in listed:
        m = members.get(pid)
        if not m:
            # On a roll call but missing from us_members: party and state at the vote.
            last = next((vs[pid] for vs in votes.values() if pid in vs), (None, None, None))
            m = {"name": pid, "party": last[1], "state": last[2]}
        chamber = m.get("chamber")
        if pid in sitting["senate"]:
            chamber = "senate"
        elif pid in sitting["house"]:
            chamber = "house"
        in_office = pid in sitting["house"] or pid in sitting["senate"]
        delegate = (m.get("state") or "") == "XX"
        if delegate and not in_office:
            # The Clerk lists a delegate only on Committee of the Whole votes,
            # never on passage: in office when seen within DELEGATE_DAYS of the
            # House's latest roll call.
            in_office = bool(m.get("as_of") and latest_house and
                             (datetime.date.fromisoformat(latest_house[:10]) -
                              datetime.date.fromisoformat(m["as_of"][:10])).days <= DELEGATE_DAYS)
        out_members.append({
            "id": pid, "name": m.get("name") or pid, "party": m.get("party"),
            "state": m.get("state"), "district": m.get("district"),
            "chamber": chamber, "delegate": delegate, "in_office": in_office})

    # --- divisions, with tallies, party splits and positions ------------------
    out_divs = []
    for d in divisions:
        vs = votes[d["division_key"]]
        codes = ["."] * len(listed)
        parties = {}
        for pid, (position, party, _state) in vs.items():
            code = POS_CODE.get(position or "", "O")
            if pid in index:
                codes[index[pid]] = code
            p = parties.setdefault(party or "?", {"Y": 0, "N": 0, "P": 0, "V": 0, "O": 0})
            p[code] += 1
        reading, direction = reading_of(entries.get(d["division_key"]))
        motion = (d["amendment_text"] or d["description"] or "").strip()
        item = {
            "key": d["division_key"], "chamber": d["chamber"], "date": (d["date"] or "")[:10],
            "roll": d["roll"], "congress": d["congress"], "session": d["session"],
            "question": d["question"], "motion": " ".join(motion.split())[:400],
            "amendment": d["amendment_author"],
            "bill": d["bill_key"], "bill_label": bill_label(d["bill_key"]) if d["bill_key"] else
            (d["legis_num"] or ""), "bill_title": bill_titles.get(d["bill_key"]),
            "result": d["result"], "yeas": d["yeas"], "nays": d["nays"],
            "present": d["present"], "not_voting": d["not_voting"],
            "areas": d["_areas"], "parties": parties, "url": division_url(d),
            "bill_url": bill_url(d["bill_key"]), "pos": "".join(codes),
            "reading": reading,
        }
        # THE GATE: direction exists in the data ONLY for a signed reading.
        if direction is not None:
            item["direction"] = direction
        out_divs.append(item)

    # Bills: one list, and per member [bill index, 'S' sponsored / 'C'
    # cosponsored, date, withdrawn date or ''], newest first.
    out_bills, bill_index, member_bills = [], {}, {}
    for pid in listed:
        mine = sorted(acts.get(pid, []), key=lambda a: a["date"] or "", reverse=True)
        if not mine:
            continue
        rows = []
        for a in mine:
            key = a["bill"]
            if key not in bill_index:
                b = bills[key]
                item = {"key": key, "label": bill_label(key),
                        "title": " ".join((b["title"] or "").split())[:200],
                        "url": bill_url(key), "areas": _areas(b["areas"]),
                        "law": b["law"], "cosponsors": b["cosponsors"],
                        "reading": "awaiting sign-off" if bill_entries.get(key) else None}
                entry = bill_entries.get(key)
                st = r5.status(entry)
                if st == "confirmed":
                    # THE GATE again: a bill reading's direction only when signed.
                    item["reading"] = "signed"
                    item["direction"] = {
                        "sponsored": entry.get("sponsored"),
                        "cosponsored": entry.get("cosponsored"),
                        "why_sponsored": (entry.get("why_sponsored") or "").strip(),
                        "why_cosponsored": (entry.get("why_cosponsored") or "").strip()}
                elif st == "unplaceable":
                    item["reading"] = "signed: evidence only"
                bill_index[key] = len(out_bills)
                out_bills.append(item)
            rows.append([bill_index[key], "S" if a["kind"] == "sponsored" else "C",
                         a["date"] or "", a.get("withdrawn") or ""])
        member_bills[pid] = rows

    out_place = {}
    for pid, per in (placements or {}).items():
        if pid in index and per:
            out_place[pid] = {str(a): v for a, v in per.items()}

    signed = sum(1 for d in out_divs if d["reading"] == "signed")
    return {
        "built": today,
        "areas": {str(k): v for k, v in sorted(area_names.items())},
        "members": out_members,
        "divisions": out_divs,
        "bills": out_bills,
        "member_bills": member_bills,
        "speeches": {pid: s for pid, s in speeches.items() if pid in index},
        "placements": out_place,
        "readings": {"divisions_signed": signed,
                     "divisions_awaiting": sum(1 for d in out_divs
                                               if d["reading"] == "awaiting sign-off"),
                     "file": r5.file_counts(entries, bill_entries)},
    }
