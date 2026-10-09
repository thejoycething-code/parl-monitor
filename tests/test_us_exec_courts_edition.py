"""The US edition's Executive actions and Supreme Court sections, and the
judge's queue for them (tools/us_monitor.py, tools/us_triage.py).
No network: a store built in memory."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


usm = _load("us_monitor")
ust = _load("us_triage")
TODAY = "2026-10-09"


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def fr_doc(conn, number, doc_type, title, published, areas, subtype=None, eo=None, close=None,
           comment_url=None, score=None, why=None):
    conn.execute("INSERT INTO us_fr_documents (document_number, doc_type, subtype, title, "
                 "agencies, publication_date, comments_close_on, eo_number, comment_url, "
                 "html_url, areas, triage_score, why_it_matters) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (number, doc_type, subtype, title, json.dumps(["Health and Human Services "
                                                                "Department"]),
                  published, close, eo, comment_url,
                  "https://www.federalregister.gov/d/" + number, json.dumps(areas), score, why))


def case(conn, key, kind, name, docket, decided, areas, summary="A holding.", term="25"):
    conn.execute("INSERT INTO us_court_cases (case_key, kind, term, docket, case_name, decided, "
                 "summary, url, areas) VALUES (?,?,?,?,?,?,?,?,?)",
                 (key, kind, term, docket, name, decided, summary,
                  "https://www.supremecourt.gov/x", json.dumps(areas)))


class ExecutiveTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        fr_doc(self.conn, "2026-20329", "Proposed Rule", "Reforming Federal Reporting in Child "
               "Welfare", "2026-10-05", [6], close="2026-11-04",
               comment_url="http://www.regulations.gov/commenton/ACF-2026-0562-0001")
        fr_doc(self.conn, "2026-19000", "Proposed Rule", "Conscience Protections", "2026-09-01",
               [1], close="2026-10-15")
        fr_doc(self.conn, "2026-18000", "Proposed Rule", "Closed Rule", "2026-08-01", [1],
               close="2026-09-01")
        fr_doc(self.conn, "2025-02175", "Presidential Document", "Enforcing the Hyde Amendment",
               "2025-01-31", [1], subtype="Executive Order", eo="14182")
        fr_doc(self.conn, "2026-20500", "Rule", "Visa Biometrics", "2026-10-06", [11])

    def section(self):
        text = usm.render_edition(self.conn, TODAY)
        return text, text.split("## Executive actions")[1].split("## Supreme Court")[0]

    def test_new_this_week_and_open_for_comment(self):
        _text, sec = self.section()
        self.assertIn("### New on our ground this week (1)", sec)
        self.assertIn("Reforming Federal Reporting", sec)
        self.assertIn("### Open for comment (2)", sec)
        self.assertNotIn("Closed Rule", sec)
        self.assertNotIn("Enforcing the Hyde Amendment", sec)     # not this week

    def test_closing_soon_is_bold_and_reaches_the_top_lines(self):
        text, sec = self.section()
        self.assertIn("**closes 2026-10-15 (6 days)**", sec)
        self.assertIn("closes 2026-11-04 (26 days)", sec)
        self.assertIn("[Comment](http://www.regulations.gov/", sec)
        top = text.split("## Top lines")[1].split("## Dates")[0]
        self.assertIn("**1 comment period(s) on our ground close within 14 days**", top)

    def test_migration_only_documents_are_never_shown(self):
        self.assertNotIn("Visa Biometrics", usm.render_edition(self.conn, TODAY))

    def test_an_executive_order_is_labelled_with_its_number(self):
        self.conn.execute("UPDATE us_fr_documents SET publication_date='2026-10-07' "
                          "WHERE document_number='2025-02175'")
        _text, sec = self.section()
        self.assertIn("**Executive Order 14182**", sec)

    def test_an_empty_store_renders_and_says_so(self):
        conn = store()
        text = usm.render_edition(conn, TODAY)
        self.assertIn("*Nothing new on our ground in the Federal Register this week.*", text)
        self.assertIn("*No proposed rule on our ground is open for comment.*", text)
        self.assertIn("*No opinion or grant on our ground this week.*", text)
        self.assertNotIn("—", text)


class CourtTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        case(self.conn, "opinion/25/24", "opinion", "Chiles v. Salazar", "24-539", "2026-03-31",
             [4, 7])
        case(self.conn, "grant/24-539", "grant", "Chiles v. Salazar", "24-539", "2025-03-10",
             [4], term="24")
        case(self.conn, "grant/26-100", "grant", "Doe v. State", "26-100", "2026-10-05", [3],
             summary="Whether a ban on puberty blockers survives scrutiny.", term="26")
        case(self.conn, "opinion/25/40", "opinion", "Tax v. Revenue", "25-1", "2026-05-01", [])
        # Consolidated under another docket, granted before the cutoff.
        case(self.conn, "grant/24-38", "grant", "Little v. Hecox", "24-38", "2025-07-03", [5],
             term="25")

    def test_this_week_pending_and_decided(self):
        text = usm.render_edition(self.conn, TODAY)
        sec = text.split("## Supreme Court")[1].split("## Coverage")[0]
        self.assertIn("### This week (1)", sec)
        self.assertIn("Doe v. State", sec.split("### Granted")[0])
        pending = sec.split("### Granted, awaiting decision")[1].split("### Decided")[0]
        self.assertIn("Doe v. State", pending)
        self.assertNotIn("Chiles", pending)                         # decided since
        self.assertNotIn("Hecox", pending)                          # before the cutoff
        self.assertIn("### Decided on our ground, October Term 2025 (1)", sec)
        self.assertNotIn("Tax v. Revenue", sec)
        self.assertIn("Supreme Court**: Doe v. State (certiorari granted)", text)

    def test_the_cutoff_follows_the_courts_june(self):
        self.assertEqual(usm.grant_cutoff("2026-10-09"), "2026-01-20")
        self.assertEqual(usm.grant_cutoff("2026-03-01"), "2025-01-20")

    def test_the_dm_carries_the_court_line(self):
        self.assertIn("Doe v. State", usm.dm_summary(self.conn, TODAY))


class JudgeQueueTests(unittest.TestCase):
    def test_documents_and_cases_on_our_ground_are_queued(self):
        conn = store()
        fr_doc(conn, "2026-20329", "Proposed Rule", "Child Welfare", "2026-10-05", [6],
               close="2026-11-04")
        fr_doc(conn, "2026-20500", "Rule", "Visa Biometrics", "2026-10-06", [11])
        case(conn, "grant/26-100", "grant", "Doe v. State", "26-100", "2026-10-05", [3])
        case(conn, "opinion/25/40", "opinion", "Tax v. Revenue", "25-1", "2026-05-01", [])
        items = {i.id: i for i in ust.pending(conn)}
        self.assertEqual(sorted(items), ["us_court_cases:grant/26-100",
                                         "us_fr_documents:2026-20329"])
        self.assertIn("Comments close: 2026-11-04", items["us_fr_documents:2026-20329"].text)
        self.assertIn("Question presented", items["us_court_cases:grant/26-100"].text)

    def test_scores_land_on_the_right_table(self):
        conn = store()
        case(conn, "grant/26-100", "grant", "Doe v. State", "26-100", "2026-10-05", [3])

        class R:
            id, score, why_it_matters = "us_court_cases:grant/26-100", 3, "Why."
        self.assertEqual(ust.apply(conn, [R()]), 1)
        self.assertEqual(conn.execute("SELECT triage_score FROM us_court_cases").fetchone()[0], 3)
        self.assertEqual(ust.pending(conn), [])

    def test_the_frame_names_the_new_sources(self):
        self.assertIn("Federal Register", ust.SYSTEM_PROMPT_US)
        self.assertIn("Supreme Court", ust.SYSTEM_PROMPT_US)


if __name__ == "__main__":
    unittest.main()
