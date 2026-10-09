"""France: Assemblee nationale deputies, dossiers and scrutins
(tools/fr_rollcalls.py). No network.

The fixtures under tests/fixtures/fr are the AN's own files, downloaded on
9 October 2026 and trimmed: seven real scrutins (the aide a mourir law's
final vote and first-reading vote, an amendment on it, a budget amendment,
a motion de censure, a scrutin with mises au point, a defence article), the
dossiers they belong to with their documents, three sitting deputies with
every political group, and one departed deputy in a one-record AMO30.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, fr_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "fr")


def _load():
    spec = importlib.util.spec_from_file_location(
        "fr_rollcalls", os.path.join(ROOT, "tools", "fr_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


frr = _load()
# Pinned to the Quebec list: these tests describe the interim classifier,
# and must not change meaning the day a France list is approved.
TAX = filt.load_taxonomy(frr.TAXONOMY_QC)
WL = frr.empty_watchlist()
TODAY = "2026-10-09"


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


class FakeClient:
    """Serves the fixture zips by URL; anything else is a FetchError."""

    def __init__(self, missing=()):
        self.pages = {
            frr.SCRUTINS.format(17): fixture("Scrutins.json.zip"),
            frr.DOSSIERS.format(17): fixture("Dossiers_Legislatifs.json.zip"),
            frr.AMO10.format(17): fixture("AMO10_deputes_actifs_mandats_actifs_organes.json.zip"),
            frr.AMO30.format(17): fixture(
                "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip"),
        }
        for url in missing:
            self.pages.pop(url)
        self.asked = []

    def get_bytes(self, url, feed, slug, archive=True, **kw):
        self.asked.append((url, archive))
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "404")
        return self.pages[url]


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def full_run(conn, client=None):
    client = client or FakeClient()
    frr.pull_members(conn, client, TODAY)
    dossiers, _read, _ours = frr.pull_dossiers(conn, client, TODAY, tax=TAX, wl=WL)
    result = frr.pull_scrutins(conn, client, TODAY, dossiers, tax=TAX, wl=WL, log=lambda *a: None)
    frr.fill_departed(conn, client, TODAY, log=lambda *a: None)
    return result


def scrutin(n):
    zf = zipfile.ZipFile(os.path.join(FIX, "Scrutins.json.zip"))
    return frr.parse_scrutin(json.loads(zf.read("json/VTANR5L17V{0}.json".format(n))))


def division(conn, n):
    cur = conn.execute("SELECT * FROM fr_divisions WHERE division_key=?", ("an-17-{0}".format(n),))
    cols = [c[0] for c in cur.description]
    return dict(zip(cols, cur.fetchone()))


class ParsingTests(unittest.TestCase):
    def test_the_aide_a_mourir_final_vote_parses_with_every_position(self):
        s = scrutin(8280)
        self.assertEqual((s["date"], s["vote_type"], s["result"]), ("2026-07-15", "SPS", "adopté"))
        self.assertEqual((s["pour"], s["contre"], s["abstentions"]), (291, 241, 29))
        self.assertEqual(s["dossier_ref"], "DLR5L17N51670")
        counted = {}
        for p in s["positions"]:
            counted[p["position"]] = counted.get(p["position"], 0) + 1
        self.assertEqual((counted["pour"], counted["contre"], counted["abstention"]),
                         (291, 241, 29))
        self.assertTrue(all(p["group_ref"].startswith("PO") for p in s["positions"]))

    def test_a_mise_au_point_is_kept_beside_the_recorded_position(self):
        s = scrutin(7045)
        corrected = [p for p in s["positions"] if p["intended"]]
        self.assertEqual(len(corrected), 2)
        # The recorded position stands; what the deputy meant is beside it.
        for p in corrected:
            self.assertNotEqual(p["position"], p["intended"])

    def test_not_a_scrutin_is_none(self):
        self.assertIsNone(frr.parse_scrutin({}))
        self.assertIsNone(frr.parse_scrutin({"scrutin": {"uid": "x"}}))

    def test_votant_shapes(self):
        self.assertEqual(frr._votants(None), [])
        self.assertEqual(frr._votants({"votant": {"acteurRef": "PA1"}}), [{"acteurRef": "PA1"}])
        self.assertEqual(frr._votants([None, {"votant": [{"acteurRef": "PA1"}, {"acteurRef": "PA2"}]}]),
                         [{"acteurRef": "PA1"}, {"acteurRef": "PA2"}])

    def test_the_dossier_timeline_reaches_promulgation(self):
        zf = zipfile.ZipFile(os.path.join(FIX, "Dossiers_Legislatifs.json.zip"))
        d = frr.parse_dossier(json.loads(zf.read(
            "json/dossierParlementaire/DLR5L17N51670.json")))
        self.assertEqual(d["title"], "Fin de vie")
        self.assertEqual((d["last_act"], d["last_act_at"]), ("PROM-PUB", "2026-08-18"))
        self.assertEqual(d["promulgated_at"], "2026-08-18")
        self.assertIn("ppl24-661", d["senat_url"])

    def test_text_name_strips_the_reading(self):
        self.assertEqual(
            frr.text_name("l'amendement n° 238 de Mme Lorho à l'article 17 de la proposition "
                          "de loi relative au droit à l'aide à mourir (première lecture)."),
            "proposition de loi relative au droit à l'aide à mourir")
        self.assertEqual(frr.text_name("la motion de rejet préalable"), None)

    def test_a_deputy_has_a_group_and_a_seat(self):
        zf = zipfile.ZipFile(os.path.join(FIX, "AMO10_deputes_actifs_mandats_actifs_organes.json.zip"))
        name = [n for n in zf.namelist() if n.startswith("json/acteur/")][0]
        m = frr.parse_acteur(json.loads(zf.read(name)))
        self.assertTrue(m["deputy"])
        self.assertTrue(m["acteur_ref"].startswith("PA"))
        self.assertTrue(m["group_ref"].startswith("PO"))
        self.assertTrue(m["department"])


class JoinAndClassifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = store()
        cls.result = full_run(cls.conn)

    def test_all_seven_are_stored_with_no_gaps(self):
        stored, _ours, gaps = self.result
        self.assertEqual((stored, gaps), (7, 0))

    def test_a_scrutin_that_names_its_dossier_is_joined_by_ref(self):
        d = division(self.conn, 8280)
        self.assertEqual((d["dossier_ref"], d["dossier_via"]), ("DLR5L17N51670", "ref"))

    def test_one_that_does_not_is_joined_by_its_texts_title(self):
        # The first-reading vote and an amendment name no dossier; their
        # titles name the bill, and one dossier carries that bill.
        for n in (2107, 2091):
            d = division(self.conn, n)
            self.assertEqual((d["dossier_ref"], d["dossier_via"]), ("DLR5L17N51670", "title"), n)

    def test_a_title_several_dossiers_carry_is_left_unjoined(self):
        d = division(self.conn, 4060)  # an amendment to the 2026 budget bill
        self.assertIsNone(d["dossier_ref"])
        self.assertIsNone(d["dossier_via"])

    def test_the_quebec_list_misses_aide_a_mourir_and_the_dossier_lends_it(self):
        # The gap the France list closes: "aide a mourir" is not a Quebec
        # term, so the amendment's own title matches nothing. Area 2 comes
        # from its dossier (watchlist-fr and the tier-2 "fin de vie").
        d = division(self.conn, 2091)
        self.assertEqual(json.loads(d["own_areas"]), [])
        self.assertEqual(json.loads(d["areas"]), [2])

    def test_a_motion_de_censure_is_not_free_speech(self):
        d = division(self.conn, 7979)
        self.assertEqual(d["vote_type"], "MOC")
        self.assertNotIn(7, json.loads(d["areas"]))
        self.assertFalse(frr.on_our_ground(json.loads(d["areas"])))

    def test_a_defence_article_is_not_ours(self):
        d = division(self.conn, 6722)
        self.assertEqual(d["dossier_ref"], "DLR5L17N54083")
        self.assertEqual(json.loads(d["areas"]), [])

    def test_the_dossier_is_ours_by_key(self):
        areas, terms = self.conn.execute(
            "SELECT areas, matched_terms FROM fr_dossiers WHERE dossier_ref='DLR5L17N51670'"
        ).fetchone()
        self.assertEqual(json.loads(areas), [2])
        self.assertIn("watch:DLR5L17N51670", json.loads(terms))

    def test_every_position_is_stored_with_the_group_at_the_vote(self):
        n, groups = self.conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT group_ref) FROM fr_votes "
            "WHERE division_key='an-17-8280'").fetchone()
        self.assertEqual(n, 291 + 241 + 29 + 0)
        self.assertGreater(groups, 5)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM fr_votes WHERE division_key='an-17-7045' "
            "AND intended IS NOT NULL").fetchone()[0], 2)

    def test_sitting_and_departed_deputies_are_named(self):
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM fr_members WHERE current=1").fetchone()[0], 3)
        name, current = self.conn.execute(
            "SELECT name, current FROM fr_members WHERE acteur_ref='PA1327'").fetchone()
        self.assertTrue(name)
        self.assertEqual(current, 0)
        self.assertGreater(self.conn.execute("SELECT COUNT(*) FROM fr_groups").fetchone()[0], 5)

    def test_bulk_files_are_not_archived(self):
        client = FakeClient()
        full_run(store(), client)
        self.assertTrue(client.asked)
        self.assertTrue(all(archive is False for _url, archive in client.asked))


class ResumeAndReclassifyTests(unittest.TestCase):
    def test_a_second_run_skips_old_scrutins_and_refreshes_recent_ones(self):
        conn = store()
        full_run(conn)
        client = FakeClient()
        dossiers, _r, _o = frr.pull_dossiers(conn, client, TODAY, tax=TAX, wl=WL)
        stored, _ours, gaps = frr.pull_scrutins(conn, client, TODAY, dossiers, tax=TAX, wl=WL,
                                                log=lambda *a: None)
        # Only scrutins of the last 30 days are re-read; all seven are older.
        self.assertEqual((stored, gaps), (0, 0))
        stored, _ours, _g = frr.pull_scrutins(conn, client, "2026-07-20", dossiers, tax=TAX,
                                              wl=WL, log=lambda *a: None)
        self.assertEqual(stored, 2)  # 15 July (8280) and 6 July (7979)

    def test_reclassify_rederives_dossiers_then_divisions(self):
        conn = store()
        full_run(conn)
        conn.execute("UPDATE fr_dossiers SET areas='[]'")
        conn.execute("UPDATE fr_divisions SET areas='[]'")
        changed_d, changed_v = frr.reclassify(conn, tax=TAX, log=lambda *a: None)
        self.assertGreaterEqual(changed_d, 1)
        self.assertEqual(json.loads(division(conn, 2091)["areas"]), [2])
        self.assertGreaterEqual(changed_v, 3)

    def test_a_missing_dossiers_zip_is_a_gap_and_nothing_is_joined_wrongly(self):
        conn = store()
        client = FakeClient(missing=[frr.DOSSIERS.format(17)])
        with self.assertRaises(FetchError):
            frr.pull_dossiers(conn, client, TODAY, tax=TAX, wl=WL)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM fr_divisions").fetchone()[0], 0)


class TaxonomyChoiceTests(unittest.TestCase):
    def test_quebec_until_a_france_list_exists(self):
        expected = frr.TAXONOMY_FR if os.path.exists(frr.TAXONOMY_FR) else frr.TAXONOMY_QC
        self.assertEqual(frr.taxonomy_path(), expected)

    def test_false_friends_are_masked(self):
        self.assertNotIn("censure", frr.mask("la motion de censure déposée par M. X"))
        self.assertIn("censure", frr.mask("la censure des réseaux sociaux"))
        self.assertNotIn("euthanasie", frr.mask("interdire l'euthanasie des animaux saisis"))


class WatchlistTests(unittest.TestCase):
    def test_every_watchlist_key_is_a_dossier_uid(self):
        import re
        wl = fr_store.watchlist()
        self.assertTrue(wl)
        for key, (areas, why) in wl.items():
            self.assertRegex(key, r"^DLR5L1[0-9]N\d+$")
            self.assertTrue(areas and all(1 <= a <= 13 for a in areas), key)
            self.assertTrue(why and len(why) > 30, key)
            self.assertFalse(re.search("\\u2014", why), "no em dashes: " + key)

    def test_the_tables_are_declared(self):
        for t in fr_store.TABLES:
            self.assertIn(t, db.TABLES)


if __name__ == "__main__":
    unittest.main()
