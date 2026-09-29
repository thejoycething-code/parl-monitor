"""The German 5CA (tools/de_5ca.py) and what feeds it (29 September 2026).

Built from a hand-run sample Christopher reviewed, and every rule below is a
mistake that sample made first:

  * 638 members in a 630-seat House: departed members kept rows in
    de_members. The sheet lists SITTING members only, from a roster check,
    and refuses to run without one.
  * Ten SPD members at ++ for whipped 2019 Nein votes, who co-sponsored
    decriminalisation in 2024. A vote is one act among equals; the side is a
    clear majority of events, else the most recent.
  * Two same-day § 219a divisions counted twice against one later bill.
  * Ulle Schauws at "-" with 35 consistent items, because the latest speech
    scored -1. The column is the strongest statement on the side.
  * Tarek Al-Wazir (Greens) at ++ for a Nein inside Hesse's CDU-Green
    coalition. An earlier-parliament act against the party line never places.
  * 24 Linke members in the 0 column for Anfragen whose side nobody judged.
  * DIP ignoring f.vorgang and answering with the global feed.
  * A Fraktion paper's two leaders counted as its authors.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, de_names  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


five = _load("de_5ca")
auth = _load("de_authorship")
prof = _load("de_profiles")
rollcalls = _load("de_rollcalls")
import datetime  # noqa: E402

TODAY = datetime.date(2026, 9, 29)


# -- names -----------------------------------------------------------------------

class NameFoldingTests(unittest.TestCase):
    PAIRS = [("Jürgen Kögel", "Jürgen Koegel"), ("Rainer Gross", "Rainer Groß"),
             ("Cansın Köktürk", "Cansin Köktürk"),
             ("Christian von Stetten", "Christian Frhr. von Stetten"),
             ("Philip Hoffmann", "Philip M. A. Hoffmann"),
             ("Michael „Moses“ Arndt", "Michael Arndt"),
             ("Dr.-Ing. Zoe Mayer", "Zoe Mayer"),
             ("Reem Alabali Radovan", "Reem Alabali-Radovan"),
             ("Michael Brand (Fulda)", "Michael Brand")]

    def test_every_measured_spelling_pair_meets(self):
        for a, b in self.PAIRS:
            self.assertEqual(de_names.key(a), de_names.key(b), (a, b))

    def test_a_two_column_signer_line_does_not_invent_a_person(self):
        line = de_names.fold("Peter Aumer Markus Kurth")
        self.assertTrue(de_names.found_in("Markus Kurth", line))
        self.assertTrue(de_names.found_in("Peter Aumer", line))
        self.assertFalse(de_names.found_in("Peter Kurth", line))

    def test_party_families_across_parliaments(self):
        self.assertEqual(de_names.party_family("CSU"), "union")
        self.assertEqual(de_names.party_family("CDU/CSU"), "union")
        self.assertEqual(de_names.party_family("EVP"), "union")
        self.assertEqual(de_names.party_family("BÜNDNIS 90/\xadDIE GRÜNEN"), "gruene")
        self.assertEqual(de_names.party_family("Grüne/EFA"), "gruene")
        self.assertIsNone(de_names.party_family("fraktionslos"))


# -- authorship -----------------------------------------------------------------

GROUP_TEXT = ("Entwurf eines Gesetzes ...\nBerlin, den 14. November 2024\n"
              "Carmen Wegge\nUlle Schauws\nCorinna Rüffer Dr. Hendrik Hoppenstedt\n"
              "Begründung\nA. Allgemeiner Teil")
FRAKTION_TEXT = ("Antrag\nder Abgeordneten Beatrix von Storch, Udo Theodor Hemmelgarn, "
                 "Dr. Malte Kaufmann und der Fraktion der AfD\nFörderung ...\n"
                 "Berlin, den 3. März 2026\nDr. Alice Weidel, Tino Chrupalla und Fraktion\n")


class AuthorshipParsingTests(unittest.TestCase):
    def test_a_fraktion_papers_authors_come_from_its_cover(self):
        self.assertEqual(auth.cover_authors(FRAKTION_TEXT),
                         ["Beatrix von Storch", "Udo Theodor Hemmelgarn", "Dr. Malte Kaufmann"])

    def test_the_leaders_signature_is_never_a_signer_block(self):
        self.assertEqual(auth.signer_block(FRAKTION_TEXT), "")

    def test_a_group_papers_signers_include_a_two_column_line(self):
        block = auth.signer_block(GROUP_TEXT)
        known = ["Carmen Wegge", "Ulle Schauws", "Corinna Rüffer", "Hendrik Hoppenstedt",
                 "Karl Lauterbach"]
        self.assertEqual(auth.names_in_block(block, known),
                         ["Carmen Wegge", "Corinna Rüffer", "Hendrik Hoppenstedt", "Ulle Schauws"])

    def test_a_reply_for_another_vorgang_records_nothing(self):
        class Client:
            def get_json(self, url, feed, slug, archive=True):
                return {"documents": [{"id": "1", "vorgang_id": "999"}], "cursor": "x"}
        logs = []
        self.assertIsNone(auth.positions(Client(), "k", "317619", log=logs.append))
        self.assertIn("filter was ignored", logs[0])

    def test_a_question_and_its_answer_are_one_position(self):
        self.assertEqual(auth.authored_type({"vorgangsposition":
                         "Schriftliche Frage/Schriftliche Antwort"}), "Schriftliche Frage")
        self.assertIsNone(auth.authored_type({"vorgangsposition": "Beratung"}))

    def test_a_complete_activity_list_is_used_as_printed(self):
        p = {"aktivitaet_anzahl": 1, "aktivitaet_anzeige": [
            {"aktivitaetsart": "Frage", "titel": "Hubert Hüppe, MdB, CDU/CSU"}]}
        self.assertEqual(auth.authors_of(None, "k", p, []), [("Hubert Hüppe", "activity")])


# -- roster ---------------------------------------------------------------------

def _conn():
    return db.init_db(db.connect(":memory:"))


def _member(conn, pid, name, party, legislature="161", parliament="5", sitting=None):
    conn.execute("INSERT INTO de_members (person_id, name, party, parliament, legislature, "
                 "sitting, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?)",
                 (pid, name, party, parliament, legislature, sitting, "2026-09-22", "2026-09-22"))


class RosterClient:
    def __init__(self, mandates, fail=False):
        self.mandates, self.fail = mandates, fail

    def get_json(self, url, feed, slug, archive=True):
        if self.fail:
            raise ValueError("boom")
        return {"data": self.mandates}


def _mandate(mid, name):
    return {"id": int(mid), "politician": {"id": 1000 + int(mid), "label": name,
                                           "abgeordnetenwatch_url": "https://x/" + mid},
            "electoral_data": {"mandate_won": "list",
                               "electoral_list": {"label": "Landesliste Berlin"}},
            "fraction_membership": [{"fraction": {"label": "SPD (Bundestag 2025 - 2029)"}}]}


class RosterTests(unittest.TestCase):
    def test_departed_members_are_unseated_and_a_successor_added(self):
        conn = _conn()
        for i in range(1, 11):
            _member(conn, str(i), "Member {0}".format(i), "SPD")
        current = [_mandate(str(i), "Member {0}".format(i)) for i in range(1, 10)]
        current.append(_mandate("42", "Katrin Zschau"))
        sitting, left, added, _ = prof.mark_sitting(conn, RosterClient(current), "2026-09-29",
                                                    log=lambda *a: None)
        self.assertEqual((sitting, left, added), (10, ["10"], 1))
        self.assertEqual(conn.execute("SELECT sitting FROM de_members WHERE person_id='10'").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT party FROM de_members WHERE person_id='42'").fetchone()[0], "SPD")

    def test_a_short_roster_is_a_failed_fetch_and_marks_nobody(self):
        conn = _conn()
        for i in range(1, 11):
            _member(conn, str(i), "Member {0}".format(i), "SPD")
        got = prof.mark_sitting(conn, RosterClient([_mandate("1", "Member 1")]), "2026-09-29",
                                log=lambda *a: None)
        self.assertIsNone(got)
        self.assertIsNone(conn.execute("SELECT sitting FROM de_members WHERE person_id='2'").fetchone()[0])

    def test_a_failed_page_marks_nobody(self):
        conn = _conn()
        _member(conn, "1", "Member 1", "SPD")
        self.assertIsNone(prof.mark_sitting(conn, RosterClient([], fail=True), "2026-09-29",
                                            log=lambda *a: None))


class RollcallParliamentTests(unittest.TestCase):
    def test_a_land_legislature_is_filed_under_its_own_parliament(self):
        class C:
            def get_json(self, url, feed, slug, archive=True):
                return {"data": {"parliament": {"id": 13, "label": "Bayern"}}}
        self.assertEqual(rollcalls.period_parliament(C(), "99"), ("13", "Bayern"))

    def test_an_unknown_legislature_names_no_parliament(self):
        class C:
            def get_json(self, url, feed, slug, archive=True):
                return {"data": {}}
        self.assertEqual(rollcalls.period_parliament(C(), "99"), (None, None))


# -- placement -------------------------------------------------------------------

def ev(kind, date, value, earlier=False):
    return {"kind": kind, "date": date, "value": value, "line": kind, "earlier": earlier}


class PlacementTests(unittest.TestCase):
    def test_a_later_bill_beats_an_older_whipped_vote(self):
        best, col, conf = five.place([ev("bill", "2024-11-14", -2), ev("vote", "2019-02-21", 2)])
        self.assertEqual(col, "--")
        self.assertIn("conflicting", conf)

    def test_two_same_day_divisions_are_one_event(self):
        items = [ev("vote", "2019-02-21", 2), ev("vote", "2019-02-21", 2),
                 ev("speech", "2024-04-24", 1), ev("bill", "2024-11-14", -2)]
        self.assertEqual(five.place(items)[1], "--")

    def test_a_clear_majority_outvotes_one_recent_speech(self):
        items = [ev("speech", "2026-02-25", 1)] + [ev("bill", "2024-11-14", -2)] + \
                [ev("speech", "2024-0{0}-01".format(m), -2) for m in range(1, 7)]
        self.assertEqual(five.place(items)[1], "--")

    def test_the_column_is_the_strongest_statement_on_the_side(self):
        items = [ev("speech", "2026-05-06", -1)] + [ev("speech", "2025-01-0{0}".format(d), -2)
                                                    for d in range(1, 5)]
        self.assertEqual(five.place(items)[1], "--")

    def test_a_motion_places_only_without_anything_stronger(self):
        self.assertEqual(five.place([ev("motion", "2026-01-28", 1)])[1], "+")
        self.assertEqual(five.place([ev("motion", "2026-01-28", 1),
                                     ev("speech", "2024-01-01", -2)])[1], "--")

    def test_an_unjudged_item_is_not_the_zero_column(self):
        best, col, conf = five.place([ev("question", "2026-03-01", None)])
        self.assertIsNone(col)
        self.assertEqual(conf, "on record, side not placed")

    def test_a_neutral_speech_is_the_zero_column(self):
        self.assertEqual(five.place([ev("speech", "2026-03-01", 0)])[1], "0")


# -- the whole sheet --------------------------------------------------------------

def _stance(draft=True):
    return {"divisions": [
        {"key": "5628", "area": 1, "draft": draft, "ja": -2, "nein": 2,
         "why_ja": "for buffer zones", "why_nein": "against buffer zones"},
        {"key": "5236", "area": 1, "draft": draft, "ja": -2, "nein": 2,
         "why_ja": "for protest zones", "why_nein": "against protest zones"}],
        "papers": []}


def _sheet_db():
    conn = _conn()
    # Twelve Greens who voted Ja on the Bundestag buffer-zone law; one of them
    # (Al-Wazir) voted Nein on Hesse's in coalition; a departed Green.
    for i in range(12):
        _member(conn, "g{0}".format(i), "Grün Nummer{0}".format(i), "BÜNDNIS 90/DIE GRÜNEN", sitting=1)
    _member(conn, "alw", "Tarek Al-Wazir", "BÜNDNIS 90/DIE GRÜNEN", sitting=1)
    _member(conn, "gone", "Annalena Baerbock", "BÜNDNIS 90/DIE GRÜNEN", sitting=0)
    _member(conn, "h1", "Tarek Al-Wazir", "BÜNDNIS 90/DIE GRÜNEN", legislature="116", parliament="11")
    # A Bavarian namesake from another party must not attach.
    _member(conn, "b1", "Grün Nummer0", "AfD", legislature="99", parliament="13")
    conn.execute("INSERT INTO de_divisions (vote_id, parliament, parliament_label, legislature, "
                 "date, label, first_seen, last_seen) VALUES "
                 "('5628','5',NULL,'132','2024-07-05','Gehsteigbelästigung','x','x'),"
                 "('5236','11','Hessen','116','2023-07-20','Schutzzonen','x','x')")
    for i in range(12):
        conn.execute("INSERT INTO de_votes (vote_id, person_id, position) VALUES ('5628', ?, 'yes')",
                     ("g{0}".format(i),))
    conn.execute("INSERT INTO de_votes (vote_id, person_id, position) VALUES ('5628','gone','yes')")
    conn.execute("INSERT INTO de_votes (vote_id, person_id, position) VALUES ('5236','h1','no')")
    conn.execute("INSERT INTO de_votes (vote_id, person_id, position) VALUES ('5236','b1','no')")
    return conn


class SheetTests(unittest.TestCase):
    def _rows(self, conn, stance, preview):
        sitting = five.roster(conn)
        e, _ = five.gather(conn, 1, sitting, stance, {}, preview)
        return {r["name"].split(" (")[0]: r for r in five.build_rows(sitting, e, TODAY)}

    def test_no_roster_check_no_sheet(self):
        conn = _conn()
        _member(conn, "1", "Member 1", "SPD")
        self.assertIsNone(five.roster(conn))

    def test_only_sitting_members_are_listed(self):
        rows = self._rows(_sheet_db(), _stance(), preview=True)
        self.assertNotIn("Annalena Baerbock", rows)
        self.assertEqual(len(rows), 13)

    def test_a_draft_reading_places_nobody(self):
        rows = self._rows(_sheet_db(), _stance(draft=True), preview=False)
        self.assertTrue(all(r["column"] is None for r in rows.values()))
        self.assertIn("reading DRAFT", rows["Grün Nummer1"]["comments"])

    def test_a_confirmed_reading_places(self):
        rows = self._rows(_sheet_db(), _stance(draft=False), preview=False)
        self.assertEqual(rows["Grün Nummer1"]["column"], "--")

    def test_a_coalition_vote_against_the_party_line_is_shown_not_placed(self):
        rows = self._rows(_sheet_db(), _stance(draft=False), preview=False)
        self.assertIsNone(rows["Tarek Al-Wazir"]["column"])
        self.assertIn("coalition discipline", rows["Tarek Al-Wazir"]["confidence"])
        self.assertIn("Hessen", rows["Tarek Al-Wazir"]["comments"])

    def test_a_namesake_from_another_party_does_not_attach(self):
        rows = self._rows(_sheet_db(), _stance(draft=False), preview=False)
        self.assertNotIn("Schutzzonen", rows["Grün Nummer0"]["comments"])


class SharedDrucksacheTests(unittest.TestCase):
    """Written questions are printed several to a Drucksache (20/10565):
    one member's two questions there are two acts, in the table and on the
    sheet."""

    def test_two_questions_in_one_drucksache_are_both_kept_and_both_count(self):
        conn = _conn()
        _member(conn, "p1", "Hubert Hüppe", "CDU/CSU", sitting=1)
        for vid in ("A", "B"):
            conn.execute("INSERT INTO de_authorship (nummer, author, vorgang_id, art, datum, "
                         "titel, source, first_seen, last_seen) VALUES "
                         "('20/10565','Hubert Hüppe',?,'Schriftliche Frage','2024-02-01','t',"
                         "'activity','x','x')", (vid,))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM de_authorship").fetchone()[0], 2)
        stance = {"divisions": [], "papers": [
            {"key": "A", "area": 1, "authored": 1},
            {"key": "B", "area": 1, "authored": 1}]}
        sitting = five.roster(conn)
        e, counts = five.gather(conn, 1, sitting, stance, {}, preview=False)
        self.assertEqual(counts["papers"], 2)


class AuthorshipKeyMigrationTests(unittest.TestCase):
    def test_an_old_key_is_rebuilt_and_its_rows_kept(self):
        conn = db.connect(":memory:")
        conn.execute("CREATE TABLE de_authorship (nummer TEXT NOT NULL, author TEXT NOT NULL, "
                     "wahlperiode TEXT, vorgang_id TEXT, art TEXT, datum TEXT, titel TEXT, "
                     "source TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, "
                     "PRIMARY KEY (nummer, author))")
        conn.execute("INSERT INTO de_authorship VALUES ('20/10565','Hubert Hüppe','20','A',"
                     "'Schriftliche Frage','2024-02-01','t','activity','x','x')")
        conn.commit()
        db.init_db(conn)
        db.init_db(conn)
        pk = [r[1] for r in sorted(conn.execute("PRAGMA table_info(de_authorship)"),
                                   key=lambda r: r[5]) if r[5]]
        self.assertEqual(pk, ["nummer", "vorgang_id", "author"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM de_authorship").fetchone()[0], 1)


class LandRecordAreaTests(unittest.TestCase):
    def test_a_land_item_counts_only_on_its_own_area(self):
        conn = _conn()
        _member(conn, "p1", "Stefan Möller", "AfD", sitting=1)
        land = {"members": [{"name": "Stefan Möller", "parliament": "Thüringen", "items": [
            {"date": "2018-12-14", "kind": "speech", "area": 1, "value": 2, "doc": "PlPr 6/135", "url": "u"}]}]}
        sitting = five.roster(conn)
        on1, _ = five.gather(conn, 1, sitting, {}, land, preview=False)
        on7, _ = five.gather(conn, 7, sitting, {}, land, preview=False)
        self.assertEqual(len(on1["p1"]), 1)
        self.assertEqual(on7["p1"], [])


class RealConfigTests(unittest.TestCase):
    def test_the_real_stance_files_load_and_every_reading_is_signed(self):
        """Christopher confirmed every reading as drafted on 29 September 2026.
        Fails the day one goes back to draft -- check a HUMAN put the flag back,
        and that the sheet is meant to lose those placements."""
        stance = five.load_yaml(five.STANCE_PATH)
        land = five.load_yaml(five.LAND_PATH)
        entries = list(stance["divisions"]) + list(stance["papers"])
        entries += [i for m in land["members"] for i in m.get("items") or []]
        self.assertTrue(entries)
        self.assertEqual({five.status(e) for e in entries}, {"confirmed", "unplaceable"})

    def test_every_land_item_names_its_document(self):
        for m in five.load_yaml(five.LAND_PATH)["members"]:
            self.assertTrue(m.get("searched"), m["name"])
            for i in m.get("items") or []:
                self.assertTrue(i.get("doc") and i.get("url"), (m["name"], i.get("date")))

    def test_every_paper_and_division_has_an_area_and_a_key(self):
        stance = five.load_yaml(five.STANCE_PATH)
        for e in stance["divisions"] + stance["papers"]:
            self.assertTrue(e.get("key") and e.get("area"), e)


if __name__ == "__main__":
    unittest.main()
