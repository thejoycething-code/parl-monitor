"""Measure how precise each PQ sweep term actually is.

    python3 tools/check_sweep_terms.py            # every configured term
    python3 tools/check_sweep_terms.py "term"     # one term, plus variants

The Written Questions API appears to match sweep terms loosely rather than
as phrases, so a term made of common words matches almost everything:
"age assurance" reported 77,980 results whose newest were about goods
vehicles, overseas students and pensioners' income tax. The sweep takes the
newest six, so such a term contributes nothing while looking like coverage.
Hyphenating usually forces a phrase match ("age-assurance": 258 results,
all about age assurance) -- but not always, and some terms answer HTTP 500
either way, so each one has to be measured rather than assumed.

Read the output as: low total + on-topic headings = a good term. A total in
the tens of thousands means the term is contributing noise. A 500 means the
API cannot serve it at all and the sweep will log a gap.

The API is slow (15-60s per term), so this takes a few minutes. It is a
diagnostic, never part of the weekly run.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.http import HttpClient

API = "https://questions-statements-api.parliament.uk/api/writtenquestions/questions"
LOOSE = 5000   # totals above this mean the term is matching far too broadly


def probe(term, user_agent, take=3):
    url = API + "?" + urllib.parse.urlencode(
        {"searchTerm": term, "answered": "Answered", "take": str(take)})
    started = time.time()
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": user_agent, "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.load(response)
    except Exception as exc:
        return {"term": term, "secs": time.time() - started, "error": str(exc)[:40]}
    headings = [((row.get("value") or {}).get("heading") or "")
                for row in (payload.get("results") or [])]
    return {"term": term, "secs": time.time() - started,
            "total": payload.get("totalResults"), "headings": headings}


def verdict(result):
    if result.get("error"):
        return "FAILS", result["error"]
    total = result.get("total") or 0
    if total > LOOSE:
        return "LOOSE", "{0:,} matches; newest are probably unrelated".format(total)
    return "good ", "{0:,} matches".format(total)


def main():
    import yaml
    ua = HttpClient(raw_dir="/tmp").user_agent
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    if argv:
        terms = []
        for term in argv:                     # a term and its obvious variants
            terms += [term, term.replace(" ", "-"), term.split()[0]]
        terms = list(dict.fromkeys(terms))
    else:
        with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as fh:
            terms = yaml.safe_load(fh)["pq_sweep_terms"]

    print("{0:<26} {1:<6} {2:<7} {3}".format("term", "state", "secs", "detail"))
    problems = []
    for term in terms:
        result = probe(term, ua)
        state, detail = verdict(result)
        print("{0:<26} {1:<6} {2:<7.1f} {3}".format(
            term[:26], state, result["secs"], detail))
        for heading in (result.get("headings") or [])[:2]:
            print("{0:<41}{1}".format("", heading[:60]))
        if state != "good ":
            problems.append((term, state, detail))
    if problems:
        print("\n{0} term(s) worth changing:".format(len(problems)))
        for term, state, detail in problems:
            print("  {0:<26} {1} {2}".format(term, state, detail))
        print("\nTry the hyphenated form; if that 500s too, try the most "
              "distinctive single word. Measure, never assume: 'assisted "
              "dying' works spaced and 500s hyphenated.")
    else:
        print("\nevery term is precise and answering")
    return 0


if __name__ == "__main__":
    sys.exit(main())
