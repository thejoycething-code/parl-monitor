"""Belgium's federal Chamber: members, dossiers, sittings, recorded votes
(tools/be_rollcalls.py). No network: real pages saved on 9 October 2026 under
tests/fixtures/be/, plus small synthetic records for the variants they lack."""

import datetime as dt
import gzip
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import be_store, db  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "be")
TODAY = "2026-10-09"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ber = _load("be_rollcalls")


def fixture(name):
    with gzip.open(os.path.join(FIX, name)) as fh:
        return fh.read()


def text(name):
    return ber.decode(fixture(name))


# A record in the 2024 layout (sittings 1-15): the annex heads each list
# French first and prints the counts French first; vote 2 is counted, not
# named; vote 3 was annulled and taken again as vote 4.
SYNTHETIC_2024 = """<html><body>
<p>Séance plénière du Jeudi 14 novembre 2024 Après-midi</p>
<h2>05 Wetsontwerp houdende diverse bepalingen inzake gezondheid (216/1-4)</h2>
<h2>05 Projet de loi portant des dispositions diverses en matière de santé (216/1-4)</h2>
<p>Stemming over amendement nr. 3 van Sofie Merckx op artikel 2. (216/4)</p>
<p>Vote sur l'amendement n° 3 de Sofie Merckx à l'article 2. (216/4)</p>
<p>(Stemming/vote 1)</p><p>Ja 2 Oui Nee 1 Non Onthoudingen 0 Abstentions Totaal 3 Total</p>
<p>Bijgevolg is het amendement verworpen.</p><p>En conséquence, l'amendement est rejeté.</p>
<h2>06 Geheel van het wetsontwerp houdende diverse bepalingen inzake gezondheid (216/4)</h2>
<h2>06 Ensemble du projet de loi portant des dispositions diverses en matière de santé (216/4)</h2>
<p>(Stemming/vote 2)</p><p>Ja 3 Oui Nee 0 Non Onthoudingen 0 Abstentions Totaal 3 Total</p>
<p>En conséquence, la Chambre adopte le projet de loi.</p>
<h2>07 Moties ingediend tot besluit van de interpellatie van de heer Kurt Moons</h2>
<h2>07 Motions déposées en conclusion de l'interpellation de M. Kurt Moons</h2>
<p>(Stemming/ vote 3 )</p><p>Ja 1 Oui Nee 1 Non Onthoudingen 1 Abstentions Totaal 3 Total</p>
<p>( Stemming nr. 3 is geannuleerd .) (Le vote n° 3 est annulé.)</p>
<p>(Stemming/vote 4)</p><p>Ja 2 Oui Nee 1 Non Onthoudingen 0 Abstentions Totaal 3 Total</p>
<p>De eenvoudige motie is aangenomen.</p><p>La motion pure et simple est adoptée.</p>
<p>DETAIL VAN DE NAAMSTEMMINGEN DETAIL DES VOTES NOMINATIFS</p>
<p>Vote nominatif - Naamstemming: 1</p><p>Oui 2 Ja</p><p>Aerts Staf, Van der Donckt
Wim</p><p>Non 1 Nee</p><p>Merckx Sofie</p><p>Abstentions 0 Onthoudingen</p>
<p>Comptage électronique &#8211; Elektronische telling: 2</p><p>Oui 3 Ja</p><p>Non 0 Nee</p>
<p>Abstentions 0 Onthoudingen</p>
<p>Vote nominatif - Naamstemming: 3</p><p>Oui 1 Ja</p><p>Aerts Staf</p><p>Non 1 Nee</p>
<p>Merckx Sofie</p><p>Abstentions 1 Onthoudingen</p><p>Van der Donckt Wim</p>
<p>Vote nominatif - Naamstemming: 4</p><p>Oui 2 Ja</p><p>Aerts Staf , Van der Donckt Wim</p>
<p>Non 1 Nee</p><p>Mertens Unknownmember</p><p>Abstentions 0 Onthoudingen</p>
</body></html>""".encode("cp1252")


class SittingTests(unittest.TestCase):
    def test_the_euthanasia_leave_votes_of_8_october_2026(self):
        p = ber.parse_sitting(fixture("criv_56_143.html.gz"), 56, 143)
        self.assertEqual(p["date"], "2026-10-08")
        self.assertEqual(p["problems"], [])
        self.assertEqual([d["division_key"] for d in p["divisions"]],
                         ["56/143/{0}".format(n) for n in range(1, 6)])
        amend, whole = p["divisions"][3], p["divisions"][4]
        # Keyed on the document number in the heading, never the title.
        self.assertEqual((amend["dossier_key"], whole["dossier_key"]), ("56/1338", "56/1338"))
        self.assertEqual((amend["yes"], amend["no"], amend["abstain"]), (55, 75, 5))
        self.assertEqual(amend["outcome"], "rejected")
        self.assertIn("amendement nr. 20 van Caroline Désir", amend["subjects"][0][0])
        self.assertEqual(amend["doc_refs"], ["1338/1-9", "1338/9"])
        self.assertEqual((whole["yes"], whole["no"], whole["abstain"]), (134, 0, 1))
        self.assertEqual(whole["outcome"], "adopted")
        self.assertTrue(whole["heading_nl"].startswith("Geheel van het wetsvoorstel"))
        self.assertTrue(whole["heading_fr"].startswith("Ensemble de la proposition de loi"))
        self.assertEqual(len(amend["positions"]), 135)
        pos = dict(amend["positions"])
        self.assertEqual(pos["Désir Caroline"], "yes")
        self.assertEqual(pos["Van der Donckt Wim"], "no")       # a name the HTML splits across lines
        self.assertEqual([n for n, v in whole["positions"] if v == "abstain"],
                         ["Dermagne Pierre-Yves"])

    def test_a_motion_has_no_dossier_and_its_result_is_read(self):
        motion = ber.parse_sitting(fixture("criv_56_143.html.gz"), 56, 143)["divisions"][0]
        self.assertIsNone(motion["dossier_key"])
        self.assertEqual(motion["result_fr"], "La motion pure et simple est adoptée.")
        self.assertEqual(motion["outcome"], "adopted")

    def test_one_result_applied_to_several_questions_is_one_division(self):
        p = ber.parse_sitting(fixture("criv_56_140.html.gz"), 56, 140)
        self.assertEqual(len(p["divisions"]), 7)
        two = p["divisions"][1]
        self.assertEqual(len(two["subjects"]), 5)
        self.assertEqual(two["dossier_key"], "56/1593")
        self.assertEqual((two["yes"], two["no"], two["abstain"]), (64, 78, 2))

    def test_a_name_list_the_record_withholds_is_a_problem_not_a_mismatch(self):
        p = ber.parse_sitting(fixture("criv_56_140.html.gz"), 56, 140)
        four = p["divisions"][3]
        self.assertEqual(four["positions"], [])
        self.assertEqual((four["yes"], four["no"], four["abstain"]), (49, 78, 17))
        self.assertEqual(len(p["problems"]), 1)
        self.assertIn("vote 4", p["problems"][0])
        self.assertIn("technical", p["problems"][0])

    def test_the_2024_layout_counted_votes_and_annulled_votes(self):
        p = ber.parse_sitting(SYNTHETIC_2024, 56, 12)
        self.assertEqual(p["date"], "2024-11-14")
        self.assertEqual(p["problems"], [])
        one, two, three, four = p["divisions"]
        self.assertEqual(one["positions"], [("Aerts Staf", "yes"), ("Van der Donckt Wim", "yes"),
                                            ("Merckx Sofie", "no")])
        self.assertEqual(one["dossier_key"], "56/216")
        self.assertEqual(one["outcome"], "rejected")
        self.assertEqual((two["kind"], two["positions"], two["yes"]), ("count", [], 3))
        self.assertEqual(three["outcome"], "annulled")
        self.assertEqual(four["outcome"], "adopted")
        self.assertIn(("Aerts Staf", "yes"), four["positions"])  # "Aerts Staf ," trimmed

    def test_a_count_that_disagrees_with_the_names_is_named(self):
        broken = SYNTHETIC_2024.replace(b"<p>Oui 2 Ja</p><p>Aerts Staf, Van der Donckt\nWim</p>",
                                        b"<p>Oui 2 Ja</p><p>Aerts Staf</p>")
        p = ber.parse_sitting(broken, 56, 12)
        self.assertEqual(p["problems"], ["sitting 56/12: vote 1: yes printed 2, 1 names"])

    def test_the_listing_names_every_html_record(self):
        self.assertEqual(ber.parse_sitting_list(text("cri_list.html.gz"), 56), list(range(1, 144)))


class IndexTests(unittest.TestCase):
    def test_members_carry_the_site_keys_as_printed(self):
        current = ber.parse_members(text("members_current.html.gz"))
        self.assertEqual(len(current), 150)
        keys = {k: (n, g) for k, n, g in current}
        self.assertEqual(keys["07757"], ("Aerts Staf", "Ecolo-Groen"))
        self.assertEqual(keys["O1330"], ("Sneppe Dominiek", "VB"))   # a capital O, not a zero
        everyone = ber.parse_members(text("members_56.html.gz"))
        self.assertEqual(len(everyone), 176)
        self.assertTrue(all(g is None for _k, _n, g in everyone))   # that list prints no group

    def test_the_dossier_index(self):
        ranges = ber.parse_ranges(text("listdoc_56.html.gz"))
        self.assertEqual(len(ranges), 19)
        self.assertEqual(ranges[0], (1800, 1800))
        self.assertEqual(ranges[-1], (0, 99))
        rows = dict((n, (t, d)) for n, t, d in ber.parse_range(text("range_56_1300_fr.html.gz")))
        self.assertEqual(len(rows), 100)
        self.assertTrue(rows[1338][0].startswith("Proposition de loi visant à flexibiliser"))
        self.assertEqual(rows[1338][1], "TRAVAIL")

    def test_a_dossier_page(self):
        d = ber.parse_dossier(text("dossier_56_1338.html.gz"))
        self.assertEqual(d["status"], "PENDANT CHAMBRE")
        self.assertEqual(d["deposited"], "2026-02-02")
        self.assertEqual(d["doc_type"], "05 PROPOSITION DE LOI")
        self.assertEqual(d["procedure"], "74 procédure monocamérale")
        self.assertIn("EUTHANASIE", d["eurovoc"])
        self.assertEqual(d["descriptor_fr"], "TRAVAIL")
        self.assertEqual(len(d["authors"]), 10)
        self.assertEqual(d["authors"][0], ["01217", "Florence, Reuter", "MR"])

    def test_recent_documents(self):
        recent = ber.parse_recent(text("recent.html.gz"))
        self.assertIn(1665, recent)
        self.assertIn(1751, recent)


class FakeClient:
    """Serves the fixtures by URL; anything unknown is a FetchError."""

    def __init__(self, extra=None, fail=()):
        self.extra = extra or {}
        self.fail = set(fail)
        self.calls = []

    def _route(self, url):
        self.calls.append(url)
        for key, value in self.extra.items():
            if key in url:
                return value
        if any(f in url for f in self.fail):
            raise FetchError(url, "be-rollcalls", "x", 1, "refused")
        if "dcricra.cfm" in url:
            return fixture("cri_list.html.gz")
        m = re.search(r"/ip(\d+)x\.html", url)
        if m:
            n = int(m.group(1))
            if n == 143:
                return fixture("criv_56_143.html.gz")
            if n == 140:
                return fixture("criv_56_140.html.gz")
            return "<html><body>Séance plénière du Jeudi 1 octobre 2026</body></html>".encode("cp1252")
        if "cvlist54.cfm?legis=" in url:
            return fixture("members_56.html.gz")
        if "cvlist54.cfm" in url:
            return fixture("members_current.html.gz")
        if "ListDocument.cfm" in url:
            return fixture("listdoc_56.html.gz")
        if "ListFromTo.cfm" in url and "from=1300" in url:
            return fixture("range_56_1300_fr.html.gz")
        if "ListFromTo.cfm" in url:
            return b"<html></html>"
        if "LastDocument.cfm" in url:
            return fixture("recent.html.gz")
        if "dossierID=1338" in url:
            return fixture("dossier_56_1338.html.gz")
        if "flwbn.cfm" in url:
            return b"<html><h4><center>Projet de loi.</center></h4></html>"
        raise FetchError(url, "be-rollcalls", "x", 1, "no fixture")

    def get_bytes(self, url, feed, slug, **_kw):
        return self._route(url)

    def get_text(self, url, feed, slug, **_kw):
        return ber.decode(self._route(url))


def store():
    return db.init_db(sqlite3.connect(":memory:"))


WATCH = os.path.join(ROOT, "config", "watchlist-be.yaml")


class StoreTests(unittest.TestCase):
    def _run(self, conn, client=None):
        client = client or FakeClient()
        ber.pull_members(conn, client, TODAY)
        return ber.pull_sittings(conn, client, TODAY, limit=None, log=lambda *_: None)

    def test_schema_is_declared(self):
        for table in be_store.TABLES:
            self.assertIn(table, db.TABLES)

    def test_a_full_pull_stores_votes_resolved_to_member_keys(self):
        conn = store()
        stats = self._run(conn)
        self.assertEqual(stats["listed"], 143)
        self.assertEqual(stats["read"], 143)
        self.assertEqual(stats["divisions"], 12)
        self.assertEqual(stats["unresolved"], set())
        row = conn.execute("SELECT member_key, position, group_seen FROM be_votes WHERE "
                           "division_key='56/143/4' AND member_name='Désir Caroline'").fetchone()
        self.assertEqual(row[1], "yes")
        self.assertEqual(row[2], "PS")
        self.assertTrue(row[0])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM be_votes WHERE member_key IS NULL")
                         .fetchone()[0], 0)
        # The watchlist lends the euthanasia dossier's areas to both its votes, by key.
        areas = dict(conn.execute("SELECT division_key, areas FROM be_divisions"))
        self.assertEqual(json.loads(areas["56/143/5"]), be_store.watch_areas("56/1338")[0])
        self.assertEqual(json.loads(areas["56/143/1"]), [])
        self.assertEqual(conn.execute("SELECT date, divisions FROM be_sittings WHERE "
                                      "sitting_key='56/143'").fetchone(), ("2026-10-08", 5))
        # The withheld name list is a gap, recorded once.
        gaps = [g for (g,) in conn.execute("SELECT detail FROM gaps WHERE feed='be-rollcalls'")]
        self.assertEqual(len(gaps), 1)
        self.assertIn("56/140", gaps[0])

    def test_the_next_run_rereads_only_the_newest_sittings(self):
        conn = store()
        self._run(conn)
        client = FakeClient()
        ber.pull_sittings(conn, client, TODAY, log=lambda *_: None)
        read = [u for u in client.calls if "/ip" in u]
        self.assertEqual(len(read), ber.REREAD_LAST)
        self.assertTrue(read[-1].endswith("ip143x.html"))
        # Re-reading upserts: nothing doubles.
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM be_votes WHERE division_key='56/143/4'")
                         .fetchone()[0], 135)

    def test_an_unknown_name_is_kept_unresolved_and_disclosed(self):
        conn = store()
        ber.pull_members(conn, FakeClient(), TODAY)
        client = FakeClient(extra={"ip012x": SYNTHETIC_2024})
        stats = ber.pull_sittings(conn, client, TODAY, log=lambda *_: None)
        self.assertEqual(stats["unresolved"], {"Mertens Unknownmember"})
        row = conn.execute("SELECT member_key FROM be_votes WHERE member_name='Mertens Unknownmember'"
                           ).fetchone()
        self.assertEqual(row, (None,))
        self.assertTrue(any("Mertens Unknownmember" in g for (g,) in conn.execute(
            "SELECT detail FROM gaps")))

    def test_a_refused_sitting_is_a_gap_and_the_rest_is_stored(self):
        conn = store()
        ber.pull_members(conn, FakeClient(), TODAY)
        stats = ber.pull_sittings(conn, FakeClient(fail=("ip142x",)), TODAY, log=lambda *_: None)
        self.assertEqual(stats["read"], 142)
        self.assertTrue(any("56/142" in g for (g,) in conn.execute("SELECT detail FROM gaps")))

    def test_the_index_and_the_dossier_drain(self):
        conn = store()
        self._run(conn)
        n, gaps = ber.pull_index(conn, FakeClient(), TODAY, log=lambda *_: None)
        self.assertEqual((n, gaps), (100, 0))
        title, areas = conn.execute("SELECT title_fr, areas FROM be_dossiers WHERE "
                                    "dossier_key='56/1338'").fetchone()
        self.assertTrue(title.startswith("Proposition de loi visant à flexibiliser"))
        self.assertTrue(json.loads(areas))
        # Voted and watched dossiers are read first.
        queue = ber.dossier_queue(conn, 56, recent=[1751])
        voted = {int(k.split("/")[1]) for (k,) in conn.execute(
            "SELECT DISTINCT dossier_key FROM be_divisions WHERE dossier_key IS NOT NULL")}
        self.assertTrue(voted <= set(queue[:len(voted) + len(be_store.watchlist())]))
        self.assertLess(queue.index(1338), queue.index(1751))
        read, g, _left = ber.pull_dossiers(conn, FakeClient(), TODAY, cap=10, log=lambda *_: None)
        self.assertEqual((read, g), (10, 0))
        eurovoc, status = conn.execute("SELECT eurovoc, status FROM be_dossiers WHERE "
                                       "dossier_key='56/1338'").fetchone()
        self.assertIn("EUTHANASIE", json.loads(eurovoc))
        self.assertEqual(status, "PENDANT CHAMBRE")

    def test_a_server_that_starts_refusing_ends_the_drain(self):
        conn = store()
        self._run(conn)
        client = FakeClient(fail=("flwbn.cfm",))
        read, g, left = ber.pull_dossiers(conn, client, TODAY, cap=50, log=lambda *_: None)
        self.assertEqual((read, g), (0, ber.DOSSIER_BREAKER))
        self.assertEqual(len([u for u in client.calls if "flwbn.cfm" in u]), ber.DOSSIER_BREAKER)

    def test_reclassify_is_stable_and_offline(self):
        conn = store()
        self._run(conn)
        ber.reclassify(conn, log=lambda *_: None)
        self.assertEqual(ber.reclassify(conn, log=lambda *_: None), (0, 0))


class ResolveTests(unittest.TestCase):
    def test_a_name_printed_without_its_forename_resolves_only_when_unique(self):
        index = {"mutyebele ngoi lydia": ("08151", "PS"), "prevot maxime": ("1", "LE"),
                 "prevot patrick": ("2", "PS")}
        self.assertEqual(ber.resolve(index, "Mutyebele Ngoi"), ("08151", "PS"))
        self.assertEqual(ber.resolve(index, "Prévot Patrick"), ("2", "PS"))
        self.assertIsNone(ber.resolve(index, "Prévot"))          # two candidates: no guess
        self.assertIsNone(ber.resolve(index, "Nobody Here"))

    def test_a_list_printed_forename_first_resolves_through_the_store(self):
        conn = store()
        ber.pull_members(conn, FakeClient(), TODAY)
        index = ber.member_index(conn)
        self.assertEqual(ber.resolve(index, "Wim Van der Donckt"),
                         ber.resolve(index, "Van der Donckt Wim"))
        self.assertIsNotNone(ber.resolve(index, "Katrijn van Riet"))

    def test_a_sitting_whose_only_vote_was_a_count(self):
        raw = ("<p>du jeudi 12 juin 2025</p><p>(Elektronische telling/comptage électronique 1)</p>"
               "<p>En conséquence, le quorum est atteint.</p><p>Ce compte rendu n'a pas d'annexe.</p>"
               "<h1>ELEKTRONISCHE TELLING</h1><h1>COMPTAGE ELECTRONIQUE</h1>"
               "<p>Elektronische telling &#8211; Comptage électronique: 1 Ja 76 Oui</p>").encode("cp1252")
        p = ber.parse_sitting(raw, 56, 48)
        self.assertEqual(p["problems"], [])
        self.assertEqual([(d["kind"], d["yes"]) for d in p["divisions"]], [("count", 76)])


class WatchlistTests(unittest.TestCase):
    def test_every_entry_is_keyed_by_document_number_with_areas_and_a_reason(self):
        import yaml
        with open(WATCH, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        self.assertTrue(raw["dossiers"])
        for key, spec in raw["dossiers"].items():
            self.assertRegex(str(key), r"^\d{2}/\d{1,4}$")
            self.assertTrue(spec.get("areas"), key)
            self.assertTrue(all(1 <= a <= 13 for a in spec["areas"]), key)
            self.assertGreater(len(spec.get("why") or ""), 20, key)


class ScheduleTests(unittest.TestCase):
    """The weekly runs on the Mini first; GitHub is the backup."""

    def setUp(self):
        self.mc = _load("mini_check")
        with open(os.path.join(ROOT, ".github", "workflows", "be-weekly.yml"), encoding="utf-8") as fh:
            self.yml = fh.read()
        self.crons = re.findall(r'cron:\s*"([^"]+)"', self.yml)

    def _decide(self, cron, now, last):
        return self.mc.decide("schedule", cron, last, now, grace_minutes=200)[0]

    def test_one_mini_run_covers_both_slots_summer_and_winter(self):
        utc = dt.timezone.utc
        for last in ("2026-07-11T01:30:05Z", "2026-11-14T02:30:05Z"):    # 02:30 London, BST / GMT
            day_ = last[:10]
            for hour in (2, 4):
                now = dt.datetime.fromisoformat(day_ + "T{0:02d}:35:00".format(hour)).replace(tzinfo=utc)
                self.assertFalse(self._decide("30 {0} * * 6".format(hour), now, last), (last, hour))

    def test_last_weeks_mini_run_does_not_cover_this_week(self):
        now = dt.datetime(2026, 10, 17, 2, 35, tzinfo=dt.timezone.utc)
        self.assertTrue(self._decide("30 2 * * 6", now, "2026-10-10T01:30:05Z"))

    def test_the_slots_collide_with_no_other_workflow(self):
        import glob
        self.assertEqual(self.crons, ["30 2 * * 6", "30 4 * * 6"])
        others = set()
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            if path.endswith("be-weekly.yml"):
                continue
            with open(path, encoding="utf-8") as fh:
                others |= set(re.findall(r'^\s*-\s*cron:\s*"([^"]+)"', fh.read(), re.M))
        self.assertFalse(set(self.crons) & others)

    def test_the_gate_and_the_plist_agree(self):
        self.assertIn("job: BE_WEEKLY", self.yml)
        self.assertIn("grace-minutes: 200", self.yml)
        with open(os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.be-weekly.plist"),
                  encoding="utf-8") as fh:
            plist = fh.read()
        self.assertIn("<string>be-weekly</string>", plist)
        self.assertIn("<key>Weekday</key><integer>6</integer><key>Hour</key><integer>2</integer><key>Minute</key><integer>30</integer>", plist)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "jobs", "be-weekly.sh")))


if __name__ == "__main__":
    unittest.main()
