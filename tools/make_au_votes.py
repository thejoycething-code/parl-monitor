#!/usr/bin/env python3
"""Build "How did your MP or senator vote?" -- the Australian Federal
Parliament vote tracker and member profiles, one page.

    python3 tools/make_au_votes.py
    python3 tools/make_au_votes.py --db /tmp/au.db --out /tmp/au-votes.html

The US tracker (tools/make_us_votes.py) on the Federal Parliament: the
divisions on our ground with tallies, party splits and every member's Aye, No
or pair, filterable by chamber, party and electorate or state; and a profile
per member (#member/<person ID>) holding their record on our ground
(divisions, speeches, motions and notices) and their 5CA placement per area.
A pair is shown as a pair, with no side: Hansard does not publish one.

Data: src/au_profiles.py. Directions come ONLY from SIGNED readings in
config/au_stance.yaml: an unsigned division ships with no direction fields at
all and the page says its reading is awaiting sign-off. 5CA placements are
computed with tools/au_5ca.build_rows, which places nobody on a draft.

Reads the store and config; writes partner_site/au-votes.html and
docs/au-votes.html. Never writes the store; fetches nothing; offline, seconds.
Run by jobs/au-weekly.sh after the 5CA step.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_profiles, au_store, db, intel  # noqa: E402
from src import readings5ca as r5  # noqa: E402

TEMPLATE = os.path.join(ROOT, "templates", "au-votes.html")
OUT = [os.path.join(ROOT, "partner_site", "au-votes.html"),
       os.path.join(ROOT, "docs", "au-votes.html")]
STANCE_PATH = os.path.join(ROOT, "config", "au_stance.yaml")


def _au_5ca():
    spec = importlib.util.spec_from_file_location("au_5ca", os.path.join(ROOT, "tools", "au_5ca.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def placements(conn, entries, areas, today=None):
    """{person_id: {area: {column, based_on, chamber, capped, mixed}}} from
    SIGNED readings. tools/au_5ca.build_rows applies only signed entries; a
    row with no signed evidence is left out. Nothing signed: nothing to do."""
    if not r5.file_counts(entries)["confirmed"]:
        return {}
    fca = _au_5ca()
    out = {}
    for chamber in ("house", "senate"):
        for area in areas:
            rows, _divs, _latest = fca.build_rows(conn, area, chamber, entries, today=today)
            for row in rows:
                if row["based_on"] in ("no signed reading", "no evidence"):
                    continue
                out.setdefault(row["person_id"], {})[area] = {
                    "column": row["column"], "based_on": row["based_on"],
                    "chamber": chamber, "capped": row["capped"], "mixed": row["conflict"]}
    return out


def build_data(conn, stance_path=STANCE_PATH, today=None):
    entries = r5.load_stance(stance_path, "divisions")
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    excluded = r5.excluded_areas(ROOT)
    five_ca = sorted(a for a in names if a not in excluded)
    placed = placements(conn, entries, five_ca, today=today)
    data = au_profiles.build(conn, entries, names, placements=placed, today=today)
    data["five_ca_areas"] = five_ca
    return data


def render(data, template=TEMPLATE):
    with open(template, encoding="utf-8") as fh:
        page = fh.read()
    # </script> inside a string would close the page's script early.
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return page.replace("/*__DATA__*/{}", blob)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--stance", default=STANCE_PATH)
    ap.add_argument("--out", action="append", help="output path (repeatable); "
                    "default partner_site/ and docs/")
    args = ap.parse_args(argv)
    conn = au_store.ensure_schema(db.connect(args.db))
    data = build_data(conn, args.stance)
    page = render(data)
    for out in args.out or OUT:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(page)
        print("  -> {0} ({1:,} bytes)".format(out, len(page.encode("utf-8"))))
    rd = data["readings"]
    sitting = sum(1 for m in data["members"] if m["in_office"])
    by = {c: sum(1 for d in data["divisions"] if d["chamber"] == c) for c in ("house", "senate")}
    pairs = sum(d["pos"].count("P") for d in data["divisions"])
    print("au-votes: {0} members ({1} current), {2} divisions on our ground (House {3}, "
          "Senate {4}; {5} pairs shown as pairs); {6} signed, {7} awaiting sign-off; {8} "
          "members with speeches, motions or notices on our ground, {9} placed by signed "
          "readings.".format(
              len(data["members"]), sitting, len(data["divisions"]), by["house"], by["senate"],
              pairs, rd["divisions_signed"], rd["divisions_awaiting"], len(data["speeches"]),
              len(data["placements"])))
    if not rd["file"]["confirmed"]:
        print("NO SIGNED READINGS in config/au_stance.yaml: the page shows the record and "
              "labels nobody.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
