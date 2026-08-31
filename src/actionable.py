"""The action-window rule (docs/parl-monitor-devolved-fix.md, 2026-08-31).

Jurisdiction was being used as a proxy for actionability: anything in the
devolved stores was non-actionable by construction, so the NI Religious
Education consultation -- the deliverable on a ministerial commitment
CitizenGO won with 96,328 signatures -- sat in Edition 5's watching brief
with no Campaigns Brief, while a Westminster consultation of the same shape
auto-briefed a week earlier.

Actionability is a property of the ITEM, not of the parliament it came
from. An item is actionable when ALL of:

  1. it has an OPEN response window with a stated closing date in the
     future (consultations, calls for evidence/views; never items that only
     report something -- questions answered, votes recorded, bills passed);
  2. it scores on the issue taxonomy at the threshold already used for
     Westminster items -- here, exactly the same non-empty-areas test the
     Devolved section has always applied, no separate or lowered threshold;
  3. a response is open to us or our supporters, not an invited list.

Everything failing (1) stays exactly where it was: watching brief,
recorded, not briefed. This module touches consultations and calls for
evidence ONLY -- the Holyrood/Senedd bill tracking, committee scrutiny and
questions/votes stores are read by nothing here. The separation guarantee
(devolved tools never write items or mp_events) is untouched: the brief
generator and the edition READ this rule; nothing is injected.
"""

from __future__ import annotations

import datetime
import json

NATION_LABEL = {"scotland": "Scotland", "wales": "Wales", "ni": "N. Ireland"}

# Condition 3, textually: the scraped sources (consult.gov.scot, gov.wales,
# the NI departments) publish PUBLIC consultations, so openness is the
# default by construction; these markers catch the exceptions that say
# otherwise on their face.
INVITED_MARKERS = ("invitation only", "by invitation", "invited participants",
                   "invited parties", "invited stakeholders")

# Deadline-proximity guard: an actionable item FIRST DETECTED with fewer
# than this many days to its deadline is flagged late-detection -- the
# Scottish justice consultation reached an edition with 0 days left, and a
# counter in the edition footer makes that failure mode visible.
LATE_DETECTION_DAYS = 21


def late_detection(first_seen, closes):
    """True when the monitor first saw the item under 21 days from close."""
    if not first_seen or not closes:
        return False
    try:
        gap = (datetime.date.fromisoformat(str(closes)[:10])
               - datetime.date.fromisoformat(str(first_seen)[:10])).days
    except ValueError:
        return False
    return gap < LATE_DETECTION_DAYS


def _open_to_us(title, summary):
    text = " ".join(x for x in (title, summary) if x).lower()
    return not any(marker in text for marker in INVITED_MARKERS)


def devolved_actionable(conn, today, hidden=(11,)):
    """dg_consultations rows meeting the action-window rule, as dicts.

    `today` is the evaluation date (ISO): an item closing today is still
    open -- a response can still be filed. Each dict carries
    `late_detection` so the brief, the top line and the edition footer all
    agree on the flag without recomputing it three ways.
    """
    out = []
    rows = conn.execute(
        "SELECT key, nation, title, url, summary, opened, closes, areas, "
        "tier, first_seen FROM dg_consultations "
        "WHERE closes IS NOT NULL AND closes >= ? ORDER BY closes",
        (today,)).fetchall()
    for r in rows:
        areas = [a for a in json.loads(r["areas"] or "[]") if a not in hidden]
        if not areas:
            continue          # the taxonomy threshold, exactly as it stands
        if not _open_to_us(r["title"], r["summary"]):
            continue
        out.append({
            "key": r["key"], "nation": r["nation"],
            "nation_label": NATION_LABEL.get(r["nation"], r["nation"]),
            "title": r["title"], "url": r["url"], "opened": r["opened"],
            "closes": r["closes"], "areas": areas, "tier": r["tier"],
            "first_seen": r["first_seen"],
            "late_detection": late_detection(r["first_seen"], r["closes"]),
        })
    return out
