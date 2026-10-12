"""The Italian weekly edition (src/editions/it.py on src/country_edition.py).

A small in-memory store built with src/it_store's schema: rows shaped as
tools/it_rollcalls.py writes them, values copied from the 9 October 2026
scoping store (bills 19/S.2057, 19/C.2799 and 19/S.1999, its final vote).
"""

import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce  # noqa: E402
from src import it_store  # noqa: E402
from src.editions import it as it_ed  # noqa: E402

BILL = ("INSERT INTO it_bills (bill_key, legislature, chamber, number, id_ddl, title, nature, "
        "initiative, presented, status, status_date, areas, matched_terms, tier) "
        "VALUES (?,19,?,?,?,?,?,?,?,?,?,?,?,?)")
DIV = ("INSERT INTO it_divisions (division_key, chamber, legislature, sitting, number, date, "
       "title, bill_key, bill_keys, is_final, outcome, ayes, noes, abstentions, own_areas, areas, "
       "matched_terms, tier, positions_fetched) VALUES (?,?,19,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)")


def store():
    conn = sqlite3.connect(":memory:")
    it_store.ensure_schema(conn)
    conn.execute(BILL, ("19/S.2057", "S", "2057", "55694",
                        "Disposizioni in materia di prevenzione dell'infertilità e di "
                        "preservazione della fertilità femminile", "ordinaria",
                        "Sen. Sensi Filippo ed altri", "2026-10-06", "da assegn. a commis.",
                        "2026-10-06", "[10]", '["fecondazione artificiale"]', 1))
    conn.execute(BILL, ("19/C.2799", "C", "2799", "55176",
                        "Introduzione dell'articolo 19.1 e modifica all'articolo 27 della legge "
                        "11 febbraio 1992, n. 157, concernenti il diritto all'obiezione di "
                        "coscienza per il personale addetto al controllo della fauna selvatica e "
                        "la formazione del personale preposto alla vigilanza venatoria",
                        "ordinaria", "Dep. Zanella Luana ed altri", "2026-02-13",
                        "esame in comm.", "2026-10-05", "[8]", '["obiezione di coscienza"]', 2))
    conn.execute(BILL, ("19/S.1999", "S", "1735", "54566",
                        "Disposizioni in materia di consenso informato in ambito scolastico",
                        "ordinaria", "Gov.", "2025-12-04", "approvato", "2026-06-04", "[6]",
                        '["consenso informato"]', 2))
    conn.execute(BILL, ("19/S.9999", "S", "9999", "1", "Ratifica di un accordo qualsiasi",
                        "ordinaria", "Gov.", "2026-10-02", "da assegn. a commis.", "2026-10-02",
                        "[11]", '["asilo"]', 1))
    conn.execute(DIV, ("senato-19-424-16", "senato", 424, 16, "2026-10-07", "Votazione finale",
                       "19/S.1999", '["19/S.1999"]', 1, "approvato", 3, 2, 0, "[]", "[6]", "[]",
                       2))
    conn.execute(DIV, ("senato-19-424-1", "senato", 424, 1, "2026-10-07", "Articolo 1",
                       "19/S.1999", '["19/S.1999"]', 0, "approvato", 3, 2, 0, "[]", "[6]", "[]",
                       2))
    conn.execute(DIV, ("senato-19-424-2", "senato", 424, 2, "2026-10-07",
                       "Verifica del numero legale", "19/S.1999", '["19/S.1999"]', 0, None,
                       None, None, None, "[]", "[6]", "[]", 2))
    for key, name, grp in (("S:1", "Rossi Mario", "FdI"), ("S:2", "Bianchi Anna", "FdI"),
                           ("S:3", "Verdi Luca", "FdI"), ("S:4", "Neri Carla", "PD-IDP"),
                           ("S:5", "Gialli Piero", "Misto")):
        conn.execute("INSERT INTO it_members (member_key, chamber, name, grp) VALUES "
                     "(?, 'senato', ?, ?)", (key, name, grp))
    for key, pos, grp in (("S:1", "aye", "FdI"), ("S:2", "aye", "FdI"), ("S:3", "no", "FdI"),
                          ("S:4", "no", "PD-IDP"), ("S:5", "aye", "Misto")):
        conn.execute("INSERT INTO it_votes (division_key, member_key, position, grp) VALUES "
                     "(?,?,?,?)", ("senato-19-424-16", key, pos, grp))
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


class ItalyEdition(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tmp = tempfile.mkdtemp()
        self.text = ce.render(self.conn, it_ed.COUNTRY, "2026-10-09", "2026-10-02",
                              directory=self.tmp)

    def items(self):
        return ce.gather(self.conn, it_ed.COUNTRY, "2026-10-02", "2026-10-09")

    def test_new_bill_with_verbatim_title_and_english_takeaway(self):
        self.assertIn("*Disposizioni in materia di prevenzione dell'infertilità", self.text)
        self.assertIn("Ordinary bill 19/S.2057 in the Senato; presented by Sen. Sensi Filippo",
                      self.text)
        self.assertIn("https://www.senato.it/leg/19/BGT/Schede/Ddliter/55694.htm", self.text)

    def test_vote_group_tally_split_and_rebel(self):
        self.assertIn("2 recorded votes on one item", self.text)
        self.assertIn("**Decisive vote** (7 Oct): *Votazione finale*", self.text)
        self.assertIn("Tally: 3 for, 2 against (electronic vote, Senato); result as recorded: "
                      "“approvato”", self.text)
        self.assertIn("By group (for-against, then abstaining where any): FdI 2-1", self.text)
        self.assertIn("Against their group's majority: Verdi Luca (FdI).", self.text)
        self.assertNotIn("Gialli Piero (Misto)", self.text)   # the mixed group has no line

    def test_noise_rules(self):
        keys = {it["key"] for it in self.items()}
        self.assertNotIn("19/C.2799", keys)             # hunting wardens' conscience
        self.assertNotIn("senato-19-424-2", keys)       # quorum check
        self.assertNotIn("19/S.9999", keys)             # migration only: hidden
        self.assertIn("1 excluded title", self.text)
        self.assertIn("1 procedural vote", self.text)

    def test_ordine_del_giorno_is_not_procedure(self):
        it = ce.item("it", "vote", "camera-vs19_704_038", "2026-10-07",
                     "ODG 9/3053/41 - Votazione Ordine del giorno 9/3053/41", [6], 2)
        self.assertIsNone(ce.noise_for(it_ed.COUNTRY).drop_reason(it))

    def test_watched_bill_by_key(self):
        wl = {"19/S.2057": {"areas": [10], "why": "Fertility preservation."}}
        got = it_ed.items(self.conn, "2026-10-02", "2026-10-09", wl)
        self.assertTrue(next(i for i in got if i["key"] == "19/S.2057")["watched"])

    def test_house_style(self):
        self.assertNotIn("—", self.text)
        self.assertNotIn("[ACT]", self.text)
        self.assertIn("# Italy Monitor - week to 9 October 2026", self.text)

    def test_camera_url(self):
        self.assertEqual(it_ed.bill_url("19/C.2822-B"),
                         "https://www.camera.it/leg19/126?leg=19&idDocumento=2822")

    def test_quiet_week(self):
        text = ce.render(self.conn, it_ed.COUNTRY, "2026-01-09", "2026-01-02",
                         directory=self.tmp)
        self.assertIn("**A quiet week.**", text)


if __name__ == "__main__":
    unittest.main()
