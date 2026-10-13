"""Brazil's state assemblies (tools/br_states.py, src/brs_store.py,
src/brs_edition.py), offline: fixtures under tests/fixtures/br_states/ (the
ALMG search and bill pages and the ALERJ Notes view as fetched on 13 October
2026, trimmed; ALESP's open-data files and the SAPL API answers rebuilt
small, in the sources' own shapes). No network.
"""

import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import br_states as S  # noqa: E402
from src import brs_edition, brs_store, db, drain  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "br_states")
TODAY = "2026-10-10"


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


# URL fragment -> fixture file, first match wins.
ROUTES = (
    ("proposituras.zip", "sp_proposituras.zip"),
    ("documento_autor.zip", "sp_autores.zip"),
    ("documento_andamento_atual.zip", "sp_andamento.zip"),
    ("deputados.xml", "sp_deputados.xml"),
    ("comissoes_permanentes_reunioes.xml", "sp_reunioes.xml"),
    ("comissoes_permanentes_votacoes.xml", "sp_votacoes.xml"),
    ("comissoes_permanentes_deliberacoes.xml", "sp_deliberacoes.xml"),
    ("comissoes.xml", "sp_comissoes.xml"),
    ("www.almg.gov.br/atividade-parlamentar/projetos-de-lei/", "mg_list.html"),
    ("www.almg.gov.br/projetos-de-lei/", "mg_bill.html"),
    ("LeiInt?OpenForm", "rj_view.html"),
    ("tipomaterialegislativa", "sapl_tipos.json"),
    ("materia/materialegislativa", "sapl_materias.json"),
    ("materia/tramitacao", "sapl_tramitacao.json"),
    ("base/autor", "sapl_autor.json"),
    ("sessao/registrovotacao", "sapl_votos.json"),
)


class FakeClient:
    def __init__(self, fail=()):
        self.urls = []
        self.fail = fail

    def get_bytes(self, url, feed, slug, **kw):
        self.urls.append(url)
        if any(f in url for f in self.fail):
            raise FetchError(url, feed, slug, 1, "HTTP Error 503")
        for frag, name in ROUTES:
            if frag in url:
                return fixture(name)
        raise FetchError(url, feed, slug, 1, "HTTP Error 404: no fixture")


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def tax():
    return S.load_taxonomy()


class Parsers(unittest.TestCase):
    def test_sp_proposituras_keeps_bills_of_this_legislature(self):
        got = S.parse_sp_proposituras(fixture("sp_proposituras.zip"))
        keys = sorted(b["bill_key"] for b in got.values())
        # The indicação and the 2019 bill are left out.
        self.assertEqual(keys, ["sp/PEC 1/2026", "sp/PL 640/2026", "sp/PL 641/2026"])
        b = got["1000699001"]
        self.assertEqual(b["presented"], "2026-07-22")
        self.assertEqual(b["url"], "https://www.al.sp.gov.br/propositura/?id=1000699001")

    def test_sp_andamento_latest_and_no_information(self):
        got = S.parse_sp_andamento(fixture("sp_andamento.zip"), {"1000699001", "1000699002"})
        self.assertEqual(got["1000699001"],
                         ("Pauta: Incluído na pauta da Comissão de Educação.", "2026-08-04"))
        # "tramita exclusivamente no Alesp Sem Papel" says nothing of the stage.
        self.assertEqual(got["1000699002"][0], None)

    def test_sp_deputados_reads_name_and_party_only(self):
        got = S.parse_sp_deputados(fixture("sp_deputados.xml"))
        self.assertEqual(got["1000000342"], ("Alex Madureira", "PL"))
        self.assertNotIn("never stored", json.dumps(got))

    def test_mg_list(self):
        got = S.parse_mg_list(fixture("mg_list.html").decode("utf-8"))
        keys = [b["bill_key"] for b in got]
        self.assertEqual(keys[:2], ["mg/PL 6070/2026", "mg/PL 6067/2026"])
        first = got[0]
        self.assertEqual(first["authors"], "Thiago Cota (PDT)")
        self.assertEqual(first["status"], "Aguardando designação de relator em comissão")
        self.assertEqual(first["url"], "https://www.almg.gov.br/projetos-de-lei/PL/6070/2026")
        # PL 6055/2026 has no ementa: ALMG prints its last action there instead.
        last = [b for b in got if b["bill_key"] == "mg/PL 6055/2026"][0]
        self.assertIsNone(last["title"])

    def test_mg_bill_page(self):
        got = S.parse_mg_bill(fixture("mg_bill.html").decode("utf-8"))
        self.assertEqual(got["presented"], "2026-08-14")
        self.assertEqual(got["status"], "Aguardando designação de relator em comissão")
        self.assertEqual(got["local"], "Comissão de Constituição e Justiça")
        self.assertEqual(got["step_date"], "2026-08-14")
        self.assertTrue(got["step"].startswith("Comissão de Constituição e Justiça: Proposição recebida"))

    def test_rj_view(self):
        got = S.parse_rj_view(S.decode(fixture("rj_view.html")))
        self.assertEqual(len(got), 15)
        b = [x for x in got if x["bill_key"] == "rj/PL 8397/2026"][0]
        self.assertEqual(b["presented"], "2026-10-08")     # Notes prints US dates
        self.assertEqual(b["authors"], "RENATO MIRANDA")
        self.assertIn("ACOMPANHANTE", b["title"])
        self.assertIn("Defesa dos Direitos da Mulher", b["committees"])
        self.assertTrue(b["url"].startswith("https://alerjln1.alerj.rj.gov.br/scpro2327.nsf/"))

    def test_sapl_types_pick_bills_and_unique_siglas(self):
        got = S.sapl_types(json.loads(fixture("sapl_tipos.json"))["results"])
        self.assertEqual(got, {"1": ["PLO", "Projeto de Lei Ordinária"],
                               "5": ["PLC", "Projeto de Lei Complementar"],
                               "12": ["PEC", "Proposta de Emenda Constitucional"],
                               "36": ["PEC-36", "Proposta de Emenda a Constitucional da Casa"]})

    def test_sapl_tramitacao_and_vote(self):
        row = json.loads(fixture("sapl_tramitacao.json"))["results"][0]
        self.assertEqual(S.parse_sapl_tramitacao(row),
                         ("Aguardando parecer da Comissão de Constituição e Justiça", "2026-10-08"))
        votes = json.loads(fixture("sapl_votos.json"))["results"]
        v = S.parse_sapl_vote("ro", votes[0], {"57992": "ro/PLO 1542/2026"})
        self.assertEqual((v["yes"], v["no"], v["abstain"], v["result"], v["date"]),
                         (14, 3, 1, "Aprovado", "2026-10-09"))
        self.assertIsNone(S.parse_sapl_vote("ro", votes[1], {"57992": "ro/PLO 1542/2026"}))


class Collect(unittest.TestCase):
    def run_sources(self, conn, sources, client=None, budget=600):
        client = client or FakeClient()
        return S.run(conn, sources, tax(), TODAY, drain.Budget(budget), lambda: client,
                     now=TODAY + "T10:00:00", workers=1), client

    def test_sp_bills_stage_and_committee_votes(self):
        conn = store()
        (_res, gaps), _c = self.run_sources(conn, ["sp"])
        self.assertEqual(gaps, 0)
        b = conn.execute("SELECT * FROM brs_bills WHERE bill_key='sp/PL 640/2026'").fetchone()
        self.assertEqual(json.loads(b["areas"]), [5])
        self.assertEqual(b["authors"], "Alex Madureira (PL); Fabiana Bolsonaro (PL)")
        self.assertEqual(b["status_date"], "2026-08-04")
        v = conn.execute("SELECT * FROM brs_votes").fetchall()
        # Only the bill on our ground keeps its vote.
        self.assertEqual(len(v), 1)
        self.assertEqual((v[0]["yes"], v[0]["no"], v[0]["result"], v[0]["body"]),
                         (2, 1, "APROVADO", "Comissão de Educação e Cultura"))
        pos = conn.execute("SELECT member, party, position FROM brs_positions ORDER BY member").fetchall()
        self.assertEqual([tuple(p) for p in pos][2], ("Luiz Claudio Marcolino", "PT",
                                                      "Contrário ao voto do relator"))
        meta = brs_store.read_meta(conn, "sp")
        self.assertEqual(meta["last_meeting"], "2026-08-04")
        # A second run with no newer meeting does not download the votes again.
        (_res, _g), client = self.run_sources(conn, ["sp"])
        self.assertFalse(any("votacoes" in u for u in client.urls))

    def test_mg_reads_detail_only_for_our_ground(self):
        conn = store()
        (_res, gaps), client = self.run_sources(conn, ["mg"])
        details = [u for u in client.urls if "/projetos-de-lei/PL/" in u and "pesquisou" not in u]
        self.assertEqual(details, ["https://www.almg.gov.br/projetos-de-lei/PL/6070/2026"])
        b = conn.execute("SELECT * FROM brs_bills WHERE bill_key='mg/PL 6070/2026'").fetchone()
        self.assertEqual(json.loads(b["areas"]), [5])
        self.assertEqual(b["presented"], "2026-08-14")
        self.assertEqual(b["seed"], 1)
        self.assertEqual(conn.execute("SELECT party FROM brs_members WHERE name='Thiago Cota'")
                         .fetchone()[0], "PDT")

    def test_mg_revisits_older_bill_on_our_ground(self):
        conn = store()
        b = {"bill_key": "mg/PL 1200/2024", "uf": "mg", "source": "mg", "title": "Escola sem Partido",
             "status": "Aguardando parecer"}
        brs_store.upsert_bill(conn, b, [6], [], 1, "2026-09-01", False)
        conn.commit()
        (_res, _g), client = self.run_sources(conn, ["mg"])
        self.assertIn("https://www.almg.gov.br/projetos-de-lei/PL/1200/2024", client.urls)
        r = conn.execute("SELECT * FROM brs_bills WHERE bill_key='mg/PL 1200/2024'").fetchone()
        self.assertEqual(r["status"], "Aguardando designação de relator em comissão")
        self.assertEqual(r["status_date"], "2026-08-14")
        self.assertEqual(json.loads(r["areas"]), [6])
        self.assertEqual(r["title"], "Escola sem Partido")

    def test_sapl_house(self):
        conn = store()
        (_res, gaps), client = self.run_sources(conn, ["sapl:ro"])
        self.assertEqual(gaps, 0)
        keys = [r[0] for r in conn.execute("SELECT bill_key FROM brs_bills ORDER BY bill_key")]
        self.assertEqual(keys, ["ro/PEC-36 2/2026", "ro/PLO 1541/2026", "ro/PLO 1542/2026"])
        b = conn.execute("SELECT * FROM brs_bills WHERE bill_key='ro/PLO 1542/2026'").fetchone()
        self.assertEqual(json.loads(b["areas"]), [1])
        self.assertEqual(b["status"], "Aguardando parecer da Comissão de Constituição e Justiça")
        self.assertEqual(b["authors"], "Fulano de Tal")
        # The tramitação and the autor are read for the bill on our ground only.
        self.assertEqual(sum("materia/tramitacao" in u for u in client.urls), 1)
        self.assertEqual(sum("base/autor" in u for u in client.urls), 1)
        q = [u for u in client.urls if "/materia/materialegislativa/?" in u][0]
        self.assertIn("tipo__in=1,5,12,36", q)
        self.assertIn("data_ultima_atualizacao__gte=2026-09-10", q)
        v = conn.execute("SELECT * FROM brs_votes").fetchall()
        self.assertEqual([r["vote_key"] for r in v], ["ro/v16770"])
        meta = brs_store.read_meta(conn, "sapl:ro")
        self.assertEqual(meta["last_read"], TODAY)
        # The editor's IP the API returns is never stored.
        self.assertNotIn("45.190.142.123", json.dumps([dict(r) for r in conn.execute(
            "SELECT * FROM brs_bills")]))

    def test_sapl_types_cached(self):
        conn = store()
        self.run_sources(conn, ["sapl:ro"])
        (_res, _g), client = self.run_sources(conn, ["sapl:ro"])
        self.assertFalse(any("tipomaterialegislativa" in u for u in client.urls))
        q = [u for u in client.urls if "/materia/materialegislativa/?" in u][0]
        self.assertIn("data_ultima_atualizacao__gte=2026-10-08", q)

    def test_unreachable_source_is_a_gap_not_a_failure(self):
        conn = store()
        (_res, gaps), _c = self.run_sources(conn, ["rj", "sapl:to"],
                                            client=FakeClient(fail=("alerjln1", "sapl.al.to")))
        self.assertEqual(gaps, 2)
        reads = {r["source"]: r["status"] for r in conn.execute("SELECT * FROM brs_reads")}
        self.assertEqual(reads, {"rj": "unreachable", "sapl:to": "unreachable"})
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='br-states'").fetchone()[0], 2)

    def test_status_change_dated_the_day_seen(self):
        conn = store()
        b = {"bill_key": "mg/PL 1/2026", "uf": "mg", "source": "mg", "status": "A"}
        brs_store.upsert_bill(conn, b, [5], [], 1, "2026-10-01", True)
        self.assertIsNone(conn.execute("SELECT status_date FROM brs_bills").fetchone()[0])
        brs_store.upsert_bill(conn, dict(b, status="B"), [5], [], 1, "2026-10-08", False)
        self.assertEqual(conn.execute("SELECT status_date FROM brs_bills").fetchone()[0], "2026-10-08")
        brs_store.upsert_bill(conn, dict(b, status="B"), [5], [], 1, "2026-10-15", False)
        self.assertEqual(conn.execute("SELECT status_date FROM brs_bills").fetchone()[0], "2026-10-08")

    def test_reclassify_offline(self):
        conn = store()
        self.run_sources(conn, ["sapl:ro"])
        conn.execute("UPDATE brs_bills SET areas=NULL")
        n, ours = S.reclassify(conn, tax())
        self.assertEqual((n, ours), (3, 1))


class Edition(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        client = FakeClient()
        S.run(self.conn, ["sp", "sapl:ro"], tax(), TODAY, drain.Budget(600), lambda: client,
              now=TODAY + "T10:00:00", workers=1)

    def test_items(self):
        got = brs_edition.items(self.conn, "2026-10-03", "2026-10-10", wl={})
        kinds = sorted((it["kind"], it["key"]) for it in got)
        self.assertEqual(kinds, [("new", "ro/PLO 1542/2026"), ("vote", "ro/v16770")])
        got = brs_edition.items(self.conn, "2026-07-20", "2026-08-10", wl={})
        kinds = sorted((it["kind"], it["key"]) for it in got)
        # ALESP's bill is new on 22 July and its committee vote is on 4 August.
        self.assertEqual(kinds, [("new", "sp/PL 640/2026"),
                                 ("vote", "sp/c1000007752/1000699001")])
        vote = [it for it in got if it["kind"] == "vote"][0]
        text = "\n".join(vote["lines"])
        self.assertIn("2 for, 1 against", text)
        self.assertIn("Against: Luiz Claudio Marcolino", text)

    def test_section_and_post_render(self):
        country = ce.adapter("br")
        text = "# Brazil\n\ncovering 4 October 2026 to 10 October 2026\n\n## Watchlist\n\n- x\n"
        out = brs_edition.post_render(self.conn, country, TODAY, text)
        self.assertIn("## State assemblies", out)
        self.assertLess(out.index("## State assemblies"), out.index("## Watchlist"))
        self.assertIn("ro/PLO 1542/2026", out)
        self.assertIn("Read cleanly (2 of 27", out)
        self.assertIn("ALEP (bill search and votes behind reCAPTCHA)", out)
        self.assertNotIn("—", out)

    def test_quiet_section(self):
        country = ce.adapter("br")
        out = "\n".join(brs_edition.section(self.conn, country, "2026-01-01", "2026-01-08"))
        self.assertIn("Nothing on our ground in the state assemblies read this week.", out)

    def test_dm_notice(self):
        self.assertIsNone(brs_edition.notice(self.conn, TODAY, dm=False))


if __name__ == "__main__":
    unittest.main()
