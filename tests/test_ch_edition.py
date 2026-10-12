"""The Swiss weekly edition (src/editions/ch.py on src/country_edition.py).

A small in-memory store built with src/ch_store's schema: rows shaped as
tools/ch_rollcalls.py writes them, values from the 9 October 2026 scoping
store (the Herbstsession 2026).
"""

import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ch_store  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src.editions import ch as ch_ed  # noqa: E402

BUS = ("INSERT INTO ch_businesses (business_id, short_number, business_type, title_de, "
       "title_fr, submitted_by, submission_date, submission_council, status, status_date, "
       "areas, matched_terms, tier) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)")
DIV = ("INSERT INTO ch_divisions (division_key, council, vote_id, date, business_id, "
       "short_number, draft_title, subject, meaning_yes, meaning_no, yes, no, abstain, result, "
       "counts_from, positions, own_areas, areas, matched_terms, tier) "
       "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")


def store():
    conn = sqlite3.connect(":memory:")
    ch_store.ensure_schema(conn)
    conn.execute(BUS, (20264624, "26.4624", "Mo.",
                       "Menschenhandel effektiv bekämpfen - Schweizer Modell zum Schutz vor "
                       "sexueller Ausbeutung", None, "Gafner Andreas", "2026-10-03", "NR",
                       "Eingereicht", "2026-10-03", "[12]",
                       '["Menschenhandel*", "sexuelle Ausbeutung"]', 1))
    conn.execute(BUS, (20264207, "26.4207", "Ip.", "Titel folgt",
                       "Exploitation sexuelle de mineures : quelle coopération entre la Suisse "
                       "et la France ?", "Klopfenstein Broggini Delphine", "2026-10-05", "NR",
                       "Eingereicht", "2026-10-05", "[12]", '["exploitation sexuelle"]', 1))
    conn.execute(BUS, (20264117, "26.4117", "Mo.",
                       "Explizite Verankerung des Lebensschutzes im Tierschutzgesetz", None,
                       "Jositsch Daniel", "2026-10-05", "SR", "Eingereicht", "2026-10-05",
                       "[1]", '["Lebensschutz*"]', 1))
    conn.execute(BUS, (20253976, "25.3976", "Ip.",
                       "Tierschutz und neue Schweiz-EU-Abkommen. Steht das Verbot ritueller "
                       "Schlachtungen in der Schweiz zur Disposition?", None, "X", "2026-10-06",
                       "NR", "Eingereicht", "2026-10-06", "[8]", '["Religionsfreiheit*"]', 2))
    conn.execute(BUS, (20244625, "24.4625", "Mo.",
                       "Aufnahme hormoneller Verhütungsmittel in den Leistungskatalog der "
                       "Grundversicherung", "Inscrire les traitements contraceptifs hormonaux",
                       "Crottaz Brigitte", "2024-12-20", "NR", "Erledigt", "2026-10-07", "[1]",
                       '["contraception"]', 2))
    conn.execute(DIV, ("nr-38742", "NR", 38742, "2026-10-07", 20244625, "24.4625", None, None,
                       "Adopter la motion", "Rejeter la motion", 2, 2, 0, None, "tallied", 4,
                       "[]", "[1]", "[]", None))
    conn.execute(DIV, ("sr-8521", "SR", 8521, "2026-10-06", 20253944, "25.3944",
                       "Rahmenregulierung", "Abstimmung über die Motion",
                       "Antrag der Mehrheit (Ablehnung)", "Antrag der Minderheit (Annahme)",
                       28, 12, 3, "ja", "published", 0, "[]", "[]", "[]", None))
    for pn, first, last, grp in ((1, "Anna", "Muster", "V"), (2, "Beat", "Beispiel", "V"),
                                 (3, "Carla", "Probe", "V"), (4, "Dora", "Test", "S")):
        conn.execute("INSERT INTO ch_members (person_number, first_name, last_name, parl_group)"
                     " VALUES (?,?,?,?)", (pn, first, last, grp))
    for pn, pos, grp in ((1, "Nein", "V"), (2, "Nein", "V"), (3, "Ja", "V"), (4, "Ja", "S")):
        conn.execute("INSERT INTO ch_votes (division_key, person_number, position, parl_group)"
                     " VALUES (?,?,?,?)", ("nr-38742", pn, pos, grp))
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


class SwissEdition(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tmp = tempfile.mkdtemp()
        self.text = ce.render(self.conn, ch_ed.COUNTRY, "2026-10-09", "2026-10-02",
                              directory=self.tmp)
        self.keys = {it["key"] for it in ce.gather(self.conn, ch_ed.COUNTRY, "2026-10-02",
                                                   "2026-10-09")}

    def test_watchlist_rekeyed_to_printed_number(self):
        wl = ch_ed.watchlist()
        self.assertIn("25.3944", wl)
        self.assertNotIn("20253944", wl)

    def test_watched_vote_by_business(self):
        self.assertIn("sr-8521", self.keys)              # no areas, but 25.3944 is watched
        self.assertIn("Tally: 28 for, 12 against, 3 abstaining (Ständerat, as published); "
                      "result as recorded: “ja”", self.text)

    def test_nationalrat_tallied_no_result(self):
        self.assertIn("Tally: 2 for, 2 against (tallied from the members' positions; the "
                      "Nationalrat publishes no result)", self.text)
        self.assertIn("A no meant: “Rejeter la motion”.", self.text)
        self.assertIn("By Fraktion (for-against, then abstaining where any): SVP 1-2, SP 1-0",
                      self.text)
        self.assertIn("Against their group's majority: Carla Probe (SVP).", self.text)

    def test_placeholder_title_falls_back_to_french(self):
        self.assertIn("*Exploitation sexuelle de mineures : quelle coopération", self.text)
        self.assertNotIn("Titel folgt", self.text)
        self.assertIn("## Questions", self.text)

    def test_false_friends(self):
        self.assertNotIn("26.4117", self.keys)           # animal welfare
        self.assertIn("25.3976", self.keys)              # ritual slaughter stays

    def test_curia_vista_link(self):
        self.assertIn("geschaeft?AffairId=20264624", self.text)

    def test_untallied_vote(self):
        self.conn.execute("UPDATE ch_divisions SET yes=NULL, no=NULL, abstain=NULL "
                          "WHERE division_key='nr-38742'")
        got = ch_ed.items(self.conn, "2026-10-02", "2026-10-09", ch_ed.watchlist())
        v = next(i for i in got if i["key"] == "nr-38742")
        self.assertTrue(v["lines"][0].startswith("Tally: not available yet"))

    def test_house_style(self):
        self.assertNotIn("—", self.text)
        self.assertNotIn("[ACT]", self.text)


if __name__ == "__main__":
    unittest.main()
