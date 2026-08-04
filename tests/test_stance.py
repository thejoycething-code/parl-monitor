"""Stance layer + 5CA sheet generation (docs/5ca-notes.md)."""

import json
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, intel, stance


def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return db.init_db(conn)


def member(conn, mid, name, party="Con", seat="Seatville", house="Commons"):
    conn.execute("INSERT INTO members (id, name, party, seat, house) VALUES (?,?,?,?,?)",
                 (mid, name, party, seat, house))


class ClassificationPlumbingTests(unittest.TestCase):
    def test_payload_carries_member_action_fields(self):
        ev = stance.Evidence(ref="pq:1", kind="pq", line="Asylum Hotels",
                             areas=[11], text="To ask HM Government...")
        payload = stance._build_payload([ev])
        body = json.loads(payload["messages"][0]["content"])
        self.assertEqual(body[0]["ref"], "pq:1")
        self.assertEqual(body[0]["areas"], [11])
        self.assertIn("To ask", body[0]["text"])

    def test_parse_reply_and_store_clamps_range(self):
        conn = fresh_conn()
        reply = {"content": [{"text": json.dumps(
            [{"ref": "pq:1", "stance": 5, "why": "over-range"},
             {"ref": "edm:2", "stance": -1, "why": "leans against"}])}]}
        results = stance._parse_reply(reply)
        stance.store_scores(conn, results, "2026-08-04")
        rows = {r["ref"]: r["stance"] for r in conn.execute("SELECT ref, stance FROM stance")}
        self.assertEqual(rows, {"pq:1": 2, "edm:2": -1})  # 5 clamped to +2

    def test_parse_reply_strips_markdown_fences(self):
        reply = {"content": [{"text": '```json\n[{"ref": "pq:1", "stance": 1, "why": "w"}]\n```'}]}
        self.assertEqual(stance._parse_reply(reply)[0].ref, "pq:1")

    def test_parse_reply_salvages_truncated_array(self):
        """A max_tokens cut mid-array keeps every complete object (live
        failure 2026-08-04: batch reply truncated, whole run died)."""
        reply = {"content": [{"text":
            '[{"ref": "pq:1", "stance": 0, "why": "a"}, {"ref": "pq:2", "stance": 2, "why": "b"}, {"ref": "pq:3", "st'}]}
        results = stance._parse_reply(reply)
        self.assertEqual([r.ref for r in results], ["pq:1", "pq:2"])

    def test_unscored_refs_dedupe_shared_refs(self):
        conn = fresh_conn()
        intel.record_event(conn, 1, "2026-08-01", "edm", "edm:9", "Sponsored", areas=[2])
        intel.record_event(conn, 2, "2026-08-01", "edm-signed", "edm:9", "Signed", areas=[2])
        intel.record_event(conn, 3, "2026-08-01", "vote", "div:c5:aye", "Voted Aye: X")
        intel.record_event(conn, 4, "2026-08-01", "vote", "div:c5:aye", "Voted Aye: X")
        refs = sorted(r["ref"] for r in stance.unscored_refs(conn))
        # One row per motion (sponsor + signer share it) and per vote
        # direction (both Aye voters share it).
        self.assertEqual(refs, ["div:c5:aye", "edm:9"])

    def test_rescoring_is_idempotent(self):
        conn = fresh_conn()
        intel.record_event(conn, 1, "2026-08-01", "pq", "pq:1", "L", areas=[11])
        stance.store_scores(conn, [stance.StanceResult("pq:1", 1, "w")], "2026-08-04")
        self.assertEqual(stance.unscored_refs(conn), [])


class SuggestRowsTests(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()
        member(self.conn, 1, "Ally Sponsor")
        member(self.conn, 2, "Neutral Asker")
        member(self.conn, 3, "Opponent Signer", party="Lab")

    def seed(self, mid, kind, ref, line, st=None, why="", date="2026-07-01", areas=(11,)):
        intel.record_event(self.conn, mid, date, kind, ref, line, areas=list(areas))
        if st is not None:
            stance.store_scores(self.conn, [stance.StanceResult(ref, st, why)], date)

    def test_columns_from_stance_and_gradient_ordering(self):
        self.seed(1, "edm", "edm:1", "Sponsored EDM: stop the boats", st=2)
        self.seed(2, "pq", "pq:1", "Asylum Hotels", st=0)
        self.seed(3, "edm-signed", "edm:2", "Signed EDM: welcome refugees", st=-1)
        rows = stance.suggest_rows(self.conn, 11)
        self.assertEqual([(r["decision_maker"].split(" (")[0], r["column"]) for r in rows],
                         [("Ally Sponsor", "++"), ("Neutral Asker", "0"),
                          ("Opponent Signer", "-")])

    def test_most_directional_evidence_wins_and_conflict_flagged(self):
        self.seed(1, "pq", "pq:1", "Neutral question", st=0, date="2026-07-30")
        self.seed(1, "edm-signed", "edm:1", "Signed EDM: directional", st=-2, date="2026-03-01")
        self.seed(1, "pq", "pq:2", "Leaning question", st=1, date="2026-07-01")
        rows = stance.suggest_rows(self.conn, 11)
        self.assertEqual(rows[0]["column"], "--")   # |stance| beats recency
        self.assertTrue(rows[0]["conflict"])        # + and - evidence both present
        self.assertIn("CONFLICTING SIGNALS", rows[0]["comments"])

    def test_unscored_evidence_sits_at_zero_not_invented(self):
        self.seed(2, "pq", "pq:9", "No stance row yet")
        rows = stance.suggest_rows(self.conn, 11)
        self.assertEqual(rows[0]["column"], "0")
        self.assertIn("[unscored]", rows[0]["comments"])

    def test_only_requested_area_included(self):
        self.seed(1, "pq", "pq:1", "Migration q", areas=(11,))
        self.seed(2, "pq", "pq:2", "Abortion q", areas=(1,))
        rows = stance.suggest_rows(self.conn, 11)
        self.assertEqual(len(rows), 1)


class VoteEvidenceTests(unittest.TestCase):
    """Division votes: direction-encoded refs, top of the evidence hierarchy."""

    def setUp(self):
        self.conn = fresh_conn()
        member(self.conn, 1, "Voting MP")

    def test_vote_outranks_contrary_edm_signature(self):
        intel.record_event(self.conn, 1, "2026-05-01", "edm-signed", "edm:1",
                           "Signed EDM", areas=[11])
        stance.store_scores(self.conn, [stance.StanceResult("edm:1", 2, "pro")], "d")
        intel.record_event(self.conn, 1, "2026-03-01", "vote", "div:c9:aye",
                           "Voted Aye: Safety of Rwanda Bill", areas=[11])
        stance.store_scores(self.conn, [stance.StanceResult("div:c9:aye", -2, "anti")], "d")
        rows = stance.suggest_rows(self.conn, 11)
        self.assertEqual(rows[0]["column"], "--")  # equal |stance|: vote weight wins

    def test_aye_and_no_refs_classify_independently(self):
        member(self.conn, 2, "Other MP")
        intel.record_event(self.conn, 1, "2026-03-01", "vote", "div:c9:aye", "Voted Aye: X", areas=[11])
        intel.record_event(self.conn, 2, "2026-03-01", "vote", "div:c9:no", "Voted No: X", areas=[11])
        refs = sorted(r["ref"] for r in stance.unscored_refs(self.conn))
        self.assertEqual(refs, ["div:c9:aye", "div:c9:no"])


class BreakdownParseTests(unittest.TestCase):
    def test_commons_breakdown(self):
        from src.ingest import divisions
        payload = {"DivisionId": 1798, "Number": 1, "Title": "Rwanda Bill",
                   "Date": "2024-04-22T00:00:00", "AyeCount": 1, "NoCount": 1,
                   "Ayes": [{"MemberId": 14, "Name": "A MP", "Party": "Con",
                             "MemberFrom": "Wokingham"}],
                   "Noes": [{"MemberId": 15, "Name": "B MP", "Party": "Lab",
                             "MemberFrom": "Leeds"}]}
        division, voters = divisions.parse_commons_breakdown(payload)
        self.assertEqual(division.id, 1798)
        self.assertEqual([(v.member_id, v.vote) for v in voters],
                         [(14, "aye"), (15, "no")])

    def test_lords_breakdown_normalises_content(self):
        from src.ingest import divisions
        payload = {"divisionId": 3128, "number": 1, "title": "Rwanda Bill",
                   "date": "2024-04-22T00:00:00",
                   "contents": [{"memberId": 147, "name": "Lord A",
                                 "party": "Lab", "memberFrom": "Life peer"}],
                   "notContents": [{"memberId": 148, "name": "Lord B",
                                    "party": "Con", "memberFrom": "Life peer"}]}
        division, voters = divisions.parse_lords_breakdown(payload)
        self.assertEqual([(v.member_id, v.vote) for v in voters],
                         [(147, "aye"), (148, "no")])


class FullRosterTests(unittest.TestCase):
    """Christopher, 2026-08-04: the 5CA sheet covers all sitting MPs."""

    def setUp(self):
        self.conn = fresh_conn()
        member(self.conn, 1, "Active MP")
        member(self.conn, 2, "Quiet MP")
        member(self.conn, 3, "Active Peer", house="Lords", seat="Life peer")
        self.conn.execute("UPDATE members SET current_mp = 1 WHERE id IN (1, 2)")
        for mid in (1, 3):
            intel.record_event(self.conn, mid, "2026-07-01", "pq",
                               "pq:{0}".format(mid), "Q", areas=[11])
            stance.store_scores(self.conn,
                                [stance.StanceResult("pq:{0}".format(mid), 1, "w")],
                                "2026-08-04")

    def test_every_sitting_mp_gets_a_row_peers_excluded(self):
        rows = {r["decision_maker"].split(" (")[0]: r
                for r in stance.suggest_rows(self.conn, 11, full_roster=True)}
        self.assertEqual(set(rows), {"Active MP", "Quiet MP"})
        self.assertEqual(rows["Active MP"]["column"], "+")
        self.assertEqual(rows["Quiet MP"]["column"], "0")
        self.assertIn("No recorded activity", rows["Quiet MP"]["comments"])

    def test_active_only_mode_still_includes_peers(self):
        names = {r["decision_maker"].split(" (")[0]
                 for r in stance.suggest_rows(self.conn, 11)}
        self.assertEqual(names, {"Active MP", "Active Peer"})


if __name__ == "__main__":
    unittest.main()
