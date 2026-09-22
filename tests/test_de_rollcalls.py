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

from src import db, drain  # noqa: E402


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

    def test_every_recorded_vote_is_stored_matched_or_not(self):
        """Volume is tiny and the label is terse, so a vote that matches
        nothing is still stored: the watching list is the proof it was read."""
        conn = store()
        seen, new, gaps = der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        self.assertEqual((seen, new, gaps), (2, 2, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM de_divisions").fetchone()[0], 2)
        row = conn.execute("SELECT * FROM de_divisions WHERE vote_id='6600'").fetchone()
        self.assertEqual(json.loads(row["areas"]), [],
                         "the Tempolimit vote is not our ground and says so")
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

    def test_members_carry_their_fraktion_without_the_legislature(self):
        """The Fraktion alone, not abgeordnetenwatch's welded-on period.

        This test used to assert "SPD (Bundestag 2025 - 2029)" -- it pinned
        the bug as the contract. abgeordnetenwatch labels a mandate and a
        fraction with the legislature attached, and stored raw that suffix
        went into every German member's NAME and PARTY: it broke any join on
        a name, and the edition's Fraktion splits would have printed "SPD
        (Bundestag 2025 - 2029) 2/1/0". The period is already held in its own
        `legislature` column, so the suffix was redundant as well as wrong.
        """
        conn = store()
        der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        rows = {r["name"]: r["party"] for r in conn.execute("SELECT name, party FROM de_members")}
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows["Sanae Abdi"], "SPD")
        self.assertNotIn("Sanae Abdi (Bundestag 2025 - 2029)", rows,
                         "the name kept the legislature too")

    def test_the_legislature_is_still_recorded_in_its_own_column(self):
        """Stripping the suffix must not LOSE the period -- only move the
        reader to the column that already held it."""
        conn = store()
        der.pull(conn, FakeClient(), "2026-09-22", log=lambda *a: None)
        legs = {r[0] for r in conn.execute(
            "SELECT legislature FROM de_members")}
        self.assertTrue(any(legs), "the legislature column is empty")

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

    def test_a_row_missing_a_column_the_schema_gained_is_refetched_once(self):
        """The 68 votes collected before `parliament` existed were `known`,
        so nothing would ever have looked at them again."""
        conn = store()
        client = FakeClient()
        der.pull(conn, client, "2026-09-22", log=lambda *a: None)
        conn.execute("UPDATE de_divisions SET parliament = NULL WHERE vote_id = '6600'")
        conn.commit()
        der.pull(conn, client, "2026-09-23", log=lambda *a: None)
        self.assertEqual(client.detail_calls, 3, "exactly the incomplete row, once")
        self.assertIsNotNone(conn.execute(
            "SELECT parliament FROM de_divisions WHERE vote_id='6600'").fetchone()[0])

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


class ClassificationTests(unittest.TestCase):
    """Areas come from config/taxonomy-de.yaml, never the English one."""

    def _poll(self, label, topics=("Recht",)):
        client = FakeClient()
        client.get_json = lambda url, feed, slug, archive=True: (
            PERIODS if "parliament-periods" in url else
            {"data": [{"id": 900}]} if "/polls?" in url else
            poll(900, label, VOTES, topics=topics))
        return client

    def test_a_german_label_is_matched_in_german(self):
        conn = store()
        der.pull(conn, self._poll("Entwurf eines Suizidhilfegesetzes"),
                 "2026-09-22", log=lambda *a: None)
        row = conn.execute("SELECT areas, matched_terms, tier FROM de_divisions").fetchone()
        self.assertIn(2, json.loads(row["areas"]), "assisted dying")
        self.assertTrue(json.loads(row["matched_terms"]))

    def test_the_apis_own_topics_are_matched_too(self):
        """The label can be bare; the German topic labels carry subject."""
        conn = store()
        der.pull(conn, self._poll("Antrag der Fraktion", topics=("Schwangerschaftsabbruch",)),
                 "2026-09-22", log=lambda *a: None)
        self.assertIn(1, json.loads(conn.execute(
            "SELECT areas FROM de_divisions").fetchone()["areas"]))

    def test_ordinary_business_matches_nothing(self):
        conn = store()
        der.pull(conn, self._poll("Sportfoerdergesetz", topics=("Sport",)),
                 "2026-09-22", log=lambda *a: None)
        self.assertEqual(json.loads(conn.execute(
            "SELECT areas FROM de_divisions").fetchone()["areas"]), [])

    def test_reclassify_rederives_offline_without_refetching(self):
        """A stored vote is never refetched, so a taxonomy change reaches
        nothing without this pass."""
        conn = store()
        client = self._poll("Entwurf eines Suizidhilfegesetzes")
        der.pull(conn, client, "2026-09-22", log=lambda *a: None)
        before = client.detail_calls
        conn.execute("UPDATE de_divisions SET areas = '[]', matched_terms = '[]', tier = NULL")
        conn.commit()
        changed, gained, lost = der.reclassify(conn, "2026-09-23", log=lambda *a: None)
        self.assertEqual((changed, gained, lost), (1, 1, 0))
        self.assertIn(2, json.loads(conn.execute(
            "SELECT areas FROM de_divisions").fetchone()["areas"]))
        self.assertEqual(client.detail_calls, before, "reclassify is offline")


class ParliamentTests(unittest.TestCase):
    """All seventeen: the Bundestag and the sixteen Landtage."""

    PARLIAMENTS = {"data": [{"id": 5, "label": "Bundestag"},
                            {"id": 13, "label": "Bayern"},
                            {"id": 1, "label": "EU-Parlament"}]}

    def _client(self):
        client = FakeClient()

        def get_json(url, feed, slug, archive=True):
            if "/parliaments?" in url:
                return self.PARLIAMENTS
            if "parliament-periods" in url:
                return PERIODS
            if "/polls?" in url:
                return {"data": [{"id": 7000}]}
            client.detail_calls += 1
            return poll(7000, "Ein Antrag", VOTES)
        client.get_json = get_json
        return client

    def test_the_european_parliament_is_left_to_its_own_collector(self):
        got = der.parliaments(self._client())
        self.assertEqual([p for p, _ in got], ["5", "13"])
        self.assertNotIn("1", [p for p, _ in got])

    def test_the_parliament_is_recorded_on_the_vote_and_the_member(self):
        conn = store()
        der.pull(conn, self._client(), "2026-09-22", parliament="13",
                 parliament_label="Bayern", log=lambda *a: None)
        row = conn.execute("SELECT parliament, parliament_label FROM de_divisions").fetchone()
        self.assertEqual((row["parliament"], row["parliament_label"]), ("13", "Bayern"))
        m = conn.execute("SELECT parliament FROM de_members LIMIT 1").fetchone()
        self.assertEqual(m["parliament"], "13")

    def test_a_parliament_with_no_legislature_is_skipped_not_crashed(self):
        conn = store()
        client = self._client()
        client.get_json = lambda url, feed, slug, archive=True: (
            {"data": []} if "parliament-periods" in url else self.PARLIAMENTS)
        said = []
        seen, new, gaps = der.pull(conn, client, "2026-09-22", parliament="99",
                                   parliament_label="Nirgendwo", log=said.append)
        self.assertEqual((seen, new, gaps), (0, 0, 0))
        self.assertTrue(any("no legislature listed" in m for m in said), said)

    def test_the_budget_stops_the_sweep_and_says_so(self):
        conn = store()
        said = []
        der.pull(conn, self._client(), "2026-09-22", log=said.append,
                 budget=drain.Budget(0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM de_divisions").fetchone()[0], 0)
        self.assertTrue(any("time budget" in m for m in said), said)
