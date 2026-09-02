"""Committee watch and MEP speeches (2026-09-02): the agenda gap closed
sideways -- meetings from eMeeting's discovered backend, the pipeline from
committee documents (stubs filtered by identifier prefix, capped detail
fetches), speeches from the Open Data search API with the taxonomy as the
judge and the search terms only the net.
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


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cmte = _load("eu_committees")
speeches = _load("eu_speeches")


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class CommitteeTests(unittest.TestCase):
    def test_stub_prefix_filter_and_cap_are_structural(self):
        src = open(os.path.join(ROOT, "tools", "eu_committees.py"),
                   encoding="utf-8").read()
        self.assertIn('ident.split("-", 1)[0]', src)
        self.assertIn("DOC_FETCH_CAP", src)
        self.assertIn("disclosed, not silent", src)

    def test_meetings_store_and_dedupe_on_uid(self):
        conn = store()

        class C:
            def get_json(self, url, feed, slug, archive=True):
                return [{"uid": "X1EN", "meetingReference": "LIBE(2026)0902_1",
                         "start": 1788334200000,
                         "title": "LIBE ORDINARY MEETING", "venue": "BRU"}]
        n, gaps = cmte.pull_meetings(conn, C(), "2026-09-01",
                                     log=lambda *a: None)
        self.assertEqual(gaps, 0)
        rows = conn.execute("SELECT * FROM eu_cmte_meetings").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-09-02")
        self.assertEqual(rows[0]["committee"], "LIBE")


class SpeechTests(unittest.TestCase):
    def test_taxonomy_judges_what_the_net_catches(self):
        conn = store()

        class C:
            def get_json(self, url, feed, slug, archive=True):
                if "/speeches/" in url:
                    return {"data": [{
                        "had_participation": {
                            "had_participant_person": ["person/9"]},
                        "recorded_in_a_realization_of": [{
                            "api:xmlFragment": {"en": "<p>Name . Text about "
                              "the persecution of Christians in Nigeria and "
                              "abortion access.</p>"}}]}]}
                return {"data": [{
                    "activity_id": "SP-1", "activity_date": "2026-07-09",
                    "activity_label": {"en": "Nigeria debate"}}]}
        cands, stored, gaps = speeches.pull(conn, C(), "2026-09-01",
                                            log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertGreaterEqual(stored, 1)
        row = conn.execute("SELECT * FROM eu_speeches").fetchone()
        self.assertEqual(row["person_id"], "9")
        self.assertTrue(json.loads(row["areas"]))

    def test_an_offside_speech_is_never_stored(self):
        conn = store()

        class C:
            def get_json(self, url, feed, slug, archive=True):
                if "/speeches/" in url:
                    return {"data": [{
                        "had_participation": {
                            "had_participant_person": ["person/9"]},
                        "recorded_in_a_realization_of": [{
                            "api:xmlFragment": {"en": "<p>Name . Vineyard "
                              "replanting authorisations text.</p>"}}]}]}
                return {"data": [{
                    "activity_id": "SP-2", "activity_date": "2026-07-09",
                    "activity_label": {"en": "Agriculture debate"}}]}
        cands, stored, gaps = speeches.pull(conn, C(), "2026-09-01",
                                            log=lambda *a: None)
        self.assertEqual(stored, 0, "the net nominates; the taxonomy judges")


if __name__ == "__main__":
    unittest.main()
