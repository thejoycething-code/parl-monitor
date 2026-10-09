"""Brazil, National Congress: nominal votes, positions, proposições and
members (tools/br_rollcalls.py). No network: the fixtures under
tests/fixtures/br/ are real responses of 9 October 2026, trimmed."""

import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import br_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "br")


def _load():
    spec = importlib.util.spec_from_file_location(
        "br_rollcalls", os.path.join(ROOT, "tools", "br_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


brr = _load()
TODAY = "2026-10-09"


def fx(name):
    with open(os.path.join(FX, name), encoding="utf-8") as fh:
        return json.load(fh)


def camara_pages(year=2026):
    pages = {
        brr.CAMARA_BULK.format("votacoes", year): fx("camara_votacoes-2026.json"),
        brr.CAMARA_BULK.format("votacoesProposicoes", year): fx("camara_votacoesProposicoes-2026.json"),
        brr.CAMARA_BULK.format("votacoesOrientacoes", year): fx("camara_votacoesOrientacoes-2026.json"),
        brr.CAMARA_API + "/deputados?itens=1000": fx("camara_deputados.json"),
        brr.SENADO + "/senador/lista/atual.json": fx("senado_senadores_atual.json"),
        brr.SENADO + "/votacao?dataInicio=2026-01-01&dataFim=2026-10-09": fx("senado_votacao-2026.json"),
    }
    for vid in ("2611313-31", "2611313-34", "2334926-27", "2636281-8"):
        pages["{0}/votacoes/{1}/votos".format(brr.CAMARA_API, vid)] = fx(
            "camara_votos_{0}.json".format(vid))
    for pid in (2334926, 2611313, 2612930):
        pages["{0}/proposicoes/{1}".format(brr.CAMARA_API, pid)] = fx(
            "camara_proposicao_{0}.json".format(pid))
    return pages


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.asked = []

    def get_json(self, url, feed, slug, archive=True, **kw):
        self.asked.append(url)
        page = self.pages.get(url)
        if isinstance(page, Exception):
            raise page
        if page is None:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return page


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def quiet(*_a, **_k):
    pass


class KeyTests(unittest.TestCase):
    def test_bill_key_is_type_number_year(self):
        self.assertEqual(brr.bill_key("PL", 1904, 2024), "PL 1904/2024")
        self.assertEqual(brr.bill_key("pec", "164", "2012"), "PEC 164/2012")

    def test_a_pre_2019_senate_bill_cannot_take_a_camara_key(self):
        # The houses numbered separately before 2019: PEC 164/2012 in the
        # Senate is not the Câmara's PEC 164/2012.
        self.assertEqual(brr.bill_key("PEC", 5, 2017, chamber="senado"), "SF PEC 5/2017")
        self.assertEqual(brr.bill_key("PLP", 124, 2022, chamber="senado"), "PLP 124/2022")

    def test_a_record_with_no_number_or_year_is_keyed_on_its_id(self):
        self.assertEqual(brr.bill_key("PRL", 1, 0, camara_id=2645880), "camara:2645880")
        self.assertIsNone(brr.bill_key("PRL", 1, 0))

    def test_years_to_read_backfills_once_then_reads_the_current_year(self):
        conn = store()
        self.assertEqual(brr.years_to_read(conn, "2026-10-09"), [2023, 2024, 2025, 2026])
        for y in (2023, 2024, 2025):
            conn.execute("INSERT INTO br_divisions (division_key, chamber, source_id, date) "
                         "VALUES (?, 'camara', ?, ?)", ("camara-x" + str(y), str(y), "%d-05-01" % y))
        self.assertEqual(brr.years_to_read(conn, "2026-10-09"), [2026])
        # January and February re-read the year just ended: late records land.
        self.assertEqual(brr.years_to_read(conn, "2026-02-10"), [2025, 2026])
        self.assertEqual(brr.years_to_read(conn, "2026-10-09", from_year=2026), [2026])


class CamaraParsingTests(unittest.TestCase):
    def test_only_nominal_votes_become_divisions(self):
        got = {d["source_id"]: d for d in brr.parse_camara_votacoes(fx("camara_votacoes-2026.json"))}
        # 2611313-34 is the symbolic approval of the final wording: 0/0/0.
        self.assertEqual(sorted(got), ["2334926-27", "2611313-31", "2636281-8"])
        d = got["2611313-31"]
        self.assertEqual((d["yes"], d["no"], d["other"], d["organ"], d["result"]),
                         (346, 46, 4, "PLEN", "approved"))
        self.assertEqual(got["2334926-27"]["organ"], "CCJC")
        self.assertEqual(got["2334926-27"]["result"], "rejected")

    def test_the_bill_a_vote_is_about_is_the_bill_not_the_urgency_request(self):
        links = brr.parse_camara_links(fx("camara_votacoesProposicoes-2026.json"))
        linked = links["2636281-8"]
        self.assertEqual(sorted(b["bill_key"] for b in linked), ["PL 896/2023", "REQ 3690/2026"])
        self.assertEqual(brr.main_bill(linked)["bill_key"], "PL 896/2023")
        self.assertIsNone(brr.main_bill([b for b in linked if b["sigla"] == "REQ"]))

    def test_positions_carry_party_and_state_at_the_vote(self):
        pos = brr.parse_camara_votos(fx("camara_votos_2611313-31.json"))
        self.assertEqual(len(pos), 4)
        self.assertTrue(all(re.match(r"^camara-\d+$", p["member_key"]) for p in pos))
        self.assertTrue(all(p["party"] and p["uf"] for p in pos))
        self.assertEqual(brr.parse_camara_votos(fx("camara_votos_2611313-34.json")), [])

    def test_blank_orientations_are_dropped(self):
        rows = fx("camara_votacoesOrientacoes-2026.json")["dados"]
        got = brr.parse_camara_orientations(fx("camara_votacoesOrientacoes-2026.json"))
        kept = sum(len(v) for v in got.values())
        self.assertEqual(kept, sum(1 for r in rows if (r.get("orientacao") or "").strip()))
        self.assertTrue(all(o for v in got.values() for _b, o in v))

    def test_proposicao_detail_carries_keywords_and_status(self):
        b = brr.parse_camara_proposicao(fx("camara_proposicao_2334926.json"))
        self.assertEqual(b["bill_key"], "PL 2410/2022")
        self.assertEqual(b["status"], "Pronta para Pauta")
        self.assertEqual(b["camara_id"], 2334926)


class SenadoParsingTests(unittest.TestCase):
    def test_votes_parse_with_counted_totals_and_bill(self):
        got = brr.parse_senado_votacoes(fx("senado_votacao-2026.json"))
        self.assertEqual(len(got), 5)
        d = got[0]
        self.assertEqual(d["source_id"], "7101")
        self.assertEqual(d["bill"]["bill_key"], "PLP 124/2022")
        self.assertEqual(d["yes"] + d["no"] + d["other"], len(d["positions"]))
        self.assertTrue(all(p["member_key"].startswith("senado-") for p in d["positions"]))

    def test_a_secret_ballot_is_flagged(self):
        got = {d["source_id"]: d for d in brr.parse_senado_votacoes(fx("senado_votacao-2026.json"))}
        self.assertEqual(got["7104"]["secret"], 1)
        self.assertEqual(got["7101"]["secret"], 0)

    def test_senators_in_office(self):
        got = brr.parse_senadores(fx("senado_senadores_atual.json"))
        self.assertEqual(len(got), 3)
        self.assertEqual(got[0]["member_key"], "senado-5672")


class PullTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.client = FakeClient(camara_pages())
        self.gaps = brr.run(self.conn, self.client, TODAY, [2026], log=quiet)

    def test_a_full_run_stores_both_houses_with_no_gaps(self):
        self.assertEqual(self.gaps, 0)
        n = lambda sql: self.conn.execute(sql).fetchone()[0]  # noqa: E731
        self.assertEqual(n("SELECT COUNT(*) FROM br_divisions WHERE chamber='camara'"), 3)
        self.assertEqual(n("SELECT COUNT(*) FROM br_divisions WHERE chamber='senado'"), 5)
        self.assertEqual(n("SELECT COUNT(*) FROM br_divisions WHERE positions_fetched=0"), 0)
        self.assertEqual(n("SELECT COUNT(*) FROM br_votes WHERE division_key LIKE 'camara-%'"), 12)
        self.assertGreater(n("SELECT COUNT(*) FROM br_orientations"), 0)
        self.assertEqual(n("SELECT COUNT(*) FROM br_members WHERE in_office=1"), 6)

    def test_the_symbolic_vote_costs_no_request(self):
        self.assertFalse(any("2611313-34" in u for u in self.client.asked))

    def test_divisions_point_at_the_bill_and_keep_every_link(self):
        bkey, linked = self.conn.execute(
            "SELECT bill_key, linked_bills FROM br_divisions WHERE division_key='camara-2636281-8'"
        ).fetchone()
        self.assertEqual(bkey, "PL 896/2023")
        self.assertEqual(sorted(json.loads(linked)), ["PL 896/2023", "REQ 3690/2026"])

    def test_a_second_run_fetches_no_position_again(self):
        before = len(self.client.asked)
        self.assertEqual(brr.run(self.conn, self.client, TODAY, [2026], log=quiet), 0)
        again = self.client.asked[before:]
        self.assertFalse(any("/votos" in u for u in again))
        self.assertFalse(any("/proposicoes/" in u for u in again))

    def test_party_is_kept_per_vote(self):
        rows = self.conn.execute("SELECT party FROM br_votes WHERE party IS NULL").fetchall()
        self.assertEqual(rows, [])


class GapTests(unittest.TestCase):
    def test_a_refused_year_file_is_a_gap_and_the_senate_still_runs(self):
        pages = camara_pages()
        pages[brr.CAMARA_BULK.format("votacoes", 2026)] = FetchError("u", "f", "s", 4, "HTTP 503")
        conn = store()
        gaps = brr.run(conn, FakeClient(pages), TODAY, [2026], log=quiet)
        self.assertEqual(gaps, 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM br_divisions WHERE chamber='senado'")
                         .fetchone()[0], 5)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='br-rollcalls'")
                         .fetchone()[0], 1)

    def test_a_failed_position_fetch_is_retried_next_run(self):
        pages = camara_pages()
        url = "{0}/votacoes/2611313-31/votos".format(brr.CAMARA_API)
        good = pages[url]
        pages[url] = FetchError(url, "f", "s", 4, "timed out")
        conn = store()
        client = FakeClient(pages)
        self.assertEqual(brr.run(conn, client, TODAY, [2026], log=quiet), 1)
        self.assertEqual(conn.execute("SELECT positions_fetched FROM br_divisions WHERE "
                                      "division_key='camara-2611313-31'").fetchone()[0], 0)
        pages[url] = good
        self.assertEqual(brr.run(conn, client, TODAY, [2026], log=quiet), 0)
        self.assertEqual(conn.execute("SELECT positions_fetched FROM br_divisions WHERE "
                                      "division_key='camara-2611313-31'").fetchone()[0], 1)

    def test_the_budget_stops_the_position_drain_and_says_so(self):
        class Spent:
            def exhausted(self):
                return True

            def disclose(self, what, done):
                return "budget: " + what

        conn = store()
        lines = []
        brr.run(conn, FakeClient(camara_pages()), TODAY, [2026], budget=Spent(), log=lines.append)
        self.assertTrue(any("budget: Câmara vote positions" in l for l in lines))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM br_divisions WHERE chamber='camara' "
                                      "AND positions_fetched=0").fetchone()[0], 3)


class RenumberTests(unittest.TestCase):
    def test_a_bill_seen_under_a_new_number_moves_with_its_divisions(self):
        # PL 3179/2012 became PL 1338/2022 on reaching the Senate; the Câmara
        # ID (534328) stayed.
        conn = store()
        old = {"bill_key": "PL 3179/2012", "camara_id": 534328, "sigla": "PL",
               "numero": 3179, "ano": 2012, "ementa": "educação domiciliar"}
        brr.store_bill(conn, old, TODAY, log=quiet)
        brr.store_division(conn, {"chamber": "camara", "source_id": "534328-1", "date": "2022-05-18",
                                  "organ": "PLEN", "description": "x", "result": "approved",
                                  "yes": 264, "no": 144, "other": 2, "secret": 0},
                           TODAY, bill=old, linked=[old])
        new = dict(old, bill_key="PL 1338/2022", numero=1338, ano=2022)
        lines = []
        brr.store_bill(conn, new, TODAY, log=lines.append)
        self.assertEqual([r[0] for r in conn.execute("SELECT bill_key FROM br_bills")],
                         ["PL 1338/2022"])
        bkey, linked = conn.execute("SELECT bill_key, linked_bills FROM br_divisions").fetchone()
        self.assertEqual((bkey, json.loads(linked)), ("PL 1338/2022", ["PL 1338/2022"]))
        self.assertTrue(any("renumbered" in l for l in lines))

    def test_renumbering_onto_a_senate_row_merges_them(self):
        conn = store()
        brr.store_bill(conn, {"bill_key": "PL 1338/2022", "senado_codigo": 153194, "sigla": "PL",
                              "numero": 1338, "ano": 2022}, TODAY, log=quiet)
        brr.store_bill(conn, {"bill_key": "PL 3179/2012", "camara_id": 534328, "sigla": "PL",
                              "numero": 3179, "ano": 2012, "keywords": "ensino domiciliar"},
                       TODAY, log=quiet)
        brr.store_bill(conn, {"bill_key": "PL 1338/2022", "camara_id": 534328, "sigla": "PL",
                              "numero": 1338, "ano": 2022}, TODAY, log=quiet)
        rows = conn.execute("SELECT bill_key, camara_id, senado_codigo, keywords FROM br_bills").fetchall()
        self.assertEqual(rows, [("PL 1338/2022", 534328, 153194, "ensino domiciliar")])


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.watch = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
        self.watch.write('bills:\n  "PL 896/2023": {areas: [7], why: "test"}\n')
        self.watch.close()

    def tearDown(self):
        os.unlink(self.watch.name)

    def test_without_a_portuguese_taxonomy_only_the_watchlist_classifies(self):
        conn = store()
        brr.run(conn, FakeClient(camara_pages()), TODAY, [2026], log=quiet)
        brr.reclassify(conn, tax=None, log=quiet, watch_path=self.watch.name)
        got = dict(conn.execute("SELECT division_key, areas FROM br_divisions").fetchall())
        self.assertEqual(json.loads(got["camara-2636281-8"]), [7])
        self.assertEqual(json.loads(got["camara-2611313-31"]), [])
        # The vote's own text matched nothing: its area is lent by the bill.
        own = conn.execute("SELECT own_areas FROM br_divisions WHERE "
                           "division_key='camara-2636281-8'").fetchone()[0]
        self.assertEqual(json.loads(own), [])

    def test_a_portuguese_taxonomy_is_read_when_it_exists(self):
        tax = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
        tax.write('version: test\nareas:\n  7_free_speech_online_safety:\n'
                  '    tier1: ["misoginia"]\n    tier2: []\nexclusions_global: []\n')
        tax.close()
        try:
            conn = store()
            brr.run(conn, FakeClient(camara_pages()), TODAY, [2026], log=quiet)
            brr.reclassify(conn, tax=brr.load_taxonomy(tax.name), log=quiet,
                           watch_path=self.watch.name)
            areas, terms = conn.execute("SELECT areas, matched_terms FROM br_bills WHERE "
                                        "bill_key='PL 896/2023'").fetchone()
            self.assertEqual(json.loads(areas), [7])
            self.assertIn("misoginia", json.loads(terms))
        finally:
            os.unlink(tax.name)
        self.assertIsNone(brr.load_taxonomy(os.path.join(FX, "no-such-taxonomy.yaml")))


class WatchlistTests(unittest.TestCase):
    def test_every_watchlist_key_is_well_formed_and_explained(self):
        wl = br_store.watchlist()
        self.assertGreater(len(wl), 0)
        for key, (areas, why) in wl.items():
            self.assertRegex(key, r"^(SF )?(PL|PEC|PLP|PDL|MPV|PRC|PDC) \d+/\d{4}$", key)
            self.assertTrue(areas and all(1 <= a <= 13 for a in areas), key)
            self.assertTrue(why, key)

    def test_the_watchlist_is_applied_by_key_not_title(self):
        res = br_store.add_watch_areas(filt.FilterResult(), "PL 1904/2024")
        self.assertEqual(res.issue_areas, [1])
        self.assertEqual(res.watchlist_hits, ["watch:PL 1904/2024"])
        self.assertEqual(br_store.add_watch_areas(filt.FilterResult(), "PL 1905/2024").issue_areas, [])


class SchemaTests(unittest.TestCase):
    def test_every_br_table_is_declared_in_db_tables(self):
        for t in br_store.TABLES:
            self.assertIn(t, db.TABLES)


if __name__ == "__main__":
    unittest.main()
