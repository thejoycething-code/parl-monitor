"""Portugal: deputies, initiatives and votes of the Assembleia da Republica
(tools/pt_rollcalls.py). No network: the fixtures are trimmed real files,
saved from parlamento.pt on 9 October 2026 (tests/fixtures/pt/)."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, pt_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "pt")


def _load():
    spec = importlib.util.spec_from_file_location(
        "pt_rollcalls", os.path.join(ROOT, "tools", "pt_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ptr = _load()
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = ptr.empty_watchlist()


def fixture(name, parse=True):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh) if parse else fh.read()


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def record(itype, nr):
    return next(r for r in fixture("iniciativas_xvii_sample.json")
                if r["IniTipo"] == itype and r["IniNr"] == nr)


class DetailTests(unittest.TestCase):
    def test_whole_groups(self):
        groups, people = ptr.parse_detail(
            "A Favor: <I>PSD</I>, <I> CDS-PP</I><BR>Contra:<I>CH</I>, <I> IL</I>"
            "<BR>Abstenção:<I>PS</I>")
        self.assertEqual(groups, [("PSD", "A Favor", None), ("CDS-PP", "A Favor", None),
                                  ("CH", "Contra", None), ("IL", "Contra", None),
                                  ("PS", "Abstenção", None)])
        self.assertEqual(people, [])

    def test_breakaway_block_and_named_deputies(self):
        # Projeto de Resolucao 6/XVII (Palestine): PS abstained, thirteen of
        # its deputies voted for, and the record names them.
        groups, people = ptr.parse_detail(
            "A Favor: <I>13-PS</I>, <I> L</I>, <I> Pedro Nuno Santos (PS)</I>, "
            "<I> Edite Estrela (PS)</I><BR>Contra:<I>PSD</I><BR>Abstenção:<I>PS</I>")
        self.assertIn(("PS", "A Favor", 13), groups)
        self.assertIn(("PS", "Abstenção", None), groups)
        self.assertEqual(people, [("Pedro Nuno Santos", "PS", "A Favor"),
                                  ("Edite Estrela", "PS", "A Favor")])

    def test_absence_label(self):
        groups, _ = ptr.parse_detail("A Favor: <I>PSD</I><BR>Ausência: <I>PAN</I>")
        self.assertIn(("PAN", "Ausente", None), groups)

    def test_empty_detail_is_unanimous_or_unrecorded(self):
        self.assertEqual(ptr.parse_detail(None), ([], []))
        self.assertEqual(ptr.parse_detail(""), ([], []))


class InitiativeTests(unittest.TestCase):
    def test_key_is_legislature_type_number(self):
        ini = ptr.parse_initiative(record("J", "479"))
        self.assertEqual(ini["key"], "XVII/J/479")
        self.assertEqual(ini["type_desc"], "Projeto de Lei")
        self.assertIn("bloqueadores da puberdade", ini["title"])
        self.assertEqual(ini["authors_gp"], ["CDS-PP"])

    def test_generality_vote_and_group_positions(self):
        ini = ptr.parse_initiative(record("J", "479"))
        gen = [d for d in ini["divisions"] if d["phase"] == "Votação na generalidade"]
        self.assertEqual(len(gen), 1)
        d = gen[0]
        self.assertEqual((d["date"], d["result"]), ("2026-03-20", "Aprovado"))
        self.assertIn(("PSD", "A Favor", None), d["groups"])
        self.assertIn(("PS", "Contra", None), d["groups"])

    def test_law_and_vetoes_are_read_from_the_phases(self):
        burqa = ptr.parse_initiative(record("J", "47"))
        self.assertEqual(burqa["latest_phase"], "Lei (Publicação DR)")
        self.assertTrue(burqa["law_published"])
        self.assertEqual(burqa["vetoes"], 0)
        nationality = ptr.parse_initiative(record("P", "1"))
        self.assertEqual(nationality["vetoes"], 3)

    def test_vote_ids_are_unique_keys(self):
        keys = [d["key"] for r in fixture("iniciativas_xvii_sample.json")
                for d in ptr.parse_initiative(r)["divisions"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(k.startswith("XVII/") for k in keys))


class DiscoveryTests(unittest.TestCase):
    def test_folder_link_finds_the_exact_legislature(self):
        page = fixture("page_iniciativas.html", parse=False)
        xvii = ptr.folder_link(page, "XVII")
        xvi = ptr.folder_link(page, "XVI")
        self.assertTrue(xvii.startswith("https://www.parlamento.pt/Cidadania/Paginas/DAIniciativas.aspx"))
        self.assertNotEqual(xvii, xvi)
        self.assertIsNone(ptr.folder_link(page, "XXX"))

    def test_json_link_matches_the_whole_filename(self):
        xvii = fixture("folder_iniciativas_xvii.html", parse=False)
        xvi = fixture("folder_iniciativas_xvi.html", parse=False)
        url = ptr.json_link(xvii, "Iniciativas", "XVII")
        self.assertIn("fich=IniciativasXVII_json.txt", url)
        self.assertNotIn("&amp;", url)
        # 'IniciativasXVI' is a prefix of 'IniciativasXVII': never confuse them.
        self.assertIsNone(ptr.json_link(xvii, "Iniciativas", "XVI"))
        self.assertIsNone(ptr.json_link(xvi, "Iniciativas", "XVII"))
        self.assertIn("fich=IniciativasXVI_json.txt", ptr.json_link(xvi, "Iniciativas", "XVI"))

    def test_fetch_dataset_walks_page_folder_file(self):
        page = fixture("page_iniciativas.html", parse=False)
        folder = fixture("folder_iniciativas_xvii.html", parse=False)
        body = json.dumps([record("J", "479")]).encode("utf-8")
        seen = []

        class Client:
            def get_text(self, url, feed, slug, archive=True, **kw):
                seen.append(slug)
                return page if "page-" in slug else folder

            def get_bytes(self, url, feed, slug, **kw):
                seen.append(slug)
                assert "IniciativasXVII_json.txt" in url
                return body

        data = ptr.fetch_dataset(Client(), "initiatives", "XVII")
        self.assertEqual(data[0]["IniNr"], "479")
        self.assertEqual(seen, ["page-initiatives", "folder-initiatives-XVII", "initiatives-XVII"])

    def test_fetch_dataset_says_what_moved(self):
        class Client:
            def get_text(self, url, feed, slug, archive=True, **kw):
                return "<html>nothing here</html>"

        with self.assertRaises(ValueError):
            ptr.fetch_dataset(Client(), "initiatives", "XVII")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        ptr.store_members(self.conn, ptr.parse_members(fixture("informacaobase_xvii_sample.json")),
                          "2026-10-09")
        self.counts = ptr.store_records(self.conn, fixture("iniciativas_xvii_sample.json"),
                                        "2026-10-09", tax=TAX, wl=WL, log=lambda *_: None)

    def q(self, sql, *args):
        return self.conn.execute(sql, args).fetchall()

    def test_tables_are_declared(self):
        for t in pt_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_watchlist_lends_areas_by_key_and_votes_inherit(self):
        (areas, terms), = self.q("SELECT areas, matched_terms FROM pt_initiatives "
                                 "WHERE ini_key='XVII/J/479'")
        self.assertEqual(json.loads(areas), [3])
        self.assertIn("watch:XVII/J/479", json.loads(terms))
        rows = self.q("SELECT areas FROM pt_divisions WHERE ini_key='XVII/J/479'")
        self.assertTrue(rows)
        self.assertTrue(all(json.loads(a) == [3] for (a,) in rows))

    def test_english_taxonomy_is_blind_to_portuguese(self):
        # Projeto de Resolucao 1202/XVII is about abortion ('interrupcao
        # voluntaria da gravidez') and is on the watchlist; strip the
        # watchlist and the English list sees nothing.
        ini = ptr.parse_initiative(record("R", "1202"))
        res = filt.filter_item(TAX, WL, ini["title"])
        self.assertEqual(res.issue_areas or [], [])

    def test_breakaway_block_and_named_deputy_are_stored(self):
        # Proposta de Lei 72/XVII: PS abstained, one PS deputy voted against,
        # named as 'Pedro Vaz (PS)'.
        (key,) = self.q("SELECT d.division_key FROM pt_divisions d WHERE d.ini_key='XVII/P/72' "
                        "AND d.phase='Votação na generalidade'")[0]
        groups = set(self.q("SELECT party, position, members FROM pt_group_votes "
                            "WHERE division_key=?", key))
        self.assertIn(("PS", "Abstenção", None), groups)
        self.assertIn(("PS", "Contra", 1), groups)
        (name, party, position, cad), = self.q(
            "SELECT name, party, position, cad_id FROM pt_votes WHERE division_key=?", key)
        self.assertEqual((name, party, position), ("Pedro Vaz", "PS", "Contra"))
        self.assertIsNotNone(cad)

    def test_absent_groups_are_stored(self):
        rows = self.q("SELECT absent_groups FROM pt_divisions WHERE absent_groups != '[]'")
        self.assertTrue(rows)
        n = self.q("SELECT COUNT(*) FROM pt_group_votes WHERE position='Ausente'")[0][0]
        self.assertGreater(n, 0)

    def test_rerun_replaces_rather_than_duplicates(self):
        before = self.q("SELECT COUNT(*) FROM pt_group_votes")[0][0]
        named = self.q("SELECT COUNT(*) FROM pt_votes")[0][0]
        ptr.store_records(self.conn, fixture("iniciativas_xvii_sample.json"), "2026-10-16",
                          tax=TAX, wl=WL, log=lambda *_: None)
        self.assertEqual(self.q("SELECT COUNT(*) FROM pt_group_votes")[0][0], before)
        self.assertEqual(self.q("SELECT COUNT(*) FROM pt_votes")[0][0], named)
        (first, last), = self.q("SELECT first_seen, last_seen FROM pt_initiatives "
                                "WHERE ini_key='XVII/J/479'")
        self.assertEqual((first, last), ("2026-10-09", "2026-10-16"))

    def test_reclassify_is_offline_and_stable(self):
        changed = ptr.reclassify(self.conn, tax=TAX, log=lambda *_: None)
        self.assertEqual(changed, (0, 0))

    def test_counts(self):
        n, ours, nd, ours_d, unresolved = self.counts
        self.assertEqual(n, 7)
        self.assertGreater(nd, n)
        self.assertEqual(unresolved, 0)


class MemberTests(unittest.TestCase):
    def test_latest_group_and_situation(self):
        members = {m["name"]: m for m in ptr.parse_members(fixture("informacaobase_xvii_sample.json"))}
        self.assertEqual(members["André Ventura"]["party"], "CH")
        self.assertTrue(all(m["cad_id"] for m in members.values()))

    def test_resolver_never_guesses(self):
        conn = store()
        conn.executemany("INSERT INTO pt_members (cad_id, name, party) VALUES (?,?,?)",
                         [(1, "Ana Silva", "PS"), (2, "Ana Silva", "PSD"), (3, "Rui Sá", "PCP"),
                          (4, "João Dias", "PS"), (5, "João Dias", "PS")])
        r = ptr.Resolver(conn)
        self.assertEqual(r.get("Rui Sá", "PCP"), 3)
        self.assertEqual(r.get("Ana Silva", "PSD"), 2)
        self.assertIsNone(r.get("João Dias", "PS"))
        self.assertIsNone(r.get("Ninguém", "PS"))


class WatchlistTests(unittest.TestCase):
    def test_keys_and_areas_are_well_formed(self):
        with open(os.path.join(ROOT, "config", "watchlist-pt.yaml"), encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        import re
        for key, spec in raw["initiatives"].items():
            self.assertRegex(key, r"^[XVI]+/[JPRDSAIC]/\d+$")
            self.assertTrue(spec.get("why"))
            self.assertTrue(set(spec["areas"]) <= set(range(1, 14)), key)
            self.assertNotIn(11, spec["areas"], key)
        self.assertTrue(re)

    def test_taxonomy_falls_back_to_english_until_approved(self):
        if not os.path.exists(ptr.TAXONOMY_PT):
            self.assertEqual(ptr.taxonomy_path(), ptr.TAXONOMY_EN)


class GapTests(unittest.TestCase):
    def test_fetch_error_propagates_for_the_caller_to_record(self):
        class Client:
            def get_text(self, url, feed, slug, archive=True, **kw):
                raise FetchError(url, feed, slug, 4, OSError("reset"))

        with self.assertRaises(FetchError):
            ptr.fetch_dataset(Client(), "members", "XVII")


class DerivedPositionsTests(unittest.TestCase):
    """X5 (Chris, 10 October 2026): named deputies are facts, the rest of a
    whole-group row is derived and labelled so; counted blocks are never spread."""

    def test_named_breakaway_is_fact_and_the_group_is_derived(self):
        conn = sqlite3.connect(":memory:")
        pt_store.ensure_schema(conn)
        conn.execute("INSERT INTO pt_members (cad_id, name, party, situation) VALUES "
                     "(1, 'Ana', 'PS', 'Efetivo'), (2, 'Rui', 'PS', 'Efetivo'), (3, 'Eva', 'PSD', 'Efetivo')")
        conn.execute("INSERT INTO pt_group_votes VALUES ('v', 'PS', 'Abstencao', NULL), "
                     "('v', 'PS', 'A Favor', 1), ('v', 'PSD', 'Contra', 60)")
        conn.execute("INSERT INTO pt_votes VALUES ('v', 'Ana', 'PS', 'A Favor', 1)")
        rows = {r["member_id"]: r for r in pt_store.derived_member_positions(conn, "v")}
        self.assertEqual((rows[1]["position"], rows[1]["derived"]), ("A Favor", False))
        self.assertEqual((rows[2]["position"], rows[2]["derived"]), ("Abstencao", True))
        self.assertNotIn(3, rows)          # a counted block is not spread


if __name__ == "__main__":
    unittest.main()
