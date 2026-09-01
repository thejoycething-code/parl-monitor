"""EU adopted texts, phase 2c: resolutions taxonomy-matched, and the
dossier watchlist's auto-proposal feed. Proposal, never addition: a
candidate must be a matched text whose parsed procedure id RESOLVES in
the procedures API and is not already watched; a human edits the config.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db
from src.http import FetchError


def _load():
    spec = importlib.util.spec_from_file_location(
        "eu_texts", os.path.join(ROOT, "tools", "eu_texts.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eut = _load()

TEXTS = {"data": [
    {"identifier": "TA-10-2026-0250", "document_date": "2026-07-09",
     "title_dcterms": {"en": "Ongoing persecution of Christians in Nigeria"},
     "inverse_decided_on_a_realization_of":
         ["eli/dl/event/2025-2248-DEC-DCPL-2026-07-09"]},
    {"identifier": "TA-10-2026-0100", "document_date": "2026-07-01",
     "title_dcterms": {"en": "Common agricultural policy transition rules"},
     "inverse_decided_on_a_realization_of":
         ["eli/dl/event/2025-0001-DEC-DCPL-2026-07-01"]},
    {"identifier": "TA-10-2026-0001", "document_date": "2026-01-05",
     "title_dcterms": {"en": "An old one outside the sixty-day window "
                             "about abortion"},
     "inverse_decided_on_a_realization_of": []},
]}


class FakeClient:
    def __init__(self, verify_ok=True):
        self.verify_ok = verify_ok

    def get_json(self, url, feed, slug, archive=True):
        if "adopted-texts" in url:
            return TEXTS
        if "/procedures/" in url:
            if not self.verify_ok:
                raise FetchError(url, feed, slug, 1, "HTTP Error 404")
            return {"data": [{"label": "2025/2248(INI)"}]}
        raise AssertionError(url)


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class TextsTests(unittest.TestCase):
    def test_window_matching_and_procedure_parsing(self):
        conn = store()
        total, ours = eut.pull(conn, FakeClient(), "2026-09-01",
                               log=lambda *a: None)
        # the 1 July and January texts both fall outside the 60-day window
        # (cutoff 3 July on 1 September)
        self.assertEqual((total, ours), (1, 1))
        row = conn.execute("SELECT * FROM eu_texts WHERE identifier = "
                           "'TA-10-2026-0250'").fetchone()
        self.assertEqual(json.loads(row["areas"]), [8])
        self.assertEqual(row["procedure"], "2025-2248")

    def test_candidates_are_verified_and_exclude_the_watched(self):
        conn = store()
        eut.pull(conn, FakeClient(), "2026-09-01", log=lambda *a: None)
        cands = eut.watchlist_candidates(conn, FakeClient(),
                                         log=lambda *a: None)
        self.assertEqual([c["process_id"] for c in cands], ["2025-2248"])
        self.assertEqual(cands[0]["label"], "2025/2248(INI)")

    def test_an_unverifiable_procedure_is_never_proposed(self):
        conn = store()
        eut.pull(conn, FakeClient(), "2026-09-01", log=lambda *a: None)
        cands = eut.watchlist_candidates(conn, FakeClient(verify_ok=False),
                                         log=lambda *a: None)
        self.assertEqual(cands, [])

    def test_the_tool_writes_eu_texts_only(self):
        src = open(os.path.join(ROOT, "tools", "eu_texts.py"),
                   encoding="utf-8").read()
        self.assertNotIn("INSERT INTO items", src)
        self.assertNotIn("INTO mp_events", src)
        self.assertNotIn("eu_watchlist.yaml\", \"w", src.replace("'", '"'))


if __name__ == "__main__":
    unittest.main()
