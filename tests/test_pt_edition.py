"""The Portuguese weekly edition (src/editions/pt.py on src/country_edition.py).

A small in-memory store built with src/pt_store's schema: rows shaped as
tools/pt_rollcalls.py writes them, values from the 9 October 2026 scoping
store. Portugal votes by group, so member positions are DERIVED (X5) and
the edition must say so.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce  # noqa: E402
from src import pt_store  # noqa: E402
from src.editions import pt as pt_ed  # noqa: E402

INI = ("INSERT INTO pt_initiatives (ini_key, ini_id, legislature, ini_type, type_desc, number, "
       "title, authors_gp, entered, latest_phase, latest_phase_at, areas, matched_terms, tier) "
       "VALUES (?,?,'XVII',?,?,?,?,?,?,?,?,?,?,?)")
DIV = ("INSERT INTO pt_divisions (division_key, vote_id, legislature, ini_key, date, phase, "
       "description, result, unanimous, meeting_type, own_areas, areas, tier) "
       "VALUES (?,?,'XVII',?,?,?,?,?,?,'RP',?,?,?)")


def store():
    conn = sqlite3.connect(":memory:")
    pt_store.ensure_schema(conn)
    conn.execute(INI, ("XVII/R/1294", 1, "R", "Projeto de Resolução", 1294,
                       "Recomenda ao Governo o reforço das competências do Conselho Nacional de "
                       "Procriação Medicamente Assistida", '["L"]', "2026-10-05", "Anúncio",
                       "2026-10-05", "[10]", '["procriação medicamente assistida"]', 1))
    conn.execute(INI, ("XVII/R/1067", 2, "R", "Projeto de Resolução", 1067,
                       "Recomenda ao Governo o desenvolvimento de uma Estratégia Nacional para a "
                       "Natalidade", '["CDS-PP"]', "2026-06-16", "Votação final global",
                       "2026-10-07", "[9]", '["natalidade"]', 2))
    conn.execute(DIV, ("XVII/182847", 182847, "XVII/R/1067", "2026-10-07", "Votação final global",
                       None, "Aprovado", 0, "[]", "[9]", None))
    conn.execute(DIV, ("XVII/172590", 172590, "XVII/R/1067", "2026-10-07",
                       "Requerimento dispensa redação final", None, "Aprovado", 1, "[]", "[9]",
                       None))
    for party, pos, n in (("PSD", "A Favor", None), ("CH", "A Favor", None),
                          ("PS", "Abstenção", None), ("PS", "A Favor", 2), ("PCP", "Contra", None)):
        conn.execute("INSERT INTO pt_group_votes (division_key, party, position, members) "
                     "VALUES (?,?,?,?)", ("XVII/182847", party, pos, n))
    conn.execute("INSERT INTO pt_votes (division_key, name, party, position, cad_id) VALUES "
                 "('XVII/182847', 'Pedro Vaz', 'PS', 'A Favor', 10)")
    for cad, name, party in ((1, "Ana", "PSD"), (2, "Bruno", "PSD"), (3, "Carla", "CH"),
                             (10, "Pedro Vaz", "PS"), (11, "Rui", "PS"), (12, "Sara", "PCP")):
        conn.execute("INSERT INTO pt_members (cad_id, name, party, situation) VALUES "
                     "(?,?,?,'Efetivo')", (cad, name, party))
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


class PortugueseEdition(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tmp = tempfile.mkdtemp()
        self.text = ce.render(self.conn, pt_ed.COUNTRY, "2026-10-09", "2026-10-02",
                              directory=self.tmp)

    def test_group_sides_as_printed(self):
        self.assertIn("Result as recorded: “Aprovado” (plenary vote by group).", self.text)
        self.assertIn("By group, as the record prints it: for CH, PSD, 2-PS; against PCP; "
                      "abstaining PS.", self.text)

    def test_named_deputy_is_a_fact(self):
        self.assertIn("Named in the record (broke from their group): Pedro Vaz (PS, for).",
                      self.text)

    def test_member_positions_derived_and_labelled(self):
        # PSD 2 + CH 1 + PS 1 (Rui; Pedro Vaz is named) + PCP 1 = 5 derived.
        self.assertIn("Member positions: 5 DERIVED from the group vote", self.text)
        self.assertIn("(the deputy's latest group, sitting deputies only; X5), not recorded per "
                      "member.", self.text)
        self.assertIn("member positions shown are DERIVED from the group vote (X5)", self.text)

    def test_free_vote_says_nothing_is_derived(self):
        self.conn.execute("DELETE FROM pt_group_votes WHERE members IS NULL")
        got = pt_ed.items(self.conn, "2026-10-02", "2026-10-09", {})
        vote = next(i for i in got if i["key"] == "XVII/182847")
        self.assertTrue(any(ln.startswith("A free vote") for ln in vote["lines"]))
        self.assertFalse(any("DERIVED" in ln for ln in vote["lines"]))

    def test_new_and_moved(self):
        new = self.text.split("## New on our ground")[1].split("## ")[0]
        moved = self.text.split("## Stage moves")[1].split("## ")[0]
        self.assertIn("XVII/R/1294", new)
        self.assertIn("Projeto de Resolução 1294/XVII; by L", new)
        self.assertIn("XVII/R/1067", moved)
        self.assertIn("DetalheIniciativa.aspx?BID=1", self.text)

    def test_waiving_final_drafting_is_procedural(self):
        self.assertNotIn("XVII/172590", self.text)
        self.assertIn("1 procedural vote", self.text)

    def test_house_style(self):
        self.assertNotIn("—", self.text)
        self.assertNotIn("[ACT]", self.text)


if __name__ == "__main__":
    unittest.main()
