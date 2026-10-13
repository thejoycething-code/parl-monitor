"""The GitHub-side states step (13 October 2026): tools/us_states_github.py
(New Jersey's data downloads, the Massachusetts Legislature's API, the
Michigan Legislature's website), and the job wiring (tools/github_half.sh,
jobs/us-weekly.sh, jobs/br-weekly.sh).

No network. Fixtures in tests/fixtures/us_states/, all REAL, read from a
GitHub runner with the read-only probe workflow (runs 38336420497,
38336688578, 38337271051 and an earlier one, 13 October 2026; robots.txt
asked first), trimmed:
  * nj_2026data_listing.html (whole), nj_votes_listing_trimmed.html (the
    2025-2026 files and the read-me lines);
  * nj_DB2026_TEXT_trimmed.zip: DB2026_TEXT.zip of 12 October 2026 20:00,
    MAINBILL/BILLHIST/BILLSPON/BILLSUBJ cut to A101, A201, A794, S1270, S2260
    and S4513 (COMMITTEE.TXT whole);
  * nj_A2026_trimmed.zip, nj_S2026_trimmed.zip: the floor votes of those bills;
  * ma_194_documents_trimmed.json (seven of the 11,910 documents), the
    histories of H550, H1663, S2365 and H4000 (its first 22 actions), and
    Senate roll call 100;
  * mi_search_2026-09-24_trimmed.html (four of 154 rows),
    mi_2025-HB-4135_trimmed.html and mi_2026-HB-6423_trimmed.html (the <main>).
"""

import json
import os
import re
import unittest

from src import drain, us_states_store as uss
from tests.test_us_states_alt import TAX, WL, act, fixture, os_bill, q, session_row, store
from tools import us_monitor
from tools import us_states as ust
from tools import us_states_github as ghs

TODAY = "2026-10-13"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class Fake:
    """URL fragment -> fixture name, first match in order; records what was asked."""

    def __init__(self, routes):
        self.routes = routes
        self.asked = []

    def _find(self, url):
        self.asked.append(url)
        for frag, name in self.routes:
            if frag in url:
                return fixture(name)
        raise ghs.FetchError(url, "f", "s", 1, "HTTP Error 404: no fixture")

    def get_bytes(self, url, feed, slug, **kw):
        return self._find(url)

    def get_text(self, url, feed, slug, **kw):
        return self._find(url).decode("utf-8")


NJ_ROUTES = (("votes/A2026.zip", "nj_A2026_trimmed.zip"), ("votes/S2026.zip", "nj_S2026_trimmed.zip"),
             ("pub.njleg.gov/votes/", "nj_votes_listing_trimmed.html"),
             ("DB2026_TEXT.zip", "nj_DB2026_TEXT_trimmed.zip"),
             ("leg-databases/2026data/", "nj_2026data_listing.html"))


class NewJersey(unittest.TestCase):

    def test_listing_and_years(self):
        got = ghs.listing_stamps(fixture("nj_2026data_listing.html", "r"))
        self.assertEqual(got["DB2026_TEXT.zip"], "10/12/2026 8:02 PM")
        votes = ghs.listing_stamps(fixture("nj_votes_listing_trimmed.html", "r"))
        self.assertEqual(votes["S2026.zip"], "10/12/2026 8:30 AM")
        self.assertEqual(ghs.nj_years("2026-10-13"), (2026, [2026]))
        self.assertEqual(ghs.nj_years("2027-01-05"), (2026, [2026, 2027]))

    def test_bills(self):
        bills = ghs.nj_bills(fixture("nj_DB2026_TEXT_trimmed.zip"))
        self.assertEqual(set(bills), {"A101", "A201", "A794", "S1270", "S2260", "S4513"})
        _p, s2260 = bills["S2260"]
        self.assertEqual(s2260["identifier"], "S 2260")
        self.assertIn("reproductive health care", s2260["title"])
        law = [a for a in s2260["actions"] if "executive-signature" in a["classification"]]
        self.assertTrue(law and law[0]["description"].startswith("Approved by the Governor (APP)"))
        passed = [a for a in s2260["actions"] if "passage" in a["classification"]]
        self.assertEqual({a["chamber"] for a in passed}, {"upper", "lower"})
        self.assertTrue(any(s["primary"] for s in s2260["sponsors"]))
        _p, s4513 = bills["S4513"]
        self.assertTrue(any("executive-veto" in a["classification"] for a in s4513["actions"]))
        # A committee code is spelled out from COMMITTEE.TXT.
        _p, a201 = bills["A201"]
        self.assertIn("Committee", a201["actions"][0]["description"])
        self.assertIn("(INT 1RA REF AHE)", a201["actions"][0]["description"])

    def test_votes(self):
        votes = ghs.nj_votes(fixture("nj_A2026_trimmed.zip"), "lower", "A2026")
        v = [v for v in votes["A794"] if v["date"] == "2026-05-18"][0]
        # The bill history says (58-16-3).
        self.assertEqual((v["counts"]["yes"], v["counts"]["no"]), (58, 16))
        self.assertEqual(len(v["people"]), sum(v["counts"].values()))
        self.assertEqual(v["motion_classification"], ["passage"])
        self.assertTrue(v["id"].startswith("nj-leg:A2026/A794/2026-05-18/"))

    def test_read_merges_stores_and_skips_unchanged(self):
        conn = store()
        session_row(conn, "nj", "222", "2026-01-13", "2027-01-12")
        ust.store_bill(conn, os_bill("nj", "222", "A 201", "Pain-Capable Unborn Child Protection Act",
                                     [act("2026-01-13", "Introduced", ["introduction"])],
                                     bill_id="ocd-bill/nj-a201"),
                       ust.classify(TAX, WL, os_bill("nj", "222", "A 201", "abortion", [])), TODAY)
        c = ghs.read_new_jersey(conn, Fake(NJ_ROUTES), TAX, WL, TODAY)
        self.assertEqual(c.read, 6)
        self.assertEqual(c.result["merged"], 1)                     # A201 into Open States' row
        keys = {r[0] for r in conn.execute("SELECT bill_key FROM uss_bills")}
        self.assertIn("NJ/222/S2260", keys)                          # reproductive health: stored
        self.assertNotIn("NJ/222/A101", keys)                        # defibrillators: off our ground
        s2260 = q(conn, "SELECT bill_id, law_at FROM uss_bills WHERE bill_key='NJ/222/S2260'")[0]
        self.assertTrue(s2260[0].startswith("nj-leg:2026/"))
        self.assertTrue(s2260[1])
        self.assertGreater(q(conn, "SELECT COUNT(*) FROM uss_vote_people p JOIN uss_votes v "
                                   "USING (vote_id) WHERE v.bill_id=?", (s2260[0],))[0][0], 0)
        # Provenance and the edition's "(via ...)".
        self.assertEqual(us_monitor.source_mark({"bill_id": s2260[0]}),
                         " *(via the New Jersey Legislature's data downloads)*")
        self.assertEqual(q(conn, "SELECT COUNT(*) FROM uss_bill_sources WHERE source='nj-leg' "
                                 "AND source_id LIKE '2026/%'"), [(6,)])
        # Same stamps next run: the export and the vote files are not fetched again.
        f = Fake(NJ_ROUTES)
        c2 = ghs.read_new_jersey(conn, f, TAX, WL, TODAY)
        self.assertIn("unchanged", c2.note)
        self.assertFalse(any("TEXT.zip" in u for u in f.asked))

    def test_no_session_no_read(self):
        conn = store()
        f = Fake(NJ_ROUTES)
        c = ghs.read_new_jersey(conn, f, TAX, WL, TODAY)
        self.assertIn("no Open States session", c.note)
        self.assertEqual(f.asked, [])

    def test_votes_survive_open_states_superseding(self):
        conn = store()
        session_row(conn, "nj", "222", "2026-01-13", "2027-01-12")
        ghs.read_new_jersey(conn, Fake(NJ_ROUTES), TAX, WL, TODAY)
        before = q(conn, "SELECT COUNT(*) FROM uss_votes WHERE state='nj'")[0][0]
        self.assertGreater(before, 0)
        b = os_bill("nj", "222", "S 2260", "reproductive health care", [act("2026-01-13", "Introduced",
                                                                            ["introduction"])],
                    bill_id="ocd-bill/nj-s2260")
        ust.store_bill(conn, b, ust.classify(TAX, WL, b), TODAY)
        # New Jersey is one of OPENSTATES_VOTE_GAPS: the Legislature's votes stay, on Open States' row.
        self.assertEqual(q(conn, "SELECT COUNT(*) FROM uss_votes WHERE state='nj'")[0][0], before)
        self.assertGreater(q(conn, "SELECT COUNT(*) FROM uss_votes WHERE bill_id='ocd-bill/nj-s2260'")[0][0], 0)


MA_ROUTES = (("Documents/H4000/DocumentHistoryActions", "ma_194_H4000_history_trimmed.json"),
             ("Documents/H1663/DocumentHistoryActions", "ma_194_H1663_history.json"),
             ("Documents/H550/DocumentHistoryActions", "ma_194_H550_history.json"),
             ("Documents/S2365/DocumentHistoryActions", "ma_194_S2365_history.json"),
             ("RollCalls/100", "ma_194_senate_rollcall_100.json"),
             ("GeneralCourts/194/Documents", "ma_194_documents_trimmed.json"))


class Massachusetts(unittest.TestCase):

    def test_court(self):
        self.assertEqual(ghs.ma_court("2026-10-13"), (194, 2025))
        self.assertEqual(ghs.ma_court("2027-01-10"), (195, 2027))
        self.assertEqual(ghs.ma_ident("H1663"), "H 1663")
        self.assertIsNone(ghs.ma_ident("H4250B"))

    def test_history_votes(self):
        hist = json.loads(fixture("ma_194_H4000_history_trimmed.json"))
        votes = ghs.ma_history_votes(hist, 194, "H4000")
        v = [v for v in votes if v["id"] == "ma-api:194/house/30"][0]
        self.assertEqual((v["date"], v["chamber"], v["counts"]), ("2025-04-28", "lower",
                                                                 {"yes": 25, "no": 132}))
        self.assertEqual(v["motion"], "Amendment 556 rejected")

    def test_senate_roll_call_members(self):
        docs = json.loads(fixture("ma_194_documents_trimmed.json"))
        names = ghs.ma_names(docs)
        counts, people = ghs.ma_vote(json.loads(fixture("ma_194_senate_rollcall_100.json")), names)
        self.assertEqual((counts["yes"], counts["no"], counts["absent"]), (6, 32, 1))
        self.assertEqual(len(people), 39)

    def test_read(self):
        conn = store()
        session_row(conn, "ma", "194th", "2025-01-01", "2026-12-31")
        b = os_bill("ma", "194th", "H 4000", "General appropriations bill for fiscal 2026",
                    [act("2025-04-17", "Reported", [])], bill_id="ocd-bill/ma-h4000")
        ust.store_bill(conn, b, ust.classify(TAX, WL, b), TODAY)
        c = ghs.read_massachusetts(conn, Fake(MA_ROUTES), TAX, WL, TODAY, drain.Budget(600))
        keys = {r[0] for r in conn.execute("SELECT bill_key FROM uss_bills")}
        self.assertIn("MA/194th/H1663", keys)       # unborn victims of violence: stored
        self.assertIn("MA/194th/H550", keys)        # parental consent, sex education: stored
        self.assertNotIn("MA/194th/H3444", keys)    # s-licence compliance: never asked
        # H4000 (stored by Open States, read first as it moved lately) gains the House's tallies.
        self.assertEqual(q(conn, "SELECT vote_id, yes, no FROM uss_votes WHERE bill_id='ocd-bill/ma-h4000' "
                                 "ORDER BY vote_id"),
                         [("ma-api:194/house/30", 25, 132), ("ma-api:194/house/31", 154, 3)])
        self.assertGreaterEqual(c.result["merged"], 1)
        self.assertEqual(q(conn, "SELECT url FROM uss_bill_sources WHERE source='ma-api' AND "
                                 "source_id='194/H1663'"),
                         [("https://malegislature.gov/Bills/194/H1663",)])
        # A second run reads the histories again but merges nothing unchanged.
        c2 = ghs.read_massachusetts(conn, Fake(MA_ROUTES), TAX, WL, TODAY, drain.Budget(600))
        self.assertEqual(c2.changed, 0)

    def test_cap(self):
        conn = store()
        session_row(conn, "ma", "194th", "2025-01-01", "2026-12-31")
        f = Fake(MA_ROUTES)
        ghs.read_massachusetts(conn, f, TAX, WL, TODAY, drain.Budget(600), max_bills=1)
        self.assertEqual(sum("DocumentHistoryActions" in u for u in f.asked), 1)


MI_ROUTES = (("ExecuteSearch", "mi_search_2026-09-24_trimmed.html"),
             ("ObjectName=2026-HB-6423", "mi_2026-HB-6423_trimmed.html"),
             ("ObjectName=2025-HB-4135", "mi_2025-HB-4135_trimmed.html"))


class Michigan(unittest.TestCase):

    def test_search(self):
        rows = ghs.mi_search(fixture("mi_search_2026-09-24_trimmed.html", "r"))
        self.assertEqual([r[0] for r in rows], ["2025-SB-0102", "2025-HB-4135", "2026-HB-6423",
                                                "2026-HB-6424"])
        self.assertTrue(rows[2][2].startswith("Children: parental rights"))

    def test_bill(self):
        b = ghs.mi_bill(fixture("mi_2025-HB-4135_trimmed.html", "r"), "2025-HB-4135")
        self.assertEqual(b["identifier"], "HB 4135")
        self.assertEqual(b["sponsors"][0]["name"], "Sarah Lightner")
        self.assertTrue(b["sponsors"][0]["primary"])
        got = [(v["chamber"], v["counts"]["yes"], v["counts"]["no"]) for v in b["votes"]]
        self.assertEqual(got, [("lower", 104, 2), ("upper", 36, 0), ("lower", 101, 2)])
        passed = [(a["date"], a["chamber"]) for a in b["actions"] if "passage" in a["classification"]]
        # "PASSED BY HOUSE WITH IMMEDIATE EFFECT" on the Senate's side is the message, not a vote.
        self.assertEqual(passed, [("2025-06-05", "lower"), ("2025-11-13", "upper")])
        self.assertEqual(ust.stage_dates(b["actions"])[5], "2026-10-06")     # approved by the Governor

    def test_read(self):
        conn = store()
        session_row(conn, "mi", "2025-2026", "2025-01-08", "2026-12-31")
        b = os_bill("mi", "2025-2026", "HB 4135", "Property: conveyance of state property",
                    [act("2025-02-26", "introduced", ["introduction"])], bill_id="ocd-bill/mi-hb4135")
        ust.store_bill(conn, b, ust.classify(TAX, WL, b), TODAY)
        f = Fake(MI_ROUTES)
        c = ghs.read_michigan(conn, f, TAX, WL, TODAY, drain.Budget(600))
        keys = {r[0] for r in conn.execute("SELECT bill_key FROM uss_bills")}
        self.assertIn("MI/2025-2026/HB6423", keys)                  # parental rights: stored
        self.assertEqual(c.result["merged"], 1)                      # HB 4135: Open States' row
        self.assertEqual(q(conn, "SELECT law_at FROM uss_bills WHERE bill_id='ocd-bill/mi-hb4135'"),
                         [("2026-10-06",)])
        # 2026-HB-6424 has no fixture: a gap, so the next run starts from the same day.
        self.assertTrue(q(conn, "SELECT COUNT(*) FROM gaps WHERE detail LIKE 'Michigan 2026-HB-6424%'")[0][0])
        self.assertIn("dateFromStr=2026-10-05", f.asked[0])
        self.assertIsNone(ghs.file_seen(conn, "mi-leg", "search"))


class Wiring(unittest.TestCase):

    def test_sources_named_and_new_jersey_skips_the_topup(self):
        for s in ("nj-leg", "ma-api", "mi-leg"):
            self.assertIn(s, uss.SOURCE_NAMES)
        self.assertIn("nj-leg", ust.DIRECT_SOURCES)
        self.assertNotIn("ma-api", ust.DIRECT_SOURCES)

    def test_jobs(self):
        us, br, half = (_read("jobs", "us-weekly.sh"), _read("jobs", "br-weekly.sh"),
                        _read("tools", "github_half.sh"))
        # One dispatch for both US halves, at the start, before any write.
        self.assertIn('github_half us-weekly.yml -f senate_only="$NEED_SENATE" -f states_github="$NEED_STATES"', us)
        self.assertLess(us.index("github_half us-weekly.yml"), us.index("tools/us_rollcalls.py --congress \"$CONGRESS\" --budget"))
        self.assertIn('--exclude-states "$GH_STATES"', us)
        self.assertIn("tools/us_states_github.py --budget-seconds 300", us)
        # Brazil: dispatched before the reclassify or the collector can write.
        self.assertLess(br.index("github_half br-weekly.yml"), br.index("br_rollcalls.py --reclassify"))
        self.assertIn('--exclude-sources "$BR_GH_SOURCES"', br)
        # Never dispatched from GitHub itself; the pull job must have passed.
        self.assertIn('[ -n "${GITHUB_ACTIONS:-}" ]', half)
        self.assertIn('select(.name == "pull")', half)
        for wf, var in (("us-weekly.yml", "US_STATES_GITHUB"), ("br-weekly.yml", "BR_STATES_GITHUB")):
            text = _read(".github", "workflows", wf)
            self.assertIn("states_github:", text)
            self.assertIn(var, text)
            self.assertIn("group: parl-monitor-state", text)
            self.assertTrue(re.search(r"from-mini: \$\{\{.*inputs\.states_github == true", text))

    def test_exclude_states_flag(self):
        import inspect
        self.assertIn("--exclude-states", inspect.getsource(ust.main))


if __name__ == "__main__":
    unittest.main()
