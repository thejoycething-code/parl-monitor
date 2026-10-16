"""Chris, 16 October 2026. Fixtures only, in-memory stores.

1. Germany's edition (tools/de_monitor.py) in the countdown layout of the
   fifteen country editions (src/country_countdown.py), reading the shared
   agenda table (country_agenda, src/agendas/de.py) for sitting days, with
   its own sections kept under Reference, "Recorded votes" among them.
2. The UK countdown gets "Recorded votes" back (src/countdown.py,
   src/digest.py), holding ONLY last week's divisions (Mon-Sun before the
   edition), Westminster and devolved, grouped by debate, with a single
   line when there were none; under Reference straight after the board.
"""

import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import agenda, countdown as cd, db, digest  # noqa: E402


def _load_de():
    spec = importlib.util.spec_from_file_location("de_monitor_cd", os.path.join(ROOT, "tools", "de_monitor.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dm = _load_de()


def store():
    conn = db.init_db(db.connect(":memory:"))
    agenda.ensure_schema(conn)
    return conn


# --- the UK: Recorded votes, last week only -----------------------------------------

WEEK = "2026-09-14"          # the window is Mon 7 to Sun 13 September


def uk_store():
    conn = store()
    conn.executemany("INSERT INTO cv_divisions (division_id, date, title, ayes, noes) VALUES (?,?,?,?,?)",
                     [(2421, "2026-09-08", "Health Bill: Report Stage: New Clause 142", 108, 357),
                      (2422, "2026-09-08", "Health Bill: Report Stage: New Clause 143", 106, 302),
                      (2428, "2026-09-11", "Terminally Ill Adults (End of Life) Bill: Second Reading", 270, 286),
                      (2399, "2026-09-02", "An earlier vote outside the window", 300, 10)])
    # The ledger holds 2422's voters on our ground (area 5).
    conn.executemany("INSERT INTO mp_events (member_id, date, kind, ref, line, areas) VALUES (?,?,?,?,?,?)",
                     [("m1", "2026-09-08", "vote", "div:c2422:aye",
                       "Voted Aye: Health Bill: Report Stage: New Clause 143", "[5]"),
                      ("l1", "2026-09-09", "vote", "div:l3001:aye",
                       "Voted Content: Children's Wellbeing and Schools Bill: Amendment 12", "[6]"),
                      ("l2", "2026-09-09", "vote", "div:l3001:no",
                       "Voted Not Content: Children's Wellbeing and Schools Bill: Amendment 12", "[6]"),
                      ("l3", "2026-09-09", "vote", "div:l3001:no",
                       "Voted Not Content: Children's Wellbeing and Schools Bill: Amendment 12", "[6]"),
                      ("m2", "2026-09-10", "vote", "div:c2500:aye", "Voted Aye: Migration only", "[11]")])
    # The sweep's division items: a title match, and a tier-2 hit nobody judged.
    conn.executemany(
        "INSERT INTO items (id, captured_at, source_feed, item_type, title, url, event_date, issue_areas, "
        "tier, triage_score) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [("division:2428", "x", "division", "division",
          "Division #75 (270-286): Terminally Ill Adults (End of Life) Bill: Second Reading",
          "https://votes.parliament.uk/Votes/Commons/Division/2428", "2026-09-11", "[2]", 1, 3),
         ("division:2430", "x", "division", "division", "Division #77 (200-100): A loose tier-2 hit",
          "https://votes.parliament.uk/Votes/Commons/Division/2430", "2026-09-10", "[7]", 2, None)])
    conn.executemany(
        "INSERT INTO sd_divisions (key, meeting_id, dated, title, total_for, total_against, total_abstain, "
        "result, areas, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,'x','x')",
        [(1, 16261, "2026-09-09", "Item 5. Reform UK Debate - grooming gangs. Motion without amendment.",
          37, 47, 0, "Motion has been rejected", "[6]", 1),
         (2, 16261, "2026-09-09", "Item 5. Reform UK Debate - grooming gangs. Amendment 1, tabled in the "
          "name of Heledd Fychan.", 47, 37, 0, "Amendment has been agreed", "[6]", 1)])
    conn.executemany(
        "INSERT INTO sp_divisions (key, reference, title, dated, vote_for, vote_against, abstentions, result, "
        "areas, tier, source, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,'votesmotion','x','x')",
        [("m1", "S7M-01163.2", "Preventing Violence Against Women", "2026-09-10", 17, 102, 0, "Defeated",
          "[5]", 1),
         ("m2", "S7M-01170", "A tier-2 Holyrood hit", "2026-09-10", 60, 50, 0, "Carried", "[7]", 2)])
    conn.commit()
    return conn


TRACKER = [{"id": 2421, "date": "2026-09-08", "title": "Health Bill: Report Stage: New Clause 142",
            "ayes": 108, "noes": 357, "url": "https://votes.parliament.uk/Votes/Commons/Division/2421"},
           {"id": 2399, "date": "2026-09-02", "title": "An earlier vote outside the window", "ayes": 300,
            "noes": 10, "url": "https://votes.parliament.uk/Votes/Commons/Division/2399"}]


class UKRecordedVotes(unittest.TestCase):
    def test_window_is_the_week_before(self):
        start, end = cd.votes_window(WEEK)
        self.assertEqual((start.isoformat(), end.isoformat()), ("2026-09-07", "2026-09-13"))

    def test_grouped_by_debate_with_results_tallies_and_links(self):
        md = cd.render_recorded_votes(cd.recorded_votes(uk_store(), WEEK, TRACKER), WEEK)
        lines = [ln for ln in md.splitlines() if ln.startswith("- ")]
        self.assertEqual(lines[0],
                         "- Tue 8 Sep · **Commons** · Health Bill: Report Stage: "
                         "[New Clause 142](https://votes.parliament.uk/Votes/Commons/Division/2421), rejected "
                         "(Ayes 108, Noes 357); [New Clause 143](https://votes.parliament.uk/Votes/Commons/"
                         "Division/2422), rejected (Ayes 106, Noes 302)")
        self.assertIn("**Lords** · Children's Wellbeing and Schools Bill: [Amendment 12]"
                      "(https://votes.parliament.uk/Votes/Lords/Division/3001), rejected "
                      "(Contents 1, Not contents 2)", md)
        self.assertIn("[Item 5. Reform UK Debate - grooming gangs](https://record.senedd.wales/Plenary/16261): "
                      "Motion without amendment, rejected (For 37, Against 47, Abstain 0); Amendment 1, "
                      "tabled in the name of Heledd Fychan, agreed (For 47, Against 37, Abstain 0)", md)
        self.assertIn("**Holyrood** · Preventing Violence Against Women: [amendment S7M-01163.2]"
                      "(https://www.parliament.scot/chamber-and-committees/votes-and-motions/S7M-01163), "
                      "defeated (For 17, Against 102, Abstentions 0)", md)
        self.assertIn("[Terminally Ill Adults (End of Life) Bill: Second Reading]"
                      "(https://votes.parliament.uk/Votes/Commons/Division/2428), rejected (Ayes 270, Noes 286)",
                      md)

    def test_only_last_week_and_only_our_ground(self):
        md = cd.render_recorded_votes(cd.recorded_votes(uk_store(), WEEK, TRACKER), WEEK)
        for gone in ("An earlier vote outside the window", "Migration only", "A loose tier-2 hit",
                     "A tier-2 Holyrood hit"):
            self.assertNotIn(gone, md)
        # The same votes a week later are last week's no longer.
        later = cd.render_recorded_votes(cd.recorded_votes(uk_store(), "2026-09-21", TRACKER), "2026-09-21")
        self.assertEqual(later, "## Recorded votes\n\n" + cd.NO_RECORDED_VOTES + "\n")

    def test_none_is_one_line(self):
        md = cd.render_recorded_votes([], WEEK)
        self.assertEqual(md.splitlines()[2], "No recorded votes on our issues last week.")
        self.assertEqual(len([ln for ln in md.splitlines() if ln.strip()]), 2)

    def test_under_reference_straight_after_the_board(self):
        e = digest.Edition(week_commencing=WEEK, number=7, mode="normal")
        e.recorded_votes = cd.recorded_votes(uk_store(), WEEK, TRACKER)
        md = digest.render(e)
        ref = md[md.index("## Reference"):]
        self.assertLess(ref.index("### Bills we track"), ref.index("### Recorded votes"))
        between = ref[ref.index("### Bills we track"):ref.index("### Recorded votes")]
        self.assertEqual(between.count("\n### "), 0, between)
        self.assertNotIn("Latest votes on our issues", md)
        e.recorded_votes = []
        self.assertIn("### Recorded votes\n\nNo recorded votes on our issues last week.", digest.render(e))

    def test_left_out_when_not_read(self):
        e = digest.Edition(week_commencing=WEEK, number=7, mode="normal")
        self.assertNotIn("Recorded votes", digest.render(e))


# --- Germany: the countdown layout ------------------------------------------------------

TODAY = "2026-10-18"         # a Sunday, as the weekly runs


def de_store():
    conn = store()
    conn.execute("INSERT INTO country_agenda_runs (cc, run_date, items, on_ground, horizon, next_sitting, note) "
                 "VALUES ('de', '2026-10-18', 4, 2, '2026-11-06', '2026-10-21', NULL)")
    pts = [
        ("plenary:21/102:TOP 4", "2026-10-22", "Plenum", "plenary",
         "TOP 4: Beratung der Beschlussempfehlung zum Schwangerschaftskonfliktgesetz", ["21/9001"], [1], 1),
        ("plenary:21/102:TOP 9", "2026-10-21", "Plenum", "plenary", "TOP 9: Haushalt", [], [], None),
        ("cttee:1", "2026-11-04", "Gesundheit", "hearing",
         "Öffentliche Anhörung zur Widerspruchslösung", ["21/9100"], [10], 1),
        ("cttee:2", "2026-10-20", "Recht", "committee", "Sitzung", [], [], None),
    ]
    for pid, date, body, kind, title, refs, areas, tier in pts:
        conn.execute("INSERT INTO country_agenda (cc, item_id, date, time, body, kind, title, refs, url, areas, "
                     "own_areas, tier, first_seen, last_seen) VALUES ('de',?,?,NULL,?,?,?,?,?,?,?,?,?,?)",
                     (pid, date, body, kind, title, json.dumps(refs), "https://www.bundestag.de/x",
                      json.dumps(areas), json.dumps(areas), tier, TODAY, "2026-10-18"))
    # A Vorgang scored 3 whose committee report is Drucksache 21/9001.
    conn.execute("INSERT INTO de_vorgaenge (vorgang_id, wahlperiode, titel, vorgangstyp, initiative, datum, "
                 "stand, areas, tier, triage_score, why_it_matters, first_seen, last_seen) VALUES "
                 "('500','21','Gesetz zur Änderung des Schwangerschaftskonfliktgesetzes','Gesetzgebung',"
                 "'Bundesregierung','2026-09-30','Beschlussempfehlung liegt vor','[1]',1,3,"
                 "'Would change counselling before an abortion.',?,?)", (TODAY, TODAY))
    conn.execute("INSERT INTO de_vorgaenge (vorgang_id, wahlperiode, titel, vorgangstyp, initiative, datum, "
                 "stand, areas, tier, triage_score, why_it_matters, first_seen, last_seen) VALUES "
                 "('501','21','Pubertätsblocker bei Minderjährigen','Kleine Anfrage','Fraktion der AfD',"
                 "'2026-10-09','Beantwortet','[3]',1,2,'Asks how many minors were prescribed blockers.',?,?)",
                 (TODAY, TODAY))
    conn.execute("INSERT INTO de_committee_reports (doc_id, kind, datum, titel, vorgang_id, parent_drucksachen, "
                 "areas, first_seen, last_seen) VALUES ('drucksache:21/9001','committee report','2026-10-10',"
                 "'Beschlussempfehlung','500','[\"21/8000\"]','[1]',?,?)", (TODAY, TODAY))
    conn.execute("INSERT INTO de_petitions (petition_id, title, closes, signatures, url, areas, tier, "
                 "first_seen, last_seen) VALUES ('p1','Lebensschutz stärken','2026-10-24',1200,"
                 "'https://epetitionen.bundestag.de/p1','[1]',1,?,?)", (TODAY, TODAY))
    conn.execute("INSERT INTO de_divisions (vote_id, parliament, parliament_label, legislature, date, label, yes, "
                 "no, abstain, absent, accepted, areas, tier, document_url, triage_score, first_seen, last_seen) "
                 "VALUES ('v1','5','Bundestag','161','2026-10-08','Monitoring des NIPT',527,18,23,62,1,'[1]',1,"
                 "'https://dserver.bundestag.de/btd/21/090/2109001.pdf',3,?,?)", (TODAY, TODAY))
    conn.commit()
    return conn


class GermanCountdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = de_store()
        cls.md = dm.render_edition(cls.conn, TODAY, write=False)

    def test_drucksache_from_a_paper_address(self):
        self.assertEqual(dm.drucksache_of("https://dserver.bundestag.de/btd/21/038/2103873.pdf"), "21/3873")
        self.assertIsNone(dm.drucksache_of("https://www.abgeordnetenwatch.de/x"))

    def test_the_country_editions_order(self):
        heads = [ln for ln in self.md.splitlines() if ln.startswith("## ")]
        order = ["## Big dates", "## This week", "## Further afield", "## Key questions",
                 "## Petitions", "## Decisions needed", "## Reference"]
        got = [next(i for i, h in enumerate(heads) if h.startswith(o)) for o in order if
               any(h.startswith(o) for h in heads)]
        self.assertEqual(got, sorted(got), heads)
        for o in ("## Big dates", "## This week", "## Further afield", "## Key questions", "## Petitions",
                  "## Reference"):
            self.assertTrue(any(h.startswith(o) for h in heads), o)
        self.assertNotIn("## Week ahead", self.md)
        self.assertNotIn("### Week ahead", self.md)
        self.assertLess(self.md.index("*Sitting this week:*"), self.md.index("## This week"))

    def test_sitting_days_from_the_shared_agenda(self):
        line = next(ln for ln in self.md.splitlines() if ln.startswith("*Sitting this week:*"))
        self.assertIn("Bundestag sitting (plenary Wed 21 and Thu 22 Oct)", line)
        self.assertNotIn("Bundesrat", line)
        self.assertIn("no published calendar read for the Bundesrat", self.md)

    def test_big_date_takes_its_vorgang_score_and_last_vote(self):
        big = self.md[self.md.index("## Big dates"):self.md.index("## This week")]
        self.assertIn("Schwangerschaftskonfliktgesetz", big)
        self.assertIn("the last recorded vote on this was on 8 October", big)

    def test_tables_rows_and_tags(self):
        week = self.md[self.md.index("## This week"):self.md.index("## Further afield")]
        self.assertIn("| BUNDESTAG |", week)
        self.assertIn("| DEADLINE |", week)          # the petition closes inside the week
        self.assertIn("Lebensschutz stärken", week)
        self.assertNotIn("TOP 9: Haushalt", self.md)   # not on our ground
        further = self.md[self.md.index("## Further afield"):self.md.index("## Key questions")]
        self.assertIn("Öffentliche Anhörung zur Widerspruchslösung", further)

    def test_key_questions_are_anfragen(self):
        kq = self.md[self.md.index("## Key questions"):self.md.index("## Petitions")]
        self.assertIn("Pubertätsblocker bei Minderjährigen", kq)
        self.assertIn("Fraktion der AfD", kq)

    def test_reference_keeps_every_section_and_recorded_votes(self):
        ref = self.md[self.md.index("## Reference"):]
        for h in ("### Active bills board", "### Top lines", "### Recorded votes · Bundestag",
                  "### The Länder", "### Coming up", "### Watching", "### Coverage notes"):
            self.assertIn(h, ref)
        self.assertLess(ref.index("### Active bills board"), ref.index("### Recorded votes"))
        # The board's Next comes from the countdown's rows.
        board = ref[ref.index("### Active bills board"):ref.index("### Top lines")]
        self.assertIn("| BUNDESTAG | Thu 22 Oct, plenary |", board)
        self.assertNotIn("## Coming up", self.md.replace("### Coming up", ""))

    def test_honesty_note_and_no_verdict_survive(self):
        self.assertIn(dm.HONESTY, self.md)
        self.assertIn(dm.NO_VERDICT, self.md)
        self.assertNotIn("—", self.md)

    def test_dm_carries_the_countdown(self):
        text = dm.dm_summary(self.conn, TODAY)
        self.assertIn("_Sitting this week: Bundestag sitting", text)
        self.assertIn("*BIG DATE*", text)
        self.assertIn("*This week*:", text)


class NoUKVotesInTheGermanEdition(unittest.TestCase):
    """Chris, 16 October 2026: the German edition's Recorded votes are German
    only (Bundestag, Bundesrat, Landtage). The UK's last-week Recorded votes
    (src/countdown.recorded_votes) belong to the UK edition alone, so a
    store holding both must never put a Westminster or devolved division
    into the German edition or its DM."""

    UK_TITLES = ("Health Bill: Report Stage", "Terminally Ill Adults", "Children's Wellbeing",
                 "Reform UK Debate - grooming gangs", "Preventing Violence Against Women")

    def test_a_shared_store_keeps_uk_divisions_out(self):
        conn = uk_store()                     # every UK division source filled
        for stmt in de_store().iterdump():    # and the German store beside it
            if stmt.startswith("INSERT INTO \"de_") or stmt.startswith("INSERT INTO \"country_agenda"):
                conn.execute(stmt)
        conn.commit()
        md = dm.render_edition(conn, TODAY, write=False)
        text = md + dm.dm_summary(conn, TODAY)
        for t in self.UK_TITLES:
            self.assertNotIn(t, text)
        for where in ("**Commons**", "**Lords**", "**Holyrood**", "**Senedd**", "**NI Assembly**",
                      "votes.parliament.uk", "parliament.scot", "record.senedd.wales", "niassembly"):
            self.assertNotIn(where, text)
        self.assertNotIn(cd.NO_RECORDED_VOTES, text)
        votes = md[md.index("### Recorded votes"):]
        self.assertTrue(votes.startswith("### Recorded votes · Bundestag"))
        self.assertIn("Monitoring des NIPT", votes)

    def test_the_german_renderer_never_calls_the_uk_section(self):
        with open(os.path.join(ROOT, "tools", "de_monitor.py"), encoding="utf-8") as fh:
            src = fh.read()
        for name in ("recorded_votes(", "westminster_votes", "devolved_votes", "render_recorded_votes"):
            self.assertNotIn(name, src)


if __name__ == "__main__":
    unittest.main()
