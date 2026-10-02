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

    def test_an_empty_html_text_falls_back_to_the_pdf(self):
        """Bill-57-e.htm (60-2) is served as 0 bytes: the PDF is read instead,
        and only when every document is empty is it a gap."""
        page = nb.parse_bill_page(fx("nb_bill52_page.html"))
        self.assertEqual(page["texts"], ["https://www.legnb.ca/content/house_business/60/2/bills/Bill-52-e.htm",
                                         "https://www.legnb.ca/content/house_business/60/2/bills/Bill-52.pdf"])
        saved = nb.pdf_text
        nb.pdf_text = lambda raw, pages=None: "A person is deemed to have consented to the donation of organs."
        try:
            conn = db.init_db(db.connect(":memory:"))
            listing = nb.BILLS.format(60, 2)
            pages = {"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n", listing: fx("nb_bills_602.html"),
                     "https://www.legnb.ca/en/legislation/bills/60/2/52/human-organ-and-tissue-donation-act":
                         fx("nb_bill52_page.html"),
                     page["texts"][0]: "", page["texts"][1]: b"%PDF-bill52"}
            ctx = Context(conn, _Client(pages), "nb", since="2023-06-15", until="2023-06-15", log=lambda *a: None)
            nb.fetch_bills(ctx, 60, 2, pc.load_taxonomy(), pc.load_watchlist("nb"))
        finally:
            nb.pdf_text = saved
        row = conn.execute("SELECT text_read, text_url, areas FROM prov_bills WHERE bill_key='nb-60-2/52'").fetchone()
        self.assertEqual(tuple(row), (1, page["texts"][1], "[13]"))
        self.assertFalse(any("nb-60-2/52" in g for g in ctx.gaps))

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


def conn_61():
    conn = db.init_db(db.connect(":memory:"))
    for m in json.loads(fx("nb_members_61.json")):
        ps.upsert_member(conn, "nb", m["key"], surname=m["surname"], given=m["given"])
        ps.replace_terms(conn, "nb", m["key"], [{"legislature": 61, "party": m["party"],
                                                "riding": m["riding"], "party_dated": 0}], "roster")
    conn.commit()
    return conn


JOURNAL_251120 = "https://www.legnb.ca/content/house_business/61/2/journals/15251120e.pdf"


class AliasTests(unittest.TestCase):
    """20 November 2025: the Journal prints 'Mr. Russel' for Kevin Russell
    in two divisions, and 'Mr. Russell' in the third. The reviewed alias in
    config/prov_record.yaml clears the two, on that day and in that Journal
    only, after the normal resolver has failed."""

    def setUp(self):
        self.divisions, _ = nb.parse_journal(fx("nb_journal_251120.txt"))
        self.r = nb.make_resolver(conn_61())

    def test_all_three_divisions_tally_with_the_alias(self):
        self.assertEqual([(d["yeas"], d["nays"]) for d in self.divisions], [(17, 24), (26, 16), (23, 17)])
        for d in self.divisions:
            votes, ok, note = nb.resolve_division(d, self.r, "2025-11-20", 61, document=JOURNAL_251120)
            self.assertTrue(ok, note)
        votes, _, _ = nb.resolve_division(self.divisions[0], self.r, "2025-11-20", 61, document=JOURNAL_251120)
        russel = next(v for v in votes if v["raw_label"] == "Mr. Russel")
        self.assertEqual(russel["member_key"], "kevin-russell")
        self.assertIn("alias (reviewed", russel["how"])
        # the correctly printed label in the third division resolves normally
        votes, _, _ = nb.resolve_division(self.divisions[2], self.r, "2025-11-20", 61, document=JOURNAL_251120)
        self.assertEqual(next(v for v in votes if v["raw_label"] == "Mr. Russell")["how"], "surname")

    def test_the_alias_holds_only_on_its_day_and_in_its_document(self):
        self.assertIsNone(self.r.resolve("Mr. Russel", "2025-11-21", 61, document=JOURNAL_251120)[0])
        self.assertIsNone(self.r.resolve("Mr. Russel", "2025-11-20", 61, document="https://x/other.pdf")[0])
        votes, ok, note = nb.resolve_division(self.divisions[0], self.r, "2025-11-21", 61, document=JOURNAL_251120)
        self.assertFalse(ok)
        self.assertIn("unresolved 'Mr. Russel'", note)

    def test_an_alias_never_overrides_an_ambiguous_label(self):
        al = pn.Aliased(pn.Resolver.from_conn(conn_61(), "nb"),
                        [{"printed": "Mr. LeBlanc", "member": "marco-leblanc", "date": "2025-11-20",
                          "document": JOURNAL_251120, "verified_against": "x", "why": "x"}])
        key, how = al.resolve("Mr. LeBlanc", "2025-11-20", 61, document=JOURNAL_251120)
        self.assertIsNone(key)
        self.assertTrue(how.startswith("ambiguous"), how)

    def test_an_alias_without_its_evidence_is_refused(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write('provinces:\n  "nb":\n    label_aliases:\n      - {printed: "Mr. Russel", member: kevin-russell, '
                     'date: 2025-11-20, document: "https://x"}\n')
        with self.assertRaises(ValueError):
            pn.load_aliases("nb", fh.name)
        os.unlink(fh.name)
        # every entry in the real file carries its evidence
        for prov in ("nb", "nl"):
            for a in pn.load_aliases(prov):
                self.assertTrue(a["verified_against"] and a["why"] and a["document"].startswith("https://"))


class PartyTests(unittest.TestCase):
    """Party at the vote from the Hansard's 'LIST OF MEMBERS BY CONSTITUENCY',
    dated to the sitting. 15 June 2023 is the Policy 713 day: Dominic Cardy
    sat as an Independent, Kris Austin and Michelle Conroy as PCs."""

    def test_the_list_parses_in_both_layouts(self):
        p = nb.parse_member_list(fx("nb_hansard_members_230615.txt"))
        self.assertEqual((p["session"], len(p["rows"])), ((60, 2), 49))
        self.assertEqual(p["legend"]["I"], "Independent")
        row = next(r for r in p["rows"] if "Cardy" in r["name"])
        self.assertEqual((row["riding"], row["code"]), ("Fredericton West-Hanwell", "I"))
        q = nb.parse_member_list(fx("nb_hansard_members_251105.txt"))     # no parentheses in 2025
        self.assertEqual((q["session"], len(q["rows"])), ((61, 2), 49))
        self.assertIn({"riding": "Miramichi West", "code": "PC", "name": "Kevin Russell"}, q["rows"])
        self.assertIsNone(nb.parse_member_list("no list here"))

    def test_every_member_on_the_list_resolves_unique_or_nothing(self):
        r = pn.Resolver.from_conn(conn_602(), "nb")
        pairs, problems = nb.resolve_member_list(nb.parse_member_list(fx("nb_hansard_members_230615.txt")),
                                                 r, DATE, 60)
        self.assertEqual((len(pairs), problems), (49, []))
        party = dict(pairs)
        self.assertEqual(party["dominic-cardy"], "Independent")
        self.assertEqual(party["kris-austin"], "Progressive Conservative Party of New Brunswick")
        self.assertEqual(party["susan-holt"], "Liberal Party of New Brunswick")
        # 'Mary E. Wilson' against a roster that prints 'Mary Wilson' (2025)
        pairs, problems = nb.resolve_member_list(nb.parse_member_list(fx("nb_hansard_members_251105.txt")),
                                                 pn.Resolver.from_conn(conn_61(), "nb"), "2025-11-05", 61)
        self.assertEqual((len(pairs), problems), (49, []))

    def _store_lists(self, conn, days):
        """The fetch loop with the network replaced by the fixture list."""
        text = fx("nb_hansard_members_230615.txt")
        listing = "".join('<a href="/content/house_business\\60\\2\\hansard\\{0} {1}bil.pdf">{2}</a>'.format(
            k, d, nb.datetime.date.fromisoformat(d).strftime("%B %-d, %Y")) for k, d in enumerate(days, 40))
        pages = {"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                 nb.HANSARD.format(60, 2): listing}
        for k, d in enumerate(days, 40):
            pages["https://www.legnb.ca/content/house_business/60/2/hansard/{0}%20{1}bil.pdf".format(k, d)] = \
                ("%PDF-" + d).encode()
        saved = nb.pdf_text
        nb.pdf_text = lambda raw, pages=None: text
        try:
            ctx = Context(conn, _Client(pages), "nb", log=lambda *a: None)
            n = nb.fetch_party_lists(ctx, 60, 2, pn.Resolver.from_conn(conn, "nb"), set(days))
        finally:
            nb.pdf_text = saved
        return n, ctx

    def test_party_lands_on_the_votes_of_the_day_and_nowhere_else(self):
        conn = conn_602()
        r = pn.Resolver.from_conn(conn, "nb")
        divisions, _ = nb.parse_journal(fx("nb_journal_230615.txt"))
        for d in divisions:
            votes, ok, note = nb.resolve_division(d, r, DATE, 60)
            ps.store_division(conn, {"division_key": ps.division_key("nb", 60, 2, DATE, d["seq"]), "prov": "nb",
                                     "legislature": 60, "session": 2, "date": DATE, "seq": d["seq"],
                                     "kind": "recorded", "positions_ok": 1 if ok else 0, "votes": votes})
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_votes WHERE party_at_vote IS NOT NULL").fetchone()[0], 0)
        n, ctx = self._store_lists(conn, [DATE])
        self.assertEqual((n, ctx.gaps), (1, []))
        total, with_party = ps.refresh_party(conn, "nb", pn.Resolver.from_conn(conn, "nb"), 60, 2)
        self.assertEqual(with_party, total)
        got = dict(conn.execute("SELECT member_key, party_at_vote FROM prov_votes WHERE division_key=?",
                                ("nb-60-2-2023-06-15-5",)).fetchall())
        self.assertEqual(got["dominic-cardy"], "Independent")
        self.assertEqual(got["trevor-holder"], "Progressive Conservative Party of New Brunswick")
        self.assertEqual(got["blaine-higgs"], "Progressive Conservative Party of New Brunswick")
        # the party term dates a party and nothing else: no one becomes a member by it
        r2 = pn.Resolver.from_conn(conn, "nb")
        self.assertEqual(r2.party_at("dominic-cardy", DATE, 60), "Independent")
        self.assertIsNone(r2.party_at("dominic-cardy", "2023-06-16", 60))       # a day not read
        self.assertTrue(all(not pn.is_party_only(t) for t in r2.valid_terms(DATE, 60)))

    def test_a_party_change_between_read_days_leaves_the_days_between_null(self):
        conn = conn_602()
        ps.extend_term(conn, "nb", "dominic-cardy", 60, "Progressive Conservative Party of New Brunswick", None,
                       "2022-06-01", nb.PARTY_SOURCE)
        ps.extend_term(conn, "nb", "dominic-cardy", 60, "Independent", None, "2022-11-15", nb.PARTY_SOURCE)
        r = pn.Resolver.from_conn(conn, "nb")
        self.assertEqual(r.party_at("dominic-cardy", "2022-06-01", 60), "Progressive Conservative Party of New Brunswick")
        self.assertIsNone(r.party_at("dominic-cardy", "2022-10-25", 60))
        self.assertEqual(r.party_at("dominic-cardy", "2022-11-15", 60), "Independent")

    def test_an_unreadable_hansard_is_covered_only_by_the_sittings_either_side(self):
        """20 November 2025's Hansard is served truncated. The lists of the
        sittings before and after it are read; a party the same on both
        spans the day, a party that differs leaves it NULL."""
        days = ["2023-06-14", DATE, "2023-06-16"]
        text = fx("nb_hansard_members_230615.txt")
        changed = text.replace("(I)              Dominic Cardy", "(PC)             Dominic Cardy")
        self.assertNotEqual(changed, text)
        texts = {b"%PDF-2023-06-14": changed, b"%PDF-2023-06-16": text}
        listing = "".join('<a href="/content/house_business\\60\\2\\hansard\\{0} {1}bil.pdf">{2}</a>'.format(
            k, d, nb.datetime.date.fromisoformat(d).strftime("%B %-d, %Y")) for k, d in enumerate(days, 40))
        pages = {"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n", nb.HANSARD.format(60, 2): listing}
        for k, d in enumerate(days, 40):
            pages["https://www.legnb.ca/content/house_business/60/2/hansard/{0}%20{1}bil.pdf".format(k, d)] = \
                ("%PDF-" + d).encode()

        def fake(raw, pages=None):
            if raw not in texts:
                raise nb.Unreadable("truncated PDF: no %%EOF marker")
            return texts[raw]
        conn = conn_602()
        saved = nb.pdf_text
        nb.pdf_text = fake
        try:
            ctx = Context(conn, _Client(pages), "nb", log=lambda *a: None)
            n = nb.fetch_party_lists(ctx, 60, 2, pn.Resolver.from_conn(conn, "nb"), {DATE})
        finally:
            nb.pdf_text = saved
        self.assertEqual(n, 2)
        self.assertTrue(any("truncated" in g for g in ctx.gaps))
        r = pn.Resolver.from_conn(conn, "nb")
        self.assertEqual(r.party_at("blaine-higgs", DATE, 60), "Progressive Conservative Party of New Brunswick")
        self.assertIsNone(r.party_at("dominic-cardy", DATE, 60))      # PC the day before, Independent after

    def test_a_day_with_no_hansard_listed_is_a_gap_and_no_party(self):
        conn = conn_602()
        other = "https://www.legnb.ca/content/house_business/60/2/hansard/x.pdf"
        listing = '<ul><a href="{0}">May 9, 2023</a></ul>'.format(other)
        ctx = Context(conn, _Client({"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                                     nb.HANSARD.format(60, 2): listing, other: b"not a pdf"}),
                      "nb", log=lambda *a: None)
        self.assertEqual(nb.fetch_party_lists(ctx, 60, 2, pn.Resolver.from_conn(conn, "nb"), {DATE}), 0)
        self.assertIn("no Hansard listed", ctx.gaps[0])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_member_terms WHERE source=?",
                                      (nb.PARTY_SOURCE,)).fetchone()[0], 0)

    def test_a_session_with_no_hansard_published_is_one_gap_not_two_a_day(self):
        # 57-2 (2011-2012): the Hansard page lists nothing before 58-3
        conn = conn_602()
        ctx = Context(conn, _Client({"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                                     nb.HANSARD.format(60, 2): "<ul></ul>"}), "nb", log=lambda *a: None)
        self.assertEqual(nb.fetch_party_lists(ctx, 60, 2, pn.Resolver.from_conn(conn, "nb"),
                                              {DATE, "2023-06-16"}), 0)
        self.assertEqual(len(ctx.gaps), 1)
        self.assertIn("names no transcript for the session", ctx.gaps[0])
        self.assertIn("2 division day(s)", ctx.gaps[0])


J572 = "https://www.legnb.ca/content/house_business/57/2/journals/Journal57-2.pdf"
J581 = "https://www.legnb.ca/content/house_business/58/1/journals/JOURNAL2014-2015-E.pdf"
J584 = "https://www.legnb.ca/content/house_business/58/4/journals/Journal_58-4.pdf"
J601 = "https://www.legnb.ca/content/house_business/60/1/journals/Journal-60-1-2020-2022-E.pdf"


def rows(name):
    return json.loads(fx(name))


def terms_by_key(parsed, leg, first, last):
    out = {}
    for m, t in nb.terms_from_compiled(parsed, leg, first, last):
        out.setdefault(m["key"], []).append((t["start"], t["end"], t["riding"]))
    return out


class Backfill2010ListingTests(unittest.TestCase):
    """The journals listings of 2010-2018, read live 2 October 2026."""

    def test_before_57_2_the_file_has_no_sitting_number(self):
        got = nb.list_records(fx("nb_journals_564.html"))
        self.assertEqual(len(got["daily"]), 68)          # the 2010 backfill parsed none
        self.assertIsNone(got["compiled"])                # 56-4 lists no compiled Journal
        by = {r["date"]: r for r in got["daily"]}
        self.assertEqual(by["2010-04-16"]["url"],
                         "https://www.legnb.ca/content/house_business/56/4/journals/100416e.pdf")
        self.assertIsNone(by["2010-04-16"]["sitting"])

    def test_the_compiled_journal_was_labelled_by_its_years(self):
        got = nb.list_records(fx("nb_journals_572.html"))
        self.assertEqual(got["compiled"], J572)           # "Journals 2011 - 2012", not "(Compiled)"
        self.assertEqual(len(got["daily"]), 55)
        self.assertTrue(all("Index" not in r["url"] for r in got["daily"]))

    def test_a_french_file_beside_the_english_one_is_skipped(self):
        got = nb.list_records(fx("nb_journals_584.html"))
        self.assertEqual(got["compiled"], J584)
        by = {r["date"]: r["url"] for r in got["daily"]}
        self.assertTrue(by["2018-03-13"].endswith("36180313e.pdf"))
        self.assertEqual(got["french_only"], [])
        # the same page with the English link gone: the day is French-only, said aloud
        html = fx("nb_journals_584.html").replace("36180313e.pdf", "36180313x.htm")
        got = nb.list_records(html)
        self.assertNotIn("2018-03-13", {r["date"] for r in got["daily"]})
        self.assertEqual([f["date"] for f in got["french_only"]], ["2018-03-13"])


    def test_a_question_period_transcript_in_the_journals_listing_is_not_a_journal(self):
        got = nb.list_records(fx("nb_journals_601.html"))
        self.assertNotIn("2022-10-04", {r["date"] for r in got["daily"]})
        self.assertEqual([(f["date"], "qp_transcripts" in f["url"]) for f in got["not_journal"]],
                         [("2022-10-04", True)])

    def test_one_file_listed_under_two_days_is_read_for_its_own_day_only(self):
        # 57-4 links both "May 20, 2014" and "May 21, 2014" to 69140521e.pdf
        got = nb.list_records(fx("nb_journals_574.html"))
        urls = {r["date"]: r["url"] for r in got["daily"]}
        self.assertEqual(urls["2014-05-20"], urls["2014-05-21"])
        conn = conn_602()
        url = urls["2014-05-20"]
        ctx = Context(conn, _Client({"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                                     url: b"%PDF-0608"}), "nb", log=lambda *a: None)
        ctx.tax = pc.load_taxonomy()
        text = fx("nb_journal_120608.txt")       # a Journal that names its own day: 8 June 2012
        self.assertEqual(nb.journal_date(text), "2012-06-08")
        saved = nb.pdf_text
        nb.pdf_text = lambda raw, pages=None: text
        try:
            wl = pc.load_watchlist("nb")
            res = pn.Resolver.from_conn(conn, "nb")
            self.assertEqual(nb.read_sitting(ctx, 57, 2, {"date": "2012-06-07", "url": url}, res, wl), (0, 1))
            self.assertEqual(nb.read_sitting(ctx, 57, 2, {"date": "2012-06-08", "url": url}, res, wl)[1], 0)
        finally:
            nb.pdf_text = saved
        self.assertIn("files the Journal of 2012-06-08 under 2012-06-07", ctx.gaps[0])
        self.assertFalse(nb.sitting_done(conn, "nb-57-2-2012-06-07"))
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings WHERE sitting_key='nb-57-2-2012-06-07'")
                         .fetchone()[0], "unreadable")
        self.assertTrue(nb.sitting_done(conn, "nb-57-2-2012-06-08"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_divisions WHERE date='2012-06-07'").fetchone()[0], 0)


class Backfill2010RosterTests(unittest.TestCase):
    """The compiled Journals' members pages, 57-2 to 60-1."""

    def test_the_2011_page_pads_its_columns_with_spaces(self):
        p = nb.parse_compiled_roster(rows("nb_roster_572_rows.json"), reviewed=nb.load_roster_rows(), document=J572)
        self.assertEqual(p["session"], (57, 2))
        self.assertEqual(p["problems"], [])
        self.assertEqual(len(p["members"]), 55)
        by = {m["riding"]: m for m in p["members"]}
        self.assertEqual(by["Albert"]["name"], "Wayne Steeves")
        self.assertEqual(by["Tracadie-Sheila"]["key"], "claude-landry")          # "Dr. Claude Landry"
        self.assertEqual(by["Moncton North"]["key"], "marie-claude-blais")       # "Hon. ..., Q.C."
        self.assertEqual(by["Grand Falls–Drummond–Saint-André"]["name"], "Danny Soucy")   # reviewed row
        self.assertEqual(by["Victoria-Tobique"]["key"], "wes-mclean")            # reviewed misprint
        t = terms_by_key(p, 57, "2011-11-23", "2012-11-27")
        self.assertEqual(t["margaret-ann-blaney"], [("2011-11-23", "2012-05-25", "Rothesay")])
        self.assertEqual(t["hugh-flemming"], [("2012-06-25", "2012-11-27", "Rothesay")])   # "Q.C.*"

    def test_macdonald_and_macdonald_are_told_apart_by_their_capitals(self):
        p = nb.parse_compiled_roster(rows("nb_roster_572_rows.json"), reviewed=nb.load_roster_rows(), document=J572)
        conn = db.init_db(db.connect(":memory:"))
        for m, t in nb.terms_from_compiled(p, 57, "2011-11-23", "2012-11-27"):
            ps.upsert_member(conn, "nb", m["key"], name=m["name"], surname=m["surname"], given=m["given"])
            ps.replace_terms(conn, "nb", m["key"], [t], "journal-57-2")
        plain = pn.Resolver.from_conn(conn, "nb")
        self.assertTrue(plain.resolve("Mr. MacDonald", "2011-12-06", 57)[1].startswith("ambiguous"))
        r = nb.make_resolver(conn)
        self.assertEqual(r.resolve("Mr. MacDonald", "2011-12-06", 57)[0], "kirk-macdonald")
        self.assertEqual(r.resolve("Mr. Macdonald", "2011-12-06", 57)[0], "brian-macdonald")
        self.assertIsNone(r.resolve("Mr. MACDONALD", "2011-12-06", 57)[0])     # no capitals to go by
        self.assertIsNone(r.resolve("Mr. Mcdonald", "2011-12-06", 57)[0])      # neither, as printed

    def test_two_landrys_and_three_leblancs_are_told_apart_by_reviewed_titles(self):
        p = nb.parse_compiled_roster(rows("nb_roster_581_rows.json"), reviewed=nb.load_roster_rows(), document=J581)
        conn = db.init_db(db.connect(":memory:"))
        for m, t in nb.terms_from_compiled(p, 58, "2014-10-24", "2015-06-05"):
            ps.upsert_member(conn, "nb", m["key"], name=m["name"], surname=m["surname"], given=m["given"])
            ps.replace_terms(conn, "nb", m["key"], [t], "journal-58-1")
        r = nb.make_resolver(conn)
        day = "2015-02-20"
        self.assertEqual(r.resolve("Hon. Ms. Landry", day, 58)[0], "francine-landry")
        self.assertEqual(r.resolve("Hon. Mr. Landry", day, 58)[0], "denis-landry")
        self.assertEqual(r.resolve("Ms. LeBlanc", day, 58)[0], "monique-leblanc")
        self.assertIsNone(r.resolve("Mr. LeBlanc", day, 58)[0])          # Bernard or Bertrand: still ambiguous
        bare = nb.CaseExact(pn.Aliased(pn.Resolver.from_conn(conn, "nb"), []), titles=[])
        self.assertIsNone(bare.resolve("Hon. Ms. Landry", day, 58)[0])
        # Motion 18, 20 February 2015, carried 25-23: Premier Gallant Yea,
        # interim Opposition Leader Fitch Nay
        (d,), _ = nb.parse_journal(fx("nb_journal_150220_trim.txt"))
        votes, ok, note = nb.resolve_division(d, r, day, 58)
        self.assertTrue(ok, note)
        side = {v["member_key"]: v["position"] for v in votes}
        self.assertEqual((side["brian-gallant"], side["bruce-fitch"]), ("Yea", "Nay"))
        self.assertEqual((side["kirk-macdonald"], side["brian-macdonald"]), ("Nay", "Nay"))

    def test_without_the_reviewed_rows_the_page_is_read_as_printed_or_not_at_all(self):
        p = nb.parse_compiled_roster(rows("nb_roster_572_rows.json"))
        self.assertEqual(len(p["members"]), 54)
        self.assertTrue(any("Danny Soucy" in x for x in p["problems"]))
        self.assertIn("wes-mcclean", {m["key"] for m in p["members"]})
        # a reviewed row applies only in its own document
        p = nb.parse_compiled_roster(rows("nb_roster_572_rows.json"), reviewed=nb.load_roster_rows(), document=J581)
        self.assertEqual(len(p["members"]), 54)

    def test_a_mark_printed_twice_binds_only_through_a_reviewed_row(self):
        bare = nb.parse_compiled_roster(rows("nb_roster_581_rows.json"))
        t = terms_by_key(bare, 58, "2014-10-24", "2015-06-05")
        self.assertNotIn("glen-savoie", t)
        self.assertNotIn("stewart-fairgrieve", t)
        self.assertEqual(sum("not bound" in x for x in bare["problems"]), 2)
        p = nb.parse_compiled_roster(rows("nb_roster_581_rows.json"), reviewed=nb.load_roster_rows(), document=J581)
        self.assertEqual(p["problems"], [])
        t = terms_by_key(p, 58, "2014-10-24", "2015-06-05")
        self.assertEqual(t["glen-savoie"], [("2014-11-17", "2015-06-05", "Saint John East")])
        self.assertEqual(t["david-alward"], [("2014-10-24", "2015-05-22", "Carleton")])
        self.assertNotIn("stewart-fairgrieve", t)          # elected 5 October 2015, after the session
        self.assertNotIn("gary-keating", t)                # resigned before its first sitting
        self.assertEqual(t["pam-lynch"][0][2], "Fredericton-Grand Lake")   # "Pan Lynch", reviewed

    def test_a_vacant_seat_a_resignation_and_an_unmappable_font(self):
        p = nb.parse_compiled_roster(rows("nb_roster_584_rows.json"), reviewed=nb.load_roster_rows(), document=J584)
        self.assertEqual(p["problems"], [])
        self.assertEqual([v["riding"] for v in p["vacant"]], ["Campbellton-Dalhousie"])
        t = terms_by_key(p, 58, "2017-10-24", "2018-03-16")
        self.assertEqual(t["donald-arseneault"], [("2017-10-24", "2017-12-01", "Campbellton-Dalhousie")])
        # "** Madeleine Dubé resigned July 1, 2018": after the session, so the whole session
        self.assertEqual(t["madeleine-dube"], [("2017-10-24", "2018-03-16", "Edmundston-Madawaska Centre")])
        self.assertIn("Shediac-Beaubassin-Cap-Pelé", {m["riding"] for m in p["members"]})
        bare = nb.parse_compiled_roster(rows("nb_roster_584_rows.json"))
        self.assertTrue(any("is not a name" in x for x in bare["problems"]))

    def test_a_resignation_marked_on_the_successor_bounds_both_terms(self):
        p = nb.parse_compiled_roster(rows("nb_roster_601_rows.json"))
        self.assertEqual(p["problems"], [])
        t = terms_by_key(p, 60, "2020-10-07", "2022-10-25")
        self.assertEqual(t["lisa-harris"], [("2020-10-07", "2021-08-16", "Miramichi Bay-Neguac")])
        self.assertEqual(t["rejean-savoie"], [("2021-08-17", "2022-10-25", "Miramichi Bay-Neguac")])
        self.assertIn("william-oliver", t)                 # "William (Bill) Oliver"
        self.assertIn("jean-claude-d-amours", t)           # "Jean - Claude (JC) D’Amours"

    def test_every_reviewed_row_still_matches_its_page(self):
        pages = {J572: "nb_roster_572_rows.json", J581: "nb_roster_581_rows.json", J584: "nb_roster_584_rows.json"}
        for a in nb.load_roster_rows():
            if a["document"] not in pages:
                continue
            p = nb.parse_compiled_roster(rows(pages[a["document"]]), reviewed=[a], document=a["document"])
            self.assertTrue(any(m.get("reviewed") for m in p["members"]), a["printed"])


class Backfill2010JournalTests(unittest.TestCase):
    """Journals of 2010-2012 come out of pypdf with no blank lines."""

    def voices(self, name):
        return {(v["bill_number"], v["stage"]) for v in nb.parse_journal(fx(name))[1]}

    def test_a_list_with_no_blank_lines_is_read(self):
        # 8 June 2012: the 2010 backfill stored this day 'ok' with nothing
        got = self.voices("nb_journal_120608.txt")
        self.assertIn(("69", "Second Reading"), got)
        self.assertIn(("69", "Third Reading"), got)

    def test_the_records_own_where_for_were(self):
        got = self.voices("nb_journal_120530_trim.txt")
        self.assertEqual({n for n, s in got if s == "Third Reading"},
                         {"25", "44", "49", "50", "51", "52", "53", "55"})

    def test_private_bills_with_titles_ending_in_semicolons_over_a_page_break(self):
        got = self.voices("nb_journal_100324_trim.txt")
        for n in ("27", "46", "47", "48"):
            self.assertIn((n, "Second Reading"), got)
            self.assertIn((n, "Third Reading"), got)

    def test_read_a_third_time_and_passed(self):
        got = self.voices("nb_journal_100223_trim.txt")
        self.assertTrue({("41", "Third Reading"), ("42", "Third Reading"), ("41", "Second Reading")} <= got)

    def test_the_motion_for_second_reading_was_defeated(self):
        self.assertIn(("57", "Second Reading"), self.voices("nb_journal_100408_trim.txt"))
        # "Debate resumed on the motion for second reading of Bill 23 ... the motion was defeated."
        self.assertIn(("23", "Second Reading"), self.voices("nb_journal_100114_trim.txt"))

    def test_a_minister_with_no_mr_is_a_name(self):
        divs, _ = nb.parse_journal(fx("nb_journal_100204_trim.txt"))
        self.assertEqual(len(divs), 1)
        self.assertEqual((divs[0]["yeas"], len(divs[0]["yea_labels"])), (22, 22))
        self.assertEqual((divs[0]["nays"], len(divs[0]["nay_labels"])), (27, 27))
        self.assertIn("Hon. S. Graham", divs[0]["nay_labels"])

    def test_a_name_list_runs_over_the_older_running_head(self):
        divs, _ = nb.parse_journal(fx("nb_journal_100326_trim.txt"))
        self.assertEqual([(d["yeas"], len(d["yea_labels"]), d["nays"], len(d["nay_labels"])) for d in divs],
                         [(17, 17, 24, 24), (24, 24, 18, 18)])

    def test_an_english_file_holding_the_french_journal_is_not_read(self):
        # 58-1: "March 11, 2015" -> 22150311e.pdf, "Jour de séance 22 le mercredi 11 mars 2015"
        text = fx("nb_journal_150311_french_head.txt")
        self.assertTrue(nb.is_french(text))
        self.assertFalse(nb.is_french(fx("nb_journal_120608.txt")))
        self.assertFalse(nb.is_french(fx("nb_journal_230615.txt")))
        conn = conn_602()
        ctx = Context(conn, _Client({"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                                     "u": b"%PDF-fr"}), "nb", log=lambda *a: None)
        ctx.tax = pc.load_taxonomy()
        saved = nb.pdf_text
        nb.pdf_text = lambda raw, pages=None: text
        try:
            got = nb.read_sitting(ctx, 58, 1, {"date": "2015-03-11", "url": "u"},
                                  pn.Resolver.from_conn(conn, "nb"), pc.load_watchlist("nb"))
        finally:
            nb.pdf_text = saved
        self.assertEqual(got, (0, 1))
        self.assertIn("is the French text", ctx.gaps[0])
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "unreadable")

    def test_yays_in_committee_of_the_whole(self):
        # 20 December 2011: "YAYS - 31", the record's own spelling; the guard
        # caught it (1 printed, 0 parsed) before the header was taught
        text = fx("nb_journal_111220_trim.txt")
        divs, _ = nb.parse_journal(text)
        self.assertEqual(nb.printed_divisions(text), 1)
        self.assertEqual([(d["yeas"], len(d["yea_labels"]), d["nays"], len(d["nay_labels"])) for d in divs],
                         [(31, 31, 12, 12)])
        self.assertEqual((divs[0]["bill_number"], divs[0]["stage"]), ("19", "Committee of the Whole"))

    def test_a_division_the_journal_prints_but_the_parser_misses_is_a_gap(self):
        text = fx("nb_journal_100204_trim.txt")
        self.assertEqual(nb.printed_divisions(text), 1)
        broken = text.replace("YEAS - 22", "YEAS 22")
        self.assertEqual(nb.parse_journal(broken)[0], [])
        self.assertEqual(nb.printed_divisions(broken), 1)       # the phrase still says one
        conn = conn_602()
        ctx = Context(conn, _Client({"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                                     "u": b"%PDF-broken"}), "nb", log=lambda *a: None)
        ctx.tax = pc.load_taxonomy()
        saved = nb.pdf_text
        nb.pdf_text = lambda raw, pages=None: broken
        try:
            n, gaps = nb.read_sitting(ctx, 56, 4, {"date": "2010-02-04", "url": "u"},
                                      pn.Resolver.from_conn(conn, "nb"), pc.load_watchlist("nb"))
        finally:
            nb.pdf_text = saved
        self.assertEqual((n, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings").fetchone()[0], "gap")
        self.assertIn("1 recorded division(s)", ctx.gaps[0])


class Backfill2010RepairTests(unittest.TestCase):
    def test_an_ok_sitting_missing_a_listed_reading_is_read_again(self):
        conn = db.init_db(db.connect(":memory:"))
        url = "https://www.legnb.ca/content/house_business/57/2/journals/52120608e.pdf"
        ps.store_bill(conn, {"bill_key": "nb-57-2/69", "prov": "nb", "legislature": 57, "session": 2,
                             "number": "69", "title_en": "Electoral Boundaries",
                             "stages": [{"stage": "Second Reading", "status": "Passed", "date": "2012-06-08"},
                                        {"stage": "Third Reading", "status": "Passed", "date": "2012-06-08"}]})
        ps.store_sitting(conn, "nb", "nb-57-2-2012-06-08", "2012-06-08", url, status="ok")
        ctx = Context(conn, _Client({}), "nb", log=lambda *a: None)
        self.assertEqual(nb.owe_listed(ctx, 57, 2, [{"date": "2012-06-08", "url": url}]), 1)
        self.assertFalse(ps.sitting_done(conn, url))
        # once the day holds both readings it is left alone
        for st in ("Second Reading", "Third Reading"):
            ps.store_division(conn, {"division_key": "nb-57-2-2012-06-08-v69-" + st[:1], "prov": "nb",
                                     "kind": "voice", "bill_key": "nb-57-2/69", "date": "2012-06-08", "stage": st})
        ps.store_sitting(conn, "nb", "nb-57-2-2012-06-08", "2012-06-08", url, status="ok")
        self.assertEqual(nb.owe_listed(ctx, 57, 2, [{"date": "2012-06-08", "url": url}]), 0)
        self.assertTrue(ps.sitting_done(conn, url))

    def test_a_sitting_read_by_the_old_parser_is_read_once_more(self):
        conn = db.init_db(db.connect(":memory:"))
        url = "https://www.legnb.ca/content/house_business/57/3/journals/34130507e.pdf"
        recs = [{"date": "2013-05-07", "url": url}]
        ps.store_sitting(conn, "nb", "nb-57-3-2013-05-07", "2013-05-07", url, status="ok", when="2026-10-02")
        ctx = Context(conn, _Client({}), "nb", log=lambda *a: None)
        self.assertEqual(nb.owe_stale(ctx, 57, 3, recs), 1)
        self.assertFalse(nb.sitting_done(conn, "nb-57-3-2013-05-07"))
        ps.store_sitting(conn, "nb", "nb-57-3-2013-05-07", "2013-05-07", url, status="ok", when="2026-10-07")
        self.assertEqual(nb.owe_stale(ctx, 57, 3, recs), 0)
        self.assertTrue(nb.sitting_done(conn, "nb-57-3-2013-05-07"))

    def test_the_57_1_roster_bridge_is_the_57_2_page_on_its_first_sitting(self):
        bridge = next(b for b in nb.load_roster_bridges() if b["session"] == "57-1")
        self.assertEqual(bridge["document"], J572)
        conn = db.init_db(db.connect(":memory:"))
        raw = b"%PDF-572"
        ctx = Context(conn, _Client({"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                                     nb.JOURNALS.format(57, 2): fx("nb_journals_572.html"), J572: raw}),
                      "nb", log=lambda *a: None)
        saved = nb.roster_rows
        nb.roster_rows = lambda r: rows("nb_roster_572_rows.json") if r == raw else []
        try:
            n = nb.fetch_roster(ctx, 57, 1, {"daily": [{"date": "2010-10-27"}, {"date": "2011-06-10"}],
                                             "compiled": None})
        finally:
            nb.roster_rows = saved
        self.assertEqual(n, 55)
        self.assertEqual(ctx.gaps, [])
        r = pn.Resolver.from_conn(conn, "nb")
        self.assertEqual(r.resolve("Hon. Ms. Blaney", "2011-05-01", 57)[0], "margaret-ann-blaney")
        self.assertIsNone(r.resolve("Mr. Flemming", "2011-05-01", 57)[0])     # elected 25 June 2012
        self.assertEqual(r.resolve("Mr. S. Graham", "2011-05-01", 57)[0], "shawn-graham")
        # the reviewed document must still be what the 57-2 listing links
        ctx2 = Context(db.init_db(db.connect(":memory:")),
                       _Client({"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\n",
                                nb.JOURNALS.format(57, 2): fx("nb_journals_572.html").replace(
                                    "Journal57-2.pdf", "Journal57-2-v2.pdf")}), "nb", log=lambda *a: None)
        self.assertEqual(nb.fetch_roster(ctx2, 57, 1, {"daily": [{"date": "2010-10-27"}, {"date": "2011-06-10"}],
                                                       "compiled": None}), 0)
        self.assertTrue(any("not the reviewed" in g for g in ctx2.gaps))


if __name__ == "__main__":
    unittest.main()
