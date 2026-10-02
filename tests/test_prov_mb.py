"""Manitoba (src/ingest/prov_mb.py). No network: fixtures in tests/fixtures/prov/.

THE PROOF (docs/canada-provinces-scope.md): Bill 207, The Abortion Protest
Buffer Zone Act, second reading on 14 October 2021, NEGATIVED 20-30 --
Fontaine, Kinew and Asagwara for, Cox, Cullen and Pedersen against --
resolved against the member list printed in that day's own Hansard.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_mb as mb  # noqa: E402
from src.prov_fetch import Context, Robots  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
DATE = "2021-10-14"
VP_BASE = "https://www.gov.mb.ca/legislature/business/42nd/42nd_3rd.html"
HANSARD_BASE = "https://www.gov.mb.ca/legislature/hansard/42nd_3rd/42nd_3rd.html"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def conn_from_cover(cover, date, leg, drop=()):
    conn = db.init_db(db.connect(":memory:"))
    members, _ = mb.parse_cover(fx(cover))
    for m in members:
        if m["key"] in drop:
            continue
        ps.upsert_member(conn, "mb", m["key"], name=m["given"] + " " + m["surname"],
                         surname=m["surname"], given=m["given"])
        ps.extend_term(conn, "mb", m["key"], leg, m["party"], m["riding"], date, "hansard-cover")
    conn.commit()
    return conn


class ListingTests(unittest.TestCase):
    def test_session_pages_come_from_the_listings(self):
        vp = mb.session_pages(fx("mb_vp_sessions.html"), mb.VP_SESSIONS, "vp")
        self.assertEqual(vp[(42, 3)], VP_BASE)
        self.assertEqual(vp[(43, 3)], "https://www.gov.mb.ca/legislature/business/43rd/43rd_3rd.html")
        h = mb.session_pages(fx("mb_hansard_sessions.html"), mb.HANSARD_SESSIONS, "hansard")
        self.assertEqual(h[(42, 3)], HANSARD_BASE)
        b = mb.session_pages(fx("mb_bill_sessions.html"), mb.BILL_SESSIONS, "bills")
        self.assertEqual(b[(42, 3)], "https://web2.gov.mb.ca/bills/42-3/index.php")

    def test_vp_calendar_and_the_stray_link(self):
        recs = mb.list_records(fx("mb_vp_42_3.html"), VP_BASE)
        self.assertIn((DATE, "https://www.gov.mb.ca/legislature/business/42nd/3rd/votes_082.pdf"), recs)
        # votes_029 is printed a second time, blank, in the 6 October cell;
        # it is listed under 3 March, so the stray is dropped.
        self.assertIn(("2021-03-03", "https://www.gov.mb.ca/legislature/business/42nd/3rd/votes_029.pdf"), recs)
        self.assertEqual([r for r in recs if r[0] is None], [])
        self.assertEqual(len(recs), 20)

    def test_a_link_listed_only_without_a_day_is_kept_undated(self):
        html = ('<table class="calendar"><thead><tr><td><strong class="thead_title">March 2021</strong>'
                '</td></tr></thead><tbody><tr><td><a href="3rd/votes_077.pdf">6</a>'
                '<a href="3rd/votes_029.pdf"> </a></td></tr></tbody></table>')
        recs = mb.list_records(html, VP_BASE)
        self.assertEqual(recs[-1], (None, "https://www.gov.mb.ca/legislature/business/42nd/3rd/votes_029.pdf"))

    def test_a_stray_is_dropped_when_the_file_is_listed_under_its_day(self):
        html = ('<table class="calendar"><thead><tr><td><strong class="thead_title">March 2021</strong>'
                '</td></tr></thead><tbody><tr><td><a href="3rd/votes_029.pdf">3</a></td>'
                '<td><a href="3rd/votes_077.pdf">6</a><a href="3rd/votes_029.pdf"> </a></td></tr></tbody></table>')
        recs = mb.list_records(html, VP_BASE)
        self.assertEqual([r[0] for r in recs], ["2021-03-03", "2021-03-06"])

    def test_hansard_calendar_gives_the_day_pdfs_in_order(self):
        h = mb.list_hansard(fx("mb_hansard_42_3.html"), HANSARD_BASE)
        self.assertEqual(h[DATE], ["https://www.gov.mb.ca/legislature/hansard/42nd_3rd/hansardpdf/82a.pdf",
                                   "https://www.gov.mb.ca/legislature/hansard/42nd_3rd/hansardpdf/82b.pdf"])


class CoverTests(unittest.TestCase):
    def test_the_hansard_cover_is_the_dated_roster(self):
        members, vacant = mb.parse_cover(fx("mb_cover_211014.txt"))
        self.assertEqual((len(members), vacant), (56, 1))
        by = {m["key"]: m for m in members}
        self.assertEqual((by["cathy-cox"]["riding"], by["cathy-cox"]["party"]), ("Kildonan-River East", "PC"))
        self.assertEqual(by["andrew-smith"]["riding"], "Lagimodière")
        self.assertEqual(by["bernadette-smith"]["riding"], "Point Douglas")
        self.assertEqual(by["janice-morley-lecomte"]["surname"], "Morley-Lecomte")
        self.assertEqual(by["jon-gerrard"]["party"], "Lib.")
        self.assertEqual(by["mark-wasyliw"]["party"], "NDP")

    def test_party_is_a_fact_of_the_day(self):
        members, vacant = mb.parse_cover(fx("mb_cover_250602.txt"))
        self.assertEqual((len(members), vacant), (56, 1))
        by = {m["key"]: m for m in members}
        self.assertEqual(by["mark-wasyliw"]["party"], "Ind.")     # NDP in 2021
        self.assertEqual(by["jelynn-dela-cruz"]["surname"], "Dela Cruz")


class ThirtyNinthLegislatureTests(unittest.TestCase):
    """The 2010 backfill (2 October 2026): the 39th Legislature's covers print
    the party as "N.D.P." and "P.C.", so only the two "Lib." lines were read
    and every division of 2010-2011 failed the tally; "McFADYEN" (mixed case)
    never matched the capitals pattern in any year, so 25 divisions of
    2011-2012 failed on his one name."""

    def test_the_dotted_parties_and_the_mc_surname_are_read(self):
        members, vacant = mb.parse_cover(fx("mb_cover_100326.txt"))
        self.assertEqual((len(members), vacant), (57, 0))
        by = {m["key"]: m for m in members}
        self.assertEqual((by["hugh-mcfadyen"]["surname"], by["hugh-mcfadyen"]["riding"],
                          by["hugh-mcfadyen"]["party"]), ("McFadyen", "Fort Whyte", "PC"))
        self.assertEqual(by["diane-mcgifford"]["surname"], "McGifford")
        self.assertEqual((by["nancy-allan"]["party"], by["nancy-allan"]["riding"], by["nancy-allan"]["hon"]),
                         ("NDP", "St. Vital", True))
        self.assertEqual(by["gord-mackintosh"]["surname"], "Mackintosh")
        self.assertEqual(by["kerri-irvin-ross"]["surname"], "Irvin-Ross")
        self.assertEqual(by["jon-gerrard"]["party"], "Lib.")
        self.assertEqual(sorted({m["party"] for m in members}), ["Lib.", "NDP", "PC"])

    def test_a_total_without_its_dot_leader_and_a_bare_nil(self):
        # 3 June 2010: "WOWCHUK 49" ends the YEA list, a bare "0" is the NAY
        # list; read before as "unexpected line in a name list".
        date = "2010-06-03"
        divisions, voices, titles, expected = mb.parse_vp(fx("mb_vp_100603.txt"))
        self.assertEqual(mb.printed_date(fx("mb_vp_100603.txt")), date)
        self.assertEqual((expected, len(divisions)), (1, 1))
        d = divisions[0]
        self.assertEqual((d["yeas"], d["nays"], d["nay_labels"], d["problem"]), (49, 0, [], None))
        self.assertEqual(d["yea_labels"][-1], "WOWCHUK")
        conn = conn_from_cover("mb_cover_100326.txt", date, 39)
        votes, ok, note = mb.resolve_division(d, pn.Resolver.from_conn(conn, "mb"), date, 39)
        self.assertTrue(ok, note)
        by = {v["member_key"]: v for v in votes}
        self.assertEqual((by["hugh-mcfadyen"]["position"], by["hugh-mcfadyen"]["party_at_vote"]),
                         ("Yea", "PC"))
        self.assertEqual(by["greg-selinger"]["party_at_vote"], "NDP")

    def test_a_bare_number_inside_a_list_is_not_a_total(self):
        # a page number between names is furniture; only a bare 0 opening an
        # empty list is the nil total
        divisions = mb.parse_vp("It was agreed to, on the following division:\nYEA\nALLAN\n243\n"
                                "ASHTON ........ 2\nNAY\n0\n")[0]
        self.assertEqual((divisions[0]["yea_labels"], divisions[0]["yeas"], divisions[0]["nays"]),
                         (["ALLAN", "ASHTON"], 2, 0))

    def test_a_cover_read_by_an_older_parser_is_read_again_when_its_sitting_is_owed(self):
        conn = db.init_db(db.connect(":memory:"))
        date, url = "2010-03-26", "https://www.gov.mb.ca/legislature/hansard/39th_4th/hansardpdf/21.pdf"
        # what the old parser left: the two Liberals only
        for key, given, sur, riding in (("jon-gerrard", "Jon", "Gerrard", "River Heights"),
                                        ("kevin-lamoureux", "Kevin", "Lamoureux", "Inkster")):
            ps.upsert_member(conn, "mb", key, name=given + " " + sur, surname=sur, given=given)
            ps.extend_term(conn, "mb", key, 39, "Lib.", riding, date, "hansard-cover")
        client = _Client({url: "%PDF-h"})
        ctx = Context(conn, client, "mb", log=lambda *a: None)
        pdf = mb.pdf_text
        mb.pdf_text = lambda raw, pages=None: fx("mb_cover_100326.txt")
        try:
            self.assertEqual(mb.roster_for_day(ctx, 39, date, {date: [url]}), 57)
            # a full cover is not fetched again for a clean sitting...
            self.assertEqual(mb.roster_for_day(ctx, 39, date, {date: [url]}), 57)
            self.assertEqual(client.asked.count(url), 1)
            # ...but is for an owed one
            mb.roster_for_day(ctx, 39, date, {date: [url]}, owed=True)
            self.assertEqual(client.asked.count(url), 2)
        finally:
            mb.pdf_text = pdf
        self.assertIsNotNone(pn.Resolver.from_conn(conn, "mb").resolve("MCFADYEN", date, 39)[0])


class FortiethLegislatureTests(unittest.TestCase):
    """2011-2016 layouts the 2010 backfill met (2 October 2026)."""

    def test_an_unclosed_calendar_cell_does_not_swallow_the_next_day(self):
        # 16 April 2013's cell has no </td>: Volume 24 was filed under the
        # 16th and the 17th's division had "no Hansard listed".
        base = "https://www.gov.mb.ca/legislature/hansard/40th_2nd/40th_2nd.html"
        h = mb.list_hansard(fx("mb_hansard_40_2.html"), base)
        self.assertEqual(h["2013-04-16"], ["https://www.gov.mb.ca/legislature/hansard/40th_2nd/hansardpdf/23.pdf"])
        self.assertEqual(h["2013-04-17"], ["https://www.gov.mb.ca/legislature/hansard/40th_2nd/hansardpdf/24.pdf"])

    def test_a_roll_call_under_on_division_is_announced(self):
        # 19 April 2012: "It was agreed to, on division." then a full YEA/NAY
        # roll call with its totals; the count check said 1 announced, 2 read.
        text = fx("mb_vp_120419.txt")
        divisions = mb.parse_vp(text)[0]
        self.assertEqual((mb.expected_divisions(text), len(divisions)), (2, 2))
        self.assertEqual([(d["yeas"], d["nays"], d["vote_on"]) for d in divisions],
                         [(19, 35, "amendment"), (36, 19, "motion")])
        self.assertEqual(divisions[1]["result"], "It was agreed to, on division")
        self.assertEqual(divisions[0]["result"], "It was negatived, on the following division")
        self.assertIn("MCFADYEN", divisions[1]["nay_labels"])

    def test_a_letter_spaced_phrase_is_still_counted(self):
        # 29 April 2013 prints "on th e / following division"
        text = fx("mb_vp_130429.txt")
        self.assertEqual((mb.expected_divisions(text), len(mb.parse_vp(text)[0])), (2, 2))

    def test_a_phrase_printed_twice_running_is_one_announcement(self):
        # 11 June 2012: "on the following divisi on, on the following division:"
        text = fx("mb_vp_120611.txt")
        divisions = mb.parse_vp(text)[0]
        self.assertEqual((mb.expected_divisions(text), len(divisions)), (2, 2))
        self.assertEqual([(d["yeas"], d["nays"]) for d in divisions], [(32, 19), (20, 30)])

    def test_on_division_without_a_roll_call_is_not_a_recorded_division(self):
        text = "And the Question being put. It was agreed to, on division.\n\nThe Bill was read.\n"
        self.assertEqual(mb.expected_divisions(text), 0)

    def test_a_misprinted_total_still_fails_the_tally(self):
        # 5 December 2013, the fourth division (Bill 27 third reading): the
        # V&P prints "WISHART ... 18" under 17 Nay names; Hansard (17b.pdf
        # p. 705) gives "Yeas 32, Nays 17" with the same 17. A record error:
        # config/prov_known_gaps.yaml, never a loosened check.
        divisions = mb.parse_vp(fx("mb_vp_131205.txt"))[0]
        self.assertEqual(len(divisions), 5)
        d = divisions[3]
        self.assertEqual((d["yeas"], len(d["yea_labels"]), d["nays"], len(d["nay_labels"])), (32, 32, 18, 17))
        self.assertNotIn("GERRARD", d["nay_labels"])
        _votes, ok, note = mb.resolve_division(d, pn.Resolver({}, []), "2013-12-05", 40)
        self.assertFalse(ok)
        self.assertIn("Nay: 17 name(s) read, 18 printed", note)


class UnheadedYeaTests(unittest.TestCase):
    """The record sometimes prints no "YEA" header at all (it is not in the
    PDF's text): the names follow "on the following division:" directly and
    only the NAY header follows the first total."""

    def test_24_may_2018_second_division_bill_229(self):
        text = fx("mb_vp_180524.txt")
        divisions = mb.parse_vp(text)[0]
        self.assertEqual((mb.expected_divisions(text), len(divisions)), (2, 2))
        d = divisions[1]
        self.assertEqual((d["yeas"], d["nays"], d["bill_number"], d["stage"], d["problem"]),
                         (15, 30, "229", "Second Reading", None))
        self.assertEqual((d["yea_labels"][0], d["nay_labels"][-1]), ("ALLUM", "YAKIMOSKI"))

    def test_15_march_2019_first_reading_45_0(self):
        text = fx("mb_vp_190315.txt")
        divisions = mb.parse_vp(text)[0]
        self.assertEqual((mb.expected_divisions(text), len(divisions)), (1, 1))
        d = divisions[0]
        self.assertEqual((d["yeas"], len(d["yea_labels"]), d["nays"], d["nay_labels"]), (45, 45, 0, []))

    def test_names_after_the_phrase_still_need_the_nay_header(self):
        text = "It was negatived, on the following division:\nALLUM\nWIEBE ........ 2\n"
        d = mb.parse_vp(text)[0][0]
        self.assertEqual(d["problem"], "no NAY list after the YEA list")

    def test_a_name_line_elsewhere_is_not_a_list(self):
        text = "And the Question being put. It was agreed to.\nWIEBE\nNAY\n"
        self.assertEqual(mb.parse_vp(text)[0], [])


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.conn = conn_from_cover("mb_cover_211014.txt", DATE, 42)
        self.r = pn.Resolver.from_conn(self.conn, "mb")

    def test_bill_207_second_reading_negatived_20_30(self):
        text = fx("mb_vp_211014.txt")
        self.assertEqual(mb.printed_date(text), DATE)
        divisions, voices, titles, expected = mb.parse_vp(text)
        self.assertEqual((expected, len(divisions)), (2, 2))
        self.assertEqual(titles["207"], "The Abortion Protest Buffer Zone Act")
        d = divisions[0]
        self.assertEqual((d["yeas"], d["nays"], d["stage"], d["bill_number"], d["result"]),
                         (20, 30, "Second Reading", "207", "It was negatived, on the following division"))
        votes, ok, note = mb.resolve_division(d, self.r, DATE, 42)
        self.assertTrue(ok, note)
        by = {v["member_key"]: v for v in votes}
        for key in ("nahanni-fontaine", "wab-kinew", "uzoma-asagwara"):
            self.assertEqual((by[key]["position"], by[key]["party_at_vote"]), ("Yea", "NDP"))
        for key in ("cathy-cox", "cliff-cullen", "blaine-pedersen"):
            self.assertEqual((by[key]["position"], by[key]["party_at_vote"]), ("Nay", "PC"))
        self.assertEqual(by["andrew-smith"]["raw_label"], "SMITH (Lagimodière)")
        self.assertEqual(by["andrew-smith"]["how"], "surname+riding")
        self.assertEqual(by["bob-lagasse"]["raw_label"], "LAGASSÉ")
        self.assertNotIn("bernadette-smith", by)            # did not vote
        self.assertNotIn("heather-stefanson", by)
        # the second division is Bill 232, 50-0, with a printed nil list
        d2 = divisions[1]
        self.assertEqual((d2["yeas"], d2["nays"], d2["nay_labels"], d2["stage"], d2["bill_number"]),
                         (50, 0, [], "Third Reading", "232"))
        self.assertTrue(mb.resolve_division(d2, self.r, DATE, 42)[1])
        self.assertEqual(voices, [])     # 232 had a recorded division, so no voice row

    def test_bill_207_is_on_our_ground_by_its_text_and_key(self):
        tax, wl = pc.load_taxonomy(), pc.load_watchlist("mb")
        text = mb.bill_text(fx("mb_bill_207.html"))
        self.assertIn("abortion services", text)
        res = pc.classify(tax, wl, "mb", title="The Abortion Protest Buffer Zone Act", texts=[text])
        self.assertIn(1, res.areas)
        self.assertEqual(pc.classify(tax, wl, "mb", title="x", bill_key="mb-42-3/207").tier, 1)

    def test_a_shared_surname_without_its_riding_is_a_gap_with_a_null(self):
        d = {"yeas": 1, "nays": 0, "yea_labels": ["SMITH"], "nay_labels": [], "problem": None}
        votes, ok, note = mb.resolve_division(d, self.r, DATE, 42)
        self.assertFalse(ok)
        self.assertIsNone(votes[0]["member_key"])
        self.assertIn("ambiguous", votes[0]["how"])

    def test_a_term_seen_on_another_day_does_not_cover_this_one(self):
        conn = conn_from_cover("mb_cover_211014.txt", "2021-10-13", 42)
        r = pn.Resolver.from_conn(conn, "mb")
        self.assertIsNone(r.resolve("KINEW", DATE, 42)[0])


class AyeLayoutTests(unittest.TestCase):
    """The 43rd Legislature prints AYE, not YEA."""

    def test_bill_43_third_reading_33_16_and_two_voice_readings(self):
        conn = conn_from_cover("mb_cover_250602.txt", "2025-06-02", 43)
        r = pn.Resolver.from_conn(conn, "mb")
        divisions, voices, titles, expected = mb.parse_vp(fx("mb_vp_250602.txt"))
        self.assertEqual((expected, len(divisions)), (1, 1))
        d = divisions[0]
        self.assertEqual((d["yeas"], d["nays"], d["bill_number"], d["stage"]), (33, 16, "43", "Third Reading"))
        votes, ok, note = mb.resolve_division(d, r, "2025-06-02", 43)
        self.assertTrue(ok, note)
        by = {v["member_key"]: v for v in votes}
        self.assertEqual((by["wab-kinew"]["position"], by["wab-kinew"]["party_at_vote"]), ("Yea", "NDP"))
        self.assertEqual((by["kelvin-goertzen"]["position"], by["kelvin-goertzen"]["party_at_vote"]), ("Nay", "PC"))
        self.assertEqual(by["jelynn-dela-cruz"]["raw_label"], "DELA CRUZ")
        self.assertEqual(sorted((v["bill_number"], v["stage"]) for v in voices),
                         [("35", "Third Reading"), ("36", "Third Reading")])
        self.assertTrue(all(v["result"] == "It was agreed to" for v in voices))


class BillListTests(unittest.TestCase):
    def test_bills_page(self):
        base = "https://web2.gov.mb.ca/bills/42-3/index.php"
        items = {b["number"]: b for b in mb.parse_bill_list(fx("mb_bills_42_3.html"), base)}
        self.assertEqual(items["207"]["text_url"], "https://web2.gov.mb.ca/bills/42-3/b207e.php")
        self.assertEqual(items["207"]["title"], "The Abortion Protest Buffer Zone Act")
        self.assertEqual(items["207"]["is_government"], 0)
        self.assertEqual(items["2"]["is_government"], 1)
        self.assertIsNone(items["1"]["text_url"])               # a formal bill, not printed


class RobotsTests(unittest.TestCase):
    def test_the_ai_crawler_list_does_not_name_us_and_star_rules_hold(self):
        rules = ("User-agent: GPTBot\nUser-agent: ClaudeBot\nUser-agent: anthropic-ai\nDisallow: /\n\n"
                 "User-agent: *\nDisallow: /_*\nDisallow: /sao/\n")
        r = Robots(rules)
        ua = "CitizenGO-ParlMonitor/1.0 (contact: x)"
        vp = "https://www.gov.mb.ca/legislature/business/42nd/3rd/votes_082.pdf"
        self.assertTrue(r.can_fetch(ua, vp))
        self.assertFalse(r.can_fetch("ClaudeBot", vp))
        self.assertFalse(r.can_fetch(ua, "https://www.gov.mb.ca/sao/x"))
        self.assertFalse(r.can_fetch(ua, "https://www.gov.mb.ca/_private"))

    def test_if_manitoba_names_us_nothing_is_read(self):
        r = Robots("User-agent: CitizenGO-ParlMonitor\nDisallow: /\n\nUser-agent: *\nDisallow: /sao/\n")
        self.assertFalse(r.can_fetch("CitizenGO-ParlMonitor/1.0 (contact: x)",
                                     "https://www.gov.mb.ca/legislature/business/votes_proceedings.html"))


class _Client:
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 1.1

    def __init__(self, pages):
        self.pages = pages
        self.asked = []

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.pages[url]

    def get_bytes(self, url, feed, slug, archive=True):
        return self.get_text(url, feed, slug).encode()


class CollectTests(unittest.TestCase):
    VP = "https://www.gov.mb.ca/legislature/business/42nd/3rd/votes_082.pdf"
    H = "https://www.gov.mb.ca/legislature/hansard/42nd_3rd/hansardpdf/82a.pdf"

    def setUp(self):
        self._pdf = mb.pdf_text
        texts = {b"%PDF-vp": fx("mb_vp_211014.txt"), b"%PDF-h": fx("mb_cover_211014.txt")}
        mb.pdf_text = lambda raw, pages=None: texts[raw]

    def tearDown(self):
        mb.pdf_text = self._pdf

    def test_the_proof_lands_in_the_store_with_its_day_roster(self):
        conn = db.init_db(db.connect(":memory:"))
        client = _Client({
            mb.VP_SESSIONS: fx("mb_vp_sessions.html"), VP_BASE: fx("mb_vp_42_3.html"),
            mb.HANSARD_SESSIONS: fx("mb_hansard_sessions.html"), HANSARD_BASE: fx("mb_hansard_42_3.html"),
            mb.BILL_SESSIONS: fx("mb_bill_sessions.html"),
            "https://web2.gov.mb.ca/bills/42-3/index.php": fx("mb_bills_42_3.html"),
            "https://web2.gov.mb.ca/bills/42-3/b207e.php": fx("mb_bill_207.html"),
            "https://web2.gov.mb.ca/bills/42-3/b002e.php": '<p class="chapter">Bill 2</p><p>Taxes.</p><!--end content-->',
            "https://web2.gov.mb.ca/bills/42-3/b232e.php": '<p class="chapter">Bill 232</p><p>A day.</p><!--end content-->',
            self.VP: "%PDF-vp", self.H: "%PDF-h"})
        ctx = Context(conn, client, "mb", since=DATE, until=DATE, log=lambda *a: None)
        stats = mb.collect(ctx, session="42-3")
        self.assertEqual((stats["records_read"], stats["divisions"], stats["tally_gaps"]), (1, 2, 0))
        row = conn.execute("SELECT division_key, bill_key, stage, yeas, nays, positions_ok, areas, tier "
                           "FROM prov_divisions WHERE bill_key='mb-42-3/207'").fetchone()
        self.assertEqual(tuple(row), ("mb-42-3-2021-10-14-1", "mb-42-3/207", "Second Reading", 20, 30, 1,
                                      "[1]", 1))
        bill = conn.execute("SELECT text_read, areas FROM prov_bills WHERE bill_key='mb-42-3/207'").fetchone()
        self.assertEqual(tuple(bill), (1, "[1]"))
        fontaine = conn.execute(
            "SELECT position, party_at_vote FROM prov_votes WHERE member_key='nahanni-fontaine' "
            "AND division_key='mb-42-3-2021-10-14-1'").fetchone()
        self.assertEqual(tuple(fontaine), ("Yea", "NDP"))
        terms = conn.execute("SELECT start, end, party FROM prov_member_terms WHERE member_key='wab-kinew'").fetchall()
        self.assertEqual([tuple(t) for t in terms], [(DATE, DATE, "NDP")])
        self.assertNotIn("https://www.gov.mb.ca/legislature/business/42nd/3rd/votes_029.pdf", client.asked)
        self.assertEqual(ctx.gaps, [])
        # a second run reads nothing again: the record was read cleanly
        stats = mb.collect(ctx, session="42-3", bills=False)
        self.assertEqual(stats["records_read"], 0)

    def test_without_the_days_hansard_the_division_is_a_gap_never_a_guess(self):
        conn = db.init_db(db.connect(":memory:"))
        client = _Client({mb.VP_SESSIONS: fx("mb_vp_sessions.html"), VP_BASE: fx("mb_vp_42_3.html"),
                          mb.HANSARD_SESSIONS: fx("mb_hansard_sessions.html"), self.VP: "%PDF-vp"})
        ctx = Context(conn, client, "mb", since=DATE, until=DATE, log=lambda *a: None)
        stats = mb.collect(ctx, session="42-3", bills=False)
        self.assertEqual(stats["tally_gaps"], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_votes WHERE member_key IS NOT NULL").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "gap")


class CopiedRecordTests(unittest.TestCase):
    """42-4 lists votes_041.pdf for 25 April 2022, but the file is V&P No. 42
    of the 26th, which votes_042.pdf is listed for. The 25th's own record is
    not served (Hansard No. 41 has three recorded votes that day): a gap."""
    BASE = "https://www.gov.mb.ca/legislature/business/42nd/42nd_4th.html"
    V41 = "https://www.gov.mb.ca/legislature/business/42nd/4th/votes_041.pdf"
    V42 = "https://www.gov.mb.ca/legislature/business/42nd/4th/votes_042.pdf"

    def setUp(self):
        self._pdf = mb.pdf_text
        mb.pdf_text = lambda raw, pages=None: fx("mb_vp_42_4_votes_041_head.txt")

    def tearDown(self):
        mb.pdf_text = self._pdf

    def test_the_listing(self):
        recs = mb.list_records(fx("mb_vp_42_4_april.html"), self.BASE)
        self.assertIn(("2022-04-25", self.V41), recs)
        self.assertIn(("2022-04-26", self.V42), recs)

    def _ctx(self):
        conn = db.init_db(db.connect(":memory:"))
        ctx = Context(conn, _Client({self.V41: "%PDF-x", self.V42: "%PDF-x"}), "mb", log=lambda *a: None)
        ctx.mb_listed = {d: u for d, u in mb.list_records(fx("mb_vp_42_4_april.html"), self.BASE) if d}
        return conn, ctx

    def test_a_copy_of_another_listed_day_is_a_gap_and_stores_nothing_under_that_day(self):
        conn, ctx = self._ctx()
        self.assertEqual(mb.read_sitting(ctx, 42, 4, "2022-04-25", self.V41, {}, []), (0, 1))
        self.assertIn("mb 2022-04-25: the record listed for the day", ctx.gaps[0])
        self.assertIn("the day's own V&P is not served", ctx.gaps[0])
        self.assertEqual([tuple(r) for r in conn.execute("SELECT sitting_key, status FROM prov_sittings")],
                         [("mb-42-4-2022-04-25", "gap")])
        self.assertFalse(ps.sitting_done(conn, self.V41))      # still owed

    def test_a_misplaced_link_whose_day_is_not_listed_is_read(self):
        # 42-5 lists votes_005.pdf under 7 November 2022 and it prints the
        # 21st, which nothing else is listed for: the record's date is used.
        conn, ctx = self._ctx()
        ctx.mb_listed.pop("2022-04-26")
        ctx.tax = pc.load_taxonomy()
        self.assertEqual(mb.read_sitting(ctx, 42, 4, "2022-04-25", self.V41, {}, pc.load_watchlist("mb")), (0, 0))
        self.assertEqual(ctx.gaps, [])
        self.assertEqual([tuple(r) for r in conn.execute("SELECT sitting_key FROM prov_sittings")],
                         [("mb-42-4-2022-04-26",)])


if __name__ == "__main__":
    unittest.main()
