"""Party as at a date, for the Northern Ireland Assembly.

WHY THIS EXISTS. `GetAllCurrentMembers` gives the roster NOW, so joining a 2025
question to it attributes the question to whatever party the member sits in
today. Doug Beattie tabled questions as leader of the Ulster Unionist Party and
now sits as an Independent; the current roster makes those questions read
"Independent", which is true of him and false of the question.
`GetAllMembersByGivenDate` answers the right question, and this module caches
its answers so a date is fetched once.

DESIGN. Sparse by intention: only dates something actually happened on are
fetched, which measured 25 for the current store (18 question dates, 9 watched
division dates, 2 shared). Each fetch returns all 90 members for that date, so
storing the whole roster per date is free and makes "who was in which party
when" answerable generally rather than only for rows we happen to hold.

FALLBACK IS EXPLICIT, NEVER SILENT. `party_at` returns a source alongside the
party -- "as-at" when the date was resolved, "current" when it fell back to
today's roster, "unknown" when neither has the member. A caller that shows a
party without saying which of those it is would be repeating the bug this
module was written to fix, so the source is returned rather than offered.
"""

from __future__ import annotations

AS_AT = "as-at"
CURRENT = "current"
UNKNOWN = "unknown"


def store_roster_at(conn, when, members, captured_at):
    """Store one date's roster. Idempotent."""
    day = when.isoformat() if hasattr(when, "isoformat") else str(when)
    for m in members:
        conn.execute(
            "INSERT OR REPLACE INTO ni_affiliations (person_id, as_at, party, "
            "constituency, display_name, captured_at) VALUES (?,?,?,?,?,?)",
            (m.person_id, day, m.party, m.constituency, m.display_name,
             captured_at))
    return len(members)


def dates_present(conn):
    """Dates already resolved, so a re-run fetches nothing it has."""
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT as_at FROM ni_affiliations")}


def resolve_dates(conn, client, dates, captured_at, fetch):
    """Fetch and store any of `dates` not already held.

    `fetch` is injected (niassembly.fetch_members_at in production) so this is
    testable without a network. Returns (fetched_count, gaps).
    """
    have = dates_present(conn)
    want = sorted({d for d in dates if d and d not in have})
    fetched, gaps = 0, []
    for day in want:
        members, err = fetch(client, day)
        if err:
            gaps.append("roster as at {0}: {1}".format(day, err))
            continue
        if not members:
            gaps.append("roster as at {0}: no members returned".format(day))
            continue
        store_roster_at(conn, day, members, captured_at)
        fetched += 1
    return fetched, gaps


def sittings_present(conn):
    """Sitting dates whose Hansard is already archived."""
    return {r[0] for r in conn.execute("SELECT dated FROM ni_sittings")}


def resolve_sittings(conn, client, dates, captured_at, fetch):
    """Fetch and archive any sitting not already held. -> (fetched, gaps).

    Same shape as resolve_dates, and `fetch` is injected for the same reason:
    the caller can be tested without a network. The archive is what makes
    re-classification free afterwards, so this is called once per date ever.
    """
    have = sittings_present(conn)
    want = sorted({d for d in dates if d and d not in have})
    fetched, gaps = 0, []
    for day in want:
        sitting, err = fetch(client, day)
        if err:
            gaps.append("hansard {0}: {1}".format(day, err))
            continue
        if sitting is None or not sitting.components:
            gaps.append("hansard {0}: no components returned".format(day))
            continue
        conn.execute(
            "INSERT OR REPLACE INTO ni_sittings (dated, components, divisions, "
            "captured_at) VALUES (?,?,?,?)",
            (day, len(sitting.components), len(sitting.anchors()), captured_at))
        fetched += 1
    return fetched, gaps


def affiliation_map(conn):
    """{(person_id, as_at): (party, constituency)} for every resolved date."""
    return {(r["person_id"], r["as_at"]): (r["party"], r["constituency"])
            for r in conn.execute(
                "SELECT person_id, as_at, party, constituency FROM ni_affiliations")}


def current_map(conn):
    """{person_id: (party, constituency)} from the current roster."""
    return {r["person_id"]: (r["party"], r["constituency"])
            for r in conn.execute(
                "SELECT person_id, party, constituency FROM ni_members")}


def party_at(person_id, when, as_at, current):
    """(party, constituency, source) for a member on a date.

    `as_at` and `current` are the two maps above, passed in so a caller
    building a long list does not re-query per row. `source` is one of AS_AT,
    CURRENT or UNKNOWN and is not optional -- see the module docstring.
    """
    key = (person_id or "", when or "")
    if key in as_at:
        party, seat = as_at[key]
        return party, seat, AS_AT
    if (person_id or "") in current:
        party, seat = current[person_id]
        return party, seat, CURRENT
    return "", "", UNKNOWN


def label(party, source):
    """How a party reads in output, with the caveat attached where it applies.

    A CURRENT-sourced party is marked "(party today)" because it may not be the
    party held at the time. Marking it is the whole point: an unmarked party is
    what made Doug Beattie's UUP questions read Independent.
    """
    if not party:
        return "party unknown"
    if source == CURRENT:
        return "{0} (party today)".format(party)
    return party
