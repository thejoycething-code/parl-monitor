"""EU monitor phase 1 (Christopher, 2026-09-01: "like the Westminster one
but catching all items of concern the EU are promoting").

Source: the Commission's Have-your-say portal, live-probed 2026-09-01
(data/raw/eu-probe-2026-09-01/). Fixtures below are cut from the real
responses. The invariants are the house ones: dates ISO and never guessed,
classification over title + summary with the SAME taxonomy, nothing
suppressed silently, and the separation guarantee -- eu_ tables only.
"""

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


def _load():
    spec = importlib.util.spec_from_file_location(
        "eu_monitor", os.path.join(ROOT, "tools", "eu_monitor.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eu = _load()

# Shapes verbatim from the live probe (one relevant, one not), plus a
# CLOSED row the server filter should never send but once did not exist
# to be tested against.
LISTING = {"initiativeResultDtoPage": {"totalElements": 2, "content": [
    {"id": 18805.0, "reference": "Ares(2026)7014840",
     "foreseenActType": "REG_DEL", "initiativeStatus": "ACTIVE",
     "shortTitle": "Fitness check of the EU legislation on violence "
                   "against women, gender equality and abortion access",
     "currentStatuses": [{"frontEndStage": "PLANNING_WORKFLOW",
                          "receivingFeedbackStatus": "OPEN",
                          "feedbackStartDate": "2026/08/31 08:24:00",
                          "feedbackEndDate": "2026/09/28 23:59:59",
                          "isCurrent": True}],
     "topics": [{"code": "JUST", "label": "Justice and fundamental rights"}]},
    {"id": 19001.0, "reference": "Ares(2026)7020001",
     "foreseenActType": "REG", "initiativeStatus": "ACTIVE",
     "shortTitle": "Plants obtained by new genomic techniques",
     "currentStatuses": [{"frontEndStage": "ISC_WORKFLOW",
                          "receivingFeedbackStatus": "OPEN",
                          "feedbackStartDate": "2026/08/20 00:00:00",
                          "feedbackEndDate": "2026/09/17 23:59:59",
                          "isCurrent": True}],
     "topics": [{"code": "FOOD", "label": "Food safety"}]},
    {"id": 17000.0, "reference": "Ares(2026)6000000",
     "foreseenActType": "DIR", "initiativeStatus": "ACTIVE",
     "shortTitle": "A closed one the server filter should have dropped",
     "currentStatuses": [{"frontEndStage": "ADOPTION_WORKFLOW",
                          "receivingFeedbackStatus": "CLOSED",
                          "feedbackStartDate": "2026/01/01 00:00:00",
                          "feedbackEndDate": "2026/02/01 23:59:59",
                          "isCurrent": True}],
     "topics": []},
]}}

DETAILS = {
    "18805": {"dossierSummary": "This initiative evaluates the framework on "
              "violence against women including access to abortion services "
              "and gender equality obligations across member states."},
    "19001": {"dossierSummary": "Information requirements for category 1 "
              "NGT plants under Regulation (EU) 2026/1388."},
}


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_json(self, url, feed, slug, archive=True):
        self.calls.append(url)
        if "searchInitiatives" in url:
            return LISTING
        key = url.rstrip("/").rsplit("/", 1)[-1]
        return DETAILS[key]


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class ParseTests(unittest.TestCase):
    def test_dates_become_iso_and_closed_rows_are_dropped(self):
        found, total = eu.parse_listing(LISTING)
        self.assertEqual([c["key"] for c in found], ["18805", "19001"])
        self.assertEqual(found[0]["opened"], "2026-08-31")
        self.assertEqual(found[0]["closes"], "2026-09-28")
        self.assertEqual(total, 2)

    def test_the_public_url_is_the_official_portal_page(self):
        found, _ = eu.parse_listing(LISTING)
        self.assertEqual(found[0]["url"],
                         "https://ec.europa.eu/info/law/better-regulation/"
                         "have-your-say/initiatives/18805")


class PullTests(unittest.TestCase):
    def test_classification_runs_on_title_plus_summary(self):
        conn = store()
        n, new, ours = eu.pull(conn, FakeClient(), "2026-09-01",
                               log=lambda *a: None)
        self.assertEqual((n, new), (2, 2))
        row = conn.execute("SELECT * FROM eu_consultations WHERE key='18805'"
                           ).fetchone()
        self.assertTrue(json.loads(row["areas"]),
                        "the VAW/abortion fitness check must match the "
                        "taxonomy")
        self.assertIn("abortion", row["summary"])
        ngt = conn.execute("SELECT areas FROM eu_consultations WHERE "
                           "key='19001'").fetchone()
        self.assertEqual(json.loads(ngt["areas"]), [],
                         "NGT plants are not our ground")

    def test_a_second_pull_fetches_no_details_for_known_rows(self):
        conn = store()
        eu.pull(conn, FakeClient(), "2026-09-01", log=lambda *a: None)
        client = FakeClient()
        eu.pull(conn, client, "2026-09-02", log=lambda *a: None)
        details = [u for u in client.calls if "groupInitiatives" in u]
        self.assertEqual(details, [], "summaries are cached in the store")

    def test_a_dead_feed_is_a_recorded_gap_not_a_crash(self):
        from src.http import FetchError

        class DeadClient:
            def get_json(self, url, feed, slug, archive=True):
                raise FetchError(url, feed, slug, 3, "boom")

        conn = store()
        n, new, ours = eu.pull(conn, DeadClient(), "2026-09-01",
                               log=lambda *a: None)
        self.assertEqual((n, new, ours), (0, 0, 0))
        gap = conn.execute("SELECT feed FROM gaps").fetchone()
        self.assertEqual(gap["feed"], "eu-consultations")


class SeparationTests(unittest.TestCase):
    def test_the_tool_never_writes_items_or_mp_events(self):
        src = open(os.path.join(ROOT, "tools", "eu_monitor.py"),
                   encoding="utf-8").read()
        self.assertNotIn("INSERT INTO items", src)
        self.assertNotIn("INTO mp_events", src)

    def test_render_prints_the_unmatched_not_just_ours(self):
        # The suppression lesson: what did not match is listed, not dropped.
        conn = store()
        eu.pull(conn, FakeClient(), "2026-09-01", log=lambda *a: None)
        lines = []
        eu.render(conn, "2026-09-01", out=lines.append)
        text = "\n".join(lines)
        self.assertIn("violence against women", text)
        self.assertIn("WATCHING - no taxonomy match", text)
        self.assertIn("Plants obtained by new genomic techniques", text)


class EditionTests(unittest.TestCase):
    """The separate EU edition (Christopher, 2026-09-01): its own document,
    not a section of Westminster's week; nothing downstream yet."""

    def test_the_edition_carries_ours_watching_and_no_downstream(self):
        import tempfile
        conn = store()
        eu.pull(conn, FakeClient(), "2026-09-01", log=lambda *a: None)
        old = eu.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "editions"))
            os.makedirs(os.path.join(tmp, "config"))
            for f in ("taxonomy.yaml", "watchlist.yaml"):
                with open(os.path.join(ROOT, "config", f), "rb") as src, \
                     open(os.path.join(tmp, "config", f), "wb") as dst:
                    dst.write(src.read())
            eu.ROOT = tmp
            try:
                path = eu.render_edition(conn, "2026-09-01")
            finally:
                eu.ROOT = old
            text = open(path, encoding="utf-8").read()
        self.assertIn("# EU Monitor - week commencing 2026-09-01", text)
        self.assertIn("## On our ground (1)", text)
        self.assertIn("violence against women", text)
        self.assertIn("(27 days, open)", text)
        self.assertIn("## Watching - no taxonomy match (1)", text)
        self.assertIn("Plants obtained by new genomic techniques", text)
        self.assertIn("No Top lines, no Slack", text)
        self.assertIn("gated by its Asana approval task", text)


if __name__ == "__main__":
    unittest.main()


class PlenaryLeadTests(unittest.TestCase):
    """Christopher, 17 Sept 2026: "fix the weekly DM to lead with the plenary".
    It opened on Commission feedback windows and reached divisions only through
    the triage-scored list, so the 15 September sitting -- 86 roll calls on our
    ground, the Democracy Shield report adopted 420-220-26 -- would not have
    appeared in the DM at all."""

    def setUp(self):
        self.conn = store()
        rows = [
            ("WHOLE", "2026-09-15", "Big report - Tomas Tobe - Motion for a resolution (as a whole)", 420, 220, 26),
            ("SPLIT1", "2026-09-15", "Big report - Tomas Tobe - Recital B", 555, 94, 21),
            ("SPLIT2", "2026-09-15", "Big report - Tomas Tobe - § 17", 434, 235, 3),
            ("SPLIT3", "2026-09-15", "Big report - Tomas Tobe - After § 88 - Am 94", 117, 489, 65),
            ("OLD", "2020-01-01", "Ancient business", 10, 5, 0),
        ]
        for vid, date, label, f, a, ab in rows:
            self.conn.execute(
                "INSERT INTO eu_divisions (vote_id, sitting_id, date, label, "
                "favor, against, abstention, areas, matched_terms, tier, "
                "first_seen, last_seen) VALUES (?,'s',?,?,?,?,?,'[7]','[]',1,"
                "'2026-09-17','2026-09-17')", (vid, date, label, f, a, ab))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_a_recital_or_paragraph_or_amendment_split_is_recognised(self):
        self.assertFalse(eu.is_split("Big report - Tomas Tobe - Motion for a resolution (as a whole)"))
        self.assertTrue(eu.is_split("Big report - Tomas Tobe - Recital B"))
        self.assertTrue(eu.is_split("Big report - Tomas Tobe - \u00a7 17"))
        self.assertTrue(eu.is_split("Big report - Tomas Tobe - After \u00a7 88 - Am 94"))
        self.assertFalse(eu.is_split("A plain motion with no splits"))

    def test_the_whole_text_vote_leads_and_the_splits_are_counted_not_listed(self):
        out = eu.plenary_lines(self.conn, "2026-09-17")
        self.assertIn("4 roll call(s) on our ground", out[0])
        self.assertIn("*adopted* 420-220-26", out[1], "the whole-text vote leads")
        self.assertTrue(any("3 further roll call(s)" in ln for ln in out), out)

    def test_an_unsigned_division_is_reported_as_a_result_and_nothing_more(self):
        out = eu.plenary_lines(self.conn, "2026-09-17")
        self.assertIn("no verdict signed", out[1])
        self.assertNotIn("OUR WAY", out[1])

    def test_business_outside_the_window_never_leads(self):
        out = eu.plenary_lines(self.conn, "2026-09-17", days=30)
        self.assertNotIn("Ancient business", " ".join(out))

    def test_a_quiet_month_says_so_rather_than_dropping_the_section(self):
        conn = store()
        body = eu.dm_summary(conn, "2026-09-17")
        self.assertIn("No plenary business on our ground", body)
        conn.close()


class AdoptedTextsGateTests(unittest.TestCase):
    """Body matching took the matched adopted texts from 8 to 44 of 145; the
    section is gated on the judge's score (18 Sept 2026)."""

    def _render(self, conn):
        import tempfile
        old = eu.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "editions"))
            os.makedirs(os.path.join(tmp, "config"))
            for f in ("taxonomy.yaml", "watchlist.yaml"):
                with open(os.path.join(ROOT, "config", f), "rb") as src, \
                     open(os.path.join(tmp, "config", f), "wb") as dst:
                    dst.write(src.read())
            eu.ROOT = tmp
            try:
                path = eu.render_edition(conn, "2026-09-01")
            finally:
                eu.ROOT = old
            return open(path, encoding="utf-8").read()

    def test_score_two_and_unscored_show_zero_and_one_do_not(self):
        conn = store()
        conn.execute("ALTER TABLE eu_texts ADD COLUMN triage_score INTEGER")
        conn.execute("ALTER TABLE eu_texts ADD COLUMN why_it_matters TEXT")
        rows = [("TA-3", "Persecution of Christians in Nigeria", "[8]", 3),
                ("TA-2", "Social media and young people", "[6]", 2),
                ("TA-1", "Enlargement report on Albania", "[7]", 1),
                ("TA-0", "Prison dietary standards", "[1]", 0),
                ("TA-N", "Not yet judged text", "[5]", None),
                ("TA-X", "Common fisheries policy", "[]", None)]
        for ident, title, areas, score in rows:
            conn.execute("INSERT INTO eu_texts (identifier, date, title, areas, tier, first_seen, "
                         "last_seen, triage_score) VALUES (?,?,?,?,?,?,?,?)",
                         (ident, "2026-08-20", title, areas, 2, "2026-08-21", "2026-08-21", score))
        text = self._render(conn)
        self.assertIn("## Adopted by the Parliament", text)
        for shown in ("Persecution of Christians in Nigeria", "Social media and young people",
                      "Not yet judged text"):
            self.assertIn(shown, text)
        for hidden in ("Enlargement report on Albania", "Prison dietary standards"):
            self.assertNotIn(hidden, text)
        self.assertIn("5 of 6 adopted texts in the window matched the taxonomy; 3 shown "
                      "(judge score 2+ or not yet scored).", text)
