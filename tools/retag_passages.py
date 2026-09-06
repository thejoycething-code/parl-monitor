"""Re-derive areas and excerpts for existing ledger rows, passage by passage.

    python3 tools/retag_passages.py [--apply] [--kind debate]

Stage 1 of the cross-tagging fix (docs/5ca-notes.md). Long contributions were
filtered as one blob, so any term anywhere tagged the whole speech with that
area -- a knife-crime speech landed on the abortion sheet. This re-filters
each row's archived text passage by passage and rewrites:

  areas    -> only the areas a qualifying passage actually supports
  excerpt  -> the strongest-matching passage, which the 5CA Comments column
              quotes instead of a debate title that may be about something else

Entirely offline (data/raw) and free: no source API traffic, no Claude calls.

Nothing is deleted. Rows with no issue area were admitted by a watchlist
name match alone (Hansard prints members' names constantly, so a name is a
poor relevance signal); they are reported for a capture-rule decision rather
than removed, since they reach no 5CA sheet anyway. Dry run by default.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, stance


def pq_detail_coverage(conn, raw_dir=None):
    """Share of the ledger's PQ ids that have a pq_detail archive."""
    import glob
    raw_dir = raw_dir or os.path.join(ROOT, "data", "raw")
    have = {os.path.basename(p)[len("pq_detail-"):-len(".json.gz")]
            for p in glob.glob(os.path.join(raw_dir, "*", "pq_detail-*.json.gz"))}
    want = {ref.split(":", 1)[1] for (ref,) in conn.execute(
        "SELECT DISTINCT ref FROM mp_events WHERE kind = 'pq'")
        if ref and ref.startswith("pq:")}
    if not want:
        return 1.0
    return len(want & have) / float(len(want))


def main():
    apply = "--apply" in sys.argv
    kind = "debate"
    if "--kind" in sys.argv:
        kind = sys.argv[sys.argv.index("--kind") + 1]

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    print("indexing archived text...")
    texts = stance.build_text_map(os.path.join(ROOT, "data", "raw"))

    rows = conn.execute(
        "SELECT rowid, ref, line, areas FROM mp_events WHERE kind = ?", (kind,)).fetchall()
    # One filter pass per distinct ref; every member's row on the same
    # contribution gets the same areas and excerpt.
    per_ref, updates, name_only = {}, [], []
    narrowed = widened = unchanged = no_text = cleared = 0
    for r in rows:
        ref = r["ref"]
        if ref not in per_ref:
            text = texts.get(ref)
            if not text:
                no_text += 1
                per_ref[ref] = None
            else:
                title = text.split("\n", 1)[0]
                body = text.split("\n", 1)[1] if "\n" in text else ""
                per_ref[ref] = filt.aggregate_passages(
                    filt.match_passages(tax, wl, body, title=title))
        derived = per_ref[ref]
        if derived is None:
            continue
        areas, _terms, excerpt = derived
        if not areas:
            # The re-derivation is authoritative: a row that no longer
            # supports any area has its areas CLEARED, not left stale.
            # Leaving them was what kept mis-tagged rows (a shoplifting
            # question under abortion) alive through a retag. The row itself
            # is kept, renders nowhere, and a future taxonomy fix can
            # re-derive it.
            name_only.append(r)
            if r["areas"] and json.loads(r["areas"]):
                # Previously TAGGED and now supports nothing: the one
                # outcome a reader of this summary must be able to see
                # on its own line, because it is the only one that can
                # take a row off a 5CA sheet.
                cleared += 1
            updates.append((None, excerpt, r["rowid"]))
            continue
        old = json.loads(r["areas"]) if r["areas"] else []
        if len(areas) < len(old):
            narrowed += 1
        elif len(areas) > len(old):
            widened += 1
        else:
            unchanged += 1
        updates.append((json.dumps(areas), excerpt, r["rowid"]))

    print("\n{0} rows over {1} contributions".format(len(rows), len(per_ref)))
    print("  areas narrowed: {0}   widened: {1}   same: {2}".format(
        narrowed, widened, unchanged))
    print("  watchlist-name captures, no issue area (left alone): {0}".format(len(name_only)))
    print("  previously tagged rows that would be CLEARED: {0}".format(cleared))
    print("  no archived text (left alone): {0}".format(no_text))

    print("\nsample of rewritten rows:")
    for areas_json, excerpt, rowid in updates[:5]:
        row = conn.execute("SELECT line, areas FROM mp_events WHERE rowid = ?",
                           (rowid,)).fetchone()
        print("  {0}".format(row["line"][:70]))
        print("     areas {0} -> {1}".format(row["areas"], areas_json))
        print('     excerpt: "{0}"'.format((excerpt or "")[:110]))

    if not apply:
        print("\ndry run; re-run with --apply to write these changes")
        return
    if kind == "pq" and "--force" not in sys.argv:
        # THE PQ ARCHIVE WAS A SNIPPET. data/raw used to hold ~255
        # characters per question (the search payload), so re-derivation
        # would have CLEARED 34 tagged rows whose matching phrase was past
        # the cut -- 23 of them "Religion: Education" tagged via
        # "religious education". Since 2026-09-06 pqs.fetch_question
        # archives the full question and answer, and this refuses only
        # while COVERAGE is short: re-derivation is authoritative when it
        # reads at least what the ingest read, and not before.
        share = pq_detail_coverage(conn)
        if share < 0.95:
            print("\nREFUSING to apply for kind=pq: only {0:.0%} of the "
                  "ledger's questions have a full-text archive, so "
                  "re-derivation would still read stubs and clear {1} "
                  "row(s) whose matching phrase was cut off. Run "
                  "tools/backfill_pq_text.py, or pass --force."
                  .format(share, cleared))
            return
        print("\npq full-text coverage {0:.0%}; applying.".format(share))
    conn.executemany(
        "UPDATE mp_events SET areas = ?, excerpt = ? WHERE rowid = ?", updates)
    conn.commit()
    print("\nrewrote {0} rows; nothing deleted".format(len(updates)))
    conn.close()


if __name__ == "__main__":
    main()
