"""Words since the last vote, for the new countries with speeches and member votes.

The UK's tools/since_last_vote.py (what each member has said on an area since
they last voted on it, ranked by drift) generalised to the countries whose
store holds both speeches (src/chamber_store.py, <cc>_speeches) and votes:

    nl  Tweede Kamer: Handelingen speeches; roll calls per member, most votes
        a fractie's show of hands (X5, derived)
    ch  Nationalrat and Ständerat: Amtliches Bulletin; every member's vote
    at  Nationalrat and Bundesrat: protocol speeches; only the Klub's vote (X5)
    fr  Assemblée nationale: compte rendu; every deputy's vote (scrutins)
    be  Kamer: Integraal Verslag; every member's vote (naamstemmingen)
    hr  Sabor: e-Doc transcripts; every member's vote          (11 October 2026,
    sk  NR SR: the debate record; every member's vote           branch gaps-speeches;
    pl  Sejm: per-statement transcripts; every deputy's vote    additive, the five
    br  Câmara: plenary speeches; every deputy's vote           above unchanged)

    python3 tools/country_since_vote.py --cc be [--area 2] [--write]

PER AREA, PER MEMBER. For every member who has spoken on an area (the
speech's OWN areas, as the chamber collector classified them passage by
passage; migration matched but hidden, as everywhere), their LAST recorded
vote on that area (a watched or tier-1 division, procedure never, as the
debate packs and the live read choose them) and every speech on the area
dated after it, with excerpts. A speech on or before the vote's day is not
"since". A member whose last vote on the area came after all their words
has no row.

NO DRIFT BEFORE SIGN-OFF. The same rule as the live read (src/country_live.py):
"drift" may only be NAMED where both

  * the vote's reading is CONFIRMED by a named signer (config/<cc>_stance.yaml,
    src/country5ca.py) and gives that side a value, and
  * a person or the free session judge has read the WORDS since
    (--queue-out writes the template, --reads loads it; `read_by` must name
    who read them), never an API call.

Then a member who voted against us whose words since read "with" or
"unclear" is DRIFTING OUR WAY (the UK's prospect), and one who voted with us
whose words read "against" is DRIFTING AWAY (the UK's call); otherwise
"holding to the vote". Before that the command lists the words beside the
vote, labelled "awaiting sign-off", ranked by recency (latest speech first)
and volume (more speeches first), never by an inferred contradiction.

A read is tied to the words it read: its key carries the date of the
latest speech, so a new speech since makes the read stale and the row goes
back to "words not read".

PARTY-GROUP VOTES NEVER NAME DRIFT. A position DERIVED from the group's
vote (X5: the Netherlands' shows of hands, every Austrian vote) is the
group's record, not the member's. It is listed, labelled, and never queued
for a read.

Read-only on the store. Nothing is posted or DMed; no AI API calls.
"""

from __future__ import annotations

import datetime
import os
import re

from src import chamber_store as cs
from src import country5ca as c5
from src import country_debatepack as dp
from src import country_live as cl
from src import debatepack_i18n as i18n

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "parl-monitor.db")
BRIEFS = os.path.join(ROOT, "data", "briefs")

# The countries with a speech collector AND votes in their store.
COUNTRIES = tuple(cc for cc in ("nl", "ch", "at", "fr", "be", "hr", "sk", "pl", "br")
                  if "speeches" in cs.COUNTRIES.get(cc, ()) and cc in c5.SPECS)

AWAITING = cl.AWAITING
OUR_WAY = "DRIFTING OUR WAY"
AWAY = "DRIFTING AWAY"
HOLDING = "holding to the vote"
NOT_READ = "words not read"
DERIVED = "group's vote (X5): no drift named"
NO_VALUE = "confirmed, this side carries no value"
ORDER = {OUR_WAY: 0, AWAY: 1, NOT_READ: 2, AWAITING: 3, HOLDING: 4, NO_VALUE: 5, DERIVED: 6}

EXCERPTS = 3            # excerpts shown per member
EXCERPT = 240
TOP = 40                # members shown per area

# A government speaker is not a member voting in the chamber (a minister in
# France and Belgium, the Federal Council in Switzerland, a Bundesminister
# in Austria, a Dutch minister or state secretary; from 11 October 2026 the
# Slovak "predseda vlády" and the roles the HR, PL and BR collectors set).
GOVERNMENT = re.compile(r"minist|federal councillor|bundesrät|government|regering|gouvernement"
                        r"|staatssecretaris|secr[ée]taire d|staatssekret|bundeskanzler|"
                        r"vizekanzler|kanzler|vlád", re.I)


def area_label(area):
    return "{0} ({1})".format(area, i18n.area_label("en", area))


def _areas(raw):
    return [a for a in c5.areas_of(raw) if a not in dp.HIDDEN_AREAS]


# --- the words ---------------------------------------------------------------------------

def speeches(conn, cc, since=None, until=None):
    """Every stored speech on our ground (non-hidden areas), oldest first."""
    sql = ("SELECT speech_id, date, chamber, debate_id, debate, speaker, party, role, person_id, "
           "excerpt, url, areas FROM {0}_speeches WHERE 1=1".format(cc))
    params = []
    if since:
        sql += " AND date >= ?"
        params.append(since)
    if until:
        sql += " AND date <= ?"
        params.append(until)
    rows = c5._rows(conn, sql + " ORDER BY date, speech_id", params)
    out = []
    for r in rows:
        r["areas"] = _areas(r.get("areas"))
        if r["areas"]:
            out.append(r)
    return out


def is_government(role):
    return bool(role) and bool(GOVERNMENT.search(role))


# --- the votes ---------------------------------------------------------------------------

def area_divisions(conn, cc, wl=None, until=None):
    """The watched or tier-1, non-procedural divisions with areas, newest first
    (the live read's and debate packs' choice of vote, src/country_debatepack.py)."""
    spec = c5.SPECS[cc]
    out = []
    for r in c5.qualifying(conn, cc, wl):
        if until and (r.get("date") or "") > until:
            continue
        r["areas_shown"] = _areas(r.get("areas"))
        if not r["areas_shown"]:
            continue
        r["kind"] = c5.vote_kind(r.get("question"), spec.hint(r))[0]
        if r["kind"] == "procedural":
            continue
        out.append(r)
    # Newest first; on one day the vote on the whole text before its articles.
    out.sort(key=lambda r: (r.get("date") or "", r["kind"] in dp.DECISIVE, r["key"]), reverse=True)
    return out


def last_votes(conn, cc, need, divs):
    """{(area, member_id): (division, position)} for each wanted pair: the newest
    division on that area where the member's position is a cast vote (yes, no
    or abstain). Positions are read only for divisions that can still answer."""
    spec = c5.SPECS[cc]
    left = set(need)
    by_area = {}
    for a, mid in left:
        by_area.setdefault(a, set()).add(mid)
    out = {}
    for d in divs:
        if not left:
            break
        wanted = [a for a in d["areas_shown"] if by_area.get(a)]
        if not wanted:
            continue
        for p in c5.positions(conn, cc, d["key"]):
            if spec.side(p.get("position")) not in ("yea", "nay", "abstain"):
                continue
            mid = str(p["member_id"])
            for a in wanted:
                if mid in by_area[a]:
                    out[(a, mid)] = (d, p)
                    by_area[a].discard(mid)
                    left.discard((a, mid))
    return out


# --- reads of the words (a person or the free session judge) -----------------------------

def read_key(area, member_id, latest):
    return "a{0}|{1}|{2}".format(area, member_id, latest)


def load_reads(path):
    """(read_by, {key: 'with' | 'against' | 'unclear'}). Without a named
    `read_by` nothing counts: a read must say who read the words."""
    import yaml
    if not path or not os.path.exists(path):
        return None, {}
    with open(path, encoding="utf-8") as h:
        raw = yaml.safe_load(h) or {}
    by = str(raw.get("read_by") or "").strip() or None
    if not by:
        return None, {}
    out = {}
    for key, val in (raw.get("reads") or {}).items():
        v = str(val or "").strip().lower()
        if v in cl.WORD_READS:
            out[str(key)] = v
    return by, out


# --- the gather --------------------------------------------------------------------------

def state_of(reading, read):
    """The row's state from the last vote's reading and the read of the words."""
    if reading["derived"]:
        return DERIVED
    if reading["state"] != "confirmed":
        return AWAITING
    if reading["stance"] in (None, 0):
        return NO_VALUE
    if not read:
        return NOT_READ
    with_us = reading["stance"] > 0
    if not with_us and read in ("with", "unclear"):
        return OUR_WAY
    if with_us and read == "against":
        return AWAY
    return HOLDING


def gather(conn, cc, areas=None, since=None, until=None, config_dir=None, wl=None,
           reads=None, read_by=None):
    """{'areas': {area: [row]}, 'unmatched': n, 'no_vote': {area: n}, 'government': n,
    'speeches': n, 'divisions': n}. A row:
    {area, member_id, name, party, vote: division, position, reading, speeches: [...],
     latest, n, key, read, state}. `since`: each member's last vote on or before
    that date (the UK's --since); `until`: speeches up to that date."""
    if cc not in COUNTRIES:
        raise ValueError("{0}: no speeches and member votes in one store".format(cc))
    spec = c5.SPECS[cc]
    roster = dp.roster(conn, cc)
    want = set(areas) if areas else None
    words = {}
    unmatched = government = 0
    said = speeches(conn, cc, until=until)
    for s in said:
        if is_government(s.get("role")):
            government += 1
            continue
        member, _how = cl.match_member(roster, s.get("speaker"), s.get("party"), s.get("person_id"))
        if member is None:
            unmatched += 1
            continue
        mid = str(member["member_id"])
        for a in s["areas"]:
            if want is None or a in want:
                words.setdefault((a, mid), {"member": member, "rows": []})["rows"].append(s)
    divs = area_divisions(conn, cc, wl, until=since or until)
    last = last_votes(conn, cc, words, divs)
    entries = c5.load(cc, config_dir)[0]
    reads = reads or {}
    out, no_vote = {}, {}
    for (a, mid), got in words.items():
        if (a, mid) not in last:
            no_vote[a] = no_vote.get(a, 0) + 1
            continue
        d, p = last[(a, mid)]
        after = [s for s in got["rows"] if (s.get("date") or "") > (d.get("date") or "")]
        if not after:
            continue
        reading = cl.vote_reading(entries, spec, d, p)
        latest = max(s["date"] for s in after)
        key = read_key(a, mid, latest)
        read = None if reading["derived"] else reads.get(key)
        m = got["member"]
        out.setdefault(a, []).append({
            "area": a, "member_id": mid, "name": m.get("name") or p.get("name"),
            "party": m.get("party") or p.get("party"), "vote": d, "position": p,
            "reading": reading, "speeches": sorted(after, key=lambda s: (s["date"], s["speech_id"]),
                                                   reverse=True),
            "latest": latest, "n": len(after), "key": key, "read": read,
            "state": state_of(reading, read)})
    for a, rows in out.items():
        rows.sort(key=lambda r: dp.fold(r["name"]))
        rows.sort(key=lambda r: r["n"], reverse=True)
        rows.sort(key=lambda r: r["latest"], reverse=True)
        rows.sort(key=lambda r: ORDER.get(r["state"], 9))
    return {"cc": cc, "areas": dict(sorted(out.items())), "unmatched": unmatched,
            "government": government, "no_vote": no_vote, "speeches": len(said),
            "divisions": len(divs), "read_by": read_by,
            "derived_country": spec.derived is not None}


def by_member(got):
    """{member_id: [row]} across areas (the member profiles' optional section)."""
    out = {}
    for rows in got["areas"].values():
        for r in rows:
            out.setdefault(r["member_id"], []).append(r)
    for rows in out.values():
        rows.sort(key=lambda r: (ORDER.get(r["state"], 9), r["area"]))
    return out


# --- rendering ---------------------------------------------------------------------------

def vote_text(r):
    d, rd = r["vote"], r["reading"]
    what = d.get("question") or d.get("subject") or d["key"]
    if d.get("subject") and dp.fold(d["subject"])[:40] not in dp.fold(what):
        what = "{0}, on {1}".format(what, d["subject"])
    bits = "{0}{1} on {2} ({3})".format(
        rd["word"], " (the group's vote, X5)" if rd["derived"] else "", dp.clip(what, 120),
        d.get("date") or "?")
    if rd["stance"] not in (None, 0):
        bits += ": {0}, confirmed by {1}".format("with us" if rd["stance"] > 0 else "against us",
                                                rd["by"])
    elif rd["state"] == "confirmed":
        bits += ": confirmed, this side carries no value"
    else:
        bits += ": " + AWAITING
    return bits


def state_line(r, read_by=None):
    s = r["state"]
    if s in (OUR_WAY, AWAY, HOLDING):
        return "**{0}**: words since read \"{1}\" by {2}, against the confirmed vote.".format(
            s, r["read"], read_by or "a named reader")
    if s == NOT_READ:
        return "Words since not read yet: no drift named (fill --reads)."
    if s == DERIVED:
        return "The group's vote, given to each member (X5): never the member's own record, " \
               "never named as drift."
    if s == NO_VALUE:
        return "The reading is confirmed but gives this side no value: no drift named."
    return "AWAITING SIGN-OFF: words listed beside the vote; no drift named."


def render_row(r, read_by=None, excerpts=EXCERPTS, heading="###"):
    out = ["{0} {1} ({2})".format(heading, r["name"], r["party"] or "?"), "",
           "- Last vote on area {0}: {1}".format(area_label(r["area"]), vote_text(r)),
           "- Since: {0} speech{1}, latest {2}.".format(r["n"], "" if r["n"] == 1 else "es",
                                                      r["latest"]),
           "- " + state_line(r, read_by)]
    for s in r["speeches"][:excerpts]:
        out.append("  - {0}, {1}: \"{2}\"{3}".format(
            s["date"], dp.clip(s.get("debate") or "(untitled)", 80),
            dp.clip(s.get("excerpt") or "", EXCERPT),
            " ({0})".format(s["url"]) if s.get("url") else ""))
    if r["n"] > excerpts:
        out.append("  - and {0} more in the store.".format(r["n"] - excerpts))
    out.append("")
    return out


INTRO = ("What each member has said on an area since they last voted on it. Words are the "
         "record's own, matched passage by passage (the chamber collector's classification); "
         "the vote is the member's latest watched or tier-1 vote on the area, procedure never. "
         "Drift is NAMED only where a signer has confirmed what that vote means for CitizenGO "
         "AND a person or the free session judge has read the words since; until then rows "
         "are labelled \"awaiting sign-off\" and ranked by recency and volume, never by an "
         "inferred contradiction. A group's vote given to each member (X5) never names drift.")


def render(got, today=None, top=TOP, sample=False):
    cc = got["cc"]
    today = today or datetime.date.today().isoformat()
    out = ["# Words since the last vote: {0} ({1}), {2}".format(dp.name_of(cc), cc, today), ""]
    if sample:
        out += ["**SAMPLE**: built from a copy of the published store, never sent.", ""]
    out += [INTRO, ""]
    if got["derived_country"]:
        out += [c5.SPECS[cc].note, ""]
    total = sum(len(v) for v in got["areas"].values())
    named = sum(1 for v in got["areas"].values() for r in v if r["state"] in (OUR_WAY, AWAY))
    out.append("{0} member-area row(s); drift named on {1}. {2} speech(es) on our ground read, "
               "{3} vote(s) on our ground considered.".format(total, named, got["speeches"],
                                                             got["divisions"]))
    if got.get("read_by"):
        out.append("Words read by: {0}.".format(got["read_by"]))
    out.append("")
    if not got["areas"]:
        out += ["Nobody has spoken on our ground since their last recorded vote on that area.", ""]
    for a, rows in got["areas"].items():
        confirmed = any(r["reading"]["state"] == "confirmed" for r in rows)
        out += ["## Area {0}: {1} member(s)".format(area_label(a), len(rows)), ""]
        if not confirmed:
            out += ["*AWAITING SIGN-OFF: no reading of these votes is confirmed for CitizenGO, so "
                    "nothing below is drift or a placement.*", ""]
        for r in rows[:top]:
            out += render_row(r, got.get("read_by"))
        if len(rows) > top:
            out += ["{0} more member(s) on this area (raise --top).".format(len(rows) - top), ""]
    foot = []
    if got["no_vote"]:
        foot.append("Spoke on an area with no recorded vote of theirs on it: " + "; ".join(
            "area {0}: {1}".format(a, n) for a, n in sorted(got["no_vote"].items())) + ".")
    if got["unmatched"]:
        foot.append("{0} speech(es) not matched to one member of the roster (not counted).".format(
            got["unmatched"]))
    if got["government"]:
        foot.append("{0} government speech(es) left out (not a member's vote to set them "
                    "against).".format(got["government"]))
    if foot:
        out += ["## Not counted", ""] + ["- " + f for f in foot] + [""]
    return "\n".join(out).rstrip() + "\n"


def queue_text(got, include_all=False):
    """The reads template for a person or the free session judge: one key per
    member and area, with the words since. By default only rows whose vote
    reading is confirmed and whose words are unread (the rows a read can
    turn into drift); `include_all` adds the rows awaiting sign-off.
    Derived (X5) rows are never queued."""
    cc = got["cc"]
    want = (NOT_READ, AWAITING) if include_all else (NOT_READ,)
    out = ["# Words since the last vote: {0} ({1})".format(dp.name_of(cc), cc),
           "# For each key write with, against or unclear: what the member's OWN WORDS below say",
           "# about CitizenGO's position on the area. Leave blank when unsure. Judge the words",
           "# only, never the party, the person or the vote. Name yourself in read_by.",
           "read_by: \"\"", "reads:"]
    n = 0
    for a, rows in got["areas"].items():
        for r in rows:
            if r["state"] not in want:
                continue
            n += 1
            out.append("  # {0} ({1}), area {2}; {3} speech(es) since {4}".format(
                r["name"], r["party"] or "?", area_label(a), r["n"], r["vote"].get("date")))
            for s in r["speeches"][:EXCERPTS]:
                out.append("  #   {0}: {1}".format(s["date"], dp.clip(s.get("excerpt") or "", 300)))
            out.append("  \"{0}\": \"\"".format(r["key"]))
    if not n:
        out.append("  {}")
    return "\n".join(out) + "\n", n


# --- the member profiles' optional section ------------------------------------------------

def profile_section(rows, read_by=None):
    """Markdown lines for one member's profile (src/member_profiles.py, --since-vote)."""
    if not rows:
        return []
    out = ["## Words since the last vote ({0})".format(len(rows)), "",
           "What they have said on an area since their last recorded vote on it. Drift is named "
           "only once a signer has confirmed the vote's reading and someone has read the words; "
           "otherwise \"awaiting sign-off\". A group's vote (X5) never names drift.", ""]
    for r in rows:
        out.append("- Area {0}: last vote {1}; {2} speech(es) since, latest {3}. {4}".format(
            area_label(r["area"]), vote_text(r), r["n"], r["latest"], state_line(r, read_by)))
        for s in r["speeches"][:2]:
            out.append("  - {0}, {1}: \"{2}\"".format(
                s["date"], dp.clip(s.get("debate") or "(untitled)", 80),
                dp.clip(s.get("excerpt") or "", EXCERPT)))
    out.append("")
    return out
