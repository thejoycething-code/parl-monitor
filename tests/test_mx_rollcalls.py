"""Mexico's Chamber of Deputies: deputies, iniciativas, votes and positions
(tools/mx_rollcalls.py). No network.

The fixtures in tests/fixtures/mx/ are real pages saved by the scoping probe
of 9 October 2026 (tools/mx_probe.py, run from a GitHub runner), trimmed:
the deputies list keeps two deputies per group, the two group lists keep
four and three deputies, and sitl_est_2_trimmed.html is the real totals page
of vote 2 with its rows cut to those two groups so that the totals and the
lists agree. sitl_est_2.html is the same page untouched.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, mx_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "mx")


def _load():
    spec = importlib.util.spec_from_file_location(
        "mx_rollcalls", os.path.join(ROOT, "tools", "mx_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mxr = _load()


def raw(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def page(name):
    return mxr.decode(raw(name))


TAX = filt.load_taxonomy(os.path.join(FIX, "taxonomy-es-test.yaml"))

# One period, one vote: the row markup is SITL's own (sitl_periodos.html,
# votacionesxperiodonplxvi.php?pert=1), cut to vote 2.
PERIODS = (b'<a href="votacionesxperiodonplxvi.php?pert=1" > Primer Per\xc3\xadodo de Sesiones '
           b'Ordinarias del Primer A\xc3\xb1o</a>')
PERT1 = ('<span class="Estilo61enex"> Primer Período de Sesiones Ordinarias del Primer Año </span>'
         '<TR><TD bgcolor="#cccccc" colspan=2 valign="middle" align="center" class="textoNegro1" '
         'height="25">3 Septiembre 2024</TD></TR><tr valign="top" ><td class="estilolinks" '
         'valign="middle" align="center"><a href="estadistico_votacionnplxvi.php?votaciont=2" '
         'class="estilolinks">1</a></td><td class="Estiloparrafoc">DECRETO POR EL QUE SE REFORMAN '
         'DIVERSAS DISPOSICIONES, EN MATERIA DE INTERRUPCION LEGAL DEL EMBARAZO </td></tr>'
         ).encode("utf-8")


class FakeClient:
    """Serves fixtures by URL fragment; records what was asked."""

    def __init__(self, routes, fail=()):
        self.routes, self.fail, self.asked = routes, fail, []

    def get_bytes(self, url, feed, slug, **kw):
        self.asked.append(url)
        for frag in self.fail:
            if frag in url:
                raise FetchError(url, feed, slug, 1, "timed out")
        for frag, body in self.routes:
            if frag in url:
                return body
        raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")


def vote_routes(est="sitl_est_2_trimmed.html"):
    return [("votaciones_por_periodo", PERIODS), ("votacionesxperiodonplxvi.php?pert=1", PERT1),
            ("estadistico_votacionnplxvi.php?votaciont=2", raw(est)),
            ("partidot=14&votaciont=2", raw("sitl_list_2_14.html")),
            ("partidot=1&votaciont=2", raw("sitl_list_2_1.html"))]


def store():
    return db.init_db(db.connect(":memory:"))


def watch_file(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


EMPTY_WATCH = watch_file("iniciativas: {}\n")


class Helpers(unittest.TestCase):
    def test_dates_in_all_three_shapes(self):
        self.assertEqual(mxr.iso_date("3 Septiembre 2024"), "2024-09-03")
        self.assertEqual(mxr.iso_date("3-Septiembre-2024"), "2024-09-03")
        self.assertEqual(mxr.iso_date("martes 1 de septiembre de 2026"), "2026-09-01")
        self.assertIsNone(mxr.iso_date("número 7116-II"))

    def test_a_mixed_encoding_page_keeps_its_names(self):
        """SITL's vote lists are UTF-8 with one Latin-1 byte in a CSS comment."""
        body = raw("sitl_list_2_14.html")
        with self.assertRaises(UnicodeDecodeError):
            body.decode("utf-8")
        names = [n for _d, n, _p in mxr.parse_listado(mxr.decode(body))]
        self.assertIn("Gómez Urrutia Napoleón", names)

    def test_fold_strips_accents_only(self):
        self.assertEqual(mxr.fold("INTERRUPCIÓN Niñas"), "INTERRUPCION Ninas")


class SitlParsers(unittest.TestCase):
    def test_members_carry_their_group_from_the_logo(self):
        rows = mxr.parse_members(page("sitl_diputados.html"))
        self.assertEqual(len(rows), 13)
        first = rows[0]
        self.assertEqual((first["dipt"], first["name"], first["party"], first["entidad"],
                          first["distrito"]),
                         (391, "Abreu Artiñano Rocío Adriana", "MORENA", "Campeche", "Circ. 3"))
        self.assertEqual({r["party"] for r in rows},
                         {"MORENA", "PAN", "PVEM", "PT", "PRI", "MC", "IND"})

    def test_periods(self):
        periods = mxr.parse_periods(page("sitl_periodos.html"))
        self.assertEqual([p for p, _l in periods], [1, 3, 5, 6, 8, 10, 11])
        self.assertEqual(periods[-1][1], "Primer Período de Sesiones Ordinarias del Tercer Año")

    def test_a_period_lists_votes_under_their_dates(self):
        label, votes = mxr.parse_period_votes(page("sitl_pert11.html"))
        self.assertEqual(label, "Primer Período de Sesiones Ordinarias del Tercer Año")
        self.assertEqual(len(votes), 11)
        self.assertEqual(votes[0][:2], (297, "2026-09-14"))
        self.assertEqual(votes[-1][:2], (307, "2026-10-07"))
        self.assertIn("LEY FEDERAL DEL DERECHO DE AUTOR", votes[-1][2])

    def test_totals_groups_and_lists(self):
        est = mxr.parse_estadistico(page("sitl_est_2.html"))
        self.assertEqual(est["date"], "2024-09-03")
        self.assertIn("REFORMA DEL PODER JUDICIAL", est["title"])
        self.assertEqual(est["total"], [359, 135, 0, 0, 6, 500])
        self.assertEqual(est["groups"]["MORENA"], [250, 0, 0, 0, 5, 255])
        self.assertEqual(est["lists"][:2], [(14, "MORENA"), (3, "PAN")])
        self.assertEqual(len(est["lists"]), 8)

    def test_a_group_list(self):
        rows = mxr.parse_listado(page("sitl_list_2_1.html"))
        self.assertEqual(rows[0], (64, "Abramo Masso Yerico", "En contra"))
        self.assertEqual(len(rows), 3)


class GacetaParsers(unittest.TestCase):
    def setUp(self):
        self.inis = {i["ini_key"]: i for i in mxr.parse_iniciativas(
            page("gaceta_inis_mix.html"), 66, "mix")}

    def test_every_entry_is_keyed_by_its_number_or_its_anchor(self):
        self.assertIn("66/7223", self.inis)
        prov = [i for i in self.inis.values() if i["provisional"]]
        self.assertEqual(len(prov), 2)
        self.assertTrue(all(i["ini_key"].startswith("66/p/") and i["number"] is None
                            for i in prov))
        self.assertTrue(prov[0]["ini_key"].endswith("20260902-II-1-1.html#Iniciativa4"))

    def test_presenter_origin_party_turno_and_date(self):
        i = self.inis["66/7223"]
        self.assertEqual(i["origin"], "senado")
        self.assertEqual(i["party"], "PVEM")
        self.assertEqual(i["turno"], "Comisión de Hacienda y Crédito Público")
        self.assertEqual(i["presented"], "2026-09-01")
        self.assertEqual(i["gaceta_ref"], "/Gaceta/66/2026/sep/20260901-II.html#Iniciativa3")

    def test_a_minuta_from_the_senate(self):
        minutas = [i for i in self.inis.values() if i["kind"] == "minuta"]
        self.assertEqual(len(minutas), 1)
        self.assertEqual(minutas[0]["origin"], "senado")
        self.assertTrue(minutas[0]["vote_tables"])

    def test_the_furthest_step_not_the_last_line(self):
        self.assertEqual(mxr.furthest_step([
            "Turnada a la Comisión de Turismo.",
            "Dictaminada y aprobada en la Cámara de Diputados con 457 votos en pro.",
            "Turnada a la Cámara de Senadores."]), "aprobada")
        self.assertEqual(self.inis["66/1"]["status"], "publicada")
        self.assertEqual(self.inis["66/1"]["vote_tables"],
                         ["/Gaceta/Votaciones/66/tabla1or1-39.php3"])

    def test_the_turno_loses_its_article(self):
        self.assertEqual(mxr.parse_iniciativas(
            "<ul><li>Que reforma algo.<br>Presentada por la diputada X, PT.<br>Turnada a las "
            "Comisiones Unidas de Salud y de Justicia.<br>Gaceta Parlamentaria, número 1, martes "
            "1 de septiembre de 2026. (9)</li></ul>")[0]["turno"],
            "Comisiones Unidas de Salud y de Justicia")

    def test_index_pages_name_this_legislatures_lists_only(self):
        inis = mxr.gaceta_lists(page("gaceta_gp_iniciativas.html"), "Iniciativas")
        self.assertIn("/Gaceta/Iniciativas/66/gp66_a3primero.html", inis)
        self.assertTrue(all("/66/" in h for h in inis))
        votes = mxr.gaceta_lists(page("gaceta_gp_votaciones.html"), "Votaciones")
        self.assertEqual(len(votes), 7)

    def test_gaceta_votes_take_the_session_date_and_leave_particulars_open(self):
        g = mxr.parse_gaceta_votes(page("gaceta_vot66_a1primero.html"))
        # Printed as "el jueves 29 de agosto de 2021" in the sentence.
        self.assertEqual(g["/Gaceta/Votaciones/66/tabla1or1-1.php3"]["date"], "2024-08-29")
        judicial = g["/Gaceta/Votaciones/66/tabla1or1-2.php3"]
        self.assertEqual((judicial["favor"], judicial["contra"]), (359, 135))
        self.assertIsNone(g["/Gaceta/Votaciones/66/tabla1or1-16.php3"]["favor"])

    def test_a_vote_table_gives_its_totals(self):
        self.assertEqual(mxr.parse_tabla(page("gaceta_tabla2or2-1.php3")), (452, 1, 0))

    def test_a_sitl_vote_finds_its_gaceta_table_by_date_and_counts(self):
        g = mxr.parse_gaceta_votes(page("gaceta_vot66_a1primero.html"))
        est = mxr.parse_estadistico(page("sitl_est_2.html"))
        self.assertEqual(mxr.match_tabla(g, est), "/Gaceta/Votaciones/66/tabla1or1-2.php3")
        self.assertIsNone(mxr.match_tabla(g, dict(est, date="2024-09-04")))


class Classification(unittest.TestCase):
    def test_no_taxonomy_means_no_term_areas(self):
        res = mxr.classify(None, "EN MATERIA DE INTERRUPCION LEGAL DEL EMBARAZO")
        self.assertEqual(res.issue_areas, [])

    def test_an_unaccented_upper_case_title_matches_an_accented_term(self):
        res = mxr.classify(TAX, "EN MATERIA DE INTERRUPCION LEGAL DEL EMBARAZO")
        self.assertEqual(res.issue_areas, [1])

    def test_the_watchlist_gives_areas_by_key_alone(self):
        path = watch_file('iniciativas:\n  "66/1130": {areas: [1], why: "test"}\n')
        res = mxr.classify(None, "Que reforma los artículos 329 y 332", "66/1130", path)
        self.assertEqual(res.issue_areas, [1])
        self.assertIn("watch:66/1130", res.watchlist_hits)
        self.assertEqual(mxr.classify(None, "Que reforma", "66/1131", path).issue_areas, [])

    def test_the_shipped_watchlist_uses_real_numbers_only(self):
        keys = mx_store.watchlist(os.path.join(ROOT, "config", "watchlist-mx.yaml"))
        self.assertTrue(keys)
        for key, spec in keys.items():
            self.assertRegex(key, r"^\d{2}/\d+$")
            self.assertTrue(spec["areas"] and spec["why"])


class Store(unittest.TestCase):
    def test_db_declares_and_creates_the_tables(self):
        conn = store()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in mx_store.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertIn(t, have)

    def test_a_provisional_entry_is_rekeyed_when_its_number_arrives(self):
        conn = store()
        prov = mxr.parse_iniciativas(page("gaceta_inis_mix.html"), 66, "mix")
        prov = [i for i in prov if i["provisional"]][0]
        mxr.store_iniciativa(conn, prov, filt.FilterResult(), "2026-10-03")
        numbered = dict(prov, ini_key="66/7840", number=7840, provisional=0)
        mxr.store_iniciativa(conn, numbered, filt.FilterResult(), "2026-10-10")
        rows = conn.execute("SELECT ini_key, number, provisional, first_seen FROM "
                            "mx_iniciativas").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("66/7840", 7840, 0, "2026-10-03")])

    def test_iniciativas_pull_reads_every_list_of_the_legislature(self):
        conn = store()
        index = (b'<A HREF="/Gaceta/Iniciativas/66/gp66_a3primero.html">x</A>'
                 b'<A HREF="/Gaceta/Iniciativas/65/gp65_a3primero.html">old</A>')
        client = FakeClient([("gp_iniciativas.html", index),
                             ("gp66_a3primero.html", raw("gaceta_inis_mix.html"))])
        read, ours, gaps = mxr.pull_iniciativas(conn, client, "2026-10-10", tax=None,
                                                log=lambda *a: None, watch_path=EMPTY_WATCH)
        self.assertEqual((read, ours, gaps), (9, 0, 0))
        self.assertFalse(any("gp65" in u for u in client.asked))
        self.assertEqual(conn.execute("SELECT period FROM mx_iniciativas LIMIT 1").fetchone()[0],
                         "a3primero")


class Votes(unittest.TestCase):
    def test_a_vote_end_to_end_with_every_position(self):
        conn = store()
        path = watch_file('iniciativas:\n  "66/1130": {areas: [1], why: "t", votaciones: [2]}\n')
        new, read, ours, gaps = mxr.pull_votes(conn, FakeClient(vote_routes()), "2026-10-10",
                                               tax=None, gaceta={}, log=lambda *a: None,
                                               watch_path=path)
        self.assertEqual((new, read, ours, gaps), (1, 1, 1, 0))
        d = conn.execute("SELECT * FROM mx_divisions").fetchone()
        self.assertEqual(d["division_key"], "dip-66-2")
        self.assertEqual((d["date"], d["favor"], d["contra"], d["ausente"], d["total"],
                          d["positions"]), ("2024-09-03", 0, 3, 4, 7, 7))
        self.assertEqual(json.loads(d["areas"]), [1])
        self.assertEqual(json.loads(d["own_areas"]), [])
        votes = conn.execute("SELECT member_key, position, party FROM mx_votes ORDER BY "
                             "member_key").fetchall()
        self.assertEqual(len(votes), 7)
        self.assertIn(("66/64", "En contra", "PRI"), [tuple(v) for v in votes])
        self.assertIn(("66/345", "Ausente", "MORENA"), [tuple(v) for v in votes])
        name = conn.execute("SELECT name FROM mx_members WHERE member_key='66/345'").fetchone()[0]
        self.assertEqual(name, "Gómez Urrutia Napoleón")

    def test_the_vote_classifies_on_its_own_title_once_there_is_a_taxonomy(self):
        conn = store()
        mxr.pull_votes(conn, FakeClient(vote_routes()), "2026-10-10", tax=TAX, gaceta={},
                       log=lambda *a: None, watch_path=EMPTY_WATCH)
        # The trimmed totals page carries the judicial-reform title, so the
        # vote's own text has no term: the PERIOD page's title is only the
        # fallback. Area comes only when the title says so.
        own = conn.execute("SELECT own_areas FROM mx_divisions").fetchone()[0]
        self.assertEqual(json.loads(own), [])

    def test_lists_that_do_not_add_up_are_a_gap_and_retried(self):
        conn = store()
        routes = vote_routes("sitl_est_2.html") + [("listados_votaciones", raw("sitl_list_2_1.html"))]
        new, read, ours, gaps = mxr.pull_votes(conn, FakeClient(routes),
                                               "2026-10-10", gaceta={}, log=lambda *a: None,
                                               watch_path=EMPTY_WATCH)
        self.assertEqual((read, gaps), (0, 1))
        self.assertIsNone(conn.execute("SELECT positions FROM mx_divisions").fetchone()[0])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM mx_votes").fetchone()[0], 0)
        self.assertIn("totals say 500", conn.execute("SELECT detail FROM gaps").fetchone()[0])

    def test_a_host_that_times_out_is_a_gap_not_a_crash(self):
        conn = store()
        client = FakeClient(vote_routes(), fail=("partidot=1&",))
        new, read, ours, gaps = mxr.pull_votes(conn, client, "2026-10-10", gaceta={},
                                               log=lambda *a: None, watch_path=EMPTY_WATCH)
        self.assertEqual((new, read, gaps), (1, 0, 1))
        # Next run: only the unread vote is asked for again, not re-indexed.
        client2 = FakeClient(vote_routes())
        new, read, ours, gaps = mxr.pull_votes(conn, client2, "2026-10-17", gaceta={},
                                               log=lambda *a: None, watch_path=EMPTY_WATCH)
        self.assertEqual((new, read, gaps), (0, 1, 0))

    def test_a_matched_table_ties_the_vote_to_its_iniciativas(self):
        conn = store()
        tabla = "/Gaceta/Votaciones/66/tabla1or1-2.php3"
        path = watch_file('iniciativas:\n  "66/77": {areas: [9], why: "t"}\n')
        ini = dict(mxr.parse_iniciativas(page("gaceta_inis_mix.html"), 66, "m")[0],
                   ini_key="66/77", number=77, vote_tables=[tabla])
        mxr.store_iniciativa(conn, ini, mxr.classify(None, ini["title"], "66/77", path),
                             "2026-10-10")
        gaceta = {tabla: {"date": "2024-09-03", "title": "x", "favor": 0, "contra": 3,
                          "abstencion": 0}}
        mxr.pull_votes(conn, FakeClient(vote_routes()), "2026-10-10", gaceta=gaceta,
                       log=lambda *a: None, watch_path=path)
        d = conn.execute("SELECT gaceta_tabla, ini_keys, areas FROM mx_divisions").fetchone()
        self.assertEqual(d["gaceta_tabla"], tabla)
        self.assertEqual(json.loads(d["ini_keys"]), ["66/77"])
        self.assertEqual(json.loads(d["areas"]), [9])

    def test_reclassify_fills_areas_once_the_taxonomy_lands(self):
        conn = store()
        conn.execute("INSERT INTO mx_iniciativas (ini_key, legislature, title, areas) VALUES "
                     "('66/1130', 66, 'Que reforma el Código Penal Federal, en materia de "
                     "interrupción legal del embarazo.', '[]')")
        changed = mxr.reclassify(conn, TAX, log=lambda *a: None, watch_path=EMPTY_WATCH)
        self.assertEqual(changed, (1, 0))
        self.assertEqual(json.loads(conn.execute("SELECT areas FROM mx_iniciativas")
                                    .fetchone()[0]), [1])


class Jobs(unittest.TestCase):
    def test_the_mini_job_is_a_clock_that_needs_no_store(self):
        with open(os.path.join(ROOT, "jobs", "mx-weekly.sh"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("\n# mini_run: no-store", src)
        self.assertIn("gh workflow run mx-weekly.yml", src)

    def test_the_workflow_is_gated_and_runs_the_collect_job(self):
        with open(os.path.join(ROOT, ".github", "workflows", "mx-weekly.yml"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("job: MX_WEEKLY", src)
        self.assertIn("bash jobs/mx-collect.sh", src)
        self.assertTrue(src.startswith("name: Mexico weekly"))


class FortnightlyTests(unittest.TestCase):
    """X9 (Chris, 10 October 2026): Mexico runs every second week, in odd ISO
    weeks; Guatemala takes the even ones."""

    def test_gate_and_clock_skip_even_weeks(self):
        with open(os.path.join(ROOT, ".github", "workflows", "mx-weekly.yml"), encoding="utf-8") as fh:
            yml = fh.read()
        with open(os.path.join(ROOT, "jobs", "mx-weekly.sh"), encoding="utf-8") as fh:
            sh = fh.read()
        self.assertIn("$((10#$WEEK % 2)) -eq 0", yml)
        self.assertIn("$((10#$week % 2)) -eq 0", sh)
        self.assertIn("MX_FORCE", sh)
        with open(os.path.join(ROOT, ".github", "workflows", "gt-weekly.yml"), encoding="utf-8") as fh:
            self.assertIn("$((10#$WEEK % 2)) -ne 0", fh.read())


if __name__ == "__main__":
    unittest.main()
