"""Bolivia's Asamblea Legislativa Plurinacional: members and proyectos de ley
of both chambers (tools/bo_rollcalls.py). No network: the fixtures are real
replies from diputados.gob.bo and apisi.senado.gob.bo archived on 9 October
2026, trimmed to a few records (and a biography cut, as nothing personal is
stored)."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import bo_store, db  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "bo")


def _load():
    spec = importlib.util.spec_from_file_location(
        "bo_rollcalls", os.path.join(ROOT, "tools", "bo_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bor = _load()
TAX = bor.load_taxonomy(os.path.join(FIX, "taxonomy-es-test.yaml"))
WL = bor.empty_watchlist()
TODAY = "2026-10-09"


def fixture_json(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as handle:
        return json.load(handle)


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def gap_400(url):
    return FetchError(url, "t", "t", 1, Exception("HTTP Error 400: Bad Request"))


class FakeClient:
    """get_json from a list of (url substring, payload); first match wins. A
    payload that is an Exception is raised. Anything unrouted is a 400, as
    WordPress answers past the last page."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get_json(self, url, feed, slug, **kw):
        self.calls.append(url)
        for needle, payload in self.routes:
            if needle in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise gap_400(url)


def full_routes(dip_ley=None):
    return [
        ("/legislatura_de_ley?", fixture_json("dip_legislaturas.json")),
        ("/comision_de_ley?", fixture_json("dip_comisiones.json")),
        ("/cargo?", [{"id": 13, "name": "Diputado"}]),
        ("/diputados?", fixture_json("dip_members.json")),
        ("/ley?", fixture_json("dip_ley_page.json") if dip_ley is None else dip_ley),
        ("senadores/pleno", fixture_json("sen_pleno.json")),
        ("ley-tratamiento/buscar", fixture_json("sen_tratamiento.json")),
        ("ley-aprobados/buscar", fixture_json("sen_aprobados.json")),
        ("ley-sancionada/buscar", fixture_json("sen_sancionada.json")),
        ("ley-promulgada/buscar", fixture_json("sen_promulgada.json")),
        ("ley-rechazada/buscar", {"data": {"data": [], "last_page": 1, "total": 0}}),
        ("ley-devuelto/buscar", {"data": {"data": [], "last_page": 1, "total": 0}}),
    ]


def quiet(*_a, **_k):
    pass


class SchemaAndKeys(unittest.TestCase):
    def test_tables_declared_and_created(self):
        conn = store()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in bo_store.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertIn(t, names)

    def test_no_vote_tables_until_a_source_exists(self):
        self.assertFalse([t for t in bo_store.TABLES if "vote" in t or "division" in t])

    def test_every_diputados_spelling_keys_the_same_way(self):
        cases = {
            "PL No 820/2025-2026": "PL 820/2025-2026 CD",
            "PL N° 005/2020-2021": "PL 5/2020-2021 CD",
            "PLS N°092/2024-2025": "PL 92/2024-2025 CS",
            "PLS-291/2025-2026": "PL 291/2025-2026 CS",
            "PLS Nº 180/2024-2025": "PL 180/2024-2025 CS",
            "PLA 429-2023-2024": "PL 429/2023-2024 CD",
            "PLA  N° 113/2021-2022": "PL 113/2021-2022 CD",
            "PL CS N°098/2022-2023": "PL 98/2022-2023 CS",
            "PL-CS N° 125/2021-2022": "PL 125/2021-2022 CS",
            "PLS CD N° 114/2019-2020": "PL 114/2019-2020 CD",
            "N°219/2022-2023": "PL 219/2022-2023 CD",
            "PLP LEY D N° 1512": "LEY 1512",
        }
        for titulo, key in cases.items():
            self.assertEqual(bo_store.dip_key(titulo)[0], key, titulo)

    def test_a_law_by_date_keys_on_its_number(self):
        self.assertEqual(bo_store.dip_key("Ley de 24 de octubre de 2019", "1245")[0], "LEY 1245")
        self.assertEqual(bo_store.dip_key("Ley de 11 de Noviembre de 2022", "Ley No 1491")[0],
                         "LEY 1491")
        self.assertIsNone(bo_store.dip_key("Ley de 11 de Noviembre de 2022", ""))

    def test_senado_spellings_meet_the_diputados_keys(self):
        self.assertEqual(bo_store.sen_key("P.L. N° 743/2025-2026 C.D.")[0], "PL 743/2025-2026 CD")
        self.assertEqual(bo_store.sen_key("P.L. N° 307/2024-2025 C.S.")[0], "PL 307/2024-2025 CS")
        self.assertEqual(bo_store.sen_key("295/2024-2025 C.S.")[0], "PL 295/2024-2025 CS")
        self.assertEqual(bo_store.sen_key("P.L. N° 001-2023-2024 C.D.")[0], "PL 1/2023-2024 CD")
        self.assertEqual(bo_store.sen_key("LEY N° 1754")[0], "LEY 1754")

    def test_origin_chamber_is_part_of_the_key(self):
        # Numbers restart per chamber of origin: 291 CD and 291 CS are two bills.
        self.assertNotEqual(bo_store.dip_key("PL No 291/2025-2026")[0],
                            bo_store.dip_key("PLS-291/2025-2026")[0])


class Classification(unittest.TestCase):
    def test_accents_fold_on_both_sides(self):
        res = bor.classify_bill(TAX, WL, "x", "LEY DE EDUCACION SEXUAL INTEGRAL", {})
        self.assertEqual(res.issue_areas, [6])

    def test_guarded_term_needs_company(self):
        alone = bor.classify_bill(TAX, WL, "x", "FINANZAS BÁSICAS EN LA CURRÍCULA ESCOLAR", {})
        self.assertEqual(alone.issue_areas, [])
        guarded = bor.classify_bill(TAX, WL, "x", "CURRÍCULA DE EDUCACIÓN SEXUAL", {})
        self.assertEqual(guarded.issue_areas, [6])

    def test_english_taxonomy_is_blind(self):
        # Measured over all 6,106 titles on 9 October 2026: no match at all.
        en = bor.load_taxonomy(bor.TAXONOMY_EN)
        res = bor.classify_bill(en, WL, "PL 691/2025-2026 CD",
                                'PROYECTO DE "LEY DE CUIDADOS PALIATIVOS, MUERTE DIGNA Y EUTANASIA"', {})
        self.assertEqual(res.issue_areas, [])

    def test_watchlist_applies_by_key_never_title(self):
        watch = {"PL 691/2025-2026 CD": ([2], "why")}
        hit = bor.classify_bill(bor.load_taxonomy(bor.TAXONOMY_EN), WL, "PL 691/2025-2026 CD",
                                "anything", watch)
        self.assertEqual(hit.issue_areas, [2])
        self.assertIn("watch:PL 691/2025-2026 CD", hit.watchlist_hits)
        miss = bor.classify_bill(bor.load_taxonomy(bor.TAXONOMY_EN), WL, "PL 691/2025-2026 CS",
                                 "anything", watch)
        self.assertEqual(miss.issue_areas, [])

    def test_repo_watchlist_parses_and_every_key_is_canonical(self):
        wl = bo_store.watchlist()
        self.assertTrue(wl)
        for key, (areas, _why) in wl.items():
            self.assertRegex(key, r"^(PL \d+/\d{4}-\d{4} C[DS]|LEY \d+)$")
            self.assertTrue(areas, key)


class Members(unittest.TestCase):
    def test_pull_members_both_chambers_no_personal_data(self):
        conn = store()
        stored, gaps = bor.pull_members(conn, FakeClient(full_routes()), TODAY, log=quiet)
        self.assertEqual((stored, gaps), (5, 0))
        rows = conn.execute("SELECT member_key, chamber, name, party_code, department, titular "
                            "FROM bo_members ORDER BY member_key").fetchall()
        dip = [r for r in rows if r[1] == "diputados"]
        sen = [r for r in rows if r[1] == "senado"]
        self.assertEqual(len(dip), 2)
        self.assertTrue(dip[0][0].startswith("diputados/"))
        self.assertIsNone(dip[0][3])   # the Diputados site carries no party
        self.assertEqual(sorted(r[5] for r in sen), [0, 1, 1])
        self.assertIn("senado/78", [r[0] for r in sen])
        avila = [r for r in sen if r[0] == "senado/78"][0]
        self.assertEqual((avila[2], avila[3], avila[4]),
                         ("Diego Esteban Mateo Ávila Navajas", "PDC", "Tarija"))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bo_members)")]
        for personal in ("email", "birth", "fecha_nacimiento", "biografia"):
            self.assertFalse([c for c in cols if personal in c])

    def test_party_code_is_accent_folded(self):
        m = bor.parse_sen_member({"id": 1, "nombre": "A", "apellidos": "B", "es_titular": 83,
                                  "bancada": {"nombre": "APB SÚMATE", "sigla": "APB-SÚMATE"}})
        self.assertEqual(m["party_code"], "APB-SUMATE")

    def test_a_failed_senado_list_is_a_gap_not_a_crash(self):
        conn = store()
        routes = [r for r in full_routes() if r[0] != "senadores/pleno"]
        routes.insert(0, ("senadores/pleno", FetchError("u", "t", "t", 4, Exception("timed out"))))
        stored, gaps = bor.pull_members(conn, FakeClient(routes), TODAY, log=quiet)
        self.assertEqual((stored, gaps), (2, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='bo-rollcalls'")
                         .fetchone()[0], 1)


class Bills(unittest.TestCase):
    def pull(self, conn, client=None, today=TODAY, watch=None):
        client = client or FakeClient(full_routes())
        d = bor.pull_dip_bills(conn, client, today, TAX, WL, watch or {}, log=quiet)
        s = bor.pull_sen_bills(conn, client, today, TAX, WL, watch or {}, log=quiet)
        return d, s, client

    def row(self, conn, key, cols="*"):
        conn.row_factory = sqlite3.Row
        r = conn.execute("SELECT {0} FROM bo_bills WHERE bill_key=?".format(cols), (key,)).fetchone()
        conn.row_factory = None
        return r

    def test_reads_current_year_and_recent_moves(self):
        conn = store()
        (_d, s, client) = self.pull(conn)
        ley_calls = [u for u in client.calls if "/ley?" in u]
        self.assertTrue(any("legislatura_de_ley=274" in u for u in ley_calls))
        self.assertTrue(any("modified_after=2026-09-18T00:00:00" in u for u in ley_calls))
        self.assertEqual(s[3], 0)

    def test_pla_folds_into_its_pl_and_the_latest_post_speaks(self):
        conn = store()
        self.pull(conn)
        r = self.row(conn, "PL 429/2023-2024 CD")
        self.assertEqual(r["dip_status"], "Proyecto de Ley Aprobado")   # PLA, Oct 2024
        self.assertEqual(r["dip_id"], 34148)

    def test_a_bill_crossing_chambers_is_one_row(self):
        conn = store()
        self.pull(conn)
        r = self.row(conn, "PL 411/2023-2024 CD")
        self.assertEqual(r["dip_status"], "Proyecto de Ley Aprobado")
        self.assertEqual(r["sen_stage"], "aprobados")
        self.assertIsNotNone(r["sen_document"])

    def test_most_advanced_senado_stage_wins(self):
        conn = store()
        self.pull(conn)
        self.assertEqual(self.row(conn, "PL 146/2024-2025 CS")["sen_stage"], "sancionada")

    def test_senado_bill_in_revision_at_diputados(self):
        conn = store()
        self.pull(conn)
        r = self.row(conn, "PL 291/2025-2026 CS")
        self.assertEqual((r["origin"], r["kind"]), ("CS", "PL"))
        self.assertIsNotNone(r["dip_status"])

    def test_law_and_unnumbered_post(self):
        conn = store()
        self.pull(conn)
        self.assertIsNotNone(self.row(conn, "LEY 1754"))
        r = self.row(conn, "LEY 1257")     # 'Ley de 24 de octubre de 2019', ley_nro '1257'
        self.assertEqual((r["kind"], r["law_number"]), ("LEY", "LEY 1257"))
        odd = conn.execute("SELECT bill_key, kind FROM bo_bills WHERE bill_key LIKE 'DIP-WP %'").fetchall()
        self.assertEqual(len(odd), 1)
        self.assertEqual(odd[0][1], "OTHER")

    def test_classified_on_spanish_terms_and_committee_named(self):
        conn = store()
        self.pull(conn)
        r = self.row(conn, "PL 691/2025-2026 CD")
        self.assertEqual(json.loads(r["areas"]), [2])
        self.assertEqual(r["tier"], 1)
        self.assertIn("Constitución", r["dip_committee"])
        self.assertEqual(json.loads(self.row(conn, "PL 238/2025-2026 CS")["areas"]), [8])

    def test_status_changes_logged_once_and_on_each_move(self):
        conn = store()
        self.pull(conn)
        first = conn.execute("SELECT COUNT(*) FROM bo_bill_changes").fetchone()[0]
        self.assertGreater(first, 0)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM bo_bill_changes WHERE old IS NOT NULL").fetchone()[0], 0)
        self.pull(conn, today="2026-10-10")     # nothing moved
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM bo_bill_changes").fetchone()[0], first)
        moved = fixture_json("sen_sancionada.json")
        promulgated = fixture_json("sen_tratamiento.json")
        routes = full_routes()
        routes.insert(0, ("ley-sancionada/buscar", promulgated))   # 743 CD and 238 CS: sancionada
        routes.insert(0, ("ley-tratamiento/buscar", {"data": {"data": [], "last_page": 1}}))
        self.pull(conn, client=FakeClient(routes), today="2026-10-17")
        rows = conn.execute("SELECT bill_key, old, new FROM bo_bill_changes WHERE seen='2026-10-17'"
                            " AND field='sen_stage' AND bill_key IN ('PL 238/2025-2026 CS',"
                            " 'PL 743/2025-2026 CD') ORDER BY bill_key").fetchall()
        self.assertEqual(rows, [("PL 238/2025-2026 CS", "tratamiento", "sancionada"),
                                ("PL 743/2025-2026 CD", "tratamiento", "sancionada")])
        # 146 CS left the sancionada list in this altered reply, so it falls
        # back to aprobados: the log records what the Senado says, even backwards.
        self.assertEqual(conn.execute("SELECT new FROM bo_bill_changes WHERE seen='2026-10-17' "
                                      "AND bill_key='PL 146/2024-2025 CS'").fetchone()[0], "aprobados")
        self.assertTrue(moved)

    def test_senado_pages_until_last_page(self):
        conn = store()
        p1 = {"data": {"data": fixture_json("sen_tratamiento.json")["data"]["data"][:1], "last_page": 2}}
        p2 = {"data": {"data": fixture_json("sen_tratamiento.json")["data"]["data"][1:], "last_page": 2}}
        routes = [("ley-tratamiento/buscar?per_page=100&page=1", p1),
                  ("ley-tratamiento/buscar?per_page=100&page=2", p2)] + full_routes()
        read, _ours, _moved, gaps = bor.pull_sen_bills(conn, FakeClient(routes), TODAY, TAX, WL, {},
                                                       log=quiet)
        self.assertEqual(gaps, 0)
        self.assertIsNotNone(self.row(conn, "PL 238/2025-2026 CS"))
        self.assertIsNotNone(self.row(conn, "PL 743/2025-2026 CD"))
        self.assertEqual(read, 5)

    def test_a_failed_bill_list_is_a_gap(self):
        conn = store()
        routes = [("ley-aprobados/buscar", FetchError("u", "t", "t", 4, Exception("timed out")))]
        routes += full_routes()
        _r, _o, _m, gaps = bor.pull_sen_bills(conn, FakeClient(routes), TODAY, TAX, WL, {}, log=quiet)
        self.assertEqual(gaps, 1)

    def test_reclassify_offline(self):
        conn = store()
        self.pull(conn)
        conn.execute("UPDATE bo_bills SET areas='[]'")
        changed = bor.reclassify(conn, tax=TAX, log=quiet)
        self.assertGreaterEqual(changed, 2)
        self.assertEqual(json.loads(self.row(conn, "PL 691/2025-2026 CD")["areas"]), [2])


if __name__ == "__main__":
    unittest.main()
