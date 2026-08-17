"""Review queue: language we did not think to list.

    python3 tools/un_emerging.py              # scan the store
    python3 tools/un_emerging.py --area 5     # one area
    python3 tools/un_emerging.py --df 2       # quieter, blinder

Builds a baseline from everything already harvested -- thousands of UPR
recommendations plus every stored draft -- and reports, for documents that
ALREADY match one of our areas, the phrases the rest of the corpus has barely
seen. That is emerging language without a list to maintain.

Also reports rights-claim escalation: a sentence that asserts a right AND
mentions one of our terms. "States should consider" becoming "the right to" is
the event, and it is structural rather than lexical.

A REVIEW QUEUE, not an alert feed. Most novel phrasing is drafting variation,
so the discard count is printed: a queue that hides what it dropped is the
thing this codebase keeps having to design against.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, emerging, filter as filt


def area_terms(tax, areas):
    """The configured terms for the given areas, for co-occurrence checks."""
    out = []
    for area in areas:
        for tier in (tax.terms.get(area) or {}).values():
            out.extend(term for term, _p, _cs, _g in tier)
    return [t.rstrip("*") for t in out]


def main():
    want = None
    if "--area" in sys.argv:
        want = int(sys.argv[sys.argv.index("--area") + 1])
    max_df = int(sys.argv[sys.argv.index("--df") + 1]) if "--df" in sys.argv else 1

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "un-taxonomy.yaml"))

    # Baseline over EVERYTHING, on-topic or not: normality is defined by the
    # whole corpus, not by the subset we already care about.
    corpus = [r["text"] for r in conn.execute(
        "SELECT text FROM upr_recommendations WHERE text IS NOT NULL")]
    corpus += [" ".join(filter(None, (r["title"], r["instruction"])))
               for r in conn.execute("SELECT title, instruction FROM un_documents")]
    baseline = emerging.build_baseline(corpus)
    print("baseline: {0} documents, {1} distinct phrases".format(
        len(corpus), len(baseline)))

    # Only documents already on our ground: novel language matters where it
    # lands near our issues, not everywhere in the UN.
    docs = [r for r in conn.execute(
        "SELECT symbol, title, subject, instruction, areas, url FROM un_documents "
        "WHERE areas IS NOT NULL AND areas != '[]'")]
    scanned = flagged = discarded = 0
    print()
    for row in docs:
        areas = json.loads(row["areas"] or "[]")
        if want is not None and want not in areas:
            continue
        scanned += 1
        # Title and instruction only. `subject` still holds a run-on from an
        # older parse for some rows, and scanning it buried real findings under
        # sponsor lists.
        text = " ".join(filter(None, (row["title"], row["instruction"])))
        novel = emerging.longest_novel(text, baseline, max_df=max_df)
        claims = emerging.rights_claims(text, area_terms(tax, areas))
        if not novel and not claims:
            discarded += 1
            continue
        flagged += 1
        print("{0}  areas {1}".format(row["symbol"],
                                      ",".join(str(a) for a in areas)))
        print("    {0}".format((row["title"] or row["subject"] or "")[:66]))
        for phrase in novel:
            print("    NEW PHRASE   {0}".format(phrase[:64]))
        for sentence, terms in claims:
            print("    RIGHTS CLAIM {0}".format(sentence[:64]))
            print("                 near: {0}".format(", ".join(terms)))

    print("\n{0} document(s) scanned, {1} raised something, {2} had nothing new"
          .format(scanned, flagged, discarded))
    print("Tuning: --df {0} was used. A higher --df is quieter and blinder; "
          "this is a queue to read, not an alert.".format(max_df))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
