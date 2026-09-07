"""The judge evaluation corpus, from the command line (src/evalbank.py).

    python3 tools/judge_eval.py sample --week 2026-09-07     # write reviews/judge-sample-<week>.md
    python3 tools/judge_eval.py ingest                       # read filled samples and review files
    python3 tools/judge_eval.py report [--write]             # agreement; --write -> docs/judge-eval.md
    python3 tools/judge_eval.py export --week 2026-09-07     # data/eval/<week>.jsonl
    python3 tools/judge_eval.py seed                         # bank the scores already in the store, once
    python3 tools/judge_eval.py rescore [--spend] [--limit N]   # drift check; asks before spending

The Sunday pull banks and exports; the Monday publish ingests, writes the
sample and the report. This is the by-hand route and the seed.
ONE WRITER AT A TIME: pull the store first, push it after.
"""

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, evalbank, triage  # noqa: E402


def seed(conn):
    """Bank every item already scored in the store, keyed to the Monday of
    its capture week. The mode is 'historic': the live/stub distinction was
    not recorded then, so these are sampled but flagged."""
    evalbank.ensure_table(conn)
    rows = conn.execute("SELECT id, title, tier, issue_areas, matched_terms, triage_score, why_it_matters, captured_at "
                        "FROM items WHERE triage_score IS NOT NULL").fetchall()
    n = 0
    for r in rows:
        try:
            d = datetime.date.fromisoformat((r["captured_at"] or "")[:10])
        except ValueError:
            continue
        week = (d + datetime.timedelta(days=(7 - d.weekday()) % 7 or 7)).isoformat() if d.weekday() != 0 else d.isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO judge_verdicts (week, item_id, feed, title, tier, candidate_areas, watchlist_hit, "
            "score, why, areas, model, prompt_sha, mode, captured_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (week, r["id"], r["id"].split(":", 1)[0], r["title"], r["tier"], r["issue_areas"] or "[]", 0,
             r["triage_score"], r["why_it_matters"] or "", r["issue_areas"] or "[]", "historic", None, "historic",
             r["captured_at"] or ""))
        n += 1
    conn.commit()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("sample", "ingest", "report", "export", "seed", "rescore"))
    ap.add_argument("--week")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--spend", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    if args.action == "seed":
        print("seeded {0} historic verdict(s)".format(seed(conn)))
    elif args.action == "sample":
        week = args.week or datetime.date.today().isoformat()
        path, n = evalbank.write_sample(conn, week, os.path.join(ROOT, "reviews", "judge-sample-{0}.md".format(week)))
        print("sample: {0} item(s) -> {1}".format(n, os.path.relpath(path, ROOT) if path else "none (no live verdicts that week)"))
    elif args.action == "ingest":
        e, i = evalbank.ingest_samples(conn, os.path.join(ROOT, "reviews"))
        print("ingested {0} explicit verdict(s) and {1} review priorit(ies)".format(e, i))
    elif args.action == "report":
        text = evalbank.report(conn, write_to=os.path.join(ROOT, "docs", "judge-eval.md") if args.write else None)
        print(text if not args.write else "docs/judge-eval.md written")
    elif args.action == "export":
        week = args.week or datetime.date.today().isoformat()
        path, n = evalbank.export(conn, week)
        print("exported {0} verdict(s) -> {1}".format(n, os.path.relpath(path, ROOT)))
    elif args.action == "rescore":
        labelled = conn.execute("SELECT COUNT(*) FROM judge_verdicts WHERE human_score IS NOT NULL AND mode != 'stub'").fetchone()[0]
        n = min(labelled, args.limit)
        if not args.spend:
            print("rescore would send {0} labelled item(s) to {1} in {2} call(s); this SPENDS API funds. "
                  "Re-run with --spend to do it.".format(n, triage.TRIAGE_MODEL, (n + 19) // 20))
        else:
            from src import publish, spend
            key = publish.load_secrets().get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
            out = evalbank.rescore(conn, key, limit=args.limit,
                                   usage_sink=lambda usage, model: spend.record(conn, "judge-rescore", model, usage))
            print(json.dumps(out, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
