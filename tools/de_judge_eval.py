#!/usr/bin/env python3
"""The GERMAN judge's evaluation corpus.

    python3 tools/de_judge_eval.py seed      # bank the scores already stored
    python3 tools/de_judge_eval.py sample --week 2026-09-21
    python3 tools/de_judge_eval.py report

Christopher, 24 September 2026: build judge evaluation. The German stack is
the least verified thing this repo runs -- an AI-drafted taxonomy no German
speaker has checked, matched by machinery built for English, judged by a
model briefed in English over untranslated text. Three layers of unexamined
judgement, and until now nothing measured any of them.

IT WAS WORSE THAN A MISSING TOOL. tools/de_triage.py never called evalbank at
all, so every German verdict since the taxonomy was written existed ONLY as a
score on its row: no record of what the judge saw, which prompt produced it,
or whether anyone agreed. The bank held 202 Westminster PQs and nothing
German. A German evaluation tool built on that would have measured an empty
set and reported perfect agreement.

SAME CORPUS, SEPARATE FIGURES. The verdicts live in the one judge_verdicts
table -- a parallel German bank would be invisible to the report that matters
-- but agreement is reported PER JURISDICTION and never pooled. Westminster,
the EU and Germany run different prompts over different taxonomies; one
number across all three would describe none of them, and would flatter
Germany, which has a fraction of the labelled rows.

Ten a week is a habit; a hundred labels is a corpus. The human verdict is the
truth here and the judge is what is measured -- concordance is agreement, not
correctness.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, evalbank, triage  # noqa: E402

JURISDICTION = "Germany"
REVIEWS = os.path.join(ROOT, "reviews")

# Every German table the judge scores, with the column its verdict lives in.
# Kept beside tools/de_triage.SOURCES rather than imported so a seed can run
# against a store whose collector set has since changed.
SCORED = {
    "de_vorgaenge": ("vorgang_id", "titel"),
    "de_documents": ("doc_id", "titel"),
    "de_divisions": ("vote_id", "label"),
    "de_agenda": ("item_id", "title"),
    # speaker AND excerpt -- see _title.
    "de_speeches": ("speech_id", "speaker"),
    "de_petitions": ("petition_id", "title"),
    "de_judgments": ("case_no", "subject"),
    "de_amendments": ("doc_id", "titel"),
    "de_committee_reports": ("doc_id", "titel"),
}


def _title(row, titlecol, keys):
    """What the reviewer will see. For a speech that is the speaker AND the
    passage: a name alone cannot be checked against a verdict, and the
    sample file is the whole reason these are banked."""
    base = (row[titlecol] if titlecol in keys else None) or "?"
    if "excerpt" in keys and titlecol == "speaker":
        said = " ".join((row["excerpt"] or "").split())[:120]
        if said:
            return "{0}: {1}".format(base, said)
    return base


def week_of(iso):
    d = datetime.date.fromisoformat(iso[:10])
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


def seed(conn, log=print):
    """Bank every German verdict already in the store, once.

    mode='historic': these were scored before banking existed, so the
    live/stub distinction was never recorded. They are sampled but flagged,
    exactly as the Westminster seed does -- pretending they were live
    verdicts would put unearned confidence into the corpus.
    """
    evalbank.ensure_table(conn)
    n = skipped = 0
    for table, (key, titlecol) in SCORED.items():
        try:
            rows = conn.execute(
                "SELECT * FROM {0} WHERE triage_score IS NOT NULL".format(table)
            ).fetchall()
        except Exception:                                   # noqa: BLE001
            continue                    # a table this store predates
        for r in rows:
            keys = r.keys()
            stamp = None
            for col in ("last_seen", "first_seen", "captured_at", "read_on"):
                if col in keys and r[col]:
                    stamp = r[col]
                    break
            if not stamp:
                skipped += 1
                continue
            item_id = "{0}:{1}".format(table, r[key])
            conn.execute(
                "INSERT INTO judge_verdicts (week, item_id, feed, title, "
                "tier, candidate_areas, watchlist_hit, score, why, areas, "
                "model, prompt_sha, mode, captured_at) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                # DO NOTHING on anything a human has touched: the seed is a
                # floor, never a source of truth. A title correction is
                # allowed on rows nobody has judged yet.
                "ON CONFLICT(week, item_id) DO UPDATE SET "
                "title=excluded.title WHERE judge_verdicts.human_score IS NULL",
                (week_of(stamp), item_id, table,
                 _title(r, titlecol, keys),
                 r["tier"] if "tier" in keys else 2,
                 r["areas"] if "areas" in keys else "[]", 0,
                 r["triage_score"],
                 (r["why_it_matters"] if "why_it_matters" in keys else "") or "",
                 r["areas"] if "areas" in keys else "[]",
                 triage.TRIAGE_MODEL,
                 evalbank.prompt_sha(triage.SYSTEM_PROMPT_DE),
                 "historic", stamp))
            n += 1
    conn.commit()
    log("de-judge-eval: {0} German verdict(s) banked as historic{1}.".format(
        n, "" if not skipped else
        ", {0} skipped with no date to file them under".format(skipped)))
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("seed", "sample", "report"))
    ap.add_argument("--week", help="ISO Monday, for sample")
    ap.add_argument("--write", action="store_true",
                    help="report: also write docs/judge-eval.md")
    args = ap.parse_args()

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    if args.command == "seed":
        seed(conn)
    elif args.command == "sample":
        week = args.week or week_of(datetime.date.today().isoformat())
        if not os.path.isdir(REVIEWS):
            os.makedirs(REVIEWS)
        path = os.path.join(REVIEWS, "de-judge-sample-{0}.md".format(week))
        written, n = evalbank.write_sample(conn, week, path,
                                           jurisdiction=JURISDICTION,
                                           exclude_hidden=True)
        if not written:
            print("de-judge-eval: no German verdict banked for w/c {0}. Run "
                  "seed, or wait for a triage pass.".format(week))
        else:
            print("de-judge-eval: {0} verdict(s) for review -> {1}".format(
                n, os.path.relpath(written, ROOT)))
    else:
        out = evalbank.report(conn, write_to=(
            os.path.join(ROOT, "docs", "judge-eval.md") if args.write else None))
        print(out if isinstance(out, str) else "")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
