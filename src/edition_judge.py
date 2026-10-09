"""The free session judge's scores for the country editions and the Latam monitor.

Chris, 10 October 2026: the paid AI judge stays off (X16, docs/country-
decisions-2026-10-10.md), and the free session judge built for the provinces
(Claude Code on the Mac Mini, on the claude.ai plan allowance, no API key,
no per-call cost; src/session_queue.py, tools/session_judge.sh) is adopted
for the fifteen weekly country editions and the Latam monitor instead.

ONE IMPLEMENTATION, KEYED BY COUNTRY CODE. tools/edition_judge.py writes the
pending items of every edition to one queue (--queue-out) and applies a
filled-in queue (--queue-in); jobs/editions-session-judge.sh runs it once a
week. This module holds what the renderers read:

  * edition_scores (src/db.py): one row per item, ever, keyed
    '<cc>:<kind>:<key>' (item_id), with the score 0-3, the why-line, the
    model ('claude-code-session') and the day it was scored.
  * annotate(): puts the score and why-line on each item as `judge` and
    `judge_why`. A vote group (one bill's amendments and final vote) is
    scored once, on the item the queue offered, and the score holds for the
    whole group.
  * split(): an item the judge scored 0 leaves the edition (counted under
    Coverage), except a watched item, which nothing but its own mute removes.
  * leads(): a judged item leads when watched or scored 3, or scored 2 with
    the minimum evidence; an unjudged item leads as before.

Unscored items render exactly as before (the stub triage, ordered by tier):
when the judge does not run, nothing changes. Read-only on the store; the
table is missing from an older store and then nothing is scored.
"""

from __future__ import annotations

import datetime
import re

from src import latam

TABLE = "edition_scores"
SESSION_MODEL = "claude-code-session"
DROP_REASON = "scored 0 by the judge"
# The fifteen weekly country editions (src/editions/<cc>.py) and the Latam
# monitor's countries with a store (src/latam.py).
EDITION_CCS = ("es", "it", "fr", "nl", "be", "at", "ch", "pl", "pt", "hr", "sk", "hu", "br",
               "ar", "mx")
LATAM_CCS = tuple(latam.COLLECTED) + ("ve", "nic")
# The judge counts as running while it has scored within this many days; the
# Latam alerts hold an unscored tier-1 item for it only then (tools/latam_alerts.py).
ALIVE_DAYS = 14


def item_id(it):
    """'<cc>:<kind>:<key>', whitespace folded to '_' (a queue id is one word)."""
    return re.sub(r"\s+", "_", "{0}:{1}:{2}".format(it["cc"], it["kind"], it["key"]).strip())


def load(conn, ccs=None):
    """{item id: (score, why)}; {} when the table is missing."""
    sql = "SELECT item, cc, score, why FROM {0}".format(TABLE)
    out = {}
    for r in latam.rows(conn, sql):
        if ccs is None or r[1] in ccs:
            out[r[0]] = (int(r[2]), r[3] or "")
    return out


def annotate(conn, items, scores=None):
    """Put `judge` (0-3 or None) and `judge_why` on each item; returns items."""
    if not items:
        return items
    if scores is None:
        scores = load(conn, {it["cc"] for it in items})
    by_group = {}
    for it in items:
        got = scores.get(item_id(it))
        if got and it.get("group"):
            k = (it["cc"], it["group"])
            if k not in by_group or got[0] > by_group[k][0]:
                by_group[k] = got
    for it in items:
        got = scores.get(item_id(it))
        if got is None and it.get("group"):
            got = by_group.get((it["cc"], it["group"]))
        it["judge"], it["judge_why"] = (got if got else (None, None))
    return items


def split(items):
    """(kept, dropped): an unwatched item the judge scored 0 is dropped, with
    its reason under "dropped", as the noise filters drop theirs."""
    kept, dropped = [], []
    for it in items:
        if it.get("judge") == 0 and not it.get("watched"):
            dropped.append(dict(it, dropped=DROP_REASON))
        else:
            kept.append(it)
    return kept, dropped


def rank(it):
    """The order score: the judge's where it has read the item, else the stub's."""
    j = it.get("judge")
    return j if j is not None else it.get("score", 0)


def leads(it, evidence, muted=False):
    """Whether an item leads its edition. `evidence` is the noise filters'
    alert_reason for it (None when it lacks the minimum evidence or is
    muted); `muted`, whether the mute list names it."""
    j = it.get("judge")
    if j is None:
        return bool(evidence)
    if muted:
        return False
    return bool(it.get("watched") or j >= 3 or (j == 2 and evidence))


def judged(items):
    return sum(1 for it in items if it.get("judge") is not None)


def why_line(it):
    """'_Judge 3/3: ..._' for a judged item, else None."""
    if it.get("judge") is None:
        return None
    why = latam.clean(it.get("judge_why"))
    return "_Judge {0}/3{1}_".format(it["judge"], ": " + why if why else "")


def alive(conn, today, days=ALIVE_DAYS):
    """True when the session judge has scored anything in the last `days`."""
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()
    got = latam.rows(conn, "SELECT 1 FROM {0} WHERE model=? AND substr(scored_at,1,10) >= ? "
                           "LIMIT 1".format(TABLE), (SESSION_MODEL, since))
    return bool(got)


def write(conn, cc, iid, score, why, today, model=SESSION_MODEL):
    """Store one score, once ever. Returns True when written."""
    cur = conn.execute("INSERT OR IGNORE INTO {0} (item, cc, score, why, model, scored_at) "
                       "VALUES (?,?,?,?,?,?)".format(TABLE), (iid, cc, int(score), why, model,
                                                               today))
    return cur.rowcount == 1
