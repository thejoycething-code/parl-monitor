"""The countdown layout for the country editions (src/country_countdown.py,
16 October 2026): sitting line, big dates, the two tables, key questions,
petitions, consultations, government publications, Reference, the DM, and
the judge's queue reading the forward rows with the watched bill's why-line.
Small stores built here; no network."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import agenda, chamber_store, petitions  # noqa: E402
from src import country_countdown as cc_  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src import edition_judge as ej  # noqa: E402
from src import noise  # noqa: E402

TODAY = "2026-10-17"          # a Saturday: This week runs Sat 17 to Sun 25 October
SINCE = "2026-10-10"
EDITION_SCORES = ("CREATE TABLE edition_scores (item TEXT PRIMARY KEY, cc TEXT NOT NULL, "
                  "score INTEGER NOT NULL, why TEXT, model TEXT, scored_at TEXT)")
WL = {"36390": {"areas": [9, 10], "why": "Wet kind, draagmoederschap en afstamming: a legal "
                                         "regime for surrogacy. Pending."}}


def point(conn, item_id, date, title, body="Plenary", kind="plenary", areas=(1,), refs=(),
          status=None, run="2026-10-16", tier=1):
    conn.execute("INSERT INTO country_agenda (cc, item_id, date, body, kind, title, refs, bill_keys, "
                 "url, status, own_areas, areas, matched_terms, tier, watch_keys, first_seen, last_seen) "
                 "VALUES ('nl',?,?,?,?,?,?,'[]',?,?,?,?,'[]',?,'[]',?,?)",
                 (item_id, date, body, kind, title, json.dumps(list(refs)),
                  "https://example.org/" + item_id, status, json.dumps(list(areas)),
                  json.dumps(list(areas)), tier if areas else None, run, run))


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    agenda.ensure_schema(conn)
    petitions.ensure_schema(conn)
    chamber_store.ensure_schema(conn, ["nl"])
    conn.execute(EDITION_SCORES)
    conn.execute("INSERT INTO country_agenda_runs VALUES ('nl','2026-10-16',9,6,'2026-12-10',"
                 "'2026-10-20',NULL)")
    point(conn, "p1", "2026-10-20", "Stemmingen over de Wet abortus is zorg")
    point(conn, "p2", "2026-10-21", "Debat over euthanasie bij psychisch lijden", areas=(2,))
    point(conn, "p3", "2026-10-22", "Wijziging van Boek 1 (draagmoederschap)", refs=("36390",),
          areas=(), body="vaste commissie voor Justitie en Veiligheid", kind="committee")
    point(conn, "p4", "2026-11-10", "Besloten overleg abortuszorg", status="closed sitting",
          body="vaste commissie voor VWS", kind="committee")
    point(conn, "p5", "2026-11-12", "Rondetafelgesprek transgenderzorg jongeren", areas=(3,),
          body="vaste commissie voor VWS", kind="committee")
    point(conn, "p6", "2026-11-19", "Notaoverleg embryowet", areas=(10,),
          body="vaste commissie voor VWS", kind="committee")
    point(conn, "p7", "2026-12-30", "Too far: past the horizon", areas=(1,))
    point(conn, "p8", "2026-10-23", "Begroting Infrastructuur", areas=())     # not on our ground
    point(conn, "old", "2026-10-21", "From an older run", run="2026-10-09")
    return conn


def score(conn, key, s, why="Why it matters."):
    ej.write(conn, "nl", "nl:agenda:" + key, s, why, TODAY)


def vote_items(conn, since, until, wl):
    return [ce.vote("nl", "2026Z1", "2026-09-30", "Amendement over draagmoederschap", [10], 1,
                    True, [ce.tally_line(80, 60, None, "Aangenomen")], group="36390",
                    watch_key="36390")]


def country(**kw):
    base = dict(cc="nl", name="Netherlands", chamber="Tweede Kamer", language="Dutch",
                taxonomies=(("taxonomy-nl.yaml", "nl"),), items=vote_items,
                watchlist=lambda config_dir=None: dict(WL))
    base.update(kw)
    return ce.Country(**base)


class Base(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        self.eds = os.path.join(self.tmp, "editions")
        os.makedirs(self.cfg)
        os.makedirs(self.eds)
        self.conn = store()

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def render(self, c=None, **kw):
        return ce.render(self.conn, c or country(), TODAY, SINCE, config_dir=self.cfg,
                         directory=self.eds, **kw)


class Layout(Base):
    def test_windows(self):
        ws, we, fs, he = cc_.windows(TODAY)
        self.assertEqual([d.isoformat() for d in (ws, we, fs, he)],
                         ["2026-10-17", "2026-10-25", "2026-10-26", "2026-12-20"])
        ws, we, fs, he = cc_.windows("2026-10-19")         # a Monday: Mon to Sun
        self.assertEqual((we.isoformat(), fs.isoformat()), ("2026-10-25", "2026-10-26"))

    def test_order_of_blocks_and_house_rules(self):
        text = self.render()
        heads = [ln for ln in text.split("\n") if ln.startswith("## ")]
        self.assertEqual(heads[:3], ["## This week · Sat 17 to Sun 25 October",
                                     "## Further afield · Mon 26 October to 20 December",
                                     "## Reference"])
        self.assertIn("| When | Where | What | Issue |", text)
        self.assertIn("| Tue 20 Oct | TWEEDE KAMER |", text)
        for gone in ("Latest votes", "Also announced", "⭐", "★", "## Week ahead", "—"):
            self.assertNotIn(gone, text)
        ref = text.split("## Reference")[1]
        self.assertIn("### Bills we track", ref)
        self.assertIn("### Coverage", ref)
        self.assertNotIn("\n## ", ref)                      # everything under Reference is demoted

    def test_rows_are_the_latest_run_on_our_ground_inside_the_horizon(self):
        text = self.render().split("## Reference")[0]
        self.assertNotIn("Too far", text)
        self.assertNotIn("Begroting Infrastructuur", text)
        self.assertNotIn("From an older run", text)
        self.assertIn("Besloten overleg abortuszorg", text)          # a row, never a big date
        self.assertIn("vaste commissie voor Justitie en Veiligheid", text)
        self.assertIn("*Watched: Wet kind, draagmoederschap en afstamming", text)

    def test_sitting_line_says_only_what_the_agenda_says(self):
        text = self.render()
        self.assertIn("*Sitting this week:* Tweede Kamer sitting (plenary Tue 20, Wed 21 and Fri 23 Oct)",
                      text)
        line, missing = cc_.sitting_line(self.conn, country(), "2026-10-26")
        self.assertIn("Tweede Kamer: no plenary on the published agenda this week", line)
        line, missing = cc_.sitting_line(self.conn, country(cc="hu"), TODAY)
        self.assertIsNone(line)
        self.assertTrue(missing)


class BigDates(Base):
    def test_score_three_rows_nearest_first_at_most_three_never_private(self):
        for k in ("p1", "p2", "p3", "p4", "p5", "p6"):
            score(self.conn, k, 3)
        text = self.render()
        big = text.split("## Big dates")[1].split("## This week")[0]
        self.assertEqual(big.count("> **BIG DATE**"), 3)
        self.assertIn("**Tuesday 20 October** · TWEEDE KAMER", big)
        self.assertNotIn("Besloten overleg", big)                    # closed sitting
        self.assertNotIn("Rondetafelgesprek", big)                   # the fourth
        self.assertIn("**Tue 20 Oct · BIG DATE**", text)             # marked in its row

    def test_context_cites_the_last_vote_on_the_bill(self):
        score(self.conn, "p3", 3)
        text = self.render()
        self.assertIn("*Context:* the last recorded vote on this was on 30 September: "
                      "“Amendement over draagmoederschap”; 80 for, 60 against", text)

    def test_context_falls_back_to_the_judge(self):
        score(self.conn, "p2", 3, "The euthanasia debate the campaign waits for.")
        self.assertIn("*Context:* The euthanasia debate the campaign waits for.", self.render())

    def test_unread_rows_are_never_big_and_zero_leaves(self):
        score(self.conn, "p2", 0)
        text = self.render()
        self.assertNotIn("## Big dates", text)
        self.assertNotIn("euthanasie bij psychisch lijden", text.split("## Reference")[0])
        self.assertIn("1 item the judge scored 0", text)


class Blocks(Base):
    def test_key_questions_cluster_and_rank(self):
        for qid, date, asker, title, tier in (
                ("Q1", "2026-10-12", "Bikker", "Vragen over abortuszorg", 1),
                ("Q2", "2026-10-12", "Bikker", "Vragen over abortuspil", 1),
                ("Q3", "2026-10-14", "Faber", "Vragen over prostitutie", 2),
                ("Q4", "2026-09-01", "Old", "Te oud", 1)):
            self.conn.execute("INSERT INTO nl_questions (question_id, kind, date, title, asker, areas, "
                              "tier) VALUES (?,?,?,?,?,?,?)",
                              (qid, "written", date, title, asker, "[1]" if qid != "Q3" else "[12]", tier))
        text = self.render()
        kq = text.split("## Key questions")[1].split("## Reference")[0]
        self.assertIn("Q1, Q2, Bikker: *Vragen over abortuszorg*; *Vragen over abortuspil*", kq)  # one row
        self.assertNotIn("Faber", kq)                    # tier 2 unread counts 1: not shown
        self.assertNotIn("Te oud", kq)
        ej.write(self.conn, "nl", "nl:question:Q3", 3, "Raises the age for sex work.", TODAY)
        kq = self.render().split("## Key questions")[1]
        self.assertLess(kq.index("Faber"), kq.index("Bikker"))   # judge score first

    def test_petitions_consultations_and_deadline_rows(self):
        rows = (("me:1", "petition", "Stop abortus na 24 weken", None, 4100, "2026-09-01"),
                ("me:2", "petition", "Geannuleerde petitie euthanasie", None, 10, "2026-10-12"),
                ("ic:1", "consultation", "Consultatie embryowet", "2026-11-05", None, "2026-10-12"),
                ("ic:2", "consultation", "Consultatie draagmoederschap", "2027-03-01", None,
                 "2026-10-12"))
        for iid, kind, title, closes, sig, first in rows:
            self.conn.execute("INSERT INTO country_petitions (cc, item_id, source, kind, title, closes, "
                              "signatures, body, areas, first_seen, last_seen, status) "
                              "VALUES ('nl',?,?,?,?,?,?,?,?,?,?,?)",
                              (iid, iid.split(":")[0], kind, title, closes, sig,
                               "Ministerie van VWS", "[1]" if "abortus" in title else "[10]", first,
                               "2026-10-16", "geannuleerd" if "Geannuleerde" in title else "open"))
        text = self.render()
        tables = text.split("## Key questions")[0] if "## Key questions" in text else \
            text.split("## Petitions")[0]
        self.assertIn("| Thu 5 Nov | GOVT | Ministerie van VWS, Consultatie embryowet, consultation closes |", tables)
        pets = text.split("## Petitions")[1].split("## ")[0]
        self.assertIn("Stop abortus na 24 weken", pets)
        self.assertIn("4,100", pets)
        self.assertNotIn("Geannuleerde", pets)
        cons = text.split("## Consultations")[1].split("## ")[0]
        self.assertIn("Consultatie draagmoederschap", cons)
        self.assertNotIn("Consultatie embryowet", cons)                 # a row of the tables
        self.assertIn("1 closing inside the 8 weeks is one of the rows", cons)

    def test_gov_docs_absent_then_present(self):
        text = self.render()
        self.assertIn("Government publications: not collected yet (gov_docs).", text)
        self.conn.execute("CREATE TABLE gov_docs (cc TEXT, doc_id TEXT, title TEXT, doc_type TEXT, "
                          "body TEXT, published TEXT, closing_date TEXT, url TEXT, areas TEXT, "
                          "matched_terms TEXT, first_seen TEXT, last_seen TEXT)")
        self.conn.executemany("INSERT INTO gov_docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("nl", "d1", "Kamerbrief over abortuszorg", "letter", "Ministerie van VWS", "2026-10-14",
             None, "https://example.org/d1", "[1]", '["abortus"]', TODAY, TODAY),
            ("nl", "d2", "Consultatie Wet zelfbeschikking", "consultation", "Autoriteit Persoonsgegevens",
             "2026-10-12", "2026-11-20", "https://example.org/d2", "[2]", "[]", TODAY, TODAY),
            ("de", "d3", "Not ours", "letter", "BMG", "2026-10-14", None, None, "[1]", "[]", TODAY, TODAY)])
        text = self.render()
        pubs = text.split("## Government publications")[1].split("## ")[0]
        self.assertIn("Kamerbrief over abortuszorg", pubs)
        self.assertNotIn("Not ours", pubs)
        self.assertNotIn("Wet zelfbeschikking", pubs)                  # a row instead
        self.assertIn("| Fri 20 Nov | AUTORITEIT PERSOONSGEGEVENS |", text)

    def test_regional_agenda_rows_and_sitting_line(self):
        self.conn.execute("CREATE TABLE regional_agenda (cc TEXT, region TEXT, body TEXT, dated TEXT, "
                          "business TEXT, item_type TEXT, url TEXT, areas TEXT, matched_terms TEXT, "
                          "first_seen TEXT, last_seen TEXT)")
        self.conn.execute("INSERT INTO regional_agenda VALUES ('at','Steiermark','Landtag Steiermark',"
                          "'2026-10-20','Antrag Schutz des ungeborenen Lebens','Antrag',NULL,'[1]','[]',?,?)",
                          (TODAY, TODAY))
        at = country(cc="at", name="Austria", taxonomies=(("taxonomy-atch.yaml", "at"),),
                     items=lambda *a: [], watchlist=lambda config_dir=None: {})
        text = self.render(at)
        self.assertIn("| Tue 20 Oct | LANDTAG STEIERMARK |", text)
        self.assertIn("Landtag Steiermark: on its agenda Tue 20 Oct", text)
        self.assertNotIn(cc_.REGIONAL_NOTE, text)


class Reference(Base):
    def test_classic_sections_and_post_render_survive(self):
        def post(conn, country_, today, text, wl):
            return text.replace("\n## Watchlist\n", "\n## Regional section\n\nHere.\n\n## Watchlist\n", 1)
        text = self.render(country(post_render=post))
        ref = text.split("## Reference")[1]
        self.assertIn("### Recorded votes", ref)
        self.assertIn("### Regional section", ref)
        self.assertLess(ref.index("### Regional section"), ref.index("### Watchlist"))
        self.assertIn("| 36390 | TWEEDE KAMER | Thu 22 Oct, vaste commissie voor Justitie en "
                      "Veiligheid |", ref)

    def test_classic_layout_is_still_there(self):
        text = self.render(country(layout="classic"))
        self.assertNotIn("## This week", text)
        self.assertIn("## Recorded votes", text)


class DmAndJudge(Base):
    def test_dm_carries_big_dates_and_this_week(self):
        score(self.conn, "p1", 3)
        dm = ce.dm_summary(self.conn, country(), TODAY, SINCE, config_dir=self.cfg, directory=self.eds)
        self.assertIn("_Sitting this week: Tweede Kamer sitting (plenary Tue 20, Wed 21 and Fri 23 Oct)_", dm)
        self.assertIn("*BIG DATE* *Tue 20 Oct* · `TWEEDE KAMER`", dm)
        self.assertIn("*This week*: 3 row(s) on our issues.", dm)
        self.assertIn("*Further afield*:", dm)

    def test_judge_queue_reads_forward_rows_with_the_why_line(self):
        import edition_judge as tj
        from unittest import mock
        with mock.patch.object(ce, "adapter", return_value=country()):
            got = tj.country_items(self.conn, "nl", TODAY, self.cfg, self.eds)
            keys = {it["key"] for it in got if it["kind"] == "agenda"}
            self.assertTrue({"p1", "p3", "p6"} <= keys)
            self.assertNotIn("p8", keys)
            p3 = next(it for it in got if it["key"] == "p3")
            text = tj.item_text(p3, WL)
            self.assertIn("Watched by CitizenGO: Wet kind, draagmoederschap en afstamming", text)
            self.assertIn("Coming up: Tweede Kamer", text)


if __name__ == "__main__":
    unittest.main()
