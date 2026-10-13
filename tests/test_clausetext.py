"""Clause text for divisions whose titles only number a clause (2026-10-13).

The 8 September 2026 puberty blockers vote (division 2421) was titled "Health
Bill: Report Stage: New Clause 142" and the single-sex NHS facilities vote
(2422) "... New Clause 143": no term, so the title sweep never saw either.
These tests read the clauses from fixtures captured from the live Bills API on
13 October 2026 (tests/fixtures/clausetext: the Health Bill's search result,
its stages, its Commons report-stage amendment list trimmed to five rows with
totalResults set to match, and the full detail of NC142, NC143 and NC145).

"Lords Amendment N" divisions (Commons ping-pong) are read from the Commons
debate in Hansard: the fixtures are Hansard's division searches for 14 to 29
April 2026, the Pension Schemes Bill debates of 15, 22, 27 and 28 April, the
Crime and Policing Bill debate of 14 April and its "Unpublished Divisions"
section, and the Pension Schemes Bill's Lords stages in the Bills API (all
captured 13 October 2026).

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
    # Lords amendments (Commons ping-pong), captured 13 October 2026: Hansard's
    # division search for each day (searchTerm=Bill), the debates it names, and
    # for the second route the Pension Schemes Bill's Lords stages in the Bills
    # API (committee: its 9 agreed amendments; report: five rows, among them
    # 115, 157 and 162; third reading: all 8), totalResults set to match.
    "searchTerm=Bill&queryParameters.startDate=2026-04-14&": "hansard_divisions_2026-04-14.json",
    "searchTerm=Bill&queryParameters.startDate=2026-04-15&": "hansard_divisions_2026-04-15.json",
    "searchTerm=Bill&queryParameters.startDate=2026-04-16&": "hansard_divisions_2026-04-16.json",
    "searchTerm=Bill&queryParameters.startDate=2026-04-22&": "hansard_divisions_2026-04-22.json",
    "searchTerm=Bill&queryParameters.startDate=2026-04-23&": "hansard_divisions_2026-04-23.json",
    "searchTerm=Bill&queryParameters.startDate=2026-04-27&": "hansard_divisions_2026-04-27.json",
    "searchTerm=Bill&queryParameters.startDate=2026-04-28&": "hansard_divisions_2026-04-28.json",
    "searchTerm=Bill&queryParameters.startDate=2026-04-29&": "hansard_divisions_2026-04-29.json",
    "/debates/debate/D93794FC": "hansard_debate_D93794FC.json",     # Pension Schemes Bill, 15 Apr
    "/debates/debate/0DF5A391": "hansard_debate_0DF5A391.json",     # Crime and Policing Bill, 14 Apr
    "/debates/debate/9985E890": "hansard_debate_9985E890.json",     # its "Unpublished Divisions"
    "/debates/debate/DCDD837C": "hansard_debate_DCDD837C.json",     # Pension Schemes Bill, 22 Apr
    "/debates/debate/A9CA6303": "hansard_debate_A9CA6303.json",     # Pension Schemes Bill, 27 Apr
    "/debates/debate/DA5B1EEF": "hansard_debate_DA5B1EEF.json",     # Pension Schemes Bill, 28 Apr
    "/Bills?SearchTerm=Pension%20Schemes%20Bill": "search_pension_schemes_bill.json",
    "/Bills/3982/Stages?": "stages_3982.json",
    # older Bills of the same name, whose stages rule them out by date
    "/Bills/2526/Stages?": "stages_2526.json",
    "/Bills/2467/Stages?": "stages_2467.json",
    "/Bills/1912/Stages?": "stages_1912.json",
    "/Bills/1411/Stages?": "stages_1411.json",
    "/Bills/3982/Stages/20365/Amendments?": "amendments_3982_20365.json",
    "/Bills/3982/Stages/20513/Amendments?": "amendments_3982_20513.json",
    "/Bills/3982/Stages/20551/Amendments?": "amendments_3982_20551.json",
    "/Bills/3982/Stages/20513/Amendments/10033587": "amendment_10033587.json",
    "/Bills/3982/Stages/20513/Amendments/10033592": "amendment_10033592.json",
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
        lk, (result, labels) = self.look("Health Bill: Report Stage: New Clause 143", did=2422)
        self.assertEqual(labels, ["New Clause 143"])
        self.assertEqual(result.issue_areas, [5])
        # Taxonomy v1.25: the clause is headed "Single sex facilities"; before
        # the unhyphenated forms it matched only "changing room*" at tier 2.
        self.assertEqual(result.tier, 1)
        self.assertIn("single sex facilit*", result.matched_terms)
        self.assertTrue(ct.ledger_ok(lk, labels, TAX, WL))

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


class LordsAmendments(unittest.TestCase):
    """"Lords Amendment N" read from the Commons debate in Hansard (and, for a
    new clause, the Lords' own report-stage text in the Bills API)."""

    def setUp(self):
        self.client = FakeClient()
        self.reader = ct.ClauseReader(self.client)

    def look(self, title, date, counts=None, did=None):
        lk = self.reader.lookup(title, date, "Commons", None, did, counts=counts)
        return lk, ct.match(lk, TAX, WL)

    def test_mentions_reads_lists_ranges_and_split_numbers(self):
        s = "With this: Lords amendments 5, 6, 13, 15 to 24, 26, 27, 30 to 43, 77 to 79 and 88."
        for n in ("5", "20", "43", "78", "88"):
            self.assertTrue(ct.mentions(s, n), n)
        for n in ("7", "25", "44", "8", "88A"):
            self.assertFalse(ct.mentions(s, n), n)
        self.assertTrue(ct.mentions("Lords amendments 38V to 38X on social media", "38W"))
        # Hansard splits a number across tags; the text keeps it whole.
        item = {"Value": "<em>Lords amendment 7</em><em>8</em><em> disagreed to.</em>"}
        self.assertTrue(ct.mentions(ct._htext(item), "78"))

    def test_new_clause_heading_finds_the_lords_report_stage_text(self):
        # Division 2318, 15 April 2026: Lords Amendment 77 is the Lords'
        # report-stage amendment 157, "Review of public service pension schemes".
        lk, (result, labels) = self.look(
            "Pension Schemes Bill: motion to disagree with Lords Amendment 77", "2026-04-15", (271, 95), 2318)
        self.assertEqual(lk.status, "ok")
        self.assertIsNone(lk.gap)
        clause = lk.clauses[0]
        self.assertEqual(clause["source"], "Hansard (Lords amendment)")
        self.assertTrue(clause["text"].startswith(
            "After Clause 117: Review of public service pension schemes"))
        self.assertIn("Lords amendment 77 calls for a review", clause["text"])
        self.assertEqual(clause["lords_stage"], "Report stage amendment 157")
        self.assertTrue(clause["explanatory"].startswith("This new clause would require the Secretary of State"))
        self.assertEqual(lk.bill_id, 3982)
        why = ct.describe(lk, ["Lords Amendment 77"])
        self.assertTrue(why.startswith("Hansard (Lords amendment): Lords Amendment 77 of the Pension Schemes Bill"))
        self.assertIn("hansard.parliament.uk/Commons/2026-04-15/debates/D93794FC", why)
        self.assertIn("bills.parliament.uk/bills/3982/stages/20513/amendments/10033592", why)

    def test_existing_clause_heading_is_not_guessed(self):
        # Lords Amendment 26 amends Clause 40, to which the Lords agreed several
        # amendments: the heading cannot say which, so no Lords-stage text.
        lk, _ = self.look("Pension Schemes Bill: motion to disagree with Lords Amendment 26", "2026-04-15", (269, 162))
        clause = lk.clauses[0]
        self.assertTrue(clause["explanatory"].startswith("Clause 40: Certain schemes"))
        self.assertNotIn("lords_stage", clause)
        self.assertIn("Lords amendments 26 and 37, which seek to create more exemptions", clause["text"])

    def test_procedural_sentences_are_not_text(self):
        lk, _ = self.look("Pension Schemes Bill: motion to disagree with Lords Amendment 1", "2026-04-15", (278, 158))
        text = lk.clauses[0]["text"]
        self.assertIn("Lords amendment 1 understandably tries to introduce an explicit prohibition", text)
        for clerk in ("beg to move", "disagreed to", "convenient to discuss", "Question put",
                      "Government motions to disagree"):
            self.assertNotIn(clerk, text)
        self.assertEqual(lk.clauses[0]["explanatory"], "")      # no heading above the first motion

    def test_unpublished_divisions_section_and_the_debate_are_both_read(self):
        # Division 2306, 14 April 2026: Hansard files the division under 15
        # April in "Unpublished Divisions: Crime and Policing Bill (14 April
        # 2026)"; the debate describing amendment 334 is the Bill's own, 14 April.
        lk, (result, labels) = self.look(
            "Crime and Policing Bill: motion to disagree with Lords Amendment 334", "2026-04-14", (356, 90), 2306)
        self.assertEqual(labels, ["Lords Amendment 334"])
        self.assertEqual(result.issue_areas, [7])
        self.assertIn("non-crime hate incident*", result.matched_terms)
        self.assertIn("seeks to abolish non-crime hate incidents", lk.clauses[0]["text"])
        # Members' sentences are argument, not purpose: stored, not ledgered.
        self.assertEqual(result.tier, 1)
        self.assertFalse(ct.ledger_ok(lk, labels, TAX, WL))
        searched = [u for u in self.client.calls if "search/divisions" in u]
        self.assertTrue(any("startDate=2026-04-15" in u for u in searched))
        debates = [u for u in self.client.calls if "/debates/debate/" in u]
        self.assertEqual(sorted(u.split("/")[-1][:8] for u in debates), ["0DF5A391", "9985E890"])

    def test_misspelt_title_is_found_by_its_counts(self):
        title = "Pensions Scheme Bill: motion to disagree with Lords Amendment 5"
        lk, _ = self.look(title, "2026-04-15", (269, 103), 2313)
        self.assertEqual(lk.status, "ok")
        self.assertIn("Lords amendment 5 would introduce specific benchmarks", lk.clauses[0]["text"])
        # Without the counts the name alone finds nothing, and says so.
        lk, _ = ct.ClauseReader(FakeClient()).lookup(title, "2026-04-15"), None
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("no Hansard debate on 'Pensions Scheme Bill'", lk.gap)

    def test_ping_pong_round_reads_the_first_consideration(self):
        # Division 2348, 28 April 2026: the debate argues the reserve power and
        # names no amendment; 15 and 27 were described on 15 April. 16 to 18 and
        # 88 were never described by number: read in part, and said so.
        lk, _ = self.look("Pension Schemes Bill: motion to disagree with Lords Amendments 15 to 18, 27 "
                          "and 88, insist on Amendments 88C", "2026-04-28", (335, 158))
        self.assertEqual(lk.status, "ok")
        got = {c["label"]: c for c in lk.clauses}
        self.assertEqual(sorted(got), ["Lords Amendment 15", "Lords Amendment 27"])
        self.assertEqual(got["Lords Amendment 15"]["described_on"], ["2026-04-15"])
        self.assertIn("mandation", got["Lords Amendment 15"]["text"])
        # The heading above a motion is its FIRST amendment's clause only.
        self.assertTrue(got["Lords Amendment 15"]["explanatory"].startswith("Clause 40"))
        self.assertEqual(got["Lords Amendment 27"]["explanatory"], "")
        self.assertIn("partly read; missing Lords Amendment 16, Lords Amendment 17, Lords Amendment 18, "
                      "Lords Amendment 88", lk.gap)

    def test_hansard_down_fails_loud(self):
        lk = ct.ClauseReader(FakeClient(down=True)).lookup(
            "Crime and Policing Bill: motion to disagree with Lords Amendment 2", "2026-04-14", counts=(307, 176))
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("could not read clause text (Hansard API unavailable", lk.gap)

    def test_store_cache_keeps_the_source(self):
        conn = db.init_db(db.connect(":memory:"))
        ct.ClauseReader(FakeClient(), conn).lookup(
            "Crime and Policing Bill: motion to disagree with Lords Amendment 334", "2026-04-14",
            "Commons", None, 2306, counts=(356, 90))
        client = FakeClient()
        again = ct.ClauseReader(client, conn).lookup(
            "Crime and Policing Bill: motion to disagree with Lords Amendment 334", "2026-04-14",
            "Commons", None, 2306, counts=(356, 90))
        self.assertTrue(again.cached)
        self.assertEqual(client.calls, [])
        self.assertEqual(ct.match_source(again), "Hansard (Lords amendment)")


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
    def test_scan_flags_the_missed_votes(self):
        import check_clause_text as tool
        rows = [(2419, "2026-09-07", "Health Bill: Report Stage: New Clause 145"),
                (2421, "2026-09-08", "Health Bill: Report Stage: New Clause 142"),
                (2422, "2026-09-08", "Health Bill: Report Stage: New Clause 143"),
                (2306, "2026-04-14", "Crime and Policing Bill: motion to disagree with Lords Amendment 334",
                 356, 90),
                (2312, "2026-04-15", "Pension Schemes Bill: motion to disagree with Lords Amendment 1", 278, 158),
                (2313, "2026-04-15", "Pensions Scheme Bill: motion to disagree with Lords Amendment 5"),
                (2318, "2026-04-15", "Pension Schemes Bill: motion to disagree with Lords Amendment 77", 271, 95)]
        flagged, gaps = tool.scan(rows, ct.ClauseReader(FakeClient()), TAX, WL)
        self.assertEqual([(f["id"], f["areas"], f["source"]) for f in flagged],
                         [(2421, [3], "clause text"), (2422, [5], "clause text"),
                          (2318, [9], "Hansard (Lords amendment)")])
        # 2318: the Lords' explanatory statement speaks of demographic change
        # (tier 2): a candidate for a human, never the ledger.
        self.assertEqual([f["tier"] for f in flagged], [1, 1, 2])
        self.assertEqual([f["ledger"] for f in flagged], [True, True, False])
        # 2306 names a watched Bill, so the title sweep already sees it; 2312
        # is read and matches nothing; 2313, misspelt and without its counts,
        # cannot be found and is a gap, not a no-match.
        self.assertEqual([g[0] for g in gaps], [2313])


if __name__ == "__main__":
    unittest.main()
