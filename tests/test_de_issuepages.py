"""German issue pages (Christopher, 24 September 2026: "Build the issue
pages").

Two properties, and the first is the one that would have done real damage.

A MEMBER IS SHOWN THE SEAT THEY HOLD, NEVER THE ONE THEY STOOD IN.
abgeordnetenwatch's `constituency` is where a member was a CANDIDATE;
mandate_won says whether they won it. Three members share "103 -
München-Giesing" -- one won it, two came in from the list. Printing the
constituency for all of them told a reader that Fabian Jacobi represents Köln
I, and a campaign mobilising Köln I constituents to write to "their MP" would
have been writing to the wrong person.

THEY ARE NOT PUBLISHED. partner_site deploys to Vercel production on the
Monday publish, and every area on these pages comes from a taxonomy the
edition itself says is unverified. Publishing them would contradict the
caveat we print, so they are built into docs/ and PUBLISH_TO_SITE is the one
line that changes that.
"""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, de_issuepages as ip

TODAY = datetime.date(2026, 9, 24)
NAMES = {1: "Abortion", 5: "Sex based rights", 11: "Migration"}


def _conn():
    return db.init_db(db.connect(":memory:"))


def _spoke(conn, pid, speaker, areas="[5]", stance=2, constituency=None,
           mandate_won=None):
    conn.execute(
        "INSERT INTO de_members (person_id, name, party, parliament, "
        "constituency, mandate_won, first_seen, last_seen) VALUES "
        "(?,?,'AfD','5',?,?,?,?)",
        (pid, speaker, constituency, mandate_won, "2026-09-24", "2026-09-24"))
    conn.execute(
        "INSERT INTO de_speeches (speech_id, protocol, date, speaker, party, "
        "role, person_id, excerpt, text, areas, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,'AfD','member',?,'Etwas Gesagtes','...',?,1,?,?)",
        ("s" + pid, "21/94", "2026-09-10", speaker, pid, areas,
         "2026-09-24", "2026-09-24"))
    conn.execute("CREATE TABLE IF NOT EXISTS stance (ref TEXT PRIMARY KEY, "
                 "stance INTEGER, why TEXT, model TEXT, scored_at TEXT)")
    if stance is not None:
        conn.execute("INSERT INTO stance (ref, stance) VALUES (?,?)",
                     ("de-speech:s" + pid, stance))
    conn.commit()


class SeatTests(unittest.TestCase):
    """THE ONE THAT MATTERS."""

    def test_a_directly_elected_member_shows_the_constituency(self):
        self.assertEqual(ip._seat("92 - Köln I (Bundestag 2025 - 2029)",
                                  "constituency"),
                         "92 - Köln I (Bundestag 2025 - 2029)")

    def test_a_list_member_is_never_shown_as_holding_the_seat(self):
        got = ip._seat("92 - Köln I (Bundestag 2025 - 2029)", "list")
        self.assertTrue(got.startswith("list"), got)
        self.assertNotEqual(got, "92 - Köln I (Bundestag 2025 - 2029)")

    def test_a_list_member_with_no_constituency_says_only_list(self):
        self.assertEqual(ip._seat(None, "list"), "list")

    def test_an_unknown_mandate_type_claims_nothing(self):
        """A member we have not profiled must not be given a seat."""
        self.assertEqual(ip._seat("92 - Köln I", None), "-")
        self.assertEqual(ip._seat(None, None), "-")

    def test_the_page_does_not_present_a_list_member_as_the_member_for_a_seat(self):
        conn = _conn()
        _spoke(conn, "1", "Fabian Jacobi",
               constituency="92 - Köln I (Bundestag 2025 - 2029)",
               mandate_won="list")
        body = ip.render(ip.collect(conn, 5, TODAY), "Sex based rights", TODAY)
        self.assertIn("Fabian Jacobi", body)
        self.assertIn("list (92 - Köln I)", body)


class PublicationTests(unittest.TestCase):
    def test_the_pages_are_not_written_to_the_deployed_site(self):
        """partner_site deploys to production on the Monday publish, and the
        taxonomy behind these pages is unverified."""
        self.assertFalse(ip.PUBLISH_TO_SITE)
        self.assertTrue(ip.OUT_DIR.endswith(os.path.join("docs",
                                                         "de-issues")))

    def test_every_page_carries_the_unverified_warning(self):
        conn = _conn()
        body = ip.render(ip.collect(conn, 1, TODAY), "Abortion", TODAY)
        self.assertIn("no German speaker has verified", body)

    def test_the_index_says_why_it_is_unpublished(self):
        import tempfile
        conn = _conn()
        with tempfile.TemporaryDirectory() as tmp:
            paths = ip.build(conn, NAMES, TODAY, out_dir=tmp)
            with open(os.path.join(tmp, "de-issues.md"), encoding="utf-8") as fh:
                index = fh.read()
        self.assertIn("Not published", index)
        self.assertIn("PUBLISH_TO_SITE", index)
        self.assertTrue(paths)


class ContentTests(unittest.TestCase):
    def test_migration_has_no_page(self):
        import tempfile
        conn = _conn()
        with tempfile.TemporaryDirectory() as tmp:
            ip.build(conn, NAMES, TODAY, out_dir=tmp)
            files = os.listdir(tmp)
        self.assertNotIn("de-issue-migration.md", files)
        self.assertIn("de-issue-abortion.md", files)

    def test_an_empty_area_says_what_it_is_empty_OF(self):
        """"Nothing collected" and "nothing exists" are different, and the
        German collectors are days old against a record going back decades."""
        conn = _conn()
        body = ip.render(ip.collect(conn, 1, TODAY), "Abortion", TODAY)
        self.assertIn("what has been COLLECTED, not what exists", body)

    def test_a_speech_on_another_area_does_not_appear(self):
        conn = _conn()
        _spoke(conn, "1", "Ein Mitglied", areas="[1]")
        body = ip.render(ip.collect(conn, 5, TODAY), "Sex based rights", TODAY)
        self.assertNotIn("Ein Mitglied", body)

    def test_an_unscored_speaker_is_not_read_as_neutral(self):
        """"Not yet scored" and "neutral" are different claims about a
        member's position."""
        conn = _conn()
        _spoke(conn, "1", "Ein Mitglied", stance=None)
        body = ip.render(ip.collect(conn, 5, TODAY), "Sex based rights", TODAY)
        self.assertIn("not yet scored", body)

    def test_divisions_carry_no_verdict(self):
        conn = _conn()
        conn.execute(
            "INSERT INTO de_divisions (vote_id, parliament, parliament_label, "
            "date, label, yes, no, areas, tier, first_seen, last_seen) VALUES "
            "('v1','13','Bayern','2025-07-24','Keine Liberalisierung',110,36,"
            "'[1]',1,'2026-09-24','2026-09-24')")
        conn.commit()
        body = ip.render(ip.collect(conn, 1, TODAY), "Abortion", TODAY)
        self.assertIn("No verdicts", body)
        self.assertIn("110 yes / 36 no", body)


if __name__ == "__main__":
    unittest.main()
