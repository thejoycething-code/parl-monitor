"""Prune superseded 5CA snapshots from data/5ca.

    python3 tools/prune_5ca.py            # dry run (default)
    python3 tools/prune_5ca.py --apply    # delete

Every Monday regenerates a full set of dated sheets, so data/5ca reached
41MB across 105 files. NOTHING reads them programmatically -- every code
reference is a write or a docstring pointing a human at the directory --
so old sets are superseded copies, not inputs.

What is kept, per sheet kind:

  * the NEWEST set -- the current 5CA, the whole point of the directory;
  * the OLDEST set -- the baseline, which is genuinely unregenerable now
    that the store is a single rolling release asset rather than 161
    committed versions;
  * the LAST set of each earlier calendar month -- a monthly spine for the
    movement-detection work on the vision list.

Everything else is an intra-week duplicate. Deletions are recoverable from
git history (these files are tracked), but this defaults to a dry run all
the same, and it prints every file it would remove rather than a count --
a silent prune is how a real record disappears.
"""

from __future__ import annotations

import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEETS = os.path.join(ROOT, "data", "5ca")
DATED = re.compile(r"^(?P<kind>.+?)-?(?P<date>\d{4}-\d{2}-\d{2})\.csv$")


def plan(names):
    """(keep, drop) filenames. Pure, so the tests can drive it directly."""
    by_kind = collections.defaultdict(list)
    unmatched = []
    for name in sorted(names):
        m = DATED.match(name)
        if not m:
            unmatched.append(name)
            continue
        by_kind[m.group("kind")].append((m.group("date"), name))

    keep = set(unmatched)          # anything undated is kept, never guessed
    for _kind, dated in by_kind.items():
        dated.sort()
        keep.add(dated[-1][1])                      # newest
        keep.add(dated[0][1])                       # baseline
        last_of_month = {}
        for date, name in dated:
            last_of_month[date[:7]] = name          # sorted, so last wins
        current = dated[-1][0][:7]
        for month, name in last_of_month.items():
            if month != current:                    # the current month's
                keep.add(name)                      # spine is the newest
    drop = [n for n in sorted(names) if n not in keep]
    return sorted(keep), drop


def main():
    apply = "--apply" in sys.argv
    if not os.path.isdir(SHEETS):
        print("no data/5ca directory")
        return 1
    names = [n for n in os.listdir(SHEETS) if n.endswith(".csv")]
    keep, drop = plan(names)
    size = lambda n: os.path.getsize(os.path.join(SHEETS, n))

    print("{0} sheet(s) in data/5ca; keeping {1}, dropping {2}.".format(
        len(names), len(keep), len(drop)))
    print("\nKEEPING (newest + baseline + monthly spine):")
    for n in keep:
        print("  {0:>7.1f} KB  {1}".format(size(n) / 1024, n))
    print("\nDROPPING (superseded intra-week duplicates):")
    freed = 0
    for n in drop:
        freed += size(n)
        print("  {0:>7.1f} KB  {1}".format(size(n) / 1024, n))
    print("\n{0:.1f} MB freed of {1:.1f} MB.".format(
        freed / 1e6, sum(size(n) for n in names) / 1e6))

    if not apply:
        print("\ndry run; re-run with --apply to delete. Recoverable from git "
              "history either way.")
        return 0
    for n in drop:
        os.remove(os.path.join(SHEETS, n))
    print("\n{0} file(s) deleted.".format(len(drop)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
