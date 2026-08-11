"""MP intelligence ledger: one mp_events row per parliamentary contribution.

Coverage is ALL parliamentarians active on our issues (Christopher,
2026-08-03) -- the watchlist confers no special marking here; a peer we have
never heard of asking the right question is exactly the intelligence wanted.

The weekly edition section and the per-member timelines are both queries over
this ledger, the same digest-as-byproduct principle as everything else.
"""

from __future__ import annotations

import json


def ensure_index(conn):
    """Dedupe guard: one row per (member, kind, ref)."""
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_mp_events "
                 "ON mp_events(member_id, kind, ref)")
    conn.commit()


def annotated_line(line, matched_terms):
    """Append the matched term when the line does not already show it.

    A tier-1 match can live in a PQ's answer text while the heading reads
    "Home Office: Written Questions" -- opaque in the weekly section. If no
    matched term appears in the line itself, annotate with the first one.
    """
    base = (line or "").strip()
    low = base.lower()

    def clean(term):
        return term.strip('"').rstrip("*").strip()

    terms = [clean(t) for t in matched_terms if clean(t)]
    if not terms or any(t.lower() in low for t in terms):
        return base
    return "{0} (re: {1})".format(base, terms[0])


def record_event(conn, member_id, date, kind, ref, line, areas=None, commit=True,
                 excerpt=None):
    """Upsert a ledger row; idempotent on re-runs and backfills.

    On conflict the line/areas/date refresh from the new capture -- unlike
    items, mp_events carries no editorial state, so a re-run stamping areas
    onto pre-areas rows (or improving an annotation) is always safe.

    commit=False lets bulk writers (a 600-voter division) batch the fsync;
    the caller commits once per unit of work.
    """
    ensure_index(conn)
    conn.execute(
        "INSERT INTO mp_events (member_id, date, kind, ref, line, areas, excerpt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(member_id, kind, ref) DO UPDATE SET "
        "date=excluded.date, line=excluded.line, areas=excluded.areas, "
        "excerpt=COALESCE(excluded.excerpt, mp_events.excerpt)",
        (member_id, date, kind, ref, (line or "")[:200],
         json.dumps(sorted(areas)) if areas else None, excerpt))
    if commit:
        conn.commit()


def record_votes(conn, division, voters, prefix, areas=None):
    """Ledger every voter of one division; one commit for the lot.

    Direction lives in the ref (div:c1798:aye vs :no) because stance
    classification is per-ref and the two sides carry opposite stances.
    Voter payloads embed name/party/seat, so the members cache seeds here
    without any Members API traffic.
    """
    from src import members

    title = " ".join((division.title or "").split())  # source carries double spaces
    n = 0
    for v in voters:
        if not v.member_id:
            continue
        if v.name and not members.cache_get(conn, v.member_id):
            members.cache_put(conn, members.Member(
                id=v.member_id, name=v.name, party=v.party,
                seat=v.seat, house=division.house))
        record_event(conn, v.member_id, division.date.isoformat(), "vote",
                     "div:{0}{1}:{2}".format(prefix, division.id, v.vote),
                     "Voted {0}: {1}".format("Aye" if v.vote == "aye" else "No", title),
                     areas=areas, commit=False,
                     excerpt=getattr(division, "notes", None))
        n += 1
    conn.commit()
    return n


def events_for_week(conn, week_start, week_end):
    """Ledger rows in a date window, joined to the members cache."""
    return conn.execute(
        "SELECT e.member_id, e.date, e.kind, e.ref, e.line, e.areas, "
        "m.name, m.party, m.seat, m.house "
        "FROM mp_events e LEFT JOIN members m ON m.id = e.member_id "
        "WHERE e.date >= ? AND e.date <= ? ORDER BY e.date DESC, m.name",
        (week_start, week_end)).fetchall()


def member_timeline(conn, member_id, limit=50):
    return conn.execute(
        "SELECT date, kind, ref, line, areas FROM mp_events WHERE member_id = ? "
        "ORDER BY date DESC LIMIT ?", (member_id, limit)).fetchall()


def area_names(taxonomy_path):
    """{area_number: display name} from the generated taxonomy's area keys
    (e.g. 3_gender_medicine_children -> "Gender medicine children")."""
    import yaml
    with open(taxonomy_path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    out = {}
    for key in (raw.get("areas") or {}):
        num, _, rest = str(key).partition("_")
        out[int(num)] = rest.replace("_", " ").capitalize()
    return out


def area_activity(conn):
    """{member_id: {area: count}} across the whole ledger.

    The raw 5CA scoring input: which decision-makers are active on which of
    our issue areas, before any stance judgement is applied.
    """
    out = {}
    for row in conn.execute(
            "SELECT member_id, areas FROM mp_events WHERE areas IS NOT NULL"):
        for area in json.loads(row["areas"]):
            per = out.setdefault(row["member_id"], {})
            per[area] = per.get(area, 0) + 1
    return out


def ledger_stats(conn):
    row = conn.execute(
        "SELECT COUNT(*) AS events, COUNT(DISTINCT member_id) AS members, "
        "MIN(date) AS earliest, MAX(date) AS latest FROM mp_events").fetchone()
    return dict(row)
