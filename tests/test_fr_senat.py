"""FR5 (Chris, 10 October 2026): the French Senat from data.senat.fr
(tools/fr_senat.py, the fr_* tables with chamber 'senat', the France
edition). No network: senat_dosleg_trim.zip is the Dosleg dump of 10 October
2026 cut to four scrutins, twelve senators and the two end-of-life dossiers,
row for row (the broken Windows-1252 apostrophes included); the two ODSEN
files are cut to the same twelve senators."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, fr_store  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "fr")
TODAY = "2026-10-10"


def _load():
    spec = importlib.util.spec_from_file_location(
        "fr_senat", os.path.join(ROOT, "tools", "fr_senat.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


frs = _load()
QUIET = dict(log=lambda *_: None)


def fixture_bytes(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def fixture_json(name):
    return json.loads(fixture_bytes(name).decode("utf-8"))


TABLES = frs.read_tables(frs.dump_lines(fixture_bytes("senat_dosleg_trim.zip")))
GENERAL = fixture_json("senat_odsen_general.json")
SPELLS = fixture_json("senat_odsen_histogroupes.json")


def store(with_an=True):
    conn = db.init_db(sqlite3.connect(":memory:"))
    if with_an:
        # The Assemblee's aide a mourir dossier, as tools/fr_rollcalls.py stores it.
        conn.execute("INSERT INTO fr_dossiers (dossier_ref, legislature, title, an_path, areas) "
                     "VALUES ('DLR5L17N51670', 17, 'Fin de vie', 'fin_de_vie_17e', '[2]')")
    return conn


def loaded(with_an=True):
    conn = store(with_an)
    result = frs.load(conn, TABLES, GENERAL, SPELLS, TODAY, **QUIET)
    return conn, result


class DumpTests(unittest.TestCase):
    def test_the_copy_blocks_are_read(self):
        self.assertEqual(len(TABLES["scr"][1]), 4)
        self.assertEqual(len(TABLES["votsen"][1]), 48)
        self.assertIsNone(TABLES["scr"][1][0]["soslib"])     # '\\N' is NULL

    def test_copy_escapes(self):
        self.assertEqual(frs.unescape_copy("a\\tb\\\\c"), "a\tb\\c")
        self.assertIsNone(frs.unescape_copy("\\N"))

    def test_the_broken_apostrophes_are_repaired(self):
        raw = [r["scrint"] for r in TABLES["scr"][1]]
        self.assertTrue(any("\x92" in t for t in raw))
        fixed = [frs.fix_c1(t) for t in raw]
        self.assertFalse(any("\x92" in t for t in fixed))
        self.assertTrue(any(t.startswith("sur l'ensemble") for t in fixed))
        self.assertEqual(frs.fix_c1("c\x9cur \x96 l\x92ensemble"), "cœur – l'ensemble")


class DueTests(unittest.TestCase):
    REMOTE = ("Fri, 09 Oct 2026 01:47:35 GMT", '"4802-f47389"', 16020361)

    def test_never_downloaded(self):
        self.assertTrue(frs.due(store(False), TODAY, self.REMOTE)[0])

    def test_unchanged_is_not_downloaded(self):
        conn = store(False)
        frs.record_download(conn, "2026-09-01", self.REMOTE)
        self.assertEqual(frs.due(conn, TODAY, self.REMOTE), (False, "unchanged since 2026-09-01"))

    def test_changed_but_read_this_week_waits(self):
        conn = store(False)
        frs.record_download(conn, "2026-10-08", self.REMOTE)
        later = ("Sat, 10 Oct 2026 01:47:35 GMT", '"x"', 16020999)
        ok, why = frs.due(conn, TODAY, later)
        self.assertFalse(ok)
        self.assertIn("2 day(s) ago", why)

    def test_changed_and_a_week_old_is_due(self):
        conn = store(False)
        frs.record_download(conn, "2026-10-03", self.REMOTE)
        self.assertTrue(frs.due(conn, TODAY, ("Sat, 10 Oct 2026", '"x"', 1))[0])

    def test_the_headers_come_from_a_one_byte_request(self):
        class Client:
            last_headers = {"Last-Modified": "Fri, 09 Oct 2026 01:47:35 GMT",
                            "ETag": '"4802-f47389"', "Content-Range": "bytes 0-0/16020361"}

            def get_bytes(self, url, feed, slug, first_bytes=None, **kw):
                assert first_bytes == 1
                return b"P"
        self.assertEqual(frs.remote_state(Client()), self.REMOTE[:1] + ('"4802-f47389"', 16020361))


class LoadTests(unittest.TestCase):
    def test_scrutins_are_joined_to_the_assemblees_dossier(self):
        conn, (dossiers, scrutins, ours, gaps) = loaded()
        self.assertEqual((dossiers, scrutins, gaps), (2, 4, 0))
        got = {k: (ref, via) for k, ref, via in conn.execute(
            "SELECT division_key, dossier_ref, dossier_via FROM fr_divisions WHERE chamber='senat'")}
        # The Senate names the law by its title; its url_an names the
        # Assemblee's path slug, which fr_dossiers.an_path carries.
        self.assertEqual(got["senat-2025-169"], ("DLR5L17N51670", "title"))
        self.assertEqual(got["senat-2025-148"], ("DLR5L17N51670", "title"))
        self.assertEqual(got["senat-2025-170"], ("SEN-ppl24-662", "title"))
        self.assertEqual(got["senat-2025-317"], (None, None))
        sen = dict(conn.execute("SELECT dossier_ref, an_dossier_ref FROM fr_senat_dossiers"))
        self.assertEqual(sen, {"SEN-ppl24-661": "DLR5L17N51670", "SEN-ppl24-662": None})

    def test_the_final_vote_record(self):
        conn, _ = loaded()
        row = conn.execute("SELECT legislature, number, date, result, pour, contre, title, areas "
                           "FROM fr_divisions WHERE division_key='senat-2025-169'").fetchone()
        self.assertEqual(row[:6], (2025, 169, "2026-01-28", None, 122, 181))
        self.assertEqual(row[6], "sur l'ensemble de la proposition de loi relative au droit "
                                 "à l'aide à mourir")
        self.assertIn(2, json.loads(row[7]))

    def test_positions_with_the_group_at_the_vote(self):
        conn, _ = loaded()
        rows = conn.execute("SELECT acteur_ref, position, group_ref FROM fr_votes "
                            "WHERE division_key='senat-2025-169'").fetchall()
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(g and g.startswith("senat:") for _a, _p, g in rows))
        self.assertTrue({p for _a, p, _g in rows} <= {"pour", "contre", "abstention",
                                                      "nonVotant"})
        members = conn.execute("SELECT COUNT(*) FROM fr_members WHERE chamber='senat'").fetchone()
        self.assertEqual(members[0], 12)

    def test_groups_carry_the_name_in_use(self):
        conn, _ = loaded()
        groups = dict(conn.execute("SELECT organe_ref, abbr FROM fr_groups WHERE chamber='senat'"))
        if "senat:UMP" in groups:
            self.assertEqual(groups["senat:UMP"], "Les Républicains")

    def test_reload_and_reclassify_are_idempotent(self):
        conn, _ = loaded()
        before = conn.execute("SELECT COUNT(*) FROM fr_votes").fetchone()[0]
        frs.load(conn, TABLES, GENERAL, SPELLS, TODAY, **QUIET)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM fr_votes").fetchone()[0], before)
        self.assertEqual(frs.reclassify(conn, **QUIET), 0)

    def test_the_assemblees_reclassify_keeps_senate_dossier_areas(self):
        conn, _ = loaded()
        conn.execute("UPDATE fr_senat_dossiers SET areas='[2]' WHERE dossier_ref='SEN-ppl24-662'")
        frr = frs.frr
        frr.reclassify(conn, **QUIET)
        areas = json.loads(conn.execute("SELECT areas FROM fr_divisions WHERE "
                                        "division_key='senat-2025-170'").fetchone()[0])
        self.assertIn(2, areas)
        self.assertEqual(fr_store.senat_dossier_areas(conn, "SEN-nope"), [])


class EditionTests(unittest.TestCase):
    def test_senate_votes_render_as_the_senates(self):
        conn, _ = loaded()
        conn.row_factory = sqlite3.Row
        from src.editions import fr
        items = {it["key"]: it for it in fr._votes(conn, "2026-01-01", "2026-02-01",
                                                   {"DLR5L17N51670": {}})}
        final = items["senat-2025-169"]
        self.assertEqual(final["url"], "https://www.senat.fr/scrutin-public/2025/scr2025-169.html")
        self.assertTrue(final["takeaway"].startswith("Sénat, scrutin 169 of the 2025-2026 session"))
        self.assertIn("absolute majority of votes cast: 152", final["lines"][0])
        self.assertNotIn("result as recorded", final["lines"][0])
        self.assertTrue(final["final"])
        self.assertTrue(final["watched"])
        self.assertEqual(final["group"], "DLR5L17N51670")

    def test_a_senate_only_dossier_in_the_week_ahead(self):
        conn, _ = loaded()
        conn.execute("UPDATE fr_senat_dossiers SET areas='[2]', last_sitting='2026-10-14' "
                     "WHERE dossier_ref='SEN-ppl24-662'")
        conn.row_factory = sqlite3.Row
        from src.editions import fr
        ahead = [it for it in fr.week_ahead(conn, TODAY, {}) if it["key"] == "SEN-ppl24-662"]
        self.assertEqual(len(ahead), 1)
        self.assertIn("sitting scheduled on 14 October 2026", ahead[0]["takeaway"])


class SchemaTests(unittest.TestCase):
    def test_tables_declared(self):
        for t in ("fr_senat_dossiers", "fr_senat_dump"):
            self.assertIn(t, fr_store.TABLES)
            self.assertIn(t, db.TABLES)

    def test_the_job_runs_it_after_the_assemblee(self):
        with open(os.path.join(ROOT, "jobs", "fr-weekly.sh"), encoding="utf-8") as fh:
            job = fh.read()
        self.assertLess(job.index("python3 tools/fr_rollcalls.py || rc=$?"),
                        job.index("python3 tools/fr_senat.py || sr=$?"))
        self.assertLess(job.index("python3 tools/fr_senat.py || sr=$?"),
                        job.rindex("tools/fr_monitor.py"))


if __name__ == "__main__":
    unittest.main()
