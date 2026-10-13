"""Paraná through ALEP's open-data API (tools/br_alep.py), the repository's
one plain-HTTP source (src/http.PLAIN_HTTP_EXCEPTIONS, Chris, 13 October
2026), offline: fixtures under tests/fixtures/br_states/alep_*.json are the
API's own answers fetched that day (GET /proposicao/{código}), plus a draft,
a requerimento and a missing código in the same shape. No network.
"""

import copy
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import br_alep as A  # noqa: E402
import br_states as S  # noqa: E402
from src import brs_edition, brs_store, db, drain  # noqa: E402
from src.http import FetchError, plain_http_allowed  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "br_states")
TODAY = "2026-10-13"


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


class FakeAlep:
    """código -> answer; GET only (a POST would fail the test)."""

    def __init__(self, answers):
        self.answers = answers
        self.urls = []

    def get_bytes(self, url, feed, slug, **kw):
        self.urls.append(url)
        code = int(url.rsplit("/", 1)[1])
        got = self.answers.get(code, load("alep_none.json"))
        if isinstance(got, Exception):
            raise got
        return json.dumps(got).encode("utf-8")

    def post_form(self, *a, **k):
        raise AssertionError("ALEP is read with GETs only")

    post_json = post_form


def ctx(conn, meta=None):
    known, stored_meta, read_ok = S.snapshot(conn)
    if meta is not None:
        stored_meta["alep"] = meta
    return {"tax": S.load_taxonomy(), "budget": drain.Budget(600), "known": known,
            "meta": stored_meta, "read_ok": read_ok, "today": TODAY, "sleep": None}


class Parse(unittest.TestCase):
    def test_a_bill_in_passage(self):
        got = A.parse_proposicao(load("alep_131487.json")["valor"], S._clean)
        b = got["bill"]
        self.assertEqual(b["bill_key"], "pr/PL 781/2026")
        self.assertEqual((b["source"], b["uf"], b["source_id"]), ("alep", "pr", "131487"))
        self.assertEqual(b["presented"], "2026-10-06")
        self.assertEqual(b["authors"], "PODER EXECUTIVO")
        # handling (INFORMAÇÃO, ENCAMINHADO, AUTUADO ...) is not a stage
        self.assertEqual(b["status"], "Em DL - AUTUAÇÃO")
        self.assertEqual(got["votes"], [])
        self.assertFalse(got["draft"])

    def test_a_bill_that_became_law_with_its_results(self):
        got = A.parse_proposicao(load("alep_127049.json")["valor"], S._clean)
        b = got["bill"]
        self.assertEqual(b["bill_key"], "pr/PL 1122/2025")
        self.assertEqual(b["status"], "Became Lei 22906/2025 (per ALEP)")
        self.assertEqual(got["normas"][0][:4], ("Lei", "Lei", 22906, 2025))
        votes = [(v["body"], v["description"], v["result"]) for v in got["votes"]]
        self.assertEqual(votes[0], ("COMISSÃO DE CONSTITUIÇÃO E JUSTIÇA",
                                    "APROVADO O PARECER FAVORÁVEL", "Aprovado"))
        self.assertIn(("plenary", "1º TURNO - APROVADO", "Aprovado"), votes)
        self.assertIn(("plenary", "2º TURNO - APROVADO", "Aprovado"), votes)
        # no tallies and no member votes: the API prints none
        self.assertTrue(all(v["yes"] is None and v["no"] is None for v in got["votes"]))

    def test_drafts_and_other_documents(self):
        self.assertTrue(A.parse_proposicao(load("alep_draft.json")["valor"])["draft"])
        req = A.parse_proposicao(load("alep_req.json")["valor"])
        self.assertIsNone(req["bill"])
        self.assertFalse(req["draft"])

    def test_similarity_reads_a_redrafted_title_as_the_same_law(self):
        alep = ("INSERE NO CALENDÁRIO OFICIAL DO ESTADO DO PARANÁ O EVENTO FESTA DO DIVINO ESPÍRITO "
                "SANTO DO MUNICÍPIO DE PINHÃO, A SER REALIZADO ANUALMENTE ENTRE OS DIAS 1 DE JUNHO E "
                "13 DE JUNHO E RECONHECE COMO PATRIMÔNIO CULTURAL E IMATERIAL A FOLIA DO DIVINO.")
        casa = ("Insere no Calendário Oficial de Eventos do Estado do Paraná a Festa do Divino Espírito "
                "Santo, realizada anualmente entre os dias 1º e 13 de junho no Município de Pinhão, e "
                "reconhece a Folia do Divino como Patrimônio Cultural e Imaterial do Estado do Paraná.")
        self.assertGreaterEqual(A.similarity(alep, casa), A.TITLE_MISMATCH)
        self.assertLess(A.similarity(alep, "Autoriza a doação de imóvel ao Município de Mariluz."),
                        A.TITLE_MISMATCH)


class Walk(unittest.TestCase):
    def setUp(self):
        self._stop = A.ALEP_MISS_STOP
        A.ALEP_MISS_STOP = 3

    def tearDown(self):
        A.ALEP_MISS_STOP = self._stop

    def test_walks_up_by_get_and_keeps_its_place(self):
        conn = store()
        client = FakeAlep({100: load("alep_131487.json"), 102: load("alep_draft.json"),
                           103: load("alep_127049.json"), 104: load("alep_req.json")})
        res = A.fetch_alep(client, ctx(conn, {"next": 100}), S)
        self.assertEqual(sorted(b["bill_key"] for b in res.bills), ["pr/PL 1122/2025", "pr/PL 781/2026"])
        # every request is inside the one exception, and a GET
        self.assertTrue(all(u.startswith(A.ALEP_API) and plain_http_allowed(u) for u in client.urls))
        self.assertEqual(client.urls[0], A.ALEP_API + "proposicao/100")
        # 105..107 missed: the top is 105 again next run; 101 is a hole, 102 a draft
        self.assertEqual(res.meta["next"], 105)
        self.assertEqual(res.meta["holes"], {"101": 0})
        self.assertEqual(res.meta["pending"], {"102": TODAY})
        self.assertEqual(len(res.votes), 3)   # CCJ, 1st and 2nd turno
        self.assertEqual(res.status, "ok")

    def test_unreachable_is_a_gap_not_a_failure(self):
        conn = store()
        client = FakeAlep({100: FetchError("u", "f", "s", 1, "timed out")})
        res = A.fetch_alep(client, ctx(conn, {"next": 100}), S)
        self.assertEqual(res.status, "unreachable")
        self.assertTrue(res.gaps)

    def test_request_cap(self):
        cap = A.ALEP_REQUEST_CAP
        A.ALEP_REQUEST_CAP = 2
        try:
            conn = store()
            client = FakeAlep({100: load("alep_131487.json"), 101: load("alep_req.json"),
                               102: load("alep_127049.json")})
            res = A.fetch_alep(client, ctx(conn, {"next": 100}), S)
        finally:
            A.ALEP_REQUEST_CAP = cap
        self.assertEqual(len(client.urls), 2)
        self.assertEqual(res.meta["next"], 102)
        self.assertIn("request cap", " ".join(res.gaps))


class CrossCheck(unittest.TestCase):
    def law(self, conn, number, title):
        b = S.law_bill("pr", "pr", "Lei", "Lei", number, 2025, title, "2025-12-12", "Lei publicada",
                       "https://www.legislacao.pr.gov.br/x", str(number))
        brs_store.upsert_bill(conn, b, [], [], None, TODAY, 0)

    def test_a_matching_law_is_quiet(self):
        conn = store()
        self.law(conn, 22906, "Altera a Lei nº 15.699, de 27 de novembro de 2007, que autoriza o Poder "
                              "Executivo a efetuar a doação do imóvel que especifica ao Município de São "
                              "José dos Pinhais.")
        normas = [("pr/PL 1122/2025", "Lei", 22906, 2025, load("alep_127049.json")["valor"]
                   ["normasLegais"][0]["ementa"])]
        self.assertEqual(A.crosscheck(conn, normas), [])

    def test_same_number_other_title_is_a_gap(self):
        conn = store()
        self.law(conn, 22906, "Concede o título de utilidade pública à Associação Atlética de Umuarama.")
        normas = [("pr/PL 1122/2025", "Lei", 22906, 2025, "ALTERA A LEI Nº 15.699 ... DOAÇÃO DO IMÓVEL "
                   "AO MUNICÍPIO DE SÃO JOSÉ DOS PINHAIS.")]
        gaps = A.crosscheck(conn, normas)
        self.assertEqual(len(gaps), 1)
        self.assertIn("not trusted", gaps[0])
        self.assertIn("Lei 22906/2025", gaps[0])

    def test_same_title_other_number_is_a_gap(self):
        conn = store()
        title = "Autoriza o Poder Executivo a efetuar a doação, ao Município de Mariluz, do imóvel que especifica."
        self.law(conn, 22879, title)
        gaps = A.crosscheck(conn, [("pr/PL 1128/2025", "Lei", 22880, 2025, title.upper())])
        self.assertEqual(len(gaps), 1)
        self.assertIn("Lei 22879/2025", gaps[0])

    def test_a_law_the_casa_civil_has_not_listed_is_no_mismatch(self):
        conn = store()
        self.assertEqual(A.crosscheck(conn, [("pr/PL 1/2026", "Lei", 1, 2026, "QUALQUER")]), [])


class ThroughTheCollector(unittest.TestCase):
    """br_states.run with 'alep': stored after 'pr', cross-checked, noted."""

    def test_run_stores_votes_flags_a_mismatch_and_notes_the_source(self):
        conn = store()
        # The Casa Civil's list (already read) gives 22906/2025 another title.
        b = S.law_bill("pr", "pr", "Lei", "Lei", 22906, 2025,
                       "Concede o título de utilidade pública à Associação Atlética de Umuarama.",
                       "2025-12-12", "Lei publicada", "https://www.legislacao.pr.gov.br/x", "1")
        brs_store.upsert_bill(conn, b, [], [], None, TODAY, 0)
        brs_store.record_read(conn, "alep", "pr", "ok", None, 0, 0, None, TODAY, {"next": 100})
        ours = copy.deepcopy(load("alep_131487.json"))
        ours["valor"]["ementa"] = "INSTITUI O DIA ESTADUAL DO NASCITURO NO ESTADO DO PARANÁ."
        ours["valor"]["dataRecebimento"] = "2026-10-12T10:00:00.000+0000"
        stop, A.ALEP_MISS_STOP = A.ALEP_MISS_STOP, 2
        try:
            client = FakeAlep({100: ours, 101: load("alep_127049.json")})
            _results, gaps = S.run(conn, ["alep"], S.load_taxonomy(), TODAY, drain.Budget(600),
                                   lambda: client, now=TODAY + "T10:00:00", workers=1)
        finally:
            A.ALEP_MISS_STOP = stop
        self.assertEqual(gaps, 1)
        gap = conn.execute("SELECT detail FROM gaps").fetchone()[0]
        self.assertIn("cross-check", gap)
        self.assertEqual(conn.execute("SELECT status FROM brs_reads WHERE source='alep'").fetchone()[0], "gap")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM brs_votes WHERE uf='pr'").fetchone()[0], 3)
        b = conn.execute("SELECT * FROM brs_bills WHERE bill_key='pr/PL 781/2026'").fetchone()
        self.assertEqual(b["source"], "alep")
        areas = json.loads(b["areas"] or "[]")
        self.assertTrue(S.on_our_ground(areas), areas)
        got = brs_edition.items(conn, "2026-10-06", "2026-10-13", wl={})
        it = [i for i in got if i["key"] == "pr/PL 781/2026"][0]
        self.assertIn("(via ALEP open data, unencrypted)", it["takeaway"])
        # the mismatch is on the edition's coverage line
        self.assertIn("Read with gaps: ALEP (ALEP open data (unencrypted) cross-check",
                      brs_edition.reads_line(conn))
        # a clean read says what the source is
        brs_store.record_read(conn, "alep", "pr", "ok", None, 2, 0, None, TODAY + "T11:00:00")
        self.assertIn("ALEP (bills via open data, unencrypted)", brs_edition.reads_line(conn))

    def test_alep_is_read_right_after_the_casa_civil(self):
        order = list(S.SOURCE_ORDER)
        self.assertEqual(order.index("alep"), order.index("pr") + 1)
        self.assertIs(S.ALT_FETCHERS["alep"].__class__, type(lambda: 0))


if __name__ == "__main__":
    unittest.main()
