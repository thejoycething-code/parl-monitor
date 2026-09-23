"""Is every source still being tracked? -- the watcher nobody had.

    python3 tools/coverage.py            # report; exit 1 if a source is overdue
    python3 tools/coverage.py --quiet    # report only what is overdue

Christopher, 2026-09-04: "What else needs building to ensure we're
properly tracking". This is the answer to how the last failure went
unseen. On 3 September the UPR monthly harvested 1,218 new
recommendations, published them, and had its store overwritten three
hours later by a hand push from a laptop holding an older copy. Both
runs were green. Nothing anywhere said "this source has not refreshed in
19 days", so the loss surfaced a day later only because someone thought
to measure it.

Two questions, because they fail differently:

  1. IS THE PIPELINE RUNNING?  source_runs, stamped by db_state.py --push
     at the end of every workflow. Answers "did the Sunday pull run?",
     which no amount of reading Westminster's tables could -- they carry
     no captured_at at all.
  2. IS THE SOURCE ANSWERING?  the newest last_seen / captured_at in each
     table. A pipeline can run green while one feed inside it 403s.

Recess is not failure. A chamber that is not sitting produces no
divisions, so this never judges freshness by the DATE OF THE BUSINESS --
only by when we last SAW the source. Feeds that are written once per
item and never re-stamped are listed as such and never fail the run.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# workflow -> (expected cadence in days, grace, why)
PIPELINES = {
    "Sunday pull": (7, 3, "Westminster: roster, events, divisions"),
    "Monday publish": (7, 3, "the edition, the pages, the briefs"),
    "Holyrood weekly": (7, 4, "Scotland"),
    "Senedd weekly": (7, 4, "Wales"),
    "NI Assembly weekly": (7, 4, "Northern Ireland"),
    "EU weekly": (7, 3, "the EU edition and its collectors"),
    "Germany weekly": (7, 4, "Bundestag and the sixteen Land parliaments"),
    # Nightly, and it stamps a heartbeat whether or not the Parliament sat:
    # most nights it records "did not sit" and publishes nothing else, which
    # is exactly the signal we want -- silence here means the workflow died,
    # not that Brussels is quiet. Grace of 2 covers a cancelled slot.
    "EU day sweep": (1, 2, "the EP swept per sitting day (roll calls and adopted texts)"),
    "UPR monthly": (31, 7, "UN Universal Periodic Review"),
    # Missing until 2026-09-04, like EU weekly was from the alert list:
    # it pulls service history, party spells and contact details for
    # every chamber, and nothing would have said if it stopped.
    "Member profiles": (7, 4, "service history, party spells, contacts"),
    # Since 2026-09-09 this is the ledger's PRIMARY source of speeches; the
    # Sunday pull only repairs what it missed. Cadence 1 with a grace of 3
    # because it runs on sitting weekdays only: Friday evening to Monday
    # morning is the longest legitimate gap.
    "Day sweep": (1, 3, "the day's speeches on our issues, and the radar"),
}

# Pipelines deliberately not running. Listed so a PAUSE never reads as a
# failure, and a pause nobody remembers never reads as health.
PAUSED = {
    "UN calls weekly": "paused 2026-08-17 by Christopher: nothing "
                       "UN-related publishes until the monitor covers the "
                       "issues and the forward calendar properly.",
}

# table -> (freshness column, expected days, grace, note)
FEEDS = [
    ("bill_amendments", "last_seen", 7, 3, "amendments to watched Bills (Sunday pull)"),
    # MEASURED (22 September 2026), not assumed: de_documents writes with
    # INSERT OR IGNORE and de_divisions SKIPS votes it already holds, so
    # neither re-stamps and both belong in ONCE_EVER. de_vorgaenge is the
    # one German table that really is a heartbeat: its upsert sets
    # last_seen=excluded.last_seen, and the weekly term sweep asks DIP for
    # every tier-1 term over a 120-day window, so a live run re-sees the
    # recent ones whether or not anything new appeared.
    ("de_vorgaenge", "last_seen", 7, 4, "Bundestag Vorgänge from DIP (Germany weekly)"),
    # The Tagesordnungen feed re-stamps every sighting, so this IS a
    # heartbeat -- and a loud one: it is a rolling window with no archive,
    # so a week the collector does not run is a week of agendas nobody can
    # ever recover.
    ("de_agenda", "last_seen", 7, 4, "Bundestag committee and plenary agendas (Germany weekly)"),
    # All four re-stamp on every sweep, so each is a real heartbeat.
    ("de_petitions", "last_seen", 7, 4, "Bundestag e-petitions open for co-signature (Germany weekly)"),
    ("de_petition_snapshots", "captured_at", 7, 4, "German petition signature snapshots"),
    ("de_judgments", "last_seen", 7, 4, "Bundesverfassungsgericht cases listed for decision"),
    ("de_amendments", "last_seen", 7, 4, "Änderungsanträge to bills (Germany weekly)"),
    ("hansard_sections", "captured_at", 7, 3, "Hansard's section list per sitting day (Sunday pull)"),
    ("judge_verdicts", "captured_at", 7, 3, "the judge evaluation bank (Sunday pull)"),
    ("dv_petitions", "last_seen", 7, 4, "Senedd and Holyrood petitions (devolved weeklies)"),
    ("dv_petition_snapshots", "captured_at", 7, 4, "devolved petition signature snapshots"),
    ("petitions", "last_seen", 7, 3, "e-petitions on our ground (collated, not published)"),
    ("petition_snapshots", "captured_at", 7, 3, "e-petition signature snapshots"),
    ("sp_items", "last_seen", 7, 4, "Holyrood questions and motions"),
    ("sp_divisions", "last_seen", 7, 4, "Holyrood divisions"),
    ("sp_members", "last_seen", 7, 4, "MSP roster"),
    ("sd_items", "last_seen", 7, 4, "Senedd questions"),
    ("sd_divisions", "last_seen", 7, 4, "Senedd divisions"),
    ("sd_members", "captured_at", 7, 4, "MS roster"),
    ("member_aliases", "captured_at", 7, 4, "the Welsh name bridge"),
    ("ni_items", "last_seen", 7, 4, "NI questions and motions"),
    ("ni_divisions", "last_seen", 7, 4, "NI divisions"),
    ("ni_members", "last_seen", 7, 4, "MLA roster"),
    ("dg_consultations", "last_seen", 7, 4, "devolved consultations"),
    ("sp_events", "last_seen", 7, 4, "Holyrood events"),
    ("sp_bills", "last_seen", 7, 4, "Holyrood bill register"),
    ("sp_committees", "last_seen", 7, 4, "Holyrood committees"),
    ("sd_events", "last_seen", 7, 4, "Senedd events"),
    ("sd_bills", "last_seen", 7, 4, "Senedd bill register"),
    ("sd_committees", "last_seen", 7, 4, "Senedd committees"),
    ("ni_committees", "last_seen", 7, 4, "NI committees"),
    ("eu_cmte_meetings", "last_seen", 7, 3, "EP committee meetings"),
    ("dv_post", "last_seen", 7, 4, "devolved members' posts"),
    ("dv_contact", "last_seen", 7, 4, "devolved members' contacts"),
    ("eu_agenda", "last_seen", 7, 3, "EP forward agenda"),
    ("eu_texts", "last_seen", 7, 3, "EP adopted texts"),
    ("eu_pqs", "last_seen", 7, 3, "EP written questions"),
    ("eu_cmte_docs", "last_seen", 7, 3, "EP committee documents"),
    ("eu_ecis", "last_seen", 7, 3, "European Citizens' Initiatives"),
    ("eu_consultations", "last_seen", 7, 3, "Commission consultations"),
    ("eu_meps", "last_seen", 7, 3, "MEP roster"),

    ("upr_recommendations", "captured_at", 31, 7, "UPR recommendations"),
]

# Which feeds each pipeline is responsible for. This drives the check
# that actually catches a CLOBBER: a pipeline that ran yesterday whose
# data is weeks old did not fail -- it succeeded and its work was thrown
# away, or it stored nothing while reporting success. That is exactly
# what happened to the UPR monthly on 2026-09-03: green run, 1,218
# recommendations harvested, and a store 19 days stale afterwards.
# Feeds a human has confirmed are legitimately empty, and why. Keep it short:
# every entry here is an alert somebody decided not to hear.
ALLOWED_EMPTY = {
    # de_documents is filled by tools/de_documents.py --mode WINDOW, which
    # sweeps /drucksache by date and body-matches. The Germany weekly runs
    # --mode TERMS, which drives /vorgang from the tier-1 German terms and
    # writes de_vorgaenge only. So this table is empty because of a mode
    # choice, not a broken collector, and the day someone adds a window step
    # to de-weekly.yml this entry must come straight back out.
    "de_documents": "the weekly runs --mode terms, which writes Vorgänge "
                    "only; --mode window is what fills this table",
}

# Write-once feeds belonging to a pipeline that is deliberately stopped: an
# empty table there is the pause, not a wipe.
PAUSED_TABLES = {"un_votes", "un_documents", "un_calendar"}


PIPELINE_FEEDS = {
    "Holyrood weekly": ["sp_items", "sp_divisions", "sp_members",
                        "sp_events", "sp_bills", "sp_committees"],
    "Senedd weekly": ["sd_items", "sd_divisions", "sd_members",
                      "member_aliases", "sd_events", "sd_bills",
                      "sd_committees"],
    "NI Assembly weekly": ["ni_items", "ni_divisions", "ni_members",
                           "ni_committees"],
    # eu_judgments is deliberately ABSENT, for the same reason the German
    # once-ever tables are: PIPELINE_FEEDS drives the CLOBBER check -- a
    # pipeline that ran but whose data is stale -- and a table written once
    # per item cannot pass it during a quiet month. Listed here it reported
    # "LOST WORK" for eleven days while nothing was lost and the Strasbourg
    # court had simply not ruled on our issues since 16 July.
    "EU weekly": ["eu_agenda", "eu_texts", "eu_pqs", "eu_cmte_docs",
                  "eu_ecis", "eu_consultations", "eu_meps",
                  "eu_cmte_meetings"],
    # de_vorgaenge only: PIPELINE_FEEDS drives the CLOBBER check (a pipeline
    # that ran but whose data is stale), and the other three German tables
    # legitimately never move -- the Bundestag takes recorded votes in
    # bursts, so listing them here would cry clobber every quiet month.
    "Germany weekly": ["de_vorgaenge", "de_agenda", "de_petitions",
                       "de_petition_snapshots", "de_judgments",
                       "de_amendments"],
    "UPR monthly": ["upr_recommendations"],
    # "EU day sweep" is deliberately absent. PIPELINE_FEEDS drives the clobber
    # check -- a pipeline that ran but whose data is stale -- and the EP sits in
    # blocks with weeks of recess between them, so its feeds age legitimately
    # and every recess would raise a false alarm. Its heartbeat in PIPELINES is
    # the honest signal: the workflow runs nightly even when nothing sat.
    "Member profiles": ["dv_post", "dv_contact"],
    "Day sweep": ["sweep_log"],
}

# Tables carrying a sighting column that are DELIBERATELY not watched,
# each with its reason. The structural test allows only what is declared
# here, so a new source cannot arrive unwatched AND unexplained -- which
# is exactly how EU weekly stayed off the failure alert from the day it
# was written, and how Member profiles was missing from this file.
EXEMPT = {}

# Workflows that write the store but run ONLY when a human dispatches
# them. They cannot "stop dead" -- there is no cadence to miss -- so they
# get no heartbeat expectation. They still stamp one when they run, which
# is what makes the clobber check work for them too.
ON_DEMAND = {
    "Historic backfill": "workflow_dispatch only: a sweep run by hand "
                         "when the taxonomy or the cutoff changes.",
    "Score stance": "workflow_dispatch only: scores outstanding refs "
                    "when someone asks for it.",
}

# Written once per item and never re-stamped, so an old date means "no new
# items", not "the feed died". Reported, never failed.
# MEASURED, not assumed: each of these was checked for whether its
# writer re-stamps last_seen on every sighting (ON CONFLICT ... SET
# last_seen=excluded.last_seen) or only writes new rows. A table that
# only gains rows goes quiet in recess through no fault of anyone, and
# alarming on it would train people to ignore the alert.
ONCE_EVER = {
    "items": "new rows only: PQs, SIs, consultations and what's on are "
             "inserted when they appear and not re-stamped",
    "sp_affiliations": "new rows only: an MSP's committee places",
    "ni_agenda": "new rows only: the forward Order Paper",
    "ni_votes": "new rows only: a member-vote is stored once",
    "ni_affiliations": "new rows only: an MLA's committee places",
    "ni_sittings": "one row per sitting date, archived once",
    "ni_sponsors": "fetched once per motion",
    "eu_speeches": "one row per speech, stored once",
    "eu_divisions": "one row per roll call, stored once",
    # MEASURED 23 September 2026, after eleven days of "LOST WORK" that was
    # no such thing. tools/eu_courts.py builds `known` from the stored item
    # ids and SKIPS anything already held, so a judgment is written once and
    # its last_seen never moves again -- the table can only ever look stale.
    #
    # The alarm was NOT simply silenced: HUDOC was probed first, because
    # "the court is quiet" and "the query broke" produce an identical empty
    # result. It answers, and it still returns 1 judgment since January, 21
    # since 2024 and 50 since 2015 -- so the search works and the Strasbourg
    # court has genuinely issued nothing on our terms since 16 July.
    "eu_judgments": "new rows only: eu_courts.py skips item ids it already "
                    "holds, so last_seen never moves; a court is quiet for "
                    "months at a time and that is not a failure",
    "eu_dossiers": "hand-curated watchlist",
    # GERMANY (promoted out of EXEMPT on 22 September 2026, when
    # de-weekly.yml started pushing the store). Each placement was checked
    # against its writer rather than guessed:
    "de_documents": "new rows only: INSERT OR IGNORE, so a Drucksache is "
                    "stored once and never re-stamped",
    "de_divisions": "new rows only in practice: tools/de_rollcalls.py skips "
                    "polls it already holds, and the Bundestag votes in "
                    "bursts -- 68 in sixteen months",
    "de_members": "re-stamped only when a recorded vote is collected, which "
                  "is itself a burst",
    "de_speeches": "new rows only: a Stenografischer Bericht is final and is "
                   "read once, and the Bundestag sits in blocks with months "
                   "of recess between them",
    "un_votes": "UN pipeline is paused",
    "un_documents": "UN pipeline is paused",
    "un_calendar": "UN pipeline is paused",
}


def age_of(conn, table, col, today):
    try:
        row = conn.execute("SELECT MAX({0}) FROM {1}".format(col, table)
                           ).fetchone()
    except sqlite3.Error:
        return None, None
    val = (row[0] or "")[:10] if row else ""
    try:
        return val, (today - datetime.date.fromisoformat(val)).days
    except ValueError:
        return val or None, None


def table_exists(conn, table):
    """A table this store has never carried is a schema gap, not a data loss:
    init_db creates every one in production, so this only separates a real
    emptying from a fixture or a store that predates the table."""
    try:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                           "AND name = ?", (table,)).fetchone()
    except sqlite3.Error:
        return False
    return bool(row)


def check(conn, today=None, log=print, quiet=False):
    today = today or datetime.date.today()
    overdue = []

    log("PIPELINES  (did the workflow run at all?)")
    seen = {}
    try:
        for r in conn.execute("SELECT source, last_run FROM source_runs"):
            seen[r[0]] = r[1]
    except sqlite3.Error:
        log("  no heartbeat table yet: every workflow stamps one on its "
            "next successful push (tools/db_state.py).")
    for name, (days, grace, why) in sorted(PIPELINES.items()):
        last = seen.get(name)
        if not last:
            log("  {0:<20} NO HEARTBEAT YET   {1}".format(name, why))
            continue
        try:
            age = (today - datetime.date.fromisoformat(last)).days
        except ValueError:
            continue
        late = age > days + grace
        if late:
            overdue.append("{0} last published {1} days ago (expected every "
                           "{2})".format(name, age, days))
        if late or not quiet:
            log("  {0:<20} {1:>3} days ago{2}   {3}".format(
                name, age, "  <-- OVERDUE" if late else "", why))
    for name, why in sorted(PAUSED.items()):
        if not quiet:
            log("  {0:<20} PAUSED   {1}".format(name, why[:60]))

    if not quiet:
        log("")
    log("FEEDS  (is the source still answering?)")
    for table, col, days, grace, why in FEEDS:
        val, age = age_of(conn, table, col, today)
        if age is None:
            # AN EMPTY WATCHED FEED IS A FAULT, NOT SILENCE (17 Sept 2026).
            # This printed "NO DATA" and moved on, so it read the same whether
            # a feed had never been populated or had just lost every row. Five
            # EU tables were emptied by the 9 Sept store rebuild -- 21 plenary
            # divisions, the adopted texts, the consultations -- and the watch
            # that exists to catch exactly that said nothing for eight days
            # while the EU weekly was also being cancelled. A feed is listed
            # here because we expect rows in it; if it has none, say so loudly
            # and put it in ALLOWED_EMPTY with a reason once a human agrees.
            if not table_exists(conn, table):
                log("  {0:<22} NO TABLE   {1}".format(table, why))
                continue
            reason = ALLOWED_EMPTY.get(table)
            if reason:
                if not quiet:
                    log("  {0:<22} EMPTY BY DESIGN   {1}".format(table, reason))
                continue
            overdue.append("{0} holds NO ROWS AT ALL; it is watched because we "
                           "expect data in it ({1})".format(table, why))
            log("  {0:<22} NO ROWS AT ALL  <-- OVERDUE   {1}".format(table, why))
            continue
        late = age > days + grace
        if late:
            overdue.append("{0} last saw data {1} days ago (expected every "
                           "{2})".format(table, age, days))
        if late or not quiet:
            log("  {0:<22} {1:>3} days ago{2}   {3}".format(
                table, age, "  <-- OVERDUE" if late else "", why))
    # THE CLOBBER CHECK. A pipeline whose own heartbeat is fresh but
    # whose data is old either stored nothing or had its store
    # overwritten. Both are silent, and both are invisible to a
    # cadence test on either signal alone.
    if not quiet:
        log("")
    log("RAN BUT DID NOT LAND  (fresh pipeline, stale data)")
    flagged = False
    for name, tables in sorted(PIPELINE_FEEDS.items()):
        last = seen.get(name)
        if not last:
            continue
        try:
            pipe_age = (today - datetime.date.fromisoformat(last)).days
        except ValueError:
            continue
        cadence = PIPELINES.get(name, (7, 3, ""))[0]
        if pipe_age > cadence:
            continue          # it is simply overdue; reported above
        for table in tables:
            col = next((c for c, _d, _g, _n in
                        [(f[1], f[2], f[3], f[4]) for f in FEEDS
                         if f[0] == table]), "last_seen")
            _val, age = age_of(conn, table, col, today)
            # A week of slack: a feed legitimately quiet for a few days
            # inside a pipeline that ran is normal; a month is not.
            if age is not None and age > pipe_age + 7:
                flagged = True
                overdue.append(
                    "{0} ran {1} days ago but {2} has not refreshed in {3} "
                    "-- it stored nothing, or its store was overwritten"
                    .format(name, pipe_age, table, age))
                log("  {0:<20} ran {1}d ago, {2} is {3}d old   <-- LOST WORK"
                    .format(name, pipe_age, table, age))
    if not flagged:
        log("  nothing: every pipeline that ran has data as fresh as its run.")

    if not quiet:
        log("")
        log("WRITTEN ONCE PER ITEM  (an old date here means no new items)")
    # Reported even in quiet mode, because the ONE thing a write-once feed can
    # tell you is fatal: it holds nothing. A quiet month is why these are not
    # cadence-checked; an EMPTY table is not a quiet month, it is a wipe. The
    # 9 Sept store rebuild emptied eu_divisions of 21 plenary roll calls, and
    # this section printed "? days ago" beside it for eight days.
    for table, why in sorted(ONCE_EVER.items()):
        if table in PAUSED_TABLES:
            continue
        if not table_exists(conn, table):
            continue
        cols = [c[1] for c in conn.execute(
            "PRAGMA table_info({0})".format(table))]
        col = next((c for c in ("last_seen", "captured_at") if c in cols), None)
        val, age = age_of(conn, table, col, today) if col else (None, None)
        empty = conn.execute("SELECT COUNT(*) FROM {0}".format(table)).fetchone()[0] == 0
        if empty and table not in ALLOWED_EMPTY:
            overdue.append("{0} is written once per item and holds NO ROWS AT "
                           "ALL: every row it had is gone ({1})".format(table, why))
            log("  {0:<22} NO ROWS AT ALL  <-- OVERDUE   {1}".format(table, why))
        elif not quiet:
            log("  {0:<22} {1:>3} days ago   {2}".format(
                table, age if age is not None else "?", why))
    return overdue


def main():
    quiet = "--quiet" in sys.argv
    conn = sqlite3.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    overdue = check(conn, quiet=quiet)
    stamped = set()
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
                    "name='source_runs'").fetchone():
        stamped = {r[0] for r in conn.execute("SELECT source FROM source_runs")}
    conn.close()
    print("")
    if overdue:
        # LOUD, and non-zero: this workflow is watched by the failure
        # alert, so an overdue source becomes a DM rather than a line in a
        # log nobody opens.
        print("{0} SOURCE(S) OVERDUE:".format(len(overdue)))
        for line in overdue:
            print("  * {0}".format(line))
        return 1
    missing = sorted(n for n in PIPELINES if n not in stamped)
    if missing:
        print("Feeds are within cadence. {0} pipeline(s) have not stamped a "
              "heartbeat yet, so whether they RAN is still unknown: {1}"
              .format(len(missing), ", ".join(missing)))
        return 0
    print("Every pipeline and feed is within its expected cadence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
