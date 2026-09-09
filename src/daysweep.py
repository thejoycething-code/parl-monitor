"""Sweep Hansard one sitting day at a time, and never sweep a day twice.

The problem this replaces. The weekly pull searched all 55 terms over the week just
ended, every week -- re-searching ground it had already covered, and still leaving the
current day unswept, because a week that has not ended is not in the window. Measured on
2026-09-07, the day of the surrogacy debate: Hansard held 25 contributions from 14
members and the ledger held 2.

The unit of new data in Parliament is the SITTING DAY: a speech happens, and it is
final. So a day is swept once, ever, and `sweep_log` remembers it -- including that a
recess day was checked and the House did not sit, so it is never checked again. About
150 sitting days a year at 55 free searches each.

What stays on a rolling window, deliberately. Written questions are answered days or
weeks after they are asked, and Early Day Motion signatures accrue for weeks, so those
sources genuinely change after the fact and a once-only day sweep would freeze them
wrong. Only speeches move here.

One pass, two purposes. The contributions fetched to decide whether a debate is worth a
pack are exactly the rows the ledger wants. They used to be fetched twice.
"""

import datetime

SOURCE = "hansard-speeches"


def sat_that_day(client, house, day):
    """Did `house` sit on `day`? Hansard's sections-for-day list is empty when not.

    There is no sitting-dates endpoint (404 as at 2026-09-09); `lastsittingdate.json`
    gives only the most recent one, so this is the reliable per-day test and it costs
    one call.
    """
    from src.ingest.oral import API
    try:
        rows = client.get_json(
            "{0}/overview/sectionsforday.json?house={1}&date={2}".format(API, house, day.isoformat()),
            "hansard", "sections-{0}-{1}".format(house, day.isoformat()), archive=False)
    except Exception:                                       # noqa: BLE001 - a failure is not a recess
        return None
    return bool(rows)


def already_swept(conn, day, house, source=SOURCE):
    row = conn.execute("SELECT sat, found FROM sweep_log WHERE source=? AND day=? AND house=?",
                       (source, day.isoformat(), house)).fetchone()
    return row if row else None


def record(conn, day, house, sat, found=0, gaps=(), source=SOURCE):
    conn.execute("INSERT OR REPLACE INTO sweep_log (source, day, house, sat, swept_at, found, gaps) "
                 "VALUES (?,?,?,?,?,?,?)",
                 (source, day.isoformat(), house, 1 if sat else 0,
                  datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                  int(found), ", ".join(str(g) for g in gaps) if gaps else None))
    conn.commit()


def pending_days(conn, start, end, houses=("Commons", "Lords"), source=SOURCE, recheck_days=2):
    """[day] still to sweep, oldest first.

    A day already swept is skipped -- unless it is within `recheck_days` of today, because
    Hansard publishes hours after the House rises and revises text afterwards, so a day
    swept the same evening can be incomplete. Weekends are skipped without a call; a
    recorded recess day is never re-checked.
    """
    today = datetime.date.today()
    out = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            seen = [already_swept(conn, day, h, source) for h in houses]
            if any(s is None for s in seen):
                out.append(day)
            elif any(s[0] for s in seen if s) and (today - day).days <= recheck_days:
                out.append(day)                 # sat recently: look again for late text
        day += datetime.timedelta(days=1)
    return out


def sweep_day(client, conn, day, terms, tax, wl, houses=("Commons", "Lords"),
              log=print, write_ledger=True):
    """Sweep one sitting day: ledger every matched contribution, return its candidates.

    One search pass covers BOTH Houses -- Hansard's contribution search is not
    house-scoped -- so the watermark records a row per House but the 55 term searches
    are paid for once. Idempotent: intel.record_event upserts on (member, kind, ref), so
    re-sweeping a day whose text was revised refreshes annotations and adds what is new.

    Returns (candidates, rows_written, gaps).
    """
    from src import debateradar as radar, intel, members
    sat = {}
    for house in houses:
        sat[house] = sat_that_day(client, house, day)
    if all(v is None for v in sat.values()):
        log("  %s: could not tell whether either House sat; leaving the day unrecorded" % day)
        return [], 0, [("sectionsforday", "unavailable")]
    if not any(sat.values()):
        for house in houses:
            record(conn, day, house, sat=False, source=SOURCE)
        log("  %s: neither House sat" % day)
        return [], 0, []
    cands, gaps = radar.candidates(client, day, terms, tax, wl, log=log)
    written = {h: 0 for h in houses}
    if write_ledger:
        cache = {}
        for cand in cands:
            for c in cand.contributions_detail:
                mid = c["member_id"]
                if mid not in cache:
                    try:
                        cache[mid] = members.resolve(conn, client, mid)
                    except Exception:                       # noqa: BLE001
                        cache[mid] = None
                if cache[mid] is None:
                    continue
                intel.record_event(
                    conn, mid, day.isoformat(), "debate", "hansard:%s" % c["ext_id"],
                    intel.annotated_line("Spoke: %s" % cand.title, c["terms"]),
                    areas=c["areas"], excerpt=c["excerpt"])
                written[c.get("house") or cand.house or houses[0]] = \
                    written.get(c.get("house") or cand.house or houses[0], 0) + 1
        conn.commit()
    for house in houses:
        if sat.get(house) is None:
            continue
        record(conn, day, house, sat=bool(sat[house]), found=written.get(house, 0),
               gaps=gaps if sat[house] else (), source=SOURCE)
    total = sum(written.values())
    log("  %s: %d debate(s) on our issues, %d ledger row(s)%s"
        % (day, len(cands), total, ", %d gap(s)" % len(gaps) if gaps else ""))
    return cands, total, gaps


def summary(conn, start, end, source=SOURCE):
    """What the watermark knows about a range, for a report or a DM."""
    rows = conn.execute(
        "SELECT day, house, sat, found, gaps FROM sweep_log WHERE source=? AND day BETWEEN ? AND ? "
        "ORDER BY day, house", (source, start.isoformat(), end.isoformat())).fetchall()
    sat = [r for r in rows if r[2]]
    return {"days_recorded": len(rows), "sitting_days": len(sat),
            "rows": sum(r[3] or 0 for r in sat),
            "with_gaps": [(r[0], r[1], r[4]) for r in rows if r[4]]}
