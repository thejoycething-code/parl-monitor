"""Ontario (src/ingest/prov_on.py). No network: fixtures in tests/fixtures/prov/.

THE PROOFS (docs/canada-provinces-scope.md):
  * Bill 28, Keeping Students in Class Act, 2022 (the notwithstanding
    clause), third reading on 3 November 2022, carried 74-34 -- Lecce for,
    Fife against -- resolved against the member list printed at the back of
    that day's own Hansard;
  * Bill 77 (2015, conversion practices) passed third reading "Carried." by
    VOICE on 4 June 2015: a voice decision, with no member record.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_on as on  # noqa: E402
from src.prov_fetch import Context, Robots  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
DATE = "2022-11-03"
SESSION_URL = "https://www.ola.org/en/legislative-business/house-documents/parliament-43/session-1/"
HUB = "https://www.ola.org/en/legislative-business/house-documents/parliament-43/session-1/2022-11-03/hansard"
VP = "https://www.ola.org/en/legislative-business/house-documents/parliament-43/session-1/2022-11-03/votes-proceedings"
PDF = "https://www.ola.org/sites/default/files/node-files/hansard/document/pdf/2023/2023-08/03-NOV-2022_L025A.pdf"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def members():
    return on.parse_member_pages([tuple(f) for f in json.loads(fx("on_members_20221103.json"))])


def conn_with_roster(date=DATE, leg=43, drop=()):
    conn = db.init_db(db.connect(":memory:"))
    for m in members():
        if m["key"] in drop:
            continue
        ps.upsert_member(conn, "on", m["key"], name=m["given"] + " " + m["surname"],
                         surname=m["surname"], given=m["given"])
        ps.extend_term(conn, "on", m["key"], leg, m["party"], m["riding"], date, "hansard-cover")
    conn.commit()
    return conn


class ListingTests(unittest.TestCase):
    def test_sessions_sittings_and_the_days_documents(self):
        self.assertEqual(on.session_page(fx("on_house_docs.html"), 43, 1), SESSION_URL)
        self.assertIsNone(on.session_page(fx("on_house_docs.html"), 49, 1))
        sittings = on.list_sittings(fx("on_sittings_43_1.html"), 43, 1)
        self.assertIn((DATE, HUB), sittings)
        self.assertEqual(sittings, sorted(sittings))
        vps, pdf = on.hub_documents(fx("on_hub_20221103.html"), DATE)
        self.assertEqual((vps, pdf), ([VP], PDF))        # the previous day's link is not this day's

    def test_robots_forbids_every_query_string(self):
        r = Robots(fx("on_robots.txt"))
        ua = "CitizenGO-ParlMonitor/1.0 (contact: x)"
        self.assertTrue(r.can_fetch(ua, VP))
        self.assertTrue(r.can_fetch(ua, PDF))
        self.assertFalse(r.can_fetch(ua, "https://www.ola.org/en/members/current?page=2"))
        self.assertFalse(r.can_fetch(ua, "https://www.ola.org/search/node?keys=x"))
        # Allow beats Disallow when it is the longer match
        self.assertTrue(r.can_fetch(ua, "https://www.ola.org/core/misc/a.css?v=1"))
        self.assertFalse(r.can_fetch(ua, "https://www.ola.org/core/misc/readme.txt"))


class MemberListTests(unittest.TestCase):
    def test_the_hansard_member_list_by_column(self):
        ms = members()
        self.assertEqual(len(ms), 123)                  # 124 seats, Hamilton Centre vacant
        by = {m["key"]: m for m in ms}
        self.assertEqual((by["stephen-lecce"]["party"], by["stephen-lecce"]["riding"]), ("PC", "King—Vaughan"))
        self.assertEqual(by["catherine-fife"]["party"], "NDP")
        self.assertEqual(by["mike-schreiner"]["party"], "GRN")
        self.assertEqual(by["bobbi-ann-brady"]["party"], "IND")
        # a member whose party wraps onto the next line
        self.assertEqual(by["prabmeet-singh-sarkaria"]["party"], "PC")
        # a riding that wraps, French name dropped
        self.assertEqual(by["steve-clark"]["riding"], "Leeds—Grenville—Thousand Islands and Rideau Lakes")
        self.assertEqual(by["chandra-pasma"]["riding"], "Ottawa West—Nepean")
        self.assertEqual(by["jennifer-stevens"]["given"], "Jennifer")          # '(Jennie)' dropped
        self.assertEqual(by["raymond-sung-joon-cho"]["riding"], "Scarborough North")


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.conn = conn_with_roster()
        self.r = pn.Resolver.from_conn(self.conn, "on")
        self.divisions, self.voices, self.titles = on.parse_vp(on.vp_events(fx("on_vp_20221103.html")))

    def test_bill_28_third_reading_74_34(self):
        d = [x for x in self.divisions if x["stage"] == "Third Reading"][0]
        self.assertEqual((d["yeas"], d["nays"], d["bill_number"], d["result"]),
                         (74, 34, "28", "Carried on the following division"))
        votes, ok, note = on.resolve_division(d, self.r, DATE, 43)
        self.assertTrue(ok, note)
        by = {v["member_key"]: v for v in votes}
        self.assertEqual((by["stephen-lecce"]["position"], by["stephen-lecce"]["party_at_vote"]), ("Yea", "PC"))
        self.assertEqual((by["catherine-fife"]["position"], by["catherine-fife"]["party_at_vote"]), ("Nay", "NDP"))
        self.assertEqual(by["mike-schreiner"]["position"], "Nay")
        self.assertEqual(by["michael-d-ford"]["raw_label"], "Ford (York South—Weston)")
        self.assertEqual(by["michael-d-ford"]["how"], "surname+riding")

    def test_every_division_of_the_day(self):
        got = [(d["stage"], d["bill_number"], d["yeas"], d["nays"], d["totals_only"]) for d in self.divisions]
        self.assertEqual(got, [("Time Allocation", "28", 78, 33, False),
                               ("Second Reading", "26", 74, 30, True),
                               ("Second Reading", "28", 76, 32, False),
                               ("Third Reading", "28", 74, 34, False)])
        for d in self.divisions:
            votes, ok, note = on.resolve_division(d, self.r, DATE, 43)
            if d["totals_only"]:
                self.assertFalse(ok)
                self.assertEqual(votes, [])
                self.assertTrue(note.startswith("totals only"))
            else:
                self.assertTrue(ok, note)
        by = {v["member_key"]: v for v in on.resolve_division(self.divisions[0], self.r, DATE, 43)[0]}
        self.assertEqual(by["doug-ford"]["raw_label"], "Ford (Etobicoke North)")
        self.assertEqual(by["doug-ford"]["position"], "Yea")
        self.assertEqual(by["jill-andrew"]["position"], "Nay")

    def test_first_readings_are_voice_decisions(self):
        self.assertEqual([(v["bill_number"], v["stage"]) for v in self.voices],
                         [(n, "First Reading") for n in ("30", "31", "32", "33", "34")])
        self.assertEqual(self.titles["30"], "An Act to proclaim Menstrual Health Day")

    def test_bill_28_is_tier_1_by_key_and_its_text_names_the_override(self):
        tax, wl = pc.load_taxonomy(), pc.load_watchlist("on")
        page = on.parse_bill_page(fx("on_bill_28.html"))
        self.assertEqual((page["sponsor"], page["sponsor_slug"]), ("Lecce, Hon. Stephen", "stephen-lecce"))
        res = pc.classify(tax, wl, "on", title="Keeping Students in Class Act, 2022", texts=[page["text"]],
                          bill_key="on-43-1/28")
        self.assertIn("operate notwithstanding", res.terms)
        self.assertEqual((res.areas, res.tier), ([7], 1))
        # without the key, the s.33 formula alone gives no area
        self.assertEqual(pc.classify(tax, wl, "on", texts=[page["text"]]).areas, [])

    def test_a_member_missing_from_the_roster_is_a_gap_with_a_null(self):
        conn = conn_with_roster(drop=("catherine-fife",))
        r = pn.Resolver.from_conn(conn, "on")
        d = self.divisions[-1]
        votes, ok, note = on.resolve_division(d, r, DATE, 43)
        self.assertFalse(ok)
        fife = [v for v in votes if v["raw_label"] == "Fife"][0]
        self.assertIsNone(fife["member_key"])


class LateLayoutTests(unittest.TestCase):
    """Since late 2025: 'table votesList', each name in an English and a
    hidden French div. Read whole, every label came out 'Bell Bell' and the
    tally check refused all of them (live run, 24 November 2025)."""

    def test_each_name_is_read_once(self):
        divisions, _v, _t = on.parse_vp(on.vp_events(fx("on_vp_20251117.html")))
        self.assertEqual(len(divisions), 1)
        d = divisions[0]
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"]), d["bill_number"],
                          d["result"]), (37, 70, 37, 70, "58", "Lost on the following division"))
        self.assertEqual(d["yea_labels"][:3], ["Bell", "Blais", "Bourgouin"])
        self.assertFalse([x for x in d["yea_labels"] + d["nay_labels"] if len(set(x.split())) < len(x.split())])

    def test_a_nil_list_is_a_header_with_no_table(self):
        html = ('<td class="votesProceedingsDoc2col" lang="en"><p>Third Reading of Bill 9, An Act.</p></td>'
                '<td class="votesProceedingsDoc2col" lang="en"><p>Carried on the following division:</p></td>'
                '<h5 class="divisionHeader"><span lang="en">Ayes</span>/<span lang="fr">pour</span> (2)</h5>'
                '<table class="table votesList"><tr><td><div lang="en">Bell</div><div lang="fr">Bell</div></td>'
                '<td><div lang="en">Blais</div><div lang="fr">Blais</div></td></tr></table>'
                '<h5 class="divisionHeader"><span lang="en">Nays</span>/<span lang="fr">contre</span> (0)</h5></div>')
        d = on.parse_vp(on.vp_events(html))[0][0]
        self.assertEqual((d["yeas"], d["nays"], d["yea_labels"], d["nay_labels"], d["problem"]),
                         (2, 0, ["Bell", "Blais"], [], None))


class OldLayoutTests(unittest.TestCase):
    """2015: one table, English cell then French, 'AYES / POUR - 95'."""

    def test_bill_77_passed_on_voice_with_no_member_record(self):
        divisions, voices, titles = on.parse_vp(on.vp_events(fx("on_vp_20150604.html")))
        self.assertEqual([(d["stage"], d["bill_number"], d["yeas"], d["nays"], len(d["yea_labels"]),
                           len(d["nay_labels"])) for d in divisions],
                         [("Third Reading", "6", 95, 0, 95, 0), ("Second Reading", "66", 73, 17, 73, 17)])
        v77 = [v for v in voices if v["bill_number"] == "77"]
        self.assertEqual(v77, [{"bill_number": "77", "stage": "Third Reading", "result": "Carried."}])
        self.assertIn("efforts to change sexual orientation or gender identity", titles["77"])
        tax, wl = pc.load_taxonomy(), pc.load_watchlist("on")
        self.assertIn(4, pc.classify(tax, wl, "on", title=titles["77"]).areas)

    def test_a_list_continued_over_a_page_is_one_list(self):
        html = ('<table><tr><td colspan="2"><p>Second Reading of Bill 9, An Act.</p></td><td colspan="2"><p>x</p></td></tr>'
                '<tr><td colspan="2"><p>Carried on the following division:-</p></td><td colspan="2"><p>y</p></td></tr>'
                '<tr><td colspan="4"><p>AYES / POUR - 3</p></td></tr><tr><td colspan="4"></td></tr>'
                '<tr><td><p>Albanese</p><p>Arnott</p></td></tr>'
                '<tr><td colspan="6"><p>AYES / POUR - Continued</p></td></tr>'
                '<tr><td><p>Miller (Parry Sound-Muskoka)</p></td><td/></tr>'
                '<tr><td colspan="5"><p>NAYS / CONTRE - 0</p></td><td rowspan="3"></td></tr>'
                '<tr><td colspan="2"><p>Referred to the Committee.</p></td><td colspan="2"><p>z</p></td></tr></table>')
        d = on.parse_vp(on.vp_events(html))[0][0]
        self.assertEqual((d["yeas"], d["nays"], d["yea_labels"], d["nay_labels"]),
                         (3, 0, ["Albanese", "Arnott", "Miller (Parry Sound-Muskoka)"], []))


def frags_of(name):
    return [tuple(f) for f in json.loads(fx(name))]


class BackfillCoverTests(unittest.TestCase):
    """The 2010 backfill (2 October 2026) read 27-33 of 107 members from
    every 2010-2012 cover, 72 from 2013-2014's, none from several 2018-2023
    ones, and dropped the last member of each page from 2018 on. Each
    fixture is a real Hansard's member-list pages, as pdf_fragments reads
    them."""

    def test_2010_one_fragment_per_row_is_split_after_the_party(self):
        ms = on.parse_member_pages(frags_of("on_members_20100323.json"))
        self.assertEqual(len(ms), 107)                  # was 31: only rows drawn in pieces
        by = {m["key"]: m for m in ms}
        # 'Albanese, Laura (LIB) York South–Weston / York-Sud–' + 'Weston'
        self.assertEqual((by["laura-albanese"]["party"], by["laura-albanese"]["riding"]),
                         ("LIB", "York South–Weston"))
        # the riding and a responsibility in one fragment
        self.assertEqual(by["sophia-aggelonitis"]["riding"], "Hamilton Mountain")
        self.assertEqual(by["christopher-bentley"]["riding"], "London West")
        self.assertEqual(by["andrea-horwath"]["riding"], "Hamilton Centre")
        self.assertEqual(by["dwight-duncan"]["riding"], "Windsor–Tecumseh")
        # the two Millers the V&P tells apart by riding
        self.assertEqual((by["norm-miller"]["party"], by["norm-miller"]["riding"]), ("PC", "Parry Sound–Muskoka"))
        self.assertEqual(by["paul-miller"]["riding"], "Hamilton East–Stoney Creek")
        for m in ms:
            self.assertNotRegex(m["riding"] or "", r"Minister|Chair|Leader|Speaker|Deputy|/")

    def test_2014_a_header_drawn_in_pieces(self):
        # 'Member and ' + 'Party / ': the first page (Albanese to Gélinas) was skipped
        ms = on.parse_member_pages(frags_of("on_members_20140225_p1.json"))
        self.assertEqual((len(ms), ms[0]["key"], ms[-1]["key"]), (35, "laura-albanese", "france-gelinas"))
        # 'Member and Pa' + 'rty /' (25 October 2021): 0 of the page's 32 before
        ms = on.parse_member_pages(frags_of("on_members_20211025_p1.json"))
        self.assertEqual((len(ms), ms[0]["key"], ms[-1]["key"]), (32, "deepak-anand", "catherine-fife"))

    def test_2018_fragments_pypdf_places_at_the_origin(self):
        frags = frags_of("on_members_20180730.json")
        self.assertTrue([f for f in frags if f[1] == 0 and f[2] == 0])
        ms = on.parse_member_pages(frags)
        self.assertEqual(len(ms), 124)                  # was 0: x=0 became the commonest column
        by = {m["key"]: m for m in ms}
        # the dash's continuation is joined, with no space
        self.assertEqual(by["deepak-anand"]["riding"], "Mississauga—Malton")
        self.assertEqual(by["jeff-yurek"]["riding"], "Elgin—Middlesex—London")
        # each page's last member: the origin line once ran into them
        pages = sorted({f[0] for f in frags})
        last = [on.parse_member_pages([f for f in frags if f[0] == p])[-1]["key"] for p in pages]
        self.assertEqual(last, ["jennifer-k-french", "taras-natyshak", "jeff-yurek"])

    def test_words_drawn_apart_keep_their_space(self):
        # 'Thompson, Lisa' + 'M. (PC)' (3 October 2013) was 'LisaM.', a second
        # key for Lisa Thompson; the fragment's end, from its glyph widths,
        # tells a gap from a word in pieces
        frags = frags_of("on_members_20131003_p3.json")
        self.assertIn("lisa-m-thompson", [m["key"] for m in on.parse_member_pages(frags)])
        self.assertIn("lisam-thompson", [m["key"] for m in on.parse_member_pages([f[:4] for f in frags])])

    def test_spaces_inside_a_name_and_a_header_in_pieces(self):
        # 12 November 2018: 'M' + 'ember and Party / ', 0 members before
        ms = on.parse_member_pages(frags_of("on_members_20181112_p1.json"))
        self.assertEqual((len(ms), ms[0]["key"], ms[-1]["key"]), (35, "deepak-anand", "jennifer-k-french"))
        # 18 December 2018: 'Bis s on, Gilles', 'E lliott', 'Fed eli', 'Des R osi ers'
        ms = on.parse_member_pages(frags_of("on_members_20181218_p1.json"))
        keys = [m["key"] for m in ms]
        for k in ("gilles-bisson", "christine-elliott", "victor-fedeli", "nathalie-des-rosiers"):
            self.assertIn(k, keys)
        self.assertEqual({m["surname"] for m in ms if m["key"] == "gilles-bisson"}, {"Bisson"})

    def test_one_seat_one_key(self):
        conn = db.init_db(db.connect(":memory:"))
        for key, given, date in (("kevin-daniel-flynn", "Kevin Daniel", "2013-03-20"),
                                 ("kevindaniel-flynn", "KevinDaniel", "2013-10-03")):
            ps.upsert_member(conn, "on", key, name=given + " Flynn", surname="Flynn", given=given)
            ps.extend_term(conn, "on", key, 40, "LIB", "Oakville", date, "hansard-cover")
        ps.extend_term(conn, "on", "kevin-daniel-flynn", 40, "LIB", "Oakville", "2013-11-27", "hansard-cover")
        ps.store_division(conn, {"division_key": "on-40-2-2013-10-03-1", "prov": "on", "kind": "recorded",
                                 "date": "2013-10-03", "positions_ok": 1, "votes": [
                                     {"position": "Yea", "ordinal": 1, "raw_label": "Flynn",
                                      "member_key": "kevindaniel-flynn"}]})
        ps.store_division(conn, {"division_key": "on-40-2-2013-03-20-1", "prov": "on", "kind": "recorded",
                                 "date": "2013-03-20", "positions_ok": 1, "votes": [
                                     {"position": "Yea", "ordinal": 1, "raw_label": "Flynn",
                                      "member_key": "kevin-daniel-flynn"},
                                     {"position": "Yea", "ordinal": 2, "raw_label": "Flynn",
                                      "member_key": "kevin-daniel-flynn"}]})
        # both valid on a day between: 'Flynn' was ambiguous
        r = pn.Resolver.from_conn(conn, "on")
        self.assertTrue(r.resolve("Flynn", "2013-10-03", 40)[1].startswith("ambiguous"))
        done = on.merge_split_members(conn, log=lambda *a: None)
        self.assertEqual(done, [("kevin-daniel-flynn", ["kevindaniel-flynn"])])     # most votes kept
        self.assertEqual([tuple(x) for x in conn.execute("SELECT DISTINCT member_key FROM prov_votes")],
                         [("kevin-daniel-flynn",)])
        self.assertEqual([tuple(x) for x in conn.execute("SELECT start, end FROM prov_member_terms")],
                         [("2013-03-20", "2013-11-27")])
        r = pn.Resolver.from_conn(conn, "on")
        self.assertEqual(r.resolve("Flynn", "2013-10-03", 40)[0], "kevin-daniel-flynn")
        # a cover printing him the glued way again is stored under the kept key
        seats = on.seat_holders(conn, 40)
        m = {"key": "kevindaniel-flynn", "surname": "Flynn", "given": "KevinDaniel", "riding": "Oakville"}
        self.assertEqual(on.canonical_key(conn, m, seats, 40), "kevin-daniel-flynn")
        # another legislature's seat, or another riding, is not his
        self.assertEqual(on.canonical_key(conn, m, seats, 41), "kevindaniel-flynn")
        self.assertEqual(on.canonical_key(conn, dict(m, riding="Burlington"), seats, 40), "kevindaniel-flynn")
        self.assertEqual(on.merge_split_members(conn, log=lambda *a: None), [])        # idempotent

    def test_a_days_cover_is_read_whenever_the_day_is_read(self):
        # The store held terms starting on 23 March 2010 from the 31-member
        # read; a re-read must read the cover again, once per run.
        conn = db.init_db(db.connect(":memory:"))
        ps.extend_term(conn, "on", "sophia-aggelonitis", 39, "LIB", "Hamilton Mountain Minister of Consumer "
                       "Services", "2010-03-23", "hansard-cover")
        asked = []
        frags = frags_of("on_members_20100323.json")
        saved = on.pdf_fragments
        on.pdf_fragments = lambda raw, pages=None, want=None, extents=False: frags
        try:
            class C:
                def bytes(self, url, slug):
                    asked.append(url)
                    return b"%PDF-"
            ctx = C()
            ctx.conn, ctx.gap = conn, lambda g: None
            self.assertEqual(on.roster_for_day(ctx, 39, "2010-03-23", "https://x/L006.pdf"), 107)
            self.assertEqual(on.roster_for_day(ctx, 39, "2010-03-23", "https://x/L006.pdf"), 107)
        finally:
            on.pdf_fragments = saved
        self.assertEqual(asked, ["https://x/L006.pdf"])
        r = pn.Resolver.from_conn(conn, "on")
        self.assertEqual(r.resolve("Albanese", "2010-03-23", 39)[0], "laura-albanese")


class BackfillVPTests(unittest.TestCase):
    """Votes and Proceedings layouts the 2010 backfill misread. Real pages,
    trimmed to the proceedings."""

    def parse(self, name):
        return on.parse_vp(on.vp_events(fx(name)))[0]

    def test_totals_in_a_paragraph_of_their_own_are_a_totals_only_division(self):
        # "Lost on the following division:-" then "AYES - 19 NAYS - 42": five
        # divisions the record names, none stored, the day a gap.
        ds = self.parse("on_vp_20120403_totals.html")
        self.assertEqual([(d["yeas"], d["nays"], d["totals_only"]) for d in ds],
                         [(19, 42, True), (22, 42, True), (24, 43, True), (21, 37, True), (49, 1, True)])
        self.assertEqual((ds[0]["stage"], ds[0]["bill_number"], ds[0]["result"]),
                         ("Second Reading", "13", "Lost on the following division"))
        votes, ok, note = on.resolve_division(ds[0], pn.Resolver({}, []), "2012-04-03", 40)
        self.assertEqual((votes, ok), ([], False))
        self.assertTrue(note.startswith("totals only"))

    def test_a_capitalised_heading_ends_a_list(self):
        ds = self.parse("on_vp_20100531_heading.html")
        self.assertEqual(len(ds), 9)                    # 1 parsed before, the record says 9
        d = ds[0]
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"])), (39, 17, 39, 17))
        self.assertNotIn("PETITIONS", d["nay_labels"])
        self.assertEqual(d["nay_labels"][-1], "Yakabuski")
        # "..., which motion was lost on the following division:-"
        self.assertEqual(ds[1]["result"], "lost on the following division")
        self.assertEqual(d["result"], "carried on the following division")

    def test_the_same_header_printed_again_continues_the_list(self):
        # 6 June 2019, Bill 115: "AYES / POUR - 68" a second time over a page
        d = self.parse("on_vp_20190606_repeat.html")[0]
        self.assertEqual((d["bill_number"], d["yeas"], len(d["yea_labels"]), d["nays"], len(d["nay_labels"])),
                         ("115", 68, 68, 46, 46))
        self.assertEqual(d["yea_labels"][-4:], ["Wai", "Walker", "Yakabuski", "Yurek"])

    def test_a_total_and_continued_on_one_header(self):
        # "NAYS / CONTRE – 50 - Continued" (19 April 2016): 36 of 50 read before
        d = self.parse("on_vp_20160419_continued.html")[2]
        self.assertEqual((d["nays"], len(d["nay_labels"])), (50, 50))
        self.assertEqual(d["nay_labels"][-3:], ["Wong", "Wynne", "Zimmer"])

    def test_the_43rd_parliaments_first_weeks_without_lang(self):
        # 10 August 2022: no lang on the cells, the names in a 'drum-table'
        ds = self.parse("on_vp_20220810_nolang.html")
        self.assertEqual(len(ds), 1)
        d = ds[0]
        self.assertEqual((d["yeas"], len(d["yea_labels"]), d["nays"], len(d["nay_labels"]), d["result"]),
                         (78, 78, 26, 26, "Carried on the following division"))
        self.assertIn("Ford (York South—Weston)", d["yea_labels"])
        # the English cell only: no French paragraph in the question
        self.assertNotIn("Adoptée", d["question"] or "")

    def test_a_page_pasted_from_word(self):
        # 30 April 2025: <p class="votesProceedingsDocdivisionHeader"> and the
        # French twin in a docHide paragraph; 0 of the day's 1 division before
        ds = self.parse("on_vp_20250430_word.html")
        self.assertEqual(len(ds), 1)
        d = ds[0]
        self.assertEqual((d["yeas"], len(d["yea_labels"]), d["nays"], len(d["nay_labels"])), (35, 35, 68, 68))
        self.assertEqual((d["yea_labels"][0], d["nay_labels"][0]), ("Armstrong", "Allsopp"))
        self.assertFalse([x for x in d["yea_labels"] + d["nay_labels"] if len(set(x.split())) < len(x.split())])

    def test_lost_of_the_following_division(self):
        ds = self.parse("on_vp_20221128_lostof.html")
        self.assertEqual([(d["bill_number"], d["result"]) for d in ds][-1],
                         ("4", "Lost of the following division"))
        ev = on.vp_events(fx("on_vp_20221128_lostof.html"))
        self.assertEqual(len(on._DIVISION_SAID.findall(" ".join(e[1] for e in ev if e[0] == "p"))), len(ds))


class MisprintTests(unittest.TestCase):
    """The V&P printed "Cuzzeto" for Rudy Cuzzetto from July 2018 to July
    2020 (config/prov_record.yaml, misprints)."""
    VP = "https://www.ola.org/en/legislative-business/house-documents/parliament-42/session-1/2018-07-25/votes-proceedings"

    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        for m in on.parse_member_pages(frags_of("on_members_20180730.json")):
            ps.upsert_member(self.conn, "on", m["key"], name=m["given"] + " " + m["surname"],
                             surname=m["surname"], given=m["given"])
            for d in ("2018-07-25", "2020-07-21"):
                ps.extend_term(self.conn, "on", m["key"], 42, m["party"], m["riding"], d, "hansard-cover")
        self.r = on.make_resolver(self.conn)
        self.ds = on.parse_vp(on.vp_events(fx("on_vp_20180725_cuzzeto.html")))[0]

    def test_both_divisions_tally_with_the_misprint_read(self):
        for d in self.ds:
            self.assertIn("Cuzzeto", d["yea_labels"] + d["nay_labels"])
            votes, ok, note = on.resolve_division(d, self.r, "2018-07-25", 42, document=self.VP)
            self.assertTrue(ok, note)
            cz = [v for v in votes if v["raw_label"] == "Cuzzeto"][0]
            self.assertEqual((cz["member_key"], cz["how"]),
                             ("rudy-cuzzetto", "alias (reviewed, config/prov_record.yaml)"))

    def test_only_inside_its_span_and_its_documents(self):
        self.assertIsNone(self.r.resolve("Cuzzeto", "2018-07-25", 42)[0])            # no document named
        self.assertIsNone(self.r.resolve("Cuzzeto", "2018-07-25", 42, document="https://x/vp")[0])
        other = self.VP.replace("parliament-42/session-1", "parliament-43/session-1")
        self.assertIsNone(self.r.resolve("Cuzzeto", "2018-07-25", 42, document=other)[0])
        self.assertEqual(self.r.resolve("Cuzzeto", "2020-07-21", 42, document=self.VP)[0], "rudy-cuzzetto")
        # the correct spelling resolves on its own, never through the entry
        self.assertEqual(self.r.resolve("Cuzzetto", "2018-07-25", 42), ("rudy-cuzzetto", "surname"))

    def test_a_misprint_without_its_evidence_is_refused(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write('provinces:\n  "on":\n    misprints:\n      - {printed: "Cuzzeto", member: rudy-cuzzetto, '
                     'from: 2018-07-19, to: 2020-07-21}\n')
        try:
            with self.assertRaises(ValueError):
                pn.load_misprints("on", fh.name)
        finally:
            os.unlink(fh.name)


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
    def setUp(self):
        self._frags = on.pdf_fragments
        frags = [tuple(f) for f in json.loads(fx("on_members_20221103.json"))]
        on.pdf_fragments = lambda raw, pages=None, want=None, extents=False: frags

    def tearDown(self):
        on.pdf_fragments = self._frags

    def pages(self):
        bills = on.BILLS.format(43, 1)
        return {"https://www.ola.org/robots.txt": fx("on_robots.txt"),
                on.HOUSE_DOCS: fx("on_house_docs.html"), SESSION_URL: fx("on_sittings_43_1.html"),
                HUB: fx("on_hub_20221103.html"), VP: fx("on_vp_20221103.html"), PDF: "%PDF-",
                bills: fx("on_bills_43_1.html"),
                "https://www.ola.org/en/legislative-business/bills/parliament-43/session-1/bill-28": fx("on_bill_28.html")}

    def test_the_proof_lands_in_the_store(self):
        conn = db.init_db(db.connect(":memory:"))
        client = _Client(self.pages())
        ctx = Context(conn, client, "on", since=DATE, until=DATE, log=lambda *a: None)
        stats = on.collect(ctx, session="43-1")
        self.assertEqual((stats["records_read"], stats["divisions"], stats["tally_gaps"]), (1, 4, 0))
        row = conn.execute("SELECT bill_key, stage, yeas, nays, positions_ok, areas FROM prov_divisions "
                           "WHERE division_key='on-43-1-2022-11-03-4'").fetchone()
        self.assertEqual(tuple(row), ("on-43-1/28", "Third Reading", 74, 34, 1, "[7]"))
        lecce = conn.execute("SELECT position, party_at_vote FROM prov_votes WHERE member_key='stephen-lecce' "
                             "AND division_key='on-43-1-2022-11-03-4'").fetchone()
        self.assertEqual(tuple(lecce), ("Yea", "PC"))
        bill = conn.execute("SELECT title_en, sponsor_key, text_read FROM prov_bills WHERE bill_key='on-43-1/28'").fetchone()
        self.assertEqual(tuple(bill), ("Keeping Students in Class Act, 2022", "stephen-lecce", 1))
        # no query-string URL was ever asked for
        self.assertFalse([u for u in client.asked if "?" in u])
        s = ps.summary(conn, "on")
        self.assertEqual((s["recorded_ok"], s["recorded_gap"], s["recorded_totals_only"]), (3, 0, 1))
        # bills named by the day but absent from the trimmed fixtures are said
        # out loud, never skipped silently; nothing else is a gap
        self.assertTrue(ctx.gaps)
        self.assertTrue(all("bills page" in g or "/bill-" in g for g in ctx.gaps), ctx.gaps)
        # resume: the day is done
        self.assertEqual(on.collect(ctx, session="43-1", bills=False)["records_read"], 0)

    def test_a_hub_without_votes_and_proceedings_is_a_gap(self):
        conn = db.init_db(db.connect(":memory:"))
        pages = self.pages()
        pages[HUB] = "<html></html>"
        ctx = Context(conn, _Client(pages), "on", since=DATE, until=DATE, log=lambda *a: None)
        stats = on.collect(ctx, session="43-1", bills=False)
        self.assertEqual(stats["tally_gaps"], 1)
        self.assertIn("names no Votes and Proceedings", ctx.gaps[0])


if __name__ == "__main__":
    unittest.main()
