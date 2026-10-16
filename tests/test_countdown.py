"""The countdown (Christopher, 15 October 2026, "A · Countdown"): one timeline
across Westminster and the devolved bodies, big dates at the top, This week
then Further afield, Reference below. Fixtures only; no network."""

import datetime
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import board, countdown as cd, db, digest  # noqa: E402

WEEK = "2026-10-19"


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


def event(date, desc, score=2, house="Lords", venue="Main Chamber", category="Short debate",
          event_id=1, members=None, areas=(3,), bill_id=None, why="A why-line."):
    ev = {"event_id": event_id, "house": house, "type": venue, "category": category,
          "description": desc, "members": members or [], "bill_id": bill_id,
          "title": "after other business, {0} {1}. {2}".format(house, category, desc)}
    return digest.Line(why, score, url="https://whatson.parliament.uk/event/cal{0}".format(event_id),
                       date=date, event=ev, areas=list(areas))


class DatesTests(unittest.TestCase):
    def test_one_date_format(self):
        self.assertEqual(cd.day_label("2026-10-22"), "Thu 22 Oct")
        self.assertEqual(cd.long_day("2026-10-22"), "Thursday 22 October")
        self.assertEqual(cd.short_day("2026-10-22"), "Thu 22")
        self.assertEqual(cd.day_label(None), "Not yet dated")

    def test_windows_this_week_then_eight_weeks(self):
        ws, we, fs, he = cd.windows(WEEK)
        self.assertEqual([d.isoformat() for d in (ws, we, fs, he)],
                         ["2026-10-19", "2026-10-25", "2026-10-26", "2026-12-20"])


class RowTests(unittest.TestCase):
    def test_whatson_row_tags_and_cells(self):
        r = cd.from_whatson(event("2026-10-22", "Puberty blockers and cross-sex hormones",
                                  score=3, members=["Baroness Deech"]))
        self.assertEqual((r.where, r.lead, r.detail, r.score), ("LORDS", "Baroness Deech", "short debate", 3))
        self.assertEqual(cd.house_tag("Commons", "Westminster Hall"), "COMMONS")
        self.assertEqual(cd.house_tag("Lords", "Grand Committee"), "LORDS")
        r.big = True
        self.assertEqual(cd.when_cell(r), "**Thu 22 Oct · BIG DATE**")
        self.assertTrue(cd.what_cell(r).startswith(
            "**[Puberty blockers and cross-sex hormones](https://whatson.parliament.uk/event/cal1)**"))

    def test_a_low_score_why_line_is_not_printed(self):
        r = cd.Row(date="2026-11-19", where="NI GOVT", title="Phone-free schools", score=1,
                   note="No connection to any monitored campaign area.")
        self.assertNotIn("No connection", cd.what_cell(r))

    def test_big_dates_are_score_three_at_most_three_nearest_first(self):
        rows = [cd.Row(date=d, where="LORDS", title="t" + d, score=s) for d, s in (
            ("2026-11-02", 3), ("2026-10-20", 3), ("2026-10-21", 2), ("2026-10-30", 3),
            ("2026-10-28", 3), ("2027-03-01", 3))]
        big = cd.mark_big(rows, WEEK)
        self.assertEqual([r.date for r in big], ["2026-10-20", "2026-10-28", "2026-10-30"])
        self.assertEqual(sum(r.big for r in rows), 3)

    def test_sittings_fold_into_the_first(self):
        rows = [cd.from_whatson(event(d, "Health Bill - committee stage (day {0})".format(i + 1),
                                      category="Legislation", event_id=i, bill_id=4124))
                for i, d in enumerate(("2026-10-28", "2026-11-03", "2026-11-09"))]
        out = cd.fold_sittings(rows, WEEK)
        self.assertEqual(len(out), 1)
        self.assertIn("then Tue 3 Nov, Mon 9 Nov", cd.what_cell(out[0]))

    def test_committee_sittings_this_week_give_way_to_the_all_week_row(self):
        pbc = cd.from_whatson(event("2026-10-20", None, house="Commons", venue="General Committee",
                                    category="Debate"))
        pbc.title = "Immigration and Asylum Bill"
        running = cd.Row(where="COMMONS", title="Immigration and Asylum Bill", running=True,
                         extra_md="[Immigration and Asylum Bill](u), in committee")
        out = cd.fold_sittings([pbc, running], WEEK)
        self.assertEqual(out, [running])

    def test_slack_title_puts_the_bill_first(self):
        r = cd.Row(title="Extension of Committee Stage: Conversion Practices (Criminalisation) Bill "
                         "(NIA Bill 45/22-27)")
        self.assertEqual(cd.short_title(r),
                         "Conversion Practices (Criminalisation) Bill: extension of committee stage")


class StoreReadTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        c = self.conn
        c.execute("INSERT INTO ni_items (id, kind, title, dated, category, areas, first_seen, last_seen) "
                  "VALUES ('ni-plenary:1', 'plenary', 'Extension of Committee Stage: Conversion Practices "
                  "(Criminalisation) Bill (NIA Bill 45/22-27)', '2026-10-19', 'Motion', '[4]', 'x', 'x')")
        c.execute("INSERT INTO ni_items (id, kind, title, dated, category, areas, first_seen, last_seen) "
                  "VALUES ('ni-plenary:2', 'plenary', 'Cost of Living Crisis', '2026-10-19', 'Motion', '[]', 'x', 'x')")
        c.execute("INSERT INTO ni_agenda (event_id, item_order, committee, business, item_type, session, "
                  "dated, areas, first_seen, last_seen) VALUES ('19848', 1, 'Committee for Communities', "
                  "'Conversion Practices (Criminalisation) Bill: Oral evidence from RaISe', "
                  "'Non Departmental Evidence', 'Public, 10:00 AM - 11:00 AM', '2026-10-15', '[4]', 'x', 'x')")
        c.execute("INSERT INTO dg_consultations (key, nation, title, url, closes, areas, first_seen, last_seen) "
                  "VALUES ('ni:/x', 'ni', 'Phone-free schools', 'https://c/1', '2026-11-19', '[6]', 'x', 'x')")
        c.execute("INSERT INTO dg_consultations (key, nation, title, url, closes, areas, first_seen, last_seen) "
                  "VALUES ('wales:/y', 'wales', 'Migration only', 'https://c/2', '2026-11-19', '[11]', 'x', 'x')")
        c.commit()
        self.ws, self.we, self.fs, self.he = cd.windows(WEEK)

    def test_ni_order_paper_on_our_ground_only(self):
        rows = cd.ni_rows(self.conn, self.ws, self.he)
        self.assertEqual([(r.where, r.date) for r in rows], [("NI ASSEMBLY", "2026-10-19")])

    def test_ni_bill_in_committee_runs_all_week(self):
        got = cd.ni_running(self.conn, self.ws, self.he)
        self.assertEqual(got, [("Conversion Practices (Criminalisation) Bill", "Committee for Communities", [4])])

    def test_devolved_consultations_carry_their_government_and_hide_migration(self):
        rows = cd.devolved_consultations(self.conn, self.ws, self.he)
        self.assertEqual([(r.where, r.title) for r in rows], [("NI GOVT", "Phone-free schools")])

    def test_holyrood_and_senedd_not_collected_line(self):
        rows, note = cd.forward_business(self.conn, self.ws, self.he)
        self.assertEqual((rows, note), ([], "Holyrood and Senedd: forward business not collected yet."))

    def test_holyrood_and_senedd_read_when_the_tables_exist(self):
        self._agenda("sp_agenda", "2026-10-21", "Chamber", "Assisted dying debate", "members' business", "[2]")
        self._agenda("sd_agenda", "2026-10-22", "Welsh Government", "Statement on RSE", "statement", "[6]")
        self._agenda("sp_agenda", "2026-10-22", "Chamber", "Government business", "to be announced", "[6]")
        rows, note = cd.forward_business(self.conn, self.ws, self.he)
        self.assertIsNone(note)
        self.assertEqual([(r.where, r.title) for r in rows],
                         [("HOLYROOD", "Assisted dying debate"), ("WELSH GOVT", "Statement on RSE")])

    def _agenda(self, table, dated, body, business, item_type, areas):
        self.conn.execute("INSERT INTO {0} (key, dated, item_time, body, business, item_type, url, areas, "
                          "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)".format(table),
                          (table + dated + business, dated, "14:00", body, business, item_type,
                           "https://x/" + table, areas, "x", "x"))

    def test_one_table_missing_names_it(self):
        self._agenda("sp_agenda", "2026-10-21", "Chamber", "Procedural", "procedural", "[]")
        _rows, note = cd.forward_business(self.conn, self.ws, self.he)
        self.assertEqual(note, "Senedd: forward business not collected yet.")


class ContextTests(unittest.TestCase):
    TRACKER = [{"id": 2422, "date": "2026-09-08", "title": "Health Bill: Report Stage: New Clause 143",
                "ayes": 106, "noes": 302, "area": 5, "issue": "Single-sex NHS facilities",
                "short": "New Clause 143", "bill": "Health Bill",
                "url": "https://votes.parliament.uk/Votes/Commons/Division/2422"},
               {"id": 2421, "date": "2026-09-08", "title": "Health Bill: Report Stage: New Clause 142",
                "ayes": 108, "noes": 357, "area": 3, "issue": "Puberty blockers for under-18s",
                "short": "New Clause 142", "bill": "Health Bill",
                "url": "https://votes.parliament.uk/Votes/Commons/Division/2421"}]

    def test_a_bill_row_cites_its_own_commons_votes(self):
        r = cd.Row(date="2026-10-28", where="LORDS", title="Health Bill - committee stage (day 1)",
                   bill_id=4124, areas=[3, 5])
        ctx = cd.context_for(r, self.TRACKER, {"Health Bill": 4124}, 2026)
        self.assertIn("[New Clause 142](https://votes.parliament.uk/Votes/Commons/Division/2421) "
                      "(puberty blockers for under-18s, rejected 108 to 357)", ctx)
        self.assertIn("New Clause 143", ctx)
        self.assertIn("8 September", ctx)

    def test_an_issue_row_cites_the_last_vote_on_the_issue(self):
        r = cd.Row(date="2026-10-22", where="LORDS", title="Age of consent to puberty blockers", areas=[3])
        self.assertEqual(cd.context_for(r, self.TRACKER, {}, 2026),
                         "the last Commons vote on this issue was [Health Bill: Report Stage: New Clause 142]"
                         "(https://votes.parliament.uk/Votes/Commons/Division/2421), rejected 108 to 357 "
                         "on 8 September.")

    def test_no_vote_falls_back_to_the_why_line(self):
        r = cd.Row(date="2026-10-22", where="LORDS", title="x", areas=[9], note="Why it matters.")
        self.assertEqual(cd.context_for(r, self.TRACKER, {}, 2026), "Why it matters.")

    def test_tracker_loads_signed_off_commons_votes_only(self):
        conn = store()
        conn.execute("INSERT INTO cv_divisions VALUES (2421, '2026-09-08', 'Health Bill: NC142', 108, 357)")
        conn.execute("INSERT INTO cv_divisions VALUES (9, '2026-09-09', 'Unsigned', 1, 2)")
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("hidden_areas: [11]\nissues:\n  - {id: gm, area: 3, name: Puberty blockers, "
                    "bill: Health Bill - New Clause 142}\ndivisions:\n  - {id: 2421, issue: gm, "
                    "signed_off: true, short: New Clause 142}\n  - {id: 9, issue: gm, signed_off: false}\n")
        try:
            got = cd.load_tracker(conn, f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual([(v["id"], v["bill"], v["area"]) for v in got], [(2421, "Health Bill", 3)])


class RenderTests(unittest.TestCase):
    def _edition(self):
        e = digest.Edition(week_commencing=WEEK, number=10, mode="normal")
        e.board_rows = [board.BoardRow(4124, "Health Bill", "s", "Lords", "Committee stage", "2026-10-28",
                                       "live", board.NEW, areas="3,5", why="Carried NC142 and NC143")]
        e.week_ahead = [event("2026-10-22", "Puberty blockers debate", score=3, event_id=56747,
                              members=["Baroness Deech"])]
        e.further_ahead = [event("2026-10-28", "Health Bill - committee stage (day 1)", score=3,
                                 category="Legislation", event_id=56696, bill_id=4124,
                                 members=["Baroness Merron"], areas=(3, 5))]
        e.deadlines = [{"type": "Evidence", "title": "Work-based immigration", "url": "https://c/e",
                        "why": "Home Affairs Committee", "committee": "Home Affairs Committee",
                        "deadline": "2026-10-27", "areas": [11], "score": 2},
                       {"type": "Consultation", "title": "A rolling one", "url": "https://c/r",
                        "why": "", "deadline": None, "areas": [6], "score": 2}]
        return e

    def test_layout_order_and_markers(self):
        md = digest.render(self._edition())
        order = ["### Edition 10 · Monday 19 October 2026", "## Big dates", "## This week · Mon 19 to Sun 25 October",
                 "## Further afield · Mon 26 October to 20 December", "## Reference",
                 "### Bills we track, all legislatures", "### Coverage notes"]
        self.assertEqual([md.index(h) for h in order], sorted(md.index(h) for h in order))
        self.assertEqual(md.count("> **BIG DATE** · "), 2)
        self.assertIn("> **BIG DATE** · **Thursday 22 October** · LORDS · Gender medicine (children)", md)
        self.assertIn("| **Wed 28 Oct · BIG DATE** | LORDS |", md)
        self.assertIn("| Tue 27 Oct | DEADLINE | Home Affairs Committee, [Work-based immigration](https://c/e), "
                      "evidence closes | Migration |", md)
        # The rolling consultation is not in a table, so it keeps its place in Reference.
        self.assertIn("### Consultations and calls for evidence, later or rolling", md)
        self.assertIn("| [Health Bill](https://bills.parliament.uk/bills/4124) | Westminster | "
                      "Lords, Committee stage | Wed 28 Oct |", md)
        for banned in ("★", "—", "## Top lines", "## Scotland, Wales and Northern Ireland"):
            self.assertNotIn(banned, md)

    def test_slack_post_under_limits(self):
        e = self._edition()
        e.timeline = cd.timeline_for(e)
        for i in range(40):
            e.timeline.append(cd.Row(date="2026-11-{0:02d}".format(1 + i % 28), where="COMMONS",
                                     title="Item {0} ".format(i) * 8, score=2, areas=[1]))
        post = cd.slack_post(e, "https://canvas", "https://tracker")
        self.assertLess(len(post), 4000)
        self.assertTrue(post.endswith("<https://canvas|Open the edition> · <https://tracker|Vote tracker>"))
        self.assertIn("+ ", post)
        self.assertIn(" more to 20 Dec: ", post)


class WhatsOnRefreshTests(unittest.TestCase):
    """The Monday re-read (2026-10-15): the render reads What's On again and
    scores only the What's On items it added."""

    def test_refresh_stores_new_events_and_scores_nothing(self):
        import run_weekly
        from src import filter as filt
        from src.ingest import whatson
        conn = store()
        conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title) "
                     "VALUES ('pq:1', 'x', 'pq', 'pq', 'Pending question')")
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        payload = [{"Id": 56696, "StartDate": "2026-10-28T00:00:00", "House": "Lords",
                    "Type": "Main Chamber", "Category": "Legislation",
                    "Description": "Health Bill - committee stage (day 1)", "BillId": 4124,
                    "Members": []},
                   {"Id": 56697, "StartDate": "2026-10-28T00:00:00", "House": "Lords",
                    "Type": "Main Chamber", "Category": "Legislation",
                    "Description": "Railways Bill - committee stage", "BillId": 4001, "Members": []}]
        events = [whatson.parse_event(r) for r in payload]
        with mock.patch.object(run_weekly.whatson, "fetch_events",
                               side_effect=[[], events]), \
                mock.patch.dict(os.environ, {"TRIAGE": "live", "ANTHROPIC_API_KEY": "sk-test"}), \
                mock.patch.object(run_weekly.triage, "score_live",
                                  side_effect=AssertionError("the paid judge must never run here")):
            seen = run_weekly.refresh_whatson(None, conn, tax, wl, datetime.date(2026, 10, 19),
                                              datetime.date(2026, 10, 25), log=lambda *_: None)
        self.assertEqual(seen, {56696, 56697})
        rows = conn.execute("SELECT id, triage_score, issue_areas FROM items WHERE id LIKE 'whatson:%'").fetchall()
        self.assertEqual([r["id"] for r in rows], ["whatson:2026-10-28:56696"])   # by BillId
        self.assertIsNone(rows[0]["triage_score"])          # no model: left for the session judge
        self.assertEqual(json.loads(rows[0]["issue_areas"]), [3, 5])
        self.assertIsNone(conn.execute("SELECT triage_score FROM items WHERE id = 'pq:1'").fetchone()[0])

    def test_failed_reread_is_a_gap_not_a_lost_edition(self):
        import run_weekly
        conn = store()
        with mock.patch.object(run_weekly.whatson, "fetch_events", side_effect=RuntimeError("down")):
            seen = run_weekly.refresh_whatson(None, conn, None, None, datetime.date(2026, 10, 19),
                                              datetime.date(2026, 10, 25), log=lambda *_: None)
        self.assertIsNone(seen)
        self.assertIn("Monday re-read failed", conn.execute("SELECT detail FROM gaps").fetchone()[0])

    def test_render_reads_whats_on_before_the_sections(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        body = src[src.index("def render_edition("):]
        self.assertLess(body.index("refresh_whatson("), body.index("sections_from_store(conn, edition)"))


class HealthBillTests(unittest.TestCase):
    def test_watched_with_its_why_line(self):
        from src import filter as filt
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        spec = wl.bills_raw[4124]
        self.assertEqual(spec["title"], "Health Bill")
        for phrase in ("NC142", "NC143", "28 Oct 2026"):
            self.assertIn(phrase, spec["why"])
        # match_title false: its name is not a matching entity, so an NHS
        # division or question naming it never reaches the ledger as gender
        # medicine (the clause-text reader handles NC142/NC143).
        r = filt.filter_item(filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml")), wl,
                             "Health Bill: Report Stage: Amendment 12")
        self.assertFalse(r.matched())

    def test_debate_watch_covers_its_lords_stages(self):
        import yaml
        with open(os.path.join(ROOT, "config", "debate_watch.yaml"), encoding="utf-8") as f:
            watches = yaml.safe_load(f)["watches"]
        lords = [w for w in watches if w.get("bill") == 4124 and w.get("house") == "Lords"]
        self.assertTrue(any(w["date"] == "2026-10-28" for w in lords))

    def test_first_read_of_a_new_bill_keeps_decided_amendments_out_of_the_edition(self):
        import run_weekly
        from src import filter as filt
        from src.ingest import amendments
        conn = store()
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        wl.bills_raw = {4124: wl.bills_raw[4124]}
        mk = lambda aid, decision, stage: mock.Mock(
            amendment_id=aid, stage_id=stage, stage="Report stage" if stage == 1 else "Committee stage",
            house="Commons" if stage == 1 else "Lords", marshalled=1, kind="NewClause",
            summary="", explanatory="", lines="", lead="Dr Caroline Johnson", sponsors=[],
            decision=decision, label="NC" + aid, url="https://x/" + aid,
            text="Prohibition of puberty blockers for under-18s")
        stages = [{"id": 1}, {"id": 2}]
        rows = {1: [mk("142", "Negatived", 1)], 2: [mk("7", "NoDecision", 2)]}
        with mock.patch.object(amendments, "fetch_stages", return_value=stages), \
                mock.patch.object(amendments, "fetch_amendments", side_effect=lambda c, b, s: rows[s["id"]]), \
                mock.patch.object(amendments, "fetch_detail", return_value=None):
            run_weekly.sweep_amendments(None, conn, tax, wl, datetime.date(2026, 10, 19), WEEK, log=lambda *_: None)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM bill_amendments").fetchone()[0], 2)
        self.assertEqual([r[0] for r in conn.execute("SELECT id FROM items")], ["amendment:7"])


if __name__ == "__main__":
    unittest.main()


class Round2Tests(unittest.TestCase):
    """Chris's review of the first DM test (16 October 2026)."""

    def test_also_announced_is_gone(self):
        e = digest.Edition(week_commencing=WEEK, number=10, mode="normal")
        e.announced = [{"date": "2026-10-19", "where": "Commons", "what": "Troubles Bill", "url": "u"}]
        md = digest.render(e)
        self.assertNotIn("Also announced", md)
        self.assertIn("### Coverage notes", md)

    def test_private_meetings_are_never_big_dates(self):
        rows = [cd.Row(date="2026-10-19", where="COMMONS", title="Draft Conversion Practices Bill",
                       detail="private meeting", score=3),
                cd.Row(date="2026-10-20", where="NI ASSEMBLY", title="Bill", session="Closed, 10:30 AM", score=3),
                cd.Row(date="2026-10-22", where="LORDS", title="Debate", score=3)]
        self.assertEqual([r.date for r in cd.mark_big(rows, WEEK)], ["2026-10-22"])

    def test_titles_shortened_by_sense(self):
        r = cd.Row(title="Age it would be considered appropriate for an individual to be able to consent "
                         "to the administration of puberty blockers and cross-sex hormones", lead="Baroness Deech")
        self.assertEqual(cd.short_title(r), "Baroness Deech: age of consent to puberty blockers and cross-sex hormones")
        long = cd.short_title(cd.Row(title="Effect of artificial intelligence, screen usage and social media "
                                           "on children and young people in schools across the country"))
        self.assertNotIn("...", long)
        self.assertLessEqual(len(long), 80)

    def test_votes_of_one_debate_are_one_line(self):
        vs = [{"date": "2026-09-16", "where": "Senedd", "result": r,
               "title": "Item 5. Reform UK Debate - grooming gangs. " + t} for t, r in (
            ("Motion without amendment.", "Motion has been rejected"),
            ("Amendment 1, tabled in the", "Amendment has been agreed"),
            ("Motion as amended.", "Motion as amended has been agreed"))]
        vs.append({"date": "2026-09-11", "where": "Commons", "title": "Terminally Ill Adults (End of Life) Bill: "
                   "Second Reading", "url": "u", "result": "rejected 270 to 286"})
        got = cd.group_votes(vs)
        self.assertEqual(len(got), 2)
        self.assertEqual(cd.vote_line(got[0]), "16 Sep · **Senedd** · Item 5. Reform UK Debate - grooming gangs: "
                                               "motion rejected; amendment agreed; motion as amended agreed")
        self.assertIn("[Terminally Ill Adults (End of Life) Bill: Second Reading](u)", cd.vote_line(got[1]))

    def test_judge_reads_the_watched_bills_why_line(self):
        from src import filter as filt, triage
        conn = store()
        conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title, matched_terms, extra) "
                     "VALUES ('whatson:2026-10-28:1', 'x', 'whatson', 'event', 'Health Bill - committee stage', "
                     "'[\"Health Bill\"]', ?)", (json.dumps({"bill_id": 4124, "description": "Health Bill"}),))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        item = triage.pending_items(conn, wl)[0]
        self.assertIn("watched bill, why we track it: Health Bill: Carried NC142", item.text)


class KeyQuestionsTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        for i, (uin, heading) in enumerate((("HL3710", "Puberty Suppressing Hormones"),
                                            ("HL3711", "Gender Dysphoria: Hormone Treatments"),
                                            ("HL3712", "Gender Dysphoria: Clinics"))):
            self.conn.execute(
                "INSERT INTO items (id, captured_at, source_feed, item_type, title, url, event_date, triage_score, "
                "why_it_matters, issue_areas, extra) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("pq:{0}".format(i), "x", "pq", "pq", "PQ " + uin, "https://q/" + uin, "2026-10-02", 3 - (i == 2),
                 "Overseas online prescribing escapes UK oversight." if i == 0 else "", "[3]",
                 json.dumps({"uin": uin, "house": "Lords", "department": "DHSC", "heading": heading,
                             "member": "Baroness Maclean of Redditch"})))
        self.conn.execute(
            "INSERT INTO items (id, captured_at, source_feed, item_type, title, url, event_date, triage_score, "
            "why_it_matters, issue_areas, extra) VALUES ('pq:9','x','pq','pq','PQ 1','u','2026-10-05',3,'w','[11]','{}')")
        self.conn.execute(
            "INSERT INTO ni_items (id, kind, reference, title, answered, tabler, areas, url, first_seen, last_seen) "
            "VALUES ('ni-question:1','question','AQW 1/22-27','Abortion services in NI.','2026-10-08','Ms A',"
            "'[1]','https://ni/1','x','x')")
        self.conn.execute(
            "INSERT INTO sd_items (id, kind, reference, member_name, body, answered, areas, tier, first_seen, "
            "last_seen) VALUES ('sd-question:1','question','WQ1','Mr B','RSE guidance?','2026-10-07','[6]',1,'x','x')")
        self.conn.commit()

    def test_cluster_rank_and_sources(self):
        rows = cd.key_questions(self.conn, WEEK)
        self.assertEqual(rows[0]["refs"], ["HL3710", "HL3711", "HL3712"])     # one row, not three
        self.assertEqual(rows[0]["where"], "LORDS")
        self.assertEqual([r["where"] for r in rows], ["LORDS", "SENEDD"])       # migration hidden; NI unscored = 1
        md = cd.render_key_questions(rows)
        self.assertIn("| Fri 2 Oct | LORDS | [HL3710\u2013HL3712](https://q/HL3710), Baroness Maclean of Redditch: "
                      "Puberty Suppressing Hormones;", md)
        self.assertIn("Overseas online prescribing escapes UK oversight.", md)
        line = cd.key_question_line(rows)
        self.assertTrue(line.startswith("*Key questions:* 3 Lords questions from Baroness Maclean of Redditch on "
                                        "puberty suppressing hormones (answered 2 Oct)"))

    def test_in_the_edition_after_further_afield(self):
        e = digest.Edition(week_commencing=WEEK, number=10, mode="normal")
        e.key_questions = cd.key_questions(self.conn, WEEK)
        md = digest.render(e)
        self.assertLess(md.index("## Further afield"), md.index("## Key questions"))
        self.assertLess(md.index("## Key questions"), md.index("## Reference"))
        e.timeline = [cd.Row(date="2026-10-22", where="LORDS", title="x", score=2)]
        self.assertIn("*Key questions:*", cd.slack_post(e))


class FreeJudgeTests(unittest.TestCase):
    def test_queue_round_trip_without_spend(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import uk_whatson_judge as j
        from src import filter as filt
        conn = store()
        conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title, event_date, issue_areas, "
                     "matched_terms, tier) VALUES ('whatson:2026-10-28:1','x','whatson','event','Health Bill - "
                     "committee stage','2026-10-28','[3, 5]','[\"Health Bill\"]',NULL)")
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "queue.md")
            self.assertEqual(j.queue_out(conn, wl, path, "2026-10-19", 10, log=lambda *_: None), 1)
            text = open(path).read()
            self.assertIn(j.QUEUE_MARKER, text)
            self.assertIn("NC142", text)
            open(path, "w").write(text.replace("SCORE: ", "SCORE: 3", 1).replace("WHY: ", "WHY: Lords can retable NC142.", 1))
            self.assertEqual(j.queue_in(conn, wl, path, "2026-10-19", log=lambda *_: None), 1)
        row = conn.execute("SELECT triage_score, why_it_matters FROM items").fetchone()
        self.assertEqual((row[0], row[1]), (3, "Lords can retable NC142."))
        src = open(os.path.join(ROOT, "tools", "uk_whatson_judge.py")).read()
        self.assertNotIn("score_live", src)
        self.assertNotIn("ANTHROPIC", src)

    def test_unscored_items_render_on_rules_alone_never_big(self):
        import run_weekly
        conn = store()
        conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title, event_date, issue_areas, "
                     "tier, extra) VALUES ('whatson:2026-10-22:1','x','whatson','event','t','2026-10-22','[3]',1,?)",
                     (json.dumps({"event_id": 1, "house": "Lords", "description": "A debate"}),))
        conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title, event_date, issue_areas, "
                     "tier, extra) VALUES ('whatson:2026-10-23:2','x','whatson','event','t','2026-10-23','[3]',2,?)",
                     (json.dumps({"event_id": 2, "house": "Lords", "description": "Tier two"}),))
        e = digest.Edition(week_commencing=WEEK, number=10, mode="normal")
        with mock.patch.object(run_weekly, "load_settings", return_value={}), \
                mock.patch("src.ingest.pqs.archive_map", return_value={}):
            run_weekly.sections_from_store(conn, e)
        self.assertEqual([l.event["description"] for l in e.week_ahead], ["A debate"])
        self.assertEqual(e.week_ahead[0].tag, 2)
        self.assertIsNone(conn.execute("SELECT triage_score FROM items WHERE id LIKE '%:1'").fetchone()[0])
