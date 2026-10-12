"""Supreme Court of Canada judgments and leave (tools/ca_courts.py). No network:
pages come from tests/fixtures/ca_courts/, trimmed from the 1 October 2026 probe."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _load("ca_courts")
TAX = filt.load_taxonomy(cc.TAXONOMY)
WL = filt.load_watchlist(cc.WATCHLIST)
FIX = os.path.join(ROOT, "tests", "fixtures", "ca_courts")
TODAY = "2026-10-02"


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return ca_store.ensure_schema(conn)


class FakeClient:
    """Serves pages by URL substring; records every URL asked for."""

    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def _find(self, url, feed, slug):
        self.asked.append(url)
        for key, body in self.pages.items():
            if key in url:
                if isinstance(body, Exception):
                    raise FetchError(url, feed, slug, 1, body)
                return body
        raise FetchError(url, feed, slug, 1, OSError("no fixture for " + url))

    def get_text(self, url, feed, slug, archive=True, **_):
        return self._find(url, feed, slug)

    def get_json(self, url, feed, slug, archive=True, **_):
        return json.loads(self._find(url, feed, slug))


def judgment(name):
    j = cc.parse_item(fixture(name))
    areas, terms, tier, excerpt = cc.classify_judgment(TAX, WL, j["title"], j["subjects"],
                                                       j["headnote"])
    return j, areas, terms, tier


class HeadnoteTests(unittest.TestCase):
    def test_carter_is_area_2_from_its_headnote(self):
        j, areas, terms, tier = judgment("carter_2015scc5.html")
        self.assertEqual((j["citation"], j["scr"], j["docket"], j["date"]),
                         ("2015 SCC 5", "[2015] 1 SCR 331", "35591", "2015-02-06"))
        self.assertEqual(j["on_appeal_from"], "British Columbia")
        self.assertEqual(len(j["judges"]), 9)
        self.assertEqual(j["subjects"], ["Constitutional law", "Courts"])
        self.assertIn(2, areas)
        self.assertEqual(tier, 1)
        self.assertNotIn(1, areas, "the abortion precedent is cited after the headnote")
        self.assertEqual(j["matched_on"], "headnote")

    def test_the_headnote_stops_at_cases_cited_and_starts_after_the_parties(self):
        j, _, _, _ = judgment("carter_2015scc5.html")
        self.assertTrue(j["headnote"].startswith("Indexed as"))
        self.assertNotIn("Cases Cited", j["headnote"])
        self.assertNotIn("Euthanasia Prevention Coalition", j["headnote"],
                         "an intervener's name is not what the Court decided")

    def test_bedford_is_prostitution_and_free_speech(self):
        j, areas, _, _ = judgment("bedford_2013scc72.html")
        self.assertEqual(j["citation"], "2013 SCC 72")
        self.assertIn(12, areas)
        self.assertIn(7, areas)

    def test_trinity_western_is_speech_and_religion(self):
        j, areas, _, _ = judgment("twu_2018scc32.html")
        self.assertEqual((j["citation"], j["docket"]), ("2018 SCC 32", "37318"))
        self.assertEqual(j["subjects"], [], "TWU carries no subjects; the headnote decides")
        self.assertIn(7, areas)
        self.assertIn(8, areas)

    def test_a_title_alone_matches_nothing(self):
        for name in ("carter_2015scc5.html", "bedford_2013scc72.html", "twu_2018scc32.html"):
            title = cc.parse_item(fixture(name))["title"]
            self.assertEqual(filt.filter_item(TAX, WL, title).issue_areas, [], title)
            self.assertEqual(cc.classify_judgment(TAX, WL, title, [], "")[0], [], title)


class IntervenerTests(unittest.TestCase):
    def test_carter_interveners_include_the_euthanasia_prevention_coalition(self):
        names = judgment("carter_2015scc5.html")[0]["interveners"]
        for who in ("Euthanasia Prevention Coalition", "Evangelical Fellowship of Canada",
                    "Catholic Civil Rights League", "Christian Legal Fellowship",
                    "Dying With Dignity", "Association for Reformed Political Action Canada"):
            self.assertIn(who, names)
        # A name the Court's Word file wrapped across two lines is one name.
        self.assertIn("Alliance of People With Disabilities Who are Supportive of Legal "
                      "Assisted Dying Society", names)
        self.assertEqual(len(names), 26)

    def test_two_names_on_one_line_are_two_names(self):
        names = judgment("bedford_2013scc72.html")[0]["interveners"]
        self.assertIn("Christian Legal Fellowship", names)
        self.assertIn("Catholic Civil Rights League", names)
        self.assertIn("REAL Women of Canada", names)
        self.assertIn("AWCEP Asian Women for Equality Society, operating as Asian Women "
                      "Coalition Ending Prostitution", names)

    def test_a_comma_inside_a_name_is_kept(self):
        names = judgment("twu_2018scc32.html")[0]["interveners"]
        self.assertIn("Faith, Fealty & Creed Society", names)
        self.assertIn("Canadian Conference of Catholic Bishops", names)
        self.assertIn("Egale Canada Human Rights Trust", names)
        self.assertEqual(len(names), 24)


class FeedTests(unittest.TestCase):
    def test_a_relisted_old_judgment_is_not_read_again(self):
        conn = store()
        conn.execute("INSERT INTO ca_judgments (judgment_id, court, title, areas, first_seen, "
                     "last_seen) VALUES ('384', 'SCC', 'Ford v. Quebec', '[]', '2026-09-01', "
                     "'2026-09-01')")
        client = FakeClient({"json/rss.do": fixture("feed_judgments.json"),
                             "/item/": fixture("carter_2015scc5.html")})
        r = cc.Run(conn, client, TODAY, TAX, WL, log=lambda *a: None)
        r.judgments_feed()
        asked = [u for u in client.asked if "/item/" in u]
        self.assertEqual(len(asked), 3)
        self.assertFalse(any("/item/384/" in u for u in asked), "Ford (1988) was re-listed, not new")
        self.assertEqual(conn.execute("SELECT last_seen FROM ca_judgments WHERE judgment_id='384'")
                         .fetchone()[0], TODAY)
        # And a second run reads nothing at all.
        client.asked.clear()
        cc.Run(conn, client, TODAY, TAX, WL, log=lambda *a: None).judgments_feed()
        self.assertEqual([u for u in client.asked if "/item/" in u], [])

    def test_a_stored_judgment_keeps_its_interveners_as_a_list(self):
        conn = store()
        client = FakeClient({"/item/14637/": fixture("carter_2015scc5.html")})
        r = cc.Run(conn, client, TODAY, TAX, WL, log=lambda *a: None)
        self.assertTrue(r.read_judgment("14637"))
        row = conn.execute("SELECT * FROM ca_judgments").fetchone()
        self.assertIn("Euthanasia Prevention Coalition", json.loads(row["interveners"]))
        self.assertEqual(json.loads(row["areas"]), [2])
        self.assertEqual(row["url"], cc.ITEM.format(id="14637").replace("?iframe=true", ""))
        self.assertIsNone(row["triage_score"])
        self.assertEqual(r.landed[0][0], "2015 SCC 5")

    def test_a_page_that_fails_is_a_recorded_gap(self):
        conn = store()
        client = FakeClient({"scc-l-csc-a": OSError("503"),
                             "json/rss.do": fixture("feed_judgments.json"),
                             "/item/": OSError("timed out")})
        r = cc.run(conn, client, TODAY, tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual(r.read, 0)
        gaps = [g[0] for g in conn.execute("SELECT detail FROM gaps WHERE feed='ca-courts'")]
        self.assertEqual(len(gaps), 5, gaps)        # four items and the leave feed
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ca_judgments").fetchone()[0], 0)

    def test_a_norma_challenge_stops_the_run_with_one_gap(self):
        """Lexum's CAPTCHA is never answered: stop, say so once, read on later."""
        class Challenge(OSError):
            code = 403

        conn = store()
        client = FakeClient({"scc-l-csc-a": fixture("feed_leave.json"),
                             "json/rss.do": fixture("feed_judgments.json"),
                             "/item/": Challenge("Forbidden")})
        r = cc.run(conn, client, TODAY, tax=TAX, wl=WL, log=lambda *a: None)
        self.assertTrue(r.blocked)
        self.assertEqual(len([u for u in client.asked if "/item/" in u]), 1,
                         "nothing is asked after the challenge")
        self.assertNotIn(cc.LEAVE_FEED, client.asked)
        gaps = [g[0] for g in conn.execute("SELECT detail FROM gaps WHERE feed='ca-courts'")]
        self.assertEqual(len(gaps), 1)
        self.assertIn("Norma challenge", gaps[0])
        self.assertIn("never answered", gaps[0])

    def test_a_dry_run_stores_nothing(self):
        conn = store()
        client = FakeClient({"scc-csc/en/json": fixture("feed_judgments.json"),
                             "scc-l-csc-a/en/json": fixture("feed_leave.json")})
        cc.run(conn, client, TODAY, dry_run=True, tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual([u for u in client.asked if "/item/" in u], [])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ca_judgments").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ca_leave").fetchone()[0], 0)

    def test_the_page_cap_is_disclosed(self):
        conn = store()
        said = []
        client = FakeClient({"json/rss.do": fixture("feed_judgments.json"),
                             "/item/": fixture("carter_2015scc5.html")})
        r = cc.Run(conn, client, TODAY, TAX, WL, limit=2, log=said.append)
        r.judgments_feed()
        self.assertEqual(r.pages, 2)
        self.assertTrue(any("page cap (2) reached" in m for m in said))


class LeaveTests(unittest.TestCase):
    def pages(self):
        leave = fixture("leave_42341.html")
        return {"scc-l-csc-a/en/json": fixture("feed_leave.json"),
                "/item/21663/": leave,
                "/item/21662/": leave.replace("42341", "42342"),
                "/item/21683/": leave.replace("42341", "42343").replace(">\n                                Granted", ">Dismissed"),
                "search-recherche/": fixture("docket_35591.html")}

    def test_a_granted_leave_is_classified_on_the_registrars_summary(self):
        conn = store()
        client = FakeClient(self.pages())
        r = cc.Run(conn, client, TODAY, TAX, WL, log=lambda *a: None)
        r.leave_feed()
        rows = {row["docket"]: row for row in conn.execute("SELECT * FROM ca_leave")}
        self.assertEqual(set(rows), {"42341", "42342", "42343"})
        granted = rows["42341"]
        self.assertEqual(granted["status"], "Granted")
        self.assertEqual(granted["lexum_id"], "21663")
        self.assertIn(2, json.loads(granted["areas"]))
        self.assertNotIn("Case summaries are prepared", granted["summary"])
        self.assertEqual(granted["url"], cc.DOCKET.format(docket="42341"))
        dismissed = rows["42343"]
        self.assertEqual(dismissed["status"], "Dismissed")
        self.assertIsNone(dismissed["summary"])
        self.assertEqual(json.loads(dismissed["areas"]), [], "the parties' names match nothing")
        dockets = [u for u in client.asked if "search-recherche" in u]
        self.assertEqual(len(dockets), 2, "a docket page is read for a GRANTED leave only")

    def test_a_leave_already_read_is_not_read_again(self):
        conn = store()
        client = FakeClient(self.pages())
        cc.Run(conn, client, TODAY, TAX, WL, log=lambda *a: None).leave_feed()
        client.asked.clear()
        cc.Run(conn, client, TODAY, TAX, WL, log=lambda *a: None).leave_feed()
        self.assertEqual([u for u in client.asked if "/item/" in u or "search-recherche" in u], [])

    def test_leave_status_reads_the_feed_note(self):
        self.assertEqual(cc.leave_status("Granted - New document published on 2026-10-01"), "Granted")
        self.assertEqual(cc.leave_status("Dismissed - Document updated on 2026-09-03"), "Dismissed")
        self.assertIsNone(cc.leave_status("New document published on 2026-10-01"))


class BackfillTests(unittest.TestCase):
    def test_the_year_index_parses(self):
        total, rows = cc.parse_year_index(fixture("index_2015_p1.html"))
        self.assertEqual(total, 66)
        self.assertEqual(rows[0], {"id": "15682", "title": "R. v. Riesberry",
                                   "citation": "2015 SCC 65", "scr": "[2015] 3 SCR 1167",
                                   "date": "2015-12-18", "subjects": ["Criminal law"]})

    def test_held_ids_are_skipped(self):
        conn = store()
        conn.execute("INSERT INTO ca_judgments (judgment_id, court, date, areas) "
                     "VALUES ('15682', 'SCC', '2015-12-18', '[]')")
        client = FakeClient({"nav_date.do": fixture("index_2015_p1.html"),
                             "/item/": fixture("carter_2015scc5.html")})
        r = cc.Run(conn, client, TODAY, TAX, WL, limit=1, log=lambda *a: None)
        r.backfill(2015, 2015)
        items = [u for u in client.asked if "/item/" in u]
        self.assertEqual(items, [cc.ITEM.format(id="15680")])


class RobotsTests(unittest.TestCase):
    def test_disallowed_paths_are_never_fetched(self):
        self.assertFalse(cc.allowed("https://www.scc-csc.ca/cso-dce/2015SCC-CSC5"))
        self.assertFalse(cc.allowed("https://www.scc-csc.ca/cases-dossiers/search-recherche/22551/"))
        self.assertFalse(cc.allowed("https://decisions.scc-csc.ca/icm/icm/en/item/120620/index.do"))
        self.assertTrue(cc.allowed(cc.DOCKET.format(docket="35591")))
        self.assertTrue(cc.allowed(cc.ITEM.format(id="14637")))


class ContextOnlyTests(unittest.TestCase):
    def test_a_judgment_never_reaches_the_5ca(self):
        with open(os.path.join(ROOT, "tools", "ca_5ca.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("ca_judgments", src)
        self.assertNotIn("ca_leave", src)

    def test_the_judge_reads_judgments_under_their_own_frame(self):
        ct = _load("ca_triage")
        conn = store()
        r = cc.Run(conn, FakeClient({"/item/": fixture("carter_2015scc5.html")}), TODAY, TAX, WL,
                   log=lambda *a: None)
        r.read_judgment("14637")
        items = ct.pending(conn)
        self.assertEqual([i.id for i in items], ["ca_judgments:14637"])
        self.assertIn("Charter of Rights", items[0].text, "the catchwords lead")
        seen = []

        def transport(payload, key):
            seen.append(payload["system"])
            batch = json.loads(payload["messages"][0]["content"])
            rows = [{"id": b["id"], "score": 3, "areas": b["candidate_areas"],
                     "why_it_matters": "Struck down the ban."} for b in batch]
            return {"content": [{"type": "text", "text": json.dumps(rows)}], "model": "m",
                    "usage": {"input_tokens": 1, "output_tokens": 1}, "stop_reason": "end_turn"}

        self.assertEqual(ct.judge(conn, items, "k", TODAY, log=lambda *a: None,
                                  transport=transport), (1, 0))
        self.assertIn("JUDGMENTS of the Supreme Court of Canada", seen[0])
        self.assertNotIn("presenting a petition", seen[0])
        self.assertEqual(conn.execute("SELECT triage_score FROM ca_judgments").fetchone()[0], 3)
        self.assertEqual(ct.rescore(conn, "ca_judgments:14637"), 1)

    def test_the_retag_reproduces_what_the_collector_stored(self):
        rt = _load("ca_retag")
        conn = store()
        r = cc.Run(conn, FakeClient({"/item/14637/": fixture("carter_2015scc5.html"),
                                     "/item/13389/": fixture("bedford_2013scc72.html")}),
                   TODAY, TAX, WL, log=lambda *a: None)
        r.read_judgment("14637")
        r.read_judgment("13389")
        said = []
        self.assertEqual(rt.retag(conn, TAX, WL, log=said.append), [])
        self.assertTrue(any("ca_judgments" in m and "2/2" in m for m in said), said)


if __name__ == "__main__":
    unittest.main()
