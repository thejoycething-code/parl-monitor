"""Saskatchewan (src/ingest/prov_sk.py). No network: fixtures in tests/fixtures/prov/.

THE PROOF (docs/canada-provinces-scope.md): Bill 137, The Education
(Parents' Bill of Rights) Amendment Act, 2023, third reading on 20 October
2023, carried 40-12 -- Moe for, Beck against -- resolved against the
member list printed on that day's own Hansard cover.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_sk as sk  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
DATE = "2023-10-20"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def conn_from_cover(cover, date, leg, drop=()):
    conn = db.init_db(db.connect(":memory:"))
    members, _ = sk.parse_cover(fx(cover))
    for m in members:
        if m["key"] in drop:
            continue
        ps.upsert_member(conn, "sk", m["key"], name=m["given"] + " " + m["surname"],
                         surname=m["surname"], given=m["given"])
        ps.extend_term(conn, "sk", m["key"], leg, m["party"], m["riding"], date, "hansard-cover")
    conn.commit()
    return conn


class ListingTests(unittest.TestCase):
    def test_minutes_are_paired_with_the_same_sessions_hansard(self):
        recs = sk.list_records(fx("sk_archive_2023_10.html"))
        oct25 = [r for r in recs if r["date"] == "2023-10-25"]
        self.assertEqual(sorted((r["legislature"], r["session"], r["label"]) for r in oct25),
                         [(29, 3, "Minutes - AM"), (29, 4, "Minutes")])
        am = [r for r in oct25 if r["session"] == 3][0]
        self.assertTrue(am["debates"].endswith("/29L3S/20231025Debates-AM.pdf"))
        self.assertTrue(am["minutes_pdf"].endswith("/29L3S/231025MinutesRevised.pdf"))
        oct20 = [r for r in recs if r["date"] == DATE][0]
        self.assertTrue(oct20["minutes_pdf"].endswith("/29L3S/231020Minutes.pdf"))
        self.assertIsNone(oct20["minutes_html"])        # the 29th Legislature is PDF only
        self.assertTrue(oct20["debates"].endswith("/29L3S/20231020Debates.pdf"))


    def test_the_pre_2023_bare_links_are_listed(self):
        """2 October 2026: a November 2015 archive card carries a bare
        <a>Minutes</a>, no <span> wrapper, and the listing returned NOTHING
        for it -- a backfill before 2023 would have read no day, silently."""
        recs = sk.list_records(fx("sk_archive_2015_11_trim.html"))
        self.assertEqual([r["date"] for r in recs], ["2015-11-26", "2015-11-25"])
        r = recs[0]
        self.assertEqual((r["legislature"], r["session"], r["label"]), (27, 4, "Minutes"))
        self.assertTrue(r["minutes_pdf"].endswith("/Minutes/27L4S/151126Minutes.pdf"))
        self.assertTrue(r["debates"].endswith("/Debates/27L4S/151126Debates.pdf"))
        self.assertNotIn("Orders", r["minutes_pdf"])

class CoverTests(unittest.TestCase):
    def test_the_hansard_cover_is_the_dated_roster(self):
        members, total = sk.parse_cover(fx("sk_cover_231020.txt"))
        self.assertEqual((len(members), total), (61, 61))
        by = {m["key"]: m for m in members}
        self.assertEqual((by["scott-moe"]["party"], by["scott-moe"]["riding"]), ("SP", "Rosthern-Shellbrook"))
        self.assertEqual(by["carla-beck"]["party"], "NDP")
        self.assertEqual(by["nadine-wilson"]["party"], "Ind.")    # Saskatchewan United, sitting as Ind.
        self.assertEqual(by["lori-carr"]["given"], "Lori")          # 'Hon.' stripped
        members, total = sk.parse_cover(fx("sk_cover_251023.txt"))
        self.assertEqual((len(members), total), (61, 61))


class OldCoverTests(unittest.TestCase):
    """The 26th and 27th Legislature cover (2010 to spring 2016): a table,
    party code before riding, no standings. Fixtures are the real second
    pages of the 9 December 2010 and 19 November 2015 Hansards."""

    def test_the_2015_table_cover_is_the_dated_roster(self):
        members, total = sk.parse_cover(fx("sk_cover_151119.txt"))
        self.assertEqual((len(members), total), (57, 57))          # 58 seats, one vacant
        by = {m["key"]: m for m in members}
        self.assertEqual((by["scott-moe"]["party"], by["scott-moe"]["riding"]), ("SP", "Rosthern-Shellbrook"))
        self.assertEqual((by["cam-broten"]["party"], by["cam-broten"]["riding"]), ("NDP", "Saskatoon Massey Place"))
        # Party is the day's: SP here, 'Ind.' on the 2023 cover.
        self.assertEqual((by["nadine-wilson"]["given"], by["nadine-wilson"]["party"]), ("Nadine", "SP"))
        self.assertEqual(by["d-f-yogi-huyghebaert"]["surname"], "Huyghebaert")
        self.assertEqual(by["laura-ross"]["riding"], "Regina Qu’Appelle Valley")
        self.assertFalse([m for m in members if "Vacant" in m["surname"] or "Albert Carlton" in m["riding"]])
        self.assertFalse([m for m in members if m["surname"] in ("Speaker", "Premier")])
        # the same member keys as the newer layout gives
        new = {m["key"] for m in sk.parse_cover(fx("sk_cover_231020.txt"))[0]}
        self.assertIn("scott-moe", new & set(by))

    def test_the_2010_table_cover(self):
        members, total = sk.parse_cover(fx("sk_cover_101209.txt"))
        self.assertEqual((len(members), total), (58, 58))
        by = {m["key"]: m for m in members}
        self.assertEqual((by["tim-mcmillan"]["party"], by["tim-mcmillan"]["riding"]), ("SP", "Lloydminster"))
        self.assertEqual(by["dwain-lingenfelter"]["party"], "NDP")

    def test_a_line_the_table_pattern_misses_is_counted_not_dropped(self):
        text = fx("sk_cover_151119.txt").replace("Young, Colleen SP Lloydminster",
                                                 "Young, Colleen Lloydminster")
        members, total = sk.parse_cover(text)
        self.assertEqual((len(members), total), (56, 57))          # roster_for_day records the gap

    def test_drop_capitals_rejoin(self):
        self.assertEqual(sk.join_drop_caps(["Y", "EAS – 9", "B", "ill No. 127", "T", "he question",
                                            "A", "Bill No. 5"]),
                         ["YEAS – 9", "Bill No. 127", "The question", "A", "Bill No. 5"])

    def test_bill_609_second_reading_negatived_9_36(self):
        """19 November 2015: drop-capital headers ('Y' / 'EAS – 9') and a
        NAYS list that runs over a page break."""
        conn = conn_from_cover("sk_cover_151119.txt", "2015-11-19", 27)
        r = pn.Resolver.from_conn(conn, "sk")
        divisions, voices, titles = sk.parse_minutes(
            sk.blocks_from_pdf(fx("sk_minutes_151119_trim.txt"), sk._vocab(r)))
        self.assertEqual(len(divisions), 1)
        d = divisions[0]
        self.assertEqual((d["yeas"], d["nays"], d["bill_number"], d["stage"], d["result"]),
                         (9, 36, "609", "Second Reading", "it was negatived"))
        self.assertEqual(titles["609"], "The Residents-in-Care Bill of Rights Act")
        votes, ok, note = sk.resolve_division(d, r, "2015-11-19", 27)
        self.assertTrue(ok, note)
        by = {v["member_key"]: v for v in votes}
        self.assertEqual((by["cam-broten"]["position"], by["cam-broten"]["party_at_vote"]), ("Yea", "NDP"))
        self.assertEqual((by["scott-moe"]["position"], by["scott-moe"]["party_at_vote"]), ("Nay", "SP"))
        self.assertEqual(by["kevin-phillips"]["position"], "Nay")          # after the page break

    def test_a_heading_in_capitals_ends_a_name_run(self):
        """12 March 2014: 'ADJOURNED DEBATES' follows the NAYS with no blank
        line, and was read as three more Nays (6 read, 3 printed)."""
        vocab = set()
        for cover in ("sk_cover_101209.txt", "sk_cover_151119.txt"):
            vocab |= {tuple(pn.fold(m["surname"]).split()) for m in sk.parse_cover(fx(cover))[0]}
        divisions, voices, _ = sk.parse_minutes(sk.blocks_from_pdf(fx("sk_minutes_140312_trim.txt"), vocab))
        self.assertEqual(len(divisions), 1)
        d = divisions[0]
        self.assertEqual((d["yeas"], d["nays"], len(d["yea_labels"])), (38, 3, 38))
        self.assertEqual(d["nay_labels"], ["Forbes", "Chartier", "Nilson"])
        # "was, accordingly, read a second time": a voice decision
        self.assertEqual([(v["bill_number"], v["stage"]) for v in voices], [("127", "Second Reading")])

    def test_which_was_agreed_to_is_the_result(self):
        """2 April 2015: the Speaker puts the question under a rule, 'which
        was agreed to on the following Recorded Division'; the NAYS header
        opens the next page."""
        vocab = {tuple(pn.fold(m["surname"]).split()) for m in sk.parse_cover(fx("sk_cover_151119.txt"))[0]}
        divisions, _, _ = sk.parse_minutes(sk.blocks_from_pdf(fx("sk_minutes_150402_trim.txt"), vocab))
        self.assertEqual([(d["yeas"], d["nays"], len(d["yea_labels"]), len(d["nay_labels"]), d["result"])
                          for d in divisions], [(39, 5, 39, 5, "it was agreed to")])

    def test_a_wrapped_recorded_division_still_reads_the_roster(self):
        """24 November 2016 (28th Legislature): '... on the following
        Recorded' / 'Division:' -- the day's roster was never read and none
        of the 56 Yeas resolved."""
        text = fx("sk_minutes_161124_trim.txt")
        self.assertNotIn("recorded division", text.lower())
        self.assertTrue(sk.has_division(text))
        self.assertTrue(sk.has_division("Y\nEAS – 9\n"))
        self.assertFalse(sk.has_division("it was read the third time and passed"))
        d = sk.parse_minutes(sk.blocks_from_pdf(text, set()))[0][0]
        self.assertEqual(d["result"], "it was agreed to")              # "it was a greed to"

    def test_a_term_spanning_the_day_does_not_skip_its_cover(self):
        """Covers read out of order (2015, then 2012) widen a term across
        2012-04-23 without that day's cover being read; the day must still
        read its own."""
        conn = db.init_db(db.connect(":memory:"))
        for day in ("2012-03-29", "2015-11-19"):
            ps.upsert_member(conn, "sk", "scott-moe", name="Scott Moe", surname="Moe", given="Scott")
            ps.extend_term(conn, "sk", "scott-moe", 27, "SP", "Rosthern-Shellbrook", day, "hansard-cover")
        url = "https://docs.legassembly.sk.ca/legdocs/Assembly/Debates/27L1S/120423Debates.pdf"
        client = _Client({url: "%PDF-cover"})
        ctx = Context(conn, client, "sk", log=lambda *a: None)
        ctx.allowed = lambda u: True
        saved = sk.pdf_text
        sk.pdf_text = lambda raw, pages=None: fx("sk_cover_151119.txt")
        try:
            n = sk.roster_for_day(ctx, {"date": "2012-04-23", "legislature": 27, "debates": url})
            self.assertEqual(n, 57)
            self.assertEqual(client.asked, [url])
            # read once, the day is now an end of every term: not read again
            self.assertTrue(sk.roster_for_day(ctx, {"date": "2012-04-23", "legislature": 27, "debates": url}))
            self.assertEqual(client.asked, [url])
        finally:
            sk.pdf_text = saved


class OldHansardTests(unittest.TestCase):
    def test_a_spaced_honorific_stop_still_resolves(self):
        """25 November 2015: 'Hon. Mr . Duncan : —' was the one unresolved
        speaker of 69."""
        from src import prov_speeches as sp
        from src.ingest import prov_sk_hansard as skh
        turns = skh.parse_pdf(fx("sk_debates_151125_trim.txt"))
        labels = [t["label"] for t in turns]
        self.assertIn("Hon. Mr. Duncan", labels)
        conn = conn_from_cover("sk_cover_151119.txt", "2015-11-25", 27)
        r = pn.Resolver.from_conn(conn, "sk")
        keys = sp.resolve_turns(conn, "sk", r, turns, "2015-11-25", 27)
        by = {t["label"]: k[0] for t, k in zip(turns, keys)}
        self.assertEqual(by["Hon. Mr. Duncan"], "dustin-duncan")
        self.assertEqual(by["Hon. Mr. Wall"], "brad-wall")


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.conn = conn_from_cover("sk_cover_231020.txt", DATE, 29)
        self.r = pn.Resolver.from_conn(self.conn, "sk")

    def parse(self):
        blocks = sk.blocks_from_pdf(fx("sk_minutes_231020.txt"), sk._vocab(self.r))
        return sk.parse_minutes(blocks)

    def test_bill_137_third_reading_40_12(self):
        divisions, voices, titles = self.parse()
        self.assertEqual(titles["137"], "The Education (Parents’ Bill of Rights) Amendment Act, 2023")
        self.assertEqual(len(divisions), 1)
        d = divisions[0]
        self.assertEqual((d["yeas"], d["nays"], d["stage"], d["bill_number"], d["result"]),
                         (40, 12, "Third Reading", "137", "it was agreed to"))
        votes, ok, note = sk.resolve_division(d, self.r, DATE, 29)
        self.assertTrue(ok, note)
        by = {v["member_key"]: v for v in votes}
        self.assertEqual((by["scott-moe"]["position"], by["scott-moe"]["party_at_vote"]), ("Yea", "SP"))
        self.assertEqual((by["carla-beck"]["position"], by["carla-beck"]["party_at_vote"]), ("Nay", "NDP"))
        self.assertEqual(by["jeremy-cockrill"]["position"], "Yea")
        self.assertEqual(by["trent-wotherspoon"]["position"], "Nay")
        # ridings that wrap across lines pick the right one of two
        self.assertEqual(by["laura-ross"]["raw_label"], "Ross (Regina Rochdale)")
        self.assertEqual(by["jeremy-harrison"]["raw_label"], "Harrison (Meadow Lake)")
        self.assertEqual(by["daryl-harrison"]["raw_label"], "Harrison (Cannington)")
        self.assertEqual(by["tim-mcleod"]["raw_label"], "McLeod (Moose Jaw North)")
        self.assertEqual(by["aleana-young"]["position"], "Nay")
        self.assertEqual(by["colleen-young"]["position"], "Yea")
        self.assertNotIn("alana-ross", by)            # did not vote

    def test_bill_137_is_on_our_ground_by_title_term_and_key(self):
        tax, wl = pc.load_taxonomy(), pc.load_watchlist("sk")
        title = "The Education (Parents’ Bill of Rights) Amendment Act, 2023"
        self.assertEqual(pc.classify(tax, wl, "sk", title=title).areas, [6])
        self.assertEqual(pc.classify(tax, wl, "sk", title=title, bill_key="sk-29-3/137").tier, 1)

    def test_a_member_missing_from_the_roster_is_a_gap_with_a_null(self):
        conn = conn_from_cover("sk_cover_231020.txt", DATE, 29, drop=("carla-beck",))
        r = pn.Resolver.from_conn(conn, "sk")
        blocks = sk.blocks_from_pdf(fx("sk_minutes_231020.txt"), sk._vocab(r) | {("beck",)})
        d = sk.parse_minutes(blocks)[0][0]
        votes, ok, note = sk.resolve_division(d, r, DATE, 29)
        self.assertFalse(ok)
        beck = [v for v in votes if v["raw_label"] == "Beck"][0]
        self.assertIsNone(beck["member_key"])

    def test_a_term_seen_on_another_day_does_not_cover_this_one(self):
        conn = conn_from_cover("sk_cover_231020.txt", "2023-10-12", 29)
        r = pn.Resolver.from_conn(conn, "sk")
        self.assertIsNone(r.resolve("Moe", DATE, 29)[0])


class HtmlMinutesTests(unittest.TestCase):
    """The 30th Legislature: an HTML edition, one full name per paragraph."""

    def test_two_divisions_on_the_tariff_motion(self):
        conn = conn_from_cover("sk_cover_251023.txt", "2025-10-23", 30)
        r = pn.Resolver.from_conn(conn, "sk")
        divisions, voices, _ = sk.parse_minutes(sk.blocks_from_html(fx("sk_minutes_20251023.htm")))
        self.assertEqual([(d["vote_on"], d["yeas"], d["nays"]) for d in divisions],
                         [("amendment", 33, 24), ("motion", 33, 24)])
        for d in divisions:
            votes, ok, note = sk.resolve_division(d, r, "2025-10-23", 30)
            self.assertTrue(ok, note)
            by = {v["member_key"]: v for v in votes}
            self.assertEqual((by["scott-moe"]["position"], by["carla-beck"]["position"]), ("Yea", "Nay"))
            self.assertEqual(by["betty-nippi-albright"]["how"], "full-name")   # 'Nippi -Albright'

    def test_a_reading_without_a_division_is_a_voice_decision(self):
        divisions, voices, titles = sk.parse_minutes(sk.blocks_from_html(fx("sk_minutes_voice.htm")))
        self.assertEqual(divisions, [])
        self.assertTrue(voices)
        for v in voices:
            self.assertEqual(v["stage"], "Second Reading")
            self.assertIn(v["bill_number"], titles)
            self.assertIn("accordingly read a second time", v["result"])


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
    MIN = "https://docs.legassembly.sk.ca/legdocs/Assembly/Minutes/29L3S/231020Minutes.pdf"
    DEB = "https://docs.legassembly.sk.ca/legdocs/Assembly/Debates/29L3S/20231020Debates.pdf"

    def setUp(self):
        self._pdf = sk.pdf_text
        texts = {b"%PDF-min": fx("sk_minutes_231020.txt"), b"%PDF-deb": fx("sk_cover_231020.txt")}
        sk.pdf_text = lambda raw, pages=None: texts[raw]

    def tearDown(self):
        sk.pdf_text = self._pdf

    def test_the_proof_lands_in_the_store_with_its_day_roster(self):
        conn = db.init_db(db.connect(":memory:"))
        client = _Client({sk.ARCHIVE.format(DATE, DATE): fx("sk_archive_2023_10.html"),
                          self.MIN: "%PDF-min", self.DEB: "%PDF-deb"})
        ctx = Context(conn, client, "sk", since=DATE, until=DATE, log=lambda *a: None)
        stats = sk.collect(ctx, session="29-3")
        self.assertEqual((stats["records_read"], stats["divisions"], stats["tally_gaps"]), (1, 1, 0))
        row = conn.execute("SELECT division_key, bill_key, stage, yeas, nays, positions_ok, areas "
                           "FROM prov_divisions").fetchone()
        self.assertEqual(tuple(row), ("sk-29-3-2023-10-20-1", "sk-29-3/137", "Third Reading", 40, 12, 1, "[6]"))
        terms = conn.execute("SELECT start, end, party FROM prov_member_terms WHERE member_key='scott-moe'").fetchall()
        self.assertEqual([tuple(t) for t in terms], [(DATE, DATE, "SP")])
        # the newest cover read is the sitting list, which the 5CA counts
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_members WHERE sitting=1").fetchone()[0], 61)
        self.assertEqual(ctx.gaps, [])


if __name__ == "__main__":
    unittest.main()
