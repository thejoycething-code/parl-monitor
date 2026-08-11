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
    since: str = None      # start of the CURRENT membership period (ISO date)
    list_as: str = None    # "Surname, First": how Parliament sorts them


def parse_member(value):
    """Parse a Members API `value` object into a Member."""
    party = (value.get("latestParty") or {}).get("name")
    membership = value.get("latestHouseMembership") or {}
    seat = membership.get("membershipFrom")
    house_id = membership.get("house")
    house = {1: "Commons", 2: "Lords"}.get(house_id, house_id)
    # API quirk: for continuously-serving members statusStartDate is the current
    # period and membershipStartDate their first entry; for returning members
    # (a by-election after time away) the two are reversed. The LATER of the two
    # is the start of the current period under both patterns -- which is what
    # "Not yet an MP for this division" depends on.
    status_start = (membership.get("membershipStatus") or {}).get("statusStartDate") or ""
    member_start = membership.get("membershipStartDate") or ""
    since = max(status_start, member_start)[:10] or None
    return Member(id=value.get("id"), name=value.get("nameDisplayAs"), party=party,
                  seat=seat, house=house, since=since,
                  list_as=value.get("nameListAs"))


def fetch_member(client, member_id):
    payload = client.get_json("{0}/Members/{1}".format(MEMBERS_API, member_id), "members", "detail-{0}".format(member_id))
    return parse_member(payload.get("value") or {})


def search_members(client, name, take=5):
    from urllib.parse import quote
    url = "{0}/Members/Search?Name={1}&take={2}".format(MEMBERS_API, quote(name), take)
    payload = client.get_json(url, "members", "search-{0}".format(name))
    return [parse_member(item.get("value") or {}) for item in (payload.get("items") or [])]


def fetch_commons_roster(client):
    """Every current MP; see fetch_roster."""
    return fetch_roster(client, house=1)


def fetch_lords_roster(client):
    """Every current peer (~800); see fetch_roster."""
    return fetch_roster(client, house=2)


def fetch_roster(client, house):
    """Every current member of one House (1=Commons, 2=Lords). The
    full-roster 5CA needs the whole chamber, not just the members the
    ledger has met. Pages the Search endpoint at its 20-per-page cap."""
    roster, skip = [], 0
    while True:
        url = ("{0}/Members/Search?House={1}&IsCurrentMember=true"
               "&skip={2}&take=20").format(MEMBERS_API, house, skip)
        payload = client.get_json(url, "members",
                                  "roster{0}-{1}".format("" if house == 1 else "-lords", skip))
        items = payload.get("items") or []
        if not items:
            break
        roster.extend(parse_member(item.get("value") or {}) for item in items)
        skip += len(items)
        if skip >= (payload.get("totalResults") or 0):
            break
    return roster


def mark_roster(conn, roster, flag="current_mp"):
    """Refresh the cache from a roster and set its currency flag. Previous
    flags are cleared first so departed members drop off full-roster sheets
    on the next pull. flag is a column name and is whitelisted, never
    interpolated from input."""
    if flag not in ("current_mp", "current_peer"):
        raise ValueError("unknown roster flag: {0!r}".format(flag))
    conn.execute("UPDATE members SET {0} = NULL".format(flag))
    for m in roster:
        conn.execute(
            "INSERT INTO members (id, name, party, seat, house, since, list_as, {0}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, party=excluded.party, "
            "seat=excluded.seat, house=excluded.house, since=excluded.since, "
            "list_as=excluded.list_as, {0}=1".format(flag),
            (m.id, m.name, m.party, m.seat, m.house, m.since, m.list_as))
    conn.commit()


# -- cache ------------------------------------------------------------------

def cache_get(conn, member_id):
    row = conn.execute("SELECT id, name, party, seat, house, since, list_as "
                       "FROM members WHERE id = ?", (member_id,)).fetchone()
    if row is None:
        return None
    return Member(id=row["id"], name=row["name"], party=row["party"], seat=row["seat"],
                  house=row["house"], since=row["since"], list_as=row["list_as"])


def cache_put(conn, member):
    # COALESCE: a voter payload carries name/party/seat but no start date, so
    # seeding from a division must not blank a date the roster pull established.
    conn.execute(
        "INSERT INTO members (id, name, party, seat, house, since, list_as) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET name=excluded.name, party=excluded.party, "
        "seat=excluded.seat, house=excluded.house, "
        "since=COALESCE(excluded.since, members.since), "
        "list_as=COALESCE(excluded.list_as, members.list_as)",
        (member.id, member.name, member.party, member.seat, member.house,
         member.since, member.list_as),
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
