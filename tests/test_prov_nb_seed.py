"""New Brunswick 56-4 from the Legislative Library's record (config/prov-nb-56-4/).

No network. The session's compiled Journal is not on legnb.ca; the Library
sent its members page and its index of recorded votes (9 October 2026). The
division blocks of the eleven recorded votes are trimmed from the daily
Journals on legnb.ca (read 13 October 2026) into
tests/fixtures/prov/nb_journal_564_divisions.json.
"""

import csv
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_names as pn  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_nb as nb  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
FIRST, LAST = "2009-11-17", "2010-04-16"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


DIVISIONS = json.loads(fx("nb_journal_564_divisions.json"))


class _Client:
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 1.1

    def __init__(self, pages):
        self.pages = pages

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        page = self.pages[url]
        return page.decode() if isinstance(page, bytes) else page

    def get_bytes(self, url, feed, slug, archive=True):
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        page = self.pages[url]
        return page if isinstance(page, bytes) else page.encode()


class SeedFilesTests(unittest.TestCase):
    def test_the_files_are_where_the_collector_looks(self):
        paths = nb.seed_paths(56, 4)
        self.assertEqual(sorted(paths), ["members", "votes"])
        self.assertEqual(nb.seed_paths(57, 1), {})
        with open(paths["members"], encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        # names, constituencies and the page's notes only: no residence column
        self.assertEqual(header, ["constituency", "member", "note", "member_key"])

    def test_the_members_page(self):
        parsed = nb.load_seed_roster(nb.seed_paths(56, 4)["members"], 56, 4)
        self.assertEqual(parsed["problems"], [])
        self.assertEqual(len(parsed["members"]), 53)
        self.assertEqual(sorted(v["riding"] for v in parsed["vacant"]), ["Moncton North", "Rogersville-Kouchibouguac"])
        keys = {m["key"]: m for m in parsed["members"]}
        self.assertEqual(len(keys), 53)
        # the same person the 57th Legislature's compiled Journals already hold
        self.assertIn("chris-collins", keys)
        self.assertNotIn("christopher-collins", keys)
        for key in ("roy-boudreau", "victor-boudreau", "cy-leblanc", "thomas-burke", "ed-doherty",
                    "claude-landry", "denis-landry", "jack-carr", "jody-carr", "carmel-robichaud",
                    "paul-robichaud", "joan-macalpine-stiles", "hedard-albert"):
            self.assertIn(key, keys)
        self.assertEqual((keys["cy-leblanc"]["given"], keys["cy-leblanc"]["surname"]), ("Cy", "Leblanc"))
        self.assertEqual(keys["kelly-lamrock"]["name"], "Kelly Lamrock")    # 'Hon.' and ', Q.C.' dropped

    def test_the_two_resignations_end_their_terms(self):
        parsed = nb.load_seed_roster(nb.seed_paths(56, 4)["members"], 56, 4)
        terms = {}
        for m, t in nb.terms_from_compiled(parsed, 56, FIRST, LAST):
            terms.setdefault(m["key"], []).append((t["start"], t["end"], t["riding"]))
        self.assertEqual(len(terms), 55)
        self.assertEqual(terms["michael-murphy"], [(FIRST, "2010-02-05", "Moncton North")])
        self.assertEqual(terms["rose-may-poirier"], [(FIRST, "2010-02-26", "Rogersville-Kouchibouguac")])
        self.assertEqual(terms["roy-boudreau"], [(FIRST, LAST, "Campbellton-Restigouche Centre")])

    def test_the_votes_index(self):
        index = nb.load_seed_votes(nb.seed_paths(56, 4)["votes"])
        self.assertEqual(len(index), 11)
        self.assertEqual(sorted({v["date"] for v in index}), sorted(DIVISIONS))
        self.assertEqual(sum(1 for v in index if v["date"] == "2010-03-26"), 2)

    def test_a_row_that_is_not_a_name_is_a_problem(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write("constituency,member,note,member_key\nAlbert,0DGHO,,\nKent,Vacant,,\n"
                     "York,Vacant,somebody left at some point,\n")
        try:
            parsed = nb.load_seed_roster(fh.name, 56, 4)
        finally:
            os.unlink(fh.name)
        self.assertEqual(len(parsed["problems"]), 3)     # not a name, not understood, no members


def seeded_ctx(journals, since=FIRST, until=LAST, log=None):
    """A Context over the 56-4 listing whose division days serve the trimmed
    Journals, every other listed day a Journal with no division."""
    listing = fx("nb_journals_564.html")
    pages = {nb.JOURNALS.format(56, 4): listing,
             "https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\ncrawl-delay: 10\n"}
    for rec in nb.list_records(listing)["daily"]:
        if rec["date"] in journals:
            pages[rec["url"]] = journals[rec["date"]]
    conn = db.init_db(db.connect(":memory:"))
    return Context(conn, _Client(pages), "nb", since=since, until=until, log=log or (lambda *a: None))


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self._pdf = nb.pdf_text

        def fake(raw, pages=None):
            text = raw.decode("utf-8")
            if not text.startswith("%PDF-"):
                raise nb.Unreadable("not a PDF")
            return text[len("%PDF-"):]
        nb.pdf_text = fake
        listing = nb.list_records(fx("nb_journals_564.html"))["daily"]
        self.journals = {r["date"]: "%PDF-And then, 6 p.m., the House adjourned." for r in listing}
        for date, text in DIVISIONS.items():
            self.journals[date] = "%PDF-" + text + "\nAnd then, 6 p.m., the House adjourned."

    def tearDown(self):
        nb.pdf_text = self._pdf

    def test_all_eleven_divisions_resolve_and_tally(self):
        logs = []
        ctx = seeded_ctx(self.journals, log=logs.append)
        stats = nb.collect(ctx, "56-4", bills=False, party=False)
        self.assertEqual(ctx.gaps, [])
        self.assertEqual((stats["members"], stats["divisions"], stats["tally_gaps"]), (55, 11, 0))
        self.assertEqual(stats["library_votes"], "11/11")
        conn = ctx.conn
        rows = conn.execute("SELECT division_key, yeas, nays, positions_ok FROM prov_divisions "
                            "WHERE kind='recorded' ORDER BY division_key").fetchall()
        self.assertEqual([tuple(r) for r in rows], [
            ("nb-56-4-2009-11-26-1", 20, 26, 1), ("nb-56-4-2009-11-27-1", 28, 15, 1),
            ("nb-56-4-2009-12-11-1", 31, 20, 1), ("nb-56-4-2009-12-15-1", 29, 14, 1),
            ("nb-56-4-2010-02-04-1", 22, 27, 1), ("nb-56-4-2010-02-18-1", 22, 28, 1),
            ("nb-56-4-2010-03-17-1", 29, 19, 1), ("nb-56-4-2010-03-26-1", 17, 24, 1),
            ("nb-56-4-2010-03-26-2", 24, 18, 1), ("nb-56-4-2010-04-06-1", 39, 0, 1),
            ("nb-56-4-2010-04-14-1", 24, 17, 1)])
        self.assertEqual(tuple(conn.execute("SELECT COUNT(*), COUNT(member_key) FROM prov_votes").fetchone()),
                         (493, 493))
        how = {}
        for label, key in conn.execute("SELECT raw_label, member_key FROM prov_votes"):
            how.setdefault(label, set()).add(key)
        # one member per printed label across the session
        self.assertEqual([k for k, v in how.items() if len(v) != 1], [])
        how = {k: (v.pop(), None) for k, v in how.items()}
        self.assertEqual(how["Mr. Northup"][0], "bruce-northrup")               # reviewed alias
        self.assertEqual(how["Mr. Robichaud"][0], "paul-robichaud")             # reviewed titles
        self.assertEqual(how["Ms. Robichaud"][0], "carmel-robichaud")
        self.assertEqual(how["Mr. C. LeBlanc"][0], "cy-leblanc")
        self.assertEqual(how["Mr. B. LeBlanc"][0], "bernard-leblanc")
        self.assertEqual(how["Hon. D. Landry"][0], "denis-landry")
        self.assertEqual(how["Mr. C. Landry"][0], "claude-landry")
        self.assertEqual(how["Mr. Jack Carr"][0], "jack-carr")
        self.assertEqual(how["Mr. Jody Carr"][0], "jody-carr")
        self.assertEqual(how["Hon. Mr. Collins"][0], "chris-collins")
        self.assertTrue(any("Legislative Library" in m and "55 member(s)" in m for m in logs))
        self.assertTrue(any("11 of the 11 recorded vote(s)" in m for m in logs))

    def test_the_vacancies_by_date(self):
        ctx = seeded_ctx(self.journals)
        nb.collect(ctx, "56-4", bills=False, party=False)
        votes = dict(((r[0], r[1]), r[2]) for r in ctx.conn.execute(
            "SELECT division_key, raw_label, member_key FROM prov_votes"))
        self.assertEqual(votes[("nb-56-4-2009-11-26-1", "Hon. Mr. Murphy")], "michael-murphy")
        self.assertEqual(votes[("nb-56-4-2010-02-18-1", "Ms. Poirier")], "rose-may-poirier")
        resolver = nb.make_resolver(ctx.conn)
        # Murphy resigned 5 February 2010, Poirier 26 February 2010
        self.assertEqual(resolver.resolve("Hon. Mr. Murphy", "2010-02-05", 56)[0], "michael-murphy")
        self.assertIsNone(resolver.resolve("Hon. Mr. Murphy", "2010-02-18", 56)[0])
        self.assertIsNone(resolver.resolve("Ms. Poirier", "2010-03-17", 56)[0])

    def test_a_vote_of_the_index_missing_from_the_store_is_a_gap(self):
        self.journals["2009-12-11"] = "%PDF-And then, 6 p.m., the House adjourned."
        ctx = seeded_ctx(self.journals)
        stats = nb.collect(ctx, "56-4", bills=False, party=False)
        self.assertEqual(stats["library_votes"], "10/11")
        self.assertEqual(len(ctx.gaps), 1)
        self.assertIn("nb 56-4 2009-12-11: the Legislative Library's index lists 1 recorded vote(s)", ctx.gaps[0])
        self.assertIn("Motion 9 (Budget Motion), Journal p. 68", ctx.gaps[0])

    def test_the_index_is_checked_only_inside_the_window(self):
        ctx = seeded_ctx(self.journals, since="2010-03-26", until="2010-03-26")
        stats = nb.collect(ctx, "56-4", bills=False, party=False)
        self.assertEqual((stats["divisions"], stats["library_votes"], ctx.gaps), (2, "2/2", []))

    def test_a_dry_run_stores_no_roster(self):
        ctx = seeded_ctx(self.journals)
        ctx.dry_run = True
        stats = nb.collect(ctx, "56-4", bills=False, party=False)
        self.assertEqual(stats["members"], 55)
        self.assertEqual(ctx.conn.execute("SELECT COUNT(*) FROM prov_member_terms").fetchone()[0], 0)


class KnownGapTests(unittest.TestCase):
    def test_no_roster_for_56_4_is_no_longer_a_known_gap(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import prov_collect
        self.assertFalse(prov_collect.known_gap("nb", "nb 56-4: no roster for the session (no usable compiled "
                                                      "Journal, and the site lists only current members)"))
        self.assertFalse(prov_collect.known_gap("nb", "nb-56-4-2010-02-04-1: tally check failed (no roster "
                                                      "for 56-4; Yea: unresolved 'Mr. Fitch')"))
        # the session still has no Hansard online, so no party at the vote
        self.assertTrue(prov_collect.known_gap("nb", "nb 56-4: the Hansard listing names no transcript for the "
                                                     "session, so no party at the vote for its 10 division day(s)"))

    def test_the_reviewed_facts_load(self):
        titles = {t["member"]: t["title"] for t in nb.load_titles()}
        self.assertEqual((titles["paul-robichaud"], titles["carmel-robichaud"]), ("Mr.", "Ms."))
        self.assertIn(("Mr. Northup", "bruce-northrup", "2010-03-26"),
                      [(a["printed"], a["member"], a["date"]) for a in pn.load_aliases("nb")])


if __name__ == "__main__":
    unittest.main()
