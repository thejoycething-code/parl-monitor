"""Remaining speech coverage (11 October 2026, branch gaps-speeches): Croatia,
Slovakia, Poland and Brazil on the shared chamber layer (src/chamber_store.py).

Fixtures (trimmed from the live sources, 11 October 2026):
  tests/fixtures/hr/fonogram-2017609-branitelji.html.gz  the Sabor's transcript
      of the joint debate on the veterans' bills (P.Z. 336 and 337), 24
      September 2026, cut after 95 contributions; page furniture and scripts
      removed
  tests/fixtures/pl/transcripts-66-2026-10-08-sample.json.gz  seven statements
      of the Sejm's 8 October 2026 list (the chair's day record, a secretary,
      a minister, a state secretary, deputies, one not delivered)
  tests/fixtures/pl/transcript-66-2026-10-08-6.html.gz    Mateusz Morawiecki
      on the 2027 budget, with the House's interjections
  tests/fixtures/pl/transcript-66-2026-10-08-248.html.gz  Grzegorz Lorek's
      statement on the abortion-pill vending machine (Oświadczenia)
  tests/fixtures/sk/rozprava-p1.html.gz  the first page of the NR SR's debate
      record on 11 October 2026, trimmed to six rows, with its pager
  tests/fixtures/br/discursos-2026-08.xml.gz  three plenary speeches of the
      Câmara's ListarDiscursosPlenario for August 2026
  tests/fixtures/br/texto-sample.html.gz  one speech page (TextoHTML.asp)
"""

import gzip
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import chamber_store as cs  # noqa: E402
from src import db, drain  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")
TODAY = "2026-10-11"


def fixture(*parts):
    with gzip.open(os.path.join(FIX, *parts)) as fh:
        return fh.read().decode("utf-8")


def store():
    return db.init_db(db.connect(":memory:"))


def quiet(*_a, **_k):
    return None


class FakeClient:
    """Answers by URL suffix (else fragment), the longest first; counts fetches."""

    def __init__(self, routes, posts=None):
        self.routes = routes
        self.posts = posts or {}
        self.fetched = []

    def _find(self, url, routes):
        bare = url.split("?")[0]
        for test in (lambda f: bare.endswith(f), lambda f: f in url):
            for frag in sorted(routes, key=len, reverse=True):
                if test(frag):
                    self.fetched.append(frag)
                    return routes[frag]
        raise AssertionError("unexpected fetch: " + url)

    def get_json(self, url, feed, slug, **kw):
        body = self._find(url, self.routes)
        return json.loads(body) if isinstance(body, (str, bytes)) else body

    def get_text(self, url, feed, slug, **kw):
        return self._find(url, self.routes)

    def post_form(self, url, fields, feed, slug, **kw):
        self.fetched.append("POST " + fields.get("__EVENTARGUMENT", ""))
        return self.posts[fields.get("__EVENTARGUMENT")]

    def enable_gzip(self, host):
        pass


def run_for(cc, conn, client, since, taxes=None):
    return cs.Run(cc, conn, client, TODAY, since, drain.Budget(600),
                  taxes if taxes is not None else cs.load_taxonomies(cc), log=quiet)


class SchemaTests(unittest.TestCase):

    def test_the_four_countries_have_speech_tables(self):
        for cc in ("hr", "sk", "pl", "br"):
            self.assertIn("{0}_speeches".format(cc), cs.tables(cc))
        # Additive: Poland and Brazil keep their questions.
        self.assertIn("pl_questions", cs.tables("pl"))
        self.assertIn("br_questions", cs.tables("br"))
        self.assertNotIn("hr_questions", cs.tables("hr"))
        self.assertTrue(set(cs.TABLES) <= set(db.TABLES))
        names = {r[0] for r in store().execute("SELECT name FROM sqlite_master")}
        self.assertTrue({"hr_speeches", "sk_speeches", "pl_speeches", "br_speeches"} <= names)

    def test_profiles_debate_report_and_live_read_know_them(self):
        from src import country_debatereport as dr, country_live as cl
        from src import country_since_vote as sv
        for cc in ("hr", "sk", "pl", "br"):
            self.assertIn(cc, sv.COUNTRIES)
            self.assertIn(cc, dr.COUNTRIES)
            self.assertIn(cc, dr.LANGUAGES)
            # Collected, but none measured as a same-day source.
            self.assertNotIn(cc, cl.COUNTRIES)
            self.assertIn("collected", cl.NOT_QUALIFYING[cc])

    def test_government_roles_never_count_as_members(self):
        from src import country_since_vote as sv
        for role in ("Government (mandate on hold)", "Government or guest",
                     "Sekretarz Stanu w Ministerstwie Zdrowia", "predseda vlády SR",
                     "minister zdravotníctva SR"):
            self.assertTrue(sv.is_government(role), role)
        self.assertFalse(sv.is_government("member"))


class CroatiaTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import hr_chamber
        cls.hr = hr_chamber
        cls.page = fixture("hr", "fonogram-2017609-branitelji.html.gz")
        cls.got = hr_chamber.turns_of(cls.page)

    def test_the_joint_debate_titles_days_and_speakers(self):
        got = self.got
        self.assertEqual(got["saziv"], "XI")
        self.assertEqual(len(got["titles"]), 2)
        self.assertTrue(got["titles"][0].startswith("Prijedlog zakona o izmjenama i dopunama "
                                                    "Zakona o hrvatskim braniteljima"))
        first = got["turns"][0]
        self.assertEqual(first["date"], "2026-09-24")
        names = {(t["speaker"], t["party"]) for t in got["turns"]}
        self.assertIn(("Šašlin, Stipan", "HDZ"), names)
        self.assertIn(("Bakić, Damir", "Možemo!"), names)

    def test_interruptions_are_cut(self):
        for t in self.got["turns"]:
            self.assertNotIn("Upadica", t["text"])

    def test_the_chair_is_found_by_the_shape_of_the_record(self):
        turns = self.got["turns"]
        chair = self.hr.chair_turns(turns)
        self.assertTrue(chair)
        self.assertEqual({turns[i]["speaker"] for i in chair} - {
            "Jandroković, Gordan", "Reiner, Željko", "Penava, Ivan"}, set())
        # Members on the floor are never the chair.
        for i, t in enumerate(turns):
            if t["speaker"] in ("Šašlin, Stipan", "Bakić, Damir", "Miletić, Marin"):
                self.assertNotIn(i, chair)

    def test_speeches_stored_once_for_a_joint_debate(self):
        conn = store()
        conn.execute("INSERT INTO hr_members (slug, name, party, mandate, saziv) VALUES "
                     "('saslin-stipan-11-saziv', 'Šašlin, Stipan', 'HDZ', 'Aktivan', 11)")
        conn.execute("INSERT INTO hr_members (slug, name, party, mandate, saziv) VALUES "
                     "('medved-tomo-11-saziv', 'Medved, Tomo', 'HDZ', 'U mirovanju', 11)")
        run = run_for("hr", conn, None, "2026-09-01")
        members = self.hr.roster(conn)
        # The same transcript printed under both items' ids (2017609, 2017610).
        self.hr.process(run, 2017609, self.got, members)
        n = conn.execute("SELECT COUNT(*) FROM hr_speeches").fetchone()[0]
        self.hr.process(run, 2017610, self.got, members)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM hr_speeches").fetchone()[0], n)
        row = conn.execute("SELECT areas, person_id, role, url FROM hr_speeches WHERE speaker = "
                           "'Šašlin, Stipan'").fetchone()
        self.assertIn(5, json.loads(row[0]))
        self.assertEqual((row[1], row[2]), ("saslin-stipan-11-saziv", "member"))
        self.assertIn("tdrid=", row[3])
        chairs = conn.execute("SELECT COUNT(*) FROM hr_speeches WHERE speaker IN "
                              "('Jandroković, Gordan')").fetchone()[0]
        self.assertEqual(chairs, 0)
        reads = conn.execute("SELECT feed, date, status FROM hr_record_reads").fetchall()
        self.assertEqual({r[1] for r in reads}, {"2026-09-24"})

    def test_roles(self):
        self.assertEqual(self.hr.role_of({"party": "HDZ"}, ("x", "U mirovanju")),
                         "Government (mandate on hold)")
        self.assertEqual(self.hr.role_of({"party": None}, None), "Government or guest")
        self.assertEqual(self.hr.role_of({"party": "SDP"}, ("y", "Aktivan")), "member")

    def test_a_settled_transcript_is_not_fetched_again(self):
        conn = store()
        conn.execute("INSERT INTO hr_transcripts (tdrid, saziv, last_date) VALUES "
                     "(2017609, 'XI', '2026-09-24')")
        conn.execute("INSERT INTO hr_transcripts (tdrid, saziv, last_date) VALUES "
                     "(2017500, 'XI', '2026-06-01')")
        cs.mark_read(conn, "hr", "tdrid-2017609", "speeches", "2026-09-24", "2026-09-24|95",
                     90, 3, 1000, "2026-09-26")
        run = run_for("hr", conn, None, "2026-09-01")
        todo = self.hr.candidates(run, 2017609)
        self.assertNotIn(2017609, todo)           # read, and its last day is a week old
        self.assertNotIn(2017500, todo)           # debated before --since
        self.assertIn(2017619, todo)              # just above the newest: not yet known


class PolandTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import pl_chamber
        cls.pl = pl_chamber

    def test_a_statement_is_the_speaker_alone(self):
        got = self.pl.parse_statement(fixture("pl", "transcript-66-2026-10-08-6.html.gz"))
        self.assertTrue(got["point"].startswith("29. Pierwsze czytanie rządowego projektu "
                                                "ustawy budżetowej na rok 2027"))
        self.assertEqual(got["label"], "Poseł Mateusz Morawiecki")
        for noise in ("Oklaski", "Głos z sali", "Frydrych", "Przebieg posiedzenia"):
            self.assertNotIn(noise, got["text"])
        statement = self.pl.parse_statement(fixture("pl", "transcript-66-2026-10-08-248.html.gz"))
        self.assertEqual(statement["point"], "Oświadczenia")

    def test_the_chair_and_secretaries_are_never_fetched(self):
        listed = json.loads(fixture("pl", "transcripts-66-2026-10-08-sample.json.gz"))
        wanted = [st["num"] for st in listed["statements"] if self.pl.wanted(st)]
        self.assertEqual(wanted, [2, 3, 6, 111, 248])
        roles = {st["num"]: self.pl.role_of(st) for st in listed["statements"]}
        self.assertEqual(roles[6], "member")
        self.assertEqual(roles[2], "Minister Finansów i Gospodarki")
        self.assertIn("not delivered", roles[111])

    def test_collect_store_and_resume(self):
        listed = fixture("pl", "transcripts-66-2026-10-08-sample.json.gz")
        lorek = fixture("pl", "transcript-66-2026-10-08-248.html.gz")
        budget = fixture("pl", "transcript-66-2026-10-08-6.html.gz")
        routes = {
            "/term10/proceedings": [{"number": 66, "dates": ["2026-10-07", "2026-10-08",
                                                             "2026-10-09"]},
                                    {"number": 0, "dates": ["2027-01-01"]}],
            "/proceedings/66/2026-10-08/transcripts": listed,
            "/proceedings/66/2026-10-09/transcripts": {"statements": []},
            "/proceedings/66/2026-10-07/transcripts": {"statements": []},
            "/transcripts/248": lorek,
        }
        for n in (2, 3, 6, 111):
            routes["/2026-10-08/transcripts/{0}".format(n)] = budget
        client = FakeClient(routes)
        conn = store()
        conn.execute("INSERT INTO pl_members (mp_key, term, mp_id, name, club) VALUES "
                     "('10/216', 10, 216, 'Grzegorz Lorek', 'PiS')")
        self.pl.speeches(run_for("pl", conn, client, "2026-10-01"))
        row = conn.execute("SELECT speaker, party, person_id, areas, debate, role FROM pl_speeches "
                           "WHERE speech_id = '66/2026-10-08#248'").fetchone()
        self.assertEqual(row[:3], ("Grzegorz Lorek", "PiS", "10/216"))
        self.assertIn(1, json.loads(row[3]))
        self.assertEqual((row[4], row[5]), ("Oświadczenia", "member"))
        self.assertNotIn("/transcripts/0", " ".join(client.fetched))
        reads = dict(conn.execute("SELECT doc_id, status FROM pl_record_reads WHERE feed = "
                                  "'speeches'").fetchall())
        # A day whose record is not published yet is not marked read.
        self.assertEqual(reads, {"66/2026-10-08": "read"})
        client.fetched.clear()
        self.pl.speeches(run_for("pl", conn, client, "2026-10-01"))
        self.assertFalse([f for f in client.fetched if "/transcripts/" in f])
