"""MP intelligence ledger: one mp_events row per parliamentary contribution.

Coverage is ALL parliamentarians active on our issues (Christopher,
2026-08-03) -- the watchlist confers no special marking here; a peer we have
never heard of asking the right question is exactly the intelligence wanted.

The weekly edition section and the per-member timelines are both queries over
this ledger, the same digest-as-byproduct principle as everything else.
"""

from __future__ import annotations


def ensure_index(conn):
    """Dedupe guard: one row per (member, kind, ref)."""
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_mp_events "
                 "ON mp_events(member_id, kind, ref)")
    conn.commit()


def record_event(conn, member_id, date, kind, ref, line):
    """Insert a ledger row; silently idempotent on re-runs and backfills."""
    ensure_index(conn)
    conn.execute(
        "INSERT OR IGNORE INTO mp_events (member_id, date, kind, ref, line) "
        "VALUES (?, ?, ?, ?, ?)",
        (member_id, date, kind, ref, (line or "")[:200]))
    conn.commit()


def events_for_week(conn, week_start, week_end):
    """Ledger rows in a date window, joined to the members cache."""
    return conn.execute(
        "SELECT e.member_id, e.date, e.kind, e.ref, e.line, "
        "m.name, m.party, m.seat, m.house "
        "FROM mp_events e LEFT JOIN members m ON m.id = e.member_id "
        "WHERE e.date >= ? AND e.date <= ? ORDER BY e.date DESC, m.name",
        (week_start, week_end)).fetchall()


def member_timeline(conn, member_id, limit=50):
    return conn.execute(
        "SELECT date, kind, ref, line FROM mp_events WHERE member_id = ? "
        "ORDER BY date DESC LIMIT ?", (member_id, limit)).fetchall()


def ledger_stats(conn):
    row = conn.execute(
        "SELECT COUNT(*) AS events, COUNT(DISTINCT member_id) AS members, "
        "MIN(date) AS earliest, MAX(date) AS latest FROM mp_events").fetchone()
    return dict(row)
