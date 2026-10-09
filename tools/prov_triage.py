#!/usr/bin/env python3
"""The provincial judge: a 0-3 score and a why-line per provincial bill on our
ground, per division whose OWN text matched, and per recent Hansard speech.

    python3 tools/prov_triage.py --dry-run              # count and cost, send nothing
    python3 tools/prov_triage.py                        # the newest LIMIT unscored
    python3 tools/prov_triage.py --limit 500 --budget-seconds 1200
    python3 tools/prov_triage.py --rescore prov_bills:ab-31-2/26

Built 9 October 2026 for the provinces edition (tools/prov_monitor.py),
modelled on tools/us_triage.py and tools/ie_triage.py. Same judge, model and
rubric as Westminster, the EU, Germany, Canada, the US and Ireland
(src/triage.py); only the FRAME differs, below.

SPEND NEEDS A YES. The repo rule (Christopher, 5 August 2026): any
Anthropic spend beyond the budgeted weekly UK passes is announced with an
estimate first; --dry-run prints it. The Provinces weekly runs this step only
when the repository variable PROV_JUDGE is 'on', which is how the yes is
recorded. It is not on.

WHAT IS JUDGED.
  * prov_bills on our ground (migration-only excluded), newest stage first;
  * prov_divisions on our ground whose bill is NOT on our ground (or which
    decided no bill): their areas are their own. A division on a bill on
    our ground takes the bill's score in the edition, so judging it again
    would pay twice for one story (src/prov_classify: a division INHERITS
    its bill's areas);
  * prov_speeches on our ground dated in the last RECENT_DAYS only. The
    store holds some 13,000 speeches on our ground back to 2010; judging the
    lot would cost about $31 for scores the edition never shows (it prints
    the week's). --all-speeches takes the whole backlog, and --dry-run
    prints both costs.

SCORES LIVE IN prov_scores, NOT ON THE ROWS (src/prov_store.py): a Hansard
day read again rewrites its speeches, and a score on the row would be lost.
SCORED ONCE, EVER. --rescore <item> puts one back on a human's say-so.
Spend lands in api_spend as 'prov-triage'.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, spend, triage, prov_store  # noqa: E402

SLICE = 4
LIMIT = 500
BUDGET_S = 1200.0
RECENT_DAYS = 90
HIDDEN_AREAS = (11,)
# Measured from the Canadian judge's spend (424 calls, 9 October 2026): per
# item about 690 input and 100 output tokens. Used for the dry run's estimate
# only; the real cost is what api_spend records.
TOKENS_IN_PER_ITEM = 690
TOKENS_OUT_PER_ITEM = 100

NAMES = {"ab": "Alberta", "sk": "Saskatchewan", "bc": "British Columbia", "mb": "Manitoba",
         "on": "Ontario", "qc": "Quebec", "nb": "New Brunswick",
         "nl": "Newfoundland and Labrador", "ns": "Nova Scotia", "pe": "Prince Edward Island",
         "yt": "Yukon", "nt": "Northwest Territories", "nu": "Nunavut"}

# THE PROVINCIAL FRAME. The EU judge, told it served a UK monitor, scored a
# Hong Kong resolution 0 as "unrelated to CitizenGO's UK-focused campaign
# areas"; every jurisdiction since gets its own frame for that reason.
SYSTEM_PROMPT_PROV = triage.SYSTEM_PROMPT.replace(
    "You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns",
    "You are the triage layer of CitizenGO's Canadian provinces monitor, covering bills, "
    "recorded divisions and Hansard speeches in the provincial legislatures: Alberta, "
    "Saskatchewan, British Columbia, Manitoba, Ontario, Quebec (the National Assembly, in "
    "French), New Brunswick, Newfoundland and Labrador and Nova Scotia. Never mark an item "
    "down for not being British or for being provincial: education, health care, "
    "human-rights codes and family law are provincial powers in Canada, so much of this "
    "ground moves here and not in Ottawa. Provincial names to know: Policy 713 (New "
    "Brunswick) and SOGI 123 (British Columbia) are school gender-identity policies; a "
    "'Parents' Bill of Rights' and parental notification or consent for a pupil's new "
    "name or pronouns are parental rights and gender ideology in schools; 'medical "
    "assistance in dying' (MAID) and 'aide médicale à mourir' and 'soins de fin de vie' are "
    "assisted suicide; 'laïcité' and the laicity of the State are freedom of religion; "
    "'safe access zones' and 'buffer zones' around clinics are abortion; 'conversion "
    "therapy' bans are gender and sexuality policy; the notwithstanding clause is a "
    "government overriding the Charter. Provincial bills name a statute, not a subject "
    "(an 'Education Amendment Act' can be the pronoun bill): judge what the text does. A "
    "BILL is given by its title and the passage of its text that matched; a DIVISION by "
    "its question, its stage, its result and its tally; a SPEECH by the member, the "
    "debate's heading and the passage that matched (score what was said and how "
    "prominent the debate is). CitizenGO campaigns", 1)
assert SYSTEM_PROMPT_PROV != triage.SYSTEM_PROMPT

TABLES = ("prov_bills", "prov_divisions", "prov_speeches")


def _ours(areas_json):
    try:
        areas = json.loads(areas_json or "[]")
    except (TypeError, ValueError):
        return None
    return areas if [a for a in areas if a not in HIDDEN_AREAS] else None


def _one(text):
    return " ".join((text or "").split())


def _last_stage_date(stages_json):
    try:
        stages = json.loads(stages_json or "[]")
    except (TypeError, ValueError):
        return ""
    dates = [s.get("date") for s in stages if isinstance(s, dict) and s.get("date")]
    return max(dates) if dates else ""


def scored_items(conn):
    prov_store.ensure_schema(conn)
    return {r[0] for r in conn.execute("SELECT item FROM prov_scores")}


def pending(conn, today, all_speeches=False, recent_days=RECENT_DAYS):
    """Unscored items on our ground, newest first, migration-only excluded."""
    done = scored_items(conn)
    dated = []
    ours = {}
    for r in conn.execute("SELECT * FROM prov_bills WHERE areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["areas"])
        if not areas:
            continue
        ours[r["bill_key"]] = True
        item = "prov_bills:" + r["bill_key"]
        if item in done:
            continue
        title = "{0} Bill {1} ({2}-{3}): {4}".format(
            NAMES.get(r["prov"], r["prov"]), r["number"] or "?", r["legislature"], r["session"],
            r["title_en"] or r["title_fr"] or "")
        text = _one("Latest stage: {0}{1}. {2}{3}Passage that matched: {4}".format(
            r["latest_stage"] or "unknown", "; royal assent " + r["royal_assent"]
            if r["royal_assent"] else "",
            "French title: {0}. ".format(r["title_fr"]) if r["title_fr"] and r["title_en"] else "",
            "Government bill. " if r["is_government"] == 1 else
            ("Private member's bill. " if r["is_government"] == 0 else ""),
            r["excerpt"] or "none"))
        dated.append((_last_stage_date(r["stages"]) or (r["last_seen"] or "")[:10],
                      triage.TriageItem(id=item, title=title, text=text[:1500],
                                        tier=r["tier"] or 2, issue_areas=areas,
                                        watchlist_hit=False)))
    for r in conn.execute("SELECT * FROM prov_divisions WHERE areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["areas"])
        if not areas or (r["bill_key"] and ours.get(r["bill_key"])):
            continue
        item = "prov_divisions:" + r["division_key"]
        if item in done:
            continue
        title = "{0} division, {1}: {2}".format(
            NAMES.get(r["prov"], r["prov"]), r["date"] or "?", r["stage"] or r["vote_on"] or "")
        tally = (" Yeas {0}, Nays {1}.".format(r["yeas"], r["nays"])
                 if r["kind"] == "recorded" and r["yeas"] is not None else " Decided on voice.")
        text = _one("Question: {0} Result: {1}.{2} Passage that matched: {3}".format(
            r["question"] or "not printed", r["result"] or "?", tally, r["excerpt"] or "none"))
        dated.append((r["date"] or "",
                      triage.TriageItem(id=item, title=title, text=text[:1500],
                                        tier=r["tier"] or 2, issue_areas=areas,
                                        watchlist_hit=False)))
    horizon = (datetime.date.fromisoformat(today) - datetime.timedelta(days=recent_days)).isoformat()
    sql = ("SELECT s.*, m.name AS member_name, m.party AS member_party FROM prov_speeches s "
           "LEFT JOIN prov_members m ON m.prov = s.prov AND m.member_key = s.member_key "
           "WHERE s.areas NOT IN ('[]', '[11]')")
    params = ()
    if not all_speeches:
        sql += " AND s.date >= ?"
        params = (horizon,)
    for r in conn.execute(sql, params):
        areas = _ours(r["areas"])
        if not areas:
            continue
        item = "prov_speeches:" + r["speech_id"]
        if item in done:
            continue
        title = "{0} Hansard, {1}: {2} ({3}) on {4}".format(
            NAMES.get(r["prov"], r["prov"]), r["date"] or "?",
            r["member_name"] or r["speaker_label"] or "?", r["member_party"] or "?",
            r["subject"] or r["rubric"] or "an unnamed debate")
        text = _one("Debate: {0}. Section: {1}. Passage that matched: {2}".format(
            r["subject"] or "?", r["rubric"] or "?", r["excerpt"] or ""))
        dated.append((r["date"] or "",
                      triage.TriageItem(id=item, title=title, text=text[:1500],
                                        tier=r["tier"] or 2, issue_areas=areas,
                                        watchlist_hit=False)))
    dated.sort(key=lambda d: (d[0], d[1].id), reverse=True)
    return [item for _, item in dated]


def estimate_usd(n, model=triage.TRIAGE_MODEL):
    rate = spend.RATES.get(model) or {"input": 0, "output": 0}
    return (n * TOKENS_IN_PER_ITEM * rate["input"] + n * TOKENS_OUT_PER_ITEM * rate["output"]) / 1e6


def _prov_of(conn, item):
    table, _, key = item.partition(":")
    col = {"prov_bills": "bill_key", "prov_divisions": "division_key",
           "prov_speeches": "speech_id"}.get(table)
    if not col:
        return None
    row = conn.execute("SELECT prov FROM {0} WHERE {1} = ?".format(table, col), (key,)).fetchone()
    return row[0] if row else None


def apply(conn, results, today=None, model=triage.TRIAGE_MODEL):
    n = 0
    for res in results:
        table = (res.id or "").partition(":")[0]
        if res.score is None or table not in TABLES:
            continue
        prov = _prov_of(conn, res.id)
        if not prov:
            continue
        conn.execute("INSERT OR REPLACE INTO prov_scores (item, prov, score, why, model, scored_at) "
                     "VALUES (?,?,?,?,?,?)", (res.id, prov, res.score, res.why_it_matters or None,
                                              model, today))
        n += 1
    conn.commit()
    return n


def rescore(conn, item):
    """Re-queue one item: 'prov_bills:<key>', 'prov_divisions:<key>' or
    'prov_speeches:<id>'. A bare key is taken as a bill."""
    if ":" not in item:
        item = "prov_bills:" + item
    prov_store.ensure_schema(conn)
    n = conn.execute("DELETE FROM prov_scores WHERE item = ?", (item,)).rowcount
    conn.commit()
    return n


def judge(conn, items, api_key, today, log=print, budget=None, transport=None):
    """Score in slices of SLICE, halving a slice that fails twice. Returns (scored, gaps)."""
    gaps = [0]

    def score_chunk(chunk):
        for attempt in (1, 2):
            try:
                return triage.score_live(
                    chunk, api_key=api_key, system=SYSTEM_PROMPT_PROV, transport=transport,
                    usage_sink=lambda usage, model: spend.record(
                        conn, "prov-triage", model, usage, dated=today))
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
        scored += apply(conn, score_chunk(chunk), today)
    return scored, gaps[0]


def counts_by_table(items):
    out = {t: 0 for t in TABLES}
    for it in items:
        out[it.id.partition(":")[0]] = out.get(it.id.partition(":")[0], 0) + 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--limit", type=int, default=LIMIT)
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--rescore", nargs="+", metavar="ITEM")
    ap.add_argument("--all-speeches", action="store_true",
                    help="judge every speech on our ground, not only the last {0} days".format(RECENT_DAYS))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    import sqlite3
    conn.row_factory = sqlite3.Row
    today = args.date
    for item in args.rescore or []:
        print("prov-triage: {0} score(s) removed for {1}; judged again this run".format(
            rescore(conn, item), item))
    queued = pending(conn, today, all_speeches=args.all_speeches)
    items = queued[:args.limit]
    if args.dry_run:
        c = counts_by_table(queued)
        print("prov-triage: {0} unscored item(s) on our ground ({1} bills, {2} divisions, {3} "
              "speeches from the last {4} days); this run would judge {5} in about {6} call(s), "
              "roughly ${7:.2f}; the whole queue about ${8:.2f}. Nothing sent.".format(
                  len(queued), c["prov_bills"], c["prov_divisions"], c["prov_speeches"],
                  RECENT_DAYS, len(items), (len(items) + SLICE - 1) // SLICE,
                  estimate_usd(len(items)), estimate_usd(len(queued))))
        if not args.all_speeches:
            every = pending(conn, today, all_speeches=True)
            print("prov-triage: with every speech on our ground (--all-speeches) the backlog "
                  "is {0} item(s), roughly ${1:.2f}.".format(len(every), estimate_usd(len(every))))
        return 0
    if not items:
        print("prov-triage: nothing unscored.")
        return 0
    if len(queued) > len(items):
        print("prov-triage: {0} unscored; judging the newest {1} this run, the rest wait "
              "-- disclosed, not silent.".format(len(queued), len(items)))
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        path = os.path.join(ROOT, "config", "secrets.yaml")
        if os.path.exists(path):
            import yaml
            api_key = (yaml.safe_load(open(path)) or {}).get("anthropic_api_key")
    if not api_key:
        print("prov-triage: {0} unscored and no ANTHROPIC_API_KEY; left unscored rather "
              "than stub-scored, because scores are written once ever.".format(len(items)))
        return 0
    scored, gaps = judge(conn, items, api_key, today, budget=drain.Budget(args.budget_seconds))
    dist = dict(conn.execute("SELECT score, COUNT(*) FROM prov_scores GROUP BY 1").fetchall())
    print("  prov_scores so far: {0}".format(
        ", ".join("{0}: {1}".format(k, dist[k]) for k in sorted(dist)) or "none"))
    print("prov-triage: {0} of {1} item(s) scored, {2} gap(s).".format(scored, len(items), gaps))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
