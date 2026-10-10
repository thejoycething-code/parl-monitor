"""Debate today and the live read for the new countries (src/country_live.py,
tools/country_debate_today.py, tools/country_live_debate.py). A small temporary
French store and a fake collector; no network, no Slack, no AI."""

import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import agenda  # noqa: E402
from src import chamber_store as cs  # noqa: E402
from src import country5ca as c5  # noqa: E402
from src import country_live as cl  # noqa: E402
from src import fr_store  # noqa: E402

QUIET = lambda *a, **k: None  # noqa: E731
DAY = "2026-10-14"
TITLE = "Proposition de loi relative au droit à l'aide à mourir"
MEMBERS = [("PA1", "Jean Dupont", "RN"), ("PA2", "Marie Martin", "LFI"),
           ("PA3", "Paul Petit", "DR"), ("PA4", "Claire Petit", "EPR")]
# One final vote on the assisted-dying bill (area 2): pour is against us.
VOTES = {"PA1": "pour", "PA2": "contre", "PA3": "contre", "PA4": "pour"}
SPEECHES = [  # speaker as printed, person id, party, excerpt
    ("M. Jean Dupont", "PA1", "RN", "Nous devons protéger les plus fragiles."),
    ("Mme Marie Martin", "PA2", "LFI", "Ce texte est une avancée pour la liberté."),
    ("M. Paul Petit", None, "DR", "Je m'interroge sur les garde-fous."),
    ("Mme Agnès Ministre", None, None, "Le Gouvernement soutient ce texte."),
]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_store(path, with_agenda=False):
    conn = sqlite3.connect(path)
    fr_store.ensure_schema(conn)
    groups = {}
    for i, (ref, name, grp) in enumerate(MEMBERS):
        org = groups.setdefault(grp, "PO{0}".format(len(groups) + 1))
        conn.execute("INSERT OR IGNORE INTO fr_groups (organe_ref, chamber, abbr) VALUES (?,?,?)",
                     (org, "an", grp))
        conn.execute("INSERT INTO fr_members (acteur_ref, chamber, name, group_ref, current) "
                     "VALUES (?,?,?,?,1)", (ref, "an", name, org))
    conn.execute("INSERT INTO fr_divisions (division_key, chamber, legislature, number, date, "
                 "result, title, dossier_ref, pour, contre, abstentions, areas, own_areas, tier) "
                 "VALUES ('an-17-1','an',17,1,'2026-05-27','adopté',"
                 "'l''ensemble de la proposition de loi relative au droit à l''aide à mourir "
                 "(première lecture).','DLR1',2,2,0,'[2]','[2]',1)")
    for ref, pos in VOTES.items():
        conn.execute("INSERT INTO fr_votes (division_key, acteur_ref, position, group_ref) "
                     "VALUES ('an-17-1',?,?,?)", (ref, pos, groups[dict(
                         (m[0], m[2]) for m in MEMBERS)[ref]]))
    if with_agenda:
        agenda.ensure_schema(conn)
        conn.execute("INSERT INTO country_agenda (cc, item_id, date, time, body, kind, title, refs, "
                     "bill_keys, areas, own_areas, tier, watch_keys) VALUES "
                     "('fr','a1',?,'15:00','Séance publique','plenary',?, '[\"DLR1\"]','[]',"
                     "'[2]','[2]',1,'[\"DLR1\"]')", (DAY, "Aide à mourir (suite)"))
        conn.execute("INSERT INTO country_agenda_runs (cc, run_date, items) VALUES ('fr',?,1)", (DAY,))
    conn.commit()
    conn.close()


def stance(cfg, status="confirmed"):
    signed = ('    confirmed_by: "Christopher"\n    confirmed_on: "2026-10-10"\n'
              if status == "confirmed" else "")
    with open(c5.stance_path("fr", cfg), "w", encoding="utf-8") as h:
        h.write(c5.header("fr") + """
bill_directions:

divisions:
  - key: "an-17-1"
    status: {0}
{1}    areas: [2]
    yea: -2
    why_yea: "For assisted dying."
    nay: 2
    why_nay: "Against assisted dying."
""".format(status, signed))


def fake_fetch(speeches=SPEECHES, title=TITLE, date=DAY):
    def fetch(run):
        for i, (who, pid, party, words) in enumerate(speeches):
            run.speech({"speech_id": "s#{0}".format(i), "doc_id": "d1", "date": date,
                        "chamber": None, "debate_id": cs.short_id(title), "debate": title,
                        "speaker": who, "party": party, "role": "member" if party else "ministre",
                        "person_id": pid, "text": words, "url": "u"},
                       cs.Match([2], ["aide à mourir"], 1, words))
        run.speech({"speech_id": "old", "doc_id": "d0", "date": "2026-10-13", "chamber": None,
                    "debate_id": "x", "debate": "Hier", "speaker": "M. Hier", "party": "RN",
                    "role": "member", "person_id": None, "text": "", "url": "u"},
                   cs.Match([2], [], 1, "hier"))
        run.read("d1", "speeches", date, None, 40, len(speeches), 1000)
    return fetch


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "store.db")
        self.cfg = os.path.join(self.tmp.name, "config")
        os.makedirs(self.cfg)
        make_store(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def live(self, reads=None, status="draft"):
        stance(self.cfg, status)
        speeches, docs, gaps = cl.read_day("fr", DAY, None, self.db, log=QUIET, fetch=fake_fetch())
        debate = cl.debates(speeches)[0]
        conn = c5.connect_ro(self.db)
        rows, divs = cl.assess(conn, "fr", debate, DAY, reads or {}, self.cfg, {})
        conn.close()
        return debate, rows, divs, cl.render("fr", DAY, debate, rows, divs)


class QualifyTests(unittest.TestCase):
    def test_every_qualifying_country_has_a_speech_collector(self):
        for cc in cl.QUALIFYING:
            self.assertIn("speeches", cs.COUNTRIES[cc], cc)
            self.assertTrue(os.path.exists(os.path.join(ROOT, "tools", cc + "_chamber.py")))
            self.assertIn(cc, c5.SPECS)

    def test_austria_and_question_only_countries_do_not(self):
        for cc in ("at", "pl", "br", "pt"):
            self.assertNotIn(cc, cl.QUALIFYING)
            self.assertIn(cc, cl.NOT_QUALIFYING)
        with self.assertRaises(ValueError):
            cl.read_day("at", DAY, None, None, log=QUIET, fetch=lambda run: None)

    def test_list_command(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = _load("country_debate_today").main(["--list"])
        self.assertEqual(rc, 0)
        self.assertIn("at  provisional protocol", out.getvalue())


class DebateTodayTests(Base):
    def test_store_is_never_written(self):
        before = os.path.getmtime(self.db), os.path.getsize(self.db)
        cl.read_day("fr", DAY, None, self.db, log=QUIET, fetch=fake_fetch())
        self.assertEqual(before, (os.path.getmtime(self.db), os.path.getsize(self.db)))
        conn = sqlite3.connect(self.db)
        self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='fr_speeches'")
                          .fetchone())

    def test_only_the_day_and_key_line(self):
        text, rows, published = cl.day("fr", DAY, None, self.db, key=4, log=QUIET, fetch=fake_fetch())
        self.assertTrue(published)
        self.assertEqual(len(rows), 1)                        # yesterday's speech left out
        self.assertEqual(text.splitlines()[-1],
                         "KEY DEBATE: fr | - | {0} | {1} | 4 speakers | areas 2".format(
                             TITLE, cs.short_id(TITLE)))
        text, _, _ = cl.day("fr", DAY, None, self.db, key=5, log=QUIET, fetch=fake_fetch())
        self.assertEqual(text.splitlines()[-1], "KEY DEBATE: fr | none")
        self.assertIn("Agenda: not collected", text)

    def test_nothing_published(self):
        text, rows, published = cl.day("fr", DAY, None, self.db, log=QUIET, fetch=lambda run: None)
        self.assertFalse(published)
        self.assertIn("nothing published for the day yet", text)
        self.assertTrue(text.endswith("KEY DEBATE: fr | none"))

    def test_agenda_point_links_and_a_watched_point_makes_it_key(self):
        os.remove(self.db)
        make_store(self.db, with_agenda=True)
        two = SPEECHES[:2]
        text, rows, _ = cl.day("fr", DAY, None, self.db, log=QUIET,
                               fetch=fake_fetch(two, title=TITLE + " (DLR1)"))
        self.assertIn("Agenda on our ground today:", text)
        self.assertIn("(agenda point)", text)
        self.assertTrue(text.splitlines()[-1].startswith("KEY DEBATE: fr | - | " + TITLE))

    def test_watched_agenda_point_not_yet_in_the_record(self):
        os.remove(self.db)
        make_store(self.db, with_agenda=True)
        text, _, _ = cl.day("fr", DAY, None, self.db, log=QUIET, fetch=lambda run: None)
        self.assertIn("KEY DEBATE: fr | none (agenda names a watched point: Aide à mourir (suite)",
                      text)


class LiveTests(Base):
    READS = {"m. jean dupont": "with", "mme marie martin": "against"}

    def test_awaiting_sign_off_names_no_contradiction(self):
        _, rows, divs, text = self.live(reads=self.READS, status="draft")
        self.assertEqual([d["key"] for d in divs], ["an-17-1"])
        self.assertFalse(any(r["kind"] for r in rows))
        self.assertIn("AWAITING SIGN-OFF", text)
        self.assertNotIn("WOBBLE", text)
        self.assertNotIn("confirmed by", text)
        self.assertIn("voted Pour on l'ensemble", text)
        self.assertIn(": awaiting sign-off", text)

    def test_confirmed_vote_and_read_words_name_contradictions(self):
        _, rows, _, text = self.live(reads=self.READS, status="confirmed")
        kinds = {r["speaker"]: r["kind"] for r in rows}
        self.assertEqual(kinds["M. Jean Dupont"], "WOBBLE")    # sounds with us, voted pour
        self.assertEqual(kinds["Mme Marie Martin"], "SLIP")    # sounds against, voted contre
        self.assertIsNone(kinds["M. Paul Petit"])             # words not read
        self.assertIn("against us (confirmed by Christopher, 2026-10-10)", text)
        self.assertIn("words not read yet", text)
        _, rows, _, text = self.live(reads={"m. jean dupont": "against"}, status="confirmed")
        self.assertIn("words read against: in line with the confirmed vote", text)
        self.assertNotIn("AWAITING SIGN-OFF", text)

    def test_confirmed_but_unread_names_nothing(self):
        _, rows, _, _ = self.live(reads={}, status="confirmed")
        self.assertFalse(any(r["kind"] for r in rows))

    def test_derived_vote_never_names(self):
        stance(self.cfg, "confirmed")
        real = c5.positions

        def derived(conn, cc, key):
            return [dict(p, derived=True) for p in real(conn, cc, key)]
        with mock.patch.object(c5, "positions", derived):
            _, rows, _, text = self.live(reads=self.READS, status="confirmed")
        self.assertFalse(any(r["kind"] for r in rows))
        self.assertIn("never named as a contradiction", text)

    def test_members_matched_by_id_then_name(self):
        _, rows, _, text = self.live()
        how = {r["speaker"]: r["match"] for r in rows}
        self.assertEqual(how["M. Jean Dupont"], "id")
        self.assertEqual(how["M. Paul Petit"], "name")       # 'Paul Petit', not 'Claire Petit'
        self.assertIn("not matched to a member", text)        # the minister

    def test_surname_alone_is_ambiguous_unless_the_party_tells(self):
        roster = {m[0]: {"member_id": m[0], "name": m[1], "party": m[2], "sitting": 1}
                  for m in MEMBERS}
        self.assertEqual(cl.match_member(roster, "Petit")[1], "ambiguous name")
        self.assertEqual(cl.match_member(roster, "Petit", "EPR")[0]["member_id"], "PA4")

    def test_reads_template_and_round_trip(self):
        debate, rows, _, _ = self.live()
        path = os.path.join(self.tmp.name, "reads.yaml")
        text = cl.queue_text("fr", DAY, debate, rows).replace(
            '"M. Jean Dupont": ""', '"M. Jean Dupont": "with"')
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        self.assertEqual(cl.load_reads(path), {"m. jean dupont": "with"})


if __name__ == "__main__":
    unittest.main()
