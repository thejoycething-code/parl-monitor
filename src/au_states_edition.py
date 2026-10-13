"""The states and territories section of the Australian edition
(tools/au_monitor.py), from the tables tools/au_states.py fills.

13 October 2026; docs/australia-states-scope.md. Read-only on the store.

WHAT IT SHOWS, for items on our ground only (area 11 is never shown):

  * new this week: bills a state's source listed for the first time (a
    source's first read lists everything already before Parliament, so
    those count only by their own introduction date);
  * moved this week: a stage dated in the window (New South Wales from the
    Hansard sitting day; elsewhere the day a weekly read saw the change, or
    Victoria's own last-changed date);
  * divisions (New South Wales): the question where the Hansard fragment was
    read, the tally, and whether its own words matched or only its bill did;
  * Acts made this week (the registers' Acts, for the states whose bill
    lists are out of reach);
  * what is before each state parliament now, and a coverage block saying
    what each source last answered and what is blocked.

NO VERDICTS, as in the federal edition: "agreed to" and "negatived" are ayes
against noes, never a win or a defeat.
"""

from __future__ import annotations

import datetime
import json
import sqlite3

from src import au_states_store as aus

HIDDEN_AREAS = (11,)
WEEK_DAYS = 7
BEFORE_LINES = 25
DIVISION_LINES = 12

# What is out of reach, state by state (docs/australia-states-scope.md).
BLOCKED = (
    "every parliament's own website except Victoria's and South Australia's refuses our "
    "collectors with a bot challenge (Cloudflare: New South Wales, Tasmania, the ACT, the "
    "Northern Territory; Azure WAF: Queensland, Western Australia), as do South Australia's "
    "Hansard search and the NSW and SA legislation registers. So: divisions only for New South "
    "Wales (its Hansard API); Queensland bills read 'introduced' until an Act of their name "
    "appears; Western Australia shows Acts only; Tasmania names its bills without a stage; the "
    "ACT shows only what its register listed in the last seven days."
)


def _visible(areas_json):
    try:
        return [a for a in json.loads(areas_json or "[]") if a not in HIDDEN_AREAS]
    except (TypeError, ValueError):
        return []


def _names(areas, names):
    return ", ".join(names.get(a, str(a)) for a in areas)


def _one(text):
    return " ".join((text or "").replace("—", " - ").split())


def _clip(text, n):
    text = _one(text)
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def _rows(conn, sql, params=()):
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []


def _ours(rows, col="areas"):
    return [r for r in rows if _visible(r[col])]


def _window(today, days=WEEK_DAYS):
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()


def new_bills(conn, today):
    since = _window(today)
    rows = _rows(conn, "SELECT * FROM aus_bills WHERE "
                       "((seed = 0 AND first_seen > ? AND first_seen <= ?) OR "
                       "(introduced > ? AND introduced <= ?)) ORDER BY introduced DESC, state",
                 (since, today, since, today))
    return _ours(rows)


def moved_bills(conn, today):
    """(bill row, [events in the window]) for bills on our ground."""
    since = _window(today)
    events = _rows(conn, "SELECT e.*, b.title, b.state, b.url, b.areas, b.stage AS now_stage, "
                         "b.status, b.introduced, b.introduced_by, b.kind, b.first_seen, b.seed "
                         "FROM aus_bill_events e JOIN aus_bills b ON b.bill_key = e.bill_key "
                         "WHERE e.date > ? AND e.date <= ? ORDER BY e.date DESC", (since, today))
    out = {}
    for e in _ours(events):
        out.setdefault(e["bill_key"], []).append(e)
    return out


def acts_made(conn, today):
    since = _window(today)
    rows = _rows(conn, "SELECT * FROM aus_acts WHERE (made > ? AND made <= ?) OR "
                       "(seed = 0 AND first_seen > ? AND first_seen <= ?) ORDER BY made DESC",
                 (since, today, since, today))
    return _ours(rows)


def divisions(conn, since, today):
    rows = _rows(conn, "SELECT * FROM aus_divisions WHERE date > ? AND date <= ? "
                       "ORDER BY date DESC, division_key", (since, today))
    return _ours(rows)


def before(conn):
    rows = _rows(conn, "SELECT * FROM aus_bills WHERE status = 'before' "
                       "ORDER BY state, COALESCE(stage_date, introduced, first_seen) DESC")
    return _ours(rows)


def outcome(ayes, noes):
    if ayes is None or noes is None:
        return "?"
    return "Agreed to" if ayes > noes else ("Negatived" if noes > ayes else "Tied")


def bill_line(r, names, what=None):
    who = "; introduced by {0}".format(_one(r["introduced_by"])) if r["introduced_by"] else ""
    kind = " (motion)" if r["kind"] == "motion" else ""
    where = what or "{0}{1}".format(_one(r["stage"]) or "listed",
                                    " ({0})".format(r["stage_date"]) if r["stage_date"] else "")
    link = "[{0}]({1})".format(_clip(r["title"], 110), r["url"]) if r["url"] else _clip(r["title"], 110)
    return "- **{0}** {1}{2}: {3}{4}. *Areas: {5}.*".format(
        aus.SHORT.get(r["state"], r["state"]), link, kind, where, who,
        _names(_visible(r["areas"]), names))


def division_line(conn, r, names):
    own = _visible(r["own_areas"])
    q = r["question"] or "{0}{1}".format(_clip(r["heading"], 90),
                                         ", " + r["stage"] if r["stage"] else "")
    pairs = ", {0} pair(s)".format(r["pairs"]) if r["pairs"] else ""
    result = " The record: *{0}*".format(_one(r["result"])) if r["result"] else ""
    return ("- **{0} {1}**, [{2}]({3}): {4} **{5}** {6}-{7}{8}.{9} *Areas: {10} (matched on {11}).*"
            .format(aus.SHORT.get(r["state"], r["state"]), r["chamber"], r["date"], r["url"] or "",
                    _clip(q, 200), outcome(r["ayes"], r["noes"]), r["ayes"], r["noes"], pairs,
                    result, _names(_visible(r["areas"]), names), "own text" if own else "bill only"))


def _read_line(conn):
    reads = {r["source"]: r for r in _rows(conn, "SELECT * FROM aus_reads")}
    parts = []
    for code, sources in (("nsw", ("nsw",)), ("vic", ("vic",)), ("qld", ("qld-bills", "qld-acts")),
                          ("sa", ("sa",)), ("wa", ("wa-acts",)), ("tas", ("tas-bills", "tas-acts")),
                          ("act", ("act-acts",)), ("nt", ("nt",))):
        got = [reads[s] for s in sources if s in reads]
        if not got:
            parts.append("{0} not read yet".format(aus.SHORT[code]))
            continue
        bad = [g for g in got if (g["status"] or "").startswith(("failed", "empty"))]
        when = max(g["last_seen"] or "" for g in got)
        parts.append("{0} read {1}{2}".format(aus.SHORT[code], when,
                                              " ({0})".format(bad[0]["status"]) if bad else ""))
    return "; ".join(parts)


def render(conn, today, names):
    """The section's lines, or a one-line note when the layer never ran."""
    if not _rows(conn, "SELECT 1 FROM aus_reads LIMIT 1"):
        return ["## States and territories", "",
                "*The states and territories layer has not run yet (tools/au_states.py, a step of "
                "the Australia weekly).*", ""]
    since, month = _window(today), _window(today, 30)
    new = new_bills(conn, today)
    new_keys = {r["bill_key"] for r in new}
    moved = {k: v for k, v in moved_bills(conn, today).items() if k not in new_keys}
    acts = acts_made(conn, today)
    live = before(conn)
    out = ["## States and territories", "",
           "*The six state parliaments and two territory assemblies, from each one's own open data "
           "where it is reachable (docs/australia-states-scope.md). Bills are matched on their "
           "titles only with the shared taxonomy, plus config/watchlist-au-states.yaml by key. "
           "Stages are each source's own words. \"Agreed to\" and \"negatived\" are ayes against "
           "noes, never a verdict.*", ""]

    out += ["### New this week ({0})".format(len(new)), ""]
    out += [bill_line(r, names) for r in new] or ["*No new bill on our ground in any state source "
                                                 "this week.*"]
    out += ["", "### Moved this week ({0})".format(len(moved)), ""]
    for key, evs in moved.items():
        e = evs[0]
        steps = "; ".join("{0}{1} {2}".format(_one(x["stage"]),
                                              " ({0})".format(x["chamber"]) if x["chamber"] else "",
                                              x["date"]) for x in reversed(evs))
        out.append(bill_line(e, names, what=steps))
    if not moved:
        out.append("*No bill on our ground reached a new stage this week.*")

    week = divisions(conn, since, today)
    if week:
        out += ["", "### Divisions this week ({0}, New South Wales)".format(len(week)), ""]
        out += [division_line(conn, r, names) for r in week[:DIVISION_LINES]]
    else:
        recent = divisions(conn, month, today)
        out += ["", "### Divisions (none this week; last 30 days: {0}, New South Wales)".format(
            len(recent)), ""]
        out += [division_line(conn, r, names) for r in recent[:DIVISION_LINES]] or [
            "*None on our ground in the last 30 days.*"]
        week = recent
    if len(week) > DIVISION_LINES:
        out.append("\n_...and {0} more._".format(len(week) - DIVISION_LINES))

    out += ["", "### Acts made this week ({0})".format(len(acts)), ""]
    out += ["- **{0}** [{1}]({2}), {3}. *Areas: {4}.*".format(
        aus.SHORT.get(a["state"], a["state"]), _clip(a["title"], 110), a["url"] or "",
        a["made"] or "date not given", _names(_visible(a["areas"]), names)) for a in acts] or [
        "*None on our ground.*"]

    out += ["", "### Before the state parliaments ({0})".format(len(live)), "",
            "*Bills and motions on our ground that the sources still list as before Parliament, "
            "newest stage first, state by state. Tasmania's titles carry no stage and are left "
            "out.*", ""]
    out += [bill_line(r, names) for r in live[:BEFORE_LINES]] or ["*None.*"]
    if len(live) > BEFORE_LINES:
        out.append("\n_...and {0} more._".format(len(live) - BEFORE_LINES))

    c = lambda sql: (_rows(conn, sql) or [[0]])[0][0]  # noqa: E731
    out += ["", "### State coverage", "",
            "- **Collected:** {0} bills and motions across the eight ({1} on our ground), {2} "
            "Acts, {3} New South Wales divisions with every member's vote from {4} House sitting "
            "days of its Hansard. {5}.".format(
                c("SELECT COUNT(*) FROM aus_bills"),
                len(_ours(_rows(conn, "SELECT areas FROM aus_bills"))),
                c("SELECT COUNT(*) FROM aus_acts"), c("SELECT COUNT(*) FROM aus_divisions"),
                c("SELECT COUNT(*) FROM aus_hansard_days"), _read_line(conn)),
            "- **Blocked:** " + BLOCKED, ""]
    return out


def dm_line(conn, today):
    """One line for the DM, or None when the layer never ran."""
    if not _rows(conn, "SELECT 1 FROM aus_reads LIMIT 1"):
        return None
    new = new_bills(conn, today)
    new_keys = {r["bill_key"] for r in new}
    moved = [k for k in moved_bills(conn, today) if k not in new_keys]
    week = divisions(conn, _window(today), today)
    acts = acts_made(conn, today)
    states = sorted({aus.SHORT[r["state"]] for r in new} |
                    {aus.SHORT.get(k.split(":")[0], k.split(":")[0]) for k in moved})
    return ("*States and territories:* {0} new, {1} moved, {2} NSW division(s), {3} Act(s) on our "
            "ground{4}.".format(len(new), len(moved), len(week), len(acts),
                                " ({0})".format(", ".join(states)) if states else ""))


def coverage_count(conn):
    """(bills, acts) stored, for the federal Coverage block's one-liner."""
    c = lambda sql: (_rows(conn, sql) or [[0]])[0][0]  # noqa: E731
    return c("SELECT COUNT(*) FROM aus_bills"), c("SELECT COUNT(*) FROM aus_acts")
