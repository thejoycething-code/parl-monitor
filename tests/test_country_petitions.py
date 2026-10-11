"""Petitions and consultations for the country editions (src/petitions.py,
src/petition_sources/, tools/country_petitions.py): each source's parser on
replies saved on 11 October 2026 (tests/fixtures/petitions/), the store and
its snapshots, and the edition's section and Coverage line: the first-run
baseline, a threshold crossed, a closing date, the campaign note."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce  # noqa: E402
from src import db, petitions as P  # noqa: E402
from src.petition_sources import ar, at, be, br, ch, co, fr, it, nl, pl, pt  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "petitions")


def text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def js(name):
    return json.loads(text(name))


class FakeClient:
    """Serves fixtures by URL substring."""

    def __init__(self, routes):
        self.routes = routes
        self.asked = []

    def _find(self, url):
        self.asked.append(url)
        for part, value in self.routes.items():
            if part in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError("unexpected URL " + url)

    def get_text(self, url, feed, slug, **kw):
        return self._find(url)

    def get_json(self, url, feed, slug, **kw):
        return self._find(url)

    def post_json(self, url, body, feed, slug, **kw):
        return self._find(url)


class FranceParsers(unittest.TestCase):
    def test_an_list(self):
        got = fr.parse_list(text("fr_an_list.html"), fr.AN, "an")
        self.assertEqual(len(got), 6)
        first = got[0]
        self.assertEqual(first["item_id"], "an:i-7242")
        self.assertEqual(first["signatures"], 2228)
        self.assertEqual(first["opened"], "2026-10-05")
        self.assertEqual(first["status"], "Enregistrée")
        self.assertIn("affaires culturelles", first["body"])
        self.assertEqual(first["url"], fr.AN + "/initiatives/i-7242")
        self.assertEqual(got[1]["signatures"], 100750)
        self.assertEqual(fr.last_page(text("fr_an_list.html")), 20)

    def test_details(self):
        an = fr.parse_detail(text("fr_an_detail.html"))
        self.assertEqual(an["closes"], "2029-06-19")
        self.assertNotIn("opened", an)
        self.assertTrue(an["text"].startswith("La répression policière"))
        senat = fr.parse_detail(text("fr_senat_detail.html"))
        self.assertEqual((senat["opened"], senat["closes"]), ("2026-09-23", "2027-03-23"))

    def test_fetch_pages_until_last(self):
        page = text("fr_an_list.html")
        client = FakeClient({"assemblee-nationale": page})
        got = fr.SOURCES[0].fetch(client, "2026-10-11")
        self.assertEqual(len(client.asked), 20)          # pages 1..20, from the pager
        self.assertEqual(len(got.entries), 120)
        self.assertFalse(got.gaps)


class AustriaParsers(unittest.TestCase):
    def test_ministerialentwuerfe(self):
        got = at.parse_me(js("at_ministerialentwuerfe.json"), "2026-10-11")
        self.assertEqual(len(got), 10)
        me = got[0]
        self.assertEqual(me["item_id"], "me:XXVIII/ME/142")
        self.assertEqual(me["kind"], "consultation")
        self.assertEqual((me["opened"], me["closes"]), ("2026-10-07", "2026-11-12"))
        self.assertIn("Landesverteidigung", me["body"])
        self.assertIn("Begutachtung läuft", me["status"])

    def test_participations(self):
        got = at.parse_participations(js("at_participations.json"))
        self.assertEqual(len(got), 44)                   # 20 BI + 24 PET, no ME
        bi = [e for e in got if e["item_id"] == "parl:XXVIII/BI/7"][0]
        self.assertEqual(bi["signatures"], 975)
        self.assertEqual(bi["kind"], "initiative")
        self.assertFalse(bi["title"].endswith("(7/BI)"))

    def test_volksbegehren(self):
        got = at.parse_volksbegehren(text("at_volksbegehren_registered.html"))
        self.assertGreater(len(got), 30)
        self.assertEqual(got[0]["opened"], "2025-01-22")
        self.assertEqual(got[0]["thresholds"][0][0], 8969)


class SwitzerlandParsers(unittest.TestCase):
    def test_consultations(self):
        got = ch.parse_consultations(js("ch_vernehmlassungen_running.json"))
        self.assertTrue(got)
        self.assertEqual(got[0]["item_id"], "vl:proj/2026/43/cons_1")
        self.assertEqual(got[0]["closes"], "2026-10-12")

    def test_petitions(self):
        got = ch.parse_petitions(js("ch_petitions.json"))
        self.assertTrue(got)
        self.assertTrue(got[0]["item_id"].startswith("pet:26."))
        self.assertTrue(got[0]["opened"].startswith("2026-"))
        self.assertIn("AffairId=", got[0]["url"])
        # the OData list form ({"d": [...]}) too
        self.assertEqual(len(ch.parse_petitions({"d": js("ch_petitions.json")["d"]["results"]})),
                         len(got))

    def test_initiatives_open_only(self):
        got = ch.parse_initiatives(js("ch_volksinitiativen_bbl.json"), "2026-10-11")
        names = [e["title"] for e in got]
        self.assertIn("Für die digitale Sicherheit der Schweiz", names)
        # an initiative with an ending notice is not collecting
        self.assertNotIn("Für bewilligungsfreie Solaranlagen", names)
        e = [x for x in got if x["title"] == "Für die digitale Sicherheit der Schweiz"][0]
        self.assertEqual((e["opened"], e["closes"]), ("2026-06-02", "2027-12-02"))


class OtherParsers(unittest.TestCase):
    T = "2026-10-11"

    def test_italy(self):
        got = it.parse_firme(js("it_firmereferendum_iniziative.json"), self.T)
        e = [x for x in got if x["item_id"] == "firme:7700001"][0]
        self.assertEqual((e["signatures"], e["closes"]), (21763, "2027-03-30"))
        self.assertEqual(e["thresholds"][0][0], 50000)
        procs = it.parse_processes(js("it_partecipa_processes.json"), self.T)
        self.assertEqual(len(procs), 3)
        self.assertTrue(all(p["closes"] >= self.T for p in procs))

    def test_portugal(self):
        got = pt.parse_petitions(js("pt_ar_peticoes.json"))
        self.assertTrue(got)
        self.assertFalse([e for e in got if (e["status"] or "").startswith("Concluída")])
        self.assertEqual(got[0]["item_id"], "ar:XVII/236")
        self.assertEqual(got[0]["signatures"], 114)

    def test_poland(self):
        got = pl.parse_bills(js("pl_sejm_bills.json"), self.T)
        cons = [e for e in got if e["source"] == "konsultacje"]
        self.assertTrue(cons)
        self.assertEqual(cons[0]["closes"], "2026-11-01")
        self.assertIn("RPW%2F30028%2F2026", cons[0]["url"])

    def test_belgium(self):
        rows = be.parse_list(js("be_chamber_initiatives.json"))
        dates = be.parse_dates(js("be_chamber_initiative_dates.json"))
        got = be.entries(rows, dates, self.T)
        first = [e for e in got if e["item_id"] == "chambre:i-1428"][0]
        self.assertEqual(first["closes"], "2028-10-04")
        self.assertFalse(first["title"].startswith("56_"))
        self.assertEqual(first["summary"], "Wijziging maatregel pensioenwetgeving")
        self.assertIn("i1428: initiative(id:1428)", be.q_dates(["1428"]))

    def test_netherlands(self):
        got = nl.parse(js("nl_tk_petitie_activiteit.json"))
        self.assertEqual(got[0]["item_id"], "tk:2026A06505")
        self.assertEqual(got[0]["opened"], "2026-11-24")

    def test_brazil(self):
        ideas = br.parse_ideas(text("br_ecidadania_ideias.html"))
        self.assertEqual((ideas[0]["item_id"], ideas[0]["signatures"]), ("ideia:223676", 13067))
        self.assertEqual(br.last_page(text("br_ecidadania_ideias.html")), 57)
        idea = br.parse_idea(text("br_ecidadania_ideia_detail.html"))
        self.assertEqual((idea["closes"], idea["signatures"]), ("2027-01-30", 9114))
        bills = br.parse_bills(text("br_ecidadania_consultas.html"))
        self.assertEqual((bills[0]["yes_count"], bills[0]["no_count"]), (716923, 1040877))
        self.assertEqual(bills[0]["signatures"], 716923 + 1040877)
        self.assertEqual(bills[0]["refs"], ["PL 5064/2023"])
        procs = br.parse_processes(js("br_brasilparticipativo_processes.json"), self.T)
        self.assertTrue(procs)
        self.assertTrue(all(P._days(p["opened"], p["closes"]) <= br.MAX_SPAN_DAYS
                            for p in procs if p["opened"]))

    def test_colombia_and_argentina(self):
        got = co.parse(js("co_sucop_procesos.json"), self.T)
        e = [x for x in got if x["item_id"] == "sucop:PN-2026-33765"][0]
        self.assertEqual((e["opened"], e["closes"], e["body"]), ("2026-10-09", "2026-10-14",
                                                                  "mintransporte"))
        self.assertEqual(co.bogota_date("2026-10-15T04:59:59Z"), "2026-10-14")
        got = ar.parse(js("ar_consultapublica_forums.json"), self.T)
        self.assertTrue(got)
        self.assertEqual(got[0]["closes"], "2026-10-03")

    def test_every_country_has_taxonomies(self):
        for cc in P.countries():
            self.assertTrue(P.taxonomies(cc), cc)


def store_db():
    path = os.path.join(tempfile.mkdtemp(), "t.db")
    conn = db.init_db(db.connect(path))
    conn.row_factory = sqlite3.Row
    return conn


TAX_FREE = []          # classification is exercised by the live run; here areas are set


def seeded(conn, today, entries, src_code="an"):
    src = [s for s in fr.SOURCES if s.code == src_code][0]
    P.store(conn, "fr", entries, today, src)
    P.record_run(conn, "fr", src_code, today, len(entries), len(entries), 0, None)


def e(pid, sigs, areas=(1,), opened="2026-01-01", closes=None, kind="petition", src="an"):
    x = P.entry(src, pid, "Pétition " + pid, kind=kind, signatures=sigs, opened=opened,
                closes=closes, status="Enregistrée", url="https://x/" + pid)
    x.update(areas=list(areas), matched_terms=["avortement"], tier=1 if areas else None,
             watch_keys=[])
    return x


class EditionItems(unittest.TestCase):
    def test_baseline_threshold_and_closing(self):
        conn = store_db()
        # First run on 4 October: everything is baseline.
        seeded(conn, "2026-10-04", [e("i-1", 90000), e("i-2", 10), e("i-3", 50, areas=())])
        self.assertEqual(P.edition_items(conn, "fr", "2026-09-27", "2026-10-04", {}), [])
        # Second run: i-1 crosses 100,000; i-4 is new; i-5 is new and closes soon.
        seeded(conn, "2026-10-11", [e("i-1", 101000), e("i-2", 11), e("i-3", 60, areas=()),
                                    e("i-4", 5, opened="2026-10-09"),
                                    e("i-5", 60000, closes="2026-10-20")])
        got = {it["key"]: it for it in P.edition_items(conn, "fr", "2026-10-04", "2026-10-11", {})}
        self.assertEqual(set(got), {"an:i-1", "an:i-4", "an:i-5"})   # not i-2 (quiet), i-3 (off ground)
        self.assertIn("passed 100,000 signatures", got["an:i-1"]["takeaway"])
        self.assertTrue(any("+11,000 since" in ln for ln in got["an:i-1"]["lines"]))
        self.assertTrue(any(ln.startswith("Threshold passed: 100,000") for ln in got["an:i-1"]["lines"]))
        self.assertIn("new in this edition", got["an:i-4"]["takeaway"])
        self.assertEqual(got["an:i-4"]["date"], "2026-10-09")
        notes = [ln for ln in got["an:i-5"]["lines"] if ln.startswith("For campaigns")]
        self.assertEqual(len(notes), 1)
        self.assertIn("60% of the way to 100,000", notes[0])
        self.assertIn("closes in 9 days", notes[0])
        self.assertEqual(got["an:i-5"]["kind"], "petition")
        lines = P.coverage_lines(conn, "fr", "2026-10-04", "2026-10-11")
        self.assertEqual(len(lines), 1)
        self.assertIn("Assemblée nationale e-petitions: read 11 October 2026, 5 listed", lines[0])

    def test_no_crossing_without_an_earlier_count(self):
        conn = store_db()
        # First run: a petition already past 100,000 is baseline, not a crossing.
        seeded(conn, "2026-10-11", [e("i-1", 150000, opened="2026-01-01")])
        self.assertEqual(P.edition_items(conn, "fr", "2026-09-11", "2026-10-11", {}), [])

    def test_surge_without_threshold(self):
        conn = store_db()
        seeded(conn, "2026-10-04", [e("i-7", 20000, kind="public_vote")])
        seeded(conn, "2026-10-11", [e("i-7", 35000, kind="public_vote")])
        got = P.edition_items(conn, "fr", "2026-10-04", "2026-10-11", {})
        self.assertEqual(len(got), 1)
        self.assertIn("+15,000 votes in the window", got[0]["takeaway"])

    def test_prev_signatures_and_snapshots(self):
        conn = store_db()
        seeded(conn, "2026-10-04", [e("i-1", 10)])
        seeded(conn, "2026-10-11", [e("i-1", 25)])
        r = conn.execute("SELECT signatures, prev_signatures, first_seen FROM country_petitions").fetchone()
        self.assertEqual(tuple(r), (25, 10, "2026-10-04"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM country_petition_snapshots").fetchone()[0], 2)

    def test_watched_off_ground_item_shows(self):
        conn = store_db()
        seeded(conn, "2026-10-04", [])
        seeded(conn, "2026-10-11", [e("i-9", 3, areas=(), opened="2026-10-10")])
        got = P.edition_items(conn, "fr", "2026-10-04", "2026-10-11", {"i-9": {"why": "test"}})
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["watched"])

    def test_consultation_campaign_note(self):
        r = {"closes": "2026-11-30", "kind": "consultation"}
        self.assertIn("still taking responses", P.campaign_note(r, "2026-10-11", None, []))
        self.assertIsNone(P.campaign_note({"closes": "2026-10-01", "kind": "consultation"},
                                          "2026-10-11", None, []))

    def test_edition_section_renders(self):
        conn = store_db()
        seeded(conn, "2026-10-04", [])
        seeded(conn, "2026-10-11", [e("i-4", 5, opened="2026-10-09")])
        md = ce.render(conn, ce.adapter("fr"), "2026-10-11", since="2026-10-04", sample=True,
                       directory=tempfile.mkdtemp())
        self.assertIn("## Petitions and consultations", md)
        self.assertIn("Petitions and consultations: Assemblée nationale e-petitions", md)
        self.assertNotIn("—", md)


class Collect(unittest.TestCase):
    def test_collect_with_detail_and_gap(self):
        conn = store_db()

        class Mod:
            SOURCES = (P.Source(code="an", name="AN", kind="petition",
                                fetch=lambda c, t, log=print: P.fetched(
                                    fr.parse_list(text("fr_an_list.html"), fr.AN, "an")),
                                detail=lambda c, x, log=print: fr.parse_detail(
                                    text("fr_an_detail.html")), detail_all=True,
                                thresholds=fr.AN_THRESHOLDS),
                       P.Source(code="senat", name="Sénat", kind="petition",
                                fetch=lambda c, t, log=print: P.fetched([], gaps=["down"])))
        listed, ground, gaps = P.collect(conn, "fr", None, "2026-10-11", mod=Mod,
                                         log=lambda *a: None, detail_limit=2)
        self.assertEqual((listed, gaps), (6, 1))
        read = conn.execute("SELECT COUNT(*) FROM country_petitions WHERE detail_read IS NOT NULL"
                            ).fetchone()[0]
        self.assertEqual(read, 2)
        th = json.loads(conn.execute("SELECT thresholds FROM country_petitions LIMIT 1").fetchone()[0])
        self.assertEqual(th[0][0], 100000)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM country_petition_runs").fetchone()[0], 1)


class WeeklySteps(unittest.TestCase):
    def test_each_country_runs_the_step_before_its_edition(self):
        for cc in P.countries():
            with open(os.path.join(ROOT, "jobs", "{0}-weekly.sh".format(cc))) as fh:
                job = fh.read()
            step = job.find("python3 tools/country_petitions.py {0} ".format(cc))
            self.assertGreater(step, 0, cc)
            edition = job.find("python3 tools/{0}_monitor.py".format(cc))
            self.assertTrue(edition < 0 or step < edition, cc)
            self.assertIn("tools/country_petitions.py {0} --reclassify".format(cc), job)

    def test_latam_edition_reads_colombia(self):
        from src import latam
        self.assertIn("co", latam.PETITIONS)
        self.assertIn("petition", latam.KINDS)


if __name__ == "__main__":
    unittest.main()
