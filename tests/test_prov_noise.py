"""The provinces noise filter (src/prov_noise.py, config/prov-noise.yaml) and
its use in the edition (tools/prov_monitor.py). No network, no model."""

import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import noise, prov_noise  # noqa: E402
import test_prov_monitor as tpm  # noqa: E402

RULES = """exclude_titles: []
exclude_in_area:
  1:
    - only_terms: ['Down syndrome']
      except_title: 'harvey'
      reason: 'day acts are not abortion'
  2:
    - only_terms: [euthanasia]
      title: 'animal'
      kinds: [bill]
      reason: 'animal euthanasia'
  8:
    - title: '^appropriation act'
      reason: 'a ministry name'
"""


def judge(nz, kind, heading, areas, terms, key="ns-65-1/57", bills=()):
    return nz.judge(kind, key, heading, areas, terms, bills)


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(self.tmp.name, "prov-noise.yaml"), "w", encoding="utf-8") as fh:
            fh.write(RULES)
        noise._FILES.clear()
        self.nz = prov_noise.ProvNoise(self.tmp.name)

    def tearDown(self):
        noise._FILES.clear()
        self.tmp.cleanup()

    def test_an_awareness_day_act_loses_abortion_and_is_muted(self):
        shown, muted = judge(self.nz, "bill", "Down Syndrome Day Act", [1], ["Down syndrome"])
        self.assertEqual(shown, [])
        self.assertEqual(muted, {1: "day acts are not abortion"})

    def test_except_title_keeps_harveys_law(self):
        self.assertEqual(judge(self.nz, "bill", "Harvey's Law", [1], ["Down syndrome"]), ([1], {}))

    def test_only_terms_needs_every_term_in_the_area(self):
        # 'abortion' is placed in area 1 by the taxonomy: the rule does not apply
        shown, muted = judge(self.nz, "bill", "Down Syndrome Day Act", [1], ["Down syndrome", "abortion"])
        self.assertEqual((shown, muted), ([1], {}))

    def test_a_term_the_taxonomies_do_not_place_keeps_the_area(self):
        shown, _ = judge(self.nz, "bill", "Down Syndrome Day Act", [1],
                         ["Down syndrome", "some watchlist phrase"])
        self.assertEqual(shown, [1])

    def test_one_area_muted_the_others_stay(self):
        shown, muted = judge(self.nz, "bill", "Animal Protection Act", [2, 13],
                             ["euthanasia", "organ donation*"])
        self.assertEqual(shown, [13])
        self.assertEqual(list(muted), [2])

    def test_kinds_limit_a_rule(self):
        shown, _ = judge(self.nz, "speech", "Animal Protection Act", [2], ["euthanasia"])
        self.assertEqual(shown, [2])

    def test_title_rule_folds_case_and_accents(self):
        shown, _ = judge(self.nz, "bill", "APPROPRIATION ACT No. 2 Loi n° 2 sur les crédits", [8], ["laïcité"])
        self.assertEqual(shown, [])

    def test_migration_alone_is_not_muted_it_was_never_shown(self):
        self.assertEqual(judge(self.nz, "bill", "Down Syndrome Day Act", [11], ["citizenship"]), ([], {}))

    def test_a_watched_item_is_never_muted(self):
        shown, muted = judge(self.nz, "bill", "Down Syndrome Day Act", [1], ["Down syndrome", "ns-65-1/57"])
        self.assertEqual((shown, muted), ([1], {}))

    def test_a_signed_reading_protects_the_division_and_its_bill(self):
        nz = prov_noise.ProvNoise(self.tmp.name, signed=({"ns-65-1-2026-04-01-1"}, {"ns-65-1/57"}))
        self.assertEqual(nz.judge("division", "ns-65-1-2026-04-01-1", "Down Syndrome Day Act", [1],
                                  ["Down syndrome"]), ([1], {}))
        self.assertEqual(nz.judge("bill", "ns-65-1/57", "Down Syndrome Day Act", [1],
                                  ["Down syndrome"]), ([1], {}))
        # a speech on the signed bill, and an unsigned division on it
        self.assertEqual(nz.judge("speech", "x-1", "Down Syndrome Day Act", [1], ["Down syndrome"],
                                  ["ns-65-1/57"])[0], [1])
        self.assertEqual(nz.judge("division", "ns-65-1-2026-04-02-1", "Down Syndrome Day Act", [1],
                                  ["Down syndrome"], ["ns-65-1/57"])[0], [1])

    def test_exclude_titles_drops_the_whole_item(self):
        path = os.path.join(self.tmp.name, "prov-noise.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("exclude_titles: ['^pension']\n")
        noise._FILES.clear()
        nz = prov_noise.ProvNoise(self.tmp.name)
        self.assertEqual(nz.judge("bill", "k", "Pension Plans Act", [7, 9], ["free speech"])[0], [])

    def test_a_rule_without_a_reason_or_a_pattern_is_refused(self):
        for bad in ("exclude_in_area:\n  1:\n    - title: 'x'\n",
                    "exclude_in_area:\n  1:\n    - reason: 'why'\n",
                    "exclude_in_area:\n  one:\n    - title: 'x'\n      reason: 'why'\n",
                    "exclude_in_area:\n  1:\n    - title: 'x'\n      kinds: [vote]\n      reason: 'why'\n"):
            with open(os.path.join(self.tmp.name, "prov-noise.yaml"), "w", encoding="utf-8") as fh:
                fh.write(bad)
            noise._FILES.clear()
            with self.assertRaises(prov_noise.RuleError, msg=bad):
                prov_noise.ProvNoise(self.tmp.name)

    def test_no_file_mutes_nothing(self):
        noise._FILES.clear()
        nz = prov_noise.ProvNoise(os.path.join(self.tmp.name, "absent"))
        self.assertEqual(nz.judge("bill", "k", "Down Syndrome Day Act", [1], ["Down syndrome"]), ([1], {}))


class TheRealFileTests(unittest.TestCase):
    """Measured cases from the store, 9 October 2026 (config/prov-noise.yaml)."""

    @classmethod
    def setUpClass(cls):
        noise._FILES.clear()
        cls.nz = prov_noise.ProvNoise()

    def shown(self, kind, heading, areas, terms):
        return self.nz.judge(kind, "k", heading, areas, terms)[0]

    def test_noise(self):
        for heading, areas, terms in (
                ("Ontario Down Syndrome Day Act, 2016", [1], ["Down syndrome"]),
                ("Standards of Care for Breeders of Companion Animals Act", [2], ["euthanasia"]),
                ("Misuse of Non-disclosure Agreements Act", [2, 5], ["coercion", "gender expression",
                                                                   "gender-based violence"]),
                ("Estate Administration Act", [10], ["surrogate"]),
                ("Safe Night Out Act, 2023", [5], ["gender expression"]),
                ("Appropriation Act No. 1, 2026-2027", [8], ["laïcité"]),
                ("Burden Reduction Act, 2016", [7], ["Article 7"])):
            self.assertEqual(self.shown("bill", heading, areas, terms), [], heading)
        self.assertEqual(self.shown("speech", "Matter of Privilege", [7], ["freedom of speech"]), [])

    def test_not_noise(self):
        for heading, areas, terms in (
                ("Harvey's Law", [1], ["Down syndrome"]),
                ("Medical Assistance in Dying", [2], ["euthanasia"]),
                ("The Employment Standards Code Amendment Act (Attachment Leave for Adoption and "
                 "Surrogacy)", [10], ["surrogacy", "surrogate"]),
                ("The Family Maintenance Amendment Act", [10], ["surrogate"]),
                ("Toby's Act (Right to be Free from Discrimination and Harassment Because of Gender "
                 "Identity or Gender Expression), 2012", [5], ["gender expression"]),
                ("Protection of Public Participation Act, 2015", [7], ["freedom of speech"])):
            self.assertEqual(self.shown("bill", heading, areas, terms), areas, heading)


class EditionTests(unittest.TestCase):
    """A muted item leaves the edition and is counted; the store keeps it."""

    def setUp(self):
        self.base = tpm.EditionTests("test_an_active_province_gets_its_section_and_the_quiet_ones_one_line")
        self.base.setUp()
        self.conn = self.base.conn
        tpm.bill(self.conn, "ns-65-1/57", "Down Syndrome Day Act", [1],
                 stages=[{"stage": "First Reading", "date": "2026-10-08"}])
        self.conn.execute("UPDATE prov_bills SET matched_terms = ? WHERE bill_key = ?",
                          ('["Down syndrome"]', "ns-65-1/57"))
        tpm.bill(self.conn, "ns-65-1/56", "Harvey's Law", [1],
                 stages=[{"stage": "First Reading", "date": "2026-10-08"}])
        self.conn.execute("UPDATE prov_bills SET matched_terms = ? WHERE bill_key = ?",
                          ('["Down syndrome"]', "ns-65-1/56"))
        self.conn.commit()
        noise._FILES.clear()

    def tearDown(self):
        self.base.tearDown()

    def render(self, **kw):
        return tpm.pm.render_edition(self.conn, tpm.TODAY, tpm.SINCE, stance_path=self.base.stance,
                                     sheet_dir=self.base.sheets, **kw)

    def test_the_day_act_is_muted_and_counted_harveys_law_stays(self):
        text = self.render()
        self.assertNotIn("Down Syndrome Day Act", text)
        self.assertIn("Harvey's Law", text)
        self.assertIn("1 item(s) on our ground muted from this edition (Nova Scotia 1 bill)", text)
        self.assertEqual(self.conn.execute("SELECT areas FROM prov_bills WHERE bill_key='ns-65-1/57'")
                         .fetchone()[0], "[1]")

    def test_without_the_filter_it_shows(self):
        text = self.render(mute=False)
        self.assertIn("Down Syndrome Day Act", text)
        self.assertIn("Noise filter:** off", text)

    def test_a_signed_bill_reading_keeps_it(self):
        stance = open(self.base.stance, encoding="utf-8").read().replace(
            "bills: []", "bills:\n  - key: ns-65-1/57\n    sponsored: 1\n")
        with open(self.base.stance, "w", encoding="utf-8") as fh:
            fh.write(stance)
        self.assertIn("Down Syndrome Day Act", self.render())

    def test_nothing_muted_says_so(self):
        self.conn.execute("DELETE FROM prov_bills WHERE bill_key='ns-65-1/57'")
        self.assertIn("nothing muted this week", self.render())


if __name__ == "__main__":
    unittest.main()
