#!/usr/bin/env python3
"""The Irish judge: a 0-3 score and a why-line per Oireachtas bill on our
ground, and per division whose OWN text (or the amendment moved) matched.

    python3 tools/ie_triage.py --dry-run                # count and cost, send nothing
    python3 tools/ie_triage.py                          # the newest LIMIT unscored
    python3 tools/ie_triage.py --limit 200 --budget-seconds 1200

Built 9 October 2026 for the Irish edition (tools/ie_monitor.py), modelled on
tools/us_triage.py. Same judge, model and rubric as Westminster, the EU,
Germany, Canada and the US (src/triage.py); only the FRAME differs, below.

SPEND NEEDS A YES. The repo rule (Christopher, 5 August 2026): any
Anthropic spend beyond the budgeted weekly UK passes is announced with an
estimate first; --dry-run prints it. The Ireland weekly runs this step only
when the repository variable IE_JUDGE is 'on', which is how the yes is
recorded. It is not on.

WHAT IS JUDGED. ie_bills on our ground, migration-only excluded (collated,
never campaigned). Newest first by last stage, so a live bill is never
queued behind a dead one. Divisions are judged ONLY where their own text or
their amendment matched (own_areas): a division that merely inherits its
bill's areas takes the bill's score in the edition, so judging it again
would pay twice for one story.

SCORED ONCE, EVER. --rescore <key> puts one back on a human's say-so.
Spend lands in api_spend as 'ie-triage'.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, spend, triage, ie_store  # noqa: E402

SLICE = 4
LIMIT = 200
BUDGET_S = 1200.0
HIDDEN_AREAS = (11,)
# Measured from the Canadian judge's spend (424 calls, 9 October 2026): per
# item about 690 input and 100 output tokens. Used for the dry run's estimate
# only; the real cost is what api_spend records.
TOKENS_IN_PER_ITEM = 690
TOKENS_OUT_PER_ITEM = 100

# THE IRISH FRAME. The EU judge, told it served a UK monitor, scored a Hong
# Kong resolution 0 as "unrelated to CitizenGO's UK-focused campaign areas";
# every jurisdiction since gets its own frame for that reason.
SYSTEM_PROMPT_IE = triage.SYSTEM_PROMPT.replace(
    "You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns",
    "You are the triage layer of CitizenGO's Ireland monitor, covering bills and divisions "
    "in the Oireachtas: Dáil Éireann, Seanad Éireann and their committees. Never mark an "
    "item down for not being British: an Irish matter in one of these areas is fully in "
    "scope. Irish names to know: the Health (Regulation of Termination of Pregnancy) Act "
    "2018 is the abortion law, and the 'three-day wait' and 'safe access zones' are "
    "abortion; 'Dying with Dignity' and 'voluntary assisted dying' are assisted suicide; "
    "'assisted human reproduction' (AHR) covers surrogacy, IVF and embryos; 'gender "
    "recognition' is self-identification of legal sex; relationships and sexuality "
    "education (RSE) and school patronage or ethos are parental rights and education; "
    "Coimisiún na Meán is the online safety and media regulator; 'hate offences' and "
    "'incitement to hatred' are free speech. A referendum bill ('an Act to amend the "
    "Constitution') is judged on what it would change. Private Members' bills rarely pass "
    "but show where parties stand; a Government 'timed amendment' delays a bill by months "
    "and often ends it. A BILL is given by its short and long titles; a DIVISION by its "
    "debate, its question and, for an amendment vote, the amendment as moved. CitizenGO "
    "campaigns", 1)
assert SYSTEM_PROMPT_IE != triage.SYSTEM_PROMPT

SOURCES = {"ie_bills": "bill_key", "ie_divisions": "division_key"}


def _ours(areas_json):
    areas = json.loads(areas_json or "[]")
    return areas if [a for a in areas if a not in HIDDEN_AREAS] else None


def pending(conn):
    """Unscored items on our ground, newest first, migration-only excluded."""
    ie_store.ensure_schema(conn)
    dated = []
    for r in conn.execute("SELECT * FROM ie_bills WHERE triage_score IS NULL "
                          "AND areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["areas"])
        if not areas:
            continue
        title = "Bill {0} of {1}: {2}".format(r["number"], r["year"], r["title"] or "")
        text = " ".join("Status: {0}; last stage {1} ({2}); {3}. Long title: {4}".format(
            r["status"] or "?", r["last_stage"] or "?", r["last_stage_house"] or "?",
            r["source"] or "?", r["long_title"] or "none").split())
        dated.append((r["last_stage_at"] or r["introduced"] or "",
                      triage.TriageItem(id="ie_bills:" + r["bill_key"], title=title,
                                        text=text[:1500], tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    for r in conn.execute("SELECT * FROM ie_divisions WHERE triage_score IS NULL "
                          "AND own_areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["own_areas"])
        if not areas:
            continue
        title = "{0} division {1} ({2}) {3}".format(
            r["committee"] or r["chamber"].title(), r["vote_id"], r["date"] or "?",
            r["debate_title"] or "")
        text = " ".join("{0} {1} Outcome: {2}, Tá {3}, Níl {4}.".format(
            r["subject"] or "", r["amendment_text"] or "", r["outcome"] or "?",
            r["ta"], r["nil"]).split())
        dated.append((r["date"] or "",
                      triage.TriageItem(id="ie_divisions:" + r["division_key"], title=title,
                                        text=text[:1500], tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    dated.sort(key=lambda d: (d[0], d[1].id), reverse=True)
    return [item for _, item in dated]


def estimate_usd(n, model=triage.TRIAGE_MODEL):
    rate = spend.RATES.get(model) or {"input": 0, "output": 0}
    return (n * TOKENS_IN_PER_ITEM * rate["input"] + n * TOKENS_OUT_PER_ITEM * rate["output"]) / 1e6


def apply(conn, results):
    n = 0
    for res in results:
        table, _, key = (res.id or "").partition(":")
        if res.score is None or table not in SOURCES:
            continue
        conn.execute("UPDATE {0} SET triage_score = ?, why_it_matters = ? WHERE {1} = ?".format(
            table, SOURCES[table]), (res.score, res.why_it_matters or None, key))
        n += 1
    conn.commit()
    return n


def rescore(conn, key):
    """Re-queue one row: '2026/10' for a bill, or 'ie_divisions:<key>'."""
    table, _, k = key.partition(":") if key.startswith("ie_") else ("ie_bills", "", key)
    if table not in SOURCES:
        return 0
    n = conn.execute("UPDATE {0} SET triage_score = NULL, why_it_matters = NULL "
                     "WHERE {1} = ?".format(table, SOURCES[table]), (k,)).rowcount
    conn.commit()
    return n


def judge(conn, items, api_key, today, log=print, budget=None, transport=None):
    """Score in slices of SLICE, halving a slice that fails twice. Returns (scored, gaps)."""
    gaps = [0]

    def score_chunk(chunk):
        for attempt in (1, 2):
            try:
                return triage.score_live(
                    chunk, api_key=api_key, system=SYSTEM_PROMPT_IE, transport=transport,
                    usage_sink=lambda usage, model: spend.record(
                        conn, "ie-triage", model, usage, dated=today))
            except Exception as exc:                        # noqa: BLE001
                log("  [gap] triage chunk of {0} attempt {1}: {2}".format(
                    len(chunk), attempt, str(exc)[:90]))
        if len(chunk) == 1:
            log("  [gap] one row still refuses; left for next run: {0}".format(chunk[0].id))
            gaps[0] += 1
            return []
        half = len(chunk) // 2
        return score_chunk(chunk[:half]) + score_chunk(chunk[half:])

    slices = [items[i:i + SLICE] for i in range(0, len(items), SLICE)]
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
    ap.add_argument("--rescore", nargs="+", metavar="KEY")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    today = datetime.date.today().isoformat()
    for key in args.rescore or []:
        print("ie-triage: {0} row(s) re-queued for {1}".format(rescore(conn, key), key))
    queued = pending(conn)
    items = queued[:args.limit]
    if args.dry_run:
        print("ie-triage: {0} unscored item(s) on our ground; this run would judge {1} "
              "in about {2} call(s), roughly ${3:.2f}. Nothing sent.".format(
                  len(queued), len(items), (len(items) + SLICE - 1) // SLICE,
                  estimate_usd(len(items))))
        return 0
    if not items:
        print("ie-triage: nothing unscored.")
        return 0
    if len(queued) > len(items):
        print("ie-triage: {0} unscored; judging the newest {1} this run, the rest wait "
              "-- disclosed, not silent.".format(len(queued), len(items)))
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        path = os.path.join(ROOT, "config", "secrets.yaml")
        if os.path.exists(path):
            import yaml
            api_key = (yaml.safe_load(open(path)) or {}).get("anthropic_api_key")
    if not api_key:
        print("ie-triage: {0} unscored and no ANTHROPIC_API_KEY; left unscored rather "
              "than stub-scored, because scores are written once ever.".format(len(items)))
        return 0
    scored, gaps = judge(conn, items, api_key, today, budget=drain.Budget(args.budget_seconds))
    for table in SOURCES:
        dist = dict(conn.execute("SELECT triage_score, COUNT(*) FROM {0} "
                                 "WHERE triage_score IS NOT NULL GROUP BY 1".format(table)).fetchall())
        print("  {0} scored so far: {1}".format(
            table, ", ".join("{0}: {1}".format(k, dist[k]) for k in sorted(dist)) or "none"))
    print("ie-triage: {0} of {1} item(s) scored, {2} gap(s).".format(scored, len(items), gaps))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
