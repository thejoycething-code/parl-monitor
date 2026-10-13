"""Clause text for divisions whose titles only number a clause (2026-10-13).

The 8 September 2026 puberty blockers vote (division 2421) was titled "Health
Bill: Report Stage: New Clause 142" and the single-sex NHS facilities vote
(2422) "... New Clause 143": no term, so the title sweep never saw either.
These tests read the clauses from fixtures captured from the live Bills API on
13 October 2026 (tests/fixtures/clausetext: the Health Bill's search result,
its stages, its Commons report-stage amendment list trimmed to five rows with
totalResults set to match, and the full detail of NC142, NC143 and NC145).

The negative case is real too: NC145 (division 2419, 7 Sept) is the Hughes
Report on valproate and pelvic mesh, read correctly and matching nothing. And
the fail-loud cases matter as much as the hits: a clause that cannot be read
must say so, never pass as "no match".
"""

import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import clausetext as ct, db, filter as filt  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "clausetext")
ROUTES = {
    "/Bills?SearchTerm=Health%20Bill": "search_health_bill.json",
    "/Bills/4124/Stages?": "stages_4124.json",
    "/Bills/4124/Stages/21130/Amendments?": "amendments_4124_21130.json",
    "/Bills/4124/Stages/21155/Amendments?": "amendments_4124_21155.json",
    "/Bills/4124/Stages/21179/Amendments?": "amendments_4124_21179.json",
    "/Bills/4124/Stages/21162/Amendments?": "amendments_4124_21162.json",
    "/Bills/4124/Stages/21130/Amendments/10038149": "amendment_10038149.json",
    "/Bills/4124/Stages/21130/Amendments/10038150": "amendment_10038150.json",
    "/Bills/4124/Stages/21130/Amendments/10038152": "amendment_10038152.json",
}


class FakeClient:
    """Serves the captured fixtures by URL; anything else fails like the network."""

    def __init__(self, down=False):
        self.calls = []
        self.down = down

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.calls.append(url)
        if self.down:
            raise RuntimeError("503 Service Unavailable")
        for key, name in ROUTES.items():
            if key in url:
                with open(os.path.join(FIX, name), encoding="utf-8") as handle:
                    return json.load(handle)
        raise RuntimeError("no fixture for " + url)


TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))


class ParseRefs(unittest.TestCase):
    def refs(self, title, house="Commons", notes=None):
        bill, refs = ct.parse_refs(title, house, notes)
        return bill, [(r.kind, r.number) for r in refs]

    def test_report_stage_new_clause(self):
        self.assertEqual(self.refs("Health Bill: Report Stage: New Clause 142"),
                         ("Health Bill", [("new_clause", "142")]))

    def test_shapes_without_punctuation(self):
        self.assertEqual(self.refs("Mental Health Bill Report Stage New Clause 26"),
                         ("Mental Health Bill", [("new_clause", "26")]))
        self.assertEqual(self.refs("Steel Industry (Nationalisation) Bill Committee: Amendment 7"),
                         ("Steel Industry (Nationalisation) Bill", [("amendment", "7")]))

    def test_lords_amendment_lists_and_ranges(self):
        _, refs = self.refs("English Devolution and Community Empowerment Bill: motion to "
                            "disagree with Lords Amendments 4B and 4C")
        self.assertEqual(refs, [("lords_amendment", "4B"), ("lords_amendment", "4C")])
        _, refs = self.refs("Pension Schemes Bill: motion to disagree with Lords Amendments 15 to 18, 27 and 30")
        self.assertEqual([n for _, n in refs], ["15", "16", "17", "18", "27", "30"])
        self.assertTrue(all(k == "lords_amendment" for k, _ in refs))

    def test_not_clause_references(self):
        for title in ("Steel Industry (Nationalisation) Bill: Reasoned Amendment to Second Reading",
                      "Railways Bill: Third Reading",
                      "King's Speech Motion for an Address: amendment (p)",
                      "Opposition Day: Puberty blockers",
                      "Draft Carbon Budget Order 2026"):
            self.assertEqual(self.refs(title)[1], [], title)

    def test_ping_pong_commons_amendments_are_not_read_as_report_amendments(self):
        # "insist on Amendments 4A" names Commons amendments to Lords amendments.
        _, refs = self.refs("Crime and Policing Bill: motion to insist on Amendments 4C and 4D "
                            "and disagree with Lords Amendments 4E and 4F")
        self.assertEqual({k for k, _ in refs}, {"lords_amendment"})

    def test_lords_notes(self):
        notes = ("Lord German moved amendment 73, after clause 48, to insert the new clause "
                 "Temporary asylum processing units. The House divided:")
        self.assertEqual(self.refs("Border Security, Asylum and Immigration Bill", "Lords", notes),
                         ("Border Security, Asylum and Immigration Bill", [("amendment", "73")]))
        motion = "Lord Jackson moved Motion A1, as an amendment to Motion A, ... insist on its Amendment 37"
        self.assertEqual(self.refs("Border Security, Asylum and Immigration Bill", "Lords", motion)[1], [])

    def test_base_name_survives_royal_assent_and_house_marks(self):
        self.assertEqual(ct.base_name("Crime and Policing Bill"), ct.base_name("Crime and Policing Act 2026"))
        self.assertEqual(ct.base_name("Mental Health Bill"), ct.base_name("Mental Health Bill [HL]"))
        self.assertEqual(ct.base_name("Social Housing Bill [Lords]"), ct.base_name("Social Housing Bill [HL]"))
        self.assertNotEqual(ct.base_name("Health Bill"), ct.base_name("Mental Health Bill"))
        self.assertEqual(ct.base_name("Bus Services (No.2) Bill"), ct.base_name("Bus Services (No. 2) Bill [HL]"))
        # The API drops "(No. 2)" ("Finance Act 2026"); the sitting date disambiguates.
        self.assertEqual(ct.base_name("Finance (No. 2) Bill"), ct.base_name("Finance Act 2026"))


class Lookup(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.reader = ct.ClauseReader(self.client)

    def look(self, title, date="2026-09-08", did=None):
        lk = self.reader.lookup(title, date, "Commons", None, did)
        return lk, ct.match(lk, TAX, WL)

    def test_nc142_puberty_blockers_matches_area_3(self):
        lk, (result, labels) = self.look("Health Bill: Report Stage: New Clause 142", did=2421)
        self.assertEqual(lk.status, "ok")
        self.assertEqual(lk.stage, "Report stage")
        self.assertEqual(labels, ["New Clause 142"])
        self.assertIn(3, result.issue_areas)
        self.assertEqual(result.tier, 1)
        self.assertTrue(any(t.startswith("puberty") for t in result.matched_terms), result.matched_terms)
        self.assertIn("clause text: New Clause 142 of the Health Bill", ct.describe(lk, labels))
        self.assertIsNone(lk.gap)

    def test_ledger_gate_reads_the_stated_purpose(self):
        lk, (_, labels) = self.look("Health Bill: Report Stage: New Clause 142", did=2421)
        self.assertTrue(ct.ledger_ok(lk, labels, TAX, WL))
        # A tier-1 Act cited only in the body (Sentencing Bill NC20, division
        # 2163: a child-cruelty register listing offences under the 1861 Act).
        body_only = ct.Lookup("ok", bill="Sentencing Bill", clauses=[{
            "label": "New Clause 20",
            "explanatory": "This new clause would create notification requirements for people "
                           "convicted of child cruelty, analogous to the Sex Offenders Register.",
            "text": "Child cruelty offences: notification ... an offence under section 27 of the "
                    "Offences against the Person Act 1861 (abandoning children) ..."}])
        result, labels = ct.match(body_only, TAX, WL)
        self.assertEqual(result.tier, 1)
        self.assertFalse(ct.ledger_ok(body_only, labels, TAX, WL))

    def test_nc143_single_sex_facilities_matches_area_5(self):
        _, (result, labels) = self.look("Health Bill: Report Stage: New Clause 143", did=2422)
        self.assertEqual(labels, ["New Clause 143"])
        self.assertEqual(result.issue_areas, [5])

    def test_negative_nc145_is_read_and_matches_nothing(self):
        lk, (result, labels) = self.look("Health Bill: Report Stage: New Clause 145", "2026-09-07", 2419)
        self.assertEqual(lk.status, "ok")                       # read, not a gap
        self.assertIn("Hughes", lk.clauses[0]["text"])
        self.assertEqual(labels, [])
        self.assertFalse(result.matched())
        self.assertIsNone(lk.gap)

    def test_the_title_alone_matches_nothing(self):
        # The reason this exists.
        for title in ("Health Bill: Report Stage: New Clause 142", "Health Bill: Report Stage: New Clause 143"):
            self.assertFalse(filt.filter_item(TAX, WL, title).matched())

    def test_wrong_date_fails_loud(self):
        lk, (result, labels) = self.look("Health Bill: Report Stage: New Clause 142", "2026-09-10")
        self.assertEqual(lk.status, "unreadable")
        self.assertIsNone(result)
        self.assertIn("could not read clause text", lk.gap)
        self.assertIn("no Commons stage", lk.gap)

    def test_unknown_number_fails_loud(self):
        lk, _ = self.look("Health Bill: Report Stage: New Clause 999")
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("New Clause 999 not found", lk.gap)

    def test_api_down_fails_loud(self):
        reader = ct.ClauseReader(FakeClient(down=True))
        lk = reader.lookup("Health Bill: Report Stage: New Clause 142", "2026-09-08")
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("Bills API unavailable", lk.gap)

    def test_lords_amendment_fails_loud_without_a_call(self):
        lk, _ = self.look("Crime and Policing Bill: motion to disagree with Lords Amendment 2", "2026-04-14")
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("Lords amendments paper", lk.gap)
        self.assertEqual(self.client.calls, [])

    def test_no_reference_is_not_a_gap(self):
        lk, (result, labels) = self.look("Draft Carbon Budget Order 2026")
        self.assertEqual(lk.status, "none")
        self.assertIsNone(lk.gap)
        self.assertEqual(self.client.calls, [])

    def test_one_bill_is_fetched_once_per_run(self):
        self.look("Health Bill: Report Stage: New Clause 142", did=2421)
        self.look("Health Bill: Report Stage: New Clause 143", did=2422)
        lists = [u for u in self.client.calls if "Amendments?" in u]
        searches = [u for u in self.client.calls if "SearchTerm" in u]
        self.assertEqual((len(lists), len(searches)), (1, 1))


class StoreCache(unittest.TestCase):
    def test_second_lookup_reads_the_store_not_the_api(self):
        conn = db.init_db(db.connect(":memory:"))
        first = ct.ClauseReader(FakeClient(), conn).lookup(
            "Health Bill: Report Stage: New Clause 142", "2026-09-08", "Commons", None, 2421)
        client = FakeClient()
        again = ct.ClauseReader(client, conn).lookup(
            "Health Bill: Report Stage: New Clause 142", "2026-09-08", "Commons", None, 2421)
        self.assertTrue(again.cached)
        self.assertEqual(client.calls, [])
        self.assertEqual(again.clauses, first.clauses)
        self.assertEqual(ct.match(again, TAX, WL)[1], ["New Clause 142"])

    def test_failures_are_not_cached(self):
        conn = db.init_db(db.connect(":memory:"))
        ct.ClauseReader(FakeClient(down=True), conn).lookup(
            "Health Bill: Report Stage: New Clause 142", "2026-09-08", "Commons", None, 2421)
        self.assertEqual(conn.execute("SELECT count(*) FROM clause_text").fetchone()[0], 0)

    def test_read_only_store_does_not_break_the_lookup(self):
        conn = sqlite3.connect(":memory:")                     # no clause_text table at all
        lk = ct.ClauseReader(FakeClient(), conn).lookup(
            "Health Bill: Report Stage: New Clause 142", "2026-09-08", "Commons", None, 2421)
        self.assertEqual(lk.status, "ok")


class CheckTool(unittest.TestCase):
    def test_scan_flags_exactly_the_two_missed_votes(self):
        import check_clause_text as tool
        rows = [(2419, "2026-09-07", "Health Bill: Report Stage: New Clause 145"),
                (2421, "2026-09-08", "Health Bill: Report Stage: New Clause 142"),
                (2422, "2026-09-08", "Health Bill: Report Stage: New Clause 143"),
                (2312, "2026-04-15", "Pension Schemes Bill: motion to disagree with Lords Amendment 1")]
        flagged, gaps = tool.scan(rows, ct.ClauseReader(FakeClient()), TAX, WL)
        self.assertEqual([(f["id"], f["areas"]) for f in flagged], [(2421, [3]), (2422, [5])])
        self.assertEqual([g[0] for g in gaps], [2312])


if __name__ == "__main__":
    unittest.main()
