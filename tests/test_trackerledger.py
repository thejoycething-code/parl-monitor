"""Every tracker division has its voters in the ledger (2026-09-10).

Two divisions were signed off on the tracker and published a verdict on nobody: the
card reads voters from the ledger, and the title sweep that fills the ledger could not
see them. This is the guarantee that closes that gap.
"""

import datetime
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, trackerledger as tl  # noqa: E402

CFG = {
    "issues": [{"id": "gender-medicine", "area": 3}, {"id": "single-sex-nhs", "area": 5},
               {"id": "abortion-ni", "area": 1}],
    "divisions": [{"id": 2421, "issue": "gender-medicine", "signed_off": True},
                  {"id": 2422, "issue": "single-sex-nhs", "signed_off": True},
                  {"id": 981, "issue": "abortion-ni", "house": "lords"}],
}


def breakdown_payload(division_id, n_aye=3, n_no=2, both=()):
    ayes = [{"MemberId": 1000 + i, "Name": "Aye %d" % i, "Party": "Con", "MemberFrom": "Seat %d" % i} for i in range(n_aye)]
    noes = [{"MemberId": 2000 + i, "Name": "No %d" % i, "Party": "Lab", "MemberFrom": "Seat %d" % i} for i in range(n_no)]
    for mid in both:                                    # a member in both lobbies: the recorded abstention
        ayes.append({"MemberId": mid, "Name": "Both %d" % mid, "Party": "Lab", "MemberFrom": "S"})
        noes.append({"MemberId": mid, "Name": "Both %d" % mid, "Party": "Lab", "MemberFrom": "S"})
    return {"DivisionId": division_id, "Number": 1, "Title": "Health Bill: Report Stage: New Clause %d" % division_id,
            "Date": "2026-09-08T00:00:00", "AyeCount": n_aye, "NoCount": n_no, "Ayes": ayes, "Noes": noes,
            "AyeTellers": [], "NoTellers": []}


class FakeClient(object):
    def __init__(self):
        self.calls = []

    def get_json(self, url, feed, slug, **kw):
        self.calls.append(url)
        if "lordsvotes" in url:
            raise RuntimeError("HTTP 500")          # the Lords one fails, to test the gap path
        division_id = int(url.rstrip("/").split("/")[-1].replace(".json", ""))
        return breakdown_payload(division_id)


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return db.init_db(conn)


class MissingTests(unittest.TestCase):
    def test_every_tracker_division_with_no_rows_is_missing(self):
        conn = store()
        got = tl.missing_divisions(conn, CFG)
        self.assertEqual(sorted(d for d, _h, _a, _i in got), [981, 2421, 2422])
        by_id = {d: (h, a) for d, h, a, _i in got}
        self.assertEqual(by_id[2421], ("commons", [3]))
        self.assertEqual(by_id[981], ("lords", [1]))

    def test_a_division_with_rows_is_left_alone(self):
        conn = store()
        conn.execute("INSERT INTO mp_events (member_id, date, kind, ref, line) VALUES (1, '2026-09-08', 'vote', 'div:c2421:aye', 'x')")
        conn.commit()
        self.assertNotIn(2421, [d for d, _h, _a, _i in tl.missing_divisions(conn, CFG)])

    def test_prefix_follows_the_house(self):
        self.assertEqual(tl.prefix_for("lords"), "l")
        self.assertEqual(tl.prefix_for("Lords"), "l")
        self.assertEqual(tl.prefix_for("commons"), "c")
        self.assertEqual(tl.prefix_for(None), "c")


class BothLobbiesTests(unittest.TestCase):
    """Gareth Snell, 11 September 2026: in both lobbies, ledgered as an Aye and a No,
    placed by the 5CA on the Aye side after a 'conflict'. An abstention has no side."""

    def test_a_member_in_both_lobbies_gets_one_both_event_and_a_zero_stance(self):
        from src import intel
        from src.ingest import divisions as dv
        conn = store()
        payload = breakdown_payload(2428, 2, 2, both=(4595,))
        division, voters = dv.parse_commons_breakdown(payload) if hasattr(dv, "parse_commons_breakdown") else (None, None)
        if division is None:
            class C(FakeClient):
                def get_json(self, url, feed, slug, **kw):
                    return payload
            division, voters = dv.fetch_commons_breakdown(C(), 2428)
        division.house = "Commons"
        intel.record_votes(conn, division, voters, "c", [2])
        rows = {r[0]: r[1] for r in conn.execute("SELECT ref, count(*) FROM mp_events WHERE member_id=4595 GROUP BY ref")}
        self.assertEqual(rows, {"div:c2428:both": 1})
        self.assertEqual(conn.execute("SELECT count(*) FROM mp_events WHERE ref='div:c2428:aye'").fetchone()[0], 2)
        self.assertEqual(tuple(conn.execute("SELECT stance, model FROM stance WHERE ref='div:c2428:both'").fetchone()), (0, "rule:both-lobbies"))


class EnsureTests(unittest.TestCase):
    def test_missing_commons_divisions_are_ledgered_under_the_issue_area(self):
        conn, client = store(), FakeClient()
        report = tl.ensure(conn, client, CFG, log=lambda *_a: None)
        done = {d: n for d, _h, _i, n in report if isinstance(n, int)}
        self.assertEqual(done, {2421: 5, 2422: 5})
        rows = conn.execute("SELECT ref, areas FROM mp_events WHERE ref LIKE 'div:c2421:%' ORDER BY ref").fetchall()
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r["areas"] == "[3]" for r in rows), [r["areas"] for r in rows])
        self.assertEqual(sorted({r["ref"] for r in rows}), ["div:c2421:aye", "div:c2421:no"])

    def test_a_failed_breakdown_is_a_gap_not_a_crash(self):
        conn, client = store(), FakeClient()
        report = tl.ensure(conn, client, CFG, log=lambda *_a: None)
        lords = next(r for r in report if r[0] == 981)
        self.assertEqual(lords[1], "lords")
        self.assertTrue(isinstance(lords[3], str) and lords[3].startswith("gap"))
        self.assertEqual(tl.ledger_count(conn, 2421), 5)     # the others still landed

    def test_running_twice_adds_nothing(self):
        conn, client = store(), FakeClient()
        tl.ensure(conn, client, CFG, log=lambda *_a: None)
        n1 = conn.execute("SELECT count(*) FROM mp_events").fetchone()[0]
        calls = len(client.calls)
        tl.ensure(conn, client, CFG, log=lambda *_a: None)
        self.assertEqual(conn.execute("SELECT count(*) FROM mp_events").fetchone()[0], n1)
        # only the Lords gap is retried; the ledgered ones cost no call
        self.assertEqual(len(client.calls) - calls, 1)

    def test_dry_run_fetches_nothing_and_writes_nothing(self):
        conn, client = store(), FakeClient()
        report = tl.ensure(conn, client, CFG, log=lambda *_a: None, dry_run=True)
        self.assertEqual(len(report), 3)
        self.assertEqual(client.calls, [])
        self.assertEqual(conn.execute("SELECT count(*) FROM mp_events").fetchone()[0], 0)


class StoreTests(unittest.TestCase):
    """Against the real store, when it is here: no signed-off tracker division may be
    publishing a verdict on voters the ledger does not hold. Thirteen were, on
    2026-09-10, and nothing measured it."""

    def test_every_signed_off_tracker_division_has_voters_in_the_ledger(self):
        path = os.path.join(ROOT, "data", "parl-monitor.db")
        if not os.path.exists(path):
            self.skipTest("no store")
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import make_vote_tracker
        cfg = make_vote_tracker.load_config()
        signed = {int(d["id"]) for d in cfg.get("divisions") or [] if d.get("id") and d.get("signed_off")}
        conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        try:
            missing = [(d, h, i) for d, h, _a, i in tl.missing_divisions(conn, cfg) if d in signed]
        finally:
            conn.close()
        self.assertEqual(missing, [],
                         "signed-off divisions with no voters in the ledger (run "
                         "tools/ledger_tracker_divisions.py, then push the store): %s" % missing)


if __name__ == "__main__":
    unittest.main()
