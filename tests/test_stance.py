"""Stance layer + 5CA sheet generation (docs/5ca-notes.md)."""

import datetime
import json
import unittest.mock
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

    def test_parse_reply_tolerates_preamble_prose(self):
        """Live failure 2026-08-04: occasional replies opened with prose
        before the JSON array and the whole batch was lost."""
        reply = {"content": [{"text":
            'Here are the classifications:\n[{"ref": "pq:1", "stance": 0, "why": "w"}]'}]}
        self.assertEqual(stance._parse_reply(reply)[0].ref, "pq:1")

    def test_parse_reply_strips_markdown_fences(self):
        reply = {"content": [{"text": '```json\n[{"ref": "pq:1", "stance": 1, "why": "w"}]\n```'}]}
        self.assertEqual(stance._parse_reply(reply)[0].ref, "pq:1")

    def test_parse_reply_salvages_break_inside_a_string(self):
        """A cut landing mid-string defeated the old last-'}' salvage, which
        lost 39 whole batches (2026-08-05)."""
        reply = {"content": [{"text":
            '[{"ref": "pq:1", "stance": 1, "why": "fine"}, '
            '{"ref": "pq:2", "stance": 0, "why": "broken } mid string'}]}
        results = stance._parse_reply(reply)
        self.assertEqual([r.ref for r in results], ["pq:1"])

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
        intel.record_event(conn, 3, "2026-08-01", "vote", "div:c5:aye", "Voted Aye: X", areas=[2])
        intel.record_event(conn, 4, "2026-08-01", "vote", "div:c5:aye", "Voted Aye: X", areas=[2])
        intel.record_event(conn, 5, "2026-08-01", "pq", "pq:7", "No area at all")
        refs = sorted(r["ref"] for r in stance.unscored_refs(conn))
        # One row per motion (sponsor + signer share it) and per vote
        # direction (both Aye voters share it). The area-less row is skipped:
        # it renders nowhere, so scoring it would be paying for nothing.
        self.assertEqual(refs, ["div:c5:aye", "edm:9"])

    def test_rescoring_is_idempotent(self):
        conn = fresh_conn()
        intel.record_event(conn, 1, "2026-08-01", "pq", "pq:1", "L", areas=[11])
        stance.store_scores(conn, [stance.StanceResult("pq:1", 1, "w")], "2026-08-04")
        self.assertEqual(stance.unscored_refs(conn), [])


class EvidenceTextTests(unittest.TestCase):
    """The classifier sees the matched passage in context, never alone."""

    def test_excerpt_centred_in_surrounding_text(self):
        text = ("A" * 1000) + "the matched words" + ("B" * 1000)
        ev = stance.Evidence(ref="h:1", kind="debate", line="L",
                             text=text, excerpt="the matched words")
        out = stance._evidence_text(ev)
        self.assertIn("the matched words", out)
        self.assertIn("A", out)   # context before survives
        self.assertIn("B", out)   # context after survives
        self.assertLessEqual(len(out), 1500)

    def test_excerpt_not_in_text_sends_both(self):
        ev = stance.Evidence(ref="h:2", kind="debate", line="L",
                             text="full contribution", excerpt="matched bit")
        out = stance._evidence_text(ev)
        self.assertTrue(out.startswith("matched bit"))
        self.assertIn("full contribution", out)

    def test_prefix_when_no_excerpt(self):
        ev = stance.Evidence(ref="h:3", kind="pq", line="L", text="Q" * 2000)
        self.assertEqual(len(stance._evidence_text(ev)), 1500)


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


class HansardTests(unittest.TestCase):
    ROW = {"ContributionExtId": "ABC-123", "MemberId": 4511,
           "MemberName": "Dr Rupa Huq", "SittingDate": "2024-03-26T00:00:00",
           "House": "Commons", "DebateSection": "Topical Questions",
           "ContributionTextFull": "Full speech text about abortion clinics.",
           "DebateSectionExtId": "DEF-456"}

    def test_parse_and_public_deep_link(self):
        from src.ingest import hansard
        c = hansard.parse_contribution(self.ROW)
        self.assertEqual((c.member_id, c.date.isoformat()), (4511, "2024-03-26"))
        self.assertEqual(
            c.url,
            "https://hansard.parliament.uk/Commons/2024-03-26/debates/DEF-456/#contribution-ABC-123")
        self.assertIn("Full speech", c.text)

    def test_speech_outranks_edm_sponsorship_but_not_vote(self):
        self.assertGreater(stance.KIND_WEIGHT["debate"], stance.KIND_WEIGHT["edm"])
        self.assertGreater(stance.KIND_WEIGHT["vote"], stance.KIND_WEIGHT["debate"])


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


class WeeklySectionAreaGuardTests(unittest.TestCase):
    """An issue area is the precondition for appearing in a section headed
    "on our issues" (Christopher, 2026-08-05)."""

    def _event(self, kind, areas, line="L", mid=1):
        return {"member_id": mid, "kind": kind, "line": line, "name": "N",
                "party": "P", "seat": "S", "areas": areas}

    def test_area_less_rows_never_render(self):
        from src import digest
        events = [self._event("debate", None, "Spoke: Extreme Heat: Preparedness"),
                  self._event("pq", "[]", "Dementia: Health Services", mid=2)]
        self.assertEqual(digest.mp_lines_from_events(events), [])

    def test_questions_omitted_they_have_their_own_section(self):
        """Christopher, 2026-08-05: every captured question reaches the Written
        questions section or its companion page, so repeating them here printed
        the same item twice with less detail."""
        from src import digest
        events = [self._event("pq", "[7]", "Internet: Age Assurance"),
                  self._event("debate", "[7]", "Spoke: Online Safety Act", mid=2)]
        lines = digest.mp_lines_from_events(events)
        self.assertEqual(len(lines), 1)
        self.assertIn("Spoke: Online Safety Act", lines[0])

    def test_tagged_rows_still_render(self):
        from src import digest
        lines = digest.mp_lines_from_events([self._event("debate", "[2]", "Spoke: Hospices")])
        self.assertEqual(len(lines), 1)
        self.assertIn("Spoke: Hospices", lines[0])


class MemberStateTests(unittest.TestCase):
    """The distinction that makes the Moved column honest: the member moving
    versus us reassessing the same evidence (Christopher, 2026-08-07)."""

    def setUp(self):
        self.conn = fresh_conn()

    def row(self, mid, column, ref, n=3):
        return {"member_id": mid, "column": column, "decided_ref": ref, "n_events": n}

    def test_first_run_is_a_baseline(self):
        state = stance.update_member_state(self.conn, 2, [self.row(1, "++", "div:c9:no")],
                                          "2026-08-07")
        self.assertEqual(state[1]["movement"], stance.NEW)
        self.assertEqual(stance.movement_label(stance.NEW, None, "++", "2026-08-07"),
                         ("NEW", "first sheet"))

    def test_unchanged_keeps_the_original_change_date(self):
        stance.update_member_state(self.conn, 2, [self.row(1, "++", "div:c9:no")], "2026-08-01")
        state = stance.update_member_state(self.conn, 2, [self.row(1, "++", "div:c9:no")],
                                          "2026-08-08")
        self.assertEqual(state[1]["movement"], stance.UNCHANGED)
        self.assertEqual(state[1]["changed_at"], "2026-08-01")

    def test_new_deciding_evidence_means_the_member_moved(self):
        stance.update_member_state(self.conn, 2, [self.row(1, "0", "pq:1")], "2026-08-01")
        state = stance.update_member_state(self.conn, 2, [self.row(1, "++", "div:c9:no")],
                                           "2026-08-08")
        self.assertEqual(state[1]["movement"], stance.MOVED_UP)
        label, detail = stance.movement_label(state[1]["movement"], state[1]["prev"],
                                              "++", state[1]["changed_at"])
        self.assertEqual(label, "moved up")
        self.assertIn("0 to ++", detail)

    def test_same_deciding_evidence_rescored_means_WE_moved(self):
        """Tonight's rescore shifted ~460 speeches. Without this branch the
        column would have reported hundreds of members changing position."""
        stance.update_member_state(self.conn, 2, [self.row(1, "0", "hansard:A")], "2026-08-01")
        state = stance.update_member_state(self.conn, 2, [self.row(1, "++", "hansard:A")],
                                           "2026-08-08")
        self.assertEqual(state[1]["movement"], stance.REASSESSED)
        self.assertEqual(stance.movement_label(state[1]["movement"], "0", "++", None)[0],
                         "reassessed")

    def test_downward_movement_detected(self):
        stance.update_member_state(self.conn, 2, [self.row(1, "+", "pq:1")], "2026-08-01")
        state = stance.update_member_state(self.conn, 2, [self.row(1, "--", "div:c1:aye")],
                                           "2026-08-08")
        self.assertEqual(state[1]["movement"], stance.MOVED_DOWN)

    def test_areas_are_tracked_independently(self):
        stance.update_member_state(self.conn, 1, [self.row(1, "++", "pq:1")], "2026-08-01")
        stance.update_member_state(self.conn, 2, [self.row(1, "--", "pq:2")], "2026-08-01")
        state = stance.update_member_state(self.conn, 1, [self.row(1, "++", "pq:1")],
                                           "2026-08-08")
        self.assertEqual(state[1]["movement"], stance.UNCHANGED)


class BasedOnTests(unittest.TestCase):
    def test_names_the_kind_and_the_age(self):
        today = datetime.date(2026, 8, 7)
        self.assertEqual(stance.based_on("vote", "2026-08-05", today), "a vote, this week")
        self.assertEqual(stance.based_on("debate", "2026-07-01", today), "a speech, 5 weeks ago")
        self.assertEqual(stance.based_on("edm-signed", "2025-06-20", today),
                         "a motion signed, 14 months ago")
        self.assertEqual(stance.based_on("vote", "2020-06-17", today), "a vote, 6 years ago")

    def test_no_evidence_says_so(self):
        self.assertEqual(stance.based_on(None, None), "no evidence")

    def test_a_bad_date_still_names_the_kind(self):
        self.assertEqual(stance.based_on("pq", "not-a-date"), "a question")


class CapTests(unittest.TestCase):
    """Christopher, 2026-08-05: voting for the Northern Ireland abortion
    regulations must not read as strong support, but a member with an
    otherwise good record must not be branded a strong opponent either."""

    CFG = {"overrides": [{"match": "Abortion (Northern Ireland)", "aye": -1,
                          "why_aye": "Voted to extend abortion services to NI"}],
           "caps": [{"match": "Abortion (Northern Ireland)", "direction": "aye",
                     "ceiling": 1, "note": "CAPPED at + : NI regulations"}],
           "free_vote_titles": [], "excluded_from_5ca": []}

    def setUp(self):
        self.conn = fresh_conn()
        member(self.conn, 1, "Good Record MP")
        member(self.conn, 2, "Only NI Vote MP")
        member(self.conn, 3, "Genuine Opponent MP")

    def seed(self, mid, ref, line, st, date="2026-01-01"):
        intel.record_event(self.conn, mid, date, "vote" if ref.startswith("div") else "edm",
                           ref, line, areas=[1])
        stance.store_scores(self.conn, [stance.StanceResult(ref, st, "w")], date)

    def test_good_record_capped_to_plus_not_double_plus(self):
        self.seed(1, "edm:1", "Sponsored EDM: defend the unborn", 2)
        self.seed(1, "div:c9:aye", "Voted Aye: Abortion (Northern Ireland) Regulations 2021", -2)
        stance.apply_overrides(self.conn, self.CFG, "2026-08-05")
        row = next(r for r in stance.suggest_rows(self.conn, 1, overrides_cfg=self.CFG)
                   if r["member_id"] == 1)
        self.assertEqual(row["column"], "+")
        self.assertIn("CAPPED", row["comments"])

    def test_ni_vote_alone_is_minus_not_double_minus(self):
        self.seed(2, "div:c9:aye", "Voted Aye: Abortion (Northern Ireland) Regulations 2021", -2)
        stance.apply_overrides(self.conn, self.CFG, "2026-08-05")
        row = next(r for r in stance.suggest_rows(self.conn, 1, overrides_cfg=self.CFG)
                   if r["member_id"] == 2)
        self.assertEqual(row["column"], "-")

    def test_cap_never_rescues_a_genuine_opponent(self):
        self.seed(3, "div:c9:aye", "Voted Aye: Abortion (Northern Ireland) Regulations 2021", -2)
        self.seed(3, "edm:2", "Sponsored EDM: decriminalise abortion fully", -2)
        stance.apply_overrides(self.conn, self.CFG, "2026-08-05")
        row = next(r for r in stance.suggest_rows(self.conn, 1, overrides_cfg=self.CFG)
                   if r["member_id"] == 3)
        self.assertEqual(row["column"], "--")  # caps limit the upside only

    def test_single_direction_rule_leaves_the_other_side_alone(self):
        self.seed(1, "div:c9:no", "Voted No: Abortion (Northern Ireland) Regulations 2021", 2)
        stance.apply_overrides(self.conn, self.CFG, "2026-08-05")
        row = self.conn.execute("SELECT stance, model FROM stance WHERE ref='div:c9:no'").fetchone()
        self.assertEqual((row["stance"], row["model"]), (2, stance.STANCE_MODEL))


class AssistedSuicideCapTests(unittest.TestCase):
    """Christopher, 12 Sept 2026: nobody who ever voted for assisted suicide is a ++,
    however they voted since. The seven who moved to No at the 2026 Second Reading
    read as + with the cap's note."""

    def test_an_earlier_aye_caps_a_later_convert_at_plus(self):
        import sqlite3
        from src import db, members, stance
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        members.cache_put(conn, members.Member(id=1, name="Convert MP", party="Labour", seat="Seat", house="Commons", since="2024-07-04"))
        conn.execute("UPDATE members SET current_mp = 1")
        stance.ensure_table(conn)
        for ref, date, line, sc in (("div:c2071:aye", "2025-06-20", "Voted Aye: Terminally Ill Adults (End of Life) Bill: Third Reading", -2),
                                    ("div:c2428:no", "2026-09-11", "Voted No: Terminally Ill Adults (End of Life) Bill: Second Reading", 2)):
            conn.execute("INSERT INTO mp_events (member_id, date, kind, ref, line, areas) VALUES (1, ?, 'vote', ?, ?, '[2]')", (date, ref, line))
            conn.execute("INSERT INTO stance (ref, stance, why, model, scored_at) VALUES (?, ?, 'w', 'm', '2026-09-12')", (ref, sc))
        conn.commit()
        cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
        row = stance.suggest_rows(conn, 2, full_roster=True, overrides_cfg=cfg, house="Commons")[0]
        self.assertEqual(row["column"], "+")
        self.assertIn("CAPPED at + : voted for the assisted suicide Bill", row["comments"])
        self.assertTrue(row["conflict"])


class ExcludedAreaTests(unittest.TestCase):
    def test_excluded_areas_parsed_from_config(self):
        cfg = stance.load_overrides(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "stance_overrides.yaml"))
        # Migration is collated but never a 5CA sheet (Christopher, 2026-08-05).
        self.assertIn(11, cfg["excluded_from_5ca"])

    def test_missing_key_defaults_empty(self):
        self.assertEqual(stance.load_overrides("/nonexistent")["excluded_from_5ca"], [])


class WeeklyScoringPassTests(unittest.TestCase):
    """The weekly pass must be cost-bounded and never silently truncate."""

    def setUp(self):
        self.conn = fresh_conn()
        member(self.conn, 1, "Some MP")
        for n in range(50):
            intel.record_event(self.conn, 1, "2026-08-01", "pq",
                               "pq:{0}".format(n), "Question {0}".format(n), areas=[11])

    def _fake_transport(self, payload, api_key):
        body = json.loads(payload["messages"][0]["content"])
        return {"content": [{"text": json.dumps(
            [{"ref": row["ref"], "stance": 0, "why": "neutral"} for row in body])}]}

    def test_cap_defers_the_remainder_and_reports_it(self):
        with unittest.mock.patch.object(stance, "_default_transport", self._fake_transport):
            stats = stance.score_pending(self.conn, "/nonexistent", "key",
                                         "2026-08-05", max_refs=20)
        self.assertEqual(stats["scored"], 20)
        self.assertEqual(stats["deferred"], 30)
        self.assertEqual(len(stance.unscored_refs(self.conn)), 30)

    def test_second_run_picks_up_the_deferred_refs(self):
        with unittest.mock.patch.object(stance, "_default_transport", self._fake_transport):
            stance.score_pending(self.conn, "/nonexistent", "key", "2026-08-05", max_refs=20)
            stats = stance.score_pending(self.conn, "/nonexistent", "key", "2026-08-05")
        self.assertEqual(stats["scored"], 30)
        self.assertEqual(stance.unscored_refs(self.conn), [])

    def test_failed_batch_keeps_earlier_batches(self):
        calls = {"n": 0}

        def flaky(payload, api_key):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("HTTP 400: credit balance is too low")
            return self._fake_transport(payload, api_key)

        with unittest.mock.patch.object(stance, "_default_transport", flaky):
            stats = stance.score_pending(self.conn, "/nonexistent", "key", "2026-08-05")
        self.assertEqual(stats["failed_batches"], 1)
        self.assertEqual(stats["scored"], 30)          # 20 lost, the rest banked
        self.assertEqual(len(stance.unscored_refs(self.conn)), 20)


class EditorialOverrideTests(unittest.TestCase):
    """Christopher, 2026-08-04: the org's judgement on named bills outranks
    the classifier; Border Security Bill votes carry no enforcement weight."""

    CFG = {"overrides": [
        {"match": "Illegal Migration Bill",
         "when_any": ["motion to disagree", "Second Reading"],
         "unless_any": ["amendment to second reading"],
         "aye": 2, "no": -2,
         "why_aye": "Backed the deterrence framework",
         "why_no": "Voted against enforcement"},
        {"match": "Border Security, Asylum and Immigration Bill",
         "aye": 0, "no": 0,
         "why_aye": "No enforcement weight", "why_no": "No enforcement weight"},
    ], "free_vote_titles": ["Terminally Ill Adults (End of Life) Bill"]}

    def setUp(self):
        self.conn = fresh_conn()
        member(self.conn, 1, "Swing MP", party="Lab")

    def seed_vote(self, ref, line, claude_stance):
        intel.record_event(self.conn, 1, "2023-07-11", "vote", ref, line, areas=[11])
        stance.store_scores(self.conn, [stance.StanceResult(ref, claude_stance, "claude why")], "d")

    def test_against_enforcement_scores_badly_regardless_of_claude(self):
        self.seed_vote("div:c100:no",
                       "Voted No: Illegal Migration Bill: motion to disagree with Lords Amendment 9",
                       0)  # classifier called it procedural
        stance.apply_overrides(self.conn, self.CFG, "2026-08-04")
        row = self.conn.execute("SELECT stance, why, model FROM stance").fetchone()
        self.assertEqual((row["stance"], row["model"]), (-2, "override"))
        self.assertIn("against enforcement", row["why"])

    def test_border_security_bill_zeroed_never_offsets(self):
        self.seed_vote("div:c100:no", "Voted No: Illegal Migration Bill: motion to disagree with Lords Amendment 9", 0)
        self.seed_vote("div:c200:aye", "Voted Aye: Border Security, Asylum and Immigration Bill: Third Reading", 2)
        stance.apply_overrides(self.conn, self.CFG, "2026-08-04")
        rows = stance.suggest_rows(self.conn, 11, overrides_cfg=self.CFG)
        self.assertEqual(rows[0]["column"], "--")     # the anti-enforcement record dominates
        self.assertFalse(rows[0]["conflict"])         # BSB aye no longer manufactures a conflict

    def test_wrecking_amendment_excluded_from_override(self):
        self.seed_vote("div:c300:aye",
                       "Voted Aye: Illegal Migration Bill amendment to second reading", -1)
        stance.apply_overrides(self.conn, self.CFG, "2026-08-04")
        row = self.conn.execute("SELECT stance, model FROM stance").fetchone()
        self.assertEqual((row["stance"], row["model"]), (-1, stance.STANCE_MODEL))

    def test_free_vote_noted_in_comments_and_preferred(self):
        self.seed_vote("div:c400:no",
                       "Voted No: Terminally Ill Adults (End of Life) Bill: Third Reading", 2)
        rows = stance.suggest_rows(self.conn, 11, overrides_cfg=self.CFG)
        self.assertIn("; free vote]", rows[0]["comments"])

    def test_lords_whip_flag_noted(self):
        stance.ensure_whip_table(self.conn)
        self.conn.execute("INSERT INTO division_whip VALUES ('div:l500', 1)")
        self.seed_vote("div:l500:aye", "Voted Aye: Some Lords Division", 1)
        rows = stance.suggest_rows(self.conn, 11, overrides_cfg=self.CFG)
        self.assertIn("; whipped]", rows[0]["comments"])


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


class LordsRosterTests(unittest.TestCase):
    def test_full_roster_selects_by_house(self):
        conn = fresh_conn()
        member(conn, 1, "Sitting MP")
        member(conn, 2, "Sitting Peer", house="Lords", seat="Life peer")
        conn.execute("UPDATE members SET current_mp=1 WHERE id=1")
        conn.execute("UPDATE members SET current_peer=1 WHERE id=2")
        intel.record_event(conn, 1, "2026-07-01", "pq", "pq:1", "Q", areas=[11])
        intel.record_event(conn, 2, "2026-07-01", "pq", "pq:2", "Q", areas=[11])
        commons = stance.suggest_rows(conn, 11, full_roster=True)
        lords = stance.suggest_rows(conn, 11, full_roster=True, house="Lords")
        self.assertEqual([r["member_id"] for r in commons], [1])
        self.assertEqual([r["member_id"] for r in lords], [2])
        self.assertEqual(lords[0]["house"], "Lords")


class ConfidenceTests(unittest.TestCase):
    """suggest_confidence encodes the evidence philosophy; each rule pinned."""

    def tier(self, **kw):
        args = {"column": "+", "decided_kind": "vote", "decided_whip": None,
                "n_events": 5, "n_directional": 3, "conflict": False,
                "n_minority": 0}
        args.update(kw)
        return stance.suggest_confidence(**args)

    def test_no_evidence_has_no_marker(self):
        self.assertEqual(self.tier(n_events=0), (None, None))

    def test_genuine_split_is_thin_regardless_of_volume(self):
        tier, why = self.tier(conflict=True, n_events=40, n_directional=20,
                              n_minority=8)
        self.assertEqual(tier, "thin")
        self.assertIn("split", why)

    def test_blemish_under_ten_percent_keeps_tier_but_says_so(self):
        # Danny Kruger: 134 with-us, 6 misread committee speeches (4%).
        tier, why = self.tier(conflict=True, decided_whip="free vote",
                              n_events=173, n_directional=140, n_minority=6)
        self.assertEqual(tier, "strong")
        self.assertIn("6 contrary items", why)

    def test_ten_to_twentyfive_percent_contrary_downgrades_one_tier(self):
        tier, why = self.tier(conflict=True, decided_whip="free vote",
                              n_events=30, n_directional=20, n_minority=3)
        self.assertEqual(tier, "moderate")
        self.assertIn("contrary", why)

    def test_free_vote_is_strong_even_alone(self):
        # Two Terminally Ill Adults (End of Life) Bill free votes say more
        # than twenty whipped ones: volume rules do not apply.
        tier, why = self.tier(decided_whip="free vote", n_events=2,
                              n_directional=2)
        self.assertEqual(tier, "strong")
        self.assertIn("free vote", why)

    def test_whipped_vote_without_corroboration_caps_at_moderate(self):
        tier, why = self.tier(decided_whip="whipped", n_directional=1)
        self.assertEqual(tier, "moderate")
        self.assertIn("whipped", why)

    def test_corroborated_vote_is_strong(self):
        tier, _ = self.tier(n_directional=4)
        self.assertEqual(tier, "strong")

    def test_two_items_are_thin_unless_free_vote(self):
        self.assertEqual(self.tier(n_events=2, n_directional=2)[0], "thin")

    def test_neutral_scales_with_volume(self):
        self.assertEqual(self.tier(column="0", n_events=10, n_directional=0)[0],
                         "moderate")
        self.assertEqual(self.tier(column="0", n_events=3, n_directional=0)[0],
                         "thin")

    def test_speeches_never_reach_strong(self):
        tier, _ = self.tier(decided_kind="debate", n_events=30, n_directional=15)
        self.assertEqual(tier, "moderate")

    def test_questions_only_are_thin(self):
        self.assertEqual(self.tier(decided_kind="pq", n_events=8,
                                   n_directional=3)[0], "thin")


if __name__ == "__main__":
    unittest.main()


class SkipHiddenTests(unittest.TestCase):
    """A backfill scores the displayable ground first; migration-only refs render
    nowhere and are a separate spend (2026-09-08)."""

    def test_skip_hidden_drops_refs_whose_only_areas_are_hidden(self):
        import sqlite3
        from src import db, intel
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row                    # as db.connect does; the filter reads columns by name
        conn = db.init_db(conn)
        intel.record_event(conn, 1, "2019-07-09", "debate", "hansard:A", "Spoke: A", areas=[1])
        intel.record_event(conn, 2, "2019-07-09", "debate", "hansard:B", "Spoke: B", areas=[11])
        intel.record_event(conn, 3, "2019-07-09", "debate", "hansard:C", "Spoke: C", areas=[7, 11])
        self.assertEqual(sorted(r["ref"] for r in stance.unscored_refs(conn)), ["hansard:A", "hansard:B", "hansard:C"])
        self.assertEqual(sorted(r["ref"] for r in stance.unscored_refs(conn, skip_hidden=True)), ["hansard:A", "hansard:C"])
