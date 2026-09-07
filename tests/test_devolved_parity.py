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


class EveryoneWhoVotedTests(unittest.TestCase):
    """Christopher, 2026-09-04: "Make sure all politicians are included."

    Every tracker listed only SITTING members, so anyone who voted and
    then left was invisible -- 32 Welsh Members of the Sixth Senedd
    (Mark Drakeford and the First Minister among them), 65 MSPs, and
    344 MPs, on precisely the divisions these pages exist to report.
    """

    def test_a_former_member_who_voted_is_listed_and_labelled(self):
        conn = store()
        member(conn, "p/1", "Sitting Member", start="2026-05-08")
        member(conn, "p/2", "Departed Voter", start="2021-05-06",
               end="2026-04-08")
        member(conn, "p/3", "Departed Silent", start="2011-05-06",
               end="2016-05-05")
        division(conn, "D1", "2026-03-17", "LCM: Schools Bill", 37, 13)
        conn.execute("INSERT INTO sd_votes (division_key, member_id, "
                     "member_name, result) VALUES ('D1', '1', "
                     "'Departed Voter', 'For')")
        conn.commit()
        data = tracker.build(conn, "wales")
        listed = {m["name"]: m["former"] for m in data["members"]}
        self.assertEqual(listed, {"Sitting Member": False,
                                  "Departed Voter": True},
                         "a former member earns a listing by VOTING; one "
                         "with nothing to show is still left off")
        self.assertEqual(data["votes"]["p/2"]["D1"]["vote"], "For")

    def test_a_seat_search_never_lands_on_a_former_member(self):
        """A former Member keeps their old constituency string, so a seat
        or postcode lookup that indexed them would answer with the person
        who no longer holds the seat."""
        for path in ("templates/devolved-votes.html",
                     "templates/vote-tracker.html"):
            src = open(os.path.join(ROOT, path), encoding="utf-8").read()
            self.assertIn("m.former", src, path)
            self.assertRegex(src, r"(!m\.former && norm\(m\.(seat|constituency)\)"
                                  r"|if \(!m\.former\) constIndex"
                                  r"|filter\(m => !m\.former\))",
                             "{0} still lets a former member own a seat"
                             .format(path))

    def test_a_former_member_s_silence_is_never_called_an_absence(self):
        """Parliament publishes no end date for the 344 former MPs, so
        the page cannot know whether they had left when a division was
        held. servedOn() fails open, which would print "DID NOT VOTE"
        for every division after they went."""
        src = open(os.path.join(ROOT, "templates", "vote-tracker.html"),
                   encoding="utf-8").read()
        body = src[src.index("function voteInfo("):]
        self.assertLess(body.index("m.former"), body.index("servedOn(m, d.date)"),
                        "the former-member case must be decided BEFORE "
                        "the service test that fails open")
        self.assertIn("FORMER MEMBER", body)


class NotOursTests(unittest.TestCase):
    """A human who read the Record outranks the title regex.

    Christopher, 2026-09-06: the Crime and Policing Bill LCM was tagged
    abortion because the Bill carried s.241, but abortion is a RESERVED
    matter in Wales (GoWA 2006 Sch 7A, Head J, J1), the motion consented
    only to devolved matters, and the refusal was about AI, facial
    recognition, non-crime hate incidents and concurrent powers. Struck.
    The collector re-derives areas from the title every week, so the
    strike has to be honoured at three points or it returns on Thursday.
    """

    def test_the_tracker_never_lists_a_struck_division(self):
        conn = store()
        member(conn, "p/1", "A Member", start="2021-05-06")
        division(conn, "D1", "2026-03-10", "LCM: Crime and Policing Bill")
        conn.execute("INSERT INTO sd_votes (division_key, member_id, member_name, "
                     "result) VALUES ('D1', '1', 'A Member', 'Against')")
        conn.commit()
        tracker.load_config = lambda spec: {"D1": {"not_ours": True}}
        self.assertEqual(tracker.build(conn, "wales")["divisions"], [])

    def test_the_scorer_never_scores_it(self):
        conn = store()
        member(conn, "p/1", "A Member")
        conn.execute("INSERT INTO sd_votes (division_key, member_id, member_name, "
                     "result) VALUES ('D1', '1', 'A Member', 'Against')")
        conn.commit()
        score.load = lambda nation: [{"key": "D1", "not_ours": True,
                                      "our_side": "against", "signed_off": True}]
        score.score(conn, "wales", apply_it=True, log=lambda *a: None)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM sd_scored").fetchone()[0], 0)

    def test_the_collector_clears_the_areas_the_title_would_give(self):
        src = open(os.path.join(ROOT, "tools", "sd_divisions.py"), encoding="utf-8").read()
        self.assertIn("def not_ours_keys", src)
        self.assertIn("if str(d.key) in struck:", src)
        body = src[src.index("if str(d.key) in struck:"):]
        self.assertIn("areas = []", body[:200])

    def test_the_live_config_strikes_the_crime_and_policing_lcm(self):
        import yaml
        cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "senedd_votes.yaml"), encoding="utf-8"))
        by = {d["key"]: d for d in cfg["divisions"]}
        self.assertTrue(by["757579"].get("not_ours"))
        self.assertFalse(by["757579"].get("signed_off"))
        two = by["759759"]
        self.assertTrue(two["signed_off"]); self.assertEqual(two["our_side"], "against")
        for k in ("meaning_good", "meaning_bad"):
            self.assertIn("children-not-in-school register", two[k])
            self.assertNotRegex(two[k], r"(?i)because|motive|competence",
                                "the sentence describes the act, never the motive")


class NorthernIrelandTests(unittest.TestCase):
    """Christopher, 2026-09-06: two NI divisions signed, one deliberately
    unsigned, four struck; and former MLAs listed from the vote record."""

    def test_the_live_config(self):
        import yaml
        cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "nia_votes.yaml"), encoding="utf-8"))
        by = {d["key"]: d for d in cfg["divisions"]}
        self.assertEqual(len(by), 7)
        for k in ("493329", "456935"):
            self.assertTrue(by[k]["signed_off"]); self.assertEqual(by[k]["our_side"], "for")
            for s in ("meaning_good", "meaning_bad"):
                self.assertNotRegex(by[k][s], r"(?i)because|motive|competence")
        self.assertFalse(by["488823"]["signed_off"], "blasphemy stays unsigned by decision")
        self.assertIsNone(by["488823"]["our_side"])
        self.assertEqual(sorted(k for k, v in by.items() if v.get("not_ours")),
                         ["448609", "449970", "449976", "475390"])

    def test_the_classifier_honours_the_strike(self):
        """ni_classify is the only writer of ni_divisions.areas and re-derives
        them weekly, so the strike must live there or return on Thursday."""
        src = open(os.path.join(ROOT, "tools", "ni_classify.py"), encoding="utf-8").read()
        self.assertIn("def not_ours_keys", src)
        self.assertIn('if str(row["doc_id"]) in struck:', src)
        body = src[src.index('if str(row["doc_id"]) in struck:'):]
        self.assertIn("areas = []", body[:200])

    def test_a_former_mla_is_listed_from_the_vote_record(self):
        """The NI roster is current-only. William Irwin and Gary Middleton
        (DUP) voted on Amendment 5 and vanished from the page without a
        word; they are now listed from the Assembly's own vote record."""
        conn = store()
        conn.execute("INSERT INTO ni_members (person_id, name, display_name, party, "
                     "constituency, first_seen, last_seen) VALUES ('m/1', 'Sitting', "
                     "'Ms Sitting', 'Alliance Party', 'North Down', '2026-01-01', '2026-01-01')")
        conn.execute("INSERT INTO ni_divisions (doc_id, dated, subject, areas, first_seen, "
                     "last_seen) VALUES ('X1', '2025-11-04', 'Amendment 5', '[1]', "
                     "'2026-01-01', '2026-01-01')")
        for pid, nm, des in (("m/1", "Ms Sitting", "Other"), ("201", "Mr William Irwin", "Unionist")):
            conn.execute("INSERT INTO ni_votes (doc_id, person_id, member, vote, designation, "
                         "captured_at) VALUES ('X1', ?, ?, 'aye', ?, '2026-01-01')", (pid, nm, des))
        conn.commit()
        tracker.load_config = lambda spec: {}
        data = tracker.build(conn, "ni")
        by = {m["name"]: m for m in data["members"]}
        self.assertIn("Mr William Irwin", by)
        self.assertTrue(by["Mr William Irwin"]["former"])
        self.assertEqual(by["Mr William Irwin"]["party"], "Unionist (designation)")
        self.assertEqual(data["votes"]["201"]["X1"]["vote"], "aye")
        self.assertEqual(data["former_from_votes"], ["Mr William Irwin"])


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


class RosterNameTests(unittest.TestCase):
    """Every politician must be findable under the name they vote as.

    parlparse stores a peer's surname in `lordname`, so the First
    Minister sat in the Welsh roster as "Mair Eluned" and matched no
    vote she ever cast; and the chamber and the roster disagree about
    middle names ("Benjamin Hodge Mckenna" / "Benjamin McKenna").
    """

    def test_a_peers_surname_is_not_dropped(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "sd_members", os.path.join(ROOT, "tools", "sd_members.py"))
        mod = iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        peer = {"other_names": [{"note": "Main", "given_name": "Mair Eluned",
                                 "honorific_prefix": "Baroness",
                                 "lordname": "Morgan"}]}
        self.assertEqual(mod.person_name(peer), "Mair Eluned Morgan")
        names = [n for n, _kind in mod.person_aliases(peer)]
        self.assertIn("Eluned Morgan", names,
                      "the name she votes under must be recorded")

    def test_a_longer_or_shorter_form_of_one_name_resolves(self):
        from src import devolved as dv
        index = {"benjamin mckenna": "p/1", "mair eluned morgan": "p/2"}
        got, missing = dv.resolve(
            ["Benjamin Hodge Mckenna", "Eluned Morgan"], index)
        self.assertEqual(missing, [])
        self.assertEqual(got["Benjamin Hodge Mckenna"], "p/1")
        self.assertEqual(got["Eluned Morgan"], "p/2")

    def test_an_ambiguous_name_is_refused_not_guessed(self):
        """The cost of a wrong match is a vote attributed to a politician
        who did not cast it, so two candidates means unresolved."""
        from src import devolved as dv
        index = {"david davies": "p/1", "david john davies": "p/2"}
        got, missing = dv.resolve(["Davies"], index)
        self.assertEqual((got, missing), ({}, ["Davies"]))
        got, missing = dv.resolve(["David Davies"], index)
        self.assertEqual(got, {"David Davies": "p/1"},
                         "an EXACT name still wins outright")

    def test_a_different_surname_never_matches(self):
        from src import devolved as dv
        index = {"jane jones": "p/1"}
        got, missing = dv.resolve(["Jane Smith"], index)
        self.assertEqual((got, missing), ({}, ["Jane Smith"]))


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
