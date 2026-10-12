"""Member records on our ground for Holyrood, the Senedd and the Assembly.

Christopher, 9 October 2026: parity with the Westminster member pages. An
MSP, MS or MLA had a name, a party, posts and (where a verdict was signed)
a handful of scored votes. This builds, offline from the store, what each
member actually did on our issues:

  * DIVISIONS on our ground, with the lobby they were in, and the signed 5CA
    direction of that lobby ONLY where a human has signed the reading in
    config/{sp,sd,ni}_stance.yaml. An unsigned division says "awaiting
    sign-off"; a reading settled as not placeable says so. No verdicts.
  * QUESTIONS asked and MOTIONS lodged or supported on our ground: one line
    and a link, never the answer (the PQ rule).
  * SPEECHES on our ground (Holyrood and the Senedd keep a speech ledger;
    the Assembly has none): date, heading, one quoted line.
  * Their 5CA PLACEMENT per area, read from the same build_rows the 5CA
    sheets use, so a profile and a sheet can never disagree.

THE WATCHING-BRIEF RULES HOLD. Holyrood motions and questions are shown at
tier 1 and counted at tier 2 (the sp_items.tier rule: Holyrood motion culture
is congratulatory, and tier 2 filed a dental fundraiser under assisted dying).
Area 11 (migration) is collated, never part of our ground on a member page.

Reads the store only. Never writes it, never posts.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Collated areas: kept in the store, never shown as a member's record.
NOT_OUR_GROUND = {11}
# One-line receipts per area and kind; the counts above them are whole.
# Holyrood alone holds 12,000 speeches, so a cap per KIND keeps the
# divisions from being crowded out by a busy speaker.
PER_KIND = {"vote": 4, "motion": 2, "signed": 2, "pq": 2, "spoke": 2}
KIND_ORDER = {"vote": 0, "motion": 1, "signed": 2, "pq": 3, "spoke": 4}
KINDS = ("vote", "motion", "signed", "pq", "spoke", "absent")
# Holyrood records every MSP in every division. 'Not Voted' is data (and is
# counted as "absent"), but it is not a position, so it is never a receipt.
NOT_A_POSITION = {"Not Voted", "DidNotVote"}

SP_QUESTION = ("https://www.parliament.scot/chamber-and-committees/"
               "questions-and-answers/question?ref={0}")
# Amendment pages (S7M-01517.3) answer with a bot check; the base motion's
# page lists every amendment with its result, so links go there.
SP_MOTION = ("https://www.parliament.scot/chamber-and-committees/"
             "votes-and-motions/{0}")
SD_QUESTION = "https://record.senedd.wales/WrittenQuestion/{0}"
SD_PLENARY = "https://record.senedd.wales/Plenary/{0}"
NI_DIVISION = ("https://data.niassembly.gov.uk/plenary.asmx/"
               "GetDivisionResult?documentId={0}")


def _tool(name):
    """Import tools/<name>.py (the 5CA builders live there, not in src)."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def ground(raw, tier=None, excluded=NOT_OUR_GROUND):
    """Our-ground areas of a row, as strings; [] when off our ground."""
    if tier is not None and tier != 1:
        return []
    try:
        areas = json.loads(raw or "[]")
    except ValueError:
        return []
    return [str(a) for a in areas if a not in excluded]


def base_ref(reference):
    return (reference or "").split(".")[0]


def one_line(text, limit=140):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


# ---------------------------------------------------------------- readings

def reading(entry, lobby_value_key, lobby_why_key):
    """(status, direction, why) for one lobby against one stance entry.

    status: 'signed' (a human-confirmed direction for THIS lobby),
            'not-placeable' (read and settled: the division cannot say who
            is with us), 'awaiting' (no reading, or a draft one), or
            'no-position' (an abstention or absence: never a direction).
    """
    if lobby_value_key is None:
        return "no-position", None, None
    if not entry:
        return "awaiting", None, None
    if entry.get("draft"):
        return "awaiting", None, None
    value = entry.get(lobby_value_key)
    if value is None:
        # Read, confirmed, and carrying no value for any lobby: not
        # placeable. A confirmed entry that values one lobby only leaves
        # the other unread rather than settled.
        lobbies = [k for k in ("aye", "no", "for", "against") if k in entry]
        return ("not-placeable", None, None) if not lobbies else \
            ("awaiting", None, None)
    return "signed", int(value), " ".join((entry.get(lobby_why_key) or "").split())


def division_status(entry):
    """The division-level status for a brief: 'signed' when a human has
    confirmed at least one lobby's direction, 'not-placeable' when settled
    as unable to discriminate, otherwise 'awaiting'."""
    if not entry or entry.get("draft"):
        return "awaiting"
    lobbies = [k for k in ("aye", "no", "for", "against")
               if entry.get(k) is not None]
    return "signed" if lobbies else "not-placeable"


# ------------------------------------------------------------- accumulator

class Ledger:
    """Per-member, per-area records with whole counts and capped receipts."""

    def __init__(self):
        self.by = {}

    def add(self, pid, areas, item):
        if not pid or not areas:
            return
        item = {k: v for k, v in item.items() if v is not None}
        kind = item["k"]
        if kind == "vote" and item.get("v") in NOT_A_POSITION:
            kind = "absent"
        for area in areas:
            block = self.by.setdefault(str(pid), {}).setdefault(
                area, {"n": {}, "items": []})
            block["n"][kind] = block["n"].get(kind, 0) + 1
            if kind != "absent":
                block["items"].append(item)

    def finish(self, placements=None):
        out = {}
        placements = placements or {}
        for pid in set(self.by) | set(placements):
            areas = {}
            for area, block in (self.by.get(pid) or {}).items():
                # Signed votes first (they carry the direction), then the
                # newest of everything else.
                # Votes first (signed directions before everything), then
                # motions, questions and speeches; newest first within each,
                # and a small cap per kind so one busy speaker cannot crowd
                # out the divisions.
                items = sorted(block["items"], key=lambda i: i.get("d") or "",
                               reverse=True)
                items.sort(key=lambda i: (KIND_ORDER.get(i["k"], 9),
                                          0 if i.get("dir") is not None else 1))
                kept, seen = [], {}
                for it in items:
                    if seen.get(it["k"], 0) >= PER_KIND.get(it["k"], 2):
                        continue
                    seen[it["k"]] = seen.get(it["k"], 0) + 1
                    kept.append(it)
                areas[area] = {"n": block["n"], "items": kept}
            place = {a: c for a, c in (placements.get(pid) or {}).items()
                     if c != "0"}
            if areas or place:
                out[pid] = {"areas": areas, "place": place}
        return out


def placements(nation, conn, areas, log=None):
    """{person_id: {area: column}} from the nation's 5CA builder.

    The same build_rows the published sheets use, so the profile and the
    sheet agree by construction. Excluded areas and builder failures are
    skipped and logged, never fatal.
    """
    out = {}
    tool = {"scotland": "sp_5ca", "wales": "sd_5ca", "ni": "ni_5ca"}[nation]
    mod = _tool(tool)
    for area in areas:
        try:
            if nation == "wales":
                rows, _former, _unknown = mod.build_rows(
                    conn, area, mod.load_stance())
            else:
                rows = mod.build_rows(conn, area, mod.load_stance(section="divisions"),
                                      mod.load_stance(section="motions"))
        except Exception as exc:               # noqa: BLE001 - logged, not fatal
            if log:
                log("{0} 5CA area {1}: {2}".format(nation, area, exc))
            continue
        for r in rows:
            pid = r.get("person_id")
            if pid:
                out.setdefault(str(pid), {})[str(area)] = r["column"]
    return out


# ------------------------------------------------------------------ nations

def scotland(conn, place=None):
    sp5 = _tool("sp_5ca")
    entries = sp5.load_stance(section="divisions")
    motion_entries = sp5.load_stance(section="motions")
    led = Ledger()
    for r in conn.execute(
            "SELECT v.person_id, v.vote, d.reference, d.title, d.dated, "
            "d.vote_for, d.vote_against, d.result, d.areas, d.tier "
            "FROM sp_votes v JOIN sp_divisions d ON d.key = v.division_key "
            "WHERE d.source = 'votesmotion' AND d.areas IS NOT NULL "
            "AND d.areas != '[]'"):
        entry = entries.get(r["reference"])
        # Tier 1, or a division a human has written a reading for.
        areas = ground(r["areas"], None if entry else r["tier"])
        if not areas:
            continue
        lobby = {"Yes": ("aye", "why_aye"), "No": ("no", "why_no")}.get(r["vote"])
        status, direction, why = reading(entry, *(lobby or (None, None)))
        led.add(r["person_id"], areas, {
            "k": "vote", "d": r["dated"], "v": r["vote"],
            "t": one_line("{0} {1}".format(r["reference"] or "", r["title"] or "")),
            "res": "{0} {1}-{2}".format(r["result"] or "", r["vote_for"],
                                        r["vote_against"]).strip(),
            "u": SP_MOTION.format(base_ref(r["reference"])) if r["reference"] else None,
            "rs": status, "dir": direction, "why": one_line(why, 160) if why else None})
    for r in conn.execute(
            "SELECT id, kind, reference, title, body, dated, msp_id, areas, tier "
            "FROM sp_items WHERE msp_id IS NOT NULL AND areas IS NOT NULL "
            "AND areas != '[]'"):
        areas = ground(r["areas"], r["tier"])
        if not areas:
            continue
        if r["kind"] == "question":
            led.add(r["msp_id"], areas, {
                "k": "pq", "d": r["dated"],
                "t": one_line("{0}: {1}".format(r["reference"] or "", r["body"] or r["title"])),
                "u": SP_QUESTION.format(r["reference"]) if r["reference"] else None})
        elif r["kind"] == "motion":
            status, direction, why = _motion_reading(motion_entries.get(r["reference"]))
            led.add(r["msp_id"], areas, {
                "k": "motion", "d": r["dated"],
                "t": one_line("{0}: {1}".format(r["reference"] or "", r["title"])),
                "u": SP_MOTION.format(base_ref(r["reference"])) if r["reference"] else None,
                "rs": status, "dir": direction})
    for r in conn.execute(
            "SELECT s.person_id, s.lodged, i.reference, i.title, i.dated, "
            "i.msp_id, i.areas, i.tier FROM sp_supports s JOIN sp_items i "
            "ON i.id = 'sp-motion:' || s.motion_uid"):
        areas = ground(r["areas"], r["tier"])
        if not areas or r["person_id"] == r["msp_id"]:
            continue
        status, direction, _why = _motion_reading(motion_entries.get(r["reference"]))
        led.add(r["person_id"], areas, {
            "k": "signed", "d": r["lodged"] or r["dated"],
            "t": one_line("{0}: {1}".format(r["reference"] or "", r["title"])),
            "u": SP_MOTION.format(base_ref(r["reference"])) if r["reference"] else None,
            "rs": status, "dir": direction})
    for r in conn.execute("SELECT person_id, dated, heading, excerpt, areas "
                          "FROM sp_events WHERE areas IS NOT NULL"):
        areas = ground(r["areas"])
        led.add(r["person_id"], areas, {
            "k": "spoke", "d": r["dated"], "t": one_line(r["heading"], 110),
            "q": _quote(r["excerpt"], r["heading"])})
    return led.finish(place)


def _quote(excerpt, heading):
    """The quoted line, unless it only repeats the heading."""
    q = one_line(excerpt, 200)
    if not q or " ".join((heading or "").split()).lower().startswith(q.lower()[:60]):
        return None
    return q


def _motion_reading(entry):
    if not entry or entry.get("draft"):
        return "awaiting", None, None
    if entry.get("sponsored") is None:
        return "not-placeable", None, None
    return "signed", int(entry["sponsored"]), entry.get("why_sponsored")


def wales(conn, place=None):
    from src import devolved
    sd5 = _tool("sd_5ca")
    entries = sd5.load_stance()
    index = devolved.roster(conn)
    resolved = {}

    def pid_of(name):
        if name not in resolved:
            got, _missing = devolved.resolve([name], index)
            resolved[name] = got.get(name)
        return resolved[name]

    led = Ledger()
    for r in conn.execute(
            "SELECT v.member_name, v.result AS vote, d.key, d.meeting_id, "
            "d.title, d.dated, d.total_for, d.total_against, d.total_abstain, "
            "d.result, d.areas, d.tier FROM sd_votes v JOIN sd_divisions d "
            "ON d.key = v.division_key WHERE d.areas IS NOT NULL "
            "AND d.areas != '[]'"):
        entry = entries.get(str(r["key"]))
        areas = ground(r["areas"], None if entry else r["tier"])
        pid = pid_of(r["member_name"])
        if not areas or not pid:
            continue
        lobby = {"For": ("for", "why_for"),
                 "Against": ("against", "why_against")}.get(r["vote"])
        status, direction, why = reading(entry, *(lobby or (None, None)))
        led.add(pid, areas, {
            "k": "vote", "d": r["dated"], "v": r["vote"],
            "t": one_line(r["title"]),
            "res": "{0} {1}-{2}-{3}".format(r["result"] or "", r["total_for"],
                                            r["total_against"], r["total_abstain"]),
            "u": SD_PLENARY.format(r["meeting_id"]) if r["meeting_id"] else None,
            "rs": status, "dir": direction, "why": one_line(why, 160) if why else None})
    for r in conn.execute(
            "SELECT reference, member_name, dated, body, areas, tier FROM sd_items "
            "WHERE kind = 'question' AND areas IS NOT NULL AND areas != '[]'"):
        areas = ground(r["areas"], r["tier"])
        pid = pid_of(r["member_name"])
        if not areas or not pid:
            continue
        num = (r["reference"] or "").replace("WQ", "")
        led.add(pid, areas, {
            "k": "pq", "d": r["dated"],
            "t": one_line("{0}: {1}".format(r["reference"] or "", r["body"])),
            "u": SD_QUESTION.format(num) if num else None})
    sittings = {r[0]: r[1] for r in conn.execute(
        "SELECT dated, MAX(meeting_id) FROM sd_divisions GROUP BY dated")}
    for r in conn.execute("SELECT member_name, dated, heading, excerpt, areas "
                          "FROM sd_events WHERE areas IS NOT NULL"):
        pid = pid_of(r["member_name"])
        meeting = sittings.get(r["dated"])
        led.add(pid, ground(r["areas"]), {
            "k": "spoke", "d": r["dated"], "t": one_line(r["heading"], 110),
            "q": _quote(r["excerpt"], r["heading"]),
            "u": SD_PLENARY.format(meeting) if meeting else None})
    return led.finish(place)


def ni(conn, place=None):
    ni5 = _tool("ni_5ca")
    entries = ni5.load_stance(section="divisions")
    motion_entries = ni5.load_stance(section="motions")
    led = Ledger()
    for r in conn.execute(
            "SELECT v.person_id, v.vote, d.doc_id, d.subject, d.item_name, "
            "d.dated, d.areas FROM ni_votes v JOIN ni_divisions d "
            "ON d.doc_id = v.doc_id WHERE d.areas IS NOT NULL AND d.areas != '[]'"):
        areas = ground(r["areas"])
        if not areas:
            continue
        entry = entries.get(str(r["doc_id"]))
        lobby = {"aye": ("aye", "why_aye"), "no": ("no", "why_no")}.get(r["vote"])
        status, direction, why = reading(entry, *(lobby or (None, None)))
        led.add(r["person_id"], areas, {
            "k": "vote", "d": r["dated"], "v": (r["vote"] or "").capitalize(),
            "t": one_line(r["item_name"] or r["subject"]),
            "u": NI_DIVISION.format(r["doc_id"]),
            "rs": status, "dir": direction, "why": one_line(why, 160) if why else None})
    for r in conn.execute(
            "SELECT reference, title, dated, url, tabler_person_id, areas "
            "FROM ni_items WHERE kind = 'question' AND tabler_person_id IS NOT NULL "
            "AND areas IS NOT NULL AND areas != '[]'"):
        led.add(r["tabler_person_id"], ground(r["areas"]), {
            "k": "pq", "d": r["dated"],
            "t": one_line("{0}: {1}".format(r["reference"] or "", r["title"])),
            "u": (r["url"] or "").replace("http://", "https://") or None})
    for r in conn.execute(
            "SELECT s.person_id, s.sequence, s.doc_id, i.title, i.dated, i.areas, i.url "
            "FROM ni_sponsors s JOIN ni_items i ON i.id = 'ni-motion:' || s.doc_id "
            "WHERE i.areas IS NOT NULL AND i.areas != '[]'"):
        status, direction, _why = _motion_reading(motion_entries.get(str(r["doc_id"])))
        led.add(r["person_id"], ground(r["areas"]), {
            "k": "motion" if r["sequence"] == 1 else "signed", "d": r["dated"],
            "t": one_line(r["title"]), "u": r["url"] or None,
            "rs": status, "dir": direction})
    return led.finish(place)


BUILDERS = {"scotland": scotland, "wales": wales, "ni": ni}


def build(nation, conn, log=None, members=None):
    """{person_id: intel} for one nation, placements included. `members`
    narrows the result to the ids a page lists."""
    from src import intel as _intel
    import yaml
    names = _intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    with open(os.path.join(ROOT, "config", "stance_overrides.yaml"),
              encoding="utf-8") as handle:
        excluded = {int(a) for a in
                    (yaml.safe_load(handle) or {}).get("excluded_from_5ca") or []}
    areas = sorted(set(names) - excluded)
    out = BUILDERS[nation](conn, placements(nation, conn, areas, log=log))
    if members is not None:
        keep = {str(m) for m in members}
        out = {k: v for k, v in out.items() if k in keep}
    return out


def area_labels():
    from src import intel as _intel
    names = _intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    return {str(a): n for a, n in names.items() if a not in NOT_OUR_GROUND}


def stats(profiles):
    """One line of counts for a run log."""
    n = {k: 0 for k in KINDS}
    placed = 0
    for p in profiles.values():
        placed += 1 if p["place"] else 0
        for block in p["areas"].values():
            for k, c in block["n"].items():
                n[k] = n.get(k, 0) + c
    return ("{0} members with a record ({1} placed in a 5CA area); "
            "{2} votes, {3} motions lodged, {4} supported, {5} questions, "
            "{6} speeches".format(len(profiles), placed, n["vote"], n["motion"],
                                  n["signed"], n["pq"], n["spoke"]))
