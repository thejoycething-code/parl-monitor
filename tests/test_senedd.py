"""Senedd ingester tests against live-probed fixtures (2026-08-21)."""

import datetime
import gzip
import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import senedd


def load(slug):
    paths = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*",
                                          slug + ".json.gz")))
    with gzip.open(paths[-1], "rt", encoding="utf-8") as fh:
        return fh.read()


class ParseTests(unittest.TestCase):
    def test_answered_question_parses_whole(self):
        q = senedd.parse_question(load("senedd_wq-answered-fixture"), 95000)
        self.assertEqual(q.reference, "WQ95000")
        self.assertEqual(q.member_name, "Andrew R.T. Davies")
        self.assertEqual(q.constituency, "South Wales Central")
        self.assertEqual(q.dated, "2024-11-14")
        self.assertEqual(q.answered, "2024-11-21")
        self.assertIn("maternity", q.body)
        self.assertIn("service standards", q.answer)

    def test_pending_question_has_minister_but_no_answer(self):
        q = senedd.parse_question(load("senedd_wq-pending-fixture"), 100032)
        self.assertEqual(q.dated, "2026-08-19")
        self.assertIsNone(q.answered)
        self.assertIsNone(q.answer)
        self.assertIn("Health", q.answered_by)

    def test_the_miss_signature_is_no_tabled_line(self):
        """A nonexistent id serves the site shell WITHOUT 'Tabled on' -- the
        walker's stop condition. It must be None, never a garbage row."""
        self.assertIsNone(
            senedd.parse_question(load("senedd_wq-miss-fixture"), 100600))


class SeparationTests(unittest.TestCase):
    """Senedd must not be able to reach the published Slack digest."""

    def _source(self, name):
        with open(os.path.join(ROOT, "tools", name), encoding="utf-8") as fh:
            return fh.read()

    def test_sd_pull_writes_its_own_tables_only(self):
        source = self._source("sd_pull.py")
        self.assertIn("sd_items", source)
        for table in ("items", "mp_events"):
            for verb in ("INTO {0} ", "INTO {0}(", "UPDATE {0} "):
                self.assertNotIn(verb.format(table), source)

    def test_monitor_is_read_only(self):
        source = self._source("sd_monitor.py")
        for verb in ("INSERT", "UPDATE ", "DELETE"):
            self.assertNotIn(verb, source)

    def test_the_honest_user_agent_rule_is_stated(self):
        """business.senedd.wales rejects the CitizenGO UA; working around the
        WAF by impersonating a browser is a recorded decision point, not a
        quiet default. The ingester must keep saying so."""
        source = open(os.path.join(ROOT, "src", "ingest", "senedd.py"),
                      encoding="utf-8").read()
        self.assertIn("honest", source)
        self.assertIn("decision", source)


if __name__ == "__main__":
    unittest.main()


class WeeklyWorkflowTests(unittest.TestCase):
    def test_the_workflow_has_no_publish_step_and_can_push(self):
        """Copied from ni-weekly rather than written from memory -- the
        sp-weekly lesson (its day-one double miss was a missing permissions
        block and sunset action majors)."""
        path = os.path.join(ROOT, ".github", "workflows", "sd-weekly.yml")
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        source = "\n".join(l for l in raw.splitlines()
                           if not l.strip().startswith("#"))
        for banned in ("slack", "secrets.yaml", "post_", "publish",
                       "ANTHROPIC", "SLACK"):
            self.assertNotIn(banned, source, banned)
        self.assertIn("group: parl-monitor-state", source)
        self.assertIn("contents: write", source)
        self.assertIn("checkout@v7", source)


class VoteTests(unittest.TestCase):
    def test_both_wrapper_schemas_parse(self):
        """The row wrapper EMBEDS the parliament name in older exports:
        XML_Plenary_Vote (Seventh) but XML_Plenary-SixthSenedd_Vote (Sixth).
        The exact-tag regex silently parsed the Sixth's two years of
        divisions to zero -- the same silent-suppression class as Holyrood's
        BackupAgendaItemID."""
        divs = senedd.parse_votes_xml(load("senedd_votes-fixture"))
        self.assertEqual(len(divs), 2, "one division per schema")

    def test_the_division_key_is_contribution_id(self):
        """<ID> is unique PER ROW (member-level): grouping on it produced 480
        one-voter divisions from a sitting that held 5 of 96 voters each."""
        divs = senedd.parse_votes_xml(load("senedd_votes-fixture"))
        for d in divs:
            self.assertGreater(len(d.votes), 1)
            self.assertTrue(d.title)
            self.assertIn(d.votes[0].result, ("For", "Against", "Abstain"))

    def test_vote_index_parses(self):
        sittings = senedd.parse_vote_index(load("senedd_voteindex-fixture"))
        self.assertTrue(sittings)
        s = sittings[0]
        self.assertEqual(s.meeting_id, 16086)
        self.assertEqual(s.dated, "2026-07-15")
        self.assertTrue(s.has_votes)

    def test_sd_divisions_writes_its_own_tables(self):
        source = open(os.path.join(ROOT, "tools", "sd_divisions.py"),
                      encoding="utf-8").read()
        self.assertIn("sd_divisions", source)
        self.assertIn("sd_votes", source)
        for table in ("items", "mp_events"):
            for verb in ("INTO {0} ", "INTO {0}(", "UPDATE {0} "):
                self.assertNotIn(verb.format(table), source)


class TranscriptTests(unittest.TestCase):
    def test_speeches_parse_with_attribution(self):
        # reuse the live probe capture committed as the votes fixture's
        # sibling: parse the real transcript sample stored below.
        text = load("senedd_transcript-fixture")
        speeches = senedd.parse_transcript(text)
        self.assertTrue(speeches)
        s = speeches[0]
        self.assertTrue(s.member_id)
        self.assertTrue(s.member_name)
        self.assertTrue(s.text)
        self.assertEqual(s.dated, "2026-07-15")

    def test_chair_furniture_is_skipped(self):
        """Blocks without a Member_Id are procedural; they must not become
        ledger rows."""
        text = ("<XML_Plenary_English><Meeting_ID>1</Meeting_ID>"
                "<MeetingDate>2026-07-15T13:30:01</MeetingDate>"
                "<Contribution_ID>9</Contribution_ID><Member_Id></Member_Id>"
                "<Contribution_English>Order.</Contribution_English>"
                "</XML_Plenary_English>")
        self.assertEqual(senedd.parse_transcript(text), [])

    def test_older_parliament_wrapper_tolerated(self):
        """The votes trap, pre-applied: older transcript exports embed the
        parliament name in the wrapper."""
        text = ("<XML_Plenary-SixthSenedd_English><Meeting_ID>1</Meeting_ID>"
                "<MeetingDate>2025-01-01T13:30:01</MeetingDate>"
                "<Contribution_ID>7</Contribution_ID><Member_Id>5</Member_Id>"
                "<Member_name_English>A Member</Member_name_English>"
                "<Contribution_English>On the Cass review.</Contribution_English>"
                "</XML_Plenary-SixthSenedd_English>")
        sp = senedd.parse_transcript(text)
        self.assertEqual(len(sp), 1)
        self.assertEqual(sp[0].key, "sdc7")


class BillTests(unittest.TestCase):
    def test_royal_assent_prose_wins_with_its_date(self):
        stage, date = senedd.parse_bill_status(
            "Stage 4 proceedings took place in April. "
            "Royal Assent was given on 27 April 2026.")
        self.assertEqual((stage, date), ("Royal Assent", "2026-04-27"))

    def test_highest_stage_mentioned_wins_without_assent(self):
        stage, date = senedd.parse_bill_status(
            "Stage 1 concluded. Stage 2 consideration began. Stage 3 next.")
        self.assertEqual(stage, "Stage 3")
        self.assertIsNone(date, "bare stage mentions carry no parseable date")

    def test_dead_markers_are_terminal(self):
        stage, _ = senedd.parse_bill_status("The Bill was withdrawn.")
        self.assertEqual(stage, "Withdrawn or rejected")

    def test_bill_links_parse(self):
        page = ('<a href="https://business.senedd.wales/mgIssueHistoryHome'
                '.aspx?IId=46468">Prohibition of Greyhound Racing '
                '(Wales) Act 2026</a>')
        self.assertEqual(senedd.parse_bill_links(page),
                         [(46468, "Prohibition of Greyhound Racing "
                                  "(Wales) Act 2026")])

    def test_sd_bills_filters_whatsnew_to_legislation(self):
        """mgWhatsNew surfaces every ModernGov issue type; the first run put
        petitions (P-07-...) and cross-party-group papers into the bill
        register. Discovery-sourced items must look like legislation."""
        source = open(os.path.join(ROOT, "tools", "sd_bills.py"),
                      encoding="utf-8").read()
        self.assertIn("Bill|Act", source)
        for table in ("items", "mp_events"):
            self.assertNotIn("INTO {0} ".format(table), source)


class SD5caTests(unittest.TestCase):
    """The placement contract, third legislature: a human-confirmed meaning
    line is the only thing that moves a Member into a column."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import sd_5ca
        cls.m = sd_5ca

    ENTRY = {"key": "623756", "for": -1, "why_for": "backed the AD motion",
             "against": 1, "why_against": "voted it down"}

    def test_a_draft_places_nobody(self):
        draft = dict(self.ENTRY, draft=True)
        self.assertEqual(self.m.vote_stance(draft, "For"), (None, None))
        self.assertEqual(self.m.vote_stance(draft, "Against"), (None, None))

    def test_a_confirmed_entry_places_both_lobbies(self):
        self.assertEqual(self.m.vote_stance(self.ENTRY, "For")[0], -1)
        self.assertEqual(self.m.vote_stance(self.ENTRY, "Against")[0], 1)

    def test_absence_is_data_not_direction(self):
        for v in ("Abstain", "DidNotVote"):
            self.assertEqual(self.m.vote_stance(self.ENTRY, v), (None, None))

    def test_conflicts_are_flagged_never_averaged(self):
        col, conflict, best = self.m.place(
            [(1, "2026-03-17", "a"), (-1, "2025-05-13", "b")])
        self.assertTrue(conflict)
        self.assertEqual(col, "+", "+1 and -1 is a flagged +1 (recency), "
                                   "never a zero")

    def test_stance_file_confirmation_state(self):
        """Pins WHICH entries place. 623756 (the Oct 2024 member debate on
        assisted dying) is the ONLY placeable Senedd division: direction was
        verified from the transcript (Julie Morgan moved the pro-AD motion,
        rejected 19-26 on a free vote). The four TIA Bill LCM divisions are
        NOT PLACEABLE -- the movers disclaimed the moral question in terms
        and the splits are constitutional coalitions (the S6M-20037
        discipline, with Welsh cross-tab evidence). A NOT PLACEABLE entry
        must never move a Member."""
        entries = self.m.load_stance()
        self.assertEqual(len(entries), 5)
        e = entries["623756"]
        self.assertFalse(e.get("draft"))
        self.assertEqual((e["for"], e["against"]), (-1, 1))
        for key in ("751826", "751832", "751837", "751866"):
            entry = entries[key]
            self.assertIsNone(entry.get("for"), key)
            self.assertIsNone(entry.get("against"), key)
            for result in ("For", "Against"):
                self.assertEqual(self.m.vote_stance(entry, result),
                                 (None, None), key)

    def test_name_join_normalises_and_falls_back(self):
        """The Record and parlparse disagree on names three ways: diacritics
        (Sian/Sian-with-a-to-bach), inserted middle names ('Benjamin Hodge
        Mckenna' vs 'Benjamin McKenna'), and casing. The join must absorb
        all three -- and must REFUSE the fallback when first+last is
        ambiguous."""
        members = {
            self.m.norm_name("Siân Gwenllian"): {"name": "Siân Gwenllian"},
            self.m.norm_name("Benjamin McKenna"): {"name": "Benjamin McKenna"},
            self.m.norm_name("John Smith"): {"name": "John Smith"},
            self.m.norm_name("John Paul Smith"): {"name": "John Paul Smith"},
        }
        roster = self.m.Roster(members)
        self.assertEqual(roster.lookup("Sian Gwenllian"),
                         self.m.norm_name("Siân Gwenllian"))
        self.assertEqual(roster.lookup("Benjamin Hodge Mckenna"),
                         self.m.norm_name("Benjamin McKenna"))
        self.assertIsNone(roster.lookup("John Andrew Smith"),
                          "two Smiths share first+last: a miss, not a guess")
        self.assertIsNone(roster.lookup("Y Llywydd / The Llywydd"))

    def test_the_sheet_is_never_posted(self):
        src = open(os.path.join(ROOT, "tools", "sd_5ca.py")).read()
        for marker in ("slack", "webhook", "requests.post", "asana"):
            self.assertNotIn(marker, src.lower())
        self.assertIn("Never posted anywhere", src)


class CommitteeTests(unittest.TestCase):
    """Committees, found 2026-08-24. The XMLExport index accepts ModernGov
    committee ids -- Plenary IS committee 908, which is why the votes
    exporter's `committee` param worked all along."""

    LIST = '''
    <a href="mgCommitteeDetails.aspx?ID=908" title="x">Plenary</a>
    <a href="mgCommitteeDetails.aspx?ID=985" title="x">Health and Social Care Committee</a>
    <a href="mgCommitteeDetails.aspx?ID=991" title="x">Llywydd&#39;s Committee</a>
    <a href="mgCommitteeDetails.aspx?ID=900" title="x">Cost of living and poverty - WYP3</a>
    <a href="mgCommitteeDetails.aspx?ID=896" title="x">Welsh Youth Parliament 3 - Plenary</a>
    '''

    DETAIL = ('<a href="https://business.senedd.wales/ieListDocuments.aspx?'
              'CId=985&MId=16251&Ver=4">The Committee will next meet on '
              'Thursday 17 September</a>')

    def test_plenary_and_youth_parliament_are_excluded(self):
        got = senedd.parse_committees(self.LIST)
        self.assertEqual(
            [n for _i, n in got],
            ["Health and Social Care Committee", "Llywydd's Committee"],
            "Plenary is harvested by sd_divisions; Youth Parliament members "
            "are not MSs and never join the roster")

    def test_next_meeting_infers_the_year_forward(self):
        mid, when = senedd.parse_next_meeting(
            self.DETAIL, today=datetime.date(2026, 8, 24))
        self.assertEqual(mid, "16251")
        self.assertEqual(when, "2026-09-17")

    def test_a_date_already_past_this_year_rolls_to_next(self):
        _mid, when = senedd.parse_next_meeting(
            self.DETAIL, today=datetime.date(2026, 12, 1))
        self.assertEqual(when, "2027-09-17",
                         "a bare '17 September' in December means next year, "
                         "never a date in the past")

    def test_no_announcement_is_none_not_a_guess(self):
        mid, when = senedd.parse_next_meeting(
            '<a href="ieListDocuments.aspx?CId=985&MId=16166">Agenda</a>',
            today=datetime.date(2026, 8, 24))
        self.assertEqual(mid, "16166")
        self.assertIsNone(when)

    def test_committee_transcripts_parse_under_their_own_wrapper(self):
        """The wrapper embeds the VENUE, so a Plenary-only pattern returned
        ZERO for every committee -- the bug this build found."""
        xml = ("<dataroot><XML_HealthAndSocialCareCommittee_English>"
               "<Meeting_ID>16166</Meeting_ID>"
               "<Contribution_ID>767159</Contribution_ID>"
               "<MeetingDate>2026-07-09T09:26:14</MeetingDate>"
               "<Member_Id>5555</Member_Id>"
               "<Member_name_English>Jayne Bryant</Member_name_English>"
               "<Agenda_item_english>3. New Petitions</Agenda_item_english>"
               "<Contribution_English>Restore parental consent for RVE"
               "</Contribution_English>"
               "</XML_HealthAndSocialCareCommittee_English></dataroot>")
        out = senedd.parse_transcript(xml)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].member_name, "Jayne Bryant")
        self.assertEqual(out[0].heading, "3. New Petitions")
        self.assertEqual(out[0].dated, "2026-07-09")

    def test_sd_committees_writes_its_own_tables(self):
        with open(os.path.join(ROOT, "tools", "sd_committees.py"),
                  encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("sd_committees", source)
        self.assertIn("sd_events", source)
        for table in ("items", "mp_events"):
            for verb in ("INTO {0} ", "INTO {0}(", "UPDATE {0} "):
                self.assertNotIn(verb.format(table), source)
        for marker in ("slack", "webhook"):
            self.assertNotIn(marker, source.lower())

    def test_the_weekly_harvests_committees(self):
        with open(os.path.join(ROOT, ".github", "workflows",
                               "sd-weekly.yml"), encoding="utf-8") as fh:
            self.assertIn("tools/sd_committees.py", fh.read())


class OpenEstateTests(unittest.TestCase):
    """The Senedd committee pipeline, re-sourced 2026-08-28.

    business.senedd.wales went behind an Azure WAF that answers 403 to
    every non-browser client -- the honest UA, the authorised browser UA
    and full browser headers alike, from a laptop and from GitHub's
    runners, on the host root as well as any page. It held the committee
    list, the meeting index and the transcripts.

    All three now come from hosts that answer: senedd.wales for the list
    and the forward look, record.senedd.wales -- the Record of Proceedings
    itself -- for the transcripts. Parsed here against real markup saved
    from those hosts, not markup I wrote to suit the parser.
    """

    FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

    def _fx(self, name):
        with open(os.path.join(self.FIXTURES, name), encoding="utf-8") as fh:
            return fh.read()

    def test_the_committee_list_comes_off_the_open_host(self):
        urls = senedd.parse_committee_index(self._fx("senedd_committee_index.html"))
        self.assertEqual(len(urls), 15)
        for u in urls:
            self.assertTrue(u.startswith("https://senedd.wales/committees/"), u)

    def test_a_committee_keeps_the_id_the_store_keys_on(self):
        """Changing source must not renumber anything: the id is still the
        ModernGov CommitteeId, read from the link the open page carries."""
        cid, name, mid, when = senedd.parse_committee_page(
            self._fx("senedd_committee_page.html"))
        self.assertEqual(cid, "984")
        self.assertEqual(name, "Finance Committee")
        self.assertEqual(when, "2026-09-17")
        self.assertEqual(mid, "16249")

    def test_the_forward_look_survived_the_move(self):
        """Same prose sentence, same parser, different host."""
        html = self._fx("senedd_committee_page.html")
        self.assertIn("will next meet", html)
        self.assertEqual(senedd.parse_next_meeting(html)[1], "2026-09-17")

    def test_contributions_carry_speaker_and_id(self):
        items, contribs = senedd.parse_record_meeting(
            self._fx("senedd_record_meeting.html"))
        self.assertTrue(items)
        self.assertTrue(contribs)
        for c in contribs:
            self.assertTrue(c.text)
            self.assertTrue(c.key, "no stable key: re-reads would duplicate")
        self.assertTrue(any(c.member_name and c.member_id for c in contribs))

    def test_the_class_is_not_always_bare_verbatim(self):
        """"verbatim fullWidth" is as common as "verbatim". Demanding an
        exact class match found 2 contributions in a meeting of 11."""
        html = self._fx("senedd_record_meeting.html")
        self.assertIn('class="verbatim fullWidth"', html)
        _items, contribs = senedd.parse_record_meeting(html)
        self.assertGreaterEqual(len(contribs), 3)

    def test_a_heading_takes_one_language_but_the_text_keeps_both(self):
        """A Petitions heading otherwise read "3. Deisebau newydd 3. New
        Petitions". The taxonomy still reads both languages, because a
        Welsh-language contribution is not less of a receipt."""
        items, contribs = senedd.parse_record_meeting(
            self._fx("senedd_record_meeting.html"))
        for title in items:
            self.assertNotRegex(title, r"\d+\.\s.+\s\d+\.\s")
        self.assertTrue(any(c.text for c in contribs))

    def test_the_record_index_arrives_as_json_not_html(self):
        """A regex over the raw response finds nothing: the endpoint
        answers with HTML fragments INSIDE JSON, so the markup is
        escaped."""
        payload = {"Results": [
            '<div class="searchResult"><a href="../Meeting/16172" class="detail">'
            '<span class="title">Transcript - Finance Committee</span>'
            '<span class="subTitle">Meeting on 09/07/2026</span></a></div>']}
        rows = senedd.parse_record_index(payload)
        self.assertEqual(rows, [("16172", "Finance Committee", "2026-07-09")])

    def test_the_blocked_readers_cannot_shadow_the_open_ones(self):
        """Both were called fetch_committees, the blocked one defined
        second -- so Python kept it, and the tool went on calling the WAF
        while reporting its 403 as a data gap."""
        import inspect
        self.assertIn("COMMITTEE_INDEX", inspect.getsource(senedd.fetch_committees))
        self.assertTrue(hasattr(senedd, "fetch_committees_moderngov"))

    def test_the_tool_no_longer_reaches_for_the_blocked_host(self):
        path = os.path.join(os.path.dirname(self.FIXTURES), os.pardir,
                            "tools", "sd_committees.py")
        with open(os.path.abspath(path), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("fetch_vote_index", src)
        # The module docstring names the blocked host to explain the move,
        # which is worth keeping; what must not survive is a CALL to it.
        import ast
        body = ast.parse(src)
        stripped = src.replace(ast.get_docstring(body) or "", "")
        self.assertNotIn("business.senedd.wales", stripped)
        self.assertNotIn("fetch_next_meeting(", stripped)


class BillRegisterTests(unittest.TestCase):
    """sd_bills, re-sourced 2026-08-28 with sd_committees.

    The tool fetched one ModernGov tracking page PER BILL, so when
    business.senedd.wales went behind its WAF every bill became a gap --
    11 in the last run. The register table on senedd.wales carries the same
    four things per bill (IId, title, stage column, progress sentence) on
    one open page.
    """

    FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

    def _fx(self, name):
        with open(os.path.join(self.FIXTURES, name), encoding="utf-8") as fh:
            return fh.read()

    def test_the_register_carries_id_title_stage_and_progress(self):
        rows = senedd.parse_bill_register(self._fx("senedd_bill_register.html"))
        self.assertTrue(rows)
        for iid, title, column, progress in rows:
            self.assertIsInstance(iid, int)
            self.assertTrue(title)
            self.assertTrue(column or progress)

    def test_the_progress_sentence_still_yields_the_assent_date(self):
        """Same prose the tracking page carried, so the same reader."""
        stage, date = senedd.bill_status_from_register(
            "Act", "Royal Assent was given on 27 April 2026")
        self.assertEqual((stage, date), ("Royal Assent", "2026-04-27"))

    def test_the_column_answers_when_the_prose_does_not(self):
        stage, date = senedd.bill_status_from_register("Stage 2", "")
        self.assertEqual(stage, "Stage 2")
        self.assertIsNone(date)

    def test_a_stage_in_the_prose_beats_the_column(self):
        stage, _date = senedd.bill_status_from_register(
            "", "Stage 3 proceedings took place on 4 March 2026")
        self.assertEqual(stage, "Stage 3")

    def test_the_register_was_fresher_than_the_store(self):
        """Not a hypothetical: IId 46599 stood at "Stage 4" in the store,
        last filled from the tracking pages, while the register already had
        it at Royal Assent on 27 April."""
        rows = senedd.parse_bill_register(self._fx("senedd_bill_register.html"))
        self.assertTrue(all(c for _i, _t, c, _p in rows))

    def test_the_tool_fetches_no_page_per_bill(self):
        """Checked on CODE, not on text: the docstring and a comment both
        name mgWhatsNew to explain what was lost, and should. Stripping the
        docstring by string-replace does not work -- ast.get_docstring
        normalises indentation, so the replace silently matches nothing."""
        import io
        import tokenize
        path = os.path.join(os.path.dirname(self.FIXTURES), os.pardir,
                            "tools", "sd_bills.py")
        with open(os.path.abspath(path), encoding="utf-8") as fh:
            src = fh.read()
        code = []
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            code.append(tok.string)
        code = " ".join(code)
        self.assertNotIn("fetch_bill", code)
        self.assertNotIn("WHATSNEW", code)

    def test_a_known_bill_absent_from_both_pages_keeps_its_stage(self):
        """Dropping it back to "Introduced" would rewrite history
        backwards."""
        path = os.path.join(os.path.dirname(self.FIXTURES), os.pardir,
                            "tools", "sd_bills.py")
        with open(os.path.abspath(path), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("register.setdefault(iid, (title, stage, date))", src)
