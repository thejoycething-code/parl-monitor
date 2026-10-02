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
        self.assertEqual(ctx.gaps, [])


if __name__ == "__main__":
    unittest.main()
