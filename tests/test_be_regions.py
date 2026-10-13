"""Belgium's community and regional parliaments: tools/be_regions.py,
src/be_regions_store.py and the "Communities and regions" section of the
Belgian edition. No network: every fixture is a real response read on 13
October 2026, trimmed, in tests/fixtures/be_regions/ (the Walloon members'
contact fields replaced with placeholders, to prove they are never stored)."""

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
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import be_regions_store as ber, db, noise  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src.http import FetchError  # noqa: E402
from src import robots_guard as rg  # noqa: E402
from robots_fakes import guarded_api  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "be_regions")
TODAY = "2026-10-13"


def _load():
    spec = importlib.util.spec_from_file_location(
        "be_regions", os.path.join(ROOT, "tools", "be_regions.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


br = _load()


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def fj(name):
    return json.loads(fx(name))


def fresh_db():
    return db.init_db(db.connect(":memory:"))


def quiet(*_a, **_k):
    return None


class FakeClient:
    """Serves the fixtures by URL; records what was asked for."""

    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 0

    ROUTES = (
        ("aggregaattype~decreet", "vl-search-decreet.json"),
        ("aggregaattype~resolutie", "vl-search-resolutie.json"),
        ("aggregaattype=Motie", "vl-search-motie.json"),
        ("aggregaattype~Conceptnota", "vl-search-conceptnota.json"),
        ("aggregaattype=Verzoekschrift", "vl-search-verzoekschrift.json"),
        ("/e/opendata/pi/1960322", "vl-pi-552.json"),
        ("/e/opendata/vv/op-datum", "vl-members.json"),
        ("type=DECRET", "pw-decret.json"),
        ("type=RES", "pw-res.json"),
        ("type=MOTION", "pw-motion.json"),
        ("type=PARCHEMIN", "pw-parchemin.json"),
        ("composition_dep_od.php", "pw-members.json"),
        ("dos_leg_legis_24-29.json", "bru-dossiers.json"),
        ("pfwb.be/documents-parlementaires", "fwb-documents.html"),
        ("pfwb.be/agendas/seances-plenieres-2026-10-07", "fwb-plenary-2026-10-07.html"),
        ("pfwb.be/agenda", "fwb-agenda.html"),
    )

    def __init__(self, fail=(), override=None):
        self.fail = set(fail)
        self.override = dict(override or {})
        self.fetched = []

    def _serve(self, url):
        self.fetched.append(url)
        if any(f in url for f in self.fail):
            raise FetchError(url, "t", "x", 3, "timeout")
        for needle, body in self.override.items():
            if needle in url:
                return body
        for needle, name in self.ROUTES:
            if needle in url:
                return fx(name)
        raise AssertionError("unexpected URL " + url)

    def get_text(self, url, feed, slug, *a, **kw):
        return self._serve(url)

    def get_json(self, url, feed, slug, *a, **kw):
        return json.loads(self._serve(url))


def client(robots=None, **kw):
    inner = FakeClient(**kw)
    wrapped, serving = guarded_api(inner, robots or {}, br.FEED)
    return wrapped, inner, serving


def run_all(conn, cl, watch_path=None):
    gaps = 0
    for code in br.ORDER:
        gaps += br.run_parliament(conn, cl, code, TODAY, log=quiet, watch_path=watch_path)
    return gaps


class Parsers(unittest.TestCase):
    def test_flemish_search(self):
        docs = br.parse_vl_search(fj("vl-search-resolutie.json"))
        by = {d["key"]: d for d in docs}
        d = by["vl/2025-2026/897"]
        self.assertEqual(d["kind"], "resolution")
        self.assertEqual(d["doc_type"], "Voorstel van resolutie")
        self.assertEqual(d["date"], "2026-06-17")
        self.assertIn("abortustermijn", d["title"])
        self.assertTrue(d["authors"].startswith("Jeremie Vaneeckhout, Mieke Schauvliege"))
        self.assertTrue(d["pi"].isdigit())
        r = by["vl/2025-2026/552"]
        self.assertEqual(r["status"], "verworpen in plenaire vergadering")
        self.assertEqual(r["status_date"], "2025-11-05")   # the latest of every statusdatum_*

    def test_flemish_petitions_have_their_own_series(self):
        docs = br.parse_vl_search(fj("vl-search-verzoekschrift.json"))
        keys = {d["key"] for d in docs}
        self.assertIn("vl/2025-2026/vzs-149", keys)
        self.assertTrue(all("/vzs-" in k for k in keys))
        self.assertTrue(all(d["kind"] == "petition" and d["pi"] is None for d in docs))

    def test_flemish_votes_name_every_member_and_group(self):
        votes = br.parse_vl_votes(fj("vl-pi-552.json"), "vl/2025-2026/552")
        self.assertEqual(len(votes), 1)
        vote, positions = votes[0]
        self.assertEqual(vote["key"], "vl/1962158/1")
        self.assertEqual((vote["yes"], vote["no"], vote["abstain"], vote["adopted"]),
                         (27, 91, 0, 0))
        self.assertEqual(vote["date"], "2025-11-05")
        self.assertIn("plenaire-vergaderingen/1953492/verslag/1962158", vote["url"])
        self.assertEqual(len(positions), 118)
        self.assertEqual(sum(1 for p in positions if p[3] == "yes"), 27)
        groups = {p[2] for p in positions}
        self.assertIn("Vlaams Belang", groups)
        self.assertTrue(all(p[0].startswith("vl/") and p[1] for p in positions))

    def test_flemish_members(self):
        got = br.parse_vl_members(fj("vl-members.json"))
        self.assertEqual(len(got), 4)
        self.assertEqual(got[0]["name"], "Hannes Anaf")
        self.assertEqual(got[0]["group"], "Vooruit")
        self.assertEqual(got[0]["constituency"], "Kieskring Antwerpen")

    def test_walloon_documents_grouped_by_number(self):
        pubs = []
        for t in ("decret", "res", "motion", "parchemin"):
            pubs += fj("pw-{0}.json".format(t))["publications"]
        by = {d["key"]: d for d in br.parse_pw(pubs)}
        d = by["pw/2025-2026/657"]
        self.assertEqual(d["kind"], "bill")
        self.assertEqual(d["doc_type"], "Projet de décret")
        self.assertEqual(d["status"], "texte adopté et transmis au Gouvernement (parchemin)")
        self.assertEqual(d["status_date"], "2026-09-30")
        self.assertNotIn("Texte adopté", d["title"])
        r = by["pw/2025-2026/549"]
        self.assertEqual(r["kind"], "resolution")
        self.assertEqual(r["status"], "Texte adopté en séance plénière")
        self.assertTrue(r["authors"].startswith("Mmes Roberty"))
        self.assertTrue(r["title"].endswith("LGBTQIA+"))
        self.assertTrue(r["url"].startswith("https://nautilus.parlement-wallon.be/"))
        self.assertEqual(by["pw/2026-2027/701"]["kind"], "motion")
        self.assertEqual(by["pw/2026-2027/701"]["status"], "déposé")

    def test_walloon_members_carry_no_contact_data(self):
        got = br.parse_pw_members(fj("pw-members.json"))
        self.assertEqual(len(got), 3)
        self.assertEqual(set(got[0]), {"key", "parliament", "name", "group", "constituency"})
        self.assertNotIn("REDACTED", json.dumps(got))
        self.assertNotIn("example.invalid", json.dumps(got))

    def test_brussels_dossiers_in_both_languages(self):
        by = {d["key"]: d for d in br.parse_bru(fj("bru-dossiers.json"))}
        a = by["bru/24-29/A-222"]
        self.assertEqual(a["kind"], "resolution")
        self.assertTrue(a["title"].startswith("Proposition de résolution visant à lutter"))
        self.assertTrue(a["title_alt"].startswith("Voorstel van resolutie ter bestrijding"))
        self.assertEqual(a["status"], "Texte adopté par la séance plénière")
        self.assertTrue(a["url"].startswith("https://www.parlement.brussels/weblex-doc-det/"))
        self.assertEqual(by["cocom/24-29/B-9"]["parliament"], "cocom")
        self.assertIsNone(by["bru/24-29/A-8"]["status"])          # one document: deposited only
        self.assertEqual(by["cocom/24-29/B-74"]["status"], "Texte adopté par la séance plénière")

    def test_fwb_newest_documents(self):
        got = br.parse_fwb_list(fx("fwb-documents.html"))
        by = {d["key"]: d for d in got}
        self.assertEqual(set(by), {"fwb/2026-2027/327", "fwb/2025-2026/285", "fwb/q/001863672"})
        self.assertEqual(by["fwb/2026-2027/327"]["date"], "2026-10-12")
        # the adopted text is a status of the resolution it adopts, never a document
        t = by["fwb/2025-2026/285"]
        self.assertEqual((t["kind"], t["status"], t["status_date"], t["date"]),
                         ("resolution", "texte adopté en séance plénière", "2026-10-07", None))
        self.assertEqual(by["fwb/q/001863672"]["authors"], "Bénédicte Linard")

    def test_fwb_plenary_agenda(self):
        self.assertEqual(br.parse_fwb_agenda_index(fx("fwb-agenda.html")),
                         [("https://www.pfwb.be/agendas/seances-plenieres-2026-10-07-001863737",
                           "2026-10-07")])
        got = br.parse_fwb_plenary(fx("fwb-plenary-2026-10-07.html"), "2026-10-07", "u")
        by = {d["key"]: d for d in got}
        self.assertEqual(set(by), {"fwb/2025-2026/285", "fwb/2026-2027/325"})
        self.assertEqual(by["fwb/2026-2027/325"]["kind"], "motion")
        self.assertEqual(by["fwb/2025-2026/285"]["status"], "on the plenary agenda of 7 October 2026")
        self.assertNotIn("déposée par", by["fwb/2025-2026/285"]["title"])

    def test_kinds(self):
        self.assertEqual(br.bill_kind("Ontwerp van decreet"), "bill")
        self.assertEqual(br.bill_kind("Ontwerp van decreet algemene rekening"), "other")
        self.assertEqual(br.bill_kind("Proposition d'ordonnance"), "bill")
        self.assertEqual(br.bill_kind("Conceptnota voor nieuwe regelgeving"), "concept")
        self.assertEqual(br.bill_kind("Budgets et comptes"), "other")
        self.assertEqual(br.session_name("26-27"), "2026-2027")


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_db()

    def test_every_parliament(self):
        cl, inner, serving = client()
        self.assertEqual(run_all(self.conn, cl), 0)
        count = dict(self.conn.execute("SELECT parliament, COUNT(*) FROM ber_docs GROUP BY 1"))
        self.assertEqual(set(count), {"vl", "pw", "bru", "cocom", "fwb"})
        self.assertEqual(count["vl"], 18)
        reads = ber.reads(self.conn)
        self.assertEqual(set(reads), set(ber.READ))
        self.assertTrue(all(r[2] == TODAY for r in reads.values()))
        # members: Flemish and Walloon, no contact data anywhere in the store
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ber_members").fetchone()[0], 7)
        dump = "\n".join(str(r) for r in self.conn.execute("SELECT * FROM ber_members"))
        self.assertNotIn("REDACTED", dump)

    def test_classification_per_language(self):
        cl, _, _ = client()
        run_all(self.conn, cl)
        area = dict(self.conn.execute("SELECT doc_key, areas FROM ber_docs"))
        self.assertEqual(json.loads(area["vl/2025-2026/897"]), [1])         # abortustermijn, NL list
        self.assertEqual(json.loads(area["pw/2025-2026/549"]), [5])         # LGBTQIA+, FR list
        self.assertIn(8, json.loads(area["bru/24-29/A-8"]))                 # ritueel slachten: the Dutch title
        self.assertIn(9, json.loads(area["cocom/24-29/B-39"]))              # kinderbijslag: the Dutch title
        self.assertEqual(json.loads(area["fwb/2026-2027/327"]), [])

    def test_votes_read_only_for_documents_on_our_ground(self):
        cl, inner, _ = client()
        run_all(self.conn, cl)
        pi_reads = [u for u in inner.fetched if "/e/opendata/pi/" in u]
        self.assertEqual(pi_reads, ["https://ws.vlpar.be/e/opendata/pi/1960322"])
        v = [tuple(r) for r in self.conn.execute("SELECT doc_key, yes, no, areas FROM ber_votes")]
        self.assertEqual(v, [("vl/2025-2026/552", 27, 91, "[8]")])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ber_positions").fetchone()[0], 118)

    def test_a_later_read_only_reads_recent_votes(self):
        cl, _, _ = client()
        run_all(self.conn, cl)
        cl2, inner2, _ = client()
        br.run_parliament(self.conn, cl2, "vl", TODAY, log=quiet)
        self.assertFalse([u for u in inner2.fetched if "/e/opendata/pi/" in u])

    def test_open_data_asks_no_robots_and_websites_do(self):
        cl, _, serving = client()
        run_all(self.conn, cl)
        asked = set(serving.robots_asked)
        self.assertNotIn("www.parlement-wallonie.be", asked)               # documented Open Data only
        self.assertIn("ws.vlpar.be", asked)                                 # the search route is a website's
        self.assertIn("www.parlement.brussels", asked)
        self.assertIn("www.pfwb.be", asked)
        self.assertTrue(rg.is_documented_api("https://ws.vlpar.be/e/opendata/pi/1"))
        self.assertFalse(rg.is_documented_api("https://ws.vlpar.be/api/search/query/x"))

    def test_robots_disallow_is_a_gap_and_costs_nothing_else(self):
        cl, inner, _ = client(robots={"www.pfwb.be": "User-agent: *\nDisallow: /\n"})
        gaps = run_all(self.conn, cl)
        self.assertEqual(gaps, 1)
        self.assertFalse([u for u in inner.fetched if "pfwb.be" in u])
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM ber_docs WHERE parliament='fwb'").fetchone()[0], 0)
        self.assertGreater(self.conn.execute(
            "SELECT COUNT(*) FROM ber_docs WHERE parliament='pw'").fetchone()[0], 0)
        self.assertTrue(self.conn.execute(
            "SELECT detail FROM gaps WHERE feed='be-regions'").fetchone()[0].startswith(
                "Parlement de la Fédération Wallonie-Bruxelles: not read"))
        self.assertIsNone(ber.reads(self.conn)["fwb"][2])

    def test_failed_source_is_a_gap(self):
        cl, _, _ = client(fail=("dos_leg_legis",))
        self.assertEqual(br.run_parliament(self.conn, cl, "bru", TODAY, log=quiet), 1)
        self.assertEqual(set(ber.reads(self.conn)), {"bru", "cocom"})

    def test_status_change_first_seen_and_first_sighting_is_no_move(self):
        cl, _, _ = client()
        br.run_parliament(self.conn, cl, "bru", "2026-10-06", log=quiet)
        self.assertEqual(tuple(self.conn.execute("SELECT status_seen, status_date FROM ber_docs "
                                                 "WHERE doc_key='bru/24-29/A-8'").fetchone()),
                         (0, None))
        data = fj("bru-dossiers.json")
        for r in data["data"]:
            if "Fiche A-8<" in r[2]:
                r[8] += '<br><a target=_blank href="http://x/y.pdf">A-8/2-25/26</a> - Rapport fait au nom de la Commission.'
        cl2, _, _ = client(override={"dos_leg_legis_24-29.json": json.dumps(data)})
        br.run_parliament(self.conn, cl2, "bru", TODAY, log=quiet)
        self.assertEqual(tuple(self.conn.execute("SELECT status, status_seen, status_date FROM "
                                                 "ber_docs WHERE doc_key='bru/24-29/A-8'").fetchone()),
                         ("Rapport fait au nom de la Commission", 1, TODAY))

    def test_fwb_partial_rows_keep_what_a_fuller_read_stored(self):
        cl, _, _ = client()
        br.run_parliament(self.conn, cl, "fwb", TODAY, log=quiet)
        row = self.conn.execute("SELECT title, status, status_date, url FROM ber_docs "
                                "WHERE doc_key='fwb/2025-2026/285'").fetchone()
        self.assertTrue(row[0].startswith("Proposition de résolution visant à soutenir"))
        self.assertIn(row[1], ("texte adopté en séance plénière",
                               "on the plenary agenda of 7 October 2026"))
        self.assertEqual(row[2], "2026-10-07")

    def test_reclassify_offline_and_watchlist_by_key(self):
        cl, _, _ = client()
        run_all(self.conn, cl)
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "watchlist-be.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('regions:\n  "fwb/2026-2027/327": {areas: [6], why: "test"}\n')
            br.reclassify(self.conn, watch_path=path, log=quiet)
            r = self.conn.execute("SELECT areas, matched_terms, tier FROM ber_docs "
                                  "WHERE doc_key='fwb/2026-2027/327'").fetchone()
            self.assertEqual(json.loads(r[0]), [6])
            self.assertIn("watch:fwb/2026-2027/327", json.loads(r[1]))
            self.assertEqual(r[2], 2)
        finally:
            shutil.rmtree(tmp)

    def test_watchlist_file_section_is_well_formed(self):
        for key, (areas, why) in ber.watchlist().items():
            self.assertRegex(key, r"^(vl|pw|fwb|bru|cocom)/")
            self.assertTrue(areas and why)


class Schema(unittest.TestCase):
    def test_tables_declared_and_created(self):
        conn = fresh_db()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ber.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertIn(t, have)

    def test_schema_is_idempotent(self):
        conn = sqlite3.connect(":memory:")
        ber.ensure_schema(conn)
        ber.ensure_schema(conn)

    def test_every_parliament_read_or_blocked(self):
        codes = {c for c, _, _, _ in ber.PARLIAMENTS}
        self.assertEqual(set(ber.READ) | set(ber.BLOCKED), codes)
        self.assertFalse(set(ber.READ) & set(ber.BLOCKED))
        self.assertEqual(set(br.READERS) | {"cocom"}, set(ber.READ))


class Edition(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        self.eds = os.path.join(self.tmp, "editions")
        os.makedirs(self.cfg)
        os.makedirs(self.eds)
        for name in ("watchlist-be.yaml", "edition-noise-be.yaml"):
            if os.path.exists(os.path.join(ROOT, "config", name)):
                shutil.copy(os.path.join(ROOT, "config", name), self.cfg)
        self.conn = fresh_db()
        self.conn.row_factory = sqlite3.Row
        cl, _, _ = client()
        run_all(self.conn, cl)

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def render(self, since):
        return ce.render(self.conn, ce.adapter("be"), TODAY, since, config_dir=self.cfg,
                         directory=self.eds)

    def test_section_after_the_watchlist(self):
        text = self.render("2026-05-31")
        self.assertIn("## Communities and regions", text)
        self.assertLess(text.index("## Watchlist"), text.index("## Communities and regions"))
        self.assertLess(text.index("## Communities and regions"), text.index("## Coverage"))
        self.assertIn("vl/2025-2026/897", text)
        self.assertIn("Vlaams Parlement: voorstel van resolutie 897 (2025-2026); deposited "
                      "17 June 2026", text)
        self.assertIn("pw/2025-2026/549", text)                  # a stage move in the window
        self.assertIn("status dated 3 June 2026", text)
        self.assertNotIn("A quiet week", text)

    def test_brussels_shows_the_dutch_title(self):
        text = self.render("2025-11-30")
        self.assertIn("bru/24-29/A-222", text)
        self.assertIn("NL: *Voorstel van resolutie ter bestrijding", text)

    def test_flemish_vote_with_group_split(self):
        text = self.render("2025-10-31")
        self.assertIn("vl/1962158/1", text)
        self.assertIn("Tally: 27 for, 91 against", text)
        self.assertIn("By group", text)
        self.assertIn("Vlaams Parlement: plenary vote on vl/2025-2026/552", text)

    def test_coverage_names_what_is_not_read(self):
        text = self.render("2026-10-06")
        self.assertIn("Parlament der Deutschsprachigen Gemeinschaft not read: pdg.be", text)
        self.assertIn("Parlement de la Fédération Wallonie-Bruxelles: partial", text)
        self.assertIn("Communities and regions read (last read): Flanders 13 Oct", text)

    def test_migration_is_never_shown(self):
        got = ce.adapter("be").extra_sections(self.conn, "2024-01-01", TODAY, {})[0][2]
        self.assertFalse([it for it in got if it["areas"] == [11]])

    def test_dm_counts_the_regions(self):
        text = ce.dm_summary(self.conn, ce.adapter("be"), TODAY, "2026-05-31",
                             config_dir=self.cfg, directory=self.eds)
        self.assertIn("*Communities and regions*:", text)


if __name__ == "__main__":
    unittest.main()
