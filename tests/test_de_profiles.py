"""German member profiles (Christopher, 24 September 2026: "Build member
profiles").

Three properties.

ONLY OFFICIAL, ROLE-RELATED FIELDS ARE STORED. abgeordnetenwatch publishes
more about a politician than this collector takes, and the extra stays where
it is. What a member does in the House is the monitor's business; who they
are outside it is not.

A MANDATE WITH NO POLITICIAN IS COUNTED, NEVER WRITTEN AS BLANK. A blank
politician_id would satisfy the "already profiled" skip and the row would
never be looked at again -- the same silent-skip trap that left 637 members
with a NULL parliament for weeks.

PRIORITY IS THE PEOPLE WE CAN SAY SOMETHING ABOUT. 2,517 mandates is too many
to fetch at once, so members with a stance placement or a vote in a matched
non-migration division come first: they are the ones a campaigner might
actually contact.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


prof = _load("de_profiles")
TODAY = "2026-09-24"

# Verbatim in shape from the live API (mandate 68376, Sanae Abdi).
MANDATE = {"data": {
    "id": 68376, "label": "Sanae Abdi (Bundestag 2025 - 2029)",
    "politician": {"id": 175489, "label": "Sanae Abdi",
                   "abgeordnetenwatch_url":
                       "https://www.abgeordnetenwatch.de/profile/sanae-abdi"},
    "electoral_data": {
        "constituency": {"label": "92 - Köln I (Bundestag 2025 - 2029)"},
        "electoral_list": {"label": "Landesliste Nordrhein-Westfalen"},
        "mandate_won": "constituency"},
}}
COMMITTEES = {"data": [
    {"committee": {"label": "Ausschuss für wirtschaftliche Zusammenarbeit"},
     "committee_role": "foreperson"},
    {"committee": {"label": "Parlamentarischer Beirat für nachhaltige "
                            "Entwicklung"}, "committee_role": "member"},
]}


def _conn():
    return db.init_db(db.connect(":memory:"))


def _member(conn, pid, name="Ein Mitglied", parliament="5"):
    conn.execute(
        "INSERT INTO de_members (person_id, name, party, parliament, "
        "legislature, first_seen, last_seen) VALUES (?,?,'SPD',?,'21',?,?)",
        (pid, name, parliament, TODAY, TODAY))
    conn.commit()


class Client:
    def __init__(self, mandate=MANDATE, committees=COMMITTEES):
        self.mandate, self.committees = mandate, committees
        self.calls = []

    def get_json(self, url, feed, slug, **kw):
        self.calls.append(url)
        return self.committees if "committee-memberships" in url \
            else self.mandate


class FieldTests(unittest.TestCase):
    def test_the_official_fields_are_read(self):
        got = prof.profile_of(MANDATE)
        self.assertEqual(got["politician_id"], "175489")
        self.assertEqual(got["constituency"], "92 - Köln I (Bundestag 2025 - 2029)")
        self.assertEqual(got["electoral_list"], "Landesliste Nordrhein-Westfalen")
        self.assertEqual(got["mandate_won"], "constituency")
        self.assertTrue(got["profile_url"].endswith("sanae-abdi"))

    def test_nothing_personal_is_collected(self):
        """The API offers more than this and the extra stays where it is."""
        self.assertEqual(
            set(prof.profile_of(MANDATE)),
            {"politician_id", "profile_url", "constituency",
             "electoral_list", "mandate_won"})

    def test_a_list_member_has_no_constituency_and_says_so(self):
        doc = {"data": {"politician": {"id": 1},
                        "electoral_data": {"mandate_won": "list",
                                           "electoral_list": {"label": "L"}}}}
        got = prof.profile_of(doc)
        self.assertIsNone(got["constituency"])
        self.assertEqual(got["mandate_won"], "list")

    def test_committee_roles_are_kept_verbatim(self):
        """'foreperson' is a different proposition from 'member' and the
        distinction is not ours to normalise away."""
        self.assertEqual(
            prof.committees_of(COMMITTEES),
            [("Ausschuss für wirtschaftliche Zusammenarbeit", "foreperson"),
             ("Parlamentarischer Beirat für nachhaltige Entwicklung",
              "member")])


class SkipTests(unittest.TestCase):
    def test_a_mandate_with_no_politician_is_not_written_as_blank(self):
        """THE ONE THAT MATTERS. A blank politician_id satisfies the
        'already profiled' skip, so the row would never be revisited -- the
        same trap that left 637 members with a NULL parliament."""
        conn = _conn()
        _member(conn, "1")
        client = Client(mandate={"data": {"politician": None,
                                          "electoral_data": {}}})
        done, failed, _, _ = prof.pull(conn, client, TODAY,
                                       log=lambda *a: None)
        self.assertEqual((done, failed), (0, 1))
        self.assertIsNone(conn.execute(
            "SELECT politician_id FROM de_members WHERE person_id='1'"
        ).fetchone()[0])

    def test_a_profiled_member_is_not_fetched_again(self):
        """Incremental, like eu_meps_enrich: after the first passes this
        costs new arrivals only."""
        conn = _conn()
        _member(conn, "1")
        prof.pull(conn, Client(), TODAY, log=lambda *a: None)
        second = Client()
        done, _, _, _ = prof.pull(conn, second, TODAY, log=lambda *a: None)
        self.assertEqual(done, 0)
        self.assertEqual(second.calls, [])


class PriorityTests(unittest.TestCase):
    def _spoke(self, conn, pid):
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "role, person_id, areas, tier, first_seen, last_seen) VALUES "
            "(?,?,?,?,'member',?,'[1]',1,?,?)",
            ("s" + pid, "21/94", "2026-09-11", "X", pid, TODAY, TODAY))
        conn.execute("CREATE TABLE IF NOT EXISTS stance (ref TEXT PRIMARY "
                     "KEY, stance INTEGER, why TEXT, model TEXT, "
                     "scored_at TEXT)")
        conn.execute("INSERT INTO stance (ref, stance) VALUES (?,2)",
                     ("de-speech:s" + pid,))
        conn.commit()

    def test_a_member_we_can_say_something_about_comes_first(self):
        conn = _conn()
        _member(conn, "quiet")
        _member(conn, "spoke")
        self._spoke(conn, "spoke")
        wanted, priority = prof.targets(conn, limit=1)
        self.assertEqual(wanted, ["spoke"])
        self.assertEqual(priority, 1)

    def test_a_migration_only_division_does_not_promote_anyone(self):
        """Area 11 renders nowhere, so a vote in it tells a campaigner
        nothing they can act on."""
        conn = _conn()
        _member(conn, "1")
        conn.execute("INSERT INTO de_divisions (vote_id, parliament, date, "
                     "label, areas, tier, first_seen, last_seen) VALUES "
                     "('v1','5','2026-09-10','X','[11]',1,?,?)",
                     (TODAY, TODAY))
        conn.execute("INSERT INTO de_votes VALUES ('v1','1','yes')")
        conn.commit()
        _, priority = prof.targets(conn, limit=10)
        self.assertEqual(priority, 0)

    def test_everyone_is_reachable_once_the_priority_set_is_done(self):
        """The tail is not abandoned, it is deferred."""
        conn = _conn()
        for pid in ("a", "b", "c"):
            _member(conn, pid)
        wanted, priority = prof.targets(conn, limit=10)
        self.assertEqual(sorted(wanted), ["a", "b", "c"])
        self.assertEqual(priority, 0)


class ReportTests(unittest.TestCase):
    """A run must not be wrong about itself.

    The first version printed the priority count measured BEFORE fetching,
    so a run that profiled all 281 priority members reported "2236 still
    unprofiled (281 of them are members we can already say something about)"
    -- describing the work it had just completed as still outstanding.
    """

    def test_the_priority_count_is_recomputed_after_the_run(self):
        conn = _conn()
        _member(conn, "spoke")
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "role, person_id, areas, tier, first_seen, last_seen) VALUES "
            "('s1','21/94','2026-09-11','X','member','spoke','[1]',1,?,?)",
            (TODAY, TODAY))
        conn.execute("CREATE TABLE IF NOT EXISTS stance (ref TEXT PRIMARY "
                     "KEY, stance INTEGER, why TEXT, model TEXT, "
                     "scored_at TEXT)")
        conn.execute("INSERT INTO stance (ref, stance) VALUES "
                     "('de-speech:s1', 2)")
        conn.commit()
        _, before = prof.targets(conn, limit=10)
        self.assertEqual(before, 1)
        prof.pull(conn, Client(), TODAY, log=lambda *a: None)
        _, after = prof.targets(conn, limit=0, everyone=True)
        self.assertEqual(after, 0,
                         "the priority count still names work already done")


class StorageTests(unittest.TestCase):
    def test_the_profile_and_its_committees_are_stored(self):
        conn = _conn()
        _member(conn, "68376")
        done, failed, committees, _ = prof.pull(conn, Client(), TODAY,
                                                log=lambda *a: None)
        self.assertEqual((done, failed, committees), (1, 0, 2))
        row = conn.execute("SELECT politician_id, constituency, mandate_won "
                           "FROM de_members WHERE person_id='68376'").fetchone()
        self.assertEqual(tuple(row),
                         ("175489", "92 - Köln I (Bundestag 2025 - 2029)",
                          "constituency"))
        seats = conn.execute("SELECT committee, role FROM de_affiliations "
                             "WHERE person_id='68376' ORDER BY committee"
                             ).fetchall()
        self.assertEqual(len(seats), 2)
        self.assertIn("foreperson", [s[1] for s in seats])

    def test_a_committee_seat_is_updated_not_duplicated(self):
        conn = _conn()
        _member(conn, "68376")
        prof.pull(conn, Client(), TODAY, log=lambda *a: None)
        conn.execute("UPDATE de_members SET politician_id = NULL")
        conn.commit()
        changed = dict(COMMITTEES)
        changed["data"] = [{"committee": {"label":
                                          "Ausschuss für wirtschaftliche "
                                          "Zusammenarbeit"},
                            "committee_role": "member"}]
        prof.pull(conn, Client(committees=changed), TODAY,
                  log=lambda *a: None)
        role = conn.execute(
            "SELECT role FROM de_affiliations WHERE person_id='68376' AND "
            "committee='Ausschuss für wirtschaftliche Zusammenarbeit'"
        ).fetchone()[0]
        self.assertEqual(role, "member", "a role change must overwrite")


if __name__ == "__main__":
    unittest.main()
