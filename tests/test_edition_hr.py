"""The Croatia weekly edition (src/editions/hr.py on src/country_edition.py):
the question put on a conclusion not to accept a bill, party shown as
listed and labelled (X6), grouped floor votes, the session agenda as the
week ahead, and the backfill rule for new items. No network: a small store
built here, the repo's own config."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce, hr_store  # noqa: E402
from src.editions import hr  # noqa: E402

TODAY = "2026-10-09"
SINCE = "2026-09-19"
BILL_236 = ("PRIJEDLOG ZAKONA O DOPUNI ZAKONA O ODGOJU I OBRAZOVANJU U OSNOVNOJ I SREDNJOJ ŠKOLI, "
            "prvo čitanje, P.Z. br. 236 - predlagatelj: Klub zastupnika SDP-a")
REJECTED = ('Na 12. sjednici, 25. rujna 2026. donesen je zaključak da se ne prihvaća Prijedlog '
            'zakona (78 glasova "za", 34 "protiv").')


def store():
    conn = sqlite3.connect(":memory:")
    hr_store.ensure_schema(conn)
    items = [
        # tid, session_id, session_no, status, title, bill_key, areas, terms, tier, first_seen
        (214631, 161305, "12", 8, BILL_236, "11/236", "[6]", '["odgoj* i obrazovanj*"]', 2, "2026-09-01"),
        (214632, 161305, "12", 8, "PRIJEDLOG ZAKONA O CESTAMA, prvo čitanje, P.Z. br. 240", "11/240",
         "[]", "[]", None, "2026-09-01"),
        (214499, 161305, "12", 8, "PRIJEDLOG ODLUKE O IZBORU ZAMJENICE PRAVOBRANITELJICE ZA DJECU",
         None, "[6]", '["pravobranitel* za djecu"]', 2, "2026-09-01"),
        (214661, 161305, "12", 6, "PRIJEDLOG ZAKONA O PRESTANKU VAŽENJA ZAKONA O POTVRĐIVANJU "
         "KONVENCIJE VIJEĆA EUROPE, prvo čitanje, P.Z. br. 41", "11/41", "[5]", '["watch:11/41"]', 1,
         "2026-09-01"),
        (214529, 159566, "10", 6, "PRIJEDLOG ZAKONA O PRESTANKU VAŽENJA ..., P.Z. br. 41", "11/41",
         "[5]", "[]", 1, "2026-09-01"),
        (214700, 161305, "12", 6, "PRIJEDLOG ZAKONA O DOPLATKU ZA DJECU, prvo čitanje, P.Z. br. 350",
         "11/350", "[9]", '["doplat* za djecu"]', 2, "2026-10-03"),
    ]
    for tid, sid, sno, st, title, bk, areas, terms, tier, fs in items:
        conn.execute("INSERT INTO hr_items (tid, saziv, session_id, session_no, status_id, title, url, "
                     "bill_key, areas, matched_terms, tier, first_seen, last_seen) "
                     "VALUES (?,11,?,?,?,?,?,?,?,?,?,?,?)",
                     (tid, sid, sno, st, title, "https://www.sabor.hr/x?tid={0}".format(tid), bk,
                      areas, terms, tier, fs, TODAY))
    divs = [
        # key, tid, voted_at, title, bill, y, n, a, outcome, ymr, areas
        ("hr-11-214631", 214631, "2026-09-25T12:59", BILL_236, "11/236", 78, 34, 0, REJECTED, 1, "[6]"),
        ("hr-11-214632", 214632, "2026-09-25T12:59", "CESTE", "11/240", 78, 34, 0, None, None, "[]"),
        ("hr-11-214499", 214499, "2026-09-25T13:10", "PRIJEDLOG ODLUKE O IZBORU ZAMJENICE "
         "PRAVOBRANITELJICE ZA DJECU", None, 84, 0, 27, None, None, "[6]"),
    ]
    for key, tid, at, title, bk, y, n, a, out, ymr, areas in divs:
        conn.execute("INSERT INTO hr_divisions (division_key, tid, saziv, session_no, voted_at, title, "
                     "bill_key, yes, no, abstain, total, outcome, yes_means_reject, areas, matched_terms, "
                     "tier) VALUES (?,?,11,'12',?,?,?,?,?,?,?,?,?,?,'[]',2)",
                     (key, tid, at, title, bk, y, n, a, y + n + a, out, ymr, areas))
    for slug, party, pos in (("a-11-saziv", "HDZ", "for"), ("b-11-saziv", "HDZ", "for"),
                             ("c-11-saziv", "HDZ", "against"), ("d-11-saziv", "SDP", "against")):
        conn.execute("INSERT INTO hr_votes VALUES ('hr-11-214631', ?, ?, ?)", (slug, pos, party))
    conn.commit()
    return conn


class CroatiaEdition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = store()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def render(self, since=SINCE):
        return ce.render(self.conn, hr.COUNTRY, TODAY, since, directory=self.tmp)

    def test_question_put_on_a_conclusion_not_to_accept(self):
        text = self.render()
        self.assertIn("The question put was a conclusion NOT to accept the bill, so “Za” (for) was "
                      "a vote to reject it", text)
        self.assertIn("The conclusion was adopted: the bill was not accepted.", text)
        self.assertIn("Tally: 78 for, 34 against (on a conclusion not to accept the bill: for = to "
                      "reject); result as recorded:", text)
        self.assertIn("First reading, session 12.", text)

    def test_unread_question_is_flagged(self):
        self.conn.execute("UPDATE hr_divisions SET outcome = NULL, yes_means_reject = NULL "
                          "WHERE division_key = 'hr-11-214631'")
        text = self.render()
        self.assertIn("The question put has not been read from the item page yet", text)
        self.assertNotIn("for = to reject", text)

    def test_conclusion_carried(self):
        self.assertTrue(hr.conclusion_carried(REJECTED))
        self.assertFalse(hr.conclusion_carried("Zaključak Kluba nije donesen zaključak da se ne "
                                               "prihvaća Prijedlog"))
        self.assertIsNone(hr.conclusion_carried("Zakon je donesen na 12. sjednici"))

    def test_party_is_labelled_and_no_member_is_named(self):
        text = self.render()
        self.assertIn("By party as listed when the vote was collected, not party history, X6 "
                      "(for-against, then abstaining where any): HDZ 2-1, SDP 0-1", text)
        self.assertIn("4 member positions stored. No member is named against their party", text)
        self.assertNotIn("c-11-saziv", text)
        self.assertNotIn("Against their group's majority", text)

    def test_grouped_floor_vote_is_said(self):
        self.assertIn("Put to one floor vote with 1 other agenda item(s)", self.render())

    def test_appointments_are_left_out(self):
        text = self.render()
        self.assertNotIn("ZAMJENICE", text)
        self.assertIn("1 excluded title", text)

    def test_week_ahead_is_the_session_agenda(self):
        text = self.render()
        self.assertIn("## Week ahead", text)
        self.assertIn("On the agenda of session 12, not yet debated; on 2 sessions' agendas", text)
        self.assertIn("**watched**", text)
        self.assertIn("Withdrawal from the Istanbul Convention", text)

    def test_new_items_skip_the_backfill_and_carry_overs(self):
        text = self.render()
        self.assertIn("## New on our ground", text)
        self.assertIn("P.Z. br. 350", text)
        new = hr.new_items(self.conn, SINCE, TODAY, hr.watchlist())
        self.assertEqual([it["key"] for it in new], ["11/350"])

    def test_watchlist_keys_match_the_store(self):
        wl = hr.watchlist()
        self.assertIn("11/41", wl)
        self.assertIn("item:214612", wl)
        self.assertTrue(wl["11/41"]["why"])


if __name__ == "__main__":
    unittest.main()
