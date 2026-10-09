"""Ireland phase 2: questions (tools/ie_questions.py), debate speeches
(tools/ie_debates.py), the week ahead (tools/ie_schedule.py), and their
place in the edition and the judge's queue. No network.

The fixtures in tests/fixtures/ie are real, saved on 9 October 2026:
questions.json.gz holds six API question records with their answers (an
abortion question the Minister for Health referred to the HSE, an
Islamophobia question with a deferred reply, an oral question to the
Minister for Justice, Home Affairs and Migration, a junior Minister's
answer, a consular question to the Taoiseach and an extreme pornography
question); debates.json.gz the Dáil's record of 30 September 2026 cut to six
sections and the Joint Committee on Health's of the same day (the Three Day
Wait Bill hearing); detailed-schedule.html.gz the Oireachtas's detailed
schedule page as read that morning, cut to a few days a tab.
"""

import copy
import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, filter as filt  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "ie")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ieq = _load("ie_questions")
ied = _load("ie_debates")
ies = _load("ie_schedule")
iem = _load("ie_monitor")
iet = _load("ie_triage")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = ied.roll.empty_watchlist()
TODAY = "2026-10-09"


def fixture(name):
    with gzip.open(os.path.join(FX, name), "rt", encoding="utf-8") as fh:
        return fh.read() if name.endswith(".html.gz") else json.load(fh)


QUESTIONS = fixture("questions.json.gz")
DEBATES = fixture("debates.json.gz")
SCHEDULE = fixture("detailed-schedule.html.gz")


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def q_rec(key):
    return next(r for r in QUESTIONS["results"] if r["question"]["uri"].endswith(key))


class FakeClient:
    """Answers /questions and /debates from the fixtures, whatever the week."""

    def __init__(self, debates=None):
        self.urls = []
        self.debates = debates or DEBATES

    def get_json(self, url, feed, slug, archive=True):
        self.urls.append(url)
        query = parse_qs(urlsplit(url).query)
        skip = int(query.get("skip", ["0"])[0])
        if "/questions?" in url:
            return {"results": QUESTIONS["results"] if skip == 0 else []}
        kind = query["chamber_type"][0]
        recs = [r for r in self.debates["results"]
                if (r["debateRecord"]["house"].get("chamberType") == "committee") == (kind == "committee")]
        return {"results": recs if skip == 0 else []}


# --- questions ------------------------------------------------------------------

class QuestionTests(unittest.TestCase):
    def test_a_question_parses_its_key_office_and_reference(self):
        q = ieq.parse_question(q_rec("2026-10-01/pq_413"))
        self.assertEqual(q["key"], "2026-10-01/pq_413")
        self.assertEqual(q["ref"], "69420/26")
        self.assertEqual(q["minister"], "Minister for Health")
        self.assertTrue(q["question"].startswith("the Minister for Health the reason"))
        self.assertEqual(q["url"], "https://www.oireachtas.ie/en/debates/question/2026-10-01/413/")

    def test_the_answer_is_one_sentence_never_the_answer(self):
        q = ieq.parse_question(q_rec("2026-10-01/pq_413"))
        self.assertEqual(q["answer_by"], "Minister for Health")    # a bare office label
        self.assertEqual(q["answer_shape"], "referred for direct reply")
        self.assertTrue(q["answer_takeaway"].startswith("As this is an operational matter"))
        oral = ieq.parse_question(q_rec("2026-10-07/pq_1"))
        self.assertLessEqual(len(oral["answer_takeaway"]), ieq.TAKEAWAY_CHARS)
        # The exchange is long; the store keeps one sentence of the Minister's turn.
        self.assertGreater(len(q_rec("2026-10-07/pq_1")["question"]["answerText"]), 2000)
        self.assertIn("(Deputy Jim O'Callaghan)", oral["answer_by"])

    def test_a_junior_minister_and_a_grouped_answer(self):
        q = ieq.parse_question(q_rec("2026-09-29/pq_554"))
        self.assertEqual(q["answer_by"],
                         "Minister of State at the Department of Justice, Home Affairs and Migration")
        # "I propose to take Questions Nos. 554 and 581 together." is passed over.
        self.assertTrue(q["answer_takeaway"].startswith("Government considers"))

    def test_a_deferred_reply_says_so(self):
        q = ieq.parse_question(q_rec("2026-10-01/pq_381"))
        self.assertEqual(q["answer_shape"], "deferred")

    def test_the_justice_ministers_title_files_nothing_under_migration(self):
        q = ieq.parse_question(q_rec("2026-10-07/pq_1"))
        self.assertIn("Migration", q["question"])
        self.assertNotIn(11, ieq.classify(TAX, WL, q).issue_areas or [])

    def test_the_takeaway_shapes(self):
        self.assertEqual(ieq.takeaway("I thank the Deputy. The data is not held centrally.")[1],
                         "The data is not held centrally.")
        # Devolution's 'not our remit' is not an Irish shape.
        shape, line = ieq.takeaway("Ensuring integrity is a shared responsibility of myself as "
                                   "Minister and my Department.")
        self.assertEqual(shape, "")
        self.assertLessEqual(len(ieq.takeaway("word " * 200)[1]), ieq.TAKEAWAY_CHARS)

    def test_pull_stores_only_our_ground_and_measures_the_week(self):
        conn = store()
        client = FakeClient()
        weeks, total, ours, gaps = ieq.pull(conn, client, TODAY, since="2026-10-05", tax=TAX, log=lambda *a: None)
        self.assertEqual((weeks, total, gaps), (1, 6, 0))
        keys = {r[0] for r in conn.execute("SELECT question_key FROM ie_questions")}
        self.assertIn("2026-10-01/pq_413", keys)              # abortion
        self.assertNotIn("2026-10-06/pq_1", keys)             # the Taoiseach, consular
        self.assertNotIn("2026-10-07/pq_1", keys)             # protected disclosures
        w = conn.execute("SELECT * FROM ie_windows WHERE feed='questions'").fetchone()
        self.assertEqual((w["week_of"], w["status"], w["records"], w["ours"]),
                         ("2026-10-05", "read", 6, ours))
        self.assertEqual(sum(json.loads(w["by_area"]).values()) >= ours, True)
        # Paged with answers, a week at a time, never to the count.
        self.assertIn("show_answers=true", client.urls[0])
        self.assertIn("date_end=2026-10-11", client.urls[0])
        # No column holds the answer itself.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ie_questions)")}
        self.assertNotIn("answer", cols)
        self.assertNotIn("answer_text", cols)

    def test_weeks_due_newest_first_and_recent_ones_again(self):
        conn = store()
        from src import ie_store
        self.assertEqual(ie_store.due_weeks(conn, "questions", "2026-09-14", TODAY, 14)[:2],
                         ["2026-10-05", "2026-09-28"])
        for w in ("2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"):
            ie_store.record_week(conn, "questions", w, "read", 1, 1, 0, {}, TODAY)
        # Read weeks drop out, except those ending within the re-read window
        # (the week of 21 September ends on the 27th, twelve days back).
        self.assertEqual(ie_store.due_weeks(conn, "questions", "2026-09-14", TODAY, 14),
                         ["2026-10-05", "2026-09-28", "2026-09-21"])
        ie_store.record_week(conn, "questions", "2026-09-14", "partial", 1, 1, 0, {}, TODAY)
        self.assertIn("2026-09-14", ie_store.due_weeks(conn, "questions", "2026-09-14", TODAY, 14))


# --- debates --------------------------------------------------------------------

class DebateTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.bills = ied.Bills(self.conn, TAX, WL, watch={"2026/76": ([7], "SLAPP")})

    def speeches(self):
        return [sp for rec in DEBATES["results"] for sp in ied.speeches_in(rec)]

    def test_labels_are_struck_and_offices_kept_as_role(self):
        sp = {(s["section"], s["speaker"]): s for s in self.speeches()}
        taoiseach = sp[("dbsect_11", "Micheál Martin")]
        self.assertEqual(taoiseach["role"], "The Taoiseach")
        self.assertFalse(taoiseach["text"].startswith("The Taoiseach"))
        brophy = sp[("dbsect_12", "Colm Brophy")]
        self.assertIn("(Deputy Colm Brophy)", brophy["role"])
        self.assertFalse(brophy["text"].startswith("Minister of State"))
        sheehan = sp[("dbsect_11", "Conor Sheehan")]
        self.assertIsNone(sheehan["role"])
        self.assertFalse(sheehan["text"].startswith("Deputy"))

    def test_one_row_per_member_per_section_and_members_only(self):
        rows = self.speeches()
        keys = [(s["record_uri"], s["section"], s["member_code"]) for s in rows]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(s["member_code"] for s in rows))
        cmte = [s for s in rows if s["chamber"] == "committee"]
        self.assertTrue(cmte and all(s["committee"] == "Joint Committee on Health" for s in cmte))

    def test_oral_pq_sections_are_skipped(self):
        rec = copy.deepcopy(DEBATES["results"][0])
        for s in rec["debateRecord"]["debateSections"]:
            s["debateSection"]["debateType"] = "question"
        self.assertEqual(list(ied.speeches_in(rec)), [])

    def test_own_words_match_and_migration_alone_is_not_stored(self):
        conn, client = self.conn, FakeClient()
        weeks, total, ours, gaps = ied.pull(conn, client, TODAY, since="2026-10-05", tax=TAX,
                                            log=lambda *a: None)
        self.assertEqual(gaps, 0)
        rows = conn.execute("SELECT * FROM ie_speeches").fetchall()
        self.assertEqual(len(rows), ours)
        self.assertTrue(all(r["areas_from"] == "own" for r in rows))
        sections = {r["section_title"] for r in rows}
        self.assertNotIn("Migration and Citizenship: Statements", sections)
        nolan = next(r for r in rows if r["speaker"] == "Carol Nolan")
        self.assertEqual(json.loads(nolan["areas"]), [1])
        self.assertLessEqual(len(nolan["excerpt"]), ied.EXCERPT)
        self.assertEqual(nolan["url"],
                         "https://www.oireachtas.ie/en/debates/debate/joint_committee_on_health/2026-09-30/2/")
        w = {r["feed"]: r for r in conn.execute("SELECT * FROM ie_windows")}
        self.assertEqual(set(w), {"debates-house", "debates-committee"})
        self.assertEqual(sum(r["items"] for r in w.values()), total)

    def _sp(self, text, words=None, bill_key=None, title="Some Bill 2026: Second Stage"):
        return {"text": text, "words": words if words is not None else len(text.split()),
                "bill_key": bill_key, "title": title}

    def test_a_bill_lends_only_its_short_title_and_only_to_a_long_speech(self):
        self.conn.execute("INSERT INTO ie_bills (bill_key, year, number, title, long_title) VALUES "
                          "('2026/47', 2026, 47, 'Health (Abolition of Three Day Wait Rule) "
                          "(Amendment) Bill 2026 abortion', 'An Act')")
        self.conn.execute("INSERT INTO ie_bills (bill_key, year, number, title, long_title) VALUES "
                          "('2024/66', 2024, 66, 'Mental Health Bill 2024', "
                          "'to provide for parental consent')")
        long_ = "We must fund the services properly and on time. " * 20
        own, areas, source, *_ = ied.classify_speech(TAX, WL, self._sp(long_, bill_key="2026/47"),
                                                     self.bills)
        self.assertEqual((own, source), ([], "bill"))
        self.assertIn(1, areas)
        # Too short to stand on the bill.
        self.assertEqual(ied.classify_speech(TAX, WL, self._sp("Is that agreed?", bill_key="2026/47"),
                                             self.bills)[2], None)
        # The long title never lends: the Mental Health Bill lesson.
        self.assertEqual(ied.classify_speech(TAX, WL, self._sp(long_, bill_key="2024/66"),
                                             self.bills)[2], None)

    def test_the_watchlist_lends_by_key_and_a_motion_by_its_heading(self):
        long_ = "We must fund the services properly and on time. " * 20
        cls = ied.classify_speech(TAX, WL, self._sp(long_, bill_key="2026/76"), self.bills)
        self.assertEqual((cls[1], cls[2]), ([7], "watch"))
        cls = ied.classify_speech(TAX, WL, self._sp(long_, title="Abortion Services: Motion"),
                                  self.bills)
        self.assertEqual(cls[2], "heading")
        self.assertIn(1, cls[1])

    def test_a_long_excerpt_is_cut_around_the_term(self):
        text = "word " * 200 + "the abortion law matters " + "more " * 200
        e = ied.around(text, ["abortion"])
        self.assertIn("abortion", e)
        self.assertLessEqual(len(e), ied.EXCERPT)

    def test_own_words_win_over_anything_lent(self):
        cls = ied.classify_speech(TAX, WL, self._sp("The abortion figures are rising.",
                                                    bill_key="2026/76"), self.bills)
        self.assertEqual((cls[0], cls[2]), ([1], "own"))

    def test_the_section_bill_joins_by_id(self):
        self.conn.execute("INSERT INTO ie_bill_debates (debate_uri, debate_section, bill_key) "
                          "VALUES ('u', 'dbsect_3', '2026/10')")
        self.assertEqual(self.bills.key("u", "dbsect_3", None), "2026/10")
        self.assertEqual(self.bills.key("u", "dbsect_4", "2026/34"), "2026/34")
        self.assertIsNone(self.bills.key("u", "dbsect_5", None))
        self.assertEqual(ied.bill_key_from_uri("https://data.oireachtas.ie/ie/oireachtas/bill/2026/34"),
                         "2026/34")


# --- the week ahead -------------------------------------------------------------

class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.parsed = ies.parse_page(SCHEDULE)

    def test_days_and_the_recess_note(self):
        dail = self.parsed["dail"]
        self.assertEqual(len(dail["2026-09-29"]["items"]), 10)
        self.assertEqual(dail["2026-10-14"]["items"], [])
        self.assertEqual(dail["2026-10-14"]["note"], "Dáil Éireann resumes on Tuesday, 13 October 2026")

    def test_a_linked_bill_is_keyed_and_a_named_one_stays_text(self):
        seanad = self.parsed["seanad"]["2026-10-14"]["items"]
        media = next(i for i in seanad if "Media Regulation" in i["text"])
        self.assertEqual((media["time"], media["bill_keys"]), ("13:00", ["2026/19"]))
        dail = self.parsed["dail"]["2026-09-29"]["items"]
        ai = next(i for i in dail if "Artificial Intelligence Companion" in i["text"])
        self.assertEqual(ai["bill_keys"], [])
        self.assertEqual(ai["bill_named"],
                         ["Artificial Intelligence Companion Services (Protection of Children) Bill 2026"])

    def test_committee_meetings_carry_their_committee_and_agenda(self):
        cmte = self.parsed["committee"]["2026-10-13"]["items"]
        slapp = next(i for i in cmte if i["bill_keys"] == ["2026/76"])
        self.assertEqual(slapp["committee"], "Select Committee on Justice, Home Affairs and Migration")
        self.assertIn("Committee Stage Consideration", slapp["text"])
        self.assertNotIn("Contact Details", slapp["text"])

    def test_store_replaces_a_days_lines_and_strikes_the_office(self):
        conn = store()
        ies.store(conn, self.parsed, TODAY, tax=TAX)
        row = conn.execute("SELECT * FROM ie_schedule WHERE bill_key='2026/76' AND "
                           "chamber='committee'").fetchone()
        # 'Minister for Justice, Home Affairs and Migration, Department of Justice, ...'
        self.assertNotIn(11, json.loads(row["own_areas"]))
        n = conn.execute("SELECT COUNT(*) FROM ie_schedule").fetchone()[0]
        ies.store(conn, self.parsed, TODAY, tax=TAX)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ie_schedule").fetchone()[0], n)
        changed = copy.deepcopy(self.parsed)
        changed["seanad"]["2026-10-14"]["items"] = changed["seanad"]["2026-10-14"]["items"][:2]
        ies.store(conn, changed, TODAY, tax=TAX)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ie_schedule WHERE chamber='seanad' "
                                      "AND date='2026-10-14'").fetchone()[0], 2)
        day = conn.execute("SELECT * FROM ie_schedule_days WHERE chamber='dail' AND "
                           "date='2026-10-14'").fetchone()
        self.assertEqual((day["status"], day["items"]), ("none", 0))


# --- the edition and the judge --------------------------------------------------

def _bill(conn, key, title, areas):
    year, number = key.split("/")
    conn.execute("INSERT INTO ie_bills (bill_key, year, number, title, areas, alive, status) "
                 "VALUES (?,?,?,?,?,1,'Current')", (key, int(year), int(number), title,
                                                     json.dumps(areas)))


class EditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = store()
        _bill(conn, "2026/19", "Media Regulation Bill 2026", [7])
        _bill(conn, "2026/76", "Strategic Lawsuits against Public Participation Bill 2026", [7])
        ieq.pull(conn, FakeClient(), TODAY, since="2026-10-05", tax=TAX, log=lambda *a: None)
        ied.pull(conn, FakeClient(), TODAY, since="2026-10-05", tax=TAX, log=lambda *a: None)
        # Questions and speeches dated inside the edition's week.
        conn.execute("UPDATE ie_questions SET date='2026-10-06'")
        conn.execute("UPDATE ie_speeches SET date='2026-10-07'")
        ies.store(conn, ies.parse_page(SCHEDULE), TODAY, tax=TAX)
        cls.template = conn

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.template.backup(self.conn)
        self.conn.row_factory = sqlite3.Row

    def test_questions_show_the_takeaway_and_link_never_the_answer(self):
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("## Questions this week (", text)
        self.assertIn("of 6 asked", text)
        self.assertIn("https://www.oireachtas.ie/en/debates/question/2026-10-01/413/", text)
        self.assertIn("I have asked the HSE to respond", text)
        self.assertIn("2026-10-06/461/", text)     # extreme pornography: 2,545 characters answered
        full = " ".join(q_rec("2026-10-06/pq_461")["question"]["answerText"].split())
        self.assertGreater(len(full), 2000)
        for start in range(300, 2000, 300):
            self.assertNotIn(full[start:start + 80], text)

    def test_debate_groups_by_section_with_excerpts(self):
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("## Debate this week (", text)
        self.assertIn("Joint Committee on Health", text)
        self.assertIn("matched on own words", text)
        self.assertIn("**Debate:**", text)

    def test_coming_up_keys_bills_and_says_the_dail_is_not_posted(self):
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("## Coming up: 2026-10-10 to 2026-10-19", text)
        self.assertIn("No business posted yet for the coming days; it resumes on 2026-10-13", text)
        self.assertIn("[Media Regulation Bill 2026](https://www.oireachtas.ie/en/bills/bill/2026/19/)", text)
        self.assertIn("Select Committee on Justice, Home Affairs and Migration", text)

    def test_a_long_recess_says_so(self):
        self.conn.execute("DELETE FROM ie_schedule")
        self.conn.execute("UPDATE ie_schedule_days SET status='none', note=NULL")
        self.conn.execute("UPDATE ie_schedule_days SET note='Dáil Éireann resumes on Tuesday, "
                          "13 January 2027' WHERE chamber='dail'")
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("**Dáil.** In recess: it resumes on 2027-01-13.", text)
        self.assertIn("Dáil: in recess to 2027-01-13", iem.dm_summary(self.conn, TODAY))

    def test_no_schedule_says_it_was_not_collected(self):
        conn = store()
        self.assertIn("The week ahead was not collected", iem.render_edition(conn, TODAY))

    def test_no_em_dashes_and_the_dm_carries_the_new_lines(self):
        text = iem.render_edition(self.conn, TODAY)
        self.assertNotIn("—", text)
        dm = iem.dm_summary(self.conn, TODAY)
        self.assertIn("Questions:", dm)
        self.assertIn("*Coming up:*", dm)
        self.assertIn("Media Regulation Bill 2026", dm)

    def test_the_judge_queues_questions_and_own_word_speeches_only(self):
        self.conn.execute("UPDATE ie_speeches SET areas_from='bill' WHERE speaker='Carol Nolan'")
        ids = [i.id for i in iet.pending(self.conn)]
        self.assertIn("ie_questions:2026-10-01/pq_413", ids)
        self.assertTrue(any(i.startswith("ie_speeches:") for i in ids))
        self.assertFalse(any(i.startswith("ie_speeches:") and "Carol-Nolan" in i for i in ids))
        n = iet.apply(self.conn, [type("R", (), {"id": "ie_questions:2026-10-01/pq_413", "score": 2,
                                                  "why_it_matters": "Abortion data."})()])
        self.assertEqual(n, 1)
        self.assertNotIn("ie_questions:2026-10-01/pq_413", [i.id for i in iet.pending(self.conn)])
        self.assertIn("PARLIAMENTARY QUESTION", iet.SYSTEM_PROMPT_IE)


if __name__ == "__main__":
    unittest.main()
