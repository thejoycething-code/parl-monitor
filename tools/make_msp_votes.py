#!/usr/bin/env python3
"""The public MSP votes page -> partner_site/msp-votes.html (and docs/).

    python3 tools/make_msp_votes.py

A SEPARATE PAGE, not an extension of the Westminster one, and the reason is
structural rather than cosmetic: an MSP is elected by CONSTITUENCY or by
REGION, and a Scottish postcode returns one constituency member and seven
regional ones. "Find your MP" has one answer; "find your MSP" has eight.
Bolting that onto a page built around a single member per postcode would
have made both worse.

WHAT IT SHOWS. Holyrood divided 218 times on the Assisted Dying for
Terminally Ill Adults (Scotland) Bill. Three of those are scored -- the
general principles, the financial resolution, and the vote on passing the
Bill, which was DEFEATED 57 to 69 in March 2026. The other 215 are Stage 3
amendment votes with no motion reference and no recorded result, so what
each decided cannot be established and they are not scored.

THE SWITCHERS. Twelve MSPs voted Yes to the general principles in May and
No to passing the Bill in March -- every one of the twelve moved that way,
none moved the other. That is the Bill's defeat, and the page says so on
each of their pages rather than leaving a reader to diff two lists.

Reads sp_scored (verdicts), sp_events (what they said), dv_post (their
posts) and sp_members. Writes nothing.
"""

from __future__ import annotations

import datetime
import html
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

CONFIG = os.path.join(ROOT, "config", "holyrood_votes.yaml")
TEMPLATE = os.path.join(ROOT, "templates", "msp-votes.html")
OUTPUTS = (os.path.join(ROOT, "partner_site", "msp-votes.html"),
           os.path.join(ROOT, "docs", "msp-votes.html"))

AREAS = {1: "Abortion", 2: "Assisted suicide",
         6: "Parental rights and education",
         7: "Free speech and civil liberties"}
# Holyrood records four states. Only two are a position; the page says so
# rather than reading silence as opposition.
POSITION = {"Yes": "for", "No": "against"}
RECORD_CAP = 3          # receipts shown per area before the roll
STAGE1, FINAL = "m7624", "m9165"


def load_config():
    import yaml
    with open(CONFIG, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("divisions") or []


def display_name(sortable, preferred):
    """"Briggs, Miles" -> "Miles Briggs"."""
    name = " ".join((sortable or "").split())
    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
        pref = " ".join((preferred or "").split())
        # A preferred name replaces the FIRST name only: "Mairi" for
        # "Màiri", not for the whole thing.
        given = pref if pref and pref.lower() != last.lower() else first
        name = "{0} {1}".format(given, last).strip()
    return name


def areas_of(raw):
    try:
        return [a for a in json.loads(raw or "[]") if a in AREAS]
    except ValueError:
        return []


def build(conn):
    divisions = load_config()
    by_key = {d["key"]: d for d in divisions}

    rows = conn.execute(
        "SELECT key, title, dated, vote_for, vote_against, result "
        "FROM sp_divisions WHERE key IN ({0})".format(
            ",".join("?" * len(divisions))), [d["key"] for d in divisions])
    counts = {r["key"]: r for r in rows}

    out_divs = []
    for d in divisions:
        row = counts.get(d["key"])
        if row is None:
            continue
        out_divs.append({
            # yaml parses an unquoted date into a datetime.date, which json
            # cannot serialise -- and the failure is at the very last step,
            # after every query has run.
            "key": d["key"], "short": d["short"], "dated": str(d["dated"]),
            "stage": d["stage"], "landmark": bool(d.get("landmark")),
            "motion": " ".join((d.get("motion") or "").split()),
            "context": " ".join((d.get("context") or "").split()),
            "for": row["vote_for"], "against": row["vote_against"],
            "result": row["result"] or "",
            "meaning_for": " ".join((d.get("meaning_for") or "").split()),
            "meaning_against": " ".join((d.get("meaning_against") or "").split()),
            # Withheld unless signed off, exactly as at Westminster.
            "ours": d["our_side"] if d.get("signed_off") else None,
        })
    out_divs.sort(key=lambda d: d["dated"])

    votes = {}
    for r in conn.execute("SELECT division_key, person_id, vote, verdict "
                          "FROM sp_scored"):
        votes.setdefault(str(r["person_id"]), {})[r["division_key"]] = {
            "v": r["vote"], "verdict": r["verdict"]}

    # "Member" and "Substitute Member" of a committee are the default state
    # for almost every MSP -- 2,744 of the 3,993 posts -- so a pill saying
    # "Member" distinguishes nobody and costs a line on every page. Offices
    # that mean something are kept.
    DULL = {"Member", "Substitute Member"}
    posts = {}
    for r in conn.execute(
            "SELECT person_id, kind, name, ended FROM dv_post "
            "WHERE nation = 'scotland' AND (ended IS NULL OR ended = '') "
            "ORDER BY kind, name"):
        if r["name"] in DULL:
            continue
        posts.setdefault(str(r["person_id"]), []).append(
            {"kind": r["kind"], "name": r["name"]})

    record = {}
    for r in conn.execute("SELECT person_id, dated, heading, areas, excerpt "
                          "FROM sp_events ORDER BY dated DESC"):
        pid = str(r["person_id"])
        for area in areas_of(r["areas"]):
            block = record.setdefault(pid, {}).setdefault(str(area),
                                                          {"n": 0, "items": []})
            block["n"] += 1
            if len(block["items"]) < RECORD_CAP:
                excerpt = " ".join((r["excerpt"] or "").split())
                block["items"].append({
                    "d": r["dated"], "t": (r["heading"] or "")[:110],
                    "q": excerpt[:400] or None})

    members = []
    for r in conn.execute(
            "SELECT person_id, name, preferred_name, party, constituency "
            "FROM sp_members WHERE is_current = 1 ORDER BY name"):
        pid = str(r["person_id"])
        mine = votes.get(pid, {})
        # THE SWITCH. Yes at Stage 1 and No on passing is not an
        # inconsistency to be caught out, it is the single most informative
        # thing on the page: twelve of them are why the Bill fell.
        s1 = (mine.get(STAGE1) or {}).get("v")
        fin = (mine.get(FINAL) or {}).get("v")
        switched = (s1 in POSITION and fin in POSITION and s1 != fin)
        # NOT A MEMBER THEN, which is not the same as not voting. The Bill
        # was decided in March 2026 and Scotland went to the polls in May:
        # 65 of the 129 sitting MSPs were not in the previous Parliament and
        # could not have voted on it. Telling them they did not vote is the
        # same falsehood the Westminster page told peers.
        #
        # The test is "cast nothing in ANY of the three": every one of the
        # 129 who sat then appears in at least one division, so silence
        # across all three means absence from the Parliament, not from the
        # chamber.
        was_there = any(mine.get(d["key"]) for d in out_divs)
        members.append({
            "id": pid,
            "there": was_there,
            "name": r["name"],
            # sp_members stores "Briggs, Miles" for sorting and "Miles" as
            # the preferred name -- neither is what to call someone. Flip
            # the sort key back into a name and keep the preferred form
            # where it differs from the first name.
            "listAs": display_name(r["name"], r["preferred_name"]),
            "party": r["party"] or "",
            "seat": r["constituency"] or "",
            "votes": mine,
            "posts": posts.get(pid, []),
            "record": record.get(pid, {}),
            "switched": [s1, fin] if switched else None,
        })
    return {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + " local",
        "areas": {str(k): v for k, v in AREAS.items()},
        "divisions": out_divs,
        "members": members,
    }


def main():
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    conn.row_factory = sqlite3.Row
    data = build(conn)

    with open(TEMPLATE, encoding="utf-8") as handle:
        page = handle.read()
    page = page.replace("/*DATA*/null",
                        json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    for path in OUTPUTS:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)

    scored = sum(1 for m in data["members"] if m["votes"])
    switched = sum(1 for m in data["members"] if m["switched"])
    with_record = sum(1 for m in data["members"] if m["record"])
    print("{0} MSPs; {1} with a scored vote, {2} with a record, "
          "{3} who switched".format(len(data["members"]), scored, with_record,
                                    switched))
    unsigned = [d["short"] for d in data["divisions"] if not d["ours"]]
    if unsigned:
        print("  NOT signed off, shown without a verdict: {0}".format(unsigned))
    for path in OUTPUTS:
        print("  -> {0}".format(path))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
