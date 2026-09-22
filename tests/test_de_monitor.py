"""The German edition (Christopher, 2026-09-21: "a section of the monitor
separate for the German team").

The invariants here are mostly DISCLOSURE invariants, and that is deliberate.
The German stack is English machinery reading German text, judged by a model
reasoning in English, through a taxonomy no German speaker has verified. Every
one of those is defensible alone and the stack can still be confidently wrong,
so what this file mostly locks is that the edition keeps SAYING so -- on its
face, every week, until the German team signs the taxonomy off.

The other half is the rule the Lords inversion bought: a recorded vote renders
its tallies and never a direction. Nobody should be able to add "the House
defended life" to this renderer without a test going red.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db


def _load():
    spec = importlib.util.spec_from_file_location(
        "de_monitor", os.path.join(ROOT, "tools", "de_monitor.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dm = _load()

TODAY = "2026-09-22"


def _conn():
    return db.init_db(db.connect(":memory:"))


def _vorgang(conn, vid, titel, areas="[1]", score=3, why="Because.",
             stand="Beschlossen"):
    conn.execute(
        "INSERT INTO de_vorgaenge (vorgang_id, wahlperiode, titel, "
        "vorgangstyp, sachgebiet, initiative, datum, stand, areas, tier, "
        "triage_score, why_it_matters, first_seen, last_seen) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (vid, "21", titel, "Gesetzgebung", "Recht", "Fraktion X",
         "2026-09-01", stand, areas, 1, score, why, TODAY, TODAY))
    conn.commit()


def _division(conn, vid, label, areas="[1]", yes=380, no=210, accepted=1,
              inherited=None, parliament="5"):
    conn.execute(
        "INSERT INTO de_divisions (vote_id, parliament, parliament_label, "
        "legislature, date, label, yes, no, abstain, absent, accepted, "
        "areas, tier, inherited_from, first_seen, last_seen) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (vid, parliament, "Bundestag" if parliament == "5" else "Landtag",
         "21", "2026-09-10", label, yes, no, 12, 31, accepted, areas, 1,
         inherited, TODAY, TODAY))
    conn.commit()


def _member(conn, pid, name, party, parliament="5"):
    conn.execute(
        "INSERT INTO de_members (person_id, name, party, parliament, "
        "parliament_label, legislature, first_seen, last_seen) VALUES "
        "(?,?,?,?,?,?,?,?)",
        (pid, name, party, parliament, "Bundestag", "21", TODAY, TODAY))
    conn.commit()


def _vote(conn, vid, pid, position):
    conn.execute("INSERT INTO de_votes (vote_id, person_id, position) "
                 "VALUES (?,?,?)", (vid, pid, position))
    conn.commit()


def _render(conn):
    """Render into a temp tree, NEVER the repo's own editions/.

    render_edition() writes to ROOT/editions/de-monitor-<date>.md, so a test
    calling it with fixture data and today's date silently overwrote the real
    edition -- 200 lines of live German intelligence replaced by a two-row
    fixture, with nothing failing to say so. The EU tests already redirect
    ROOT for exactly this reason; this one did not until it had done it once.
    """
    old_root = dm.ROOT
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "editions"))
        dm.ROOT = tmp
        try:
            path = dm.render_edition(conn, TODAY)
            self_check = os.path.realpath(path)
            assert self_check.startswith(os.path.realpath(tmp)), \
                "render_edition wrote outside the temp tree: " + path
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        finally:
            dm.ROOT = old_root


class HonestyNoteTests(unittest.TestCase):
    """The standing disclosure. It is the reason this edition can be
    circulated at all, so it is not conditional on there being content."""

    def test_the_edition_says_the_taxonomy_is_unverified(self):
        conn = _conn()
        _vorgang(conn, "1", "Schwangerschaftskonfliktgesetz")
        text = _render(conn)
        self.assertIn("no German speaker has verified", text.replace("**", ""))
        self.assertIn("taxonomy-de.yaml", text)

    def test_the_note_survives_an_empty_week(self):
        """An empty edition is the MOST likely one to be skimmed and the
        least likely to carry its caveat, so this is the case that matters."""
        text = _render(_conn())
        self.assertIn("no German speaker has verified", text.replace("**", ""))

    def test_the_dm_carries_the_caveat_too(self):
        """A DM is the surface most likely to be forwarded without the
        edition attached; the caveat has to travel with it."""
        conn = _conn()
        _vorgang(conn, "1", "Selbstbestimmungsgesetz")
        msg = dm.dm_summary(conn, TODAY)
        self.assertIn("no German speaker has verified", msg)

    def test_the_named_version_matches_the_taxonomy_on_disk(self):
        """The note names a version. A note naming a version the file no
        longer carries is worse than no version at all."""
        import yaml
        with open(dm.TAXONOMY, encoding="utf-8") as fh:
            raw = fh.read()
        header = json.dumps(yaml.safe_load(raw) or "")[:2000]
        self.assertIn(dm.TAXONOMY_VERSION, raw[:2000] + header,
                      "the honesty note names {0} but the taxonomy file does "
                      "not say so".format(dm.TAXONOMY_VERSION))


class NoVerdictTests(unittest.TestCase):
    """A division's direction is a signed human judgement. The renderer must
    report what the House did and never what it meant."""

    BANNED = ("defeat", "victory", "win for", "defended", "attack on",
              "good news", "bad news", "we won", "we lost")

    def test_a_division_renders_tallies_and_no_direction(self):
        conn = _conn()
        _division(conn, "v1", "Gesetz zur Suizidhilfe")
        text = _render(conn).lower()
        self.assertIn("380 yes", text)
        self.assertIn("no verdicts", text)
        for word in self.BANNED:
            self.assertNotIn(word, text,
                             "the edition editorialised a division: " + word)

    def test_accepted_comes_from_the_house_not_the_tallies(self):
        """A vote the House recorded as NOT accepted despite more ayes than
        noes (quorum, two-thirds thresholds) must render the House's own
        outcome -- the ePrivacy lesson, in German."""
        conn = _conn()
        _division(conn, "v1", "Grundgesetzänderung", yes=400, no=100,
                  accepted=0)
        text = _render(conn)
        self.assertIn("not accepted", text)


class FraktionSplitTests(unittest.TestCase):
    def test_the_split_is_counted_per_party(self):
        conn = _conn()
        _division(conn, "v1", "Gesetz X")
        for i, (party, pos) in enumerate(
                [("SPD", "yes"), ("SPD", "yes"), ("SPD", "no"),
                 ("CDU/CSU", "no"), ("CDU/CSU", "abstain")]):
            _member(conn, "p{0}".format(i), "Name {0}".format(i), party)
            _vote(conn, "v1", "p{0}".format(i), pos)
        split = dm.fraktion_split(conn, "v1")
        self.assertEqual(split["SPD"], {"yes": 2, "no": 1})
        self.assertEqual(split["CDU/CSU"], {"no": 1, "abstain": 1})
        self.assertIn("SPD 2/1/0", _render(conn))

    def test_a_vote_by_someone_we_have_no_member_row_for_is_counted(self):
        """Never silently dropped: a missing member row is a gap in OUR data,
        and a Fraktion split that quietly omits people overstates discipline."""
        conn = _conn()
        _division(conn, "v1", "Gesetz X")
        _vote(conn, "v1", "ghost", "no")
        self.assertEqual(dm.fraktion_split(conn, "v1"),
                         {"(unknown)": {"no": 1}})


class UnscoredRowsAreShownTests(unittest.TestCase):
    """degate's contract: a row the judge has not reached is not a row the
    judge rejected. Hiding it makes a stalled triage look like a quiet week --
    the exact failure shape this repo keeps paying for."""

    def test_an_unscored_matched_row_renders(self):
        conn = _conn()
        _vorgang(conn, "1", "Verbot der Konversionsbehandlung", score=None,
                 why=None)
        text = _render(conn)
        self.assertIn("Verbot der Konversionsbehandlung", text)
        self.assertIn("unscored", text)

    def test_a_row_the_judge_scored_below_the_bar_is_suppressed_but_counted(self):
        conn = _conn()
        _vorgang(conn, "1", "Ein Randthema", score=0, why="Not ours.")
        text = _render(conn)
        self.assertNotIn("Ein Randthema", text)
        self.assertIn("Judged below the bar", text)
        self.assertIn("| 1 | 1 | 1 | 0 |", text.replace("  ", " "))

    def test_the_backlog_is_named_in_the_edition_and_the_dm(self):
        conn = _conn()
        _vorgang(conn, "1", "Etwas Neues", score=None, why=None)
        self.assertIn("await the judge", _render(conn))
        self.assertIn("await the judge", dm.dm_summary(conn, TODAY))


class DmOrderingTests(unittest.TestCase):
    def test_the_newest_leads_within_a_score(self):
        """A weekly DM led with six Vorgänge from 2024 because the sort ran
        ascending on date. Highest score first, then most recent."""
        conn = _conn()
        for vid, titel, datum in (("1", "Alt", "2024-01-18"),
                                  ("2", "Neu", "2026-09-14")):
            conn.execute(
                "INSERT INTO de_vorgaenge (vorgang_id, titel, datum, areas, "
                "tier, triage_score, why_it_matters, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (vid, titel, datum, "[1]", 1, 3, "Why.", TODAY, TODAY))
        conn.commit()
        msg = dm.dm_summary(conn, TODAY)
        self.assertLess(msg.index("Neu"), msg.index("Alt"))

    def test_a_long_title_is_clipped_with_an_ellipsis(self):
        """Cut at exactly n characters mid-word, a German title reads as
        corrupted data rather than as an abbreviation."""
        conn = _conn()
        _vorgang(conn, "1", "Vorkehrungen zum besonderen Schutz von Kindern "
                 "und Jugendlichen bei Aenderung des Geschlechtseintrags")
        msg = dm.dm_summary(conn, TODAY)
        self.assertIn("\u2026", msg)


class DisclosureTests(unittest.TestCase):
    def test_inherited_areas_are_declared_as_second_hand(self):
        """A terse vote label that matched nothing takes its ground from the
        paper it voted on. A reader is entitled to know the classification is
        not the vote's own."""
        conn = _conn()
        _division(conn, "v1", "Sportfoerdergesetz", inherited="drucksache:21/1")
        text = _render(conn)
        self.assertIn("inherited from the paper", text)
        self.assertIn("drucksache:21/1", text)

    def test_the_laender_section_says_the_source_is_thin(self):
        text = _render(_conn())
        self.assertIn("no document layer", text)
        self.assertIn("thin *source*, not a strict filter", text)

    def test_a_land_vote_is_not_counted_as_a_bundestag_one(self):
        conn = _conn()
        _division(conn, "v1", "Bundestagsgesetz", parliament="5")
        _division(conn, "v2", "Landesgesetz", parliament="12")
        self.assertEqual([r["vote_id"] for r in dm.divisions(conn, True)],
                         ["v1"])
        self.assertEqual([r["vote_id"] for r in dm.divisions(conn, False)],
                         ["v2"])

    def test_gaps_are_printed_rather_than_swallowed(self):
        conn = _conn()
        conn.execute("INSERT INTO gaps (feed, edition, detail) VALUES "
                     "(?,?,?)", ("de-documents", TODAY, "DIP refused page 3"))
        conn.commit()
        self.assertIn("DIP refused page 3", _render(conn))


class MigrationIsCollatedNeverCampaignedTests(unittest.TestCase):
    """Christopher's standing instruction, and a repo-wide rule: area 11 is
    collated, never campaigned, shown nowhere. src/partner.py holds the
    original; four other modules carry the same tuple.

    NOT hypothetical in Germany. The first German triage pass (22 September
    2026) scored 199 items and the six highest were deportation Vorgänge in a
    row: without this rule the German team's first edition would have opened
    on precisely the campaign the organisation does not run.
    """

    def test_a_migration_only_item_is_not_rendered(self):
        conn = _conn()
        _vorgang(conn, "1", "Abschiebungen nach Syrien", areas="[11]")
        text = _render(conn)
        self.assertNotIn("Abschiebungen nach Syrien", text)

    def test_it_is_counted_and_disclosed_rather_than_disappeared(self):
        """Collated, never campaigned -- not deleted. A filter that drops rows
        and reports only what survived is how real news dies quietly."""
        conn = _conn()
        _vorgang(conn, "1", "Abschiebungen nach Syrien", areas="[11]")
        text = _render(conn)
        self.assertIn("matched on migration alone", text)
        self.assertIn("collated, never campaigned", text)
        self.assertIn("They are in the store", text)

    def test_an_item_with_migration_AND_another_area_still_shows(self):
        """The rule suppresses the campaign, not the item."""
        conn = _conn()
        _vorgang(conn, "1", "Kinderehen und Aufenthaltsrecht", areas="[9, 11]")
        text = _render(conn)
        self.assertIn("Kinderehen und Aufenthaltsrecht", text)
        self.assertNotIn("Migration", text)     # shown under area 9 only

    def test_an_empty_section_says_WHY_it_is_empty(self):
        """"Nothing matched" and "the standing rule removed everything that
        matched" are different facts and a reader acts differently on each.
        Measured 22 September 2026: all six matched Bundestag votes in the
        store are migration, so this is the live case, not a corner one."""
        conn = _conn()
        _division(conn, "v1", "Gesetz zur Rueckfuehrung", areas="[11]")
        text = _render(conn)
        self.assertIn("all 1 matched Bundestag vote(s) are on migration "
                      "alone", text)
        self.assertNotIn("is normal and is not evidence of anything", text)

    def test_a_genuinely_quiet_week_still_says_so(self):
        text = _render(_conn())
        self.assertIn("is normal and is not evidence of anything", text)

    def test_the_dm_obeys_it_too(self):
        conn = _conn()
        _vorgang(conn, "1", "Abschiebungen nach Syrien", areas="[11]")
        msg = dm.dm_summary(conn, TODAY)
        self.assertNotIn("Abschiebungen", msg)

    def test_a_migration_only_division_is_suppressed(self):
        conn = _conn()
        _division(conn, "v1", "Gesetz zur Rueckfuehrung", areas="[11]")
        self.assertNotIn("Rueckfuehrung", _render(conn))

    def test_this_file_agrees_with_the_repo_wide_tuple(self):
        """Five modules carry HIDDEN_AREAS and they must not drift apart."""
        from src import partner
        self.assertEqual(tuple(dm.HIDDEN_AREAS), tuple(partner.HIDDEN_AREAS))


class StructuralTests(unittest.TestCase):
    def test_every_german_table_carrying_areas_is_in_the_watching_table(self):
        """The EU monitor grew five collectors whose rows sat unreported while
        the run cheerfully printed a summary. A German table that gains
        `areas` and never reaches the edition would repeat it."""
        conn = _conn()
        carrying = set()
        for row in conn.execute("SELECT name FROM sqlite_master WHERE "
                                "type='table' AND name LIKE 'de|_%' "
                                "ESCAPE '|'"):
            cols = [c[1] for c in conn.execute(
                "PRAGMA table_info({0})".format(row[0]))]
            if "areas" in cols:
                carrying.add(row[0])
        self.assertTrue(carrying, "no de_ tables carry areas; the probe is wrong")
        text = _render(conn)
        with open(os.path.join(ROOT, "tools", "de_monitor.py"),
                  encoding="utf-8") as fh:
            source = fh.read()
        for table in sorted(carrying):
            self.assertIn(table, source,
                          "{0} carries areas and tools/de_monitor.py never "
                          "mentions it: its rows would be collected, judged "
                          "and never shown".format(table))
        self.assertIn("Watching", text)

    def test_a_title_spanning_two_lines_stays_one_heading(self):
        """DIP puts the document number on a second line. Left alone it
        breaks the markdown heading in half and the number floats free."""
        conn = _conn()
        _vorgang(conn, "1", 'Mitteilung der Kommission\nK(2026)3333 endg.')
        text = _render(conn)
        self.assertIn("### Mitteilung der Kommission K(2026)3333 endg.", text)

    def test_the_drucksachen_zero_is_explained(self):
        """de_documents is filled by --mode window, which the weekly does not
        run. An unexplained 0 in the table reads as a broken collector."""
        self.assertIn("configuration choice, not a collector that failed",
                      _render(_conn()))

    def test_the_renderer_never_invents_a_why_line(self):
        conn = _conn()
        _vorgang(conn, "1", "Ein Gesetz", score=2, why=None)
        text = _render(conn)
        self.assertIn("Ein Gesetz", text)
        self.assertNotIn("None", text)


if __name__ == "__main__":
    unittest.main()
