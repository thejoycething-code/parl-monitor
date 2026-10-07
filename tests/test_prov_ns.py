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

# -- the 2010 backfill (CI runs 37076568654 and 37108083021, 3 October 2026) -----------
#
# The backfill stored 169 recorded divisions and 108 failed the tally check.
# Every fixture below is a trimmed copy of a page fetched from a GitHub runner
# on 7 October 2026 (probe-hosts.yml, run 37568416383), each the record of a
# division the backfill could not read or a reading it missed.

def _hansard(name, leg, sess, keys=None, histories=None):
    """(divisions, voices, resolver, strays) for a fixture, against the
    session's roster from its own fixtures."""
    conn = store_roster(_conn(), leg, sess, keys=keys, histories=histories)
    r = ns.make_resolver(conn)
    strays = []
    divs, voices = ns.parse_hansard(fx(name), vocab=r.base.surname_vocab(), strays=strays)
    return divs, voices, r, strays


def _resolve(d, r, date, leg, doc=None, key=None):
    votes, ok, note = ns.resolve_division(d, r, date, leg, document=(H + doc) if doc else None,
                                          division_key=key, reviewed=pn.ReviewedDivisions.load("ns"))
    return votes, ok, note


def _by(votes):
    return {v["member_key"]: v["position"] for v in votes}


class Backfill2010LayoutTests(unittest.TestCase):
    """The layouts the parser of 2 October did not know."""

    def test_a_column_of_names_in_one_cell(self):
        """27 April 2012: each column is ONE cell, a name a line ("Mr. Landry<br />
        Ms. More<br />..."), continued after the page break. Read as one name
        each: 1 of 29 and 1 of 19 before."""
        d1, d2 = ns.parse_hansard(fx("ns_hansard_120427.htm"))[0]
        self.assertEqual((d1["yeas"], d1["nays"], len(d1["yea_labels"]), len(d1["nay_labels"])), (29, 19, 29, 19))
        self.assertEqual((d2["bill_number"], d2["stage"]), ("69", "Third Reading"))
        self.assertEqual(d1["yea_labels"][:2], ["Mr. Landry", "Ms. More"])
        self.assertIn("Mr. Zinc", d2["nay_labels"])           # "Mr. Zinck" in the first list
        self.assertIn("Mr. Zinck", d1["nay_labels"])

    def test_the_header_inside_its_cell_was_a_silent_loss(self):
        """5 November 2012: "YEAS<br>Mr. Landry<br>..." in one cell. No header
        row was seen, nothing was read and the sitting was stored 'ok' with no
        division, though Bill 94 passed second reading 28-19 on a recorded vote."""
        (d,), _ = ns.parse_hansard(fx("ns_hansard_121105.htm"))
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (28, 19, 28, 19))
        self.assertEqual((d["bill_number"], d["stage"]), ("94", "Second Reading"))
        self.assertEqual(d["yea_labels"][0], "Mr. Landry")

    def test_a_double_space_inside_a_name_is_no_column_mark(self):
        """6 December 2012: "Ms. Maureen  MacDonald  Mr. Samson". Cut at runs of
        spaces it was three names, the list ended at six lines, and the Clerk's
        count was never reached."""
        (d,), _ = ns.parse_hansard(fx("ns_hansard_121206.htm"))
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (26, 22, 26, 22))
        self.assertIn("Ms. Maureen MacDonald", d["yea_labels"])
        self.assertIn("Mr. Samson", d["nay_labels"])
        self.assertIn("Mr. Burrill", d["yea_labels"])           # the one-name lines are the longer column's
        self.assertIsNone(d["problem"])

    def test_columns_run_together_with_one_space(self):
        """18 October 2023: "Elizabeth Smith-McCrossin Larry Harrison". The
        Clerk's count says how many lines hold two names; each is cut where it
        leaves two full names."""
        divs, _, r, _ = _hansard("ns_hansard_231018.htm", 64, 1)
        (d,) = divs
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (19, 28, 19, 28))
        self.assertIn("Elizabeth Smith-McCrossin", d["yea_labels"])
        self.assertIn("Larry Harrison", d["nay_labels"])
        self.assertIn("Lorelei Nicoll", d["yea_labels"])
        self.assertIn("Hon. Colton LeBlanc", d["nay_labels"])
        _v, ok, note = _resolve(d, r, "2023-10-18", 64)
        self.assertTrue(ok, note)

    def test_a_line_that_is_not_two_names_is_a_gap_not_a_guess(self):
        y, n, a, note, problem = ns._place_lines(["Hon. Nolan Young Claudia Chender", "Kent Smith Lena Diab Rod"],
                                                 (2, 2, None))
        self.assertIsNotNone(problem)
        self.assertEqual(ns._split_n("Hon. Nolan Young Claudia Chender", 2), ["Hon. Nolan Young", "Claudia Chender"])
        self.assertEqual(ns._split_n("John A. MacDonald Larry Harrison", 2), ["John A. MacDonald", "Larry Harrison"])
        self.assertIsNone(ns._split_n("Lena Metlege Diab Kent Smith", 2))              # two cuts, no vocabulary
        vocab = {("diab",), ("smith",), ("metlege", "diab")}
        self.assertEqual(ns._split_n("Lena Metlege Diab Kent Smith", 2, vocab), ["Lena Metlege Diab", "Kent Smith"])

    def test_one_column_full_names_and_a_three_column_list(self):
        """17 October 2022. A one-column list prints a name a line, "Dave  Ritcey"
        with two spaces (44-0, Bill 204); the earlier list that day has a third
        column, ABSTENTIONS, and the count "For, 28. Nay, 17. Abstentions, 1.":
        never read before, a division silently lost."""
        divs, _, r, _ = _hansard("ns_hansard_221017.htm", 64, 1)
        hours, bill = divs
        self.assertEqual((hours["yeas"], hours["nays"], hours["abstentions"]), (28, 17, 1))
        self.assertEqual(hours["abs_labels"], ["E. Smith-McCrossin"])
        votes, ok, note = _resolve(hours, r, "2022-10-17", 64)
        self.assertTrue(ok, note)
        self.assertEqual(_by(votes)["elizabeth-smith-mccrossin"], "Abstain")
        self.assertEqual(_by(votes)["claudia-chender"], "Nay")
        self.assertEqual((bill["yeas"], bill["nays"], len(bill["yea_labels"])), (44, 0, 44))
        self.assertEqual((bill["bill_number"], bill["stage"]), ("204", "Second Reading"))   # "Bill 204", no "No."
        self.assertIn("Dave Ritcey", bill["yea_labels"])
        self.assertTrue(_resolve(bill, r, "2022-10-17", 64)[1])

    def test_a_list_printed_with_no_header(self):
        """9 March 2026: the second list runs straight from "[The Clerk called the
        roll.]" to the Clerk's count, with no YEAS NAYS. Read between those two
        marks only; it was a division silently lost."""
        divs, _, r, strays = _hansard("ns_hansard_260309.htm", 65, 1)
        self.assertEqual(strays, [])
        first, second = divs
        self.assertEqual((second["yeas"], second["nays"], len(second["yea_labels"]), len(second["nay_labels"])),
                         (38, 10, 38, 10))
        self.assertIn("no YEAS NAYS header printed", second["note"])
        self.assertTrue(_resolve(second, r, "2026-03-09", 65)[1])
        # The first list misprints two names; each is a reviewed alias, on its day and in its record only.
        _v, ok, note = _resolve(first, r, "2026-03-09", 65, doc="elsewhere")
        self.assertFalse(ok)
        self.assertIn("LeBlancoHon", note)
        votes, ok, note = _resolve(first, r, "2026-03-09", 65, doc="assembly-65-session-1/house_26mar09")
        self.assertTrue(ok, note)
        self.assertEqual(_by(votes)["ryan-robicheau"], "Yea")

    def test_a_list_a_table_begins_and_paragraphs_finish(self):
        """13 March 2026: the YEAS run on after the table, a name a paragraph,
        to the Clerk's count ten blocks on: no count was found."""
        divs, _, r, strays = _hansard("ns_hansard_260313.htm", 65, 1)
        d = divs[1]
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (37, 13, 37, 13))
        self.assertEqual((d["bill_number"], d["stage"]), ("198", "Second Reading"))
        votes, ok, note = _resolve(d, r, "2026-03-13", 65)
        self.assertTrue(ok, note)
        # Financial Measures (2026), whipped: the Premier for, the NDP leader against.
        self.assertEqual((_by(votes)["tim-houston"], _by(votes)["claudia-chender"]), ("Yea", "Nay"))
        self.assertEqual(strays, [])

    def test_unclosed_paragraphs_late_2011(self):
        """25 November 2011 closes no <p>: the page read as ten paragraphs and
        the sitting was stored 'ok' and empty. Bill 102's second reading was
        divided (25-13)."""
        divs, voices = ns.parse_hansard(fx("ns_hansard_111125.htm"))
        (d,) = divs
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (25, 13, 25, 13))
        self.assertEqual((d["bill_number"], d["stage"]), ("102", "Second Reading"))

    def test_a_paragraph_left_open_over_a_table(self):
        """11 May 2015: a page marker's <p> is left open over the second half of
        the list, which was read as one paragraph with the Clerk's count."""
        divs, _, r, _ = _hansard("ns_hansard_150511.htm", 62, 2)
        self.assertEqual(len(divs), 5)
        d = divs[0]
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (15, 27, 15, 27))
        for d in divs:
            self.assertTrue(_resolve(d, r, "2015-05-11", 62, doc="assembly-62-session-2/house_15may11")[1])

    def test_the_roll_call_interrupted(self):
        """The Chair breaks in: "Can the honourable member for Halifax Chebucto
        please stand with his vote?" (5 May 2015); the gallery is cleared and
        the header printed again (18 December 2015). The same list goes on."""
        divs, _, r, _ = _hansard("ns_hansard_150505.htm", 62, 2)
        self.assertEqual((divs[0]["yeas"], divs[0]["nays"], len(divs[0]["yea_labels"]), len(divs[0]["nay_labels"])),
                         (13, 24, 13, 24))
        divs, _, r, _ = _hansard("ns_hansard_151218.htm", 62, 2)
        (d,) = divs
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (30, 14, 30, 14))
        votes, ok, note = _resolve(d, r, "2015-12-18", 62)
        self.assertTrue(ok, note)
        self.assertEqual((_by(votes)["stephen-mcneil"], _by(votes)["jamie-baillie"]), ("Yea", "Nay"))

    def test_typesetting_slips(self):
        # Two cells run into one: ['Mr. Churchill Mr. Dunn'] (6 May 2016)
        divs = ns.parse_hansard(fx("ns_hansard_160506.htm"))[0]
        self.assertEqual([(d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])) for d in divs],
                         [(32, 12, 32, 12)] * 3)
        self.assertEqual((divs[1]["yea_labels"][0], divs[1]["nay_labels"][0]), ("Mr. Churchill", "Mr. Dunn"))
        # An entity split around a name: "&Mr. Rankinnbsp;" (7 November 2014)
        divs = ns.parse_hansard(fx("ns_hansard_141107.htm"))[0]
        self.assertIn("Mr. Rankin", divs[1]["yea_labels"])
        # Two names on one line of a one-column list: "Mr. MacDonell Ms. Zann" (3 December 2010, 38-0)
        d = ns.parse_hansard(fx("ns_hansard_101203.htm"))[0][0]
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (38, 0, 38, 0))
        self.assertTrue({"Mr. MacDonell", "Ms. Zann"} <= set(d["yea_labels"]))
        # A title run into the name: "Mr.Scott", "Mr.Whynott" (22 April 2010)
        (d,), _ = ns.parse_hansard(fx("ns_hansard_100422.htm"))
        self.assertIn("Mr. Scott", d["nay_labels"])
        self.assertIn("Mr. Whynott", d["yea_labels"])

    def test_every_form_of_the_clerks_count(self):
        cases = {
            "THE CLERK: For, 28, Against 12.": (28, 12, None),
            "THE CLERK « » : For, 23. Against. 20. (Applause)": (23, 20, None),
            "THE CLERK » : Those in favour of the motion, 31; those against, 17.": (31, 17, None),
            "THE CLERK « » : Those in favour of the motion 30, those against 11.": (30, 11, None),
            "THE CLERK « » : Those in favour of the motion to concur, 25. Those against, 23.": (25, 23, None),
            "THE CLERK « » : Mr. Speaker, in favour of Resolution No. 35, 33; against, 13 - meeting the "
            "two-thirds threshold.": (33, 13, None),
            "THE CLERK « » : The results of the recorded vote are as follows: Yays, 47. Nays, 0.": (47, 0, None),
            "THE CLERK » : For, 28. Nay, 17. Abstentions, 1.": (28, 17, 1),
            "THE CLERK » : For, 36. Against,13.": (36, 13, None),
        }
        for text, want in cases.items():
            self.assertEqual(ns.clerk_count(text), want, text)
        self.assertIsNone(ns.clerk_count("THE CLERK « » : That the committee has met and considered the following bill:"))
        self.assertIsNone(ns.clerk_count("YEAS NAYS"))


class Backfill2010NameTests(unittest.TestCase):
    def test_mr_david_wilson_is_dave_wilson_by_initial(self):
        """2013-2018 Hansard prints "Mr. David Wilson" for the Member the roster
        calls Dave Wilson (his own profile: "The Honourable Dave Wilson",
        "Bills introduced by David Wilson"), beside "Mr. Gordon Wilson". The
        given name is not the roster's, and the surname alone is two Members:
        the INITIAL of the printed given name is one. 69 votes in 62 divisions
        were unresolved."""
        divs, _, r, _ = _hansard("ns_hansard_141020.htm", 62, 2)
        (d,) = divs
        votes, ok, note = _resolve(d, r, "2014-10-20", 62, doc="assembly-62-session-2/house_14oct20")
        self.assertTrue(ok, note)
        by_label = {v["raw_label"]: v["member_key"] for v in votes}
        self.assertEqual(by_label["Mr. David Wilson"], "david-wilson")
        self.assertEqual(by_label["Mr. Gordon Wilson"], "gordon-l-wilson")
        self.assertEqual(by_label["Mr. Bailey"], "jamie-baillie")              # reviewed alias, this day only
        self.assertIsNone(r.resolve("Mr. Bailey", "2014-10-21", 62, document=H + "elsewhere")[0])
        # Never a guess: an initial no Wilson has stays unresolved.
        key, how = r.resolve("Mr. Peter Wilson", "2014-10-20", 62)
        self.assertIsNone(key)
        self.assertTrue(how.startswith("ambiguous"), how)

    def test_a_bare_wilson_beside_gordon_wilson_by_elimination(self):
        """4 April 2014: "Mr. Wilson" and "Mr. Gordon Wilson" in one 48-0 list.
        Gordon Wilson cannot vote twice (British Columbia's rule)."""
        divs, _, r, _ = _hansard("ns_hansard_140404.htm", 62, 1)
        first, bill37 = divs
        self.assertEqual((first["yeas"], first["nays"]), (48, 0))       # "Those in favour of the motion, 48 ..."
        votes, ok, note = _resolve(first, r, "2014-04-04", 62)
        self.assertTrue(ok, note)
        self.assertEqual({v["raw_label"]: v["member_key"] for v in votes}["Mr. Wilson"], "david-wilson")
        # Bill 37 (essential health services), third reading 31-17, whipped:
        # Premier McNeil for; Baillie (PC) and Maureen MacDonald (NDP) against.
        self.assertEqual((bill37["bill_number"], bill37["stage"], bill37["yeas"], bill37["nays"]),
                         ("37", "Third Reading", 31, 17))
        votes, ok, note = _resolve(bill37, r, "2014-04-04", 62, doc="assembly-62-session-1/house_14apr04")
        self.assertTrue(ok, note)                                      # "Mr. MacNeil", reviewed
        by = _by(votes)
        self.assertEqual((by["stephen-mcneil"], by["jamie-baillie"], by["maureen-macdonald"]), ("Yea", "Nay", "Nay"))

    def test_ms_macdonald_settled_by_a_reviewed_hansard_label(self):
        """23 April 2013: a bare "Ms. MacDonald" with Manning and Maureen
        MacDonald both sitting; reviewed in config/prov_record.yaml for that
        division only. The first division that day stays a gap: it prints 25
        NAYS and the Clerk counted 26 (a record error, a known gap)."""
        # Glace Bay's David Wilson had left before 61-2: its Journal's list of
        # Members names only David A. Wilson (test above), so he sits in no
        # later session of the 61st.
        keys = {row["key"] for row in roster(61)} - {"david-wilson-0"}
        divs, _, r, _ = _hansard("ns_hansard_130423.htm", 61, 5, keys=keys)
        first, bill58 = divs
        bare = ns.resolve_division(bill58, r, "2013-04-23", 61)
        self.assertFalse(bare[1])
        votes, ok, note = _resolve(bill58, r, "2013-04-23", 61, key="ns-61-5-2013-04-23-2")
        self.assertTrue(ok, note)
        self.assertEqual({v["raw_label"]: v["member_key"] for v in votes}["Ms. MacDonald"], "maureen-macdonald")
        _v, ok, note = _resolve(first, r, "2013-04-23", 61, key="ns-61-5-2013-04-23-1")
        self.assertFalse(ok)
        self.assertIn("25 name(s) read, 26 printed", note)

    def test_a_record_that_prints_fewer_names_than_counted_stays_a_gap(self):
        """11 April 2023: Bill 316's third reading lists 27 YEAS and the Clerk
        counted 28 (Premier Houston is in no list that day). The tally check
        is never loosened: the division places nobody."""
        divs, _, r, _ = _hansard("ns_hansard_230411.htm", 64, 1)
        self.assertTrue(_resolve(divs[0], r, "2023-04-11", 64)[1])
        _v, ok, note = _resolve(divs[1], r, "2023-04-11", 64)
        self.assertFalse(ok)
        self.assertIn("Yea: 27 name(s) read, 28 printed", note)

    def test_the_stage_from_a_question_that_names_no_bill(self):
        """17 October 2019: "The motion is for second reading." The stage is
        the question's; the bill is the one whose second reading was moved."""
        keys = set()
        for name in ("ns_memberlist_632a_rows.json", "ns_memberlist_632b_rows.json"):
            keys |= ns.match_members(ns.parse_member_list(json.loads(fx(name))), roster(63))[0]
        (d,), _, r, _ = _hansard("ns_hansard_191017.htm", 63, 2, keys=keys,
                                 histories={"david-wilson": "ns_profile_david-wilson.html",
                                            "gordon-l-wilson": "ns_profile_gordon-l-wilson.html"})
        self.assertEqual((d["bill_number"], d["stage"], d["yeas"], d["nays"]), ("203", "Second Reading", 24, 20))
        votes, ok, note = _resolve(d, r, "2019-10-17", 63)
        self.assertTrue(ok, note)
        self.assertEqual({v["raw_label"]: v["member_key"] for v in votes}["Mr. Wilson"], "gordon-l-wilson")


class Backfill2010VoiceTests(unittest.TestCase):
    def test_readings_put_without_a_division(self):
        # The mover's words, put at once (7 May 2010, Bill 1)
        self.assertIn(("1", "Second Reading"), {(v["bill_number"], v["stage"])
                                               for v in ns.parse_hansard(fx("ns_hansard_100507.htm"))[1]})
        # Carried by the order that follows, no "The motion is carried." (6 March 2025, Bill 68)
        self.assertIn(("68", "Second Reading"), {(v["bill_number"], v["stage"])
                                                for v in ns.parse_hansard(fx("ns_hansard_250306.htm"))[1]})
        # Bills called together: "The motions are carried." / "Ordered that these bills do pass." (28 Nov 2011)
        got = {(v["bill_number"], v["stage"]) for v in ns.parse_hansard(fx("ns_hansard_111128.htm"))[1]}
        self.assertTrue({("84", "Third Reading"), ("85", "Third Reading")} <= got, got)


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

    def test_a_sitting_the_old_parser_stored_ok_is_read_again_and_replaced(self):
        """The CI repair (REREAD_BEFORE): every sitting stored 'ok' before the
        parser of 7 October 2026 is owed once; a re-read replaces what the
        record stored before, so a division an older parse left is gone."""
        conn = _conn()
        pages = self._pages()
        ctx = Context(conn, _Client(pages), "ns", since="2025-03-25", until="2025-03-25", log=lambda *a: None)
        ns.collect(ctx, session="65-1", bills=False)
        conn.execute("UPDATE prov_sittings SET read_at='2026-10-03'")
        ps.store_division(conn, {"division_key": "ns-65-1-2025-03-25-9", "prov": "ns", "legislature": 65,
                                 "session": 1, "date": "2025-03-25", "seq": "9", "kind": "recorded",
                                 "source_url": HANSARD_250325, "positions_ok": 0, "votes": []})
        conn.commit()
        ctx = Context(conn, _Client(pages), "ns", since="2025-03-25", until="2025-03-25", log=lambda *a: None)
        stats = ns.collect(ctx, session="65-1", bills=False)
        self.assertEqual((stats["owed_stale"], stats["records_read"]), (1, 1))
        keys = [r[0] for r in conn.execute("SELECT division_key FROM prov_divisions WHERE kind='recorded'")]
        self.assertEqual(keys, ["ns-65-1-2025-03-25-1"])
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "ok")

    def test_a_clerks_count_with_no_list_read_is_a_gap_never_ok(self):
        import re as _re
        pages = self._pages()
        pages[HANSARD_250325] = _re.sub(r"(?is)<table\b.*?</table>", "", fx("ns_hansard_250325.htm"))
        conn = _conn()
        ctx = Context(conn, _Client(pages), "ns", since="2025-03-25", until="2025-03-25", log=lambda *a: None)
        ns.collect(ctx, session="65-1", bills=False)
        self.assertTrue(any("follows no list of names read" in g for g in ctx.gaps), ctx.gaps)
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "gap")
        self.assertFalse(ps.sitting_done(conn, HANSARD_250325))


if __name__ == "__main__":
    unittest.main()
