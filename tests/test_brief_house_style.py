"""Christopher's refinement of the RE Core Syllabus brief (2026-08-31)
became the generator's house style. Source of truth: his edited sheet,
diffed field by field against what the generator produced.

What he changed, and where each lesson landed:
- campaign name is a headline ("Tell Paul Givan: ..."), never the official
  consultation title -> drafted campaign_name field, official title kept in
  Notes/slug/Drive name for traceability;
- addressee is one named decision-maker in formal style -> drafted field,
  deterministic fallback;
- long fields are labelled claim-colon-support points, the ask is one moral
  demand in prose -> DRAFT_SYSTEM house-style block;
- TIM row filled with related petition ids -> model picks from a WHITELIST
  built from campaign_performance (ids never composed), widened by nation
  mention because his top pick matched on geography, not area;
- sources are titled lines, no internal monitor link -> build_sources;
- delivery date is a concrete date days before the close -> delivery_date;
- Main Purposes defaults to Acquisition (his answer, 2026-08-31);
- ledger telemetry stays out of the rendered Background.
"""

import datetime
import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db

import make_briefs as mb


def perf_conn(rows):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    conn.execute("CREATE TABLE campaign_performance (petition_id INTEGER, "
                 "name TEXT, areas TEXT, new_members INTEGER, "
                 "signatures INTEGER, logged_at TEXT)")
    for pid, name, areas, new_members in rows:
        conn.execute("INSERT INTO campaign_performance (petition_id, name, "
                     "areas, new_members, signatures, logged_at) "
                     "VALUES (?,?,?,?,?, '2026-08-20')",
                     (pid, name, json.dumps(areas), new_members,
                      new_members * 4))
    conn.commit()
    return conn


NI_SUBJECT = {"kind": "consultation", "areas": [6], "nation": "N. Ireland",
              "title": "Consultation on the RE Core Syllabus",
              "url": "https://x/re"}


class TimCandidateTests(unittest.TestCase):
    def test_nation_mention_widens_beyond_area_overlap(self):
        # Petition 17165 is area [8] on a subject tagged [6]; its name says
        # NI. Christopher led his TIM list with it - geography and audience
        # made it the exact match, and areas alone would have missed it.
        conn = perf_conn([
            (17165, "Protect Christian Teaching in NI Schools", [8], 29509),
            (12992, "Stop LGBT indoctrination clubs in schools", [6], 4417),
            (14001, "Defend marriage", [3], 9000)])
        got = mb.tim_candidates(conn, NI_SUBJECT)
        self.assertEqual([c["id"] for c in got], [17165, 12992])

    def test_westminster_subjects_use_area_overlap_only(self):
        conn = perf_conn([
            (17165, "Protect Christian Teaching in NI Schools", [8], 29509),
            (12992, "Stop LGBT indoctrination clubs in schools", [6], 4417)])
        subject = dict(NI_SUBJECT, nation=None)
        self.assertEqual([c["id"] for c in mb.tim_candidates(conn, subject)],
                         [12992])

    def test_the_whitelist_is_capped_and_ranked(self):
        conn = perf_conn([(9000 + i, "Education petition {0}".format(i),
                           [6], i) for i in range(20)])
        got = mb.tim_candidates(conn, dict(NI_SUBJECT, nation=None))
        self.assertEqual(len(got), 15)
        self.assertEqual(got[0]["new_members"], 19)

    def test_the_model_is_told_to_cite_only_the_whitelist(self):
        tim_q = dict(mb.NARRATIVE_FIELDS)["tim"]
        self.assertIn("tim_candidates ONLY", tim_q)
        self.assertIn("verbatim", tim_q)


class SourcesTests(unittest.TestCase):
    SOURCE = ("**Sources**\n"
              "- Consultation portal: https://x/re\n"
              "- Supreme Court judgment: https://supremecourt.uk/j.pdf\n"
              "\n**What should the image look like**\nA child.")

    def test_source_material_lines_are_copied_verbatim(self):
        got = mb.build_sources(NI_SUBJECT, self.SOURCE)
        self.assertIn("- Supreme Court judgment: https://supremecourt.uk/j.pdf",
                      got)

    def test_the_subject_url_is_not_duplicated(self):
        got = mb.build_sources(NI_SUBJECT, self.SOURCE)
        self.assertEqual(got.count("https://x/re"), 1)

    def test_without_source_material_the_subject_url_is_titled(self):
        got = mb.build_sources(NI_SUBJECT)
        self.assertEqual(got, "- Consultation on the RE Core Syllabus: "
                              "https://x/re")

    def test_the_internal_monitor_link_is_never_a_source(self):
        src = open(os.path.join(ROOT, "tools", "make_briefs.py"),
                   encoding="utf-8").read()
        self.assertNotIn("parl-monitor-partner", src)


class DeliveryDateTests(unittest.TestCase):
    def test_a_concrete_date_days_before_the_close(self):
        # Christopher set 26 September against a 30 September close.
        self.assertEqual(mb.delivery_date("2026-09-30"),
                         "2026-09-26 (close: 2026-09-30)")

    def test_an_unparseable_deadline_degrades_to_before(self):
        self.assertEqual(mb.delivery_date("late September"),
                         "Before late September")


class HouseStyleTests(unittest.TestCase):
    def test_the_system_prompt_carries_the_refinement_rules(self):
        for anchor in ("ONE memorable hook phrase",
                       "one moral demand of the named decision-maker",
                       "short assertive claim ending in a colon",
                       "silence would read as consent",
                       "never a bulleted\n  list"):
            self.assertIn(anchor, mb.DRAFT_SYSTEM)

    def test_campaign_name_and_addressee_are_drafted_fields(self):
        ids = [fid for fid, _ in mb.NARRATIVE_FIELDS]
        for fid in ("campaign_name", "addressee", "tim"):
            self.assertIn(fid, ids)

    def test_main_purposes_defaults_to_acquisition(self):
        src = open(os.path.join(ROOT, "tools", "make_briefs.py"),
                   encoding="utf-8").read()
        self.assertIn('("Main Purposes", "Acquisition")', src)
        self.assertNotIn('("Main Purposes", "Political Impact")', src)

    def test_ledger_telemetry_stays_out_of_the_background(self):
        got = mb.background(dict(NI_SUBJECT, deadline="2026-09-30", why=None,
                                 next_key_date=None),
                            {"debate": 105, "pq": 23})
        self.assertNotIn("105", got)
        self.assertNotIn("ledger", got)

    def test_the_markdown_title_is_the_campaign_name_with_the_subject_kept(self):
        fields = {"general": [], "plan": [], "prepare": [],
                  "urgency": "Non-Urgent Campaign (by default)",
                  "campaign_name": "Tell Paul Givan: keep your promise"}
        md = mb.render_markdown(NI_SUBJECT, fields, ["", "", "", "", ""],
                                [], "", [], "2026-08-31")
        self.assertIn("# Campaigns Brief (DRAFT): Tell Paul Givan: "
                      "keep your promise", md)
        self.assertIn("Subject: Consultation on the RE Core Syllabus", md)


if __name__ == "__main__":
    unittest.main()
