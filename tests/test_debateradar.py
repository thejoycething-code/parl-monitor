"""The debate radar (Christopher, 2026-09-09): find the day's debates on our issues.

The measurement that shaped it: on 2026-09-07 Hansard's search returned 25 surrogacy
contributions from 14 members, and the ledger held 2, because the spoken sweep runs
weekly over the week just ended. A radar reading the ledger would have missed the
surrogacy debate on the day it happened.
"""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import debateradar as radar, filter as filt  # noqa: E402

DAY = datetime.date(2026, 9, 7)


def contribution(ext, member, title, text, debate_ext="D1", house="Commons"):
    return {"ContributionExtId": ext, "MemberId": member, "SittingDate": DAY.isoformat() + "T00:00:00",
            "House": house, "DebateSection": title, "DebateSectionExtId": debate_ext,
            "ContributionText": text}


class FakeClient(object):
    """Answers the contributions search from a fixed table keyed by search term."""

    def __init__(self, by_term):
        self.by_term = by_term
        self.calls = []

    def get_json(self, url, feed, slug, **kw):
        import re
        term = re.search(r"searchTerm=([^&]+)", url).group(1).replace("+", " ").replace("%20", " ")
        self.calls.append(term)
        return {"Results": self.by_term.get(term, [])}


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        # the real watchlist: filter.match_passages scans it, so None is not an option
        self.wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    def _run(self, by_term, terms):
        return radar.candidates(FakeClient(by_term), DAY, terms, self.tax, self.wl)

    def test_a_real_debate_qualifies_on_members(self):
        text = ("I cannot support the change proposed by the petition. The question is whether the woman who has "
                "carried and given birth to a child should lose her legal status as that child's mother. "
                "A parental order in a surrogacy arrangement cannot begin until six weeks after the birth.")
        rows = [contribution("c%d" % i, 5000 + i, "Surrogacy Law and Legal Parenthood", text) for i in range(4)]
        cands, gaps = self._run({"surrogacy": rows}, ["surrogacy"])
        self.assertEqual(len(cands), 1)
        c = cands[0]
        self.assertEqual((len(c.members), len(c.contributions)), (4, 4))
        self.assertIn(10, c.areas)
        self.assertTrue(c.worth_a_pack())
        self.assertEqual(c.strength, "strong")          # the title itself matches
        self.assertIn("Surrogacy", c.title)
        self.assertEqual(gaps, [])

    def test_one_member_intervening_many_times_is_not_our_debate(self):
        """The EU Membership Referendum false positive of 2026-09-02 looked busy
        because ONE member kept intervening. Members, not contributions."""
        text = "Surrogacy arrangements abroad raise questions about a surrogate mother's consent."
        rows = [contribution("c%d" % i, 4321, "Some Other Bill", text, debate_ext="D9") for i in range(8)]
        cands, _ = self._run({"surrogacy": rows}, ["surrogacy"])
        self.assertEqual(len(cands[0].contributions), 8)
        self.assertEqual(len(cands[0].members), 1)
        self.assertFalse(cands[0].worth_a_pack())
        self.assertEqual(cands[0].strength, "thin")

    def test_a_migration_only_debate_never_earns_a_pack(self):
        """Area 11 is collated and never campaigned: a busy small-boats debate must
        not produce reels and a canvas."""
        text = "The small boats crossing the channel and illegal migration must be stopped at the border."
        rows = [contribution("m%d" % i, 6000 + i, "Dover and Portsmouth: Protests", text, debate_ext="D2") for i in range(6)]
        cands, _ = self._run({"illegal migration": rows}, ["illegal migration"])
        c = cands[0]
        self.assertEqual(len(c.members), 6)
        self.assertTrue(c.hidden_only, c.areas)
        self.assertEqual(c.displayable_areas, [])
        self.assertFalse(c.worth_a_pack())
        self.assertEqual(c.strength, "thin")

    def test_a_debate_touching_migration_and_a_campaign_area_does_qualify(self):
        text = ("Free speech at these protests matters, and so does illegal migration policy; "
                "freedom of speech cannot be set aside because a crowd is unpopular.")
        rows = [contribution("x%d" % i, 7000 + i, "Protests and Free Speech", text, debate_ext="D3") for i in range(4)]
        cands, _ = self._run({"free speech": rows}, ["free speech"])
        c = cands[0]
        self.assertFalse(c.hidden_only)
        self.assertIn(7, c.areas)
        self.assertTrue(c.worth_a_pack())

    def test_a_passing_mention_is_gated_out_by_the_taxonomy(self):
        rows = [contribution("h%d" % i, 8000 + i, "Housing Supply", "We must build more homes for families.", debate_ext="D4")
                for i in range(5)]
        cands, _ = self._run({"surrogacy": rows}, ["surrogacy"])
        self.assertEqual(cands, [])

    def test_the_same_debate_found_by_two_terms_is_one_candidate(self):
        a = contribution("c1", 100, "Assisted Dying and Palliative Care",
                         "Assisted dying would change the relationship between doctor and patient for ever.")
        b = contribution("c2", 101, "Assisted Dying and Palliative Care",
                         "Palliative care funding must come before any assisted suicide law.")
        cands, _ = self._run({"assisted dying": [a], "palliative care": [b]}, ["assisted dying", "palliative care"])
        self.assertEqual(len(cands), 1)
        self.assertEqual(len(cands[0].members), 2)
        self.assertGreaterEqual(len(cands[0].terms), 1)

    def test_report_names_what_it_dropped_and_why(self):
        text = "The small boats and illegal migration at the border."
        rows = [contribution("m%d" % i, 9000 + i, "Border Security", text, debate_ext="D5") for i in range(6)]
        cands, _ = self._run({"illegal migration": rows}, ["illegal migration"])
        out = radar.report(cands, gaps=[], date=DAY)
        self.assertIn("Seen and not proposed", out)
        self.assertIn("migration only", out)
        self.assertIn("Nothing cleared", out)          # nothing qualified, and it says so

    def test_a_failing_term_is_a_gap_not_a_silent_loss(self):
        from src.http import FetchError

        class Broken(FakeClient):
            def get_json(self, url, feed, slug, **kw):
                raise FetchError(url, feed, slug, 1, "HTTP Error 500")
        cands, gaps = radar.candidates(Broken({}), DAY, ["surrogacy"], self.tax, self.wl)
        self.assertEqual(cands, [])
        self.assertEqual(len(gaps), 1)
        self.assertIn("Gaps", radar.report(cands, gaps, DAY))


if __name__ == "__main__":
    unittest.main()
