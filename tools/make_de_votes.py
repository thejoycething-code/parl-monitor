#!/usr/bin/env python3
"""Build "Wie hat mein MdB abgestimmt?" -- the German vote page.

    python3 tools/make_de_votes.py                                  # partner_site/de-votes.html
    python3 tools/make_de_votes.py --db /tmp/s.db --out /tmp/de-votes.html

The EU tracker's grammar (tools/make_eu_tracker.py) on Bundestag data: the
namentliche Abstimmungen on our ground, each with its Fraktion split, and a
card per SITTING member of the 21st Bundestag with how they voted, including
in earlier Bundestag terms. Search by name, Fraktion or Wahlkreis.

DIRECTIONS ONLY FROM SIGNED READINGS. Which lobby is ours is a human
judgement written in config/de_stance.yaml -- the same lines tools/de_5ca.py
applies. A division's `readings` carry ja/nein values ONLY when the reading
is confirmed (no `draft: true`, placeable); a draft, an unread division and
an unplaceable one ship with no values at all, so the page cannot colour what
was never signed, structurally. A confirmed reading may value one lobby only
(an AfD-only motion's Nein tells no member apart): the other lobby shows the
vote, no direction.

WHICH DIVISIONS: Bundestag (never Landtag) divisions tagged with an area
other than migration (collated, never campaigned, as on the issue pages),
that either have a reading in config/de_stance.yaml or reached triage score
2 (unscored ones are shown too, as on the EU page).

WHO VOTED: a vote cast under an earlier mandate attaches to the sitting
member through tools/de_5ca.py's own bridge (name and party family), so the
page and the 5CA sheet always agree on who did what.

Reads the store and config; writes one HTML file. Never writes the store and
fetches nothing. Runs offline in the Germany weekly after the 5CA sheets;
the page reaches the partner site the way eu-votes.html does: committed by
the weekly, shipped by the Monday Deploy tracker (behind the passphrase).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, intel  # noqa: E402
import de_5ca  # noqa: E402

TEMPLATE = os.path.join(ROOT, "templates", "de-votes.html")
OUT = os.path.join(ROOT, "partner_site", "de-votes.html")
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
HIDDEN = (11,)            # migration: collated, never campaigned (src/de_issuepages.py)
MIN_SCORE = 2
TERMS = {"67": "16th Bundestag, 2005-2009", "83": "17th Bundestag, 2009-2013",
         "97": "18th Bundestag, 2013-2017", "111": "19th Bundestag, 2017-2021",
         "132": "20th Bundestag, 2021-2025", "161": "21st Bundestag, 2025-2029"}
POS = {"yes": "J", "no": "N", "abstain": "E", "no_show": "X"}


def _party(text):
    return (text or "").replace("\xad", "").strip() or "?"


def _areas(row):
    try:
        return [int(a) for a in json.loads(row["areas"] or "[]")]
    except (TypeError, ValueError):
        return []


def reading_of(entry, names):
    """What the page may say about one reading. Values only when signed."""
    st = de_5ca.status(entry)
    out = {"area": entry.get("area"), "area_name": names.get(entry.get("area"), ""),
           "status": st}
    if st == "confirmed":
        out.update({"ja": entry.get("ja"), "nein": entry.get("nein"),
                    "why_ja": entry.get("why_ja") or "",
                    "why_nein": entry.get("why_nein") or "",
                    "free_vote": bool(entry.get("free_vote"))})
    elif st == "unplaceable":
        out["reason"] = entry.get("reason") or ""
    return out


def build_data(conn, stance_cfg, names, today=None):
    sitting = de_5ca.roster(conn)
    if sitting is None:
        return None
    bridge = de_5ca.Bridge(sitting)
    members_all = {r["person_id"]: r for r in conn.execute(
        "SELECT person_id, name, party, legislature FROM de_members")}

    def resolve(pid):
        if pid in sitting:
            return pid
        m = members_all.get(pid)
        return bridge.find(m["name"], m["party"]) if m else None

    by_key = {}
    for e in stance_cfg.get("divisions") or []:
        by_key.setdefault(str(e["key"]), []).append(e)

    divisions, votes = [], {}
    counts = {"signed": 0, "unplaceable": 0, "draft": 0, "unread": 0}
    for r in conn.execute("SELECT * FROM de_divisions WHERE parliament = '5' "
                          "ORDER BY date DESC, vote_id DESC"):
        areas = [a for a in _areas(r) if a not in HIDDEN]
        entries = [e for e in by_key.get(r["vote_id"], []) if e.get("area") not in HIDDEN]
        if not areas and not entries:
            continue
        score = r["triage_score"]
        if not entries and score is not None and score < MIN_SCORE:
            continue
        readings = [reading_of(e, names) for e in entries]
        split = {}
        for v in conn.execute("SELECT person_id, position FROM de_votes WHERE vote_id = ?",
                              (r["vote_id"],)):
            m = members_all.get(v["person_id"])
            party = _party(m["party"] if m else None)
            t = split.setdefault(party, {"J": 0, "N": 0, "E": 0, "X": 0})
            code = POS.get(v["position"], "X")
            t[code] += 1
            pid = resolve(v["person_id"])
            if pid is not None:
                votes.setdefault(pid, {})[r["vote_id"]] = code
        signed = [x for x in readings if x["status"] == "confirmed"]
        if signed:
            counts["signed"] += 1
        elif any(x["status"] == "unplaceable" for x in readings):
            counts["unplaceable"] += 1
        elif any(x["status"] == "draft" for x in readings):
            counts["draft"] += 1
        else:
            counts["unread"] += 1
        title = next((e.get("title") for e in entries if e.get("title")), None)
        divisions.append({
            "id": r["vote_id"], "date": r["date"], "label": r["label"] or "",
            "title": title or r["label"] or "",
            "term": TERMS.get(r["legislature"], "Bundestag"),
            "current": r["legislature"] == de_5ca.CURRENT,
            "yes": r["yes"], "no": r["no"], "abstain": r["abstain"], "absent": r["absent"],
            "accepted": r["accepted"], "doc": r["document_url"] or "",
            "why": r["why_it_matters"] or "",
            "areas": sorted({names.get(a, str(a)) for a in areas}
                            | {x["area_name"] for x in readings if x["area_name"]}),
            "readings": readings,
            "split": sorted(({"p": p, **t} for p, t in split.items()),
                            key=lambda x: -(x["J"] + x["N"] + x["E"] + x["X"])),
        })
    members = []
    for pid, r in sitting.items():
        seat = de_5ca.seat_of(r)
        members.append({"id": pid, "name": r["name"], "party": _party(r["party"]),
                        "seat": seat, "constituency": r["mandate_won"] == "constituency",
                        "profile": r["profile_url"] or ""})
    members.sort(key=lambda m: m["name"])
    return {"members": members, "divisions": divisions,
            "votes": {pid: v for pid, v in votes.items() if pid in sitting},
            "counts": counts,
            "built": (today or datetime.date.today()).isoformat()}


def render(data, template=TEMPLATE):
    with open(template, encoding="utf-8") as fh:
        page = fh.read()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return page.replace("/*__DATA__*/{}", blob)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--stance", default=de_5ca.STANCE_PATH)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    conn = db.connect(args.db)
    data = build_data(conn, de_5ca.load_yaml(args.stance), intel.area_names(TAXONOMY))
    conn.close()
    if data is None:
        print("de-votes: the Bundestag roster has never been checked -- run "
              "tools/de_profiles.py --roster first. Nothing written.")
        return 1
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(data))
    c = data["counts"]
    print("de-votes: {0} sitting MdBs, {1} divisions ({2} with a signed reading, {3} "
          "never-placeable, {4} draft, {5} unread), {6} member votes -> {7}".format(
              len(data["members"]), len(data["divisions"]), c["signed"], c["unplaceable"],
              c["draft"], c["unread"], sum(len(v) for v in data["votes"].values()),
              os.path.relpath(args.out, ROOT) if args.out.startswith(ROOT) else args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
