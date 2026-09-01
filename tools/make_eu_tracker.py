"""Build "How did your MEP vote?" -- the EU vote tracker page.

    python3 tools/make_eu_tracker.py

The Westminster tracker's grammar on EP data: search by MEP name or
COUNTRY (the EP has no postcodes), a member card led by verdict chips,
every judgement gated by config/eu_divisions.yaml's signed_off flag.
An UNSIGNED division ships with NO verdict fields at all -- the page
cannot colour what was never signed, structurally -- and renders lobby
facts (FAVOR/AGAINST/ABSTAINED) in neutral dress. Divisions with no
recorded positions (electronic votes) never appear on member cards;
they are context, listed on the landing state only.

Group cohesion is computed per division at build time -- the EP analog
of the party split, and the anchor-check evidence for sign-offs.

Reads the store and config; writes partner_site/eu-votes.html and
docs/eu-votes.html. Never writes the store.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

TEMPLATE = os.path.join(ROOT, "templates", "eu-votes.html")
OUT = [os.path.join(ROOT, "partner_site", "eu-votes.html"),
       os.path.join(ROOT, "docs", "eu-votes.html")]


def load_config():
    import yaml
    path = os.path.join(ROOT, "config", "eu_divisions.yaml")
    if not os.path.exists(path):
        return {}
    return (yaml.safe_load(open(path, encoding="utf-8")) or {}).get(
        "divisions") or {}


def build_data(conn):
    cfg = load_config()
    meps = [{"id": r["person_id"], "name": r["name"],
             "country": r["country"], "group": r["group_label"]}
            for r in conn.execute(
                "SELECT * FROM eu_meps ORDER BY name").fetchall()]
    by_group = {}
    votes = {}
    for r in conn.execute("SELECT * FROM eu_votes").fetchall():
        votes.setdefault(r["person_id"], {})[r["vote_id"]] = {
            "favor": "F", "against": "A", "abstention": "AB"}[r["position"]]
    mep_group = {m["id"]: m["group"] for m in meps}
    divisions = []
    for r in conn.execute("SELECT * FROM eu_divisions ORDER BY date DESC"
                          ).fetchall():
        c = cfg.get(r["vote_id"]) or {}
        pos = conn.execute("SELECT person_id, position FROM eu_votes WHERE "
                           "vote_id = ?", (r["vote_id"],)).fetchall()
        cohesion = {}
        for p in pos:
            g = mep_group.get(p["person_id"]) or "Unknown"
            cohesion.setdefault(g, {"favor": 0, "against": 0,
                                    "abstention": 0})
            cohesion[g][p["position"]] += 1
        d = {
            "id": r["vote_id"], "date": r["date"], "label": r["label"],
            "short": c.get("short") or r["label"],
            "favor": r["favor"], "against": r["against"],
            "abstention": r["abstention"], "positions": len(pos),
            "why": (r["why_it_matters"]
                    if "why_it_matters" in r.keys() else None),
            "groups": sorted(
                ({"g": g, **v} for g, v in cohesion.items()),
                key=lambda x: -(x["favor"] + x["against"] + x["abstention"])),
        }
        # The gate: verdict fields exist in the page's data ONLY when
        # signed off. An unsigned meaning cannot leak into a chip because
        # it was never embedded.
        if c.get("signed_off") and c.get("our_side"):
            d["verdict"] = {"our_side": c["our_side"],
                            "meaning_favor": (c.get("meaning_favor") or "").strip(),
                            "meaning_against": (c.get("meaning_against") or "").strip()}
        divisions.append(d)
    return {"meps": meps, "divisions": divisions, "votes": votes,
            "built": datetime.date.today().isoformat()}


def main():
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    data = build_data(conn)
    with open(TEMPLATE, encoding="utf-8") as fh:
        page = fh.read().replace("/*__DATA__*/{}",
                                 json.dumps(data, ensure_ascii=False))
    for out in OUT:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(page)
        print("  -> {0}".format(out))
    signed = sum(1 for d in data["divisions"] if d.get("verdict"))
    print("eu-tracker: {0} MEPs, {1} divisions ({2} signed off), "
          "{3} vote records.".format(
              len(data["meps"]), len(data["divisions"]), signed,
              sum(len(v) for v in data["votes"].values())))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
