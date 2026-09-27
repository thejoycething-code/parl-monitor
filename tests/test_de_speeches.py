"""Who said what in the Bundestag (Christopher, 23 September 2026: build the
speeches layer first).

Everything here defends one property: A SPEECH IS ATTRIBUTED TO THE PERSON WHO
GAVE IT, OR TO NOBODY. Putting words in a parliamentarian's mouth is the worst
thing this repo could do, and it is the standing rule that we never invent
their names or their words. So the resolver takes exactly one match or none,
and an unresolved speaker is disclosed rather than guessed at.

The second property is that what is NOT stored is counted. A sitting day
carries a hundred speeches and only the matching ones are kept; without the
protocol count, "nothing on our ground" and "nothing was ever read" are the
same empty query.

Fixtures are cut from protocol 21/94 (11 September 2026).
"""

import importlib.util
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


sp = _load("de_speeches")
rc = _load("de_rollcalls")
TODAY = "2026-09-23"

# The three heading forms, the chair, and the two traps: a procedural heading
# shaped exactly like a name with a party, and a question-time label.
PROTOCOL = """Plenarprotokoll 21/94
Deutscher Bundestag

Tagesordnungspunkt 3 (Fortsetzung):

a) Erste Beratung des Entwurfs eines Gesetzes

Vizepräsidentin Andrea Lindholz:
Das Wort hat die Kollegin.

Cansin Köktürk (Die Linke):
Wir reden hier über Schwangerschaftsabbruch und die Beratung dazu.
Das ist eine Frage der Selbstbestimmung.

Dr. Dietmar Bartsch (Die Linke):
Sie kürzen beim Elterngeld und beim Unterhaltsvorschuss.

Bärbel Bas, Bundesministerin für Arbeit und Soziales:
Ich will zum Thema Leihmutterschaft etwas sagen.

Frage der Abgeordneten Clara Bünger (Die Linke):
Wie steht die Regierung zur Konversionsbehandlung?

Vizepräsidentin Andrea Lindholz:
Vielen Dank.
"""


def _conn():
    return db.init_db(db.connect(":memory:"))


def _member(conn, pid, name, party="Die Linke", parliament="5"):
    conn.execute(
        "INSERT INTO de_members (person_id, name, party, parliament, "
        "parliament_label, legislature, first_seen, last_seen) VALUES "
        "(?,?,?,?,?,?,?,?)",
        (pid, name, party, parliament, "Bundestag", "21", TODAY, TODAY))
    conn.commit()


class ParseTests(unittest.TestCase):
    def test_all_three_speaker_forms_are_found(self):
        got, skipped = sp.parse_speeches(PROTOCOL)
        roles = [r for _, _, r, _ in got]
        self.assertEqual(roles.count("chair"), 2)
        self.assertEqual(roles.count("member"), 3)
        self.assertEqual(roles.count("minister"), 1)

    def test_a_procedural_heading_is_not_a_speaker(self):
        """"Tagesordnungspunkt 3 (Fortsetzung):" has the exact shape of a name
        with a party in brackets. Left in, every sitting day would carry a
        speech by a member called Tagesordnungspunkt."""
        got, skipped = sp.parse_speeches(PROTOCOL)
        self.assertEqual(skipped, 1)
        self.assertNotIn("Tagesordnungspunkt 3",
                         [name for name, _, _, _ in got])

    def test_the_question_time_label_is_not_part_of_the_name(self):
        """"Frage der Abgeordneten Clara Bünger" is a label meaning "question
        from MP X", not a name. Stored whole it attributes to nobody."""
        got, _ = sp.parse_speeches(PROTOCOL)
        self.assertIn("Clara Bünger", [name for name, _, _, _ in got])

    def test_the_body_runs_to_the_next_heading(self):
        got, _ = sp.parse_speeches(PROTOCOL)
        body = [b for n, _, _, b in got if n == "Cansin Köktürk"][0]
        self.assertIn("Schwangerschaftsabbruch", body)
        self.assertIn("Selbstbestimmung", body)
        self.assertNotIn("Elterngeld", body, "the speech ran into the next one")

    def test_the_party_is_taken_verbatim(self):
        got, _ = sp.parse_speeches(PROTOCOL)
        self.assertEqual([p for n, p, _, _ in got if n == "Cansin Köktürk"][0],
                         "Die Linke")


class AttributionTests(unittest.TestCase):
    """A speech belongs to the person who gave it, or to nobody."""

    def setUp(self):
        sp.resolve_person.__defaults__[0].clear()   # the module-level cache
        sp._register.__defaults__[0].clear()

    def test_a_title_in_the_protocol_still_resolves(self):
        """The Bericht prints "Dr. Dietmar Bartsch"; abgeordnetenwatch stores
        "Dietmar Bartsch". That mismatch left 32 of 125 speeches
        unattributed on the first live run, every one of them a member we
        hold."""
        conn = _conn()
        _member(conn, "p1", "Dietmar Bartsch")
        self.assertEqual(sp.resolve_person(conn, "Dr. Dietmar Bartsch",
                                           "Die Linke"), "p1")

    def test_two_members_sharing_a_name_resolve_to_nobody(self):
        """THE RULE. A guess here puts words in the mouth of someone who did
        not say them."""
        conn = _conn()
        _member(conn, "p1", "Michael Müller")
        _member(conn, "p2", "Michael Müller", party="CDU/CSU")
        self.assertIsNone(sp.resolve_person(conn, "Michael Müller", "SPD"))

    def test_an_unknown_speaker_resolves_to_nobody_rather_than_the_nearest(self):
        conn = _conn()
        _member(conn, "p1", "Dietmar Bartsch")
        self.assertIsNone(sp.resolve_person(conn, "Karin Prien", None))

    def test_the_stored_name_keeps_the_protocols_own_wording(self):
        """match_key is a JOIN KEY, not a rename. The title is stripped for
        comparison and kept in the record."""
        self.assertEqual(sp.match_key("Dr. Dietmar Bartsch"),
                         "dietmar bartsch")
        got, _ = sp.parse_speeches(PROTOCOL)
        self.assertIn("Dr. Dietmar Bartsch", [n for n, _, _, _ in got])


def _mandate(conn, pid, name, legislature):
    conn.execute(
        "INSERT INTO de_members (person_id, name, party, parliament, "
        "parliament_label, legislature, first_seen, last_seen) VALUES "
        "(?,?,?,?,?,?,?,?)",
        (pid, name, "AfD", "5", "Bundestag", legislature, TODAY, TODAY))
    conn.commit()


def _registered(conn, mdb_id, vorname, nachname, wps, praefix="", ort=""):
    conn.execute(
        "INSERT INTO de_mdb (mdb_id, nachname, vorname, ortszusatz, praefix, "
        "first_wp, last_wp, captured_at) VALUES (?,?,?,?,?,?,?,?)",
        (mdb_id, nachname, vorname, ort, praefix, min(wps), max(wps), TODAY))
    for wp in wps:
        conn.execute("INSERT INTO de_mdb_terms (mdb_id, wp) VALUES (?,?)",
                     (mdb_id, wp))
    conn.commit()


class OnePersonSeveralMandatesTests(unittest.TestCase):
    """27 September 2026: de_members holds a row per MANDATE, so storing the
    2017-21 term beside 2025-29 left 2,609 of 5,386 speeches unattributed.
    The register decides whether several mandates are one person."""

    def setUp(self):
        sp.resolve_person.__defaults__[0].clear()
        sp._register.__defaults__[0].clear()

    def test_one_person_in_two_terms_takes_the_latest_mandate(self):
        conn = _conn()
        _mandate(conn, "m111", "Beatrix von Storch", "111")
        _mandate(conn, "m161", "Beatrix von Storch", "161")
        _registered(conn, "1", "Beatrix", "Storch", {19, 20, 21}, praefix="von")
        self.assertEqual(sp.resolve_person(conn, "Beatrix von Storch", "AfD"), "m161")

    def test_two_people_of_one_name_in_different_terms_are_told_apart(self):
        """Only the mandate from the term the register puts ONE of them in
        can be theirs; here both terms are split, so each is unambiguous but
        the speaker is not -- nobody."""
        conn = _conn()
        _mandate(conn, "a", "Michael Müller", "97")
        _mandate(conn, "b", "Michael Müller", "161")
        _registered(conn, "1", "Michael", "Müller", {18})
        _registered(conn, "2", "Michael", "Müller", {21})
        self.assertIsNone(sp.resolve_person(conn, "Michael Müller", "SPD"))

    def test_a_place_suffix_picks_the_person_the_register_names(self):
        conn = _conn()
        _mandate(conn, "cm", "Carsten Müller", "161")
        _registered(conn, "1", "Carsten", "Müller", {21}, ort="Braunschweig")
        _registered(conn, "2", "Carsten", "Müller", {14})
        self.assertEqual(
            sp.resolve_person(conn, "Carsten Müller (Braunschweig)", "CDU/CSU"), "cm")

    def test_a_shared_name_in_the_same_term_is_still_nobody(self):
        conn = _conn()
        _mandate(conn, "x", "Dagmar Schmidt", "161")
        _registered(conn, "1", "Dagmar", "Schmidt", {21}, ort="Wetzlar")
        _registered(conn, "2", "Dagmar", "Schmidt", {21}, ort="Meißen")
        self.assertIsNone(sp.resolve_person(conn, "Dagmar Schmidt", "SPD"))

    def test_without_the_register_the_old_rule_stands(self):
        conn = _conn()
        _mandate(conn, "m111", "Stephan Brandner", "111")
        _mandate(conn, "m161", "Stephan Brandner", "161")
        self.assertIsNone(sp.resolve_person(conn, "Stephan Brandner", "AfD"))


class MemberRepairTests(unittest.TestCase):
    """The two data bugs the speeches work uncovered in de_members."""

    def test_the_welded_legislature_is_stripped_from_names_and_parties(self):
        """abgeordnetenwatch labels a mandate "Sanae Abdi (Bundestag 2025 -
        2029)" and a fraction "SPD (Bundestag 2025 - 2029)". Stored raw, the
        edition's Fraktion splits would have read "SPD (Bundestag 2025 -
        2029) 2/1/0"."""
        self.assertEqual(rc.clean_label("Sanae Abdi (Bundestag 2025 - 2029)"),
                         "Sanae Abdi")
        self.assertEqual(rc.clean_label("SPD (Bundestag 2025 - 2029)"), "SPD")

    def test_a_real_bracket_in_a_name_is_left_alone(self):
        """Only a bracket containing a YEAR RANGE is a legislature label."""
        self.assertEqual(rc.clean_label("Hans Meier (CSU)"), "Hans Meier (CSU)")
        self.assertEqual(rc.clean_label("Karl-Theodor zu Guttenberg"),
                         "Karl-Theodor zu Guttenberg")

    def test_the_parliament_is_derived_from_the_members_own_votes(self):
        """637 Bundestag members carried parliament NULL: they were stored
        before the column existed and the upsert's DO UPDATE never set it, so
        every later run hit the conflict branch and left it empty."""
        conn = _conn()
        conn.execute(
            "INSERT INTO de_members (person_id, name, party, first_seen, "
            "last_seen) VALUES ('p1','Sanae Abdi (Bundestag 2025 - 2029)',"
            "'SPD (Bundestag 2025 - 2029)',?,?)", (TODAY, TODAY))
        conn.execute(
            "INSERT INTO de_divisions (vote_id, parliament, parliament_label, "
            "date, label, first_seen, last_seen) VALUES "
            "('v1','5','Bundestag','2026-09-10','X',?,?)", (TODAY, TODAY))
        conn.execute("INSERT INTO de_votes VALUES ('v1','p1','yes')")
        conn.commit()
        cleaned, filled, ambiguous = rc.repair_members(conn, TODAY,
                                                       log=lambda *a: None)
        self.assertEqual((cleaned, filled, ambiguous), (1, 1, 0))
        row = conn.execute("SELECT name, party, parliament FROM de_members "
                           "WHERE person_id='p1'").fetchone()
        self.assertEqual(tuple(row), ("Sanae Abdi", "SPD", "5"))

    def test_a_member_voting_in_two_parliaments_is_left_null(self):
        """A wrong parliament is worse than a missing one: it would put a
        Landtag member into the Bundestag's Fraktion splits."""
        conn = _conn()
        conn.execute("INSERT INTO de_members (person_id, name, first_seen, "
                     "last_seen) VALUES ('p1','X',?,?)", (TODAY, TODAY))
        for vid, parl in (("v1", "5"), ("v2", "13")):
            conn.execute(
                "INSERT INTO de_divisions (vote_id, parliament, date, label, "
                "first_seen, last_seen) VALUES (?,?,?,?,?,?)",
                (vid, parl, "2026-09-10", "X", TODAY, TODAY))
            conn.execute("INSERT INTO de_votes VALUES (?,'p1','yes')", (vid,))
        conn.commit()
        _, filled, ambiguous = rc.repair_members(conn, TODAY,
                                                 log=lambda *a: None)
        self.assertEqual((filled, ambiguous), (0, 1))
        self.assertIsNone(conn.execute("SELECT parliament FROM de_members "
                                       "WHERE person_id='p1'").fetchone()[0])


class DisclosureTests(unittest.TestCase):
    def test_a_protocol_row_is_written_even_when_nothing_matched(self):
        """"No speech on our ground in September" and "September was never
        read" must not be the same empty query."""
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "de_monitor", os.path.join(ROOT, "tools", "de_monitor.py"))
        mon = iu.module_from_spec(spec)
        spec.loader.exec_module(mon)
        conn = _conn()
        conn.execute("INSERT INTO de_protocols (protocol, date, speeches, "
                     "matched, chars, read_on) VALUES ('21/94','2026-09-11',"
                     "101,0,368736,?)", (TODAY,))
        conn.commit()
        rows, (protos, first, last) = mon.speeches(conn, TODAY)
        self.assertEqual(rows, [])
        self.assertEqual(protos, 1)

    def test_an_unattributed_speaker_is_flagged_in_the_edition(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "de_monitor", os.path.join(ROOT, "tools", "de_monitor.py"))
        mon = iu.module_from_spec(spec)
        spec.loader.exec_module(mon)
        import tempfile
        conn = _conn()
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "party, role, person_id, excerpt, areas, tier, first_seen, "
            "last_seen) VALUES ('s1','21/94','2026-09-22','Karin Prien',NULL,"
            "'minister',NULL,'Etwas','[1]',1,?,?)", (TODAY, TODAY))
        conn.commit()
        old = mon.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "editions"))
            mon.ROOT = tmp
            try:
                path = mon.render_edition(conn, TODAY)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            finally:
                mon.ROOT = old
        self.assertIn("Karin Prien", text)
        self.assertIn("not matched to a member", text)



class BackfillWindowTests(unittest.TestCase):
    """--until and the page cap (26 September 2026): the first backfill to
    2020 read the newest 188 of ~400 protocols and could never have read
    more, because the pager stopped at 20 pages and re-reading the same
    `since` pages the same newest documents again."""

    def _capture(self, limit, until=None):
        seen = {}

        def fake_pages(client, path, key, **kw):
            seen.update(kw)
            return iter([])

        real = sp.dip.pages
        sp.dip.pages = fake_pages
        try:
            sp.protocols(None, "k", "2020-01-01", limit, log=lambda *a: None, until=until)
        finally:
            sp.dip.pages = real
        return seen

    def test_until_becomes_the_dip_end_date(self):
        seen = self._capture(450, until="2023-11-15")
        self.assertEqual(seen["f.datum.start"], "2020-01-01")
        self.assertEqual(seen["f.datum.end"], "2023-11-15")

    def test_no_until_sends_no_end_date(self):
        self.assertNotIn("f.datum.end", self._capture(20))

    def test_the_page_cap_scales_with_the_limit(self):
        """Ten documents a page: a limit of 450 needs more than 20 pages."""
        self.assertGreaterEqual(self._capture(450)["limit_pages"], 46)
        self.assertEqual(self._capture(20)["limit_pages"], 20)


if __name__ == "__main__":
    unittest.main()
