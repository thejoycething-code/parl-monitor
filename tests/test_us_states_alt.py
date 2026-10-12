"""Alternative sources for the fifty states (13 October 2026):
tools/us_states_legiscan.py, tools/us_states_direct.py and the merge layer
in tools/us_states.py (merge_foreign, supersede_foreign, the smarter top-up).

No network. Fixtures in tests/fixtures/us_states/:
  * ks_bill_status_trimmed.json: the Kansas KLISS bill_status reply of 13
    October 2026 (revision 877182) cut to four bills: HB 2010 (abortion,
    died in committee), SB 244 and HB 2635 (vetoed, veto overridden), HB
    2347 (signed). Real.
  * ca_pubinfo_Mon_trimmed.zip: California's pubinfo_Mon.zip of 5 October
    2026 cut to AB 1999 and AB 1126 (BILL_TBL and BILL_HISTORY_TBL rows,
    real). The recess files carry no versions or votes, so the
    BILL_VERSION_TBL subjects (AB 1999's is NOT its real title), the
    BILL_MOTION_TBL row and the vote rows are CONSTRUCTED in the real
    column layout (pubinfo_load.zip, capublic.sql).
  * tx_89R_HB229.xml: the Texas Legislative Council's FTP file for 89(R) HB
    229, real. tx_listing.txt: an FTP listing in the server's format.
  * legiscan_constructed.json: LegiScan replies CONSTRUCTED from the API
    manual's examples (revision 20250317): we hold no key, so none was read.
"""

import json
import os
import unittest

from src import db, drain, filter as filt, us_states_store as uss
from tools import us_monitor
from tools import us_states as ust
from tools import us_states_direct as usd
from tools import us_states_legiscan as usl

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "us_states")
TODAY = "2026-10-13"
TAX = filt.load_taxonomy(ust.TAXONOMY)
WL = ust.empty_watchlist()


def fixture(name, mode="rb"):
    with open(os.path.join(FIX, name), mode) as fh:
        return fh.read()


def store():
    return db.init_db(db.connect(":memory:"))


def q(conn, sql, params=()):
    return [tuple(r) for r in conn.execute(sql, params).fetchall()]


def session_row(conn, st, session, start, end=None, name=None, classification=""):
    conn.execute("INSERT INTO uss_sessions (state, session, name, classification, start_date, "
                 "end_date, first_seen, last_seen, read_at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (st, session, name or session, classification, start, end, TODAY, TODAY, TODAY))


def os_bill(st, session, ident, title, actions, votes=(), bill_id=None):
    return {"id": bill_id or "ocd-bill/{0}-{1}".format(st, ident.replace(" ", "")),
            "state": st, "session": session, "identifier": ident, "title": title,
            "classification": ["bill"], "subjects": [], "abstracts": [], "other_titles": [],
            "chamber": "lower", "url": None, "actions": actions, "sponsors": [],
            "votes": list(votes)}


def act(date, desc, cls=(), chamber="lower", ord_=0):
    return {"date": date, "description": desc, "classification": list(cls), "chamber": chamber,
            "ord": ord_}


class FakeClient:
    def __init__(self, files):
        self.files = files
        self.asked = []
        self.archived = []

    def _find(self, url):
        self.asked.append(url)
        for frag, data in self.files.items():
            if frag in url:
                return data
        raise AssertionError("unexpected URL " + url)

    def get_bytes(self, url, feed, slug, **kw):
        data = self._find(url)
        return data if isinstance(data, bytes) else data.encode("utf-8")

    def get_text(self, url, feed, slug, **kw):
        data = self._find(url)
        return data.decode("utf-8") if isinstance(data, bytes) else data

    def _archive(self, raw, feed, slug):
        self.archived.append(slug)


class StoreHelpers(unittest.TestCase):

    def test_norm_ident_and_key(self):
        self.assertEqual(uss.norm_ident("HB 229"), "HB229")
        self.assertEqual(uss.norm_ident("A01234"), "A1234")
        self.assertEqual(uss.norm_ident("HB 1000"), "HB1000")
        self.assertEqual(uss.norm_key("tx", "89R", "HB 0229"), "TX/89R/HB229")

    def test_session_for(self):
        conn = store()
        session_row(conn, "ks", "2025-2026", "2025-01-13")
        session_row(conn, "ks", "2024S", "2024-06-18", name="2024 Special Session",
                    classification="special")
        session_row(conn, "ca", "20252026", "2024-12-02")
        session_row(conn, "tx", "89R", "2025-01-14")
        session_row(conn, "tx", "891", "2025-07-21", name="89th Legislature, 1st Called Session")
        self.assertEqual(uss.session_for(conn, "ks", 2025, 2026), "2025-2026")
        self.assertEqual(uss.session_for(conn, "ks", 2024, 2024, special=True), "2024S")
        self.assertEqual(uss.session_for(conn, "ca", 2025, 2026), "20252026")
        self.assertEqual(uss.session_for(conn, "tx", 2025, 2025), "89R")
        self.assertIsNone(uss.session_for(conn, "ny", 2025, 2026))

    def test_new_tables_declared(self):
        for t in ("uss_bill_sources", "uss_source_ledger"):
            self.assertIn(t, db.TABLES)
            self.assertIn(t, uss.TABLES)


class Merge(unittest.TestCase):

    def setUp(self):
        self.conn = store()
        session_row(self.conn, "nj", "222", "2026-01-13")
        b = os_bill("nj", "222", "A 123", "Requires parental consent for minors' gender "
                    "transition procedures.",
                    [act("2026-01-13", "Introduced, Referred to Assembly Health Committee",
                         ("introduction",))])
        self.res = ust.classify(TAX, WL, b)
        ust.store_bill(self.conn, b, self.res, TODAY)
        self.os_id = b["id"]

    def foreign(self, ident="A123"):
        return {"id": None, "state": "nj", "session": "222", "identifier": ident,
                "title": "Requires parental consent for minors' gender transition procedures.",
                "classification": ["bill"], "subjects": [], "abstracts": [], "other_titles": [],
                "chamber": "lower", "url": "https://example.org/A123",
                "actions": [act("2026-01-13", "Introduced,  referred to Assembly Health Committee"),
                            act("2026-10-06", "Passed by the Assembly (52-20-0)", ("passage",))],
                "sponsors": [], "votes": [{
                    "id": "legiscan-rc:1", "date": "2026-10-06", "motion": "Third Reading",
                    "motion_classification": [], "result": "pass", "chamber": "lower",
                    "counts": {"yes": 52, "no": 20}, "url": None, "people": []}]}

    def test_merge_into_open_states_row(self):
        what, bid, _ = ust.merge_foreign(self.conn, TAX, WL, "legiscan", "2000001",
                                         self.foreign(), TODAY, change_hash="h")
        self.assertEqual((what, bid), ("merged", self.os_id))
        rows = self.conn.execute("SELECT date, description FROM uss_actions WHERE bill_id=? "
                                 "ORDER BY ord", (self.os_id,)).fetchall()
        # The introduction is not repeated (same day, same words); the
        # passage is appended and the stage dates follow it.
        self.assertEqual(len(rows), 2)
        r = q(self.conn, "SELECT latest_action_at, passed_lower_at FROM uss_bills "
              "WHERE bill_id=?", (self.os_id,))
        self.assertEqual(r, [("2026-10-06", "2026-10-06")])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM uss_bills").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM uss_votes").fetchone()[0], 1)
        self.assertTrue(ust.source_unchanged(self.conn, "legiscan", "2000001", "h"))
        self.assertFalse(ust.source_unchanged(self.conn, "legiscan", "2000001", "h2"))

    def test_new_bill_stored_then_superseded(self):
        f = self.foreign("A 456")
        what, bid, _ = ust.merge_foreign(self.conn, TAX, WL, "legiscan", "2000009", f, TODAY,
                                         change_hash="h")
        self.assertEqual((what, bid), ("stored", "legiscan:2000009"))
        # Open States' own file catches up: the LegiScan row goes, and New
        # Jersey's vote (Open States gives NJ none) is kept on its row.
        b = os_bill("nj", "222", "A 456", f["title"], f["actions"])
        ust.store_bill(self.conn, b, ust.classify(TAX, WL, b), TODAY)
        ids = [r[0] for r in self.conn.execute("SELECT bill_id FROM uss_bills ORDER BY bill_id")]
        self.assertNotIn("legiscan:2000009", ids)
        self.assertEqual(self.conn.execute("SELECT bill_id FROM uss_votes WHERE vote_id="
                                           "'legiscan-rc:1'").fetchone()[0], b["id"])
        self.assertEqual(self.conn.execute("SELECT bill_id FROM uss_bill_sources WHERE "
                                           "source_id='2000009'").fetchone()[0], b["id"])

    def test_superseded_votes_dropped_where_open_states_has_them(self):
        session_row(self.conn, "pa", "2025-2026", "2025-01-07")
        f = dict(self.foreign("HB 9"), state="pa", session="2025-2026")
        ust.merge_foreign(self.conn, TAX, WL, "legiscan", "77", f, TODAY)
        b = os_bill("pa", "2025-2026", "HB 9", f["title"], f["actions"])
        ust.store_bill(self.conn, b, ust.classify(TAX, WL, b), TODAY)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM uss_votes").fetchone()[0], 0)

    def test_off_ground_unknown_bill_skipped(self):
        f = dict(self.foreign("A 999"), title="Concerns motor vehicle registration fees.")
        what, bid, _ = ust.merge_foreign(self.conn, TAX, WL, "legiscan", "5", f, TODAY)
        self.assertEqual((what, bid), ("skipped", None))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM uss_bills").fetchone()[0], 1)


class SmarterTopup(unittest.TestCase):

    def test_order_and_cover(self):
        conn = store()
        for st in ("nj", "ks"):
            conn.execute("INSERT INTO uss_sessions (state, session, start_date, zip_url, "
                         "zip_updated, read_zip_updated, read_via, data_through, read_at, "
                         "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (st, "S", "2026-01-01", "u", "2026-10-11", "2026-10-11", "bulk",
                          "2026-10-10", TODAY, TODAY, TODAY))
        rows = [("nj", "A 1", 2, "[]", "2026-10-12"), ("nj", "A 2", 1, "[]", "2026-10-01"),
                ("nj", "A 3", 2, '["watch:NJ/S/A3"]', "2026-09-30"),
                ("ks", "HB 1", 1, "[]", "2026-10-12")]
        for st, ident, tier, terms, at in rows:
            conn.execute("INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, "
                         "areas, tier, matched_terms, latest_action_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         ("ocd-bill/" + st + ident, st + ident, st, "S", ident, "[1]", tier,
                          terms, at))
        self.assertEqual(ust.live_bills(conn, "nj", "S", TODAY), ["A 3", "A 2", "A 1"])
        by_state = {st: [{"state": st, "session": "S", "name": "S", "classification": "",
                          "start_date": "2026-01-01", "end_date": None, "zip_url": "u",
                          "zip_updated": "2026-10-11"}] for st in ("nj", "ks")}
        plan = ust.topup_plan(conn, by_state, ["nj", "ks"], TODAY, use_cover=True)
        self.assertEqual({p[0] for p in plan}, {"nj", "ks"})
        # Kansas read by its own feed this week, LegiScan active: Kansas is
        # left out and New Jersey keeps only watched and tier-1 bills.
        conn.execute("INSERT INTO uss_bill_sources (source, source_id, state, fetched_at) "
                     "VALUES ('ks-kliss', 'x', 'ks', ?), ('legiscan', 'y', 'nj', ?)", (TODAY, TODAY))
        plan = ust.topup_plan(conn, by_state, ["nj", "ks"], TODAY, use_cover=True)
        self.assertEqual([(p[0], p[3]) for p in plan], [("nj", ["A 3", "A 2"])])
        plan = ust.topup_plan(conn, by_state, ["nj", "ks"], TODAY, use_cover=False)
        self.assertEqual({p[0] for p in plan}, {"nj", "ks"})


class Kansas(unittest.TestCase):

    def run_ks(self, conn):
        client = FakeClient({"kslegislature.gov": fixture("ks_bill_status_trimmed.json")})
        return usd.read_kansas(conn, client, TAX, WL, TODAY, "2026-09-13")

    def test_read(self):
        conn = store()
        session_row(conn, "ks", "2025-2026", "2025-01-13")
        c = self.run_ks(conn)
        self.assertEqual(c.read, 4)
        keys = {r[0] for r in conn.execute("SELECT bill_key FROM uss_bills")}
        self.assertIn("KS/2025-2026/HB2010", keys)
        self.assertIn("KS/2025-2026/HB2635", keys)
        r = conn.execute("SELECT vetoed_at, passed_lower_at, passed_upper_at, url, sponsor "
                         "FROM uss_bills WHERE bill_key='KS/2025-2026/HB2635'").fetchone()
        self.assertTrue(r[0] and r[1] and r[2])
        self.assertEqual(r[3], "https://www.kslegislature.gov/li/b2025_26/measures/hb2635/")
        # Final-action tallies become vote totals (Open States has no Kansas votes).
        v = q(conn, "SELECT yes, no, chamber, positions FROM uss_votes WHERE bill_id="
              "'ks-kliss:2025-2026/HB2635' AND motion LIKE 'Final Action%' ORDER BY yes")
        self.assertEqual(v, [(31, 9, "upper", 0), (87, 37, "lower", 0)])
        # A second run with the same revision reads nothing.
        c2 = self.run_ks(conn)
        self.assertIn("unchanged", c2.note)
        self.assertEqual(c2.changed, 0)


class California(unittest.TestCase):

    def test_dat_rows(self):
        rows = usd.dat_rows("`a`\t1\tNULL\t`tab\there`\n`b`\t2\t`x`\t``\n")
        self.assertEqual(rows, [["a", "1", None, "tab\there"], ["b", "2", "x", ""]])

    def test_index(self):
        page = ('<a href="pubinfo_Mon.zip">pubinfo_Mon.zip</a></td><td align="right">'
                '2026-10-05 21:20  </td><td align="right">152K</td>'
                '<a href="pubinfo_daily_Mon.zip">x</a></td><td>2026-10-12 04:23</td>')
        self.assertEqual(usd.ca_index(page), {"pubinfo_Mon.zip": "2026-10-05 21:20"})

    def test_bills_and_merge(self):
        bills = usd.ca_bills(fixture("ca_pubinfo_Mon_trimmed.zip"))
        ab = bills["202520260AB1999"]
        self.assertEqual(ab["identifier"], "AB 1999")
        self.assertEqual(ab["title"], "Abortion: reproductive health care services.")
        self.assertEqual(len(ab["votes"]), 1)            # the committee vote is not a floor vote
        v = list(ab["votes"].values())[0]
        self.assertEqual((v["chamber"], v["counts"]["yes"], len(v["people"])), ("lower", 3, 5))
        signed = [a for a in ab["actions"] if "executive-signature" in a["classification"]]
        self.assertEqual(signed[0]["date"], "2026-09-14")
        conn = store()
        page = '<a href="pubinfo_Mon.zip">pubinfo_Mon.zip</a></td><td>2026-10-12 21:20</td>'
        client = FakeClient({"pubinfo_Mon.zip": fixture("ca_pubinfo_Mon_trimmed.zip"),
                             "downloads.leginfo": page})
        c = usd.read_california(conn, client, TAX, WL, TODAY)
        self.assertEqual(c.result["stored"], 1)        # AB 1999; AB 1126 is off our ground
        r = q(conn, "SELECT bill_key, law_at, sponsors FROM uss_bills")
        self.assertEqual(r[0][0], "CA/20252026/AB1999")
        self.assertEqual(r[0][1], "2026-09-14")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM uss_vote_people").fetchone()[0], 5)
        # The file is not read twice.
        c2 = usd.read_california(conn, client, TAX, WL, TODAY)
        self.assertEqual(c2.read, 0)


class Texas(unittest.TestCase):

    def test_listing(self):
        got = usd.ftp_listing(fixture("tx_listing.txt", "r"))
        self.assertEqual(got[0], ("HB00001_HB00099", True, "2025-03-31 14:00"))
        self.assertEqual(got[3], ("HB 229.xml", False, "2025-06-21 02:00"))

    def test_bill(self):
        b = usd.tx_bill(fixture("tx_89R_HB229.xml"), "89R")
        self.assertEqual(b["identifier"], "HB 229")
        self.assertIn("biological sex", b["title"])
        self.assertEqual(b["sponsors"][0]["name"], "Troxclair")
        intro, _l, _la, lower, upper, law, veto = ust.stage_dates(b["actions"])
        self.assertEqual((intro, lower, upper, law, veto),
                         ("2024-11-12", "2025-05-12", "2025-05-28", "2025-06-20", None))
        res = ust.classify(TAX, WL, b)
        self.assertTrue(res.issue_areas)

    def test_read_merges_into_open_states_row(self):
        conn = store()
        session_row(conn, "tx", "89R", "2025-01-14")
        b = os_bill("tx", "89R", "HB 229", "Relating to biological sex.",
                    [act("2024-11-12", "Filed", ("introduction",))])
        ust.store_bill(conn, b, ust.classify(TAX, WL, b), TODAY)
        top = "\r\n".join(["09-18-10  12:25PM       <DIR>          89R"])
        types = "05-05-25  09:00PM       <DIR>          house_bills"
        ranges = "03-05-25  06:00PM       <DIR>          HB00200_HB00299"
        files = fixture("tx_listing.txt", "r")

        class TxClient(FakeClient):
            def get_text(self, url, feed, slug, **kw):
                self.asked.append(url)
                if url.endswith("/bills/"):
                    return top
                if url.endswith("/house_bills/"):
                    return ranges
                if url.endswith("/HB00200_HB00299/"):
                    return files
                if url.endswith("/billhistory/" + url.rsplit("/billhistory/", 1)[-1]) and \
                        url.rstrip("/").endswith(("bills", "resolutions")):
                    raise usd.FetchError(url, "f", "s", 1, OSError("550"))
                return types
        client = TxClient({"HB%20229.xml": fixture("tx_89R_HB229.xml"),
                           "HB%20201.xml": fixture("tx_89R_HB229.xml").replace(b"HB 229", b"HB 201")
                           .replace(b"biological sex", b"railroad crossings")})
        c = usd.read_texas(conn, client, TAX, WL, TODAY, "2025-06-01", drain.Budget(60))
        # Only files written since 1 June: HB 229 (stored, merged first) and
        # HB 201 (a new number, read for its caption).
        fetched = [u for u in client.asked if u.endswith(".xml")]
        self.assertEqual(fetched[0].rsplit("/", 1)[-1], "HB%20229.xml")
        self.assertEqual(len(fetched), 2)
        self.assertEqual(c.result["merged"], 1)
        r = q(conn, "SELECT law_at, passed_upper_at FROM uss_bills WHERE bill_id=?", (b["id"],))
        self.assertEqual(r, [("2025-06-20", "2025-05-28")])


class LegiScan(unittest.TestCase):

    def client(self):
        fx = json.loads(fixture("legiscan_constructed.json"))

        class LsClient(FakeClient):
            def get_bytes(self, url, feed, slug, headers=None, **kw):
                assert headers, "a keyed URL must take HttpClient's unarchived keyed path"
                self.asked.append(url)
                from urllib.parse import parse_qs, urlsplit
                q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
                name = q["op"] + ("-" + q["id"] if "id" in q else "")
                return json.dumps(fx[name]).encode()
        return LsClient({})

    def test_skips_without_key(self):
        with unittest.mock.patch.object(usl, "legiscan_key", return_value=None):
            self.assertEqual(usl.main(["--db", ":memory:"]), 0)

    def test_collect(self):
        conn = store()
        session_row(conn, "ca", "20252026", "2024-12-02")
        session_row(conn, "nj", "222", "2026-01-13")
        client = self.client()
        api = usl.LegiScan(client, "SECRETKEY", ust.SourceLedger(conn, "legiscan", 100))
        n = usl.collect(conn, api, TAX, WL, ["ca", "nj", "tx"], TODAY, drain.Budget(60),
                        log=lambda *a: None)
        # Texas 89R is adjourned sine die in 2025: not read. California
        # 2021-2022 is 'prior'. California AB 2 is off our ground; SB 10 has
        # not moved in the last 30 days.
        self.assertEqual(n["sessions"], 2)
        self.assertEqual(n["fetched"], 2)
        self.assertEqual(n["stored"], 2)
        keys = {r[0] for r in conn.execute("SELECT bill_key FROM uss_bills")}
        self.assertEqual(keys, {"CA/20252026/AB1999", "NJ/222/A123"})
        ca = q(conn, "SELECT law_at, passed_lower_at, passed_upper_at FROM uss_bills WHERE "
               "bill_key='CA/20252026/AB1999'")
        self.assertEqual(ca, [("2026-09-14", "2026-05-28", "2026-08-20")])
        # New Jersey (no votes in Open States): the roll call is read with names.
        people = q(conn, "SELECT voter_name, option, person_id FROM uss_vote_people ORDER BY seq")
        self.assertEqual(people, [("Jane Doe", "yes", None), ("John Roe", "yes", None),
                                  ("Ann Poe", "no", None)])
        # 1 session list + 2 master lists + 2 bills + people + 1 roll call.
        self.assertEqual(api.used, 7)
        self.assertEqual(ust.SourceLedger(conn, "legiscan", 100).spent(), 7)
        self.assertNotIn("SECRETKEY", json.dumps(client.archived))
        # Unchanged hashes: a second run fetches no bill.
        api2 = usl.LegiScan(client, "SECRETKEY", ust.SourceLedger(conn, "legiscan", 100))
        n2 = usl.collect(conn, api2, TAX, WL, ["ca", "nj"], TODAY, drain.Budget(60),
                         log=lambda *a: None)
        self.assertEqual(n2["fetched"], 0)

    def test_monthly_cap(self):
        conn = store()
        ledger = ust.SourceLedger(conn, "legiscan", 1)
        api = usl.LegiScan(self.client(), "K", ledger)
        api.get("getSessionList", "s")
        with self.assertRaises(ust.ApiSpent):
            api.get("getSessionList", "s")

    def test_error_scrubs_key(self):
        class Refusing(FakeClient):
            def get_bytes(self, url, feed, slug, **kw):
                raise usd.FetchError(url, feed, slug, 1, OSError("refused " + url))
        api = usl.LegiScan(Refusing({}), "SECRETKEY", ust.SourceLedger(store(), "legiscan", 5))
        with self.assertRaises(usl.LegiScanError) as cm:
            api.get("getBill", "b", id=1)
        self.assertNotIn("SECRETKEY", str(cm.exception))


class Edition(unittest.TestCase):

    def test_sources_named(self):
        conn = store()
        session_row(conn, "ks", "2025-2026", "2025-01-13")
        client = FakeClient({"kslegislature.gov": fixture("ks_bill_status_trimmed.json")})
        usd.read_kansas(conn, client, TAX, WL, TODAY, "2026-01-01")
        text = "\n".join(us_monitor.states_section(conn, "2026-01-01", TODAY,
                                                   us_monitor.area_names()))
        self.assertIn("Kansas", text)
        self.assertIn("KLISS", text)
        self.assertIn("via the Kansas Legislature's KLISS API", text)
        # HB 2635: vetoed 27 March 2026, the veto overridden in both chambers.
        self.assertIn("Enacted over the governor's veto", text)


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
