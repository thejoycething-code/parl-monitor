"""Sanity-check buffer-zone matches in the ledger and drop the false positives.

    python3 tools/clean_buffer_zone_noise.py [--apply]

"buffer zone*" stays a tier-1 abortion term (Christopher, 2026-08-05) because
clinic and hospital buffer zones are exactly what we watch. But the phrase
also appears in pest control, military and territorial contexts, and those
rows were tagging unrelated business into the abortion area.

Because deleting is irreversible and the archived Hansard text is only an
~900-character excerpt, the test is deliberately asymmetric: drop a row only
when its subject is CLEARLY unrelated (agriculture, planning, environment,
military, foreign affairs), and keep anything ambiguous. A stray kept row
adds a little noise; a wrong deletion loses evidence. This rescued three
Police, Crime, Sentencing and Courts Bill speeches whose excerpts never said
"abortion" but which debated clinic buffer zones (new clause 42).

Dry run by default: it prints what it would remove, and only --apply deletes.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, stance

BUFFER_FAMILY = ("buffer zone", "buffer zones")

# Subjects where "buffer zone" is unambiguously about land, water, wildlife
# or territory rather than clinics, hospitals or speech.
DROP_SUBJECTS = re.compile(
    r"bird|pest control|badger|bovine|hedgerow|agricultur|farm|solar|quarr|"
    r"planning|levelling-up|environment|river|oil and gas|firework|"
    r"national park|unesco|diego garcia|chagos|british indian ocean|gaza|"
    r"syria|israel|military base|ceasefire|overseas matters|foreign relations|"
    r"trade agreement|cook islands|mauritius|cyprus|golan|humanitarian law|"
    r"property development|: roads", re.I)


def main():
    apply = "--apply" in sys.argv
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    texts = stance.build_text_map(os.path.join(ROOT, "data", "raw"))

    rows = conn.execute(
        "SELECT rowid, member_id, ref, line, areas FROM mp_events "
        "WHERE line LIKE '%buffer zone%'").fetchall()
    drop, keep = [], 0
    for r in rows:
        subject = re.sub(r"^(Spoke|Voted \w+|Signed EDM|Sponsored EDM):\s*", "",
                         r["line"] or "").split(" (re:")[0].strip()
        if not DROP_SUBJECTS.search(subject):
            keep += 1
            continue
        # Even an unrelated-looking subject stays if the taxonomy matched
        # something beyond the buffer-zone family.
        blob = "{0}\n{1}".format(r["line"] or "", texts.get(r["ref"], ""))
        result = filt.filter_item(tax, wl, blob)
        others = [t for t in (result.matched_terms + result.watchlist_hits)
                  if t.strip('"').rstrip("*").strip().lower() not in BUFFER_FAMILY]
        if others:
            keep += 1
            continue
        drop.append(r)

    subjects = {}
    for r in drop:
        subject = re.sub(r"^(Spoke|Voted \w+|Signed EDM|Sponsored EDM):\s*", "",
                         r["line"] or "").split(" (re:")[0].strip()
        subjects[subject] = subjects.get(subject, 0) + 1
    print("buffer-zone rows: {0} kept, {1} to drop".format(keep, len(drop)))
    for subject, n in sorted(subjects.items(), key=lambda kv: -kv[1])[:25]:
        print("  x{0:<4} {1}".format(n, subject[:80]))

    if not apply:
        print("\ndry run; re-run with --apply to delete these rows")
        return
    conn.executemany("DELETE FROM mp_events WHERE rowid = ?",
                     [(r["rowid"],) for r in drop])
    # Stance rows for refs that no longer have any ledger event are dead weight.
    conn.execute("DELETE FROM stance WHERE ref NOT IN (SELECT ref FROM mp_events)")
    conn.commit()
    print("\ndeleted {0} rows".format(len(drop)))
    conn.close()


if __name__ == "__main__":
    main()
