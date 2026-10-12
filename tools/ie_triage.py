#!/usr/bin/env python3
"""The Irish judge: a 0-3 score and a why-line per Oireachtas bill on our
ground, and per division whose OWN text (or the amendment moved) matched.

    python3 tools/ie_triage.py --dry-run                # count and cost, send nothing
    python3 tools/ie_triage.py --queue-out /tmp/q.md --limit 25   # for a session
    python3 tools/ie_triage.py --queue-in /tmp/q.md               # apply its scores
    python3 tools/ie_triage.py                          # the newest LIMIT unscored
    python3 tools/ie_triage.py --limit 200 --budget-seconds 1200

Built 9 October 2026 for the Irish edition (tools/ie_monitor.py), modelled on
tools/us_triage.py. Same judge, model and rubric as Westminster, the EU,
Germany, Canada and the US (src/triage.py); only the FRAME differs, below.

SPEND NEEDS A YES. The repo rule (Christopher, 5 August 2026): any
Anthropic spend beyond the budgeted weekly UK passes is announced with an
estimate first; --dry-run prints it. The Ireland weekly runs this step only
when the repository variable IE_JUDGE is 'on', which is how the yes is
recorded. It was on from 9 October 2026 (Christopher's yes) until the
same day's move to the free session judge below; it is off.

WHAT IS JUDGED. ie_bills on our ground, migration-only excluded (collated,
never campaigned). Newest first by last stage, so a live bill is never
queued behind a dead one. Divisions are judged ONLY where their own text or
their amendment matched (own_areas): a division that merely inherits its
bill's areas takes the bill's score in the edition, so judging it again
would pay twice for one story. Since phase 2 (9 October 2026), questions on
our ground (ie_questions) and speeches whose member's own words matched
(ie_speeches, areas_from 'own') are judged too, newest first with the rest:
a backfill's old questions queue behind this week's.

SCORED ONCE, EVER. --rescore <key> puts one back on a human's say-so.
Spend lands in api_spend as 'ie-triage'.

THE SESSION JUDGE, FREE (9 October 2026, Christopher: "Switch US, Ireland
and Australia scoring to the free route"; the DEFAULT route since).
--queue-out writes the newest --limit pending items, with the Irish frame
and the very text the API judge would read, to a file in
src/session_queue.py's format, under this judge's own marker line. A Claude
Code session on the Mac Mini, on the work subscription, fills in SCORE and
WHY (jobs/ie-session-judge.sh through tools/session_judge.sh). --queue-in
reads it back STRICTLY, item by item (one digit 0-3 and a why-line, or
refused with its reason; another judge's file is refused whole), and
applies the scores through apply() exactly as API scores are applied; the
rows carry no model column, so session_scores notes each one as model
'claude-code-session'. Once ever still holds: a row scored meanwhile is not
overwritten. Neither flag needs ANTHROPIC_API_KEY or spends anything;
IE_JUDGE (the paid API path) stays the alternative, and off.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, spend, triage, ie_store, session_queue  # noqa: E402

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
    "debate, its question and, for an amendment vote, the amendment as moved; a "
    "PARLIAMENTARY QUESTION by what the member asked (one line of the Minister's answer is "
    "context, not the member's position); a SPEECH by its debate and an excerpt of the "
    "member's own words. CitizenGO "
    "campaigns", 1)
assert SYSTEM_PROMPT_IE != triage.SYSTEM_PROMPT

SOURCES = {"ie_bills": "bill_key", "ie_divisions": "division_key",
           "ie_questions": "question_key", "ie_speeches": "speech_key"}
QUEUE_MARKER = "<!-- ie-session-queue v1 -->"


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
    # Phase 2 (9 October 2026). A question is judged on its own words (the
    # answer's one line goes with it, as context, never as the asker's
    # ground). A speech is judged only when the member's OWN words matched
    # (areas_from 'own'): one that stands on its bill's title takes the
    # bill's score in the edition, as an inheriting division does.
    for r in conn.execute("SELECT * FROM ie_questions WHERE triage_score IS NULL "
                          "AND areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["areas"])
        if not areas:
            continue
        title = "{0} parliamentary question {1} ({2}) by {3}{4} to the {5}: {6}".format(
            (r["qtype"] or "written").title(), r["ref"] or r["question_key"], r["date"] or "?",
            r["asker"] or "?", " ({0})".format(r["party"]) if r["party"] else "",
            r["minister"] or r["department"] or "Government", r["heading"] or "")
        text = " ".join("Asked: {0} Answer, one line: {1}".format(
            r["question"] or "", r["answer_takeaway"] or "none yet").split())
        dated.append((r["date"] or "",
                      triage.TriageItem(id="ie_questions:" + r["question_key"], title=title,
                                        text=text[:1500], tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    for r in conn.execute("SELECT * FROM ie_speeches WHERE triage_score IS NULL "
                          "AND areas_from = 'own' AND own_areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["own_areas"])
        if not areas:
            continue
        title = "{0} speech ({1}) by {2}{3}{4} in: {5}".format(
            r["committee"] or (r["chamber"] or "").title(), r["date"] or "?", r["speaker"] or "?",
            " ({0})".format(r["party"]) if r["party"] else "",
            ", {0}".format(r["role"]) if r["role"] else "", r["section_title"] or "")
        text = " ".join("{0} words. Excerpt: {1}".format(r["words"] or 0, r["excerpt"] or "").split())
        dated.append((r["date"] or "",
                      triage.TriageItem(id="ie_speeches:" + r["speech_key"], title=title,
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
    session_queue.forget(conn, table + ":" + k)
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


def counts_by_table(items):
    out = {t: 0 for t in SOURCES}
    for it in items:
        table = it.id.partition(":")[0]
        out[table] = out.get(table, 0) + 1
    return out


def queue_out(conn, path, today, limit, log=print):
    """Write the newest `limit` pending items, with the Irish frame and the
    text the API judge would read, for a Claude Code session to score.
    Returns (written, still pending after)."""
    queued = pending(conn)
    items = queued[:max(0, limit)]
    n = session_queue.write_queue(path, items, "Ireland (Oireachtas) judge queue, {0}".format(today), QUEUE_MARKER,
                                  SYSTEM_PROMPT_IE)
    c = counts_by_table(items)
    log("ie-triage: session queue: {0} item(s) written to {1} ({2}); {3} unscored on "
        "our ground in all.".format(n, path, ", ".join(
            "{0} {1}".format(v, k) for k, v in c.items() if v) or "none", len(queued)))
    return n, len(queued) - n


def queue_in(conn, path, today, log=print):
    """Apply a filled-in queue, item by item. Returns (scored, refused, blank),
    or None when the file is not this judge's queue."""
    results, refused, blank = session_queue.read_queue(path, QUEUE_MARKER)
    if refused and refused[0][0] == "(file)":
        log("  [gap] session queue {0} refused: {1}".format(path, refused[0][1]))
        return None
    good, more = session_queue.check_rows(conn, results, SOURCES, "Irish")
    refused = refused + more
    scored = apply(conn, good)
    session_queue.record(conn, "ie", good, today)
    for iid, why in refused:
        log("  [gap] queue item refused: {0}: {1}".format(iid, why))
    log("ie-triage: session queue: {0} item(s) scored, {1} refused, {2} left blank "
        "(they stay pending for the next run).".format(scored, len(refused), len(blank)))
    return scored, len(refused), len(blank)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--limit", type=int, default=LIMIT)
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--rescore", nargs="+", metavar="KEY")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    q = ap.add_mutually_exclusive_group()
    q.add_argument("--queue-out", metavar="PATH",
                   help="write the newest --limit pending items for a Claude Code session; no spend")
    q.add_argument("--queue-in", metavar="PATH",
                   help="apply a session's SCORE/WHY lines from PATH; no spend")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    today = args.date
    for key in args.rescore or []:
        print("ie-triage: {0} row(s) re-queued for {1}".format(rescore(conn, key), key))
    if args.queue_out:
        queue_out(conn, args.queue_out, today, args.limit)
        return 0
    if args.queue_in:
        got = queue_in(conn, args.queue_in, today)
        conn.close()
        return 1 if got is None else 0
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
