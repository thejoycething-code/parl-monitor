"""Switzerland's cantonal parliaments (CH7): tools/ch_cantons.py and the
"Cantons" section of the Swiss edition (src/editions/ch.py).

Fixtures under tests/fixtures/ch_cantons/ are trimmed copies of the live
sources read on 13 October 2026: six Geschaefte from Zuerich's CMI service
(their full texts cut to '(trimmed)'), seventeen rows of Bern's
geschaeft.json and twelve of its abstimmung_tagblatt.json (two before the
legislature), one page of
Geneva's search ('genre', last year), Vaud's list of objects awaiting
treatment for the health and social department, and Ticino's order of the
day of 5 October 2026. No network.
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

from src import ch_store, db  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src.editions import ch as ch_ed  # noqa: E402
from tools import ch_cantons as C  # noqa: E402
from tests.robots_fakes import RobotsServing  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "ch_cantons")
HAVE_TAX = all(os.path.exists(p) for p in (C.TAXONOMY_DE, C.TAXONOMY_FR, C.TAXONOMY_IT))


def fixture(name, mode="r"):
    with open(os.path.join(FIX, name), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        return fh.read()


def by_key(acts):
    return {a["key"]: a for a in acts}


class FakeClient:
    """get_json / get_bytes / get_text from fixtures, by URL prefix."""

    user_agent = "citizengo-parlmonitor/1.0 (+test)"
    throttle = 1.0

    def __init__(self, pages):
        self.pages = pages
        self.urls = []

    def _get(self, url):
        if url.endswith("/robots.txt"):
            raise C.FetchError(url, C.FEED, "robots", 1,
                               urllib.error.HTTPError(url, 404, "Not Found", {}, None))
        self.urls.append(url)
        for prefix, body in self.pages:
            if url.startswith(prefix):
                return body
        raise C.FetchError(url, C.FEED, "test", 1, "no fixture")

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._get(url))

    def get_bytes(self, url, feed, slug, **kw):
        body = self._get(url)
        return body.encode("utf-8") if isinstance(body, str) else body

    def get_text(self, url, feed, slug, **kw):
        body = self._get(url)
        return body.decode("utf-8") if isinstance(body, bytes) else body


class ZuerichTests(unittest.TestCase):
    def setUp(self):
        self.acts, self.hits = C.parse_zuerich(fixture("zh_searchdetails.xml", "rb"))
        self.by = by_key(self.acts)

    def test_rows_keyed_on_the_kantonsrat_number(self):
        self.assertEqual(self.hits, 93)
        self.assertEqual(sorted(self.by), ["zh/360/2026", "zh/361/2026", "zh/362/2026",
                                           "zh/363/2026", "zh/376/2026", "zh/6129"])

    def test_a_parliamentary_initiative(self):
        a = self.by["zh/376/2026"]
        self.assertEqual(a["kind"], "Parlamentarische Initiative")
        self.assertEqual(a["title"], "Standesinitiative: Konversionsmassnahmen wirksam verbieten")
        self.assertEqual((a["presented"], a["status"], a["status_date"]),
                         ("2026-09-28", "Eingereicht", "2026-09-28"))
        self.assertTrue(a["initiative"].endswith("(GLP) and 1 other(s)") or "(GLP)" in a["initiative"])
        self.assertFalse(a["question"])
        self.assertTrue(a["seq"])

    def test_a_question_and_a_government_bill(self):
        self.assertTrue(self.by["zh/360/2026"]["question"])
        v = self.by["zh/6129"]
        self.assertEqual((v["kind"], v["label"]), ("Vorlage", "Vorlage 6129"))
        self.assertEqual(v["status"], "Antrag Regierungsrat")

    def test_the_queries(self):
        self.assertEqual(C.zh_query_new("2026-10-13", 45),
                         'beginn_start > "2026-08-29 00:00:00" sortBy beginn_start/sort.descending')
        self.assertEqual(C.zh_query_changed(4414191), "seq > 4414191 sortBy seq/sort.ascending")
        self.assertIn("q=seq%20%3E%2010", C.zh_url(C.zh_query_changed(10)))


class BernTests(unittest.TestCase):
    def setUp(self):
        self.acts = C.parse_bern(json.loads(fixture("be_geschaeft.json")))
        self.by = by_key(self.acts)

    def test_two_titles_and_epoch_dates(self):
        a = self.by["be/2026.GRPARL.151"]
        self.assertEqual(a["title"], "Stärkung der Suizidprävention im Kanton Bern")
        self.assertEqual(a["title_fr"], "Renforcer la prévention du suicide dans le canton de Berne")
        self.assertEqual((a["presented"], a["status_date"]), ("2026-03-12", "2026-09-01"))

    def test_a_point_by_point_decision_is_spaced(self):
        status = self.by["be/2026.GRPARL.151"]["status"]
        self.assertIn("Enthaltungen) Ziffer 2", status)

    def test_a_government_business_has_no_submission_date(self):
        a = self.by["be/2025.BVD.6081"]
        self.assertIsNone(a["presented"])
        self.assertEqual(a["status_date"], "2026-09-03")
        self.assertTrue(a["status"].startswith("Annahme"))

    def test_before_the_legislature_is_dropped(self):
        rows = json.loads(fixture("be_geschaeft.json"))
        self.assertEqual(C.parse_bern(rows, since="2026-08-01"),
                         [a for a in C.parse_bern(rows, since="2026-08-01")])
        self.assertTrue(all(max(a["presented"] or "", a["status_date"] or "") >= "2026-08-01"
                            for a in C.parse_bern(rows, since="2026-08-01")))

    def test_votes_carry_the_act_subject_result_and_tally(self):
        votes = C.parse_bern_votes(json.loads(fixture("be_abstimmung.json")))
        three = [v for v in votes if v["act_key"] == "be/2026.GRPARL.151"
                 and v["subject"].startswith("Ziff. 3")][0]
        self.assertEqual((three["yes"], three["no"], three["abstain"]), (77, 63, 4))
        self.assertEqual(three["result"], "Annahme / Adoption")
        self.assertEqual(three["date"], "2026-09-01")
        amend = [v for v in votes if v["subject"] and v["subject"].startswith("Antrag 2")][0]
        self.assertEqual(amend["subject"], "Antrag 2, BaK / Proposition 2, CIAT")
        cond = [v for v in votes if v["subject"] and v["subject"].startswith("Annahme mit")][0]
        self.assertEqual(cond["result"], "Annahme / Adoption")
        casting = [v for v in votes if v["subject"] == "Ziff. 1 / ch. 1"
                   and v["act_key"] == "be/2023.RRGR.210"][0]
        self.assertTrue(casting["result"].startswith("Annahme mit Stichentscheid"))


class GenevaTests(unittest.TestCase):
    def setUp(self):
        self.by = by_key(C.merge_geneva(C.parse_geneva(fixture("ge_search_genre.html"))))

    def test_documents_fold_into_their_object(self):
        a = self.by["ge/M3087"]
        self.assertEqual(a["label"], "M 3087-B (2026-07)")
        self.assertEqual((a["status"], a["status_date"]), ("Pris acte", "2026-09-04"))
        self.assertTrue(a["title"].startswith("pour intégrer les soins de transition de genre"))

    def test_a_reports_title_gives_the_objects_words_and_authors(self):
        a = self.by["ge/M3137"]
        self.assertTrue(a["title"].startswith("demandant un moratoire sur les interventions"))
        self.assertTrue(a["initiative"].startswith("Yves Nidegger"))
        b = self.by["ge/M3010"]
        self.assertTrue(b["title"].startswith("Interventions de réassignation sexuelle"))
        self.assertEqual((b["status"], b["status_date"]), ("Objet refusé", "2026-01-23"))

    def test_questions_are_marked(self):
        self.assertTrue(self.by["ge/Q4162"]["question"])
        self.assertEqual(self.by["ge/Q4162"]["initiative"], "Isabel Jan-Hess")
        self.assertFalse(self.by["ge/PL13327"]["question"])

    def test_dates(self):
        self.assertEqual(C.ge_month("Juill. 2026"), "2026-07")
        self.assertEqual(C.ge_month("Févr. 2023"), "2023-02")
        self.assertEqual(C.ge_day("4 sept. 2026"), "2026-09-04")
        self.assertEqual(C.ge_day("23 janv. 2026"), "2026-01-23")


class VaudTests(unittest.TestCase):
    def setUp(self):
        self.acts = C.parse_vaud(fixture("vd_dsas.html"))
        self.by = by_key(self.acts)

    def test_objects(self):
        self.assertGreater(len(self.acts), 50)
        a = self.by["vd/25_MOT_40"]
        self.assertEqual((a["kind"], a["title"]),
                         ("Motion", "Pour une harmonisation des seuils d’aide sociale"))
        self.assertEqual(a["initiative"], "Cédric Weissert et consorts au nom UDC")
        self.assertEqual(a["committee"], "Commission thématique des affaires sociales")
        self.assertEqual(a["status"], "Séance de commission le 09.03.26")
        self.assertFalse(a["dated"])

    def test_two_reports_are_one_status(self):
        a = self.by["vd/24_MOT_20"]
        self.assertEqual(a["status"], "Rapport de la majorité de la commission reçu le 04.02.25; "
                                      "Rapport de la minorité de la commission reçu le 12.05.25")


class TicinoTests(unittest.TestCase):
    def setUp(self):
        self.acts = C.parse_ticino(fixture("ti_odg.html"))
        self.by = by_key(self.acts)

    def test_session_and_points_with_acts(self):
        self.assertEqual(C.ti_session(fixture("ti_odg.html"))[0], "2026-10-05")
        self.assertEqual(len(self.acts), 19)        # procedural points carry no act
        a = self.by["ti/133577"]
        self.assertEqual(a["kind"], "Messaggio")
        self.assertTrue(a["title"].startswith("Concessione di un contributo"))
        self.assertEqual(a["status_date"], "2026-10-05")
        self.assertIn("seduta di lunedì 5 ottobre 2026", a["status"])
        self.assertIn("procedura scritta", a["status"])
        self.assertEqual(a["committee"], "DECS")

    def test_a_cantonal_initiative(self):
        a = self.by["ti/112241"]
        self.assertEqual(a["kind"], "Iniziativa cantonale")
        self.assertIn("stalking", a["title"] + " " + a["body"])


@unittest.skipUnless(HAVE_TAX, "a taxonomy file is missing")
class AlternativeRouteTests(unittest.TestCase):
    """The cantons whose open-data portals (or www.ag.ch/grossrat) robots.txt
    closes, read from their parliaments' own hosts (access-routes, 13
    October 2026)."""

    def test_stgallen_businesses_types_and_states(self):
        types = C.sg_names(json.loads(fixture("sg_business_types.json")))
        states = C.sg_names(json.loads(fixture("sg_process_states.json")))
        self.assertEqual(types[6], "Motion")
        self.assertEqual(states[46], "Geschäft abgeschlossen")
        acts, oldest = C.parse_sg_businesses(json.loads(fixture("sg_businesses.json")), types, states)
        self.assertEqual(len(acts), 5)
        a = acts[0]
        self.assertEqual((a["key"], a["kind"], a["presented"], a["status"]),
                         ("sg/61.26.79", "Einfache Anfrage", "2026-10-12", "Beratung durch Regierung"))
        self.assertTrue(a["question"])
        self.assertEqual(a["url"], "https://www.ratsinfo.sg.ch/businesses/7214")
        self.assertEqual(oldest, "2026-09-28")

    def test_stgallen_votes_and_tally(self):
        got = C.parse_sg_votings(json.loads(fixture("sg_votings.json")))
        self.assertEqual(got[0]["act_key"], "sg/22.26.15")
        self.assertEqual(got[0]["date"], "2026-09-16")
        v = C.parse_sg_voting(json.loads(fixture("sg_voting_7449.json")), got[0])
        self.assertEqual((v["yes"], v["no"], v["abstain"], v["result"]), (33, 78, 3, "Abgelehnt"))
        self.assertEqual(v["act_key"], "sg/22.26.15")
        self.assertEqual(v["key"], "sg/v/7449")

    def test_baselland_newest_documents(self):
        acts = by_key(C.parse_bl(fixture("bl_neuste.html")))
        m = acts["bl/2026/6989"]
        self.assertEqual((m["kind"], m["presented"], m["status_date"]), ("Motion", "2026-09-24", "2026-09-24"))
        self.assertEqual(m["status"], "Eingereicht (Text Motion)")
        r = acts["bl/2025/571"]
        self.assertEqual(r["status"], "Bericht der Bildungs-, Kultur- und Sportkommission")
        self.assertEqual(r["status_date"], "2026-10-12")
        self.assertIn("geschaeft.php?gid=", r["url"])

    def test_baselstadt_motions_and_versand(self):
        new = C.parse_bs_new(fixture("bs_vorstoesse.html"))
        self.assertEqual(len(new), 9)
        a = by_key(new)["bs/26.5441"]
        self.assertEqual((a["kind"], a["initiative"]), ("Interpellation", "Franziska Stier"))
        self.assertEqual(a["title"], "Entsiegeln und Begrünen - Erfahrungen und Umsetzung in Basel-Stadt")
        self.assertEqual(a["status"], "Eingereicht für die Sitzung vom 14.10.2026")
        self.assertEqual(by_key(new)["bs/26.5263"]["status"], "Eingereicht für die Sitzung vom 24.06.2026")
        versand = C.parse_bs_versand(fixture("bs_versand.html"))
        self.assertEqual(versand[0][:3], ("2026-10-02", "Bericht oder Schreiben einer Kommission", "26.5272"))
        cats = {v[1] for v in versand}
        self.assertIn("Schriftliche Antwort des Regierungsrates", cats)
        merged = by_key(C.merge_bs(new, versand))
        answered = merged["bs/26.5307"]
        self.assertEqual((answered["kind"], answered["initiative"], answered["status_date"]),
                         ("Interpellation", "Lukas Hug", "2026-09-25"))
        self.assertTrue(answered["status"].startswith("Schriftliche Antwort des Regierungsrates"))

    def test_thurgau_pending_business(self):
        acts = by_key(C.parse_tg(fixture("tg_pendente.html")))
        m = acts["tg/2024/117"]
        self.assertEqual((m["kind"], m["presented"]), ("Motion", "2025-02-19"))
        self.assertIn("Geschlechtsumwandlung", m["title"])
        self.assertEqual(m["initiative"], "Christian Caviezel, Raphael Stutz, Christina Fäsi")
        self.assertEqual(acts["tg/2024/281"]["kind"], "Einfache Anfrage")
        self.assertTrue(acts["tg/2024/281"]["question"])

    def test_aargau_law_collection(self):
        acts = C.parse_ag(json.loads(fixture("ag_index.json")))
        self.assertEqual(len(acts), 8)                 # the 2024 entries predate AG_SINCE
        a = by_key(acts)["ag/2026/06-03"]
        self.assertEqual((a["kind"], a["presented"], a["status_date"]), ("Dekret", "2026-08-20", "2026-08-20"))
        self.assertEqual(a["url"], "https://gesetzessammlungen.ag.ch/app/de/change_documents/1820")

    @unittest.skipUnless(HAVE_TAX, "taxonomies missing")
    def test_thurgau_gender_motion_is_on_our_ground(self):
        tax = C.Taxonomies()
        a = by_key(C.parse_tg(fixture("tg_pendente.html")))["tg/2024/117"]
        self.assertIn(3, C.classify(tax, a)[0])

    def test_the_closed_portals_are_never_asked(self):
        # The page routes (Basel-Stadt's and Thurgau's are now the fallback)
        # never touch a portal whose robots.txt refuses us.
        for url in (C.SG_API, C.BL_NEW, C.BS_NEW, C.BS_VERSAND, C.TG_PENDING, C.AG_INDEX):
            self.assertNotRegex(url, r"data\.bs\.ch|data\.bl\.ch|daten\.sg\.ch|data\.tg\.ch|"
                                     r"www\.ag\.ch/grossrat")


def load(name):
    return json.loads(fixture(name))


class OpenDataTests(unittest.TestCase):
    """Basel-Stadt (data.bs.ch) and Thurgau (data.tg.ch), read with the
    owners' written permission of 13 October 2026. Fixtures: trimmed exports
    of the live datasets, read on 13 October 2026."""

    def bs(self, rows=None):
        return by_key(C.parse_bs_api(rows if rows is not None else load("bs_ods_geschaefte.json"),
                                     load("bs_ods_dokumente.json"), load("bs_ods_vorgaenge.json"),
                                     today="2026-10-13", since="2026-08-29"))

    def test_basel_stadt_businesses_dated_by_document_or_step(self):
        acts = self.bs()
        a = acts["bs/26.5228"]
        self.assertEqual((a["kind"], a["presented"], a["status_date"]),
                         ("Anzug", "2026-06-24", "2026-09-23"))
        self.assertEqual(a["status"], "Grosser Rat, Sitzung vom 23.09.2026: Überweisung an RR "
                                      "Frist: 23.09.2028 (In Bearbeitung)")
        self.assertEqual(a["initiative"], "Andrea Strahm and 1 other(s)")   # one row per co-author
        self.assertEqual(a["title"], "Ermöglichung von anonymen Geburten")
        self.assertEqual(a["url"], "https://grosserrat.bs.ch/?gnr=26.5228")
        self.assertEqual(a["source_url"],
                         "https://data.bs.ch/explore/dataset/100311/?refine.signatur_ges=26.5228")
        q = acts["bs/26.5411"]
        self.assertEqual((q["presented"], q["question"], q["initiative"]),
                         ("2026-09-23", True, "Amina Trevisan (SP)"))
        # A step scheduled for a later sitting is not a status yet.
        self.assertEqual(acts["bs/26.5405"]["status_date"], "2026-09-17")
        closed = acts["bs/26.5215"]
        self.assertEqual((closed["status"], closed["status_date"]), ("Abgeschlossen", "2026-09-14"))
        self.assertTrue(all(x["dated"] and "data.bs.ch" in x["source_url"] for x in acts.values()))

    def test_basel_stadt_skips_elections_and_untouched_business(self):
        rows = load("bs_ods_geschaefte.json") + [
            {"signatur_ges": "26.9001", "ga_rr_gr": "Wahl", "titel_ges": "Wahl", "beginn_ges": "2026-10-01"},
            {"signatur_ges": "19.5000", "ga_rr_gr": "Anzug", "titel_ges": "Anzug X betreffend alt",
             "beginn_ges": "2019-01-01", "status_ges": "In Bearbeitung"}]
        acts = self.bs(rows)
        self.assertNotIn("bs/26.9001", acts)
        self.assertNotIn("bs/19.5000", acts)       # pending, nothing in the window
        self.assertEqual(len(acts), 7)

    def test_basel_stadt_votes_with_every_members_vote(self):
        votes = {v["key"]: v for v in C.parse_bs_api_votes(load("bs_ods_abstimmungen.json"))}
        v = votes["bs/v/0009609-20260923-212113"]
        self.assertEqual((v["act_key"], v["date"], v["yes"], v["no"], v["abstain"], v["counts_from"]),
                         ("bs/26.5228", "2026-09-23", 44, 38, 10, "published"))
        self.assertEqual(len(v["positions"]), 12)
        self.assertEqual(v["positions"][0], {"member": "Melanie Eberhard", "member_id": "15004054",
                                             "parl_group": "SP", "position": "Ja"})
        self.assertIn("data.bs.ch/explore/dataset/100186", v["source_url"])
        positions = {p["position"] for x in votes.values() for p in x["positions"]}
        self.assertTrue(positions <= set(C.BS_POSITIONS.values()))

    def test_thurgau_business_and_signatories(self):
        acts = by_key(C.parse_tg_api(load("tg_ods_geschaefte.json"),
                                     C.tg_authors(load("tg_ods_urheber.json")), today="2026-10-13"))
        self.assertEqual(sorted(acts), ["tg/2024/117", "tg/2024/173", "tg/2024/391"])  # no Wahlgeschäft
        m = acts["tg/2024/117"]                       # the key the pending list gives it too
        self.assertIn("Geschlechtsumwandlung", m["title"])
        self.assertEqual((m["presented"], m["status_date"]), ("2025-02-19", "2026-09-16"))
        self.assertEqual(m["status"], "Abgeschlossen; Abschluss am 16.09.2026; "
                                      "Erheblicherklärung: nein; Teilerheblicherklärung: nein")
        self.assertEqual(m["initiative"], "Christian Caviezel (EDU) and 2 other(s)")
        ea = acts["tg/2024/391"]
        self.assertEqual((ea["status"], ea["question"]), ("In Bearbeitung; pendent bei: Regierungsrat", True))
        self.assertTrue(all(a["source_url"] == "https://data.tg.ch/explore/dataset/sk-stat-140/"
                            for a in acts.values()))
        self.assertEqual(C.tg_key("96/PE 1/98"), "tg/1996/98")
        self.assertIsNone(C.tg_key("Wahl"))

    def test_thurgau_votes_tallied_from_members(self):
        votes = C.parse_tg_api_votes(load("tg_ods_abstimmungen.json"))
        plain = [v for v in votes if v["date"] == "2025-09-10"][0]
        self.assertEqual((plain["act_key"], plain["subject"], plain["yes"], plain["no"], plain["abstain"],
                          plain["counts_from"]), ("tg/2024/179", "Abstimmung Beschlussesentwurf", 4, 3, 1,
                                                  "tallied"))
        self.assertEqual(plain["act_title"],
                         "Kantonsreferendum gegen das Bundesgesetz über die Individualbesteuerung")
        self.assertEqual(len(plain["positions"]), 9)
        options = [v for v in votes if v["date"] == "2023-12-06"][0]
        self.assertEqual((options["yes"], options["no"]), (None, None))
        self.assertIn("Antrag GFK 3", options["result"])

    def test_every_api_url_is_under_a_written_permission(self):
        from src import robots_guard as rg
        urls = [C.ods_export(C.BS_ODS, d, "x") for d in C.BS_SETS.values()]
        urls += [C.ods_export(C.TG_ODS, d, "x") for d in C.TG_SETS.values()]
        for u in urls:
            self.assertIsNotNone(rg.permission_for(u), u)
        self.assertIsNone(rg.permission_for(C.ods_export(C.BS_ODS, "100307", "x")))
        self.assertEqual(C.batches("2026-09-01", "2026-09-30", 14),
                         [("2026-09-01", "2026-09-14"), ("2026-09-15", "2026-09-28"),
                          ("2026-09-29", "2026-09-30")])


class StoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tax = C.Taxonomies()

    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))

    def test_classified_in_the_cantons_language(self):
        zh = by_key(C.parse_zuerich(fixture("zh_searchdetails.xml", "rb"))[0])["zh/376/2026"]
        self.assertIn(4, C.classify(self.tax, zh)[0])
        ge = by_key(C.merge_geneva(C.parse_geneva(fixture("ge_search_genre.html"))))["ge/M3010"]
        self.assertIn(3, C.classify(self.tax, ge)[0])
        be = by_key(C.parse_bern(json.loads(fixture("be_geschaeft.json"))))["be/2023.RRGR.210"]
        areas, terms, tier = C.classify(self.tax, be)
        self.assertIn(3, areas)
        self.assertEqual(tier, 1)

    def test_the_first_sighting_is_never_a_change(self):
        a = {"key": "vd/26_MOT_1", "canton": "vd", "kind": "Motion", "title": "t",
             "status": "A", "dated": False}
        self.assertEqual(C.store_act(self.conn, a, ([], [], None), "2026-10-13"), "new")
        self.assertEqual(C.store_act(self.conn, a, ([], [], None), "2026-10-20"), "same")
        row = self.conn.execute("SELECT status_date, status_seen FROM ch_canton_acts").fetchone()
        self.assertEqual(tuple(row), (None, 0))

    def test_an_undated_change_is_stamped_with_the_run_that_saw_it(self):
        a = {"key": "vd/26_MOT_1", "canton": "vd", "kind": "Motion", "title": "t",
             "status": "A", "dated": False}
        C.store_act(self.conn, a, ([], [], None), "2026-10-13", baseline=True)
        self.assertEqual(C.store_act(self.conn, dict(a, status="B"), ([], [], None),
                                     "2026-10-20"), "moved")
        row = self.conn.execute("SELECT status_date, status_seen, baseline, first_seen FROM "
                                "ch_canton_acts").fetchone()
        self.assertEqual(tuple(row), ("2026-10-20", 1, 1, "2026-10-13"))

    def test_a_dated_source_keeps_its_own_dates(self):
        a = {"key": "be/X", "canton": "be", "kind": "Motion", "title": "t", "status": "A",
             "status_date": "2026-09-01", "dated": True, "presented": "2026-03-01"}
        C.store_act(self.conn, a, ([], [], None), "2026-10-13")
        self.assertEqual(C.store_act(self.conn, dict(a, status="B", status_date="2026-10-01"),
                                     ([], [], None), "2026-10-20"), "moved")
        row = self.conn.execute("SELECT status_date, status_seen, presented FROM "
                                "ch_canton_acts").fetchone()
        self.assertEqual(tuple(row), ("2026-10-01", 0, "2026-03-01"))

    def test_watched_by_key(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "w.yaml")
            with open(path, "w") as fh:
                fh.write('businesses: {}\ncantons:\n  "vd/26_MOT_1": {areas: [9], why: test}\n')
            a = {"key": "vd/26_MOT_1", "canton": "vd", "title": "rien"}
            areas, terms, tier = C.classify(self.tax, a, watch_path=path)
            self.assertEqual((areas, terms, tier), ([9], ["watch:vd/26_MOT_1"], 2))

    def test_votes_take_their_acts_areas_and_reclassify_is_offline(self):
        be = C.parse_bern(json.loads(fixture("be_geschaeft.json")))
        C.store_all(self.conn, be, self.tax, "2026-10-13")
        for v in C.parse_bern_votes(json.loads(fixture("be_abstimmung.json"))):
            C.store_vote(self.conn, v, "2026-10-13")
        got = self.conn.execute("SELECT areas FROM ch_canton_divisions WHERE act_key="
                                "'be/2023.RRGR.210'").fetchall()
        self.assertTrue(got and all("3" in r[0] for r in got))
        self.conn.execute("UPDATE ch_canton_acts SET areas='[]'")
        C.reclassify(self.conn, self.tax)
        self.assertIn("3", self.conn.execute("SELECT areas FROM ch_canton_acts WHERE act_key="
                                             "'be/2023.RRGR.210'").fetchone()[0])


@unittest.skipUnless(HAVE_TAX, "a taxonomy file is missing")
class MainTests(unittest.TestCase):
    def run_main(self, pages, cantons, robots=None, check=None):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            inner = FakeClient(pages)
            client = RobotsServing(inner, robots) if robots is not None else inner
            self.serving = client
            orig = C.HttpClient
            C.HttpClient = lambda **kw: client
            try:
                rc = C.main(["--db", path, "--today", "2026-10-13", "--canton"] + list(cantons))
            finally:
                C.HttpClient = orig
            conn = sqlite3.connect(path)
            gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed=?", (C.FEED,))]
            stored = {r[0]: r[1] for r in conn.execute(
                "SELECT canton, COUNT(*) FROM ch_canton_acts GROUP BY canton")}
            base = conn.execute("SELECT COUNT(*) FROM ch_canton_acts WHERE baseline=1").fetchone()[0]
            votes = conn.execute("SELECT COUNT(*) FROM ch_canton_divisions").fetchone()[0]
            if check:
                check(conn)
            conn.close()
            return rc, gaps, stored, base, votes, inner

    def test_a_canton_that_fails_is_a_gap_not_the_run(self):
        rc, gaps, stored, base, votes, _ = self.run_main(
            [(C.BE_GESCHAEFT, fixture("be_geschaeft.json")),
             (C.BE_VOTES, fixture("be_abstimmung.json"))], ["be", "ti"])
        self.assertEqual(rc, 3)
        self.assertEqual(stored, {"be": 17})
        self.assertEqual(votes, 10)          # two of the twelve predate the legislature
        self.assertEqual(len(gaps), 1)
        self.assertIn("Gran Consiglio ticinese: not read", gaps[0])

    def test_an_undated_cantons_first_read_is_a_baseline(self):
        rc, gaps, stored, base, _, _ = self.run_main([(C.TI_ODG, fixture("ti_odg.html"))], ["ti"])
        self.assertEqual((rc, gaps, stored, base), (0, [], {"ti": 19}, 19))

    def test_the_alternative_routes_store_their_cantons(self):
        pages = [(C.SG_API + "business_types", fixture("sg_business_types.json")),
                 (C.SG_API + "process_states", fixture("sg_process_states.json")),
                 (C.SG_API + "businesses", fixture("sg_businesses.json")),
                 (C.SG_API + "votings?", fixture("sg_votings.json")),
                 (C.SG_API + "votings/7449", fixture("sg_voting_7449.json")),
                 (C.BL_NEW, fixture("bl_neuste.html")),
                 (C.BS_NEW, fixture("bs_vorstoesse.html")),
                 (C.BS_VERSAND, fixture("bs_versand.html")),
                 (C.TG_PENDING, fixture("tg_pendente.html")),
                 (C.AG_INDEX, fixture("ag_index.json"))]
        rc, gaps, stored, base, votes, inner = self.run_main(pages, ["sg", "bl", "bs", "tg", "ag"])
        # No data.bs.ch / data.tg.ch fixture: their APIs fail, and both fall
        # back to their parliaments' own pages, one gap each.
        self.assertEqual(rc, 3)
        self.assertEqual(len(gaps), 2)
        self.assertTrue(all("open-data API not read" in g and "own site instead" in g for g in gaps))
        self.assertEqual(stored, {"sg": 5, "bl": 27, "bs": 18, "tg": 8, "ag": 8})
        self.assertEqual(base, 18)        # Basel-Stadt prints no submission date: a baseline
        # The only vote listed is on business off our ground: its tally is not asked for.
        self.assertEqual(votes, 0)
        self.assertFalse(any("votings/7449" in u for u in inner.urls))

    def test_the_open_data_apis_with_written_permission(self):
        pages = [(C.BS_ODS + "100311/", fixture("bs_ods_geschaefte.json")),
                 (C.BS_ODS + "100313/", fixture("bs_ods_dokumente.json")),
                 (C.BS_ODS + "100314/", fixture("bs_ods_vorgaenge.json")),
                 (C.BS_ODS + "100186/", fixture("bs_ods_abstimmungen.json")),
                 (C.TG_ODS + "sk-stat-140/", fixture("tg_ods_geschaefte.json")),
                 (C.TG_ODS + "sk-stat-141/", fixture("tg_ods_urheber.json")),
                 (C.TG_ODS + "sk-stat-136/", fixture("tg_ods_abstimmungen.json"))]
        refuse = "User-agent: *\nDisallow: /api/\n"
        seen = {}

        def check(conn):
            seen["src"] = conn.execute("SELECT COUNT(*) FROM ch_canton_acts WHERE source_url IS "
                                       "NULL").fetchone()[0]
            seen["members"] = conn.execute("SELECT COUNT(*) FROM ch_canton_votes").fetchone()[0]
            seen["vote"] = conn.execute(
                "SELECT yes, no, abstain, counts_from, areas FROM ch_canton_divisions WHERE "
                "vote_key='bs/v/0009609-20260923-212113'").fetchone()
            seen["tg_vote_areas"] = conn.execute(
                "SELECT areas FROM ch_canton_divisions WHERE act_key='tg/2024/179'").fetchone()[0]
        rc, gaps, stored, base, votes, inner = self.run_main(
            pages, ["bs", "tg"], robots={"data.bs.ch": refuse, "data.tg.ch": refuse}, check=check)
        self.assertEqual((rc, gaps), (0, []))
        self.assertEqual(stored, {"bs": 7, "tg": 3})
        self.assertEqual(base, 0)                      # dated: never a baseline
        self.assertEqual(votes, 4)                     # two in Basel-Stadt, two in Thurgau
        self.assertEqual(seen["src"], 0)               # every act links its dataset
        self.assertEqual(seen["members"], 24 + 12)
        self.assertEqual(tuple(seen["vote"][:4]), (44, 38, 10, "published"))
        self.assertIn("1", seen["vote"][4])            # the act's areas (anonymous births)
        self.assertIn("9", seen["tg_vote_areas"])      # an act not stored: its printed title
        # robots.txt refuses /api/ there; the written permission covers these datasets.
        self.assertNotIn("data.bs.ch", self.serving.robots_asked)
        self.assertNotIn("data.tg.ch", self.serving.robots_asked)
        self.assertTrue(all("/exports/json?" in u for u in inner.urls))

    def test_robots_disallow_is_a_gap(self):
        rc, gaps, stored, _, _, inner = self.run_main(
            [(C.TI_ODG, fixture("ti_odg.html"))], ["ti"],
            robots={"www4.ti.ch": "User-agent: *\nDisallow: /poteri/gc/\n"})
        self.assertEqual(rc, 3)
        self.assertEqual(stored, {})
        self.assertEqual(inner.urls, [])
        self.assertIn("robots.txt disallows", gaps[0])

    def test_zuerich_reads_changes_past_the_highest_seq(self):
        body = fixture("zh_searchdetails.xml")
        rc, gaps, stored, _, _, inner = self.run_main([(C.ZH_API, body)], ["zh"])
        self.assertEqual(stored, {"zh": 6})
        self.assertEqual(len(inner.urls), 1)          # first run: the new-items query only
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.db")
            client = FakeClient([(C.ZH_API, body)])
            orig = C.HttpClient
            C.HttpClient = lambda **kw: client
            try:
                C.main(["--db", path, "--canton", "zh"])
                C.main(["--db", path, "--canton", "zh"])
            finally:
                C.HttpClient = orig
            self.assertTrue(any("seq%20%3E%204417371" in u for u in client.urls))


class SchemaTests(unittest.TestCase):
    def test_declared_and_created(self):
        for t in ("ch_canton_acts", "ch_canton_divisions", "ch_canton_votes"):
            self.assertIn(t, db.TABLES)
            self.assertIn(t, ch_store.TABLES)
        conn = db.init_db(sqlite3.connect(":memory:"))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ch_canton_acts)")}
        self.assertTrue({"act_key", "canton", "status_seen", "baseline", "seq", "last_seen",
                         "source_url"} <= cols)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ch_canton_divisions)")}
        self.assertTrue({"source_url", "counts_from"} <= cols)
        ch_store.ensure_schema(conn)   # idempotent

    def test_the_federal_watchlist_ignores_the_cantons_section(self):
        self.assertTrue(all(isinstance(k, int) for k in ch_store.watchlist()))


ACT = ("INSERT INTO ch_canton_acts (act_key, canton, kind, number, label, title, title_fr, "
       "presented, status, status_date, status_seen, initiative, committee, url, question, "
       "baseline, areas, matched_terms, tier, first_seen, last_seen) "
       "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.row_factory = sqlite3.Row
        rows = [
            # new by submission date
            ("zh/376/2026", "zh", "Parlamentarische Initiative", "376/2026", "Parlamentarische "
             "Initiative 376/2026", "Konversionsmassnahmen wirksam verbieten", None, "2026-10-08",
             "Eingereicht", "2026-10-08", 0, "A (GLP)", None, "u", 0, 0, "[4]", "[]", 1,
             "2026-10-13", "2026-10-13"),
            # moved by its dated status
            ("be/2026.GRPARL.151", "be", "Motion", "2026.GRPARL.151", "Motion 2026.GRPARL.151",
             "Suizidprävention", "Prévention du suicide", "2026-03-12", "Annahme", "2026-10-09",
             0, None, None, "u", 0, 0, "[2]", "[]", 2, "2026-09-01", "2026-10-13"),
            # undated canton, first seen after its first read: new
            ("vd/26_POS_9", "vd", "Postulat", "26_POS_9", "Postulat (26_POS_9)", "Foulard",
             None, None, "Date communiquée ultérieurement", None, 0, None, None, "u", 0, 0,
             "[8]", "[]", 1, "2026-10-10", "2026-10-13"),
            # undated canton, baseline row: never new
            ("vd/23_POS_17", "vd", "Postulat", "23_POS_17", "Postulat (23_POS_17)", "Port du "
             "foulard", None, None, "Rapport", None, 0, None, None, "u", 0, 1, "[8]", "[]", 1,
             "2026-10-10", "2026-10-13"),
            # off our ground
            ("zh/360/2026", "zh", "Anfrage", "360/2026", "Anfrage 360/2026", "Lex Koller", None,
             "2026-10-08", "Eingereicht", "2026-10-08", 0, None, None, "u", 1, 0, "[]", "[]",
             None, "2026-10-13", "2026-10-13"),
            # a question whose later step is in the window: not shown
            ("ge/Q4162", "ge", "Q", "4162", "Q 4162", "genre à l'école", None, None,
             "Objet clos", "2026-10-09", 0, None, None, "u", 1, 1, "[5]", "[]", 2,
             "2026-09-01", "2026-10-13"),
        ]
        for r in rows:
            self.conn.execute(ACT, r)
        self.conn.execute("INSERT INTO ch_canton_divisions (vote_key, canton, act_key, date, subject, "
                          "result, yes, no, abstain, url, areas, matched_terms, tier) VALUES "
                          "('be/v/1','be','be/2026.GRPARL.151','2026-10-09','Ziff. 1',"
                          "'Annahme / Adoption',145,0,0,'u','[2]','[]',2)")
        self.conn.commit()

    def test_items_in_the_window(self):
        got = ch_ed.canton_items(self.conn, "2026-10-06", "2026-10-13", {})
        kinds = {it["key"]: it["kind"] for it in got}
        self.assertEqual(kinds, {"zh/376/2026": "new", "be/2026.GRPARL.151": "moved",
                                 "vd/26_POS_9": "new", "be/v/1": "vote"})
        vote = [it for it in got if it["key"] == "be/v/1"][0]
        self.assertIn("145 for, 0 against", " ".join(vote["lines"]))
        moved = [it for it in got if it["key"] == "be/2026.GRPARL.151"][0]
        self.assertIn("French title", " ".join(moved["lines"]))

    def test_outside_the_window(self):
        self.assertEqual(ch_ed.canton_items(self.conn, "2026-10-13", "2026-10-20", {}), [])

    def test_the_section_and_its_coverage(self):
        (heading, intro, items, cover), = ch_ed.cantons(self.conn, "2026-10-06", "2026-10-13", {})
        self.assertEqual(heading, "Cantons")
        self.assertEqual(len(items), 4)
        text = " ".join(cover)
        self.assertIn("Kantonsrat Zürich 13 Oct", text)
        self.assertIn("robots.txt disallows /api/", text)
        self.assertIs(ch_ed.COUNTRY.extra_sections, ch_ed.cantons)

    def test_a_store_without_cantonal_rows(self):
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        (_, _, items, cover), = ch_ed.cantons(conn, "2026-10-06", "2026-10-13", {})
        self.assertEqual(items, [])
        self.assertIn("none yet", cover[0])

    def test_open_data_items_link_their_dataset_and_show_members_votes(self):
        self.conn.execute(ACT, ("bs/26.5228", "bs", "Anzug", "26.5228", "Anzug 26.5228",
                                "Ermöglichung von anonymen Geburten", None, "2026-06-24",
                                "Grosser Rat, Sitzung vom 09.10.2026: Überweisung", "2026-10-09", 0,
                                "Andrea Strahm", None, "https://grosserrat.bs.ch/?gnr=26.5228", 0, 0,
                                "[1]", "[]", 2, "2026-10-13", "2026-10-13"))
        self.conn.execute("UPDATE ch_canton_acts SET source_url=? WHERE act_key='bs/26.5228'",
                          ("https://data.bs.ch/explore/dataset/100311/?refine.signatur_ges=26.5228",))
        self.conn.execute("INSERT INTO ch_canton_divisions (vote_key, canton, act_key, date, subject, "
                          "yes, no, abstain, url, areas, matched_terms, tier, source_url, counts_from) "
                          "VALUES ('bs/v/9609','bs','bs/26.5228','2026-10-09','Abstimmung',2,1,0,'u',"
                          "'[1]','[]',2,'https://data.bs.ch/explore/dataset/100186/','published')")
        self.conn.executemany("INSERT INTO ch_canton_votes VALUES ('bs/v/9609',?,?,?,?)",
                              [("A B", "1", "SP", "Ja"), ("C D", "2", "SP", "Nein"),
                               ("E F", "3", "SP", "Ja"), ("G H", "4", "SVP", "Nein")])
        self.conn.execute("INSERT INTO ch_canton_divisions (vote_key, canton, act_key, date, subject, "
                          "result, url, areas, matched_terms, tier, source_url, counts_from) VALUES "
                          "('tg/v/x','tg',NULL,'2026-10-09','Wahl zwischen Anträgen','Stimmen je Antrag "
                          "(gezählt): Antrag GFK 70, Antrag Wyss 46','u','[1]','[]',2,"
                          "'https://data.tg.ch/explore/dataset/sk-stat-136/','tallied')")
        self.conn.commit()
        got = {it["key"]: it for it in ch_ed.canton_items(self.conn, "2026-10-06", "2026-10-13", {})}
        act = " ".join(got["bs/26.5228"]["lines"])
        self.assertIn("Source: [data.bs.ch](https://data.bs.ch/explore/dataset/100311/"
                      "?refine.signatur_ges=26.5228) (CC BY 4.0", act)
        vote = " ".join(got["bs/v/9609"]["lines"])
        self.assertIn("2 for, 1 against", vote)
        self.assertIn("By Fraktion", vote)
        self.assertIn("SP 2-1", vote)
        self.assertIn("4 member positions stored. Against their group's majority: C D (SP)", vote)
        self.assertIn("Source: [data.bs.ch](https://data.bs.ch/explore/dataset/100186/)", vote)
        self.assertEqual(len(got["bs/v/9609"]["positions"]), 4)
        tg = " ".join(got["tg/v/x"]["lines"])
        self.assertIn("Antrag GFK 70, Antrag Wyss 46 (tallied from the members' votes; data.tg.ch "
                      "publishes no totals)", tg)
        self.assertIn("Source: [data.tg.ch]", tg)
        (_, intro, _items, cover), = ch_ed.cantons(self.conn, "2026-10-06", "2026-10-13", {})
        text = " ".join(cover)
        for url in ("https://data.bs.ch/explore/dataset/100311/", "https://data.bs.ch/explore/dataset/100186/",
                    "https://data.tg.ch/explore/dataset/sk-stat-140/",
                    "https://data.tg.ch/explore/dataset/sk-stat-136/"):
            self.assertIn(url, text)
        self.assertIn("written permission", text)
        self.assertIn("CC BY 4.0", text)

    def test_watched_by_key(self):
        got = ch_ed.canton_items(self.conn, "2026-10-06", "2026-10-13", {"vd/26_POS_9": {}})
        self.assertTrue([it for it in got if it["key"] == "vd/26_POS_9"][0]["watched"])


if __name__ == "__main__":
    unittest.main()
