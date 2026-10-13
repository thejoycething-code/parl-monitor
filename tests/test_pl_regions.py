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

Second build (13 October 2026, nine more registers), trimmed the same way:
Wielkopolskie's index of sittings and one sitting's table; Lubelskie's two
document lists (the page's own JSON; staff names blanked, and the 27
September 2021 amending position appended from the first read's reply,
because the weekly read's twenty rows stop in 2024); two Kujawsko-Pomorskie
agendas and one agenda's items; Warmińsko-Mazurskie's filtered act list and
stanowiska category; Świętokrzyskie's register page and the text of its
register PDF (pypdf's output, first and last sittings); Lubuskie's filtered
act list plus one board resolution from the unfiltered list; the Madkom JSON
of Małopolskie, Pomorskie and Dolnośląskie (a menu's year children and two
articles of a year list).
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

    def get_bytes(self, url, feed, slug, **kw):
        return self._get(url).encode("utf-8")

    def post_form(self, url, fields, feed, slug, **kw):
        self.posted = dict(fields)
        return self._get(url + "#post")

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


class NewRegisters(unittest.TestCase):
    """The nine registers added on 13 October 2026."""

    def test_wielkopolskie(self):
        sessions = R.parse_wp_index(fixture("wp_index.html"))
        self.assertEqual(sessions[0][1:], ("XXVIII sesja", "2026-09-28"))
        acts = R.parse_wp_session(fixture("wp_session.html"), sessions[0][0], *sessions[0][1:])
        self.assertEqual([a["key"] for a in acts], ["wp/XXVIII/681/26", "wp/XXVIII/682/26"])
        self.assertTrue(acts[0]["title"].startswith("zmieniająca uchwałę Nr XX/473/25"))
        self.assertEqual(acts[0]["url"], "https://bip.umww.pl/artykuly/2834351/pliki/"
                         "20260929113036_uchwaanrxxviii68126.pdf")
        self.assertEqual(acts[0]["adopted"], "2026-09-28")

    def test_lubelskie(self):
        acts = R.parse_lubelskie(json.loads(fixture("lu_56.json")), 56)
        self.assertEqual(acts[0]["key"], "lu/XXV/427/2026")
        self.assertEqual(acts[0]["adopted"], "2026-09-23")
        self.assertIn("p1=szczegoly&p2=", acts[0]["url"])
        docs = by_key(R.parse_lubelskie(json.loads(fixture("lu_57.json")), 57))
        self.assertEqual(docs["lu/doc/1677532"]["kind"], "stanowisko")
        self.assertIsNone(docs["lu/doc/1677532"]["number"])
        self.assertIn("iDisplayLength=60", R.lu_url(56, 60))

    def test_kujawsko_pomorskie_drafts(self):
        sessions = R.parse_kp_index(fixture("kp_index.html"))
        self.assertEqual([s[1] for s in sessions], ["XXX sesja", "XXIX sesja"])
        acts = R.parse_kp_agenda(fixture("kp_agenda.html"), *sessions[0])
        self.assertEqual([a["key"] for a in acts], ["kp/druk/64/26", "kp/druk/65/26", "kp/druk/63/26"])
        self.assertEqual(acts[0]["kind"], "projekt uchwały")
        self.assertEqual(acts[0]["adopted"], "2026-09-28")
        self.assertTrue(acts[2]["title"].startswith("w sprawie udzielenia pomocy finansowej"))

    def test_warminsko_mazurskie(self):
        acts = R.parse_wn(fixture("wn_list.html"))
        self.assertEqual(acts[0]["key"], "wn/XXVII/465/26")
        self.assertEqual(acts[0]["adopted"], "2026-09-29")
        self.assertTrue(acts[0]["title"].startswith("w sprawie"))
        st = R.parse_wn(fixture("wn_stanowiska.html"), R.WN_STANOWISKA)
        self.assertEqual(st[0]["key"], "wn/doc/4232")
        self.assertEqual(st[0]["kind"], "stanowisko")

    def test_swietokrzyskie(self):
        self.assertTrue(R.parse_sk_pdf_link(fixture("sk_page.html")).startswith(
            "https://bip.sejmik.kielce.pl/download/"))
        acts = by_key(R.parse_sk_register(fixture("sk_register.txt")))
        self.assertEqual(acts["sk/I/1/24"]["adopted"], "2024-05-06")
        a = acts["sk/XXX/362/26"]
        self.assertEqual(a["adopted"], "2026-08-17")
        self.assertEqual(a["session"], "XXX sesja")
        self.assertNotIn("Wojewoda", a["title"])
        self.assertTrue(a["title"].startswith("w sprawie przyjęcia apelu"))
        self.assertNotIn("RIO", acts["sk/XXX/359/26"]["title"])

    def test_pdf_without_pypdf_is_a_gap(self):
        import builtins
        real = builtins.__import__

        def no_pypdf(name, *a, **kw):
            if name == "pypdf":
                raise ImportError(name)
            return real(name, *a, **kw)
        builtins.__import__ = no_pypdf
        try:
            with self.assertRaises(ValueError):
                R.pdf_text(b"%PDF-1.6")
        finally:
            builtins.__import__ = real

    def test_lubuskie(self):
        acts = R.parse_lubuskie(fixture("lb_list.html"))
        self.assertEqual([a["key"] for a in acts], ["lb/XXIII/365/26", "lb/XXIII/364/26"])  # board's dropped
        self.assertEqual(acts[0]["adopted"], "2026-09-21")
        self.assertTrue(acts[1]["title"].startswith("w sprawie rozpatrzenia petycji"))
        form = '<select name="filtr[id_grupa]"><option value="61" >Uchwa&#x142;y Sejmiku 2027</option>'
        self.assertEqual(R.lb_year_group(form, 2027), "61")
        self.assertEqual(R.lb_year_group("<html></html>", 2026), "59")
        self.assertIsNone(R.lb_year_group("<html></html>", 2031))

    def test_madkom_three_layouts(self):
        ma = R.parse_madkom(json.loads(fixture("ma_2026.json")), "ma", "uchwała", R.MADKOM["ma"][0])
        self.assertEqual(ma[0]["key"], "ma/XXXIV/513/26")
        self.assertEqual(ma[0]["adopted"], "2026-09-28")
        self.assertTrue(ma[0]["title"].startswith("w sprawie zmian w składach"))
        self.assertTrue(ma[0]["url"].startswith("https://bip.malopolska.pl/umwm,a,2946979,"))
        dk = by_key(R.parse_madkom(json.loads(fixture("ma_deklaracje_2021.json")), "ma", "deklaracja",
                                   R.MADKOM["ma"][0]))
        self.assertEqual(dk["ma/deklaracja/5/21"]["adopted"], "2021-09-27")
        self.assertEqual(dk["ma/deklaracja/5/21"]["kind"], "deklaracja")
        pm = R.parse_madkom(json.loads(fixture("pm_2026.json")), "pm", "uchwała", R.MADKOM["pm"][0])
        self.assertEqual(pm[0]["key"], "pm/366/XXX/26")          # Pomorskie's own number order
        ds = R.parse_madkom(json.loads(fixture("ds_2026.json")), "ds", "uchwała", R.MADKOM["ds"][0])
        self.assertEqual(ds[0]["key"], "ds/XXX/898/26")
        self.assertEqual(ds[0]["published"], "2026-10-07")       # only a publication date: adopted falls back
        self.assertEqual(ds[0]["adopted"], "2026-10-07")

    def test_madkom_years(self):
        self.assertEqual(R.madkom_years(json.loads(fixture("pm_menu_42.json")), "42")[0], (2026, "762"))
        ds = R.madkom_years(json.loads(fixture("ds_menu_1914.json")), "1914")
        self.assertEqual(ds[0], (2026, "2842"))                  # 'Rejestr Uchwał' is not a year
        self.assertNotIn("1983", [m for _, m in ds])


class Citations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "watchlist-pl.yaml")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write('regional:\n'
                     '  "sk/X/125/19": {areas: [5], why: "2019 position"}\n'
                     '  "ma/deklaracja/1/19": {areas: [5], why: "Deklaracja Nr 1/19"}\n'
                     '  "lu/doc/1382854": {areas: [5], why: "2019 position", '
                     'cites: ["stanowisko z dnia 25 kwietnia 2019"]}\n')
        self.tax = filt.load_taxonomy(TAX, country="pl")

    def tearDown(self):
        self.tmp.cleanup()

    def res(self, key, title):
        return R.classify(self.tax, R.empty_watchlist(), act(key, title, region=key.split("/")[0]), self.path)

    def test_repeal_citing_the_number(self):
        r = self.res("sk/XL/600/22", "w sprawie uchylenia uchwały Nr X/125/19 Sejmiku Województwa")
        self.assertEqual(r.issue_areas, [5])
        self.assertIn("cites:sk/X/125/19", r.watchlist_hits)
        self.assertEqual(r.tier, 2)

    def test_kind_numbered_apart_needs_the_kind(self):
        self.assertIn("cites:ma/deklaracja/1/19", self.res(
            "ma/deklaracja/5/21", "Deklaracja Nr 5/21 w sprawie uchylenia Deklaracji Nr 1/19").watchlist_hits)
        self.assertEqual(self.res("ma/apel/2/19", "Apel Nr 1/19 w sprawie kolei").issue_areas, [])

    def test_phrase_for_an_unnumbered_position(self):
        r = self.res("lu/doc/1677532", "Stanowisko Sejmiku Województwa Lubelskiego zmieniające stanowisko "
                                       "z dnia 25 kwietnia 2019 r.")
        self.assertIn("cites:lu/doc/1382854", r.watchlist_hits)

    def test_other_voivodeship_and_longer_numbers_do_not_match(self):
        self.assertEqual(self.res("ld/XL/600/22", "w sprawie uchylenia uchwały Nr X/125/19").issue_areas, [])
        self.assertEqual(self.res("sk/XL/601/22", "zmieniająca uchwałę Nr XX/125/19").issue_areas, [])
        self.assertEqual(self.res("sk/XL/602/22", "zmieniająca uchwałę Nr X/125/190").issue_areas, [])


class NewTerms(unittest.TestCase):
    """taxonomy-pl v0.3 (Chris, 13 October 2026: "Add both")."""

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAX, country="pl")

    def res(self, title):
        return filt.filter_item(self.tax, R.empty_watchlist(), title, title=title)

    def test_family_charter(self):
        for t in ("w sprawie przyjęcia Samorządowej Karty Praw Rodzin",
                  "w sprawie petycji dotyczącej przyjęcia „Karty Praw Rodziny”"):
            r = self.res(t)
            self.assertIn(9, r.issue_areas)
            self.assertIn("Kart* Praw Rodzin*", r.matched_terms)
            self.assertEqual(r.tier, 1)
        self.assertNotIn("Kart* Praw Rodzin*", self.res("Karta Dużej Rodziny").matched_terms or [])

    def test_ideology_free_zones(self):
        r = self.res("w sprawie uchylenia deklaracji: strefy wolne od ideologii")
        self.assertIn(5, r.issue_areas)
        self.assertIn("stref* wolne od ideologii", r.matched_terms)


class NewRegistersRun(unittest.TestCase):
    def test_lubuskie_posts_its_filter_and_madkom_reads_the_year(self):
        site = R.MADKOM["pm"][0]
        pages = [(R.LB_LIST, "<html></html>"), (R.LB_LIST + "#post", fixture("lb_list.html")),
                 (R.madkom_menu_url(site, "42"), fixture("pm_menu_42.json")),
                 (site + "api/menu/762/articles*", fixture("pm_2026.json")),
                 (site + "api/menu/693/articles*", '{"columns": [], "articles": []}')]
        with tempfile.TemporaryDirectory() as tmp:
            rc, conn, client = run_main(pages, ["--region", "lb", "pm", "--source", "bip"], tmp)
            self.assertEqual(rc, 0)
            got = dict(conn.execute("SELECT region, COUNT(*) FROM plr_acts GROUP BY region").fetchall())
            self.assertEqual(got, {"lb": 2, "pm": 2})
            self.assertEqual(client.posted["filtr[id_grupa]"], R.LB_YEAR_GROUP[2026])
            self.assertTrue(any("/api/menu/762/articles?limit=200" in u for u in client.urls))  # first read

    def test_every_register_has_a_reader(self):
        self.assertEqual(set(R.REGISTERS), set(R.REGISTER_FETCH))
        self.assertEqual(set(R.REGISTERS), set(pl_ed.REGISTERS))
        self.assertEqual(len(R.REGISTERS) + len(pl_ed.NOT_READ), 16)


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

    def test_draft_on_an_agenda_is_not_called_adopted(self):
        tax = filt.load_taxonomy(TAX, country="pl")
        a = act("kp/druk/70/26", "w sprawie przyjęcia programu in vitro", region="kp", number="druk nr 70/26")
        a["kind"] = "projekt uchwały"
        R.store_all(self.conn, [a], tax, R.empty_watchlist(), "2026-10-13", seed=True)
        got = {it["key"]: it for it in pl_ed.regional_items(self.conn, "2026-10-04", "2026-10-11", {})}
        it = got["kp/druk/70/26"]
        self.assertEqual(it["layer"], "agenda")
        self.assertIn("Draft resolution (druk nr 70/26) on the agenda", it["takeaway"])
        self.assertNotIn("adopted", it["takeaway"])
        text = "\n".join(pl_ed.regional_section(self.conn, pl_ed.COUNTRY, "2026-10-04", "2026-10-11", {}))
        self.assertIn("### On a sejmik's agenda", text)
        self.assertIn("Not read: the registers of Zachodniopomorskie", text)

    def test_no_section_before_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = scratch_db(tmp)
            self.assertEqual(pl_ed.post_render(conn, pl_ed.COUNTRY, "2026-10-13", "x\n", {}), "x\n")


if __name__ == "__main__":
    unittest.main()
