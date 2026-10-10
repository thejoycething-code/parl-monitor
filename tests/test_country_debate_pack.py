"""The country debate pack (src/country_debatepack.py, src/debatepack_i18n.py,
tools/country_debate_pack.py). A small temporary Polish store; no network,
no Slack, no AI."""

import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import country_debatepack as dp  # noqa: E402
from src import debatepack_i18n as i18n  # noqa: E402
from src import pl_store  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tool = _load("country_debate_pack")
QUIET = lambda *a, **k: None  # noqa: E731

PROCESSES = [
    # key, title, areas, tier, start, last stage date
    ("10/2110", "Rządowy projekt ustawy o statusie osoby najbliższej", [9], 1,
     "2026-05-01", "2026-09-20"),
    ("10/3000", "Poselski projekt ustawy o ochronie rodziny", [9], 1, "2026-04-01", "2026-06-10"),
    ("10/50", "Projekt ustawy o radiofonii", [7], 2, "2026-03-01", "2026-03-02"),
]
DIVS = [
    # key, sitting, number, date, topic, processes, areas, tier, yes, no, abstain
    ("pl-10-1-1", 1, 1, "2026-05-29", "głosowanie nad całością projektu.", ["10/2110"], [9], 1, 4, 3, 0),
    ("pl-10-1-2", 1, 2, "2026-05-29", "poprawka 1", ["10/2110"], [9], 1, 3, 4, 0),
    ("pl-10-1-4", 1, 4, "2026-05-28", "wniosek o odrzucenie w całości projektu.", ["10/2110"], [9], 1, 3, 4, 0),
    ("pl-10-2-1", 2, 1, "2026-06-10", "głosowanie nad całością projektu.", ["10/3000"], [9], 1, 4, 3, 0),
    ("pl-10-2-2", 2, 2, "2026-06-10", "wniosek o uzupełnienie porządku dziennego.", ["10/3000"], [9], 1, 5, 2, 0),
]
MEMBERS = [("10/1", "Anna Adamska", "PiS"), ("10/2", "Bartosz Bielski", "PiS"),
           ("10/3", "Celina Czarnecka", "PiS"), ("10/4", "Dawid Dudek", "PiS"),
           ("10/5", "Ewa Ekiert", "KO"), ("10/6", "Filip Fornal", "KO"),
           ("10/7", "Grażyna Gil", "KO")]
# PiS mostly NO on the final 10/2110 vote, Dawid Dudek YES (a rebel); KO YES.
VOTES = {
    "pl-10-1-1": {"10/1": "NO", "10/2": "NO", "10/3": "NO", "10/4": "YES",
                  "10/5": "YES", "10/6": "YES", "10/7": "YES"},
    "pl-10-1-4": {"10/1": "YES", "10/2": "YES", "10/3": "YES", "10/4": "NO",
                  "10/5": "NO", "10/6": "NO", "10/7": "NO"},
    "pl-10-2-1": {"10/1": "YES", "10/2": "YES", "10/3": "YES", "10/4": "YES",
                  "10/5": "NO", "10/6": "NO", "10/7": "ABSENT"},
}
WATCHLIST = """watched:
  "10/2110":
    name: "Osoba najbliższa"
    areas: [9]
"""
STANCE = c5.header("pl") + """
bill_directions:
  - key: "10/2110"
    direction: against
    status: draft
    areas: [9]
    why: "Registered cohabitation contracts."
    drafted: "test"
  - key: "10/3000"
    direction: with
    status: draft
    areas: [9]
    why: "Family protection."
    drafted: "test"

divisions:
"""


def make_store(path):
    conn = sqlite3.connect(path)
    pl_store.ensure_schema(conn)
    for key, title, areas, tier, start, last in PROCESSES:
        conn.execute("INSERT INTO pl_processes (process_key, term, number, title, start_date, "
                     "last_stage, last_stage_date, areas, tier) VALUES (?,10,?,?,?,?,?,?,?)",
                     (key, key.split("/")[1], title, start, "Drugie czytanie", last,
                      json.dumps(areas), tier))
    for key, sitting, number, date, topic, procs, areas, tier, yes, no, ab in DIVS:
        conn.execute("INSERT INTO pl_divisions (division_key, term, sitting, number, voted_at, "
                     "kind, title, topic, process_keys, areas, own_areas, tier, yes, no, abstain) "
                     "VALUES (?,10,?,?,?,'ELECTRONIC',?,?,?,?,?,?,?,?,?)",
                     (key, sitting, number, date + "T10:00:00", "Pkt. 5 Sprawozdanie", topic,
                      json.dumps(procs), json.dumps(areas), json.dumps(areas), tier, yes, no, ab))
    for mp, name, club in MEMBERS:
        conn.execute("INSERT INTO pl_members (mp_key, term, mp_id, name, club, active) "
                     "VALUES (?,10,?,?,?,1)", (mp, int(mp.split("/")[1]), name, club))
    clubs = {m: c for m, _n, c in MEMBERS}
    for key, got in VOTES.items():
        for mp, pos in got.items():
            conn.execute("INSERT INTO pl_votes (division_key, mp_key, position, club) "
                         "VALUES (?,?,?,?)", (key, mp, pos, clubs[mp]))
    conn.commit()
    conn.close()


def add_agenda(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE country_agenda (cc TEXT, item_id TEXT, date TEXT, time TEXT,
        body TEXT, kind TEXT, title TEXT, detail TEXT, refs TEXT, bill_keys TEXT, url TEXT,
        status TEXT, own_areas TEXT, areas TEXT, matched_terms TEXT, tier INTEGER,
        watch_keys TEXT, first_seen TEXT, last_seen TEXT, PRIMARY KEY (cc, item_id))""")
    conn.execute("CREATE TABLE country_agenda_runs (cc TEXT, run_date TEXT, items INTEGER, "
                 "on_ground INTEGER, horizon TEXT, next_sitting TEXT, note TEXT)")
    conn.execute("INSERT INTO country_agenda_runs VALUES ('pl', '2026-10-10', 2, 1, "
                 "'2026-10-16', '2026-10-15', NULL)")
    for r in rows:
        conn.execute("INSERT INTO country_agenda (cc, item_id, date, time, body, kind, title, "
                     "refs, bill_keys, url, status, areas, tier, watch_keys) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", r)
    conn.commit()
    conn.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.tmp.name, "config")
        os.makedirs(self.cfg)
        with open(os.path.join(self.cfg, "watchlist-pl.yaml"), "w", encoding="utf-8") as h:
            h.write(WATCHLIST)
        with open(os.path.join(self.cfg, "pl_stance.yaml"), "w", encoding="utf-8") as h:
            h.write(STANCE)
        self.db = os.path.join(self.tmp.name, "store.db")
        make_store(self.db)
        conn = c5.connect_ro(self.db)
        c5.draft(conn, "pl", self.cfg, "2026-10-10", QUIET, wl={"10/2110": {"areas": [9]}})
        conn.close()
        self.conn = c5.connect_ro(self.db)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def subject(self, item="10/2110", date="2026-10-14"):
        subs = dp.find_subjects(self.conn, "pl", date, item=item, config_dir=self.cfg)
        self.assertEqual(len(subs), 1, [s["subject"] for s in subs])
        return subs[0]

    def pack(self, **kw):
        return dp.assemble(self.conn, "pl", "2026-10-14", self.subject(), config_dir=self.cfg,
                           today="2026-10-10", **kw)


class FindTests(Base):
    def test_item_by_key_merges_the_bill_and_its_votes(self):
        s = self.subject()
        self.assertEqual(s["subject"], "10/2110")
        self.assertTrue(s["watched"])
        self.assertIn("pl-10-1-1", s["ids"])
        self.assertEqual(s["title"], "Rządowy projekt ustawy o statusie osoby najbliższej")

    def test_find_by_words_and_several_matches_are_listed(self):
        one = dp.find_subjects(self.conn, "pl", "2026-10-14", find="osoby najbliższej",
                               config_dir=self.cfg)
        self.assertEqual([s["subject"] for s in one], ["10/2110"])
        many = dp.find_subjects(self.conn, "pl", "2026-10-14", find="projekt ustawy",
                                config_dir=self.cfg)
        self.assertGreater(len(many), 1)
        self.assertEqual(many[0]["subject"], "10/2110")      # watched first

    def test_no_keyword_alone_puts_an_item_on_our_ground(self):
        # The tier-2 radio bill is on our ground through its stored areas; a
        # title with no areas and no watch key never appears.
        subs = dp.find_subjects(self.conn, "pl", "2026-10-14", find="Sprawozdanie",
                                config_dir=self.cfg)
        self.assertTrue(all(s["areas"] for s in subs))


class AssembleTests(Base):
    def test_votes_on_the_bill_by_id_and_topic_votes_without_procedure(self):
        p = self.pack()
        self.assertEqual(sorted(d["key"] for d in p["bill_votes"]),
                         ["pl-10-1-1", "pl-10-1-2", "pl-10-1-4"])
        self.assertEqual(sorted(d["key"] for d in p["decisive"]), ["pl-10-1-1", "pl-10-1-4"])
        self.assertEqual([d["key"] for d in p["topic_votes"]], ["pl-10-2-1"])

    def test_rebels_are_arithmetic_on_the_record(self):
        p = self.pack()
        names = [r["name"] for r in p["watch"]]
        self.assertEqual(names, ["Dawid Dudek"])
        self.assertEqual(len(p["watch"][0]["broke"]), 2)   # final and reject votes

    def test_awaiting_signoff_places_nobody(self):
        p = self.pack()
        self.assertEqual(p["confirmed"], 0)
        self.assertEqual(p["placements"], {})
        text = dp.render_pack(p)
        self.assertIn(i18n.text("pl", "place_awaiting"), text)
        self.assertNotIn("++", text)
        self.assertNotIn("| --", text)
        rows = dp.member_rows(p)
        self.assertTrue(all(r["place_cell"] == "czeka na zatwierdzenie" for r in rows))

    def test_a_draft_with_values_still_places_nobody(self):
        e = c5.load("pl", self.cfg)[0]["pl-10-1-1"]
        self.assertEqual((e["status"], e["yea"]), ("draft", -2))
        self.assertEqual(self.pack()["placements"], {})

    def test_confirmed_reading_places_members(self):
        c5.confirm("pl", ["pl-10-1-1"], "Christopher", "2026-10-10", config_dir=self.cfg,
                   log=QUIET)
        p = self.pack()
        self.assertEqual(p["confirmed"], 1)
        # passing 10/2110 is against us: NO places ++, YES places --
        self.assertEqual(p["placements"]["10/1"], ["9: ++"])
        self.assertEqual(p["placements"]["10/4"], ["9: --"])
        text = dp.render_pack(p)
        self.assertNotIn(i18n.text("pl", "place_awaiting"), text)
        self.assertIn("9: ++", text)

    def test_pack_is_in_polish_with_verbatim_titles(self):
        text = dp.render_pack(self.pack())
        self.assertIn("# Pakiet na debatę: Rządowy projekt ustawy o statusie osoby najbliższej", text)
        self.assertIn("## Zarejestrowane głosowania nad tym projektem", text)
        self.assertIn("Za 4, Przeciw 3", text)
        self.assertIn("PiS: Za 1, Przeciw 3", text)
        self.assertIn("- Projekt lub druk: 10/2110\n", text)
        self.assertIn("- Link: https://www.sejm.gov.pl/Sejm10.nsf/PrzebiegProc.xsp?nr=2110", text)
        self.assertNotIn("\u2014", text)

    def test_agenda_uncollected_then_matched_by_bill_key(self):
        text = dp.render_pack(self.pack())
        self.assertIn(i18n.text("pl", "agenda_uncollected"), text)
        self.conn.close()
        add_agenda(self.db, [
            ("pl", "pl-41-3", "2026-10-15", "10:00", "Plenary", "plenary",
             "Drugie czytanie rządowego projektu ustawy (druk 2110)", json.dumps(["10/2110"]),
             json.dumps(["10/2110"]), "https://www.sejm.gov.pl/x", "Planowane", "[9]", 1, "[]"),
            ("pl", "pl-41-4", "2026-10-15", "12:00", "Plenary", "plenary",
             "Inny punkt", "[]", "[]", None, None, "[]", None, "[]")])
        self.conn = c5.connect_ro(self.db)
        p = self.pack()
        self.assertEqual(p["agenda_state"], "collected")
        self.assertEqual([a["item_id"] for a in p["agenda"]], ["pl-41-3"])
        self.assertIn("2026-10-15 10:00, Plenary", dp.render_pack(p))

    def test_speakers_matched_to_the_roster(self):
        p = self.pack(speakers=["Dudek Dawid", "Nikt Nieznany"])
        got = [(g, m["name"] if m else None) for g, m in p["speakers"]]
        self.assertEqual(got, [("Dudek Dawid", "Dawid Dudek"), ("Nikt Nieznany", None)])
        text = dp.render_pack(p)
        self.assertIn("Nikt Nieznany: nie znaleziono na liście posłów", text)

    def test_profile_link_only_when_the_profile_exists(self):
        prof = os.path.join(self.tmp.name, "profiles")
        os.makedirs(os.path.join(prof, "pl"))
        with open(os.path.join(prof, "pl", "anna-adamska-10-1.md"), "w", encoding="utf-8") as h:
            h.write("# Anna Adamska\n\n## Votes on our ground (12)\n")
        p = dp.assemble(self.conn, "pl", "2026-10-14", self.subject(), config_dir=self.cfg,
                        today="2026-10-10", profiles_dir=prof)
        self.assertTrue(p["members"]["10/1"]["profile"].endswith("anna-adamska-10-1.md"))
        self.assertIsNone(p["members"]["10/2"]["profile"])
        self.assertEqual(p["members"]["10/1"]["profile_votes"], 12)

    def test_derived_positions_are_starred(self):
        rec = {"bill": [({"date": "2026-01-01", "key": "k"},
                         {"position": "Dafür", "derived": True})]}
        self.assertEqual(dp.bill_cell(rec, c5.SPECS["at"], "de"), "Dafür* (2026-01-01)")


class WriteTests(Base):
    def test_folder_files_and_checklist_round_trip(self):
        folder = dp.write_pack(self.pack(), os.path.join(self.tmp.name, "pack"))
        self.assertEqual(sorted(os.listdir(folder)),
                         ["README.md", "checklist.md", "members.csv", "pack.json", "pack.md"])
        check = os.path.join(folder, "checklist.md")
        with open(check, encoding="utf-8") as h:
            text = h.read()
        self.assertIn("# Lista kontrolna kampanii", text)
        self.assertIn("### group: PiS", text)
        self.assertIn("### member: Dawid Dudek", text)
        text = text.replace("### group: PiS\n- głosy", "### group: PiS\n- głosy", 1)
        text = text.replace("ONSIDE: \nNOTE: ", "ONSIDE: tak\nNOTE: rozmowa we wtorek", 1)
        with open(check, "w", encoding="utf-8") as h:
            h.write(text)
        got = dp.parse_checklist(check)
        self.assertEqual(got, [("group", "PiS", True, "rozmowa we wtorek")])
        with open(os.path.join(folder, "pack.json"), encoding="utf-8") as h:
            state = json.load(h)
        self.assertEqual(state["confirmed_readings"], 0)
        self.assertEqual(state["watch"], ["10/4"])

    def test_blank_is_not_agreement(self):
        path = os.path.join(self.tmp.name, "c.md")
        with open(path, "w", encoding="utf-8") as h:
            h.write("### member: A\nONSIDE: \n### member: B\nONSIDE: nie\n### member: C\n"
                    "ONSIDE: maybe\n### speaker: D\nONSIDE: yes\n")
        self.assertEqual(dp.parse_checklist(path), [("member", "B", False, ""),
                                                     ("speaker", "D", True, "")])


class ToolTests(Base):
    def run_tool(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = tool.main(list(argv) + ["--db", self.db, "--config-dir", self.cfg,
                                         "--today", "2026-10-10"])
        return rc, buf.getvalue()

    def test_build_dry_run_and_ambiguity(self):
        out = os.path.join(self.tmp.name, "p")
        rc, text = self.run_tool("--country", "pl", "--date", "2026-10-14", "--item", "10/2110",
                                 "--dry-run", "--out", out)
        self.assertEqual(rc, 0)
        self.assertIn("awaiting sign-off", text)
        self.assertFalse(os.path.exists(out))
        rc, text = self.run_tool("--country", "pl", "--date", "2026-10-14", "--find",
                                 "projekt ustawy")
        self.assertEqual(rc, 1)
        self.assertIn("several subjects match", text)
        rc, text = self.run_tool("--country", "pl", "--date", "2026-10-14", "--item", "10/2110",
                                 "--out", out, "--sample")
        self.assertEqual(rc, 0)
        with open(os.path.join(out, "pack.md"), encoding="utf-8") as h:
            self.assertIn(i18n.text("pl", "sample"), h.read())

    def test_list_and_unknown_country(self):
        rc, text = self.run_tool("--country", "pl", "--date", "2026-10-14", "--list",
                                 "--since", "2026-01-01")
        self.assertEqual(rc, 0)
        self.assertIn("10/2110", text)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.run_tool("--country", "gb", "--find", "x")


class I18nTests(unittest.TestCase):
    def test_every_language_has_every_phrase(self):
        en = set(i18n.TEXT["en"])
        for lang, table in i18n.TEXT.items():
            self.assertEqual(set(table) ^ en, set(), lang)
            self.assertEqual(set(table["areas_labels"]), set(i18n.TEXT["en"]["areas_labels"]), lang)
            for v in table.values():
                if isinstance(v, str):
                    self.assertNotIn("\u2014", v, lang)

    def test_every_country_has_a_language_and_a_spec_or_no_member_votes(self):
        for cc in dp.COUNTRIES:
            self.assertIn(i18n.lang_of(cc), i18n.TEXT, cc)
        self.assertEqual(i18n.lang_of("ch"), "de")
        self.assertEqual(i18n.lang_of("br"), "pt")


if __name__ == "__main__":
    unittest.main()
