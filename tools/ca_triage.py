#!/usr/bin/env python3
"""The Canadian judge: a 0-3 score and a why-line per petition and per
Supreme Court judgment on our ground.

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

SUPREME COURT JUDGMENTS (2 October 2026). ca_judgments rows on our ground
(tools/ca_courts.py) join the queue under their own frame,
SYSTEM_PROMPT_CA_JUDGMENTS: the item is a judgment given by its catchwords and
the headnote passage that matched, and the Court's holding is judged, never
the parties' names. A tier-2 match on "coercion" in Trinity Western is
exactly what a judgement separates. Each slice is one source, so each call
carries the right frame. A judgment is context only: it never places anyone.
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

# THE COURT'S FRAME. The petitions frame says the items are petitions and
# that presenting one is not endorsing it; told that about a judgment, the
# judge would be judging the wrong thing.
SYSTEM_PROMPT_CA_JUDGMENTS = triage.SYSTEM_PROMPT.replace(
    "You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns",
    "You are the triage layer of CitizenGO's Canadian monitor, which also watches the "
    "Supreme Court of Canada. Never mark an item down for not being British: a Canadian "
    "matter in one of these areas is fully in scope. MAID (medical assistance in dying) is "
    "Canada's statutory name for assisted suicide and euthanasia. The items are JUDGMENTS "
    "of the Supreme Court of Canada, each given by its catchwords and the passage of its "
    "headnote that matched: judge what the Court decided and how far it moves the law in "
    "these areas, never the parties' names -- a criminal appeal that mentions an area in "
    "passing scores low. CitizenGO campaigns", 1)
assert SYSTEM_PROMPT_CA_JUDGMENTS != triage.SYSTEM_PROMPT

# Every source the judge reads: table -> (key column, frame). A ca_ table
# that is classified and carries triage_score belongs here.
SOURCES = {
    "ca_petitions": ("petition_id", SYSTEM_PROMPT_CA),
    "ca_judgments": ("judgment_id", SYSTEM_PROMPT_CA_JUDGMENTS),
}


def _ours(areas_json):
    areas = json.loads(areas_json or "[]")
    return areas if [a for a in areas if a not in HIDDEN_AREAS] else None


def _catchwords(headnote, cap=900):
    """The headnote's catchwords ("Constitutional law \u2014 Charter of Rights
    \u2014 ..."), every such paragraph: the Court's own summary of what the
    case is about. Carter has two, division of powers first."""
    lines = [l for l in (headnote or "").split("\n")
             if len(l) > 60 and l.count("\u2014") >= 2]
    return " ".join(lines)[:cap]


def pending(conn):
    """Unscored rows on our ground, newest first across sources,
    migration-only excluded."""
    ca_store.ensure_schema(conn)
    dated = []
    for r in conn.execute(
            "SELECT * FROM ca_petitions WHERE areas IS NOT NULL AND areas != '[]' "
            "AND triage_score IS NULL"):
        areas = _ours(r["areas"])
        if not areas:
            continue
        keywords = ", ".join(json.loads(r["keywords"] or "[]"))
        title = "{0} ({1}){2}".format(r["petition_id"], r["category"] or "?",
                                      ": " + keywords if keywords else "")
        text = " ".join((r["prayer"] or "").split())[:1500]
        dated.append((r["presented"] or r["opened"] or r["first_seen"] or "",
                      triage.TriageItem(
                          id="ca_petitions:" + r["petition_id"], title=title, text=text,
                          tier=r["tier"] or 2, issue_areas=areas, watchlist_hit=False)))
    for r in conn.execute(
            "SELECT * FROM ca_judgments WHERE areas IS NOT NULL AND areas != '[]' "
            "AND triage_score IS NULL"):
        areas = _ours(r["areas"])
        if not areas:
            continue
        subjects = ", ".join(json.loads(r["subjects"] or "[]"))
        title = "{0} {1}{2}".format(r["citation"] or r["judgment_id"], r["title"] or "",
                                    " [{0}]".format(subjects) if subjects else "")
        text = " ".join("{0}\n{1}".format(_catchwords(r["headnote"]), r["excerpt"] or "")
                        .split())[:1500]
        dated.append((r["date"] or r["first_seen"] or "",
                      triage.TriageItem(
                          id="ca_judgments:" + r["judgment_id"], title=title, text=text,
                          tier=r["tier"] or 2, issue_areas=areas, watchlist_hit=False)))
    dated.sort(key=lambda d: (d[0], d[1].id), reverse=True)
    return [item for _, item in dated]


def apply(conn, results):
    n = 0
    for res in results:
        table, _, key = (res.id or "").partition(":")
        if res.score is None or table not in SOURCES:
            continue
        conn.execute("UPDATE {0} SET triage_score = ?, why_it_matters = ? WHERE {1} = ?".format(
            table, SOURCES[table][0]), (res.score, res.why_it_matters or None, key))
        n += 1
    conn.commit()
    return n


def rescore(conn, pid):
    """Re-queue one row: a petition id as before, or 'ca_judgments:<id>'."""
    table, _, key = pid.partition(":") if pid.startswith("ca_") else ("ca_petitions", "", pid)
    if table not in SOURCES:
        return 0
    n = conn.execute("UPDATE {0} SET triage_score = NULL, why_it_matters = NULL "
                     "WHERE {1} = ?".format(table, SOURCES[table][0]), (key,)).rowcount
    conn.commit()
    return n


def judge(conn, items, api_key, today, log=print, budget=None, transport=None):
    """Score `items` in slices of SLICE, halving a slice that fails twice.
    Returns (scored, gaps)."""
    gaps = [0]

    def score_chunk(chunk):
        system = SOURCES[chunk[0].id.split(":", 1)[0]][1]
        for attempt in (1, 2):
            try:
                return triage.score_live(
                    chunk, api_key=api_key, system=system, transport=transport,
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

    # One source per slice, so each call carries its own frame; the order
    # within a source (newest first) is kept.
    slices = []
    for table in SOURCES:
        mine = [it for it in items if it.id.startswith(table + ":")]
        slices += [mine[i:i + SLICE] for i in range(0, len(mine), SLICE)]
    scored = 0
    for done, chunk in enumerate(slices):
        if budget is not None and budget.exhausted():
            log("  " + budget.disclose("triage slices", done))
            break
        scored += apply(conn, score_chunk(chunk))
    return scored, gaps[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--limit", type=int, default=LIMIT)
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--rescore", nargs="+", metavar="ID",
                    help="a petition id, or ca_judgments:<lexum id>")
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
        print("ca-triage: {0} unscored row(s) on our ground; this run would judge {1} "
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
    for table in SOURCES:
        dist = dict(conn.execute("SELECT triage_score, COUNT(*) FROM {0} "
                                 "WHERE triage_score IS NOT NULL GROUP BY 1".format(table)).fetchall())
        print("  {0} scored so far: {1}".format(
            table, ", ".join("{0}: {1}".format(k, dist[k]) for k in sorted(dist)) or "none"))
    print("ca-triage: {0} of {1} row(s) scored, {2} gap(s).".format(scored, len(items), gaps))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
