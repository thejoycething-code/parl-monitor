#!/usr/bin/env python3
"""The US judge: a 0-3 score and a why-line per Congress bill on our ground,
and per roll call whose OWN text matched.

    python3 tools/us_triage.py --dry-run                # count and cost, send nothing
    python3 tools/us_triage.py --queue-out /tmp/q.md --limit 25   # for a session
    python3 tools/us_triage.py --queue-in /tmp/q.md               # apply its scores
    python3 tools/us_triage.py                          # the newest LIMIT unscored
    python3 tools/us_triage.py --limit 800 --budget-seconds 2400

Built 9 October 2026 for the US edition (tools/us_monitor.py). Same judge,
model and rubric as Westminster, the EU, Germany and Canada (src/triage.py);
only the FRAME differs, below.

SPEND NEEDS A YES. The repo rule (Christopher, 5 August 2026): any
Anthropic spend beyond the budgeted weekly UK passes is announced with an
estimate first. The backlog at first run was 769 items (753 bills, 16 votes);
--dry-run prints the estimate. The US weekly runs this step only when the
repository variable US_JUDGE is 'on', which is how the yes is recorded. Since
9 October 2026 the free session judge below is the default and it is off.

WHAT IS JUDGED. us_bills on our ground, migration-only excluded (collated,
never campaigned). Newest first by latest action, so a live bill is never
queued behind a dead one. Votes are judged ONLY where their own text matched
(own_areas): a vote that merely inherits its bill's areas takes the bill's
score in the edition, so judging it again would pay twice for one story.
Since 9 October 2026 also the Federal Register documents (us_fr_documents)
and Supreme Court opinions and grants (us_court_cases) on our ground, each
on the text its collector classified, and floor speeches from the
Congressional Record (us_record_speeches) whose OWN words matched, on the
stored excerpt (the text itself is never stored). Since the states were
added (same day), state bills on our ground (uss_bills) with an action in the last 30
days: never the whole first read.

SCORED ONCE, EVER. --rescore <key> puts one back on a human's say-so.
Spend lands in api_spend as 'us-triage'.

THE SESSION JUDGE, FREE (9 October 2026, Christopher: "Switch US, Ireland
and Australia scoring to the free route"; the DEFAULT route since).
--queue-out writes the newest --limit pending items, with the US frame
and the very text the API judge would read, to a file in
src/session_queue.py's format, under this judge's own marker line. A Claude
Code session on the Mac Mini, on the work subscription, fills in SCORE and
WHY (jobs/us-session-judge.sh through tools/session_judge.sh). --queue-in
reads it back STRICTLY, item by item (one digit 0-3 and a why-line, or
refused with its reason; another judge's file is refused whole), and
applies the scores through apply() exactly as API scores are applied; the
rows carry no model column, so session_scores notes each one as model
'claude-code-session'. Once ever still holds: a row scored meanwhile is not
overwritten. Neither flag needs ANTHROPIC_API_KEY or spends anything;
US_JUDGE (the paid API path) stays the alternative, and off.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, spend, triage, us_store, session_queue  # noqa: E402

SLICE = 4
LIMIT = 800
BUDGET_S = 1800.0
HIDDEN_AREAS = (11,)
# Measured from the Canadian judge's spend (424 calls, 9 October 2026): per
# item about 690 input and 100 output tokens. Used for the dry run's estimate
# only; the real cost is what api_spend records.
TOKENS_IN_PER_ITEM = 690
TOKENS_OUT_PER_ITEM = 100

# THE US FRAME. The EU judge, told it served a UK monitor, scored a Hong Kong
# resolution 0 as "unrelated to CitizenGO's UK-focused campaign areas"; every
# jurisdiction since gets its own frame for that reason.
SYSTEM_PROMPT_US = triage.SYSTEM_PROMPT.replace(
    "You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns",
    "You are the triage layer of CitizenGO's US Congress monitor, covering bills and recorded "
    "votes in the House of Representatives and the Senate, executive orders and agency rules "
    "in the Federal Register, Supreme Court opinions and grants of certiorari, and members' "
    "floor speeches in the Congressional Record. Never mark an item down for not "
    "being British: an American matter in one of these areas is fully in scope. American "
    "names to know: 'medical aid in dying' and 'Death with Dignity' are assisted suicide; "
    "the Hyde Amendment and Planned Parenthood funding are abortion; Title IX disputes over "
    "sex are single-sex spaces; 'gender transition procedures' are youth gender medicine; "
    "RFRA is freedom of religion. Contraception is in scope where it touches life "
    "(abortifacient methods, mandates against conscience), not as routine health policy. "
    "Much of this ground moves as riders inside appropriations, defence (NDAA) and "
    "reconciliation bills: score such a bill on what it does in these areas, not on its "
    "size. A BILL is given by its titles, its Congressional Research Service subject terms "
    "and its CRS summary; a VOTE by its question and its own text; an EXECUTIVE ACTION by "
    "its title and the agency's abstract (a proposed rule open for comment is something "
    "campaigners can act on); a COURT item by the case name and the Court's holding or the "
    "question presented; a FLOOR SPEECH by the member, the debate's heading and the passage "
    "of the speech that matched (score what the member said and how prominent the "
    "debate is, never the size of the bill); a STATE BILL by its title, the state's subject "
    "terms and its abstract, where the state gives them (many give only a title). "
    "CitizenGO campaigns", 1)
assert SYSTEM_PROMPT_US != triage.SYSTEM_PROMPT

SOURCES = {"us_bills": "bill_key", "us_divisions": "division_key",
           "us_fr_documents": "document_number", "us_court_cases": "case_key",
           "us_record_speeches": "speech_key", "uss_bills": "bill_id"}
QUEUE_MARKER = "<!-- us-session-queue v1 -->"


def _try(conn, sql):
    """Rows of a table an older store may not have yet."""
    import sqlite3
    try:
        return conn.execute(sql).fetchall()
    except sqlite3.OperationalError:
        return []


# State bills are judged only once they MOVE: one with an action in the last
# STATE_RECENT_DAYS. The first read of the fifty stored 4,418 bills on our
# ground (9 October 2026), most of them dead with their session; judging the
# lot would cost about $11 for scores the edition never shows.
STATE_RECENT_DAYS = 30


def _ours(areas_json):
    areas = json.loads(areas_json or "[]")
    return areas if [a for a in areas if a not in HIDDEN_AREAS] else None


def pending(conn):
    """Unscored items on our ground, newest first, migration-only excluded."""
    us_store.ensure_schema(conn)
    dated = []
    for r in conn.execute("SELECT * FROM us_bills WHERE triage_score IS NULL "
                          "AND areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["areas"])
        if not areas:
            continue
        subjects = "; ".join(json.loads(r["subjects"] or "[]")[:25])
        title = "{0} {1}".format(r["bill_key"].split("/", 1)[1].upper().replace("/", " "),
                                 r["title"] or "")
        text = " ".join("Status: {0}. Subjects: {1}. Summary: {2}".format(
            r["latest_action"] or "?", subjects or "none", r["summary"] or "none yet").split())
        dated.append((r["latest_action_at"] or r["introduced"] or "",
                      triage.TriageItem(id="us_bills:" + r["bill_key"], title=title,
                                        text=text[:1500], tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    for r in conn.execute("SELECT * FROM us_divisions WHERE triage_score IS NULL "
                          "AND own_areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["own_areas"])
        if not areas:
            continue
        title = "{0} vote {1} ({2}) {3}".format(r["chamber"].title(), r["roll"],
                                                 r["date"] or "?", r["legis_num"] or "")
        # The amendment's own purpose (phase 1b) is the substance of a House
        # amendment vote, whose Clerk description is usually blank: without it
        # the judge scored the NDAA gender-transition amendment 1 (9 October).
        text = " ".join("{0}. {1}. {2}. Result: {3}.".format(
            r["question"] or "", r["description"] or "",
            "Amendment: {0}".format(r["amendment_text"]) if r["amendment_text"] else "",
            r["result"] or "?").split())
        dated.append((r["date"] or "",
                      triage.TriageItem(id="us_divisions:" + r["division_key"], title=title,
                                        text=text[:1500], tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    # Executive actions and the Court (9 October 2026): judged on what each
    # collector classified, so the judge reads the text the filter read.
    for r in conn.execute("SELECT * FROM us_fr_documents WHERE triage_score IS NULL "
                          "AND areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["areas"])
        if not areas:
            continue
        title = "{0}{1}: {2}".format(r["subtype"] or r["doc_type"],
                                     " {0}".format(r["eo_number"]) if r["eo_number"] else "",
                                     r["title"] or "")
        text = " ".join("{0}. Agencies: {1}. {2} Comments close: {3}.".format(
            r["action"] or r["doc_type"], ", ".join(json.loads(r["agencies"] or "[]")) or "?",
            r["abstract"] or "", r["comments_close_on"] or "n/a").split())
        dated.append((r["publication_date"] or "",
                      triage.TriageItem(id="us_fr_documents:" + r["document_number"], title=title,
                                        text=text[:1500], tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    for r in conn.execute("SELECT * FROM us_court_cases WHERE triage_score IS NULL "
                          "AND areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["areas"])
        if not areas:
            continue
        kind = "Supreme Court opinion" if r["kind"] == "opinion" else "Supreme Court grant of certiorari"
        title = "{0}: {1} (No. {2})".format(kind, r["case_name"] or "?", r["docket"] or "?")
        text = " ".join("{0}. {1}: {2}".format(
            r["title"] or "", "Holding" if r["kind"] == "opinion" else "Question presented",
            r["summary"] or "not read").split())
        dated.append((r["decided"] or "",
                      triage.TriageItem(id="us_court_cases:" + r["case_key"], title=title,
                                        text=text[:1500], tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    # Floor speeches (phase 3a, 9 October 2026): judged on what the member
    # said, never on the bill. Only a speech whose OWN words matched: one
    # that only borrows its debate's bill (areas_from 'bill' or 'watch')
    # takes the bill's score in the edition, as an inheriting vote does.
    for r in _try(conn, "SELECT * FROM us_record_speeches WHERE triage_score IS NULL "
                        "AND own_areas NOT IN ('[]', '[11]')"):
        areas = _ours(r["own_areas"])
        if not areas:
            continue
        title = "Floor speech, {0} {1}, {2} ({3}-{4}): {5}".format(
            "Senate" if r["chamber"] == "senate" else "House", r["date"] or "?",
            r["name"] or r["speaker"] or "?", r["party"] or "?", r["state"] or "?",
            r["title"] or "")
        bills = ", ".join(json.loads(r["bill_keys"] or "[]")[:5])
        text = " ".join("{0} Bills cited: {1}. Matched: {2}.".format(
            r["excerpt"] or "", bills or "none",
            ", ".join(json.loads(r["matched_terms"] or "[]")[:8])).split())
        dated.append((r["date"] or "",
                      triage.TriageItem(id="us_record_speeches:" + r["speech_key"], title=title,
                                        text=text[:1500], tier=r["tier"] or 2,
                                        issue_areas=areas, watchlist_hit=False)))
    # The fifty states (tools/us_states.py): only bills that moved recently.
    recent = (datetime.date.today() - datetime.timedelta(days=STATE_RECENT_DAYS)).isoformat()
    try:
        state_rows = conn.execute("SELECT * FROM uss_bills WHERE triage_score IS NULL "
                                  "AND areas NOT IN ('[]', '[11]') AND latest_action_at >= ?",
                                  (recent,)).fetchall()
    except Exception:                                       # noqa: BLE001
        state_rows = []
    for r in state_rows:
        areas = _ours(r["areas"])
        if not areas:
            continue
        title = "{0} {1}: {2}".format(r["state"].upper(), r["identifier"], r["title"] or "")
        subjects = "; ".join(json.loads(r["subjects"] or "[]")[:25])
        text = " ".join("State legislature bill. Status: {0}. Subjects: {1}. Abstract: {2}".format(
            r["latest_action"] or "?", subjects or "none given",
            r["abstract"] or "none given").split())
        dated.append((r["latest_action_at"] or r["introduced_at"] or "",
                      triage.TriageItem(id="uss_bills:" + r["bill_id"], title=title,
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
    """Re-queue one row: '119/hr/28' for a bill, 'us_divisions:<key>', or
    'uss_bills:ocd-bill/<uuid>' for a state bill."""
    table, _, k = key.partition(":") if key.startswith(("us_", "uss_")) else ("us_bills", "", key)
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
                    chunk, api_key=api_key, system=SYSTEM_PROMPT_US, transport=transport,
                    usage_sink=lambda usage, model: spend.record(
                        conn, "us-triage", model, usage, dated=today))
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
    """Write the newest `limit` pending items, with the US frame and the
    text the API judge would read, for a Claude Code session to score.
    Returns (written, still pending after)."""
    queued = pending(conn)
    items = queued[:max(0, limit)]
    n = session_queue.write_queue(path, items, "US Congress judge queue, {0}".format(today), QUEUE_MARKER,
                                  SYSTEM_PROMPT_US)
    c = counts_by_table(items)
    log("us-triage: session queue: {0} item(s) written to {1} ({2}); {3} unscored on "
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
    good, more = session_queue.check_rows(conn, results, SOURCES, "US")
    refused = refused + more
    scored = apply(conn, good)
    session_queue.record(conn, "us", good, today)
    for iid, why in refused:
        log("  [gap] queue item refused: {0}: {1}".format(iid, why))
    log("us-triage: session queue: {0} item(s) scored, {1} refused, {2} left blank "
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
        print("us-triage: {0} row(s) re-queued for {1}".format(rescore(conn, key), key))
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
        print("us-triage: {0} unscored item(s) on our ground; this run would judge {1} "
              "in about {2} call(s), roughly ${3:.2f}. Nothing sent.".format(
                  len(queued), len(items), (len(items) + SLICE - 1) // SLICE,
                  estimate_usd(len(items))))
        return 0
    if not items:
        print("us-triage: nothing unscored.")
        return 0
    if len(queued) > len(items):
        print("us-triage: {0} unscored; judging the newest {1} this run, the rest wait "
              "-- disclosed, not silent.".format(len(queued), len(items)))
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        path = os.path.join(ROOT, "config", "secrets.yaml")
        if os.path.exists(path):
            import yaml
            api_key = (yaml.safe_load(open(path)) or {}).get("anthropic_api_key")
    if not api_key:
        print("us-triage: {0} unscored and no ANTHROPIC_API_KEY; left unscored rather "
              "than stub-scored, because scores are written once ever.".format(len(items)))
        return 0
    scored, gaps = judge(conn, items, api_key, today, budget=drain.Budget(args.budget_seconds))
    for table in SOURCES:
        dist = dict(conn.execute("SELECT triage_score, COUNT(*) FROM {0} "
                                 "WHERE triage_score IS NOT NULL GROUP BY 1".format(table)).fetchall())
        print("  {0} scored so far: {1}".format(
            table, ", ".join("{0}: {1}".format(k, dist[k]) for k in sorted(dist)) or "none"))
    print("us-triage: {0} of {1} item(s) scored, {2} gap(s).".format(scored, len(items), gaps))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
