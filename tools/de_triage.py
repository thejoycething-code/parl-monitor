#!/usr/bin/env python3
"""Score the German monitor's matched rows, once ever.

    python3 tools/de_triage.py
    python3 tools/de_triage.py --rescore de_vorgaenge:12345

Same rubric, model and batching as Westminster and the EU, through
src/triage.py, but with the German frame (triage.SYSTEM_PROMPT_DE): the text
is German and untranslated, the sixteen Land parliaments are in scope, and the
why-line is written in English because the reader is the London team.

Scored once, ever: a row keeps its score, so the weekly cost is the week's NEW
matched rows and nothing else. A wrong score is corrected by a human asking,
with --rescore, never by a rerun.

EVERY de_ table that carries `areas` belongs in SOURCES. A structural test
fails if one is missing, because the EU monitor grew five collectors whose
rows sat unscored while the run cheerfully printed "nothing unscored".

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, spend, triage  # noqa: E402

# table -> (key column, text columns joined for the judge)
SOURCES = {
    # The excerpt travels with the title: a Vorgang title is administrative
    # ("Schriftliche Frage"), and the passage that earned the match is what
    # tells the judge what the item is actually about.
    "de_documents": ("doc_id", ("titel", "excerpt")),
    "de_vorgaenge": ("vorgang_id", ("titel", "sachgebiet")),
    "de_divisions": ("vote_id", ("label",)),
    # The agenda's TITLE is a committee and a sitting number; the excerpt is
    # the agenda point that earned the match, so it is what tells the judge
    # what is actually being sat on.
    "de_agenda": ("item_id", ("title", "excerpt")),
    # The speaker and the passage that matched. The protocol number would
    # tell the judge nothing about what was said.
    "de_speeches": ("speech_id", ("speaker", "excerpt")),
    # A petition's title is a subject line; the excerpt is the passage that
    # earned the match.
    "de_petitions": ("petition_id", ("title", "excerpt")),
    # The court's own description of the case is the substance.
    "de_judgments": ("case_no", ("subject",)),
    # An amendment's own title is procedure, so the BILL it amends is what
    # tells the judge what is at stake.
    "de_amendments": ("doc_id", ("vorgang_titel", "titel")),
    # The report's own title names the bill, so it is the substance; the
    # committee is carried too because who is recommending matters.
    "de_committee_reports": ("doc_id", ("titel", "committee")),
}

# A de_ table with `areas` that is deliberately NOT judged, with the reason.
EXEMPT = {}

SLICE = 4


def ensure_columns(conn):
    for table in SOURCES:
        cols = [c[1] for c in conn.execute("PRAGMA table_info({0})".format(table))]
        for col, kind in (("triage_score", "INTEGER"), ("why_it_matters", "TEXT")):
            if col not in cols:
                conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(table, col, kind))
    conn.commit()


def pending(conn):
    items = []
    for table, (key, textcols) in SOURCES.items():
        # An inherited division is judged through the document it took its
        # ground from, never on its own: one judgement per document, not one
        # per roll call.
        extra = " AND inherited_from IS NULL" if table == "de_divisions" else ""
        rows = conn.execute(
            "SELECT * FROM {0} WHERE areas != '[]' AND areas IS NOT NULL "
            "AND triage_score IS NULL{1}".format(table, extra)).fetchall()
        for r in rows:
            keys = r.keys()
            text = " ".join((r[c] or "") for c in textcols if c in keys).strip()[:300]
            title = (r["titel"] if "titel" in keys else None) or \
                    (r["label"] if "label" in keys else None) or "?"
            items.append(triage.TriageItem(
                id="{0}:{1}".format(table, r[key]), title=title, text=text,
                tier=r["tier"] if "tier" in keys else 2,
                issue_areas=json.loads(r["areas"] or "[]"), watchlist_hit=False))
    return items


def propagate(conn):
    """A division that took its ground from a document takes the document's
    score and why-line too. One judgement per document."""
    n = conn.execute(
        "UPDATE de_divisions SET "
        "triage_score = (SELECT d.triage_score FROM de_documents d "
        "WHERE d.doc_id = de_divisions.inherited_from), "
        "why_it_matters = (SELECT d.why_it_matters FROM de_documents d "
        "WHERE d.doc_id = de_divisions.inherited_from) "
        "WHERE inherited_from IS NOT NULL AND triage_score IS NULL AND EXISTS ("
        "SELECT 1 FROM de_documents d WHERE d.doc_id = de_divisions.inherited_from "
        "AND d.triage_score IS NOT NULL)").rowcount
    conn.commit()
    return n


def rescore(conn, ref):
    """Put ONE row back in the queue, on a human's say-so."""
    table, key = ref.split(":", 1)
    if table not in SOURCES:
        raise SystemExit("unknown table {0}; one of {1}".format(table, ", ".join(SOURCES)))
    n = conn.execute("UPDATE {0} SET triage_score = NULL, why_it_matters = NULL "
                     "WHERE {1} = ?".format(table, SOURCES[table][0]), (key,)).rowcount
    conn.commit()
    print("de-triage: {0} row(s) re-queued for {1}".format(n, ref))
    return n


def apply(conn, results):
    for res in results:
        table, key = res.id.split(":", 1)
        conn.execute("UPDATE {0} SET triage_score = ?, why_it_matters = ? "
                     "WHERE {1} = ?".format(table, SOURCES[table][0]),
                     (res.score, res.why_it_matters or None, key))
    conn.commit()
    propagate(conn)


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    ensure_columns(conn)
    if "--rescore" in sys.argv:
        for ref in sys.argv[sys.argv.index("--rescore") + 1:]:
            if ref.startswith("--"):
                break
            rescore(conn, ref)
    carried = propagate(conn)
    if carried:
        print("de-triage: {0} inherited division(s) took their document's score."
              .format(carried))
    items = pending(conn)
    if not items:
        print("de-triage: nothing unscored.")
        conn.close()
        return 0
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        secrets_path = os.path.join(ROOT, "config", "secrets.yaml")
        if os.path.exists(secrets_path):
            import yaml
            api_key = (yaml.safe_load(open(secrets_path)) or {}).get("anthropic_api_key")
    today = datetime.date.today().isoformat()
    if not api_key:
        print("de-triage: {0} row(s) unscored and no ANTHROPIC_API_KEY; they "
              "stay unscored rather than stub-scored, because scores are "
              "written once ever.".format(len(items)))
        conn.close()
        return 0

    def score_chunk(chunk):
        for attempt in (1, 2):
            try:
                return triage.score_live(
                    chunk, api_key=api_key, system=triage.SYSTEM_PROMPT_DE,
                    usage_sink=lambda usage, model: spend.record(
                        conn, "de-triage", model, usage, dated=today))
            except Exception as exc:                        # noqa: BLE001
                print("  [gap] triage chunk of {0} attempt {1}: {2}"
                      .format(len(chunk), attempt, exc))
        if len(chunk) == 1:
            print("  [gap] one row still refuses; left for next run: {0}"
                  .format(chunk[0].id))
            return []
        half = len(chunk) // 2
        return score_chunk(chunk[:half]) + score_chunk(chunk[half:])

    results = []
    for start in range(0, len(items), SLICE):
        results.extend(score_chunk(items[start:start + SLICE]))
    apply(conn, [r for r in results if r.score is not None])
    print("de-triage: {0} of {1} item(s) scored.".format(len(results), len(items)))
    for res in results[:6]:
        print("  [{0}] {1}".format(res.score, (res.why_it_matters or "")[:96]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
