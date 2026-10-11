"""Words since the last vote for the new countries (src/country_since_vote.py,
tools/country_since_vote.py, the member profiles' optional section). Small
temporary French and Dutch stores; no network, no Slack, no AI."""

import contextlib
import importlib.util
import io
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src import country5ca as c5  # noqa: E402
from src import country_since_vote as sv  # noqa: E402
from src import fr_store  # noqa: E402
from src import member_profiles as mp  # noqa: E402
from src import nl_store  # noqa: E402

QUIET = lambda *a, **k: None  # noqa: E731
MEMBERS = [("PA1", "Jean Dupont", "RN"), ("PA2", "Marie Martin", "LFI"),
           ("PA3", "Paul Petit", "DR"), ("PA4", "Claire Petit", "EPR")]
# Area 2 (assisted dying): an article vote on 2026-05-27 and the final vote the
# same day (the final is the last vote), and an older final vote in 2025.
# Pour is against us.
FINAL = {"PA1": "pour", "PA2": "contre", "PA3": "contre", "PA4": "pour"}
ARTICLE = {"PA1": "contre", "PA2": "pour", "PA3": "pour", "PA4": "contre"}
# (speech id, date, speaker, person id, party, role, areas, excerpt)
SPEECHES = [
    ("s1", "2026-05-20", "M. Jean Dupont", "PA1", "RN", "member", "[2]", "Avant le vote."),
    ("s2", "2026-06-10", "M. Jean Dupont", "PA1", "RN", "member", "[2]", "Je doute du texte."),
    ("s3", "2026-09-30", "M. Jean Dupont", "PA1", "RN", "member", "[2]", "Protégeons les fragiles."),
    ("s4", "2026-10-01", "Mme Marie Martin", "PA2", "LFI", "member", "[2]", "Une liberté."),
    ("s5", "2026-10-02", "M. Paul Petit", None, "DR", "member", "[2]", "Les garde-fous."),
    ("s6", "2026-10-02", "Mme Agnès Ministre", None, None, "ministre déléguée", "[2]", "Le Gouvernement."),
    ("s7", "2026-10-02", "M. Inconnu", None, "RN", "member", "[2]", "Qui suis-je."),
    ("s8", "2026-10-03", "Mme Claire Petit", "PA4", "EPR", "member", "[1]", "Sur l'IVG."),
    ("s9", "2026-10-03", "Mme Claire Petit", "PA4", "EPR", "member", "[11]", "Migration only."),
]


def _read(path):
    with open(path, encoding="utf-8") as h:
        return h.read()


def make_fr(path):
    conn = sqlite3.connect(path)
    fr_store.ensure_schema(conn)
    cs.ensure_schema(conn, ["fr"])
    groups = {}
    for ref, name, grp in MEMBERS:
        org = groups.setdefault(grp, "PO{0}".format(len(groups) + 1))
        conn.execute("INSERT OR IGNORE INTO fr_groups (organe_ref, chamber, abbr) VALUES (?,?,?)",
                     (org, "an", grp))
        conn.execute("INSERT INTO fr_members (acteur_ref, chamber, name, group_ref, current) "
                     "VALUES (?,?,?,?,1)", (ref, "an", name, org))
    party = {m[0]: groups[m[2]] for m in MEMBERS}
    for key, date, title, pos in (
            ("an-17-1", "2026-05-27", "l'ensemble de la proposition de loi relative à l'aide à "
                                      "mourir (première lecture).", FINAL),
            ("an-17-0", "2026-05-27", "l'article premier de la proposition de loi relative à "
                                      "l'aide à mourir.", ARTICLE),
            ("an-16-9", "2025-02-01", "l'ensemble de la proposition de loi sur la fin de vie.",
             ARTICLE)):
        conn.execute("INSERT INTO fr_divisions (division_key, chamber, legislature, number, date, "
                     "result, title, dossier_ref, pour, contre, abstentions, areas, own_areas, tier) "
                     "VALUES (?,'an',17,1,?,'adopté',?,'DLR1',2,2,0,'[2]','[2]',1)",
                     (key, date, title))
        for ref, p in pos.items():
            conn.execute("INSERT INTO fr_votes (division_key, acteur_ref, position, group_ref) "
                         "VALUES (?,?,?,?)", (key, ref, p, party[ref]))
    for sid, date, who, pid, prt, role, areas, words in SPEECHES:
        conn.execute("INSERT INTO fr_speeches (speech_id, doc_id, date, debate_id, debate, speaker, "
                     "party, role, person_id, excerpt, text, url, areas, tier) VALUES "
                     "(?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                     (sid, "d", date, "x", "Aide à mourir", who, prt, role, pid, words, words,
                      "u", areas))
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


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "store.db")
        self.cfg = os.path.join(self.tmp.name, "config")
        os.makedirs(self.cfg)
        make_fr(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def gather(self, status="draft", reads=None, read_by=None, **kw):
        stance(self.cfg, status)
        conn = c5.connect_ro(self.db)
        try:
            return sv.gather(conn, "fr", config_dir=self.cfg, wl={}, reads=reads,
                             read_by=read_by, **kw)
        finally:
            conn.close()

    def rows(self, got, area=2):
        return {r["member_id"]: r for r in got["areas"].get(area, [])}


class GatherTests(Base):
    def test_countries_are_the_speech_and_vote_ones(self):
        # HR, SK, PL and BR since their speeches (11 October 2026, gaps-speeches).
        self.assertEqual(set(sv.COUNTRIES), {"nl", "ch", "at", "fr", "be", "hr", "sk", "pl",
                                             "br"})
        with self.assertRaises(ValueError):
            sv.gather(None, "pt")                   # questions only

    def test_last_vote_is_the_final_on_the_day_and_only_later_words_count(self):
        got = self.gather()
        r = self.rows(got)["PA1"]
        self.assertEqual(r["vote"]["key"], "an-17-1")
        self.assertEqual([s["speech_id"] for s in r["speeches"]], ["s3", "s2"])  # newest first
        self.assertEqual((r["n"], r["latest"]), (2, "2026-09-30"))

    def test_name_match_government_and_unmatched(self):
        got = self.gather()
        rows = self.rows(got)
        self.assertIn("PA3", rows)                       # matched by name, no person id
        self.assertEqual(got["government"], 1)
        self.assertEqual(got["unmatched"], 1)
        self.assertEqual(got["no_vote"], {1: 1})          # Claire Petit on area 1, no vote
        self.assertNotIn(11, got["areas"])                # migration hidden
        self.assertNotIn("PA4", rows)                     # spoke on area 1 only

    def test_since_takes_the_vote_on_or_before_that_date(self):
        got = self.gather(since="2026-01-01")
        r = self.rows(got)["PA1"]
        self.assertEqual(r["vote"]["key"], "an-16-9")
        self.assertEqual(r["n"], 3)

    def test_unconfirmed_is_awaiting_and_ranked_by_recency_then_volume(self):
        got = self.gather("draft")
        order = [r["member_id"] for r in got["areas"][2]]
        self.assertEqual(order, ["PA3", "PA2", "PA1"])
        self.assertTrue(all(r["state"] == sv.AWAITING for r in got["areas"][2]))
        text = sv.render(got, "2026-10-11")
        self.assertIn("AWAITING SIGN-OFF", text)
        self.assertNotIn("DRIFTING", text)
        self.assertNotIn("—", text)

    def test_confirmed_but_unread_names_no_drift(self):
        got = self.gather("confirmed")
        self.assertTrue(all(r["state"] == sv.NOT_READ for r in got["areas"][2]))
        self.assertNotIn("DRIFTING", sv.render(got))

    def test_confirmed_and_read_names_drift(self):
        keys = {"PA1": sv.read_key(2, "PA1", "2026-09-30"),
                "PA2": sv.read_key(2, "PA2", "2026-10-01"),
                "PA3": sv.read_key(2, "PA3", "2026-10-02")}
        reads = {keys["PA1"]: "with", keys["PA2"]: "against", keys["PA3"]: "with"}
        got = self.gather("confirmed", reads=reads, read_by="Christopher")
        rows = self.rows(got)
        # PA1 voted pour (against us), words read with: our way.
        self.assertEqual(rows["PA1"]["state"], sv.OUR_WAY)
        # PA2 voted contre (with us), words read against: away.
        self.assertEqual(rows["PA2"]["state"], sv.AWAY)
        self.assertEqual(rows["PA3"]["state"], sv.HOLDING)
        self.assertEqual(got["areas"][2][0]["member_id"], "PA1")
        text = sv.render(got)
        self.assertIn("DRIFTING OUR WAY", text)
        self.assertIn("by Christopher", text)

    def test_a_read_goes_stale_when_new_words_arrive(self):
        stale = {sv.read_key(2, "PA1", "2026-06-10"): "with"}
        got = self.gather("confirmed", reads=stale, read_by="C")
        self.assertEqual(self.rows(got)["PA1"]["state"], sv.NOT_READ)


class ReadsAndToolTests(Base):
    def test_reads_need_a_named_reader(self):
        path = os.path.join(self.tmp.name, "r.yaml")
        with open(path, "w") as h:
            h.write('read_by: ""\nreads:\n  "a2|PA1|2026-09-30": "with"\n')
        self.assertEqual(sv.load_reads(path), (None, {}))
        with open(path, "w") as h:
            h.write('read_by: "Chris"\nreads:\n  "a2|PA1|2026-09-30": "with"\n  "x": "maybe"\n')
        self.assertEqual(sv.load_reads(path), ("Chris", {"a2|PA1|2026-09-30": "with"}))

    def test_queue_only_confirmed_unread_unless_all(self):
        q, n = sv.queue_text(self.gather("draft"))
        self.assertEqual(n, 0)
        q, n = sv.queue_text(self.gather("draft"), include_all=True)
        self.assertEqual(n, 3)
        q, n = sv.queue_text(self.gather("confirmed"))
        self.assertEqual(n, 3)
        self.assertIn('"a2|PA1|2026-09-30": ""', q)

    def test_tool_round_trip(self):
        spec = importlib.util.spec_from_file_location(
            "country_since_vote_tool", os.path.join(ROOT, "tools", "country_since_vote.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        stance(self.cfg, "confirmed")
        qpath = os.path.join(self.tmp.name, "q.yaml")
        out = os.path.join(self.tmp.name, "out.md")
        base = ["--cc", "fr", "--db", self.db, "--config-dir", self.cfg, "--out", out]
        self.assertEqual(tool.main(base + ["--queue-out", qpath], log=QUIET), 0)
        text = _read(qpath).replace('read_by: ""', 'read_by: "Chris"').replace(
            '"a2|PA2|2026-10-01": ""', '"a2|PA2|2026-10-01": "against"')
        with open(qpath, "w") as h:
            h.write(text)
        self.assertEqual(tool.main(base + ["--reads", qpath], log=QUIET), 0)
        got = _read(out)
        self.assertIn("DRIFTING AWAY", got)
        self.assertIn("Words read by: Chris.", got)


class DerivedTests(unittest.TestCase):
    """The Netherlands: a show of hands gives each member the fractie's vote
    (X5), which never names drift and is never queued."""

    def test_group_vote_never_names_drift(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        nl_store.ensure_schema(conn)
        cs.ensure_schema(conn, ["nl"])
        conn.execute("INSERT INTO nl_members (persoon_id, name, fractie) VALUES ('p1','Anna de Vries','SGP')")
        conn.execute("INSERT INTO nl_zaken (zaak_nummer, soort, onderwerp, areas, tier) VALUES "
                     "('Z1','Motie','Motie over euthanasie','[2]',1)")
        conn.execute("INSERT INTO nl_divisions (besluit_id, zaak_nummer, date, besluit_tekst, areas) "
                     "VALUES ('B1','Z1','2026-06-01','Verworpen.','[2]')")
        conn.execute("INSERT INTO nl_votes (stemming_id, besluit_id, kind, fractie, position) "
                     "VALUES ('v1','B1','fractie','SGP','Tegen')")
        conn.execute("INSERT INTO nl_speeches (speech_id, date, debate, speaker, party, role, "
                     "excerpt, areas) VALUES ('n1','2026-10-01','Euthanasie','Anna de Vries','SGP',"
                     "'member','Woorden.','[2]')")
        got = sv.gather(conn, "nl", wl={}, reads={sv.read_key(2, "p1", "2026-10-01"): "against"},
                        read_by="C")
        r = got["areas"][2][0]
        self.assertTrue(r["reading"]["derived"])
        self.assertEqual(r["state"], sv.DERIVED)
        self.assertIsNone(r["read"])
        self.assertEqual(sv.queue_text(got, include_all=True)[1], 0)
        self.assertIn("X5", sv.render(got))


class ProfileTests(Base):
    def test_optional_section(self):
        stance(self.cfg, "draft")
        conn = sqlite3.connect("file:{0}?mode=ro".format(self.db), uri=True)
        try:
            plain = mp.build(conn, "fr", "2026-10-11", config_dir=self.cfg)
            with_it = mp.build(conn, "fr", "2026-10-11", config_dir=self.cfg, since_vote=True)
        finally:
            conn.close()
        self.assertIsNone(plain["since_vote"])
        m = with_it["members"]["PA1"]
        self.assertEqual(len(m.since_vote), 1)
        text = mp.render_member(with_it, m)
        self.assertIn("## Words since the last vote (1)", text)
        self.assertIn("awaiting sign-off", text)
        self.assertNotIn("Words since the last vote", mp.render_member(plain, plain["members"]["PA1"]))


if __name__ == "__main__":
    unittest.main()
