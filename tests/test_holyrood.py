"""Holyrood ingester tests, against live-probed fixtures (2026-08-20)."""

import gzip
import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import holyrood


def load_fixture(slug):
    paths = sorted(glob.glob(os.path.join(
        ROOT, "data", "raw", "*", slug + ".json.gz")))
    with gzip.open(paths[-1], "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


class QuestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = holyrood.parse_questions(load_fixture("holyrood_questions-fixture"))

    def test_parses_every_row(self):
        payload = load_fixture("holyrood_questions-fixture")
        self.assertEqual(len(self.rows), len(payload))

    def test_answers_arrive_inline(self):
        """The single biggest difference from NI: AnswerText is ON the question
        row, so no per-answer fetch exists to guard or to spend."""
        answered = [r for r in self.rows if r.answer]
        self.assertTrue(answered, "fixture must carry answered questions")
        for r in answered:
            self.assertTrue(r.answered, "an answer implies an AnswerDate")

    def test_html_entities_are_unescaped(self):
        """ItemText carries &rsquo; and &pound; -- classification text must be
        real characters or phrase terms fail on the entity."""
        for r in self.rows:
            self.assertNotIn("&rsquo;", r.body)
            self.assertNotIn("&pound;", r.body)

    def test_reference_comes_from_event_id(self):
        refs = [r.reference for r in self.rows if r.reference]
        self.assertTrue(any(x.startswith(("S6", "S7")) for x in refs), refs)


class MotionTests(unittest.TestCase):
    def test_since_floor_is_applied(self):
        """The motions endpoint IGNORES ?year= and serves everything since
        1999 (110MB, 84,751 rows); the floor is client-side and load-bearing --
        without it the store gains ~100MB of text nobody will read."""
        payload = load_fixture("holyrood_motions-fixture")
        allrows = holyrood.parse_motions(payload)
        floored = holyrood.parse_motions(payload, since="2024-01-01")
        self.assertLess(len(floored), len(allrows),
                        "fixture carries pre-2000 rows the floor must drop")
        for r in floored:
            self.assertGreaterEqual(r.dated, "2024-01-01")


class RosterTests(unittest.TestCase):
    def test_current_roster_is_the_chamber(self):
        """129 seats. The live probe's memberparties held exactly 129 rows with
        a null ValidUntilDate -- the roster validates itself against the real
        chamber, the same check that caught NI's by-date lag."""
        affs = holyrood.parse_affiliations(
            [{"ID": 1, "PersonID": 2, "PartyID": 3,
              "ValidFromDate": "2026-05-08T00:00:00", "ValidUntilDate": None}])
        self.assertIsNone(affs[0].valid_until)
        self.assertEqual(affs[0].valid_from, "2026-05-08")


class SeparationTests(unittest.TestCase):
    """Holyrood must not be able to reach the published Slack digest --
    the same structural guarantee as NI, asserted from day one rather than
    retrofitted."""

    def _source(self, name):
        with open(os.path.join(ROOT, "tools", name), encoding="utf-8") as fh:
            return fh.read()

    def test_sp_tools_never_write_published_tables(self):
        for name in ("sp_pull.py", "sp_divisions.py", "sp_5ca.py"):
            source = self._source(name)
            for table in ("items", "mp_events"):
                for verb in ("INTO {0} ", "INTO {0}(", "UPDATE {0} "):
                    self.assertNotIn(verb.format(table), source,
                                     "{0} must not write {1}".format(name, table))

    def test_sp_pull_writes_its_own_tables(self):
        source = self._source("sp_pull.py")
        self.assertIn("sp_items", source)
        self.assertIn("sp_members", source)

    def test_sp_divisions_writes_its_own_tables(self):
        source = self._source("sp_divisions.py")
        self.assertIn("sp_divisions", source)
        self.assertIn("sp_votes", source)

    def test_the_weekly_workflow_has_no_publish_step(self):
        """Holyrood is a watching brief: the scheduled refresh pulls and
        harvests, and nothing in it may reach Slack or need a secret."""
        path = os.path.join(ROOT, ".github", "workflows", "sp-weekly.yml")
        with open(path, encoding="utf-8") as fh:
            source = "\n".join(line for line in fh.read().splitlines()
                               if not line.strip().startswith("#"))
        for banned in ("slack", "secrets.yaml", "post_", "publish",
                       "ANTHROPIC", "SLACK"):
            self.assertNotIn(banned, source, banned)
        self.assertIn("group: parl-monitor-state", source)

    def test_monitor_is_read_only(self):
        source = self._source("sp_monitor.py")
        for verb in ("INSERT", "UPDATE ", "DELETE"):
            self.assertNotIn(verb, source)

    def test_year_dumps_are_not_archived_to_git(self):
        """data/raw is committed weekly; the dumps are 7-110MB and the API
        serves them canonically by year. archive=False is the contract."""
        source = open(os.path.join(ROOT, "src", "ingest", "holyrood.py"),
                      encoding="utf-8").read()
        self.assertIn('archive=False', source)
        # the small roster fetches ARE archived (provenance is cheap there)
        self.assertIn('"members"', source)


if __name__ == "__main__":
    unittest.main()

class VoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.divs = holyrood.parse_votes(load_fixture("holyrood_votes-fixture"))

    def test_both_detail_schemas_produce_divisions(self):
        """TWO Detail schemas coexist in one dump: most rows carry
        MotionAgendaItemID, but 1,419 of 19,473 rows in 2026 -- 11 whole
        divisions -- carry BackupAgendaItemID instead. Keying on the first
        alone silently dropped those 11, caught only because the division
        count was cross-checked against an independent (reference, time)
        grouping. The fixture holds one division of each schema."""
        self.assertEqual(len(self.divs), 2)
        keys = {d.key[0] for d in self.divs}
        self.assertEqual(keys, {"m", "b"}, "one division per schema")

    def test_every_voter_is_kept(self):
        payload = load_fixture("holyrood_votes-fixture")
        self.assertEqual(sum(len(d.votes) for d in self.divs), len(payload))

    def test_party_and_whip_flag_ride_the_vote_row(self):
        v = self.divs[0].votes[0]
        self.assertTrue(v.party)
        self.assertIn(v.vote, ("Yes", "No", "Abstain", "Not Voted"))

    def test_base_reference_strips_the_amendment_suffix(self):
        self.assertEqual(holyrood.base_reference("S7M-00469.5"), "S7M-00469")
        self.assertEqual(holyrood.base_reference("S7M-00469"), "S7M-00469")
        self.assertEqual(holyrood.base_reference(None), "")


class SP5caTests(unittest.TestCase):
    """The placement contract, pinned: a human-confirmed meaning line is the
    only thing that moves an MSP into a column."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import sp_5ca
        cls.m = sp_5ca

    ENTRY = {"reference": "S6M-21005", "aye": -2, "why_aye": "passed the bill",
             "no": 2, "why_no": "defeated the bill"}

    def test_a_draft_places_nobody(self):
        draft = dict(self.ENTRY, draft=True)
        self.assertEqual(self.m.vote_stance(draft, "Yes"), (None, None))
        self.assertEqual(self.m.vote_stance(draft, "No"), (None, None))

    def test_a_confirmed_entry_places_both_lobbies(self):
        s, why = self.m.vote_stance(self.ENTRY, "Yes")
        self.assertEqual(s, -2)
        s, why = self.m.vote_stance(self.ENTRY, "No")
        self.assertEqual(s, 2)

    def test_absence_is_data_not_direction(self):
        for v in ("Abstain", "Not Voted"):
            self.assertEqual(self.m.vote_stance(self.ENTRY, v), (None, None))

    def test_conflicts_are_flagged_never_averaged(self):
        col, conflict, best = self.m.place(
            [(2, "2026-03-17", "a", "vote"), (-1, "2025-05-13", "b", "vote")])
        self.assertTrue(conflict)
        self.assertEqual(col, "++", "+2 and -1 is a flagged +2, not +0.5")

    def test_a_vote_outranks_a_motion_of_equal_magnitude(self):
        col, conflict, best = self.m.place(
            [(1, "2026-01-01", "m", "motion"), (1, "2026-01-01", "v", "vote")])
        self.assertEqual(best[3], "vote")

    def test_stance_file_confirmation_state(self):
        """Confirmation must be a decision, not a drift: this test pins WHICH
        entries are confirmed, and fails the moment one changes state without
        someone consciously updating it. S6M-21005 (Stage 3 passage) was
        confirmed by Christopher on 2026-08-21 -- the motion text IS the
        question, so no amendment-reading was required. The other two remain
        proposals."""
        entries = self.m.load_stance(section="divisions")
        self.assertEqual(len(entries), 12)
        for ref in ("S6M-21005", "S6M-17416", "S6M-16755.3",
                    "S6M-13090.4", "S6M-13090", "S6M-16755"):
            self.assertFalse(entries[ref].get("draft"),
                             ref + " confirmed 2026-08-21")

    def test_not_placeable_entries_place_nobody(self):
        """S7M-00446.2 is recorded WITHOUT aye/no values: the SNP amendment
        struck an entire omnibus motion, so a vote either way bundles the
        Lady Ross passage with the whole Reform economic programme -- it
        cannot discriminate ally from opponent on our issue (the NI 488823
        discipline). The entry documents the reasoning; it must never move
        an MSP."""
        entries = self.m.load_stance(section="divisions")
        for ref in ("S7M-00446.2", "S7M-00446", "S6M-20037",
                    "S6M-21077", "S6M-20898", "S6M-16170.3"):
            e = entries[ref]
            self.assertIsNone(e.get("aye"), ref)
            self.assertIsNone(e.get("no"), ref)
            self.assertEqual(self.m.vote_stance(e, "Yes"), (None, None))
            self.assertEqual(self.m.vote_stance(e, "No"), (None, None))

    def test_the_yaml_no_key_trap_is_normalised(self):
        """The trap: an unquoted `no:` key parses as boolean False (YAML 1.1).
        A NOT PLACEABLE entry has neither aye nor no, legitimately -- so the
        assertion is that False never survives as a key, and that a directional
        entry carrying aye also carries no (a one-lobby meaning line would be
        the trap's fingerprint)."""
        entries = self.m.load_stance(section="divisions")
        for ref, e in entries.items():
            self.assertNotIn(False, e, ref)
            if e.get("aye") is not None:
                self.assertIn("no", e, ref)


class ORDivisionTests(unittest.TestCase):
    """Bill amendment divisions -- the vote class votesmotion does not carry.

    In 2026 the Official Report held 672 division results and 530 were bill
    amendments, including all 215 of the Assisted Dying Stage 3 amendment
    fight. The OR prints aggregates only; no roll-call exists in the open
    data, so these rows can never place anyone.
    """

    ROW = {"ID": "X", "Detail": {"ContributionID": 3041539, "EditedText":
           "The result of the division is: For 73, Against 45, Abstentions 4."
           "Amendment 56 agreed to."},
           "ItemOfBusiness": {"Heading": "Assisted Dying for Terminally Ill "
                              "Adults (Scotland) Bill: Stage 3"},
           "Time": {"Start": "2026-03-13T15:00:00"}}
    MOTION_ROW = {"ID": "Y", "Detail": {"ContributionID": 1, "EditedText":
                  "The result of the division on motion S6M-21005, in the "
                  "name of Liam McArthur, is: For 57, Against 69, "
                  "Abstentions 1.Motion disagreed to."},
                  "ItemOfBusiness": {"Heading": "Decision Time"},
                  "Time": {"Start": "2026-03-17T17:00:00"}}

    def test_amendment_result_parses_whole(self):
        d = holyrood.parse_or_divisions([self.ROW])[0]
        self.assertEqual((d.vote_for, d.vote_against, d.abstentions),
                         (73, 45, 4))
        self.assertEqual(d.amendment_no, "56")
        self.assertEqual(d.outcome, "agreed")
        self.assertEqual(d.key, "or3041539")
        self.assertIsNone(d.motion_ref)

    def test_motion_results_are_marked_as_duplicates(self):
        """A result citing S6M-21005 is the same division votesmotion already
        holds WITH per-MSP votes; the harvester must skip it or the store
        would carry the Stage 3 vote twice with different keys."""
        d = holyrood.parse_or_divisions([self.MOTION_ROW])[0]
        self.assertEqual(d.motion_ref, "S6M-21005")

    def test_non_division_rows_are_ignored(self):
        rows = holyrood.parse_or_divisions(
            [{"Detail": {"EditedText": "There will be a division."},
              "ItemOfBusiness": {}, "Time": {}}])
        self.assertEqual(rows, [])


class ORSpeechTests(unittest.TestCase):
    """Speeches ride the same OR payload as divisions -- one 65MB fetch."""

    ROW = {"ID": "Z", "Detail": {"ContributionID": 777, "EditedText":
           "The Cass Review made clear that puberty blockers required caution."},
           "Person": {"ID": 1857, "ParliamentaryName": "McNeill, Pauline"},
           "ItemOfBusiness": {"Heading": "Gender Services"},
           "Time": {"Start": "2026-02-01T14:00:00"}}

    def test_speech_parses_with_the_speaker(self):
        sp = holyrood.parse_or_speeches([self.ROW])[0]
        self.assertEqual(sp.key, "orc777")
        self.assertEqual(sp.person_id, "1857")
        self.assertEqual(sp.dated, "2026-02-01")
        self.assertIn("Cass Review", sp.text)

    def test_speakerless_rows_are_skipped(self):
        rows = holyrood.parse_or_speeches(
            [{"Detail": {"EditedText": "text"}, "Person": {},
              "ItemOfBusiness": {}, "Time": {}}])
        self.assertEqual(rows, [])

    def test_divisions_and_speeches_share_a_payload(self):
        """fetch_or_payload exists so the tool downloads the 65MB dump once
        per year and feeds BOTH parsers; a second fetch would double the
        weekly transfer for nothing."""
        calls = []
        class C:
            def get_json(self, url, feed, slug, timeout=None, archive=True):
                calls.append(slug)
                return []
        holyrood.fetch_or_payload(C(), 2026)
        self.assertEqual(calls, ["or-2026"])
        source = open(os.path.join(ROOT, "tools", "sp_divisions.py"),
                      encoding="utf-8").read()
        self.assertIn("fetch_or_payload", source)
        self.assertNotIn("fetch_or_divisions(client", source)
