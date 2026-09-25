"""Judge what KIND of reply each written question got.

    python3 tools/judge_answers.py --dry-run      # what it would cost
    python3 tools/judge_answers.py --week 2026-09-21
    python3 tools/judge_answers.py                # every unjudged question

Christopher, 2026-09-25: "add those two as a judge field." The edition
labels a reply as referred / not held / deferred by RULE, because
departments phrase those formulaically. The two that are left -- whether an
answer gave figures, or merely restated policy without engaging the
question -- are judgements, and a regex attempt at them filed four
palliative-care answers under "figures given" with no figure in any of
them. So they come from the triage model, as answer_kind, and the renderer
routes a "restated" reply to the tail.

Two passes, and the first is FREE:

  1. Fill extra.answer_text from the detail archive. Until 2026-09-25 the
     ingester never stored the answer, so the judge scored a written
     question from its heading alone -- it wrote a why-line for "Georgia:
     Surrogacy" having read neither the question nor the reply. Local
     only, no network, no API.
  2. Score the questions that still have no answer_kind.

Pass 1 alone is worth running: it is what lets every LATER rescore, retag
or stance pass see the reply. Pass 2 costs tokens, so --dry-run prints the
item count and the batch count and stops.

STORE WRITER. Obeys the usual discipline -- the caller pulls the store
first and pushes after; this opens it for writing and must not run beside
another writer.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, triage
from src.ingest import pqs

RAW = os.path.join(ROOT, "data", "raw")


def fill_answers(conn, raw_dir=RAW, limit=None):
    """Copy the archived answer into items.extra. Returns (filled, missing)."""
    rows = conn.execute(
        "SELECT id, extra FROM items WHERE source_feed = 'pq'").fetchall()
    want = {}
    for row in rows:
        try:
            extra = json.loads(row["extra"] or "{}")
        except ValueError:
            continue
        if (extra.get("answer_text") or "").strip():
            continue
        want[str(row["id"]).split(":")[-1]] = (row["id"], extra)
    if not want:
        return 0, 0
    archive = pqs.archive_map(raw_dir, list(want))
    filled = 0
    for qid, (item_id, extra) in want.items():
        got = archive.get(qid)
        if not got or not got["answer"]:
            continue
        extra["answer_text"] = got["answer"][:900]
        # The archived question is whole; ingest's copy was cut at 600.
        if len(got["question"]) > len(extra.get("question_text") or ""):
            extra["question_text"] = got["question"][:600]
        conn.execute("UPDATE items SET extra = ? WHERE id = ?",
                     (json.dumps(extra), item_id))
        filled += 1
        if limit and filled >= limit:
            break
    conn.commit()
    return filled, len(want) - filled


def unjudged(conn, week=None):
    """PQ rows with an answer stored and no answer_kind yet."""
    sql = ("SELECT id, title, extra, issue_areas, tier FROM items "
           "WHERE source_feed = 'pq' AND answer_kind IS NULL")
    args = []
    if week:
        # The edition's window: the seven days before its Monday.
        import datetime
        monday = datetime.date.fromisoformat(week)
        sql += " AND event_date >= ? AND event_date < ?"
        args = [(monday - datetime.timedelta(days=7)).isoformat(), week]
    out = []
    for row in conn.execute(sql, args):
        try:
            extra = json.loads(row["extra"] or "{}")
        except ValueError:
            continue
        if not (extra.get("answer_text") or "").strip():
            continue      # nothing to judge; pass 1 has not reached it
        out.append(triage.TriageItem(
            id=row["id"], title=row["title"],
            text=triage.evidence_text(row["extra"]),
            tier=row["tier"], issue_areas=json.loads(row["issue_areas"] or "[]"),
            watchlist_hit=False))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", help="ISO Monday; limits to that edition's window")
    ap.add_argument("--dry-run", action="store_true",
                    help="fill answers, then report what scoring would cover")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--rescore", action="store_true",
                    help="also rewrite triage_score and why_it_matters from "
                         "this pass. Off by default: it would change editions "
                         "already sent.")
    args = ap.parse_args()

    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    db.init_db(conn)

    filled, missing = fill_answers(conn)
    print("answers copied into the store: {0} (archive had none for {1})".format(
        filled, missing))

    items = unjudged(conn, args.week)
    if args.limit:
        items = items[:args.limit]
    batches = (len(items) + triage.BATCH_SIZE - 1) // triage.BATCH_SIZE
    chars = sum(len(i.text) for i in items)
    print("to judge: {0} question(s) in {1} batch(es), {2} chars of evidence".format(
        len(items), batches, chars))
    if args.dry_run or not items:
        print("dry run: nothing scored." if args.dry_run else "nothing to do.")
        return 0

    results = triage.score_live(items)
    kinds = {}
    for r in results:
        kinds[r.answer_kind or "(none)"] = kinds.get(r.answer_kind or "(none)", 0) + 1

    # ONLY answer_kind. triage.apply_scores would also write triage_score and
    # why_it_matters, and this pass puts the answer in front of the model for
    # the first time, so a score could move: a question in this week's
    # edition could quietly drop below the digest floor and vanish. Adding a
    # label is what was asked for; re-judging the whole back catalogue is
    # not, and it would silently change an edition already sent.
    # --rescore is the deliberate way to do the other thing.
    written = 0
    for r in results:
        if not r.answer_kind:
            continue
        conn.execute("UPDATE items SET answer_kind = ? WHERE id = ?",
                     (r.answer_kind, r.id))
        written += 1
    conn.commit()
    if args.rescore:
        triage.apply_scores(conn, items, results)
        print("scores and why-lines rewritten too (--rescore)")
    print("judged {0}, labels written {1}: {2}".format(
        len(results), written,
        ", ".join("{0} {1}".format(v, k) for k, v in sorted(kinds.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
