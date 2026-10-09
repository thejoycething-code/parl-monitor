"""US Congress bills, House roll calls and members (tools/us_rollcalls.py). No network."""

import importlib.util
import io
import json
import os
import sqlite3
import sys
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, us_store  # noqa: E402
from src.http import FetchError  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "us_rollcalls", os.path.join(ROOT, "tools", "us_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


usr = _load()
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = usr.empty_watchlist()

ERROR_PAGE = b'<xml>Error sanitizing file "roll363.xml". Please try again.</xml>'


def roll_xml(roll, legis="H R 8800", question="On Agreeing to the Amendment", desc="",
             author="Roy of Texas Amendment No. 1", date="15-Jul-2026", session="2nd",
             votes=(("A000370", "Adams", "D", "NC", "No"), ("S001214", "Steube", "R", "FL", "Aye"))):
    recs = "".join(
        '<recorded-vote><legislator name-id="{0}" sort-field="{1}" unaccented-name="{1}" '
        'party="{2}" state="{3}" role="legislator">{1}</legislator><vote>{4}</vote>'
        '</recorded-vote>'.format(*v) for v in votes)
    return ('<?xml version="1.0" encoding="utf-8"?><rollcall-vote><vote-metadata>'
            '<majority>R</majority><congress>119</congress><session>{session}</session>'
            '<chamber>U.S. House of Representatives</chamber><rollcall-num>{roll}</rollcall-num>'
            '<legis-num>{legis}</legis-num><vote-question>{question}</vote-question>'
            '<amendment-num>1</amendment-num><amendment-author>{author}</amendment-author>'
            '<vote-type>RECORDED VOTE</vote-type><vote-result>Failed</vote-result>'
            '<action-date>{date}</action-date><vote-desc>{desc}</vote-desc>'
            '<vote-totals><totals-by-vote><total-stub>Totals</total-stub><yea-total>127</yea-total>'
            '<nay-total>291</nay-total><present-total>0</present-total>'
            '<not-voting-total>18</not-voting-total></totals-by-vote></vote-totals>'
            '</vote-metadata><vote-data>{recs}</vote-data></rollcall-vote>').format(
                session=session, roll=roll, legis=legis, question=question, author=author,
                date=date, desc=desc, recs=recs).encode("utf-8")


def bill_xml(btype="HR", number=15, title="Equality Act", subjects=(), summary="",
             cosponsors=(), law=None, policy="Civil Rights and Liberties, Minority Issues"):
    cos = "".join(
        "<item><bioguideId>{0}</bioguideId><fullName>Rep. {1} [D-CA-1]</fullName>"
        "<party>D</party><state>CA</state><district>1</district>"
        "<sponsorshipDate>2025-03-01</sponsorshipDate>{2}"
        "<isOriginalCosponsor>True</isOriginalCosponsor></item>".format(
            bid, name, "<sponsorshipWithdrawnDate>2025-05-01</sponsorshipWithdrawnDate>"
            if withdrawn else "") for bid, name, withdrawn in cosponsors)
    subj = "".join("<item><name>{0}</name></item>".format(s) for s in subjects)
    laws = ("<laws><item><type>Public Law</type><number>{0}</number></item></laws>".format(law)
            if law else "")
    return ("<billStatus><bill><number>{number}</number><type>{btype}</type>"
            "<congress>119</congress><introducedDate>2025-04-29</introducedDate>"
            "<updateDate>2026-09-22T18:06:17Z</updateDate>"
            "<sponsors><item><bioguideId>T000468</bioguideId>"
            "<fullName>Rep. Takano, Mark [D-CA-39]</fullName><party>D</party><state>CA</state>"
            "<district>39</district></item></sponsors>"
            "<cosponsors>{cos}</cosponsors><policyArea><name>{policy}</name></policyArea>"
            "<subjects><legislativeSubjects>{subj}</legislativeSubjects></subjects>"
            "<summaries><summary><actionDate>2025-04-29</actionDate>"
            "<updateDate>2025-05-01T00:00:00Z</updateDate><text>&lt;p&gt;old&lt;/p&gt;</text></summary>"
            "<summary><actionDate>2025-06-01</actionDate><updateDate>2025-07-01T00:00:00Z</updateDate>"
            "<text>&lt;p&gt;&lt;strong&gt;{title}&lt;/strong&gt;&lt;/p&gt;&lt;p&gt;{summary}&lt;/p&gt;</text>"
            "</summary></summaries><title>{title}</title>"
            "<titles><item><title>{title}</title></item><item><title>{title} of 2025</title></item>"
            "</titles>{laws}<latestAction><actionDate>2025-04-29</actionDate>"
            "<text>Referred to the Committee on the Judiciary.</text></latestAction>"
            "</bill></billStatus>").format(number=number, btype=btype, cos=cos, policy=policy,
                                           subj=subj, title=title, summary=summary,
                                           laws=laws).encode("utf-8")


class FakeClient:
    def __init__(self, pages=None, json_pages=None):
        self.pages = pages or {}
        self.json_pages = json_pages or {}
        self.asked = []

    def get_bytes(self, url, feed, slug, archive=True, **kw):
        self.asked.append(url)
        page = self.pages.get(url, ERROR_PAGE)
        if isinstance(page, Exception):
            raise page
        return page

    def get_json(self, url, feed, slug, archive=True, **kw):
        return self.json_pages[url]


def store():
    return db.init_db(sqlite3.connect(":memory:"))


class ParsingTests(unittest.TestCase):
    def test_a_roll_call_parses_with_positions_and_party_at_the_vote(self):
        d = usr.parse_roll(roll_xml(240))
        self.assertEqual((d["congress"], d["session"], d["roll"], d["date"]), (119, 2, 240, "2026-07-15"))
        self.assertEqual((d["yeas"], d["nays"], d["not_voting"]), (127, 291, 18))
        self.assertEqual(d["amendment_author"], "Roy of Texas Amendment No. 1")
        # Aye/No on a recorded vote are Yea/Nay on a yea-and-nay vote: one vocabulary.
        self.assertEqual([(p["bioguide"], p["party"], p["position"]) for p in d["positions"]],
                         [("A000370", "D", "Nay"), ("S001214", "R", "Yea")])

    def test_the_clerks_200_error_page_is_not_a_vote(self):
        self.assertIsNone(usr.parse_roll(ERROR_PAGE))
        self.assertIsNone(usr.parse_roll(b"<html>not xml at all"))

    def test_legis_num_to_bill_key(self):
        cases = {"H R 8800": "119/hr/8800", "H RES 580": "119/hres/580",
                 "H CON RES 23": "119/hconres/23", "H J RES 127": "119/hjres/127",
                 "S 1071": "119/s/1071", "S J RES 9": "119/sjres/9", "S CON RES 11": "119/sconres/11",
                 "QUORUM": None, "ADJOURN": None, "": None, None: None}
        for legis, want in cases.items():
            self.assertEqual(usr.legis_bill_key(legis, 119), want, legis)

    def test_congress_years(self):
        self.assertEqual(usr.congress_years(119), (2025, 2026))
        self.assertEqual(usr.congress_years(120), (2027, 2028))

    def test_billstatus_takes_the_latest_summary_and_counts_current_cosponsors(self):
        b = usr.parse_billstatus(bill_xml(summary="Adds gender identity.", subjects=("Civil rights",),
                                          cosponsors=(("P000197", "Pelosi, Nancy", False),
                                                      ("X000001", "Gone, Someone", True)),
                                          law="119-12"))
        self.assertEqual(b["summary"], "Equality Act Adds gender identity.")
        self.assertEqual(b["titles"], ["Equality Act of 2025"])
        self.assertEqual(b["subjects"], ["Civil rights"])
        self.assertEqual(b["law"], "Public Law 119-12")
        conn = store()
        usr.store_bill(conn, b, usr.classify_bill(TAX, WL, b), "2026-10-09")
        self.assertEqual(conn.execute("SELECT cosponsors FROM us_bills").fetchone()[0], 1)
        # The withdrawal is a public reversal: kept, dated, not deleted.
        self.assertEqual(conn.execute("SELECT withdrawn_at FROM us_cosponsors WHERE "
                                      "bioguide='X000001'").fetchone()[0], "2025-05-01")

    def test_display_name(self):
        self.assertEqual(usr.display_name("Rep. Steube, W. Gregory [R-FL-17]"), "W. Gregory Steube")
        self.assertEqual(usr.display_name("Sen. Lee, Mike [R-UT]"), "Mike Lee")
        self.assertIsNone(usr.display_name(None))


class ClassificationTests(unittest.TestCase):
    def test_the_us_equality_act_is_ours_by_key_and_its_namesakes_are_not(self):
        eq = usr.parse_billstatus(bill_xml())
        refund = usr.parse_billstatus(bill_xml(btype="S", number=2197, title="Refund Equality Act of 2025",
                                               policy="Taxation"))
        self.assertEqual(usr.classify_bill(TAX, WL, eq).issue_areas, [5, 8])
        self.assertEqual(usr.classify_bill(TAX, WL, refund).issue_areas, [])

    def test_crs_subjects_and_summary_are_read_not_just_the_title(self):
        b = usr.parse_billstatus(bill_xml(btype="S", number=3667, title="Life Act",
                                          summary="Declares that the right to life begins at "
                                                  "fertilization, establishing fetal personhood."))
        self.assertIn(1, usr.classify_bill(TAX, WL, b).issue_areas)

    def test_a_vote_inherits_its_bills_areas_and_keeps_its_own_apart(self):
        conn = store()
        b = usr.parse_billstatus(bill_xml(btype="HR", number=8800, title="National Defense Authorization Act",
                                          summary="Prohibits the Hyde Amendment from lapsing."))
        usr.store_bill(conn, b, usr.classify_bill(TAX, WL, b), "2026-10-09")
        key, areas = usr.store_division(conn, usr.parse_roll(roll_xml(240)), TAX, WL, "2026-10-09")
        row = conn.execute("SELECT bill_key, own_areas, areas FROM us_divisions").fetchone()
        self.assertEqual(row[0], "119/hr/8800")
        self.assertEqual(json.loads(row[1]), [])
        self.assertEqual(json.loads(row[2]), [1])
        self.assertEqual(key, "house-119-2-240")

    def test_reclassify_rederives_bills_then_divisions(self):
        conn = store()
        b = usr.parse_billstatus(bill_xml(btype="HR", number=8800, title="Some Act",
                                          summary="Planned Parenthood funding."))
        usr.store_bill(conn, b, usr.classify_bill(TAX, WL, b), "2026-10-09")
        usr.store_division(conn, usr.parse_roll(roll_xml(240)), TAX, WL, "2026-10-09")
        conn.execute("UPDATE us_bills SET areas='[]'")
        conn.execute("UPDATE us_divisions SET areas='[]'")
        self.assertEqual(usr.reclassify(conn, TAX, log=lambda *a: None), (1, 1))
        self.assertEqual(conn.execute("SELECT areas FROM us_divisions").fetchone()[0], "[1]")


class PullRollsTests(unittest.TestCase):
    URL = staticmethod(lambda year, n: usr.ROLL.format(year, n))

    def test_the_walk_stops_on_misses_and_reports_a_hole(self):
        pages = {self.URL(2025, 1): roll_xml(1, session="1st", date="3-Jan-2025"),
                 self.URL(2025, 2): roll_xml(2, session="1st", date="3-Jan-2025"),
                 self.URL(2025, 4): roll_xml(4, session="1st", date="4-Jan-2025")}
        conn, client = store(), FakeClient(pages)
        stored, ours, gaps = usr.pull_rolls(conn, client, "2025-06-01", tax=TAX, wl=WL,
                                            log=lambda *a: None)
        self.assertEqual((stored, gaps), (3, 1))
        self.assertIn("rolls 3-3 answered with no vote",
                      conn.execute("SELECT detail FROM gaps").fetchone()[0])
        # 2026 is in the future on this date and is not asked for.
        self.assertFalse(any("/2026/" in u for u in client.asked))

    def test_a_second_run_resumes_after_the_last_stored_roll(self):
        conn = store()
        usr.pull_rolls(conn, FakeClient({self.URL(2025, 1): roll_xml(1, session="1st")}),
                       "2025-06-01", tax=TAX, wl=WL, log=lambda *a: None)
        client = FakeClient({self.URL(2025, 2): roll_xml(2, session="1st")})
        stored, _o, _g = usr.pull_rolls(conn, client, "2025-06-01", tax=TAX, wl=WL,
                                        log=lambda *a: None)
        self.assertEqual(stored, 1)
        self.assertEqual(client.asked[0], self.URL(2025, 2))

    def test_an_http_failure_is_a_gap_and_stops_the_year(self):
        conn = store()
        client = FakeClient({self.URL(2025, 1): FetchError(usr.ROLL.format(2025, 1), usr.FEED, "x", 4, "HTTP 503")})
        stored, _o, gaps = usr.pull_rolls(conn, client, "2025-06-01", tax=TAX, wl=WL,
                                          log=lambda *a: None)
        self.assertEqual((stored, gaps), (0, 1))
        self.assertEqual(client.asked, [self.URL(2025, 1)])

    def test_every_position_is_stored_with_party_at_the_vote(self):
        conn = store()
        usr.pull_rolls(conn, FakeClient({self.URL(2025, 1): roll_xml(1, session="1st")}),
                       "2025-06-01", tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual(conn.execute("SELECT bioguide, position, party FROM us_votes "
                                      "ORDER BY bioguide").fetchall(),
                         [("A000370", "Nay", "D"), ("S001214", "Yea", "R")])


class PullBillsAndMembersTests(unittest.TestCase):
    def test_bills_come_from_the_bulk_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("BILLSTATUS-119hr15.xml", bill_xml())
            zf.writestr("BILLSTATUS-119hr16.xml", bill_xml(number=16, title="Bridges Act",
                                                           policy="Transportation"))
        url = usr.BILLSTATUS.format(119, "hr")
        conn = store()
        read, ours, gaps = usr.pull_bills(conn, FakeClient({url: buf.getvalue()}), "2026-10-09",
                                          types=("hr",), tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual((read, ours, gaps), (2, 1, 0))

    def test_a_missing_zip_is_a_gap_not_an_empty_congress(self):
        conn = store()
        read, ours, gaps = usr.pull_bills(conn, FakeClient(), "2026-10-09", types=("hr",),
                                          tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual((read, gaps), (0, 1))

    def test_the_crosswalk_name_is_never_overwritten_by_a_surname(self):
        conn = store()
        records = [{"id": {"bioguide": "A000370", "lis": None},
                    "name": {"official_full": "Alma S. Adams"},
                    "terms": [{"type": "rep", "party": "Democrat", "state": "NC", "district": 12,
                               "start": "2025-01-03"}]}]
        usr.pull_members(conn, FakeClient(json_pages={usr.MEMBERS: records}), "2026-10-09")
        usr.store_division(conn, usr.parse_roll(roll_xml(1, votes=(
            ("A000370", "Adams", "D", "NC", "Aye"), ("G000001", "Gone", "R", "TX", "No")))),
            TAX, WL, "2026-10-09")
        names = dict(conn.execute("SELECT bioguide, name FROM us_members"))
        self.assertEqual(names["A000370"], "Alma S. Adams")
        # A member who has left is not in the crosswalk; the roll's surname is all there is.
        self.assertEqual(names["G000001"], "Gone")
        self.assertEqual(conn.execute("SELECT party, district, chamber FROM us_members "
                                      "WHERE bioguide='A000370'").fetchone(), ("D", "12", "house"))


class WatchlistTests(unittest.TestCase):
    def test_every_watchlist_key_is_well_formed(self):
        import re
        for key, (areas, why) in us_store.watchlist().items():
            self.assertRegex(key, r"^\d{3}/(hr|s|hres|sres|hjres|sjres|hconres|sconres)/\d+$")
            self.assertTrue(areas and why, key)
            self.assertTrue(all(isinstance(a, int) for a in areas), key)
        del re


if __name__ == "__main__":
    unittest.main()


FIX = os.path.join(ROOT, "tests", "fixtures", "us_senate")


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def senate_menu(*numbers, issue=""):
    return ("<vote_summary><congress>119</congress><session>1</session><votes>" +
            "".join("<vote><vote_number>{0:05d}</vote_number><issue>{1}</issue></vote>".format(n, issue)
                    for n in numbers) +
            "</votes></vote_summary>").encode("utf-8")


class SenateTests(unittest.TestCase):
    """Real files saved from senate.gov by the probe workflow, 9 October 2026."""

    def test_the_born_alive_cloture_vote_parses_and_finds_its_bill(self):
        d = usr.parse_senate_vote(fixture("vote_119_1_00011.xml"))
        self.assertEqual((d["chamber"], d["congress"], d["session"], d["roll"], d["date"]),
                         ("senate", 119, 1, 11, "2025-01-22"))
        self.assertEqual(usr.legis_bill_key(d["legis_num"], 119), "119/s/6")
        self.assertEqual((d["yeas"], d["nays"], d["vote_type"]), (52, 47, "3/5"))
        self.assertEqual(len(d["positions"]), 100)
        self.assertEqual({p["position"] for p in d["positions"]} - {"Yea", "Nay", "Not Voting"}, set())

    def test_senate_votes_classify_on_their_own_text(self):
        """The bill's long title travels in the vote file, so the vote is ours
        before the bill lends anything."""
        born_alive = usr.parse_senate_vote(fixture("vote_119_1_00011.xml"))
        sports = usr.parse_senate_vote(fixture("vote_119_1_00100.xml"))
        self.assertIn(1, usr.classify_division(TAX, WL, born_alive, [])[0].issue_areas)
        self.assertIn(5, usr.classify_division(TAX, WL, sports, [])[0].issue_areas)

    def test_a_nomination_has_no_bill(self):
        d = usr.parse_senate_vote(fixture("vote_119_1_00655.xml"))
        self.assertTrue(d["legis_num"].startswith("PN"))
        self.assertIsNone(usr.legis_bill_key(d["legis_num"], 119))
        self.assertEqual(d["result"], "Nomination Confirmed")

    def test_no_statement_of_purpose_is_not_text(self):
        d = usr.parse_senate_vote(fixture("vote_119_1_00648.xml"))
        self.assertNotIn(usr.NO_PURPOSE, d["description"])

    def test_the_menu_lists_every_vote(self):
        self.assertEqual(len(usr.parse_senate_menu(fixture("menu_119_1.xml"))), 659)
        self.assertEqual(usr.parse_senate_menu(b"<html>403</html>"), {})
        self.assertEqual(usr.parse_senate_menu(fixture("menu_119_1.xml"))[82], "S.Con.Res. 7")

    def test_pull_maps_senators_by_lis_id_and_never_guesses(self):
        conn = store()
        vote = usr.parse_senate_vote(fixture("vote_119_1_00011.xml"))
        lis = [p["lis_id"] for p in vote["positions"]]
        # The sitting crosswalk knows one senator; the historical one knows
        # all but the last; the last is known to nobody.
        conn.execute("INSERT INTO us_members (bioguide, lis_id) VALUES ('B000001', ?)", (lis[0],))
        history = [{"id": {"lis": x, "bioguide": "H{0:06d}".format(i)}}
                   for i, x in enumerate(lis[1:-1])]
        client = FakeClient({usr.SENATE_MENU.format(119, 1): senate_menu(11),
                             usr.SENATE_VOTE.format(119, 1, 11): fixture("vote_119_1_00011.xml")},
                            json_pages={usr.MEMBERS_HISTORICAL: history})
        stored, ours, gaps = usr.pull_senate(conn, client, "2025-06-01", tax=TAX, wl=WL,
                                             log=lambda *a: None)
        self.assertEqual((stored, ours, gaps), (1, 1, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM us_votes").fetchone()[0], 99)
        self.assertIn(lis[-1], conn.execute("SELECT detail FROM gaps").fetchone()[0])
        self.assertEqual(conn.execute("SELECT bioguide FROM us_votes WHERE bioguide='B000001'")
                         .fetchone()[0], "B000001")
        # A second run asks only for votes it does not hold.
        client.asked = []
        self.assertEqual(usr.pull_senate(conn, client, "2025-06-01", tax=TAX, wl=WL,
                                         log=lambda *a: None)[0], 0)
        self.assertEqual(client.asked, [usr.SENATE_MENU.format(119, 1)])

    def test_an_amendment_vote_takes_its_bill_from_the_menu(self):
        conn = store()
        blank = fixture("vote_119_1_00648.xml").replace(b"<document_name>S. 1071</document_name>",
                                                         b"<document_name></document_name>")
        client = FakeClient({usr.SENATE_MENU.format(119, 1): senate_menu(648, issue="S.Con.Res. 7"),
                             usr.SENATE_VOTE.format(119, 1, 648): blank},
                            json_pages={usr.MEMBERS_HISTORICAL: []})
        usr.pull_senate(conn, client, "2025-06-01", tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual(conn.execute("SELECT legis_num, bill_key FROM us_divisions").fetchone(),
                         ("S.Con.Res. 7", "119/sconres/7"))

    def test_a_refused_menu_is_a_gap_and_the_other_session_still_runs(self):
        conn = store()
        refused = FetchError(usr.SENATE_MENU.format(119, 1), usr.FEED, "x", 4, "HTTP 403")
        client = FakeClient({usr.SENATE_MENU.format(119, 1): refused,
                             usr.SENATE_MENU.format(119, 2): senate_menu()})
        stored, _o, gaps = usr.pull_senate(conn, client, "2026-10-09", tax=TAX, wl=WL,
                                           log=lambda *a: None)
        self.assertEqual((stored, gaps), (0, 1))
        self.assertIn(usr.SENATE_MENU.format(119, 2), client.asked)


class AmendmentTests(unittest.TestCase):
    """Phase 1b: what a House amendment vote was about, from Congress.gov."""

    def setUp(self):
        self.conn = store()
        b = usr.parse_billstatus(bill_xml(btype="HR", number=8800, title="Appropriations Act",
                                          summary="Continues the Hyde Amendment."))
        usr.store_bill(self.conn, b, usr.classify_bill(TAX, WL, b), "2026-10-09")
        usr.store_division(self.conn, usr.parse_roll(roll_xml(27)), TAX, WL, "2026-10-09")
        self.vote_url = usr.CG_HOUSE_VOTE.format(119, 2, 27)
        self.amd_url = usr.CG_AMENDMENT.format(119, "hamdt", 150)

    def client(self, purpose):
        vote = {"houseRollCallVote": {"amendmentType": "HAMDT", "amendmentNumber": "150"}}
        amd = {"amendment": {"description": "An amendment numbered 2 printed in House Report "
                                            "119-445 " + purpose, "purpose": "Amendment sought " + purpose}}
        return FakeClient({self.vote_url: json.dumps(vote).encode(),
                           self.amd_url: json.dumps(amd).encode()})

    def row(self):
        return self.conn.execute("SELECT amendment_key, amendment_text, own_areas, areas, "
                                 "amendment_checked FROM us_divisions").fetchone()

    def test_before_phase_1b_the_vote_borrows_the_bills_areas(self):
        self.assertEqual(json.loads(self.row()[3]), [1])

    def test_an_unrelated_amendment_stops_borrowing(self):
        usr.fill_amendments(self.conn, self.client("to prohibit funding for the National "
                                                   "Endowment for Democracy."),
                            "2026-10-09", "KEY", tax=TAX, wl=WL, log=lambda *a: None)
        key, text, own, areas, checked = self.row()
        self.assertEqual(key, "119/hamdt/150")
        self.assertIn("National Endowment for Democracy", text)
        self.assertEqual((json.loads(own), json.loads(areas), checked), ([], [], "2026-10-09"))

    def test_an_amendment_on_our_ground_is_ours_on_its_own_text(self):
        filled, ours, gaps = usr.fill_amendments(
            self.conn, self.client("to prohibit funds for Planned Parenthood."),
            "2026-10-09", "KEY", tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual((filled, ours, gaps), (1, 1, 0))
        self.assertEqual(json.loads(self.row()[2]), [1])

    def test_the_key_goes_in_a_header_never_the_url(self):
        seen = []
        client = self.client("x.")
        real = client.get_bytes

        def spy(url, feed, slug, archive=True, headers=None, **kw):
            seen.append((url, headers))
            return real(url, feed, slug, archive=archive)
        client.get_bytes = spy
        usr.fill_amendments(self.conn, client, "2026-10-09", "SECRETKEY", tax=TAX, wl=WL,
                            log=lambda *a: None)
        self.assertTrue(seen)
        for url, headers in seen:
            self.assertNotIn("SECRETKEY", url)
            self.assertEqual(headers, {"X-Api-Key": "SECRETKEY"})

    def test_a_failure_is_a_gap_and_is_asked_again(self):
        client = FakeClient({self.vote_url: FetchError(self.vote_url, usr.FEED, "x", 4, "HTTP 500")})
        self.assertEqual(usr.fill_amendments(self.conn, client, "2026-10-09", "KEY", tax=TAX,
                                             wl=WL, log=lambda *a: None), (0, 0, 1))
        self.assertIsNone(self.row()[4])
        # The next run asks again and succeeds.
        usr.fill_amendments(self.conn, self.client("x."), "2026-10-09", "KEY", tax=TAX, wl=WL,
                            log=lambda *a: None)
        self.assertEqual(self.row()[4], "2026-10-09")

    def test_reclassify_keeps_the_amendment_rule(self):
        usr.fill_amendments(self.conn, self.client("to prohibit funding for a museum."),
                            "2026-10-09", "KEY", tax=TAX, wl=WL, log=lambda *a: None)
        usr.reclassify(self.conn, TAX, log=lambda *a: None)
        self.assertEqual(json.loads(self.row()[3]), [])
