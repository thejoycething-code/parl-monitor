#!/usr/bin/env python3
"""Published profile detail for sitting MPs: contact, roles, seat.

Built 2026-08-26 ("Build it. Are there any dangers this breaks the Sunday
pull?").

WHAT THIS TAKES, AND WHY IT IS SAFE TO REPUBLISH. Everything here comes from
the Members API register -- the details each member has GIVEN Parliament for
publication. We are not researching handles or inferring accounts, which is
the same discipline the vote page already applies to quotes: publish the
official record, not our own digging. Measured coverage on a live sample:
Facebook 62%, website 58%, X 55%, Instagram 40%, Bluesky 10%, and a
parliamentary email or phone for 100%.

WHAT IT DELIBERATELY DOES NOT TAKE. Address lines. A "Constituency office"
record is frequently a member's home, and publishing where someone lives is a
different act from reporting how they voted. Only email, phone and web
addresses are read out of a contact record; line1-line5 and postcode are
ignored except when the record IS a web address.

WHY THIS IS NOT IN THE SUNDAY PULL. Sunday pull is the critical weekly job
and its steps are guarded `if: env.SKIP != '1'`, which does not run after a
failure -- so an enrichment step placed before the weekly gather would block
the gather outright if the API hiccupped. It also has a 60-minute budget
against a cold pull already measured at 40m05s, and its Monday 02:00 retry
slot has to finish before the 03:00 publish. Reference data that changes at
by-elections, reshuffles and committee turnover does not belong on that path,
so it runs in member-profiles.yml on a free day instead. pull_service.py was
moved out for the same reason.

Nothing here raises on a partial failure: a member whose record cannot be
fetched keeps whatever was stored last week, and the run reports what it
missed rather than failing the workflow.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import HttpClient

MEMBERS_API = "https://members-api.parliament.uk/api"

# The register's type strings, mapped to what the page calls them. Anything
# not listed is ignored rather than guessed at.
WEB_KINDS = {
    "Website": "website",
    "X (formerly Twitter)": "x",
    "Twitter": "x",
    "Facebook": "facebook",
    "Instagram": "instagram",
    "Bluesky": "bluesky",
    "LinkedIn": "linkedin",
    "Youtube": "youtube",
    "YouTube": "youtube",
    "Substack": "substack",
}
OFFICE_KINDS = ("Parliamentary office", "Constituency office")


def parse_contact(records):
    """{kind: value} from a Contact payload.

    Emails and phones are taken from either office record -- the
    parliamentary email is sometimes filed under "Constituency office" --
    but the ADDRESS on those records is never read.
    """
    out = {}
    for rec in records or []:
        kind = rec.get("type")
        if rec.get("isWebAddress"):
            mapped = WEB_KINDS.get(kind)
            url = (rec.get("line1") or "").strip()
            if mapped and url and mapped not in out:
                out[mapped] = url
            continue
        if kind in OFFICE_KINDS:
            # Parliamentary office wins where both carry one.
            preferred = kind == "Parliamentary office"
            for field, key in (("email", "email"), ("phone", "phone")):
                val = (rec.get(field) or "").strip()
                if val and (key not in out or preferred):
                    out[key] = val
    return out


def parse_posts(bio):
    """[(kind, name, started, ended)] -- ministerial, shadow and committee."""
    out = []
    for source, kind in (("governmentPosts", "government"),
                         ("oppositionPosts", "opposition"),
                         ("otherPosts", "other"),
                         ("committeeMemberships", "committee")):
        for post in (bio.get(source) or []):
            name = post.get("name")
            if not name:
                continue
            out.append((kind, name, (post.get("startDate") or "")[:10] or None,
                        (post.get("endDate") or "")[:10] or None))
    return out


def constituency_id(bio):
    """The member's CURRENT seat id, for the election result."""
    for rep in (bio.get("representations") or []):
        if rep.get("house") == 1 and not rep.get("endDate"):
            return rep.get("id")
    return None


def parse_result(payload):
    d = payload or {}
    return {"majority": d.get("majority"), "electorate": d.get("electorate"),
            "turnout": d.get("turnout"), "result": d.get("result"),
            "election_date": (d.get("electionDate") or "")[:10] or None}


def store_contact(conn, mid, values):
    conn.execute("DELETE FROM member_contact WHERE member_id = ?", (mid,))
    for kind, value in sorted(values.items()):
        conn.execute("INSERT OR REPLACE INTO member_contact "
                     "(member_id, kind, value) VALUES (?,?,?)",
                     (mid, kind, value))


def store_posts(conn, mid, posts):
    conn.execute("DELETE FROM member_post WHERE member_id = ?", (mid,))
    for kind, name, started, ended in posts:
        conn.execute("INSERT OR REPLACE INTO member_post "
                     "(member_id, kind, name, started, ended) VALUES (?,?,?,?,?)",
                     (mid, kind, name, started, ended))


def store_seat(conn, mid, cid, result, synopsis):
    conn.execute(
        "INSERT OR REPLACE INTO member_seat (member_id, constituency_id, "
        "majority, electorate, turnout, result, election_date, synopsis) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (mid, cid, result.get("majority"), result.get("electorate"),
         result.get("turnout"), result.get("result"),
         result.get("election_date"), synopsis))


def clean_synopsis(text):
    """Parliament's line, with its internal links stripped.

    It reads "...the Labour MP for <a href='/constituency/4074/overview'>
    Hackney North</a>, and has been an MP continually since 11 June 1987."
    The anchor points at Parliament's own site relative to THEIR root, so it
    would 404 on ours.
    """
    import re
    if not text:
        return None
    return " ".join(re.sub(r"<[^>]+>", "", text).split()) or None


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    # archive=False: 650 members x 3 endpoints is ~1,950 files a week into
    # data/raw, which is committed to git and already 212MB. These payloads
    # are re-fetchable at will and carry no evidence we quote, so mirroring
    # them buys nothing and costs the repo.
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM members WHERE current_mp = 1 ORDER BY id")]
    print("sitting members: {0}".format(len(ids)))

    def fetch(path):
        """The payload itself, not the API envelope.

        Every Members API response is {"value": ..., "links": [...]}. Passing
        the envelope to the parsers made them iterate its KEYS, so every
        member raised into the failure list and a 650-member run stored
        exactly nothing -- silently, because per-member failures are caught
        by design.
        """
        payload = client.get_json(MEMBERS_API + path, "members",
                                  path.strip("/").replace("/", "-"),
                                  archive=False)
        if isinstance(payload, dict) and "value" in payload:
            return payload["value"]
        return payload

    seats = {}          # constituency id -> result, so a seat is fetched once
    counts = {"contact": 0, "posts": 0, "seat": 0}
    failed = []
    for n, mid in enumerate(ids, 1):
        try:
            contact = parse_contact((fetch("/Members/{0}/Contact".format(mid))
                                     or []))
            if contact:
                store_contact(conn, mid, contact)
                counts["contact"] += 1
        except Exception as exc:                        # noqa: BLE001
            failed.append((mid, "contact", str(exc)[:60]))
        try:
            bio = fetch("/Members/{0}/Biography".format(mid)) or {}
            posts = parse_posts(bio)
            if posts:
                store_posts(conn, mid, posts)
                counts["posts"] += 1
            cid = constituency_id(bio)
        except Exception as exc:                        # noqa: BLE001
            failed.append((mid, "biography", str(exc)[:60]))
            cid = None
        try:
            synopsis = clean_synopsis(
                fetch("/Members/{0}/Synopsis".format(mid)))
            if cid is not None:
                if cid not in seats:
                    seats[cid] = parse_result(fetch(
                        "/Location/Constituency/{0}/ElectionResult/latest".format(cid)))
                store_seat(conn, mid, cid, seats[cid], synopsis)
                counts["seat"] += 1
        except Exception as exc:                        # noqa: BLE001
            failed.append((mid, "seat", str(exc)[:60]))
        if n % 100 == 0:
            conn.commit()
            print("  {0}/{1}".format(n, len(ids)))
    conn.commit()

    print("stored: contact {contact}, roles {posts}, seat {seat}".format(**counts))
    # Coverage, printed rather than assumed -- a social row that is mostly
    # empty is a design fact the page has to handle.
    for kind, num in conn.execute(
            "SELECT kind, COUNT(*) FROM member_contact GROUP BY kind "
            "ORDER BY COUNT(*) DESC"):
        print("   {0:<10} {1:>3} members ({2}%)".format(
            kind, num, round(100 * num / max(1, len(ids)))))
    if failed:
        # Loud but not fatal: a member who could not be fetched keeps last
        # week's detail, and the workflow must not die for it.
        print("\n{0} fetch failures (previous values retained):".format(len(failed)))
        for mid, what, why in failed[:10]:
            print("   {0} {1}: {2}".format(mid, what, why))
    return 0


if __name__ == "__main__":
    sys.exit(main())
