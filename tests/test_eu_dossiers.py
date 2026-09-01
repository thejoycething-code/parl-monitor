"""EU dossier board, phase 2a: watched procedures, movement marked.

The board is CURATED (config/eu_watchlist.yaml, verified ids only) because
the procedures listing carries no titles: enumerating would cost a detail
fetch per procedure against a 500/5min limit. Movement is a change of
current_stage between runs, marked like the Westminster board's "▲ moved".
"""

import importlib.util
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db


def _load():
    spec = importlib.util.spec_from_file_location(
        "eu_dossiers", os.path.join(ROOT, "tools", "eu_dossiers.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eud = _load()

WATCH = [{"process_id": "2022-0155", "label": "2022/0155(COD)",
          "title": "CSA Regulation", "areas": [7], "why": "chat control"}]


def reply(stage):
    return {"data": [{
        "process_id": "2022-0155",
        "process_title": {"en": "Laying down rules to prevent and combat "
                                "child sexual abuse"},
        "current_stage": "http://publications.europa.eu/resource/authority/"
                         "procedure-phase/" + stage}]}


class StagedClient:
    def __init__(self, stage):
        self.stage = stage

    def get_json(self, url, feed, slug, archive=True):
        return reply(self.stage)


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class MovementTests(unittest.TestCase):
    def test_first_sight_is_new_then_no_change(self):
        conn = store()
        eud.track(conn, StagedClient("RDG1"), WATCH, "2026-09-01",
                  log=lambda *a: None)
        row = eud.board_rows(conn, "2026-09-01")[0]
        self.assertEqual((row["stage"], row["movement"]),
                         ("First reading", "NEW"))
        eud.track(conn, StagedClient("RDG1"), WATCH, "2026-09-08",
                  log=lambda *a: None)
        row = eud.board_rows(conn, "2026-09-08")[0]
        self.assertEqual(row["movement"], "no change")

    def test_a_stage_change_is_movement_named_both_ends(self):
        conn = store()
        eud.track(conn, StagedClient("RDG1"), WATCH, "2026-09-01",
                  log=lambda *a: None)
        moved, _ = eud.track(conn, StagedClient("RDG2"), WATCH, "2026-09-08",
                             log=lambda *a: None)
        self.assertEqual(moved, 1)
        row = eud.board_rows(conn, "2026-09-08")[0]
        self.assertEqual(row["movement"],
                         "▲ moved (First reading → Second reading)")

    def test_an_unknown_stage_code_renders_as_itself_never_guessed(self):
        conn = store()
        eud.track(conn, StagedClient("XYZZY"), WATCH, "2026-09-01",
                  log=lambda *a: None)
        self.assertEqual(eud.board_rows(conn, "2026-09-01")[0]["stage"],
                         "XYZZY")

    def test_a_dead_api_is_a_recorded_gap_and_the_board_keeps_last_state(self):
        from src.http import FetchError

        class Dead:
            def get_json(self, url, feed, slug, archive=True):
                raise FetchError(url, feed, slug, 3, "boom")

        conn = store()
        eud.track(conn, StagedClient("RDG1"), WATCH, "2026-09-01",
                  log=lambda *a: None)
        moved, gaps = eud.track(conn, Dead(), WATCH, "2026-09-08",
                                log=lambda *a: None)
        self.assertEqual((moved, gaps), (0, 1))
        self.assertEqual(eud.board_rows(conn, "2026-09-08")[0]["stage"],
                         "First reading")


class WatchlistTests(unittest.TestCase):
    def test_the_shipped_watchlist_parses_and_carries_why_lines(self):
        wl = eud.load_watchlist()
        self.assertGreaterEqual(len(wl), 2)
        for d in wl:
            self.assertTrue(d.get("process_id"))
            self.assertTrue(d.get("why"),
                            "{0} needs a why line".format(d.get("label")))


if __name__ == "__main__":
    unittest.main()
