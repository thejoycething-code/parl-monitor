"""Member portraits and party colour chips (src/portraits.py,
tools/fetch_portraits.py, the vote page wiring). Fixtures only, no network:
a fake client serves the images and robots.txt."""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_votes as cv  # noqa: E402
from src import portraits as pt  # noqa: E402
from src.http import FetchError  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64          # magic bytes are all is_image reads
HTML = b"<!doctype html><title>Not found</title>"


class FakeClient:
    user_agent = "CitizenGO-parl-monitor/1.0 (test)"

    def __init__(self, files, robots=None):
        self.files, self.robots, self.calls = files, robots or {}, []

    def get_text(self, url, feed, slug, archive=True, **kw):
        self.calls.append(url)
        host = url.rsplit("/robots.txt", 1)[0]
        if host in self.robots:
            body = self.robots[host]
            if isinstance(body, int):
                raise FetchError(url, feed, slug, 1, types.SimpleNamespace(code=body))
            return body
        raise FetchError(url, feed, slug, 1, types.SimpleNamespace(code=404))

    def get_bytes(self, url, feed, slug, archive=True, **kw):
        self.calls.append(url)
        if url not in self.files:
            raise FetchError(url, feed, slug, 1, types.SimpleNamespace(code=404))
        return self.files[url]


def fake_shrink(raw, size=pt.THUMB):
    return b"\xff\xd8\xffTHUMB" + raw[:8]


def member(name, chamber="Sejm"):
    return types.SimpleNamespace(name=name, chamber=chamber)


class PortraitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cache = os.path.join(self.tmp, "cache")
        self.site = os.path.join(self.tmp, "site")
        self.saved = dict(pt.SOURCES)
        pt.SOURCES["zz"] = pt.Source(
            "zz", "Test Parliament", "attribution", "CC BY 4.0", "https://example.test/terms",
            "Test Parliament, CC BY 4.0",
            photo=lambda key, m: ("https://img.example.test/{0}.jpg".format(key),
                                  "https://example.test/m/{0}".format(key)))
        pt.SOURCES["yy"] = pt.Source(
            "yy", "Closed Parliament", "not_allowed", "all rights reserved",
            "https://closed.test/legal", "n/a",
            photo=lambda key, m: ("https://closed.test/{0}.jpg".format(key), None))

    def tearDown(self):
        pt.SOURCES.clear()
        pt.SOURCES.update(self.saved)
        shutil.rmtree(self.tmp)

    def fetch(self, client, members, today="2026-10-12", **kw):
        return pt.fetch_country(client, "zz", members, today, cache_dir=self.cache,
                                shrink_fn=fake_shrink, log=lambda *a: None, **kw)

    # --- the gate --------------------------------------------------------------
    def test_only_ok_classes_are_usable(self):
        self.assertTrue(pt.SOURCES["zz"].usable)
        self.assertFalse(pt.SOURCES["yy"].usable)
        with self.assertRaises(ValueError):
            pt.fetch_country(FakeClient({}), "yy", [("1", member("A"))], "2026-10-12",
                             cache_dir=self.cache)
        self.assertNotIn("yy", pt.usable_countries())

    def test_every_real_source_has_a_class_terms_and_credit(self):
        for cc, s in self.saved.items():
            self.assertIn(s.licence_class, pt.CLASSES, cc)
            self.assertTrue(s.terms_url.startswith("http"), cc)
            if s.usable:
                self.assertTrue(s.credit.strip(), cc)

    def test_licence_doc_names_every_usable_source(self):
        with open(os.path.join(ROOT, "docs", "portraits-logos-licences.md"), encoding="utf-8") as fh:
            doc = fh.read()
        for cc, s in self.saved.items():
            if s.usable:
                self.assertIn(s.terms_url, doc, cc)

    # --- fetching --------------------------------------------------------------
    def test_fetch_writes_thumbnail_and_manifest(self):
        client = FakeClient({"https://img.example.test/1.jpg": JPEG,
                             "https://img.example.test/2.jpg": HTML})
        got = self.fetch(client, [("1", member("Anna Nowak")), ("2", member("Beata Lis")),
                                  ("3", member("Cezary Wolny"))])
        self.assertEqual((got["fetched"], got["missing"]), (1, 2))
        with open(pt.manifest_path("zz", self.cache), encoding="utf-8") as fh:
            man = json.load(fh)
        self.assertEqual(man["licence_class"], "attribution")
        self.assertEqual(man["credit"], "Test Parliament, CC BY 4.0")
        row = man["members"]["1"]
        self.assertEqual(row["image_url"], "https://img.example.test/1.jpg")
        self.assertEqual(row["page_url"], "https://example.test/m/1")
        with open(os.path.join(self.cache, "zz", row["file"]), "rb") as fh:
            self.assertTrue(fh.read().startswith(b"\xff\xd8\xffTHUMB"))
        self.assertEqual(man["missing"]["2"]["why"], "not an image")
        self.assertIn("fetch failed", man["missing"]["3"]["why"])

    def test_no_thumbnail_tool_means_no_file_never_the_original(self):
        client = FakeClient({"https://img.example.test/1.jpg": JPEG})
        got = pt.fetch_country(client, "zz", [("1", member("A"))], "2026-10-12",
                               cache_dir=self.cache, shrink_fn=lambda raw: None,
                               log=lambda *a: None)
        self.assertEqual(got["fetched"], 0)
        self.assertEqual(os.listdir(os.path.join(self.cache, "zz")), [])

    def test_robots_disallow_is_obeyed(self):
        client = FakeClient({"https://img.example.test/1.jpg": JPEG},
                            robots={"https://img.example.test": "User-agent: *\nDisallow: /\n"})
        got = self.fetch(client, [("1", member("A"))])
        self.assertEqual(got["refused"], 1)
        self.assertNotIn("https://img.example.test/1.jpg", client.calls)

    def test_unreadable_robots_means_no_fetch(self):
        client = FakeClient({"https://img.example.test/1.jpg": JPEG},
                            robots={"https://img.example.test": 403})
        got = self.fetch(client, [("1", member("A"))])
        self.assertEqual(got["refused"], 1)

    def test_unreachable_robots_means_no_fetch(self):
        # The per-run guard (src/prov_fetch.read_robots): a 5xx is Disallow: /.
        client = FakeClient({"https://img.example.test/1.jpg": JPEG},
                            robots={"https://img.example.test": 500})
        robots = pt.Robots(client, robots_sleep=lambda s: None, robots_cache_dir=None)
        got = self.fetch(client, [("1", member("A"))], robots=robots)
        self.assertEqual(got["refused"], 1)
        self.assertNotIn("https://img.example.test/1.jpg", client.calls)

    def test_documented_api_is_fetched_as_the_collectors_fetch_it(self):
        url = "https://api.sejm.gov.pl/sejm/term10/MP/1/photo"
        pt.SOURCES["zz"].photo = lambda key, m: (url, None)
        client = FakeClient({url: JPEG}, robots={"https://api.sejm.gov.pl": 500})
        got = self.fetch(client, [("1", member("A"))])
        self.assertEqual(got["fetched"], 1)
        self.assertNotIn("https://api.sejm.gov.pl/robots.txt", client.calls)
        man = pt.load_manifest("zz", self.cache)
        self.assertEqual(man["members"]["1"]["page_url"], url)   # no page: the image is the source

    def test_member_page_is_checked_against_robots(self):
        pt.SOURCES["zz"].photo = None
        pt.SOURCES["zz"].photo_from_page = lambda c, key, m: (
            c.get_text("https://pages.example.test/m/" + key, "portraits", "p"), None)
        client = FakeClient({}, robots={"https://pages.example.test":
                                        "User-agent: *\nDisallow: /m/\n"})
        got = self.fetch(client, [("1", member("A"))])
        self.assertEqual(got["refused"], 1)
        self.assertNotIn("https://pages.example.test/m/1", client.calls)
        man = pt.load_manifest("zz", self.cache)
        self.assertEqual(man["missing"]["1"]["why"], "robots.txt disallows")

    def test_missing_robots_allows(self):
        client = FakeClient({"https://img.example.test/1.jpg": JPEG})
        self.assertEqual(self.fetch(client, [("1", member("A"))])["fetched"], 1)

    def test_budget_and_due_dates(self):
        files = {"https://img.example.test/{0}.jpg".format(i): JPEG for i in range(5)}
        members = [(str(i), member("M{0}".format(i))) for i in range(5)]
        got = self.fetch(FakeClient(files), members, max_fetch=2)
        self.assertEqual((got["fetched"], got["left"]), (2, 3))
        client = FakeClient(files)
        got = self.fetch(client, members, today="2026-10-19", max_fetch=10)
        self.assertEqual((got["fetched"], got["not_due"]), (3, 2))
        got = self.fetch(FakeClient(files), members, today="2027-05-01", max_fetch=10)
        self.assertEqual(got["fetched"], 5)       # refreshed after REFRESH_DAYS

    def test_missing_rechecked_after_a_month(self):
        self.fetch(FakeClient({}), [("1", member("A"))])
        self.assertEqual(self.fetch(FakeClient({}), [("1", member("A"))],
                                    today="2026-10-20")["not_due"], 1)
        self.assertEqual(self.fetch(FakeClient({}), [("1", member("A"))],
                                    today="2026-11-20")["missing"], 1)

    def test_is_image(self):
        self.assertTrue(pt.is_image(JPEG))
        self.assertTrue(pt.is_image(b"\x89PNG\r\n\x1a\nxxxx"))
        self.assertFalse(pt.is_image(HTML))
        self.assertFalse(pt.is_image(b""))

    # --- the page --------------------------------------------------------------
    def page_data(self):
        return {"cc": "zz", "members": [["Anna Nowak", "KO", "Sejm", "", True, False, None],
                                        ["Beata Lis", "PiS", "Sejm", "", True, False, None]],
                "groups": ["KO", "PiS"], "_keys": ["1", "2"]}

    def test_attach_copies_only_page_members_and_prunes(self):
        self.fetch(FakeClient({"https://img.example.test/1.jpg": JPEG,
                               "https://img.example.test/9.jpg": JPEG}),
                   [("1", member("A")), ("9", member("Z"))])
        stale = os.path.join(self.site, "portraits", "zz", "stale.jpg")
        os.makedirs(os.path.dirname(stale))
        with open(stale, "wb") as fh:
            fh.write(b"x")
        data = pt.attach(self.page_data(), self.site, cache_dir=self.cache,
                         colours={"zz": {"KO": "#F68F2D", "Other": "#000000"}})
        self.assertEqual(list(data["portraits"]), [0])
        src, page = data["portraits"][0]
        self.assertEqual(src, "portraits/zz/" + pt.file_for("1"))
        self.assertEqual(page, "https://example.test/m/1")
        self.assertEqual(data["portrait_credit"], "Test Parliament, CC BY 4.0")
        self.assertEqual(sorted(os.listdir(os.path.join(self.site, "portraits", "zz"))),
                         [pt.file_for("1")])
        self.assertEqual(data["colours"], {"KO": "#F68F2D"})

    def test_attach_keeps_published_thumbnail_without_cache(self):
        """GitHub's backup run has no cache: a thumbnail already on the site stays."""
        self.fetch(FakeClient({"https://img.example.test/1.jpg": JPEG}), [("1", member("A"))])
        pt.attach(self.page_data(), self.site, cache_dir=self.cache, colours={})
        shutil.rmtree(os.path.join(self.cache, "zz"))
        data = pt.attach(self.page_data(), self.site, cache_dir=self.cache, colours={})
        self.assertIn(0, data["portraits"])

    def test_attach_without_manifest_or_usable_source(self):
        data = pt.attach(self.page_data(), self.site, cache_dir=self.cache, colours={})
        self.assertNotIn("portraits", data)
        d = dict(self.page_data(), cc="yy")
        self.assertNotIn("portraits", pt.attach(d, self.site, cache_dir=self.cache, colours={}))
        self.assertFalse(os.path.exists(os.path.join(self.site, "portraits", "yy")))

    def test_render_page_drops_keys_and_shows_credit(self):
        self.fetch(FakeClient({"https://img.example.test/1.jpg": JPEG}), [("1", member("A"))])
        data = pt.attach(self.page_data(), self.site, cache_dir=self.cache,
                         colours={"zz": {"KO": "#F68F2D"}})
        blob = {"name": "Testland", **data}
        page = cv.render_page(blob)
        self.assertNotIn('"_keys"', page)
        self.assertIn('"portrait_credit":"Test Parliament, CC BY 4.0"', page)
        self.assertIn('"colours":{"KO":"#F68F2D"}', page)
        self.assertIn("pchip", page)
        self.assertNotIn("logos/", page)

    def test_colours_config_is_valid(self):
        colours = pt.load_colours()
        self.assertTrue(colours)
        for cc, parties in colours.items():
            for party, colour in parties.items():
                self.assertRegex(colour, r"^#[0-9A-Fa-f]{6}$", (cc, party))


class SourceUrlTest(unittest.TestCase):
    """The real sources' URL builders, from store keys and a fixture page; no network."""

    def test_brazil(self):
        img, page = pt.SOURCES["br"].photo("camara-204379", member("X"))
        self.assertEqual(img, "https://www.camara.leg.br/internet/deputado/bandep/204379.jpg")
        img, page = pt.SOURCES["br"].photo("senado-1173", member("X"))
        self.assertEqual(img, "https://www.senado.leg.br/senadores/img/fotos-oficiais/senador1173.jpg")
        self.assertEqual(pt.SOURCES["br"].photo("name:someone", member("X")), (None, None))

    def test_croatia_reads_the_member_page(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "portraits", "hr-member.html"),
                  encoding="utf-8") as fh:
            page = fh.read()

        class Pages:
            def get_text(self, url, feed, slug, archive=True, **kw):
                self.url = url
                return page
        c = Pages()
        img, src = pt.SOURCES["hr"].photo_from_page(c, "ackar-kresimir-11-saziv", member("X"))
        self.assertEqual(c.url, "https://www.sabor.hr/hr/zastupnici/ackar-kresimir-11-saziv")
        self.assertEqual(img, "https://www.sabor.hr/sites/default/files/uploads/sabor/2024-07-19/"
                              "182044/A%C4%8Dkar%2C%20Kre%C5%A1imir.jpeg")
        self.assertIsNone(pt.hr_photo_in("<html>no photo</html>"))
        self.assertEqual(pt.SOURCES["hr"].photo_from_page(c, "name:x y", member("X")), (None, None))

    def test_not_allowed_never_fetch(self):
        for cc in ("fr", "sk", "do"):
            self.assertEqual(pt.SOURCES[cc].licence_class, "not_allowed", cc)
            self.assertFalse(pt.SOURCES[cc].usable, cc)
        self.assertNotIn("not_allowed", pt.USABLE)
        self.assertNotIn("unclear", pt.USABLE)

    def test_enabled_on_chris_instruction_12_october(self):
        # "Yes for all four" (internal) and "use the photos anyway where possible".
        for cc in ("it", "nl", "at", "ch"):
            self.assertEqual(pt.SOURCES[cc].licence_class, "internal", cc)
        for cc in ("pl", "pt", "be", "hu", "mx", "cl", "pe", "ec", "sv", "gt", "co", "uy"):
            self.assertEqual(pt.SOURCES[cc].licence_class, "unclear_used", cc)
        self.assertFalse([cc for cc, s in pt.SOURCES.items() if s.licence_class == "unclear"])
        self.assertEqual(pt.usable_countries(), ["at", "br", "ch", "hr", "nl", "pl", "pt"])

    def test_enabled_but_not_mappable_yet_fetch_nothing(self):
        for cc in ("it", "es", "be", "hu", "cl", "ec", "sv", "ar"):
            s = pt.SOURCES[cc]
            self.assertIn(s.licence_class, pt.USABLE, cc)
            self.assertFalse(s.usable, cc)

    def test_unclear_used_credit_names_the_institution(self):
        for cc, s in pt.SOURCES.items():
            if s.licence_class == "unclear_used":
                self.assertTrue(s.credit.endswith(" (official portrait)"), cc)
                self.assertGreater(len(s.credit), len(" (official portrait)"), cc)

    def test_poland(self):
        img, page = pt.SOURCES["pl"].photo("10/1", member("X"))
        self.assertEqual(img, "https://api.sejm.gov.pl/sejm/term10/MP/1/photo")
        self.assertEqual(page, "https://www.sejm.gov.pl/Sejm10.nsf/posel.xsp?id=001&type=A")
        self.assertEqual(pt.SOURCES["pl"].photo("10/460", member("X"))[0],
                         "https://api.sejm.gov.pl/sejm/term10/MP/460/photo")
        for bad in ("name:anna-nowak", "460", "10/x", "10/1/2"):
            self.assertEqual(pt.SOURCES["pl"].photo(bad, member("X")), (None, None), bad)

    def test_portugal(self):
        img, page = pt.SOURCES["pt"].photo("7040", member("X"))
        self.assertEqual(img, "https://app.parlamento.pt/webutils/getimage.aspx?id=7040&type=deputado")
        self.assertEqual(page, "https://www.parlamento.pt/DeputadoGP/Paginas/Biografia.aspx?BID=7040")
        self.assertEqual(pt.SOURCES["pt"].photo("name:x", member("X")), (None, None))

    def test_switzerland(self):
        img, page = pt.SOURCES["ch"].photo("1109", member("X"))
        self.assertEqual(img, "https://www.parlament.ch/SiteCollectionImages/profil/portrait-260/1109.jpg")
        self.assertEqual(pt.SOURCES["ch"].photo("../1109", member("X")), (None, None))

    def test_netherlands(self):
        key = "b29c0e00-7ac2-4c28-ab4f-8fceb156337b"
        img, page = pt.SOURCES["nl"].photo(key, member("X"))
        self.assertEqual(img, "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Persoon({0})"
                              "/resource".format(key))
        self.assertTrue(img.startswith(page))
        self.assertEqual(pt.SOURCES["nl"].photo("name:corrie", member("X")), (None, None))

    def test_austria_reads_the_member_page(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "portraits", "at-person.html"),
                  encoding="utf-8") as fh:
            page = fh.read()

        class Pages:
            def get_text(self, url, feed, slug, archive=True, **kw):
                self.url = url
                return page
        c = Pages()
        img, src = pt.SOURCES["at"].photo_from_page(c, "33457", member("X"))
        self.assertEqual(c.url, "https://www.parlament.gv.at/person/33457")
        self.assertEqual(src, "https://www.parlament.gv.at/person/33457")
        self.assertEqual(img, "https://www.parlament.gv.at/dokument/bild/201646/20164630_384.jpg")
        self.assertIsNone(pt.at_photo_in("<html>no photo</html>"))
        self.assertEqual(pt.SOURCES["at"].photo_from_page(c, "name:x", member("X")), (None, None))

    def test_licence_doc_records_the_decisions(self):
        with open(os.path.join(ROOT, "docs", "portraits-logos-licences.md"), encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn("Used on Chris's instruction, licence unclear (12 Oct 2026)", doc)
        self.assertIn("Yes for all four", doc)
        self.assertIn("Not mappable yet", doc)
        self.assertIn("Expected complete", doc)


if __name__ == "__main__":
    unittest.main()
