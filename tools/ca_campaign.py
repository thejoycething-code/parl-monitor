"""Open, resolve and score a 5CA campaign.

    python3 tools/ca_campaign.py open <area> <slug> [--label "..."]
    python3 tools/ca_campaign.py find <search term> [--house commons|lords]
    python3 tools/ca_campaign.py outcome <slug> <division-id> --our-side aye|no
    python3 tools/ca_campaign.py score <slug> [--csv]
    python3 tools/ca_campaign.py list

`open` snapshots today's placements as the campaign's prediction, because a
forecast you did not keep cannot be scored. `find` searches the ledger for the
division that settled it. `outcome` nominates that division and states which
way was OUR side. `score` reports what the decision-makers actually did.
"""

from __future__ import annotations

import csv
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, evaluate, intel, stance


def _conn():
    return db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))


def cmd_open(args):
    area = int(args[0])
    slug = args[1]
    label = _opt(args, "--label")
    conn = _conn()
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    if area in (cfg.get("excluded_from_5ca") or []):
        print("{0} is collated only, not a 5CA area".format(names.get(area, area)))
        return 1
    rows = stance.suggest_rows(conn, area, full_roster=True, overrides_cfg=cfg)
    n = evaluate.open_campaign(
        conn, slug, area, label or names.get(area, "area {0}".format(area)),
        datetime.date.today().isoformat(), rows)
    counts = {}
    for r in rows:
        counts[r["column"]] = counts.get(r["column"], 0) + 1
    print("opened '{0}' on {1}: {2} decision-makers snapshotted".format(
        slug, names.get(area, area), n))
    print("  " + "  ".join("{0} x{1}".format(c, counts[c])
                           for c in stance.COLUMNS if c in counts))
    print("\nWhen the vote happens: tools/ca_campaign.py find <term>, then\n"
          "  tools/ca_campaign.py outcome {0} <division-id> --our-side aye|no".format(slug))
    conn.close()
    return 0


def cmd_find(args):
    term = " ".join(a for a in args if not a.startswith("--")).lower()
    conn = _conn()
    rows = conn.execute(
        "SELECT ref, MIN(line) AS line, MIN(date) AS date, COUNT(*) n FROM mp_events "
        "WHERE kind = 'vote' AND LOWER(line) LIKE ? GROUP BY ref ORDER BY date DESC "
        "LIMIT 25", ("%" + term + "%",)).fetchall()
    if not rows:
        print("no divisions in the ledger matching {0!r}".format(term))
        return 1
    seen = set()
    for r in rows:
        base = r["ref"].rsplit(":", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        title = re.sub(r"^Voted (Aye|No): ", "", r["line"] or "")
        print("  {0}  {1}  {2}".format(base, r["date"], title[:82]))
    print("\nThe id is the whole 'div:c1798' part. Aye and No are counted together.")
    conn.close()
    return 0


def cmd_outcome(args):
    slug, ref_base = args[0], args[1]
    our_side = _opt(args, "--our-side")
    if our_side not in ("aye", "no"):
        print("--our-side must be aye or no: which way a member had to vote to "
              "be with us on this division")
        return 1
    conn = _conn()
    row = conn.execute(
        "SELECT MIN(line) AS line, MIN(date) AS date FROM mp_events "
        "WHERE ref LIKE ?", (ref_base + ":%",)).fetchone()
    if not row or not row["line"]:
        print("no ledger votes for {0}".format(ref_base))
        return 1
    title = re.sub(r"^Voted (Aye|No): ", "", row["line"])
    evaluate.record_outcome(conn, slug, ref_base, title, row["date"], our_side)
    print("recorded for '{0}': {1} ({2}), our side = {3}".format(
        slug, title[:70], row["date"], our_side.upper()))
    conn.close()
    return 0


def cmd_score(args):
    slug = args[0]
    conn = _conn()
    result = evaluate.evaluate(conn, slug)
    if result is None:
        print("no campaign called {0!r}; open one first".format(slug))
        return 1
    s, c = result["summary"], result["campaign"]
    print("{0} -- {1}, opened {2}".format(slug, c["label"], c["opened"]))
    if not result["outcomes"]:
        print("no outcome division recorded yet; nothing to score")
        return 0
    for o in result["outcomes"]:
        print("  outcome: {0} ({1}), our side {2}".format(
            o["title"][:66], o["date"], o["our_side"].upper()))
    print("\n{0} decision-makers: {1} voted with us, {2} against, {3} no vote recorded".format(
        s.get("total", 0), s.get("voted_with_us", 0), s.get("voted_against_us", 0),
        s.get("vote_0", 0)))
    if s.get("accuracy") is not None:
        print("placement held for {0}% of the {1} members whose vote tested it".format(
            s["accuracy"], s.get("placement_tested", 0)))
    if s.get("circular"):
        print("  ^ NOT a prediction score: this division predates the snapshot, so it\n"
              "    is part of the evidence the placements came from. The alignment\n"
              "    counts above are real; treat the percentage as a consistency check.")
    print("\nby group:")
    for group in ("ally", "opponent", "no position"):
        key = group.replace(" ", "_")
        print("  {0:12} with us {1:4}  against {2:4}  no vote {3:4}".format(
            group, s.get(key + "_with_us", 0), s.get(key + "_against_us", 0),
            sum(v for k, v in s.items()
                if k.startswith(key + "_no_vote"))))
    surprises = [r for r in result["rows"] if r["surprise"]]
    if surprises:
        print("\n{0} worth a look:".format(len(surprises)))
        for r in surprises[:20]:
            print("  {0:52} {1}".format(r["decision_maker"][:52], r["surprise"]))
        if len(surprises) > 20:
            print("  ...and {0} more".format(len(surprises) - 20))

    if "--csv" in args:
        out = os.path.join(ROOT, "data", "5ca",
                           "5ca-evaluate-{0}-{1}.csv".format(slug, datetime.date.today()))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="") as handle:
            w = csv.writer(handle)
            w.writerow(["Decision-Maker", "Planned placement", "Vote", "Alignment", "Comments"])
            for r in result["rows"]:
                w.writerow([r["decision_maker"], r["placement"], r["vote"],
                            r["alignment"], r["surprise"] or ""])
        print("\nEvaluate sheet: {0}".format(out))
    conn.close()
    return 0


def cmd_list(args):
    conn = _conn()
    evaluate.ensure_tables(conn)
    rows = conn.execute(
        "SELECT c.slug, c.label, c.opened, "
        "(SELECT COUNT(*) FROM ca_predictions p WHERE p.slug = c.slug) preds, "
        "(SELECT COUNT(*) FROM ca_outcomes o WHERE o.slug = c.slug) outs "
        "FROM ca_campaigns c ORDER BY c.opened DESC").fetchall()
    if not rows:
        print("no campaigns opened yet")
    for r in rows:
        print("  {0:22} {1:28} opened {2}  {3} predictions, {4} outcome(s)".format(
            r["slug"], (r["label"] or "")[:28], r["opened"], r["preds"], r["outs"]))
    conn.close()
    return 0


def _opt(args, flag):
    return args[args.index(flag) + 1] if flag in args else None


COMMANDS = {"open": cmd_open, "find": cmd_find, "outcome": cmd_outcome,
            "score": cmd_score, "list": cmd_list}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__.strip())
        return 1
    return COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
