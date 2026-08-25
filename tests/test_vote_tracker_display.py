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


if __name__ == "__main__":
    unittest.main()


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
    """'Also on the record' is RECEIPTS ONLY (Christopher, 2026-08-25):
    dated facts in the member's own words with a source. The inference
    layer -- stance scores, placements, characterisations -- is campaign
    intelligence and must never reach this public payload."""

    def _store(self):
        import sqlite3
        sys.path.insert(0, ROOT)
        from src import db
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        rows = [
            ("1", "2025-03-19", "debate", "hansard:AAA",
             "Spoke: TIA Bill (Twenty-seventh sitting) (re: assisted dying)",
             "[2]", "Some Members suggested that institutions receiving public funding should deliver the service."),
            ("1", "2025-03-19", "debate", "hansard:BBB",
             "Spoke: TIA Bill (Twenty-seventh sitting) (re: assisted dying)",
             "[2]", "A second contribution in the same sitting."),
            ("1", "2025-01-01", "debate", "hansard:CCC",
             "Spoke: Some Debate (re: term)", "[2]", "Some Debate"),
            ("1", "2024-01-01", "edm-signed", "edm:603",
             "Signed EDM: Amnesty report", "[2]", ""),
            ("2", "2025-01-01", "debate", "hansard:DDD",
             "Spoke: Another (re: t)", "[2]", "Not a sitting member."),
        ]
        for r in rows:
            conn.execute("INSERT INTO mp_events (member_id, date, kind, ref, "
                         "line, areas, excerpt) VALUES (?,?,?,?,?,?,?)", r)
        # a stance row exists but must never surface
        from src import stance as _st
        _st.ensure_table(conn)
        conn.execute("INSERT INTO stance (ref, stance, why, scored_at) "
                     "VALUES ('hansard:AAA', 2, 'ally', '2025-01-01')")
        return conn

    def test_receipts_carry_no_stance(self):
        rec = mvt.on_record(self._store(), {"1"})
        import json
        flat = json.dumps(rec)
        self.assertNotIn("stance", flat)
        # the real guard is the key whitelist below: '2' appears legitimately
        # as an AREA key, so a naive scan for score-like values false-alarms
        for items in rec["1"].values():
            for it in items:
                self.assertEqual(sorted(it.keys() - {"e"}),
                                 ["d", "k", "q", "t"],
                                 "only date, kind, quote, title (and an EDM "
                                 "id) may ship")

    def test_internal_dressing_is_stripped(self):
        rec = mvt.on_record(self._store(), {"1"})
        titles = [it["t"] for it in rec["1"]["2"]]
        for t in titles:
            self.assertNotIn("Spoke:", t)
            self.assertNotIn("(re:", t)

    def test_one_receipt_per_debate(self):
        """Five contributions in one committee sitting are one receipt."""
        rec = mvt.on_record(self._store(), {"1"})
        titles = [it["t"] for it in rec["1"]["2"]]
        self.assertEqual(len(titles), len(set(titles)))

    def test_a_heading_is_not_a_quote(self):
        rec = mvt.on_record(self._store(), {"1"})
        some_debate = next(it for it in rec["1"]["2"]
                           if it["t"] == "Some Debate")
        self.assertEqual(some_debate["q"], "",
                         "an excerpt that merely repeats the title must not "
                         "render in quotation marks as the member's words")

    def test_non_sitting_members_are_excluded(self):
        rec = mvt.on_record(self._store(), {"1"})
        self.assertNotIn("2", rec)

    def test_the_section_declares_itself_factual(self):
        t = template()
        self.assertIn("Also on the record", t)
        self.assertIn("a speech is not a vote", t)
