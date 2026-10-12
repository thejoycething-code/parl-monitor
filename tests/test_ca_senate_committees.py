"""Senate committee transcripts (tools/ca_senate_committees.py) and committee
reports, House and Senate (tools/ca_committee_reports.py). No network.

Fixtures are the live pages of 12 October 2026: LCJC 45-1's Studies table cut
to three studies (meetings 53, 29 and 4), the LCJC meeting 4 transcript whole
(Bill S-209, 1 October 2025; gzipped), the SOCI 45-1 and RIDR 44-1 reports
partials whole, LCJC's Twelfth Report page, the JUST 44-1 Work page cut to
three reports, and the JUST 44-1 report 4 and HESA 45-1 report 1 pages.
"""

import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.robots_guard import RobotsRefused  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scm = _load("ca_senate_committees")
rep = _load("ca_committee_reports")
rt = _load("ca_retag")
TAX = filt.load_taxonomy(scm.cm.TAXONOMY)
WL = filt.load_watchlist(scm.cm.WATCHLIST)
TODAY = "2026-10-12"


def fixture(name):
    path = os.path.join(FIX, name)
    if name.endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            return fh.read().decode("utf-8")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


LCJC_P1 = scm.studies_url(1011, "45-1", 1)
LCJC_P2 = scm.studies_url(1011, "45-1", 2)
LCJC_4 = "https://sencanada.ca/en/content/sen/committee/451/lcjc/04ev-57219-e"
LCJC_29 = "https://sencanada.ca/en/content/sen/committee/451/lcjc/29ev-57566-e"
EMPTY_PAGE = "<html><body><div id=\"table-print\"></div></body></html>"
PAGES = {
    LCJC_P1: ("ca_sencmte_lcjc_451_studies.html", None),
    LCJC_P2: (None, EMPTY_PAGE),
    LCJC_4: ("ca_sencmte_lcjc_451_4.html.gz", None),
    # meeting 29's transcript is NOT served: a 404, so a gap.
}

JUST_WORK = rep.work_url("JUST", 44, 1)
R4 = "https://www.ourcommons.ca/DocumentViewer/en/44-1/JUST/report-4/"
REPORT_PAGES = {
    JUST_WORK: ("ca_cmte_just_441_work.html", None),
    R4 + "page-ToC": ("ca_cmte_just_441_r4_toc.html.gz", None),
    "https://www.ourcommons.ca/documentviewer/en/44-1/JUST/report-4/page-18":
        ("ca_cmte_just_441_r4_recs.html.gz", None),
    "https://www.ourcommons.ca/DocumentViewer/en/44-1/JUST/report-3/page-ToC":
        ("ca_cmte_hesa_451_r1_toc.html.gz", None),     # a one-page report stands in
    rep.SENATE_REPORTS.format(1047, "45-1"): ("ca_sencmte_soci_451_reports.html", None),
    "https://sencanada.ca/en/committees/SOCI/report/158155/45-1":
        ("ca_sencmte_lcjc_report_158212.html.gz", None),
}


class FakeClient:
    """Serves the fixtures by URL; anything else is a 404."""

    def __init__(self, pages=None, refused=()):
        self.pages = dict(PAGES if pages is None else pages)
        self.refused = set(refused)
        self.calls = []

    def get_text(self, url, feed, slug, archive=True, **kw):
        self.calls.append((url, archive))
        if url in self.refused:
            raise RobotsRefused(url, feed, slug, "robots.txt disallows " + url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1,
                             urllib.error.HTTPError(url, 404, "Not Found", {}, None))
        name, text = self.pages[url]
        return fixture(name) if name else text


def quiet(*a):
    return None


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    ca_store.ensure_schema(conn)
    for pid, name in (("senator-214107", "Miville-Dechêne, Julie"),
                      ("senator-3571", "Batters, Denise"),
                      ("senator-235202", "Wells, Kristopher"),
                      ("senator-9", "Wells, David"),
                      ("senator-236807", "Dhillon, Baltej S."),
                      ("senator-207802", "Pate, Kim"),
                      ("senator-10", "Simons, Paula"),
                      ("senator-11", "Simons, Someone Else")):
        conn.execute("INSERT INTO ca_senators (person_id, name) VALUES (?,?)", (pid, name))
    conn.commit()
    return conn


def run(conn, client=None, **kw):
    kw.setdefault("committees", ("LCJC",))
    kw.setdefault("gated", ())
    kw.setdefault("session", "45-1")
    return scm.pull(conn, client or FakeClient(), TODAY, tax=TAX, wl=WL, log=quiet, **kw)


class StudiesTableTests(unittest.TestCase):
    def setUp(self):
        self.got, self.unkeyed, self.items = scm.parse_studies(
            fixture("ca_sencmte_lcjc_451_studies.html"), "LCJC", 45, 1)

    def test_meetings_are_keyed_by_the_number_in_their_links(self):
        self.assertEqual(sorted(self.got), [4, 29, 53])
        self.assertEqual(self.items, 3)
        four = self.got[4]
        self.assertEqual(four["key"], "45-1-LCJC-4")
        self.assertEqual(four["date"], "2025-10-01")
        self.assertEqual(four["evidence_url"], LCJC_4)
        self.assertEqual(four["studies"], ["Bill S-209, An Act to restrict young persons’ online "
                                           "access to pornographic material"])

    def test_a_meeting_held_for_two_studies_keeps_both_titles(self):
        self.assertEqual(len(self.got[29]["studies"]), 2)
        self.assertTrue(any("S-205" in s for s in self.got[29]["studies"]))
        self.assertTrue(any("S-209" in s for s in self.got[29]["studies"]))

    def test_a_meeting_with_no_transcript_has_no_evidence_url(self):
        self.assertIsNone(self.got[53]["evidence_url"])
        self.assertEqual(self.got[53]["date"], "2026-10-01")

    def test_witnesses_carry_name_role_and_organisation_only(self):
        w = self.got[4]["witnesses"]
        awad = [x for x in w if x["name"] == "Amy Awad"]
        self.assertEqual(len(awad), 1)
        self.assertEqual(awad[0]["organisation"], "Canadian Heritage")
        self.assertEqual(set(awad[0]), {"name", "role", "organisation"})


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.problem, self.info, self.ivs = scm.parse_transcript(
            fixture("ca_sencmte_lcjc_451_4.html.gz"))

    def test_it_parses(self):
        self.assertIsNone(self.problem)
        self.assertEqual(self.info["date"], "2025-10-01")
        self.assertEqual(self.info["chair"], "David M. Arnot")
        self.assertEqual(len(self.ivs), 118)
        self.assertEqual([iv["seq"] for iv in self.ivs[:3]], [1, 2, 3])

    def test_the_chair_line_is_not_an_intervention(self):
        self.assertFalse(any(iv["label"].startswith("Senator David M. Arnot") for iv in self.ivs))

    def test_kinds(self):
        self.assertEqual(scm.label_kind("The Chair"), "chair")
        self.assertEqual(scm.label_kind("The Deputy Chair"), "chair")
        self.assertEqual(scm.label_kind("Hon. Senators"), "chair")
        self.assertEqual(scm.label_kind("Senator K. Wells"), "senator")
        self.assertEqual(scm.label_kind("Hon. Julie Miville-Dechêne, sponsor of the bill"), "senator")
        self.assertEqual(scm.label_kind("Hon. Arif Virani, P.C., M.P., Minister of Justice"), "other")
        self.assertEqual(scm.label_kind("Ms. Awad"), "other")

    def test_a_soft_404_and_a_page_with_no_evidence_are_problems(self):
        self.assertIsNotNone(scm.parse_transcript("<html><title></title></html>")[0])
        self.assertIsNotNone(scm.parse_transcript(
            '<html><title>x</title><div id="content-viewer-document"><p>no</p></div></html>')[0])


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        _, info, self.ivs = scm.parse_transcript(fixture("ca_sencmte_lcjc_451_4.html.gz"))
        listed = scm.parse_studies(fixture("ca_sencmte_lcjc_451_studies.html"),
                                   "LCJC", 45, 1)[0][4]["witnesses"]
        scm.attribute(self.ivs, scm.SenatorSurnames(self.conn), info["chair"], listed)

    def by_label(self, label):
        return [iv for iv in self.ivs if iv["label"] == label]

    def test_a_unique_surname_resolves(self):
        iv = self.by_label("Senator Batters")[0]
        self.assertEqual((iv["person_id"], iv["speaker_key"]), ("senator-3571", "denise batters"))

    def test_the_initial_separates_two_wells(self):
        iv = self.by_label("Senator K. Wells")[0]
        self.assertEqual(iv["person_id"], "senator-235202")

    def test_two_candidates_resolve_nothing(self):
        iv = self.by_label("Senator Simons")[0]
        self.assertEqual((iv["person_id"], iv["speaker_key"]), (None, None))

    def test_a_senator_sponsoring_her_bill_is_a_senator_not_a_witness(self):
        iv = self.by_label("Hon. Julie Miville-Dechêne, sponsor of the bill")[0]
        self.assertEqual((iv["kind"], iv["person_id"]), ("senator", "senator-214107"))
        self.assertEqual(self.by_label("Senator Miville-Dechêne")[0]["person_id"], "senator-214107")

    def test_a_witness_short_label_resolves_to_the_full_one(self):
        iv = self.by_label("Ms. Awad")[0]
        self.assertEqual(iv["kind"], "witness")
        self.assertEqual(iv["witness"], "Amy Awad")
        self.assertEqual(iv["organisation"], "Canadian Heritage")
        self.assertIsNone(iv["person_id"])
        self.assertTrue(iv["affiliation"].startswith("Director General"))

    def test_clerks_and_analysts_are_officers(self):
        ivs = [{"seq": 1, "label": "Vincent Labrosse, Clerk of the Committee", "text": "x", "time": None},
               {"seq": 2, "label": "Mr. Labrosse", "text": "y", "time": None},
               {"seq": 3, "label": "Michaela Keenan-Pelletier, analyst, Library of Parliament",
                "text": "z", "time": None}]
        scm.attribute(ivs, scm.SenatorSurnames(self.conn))
        self.assertEqual([iv["kind"] for iv in ivs], ["chair", "chair", "chair"])


class PullTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.client = FakeClient()
        self.s = run(self.conn, self.client)

    def test_one_read_one_gap_one_without_transcript(self):
        self.assertEqual((self.s["read"], self.s["gaps"], self.s["no_evidence"]), (1, 1, 1))
        rows = {r["meeting_key"]: r for r in self.conn.execute(
            "SELECT * FROM ca_committee_meetings")}
        self.assertEqual(rows["45-1-LCJC-4"]["status"], "read")
        self.assertEqual(rows["45-1-LCJC-4"]["chamber"], "senate")
        self.assertEqual(rows["45-1-LCJC-53"]["status"], "no_evidence")
        self.assertNotIn("45-1-LCJC-29", rows)      # gapped: retried next run
        self.assertIn("45-1-LCJC-29: transcript", self.conn.execute(
            "SELECT detail FROM gaps").fetchone()[0])

    def test_senators_go_to_ca_speeches_as_senate_committee_speeches(self):
        rows = self.conn.execute("SELECT * FROM ca_speeches").fetchall()
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual((r["chamber"], r["forum"], r["committee"]), ("senate", "committee", "LCJC"))
            self.assertTrue(r["speech_id"].startswith("scmte-451-LCJC-4-"))
            self.assertTrue(r["speaker"].startswith(("Senator", "Hon.")))
        self.assertEqual(rows[0]["bill_number"], "S-209")

    def test_witnesses_go_only_to_ca_testimony(self):
        t = self.conn.execute("SELECT * FROM ca_testimony").fetchall()
        self.assertTrue(t)
        self.assertEqual({r["chamber"] for r in t}, {"senate"})
        names = {r["witness"] for r in t}
        self.assertIn("Amy Awad", names)
        speakers = {r["speaker"] for r in self.conn.execute("SELECT speaker FROM ca_speeches")}
        self.assertFalse(any("Awad" in s for s in speakers))

    def test_the_transcript_is_archived_and_the_table_is_not(self):
        self.assertIn((LCJC_4, True), self.client.calls)
        self.assertIn((LCJC_P1, False), self.client.calls)

    def test_a_second_run_reads_nothing_again(self):
        client = FakeClient()
        s = run(self.conn, client)
        self.assertEqual((s["read"], s["skipped"]), (0, 1))
        self.assertNotIn(LCJC_4, [u for u, _ in client.calls])

    def test_the_retag_reproduces_senate_committee_rows(self):
        rt.retag(self.conn, TAX, WL, dry_run=True, log=quiet)   # raises Untrusted if not

    def test_ids_never_collide_with_the_house_or_the_floor(self):
        self.assertTrue(scm.speech_id(45, 1, "LCJC", 4, 11).startswith("scmte-"))


class ProductionTests(unittest.TestCase):
    def test_a_table_robots_refuses_is_a_gap_not_fatal(self):
        conn = store()
        s = run(conn, FakeClient(refused={LCJC_P1}))
        self.assertEqual((s["read"], s["gaps"]), (0, 1))
        self.assertIn("robots.txt", conn.execute("SELECT detail FROM gaps").fetchone()[0])

    def test_joint_committees_are_left_to_the_house_collector(self):
        conn = store()
        client = FakeClient()
        run(conn, client, committees=("AMAD",))
        self.assertEqual(client.calls, [])

    def test_an_unpinned_committee_reads_its_id_off_its_page(self):
        pages = dict(PAGES)
        pages["https://sencanada.ca/en/committees/secd/45-1"] = (
            None, 'data-ajaxpartial-data="{&quot;CommitteeId&quot;:1011,&quot;SessionId&quot;:32}"')
        conn = store()
        client = FakeClient(pages)
        s = run(conn, client, committees=(), gated=("SECD",))
        self.assertEqual(client.calls[0][0], "https://sencanada.ca/en/committees/secd/45-1")
        self.assertEqual(client.calls[1][0], LCJC_P1)       # the id read off the page
        # Gated by study title: none of the three titles alone is on our
        # ground, so no transcript is fetched.
        self.assertEqual((s["listed"], s["title_gated"], s["read"]), (3, 3, 0))
        self.assertNotIn(LCJC_4, [u for u, _ in client.calls])

    def test_the_live_client_asks_robots_txt(self):
        for name in ("ca_senate_committees.py", "ca_committee_reports.py"):
            with open(os.path.join(ROOT, "tools", name), encoding="utf-8") as fh:
                self.assertIn("guard(HttpClient(", fh.read())


# --------------------------------------------------------------- reports

def rstore():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    ca_store.ensure_schema(conn)
    return conn


def rrun(conn, client=None, **kw):
    kw.setdefault("house", ("JUST",))
    kw.setdefault("senate", ())
    kw.setdefault("session", "44-1")
    return rep.pull(conn, client or FakeClient(REPORT_PAGES), TODAY, tax=TAX, wl=WL, log=quiet, **kw)


class HouseReportTests(unittest.TestCase):
    def test_the_work_page_lists_reports_with_dates_and_responses(self):
        rows = {r["number"]: r for r in rep.parse_work(fixture("ca_cmte_just_441_work.html"),
                                                         "JUST", 44, 1)}
        self.assertEqual(sorted(rows), [1, 2, 3, 4])
        four = rows[4]
        self.assertEqual(four["key"], "commons-44-1-JUST-4")
        self.assertTrue(four["title"].startswith("Preventing Harm in the Canadian Sex Industry"))
        self.assertEqual(four["study"], "Review of the Protection of Communities and Exploited "
                                        "Persons Act")
        self.assertEqual(four["date"], "2022-06-22")
        self.assertTrue(four["response_url"].endswith("/report-4/response-8512-441-124"))
        self.assertEqual(four["response_date"], "2022-10-20")
        self.assertIsNone(rows[3]["title"])                 # 'Report 3': a bill report
        self.assertIsNone(rows[3]["response_url"])

    def test_the_list_of_recommendations_parses(self):
        recs = rep.parse_recommendations(fixture("ca_cmte_just_441_r4_recs.html.gz"))
        self.assertEqual(len(recs), 17)
        self.assertTrue(recs[0].startswith("Recommendation 1: That the Government of Canada"))

    def test_a_non_breaking_space_in_the_heading_still_parses(self):
        page = '<p class="Rhead">Recommendation&nbsp;1</p>\n<p class="R1">That X.</p>'
        self.assertEqual(rep.parse_recommendations(page), ["Recommendation 1: That X."])

    def test_pull_reads_recommendations_and_a_one_page_report(self):
        conn = rstore()
        s = rrun(conn)
        self.assertEqual(s["listed"], 4)
        self.assertEqual(s["gaps"], 2)             # reports 1 and 2: no ToC served
        r4 = conn.execute("SELECT * FROM ca_committee_reports WHERE report_key="
                          "'commons-44-1-JUST-4'").fetchone()
        self.assertEqual(r4["recommendations"], 17)
        self.assertTrue(r4["recommendations_url"].endswith("/report-4/page-18"))
        self.assertTrue(r4["pdf_url"].endswith("justrp04-e.pdf"))
        self.assertEqual(r4["chamber"], "commons")
        self.assertTrue(json.loads(r4["areas"]))      # sex work and trafficking: on our ground
        r3 = conn.execute("SELECT * FROM ca_committee_reports WHERE report_key="
                          "'commons-44-1-JUST-3'").fetchone()
        self.assertIsNone(r3["recommendations"])
        self.assertIn("Breast Cancer Screening", r3["text"])

    def test_the_retag_reproduces_reports_and_adds_to_them(self):
        conn = rstore()
        rrun(conn)
        rt.retag(conn, TAX, WL, dry_run=True, log=quiet)        # raises Untrusted if not
        conn.execute("UPDATE ca_committee_reports SET areas='[]' WHERE report_key="
                     "'commons-44-1-JUST-4'")
        # One emptied row of two tagged would fail the trust floor; with the
        # floor lowered, the retag puts the areas back, additively.
        changes = rt.retag(conn, TAX, WL, log=quiet, floor=0.0)
        self.assertIn("commons-44-1-JUST-4", [c[1] for c in changes if c[0] == "ca_committee_reports"])
        self.assertTrue(json.loads(conn.execute(
            "SELECT areas FROM ca_committee_reports WHERE report_key='commons-44-1-JUST-4'"
        ).fetchone()[0]))

    def test_a_second_run_fetches_no_report_again_and_links_a_new_response(self):
        conn = rstore()
        rrun(conn)
        conn.execute("UPDATE ca_committee_reports SET response_url=NULL, response_date=NULL")
        client = FakeClient(REPORT_PAGES)
        s = rrun(conn, client)
        self.assertEqual(s["responses"], 1)        # report 4's, report 1 was a gap
        self.assertNotIn(R4 + "page-ToC", [u for u, _ in client.calls])
        self.assertEqual(conn.execute("SELECT response_date FROM ca_committee_reports WHERE "
                                      "report_key='commons-44-1-JUST-4'").fetchone()[0],
                         "2022-10-20")


class SenateReportTests(unittest.TestCase):
    def test_the_partial_lists_substantive_reports(self):
        rows = rep.parse_senate_reports(fixture("ca_sencmte_soci_451_reports.html"), "SOCI")
        self.assertEqual(len(rows), 12)
        eleven = [r for r in rows if r["number"] == 11][0]
        self.assertEqual(eleven["key"], "senate-45-1-SOCI-158141")
        self.assertTrue(eleven["title"].startswith("Fuelled by Technology"))
        self.assertTrue(eleven["pdf_url"].endswith("SOCI_InterimReport_AIStudy_e.pdf"))
        self.assertIsNone(eleven["response_url"])

    def test_government_responses_are_linked(self):
        rows = rep.parse_senate_reports(fixture("ca_sencmte_ridr_441_reports.html"), "RIDR")
        eight = [r for r in rows if r["number"] == 8][0]
        self.assertTrue(eight["response_url"].endswith("GovtResp_Report08_Immigration_e.pdf"))
        self.assertTrue(eight["pdf_url"].endswith("GlobalForcedDisplacement_e.pdf"))

    def test_ordinals(self):
        self.assertEqual(rep.ordinal("Twelfth Report"), 12)
        self.assertEqual(rep.ordinal("Twenty-first Report"), 21)
        self.assertEqual(rep.ordinal("Thirtieth Report"), 30)
        self.assertIsNone(rep.ordinal("Report"))

    def test_the_report_page_gives_date_and_text(self):
        r = {"key": "k", "url": "https://sencanada.ca/en/committees/SOCI/report/158155/45-1"}
        self.assertIsNone(rep.read_senate_report(FakeClient(REPORT_PAGES), r))
        self.assertEqual(r["date"], "2026-06-18")
        self.assertIn("TWELFTH REPORT", r["text"])

    def test_pull_reads_the_one_page_served_and_gaps_the_rest(self):
        conn = rstore()
        s = rrun(conn, house=(), senate=("SOCI",), session="45-1", limit=3)
        self.assertEqual(s["listed"], 12)
        # Twelfth and eleventh are not served (gaps); the tenth is.
        self.assertEqual((s["read"], s["gaps"]), (1, 2))
        row = conn.execute("SELECT * FROM ca_committee_reports").fetchone()
        self.assertEqual((row["chamber"], row["committee"], row["number"]), ("senate", "SOCI", 10))


class MonitorTests(unittest.TestCase):
    def test_senate_witnesses_and_reports_reach_the_edition(self):
        cam = _load("ca_monitor")
        conn = store()
        run(conn)
        rrun(conn)
        conn.execute("UPDATE ca_committee_reports SET date='2026-10-08'")
        conn.execute("UPDATE ca_testimony SET date='2026-10-08'")
        lines, _ = cam.committee_section(conn, "2026-09-01", TODAY, {7: "Pornography"})
        text = "\n".join(lines)
        self.assertIn("**Senate LCJC** [meeting 4](" + LCJC_4 + ")", text)
        self.assertIn("Amy Awad (Canadian Heritage)", text)
        self.assertIn("Committee reports on our ground", text)
        self.assertIn("JUST report 4", text)
        self.assertIn("government response", text)


if __name__ == "__main__":
    unittest.main()
