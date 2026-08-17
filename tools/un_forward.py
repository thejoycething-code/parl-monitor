"""The UN forward look: what is coming, and what closes before it.

    python3 tools/un_forward.py             # next 180 days
    python3 tools/un_forward.py --days 90   # a shorter horizon
    python3 tools/un_forward.py --days 3650 # everything published

One chronological list, because that is how a campaign is planned: a call for
input closing three weeks before a Council session is a different thing from
one closing after it, and two separate lists hide that relationship.

Coverage is honest rather than complete. The Human Rights Council is the only
body whose calendar could be read; UPR working groups, treaty bodies, CSW and
the Third Committee are all missing, for the reasons recorded in
src/ingest/un_calendar.py. The footer says so on every run, so an empty
stretch is never mistaken for a quiet UN.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.http import FetchError, HttpClient
from src.ingest import ohchr_calls, un_calendar

sys.path.insert(0, os.path.join(ROOT, "tools"))
from pull_un_calls import areas_for, load_un_filter  # noqa: E402


# Six months. Without a default the UPR list alone runs to January 2031,
# which is a schedule rather than a forward look. --days 3650 for everything.
DEFAULT_HORIZON_DAYS = 180


def main():
    days = DEFAULT_HORIZON_DAYS
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    today = datetime.date.today()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax, wl = load_un_filter()

    rows, gaps = [], []
    try:
        sessions = un_calendar.fetch_sessions(client)
        if not sessions:
            gaps.append("HRC sessions: page parsed to nothing (layout change?)")
        for s in un_calendar.upcoming(sessions, today=today, horizon_days=days):
            rows.append((s.starts, "SESSION", s.name, s.when, "", s.url))
    except FetchError as exc:
        gaps.append("HRC sessions: {0}".format(exc.cause))

    try:
        csw, csw_failures = un_calendar.fetch_csw_sessions(client, today=today)
        gaps.extend(csw_failures)
        for s in un_calendar.upcoming(csw, today=today, horizon_days=days):
            rows.append((s.starts, "SESSION", s.name, s.when, "committee", s.url))
    except FetchError as exc:
        gaps.append("CSW sessions: {0}".format(exc.cause))

    try:
        upr = un_calendar.fetch_upr_sessions(client)
        if not upr:
            gaps.append("UPR sessions: parsed to nothing (layout change?)")
        for s in un_calendar.upcoming(upr, today=today, horizon_days=days):
            rows.append((s.starts, "SESSION", s.name,
                         s.when + " (month only)", "committee", s.url))
    except FetchError as exc:
        gaps.append("UPR sessions: {0}".format(exc.cause))

    try:
        ga = un_calendar.fetch_ga_session(client, today=today)
        if ga and ga.ends >= today and not (days and ga.days_until > days):
            rows.append((ga.starts, "SESSION", ga.name,
                         "{0} to {1} (Third Committee sits within this)".format(
                             ga.starts, ga.ends), "", ga.url))
        elif not ga:
            gaps.append("GA session: page loaded but no session window found")
    except FetchError as exc:
        gaps.append("GA session: {0}".format(exc.cause))

    try:
        deadlines = un_calendar.fetch_treaty_deadlines(client)
        if not deadlines:
            gaps.append("treaty body calendar: parsed to nothing (layout change?)")
        for d in deadlines:
            if d.due < today or (days and (d.due - today).days > days):
                continue
            rows.append((d.due, "TREATY", "{0}: {1} ({2})".format(
                d.treaty, d.country, d.document[:40]),
                "due {0}".format(d.due), "committee" if d.ours else "", d.url))
    except FetchError as exc:
        gaps.append("treaty body calendar: {0}".format(exc.cause))

    try:
        calls = ohchr_calls.fetch_calls(client)
        if not calls:
            gaps.append("calls for input: parsed to nothing (layout change?)")
        for c in ohchr_calls.open_calls(calls, today=today, horizon_days=days):
            areas = areas_for(c, tax, wl)
            rows.append((c.deadline, "DEADLINE", c.title,
                         "closes {0}".format(c.deadline),
                         ",".join(str(a) for a in areas), c.url))
    except FetchError as exc:
        gaps.append("calls for input: {0}".format(exc.cause))

    rows.sort(key=lambda r: r[0])
    horizon = " (next {0} days)".format(days)
    print("UN forward look{0} — {1} item(s)\n".format(horizon, len(rows)))
    for when, kind, title, detail, areas, url in rows:
        left = (when - today).days
        flag = "OURS" if areas else "    "
        print("{0}  {1:>4}d  {2:<8} {3}".format(flag, left, kind, title[:60]))
        # The marker is an area list for calls and the word "committee" for
        # treaty rows; label it rather than printing "areas committee".
        suffix = ""
        if areas == "committee":
            suffix = "  (one of our committees)"
        elif areas:
            suffix = "  areas " + areas
        print("            {0}{1}".format(detail, suffix))
        print("            {0}".format(url))

    print("\nCoverage: Human Rights Council, CSW and UPR working group "
          "sessions, the General Assembly window, treaty body reporting "
          "deadlines (CEDAW/CRC/CCPR flagged), and OHCHR calls for input.")
    print("NOT covered: the Third Committee's item-level schedule, which "
          "exists only as a programme-of-work document. UPR sessions are "
          "MONTH precision only -- the source publishes no days. See "
          "src/ingest/un_calendar.py.")
    if gaps:
        print("\nGAPS ({0}):".format(len(gaps)))
        for g in gaps:
            print("  " + g)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
