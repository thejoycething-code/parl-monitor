"""The public MP votes page (Christopher's decisions, 2026-08-24).

Four changes land together: verdicts go public, the whip is stated on every
vote and can differ BY PARTY, a division we decline to score is demoted with
its reason attached, and cards are grouped by bill in date order.
"""

import os
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
        self.assertEqual(mvt.whip_label({}, "", split), "whipped")


class TemplateTests(unittest.TestCase):
    def test_the_whip_is_shown_on_every_vote_not_only_whipped_ones(self):
        """A badge that appears only when something is wrong teaches readers
        to ignore its absence."""
        t = template()
        self.assertIn("FREE VOTE", t)
        self.assertIn("WHIP NOT RECORDED", t)
        self.assertIn("whipChip(d, m)", t)

    def test_the_whip_chip_is_inside_the_vote_block(self):
        t = template()
        self.assertIn("vwhip", t)
        block = t[t.index("const voteBlock"):t.index("const bigCard")]
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
