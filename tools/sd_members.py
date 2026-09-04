"""Senedd roster from mySociety parlparse -> sd_members.

    python3 tools/sd_members.py

WHY PARLPARSE. The Senedd publishes no member data our honest User-Agent can
reach: business.senedd.wales (party, via ModernGov) WAF-403s it, and the
senedd.wales member directory loads by an opaque Umbraco form. parlparse is
public, maintained by mySociety, and carried the full 96-member post-expansion
chamber (start 2026-05-08) the day we probed. One 27MB fetch, archive=False.

Question attribution joins sd_items.member_name to this roster BY NAME at
display time; unmatched names are reported, never guessed.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import HttpClient

URL = ("https://raw.githubusercontent.com/mysociety/parlparse/master/"
       "members/people.json")

PARTY_NAMES = {"plaid-cymru": "Plaid Cymru", "reform": "Reform UK",
               "labour": "Welsh Labour", "conservative": "Welsh Conservative",
               "liberal-democrat": "Welsh Liberal Democrats",
               "green": "Wales Green Party"}


def person_name(person):
    """The member's display name, SURNAME INCLUDED.

    parlparse records a peer's surname in `lordname`, not `family_name`,
    and eight Welsh Members are peers. Reading family_name alone stored
    the First Minister as "Mair Eluned" -- a roster entry that matched
    no vote she ever cast, and left her off the page entirely.
    """
    for n in (person.get("other_names") or []):
        if n.get("note") == "Main":
            surname = n.get("family_name") or n.get("lordname") or ""
            return "{0} {1}".format(n.get("given_name", ""), surname).strip()
    return ""


def person_aliases(person):
    """Every name parlparse knows this person by.

    Votes are joined to the Welsh roster BY NAME (the two id spaces
    share nothing), so a member who votes under a name the roster does
    not carry simply vanishes. parlparse already answers this: it keeps
    "Alternate" names beside the "Main" one -- which is the only reason
    "Dafydd Trystan Davies" can be matched at all. These are parlparse's
    own assertions that the names belong to one person; nothing here
    guesses.
    """
    out = []
    for n in (person.get("other_names") or []):
        kind = n.get("note") or "Alternate"
        if n.get("name"):
            out.append((n["name"], kind))
        surname = n.get("family_name") or n.get("lordname")
        if n.get("given_name") and surname:
            out.append(("{0} {1}".format(n["given_name"], surname), kind))
            # A peer's given_name may carry forenames the chamber does
            # not use ("Mair Eluned" for Eluned Morgan), so record the
            # last forename with the surname too.
            first = n["given_name"].split()
            if len(first) > 1:
                out.append(("{0} {1}".format(first[-1], surname), kind))
    seen, uniq = set(), []
    for name, kind in out:
        key = name.strip().lower()
        if name.strip() and key not in seen:
            seen.add(key)
            uniq.append((name.strip(), kind))
    return uniq


def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    data = client.get_json(URL, "senedd", "parlparse-people",
                           timeout=180, archive=False)
    wposts = {p["id"]: (p.get("area") or {}).get("name") or p.get("label")
              for p in data["posts"]
              if p.get("organization_id") == "welsh-parliament"}
    persons = {p["id"]: p for p in data["persons"]}
    stored = sitting = 0
    for m in data["memberships"]:
        if m.get("post_id") not in wposts:
            continue
        pid = m.get("person_id")
        person = persons.get(pid) or {}
        end = m.get("end_date")
        conn.execute(
            "INSERT OR REPLACE INTO sd_members (person_id, name, party, post, "
            "start_date, end_date, captured_at) VALUES (?,?,?,?,?,?,?)",
            (pid, person_name(person),
             PARTY_NAMES.get(m.get("on_behalf_of_id"),
                             m.get("on_behalf_of_id")),
             wposts.get(m.get("post_id")), m.get("start_date"), end, now))
        for alias, kind in person_aliases(person):
            conn.execute(
                "INSERT OR REPLACE INTO member_aliases (chamber, person_id, "
                "name, kind, captured_at) VALUES ('wales',?,?,?,?)",
                (pid, alias, kind, now))
        stored += 1
        if not end or end >= now[:10]:
            sitting += 1
    conn.commit()
    aliases = conn.execute("SELECT COUNT(*) FROM member_aliases WHERE "
                           "chamber='wales'").fetchone()[0]
    print("{0} Welsh membership(s) stored; {1} sitting; {2} known name(s) "
          "recorded.".format(stored, sitting, aliases))
    if sitting != 96:
        print("  WARNING: sitting count is {0}, not 96 -- the post-expansion "
              "chamber. Check parlparse before trusting party joins."
              .format(sitting))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
