"""German Campaigns Brief drafts (Christopher, 24 September 2026: "Build the
campaign briefs").

Two properties carry this file.

SLUGS MUST BE UNIQUE, and the id is what makes them so. Two different EU
citizens' initiatives -- "My Voice, My Choice" on abortion access and "Verbot
von Konversionsmaßnahmen" -- both open "Mitteilung der Kommission über die
Europäische Bürgerinitiative", so their truncated slugs were IDENTICAL. Both
are campaign-relevant; one would have silently overwritten the other's file
AND its brief_log row, and the run would have reported two briefs written.

A SUBJECT MUST BE LIVE. A brief on a bill the House has already decided is a
history essay, and the stage test is shared with the edition so the two can
never disagree about what is still running.
"""

import datetime
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dbr = _load("de_briefs")
TODAY = "2026-09-24"


def _conn():
    return db.init_db(db.connect(":memory:"))


def _vorgang(conn, vid, titel, stand="Überwiesen", score=3, areas="[1]"):
    conn.execute(
        "INSERT INTO de_vorgaenge (vorgang_id, titel, vorgangstyp, stand, "
        "areas, tier, triage_score, why_it_matters, datum, first_seen, "
        "last_seen) VALUES (?,?,'Antrag',?,?,1,?,'Because.','2026-09-01',?,?)",
        (vid, titel, stand, areas, score, TODAY, TODAY))
    conn.commit()


def _petition(conn, pid, title, closes="2026-10-06", areas="[9]"):
    conn.execute(
        "INSERT INTO de_petitions (petition_id, title, closes, signatures, "
        "url, areas, tier, triage_score, why_it_matters, first_seen, "
        "last_seen) VALUES (?,?,?,100,'u',?,1,3,'Because.',?,?)",
        (pid, title, closes, areas, TODAY, TODAY))
    conn.commit()


class SlugTests(unittest.TestCase):
    def test_two_titles_that_truncate_alike_get_different_slugs(self):
        """THE ONE THAT MATTERS. Both of these are real, both are on our
        ground, and before the id suffix they collided exactly."""
        conn = _conn()
        _vorgang(conn, "333268", 'Mitteilung der Kommission über die '
                 'Europäische Bürgerinitiative (EBI) "My Voice, My Choice"')
        _vorgang(conn, "337142", 'Mitteilung der Kommission über die '
                 'Europäische Bürgerinitiative "Verbot von '
                 'Konversionsmaßnahmen in der Europäischen Union"')
        slugs = [s["slug"] for s in dbr.subjects(conn, TODAY)]
        self.assertEqual(len(slugs), 2)
        self.assertEqual(len(set(slugs)), 2, slugs)
        self.assertTrue(all(s.endswith(("333268", "337142")) for s in slugs))

    def test_the_slug_is_stable_so_the_log_row_is_not_orphaned(self):
        """brief_log is keyed on the slug. One that shifted when a title was
        edited would strand the campaigner's record of the brief."""
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz")
        first = dbr.subjects(conn, TODAY)[0]["slug"]
        conn.execute("UPDATE de_vorgaenge SET titel = 'Ein Gesetz (neu)' "
                     "WHERE vorgang_id = '1'")
        conn.commit()
        second = dbr.subjects(conn, TODAY)[0]["slug"]
        self.assertTrue(first.endswith("-1") and second.endswith("-1"))

    def test_a_titleless_subject_still_gets_a_usable_slug(self):
        conn = _conn()
        _vorgang(conn, "7", None)
        self.assertEqual(dbr.subjects(conn, TODAY)[0]["slug"], "de-subject-7")


class SubjectTests(unittest.TestCase):
    def test_only_live_business_is_brief_worthy(self):
        """A brief on a bill the House has already decided is a history
        essay. The stage test is shared with the edition."""
        conn = _conn()
        _vorgang(conn, "1", "Noch offen", stand="Überwiesen")
        _vorgang(conn, "2", "Schon entschieden", stand="Angenommen")
        _vorgang(conn, "3", "Verfallen",
                 stand="Erledigt durch Ablauf der Wahlperiode")
        titles = [s["title"] for s in dbr.subjects(conn, TODAY)]
        self.assertEqual(titles, ["Noch offen"])

    def test_an_unknown_stage_is_treated_as_live(self):
        """Consistent with the edition: a stage this code has not seen is
        not evidence the thing is over."""
        conn = _conn()
        _vorgang(conn, "1", "Neuer Stand", stand="Etwas Unbekanntes")
        self.assertEqual(len(dbr.subjects(conn, TODAY)), 1)

    def test_only_score_three_reaches_a_brief(self):
        """Score 3 is the rubric's own campaign-trigger level."""
        conn = _conn()
        _vorgang(conn, "1", "Ein Dreier", score=3)
        _vorgang(conn, "2", "Ein Zweier", score=2)
        self.assertEqual([s["title"] for s in dbr.subjects(conn, TODAY)],
                         ["Ein Dreier"])

    def test_migration_only_is_never_briefed(self):
        conn = _conn()
        _vorgang(conn, "1", "Abschiebungen", areas="[11]")
        self.assertEqual(dbr.subjects(conn, TODAY), [])

    def test_a_closed_petition_is_not_a_subject(self):
        conn = _conn()
        _petition(conn, "1", "Schon zu", closes="2026-09-01")
        _petition(conn, "2", "Noch offen", closes="2026-10-06")
        self.assertEqual([s["title"] for s in dbr.subjects(conn, TODAY)],
                         ["Noch offen"])

    def test_a_petition_carries_its_deadline(self):
        """The only German subjects with a date to act on."""
        conn = _conn()
        _petition(conn, "1", "Eine Petition")
        self.assertEqual(dbr.subjects(conn, TODAY)[0]["deadline"],
                         "2026-10-06")


class FactsTests(unittest.TestCase):
    def test_the_record_is_quoted_never_invented(self):
        """A brief that puts words in a German parliamentarian's mouth is
        the worst thing this file could produce."""
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz", areas="[1]")
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "party, role, person_id, excerpt, text, areas, tier, first_seen, "
            "last_seen) VALUES ('s1','21/94','2026-09-11','Ein Mitglied',"
            "'SPD','member','p1','Etwas Gesagtes','...','[1]',1,?,?)",
            (TODAY, TODAY))
        conn.commit()
        got = dbr.facts(conn, dbr.subjects(conn, TODAY)[0])
        said = got["what_members_said"]
        self.assertEqual(len(said), 1)
        self.assertEqual(said[0]["member"], "Ein Mitglied")
        self.assertIn("Etwas Gesagtes", said[0]["said"])

    def test_a_speech_on_a_different_area_is_not_pulled_in(self):
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz", areas="[1]")
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "role, person_id, excerpt, text, areas, tier, first_seen, "
            "last_seen) VALUES ('s1','21/94','2026-09-11','X','member','p1',"
            "'Anderes Thema','...','[7]',1,?,?)", (TODAY, TODAY))
        conn.commit()
        got = dbr.facts(conn, dbr.subjects(conn, TODAY)[0])
        self.assertEqual(got["what_members_said"], [])


class RenderTests(unittest.TestCase):
    def _render(self, conn, drafted=True, fields=None):
        mb = dbr._make_briefs()
        s = dbr.subjects(conn, TODAY)[0]
        s["_facts"] = dbr.facts(conn, s)
        return dbr.render(s, fields or {}, mb, TODAY, drafted)

    def test_a_failed_narrative_says_so_at_the_top(self):
        """Five hollow Westminster briefs shipped on 21 September because a
        placeholder read like a considered blank."""
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz")
        body = self._render(conn, drafted=False)
        self.assertIn("NARRATIVE DRAFT FAILED", body)
        self.assertIn("de_briefs.py", body,
                      "the regenerate command must name THIS tool")

    def test_rf4_scores_are_never_auto_filled(self):
        """The Cheat Sheet is explicit that scoring is the campaigner's."""
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz")
        body = self._render(conn)
        self.assertIn("| **RF#1**", body)
        self.assertIn("campaigner's judgement", body)
        # The score column must be EMPTY, not zero or "TBC".
        for line in body.splitlines():
            if line.startswith("| **RF#"):
                self.assertTrue(line.rstrip().endswith("| |"), line)

    def test_the_unverified_taxonomy_warning_travels_with_the_brief(self):
        """A brief is the surface most likely to be read away from the
        edition that carries the caveat."""
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz")
        self.assertIn("no German speaker has verified", self._render(conn))

    def test_westminster_only_blocks_are_named_as_absent(self):
        """An empty Five Column tally would read as an unanalysed campaign
        rather than a jurisdiction the analysis does not cover."""
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz")
        body = self._render(conn)
        self.assertIn("Not in this brief, and why", body)
        self.assertIn("Five Column Analysis", body)

    def test_a_neutral_stance_is_not_shown_as_a_positive_score(self):
        """'+0' reads as a judgement that was never made."""
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz", areas="[1]")
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "role, person_id, excerpt, text, areas, tier, first_seen, "
            "last_seen) VALUES ('s1','21/94','2026-09-11','X','member','p1',"
            "'Etwas','...','[1]',1,?,?)", (TODAY, TODAY))
        conn.execute("CREATE TABLE IF NOT EXISTS stance (ref TEXT PRIMARY "
                     "KEY, stance INTEGER, why TEXT, model TEXT, "
                     "scored_at TEXT)")
        conn.execute("INSERT INTO stance (ref, stance) VALUES "
                     "('de-speech:s1', 0)")
        conn.commit()
        body = self._render(conn)
        self.assertNotIn("+0", body)
        self.assertIn("| 0 |", body)


if __name__ == "__main__":
    unittest.main()
