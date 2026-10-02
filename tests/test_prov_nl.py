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


if __name__ == "__main__":
    unittest.main()
