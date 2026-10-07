"""Newfoundland and Labrador (src/ingest/prov_nl.py). No network: fixtures in tests/fixtures/prov/.

THE PROOFS (docs/canada-provinces-scope.md):
  * 1 November 2022, third reading of Bill 7 (Schools Act, 1997), carried
    21-14 on a recorded division: Crocker and A. Parsons for, Petten and
    J. Dinn against. Hansard reads every name and the Clerk's count.
  * 21 November 2016, the Access to Abortion Services Act (Bill 43) read a
    third time on voice: "Carried", no division, no member record.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_nl as nl  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
HANSARD_481 = "https://www.assembly.nl.ca/HouseBusiness/Hansard/ga48session1/"
BILLS_481 = "https://www.assembly.nl.ca/HouseBusiness/Bills/ga48session1/"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def attendance(year):
    return nl.parse_attendance([[(None, fr) for fr in json.loads(fx("nl_attendance_{0}_rows.json".format(year)))]],
                               year)


def conn_for(year):
    conn = db.init_db(db.connect(":memory:"))
    for r in attendance(year):
        key = nl.member_key(r["given"], r["surname"])
        ps.upsert_member(conn, "nl", key, name=r["given"] + " " + r["surname"], surname=r["surname"], given=r["given"])
        ps.replace_terms(conn, "nl", key, [{"legislature": None, "party": None, "riding": r["district"],
                                            "start": "{0}-01-01".format(year), "end": "{0}-12-31".format(year),
                                            "party_dated": 0}], "attendance-{0}".format(year))
    conn.commit()
    return conn


class _Client:
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 1.1

    def __init__(self, pages):
        self.pages = pages

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.pages[url]

    def get_bytes(self, url, feed, slug, archive=True):
        return self.get_text(url, feed, slug).encode()


class ListingTests(unittest.TestCase):
    def test_sitting_files_come_from_the_calendar(self):
        recs = nl.list_records(fx("nl_hansard_481_nov.html"), HANSARD_481)
        self.assertIn({"date": "2016-11-21", "url": HANSARD_481 + "16-11-21.htm", "part": None}, recs)
        self.assertTrue(all(r["date"].startswith("2016-11") for r in recs))

    def test_the_progress_table_and_its_loose_dates(self):
        self.assertEqual(nl.table_date("Nov. 15/2016"), "2016-11-15")
        self.assertEqual(nl.table_date("June 6/2016"), "2016-06-06")
        self.assertEqual(nl.table_date("Apr. 13.2016"), "2016-04-13")
        self.assertEqual(nl.table_date("Decd. 14/2016"), "2016-12-14")
        self.assertEqual(nl.table_date("October 5, 2022"), "2022-10-05")
        bills = {b["number"]: b for b in nl.parse_bill_list(fx("nl_bills_481.html"), BILLS_481)}
        b43 = bills["43"]
        self.assertEqual(b43["href"], BILLS_481 + "bill1643.htm")
        self.assertEqual([(s["stage"], s["date"]) for s in b43["stages"]],
                         [("First Reading", "2016-11-15"), ("Second Reading", "2016-11-17"),
                          ("Committee", "2016-11-17"), ("Third Reading", "2016-11-21"),
                          ("Royal Assent", "2016-12-14")])
        res = pc.classify(pc.load_taxonomy(), pc.load_watchlist("nl"), "nl", title=b43["title"],
                          bill_key="nl-48-1/43")
        self.assertIn(1, res.areas)
        self.assertEqual(res.tier, 1)


class RosterTests(unittest.TestCase):
    def test_the_current_members_script(self):
        rows = {r["key"]: r for r in nl.parse_members_js(fx("nl_members_index.js"))}
        self.assertEqual(rows["helen-conway-ottenheimer"]["surname"], "Conway Ottenheimer")
        self.assertEqual(rows["andrea-barbour"]["district"], "St. Barbe - L'Anse aux Meadows")
        self.assertEqual(rows["keith-russell"]["party"], "Independent/Non-Affiliated")
        self.assertEqual(nl.members_js_url('<script src="../js/members-index.js"></script>'),
                         "https://www.assembly.nl.ca/js/members-index.js")

    def test_attendance_summaries_both_layouts(self):
        r16 = {(r["surname"], r["given"]): r for r in attendance(2016)}
        r22 = {(r["surname"], r["given"]): r for r in attendance(2022)}
        self.assertEqual((len(r16), len(r22)), (40, 40))
        self.assertIn(("Haley", "Carol Anne"), r16)                     # given name first, two words
        self.assertIn(("Walsh", "Sherry Gambin"), r16)                  # hyphen lost in the 2016 PDF
        self.assertEqual(r16[("Brazil", "David")]["district"], "Conception Bay East - Bell Island")  # wrapped
        self.assertIn(("Conway Ottenheimer", "Helen"), r22)
        self.assertIn(("Gambin-Walsh", "Sheryl"), r22)
        # the 2022 summary prints 'Dempter, Lisa'; corrected by hand, with the reason
        self.assertIn(("Dempster", "Lisa"), r22)
        self.assertNotIn(("Dempter", "Lisa"), r22)
        # 2023: a leave of absence is printed 'LOA' where the counts go
        r23 = {(r["surname"], r["given"]) for r in attendance(2023)}
        self.assertEqual(len(r23), 40)
        self.assertIn(("Bragg", "Derrick"), r23)


class ProofTests(unittest.TestCase):
    def test_bill_7_third_reading_21_14_every_name_resolved(self):
        divisions, voices, problems = nl.parse_hansard(nl.hansard_text(fx("nl_hansard_221101.htm")))
        self.assertEqual(problems, [])
        self.assertEqual([(d["yeas"], d["nays"], d["stage"], d["bill_number"], d["vote_on"]) for d in divisions],
                         [(21, 14, "Third Reading", "7", "motion")])
        d = divisions[0]
        self.assertEqual(d["result"], "I declare the motion passed")
        self.assertEqual((d["yea_labels"][0], d["nay_labels"][-1]), ("Steve Crocker", "Paul Lane"))
        r = nl.NameResolver(pn.Resolver.from_conn(conn_for(2022), "nl"))
        votes, ok, note = nl.resolve_division(d, r, "2022-11-01", 50)
        self.assertTrue(ok, note)
        side = {v["member_key"]: v["position"] for v in votes}
        self.assertEqual((side["steve-crocker"], side["andrew-parsons"]), ("Yea", "Yea"))
        self.assertEqual((side["barry-petten"], side["james-dinn"], side["paul-dinn"]), ("Nay", "Nay", "Nay"))
        how = {v["raw_label"]: (v["member_key"], v["how"]) for v in votes}
        # familiar names against the formal roster, by initial, unique-or-nothing
        self.assertEqual(how["Eddie Joyce"][0], "edward-joyce")
        self.assertEqual(how["Pam Parsons"][0], "pamela-parsons")
        self.assertEqual(how["Sherry Gambin-Walsh"][0], "sheryl-gambin-walsh")
        self.assertTrue(how["Eddie Joyce"][1].startswith("initial"))
        self.assertTrue(all(v["party_at_vote"] is None for v in votes))
        # the same day's voice decisions, excluding the divided one
        self.assertEqual([(v["bill_number"], v["stage"]) for v in voices][:3],
                         [("8", "Third Reading"), ("9", "Third Reading"), ("11", "Third Reading")])
        self.assertNotIn(("7", "Third Reading"), [(v["bill_number"], v["stage"]) for v in voices])

    def test_the_2016_names_resolve_against_the_2016_summary(self):
        r = nl.NameResolver(pn.Resolver.from_conn(conn_for(2016), "nl"))
        for label, key in (("Ms. Gambin-Walsh", "sherry-walsh"), ("Ms. Haley", "carol-haley"),
                           ("Mr. Andrew Parsons", "andrew-parsons"), ("Ms. Pam Parsons", "pam-parsons"),
                           ("Mr. Kevin Parsons", "kevin-parsons"), ("Mr. Bernard Davis", "bernard-davis")):
            self.assertEqual(r.resolve(label, "2016-05-31")[0], key, label)
        self.assertIsNone(r.resolve("Mr. Parsons", "2016-05-31")[0])      # three Parsons: ambiguous
        self.assertIsNone(r.resolve("Ms. Haley", "2017-02-01")[0])        # outside the year's term

    def test_access_to_abortion_services_act_passed_on_voice(self):
        divisions, voices, problems = nl.parse_hansard(nl.hansard_text(fx("nl_hansard_161121.htm")))
        self.assertEqual((divisions, problems), ([], []))
        self.assertEqual([(v["bill_number"], v["stage"]) for v in voices], [("43", "Third Reading")])
        self.assertIn("Facilitating Abortion Services", voices[0]["result"])


class VariantTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads(fx("nl_hansard_variants.json"))

    def parse(self, case):
        return nl.parse_hansard(self.cases[case])

    def test_committee_counts_in_words_and_an_aside_before_the_clerk(self):
        d, _v, p = self.parse("committee_words_and_aside")
        self.assertEqual(p, [])
        self.assertEqual([(x["yeas"], x["nays"], len(x["yea_labels"]), len(x["nay_labels"]), x["stage"])
                          for x in d][:1], [(24, 9, 24, 9, "Committee of the Whole")])
        self.assertEqual(nl.count_value("nine"), 9)
        self.assertEqual(nl.count_value("twenty-one"), 21)

    def test_a_count_without_the_word_the(self):
        d, _v, _p = self.parse("no_the_before_ayes")
        self.assertEqual([(x["yeas"], x["nays"], x["stage"], x["bill_number"]) for x in d][-1:],
                         [(25, 9, "Third Reading", "14")])

    def test_names_with_no_count_are_kept_as_a_gap(self):
        d, _v, _p = self.parse("committee_no_count")
        self.assertEqual(len(d), 1)
        self.assertEqual((d[0]["yeas"], d[0]["nays"], len(d[0]["yea_labels"])), (None, None, 23))
        self.assertIn("no Clerk's count", d[0]["problem"])
        self.assertEqual(d[0]["nay_labels"][-1], "Ms. Michael")          # not '... On motion, that ...'
        _votes, ok, note = nl.resolve_division(d[0], nl.NameResolver(pn.Resolver.from_conn(conn_for(2016), "nl")),
                                               "2016-05-12", 48)
        self.assertFalse(ok)
        self.assertIn("no printed totals", note)

    def test_a_call_the_clerk_does_not_answer_is_not_a_division(self):
        d, _v, p = self.parse("speaker_misspoke")
        self.assertEqual(p, [])
        self.assertEqual([(x["yeas"], x["nays"]) for x in d], [(9, 25)])

    def test_a_table_officer_reads_the_names(self):
        d, _v, p = self.parse("table_officer")
        self.assertEqual(p, [])
        self.assertEqual([(x["yeas"], x["nays"], len(x["yea_labels"]), len(x["nay_labels"])) for x in d],
                         [(15, 18, 15, 18)])

    def test_a_list_broken_off_and_resumed_with_a_dash(self):
        d, _v, _p = self.parse("resumed_after_dash")
        x = d[0]
        self.assertEqual((x["yeas"], x["nays"], len(x["nay_labels"])), (21, 15, 15))
        self.assertIn("Jeff Dwyer", x["nay_labels"])                    # not 'Jeff Dwyer –'
        self.assertEqual(x["nay_labels"][-1], "Lela Evans")

    def test_a_list_the_clerk_starts_again(self):
        d, _v, _p = self.parse("restarted_list")
        self.assertEqual([(x["yeas"], x["nays"], len(x["yea_labels"]), len(x["nay_labels"])) for x in d][:1],
                         [(15, 16, 15, 16)])
        self.assertEqual(d[0]["yea_labels"].count("Barry Petten"), 1)

    def test_unanimous_with_no_call_for_those_against(self):
        d, _v, p = self.parse("unanimous_no_against_call")
        self.assertEqual(p, [])
        self.assertEqual([(x["yeas"], x["nays"], len(x["yea_labels"]), x["nay_labels"], x["problem"]) for x in d],
                         [(33, 0, 33, [], None)])

    def test_hear_hear_between_the_call_and_the_clerk(self):
        d, _v, p = self.parse("hear_hear_before_the_clerk")
        self.assertEqual(p, [])
        self.assertEqual([(x["yeas"], x["nays"], len(x["yea_labels"])) for x in d], [(25, 0, 25)])  # 'nays: zero'

    def test_table_officer_in_mixed_case(self):
        d, _v, p = self.parse("table_officer_mixed_case")
        self.assertEqual(p, [])
        self.assertEqual([(x["yeas"], x["nays"], len(x["yea_labels"]), len(x["nay_labels"])) for x in d][:1],
                         [(21, 17, 21, 17)])

    def test_lists_interrupted_by_hear_hear(self):
        d, _v, p = self.parse("interrupted_lists")
        self.assertEqual(p, [])
        self.assertEqual([(x["yeas"], x["nays"], len(x["yea_labels"]), len(x["nay_labels"]), x["vote_on"])
                          for x in d], [(28, 10, 28, 10, "amendment"), (28, 10, 28, 10, "motion")])


class CollectTests(unittest.TestCase):
    def test_a_sitting_lands_in_the_store_and_the_table_agrees(self):
        conn = conn_for(2016)
        for b in nl.parse_bill_list(fx("nl_bills_481.html"), BILLS_481):
            ps.store_bill(conn, {"bill_key": ps.bill_key("nl", 48, 1, b["number"]), "prov": "nl",
                                 "legislature": 48, "session": 1, "number": b["number"], "title_en": b["title"],
                                 "stages": b["stages"], "areas": [1] if b["number"] == "43" else []})
        url = HANSARD_481 + "16-11-21.htm"
        ctx = Context(conn, _Client({"https://www.assembly.nl.ca/robots.txt": "User-agent: *\nDisallow: /search\n",
                                     url: fx("nl_hansard_161121.htm")}), "nl", log=lambda *a: None)
        ctx.tax = pc.load_taxonomy()
        resolver = nl.NameResolver(pn.Resolver.from_conn(conn, "nl"))
        n, gaps = nl.read_sitting(ctx, 48, 1, {"date": "2016-11-21", "url": url, "part": None},
                                  resolver, pc.load_watchlist("nl"))
        self.assertEqual((n, gaps), (0, 0))
        row = conn.execute("SELECT kind, stage, yeas, positions_ok, areas FROM prov_divisions "
                           "WHERE division_key='nl-48-1-2016-11-21-v43-3r'").fetchone()
        self.assertEqual(tuple(row), ("voice", "Third Reading", None, None, "[1]"))
        # the table's third reading of Bill 43 that day is found (Bill 46's
        # first reading the same day is not cross-checked)
        self.assertEqual(nl.check_listing_stages(ctx, 48, 1, {"2016-11-21"}), 0)
        conn.execute("DELETE FROM prov_divisions")
        self.assertEqual(nl.check_listing_stages(ctx, 48, 1, {"2016-11-21"}), 1)
        self.assertIn("nl-48-1/43", ctx.gaps[-1])

    def test_a_truncated_hansard_is_a_gap_not_an_empty_day(self):
        conn = conn_for(2016)
        url = HANSARD_481 + "16-11-21.htm"
        cut = fx("nl_hansard_161121.htm")[:1500]
        ctx = Context(conn, _Client({"https://www.assembly.nl.ca/robots.txt": "", url: cut}), "nl",
                      log=lambda *a: None)
        ctx.tax = pc.load_taxonomy()
        n, gaps = nl.read_sitting(ctx, 48, 1, {"date": "2016-11-21", "url": url, "part": None},
                                  nl.NameResolver(pn.Resolver.from_conn(conn, "nl")), pc.load_watchlist("nl"))
        self.assertEqual((n, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "unreadable")
        self.assertFalse(ps.sitting_done(conn, url))


def attendance_pages(year):
    return nl.parse_attendance([[(None, fr) for fr in page]
                                for page in json.loads(fx("nl_attendance_{0}_pages.json".format(year)))], year)


def bridged_2024():
    return nl.bridge_year(attendance(2023), attendance_pages(2025), 2024, pn.load_record("nl").get("by_elections"))


def conn_with(rows, source):
    conn = db.init_db(db.connect(":memory:"))
    for r in rows:
        key = nl.member_key(r["given"], r["surname"])
        ps.upsert_member(conn, "nl", key, name=r["given"] + " " + r["surname"], surname=r["surname"], given=r["given"])
        conn.execute("INSERT INTO prov_member_terms (prov, member_key, riding, start, end, party_dated, source) "
                     "VALUES ('nl', ?, ?, ?, ?, 0, ?)", (key, r["district"], r["start"], r["end"], source))
    conn.commit()
    return conn


DIVS = None


def division(date):
    global DIVS
    DIVS = DIVS or json.loads(fx("nl_hansard_divisions_2022_2024.json"))
    d, _v, p = nl.parse_hansard(DIVS[date])
    assert len(d) == 1 and not p, (date, p)
    return d[0]


class AliasTests(unittest.TestCase):
    """19 October 2022: Hansard prints 'Lloyd Parrot'; the Journal the same
    day prints 'L. Parrott' at the same place. The reviewed alias clears it."""

    URL = "https://www.assembly.nl.ca/HouseBusiness/Hansard/ga50session2/22-10-19.htm"

    def test_bill_3_third_reading_tallies_with_the_alias(self):
        d = division("2022-10-19")
        self.assertEqual((d["yeas"], d["nays"], d["stage"], d["bill_number"]), (29, 3, "Third Reading", "3"))
        r = nl.make_resolver(conn_for(2022))
        votes, ok, note = nl.resolve_division(d, r, "2022-10-19", 50, document=self.URL)
        self.assertTrue(ok, note)
        parrot = next(v for v in votes if v["raw_label"] == "Lloyd Parrot")
        self.assertEqual((parrot["member_key"], parrot["how"][:5]), ("lloyd-parrott", "alias"))
        # without the alias (the old resolver) it stays a gap
        _v, ok, note = nl.resolve_division(d, nl.NameResolver(pn.Resolver.from_conn(conn_for(2022), "nl")),
                                           "2022-10-19", 50)
        self.assertFalse(ok)
        self.assertIn("unresolved 'Lloyd Parrot'", note)
        # nor on another day
        self.assertIsNone(r.resolve("Lloyd Parrot", "2022-10-20", 50, document=self.URL)[0])


class Roster2024Tests(unittest.TestCase):
    """The 2024 Members' Attendance summary is a scan with no text. 2024 is
    bridged from the 2023 and 2025 summaries and the Elections NL by-election
    reports (config/prov_record.yaml), and all five divisions of 2024 tally."""

    def test_the_bridge_and_its_by_elections(self):
        members, problems = bridged_2024()
        self.assertEqual(problems, [])
        by = {(m["surname"], m["given"]): m for m in members}
        self.assertEqual(len(by), 43)       # the scan's 42 rows, read by eye, plus Jim McKenna, whom it omits
        span = lambda s, g: (by[(s, g)]["start"], by[(s, g)]["end"])  # noqa: E731
        self.assertEqual(span("Hutton", "Fred"), ("2024-02-21", "2024-12-31"))
        self.assertEqual(span("Bragg", "Derrick"), ("2024-01-01", "2024-01-22"))
        self.assertEqual(span("Warr", "Brian"), ("2024-01-01", "2024-03-01"))
        self.assertEqual(span("McKenna", "Jim"), ("2024-05-02", "2024-12-31"))
        self.assertEqual(span("Paddock", "Lin"), ("2024-06-26", "2024-12-31"))
        self.assertEqual(span("Osborne", "Thomas"), ("2024-01-01", "2024-07-08"))
        self.assertEqual(span("Korab", "Jamie"), ("2024-09-13", "2024-12-31"))
        self.assertEqual(span("Dinn", "James"), ("2024-01-01", "2024-12-31"))   # 'Jim' in 2025: same initial
        self.assertNotIn(("Brazil", "David J"), by)                              # resigned 29 Dec 2023
        # the 2023 summary's 'St. Barb' is corrected, so Howell bridges
        self.assertEqual(by[("Howell", "Krista Lynn")]["district"], "St. Barbe - L’Anse aux Meadows")

    def test_all_five_divisions_of_2024_tally(self):
        members, _ = bridged_2024()
        r = nl.make_resolver(conn_with(members, "attendance-2024-bridged"))
        got = []
        for date in ("2024-03-13", "2024-03-21", "2024-05-02", "2024-05-15", "2024-12-03"):
            d = division(date)
            votes, ok, note = nl.resolve_division(d, r, date, 50)
            self.assertTrue(ok, (date, note))
            got.append((d["yeas"], d["nays"], len(votes)))
        self.assertEqual(got, [(19, 16, 35), (20, 0, 20), (19, 17, 36), (17, 15, 32), (17, 15, 32)])

    def test_two_names_joined_by_and(self):
        d = division("2024-05-02")
        self.assertEqual(d["yea_labels"][-2:], ["Lucy Stoyles", "Perry Trimper"])

    def test_a_member_who_vanishes_with_no_record_gets_no_term(self):
        later = [r for r in attendance_pages(2025) if r["surname"] != "Lane"]
        members, problems = nl.bridge_year(attendance(2023), later, 2024, pn.load_record("nl").get("by_elections"))
        self.assertNotIn("Lane", {m["surname"] for m in members})
        self.assertTrue(any("Paul Lane" in p and "no official record" in p for p in problems), problems)
        # ...so a 2024 division he voted in fails the tally check instead of guessing
        r = nl.make_resolver(conn_with(members, "attendance-2024-bridged"))
        _v, ok, note = nl.resolve_division(division("2024-03-13"), r, "2024-03-13", 50)
        self.assertFalse(ok)
        self.assertIn("Paul Lane", note)

    def test_a_by_election_winner_missing_from_the_later_summary_is_a_problem(self):
        later = [r for r in attendance_pages(2025) if r["surname"] != "Korab"]
        members, problems = nl.bridge_year(attendance(2023), later, 2024, pn.load_record("nl").get("by_elections"))
        self.assertTrue(any("Korab" in p for p in problems), problems)


class StandingsPartyTests(unittest.TestCase):
    """Party at the vote for the current (51st) General Assembly, from the
    House's History of the Standings and the members page."""

    def setUp(self):
        self.st = nl.parse_standings(fx("nl_standings_51.html"))
        self.rows = nl.parse_members_js(fx("nl_members_index_51.js"))

    def test_the_page(self):
        self.assertEqual((self.st["assembly"], self.st["election"], self.st["unknown"]), (51, "2025-10-14", []))
        self.assertEqual(self.st["counts"], {"pc": 21, "lib": 15, "ndp": 2, "ind": 2})
        self.assertEqual(self.st["events"], [{"date": "2026-09-14", "name": "Keith Russell",
                                              "party": "Independent/Non-Affiliated"}])

    def test_every_member_dated_and_the_one_change_reconciled(self):
        terms, problems = nl.standings_party_terms(self.rows, self.st, "2026-10-02")
        self.assertEqual((len(terms), problems), (40, []))
        self.assertEqual(terms["keith-russell"], [("2025-10-14", "2026-09-13", "Progressive Conservative"),
                                                  ("2026-09-14", "2026-10-02", "Independent/Non-Affiliated")])
        self.assertEqual(terms["andrea-barbour"], [("2025-10-14", "2026-10-02", "Progressive Conservative")])

    def test_counts_that_do_not_reconcile_store_nothing(self):
        st = dict(self.st, counts={"pc": 22, "lib": 14, "ndp": 2, "ind": 2})
        terms, problems = nl.standings_party_terms(self.rows, st, "2026-10-02")
        self.assertEqual(terms, {})
        self.assertTrue(problems)

    def test_a_sentence_not_understood_stores_nothing(self):
        st = dict(self.st, unknown=["On May 1, 2026, the Member for X resigned."])
        self.assertEqual(nl.standings_party_terms(self.rows, st, "2026-10-02")[0], {})

    def test_party_reaches_the_votes(self):
        conn = db.init_db(db.connect(":memory:"))
        terms, _ = nl.standings_party_terms(self.rows, self.st, "2026-10-02")
        for r in self.rows:
            ps.upsert_member(conn, "nl", r["key"], surname=r["surname"], given=r["given"])
            ps.replace_terms(conn, "nl", r["key"], [{"legislature": 51, "party": r["party"], "riding": r["district"],
                                                    "party_dated": 0}], "roster")
            ps.replace_terms(conn, "nl", r["key"], [{"legislature": 51, "party": p, "start": a, "end": b,
                                                    "party_dated": 1} for a, b, p in terms[r["key"]]],
                             nl.STANDINGS_SOURCE)
        for date in ("2026-03-30", "2026-09-30"):
            ps.store_division(conn, {"division_key": "nl-51-1-{0}-1".format(date), "prov": "nl", "legislature": 51,
                                     "session": 1, "date": date, "seq": 1, "kind": "recorded",
                                     "votes": [{"position": "Yea", "ordinal": 1, "raw_label": "Keith Russell",
                                                "member_key": "keith-russell"}]})
        n, with_party = ps.refresh_party(conn, "nl", pn.Resolver.from_conn(conn, "nl"), 51, 1)
        self.assertEqual((n, with_party), (2, 2))
        self.assertEqual([r[0] for r in conn.execute("SELECT party_at_vote FROM prov_votes ORDER BY division_key")],
                         ["Progressive Conservative", "Independent/Non-Affiliated"])
        # the undated roster party is never used; a past Assembly has no party at all
        r = pn.Resolver.from_conn(conn, "nl")
        self.assertIsNone(r.party_at("keith-russell", "2024-03-13", 50))


V2010 = None


def v2010(case):
    """parse_hansard on one sitting of the 2010 backfill's failures
    (tests/fixtures/prov/nl_hansard_variants_2010_2022.json: real Hansard
    text, trimmed to the division)."""
    global V2010
    V2010 = V2010 or json.loads(fx("nl_hansard_variants_2010_2022.json"))
    return nl.parse_hansard(V2010[case])


def shape(divisions):
    return [(d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])) for d in divisions]


RECORD = pn.load_record("nl")


def dated(year, prev=None, nxt=None):
    """date_terms on the fixture summaries (pages for 2011-2015 and 2018,
    rows for 2016)."""
    def rows(y):
        if y is None:
            return None
        return attendance(y) if y == 2016 else attendance_pages(y)
    return nl.date_terms(rows(year), year, rows(prev), rows(nxt), RECORD.get("by_elections"),
                         nl.load_general_elections(RECORD), nl._other_surnames(RECORD))


def span(members, surname, given):
    m = [x for x in members if (x["surname"], x["given"]) == (surname, given)]
    assert len(m) == 1, (surname, given, m)
    return m[0]["start"], m[0]["end"]


class Backfill2010CallTests(unittest.TestCase):
    """CI run 37044556156 (2 October 2026), 2010 backfill: 84 of 189 recorded
    divisions failed the tally check and 28 Clerk's counts had no division.
    Every case below is a real sitting that failed."""

    def test_a_long_call_with_hon_and_a_list_resumed_after_order(self):
        # 23 June 2010: 'All those in favour of the motion as put forward by
        # the hon. the Member for the District of Burgeo & La Poile, please
        # stand' (the 'hon.' hid the call); the Nays resumed after 'SOME HON.
        # MEMBERS: Oh, oh! MR. SPEAKER: Order, please! CLERK: Mr. Davis, ...'
        d, _v, p = v2010("resumed_after_order_2010")
        self.assertEqual((shape(d), p), ([(4, 33, 4, 33)], []))
        self.assertEqual(d[0]["nay_labels"][16], "Mr. Davis")

    def test_an_ellipsis_and_the_speakers_request_inside_a_list(self):
        d, _v, p = v2010("ellipsis_and_speaker_request_2011")
        self.assertEqual((shape(d), p), ([(35, 5, 35, 5), (35, 5, 35, 5)], []))
        self.assertIn("Mr. Harding", d[0]["yea_labels"])                 # not 'Mr. Harding…'
        self.assertEqual(d[0]["vote_on"], "amendment")

    def test_all_in_favour_and_all_opposed(self):
        d, _v, p = v2010("all_in_favour_all_opposed_2011")
        self.assertEqual((shape(d), p), ([(35, 8, 35, 8)], []))

    def test_a_call_with_no_please_rise(self):
        d, _v, p = v2010("no_please_rise_2012")                          # 'All those in favour of the motion? CLERK:'
        self.assertEqual((shape(d), p), ([(34, 11, 34, 11)], []))

    def test_a_dash_and_the_clerk_carrying_on_is_not_a_restart(self):
        d, _v, p = v2010("dash_then_clerk_continues_2012")
        self.assertEqual((shape(d), p), ([(37, 5, 37, 5)], []))
        self.assertEqual(d[0]["yea_labels"][:4], ["Ms Dunderdale", "Mr. Kennedy", "Ms Burke", "Mr. King"])
        self.assertEqual((d[0]["stage"], d[0]["bill_number"]), ("Second Reading", "12"))

    def test_the_nays_called_first_with_all_those_for(self):
        d, _v, p = v2010("nays_called_first_2013")
        self.assertEqual((shape(d), p), ([(39, 2, 39, 2)], []))
        self.assertEqual(d[0]["nay_labels"], ["Ms Michael", "Ms Rogers"])

    def test_unanimous_counts(self):
        self.assertEqual(shape(v2010("unanimous_the_ayes_2014")[0]), [(34, 0, 34, 0)])   # 'it is unanimous: the ayes thirty-four'
        self.assertEqual(shape(v2010("unanimous_n_ayes_2015")[0]), [(39, 0, 39, 0)])     # 'it is unanimous, thirty-nine ayes'
        self.assertEqual(shape(v2010("there_are_no_nays_2022")[0]), [(31, 0, 31, 0)])    # 'The ayes: 31; there are no nays'
        d, _v, _p = v2010("unanimous_no_count_2013")       # 'The vote is unanimous in favour': no number, a gap
        self.assertEqual((d[0]["yeas"], d[0]["problem"]), (None, "no Clerk's count read after the names"))

    def test_quoted_ayes_and_a_leading_and(self):
        d, _v, p = v2010("quoted_ayes_and_2014")           # "the 'ayes' thirty-one; the 'nays' fourteen"
        self.assertEqual((shape(d), p), ([(31, 14, 31, 14)], []))
        self.assertEqual(d[0]["yea_labels"][-1], "Mr. Russell")          # 'Mr. Dinn, and Mr. Russell'

    def test_voice_calls_answered_by_the_clerk_reading_heads_are_not_divisions(self):
        # 12 May 2016, Committee of Supply: "All those against, 'nay.'
        # Carried. On motion, subhead 1.1.01 carried. CLERK: Office of the
        # Executive Council, ..." -- the first rewrite read 17 such as divisions.
        self.assertEqual(v2010("voice_calls_in_supply_2016")[0], [])
        d, _v, _p = v2010("voice_calls_in_supply_2016_division")         # the real one: names, no count (known)
        self.assertEqual([(x["yeas"], len(x["yea_labels"]), len(x["nay_labels"])) for x in d], [(None, 23, 6)])

    def test_more_call_and_list_forms(self):
        self.assertEqual(shape(v2010("in_favor_2017")[0]), [(27, 10, 27, 10)])
        self.assertEqual(shape(v2010("semicolon_2018")[0]), [(29, 2, 29, 2)])          # 'Ms. Michael; Ms. Rogers'
        self.assertEqual(shape(v2010("members_against_2019")[0]), [(21, 9, 21, 9)])    # 'all those Members against'
        self.assertEqual(shape(v2010("order_please_before_clerk_2020")[0]), [(20, 16, 20, 16)])
        self.assertEqual(shape(v2010("not_in_favour_or_against_2022")[0]), [(20, 13, 20, 13)])
        d, _v, _p = v2010("full_stop_between_names_2020")                 # 'Mr. Byrne. Ms. Dempster'
        self.assertEqual(shape(d), [(35, 2, 35, 2)])
        d, _v, _p = v2010("exchange_before_clerk_2019")                   # 'MS. COADY: Of the sub-amendment?'
        self.assertEqual(shape(d)[0], (20, 19, 20, 19))
        self.assertEqual(d[0]["vote_on"], "subamendment")

    def test_a_count_after_an_interruption_and_a_count_repeated(self):
        d, _v, p = v2010("late_count_2017")                # 'Now I ask for a report from the Clerk.'
        self.assertEqual((shape(d), p), ([(32, 0, 32, 0)], []))
        self.assertIn("characters after the names", d[0]["count_note"])
        d, _v, p = v2010("speaker_repeats_count_2018")      # the Speaker repeats 'The ayes: 8, and the nays: 20'
        self.assertEqual((shape(d), p), ([(8, 20, 8, 20)], []))

    def test_a_clerks_recount_is_one_count_too_many_until_reviewed(self):
        d, _v, p = v2010("clerk_recount_2012")
        self.assertEqual(shape(d)[-1], (31, 11, 32, 11))
        self.assertEqual(p, ["1 Clerk's count(s) with no division read before them"])


class Backfill2010ReadingTests(unittest.TestCase):
    """The backfill's 52 listing misses: a reading the progress table dates to
    a day whose Hansard was read, found neither divided nor on voice. 44 were
    the voice reader's; every form below is a real sitting's."""

    def voices(self, case):
        d, v, p = nl.parse_hansard(json.loads(fx("nl_hansard_readings_2010_2025.json"))[case])
        return [(x["bill_number"], x["stage"]) for x in v], p, v

    def test_loose_formal_lines(self):
        self.assertIn(("2", "Third Reading"), self.voices("third_no_time_2013")[0])      # 'read a third, ordered passed'
        self.assertIn(("8", "Third Reading"), self.voices("read_third_time_2014")[0])    # 'read third time'
        self.assertEqual(self.voices("as_amended_2020")[0], [("26", "Second Reading")])  # 'Bill 26, as amended, read'

    def test_the_speakers_words_and_the_clerks(self):
        self.assertEqual(self.voices("speaker_only_2013")[0], [("1", "Second Reading")])
        self.assertEqual(self.voices("been_a_second_time_2011")[0], [("15", "Second Reading")])
        got, problems, _ = self.voices("clerk_names_stage_2014")    # 'CLERK: The second reading of Bill 23.'
        self.assertIn(("23", "Second Reading"), got)
        self.assertNotIn(("2", "Second Reading"), got)              # the formal line's misprinted 'Bill 2'
        self.assertEqual(problems, [])

    def test_a_formal_line_that_contradicts_the_clerk(self):
        got, problems, v = self.voices("formal_line_contradicts_2018")   # '(Bill 6) On motion, Bill 14 read ...'
        self.assertEqual((got, problems), ([("6", "Second Reading")], []))
        self.assertIn("the formal line prints", v[0]["result"])
        # with nothing else naming Bill 6's reading, it is a gap, never Bill 14
        text = json.loads(fx("nl_hansard_readings_2010_2025.json"))["formal_line_contradicts_2018"]
        text = text.replace("that Bill 6 be now read a second time", "that it be now read a second time")
        d, v, p = nl.parse_hansard(text)
        self.assertEqual([x for x in v if x["bill_number"] in ("6", "14") and x["stage"] == "Second Reading"], [])
        self.assertTrue(any("names Bill 14 just after the Clerk reads Bill 6" in x for x in p), p)

    def test_the_question_put_carried_and_the_title_read(self):
        self.assertEqual(self.voices("put_and_carried_2010")[0], [("10", "Second Reading"), ("10", "Third Reading")])
        self.assertEqual(self.voices("put_and_carried_2025")[0], [("90", "Third Reading")])


class Backfill2010RosterTests(unittest.TestCase):
    """The Members' Attendance summaries as the 2010 backfill read them."""

    def test_credentials_wrapped_rows_and_the_heading(self):
        rows = attendance_pages(2012)
        by = {r["surname"]: r for r in rows}
        self.assertEqual((by["Kennedy"]["given"], by["King"]["given"]), ("Jerome", "Darin"))   # ', Q.C.', ', Ph.D'
        self.assertEqual(by["Hunter"]["district"], "Grand Falls - Windsor - Green Bay South")  # set the other way up
        self.assertEqual(by["Hedderson"]["district"], "Harbour Main")                          # not '... South'
        self.assertEqual(len(rows), 48)
        self.assertFalse([r for r in attendance_pages(2011) if "Absences" in r["district"]])
        self.assertEqual({r["district"] for r in attendance_pages(2018) if r["surname"] == "Bennett"},
                         {"Windsor Lake", "Lewisporte - Twillingate"})                         # '5.5' is a count

    def test_members_who_resigned_are_added_up_to_the_vacancy(self):
        members, notes = dated(2013, prev=2012)
        self.assertEqual(span(members, "Jones", "Yvonne"), ("2013-01-01", "2013-04-08"))
        self.assertEqual(span(members, "Kennedy", "Jerome"), ("2013-01-01", "2013-10-02"))
        self.assertEqual(span(members, "Dempster", "Lisa"), ("2013-07-18", "2013-12-31"))
        self.assertEqual(len(notes), 2)

    def test_by_elections_date_the_year(self):
        members, _ = dated(2014, prev=2013, nxt=2015)
        self.assertEqual(span(members, "Dunderdale", "Kathy"), ("2014-01-01", "2014-02-28"))
        self.assertEqual(span(members, "Bennett", "Cathy"), ("2014-05-05", "2014-12-31"))
        self.assertEqual(span(members, "Shea", "Joan"), ("2014-01-01", "2014-06-02"))
        self.assertEqual(span(members, "Hillier", "Rex"), ("2014-11-21", "2014-12-31"))

    def test_the_general_election_dates_who_came_and_went(self):
        members, _ = dated(2015, prev=2014, nxt=2016)
        self.assertEqual(span(members, "Davis", "Bernard"), ("2015-11-30", "2015-12-31"))
        self.assertEqual(span(members, "Davis", "Paul"), ("2015-01-01", "2015-12-31"))
        self.assertEqual(span(members, "King", "Neil"), ("2015-11-30", "2015-12-31"))
        self.assertEqual(span(members, "Bennett", "Jim"), ("2015-01-01", "2015-11-30"))
        members, _ = dated(2011, nxt=2012)          # 2010 is a scan: no start is dated in 2011
        self.assertEqual(span(members, "Parsons", "Kelvin"), ("2011-01-01", "2011-10-11"))
        self.assertEqual(span(members, "Parsons", "Kevin"), ("2011-01-01", "2011-12-31"))   # 'K' twice: not him
        self.assertEqual(span(members, "Burke", "Joan"), ("2011-01-01", "2011-12-31"))     # Shea in 2012 (reviewed)
        self.assertEqual(span(members, "Osborne", "Sheila"), ("2011-01-01", "2011-10-11"))

    def resolver(self, *years_args):
        rows = []
        for year, prev, nxt in years_args:
            rows += dated(year, prev, nxt)[0]
        return nl.make_resolver(conn_with(rows, "summary-test"))

    def test_the_2015_labels(self):
        r = self.resolver((2015, 2014, 2016))
        for label, key in (("Mr. Davis", "paul-davis"), ("Mr. King", "darin-king"), ("Mr. Bennett", "jim-bennett"),
                           ("Ms Bennett", "cathy-bennett")):
            self.assertEqual(r.resolve(label, "2015-01-22", 47)[0], key, label)
        self.assertTrue(r.resolve("Mr. Bennett", "2015-01-22", 47)[1].startswith("title (reviewed"))
        self.assertIsNone(r.resolve("Mr. Davis", "2015-12-15", 48)[0])          # both sat by then

    def test_ms_burke_in_2012_and_the_spacing_typos(self):
        r = self.resolver((2012, 2011, 2013))
        self.assertEqual(r.resolve("Ms Burke", "2012-03-07", 47)[0], "joan-shea")
        self.assertEqual(r.resolve("Mr. Kennedy", "2012-03-07", 47)[0], "jerome-kennedy")
        r = nl.make_resolver(conn_for(2016))
        self.assertEqual(r.resolve("Ms. Gambin- Walsh", "2016-05-03", 48)[0], "sherry-walsh")
        r = nl.make_resolver(conn_for(2022))
        self.assertEqual(r.resolve("Loyola O' Driscoll", "2022-05-12", 50)[0], "loyola-o-driscoll")

    def test_the_2011_division_settled_from_the_journal(self):
        d = v2010("all_in_favour_all_opposed_2011")[0][0]
        r = self.resolver((2011, None, 2012))
        rv = pn.ReviewedDivisions.load("nl")
        key = "nl-47-1-2011-10-27-1"
        votes, ok, note = nl.resolve_division(d, r, "2011-10-27", 47, reviewed=rv, division_key=key)
        self.assertTrue(ok, note)
        self.assertEqual(next(v["member_key"] for v in votes if v["raw_label"] == "Mr. Parsons"), "andrew-parsons")
        _v, ok, note = nl.resolve_division(d, r, "2011-10-27", 47)
        self.assertFalse(ok)                                                    # without the reviewed fact

    def test_osbourne_alias(self):
        d = v2010("osbourne_2022")[0][0]
        url = "https://www.assembly.nl.ca/HouseBusiness/Hansard/ga50session1/22-05-18.htm"
        votes, ok, note = nl.resolve_division(d, nl.make_resolver(conn_for(2022)), "2022-05-18", 50, document=url)
        self.assertTrue(ok, note)
        self.assertEqual(next(v["member_key"] for v in votes if v["raw_label"] == "Tom Osbourne"), "thomas-osborne")


class Backfill2010OwedTests(unittest.TestCase):
    """The repair: sittings stored 'ok' by the old parser are read again, and
    speech days with an unresolved speaker read before the roster fixes."""

    def test_stale_sittings_and_speech_days_are_owed_once(self):
        from src import prov_speeches as sp
        from src.ingest import prov_nl_hansard as nh
        conn = db.init_db(db.connect(":memory:"))
        old = HANSARD_481 + "16-11-21.htm"
        new = HANSARD_481 + "16-11-22.htm"
        ps.store_sitting(conn, "nl", "nl-48-1-2016-11-21", "2016-11-21", old, when="2026-10-02")
        ps.store_sitting(conn, "nl", "nl-48-1-2016-11-22", "2016-11-22", new, when="2026-10-08")
        ctx = Context(conn, _Client({}), "nl", log=lambda *a: None)
        self.assertEqual(nl.owe_stale(ctx, [{"url": old}, {"url": new}]), 1)
        self.assertFalse(ps.sitting_done(conn, old))
        self.assertTrue(ps.sitting_done(conn, new))
        day = lambda k, d: {"key": k, "date": d, "legislature": 48, "session": 1, "url": old}  # noqa: E731
        sp.store_sitting(conn, "nl", day("a", "2016-11-21"), {"members": 10, "resolved": 9}, "ok", when="2026-10-02")
        sp.store_sitting(conn, "nl", day("b", "2016-11-22"), {"members": 10, "resolved": 10}, "ok", when="2026-10-02")
        ctx.prov = "nl"
        self.assertEqual(nh.owe_unresolved(ctx, [{"key": "a"}, {"key": "b"}]), 1)
        self.assertEqual((sp.day_done(conn, "a"), sp.day_done(conn, "b")), (False, True))


class Backfill2010SpeechTests(unittest.TestCase):
    def test_a_bold_opened_before_the_paragraph_is_still_a_speaker(self):
        # 12 December 2012: '<b>\n<p ...>MR. SPEAKER (Wiseman): </b>Order, please!</p>'
        # -- the day read as 'no speaker turns parsed'
        from src.ingest import prov_nl_hansard as nh
        turns = nh.parse_day(fx("nl_hansard_121212_head.htm"))
        self.assertEqual([t["label"] for t in turns][:2], ["MR. SPEAKER (Wiseman)", "SOME HON. MEMBERS"])
        self.assertIn("MR. EDMUNDS", [t["label"] for t in turns])


class Backfill2010ReadTests(unittest.TestCase):
    URL ="https://www.assembly.nl.ca/HouseBusiness/Hansard/ga47session1/12-06-14.htm"

    def test_a_reviewed_recount_and_a_reread_that_replaces(self):
        rows = dated(2012, 2011, 2013)[0]
        conn = conn_with(rows, "summary-2012")
        page = "<html><body><p>" + json.loads(fx("nl_hansard_variants_2010_2022.json"))["clerk_recount_2012"] + \
               "</p></body></html>"
        ps.store_division(conn, {"division_key": "nl-47-1-2012-06-14-9", "prov": "nl", "legislature": 47,
                                 "session": 1, "date": "2012-06-14", "seq": "9", "kind": "recorded",
                                 "source_url": self.URL, "votes": []})
        ctx = Context(conn, _Client({"https://www.assembly.nl.ca/robots.txt": "", self.URL: page}), "nl",
                      log=lambda *a: None)
        ctx.tax = pc.load_taxonomy()
        ctx.nl_reviewed = pn.ReviewedDivisions.load("nl")
        n, gaps = nl.read_sitting(ctx, 47, 1, {"date": "2012-06-14", "url": self.URL, "part": None},
                                  nl.make_resolver(conn), pc.load_watchlist("nl"))
        self.assertEqual((n, gaps), (4, 0), ctx.gaps)
        got = conn.execute("SELECT division_key, yeas, positions_ok, tally_note FROM prov_divisions "
                           "ORDER BY division_key").fetchall()
        self.assertEqual([g[:3] for g in got], [("nl-47-1-2012-06-14-{0}".format(k), y, 1)
                                                for k, y in ((1, 31), (2, 31), (3, 32), (4, 32))])
        self.assertIn("replaces the record's printed 31", got[3][3])
        # without the reviewed fact: the recount is a stray count and the division a gap
        ctx.nl_reviewed = None
        ctx.gaps = []
        n, gaps = nl.read_sitting(ctx, 47, 1, {"date": "2012-06-14", "url": self.URL, "part": None},
                                  nl.make_resolver(conn), pc.load_watchlist("nl"))
        self.assertEqual(gaps, 2)


if __name__ == "__main__":
    unittest.main()
