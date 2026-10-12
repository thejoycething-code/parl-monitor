#!/usr/bin/env python3
"""Propose party colour chips for the country vote pages from Wikidata.

    python3 tools/party_colours.py                     # every vote-page country
    python3 tools/party_colours.py --country pl --country fr

Party LOGOS are trademarks with no open licence (docs/portraits-logos-licences.md),
so the pages show a colour chip instead. The colour comes from Wikidata's
"sRGB colour hex triplet" (P465) on the party or parliamentary group item
(Wikidata is CC0), matched to the label the store uses (the group the vote
record names) by the item's short name (P1813), label or alias, folded.

Prints YAML for config/party-colours.yaml: matched labels with the Wikidata
item as a comment, and the labels it could not match. Nothing is written:
a person pastes and checks what goes in (a wrong colour is worse than none).
Read-only on the store; queries go through src/http.py (UA, throttle).
"""

from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
import unicodedata
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_votes as cv  # noqa: E402
from src.http import HttpClient  # noqa: E402

COUNTRY_QID = {
    "pl": "Q36", "it": "Q38", "ch": "Q39", "fr": "Q142", "es": "Q29", "nl": "Q55",
    "be": "Q31", "at": "Q40", "pt": "Q45", "sk": "Q214", "hr": "Q224", "hu": "Q28",
    "br": "Q155", "ar": "Q414", "mx": "Q96", "cl": "Q298", "pe": "Q419", "ec": "Q736",
    "do": "Q786", "sv": "Q792", "gt": "Q774", "co": "Q739", "uy": "Q77",
}

QUERY = """SELECT ?item ?colour (GROUP_CONCAT(DISTINCT ?name; separator="|") AS ?names) WHERE {
  VALUES ?kind { wd:Q7278 wd:Q848197 }
  ?item wdt:P31/wdt:P279? ?kind ; wdt:P17 wd:%s ; wdt:P465 ?colour .
  { ?item wdt:P1813 ?name } UNION { ?item rdfs:label ?name } UNION { ?item skos:altLabel ?name }
} GROUP BY ?item ?colour"""


def fold(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return "".join(c for c in text if c.isalnum())


def candidates(rows):
    """{folded name: {(qid, '#hex')}} from the SPARQL rows."""
    out = {}
    for r in rows:
        qid = r["item"]["value"].rsplit("/", 1)[-1]
        colour = "#" + r["colour"]["value"].strip().lstrip("#").upper()
        for name in r["names"]["value"].split("|"):
            if fold(name):
                out.setdefault(fold(name), set()).add((qid, colour))
    return out


def match(labels, cands):
    """[(label, qid, colour)] for labels with one unambiguous colour; [label] unmatched."""
    got, missed = [], []
    for label in labels:
        hits = cands.get(fold(label)) or set()
        colours = {c for _q, c in hits}
        if len(colours) == 1:
            qid = sorted(q for q, _c in hits)[0]
            got.append((label, qid, colours.pop()))
        else:
            missed.append(label)
    return got, missed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--country", action="append")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    args = ap.parse_args(argv)
    conn = sqlite3.connect("file:{0}?mode=ro".format(args.db), uri=True)
    client = HttpClient(os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    print("countries:")
    for cc in args.country or cv.COUNTRIES:
        if cc not in COUNTRY_QID:
            continue
        data = cv.build(conn, cc, today)
        labels = sorted({g for g in data["groups"] if g} |
                        {m[1] for m in data["members"] if m[1]})
        if not labels:
            continue
        url = "https://query.wikidata.org/sparql?" + urlencode(
            {"query": QUERY % COUNTRY_QID[cc], "format": "json"})
        rows = client.get_json(url, "party-colours", "wikidata-" + cc)["results"]["bindings"]
        got, missed = match(labels, candidates(rows))
        print("  {0}:".format(cc))
        for label, qid, colour in got:
            print('    "{0}": "{1}"   # wikidata {2}'.format(label.replace('"', '\\"'), colour, qid))
        for label in missed:
            print('    # unmatched: "{0}"'.format(label.replace('"', '\\"')))
    return 0


if __name__ == "__main__":
    sys.exit(main())
