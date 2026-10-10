"""Campaign briefs for the new countries (src/country_briefs.py,
tools/country_briefs.py, src/brief_phrases.py, and the bill-direction sign-off
in src/country5ca.py). Small temporary Polish stores and a temporary config;
no network, no Slack, no model."""

import csv
import datetime
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import string
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import brief_phrases  # noqa: E402
from src import country5ca as c5  # noqa: E402
from src import country_briefs as cb  # noqa: E402
from src import pl_store  # noqa: E402

QUIET = lambda *a, **k: None  # noqa: E731
TODAY = "2026-10-10"

STANCE = c5.header("pl") + """
bill_directions:
  - key: "10/2110"
    direction: against
    status: draft
    areas: [9]
    why: "Registered cohabitation contracts."
    drafted: "test"

divisions:
"""

WATCHLIST = """processes:
  "10/2110": {areas: [9], why: "Registered cohabitation contracts."}
"""

PROCESSES = [
    # key, title, start, last stage, last stage date, areas, tier, passed
    ("10/2110", "Rządowy projekt ustawy o statusie osoby najbliższej", "2025-12-30",
     "Rozpatrywanie wniosku Prezydenta", "2026-09-17", [9], 2, 0),
    ("10/2600", "Poselski projekt ustawy o ochronie życia", "2026-08-01", "I czytanie", "2026-09-01",
     [1], 1, 0),
    ("10/2700", "Poselski projekt ustawy o czymś innym", "2026-08-01", "I czytanie", "2026-09-01",
     [7], 2, 0),
    ("10/2800", "Rządowy projekt ustawy już uchwalony", "2026-06-01", "Prezydent podpisał ustawę",
     "2026-09-20", [1], 1, 1),
    ("10/100", "Obywatelski projekt ustawy stary", "2021-01-01", "I czytanie", "2021-02-01", [1], 1, 0),
]
DIVS = [
    ("pl-10-58-62", 62, "głosowanie nad całością projektu.", "2026-05-29T10:00:00", 230, 198),
    ("pl-10-58-54", 54, "wniosek o odrzucenie w całości projektu.", "2026-05-29T09:00:00", 193, 228),
    ("pl-10-58-59", 59, "poprawka 12", "2026-05-29T09:30:00", 227, 199),
    ("pl-10-65-10", 10, "głosowanie nad ponownym uchwaleniem ustawy", "2026-09-17T10:00:00", 232, 199),
]
MEMBERS = [("10/1", "Anna Adamska", "PiS"), ("10/2", "Bartosz Bielski", "KO"),
           ("10/3", "Celina Czarnecka", "PiS"), ("10/4", "Dawid Dudek", "PSL")]
VOTES = {"pl-10-58-62": {"10/1": "NO", "10/2": "YES", "10/3": "NO", "10/4": "YES"},
         "pl-10-58-54": {"10/1": "YES", "10/2": "NO", "10/3": "YES", "10/4": "NO"},
         "pl-10-65-10": {"10/1": "NO", "10/2": "YES", "10/3": "ABSENT", "10/4": "YES"}}


def make_store(path):
    conn = sqlite3.connect(path)
    pl_store.ensure_schema(conn)
    for key, title, start, stage, sdate, areas, tier, passed in PROCESSES:
        conn.execute("INSERT INTO pl_processes (process_key, term, number, title, document_type, "
                     "start_date, passed, last_stage, last_stage_date, areas, tier) VALUES "
                     "(?,10,?,?,?,?,?,?,?,?,?)",
                     (key, key.split("/")[1], title, "projekt ustawy", start, passed, stage, sdate,
                      json.dumps(areas), tier))
    for key, number, topic, voted, yes, no in DIVS:
        conn.execute("INSERT INTO pl_divisions (division_key, term, sitting, number, voted_at, "
                     "title, topic, process_keys, areas, tier, yes, no) VALUES "
                     "(?,10,58,?,?,?,?,?,?,?,?,?)",
                     (key, number, voted, "Pkt. 5 Sprawozdanie Komisji", topic,
                      json.dumps(["10/2110"]), json.dumps([9]), 2, yes, no))
    for mp, name, club in MEMBERS:
        conn.execute("INSERT INTO pl_members (mp_key, term, mp_id, name, club, active) "
                     "VALUES (?,10,?,?,?,1)", (mp, int(mp.split("/")[1]), name, club))
    for key, got in VOTES.items():
        for mp, pos in got.items():
            club = dict((m, c) for m, _, c in MEMBERS)[mp]
            conn.execute("INSERT INTO pl_votes (division_key, mp_key, position, club) "
                         "VALUES (?,?,?,?)", (key, mp, pos, club))
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.cfg_dir = os.path.join(t, "config")
        self.out = os.path.join(t, "briefs")
        self.ledger = os.path.join(t, "ledger")
        os.makedirs(self.cfg_dir)
        with open(os.path.join(self.cfg_dir, "pl_stance.yaml"), "w", encoding="utf-8") as h:
            h.write(STANCE)
        with open(os.path.join(self.cfg_dir, "watchlist-pl.yaml"), "w", encoding="utf-8") as h:
            h.write(WATCHLIST)
        self.conn = make_store(os.path.join(t, "store.db"))
        self.cfg = cb.load_config()
        # These tests check the country-language phrases; the shipped config
        # writes English (rule 6), so pin the local mode here.
        self.cfg["language"] = "local"
        wl = {"10/2110": {"areas": [9]}}
        c5.draft(self.conn, "pl", self.cfg_dir, TODAY, QUIET, wl=wl)
        self._wl = c5.SPECS["pl"].watchlist_fn
        c5.SPECS["pl"].watchlist_fn = lambda: wl
        cb._QUAL.clear()

    def tearDown(self):
        c5.SPECS["pl"].watchlist_fn = self._wl
        self.conn.close()
        self.tmp.cleanup()

    def run_step(self, **kw):
        return cb.run(self.conn, "pl", self.cfg, kw.pop("today", TODAY), self.out, self.ledger,
                      self.cfg_dir, log=QUIET, **kw)

    def read(self, suffix=".md"):
        names = [n for n in os.listdir(self.out) if n.startswith("pl-") and "10-2110" in n
                 and n.endswith(suffix) and (suffix != ".csv" or not n.endswith("-5ca.csv"))]
        self.assertEqual(len(names), 1, names)
        with open(os.path.join(self.out, names[0]), encoding="utf-8") as h:
            return h.read()

    def confirm_all(self):
        c5.confirm_direction("pl", ["10/2110"], "Christopher", TODAY, self.cfg_dir, QUIET)
        path = c5.stance_path("pl", self.cfg_dir)
        with open(path, encoding="utf-8") as h:
            text = h.read()
        # the amendment needs reading: a person writes its values first
        text = text.replace("status: needs_reading", "status: draft\n    yea: 0\n    nay: 0\n"
                            "    placeable: false\n    reason: \"test\"")
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        entries, _, _ = c5.load("pl", self.cfg_dir)
        c5.confirm("pl", [k for k, e in entries.items() if e.get("status") == "draft"],
                   "Christopher", TODAY, self.cfg_dir, QUIET)


class SubjectTests(Base):
    def test_watched_and_tier1_live_recent_bills_only(self):
        subs = {s["key"]: s for s in cb.subjects(self.conn, "pl", TODAY, config_dir=self.cfg_dir)}
        self.assertIn("10/2110", subs)                 # watched (tier 2), voted in September
        self.assertIn("10/2600", subs)                 # tier 1, moved in September
        self.assertNotIn("10/2700", subs)              # tier 2, unwatched
        self.assertNotIn("10/2800", subs)              # passed: no campaign subject
        self.assertTrue(subs["10/2110"]["recent"] and subs["10/2110"]["watched"])
        self.assertFalse(subs["10/100"]["recent"])     # live but quiet since 2021
        self.assertEqual(subs["10/2110"]["last_date"], "2026-09-17")

    def test_slug_is_folded_and_keyed(self):
        self.assertEqual(cb.slug_for("pl", "Rządowy projekt ustawy", "10/2110"),
                         "pl-rzadowy-projekt-ustawy-10-2110")

    def test_working_days_skip_weekends(self):
        fri = datetime.date(2026, 10, 9)
        self.assertEqual(cb.add_working_days(fri, 3), datetime.date(2026, 10, 14))
        self.assertEqual(cb.add_working_days(datetime.date(2026, 10, 14), -2), datetime.date(2026, 10, 12))


class NotReadyTests(Base):
    def test_unconfirmed_brief_is_not_ready_and_places_nobody(self):
        got = self.run_step()
        self.assertEqual(got["new"], 2)
        md = self.read()
        self.assertIn("NIEGOTOWE", md)                               # Polish banner
        self.assertIn("(EN) NOT READY: awaiting sign-off.", md)
        self.assertIn("NOT READY: awaiting sign-off", md)           # the form's Notes line
        self.assertIn("5CA czeka na zatwierdzenie", md)
        self.assertIn("[CAMPAIGNER: apel, gdy stanowisko CitizenGO", md)   # no ask from a draft
        self.assertNotIn("Głosować przeciw", md)
        self.assertNotIn("Possible Survival", md)
        self.assertFalse([n for n in os.listdir(self.out) if n.endswith("-5ca.csv")])
        self.assertIn("is a DRAFT", md)
        self.assertNotIn("—", md)
        row = self.conn.execute("SELECT status FROM brief_log WHERE slug LIKE 'pl-%-10-2110'").fetchone()
        self.assertEqual(row[0], "not-ready")

    def test_csv_keeps_the_template_rows(self):
        self.run_step()
        rows = list(csv.reader(io.StringIO(self.read(".csv"))))
        self.assertEqual(rows[0][:5], ["Campaign Name", "Campaigner", "Date of Submission", "Urgency",
                                       "List"])
        self.assertEqual(rows[1][4], "PL")
        labels = [r[0] for r in rows if r]
        for want in ("GENERAL INFORMATION", "RED FOX FOUR", "EVALUATE DASHBOARD", "BUILDER TAB",
                     "What are we asking for in the petition?", "TOTAL IF WE WIN"):
            self.assertIn(want, labels)

    def test_one_brief_per_subject_and_quiet_bills_wait(self):
        self.run_step()
        again = self.run_step()
        self.assertEqual((again["new"], again["refreshed"]), (0, 0))
        names = [n for n in os.listdir(self.out) if n.endswith(".md")]
        self.assertFalse([n for n in names if "10-100" in n])           # quiet: no brief
        got = self.run_step(subject_keys=["10/100"])
        self.assertEqual(got["new"], 1)

    def test_max_new_caps_a_run(self):
        got = self.run_step(max_new=1)
        self.assertEqual((got["new"], got["waiting"]), (1, 1))

    def test_rejected_slug_is_never_written(self):
        subs = cb.subjects(self.conn, "pl", TODAY, config_dir=self.cfg_dir)
        slug = [s["slug"] for s in subs if s["key"] == "10/2600"][0]
        cb.make_briefs().ensure_log(self.conn)
        self.conn.execute("INSERT INTO brief_log (slug, subject, generated_at, path, status) "
                          "VALUES (?,?,?,?,?)", (slug, "x", TODAY, "x", "rejected"))
        self.run_step()
        self.assertFalse(os.path.exists(os.path.join(self.out, slug + ".md")))


class KeyDateTests(Base):
    def test_an_official_date_too_close_proposes_urgent_and_a_ladder(self):
        s = [x for x in cb.subjects(self.conn, "pl", TODAY, config_dir=self.cfg_dir)
             if x["key"] == "10/2110"][0]
        s["next_date"] = "2026-10-20"
        b = cb.build(self.conn, "pl", s, self.cfg, TODAY, config_dir=self.cfg_dir)
        self.assertEqual(dict(b["header"])["Urgency"], "Urgent")
        prepare = dict((k, v) for k, v, _ in b["prepare"])
        self.assertIn("**Start (", prepare["Why is it urgent that we take action now?"])
        general = dict((k, v) for k, v, _ in b["general"])
        self.assertIn("2026-10-16", general["Estimated date for Delivering Signatures"])
        s["next_date"] = "2026-12-15"
        b = cb.build(self.conn, "pl", s, self.cfg, TODAY, config_dir=self.cfg_dir)
        self.assertEqual(dict(b["header"])["Urgency"], "Non-Urgent")

    def test_no_date_means_no_invented_deadline(self):
        s = [x for x in cb.subjects(self.conn, "pl", TODAY, config_dir=self.cfg_dir)
             if x["key"] == "10/2110"][0]
        b = cb.build(self.conn, "pl", s, self.cfg, TODAY, config_dir=self.cfg_dir)
        self.assertEqual(dict(b["header"])["Urgency"], "Non-Urgent")
        prepare = dict((k, v) for k, v, _ in b["prepare"])
        self.assertTrue(prepare["Why is it urgent that we take action now?"].startswith("[CAMPAIGNER:"))


class ConfirmedTests(Base):
    def test_confirmations_reach_an_unedited_brief_next_week(self):
        self.run_step()
        self.confirm_all()
        got = self.run_step(today="2026-10-17")
        self.assertEqual((got["refreshed"], got["now_ready"]), (1, 1))
        md = self.read()
        self.assertIn("GOTOWE", md)
        self.assertIn("Głosować przeciw", md)                      # the ask, from the CONFIRMED direction
        self.assertIn("now READY", md)
        self.assertIn("Analiza pięciu kolumn", md)
        fca = self.read("-5ca.csv")
        self.assertIn("SECTION 1: TARGETS", fca)
        self.assertIn("SECTION 2: ALL MEMBERS", fca)
        rows = list(csv.reader(io.StringIO(fca)))
        anna = [r for r in rows if r and r[0].startswith("Anna Adamska")]
        self.assertEqual(anna[-1][2], "1")                         # ++: voted against the bill
        self.assertEqual(anna[-1][7], "N")
        bart = [r for r in rows if r and r[0].startswith("Bartosz Bielski")]
        self.assertEqual(bart[-1][6], "1")                         # --
        row = self.conn.execute("SELECT status FROM brief_log WHERE slug LIKE 'pl-%-10-2110'").fetchone()
        self.assertEqual(row[0], "draft")

    def test_a_draft_reading_still_blocks_ready(self):
        c5.confirm_direction("pl", ["10/2110"], "Christopher", TODAY, self.cfg_dir, QUIET)
        self.run_step()
        md = self.read()
        self.assertIn("NIEGOTOWE", md)
        self.assertIn("Głosować przeciw", md)        # the direction is confirmed: the ask may show
        self.assertIn("Odczyty jego głosowań czekające na potwierdzenie", md)

    def test_an_edited_brief_is_left_alone_unless_forced(self):
        self.run_step()
        path = [os.path.join(self.out, n) for n in os.listdir(self.out)
                if "10-2110" in n and n.endswith(".md")][0]
        with open(path, "a", encoding="utf-8") as h:
            h.write("\nA campaigner's note.\n")
        self.confirm_all()
        got = self.run_step(today="2026-10-17")
        self.assertEqual((got["edited"], got["refreshed"]), (1, 0))
        self.assertIn("campaigner's note", open(path, encoding="utf-8").read())
        got = self.run_step(today="2026-10-17", force=["10/2110"])
        self.assertEqual(got["refreshed"], 1)
        self.assertIn("rewritten (--force)", open(path, encoding="utf-8").read())

    def test_withdrawn_confirmation_removes_the_5ca_sheet(self):
        self.confirm_all()
        self.run_step()
        self.assertTrue(self.read("-5ca.csv"))
        path = c5.stance_path("pl", self.cfg_dir)
        text = open(path, encoding="utf-8").read().replace("status: confirmed", "status: draft")
        open(path, "w", encoding="utf-8").write(text)
        self.run_step(today="2026-10-17")
        self.assertFalse([n for n in os.listdir(self.out) if n.endswith("-5ca.csv")])
        self.assertIn("NOT READY again", self.read())


class LanguageTests(Base):
    def test_english_switch(self):
        self.cfg["language"] = "en"
        self.run_step()
        md = self.read()
        self.assertIn("**NOT READY: awaiting sign-off.", md)
        self.assertNotIn("(EN)", md)

    def test_every_language_has_every_phrase_and_placeholder(self):
        en = brief_phrases.EN
        for lang, table in brief_phrases.LANGUAGES.items():
            self.assertEqual(set(table), set(en), lang)
            for k, v in table.items():
                fields = {f for _, f, _, _ in string.Formatter().parse(v) if f}
                want = {f for _, f, _, _ in string.Formatter().parse(en[k]) if f}
                self.assertEqual(fields, want, (lang, k))
                self.assertNotIn("—", v, (lang, k))

    def test_swiss_german_writes_ss(self):
        got = brief_phrases.phrases("de", swiss=True)
        self.assertFalse([k for k, v in got.items() if "ß" in v])

    def test_every_configured_country_has_a_phrase_table_and_list(self):
        for cc, c in self.cfg["countries"].items():
            self.assertIn(c["lang"], brief_phrases.LANGUAGES, cc)
            self.assertTrue(c.get("list"), cc)


class DirectionSignOffTests(Base):
    def test_confirm_direction_needs_a_named_signer(self):
        with self.assertRaises(SystemExit):
            c5.confirm_direction("pl", ["10/2110"], "", TODAY, self.cfg_dir, QUIET)
        with self.assertRaises(SystemExit):
            c5.confirm_direction("pl", ["10/2110"], "Somebody Else", TODAY, self.cfg_dir, QUIET)
        self.assertFalse(c5.direction_confirmed(c5.load("pl", self.cfg_dir)[1]["10/2110"]))
        ok = c5.confirm_direction("pl", ["10/2110", "10/9999"], "Christopher", TODAY, self.cfg_dir, QUIET)
        self.assertEqual(ok, ["10/2110"])
        b = c5.load("pl", self.cfg_dir)[1]["10/2110"]
        self.assertTrue(c5.direction_confirmed(b))
        self.assertEqual((b["confirmed_by"], b["confirmed_on"]), ("Christopher", TODAY))
        # the divisions section is untouched
        self.assertFalse([e for e in c5.load("pl", self.cfg_dir)[0].values()
                          if e.get("status") == "confirmed"])


class ToolTests(Base):
    def test_cli_list_and_scratch_run(self):
        spec = importlib.util.spec_from_file_location(
            "country_briefs_tool", os.path.join(ROOT, "tools", "country_briefs.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        db = os.path.join(self.tmp.name, "store.db")
        mp = os.path.join(self.tmp.name, "map.txt")
        with open(mp, "w") as h:
            h.write("pl {0}\n".format(db))
        self.conn.commit()
        rc = tool.main(["--db-map", mp, "--list", "--today", TODAY, "--config-dir", self.cfg_dir,
                        "--ledger-dir", self.ledger])
        self.assertEqual(rc, 0)
        rc = tool.main(["--db-map", mp, "--no-log", "--today", TODAY, "--config-dir", self.cfg_dir,
                        "--ledger-dir", self.ledger, "--out-dir", self.out])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(cb.ledger_path("pl", self.ledger)))


class WiringTests(unittest.TestCase):
    def test_each_configured_country_job_runs_the_step_and_commits_briefs(self):
        cfg = cb.load_config()
        for cc in cfg["countries"]:
            # Mexico collects on GitHub (X9): its Mini job only dispatches.
            job = "mx-collect.sh" if cc == "mx" else "{0}-weekly.sh".format(cc)
            text = open(os.path.join(ROOT, "jobs", job), encoding="utf-8").read()
            self.assertIn("tools/country_briefs.py --cc {0}".format(cc), text, cc)
            if cc != "mx":
                self.assertRegex(text, r"# mini_run: commit .*\bbriefs\b", cc)
            wf = os.path.join(ROOT, ".github", "workflows", "{0}-weekly.yml".format(cc))
            if os.path.exists(wf):
                self.assertIn("briefs/", open(wf, encoding="utf-8").read(), cc)


if __name__ == "__main__":
    unittest.main()


class LanguageDecisionTests(unittest.TestCase):
    def test_shipped_config_writes_english_per_rule_6(self):
        # Chris, 10 October 2026: "keep briefs in English per rule 6".
        self.assertEqual(cb.load_config().get("language"), "en")
