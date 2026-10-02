"""New Brunswick (src/ingest/prov_nb.py). No network: fixtures in tests/fixtures/prov/.

THE PROOF (docs/canada-provinces-scope.md): on 15 June 2023 Motion 50 as
amended, on Policy 713, carried 26-20 -- Holt and the PC rebels Holder and
Shephard for, Higgs and Hogan against -- resolved against the members page
of that session's compiled Journal. The same day Bill 52, the Human Organ
and Tissue Donation Act, passed third reading on voice: no member record.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_nb as nb  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
DATE = "2023-06-15"
JOURNAL = "https://www.legnb.ca/content/house_business/60/2/journals/47230615e2.pdf"
COMPILED = "https://www.legnb.ca/content/house_business/60/2/journals/Journal_60-2_2022-2023-E.pdf"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def roster_602():
    return nb.parse_compiled_roster(json.loads(fx("nb_roster_602_rows.json")))


def conn_602():
    conn = db.init_db(db.connect(":memory:"))
    rows = nb.terms_from_compiled(roster_602(), 60, "2022-10-25", "2023-10-17")
    by = {}
    for m, t in rows:
        by.setdefault(m["key"], (m, []))[1].append(t)
    for key, (m, terms) in by.items():
        ps.upsert_member(conn, "nb", key, name=m["name"], surname=m["surname"], given=nb.clean_given(m["given"]))
        ps.replace_terms(conn, "nb", key, terms, "journal-60-2")
    conn.commit()
    return conn


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
        page = self.get_text(url, feed, slug)
        return page if isinstance(page, bytes) else page.encode()


class ListingTests(unittest.TestCase):
    def test_file_names_come_from_the_listing_backslashes_turned(self):
        got = nb.list_records(fx("nb_journals_602.html"))
        self.assertEqual(got["compiled"], COMPILED)
        by = {r["date"]: r for r in got["daily"]}
        self.assertEqual(by[DATE]["url"], JOURNAL)                 # the 'e2' revision, as listed
        self.assertEqual((by[DATE]["sitting"], by[DATE]["revision"]), (47, 2))
        self.assertTrue(all("/journals/" in r["url"] and "\\" not in r["url"] for r in got["daily"]))
        self.assertTrue(all(r["url"].endswith("e.pdf") or r["url"].endswith("e2.pdf") for r in got["daily"]))


class RosterTests(unittest.TestCase):
    def test_the_compiled_journal_names_its_session_and_its_by_elections(self):
        r = roster_602()
        self.assertEqual(r["session"], (60, 2))
        self.assertEqual(r["problems"], [])
        self.assertEqual(len(r["members"]), 49)
        by = {m["key"]: m for m in r["members"]}
        self.assertEqual((by["dorothy-shephard"]["surname"], by["dorothy-shephard"]["given"]), ("Shephard", "K. Dorothy"))
        self.assertEqual(by["jean-claude-d-amours"]["given"], "Jean-Claude")       # "(JC)" dropped
        self.assertEqual(by["andrea-anderson-mason"]["surname"], "Anderson-Mason")     # ', K.C.' dropped
        self.assertEqual(by["tammy-scott-wallace"]["surname"], "Scott-Wallace")        # 'Scott -Wallace' closed
        self.assertEqual(by["susan-holt"]["riding"], "Bathurst East-Nepisiguit-Saint Isidore")
        self.assertEqual([n["vice"] for n in r["notes"]], ["Denis Landry", "Roger Melanson", "Daniel Guitar"])

    def test_terms_start_at_the_by_election_and_end_at_the_resignation(self):
        rows = nb.terms_from_compiled(roster_602(), 60, "2022-10-25", "2023-10-17")
        terms = {m["key"]: t for m, t in rows}
        self.assertEqual((terms["susan-holt"]["start"], terms["susan-holt"]["end"]), ("2023-04-24", "2023-10-17"))
        self.assertEqual((terms["denis-landry"]["start"], terms["denis-landry"]["end"]), ("2022-10-25", "2022-11-30"))
        self.assertNotIn("roger-melanson", terms)        # resigned 21 Oct 2022, before the session opened
        self.assertTrue(all(t["party"] is None and t["party_dated"] == 0 for _, t in rows))

    def test_a_compiled_journal_for_another_session_is_refused(self):
        conn = db.init_db(db.connect(":memory:"))
        saved = nb.roster_rows
        nb.roster_rows = lambda raw: json.loads(fx("nb_roster_602_rows.json"))
        try:
            ctx = Context(conn, _Client({"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                                         "https://x/compiled.pdf": b"%PDF-x"}), "nb", log=lambda *a: None)
            n = nb.fetch_roster(ctx, 60, 3, {"daily": [{"date": "2023-10-17"}], "compiled": "https://x/compiled.pdf"})
        finally:
            nb.roster_rows = saved
        self.assertEqual(n, 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_member_terms").fetchone()[0], 0)
        self.assertTrue(any("is for session (60, 2), not this one" in g for g in ctx.gaps))

    def test_the_current_members_page_has_party_but_no_dates(self):
        rows = nb.parse_current_members(fx("nb_members_current.html"))
        by = {r["key"]: r for r in rows}
        self.assertEqual(by["claire-johnson"]["party"], "Liberal Party")
        self.assertEqual(by["margaret-johnson"]["party"], "Progressive Conservative Party")
        self.assertEqual(by["kevin-russell"]["riding"], "Miramichi West")

    def test_m_after_an_honorific_is_an_initial_not_monsieur(self):
        lab = pn.parse_label("Mr. M. LeBlanc")
        self.assertEqual((lab.tokens, lab.initials), (["leblanc"], "m"))
        self.assertEqual(pn.parse_label("M. Savoie").tokens, ["savoie"])


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.conn = conn_602()
        self.r = pn.Resolver.from_conn(self.conn, "nb")
        self.divisions, self.voices = nb.parse_journal(fx("nb_journal_230615.txt"))

    def test_five_recorded_divisions_all_tally(self):
        got = [(d["yeas"], d["nays"], d["vote_on"], d["stage"], d["bill_number"], d["motion"]) for d in self.divisions]
        self.assertEqual(got, [(27, 20, "motion", "Second Reading", "46", None),
                               (20, 26, "amendment", "Motion", None, "49"),
                               (25, 20, "motion", "Motion", None, "49"),
                               (26, 20, "amendment", "Motion", None, "50"),
                               (26, 20, "motion", "Motion", None, "50")])
        for d in self.divisions:
            _votes, ok, note = nb.resolve_division(d, self.r, DATE, 60)
            self.assertTrue(ok, note)

    def test_policy_713_motion_carried_26_20_with_the_pc_rebels(self):
        d = self.divisions[-1]
        self.assertEqual(d["result"], "Motion 50 as amended was resolved in the affirmative")
        votes, ok, _ = nb.resolve_division(d, self.r, DATE, 60)
        self.assertTrue(ok)
        side = {v["member_key"]: v["position"] for v in votes}
        for k in ("susan-holt", "trevor-holder", "dorothy-shephard", "dominic-cardy"):
            self.assertEqual(side[k], "Yea", k)
        for k in ("blaine-higgs", "bill-hogan", "mary-wilson", "rejean-savoie", "glen-savoie"):
            self.assertEqual(side[k], "Nay", k)
        how = {v["raw_label"]: v["how"] for v in votes}
        self.assertEqual(how["Ms. M. Wilson"], "initial")              # not 'M.' for Monsieur
        self.assertTrue(all(v["party_at_vote"] is None for v in votes))  # no dated party in NB
        res = pc.classify(pc.load_taxonomy(), pc.load_watchlist("nb"), "nb", texts=[d["item"]])
        self.assertIn(6, res.areas)
        self.assertIn("Policy 713", res.terms)

    def test_bill_52_passed_on_voice_and_bill_30_was_listed_read(self):
        self.assertEqual([(v["bill_number"], v["stage"]) for v in self.voices],
                         [("52", "Third Reading"), ("30", "Third Reading")])
        self.assertIn("resolved in the affirmative", self.voices[0]["result"])

    def test_a_unanimous_division_prints_yeas_only(self):
        """8 June 2023, Motion 36 as amended: YEAS - 44 and no NAYS list. No
        NAYS total is printed, so none is checked; the 44 must all resolve."""
        divisions, _ = nb.parse_journal(fx("nb_journal_230608.txt"))
        d = divisions[0]
        self.assertEqual((d["yeas"], d["nays"], d["problem"], d["note"]), (44, None, None, "no NAYS list printed (unanimous)"))
        _votes, ok, note = nb.resolve_division(d, pn.Resolver.from_conn(conn_602(), "nb"), "2023-06-08", 60)
        self.assertTrue(ok, note)

    def test_the_bill_is_the_items_own_not_the_one_before_it(self):
        """16 June 2023: Bill 32's third reading carried on voice just before
        the item 'The Order being read for third reading of Bill 37 ... on
        the following recorded division'. The division is Bill 37's."""
        divisions, voices = nb.parse_journal(fx("nb_journal_230616.txt"))
        self.assertEqual([(d["yeas"], d["nays"], d["stage"], d["bill_number"]) for d in divisions],
                         [(44, 3, "Motion", None), (28, 18, "Third Reading", "37"),
                          (28, 19, "Third Reading", "40"), (28, 19, "Third Reading", "45")])
        self.assertIn(("32", "Third Reading"), [(v["bill_number"], v["stage"]) for v in voices])
        r = pn.Resolver.from_conn(conn_602(), "nb")
        for d in divisions:
            _votes, ok, note = nb.resolve_division(d, r, "2023-06-16", 60)
            self.assertTrue(ok, note)

    def test_a_typo_in_a_name_list_is_a_gap_never_a_guess(self):
        conn = db.init_db(db.connect(":memory:"))
        for m in json.loads(fx("nb_members_61.json")):
            ps.upsert_member(conn, "nb", m["key"], surname=m["surname"], given=m["given"])
            ps.replace_terms(conn, "nb", m["key"], [{"legislature": 61, "party": m["party"],
                                                    "riding": m["riding"], "party_dated": 0}], "roster")
        r = pn.Resolver.from_conn(conn, "nb")
        divisions, voices = nb.parse_journal(fx("nb_journal_260526.txt"))
        self.assertEqual([(d["yeas"], d["nays"], d["vote_on"], d["stage"], d["bill_number"]) for d in divisions],
                         [(13, 26, "amendment", "Second Reading", "40")])
        self.assertEqual(voices[0], {"bill_number": "40", "stage": "Second Reading", "result":
                                     "question being put that Bill 40 be now read a second time, "
                                     "it was resolved in the affirmative."})
        _v, ok, note = nb.resolve_division(divisions[0], r, "2026-05-26", 61)
        self.assertTrue(ok, note)
        # 20 November 2025 prints 'Mr. Russel' (Kevin Russell): unresolved, so a gap
        d = dict(divisions[0], yea_labels=[("Mr. Russel" if x == "Mr. Russell" else x)
                                          for x in divisions[0]["yea_labels"]])
        votes, ok, note = nb.resolve_division(d, r, "2026-05-26", 61)
        self.assertFalse(ok)
        self.assertIn("unresolved 'Mr. Russel'", note)
        self.assertIsNone(next(v for v in votes if v["raw_label"] == "Mr. Russel")["member_key"])


class BillTests(unittest.TestCase):
    def test_the_listing_gives_stage_dates_and_the_page_gives_the_english_text(self):
        bills = {b["number"]: b for b in nb.parse_bill_list(fx("nb_bills_602.html"))}
        self.assertEqual([(s["stage"], s["status"], s["date"]) for s in bills["52"]["stages"]],
                         [("First Reading", "Introduced", "2023-05-10"), ("Second Reading", "Passed", "2023-05-11"),
                          ("Third Reading", "Passed", "2023-06-15"), ("Royal Assent", "Received", "2023-06-16")])
        self.assertEqual(bills["56"]["stages"][1], {"stage": "Second Reading", "status": "Defeated", "date": "2023-06-08"})
        page = nb.parse_bill_page(fx("nb_bill52_page.html"))
        self.assertEqual(page["bill_type"], "Private Member Public Bill")
        self.assertEqual(page["sponsor_party"], "Liberal Party")
        self.assertEqual(page["text_url"], "https://www.legnb.ca/content/house_business/60/2/bills/Bill-52-e.htm")

    def test_bill_52_is_watched_for_area_13(self):
        res = pc.classify(pc.load_taxonomy(), pc.load_watchlist("nb"), "nb",
                          title="Human Organ and Tissue Donation Act", bill_key="nb-60-2/52")
        self.assertIn(13, res.areas)
        self.assertEqual(res.tier, 1)


class CollectTests(unittest.TestCase):
    def setUp(self):
        self._pdf = nb.pdf_text
        texts = {b"%PDF-journal": fx("nb_journal_230615.txt")}

        def fake(raw, pages=None):
            if raw not in texts:
                raise nb.Unreadable("truncated PDF: no %%EOF marker in {0} bytes".format(len(raw)))
            return texts[raw]
        nb.pdf_text = fake

    def tearDown(self):
        nb.pdf_text = self._pdf

    def _ctx(self, conn, pages):
        pages = dict(pages, **{"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\ncrawl-delay: 10\n"})
        return Context(conn, _Client(pages), "nb", since=DATE, until=DATE, log=lambda *a: None)

    def test_the_day_lands_in_the_store_and_the_listing_agrees(self):
        conn = conn_602()
        for b in nb.parse_bill_list(fx("nb_bills_602.html")):
            ps.store_bill(conn, {"bill_key": ps.bill_key("nb", 60, 2, b["number"]), "prov": "nb",
                                 "legislature": 60, "session": 2, "number": b["number"],
                                 "title_en": b["title"], "stages": b["stages"],
                                 "areas": [13] if b["number"] == "52" else []})
        ctx = self._ctx(conn, {JOURNAL: b"%PDF-journal"})
        ctx.tax = pc.load_taxonomy()
        resolver = pn.Resolver.from_conn(conn, "nb")
        n, gaps = nb.read_sitting(ctx, 60, 2, {"date": DATE, "url": JOURNAL}, resolver, pc.load_watchlist("nb"))
        self.assertEqual((n, gaps), (5, 0))
        rows = conn.execute("SELECT division_key, kind, stage, bill_key, yeas, nays, positions_ok "
                            "FROM prov_divisions ORDER BY division_key").fetchall()
        self.assertIn(("nb-60-2-2023-06-15-5", "recorded", "Motion", None, 26, 20, 1), [tuple(r) for r in rows])
        voice = conn.execute("SELECT kind, yeas, positions_ok, areas FROM prov_divisions "
                             "WHERE division_key='nb-60-2-2023-06-15-v52-3r'").fetchone()
        self.assertEqual(tuple(voice), ("voice", None, None, "[13]"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_votes v JOIN prov_divisions d USING (division_key) "
                                      "WHERE d.kind='voice'").fetchone()[0], 0)
        # Bills 46 (2R, divided), 52 (3R, voice) and 30 (3R, listed) are all found
        self.assertEqual(nb.check_listing_stages(ctx, 60, 2, {DATE}), 0)
        conn.execute("DELETE FROM prov_divisions WHERE division_key='nb-60-2-2023-06-15-v52-3r'")
        self.assertEqual(nb.check_listing_stages(ctx, 60, 2, {DATE}), 1)
        self.assertIn("nb-60-2/52", ctx.gaps[-1])
        self.assertTrue(ps.sitting_done(conn, JOURNAL))

    def test_a_truncated_record_is_a_gap_not_an_empty_day(self):
        """The 20 November 2025 Hansard was served cut short at 1,290,240 bytes
        with no %%EOF; any record like it is owed, not empty."""
        conn = conn_602()
        ctx = self._ctx(conn, {JOURNAL: b"%PDF-1.7 cut short"})
        ctx.tax = pc.load_taxonomy()
        n, gaps = nb.read_sitting(ctx, 60, 2, {"date": DATE, "url": JOURNAL},
                                  pn.Resolver.from_conn(conn, "nb"), pc.load_watchlist("nb"))
        self.assertEqual((n, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "unreadable")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_divisions").fetchone()[0], 0)
        self.assertFalse(ps.sitting_done(conn, JOURNAL))
        self.assertIn("truncated", ctx.gaps[0])

    def test_the_crawl_delay_slows_legnb_only(self):
        from src.http import HttpClient
        client = HttpClient(raw_dir="/tmp/unused", throttle=1.1)
        client.get_text = lambda url, feed, slug, archive=True, fallback_encoding=None: \
            "User-agent: *\nDisallow:\ncrawl-delay: 10\n"
        ctx = Context(db.init_db(db.connect(":memory:")), client, "nb", log=lambda *a: None)
        self.assertTrue(ctx.allowed("https://www.legnb.ca/en/house-business/journals/60/2"))
        self.assertEqual(client.host_throttle("www.legnb.ca"), 10.0)
        self.assertEqual(client.host_throttle("www.assembly.nl.ca"), 1.1)
        self.assertEqual(client.throttle, 1.1)


if __name__ == "__main__":
    unittest.main()
