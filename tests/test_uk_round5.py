"""UK countdown round 5 (Chris's decisions, 16 October 2026). Fixtures only.

1. "Latest votes on our issues" leaves the edition, with the division
   lines it had absorbed (tests/test_digest.py pins the section order).
2. The petitions noise list (config/uk-petitions-noise.yaml).
3. CARE (the charity) is not the CARE pension scheme (entity_vetoes).
4. Regulators carry their own Where tag, never UK GOVT; deadline wording
   follows the item (call for evidence / consultation / committee evidence).
"""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import countdown as cd, db, digest, filter as filt  # noqa: E402
from src.uk_petition_noise import PetitionNoise, RuleError  # noqa: E402

WEEK = "2026-10-19"


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class LatestVotesRemoved(unittest.TestCase):
    def test_no_votes_section_at_all(self):
        e = digest.Edition(week_commencing="2026-08-31", number=5, mode="normal")
        e.votes = [digest.Line("A division on our ground", 2, url="https://votes.parliament.uk/x")]
        e.latest_votes = [{"date": "2026-06-01", "where": "Senedd", "title": "An old vote", "result": "Agreed"}]
        md = digest.render(e)
        self.assertNotIn("Latest votes on our issues", md)
        self.assertNotIn("An old vote", md)
        self.assertNotIn("A division on our ground", md)


class PetitionNoiseFile(unittest.TestCase):
    """The shipped rules, on the petitions they were measured against."""

    @classmethod
    def setUpClass(cls):
        cls.n = PetitionNoise()

    def judge(self, pid, title, areas, terms):
        return self.n.judge(pid, title, areas, terms)[0]

    def test_measured_false_positives_are_muted(self):
        cases = [
            (764510, "Hold a public inquiry to review the use of dopamine agonists", [9], ["family breakdown"]),
            (766482, "Require tracking of companion animal euthanasia to prevent unnecessary deaths", [2],
             ["euthanasia"]),
            (767158, "Ban euthanasia of healthy pets, create register of owners who have attempted it", [2],
             ["euthanasia"]),
            (758639, "Amend Dangerous Dogs Act to recognise and fund rehoming of non-dangerous dogs", [2],
             ["euthanasia"]),
            (768606, "Fund annual cancer screening at 40 for adults with Down syndrome & LD", [1], ["Down syndrome"]),
            (754013, "Fund more British Sign Language (BSL) interpreters in the emergency services", [5],
             ["Equality Act 2010"]),
            (771042, "Require warnings for social media content about open water swimming", [6, 7],
             ["social media", "Online Safety Act"]),
        ]
        for pid, title, areas, terms in cases:
            self.assertEqual(self.judge(pid, title, areas, terms), [], title)

    def test_only_the_wrong_area_goes(self):
        self.assertEqual(self.judge(760849, "Make reproductive coercion a standalone criminal offence", [1, 2],
                                    ["abortion", "contracepti*", "coercion"]), [1])

    def test_the_real_thing_stays(self):
        keep = [
            (770527, "Disapprove the draft Equality Act 2010 guidance laid on 21 May 2026", [5], ["Equality Act 2010"]),
            (757242, "Ban abortions after 24 weeks due to Down's syndrome diagnosis", [1],
             ["abortion", "Down's syndrome"]),
            (777578, "Legalise assisted dying for terminally ill adults", [2], ["assisted dying", "coercion"]),
            (759505, "Give kinship carers equal financial & legal support to foster carers", [6, 9],
             ["foster care", "family breakdown"]),
            (999999, "Ban euthanasia", [2], ["euthanasia"]),
        ]
        for pid, title, areas, terms in keep:
            self.assertEqual(self.judge(pid, title, areas, terms), areas, title)

    def test_a_watched_petition_is_never_muted(self):
        # Names a watchlist Bill: protected even though its id is listed.
        n = PetitionNoise()
        n.exclude_ids["123"] = "test"
        self.assertEqual(n.judge(123, "x", [2], ["Terminally Ill Adults (End of Life) Bill"])[0], [2])

    def test_a_rule_without_a_reason_is_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "n.yaml"), "w") as fh:
                fh.write("exclude_in_area:\n  2:\n    - only_terms: [euthanasia]\n")
            with self.assertRaises(RuleError):
                PetitionNoise(config_dir=d, noise_file="n.yaml")

    def test_edition_applies_the_list(self):
        conn = store()
        conn.executemany(
            "INSERT INTO uk_petitions (petition_id, title, state, signatures, threshold_reached, areas, "
            "matched_terms, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,'x','x')",
            [(764510, "Hold a public inquiry to review the use of dopamine agonists", "open", 10872, "10k", "[9]",
              '["family breakdown"]'),
             (777000, "Ban puberty blockers for good", "open", 20000, "10k", "[3]", '["puberty blocker*"]')])
        rows, note = cd.petitions_from_store(conn, WEEK)
        self.assertIsNone(note)
        self.assertEqual([p["id"] for p in rows], ["777000"])


class CareIsNotAPension(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        cls.wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    def hits(self, *text):
        return filt.filter_item(self.tax, self.wl, *text).watchlist_hits

    def test_pension_scheme_care_is_vetoed(self):
        self.assertEqual(self.hits("Police Pension Scheme 2015: CPI revaluation", "the CARE scheme"), [])
        self.assertEqual(self.hits("lower pensionable pay from connected CARE scheme service"), [])

    def test_the_charity_still_matches(self):
        self.assertIn("CARE", self.hits("CARE briefing on the assisted suicide Bill"))
        self.assertIn("CARE", self.hits("the Secretary of State for Work and Pensions and his links to CARE"))


class RegulatorsAndWording(unittest.TestCase):
    def test_regulator_tags(self):
        self.assertEqual(cd.regulator_tag("Ofcom"), "OFCOM")
        self.assertEqual(cd.regulator_tag("NHS England"), "NHS ENGLAND")
        self.assertEqual(cd.regulator_tag("Equality and Human Rights Commission"), "EHRC")
        self.assertEqual(cd.regulator_tag("Human Fertilisation and Embryology Authority"), "HFEA")
        self.assertIsNone(cd.regulator_tag("Department for Education"))
        self.assertEqual(cd.regulator_tag("Some Authority", regulator=True), cd.REGULATOR)
        for tag in ("OFCOM", "NHS ENGLAND", "EHRC", "HFEA", "REGULATOR"):
            self.assertIn(tag, cd.TAGS)

    def test_wording_follows_the_item(self):
        self.assertEqual(cd.deadline_detail("Call for Evidence: A Safer Life Online for Women and Girls"),
                         "call for evidence closes")
        self.assertEqual(cd.deadline_detail("x", "open_call_for_evidence"), "call for evidence closes")
        self.assertEqual(cd.deadline_detail("Call for input: age assurance"), "call for input closes")
        self.assertEqual(cd.deadline_detail("RSHE guidance consultation"), "consultation closes")
        self.assertEqual(cd.deadline_detail("Work-based immigration", committee=True), "evidence closes")

    def test_ofcom_row_is_ofcom_not_uk_govt(self):
        conn = store()
        conn.executemany(
            "INSERT INTO govuk_docs (base_path, title, doc_type, organisation, closing_date, url, areas, "
            "matched_terms, first_seen, last_seen, source) VALUES (?,?,?,?,?,?,?,?,'x','x',?)",
            [("https://www.ofcom.org.uk/x", "Call for Evidence: A Safer Life Online for Women and Girls",
              "consultation", "Ofcom", "2026-11-04", "https://www.ofcom.org.uk/x", "[7]", '["online safety"]', "ofcom"),
             ("/government/consultations/rshe", "RSHE guidance consultation", "open_consultation",
              "Department for Education", "2026-11-20", None, "[6]", '["RSE"]', "govuk")])
        rows, _pubs, _note = cd.govuk_from_store(conn, WEEK)
        got = {(r.where, r.detail) for r in rows}
        self.assertEqual(got, {("OFCOM", "call for evidence closes"), ("UK GOVT", "consultation closes")})
        post = cd.short_title(next(r for r in rows if r.where == "OFCOM"))
        self.assertTrue(post.endswith(", call for evidence closes"), post)

    def test_regulator_consultation_from_the_weekly_feed(self):
        row = cd.from_deadline({"type": "Consultation", "title": "NICE guideline on gender", "url": "u",
                                "deadline": "2026-11-01", "regulator": "NICE"})
        self.assertEqual((row.where, row.detail), ("NICE", "consultation closes"))
        row = cd.from_deadline({"type": "Evidence", "title": "Inquiry", "url": "v", "deadline": "2026-11-01",
                                "committee": "Women and Equalities Committee"})
        self.assertEqual((row.where, row.detail), ("DEADLINE", "evidence closes"))

    def test_merge_takes_the_regulator_tag(self):
        existing = [cd.from_deadline({"type": "Consultation", "title": "Ofcom call", "url": "https://o/1",
                                      "deadline": "2026-11-04"})]
        g = cd.Row(date="2026-11-04", where="OFCOM", title="Ofcom call", url="https://o/1",
                   detail="consultation closes", kind="consultation")
        merged = cd.merge_consultations(existing, [g])
        self.assertEqual([r.where for r in merged], ["OFCOM"])


if __name__ == "__main__":
    unittest.main()
