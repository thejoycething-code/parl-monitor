"""Devolved government consultations: open calls in Scotland, Wales and NI.

    python3 tools/dg_consultations.py                 # all three nations
    python3 tools/dg_consultations.py --nation wales

Executive consultations (governments, not parliaments), so they live in
their own dg_consultations table and surface in each nation's monitor --
never in items/mp_events, so nothing here can reach the published digest.

Fetch discipline: listings are cheap; the closing date lives only on the
detail page, so each NEW consultation costs one detail fetch and a key
already holding a closing date is never refetched. Everything is stored
(the open sets are small); classification runs on title + listing summary
and marks OURS in the monitors. All pages fetch with archive=False -- the
db is the archive, and gov.wales detail pages are 240KB each.

CADENCE: WEEKLY, AND DELIBERATELY SO (Christopher, 24 September 2026:
"Keep devolved consultations in a weekly sweep as they run for a long time").
Each nation's consultations are collected by that nation's weekly workflow --
Saturdays for NI, Thursdays for Wales, Fridays for Scotland -- so an item
opening the day after a sweep waits up to six days to be seen.

That was questioned when NI consultations surfaced late, and the answer is
that the lateness had nothing to do with cadence: the fetch read page one
only, so anything below Citizen Space's 30-row page was invisible however
often it ran. The NI weekly ran on 29 August AND 5 September without seeing a
consultation that had been open since 24 August. Pagination fixed that, and
late-by went from 16-52 days to 1-3.

The window lengths say the weekly sweep is right. Measured 24 September 2026
over 166 stored consultations:

    Scotland   15 rows   average window 86 days   shortest 30
    Wales      28 rows   average window 78 days   shortest 28
    NI        123 rows   average window 682 days  shortest 7

Only two NI consultations run under a fortnight, and every one of the
shortest is a job fair, a bursary form or an event evaluation -- areas is []
on all of them. Nothing on our ground has a window a weekly sweep endangers:
the shortest REAL consultation is four weeks, so six days of latency costs at
most a fifth of it and usually far less.

Do not move these to the daily sweep without new evidence. The thing to watch
is not the calendar but the shortest window that ever carries an area: if one
appears under 14 days, this reasoning expires.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import FetchError, HttpClient
from src.ingest import devolved

# A consultation on our ground opening with this long or less to run means
# the weekly sweep can no longer be justified by window length. Fourteen
# days: six of latency out of fourteen is not a margin anyone should accept
# on something we might campaign on.
SHORT_WINDOW_DAYS = 14


def _window_days(opened, closes):
    """How long the consultation runs, or None when either date is missing."""
    import datetime as _dt
    try:
        return (_dt.date.fromisoformat(closes)
                - _dt.date.fromisoformat(opened)).days
    except (TypeError, ValueError):
        return None

WALES_MAX_PAGES = 10    # ~5 pages of open consultations in 2026; cap, don't spin

# THE CITIZEN SPACE FINDERS PAGINATE (21 September 2026). Northern Ireland's
# listing was serving 107 open consultations over four pages and this fetched
# the first, so 56 of them had never been stored at all -- not seen late,
# never seen. Items rise onto page one only as the ones above them close, so
# the monitor was meeting a consultation near the end of its life: the Good
# Relations framework opened on 24 August, surfaced on 12 September and its
# brief reached Drive on the closing day. Scotland's 13 still fit one page;
# it pages by the same rule the day it does not.
CITIZEN_SPACE_BATCH = 30     # the finder's own page size, counted by b_start
CITIZEN_SPACE_MAX_PAGES = 12


def fetch_open(client, nation, log):
    if nation in ("scotland", "ni"):
        url = devolved.SOURCES[nation]
        host = url.split("/consultation_finder")[0]
        out, seen, page = [], set(), 0
        while page < CITIZEN_SPACE_MAX_PAGES:
            start = page * CITIZEN_SPACE_BATCH
            html = client.get_text(
                url if not start else "{0}&b_start={1}".format(url, start),
                "dg-consultations",
                nation if not start else "{0}-b{1}".format(nation, start),
                archive=False)
            batch = devolved.parse_citizen_space_finder(html, nation, host)
            # STOP ON NOTHING NEW, not merely on an empty page. Citizen Space
            # ignores a parameter it does not know and serves page one again:
            # ?page=2 returns the same thirty rows, which is what hid the
            # pagination in the first place. If b_start is ever renamed this
            # loop ends after one wasted fetch instead of collecting the
            # first page twelve times.
            fresh = [c for c in batch if c.key not in seen]
            if not fresh:
                break
            out.extend(fresh)
            seen.update(c.key for c in fresh)
            page += 1
        else:
            log("  [gap] {0} listing still returning new items at page {1} "
                "-- capped, later pages unseen".format(
                    nation, CITIZEN_SPACE_MAX_PAGES))
        return out
    out, page = [], 0
    while page < WALES_MAX_PAGES:
        html = client.get_text(devolved.SOURCES["wales"].format(page),
                               "dg-consultations", "wales-p{0}".format(page),
                               archive=False)
        batch = devolved.parse_govwales_index(html)
        if not batch:
            break
        out.extend(batch)
        page += 1
    else:
        log("  [gap] wales listing still returning items at page {0} -- "
            "capped, later pages unseen".format(WALES_MAX_PAGES))
    return out


def main():
    nations = ["scotland", "wales", "ni"]
    if "--nation" in sys.argv:
        nations = [sys.argv[sys.argv.index("--nation") + 1]]

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    now = datetime.date.today().isoformat()

    total = new = ours = gaps = 0

    short = []
    for nation in nations:
        try:
            found = fetch_open(client, nation, print)
        except FetchError as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (now, "dg-consultations",
                          "{0}: {1}".format(nation, exc.cause)))
            conn.commit()
            print("  [gap] {0}: {1}".format(nation, exc.cause))
            gaps += 1
            continue
        known = {r[0]: r[1] for r in conn.execute(
            "SELECT key, closes FROM dg_consultations WHERE nation = ?",
            (nation,))}
        for c in found:
            total += 1
            if c.key not in known or not known[c.key]:
                # One detail fetch per new (or dateless) consultation.
                try:
                    html = client.get_text(c.url, "dg-consultations",
                                           "detail", archive=False)
                    if nation == "wales":
                        c.opened, c.closes = devolved.parse_govwales_detail(html)
                    else:
                        c.opened, c.closes = devolved.parse_citizen_space_detail(html)
                except FetchError as exc:
                    print("  [gap] detail {0}: {1}".format(c.url, exc.cause))
                    gaps += 1
            res = filt.filter_item(tax, wl, "{0} {1}".format(c.title,
                                                             c.summary))
            areas = res.issue_areas or []
            if areas:
                ours += 1
                # THE TRIPWIRE FOR THE WEEKLY CADENCE. These are swept once a
                # week on purpose, because the shortest consultation on our
                # ground measured four weeks and six days of latency costs a
                # fifth of that at worst. The premise is the WINDOW LENGTH,
                # not the calendar -- so the moment something on our ground
                # opens with a fortnight or less to run, the reasoning has
                # expired and whoever sees this needs to know.
                window = _window_days(c.opened, c.closes)
                if window is not None and window <= SHORT_WINDOW_DAYS:
                    short.append((nation, window, c.closes, c.title))
            if c.key not in known:
                new += 1
            conn.execute(
                "INSERT INTO dg_consultations (key, nation, title, url, "
                "summary, opened, closes, areas, matched_terms, tier, "
                "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET title=excluded.title, "
                "summary=excluded.summary, "
                "opened=COALESCE(excluded.opened, opened), "
                "closes=COALESCE(excluded.closes, closes), "
                "areas=excluded.areas, matched_terms=excluded.matched_terms, "
                "tier=excluded.tier, last_seen=excluded.last_seen",
                (c.key, nation, c.title, c.url, c.summary, c.opened,
                 c.closes, json.dumps(areas),
                 json.dumps(res.matched_terms or []), res.tier, now, now))
        conn.commit()
        print("{0}: {1} open consultation(s) listed.".format(
            nation, len(found)))

    if short:
        print("")
        print("SHORT WINDOW ON OUR GROUND -- the weekly cadence was justified "
              "by consultations running for months (Christopher, 24 September "
              "2026). These do not, so that reasoning no longer covers them:")
        for nation, window, closes, title in sorted(short, key=lambda x: x[1]):
            print("  {0} {1} day(s), closes {2}: {3}".format(
                nation, window, closes, (title or "?")[:60]))
    print("\n{0} open consultation(s) across {1} nation(s); {2} new, {3} on "
          "our ground by title+summary.".format(total, len(nations), new,
                                                ours))
    dateless = conn.execute("SELECT COUNT(*) FROM dg_consultations WHERE "
                            "closes IS NULL AND last_seen = ?",
                            (now,)).fetchone()[0]
    if dateless:
        print("{0} still carry NO closing date (detail parse failed) -- "
              "shown dateless, never guessed.".format(dateless))
    print("no gaps." if not gaps else
          "{0} gap(s) -- printed above.".format(gaps))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
