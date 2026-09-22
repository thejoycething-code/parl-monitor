"""Bundestag recorded votes (tools/de_rollcalls.py). Nothing here touches the network."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "de_rollcalls", os.path.join(ROOT, "tools", "de_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


der = _load()

PERIODS = {"data": [
    {"id": 161, "label": "Bundestag 2025 - 2029", "start_date_period": "2025-03-25"},
    {"id": 132, "label": "Bundestag 2021 - 2025", "start_date_period": "2021-10-26"}]}
POLLS = {"data": [{"id": 6600}, {"id": 6601}]}
INTRO = ('<p>Der Bundestag hat einen <a class="link-read-more" '
         'href="https://dserver.bundestag.de/btd/21/053/2105319.pdf">Gesetzentwurf</a> '
         'der <a href="https://www.abgeordnetenwatch.de/bundestag/abgeordnete">Fraktion</a>...')


def poll(pid, label, votes, accepted=False, topics=("Verkehr",)):
    return {"data": {
        "id": pid, "label": label, "field_poll_date": "2026-07-09",
        "field_accepted": accepted, "field_intro": INTRO,
        "field_committees": [{"label": "Verkehrsausschuss"}],
        "field_topics": [{"label": t} for t in topics],
        "related_data": {"votes": votes}}}


def voter(vid, name, party, how):
    return {"id": vid, "vote": how,
            "mandate": {"id": vid, "label": name},
            "fraction": {"label": party}}


VOTES = [voter(1, "Sanae Abdi", "SPD (Bundestag 2025 - 2029)", "no"),
         voter(2, "Anna Muster", "BÜNDNIS 90/­DIE GRÜNEN (Bundestag 2025 - 2029)", "yes"),
         voter(3, "Otto Beispiel", "CDU/CSU (Bundestag 2025 - 2029)", "no"),
         voter(4, "Lea Fehlt", "Die Linke (Bundestag 2025 - 2029)", "no_show"),
         voter(5, "Max Enthalt", "fraktionslos (Bundestag 2025 - 2029)", "abstain")]


class FakeClient:
    def __init__(self, polls=None):
        self.detail_calls = 0
        self.polls = polls or POLLS

    def get_json(self, url, feed, slug, archive=True):
        if "parliament-periods" in url:
            return PERIODS
        if "/polls?" in url:
            return self.polls
        if "/polls/" in url:
            self.detail_calls += 1
            pid = url.split("/polls/")[1].split("?")[0]
            return poll(int(pid), "Einführung eines allgemeinen Tempolimits", VOTES)
        raise AssertionError(url)


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class RollCallTests(unittest.TestCase):
    def test_the_newest_legislature_is_chosen(self):
        self.assertEqual(der.current_legislature(FakeClient())[0], "161")

    def test_every_recorded_vote_is_stored_unclassified(self):
        """The English taxonomy matched 1 useful vote in 68 over this House,
        so a filter here would discard the lot and report success."""
        conn = store()
        seen, new, gaps = der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        self.assertEqual((seen, new, gaps), (2, 2, 0))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(de_divisions)")}
        for banned in ("areas", "matched_terms", "tier", "triage_score"):
            self.assertNotIn(banned, cols,
                             "nothing is classified until the German terms exist")
        row = conn.execute("SELECT * FROM de_divisions WHERE vote_id='6600'").fetchone()
        self.assertEqual(row["label"], "Einführung eines allgemeinen Tempolimits")
        self.assertEqual(row["committee"], "Verkehrsausschuss")
        self.assertEqual(json.loads(row["topics"]), ["Verkehr"])

    def test_the_tally_is_counted_from_the_member_rows(self):
        conn = store()
        der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        r = conn.execute("SELECT yes, no, abstain, absent FROM de_divisions WHERE vote_id='6600'").fetchone()
        self.assertEqual(tuple(r), (1, 2, 1, 1))

    def test_the_houses_own_outcome_is_stored_never_derived(self):
        """More no than yes here, and the House still says what it says."""
        conn = store()
        client = FakeClient()
        client.get_json = lambda url, feed, slug, archive=True: (
            PERIODS if "parliament-periods" in url else
            {"data": [{"id": 1}]} if "/polls?" in url else
            poll(1, "Angenommen trotz allem", VOTES, accepted=True))
        der.pull(conn, client, "2026-09-22", log=lambda *a: None)
        r = conn.execute("SELECT accepted, yes, no FROM de_divisions").fetchone()
        self.assertEqual(r["accepted"], 1)
        self.assertGreater(r["no"], r["yes"], "the outcome is not read off the tallies")

    def test_members_carry_their_fraktion(self):
        conn = store()
        der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        rows = {r["name"]: r["party"] for r in conn.execute("SELECT name, party FROM de_members")}
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows["Sanae Abdi"], "SPD (Bundestag 2025 - 2029)")

    def test_an_absence_is_recorded_as_a_position(self):
        conn = store()
        der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        pos = {r["person_id"]: r["position"] for r in
               conn.execute("SELECT person_id, position FROM de_votes WHERE vote_id='6600'")}
        self.assertEqual(pos["4"], "no_show")
        self.assertEqual(pos["5"], "abstain")

    def test_a_stored_vote_is_never_refetched(self):
        conn = store()
        client = FakeClient()
        der.pull(conn, client, "2026-09-22", log=lambda *a: None)
        self.assertEqual(client.detail_calls, 2)
        der.pull(conn, client, "2026-09-23", log=lambda *a: None)
        self.assertEqual(client.detail_calls, 2, "a completed vote costs nothing twice")

    def test_the_drucksache_is_recorded_for_phase_three(self):
        conn = store()
        der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        url = conn.execute("SELECT document_url FROM de_divisions WHERE vote_id='6600'").fetchone()[0]
        self.assertEqual(url, "https://dserver.bundestag.de/btd/21/053/2105319.pdf")
        self.assertIsNone(der.document_url("<p>no link here</p>"))

    def test_the_cap_is_disclosed(self):
        conn = store()
        said = []
        seen, new, gaps = der.pull(conn, FakeClient(), "2026-09-22", log=said.append, limit=1)
        self.assertEqual(new, 1)
        self.assertTrue(any("fetch cap" in m and "disclosed, not silent" in m for m in said), said)

    def test_it_writes_german_tables_only(self):
        conn = store()
        der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        for table in ("items", "eu_divisions", "mp_events", "dg_consultations"):
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0], 0,
                             table + " must not be touched by the German collector")


if __name__ == "__main__":
    unittest.main()
