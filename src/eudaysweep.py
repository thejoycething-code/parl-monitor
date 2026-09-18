"""Sweep the European Parliament one sitting day at a time, and never twice.

The gap this closes. Westminster has been swept per sitting day since 9
September; the EU ran weekly, so a Tuesday plenary waited until Saturday even
when everything worked. On 17 September it was worse than that: the weekly had
been cancelled for eleven days and the 15 September sitting -- 87 roll calls on
our ground, the Democracy Shield report adopted 420-220 -- sat uncollected until
somebody went looking.

What moves per day, and what deliberately does not. A roll call is final the
moment the President reads it out, and an adopted text is published the same
day: those are day-final, so they are swept once per sitting day and remembered.
Written questions are answered weeks after they are tabled, ECI signatures
accrue, dossiers move between readings, and consultations open and close on
their own clock -- all of those genuinely change after the fact, so a
once-per-day sweep would freeze them wrong and they stay on the weekly rolling
window, exactly as Hansard's questions and Early Day Motions do.

Why a calendar rather than a per-day probe. Hansard has no sitting-dates
endpoint, so Westminster asks each day whether the House sat. The Parliament
publishes its meetings for a whole year in one call, so a year of sitting dates
costs one request and is cached for the run. The EP sits in blocks -- four days
in Strasbourg, the odd Brussels mini-plenary -- so most days are not sittings
and cost nothing at all.

Sharing sweep_log with Hansard, under its own source. `house` is 'EP'.
"""

import datetime

from src import daysweep

SOURCE = "ep-plenary"
HOUSE = "EP"

MEETINGS = ("https://data.europarl.europa.eu/api/v2/meetings"
            "?year={0}&limit=500&format=application%2Fld%2Bjson")


def sitting_dates(client, year, cache=None):
    """{ISO date} the Parliament met in `year`. One call, cached per run."""
    if cache is not None and year in cache:
        return cache[year]
    out = set()
    try:
        reply = client.get_json(MEETINGS.format(year), "eu-daysweep",
                                "meetings-{0}".format(year), archive=False)
    except Exception:                                       # noqa: BLE001
        # A failure is not a recess: return nothing and let the day stay
        # pending, rather than recording it as "did not sit" for ever.
        return None
    for m in (reply or {}).get("data") or []:
        d = m.get("activity_date")
        if d:
            out.add(d)
    if cache is not None:
        cache[year] = out
    return out


def pending_days(conn, start, end, recheck_days=2):
    """[day] still to sweep, oldest first. Weekends included: the Parliament
    does not sit at weekends, but its calendar decides that, not the clock --
    and a recorded non-sitting day is never asked about again."""
    today = datetime.date.today()
    out = []
    day = start
    while day <= end:
        seen = daysweep.already_swept(conn, day, HOUSE, SOURCE)
        if seen is None:
            out.append(day)
        elif seen[0] and (today - day).days <= recheck_days:
            out.append(day)          # sat recently: roll calls publish late
        day += datetime.timedelta(days=1)
    return out


def sweep_day(conn, client, day, log=print, cache=None):
    """Collect one sitting day's roll calls and adopted texts.

    Returns (sat, divisions_on_our_ground, texts_on_our_ground, gaps). A day the
    Parliament did not sit is recorded as such and costs no further call.
    """
    iso = day.isoformat()
    dates = sitting_dates(client, day.year, cache)
    if dates is None:
        log("  {0}: calendar unavailable; leaving the day pending".format(iso))
        return None, 0, 0, 1
    if iso not in dates:
        daysweep.record(conn, day, HOUSE, sat=False, source=SOURCE)
        return False, 0, 0, 0
    import importlib.util
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _tool(name):
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(root, "tools", name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    gaps = 0
    # Texts and their bodies FIRST, roll calls second. A vote item whose
    # label matches nothing inherits the areas of its adopted text
    # (eu_rollcalls.inherit_from_text), and that only works if the text has
    # been read when the roll calls are pulled. The first cut ran them the
    # other way round and would have left the 16 Sept gender-and-health roll
    # calls uncollected until the recheck night.
    texts = _tool("eu_texts")
    _total, ours = texts.pull(conn, client, iso, log=log, on_day=iso)
    # Read the bodies the same night. Adopted texts are matched on their title
    # by the collector and Parliament's titles are generic, so the body is where
    # the subject actually is; a text read the night it passes is a text the
    # Saturday edition can already place. Capped, and a text is read once.
    try:
        _read, gained, _failed = texts.read_bodies(conn, client, iso, log=log,
                                                   limit=texts.BODY_LIMIT)
        ours += gained
    except Exception as exc:                                # noqa: BLE001
        log("  [body] pass failed: {0}".format(str(exc)[:80]))
        gaps += 1
    rolls = _tool("eu_rollcalls")
    _seen, matched, g = rolls.pull(conn, client, iso, log=log, days=1, on_day=iso)
    gaps += g
    daysweep.record(conn, day, HOUSE, sat=True, found=matched + ours,
                    gaps=(["roll-call fetch"] if gaps else ()), source=SOURCE)
    return True, matched, ours, gaps


def summary(conn, start, end):
    rows = conn.execute(
        "SELECT day, sat, found FROM sweep_log WHERE source=? AND house=? "
        "AND day BETWEEN ? AND ? ORDER BY day",
        (SOURCE, HOUSE, start.isoformat(), end.isoformat())).fetchall()
    sat = [r for r in rows if r[1]]
    return {"days_checked": len(rows), "sittings": len(sat),
            "found": sum(r[2] or 0 for r in sat)}
