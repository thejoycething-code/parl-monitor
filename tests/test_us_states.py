"""The fifty state legislatures (tools/us_states.py, src/us_states_store.py)
and the States section of the US edition.

Fixtures are Open States' own files, trimmed, with no key in them:
  * WY_2026_csv_trimmed.zip: the Wyoming 2026 bulk file cut to three bills
    (HB 126 Human heartbeat act, HB 113 Parent rights-amendments, HB 114
    Railroad safety) with all their actions, sponsors, votes and positions.
  * api_bills_vt.json: one page of /bills (Vermont H 951 and H 930) with
    every include, as the API returned it on 9 October 2026.
  * jurisdictions.json: the jurisdiction list cut to five, sessions included.
  * people_vt.csv: four rows of the open people file, contact columns dropped.
"""

import datetime
import io
import json
import os
import sqlite3
import tempfile
import unittest
import urllib.error
from unittest import mock

from src import db, filter as filt, us_states_store as uss
from src.http import FetchError
from tools import us_monitor
from tools import us_states as ust

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "us_states")
TODAY = "2026-10-09"


def fixture(name, mode="rb"):
    with open(os.path.join(FIX, name), mode) as fh:
        return fh.read()


def store():
    conn = db.init_db(db.connect(":memory:"))
    return conn


TAX = filt.load_taxonomy(ust.TAXONOMY)
WL = ust.empty_watchlist()


class FakeClient:
    """Answers bulk and people URLs from fixtures; records what was asked."""

    def __init__(self, files=None):
        self.files = files or {}
        self.asked = []
        self.archived = []

    def get_bytes(self, url, feed, slug, timeout=None, archive=True, headers=None, **kw):
        self.asked.append((url, headers))
        for frag, data in self.files.items():
            if frag in url:
                if isinstance(data, Exception):
                    raise data
                return data
        raise FetchError(url, feed, slug, 1, urllib.error.HTTPError(url, 404, "nf", {}, None))

    def get_text(self, url, feed, slug, **kw):
        return self.get_bytes(url, feed, slug).decode("utf-8")

    def _archive(self, raw, feed, slug):
        self.archived.append(slug)


def refusal(code, body):
    err = urllib.error.HTTPError("https://v3.openstates.org/bills", code, "x", {},
                                 io.BytesIO(body.encode()))
    return FetchError("https://v3.openstates.org/bills", ust.FEED, "s", 1, err)


class KeyTests(unittest.TestCase):
    def test_readable_key_drops_spaces_never_uses_the_title(self):
        self.assertEqual(uss.bill_key("tx", "89R", "HB 229"), "TX/89R/HB229")
        self.assertEqual(uss.bill_key("ia", "2025-2026", "HSB 158"), "IA/2025-2026/HSB158")

    def test_state_of_jurisdiction(self):
        self.assertEqual(uss.state_of("ocd-jurisdiction/country:us/state:wy/government"), "wy")
        self.assertIsNone(uss.state_of("ocd-jurisdiction/country:us/district:dc/government"))

    def test_tables_declared(self):
        for t in uss.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertTrue(t.startswith("uss_"))

    def test_watchlist_keys_are_well_formed(self):
        wl = uss.watchlist()
        self.assertGreater(len(wl), 30)
        for key, (areas, why) in wl.items():
            st, session, ident = key.split("/", 2)
            self.assertIn(st.lower(), uss.STATES, key)
            self.assertNotIn(" ", ident, key)
            self.assertTrue(session and why, key)
            self.assertTrue(areas and all(1 <= a <= 13 for a in areas), key)


class BulkTests(unittest.TestCase):
    def setUp(self):
        self.raw = fixture("WY_2026_csv_trimmed.zip")

    def test_reads_every_bill_and_keeps_what_keep_says(self):
        n, bills = ust.bills_from_bulk(self.raw, lambda b: True)
        self.assertEqual(n, 3)
        by = {b["identifier"]: b for b in bills}
        self.assertEqual(set(by), {"HB 126", "HB 113", "HB 114"})
        hb = by["HB 126"]
        self.assertEqual(hb["title"], "Human heartbeat act.")
        self.assertEqual(hb["chamber"], "lower")
        self.assertTrue(hb["url"].startswith("http"))
        # Actions carry the chamber from organizations.csv.
        self.assertTrue({a["chamber"] for a in hb["actions"]} >= {"lower", "upper"})
        # Every recorded vote, with every legislator's position.
        self.assertEqual(len(hb["votes"]), 6)
        v = hb["votes"][0]
        self.assertTrue(v["counts"])
        self.assertTrue(all(p["option"] for p in v["people"]))
        # Open States' positions do not always add up to its own tally: the
        # Wyoming House has 62 members and this vote lists 63 positions for
        # a 51-10-1 count. Kept as given and flagged (positions_ok), never fixed.
        self.assertEqual((len(v["people"]), sum(v["counts"].values())), (63, 62))

    def test_since_filters_on_actions(self):
        n, bills = ust.bills_from_bulk(self.raw, lambda b: True, since="2027-01-01")
        self.assertEqual((n, bills), (3, []))

    def test_classification(self):
        _, bills = ust.bills_from_bulk(self.raw, lambda b: True)
        got = {}
        for b in bills:
            b["state"] = "wy"
            got[b["identifier"]] = ust.classify(TAX, WL, b).issue_areas
        self.assertIn(1, got["HB 126"])
        self.assertIn(5, got["HB 113"])
        self.assertEqual(got["HB 114"], [])

    def test_bulk_read_stores_only_our_ground_with_every_position(self):
        conn = store()
        s = {"state": "wy", "session": "2026", "name": "2026 Regular Session",
             "classification": "primary", "start_date": "2026-02-09", "end_date": "2026-03-06",
             "zip_url": "https://data.openstates.org/csv/latest/WY_2026_csv_x.zip",
             "zip_updated": "2026-09-22T23:01:00+00:00"}
        ust.store_session_meta(conn, s, TODAY)
        client = FakeClient({"WY_2026": self.raw})
        tally = ust.Tally()
        self.assertTrue(ust.bulk_read(conn, client, TAX, WL, s, TODAY, tally, log=lambda *_: None))
        conn.row_factory = sqlite3.Row
        keys = {r["bill_key"] for r in conn.execute("SELECT bill_key FROM uss_bills")}
        self.assertEqual(keys, {"WY/2026/HB126", "WY/2026/HB113"})
        hb = conn.execute("SELECT * FROM uss_bills WHERE bill_key='WY/2026/HB126'").fetchone()
        self.assertTrue(hb["bill_id"].startswith("ocd-bill/"))
        self.assertIsNotNone(hb["law_at"])
        self.assertIsNotNone(hb["passed_lower_at"])
        self.assertIsNotNone(hb["passed_upper_at"])
        votes = conn.execute("SELECT COUNT(*) FROM uss_votes WHERE bill_id=?",
                             (hb["bill_id"],)).fetchone()[0]
        people = conn.execute("SELECT COUNT(*) FROM uss_vote_people vp JOIN uss_votes v "
                              "USING (vote_id) WHERE v.bill_id=?", (hb["bill_id"],)).fetchone()[0]
        self.assertEqual(votes, 6)
        self.assertEqual(people, 9 + 63 + 5 + 31 + 63 + 63)
        bad = conn.execute("SELECT COUNT(*) FROM uss_votes WHERE positions_ok=0").fetchone()[0]
        # The three House floor votes list 63 positions against a 62-member tally.
        self.assertEqual(bad, 3)
        sess = conn.execute("SELECT * FROM uss_sessions WHERE state='wy'").fetchone()
        self.assertEqual((sess["bills_read"], sess["bills_ours"], sess["read_via"]),
                         (3, 2, "bulk"))
        # The day before the file's stamp: the nightly export lags the
        # scrapers by about a day (Pennsylvania, 8 October 2026).
        self.assertEqual(sess["data_through"], "2026-09-21")
        # The bulk file is never archived (its URL and stamp are the provenance).
        self.assertEqual(client.archived, [])

    def test_a_refused_bulk_file_is_a_gap(self):
        conn = store()
        s = {"state": "wy", "session": "2026", "zip_url": "https://x/WY_2026.zip",
             "zip_updated": None}
        ok = ust.bulk_read(conn, FakeClient(), TAX, WL, s, TODAY, ust.Tally(),
                           log=lambda *_: None)
        self.assertFalse(ok)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed=?",
                                      (ust.FEED,)).fetchone()[0], 1)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.page = json.loads(fixture("api_bills_vt.json", "r"))

    def test_bill_from_api(self):
        b = ust.bill_from_api(self.page["results"][0])
        self.assertEqual((b["state"], b["session"], b["identifier"]), ("vt", "2025-2026", "H 951"))
        # The state's own status page, not the roll-call data endpoint listed first.
        self.assertIn("/bill/status/", b["url"])
        self.assertEqual(len(b["votes"]), 3)
        v = b["votes"][0]
        self.assertEqual(v["chamber"], "upper")
        self.assertEqual(v["counts"], {"yes": 7, "no": 23, "not voting": 0})
        self.assertEqual(len(v["people"]), 30)
        # Three of thirty senators came unlinked (White, Benson, Morley): their
        # names are kept, the person left NULL, never guessed.
        linked = [p for p in v["people"] if p["person_id"]]
        self.assertEqual(len(linked), 27)
        self.assertTrue(all(p["person_id"].startswith("ocd-person/") for p in linked))
        intro, latest, latest_at, lower, upper, law, veto = ust.stage_dates(b["actions"])
        self.assertEqual(law, "2026-05-29")

    def test_watchlist_by_key(self):
        b = ust.bill_from_api(self.page["results"][1])
        path = os.path.join(tempfile.mkdtemp(), "wl.yaml")
        with open(path, "w") as fh:
            fh.write('bills:\n  "VT/2025-2026/H930": {areas: [6], why: "test"}\n')
        res = filt.filter_item(TAX, WL, b["title"])
        self.assertEqual(res.issue_areas, [])
        uss.add_watch_areas(res, uss.bill_key(b["state"], b["session"], b["identifier"]), path)
        self.assertEqual(res.issue_areas, [6])
        self.assertIn("watch:VT/2025-2026/H930", res.watchlist_hits)

    def test_api_read_pages_and_stores(self):
        conn = store()

        class Api:
            used = 0

            def remaining(self):
                return 100

            def get(self, path, params, slug):
                self.params = params
                return dict(self_page, pagination={"max_page": 1, "total_items": 2})
        self_page = self.page
        api = Api()
        # Nothing here is on our ground, so nothing is stored...
        tally = ust.Tally()
        self.assertEqual(ust.api_read(conn, api, TAX, WL, "vt", "2026-10-01", TODAY, tally,
                                      log=lambda *_: None), "done")
        self.assertEqual((tally.read, tally.stored), (2, 0))
        self.assertEqual(api.params["action_since"], "2026-10-01")
        self.assertNotIn("updated_since", api.params)
        # ...but a bill already stored is updated, so its areas cannot go stale.
        conn.execute("INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, areas) "
                     "VALUES (?,?,?,?,?,?)", (self.page["results"][0]["id"], "VT/2025-2026/H951",
                                              "vt", "2025-2026", "H 951", "[1]"))
        tally = ust.Tally()
        ust.api_read(conn, api, TAX, WL, "vt", "2026-10-01", TODAY, tally, log=lambda *_: None)
        self.assertEqual(tally.stored, 1)
        conn.row_factory = sqlite3.Row
        r = conn.execute("SELECT * FROM uss_bills").fetchone()
        self.assertEqual(r["areas"], "[]")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM uss_votes").fetchone()[0], 3)

    def test_too_many_pages_falls_back(self):
        class Api:
            def remaining(self):
                return 100

            def get(self, path, params, slug):
                return {"pagination": {"max_page": 12, "total_items": 223}, "results": []}
        self.assertEqual(ust.api_read(store(), Api(), TAX, WL, "nj", "2026-10-01", TODAY,
                                      ust.Tally(), log=lambda *_: None), "too-big")


class RateLimitTests(unittest.TestCase):
    def make(self, answers, budget=10):
        calls = []
        sleeps = []

        class Client:
            def get_bytes(self, url, feed, slug, headers=None, **kw):
                calls.append((url, headers))
                a = answers.pop(0)
                if isinstance(a, Exception):
                    raise a
                return a

            def _archive(self, raw, feed, slug):
                pass
        clock = [0.0]

        def sleep(s):
            sleeps.append(s)
            clock[0] += s
        api = ust.OpenStates(Client(), "k", budget=budget, sleep=sleep, clock=lambda: clock[0],
                             log=lambda *_: None)
        return api, calls, sleeps

    def test_key_only_in_header_and_requests_spaced(self):
        api, calls, sleeps = self.make([b'{"results": []}', b'{"results": []}'])
        api.get("/bills", {"jurisdiction": "vt"}, "a")
        api.get("/bills", {"jurisdiction": "vt"}, "b")
        for url, headers in calls:
            self.assertNotIn("apikey", url.lower())
            self.assertEqual(headers, {"X-API-KEY": "k"})
        self.assertEqual(sleeps, [ust.API_SPACING_S])
        self.assertLess(60.0 / ust.API_SPACING_S, 10)   # under the tier's 10 a minute

    def test_minute_limit_waits_once(self):
        api, calls, sleeps = self.make([refusal(429, '{"detail":"exceeded limit of 10/min: 11"}'),
                                        b'{"ok": 1}'])
        self.assertEqual(api.get("/bills", {}, "a"), {"ok": 1})
        self.assertIn(61, sleeps)

    def test_day_limit_ends_the_api(self):
        api, _, _ = self.make([refusal(429, '{"detail":"exceeded limit of 250/day: 251"}')])
        with self.assertRaises(ust.ApiSpent):
            api.get("/bills", {}, "a")
        self.assertEqual(api.remaining(), 0)
        self.assertIn("250/day", api.refused)

    def test_a_timeout_is_tried_once_more(self):
        timeout = FetchError("u", ust.FEED, "s", 1, TimeoutError("The read operation timed out"))
        api, calls, _ = self.make([timeout, b'{"ok": 1}'])
        self.assertEqual(api.get("/bills", {}, "a"), {"ok": 1})
        self.assertEqual(len(calls), 2)

    def test_budget_is_a_hard_cap(self):
        api, calls, _ = self.make([b"{}"] * 5, budget=2)
        api.get("/x", {}, "a")
        api.get("/x", {}, "b")
        with self.assertRaises(ust.ApiSpent):
            api.get("/x", {}, "c")
        self.assertEqual(len(calls), 2)


class LedgerTests(unittest.TestCase):
    """No paid tier: the key's 250 a day is guarded across runs by the store."""

    def api(self, conn, budget=10, cap=3, answers=None):
        calls = []

        class Client:
            def get_bytes(self, url, feed, slug, headers=None, **kw):
                calls.append(url)
                a = (answers or [b"{}"]).pop(0) if answers else b"{}"
                if isinstance(a, Exception):
                    raise a
                return a

            def _archive(self, raw, feed, slug):
                pass
        ledger = ust.Ledger(conn, cap=cap, day=lambda: TODAY)
        return ust.OpenStates(Client(), "k", budget=budget, sleep=lambda s: None,
                              clock=lambda: 0.0, log=lambda *_: None, ledger=ledger), calls

    def test_two_runs_in_a_day_cannot_overrun_the_cap(self):
        conn = store()
        first, c1 = self.api(conn)
        first.get("/x", {}, "a")
        first.get("/x", {}, "b")
        second, c2 = self.api(conn)
        self.assertEqual(second.remaining(), 1)
        second.get("/x", {}, "c")
        with self.assertRaises(ust.ApiSpent) as ctx:
            second.get("/x", {}, "d")
        self.assertIn("ledger", str(ctx.exception))
        self.assertEqual(len(c1) + len(c2), 3)
        self.assertEqual(ust.Ledger(conn, day=lambda: TODAY).spent(), 3)
        # Another day starts afresh.
        self.assertEqual(ust.Ledger(conn, cap=3, day=lambda: "2026-10-10").left(), 3)

    def test_a_refused_request_still_counts(self):
        conn = store()
        api, _ = self.api(conn, answers=[refusal(404, "nf")])
        with self.assertRaises(FetchError):
            api.get("/x", {}, "a")
        self.assertEqual(ust.Ledger(conn, day=lambda: TODAY).spent(), 1)

    def test_a_day_refusal_closes_the_day_for_every_run(self):
        conn = store()
        api, _ = self.api(conn, cap=225,
                          answers=[refusal(429, '{"detail":"exceeded limit of 250/day: 251"}')])
        with self.assertRaises(ust.ApiSpent):
            api.get("/x", {}, "a")
        later, _ = self.api(conn, cap=225)
        self.assertEqual(later.remaining(), 0)

    def test_zip_through_is_the_day_before_the_stamp(self):
        self.assertEqual(ust.zip_through("2026-10-08T23:18:09.003648+00:00"), "2026-10-07")
        self.assertIsNone(ust.zip_through(None))


class RouteTests(unittest.TestCase):
    """Bulk files carry the week; the API only tops up the last day."""

    SESSION = {"state": "wy", "session": "2026", "name": "2026", "classification": "primary",
               "start_date": "2026-02-09", "end_date": "2026-03-06",
               "zip_url": "https://data.openstates.org/csv/latest/WY_2026_csv_x.zip",
               "zip_updated": "2026-09-22T23:19:36+00:00"}

    def args(self, **kw):
        return ust.argparse.Namespace(**dict({"full": False, "since": None, "max_pages": 10}, **kw))

    def test_unread_whole_then_unchanged_not_downloaded_then_changed_since(self):
        conn = store()
        s = dict(self.SESSION)
        ust.store_session_meta(conn, s, TODAY)
        client = FakeClient({"WY_2026": fixture("WY_2026_csv_trimmed.zip")})
        tally = ust.Tally()
        quiet = lambda *_: None  # noqa: E731
        ust.collect_state(conn, client, TAX, WL, "wy", [s], TODAY, self.args(), tally, log=quiet)
        self.assertEqual(len(client.asked), 1)
        self.assertEqual(tally.read, 3)
        # The same stamp: Open States wrote no new file, so nothing is fetched.
        ust.collect_state(conn, client, TAX, WL, "wy", [s], TODAY, self.args(), tally, log=quiet)
        self.assertEqual(len(client.asked), 1)
        # A newer file (a new name each export): read for bills with an action
        # since data_through less the overlap. The fixture's bills all acted
        # in spring, so none is re-read.
        s2 = dict(s, zip_url=s["zip_url"].replace("_x", "_y"),
                  zip_updated="2026-10-08T23:19:36+00:00")
        ust.store_session_meta(conn, s2, TODAY)
        tally = ust.Tally()
        ust.collect_state(conn, client, TAX, WL, "wy", [s2], TODAY, self.args(), tally, log=quiet)
        self.assertEqual(len(client.asked), 2)
        self.assertIn("_y", client.asked[-1][0])
        self.assertEqual(tally.stored, 0)
        self.assertEqual(ust.read_state(conn, "wy", "2026")[:2],
                         ("2026-10-08T23:19:36+00:00", "2026-10-07"))
        # No keyed request anywhere in the bulk route.
        self.assertTrue(all(h is None for _, h in client.asked))

    def _vt_store(self):
        page = json.loads(fixture("api_bills_vt.json", "r"))
        conn = store()
        conn.execute("INSERT INTO uss_sessions (state, session, zip_url, zip_updated, "
                     "read_zip_updated, data_through, read_at) VALUES "
                     "('vt','2025-2026','u','2026-10-06T23:00:00+00:00',"
                     "'2026-10-06T23:00:00+00:00','2026-10-05','2026-10-07')")
        conn.execute("INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, areas, "
                     "latest_action_at, tier) VALUES (?,?,?,?,?,?,?,?)",
                     (page["results"][0]["id"], "VT/2025-2026/H951", "vt", "2025-2026", "H 951",
                      "[1]", "2026-10-01", 1))
        # Off our ground, and on it but long quiet: neither is asked for.
        conn.execute("INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, areas, "
                     "latest_action_at) VALUES ('ocd-bill/x','VT/2025-2026/H1','vt','2025-2026',"
                     "'H 1','[11]','2026-10-01')")
        conn.execute("INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, areas, "
                     "latest_action_at) VALUES ('ocd-bill/y','VT/2025-2026/H2','vt','2025-2026',"
                     "'H 2','[5]','2026-05-01')")
        conn.commit()
        return conn, page

    def test_topup_asks_only_live_bills_on_our_ground_by_identifier(self):
        conn, page = self._vt_store()
        sessions = {"vt": [{"state": "vt", "session": "2025-2026", "name": "x",
                            "classification": "primary", "start_date": "2025-01-08",
                            "end_date": "2026-05-30", "zip_url": "u",
                            "zip_updated": "2026-10-06T23:00:00+00:00"}]}
        plan = ust.topup_plan(conn, sessions, ["vt"], TODAY)
        self.assertEqual(plan, [("vt", "2025-2026", "2026-10-05", ["H 951"])])

        class Api:
            used = 0

            def remaining(self):
                return 10

            def get(self, path, params, slug):
                self.used += 1
                self.params = params
                return {"pagination": {"max_page": 1}, "results": [page["results"][0]]}
        api = Api()
        tally = ust.Tally()
        n, got, done, left = ust.topup(conn, api, TAX, WL, plan, TODAY, tally, log=lambda *_: None)
        self.assertEqual((n, got, done, left), (1, 1, ["vt"], []))
        self.assertEqual(api.params["identifier"], ["H 951"])
        self.assertEqual(api.params["session"], "2025-2026")
        self.assertEqual(api.params["action_since"], "2026-10-05")
        self.assertNotIn("updated_since", api.params)
        conn.row_factory = sqlite3.Row
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM uss_votes").fetchone()[0], 3)

    def test_topup_batches_twenty_and_stops_when_spent(self):
        conn = store()
        ids = ["HB {0}".format(i) for i in range(45)]

        class Api:
            used = 0
            batches = []

            def remaining(self):
                return 2 - self.used

            def get(self, path, params, slug):
                if not self.remaining():
                    raise ust.ApiSpent("spent")
                self.used += 1
                self.batches.append(len(params["identifier"]))
                return {"results": []}
        api = Api()
        n, got, done, left = ust.topup(conn, api, TAX, WL, [("tx", "89R", "2026-10-05", ids)],
                                       TODAY, ust.Tally(), log=lambda *_: None)
        self.assertEqual(api.batches, [20, 20])
        self.assertEqual((n, done, left), (2, [], ["tx"]))

    def test_salience_orders_the_plan(self):
        conn = store()
        for st, n in (("ca", 1), ("tx", 3)):
            conn.execute("INSERT INTO uss_sessions (state, session, data_through, read_at) "
                         "VALUES (?,?,?,?)", (st, "s", "2026-10-07", "2026-10-08"))
            for i in range(n):
                conn.execute("INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, "
                             "areas, latest_action_at) VALUES (?,?,?,?,?,?,?)",
                             ("ocd-bill/{0}{1}".format(st, i), "k", st, "s", "B {0}".format(i),
                              "[1]", "2026-10-06"))
        # Florida's file is a week behind (an export missed): it goes first.
        conn.execute("INSERT INTO uss_sessions (state, session, data_through, read_at) "
                     "VALUES ('fl','s','2026-10-01','2026-10-08')")
        conn.execute("INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, areas, "
                     "latest_action_at) VALUES ('ocd-bill/fl','k','fl','s','B 1','[1]','2026-09-30')")
        sess = lambda st: [{"state": st, "session": "s", "name": "s", "classification": "",  # noqa: E731
                            "start_date": "2026-01-01", "end_date": None, "zip_url": "u",
                            "zip_updated": None}]
        plan = ust.topup_plan(conn, {st: sess(st) for st in ("ca", "tx", "fl")},
                              ["ca", "tx", "fl"], TODAY)
        self.assertEqual([p[0] for p in plan], ["fl", "tx", "ca"])


class SessionTests(unittest.TestCase):
    def sessions(self, name):
        for j in json.loads(fixture("jurisdictions.json", "r"))["results"]:
            if j["name"] == name:
                return ust.session_rows(j)

    def current(self, name):
        return [s["session"] for s in ust.current_sessions(self.sessions(name), TODAY)]

    def test_mississippi_2026_despite_its_2025_dates(self):
        # Open States dates Mississippi's 2026 session January 2025; the bulk
        # file regenerated yesterday is what marks it current.
        self.assertIn("2026", self.current("Mississippi"))

    def test_virginia_prefiling_session_is_read(self):
        self.assertIn("2027", self.current("Virginia"))

    def test_texas_odd_year_regular_session(self):
        self.assertIn("89R", self.current("Texas"))
        self.assertNotIn("88R", self.current("Texas"))

    def test_session_rows_carry_the_bulk_file(self):
        rows = {s["session"]: s for s in self.sessions("Texas")}
        self.assertTrue(rows["89R"]["zip_url"].endswith(".zip"))
        self.assertTrue(rows["89R"]["zip_updated"])


class RunTests(unittest.TestCase):
    def test_no_key_is_one_gap_and_a_skip(self):
        path = os.path.join(tempfile.mkdtemp(), "s.db")
        with mock.patch.object(ust, "openstates_key", return_value=None):
            self.assertEqual(ust.main(["--db", path, "--states", "vt"]), 0)
        conn = db.connect(path)
        rows = conn.execute("SELECT detail FROM gaps WHERE feed=?", (ust.FEED,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertIn("no openstates_api_key", rows[0][0])

    def test_people(self):
        conn = store()
        client = FakeClient({"people/current/vt.csv": fixture("people_vt.csv")})
        self.assertEqual(ust.pull_people(conn, client, "vt", TODAY), 4)
        conn.row_factory = sqlite3.Row
        r = conn.execute("SELECT * FROM uss_people LIMIT 1").fetchone()
        self.assertTrue(r["person_id"].startswith("ocd-person/"))
        self.assertEqual(r["state"], "vt")

    def test_rotation_puts_the_unread_first(self):
        conn = store()
        conn.execute("INSERT INTO uss_sessions (state, session, read_at) VALUES ('tx','89R','2026-10-02')")
        conn.execute("INSERT INTO uss_sessions (state, session, read_at) VALUES ('fl','2026','2026-09-25')")
        self.assertEqual(ust.order_states(conn, ["tx", "fl", "vt"]), ["vt", "fl", "tx"])


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        s = {"state": "wy", "session": "2026", "name": "2026", "classification": "primary",
             "start_date": "2026-02-09", "end_date": "2026-03-06",
             "zip_url": "https://x/WY_2026.zip", "zip_updated": "2026-09-22T00:00:00+00:00"}
        ust.store_session_meta(self.conn, s, TODAY)
        ust.bulk_read(self.conn, FakeClient({"WY_2026": fixture("WY_2026_csv_trimmed.zip")}),
                      TAX, WL, s, TODAY, ust.Tally(), log=lambda *_: None)
        self.conn.row_factory = sqlite3.Row
        self.law = self.conn.execute("SELECT law_at FROM uss_bills WHERE bill_key='WY/2026/HB126'"
                                     ).fetchone()[0]

    def test_week_with_a_law(self):
        day = datetime.date.fromisoformat(self.law)
        today = (day + datetime.timedelta(days=2)).isoformat()
        since = (day - datetime.timedelta(days=5)).isoformat()
        text = "\n".join(us_monitor.states_section(self.conn, since, today,
                                                   us_monitor.area_names()))
        self.assertIn("### Wyoming", text)
        self.assertIn("Signed into law {0}".format(self.law), text)
        self.assertIn("[WY HB 126](", text)
        self.assertNotIn("—", text)
        tops = us_monitor.states_tops(self.conn, since, today)
        self.assertIn("signed into law this week** (WY)", tops[0])

    def test_quiet_week_says_so_with_counts(self):
        text = "\n".join(us_monitor.states_section(self.conn, "2026-10-02", TODAY,
                                                   us_monitor.area_names()))
        self.assertIn("Nothing on our ground moved in the states this week", text)
        self.assertIn("1 of 50 legislatures read", text)

    def test_chamber_names(self):
        self.assertEqual(us_monitor.chamber_name("ca", "lower"), "Assembly")
        self.assertEqual(us_monitor.chamber_name("va", "lower"), "House of Delegates")
        self.assertEqual(us_monitor.chamber_name("tx", "lower"), "House")
        self.assertEqual(us_monitor.chamber_name("ne", "legislature"), "Legislature")

    def test_never_read(self):
        text = "\n".join(us_monitor.states_section(store(), "2026-10-02", TODAY, {}))
        self.assertIn("Not read yet", text)


class JudgeTests(unittest.TestCase):
    def test_only_recent_state_bills_are_queued(self):
        from tools import us_triage
        conn = store()
        today = datetime.date.today()
        old = (today - datetime.timedelta(days=200)).isoformat()
        new = (today - datetime.timedelta(days=3)).isoformat()
        for i, when in enumerate((old, new)):
            conn.execute("INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, "
                         "title, areas, latest_action_at) VALUES (?,?,?,?,?,?,?,?)",
                         ("ocd-bill/{0}".format(i), "TX/89R/HB{0}".format(i), "tx", "89R",
                          "HB {0}".format(i), "Relating to abortion.", "[1]", when))
        conn.commit()
        ids = [i.id for i in us_triage.pending(conn) if i.id.startswith("uss_bills:")]
        self.assertEqual(ids, ["uss_bills:ocd-bill/1"])
        self.assertEqual(us_triage.rescore(conn, "uss_bills:ocd-bill/0"), 1)


if __name__ == "__main__":
    unittest.main()
