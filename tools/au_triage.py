#!/usr/bin/env python3
"""The Australian judge: a 0-3 score and a why-line per Federal bill on our
ground, and per division whose OWN words matched.

    python3 tools/au_triage.py --dry-run                # count and cost, send nothing
    python3 tools/au_triage.py                          # the newest LIMIT unscored
    python3 tools/au_triage.py --db /tmp/au.db --dry-run

Built 9 October 2026 for the Australian edition (tools/au_monitor.py),
modelled on tools/us_triage.py. Same judge, model and rubric as Westminster,
the EU, Germany, Canada and the US (src/triage.py); only the FRAME differs.

SPEND NEEDS A YES. The repo rule (Christopher, 5 August 2026): any Anthropic
spend beyond the budgeted weekly UK passes is announced with an estimate
first; --dry-run prints it. The Australia weekly runs this step only when the
repository variable AU_JUDGE is 'on', which is how the yes is recorded. It is
not on.

WHAT IS JUDGED. au_bills of the current Parliament on our ground,
migration-only excluded (collated, never campaigned), newest stage first.
Divisions are judged ONLY where their own words matched (own_areas): one that
merely inherits its bill's areas takes the bill's score in the edition, so
judging it again would pay twice for one story. A bill is given by its TITLE
ONLY (aph.gov.au, where the explanatory memoranda are, refuses our
collectors), which the frame tells the judge.

SCORED ONCE, EVER. --rescore <key> puts one back on a human's say-so.
Spend lands in api_spend as 'au-triage'.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_store, db, drain, spend, triage  # noqa: E402

SLICE = 4
LIMIT = 800
BUDGET_S = 1800.0
HIDDEN_AREAS = (11,)
# Measured from the Canadian judge's spend (424 calls, 9 October 2026): per
# item about 690 input and 100 output tokens. Used for the dry run's estimate
# only; the real cost is what api_spend records.
TOKENS_IN_PER_ITEM = 690
TOKENS_OUT_PER_ITEM = 100

# THE AUSTRALIAN FRAME. The EU judge, told it served a UK monitor, scored a
# Hong Kong resolution 0 as "unrelated to CitizenGO's UK-focused campaign
# areas"; every jurisdiction since gets its own frame for that reason.
SYSTEM_PROMPT_AU = triage.SYSTEM_PROMPT.replace(
    "You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns",
    "You are the triage layer of CitizenGO's Australian Federal Parliament monitor, covering "
    "bills and divisions in the House of Representatives and the Senate. Never mark an item "
    "down for not being British: an Australian matter in one of these areas is fully in "
    "scope. Australian names to know: 'voluntary assisted dying' is assisted suicide and "
    "euthanasia, and the Territories' power to legislate for it is a federal question; the "
    "Sex Discrimination Act is where sex and gender identity are defined federally, so its "
    "amendments touch single-sex spaces; 'child abuse material' is the Criminal Code's name "
    "for child sexual abuse material; the eSafety Commissioner and the Online Safety Act "
    "govern online speech and the under-16 social media minimum age; 'vilification' is "
    "hate speech law; religious discrimination bills are freedom of religion. Much of "
    "Australia's ground on abortion, assisted dying and conversion practices is state law; "
    "a federal item still counts in full. A BILL is given by its TITLE ONLY, because the "
    "explanatory memoranda are not available to this monitor: score what the title shows "
    "and do not invent contents. A DIVISION is given by the debate's headings, the question "
    "put and the motion moved; 'negatived' and 'agreed to' are counts, not verdicts. "
    "CitizenGO campaigns", 1)
assert SYSTEM_PROMPT_AU != triage.SYSTEM_PROMPT

SOURCES = {"au_bills": "bill_id", "au_divisions": "division_key"}
PARLIAMENT = 48


def _ours(areas_json):
    areas = json.loads(areas_json or "[]")
    return areas if [a for a in areas if a not in HIDDEN_AREAS] else None


def pending(conn):
    """Unscored items on our ground, newest first, migration-only excluded."""
    au_store.ensure_schema(conn)
    dated = []
    for r in conn.execute("SELECT * FROM au_bills WHERE triage_score IS NULL AND parliament = ? "
                          "AND areas NOT IN ('[]', '[11]')", (PARLIAMENT,)):
        areas = _ours(r["areas"])
        if not areas:
            continue
        status = ("became an Act, assent {0}".format(r["assent_date"]) if r["act_id"] else
                  "{0} in the {1}, {2}".format(r["last_stage"], r["last_stage_chamber"],
                                               r["last_stage_date"]) if r["last_stage"] else
                  "named in the Hansard {0}".format(r["first_date"]))
        text = "Introduced in the {0}. Status: {1}. Title only; no explanatory memorandum.".format(
            "Senate" if r["origin"] == "senate" else "House of Representatives", status)
        dated.append((r["last_stage_date"] or r["first_date"] or "",
                      triage.TriageItem(id="au_bills:" + r["bill_id"],
                                        title="{0} {1}".format(r["bill_id"], r["title"] or ""),
                                        text=text, tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    for r in conn.execute("SELECT * FROM au_divisions WHERE triage_score IS NULL "
                          "AND own_areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["own_areas"])
        if not areas:
            continue
        title = "{0} division {1} ({2}): {3}".format(r["chamber"].title(), r["number"],
                                                      r["date"], r["minor_heading"] or "")
        text = " ".join("{0}. Question: {1} Motion: {2} Ayes {3}, noes {4}.".format(
            r["major_heading"] or "", r["question"] or "?", r["motion"] or "none recorded",
            r["ayes"], r["noes"]).split())
        dated.append((r["date"] or "",
                      triage.TriageItem(id="au_divisions:" + r["division_key"], title=title,
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
    """Re-queue one row: 'r7512' for a bill, or 'au_divisions:<key>'."""
    table, _, k = key.partition(":") if key.startswith("au_") else ("au_bills", "", key)
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
                    chunk, api_key=api_key, system=SYSTEM_PROMPT_AU, transport=transport,
                    usage_sink=lambda usage, model: spend.record(
                        conn, "au-triage", model, usage, dated=today))
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
        print("au-triage: {0} row(s) re-queued for {1}".format(rescore(conn, key), key))
    queued = pending(conn)
    items = queued[:args.limit]
    if args.dry_run:
        print("au-triage: {0} unscored item(s) on our ground; this run would judge {1} "
              "in about {2} call(s), roughly ${3:.2f}. Nothing sent.".format(
                  len(queued), len(items), (len(items) + SLICE - 1) // SLICE,
                  estimate_usd(len(items))))
        return 0
    if not items:
        print("au-triage: nothing unscored.")
        return 0
    if len(queued) > len(items):
        print("au-triage: {0} unscored; judging the newest {1} this run, the rest wait "
              "-- disclosed, not silent.".format(len(queued), len(items)))
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        path = os.path.join(ROOT, "config", "secrets.yaml")
        if os.path.exists(path):
            import yaml
            api_key = (yaml.safe_load(open(path)) or {}).get("anthropic_api_key")
    if not api_key:
        print("au-triage: {0} unscored and no ANTHROPIC_API_KEY; left unscored rather "
              "than stub-scored, because scores are written once ever.".format(len(items)))
        return 0
    scored, gaps = judge(conn, items, api_key, today, budget=drain.Budget(args.budget_seconds))
    for table in SOURCES:
        dist = dict(conn.execute("SELECT triage_score, COUNT(*) FROM {0} "
                                 "WHERE triage_score IS NOT NULL GROUP BY 1".format(table)).fetchall())
        print("  {0} scored so far: {1}".format(
            table, ", ".join("{0}: {1}".format(k, dist[k]) for k in sorted(dist)) or "none"))
    print("au-triage: {0} of {1} item(s) scored, {2} gap(s).".format(scored, len(items), gaps))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
