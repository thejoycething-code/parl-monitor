"""The public MP votes page (Christopher's decisions, 2026-08-24).

Four changes land together: verdicts go public, the whip is stated on every
vote and can differ BY PARTY, a division we decline to score is demoted with
its reason attached, and cards are grouped by bill in date order.
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_vote_tracker as mvt

TEMPLATE = os.path.join(ROOT, "templates", "vote-tracker.html")


def template():
    with open(TEMPLATE, encoding="utf-8") as fh:
        return fh.read()


class WhipLabelTests(unittest.TestCase):
    """Whipping is PER PARTY. A division can be free for one side and
    instructed for the other, which the old single value could not say."""

    def test_an_explicit_string_wins_over_inference(self):
        # bloc arithmetic would say 'whipped'; the declared value must win
        splits = [["Labour", 300, 0], ["Conservative", 0, 200]]
        self.assertEqual(mvt.whip_label({"whip": "free"}, "", splits), "free")

    def test_a_per_party_map_is_carried_through(self):
        got = mvt.whip_label({"whip": {"Labour": "whipped",
                                       "Conservative": "free"}}, "", [])
        self.assertEqual(got, {"Labour": "whipped", "Conservative": "free"})

    def test_editorial_text_still_decides_when_nothing_is_declared(self):
        self.assertEqual(mvt.whip_label({"context": "a free vote"}, "", []),
                         "free")

    def test_the_bloc_test_needs_BOTH_parties_near_unanimous(self):
        """The silent-prayer division returned None because Conservatives
        split 107-109. One bloc is not a party-line vote, and inferring
        'free' from a split would be equally wrong -- a split can also be a
        rebellion. It stays unknown until a human declares it."""
        split = [["Labour", 0, 169], ["Conservative", 107, 109]]
        self.assertIsNone(mvt.whip_label({}, "", split))

    def test_both_blocs_on_opposite_sides_is_whipped(self):
        split = [["Labour", 313, 0], ["Conservative", 0, 95]]
        # PER PARTY since 2026-08-26: the bloc test identifies WHICH parties
        # went through the lobbies as one, and only those are claimed. A
        # division-wide "whipped" put the label on a Reform UK member's card
        # for a division whipped by Labour and the Conservatives.
        self.assertEqual(mvt.whip_label({}, "", split),
                         {"Labour": "whipped", "Conservative": "whipped"})


class TemplateTests(unittest.TestCase):
    def test_the_whip_is_shown_on_every_vote_not_only_whipped_ones(self):
        """A badge that appears only when something is wrong teaches readers
        to ignore its absence."""
        t = template()
        self.assertIn("FREE VOTE", t)
        self.assertIn("WHIP NOT RECORDED", t)
        self.assertIn("whipChip(d, m)", t)

    def test_the_whip_chip_is_inside_the_vote_block(self):
        """Christopher, 2026-08-24: "I prefer inside the Block."

        Anchored on the END of voteBlock rather than on whatever function
        happens to follow it -- `bigCard` was renamed `cardHead` when the
        cards became the bill's passage, and this test broke on the rename
        rather than on the behaviour it exists to protect."""
        t = template()
        self.assertIn("vwhip", t)
        start = t.index("const voteBlock")
        block = t[start:t.index("`;", t.index("</div>", start))]
        self.assertIn("whipChip", block)

    def test_the_lobby_shows_under_the_verdict_not_in_a_hover(self):
        """A phone has no hover, and a reader is owed the fact behind the
        judgement."""
        t = template()
        self.assertIn('sub: "(" + (info.lobby || factLabel) + ")"', t)

    def test_an_unscored_division_is_demoted_with_its_reason(self):
        t = template()
        self.assertIn("demote", t)
        self.assertIn("Why there is no verdict", t)
        self.assertIn("FOR THE RECORD", t)

    def test_cards_group_by_bill_in_date_order(self):
        t = template()
        self.assertIn("billblock", t)
        self.assertIn("b.major.date.localeCompare(a.major.date)", t)

    def test_the_intro_no_longer_claims_every_vote_is_free(self):
        """Three of eighteen are whipped, and two of those carry a verdict --
        so the old blanket claim would have marked an MP good or bad for
        obeying a whip on a page saying no whip existed."""
        t = template()
        self.assertNotIn("Every vote we track is a <b>free vote</b>", t)


class PublicBuildTests(unittest.TestCase):
    def test_the_public_build_no_longer_strips_verdicts(self):
        with open(os.path.join(ROOT, "tools", "make_vote_tracker.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("dict(d, good=None)", src)


class TemplateIntegrityTests(unittest.TestCase):
    """The template is HTML with a script inside. An edit that lands OUTSIDE
    the document prints raw JavaScript above the page -- which is exactly
    what happened on 2026-08-25: a slice taken between two anchors ran
    backwards (the second string also occurs in renderEmpty, earlier), the
    slice came back empty, and replacing an empty string PREPENDED 3.4KB of
    render code above the doctype."""

    def test_the_template_starts_with_the_doctype(self):
        t = template()
        self.assertTrue(t.lstrip().startswith("<!DOCTYPE html>"),
                        "something has been inserted above the document")

    def test_nothing_renders_before_the_html_element(self):
        for path in ("docs/mp-votes.html", "partner_site/mp-votes.html"):
            full = os.path.join(ROOT, path)
            if not os.path.exists(full):
                continue
            with open(full, encoding="utf-8") as fh:
                head = fh.read(200).lstrip()
            self.assertTrue(head.startswith("<!DOCTYPE html>"), path)

    def test_only_one_render_path_survives(self):
        """The old issue-grouped loop and the new bill-card loop both ran for
        a while, so the page showed KEY VOTE chips the new render never
        emits."""
        t = template()
        self.assertNotIn("KEY VOTE", t)
        self.assertIn("billblock", t)

    def test_both_builds_are_byte_identical(self):
        import hashlib
        digests = []
        for path in ("docs/mp-votes.html", "partner_site/mp-votes.html"):
            full = os.path.join(ROOT, path)
            if not os.path.exists(full):
                self.skipTest("builds not present")
            digests.append(hashlib.md5(open(full, "rb").read()).hexdigest())
        self.assertEqual(digests[0], digests[1],
                         "the password-protected and public pages must match")

    def test_the_free_vote_claim_is_not_absolute_anywhere(self):
        """Three of eighteen are whipped. The claim appeared in TWO places
        and only the first was fixed at first."""
        t = template()
        self.assertNotIn("Every division tracked here was a free vote", t)
        self.assertNotIn("Every vote we track is a", t)


class OnRecordTests(unittest.TestCase):
    """The record is RECEIPTS ONLY (Christopher, 2026-08-25/26).

    Option A puts quotes inside the bill card they came from; Option B lists
    what is left, per issue area. Both publish facts -- dated words with a
    source -- and neither publishes an inference. The inference layer
    (stance scores, placements, characterisations) is campaign intelligence
    and must never reach this payload.
    """

    ISSUES = [{"id": "assisted-suicide", "name": "Assisted suicide", "area": 2,
               "bill": "Terminally Ill Adults (End of Life) Bill",
               "debate_match": ["Terminally Ill Adults"]},
              {"id": "abortion", "name": "Abortion", "area": 1,
               "bill": "Crime and Policing Bill",
               "debate_match": ["Crime and Policing Bill"]}]

    class FakeRaw:
        """Stands in for the Hansard payloads under data/raw."""

        TEXTS = {
            "AAA": ("I beg to move amendment 12. I do not believe assisted "
                    "dying can ever be made safe for the terminally ill, and "
                    "the evidence from Oregon bears that out. The conscience "
                    "clause in the Abortion Act 1967 is the precedent that "
                    "Members keep citing here."),
            "BBB": ("Will the Minister confirm that assisted dying services "
                    "cannot currently be delivered under the NHS Act?"),
        }

        def get(self, ref):
            ext = ref.split(":", 1)[1]
            return self.TEXTS.get(ext), {}

        def url(self, ref):
            ext = ref.split(":", 1)[1]
            return ("https://hansard.parliament.uk/Commons/2025-03-19/"
                    "debates/DEB1/#contribution-" + ext) if ext in self.TEXTS else None

    def _store(self):
        import sqlite3
        sys.path.insert(0, ROOT)
        from src import db
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        rows = [
            # a bill debate: belongs inside the assisted-suicide card
            ("1", "2025-03-19", "debate", "hansard:AAA",
             "Spoke: Terminally Ill Adults (End of Life) Bill (Twenty-seventh sitting) (re: assisted dying)",
             "[1, 2]", "ignored -- the full text is used instead"),
            # a second contribution to the SAME sitting: one debate, not two
            ("1", "2025-03-19", "debate", "hansard:BBB",
             "Spoke: Terminally Ill Adults (End of Life) Bill (Twenty-seventh sitting)",
             "[2]", ""),
            # a procedural container: never published
            ("1", "2025-03-26", "debate", "hansard:CCC",
             "Spoke: Engagements (re: assisted dying)", "[2]",
             "Q6. Will the Prime Minister join me in thanking the Clerks?"),
            ("1", "2024-01-01", "edm-signed", "edm:603",
             "Signed EDM: Safe access zones", "[1]", ""),
            ("2", "2025-01-01", "debate", "hansard:AAA",
             "Spoke: Terminally Ill Adults (End of Life) Bill", "[2]", ""),
        ]
        for r in rows:
            conn.execute("INSERT INTO mp_events (member_id, date, kind, ref, "
                         "line, areas, excerpt) VALUES (?,?,?,?,?,?,?)", r)
        from src import stance as _st
        _st.ensure_table(conn)
        conn.execute("INSERT INTO stance (ref, stance, why, scored_at) "
                     "VALUES ('hansard:AAA', 2, 'ally', '2025-01-01')")
        return conn

    def _run(self):
        sys.path.insert(0, ROOT)
        from src import filter as filt
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        return mvt.on_record(self._store(), {"1"}, self.ISSUES,
                             self.FakeRaw(), tax)

    # ---- the boundary ----------------------------------------------------
    def test_no_stance_reaches_the_payload(self):
        """The store holds a scored stance for this very ref; none of it,
        and no field carrying it, may appear in what the page ships.

        Checked by KEY, not by substring: a scan for the word "ally"
        matched inside "termin-ally ill" and failed a payload that was
        perfectly clean."""
        words, record = self._run()

        def keys(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield k
                    for kk in keys(v):
                        yield kk
            elif isinstance(obj, list):
                for v in obj:
                    for kk in keys(v):
                        yield kk

        shipped = set(keys(words)) | set(keys(record))
        for banned in ("stance", "why", "scored_at", "confidence", "tier",
                       "placement", "areas", "ref"):
            self.assertNotIn(banned, shipped)

    def test_only_display_fields_ship(self):
        words, record = self._run()
        for per in words["1"].values():
            for q in per["q"]:
                self.assertEqual(sorted(q.keys()), ["d", "q", "t", "u"])
        for block in record["1"].values():
            self.assertNotIn("_seen", block, "build-time state must be dropped")
            for it in block["items"]:
                self.assertTrue(set(it.keys()) <= {"d", "k", "t", "q", "u", "e"})

    # ---- Option A: attribution is structural, not inferred ---------------
    def test_a_quote_sits_with_the_bill_it_came_from(self):
        words, _ = self._run()
        self.assertIn("assisted-suicide", words["1"])
        self.assertNotIn("abortion", words["1"],
                         "the speech mentions the Abortion Act as precedent; "
                         "citing an Act is not a statement about it, and no "
                         "abortion bill debate took place")

    def test_bill_tally_counts_debates_not_contributions(self):
        """Two contributions to one sitting is one debate. Counting raw
        contributions produced 'spoke 216 times' on a public page."""
        words, _ = self._run()
        self.assertEqual(words["1"]["assisted-suicide"]["n"], 1)

    # ---- quote quality ---------------------------------------------------
    def test_quotes_are_whole_sentences(self):
        words, _ = self._run()
        for per in words["1"].values():
            for q in per["q"]:
                self.assertRegex(q["q"], r'[.!?]["\u201d\u2019)]?$',
                                 "a quote must end at a sentence boundary")
                self.assertNotIn("\u2026", q["q"],
                                 "an ellipsis means we cut mid-thought")

    def test_procedural_openers_are_stripped(self):
        words, _ = self._run()
        for per in words["1"].values():
            for q in per["q"]:
                self.assertFalse(q["q"].startswith("I beg to move"))

    def test_a_stance_sentence_outranks_a_request_to_the_minister(self):
        words, _ = self._run()
        lead = words["1"]["assisted-suicide"]["q"][0]["q"]
        self.assertIn("I do not believe", lead)

    def test_every_quote_carries_its_source(self):
        words, _ = self._run()
        for per in words["1"].values():
            for q in per["q"]:
                self.assertTrue(q["u"].startswith("https://hansard.parliament.uk/"))
                self.assertIn("#contribution-", q["u"],
                              "a day-level link makes a reader hunt for the "
                              "words, which defeats a shareable quote")

    # ---- Option B --------------------------------------------------------
    def test_procedural_containers_never_publish(self):
        words, record = self._run()
        import json
        self.assertNotIn("Engagements", json.dumps([words, record]))

    def test_items_shown_beside_a_vote_are_not_repeated_below(self):
        _, record = self._run()
        for block in record["1"].values():
            for it in block["items"]:
                self.assertNotIn("Terminally Ill Adults", it["t"])

    def test_signing_an_edm_is_itself_the_fact(self):
        """An EDM needs no quote: the signature is the record."""
        _, record = self._run()
        edms = [it for it in record["1"]["1"]["items"] if it["k"] == "edm-signed"]
        self.assertTrue(edms)
        self.assertEqual(edms[0]["e"], "603")

    def test_non_sitting_members_are_excluded(self):
        words, record = self._run()
        self.assertNotIn("2", record)
        self.assertNotIn("2", words)

    # ---- the page says what it is ---------------------------------------
    def test_the_section_declares_itself_factual(self):
        t = template()
        flat = " ".join(t.split())   # the template wraps its prose
        self.assertIn("Also on the record", flat)
        self.assertIn("a speech is not a vote", flat)
        self.assertIn("every quote names the debate it came from", flat)


class QuoteCuttingTests(unittest.TestCase):
    """src/quotes.py -- whole sentences, cleanly cut.

    The ledger's stored excerpt is a hard 260-character slice: of 20,453
    debate excerpts the median is 255 and 11,179 end in an ellipsis, so the
    first public build quoted members mid-word ("not as healthcare, but as a
    com"). A truncated quote under a member's name is a quotation published
    on our authority.
    """

    def setUp(self):
        sys.path.insert(0, ROOT)
        from src import quotes
        self.q = quotes

    def test_abbreviations_do_not_end_sentences(self):
        got = self.q.sentences("I thank the hon. Member for Spen Valley. "
                               "The Bill is flawed.")
        self.assertEqual(got, ["I thank the hon. Member for Spen Valley.",
                               "The Bill is flawed."])

    def test_a_closing_quotation_mark_does_not_break_the_guard(self):
        """The rejoining splitter lost its abbreviation guard whenever the
        boundary carried a closing quote, which is how 'the hon. Member for
        Spen Valley' became the start of a sentence."""
        got = self.q.sentences('He told the hon. Gentleman: "No." I disagree.')
        self.assertEqual(len(got), 2)

    def test_hansard_column_markers_are_stripped(self):
        got = self.q.clean('As I said:<span id="730" class="column-number">'
                           '</span> that is wrong.')
        self.assertEqual(got, "As I said: that is wrong.")

    def test_an_overlong_sentence_is_not_a_candidate(self):
        """One Hansard 'sentence' ran to 5,593 characters -- a block
        quotation with no terminator. It cannot be trimmed without cutting
        mid-sentence, so it is refused rather than truncated."""
        import re as _re
        long_one = "I believe " + ("assisted dying is wrong and " * 60) + "today."
        self.assertGreater(len(long_one), self.q.CAP)
        got = self.q.shareable(long_one, [_re.compile("assisted dying", _re.I)])
        self.assertIsNone(got)

    def test_a_quote_always_contains_its_own_subject(self):
        """The window can grow away from the term that justified it, leaving
        a passage displayed under a heading nothing in it mentions."""
        import re as _re
        text = ("Assisted dying is the question before us. " +
                "The weather in Wiltshire was fine that morning. " * 12)
        got = self.q.shareable(text, [_re.compile("assisted dying", _re.I)])
        if got is not None:
            self.assertIn("assisted dying", got.lower())

    def test_nothing_on_topic_means_no_quote(self):
        import re as _re
        got = self.q.shareable("The weather was fine and the train was late.",
                               [_re.compile("assisted dying", _re.I)])
        self.assertIsNone(got)

    def test_an_interrupted_sentence_is_not_published(self):
        """Hansard writes an em-dash where a member was cut off or gave way.
        It is a true feature of the record and a bad end to a pulled quote:
        it reads as if WE cut them off. Three shipped in the first build."""
        import re as _re
        text = ("I believe assisted dying is wrong and the safeguards are "
                "inadequate for the terminally ill in this country. A number "
                "of professional bodies and\u2014")
        got = self.q.shareable(text, [_re.compile("assisted dying", _re.I)])
        if got is not None:
            self.assertFalse(got.rstrip().endswith("\u2014"))

    def test_nested_closing_quotes_still_end_a_sentence(self):
        """Hansard nests quotations, so ...consent.'\u201d is complete. The
        first end-check allowed only ONE closing character and called it a
        fragment."""
        self.assertTrue(self.q.SENTENCE_END.search(
            "the child\u2019s own consent.\u2019\u201d"))

    def test_stored_text_is_cut_back_to_whole_sentences(self):
        """Written questions have no full-text source on disk, so their text
        is the ledger's own 260-character slice -- which ends in an ellipsis
        about half the time."""
        got = self.q.trim_to_sentence(
            "To ask the Secretary of State whether she has made an assessment "
            "of the impact of the policy on families. She has not published "
            "the dat...", floor=80)
        self.assertEqual(got, "To ask the Secretary of State whether she has "
                              "made an assessment of the impact of the policy "
                              "on families.")

    def test_nothing_whole_means_nothing_published(self):
        self.assertIsNone(self.q.trim_to_sentence(
            "To ask the Secretary of State for the Home Department, what "
            "estimate she has made of the reven...", floor=80))

    def test_quotability_never_looks_at_direction(self):
        """Ranking is a readability judgement. If it scored which SIDE the
        words are on, a receipt would become an inference."""
        for_it = "I believe assisted dying is a compassionate reform."
        against = "I believe assisted dying is a grave mistake."
        self.assertEqual(self.q.quotability(for_it),
                         self.q.quotability(against))


if __name__ == "__main__":
    unittest.main()


class NoVoteBadgeTests(unittest.TestCase):
    """"NO VOTE RECORDED" must key off whether the member actually walked
    through a lobby, not off whether a bill card exists.

    Every member's page renders all six cards, so the first version keyed
    off the cards and the badge was unreachable: it appeared on none of the
    650 pages. It now shows for 127 members -- 95 of them on free speech,
    which is exactly where the record-without-a-vote gap lives.
    """

    def test_the_badge_is_driven_by_votes_not_by_cards(self):
        t = template()
        self.assertIn("votedAreas", t)
        self.assertNotIn("shownAreas", t,
                         "keying off rendered cards made this unreachable")
        flat = " ".join(t.split())
        self.assertIn('const v = (m.votes || {})[d.id];', flat)

    def test_both_builds_agree(self):
        import hashlib
        digests = set()
        for path in ("partner_site/mp-votes.html", "docs/mp-votes.html"):
            full = os.path.join(ROOT, path)
            if not os.path.exists(full):
                self.skipTest("page not built")
            with open(full, "rb") as fh:
                digests.add(hashlib.md5(fh.read()).hexdigest())
        self.assertEqual(len(digests), 1,
                         "the password page and the public page must match")


class ServiceAndWhipTests(unittest.TestCase):
    """Who was sitting, for which party, and who was actually whipped.

    Christopher, 2026-08-26, on Farage's page: "Crime and Policing Bill -
    New Clause 7 says Whipped for Nigel Farage. Let's amend the rules so we
    only say whipped if the MP was an MP at the time and if it is clear
    that the party had whipped the vote. Not just any party but the Party
    the MP was an MP for at the time."
    """

    def test_a_bare_whipped_names_the_parties_the_arithmetic_identifies(self):
        split = [("Labour", 400, 1), ("Conservative", 0, 100)]
        self.assertEqual(mvt.whip_label({"whip": "whipped"}, "", split),
                         {"Labour": "whipped", "Conservative": "whipped"})

    def test_a_bare_whipped_with_no_bloc_claims_nothing(self):
        """A whip was on; the record does not say whose. Claiming it for
        every party is how a Reform UK member acquired a Labour whip."""
        self.assertEqual(
            mvt.whip_label({"whip": "whipped"}, "", [("Labour", 200, 180)]), {})

    def test_a_third_party_voting_the_same_way_is_not_claimed(self):
        """Unanimity is not evidence of instruction: a party can agree."""
        split = [("Labour", 400, 1), ("Conservative", 0, 100),
                 ("Reform UK", 5, 0)]
        self.assertNotIn("Reform UK", mvt.whip_label({}, "", split))

    def test_an_explicit_map_still_wins(self):
        split = [("Labour", 400, 1), ("Conservative", 0, 100)]
        self.assertEqual(
            mvt.whip_label({"whip": {"Labour": "whipped", "Conservative": "free"}},
                           "", split),
            {"Labour": "whipped", "Conservative": "free"})

    def test_free_stays_house_wide(self):
        """A free vote means no party issued an instruction."""
        self.assertEqual(mvt.whip_label({"whip": "free"}, "", []), "free")

    # ---- the client-side rule -------------------------------------------
    def test_the_template_checks_service_before_claiming_a_whip(self):
        flat = " ".join(template().split())
        self.assertIn("if (!servedOn(m, d.date)) return {label: null", flat)

    def test_the_template_uses_the_party_held_on_the_day(self):
        flat = " ".join(template().split())
        self.assertIn("const mine = w[partyOn(m, d.date)];", flat)
        self.assertNotIn("w[m && m.party]", flat,
                         "m.party is today's party; a member who crossed the "
                         "floor was whipped by whoever they belonged to then")

    def test_unknown_service_never_excuses_an_absence(self):
        """A member with no service history must not be credited with 'not
        yet an MP' -- silence in our data is not evidence they were away."""
        flat = " ".join(template().split())
        self.assertIn("if (!periods.length) return true;", flat)


class BillHeadingTests(unittest.TestCase):
    """A card heading describes the vote beneath it."""

    ISSUE = {"id": "parental-rights", "name": "Parental rights in education",
             "bill": "Various"}

    def test_the_stage_suffix_is_removed(self):
        got = mvt.bill_of({"title": "Children's Wellbeing and Schools Bill: "
                                    "Third Reading", "stage": "Third Reading"},
                          self.ISSUE)
        self.assertEqual(got, "Children's Wellbeing and Schools Bill")

    def test_various_is_never_a_heading(self):
        """The issue spans three different bills, so its `bill` says
        "Various" -- honest in config, meaningless as a title over a vote."""
        got = mvt.bill_of({"title": "", "short": "", "stage": "Division"},
                          self.ISSUE)
        self.assertEqual(got, "Parental rights in education")
        self.assertNotEqual(got, "Various")

    def test_no_shipped_division_is_titled_various(self):
        import json as _json
        page = os.path.join(ROOT, "partner_site", "mp-votes.html")
        if not os.path.exists(page):
            self.skipTest("page not built")
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        data = _json.loads(re.search(r"const DATA = (\{.*?\});\n",
                                     text, re.S).group(1))
        for d in data["divisions"]:
            self.assertNotEqual((d.get("bill") or "").lower(), "various")


class PassageCardTests(unittest.TestCase):
    """The card is the bill's passage (Christopher, 2026-08-26: "ship
    option B"): votes and words in the order they happened, so a committee
    speech sits between the readings and explains the vote that follows.
    """

    def test_the_spine_is_chronological(self):
        flat = " ".join(template().split())
        self.assertIn("nodes.sort((a, b) => a.date.localeCompare(b.date)", flat)

    def test_quotes_are_nodes_on_the_spine_not_an_appendix(self):
        """The whole point of B: a quote is placed at its date, among the
        votes, rather than collected underneath them."""
        flat = " ".join(template().split())
        self.assertIn('nodes.push({type: "said", date: q.d, q: q})', flat)
        self.assertNotIn('<p class="wordshead">In their own words</p>', flat,
                         "the trailing words block is replaced by the spine")

    def test_the_header_does_not_repeat_the_spine(self):
        """The header is a summary. Printing the meaning there as well
        showed the Third Reading twice on every card."""
        head = template()
        start = head.index("const cardHead")
        block = head[start:head.index("const passageNodes")]
        self.assertNotIn("${vi.text}", block)
        self.assertIn("cardsum", block)

    def test_a_stage_names_itself_as_its_divisions_do(self):
        """Three approval motions grouped under stage_group 'Third Reading'
        should say "Approval motion", which is what happened."""
        flat = " ".join(template().split())
        self.assertIn("node.label = stages.length === 1 ? stages[0] : node.key", flat)

    def test_a_grouped_stage_summarises_its_verdicts(self):
        flat = " ".join(template().split())
        self.assertIn('infos.filter(v => v.cls === "G").length', flat)
        self.assertNotIn("v.verdict ===", flat,
                         "there is no verdict field; the verdict is in cls")

    def test_every_card_renders_a_passage(self):
        """Guards the whole feature end to end: a card without its spine
        would be a silent regression to a bare headline."""
        page = os.path.join(ROOT, "partner_site", "mp-votes.html")
        if not os.path.exists(page):
            self.skipTest("page not built")
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('class="passage"', text)
        self.assertIn('class="stage"', text)

    def test_no_dead_fallback_for_long_cards(self):
        """The largest card any member can have is seven votes, so a
        compact-roll threshold would be code that never runs."""
        flat = " ".join(template().split())
        self.assertNotIn("compactRoll", flat)


class ProfileDetailTests(unittest.TestCase):
    """Published register detail: contact, roles, seat.

    Everything here is what a member gave Parliament FOR publication. The
    two rules that matter: no address is ever stored or shown, and contact
    sits BELOW the record rather than beside a verdict.
    """

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import pull_profiles
        self.pp = pull_profiles

    def test_no_address_is_ever_taken(self):
        """A "Constituency office" record is frequently a member's home."""
        got = self.pp.parse_contact([
            {"type": "Constituency office", "line1": "12 Private Road",
             "line5": "Wiltshire", "postcode": "SN1 2AB",
             "email": "mp@example.org", "phone": "01234 567890"},
            {"type": "Parliamentary office", "line1": "House of Commons",
             "postcode": "SW1A 0AA", "email": "mp@parliament.uk"},
        ])
        flat = " ".join(got.values())
        for leak in ("Private Road", "SN1 2AB", "SW1A", "Wiltshire",
                     "House of Commons"):
            self.assertNotIn(leak, flat)

    def test_the_parliamentary_email_wins(self):
        got = self.pp.parse_contact([
            {"type": "Constituency office", "email": "local@example.org"},
            {"type": "Parliamentary office", "email": "mp@parliament.uk"},
        ])
        self.assertEqual(got["email"], "mp@parliament.uk")

    def test_an_email_filed_under_the_constituency_is_still_taken(self):
        """Some members file their parliament.uk address there and nowhere
        else -- Danny Kruger is one."""
        got = self.pp.parse_contact([
            {"type": "Constituency office", "email": "d.k.mp@parliament.uk"}])
        self.assertEqual(got["email"], "d.k.mp@parliament.uk")

    def test_unknown_contact_types_are_ignored_not_guessed(self):
        got = self.pp.parse_contact([
            {"type": "Mastodon", "isWebAddress": True, "line1": "https://m.example"}])
        self.assertEqual(got, {})

    def test_the_api_envelope_is_unwrapped(self):
        """Passing {"value": ..., "links": ...} to the parsers made them
        iterate the envelope's KEYS, so a 650-member run stored nothing --
        silently, because per-member failures are caught by design."""
        with open(os.path.join(ROOT, "tools", "pull_profiles.py"),
                  encoding="utf-8") as fh:
            self.assertIn('return payload["value"]', fh.read())

    # ---- Parliament's line vs ours --------------------------------------
    def test_continuous_service_comes_from_parliaments_own_sentence(self):
        got = mvt.continuous_since(
            "Sir Christopher Chope is the Conservative MP for Christchurch, "
            "and has been an MP continually since 1 May 1997.")
        self.assertEqual(got, "1997-05-01")

    def test_a_synopsis_without_a_date_yields_nothing(self):
        self.assertIsNone(mvt.continuous_since("An MP for somewhere."))
        self.assertIsNone(mvt.continuous_since(None))

    def test_the_header_prefers_continuous_service(self):
        """"MP since 1983" for Chope claims service he did not have: he was
        out from 1992 to 1997. 24 of 650 members differ this way."""
        flat = " ".join(template().split())
        self.assertIn("const cont = (m.seat || {}).continuous;", flat)
        self.assertIn("first elected ${first.slice(0, 4)}", flat)

    # ---- placement -------------------------------------------------------
    # MOVED INTO THE HERO on Christopher's instruction, 2026-08-26, after
    # four rounds of mockups: "Perhaps a second column is better after all?"
    # I had put it below the record because a social handle beside a red BAD
    # VOTE chip is effectively a pile-on button, and that reasoning still
    # stands -- so what survives the move is the mitigation, not the
    # placement: the parliamentary office leads and stays readable, the
    # handles are reduced to quiet icons, and no address is ever shown.
    def test_contact_is_the_heros_second_column(self):
        t = template()
        self.assertIn("contactColumn(m)", t)
        # Compare against the RENDERED form. Searching for "card-summary"
        # finds the CSS rule near the top of the file instead, which is the
        # same anchor mistake that has now bitten three of these tests.
        self.assertLess(t.index("${contactColumn(m)}"),
                        t.index('<div class="card-summary">'),
                        "the column belongs in the hero, above the summary line")
        self.assertNotIn("contactBlock", t,
                         "the bottom block was MOVED, not duplicated")

    def test_the_parliamentary_office_stays_readable_text(self):
        """An icon-only mailto is useless to anyone on webmail, and reducing
        the official route to a glyph gives it the same weight as a Facebook
        page -- which is what keeps this block constituent service."""
        flat = " ".join(template().split())
        block = flat[flat.index("function contactColumn"):]
        self.assertIn("PARLIAMENTARY OFFICE", block)
        self.assertIn('class="em" href="mailto:', block)
        self.assertLess(block.index('class="em"'), block.index('class="icons"'))

    def test_social_links_carry_nofollow(self):
        flat = " ".join(template().split())
        block = flat[flat.index("function contactColumn"):]
        self.assertIn('rel="noopener nofollow"', block)

    def test_every_icon_has_an_accessible_name(self):
        """Icon-only links need a name, and a phone has no hover -- so the
        label cannot live in title= alone."""
        flat = " ".join(template().split())
        block = flat[flat.index("function contactColumn"):]
        self.assertIn('aria-label="${esc(i.label)}"', block)

    def test_icons_are_drawn_not_fetched(self):
        """The page is a single self-contained file. These are letterforms
        and simple shapes; the official brand marks are specific paths that
        would have to be sourced."""
        flat = " ".join(template().split())
        self.assertNotIn("cdn", flat.lower())
        block = flat[flat.index("const ICONS"):flat.index("function contactColumn")]
        self.assertIn("<svg viewBox", block)
        self.assertNotIn("http", block)

    def test_absent_details_render_nothing_rather_than_a_gap(self):
        """155 members publish no website or social link at all, and one
        publishes no contact of any kind."""
        flat = " ".join(template().split())
        block = flat[flat.index("function contactColumn"):]
        self.assertIn("ICON_ORDER.filter(k => c[k])", block)
        self.assertIn('if (!c.email && !c.phone && !links.length) return "";',
                      block)


class HeroRoleTests(unittest.TestCase):
    """The post is a LINE, the committees are pills below the majority.

    Christopher, 2026-08-26: "apply the line under their name whether it be
    a secretary of state or backbencher, any committee pills should be added
    underneath the majority line."

    The line exists because a job title is a phrase: ministerial titles run
    to 159 characters, and 116 current posts across 109 members are over 46,
    so one page in six had a paragraph with rounded corners in its hero.
    """

    def test_the_post_line_always_renders(self):
        flat = " ".join(template().split())
        block = flat[flat.index("function postLine"):flat.index("function committeePills")]
        self.assertIn('<div class="postline quiet">Backbencher</div>', block)
        self.assertIn('<div class="postline">', block)

    def test_both_titles_occupy_the_same_position(self):
        """Christopher, 2026-08-26: "both titles should occupy the same
        position as one another."

        An earlier plan moved "Backbencher" to the meta row and left
        ministerial titles on the post line, which split the same field by
        its VALUE -- so a reader comparing two members would hunt in
        different places for the same fact. One slot; the weight varies.
        """
        flat = " ".join(template().split())
        block = flat[flat.index("function postLine"):flat.index("function committeePills")]
        # both returns emit .postline, and nothing emits into mp-meta
        self.assertEqual(block.count('class="postline'), 2)
        self.assertNotIn("mp-meta", block)
        # and the slot itself sits between the meta row and the majority
        t = template()
        self.assertLess(t.index('<div class="mp-meta">'), t.index("${postLine(m)}"))
        self.assertLess(t.index("${postLine(m)}"), t.index("${seatLine(m)}"))

    def test_a_held_office_carries_weight_and_the_fallback_does_not(self):
        """The fallback is 69% of pages (447 of 650); left at full weight it
        spends the most prominent line under the name on one word meaning
        "holds no post"."""
        flat = " ".join(template().split())
        self.assertIn(".postline{font-size:13px;color:#fff;font-weight:500", flat)
        self.assertIn(".postline.quiet{font-size:12.5px;color:#cfe0fc;font-weight:400}",
                      flat)

    def test_jointly_with_is_dropped(self):
        """The only genuinely redundant part of a ministerial title on a
        public page, and it takes the longest from 159 characters to a line."""
        flat = " ".join(template().split())
        self.assertIn("JOINTLY", flat)
        self.assertIn("(Jointly with[^)]*)", " ".join(template().split())
                      .replace("\\", ""))

    def test_committees_sit_below_the_majority(self):
        t = template()
        self.assertLess(t.index("${postLine(m)}"), t.index("${seatLine(m)}"))
        self.assertLess(t.index("${seatLine(m)}"), t.index("${committeePills(m)}"))

    def test_committees_are_still_pills(self):
        flat = " ".join(template().split())
        block = flat[flat.index("function committeePills"):]
        self.assertIn('class="rolepill"', block)
        self.assertIn("coms.length > 2", block)


class NoBacklinkTests(unittest.TestCase):
    """The MP header has no "New search" link (Christopher, 2026-08-26:
    "For now people can just scroll up to the find your MP box").

    The search box lives outside #main, so it survives renderMP and is
    genuinely still there to scroll back to.
    """

    def test_the_header_has_no_new_search_link(self):
        t = template()
        self.assertNotIn("New search", t)
        self.assertNotIn("backlink", t, "its CSS went with it")

    def test_no_listener_looks_for_the_removed_element(self):
        """getElementById("back") would return null once the element is gone,
        and the TypeError would take the whole render down with it."""
        t = template()
        self.assertNotIn('getElementById("back")', t)

    def test_the_search_box_is_outside_the_render_target(self):
        """What makes "scroll up" true: renderMP replaces #main only."""
        t = template()
        self.assertLess(t.index('<div class="searchbox">'),
                        t.index('<main id="main">'))

    def test_the_masthead_reset_still_works(self):
        """resetToEmpty is still reachable -- the masthead link calls it."""
        t = template()
        self.assertIn("function resetToEmpty()", t)
        self.assertIn('getElementById("home")', t)


class NoDivisionWideWhipBadgeTests(unittest.TestCase):
    """The tally's whipBadge is gone.

    It tested `d.whip === "whipped"`, and when whipping became per-party on
    2026-08-26 the value became an object -- so the badge silently returned
    empty on all three whipped divisions. Repairing it would have restored a
    DIVISION-WIDE whip claim, which is exactly what Christopher had just
    asked to stop: whipChip already states it per party, and only for the
    party a member sat for on the day.
    """

    def test_the_badge_is_gone(self):
        t = template()
        self.assertNotIn("whipBadge", t)
        self.assertNotIn('class="whip free"', t)
        self.assertNotIn('class="whip whipped"', t)

    def test_the_per_party_chip_is_what_remains(self):
        t = template()
        self.assertIn("function whipChip", t)
        self.assertIn("whipmark", t)

    def test_the_tally_still_shows_the_counts(self):
        flat = " ".join(template().split())
        self.assertIn("Ayes ${d.ayes} &ndash; Noes ${d.noes}", flat)
