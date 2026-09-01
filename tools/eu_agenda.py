"""EU plenary forward look: what the Parliament will debate and vote.

    python3 tools/eu_agenda.py

Phase 2b of the EU monitor -- the coming-up analog, and where Caroline's
1-2 month forward look lands (her ask, 2026-08-28): the EP publishes its
plenary calendar for the whole year and each sitting's foreseen agenda
weeks ahead, in English, through the Open Data API. The Westminster
Order Paper gives days; this gives WEEKS.

Method: sittings for a 90-day horizon (60 until 2026-09-01; Christopher: extend the forward look for both monitors) from /meetings (one call, two when
the horizon crosses a year boundary), then one /foreseen-activities call
per future sitting (~12 in a typical month-pair). Every activity label is
taxonomy-matched; matches surface in the EU edition's "Coming up" with
the sitting date, the rest are counted per sitting -- never silently
dropped, never printed at 100 rows a sitting either.

Committee agendas (LIBE/FEMM/JURI/EMPL) are NOT here yet: EP Open Data
carries no committee meetings, and the eMeeting service is an Angular
shell whose backend the 2026-09-01 probe did not find. Recorded as an
open probe in docs/eu-monitor-spec.md.

Separation guarantee: writes eu_agenda only.
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

MEETINGS = ("https://data.europarl.europa.eu/api/v2/meetings"
            "?year={0}&limit=500&format=application%2Fld%2Bjson")
FORESEEN = ("https://data.europarl.europa.eu/api/v2/meetings/{0}"
            "/foreseen-activities?format=application%2Fld%2Bjson")
HORIZON_DAYS = 90


def future_sittings(client, today, log=print):
    """Plenary sitting ids inside the horizon, from the year calendar(s)."""
    t = datetime.date.fromisoformat(today)
    end = t + datetime.timedelta(days=HORIZON_DAYS)
    years = sorted({t.year, end.year})
    out = []
    for y in years:
        reply = client.get_json(MEETINGS.format(y), "eu-agenda",
                                "meetings-{0}".format(y), archive=False)
        for m in reply.get("data") or []:
            d = m.get("activity_date")
            if d and today <= d <= end.isoformat():
                out.append((m["activity_id"], d))
    return sorted(out, key=lambda x: x[1])


def pull(conn, client, today, log=print):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    try:
        sittings = future_sittings(client, today, log)
    except FetchError as exc:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                     "VALUES (?,?,?)", (today, "eu-agenda", str(exc.cause)))
        conn.commit()
        log("  [gap] eu-agenda calendar: {0}".format(exc.cause))
        return 0, 0, 0
    total = ours = gaps = 0
    for sid, date in sittings:
        try:
            reply = client.get_json(FORESEEN.format(sid), "eu-agenda", sid,
                                    archive=False)
        except ValueError:
            # A sitting whose agenda is not yet published answers 204 with
            # an EMPTY body (measured live: October sittings on 1 Sep).
            # Expected, not a gap: the agenda will appear as the date nears.
            continue
        except FetchError as exc:
            if "404" in str(exc.cause):
                # Also not-yet-published: some future sittings 404 rather
                # than 204 (measured live: 20 Oct on 1 Sep, while its
                # sibling sittings answered 204).
                continue
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (today, "eu-agenda", "{0}: {1}".format(sid,
                                                                exc.cause)))
            log("  [gap] {0}: {1}".format(sid, exc.cause))
            gaps += 1
            continue
        for a in (reply or {}).get("data") or []:
            label = (a.get("activity_label") or {}).get("en")
            if not label:
                continue
            total += 1
            res = filt.filter_item(tax, wl, label)
            areas = res.issue_areas or []
            if areas:
                ours += 1
            conn.execute(
                "INSERT INTO eu_agenda (activity_id, sitting_id, date, "
                "label, activity_type, areas, matched_terms, tier, "
                "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(activity_id) DO UPDATE SET label=excluded.label, "
                "date=excluded.date, activity_type=excluded.activity_type, "
                "areas=excluded.areas, matched_terms=excluded.matched_terms, "
                "tier=excluded.tier, last_seen=excluded.last_seen",
                (a.get("activity_id"), sid, date, label,
                 (a.get("had_activity_type") or "").rsplit("/", 1)[-1],
                 json.dumps(areas), json.dumps(res.matched_terms or []),
                 res.tier, today, today))
    conn.commit()
    return total, ours, gaps


def coming_up(conn, today):
    """The edition's forward look: matched items dated, the rest counted."""
    rows = conn.execute("SELECT * FROM eu_agenda WHERE date >= ? "
                        "ORDER BY date, activity_id", (today,)).fetchall()
    matched = [r for r in rows if json.loads(r["areas"] or "[]")]
    per_day = {}
    for r in rows:
        per_day[r["date"]] = per_day.get(r["date"], 0) + 1
    return matched, per_day


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    total, ours, gaps = pull(conn, client, today)
    print("eu-agenda: {0} foreseen items inside {1} days, {2} on our "
          "ground, {3} gap(s).".format(total, HORIZON_DAYS, ours, gaps))
    matched, per_day = coming_up(conn, today)
    for r in matched:
        print("  [{0}] {1} - {2} ({3})".format(
            ",".join(str(a) for a in json.loads(r["areas"])), r["date"],
            r["label"][:80], r["activity_type"]))
    if not matched:
        print("  nothing on our ground; sittings with published agendas: "
              + ", ".join("{0} ({1})".format(d, n)
                          for d, n in sorted(per_day.items())))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
