#!/usr/bin/env python3
"""Mexico's state congresses: what each readable state lists (12 October 2026).

    python3 tools/mxs_collect.py                         # every state with a reader
    python3 tools/mxs_collect.py --state cdmx --state jal
    python3 tools/mxs_collect.py --since 2025-09-01      # how far back to list
    python3 tools/mxs_collect.py --reclassify            # re-derive areas, offline
    python3 tools/mxs_collect.py --dry-run --db /tmp/x.db

SCHEDULED as a step of jobs/mx-collect.sh (the Mexican edition's GitHub job,
fortnightly, X9), after the federal collector and before the edition, under
its own clock (--budget-seconds). It runs on GitHub's runners because
several state hosts, like the federal Chamber's, do not answer UK addresses
(docs/mexico-regions-scope.md, measured 12 October 2026).

ONE MODULE PER STATE (src/ingest/mxs_<state>.py), each exposing
    READER  a one-line description of the source
    collect(ctx, since) -> [item dict]
and the parsers its tests use. An item dict carries state, source_id and
whatever the source gives of: legislature, kind, title, presenter, party,
presented, turno, status, status_date, url (src/mxs_store.py). States with
no reader are recorded in mxs_reads with the reason from NOT_READ, so the
edition says which states were not read and why.

THE FETCH CONTEXT is the provinces' (src/prov_fetch.Context): the shared
HttpClient with the honest CitizenGO User-Agent and contact, at least 1.1 s
between requests to a host, robots.txt HONOURED (a disallowed URL is never
requested and is a gap; a Crawl-delay raises that host's interval), the
run's clock, and gaps gathered and written once through db.record_gaps.

CLASSIFICATION: config/taxonomy-es.yaml for country 'mx' with the accent
fold the federal collector uses (tools/mx_rollcalls.classify), plus
config/watchlist-mx-states.yaml by item key. Every listed item is stored,
on our ground or not, so --reclassify works offline.

Exit status 3 when it stored what it could and recorded gaps (as
tools/mx_rollcalls.py does; jobs/mx-collect.sh treats 3 as green).
ONE WRITER AT A TIME on the store. Separation guarantee: writes mxs_* and
the shared gaps table and its own source_runs heartbeat only.
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, drain, mxs_store  # noqa: E402
from src.http import HttpClient  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FEED = "mx-states"
HEARTBEAT = "MX states"
BUDGET_S = 900.0
# How far back a first read lists: the start of the 2025-26 legislative year.
DEFAULT_SINCE = "2025-09-01"

# state -> module under src/ingest/. Ordered by CitizenGO relevance and size.
READERS = {
    "mex": "mxs_mex",        # Estado de México: one list, the page's own XHR reply
    "cdmx": "mxs_cdmx",      # Ciudad de México: the citizen portal, newest first
    "chis": "mxs_chis",      # Chiapas: one table, stage documents per row
    "oax": "mxs_oax",        # Oaxaca: one table per legislative year
    "chih": "mxs_chih",      # Chihuahua: listing pages, newest first
    "bc": "mxs_bc",          # Baja California: one table, outcome per row
    "tamps": "mxs_tamps",    # Tamaulipas: one table per period
    "sin": "mxs_sin",        # Sinaloa: the Gaceta app's JSON API
    "yuc": "mxs_yuc",        # Yucatán: one table since 2015
    "tab": "mxs_tab",        # Tabasco: one WordPress table
    "qroo": "mxs_qroo",      # Quintana Roo: list pages, newest first
    "ags": "mxs_ags",        # Aguascalientes: the agenda's JSON back end
    "nay": "mxs_nay",        # Nayarit: the Proceso Legislativo JSON
    # Alternative routes (12 October 2026, Chris: "prepare alternative methods
    # too"): where the congress's own site is blocked to us, the decrees it
    # ADOPTS, read from the state's official gazette (Periódico Oficial) on
    # a different, government-run host. Never the congress's site, never a
    # bot check. The edition marks these "(from the official gazette)".
    "slp": "mxs_slp_gazette",   # San Luis Potosí: the gazette's own search JSON
    "dgo": "mxs_dgo_gazette",   # Durango: each edition's HTML contents
    "qro": "mxs_qro_gazette",   # Querétaro: La Sombra de Arteaga's annual index PDF
    "cam": "mxs_cam_gazette",   # Campeche: SECCIÓN LEGISLATIVA edition PDFs
    # Puebla (13 October 2026, Chris: "Find an alternate method"): its gazette
    # refuses UK connections, so the gazette's decrees are read from the
    # Supreme Court's compilation of state legislation (legislacion.scjn.gob.mx).
    "pue": "mxs_pue_gazette",   # Puebla: the SCJN's 50 most recent Puebla reforms
}
# Readers that read an official gazette rather than the congress itself.
GAZETTE = {s for s, m in READERS.items() if m.endswith("_gazette")}

# Why a state has no reader (docs/mexico-regions-scope.md has the detail):
# state -> (status, one line). 'unreachable' states are asked once a run
# (PROBE below), so the day a runner can reach one, the edition says so.
NOT_READ = {
    "ver": ("unreachable", "www.legisver.gob.mx does not answer UK addresses; no reader yet"),
    "nl": ("unreachable", "www.hcnl.gob.mx does not answer UK addresses; no reader yet"),
    "gto": ("unreachable", "www.congresogto.gob.mx does not answer UK addresses; no reader yet"),
    "zac": ("unreachable", "www.congresozac.gob.mx does not answer UK addresses; no reader yet"),
    "coah": ("not built", "a JSF table paged by stateful postbacks; vote PDFs by date"),
    "son": ("not built", "a JSON API of only 413 items with no committee or status"),
    "hgo": ("not built", "per-sitting pages without author or committee (PDFs)"),
    "mor": ("not built", "Gaceta PDFs only, posted months late"),
    "mich": ("unreachable", "https://congresomich.gob.mx does not answer UK addresses; the "
                            "http copy stopped in June 2025"),
    "jal": ("not built", "INFOLEJ answers a two-step session search at about 77 s a page; "
                         "too slow for the step's clock"),
    "gro": ("not built", "per-sitting gacetas on a third-party host; the tracker is a "
                         "420-page PDF"),
    "tlax": ("not built", "all LXV work is one 1.5 MB WordPress page of tabbed tables"),
    "col": ("not built", "an undated HTML fragment by POST; no presentation dates"),
    "bcs": ("not built", "no listing of iniciativas; only orden del día RSS"),
}
# The home page asked once a run for an unreachable state (robots.txt
# honoured), so the coverage line says whether this runner reaches it.
PROBE = {
    "ver": "https://www.legisver.gob.mx/",
    "nl": "https://www.hcnl.gob.mx/",
    "gto": "https://www.congresogto.gob.mx/",
    "zac": "https://www.congresozac.gob.mx/",
    # Jalisco: the official GAZETTE's home page, not the congress. (Puebla's
    # gazette was probed here until 13 October 2026; Puebla now has a reader.)
    "jal": "https://periodicooficial.jalisco.gob.mx/",
    "mich": "https://congresomich.gob.mx/",
}
PROBE_WHAT = {"jal": "the Periódico Oficial's home page"}


def classify(tax, text, key, watch_path=None):
    import mx_rollcalls
    res = mx_rollcalls.classify(tax, text)
    return mxs_store.add_watch_areas(res, key, watch_path)


def load_taxonomy():
    import mx_rollcalls
    return mx_rollcalls.load_taxonomy()


def make_client():
    return HttpClient(os.path.join(ROOT, "data", "raw"), throttle=1.5)


_PROBE_CLIENT = []


def probe_client():
    """One try, 20 seconds: a host that does not answer costs 20 s, not the
    four minutes the shared client's retry ladder would spend."""
    if not _PROBE_CLIENT:
        _PROBE_CLIENT.append(HttpClient(os.path.join(ROOT, "data", "raw"), throttle=1.5,
                                        max_retries=0, default_timeout=20.0))
    return _PROBE_CLIENT[0]


def store_items(conn, tax, got, today, watch_path=None):
    """(new, on our ground) after storing every item a reader returned."""
    new = ours = 0
    for it in got:
        if not it.get("source_id") or not it.get("title"):
            continue
        key = mxs_store.item_key(it["state"], it["source_id"])
        text = " ".join(x for x in (it.get("title"), it.get("turno")) if x)
        res = classify(tax, text, key, watch_path)
        new += mxs_store.upsert_item(conn, it, res, today)
        ours += bool(res.issue_areas)
    return new, ours


def run_state(conn, client, state, tax, since, budget, today, now, dry_run=False, log=print):
    """Read one state; returns its gap count."""
    mod_name = READERS.get(state)
    if not mod_name:
        status, detail = NOT_READ.get(state, ("not built", "no reader yet"))
        if state in PROBE and not dry_run:
            ctx = Context(conn, probe_client(), state, feed=FEED, budget=budget,
                          log=lambda *a: None)
            page = ctx.text(PROBE[state], "probe-" + state)
            what = PROBE_WHAT.get(state, "the home page")
            if page is not None and len(page) > 2000:
                status, detail = "not built", "{0} ANSWERS this runner ({1} bytes); " \
                    "a reader can be written".format(what, len(page))
            elif page is not None:
                detail += "; {0} answered with only {1} bytes".format(what, len(page))
        if not dry_run:
            mxs_store.record_read(conn, state, None, status, detail, None, None, None, now)
        log("mxs: {0}: not read ({1}: {2})".format(state, status, detail))
        return 0
    mod = importlib.import_module("src.ingest." + mod_name)
    ctx = Context(conn, client, state, feed=FEED, since=since, budget=budget,
                  dry_run=dry_run, log=log)
    try:
        got = list(mod.collect(ctx, since) or [])
    except Exception as exc:  # noqa: BLE001 -- one state's layout change never costs the rest
        ctx.gap("{0}: reader failed: {1}: {2}".format(state, type(exc).__name__, exc))
        got = []
    for it in got:
        it.setdefault("state", state)
    through = max((it.get("presented") or "" for it in got), default="") or None
    if dry_run:
        log("mxs: {0}: {1} item(s) listed (dry run, nothing stored)".format(state, len(got)))
        return len(ctx.gaps)
    new, ours = store_items(conn, tax, got, today)
    if not got and ctx.gaps:
        status = "unreachable"
    else:
        status = "gap" if ctx.gaps else "ok"
    detail = ctx.gaps[0] if ctx.gaps else mod.READER
    mxs_store.record_read(conn, state, mod_name, status, str(detail)[:300], len(got), new,
                          through, now)
    db.record_gaps(conn, FEED, ctx.gaps)
    conn.commit()
    log("mxs: {0}: {1} listed, {2} new, {3} on our ground, {4} gap(s)".format(
        state, len(got), new, ours, len(ctx.gaps)))
    return len(ctx.gaps)


def reclassify(conn, tax, watch_path=None):
    n = ours = 0
    for r in conn.execute("SELECT item_key, title, turno FROM mxs_items").fetchall():
        text = " ".join(x for x in (r[1], r[2]) if x)
        res = classify(tax, text, r[0], watch_path)
        conn.execute("UPDATE mxs_items SET areas=?, matched_terms=?, tier=? WHERE item_key=?",
                     (mxs_store.dumps(res.issue_areas), mxs_store.dumps(res.matched_terms),
                      res.tier, r[0]))
        n += 1
        ours += bool(res.issue_areas)
    conn.commit()
    print("mxs: reclassified {0} item(s), {1} on our ground".format(n, ours))


def summary(conn):
    for r in conn.execute(
            "SELECT state, COUNT(*), SUM(areas != '[]') FROM mxs_items GROUP BY state "
            "ORDER BY state").fetchall():
        print("  {0}: {1} item(s) stored, {2} on our ground".format(r[0], r[1], r[2] or 0))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--state", action="append", choices=sorted(mxs_store.STATES))
    ap.add_argument("--since", help="list items from this date (default: the newest "
                    "stored item of the state less 30 days, or {0})".format(DEFAULT_SINCE))
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    conn = db.init_db(db.connect(args.db))
    tax = load_taxonomy()
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        return 0
    client = make_client()
    budget = drain.Budget(args.budget_seconds)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now[:10]
    gaps = 0
    for state in args.state or list(READERS) + [s for s in mxs_store.STATES if s not in READERS]:
        if budget.exhausted() and state in READERS:
            print(budget.disclose("states", state))
            mxs_store.record_read(conn, state, READERS[state], "gap",
                                  "not reached: the run's clock was spent", None, None, None,
                                  now)
            gaps += 1
            continue
        since = args.since or resume_since(conn, state)
        gaps += run_state(conn, client, state, tax, since, budget, today, now, args.dry_run)
    if not args.dry_run:
        conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                     "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                          "step heartbeat: tools/mxs_collect.py"))
    conn.commit()
    summary(conn)
    conn.close()
    return 3 if gaps else 0


def resume_since(conn, state, lookback_days=30):
    row = conn.execute("SELECT MAX(substr(presented,1,10)) FROM mxs_items WHERE state=?",
                       (state,)).fetchone()
    if not row or not row[0]:
        return DEFAULT_SINCE
    d = datetime.date.fromisoformat(row[0]) - datetime.timedelta(days=lookback_days)
    return max(d.isoformat(), DEFAULT_SINCE)


if __name__ == "__main__":
    sys.exit(main())
