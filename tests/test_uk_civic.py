"""The UK edition's civic layer (16 October 2026): tools/uk_petitions.py and
tools/govuk_docs.py against fixtures captured live on 16 October 2026
(tests/fixtures/uk_civic). No network."""

import copy
import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402
from tools import govuk_docs, uk_petitions  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "uk_civic")
TODAY = datetime.date(2026, 10, 18)          # a Sunday: the edition is 19 October
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))


def _json(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def _text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def _store():
    return db.init_db(db.connect(":memory:"))


def _fail(url):
    return FetchError(url, "test", "slug", 3, "HTTP Error 503")


class PetitionClient:
    """Answers the petition JSON from fixtures; records every URL asked."""

    def __init__(self, open_payload=None, closed_payload=None, details=None, fail_open=False):
        self.open = open_payload if open_payload is not None else _json("petitions_open.json")
        self.closed = closed_payload if closed_payload is not None else _json("petitions_closed.json")
        self.details = details if details is not None else {764268: _json("petition_764268.json")}
        self.fail_open = fail_open
        self.urls = []

    def get_json(self, url, feed, slug, archive=True):
        self.urls.append(url)
        if url.endswith("state=open"):
            if self.fail_open:
                raise _fail(url)
            return self.open
        if url.endswith("state=closed"):
            return self.closed
        for pid, payload in self.details.items():
            if url.endswith("/petitions/{0}.json".format(pid)):
                return payload
        raise _fail(url)


def _sweep(conn, client, today=TODAY):
    return uk_petitions.Sweep(client, conn, TAX, WL, today, log=lambda *a: None)


class PetitionParsingTests(unittest.TestCase):
    def test_debated_petition_carries_its_milestones(self):
        row = next(r for r in _json("petitions_closed.json")["data"] if r["id"] == 763161)
        p = uk_petitions.parse_row(row)
        self.assertEqual(uk_petitions.threshold(p), "100k")
        self.assertEqual(uk_petitions.debate_date(p), "2026-09-07")
        self.assertIn("hansard.parliament.uk", p.debate_url)
        self.assertEqual(p.government_response_at, "2026-05-20")
        self.assertEqual(p.closed_at, "2026-10-10")

    def test_thresholds(self):
        row = copy.deepcopy(_json("petitions_open.json")["data"][0])
        a = row["attributes"]
        a.update(signature_count=9999, response_threshold_reached_at=None, debate_threshold_reached_at=None)
        self.assertIsNone(uk_petitions.threshold(uk_petitions.parse_row(row)))
        a.update(signature_count=10000)
        self.assertEqual(uk_petitions.threshold(uk_petitions.parse_row(row)), "10k")
        a.update(signature_count=100001)
        self.assertEqual(uk_petitions.threshold(uk_petitions.parse_row(row)), "100k")

    def test_edition_week(self):
        self.assertEqual(uk_petitions.edition_week(TODAY), "2026-10-19")
        self.assertEqual(uk_petitions.edition_week(datetime.date(2026, 10, 16)), "2026-10-12")


class PetitionSweepTests(unittest.TestCase):
    def test_first_run_reads_open_and_every_closed_page(self):
        conn, client = _store(), PetitionClient()
        stats = _sweep(conn, client).run()
        self.assertTrue(any(u.endswith("state=closed") for u in client.urls))
        rows = {r["petition_id"]: r for r in conn.execute("SELECT * FROM uk_petitions")}
        # on our ground, open
        self.assertIn(773633, rows)                     # illegal migration inquiry (tier 1)
        self.assertIn(781598, rows)                     # children in pornography promotion, 42k
        # on our ground, closed within three months, with milestones
        self.assertEqual(rows[763161]["threshold_reached"], "100k")
        self.assertEqual(rows[763161]["debate_date"], "2026-09-07")
        self.assertEqual(rows[763161]["debate_held"], 1)
        self.assertEqual(rows[757233]["debate_date"], "2026-11-02")    # scheduled, not yet held
        self.assertEqual(rows[757233]["debate_held"], 0)
        # off our ground, or closed too long ago
        self.assertNotIn(767687, rows)                  # climate briefing
        self.assertNotIn(700143, rows)                  # general election, closed 2025
        self.assertEqual(stats["matched"], len(rows))
        self.assertTrue(json.loads(rows[763161]["areas"]))
        counts = conn.execute("SELECT COUNT(*) FROM uk_petition_counts WHERE captured_at = ?",
                              (TODAY.isoformat(),)).fetchone()[0]
        self.assertEqual(counts, len(rows))

    def test_no_signer_data_is_stored(self):
        cols = {r[1] for r in _store().execute("PRAGMA table_info(uk_petitions)")}
        self.assertFalse({c for c in cols if "creator" in c or "constituen" in c or "region" in c})

    def test_tier_two_below_ten_thousand_is_left_out(self):
        payload = _json("petitions_open.json")
        row = next(r for r in payload["data"] if r["id"] == 781598)   # matched on tier-2 pornograph*
        row["attributes"].update(signature_count=4000, response_threshold_reached_at=None)
        conn = _store()
        _sweep(conn, PetitionClient(open_payload=payload)).run()
        self.assertIsNone(conn.execute("SELECT 1 FROM uk_petitions WHERE petition_id = 781598").fetchone())

    def test_threshold_first_seen_is_the_sunday_it_was_crossed(self):
        before = _json("petitions_open.json")
        row = next(r for r in before["data"] if r["id"] == 773633)
        row["attributes"].update(signature_count=9000, response_threshold_reached_at=None,
                                 government_response_at=None, government_response=None)
        conn = _store()
        _sweep(conn, PetitionClient(open_payload=before)).run()
        r = conn.execute("SELECT threshold_reached, threshold_first_seen FROM uk_petitions "
                         "WHERE petition_id = 773633").fetchone()
        self.assertEqual((r[0], r[1]), (None, None))
        week2 = TODAY + datetime.timedelta(days=7)
        _sweep(conn, PetitionClient(), today=week2).run()
        r = conn.execute("SELECT threshold_reached, threshold_first_seen, response_threshold_at FROM uk_petitions "
                         "WHERE petition_id = 773633").fetchone()
        self.assertEqual((r[0], r[1]), ("10k", week2.isoformat()))
        self.assertTrue(r[2])                            # the API's own crossing date, kept
        week3 = week2 + datetime.timedelta(days=7)
        _sweep(conn, PetitionClient(), today=week3).run()
        r = conn.execute("SELECT threshold_first_seen FROM uk_petitions WHERE petition_id = 773633").fetchone()
        self.assertEqual(r[0], week2.isoformat())

    def test_a_held_petition_that_closed_is_re_read_without_a_full_scan(self):
        conn = _store()
        conn.execute("INSERT INTO uk_petitions (petition_id, title, state, signatures, url, first_seen, last_seen) "
                     "VALUES (764268, 'x', 'open', 90000, 'u', '2026-10-11', '2026-10-11')")
        conn.execute("INSERT INTO uk_civic_runs (source, run_date, ok) VALUES ('uk_petitions:closed-scan', "
                     "'2026-10-04', 1)")
        client = PetitionClient()
        stats = _sweep(conn, client).run()
        self.assertFalse(any(u.endswith("state=closed") for u in client.urls))
        self.assertTrue(any(u.endswith("/petitions/764268.json") for u in client.urls))
        self.assertEqual(stats["reread"], 1)
        r = conn.execute("SELECT state, signatures, threshold_reached FROM uk_petitions "
                         "WHERE petition_id = 764268").fetchone()
        self.assertEqual(r[0], "closed")
        self.assertEqual(r[2], "100k")

    def test_closed_scan_returns_after_four_weeks(self):
        conn = _store()
        conn.execute("INSERT INTO uk_civic_runs (source, run_date, ok) VALUES ('uk_petitions:closed-scan', "
                     "'2026-09-20', 1)")
        client = PetitionClient()
        _sweep(conn, client).run()
        self.assertTrue(any(u.endswith("state=closed") for u in client.urls))

    def test_a_failed_listing_is_a_gap_and_proves_nothing_closed(self):
        conn = _store()
        conn.execute("INSERT INTO uk_petitions (petition_id, title, state, signatures, url, first_seen, last_seen) "
                     "VALUES (764268, 'x', 'open', 90000, 'u', '2026-10-11', '2026-10-11')")
        conn.execute("INSERT INTO uk_civic_runs (source, run_date, ok) VALUES ('uk_petitions:closed-scan', "
                     "'2026-10-04', 1)")
        client = PetitionClient(fail_open=True)
        sweep = _sweep(conn, client)
        sweep.run()
        self.assertTrue(sweep.gaps and "open listing failed" in sweep.gaps[0])
        self.assertFalse(any("/petitions/764268.json" in u for u in client.urls))
        edition = uk_petitions.write_gaps(conn, TODAY, sweep.gaps)
        self.assertEqual(edition, "2026-10-19")
        self.assertEqual(conn.execute("SELECT feed FROM gaps WHERE edition = '2026-10-19'").fetchone()[0],
                         "uk_petitions")
        ok = conn.execute("SELECT ok FROM uk_civic_runs WHERE source = 'uk_petitions'").fetchone()[0]
        self.assertEqual(ok, 0)

    def test_exclusions_apply(self):
        conn = _store()
        _sweep(conn, PetitionClient()).run(settings={"petition_exclusions": [{"id": 773633, "reason": "test"}]})
        self.assertIsNone(conn.execute("SELECT 1 FROM uk_petitions WHERE petition_id = 773633").fetchone())


class GovukClient:
    def __init__(self, closed=None, fail=()):
        self.closed = closed if closed is not None else _json("govuk_closed_consultations.json")
        self.fail = fail
        self.urls = []

    def _maybe_fail(self, url):
        if any(f in url for f in self.fail):
            raise _fail(url)

    def get_json(self, url, feed, slug, archive=True):
        self.urls.append(url)
        self._maybe_fail(url)
        if url.startswith(govuk_docs.CONTENT.format("")):
            return _json("govuk_content_tying_the_knot.json")
        if "filter_organisations=" in url:
            return _json("govuk_publications.json")
        if "closed_consultation" in url and "filter_end_date" in url:
            return self.closed
        return {"results": [], "total": 0}

    def get_text(self, url, feed, slug, archive=True):
        self.urls.append(url)
        self._maybe_fail(url)
        if url == govuk_docs.OFCOM_LIST:
            return _text("ofcom_listing.html")
        if "a-safer-life-online-for-women-and-girls" in url:
            return _text("ofcom_women_and_girls.html")
        if url == govuk_docs.NHSE_FEED:
            return _text("nhse_feed.xml")
        if url.startswith(govuk_docs.NHSE_FEED):
            return "<rss><channel></channel></rss>"
        if "guidance-on-nhs-staff-facilities" in url:
            return _text("nhse_staff_facilities.html")
        if "england.nhs.uk/publication/" in url:
            return "<main><p>Meeting papers.</p></main>"
        raise _fail(url)


def _gsweep(conn, client, since_days=30):
    return govuk_docs.Sweep(client, conn, TAX, WL, TODAY, log=lambda *a: None, since_days=since_days)


class GovukParsingTests(unittest.TestCase):
    def test_search_rows(self):
        docs, total = govuk_docs.parse_search(_json("govuk_closed_consultations.json"))
        ttk = next(d for d in docs if d.title.startswith("Tying the Knot"))
        self.assertEqual(ttk.base_path, "/government/consultations/tying-the-knot-reforming-weddings-law-in-england-and-wales")
        self.assertEqual(ttk.closing_date, "2026-09-24")
        self.assertEqual(ttk.doc_type, "closed_consultation")
        self.assertEqual(ttk.organisation, "Ministry of Justice")
        self.assertTrue(ttk.url.startswith("https://www.gov.uk/government/"))

    def test_ofcom_listing_skips_news_pdfs_and_welsh_copies(self):
        docs = govuk_docs.parse_ofcom_listing(_text("ofcom_listing.html"))
        urls = [d.url for d in docs]
        self.assertFalse([u for u in urls if "/siteassets/" in u])
        wg = next(d for d in docs if "Women and Girls" in d.title)
        self.assertEqual(wg.doc_type, "consultation")      # the edition reads it as a deadline
        self.assertEqual(wg.extra_text, "online safety")
        self.assertEqual(wg.opening_date, "2026-09-09")

    def test_ofcom_page_closing_date(self):
        self.assertEqual(govuk_docs.parse_ofcom_page(_text("ofcom_women_and_girls.html")), ("2026-11-04", "Open"))

    def test_nhse_feed(self):
        items = govuk_docs.parse_rss(_text("nhse_feed.xml"))
        title, link, pub, cats, _desc = items[0]
        self.assertEqual(title, "Guidance on NHS staff facilities")
        self.assertEqual(pub, "2026-10-15")
        self.assertEqual(cats, ["Gender identity"])
        self.assertIn("single-sex", govuk_docs.parse_nhse_page(_text("nhse_staff_facilities.html")))


class GovukSweepTests(unittest.TestCase):
    def _run(self, client=None):
        conn, client = _store(), client or GovukClient()
        sweep = _gsweep(conn, client)
        sweep.run()
        return conn, sweep, client, {r["base_path"]: r for r in conn.execute("SELECT * FROM govuk_docs")}

    def test_what_lands_on_our_ground(self):
        conn, sweep, client, rows = self._run()
        self.assertEqual(sweep.gaps, [])
        titles = {r["title"]: r for r in rows.values()}
        ttk = titles["Tying the Knot: Reforming weddings law in England and Wales"]
        self.assertEqual((ttk["closing_date"], ttk["source"]), ("2026-09-24", "govuk"))
        self.assertIn("Abortion statistics user engagement plan", titles)
        wg = next(r for t, r in titles.items() if "Women and Girls" in t)
        self.assertEqual((wg["closing_date"], wg["source"], wg["organisation"]), ("2026-11-04", "ofcom", "Ofcom"))
        self.assertIn("Guidance on NHS staff facilities", titles)
        self.assertEqual(titles["Guidance on NHS staff facilities"]["doc_type"], "guidance")
        self.assertEqual(titles["Guidance on NHS staff facilities"]["source"], "nhs-england")
        # "Ofcom" alone on Ofcom's own pages is not our ground
        self.assertFalse([t for t in titles if "Competition Act" in t or "1.4 GHz" in t])
        # Ofcom statements are not opened for a closing date
        self.assertFalse([u for u in client.urls if "statement-crisis-response-protocol" in u])

    def test_publications_need_tier_one_or_the_watchlist(self):
        _conn, _sweep, _client, rows = self._run()
        pubs = [r for r in rows.values() if r["source"] == "govuk" and r["doc_type"] not in govuk_docs.CONSULTATION_TYPES]
        self.assertTrue(pubs)
        for r in pubs:
            f = filt.filter_item(TAX, WL, r["title"], r["description"])
            self.assertTrue(f.tier == 1 or f.watchlist_hits, r["title"])

    def test_content_api_fills_a_missing_closing_date(self):
        closed = _json("govuk_closed_consultations.json")
        for r in closed["results"]:
            if r["title"].startswith("Tying the Knot"):
                r.pop("end_date", None)
        conn, sweep, client, rows = self._run(GovukClient(closed=closed))
        self.assertTrue([u for u in client.urls if u.startswith("https://www.gov.uk/api/content/government/consultations/tying")])
        ttk = next(r for r in rows.values() if r["title"].startswith("Tying the Knot"))
        self.assertEqual(ttk["closing_date"], "2026-09-24")

    def test_failures_are_gap_lines(self):
        conn, sweep, _client, rows = self._run(GovukClient(fail=("filter_organisations=", govuk_docs.OFCOM_LIST)))
        self.assertTrue([g for g in sweep.gaps if "publications" in g])
        self.assertTrue([g for g in sweep.gaps if g.startswith("Ofcom")])
        self.assertTrue(rows)                       # the rest still lands
        govuk_docs.write_gaps(conn, TODAY, sweep.gaps)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE edition = '2026-10-19' "
                                      "AND feed = 'govuk_docs'").fetchone()[0], len(sweep.gaps))

    def test_search_urls_are_the_documented_api(self):
        _conn, _sweep, client, _rows = self._run()
        searches = [u for u in client.urls if u.startswith(govuk_docs.SEARCH)]
        self.assertEqual(len(searches), 4)
        pubs = next(u for u in searches if "filter_organisations=" in u)
        for slug in ("department-of-health-and-social-care", "department-for-education", "home-office",
                     "ministry-of-justice", "government-equalities-office", "office-for-equality-and-opportunity",
                     "department-for-science-innovation-and-technology", "cabinet-office", "nhs-england",
                     "northern-ireland-office", "office-of-the-secretary-of-state-for-scotland",
                     "office-of-the-secretary-of-state-for-wales"):
            self.assertIn("filter_organisations=" + slug, pubs)


class StoreTests(unittest.TestCase):
    def test_agreed_columns(self):
        conn = _store()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(uk_petitions)")]
        self.assertEqual(cols[:12], ["petition_id", "title", "state", "signatures", "threshold_reached",
                                     "response_date", "debate_date", "url", "areas", "matched_terms",
                                     "first_seen", "last_seen"])
        cols = [r[1] for r in conn.execute("PRAGMA table_info(govuk_docs)")]
        self.assertEqual(cols[:11], ["base_path", "title", "doc_type", "organisation", "public_updated_at",
                                     "closing_date", "url", "areas", "matched_terms", "first_seen", "last_seen"])
        for t in ("uk_petitions", "govuk_docs", "uk_petition_counts", "uk_civic_runs"):
            self.assertIn(t, db.TABLES)


if __name__ == "__main__":
    unittest.main()
