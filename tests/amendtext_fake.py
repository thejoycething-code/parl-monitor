"""A client that answers from fixtures captured from the live sources, for
the country amendment-text readers' tests (src/amendtext_<cc>.py).

tests/fixtures/amendtext/<cc>/index.json maps each URL a reader asked for to
the file holding the reply, byte for byte, plus the stored vote rows and the
outcome measured live. A key in a URL ("apikey=") is removed before the
lookup, so no key is ever kept in a fixture. A URL with no fixture answers
404, as a missing page would."""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KEY = re.compile(r"([?&])apikey=[^&]*&?")


def norm(url):
    return _KEY.sub(r"\1", url).rstrip("?&")


class FixtureClient:
    def __init__(self, cc):
        self.dir = os.path.join(ROOT, "tests", "fixtures", "amendtext", cc)
        with open(os.path.join(self.dir, "index.json"), encoding="utf-8") as fh:
            self.index = json.load(fh)
        self.urls = {norm(u): f for u, f in self.index["urls"].items()}
        self.asked = []
        self.last_headers = {}

    def rows(self):
        return self.index["rows"]

    def expected(self):
        return self.index["expected"]

    def get_bytes(self, url, feed=None, slug=None, *a, **k):
        from src.http import FetchError
        self.asked.append(url)
        name = self.urls.get(norm(url))
        if name is None:
            raise FetchError(url, feed, slug, 1, Exception("HTTP Error 404: Not Found (no fixture)"))
        with open(os.path.join(self.dir, name), "rb") as fh:
            return fh.read()

    def get_text(self, url, feed=None, slug=None, *a, **k):
        return self.get_bytes(url, feed, slug).decode("utf-8", "replace")

    def get_json(self, url, feed=None, slug=None, *a, **k):
        return json.loads(self.get_bytes(url, feed, slug).decode("utf-8"))
