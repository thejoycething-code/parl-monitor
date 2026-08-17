"""Store the UN forward calendar, and work out what changed since last time.

Without this the calendar is a snapshot: every run prints the same fifteen
calls and the same session dates, and a weekly message would be indist-
inguishable week to week. What a reader needs is the diff -- what is NEW, what
MOVED, and what has QUIETLY DISAPPEARED.

Three rules the implementation turns on:

  * ids never contain the date. A deadline that slips then shows up as one row
    changing rather than as one row vanishing and a new one appearing, which
    is both the truth and the more useful reading.
  * "new" is a set difference against the ids already stored, not a test on
    first_seen. first_seen is backfilled when the column is added and is
    equal to today for every row on that day, which made exactly this test
    report an entire store as new once already (see brief_log, 2026-08-17).
  * disappearance is only claimed WITHIN the window that was actually
    fetched. A session in 2029 is absent from a 180-day query because it was
    never asked for, not because it was cancelled.
"""

from __future__ import annotations

import datetime
import json


def item_id(kind, *parts):
    """A stable id. Deliberately excludes dates -- see the module docstring."""
    clean = [str(p).strip().lower().replace(" ", "-") for p in parts if p]
    return "{0}:{1}".format(kind, ":".join(clean))


def record(conn, items, today=None):
    """Upsert forward-calendar items; return (new_ids, moved).

    `items` are dicts with id/kind/title/body/starts/ends/approximate/areas/url.
    `moved` lists (id, title, old_starts, new_starts) for items whose date
    changed, which is the signal a slipping deadline gives off.
    """
    today = (today or datetime.date.today()).isoformat()
    before = {r["id"]: r for r in conn.execute(
        "SELECT id, starts, ends FROM un_calendar")}
    moved = []
    for it in items:
        prior = before.get(it["id"])
        if prior and (prior["starts"] != it.get("starts")
                      or prior["ends"] != it.get("ends")):
            moved.append((it["id"], it.get("title"), prior["starts"], it.get("starts")))
        conn.execute(
            "INSERT INTO un_calendar (id, kind, title, body, starts, ends, "
            "approximate, areas, url, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            # first_seen is absent from the update list on purpose: it records
            # when we first saw the item and a re-read must not move it.
            "ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, title=excluded.title, "
            "body=excluded.body, starts=excluded.starts, ends=excluded.ends, "
            "approximate=excluded.approximate, areas=excluded.areas, "
            "url=excluded.url, last_seen=excluded.last_seen, gone_at=NULL",
            (it["id"], it["kind"], it.get("title"), it.get("body"),
             it.get("starts"), it.get("ends"),
             1 if it.get("approximate") else 0,
             json.dumps(it.get("areas") or []), it.get("url"), today, today))
    conn.commit()
    new_ids = {it["id"] for it in items} - set(before)
    return new_ids, moved


def mark_gone(conn, horizon_end, today=None, seen_ids=None):
    """Flag still-future items inside the fetched window that stopped appearing.

    Scoped to the window on purpose. Anything starting after horizon_end was
    not requested this run, so its absence says nothing; treating that as a
    cancellation would raise a false alarm every time the horizon shortened.
    """
    today = (today or datetime.date.today()).isoformat()
    rows = conn.execute(
        "SELECT id, kind, title, starts FROM un_calendar "
        "WHERE gone_at IS NULL AND last_seen < ? AND starts >= ? AND starts <= ?",
        (today, today, horizon_end.isoformat())).fetchall()
    gone = [r for r in rows if not seen_ids or r["id"] not in seen_ids]
    for row in gone:
        conn.execute("UPDATE un_calendar SET gone_at = ? WHERE id = ?",
                     (today, row["id"]))
    conn.commit()
    return gone


def summarise(conn, new_ids, moved, gone):
    """Lines for a human, or [] when nothing changed.

    Returning nothing when nothing changed is the point: a weekly message that
    always has content trains people to stop reading it.
    """
    lines = []
    if new_ids:
        rows = conn.execute(
            "SELECT kind, title, starts, url, areas FROM un_calendar "
            "WHERE id IN ({0}) ORDER BY starts".format(
                ",".join("?" * len(new_ids))), tuple(new_ids)).fetchall()
        lines.append("NEW ({0}):".format(len(rows)))
        for r in rows:
            areas = json.loads(r["areas"] or "[]")
            lines.append("  {0} {1} {2}{3}".format(
                r["starts"], r["kind"].upper(), (r["title"] or "")[:70],
                "  areas " + ",".join(str(a) for a in areas) if areas else ""))
    for _id, title, was, now in moved:
        lines.append("MOVED: {0} — {1} -> {2}".format((title or "")[:60], was, now))
    for r in gone:
        lines.append("NO LONGER LISTED: {0} {1} (was {2})".format(
            r["kind"].upper(), (r["title"] or "")[:60], r["starts"]))
    return lines
