"""The German debate pack.

Every number in these tests was measured against protocol 21/96 and the
Mediathek's listing for sitting 96 on 25 September 2026, not assumed.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import de_debatepack as dp, de_protocol  # noqa: E402


# One entry as the Mediathek serves it, trimmed to the fields we read.
def _entry(videoid, clock, name, role, whole=False):
    return (
        '<a href="https://www.bundestag.de/mediathek/video?videoid={vid}">'
        '<div class="bt-teaser-person">'
        '<p class="bt-teaser-person-time"><i class="icon-time"></i>{clock}</p>'
        '{gesamt}'
        '<p>{name}</p><p>&copy;&nbsp;Photographer</p><p>{role}</p>'
        '</div></a>'
    ).format(vid=videoid, clock=clock, name=name, role=role,
             gesamt="<span>Gesamter TOP</span>" if whole else "")


PAGE = (
    '<div class="meta-slider" data-hits="309" data-nextoffset="8" data-limit="8">'
    '<h3 class="col-xs-12 bt-top-headline">'
    '<span class="bt-dachzeile">24.09.2026</span>'
    '96. Sitzung TOP 9 &Auml;nderung des Transplantationsgesetzes</h3></div>'
    + _entry("7657221", "12:29:27", "Josephine Ortleb", "Bundestagsvizepr&auml;sidentin")
    + _entry("7657220", "12:23:42", "Elisabeth Winkelmeier-Becker", "CDU/CSU")
    + _entry("7657219", "12:17:49", "Michael Brand", "CDU/CSU")
    + _entry("7657207", "11:23:00", "Blick in den Plenarsaal", "", whole=True)
)


class MediaParseTests(unittest.TestCase):
    def test_entries_carry_speaker_party_and_a_wall_clock(self):
        rows = dp.parse_media_page(PAGE)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1]["videoid"], "7657220")
        self.assertEqual(rows[1]["clock"], "12:23:42")
        self.assertEqual(rows[1]["speaker"], "Elisabeth Winkelmeier-Becker")
        self.assertEqual(rows[1]["party"], "CDU/CSU")

    def test_the_whole_debate_entry_is_marked_not_taken_for_a_speaker(self):
        """Its person block carries the generic plenary photo's caption
        where a name would be, so it put a photograph in the speaker list."""
        rows = dp.parse_media_page(PAGE)
        self.assertTrue(rows[3]["whole_top"])
        self.assertEqual(rows[3]["speaker"], "")
        self.assertEqual(dp.whole_debate_video(rows)["videoid"], "7657207")

    def test_the_sitting_total_is_read_from_the_page(self):
        """8 rows come back whatever limit says; data-hits is how the caller
        knows to keep paging."""
        self.assertEqual(dp.media_hits(PAGE), 309)

    def test_the_agenda_heading_is_carried_on_every_entry(self):
        rows = dp.parse_media_page(PAGE)
        self.assertIn("Transplantationsgesetzes", rows[0]["top"])


class SurnameTests(unittest.TestCase):
    """The two sources disagree on name order and on what else is in the
    name, and the join is only as good as this."""

    def test_both_orders_key_the_same(self):
        self.assertEqual(dp.surname("Michael Brand"), "brand")
        self.assertEqual(dp.surname("Brand, Michael"), "brand")

    def test_a_constituency_suffix_is_not_the_surname(self):
        """The Bericht prints "Michael Brand (Fulda)" to tell two members
        apart; the last word would be "(fulda)" and match nobody."""
        self.assertEqual(dp.surname("Michael Brand (Fulda)"), "brand")

    def test_a_role_after_the_comma_is_not_the_surname(self):
        self.assertEqual(
            dp.surname("Karl-Josef Laumann, Minister (Nordrhein-Westfalen)"),
            "laumann")

    def test_titles_are_ignored(self):
        self.assertEqual(dp.surname("Dr. Konrad Körner"), "körner")


class ChairTests(unittest.TestCase):
    def test_the_presiding_officer_is_not_a_speaker(self):
        """Josephine Ortleb had three Mediathek entries in one debate, all of
        them calling the next speaker. Listed as speakers they were then
        reported as text the protocol could not find."""
        self.assertTrue(dp.is_chair("Bundestagsvizepräsidentin"))
        self.assertTrue(dp.is_chair("Vizepräsident"))
        self.assertFalse(dp.is_chair("CDU/CSU"))
        self.assertFalse(dp.is_chair(""))


class AlignmentTests(unittest.TestCase):
    """The protocol is the WHOLE sitting day. Keying on surname alone took
    the first speech by that name anywhere in it."""

    def _speeches(self, names):
        return [{"speaker": n, "party": "X", "role": "member",
                 "body": "body of " + n, "excerpt": n} for n in names]

    def test_it_takes_the_run_that_matches_the_order(self):
        speeches = self._speeches([
            "Michael Brand", "Someone Else",           # an earlier debate
            "Sabine Dittmar", "Martin Sichert", "Michael Brand",  # ours
        ])
        speakers = [{"speaker": "Dittmar, Sabine"},
                    {"speaker": "Sichert, Martin"},
                    {"speaker": "Brand, Michael"}]
        bodies, matched = dp.align_bodies(speakers, speeches)
        self.assertEqual(matched, 3)
        self.assertEqual(bodies[2]["body"], "body of Michael Brand")
        self.assertEqual(bodies[0]["body"], "body of Sabine Dittmar")

    def test_a_speaker_the_protocol_lacks_borrows_nobody_elses_words(self):
        """A Vorabfassung omits whole agenda items. The row stays, the body
        does not appear from somewhere else."""
        speeches = self._speeches(["Sabine Dittmar", "Martin Sichert"])
        speakers = [{"speaker": "Dittmar, Sabine"},
                    {"speaker": "Laumann, Karl-Josef"},
                    {"speaker": "Sichert, Martin"}]
        bodies, matched = dp.align_bodies(speakers, speeches)
        self.assertEqual(matched, 2)
        self.assertNotIn(1, bodies)

    def test_nothing_to_align_is_not_an_error(self):
        self.assertEqual(dp.align_bodies([], []), ({}, 0))


class TopicTermTests(unittest.TestCase):
    def test_stems_not_words(self):
        """German compounds: the heading says "Transplantationsgesetzes" and
        the speeches say "Transplantation" and "Organtransplantation".
        Matching the heading's word verbatim found NOTHING in a debate
        entirely about it."""
        terms = dp.topic_terms(
            "24.09.2026 96. Sitzung TOP 9 Änderung des Transplantationsgesetzes")
        self.assertEqual(terms, ["Transplantat"])
        found = dp.sentences_matching(
            "Die Transplantation im Februar glueckte und half sehr vielen "
            "Menschen weiter.", terms)
        self.assertEqual(len(found), 1)

    def test_the_boilerplate_of_a_heading_is_not_a_topic(self):
        self.assertEqual(dp.topic_terms("96. Sitzung TOP 41 Abschließende "
                                        "Beratungen ohne Aussprache"), [])


class TitleTests(unittest.TestCase):
    def test_the_date_and_sitting_are_not_repeated_in_the_name(self):
        self.assertEqual(
            dp.short_title("24.09.2026 96. Sitzung TOP 9 Neues Gesetz"),
            "Neues Gesetz")

    def test_umlauts_are_transliterated_not_dropped(self):
        """"Änderung" became "nderung" on the first real pack, which is not
        a word and not searchable."""
        self.assertEqual(
            dp.slug("24.09.2026 96. Sitzung TOP 9 Änderung des Transplantationsgesetzes"),
            "aenderung-des-transplantationsgesetzes")


class SpeakerRegexTests(unittest.TestCase):
    """Both forms were missing from the collector in production, not only
    from the packs: 5 headings in protocol 21/96."""

    def test_a_constituency_before_the_party(self):
        text = "Michael Brand (Fulda) (CDU/CSU):\nMeine Damen und Herren.\n"
        rows, _skipped = de_protocol.parse_speeches(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "CDU/CSU", "the party, not the constituency")

    def test_a_land_minister_speaking_for_the_bundesrat(self):
        """The Land name is hyphenated across a line break, which a plain
        [^\\n:] would not cross."""
        text = "Karl-Josef Laumann, Minister (Nordrhein-\nWestfalen):\nSehr geehrte Frau.\n"
        rows, _skipped = de_protocol.parse_speeches(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "minister")

    def test_an_ordinary_member_still_parses(self):
        text = "Cansin Köktürk (Die Linke):\nEs ist so.\n"
        rows, _skipped = de_protocol.parse_speeches(text)
        self.assertEqual([(r[0], r[1], r[2]) for r in rows],
                         [("Cansin Köktürk", "Die Linke", "member")])


class PackTests(unittest.TestCase):
    def _rows(self):
        return [{"speaker": "Sabine Dittmar", "party": "SPD", "role": "member",
                 "body": "So ist es im Transplantationsgesetz geregelt und gut.",
                 "excerpt": "So ist es...",
                 "video": {"videoid": "1", "clock": "11:25:25"}},
                {"speaker": "Nicht Gefunden", "party": "AfD", "role": "",
                 "body": "", "excerpt": "", "video": None}]

    def test_the_pack_writes_its_four_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = dp.write_pack({"title": "Neues Gesetz", "date": "2026-09-24",
                                    "sitzung": 96, "wahlperiode": 21},
                                   self._rows(), 1, ["Transplantat"], (9, 0),
                                   root=tmp)
            names = sorted(os.listdir(folder))
        self.assertEqual(names, ["README.md", "checklist.md", "quotes.md",
                                 "roundup.md", "shotlist.csv"])

    def test_the_readme_says_footage_is_linked_not_downloaded(self):
        """The Bundestag's terms are its own and we have not read them."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = dp.write_pack({"title": "T", "date": "2026-09-24",
                                    "sitzung": 96, "wahlperiode": 21},
                                   self._rows(), 1, [], None, root=tmp)
            with open(os.path.join(folder, "README.md")) as fh:
                text = fh.read()
        self.assertIn("LINKED, NOT DOWNLOADED", text)

    def test_a_speaker_without_a_recording_still_appears(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = dp.write_pack({"title": "T", "date": "2026-09-24",
                                    "sitzung": 96, "wahlperiode": 21},
                                   self._rows(), 1, [], None, root=tmp)
            with open(os.path.join(folder, "roundup.md")) as fh:
                roundup = fh.read()
        self.assertIn("Nicht Gefunden", roundup)
        self.assertIn("not found", roundup)

    def test_the_roundup_reads_no_direction(self):
        """Who is with us is the checklist's question and a human answers
        it. The pack must not pre-empt that."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = dp.write_pack({"title": "T", "date": "2026-09-24",
                                    "sitzung": 96, "wahlperiode": 21},
                                   self._rows(), 1, [], None, root=tmp)
            with open(os.path.join(folder, "roundup.md")) as fh:
                roundup = fh.read()
        self.assertIn("Direction is NOT read here", roundup)
        for word in ("With us", "Against us"):
            self.assertNotIn(word, roundup)

    def test_the_checklist_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = dp.write_pack({"title": "T", "date": "2026-09-24",
                                    "sitzung": 96, "wahlperiode": 21},
                                   self._rows(), 1, [], None, root=tmp)
            path = os.path.join(folder, "checklist.md")
            with open(path) as fh:
                text = fh.read().replace("ONSIDE: \n", "ONSIDE: yes\n", 1)
            with open(path, "w") as fh:
                fh.write(text)
            answered = dp.parse_checklist(path)
        self.assertEqual(answered, [("Sabine Dittmar", True, "")])

    def test_an_unanswered_line_is_not_agreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "checklist.md")
            with open(path, "w") as fh:
                fh.write("### speaker: A\nONSIDE: \nNOTE: \n")
            self.assertEqual(dp.parse_checklist(path), [])


if __name__ == "__main__":
    unittest.main()
