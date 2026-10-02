"""Nova Scotia (src/ingest/prov_ns.py). No network: fixtures in tests/fixtures/prov/.

Every fixture is a trimmed copy of a page fetched from a GitHub runner on
2 October 2026 (.github/workflows/probe-hosts.yml): nslegislature.ca resets
the laptop's VPN exit, and answers the runner.

THE PROOF: on 25 March 2025 Bill 6 (Agriculture, Energy and Natural
Resources) passed third reading 39-11 on a recorded vote -- Premier Houston
for, Claudia Chender (NDP leader) against -- and the Clerk's count "For, 39.
Against, 11." is the printed total the tally check needs. On 6 May 2010, in
the paragraph layout of that era, Bill 24 passed third reading 28-12: Premier
Dexter for, Stephen McNeil (Liberal leader) against.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_ns as ns  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
H = "https://nslegislature.ca/legislative-business/hansard-debates/"
HANSARD_250325 = H + "assembly-65-session-1/house_25mar25"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def _conn():
    return db.init_db(db.connect(":memory:"))


def roster(leg):
    return ns.parse_roster_table(fx("ns_roster_{0}.html".format(leg)))


def store_roster(conn, leg, sess, keys=None, histories=None):
    """The session's terms as fetch_roster stores them, without the network:
    the Assembly's table, cut to `keys` (a session list's Members), dated by
    `histories` ({key: profile fixture})."""
    dates = ns.parse_assembly_dates(fx("ns_assembly_dates_{0}.html".format(leg)), leg)[sess]
    for r in roster(leg):
        if keys is not None and r["key"] not in keys:
            continue
        ps.upsert_member(conn, "ns", r["key"], name=r["name"], surname=r["surname"], given=r["given"])
        hist = []
        if histories and r["key"] in histories:
            rows = ns.parse_profile_parties(fx(histories[r["key"]]))
            ps.replace_terms(conn, "ns", r["key"], ns.profile_party_terms(rows), ns.PROFILE_SOURCE)
            hist = ns.stored_history(conn, r["key"])
        ps.replace_terms(conn, "ns", r["key"], ns.membership_terms(hist, (dates["start"], dates["end"]), leg,
                                                                     r["riding"]),
                         "roster-{0}-{1}".format(leg, sess))
    conn.commit()
    return conn


class _Client:
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 1.1

    def __init__(self, pages):
        self.pages = pages
        self.asked = []
        self.host_throttles = {}

    def set_host_throttle(self, host, seconds):
        self.host_throttles[host] = max(seconds, self.host_throttles.get(host, 0))

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        page = self.pages[url]
        return page.decode("utf-8") if isinstance(page, bytes) else page

    def get_bytes(self, url, feed, slug, archive=True):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        page = self.pages[url]
        return page if isinstance(page, bytes) else page.encode()


# -- sessions and listings ----------------------------------------------------------

class SessionTests(unittest.TestCase):
    def test_the_hansard_index_lists_sessions_from_the_56th_assembly(self):
        got = ns.index_sessions(fx("ns_hansard_index.html"))
        self.assertEqual(got[0], (65, 1))
        self.assertIn((61, 2), got)
        self.assertEqual(got[-1], (56, 2))
        self.assertEqual(len(got), 26)

    def test_the_assembly_dates_page_dates_each_session(self):
        d61 = ns.parse_assembly_dates(fx("ns_assembly_dates_61.html"), 61)
        self.assertEqual(d61[2], {"start": "2010-03-25", "end": "2011-03-31"})   # opened .. prorogued
        self.assertEqual(d61[5]["end"], "2013-09-07")                              # dissolved
        self.assertEqual(ns.assembly_span(fx("ns_assembly_dates_61.html")), ("2009-06-09", "2013-09-07"))
        d65 = ns.parse_assembly_dates(fx("ns_assembly_dates_65.html"), 65)
        self.assertEqual(d65[1], {"start": "2024-12-10", "end": None})            # still sitting

    def test_only_the_assemblies_a_window_can_touch_are_asked_for_dates(self):
        base = "https://nslegislature.ca/legislative-business/bills-statutes/assembly-dates/"
        client = _Client({"https://nslegislature.ca/robots.txt": fx("ns_robots.txt"),
                          ns.HANSARD_INDEX: fx("ns_hansard_index.html"),
                          base + "65": fx("ns_assembly_dates_65.html"),
                          base + "64": fx("ns_assembly_dates_64.html"),
                          base + "63": fx("ns_assembly_dates_63.html")})
        ctx = Context(_conn(), client, "ns", since="2019-01-01", log=lambda *a: None)
        got = ns.list_sessions(ctx)
        self.assertEqual([s["code"] for s in got], ["63-1", "63-2", "63-3", "64-1", "65-1"])
        self.assertIn({"code": "64-1", "start": "2021-09-24", "end": "2024-10-27"}, got)
        self.assertFalse(any(u.endswith("/62") or u.endswith("/61") for u in client.asked), client.asked)
        self.assertEqual(ctx.gaps, [])
        # robots.txt's Crawl-delay is honoured for the host
        self.assertEqual(client.host_throttles.get("nslegislature.ca"), 10.0)

    def test_the_listing_is_taken_as_listed_across_its_pages(self):
        url = ns.HANSARD.format(61, 2)
        client = _Client({"https://nslegislature.ca/robots.txt": fx("ns_robots.txt"),
                          url: fx("ns_hansard_612.html"), url + "?page=1": fx("ns_hansard_612_p1.html")})
        ctx = Context(_conn(), client, "ns", log=lambda *a: None)
        recs = ns.fetch_listing(ctx, 61, 2)
        self.assertEqual(len(recs), 64)
        self.assertEqual(recs[0]["date"], "2010-03-25")
        last = recs[-1]
        self.assertEqual(last["date"], "2011-03-31")
        # linked under the French path, and kept so: never constructed
        self.assertEqual(last["url"], H + "61e-assemblee-2e-session/house_11mar31")
        self.assertEqual(ctx.gaps, [])


# -- divisions ----------------------------------------------------------------------

class DivisionParseTests(unittest.TestCase):
    def test_bill_6_third_reading_2025_table_layout(self):
        divs, voices = ns.parse_hansard(fx("ns_hansard_250325.htm"))
        self.assertEqual(len(divs), 1)
        d = divs[0]
        self.assertEqual((d["yeas"], d["nays"]), (39, 11))
        self.assertEqual((len(d["yea_labels"]), len(d["nay_labels"])), (39, 11))
        self.assertEqual((d["bill_number"], d["stage"], d["result"]), ("6", "Third Reading", "The motion is carried"))
        self.assertEqual(d["question"], "The motion is for third reading of Bill No. 6.")
        self.assertIn("Hon. Tim Houston", d["yea_labels"])
        self.assertIn("Claudia Chender", d["nay_labels"])
        # The continuation table after the page break closes no <td>.
        self.assertIn("Danny MacGillivray", d["yea_labels"])
        # Bill 48's third reading the same day: all those in favour, carried.
        self.assertIn({"bill_number": "48", "stage": "Third Reading",
                       "result": "The motion is carried (no recorded vote)"}, voices)
        self.assertFalse(any(v["bill_number"] == "6" for v in voices))

    def test_bill_24_third_reading_2010_paragraph_layout(self):
        """Before about 2015 each printed line is a paragraph, the columns cut
        by a run of spaces; once the NAYS run out the YEAS go on one a line."""
        (d,), _ = ns.parse_hansard(fx("ns_hansard_100506.htm"))
        self.assertEqual((d["yeas"], d["nays"]), (28, 12))
        self.assertEqual((len(d["yea_labels"]), len(d["nay_labels"])), (28, 12))
        self.assertEqual((d["bill_number"], d["stage"]), ("24", "Third Reading"))
        self.assertEqual(d["yea_labels"][0], "Mr. Landry")
        self.assertEqual(d["nay_labels"][0], "Mr. Samson")
        self.assertIn("Mr. Manning MacDonald", d["nay_labels"])     # wrapped in the source: "Manning\nMacDonald"
        self.assertIn("Ms. Maureen MacDonald", d["yea_labels"])
        self.assertIn("Mr. Dexter", d["yea_labels"])
        self.assertIn("Mr. McNeil", d["nay_labels"])
        self.assertIn("read as YEAS", d["note"])
        self.assertIsNone(d["problem"])

    def test_a_header_paragraph_then_a_table_with_its_own_header(self):
        (d,), _ = ns.parse_hansard(fx("ns_hansard_191030.htm"))      # October 2019
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (46, 0, 46, 0))
        self.assertEqual((d["bill_number"], d["stage"]), ("213", "Third Reading"))

    def test_a_continuation_table_that_repeats_the_header(self):
        (d,), _ = ns.parse_hansard(fx("ns_hansard_231109.htm"))      # 9 November 2023
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (36, 7, 36, 7))
        # "The motion is to close third reading debate of Bill No. 340"
        self.assertEqual((d["bill_number"], d["stage"]), ("340", "Third Reading"))

    def test_rows_with_no_opening_tr(self):
        (d,), _ = ns.parse_hansard(fx("ns_hansard_240404.htm"))      # 4 April 2024
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (46, 0, 46, 0))
        self.assertEqual(d["yea_labels"][0], "Hon. Brad Johns")

    def test_a_dilatory_motion_is_a_motion_on_the_bill_not_its_reading(self):
        recommit, third = ns.parse_hansard(fx("ns_hansard_240405.htm"))[0]
        self.assertEqual((recommit["yeas"], recommit["nays"]), (21, 28))
        self.assertEqual((recommit["bill_number"], recommit["stage"]), ("419", "Motion"))
        self.assertEqual(recommit["result"], "The motion is defeated")
        self.assertIn("recommit", recommit["question"])
        self.assertEqual((third["yeas"], third["nays"], third["stage"]), (28, 17, "Third Reading"))

    def test_a_motion_with_no_bill(self):
        d = ns.parse_hansard(fx("ns_hansard_190412.htm"))[0][0]
        self.assertEqual((d["yeas"], d["nays"]), (25, 22))
        self.assertIsNone(d["bill_number"])
        self.assertTrue(d["question"].startswith("The motion is that the House concur in the report"))


class ResolutionTests(unittest.TestCase):
    def _resolve(self, conn, raw, date, leg):
        return ns.resolve_division(raw, ns.make_resolver(conn), date, leg, document=None)

    def test_bill_6_tallies_with_the_reviewed_alias_and_not_without(self):
        conn = store_roster(_conn(), 65, 1)
        (d,), _ = ns.parse_hansard(fx("ns_hansard_250325.htm"))
        bare = ns.NameResolver(pn.Resolver.from_conn(conn, "ns"))
        _v, ok, note = ns.resolve_division(d, bare, "2025-03-25", 65)
        self.assertFalse(ok)
        self.assertIn("'Tom Taggar'", note)                      # printed so; the roster has one Taggart
        votes, ok, note = ns.resolve_division(d, ns.make_resolver(conn), "2025-03-25", 65,
                                              document=HANSARD_250325)
        self.assertTrue(ok, note)
        by = {v["member_key"]: v["position"] for v in votes}
        self.assertEqual(by["tim-houston"], "Yea")
        self.assertEqual(by["claudia-chender"], "Nay")
        self.assertEqual(by["tom-taggart"], "Yea")
        # The alias is good on its day and in its document only.
        other = ns.make_resolver(conn).resolve("Tom  Taggar", "2025-03-25", 65, document=H + "elsewhere")
        self.assertIsNone(other[0])

    def test_bill_24_resolves_only_with_the_sessions_own_list_of_members(self):
        """The 61st Assembly had two David Wilsons. The 61-2 Journal's list of
        Members names David A. Wilson (Sackville-Cobequid) only: Glace Bay's
        David Wilson had gone, and 'Mr. Wilson' in May 2010 is the former."""
        (d,), _ = ns.parse_hansard(fx("ns_hansard_100506.htm"))
        conn = store_roster(_conn(), 61, 2)
        _v, ok, note = self._resolve(conn, d, "2010-05-06", 61)
        self.assertFalse(ok)
        self.assertIn("'Mr. Wilson'", note)
        parsed = ns.parse_member_list(json.loads(fx("ns_memberlist_612_rows.json")))
        keys, problems = ns.match_members(parsed, roster(61))
        conn = store_roster(_conn(), 61, 2, keys=keys)
        votes, ok, note = self._resolve(conn, d, "2010-05-06", 61)
        self.assertTrue(ok, note)
        by = {v["raw_label"]: v["member_key"] for v in votes}
        self.assertEqual(by["Mr. Wilson"], "david-wilson")
        self.assertEqual(by["Mr. Manning MacDonald"], "manning-macdonald")
        self.assertEqual(by["Ms. K. Regan"], "kelly-regan")
        pos = {v["member_key"]: v["position"] for v in votes}
        self.assertEqual(pos["darrell-dexter"], "Yea")
        self.assertEqual(pos["stephen-mcneil"], "Nay")

    def test_the_recommit_motion_and_the_third_reading_of_bill_419(self):
        recommit, third = ns.parse_hansard(fx("ns_hansard_240405.htm"))[0]
        conn = store_roster(_conn(), 64, 1)
        votes, ok, note = self._resolve(conn, recommit, "2024-04-05", 64)
        self.assertTrue(ok, note)
        by = {v["raw_label"]: v["member_key"] for v in votes}
        self.assertEqual(by["Susan Leblanc"], "susan-leblanc")
        self.assertEqual(by["Hon. Colton LeBlanc"], "colton-leblanc")
        doc = H + "assembly-64-session-1/house_24apr05"
        votes, ok, note = ns.resolve_division(third, ns.make_resolver(conn), "2024-04-05", 64, document=doc)
        self.assertTrue(ok, note)                                 # "Hon. Timothy Hallman", reviewed

    def test_the_printed_case_may_split_leblanc_from_leblanc(self):
        conn = store_roster(_conn(), 64, 1)
        r = ns.make_resolver(conn)
        self.assertEqual(r.resolve("Ms. Leblanc", "2024-04-05", 64)[0], "susan-leblanc")
        key, how = r.resolve("Mr. LeBlanc", "2024-04-05", 64)          # Colton and Ronnie
        self.assertIsNone(key)
        self.assertTrue(how.startswith("ambiguous"), how)

    def test_a_misprinted_given_name_falls_back_to_the_surname_alone(self):
        conn = store_roster(_conn(), 65, 1)
        r = ns.make_resolver(conn)
        # printed so on 24 March 2025 (Bill 68, third reading)
        self.assertEqual(r.resolve("Diane Timmins", "2025-03-24", 65)[0], "dianne-timmins")
        self.assertEqual(r.resolve("Suzie Hansen", "2025-03-24", 65)[0], "suzy-hansen")
        # ... but a misprinted SURNAME is never guessed
        self.assertIsNone(r.resolve("Tom Taggar", "2025-03-24", 65)[0])


# -- roster, party at the vote --------------------------------------------------------

class RosterTests(unittest.TestCase):
    def test_the_table_gives_slugs_ridings_and_latest_party(self):
        rows = {r["key"]: r for r in roster(61)}
        self.assertEqual(len(rows), 58)
        self.assertEqual(rows["trevor-zinck"]["party"], "Independent")   # elected NDP in 2009: latest, undated
        self.assertEqual(rows["david-wilson"]["riding"], "Sackville-Cobequid")
        self.assertEqual(rows["david-wilson-0"]["riding"], "Glace Bay")
        self.assertEqual(rows["david-wilson"]["page"], "https://nslegislature.ca/members/profiles/david-wilson")
        self.assertEqual(ns.roster_assembly(fx("ns_roster_61.html")), 61)

    def test_the_session_list_names_who_sat_in_the_session(self):
        parsed = ns.parse_member_list(json.loads(fx("ns_memberlist_612_rows.json")))
        self.assertEqual(parsed["session"], (61, 2))
        self.assertEqual(len(parsed["rows"]), 52)
        self.assertIn("Jamie Baillie won the by-election", parsed["notes"]["4"])
        keys, problems = ns.match_members(parsed, roster(61))
        self.assertEqual(problems, [])
        self.assertIn("jamie-baillie", keys)                 # from footnote 4, by Cumberland South
        for gone in ("david-wilson-0", "rodney-j-macdonald", "angus-macisaac", "richard-hurlburt"):
            self.assertNotIn(gone, keys)
        self.assertNotIn("eddie-orrell", keys)               # elected in 2011, after the session
        self.assertEqual(len(keys), 53)

    def test_the_lists_of_a_session_with_two(self):
        rows = roster(63)
        got = set()
        for name in ("ns_memberlist_632a_rows.json", "ns_memberlist_632b_rows.json"):
            parsed = ns.parse_member_list(json.loads(fx(name)))
            self.assertEqual(parsed["session"], (63, 2))
            keys, problems = ns.match_members(parsed, rows)
            self.assertEqual(problems, [], name)
            got |= keys
        # Dave Wilson resigned in November 2018, Kendra Coombes won in March 2020
        self.assertTrue({"david-wilson", "gordon-l-wilson", "kendra-coombes", "dave-ritcey"} <= got, got)

    def test_party_history_is_dated_by_year_and_a_change_year_has_none(self):
        self.assertEqual(ns.parse_profile_parties(fx("ns_profile_smith-mccrossin.html")),
                         [("Independent", 2021, None), ("Progressive Conservative", 2017, 2021)])
        conn = _conn()
        for key, f in (("elizabeth-smith-mccrossin", "ns_profile_smith-mccrossin.html"),
                       ("becky-druhan", "ns_profile_becky-druhan.html")):
            ps.upsert_member(conn, "ns", key, surname=key.split("-")[-1])
            ps.replace_terms(conn, "ns", key, ns.profile_party_terms(ns.parse_profile_parties(fx(f))),
                             ns.PROFILE_SOURCE)
        r = pn.Resolver.from_conn(conn, "ns")
        self.assertEqual(r.party_at("elizabeth-smith-mccrossin", "2020-06-01"), "Progressive Conservative")
        self.assertIsNone(r.party_at("elizabeth-smith-mccrossin", "2021-06-01"))      # the year she left
        self.assertEqual(r.party_at("elizabeth-smith-mccrossin", "2025-03-25"), "Independent")
        self.assertEqual(r.party_at("becky-druhan", "2024-04-05"), "Progressive Conservative")
        self.assertIsNone(r.party_at("becky-druhan", "2025-06-01"))
        self.assertIsNone(r.party_at("becky-druhan", "2026-04-08"))         # Independent to Liberal in 2026
        self.assertEqual(r.party_at("becky-druhan", "2027-01-15"), "Liberal")
        # party-only terms never make anyone a member
        self.assertIsNone(r.resolve("Ms. Druhan", "2024-04-05")[0])

    def test_a_profile_dates_membership_too(self):
        """'Mr. Wilson' in April 2019 is Gordon Wilson: Dave Wilson's last
        year was 2018 (the 63-2 Journal: he resigned 16 November 2018)."""
        hist = ns.profile_party_terms(ns.parse_profile_parties(fx("ns_profile_gordon-l-wilson.html")))
        got = ns.membership_terms([{"party": t["party"], "start": t["start"], "end": t["end"]} for t in hist],
                                  ("2018-09-06", "2020-12-18"), 63, "Clare-Digby")
        self.assertEqual([(t["start"], t["end"]) for t in got], [("2018-09-06", "2020-12-18")])
        two = ns.membership_terms([{"party": "New Democratic", "start": "2003-01-01", "end": "2018-12-31"}],
                                  ("2018-09-06", "2020-12-18"), 63, "Sackville-Cobequid")
        self.assertEqual([(t["start"], t["end"]) for t in two], [("2018-09-06", "2018-12-31")])
        # no history: the whole session
        self.assertEqual([(t["start"], t["end"]) for t in ns.membership_terms([], ("2010-03-25", None), 61, "x")],
                         [("2010-03-25", None)])


# -- bills -----------------------------------------------------------------------------

class BillTests(unittest.TestCase):
    def test_the_listing(self):
        items = {b["number"]: b for b in ns.parse_bill_list(fx("ns_bills_651.html"), ns.BILLS.format(65, 1))}
        self.assertEqual(set(items), {"6", "48", "201", "240", "268"})
        self.assertEqual(items["240"]["text_url"], "https://nslegislature.ca/legc/bills/65th_1st/1st_read/b240.htm")
        self.assertEqual(items["6"]["bill_type"], "Government Bill")
        self.assertEqual(items["268"]["bill_type"], "Private Member's Bill")
        self.assertEqual(items["6"]["last_activity"], "2025-03-26")

    def test_the_bill_page(self):
        page = ns.parse_bill_page(fx("ns_bill6_651.html"))
        self.assertEqual((page["sponsor"], page["sponsor_key"]), ("Tory Rushton", "tory-rushton"))
        st = {s["stage"]: s["date"] for s in page["stages"]}
        self.assertEqual(st["Second Reading"], "2025-03-07")
        self.assertEqual(st["Third Reading"], "2025-03-25")
        self.assertEqual(st["Royal Assent"], "2025-03-26")

    def test_a_government_bill_names_its_sponsor_without_a_link(self):
        page = ns.parse_bill_page(fx("ns_bill133_632.html"))
        self.assertEqual((page["sponsor"], page["sponsor_key"]), ("Stephen McNeil", None))
        self.assertIn({"stage": "Third Reading", "date": "2019-04-12", "status": "passed"}, page["stages"])

    def test_deemed_consent_passed_on_voice_and_is_watched(self):
        divs, voices = ns.parse_hansard(fx("ns_hansard_190412_bill133.htm"))
        self.assertEqual(divs, [])
        self.assertEqual(voices, [{"bill_number": "133", "stage": "Third Reading",
                                   "result": "The motion is carried (no recorded vote)"}])
        res = pc.classify(pc.load_taxonomy(), pc.load_watchlist("ns"), "ns",
                          title="Human Organ and Tissue Donation Act", bill_key="ns-63-2/133")
        self.assertEqual((res.areas, res.tier), ([13], 1))
        # The conversion-practices ban's text says "efforts to change THEIR
        # sexual orientation": only its key files it.
        res = pc.classify(pc.load_taxonomy(), pc.load_watchlist("ns"), "ns",
                          texts=["The purpose of this Act is to protect Nova Scotia youth from damaging efforts to "
                                 "change their sexual orientation or gender identity."])
        self.assertEqual(res.areas, [])
        self.assertEqual(pc.watched_bill("ns", "ns-63-2/16")["areas"], [4])

    def test_the_bill_text_is_the_bill_not_the_site(self):
        body = ns.bill_body(fx("ns_billtext_240_651.htm"))
        self.assertTrue(body.startswith("BILL NO. 240"))
        self.assertIn("gender-affirming care", body)
        self.assertNotIn("Legislative Library", body)

    def test_fetch_bills_reads_texts_and_the_pages_a_division_names(self):
        conn = _conn()
        base = ns.BILLS.format(65, 1)
        client = _Client({"https://nslegislature.ca/robots.txt": fx("ns_robots.txt"), base: fx("ns_bills_651.html"),
                          "https://nslegislature.ca/legc/bills/65th_1st/1st_read/b240.htm": fx("ns_billtext_240_651.htm"),
                          base + "/bill-6": fx("ns_bill6_651.html")})
        ctx = Context(conn, client, "ns", since="2026-03-01", log=lambda *a: None)
        stats = ns.fetch_bills(ctx, 65, 1, pc.load_taxonomy(), pc.load_watchlist("ns"), want_pages={"6"})
        self.assertEqual(stats["bills"], 5)
        row = conn.execute("SELECT text_read FROM prov_bills WHERE bill_key='ns-65-1/240'").fetchone()
        self.assertEqual(row[0], 1)
        # A bill seen for the first time has its text asked for whatever the
        # window; on the next run a bill quiet since the window opened is
        # listed, not read again.
        b006 = "https://nslegislature.ca/legc/bills/65th_1st/1st_read/b006.htm"
        self.assertIn(b006, client.asked)
        client.asked.clear()
        ns.fetch_bills(ctx, 65, 1, pc.load_taxonomy(), pc.load_watchlist("ns"))
        self.assertNotIn(b006, client.asked)
        self.assertNotIn("https://nslegislature.ca/legc/bills/65th_1st/1st_read/b240.htm", client.asked)
        six = conn.execute("SELECT sponsor_key, stages FROM prov_bills WHERE bill_key='ns-65-1/6'").fetchone()
        self.assertEqual(six[0], "tory-rushton")
        self.assertIn("2025-03-25", six[1])
        # an unread text is a gap, said out loud
        self.assertTrue(any("b201.htm" in g for g in ctx.gaps), ctx.gaps)


# -- the run, end to end -----------------------------------------------------------------

class CollectTests(unittest.TestCase):
    def _pages(self):
        listing = ns.HANSARD.format(65, 1)
        return {"https://nslegislature.ca/robots.txt": fx("ns_robots.txt"),
                listing: fx("ns_hansard_651.html"), listing + "?page=1": fx("ns_hansard_651_p1.html"),
                ns.DATES.format(65): fx("ns_assembly_dates_65.html"),
                ns.ROSTER.format(65): fx("ns_roster_65.html"),
                ns.JOURNALS: fx("ns_journals.html"),
                HANSARD_250325: fx("ns_hansard_250325.htm"),
                ns.BILLS.format(65, 1): fx("ns_bills_651.html"),
                ns.BILLS.format(65, 1) + "/bill-6": fx("ns_bill6_651.html")}

    def test_one_sitting_end_to_end(self):
        conn = _conn()
        client = _Client(self._pages())
        ctx = Context(conn, client, "ns", since="2025-03-25", until="2025-03-25", log=lambda *a: None)
        stats = ns.collect(ctx, session="65-1")
        self.assertEqual(stats["records_read"], 1)
        self.assertEqual(stats["members"], 56)
        d = [tuple(r) for r in conn.execute("SELECT positions_ok, yeas, nays, bill_key, stage FROM prov_divisions "
                                            "WHERE kind='recorded'")]
        self.assertEqual(d, [(1, 39, 11, "ns-65-1/6", "Third Reading")])
        voice = [tuple(r) for r in conn.execute("SELECT bill_key, stage FROM prov_divisions WHERE kind='voice'")]
        self.assertIn(("ns-65-1/48", "Third Reading"), voice)
        # The Hansard has Bill 6's third reading, which its page dates that day: no listing miss.
        self.assertEqual(stats["listing_misses"], 0)
        # The run waits ten seconds between requests to the host.
        self.assertEqual(client.host_throttles.get("nslegislature.ca"), 10.0)
        # Profiles were not served: each is a gap, and those Members' votes carry no party.
        self.assertTrue(any("/members/profiles/" in g for g in ctx.gaps))
        n = conn.execute("SELECT COUNT(*) FROM prov_votes WHERE party_at_vote IS NOT NULL").fetchone()[0]
        self.assertEqual(n, 0)
        # The 65th Assembly has no Journal list of Members: everyone in the table sits.
        self.assertFalse(any("member list" in g for g in ctx.gaps))

    def test_a_truncated_hansard_is_unreadable_not_an_empty_day(self):
        pages = self._pages()
        pages[HANSARD_250325] = fx("ns_hansard_250325.htm")[:4000]
        conn = _conn()
        ctx = Context(conn, _Client(pages), "ns", since="2025-03-25", until="2025-03-25", log=lambda *a: None)
        ns.collect(ctx, session="65-1", bills=False)
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "unreadable")
        self.assertFalse(ps.sitting_done(conn, HANSARD_250325))


if __name__ == "__main__":
    unittest.main()
