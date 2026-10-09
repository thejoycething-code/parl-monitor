"""The Brazilian, Argentine and Mexican editions (src/editions/br.py, ar.py,
mx.py; Argentina's post_render and Mexico's fortnightly cadence) on small stores built here, with the
real noise configs (config/edition-noise-{br,ar,mx}.yaml)."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ar_store, br_store, mx_store  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src import noise  # noqa: E402
from src.editions import ar, br, mx  # noqa: E402


def conn_with(store):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    store.ensure_schema(conn)
    return conn


def dumps(v):
    return json.dumps(v, ensure_ascii=False)


class Base(unittest.TestCase):
    CC = None

    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        self.eds = os.path.join(self.tmp, "editions")
        os.makedirs(self.cfg)
        os.makedirs(self.eds)
        for name in ("edition-noise-{0}.yaml".format(self.CC), "taxonomy-pt.yaml",
                     "taxonomy-es.yaml"):
            shutil.copy(os.path.join(ROOT, "config", name), self.cfg)

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def watch(self, text):
        with open(os.path.join(self.cfg, "watchlist-{0}.yaml".format(self.CC)), "w",
                  encoding="utf-8") as fh:
            fh.write(text)


# --- Brazil -----------------------------------------------------------------------

class BrazilTests(Base):
    CC = "br"

    def store(self):
        c = conn_with(br_store)
        c.execute("INSERT INTO br_bills (bill_key, sigla, numero, ano, camara_id, ementa, status, "
                  "areas, matched_terms, tier, former_keys, renamed_on) VALUES "
                  "('PL 1338/2022','PL',1338,2022,534328,'Dispõe sobre a educação domiciliar.',"
                  "'Aguardando Apreciação pelo Senado Federal','[6]',?,1,?,'2026-10-07')",
                  (dumps(["educação domiciliar"]), dumps(["PL 3179/2012"])))
        c.execute("INSERT INTO br_bills (bill_key, sigla, numero, ano, camara_id, ementa, status, "
                  "areas, matched_terms, tier) VALUES ('PL 6461/2019','PL',6461,2019,1,"
                  "'Institui o Estatuto do Aprendiz e dá outras providências.','Pronta para Pauta',"
                  "'[1]',?,2)", (dumps(["gestante*"]),))
        rows = (
            ("camara-1-10", "camara", "2026-10-06", "PLEN",
             "Aprovado o Requerimento de Urgência (Art. 155 do RICD).", "approved", 300, 100,
             "PL 1338/2022"),
            ("camara-1-12", "camara", "2026-10-07", "PLEN",
             "Aprovado o Projeto. Sim: 280; Não: 120.", "approved", 280, 120, "PL 1338/2022"),
            ("camara-1-11", "camara", "2026-10-06", "CCJC",
             "Rejeitado o Requerimento de Retirada de Pauta.", "rejected", 10, 20,
             "PL 4322/2024"),
            ("camara-2-1", "camara", "2026-10-05", "PLEN", "Mantido o texto.", None, 250, 160,
             "PL 6461/2019"),
            ("senado-9", "senado", "2026-10-08", "PLEN", "Votação secreta: autoridade.", "A",
             50, 10, None),
        )
        for k, ch, d, organ, desc, res, y, n, bill in rows:
            areas = "[6]" if bill == "PL 1338/2022" else ("[1]" if bill else "[]")
            c.execute("INSERT INTO br_divisions (division_key, chamber, source_id, date, organ, "
                      "description, result, yes, no, other, secret, bill_key, linked_bills, "
                      "own_areas, areas, tier) VALUES (?,?,?,?,?,?,?,?,?,0,?,?,?,'[]',?,2)",
                      (k, ch, k, d, organ, desc, res, y, n, 1 if ch == "senado" else 0, bill,
                       dumps([bill] if bill else []), areas))
        for i, (party, pos) in enumerate((("PL", "Sim"), ("PL", "Sim"), ("PL", "Não"),
                                          ("PT", "Não"), ("PT", "Não"), ("PT", "Abstenção"))):
            c.execute("INSERT INTO br_members (member_key, chamber, source_id, name) VALUES "
                      "(?, 'camara', ?, ?)", ("camara-{0}".format(i), str(i), "Dep {0}".format(i)))
            c.execute("INSERT INTO br_votes VALUES ('camara-1-12', ?, ?, ?, 'SP')",
                      ("camara-{0}".format(i), pos, party))
        c.execute("INSERT INTO br_orientations VALUES ('camara-1-12', 'Governo', 'Não')")
        c.execute("INSERT INTO br_orientations VALUES ('camara-1-12', 'Oposição', 'Sim')")
        return c

    def render(self, conn, wl='bills:\n  "PL 3179/2012": {areas: [6], why: "Home education."}\n'):
        self.watch(wl)
        return ce.render(conn, br.COUNTRY, "2026-10-09", "2026-10-02", config_dir=self.cfg,
                         directory=self.eds)

    def test_renumbered_bill_shows_both_numbers_and_old_watch_key_matches(self):
        text = self.render(self.store())
        self.assertIn("PL 1338/2022 (formerly PL 3179/2012)", text)
        self.assertIn("## Updated on the register", text)
        self.assertIn("Watched: Home education.", text)
        self.assertIn("activity in this edition: PL 3179/2012", text)

    def test_vote_group_split_orientations_and_takeaway(self):
        text = self.render(self.store())
        self.assertIn("2 recorded votes on one item", text)
        self.assertIn("**Decisive vote**", text)
        self.assertIn("Tally: 280 for, 120 against, 1 abstaining", text)
        self.assertIn("PL 2-1", text)
        self.assertIn("PT 0-2-1", text)
        self.assertIn("Leaders' orientations (as recorded): Governo Não, Oposição Sim.", text)
        self.assertIn("Against their group's majority: Dep 2 (PL)", text)
        self.assertIn("plenary: vote on the bill itself", text)
        self.assertNotIn("—", text)

    def test_noise_procedural_and_excluded_bill(self):
        text = self.render(self.store())
        self.assertNotIn("Retirada de Pauta", text)
        self.assertNotIn("Estatuto do Aprendiz", text)
        self.assertIn("1 procedural vote", text)
        self.assertIn("1 vote on excluded bills only", text)

    def test_areas_14_and_15_have_labels(self):
        self.assertEqual(ce.area_text([14, 15]), "gambling and betting, drug decriminalisation")

    def test_vote_kinds(self):
        self.assertTrue(br.vote_kind("Aprovada, em segundo turno, a PEC").startswith("second-round"))
        self.assertEqual(br.status_english("Transformado em Norma Jurídica"), "became law")
        self.assertTrue(br.FINAL.search("aprovado o projeto"))


class BrazilRenameTests(unittest.TestCase):
    def test_rename_keeps_the_old_number(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import br_rollcalls
        conn = sqlite3.connect(":memory:")
        br_store.ensure_schema(conn)
        conn.execute("INSERT INTO br_bills (bill_key, camara_id) VALUES ('PL 3179/2012', 534328)")
        conn.execute("INSERT INTO br_divisions (division_key, chamber, source_id, bill_key, "
                     "linked_bills) VALUES ('camara-1', 'camara', '1', 'PL 3179/2012', "
                     "'[\"PL 3179/2012\"]')")
        br_rollcalls.store_bill(conn, {"bill_key": "PL 1338/2022", "camara_id": 534328},
                                "2026-10-09", log=lambda *a: None)
        row = conn.execute("SELECT former_keys, renamed_on FROM br_bills WHERE "
                           "bill_key='PL 1338/2022'").fetchone()
        self.assertEqual(json.loads(row[0]), ["PL 3179/2012"])
        self.assertEqual(row[1], "2026-10-09")
        self.assertEqual(conn.execute("SELECT bill_key, linked_bills FROM br_divisions")
                         .fetchone(), ("PL 1338/2022", '["PL 1338/2022"]'))

    def test_schema_adds_columns_to_an_old_store(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE br_bills (bill_key TEXT PRIMARY KEY)")
        br_store.ensure_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(br_bills)")}
        self.assertTrue({"former_keys", "renamed_on"} <= cols)


# --- Argentina --------------------------------------------------------------------

class ArgentinaTests(Base):
    CC = "ar"

    def store(self):
        c = conn_with(ar_store)
        bills = (
            ("dip/4642-D-2026", "LEY", "2026-09-10", None, None, "[9]", 1,
             "CODIGO CIVIL Y COMERCIAL DE LA NACION. MODIFICACIONES SOBRE NULIDAD MATRIMONIAL."),
            ("dip/4502-D-2026", "RESOLUCION", "2026-10-04", None, None, "[8]", 2,
             "CITAR AL SEÑOR MINISTRO DE RELACIONES EXTERIORES, COMERCIO INTERNACIONAL Y CULTO."),
            ("dip/100-D-2025", "LEY", "2025-05-01", None, None, "[2]", 1,
             "REGULACION DE LA EUTANASIA."),
            ("sen/7-CD-2025", "PL", None, None, None, "[1]", 1, "Protección del niño por nacer."),
            ("dip/5-D-2025", "LEY", "2025-04-01", None, "Ley 27999", "[1]", 1, "Sancionado."),
        )
        for key, tipo, pub, other, law, areas, tier, title in bills:
            n, origin, year = key.split("/")[1].split("-")
            c.execute("INSERT INTO ar_bills (exp_key, chamber, number, origin, year, tipo, title, "
                      "author, published, exp_other, law, areas, matched_terms, tier) VALUES "
                      "(?,?,?,?,?,?,?,?,?,?,?,?,'[]',?)",
                      (key, "diputados" if key.startswith("dip") else "senado", int(n), origin,
                       int(year), tipo, title, "PEREZ, ANA", pub, other, law, areas, tier))
        c.execute("INSERT INTO ar_divisions (division_key, chamber, acta_id, date, title, "
                  "vote_type, result, majority, exp_keys, ayes, noes, abstentions, absent, "
                  "has_detail, own_areas, areas, tier, source_url) VALUES ('sen-acta-1','senado',"
                  "1,'2026-10-08','Protección del niño por nacer.','EN GENERAL','AFIRMATIVO',"
                  "'SIMPLE',?,40,30,1,1,1,'[1]','[1]',1,'https://www.senado.gob.ar/x')",
                  (dumps(["sen/7-CD-2025"]),))
        for i, (bloc, pos) in enumerate((("UCR", "AFIRMATIVO"), ("UCR", "AFIRMATIVO"),
                                         ("UCR", "NEGATIVO"), ("PJ", "NEGATIVO"))):
            c.execute("INSERT INTO ar_members (member_key, chamber, name) VALUES (?,?,?)",
                      ("sen/{0}".format(i), "senado", "SEN {0}".format(i)))
            c.execute("INSERT INTO ar_votes VALUES ('sen-acta-1', ?, ?, ?, 'CABA')",
                      ("sen/{0}".format(i), pos, bloc))
        return c

    def test_lapse_dates_follow_ley_13640(self):
        c = self.store()
        rows = {r["exp_key"]: r for r in c.execute("SELECT * FROM ar_bills")}
        self.assertEqual(ar.lapse_date(c, rows["dip/4642-D-2026"]), "2028-02-29")
        self.assertEqual(ar.lapse_date(c, rows["dip/100-D-2025"]), "2027-02-28")
        # came from Diputados ('CD'): one more year
        self.assertEqual(ar.lapse_date(c, rows["sen/7-CD-2025"]), "2028-02-29")
        self.assertIsNone(ar.lapse_date(c, rows["dip/5-D-2025"]))           # a law
        self.assertIsNone(ar.lapse_date(c, rows["dip/4502-D-2026"]))        # not a bill
        self.assertEqual(ar.parliamentary_year("2026-02-10"), 2025)

    def test_edition_with_lapse_section_split_and_noise(self):
        c = self.store()
        self.watch('expedientes:\n  "sen/7-CD-2025": {areas: [1], why: "Unborn child."}\n')
        text = ce.render(c, ar.COUNTRY, "2026-10-09", "2026-10-02",
                         config_dir=self.cfg, directory=self.eds)
        self.assertIn("## Nearing lapse (Ley 13.640)", text)
        self.assertLess(text.index("## Nearing lapse"), text.index("## Watchlist"))
        self.assertIn("**dip/100-D-2025** · lapses 28 February 2027", text)
        self.assertIn("Later: 2 bill(s) lapse on 29 February 2028.", text)
        self.assertIn("By bloc (for-against, then abstaining where any): UCR 2-1, PJ 0-1", text)
        self.assertIn("Against their group's majority: SEN 2 (UCR)", text)
        self.assertIn("activity in this edition: sen/7-CD-2025", text)
        self.assertNotIn("COMERCIO INTERNACIONAL Y CULTO", text)
        self.assertIn("1 excluded title", text)
        self.assertNotIn("—", text)

    def test_openings(self):
        self.assertEqual(ar.opening("PEDIDO DE INFORMES AL PODER EJECUTIVO"),
                         "a request for information to the Executive")
        self.assertTrue(ar.opening("EXPRESAR REPUDIO POR").startswith("a motion of repudiation"))


# --- Mexico -----------------------------------------------------------------------

class MexicoTests(Base):
    CC = "mx"

    def store(self):
        c = conn_with(mx_store)
        inis = (
            ("66/7585", "2026-10-01", "turnada", 1, "[2]", ["Turnada a la Comisión de Salud."],
             "44Que reforma la Ley General de Salud, en materia de eutanasia."),
            ("66/3474", "2026-02-01", "aprobada", 1, "[12]",
             ["Turnada a la Comisión de Justicia.",
              "Prórroga hasta el 30 de octubre de 2026, otorgada el jueves 1 de octubre de 2026.",
              "Dictaminada y aprobada en la Cámara de Diputados con 400 votos en pro, el martes "
              "6 de octubre de 2026. Votación ."],
             "Que adiciona un artículo 88 Bis a la Ley General de Trata de Personas."),
            ("66/3500", "2026-02-01", "prorroga", 1, "[12]",
             ["Turnada a la Comisión de Justicia.",
              "Prórroga hasta el 30 de octubre de 2026, otorgada el jueves 1 de octubre de 2026."],
             "Que reforma la Ley General en materia de trata de personas."),
            ("66/3600", "2026-10-02", "turnada", 2, "[7]", [],
             "Que reforma la Ley Federal de Protección de Datos Personales en Posesión de los "
             "Particulares, en materia de inteligencia artificial."),
        )
        for key, pres, status, tier, areas, lines, title in inis:
            c.execute("INSERT INTO mx_iniciativas (ini_key, legislature, number, provisional, "
                      "kind, title, origin, party, turno, status, status_lines, presented, "
                      "gaceta_ref, areas, matched_terms, tier) VALUES (?,66,?,0,'iniciativa',?,"
                      "'diputados','Morena','Comisión de Salud',?,?,?,'/Gaceta/66/x.html',?,'[]',?)",
                      (key, int(key.split("/")[1]), title, status, dumps(lines), pres, areas, tier))
        c.execute("INSERT INTO mx_divisions (division_key, chamber, legislature, votaciont, date, "
                  "title, favor, contra, abstencion, groups, ini_keys, positions, own_areas, areas, "
                  "tier) VALUES ('dip-66-300','diputados',66,300,'2026-10-06','DECRETO EN MATERIA "
                  "DE TRATA DE PERSONAS',400,2,1,?,?,3,'[12]','[12]',1)",
                  (dumps({"MORENA": [300, 0, 1, 0, 2, 303], "PAN": [100, 2, 0, 0, 0, 102]}),
                   dumps(["66/3474"])))
        c.execute("INSERT INTO mx_divisions (division_key, chamber, legislature, votaciont, date, "
                  "title, favor, contra, abstencion, groups, ini_keys, own_areas, areas, tier) "
                  "VALUES ('dip-66-301','diputados',66,301,'2026-10-06','DECRETO DE LA LEY "
                  "GENERAL DE TURISMO',400,0,0,'{}','[]','[]','[9]',NULL)")
        return c

    def test_fortnightly_edition_new_moved_votes_and_noise(self):
        c = self.store()
        self.watch("iniciativas: {}\n")
        text = ce.render(c, mx.COUNTRY, "2026-10-10", None, config_dir=self.cfg,
                         directory=self.eds)
        self.assertIn("# Mexico Monitor - 27 September 2026 to 10 October 2026", text)
        self.assertIn("Fortnightly (X9), to Chris by DM.", text)
        self.assertIn("*Que reforma la Ley General de Salud, en materia de eutanasia.*", text)
        self.assertIn("## Stage moves", text)
        self.assertIn("New stage: approved by the Chamber", text)
        self.assertNotIn("66/3500", text)                   # a prórroga is not a stage
        self.assertIn("By group (for-against, then abstaining where any): MORENA 300-0-1, "
                      "PAN 100-2", text)
        self.assertNotIn("TURISMO", text)                   # inherited areas only: dropped
        self.assertNotIn("Posesión de los Particulares", text)
        self.assertIn("1 excluded title", text)
        self.assertIn("1 item with too little evidence", text)
        self.assertNotIn("—", text)

    def test_line_dates(self):
        self.assertEqual(mx.line_date("Publicado en el Diario Oficial de la Federación el jueves "
                                      "19 de diciembre de 2024."), "2024-12-19")
        self.assertIsNone(mx.line_date("Prórroga hasta el 30 de mayo de 2025, otorgada el jueves "
                                       "6 de febrero de 2025"))
        self.assertIsNone(mx.line_date("Turnada a la Comisión de Salud."))
        self.assertEqual(mx.clean_title("81Que reforma"), "Que reforma")

    def test_fortnight_wording(self):
        c = conn_with(mx_store)
        self.watch("iniciativas: {}\n")
        text = ce.render(c, mx.COUNTRY, "2026-10-10", "2026-10-03", config_dir=self.cfg,
                         directory=self.eds)
        self.assertIn("# Mexico Monitor - fortnight to 10 October 2026", text)
        self.assertIn("**A quiet fortnight.** Nothing on our ground", text)
        self.assertIn("Fortnightly (X9), to Chris by DM.", text)
        dm = ce.dm_summary(c, mx.COUNTRY, "2026-10-10", config_dir=self.cfg, directory=self.eds)
        self.assertIn("*Mexico Monitor - fortnight to 10 October 2026*", dm)
        self.assertIn("*A quiet fortnight*", dm)

    def test_fortnightly_dm_window_is_a_fortnight(self):
        c = self.store()
        self.watch("iniciativas: {}\n")
        dm = ce.dm_summary(c, mx.COUNTRY, "2026-10-10", config_dir=self.cfg, directory=self.eds)
        self.assertIn("eutanasia", dm)        # presented 1 October: inside 14 days, not 7


if __name__ == "__main__":
    unittest.main()
