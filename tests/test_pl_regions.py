"""Poland's voivodeship assemblies (sejmiki): tools/pl_regions.py and the
"Regional assemblies" section of the Polish edition (src/editions/pl.py).

Fixtures under tests/fixtures/pl_regions/ are trimmed copies of the live
sources read on 13 October 2026: positions of the Mazowieckie and Podlaskie
journals' September month list (e-Dziennik /api/positions), the Mazowieckie
CMS year page (its month list) and two month pages (Mazowieckie, Śląskie),
rows of Łódzkie's one-page table of the term, two sittings of Podkarpackie's
index and one sitting's attachments. One journal position is EDITED: a
supervisory ruling on a municipal council's act with its Subject changed to
"Sejmik Województwa Mazowieckiego" and its position to 99999, because no
ruling on a sejmik's act was published in the two months read. No network.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce  # noqa: E402
from src import db, filter as filt, pl_regions_store as plr  # noqa: E402
from src.editions import pl as pl_ed  # noqa: E402
from tools import pl_regions as R  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "pl_regions")
TAX = os.path.join(ROOT, "config", "taxonomy-pl.yaml")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    """get_json / get_text from fixtures, by URL (exact, or a prefix ending '*')."""

    user_agent = "citizengo-parlmonitor/1.0 (+test)"
    throttle = 1.0

    def __init__(self, pages):
        self.pages = pages
        self.urls = []

    def _get(self, url):
        if url.endswith("/robots.txt"):
            raise R.FetchError(url, R.FEED, "robots", 1,
                               urllib.error.HTTPError(url, 404, "Not Found", {}, None))
        self.urls.append(url)
        for key, body in self.pages:
            if url == key or (key.endswith("*") and url.startswith(key[:-1])):
                return body
        raise R.FetchError(url, R.FEED, "test", 1, "no fixture")

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._get(url))

    def get_text(self, url, feed, slug, **kw):
        return self._get(url)

    def set_host_throttle(self, host, seconds):
        pass


def by_key(acts):
    return {a["key"]: a for a in acts}


class JournalParse(unittest.TestCase):
    def test_sejmik_positions_kept_others_dropped(self):
        acts = by_key(R.parse_journal(json.loads(fixture("journal_mz_2026_09.json")), "mz",
                                      R.JOURNALS["mz"]))
        self.assertEqual(sorted(acts), ["mz/dz/2026/9183", "mz/dz/2026/99999"])
        a = acts["mz/dz/2026/9183"]
        self.assertEqual(a["number"], "154/26")
        self.assertEqual(a["kind"], "uchwała")
        self.assertEqual(a["adopted"], "2026-09-22")
        self.assertEqual(a["published"][:7], "2026-09")
        self.assertEqual(a["url"], "https://edziennik.mazowieckie.pl/legalact/2026/9183/")
        self.assertIn("poz. 9183", a["journal_ref"])
        self.assertIn("dzików", a["title"])

    def test_ruling_on_a_sejmik_act_names_the_sejmik(self):
        a = by_key(R.parse_journal(json.loads(fixture("journal_mz_2026_09.json")), "mz",
                                   R.JOURNALS["mz"]))["mz/dz/2026/99999"]
        self.assertEqual(a["kind"], "rozstrzygnięcie nadzorcze")
        self.assertIsNone(a["number"])
        self.assertTrue(a["title"].endswith("(Sejmik Województwa Mazowieckiego)"))

    def test_genitive_publisher(self):
        # Podlaskie's journal names the publisher 'Sejmiku Województwa Podlaskiego'.
        acts = R.parse_journal(json.loads(fixture("journal_pd_2026_09.json")), "pd", R.JOURNALS["pd"])
        self.assertEqual(len(acts), 2)
        self.assertEqual(acts[0]["number"], "XXVIII/317/2026")

    def test_another_region_sejmik_not_taken(self):
        self.assertEqual(R.parse_journal(json.loads(fixture("journal_pd_2026_09.json")), "mz",
                                         R.JOURNALS["mz"]), [])

    def test_months_cross_the_year(self):
        self.assertEqual(R._months("2026-01-05"), [(2026, 1), (2025, 12)])
        self.assertEqual(R._months("2026-10-13"), [(2026, 10), (2026, 9)])


class RegisterParse(unittest.TestCase):
    def test_cms_months_newest_first(self):
        months = R.parse_cms_months(fixture("cms_mz_2026.html"), R.CMS["mz"])
        self.assertTrue(months[0].startswith("https://bip.mazovia.pl/pl/bip/sejmik/uchwaly-sejmiku/?p=2026%5E"))
        self.assertIn("wrzesie%C5%84", months[0])
        self.assertEqual(len(months), len(set(months)))

    def test_cms_mazowieckie(self):
        acts = R.parse_cms(fixture("cms_mz_month.html"), "mz", R.CMS["mz"])
        self.assertEqual(len(acts), 3)
        a = acts[0]
        self.assertRegex(a["key"], r"^mz/\d+/26$")
        self.assertEqual(a["adopted"], "2026-09-22")
        self.assertTrue(a["title"].startswith(("w sprawie", "zmieniaj")))
        self.assertNotIn("Czego dotyczy", a["title"])
        self.assertTrue(a["url"].startswith("https://bip.mazovia.pl/pl/bip/sejmik/uchwaly-sejmiku/rejestr-uchwal-sejmiku/"))

    def test_cms_slaskie(self):
        acts = R.parse_cms(fixture("cms_sl_month.html"), "sl", R.CMS["sl"])
        self.assertEqual(acts[0]["key"], "sl/VII/30/10/2026")
        self.assertEqual(acts[0]["adopted"], "2026-09-21")
        self.assertIn("Radzie Społecznej", acts[0]["title"])
        self.assertTrue(acts[0]["url"].startswith("https://bip.slaskie.pl/sejmik_wojewodztwa/"))

    def test_lodzkie_table(self):
        acts = by_key(R.parse_lodzkie(fixture("ld.html")))
        a = acts["ld/XXXI/396/2026"]
        self.assertEqual(a["adopted"], "2026-09-22")
        self.assertEqual(a["kind"], "stanowisko")
        self.assertEqual(a["session"], "XXXI sesja")
        self.assertEqual(a["url"], "https://bip.lodzkie.pl/files/xxxi.396.2026_2.pdf")
        self.assertIn("ld/XXV/307/2026", acts)

    def test_podkarpackie(self):
        sessions = R.parse_pk_index(fixture("pk_index.html"))
        self.assertEqual(len(sessions), 2)
        self.assertTrue(sessions[0][1].startswith("XXXI sesja"))
        acts = R.parse_pk_session(fixture("pk_session.html"), sessions[0][0])
        self.assertEqual(acts[0]["key"], "pk/XXXI/520/26")
        self.assertEqual(acts[0]["adopted"], "2026-08-31")
        self.assertEqual(acts[0]["session"], "XXXI sesja")
        self.assertEqual(acts[0]["kind"], "stanowisko")
        self.assertIn("stanowiska Sejmiku", acts[0]["title"])

    def test_dates(self):
        self.assertEqual(R.iso("22 września 2026 r."), "2026-09-22")
        self.assertEqual(R.iso("2.09.2026"), "2026-09-02")
        self.assertIsNone(R.iso("bez daty"))


def act(key, title, region="ld", source="bip", adopted="2026-10-07", published=None, number=None):
    return {"key": key, "region": region, "source": source, "number": number or key.split("/", 1)[1],
            "kind": R.kind_of(title), "title": title, "adopted": adopted, "published": published,
            "session": None, "url": "https://example.test/" + key,
            "journal_ref": "Dziennik Urzędowy Województwa {0} 2026, poz. {1}".format(
                plr.SEJMIK[region].split("Województwa ")[1], key.rsplit("/", 1)[1])
            if source == "journal" else None}


class Classification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAX, country="pl")

    def areas(self, title, key="ld/I/1/2026", watch=None):
        return R.classify(self.tax, R.empty_watchlist(), act(key, title), watch).issue_areas

    def test_in_vitro_programme(self):
        self.assertIn(10, self.areas("w sprawie przyjęcia programu polityki zdrowotnej leczenia "
                                     "niepłodności metodą zapłodnienia pozaustrojowego"))

    def test_lgbt_resolution(self):
        self.assertIn(5, self.areas("w sprawie przyjęcia stanowiska w sprawie wprowadzenia ideologii "
                                    "LGBT do wspólnot samorządowych"))

    def test_budget_is_off_ground(self):
        self.assertEqual(self.areas("w sprawie zmian budżetu Województwa Łódzkiego na 2026 rok"), [])

    def test_watched_repeal_by_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "watchlist-pl.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('regional:\n  "ld/II/9/2026": {areas: [9], why: "repeals the family charter"}\n')
            self.assertEqual(self.areas("w sprawie uchylenia uchwały nr XVII/236/19",
                                        key="ld/II/9/2026", watch=path), [9])


def scratch_db(tmp):
    return db.init_db(db.connect(os.path.join(tmp, "pm.db")))


class Storing(unittest.TestCase):
    def test_seed_flag_and_update(self):
        tax = filt.load_taxonomy(TAX, country="pl")
        with tempfile.TemporaryDirectory() as tmp:
            conn = scratch_db(tmp)
            a = act("ld/XXXI/400/2026", "w sprawie in vitro")
            self.assertEqual(R.store_all(conn, [a], tax, R.empty_watchlist(), "2026-10-13", seed=True),
                             (1, 1, 1))
            self.assertEqual(R.store_all(conn, [a], tax, R.empty_watchlist(), "2026-10-20"), (1, 1, 0))
            row = conn.execute("SELECT seed, first_seen, last_seen FROM plr_acts").fetchone()
            self.assertEqual(tuple(row), (1, "2026-10-13", "2026-10-20"))
            self.assertFalse(R.first_read(conn, "bip:ld"))
            self.assertTrue(R.first_read(conn, "bip:mz"))


def run_main(pages, args, tmp):
    path = os.path.join(tmp, "pm.db")
    client = FakeClient(pages)
    orig = R.HttpClient
    R.HttpClient = lambda **kw: client
    try:
        rc = R.main(["--db", path, "--today", "2026-10-13"] + args)
    finally:
        R.HttpClient = orig
    return rc, sqlite3.connect(path), client


class MainRun(unittest.TestCase):
    def test_journal_and_lodzkie(self):
        pages = [(R.journal_url(R.JOURNALS["mz"], 2026, 10), '{"Positions": []}'),
                 (R.journal_url(R.JOURNALS["mz"], 2026, 9), fixture("journal_mz_2026_09.json")),
                 (R.LD_LIST, fixture("ld.html"))]
        with tempfile.TemporaryDirectory() as tmp:
            rc, conn, client = run_main(pages, ["--region", "mz", "ld", "--source", "journal"], tmp)
            self.assertEqual(rc, 3)   # the Łódzkie journal has no fixture: a gap
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM plr_acts WHERE source='journal'").fetchone()[0], 2)
            reads = dict(conn.execute("SELECT source, status FROM plr_reads").fetchall())
            self.assertEqual(reads["journal:mz"], "ok")
            self.assertTrue(reads["journal:ld"].startswith("failed"))
            self.assertTrue(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed=?", (R.FEED,)).fetchone()[0])

    def test_registers(self):
        pages = [(R.LD_LIST, fixture("ld.html")),
                 (R.PK_INDEX, fixture("pk_index.html")),
                 ("https://bip.podkarpackie.pl/sejmik/uchwaly-sejmiku/*", fixture("pk_session.html")),
                 (R.CMS["mz"] + "?p=2026", fixture("cms_mz_2026.html")),
                 (R.CMS["mz"] + "?p=2026%5E*", fixture("cms_mz_month.html"))]
        with tempfile.TemporaryDirectory() as tmp:
            rc, conn, client = run_main(pages, ["--region", "ld", "pk", "mz", "--source", "bip"], tmp)
            self.assertEqual(rc, 0)
            got = dict(conn.execute("SELECT region, COUNT(*) FROM plr_acts GROUP BY region").fetchall())
            self.assertEqual(got["ld"], 4)
            self.assertEqual(got["mz"], 3)    # the same three resolutions on every month page
            self.assertTrue(got["pk"] >= 3)
            self.assertEqual(conn.execute("SELECT MIN(seed) FROM plr_acts").fetchone()[0], 1)

    def test_kp_off_by_default(self):
        ids = [s for s, _, _ in R.sources(list(plr.REGIONS), "journal")]
        self.assertNotIn("journal:kp", ids)
        self.assertEqual(len(ids), 15)
        self.assertIn("journal:kp", [s for s, _, _ in R.sources(["kp"], "journal", asked=True)])

    def test_robots_refusal_is_a_gap(self):
        from tests.robots_fakes import RobotsServing
        pages = [(R.LD_LIST, fixture("ld.html"))]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pm.db")
            serving = RobotsServing(FakeClient(pages), {"bip.lodzkie.pl": "User-agent: *\nDisallow: /\n"})
            orig = R.HttpClient
            R.HttpClient = lambda **kw: serving
            try:
                rc = R.main(["--db", path, "--today", "2026-10-13", "--region", "ld", "--source", "bip"])
            finally:
                R.HttpClient = orig
            conn = sqlite3.connect(path)
            self.assertEqual(rc, 3)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM plr_acts").fetchone()[0], 0)
            self.assertIn("robots.txt", conn.execute("SELECT detail FROM gaps").fetchone()[0])


class Edition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = scratch_db(self.tmp.name)
        tax = filt.load_taxonomy(TAX, country="pl")
        wl = R.empty_watchlist()
        R.store_all(self.conn, [
            act("ld/XXXII/401/2026", "w sprawie przyjęcia programu leczenia niepłodności metodą in vitro"),
            act("ld/XXXII/402/2026", "w sprawie zmian budżetu Województwa Łódzkiego"),
            act("ld/XX/250/2025", "w sprawie edukacji seksualnej", adopted="2025-03-01"),
            act("mz/dz/2026/9999", "Uchwała nr 200/26 Sejmiku Województwa Mazowieckiego w sprawie in vitro",
                region="mz", source="journal", adopted="2026-10-01", published="2026-10-09", number="200/26"),
            act("ld/dz/2026/5000", "Uchwała nr XXXII/401/2026 w sprawie programu in vitro", source="journal",
                adopted="2026-10-07", published="2026-10-10", number="XXXII/401/2026"),
        ], tax, wl, "2026-10-13", seed=True)
        R.mark_read(self.conn, "journal:mz", "2026-10-13", 1, "ok")
        R.mark_read(self.conn, "bip:ld", "2026-10-13", 3, "ok")
        R.mark_read(self.conn, "journal:op", "2026-10-13", 0, "failed: timed out")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_items_in_window_deduplicated(self):
        got = pl_ed.regional_items(self.conn, "2026-10-04", "2026-10-11", {})
        keys = [it["key"] for it in got]
        self.assertEqual(keys, ["ld/XXXII/401/2026", "mz/dz/2026/9999"])  # ld journal copy dropped
        self.assertEqual(got[0]["takeaway"], "Resolution XXXII/401/2026 of the Sejmik Województwa "
                         "Łódzkiego; adopted on 7 October 2026")
        self.assertIn("published in the Dziennik Urzędowy Województwa Mazowieckiego", got[1]["takeaway"])

    def test_section_and_coverage(self):
        lines = pl_ed.regional_section(self.conn, pl_ed.COUNTRY, "2026-10-04", "2026-10-11", {})
        text = "\n".join(lines)
        self.assertTrue(text.startswith("## Regional assemblies"))
        self.assertIn("### Adopted by the sejmiki", text)
        self.assertIn("### In the voivodeship journals", text)
        self.assertIn("1 of 16 read; failed: Opolskie", text)
        self.assertIn("Łódzkie (read 13 Oct)", text)
        self.assertNotIn("budżetu", text)

    def test_post_render_before_watchlist(self):
        text = ("# Poland\n\n_covering 5 October 2026 to 11 October 2026_\n\nbody\n\n## Watchlist\n\nx\n")
        out = pl_ed.post_render(self.conn, pl_ed.COUNTRY, "2026-10-13", text, {})
        self.assertLess(out.index("## Regional assemblies"), out.index("## Watchlist"))
        self.assertIn("in vitro", out)

    def test_no_section_before_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = scratch_db(tmp)
            self.assertEqual(pl_ed.post_render(conn, pl_ed.COUNTRY, "2026-10-13", "x\n", {}), "x\n")


if __name__ == "__main__":
    unittest.main()
