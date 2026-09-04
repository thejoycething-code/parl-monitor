"""Devolved parity (Christopher, 2026-09-04: "We need everything to have
parity with westminster"): triage, verdicts and trackers for Scotland,
Wales and Northern Ireland.

Each test here pins a mistake that was actually made and measured while
building this, not a hypothetical one. Read the docstrings before
loosening any of them.
"""

import importlib.util
import json
import os
import re
import sqlite3
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


score = _load("devolved_score")
triage = _load("devolved_triage")
tracker = _load("make_devolved_votes")


def member(conn, pid, name, party=None, post=None, start=None, end=None):
    conn.execute("INSERT INTO sd_members (person_id, name, party, post, "
                 "start_date, end_date, captured_at) VALUES (?,?,?,?,?,?,?)",
                 (pid, name, party, post, start, end, "2026-01-01"))


def division(conn, key, dated, title, for_=None, against=None, areas="[1]"):
    conn.execute("INSERT INTO sd_divisions (key, dated, title, total_for, "
                 "total_against, total_abstain, areas, tier, first_seen, "
                 "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (key, dated, title, for_, against, None, areas,
                  1 if areas else None, "2026-01-01", "2026-01-01"))


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class JoinTests(unittest.TestCase):
    """The two chambers key their votes differently, and getting it wrong
    is silent: the page builds, the counts look plausible, and every vote
    belongs to nobody.

    NI first rendered 0 votes (joined on event_id, stored as doc_id).
    Wales then rendered 1,036 votes belonging to nobody: sd_votes.member_id
    holds the Senedd's own integers (1, 143, 145) and sd_members.person_id
    holds publicwhip URIs -- two id spaces with no overlap at all, so the
    only join available is the member's NAME.
    """

    def test_wales_joins_on_name_because_the_id_spaces_differ(self):
        conn = store()
        member(conn, "uk.org.publicwhip/person/900", "Siân Gwenllian",
               party="Plaid Cymru", post="Arfon", start="2021-05-06")
        division(conn, "D1", "2026-03-17", "LCM: Schools Bill", 37, 13)
        # member_id is the Senedd's integer; it must NOT be used to join
        conn.execute("INSERT INTO sd_votes (division_key, member_id, "
                     "member_name, result) VALUES "
                     "('D1', '143', 'Siân Gwenllian', 'For')")
        conn.execute("INSERT INTO sd_scored (division_key, person_id, vote, "
                     "verdict) VALUES ('D1', 'uk.org.publicwhip/person/900',"
                     " 'For', NULL)")
        conn.commit()
        data = tracker.build(conn, "wales")
        pid = "uk.org.publicwhip/person/900"
        self.assertEqual(list(data["votes"]), [pid],
                         "the vote must land on the member's person_id")
        self.assertEqual(data["votes"][pid]["D1"]["vote"], "For")

    def test_a_name_that_does_not_resolve_is_reported_never_dropped(self):
        """Never-silent-suppression, applied to the join.

        130 names vote in the Welsh record and 96 Members sit today; the
        difference is departed Members, the Llywydd by title, and
        "Casting Vote". Those rows cannot be shown, so the build must SAY
        how many it set aside.
        """
        conn = store()
        member(conn, "p/1", "Siân Gwenllian", start="2021-05-06")
        division(conn, "D1", "2026-03-17", "LCM: Schools Bill")
        for n, who in enumerate(("Siân Gwenllian", "Casting Vote",
                                 "Y Llywydd / The Llywydd")):
            conn.execute("INSERT INTO sd_votes (division_key, member_id, "
                         "member_name, result) VALUES ('D1', ?, ?, 'For')",
                         (str(n), who))
        conn.execute("INSERT INTO sd_scored (division_key, person_id, vote, "
                     "verdict) VALUES ('D1', 'p/1', 'For', NULL)")
        conn.commit()
        data = tracker.build(conn, "wales")
        self.assertEqual(sorted(data["unresolved"]),
                         ["Casting Vote", "Y Llywydd / The Llywydd"])

    def test_ni_joins_on_doc_id(self):
        conn = store()
        conn.execute("INSERT INTO ni_members (person_id, name, display_name,"
                     " party, constituency, first_seen, last_seen) VALUES "
                     "('m/1', 'Caoimhe Archibald', 'Dr Caoimhe Archibald', "
                     "'Sinn Féin', 'East Londonderry', '2026-01-01', "
                     "'2026-01-01')")
        conn.execute("INSERT INTO ni_divisions (doc_id, dated, subject, "
                     "areas, first_seen, last_seen) VALUES ('X1', "
                     "'2026-06-30', 'Amendment 97', '[1]', '2026-01-01', "
                     "'2026-01-01')")
        conn.execute("INSERT INTO ni_votes (doc_id, person_id, member, vote, "
                     "captured_at) VALUES ('X1', 'm/1', 'Archibald', 'NO', "
                     "'2026-01-01')")
        conn.execute("INSERT INTO ni_scored (division_key, person_id, vote, "
                     "verdict) VALUES ('X1', 'm/1', 'NO', NULL)")
        conn.commit()
        data = tracker.build(conn, "ni")
        self.assertEqual(data["votes"]["m/1"]["X1"]["vote"], "NO")


class RosterTests(unittest.TestCase):
    def test_only_sitting_members_are_listed(self):
        """The Welsh roster carries a row per TERM -- 227 ids for 96
        sitting Members. Listing someone who left in 2016 invites a
        reader to write to a Member who is not there."""
        conn = store()
        member(conn, "p/1", "Sitting Member", start="2026-05-08")
        member(conn, "p/2", "Departed Member", start="2011-05-06",
               end="2016-05-05")
        conn.commit()
        names = [m["name"] for m in tracker.build(conn, "wales")["members"]]
        self.assertEqual(names, ["Sitting Member"])

    def test_two_members_may_share_a_name(self):
        """The roster holds 227 distinct people and the bridge is their
        NAME, so a repeated name must resolve to ONE id deterministically
        (the first), never silently to whichever row came back last."""
        from src import devolved as dv
        conn = store()
        member(conn, "p/old", "Jane Jones", start="1999-05-06",
               end="2003-04-02")
        member(conn, "p/new", "Jane Jones", start="2026-05-08")
        conn.commit()
        self.assertEqual(dv.roster(conn)["jane jones"], "p/old")
        self.assertEqual(dv.roster(conn, sitting_only=True)["jane jones"],
                         "p/new")


class VerdictGateTests(unittest.TestCase):
    """signed_off gates the verdict here exactly as at Westminster: an
    unsigned division may show HOW someone voted, never what we think of
    it."""

    def test_unsigned_divisions_write_a_null_verdict(self):
        conn = store()
        member(conn, "p/1", "A Member")
        conn.execute("INSERT INTO sd_votes (division_key, member_id, "
                     "member_name, result) VALUES ('D1', '1', 'A Member', "
                     "'For')")
        conn.commit()
        div = {"key": "D1", "our_side": "for", "signed_off": False}
        score.load = lambda nation: [div]
        written, signed = score.score(conn, "wales", apply_it=True,
                                      log=lambda *a: None)
        row = conn.execute("SELECT verdict FROM sd_scored").fetchone()
        self.assertIsNone(row["verdict"])
        self.assertEqual(signed, 0)

    def test_a_signed_division_scores_both_ways(self):
        conn = store()
        member(conn, "p/1", "Ayes Member")
        member(conn, "p/2", "Noes Member")
        for n, (who, how) in enumerate((("Ayes Member", "For"),
                                        ("Noes Member", "Against"))):
            conn.execute("INSERT INTO sd_votes (division_key, member_id, "
                         "member_name, result) VALUES ('D1', ?, ?, ?)",
                         (str(n), who, how))
        conn.commit()
        score.load = lambda nation: [
            {"key": "D1", "our_side": "for", "signed_off": True}]
        score.score(conn, "wales", apply_it=True, log=lambda *a: None)
        got = {r["person_id"]: r["verdict"] for r in conn.execute(
            "SELECT person_id, verdict FROM sd_scored")}
        self.assertEqual(got, {"p/1": "good", "p/2": "bad"})

    def test_an_abstention_never_earns_a_verdict(self):
        """Not voting is not a position. 'Abstain', 'Absent' and 'Not
        voting' all resolve to no side, so no judgement is published."""
        for raw in ("Abstain", "ABSENT", "Not Voting", ""):
            self.assertIsNone(score.side_of(raw), raw)

    def test_each_chamber_s_own_words_for_the_lobbies(self):
        self.assertEqual(score.side_of("Content"), "for")      # Lords-style
        self.assertEqual(score.side_of("NOT CONTENT"), "against")
        self.assertEqual(score.side_of("Aye"), "for")
        self.assertEqual(score.side_of("no"), "against")


class EndToEndTests(unittest.TestCase):
    def test_a_signed_verdict_reaches_the_card(self):
        """The scorer and the page must agree on WHO a member is.

        They did not: the page resolved Welsh names to roster ids while
        the scorer wrote the Senedd's own integers into
        sd_scored.person_id, so every verdict lookup missed. Nothing
        looked broken because no Welsh division is signed off -- the
        failure was scheduled for the day one is. This test signs one.
        """
        conn = store()
        member(conn, "uk.org.publicwhip/person/900", "Siân Gwenllian",
               start="2021-05-06")
        member(conn, "uk.org.publicwhip/person/901", "Other Member",
               start="2021-05-06")
        division(conn, "D1", "2026-03-17", "LCM: Schools Bill", 37, 13)
        for n, (who, how) in enumerate((("Siân Gwenllian", "For"),
                                        ("Other Member", "Against"))):
            conn.execute("INSERT INTO sd_votes (division_key, member_id, "
                         "member_name, result) VALUES ('D1', ?, ?, ?)",
                         (str(n), who, how))
        conn.commit()
        score.load = lambda nation: [
            {"key": "D1", "our_side": "for", "signed_off": True}]
        score.score(conn, "wales", apply_it=True, log=lambda *a: None)
        tracker.load_config = lambda spec: {
            "D1": {"signed_off": True, "our_side": "for",
                   "short": "LCM: Schools Bill",
                   "meaning_good": "voted with us", "meaning_bad": "against"}}
        data = tracker.build(conn, "wales")
        got = {pid: v["D1"]["verdict"] for pid, v in data["votes"].items()}
        self.assertEqual(got, {"uk.org.publicwhip/person/900": "good",
                               "uk.org.publicwhip/person/901": "bad"})

    def test_rescoring_leaves_no_ghost_under_an_old_id(self):
        """Rows are keyed (division_key, person_id), so when a member's
        identity changes an INSERT OR REPLACE leaves the OLD row behind
        as a vote under an id nothing reads. The scorer clears the
        division first."""
        conn = store()
        member(conn, "p/1", "A Member", start="2021-05-06")
        conn.execute("INSERT INTO sd_votes (division_key, member_id, "
                     "member_name, result) VALUES ('D1', '7', 'A Member', "
                     "'For')")
        conn.execute("INSERT INTO sd_scored (division_key, person_id, vote, "
                     "verdict) VALUES ('D1', '7', 'For', NULL)")
        conn.commit()
        score.load = lambda nation: [
            {"key": "D1", "our_side": "for", "signed_off": True}]
        score.score(conn, "wales", apply_it=True, log=lambda *a: None)
        ids = [r[0] for r in conn.execute(
            "SELECT person_id FROM sd_scored WHERE division_key='D1'")]
        self.assertEqual(ids, ["p/1"], "the integer-keyed ghost survived")


class TrackerDisplayTests(unittest.TestCase):
    def test_an_unsigned_division_is_shown_without_judgement(self):
        src = open(os.path.join(ROOT, "templates", "devolved-votes.html"),
                   encoding="utf-8").read()
        self.assertIn("no signed verdict", src)

    def test_a_recorded_vote_beats_the_membership_dates(self):
        """Every sitting Welsh Member's start_date is 2026-05-08 (the
        96-seat Senedd) and every tracked division predates it, yet 29 of
        them sat in the previous Senedd and voted under the same id. A
        date-only test told Adam Price he was "not yet elected" for a vote
        he had actually cast."""
        src = open(os.path.join(ROOT, "templates", "devolved-votes.html"),
                   encoding="utf-8").read()
        guard = re.search(r"if \(([^)]*?)m\.start && d\.dated", src)
        self.assertIsNotNone(guard, "the not-yet-elected guard is gone")
        self.assertIn("!mine[d.key]", guard.group(1),
                      "a recorded vote must win over the dates")

    def test_missing_tallies_are_omitted_not_printed_as_null(self):
        """NI publishes no tally columns, so the card printed
        'null-null' under every division."""
        src = open(os.path.join(ROOT, "templates", "devolved-votes.html"),
                   encoding="utf-8").read()
        self.assertIn("d.for != null && d.against != null", src)

    def test_both_nations_build_from_one_template(self):
        self.assertEqual(sorted(tracker.NATIONS), ["ni", "wales"])


class LogRelayTests(unittest.TestCase):
    """run_monday.py relays a tool's FIRST line and drops the rest unless
    it names a caveat. A build that opens with an output path therefore
    tells an unattended log nothing, and a suppression it will not lift
    is a silent suppression."""

    CAVEAT = (r"\bNOT\b|missing|no recorded|gap|stale|gaps|published"
              r"|FAILED|adopted|no generated")

    @staticmethod
    def relayed(lines):
        """What run_monday.py would actually print for this output."""
        def noise(l):
            low = l.lower()
            return ("warning:" in low or l.startswith((" ", "\t"))
                    or ".py:" in l.split(" ")[0])
        speaking = [l for l in lines if l.strip() and not noise(l)]
        kept = [speaking[0]] if speaking else []
        kept += [l for l in speaking[1:]
                 if re.search(LogRelayTests.CAVEAT, l)]
        return kept

    def test_every_nation_and_its_caveats_survive_the_relay(self):
        out = ["wales 96 members, 17 division(s), 0 signed, 483 votes; "
               "ni 90 members, 7 division(s), 0 signed, 237 votes",
               "wales: 36 voter name(s) are missing from the sitting "
               "roster, so their votes are not shown: Altaf Hussain ...",
               "   -> /x/partner_site/ms-votes.html"]
        kept = self.relayed(out)
        self.assertEqual(len(kept), 2, "the caveat was dropped")
        self.assertIn("ni 90 members", kept[0],
                      "NI's summary must ride in the head line: an "
                      "indented or unquotable second summary is binned")
        self.assertIn("missing from the sitting roster", kept[1])

    def test_the_tool_emits_that_shape(self):
        src = open(os.path.join(ROOT, "tools", "make_devolved_votes.py"),
                   encoding="utf-8").read()
        self.assertIn('print("; ".join(stats))', src,
                      "one head line must cover every nation built")
        caveat = re.search(r'"\{0\}: \{1\} voter name\(s\) ([^"]+)"', src)
        self.assertIsNotNone(caveat, "the unresolved-names line is gone")
        self.assertRegex(caveat.group(1), self.CAVEAT,
                         "the relay will drop this line")

    def test_run_monday_passes_a_tool_s_arguments(self):
        src = open(os.path.join(ROOT, "run_monday.py"),
                   encoding="utf-8").read()
        self.assertIn("+ list(argv[1:])", src,
                      "the build loop drops every flag after argv[0]")


class TriageScopeTests(unittest.TestCase):
    def test_amendment_divisions_are_never_judged(self):
        """The judge sees only the BILL title, so it writes a line about
        the Bill; attached to "Amendment 47" that reads as what the
        amendment meant -- the Lords inversion wearing a why-line. A first
        run scored 268 Scottish divisions, 219 of them Stage 3 amendments
        on one Bill, while Holyrood's own scorer verdicts 3 of 218."""
        self.assertEqual(sorted(triage.AMENDMENT_FILTER),
                         ["ni_divisions", "sd_divisions", "sp_divisions"])

    def test_the_amendment_filter_actually_excludes_them(self):
        conn = store()
        triage.ensure_columns(conn)
        division(conn, "D1", "2026-09-01", "Stage 3 Amendment 47")
        division(conn, "D2", "2026-09-01", "LCM: Schools Bill")
        conn.commit()
        ids = [i.id for i in triage.pending(conn, today="2026-09-04")]
        self.assertIn("sd_divisions:D2", ids)
        self.assertNotIn("sd_divisions:D1", ids,
                         "an amendment division must not reach the judge")

    def test_a_keyless_run_refuses_to_stub_score(self):
        """Scores are once-ever, so a workflow that merely lacks the
        secret would freeze empty tier-derived stubs into every row and
        never revisit them. The keyless path leaves rows unscored unless
        --allow-stub is passed on purpose."""
        src = open(os.path.join(ROOT, "tools", "devolved_triage.py"),
                   encoding="utf-8").read()
        self.assertIn("--allow-stub", src)
        body = src[src.index("def main()"):]
        head = body[body.index("key = api_key()"):]
        self.assertLess(head.index("left UNSCORED"), head.index("score_stub"),
                        "the refusal must come BEFORE the stub path")

    def test_all_three_nations_reach_the_judge(self):
        tables = " ".join(triage.SOURCES)
        for prefix in ("sp_", "sd_", "ni_"):
            self.assertIn(prefix, tables,
                          "{0} has no source in devolved triage".format(
                              prefix))


if __name__ == "__main__":
    unittest.main()
