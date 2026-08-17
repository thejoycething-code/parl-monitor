"""The UN forward look: what is coming, and what closes before it.

    python3 tools/un_forward.py             # sessions + open calls, by date
    python3 tools/un_forward.py --days 90   # next 90 days only

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


def main():
    days = None
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
            rows.append((s.starts, "SESSION", s.name,
                         "{0} to {1}".format(s.starts, s.ends), "", s.url))
    except FetchError as exc:
        gaps.append("HRC sessions: {0}".format(exc.cause))

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
    horizon = " (next {0} days)".format(days) if days else ""
    print("UN forward look{0} — {1} item(s)\n".format(horizon, len(rows)))
    for when, kind, title, detail, areas, url in rows:
        left = (when - today).days
        flag = "OURS" if areas else "    "
        print("{0}  {1:>4}d  {2:<8} {3}".format(flag, left, kind, title[:60]))
        print("            {0}{1}".format(
            detail, "  areas " + areas if areas else ""))
        print("            {0}".format(url))

    print("\nCoverage: Human Rights Council sessions and OHCHR calls for "
          "input only.")
    print("NOT covered: UPR working groups, treaty bodies (CEDAW/CRC), CSW, "
          "Third Committee. See src/ingest/un_calendar.py for why each is "
          "missing -- a quiet stretch here does not mean a quiet UN.")
    if gaps:
        print("\nGAPS ({0}):".format(len(gaps)))
        for g in gaps:
            print("  " + g)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
