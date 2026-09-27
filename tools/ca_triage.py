#!/usr/bin/env python3
"""The judge for Canadian petitions: a 0-3 score and a why-line per petition.

    python3 tools/ca_triage.py                       # the newest LIMIT unscored
    python3 tools/ca_triage.py --limit 2000 --budget-seconds 2400
    python3 tools/ca_triage.py --dry-run             # count and cost, send nothing

Built 27 September 2026, when the backfill to 2020 had stored ~5,800
presented petitions and the taxonomy had put ~1,600 of them on our ground --
including tier-2 noise ("misinformation" on a US-tariffs petition, "places of
worship" on one about IRGC agents) that only a judgement separates. Same
judge, model and rubric as Westminster, the EU and Germany (src/triage.py);
only the FRAME differs, below.

WHAT IS JUDGED. ca_petitions rows on our ground with no score yet, EXCLUDING
rows whose only area is migration: migration is collated, never campaigned
(src/partner.py HIDDEN_AREAS), so paying to rank it buys nothing. Newest first
by the petition's own date, so this week's are never queued behind 2020's.

SCORED ONCE, EVER. A row keeps its score; --rescore <petition_id> puts one
back in the queue on a human's say-so.

A CAP AND A CLOCK, as tools/de_triage.py has: at most LIMIT rows a run inside
BUDGET_S, because a job killed by its timeout never publishes the store. The
rest waits, and the log says how many.

Spend lands in api_spend as 'ca-triage'.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, spend, triage  # noqa: E402

SLICE = 4
LIMIT = 600
BUDGET_S = 1200.0
HIDDEN_AREAS = (11,)

# THE CANADIAN FRAME. The EU judge, told it served a UK monitor, scored a
# Hong Kong resolution 0 as "unrelated to CitizenGO's UK-focused campaign
# areas"; the German frame exists for the same reason. Canada adds two
# things: its statutory name for assisted suicide, which the base prompt does
# not use, and what a petition IS -- the House's own rule that presenting one
# does not mean the member endorses it, so the petition's prayer is judged,
# not the member who carried it.
SYSTEM_PROMPT_CA = triage.SYSTEM_PROMPT.replace(
    "You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns",
    "You are the triage layer of CitizenGO's Canadian parliamentary monitor, covering the "
    "House of Commons and Senate of Canada. Never mark an item down for not being British: "
    "a Canadian matter in one of these areas is fully in scope. MAID (medical assistance in "
    "dying) is Canada's statutory name for assisted suicide and euthanasia. The items are "
    "PETITIONS presented to the House of Commons: judge the petition's own request, never "
    "the member who presented it -- presenting a petition does not mean endorsing it. "
    "CitizenGO campaigns", 1)
assert SYSTEM_PROMPT_CA != triage.SYSTEM_PROMPT


def pending(conn):
    """Unscored petitions on our ground, newest first, migration-only excluded."""
    ca_store.ensure_schema(conn)
    out = []
    for r in conn.execute(
            "SELECT * FROM ca_petitions WHERE areas IS NOT NULL AND areas != '[]' "
            "AND triage_score IS NULL "
            "ORDER BY COALESCE(presented, opened, first_seen) DESC, petition_id DESC"):
        areas = json.loads(r["areas"] or "[]")
        if not [a for a in areas if a not in HIDDEN_AREAS]:
            continue
        keywords = ", ".join(json.loads(r["keywords"] or "[]"))
        title = "{0} ({1}){2}".format(r["petition_id"], r["category"] or "?",
                                      ": " + keywords if keywords else "")
        text = " ".join((r["prayer"] or "").split())[:1500]
        out.append(triage.TriageItem(
            id="ca_petitions:" + r["petition_id"], title=title, text=text,
            tier=r["tier"] or 2, issue_areas=areas, watchlist_hit=False))
    return out


def apply(conn, results):
    n = 0
    for res in results:
        if res.score is None or not (res.id or "").startswith("ca_petitions:"):
            continue
        conn.execute("UPDATE ca_petitions SET triage_score = ?, why_it_matters = ? "
                     "WHERE petition_id = ?",
                     (res.score, res.why_it_matters or None, res.id.split(":", 1)[1]))
        n += 1
    conn.commit()
    return n


def rescore(conn, pid):
    n = conn.execute("UPDATE ca_petitions SET triage_score = NULL, why_it_matters = NULL "
                     "WHERE petition_id = ?", (pid,)).rowcount
    conn.commit()
    return n


def judge(conn, items, api_key, today, log=print, budget=None, transport=None):
    """Score `items` in slices of SLICE, halving a slice that fails twice.
    Returns (scored, gaps)."""
    gaps = [0]

    def score_chunk(chunk):
        for attempt in (1, 2):
            try:
                return triage.score_live(
                    chunk, api_key=api_key, system=SYSTEM_PROMPT_CA, transport=transport,
                    usage_sink=lambda usage, model: spend.record(
                        conn, "ca-triage", model, usage, dated=today))
            except Exception as exc:                        # noqa: BLE001
                log("  [gap] triage chunk of {0} attempt {1}: {2}".format(
                    len(chunk), attempt, str(exc)[:90]))
        if len(chunk) == 1:
            log("  [gap] one row still refuses; left for next run: {0}".format(chunk[0].id))
            gaps[0] += 1
            return []
        half = len(chunk) // 2
        return score_chunk(chunk[:half]) + score_chunk(chunk[half:])

    scored = 0
    for start in range(0, len(items), SLICE):
        if budget is not None and budget.exhausted():
            log("  " + budget.disclose("triage slices", start // SLICE))
            break
        scored += apply(conn, score_chunk(items[start:start + SLICE]))
    return scored, gaps[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--limit", type=int, default=LIMIT)
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--rescore", nargs="+", metavar="PETITION_ID")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    today = datetime.date.today().isoformat()
    for pid in args.rescore or []:
        print("ca-triage: {0} row(s) re-queued for {1}".format(rescore(conn, pid), pid))
    queued = pending(conn)
    items = queued[:args.limit]
    calls = (len(items) + SLICE - 1) // SLICE
    if args.dry_run:
        print("ca-triage: {0} unscored petition(s) on our ground; this run would judge {1} "
              "in about {2} call(s). Nothing sent.".format(len(queued), len(items), calls))
        return 0
    if not items:
        print("ca-triage: nothing unscored.")
        return 0
    if len(queued) > len(items):
        print("ca-triage: {0} unscored; judging the newest {1} this run, the rest wait "
              "-- disclosed, not silent.".format(len(queued), len(items)))
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        path = os.path.join(ROOT, "config", "secrets.yaml")
        if os.path.exists(path):
            import yaml
            api_key = (yaml.safe_load(open(path)) or {}).get("anthropic_api_key")
    if not api_key:
        print("ca-triage: {0} unscored and no ANTHROPIC_API_KEY; left unscored rather "
              "than stub-scored, because scores are written once ever.".format(len(items)))
        return 0
    scored, gaps = judge(conn, items, api_key, today, budget=drain.Budget(args.budget_seconds))
    dist = dict(conn.execute("SELECT triage_score, COUNT(*) FROM ca_petitions "
                             "WHERE triage_score IS NOT NULL GROUP BY 1").fetchall())
    print("ca-triage: {0} of {1} petition(s) scored, {2} gap(s). All scored so far: {3}".format(
        scored, len(items), gaps, ", ".join("{0}: {1}".format(k, dist[k]) for k in sorted(dist))))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
