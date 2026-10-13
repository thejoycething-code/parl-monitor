"""Shared fixture loaders for the UN gap tests (tests/fixtures/un/).

The fixtures are the raw responses archived on 13 October 2026 while fixing
the gaps that let the 12 October 2026 GA vote on the political declaration on
pandemic prevention, preparedness and response go unseen.
"""

import gzip
import json
import os

from src import filter as filt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "un")


def fixture_json(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as h:
        return json.load(h)


def fixture_text(name):
    path = os.path.join(FIX, name)
    if name.endswith(".gz"):
        with gzip.open(path, "rb") as h:
            return h.read().decode("utf-8")
    with open(path, encoding="utf-8") as h:
        return h.read()


def un_filter():
    return (filt.load_taxonomy(os.path.join(ROOT, "config", "un-taxonomy.yaml")),
            filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml")))
