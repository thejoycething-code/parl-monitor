"""DIP: the key, the cursor, and body matching. Nothing here touches the network."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, dip, drain, filter as filt  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "de_documents", os.path.join(ROOT, "tools", "de_documents.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ded = _load()
SPEC = 'components: securitySchemes: ApiKeyQuery: description: "Beispiel: *AbC123.dEf456GhI789jkl*\\n"'


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class KeyTests(unittest.TestCase):
    """The key must never be hardcoded, and never fail silently."""

    def setUp(self):
        dip.forget_key()

    tearDown = setUp

    def test_the_environment_wins(self):
        self.assertEqual(dip.api_key(env={"DIP_API_KEY": "env"},
                                     secrets={"dip_api_key": "sec"},
                                     log=lambda *a: None), "env")

    def test_then_secrets_then_the_published_spec(self):
        self.assertEqual(dip.api_key(env={}, secrets={"dip_api_key": "sec"},
                                     log=lambda *a: None), "sec")
        dip.forget_key()

        class C:
            def get_text(self, u, f, s, archive=True):
                return SPEC
        self.assertEqual(dip.api_key(client=C(), env={}, secrets={},
                                     log=lambda *a: None), "AbC123.dEf456GhI789jkl")

    def test_no_key_anywhere_is_disclosed_not_silent(self):
        """A quiet zero-document run is indistinguishable from a quiet week."""
        said = []

        class C:
            def get_text(self, u, f, s, archive=True):
                raise RuntimeError("spec reflowed")
        self.assertIsNone(dip.api_key(client=C(), env={}, secrets={}, log=said.append))
        self.assertTrue(any("[gap] DIP key" in m for m in said), said)
        self.assertTrue(any("disclosed" in m for m in said), said)

    def test_the_key_is_never_written_into_the_repo(self):
        src = open(os.path.join(ROOT, "src", "dip.py"), encoding="utf-8").read()
        src += open(os.path.join(ROOT, "tools", "de_documents.py"), encoding="utf-8").read()
        self.assertNotIn("R2BZaee", src, "the example key must be discovered, not stored")


class CursorTests(unittest.TestCase):
    """DIP REPEATS the cursor when a result set is exhausted, so a loop that
    waits for an empty page never ends."""

    def _client(self, pages):
        class C:
            def __init__(self):
                self.calls = 0

            def get_json(self, url, feed, slug, archive=True):
                page = pages[min(self.calls, len(pages) - 1)]
                self.calls += 1
                return page
        return C()

    def test_it_stops_when_the_cursor_stops_moving(self):
        pages = [{"documents": [{"id": 1}], "cursor": "a"},
                 {"documents": [{"id": 2}], "cursor": "b"},
                 {"documents": [{"id": 3}], "cursor": "b"}]
        client = self._client(pages)
        got = list(dip.pages(client, "drucksache", "k", log=lambda *a: None))
        self.assertEqual(len(got), 3)
        self.assertEqual(client.calls, 3, "one page past the repeat, then stop")

    def test_an_empty_page_ends_it(self):
        client = self._client([{"documents": [], "cursor": "a"}])
        self.assertEqual(list(dip.pages(client, "vorgang", "k", log=lambda *a: None)), [])

    def test_the_page_cap_is_disclosed(self):
        pages = [{"documents": [{"id": i}], "cursor": str(i)} for i in range(30)]
        said = []
        list(dip.pages(self._client(pages), "drucksache", "k", limit_pages=3, log=said.append))
        self.assertTrue(any("page cap" in m and "disclosed, not silent" in m for m in said), said)


class TermQueryTests(unittest.TestCase):
    def test_only_precise_tier_one_terms_are_asked_of_dip(self):
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
        terms = ded.tier1_terms(tax)
        self.assertIn("Selbstbestimmungsgesetz", terms)
        self.assertIn("Leihmutterschaft", terms)
        self.assertTrue(all(not t.startswith("§") for t in terms),
                        "a section number is not a title query DIP can use")
        self.assertTrue(all(len(t) >= 8 for t in terms),
                        "a short stem would flood the title search")
        self.assertTrue(all(not t.endswith("*") for t in terms),
                        "DIP does its own matching and has no wildcard of ours")


class BodyTests(unittest.TestCase):
    """The title is the weak signal; the body is where the subject lives."""

    def _client(self, text):
        class C:
            def get_json(self, url, feed, slug, archive=True):
                return {"documents": [{"text": text}]} if text is not None else {"documents": []}
        return C()

    def _row(self, conn, titel="Schriftliche Frage"):
        conn.execute(
            "INSERT INTO de_documents (doc_id, kind, nummer, datum, titel, areas, "
            "matched_terms, first_seen, last_seen) VALUES "
            "('drucksache:21/5319','drucksache','21/5319','2026-09-01',?,'[]','[]',"
            "'2026-09-22','2026-09-22')", (titel,))
        conn.commit()

    def _tax(self):
        return (filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml")),
                filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml")))

    def test_a_body_match_gains_ground_a_title_never_would(self):
        conn = store(); self._row(conn)
        tax, wl = self._tax()
        body = ("Der Bundestag wolle beschliessen. " * 3 +
                "Die Bundesregierung wird aufgefordert, die Leihmutterschaft im Ausland "
                "zu verbieten und das Embryonenschutzgesetz entsprechend zu aendern. " +
                "Weitere Ausfuehrungen folgen. " * 3)
        read, gained, failed = ded.read_bodies(conn, self._client(body), "k",
                                               "2026-09-22", tax, wl, log=lambda *a: None)
        self.assertEqual((read, gained, failed), (1, 1, 0))
        row = conn.execute("SELECT areas, excerpt, body_read FROM de_documents").fetchone()
        self.assertIn(10, json.loads(row["areas"]), "surrogacy, from the body")
        self.assertTrue(row["excerpt"], "the passage that earned the match is kept")
        self.assertLessEqual(len(row["excerpt"]), 400, "an excerpt, never the full body")
        self.assertEqual(row["body_read"], "2026-09-22")

    def test_a_document_is_read_once(self):
        conn = store(); self._row(conn)
        tax, wl = self._tax()
        ded.read_bodies(conn, self._client("nichts hier"), "k", "2026-09-22", tax, wl,
                        log=lambda *a: None)
        read, _g, _f = ded.read_bodies(conn, self._client("Leihmutterschaft"), "k",
                                       "2026-09-23", tax, wl, log=lambda *a: None)
        self.assertEqual(read, 0, "body_read means never again")

    def test_an_empty_body_is_stamped_not_retried_for_ever(self):
        conn = store(); self._row(conn)
        tax, wl = self._tax()
        read, gained, failed = ded.read_bodies(conn, self._client(None), "k",
                                               "2026-09-22", tax, wl, log=lambda *a: None)
        self.assertEqual((read, failed), (0, 1))
        self.assertIsNotNone(conn.execute(
            "SELECT body_read FROM de_documents").fetchone()[0])

    def test_the_budget_stops_the_read_and_says_so(self):
        conn = store(); self._row(conn)
        tax, wl = self._tax()
        said = []
        ded.read_bodies(conn, self._client("x"), "k", "2026-09-22", tax, wl,
                        log=said.append, budget=drain.Budget(0))
        self.assertTrue(any("time budget" in m for m in said), said)


class VorgangTests(unittest.TestCase):
    def test_a_stage_change_is_recorded_as_a_movement(self):
        conn = store()
        res = filt.filter_item(*[filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml")),
                                 filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))],
                               text="Leihmutterschaft verbieten")
        v = {"id": 1, "titel": "Leihmutterschaft verbieten", "beratungsstand": "Noch nicht beraten"}
        self.assertFalse(ded.store_vorgang(conn, "2026-09-22", v, res))
        v2 = dict(v, beratungsstand="Verabschiedet")
        self.assertTrue(ded.store_vorgang(conn, "2026-09-23", v2, res))
        row = conn.execute("SELECT stand, prev_stand, moved_date FROM de_vorgaenge").fetchone()
        self.assertEqual((row["stand"], row["prev_stand"], row["moved_date"]),
                         ("Verabschiedet", "Noch nicht beraten", "2026-09-23"))

    def test_it_writes_german_tables_only(self):
        conn = store()
        res = filt.filter_item(filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml")),
                               filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml")),
                               "Leihmutterschaft")
        ded.store_vorgang(conn, "2026-09-22", {"id": 9, "titel": "Leihmutterschaft"}, res)
        conn.commit()
        for table in ("items", "eu_divisions", "mp_events", "dg_consultations"):
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM {0}".format(table)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
