"""The Slovakia weekly edition (src/editions/sk.py on src/country_edition.py):
tallies counted from member positions, never the open data's absent count
(wrong on about 12% of votes); clubs at the vote; procedural votes left
out; one entry per print with the vote as a whole decisive;
interpellations. No network: a small store built here, the repo's own
config."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce, sk_store  # noqa: E402
from src.editions import sk  # noqa: E402

TODAY = "2026-09-19"
SINCE = "2026-09-12"
HEAD = ("Návrh poslankyne Národnej rady Slovenskej republiky Pauly PUŠKÁROVEJ na vydanie zákona, "
        "ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rodine (tlač 1254) - tretie čítanie.")


def store():
    conn = sqlite3.connect(":memory:")
    sk_store.ensure_schema(conn)
    conn.execute("INSERT INTO sk_bills (bill_key, term, tlac, type_name, title, delivered, areas, "
                 "matched_terms, tier) VALUES ('9/1254', 9, '1254', 'Návrh zákona', ?, '2026-09-14', "
                 "'[9]', '[\"36/2005 Z. z.\"]', 1)", (HEAD.split(" (tlač")[0],))
    votes = [
        # id, date, number, question, result, present, Z, P, ?, N, absent(open data), areas
        (58272, "2026-09-16T17:12:14", 36, "Hlasovanie o návrhu zákona ako o celku.", "Návrh prešiel",
         6, 3, 2, 1, 0, 53, "[9]"),
        (58270, "2026-09-16T17:10:42", 34, "Hlasovanie o pozmeňujúcich a doplňujúcich návrhoch z "
         "rozpravy - posl. P. Puškárová.", "Návrh prešiel", 139, 118, 1, 20, 0, 11, "[9]"),
        (58271, "2026-09-16T17:11:24", 35, "Hlasovanie o pristúpení k tretiemu čítaniu ihneď.",
         "Návrh prešiel", 141, 77, 12, 51, 1, 9, "[9]"),
        (58300, "2026-09-17T11:00:00", 50, "Hlasovanie o návrhu zákona ako o celku.", "Návrh prešiel",
         140, 140, 0, 0, 0, 10, "[]"),
    ]
    for vid, date, num, q, res, pres, z, p, a, n, absent, areas in votes:
        conn.execute("INSERT INTO sk_divisions (voting_id, term, meeting, number, date, name, bill_key, "
                     "is_secret, result, present, agreed, disagreed, abstained, not_voting, absent, "
                     "own_areas, areas, matched_terms, tier) VALUES (?,9,61,?,?,?,?,0,?,?,?,?,?,?,?,'[]',?,"
                     "'[\"36/2005 Z. z.\"]',1)",
                     (vid, num, date, HEAD + "\n" + q, "9/1254" if areas != "[]" else "9/9999", res, pres,
                      z, p, a, n, absent, areas))
    members = [(1, "Smer, Jana", "SMER - SD", "Z"), (2, "Smer, Karol", "SMER - SD", "Z"),
               (3, "Smer, Peter", "SMER - SD", "P"), (4, "Pes, Eva", "PS", "Z"),
               (5, "Pes, Ivan", "PS", "P"), (6, "Kdh, Mária", "KDH", "?"),
               (7, "Absent, One", "SaS", "0"), (8, "Absent, Two", None, "0")]
    for mp, name, club, pos in members:
        conn.execute("INSERT INTO sk_members (mp_id, name) VALUES (?, ?)", (mp, name))
        conn.execute("INSERT INTO sk_votes VALUES (58272, ?, ?, ?)", (mp, pos, club))
    conn.execute("UPDATE sk_divisions SET positions_at = '2026-09-17' WHERE voting_id = 58272")
    conn.execute("INSERT INTO sk_interpellations (int_id, term, subject, questioner, addressee, state, "
                 "submitted, answered, areas, matched_terms, tier) VALUES (4016, 9, 'vo veci úpravy "
                 "práv a povinností párov rovnakého pohlavia', 'Plaváková, Lucia', 'minister "
                 "spravodlivosti SR', 'Uzavretá odpoveď na interpeláciu', '2026-08-13', '2026-09-17', "
                 "'[9]', '[\"rovnakého pohlavia\"]', 1)")
    conn.commit()
    return conn


class SlovakiaEdition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = store()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def render(self):
        return ce.render(self.conn, sk.COUNTRY, TODAY, SINCE, directory=self.tmp)

    def test_tally_is_counted_from_positions_not_the_absent_field(self):
        text = self.render()
        self.assertIn("Tally: 3 for, 2 against, 1 abstaining (counted from the 8 member positions: "
                      "0 not voting, 2 absent); result as recorded: “Návrh prešiel”", text)
        self.assertNotIn("53", text)                 # the open data's absent count

    def test_without_positions_absences_are_left_out(self):
        text = self.render()
        self.assertIn("118 for, 1 against, 20 abstaining (open-data totals, 0 not voting; "
                      "absences left out until the member positions are read", text)
        self.assertNotIn("11 absent", text)

    def test_clubs_at_the_vote_and_members_against_their_club(self):
        text = self.render()
        self.assertIn("By club at the vote (for-against, then abstaining where any): "
                      "SMER - SD 2-1, PS 1-1, KDH 0-0-1", text)
        self.assertIn("Against their group's majority: Smer, Peter (SMER - SD).", text)

    def test_one_entry_per_print_with_the_whole_decisive(self):
        text = self.render()
        self.assertIn("2 recorded votes on one item", text)
        self.assertIn("**Decisive vote** (16 Sep): *Hlasovanie o návrhu zákona ako o celku. Návrh", text)
        self.assertIn("Final vote on the bill as a whole, third reading. The record says the motion "
                      "passed", text)

    def test_procedural_votes_are_left_out_and_counted(self):
        text = self.render()
        self.assertNotIn("pristúpení k tretiemu", text)
        self.assertIn("1 procedural vote", text)

    def test_off_ground_votes_never_appear(self):
        self.assertNotIn("58300", self.render())

    def test_new_print_and_interpellation(self):
        text = self.render()
        self.assertIn("## New on our ground", text)
        self.assertIn("Bill, print (tlač) 1254, delivered to the House", text)
        self.assertIn("## Answers", text)
        self.assertIn("Answered: the interpellation by Plaváková, Lucia of 13 August 2026, "
                      "addressed to: minister spravodlivosti SR", text)

    def test_label_split(self):
        head, q = sk.split_label(HEAD + "\nHlasovanie o návrhu zákona ako o celku.")
        self.assertTrue(head.endswith("tretie čítanie."))
        self.assertEqual(q, "Hlasovanie o návrhu zákona ako o celku.")
        self.assertTrue(sk.vote_title(HEAD + "\n" + q).startswith("Hlasovanie o návrhu"))

    def test_watched_print(self):
        self.conn.execute("UPDATE sk_divisions SET bill_key = '9/733' WHERE voting_id = 58300")
        text = self.render()
        self.assertIn("9/733", text)
        self.assertIn("**watched**", text)


if __name__ == "__main__":
    unittest.main()
