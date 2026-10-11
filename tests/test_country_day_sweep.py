"""The daily sweep of new items for the new country editions
(src/country_day_sweep.py, src/day_sweep_sources.py, and its step in
tools/country_vote_briefs.py --daily; 11 October 2026).

No network. The readers are driven with the collectors' own fixtures
(tests/fixtures/<cc>/) and small payloads in the sources' shapes; the rules
with a fake adapter, as tests/test_country_vote_briefs.py does.
"""

import argparse
import gzip
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_day_sweep as sweep  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src import country_vote_brief as cvb  # noqa: E402
from src import day_sweep_sources as sources  # noqa: E402
from src import db, noise, vote_brief  # noqa: E402
from src.http import FetchError  # noqa: E402
import country_vote_briefs as tool  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")
TODAY = "2026-10-09"
SINCE = "2026-10-06"


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _fix(*parts):
    path = os.path.join(FIX, *parts)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return fh.read()


class FakeClient:
    """Answers by URL substring, first match wins; anything else is a 404."""

    def __init__(self, routes):
        self.routes = list(routes)
        self.calls = []

    def _find(self, url):
        for needle, answer in self.routes:
            if needle in url:
                return answer(url) if callable(answer) else answer
        raise FetchError(url, "test", "x", 1, "404")

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.calls.append((url, archive))
        got = self._find(url)
        return json.loads(got) if isinstance(got, bytes) else got

    def get_bytes(self, url, feed, slug, timeout=None, first_bytes=None, archive=True,
                  headers=None):
        self.calls.append((url, archive))
        got = self._find(url)
        return got if isinstance(got, bytes) else json.dumps(got).encode("utf-8")

    def get_text(self, url, feed, slug, timeout=None, archive=True, **kw):
        return self.get_bytes(url, feed, slug, archive=archive).decode("utf-8")

    def post_json(self, url, body, feed, slug, headers=None, timeout=None):
        self.calls.append((url, body))
        got = self._find(url + " " + body)
        return json.loads(got) if isinstance(got, bytes) else got

    def _archive(self, raw, feed, slug):
        self.archived = getattr(self, "archived", []) + [(feed, slug, len(raw))]
        return os.path.join(ROOT, "data", "raw", "x", "{0}_{1}.json.gz".format(feed, slug))


def scratch():
    conn = db.init_db(db.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def fake_country(items, cc="xx"):
    return ce.Country(cc=cc, name="Testland", chamber="Diet", language="Testish",
                      taxonomies=(("taxonomy-nl.yaml", "nl"),), items=lambda *a: list(items),
                      flag=":flag-xx:")


def new(key, date="2026-10-08", title=None, tier=1, watched=False, kind="new", areas=(1,),
        cc="xx"):
    """Titles differ by key: the edition collapses items of one kind and title."""
    return ce.item(cc, kind, key, date, title or "Wetsvoorstel abortus " + key, list(areas),
                   tier, watched,
                   url="https://example.org/" + key, takeaway="Bill " + key)


class NoAgenda(sources.Reader):
    AGENDA = False


class Base(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        self.out = os.path.join(self.tmp, "briefs")
        self.ledgers = os.path.join(self.tmp, "ledgers")
        self.editions = os.path.join(self.tmp, "editions")
        for d in (self.cfg, self.editions):
            os.makedirs(d)
        self.items = []

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def run_pass(self, today=TODAY, skip=(), record=True):
        with mock.patch.object(ce, "adapter", lambda cc: fake_country(self.items, cc)), \
                mock.patch.dict(sources.READERS, {"xx": NoAgenda}):
            return sweep.run(sqlite3.connect(":memory:"), ["xx"], SINCE, today, today=today,
                             out_dir=self.out, record=record, directory=self.ledgers,
                             config_dir=self.cfg, skip_keys=skip, generated="2026-10-09T22:00",
                             log=lambda *a: None, editions_dir=self.editions)


class RuleTests(Base):
    def nz(self):
        return ce.noise_for(fake_country([]))

    def test_watched_or_tier_one_with_evidence(self):
        nz = self.nz()
        self.assertTrue(sweep.qualifies(new("a", tier=2, watched=True), nz, self.cfg))
        self.assertTrue(sweep.qualifies(new("b", tier=1), nz, self.cfg))
        self.assertFalse(sweep.qualifies(new("c", tier=2), nz, self.cfg))
        self.assertFalse(sweep.qualifies(new("d", kind="moved"), nz, self.cfg))
        self.assertFalse(sweep.qualifies(new("e", kind="vote"), nz, self.cfg))
        self.assertTrue(sweep.qualifies(new("f", kind="question"), nz, self.cfg))
        self.assertTrue(sweep.qualifies(new("g", kind="agenda"), nz, self.cfg))

    def test_judge_gate_as_the_vote_briefs(self):
        nz = self.nz()
        self.assertFalse(sweep.qualifies(dict(new("a"), judge=1), nz, self.cfg))
        self.assertTrue(sweep.qualifies(dict(new("b"), judge=2), nz, self.cfg))
        self.assertTrue(sweep.qualifies(dict(new("c", tier=2, watched=True), judge=0), nz,
                                        self.cfg))

    def test_minimum_evidence_from_the_noise_rules(self):
        with open(os.path.join(self.cfg, "edition-noise-xx.yaml"), "w") as fh:
            fh.write("alert:\n  title_tier1: true\n")
        noise.load_yaml.__globals__["_FILES"].clear()
        nz = self.nz()
        self.assertTrue(sweep.qualifies(new("a", title="Wetsvoorstel abortus"), nz, self.cfg))
        self.assertFalse(sweep.qualifies(new("b", title="Wetsvoorstel 36001"), nz, self.cfg))

    def test_muted_items_never_alert(self):
        with open(os.path.join(self.cfg, "edition-mute-xx.yaml"), "w") as fh:
            fh.write("mute_in_edition: true\nitems: ['xx|new|m1']\npatterns: []\n")
        noise.load_yaml.__globals__["_FILES"].clear()
        self.assertFalse(sweep.qualifies(new("m1", watched=True), self.nz(), self.cfg))

    def test_agenda_id_survives_renumbering_and_names_the_day(self):
        a = dict(new("P1", kind="agenda", title="Embryowet"), watch_key="36001")
        b = dict(new("P9", kind="agenda", title="Embryowet (vervolg)"), watch_key="36001")
        c = dict(b, date="2026-10-15")
        self.assertEqual(sweep.sweep_id(a), sweep.sweep_id(b))
        self.assertNotEqual(sweep.sweep_id(a), sweep.sweep_id(c))
        self.assertEqual(sweep.sweep_id(new("Q1", kind="question")), "xx|question|Q1")


class RunTests(Base):
    def test_first_pass_seeds_silently_then_only_the_new(self):
        self.items = [new("a"), new("b", kind="question")]
        text, blocks, path = self.run_pass()
        self.assertIsNone(text)
        self.assertIsNone(path)
        self.assertEqual(sweep.load("xx", self.ledgers)["seeded"], TODAY)
        self.items = [new("a"), new("b", kind="question"), new("c"), new("d", tier=2)]
        text, blocks, path = self.run_pass()
        self.assertEqual([it["key"] for it, _r in blocks[0][1]], ["c"])
        self.assertIn("Testland: 1 new on our ground", text)
        self.assertIn("_Wetsvoorstel abortus c_", text)
        self.assertTrue(os.path.exists(path))
        text, blocks, path = self.run_pass()         # never twice
        self.assertIsNone(text)

    def test_nothing_recorded_without_record(self):
        self.items = [new("a")]
        self.run_pass(record=False)
        self.assertFalse(os.path.exists(sweep.ledger_path("xx", self.ledgers)))

    def test_what_an_edition_or_a_vote_brief_carries_is_left_out(self):
        self.run_pass()
        with open(os.path.join(self.editions, "xx-monitor-2026-10-05.md"), "w") as fh:
            fh.write("# Edition\n\n- **New item** · e1 · 4 Oct · abortion · tier 1\n")
        with open(os.path.join(self.editions, "xx-monitor-2026-10-02.md"), "w") as fh:
            fh.write("# SAMPLE EDITION\n\n- **New item** · s1 · 1 Oct · abortion · tier 1\n")
        with open(os.path.join(self.editions, "xx-monitor-2026-08-01.md"), "w") as fh:
            fh.write("# Edition\n\n- **New item** · old1 · 1 Aug · abortion · tier 1\n")
        self.items = [new("e1"), new("s1"), new("old1"), new("v1"),
                      dict(new("v2"), watch_key="bill-7"), new("n1")]
        text, blocks, _p = self.run_pass(skip={"v1", "bill-7"})
        self.assertEqual(sorted(it["key"] for it, _r in blocks[0][1]), ["n1", "old1", "s1"])
        sent = sweep.load("xx", self.ledgers)["sent"]
        self.assertIn("xx|new|e1", sent)                  # recorded, so never later either

    def test_the_dm_shows_at_most_twenty_and_points_to_the_rest(self):
        self.run_pass()
        self.items = [new("k{0:02d}".format(i)) for i in range(25)]
        text, blocks, path = self.run_pass()
        self.assertEqual(text.count("• *New*"), sweep.MAX_DM_ITEMS)
        self.assertIn("_and 5 more_", text)
        self.assertEqual(open(path, encoding="utf-8").read().count("- **New**"), 25)
        self.assertIsNone(vote_brief.VERDICT_WORDS.search(text))
        self.assertNotIn("—", text)

    def test_one_country_failing_costs_the_others_nothing(self):
        def boom(*a, **k):
            raise ValueError("bad payload")
        with mock.patch.object(sweep, "candidates", boom):
            text, blocks, path = sweep.run(sqlite3.connect(":memory:"), ["xx"], SINCE, TODAY,
                                           directory=self.ledgers, log=lambda *a: None)
        self.assertIsNone(text)


class LatamTests(Base):
    """Latam countries go through the Latam alerts' reader, rule and ledger,
    both ways (gaps-day-sweep, 11 October 2026)."""

    def latam_item(self, key, kind="new", tier=1, watched=False, title=None):
        from src import latam
        return latam.item("co", kind, key, "2026-10-08",
                          title or "Proyecto de ley sobre aborto " + key, [1], tier, watched,
                          status="Radicado", url="https://example.org/" + key)

    def run_latam(self, items, record=True):
        self.latam_dir = os.path.join(self.tmp, "latam-alerts")
        with mock.patch("src.latam.country_items", lambda *a, **k: list(items)):
            return sweep.run(sqlite3.connect(":memory:"), ["co"], SINCE, TODAY, today=TODAY,
                             out_dir=self.out, record=record, directory=self.ledgers,
                             config_dir=self.cfg, generated="2026-10-09T22:00",
                             log=lambda *a: None, editions_dir=self.editions,
                             latam_dir=self.latam_dir)

    def test_latam_rule_and_both_ledgers(self):
        import latam_alerts
        a, b = self.latam_item("100/26C"), self.latam_item("101/26C")
        moved = self.latam_item("102/26C", kind="moved", watched=True)
        self.assertIsNone(self.run_latam([a])[0])                 # first pass seeds silently
        self.assertEqual(latam_alerts.load("co", self.latam_dir)["sent"], {})
        led = latam_alerts.load("co", self.latam_dir)
        led["sent"]["co|new|101/26C"] = "2026-10-08"               # the weekly sent it
        latam_alerts.save(led, TODAY, self.latam_dir)
        c = self.latam_item("103/26C", tier=2)                    # tier 2, not watched
        d = self.latam_item("104/26C", tier=2, watched=True)
        text, blocks, _p = self.run_latam([a, b, moved, c, d])
        self.assertEqual([it["key"] for it, _r in blocks[0][1]], ["104/26C"])
        self.assertIn("Colombia", text)
        self.assertIn("New bill", text)
        sent = latam_alerts.load("co", self.latam_dir)["sent"]
        self.assertIn("co|new|104/26C", sent)                     # the weekly step skips it
        self.assertIsNone(self.run_latam([a, b, d])[0])           # never twice

    def test_latam_ledger_untouched_without_record(self):
        import latam_alerts
        sweep.save(dict(sweep.load("co", self.ledgers), seeded="x"), TODAY, self.ledgers)
        text, _b, _p = self.run_latam([self.latam_item("9/26C", watched=True)], record=False)
        self.assertIn("9/26C", text)
        self.assertFalse(os.path.exists(latam_alerts.ledger_path("co", self.latam_dir)))


class CollectTests(Base):
    def test_gated_once_a_day_and_failing_readers(self):
        class Bad(sources.Reader):
            AGENDA = False

            @staticmethod
            def collect(*a, **k):
                raise FetchError("u", "f", "s", 1, "500")

        class Heavy(sources.Reader):
            AGENDA = False
            ONCE_A_DAY = True
            ARCHIVE_ON_HIT = True

            @staticmethod
            def collect(conn, client, since, today, log=print):
                client.get_bytes("https://example.org/big.zip", "big", "big-zip")
                return 1

        class Later(sources.Reader):
            ACTIVE_FROM = "2026-12-23"

        log = []
        client = FakeClient([("big.zip", b"PK-zip")])
        with mock.patch.dict(sources.READERS, {"aa": Bad, "bb": Heavy, "cc": Later}):
            read, held = sweep.collect(scratch(), client, SINCE, TODAY, ["aa", "bb", "cc"],
                                       log=log.append, directory=self.ledgers)
            self.assertEqual(read, ["bb"])
            self.assertEqual(client.calls, [("https://example.org/big.zip", False)])
            self.assertTrue(any("[gap] aa" in ln for ln in log))
            self.assertTrue(any("cc: not swept before 2026-12-23" in ln for ln in log))
            sources.archive_hit(client, held["bb"].fetched, log=log.append)
            self.assertEqual(client.archived, [("big", "big-zip", 6)])
            sweep.save(dict(sweep.load("bb", self.ledgers), read=TODAY), TODAY, self.ledgers)
            read, _h = sweep.collect(scratch(), client, SINCE, TODAY, ["bb"], log=log.append,
                                     directory=self.ledgers)
            self.assertEqual(read, [])


class ReaderTests(unittest.TestCase):
    """Each reader over its collector's own fixtures: what it stores, and that
    the edition's reader turns it into the sweep's items."""

    def items(self, conn, cc, since="2026-01-01", until=TODAY):
        _c, wide = sweep.sweep_country(cc, type("R", (sources.READERS[cc],), {"AGENDA": False}))
        return [it for it in wide.items(conn, since, until, ce.watchlist_of(_c))
                if it["kind"] in sweep.SWEEP_KINDS]

    def test_nl_motions_are_the_sweeps_own_items(self):
        zaken = {"value": [
            {"Id": "g1", "Nummer": "2026Z90001", "Soort": "Motie",
             "Onderwerp": "Motie van het lid Test over het verruimen van abortus tot 24 weken",
             "Titel": "Zorg", "GestartOp": "2026-10-08T00:00:00+02:00",
             "Kabinetsappreciatie": "Ontraden",
             "Kamerstukdossier": [{"Nummer": 36800, "Toevoeging": "XVI", "Titel": "Begroting VWS"}]},
            {"Id": "g2", "Nummer": "2026Z90002", "Soort": "Motie", "Onderwerp": "Motie over dijken",
             "GestartOp": "2026-10-08T00:00:00+02:00", "Kamerstukdossier": []},
            {"Id": "g3", "Nummer": "2026Z80000", "Soort": "Motie", "Onderwerp": "Motie abortus",
             "GestartOp": "2026-10-01T00:00:00+02:00", "Kamerstukdossier": []}]}
        client = FakeClient([("Motie%27", zaken), ("Zaak?", {"value": []})])
        conn = scratch()
        sources.NL.collect(conn, client, SINCE, TODAY, log=lambda *a: None)
        got = {r[0] for r in conn.execute("SELECT zaak_nummer FROM nl_zaken")}
        self.assertEqual(got, {"2026Z90001", "2026Z90002"})        # started after since
        items = self.items(conn, "nl")
        self.assertEqual([it["key"] for it in items], ["2026Z90001"])
        self.assertEqual(items[0]["kind"], "new")
        self.assertIn("the government's advice: Ontraden", items[0]["takeaway"])

    def test_pl_newest_processes_by_start_date(self):
        procs = [{"number": "3207", "term": 10, "processStartDate": "2026-10-08",
                  "title": "Poselski projekt ustawy o zmianie ustawy o planowaniu rodziny, "
                           "ochronie płodu ludzkiego i warunkach dopuszczalności przerywania "
                           "ciąży", "documentType": "projekt ustawy",
                  "changeDate": "2026-10-08T10:00:00"},
                 {"number": "3100", "term": 10, "processStartDate": "2026-09-01",
                  "title": "Projekt ustawy o aborcji"}]
        client = FakeClient([("processes?limit=150&sort_by=-number", procs),
                             ("interpellations", []), ("writtenQuestions", [])])
        conn = scratch()
        sources.PL.collect(conn, client, SINCE, TODAY, log=lambda *a: None)
        self.assertEqual([r[0] for r in conn.execute("SELECT process_key FROM pl_processes")],
                         ["10/3207"])
        items = self.items(conn, "pl", since=SINCE)
        self.assertEqual([(it["key"], it["kind"]) for it in items], [("10/3207", "new")])

    def test_ch_businesses_submitted_in_the_window(self):
        client = FakeClient([("'DE'", _fix("ch", "business_de.json.gz")),
                             ("'FR'", _fix("ch", "business_fr.json.gz"))])
        conn = scratch()
        n = sources.CH.collect(conn, client, "2026-09-01", TODAY, log=lambda *a: None)
        self.assertGreater(n, 0)
        self.assertIn("SubmissionDate%20gt%20datetime'2026-09-01T23:59:59'", client.calls[0][0])
        self.assertTrue(all(i["kind"] in ("new", "question")
                            for i in self.items(conn, "ch", since="2026-09-01")))

    def test_br_bills_presented_in_the_window(self):
        props = {"dados": [{"id": 2647999, "siglaTipo": "PL", "numero": 5600, "ano": 2026,
                            "ementa": "Altera o Código Penal para tipificar o aborto "
                                      "realizado após vinte e duas semanas de gestação.",
                            "dataApresentacao": "2026-10-08T11:00"}], "links": []}
        client = FakeClient([("siglaTipo=RIC", {"dados": []}), ("siglaTipo=PL", props)])
        conn = scratch()
        sources.BR.collect(conn, client, SINCE, TODAY, log=lambda *a: None)
        self.assertIn("dataApresentacaoInicio=2026-10-07", client.calls[0][0])
        items = self.items(conn, "br", since=SINCE)
        self.assertEqual([(it["key"], it["kind"]) for it in items], [("PL 5600/2026", "new")])

    def test_it_bills_presented_from_the_senate_sparql(self):
        client = FakeClient([("classificazione", _fix("it", "senato_teseo_56640.json")),
                             ("sparql", _fix("it", "senato_bills_56640.json"))])
        conn = scratch()
        n = sources.IT.collect(conn, client, "2023-01-01", TODAY, log=lambda *a: None)
        self.assertGreater(n, 0)
        self.assertIn("dataPresentazione", client.calls[0][0])
        self.assertEqual(n, conn.execute("SELECT COUNT(*) FROM it_bills").fetchone()[0])

    def test_at_items_received_in_the_window(self):
        client = FakeClient([('"NR"', _fix("at", "items-nr.json")),
                             ('"BR"', _fix("at", "items-br.json"))])
        conn = scratch()
        sources.AT.collect(conn, client, "2026-09-01", TODAY, log=lambda *a: None)
        self.assertIn('"DATUM_VON": ["2026-09-02", "2026-10-09"]', client.calls[0][1])
        keys = [r[0] for r in conn.execute("SELECT item_key FROM at_items")]
        self.assertIn("XXVIII/A/1026", keys)
        self.assertNotIn("XXVIII/I/525", keys)                     # received in June
        items = self.items(conn, "at", since="2026-09-01")
        self.assertIn(("XXVIII/A/1026", "new"), [(i["key"], i["kind"]) for i in items])

    def test_spain_waits_for_the_new_legislature_and_france_reads_its_agenda_only(self):
        self.assertEqual(sources.ES.ACTIVE_FROM, "2026-12-23")
        self.assertTrue(sources.FR.ONCE_A_DAY and sources.FR.ARCHIVE_ON_HIT)
        self.assertEqual(sources.FR.collect(None, None, SINCE, TODAY), 0)
        self.assertEqual(set(sources.SWEEP), set(sources.READERS))


class DailyJobTests(Base):
    def args(self, send=True):
        return argparse.Namespace(out=self.out, send=send, no_seed=False)

    def run_daily(self, vote_entries, sweep_text, send=True):
        sent = []

        def fake_cvb_run(*a, entries_out=None, **k):
            entries_out.extend(vote_entries)
            return len(vote_entries)

        blocks = [("xx", [(new("a"), "watched")])] if sweep_text else []
        with mock.patch.object(cvb, "run", fake_cvb_run), \
                mock.patch.object(sweep, "collect", lambda *a, **k: (["xx"], {})), \
                mock.patch.object(sweep, "run", lambda *a, **k: (sweep_text, blocks, None)):
            tool.daily_with_sweep(scratch(), FakeClient([]), [], SINCE, TODAY,
                                  self.args(send), sender=lambda s, t: sent.append(
                                      (s.get("slack_dm_user_id"), t)) or {"ok": True},
                                  secrets={"slack_dm_user_id": "U0SOMEONE"}, log=lambda *a: None)
        return sent

    def test_one_dm_for_votes_and_new_items_to_chris_alone(self):
        sent = self.run_daily(["VOTE ENTRY"], "SWEEP BLOCK")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0], cvb.CHRIS)
        self.assertTrue(sent[0][1].startswith(":mag: *Daily watch: 1 vote brief, 1 new item"))
        self.assertLess(sent[0][1].index("VOTE ENTRY"), sent[0][1].index("SWEEP BLOCK"))

    def test_nothing_when_nothing(self):
        self.assertEqual(self.run_daily([], None), [])

    def test_no_send_without_send(self):
        self.assertEqual(self.run_daily(["VOTE ENTRY"], None, send=False), [])

    def test_the_sweep_is_a_step_of_the_one_daily_job(self):
        job = _read("jobs", "vote-briefs-daily.sh")
        self.assertIn("python3 tools/country_vote_briefs.py", job)
        self.assertIn("sweep", job.lower())
        self.assertFalse(os.path.exists(os.path.join(ROOT, "jobs", "day-sweep-countries.sh")))
        self.assertIn("src/country_day_sweep.py", _read("docs", "mac-mini.md"))


if __name__ == "__main__":
    unittest.main()
