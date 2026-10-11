"""Length of service for the new countries (src/member_service.py,
tools/member_service.py): the parsers on trimmed real replies
(tests/fixtures/member_service/) and small dicts, what a profile and a vote
page may say, and the X5 / X6 corrections. No network."""
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import at_store, member_service as ms, noise, pt_store  # noqa: E402
from src import member_profiles as mp  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "member_service")
TODAY = "2026-10-11"


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def svc_of(periods, spells=()):
    s = ms.Service()
    s.periods, s.spells, s.sources = list(periods), list(spells), {"x"}
    return s


class Parsers(unittest.TestCase):
    def test_iso_reads_every_form_the_sources_use(self):
        self.assertEqual(ms.iso("/Date(-822787200000)/"), "1943-12-06")
        self.assertEqual(ms.iso("21/05/2019"), "2019-05-21")
        self.assertEqual(ms.iso("24.05.2019"), "2019-05-24")
        self.assertEqual(ms.iso("20180309"), "2018-03-09")
        self.assertEqual(ms.iso("2023-02-01T12:05"), "2023-02-01")
        self.assertIsNone(ms.iso(""))

    def test_austria_biography_gives_both_nationalrat_periods_and_skips_the_ministry(self):
        periods, spells = ms.parse_at_person("35520", fixture("at-person-35520.json"))
        got = sorted((p["chamber"], p["start"], p["end"], p["grp"]) for p in periods)
        self.assertEqual(got, [("NR", "2006-10-30", "2017-12-18", "Freiheitlicher Parlamentsklub"),
                               ("NR", "2019-05-24", None, "Freiheitlicher Parlamentsklub")])
        self.assertEqual(periods[0]["name"], "Kickl Herbert")
        self.assertEqual({s["kind"] for s in spells}, {"group"})
        rs = ms.runs(periods)
        self.assertEqual([(r[1], r[2]) for r in rs], [("2006-10-30", "2017-12-18"),
                                                      ("2019-05-24", None)])

    def test_austria_klub_names_map_to_the_vote_label_by_the_sitting_members(self):
        spells = [ms.spell("1", "1", None, "group", "Freiheitlicher Parlamentsklub", None,
                           "2019-05-24", None),
                  ms.spell("2", "2", None, "group", "Freiheitlicher Parlamentsklub", None,
                           "2024-10-24", None),
                  ms.spell("3", "3", None, "group", "Team Stronach", None, "2013-10-29",
                           "2017-11-08")]
        self.assertEqual(ms.at_klub_map(spells, {"1": "FPÖ", "2": "FPÖ", "3": "ÖVP"}),
                         {"Freiheitlicher Parlamentsklub": "FPÖ"})

    def test_portugal_only_effective_situations_are_seats(self):
        periods, spells = ms.parse_pt_base(fixture("pt-informacaobase-XVI.json"))
        by = {p["member_key"]: p for p in periods}
        self.assertEqual((by["2071"]["start"], by["2071"]["end"], by["2071"]["grp"]),
                         ("2024-04-05", "2025-06-02", "PSD"))
        self.assertEqual(by["8788"]["start"], "2025-02-13")     # a substitute until then
        self.assertEqual({s["party"] for s in spells}, {"PSD"})
        self.assertEqual(len(periods), 2)

    def test_switzerland_history_rows(self):
        rows = [{"PersonNumber": 4075, "FirstName": "Andrea", "LastName": "Caroni",
                 "CouncilAbbreviation": "NR", "DateJoining": "/Date(1323043200000)/",
                 "DateLeaving": "/Date(1448755200000)/", "PartyAbbreviation": "FDP-Liberale",
                 "ParlGroupAbbreviation": "RL", "CantonAbbreviation": "AR"},
                {"PersonNumber": 4075, "FirstName": "Andrea", "LastName": "Caroni",
                 "CouncilAbbreviation": "SR", "DateJoining": "/Date(1448841600000)/",
                 "DateLeaving": None, "PartyAbbreviation": "FDP-Liberale",
                 "ParlGroupAbbreviation": "RL", "CantonAbbreviation": "AR"},
                {"PersonNumber": 9, "CouncilAbbreviation": "BR"}]
        periods, spells = ms.parse_ch_history(rows, keep={"4075"})
        self.assertEqual([(p["chamber"], p["start"], p["end"]) for p in periods],
                         [("NR", "2011-12-05", "2015-11-29"), ("SR", "2015-11-30", None)])
        s = svc_of(periods, spells)
        got = ms.summary("ch", s, {"x": {"covers": "since 1848"}}, TODAY)
        self.assertEqual((got["since"], got["since_chamber"]), ("2015-11-30", "SR"))
        self.assertFalse(got["at_least"])
        self.assertEqual(got["earlier"][0]["start"], "2011-12-05")

    def test_netherlands_seats_join_and_keep_the_fractie_id(self):
        rows = [{"Persoon_Id": "p1", "Van": "2017-03-23T00:00:00+01:00",
                 "TotEnMet": "2021-03-30T00:00:00+02:00", "Verwijderd": False,
                 "FractieZetel": {"Fractie": {"Id": "f-a", "Afkorting": "A"}}},
                {"Persoon_Id": "p1", "Van": "2021-03-31T00:00:00+02:00", "TotEnMet": None,
                 "Verwijderd": False, "FractieZetel": {"Fractie": {"Id": "f-b", "Afkorting": "B"}}},
                {"Persoon_Id": "p2", "Van": "2020-01-01", "Verwijderd": True}]
        periods, spells = ms.parse_nl_seats(rows)
        self.assertEqual([(p["start"], p["end"], p["grp"]) for p in periods],
                         [("2017-03-23", None, "A / B")])
        self.assertEqual(ms.party_on(spells, "2021-01-05")["party_ref"], "f-a")
        self.assertEqual(ms.party_on(spells, "2026-01-05")["party"], "B")

    def test_france_takes_the_seat_on_prise_de_fonction(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("json/organe/PO1.json", json.dumps(
                {"organe": {"uid": "PO1", "libelleAbrege": "EPR", "codeType": "GP"}}))
            z.writestr("json/acteur/PA1.json", json.dumps({"acteur": {
                "uid": {"#text": "PA1"}, "etatCivil": {"ident": {"prenom": "Olga", "nom": "G"}},
                "mandats": {"mandat": [
                    {"typeOrgane": "ASSEMBLEE", "legislature": "17", "dateDebut": "2024-07-07",
                     "dateFin": "2024-10-21", "mandature": {"datePriseFonction": "2024-07-08"},
                     "election": {"lieu": {"departement": "Ain", "numCirco": "3"}}},
                    {"typeOrgane": "ASSEMBLEE", "legislature": "17", "dateDebut": "2024-07-07",
                     "dateFin": None, "mandature": {"datePriseFonction": "2025-01-24"}},
                    {"typeOrgane": "GP", "dateDebut": "2025-01-25", "dateFin": None,
                     "organes": {"organeRef": "PO1"}}]}}}))
        periods, spells = ms.parse_fr_amo30(buf.getvalue())
        self.assertEqual([(p["start"], p["end"]) for p in periods],
                         [("2024-07-08", "2024-10-21"), ("2025-01-24", None)])
        self.assertEqual(periods[0]["seat"], "Ain, circonscription 3")
        self.assertEqual((spells[0]["party"], spells[0]["party_ref"]), ("EPR", "PO1"))
        self.assertEqual(ms.fr_first_day(buf.getvalue()), "2024-07-08")
        got = ms.summary("fr", svc_of(periods, spells), {}, TODAY)
        self.assertEqual(got["since"], "2025-01-24")          # the ministerial gap breaks the run
        self.assertEqual(len(got["earlier"]), 1)

    def test_italy_camera_rows_dedupe_and_strip_the_dates_from_group_labels(self):
        b = {"d": "http://dati.camera.it/ocd/deputato.rdf/d307122_18", "first": "MARIA LAURA",
             "surname": "PAXIA", "ms": "20180309", "me": "20221012", "gs": "20210219",
             "ge": "20221012", "glabel": "MISTO (19.02.2021-12.10.2022)"}
        periods, spells, names = ms.parse_it_camera([b, dict(b)], 18)
        self.assertEqual(len(periods), 1)
        self.assertEqual((periods[0]["member_ref"], periods[0]["start"]), ("307122", "2018-03-09"))
        self.assertEqual(spells[0]["party"], "MISTO")
        self.assertEqual(names["307122"], "MARIA LAURA PAXIA")
        self.assertEqual(ms.parse_it_camera([b], 18, keep_refs={"1"})[0], [])

    def test_spain_reads_seats_and_groups_never_the_biography(self):
        rec = {"NOMBRE": "Ábalos Meco, José Luis", "CIRCUNSCRIPCION": "Valencia/València",
               "FORMACIONELECTORAL": "PSOE", "FECHAALTA": "08/05/2019", "FECHABAJA": "24/09/2019",
               "GRUPOPARLAMENTARIO": "Grupo Parlamentario Socialista",
               "FECHAALTAENGRUPOPARLAMENTARIO": "23/05/2019",
               "FECHABAJAENGRUPOPARLAMENTARIO": "24/09/2019", "BIOGRAFIA": "Casado..."}
        periods, spells = ms.parse_es_file([rec], 13)
        self.assertEqual((periods[0]["start"], periods[0]["end"], periods[0]["term"]),
                         ("2019-05-08", "2019-09-24", "13"))
        self.assertNotIn("Casado", json.dumps(periods + spells))
        page = ('<a href="/webpublica/opendata/diputados/odsDiputados13__2026.json">'
                '<a href="/webpublica/opendata/diputados/DiputadosActivos__2026.json">'
                '<a href="/webpublica/opendata/diputados/Diput__2026.json">')
        self.assertEqual([leg for _p, leg in ms.es_files(page, 15)], [13, 15])

    def test_poland_links_terms_by_name_and_birth_date_and_never_stores_the_date(self):
        terms = [{"num": 9, "from": "2019-11-12", "to": "2023-11-12"},
                 {"num": 10, "from": "2023-11-13", "current": True}]
        anna = {"firstLastName": "Anna Nowak", "birthDate": "1970-01-01", "club": "KO",
                "active": True, "oathDate": "2023-11-13", "id": 5}
        by_term = {9: [dict(anna, id=77, club="PO", oathDate="2019-11-12")],
                   10: [anna, {"firstLastName": "Anna Nowak", "birthDate": "1980-02-02",
                               "active": True, "oathDate": "2023-11-13", "id": 6}]}
        periods = ms.parse_pl_terms(terms, by_term, 10)
        mine = [p for p in periods if p["member_key"] == "10/5"]
        self.assertEqual([(p["term"], p["start"], p["end"], p["grp"]) for p in mine],
                         [("9", "2019-11-12", "2023-11-12", "PO"), ("10", "2023-11-13", None, "KO")])
        self.assertNotIn("1970-01-01", json.dumps(periods))

    def test_brazil_status_history_entries_and_exits(self):
        reply = {"dados": [
            {"id": 1, "nome": "X", "siglaPartido": "PSDB", "idLegislatura": 56,
             "dataHora": "2019-02-01T11:45", "descricaoStatus": "Entrada - Posse de Eleito Titular"},
            {"id": 1, "nome": "X", "siglaPartido": "PSDB", "idLegislatura": 56,
             "dataHora": "2023-01-31T23:59", "descricaoStatus": "Saída - Afastamento definitivo"},
            {"id": 1, "nome": "X", "siglaPartido": "PSDB", "idLegislatura": 57,
             "dataHora": "2023-02-01T00:00", "descricaoStatus": "Nome no início da legislatura"},
            {"id": 1, "nome": "X", "siglaPartido": "PSDB", "idLegislatura": 57,
             "dataHora": "2023-02-01T12:05", "descricaoStatus": "Entrada - Posse"},
            {"id": 1, "nome": "X", "siglaPartido": "PSDB", "idLegislatura": 58,
             "dataHora": "2027-02-01T12:05", "descricaoStatus": "Entrada - Posse"}]}
        periods = ms.parse_br_historico("camara-1", reply, TODAY)
        self.assertEqual([(p["start"], p["end"]) for p in periods],
                         [("2019-02-01", "2023-01-31"), ("2023-02-01", None)])
        got = ms.summary("br", svc_of(periods), {}, TODAY)
        self.assertEqual(got["since"], "2019-02-01")          # the two abut: one run

    def test_brazil_senate_mandates(self):
        reply = {"MandatoParlamentar": {"Parlamentar": {"Codigo": "5672", "Nome": "Alan Rick",
                 "Mandatos": {"Mandato": [{"UfParlamentar": "AC",
                     "PrimeiraLegislaturaDoMandato": {"NumeroLegislatura": "57"},
                     "SegundaLegislaturaDoMandato": {"NumeroLegislatura": "58"},
                     "Exercicios": {"Exercicio": [{"DataInicio": "2023-02-01"}]},
                     "Partidos": {"Partido": [
                         {"Sigla": "REPUBLICANOS", "DataFiliacao": "2025-11-12"},
                         {"Sigla": "UNIÃO", "DataFiliacao": "2022-02-24",
                          "DataDesfiliacao": "2025-11-10"}]}}]}}}}
        periods, spells = ms.parse_br_mandatos("senado-5672", reply)
        self.assertEqual((periods[0]["start"], periods[0]["term"]), ("2023-02-01", "57-58"))
        self.assertEqual(ms.party_on(spells, "2024-01-01", "party")["party"], "UNIÃO")

    def test_slovakia_terms_are_term_precision(self):
        rows = [{"mpId": 226, "name": "Abrhan, Pavol", "lastClubAbbr": "KDH",
                 "partyDepartmentName": "KDH"}]
        p = ms.parse_sk_term(rows, 6)[0]
        self.assertEqual((p["precision"], p["start"], p["term"]), ("term", None, "6"))
        got = ms.summary("sk", svc_of([p]), {}, TODAY)
        self.assertIsNone(got["since"])
        self.assertEqual(got["terms"][0]["term"], "6")


class WhatMayBeSaid(unittest.TestCase):
    def test_at_least_only_when_the_run_starts_on_the_sources_first_day(self):
        p = ms.period("1", "1", None, "TK", None, "2008-01-01", None)
        covers = {"x": {"covers": "seats", "covers_from": "2008-01-01"}}
        got = ms.summary("nl", svc_of([p]), covers, TODAY)
        self.assertTrue(got["at_least"])
        line = ms.lines("nl", svc_of([p]), covers, TODAY)[0]
        self.assertIn("at least 1 January 2008", line)
        covers["x"]["covers_from"] = None
        self.assertFalse(ms.summary("nl", svc_of([p]), covers, TODAY)["at_least"])

    def test_a_member_who_left_has_no_serving_since(self):
        p = ms.period("1", "1", None, "NR", None, "2007-12-03", "2025-09-19")
        got = ms.lines("ch", svc_of([p]), {}, TODAY)
        self.assertTrue(got[0].startswith("**Last period ended:** 19 September 2025"))
        self.assertFalse(any("Serving since" in g for g in got))
        # the roster says they left even though the source's period is open: no "since"
        q = ms.period("1", "1", None, "NR", None, "2007-12-03", None)
        self.assertIsNone(ms.summary("ch", svc_of([q]), {}, TODAY, current=False)["since"])

    def test_every_service_block_says_what_the_source_covers(self):
        p = ms.period("1", "1", None, "Sabor", "11", None, None, "term")
        got = ms.lines("hr", svc_of([p]), {"x": {"covers": "the 10th and 11th sazivi only"}},
                       TODAY)
        self.assertIn("Terms in the source", got[0])
        self.assertIn("the 10th and 11th sazivi only", got[-1])
        self.assertIn("nothing here says whether this is a first term", got[-1])

    def test_merged_spells_join_abutting_spells_of_one_group(self):
        spells = [ms.spell("1", None, None, "group", "V", None, "2007-12-03", "2011-12-04"),
                  ms.spell("1", None, None, "group", "V", None, "2011-12-05", None)]
        self.assertEqual(ms.merged_spells(spells), [("V", "2007-12-03", None)])


def at_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    at_store.ensure_schema(conn)
    ms.ensure(conn)
    conn.executemany("INSERT INTO at_members (pad, name, chamber, klub) VALUES (?,?,?,?)",
                     [("1", "Auer Katrin", "NR", "SPÖ"), ("2", "Berger Ricarda", "NR", "FPÖ"),
                      ("3", "Neu Nina", "NR", "SPÖ")])
    conn.execute("INSERT INTO at_items (item_key, gp, chamber, art, title, areas, tier, "
                 "introduced) VALUES ('XXVIII/I/525', 'XXVIII', 'NR', 'RV', "
                 "'Sterbeverfügungsgesetz-Novelle 2026', '[2]', 1, '2026-06-01')")
    conn.execute("INSERT INTO at_divisions (division_key, item_key, date, body, question, "
                 "outcome, unanimous, roll_call, areas) VALUES ('d1', 'XXVIII/I/525', "
                 "'2026-07-07', 'NR', 'Gesetzesvorschlag in dritter Lesung', 'angenommen', 0, 0, "
                 "'[2]')")
    conn.executemany("INSERT INTO at_votes (division_key, klub, position) VALUES (?,?,?)",
                     [("d1", "SPÖ", "Dafür"), ("d1", "FPÖ", "Dagegen")])
    return conn


def at_service(conn):
    """Auer sat since 2019 (SPÖ); Berger sat in the SPÖ Klub until 1 July 2026
    and has sat in the FPÖ's since; Neu took her seat on 1 September 2026."""
    full = {"SPÖ": "Die Sozialdemokratische Parlamentsfraktion", "FPÖ": "Freiheitlicher Parlamentsklub"}
    periods = [ms.period("1", "1", None, "NR", None, "2019-10-23", None),
               ms.period("2", "2", None, "NR", None, "2024-10-24", None),
               ms.period("3", "3", None, "NR", None, "2026-09-01", None)]
    spells = [ms.spell("1", "1", None, "group", full["SPÖ"], "SPÖ", "2019-10-23", None),
              ms.spell("2", "2", None, "group", full["SPÖ"], "SPÖ", "2024-10-24", "2026-07-01"),
              ms.spell("2", "2", None, "group", full["FPÖ"], "FPÖ", "2026-07-02", None),
              ms.spell("3", "3", None, "group", full["SPÖ"], "SPÖ", "2026-09-01", None)]
    ms.replace(conn, "at", "at-biografien", TODAY, periods, spells, "every mandate", None)


class DerivedPositions(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        os.makedirs(self.cfg)

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def test_without_service_rows_the_stores_derivation_stands(self):
        conn = at_conn()
        rows = at_store.derived_member_positions(conn, "d1")
        self.assertEqual(ms.adjust_derived(conn, "at", "d1", rows, {}), (rows, 0))
        data = mp.build(conn, "at", TODAY, config_dir=self.cfg)
        # the old claim: Neu, who took her seat in September, "voted" in July
        self.assertEqual(data["members"]["3"].votes[0]["position"], "Dafür")

    def test_a_member_is_given_their_group_on_the_day_and_only_if_they_sat(self):
        conn = at_conn()
        at_service(conn)
        services = ms.by_store_key(ms.load(conn, "at"))
        rows, dropped = ms.adjust_derived(conn, "at", "d1",
                                          at_store.derived_member_positions(conn, "d1"), services)
        by = {r["member_id"]: r for r in rows}
        self.assertNotIn("3", by)                           # not yet sitting on 7 July
        self.assertEqual(dropped, 1)
        self.assertEqual((by["2"]["party"], by["2"]["position"]), ("FPÖ", "Dagegen"))
        self.assertEqual(by["2"]["basis"], ms.DERIVED_ON_DAY)
        self.assertEqual(by["1"]["position"], "Dafür")

    def test_profiles_and_pages_carry_the_correction_and_the_service_block(self):
        conn = at_conn()
        at_service(conn)
        # Berger was in the SPÖ Klub on a June vote: the store's derivation
        # (today's Klub, FPÖ) said "Dagegen"; the day's Klub says "Dafür".
        conn.execute("INSERT INTO at_divisions (division_key, item_key, date, body, question, "
                     "outcome, unanimous, roll_call, areas) VALUES ('d0', 'XXVIII/I/525', "
                     "'2026-06-10', 'NR', 'Gesetzesvorschlag in zweiter Lesung', 'angenommen', "
                     "0, 0, '[2]')")
        conn.executemany("INSERT INTO at_votes (division_key, klub, position) VALUES (?,?,?)",
                         [("d0", "SPÖ", "Dafür"), ("d0", "FPÖ", "Dagegen")])
        data = mp.build(conn, "at", TODAY, config_dir=self.cfg)
        berger = data["members"]["2"]
        june = [v for v in berger.votes if v["date"].startswith("2026-06")][0]
        self.assertEqual((june["position"], june["party"], june["basis"]),
                         ("Dafür", "SPÖ", mp.DERIVED_DAY))
        self.assertEqual(data["members"]["3"].votes, [])
        self.assertEqual(data["service"]["dropped"], 2)
        text = mp.render_member(data, berger)
        self.assertIn("## Length of service", text)
        self.assertIn("**Serving since:** 24 October 2024", text)
        self.assertIn("SPÖ (group's vote on the day, X5)", text)
        self.assertIn("Group spells, as the source dates them", text)
        index = mp.render_index(data, {"2": "b.md"})
        self.assertIn("| Service |", index)
        self.assertIn("2 position(s) the store's derivation", index)
        from src import country_votes as cv
        page = cv.build(conn, "at", TODAY, config_dir=self.cfg)
        names = {m[0]: m for m in page["members"]}
        self.assertEqual(names["Berger Ricarda"][6], "serving since 24 October 2024")
        self.assertIn("left out", page["service_note"])
        self.assertTrue(page["derived_bases"])

    def test_country5ca_positions_use_the_same_correction(self):
        from src import country5ca as c5
        conn = at_conn()
        at_service(conn)
        got = {p["member_id"]: p for p in c5.positions(conn, "at", "d1")}
        self.assertNotIn("3", got)
        self.assertEqual(got["2"]["party"], "FPÖ")

    def test_portugal_adds_a_deputy_who_sat_then_and_has_since_left(self):
        conn = sqlite3.connect(":memory:")
        pt_store.ensure_schema(conn)
        ms.ensure(conn)
        conn.executemany("INSERT INTO pt_members (cad_id, name, party, situation) VALUES "
                         "(?,?,?,?)", [(1, "Ana", "PS", "Efetivo"), (2, "Rui", "PS", "Renunciou")])
        conn.execute("INSERT INTO pt_divisions (division_key, vote_id, legislature, date) "
                     "VALUES ('XVII/1', 1, 'XVII', '2025-07-01')")
        conn.execute("INSERT INTO pt_group_votes (division_key, party, position, members) "
                     "VALUES ('XVII/1', 'PS', 'Contra', NULL)")
        ms.replace(conn, "pt", "pt-informacaobase", TODAY,
                   [ms.period("1", "1", "Ana", "AR", "XVII", "2025-06-03", None),
                    ms.period("2", "2", "Rui", "AR", "XVII", "2025-06-03", "2026-01-10")],
                   [ms.spell("1", "1", "Ana", "group", "PS", "PS", "2025-06-03", None),
                    ms.spell("2", "2", "Rui", "group", "PS", "PS", "2025-06-03", "2026-01-10")])
        rows, dropped = ms.adjust_derived(conn, "pt", "XVII/1",
                                          pt_store.derived_member_positions(conn, "XVII/1"),
                                          ms.by_store_key(ms.load(conn, "pt")))
        self.assertEqual(sorted(str(r["member_id"]) for r in rows), ["1", "2"])
        self.assertEqual(dropped, 0)


class XSixSpell(unittest.TestCase):
    def test_a_dated_group_spell_beats_the_listed_party(self):
        spec = mp.SPECS["be"]
        m = mp.Member("k", "Ana")
        m.party = "SDP"
        s = svc_of([], [ms.spell("k", None, None, "group", "Možemo!", None, "2024-01-01", None)])
        got = mp.party_of(spec, {"service": {"k": s}}, m, "2025-01-01", None, False)
        self.assertEqual(got, ("Možemo!", mp.SPELL_ON_DAY))
        self.assertEqual(mp.short_basis(mp.SPELL_ON_DAY), "on the day, dated spells")
        # without a spell on the day: as listed, as before
        got = mp.party_of(spec, {"service": {"k": s}, "history": {}}, m, "2023-01-01", None,
                          False)
        self.assertEqual(got[1], spec.listed_label)


class Tool(unittest.TestCase):
    def test_cadence_and_a_store_only_country(self):
        tmp = tempfile.mkdtemp()
        try:
            db = os.path.join(tmp, "s.db")
            conn = sqlite3.connect(db)
            from src import hu_store
            hu_store.ensure_schema(conn)
            conn.execute("INSERT INTO hu_members (member_id, name, faction, current, mandate_from, "
                         "source) VALUES ('a011', 'Ágh Péter', 'Fidesz', 1, '2026-05-09', 'karzat')")
            conn.commit()
            conn.close()
            from tools import member_service as tool
            self.assertEqual(tool.main(["hu", "--db", db, "--raw", tmp, "--date", TODAY]), 0)
            conn = sqlite3.connect(db)
            self.assertEqual(conn.execute("SELECT start, precision FROM ms_periods").fetchone(),
                             ("2026-05-09", "day"))
            self.assertFalse(ms.due(conn, "hu", "2026-10-12"))
            self.assertTrue(ms.due(conn, "hu", "2026-10-18"))
            self.assertTrue(ms.due(conn, "fr", TODAY))
            conn.close()
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
