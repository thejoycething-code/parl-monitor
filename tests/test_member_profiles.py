"""Member profiles for the new countries (src/member_profiles.py,
tools/member_profiles.py) and the two X6 party-history sources
(tools/hr_party_history.py, tools/cl_senate_parties.py), on small stores
built here. No network."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import at_store, cl_store, country_edition as ce, hr_store, noise, pl_store  # noqa: E402
from src import member_profiles as mp  # noqa: E402
from tools import cl_senate_parties, hr_party_history  # noqa: E402

TODAY = "2026-10-10"
FIX = os.path.join(ROOT, "tests", "fixtures", "profiles")


def conn_with(*stores):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for store in stores:
        store.ensure_schema(conn)
    return conn


class Base(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        os.makedirs(self.cfg)

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def build(self, conn, cc):
        return mp.build(conn, cc, TODAY, config_dir=self.cfg)


def pl_store_with_votes():
    conn = conn_with(pl_store)
    conn.executemany("INSERT INTO pl_members (mp_key, term, mp_id, name, club, district, active) "
                     "VALUES (?,?,?,?,?,?,?)",
                     [("10/1", 10, 1, "Anna Nowak", "KO", "Kraków (13)", 1),
                      ("10/2", 10, 2, "Jan Kowalski", "PiS", "Gdańsk (25)", 0)])
    conn.executemany("INSERT INTO pl_divisions (division_key, term, sitting, number, voted_at, "
                     "kind, title, topic, process_keys, yes, no, abstain, areas, own_areas, "
                     "tier) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     [("pl-10-60-1", 10, 60, 1, "2026-06-01T10:00", "ELECTRONIC",
                       "Pkt 3. Projekt ustawy o ochronie życia", "głosowanie nad całością",
                       "[]", 230, 200, 5, "[1]", "[1]", 1),
                      ("pl-10-60-2", 10, 60, 2, "2026-06-01T10:05", "ELECTRONIC",
                       "Pkt 4. Projekt ustawy o drogach", "głosowanie nad całością",
                       "[]", 400, 10, 0, "[]", "[]", None)])
    conn.executemany("INSERT INTO pl_votes (division_key, mp_key, position, club) VALUES (?,?,?,?)",
                     [("pl-10-60-1", "10/1", "YES", "KO"), ("pl-10-60-1", "10/2", "NO", "PiS"),
                      ("pl-10-60-2", "10/1", "YES", "KO"), ("pl-10-60-2", "10/2", "YES", "Konf")])
    return conn


class AtTheVote(Base):
    def test_positions_verbatim_with_the_party_the_record_names(self):
        data = self.build(pl_store_with_votes(), "pl")
        anna, jan = data["members"]["10/1"], data["members"]["10/2"]
        self.assertEqual(len(anna.votes), 1)          # the roads vote is not on our ground
        v = anna.votes[0]
        self.assertEqual((v["position"], v["party"], v["basis"]), ("YES", "KO", mp.AT_VOTE))
        self.assertEqual(v["areas"], [1])
        self.assertFalse(v["derived"])
        self.assertEqual(jan.votes[0]["position"], "NO")

    def test_parties_recorded_at_votes_cover_the_whole_store(self):
        data = self.build(pl_store_with_votes(), "pl")
        parties = {p for p, _a, _b in data["members"]["10/2"].at_votes}
        self.assertEqual(parties, {"PiS", "Konf"})

    def test_write_profiles_index_and_remove_stale_files(self):
        data = self.build(pl_store_with_votes(), "pl")
        out = os.path.join(self.tmp, "profiles")
        os.makedirs(os.path.join(out, "pl"))
        stale = os.path.join(out, "pl", "someone-who-left-10-9.md")
        open(stale, "w").close()
        written, removed = mp.write(data, out, sample=True)
        self.assertEqual((written, removed), (2, 1))
        files = sorted(os.listdir(os.path.join(out, "pl")))
        self.assertEqual(files, ["anna-nowak-10-1.md", "index.md", "jan-kowalski-10-2.md"])
        text = open(os.path.join(out, "pl", "anna-nowak-10-1.md"), encoding="utf-8").read()
        self.assertIn(mp.SAMPLE_MARK, text)
        self.assertIn("**YES** · KO (at the vote", text)
        self.assertIn("*Pkt 3. Projekt ustawy o ochronie życia*", text)
        self.assertIn("never a verdict", text)
        self.assertNotIn("—", text)
        index = open(os.path.join(out, "pl", "index.md"), encoding="utf-8").read()
        self.assertIn("[Anna Nowak](anna-nowak-10-1.md)", index)

    def test_a_rerun_with_nothing_new_rewrites_nothing(self):
        data = self.build(pl_store_with_votes(), "pl")
        out = os.path.join(self.tmp, "profiles")
        mp.write(data, out)
        path = os.path.join(out, "pl", "anna-nowak-10-1.md")
        before = os.stat(path).st_mtime_ns
        mp.write(self.build(pl_store_with_votes(), "pl"), out)
        self.assertEqual(os.stat(path).st_mtime_ns, before)


def hr_store_with_votes():
    conn = conn_with(hr_store)
    conn.executemany("INSERT INTO hr_members (slug, name, party, constituency, mandate, saziv) "
                     "VALUES (?,?,?,?,?,?)",
                     [("a-ana-11-saziv", "Anić, Ana", "HDZ", "I. izborna jedinica", "Aktivan", 11),
                      ("b-bruno-11-saziv", "Babić, Bruno", "Most", "II. izborna jedinica",
                       "Aktivan", 11)])
    conn.execute("INSERT INTO hr_divisions (division_key, tid, saziv, session_no, voted_at, title, "
                 "bill_key, yes, no, abstain, outcome, yes_means_reject, areas, tier) VALUES "
                 "('hr-11-1', 1, 11, '9', '2026-03-06T12:00', 'PRIJEDLOG ZAKONA O OBITELJI', "
                 "'11/5', 80, 50, 1, NULL, NULL, '[9]', 1)")
    conn.executemany("INSERT INTO hr_votes (division_key, slug, position, party_seen) "
                     "VALUES (?,?,?,?)", [("hr-11-1", "a-ana-11-saziv", "for", "HDZ"),
                                          ("hr-11-1", "b-bruno-11-saziv", "against", "Most")])
    return conn


class AsListedAndTranscripts(Base):
    def test_without_sightings_the_party_is_as_listed(self):
        data = self.build(hr_store_with_votes(), "hr")
        v = data["members"]["a-ana-11-saziv"].votes[0]
        self.assertEqual(v["party"], "HDZ")
        self.assertIn("not party at the vote", v["basis"])

    def test_sightings_on_both_sides_of_the_vote_give_the_party(self):
        conn = hr_store_with_votes()
        conn.executemany("INSERT INTO hr_party_seen (slug, date, party, tdrid) VALUES (?,?,?,?)",
                         [("b-bruno-11-saziv", "2026-02-01", "Nezavisni", 1),
                          ("b-bruno-11-saziv", "2026-04-01", "Nezavisni", 2),
                          ("a-ana-11-saziv", "2026-02-01", "HDZ", 1),
                          ("a-ana-11-saziv", "2026-04-01", "DP", 2)])
        data = self.build(conn, "hr")
        bruno = data["members"]["b-bruno-11-saziv"]
        self.assertEqual(bruno.votes[0]["party"], "Nezavisni")
        self.assertIn("transcripts", bruno.votes[0]["basis"])
        self.assertEqual([h[0] for h in bruno.history], ["Nezavisni"])
        # Ana's sightings disagree either side of the vote: as listed, said so.
        ana = data["members"]["a-ana-11-saziv"]
        self.assertIn("not party at the vote", ana.votes[0]["basis"])
        self.assertEqual([h[0] for h in ana.history], ["HDZ", "DP"])

    def test_spells_and_sighted_party(self):
        spells = mp.sightings_to_spells([("2026-01-01", "A"), ("2026-02-01", "A"),
                                         ("2026-03-01", "B")])
        self.assertEqual(spells, [("A", "2026-01-01", "2026-02-01", 2),
                                  ("B", "2026-03-01", "2026-03-01", 1)])
        self.assertEqual(mp.sighted_party(spells, "2026-01-15"), "A")
        self.assertIsNone(mp.sighted_party(spells, "2026-02-15"))
        self.assertIsNone(mp.sighted_party(spells, "2026-05-01"))


class Derived(Base):
    def test_party_group_votes_are_derived_and_labelled(self):
        conn = conn_with(at_store)
        conn.executemany("INSERT INTO at_members (pad, name, chamber, klub, wahlkreis, "
                         "bundesland) VALUES (?,?,?,?,?,?)",
                         [("1", "Auer Katrin, Mag.", "NR", "SPÖ", "9A", "Wien"),
                          ("2", "Berger Ricarda", "NR", "FPÖ", "9", "Wien")])
        conn.execute("INSERT INTO at_items (item_key, gp, chamber, art, title, areas, tier, "
                     "persons, art_long, introduced) VALUES ('XXVIII/I/525', 'XXVIII', 'NR', "
                     "'RV', 'Sterbeverfügungsgesetz-Novelle 2026', '[2]', 1, '[\"2\"]', "
                     "'Regierungsvorlage', '2026-06-01')")
        conn.execute("INSERT INTO at_divisions (division_key, item_key, date, body, question, "
                     "outcome, unanimous, roll_call, areas) VALUES ('d1@x', 'XXVIII/I/525', "
                     "'2026-07-07', 'NR', 'Gesetzesvorschlag in dritter Lesung', 'angenommen', "
                     "0, 0, '[2]')")
        conn.executemany("INSERT INTO at_votes (division_key, klub, position) VALUES (?,?,?)",
                         [("d1@x", "SPÖ", "Dafür"), ("d1@x", "FPÖ", "Dagegen")])
        data = self.build(conn, "at")
        v = data["members"]["2"].votes[0]
        self.assertTrue(v["derived"])
        self.assertEqual((v["position"], v["party"], v["basis"]), ("Dagegen", "FPÖ", mp.DERIVED))
        self.assertEqual(data["members"]["2"].authored[0]["key"], "XXVIII/I/525")
        text = mp.render_member(data, data["members"]["2"])
        self.assertIn("DERIVED from the group, not recorded per member", text)
        self.assertIn("DERIVED positions (1", text)
        self.assertNotIn("Recorded positions", text)


class ChileSpells(Base):
    def test_senate_votes_take_the_bcn_party_on_the_day(self):
        conn = conn_with(cl_store)
        conn.executemany("INSERT INTO cl_members (member_key, chamber, source_id, name, party) "
                         "VALUES (?,?,?,?,?)",
                         [("S-1110", "senado", "1110", "Pedro Araya Guerrero", "P.P.D."),
                          ("D-803", "camara", "803", "René Alinco Bustos", "IND")])
        conn.executemany("INSERT INTO cl_party_spells (member_key, party, party_name, start, end) "
                         "VALUES (?,?,?,?,?)",
                         [("S-1110", "Independiente", "Independiente", "2014-03-11", "2024-01-08"),
                          ("S-1110", "Partido Por la Democracia", "Partido Por la Democracia",
                           "2024-01-08", None)])
        conn.executemany("INSERT INTO cl_divisions (division_key, chamber, date, boletin, "
                         "description, yes, no, areas, tier) VALUES (?,?,?,?,?,?,?,?,?)",
                         [("cl-s-1", "senado", "2023-05-02", "1-07", "Aborto", 20, 10, "[1]", 1),
                          ("cl-c-1", "camara", "2026-05-02", "2-07", "Aborto", 80, 50, "[1]", 1)])
        conn.executemany("INSERT INTO cl_votes (division_key, member_key, position, party) "
                         "VALUES (?,?,?,?)", [("cl-s-1", "S-1110", "Si", "P.P.D."),
                                              ("cl-c-1", "D-803", "Afirmativo", "PRI")])
        data = self.build(conn, "cl")
        s = data["members"]["S-1110"].votes[0]
        self.assertEqual(s["party"], "Independiente")
        self.assertIn("BCN", s["basis"])
        d = data["members"]["D-803"].votes[0]
        self.assertEqual(d["party"], "PRI")
        self.assertIn("militancias", d["basis"])
        self.assertEqual(len(data["members"]["S-1110"].history), 2)


class Names(unittest.TestCase):
    def test_short_forms_resolve_only_when_unique(self):
        ros = mp.Roster([mp.Member("1", "Adolfo Antonio Rivas Ramírez"),
                         mp.Member("2", "Ana Magdalena Figueroa Figueroa"),
                         mp.Member("3", "Ana Lucía Figueroa Pérez")])
        self.assertEqual(ros.resolve(None, "ADOLFO RIVAS").key, "1")
        self.assertEqual(ros.resolve(None, "Rivas Ramírez, Adolfo Antonio").key, "1")
        stub = ros.resolve(None, "ANA FIGUEROA")           # two listed members fit
        self.assertTrue(stub.stub)
        self.assertIsNone(ros.resolve(None, "Nobody Here", make_stub=False))

    def test_titles_are_not_name_words(self):
        self.assertEqual(mp.name_tokens("Auer Katrin, Mag."), mp.name_tokens("Katrin Auer"))

    def test_every_spec_names_its_chamber_columns(self):
        for cc, spec in mp.SPECS.items():
            self.assertEqual(spec.cc, cc)
            self.assertIn(spec.basis, ("at_vote", "as_listed", "derived"), cc)
            self.assertTrue(spec.party_note, cc)
            self.assertNotIn("—", spec.party_note, cc)


class EditionField(unittest.TestCase):
    def test_item_carries_a_division_only_when_given(self):
        it = ce.vote("hr", "11/5", "2026-03-06", "t", [9], 1, False, [], division="hr-11-1")
        self.assertEqual(it["division"], "hr-11-1")
        self.assertNotIn("division", ce.vote("pl", "pl-1", "2026-03-06", "t", [9], 1, False, []))


class CroatianTranscripts(unittest.TestCase):
    PAGE = open(os.path.join(FIX, "hr-fonogram.html"), encoding="utf-8").read() \
        if os.path.exists(os.path.join(FIX, "hr-fonogram.html")) else ""

    def test_parse_reads_saziv_days_and_party_headings(self):
        got = hr_party_history.parse(self.PAGE)
        self.assertEqual((got["saziv"], got["session_no"]), ("XI", "12"))
        self.assertIn(("Reiner, Željko", "HDZ", "2026-09-29"), got["sightings"])
        self.assertIn(("Kolarić, Branko", "Nezavisni", "2026-09-29"), got["sightings"])
        # The state secretary's heading names no party: not a sighting.
        self.assertFalse(any(n.startswith("Vuković") for n, _p, _d in got["sightings"]))

    def test_no_transcript_is_none(self):
        self.assertIsNone(hr_party_history.parse("<html><body>e-doc</body></html>"))

    def test_store_keeps_only_listed_members_of_this_saziv(self):
        conn = conn_with(hr_store)
        conn.execute("INSERT INTO hr_members (slug, name, party, saziv) VALUES "
                     "('reiner-zeljko-11-saziv', 'Reiner, Željko', 'HDZ', 11)")
        got = hr_party_history.parse(self.PAGE)
        kept = hr_party_history.store(conn, 2017620, got, hr_party_history.members(conn), TODAY)
        self.assertGreater(kept, 0)
        rows = conn.execute("SELECT DISTINCT slug, date, party FROM hr_party_seen").fetchall()
        self.assertEqual([tuple(r) for r in rows],
                         [("reiner-zeljko-11-saziv", "2026-09-29", "HDZ")])
        hr_party_history.store(conn, 2017640, None, {}, TODAY)
        self.assertEqual(conn.execute("SELECT saziv FROM hr_transcripts WHERE tdrid=2017640")
                         .fetchone()[0], None)

    def test_todo_walks_newest_first_and_rechecks_recent_empties(self):
        conn = conn_with(hr_store)
        start = 1000
        conn.executemany("INSERT INTO hr_transcripts (tdrid, saziv, speakers) VALUES (?,?,?)",
                         [(1000, "XI", 3), (1001, None, 0), (1002, "XI", 2)])
        got = hr_party_history.todo(conn, start=start, lookahead=2, recheck=5, newest=1004)
        self.assertEqual(got, [1006, 1005, 1004, 1003, 1001])

    def test_frontier_is_the_list_pages_newest_id(self):
        page = ("<a href='Views/FonogramView.aspx?tdrid=2017620'>28</a>"
                "<a href='/Views/FonogramView.aspx?tdrid=2017615'>x</a>")
        self.assertEqual(hr_party_history.frontier(page), 2017620)


class ChileBcn(unittest.TestCase):
    def test_parse_and_store(self):
        # The fixture is the real answer for senator 1110, plus one real row
        # of another senator with its start date removed (an undated spell).
        with open(os.path.join(FIX, "cl-bcn-militancias.json"), encoding="utf-8") as fh:
            spells, undated = cl_senate_parties.parse(json.load(fh))
        self.assertEqual(undated, 1)
        self.assertEqual([s["party"] for s in spells["1110"]],
                         ["Partido Demócrata Cristiano",
                          "Partido Regionalista de los Independientes", "Independiente",
                          "Partido Por la Democracia"])
        self.assertIsNone(spells["1110"][-1]["end"])
        conn = conn_with(cl_store)
        conn.execute("INSERT INTO cl_members (member_key, chamber, source_id, name) VALUES "
                     "('S-1110', 'senado', '1110', 'Pedro Araya Guerrero')")
        conn.execute("INSERT INTO cl_party_spells VALUES ('D-803','PRI','x','2022-03-11',NULL)")
        self.assertEqual(cl_senate_parties.store(conn, spells), (1, 4))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM cl_party_spells WHERE member_key="
                                      "'D-803'").fetchone()[0], 1)


class Tool(unittest.TestCase):
    def test_tool_renders_from_a_store_file(self):
        from tools import member_profiles as tool
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "store.db")
            src = pl_store_with_votes()
            src.commit()
            dst = sqlite3.connect(path)
            src.backup(dst)
            dst.close()
            out = os.path.join(tmp, "profiles")
            self.assertEqual(tool.main(["pl", "--db", path, "--out", out, "--date", TODAY]), 0)
            self.assertTrue(os.path.exists(os.path.join(out, "pl", "index.md")))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
