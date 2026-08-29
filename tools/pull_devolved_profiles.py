#!/usr/bin/env python3
"""Contact details and posts for devolved members -> dv_contact, dv_post.

    python3 tools/pull_devolved_profiles.py

Westminster members have had contact details, posts and seat history since
the profile work in August. MSs, MSPs and MLAs had a name, a party and
nothing else -- so a devolved page could not have said who anyone is.

WHAT EACH NATION PUBLISHES, which is not the same thing:

  * Northern Ireland gives the most. members.asmx answers for EVERY member
    in one call: GetAllMemberContactDetails_JSON (email and offices) and
    GetAllMemberRoles_JSON (ministerial, committee, party and all-party
    group roles). Two requests for the whole Assembly.
  * Scotland gives ROLES and SEATS but no contact details:
    Membergovernmentroles, Memberpartyroles, MemberCrossPartyRoles and the
    constituency/region status endpoints. Contact is not in the open data.
  * Wales gives NEITHER. senedd.wales has no members API, and the ModernGov
    instance that might have carried one is behind the WAF. Absent by fact,
    not by omission -- there is nothing here to call.

Free APIs both, no spend. Watching brief: writes dv_* only.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import FetchError, HttpClient
from src.ingest import niassembly

SCOT_API = "https://data.parliament.scot/api"
# Roles Scotland publishes per member. Each is a flat list of every role
# ever held, with ValidUntilDate NULL while it is still held.
# Each per-member endpoint gives a role ID; the NAME lives in a separate
# lookup. Fetching both matters: "Membergovernmentroles (role 12)" is not a
# post a reader can use, and storing it would have been worse than storing
# nothing. (member endpoint, id field, lookup endpoint)
SCOT_ROLES = (("government", "Membergovernmentroles", "GovernmentRoleID",
               "Governmentroles"),
              ("party", "Memberpartyroles", "PartyRoleID", "Partyroles"),
              ("committee", "Personcommitteeroles", "CommitteeRoleID",
               "Committeeroles"))


def store_contact(conn, nation, pid, kind, value, now):
    conn.execute(
        "INSERT INTO dv_contact (nation, person_id, kind, value, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(nation, person_id, kind, value) DO UPDATE SET "
        "last_seen=excluded.last_seen", (nation, pid, kind, value, now, now))


def store_post(conn, nation, pid, kind, name, started, ended, now):
    conn.execute(
        "INSERT INTO dv_post (nation, person_id, kind, name, started, ended, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(nation, person_id, kind, name, started) DO UPDATE SET "
        "ended=excluded.ended, last_seen=excluded.last_seen",
        (nation, pid, kind, name, started or "", ended, now, now))


def northern_ireland(conn, client, now, gaps):
    contacts = posts = 0
    try:
        payload = client.get_json(niassembly.MEMBER_CONTACTS, "ni",
                                  "member-contacts", archive=False)
        for pid, kind, value in niassembly.parse_member_contacts(payload):
            store_contact(conn, "ni", pid, kind, value, now)
            contacts += 1
    except FetchError as exc:
        gaps.append("NI contact details: {0}".format(exc.cause))
    try:
        payload = client.get_json(niassembly.MEMBER_ROLES, "ni",
                                  "member-roles", archive=False)
        for pid, kind, name in niassembly.parse_member_roles(payload):
            store_post(conn, "ni", pid, kind, name, None, None, now)
            posts += 1
    except FetchError as exc:
        gaps.append("NI roles: {0}".format(exc.cause))
    conn.commit()
    return contacts, posts


def scot_lookup(client, endpoint, gaps):
    """{id: name} from a Scottish role lookup table."""
    try:
        payload = client.get_json("{0}/{1}".format(SCOT_API, endpoint),
                                  "holyrood", endpoint.lower(), archive=False)
    except FetchError as exc:
        gaps.append("Scotland {0}: {1}".format(endpoint, exc.cause))
        return {}
    out = {}
    for row in (payload if isinstance(payload, list) else []):
        rid, name = row.get("ID"), " ".join((row.get("Name") or "").split())
        if rid is not None and name:
            out[str(rid)] = name
    return out


def scotland(conn, client, now, gaps):
    posts = unnamed = outsiders = 0
    # Personcommitteeroles covers everyone attached to a committee, CLERKS
    # INCLUDED -- 45 of the 453 people it returns are staff, holding roles
    # like "Committee Clerk". This table is about members, so a person the
    # roster does not know is skipped rather than filed as an MSP.
    msps = {str(r[0]) for r in conn.execute("SELECT person_id FROM sp_members")}
    for kind, endpoint, id_field, lookup in SCOT_ROLES:
        names = scot_lookup(client, lookup, gaps)
        try:
            payload = client.get_json("{0}/{1}".format(SCOT_API, endpoint),
                                      "holyrood", endpoint.lower(),
                                      archive=False)
        except FetchError as exc:
            gaps.append("Scotland {0}: {1}".format(endpoint, exc.cause))
            continue
        for row in (payload if isinstance(payload, list) else []):
            pid = str(row.get("PersonID") or row.get("PersonId") or "").strip()
            rid = str(row.get(id_field) or "").strip()
            if not pid:
                continue
            if pid not in msps:
                outsiders += 1
                continue
            name = names.get(rid)
            if not name:
                # A post the lookup cannot name is not stored: an unnamed
                # role tells a reader nothing and would pad every profile.
                unnamed += 1
                continue
            store_post(conn, "scotland", pid, kind, name,
                       (row.get("ValidFromDate") or "")[:10],
                       (row.get("ValidUntilDate") or "")[:10] or None, now)
            posts += 1
    if unnamed:
        print("  {0} Scottish role(s) had no name in the lookup and were "
              "skipped".format(unnamed))
    if outsiders:
        print("  {0} Scottish role(s) belonged to staff, not MSPs, and were "
              "skipped".format(outsiders))
    conn.commit()
    return 0, posts


def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    gaps = []

    c, p = northern_ireland(conn, client, now, gaps)
    print("Northern Ireland: {0} contact row(s), {1} post(s)".format(c, p))
    c2, p2 = scotland(conn, client, now, gaps)
    print("Scotland:         {0} contact row(s), {1} post(s)".format(c2, p2))
    print("Wales:            no members API published; nothing to call")

    if gaps:
        db.record_gaps(conn, "dv-profiles", gaps)
        print("\n{0} gap(s) -- printed, never swallowed:".format(len(gaps)))
        for g in gaps:
            print("  * {0}".format(g))
    else:
        print("\nno gaps.")

    held = conn.execute("SELECT nation, COUNT(DISTINCT person_id) FROM dv_contact "
                        "GROUP BY nation").fetchall()
    print("members with contact details: {0}".format(
        {r[0]: r[1] for r in held} or "none"))
    held = conn.execute("SELECT nation, COUNT(DISTINCT person_id) FROM dv_post "
                        "GROUP BY nation").fetchall()
    print("members with a post:          {0}".format({r[0]: r[1] for r in held} or "none"))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
