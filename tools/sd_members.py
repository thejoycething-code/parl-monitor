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
    for n in (person.get("other_names") or []):
        if n.get("note") == "Main":
            return "{0} {1}".format(n.get("given_name", ""),
                                    n.get("family_name", "")).strip()
    return ""


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
        stored += 1
        if not end or end >= now[:10]:
            sitting += 1
    conn.commit()
    print("{0} Welsh membership(s) stored; {1} sitting.".format(stored, sitting))
    if sitting != 96:
        print("  WARNING: sitting count is {0}, not 96 -- the post-expansion "
              "chamber. Check parlparse before trusting party joins."
              .format(sitting))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
