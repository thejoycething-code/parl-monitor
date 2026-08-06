"""The 5CA Evaluate phase: what the decision-makers actually did.

The Plan phase places every member on the gradient. The Evaluate phase records
the real vote against that placement -- the half of the Campaigns Brief that
almost never gets filled in, because reconciling 650 names against a division
list by hand is nobody's afternoon.

You cannot score a forecast you did not keep, so opening a campaign SNAPSHOTS
the placements as they stood that day (ca_predictions). Nominating a division
as the campaign's outcome then produces the scorecard.

`our_side` is stated explicitly per division and matters more than anything
else here: on the Terminally Ill Adults (End of Life) Bill, voting *No* is
CitizenGO's side, so a tool that assumed Aye-is-good would report every ally
as a defector. The sheet's own Y/N/0 stays literal -- Y voted Aye, N voted No,
0 no vote recorded -- and alignment is computed separately.

What this measures is correlation, never causation: that a member voted with
us, not that we moved them. The campaigner attributes; the tool counts.
"""

from __future__ import annotations

SCHEMA = """
CREATE TABLE IF NOT EXISTS ca_campaigns (
  slug TEXT PRIMARY KEY, area INTEGER, label TEXT, opened TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS ca_predictions (
  slug TEXT, member_id INTEGER, decision_maker TEXT, placement TEXT,
  n_events INTEGER, PRIMARY KEY (slug, member_id)
);
CREATE TABLE IF NOT EXISTS ca_outcomes (
  slug TEXT, ref_base TEXT, title TEXT, date TEXT, our_side TEXT,
  PRIMARY KEY (slug, ref_base)
);
"""

ALLY = ("++", "+")
OPPONENT = ("--", "-")


def ensure_tables(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def open_campaign(conn, slug, area, label, opened, rows, note=None):
    """Snapshot today's placements as the campaign's prediction.

    Re-opening the same slug replaces the snapshot: a campaign re-planned
    before any vote should be scored against what it actually predicted.
    """
    ensure_tables(conn)
    conn.execute("INSERT OR REPLACE INTO ca_campaigns (slug, area, label, opened, note) "
                 "VALUES (?, ?, ?, ?, ?)", (slug, area, label, opened, note))
    conn.execute("DELETE FROM ca_predictions WHERE slug = ?", (slug,))
    conn.executemany(
        "INSERT INTO ca_predictions (slug, member_id, decision_maker, placement, n_events) "
        "VALUES (?, ?, ?, ?, ?)",
        [(slug, r["member_id"], r["decision_maker"], r["column"], r["n_events"])
         for r in rows])
    conn.commit()
    return len(rows)


def record_outcome(conn, slug, ref_base, title, date, our_side):
    """Nominate a division as (part of) the campaign's outcome.

    our_side is 'aye' or 'no': which way a member had to vote to be with us.
    """
    if our_side not in ("aye", "no"):
        raise ValueError("our_side must be 'aye' or 'no', got {0!r}".format(our_side))
    ensure_tables(conn)
    conn.execute("INSERT OR REPLACE INTO ca_outcomes (slug, ref_base, title, date, our_side) "
                 "VALUES (?, ?, ?, ?, ?)", (slug, ref_base, title, date, our_side))
    conn.commit()


def _votes_for(conn, ref_base):
    """{member_id: 'aye'|'no'} for one division."""
    rows = conn.execute(
        "SELECT member_id, ref FROM mp_events WHERE kind = 'vote' AND ref IN (?, ?)",
        (ref_base + ":aye", ref_base + ":no")).fetchall()
    return {r["member_id"]: r["ref"].rsplit(":", 1)[1] for r in rows}


def evaluate(conn, slug):
    """Per-member outcomes plus the scorecard, or None if nothing to score."""
    ensure_tables(conn)
    campaign = conn.execute(
        "SELECT slug, area, label, opened FROM ca_campaigns WHERE slug = ?", (slug,)).fetchone()
    if campaign is None:
        return None
    outcomes = conn.execute(
        "SELECT ref_base, title, date, our_side FROM ca_outcomes WHERE slug = ? "
        "ORDER BY date", (slug,)).fetchall()
    predictions = conn.execute(
        "SELECT member_id, decision_maker, placement, n_events FROM ca_predictions "
        "WHERE slug = ? ORDER BY decision_maker", (slug,)).fetchall()
    if not outcomes or not predictions:
        return {"campaign": dict(campaign), "outcomes": [], "rows": [], "summary": {}}

    # A member's alignment across every nominated division: with us if they
    # voted our side in all of them, against if in none, split otherwise.
    ballots = {}
    for o in outcomes:
        for member_id, side in _votes_for(conn, o["ref_base"]).items():
            ballots.setdefault(member_id, []).append(
                (o["ref_base"], side, side == o["our_side"]))

    rows, summary = [], {}

    def bump(key):
        summary[key] = summary.get(key, 0) + 1

    for p in predictions:
        cast = ballots.get(p["member_id"], [])
        if not cast:
            vote, alignment = "0", "no vote recorded"
        else:
            sides = {c[1] for c in cast}
            vote = "Y" if sides == {"aye"} else ("N" if sides == {"no"} else "split")
            withs = sum(1 for c in cast if c[2])
            alignment = ("with us" if withs == len(cast)
                         else ("against us" if withs == 0 else "split"))
        placement = p["placement"]
        group = ("ally" if placement in ALLY
                 else ("opponent" if placement in OPPONENT else "no position"))
        held = (alignment == "with us" and group == "ally") or \
               (alignment == "against us" and group == "opponent")
        surprise = None
        if group == "ally" and alignment == "against us":
            surprise = "placed as an ally, voted against us"
        elif group == "opponent" and alignment == "with us":
            surprise = "placed as an opponent, voted with us"
        elif group == "no position" and alignment == "with us":
            surprise = "no prior record, voted with us"
        rows.append({
            "member_id": p["member_id"], "decision_maker": p["decision_maker"],
            "placement": placement, "vote": vote, "alignment": alignment,
            "group": group, "held": held, "surprise": surprise,
            "n_events": p["n_events"],
        })
        bump("total")
        bump("vote_" + vote)
        bump("{0}_{1}".format(group.replace(" ", "_"), alignment.replace(" ", "_")))
        if surprise:
            bump("surprises")
        if alignment in ("with us", "against us") and group != "no position":
            bump("placement_tested")
            if held:
                bump("placement_held")
        if alignment == "with us":
            bump("voted_with_us")
        elif alignment == "against us":
            bump("voted_against_us")

    tested = summary.get("placement_tested", 0)
    summary["accuracy"] = (round(100.0 * summary.get("placement_held", 0) / tested)
                           if tested else None)
    # A division that happened BEFORE the snapshot is part of the evidence the
    # placement was derived from, so scoring against it measures nothing: the
    # first real run of this scored 100%, which was circularity, not foresight.
    # The alignment counts stay valid; the accuracy figure does not.
    summary["circular"] = any(o["date"] and o["date"] < campaign["opened"]
                              for o in outcomes)
    return {"campaign": dict(campaign),
            "outcomes": [dict(o) for o in outcomes],
            "rows": rows, "summary": summary}
