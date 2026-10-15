"""Holyrood and Senedd forward business (sp_agenda, sd_agenda), from trimmed
live captures of 15 October 2026. No network."""
import datetime
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, devolved_agenda as dva, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import holyrood_agenda as ha, senedd_agenda as sa  # noqa: E402

import sd_agenda  # noqa: E402
import sp_agenda  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "devolved_agenda")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    """URL -> text; anything else raises FetchError, as a dead host would."""

    def __init__(self, pages):
        self.pages = dict(pages)
        self.asked = []

    def get_text(self, url, feed, slug, **kw):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 503: Service Unavailable")
        return self.pages[url]

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self.get_text(url, feed, slug, **kw))


_TAX = _WL = None


def taxonomy():
    global _TAX, _WL
    if _TAX is None:
        _TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        _WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    return _TAX, _WL


def store():
    return db.init_db(sqlite3.connect(":memory:"))


class WhatsOnTests(unittest.TestCase):
    def test_a_sitting_day_gives_chamber_and_committee_items(self):
        day = ha.parse_whats_on(fixture("sp_whats_on_2026-10-07.html"), "2026-10-07")
        self.assertTrue(day.sitting)
        titles = [i.business for i in day.chamber]
        self.assertEqual(titles[0], "Parliamentary Bureau Motions")
        self.assertTrue(titles[1].startswith("Portfolio Questions: Deputy First Minister"))
        mb = day.chamber[-1]
        self.assertEqual(mb.business, "Members’ Business: Baby Loss Awareness Week 2026")
        self.assertEqual(mb.reference, "S7M-00815")
        self.assertEqual(mb.url, "https://www.parliament.scot/chamber-and-committees/"
                                 "votes-and-motions/S7M-00815")
        self.assertEqual(mb.item_time, "")
        self.assertEqual(day.chamber[0].item_time, "2pm")
        # The oral question lodged is the item's detail, so it is classified too.
        self.assertIn("UK Budget", day.chamber[1].detail)

        rural = [i for i in day.committees if i.body == "Rural Affairs Committee"]
        self.assertEqual([i.order for i in rural], [1, 2, 3, 4, 5])
        self.assertEqual(rural[1].business, "Rural Support Plan")
        self.assertEqual(rural[0].item_time, "8:45am")
        self.assertTrue(rural[1].url.endswith("/session-7/rural-affairs-committee"))
        # Witness lists are names, not business: never in the detail.
        self.assertNotIn("Gillian Martin", rural[1].detail)
        self.assertIn("7th Meeting, 2026", rural[1].detail)
        transport = [i for i in day.committees if i.body == "Transport Committee"]
        self.assertEqual(transport[1].business,
                         "Islands and Regional Air Travel - review of evidence (in private)")

    def test_a_programmed_day_with_no_committee_agenda_yet(self):
        day = ha.parse_whats_on(fixture("sp_whats_on_2026-11-03.html"), "2026-11-03")
        self.assertTrue(day.sitting and day.committee_pending)
        self.assertEqual(len(day.chamber), 10)
        self.assertEqual(day.committees, [])
        self.assertEqual(dva.item_type(day.chamber[4].business), "to be announced")
        self.assertEqual(dva.item_type(day.chamber[-1].business), "to be announced")

    def test_a_day_with_no_meetings_is_empty_not_a_gap(self):
        day = ha.parse_whats_on(fixture("sp_whats_on_2026-11-24.html"), "2026-11-24")
        self.assertFalse(day.sitting)
        self.assertEqual(day.chamber + day.committees, [])

    def test_a_page_for_another_day_or_a_new_shape_is_an_error(self):
        with self.assertRaises(ha.PageShapeError):
            ha.parse_whats_on(fixture("sp_whats_on_2026-11-24.html"), "2026-11-25")
        with self.assertRaises(ha.PageShapeError):
            ha.parse_whats_on('<h2 class="h2">Tuesday 03 November 2026</h2><p>new site</p>',
                              "2026-11-03")


class RedirectTests(unittest.TestCase):
    def test_the_archive_redirect_is_refused(self):
        guard = dva.official_only(("www.parliament.scot", "data.parliament.scot"))
        self.assertIsNone(guard(ha.WHATS_ON.format("2026-11-03"), ""))
        reason, skipped = guard("https://webarchive.nrscotland.gov.uk/3/https://www.parliament."
                                "scot/chamber-and-committees/business-bulletin", "")
        self.assertIn("webarchive.nrscotland.gov.uk", reason)
        self.assertFalse(skipped)


class ProgrammeTests(unittest.TestCase):
    def test_the_newest_programme_wins_and_revisions_are_skipped(self):
        prog, refs = ha.parse_programme(json.loads(fixture("sp_business_programme.json")))
        self.assertEqual(refs["2026-10-27"], "S7M-01505")    # newer than S7M-01390
        self.assertEqual(refs["2026-10-06"], "S7M-01390")
        self.assertEqual(sorted(d for d in prog if d >= "2026-10-27"),
                         ["2026-10-27", "2026-10-28", "2026-10-29",
                          "2026-11-03", "2026-11-04", "2026-11-05"])
        day = [b for _t, b in prog["2026-10-29"]]
        self.assertIn("Scottish Government Debate: Strengthening Scotland's Public Health "
                      "Approach to Preventing Alcohol and Drug Deaths", day)
        self.assertEqual(prog["2026-10-29"][0], ("1.30pm", "Parliamentary Bureau Motions"))
        # The (b) clause about rule 13.7.3 is not business.
        self.assertFalse(any("13.7.3" in b for _t, b in prog["2026-11-05"]))
        self.assertEqual(prog["2026-11-05"][-1], ("5pm", "Members’ Business"))


class ItemTypeTests(unittest.TestCase):
    def test_types(self):
        cases = {
            "Time for Reflection": "procedural",
            "Members’ Business: World Stroke Day 2026": "members' business",
            "Motion on Legislative Consent: Armed Forces Bill - UK Legislation": "legislative consent",
            "Assisted Dying for Terminally Ill Adults (Scotland) Bill: Stage 3": "bill stage",
            "Ministerial Statement: Keeping The Promise": "statement",
            "Portfolio Questions: Justice; Health and Care": "questions",
            "Questions to the First Minister": "questions",
            "Reform UK Debate - Prostate cancer strategy": "debate",
            "Scottish Liberal Democrats Business": "to be announced",
            "Voting Time": "procedural",
        }
        for title, kind in cases.items():
            self.assertEqual(dva.item_type(title), kind, title)
        self.assertEqual(dva.item_type("Motion under Standing Orders 17.42 (vi) to exclude",
                                       committee=True), "procedural")
        self.assertEqual(dva.item_type("Rural Support Plan",
                                       "The Committee will take evidence from", True),
                         "committee evidence")


def whats_on_pages(**dates):
    return {ha.WHATS_ON.format(d): fixture(f) for d, f in dates.items()}


class HolyroodCollectTests(unittest.TestCase):
    def setUp(self):
        self.tax, self.wl = taxonomy()
        self.conn = store()

    def run_window(self, pages, start, end, today):
        client = FakeClient(pages)
        return sp_agenda.collect(client, self.conn, self.tax, self.wl,
                                 datetime.date.fromisoformat(start),
                                 datetime.date.fromisoformat(end), today, log=lambda *a: None)

    def test_pages_programme_fallback_and_gaps(self):
        pages = whats_on_pages(**{"2026-11-03": "sp_whats_on_2026-11-03.html",
                                  "2026-10-07": "sp_whats_on_2026-10-07.html"})
        pages[ha.PROGRAMME_URL] = fixture("sp_business_programme.json")
        # 7 Oct is read from its page; 3 Nov from its page; 4 Nov's page is
        # down, so the Business Programme stands in and a gap is recorded.
        s = self.run_window(pages, "2026-10-07", "2026-10-07", "2026-10-06")
        self.assertEqual(s["gaps"], [])
        s = self.run_window(pages, "2026-11-03", "2026-11-04", "2026-10-15")
        self.assertTrue(s["source_read"])
        self.assertEqual(len(s["gaps"]), 1)
        self.assertIn("What's on 2026-11-04", s["gaps"][0])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='sp-agenda'")
                         .fetchone()[0], 1)
        rows = self.conn.execute("SELECT dated, source, business FROM sp_agenda "
                                 "WHERE dated='2026-11-04' ORDER BY item_order").fetchall()
        self.assertEqual({r[1] for r in rows}, {"business-programme"})
        self.assertIn("Reform UK Business", [r[2] for r in rows])

        # The members' business motion on baby loss is on our ground.
        ours = self.conn.execute(
            "SELECT business, item_type, areas, matched_terms, url, first_seen FROM sp_agenda "
            "WHERE areas != '[]'").fetchall()
        self.assertEqual(len(ours), 1)
        self.assertEqual(ours[0][1], "members' business")
        self.assertIn("baby loss", json.loads(ours[0][3]))
        # Two "Parliamentary Bureau Motions" on one day are two rows.
        n = self.conn.execute("SELECT COUNT(*) FROM sp_agenda WHERE dated='2026-11-03' "
                              "AND business='Parliamentary Bureau Motions'").fetchone()[0]
        self.assertEqual(n, 2)

    def test_a_day_read_again_drops_what_the_source_no_longer_lists(self):
        pages = whats_on_pages(**{"2026-11-03": "sp_whats_on_2026-11-03.html"})
        self.run_window(pages, "2026-11-03", "2026-11-03", "2026-10-15")
        first = self.conn.execute("SELECT first_seen FROM sp_agenda WHERE "
                                  "business='General Questions'").fetchone()[0]
        # A week on the placeholder has become a named debate.
        page = fixture("sp_whats_on_2026-11-03.html").replace(
            "Scottish Government Business", "Scottish Government Debate: Example")
        pages[ha.WHATS_ON.format("2026-11-03")] = page
        s = self.run_window(pages, "2026-11-03", "2026-11-03", "2026-10-22")
        self.assertEqual(s["pruned"], 1)
        names = {r[0] for r in self.conn.execute("SELECT business FROM sp_agenda")}
        self.assertIn("Scottish Government Debate: Example", names)
        self.assertNotIn("Scottish Government Business", names)
        self.assertEqual(self.conn.execute("SELECT first_seen, last_seen FROM sp_agenda WHERE "
                                           "business='General Questions'").fetchone(),
                         (first, "2026-10-22"))

    def test_a_failed_read_keeps_the_rows_it_had(self):
        pages = whats_on_pages(**{"2026-11-03": "sp_whats_on_2026-11-03.html"})
        self.run_window(pages, "2026-11-03", "2026-11-03", "2026-10-15")
        s = self.run_window({}, "2026-11-03", "2026-11-03", "2026-10-22")
        self.assertFalse(s["source_read"])
        self.assertEqual(len(s["gaps"]), 2)        # the page and the API
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sp_agenda").fetchone()[0], 10)


def meetings_xml(committee_id, title, meetings):
    rows = "".join(
        "<meeting><meetingid>{0}</meetingid><meetingdate>{1}</meetingdate>"
        "<meetingstatus>Confirmed</meetingstatus><meetingtime>09.30</meetingtime>"
        "</meeting>".format(mid, d) for mid, d in meetings)
    return ("<?xml version=\"1.0\"?><getmeetings><committee><committeeid>{0}</committeeid>"
            "<committeetitle>{1}</committeetitle><committeemeetings>{2}"
            "</committeemeetings></committee></getmeetings>".format(committee_id, title, rows))


class SeneddTests(unittest.TestCase):
    def setUp(self):
        self.tax, self.wl = taxonomy()
        self.conn = store()
        self.start, self.end = datetime.date(2026, 10, 19), datetime.date(2026, 12, 13)
        f, t = sa.window(self.start, self.end)
        self.pages = {
            sa.COMMITTEES_URL: fixture("sd_committees.xml"),
            sa.MEETINGS_URL.format("908", f, t): fixture("sd_meetings_908.xml"),
            sa.MEETINGS_URL.format("985", f, t): meetings_xml(
                "985", "Health and Social Care Committee", [("16301", "22/10/2026")]),
            sa.MEETING_URL.format("16317"): fixture("sd_meeting_16317.xml"),
            sa.MEETING_URL.format("16420"): fixture("sd_meeting_16420.xml"),
            sa.MEETING_URL.format("16301"): fixture("sd_meeting_16301.xml"),
        }

    def test_parsers(self):
        live = sa.parse_committees(fixture("sd_committees.xml"))
        self.assertEqual([c[0] for c in live], ["983", "985", "908"])   # no expired, WYP, Business
        self.assertEqual(sa.window(self.start, self.end), ("19/10/2026", "13/12/2026"))
        published, _loc, items = sa.parse_meeting(fixture("sd_meeting_16317.xml"))
        self.assertTrue(published)
        self.assertEqual([i.number for i in items], ["1", "3", "9"])    # the note is dropped
        self.assertTrue(items[2].title.startswith("Legislative Consent Motion: The Cyber"))
        self.assertIn("NDM9331", items[2].text)
        self.assertEqual(sa.parse_meeting(fixture("sd_meeting_16420.xml"))[0:3:2], (False, []))
        with self.assertRaises(sa.ServiceShapeError):
            sa.parse_meetings("<!doctype html><title>Service unavailable</title>")

    def test_collect(self):
        client = FakeClient(self.pages)
        s = sd_agenda.collect(client, self.conn, self.tax, self.wl, self.start, self.end,
                              "2026-10-15", log=lambda *a: None)
        self.assertTrue(s["source_read"])
        # Equality's meeting list and Plenary 16318 cannot be read: two gaps.
        self.assertEqual(len(s["gaps"]), 2, s["gaps"])
        self.assertTrue(any("GetMeetings 983" in g for g in s["gaps"]))
        self.assertTrue(any("GetMeeting 16318" in g for g in s["gaps"]))
        self.assertEqual((s["published"], s["unpublished"]), (2, 1))
        rows = self.conn.execute("SELECT key, dated, body, business, item_type, reference, url "
                                 "FROM sd_agenda ORDER BY dated, item_order").fetchall()
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0][:3], ("sd:16317:108860", "2026-10-20", "Plenary"))
        lcm = [r for r in rows if r[5] == "NDM9331"][0]
        self.assertEqual(lcm[4], "legislative consent")
        self.assertEqual(lcm[6], "https://business.senedd.wales/ieListDocuments.aspx?MId=16317")
        self.assertIn("Health and Social Care Committee", {r[2] for r in rows})

        # Next week Health has dropped the 22 October meeting: its rows go.
        self.pages[sa.MEETINGS_URL.format("985", *sa.window(self.start, self.end))] = \
            meetings_xml("985", "Health and Social Care Committee", [])
        s = sd_agenda.collect(FakeClient(self.pages), self.conn, self.tax, self.wl,
                              self.start, self.end, "2026-10-22", log=lambda *a: None)
        self.assertEqual(s["pruned"], 2)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sd_agenda WHERE body = "
                                           "'Health and Social Care Committee'").fetchone()[0], 0)

    def test_no_committee_list_is_a_failed_run(self):
        s = sd_agenda.collect(FakeClient({}), self.conn, self.tax, self.wl, self.start,
                              self.end, "2026-10-15", log=lambda *a: None)
        self.assertFalse(s["source_read"])
        self.assertEqual(len(s["gaps"]), 1)

    def test_bilingual_titles_read_in_english(self):
        self.assertEqual(sa.english("Cyfarfod Llawn / Plenary"), "Plenary")
        self.assertEqual(sa.english("Health and Social Care Committee"),
                         "Health and Social Care Committee")


if __name__ == "__main__":
    unittest.main()
