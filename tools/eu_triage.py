"""EU triage: the same relevance judge Westminster items get.

    python3 tools/eu_triage.py

Christopher, 2026-09-01: "Triage the EU items." Until now the EU monitor
was taxonomy-only -- a tier-2 match had no judge, and nothing wrote the
why-it-matters line. This pass sends every UNSCORED taxonomy-matched EU
row (consultations, foreseen agenda items, adopted texts, divisions)
through src/triage.py: the same rubric, model and batching Westminster
uses, with the same fallback -- no API key means the deterministic stub
(tier 1 -> 2, tier 2 -> 1) and an empty why line, never a crash.

Scored once, ever: rows keep their score, so the weekly cost is the
week's NEW matched rows -- single digits. Spend is recorded in api_spend
under pass 'eu-triage' like every other paid pass.

Separation guarantee: writes triage_score/why_it_matters on eu_ tables
only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, spend, triage

# table -> (key column, text columns joined for the judge)
SOURCES = {
    "eu_consultations": ("key", ("title", "summary")),
    "eu_agenda": ("activity_id", ("label",)),
    "eu_texts": ("identifier", ("title",)),
    "eu_divisions": ("vote_id", ("label",)),
}


def ensure_columns(conn):
    for table in SOURCES:
        cols = [c[1] for c in conn.execute(
            "PRAGMA table_info({0})".format(table))]
        for col, typ in (("triage_score", "INTEGER"),
                         ("why_it_matters", "TEXT")):
            if col not in cols:
                conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(
                    table, col, typ))
    conn.commit()


def pending(conn):
    items = []
    for table, (key, textcols) in SOURCES.items():
        rows = conn.execute(
            "SELECT * FROM {0} WHERE areas != '[]' AND areas IS NOT NULL "
            "AND triage_score IS NULL".format(table)).fetchall()
        for r in rows:
            text = " ".join((r[c] or "") for c in textcols).strip()
            items.append(triage.TriageItem(
                id="{0}:{1}".format(table, r[key]),
                title=(r["title"] if "title" in r.keys() else None)
                      or (r["label"] if "label" in r.keys() else "?"),
                text=text,
                tier=r["tier"] if "tier" in r.keys() else 2,
                issue_areas=json.loads(r["areas"] or "[]"),
                watchlist_hit=False))
    return items


def apply(conn, results):
    for res in results:
        table, key = res.id.split(":", 1)
        keycol = SOURCES[table][0]
        conn.execute(
            "UPDATE {0} SET triage_score = ?, why_it_matters = ? "
            "WHERE {1} = ?".format(table, keycol),
            (res.score, res.why_it_matters or None, key))
    conn.commit()


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    ensure_columns(conn)
    items = pending(conn)
    if not items:
        print("eu-triage: nothing unscored.")
        return 0
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        secrets_path = os.path.join(ROOT, "config", "secrets.yaml")
        if os.path.exists(secrets_path):
            import yaml
            api_key = (yaml.safe_load(open(secrets_path)) or {}).get(
                "anthropic_api_key")
    today = datetime.date.today().isoformat()
    if api_key:
        # The judge must never take the run down (the 2026-08-05 lesson:
        # an unwrapped triage pass would have crashed Sunday's unattended
        # run). One retry, then the items stay UNSCORED for next week's
        # run -- deliberately not stub-scored, because scores are written
        # once-ever and a transient failure must not freeze stub scores in.
        results, mode = None, "live"
        for attempt in (1, 2):
            try:
                results = triage.score_live(
                    items, api_key=api_key,
                    usage_sink=lambda usage, model: spend.record(
                        conn, "eu-triage", model, usage, dated=today))
                break
            except Exception as exc:
                print("  [gap] live triage attempt {0} failed: {1}".format(
                    attempt, exc))
        if results is None:
            print("eu-triage: {0} item(s) left unscored; next run retries."
                  .format(len(items)))
            conn.close()
            return 0
    else:
        results = triage.score_stub(items)
        mode = "stub (no API key; why lines empty, scores tier-derived)"
    apply(conn, results)
    print("eu-triage: {0} item(s) scored ({1}).".format(len(results), mode))
    for res in sorted(results, key=lambda r: -r.score):
        print("  [{0}] {1}".format(res.score, (res.why_it_matters or
                                               res.id)[:100]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
