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
        # Area 5 too since taxonomy v1.15 (3 Oct 2026): the bill's text says
        # "gender identity or gender expression".
        self.assertEqual((res.areas, res.tier), ([3, 5], 1))

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
        self.assertTrue(self.divs[1]["result"].startswith("the motion was carried on division, 47-35"),
                        self.divs[1]["result"])
        # The voice vote is printed first and the division decides: an
        # amendment the Speaker called on the voice vote can still be defeated.
        self.assertTrue(self.divs[0]["result"].startswith("the amendment was defeated on division, 35-47"),
                        self.divs[0]["result"])

    def test_the_division_decides_not_the_voice_vote(self):
        """3 Oct 2026: Bill 26's first reading was "defeated on the voice
        vote" and carried 45-34 on division; the stored result said defeated."""
        r = ab.division_result("the motion was defeated", 45, 34, voice=True)
        self.assertTrue(r.startswith("the motion was carried on division, 45-34"), r)
        self.assertIn("voice vote before the division", r)
        self.assertTrue(ab.division_result("the amendment was agreed to", 32, 44)
                        .startswith("the amendment was defeated on division, 32-44"))

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


# -- the 2010 backfill's tally gaps (2 October 2026) ---------------------------
#
# 358 of 1,338 recorded divisions failed the tally check after the backfill.
# Each cause below is pinned by a trimmed page of the real V&P text (pypdf's
# own extraction, glyph spacing and all) and resolved against the dated
# terms of the 28th-30th Legislatures as collected from the member pages.

def conn_with_history():
    """Terms of every member of the 28th, 29th and 30th Legislatures, one
    set per legislature, as the fixed roster reader stores them."""
    conn = db.init_db(db.connect(":memory:"))
    data = json.loads(fx("ab_terms_28_30.json"))
    for m in data["members"]:
        ps.upsert_member(conn, "ab", m["member_key"], name=m["name"], surname=m["surname"],
                         given=m["given"])
    by = {}
    for t in data["terms"]:
        by.setdefault((t["member_key"], t["legislature"]), []).append(t)
    for (key, leg), ts in by.items():
        ps.replace_terms(conn, "ab", key, ts, "member-page", legislature=leg)
    conn.commit()
    return conn


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = conn_with_history()
        cls.r = ab.make_resolver(cls.conn)
        cls.vocab = cls.r.surname_vocab()

    def divisions(self, name):
        return ab.parse_vp(fx(name), self.vocab)

    def verdicts(self, name, date, legislature, resolver=None):
        out = []
        for d in self.divisions(name):
            votes, ok, note = ab.resolve_division(d, resolver or self.r, date, legislature)
            out.append((d, votes, ok, note))
        return out

    def test_the_remote_vote_asterisk_is_a_footnote_mark_not_a_name(self):
        """2 June 2021. The V&P explains its own mark under every list:
        "* Member voted remotely". It follows the name ('Amery*'), stands
        apart from it ('Hanson *', 'Toor *') or wraps onto the next line
        ('Allard' / '* Hunter Rutherford', 'Hanson' / '*'). Every list used
        to stop at the first lone '*'."""
        got = self.verdicts("ab_vp_20210602_remote.txt", "2021-06-02", 30)
        self.assertEqual([(d["yeas"], d["nays"]) for d, _, _, _ in got],
                         [(7, 30), (7, 31), (6, 31), (7, 33), (3, 44)])
        for d, votes, ok, note in got:
            self.assertTrue(ok, (d["seq"], note))
        labels = [v["raw_label"] for v in got[1][1]]
        self.assertIn("Allard*", labels)                 # 'Allard' / '* Hunter ...'
        self.assertIn("Hanson*", labels)                 # 'Hanson' / '*'
        self.assertIn("Hunter", labels)
        self.assertFalse(any("remotely" in l or l.strip() == "*" for l in labels))
        by = {v["raw_label"]: v["member_key"] for v in got[3][1]}
        self.assertEqual(by["Sigurdson (Highwood)*"], "0945")    # R.J. Sigurdson
        self.assertEqual(by["Sigurdson (Edmonton-Riverview)"], "0875")
        self.assertEqual(by["Nixon (Calgary-Klein)*"], "0932")   # Jeremy Nixon

    def test_a_heading_after_the_list_is_not_two_surnames(self):
        """26 Oct 2015: "Intersessional Deposits" follows the Nay list."""
        (d, votes, ok, note), = self.verdicts("ab_vp_20151026_heading.txt", "2015-10-26", 29)
        self.assertEqual((d["yeas"], d["nays"]), (56, 9))
        self.assertNotIn("Intersessional", d["nay_labels"])
        self.assertTrue(ok, note)

    def test_names_read_one_glyph_at_a_time_are_closed_up(self):
        """24 June 2015: "(Leduc-Beaumont) G a n l e y  P a y n e" ended the list at 'Anderson'."""
        (d, votes, ok, note), = self.verdicts("ab_vp_20150624_spaced.txt", "2015-06-24", 29)
        self.assertIn("Ganley", d["nay_labels"])
        self.assertIn("Payne", d["nay_labels"])
        self.assertEqual(len(d["nay_labels"]), 45)
        self.assertTrue(ok, note)

    def test_a_surname_split_by_the_extraction_is_rejoined_only_when_known(self):
        """13 Dec 2017: "Cortes-Vargas La rivee Shepherd"."""
        (d, votes, ok, note), = self.verdicts("ab_vp_20171213_split.txt", "2017-12-13", 29)
        self.assertIn("Larivee", d["yea_labels"])
        self.assertTrue(ok, note)
        self.assertEqual(pn.close_split_names("Cortes-Vargas La rivee Shepherd", {"larivee"}),
                         "Cortes-Vargas Larivee Shepherd")
        # 'van' is a surname token of its own; an unknown join is not made
        self.assertEqual(pn.close_split_names("Orr van Dijken", {"van", "dijken", "orrvan"}),
                         "Orr van Dijken")
        self.assertEqual(pn.close_split_names("La rivee", {"lariviere"}), "La rivee")

    def test_a_header_without_the_article_is_still_a_header(self):
        """22 Apr 2013: "Against amendment:  44"."""
        (d, votes, ok, note), = self.verdicts("ab_vp_20130422_noarticle.txt", "2013-04-22", 28)
        self.assertEqual((d["yeas"], d["nays"], len(d["nay_labels"])), (23, 44, 44))
        self.assertTrue(ok, note)

    def test_a_list_without_a_printed_total_is_read_but_never_trusted(self):
        """3 Dec 2012: the V&P prints "Against the amendment" with no total.
        Hansard gives 29 and the list holds 29, but the V&P's own check is
        missing, so the division stays a gap (config/prov_known_gaps.yaml)."""
        (d, votes, ok, note), = self.verdicts("ab_vp_20121203_nototal.txt", "2012-12-03", 28)
        self.assertEqual((d["yeas"], d["nays"], len(d["nay_labels"])), (9, None, 29))
        self.assertFalse(ok)
        self.assertIn("no printed total", note)

    def test_a_name_the_record_left_out_stays_a_gap(self):
        """13 May 2013: "Against the motion: 14" over 13 names. Hansard's
        list for the same division has Wilson; the V&P dropped him. The check
        is not loosened and no name is supplied."""
        (d, votes, ok, note), = self.verdicts("ab_vp_20130513_misprint.txt", "2013-05-13", 28)
        self.assertFalse(ok)
        self.assertEqual(note, "Nay: 13 name(s) read, 14 printed")

    def test_glasgo_is_michaela_frey_and_the_abbreviated_riding_is_jason_nixon(self):
        """23 May 2019, 80-0. Both from config/prov_record.yaml, reviewed:
        Frey's member page says "Also served under Glasgo"; the V&P writes
        "Rimbey-Rocky Mtn. House-Sundre"."""
        (d, votes, ok, note), = self.verdicts("ab_vp_20190523_glasgo_nixon.txt", "2019-05-23", 30)
        self.assertTrue(ok, note)
        by = {v["raw_label"]: (v["member_key"], v["how"]) for v in votes}
        self.assertEqual(by["Glasgo"], ("0918", "other-surname"))
        self.assertEqual(by["Nixon (Rimbey-Rocky Mtn. House-Sundre)"], ("0892", "surname+riding"))
        self.assertEqual(by["Nixon (Calgary-Klein)"], ("0932", "surname+riding"))
        # Without the reviewed facts, both are gaps, never guesses.
        bare = pn.Resolver.from_conn(self.conn, "ab")
        (_, votes, ok, note), = self.verdicts("ab_vp_20190523_glasgo_nixon.txt", "2019-05-23", 30, bare)
        self.assertFalse(ok)
        self.assertIn("'Glasgo'", note)
        self.assertIn("'Nixon (Rimbey-Rocky Mtn. House-Sundre)'", note)

    def test_an_other_surname_is_still_unique_or_nothing(self):
        members = {"0918": {"surname": "Frey", "given": "Michaela"},
                   "x1": {"surname": "Glasgo", "given": "Someone"}}
        terms = [{"member_key": k, "legislature": 30, "riding": None, "start": "2019-04-16",
                  "end": None} for k in members]
        r = pn.Resolver(members, terms, other_surnames={"0918": ["Glasgo"]})
        key, how = r.resolve("Glasgo", "2019-05-23", 30)
        self.assertIsNone(key)
        self.assertTrue(how.startswith("ambiguous"), how)
        self.assertEqual(r.resolve("Frey", "2019-05-23", 30)[0], "0918")

    def test_reviewed_entries_must_carry_their_evidence(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write('provinces:\n  "ab":\n    other_surnames:\n      - member: "0918"\n'
                     '        surname: "Glasgo"\n')
        try:
            with self.assertRaises(ValueError):
                pn.load_other_surnames("ab", fh.name)
        finally:
            os.unlink(fh.name)
        self.assertEqual([a["surname"] for a in pn.load_other_surnames("ab")], ["Glasgo"])
        self.assertEqual([a["printed"] for a in pn.load_riding_aliases("ab")],
                         ["Rimbey-Rocky Mtn. House-Sundre"])


class DivisionBillTests(unittest.TestCase):
    """Which bill a division decided: three of the six bill-page flags no
    parsed division matched were Standing Order 64 questions "on the
    Appropriation Bill standing on the Order Paper", which name no bill."""

    def bills(self, name):
        return [d["bill_number"] for d in ab.parse_vp(fx(name), set())]

    def test_the_appropriation_bill_is_the_one_the_outcome_line_names(self):
        """28 Apr 2011: Bill 16 was debated last; the question was on Bill 17."""
        self.assertEqual(self.bills("ab_vp_20110428_so64.txt"), ["17"])

    def test_with_two_appropriation_bills_the_main_act_is_meant(self):
        """26 Mar 2026: Bills 19 (Appropriation Act) and 20 (Supplementary
        Supply) are both listed; Bill 20 passed on the voice earlier."""
        self.assertEqual(self.bills("ab_vp_20260326_so64.txt"), ["19"])

    def test_the_outcome_line_never_overrides_a_named_bill(self):
        """9 Dec 2025: a division on adjourning Bill 9's debate, then the line
        "The following Bill was read a Third time and passed: Bill 13" -- the
        report of an earlier division. The division stays on Bill 9."""
        self.assertEqual(self.bills("ab_vp_20251209_adjourn.txt"), ["9"])


class RosterLegislatureTests(unittest.TestCase):
    """Reading the 31st Legislature's roster deleted the member-page terms
    stored for the 29th and 30th: one member page, one delete for ALL of
    that member's terms, re-inserted under the legislature being read. A
    2015-2023 member then held no term in the 30th, and re-reading its
    divisions failed (Rachel Notley, Jason Nixon). Terms are replaced per
    legislature now."""

    def test_replace_terms_can_be_scoped_to_one_legislature(self):
        conn = db.init_db(db.connect(":memory:"))
        for leg in (29, 30, 31):
            ps.replace_terms(conn, "ab", "0791", [{"legislature": leg, "party": "NDP"}],
                             "member-page", legislature=leg)
        ps.replace_terms(conn, "ab", "0791", [{"legislature": 31, "party": "NDP"}],
                         "member-page", legislature=31)
        legs = [r[0] for r in conn.execute("SELECT legislature FROM prov_member_terms ORDER BY 1")]
        self.assertEqual(legs, [29, 30, 31])

    def test_reading_two_rosters_keeps_both_legislatures_terms(self):
        """The 31st roster fixture stands in for both rosters: what is under
        test is that the second read leaves the first one's terms alone."""
        conn = db.init_db(db.connect(":memory:"))
        page = "https://www.assembly.ab.ca/members/members-of-the-legislative-assembly/member-information?mid=0791"
        rows = {r["mid"]: r for r in ab.parse_roster(fx("ab_roster_31.html"))}
        client = _Client({ab.ROSTER.format(30): fx("ab_roster_31.html"),
                          ab.ROSTER.format(31): fx("ab_roster_31.html"),
                          rows["0791"]["href"]: fx("ab_member_0791.html"), page: fx("ab_member_0791.html")})
        ctx = Context(conn, client, "ab", log=lambda *a: None, robots=False)
        ab.fetch_roster(ctx, 30)
        ab.fetch_roster(ctx, 31)
        legs = {r[0] for r in conn.execute(
            "SELECT legislature FROM prov_member_terms WHERE member_key='0791' AND source='member-page'")}
        self.assertEqual(legs, {30, 31})
        r = pn.Resolver.from_conn(conn, "ab")
        self.assertEqual(r.resolve("Notley", "2019-06-05", 30)[0], "0791")


class NameRunTests(unittest.TestCase):
    def test_letter_spacing(self):
        self.assertEqual(pn.close_letter_spacing("(Leduc-Beaumont) G a n l e y  P a y n e "),
                         "(Leduc-Beaumont) Ganley  Payne ")
        self.assertEqual(pn.close_letter_spacing("Sigurdson, R J"), "Sigurdson, R J")

    def test_the_mark_is_kept_on_the_label_and_dropped_from_the_name(self):
        lab = pn.parse_label("Sigurdson (Highwood)*")
        self.assertEqual((lab.tokens, lab.riding), (["sigurdson"], "Highwood"))
        self.assertEqual(pn.split_name_run(["Allard", "* Hunter Rutherford", "van Dijken *"],
                                           {("van", "dijken"), ("allard",), ("hunter",)}),
                         ["Allard*", "Hunter", "Rutherford", "van Dijken*"])
        self.assertFalse(pn.is_name_line("* Member voted remotely", set()))
        self.assertFalse(pn.is_name_line("*Member voted remotely", set()))
        self.assertTrue(pn.is_name_line("*", set()))


if __name__ == "__main__":
    unittest.main()
