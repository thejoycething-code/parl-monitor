"""Decisions needed: the block under Top lines that stops a question recurring.

Christopher, 2026-09-07: "Build the decisions block." Two why-lines in
Edition 6 said a supporter response was "still an open decision", one of
them for the second week. A why-line can flag a decision; it cannot carry
an owner or a date, so the same sentence returns every Monday until
someone happens to act. config/decisions.yaml holds the owner and the
decide-by date; this module pairs the log with the week's items and
renders both the logged decisions (counting down, marking overdue) and
any why-line that calls something an open decision WITHOUT a log entry --
so the recurrence is made visible, never quietly accepted.
"""

from __future__ import annotations

import datetime
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "config", "decisions.yaml")

# The phrasings the judge and the reviewer use for "nobody has decided yet".
OPEN_PHRASE = re.compile(
    r"open decision|still to (be )?decide|yet to (be )?decide|undecided|"
    r"decision (is )?(still )?pending|not yet decided|awaits a decision",
    re.IGNORECASE)
SHOW_DECIDED_DAYS = 14


def load(path=PATH):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    out = []
    for d in cfg.get("decisions") or []:
        if not d.get("id") or not d.get("decision"):
            raise ValueError("decisions.yaml: every entry needs an id and a decision")
        out.append(d)
    return out


def _iso(value):
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)[:10] if value else None


def collect(log, mentions, week_commencing, today=None):
    """-> {"open": [...], "decided": [...], "unlogged": [...]}.

    `mentions` are (title, why) pairs for the items the edition renders;
    a why-line matching OPEN_PHRASE whose title matches no log entry's
    `about` is unlogged. `today` defaults to week_commencing, so a
    re-render of an old edition counts down from its own Monday.
    """
    today = today or datetime.date.fromisoformat(week_commencing)
    open_rows, decided_rows = [], []
    for d in log:
        row = dict(d)
        row["decide_by"] = _iso(d.get("decide_by"))
        row["decided_on"] = _iso(d.get("decided_on"))
        row["opened"] = _iso(d.get("opened"))
        if (d.get("status") or "open") == "decided":
            if row["decided_on"]:
                age = (today - datetime.date.fromisoformat(row["decided_on"])).days
                if age <= SHOW_DECIDED_DAYS:
                    decided_rows.append(row)
            continue
        if row["decide_by"]:
            left = (datetime.date.fromisoformat(row["decide_by"]) - today).days
            row["days_left"] = left
            row["overdue"] = left < 0
        else:
            row["days_left"] = None
            row["overdue"] = False
        open_rows.append(row)
    open_rows.sort(key=lambda r: (r["days_left"] is None, r["days_left"] or 0))

    abouts = [(d.get("about") or "").lower() for d in log if d.get("about")]
    unlogged, seen = [], set()
    for title, why in mentions or []:
        if not why or not OPEN_PHRASE.search(why):
            continue
        t = (title or "").lower()
        if any(a and a in t for a in abouts):
            continue
        key = t[:80]
        if key in seen:
            continue
        seen.add(key)
        unlogged.append({"title": title, "why": why})
    return {"open": open_rows, "decided": decided_rows, "unlogged": unlogged}


def _status(row):
    if row["days_left"] is None:
        return "no date set"
    if row["overdue"]:
        n = -row["days_left"]
        return "**OVERDUE by {0} day{1}**".format(n, "" if n == 1 else "s")
    if row["days_left"] == 0:
        return "**today**"
    return "{0} day{1} left".format(row["days_left"], "" if row["days_left"] == 1 else "s")


def render(rows):
    """Markdown for the block, or None when there is nothing to decide."""
    if not rows or not (rows["open"] or rows["decided"] or rows["unlogged"]):
        return None
    out = ["## Decisions needed", ""]
    if rows["open"]:
        out.append("| Decision | Owner | Decide by | Status |")
        out.append("|---|---|---|---|")
        for r in rows["open"]:
            out.append("| {0} | {1} | {2} | {3} |".format(
                (r["decision"] or "").replace("|", "/"),
                r.get("owner") or "*unassigned*", r["decide_by"] or "*none*", _status(r)))
        out.append("")
    if rows["decided"]:
        out.append("*Decided since last edition:*")
        for r in rows["decided"]:
            out.append("- {0} — **{1}** ({2}{3})".format(
                r["decision"], r.get("outcome") or "decided", r["decided_on"],
                ", " + r["owner"] if r.get("owner") else ""))
        out.append("")
    if rows["unlogged"]:
        out.append("*Called an open decision this week but not yet logged in config/decisions.yaml "
                   "(needs an owner and a date):*")
        for u in rows["unlogged"]:
            out.append("- {0}".format(u["title"]))
        out.append("")
    return "\n".join(out)
