"""Alberta (src/ingest/prov_ab.py). No network: fixtures in tests/fixtures/prov/.

THE PROOF (docs/canada-provinces-scope.md): on 3 December 2024 Bills 26
(puberty blockers), 27 (pronouns, parental notification) and 29 (female
sport) passed third reading on division, 47-35, 47-33 and 47-33, with Smith
and LaGrange for and Notley and Gray against -- and every printed total
accounted for by resolved names.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_ab as ab  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
DATE = "2024-12-03"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def load_terms(conn, drop=()):
    data = json.loads(fx("ab_terms_31.json"))
    for m in data["members"]:
        if m["member_key"] in drop:
            continue
        ps.upsert_member(conn, "ab", m["member_key"], name=m["name"], surname=m["surname"],
                         given=m["given"])
    by = {}
    for t in data["terms"]:
        if t["member_key"] not in drop:
            by.setdefault(t["member_key"], []).append(t)
    for key, ts in by.items():
        ps.replace_terms(conn, "ab", key, ts, "member-page")
    conn.commit()


def conn_with_terms(drop=()):
    conn = db.init_db(db.connect(":memory:"))
    load_terms(conn, drop)
    return conn


class ListingTests(unittest.TestCase):
    def test_file_names_come_from_the_listing_with_backslashes_turned(self):
        recs = dict(ab.list_records(fx("ab_vp_list_31_1.html")))
        self.assertEqual(recs[DATE], "https://docs.assembly.ab.ca/LADDAR_files/docs/houserecords/vp/"
                                     "legislature_31/session_1/20241203_1200_01_vp.pdf")
        self.assertIn("2024-11-26", recs)


class RosterTests(unittest.TestCase):
    def test_the_listing(self):
        rows = ab.parse_roster(fx("ab_roster_31.html"))
        self.assertEqual(len(rows), 91)
        by = {r["mid"]: r for r in rows}
        self.assertEqual(by["0958"]["surname"], "Calahoo Stonehouse")
        self.assertEqual((by["0958"]["given"], by["0958"]["caucus"]), ("Jodi", "NDP"))
        self.assertTrue(by["0791"]["former"])               # Notley
        self.assertIsNone(by["0791"]["riding"])
        self.assertEqual(by["0945"]["riding"], "Highwood")   # R.J. Sigurdson

    def test_party_over_time_from_the_member_page(self):
        """Pete Guthrie: UCP to 16 April 2025, then Independent, Alberta
        Party, Progressive Tory -- each a dated term."""
        page = ab.parse_member_page(fx("ab_member_0920.html"))
        terms = ab.terms_from_page(page, 31)
        self.assertEqual([t["party"] for t in terms],
                         ["Progressive Tory Party", "Alberta Party", "Independent", "United Conservative"])
        ucp = terms[-1]
        self.assertEqual((ucp["start"], ucp["end"], ucp["riding"]), ("2019-04-16", "2025-04-16", "Airdrie-Cochrane"))
        r = pn.Resolver({"0920": {"surname": "Guthrie", "given": "Peter", "name": "Pete Guthrie"}},
                        [dict(t, member_key="0920") for t in terms])
        self.assertEqual(r.party_at("0920", DATE, 31), "United Conservative")
        self.assertEqual(r.party_at("0920", "2025-10-01", 31), "Independent")

    def test_the_roles_table_is_not_read_as_party_dates(self):
        """Measured live: the Offices and Roles table follows and has Start
        and End cells too; it once replaced Notley's party dates with a
        ministry's."""
        page = ab.parse_member_page(fx("ab_member_0791.html"))
        self.assertEqual(page["affiliations"], [("2008-03-03", "2024-12-30", "Alberta New Democratic Party")])
        self.assertEqual(page["service"], [("2008-03-03", "2024-12-30")])
        self.assertEqual(page["elected"][31], "Edmonton-Strathcona")


class BillTests(unittest.TestCase):
    def test_the_bill_page(self):
        page = ab.parse_bill_page(fx("ab_bill26_page.html"))
        self.assertEqual(page["title"], "Health Statutes Amendment Act, 2024 (No. 2)")
        self.assertEqual(page["sponsor_mid"], "0924")
        self.assertTrue(page["text_url"].endswith("/legislature_31/session_1/20230530_bill-026.pdf"))
        got = [(s["stage"], s["date"], s["status"]) for s in page["stages"]]
        self.assertEqual(got[0], ("First Reading", "2024-10-31", "passed on division"))
        self.assertIn(("Third Reading", DATE, "passed on division"), got)
        self.assertIn(("Committee of the Whole", "2024-11-27", "passed"), got)
        self.assertIn(("Second Reading", "2024-11-05", ""), got)       # debated, not decided

    def test_the_bill_list(self):
        items = {b["number"]: b for b in ab.parse_bill_list(fx("ab_bills_31_1.html"))}
        self.assertEqual(items["29"]["title"], "Fairness and Safety in Sport Act")
        self.assertEqual(items["27"]["bill_type"], "Government Bills")
        self.assertEqual(items["201"]["bill_type"], "Private Members' Public Bills")

    def test_voice_stages_are_stored_as_voice_and_divided_ones_are_not(self):
        conn = db.init_db(db.connect(":memory:"))
        ctx = Context(conn, _Client({}), "ab", since="2024-10-28", until="2024-12-05", log=lambda *a: None)
        page = ab.parse_bill_page(fx("ab_bill26_page.html"))
        n = ab.store_voice_stages(ctx, "ab-31-1/26", 31, 1, page["stages"], "https://x")
        self.assertEqual(n, 1)
        row = conn.execute("SELECT kind, stage, date, yeas, positions_ok FROM prov_divisions").fetchone()
        self.assertEqual(tuple(row), ("voice", "Committee of the Whole", "2024-11-27", None, None))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_votes").fetchone()[0], 0)


class ClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tax = pc.load_taxonomy()
        cls.wl = pc.load_watchlist("ab")

    def test_bill_26_text_is_area_3_and_not_organ_donation(self):
        res = pc.classify(self.tax, self.wl, "ab", title="Health Statutes Amendment Act, 2024 (No. 2)",
                          texts=[fx("ab_bill26_excerpt.txt")])
        self.assertEqual((res.areas, res.tier), ([3], 1))

    def test_bill_27_text_is_area_6_on_pronouns_and_notification(self):
        res = pc.classify(self.tax, self.wl, "ab", title="Education Amendment Act, 2024",
                          texts=[fx("ab_bill27.txt")])
        self.assertEqual(res.areas, [6])
        self.assertIn("preferred name*", res.terms)
        self.assertIn("parental notification", res.terms)

    def test_bill_29_needs_its_text_or_its_key(self):
        title_only = pc.classify(self.tax, self.wl, "ab", title="Fairness and Safety in Sport Act")
        self.assertEqual(title_only.areas, [])
        text = pc.classify(self.tax, self.wl, "ab", title="Fairness and Safety in Sport Act",
                           texts=[fx("ab_bill29.txt")])
        self.assertEqual(text.areas, [5])                     # 'mixed-sex leagues'
        keyed = pc.classify(self.tax, self.wl, "ab", title="Fairness and Safety in Sport Act",
                            bill_key="ab-31-1/29")
        self.assertEqual((keyed.areas, keyed.tier), ([5], 1))

    def test_bill_9_of_2025_is_caught_only_by_its_key(self):
        """The notwithstanding clause over Bills 26, 27 and 29: its text
        never says 'gender'."""
        text = pc.classify(self.tax, self.wl, "ab", title="Protecting Alberta's Children Statutes Amendment Act, 2025",
                           texts=[fx("ab_bill9_312.txt")])
        self.assertEqual(text.areas, [])
        self.assertIn("operate notwithstanding", text.terms)     # flagged for the judge
        keyed = pc.classify(self.tax, self.wl, "ab", texts=[fx("ab_bill9_312.txt")], bill_key="ab-31-2/9")
        self.assertEqual(keyed.areas, [3, 5, 6])


class ProofTests(unittest.TestCase):
    """3 December 2024, from the V&P text and the terms collected live."""

    def setUp(self):
        self.conn = conn_with_terms()
        self.r = pn.Resolver.from_conn(self.conn, "ab")
        self.divs = ab.parse_vp(fx("ab_vp_20241203.txt"), self.r.surname_vocab())

    def by_name(self, votes):
        names = {k: m["name"] for k, m in self.r.members.items()}
        return {names.get(v["member_key"]): v for v in votes}

    def test_nine_divisions_with_their_bills_stages_and_printed_totals(self):
        got = [(d["bill_number"], d["stage"], d["vote_on"], d["yeas"], d["nays"]) for d in self.divs]
        self.assertEqual(got, [
            ("26", "Third Reading", "amendment", 35, 47), ("26", "Third Reading", "motion", 47, 35),
            ("27", "Third Reading", "amendment", 33, 47), ("27", "Third Reading", "motion", 47, 33),
            ("29", "Third Reading", "amendment", 33, 47), ("29", "Third Reading", "motion", 47, 33),
            ("32", "Committee of the Whole", "motion", 75, 0),
            ("34", "Committee of the Whole", "motion", 44, 17),
            ("35", "Committee of the Whole", "amendment", 17, 42)])
        self.assertEqual(self.divs[1]["result"],
                         "The question being immediately put, the motion for Third Reading was agreed to")

    def test_every_tally_matches_and_the_partisans_sit_where_they_should(self):
        for d in self.divs:
            votes, ok, note = ab.resolve_division(d, self.r, DATE, 31)
            self.assertTrue(ok, (d["seq"], note))
        for seq in (2, 4, 6):                                 # the three third readings
            votes, ok, _ = ab.resolve_division(self.divs[seq - 1], self.r, DATE, 31)
            v = self.by_name(votes)
            self.assertEqual(v["Danielle Smith"]["position"], "Yea")
            self.assertEqual(v["Adriana LaGrange"]["position"], "Yea")
            self.assertEqual(v["Rachel Notley"]["position"], "Nay")
            self.assertEqual(v["Christina Gray"]["position"], "Nay")
            self.assertEqual(v["Danielle Smith"]["party_at_vote"], "United Conservative")
            self.assertEqual(v["Rachel Notley"]["party_at_vote"], "Alberta New Democratic Party")
        votes, _, _ = ab.resolve_division(self.divs[1], self.r, DATE, 31)
        v = self.by_name(votes)
        self.assertEqual(v["R.J. Sigurdson"]["raw_label"], "Sigurdson (Highwood)")
        self.assertEqual(v["Lori Sigurdson"]["raw_label"], "Sigurdson (Edmonton-Riverview)")
        self.assertEqual(v["Jodi Calahoo Stonehouse"]["position"], "Nay")
        # One Brar sat in December 2024; the 2025 by-election winner is not him.
        self.assertEqual(v["Gurinder Brar"]["position"], "Nay")
        self.assertNotIn("Gurtej Singh Brar", v)

    def test_a_missing_member_makes_a_gap_and_a_null_never_a_guess(self):
        conn = conn_with_terms(drop=("0791",))                # Notley
        r = pn.Resolver.from_conn(conn, "ab")
        divs = ab.parse_vp(fx("ab_vp_20241203.txt"), r.surname_vocab() | {("notley",)})
        votes, ok, note = ab.resolve_division(divs[1], r, DATE, 31)
        self.assertFalse(ok)
        self.assertIn("unresolved 'Notley'", note)
        notley = [v for v in votes if v["raw_label"] == "Notley"][0]
        self.assertIsNone(notley["member_key"])


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


class CollectTests(unittest.TestCase):
    """The collector end to end on fixtures: listing -> V&P -> store."""

    def setUp(self):
        self._pdf = ab.pdf_text
        text = fx("ab_vp_20241203.txt")
        ab.pdf_text = lambda raw: text if raw == b"%PDF-vp-20241203" else self._pdf(raw)

    def tearDown(self):
        ab.pdf_text = self._pdf

    def run_collect(self, conn):
        url = ("https://docs.assembly.ab.ca/LADDAR_files/docs/houserecords/vp/legislature_31/"
               "session_1/20241203_1200_01_vp.pdf")
        client = _Client({ab.VP_LIST.format(31, 1): fx("ab_vp_list_31_1.html"),
                          url: "%PDF-vp-20241203"})
        ctx = Context(conn, client, "ab", since=DATE, until=DATE, log=lambda *a: None)
        stats = ab.collect(ctx, session="31-1", roster=False, bills=False)
        return ctx, stats

    def test_the_proof_lands_in_the_store(self):
        conn = conn_with_terms()
        ctx, stats = self.run_collect(conn)
        self.assertEqual((stats["records_read"], stats["divisions"], stats["tally_gaps"]), (1, 9, 0))
        rows = conn.execute("SELECT division_key, bill_key, yeas, nays, positions_ok, areas FROM prov_divisions "
                            "WHERE vote_on='motion' AND stage='Third Reading' ORDER BY division_key").fetchall()
        self.assertEqual([tuple(r) for r in rows], [
            ("ab-31-1-2024-12-03-2", "ab-31-1/26", 47, 35, 1, "[3]"),
            ("ab-31-1-2024-12-03-4", "ab-31-1/27", 47, 33, 1, "[6]"),
            ("ab-31-1-2024-12-03-6", "ab-31-1/29", 47, 33, 1, "[5]")])
        smith = conn.execute("SELECT position FROM prov_votes WHERE division_key='ab-31-1-2024-12-03-2' "
                             "AND member_key='0814'").fetchone()[0]
        self.assertEqual(smith, "Yea")
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "ok")
        # read cleanly once: not read again
        ctx, stats = self.run_collect(conn)
        self.assertEqual(stats["records_read"], 0)

    def test_a_tally_gap_is_recorded_and_the_sitting_stays_owed(self):
        conn = conn_with_terms(drop=("0791",))
        ctx, stats = self.run_collect(conn)
        self.assertGreater(stats["tally_gaps"], 0)
        self.assertTrue(any("tally check failed" in g for g in ctx.gaps))
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "gap")
        ok = conn.execute("SELECT positions_ok FROM prov_divisions WHERE division_key='ab-31-1-2024-12-03-2'").fetchone()[0]
        self.assertEqual(ok, 0)
        ctx, stats = self.run_collect(conn)
        self.assertEqual(stats["records_read"], 1)             # owed, so read again

    def test_a_bill_page_flag_without_a_parsed_division_is_a_gap(self):
        conn = conn_with_terms()
        ps.store_bill(conn, {"bill_key": "ab-31-1/99", "prov": "ab", "legislature": 31, "session": 1,
                             "number": "99", "stages": [{"stage": "Third Reading", "date": DATE,
                                                         "status": "passed on division"}]})
        ctx = Context(conn, _Client({}), "ab", log=lambda *a: None)
        self.assertEqual(ab.check_division_flags(ctx, 31, 1, {DATE}), 1)
        self.assertIn("passed on division", ctx.gaps[0])


if __name__ == "__main__":
    unittest.main()
