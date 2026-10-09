"""The Spain weekly edition (src/editions/es.py on src/country_edition.py):
the dissolution notice (ES6), votes with group splits and named members
against their group, the procedural filter, and the switch to the next
legislature. No network: a small store built here, the repo's own config."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce, es_store  # noqa: E402
from src.editions import es  # noqa: E402

TODAY = "2026-10-09"


def store():
    conn = sqlite3.connect(":memory:")
    es_store.ensure_schema(conn)
    conn.execute("INSERT INTO es_members (legislature, name, grupo) VALUES (15, 'Abascal Conde, Santiago', 'GVOX')")
    conn.execute(
        "INSERT INTO es_initiatives (initiative_key, legislature, expediente, tipo, objeto, autor, "
        "presentada, situacion, areas, matched_terms, tier) VALUES "
        "('15/122/000201', 15, '122/000201', 'Proposición de ley de Grupos Parlamentarios del Congreso', "
        "'Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, de 23 de noviembre, "
        "del Código Penal, para penalizar las terapias de conversión.', 'Grupo Parlamentario Socialista', "
        "'2026-09-24', 'Pleno, Toma en consideración', '[4, 5]', '[\"terapias de conversión\"]', 1)")
    rows = [
        # key, date, section, title, subgroup, init, yes, no, abst, areas, terms, tier
        ("congreso-15-200-2", "2026-09-23", "Proposiciones no de Ley.",
         "Proposición no de Ley del Grupo Parlamentario Mixto, relativa a la aprobación de la Ley de Familias.",
         None, "15/162/000260", 19, 177, 147, "[9]", '["Ley de Familias"]', 1),
        ("congreso-15-202-18", "2026-09-30", "Solicitud de prórroga de Subcomisiones.",
         "Solicitud de la Comisión de Igualdad, de prórroga de seis meses del plazo para la conclusión "
         "de los trabajos de la Subcomisión relativa a la lucha contra los discursos de odio.",
         None, "15/154/000006", 176, 33, 138, "[7]", '["discursos de odio"]', 1),
        ("congreso-15-202-5", "2026-09-30", "Dictámenes de Comisiones sobre iniciativas legislativas.",
         "Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, del Código Penal, "
         "para penalizar las terapias de conversión.", "Votación de conjunto.", "15/122/000201",
         3, 2, 0, "[4, 5]", '["terapias de conversión"]', 1),
        ("congreso-15-202-4", "2026-09-30", "Dictámenes de Comisiones sobre iniciativas legislativas.",
         "Proposición de Ley Orgánica por la que se modifica la Ley Orgánica 10/1995, del Código Penal, "
         "para penalizar las terapias de conversión.",
         "Enmiendas presentadas por el Grupo Parlamentario VOX.", "15/122/000201",
         2, 3, 0, "[4, 5]", '["terapias de conversión"]', 1),
        ("congreso-15-202-9", "2026-09-30", "Proposiciones no de Ley.",
         "Proposición no de Ley sobre infraestructuras ferroviarias.", None, None, 100, 100, 0, "[]", "[]", None),
    ]
    for (key, date, section, title, sub, init, y, n, a, areas, terms, tier) in rows:
        sess, num = key.split("-")[2:]
        conn.execute(
            "INSERT INTO es_divisions (division_key, chamber, legislature, session, vote_number, date, "
            "section, title, subgroup, initiative_key, assent, yes, no, abstain, not_voting, json_url, "
            "positions, own_areas, areas, matched_terms, tier) VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?,?,0,?,?,?,?,?,?)",
            (key, "congreso", 15, int(sess), int(num), date, section, title, sub, init, y, n, a,
             "https://x/VOT.json", None, areas, areas, terms, tier))
    for name, grupo, pos in (("Uno, Ana", "GS", "Sí"), ("Dos, Berta", "GS", "Sí"),
                             ("Tres, Carla", "GS", "No"), ("Cuatro, Dani", "GP", "No"),
                             ("Cinco, Eva", "GP", "No")):
        conn.execute("INSERT INTO es_votes VALUES ('congreso-15-202-5', ?, ?, ?, '1')", (name, grupo, pos))
    conn.execute("UPDATE es_divisions SET positions = 5 WHERE division_key = 'congreso-15-202-5'")
    conn.commit()
    return conn


class SpainEdition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = store()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def render(self, today=TODAY, since=None):
        return es.render(self.conn, today, since, directory=self.tmp)

    def test_dissolved_quiet_week_is_short_and_names_the_next_sitting(self):
        text = self.render()                       # window 2 to 9 October: nothing
        self.assertIn("The Cortes Generales are dissolved; next sitting 23 December 2026.", text)
        self.assertIn("Real Decreto 806/2026", text)
        self.assertIn("29 November 2026", text)
        self.assertIn("**A quiet week.**", text)
        self.assertNotIn("## Recorded votes", text)
        self.assertNotIn("—", text)

    def test_notice_comes_under_the_subtitle(self):
        lines = self.render().split("\n")
        sub = next(i for i, ln in enumerate(lines) if ln.startswith("_Congreso"))
        self.assertTrue(lines[sub + 2].startswith("> **The Cortes Generales are dissolved"))

    def test_no_notice_before_the_dissolution(self):
        self.assertEqual(es.notice(self.conn, "2026-10-05"), [])
        self.assertNotIn("dissolved", self.render("2026-10-01", "2026-09-22"))

    def test_after_the_election_and_after_convening(self):
        self.assertIn("was held on 29 November 2026", es.notice(self.conn, "2026-12-01")[0])
        late = es.notice(self.conn, "2026-12-28")[0]
        self.assertIn("The XVI legislature has convened; its data is not out yet.", late)

    def test_next_legislature_data_lifts_the_notice(self):
        self.conn.execute("INSERT INTO es_members (legislature, name) VALUES (16, 'Nuevo, Diputado')")
        self.assertIsNone(es.state(self.conn, "2027-01-10"))
        self.assertNotIn("dissolved", self.render("2027-01-10"))

    def test_last_sitting_week_votes(self):
        text = self.render(since="2026-09-22")
        self.assertIn("dissolved; next sitting", text)
        self.assertIn("Ley de Familias", text)
        self.assertIn("Non-binding motion (proposición no de ley), XV legislature", text)
        # one entry for the bill's two votes, the vote of the whole decisive
        self.assertIn("2 recorded votes on one item", text)
        self.assertIn("**Decisive vote** (30 Sep): *Votación de conjunto. Proposición de Ley", text)
        self.assertIn("By group at the vote (for-against, then abstaining where any): GS 2-1, GP 0-2", text)
        self.assertIn("Against their group's majority: Tres, Carla (GS).", text)
        self.assertIn("Member positions not read yet", text)
        # the deadline extension is procedural, counted, not shown
        self.assertNotIn("prórroga de seis meses", text)
        self.assertIn("1 procedural vote", text)
        # off our ground never appears
        self.assertNotIn("ferroviarias", text)

    def test_new_initiative_says_it_lapsed(self):
        text = self.render(since="2026-09-22")
        self.assertIn("## New on our ground", text)
        self.assertIn("Lapsed with the dissolution of 6 October 2026", text)

    def test_watched_by_key(self):
        self.conn.execute("UPDATE es_divisions SET initiative_key = '15/102/000001', areas = '[]' "
                          "WHERE division_key = 'congreso-15-202-9'")
        text = self.render(since="2026-09-22")
        self.assertIn("ferroviarias", text)
        self.assertIn("**watched**", text)

    def test_dm_carries_the_notice(self):
        dm = es.dm_summary(self.conn, TODAY, directory=self.tmp)
        self.assertEqual(dm.split("\n")[1],
                         "_Cortes dissolved on 6 Oct; next sitting 23 December 2026 (XVI legislature)._")
        self.assertIn("A quiet week", dm)

    def test_wrapper_leaves_the_framework_unpatched(self):
        before = (ce.render, ce.dm_summary)
        self.render()
        self.assertEqual((ce.render, ce.dm_summary), before)
        plain = ce.render(self.conn, es.COUNTRY, TODAY, directory=self.tmp)
        self.assertNotIn("dissolved", plain)


if __name__ == "__main__":
    unittest.main()
