"""Devolved triage: the why-line the nations never had.

    python3 tools/devolved_triage.py            # recent items + all divisions
    python3 tools/devolved_triage.py --all      # the full backlog

Westminster items have been judged since the pipeline began and the EU
since 2026-09-01; Holyrood, the Senedd and the Assembly never were.
Their rows carried a taxonomy match and nothing else -- no score, no
"why it matters" -- so a devolved section could say WHAT happened but
never why it mattered (measured 2026-09-04: sp_items, sd_items and
ni_items had no triage_score column at all).

Scope, and why it is not everything. 1,753 devolved rows carry a
taxonomy match going back years, and judging the lot would be ~520 API
calls for history nothing renders. The default window is what the
monitors actually show: items from the last 90 days, plus EVERY division
on our ground whatever its date, because a division is judged once and
then read for as long as the member sits. --all does the backlog when
someone wants it.

Same judge as Westminster and the EU: same rubric, same model, the
shared slicer in src/triage.py, scored once ever, spend recorded under
pass 'devolved-triage'.

Separation guarantee: writes triage_score/why_it_matters on sp_/sd_/ni_
and dg_ tables only -- never items or mp_events.
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

WINDOW_DAYS = 90

# table -> (key column, date column or None, text columns for the judge)
SOURCES = {
    "sp_items": ("id", "dated", ("title", "body")),
    "sd_items": ("id", "dated", ("title", "body")),
    "ni_items": ("id", "dated", ("title", "body")),
    "dg_consultations": ("key", None, ("title", "summary")),
    # Divisions carry no date filter: a verdict is read for years.
    "sp_divisions": ("key", None, ("title",)),
    "sd_divisions": ("key", None, ("title",)),
    "ni_divisions": ("event_id", None, ("subject", "excerpt")),
}

# AMENDMENT divisions are excluded from triage, and the reason is the
# standing one. Their question is not in the record -- Holyrood's own
# scorer says so of 215 Stage 3 votes on the assisted dying Bill, and 78
# of 83 NI amendment divisions have no amendment text under the item id
# on the day. The judge sees only the BILL title, so it writes a line
# about the Bill; attached to "Amendment 47" that reads as what the
# amendment meant, which is the Lords inversion wearing a why-line.
# Found 2026-09-04 after a first run gave 268 Scottish divisions a score,
# 219 of them Stage 3 amendments on one Bill; those lines were cleared.
AMENDMENT_FILTER = {
    "sp_divisions": "(amendment_no IS NULL OR amendment_no = '')",
    "ni_divisions": "(amendment_no IS NULL OR amendment_no = '')",
    "sd_divisions": "title NOT LIKE '%Amendment%'",
}


def columns_of(conn, table):
    return [c[1] for c in conn.execute(
        "PRAGMA table_info({0})".format(table))]


def ensure_columns(conn):
    for table in SOURCES:
        cols = columns_of(conn, table)
        if not cols:
            continue          # table absent in this store; skip silently
        for col, typ in (("triage_score", "INTEGER"),
                         ("why_it_matters", "TEXT")):
            if col not in cols:
                conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(
                    table, col, typ))
    conn.commit()


def pending(conn, everything=False, today=None):
    today = today or datetime.date.today().isoformat()
    cutoff = (datetime.date.fromisoformat(today)
              - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    items = []
    for table, (key, datecol, textcols) in SOURCES.items():
        cols = columns_of(conn, table)
        if not cols or key not in cols:
            continue
        where = ["areas NOT IN ('', '[]')", "areas IS NOT NULL",
                 "triage_score IS NULL"]
        params = []
        if datecol and datecol in cols and not everything:
            where.append("{0} >= ?".format(datecol))
            params.append(cutoff)
        if table in AMENDMENT_FILTER:
            where.append(AMENDMENT_FILTER[table])
        rows = conn.execute("SELECT * FROM {0} WHERE {1}".format(
            table, " AND ".join(where)), params).fetchall()
        for r in rows:
            keys = r.keys()
            text = " ".join((r[c] or "") for c in textcols
                            if c in keys).strip()[:300]
            title = None
            for cand in ("title", "subject", "short", "label"):
                if cand in keys and r[cand]:
                    title = r[cand]
                    break
            items.append(triage.TriageItem(
                id="{0}:{1}".format(table, r[key]),
                title=title or "?", text=text,
                tier=r["tier"] if "tier" in keys else 2,
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


def api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    path = os.path.join(ROOT, "config", "secrets.yaml")
    if os.path.exists(path):
        import yaml
        return (yaml.safe_load(open(path)) or {}).get("anthropic_api_key")
    return None


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    ensure_columns(conn)
    everything = "--all" in sys.argv
    items = pending(conn, everything=everything)
    if not items:
        print("devolved-triage: nothing unscored.")
        return 0
    today = datetime.date.today().isoformat()
    key = api_key()
    if not key and "--allow-stub" not in sys.argv:
        # Scores are written ONCE, EVER. A keyless run would freeze
        # tier-derived stubs with empty why-lines into every row and no
        # later run would revisit them -- so an unattended workflow that
        # simply lacks the secret would quietly destroy the judgement it
        # was meant to make. Refuse instead, and leave the rows for a run
        # that can actually judge them. --allow-stub is the deliberate
        # offline path, for tests and for working without the key.
        print("devolved-triage: no ANTHROPIC_API_KEY, so {0} item(s) are "
              "left UNSCORED for a run that can judge them. Pass "
              "--allow-stub to write tier-derived stub scores instead "
              "(they are permanent).".format(len(items)))
        conn.close()
        return 0
    if not key:
        results = triage.score_stub(items)
        mode = "stub (no API key; why lines empty, scores tier-derived)"
    else:
        results = triage.score_in_slices(
            items, key,
            on_usage=lambda usage, model: spend.record(
                conn, "devolved-triage", model, usage, dated=today))
        mode = "live"
    apply(conn, results)
    print("devolved-triage: {0} of {1} item(s) scored ({2}).".format(
        len(results), len(items), mode))
    by_table = {}
    for res in results:
        by_table.setdefault(res.id.split(":", 1)[0], []).append(res)
    for table, rows in sorted(by_table.items()):
        threes = [r for r in rows if r.score == 3]
        print("  {0:18} {1:4} scored, {2} at score 3".format(
            table, len(rows), len(threes)))
        for r in threes[:2]:
            print("      {0}".format((r.why_it_matters or "")[:88]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
