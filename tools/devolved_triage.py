"""Devolved triage: the why-line the nations never had.

    tools/session_judge.sh tools/devolved_triage.py 60 20   # the FREE judge (Mac Mini, plan allowance)
    python3 tools/devolved_triage.py --queue-out /tmp/q.md --limit 20
    python3 tools/devolved_triage.py --queue-in /tmp/q.md
    python3 tools/devolved_triage.py --pending
    UK_PAID_JUDGE=1 python3 tools/devolved_triage.py        # the paid API judge, opt-in only
    UK_PAID_JUDGE=1 python3 tools/devolved_triage.py --all  # the full backlog, paid

PAID AI OFF BY DEFAULT (round 3, Chris, 16 October 2026). The Monday
publish used to call this with the API key whenever one was set. Now the
default route is the free session judge (--queue-out / --queue-in through
tools/session_judge.sh, in jobs/uk-session-judge.sh on Sundays and a
catch-up in run_monday.py); the API path runs only with UK_PAID_JUDGE=1. A
plain run without the flag scores nothing and says so.

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


QUEUE_MARKER = "<!-- devolved-session-queue v1 -->"
PAID_JUDGE_FLAG = "UK_PAID_JUDGE"


def paid_judge_opted_in():
    return os.environ.get(PAID_JUDGE_FLAG, "").strip() == "1"


def _db_path():
    name = os.environ.get("PARL_DB") or "parl-monitor.db"
    if "--db" in sys.argv:
        name = sys.argv[sys.argv.index("--db") + 1]
    return name if os.path.isabs(name) else os.path.join(ROOT, "data", name)


def _ordered(items):
    """Divisions first (a verdict is read for years), then the rest."""
    return sorted(items, key=lambda i: (0 if "divisions" in i.id else 1, i.id), reverse=False)


def queue_out(conn, path, limit, today, log=print):
    from src import session_queue
    items = _ordered(pending(conn, today=today))
    chosen = items[:max(0, limit)]
    n = session_queue.write_queue(path, chosen, "Devolved judge queue, {0}".format(today),
                                  QUEUE_MARKER, triage.SYSTEM_PROMPT)
    log("devolved-triage: session queue: {0} item(s) written to {1}; {2} unscored in the window.".format(
        n, path, len(items)))
    return n


def queue_in(conn, path, today, log=print):
    from src import session_queue
    results, refused, blank = session_queue.read_queue(path, QUEUE_MARKER)
    if refused and refused[0][0] == "(file)":
        log("  [gap] session queue {0} refused: {1}".format(path, refused[0][1]))
        return None
    known = {i.id: i for i in pending(conn, everything=True, today=today)}
    good = []
    for res in results:
        if res.id not in known:
            refused.append((res.id, "not an unscored devolved row"))
            continue
        good.append(triage.TriageResult(id=res.id, score=res.score, areas=list(known[res.id].issue_areas),
                                        why_it_matters=res.why, stub=False))
    apply(conn, good)
    session_queue.record(conn, "devolved", good, today)
    for iid, why in refused:
        log("  [gap] queue item refused: {0}: {1}".format(iid, why))
    log("devolved-triage: session queue: {0} item(s) scored, {1} refused, {2} left blank".format(
        len(good), len(refused), len(blank)))
    return len(good)


def main():
    conn = db.init_db(db.connect(_db_path()))
    ensure_columns(conn)
    today = datetime.date.today().isoformat()
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 20
    if "--queue-out" in sys.argv:
        queue_out(conn, sys.argv[sys.argv.index("--queue-out") + 1], limit, today)
        return 0
    if "--queue-in" in sys.argv:
        return 1 if queue_in(conn, sys.argv[sys.argv.index("--queue-in") + 1], today) is None else 0
    everything = "--all" in sys.argv
    items = pending(conn, everything=everything)
    if "--pending" in sys.argv:
        print("devolved-triage: {0} unscored row(s) in the window".format(len(items)))
        return 0
    if not items:
        print("devolved-triage: nothing unscored.")
        return 0
    if not paid_judge_opted_in() and "--allow-stub" not in sys.argv:
        print("devolved-triage: the paid judge is off ({0}=1 opts in); {1} item(s) are left for "
              "the free session judge (tools/session_judge.sh tools/devolved_triage.py).".format(
                  PAID_JUDGE_FLAG, len(items)))
        conn.close()
        return 0
    key = api_key() if paid_judge_opted_in() else None
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
        budget = 480
        if "--budget-seconds" in sys.argv:
            budget = int(sys.argv[sys.argv.index("--budget-seconds") + 1])
        results = triage.score_in_slices(
            items, key,
            on_usage=lambda usage, model: spend.record(
                conn, "devolved-triage", model, usage, dated=today),
            budget_seconds=budget)
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
