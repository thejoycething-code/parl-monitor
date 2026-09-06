"""Apply a nation's verdict config to its record.

    python3 tools/devolved_score.py --nation wales        # report
    python3 tools/devolved_score.py --nation wales --apply
    python3 tools/devolved_score.py --nation ni --apply

The Holyrood scorer (tools/sp_score.py) generalised to the Senedd and the
Assembly, whose votes were collected but never judged: 58,698 Welsh and
2,722 NI member-votes sat in the store with no page and no verdict
(measured 2026-09-04).

signed_off gates the verdict exactly as it does at Westminster, in
Holyrood and in the EU: an unsigned division still writes its rows, so
the tracker can show HOW someone voted, with verdict NULL so it cannot
say what that meant. Nothing here reaches items or the Slack digest.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, devolved

# nation -> (config, votes table, key column, vote column, member column,
#            scored table)
NATIONS = {
    "wales": ("senedd_votes.yaml", "sd_votes", "division_key", "result",
              "member_id", "sd_scored"),
    "ni": ("nia_votes.yaml", "ni_votes", "doc_id", "vote",
           "person_id", "ni_scored"),
}

# Each chamber records its lobbies in its own words.
AYE = {"for", "aye", "yes", "content"}
NO = {"against", "no", "not content"}


def side_of(raw):
    v = (raw or "").strip().lower()
    if v in AYE:
        return "for"
    if v in NO:
        return "against"
    return None            # abstain, absent, not voting: never a verdict


def load(nation):
    import yaml
    path = os.path.join(ROOT, "config", NATIONS[nation][0])
    if not os.path.exists(path):
        return []
    return (yaml.safe_load(open(path, encoding="utf-8")) or {}).get(
        "divisions") or []


def score(conn, nation, apply_it=False, log=print):
    cfg, votes_t, keycol, votecol, memcol, scored_t = NATIONS[nation]
    # Wales votes under the Senedd's own member number; the page looks
    # verdicts up by publicwhip URI. Resolve here, through the SAME
    # bridge the page uses, or the verdict never reaches the card.
    index = devolved.roster(conn) if nation == "wales" else None
    unresolved = set()
    divisions = load(nation)
    if not divisions:
        log("{0}: no divisions in config/{1} -- nothing to score. The "
            "tracker will show votes without verdicts.".format(nation, cfg))
        return 0, 0
    written = signed = 0
    for d in divisions:
        if d.get("not_ours"):
            log("  {0}  {1}  struck as not ours; not scored".format(
                d.get("dated", "?"), (d.get("short") or d["key"])[:52]))
            continue
        rows = conn.execute(
            "SELECT * FROM {0} WHERE {1} = ?".format(votes_t, keycol),
            (str(d["key"]),)).fetchall()
        if apply_it:
            # Clear the division first. Rows are keyed (division_key,
            # person_id), so when a member's identity changes -- as it
            # did when Wales moved from the Senedd's integers to roster
            # ids -- an INSERT OR REPLACE leaves the OLD row sitting
            # there as a ghost vote under an id nothing reads.
            conn.execute("DELETE FROM {0} WHERE division_key = ?".format(
                scored_t), (str(d["key"]),))
        ours = d.get("our_side")
        is_signed = bool(d.get("signed_off")) and ours in ("for", "against")
        if is_signed:
            signed += 1
        for r in rows:
            person = str(r[memcol])
            if index is not None:
                got, missing = devolved.resolve([r["member_name"]], index)
                if missing:
                    unresolved.update(missing)
                    continue
                person = got[r["member_name"]]
            side = side_of(r[votecol])
            verdict = None
            if is_signed and side:
                verdict = "good" if side == ours else "bad"
            if apply_it:
                conn.execute(
                    "INSERT OR REPLACE INTO {0} (division_key, person_id, "
                    "vote, verdict) VALUES (?,?,?,?)".format(scored_t),
                    (str(d["key"]), person, r[votecol], verdict))
            written += 1
        log("  {0}  {1}  {2} vote(s){3}".format(
            d.get("dated", "?"), (d.get("short") or d["key"])[:52],
            len(rows),
            "" if is_signed else "   [UNSIGNED - no verdict published]"))
    if unresolved:
        log("  {0} voter name(s) are not in the roster and carry no "
            "verdict: {1}".format(len(unresolved),
                                  ", ".join(sorted(unresolved))))
    if apply_it:
        conn.commit()
    return written, signed


def main():
    nation = "wales"
    if "--nation" in sys.argv:
        nation = sys.argv[sys.argv.index("--nation") + 1]
    if nation not in NATIONS:
        print("unknown nation: {0} (wales|ni)".format(nation))
        return 1
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    apply_it = "--apply" in sys.argv
    written, signed = score(conn, nation, apply_it=apply_it)
    print("\n{0}: {1} vote row(s) {2}; {3} division(s) carry a signed "
          "verdict.".format(nation, written,
                            "written" if apply_it else "would be written",
                            signed))
    if not signed:
        print("No verdicts are signed, so the page shows how each member "
              "voted and says nothing about what it meant.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
