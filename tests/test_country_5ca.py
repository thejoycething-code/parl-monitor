"""5CA with stance sign-off for the new countries (src/country5ca.py,
tools/country_5ca.py, tools/stance_digest.py). Small temporary stores; no
network, no Slack."""

import csv
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import at_store, pl_store  # noqa: E402
from src import country5ca as c5  # noqa: E402
from src import readings5ca as r5  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


digest_tool = _load("stance_digest")
QUIET = lambda *a, **k: None  # noqa: E731

PL_STANCE = c5.header("pl") + """
bill_directions:
  - key: "10/2110"
    direction: against
    status: draft
    areas: [9]
    why: "Registered cohabitation contracts."
    drafted: "test"

divisions:
"""

PL_DIVS = [
    # key, number, topic, process_keys, areas, tier, yes, no
    ("pl-10-1-1", 1, "głosowanie nad całością projektu.", ["10/2110"], [9], 1, 230, 198),
    ("pl-10-1-2", 2, "poprawka 1", ["10/2110"], [9], 1, 200, 220),
    ("pl-10-1-3", 3, "wniosek o uzupełnienie porządku dziennego.", ["10/2110"], [9], 1, 240, 190),
    ("pl-10-1-4", 4, "wniosek o odrzucenie w całości projektu.", ["10/2110"], [9], 1, 193, 228),
    ("pl-10-1-5", 5, "głosowanie nad całością projektu.", ["10/50"], [7], 2, 300, 100),
    ("pl-10-1-6", 6, "głosowanie nad całością projektu.", ["10/999"], [1], 1, 210, 220),
]
PL_MEMBERS = [("10/1", "Anna Adamska", "PiS"), ("10/2", "Bartosz Bielski", "KO"),
              ("10/3", "Celina Czarnecka", "PiS")]
PL_VOTES = {"pl-10-1-1": {"10/1": "NO", "10/2": "YES", "10/3": "ABSENT"},
            "pl-10-1-4": {"10/1": "YES", "10/2": "NO", "10/3": "YES"},
            "pl-10-1-2": {"10/1": "YES", "10/2": "NO", "10/3": "YES"}}
PL_WL = {"10/2110": {"areas": [9]}}


def pl_store_at(path):
    conn = sqlite3.connect(path)
    pl_store.ensure_schema(conn)
    for key, number, topic, procs, areas, tier, yes, no in PL_DIVS:
        conn.execute("INSERT INTO pl_divisions (division_key, term, sitting, number, voted_at, "
                     "title, topic, process_keys, areas, tier, yes, no) VALUES "
                     "(?,10,1,?,?,?,?,?,?,?,?,?)",
                     (key, number, "2026-05-29T10:00:00", "Pkt. 5 Sprawozdanie", topic,
                      json.dumps(procs), json.dumps(areas), tier, yes, no))
    for mp, name, club in PL_MEMBERS:
        conn.execute("INSERT INTO pl_members (mp_key, term, mp_id, name, club, active) "
                     "VALUES (?,10,?,?,?,1)", (mp, int(mp.split("/")[1]), name, club))
    for key, got in PL_VOTES.items():
        for mp, pos in got.items():
            club = dict((m, c) for m, _, c in PL_MEMBERS)[mp]
            conn.execute("INSERT INTO pl_votes (division_key, mp_key, position, club) "
                         "VALUES (?,?,?,?)", (key, mp, pos, club))
    conn.commit()
    conn.close()
    return c5.connect_ro(path)


def read_csv(path):
    with open(path, encoding="utf-8") as h:
        return list(csv.reader(h))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.tmp.name, "config")
        self.docs = os.path.join(self.tmp.name, "docs")
        self.out = os.path.join(self.tmp.name, "5ca")
        os.makedirs(self.cfg)
        os.makedirs(self.docs)
        with open(os.path.join(self.cfg, "pl_stance.yaml"), "w", encoding="utf-8") as h:
            h.write(PL_STANCE)
        self.conn = pl_store_at(os.path.join(self.tmp.name, "store.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def draft(self, today="2026-10-10"):
        return c5.draft(self.conn, "pl", self.cfg, today, QUIET, wl=PL_WL)

    def entries(self):
        return c5.load("pl", self.cfg)[0]


class DrafterTests(Base):
    def test_watched_and_tier1_votes_are_drafted_by_kind(self):
        got = self.draft()
        self.assertEqual(got["new"], 5)               # the tier-2 unwatched vote is not
        e = self.entries()
        self.assertNotIn("pl-10-1-5", e)
        final = e["pl-10-1-1"]
        self.assertEqual((final["status"], final["vote_kind"], final["yea"], final["nay"]),
                         ("draft", "final", -2, 2))
        self.assertIn("AGAINST", final["reasoning"])
        self.assertIn("Area 9", final["reasoning"])
        reject = e["pl-10-1-4"]
        self.assertEqual((reject["vote_kind"], reject["yea"], reject["nay"]), ("reject", 2, -2))
        amend = e["pl-10-1-2"]
        self.assertEqual((amend["status"], amend.get("yea")), ("needs_reading", None))
        self.assertIn("amendment", amend["read_first"])
        proc = e["pl-10-1-3"]
        self.assertEqual((proc["status"], proc["placeable"]), ("draft", False))

    def test_no_direction_means_needs_reading_never_a_guess(self):
        self.draft()
        e = self.entries()["pl-10-1-6"]
        self.assertEqual(e["status"], "needs_reading")
        self.assertIsNone(e.get("yea"))
        self.assertIn("no bill direction is on file", e["read_first"])

    def test_redraft_appends_nothing_and_never_rewrites(self):
        self.draft()
        path = c5.stance_path("pl", self.cfg)
        with open(path, encoding="utf-8") as h:
            text = h.read().replace("yea: -2", "yea: -1", 1)
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        got = self.draft("2026-10-17")
        self.assertEqual(got["new"], 0)
        with open(path, encoding="utf-8") as h:
            self.assertEqual(h.read(), text)

    def test_lobbies_are_counted_from_positions(self):
        self.draft()
        self.assertIn("Za: KO 1", self.entries()["pl-10-1-1"]["lobbies"])

    def test_refuses_when_divisions_is_not_last(self):
        path = c5.stance_path("pl", self.cfg)
        with open(path, "a", encoding="utf-8") as h:
            h.write("\nlater: []\n")
        with self.assertRaises(SystemExit):
            self.draft()


class SignOffTests(Base):
    def setUp(self):
        super().setUp()
        self.draft()

    def test_confirm_needs_a_named_signer(self):
        with self.assertRaises(SystemExit):
            c5.confirm("pl", ["pl-10-1-1"], "", config_dir=self.cfg, log=QUIET)
        with self.assertRaises(SystemExit):
            c5.confirm("pl", ["pl-10-1-1"], "Somebody Else", config_dir=self.cfg, log=QUIET)

    def test_confirm_stamps_person_and_date(self):
        ok = c5.confirm("pl", ["pl-10-1-1"], "Christopher", "2026-10-10", self.cfg, log=QUIET)
        self.assertEqual(ok, ["pl-10-1-1"])
        e = self.entries()["pl-10-1-1"]
        self.assertEqual((e["status"], e["confirmed_by"], e["confirmed_on"]),
                         ("confirmed", "Christopher", "2026-10-10"))
        self.assertEqual(r5.status(e), "confirmed")

    def test_needs_reading_cannot_be_confirmed(self):
        msgs = []
        ok = c5.confirm("pl", ["pl-10-1-2"], "Christopher", config_dir=self.cfg, log=msgs.append)
        self.assertEqual(ok, [])
        self.assertTrue(any("needs_reading" in m for m in msgs))
        self.assertEqual(self.entries()["pl-10-1-2"]["status"], "needs_reading")

    def test_guide_ticks_sign_and_survive_a_rewrite(self):
        c5.write_signoff_doc("pl", self.cfg, self.docs, QUIET)
        path = c5.doc_path("pl", self.docs)
        with open(path, encoding="utf-8") as h:
            text = h.read()
        self.assertIn("### [ ] `pl-10-1-1`", text)
        self.assertNotIn("### [ ] `pl-10-1-2`", text)          # needs reading: no box
        ticked = text.replace("### [ ] `pl-10-1-4`", "### [x] `pl-10-1-4`")
        with open(path, "w", encoding="utf-8") as h:
            h.write(ticked)
        kept = c5.write_signoff_doc("pl", self.cfg, self.docs, QUIET)   # the weekly rewrite
        self.assertEqual(kept, ["pl-10-1-4"])
        with open(path, encoding="utf-8") as h:
            self.assertIn("### [x] `pl-10-1-4`", h.read())
        ok = c5.sign_from_doc("pl", "Christopher", "2026-10-11", self.cfg, self.docs, QUIET)
        self.assertEqual(ok, ["pl-10-1-4"])
        self.assertEqual(self.entries()["pl-10-1-4"]["confirmed_on"], "2026-10-11")


class StatusTests(unittest.TestCase):
    def test_status_field(self):
        self.assertEqual(r5.status({"status": "draft", "yea": 2}), "draft")
        self.assertEqual(r5.status({"status": "needs_reading"}), "unread")
        self.assertEqual(r5.status({"status": "confirmed", "yea": 2}), "draft")   # nobody named
        self.assertEqual(r5.status({"status": "confirmed", "yea": 2, "confirmed_by": "X",
                                    "confirmed_on": "2026-10-10"}), "confirmed")
        self.assertEqual(r5.status({"status": "confirmed", "placeable": False,
                                    "confirmed_by": "X", "confirmed_on": "2026-10-10"}),
                         "unplaceable")

    def test_older_files_unchanged(self):
        self.assertEqual(r5.status({"draft": True, "yea": 2}), "draft")
        self.assertEqual(r5.status({"yea": 2}), "confirmed")
        self.assertEqual(r5.status({"read_first": "x"}), "unread")


class SheetTests(Base):
    def setUp(self):
        super().setUp()
        self.draft()
        self.sheet = c5.sheet_path("pl", "sejm", 9, self.out)

    def run_sheets(self):
        return c5.run_sheets(self.conn, "pl", self.cfg, self.out, "2026-10-10", QUIET)

    def test_no_sheet_without_a_confirmed_reading(self):
        self.assertEqual(self.run_sheets(), [])
        self.assertFalse(os.path.exists(self.sheet))

    def test_confirmed_reading_places_and_drafts_do_not(self):
        c5.confirm("pl", ["pl-10-1-1"], "Christopher", "2026-10-10", self.cfg, log=QUIET)
        self.assertEqual(self.run_sheets(), [self.sheet])
        rows = {r[0]: r for r in read_csv(self.sheet)}
        cols = ["++", "+", "0", "-", "--"]

        def column(prefix):
            row = next(v for k, v in rows.items() if k.startswith(prefix))
            return cols[[c == "1" for c in row[1:6]].index(True)]
        self.assertEqual(column("Anna Adamska"), "++")       # voted No on the whole bill
        self.assertEqual(column("Bartosz Bielski"), "--")
        self.assertEqual(column("Celina Czarnecka"), "0")    # absent; the reject vote is a draft
        celina = next(v for k, v in rows.items() if k.startswith("Celina"))
        self.assertIn("awaiting sign-off -- not placed", celina[11])
        self.assertNotIn("+2", celina[11])                   # no unconfirmed direction shown

    def test_sheet_removed_when_reading_is_no_longer_confirmed(self):
        c5.confirm("pl", ["pl-10-1-1"], "Christopher", "2026-10-10", self.cfg, log=QUIET)
        self.run_sheets()
        path = c5.stance_path("pl", self.cfg)
        with open(path, encoding="utf-8") as h:
            text = h.read().replace("status: confirmed", "status: draft")
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        self.run_sheets()
        self.assertFalse(os.path.exists(self.sheet))


class DerivedTests(unittest.TestCase):
    """Austria: only the Klub's vote is recorded; member rows are DERIVED (X5)."""

    def test_derived_rows_are_labelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "at.db")
            conn = sqlite3.connect(path)
            at_store.ensure_schema(conn)
            conn.execute("INSERT INTO at_items (item_key, gp, chamber, title, areas, tier) VALUES "
                         "('XXVIII/UEA/26', 'XXVIII', 'NR', 'Schutz der biologischen Geschlechter', "
                         "'[5]', 1)")
            conn.execute("INSERT INTO at_divisions (division_key, item_key, date, body, question, "
                         "areas) VALUES ('k1', 'XXVIII/UEA/26', '2025-03-27', 'NR', "
                         "'Unselbständiger Entschließungsantrag', '[5]')")
            conn.executemany("INSERT INTO at_votes (division_key, klub, position) VALUES (?,?,?)",
                             [("k1", "FPÖ", "Dafür"), ("k1", "ÖVP", "Dagegen")])
            conn.executemany("INSERT INTO at_members (pad, name, chamber, klub) VALUES (?,?,?,?)",
                             [("1", "Frau F", "NR", "FPÖ"), ("2", "Herr G", "NR", "FPÖ"),
                              ("3", "Frau O", "NR", "ÖVP")])
            conn.commit()
            conn.close()
            cfg = os.path.join(tmp, "config")
            os.makedirs(cfg)
            with open(os.path.join(cfg, "at_stance.yaml"), "w", encoding="utf-8") as h:
                h.write(c5.header("at") + """
bill_directions:
  - key: "XXVIII/UEA/26"
    direction: with
    status: draft
    why: "Protects the two biological sexes."

divisions:
""")
            ro = c5.connect_ro(path)
            c5.draft(ro, "at", cfg, "2026-10-10", QUIET, wl={"XXVIII/UEA/26": {}})
            e = c5.load("at", cfg)[0]["k1"]
            self.assertEqual((e["yea"], e["nay"]), (2, -2))
            self.assertIn("DERIVED", e["lobbies"])
            c5.confirm("at", ["k1"], "Christopher", "2026-10-10", cfg, log=QUIET)
            out = os.path.join(tmp, "5ca")
            written = c5.run_sheets(ro, "at", cfg, out, "2026-10-10", QUIET)
            rows = read_csv(written[0])
            frau = next(r for r in rows if r[0].startswith("Frau F"))
            self.assertIn("[DERIVED]", frau[0])
            self.assertEqual(frau[1], "1")                   # ++
            self.assertIn("derived", frau[8])
            self.assertIn("X5", rows[-1][0])
            ro.close()


class VoteKindTests(unittest.TestCase):
    CASES = [
        ("głosowanie nad całością projektu.", "final"),
        ("wniosek o odrzucenie projektu w pierwszym czytaniu.", "reject"),
        ("poprawka 12", "amendment"),
        ("wniosek o uzupełnienie porządku dziennego.", "procedural"),
        ("l'ensemble de la proposition de loi relative au droit à l'aide à mourir", "final"),
        ("l'amendement n° 12 de M. Juvin à l'article 2", "amendment"),
        ("la motion de rejet préalable, déposée par M. Hetzel", "reject"),
        ("Votazione finale", "final"),
        ("Votazione questione pregiudiziale", "reject"),
        ("DDL 2423-A E AB - Q PREG COST 1,2,3 - Votazione", "reject"),
        ("Schlussabstimmung", "final"),
        ("Votação na generalidade:", "final"),
        ("Requerimento dispensa redação final: Requerimento oral", "procedural"),
        ("Votación conjunta de las enmiendas a la totalidad de devolución", "reject"),
        ("Votación separada por puntos. Punto 1. Proposición no de Ley", "amendment"),
        ("Aprovada, em primeiro turno, a Proposta de Emenda à Constituição nº 5", "final"),
        ("DECRETO POR EL QUE SE REFORMAN ... (EN LO GENERAL Y EN LO PARTICULAR)", "final"),
        ("Hlasovanie o návrhu zákona ako o celku.", "final"),
        ("Motie: Motie van het lid Piri c.s. over de regenboogvlag", "final"),
        ("Amendement: Gewijzigd amendement van het lid Faber", "amendment"),
        ("Geheel van het wetsvoorstel tot flexibilisering", "final"),
        ("önálló indítvány minősített többséget igénylő része elfogadva", "final"),
        ("Fiducia conversione decreto", "other"),
    ]

    def test_kinds(self):
        for text, want in self.CASES:
            self.assertEqual(c5.vote_kind(text)[0], want, text)

    def test_store_flag_wins(self):
        self.assertEqual(c5.vote_kind("PRIJEDLOG ZAKONA, prvo čitanje", "inverted")[0], "inverted")

    def test_motion_in_a_dossier_is_its_own_text(self):
        bills = {"36416": {"direction": "against", "why": "Lifts the embryo ban."}}
        row = {"key": "b1", "question": "Motie: Motie van de leden Bikker over onderzoek",
               "subject": "Embryowet", "areas": "[10]", "tier": 1, "watch_key": "36416",
               "zaak_nummer": "2025Z1", "dossiers": '["36416"]', "date": "2025-12-09",
               "chamber": "tk"}
        e = c5.draft_entry("nl", row, bills, [], "2026-10-10")
        self.assertEqual(e["status"], "needs_reading")
        self.assertIn("its own text", e["read_first"])


class SpecTests(unittest.TestCase):
    def test_every_spec_query_runs_on_the_schema(self):
        from src import db
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.init_db(db.connect(os.path.join(tmp, "s.db")))
            for cc, spec in c5.SPECS.items():
                conn.execute(spec.div_sql).fetchall()
                conn.execute(spec.roster_sql).fetchall()
                if spec.positions_sql:
                    conn.execute(spec.positions_sql, ("x",)).fetchall()
            conn.close()

    def test_every_country_has_a_stance_file_that_parses(self):
        for cc in c5.COUNTRIES:
            divs, bills, _ = c5.load(cc)
            self.assertTrue(os.path.exists(c5.stance_path(cc)), cc)
            for k, e in divs.items():
                self.assertIn(e.get("status"), ("draft", "needs_reading", "confirmed"), (cc, k))
                if e.get("status") == "confirmed":
                    self.assertTrue(e.get("confirmed_by") and e.get("confirmed_on"), (cc, k))
            for k, b in bills.items():
                self.assertIn(b.get("direction"), ("with", "against"), (cc, k))


class DigestTests(Base):
    def test_digest_lists_country_and_sends_once_a_week(self):
        self.draft()
        text = c5.digest_text("2026-10-11", self.cfg, self.docs, countries=("pl",))
        self.assertIn("*Poland*", text)
        self.assertIn("2 proposed, 1 procedural, 2 need reading, 0 confirmed", text)
        self.assertIn("`pl-10-1-1`", text)
        sent = []
        state = os.path.join(self.tmp.name, "digest")
        orig = c5.digest_text
        c5.digest_text = lambda today: orig(today, self.cfg, self.docs, countries=("pl",))
        try:
            fake = lambda t: sent.append(t) or {"ok": True}  # noqa: E731
            digest_tool.main(["--dm", "--date", "2026-10-11", "--state-dir", state], send=fake)
            digest_tool.main(["--dm", "--date", "2026-10-11", "--state-dir", state], send=fake)
            digest_tool.main(["--dm", "--date", "2026-10-18", "--state-dir", state], send=fake)
        finally:
            c5.digest_text = orig
        self.assertEqual(len(sent), 2)                       # once in week 41, once in week 42

    def test_nothing_waiting_sends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(c5.digest_text("2026-10-11", tmp, tmp, countries=("pl",)))


if __name__ == "__main__":
    unittest.main()
