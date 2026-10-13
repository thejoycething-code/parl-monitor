"""Other official routes for the states (13 October 2026):
tools/us_states_routes.py (Pennsylvania's LDPC bill history, the Missouri
House's XML exports, Arkansas's bill pages).

No network. Fixtures in tests/fixtures/us_states/, all REAL (read 13 October
2026 from the laptop, robots.txt asked first), trimmed:
  * pa_data_trimmed.html: the www.palegis.us/data table rows (four sessions).
  * pa_bill_history_2025_0_trimmed.zip: the 2025-2026 Bill History export of
    12 October 2026 19:31, cut to HB 17 (cursive, off our ground), HB 2215
    (age verification), SB 45 (trafficking; Act 41 of 2026) and HB 1638
    (reproductive freedom).
  * mo_SessionSet.js (the export page's session codes, its variables only),
    mo_261-BillList_trimmed.xml (HB 2, HB 1667, HB 2033),
    mo_261-HB1667.xml and mo_261-HB2033.xml (whole).
  * ar_recent_2025-04-08_trimmed.html: Recent Bill Activity of 8 April 2025,
    cut to the session field and three rows (SB 591, HB 1797 twice).
  * ar_sb591.html and ar_sb591_vote0.html: SB 591 of 2025 (race-selection
    abortion, Act 973) and its House roll call of 16 April 2025 (63-17).
"""

import os
import unittest

from src import db, drain, us_states_store as uss
from tests.test_us_states_alt import FakeClient, TAX, WL, act, fixture, os_bill, q, \
    session_row, store
from tools import us_monitor
from tools import us_states as ust
from tools import us_states_routes as usr

TODAY = "2026-10-13"


class Pennsylvania(unittest.TestCase):

    def client(self, stamp="10/12/2026 07:31 PM"):
        page = fixture("pa_data_trimmed.html", "r").replace("10/12/2026 07:31 PM", stamp)
        return FakeClient({"palegis.us/data/file": fixture("pa_bill_history_2025_0_trimmed.zip"),
                           "palegis.us/data": page})

    def test_listing(self):
        got = usr.pa_listing(fixture("pa_data_trimmed.html", "r"))
        self.assertEqual(got["2025_0"], "10/12/2026 07:31 PM")
        self.assertEqual(got["2023_1"], "12/31/2024 10:20 PM")

    def test_bills(self):
        import io
        import zipfile
        z = zipfile.ZipFile(io.BytesIO(fixture("pa_bill_history_2025_0_trimmed.zip")))
        bills = {b["identifier"]: (sid, b) for sid, _u, b in usr.pa_bills(z.read(z.namelist()[0]))}
        self.assertEqual(set(bills), {"HB 17", "HB 2215", "SB 45", "HB 1638"})
        sid, sb45 = bills["SB 45"]
        self.assertEqual(sid, "2025_0/SB45")
        self.assertEqual(sb45["url"], "https://www.palegis.us/legislation/bills/2025/sb45")
        law = [a for a in sb45["actions"] if "executive-signature" in a["classification"]]
        self.assertEqual(law[0]["date"], "2026-07-20")
        self.assertFalse(any(a["description"].startswith("(Remarks") for a in sb45["actions"]))
        self.assertIn("introduction", sb45["actions"][0]["classification"])
        final = [v for v in sb45["votes"] if v["motion"] == "Third consideration and final passage"]
        self.assertEqual((final[0]["counts"], final[0]["chamber"]),
                         ({"yes": 49, "no": 1}, "upper"))

    def test_read_merges_and_stores(self):
        conn = store()
        session_row(conn, "pa", "2025-2026", "2025-01-07", "2026-11-30")
        ust.store_bill(conn, os_bill("pa", "2025-2026", "HB 2215", "age verification bill",
                                     [act("2026-02-11", "Referred to COMMUNICATIONS AND TECHNOLOGY",
                                          ["introduction"])]),
                       ust.classify(TAX, WL, os_bill("pa", "2025-2026", "HB 2215",
                                                     "age verification", [])), TODAY)
        c = usr.read_pennsylvania(conn, self.client(), TAX, WL, TODAY)
        self.assertEqual(c.read, 4)
        self.assertEqual(c.result["merged"], 1)
        keys = {r[0] for r in conn.execute("SELECT bill_key FROM uss_bills")}
        self.assertIn("PA/2025-2026/HB1638", keys)     # reproductive freedom: new, stored
        self.assertNotIn("PA/2025-2026/HB17", keys)    # cursive handwriting: off our ground
        self.assertEqual(q(conn, "SELECT law_at FROM uss_bills WHERE bill_key='PA/2025-2026/SB45'"),
                         [("2026-07-20",)])
        # Provenance, and the edition names the source.
        self.assertEqual(q(conn, "SELECT COUNT(*) FROM uss_bill_sources WHERE source='pa-ldpc' "
                                 "AND source_id LIKE '2025_0/%'"), [(4,)])
        # Same stamp next run: the export is not downloaded again.
        client = self.client()
        c2 = usr.read_pennsylvania(conn, client, TAX, WL, TODAY)
        self.assertIn("unchanged", c2.note)
        self.assertFalse(any("data/file" in u for u in client.asked))

    def test_no_session_no_read(self):
        conn = store()
        client = self.client()
        c = usr.read_pennsylvania(conn, client, TAX, WL, TODAY)
        self.assertIn("no Open States session", c.note)
        self.assertFalse(any("data/file" in u for u in client.asked))


class Missouri(unittest.TestCase):

    def client(self):
        return FakeClient({"SessionSet.js": fixture("mo_SessionSet.js", "r"),
                           "261-BillList.XML": fixture("mo_261-BillList_trimmed.xml"),
                           "261-HB1667.xml": fixture("mo_261-HB1667.xml"),
                           "261-HB2033.xml": fixture("mo_261-HB2033.xml")})

    def test_codes(self):
        self.assertEqual(usr.mo_codes(fixture("mo_SessionSet.js", "r")),
                         ["https://documents.house.mo.gov/xml/261-"])
        shown = fixture("mo_SessionSet.js", "r").replace("'false'", "'true'")
        self.assertEqual(len(usr.mo_codes(shown)), 3)

    def test_bill(self):
        b = usr.mo_bill(fixture("mo_261-HB1667.xml"), "2026", "2026", "R")
        self.assertEqual(b["identifier"], "HB 1667")
        self.assertIn("Born-Alive", b["title"])
        self.assertEqual(b["sponsors"][0]["name"], "Brian Seitz")
        # Floor tallies only (committee tallies are left out).
        self.assertEqual([(v["date"], v["chamber"], v["counts"]) for v in b["votes"]],
                         [("2026-02-05", "lower", {"yes": 103, "no": 40, "other": 5})])
        passed = [a for a in b["actions"] if "passage" in a["classification"]]
        self.assertEqual([(a["date"], a["chamber"]) for a in passed], [("2026-02-05", "lower")])
        self.assertEqual(sum("introduction" in a["classification"] for a in b["actions"]), 1)

    def test_read_only_bills_on_our_ground(self):
        conn = store()
        session_row(conn, "mo", "2026", "2026-01-07", "2026-05-15")
        bill = os_bill("mo", "2026", "HB 1667", "Creates the Born-Alive Abortion Survivors "
                       "Protection Act", [act("2026-01-07", "Read First Time (H)",
                                              ["introduction"])])
        ust.store_bill(conn, bill, ust.classify(TAX, WL, bill), TODAY)
        client = self.client()
        c = usr.read_missouri(conn, client, TAX, WL, TODAY, drain.Budget(600))
        self.assertEqual(c.read, 1)                 # HB 2 and HB 2033 are not stored
        self.assertFalse(any("HB2033" in u for u in client.asked))
        r = conn.execute("SELECT passed_lower_at FROM uss_bills WHERE bill_key='MO/2026/HB1667'"
                         ).fetchone()
        self.assertEqual(r[0], "2026-02-05")
        # Missouri is a vote-gap state: the House's tally is stored on Open States' row.
        self.assertEqual(q(conn, "SELECT yes, no FROM uss_votes WHERE vote_id LIKE 'mo-house:%'"),
                         [(103, 40)])

    def test_max_files(self):
        conn = store()
        session_row(conn, "mo", "2026", "2026-01-07", "2026-05-15")
        for ident, title in (("HB 1667", "Born-Alive Abortion Survivors Protection Act"),
                             ("HB 2033", "gender transition procedures")):
            bill = os_bill("mo", "2026", ident, title, [act("2026-01-07", "Read First Time (H)")])
            ust.store_bill(conn, bill, ust.classify(TAX, WL, bill), TODAY)
        c = usr.read_missouri(conn, self.client(), TAX, WL, TODAY, drain.Budget(600), max_files=1)
        self.assertIn("stopped at 1 of 2", c.note)


class Arkansas(unittest.TestCase):

    def client(self):
        return FakeClient({"Votes?id=SB591": fixture("ar_sb591_vote0.html", "r"),
                           "Detail?id=SB591": fixture("ar_sb591.html", "r"),
                           "Detail?id=HB1797": "<html><h1>HB1797 - TO AMEND THE LAW CONCERNING "
                                               "STATE PARKS.</h1></html>",
                           "RecentActivities": fixture("ar_recent_2025-04-08_trimmed.html", "r")})

    def test_recent(self):
        page = fixture("ar_recent_2025-04-08_trimmed.html", "r")
        self.assertEqual(usr.ar_session_code(page), "2025/2025R")
        self.assertEqual(usr.ar_recent(page), [("SB591", "2025/2025R"), ("HB1797", "2025/2025R")])

    def test_detail_and_vote(self):
        b, links = usr.ar_detail(fixture("ar_sb591.html", "r"), "2025", "2025/2025R")
        self.assertEqual(b["identifier"], "SB 591")
        self.assertIn("RACE-SELECTION ABORTION", b["title"])
        self.assertEqual(b["sponsors"][0]["name"], "C. Penzo")
        self.assertEqual(b["actions"][0]["description"].lower()[:5], "filed")
        law = [a for a in b["actions"] if "became-law" in a["classification"]]
        self.assertTrue(law and law[0]["date"] >= "2025-04-16")
        self.assertEqual(len(links), 3)
        url, a = links[-1]                      # newest last: the House's passage
        self.assertIn("rcs=1386", url)
        v = usr.ar_vote(fixture("ar_sb591_vote0.html", "r"), url, a)
        self.assertEqual((v["counts"]["yes"], v["counts"]["no"]), (63, 17))
        self.assertEqual((v["date"], v["chamber"]), ("2025-04-16", "lower"))
        self.assertEqual(sum(p["option"] == "yes" for p in v["people"]), 63)
        self.assertEqual(sum(p["option"] == "no" for p in v["people"]), 17)

    def test_read(self):
        conn = store()
        session_row(conn, "ar", "2025", "2025-01-13", "2025-04-11")
        today = "2025-04-16"
        c = usr.read_arkansas(conn, self.client(), TAX, WL, today, drain.Budget(600), days=8)
        self.assertEqual(c.read, 2)
        self.assertEqual(c.result["stored"], 1)     # SB 591 on our ground
        self.assertEqual(c.result["skipped"], 1)    # HB 1797, parks
        r = conn.execute("SELECT bill_id, law_at FROM uss_bills WHERE bill_key='AR/2025/SB591'"
                         ).fetchone()
        self.assertEqual(r[0], "ar-arkleg:2025/2025R/SB591")
        # Three roll calls, each with its members' votes.
        self.assertEqual(q(conn, "SELECT COUNT(*) FROM uss_votes WHERE bill_id=?", (r[0],)), [(3,)])
        self.assertGreater(q(conn, "SELECT COUNT(*) FROM uss_vote_people")[0][0], 60)
        # Arkansas is a vote-gap state: when Open States stores the bill, the
        # roll calls move to its row and are kept.
        os_b = os_bill("ar", "2025", "SB 591", "TO PROHIBIT RACE-SELECTION ABORTION",
                       [act("2025-03-01", "Filed", ["introduction"], "upper")])
        ust.supersede_foreign(conn, os_b)
        self.assertEqual(q(conn, "SELECT COUNT(*) FROM uss_votes WHERE bill_id=?", (os_b["id"],)),
                         [(3,)])
        # Days already read are not asked again.
        client = self.client()
        usr.read_arkansas(conn, client, TAX, WL, today, drain.Budget(600), days=8)
        self.assertEqual(sum("date=" in u for u in client.asked), 0)


class Edition(unittest.TestCase):

    def test_sources_named_and_cover(self):
        conn = store()
        session_row(conn, "ar", "2025", "2025-01-13", "2025-04-11")
        usr.read_arkansas(conn, Arkansas().client(), TAX, WL, "2025-04-16", drain.Budget(600))
        text = "\n".join(us_monitor.states_section(conn, "2025-04-01", "2025-04-16",
                                                   us_monitor.area_names()))
        self.assertIn("via the Arkansas Legislature's bill pages", text)
        # PA's export covers the whole state the same day: no top-up for it.
        self.assertIn("pa-ldpc", ust.DIRECT_SOURCES)
        self.assertNotIn("mo-house", ust.DIRECT_SOURCES)     # House bills only, budgeted
        for src in ("pa-ldpc", "mo-house", "ar-arkleg"):
            self.assertIn(src, uss.SOURCE_NAMES)


if __name__ == "__main__":
    unittest.main()
