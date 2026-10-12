"""Vote pages, the vote tracker and bill timelines for the new countries
(src/country_votes.py, tools/make_country_votes.py), on small stores built
here. No network."""
import importlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import agenda, at_store, hr_store, noise, partner, pl_store  # noqa: E402
from src import country_votes as cv  # noqa: E402
from src import member_profiles as mp  # noqa: E402

TODAY = "2026-10-10"

WATCHLIST = """processes:
  "10/9": {areas: [1], why: "INTERNAL REASONING NOT FOR PARTNERS"}
"""

STANCE = """bill_directions:
  - key: "10/9"
    direction: against
divisions:
  - key: "pl-10-60-1"
    status: confirmed
    confirmed_by: Christopher
    confirmed_on: 2026-10-09
    yea: -2
    nay: 2
    areas: [1]
    chamber: sejm
  - key: "pl-10-60-3"
    status: draft
    yea: -2
    nay: 2
    why_yea: "DRAFT DIRECTION THAT MUST NOT LEAK"
    areas: [1]
    chamber: sejm
"""

MEMBERS = [("10/1", "Anna Nowak", "KO"), ("10/2", "Beata Lis", "KO"), ("10/3", "Cezary Wolny", "KO"),
           ("10/4", "Dariusz Kot", "PiS"), ("10/5", "Ewa Sowa", "PiS"),
           ("10/6", "Filip Zając", "niez."), ("10/7", "Gosia Bąk", "niez."),
           ("10/8", "Henryk Mak", "niez.")]


def conn_with(*stores):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for store in stores:
        store.ensure_schema(conn)
    return conn


def pl_conn():
    conn = conn_with(pl_store, agenda)
    conn.executemany("INSERT INTO pl_members (mp_key, term, mp_id, name, club, district, active) "
                     "VALUES (?,10,?,?,?,'Kraków (13)',1)",
                     [(k, i, n, c) for i, (k, n, c) in enumerate(MEMBERS, 1)])
    conn.execute("INSERT INTO pl_processes (process_key, term, number, title, start_date, "
                 "last_stage, last_stage_date, areas, tier) VALUES ('10/9', 10, '9', "
                 "'Projekt ustawy o ochronie życia', '2026-03-02', 'Drugie czytanie', "
                 "'2026-06-01', '[1]', 1)")
    divs = [("pl-10-60-1", 1, "2026-06-01T10:00", "głosowanie nad całością", '["10/9"]', "[1]", 1),
            ("pl-10-60-2", 2, "2026-06-01T10:05", "Pkt 4. Projekt ustawy o drogach", "[]", "[]", None),
            ("pl-10-60-3", 3, "2026-06-02T10:00", "wniosek o odrzucenie", '["10/9"]', "[1]", 1)]
    conn.executemany("INSERT INTO pl_divisions (division_key, term, sitting, number, voted_at, kind, "
                     "title, topic, process_keys, yes, no, abstain, areas, own_areas, tier) "
                     "VALUES (?,10,60,?,?,'ELECTRONIC','Pkt 3. Projekt ustawy o ochronie życia',"
                     "?,?,4,4,0,?,?,?)", [d[:6] + (d[5], d[6]) for d in divs])
    votes = {"10/1": "YES", "10/2": "YES", "10/3": "NO", "10/4": "NO", "10/5": "NO",
             "10/6": "YES", "10/7": "YES", "10/8": "NO"}
    for div in ("pl-10-60-1", "pl-10-60-2", "pl-10-60-3"):
        conn.executemany("INSERT INTO pl_votes (division_key, mp_key, position, club) "
                         "VALUES (?,?,?,?)",
                         [(div, k, votes[k], c) for k, _n, c in MEMBERS])
    conn.execute("INSERT INTO country_agenda (cc, item_id, date, body, kind, title, refs, bill_keys, "
                 "status, watch_keys, first_seen, last_seen) VALUES ('pl', 'p1', '2026-10-15', "
                 "'Plenary', 'plenary', 'Trzecie czytanie projektu ustawy (druk 9)', '[\"10/9\"]', "
                 "'[\"10/9\"]', 'planned', '[]', '2026-10-09', '2026-10-09')")
    return conn


class Base(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        os.makedirs(self.cfg)
        with open(os.path.join(self.cfg, "watchlist-pl.yaml"), "w", encoding="utf-8") as fh:
            fh.write(WATCHLIST)
        with open(os.path.join(self.cfg, "pl_stance.yaml"), "w", encoding="utf-8") as fh:
            fh.write(STANCE)

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def pl(self):
        return cv.build(pl_conn(), "pl", TODAY, config_dir=self.cfg)


def div(data, key):
    return next(d for d in data["divisions"] if d["k"] == key)


class VotePage(Base):
    def test_only_votes_on_our_ground_newest_first(self):
        data = self.pl()
        self.assertEqual([d["k"] for d in data["divisions"]], ["pl-10-60-3", "pl-10-60-1"])
        self.assertEqual(data["total"], 2)
        self.assertTrue(all(d["w"] for d in data["divisions"]))

    def test_positions_verbatim_with_party_at_the_vote(self):
        data = self.pl()
        d = div(data, "pl-10-60-1")
        got = sorted((data["members"][p[0]][0], data["words"][p[1]], data["groups"][p[2]],
                      data["bases"][p[3]]) for p in d["p"])
        self.assertIn(("Anna Nowak", "YES", "KO", mp.AT_VOTE), got)
        self.assertIn(("Ewa Sowa", "NO", "PiS", mp.AT_VOTE), got)
        self.assertEqual(len(got), 8)
        self.assertEqual((d["y"], d["n"], d["ab"]), (4, 4, 0))

    def test_against_the_group_never_counts_the_non_attached(self):
        data = self.pl()
        rebels = [data["members"][i][0] for i in div(data, "pl-10-60-1")["rb"]]
        # Cezary broke with KO; Henryk voted against the other non-attached
        # members, but they have no group line to break (#80).
        self.assertEqual(rebels, ["Cezary Wolny"])

    def test_a_confirmed_reading_is_shown_with_who_and_when(self):
        r = div(self.pl(), "pl-10-60-1")["reading"]
        self.assertEqual(r, {"state": "confirmed", "by": "Christopher", "on": "2026-10-09",
                             "yea": -2, "nay": 2})

    def test_an_unconfirmed_reading_carries_no_direction_at_all(self):
        data = self.pl()
        r = div(data, "pl-10-60-3")["reading"]
        self.assertEqual(r, {"state": cv.AWAITING})
        page = cv.render_page(data)
        blob = json.loads(re.search(r"const DATA = (\{.*?\});\n", page, re.S).group(1)
                          .replace("<\\/", "</"))
        self.assertEqual(div(blob, "pl-10-60-3")["reading"], {"state": cv.AWAITING})
        self.assertNotIn("DRAFT DIRECTION THAT MUST NOT LEAK", page)

    def test_no_entry_means_no_reading_drafted(self):
        self.assertEqual(cv.reading_of(None), {"state": cv.NOT_DRAFTED})
        self.assertEqual(cv.reading_of({"key": "x", "status": "confirmed", "yea": 2}),
                         {"state": cv.AWAITING})        # no confirmed_by / confirmed_on

    def test_page_is_gated_and_clean(self):
        page = cv.render_page(self.pl(), sample=True)
        self.assertIn('<meta name="robots" content="noindex, nofollow">', page)
        self.assertIn("Poland: votes on our ground", page)
        self.assertIn(cv.SAMPLE_MARK, page)
        self.assertNotIn("/*__DATA__*/", page)
        self.assertNotIn("—", page)
        self.assertNotIn("INTERNAL REASONING", page)

    def test_listed_divisions_are_capped_and_the_rest_counted(self):
        data = cv.build(pl_conn(), "pl", TODAY, config_dir=self.cfg, max_divisions=1)
        self.assertEqual((data["shown"], data["total"]), (1, 2))


class Derived(Base):
    def test_party_group_positions_are_derived_and_never_rebels(self):
        conn = conn_with(at_store)
        conn.executemany("INSERT INTO at_members (pad, name, chamber, klub) VALUES (?,?,?,?)",
                         [("1", "Auer Katrin", "NR", "SPÖ"), ("2", "Berger Ricarda", "NR", "FPÖ"),
                          ("3", "Corn Hans", "NR", "FPÖ"), ("4", "Dorn Eva", "NR", "FPÖ")])
        conn.execute("INSERT INTO at_items (item_key, gp, chamber, art, title, areas, tier) VALUES "
                     "('XXVIII/I/525', 'XXVIII', 'NR', 'RV', 'Sterbeverfügungsgesetz', '[2]', 1)")
        conn.execute("INSERT INTO at_divisions (division_key, item_key, date, body, question, "
                     "outcome, unanimous, roll_call, areas) VALUES ('d1@x', 'XXVIII/I/525', "
                     "'2026-07-07', 'NR', 'in dritter Lesung', 'angenommen', 0, 0, '[2]')")
        conn.executemany("INSERT INTO at_votes (division_key, klub, position) VALUES (?,?,?)",
                         [("d1@x", "SPÖ", "Dafür"), ("d1@x", "FPÖ", "Dagegen")])
        data = cv.build(conn, "at", TODAY, config_dir=self.cfg)
        d = data["divisions"][0]
        self.assertTrue(d["p"])
        self.assertTrue(all(data["bases"][p[3]] == mp.DERIVED for p in d["p"]))
        self.assertEqual(d["rb"], [])
        self.assertEqual(data["counts"]["derived"], len(d["p"]))
        self.assertEqual(data["counts"]["recorded"], 0)


class AsListed(Base):
    def test_x6_parties_are_labelled_and_never_rebels(self):
        conn = conn_with(hr_store)
        conn.executemany("INSERT INTO hr_members (slug, name, party, mandate, saziv) "
                         "VALUES (?,?,?,'Aktivan',11)",
                         [("a", "Anić, Ana", "HDZ"), ("b", "Babić, Bruno", "HDZ"),
                          ("c", "Cvitić, Cvita", "HDZ")])
        conn.execute("INSERT INTO hr_divisions (division_key, tid, saziv, session_no, voted_at, "
                     "title, yes, no, abstain, areas, tier) VALUES ('hr-1', 1, 11, 5, "
                     "'2026-05-05T10:00', 'Prijedlog zakona o pobačaju', 2, 1, 0, '[1]', 1)")
        conn.executemany("INSERT INTO hr_votes (division_key, slug, position) VALUES (?,?,?)",
                         [("hr-1", "a", "for"), ("hr-1", "b", "for"), ("hr-1", "c", "against")])
        data = cv.build(conn, "hr", TODAY, config_dir=self.cfg)
        d = data["divisions"][0]
        self.assertEqual({data["bases"][p[3]] for p in d["p"]},
                         {"as listed when the vote was collected, not party at the vote, X6"})
        self.assertEqual(d["rb"], [])


class Tracker(Base):
    def test_one_row_per_country_and_the_latest_votes(self):
        data = self.pl()
        page = cv.render_tracker([data], "2026-07-01")
        self.assertIn('<a href="/pl-votes.html">Poland</a>', page)
        self.assertIn('href="/pl-votes.html#v=pl-10-60-3"', page)
        self.assertIn("1 confirmed, 1 awaiting sign-off", page)
        self.assertIn("awaiting sign-off", page)
        self.assertIn("confirmed by Christopher on 2026-10-09", page)
        self.assertIn('<meta name="robots" content="noindex, nofollow">', page)
        self.assertNotIn("—", page)

    def test_nav_links_the_tracker_and_timelines_once_they_exist(self):
        site = os.path.join(self.tmp, "site")
        os.makedirs(site)
        self.assertNotIn("votes-countries.html", partner.vote_pages_nav(site))
        for f in ("votes-countries.html", "bill-timelines.html"):
            open(os.path.join(site, f), "w").close()
        nav = partner.vote_pages_nav(site)
        self.assertIn('<a href="/votes-countries.html">', nav)
        self.assertIn('<a href="/bill-timelines.html">', nav)


class Timelines(Base):
    def test_a_watched_bill_with_its_stages_agenda_slot_and_votes(self):
        tls = cv.timelines(pl_conn(), "pl", TODAY, config_dir=self.cfg)
        self.assertEqual(len(tls), 1)
        b = tls[0]
        self.assertEqual((b["key"], b["title"]), ("10/9", "Projekt ustawy o ochronie życia"))
        kinds = [(e[0], e[1]) for e in b["events"]]
        self.assertEqual(kinds, [("2026-03-02", "introduced"), ("2026-06-01", "stage"),
                                 ("2026-06-01", "vote"), ("2026-06-02", "vote"),
                                 ("2026-10-15", "agenda")])
        self.assertEqual([e[0] for e in b["upcoming"]], ["2026-10-15"])
        vote = [e for e in b["events"] if e[1] == "vote"][0]
        self.assertEqual(vote[3], "/pl-votes.html#v=pl-10-60-1")
        self.assertIn("Za 4, Przeciw 4", vote[2])

    def test_the_page_says_upcoming_and_keeps_internal_notes_out(self):
        tls = cv.timelines(pl_conn(), "pl", TODAY, config_dir=self.cfg)
        page = cv.render_timelines([("pl", "Poland", tls)], TODAY)
        self.assertIn("(upcoming)", page)
        self.assertIn("next on the agenda 15 October 2026", page)
        self.assertNotIn("INTERNAL REASONING", page)
        self.assertNotIn("—", page)

    def test_spain_procedural_history(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE es_initiatives (initiative_key TEXT, tramitacion TEXT)")
        conn.execute("INSERT INTO es_initiatives VALUES ('15/121/1', ?)",
                     ("Comisión de Igualdad \nPublicación \ndesde 12/12/2023 hasta 15/12/2023 \n"
                      "Comisión de Igualdad \nEnmiendas \ndesde 15/12/2023 \n",))
        self.assertEqual(cv.es_history(conn, "15/121/1"), [
            ("2023-12-12", "stage", "Comisión de Igualdad: Publicación (until 15 December 2023)"),
            ("2023-12-15", "stage", "Comisión de Igualdad: Enmiendas")])

    def test_every_bill_statement_runs_on_its_store(self):
        for cc, sql in cv.BILLS.items():
            store = importlib.import_module("src.{0}_store".format(cc))
            conn = sqlite3.connect(":memory:")
            store.ensure_schema(conn)
            with self.subTest(cc=cc):
                conn.execute(sql).fetchall()          # raises on a wrong column

    def test_every_vote_country_has_a_bill_statement_or_none_by_design(self):
        self.assertEqual(set(cv.COUNTRIES) - set(cv.BILLS), {"ec", "sv"})


class Tool(Base):
    def test_writes_pages_and_removes_a_page_left_with_no_votes(self):
        db = os.path.join(self.tmp, "store.db")
        src = pl_conn()
        dst = sqlite3.connect(db)
        src.commit()
        src.backup(dst)
        dst.close()
        site = os.path.join(self.tmp, "site")
        os.makedirs(site)
        stale = os.path.join(site, "hr-votes.html")
        open(stale, "w").close()
        from tools import make_country_votes as tool
        old = (cv.c5.CONFIG, mp.watchlist)
        try:
            cv.c5.CONFIG = self.cfg
            mp.watchlist = lambda cc, config_dir=None: (
                {"10/9": {"areas": [1]}} if cc == "pl" else {})
            rc = tool.main(["--db", db, "--out", site, "--date", TODAY,
                            "--country", "pl", "--country", "hr"])
        finally:
            cv.c5.CONFIG, mp.watchlist = old
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(stale))
        self.assertEqual(sorted(os.listdir(site)),
                         ["bill-timelines.html", "pl-votes.html", "votes-countries.html"])


if __name__ == "__main__":
    unittest.main()
