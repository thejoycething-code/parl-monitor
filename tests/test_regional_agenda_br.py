"""Brazil's state assemblies' forward agendas (src/regional_agendas/br.py).
Fixtures are live replies of 16 October 2026, trimmed (the ALMG guests'
names and CPF numbers removed); PDFs are kept as the text pypdf extracts.
No network."""
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import br  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402

TODAY = "2026-10-16"
CTX = ra.Ctx(TODAY, "2026-12-11")
PAST = ra.Ctx("2026-10-01", "2026-12-11")      # for captures of sittings already held


def fx(name):
    return load_fixture("br", name)


def fj(name):
    return json.loads(fx(name))


def sp_pages(ctx=CTX, meetings="sp_reunioes_empty.json"):
    q = "page=0&size=100&dataInicial={0}&dataFinal={1}".format(ctx.today, ctx.until)
    q2 = "page=0&size=100&dataInicio={0}&dataFim={1}".format(ctx.today, ctx.until)
    return {br.SP_API + "/sessoes-plenarias/consulta?" + q: fx("sp_sessoes.json"),
            br.SP_API + "/sessoes-plenarias/24178/pauta": fx("sp_pauta_24178.json"),
            br.SP_API + "/colegiado/reunioes?" + q2: fx(meetings)}


class SaoPauloTest(unittest.TestCase):
    def test_pauta_for_amendments(self):
        sess = {"id": 24178, "dtInicio": "2026-10-16T14:00"}
        items = br.sp_session_items(sess, fj("sp_pauta_24178.json"), CTX, "pauta")
        self.assertEqual(len(items), 12)
        first = items[0]
        self.assertEqual(first["reference"], "PL 875/2026")
        self.assertTrue(first["business"].startswith("PL 875/2026: Institui o Estatuto Paulista "
                                                     "de Defesa da Vida desde a concepção"))
        self.assertIn("Pauta para emendas e recursos", first["detail"])
        self.assertIn("Autoria: Carla Morando", first["detail"])
        self.assertEqual((first["dated"], first["item_time"], first["body"]),
                         ("2026-10-16", "14:00", "Plenário"))

    def test_ordem_do_dia(self):
        sess = {"id": 24176, "dtInicio": "2026-10-14T14:03"}
        items = br.sp_session_items(sess, fj("sp_ordem_24176.json"), PAST, "ordem-do-dia")
        self.assertEqual([i["reference"] for i in items[:2]], ["PLC 31/2017", "PLC 4/2019"])
        self.assertIn("Regime de Urgência", items[0]["detail"])
        self.assertIn("Votação adiada", items[0]["detail"])
        self.assertEqual(items[0]["item_type"], None)       # typed by the store

    def test_solemn_session_and_tba(self):
        s = fj("sp_sessoes.json")["content"]
        solemn = br.sp_session_slot(s[0])
        self.assertTrue(solemn["business"].startswith("Sessão Solene: OUTORGA DE COLAR"))
        ordinary = dict(s[3], temPauta=False)
        self.assertEqual(br.sp_session_slot(ordinary)["business"], "")

    def test_committee_pauta(self):
        meet = fj("sp_reunioes_past.json")["content"][0]
        items = br.sp_meeting_items(meet, fj("sp_reuniao_pauta.json"))
        self.assertEqual(items[0]["body"], "Comissão de Constituição, Justiça e Redação")
        self.assertEqual(items[0]["reference"], "PR 5/2026")
        self.assertEqual(len(items), 3)
        empty = br.sp_meeting_items(meet, {"content": []})
        self.assertEqual([i["business"] for i in empty], [""])

    def test_read_sp_end_to_end(self):
        client = FakeClient(sp_pages())
        conn = store()
        s = ra.collect(conn, "br", client, TODAY, regions=["sp"], log=lambda *a: None)
        self.assertEqual(s["read"], ["sp"])
        rows = conn.execute("SELECT business, item_type, areas FROM regional_agenda").fetchall()
        # 12 pauta items + three solemn sessions.
        self.assertEqual(len(rows), 15)
        estatuto = [r for r in rows if "Estatuto Paulista" in r[0]]
        self.assertEqual(len(estatuto), 1)
        self.assertNotEqual(estatuto[0][2], "[]")          # on our ground (vida desde a concepção)


class MinasGeraisTest(unittest.TestCase):
    def meetings(self):
        res = fj("mg_comissoes.json")["resultadoPesquisa"]
        return next(v for v in res.values() if isinstance(v, list))

    def test_committee_meetings(self):
        got = [br.mg_committee_items(m)[0] for m in self.meetings()]
        self.assertEqual([g["dated"] for g in got],
                         ["2026-10-20", "2026-10-26", "2026-10-27", "2026-10-28"])
        self.assertEqual(got[0]["business"], "")             # booked, nothing on it
        self.assertEqual(got[1]["body"], "Comissão de Educação, Ciência e Tecnologia")
        self.assertTrue(got[1]["business"].startswith("Audiência pública: Debater os impactos"))
        self.assertEqual(got[1]["reference"], "RQC 23306/2026")
        self.assertEqual(got[1]["item_type"], "committee evidence")

    def test_plenary_ordem_do_dia(self):
        items, mid = br.mg_plenary_items(fj("mg_detalhes.json"), "2026-10-14", "14:00")
        self.assertEqual(mid, "mg-plenario-8584")
        self.assertEqual([i["reference"] for i in items], ["VET 35/2026", "PL 873/2023",
                                                           "PL 3317/2025"])
        self.assertTrue(items[1]["business"].startswith("Projeto de Lei nº 873/2023: Dispõe"))
        self.assertEqual(items[1]["detail"], "Votação - 2º Turno")

    def test_never_pages(self):
        with self.assertRaises(ValueError):
            br.mg_url("comissoes/reunioes/pesquisa", formato="json", p=2)

    def test_read_mg_splits_a_full_page(self):
        full = fj("mg_comissoes.json")
        full["resultadoPesquisa"]["numeroOcorrencias"] = 25     # more than a page of 20
        empty = {"resultadoPesquisa": {"tamanhoPagina": 20, "numeroOcorrencias": 0,
                                       "listaReuniao": []}}
        asked = []

        class Client(FakeClient):
            def get_json(self, url, feed, slug, **kw):
                asked.append(url)
                if "comissoes" in url:
                    return full if "ini=20261016&fim=20261211" in url else empty
                return json.loads(fx("mg_plenario_empty.json"))
        read = br.read_mg(Client({}), CTX)
        self.assertGreater(len([u for u in asked if "comissoes" in u]), 1)
        self.assertFalse(any("&p=" in u or "?p=" in u for u in asked))
        self.assertEqual(read.items, [])


class RioTest(unittest.TestCase):
    def test_calendar(self):
        self.assertEqual(br.parse_rj_calendar(fx("rj_calendario.html")),
                         (2026, 10, [1, 6, 7, 8, 13, 14, 15]))

    def test_pauta(self):
        items = br.parse_rj_pauta(fx("rj_pauta_20261015.html"), "2026-10-15")
        self.assertEqual(len(items), 8)
        self.assertTrue(items[1]["business"].startswith(
            "PROJETO DE LEI Nº 1961/2023: DISPÕE SOBRE A COLETA DE DADOS SOBRE SUICÍDIO"))
        self.assertIn("EM 1ª DISCUSSÃO", items[1]["detail"])
        self.assertEqual(items[0]["order"] if "order" in items[0] else items[0]["item_order"], 1)

    def test_read_rj_no_day_ahead(self):
        client = FakeClient({br.RJ_OD: fx("rj_calendario.html")})
        read = br.read_rj(client, CTX)
        self.assertEqual(read.items, [])
        self.assertEqual(read.units, [ra.window(TODAY, "2026-10-31")])
        read = br.read_rj(FakeClient({
            br.RJ_OD: fx("rj_calendario.html"),
            br.RJ_OD + "pauta/?op=D&data=2026;10;15": fx("rj_pauta_20261015.html")}),
            ra.Ctx("2026-10-15", "2026-12-10"))
        self.assertEqual(len(read.items), 8)


class ParanaTest(unittest.TestCase):
    def test_ordem_pdf(self):
        got = br.parse_pr_pdf(fx("pr_ordem84.txt"))
        self.assertEqual(got[0][0], "2º Turno do Projeto de Lei nº 292/2026")
        self.assertTrue(got[0][1].startswith("Institui a Rota dos Bichos do Norte do Paraná"))
        self.assertIn("Cobra Repórter", got[0][2])
        self.assertTrue(got[0][3].startswith("Parecer favorável"))

    def test_committee_pdfs(self):
        mulher = br.parse_pr_pdf(fx("pr_comissao_mulher.txt"))
        self.assertEqual(mulher[0][0], "Projeto de Lei nº 130/2018")
        self.assertTrue(mulher[0][1].startswith("Dispõe Sobre a Garantia de Matricula"))
        self.assertIn("Maria Victória", mulher[0][2])           # a wrapped author line
        ccj = br.parse_pr_pdf(fx("pr_ccj_suplementar.txt"))
        self.assertEqual(ccj[0][0], "EMENDA DE PLENÁRIO AO PROJETO DE LEI 575/2026")

    def test_lists(self):
        ordem = br.parse_pr_list(fj("pr_ordem.json"), "ordem")
        self.assertEqual((ordem[0]["dated"], ordem[0]["time"]), ("2026-10-13", "14:30"))
        com = br.parse_pr_list(fj("pr_comissoes.json"), "comissoes")
        self.assertTrue(all(c["body"].startswith("Comissão") for c in com))
        self.assertTrue(com[0]["pdfs"])

    def test_read_pr_with_a_pdf(self):
        data = fj("pr_ordem.json")
        first = next(iter(data["data"].values()))[0]
        first["data_sessao"] = "2026-10-20T17:30:00.000000Z"
        pdf = first["arquivos"][0]["url"]
        client = FakeClient({br.PR_PAUTAS + "ordem-do-dia/ajax?page=1": data,
                             br.PR_PAUTAS + "ccj/ajax?page=1": fx("pr_ccj.json"),
                             br.PR_PAUTAS + "comissoes-tematicas/ajax?page=1": fx("pr_comissoes.json"),
                             pdf: b"%PDF"})
        with mock.patch.object(br, "pdf_text", return_value=fx("pr_ordem84.txt")):
            read = br.read_pr(client, CTX)
        self.assertEqual(len(read.items), 5)
        self.assertEqual(read.items[0]["dated"], "2026-10-20")
        self.assertEqual(read.units, [ra.window(TODAY, CTX.until)])


class PernambucoCearaParaTest(unittest.TestCase):
    def test_pe_month(self):
        ev = br.parse_pe_month(fx("pe_agenda_202610.html"))
        self.assertEqual(len(ev), 16)
        aud = [e for e in ev if e["title"] == "Audiência Pública"]
        self.assertEqual(aud[0]["author"], "Comissão de Agricultura, Pecuária e Desenvolvimento Rural")
        self.assertEqual(aud[0]["desc"], "O El Niño e as suas consequências")

    def test_pe_ordem(self):
        self.assertEqual(br.parse_pe_ordem_list(fx("pe_ordem_lista_20261014.html"))[0][:2],
                         ("896", "REUNIAO ORDINÁRIA 77/2026"))
        got = br.parse_pe_ordem(fx("pe_ordem_896.html"))
        self.assertEqual(got[0][0], "Discussão Única da Indicação nº 16692/2026")
        self.assertTrue(got[0][1].startswith("Apelo à Governadora do Estado"))

    def test_read_pe(self):
        pages = {}

        class Client(FakeClient):
            def post_form(self, url, fields, feed, slug, **kw):
                self.asked.append((url, fields.get("field-filter-mes") or fields.get("hiddenData")))
                if url.endswith("/agenda"):
                    return fx("pe_agenda_202610.html") if fields["field-filter-mes"] == "10" else ""
                return "<div class=\"proposicao-list\"></div>"
        client = Client(pages)
        read = br.read_pe(client, CTX)
        bodies = {i["body"] for i in read.items}
        self.assertIn("Comissão de Finanças, Orçamento e Tributação", bodies)
        plen = [i for i in read.items if i["body"] == "Plenário" and not i["business"]]
        self.assertTrue(plen)                                # booked plenaries, no ordem yet
        self.assertEqual(read.units, [ra.window(TODAY, CTX.until)])
        months = [a[1] for a in client.asked if a[0].endswith("/agenda")]
        self.assertEqual(months, ["10", "11", "12"])

    def test_ce(self):
        items = br.ce_items(br.parse_ce_agenda(fx("ce_agenda.html")), CTX)
        self.assertFalse(any("MANUTENÇÃO" in i["business"] for i in items))
        aud = [i for i in items if i["body"].startswith("Comissão")]
        self.assertTrue(aud[0]["business"].startswith("Audiência Pública"))
        self.assertTrue(any(i["body"] == "Plenário" for i in items))

    def test_pa(self):
        rows = br.parse_pa_list(fx("pa_pautas.html"))
        self.assertEqual(rows[0][:2], ("1253", "2026-10-13"))
        got = br.parse_pa_pauta(fx("pa_pauta_1253.html"))
        self.assertEqual(len(got), 6)
        self.assertTrue(got[0][0].startswith("PROJETO DE LEI ORDINÁRIA Nº 217/2025"))
        self.assertEqual(got[0][2], "TURNO ÚNICO")


class SaplTest(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(br.parse_sapl_sessions(fj("sapl_sessoes_empty.json"), CTX), [])
        s = br.parse_sapl_sessions(fj("sapl_pb_sessoes_20260920.json"), PAST)
        self.assertEqual(s[0]["dated"], "2026-10-14")
        self.assertTrue(s[0]["pauta"].startswith("https://sapl.al.pb.leg.br/media/"))
        od, more = br.parse_sapl_ordem(fj("sapl_pb_ordem_1415.json"))
        self.assertTrue(more)
        self.assertEqual(od[0][:2], (1, "Veto nº 390 de 2025"))
        self.assertIn("cargas roubadas", od[0][2])

    def test_houses_read_once_in_parallel(self):
        br._SAPL_CACHE.clear()
        pages = {}
        for uf, host in br.SAPL_HOSTS.items():
            url = ("https://{0}/api/sessao/sessaoplenaria/?data_inicio__gte={1}"
                   "&page_size=100".format(host, PAST.today))
            pages[url] = fx("sapl_pb_sessoes_20260920.json") if uf == "pb" else fx(
                "sapl_sessoes_empty.json")
        del pages["https://sapl.al.am.leg.br/api/sessao/sessaoplenaria/?data_inicio__gte="
                  "2026-10-01&page_size=100"]                     # a dead house
        pages["https://sapl.al.pb.leg.br/api/sessao/ordemdia/?sessao_plenaria=1415&page_size=100"] = \
            fx("sapl_pb_ordem_1415.json")
        client = FakeClient(pages)
        conn = store()
        s = ra.collect(conn, "br", client, PAST.today, days=71,
                       regions=list(br.SAPL_HOSTS), log=lambda *a: None)
        self.assertEqual(s["gap"], ["am"])
        self.assertEqual(sorted(s["read"]), sorted(set(br.SAPL_HOSTS) - {"am"}))
        self.assertEqual(s["per_region"]["pb"]["rows"], 3)
        # Each house's sessions list asked once, though seven regions read.
        sess = [u for u in client.asked if "sessaoplenaria" in u]
        self.assertEqual(len(sess), len(br.SAPL_HOSTS))
        br._SAPL_CACHE.clear()


class FailureTest(unittest.TestCase):
    def test_dead_host_keeps_rows(self):
        conn = store()
        ra.collect(conn, "br", FakeClient(sp_pages()), TODAY, regions=["sp"], log=lambda *a: None)
        before = conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0]
        s = ra.collect(conn, "br", FakeClient({}), TODAY, regions=["sp"], log=lambda *a: None)
        self.assertEqual(s["gap"], ["sp"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], before)

    def test_every_state_declared(self):
        from src import brs_store
        self.assertEqual(set(br.REGIONS), set(brs_store.STATES))
        for code, reg in br.REGIONS.items():
            if reg.reader is None:
                self.assertTrue(reg.note, code)


if __name__ == "__main__":
    unittest.main()
