"""Campaign targets and outcomes for the new countries (src/country_campaign.py,
tools/country_campaign.py). The Polish fixture store of test_country_5ca; the
confirmations are made in a temporary config only. No network, no Slack."""

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import country_campaign as camp  # noqa: E402
from tests import test_country_5ca as fx  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tool = _load("country_campaign")
QUIET = fx.QUIET
TODAY = "2026-10-10"

TSV = """# test export
program\tbound\tlooker_topic\tstart_date\tsignatures\tnew_members\totd_eur\tmd_eur\tsent_emails
PL-2026-03-01-Local-NA-ABC-17001-Tell_Anna_Adamska_protect_the_family\tLocal\t\t2026-03-02\t12000\t800\t950.50\t10\t200000
PL-2026-04-01-Local-NA-ABC-17002-Stop_cohabitation_contracts\tLocal\t\t2026-04-02\t8000\t300\t400\t5\t150000
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.cfg, self.camps = os.path.join(t, "config"), os.path.join(t, "campaigns")
        self.looker, self.out = os.path.join(t, "looker"), os.path.join(t, "5ca")
        os.makedirs(self.cfg)
        with open(os.path.join(self.cfg, "pl_stance.yaml"), "w", encoding="utf-8") as h:
            h.write(fx.PL_STANCE)
        self.db = os.path.join(t, "store.db")
        self.conn = fx.pl_store_at(self.db)
        c5.draft(self.conn, "pl", self.cfg, TODAY, QUIET, wl=fx.PL_WL)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def open(self, slug="pl-family", **kw):
        return camp.open_campaign(self.conn, "pl", 9, slug, config_dir=self.cfg,
                                  base=self.camps, today=TODAY, **kw)

    def confirm_soft(self):
        """Scratch sign-off: the final vote on 10/2110 at -1/+1, so the
        members land at + and -; confirmed by Chris in the temp config."""
        path = c5.stance_path("pl", self.cfg)
        with open(path, encoding="utf-8") as h:
            text = h.read()
        start = text.index('- key: "pl-10-1-1"')
        end = text.index("- key:", start + 5)
        block = text[start:end].replace("yea: -2", "yea: -1").replace("nay: 2", "nay: 1")
        with open(path, "w", encoding="utf-8") as h:
            h.write(text[:start] + block + text[end:])
        c5.confirm("pl", ["pl-10-1-1"], "Christopher", TODAY, self.cfg, log=QUIET)

    def run_tool(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = tool.main(list(argv) + ["--db", self.db, "--config-dir", self.cfg,
                                         "--campaign-dir", self.camps, "--looker-dir", self.looker,
                                         "--out-dir", self.out, "--today", TODAY])
        return rc, buf.getvalue()


class BeforeSignOff(Base):
    def test_open_holds_everyone_at_zero_and_says_so(self):
        c = self.open()
        self.assertEqual(c["state"], camp.AWAITING)
        self.assertEqual({r["column"] for r in c["snapshot"]}, {"0"})
        self.assertEqual(c["chamber"], "sejm")
        self.assertEqual(len(c["snapshot"]), 3)
        self.assertTrue(os.path.exists(camp.campaign_path("pl", "pl-family", self.camps)))

    def test_no_target_is_suggested_and_candidates_are_labelled(self):
        self.open()
        rows, ready = camp.placements(self.conn, "pl", "sejm", 9, self.cfg)
        self.assertEqual(ready["placing"], 0)
        self.assertEqual(camp.suggested_targets(rows), [])
        cands, pending = camp.candidates(self.conn, "pl", "sejm", 9, self.cfg)
        self.assertEqual(pending, 3)                    # the procedural vote is left out
        by = {c["member_id"]: c for c in cands}
        self.assertEqual(set(by), {"10/1", "10/2", "10/3"})
        self.assertTrue(all(c["label"] == camp.NOT_A_TARGET for c in cands))
        self.assertEqual((by["10/1"]["yea"], by["10/1"]["nay"]), (2, 1))   # facts only
        self.assertNotIn("mixed", by["10/1"])
        _, text = self.run_tool("targets", "--cc", "pl", "pl-family")
        self.assertIn("AWAITING SIGN-OFF", text)
        self.assertIn("Suggested targets: none", text)
        self.assertIn(camp.NOT_A_TARGET, text)
        self.assertNotIn("++", text.split("Candidates")[1])

    def test_adding_an_unplaced_member_needs_a_reason_and_is_labelled_a_choice(self):
        c = self.open()
        added, refused = camp.add_targets(c, self.conn, ["10/1"], "Christopher",
                                          config_dir=self.cfg, base=self.camps, today=TODAY)
        self.assertEqual(added, [])
        self.assertIn("no confirmed placement", refused[0][1])
        with self.assertRaises(ValueError):
            camp.add_targets(c, self.conn, ["10/1"], "", reason="x", config_dir=self.cfg)
        added, _ = camp.add_targets(c, self.conn, ["10/1"], "Christopher", reason="sits on the "
                                    "committee", config_dir=self.cfg, base=self.camps, today=TODAY)
        self.assertIn("no confirmed stance", added[0]["basis"])
        self.assertNotIn("suggested", added[0]["basis"])
        again = camp.load_campaign("pl", "pl-family", self.camps)
        self.assertEqual([t["member_id"] for t in again["targets"]], ["10/1"])
        _, refused = camp.add_targets(again, self.conn, ["10/1", "99/9"], "Christopher", reason="r",
                                      config_dir=self.cfg, base=self.camps)
        self.assertEqual([r[0] for r in refused], ["10/1", "99/9"])

    def test_score_without_a_prediction_gives_counts_only(self):
        c = self.open()
        camp.record_outcome(c, self.conn, "pl-10-1-4", "yes", "Christopher", self.cfg, TODAY,
                            self.camps)
        res = camp.score(c, self.conn)
        s = res["summary"]
        self.assertFalse(s["prediction"])
        self.assertEqual((s["align_with_us"], s["align_against_us"]), (2, 1))
        text = camp.score_text(c, res)
        self.assertIn("No prediction to score", text)
        self.assertIn("stated by Christopher; no confirmed reading", text)
        self.assertNotIn("Placement held", text)

    def test_no_performance_data_is_reported_plainly(self):
        status, lines = camp.performance("pl", looker_dir=self.looker)
        self.assertEqual(status, "no data")
        text = "\n".join(lines)
        self.assertIn("NO CAMPAIGN PERFORMANCE DATA YET", text)
        self.assertIn("pl_campaigns.tsv", text)
        self.assertIn('program: "PL%"', text)


class AfterSignOff(Base):
    def setUp(self):
        super().setUp()
        self.confirm_soft()

    def test_targets_come_from_confirmed_placements(self):
        c = self.open()
        self.assertEqual(c["state"], "placed")
        cols = {r["member_id"]: r["column"] for r in c["snapshot"]}
        self.assertEqual(cols, {"10/1": "+", "10/2": "-", "10/3": "0"})
        rows, _ = camp.placements(self.conn, "pl", "sejm", 9, self.cfg)
        self.assertEqual(sorted(r["person_id"] for r in camp.suggested_targets(rows)),
                         ["10/1", "10/2"])
        added, _ = camp.add_targets(c, self.conn, ["10/2"], "Christopher", config_dir=self.cfg,
                                    base=self.camps, today=TODAY)
        self.assertIn("suggested from a confirmed placement (-)", added[0]["basis"])
        _, text = self.run_tool("targets", "--cc", "pl", "pl-family")
        self.assertIn("Suggested targets, from CONFIRMED readings only (2)", text)
        cand = text.split("Candidates")[1]
        self.assertIn("Celina", cand)                   # unplaced: still only a candidate
        self.assertNotIn("Anna", cand)

    def test_outcome_side_must_agree_with_a_confirmed_reading(self):
        c = self.open()
        with self.assertRaises(ValueError) as ctx:
            camp.record_outcome(c, self.conn, "pl-10-1-1", "yes", config_dir=self.cfg,
                                base=self.camps)
        self.assertIn("CONFIRMED reading", str(ctx.exception))
        o = camp.record_outcome(c, self.conn, "pl-10-1-1", "no", config_dir=self.cfg,
                                base=self.camps, today=TODAY)
        self.assertEqual(o["basis"], "matches the confirmed reading")
        with self.assertRaises(ValueError):
            camp.record_outcome(c, self.conn, "pl-99", "no", config_dir=self.cfg)

    def test_score_measures_the_placements(self):
        c = self.open()
        camp.add_targets(c, self.conn, ["10/2"], "Christopher", config_dir=self.cfg,
                         base=self.camps, today=TODAY)
        camp.record_outcome(c, self.conn, "pl-10-1-4", "yes", config_dir=self.cfg,
                            base=self.camps, today=TODAY)
        res = camp.score(c, self.conn)
        s = res["summary"]
        self.assertTrue(s["prediction"])
        self.assertEqual((s["tested"], s["held"], s["accuracy"]), (2, 2, 100))
        self.assertTrue(s["circular"])                  # the vote predates the snapshot
        self.assertEqual(s["target_against_us"], 1)
        rc, text = self.run_tool("score", "--cc", "pl", "pl-family", "--csv")
        self.assertEqual(rc, 0)
        self.assertIn("NOT a prediction score", text)
        self.assertTrue(os.path.exists(os.path.join(self.out,
                                                    "pl-5ca-evaluate-pl-family-2026-10-10.csv")))

    def test_absence_is_never_counted_as_an_abstention(self):
        c = self.open()
        camp.record_outcome(c, self.conn, "pl-10-1-1", "no", config_dir=self.cfg,
                            base=self.camps, today=TODAY)
        rows = {r["member_id"]: r for r in camp.score(c, self.conn)["rows"]}
        self.assertEqual((rows["10/3"]["vote"], rows["10/3"]["alignment"]), ("0", "did not vote"))
        self.assertEqual(rows["10/1"]["alignment"], "with us")

    def test_reopen_keeps_targets_and_refuses_another_area(self):
        c = self.open()
        camp.add_targets(c, self.conn, ["10/2"], "Christopher", config_dir=self.cfg,
                         base=self.camps, today=TODAY)
        again = self.open()
        self.assertEqual(len(again["targets"]), 1)
        with self.assertRaises(ValueError):
            camp.open_campaign(self.conn, "pl", 1, "pl-family", config_dir=self.cfg,
                               base=self.camps, today=TODAY)


class FindAndPerformance(Base):
    def test_find_reports_the_reading_status(self):
        got = camp.find_divisions(self.conn, "pl", "odrzucenie", self.cfg)
        self.assertEqual([r["key"] for r, _ in got], ["pl-10-1-4"])
        self.assertIn(camp.AWAITING, got[0][1])
        got = camp.find_divisions(self.conn, "pl", "10/50", self.cfg)
        self.assertIn("no reading drafted", got[0][1])

    def test_performance_joins_by_petition_and_names(self):
        os.makedirs(self.looker)
        with open(os.path.join(self.looker, "pl_campaigns.tsv"), "w", encoding="utf-8") as h:
            h.write(TSV)
        c = self.open(petitions=["17002", "17999"])
        status, lines = camp.performance("pl", c, self.conn, self.looker)
        text = "\n".join(lines)
        self.assertEqual(status, "joined")
        self.assertIn("17002 Stop cohabitation contracts: 8000 signatures", text)
        self.assertIn("not in the export: 17999", text)
        self.assertIn("Members named in a petition (1)", text)
        self.assertIn("10/1", text)

    def test_cli_open_list_and_performance(self):
        rc, text = self.run_tool("open", "--cc", "pl", "9", "pl-cli")
        self.assertEqual(rc, 0)
        self.assertIn("This snapshot is no prediction", text)
        _, text = self.run_tool("list", "--cc", "pl")
        self.assertIn("pl-cli", text)
        _, text = self.run_tool("performance", "--cc", "pl", "pl-cli")
        self.assertIn("NO CAMPAIGN PERFORMANCE DATA YET", text)
        _, text = self.run_tool("members", "--cc", "pl", "adamska")
        self.assertIn("[10/1] Anna Adamska", text)


if __name__ == "__main__":
    unittest.main()
