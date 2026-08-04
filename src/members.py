"""Member id -> name/party/seat resolution with a permanent cache (handoff 4.9).

The Members API is fast, but PQ/EDM sweeps reference members only by id and we
resolve lazily for shortlisted items only (never expandMember=true on the PQ
API). Resolved members are cached permanently in the `members` table.
"""

from __future__ import annotations

from dataclasses import dataclass

MEMBERS_API = "https://members-api.parliament.uk/api"


@dataclass
class Member:
    id: int
    name: str
    party: str
    seat: str
    house: str


def parse_member(value):
    """Parse a Members API `value` object into a Member."""
    party = (value.get("latestParty") or {}).get("name")
    membership = value.get("latestHouseMembership") or {}
    seat = membership.get("membershipFrom")
    house_id = membership.get("house")
    house = {1: "Commons", 2: "Lords"}.get(house_id, house_id)
    return Member(id=value.get("id"), name=value.get("nameDisplayAs"), party=party, seat=seat, house=house)


def fetch_member(client, member_id):
    payload = client.get_json("{0}/Members/{1}".format(MEMBERS_API, member_id), "members", "detail-{0}".format(member_id))
    return parse_member(payload.get("value") or {})


def search_members(client, name, take=5):
    from urllib.parse import quote
    url = "{0}/Members/Search?Name={1}&take={2}".format(MEMBERS_API, quote(name), take)
    payload = client.get_json(url, "members", "search-{0}".format(name))
    return [parse_member(item.get("value") or {}) for item in (payload.get("items") or [])]


def fetch_commons_roster(client):
    """Every current MP (the full-roster 5CA needs all ~650, not just the
    active ones the ledger has met). Pages the Search endpoint at its
    20-per-page cap; ~33 calls."""
    roster, skip = [], 0
    while True:
        url = ("{0}/Members/Search?House=1&IsCurrentMember=true"
               "&skip={1}&take=20").format(MEMBERS_API, skip)
        payload = client.get_json(url, "members", "roster-{0}".format(skip))
        items = payload.get("items") or []
        if not items:
            break
        roster.extend(parse_member(item.get("value") or {}) for item in items)
        skip += len(items)
        if skip >= (payload.get("totalResults") or 0):
            break
    return roster


def mark_roster(conn, roster):
    """Refresh the cache from the roster and flag its members current_mp=1.
    Previous flags are cleared first so departed MPs drop off full-roster
    sheets on the next pull."""
    conn.execute("UPDATE members SET current_mp = NULL")
    for m in roster:
        conn.execute(
            "INSERT INTO members (id, name, party, seat, house, current_mp) "
            "VALUES (?, ?, ?, ?, ?, 1) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, party=excluded.party, "
            "seat=excluded.seat, house=excluded.house, current_mp=1",
            (m.id, m.name, m.party, m.seat, m.house))
    conn.commit()


# -- cache ------------------------------------------------------------------

def cache_get(conn, member_id):
    row = conn.execute("SELECT id, name, party, seat, house FROM members WHERE id = ?", (member_id,)).fetchone()
    if row is None:
        return None
    return Member(id=row["id"], name=row["name"], party=row["party"], seat=row["seat"], house=row["house"])


def cache_put(conn, member):
    conn.execute(
        "INSERT OR REPLACE INTO members (id, name, party, seat, house) VALUES (?, ?, ?, ?, ?)",
        (member.id, member.name, member.party, member.seat, member.house),
    )
    conn.commit()


def resolve(conn, client, member_id):
    """Return a Member, from cache if present, else fetch-and-cache."""
    cached = cache_get(conn, member_id)
    if cached is not None:
        return cached
    member = fetch_member(client, member_id)
    cache_put(conn, member)
    return member
