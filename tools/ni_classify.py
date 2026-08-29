"""Classify NI divisions by the amendment's own wording, from archived Hansard.

    python3 tools/ni_classify.py            # dry run: what would change
    python3 tools/ni_classify.py --apply    # write it
    python3 tools/ni_classify.py --area 5   # look at one area's results

DRY RUN BY DEFAULT, because re-derivation is authoritative: a division that no
longer supports an area has its areas CLEARED, not left stale. That is the
retag_passages.py contract, and it can destroy data if the taxonomy is mid-edit.

OFFLINE. Reads the Hansard archived by tools/ni_divisions.py under data/raw,
so it can be re-run for free every time config/taxonomy.yaml is regenerated --
which is the normal case, since the taxonomy is generated from
docs/keyword-taxonomy.md and must never be hand-edited.

WHY THIS EXISTS AT ALL. A DivisionSubject names an amendment NUMBER, never its
content, and is truncated at 100 characters, so `ni_divisions.areas` sat empty
on all 139 rows for a year. Hansard carries the amendment's wording: amendment
97 of the Justice Bill is "Accommodation of women prisoners", which is area 5,
while amendments 79-86 on the same day are "Minimum age of criminal
responsibility" and are correctly nothing of ours.

TWO DELIBERATE DIVERGENCES FROM retag_passages.py, both measured:

  * It classifies with filter_item, NOT match_passages. The passage gate keeps
    only tier-1-or-watchlist passages, which is right for one stray term in a
    3,000-word speech but wrong here: an amendment IS the whole document and it
    is short. Measured -- the gate drops amendment 97 (area 5, tier 2, "Equality
    Act 2010") and amendment 73 (area 7, "blasphemy"), which are precisely the
    interesting ones. split_passages/aggregate_passages are still used, but only
    to pick the excerpt.
  * It never promotes item text into amendment text. A motion's areas standing
    in for an amendment that guts it is the unmarked-fallback bug this codebase
    keeps designing out, so evidence_source is stored and displayed.

Writes only ni_divisions. Never `items`, never `mp_events`.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import HttpClient
from src.ingest import ni_hansard

# The subject's amendment number, used only where the Hansard question line is
# unnumbered ("Question put, That the amendment be made.") -- 4 of 7 divisions
# on 2026-06-30. The question line wins whenever it carries a number.
_SUBJECT_AMD = re.compile(r"Amendment\s*(?:No\s*)?(\d+)", re.I)


def load_filter():
    return (filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml")),
            filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml")))


def watched_names():
    import yaml
    path = os.path.join(ROOT, "config", "ni_watch.yaml")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    return [(b.get("name") or "").strip()
            for b in (cfg.get("bills") or []) if b.get("name")]


def classify(tax, wl, evidence):
    """(areas, terms, excerpt) for one Evidence. See the docstring on why this
    uses filter_item rather than the passage gate."""
    title, body = evidence.classify_fields
    if not body:
        return [], [], None
    res = filt.filter_item(tax, wl, title or "", body, title=title or "")
    if not res.matched():
        return [], [], None
    # Excerpt only: the passage machinery picks the most telling fragment, but
    # a division whose areas came from filter_item must still get an excerpt
    # even when no single passage clears the tier-1 gate.
    _a, _t, excerpt = filt.aggregate_passages(
        filt.match_passages(tax, wl, body, title=title or ""))
    if not excerpt:
        chunks = filt.split_passages(body)
        excerpt = (chunks[0][:260] if chunks else body[:260])
    return res.issue_areas, res.matched_terms, excerpt


def main():
    apply = "--apply" in sys.argv
    want = None
    if "--area" in sys.argv:
        want = int(sys.argv[sys.argv.index("--area") + 1])
    today = datetime.date.today().isoformat()

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax, wl = load_filter()
    watch = watched_names()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))

    rows = [r for r in conn.execute(
        "SELECT doc_id, subject, dated, bill, watched, areas FROM ni_divisions "
        "WHERE dated IS NOT NULL ORDER BY dated DESC, doc_id")]
    by_date = {}
    for r in rows:
        by_date.setdefault(r["dated"], []).append(r)
    print("{0} division(s) over {1} sitting date(s)".format(
        len(rows), len(by_date)))

    scoped = on_amd = with_amd = with_item = no_text = 0
    narrowed = widened = unchanged = 0
    updates, gaps, hits = [], [], []

    for day, drows in sorted(by_date.items(), reverse=True):
        # Archive first, network only if absent -- see ni_hansard.sitting.
        sitting, err = ni_hansard.sitting(
            client, os.path.join(ROOT, "data", "raw"), day)
        if err or sitting is None:
            gaps.append("hansard {0}: {1}".format(day, err or "no sitting"))
            continue
        hints = {}
        for r in drows:
            m = _SUBJECT_AMD.search(r["subject"] or "")
            if m:
                hints[r["doc_id"]] = int(m.group(1))
        evs, day_gaps = ni_hansard.evidence_for(
            sitting, [r["doc_id"] for r in drows], hints=hints)
        gaps.extend(day_gaps)
        index = {r["doc_id"]: r for r in drows}
        for ev in evs:
            row = index.get(ev.doc_id)
            if row is None:
                continue
            if ev.item_id or ev.item_name:
                scoped += 1
            if ev.on_amendment:
                on_amd += 1
            if ev.source == ni_hansard.AMENDMENT_TEXT:
                with_amd += 1
            elif ev.source == ni_hansard.ITEM_ONLY:
                with_item += 1
            else:
                no_text += 1
            areas, terms, excerpt = classify(tax, wl, ev)
            before = json.loads(row["areas"] or "[]")
            if set(areas) == set(before):
                unchanged += 1
            elif len(areas) < len(before):
                narrowed += 1
            else:
                widened += 1
            updates.append((
                json.dumps(sorted(areas)) if areas else None,
                json.dumps(terms) if terms else None,
                ev.item_id or None, ev.item_name or None, ev.amendment_no,
                1 if ev.on_amendment else 0,
                ev.amendment_text or ev.item_text or None,
                ev.source, excerpt, today, ev.doc_id))
            if areas and (want is None or want in areas):
                hits.append((day, ev, row, areas, terms, excerpt))

    print("  scoped to a Hansard item   {0:>4}   (ParentComponentId -> Header)"
          .format(scoped))
    print("  on an amendment            {0:>4}   (per the 'Question put' line)"
          .format(on_amd))
    print("  amendment text recovered   {0:>4}".format(with_amd))
    print("  item text only             {0:>4}".format(with_item))
    print("  no text                    {0:>4}".format(no_text))
    print("  areas derived              {0:>4}   narrowed {1}  widened {2}  "
          "unchanged {3}".format(len(hits) if want is None else len(hits),
                                 narrowed, widened, unchanged))

    unwatched = 0
    for day, ev, row, areas, terms, excerpt in hits:
        watched = bool(row["watched"])
        mark = "WATCHED" if watched else "       "
        if not watched:
            unwatched += 1
        print("\n  {0}  {1}  {2}  areas {3}  {4}".format(
            day, ev.doc_id, mark, areas, ",".join(terms[:3])))
        print("      {0}  (item {1})".format(
            (ev.item_name or row["bill"] or "?")[:60], ev.item_id or "?"))
        label = ("amendment {0}".format(ev.amendment_no)
                 if ev.amendment_no is not None else ev.source)
        print("      {0}: {1}".format(label, (excerpt or "")[:118]))
        if not watched:
            print("      NOT IN config/ni_watch.yaml -- no member votes are "
                  "held for this division.")

    if unwatched:
        print("\n  {0} classified division(s) sit on bills NOT in "
              "config/ni_watch.yaml.".format(unwatched))
        print("  That is the feedback loop: add one with a `why` line and "
              "tools/ni_divisions.py\n  will harvest its member votes.")

    if gaps:
        print("\n{0} gap(s) -- printed, never swallowed:".format(len(gaps)))
        for g in gaps[:12]:
            print("  * {0}".format(g[:104]))
        if len(gaps) > 12:
            print("  ...and {0} more".format(len(gaps) - 12))
        # The PRINT stops at 12; the table takes all of them. That gap
        # between what a log shows and what happened is the reason for
        # persisting at all.
        if apply:
            db.record_gaps(conn, "ni-classify", gaps)

    if not apply:
        print("\ndry run; {0} row(s) would be written. Re-run with --apply."
              .format(len(updates)))
        conn.close()
        return 0

    conn.executemany(
        "UPDATE ni_divisions SET areas = ?, matched_terms = ?, item_id = ?, "
        "item_name = ?, amendment_no = ?, on_amendment = ?, evidence = ?, "
        "evidence_source = ?, excerpt = ?, classified_at = ? WHERE doc_id = ?",
        updates)
    conn.commit()
    print("\n{0} row(s) written.".format(len(updates)))
    print("Read it with: python3 tools/ni_monitor.py")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
