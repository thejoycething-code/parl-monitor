"""Measure whether a candidate taxonomy term would actually add anything.

    python3 tools/find_taxonomy_gaps.py "hate crime" "kinship care"

A raw corpus count is NOT a gap. "gender recognition" appears in 336 ledger
rows and every one is ALREADY matched, by "Gender Recognition Act" or
"gender recognition certificate"; adding the bare phrase would buy nothing
and widen the triage bill. The same held for freedom of religion (256 rows,
0 unmatched), safeguarding (107, 0), embryo (59, 0) and trans women (20, 0).

So the number that matters is rows containing the phrase that NOTHING in the
taxonomy or watchlist currently matches. This prints that, with an example,
so a term is added on evidence rather than on the impression a big count
gives. Free and offline -- it reads the store, never a source API.

The one real find this method produced: "freedom of speech" had 2,398 rows
and matched nothing, because "free speech" and "freedom of expression" were
both terms and neither is a substring of the commonest phrasing.
"""

from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt

SOURCES = (
    ("mp_events", "COALESCE(excerpt,'')||' '||COALESCE(line,'')"),
    ("sp_items", "body"),
    ("sd_items", "body"),
    ("ni_items", "body"),
)


def gap(conn, tax, wl, term):
    rows = []
    for table, expr in SOURCES:
        try:
            rows += [r[0] for r in conn.execute(
                "SELECT {0} FROM {1} WHERE LOWER({0}) LIKE ?".format(expr, table),
                ("%" + term.lower() + "%",))]
        except sqlite3.OperationalError:
            continue
    missed = [t for t in rows if not filt.filter_item(tax, wl, t or "").matched()]
    return rows, missed


def main():
    terms = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not terms:
        print(__doc__)
        return 1
    conn = sqlite3.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    print("{0:<30}{1:>7}{2:>11}  verdict".format("term", "rows", "unmatched"))
    for term in terms:
        rows, missed = gap(conn, tax, wl, term)
        pct = 100 * len(missed) / max(len(rows), 1)
        verdict = ("nothing to add" if not missed
                   else "WORTH ADDING" if len(missed) >= 20
                   else "marginal")
        print("{0:<30}{1:>7}{2:>11}  {3} ({4:.0f}%)".format(
            term, len(rows), len(missed), verdict, pct))
        if missed:
            text = " ".join((missed[0] or "").split())
            i = text.lower().find(term.lower())
            print("      e.g. ...{0}".format(text[max(0, i - 60):i + 80]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
