"""The French weekly edition (src/editions/fr.py on src/country_edition.py).

A small in-memory store built with src/fr_store's schema: rows shaped as
tools/fr_rollcalls.py writes them, values from the 9 October 2026 scoping
store (the IVG conscience-clause bill, the aide a mourir final vote).
"""

import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce  # noqa: E402
from src import fr_store  # noqa: E402
from src.editions import fr as fr_ed  # noqa: E402

DOS = ("INSERT INTO fr_dossiers (dossier_ref, legislature, title, procedure, an_path, last_act, "
       "last_act_label, last_act_at, promulgated_at, areas, matched_terms, tier) "
       "VALUES (?,17,?,?,?,?,?,?,?,?,?,?)")
DIV = ("INSERT INTO fr_divisions (division_key, chamber, legislature, number, date, vote_type, "
       "result, title, dossier_ref, dossier_via, pour, contre, abstentions, own_areas, areas, "
       "matched_terms, tier) VALUES (?,'an',17,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")


def store():
    conn = sqlite3.connect(":memory:")
    fr_store.ensure_schema(conn)
    conn.execute(DOS, ("DLR5L17N54992", "Supprimer la clause de conscience spécifique en matière "
                       "d’interruption volontaire de grossesse", "Proposition de loi ordinaire",
                       None, "AN1-COM-FOND-SAISIE", "Renvoi en commission au fond",
                       "2026-10-06", None, "[1]", '["interruption* volontaire* de grossesse"]',
                       1))
    conn.execute(DOS, ("DLR5L17N55019", "Rapport d'information sur l’instruction en famille",
                       "Rapport d'information sans mission", None, "AN20-RAPPORT",
                       "Dépôt de rapport", "2026-10-07", None, "[6]",
                       '["instruction en famille"]', 1))
    conn.execute(DOS, ("DLR5L17N55023", "Faire de l’Union européenne le cadre d’une interdiction "
                       "effective des mécanismes addictifs", "Résolution", None,
                       "ANLUNI-COM-CAE-REUNION", "Réunion de commission", "2026-10-14", None,
                       "[6, 7]", '["reseaux sociaux"]', 1))
    conn.execute(DOS, ("DLR5L17N51670", "Fin de vie", "Proposition de loi ordinaire",
                       "fin_de_vie_17e", "PROM-PUB", "Promulgation d'une loi", "2026-08-18",
                       "2026-08-18", "[2]", '["aide a mourir"]', 1))
    conn.execute(DIV, ("an-17-8280", 8280, "2026-10-07", "SPS", "adopté",
                       "l'ensemble de la proposition de loi relative au droit à l'aide à mourir "
                       "(lecture définitive).", "DLR5L17N51670", "ref", 3, 2, 0, "[2]", "[2]",
                       '["aide a mourir"]', 1))
    conn.execute(DIV, ("an-17-8281", 8281, "2026-10-07", "SPO", None,
                       "la demande de suspension de séance formulée par M. Boyard",
                       None, None, 10, 20, 0, "[]", "[2]", "[]", None))
    conn.execute("INSERT INTO fr_groups (organe_ref, chamber, abbr) VALUES ('PO1', 'an', 'RN')")
    conn.execute("INSERT INTO fr_groups (organe_ref, chamber, abbr) VALUES ('PO2', 'an', 'EPR')")
    # PA4 has left: AMO30 did not name them, so the edition shows their ref.
    for ref, name in (("PA1", "Jean Martin"), ("PA2", "Marie Durand"), ("PA3", "Paul Petit"),
                      ("PA5", "Luc Moreau")):
        conn.execute("INSERT INTO fr_members (acteur_ref, chamber, name) VALUES (?,'an',?)",
                     (ref, name))
    for ref, pos, grp, intended in (("PA1", "pour", "PO2", None), ("PA2", "pour", "PO2", None),
                                    ("PA3", "contre", "PO1", None),
                                    ("PA4", "pour", "PO1", "contre"), ("PA5", "contre", "PO1",
                                                                       None)):
        conn.execute("INSERT INTO fr_votes (division_key, acteur_ref, position, group_ref, "
                     "intended) VALUES (?,?,?,?,?)", ("an-17-8280", ref, pos, grp, intended))
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


class FrenchEdition(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tmp = tempfile.mkdtemp()
        self.text = ce.render(self.conn, fr_ed.COUNTRY, "2026-10-09", "2026-10-02",
                              directory=self.tmp)

    def test_new_and_moved_from_the_latest_act(self):
        self.assertTrue(fr_ed.is_new("AN1-COM-FOND-SAISIE"))
        self.assertFalse(fr_ed.is_new("AN20-RAPPORT"))
        self.assertFalse(fr_ed.is_new("AN2-COM-FOND-SAISIE"))
        new = self.text.split("## New on our ground")[1].split("## ")[0]
        moved = self.text.split("## Stage moves")[1].split("## ")[0]
        self.assertIn("DLR5L17N54992", new)
        self.assertIn("DLR5L17N55019", moved)

    def test_vote_split_rebels_and_mises_au_point(self):
        self.assertIn("Tally: 3 for, 2 against (scrutin public solennel); result as recorded: "
                      "“adopté”", self.text)
        self.assertIn("By group (for-against, then abstaining where any): RN 1-2, EPR 2-0",
                      self.text)
        self.assertIn("Against their group's majority: PA4 (RN).", self.text)
        self.assertIn("1 mise(s) au point", self.text)
        self.assertIn("https://www.assemblee-nationale.fr/dyn/17/scrutins/8280", self.text)

    def test_suspension_is_procedural(self):
        keys = {it["key"] for it in ce.gather(self.conn, fr_ed.COUNTRY, "2026-10-02",
                                              "2026-10-09")}
        self.assertNotIn("an-17-8281", keys)
        self.assertIn("1 procedural vote", self.text)

    def test_week_ahead_and_fr4_standing_note(self):
        ahead = self.text.split("## Week ahead")[1].split("## Coverage")[0]
        self.assertIn("DLR5L17N55023", ahead)
        self.assertIn("Réunion de commission on 14 October 2026", ahead)
        self.assertIn("*Aide à mourir: decrees to watch*", ahead)
        self.assertIn("Haute Autorité de santé", ahead)

    def test_note_keeps_a_quiet_week_from_hiding_fr4(self):
        text = ce.render(self.conn, fr_ed.COUNTRY, "2026-01-09", "2026-01-02",
                         directory=self.tmp)
        self.assertIn("Aide à mourir: decrees to watch", text)

    def test_no_note_without_a_decrees_list(self):
        self.assertIsNone(fr_ed.decrees_note("2026-10-09", {"DLR5L17N51670": {"areas": [2]}}))

    def test_dossier_url_uses_the_an_path(self):
        self.assertEqual(fr_ed.dossier_url("DLR5L17N51670", "fin_de_vie_17e"),
                         "https://www.assemblee-nationale.fr/dyn/17/dossiers/fin_de_vie_17e")
        self.assertEqual(fr_ed.dossier_url("DLR5L16N49654"),
                         "https://www.assemblee-nationale.fr/dyn/16/dossiers/DLR5L16N49654")

    def test_house_style(self):
        self.assertNotIn("—", self.text)
        self.assertNotIn("[ACT]", self.text)


if __name__ == "__main__":
    unittest.main()
