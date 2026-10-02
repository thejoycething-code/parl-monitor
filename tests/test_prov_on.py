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
        on.pdf_fragments = lambda raw, pages=None, want=None: frags

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
