"""Campaign targets and outcomes for the new country editions (10 October 2026).

Item 7 of docs/country-parity-handover.md ("campaign targets"), for every new
country whose store holds member votes (src/country5ca.COUNTRIES). It
generalises the UK's tools/ca_campaign.py (src/evaluate.py) and
tools/campaign_targets.py to any country, on top of the 5CA layer
(src/country5ca.py), and keeps its rule: **only a CONFIRMED stance reading
places a member, and so only a confirmed reading may suggest a target.**

A campaign is one area in one chamber of one country. Its life:

1. OPEN. Snapshot every sitting member's 5CA placement on the area, as
   src/country5ca.build_rows makes it from the CONFIRMED readings in
   config/<cc>_stance.yaml. A forecast that was not kept cannot be scored, so
   the snapshot is the campaign's prediction. Before sign-off every member
   sits at 0 and the campaign records that it was opened "awaiting sign-off":
   it has no prediction to score. Re-opening the same slug after sign-off
   retakes the snapshot (targets and outcomes are kept).

2. TARGETS. Suggested targets come from confirmed placements only: the soft
   middle of the 5CA, `+` (secure them) and `-` (move them), and anyone whose
   confirmed record is MIXED. `++` are allies to mobilise and `--` are not
   expected to move; `0` has no confirmed evidence, so nothing is suggested
   for it. Members who voted on the area's votes whose readings are not yet
   confirmed are listed as CANDIDATES BY VOTE RECORD, each labelled "not a
   target until the stance is confirmed", with the bare record (how they
   voted, as the chamber records it) and no direction. Adding a target is a
   person's decision (`add --by NAME`); a member with no confirmed placement
   can be added only with a reason, and is stored as "chosen by NAME, no
   confirmed stance", never as a suggestion.

3. OUTCOME. The vote that settled it, by the store's division key, and OUR
   side (`yes` or `no`, as the chamber records it). Where the division has a
   confirmed reading, a stated side that contradicts it is refused (edit the
   stance file, which a named person signs, instead); where it has none, the
   side is recorded as stated by the person, and the score says so.

4. SCORE. What the members actually did on the outcome vote(s): with us,
   against us, abstained, or no vote recorded; by placement group (ally,
   opponent, no position) and for the targets. Like the UK, this counts
   correlation, never causation. A snapshot with no placements yields
   alignment counts only, and a vote dated before the snapshot is flagged as
   circular (it was evidence for the placements).

5. PERFORMANCE. The petition side (signatures, new members, money) joins
   from a Looker export per country, `data/looker/<cc>_campaigns.tsv`, in the
   same shape as the UK's `data/looker/en_gb_campaigns.tsv`
   (tools/load_looker_campaigns.py, docs/campaign-benchmarks.md). Only the UK
   has one today; for every new country the report says so plainly and
   names the file it expects. The join is by petition id (a campaign's
   `--petition` ids against the program's id segment), then by area (the
   keyword table of tools/log_campaign_performance.py, English, so a slug in
   another language may stay unmapped and is counted as such), then members
   named in a petition (first and last name both in its name). The file is
   read, never loaded into the store.

State is one JSON file per campaign, `data/campaigns/<cc>/<slug>.json`,
committed by whoever runs the command. The store is opened read-only. Nothing
is fetched, posted or scheduled: this is a manual command
(tools/country_campaign.py).
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import re

from src import country5ca as c5
from src import readings5ca as r5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN_DIR = os.path.join(ROOT, "data", "campaigns")
LOOKER_DIR = os.path.join(ROOT, "data", "looker")
EVAL_DIR = os.path.join(ROOT, "data", "5ca")

ALLY = ("++", "+")
OPPONENT = ("--", "-")
SUGGEST = ("+", "-")
NOT_A_TARGET = "not a target until the stance is confirmed"
AWAITING = "awaiting sign-off"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")

# The Looker list prefix each country's export is expected to filter on
# (`filters program: "<PREFIX>%"`). Germany's DE is seen in the UK export's
# notes; the rest follow the same two-letter pattern and are to be checked in
# Looker before the first pull. The loader accepts any prefix in the file and
# reports the ones it saw.
LIST_PREFIX = {cc: cc.upper() for cc in c5.COUNTRIES}


def area_name(area):
    from src.latam import AREA_LABELS
    return AREA_LABELS.get(area, "area {0}".format(area))


def today_iso(today=None):
    return today or datetime.date.today().isoformat()


# --- the campaign file ---------------------------------------------------------------

def campaign_path(cc, slug, base=None):
    return os.path.join(base or CAMPAIGN_DIR, cc, "{0}.json".format(slug))


def load_campaign(cc, slug, base=None):
    path = campaign_path(cc, slug, base)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as h:
        return json.load(h)


def save_campaign(camp, base=None):
    path = campaign_path(camp["cc"], camp["slug"], base)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as h:
        json.dump(camp, h, ensure_ascii=False, indent=1, sort_keys=True)
        h.write("\n")
    return path


def list_campaigns(cc=None, base=None):
    base = base or CAMPAIGN_DIR
    out = []
    if not os.path.isdir(base):
        return out
    for c in sorted(os.listdir(base)):
        if cc and c != cc:
            continue
        d = os.path.join(base, c)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".json"):
                with open(os.path.join(d, f), encoding="utf-8") as h:
                    out.append(json.load(h))
    return out


# --- the area in a chamber -------------------------------------------------------------

def area_entries(cc, chamber, area, config_dir=None):
    """The stance entries (drafts included) for one chamber and area."""
    divs, _, _ = c5.load(cc, config_dir)
    return {k: e for k, e in divs.items()
            if area in (e.get("areas") or []) and str(e.get("chamber") or "") == str(chamber)}


def chambers_for(cc, area, config_dir=None):
    divs, _, _ = c5.load(cc, config_dir)
    return sorted({str(e.get("chamber") or "") for e in divs.values()
                   if area in (e.get("areas") or [])})


def resolve_chamber(cc, area, chamber=None, config_dir=None):
    """The chamber to use, or raise ValueError saying what to pass."""
    spec = c5.SPECS[cc]
    have = chambers_for(cc, area, config_dir)
    if chamber:
        matches = [k for k, v in spec.chambers.items()
                   if chamber.lower() in (k.lower(), str(v).lower())]
        for k in matches:
            if k in have:
                return k
        return matches[0] if matches else chamber
    if len(have) == 1:
        return have[0]
    if not have:
        known = sorted(set(spec.chambers)) or []
        if len(known) == 1:
            return known[0]
        raise ValueError("no vote on {0} is in config/{1}_stance.yaml yet, so the chamber "
                         "cannot be read from it: pass --chamber ({2})".format(
                             area_name(area), cc, ", ".join(known) or "the store's chamber code"))
    raise ValueError("{0} has votes in more than one chamber ({1}): pass --chamber".format(
        area_name(area), ", ".join(have)))


def readiness(entries):
    """{'confirmed': n, 'unconfirmed': n, 'placing': n} over an area's entries."""
    conf = [e for e in entries.values() if r5.status(e) == "confirmed"]
    placing = [e for e in conf if any((e.get(k) or 0) != 0 for k in ("yea", "nay"))]
    return {"confirmed": len(conf), "unconfirmed": len(entries) - len(conf),
            "placing": len(placing)}


def placements(conn, cc, chamber, area, config_dir=None, today=None):
    """(rows, readiness): src/country5ca.build_rows over CONFIRMED readings only."""
    entries = area_entries(cc, chamber, area, config_dir)
    rows, _, _ = c5.build_rows(conn, cc, chamber, area, entries, today)
    return rows, readiness(entries)


def state_line(cc, chamber, area, ready):
    spec = c5.SPECS[cc]
    where = "{0}, {1}, {2}".format(spec.name, spec.chambers.get(chamber, chamber), area_name(area))
    if ready["placing"]:
        return "{0}: {1} confirmed reading(s) place members ({2} not yet confirmed).".format(
            where, ready["placing"], ready["unconfirmed"])
    return ("{0}: {1}. {2} vote reading(s) drafted, {3} confirmed that place anyone. No member "
            "is placed, so no target can be suggested; every member sits at 0 by design.".format(
                where, AWAITING.upper(), ready["unconfirmed"], ready["placing"]))


# --- open ----------------------------------------------------------------------------

def open_campaign(conn, cc, area, slug, label=None, chamber=None, petitions=None,
                  config_dir=None, base=None, today=None):
    """Snapshot the placements as the campaign's prediction. Returns the
    campaign dict (saved). Re-opening keeps targets, outcomes and petitions."""
    if cc not in c5.SPECS:
        raise ValueError("unknown country {0}".format(cc))
    if not SLUG.match(slug or ""):
        raise ValueError("slug: lower case letters, digits and hyphens, e.g. 'pl-abortion-2026'")
    if area in r5.excluded_areas(ROOT):
        raise ValueError("{0} is collated only, not a 5CA area".format(area_name(area)))
    chamber = resolve_chamber(cc, area, chamber, config_dir)
    today = today_iso(today)
    rows, ready = placements(conn, cc, chamber, area, config_dir, today)
    old = load_campaign(cc, slug, base) or {}
    if old and (old.get("area") != area or str(old.get("chamber")) != str(chamber)):
        raise ValueError("{0} is already a campaign on {1} in {2}; choose another slug".format(
            slug, area_name(old.get("area")), old.get("chamber")))
    snap = [{"member_id": r["person_id"], "decision_maker": r["decision_maker"],
             "party": r.get("party") or "", "column": r["column"],
             "conflict": bool(r.get("conflict")), "based_on": r.get("based_on") or "",
             "derived": "[DERIVED]" in r["decision_maker"]}
            for r in rows if r.get("sitting")]
    camp = {
        "cc": cc, "slug": slug, "area": area, "chamber": chamber,
        "label": label or old.get("label") or "{0}: {1}".format(c5.SPECS[cc].name, area_name(area)),
        "opened": old.get("opened") or today, "snapshot_on": today,
        "state": "placed" if ready["placing"] else AWAITING,
        "readings": ready, "snapshot": snap,
        "targets": old.get("targets") or [], "outcomes": old.get("outcomes") or [],
        "petitions": sorted(set((old.get("petitions") or []) + [str(p) for p in (petitions or [])])),
    }
    save_campaign(camp, base)
    return camp


def column_counts(snapshot):
    counts = {}
    for r in snapshot:
        counts[r["column"]] = counts.get(r["column"], 0) + 1
    return counts


# --- targets -----------------------------------------------------------------------

def suggested_targets(rows):
    """Rows a confirmed reading places in the soft middle, or with a mixed
    confirmed record. Rows at 0 never qualify (no confirmed evidence)."""
    out = []
    for r in rows:
        if not r.get("sitting") or r["column"] == "0":
            continue
        if r["column"] in SUGGEST or r.get("conflict"):
            why = {"+": "soft ally (+): secure the vote",
                   "-": "soft opponent (-): the one to move"}.get(r["column"], "")
            if r.get("conflict"):
                why = (why + "; " if why else "") + "MIXED confirmed record: read the acts"
            out.append(dict(r, why=why))
    return out


def candidates(conn, cc, chamber, area, config_dir=None):
    """Members by their vote record on the area's votes whose readings are
    NOT confirmed. Each is labelled NOT_A_TARGET and carries no direction:
    only how they voted, as the chamber records it."""
    spec = c5.SPECS[cc]
    entries = area_entries(cc, chamber, area, config_dir)
    pending = sorted((e for e in entries.values() if r5.status(e) != "confirmed"
                      and e.get("placeable") is not False),
                     key=lambda e: (str(e.get("dated") or ""), str(e["key"])))
    per = {}
    for e in pending:
        for p in c5.positions(conn, cc, str(e["key"])):
            side = spec.side(p["position"])
            rec = per.setdefault(str(p["member_id"]), {
                "member_id": str(p["member_id"]), "name": p["name"], "party": p["party"],
                "yea": 0, "nay": 0, "abstain": 0, "derived": False, "votes": []})
            rec["party"] = p["party"] or rec["party"]
            rec["derived"] = rec["derived"] or bool(p["derived"])
            if side in ("yea", "nay", "abstain"):
                rec[side] += 1
            rec["votes"].append("{0} {1} on {2} `{3}` ({4})".format(
                e.get("dated") or "?", p["position"] or "?", r5.clip(e.get("title"), 60), e["key"],
                AWAITING))
    out = []
    for rec in per.values():
        if not (rec["yea"] or rec["nay"] or rec["abstain"]):
            continue
        rec["label"] = NOT_A_TARGET
        out.append(rec)
    # By group, then by how often they voted: a Yes on one vote and a No on
    # another says nothing about direction until the readings are confirmed,
    # so the list is never ordered by "mixed" or any other implied stance.
    out.sort(key=lambda r: (str(r["party"] or "~"), -(r["yea"] + r["nay"] + r["abstain"]),
                            str(r["name"] or "")))
    return out, len(pending)


def roster(conn, cc, chamber=None):
    spec = c5.SPECS[cc]
    out = {}
    for m in c5._rows(conn, spec.roster_sql):
        if chamber and str(m.get("chamber") or chamber) not in (chamber, spec.chambers.get(chamber)):
            continue
        out[str(m["member_id"])] = m
    return out


def find_members(conn, cc, term, chamber=None):
    t = c5.fold(term)
    return [m for m in roster(conn, cc, chamber).values()
            if t in c5.fold(m.get("name")) or t == c5.fold(str(m["member_id"]))]


def add_targets(camp, conn, member_ids, by, reason=None, config_dir=None, today=None, base=None):
    """Add members as targets. Returns (added, refused[(id, why)])."""
    by = (by or "").strip()
    if not by:
        raise ValueError("--by NAME is required: choosing a target is a person's decision")
    cc, chamber, area = camp["cc"], camp["chamber"], camp["area"]
    rows, _ = placements(conn, cc, chamber, area, config_dir, today)
    placed = {r["person_id"]: r for r in rows}
    sugg = {r["person_id"] for r in suggested_targets(rows)}
    members = roster(conn, cc, chamber)
    have = {t["member_id"] for t in camp["targets"]}
    added, refused = [], []
    for mid in member_ids:
        mid = str(mid)
        if mid in have:
            refused.append((mid, "already a target"))
            continue
        m = members.get(mid)
        r = placed.get(mid)
        if m is None and r is None:
            refused.append((mid, "not on the {0} roster (find it with `members`)".format(chamber)))
            continue
        col = r["column"] if r else "0"
        if col == "0":
            if not reason:
                refused.append((mid, "no confirmed placement ({0}): add only with --reason, and it "
                                     "is stored as your choice, not a suggestion".format(AWAITING)))
                continue
            basis = "chosen by {0}, no confirmed stance ({1}): {2}".format(by, AWAITING, reason)
        elif mid in sugg:
            basis = "suggested from a confirmed placement ({0})".format(col)
        else:
            basis = "chosen by {0} at a confirmed placement of {1}{2}".format(
                by, col, ": " + reason if reason else "")
        t = {"member_id": mid, "name": (m or {}).get("name") or (r or {}).get("decision_maker"),
             "party": (m or {}).get("party") or (r or {}).get("party") or "",
             "column_when_added": col, "basis": basis, "added_by": by,
             "added_on": today_iso(today)}
        camp["targets"].append(t)
        have.add(mid)
        added.append(t)
    if added:
        save_campaign(camp, base)
    return added, refused


def drop_targets(camp, member_ids, base=None):
    want = {str(m) for m in member_ids}
    before = len(camp["targets"])
    camp["targets"] = [t for t in camp["targets"] if t["member_id"] not in want]
    if len(camp["targets"]) != before:
        save_campaign(camp, base)
    return before - len(camp["targets"])


# --- outcome --------------------------------------------------------------------------

def find_divisions(conn, cc, term, config_dir=None, limit=25):
    """[(division row, reading status)] whose wording, subject, key or bill
    refs contain the term, newest first."""
    spec = c5.SPECS[cc]
    divs, _, _ = c5.load(cc, config_dir)
    t = c5.fold(term)
    out = []
    for r in reversed(c5.divisions(conn, cc)):
        hay = " ".join(c5.fold(str(x)) for x in [r["key"], r.get("question"), r.get("subject")]
                       + list(spec.refs(r) or []) if x)
        if t in hay:
            e = divs.get(r["key"])
            out.append((r, reading_status(e)))
            if len(out) >= limit:
                break
    return out


def reading_status(e):
    if not e:
        return "no reading drafted (not watched or tier 1)"
    st = r5.status(e)
    if st == "confirmed":
        return "CONFIRMED by {0} on {1}".format(e.get("confirmed_by"), e.get("confirmed_on"))
    if st == "unplaceable" or (e.get("placeable") is False):
        return "procedural ({0})".format("confirmed" if e.get("status") == "confirmed" else AWAITING)
    if st == "unread":
        return "needs reading ({0})".format(AWAITING)
    return "draft ({0})".format(AWAITING)


def implied_side(e):
    """'yes' / 'no' from a CONFIRMED reading, else None."""
    if r5.status(e) != "confirmed":
        return None
    yea, nay = e.get("yea") or 0, e.get("nay") or 0
    if yea > nay:
        return "yes"
    if nay > yea:
        return "no"
    return None


def record_outcome(camp, conn, key, our_side, by=None, config_dir=None, today=None, base=None):
    """Nominate a division as (part of) the outcome. Returns the outcome
    dict; raises ValueError on a refusal."""
    if our_side not in ("yes", "no"):
        raise ValueError("--our-side must be yes or no: which way a member had to vote, as the "
                         "chamber records it, to be with us")
    cc = camp["cc"]
    spec = c5.SPECS[cc]
    row = next((r for r in c5.divisions(conn, cc) if r["key"] == str(key)), None)
    if row is None:
        raise ValueError("no division {0} in the {1} store (find it with `find`)".format(key, cc))
    if str(row.get("chamber")) != str(camp["chamber"]):
        raise ValueError("division {0} is in {1}, the campaign is in {2}".format(
            key, row.get("chamber"), camp["chamber"]))
    divs, _, _ = c5.load(cc, config_dir)
    e = divs.get(str(key))
    signed = implied_side(e)
    if signed and signed != our_side:
        raise ValueError("the CONFIRMED reading of {0} puts our side at {1} ({2}); you said {3}. "
                         "A confirmed reading is changed in config/{4}_stance.yaml, by a named "
                         "signer, not here".format(key, signed.upper(), spec.labels[0 if signed == "yes"
                                                                                    else 1],
                                                    our_side, cc))
    out = {"key": str(key), "date": row.get("date"), "title": r5.clip(row.get("question"), 200),
           "our_side": our_side, "label": spec.labels[0 if our_side == "yes" else 1],
           "reading": reading_status(e), "stated_by": (by or "").strip() or None,
           "basis": "matches the confirmed reading" if signed else
                    "stated by {0}; no confirmed reading for this vote".format(
                        (by or "").strip() or "the person who recorded it"),
           "recorded_on": today_iso(today)}
    camp["outcomes"] = [o for o in camp["outcomes"] if o["key"] != out["key"]] + [out]
    camp["outcomes"].sort(key=lambda o: (str(o.get("date") or ""), o["key"]))
    save_campaign(camp, base)
    return out


# --- score ----------------------------------------------------------------------------

def score(camp, conn):
    """Per-member outcome rows and the summary (the UK's evaluate.evaluate,
    by the store's own positions)."""
    cc = camp["cc"]
    spec = c5.SPECS[cc]
    targets = {t["member_id"] for t in camp["targets"]}
    if not camp["outcomes"]:
        return {"rows": [], "summary": {}, "targets": []}
    ballots, names = {}, {}
    for o in camp["outcomes"]:
        for p in c5.positions(conn, cc, o["key"]):
            mid = str(p["member_id"])
            names.setdefault(mid, (p["name"], p["party"]))
            side = spec.side(p["position"])
            ours = "yea" if o["our_side"] == "yes" else "nay"
            ballots.setdefault(mid, []).append({
                "key": o["key"], "position": p["position"], "side": side,
                "with_us": None if side not in ("yea", "nay") else side == ours,
                "derived": bool(p["derived"])})
    snap = {r["member_id"]: r for r in camp["snapshot"]}
    ids = list(snap) + [m for m in ballots if m not in snap]
    rows, s = [], {}

    def bump(k):
        s[k] = s.get(k, 0) + 1

    for mid in ids:
        r = snap.get(mid)
        cast = ballots.get(mid, [])
        directional = [c for c in cast if c["with_us"] is not None]
        if not cast:
            vote, align = "0", "no vote recorded"
        elif not directional:
            # An abstention is a recorded choice; absent, on mission, present
            # but not voting and the like are not, and are never counted as one.
            if any(c["side"] == "abstain" for c in cast):
                vote, align = "abstain", "abstained"
            else:
                vote, align = "0", "did not vote"
        else:
            sides = {c["side"] for c in directional}
            vote = ("Y" if sides == {"yea"} else "N" if sides == {"nay"} else "split")
            w = sum(1 for c in directional if c["with_us"])
            align = "with us" if w == len(directional) else ("against us" if w == 0 else "split")
        col = r["column"] if r else "-"
        group = ("ally" if col in ALLY else "opponent" if col in OPPONENT
                 else "not in snapshot" if r is None else "no position")
        held = (align == "with us" and group == "ally") or (align == "against us" and group == "opponent")
        surprise = None
        if group == "ally" and align == "against us":
            surprise = "placed as an ally, voted against us"
        elif group == "opponent" and align == "with us":
            surprise = "placed as an opponent, voted with us"
        derived = any(c["derived"] for c in cast) or bool(r and r.get("derived"))
        name = r["decision_maker"] if r else "{0} ({1})".format(*names.get(mid, (mid, "?")))
        rows.append({"member_id": mid, "decision_maker": name, "placement": col,
                     "vote": vote, "alignment": align, "group": group, "held": held,
                     "surprise": surprise, "target": mid in targets, "derived": derived,
                     "positions": "; ".join("{0}: {1}".format(c["key"], c["position"] or "?")
                                            for c in cast)})
        bump("total")
        bump("align_" + align.replace(" ", "_"))
        bump("{0}_{1}".format(group.replace(" ", "_"), align.replace(" ", "_")))
        if derived:
            bump("derived")
        if surprise:
            bump("surprises")
        if align in ("with us", "against us") and group in ("ally", "opponent"):
            bump("tested")
            if held:
                bump("held")
        if mid in targets:
            bump("target_" + align.replace(" ", "_"))
    s["accuracy"] = round(100.0 * s.get("held", 0) / s["tested"]) if s.get("tested") else None
    s["prediction"] = camp.get("state") != AWAITING and any(
        r["column"] != "0" for r in camp["snapshot"])
    s["circular"] = any(o.get("date") and o["date"] < camp["snapshot_on"] for o in camp["outcomes"])
    return {"rows": rows, "summary": s, "targets": [r for r in rows if r["target"]]}


def score_text(camp, result):
    spec = c5.SPECS[camp["cc"]]
    s = result["summary"]
    out = ["{0} -- {1}; {2}, area {3} ({4}); snapshot {5}, {6}".format(
        camp["slug"], camp["label"], spec.chambers.get(camp["chamber"], camp["chamber"]),
        camp["area"], area_name(camp["area"]), camp["snapshot_on"],
        "opened {0}".format(AWAITING) if camp.get("state") == AWAITING else "placements confirmed")]
    if not camp["outcomes"]:
        out.append("No outcome vote recorded yet; nothing to score.")
        return "\n".join(out)
    for o in camp["outcomes"]:
        out.append("  outcome: {0} `{1}` {2}; our side {3} ({4}); {5}".format(
            o.get("date"), o["key"], r5.clip(o["title"], 70), o["our_side"].upper(), o["label"],
            o["basis"]))
    out.append("")
    out.append("{0} members: {1} with us, {2} against, {3} abstained, {4} split, {5} did not "
               "vote (absent, on mission, present only), {6} no position recorded".format(
                   s.get("total", 0), s.get("align_with_us", 0), s.get("align_against_us", 0),
                   s.get("align_abstained", 0), s.get("align_split", 0),
                   s.get("align_did_not_vote", 0), s.get("align_no_vote_recorded", 0)))
    if s.get("derived"):
        out.append("  {0} of them carry a position DERIVED from their group's vote (X5), not their "
                   "own record.".format(s["derived"]))
    if not s.get("prediction"):
        out.append("No prediction to score: the snapshot was taken {0} (no confirmed reading "
                   "placed anyone). The counts above are real; re-open the campaign after sign-off "
                   "to keep a prediction for the next vote.".format(AWAITING))
    elif s.get("accuracy") is not None:
        out.append("Placement held for {0}% of the {1} members whose vote tested it.".format(
            s["accuracy"], s["tested"]))
        if s.get("circular"):
            out.append("  ^ NOT a prediction score: an outcome vote predates the snapshot, so it "
                       "was evidence for the placements. Treat it as a consistency check.")
    if s.get("prediction"):
        out.append("")
        out.append("By group:")
        for g in ("ally", "opponent", "no position"):
            k = g.replace(" ", "_")
            out.append("  {0:12} with us {1:4}  against {2:4}  abstained {3:4}  did not vote {4:4}"
                       .format(g, s.get(k + "_with_us", 0), s.get(k + "_against_us", 0),
                               s.get(k + "_abstained", 0),
                               s.get(k + "_did_not_vote", 0) + s.get(k + "_no_vote_recorded", 0)))
    if result["targets"]:
        out.append("")
        out.append("Targets ({0}): {1} with us, {2} against, {3} abstained, {4} did not vote".format(
            len(result["targets"]), s.get("target_with_us", 0), s.get("target_against_us", 0),
            s.get("target_abstained", 0),
            s.get("target_did_not_vote", 0) + s.get("target_no_vote_recorded", 0)))
        for r in result["targets"]:
            out.append("  {0:48} was {1:2}  {2}".format(r5.clip(r["decision_maker"], 48),
                                                        r["placement"], r["alignment"]))
    surprises = [r for r in result["rows"] if r["surprise"]]
    if surprises:
        out.append("")
        out.append("{0} worth a look:".format(len(surprises)))
        for r in surprises[:20]:
            out.append("  {0:48} {1}".format(r5.clip(r["decision_maker"], 48), r["surprise"]))
        if len(surprises) > 20:
            out.append("  ...and {0} more".format(len(surprises) - 20))
    return "\n".join(out)


def write_score_csv(camp, result, out_dir=None, today=None):
    path = os.path.join(out_dir or EVAL_DIR, "{0}-5ca-evaluate-{1}-{2}.csv".format(
        camp["cc"], camp["slug"], today_iso(today)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as h:
        w = csv.writer(h)
        w.writerow(["Decision-Maker", "Planned placement", "Target (Y/N)", "Vote", "Alignment",
                    "Positions", "Comments"])
        for r in result["rows"]:
            note = r["surprise"] or ""
            if r["derived"]:
                note = (note + "; " if note else "") + "DERIVED from the group vote (X5)"
            w.writerow([r["decision_maker"], r["placement"], "Y" if r["target"] else "N",
                        r["vote"], r["alignment"], r["positions"], note])
        if not result["summary"].get("prediction"):
            w.writerow(["Opened {0}: no member was placed, so the planned placement is 0 by "
                        "design, never a judgement.".format(AWAITING)])
    return path


# --- campaign performance (the petition side) -----------------------------------------

def export_path(cc, looker_dir=None):
    return os.path.join(looker_dir or LOOKER_DIR, "{0}_campaigns.tsv".format(cc))


EXPECTED_FILE = """Expected: {path}
  The same Looker export as data/looker/en_gb_campaigns.tsv
  (docs/campaign-benchmarks.md), pulled by hand through the Looker MCP:
    model   gbq_2_0_reports
    explore aa_downstream_report
    fields  program, bound, topic, start_date, total_signatures,
            new_members_count, otd_amount, md_amount, sent_emails
    filters program: "{prefix}%", series_email_number: "<=20",
            start_date: "after 2024/01/01"
  saved as a TSV with the header line
    program	bound	looker_topic	start_date	signatures	new_members	otd_eur	md_eur	sent_emails
  ('#' comment lines above it say when and how it was pulled). The list
  prefix {prefix} is a guess from the country code: check it in Looker first."""


def read_performance(cc, looker_dir=None):
    """[row dicts] with pid, list and name parsed, or None when no export."""
    path = export_path(cc, looker_dir)
    if not os.path.exists(path):
        return None
    import importlib
    import sys
    tools = os.path.join(ROOT, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    llc = importlib.import_module("load_looker_campaigns")
    out = []
    for r in llc.read_export(path):
        program = (r.get("program") or "").strip()
        if not program:
            continue
        m = llc._PROGRAM.match(program)
        lst, name = llc.parse_program(program)
        out.append(dict(r, program=program, list=lst, name=name,
                        pid=(m.group("pid") if m else "") or "",
                        signatures=llc._num(r.get("signatures")),
                        new_members=llc._num(r.get("new_members")),
                        otd_eur=llc._num(r.get("otd_eur"), float)))
    return out


def _areas_for(name):
    import importlib
    import sys
    tools = os.path.join(ROOT, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    return importlib.import_module("log_campaign_performance").areas_for(name or "")


def named_members(rows, members):
    """{member_id: [program]} where a roster member's first and last name
    both appear as words in a petition's name."""
    idx = []
    for mid, m in members.items():
        parts = [p for p in c5.fold(m.get("name")).replace(",", " ").split() if len(p) >= 3]
        if len(parts) >= 2:
            idx.append((mid, parts[0], parts[-1]))
    out = {}
    for r in rows:
        words = set(re.split(r"[^a-z0-9']+", c5.fold(r["name"])))
        for mid, first, last in idx:
            if first in words and last in words:
                out.setdefault(mid, []).append(r["program"])
    return out


def performance(cc, camp=None, conn=None, looker_dir=None):
    """(status, lines). status is 'no data' or 'joined'."""
    spec = c5.SPECS[cc]
    rows = read_performance(cc, looker_dir)
    if rows is None:
        return "no data", [
            "{0}: NO CAMPAIGN PERFORMANCE DATA YET. Petition numbers exist only for the UK "
            "today (data/looker/en_gb_campaigns.tsv, campaign_performance); nothing is "
            "estimated or borrowed from another country.".format(spec.name),
            EXPECTED_FILE.format(path=os.path.relpath(export_path(cc, looker_dir), ROOT)
                                 if export_path(cc, looker_dir).startswith(ROOT)
                                 else export_path(cc, looker_dir), prefix=LIST_PREFIX[cc])]
    lists = sorted({r["list"] for r in rows if r["list"]})
    lines = ["{0}: {1} program(s) in {2} (lists: {3}).".format(
        spec.name, len(rows), os.path.basename(export_path(cc, looker_dir)), ", ".join(lists) or "?")]
    if LIST_PREFIX[cc] not in lists:
        lines.append("  note: no program carries the expected prefix {0}; check the export's "
                     "filter.".format(LIST_PREFIX[cc]))
    if camp is not None:
        pids = set(camp.get("petitions") or [])
        linked = [r for r in rows if r["pid"] and r["pid"] in pids]
        if pids:
            lines.append("Linked petitions ({0} id(s) on the campaign, {1} found):".format(
                len(pids), len(linked)))
            for r in linked:
                lines.append("  {0} {1}: {2} signatures, {3} new members, OTD EUR {4}".format(
                    r["pid"], r5.clip(r["name"], 50), r["signatures"], r["new_members"],
                    r["otd_eur"]))
            missing = sorted(pids - {r["pid"] for r in linked})
            if missing:
                lines.append("  not in the export: {0}".format(", ".join(missing)))
        else:
            lines.append("No petition linked to this campaign (open it again with --petition ID).")
        area = camp["area"]
        mapped = [r for r in rows if area in _areas_for(r["name"])]
        unmapped = [r for r in rows if not _areas_for(r["name"])]
        sig = [r["signatures"] for r in mapped if r["signatures"] is not None]
        lines.append("On {0}: {1} program(s), {2} signatures in all{3}. {4} program(s) map to no "
                     "area (the keyword table is English; a slug in {5} may not match).".format(
                         area_name(area), len(mapped), sum(sig),
                         ", median {0}".format(sorted(sig)[len(sig) // 2]) if sig else "",
                         len(unmapped), spec.name))
        if conn is not None:
            named = named_members(rows, roster(conn, cc, camp["chamber"]))
            if named:
                lines.append("Members named in a petition ({0}):".format(len(named)))
                for mid, progs in sorted(named.items()):
                    lines.append("  {0}: {1}".format(mid, "; ".join(r5.clip(p, 60) for p in progs)))
    return "joined", lines
