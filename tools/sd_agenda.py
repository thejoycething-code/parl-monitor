"""Senedd forward business into sd_agenda: Plenary and committee agendas
from ModernGov's web service, from today to as far ahead as it lists.

    python3 tools/sd_agenda.py                       # today + 56 days
    python3 tools/sd_agenda.py --from 2026-10-19 --to 2026-12-13
    python3 tools/sd_agenda.py --db /tmp/scratch.db  # any store

business.senedd.wales/mgWebService.asmx answers the identified CitizenGO
User-Agent (src/ingest/senedd_agenda.py has the probing), so this client
sends that UA to the host, NOT the browser UA src/http.py keeps for the
host's blocked web pages. robots.txt is asked every run (src/robots_guard).

One GetCommittees, one GetMeetings per live committee and Plenary, one
GetMeeting per meeting in the window. A meeting whose agenda is not
published yet is counted, not stored: there is no business to classify.

Fails loud: a call that cannot be read, or an answer that is not the
service's XML, is a [gap] line and a gaps row (feed sd-agenda), and that
committee's or meeting's stored rows are kept. No committee list read at
all exits 1.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, devolved_agenda as dva, filter as filt, robots_guard  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.ingest import senedd_agenda as sa  # noqa: E402

FEED = "sd-agenda"
TABLE = "sd_agenda"
DEFAULT_DAYS = 56
HOST = "business.senedd.wales"


def rows_for(meeting, items, tax, wl):
    out = []
    body = "Plenary" if meeting.committee_id == sa.PLENARY else meeting.committee
    committee = meeting.committee_id != sa.PLENARY
    for it in items:
        title = sa.english(it.title)
        areas, terms = dva.classify(tax, wl, title, it.text)
        ref = next(iter(re.findall(r"\bNDM\d{4,5}\b", it.text)), None)
        out.append({
            "key": "sd:{0}:{1}".format(meeting.meeting_id, it.item_id),
            "dated": meeting.dated, "item_time": meeting.time if it.order <= 1 else "",
            "body": body, "item_order": it.order, "business": title,
            "detail": ("(private) " if it.restricted else "") + it.text,
            "item_type": dva.item_type(title, it.text, committee),
            "reference": ref, "meeting_id": meeting.meeting_id,
            "url": sa.AGENDA_PAGE.format(meeting.meeting_id), "source": "moderngov",
            "areas": areas, "matched_terms": terms})
    return out


def collect(client, conn, tax, wl, start, end, today, log=print):
    gaps = []
    stats = {"committees": 0, "meetings": 0, "published": 0, "unpublished": 0,
             "rows": 0, "new": 0, "ours": 0, "pruned": 0, "gaps": gaps,
             "source_read": False}

    def gap(detail):
        gaps.append(detail)
        db.record_gap(conn, FEED, detail)

    try:
        committees = sa.parse_committees(client.get_text(
            sa.COMMITTEES_URL, "senedd", "ws-committees", archive=False))
    except (FetchError, sa.ServiceShapeError) as exc:
        gap("GetCommittees: {0}".format(getattr(exc, "cause", exc)))
        return stats
    if not committees:
        gap("GetCommittees: answered but listed no live committee")
        return stats
    stats["source_read"] = True
    s_from, s_to = sa.window(start, end)
    for cid, title, _cat in committees:
        try:
            meetings = sa.parse_meetings(client.get_text(
                sa.MEETINGS_URL.format(cid, s_from, s_to), "senedd",
                "ws-meetings-{0}".format(cid), archive=False), cid, title)
        except (FetchError, sa.ServiceShapeError) as exc:
            gap("GetMeetings {0} ({1}): {2}".format(cid, title[:40], getattr(exc, "cause", exc)))
            continue
        stats["committees"] += 1
        listed = set()
        for m in meetings:
            if not m.dated or not (start.isoformat() <= m.dated <= end.isoformat()):
                continue
            if m.status.lower().startswith("cancel"):
                continue
            listed.add(m.meeting_id)
            stats["meetings"] += 1
            try:
                published, _loc, items = sa.parse_meeting(client.get_text(
                    sa.MEETING_URL.format(m.meeting_id), "senedd",
                    "ws-meeting-{0}".format(m.meeting_id), archive=False))
            except (FetchError, sa.ServiceShapeError) as exc:
                gap("GetMeeting {0} ({1} {2}): {3}".format(
                    m.meeting_id, title[:30], m.dated, getattr(exc, "cause", exc)))
                continue
            if not published or not items:
                stats["unpublished"] += 1
            else:
                stats["published"] += 1
            for row in rows_for(m, items, tax, wl):
                stats["new"] += dva.upsert(conn, TABLE, row, today)
                stats["rows"] += 1
                if row["areas"] or row["matched_terms"]:
                    stats["ours"] += 1
            stats["pruned"] += dva.prune_unseen(conn, TABLE, today, "meeting_id = ?",
                                                [m.meeting_id])
        # A meeting this committee no longer lists in the window (cancelled,
        # moved out) takes its rows with it.
        body = "Plenary" if cid == sa.PLENARY else title
        marks = ",".join("?" * len(listed)) or "''"
        stats["pruned"] += dva.prune_unseen(
            conn, TABLE, today,
            "body = ? AND dated BETWEEN ? AND ? AND meeting_id NOT IN ({0})".format(marks),
            [body, start.isoformat(), end.isoformat()] + sorted(listed))
        conn.commit()
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="start", type=datetime.date.fromisoformat)
    ap.add_argument("--to", dest="end", type=datetime.date.fromisoformat)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    args = ap.parse_args(argv)
    today = datetime.date.today()
    start = args.start or today
    end = args.end or (start + datetime.timedelta(days=args.days))

    conn = db.init_db(db.connect(args.db))
    raw = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    # The web service answers our own UA: send it, not the browser override.
    raw.host_user_agents.pop(HOST, None)
    raw.set_host_throttle(HOST, 1.0)
    raw.add_redirect_guard(dva.official_only((HOST,)))
    client = robots_guard.guard(raw, FEED)
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    print("Senedd forward business {0} to {1}".format(start, end))
    s = collect(client, conn, tax, wl, start, end, today.isoformat())
    held = conn.execute("SELECT COUNT(*) FROM sd_agenda WHERE dated >= ?",
                        (start.isoformat(),)).fetchone()[0]
    print("{0} committee list(s) read; {1} meeting(s) in the window, {2} with an agenda "
          "published, {3} not yet; {4} agenda item(s) stored ({5} new), {6} match our "
          "areas; {7} stale row(s) removed; {8} held from {9}.".format(
              s["committees"], s["meetings"], s["published"], s["unpublished"], s["rows"],
              s["new"], s["ours"], s["pruned"], held, start))
    print("no gaps." if not s["gaps"] else "{0} gap(s) -- printed above.".format(len(s["gaps"])))
    return 0 if s["source_read"] else 1


if __name__ == "__main__":
    sys.exit(main())
