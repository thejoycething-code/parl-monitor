"""The registers batch (Christopher, 2026-08-31): APPG offices, declared
interests, whole-record alignment, and the coming-up strip.

Sources with three different access shapes: the APPG register is scraped in
a browser and committed (its host blocks CI), the interests register is an
open API swept incrementally, and the division rolls are an open API whose
product is computed loyalty. What they share: names resolve against the
members table or are stored with NULL and printed -- never guessed.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, members

import make_vote_tracker as mvt


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


appgs = _load("load_appgs")
rolls = _load("pull_division_rolls")
pbc = _load("pull_pbc_attendance")


def template():
    with open(os.path.join(ROOT, "templates", "vote-tracker.html"),
              encoding="utf-8") as fh:
        return fh.read()


class AppgTitleTests(unittest.TestCase):
    """The register puts its boilerplate in three different places."""

    def test_all_three_title_arrangements_shorten(self):
        self.assertEqual(
            mvt.appg_short("All-Party Parliamentary Group on Dying Well"),
            "Dying Well")
        self.assertEqual(
            mvt.appg_short("All-Party Parliamentary Pro-Life Group"),
            "Pro-Life")
        self.assertEqual(
            mvt.appg_short("Christians in Parliament All-Party "
                           "Parliamentary Group"),
            "Christians in Parliament")
        self.assertEqual(
            mvt.appg_short("All-Party Parliamentary Group for Choice "
                           "at the End of Life"),
            "Choice at the End of Life")

    def test_registered_contact_is_plumbing_not_an_office(self):
        self.assertEqual(mvt.appg_role("Chair & Registered Contact"), "Chair")
        self.assertEqual(mvt.appg_role("Co-Chair"), "Co-Chair")


class AppgLoaderTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        db.init_db(self.conn)
        for mid, name, current in ((1, "Rachael Maskell", 1),
                                   (2, "Baroness Finlay of Llandaff", 0)):
            members.cache_put(self.conn, members.Member(
                id=mid, name=name, party="X", seat="S", house="Commons",
                since="2024-07-04", list_as=name))
            if current:
                self.conn.execute(
                    "UPDATE members SET current_mp = 1 WHERE id = ?", (mid,))

    def _file(self, payload):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False)
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_officers_load_and_unknowns_are_null_not_guessed(self):
        path = self._file({"edition": "2026-06-29", "groups": {
            "dying-well": {"title": "APPG on Dying Well", "purpose": "p",
                           "category": "Subject Group", "officers": [
                {"role": "Chair & Registered Contact",
                 "name": "Rachael Maskell", "party": "Labour (Co-op)"},
                {"role": "Officer", "name": "Nobody We Know",
                 "party": "Independent"}]}}})
        names = appgs.resolve(self.conn, prefer_current=True)
        edition, rows, missing = appgs.load_file(self.conn, path, names)
        self.assertEqual((edition, rows), ("2026-06-29", 2))
        self.assertEqual(missing, ["Nobody We Know"])
        got = {r["name"]: r["member_id"] for r in self.conn.execute(
            "SELECT name, member_id FROM appg_officers")}
        self.assertEqual(got["Rachael Maskell"], 1)
        self.assertIsNone(got["Nobody We Know"])


class PreferCurrentTests(unittest.TestCase):
    """Two members, one name: the current register may prefer the sitting
    one; a historic roster must not."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        db.init_db(self.conn)
        for mid, current in ((1, 0), (2, 1)):
            members.cache_put(self.conn, members.Member(
                id=mid, name="Paul Holmes", party="X", seat="S",
                house="Commons", since="2024-07-04", list_as=None))
        self.conn.execute("UPDATE members SET current_mp = 1 WHERE id = 2")

    def test_strict_mode_refuses_and_current_mode_resolves(self):
        strict = pbc.resolve(self.conn)
        self.assertIsNone(strict[pbc.norm("Paul Holmes")])
        current = pbc.resolve(self.conn, prefer_current=True)
        self.assertEqual(current[pbc.norm("Paul Holmes")], 2)

    def test_two_sitting_namesakes_still_refuse(self):
        self.conn.execute("UPDATE members SET current_mp = 1")
        current = pbc.resolve(self.conn, prefer_current=True)
        self.assertIsNone(current[pbc.norm("Paul Holmes")])


class AlignmentComputeTests(unittest.TestCase):
    """The loyalty arithmetic, on a synthetic corpus. The bloc test is the
    tracker's own: two largest parties >=98% on opposite sides."""

    def _conn(self, votes):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        conn.execute("INSERT INTO cv_divisions (division_id, date, title, "
                     "ayes, noes) VALUES (900, '2025-01-01', 'A Motion', 0, 0)")
        for member_id, side, party in votes:
            conn.execute("INSERT INTO cv_votes (division_id, member_id, "
                         "side, party) VALUES (900, ?, ?, ?)",
                         (member_id, side, party))
        return conn

    def _bloc(self, rebel_side="N"):
        # Labour 59 aye + a teller, Conservative 40 no: two blocs, opposite.
        # The rebel is COUNTED IN their party's split -- exactly as the
        # tracker's party_line counts them -- so the loyal wing must be big
        # enough that one rebel leaves cohesion at >=98%: 60 of 61 is
        # 98.4%. Member 1 is the Labour rebel; member 99 is absent.
        votes = [(100 + i, "A", "Labour") for i in range(59)]
        votes.append((159, "TA", "Labour"))
        votes += [(200 + i, "N", "Conservative") for i in range(40)]
        votes.append((1, rebel_side, "Labour"))
        votes.append((99, "X", "Labour"))
        return votes

    def test_a_rebel_against_a_bloc_is_a_defiance(self):
        conn = self._conn(self._bloc())
        rolls.compute(conn)
        row = conn.execute("SELECT * FROM mp_alignment WHERE member_id = 1"
                           ).fetchone()
        self.assertEqual((row["voted"], row["against_party"], row["defied"]),
                         (1, 1, 1))
        d = conn.execute("SELECT * FROM mp_defiance WHERE member_id = 1"
                         ).fetchone()
        self.assertEqual((d["division_id"], d["party"]), (900, "Labour"))

    def test_a_loyalist_and_a_teller_count_with_their_party(self):
        conn = self._conn(self._bloc())
        rolls.compute(conn)
        loyal = conn.execute("SELECT with_party, defied FROM mp_alignment "
                             "WHERE member_id = 100").fetchone()
        self.assertEqual(tuple(loyal), (1, 0))
        teller = conn.execute("SELECT with_party FROM mp_alignment "
                              "WHERE member_id = 159").fetchone()
        self.assertEqual(teller["with_party"], 1)

    def test_absence_is_eligibility_not_a_position(self):
        conn = self._conn(self._bloc())
        rolls.compute(conn)
        row = conn.execute("SELECT eligible, voted, with_party, against_party "
                           "FROM mp_alignment WHERE member_id = 99").fetchone()
        self.assertEqual(tuple(row), (1, 0, 0, 0))

    def test_one_rebel_does_not_dissolve_the_bloc(self):
        # 25 with + 1 against is 96%... the bloc share is measured on the
        # party's OWN split: 25/26 = 96.2% < 98, so a single rebel in a
        # small party CAN dissolve the bloc -- the arithmetic must follow
        # the rule, not the wish. With 49 loyalists, 49/50 = 98% holds.
        votes = [(100 + i, "A", "Labour") for i in range(49)]
        votes += [(200 + i, "N", "Conservative") for i in range(30)]
        votes.append((1, "N", "Labour"))
        conn = self._conn(votes)
        rolls.compute(conn)
        row = conn.execute("SELECT defied FROM mp_alignment "
                           "WHERE member_id = 1").fetchone()
        self.assertEqual(row["defied"], 1)

    def test_labour_coop_is_measured_against_labour(self):
        votes = [(100 + i, "A", "Labour") for i in range(60)]
        votes += [(200 + i, "N", "Conservative") for i in range(40)]
        votes.append((1, "N", "Labour (Co-op)"))
        conn = self._conn(votes)
        rolls.compute(conn)
        row = conn.execute("SELECT against_party, defied FROM mp_alignment "
                           "WHERE member_id = 1").fetchone()
        self.assertEqual(tuple(row), (1, 1))


class PageAdditionsTests(unittest.TestCase):
    def test_the_coming_up_strip_renders_from_the_dataset(self):
        flat = " ".join(template().split())
        self.assertIn('const cu = DATA.coming_up || [];', flat)
        self.assertIn('<div id="comingup"></div>', flat)
        self.assertIn("COMING UP", flat)

    def test_interests_are_a_count_and_the_official_link(self):
        flat = " ".join(template().split())
        self.assertIn("if (!m.interests) return \"\";", flat)
        self.assertIn("members.parliament.uk/member/${m.id}/registeredinterests",
                      flat)

    def test_appg_offices_render_as_pills_and_only_resolved_ones_ship(self):
        flat = " ".join(template().split())
        self.assertIn("APPG", flat)
        with open(os.path.join(ROOT, "tools", "make_vote_tracker.py"),
                  encoding="utf-8") as fh:
            tool = fh.read()
        self.assertIn("AND member_id IS NOT NULL", tool,
                      "an unresolved officer name must never reach a page")
        self.assertIn("SELECT MAX(edition) FROM appg_officers", tool,
                      "a superseded register edition is history, not fact")

    def test_the_5ca_carries_loyalty_but_only_where_it_is_computed(self):
        with open(os.path.join(ROOT, "tools", "make_5ca_web.py"),
                  encoding="utf-8") as fh:
            tool = fh.read()
        self.assertIn("FROM mp_alignment", tool)
        self.assertIn('m.al == null ? ""', tool,
                      "a member with no rolls (peers) shows nothing, not 0%")


class ComingUpQueryTests(unittest.TestCase):
    def test_only_live_dated_future_rows_and_at_most_four(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        rows = [
            (1, "Past Bill", "Commons", "2nd reading", "2020-01-01", "live"),
            (2, "TBA Bill", "Commons", "2nd reading", "TBA", "live"),
            (3, "Closed Bill", "Commons", "2nd reading", "2099-01-01", "closed"),
            (4, "Bill A", "Commons", "2nd reading", "2099-01-02", "live"),
            (5, "Bill B", "Commons", "2nd reading", "2099-01-03", "live"),
            (6, "Bill C", "Lords", "Committee", "2099-01-04", "live"),
            (7, "Bill D", "Commons", "2nd reading", "2099-01-05", "live"),
        ]
        for r in rows:
            conn.execute("INSERT INTO bills_board (bill_id, title, house, "
                         "stage, next_key_date, status) VALUES (?,?,?,?,?,?)", r)
        members.cache_put(conn, members.Member(
            id=1, name="Aye MP", party="Labour", seat="Seat",
            house="Commons", since="2024-07-04", list_as="Aye MP"))
        conn.execute("UPDATE members SET current_mp = 1")
        conn.commit()
        cfg = {"issues": [{"id": "iss", "name": "An issue", "area": 2,
                           "bill": "A Bill", "note": "n", "status": "s"}],
               "divisions": []}
        dataset, _ = mvt.build(conn, cfg, {})
        got = [c["title"] for c in dataset["coming_up"]]
        self.assertEqual(got, ["Bill A", "Bill B", "Bill C", "Bill D"])


if __name__ == "__main__":
    unittest.main()
