"""Austria's Landtage (AT6): tools/at_landtage.py, src/atl_store.py and the
Landtage section of the Austrian edition. No network: every page is a real
one read on 12 October 2026, trimmed, in tests/fixtures/at_landtage/."""

import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import atl_store, db, filter as filt, noise  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "at_landtage")
TODAY = "2026-10-12"


def _load():
    spec = importlib.util.spec_from_file_location(
        "at_landtage", os.path.join(ROOT, "tools", "at_landtage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


atl = _load()
TAX = filt.load_taxonomy(atl.TAXONOMY, country=atl.TAXONOMY_COUNTRY)
WL = atl.empty_watchlist()


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def fresh_db():
    return db.init_db(db.connect(":memory:"))


def quiet(*_a, **_k):
    return None


class FakeClient:
    """Serves the fixtures by URL; records what was asked for."""

    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 0

    ROUTES = (
        ("noe-landtag.gv.at/gegenstaende/XX/suche?page=1", "noe-list.html"),
        ("noe-landtag.gv.at/gegenstaende/XX/suche", None),           # later pages: empty
        ("noe-landtag.gv.at/gegenstaende/XX/", "noe-detail.html"),
        ("pallast-p/pub/documents?type=", "stmk-list.html"),
        ("ref=67464713", "stmk-beschluss.html"),
        ("ref=ee2a735c", "stmk-beschluss.html"),
        ("pallast-p/pub/document?ref=", "stmk-detail.html"),
        ("internetltgbeilagen/Start.jsp", "@ooe-start"),
        ("InternetLtgBeilagenSuche.jsp", "ooe-search.html"),
        ("InternetLtgBeilagenAnzeige", "ooe-detail-motion.html"),
        ("infodat/suchergebnisse", "wien-list.html"),
        ("lpi/searchExtern", "sbg-search.html"),
        ("ReadViewEntries&CollapseView", "vbg-top.xml"),
        ("ReadViewEntries&RestrictToCategory", "vbg-period.xml"),
        ("?OpenDocument", "vbg-detail.html"),
        ("VorlZahl_GPXXIII.xsp", "bgld-list.html"),
        ("data.bka.gv.at/ris", "ris-landesrecht.json"),
    )

    def __init__(self, robots=None, fail=()):
        self.robots = robots or {}
        self.fail = set(fail)
        self.fetched = []
        self.posted = []

    def _serve(self, url):
        if url.endswith("/robots.txt"):
            host = url.split("/")[2]
            if host in self.robots:
                return self.robots[host]
            raise FetchError(url, "t", "robots", 1, "404")
        self.fetched.append(url)
        if any(f in url for f in self.fail):
            raise FetchError(url, "t", "x", 3, "timeout")
        for needle, name in self.ROUTES:
            if needle in url:
                if name is None:
                    return "<html></html>"
                if name == "@ooe-start":
                    return '<a href="Start.jsp?SessionID=SID-ABC123-DEF456">x</a>'
                return fx(name)
        raise AssertionError("unexpected URL " + url)

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None, timeout=None):
        return self._serve(url)

    def post_form(self, url, fields, feed, slug, timeout=None, archive=False):
        self.posted.append((url, dict(fields)))
        return fx("stmk-page.xml")


class Parsers(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(atl.de_date("eingebracht am 09.10.2026, 08:27"), "2026-10-09")
        self.assertEqual(atl.us_date("Eingelangt 10/02/2026"), "2026-10-02")   # MM/DD
        self.assertIsNone(atl.de_date("31.02.2026"))

    def test_kinds(self):
        k = atl.kind_of
        self.assertEqual(k("Regierungsvorlage"), "bill")
        self.assertEqual(k("Selbstständiger Antrag von Abgeordneten"), "motion")
        self.assertEqual(k("Schriftliche Anfragebeantwortung"), "answer")
        self.assertEqual(k("Schriftliche Anfrage an ein Mitglied der Landesregierung"), "question")
        self.assertEqual(k("Beschluss"), "decision")
        self.assertEqual(k("Begutachtungsverfahren"), "consultation")
        self.assertEqual(k("Antwort"), "answer")
        self.assertEqual(k("Aktuelle Stunde"), "other")
        self.assertEqual(k(None, "Antrag der Abg. X betreffend Y"), "motion")
        self.assertEqual(atl.OOE_ART["SAAN"], "answer")

    def test_noe(self):
        rows = atl.parse_noe_list(fx("noe-list.html"))
        self.assertEqual(len(rows), 8)
        first = rows[0]
        self.assertEqual(first["item_key"], "noe/XX/1096")
        self.assertEqual(first["number"], "Ltg.-1096/XX-2026")
        self.assertEqual(first["doc_type"], "Eingabe an den Landtag (EL)")
        q = rows[1]
        self.assertEqual((q["kind"], q["by_whom"]), ("question", "Kollermann, Edith"))
        self.assertIsNone(q["date"])                       # the list is undated
        d = atl.parse_noe_detail(fx("noe-detail.html"))
        self.assertEqual(d["date"], "2026-10-05")
        self.assertEqual(d["status"], "Offen")
        self.assertEqual(d["latest"], "Einbringung on 2026-10-05")

    def test_stmk(self):
        rows = atl.parse_stmk_rows(fx("stmk-list.html"))
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["item_key"], "stmk/XIX/1715/1")
        self.assertEqual(rows[0]["kind"], "bill")
        self.assertEqual(rows[2]["by_whom"], "Grüne")
        page = atl.parse_stmk_rows(fx("stmk-page.xml"))
        keys = {r["item_key"]: r for r in page}
        self.assertEqual(keys["stmk/XIX/1265/6"]["kind"], "decision")
        vs, action = atl._pallast_view_state(fx("stmk-list.html"))
        self.assertTrue(vs and action.startswith("/pallast-p/pub/documents"))
        d = atl.parse_stmk_detail(fx("stmk-detail.html"))
        self.assertEqual(d["date"], "2026-10-09")
        self.assertIn("Sandra Krautwaschl (Grüne)", d["by_whom"])
        b = atl.parse_stmk_detail(fx("stmk-beschluss.html"))
        self.assertEqual(b["date"], "2026-09-29")
        self.assertEqual(b["basis"], "decided")
        self.assertEqual(b["status"], "Landtagsbeschluss Nr. 531, 22. Landtagssitzung")
        self.assertEqual(b["outcome"],
                         "Der Beschluss wurde einstimmig (mit den Stimmen von FPÖ und ÖVP) angenommen")

    def test_ooe(self):
        rows = atl.parse_ooe_list(fx("ooe-search.html"))
        self.assertEqual(len(rows), 30)
        ia = next(r for r in rows if r["item_key"] == "ooe/XXIX/1469/2026")
        self.assertEqual((ia["doc_type"], ia["kind"]), ("IA", "motion"))
        self.assertIn("jahr=2026&nummer=1469&gp=XXIX", ia["url"])
        self.assertEqual(atl.parse_ooe_detail(fx("ooe-detail-motion.html"))["date"], "2026-10-01")
        law = atl.parse_ooe_detail(fx("ooe-detail-law.html"))
        self.assertEqual(law["status"], "100% abgeschlossen")
        self.assertEqual(law["outcome"], "Antrag angenommen - mehrstimmig - Dafür: ÖVP, FPÖ, SPÖ / "
                                         "Dagegen: GRÜNE, MFG, NEOS")

    def test_wien(self):
        rows, last = atl.parse_wien_list(fx("wien-list.html"))
        self.assertEqual(len(rows), 20)
        self.assertEqual(last, 5)                         # the page's own "last page" link
        kt = [r for r in rows if "Kopftuch" in (r["title"] or "")]
        self.assertTrue(kt)
        self.assertEqual(kt[0]["date"], "2026-09-22")
        self.assertEqual(kt[0]["date_basis"], "sitting")
        self.assertTrue(kt[0]["item_key"].startswith("wien/"))

    def test_sbg(self):
        rows = atl.parse_sbg_list(fx("sbg-search.html"))
        keys = {r["item_key"]: r for r in rows}
        a = keys["sbg/17/4/362-BEA"]
        self.assertEqual((a["kind"], a["date"], a["date_basis"]), ("answer", "2026-09-30", "reported"))
        self.assertTrue(a["url"].endswith("viewExtern?id=41544"))
        # The referenced question under an answer is not a row of its own here.
        self.assertNotIn("sbg/17/4/362-ANF", keys)
        queer = [r for r in rows if "queere Menschen" in r["title"]]
        self.assertEqual(queer[0]["kind"], "motion")

    def test_vbg(self):
        top = atl.parse_vbg_top(fx("vbg-top.xml"))
        cat = next(t for t in top if t.startswith(atl.VBG_PERIOD))
        self.assertIn("2029", cat)
        rows = atl.parse_vbg_view(fx("vbg-period.xml"))
        self.assertTrue(all(r["item_key"].startswith("vbg/") and len(r["item_key"]) == 36
                            for r in rows))
        first = rows[0]
        self.assertEqual((first["doc_type"], first["kind"], first["year"]),
                         ("Aktuelle Stunde", "other", "2026"))
        self.assertTrue(any("Palliativversorgung" in r["title"] for r in rows))
        self.assertEqual(atl.parse_vbg_detail(fx("vbg-detail.html"))["date"], "2026-10-02")
        treated = atl.parse_vbg_detail(fx("vbg-detail-treated.html"))
        self.assertEqual(treated["date"], "2025-12-05")
        self.assertEqual(treated["status"], "dealt with in the Landtag on 2025-12-11")

    def test_bgld(self):
        rows = atl.parse_bgld_list(fx("bgld-list.html"))
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["item_key"], "bgld/XXIII/2100-0603")
        self.assertEqual(rows[0]["kind"], "motion")

    def test_ris(self):
        rows = atl.parse_ris(json.loads(fx("ris-landesrecht.json")))
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["item_key"], r["land"], r["kind"], r["source"]),
                         ("ris/LGBLA_WI_20261009_37", "wien", "law", "ris"))
        self.assertEqual((r["date"], r["number"]), ("2026-10-09", "LGBl. Nr. 37/2026"))
        self.assertEqual(r["outcome"], "Beschlossen am 2026-09-22")


class Pull(unittest.TestCase):
    def run_land(self, conn, land, client=None, today=TODAY):
        client = client or FakeClient()
        return atl.run_land(conn, client, land, today, "2026-09-01", today, TAX, WL,
                            log=quiet), client

    def test_every_land_end_to_end(self):
        conn = fresh_db()
        for land in atl_store.READ:
            (seen, _ours, gaps), _ = self.run_land(conn, land)
            self.assertGreater(seen, 0, land)
            self.assertEqual(gaps, [], land)
        n = dict(conn.execute("SELECT land, COUNT(*) FROM atl_items GROUP BY land"))
        self.assertEqual(set(n), set(atl_store.READ))
        reads = atl_store.reads(conn)
        self.assertEqual(reads["wien"][2], TODAY)            # last_ok
        # Steiermark: the two decisions on our ground had their own page read.
        r = conn.execute("SELECT date, date_basis, outcome FROM atl_items "
                         "WHERE item_key='stmk/XIX/1265/6'").fetchone()
        self.assertEqual(r[:2], ("2026-09-29", "decided"))
        self.assertIn("FPÖ und ÖVP", r[2])
        # Vorarlberg's palliative-care question: area 2, dated from its own page.
        r = conn.execute("SELECT areas, date FROM atl_items WHERE title LIKE "
                         "'%Palliativversorgung%'").fetchone()
        self.assertIn(2, json.loads(r[0]))
        self.assertEqual(r[1], "2026-10-02")                 # the fixture page's date

    def test_only_rows_on_our_ground_get_their_page_read(self):
        conn = fresh_db()
        (_, ours, _), client = self.run_land(conn, "noe")
        details = [u for u in client.fetched if "/gegenstaende/XX/XX-" in u]
        self.assertEqual(len(details), ours)

    def test_baseline_rows_are_never_new(self):
        conn = fresh_db()
        self.run_land(conn, "bgld")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM atl_items WHERE baseline=1"
                                      ).fetchone()[0], 8)
        # A second read: nothing new, nothing re-baselined; a new row would be 0.
        conn.execute("DELETE FROM atl_items WHERE item_key='bgld/XXIII/2100-0603'")
        self.run_land(conn, "bgld", today="2026-10-19")
        self.assertEqual(tuple(conn.execute("SELECT baseline, first_seen FROM atl_items WHERE "
                                            "item_key='bgld/XXIII/2100-0603'").fetchone()),
                         (0, "2026-10-19"))

    def test_dated_rows_are_never_baseline(self):
        conn = fresh_db()
        self.run_land(conn, "wien")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM atl_items WHERE baseline=1"
                                      ).fetchone()[0], 0)

    def test_robots_disallow_is_honoured_and_is_a_gap(self):
        conn = fresh_db()
        client = FakeClient(robots={"data.bka.gv.at": "User-agent: *\nDisallow: /\n"})
        (seen, _, gaps), _ = self.run_land(conn, "ris", client)
        self.assertEqual(seen, 0)
        self.assertEqual(client.fetched, [])                 # never asked
        self.assertIn("robots.txt disallows", gaps[0])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='at-landtage'"
                                      ).fetchone()[0], 1)

    def test_wien_disallowed_paths_are_never_used(self):
        rules = "User-agent: *\nDisallow: /infodat/ergli\nDisallow: /infodat/sukri\n"
        conn = fresh_db()
        (seen, _, gaps), client = self.run_land(
            conn, "wien", FakeClient(robots={"www.wien.gv.at": rules}))
        self.assertGreater(seen, 0)
        self.assertEqual(gaps, [])
        self.assertFalse(any("ergli" in u or "sukri" in u for u in client.fetched))

    def test_failed_list_is_a_gap_and_costs_nothing_else(self):
        conn = fresh_db()
        (seen, _, gaps), _ = self.run_land(conn, "sbg", FakeClient(fail={"searchExtern"}))
        self.assertEqual(seen, 0)
        self.assertEqual(len(gaps), 1)
        self.assertIsNone(atl_store.reads(conn)["sbg"][2])   # no last_ok

    def test_stmk_pages_with_the_view_state(self):
        conn = fresh_db()
        _, client = self.run_land(conn, "stmk")
        url, fields = client.posted[0]
        self.assertTrue(url.startswith("https://pallast2.stmk.gv.at/pallast-p/pub/documents"))
        self.assertEqual(fields["contentForm:documentsTable_rows"], "100")
        self.assertTrue(fields["javax.faces.ViewState"])

    def test_reclassify_offline_and_watchlist_by_key(self):
        conn = fresh_db()
        self.run_land(conn, "bgld")
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "watchlist-at.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('landtage:\n  "bgld/XXIII/2100-0603": {areas: [9], why: "test"}\n')
            atl.reclassify(conn, TAX, log=quiet, wl_path=path)
        finally:
            shutil.rmtree(tmp)
        r = conn.execute("SELECT areas, matched_terms FROM atl_items WHERE "
                         "item_key='bgld/XXIII/2100-0603'").fetchone()
        self.assertEqual(json.loads(r[0]), [9])
        self.assertIn("watch:bgld/XXIII/2100-0603", json.loads(r[1]))

    def test_watchlist_file_section_is_well_formed(self):
        wl = atl_store.watchlist()
        for key, (areas, why) in wl.items():
            self.assertRegex(key, r"^(wien|noe|ooe|stmk|sbg|vbg|bgld|ris)/")
            self.assertTrue(areas and why)


class Schema(unittest.TestCase):
    def test_tables_declared_and_created(self):
        conn = fresh_db()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in atl_store.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertIn(t, have)

    def test_schema_is_idempotent(self):
        conn = sqlite3.connect(":memory:")
        atl_store.ensure_schema(conn)
        atl_store.ensure_schema(conn)

    def test_nine_landtage_seven_read_two_blocked(self):
        self.assertEqual(len(atl_store.LANDTAGE), 9)
        self.assertEqual(set(atl_store.READ) | set(atl_store.BLOCKED),
                         {c for c, _, _ in atl_store.LANDTAGE})
        self.assertEqual(set(atl_store.READ), set(atl.READERS) - {"ris"})


class Edition(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        self.eds = os.path.join(self.tmp, "editions")
        os.makedirs(self.cfg)
        os.makedirs(self.eds)
        for name in ("watchlist-at.yaml", "edition-noise-at.yaml"):
            shutil.copy(os.path.join(ROOT, "config", name), self.cfg)
        self.conn = fresh_db()
        self.conn.row_factory = sqlite3.Row
        for land in atl_store.READ:
            atl.run_land(self.conn, FakeClient(), land, TODAY, "2026-09-01", TODAY, TAX, WL,
                         log=quiet)

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def render(self, since="2026-09-01"):
        return ce.render(self.conn, ce.adapter("at"), TODAY, since, config_dir=self.cfg,
                         directory=self.eds)

    def test_landtage_section_after_the_watchlist(self):
        text = self.render()
        self.assertIn("## Landtage", text)
        self.assertLess(text.index("## Watchlist"), text.index("## Landtage"))
        self.assertLess(text.index("## Landtage"), text.index("## Coverage"))
        self.assertIn("Plus **", text)                        # the In-brief line
        self.assertIn("das Kopftuchverbot bis 14 Jahre an allen", text)
        self.assertIn("Wiener Landtag: question (Mündliche Anfrage)", text)
        self.assertIn("dealt with at the sitting of 22 September 2026", text)
        # Steiermark's decision with its Klubs, in the Landtag's words.
        self.assertIn("Recorded decision: “Der Beschluss wurde einstimmig", text)
        # Not a quiet week: the Landtage had items though the Nationalrat had none.
        self.assertNotIn("A quiet week", text)

    def test_coverage_names_what_is_not_read(self):
        text = self.render()
        self.assertIn("Kärnten not read: www.ktn.gv.at", text)
        self.assertIn("Tirol not read: lte.tirol.gv.at", text)
        self.assertIn("RIS Landesrecht (adopted Land laws)", text)
        self.assertIn("Landtage read (last read): Wien 12 Oct", text)

    def test_undated_baseline_rows_stay_out(self):
        # Burgenland's first read: undated rows, all baseline, none shown.
        self.conn.execute("UPDATE atl_items SET areas='[9]' WHERE land='bgld'")
        text = self.render()
        self.assertNotIn("bgld/XXIII/", text)
        # A row first seen in a later week is shown, dated by that week.
        self.conn.execute("UPDATE atl_items SET baseline=0 WHERE item_key='bgld/XXIII/2100-0603'")
        text = self.render()
        self.assertIn("bgld/XXIII/2100-0603", text)
        self.assertIn("first seen by us 12 October 2026", text)

    def test_other_documents_are_stored_not_shown(self):
        got = ce.adapter("at").extra_sections(self.conn, "2026-09-01", TODAY, {})[0][2]
        self.assertFalse(any(it["kind"] not in ce.KIND_NAMES for it in got))
        keys = {it["key"] for it in got}
        others = {r[0] for r in self.conn.execute(
            "SELECT item_key FROM atl_items WHERE kind='other' AND areas!='[]'")}
        self.assertFalse(keys & others)

    def test_dm_counts_the_landtage(self):
        text = ce.dm_summary(self.conn, ce.adapter("at"), TODAY, "2026-09-01",
                             config_dir=self.cfg, directory=self.eds)
        self.assertIn("*Landtage*:", text)

    def test_a_country_without_the_hook_is_unchanged(self):
        self.assertIsNone(ce.adapter("it").extra_sections)


if __name__ == "__main__":
    unittest.main()


class RobotsUnreachableTests(unittest.TestCase):
    """RFC 9309 2.3.1 (12 October 2026): a 5xx or no answer for robots.txt
    is read as Disallow: /; a 4xx means no rules."""

    def _ctx(self, cause):
        import urllib.error
        from src import prov_fetch
        from src.http import FetchError

        class Client:
            user_agent = "CitizenGO-ParlMonitor/1.0"
            throttle = 0

            def get_text(self, url, *a, **k):
                raise FetchError(url, "f", "s", 1, cause)

        ctx = prov_fetch.Context.__new__(prov_fetch.Context)
        ctx.client, ctx.feed, ctx.robots, ctx._robots = Client(), "f", True, {}
        ctx.gaps = []
        ctx.gap = ctx.gaps.append
        ctx.log = lambda *a, **k: None
        ctx.robots_sleep = lambda s: None   # read_robots retries: no real waits
        return ctx, urllib.error

    def test_503_disallows(self):
        import urllib.error
        ctx, _ = self._ctx(urllib.error.HTTPError("u", 503, "x", {}, None))
        self.assertFalse(ctx.allowed("https://example.at/lpi/searchExtern"))
        self.assertTrue(ctx.gaps)

    def test_no_answer_disallows(self):
        ctx, _ = self._ctx(OSError("timed out"))
        self.assertFalse(ctx.allowed("https://example.at/x"))

    def test_404_means_no_rules(self):
        import urllib.error
        ctx, _ = self._ctx(urllib.error.HTTPError("u", 404, "x", {}, None))
        self.assertTrue(ctx.allowed("https://example.at/x"))
