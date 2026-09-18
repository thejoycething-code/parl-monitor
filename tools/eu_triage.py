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
# EVERY eu_ table that carries `areas` belongs here. The first version
# listed four and the monitor then grew five more collectors -- courts,
# written questions, committee documents, ECIs, speeches -- so 66 matched
# rows sat unscored while the run cheerfully printed "nothing unscored"
# (found 2026-09-03 by reading a green CI log that had just stored 22
# matched questions). A structural test now fails if a table with an
# `areas` column is missing from this map.
SOURCES = {
    "eu_consultations": ("key", ("title", "summary")),
    "eu_agenda": ("activity_id", ("label",)),
    # The EXCERPT goes with the title (17 Sept 2026). Adopted texts are now
    # matched on their BODY, because Parliament titles are generic -- so the
    # judge was about to be handed "An EU cardiovascular diseases strategy"
    # with no idea that what admitted it was a passage on marketing food high
    # in fat and sugar to children. Recall moved to the body; the evidence has
    # to move with it, or the judge scores a title that already failed to
    # match. eu_speeches has read ("debate", "excerpt") from the start.
    "eu_texts": ("identifier", ("title", "excerpt")),
    "eu_divisions": ("vote_id", ("label",)),
    "eu_pqs": ("identifier", ("title",)),
    "eu_cmte_docs": ("identifier", ("title",)),
    "eu_judgments": ("item_id", ("case_name", "conclusion")),
    "eu_ecis": ("reg_num", ("title",)),
    "eu_speeches": ("speech_id", ("debate", "excerpt")),
}

# Tables that carry `areas` and are DELIBERATELY not judged, each with
# its reason. The coverage test allows only what is declared here, so a
# new table cannot slip through unjudged AND unexplained -- which is how
# eu_dossiers surfaced: the guard caught it on its first run.
EXEMPT = {
    "eu_dossiers": "hand-curated: every row carries a human-written "
                   "why: line in config/eu_watchlist.yaml, and a model "
                   "line would overwrite a person's judgement with a "
                   "worse one.",
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
        # An inherited division is judged through its text (propagate()),
        # never on its own: 18 Sept 2026, 587 amendment votes queued at once.
        extra = " AND inherited_from IS NULL" if table == "eu_divisions" else ""
        rows = conn.execute(
            "SELECT * FROM {0} WHERE areas != '[]' AND areas IS NOT NULL "
            "AND triage_score IS NULL{1}".format(table, extra)).fetchall()
        for r in rows:
            # Trimmed at 300 characters. The shared judge budgets
            # 400 + 160 tokens per item and the reply may open with a
            # thinking block that spends from the SAME budget; EU rows
            # carry 866-character court conclusions and speech excerpts
            # where Westminster's are terse, and 20 of those overflowed
            # it twice (measured 2026-09-03: 0 and 248 characters
            # returned). A why-line needs the gist, not the passage.
            text = " ".join((r[c] or "") for c in textcols).strip()[:300]
            items.append(triage.TriageItem(
                id="{0}:{1}".format(table, r[key]),
                # Speeches carry neither: the debate name is their title.
                # Without this the judge saw "?" above every speech.
                title=(r["title"] if "title" in r.keys() else None)
                      or (r["label"] if "label" in r.keys() else None)
                      or (r["debate"] if "debate" in r.keys() else None)
                      or "?",
                text=text,
                tier=r["tier"] if "tier" in r.keys() else 2,
                issue_areas=json.loads(r["areas"] or "[]"),
                watchlist_hit=False))
    return items


def propagate(conn):
    """A division that took its areas from an adopted text takes the text's
    score and why-line too, once the text has one. One judgement per text;
    the roll calls under it are its parts, not separate questions."""
    n = conn.execute(
        "UPDATE eu_divisions SET "
        "triage_score = (SELECT t.triage_score FROM eu_texts t WHERE t.identifier = eu_divisions.inherited_from), "
        "why_it_matters = (SELECT t.why_it_matters FROM eu_texts t WHERE t.identifier = eu_divisions.inherited_from) "
        "WHERE inherited_from IS NOT NULL AND triage_score IS NULL AND EXISTS ("
        "SELECT 1 FROM eu_texts t WHERE t.identifier = eu_divisions.inherited_from "
        "AND t.triage_score IS NOT NULL)").rowcount
    conn.commit()
    return n


def apply(conn, results):
    for res in results:
        table, key = res.id.split(":", 1)
        keycol = SOURCES[table][0]
        conn.execute(
            "UPDATE {0} SET triage_score = ?, why_it_matters = ? "
            "WHERE {1} = ?".format(table, keycol),
            (res.score, res.why_it_matters or None, key))
    conn.commit()
    propagate(conn)


def rescore(conn, ref):
    """Put ONE row back in the queue, on a human's say-so.

    Scores are written once, ever, so a wrong one stands until somebody
    asks. 18 Sept 2026: the judge marked the statement on Nicaraguan
    political prisoners unrelated while the adopted text on the same case
    matched freedom of religion. `ref` is table:key as the judge's item id.
    """
    table, key = ref.split(":", 1)
    if table not in SOURCES:
        raise SystemExit("unknown table {0}; one of {1}".format(table, ", ".join(SOURCES)))
    keycol = SOURCES[table][0]
    n = conn.execute("UPDATE {0} SET triage_score = NULL, why_it_matters = NULL "
                     "WHERE {1} = ?".format(table, keycol), (key,)).rowcount
    conn.commit()
    print("eu-triage: {0} row(s) re-queued for {1}".format(n, ref))
    return n


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    ensure_columns(conn)
    if "--rescore" in sys.argv:
        for ref in sys.argv[sys.argv.index("--rescore") + 1:]:
            if ref.startswith("--"):
                break
            rescore(conn, ref)
    carried = propagate(conn)
    if carried:
        print("eu-triage: {0} inherited division(s) took their text's score.".format(carried))
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
        # Slices of EIGHT, not the shared batch of 20: same reason as the
        # text trim above -- less content per call leaves the reply room
        # to answer. A slice that fails twice is skipped and its rows stay
        # unscored for next week rather than taking the run down.
        results, mode = [], "live"
        # FOUR, not eight. The halving fallback works -- the 2026-09-04
        # run scored all 46 new rows -- but it paid five wasted calls to
        # get there: two chunks of eight failed twice each before
        # splitting. EU rows are long enough that eight is the wrong
        # opening bid, and a chunk that still overflows halves to two and
        # then one exactly as before.
        SLICE = 4

        def score_chunk(chunk, depth=0):
            """Score a chunk, HALVING it on failure down to singles.

            Measured 2026-09-03: slices of eight mostly succeed, but one
            fat slice (long court conclusions) overflowed the reply
            budget on both attempts and stalled eight rows. Halving turns
            that into progress -- four, then two, then one -- and only a
            single item that still fails is left for next week.
            """
            for attempt in (1, 2):
                try:
                    return triage.score_live(
                        chunk, api_key=api_key,
                        usage_sink=lambda usage, model: spend.record(
                            conn, "eu-triage", model, usage, dated=today))
                except Exception as exc:
                    print("  [gap] triage chunk of {0} attempt {1}: {2}"
                          .format(len(chunk), attempt, exc))
            if len(chunk) == 1:
                print("  [gap] one row still refuses; left for next run: "
                      "{0}".format(chunk[0].id))
                return []
            half = len(chunk) // 2
            return (score_chunk(chunk[:half], depth + 1)
                    + score_chunk(chunk[half:], depth + 1))

        for start in range(0, len(items), SLICE):
            results.extend(score_chunk(items[start:start + SLICE]))
        if not results:
            results = None
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
