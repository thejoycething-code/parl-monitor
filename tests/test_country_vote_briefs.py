"""Same-day vote briefs for the new country editions and the Latam monitor
(src/country_vote_brief.py, src/vote_brief_sources.py,
tools/country_vote_briefs.py; handover item 1, 10 October 2026).

No network. The daily readers are driven with the collectors' own fixtures
(tests/fixtures/<cc>/, real payloads) and two Câmara API payloads recorded on
10 October 2026 (tests/fixtures/vote_briefs/); the store path with small
stores built here.
"""

import datetime
import glob
import gzip
import json
import os
import plistlib
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_edition as ce  # noqa: E402
from src import country_vote_brief as cvb  # noqa: E402
from src import db, noise, vote_brief  # noqa: E402
from src import vote_brief_sources as vs  # noqa: E402
from src.http import FetchError  # noqa: E402
import country_vote_briefs as tool  # noqa: E402
import latam_alerts  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")
TODAY = "2026-10-09"
SINCE = "2026-09-30"


def _json(*parts):
    path = os.path.join(FIX, *parts)
    with (gzip.open(path, "rt", encoding="utf-8") if path.endswith(".gz")
          else open(path, encoding="utf-8")) as fh:
        return json.load(fh)


def _bytes(*parts):
    with open(os.path.join(FIX, *parts), "rb") as fh:
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
        return self._find(url)

    def get_bytes(self, url, feed, slug, timeout=None, first_bytes=None, archive=True):
        self.calls.append((url, archive))
        got = self._find(url)
        return got if isinstance(got, bytes) else json.dumps(got).encode("utf-8")


def fake_country(items, cc="xx"):
    return ce.Country(cc=cc, name="Testland", chamber="Diet", language="Testish",
                      taxonomies=(("taxonomy-nl.yaml", "nl"),), items=lambda *a: list(items),
                      flag=":flag-xx:")


def vote(key, date="2026-10-08", title="Stemming", tier=None, watched=False, group=None,
         group_title=None, final=False, rebels=None, note=None, positions=None, areas=(1,),
         cc="xx"):
    return ce.vote(cc, key, date, title, list(areas), tier, watched,
                   [ce.tally_line(80, 60, 1, "Aangenomen", "roll call")], group=group,
                   group_title=group_title, final=final, rebels=rebels, rebels_note=note,
                   positions=positions, url="https://example.org/" + key)


class Base(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        self.out = os.path.join(self.tmp, "briefs")
        self.ledgers = os.path.join(self.tmp, "ledgers")
        os.makedirs(self.cfg)
        self.sent = []
        self.items = []

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def sender(self, secrets, text):
        self.sent.append((secrets.get("slack_dm_user_id"), text))
        return {"ok": True, "message_ts": "1"}

    def run_pass(self, today=TODAY, since=SINCE, dm=True):
        with mock.patch.object(ce, "adapter", lambda cc: fake_country(self.items, cc)):
            return cvb.run(sqlite3.connect(":memory:"), ["xx"], since, today, today=today,
                           out_dir=self.out, dm=dm, secrets={"slack_dm_user_id": "U0SOMEONE"},
                           sender=self.sender, directory=self.ledgers, config_dir=self.cfg,
                           generated="2026-10-09T22:00", log=lambda *a: None)

    def briefs(self):
        return sorted(glob.glob(os.path.join(self.out, "*.md")))


class LedgerTests(Base):
    def test_first_pass_seeds_then_each_vote_is_briefed_once(self):
        self.items = [vote("v1", watched=True)]
        self.assertEqual(self.run_pass(), 0)                  # seeded: nothing briefed
        self.assertEqual(self.sent, [])
        with open(os.path.join(self.ledgers, "xx.json")) as fh:
            self.assertEqual(json.load(fh)["seeded"], TODAY)
        self.items.append(vote("v2", date="2026-10-09", watched=True, title="Motie abortus"))
        self.assertEqual(self.run_pass(), 1)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][0], "U05LJP0BT61")      # Chris alone, whatever secrets say
        self.assertIn("Motie abortus", self.sent[0][1])
        self.assertNotIn("v1", self.sent[0][1])
        self.assertEqual(self.run_pass(), 0)                  # de-duplicated
        self.assertEqual(len(self.sent), 1)

    def test_without_send_nothing_is_recorded(self):
        self.items = [vote("v1", watched=True)]
        self.run_pass()
        self.items.append(vote("v2", watched=True))
        self.run_pass(dm=False)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.run_pass(), 1)                  # still owed

    def test_a_bill_keyed_vote_is_told_apart_by_date_and_title(self):
        a = vote("PL 1/2026", title="Second reading")
        b = vote("PL 1/2026", title="Final vote")
        c = vote("PL 1/2026", date="2026-10-01", title="Second reading")
        self.assertEqual(len({cvb.vote_id(a), cvb.vote_id(b), cvb.vote_id(c)}), 3)

    def test_a_vote_waits_for_its_positions_then_goes_without(self):
        self.items = []
        self.run_pass()                                       # seed
        self.items = [vote("v9", date="2026-10-09", watched=True)]
        with mock.patch.object(cvb, "POSITIONS_LATER", ("xx",)):
            self.assertEqual(self.run_pass(today="2026-10-09"), 0)
            self.assertEqual(self.sent, [])
            with open(os.path.join(self.ledgers, "xx.json")) as fh:
                self.assertIn("held", json.load(fh))
            self.assertEqual(self.run_pass(today="2026-10-11"), 1)
        self.assertIn("Member positions not published yet", self.sent[0][1])


class QualifyTests(Base):
    def nz(self):
        with open(os.path.join(self.cfg, "edition-noise-xx.yaml"), "w") as fh:
            fh.write("alert:\n  title_tier1: true\n  distinct_terms: 2\n")
        return ce.noise_for(fake_country([]))

    def test_watched_and_tier1_with_evidence_only(self):
        nz = self.nz()
        self.assertTrue(cvb.qualifies(vote("a", watched=True), nz, self.cfg))
        self.assertTrue(cvb.qualifies(vote("b", tier=1, title="Motie over abortus"), nz, self.cfg))
        self.assertFalse(cvb.qualifies(vote("c", tier=2, title="Motie over abortus"), nz, self.cfg))
        item = ce.item("xx", "new", "d", "2026-10-08", "Wetsvoorstel abortus", [1], 1)
        self.assertFalse(cvb.qualifies(item, nz, self.cfg))  # votes only

    def test_the_bill_title_lends_the_evidence(self):
        nz = self.nz()
        bare = vote("e", title="Votazione finale", group="b1", group_title="Wetsvoorstel abortus")
        self.assertTrue(cvb.qualifies(bare, nz, self.cfg))
        self.assertEqual(cvb.why(bare, nz, self.cfg), "tier-1 term in the title")
        dull = vote("f", title="Votazione finale", group="b2", group_title="Wet op de visserij")
        self.assertFalse(cvb.qualifies(dull, nz, self.cfg))

    def test_the_session_judge_gates_tier1(self):
        nz = self.nz()
        low = dict(vote("g", tier=1, title="Motie over abortus"), judge=1)
        high = dict(vote("h", tier=1, title="Motie over abortus"), judge=2)
        watched = dict(vote("i", watched=True), judge=0)
        self.assertFalse(cvb.qualifies(low, nz, self.cfg))
        self.assertTrue(cvb.qualifies(high, nz, self.cfg))
        self.assertTrue(cvb.qualifies(watched, nz, self.cfg))

    def test_muted_and_procedural_votes_never_brief(self):
        with open(os.path.join(self.cfg, "edition-mute-xx.yaml"), "w") as fh:
            fh.write("mute_in_edition: true\nitems: ['xx|vote|m1']\npatterns: []\n")
        with open(os.path.join(self.cfg, "edition-noise-xx.yaml"), "w") as fh:
            fh.write("procedural_votes: ['^ordre du jour']\n")
        self.items = [vote("m0", watched=False, tier=1, title="Motie abortus")]
        self.run_pass()
        self.items = [vote("m1", tier=1, title="Motie abortus"),
                      vote("m2", tier=1, title="Ordre du jour abortus"),
                      vote("m3", tier=1, title="Motie euthanasie")]
        self.run_pass()
        self.assertEqual(len(self.briefs()), 1)
        self.assertIn("euthanasie", open(self.briefs()[0], encoding="utf-8").read())


class RenderTests(Base):
    def test_a_bill_and_its_votes_are_one_brief_decisive_first(self):
        self.run_pass()
        self.items = [vote("a1", watched=True, group="bill-9", group_title="Embryowet",
                           title="Amendement 3"),
                      vote("a2", watched=True, group="bill-9", group_title="Embryowet",
                           title="Wetsvoorstel", final=True),
                      vote("a3", watched=True, date="2026-10-02", group="bill-9",
                           group_title="Embryowet", title="Amendement 1")]
        self.assertEqual(self.run_pass(), 2)                  # one per bill per day
        text = open([b for b in self.briefs() if "2026-10-08" in b][0], encoding="utf-8").read()
        self.assertLess(text.index("## Decisive vote: Wetsvoorstel"), text.index("Amendement 3"))
        self.assertIn("2 recorded votes on our ground", text)
        self.assertEqual(len(self.sent), 1)                   # one DM for the run
        self.assertIn("2 vote briefs", self.sent[0][1])

    def test_every_rebel_is_named_and_independents_are_not(self):
        rebels = ["Member {0} (Party A)".format(i) for i in range(15)] + ["Loner (INDEP)",
                                                                          "Solo (no club)"]
        positions = [("Member {0}".format(i), "Party A", "nein") for i in range(15)] + \
            [("Other {0}".format(i), "Party A", "ja") for i in range(40)]
        self.run_pass()
        self.items = [vote("r1", watched=True, rebels=rebels, positions=positions)]
        self.run_pass()
        text = open(self.briefs()[0], encoding="utf-8").read()
        self.assertIn("Broke from their group (15)", text)
        self.assertIn("Member 14 (Party A)", text)            # never truncated in the brief
        self.assertNotIn("Loner", text)
        self.assertNotIn("Solo", text)
        self.assertIn("| Party A | 40 | 15 |", text)          # the record's own words, by frequency
        dm = self.sent[0][1]
        self.assertIn("and 3 more (in the brief)", dm)        # twelve in the DM

    def test_why_nobody_is_named(self):
        self.run_pass()
        self.items = [vote("x6", watched=True, note=cvb.X6),
                      vote("x5", watched=True, rebels=[], note="Klub votes, DERIVED (X5)."),
                      vote("ok", watched=True, rebels=[])]
        self.run_pass()
        text = " ".join(open(b, encoding="utf-8").read() for b in self.briefs())
        self.assertIn("No member is named against their party until party history is sourced (X6).",
                      text)
        self.assertIn("Broke from their group: none named. Klub votes, DERIVED (X5).", text)
        self.assertIn("every member voted with their group's majority (abstentions aside)", text)

    def test_no_verdict_no_em_dash_and_only_the_readings_status(self):
        stance = os.path.join(self.tmp, "xx_stance.yaml")
        with open(stance, "w") as fh:
            fh.write("divisions:\n  - key: 'v5'\n    draft: true\n    yea: 2\n    nay: -2\n"
                     "    why_yea: 'CitizenGO supports this'\n")
        self.run_pass()
        self.items = [vote("v5", watched=True, title="Motion — the bill was defeated")]
        with mock.patch.object(cvb, "stance_path", lambda cc: stance):
            self.run_pass()
        text = open(self.briefs()[0], encoding="utf-8").read() + self.sent[0][1]
        self.assertNotIn("—", text)
        self.assertIn("reading awaiting sign-off", text)
        self.assertNotIn("CitizenGO supports", text)
        ours = text.replace("the bill was defeated", "")       # the record's own words aside
        self.assertIsNone(vote_brief.VERDICT_WORDS.search(ours))

    def test_the_new_stance_files_are_read_by_the_stores_division_key(self):
        stance = os.path.join(self.tmp, "xx_stance.yaml")
        with open(stance, "w") as fh:
            fh.write("divisions:\n  - key: 'besluit-1'\n    status: draft\n    yea: 2\n    nay: -2\n"
                     "  - key: 'besluit-2'\n    status: confirmed\n    yea: 2\n    nay: -2\n"
                     "  - key: 'besluit-3'\n    status: needs_reading\n")
        def say(key):
            with mock.patch.object(cvb, "stance_path", lambda cc: stance):
                return cvb.stance_status("xx", key)
        a = ce.vote("xx", "2026Z1", "2026-10-08", "Motie", [1], 1, True, [], division_key="besluit-1")
        self.assertEqual(cvb.stance_key(a), "besluit-1")
        self.assertIn("awaiting sign-off", say(cvb.stance_key(a)))
        self.assertIn("awaiting sign-off", say("besluit-2"))      # confirmed needs a name and a date
        self.assertIn("to read first", say("besluit-3"))
        b = ce.vote("xx", "2026Z1", "2026-10-08", "Motie", [1], 1, True, [], division_key="2026Z1")
        self.assertNotIn("division_key", b)                          # same as the key: not stored
        self.assertNotEqual(cvb.vote_id(a), cvb.vote_id(b))

    def test_the_dm_is_capped(self):
        self.run_pass()
        self.items = [vote("c{0}".format(i), watched=True) for i in range(11)]
        self.assertEqual(self.run_pass(), 11)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][1].count("Brief: "), cvb.MAX_DM_BRIEFS)
        self.assertIn("and 3 more brief(s)", self.sent[0][1])


# --- the adapters hand over positions and rebels ----------------------------------------

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.row_factory = sqlite3.Row

    def test_poland_hands_over_every_position_and_the_full_rebel_list(self):
        from src.editions import pl
        c = self.conn
        c.execute("INSERT INTO pl_divisions (division_key, term, sitting, number, voted_at, kind, "
                  "title, topic, process_keys, yes, no, abstain, areas, own_areas, tier, positions) "
                  "VALUES ('pl-10-66-1', 10, 66, 1, '2026-10-08T12:00:00', 'ELECTRONIC', 'Pkt. 3', "
                  "'glosowanie nad caloscia projektu', '[\"10/3030\"]', 30, 12, 0, '[1]', '[]', 1, 42)")
        for i in range(30):
            c.execute("INSERT INTO pl_votes VALUES (?,?,?,?,NULL)",
                      ("pl-10-66-1", "10/{0}".format(i), "YES", "PiS" if i < 20 else "KO"))
        for i in range(30, 42):
            c.execute("INSERT INTO pl_votes VALUES (?,?,?,?,NULL)",
                      ("pl-10-66-1", "10/{0}".format(i), "NO", "KO" if i < 41 else "PiS"))
        c.execute("INSERT INTO pl_votes VALUES ('pl-10-66-1','10/99','NO','niez.',NULL)")
        for i in list(range(42)) + [99]:
            c.execute("INSERT INTO pl_members (mp_key, term, mp_id, name) VALUES (?,10,?,?)",
                      ("10/{0}".format(i), i, "Posel {0}".format(i)))
        got = [it for it in pl.items(c, "2026-10-01", TODAY, {}) if it["kind"] == "vote"][0]
        self.assertEqual(len(got["positions"]), 43)
        self.assertEqual(got["rebels"], sorted(["Posel 41 (PiS)"] +
                                               ["Posel {0} (KO)".format(i) for i in range(20, 30)]))
        self.assertIn("Against their group's majority", " ".join(got["lines"]))

    def test_a_dutch_show_of_hands_names_only_who_the_kamer_recorded_apart(self):
        from src.editions import nl
        c = self.conn
        c.execute("INSERT INTO nl_zaken (zaak_nummer, soort, onderwerp, dossiers, dossier_titels, "
                  "own_areas, areas, tier) VALUES ('2026Z1', 'Motie', 'Motie abortus', '[]', '[]', "
                  "'[1]', '[1]', 1)")
        c.execute("INSERT INTO nl_divisions (besluit_id, zaak_nummer, date, stemmingssoort, voor, "
                  "tegen, positions_pending, areas) VALUES ('b1', '2026Z1', '2026-10-06', "
                  "'Met handopsteken', 80, 70, 0, '[1]')")
        rows = [("s1", "fractie", "Groep M", "Tegen", 7, None), ("s2", "lid", "Groep M", "Voor", None, "Jan"),
                ("s3", "fractie", "PVV", "Voor", 25, None)]
        for sid, kind, fr, pos, seats, actor in rows:
            c.execute("INSERT INTO nl_votes (stemming_id, besluit_id, kind, fractie, actor, position, "
                      "zetels) VALUES (?,?,?,?,?,?,?)", (sid, "b1", kind, fr, actor or fr, pos, seats))
        got = [it for it in nl.items(c, "2026-10-01", TODAY, {})][0]
        self.assertEqual(got["rebels"], ["Jan (Groep M)"])
        self.assertIn("DERIVED", got["rebels_note"])

    def test_latam_positions_and_party_history(self):
        c = self.conn
        for name, party, pos in (("A", "PRM", "SI"), ("B", "PRM", "SI"), ("C", "PRM", "NO"),
                                 ("D", "INDEP", "NO"), ("E", "PLD", "NO")):
            c.execute("INSERT INTO do_votes (division_key, member_key, name, party, position) "
                      "VALUES ('cd/1', ?, ?, ?, ?)", ("cd/" + name, name, party, pos))
        it = cvb.drop_independents(cvb.latam_positions(c, "do", {"key": "cd/1", "cc": "do"}))
        self.assertEqual(it["rebels"], ["C (PRM)"])
        self.assertEqual(len(it["positions"]), 5)
        c.execute("INSERT INTO cl_votes VALUES ('camara-1', 'D-1', 'En Contra', 'UDI')")
        it = cvb.latam_positions(c, "cl", {"key": "camara-1", "cc": "cl"})
        self.assertNotIn("rebels", it)
        self.assertEqual(it["rebels_note"], cvb.X6)

    def test_a_vote_the_brief_sent_is_not_alerted_again(self):
        tmp = tempfile.mkdtemp()
        try:
            it = {"cc": "cl", "kind": "vote", "key": "camara-1", "date": "2026-10-08",
                  "title": "Boletín 1"}
            cvb.save(dict(cvb.load("cl", tmp), seeded=TODAY,
                          sent={cvb.vote_id(it): TODAY}), TODAY, tmp)
            with mock.patch.object(latam_alerts, "VOTE_BRIEF_DIR", tmp):
                self.assertTrue(latam_alerts.briefed(it, {}))
                self.assertFalse(latam_alerts.briefed(dict(it, key="camara-2"), {}))
                self.assertFalse(latam_alerts.briefed(dict(it, kind="new"), {}))
        finally:
            shutil.rmtree(tmp)


# --- the daily readers -------------------------------------------------------------------

def scratch():
    conn = db.init_db(sqlite3.connect(":memory:"))
    return conn


def candidates(conn, cc, since, until):
    conn.row_factory = sqlite3.Row
    got = cvb.candidates(conn, cc, since, until)
    conn.row_factory = None
    return got


class DailyReaderTests(unittest.TestCase):
    def test_netherlands_one_query_classified_by_the_collector(self):
        page = _json("nl", "besluiten.json")
        client = FakeClient([("Besluit?", page)])
        conn = scratch()
        n = vs.NL.collect(conn, client, "2026-10-01", TODAY, log=lambda *a: None)
        self.assertEqual(n, conn.execute("SELECT COUNT(*) FROM nl_divisions").fetchone()[0])
        self.assertGreater(n, 0)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(vs.NL.positions(conn, client, TODAY), 0)

    def test_poland_reads_the_sittings_in_the_window_and_the_bills_from_the_store_map(self):
        index = _json("pl", "votings_index_10_trimmed.json")
        sitting = _json("pl", "sitting_10_58.json")
        detail = _json("pl", "vote_10_65_1.json")
        mps = _json("pl", "mp_10_trimmed.json")
        tmp = tempfile.mkdtemp()
        try:
            prints = sorted({n for v in sitting for n in __import__("pl_rollcalls").print_numbers(
                v.get("title"), v.get("topic"), v.get("description"))})
            with open(os.path.join(tmp, "pl-parents.json"), "w") as fh:
                json.dump({"processes": [{"process_key": "10/" + prints[0], "term": 10,
                                          "number": prints[0], "title": "Projekt",
                                          "areas": "[1]", "matched_terms": "[\"aborcj*\"]",
                                          "tier": 1}],
                           "prints": {"10/" + prints[0]: "10/" + prints[0]}}, fh)
            client = FakeClient([("/votings/58/", lambda url: dict(detail, sitting=58)),
                                 ("/votings/58", sitting), ("/votings/6", []),
                                 ("/votings", index), ("/MP", mps)])
            conn = scratch()
            n = vs.PL.collect(conn, client, "2026-05-28", TODAY, log=lambda *a: None, parents_dir=tmp)
            self.assertEqual(n, sum(1 for v in sitting if v["date"][:10] >= "2026-05-28"))
            self.assertFalse(any("/term" == u[-5:] for u, _ in client.calls))   # term from the map
            linked = conn.execute("SELECT COUNT(*) FROM pl_divisions WHERE process_keys LIKE ?",
                                  ('%"10/{0}"%'.format(prints[0]),)).fetchone()[0]
            wl = vs._watch("pl")
            ours = sum(vs._ground(a, *(k in wl for k in json.loads(p or "[]"))) for a, p in
                       conn.execute("SELECT areas, process_keys FROM pl_divisions"))
            self.assertGreater(linked, 0)                     # the store map lends the bill's areas
            self.assertGreaterEqual(ours, linked)            # and own words count too
            got = vs.PL.positions(conn, client, TODAY, log=lambda *a: None)
            self.assertEqual(got, ours)
            asked = [u for u, _ in client.calls if re.search(r"/votings/58/\d+$", u)]
            self.assertEqual(len(asked), ours)                 # only votes on our ground
            conn.execute("UPDATE pl_divisions SET positions=NULL")
            client.calls = []
            one = conn.execute("SELECT division_key FROM pl_divisions LIMIT 1").fetchone()[0]
            self.assertEqual(vs.PL.positions(conn, client, TODAY, log=lambda *a: None,
                                             keys={one}), 1)   # only the votes to brief
        finally:
            shutil.rmtree(tmp)

    def test_poland_with_no_sitting_in_the_window_costs_two_requests(self):
        client = FakeClient([("/votings", _json("pl", "votings_index_10_trimmed.json")),
                             ("/term", _json("pl", "terms.json"))])
        conn = scratch()
        with mock.patch.object(vs, "load_parents", lambda *a, **k: None):
            self.assertEqual(vs.PL.collect(conn, client, "2026-10-09", TODAY, log=lambda *a: None), 0)
        self.assertEqual(len(client.calls), 2)

    def test_switzerland_the_current_sessions_nationalrat_votes(self):
        import ch_rollcalls as chr_
        votes = _json("ch", "nr_votes_5215.json.gz")
        de, fr = _json("ch", "business_de.json.gz"), _json("ch", "business_fr.json.gz")
        voting = _json("ch", "nr_voting_38691.json.gz")
        dates = sorted(chr_.odata_date(r.get("VoteEndWithTimezone")) for r in chr_.rows(votes))
        ms = lambda d: "/Date({0})/".format(int(datetime.datetime.fromisoformat(d).replace(
            tzinfo=datetime.timezone.utc).timestamp() * 1000))
        sessions = {"d": [{"ID": 5215, "SessionName": "Herbstsession 2026", "StartDate": ms(dates[0]),
                           "EndDate": ms(dates[-1]), "Type": 1, "LegislativePeriodNumber": 52}]}
        client = FakeClient([("/Vote?", votes), ("Voting?", voting), ("/Session?", sessions),
                             ("Language+eq+%27FR%27", fr), ("Language%20eq%20'FR'", fr),
                             ("Business", de)])
        conn = scratch()
        n = vs.CH.collect(conn, client, dates[-1], dates[-1], log=lambda *a: None)
        self.assertEqual(n, sum(1 for d in dates if d >= dates[-1]))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ch_divisions WHERE date < ?",
                                      (dates[-1],)).fetchone()[0], 0)
        conn.execute("UPDATE ch_divisions SET areas='[1]' WHERE rowid = (SELECT MIN(rowid) FROM ch_divisions)")
        self.assertEqual(vs.CH.positions(conn, client, dates[-1]), 1)
        self.assertEqual(conn.execute("SELECT counts_from FROM ch_divisions WHERE areas='[1]'").fetchone()[0],
                         "tallied")

    def test_switzerland_out_of_session_reads_one_list(self):
        client = FakeClient([("/Session?", {"d": [{"ID": 5215, "SessionName": "Herbstsession 2026",
                                                  "StartDate": "/Date(1788134400000)/",
                                                  "EndDate": "/Date(1789862400000)/"}]})])
        self.assertEqual(vs.CH.collect(scratch(), client, "2026-10-05", TODAY, log=lambda *a: None), 0)
        self.assertEqual(len(client.calls), 1)

    def test_brazil_the_apis_nominal_votes_their_bills_and_the_senate(self):
        api = _json("vote_briefs", "br_camara_votacoes_2026-09-01.json")
        detail = _json("vote_briefs", "br_camara_votacao_2611313-31.json")
        listed = dict(api, dados=api["dados"] + [
            {"id": "2611313-31", "data": "2026-09-03", "siglaOrgao": "PLEN", "aprovacao": 1,
             "descricao": detail["dados"]["descricao"]}])
        client = FakeClient([("/votacao?", _json("br", "senado_votacao-2026.json")),
                             ("/votacoes?", listed),
                             ("/votacoes/2611313-31/votos", _json("br", "camara_votos_2611313-31.json")),
                             ("/votacoes/2611313-31/orientacoes", {"dados": []}),
                             ("/votos", {"dados": []}), ("/orientacoes", {"dados": []}),
                             ("/votacoes/", detail),
                             ("/proposicoes/2611313", _json("br", "camara_proposicao_2611313.json"))])
        conn = scratch()
        n = vs.BR.collect(conn, client, "2026-09-01", "2026-09-03", log=lambda *a: None)
        cam = conn.execute("SELECT division_key, bill_key, yes, no FROM br_divisions WHERE "
                           "chamber='camara' ORDER BY division_key").fetchall()
        self.assertEqual([r[0] for r in cam], ["camara-2611313-31", "camara-2643915-8",
                                                "camara-2645346-18"])       # nominal only
        self.assertIn(("camara-2611313-31", "PLP 74/2026", 346, 46), cam)
        self.assertGreater(n, 3)                                 # the Senate's too
        self.assertEqual(conn.execute("SELECT keywords IS NOT NULL FROM br_bills WHERE "
                                      "bill_key='PLP 74/2026'").fetchone()[0], 1)
        with mock.patch.object(vs, "_watch", lambda cc: {"PLP 74/2026"}):
            self.assertEqual(vs.BR.positions(conn, client, TODAY), 1)

    def test_brazil_both_count_wordings(self):
        new = vs.camara_nominal({"id": "1-1", "descricao": "Aprovado. Sim: 346; Não: 46; "
                                 "Abstenção: 3; Total: 395.", "aprovacao": 1})
        old = vs.camara_nominal({"id": "1-2", "descricao": 'Rejeitado. Resultado:  18 votos "Sim", '
                                 '19 votos "Não". Quórum de votação: 37 votos.', "aprovacao": 0})
        self.assertEqual((new["yes"], new["no"], new["other"], new["result"]), (346, 46, 3, "approved"))
        self.assertEqual((old["yes"], old["no"], old["result"]), (18, 19, "rejected"))
        self.assertIsNone(vs.camara_nominal({"id": "1-3", "descricao": "Mantido o texto."}))

    def test_italy_senate_votes_with_their_readings_then_positions(self):
        senate = _bytes("it", "senato_votes_232.json")
        bills = json.loads(_bytes("it", "senato_bills_56640.json").decode("utf-8"), strict=False)
        more = json.loads(_bytes("it", "senato_bills_57360.json").decode("utf-8"), strict=False)
        bills["results"]["bindings"] += more["results"]["bindings"]
        client = FakeClient([
            ("MAX%28%3Fn%29", {"results": {"bindings": [{"hi": {"value": "233"}}]}}),
            ("osr%3AVotazione", senate), ("osr%3Aclassificazione", _bytes("it", "senato_teseo_56640.json")),
            ("osr%3ADdl", json.dumps(bills).encode("utf-8")),
            ("osr%3ASenatore", _bytes("it", "senato_senators.json")),
            ("votazione%2F19-232-", _bytes("it", "senato_positions_19-232-24.json")),
            ("votings/?branch=C", {"results": []})])
        conn = scratch()
        n = vs.IT.collect(conn, client, "2024-10-16", "2024-10-16", log=lambda *a: None)
        import it_rollcalls as itr
        rows = [{k: v.get("value") for k, v in b.items()} for b in
                json.loads(senate.decode("utf-8"), strict=False)["results"]["bindings"]]
        self.assertEqual(n, len(itr.parse_senate_votes(rows)))
        surrogacy = conn.execute("SELECT COUNT(*) FROM it_divisions WHERE bill_keys LIKE '%S.824%' "
                                 "AND areas != '[]'").fetchone()[0]
        self.assertEqual(surrogacy, 24)                    # the reading lends its areas
        done = vs.IT.positions(conn, client, "2024-10-17", log=lambda *a: None)
        self.assertEqual(done, conn.execute("SELECT COUNT(*) FROM it_divisions WHERE "
                                            "areas != '[]'").fetchone()[0])

    def test_italy_one_chambers_source_failing_costs_the_other_nothing(self):
        camera = _json("it", "camera_votings_p337.json")
        client = FakeClient([("votings/?branch=C", camera)])   # the Senate answers 404
        said = []
        n = vs.IT.collect(scratch(), client, "2023-07-31", "2023-07-31", log=said.append)
        self.assertEqual(n, sum(1 for r in camera["results"] if r["sitting"]["date"] >= "2023-07-31"))
        self.assertTrue(any("[gap] it: the Senate" in s for s in said))
        with self.assertRaises(ValueError):
            vs.IT.collect(scratch(), FakeClient([]), "2023-07-31", "2023-07-31", log=said.append)

    def test_a_failing_reader_is_a_gap_and_costs_the_others_nothing(self):
        said = []
        broken = FakeClient([])
        with mock.patch.dict(vs.READERS, {"nl": vs.NL, "ch": vs.CH}, clear=True):
            conn, path, read = tool.daily(broken, "2026-10-01", TODAY, countries=("ch", "nl"),
                                          log=said.append, scratch_dir=tempfile.mkdtemp())
        shutil.rmtree(os.path.dirname(path))
        self.assertEqual(read, [])
        self.assertTrue(any(s.startswith("  [gap] nl: the daily reader failed") for s in said))
        self.assertTrue(any(s.startswith("  [gap] ch: the daily reader failed") for s in said))
        self.assertFalse(path.startswith(os.path.join(ROOT, "data")))


# --- wiring ------------------------------------------------------------------------------

def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class WiringTests(unittest.TestCase):
    def test_every_country_with_member_votes_briefs_after_its_collection(self):
        for cc in cvb.COUNTRIES:
            job = _read("jobs", "mx-collect.sh" if cc == "mx" else "{0}-weekly.sh".format(cc))
            self.assertIn("python3 tools/country_vote_briefs.py --country {0} --send".format(cc), job)
            step = job.index("country_vote_briefs.py")
            self.assertLess(job.index("|| rc=$?"), step, cc)       # after the collector
            if "latam_alerts.py --country" in job:
                self.assertLess(step, job.index("python3 tools/latam_alerts.py --country"), cc)

    def test_the_daily_job_is_one_lean_mini_job(self):
        job = _read("jobs", "vote-briefs-daily.sh")
        self.assertIn("# mini_run: no-store", job)
        self.assertIn("python3 tools/country_vote_briefs.py", job)
        self.assertIn("--daily --send", job)
        self.assertIn("python3 tools/raw_state.py --push", job)
        self.assertNotIn("db_state.py", job)
        self.assertIn("vote-briefs-daily", _read("ops", "install_country_jobs.sh"))
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".github", "workflows",
                                                     "vote-briefs-daily.yml")))
        self.assertEqual(set(vs.DAILY), {"nl", "pl", "ch", "br", "it"})

    def test_the_daily_slots_are_clear_of_every_other_mini_job(self):
        def slots(path):
            with open(path, "rb") as fh:
                got = plistlib.load(fh).get("StartCalendarInterval") or []
            got = [got] if isinstance(got, dict) else got
            out = set()
            for s in got:
                days = [s["Weekday"]] if "Weekday" in s else list(range(7))
                for d in days:
                    out.add((d % 7, s.get("Hour"), s.get("Minute")))
            return out
        mine = os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.vote-briefs-daily.plist")
        ours = slots(mine)
        self.assertEqual(len(ours), 10)
        for path in glob.glob(os.path.join(ROOT, "ops", "launchd", "*.plist")):
            if path != mine:
                self.assertFalse(ours & slots(path), os.path.basename(path))

    def test_coverage_names_the_daily_job(self):
        import coverage
        self.assertIn("Daily vote briefs", coverage.ON_DEMAND)
        self.assertIn('GITHUB_WORKFLOW:-Daily vote briefs', _read("jobs", "vote-briefs-daily.sh"))


if __name__ == "__main__":
    unittest.main()
