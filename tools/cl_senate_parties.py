#!/usr/bin/env python3
"""Chile: senators' party history from the BCN's open data (X6).

    python3 tools/cl_senate_parties.py
    python3 tools/cl_senate_parties.py --db /tmp/cl.db

WHY. The Cámara gives each deputy's dated party spells (militancias), so a
deputy's party at the vote is known; the Senate gives only the current
party, so a Senate vote carries the party at collection (docs/chile-scope.md).
Chris's X6 (10 October 2026): source party history before relying on party
at the vote. The Biblioteca del Congreso Nacional publishes every
parliamentarian's militancies as linked open data (datos.bcn.cl), each with
its party and its start and end dates, and ties the person to the Senate's
own id (bcn-biographies#idSenado), which is cl_members.source_id for a
senator. One SPARQL query reads all of them.

WHAT IS STORED. Rows in cl_party_spells for 'S-<id>' members, beside the
Cámara's 'D-<id>' rows: party and party_name are the BCN's party label
(the Cámara's rows carry its alias in `party`), start and end the BCN's
dates. A militancy with no start date cannot be placed and is counted, not
stored. cl_votes is not touched: src/member_profiles.py reads the spells
and states the party on the day of each Senate vote, saying where it came
from. Additive: nothing the collector reads changes (it reads spells for
Cámara members only).

robots.txt on datos.bcn.cl allows every agent, with a 10-second crawl delay
(measured 10 October 2026); this is one request a week.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "cl-bcn"
HOST = "datos.bcn.cl"
SPARQL = "https://datos.bcn.cl/sparql?query={0}&format=json"
QUERY = """PREFIX bio: <http://datos.bcn.cl/ontologies/bcn-biographies#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?sen ?party ?label ?start ?end WHERE {
  ?per bio:idSenado ?sen ; bio:hasMilitancy ?m .
  ?m bio:hasPoliticalParty ?party .
  OPTIONAL { ?party rdfs:label ?label }
  OPTIONAL { ?m bio:hasBeginning ?b . ?b bio:originalDate ?start }
  OPTIONAL { ?m bio:hasEnd ?e . ?e bio:originalDate ?end }
}"""
CRAWL_DELAY_S = 10.0


def _iso(value):
    """'2024-01-08' (or '2024-01-08T...') -> ISO date; anything else None."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", (value or "").strip())
    return "-".join(m.groups()) if m else None


def _label(uri, label):
    if label:
        return " ".join(label.split())
    slug = (uri or "").rstrip("/").rsplit("/", 1)[-1]
    return slug.replace("-", " ").capitalize() if slug else None


def parse(doc):
    """{senate_id: [{'party', 'start', 'end'}]} from the SPARQL JSON; spells
    with no start date are returned under the key None as a count."""
    out, undated = {}, 0
    for b in ((doc or {}).get("results") or {}).get("bindings") or []:
        sen = (b.get("sen") or {}).get("value")
        party = _label((b.get("party") or {}).get("value"), (b.get("label") or {}).get("value"))
        start = _iso((b.get("start") or {}).get("value"))
        if not sen or not party:
            continue
        if not start:
            undated += 1
            continue
        spell = {"party": party, "start": start, "end": _iso((b.get("end") or {}).get("value"))}
        if spell not in out.setdefault(str(sen).strip(), []):
            out[str(sen).strip()].append(spell)
    for spells in out.values():
        spells.sort(key=lambda s: s["start"])
    return out, undated


def store(conn, spells):
    """Write spells for senators the store knows; returns (members, spells)."""
    senators = dict(conn.execute("SELECT source_id, member_key FROM cl_members WHERE "
                                 "chamber = 'senado' AND source_id IS NOT NULL").fetchall())
    members = n = 0
    for sid, rows in spells.items():
        mk = senators.get(sid)
        if not mk:
            continue
        members += 1
        conn.execute("DELETE FROM cl_party_spells WHERE member_key = ?", (mk,))
        for s in rows:
            conn.execute("INSERT OR REPLACE INTO cl_party_spells (member_key, party, party_name, "
                         "start, end) VALUES (?,?,?,?,?)",
                         (mk, s["party"], s["party"], s["start"], s["end"]))
            n += 1
    conn.commit()
    return members, n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    client.set_host_throttle(HOST, CRAWL_DELAY_S)
    conn = db.init_db(db.connect(args.db))
    try:
        doc = json.loads(client.get_text(SPARQL.format(urllib.parse.quote(QUERY)), FEED,
                                         "militancias-senado", timeout=180))
    except (FetchError, ValueError) as exc:
        print("  [gap] cl-senate-parties: the BCN query failed: {0}".format(str(exc)[:120]))
        conn.close()
        return 3
    spells, undated = parse(doc)
    members, n = store(conn, spells)
    print("cl-senate-parties: {0} spell(s) for {1} senator(s) in the store, from {2} "
          "senator(s) with militancies at the BCN; {3} undated militancy(ies) left out "
          "({4})".format(n, members, len(spells), undated, datetime.date.today().isoformat()))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
