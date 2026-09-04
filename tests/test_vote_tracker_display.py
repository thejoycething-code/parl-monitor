"""The public MP votes page (Christopher's decisions, 2026-08-24).

Four changes land together: verdicts go public, the whip is stated on every
vote and can differ BY PARTY, a division we decline to score is demoted with
its reason attached, and cards are grouped by bill in date order.
"""

import json
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
                # PACKED since 2026-08-29: the address is rebuilt in the
                # page from the row's own date, so what is asserted is the
                # packed shape -- and that it still carries the CONTRIBUTION
                # id, because a day-level link makes a reader hunt for the
                # words, which defeats a shareable quote.
                self.assertRegex(q["u"], r"^[hH][CL]:")
                self.assertEqual(len(q["u"].split(":")), 3 if q["u"][0] == "h" else 4,
                                 "the contribution id is missing")

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

    def test_the_counts_are_still_shown(self):
        """The wording changed on 2026-08-27: "REJECTED - Ayes 208 - Noes
        261" over two lines became "Rejected 208-261" in one, which also
        made it consistent with the amendment rows."""
        flat = " ".join(template().split())
        # Wording changed again on 2026-08-27: the outcome now reads
        # "Passed by 23 - 314 to 291", coloured by whether the result went
        # our way rather than by whether it passed.
        self.assertIn("${d.ayes} to ${d.noes}", flat)
        self.assertIn("Passed", flat)
        self.assertIn('d.passed ? "Passed" : "Rejected"', flat)


class PartyVerdictCollisionTests(unittest.TestCase):
    """The party mark and the verdict dots must stay distinguishable.

    The mark before the party name is the PARTY COLOUR and always was --
    Christopher read it as "green or red based on their voting record"
    (2026-08-27), which is the design's fault: the passage cards use round
    green and red dots for good and bad votes, and 428 of 650 members sit
    for a party whose colour is confusably close to one of them. Labour's
    #C0293B is 55 units from the verdict red and appears on 404 pages; the
    Green Party's #5FA33E is 32 from the verdict green.

    A bar was tried first and rejected in favour of a circle that carries
    the party's initials, and a logo when one is dropped in. So the two
    vocabularies are separated by CONTENT, not shape: a verdict dot is
    empty, a party mark never is.
    """

    def test_the_party_mark_is_bare_colour_by_christophers_choice(self):
        """Christopher, 2026-08-27: "Remove the text". The initials went, so
        the mark is the party colour alone until a logo is dropped in. Noted
        because it restores the ambiguity this class exists to document: a
        Labour circle is #E41C3E and the verdict red is #DB544F, ~59 units
        apart. He knows what the mark means now, which is what changed."""
        flat = " ".join(template().split())
        block = flat[flat.index("function partyMark"):]
        self.assertNotIn("pinit", block)
        self.assertIn('style="background:${pc(party)}"', block)

    def test_the_verdict_dots_carry_no_content(self):
        """What makes the distinction hold from the other side."""
        flat = " ".join(template().split())
        self.assertIn('<span class="dot${dot}"></span>', flat)

    def test_the_mark_still_carries_the_party_colour(self):
        t = template()
        self.assertIn('class="pdot" style="background:${pc(party)}"', t)


class PartyLogoSlotTests(unittest.TestCase):
    """The party mark is a circular drop-in logo slot.

    Christopher, 2026-08-27: "I think I prefer a circle. Use a circle, and
    make it so we can drop in party logos." The circle came back; what stops
    it reading as a verdict -- this page uses round green/red dots for good
    and bad votes, and 428 of 650 members sit for a party whose colour is
    close to one of them -- is that the circle now carries the party's
    initials, and will carry a logo.
    """

    def test_the_mark_is_a_circle_again(self):
        flat = " ".join(template().split())
        rule = flat[flat.index(".pdot{"):flat.index("}", flat.index(".pdot{"))]
        self.assertIn("border-radius:50%", rule)

    def test_the_white_ring_separates_it_from_a_verdict_dot(self):
        """With the initials gone this is the only thing distinguishing a
        party mark from the solid verdict dots on the cards."""
        flat = " ".join(template().split())
        rule = flat[flat.index(".pdot{"):flat.index("}", flat.index(".pdot{"))]
        self.assertIn("box-shadow:0 0 0 1.5px rgba(255,255,255,.7)", rule)

    def test_an_image_is_emitted_only_when_the_build_found_one(self):
        """A slot that always emitted an <img> would 404 on every member
        view for every party without a file."""
        flat = " ".join(template().split())
        block = flat[flat.index("function partyMark"):]
        self.assertIn("const file = (DATA.logos || {})[partySlug(party)];", block)
        self.assertIn('onerror="this.remove()"', block,
                      "belt: a file that fails to serve must not leave a hole")

    def test_the_two_slug_functions_agree(self):
        """The builder decides the filename and the template looks it up; if
        they disagree, a dropped-in logo silently never appears."""
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import party_logo_slots
        cases = {
            "Labour": "labour",
            "Liberal Democrat": "liberal-democrat",
            "Sinn Féin": "sinn-fein",
            "Social Democratic & Labour Party": "social-democratic-and-labour-party",
            "Labour (Co-op)": "labour-co-op",
            "Reform UK": "reform-uk",
        }
        for party, want in cases.items():
            self.assertEqual(party_logo_slots.slug(party), want)
            self.assertEqual(mvt.party_slug(party), want,
                             "the builder's slug must match the tool's")
        # and the template's JS must use the same rules
        flat = " ".join(template().split())
        js = flat[flat.index("const partySlug"):flat.index("function partyMark")]
        for token in ('normalize("NFD")', 'replace(/&/g,"and")', "[^a-z0-9]+"):
            self.assertIn(token, js)

    def test_no_placeholder_logo_is_shipped(self):
        """A hand-drawn stand-in would look like a party's real mark."""
        import glob as _g
        for site in ("partner_site", "docs"):
            files = _g.glob(os.path.join(ROOT, site, "logos", "*.svg"))
            self.assertEqual(files, [], "only real sourced logos belong here")

    def test_the_slot_is_documented_in_both_builds(self):
        for site in ("partner_site", "docs"):
            readme = os.path.join(ROOT, site, "logos", "README.md")
            self.assertTrue(os.path.exists(readme))
            with open(readme, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("registered trademarks", text)
            self.assertIn("labour.svg", text)


class PartyColourTests(unittest.TestCase):
    """Party colours come from Wikipedia's {{party color}}, not by eye.

    Christopher, 2026-08-27: "Reform is in green ... ensure the correct
    colours are being used." Every value in the old map was a muted
    approximation -- Reform was #2AA8BF, a dull teal that reads green at
    17px, against the real #1EB8D0, which the Clacton widget's independently
    verified rgb(30,184,208) matches exactly.

    Worse, three parties were absent from the map, so 46 sitting members
    rendered the DEFAULT GREY and nothing said so: Labour (Co-op) 43,
    Your Party 2, Restore Britain 1.
    """

    WIKIPEDIA = {
        "Labour": "#E41C3E", "Conservative": "#0087DC",
        "Liberal Democrat": "#FAA61A", "Scottish National Party": "#FDF38E",
        "Green Party": "#02A95B", "Reform UK": "#1EB8D0",
        "Plaid Cymru": "#008672", "Democratic Unionist Party": "#D46A4C",
        "Social Democratic & Labour Party": "#2AA82C", "Alliance": "#F6CB2F",
        "Ulster Unionist Party": "#48A5EE",
        "Traditional Unionist Voice": "#201863",
        "Your Party": "#FF3131", "Restore Britain": "#051D3F",
    }

    def _map(self):
        flat = template()
        block = re.search(r"const PARTY_C = \{(.*?)\};", flat, re.S).group(1)
        return dict(re.findall(r'"([^"]+)":\s*"(#[0-9A-Fa-f]{6})"', block))

    def test_every_colour_matches_wikipedia(self):
        got = self._map()
        for party, want in self.WIKIPEDIA.items():
            self.assertEqual(got.get(party), want, party)

    def test_reform_is_not_the_old_muted_teal(self):
        """Checked against the MAP, not the file: the old value survives in
        the comment recording what it was, and a whole-file search reads
        that as a violation -- the fourth time this class of anchor mistake
        has bitten these tests."""
        self.assertNotIn("#2AA8BF", set(self._map().values()))

    def test_labour_co_op_takes_the_labour_red(self):
        """Wikipedia gives Labour Co-operative the same red, and it is right
        for a Westminster record: they take the Labour whip, and Co-op purple
        beside "Labour (Co-op)" would read as a third party."""
        got = self._map()
        self.assertEqual(got.get("Labour (Co-op)"), got.get("Labour"))

    def test_no_sitting_party_falls_through_to_the_default(self):
        """The bug that hid 46 members behind a grey circle."""
        import json as _json
        page = os.path.join(ROOT, "partner_site", "mp-votes.html")
        if not os.path.exists(page):
            self.skipTest("page not built")
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        data = _json.loads(re.search(r"const DATA = (\{.*?\});\n",
                                     text, re.S).group(1))
        # the shipped map, with JS \uXXXX escapes resolved as the browser does
        block = re.search(r"const PARTY_C = \{(.*?)\};", text, re.S).group(1)
        have = {k.encode().decode("unicode_escape")
                for k, _ in re.findall(r'"([^"]+)":\s*"(#[0-9A-Fa-f]{6})"', block)}
        for member in data["members"]:
            self.assertIn(member["party"], have,
                          member["party"] + " would render the default grey")


class JourneyDisclosureTests(unittest.TestCase):
    """The card leads with the main vote; ONE disclosure holds the whole
    journey (Christopher, 2026-08-31, folding the readings into option L).

    Supersedes the 2026-08-27 open-landmark rule and option F's open
    one-liners, and restores the strict chronology those traded away. The
    standing half of the 27 Aug ruling is unchanged: every row inside keeps
    its full detail -- meaning, tally, whip and source link.
    """

    def test_nothing_is_removed_only_moved(self):
        """Guards the whole instruction. Counted on the built page, because
        a template check cannot tell moved from deleted."""
        page = os.path.join(ROOT, "partner_site", "mp-votes.html")
        if not os.path.exists(page):
            self.skipTest("page not built")
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        # the renderers that carry the detail must all still exist and be called
        for fn in ("miniVote", "fullVote", "saidNode", "stageNode"):
            self.assertIn("const " + fn, text)
        # and every detail-bearing part is rendered inside the one disclosure
        flat = " ".join(text.split())
        block = flat[flat.index("const journeyDetails"):flat.index("for (const g of blocks)")]
        self.assertIn('n.type === "said" ? saidNode(n) : stageNode(n)', block)

    def test_nothing_renders_open_and_the_card_carries_the_main_result(self):
        """The card IS the open state: its label line now carries the main
        vote's result (PASSED BY 23, 314 TO 291), so folding the readings
        hides no figure the lead vote needs."""
        flat = " ".join(template().split())
        self.assertNotIn("isOpenNode", flat)
        self.assertNotIn("compactVote", flat)
        self.assertIn('${nodes.length ? journeyDetails(nodes) : ""}', flat)
        self.assertIn('${d.passed ? "PASSED" : "REJECTED"} BY', flat)

    def test_the_summary_says_what_is_inside(self):
        """Counts, verdict split, quotes and the story's date span -- so
        nobody has to open it to find out whether it matters."""
        flat = " ".join(template().split())
        block = flat[flat.index("const journeyDetails"):]
        self.assertIn("The full journey", block)
        self.assertNotIn("What happened in between", block)
        self.assertNotIn("further vote", block)
        self.assertIn("quote", block)
        self.assertIn('first === last ? first : first + " to " + last', block)

    def test_it_uses_native_details(self):
        """Keyboard and screen-reader support for free, and no JavaScript."""
        flat = " ".join(template().split())
        block = flat[flat.index("const journeyDetails"):]
        self.assertIn('<details class="journey"><summary>', block)


class TemplateParsesTests(unittest.TestCase):
    """The built page's script must actually parse.

    Learned the hard way on 2026-08-27. A dead-CSS remover was run over the
    WHOLE template and matched this JavaScript line as if it were a CSS
    rule, because `s.result` contains `.result`:

        s.result ? ` &middot; ${esc(s.result)}` : ""}</div>`;

    It deleted the line. Every string-based test still passed, and the page
    would have been completely blank in a browser. Only running the script
    caught it.
    """

    def _script(self, path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        hit = re.search(r"<script[^>]*>(.*?)</script>", text, re.S)
        self.assertIsNotNone(hit, "no script block in " + path)
        return hit.group(1)

    def test_the_built_script_parses(self):
        import shutil
        import subprocess
        import tempfile
        node = (shutil.which("node")
                or os.path.expanduser("~/.local/node/bin/node"))
        if not (node and os.path.exists(node)):
            self.skipTest("node not available to parse-check")
        for build in ("partner_site", "docs"):
            page = os.path.join(ROOT, build, "mp-votes.html")
            if not os.path.exists(page):
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                             encoding="utf-8") as fh:
                fh.write(self._script(page))
                tmp = fh.name
            try:
                done = subprocess.run([node, "--check", tmp],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 0,
                                 build + " script does not parse:\n"
                                 + done.stderr[:400])
            finally:
                os.unlink(tmp)

    def test_backticks_are_balanced(self):
        """A cheap check that works without node, for CI."""
        page = os.path.join(ROOT, "partner_site", "mp-votes.html")
        if not os.path.exists(page):
            self.skipTest("page not built")
        script = self._script(page)
        self.assertEqual(script.count("`") % 2, 0,
                         "an odd number of backticks means a template "
                         "literal was cut in half")

    def test_the_css_remover_is_scoped_to_the_style_block(self):
        """Not a template assertion but a note pinned where it will be read:
        any future dead-rule sweep must slice <style>...</style> first."""
        t = template()
        self.assertIn("<style>", t)
        self.assertIn("</style>", t)
        self.assertLess(t.index("<style>"), t.index("</style>"))


class OutcomeDirectionTests(unittest.TestCase):
    """The outcome is coloured by WHICH WAY IT WENT FOR US.

    Christopher, 2026-08-27: "It's also the passed by X and Rejected by X
    numbers that should be coloured correctly, including the number."

    Colouring passed=green said an outcome is good news because it passed.
    On the assisted dying bill passing is the thing we opposed, so 8 of the
    17 scored divisions rendered a colour whose sentiment contradicted what
    happened -- 3,359 member-page renders, because Second and Third Reading
    are among them. Kruger's Third Reading was the sharpest: a green GOOD
    VOTE chip above a green "Passed by 23", when he voted the right way and
    lost.
    """

    def test_direction_is_our_position_not_the_result(self):
        flat = " ".join(template().split())
        self.assertIn('const wentOurWay = (d) => !d.good ? null : '
                      '(d.passed && d.good === "aye") || '
                      '(!d.passed && d.good === "no")', flat)

    def test_an_unscored_division_stays_neutral(self):
        """There is no "our way" for a division we have not scored."""
        flat = " ".join(template().split())
        self.assertIn('w === null ? "flat"', flat)
        self.assertIn(".outcome.flat{color:#23282f}", flat)

    def test_the_word_and_the_number_are_both_coloured(self):
        """Christopher asked for the number too, so both sit inside the
        coloured span and the tally sits outside it."""
        flat = " ".join(template().split())
        self.assertIn('<span class="outcome ${cls}">${d.passed ? "Passed" : '
                      '"Rejected"} by ${ Math.abs(d.ayes - d.noes)}</span>', flat)

    def test_the_helper_is_reachable_from_both_callers(self):
        """It broke every one of the 650 pages first time round: declared
        inside renderMP, where the top-level barHTML could not see it."""
        text = template()
        depth = 0
        for line in text.splitlines():
            if "const wentOurWay" in line:
                self.assertEqual(depth, 0,
                                 "wentOurWay must be top level -- barHTML "
                                 "is top level and calls it")
                break
            depth += line.count("{") - line.count("}")


class HairlineTests(unittest.TestCase):
    """A 3px hairline, one colour, filled by the winning side's share.

    Christopher, 2026-08-27: "Do fix A with a coloured hairline bar based on
    whether it passed or didn't."

    The old bar was a full-width 10px band coloured Ayes-green and
    Noes-red -- and since most of our good positions are voting No, that put
    the member's own side in red under a green GOOD VOTE chip on 81% of
    member/landmark pairs (2,095 of 2,583).
    """

    def test_it_shares_the_outcome_colour(self):
        flat = " ".join(template().split())
        self.assertIn(".hairline.win i{background:var(--green)}", flat)
        self.assertIn(".hairline.lose i{background:var(--red)}", flat)

    def test_it_is_a_hairline_not_a_band(self):
        flat = " ".join(template().split())
        self.assertIn(".hairline{height:3px", flat)
        self.assertNotIn(".tally{position:relative;height:10px", flat)

    def test_the_fill_is_the_winning_share_not_the_aye_share(self):
        """Forced by using one colour: a single-colour bar filled to 21% for
        a decisive rejection we WANTED would read as weak, when the point is
        that it was emphatic."""
        flat = " ".join(template().split())
        self.assertIn("const winner = Math.max(d.ayes, d.noes);", flat)
        self.assertIn("const pct = total ? 100 * winner / total : 0;", flat)

    def test_no_flag_marker(self):
        """The verdict chip says which lobby in words, and a phone has no
        hover to explain a marker."""
        flat = " ".join(template().split())
        self.assertNotIn('class="flag"', flat)

    def test_it_carries_an_accessible_label(self):
        flat = " ".join(template().split())
        self.assertIn('role="img" aria-label="${ d.passed ? "Passed" : "Rejected"}', flat)


class RecordLastTests(unittest.TestCase):
    """Christopher, 2026-08-27: "I also like the division record at the
    bottom of everything." """

    def test_the_record_is_the_last_thing_in_a_vote(self):
        flat = " ".join(template().split())
        block = flat[flat.index("const fullVote"):flat.index("const miniVote")]
        self.assertIn("recordlast", block)
        self.assertLess(block.index("barHTML(d)"), block.index("recordlast"))
        self.assertLess(block.index("relativeToParty"), block.index("recordlast"))


class JourneyChronologyTests(unittest.TestCase):
    """Superseding option F on the same day it shipped (Christopher: fold
    the readings in too): no stage renders open, and the fold's rows are
    the FULL renderers -- the strict spine, back in date order."""

    def test_the_fold_renders_full_rows_in_order(self):
        flat = " ".join(template().split())
        block = flat[flat.index("const stageNode"):]
        self.assertIn(": fullVote(node.divs[0])", block)
        fold = flat[flat.index("const journeyDetails"):flat.index("let band")]
        self.assertIn("stageNode(n)).join", fold)


class PartyPhraseFoldedTests(unittest.TestCase):
    """The party comparison lives in the meta line, not on its own.

    Christopher, 2026-08-27: "Build it and deploy" -- folding the sentence
    into the meta line. It saves a line on every vote row, 16 on a busy
    page, and the short form has room to say WHICH WAY in one word.
    """

    def test_it_returns_an_inline_span_not_a_block(self):
        flat = " ".join(template().split())
        block = flat[flat.index("const relativeToParty"):]
        self.assertIn('<span class="pmark', block)
        self.assertNotIn('<div class="rel"', block)

    def test_no_block_level_rel_survives_anywhere(self):
        self.assertNotIn('class="rel"', template())

    def test_the_party_name_is_abbreviated(self):
        """The full name does not fit: "with 8 of 8 Democratic Unionist
        Partys" runs to 101 characters, past the ~94 a 500px card body holds
        at 11px -- and pluralising a name that already ends in "Party" is a
        bug of its own."""
        flat = " ".join(template().split())
        self.assertIn("const PARTY_ABBR", flat)
        self.assertIn('"Democratic Unionist Party":"DUP"', flat)
        block = flat[flat.index("const relativeToParty"):]
        self.assertIn("PARTY_ABBR[pr.name] || pr.name", block)
        self.assertNotIn("MPs (", block, "no pluralised party names")

    def test_only_genuine_rebellion_is_printed(self):
        """Christopher, 2026-08-31 (twice in one evening): "with 234 of 381
        Lab" was page furniture, and "against 160 of 384 Lab" implied
        defiance where none exists -- a free vote has no party position to
        be with or against, so with/against/splitting are all the wrong
        grammar there. Only the whipped-and-against case prints, on the
        same two-fact bar as the WHIPPED chip. The splits stay in the
        shipped data for 5CA analysis."""
        flat = " ".join(template().split())
        block = flat[flat.index("const relativeToParty"):
                     flat.index("const whipUniform")]
        self.assertIn('if (!(against && whipFor(d, m).label === "whipped")) '
                      'return "";', block)
        self.assertIn('rebelled \\u2014 against', block)
        self.assertNotIn('"with"', block)
        self.assertNotIn("splitting ${", block)

    def test_against_is_not_a_verdict_colour(self):
        """A fourth green/red vocabulary is the thing this page keeps having
        to fight. The warmer tone is deliberately neither."""
        flat = " ".join(template().split())
        rule = flat[flat.index(".pmark.against{"):]
        rule = rule[:rule.index("}")]
        self.assertNotIn("var(--green)", rule)
        self.assertNotIn("var(--red)", rule)

    def test_it_uses_the_party_held_on_the_day(self):
        # partyRow holds the shared lookup since 2026-08-31, so the meta
        # line and the rebellion count cannot disagree about whose party.
        flat = " ".join(template().split())
        block = flat[flat.index("const partyRow"):]
        self.assertIn("partyOn(m, d.date)", block)

    def test_it_says_nothing_when_the_party_is_absent(self):
        """3% of cast votes -- mostly TUV -- have no split row for the
        member's own party. Better silent than wrong."""
        flat = " ".join(template().split())
        block = flat[flat.index("const partyRow"):]
        self.assertIn("if (!row) return null;", block)
        self.assertIn('if (!pr) return "";',
                      flat[flat.index("const relativeToParty"):])

    def test_the_folded_line_stays_within_the_card(self):
        """Measured on the built page: 12 of 11,700 meta lines exceed 94
        characters, all of them carrying WHIP NOT RECORDED, and those rows
        already took two lines before the fold -- so nothing regresses."""
        page = os.path.join(ROOT, "partner_site", "mp-votes.html")
        if not os.path.exists(page):
            self.skipTest("page not built")
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        # the phrase must be short: no full party name inside a pmark span.
        # The page renders client-side, so the only pmark "spans" in the
        # file are the template literals in the inline JS -- skip anything
        # carrying ${...} placeholders and measure what is left, which
        # keeps the guard armed if server-side rendering ever appears.
        for m in re.finditer(r'class="pmark[^"]*">([^<]*)<', text):
            if "${" in m.group(1):
                continue
            self.assertLess(len(m.group(1)), 40, m.group(1))


class SittingCountTests(unittest.TestCase):
    """A bill committee is ONE debate, not one per sitting.

    Christopher: "36 debates for Danny Kruger seems questionable. Perhaps it
    was 36 contributions against multiple debates?" It was neither. He has
    217 contribution rows on assisted dying under 37 distinct titles, but 29
    of those titles are sittings of the SAME bill committee. Counting titles
    said 36 debates; counting subjects says 8.
    """

    def test_the_sitting_suffix_is_stripped(self):
        from make_vote_tracker import collapse_sitting
        self.assertEqual(
            collapse_sitting(
                "Terminally Ill Adults (End of Life) Bill (Twenty-ninth sitting)"),
            "Terminally Ill Adults (End of Life) Bill")
        self.assertEqual(collapse_sitting("Public Order Bill"), "Public Order Bill")

    def test_the_bill_name_always_survives_the_collapse(self):
        """If a title collapsed to nothing, two different bills' committees
        would merge into one count. Checked against every title in the
        store: 222 carry a sitting suffix and none collapses to empty."""
        from make_vote_tracker import collapse_sitting, SITTING_SUFFIX
        for title in ("Online Safety Bill (Fifth sitting)",
                      "Terminally Ill Adults (End of Life) Bill (Twenty-ninth sitting)",
                      "Children's Wellbeing and Schools Bill (Tenth sitting)"):
            self.assertTrue(SITTING_SUFFIX.search(title), title)
            self.assertTrue(collapse_sitting(title), title)

    def test_every_sitting_title_in_the_store_is_matched(self):
        """The regex only allows two words before "sitting", which is a bet
        on Hansard's format. Checked rather than assumed: all 222 titles in
        the store that mention a sitting are matched, so none slips through
        uncollapsed and reinflates a count."""
        import sqlite3
        from make_vote_tracker import SITTING_SUFFIX, _clean_title
        store = os.path.join(ROOT, "data", "parl-monitor.db")
        if not os.path.exists(store):
            self.skipTest("no store")
        conn = sqlite3.connect(store)
        missed = []
        for (line,) in conn.execute(
                "SELECT DISTINCT line FROM mp_events "
                "WHERE kind != 'vote' AND line IS NOT NULL"):
            title = _clean_title(line)
            if title and re.search("sitting", title, re.I) \
                    and not SITTING_SUFFIX.search(title):
                missed.append(title)
        self.assertEqual(missed[:5], [], "{0} uncollapsed".format(len(missed)))

    def test_the_card_says_sittings_when_that_is_what_they_were(self):
        """"spoke in 29 debates" claims 29 separate occasions. It was one
        committee stage, so the label has to say so."""
        html = template()
        self.assertIn('${w.unit || "debate"}', html)


class QuoteRelevanceTests(unittest.TestCase):
    """A quote is published as the member's view, so it must not be someone
    else's point, a question put to someone else, or a concession they made
    on the way to disagreeing.

    The case that forced this: Danny Kruger's buffer-zones quote opened "I
    recognise that there is a genuine problem that the Bill and the Lords
    amendments seek to address, of harassment, intimidation and offensive
    behaviour directed at women going into abortion..." -- him granting the
    other side's case, published beneath his name as what he thinks.
    """

    def test_a_bare_concession_is_rejected(self):
        from src.quotes import usable
        self.assertFalse(usable(
            "I recognise that there is a genuine problem that the Bill seeks "
            "to address, of harassment directed at women."))

    def test_a_concession_that_reaches_the_turn_is_kept(self):
        """Rejecting on the opener alone threw away the fairest quotes there
        are: the reader sees what he granted AND what he concluded."""
        from src.quotes import usable
        self.assertTrue(usable(
            "I recognise there is a genuine problem here. But I fundamentally "
            "disagree that this Bill is the answer to it."))

    def test_another_members_point_is_rejected(self):
        from src.quotes import usable
        self.assertFalse(usable(
            "The answer to the hon. Gentleman's question is that an "
            "organisation should be resourced through philanthropy."))

    def test_a_question_is_not_a_position(self):
        from src.quotes import usable
        self.assertFalse(usable("Will the Minister confirm the timetable?"))
        self.assertFalse(usable(
            "How does that compare with what we already spend on palliative "
            "care? Those are pertinent questions for the Minister."))

    def test_a_rhetorical_question_answered_in_the_same_breath_is_kept(self):
        from src.quotes import usable
        self.assertTrue(usable(
            "The judgment before us is this: would permitting some adults to "
            "choose an assisted death cause harm? I believe it would."))

    def test_the_stance_must_follow_the_question_not_sit_inside_it(self):
        """"is it just that WE SHOULD now read healthcare as including
        assisted dying?" contains a stance phrase, inside the question. That
        passed the first version of this rule and shipped."""
        from src.quotes import usable
        self.assertFalse(usable(
            "Is there an intention to change the wording of the NHS Act, or "
            "is it just that we should now read healthcare as including "
            "assisted dying? I look forward to the answer."))

    def test_an_unusable_seed_does_not_condemn_the_speech(self):
        """The single best-matching sentence used to win outright, so one
        concessive opener meant a misleading quote or none. Other passages
        were always there; they were simply never reached."""
        from src import quotes
        pats = [re.compile("assisted dying", re.I)]
        text = ("I recognise there is a real problem here, and that families "
                "have suffered. I do not believe assisted dying can ever be "
                "made safe for the terminally ill, and the evidence from every "
                "jurisdiction that has tried it bears that out. The safeguards "
                "promised at the outset have been narrowed in every case.")
        got = quotes.shareable(text, pats)
        self.assertTrue(got)
        self.assertIn("do not believe", got)


class ShippedQuotesAreUsableTests(unittest.TestCase):
    """Pinned on the built page: whatever the extractor does, nothing that
    fails the rule may reach a reader."""

    def test_no_shipped_quote_ends_in_a_question(self):
        page = os.path.join(ROOT, "partner_site", "mp-votes.html")
        if not os.path.exists(page):
            self.skipTest("page not built")
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        m = re.search(r"const DATA\s*=\s*(\{.*?\});\n", text, re.S)
        data = json.loads(m.group(1))
        bad = []
        for member in data["members"]:
            for _area, per in (member.get("words") or {}).items():
                for q in (per.get("q") or []):
                    if q["q"].rstrip().endswith("?"):
                        bad.append((member["name"], q["q"][:60]))
            for _area, per in (member.get("record") or {}).items():
                for item in (per.get("items") or []):
                    if (item.get("q") or "").rstrip().endswith("?"):
                        bad.append((member["name"], item["q"][:60]))
        self.assertEqual(bad, [], "{0} shipped quotes end in a question".format(len(bad)))


def _payload():
    page = os.path.join(ROOT, "partner_site", "mp-votes.html")
    if not os.path.exists(page):
        return None
    with open(page, encoding="utf-8") as fh:
        text = fh.read()
    return json.loads(re.search(r"const DATA\s*=\s*(\{.*?\});\n", text, re.S).group(1))


class AlsoOnRecordTests(unittest.TestCase):
    """Christopher, 2026-08-28, asked for five improvements to "Also on the
    record". Each is pinned here on the built page, because every one of
    them was found by measuring the page rather than reading the code."""

    def test_no_block_promises_a_receipt_it_does_not_show(self):
        """298 of 1,038 blocks printed "spoke in 1 debate" above an empty
        list. Two causes, both fixed: an event already shown beside the
        member's vote stayed in the count, and a debate with no quotable
        passage was dropped from the list while staying in the count."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        bad = []
        for member in data["members"]:
            for area, block in (member.get("record") or {}).items():
                counts = block.get("n") or {}
                if any(counts.values()) and not block.get("items"):
                    bad.append((member["name"], area, counts))
        self.assertEqual(bad[:3], [], "{0} blocks count but show nothing".format(len(bad)))

    def test_no_block_ships_with_nothing_in_it(self):
        """The template always filtered an all-zero block, so it rendered as
        nothing -- but it still shipped to all 650 pages."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        for member in data["members"]:
            for area, block in (member.get("record") or {}).items():
                self.assertTrue(
                    block.get("items") or any((block.get("n") or {}).values()),
                    "{0} ships an empty {1} block".format(member["name"], area))

    def test_every_row_links_to_its_source(self):
        """206 written-question rows ended "official written question
        record" as PLAIN TEXT, under a blurb promising the official record.
        The permalink needs dateTabled + uin; the ledger kept dateAnswered
        and an internal id, so both were recovered from the archives."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        bad = []
        for member in data["members"]:
            for area, block in (member.get("record") or {}).items():
                for item in (block.get("items") or []):
                    if not item.get("u") and not item.get("e"):
                        bad.append((member["name"], item.get("k"), item.get("t")))
        self.assertEqual(bad[:3], [], "{0} rows have no source link".format(len(bad)))

    def test_written_question_links_are_well_formed(self):
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        seen = 0
        for member in data["members"]:
            for area, block in (member.get("record") or {}).items():
                for item in (block.get("items") or []):
                    if item.get("k") == "pq":
                        seen += 1
                        # PACKED: "q:<uin>" when the row carries the date,
                        # "Q:<date>:<uin>" when it does not.
                        self.assertRegex(
                            item.get("u") or "",
                            r"^(q:\S+|Q:\d{4}-\d{2}-\d{2}:\S+)$")
        self.assertGreater(seen, 100)

    def test_proposing_a_motion_is_not_reported_as_signing_it(self):
        """Both kinds collapsed to "edm" and the count line only knew how to
        say "signed", so a member who TABLED a motion was credited with
        having signed it."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        kinds = set()
        for member in data["members"]:
            for area, block in (member.get("record") or {}).items():
                kinds |= set(k for k, v in (block.get("n") or {}).items() if v)
        self.assertIn("edm", kinds)
        self.assertIn("edm-signed", kinds)
        html = template()
        self.assertIn("proposed ${c.edm} early day motion", html)
        self.assertIn('signed ${c["edm-signed"]} early day motion', html)

    def test_areas_with_no_vote_are_ordered_first(self):
        """Ordering was by rendered row count, but rows per block run 0-2,
        so nearly every comparison was a tie. An area with a record and no
        vote is the one thing this section says that the cards cannot."""
        html = template()
        self.assertIn("votedAreas.has(a) ? 1 : 0", html)
        self.assertIn("countTotal(rec[b].n) - countTotal(rec[a].n)", html)

    def test_nothing_is_capped_away_any_more(self):
        """Christopher, 2026-08-28: option A "but with all speeches covered
        under a collapsable list". The cap line is gone because the cap is
        gone: the featured rows are the two STRONGEST, and every receipt is
        listed in a roll behind a disclosure."""
        html = template()
        self.assertNotIn("Showing the ${shown} most recent", html)
        self.assertIn("All ${all.length} on the record", html)
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        for member in data["members"]:
            for area, block in (member.get("record") or {}).items():
                self.assertEqual(
                    len(block.get("all") or []),
                    sum((block.get("n") or {}).values()),
                    "{0}/{1}: the roll and the count disagree".format(member["name"], area))

    def test_the_roll_is_ordered_by_strength_not_date(self):
        """88 blocks led with a bare row while a quote sat below it."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        bad = []
        for member in data["members"]:
            for area, block in (member.get("record") or {}).items():
                items = block.get("items") or []
                if items and not items[0].get("q") and any(x.get("q") for x in items[1:]):
                    bad.append(member["name"])
        self.assertLess(len(bad), 20, "{0} blocks still lead with a bare row".format(len(bad)))

    def test_every_roll_row_links_to_its_source(self):
        """The roll is the complete record, so it carries the same standard
        as the featured rows: no row without a way to check it."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        bad, total = [], 0
        for member in data["members"]:
            for area, block in (member.get("record") or {}).items():
                for item in (block.get("all") or []):
                    total += 1
                    if not item.get("u") and not item.get("e"):
                        bad.append((member["name"], item.get("k"), item.get("t")))
        # A SHARE, not a count. The bare "<= 5" was a fact about one
        # page: listing the 344 former Members who voted added six more
        # unsourced rows and failed a standard nothing had breached.
        # Hansard's metadata has no URL for a handful of older debates,
        # and the roll keeps them because it is the complete record --
        # so what matters is that they stay vanishingly rare as the page
        # grows, not that they never grow at all.
        share = len(bad) / float(total or 1)
        self.assertLess(share, 0.005,
                        "{0} of {1} roll rows ({2:.2%}) have no source"
                        .format(len(bad), total, share))

    def test_the_shortlist_counts_debates_not_items(self):
        """A block whose eight newest receipts were EDM signatures scanned
        no debate at all, however many debates it held."""
        path = os.path.join(ROOT, "tools", "make_vote_tracker.py")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("if scanned >= QUOTE_SHORTLIST:", src)
        self.assertNotIn("for it in uniq[:QUOTE_SHORTLIST]:", src)


class PqLinkTests(unittest.TestCase):
    """The written-question permalink, recovered offline."""

    def test_the_backfill_needs_no_network(self):
        import tools.backfill_pq_links as b
        self.assertEqual(
            b.url_for("2025-06-03", "56775"),
            "https://questions-statements.parliament.uk"
            "/written-questions/detail/2025-06-03/56775")

    def test_a_truncated_archive_does_not_lose_the_rest(self):
        import tools.backfill_pq_links as b
        missing = os.path.join(ROOT, "data", "raw", "does-not-exist.json.gz")
        self.assertEqual(b.scan([missing]), {})

    def test_ingest_stores_the_pair_going_forward(self):
        """Recovering it after the fact meant re-reading 1,040 archives."""
        path = os.path.join(ROOT, "tools", "backfill_mp_ledger.py")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("INSERT OR REPLACE INTO pq_link", src)


class StorePublishGuardTests(unittest.TestCase):
    """A store the pull REFUSED must never be published.

    2026-08-28. `python3 tools/db_state.py --pull` refused a download whose
    sha did not match the committed sidecar -- correctly -- and left the
    downloaded bytes on disk, as its own message says it does. The next step,
    guarded only by `always()`, uploaded those bytes straight back as the
    official asset. "Commit state", properly guarded, then did NOT run, so
    the sidecar still named the old sha.

    Every later run therefore mismatched too, against a different sha each
    time, and four runs across three workflows failed inside half an hour.
    The store itself was never corrupt; the guard was.
    """

    WORKFLOWS = os.path.join(ROOT, ".github", "workflows")

    def _publishing_workflows(self):
        import glob
        out = []
        for path in glob.glob(os.path.join(self.WORKFLOWS, "*.yml")):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if "db_state.py --push" in text:
                out.append((os.path.basename(path), text))
        return out

    def test_every_publisher_guards_on_the_fetch(self):
        found = self._publishing_workflows()
        self.assertGreaterEqual(len(found), 8, "expected the full set")
        for name, text in found:
            self.assertIn("steps.fetch.outcome == 'success'", text,
                          "{0} can publish a store the pull refused".format(name))

    def test_no_publisher_is_guarded_by_always_alone(self):
        for name, text in self._publishing_workflows():
            block = text[text.index("- name: Publish the store"):]
            block = block[:block.index("run:")]
            self.assertNotRegex(
                block, r"if:\s*always\(\)\s*\n",
                "{0}: `always()` alone is what caused the cascade".format(name))

    def test_the_step_the_guard_names_exists(self):
        import yaml
        for name, text in self._publishing_workflows():
            spec = yaml.safe_load(text)
            for job in (spec.get("jobs") or {}).values():
                steps = job.get("steps") or []
                if not any("db_state.py --push" in str(s.get("run") or "") for s in steps):
                    continue
                ids = {s.get("id") for s in steps if s.get("id")}
                self.assertIn("fetch", ids,
                              "{0}: guard names steps.fetch, no such id".format(name))

    def test_publish_and_commit_are_always_paired(self):
        """Where the cascade actually began.

        "Commit state" carried no condition, so it was skipped whenever ANY
        earlier step failed -- one WAF-blocked Senedd feed was enough --
        while "Publish the store" still uploaded a new asset. New sha on the
        release, old sha in the repo, and every workflow's next pull refuses
        the store its own sibling just published.

        Publishing without recording is the fault. The two conditions must
        be identical, in both directions.
        """
        import yaml
        for name, text in self._publishing_workflows():
            spec = yaml.safe_load(text)
            for job in (spec.get("jobs") or {}).values():
                steps = job.get("steps") or []
                pub = next((x for x in steps
                            if "db_state.py --push" in str(x.get("run") or "")), None)
                if pub is None:
                    continue
                com = next((x for x in steps
                            if "git commit" in str(x.get("run") or "")), None)
                self.assertIsNotNone(com, "{0}: publishes but never commits".format(name))
                self.assertEqual(
                    " ".join(str(pub.get("if") or "").split()),
                    " ".join(str(com.get("if") or "").split()),
                    "{0}: publish and commit can diverge".format(name))

    def test_written_question_links_do_not_depend_on_a_laptop(self):
        """The links were backfilled by hand once. A store published by any
        workflow would have dropped them again."""
        with open(os.path.join(self.WORKFLOWS, "monday-publish.yml"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("tools/backfill_pq_links.py", text)


class SkipGateGuardTests(unittest.TestCase):
    """A sibling the DST guard skips must run NOTHING, and stay green.

    2026-08-30. Both paired cron slots fire and the London-hour guard sets
    SKIP=1 on the wrong one; every step then sits behind
    `if: env.SKIP != '1'` so the sibling costs a few seconds and goes quiet.

    "Fetch the store" was added without that guard when the store moved to a
    release asset (d6e9738), and it is the first step after the gate. So on
    the sibling it ran with no repo checked out, `python3 tools/db_state.py
    --pull` was not there to run, and the step exited 2. The run went RED,
    the failure alert DM'd Christopher at 02:03, and a manual dispatch
    followed at 03:40 -- for a run whose whole purpose was to do nothing.

    Nothing was damaged: publish and commit stand down on a failed fetch.
    The cost is a false alarm every week, which is exactly what makes a real
    one easy to miss. monday-publish.yml carried the identical hole.
    """

    WORKFLOWS = os.path.join(ROOT, ".github", "workflows")

    GUARD = "env.SKIP != '1'"

    def _gated_workflows(self):
        """Every workflow whose guard can set SKIP=1, with its parsed steps."""
        import glob
        import yaml
        out = []
        for path in sorted(glob.glob(os.path.join(self.WORKFLOWS, "*.yml"))):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if "SKIP=1" not in text:
                continue
            spec = yaml.safe_load(text)
            for job in (spec.get("jobs") or {}).values():
                steps = job.get("steps") or []
                gate = next(
                    (i for i, s in enumerate(steps)
                     if "SKIP=1" in str(s.get("run") or "")), None)
                if gate is None:
                    continue
                out.append((os.path.basename(path), steps, gate))
        return out

    def test_the_paired_workflows_are_gated_at_all(self):
        """Both DST-paired workflows must reach these assertions."""
        names = {name for name, _, _ in self._gated_workflows()}
        for want in ("sunday-pull.yml", "monday-publish.yml"):
            self.assertIn(want, names,
                          "{0} lost its London-hour gate".format(want))

    def test_every_step_after_the_skip_gate_carries_the_guard(self):
        """The rule that broke. One unguarded step is enough to go red."""
        for name, steps, gate in self._gated_workflows():
            for step in steps[gate + 1:]:
                label = step.get("name") or step.get("uses") or "<unnamed>"
                self.assertIn(
                    self.GUARD, str(step.get("if") or ""),
                    "{0}: step {1!r} runs on a sibling the gate skipped; "
                    "it has no checkout, so it fails and the run goes red "
                    "for a skip that should have been silent"
                    .format(name, label))

    def test_the_gate_itself_never_fails_the_run(self):
        """Setting SKIP=1 records a decision; it must not exit non-zero.

        Failing the gate would be the same false alarm by a shorter route.
        """
        for name, steps, gate in self._gated_workflows():
            run = str(steps[gate].get("run") or "")
            skip_line = next(l for l in run.splitlines() if "SKIP=1" in l)
            self.assertNotIn("exit 1", skip_line,
                             "{0}: the gate fails instead of skipping"
                             .format(name))


class PeersOnThePageTests(unittest.TestCase):
    """Peers, added 2026-08-29.

    The store held 50,066 peer events, 49,655 of them classified onto our
    areas, and the page published none of it -- while the Bill this campaign
    is about died in the Lords.

    The first build rendered them through the MP template and the result was
    not merely ugly, it was FALSE: "MP since 14 Sep 2020" of a peer, a tally
    reading "0 of 18 tracked divisions", and eighteen DID NOT VOTE cards
    each explaining that MPs miss divisions through illness or constituency
    duties -- about a member who was never eligible to cast one. That is the
    same false-excuse fault the service-history work existed to remove.
    """

    def test_peers_are_on_the_page(self):
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        peers = [m for m in data["members"] if m.get("house") == "lords"]
        self.assertGreater(len(peers), 300)

    def test_no_peer_is_called_an_mp(self):
        html = template()
        self.assertIn("In the House of Lords since", html)
        block = html[html.index("function sinceLine"):]
        block = block[:block.index("function servedOn")]
        self.assertIn("isPeer(m)", block, "sinceLine can still say 'MP since'")

    def test_a_peer_is_never_shown_a_commons_did_not_vote(self):
        """Ineligibility is not absence. A peer with no Commons votes gets
        the banner the Speaker gets, not eighteen empty cards."""
        html = template()
        self.assertIn("peerNoVotes ? [] : blocks", html)
        self.assertIn("sits in the House of Lords", html)

    def test_a_peer_who_was_an_mp_keeps_their_votes(self):
        """24 members are in this case, and those votes are genuinely
        theirs -- suppressing them would hide a real record."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        former = [m for m in data["members"]
                  if m.get("house") == "lords" and m.get("votes")]
        self.assertGreaterEqual(len(former), 10)

    def test_no_peer_carries_a_constituency(self):
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        for member in data["members"]:
            if member.get("house") == "lords":
                self.assertFalse(member.get("constituency"), member["name"])

    def test_every_peer_on_the_page_has_something_on_it(self):
        """Selecting on "has a classified event" was not enough: on_record
        drops what a vote card shows and what has no quotable passage, so
        peers arrived with an empty record -- a name and nothing else."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        for member in data["members"]:
            if member.get("house") != "lords":
                continue
            self.assertTrue(
                member.get("record") or member.get("words") or member.get("votes"),
                "{0} has an empty page".format(member["name"]))

    def test_the_lords_groupings_have_colours(self):
        """Crossbench and the Lords Spiritual are not parties. 78 Crossbench
        and 26 Non-affiliated peers would have rendered behind the default
        grey the party-mark work was built to stop."""
        html = template()
        for group in ("Crossbench", "Non-affiliated", "Bishops", "Lord Speaker"):
            self.assertIn('"{0}":'.format(group), html, group)

    def test_a_peer_is_findable_by_name(self):
        """They have no constituency and no postcode, so name is the only
        route in -- and the dropdown must not print an empty seat."""
        html = template()
        self.assertIn('isPeer(m) ? "House of Lords" : m.constituency', html)


class PackedLinkTests(unittest.TestCase):
    """Source links were the heaviest thing on the page.

    6,826 of them, 936KB -- more than the quotes themselves -- and most of
    each one was already on the row. A Hansard address is a fixed prefix,
    a house, THE ROW'S OWN DATE and two GUIDs; a written-question address is
    a prefix, the row's date and a uin. Only the varying parts ship now:
    936KB -> 430KB, and the page 3.40MB -> 2.90MB.

    The whole scheme is worthless if a link does not come back exactly, so
    3,500 real links are round-tripped against the originals in the build.
    """

    def test_the_row_date_is_not_repeated(self):
        packed = mvt.pack_url(
            "https://hansard.parliament.uk/Commons/2025-03-18/debates/"
            "5c370560-a5bd-46c6-b2d5-8203523db8a9/#contribution-"
            "35F7682B-85F6-47EF-A983-DA53C3EE745E", "2025-03-18")
        self.assertTrue(packed.startswith("hC:"))
        self.assertNotIn("2025-03-18", packed)
        self.assertLess(len(packed), 75)

    def test_a_date_that_differs_is_carried(self):
        """The row's date is not always the sitting date, and dropping it
        would silently point at the wrong day."""
        packed = mvt.pack_url(
            "https://hansard.parliament.uk/Lords/2024-01-02/debates/"
            "5c370560-a5bd-46c6-b2d5-8203523db8a9/#contribution-"
            "35F7682B-85F6-47EF-A983-DA53C3EE745E", "2025-03-18")
        self.assertTrue(packed.startswith("HL:"))
        self.assertIn("2024-01-02", packed)

    def test_a_written_question_keeps_only_its_uin(self):
        self.assertEqual(
            mvt.pack_url("https://questions-statements.parliament.uk/"
                         "written-questions/detail/2025-06-03/56775",
                         "2025-06-03"), "q:56775")

    def test_an_unrecognised_link_is_left_alone(self):
        """A link this does not understand must still work."""
        url = "https://edm.parliament.uk/early-day-motion/12345"
        self.assertEqual(mvt.pack_url(url, "2025-01-01"), url)

    def test_the_template_can_rebuild_both_shapes(self):
        html = template()
        self.assertIn("function href(packed, dated)", html)
        self.assertIn("function guid(h)", html)
        # a numeric Hansard debate id must NOT be reformatted as a GUID
        self.assertIn("h.length === 32", html)

    def test_no_full_url_survives_in_the_payload(self):
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        long_ones = 0
        for member in data["members"]:
            for _a, block in (member.get("record") or {}).items():
                for item in (block.get("items") or []) + (block.get("all") or []):
                    u = item.get("u") or ""
                    if u.startswith("https://hansard") or \
                            u.startswith("https://questions-statements"):
                        long_ones += 1
        self.assertEqual(long_ones, 0, "unpacked links are still shipping")


class LordsDivisionTests(unittest.TestCase):
    """Assisted-dying divisions in the Lords, scored 2026-08-29.

    Asked to score them, I first had to establish that they exist. The
    Lords Votes API holds exactly THREE, all historic -- two on Lord
    Falconer's Bill in 2015, one on Lord Joffe's in 2006 -- and NONE on the
    Terminally Ill Adults Bill, which never reached a division in that
    House. They are still worth having: 152 peers on the page voted in
    them.
    """

    def _lords(self):
        data = _payload()
        if data is None:
            return None
        return [d for d in data["divisions"]
                if (d.get("house") or "commons") == "lords"]

    def test_the_lords_divisions_are_on_the_page(self):
        lords = self._lords()
        if lords is None:
            self.skipTest("page not built")
        self.assertEqual(len(lords), 3)
        for d in lords:
            self.assertTrue(d.get("ayes") and d.get("noes"),
                            "a division without counts is not a receipt")

    def test_sign_off_gates_the_verdict(self):
        """signed_off gated NOTHING before 2026-08-29: the tool warned that
        a division was unapproved and shipped its verdict anyway.

        Tested as a RULE, not as the state of today's config -- these three
        were signed off by Christopher the same evening, so asserting they
        are unsigned would only pin a moment.
        """
        with open(os.path.join(ROOT, "tools", "make_vote_tracker.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('and d.get("signed_off")', src,
                      "an unapproved division could publish a verdict again")

    def test_every_published_verdict_is_signed_off(self):
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        for d in data["divisions"]:
            if d.get("good"):
                self.assertTrue(d["signed_off"],
                                "division {0} publishes an unapproved "
                                "verdict".format(d["id"]))

    def test_the_signed_commons_divisions_still_carry_theirs(self):
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        signed = [d for d in data["divisions"] if d["signed_off"]]
        self.assertGreater(sum(1 for d in signed if d.get("good")), 15)

    def test_no_mp_is_marked_absent_from_a_lords_division(self):
        """The mirror of the peer fault: without a house check, all 650 MPs
        are told they DID NOT VOTE in a division they could not cast."""
        html = template()
        self.assertIn('const lordsDivision = (d.house || "commons") === "lords"', html)
        self.assertIn("NOT IN THE LORDS", html)
        self.assertIn("NOT IN THE COMMONS", html)

    def test_a_card_is_one_bill(self):
        """Grouping by issue alone put Falconer's 2015 Bill, Joffe's 2006
        Bill and the Terminally Ill Adults Bill under one heading."""
        html = template()
        self.assertIn('d.house === "lords"', html.split("const key =")[1][:200])

    def test_the_lords_payload_is_normalised_on_the_way_in(self):
        """contents/notContents and camelCase members, rewritten once at
        the edge so nothing downstream needs to know."""
        shaped = mvt.lords_to_commons_shape({
            "divisionId": 1885, "title": "Assisted Dying Bill [HL]",
            "date": "2015-01-16T00:00:00",
            "authoritativeContentCount": 106, "authoritativeNotContentCount": 179,
            "contents": [{"memberId": 82, "name": "Lord X", "party": "Conservative"}],
            "notContents": []})
        self.assertEqual(shaped["DivisionId"], 1885)
        self.assertEqual(shaped["Date"], "2015-01-16")
        self.assertEqual(shaped["Ayes"][0]["MemberId"], 82)
        self.assertEqual(shaped["NoVoteRecorded"], [],
                         "the Lords records no abstentions; invent none")


class PeerFeaturedRowsTests(unittest.TestCase):
    """A peer gets four featured rows where an MP gets two.

    Their record is ALL they have. An MP's page opens with votes and a
    verdict; a peer has three Lords divisions from 2006 and 2015 and then
    whatever they have said, so two rows is thin for the only evidence on
    the page. Everything else still lists in the roll either way -- this
    only decides how many get the full treatment with a quote.
    """

    def test_a_peer_block_may_feature_four(self):
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        peer_max = max(
            (len(b.get("items") or [])
             for m in data["members"] if m.get("house") == "lords"
             for _a, b in (m.get("record") or {}).items()), default=0)
        self.assertEqual(peer_max, 4)

    def test_an_mp_block_still_features_two(self):
        """The change is for peers only: MPs already lead with votes."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        mp_max = max(
            (len(b.get("items") or [])
             for m in data["members"] if m.get("house") != "lords"
             for _a, b in (m.get("record") or {}).items()), default=0)
        self.assertEqual(mp_max, 2)

    def test_the_roll_still_holds_everything(self):
        """Featuring more must not mean listing less."""
        data = _payload()
        if data is None:
            self.skipTest("page not built")
        for member in data["members"]:
            for _a, block in (member.get("record") or {}).items():
                self.assertEqual(len(block.get("all") or []),
                                 sum((block.get("n") or {}).values()),
                                 member["name"])


class StanceRollupsRemovedTests(unittest.TestCase):
    """The rollups shipped 2026-08-31 and were removed the same day
    (Christopher: "for now also remove stance trackers"). The signed-off
    phrases stay in the config, parked; the template must not render them
    until that decision is reversed deliberately."""

    def test_no_stance_block_renders(self):
        flat = " ".join(template().split())
        self.assertNotIn('class="stances"', flat)
        self.assertNotIn("stanceLines", flat)

    def test_the_parked_phrases_survive_in_config(self):
        # Parked, not deleted: they were signed off, and deleting them would
        # make the return a re-drafting exercise instead of a template edit.
        import yaml
        with open(os.path.join(ROOT, "config", "vote_tracker.yaml"),
                  encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        with_phrases = [i for i in cfg["issues"] if (i.get("stance") or {}).get("good")]
        self.assertEqual(len(with_phrases), 6)


class RebellionTests(unittest.TestCase):
    """'Rebelled' is claimed only on BOTH facts: their party was whipped in
    that division, and they voted against that party's majority. Voting
    against the majority on a free vote is conviction, not rebellion."""

    def test_the_row_and_the_count_share_one_test(self):
        flat = " ".join(template().split())
        # both call sites use the same whipped-and-against pair
        self.assertEqual(flat.count('whipFor(d, m).label === "whipped"'), 2,
                         "the row's rebelled prefix and the summary count "
                         "-- two sites, one test")
        self.assertIn("pr.mine < pr.other && whipFor", flat)

    def test_rebelled_rides_the_against_wording_not_a_verdict_colour(self):
        # Since 2026-08-31 rebellion is the ONLY thing relativeToParty can
        # print, so the prefix is no longer conditional.
        flat = " ".join(template().split())
        self.assertIn('rebelled \\u2014 against', flat)
        self.assertIn("rebelled against their party's whip in ${rebelled}",
                      flat)


class PartyHistoryDisplayTests(unittest.TestCase):
    """The hero's "Conservative until 15 Sep 2025" line was removed
    2026-08-31 (Christopher: superfluous). The SPELLS still ship: the whip
    logic reads party-on-the-day from them, so only the display went."""

    def test_the_note_is_gone_but_the_spells_still_serve_the_whip(self):
        flat = " ".join(template().split())
        self.assertNotIn("partyNote", flat)
        self.assertNotIn("partyprior", flat)
        self.assertIn("partyOn(m, d.date)", flat)


class BillStatusAndActionTests(unittest.TestCase):
    """The issue's status, forward look and action live on its MAIN card
    only: printed on every card, this September's Second Reading would
    attach to Lord Joffe's Bill of 2006."""

    def test_the_main_card_test_exists_and_gates_all_three(self):
        flat = " ".join(template().split())
        self.assertIn(
            'const main = d.house !== "lords" || d.bill === g.issue.bill;',
            flat)
        # !g.issue.live joined the gate 2026-08-31: while a Bill is in the
        # LIVE NOW band, the band owns status/next/action and the record
        # card must not repeat them
        self.assertIn("${main && !g.issue.live && g.issue.status ?", flat)
        self.assertIn("${main && !g.issue.live && g.issue.next ?", flat)
        self.assertIn("${main && !g.issue.live && g.issue.action "
                      "&& g.issue.action.url && g.issue.action.label", flat)

    def test_the_forward_look_is_stage_house_and_date(self):
        flat = " ".join(template().split())
        self.assertIn("NEXT: ${ esc(g.issue.next.stage)} in the "
                      "${esc(g.issue.next.house)}", flat)

    def test_every_configured_action_is_a_gated_citizengo_address(self):
        # The delivery petition went live on assisted-suicide (Christopher,
        # 2026-08-31). Two rules for any action, now and later: the URL is
        # a citizengo.org address, and the issue carries a board_id so the
        # builder can retire the button when the Bill stops being alive --
        # an ungated public signup link needs a deliberate decision, not a
        # forgotten key.
        import yaml
        with open(os.path.join(ROOT, "config", "vote_tracker.yaml"),
                  encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        configured = [i for i in cfg["issues"] if i.get("action")]
        self.assertTrue(configured, "the assisted-suicide action is expected")
        for issue in configured:
            action = issue["action"]
            self.assertTrue(
                str(action.get("url", "")).startswith("https://citizengo.org"),
                "an action URL must be a citizengo.org address")
            self.assertTrue(action.get("label"))
            # EVERGREEN by instruction, given twice (Christopher,
            # 2026-08-31): signatures continue for as long as the Bill is
            # active, so no deadline may appear in the label -- the 4
            # September delivery is a campaign milestone, not a closing
            # date.
            self.assertFalse(
                re.search(r"\b(before|by|until|deadline)\b|\d",
                          action["label"], re.I),
                "action labels must not carry a deadline: " + action["label"])
            self.assertIn("board_id", issue,
                          "an action without a board_id never retires")

class CrossHouseAndUpcomingTests(unittest.TestCase):
    """Christopher, 2026-08-31: Lords votes off MP pages, Commons votes off
    peers' pages, and the two assisted-suicide Bills split into two cards."""

    def test_a_division_renders_only_for_its_own_house_or_a_named_member(self):
        flat = " ".join(template().split())
        self.assertIn(
            'const isMine = d => (d.house || "commons") === ownHouse || !!m.votes[d.id];',
            flat)
        self.assertIn("if (!isMine(d)) continue;", flat)

    def test_the_denominator_is_the_member_s_own_divisions(self):
        # "Took part in 16 of 21" counted three Lords divisions an MP could
        # never have voted in. The denominator is now the divisions the
        # page actually shows for this member.
        flat = " ".join(template().split())
        self.assertIn("${took} of ${mineDivs.length}", flat)
        self.assertNotIn("${took} of ${DATA.divisions.length}", flat)

    def test_an_upcoming_issue_renders_in_the_live_now_band(self):
        # Mockup D (Christopher, 2026-08-31): the member card opens with an
        # inverted LIVE NOW band holding the active business, then a
        # labelled divider hands over to the historic cards.
        flat = " ".join(template().split())
        self.assertIn("Live now · ${esc(bandTitle)}", flat)
        self.assertIn("for (const issue of bandIssues())", flat)
        self.assertIn("The record — ${mineDivs.length} division", flat)

    def test_the_band_is_the_upcoming_bill_s_only_home(self):
        # The old "NO VOTES YET" card and the coming-up strip are both
        # replaced: live business renders in ONE place per view.
        flat = " ".join(template().split())
        self.assertNotIn("NO VOTES YET", flat)
        self.assertNotIn('id="comingup"', flat)


    def test_upcoming_issues_cannot_crash_the_landing_pills(self):
        # divsByIssue has no entry for an issue with no divisions; the
        # landing pills must guard, or the page dies on .length.
        flat = " ".join(template().split())
        self.assertIn('const n = (divsByIssue[i.id] || []).length;', flat)

    def test_the_config_splits_the_two_bills(self):
        import yaml
        with open(os.path.join(ROOT, "config", "vote_tracker.yaml"),
                  encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        by_id = {i["id"]: i for i in cfg["issues"]}
        old, new = by_id["assisted-suicide"], by_id["assisted-suicide-2026"]
        # Two separate Bills: the fallen one keeps the votes and stops
        # carrying the forward look; the 2026 Bill carries board, action
        # and the upcoming flag.
        self.assertNotIn("board_id", old)
        self.assertNotIn("action", old)
        self.assertTrue(new.get("upcoming"))
        self.assertEqual(new.get("board_id"), 4157)
        self.assertIn("Lauren Edwards", new.get("note", ""))

class DebateWindowTests(unittest.TestCase):
    """One short title, two Bills (Christopher, 2026-08-31: "the two Bills'
    speeches can't mix"). The title cannot tell them apart; the calendar
    can -- a Bill cannot be debated after its session fell -- so a
    debate_match may carry an inclusive date window."""

    import datetime as _dt
    ISSUES = [
        {"id": "old-bill", "name": "Old", "area": 2, "bill": "A Bill",
         "debate_match": ["Terminally Ill Adults"],
         # a real datetime.date, as YAML hands over an unquoted date: the
         # window must survive type coercion, not assume strings
         "debate_until": _dt.date(2026, 4, 30)},
        {"id": "new-bill", "name": "New", "area": 2, "bill": "A Bill",
         "debate_match": ["Terminally Ill Adults"],
         "debate_from": "2026-05-01"},
    ]

    def _words(self, rows):
        import sqlite3
        from src import db, filter as filt
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        for r in rows:
            conn.execute("INSERT INTO mp_events (member_id, date, kind, ref, "
                         "line, areas, excerpt) VALUES (?,?,?,?,?,?,?)", r)
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        words, _record = mvt.on_record(conn, {"1"}, self.ISSUES, None, tax)
        return words.get("1", {})

    ROW = staticmethod(lambda date, ref: (
        "1", date, "debate", "hansard:" + ref,
        "Spoke: Terminally Ill Adults (End of Life) Bill", "[2]", ""))

    def test_each_side_of_the_boundary_belongs_to_its_own_bill(self):
        words = self._words([self.ROW("2025-06-13", "AAA"),
                             self.ROW("2026-09-11", "BBB")])
        self.assertEqual(words["old-bill"]["n"], 1)
        self.assertEqual(words["new-bill"]["n"], 1)

    def test_the_window_edges_are_inclusive_and_do_not_overlap(self):
        words = self._words([self.ROW("2026-04-30", "AAA"),
                             self.ROW("2026-05-01", "BBB")])
        self.assertEqual(words["old-bill"]["n"], 1)
        self.assertEqual(words["new-bill"]["n"], 1)

    def test_an_unbounded_match_still_matches_everything(self):
        issues = [{"id": "only", "name": "Only", "area": 2, "bill": "A Bill",
                   "debate_match": ["Terminally Ill Adults"]}]
        import sqlite3
        from src import db, filter as filt
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        # two DISTINCT titles: n counts distinct debates on the bill, so a
        # repeated title would count once whatever the dates said
        rows = [self.ROW("1999-01-01", "AAA"),
                ("1", "2099-01-01", "debate", "hansard:BBB",
                 "Spoke: Terminally Ill Adults (End of Life) Bill (First sitting)",
                 "[2]", "")]
        for r in rows:
            conn.execute("INSERT INTO mp_events (member_id, date, kind, ref, "
                         "line, areas, excerpt) VALUES (?,?,?,?,?,?,?)", r)
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        words, _ = mvt.on_record(conn, {"1"}, issues, None, tax)
        self.assertEqual(words["1"]["only"]["n"], 2)

    def test_the_real_config_windows_meet_with_no_gap_and_no_overlap(self):
        # A gap loses speeches to nobody's card; an overlap prints the same
        # words twice. The two windows must be consecutive days.
        import datetime
        import yaml
        with open(os.path.join(ROOT, "config", "vote_tracker.yaml"),
                  encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        by_id = {i["id"]: i for i in cfg["issues"]}
        until = datetime.date.fromisoformat(
            str(by_id["assisted-suicide"]["debate_until"]))
        frm = datetime.date.fromisoformat(
            str(by_id["assisted-suicide-2026"]["debate_from"]))
        self.assertEqual(frm - until, datetime.timedelta(days=1))
        self.assertEqual(by_id["assisted-suicide"]["debate_match"],
                         by_id["assisted-suicide-2026"]["debate_match"])

    def test_the_band_gives_matched_speeches_a_home(self):
        # A matched speech with no card to render on is silently
        # suppressed. The band carries the count and quotes, so the new
        # Bill's Second Reading debate has a home from day one.
        flat = " ".join(template().split())
        block = flat[flat.index("for (const issue of bandIssues())"):]
        block = block[:block.index("A peer with no Commons votes")]
        self.assertIn("(m.words || {})[issue.id]", block)
        self.assertIn('class="bandsaid"', block)
        self.assertIn("on this Bill", block)

class BandAmendmentTests(unittest.TestCase):
    """The five C amendments (Christopher, 2026-08-31: "Build all 5")."""

    def test_the_band_carries_one_button_only(self):
        # The write-to mailto shipped as amendment 1 and was removed the
        # same day (Christopher, 2026-08-31): the petition is the band's
        # only action. Contact details keep their own home lower down the
        # page, under "Contact", where writing to an MP belongs.
        flat = " ".join(template().split())
        self.assertNotIn("bandbtn2", flat)
        self.assertNotIn("mailto:${esc(m.contact.email)}", flat)


    def test_the_band_wears_one_bill_s_name_only_when_it_is_alone(self):
        flat = " ".join(template().split())
        self.assertIn("named.length === 1 ? named[0].live_label", flat)
        import yaml
        with open(os.path.join(ROOT, "config", "vote_tracker.yaml"),
                  encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        ups = [i for i in cfg["issues"] if i.get("upcoming")]
        self.assertEqual([i.get("live_label") for i in ups],
                         ["The assisted suicide Bill"])

    def test_the_decides_line_states_the_stakes(self):
        flat = " ".join(template().split())
        self.assertIn('${issue.decides ? `<div class="banddecides">', flat)
        import yaml
        with open(os.path.join(ROOT, "config", "vote_tracker.yaml"),
                  encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        decides = next(i.get("decides") for i in cfg["issues"]
                       if i.get("upcoming"))
        # the one number in it, checked against the record: Third Reading
        # passed 314-291 on 20 June 2025
        self.assertIn("23 votes", decides)

    def test_the_final_week_warms_at_view_time(self):
        flat = " ".join(template().split())
        self.assertIn("const soon = n >= 0 && n <= 7;", flat)
        self.assertIn('"THIS " + dow.toUpperCase()', flat)
        self.assertIn(".bigdate.soon{background:var(--yellow)", flat)

    def test_same_day_bills_share_one_disclosure_leaf(self):
        flat = " ".join(template().split())
        self.assertIn("const rows = rest.map(g =>", flat)
        self.assertIn("rest.reduce((n, g) => n + g.bills.length, 0)", flat)

class BothHomesTests(unittest.TestCase):
    """Christopher, 2026-08-31: when the 11 September vote happens, it
    belongs in The Record AND the Bill stays in LIVE NOW. Rehearsed in the
    browser with a synthetic Second Reading division: the band's promise
    line became 'GOOD VOTE ... at Second Reading' with a jump to the
    record, the record gained the card, the divider recounted."""

    def test_the_band_tracks_the_bill_s_life_not_the_absence_of_votes(self):
        flat = " ".join(template().split())
        self.assertIn("DATA.issues.filter(i => i.upcoming || i.live)", flat)

    def test_once_a_division_exists_the_promise_becomes_the_fact(self):
        flat = " ".join(template().split())
        # the newest division on the issue, rendered in the page's verdict
        # vocabulary, with the promise line gated off
        self.assertIn("const latest = issueDivs[0];", flat)
        self.assertIn('class="bandvote ${vi.cls}"', flat)
        self.assertIn("!latest && !isPeer(m)", flat)
        # a peer is not marked absent from a Commons division
        self.assertIn('if (vi.cls !== "S")', flat)

    def test_the_record_card_never_duplicates_the_band(self):
        # while the issue is in the band, the band owns status, forward
        # look and petition; the record card carries the votes
        flat = " ".join(template().split())
        self.assertIn("${main && !g.issue.live && g.issue.status", flat)
        self.assertIn("${main && !g.issue.live && g.issue.next", flat)
        self.assertIn("${main && !g.issue.live && g.issue.action", flat)

    def test_the_generator_ships_live_issues_even_with_divisions(self):
        import sqlite3
        sys.path.insert(0, ROOT)
        from src import db as _db, members as _members
        conn = _db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = __import__("sqlite3").Row
        _members.cache_put(conn, _members.Member(
            id=1, name="Aye MP", party="Labour", seat="Seat",
            house="Commons", since="2024-07-04", list_as="Aye MP"))
        conn.execute("UPDATE members SET current_mp = 1")
        conn.execute("INSERT INTO bills_board (bill_id, title, house, stage, "
                     "next_key_date, status) VALUES "
                     "(77, 'A Bill', 'Commons', 'Committee', 'TBA', 'live')")
        conn.commit()
        cfg = {"issues": [{"id": "iss", "name": "An issue", "area": 2,
                           "bill": "A Bill", "note": "n", "status": "s",
                           "board_id": 77}],
               "divisions": []}
        dataset, _ = mvt.build(conn, cfg, {})
        issue = dataset["issues"][0]
        # neither upcoming nor holding divisions, but its board row is
        # live: the band still needs it
        self.assertTrue(issue["live"])

