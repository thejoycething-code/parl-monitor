"""US state legislatures' forward agendas (src/regional_agendas/us.py):
Open States /events, Washington's web services, Texas's TLO RSS. Fixtures
are live replies of 16 October 2026, trimmed. No network."""
import datetime
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.regional_agendas import us  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402

TODAY = "2026-10-16"
CTX = ra.Ctx(TODAY, "2026-12-11")


def fx(name):
    return json.loads(load_fixture("us", name))


def wa_pages(ctx=CTX, items_fail=False):
    pages = {"{0}GetCommitteeMeetings?beginDate={1}&endDate={2}".format(
        us.WA_API, ctx.today, ctx.until): load_fixture("us", "wa_meetings.xml")}
    for m in us.parse_wa_meetings(load_fixture("us", "wa_meetings.xml")):
        url = "{0}GetCommitteeMeetingItems?agendaId={1}".format(us.WA_API, m["id"])
        if m["id"] == "34141":
            pages[url] = load_fixture("us", "wa_items_34141.xml")
        elif not (items_fail and m["id"] == "33552"):
            pages[url] = load_fixture("us", "wa_items_33489.xml")
    return pages


def tx_pages(text=None):
    return {us.TX_RSS.format(k): text or load_fixture("us", "tx_rss_empty.xml")
            for k, _ in us.TX_FEEDS}


class OpenStatesParseTest(unittest.TestCase):
    def test_pennsylvania_bills_times_and_tba(self):
        items = us.parse_os_events(fx("os_pa_1.json"), "pa", CTX)
        jud = [i for i in items if i["body"] == "House Judiciary"]
        self.assertEqual(len(jud), 1)
        self.assertEqual(jud[0]["dated"], "2026-10-19")
        self.assertEqual(jud[0]["item_time"], "10:00")          # 14:00 UTC, Eastern
        self.assertTrue(jud[0]["business"].startswith("SB 1431: An Act amending Title 34"))
        self.assertEqual(jud[0]["reference"], "SB 1431")
        self.assertEqual(jud[0]["item_type"], "bill stage")
        # 'Voting meeting on and any other business' with no bill: a booked slot.
        app = [i for i in items if i["body"] == "House Appropriations"]
        self.assertEqual([i["business"] for i in app], [""])
        # A hearing on a named subject keeps its words, the bills as detail.
        ai = [i for i in items if "Frontier AI" in i["business"]]
        self.assertEqual(len(ai), 1)
        self.assertEqual(ai[0]["reference"], "HB 2800, HB 2829")
        self.assertNotIn("opens in a new tab", json.dumps(items))

    def test_new_jersey_one_item_per_bill(self):
        items = us.parse_os_events(fx("os_nj.json"), "nj", CTX)
        labor = [i for i in items if i["body"] == "Assembly Labor Committee"]
        self.assertEqual([i["reference"] for i in labor], ["A 5433", "A 5517", "A 5535"])
        self.assertTrue(all(i["meeting_id"] == labor[0]["meeting_id"] for i in labor))
        self.assertEqual([i["item_order"] for i in labor], [1, 2, 3])
        self.assertIn("tipped workers", labor[1]["business"])

    def test_california_generic_names_and_committee_agenda(self):
        items = us.parse_os_events(fx("os_ca.json"), "ca", CTX)
        first = items[0]
        # Event 'JOINT HEARING': the committee participant names the body.
        self.assertTrue(first["body"].startswith("Senate Joint Legislative Committee on Climate"))
        self.assertEqual(first["business"], "")                 # 'COMMITTEE AGENDA - ...'
        self.assertEqual(first["item_time"], "10:30")           # Pacific
        named = [i["business"] for i in items if i["business"]]
        self.assertIn("Electric Vehicle Deployment in California", named)

    def test_louisiana_name_prefix(self):
        items = us.parse_os_events(fx("os_la.json"), "la", CTX)
        self.assertFalse(any(i["body"].startswith("Meeting on") for i in items))
        self.assertEqual(items[0]["body"], "Joint Highway Priority Construction")

    def test_cancelled_and_out_of_window(self):
        data = fx("os_nj.json")
        data["results"][0]["status"] = "cancelled"
        data["results"][1]["start_date"] = "2027-02-01T15:00:00+00:00"
        items = us.parse_os_events(data, "nj", CTX)
        bodies = {i["body"] for i in items}
        self.assertNotIn("Assembly Labor Committee", bodies)
        self.assertEqual(len(bodies), 1)

    def test_local_when(self):
        self.assertEqual(us.local_when("2026-10-19", "pa"), ("2026-10-19", None))
        self.assertEqual(us.local_when("2026-10-20T03:00:00+00:00", "ca"), ("2026-10-19", "20:00"))
        self.assertEqual(us.local_when("2026-10-20T15:00:00+00:00", "hi"), ("2026-10-20", "05:00"))

    def test_plan_rotates_and_covers_everyone(self):
        d = datetime.date(2026, 10, 16)
        plan = us.plan_states(d)
        self.assertTrue(set(us.PRIORITY) <= plan)
        self.assertFalse(plan & set(us.DIRECT))
        self.assertLessEqual(len(plan), us.OS_CALLS - us.RESERVE)
        seen = set()
        for w in range(4):
            seen |= us.plan_states(d + datetime.timedelta(weeks=w))
        self.assertEqual(seen, set(us.STATES) - set(us.DIRECT))
        self.assertNotEqual(plan, us.plan_states(d + datetime.timedelta(weeks=1)))


class DirectParseTest(unittest.TestCase):
    def test_washington(self):
        meetings = us.parse_wa_meetings(load_fixture("us", "wa_meetings.xml"))
        self.assertEqual(len(meetings), 11)
        jtc = [m for m in meetings if m["id"] == "34187"][0]
        self.assertTrue(jtc["cancelled"])
        pen = [m for m in meetings if m["id"] == "34141"][0]
        self.assertEqual((pen["dated"], pen["time"]), ("2026-10-20", "10:00"))
        self.assertIn("Pension Policy", pen["body"])
        items = us.parse_wa_items(load_fixture("us", "wa_items_34141.xml"))
        self.assertEqual(len(items), 7)
        self.assertEqual(items[0][1], "Approval of September Minutes")
        self.assertEqual(items[-1][2], "Public Hearing")
        self.assertEqual(us.parse_wa_items(load_fixture("us", "wa_items_33489.xml")), [])

    def test_texas_rss(self):
        self.assertEqual(us.parse_tx_rss(load_fixture("us", "tx_rss_empty.xml"), "House"), [])
        # CONSTRUCTED (no meeting was posted on 16 October 2026): the channel
        # as served, with one item in the shape of a TLO notice.
        text = load_fixture("us", "tx_rss_empty.xml").replace(
            "<item><title>No committee meetings scheduled.</title>",
            "<item><title>Public Health - 11/04/2026 9:00 AM</title>"
            "<link>https://capitol.texas.gov/tlodocs/89R/schedules/html/C4102026110409001.HTM</link>"
            "</item><item><title>No committee meetings scheduled.</title>")
        got = us.parse_tx_rss(text, "House")
        self.assertEqual(got, [("2026-11-04", "09:00", "House Public Health",
                                "https://capitol.texas.gov/tlodocs/89R/schedules/html/"
                                "C4102026110409001.HTM")])


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.p = [mock.patch.object(us, "openstates_key", lambda: "test-key"),
                  mock.patch.object(us, "API_SPACING_S", 0)]
        for p in self.p:
            p.start()

    def tearDown(self):
        for p in self.p:
            p.stop()

    def pages(self):
        pages = {us.events_url("pa", CTX, 1): load_fixture("us", "os_pa_1.json"),
                 us.events_url("pa", CTX, 2): load_fixture("us", "os_pa_2.json"),
                 us.events_url("nj", CTX, 1): load_fixture("us", "os_nj.json")}
        pages.update(wa_pages())
        pages.update(tx_pages())
        return pages

    def run_collect(self, client, conn=None, regions=("pa", "nj", "wa", "tx", "al"), today=TODAY):
        conn = conn or store()
        s = ra.collect(conn, "us", client, today, days=56, regions=list(regions), mod=us,
                       log=lambda *a: None)
        return conn, s

    def test_end_to_end(self):
        client = FakeClient(self.pages())
        conn, s = self.run_collect(client)
        self.assertEqual(sorted(s["read"]), ["nj", "pa", "tx", "wa"])
        self.assertEqual(s["skipped"], ["al"])                  # rotation: not asked
        self.assertEqual(s["gap"], [])
        os_calls = [u for u in client.asked if u.startswith(us.API)]
        self.assertEqual(len(os_calls), 3)                      # pa x2, nj; al not in plan
        rows = {r["region"]: r["n"] for r in conn.execute(
            "SELECT region, COUNT(*) n FROM regional_agenda GROUP BY region")}
        self.assertNotIn("al", rows)
        self.assertGreater(rows["pa"], 5)
        self.assertGreater(rows["wa"], 7)
        runs = {r["region"]: dict(r) for r in conn.execute("SELECT * FROM regional_agenda_runs")}
        self.assertIn("not asked this run", runs["al"]["note"])
        self.assertEqual(runs["al"]["status"], "skipped")
        tba = conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE item_type=?",
                           (ra.TBA,)).fetchone()[0]
        self.assertEqual(tba, s["tba"])
        self.assertGreater(tba, 0)
        hearing = conn.execute("SELECT item_type FROM regional_agenda WHERE region='wa' "
                               "AND business LIKE 'WSPRS Survivor Medical%'").fetchone()[0]
        self.assertEqual(hearing, "committee evidence")
        # Cancelled Washington meeting (34187) not stored.
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda "
                                      "WHERE meeting_id='wa:34187'").fetchone()[0], 0)

    def test_dead_hosts_keep_rows(self):
        conn, _ = self.run_collect(FakeClient(self.pages()))
        before = conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0]
        conn, s = self.run_collect(FakeClient({}), conn=conn, today="2026-10-17")
        self.assertEqual(sorted(s["gap"]), ["nj", "pa", "tx", "wa"])
        after = conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0]
        self.assertEqual(before, after)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='us-regional-agenda'")]
        self.assertEqual(len(gaps), 4)

    def test_wa_one_agenda_fails(self):
        pages = wa_pages(items_fail=True)
        read = us.read_wa(FakeClient(pages), CTX)
        self.assertEqual(len(read.gaps), 1)
        self.assertTrue(all(u[0] == "meeting" for u in read.units))
        self.assertNotIn(("meeting", "wa:33552"), read.units)

    def test_budget_spent_mid_state(self):
        with mock.patch.object(us, "OS_CALLS", 1):
            ctx = ra.Ctx(TODAY, "2026-12-11")
            read = us.os_reader("pa")(FakeClient(self.pages()), ctx)
        self.assertEqual(len(read.gaps), 1)
        self.assertEqual(read.units[0][0], "window")
        self.assertLess(read.units[0][2], "2026-12-11")          # only the days fully read

    def test_no_key_one_gap(self):
        with mock.patch.object(us, "openstates_key", lambda: None):
            conn, s = self.run_collect(FakeClient(self.pages()), regions=("pa", "nj", "wa"))
        self.assertEqual(s["gap"], ["pa"])
        self.assertIn("wa", s["read"])
        runs = {r["region"]: r["note"] for r in conn.execute("SELECT * FROM regional_agenda_runs")}
        self.assertIn("no Open States key", runs["nj"])

    def test_ledger_at_cap_stops_calls(self):
        conn = store()
        from src import us_states_store as uss
        uss.ensure_schema(conn)
        conn.execute("INSERT INTO uss_api_ledger (day, requests, last_at) VALUES (?,?,?)",
                     (us.utc_day(), us.DAILY_CAP, "x"))
        ctx = ra.Ctx(TODAY, "2026-12-11")
        ctx.conn = conn
        client = FakeClient(self.pages())
        read = us.os_reader("pa")(client, ctx)
        self.assertEqual(client.asked, [])
        self.assertIn("not read", read.note)
        # Under the cap: each request is written to the ledger before it goes.
        conn.execute("UPDATE uss_api_ledger SET requests=10")
        ctx2 = ra.Ctx(TODAY, "2026-12-11")
        ctx2.conn = conn
        us.os_reader("pa")(FakeClient(self.pages()), ctx2)
        self.assertEqual(conn.execute("SELECT requests FROM uss_api_ledger").fetchone()[0], 12)

    def test_429_stops_the_run(self):
        err = FetchError(us.events_url("pa", CTX, 1), "f", "s", 1, "HTTP Error 429")
        err.cause = type("C", (), {"code": 429})()
        pages = self.pages()
        pages[us.events_url("pa", CTX, 1)] = err
        conn, s = self.run_collect(FakeClient(pages), regions=("pa", "nj"))
        self.assertEqual(s["gap"], ["pa"])
        runs = {r["region"]: r["note"] for r in conn.execute("SELECT * FROM regional_agenda_runs")}
        self.assertIn("429", runs["nj"])


if __name__ == "__main__":
    unittest.main()
