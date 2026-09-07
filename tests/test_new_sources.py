"""The six sources added 2026-09-07 (Christopher: "Build all of these")."""

import datetime
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import digest  # noqa: E402
from src.ingest import amendments, caselaw, committee_pubs, dv_petitions, oral, regulators  # noqa: E402


class AmendmentTests(unittest.TestCase):
    ROW = {"summaryText": ["To move the following Clause—", "<b>“Report on conversion practices</b>"],
           "amendmentId": "10021041", "amendmentType": "AddClauseOrSchedule", "marshalledListText": "NC42",
           "billStageId": 19748, "decision": "NegativedOnDivision",
           "sponsors": [{"isLead": True, "name": "Matt Vickers", "party": "Conservative"},
                        {"isLead": False, "name": "Another Member"}]}

    def test_parse_strips_markup_and_names_the_lead(self):
        a = amendments.parse_amendment(self.ROW, bill_id=3938, stage="Committee stage", house="Commons")
        self.assertEqual(a.summary, "To move the following Clause— “Report on conversion practices")
        self.assertEqual(a.lead, "Matt Vickers")
        self.assertEqual(a.sponsors, ["Matt Vickers", "Another Member"])
        self.assertEqual(a.label, "NC42")
        self.assertEqual(a.url, "https://bills.parliament.uk/bills/3938/stages/19748/amendments/10021041")
        self.assertEqual(amendments.decision_word(a.decision), "negatived on division")

    def test_numeric_marshalled_text_reads_as_amendment(self):
        a = amendments.parse_amendment(dict(self.ROW, marshalledListText="94"), bill_id=1, stage="Report stage")
        self.assertEqual(a.label, "Amendment 94")

    def test_paging_stops_at_total(self):
        class Client:
            calls = 0

            def get_json(self, url, feed, slug, **kw):
                Client.calls += 1
                skip = int(url.split("Skip=")[1])
                items = [dict(AmendmentTests.ROW, amendmentId=str(skip + i)) for i in range(2 if skip == 0 else 1)]
                return {"items": items, "totalResults": 3}
        rows = amendments.fetch_amendments(Client(), 3938, {"id": 19748, "description": "Committee stage"}, page=2)
        self.assertEqual(len(rows), 3)
        self.assertEqual(Client.calls, 2)

    def test_the_single_issue_bill_carries_the_flag(self):
        from src import filter as filt
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        self.assertTrue(wl.bills_raw[4157].get("all_amendments"))
        self.assertFalse((wl.bills_raw.get(3938) or {}).get("all_amendments"))


class CommitteePublicationTests(unittest.TestCase):
    ROW = {"id": "54700", "description": "Government Response - Assisted dying safeguards",
           "publicationStartDate": "2026-09-02T00:00:00", "type": {"id": 2, "name": "Government Response"},
           "committee": {"name": "Health and Social Care Committee", "house": "Commons"},
           "respondingDepartment": {"name": "Department of Health and Social Care"},
           "responseToPublicationId": 54100, "businesses": [{"title": "Assisted dying"}]}

    def test_parse_and_response_flag(self):
        pb = committee_pubs.parse_publication(self.ROW)
        self.assertEqual(pb.published, datetime.date(2026, 9, 2))
        self.assertTrue(pb.is_response)
        self.assertEqual(pb.responding_department, "Department of Health and Social Care")
        self.assertEqual(pb.url, "https://committees.parliament.uk/publications/54700/")
        self.assertIn("Assisted dying", pb.text)

    def test_the_type_filter_uses_the_parameter_the_api_honours(self):
        class Client:
            def get_json(self, url, feed, slug, **kw):
                Client.url = url
                return {"items": [], "totalResults": 0}
        committee_pubs.fetch_publications(Client(), "2026-08-31", "2026-09-06")
        self.assertIn("PublicationTypeIds=1&PublicationTypeIds=2&PublicationTypeIds=12", Client.url)


class CaseLawTests(unittest.TestCase):
    XML = ('<feed><entry><title>For Women Scotland Ltd v The Scottish Ministers</title>'
           '<link href="https://caselaw.nationalarchives.gov.uk/uksc/2025/16" rel="alternate"/>'
           '<published>2026-09-03T00:00:00+00:00</published><summary type="html">sex means biological sex</summary>'
           '<link href="https://caselaw.nationalarchives.gov.uk/uksc/2025/16/data.xml" rel="alternate" type="application/akn+xml"/>'
           '<tna:identifier slug="uksc/2025/16" type="ukncn">[2025] UKSC 16</tna:identifier></entry>'
           '<entry><title>No link</title></entry></feed>')

    def test_parse_feed(self):
        rows = caselaw.parse_feed(self.XML, "uksc")
        self.assertEqual(len(rows), 1)
        j = rows[0]
        self.assertEqual(j.ncn, "[2025] UKSC 16")
        self.assertEqual(j.published, datetime.date(2026, 9, 3))
        self.assertEqual(j.court_name, "Supreme Court")
        self.assertEqual(j.xml_url, "https://caselaw.nationalarchives.gov.uk/uksc/2025/16/data.xml")
        self.assertEqual(j.summary, "sex means biological sex")

    def test_text_is_never_archived(self):
        class Client:
            def get_text(self, url, feed, slug, archive=True):
                Client.archive = archive
                return "<p>The word woman in the Equality Act 2010 refers to biological sex.</p>"
        j = caselaw.parse_feed(self.XML, "uksc")[0]
        text = caselaw.fetch_text(Client(), j)
        self.assertFalse(Client.archive)
        self.assertIn("biological sex", text)


class OralTests(unittest.TestCase):
    TREE = [{"Title": "Debate", "SectionTreeItems": [
        {"Title": "Engagements", "HRSTag": "hs_8Question", "ExternalId": "Q1"},
        {"Title": "Rewiring the State", "HRSTag": "hs_2cStatement", "ExternalId": "S1"},
        {"Title": "Bluetongue Virus in Livestock", "HRSTag": "hs_2cUrgentQuestion", "ExternalId": "U1"}]}]

    def test_sections_picks_statements_and_uqs_only(self):
        self.assertEqual(oral.sections(self.TREE), [("Rewiring the State", "hs_2cStatement", "S1"),
                                                    ("Bluetongue Virus in Livestock", "hs_2cUrgentQuestion", "U1")])

    def test_a_statement_takes_the_minister_as_opener(self):
        payload = {"Items": [{"ItemType": "Timestamp", "Value": "12:45"},
                             {"ItemType": "Contribution", "AttributedTo": "The First Secretary of State (Louise Haigh)",
                              "Value": "With your permission, Mr Speaker, I would like to make a statement."},
                             {"ItemType": "Contribution", "AttributedTo": "Mr Speaker", "Value": "I call the shadow."}]}
        it = oral.parse_debate(payload, "Commons", datetime.date(2026, 9, 2), "Rewiring the State", "hs_2cStatement", "S1")
        self.assertEqual(it.kind, "Oral statement")
        self.assertEqual(it.minister_name, "The First Secretary of State (Louise Haigh)")
        self.assertIn("make a statement", it.minister_text)
        self.assertEqual(it.url, "https://hansard.parliament.uk/Commons/2026-09-02/debates/S1/")

    def test_a_uq_keeps_the_asker_and_the_answering_minister(self):
        payload = {"Items": [
            {"ItemType": "Contribution", "AttributedTo": "Danny Kruger (East Wiltshire) (Con)", "Value": "To ask the Secretary of State..."},
            {"ItemType": "Contribution", "AttributedTo": "The Minister for Care (Stephen Kinnock)", "Value": "The Government's position is unchanged."}]}
        it = oral.parse_debate(payload, "Commons", datetime.date(2026, 9, 3), "Assisted Dying", "hs_2cUrgentQuestion", "U1")
        self.assertEqual(it.kind, "Urgent Question")
        self.assertEqual(it.opener_name, "Danny Kruger (East Wiltshire) (Con)")
        self.assertEqual(it.minister_name, "The Minister for Care (Stephen Kinnock)")
        self.assertIn("position is unchanged", it.minister_text)


class LordsOralTests(unittest.TestCase):
    """The Lords tree has no HRSTags (every item 'NewDebate'); the debate's
    first unattributed line says what it is."""

    def test_classify_by_the_first_unattributed_line(self):
        st = {"Items": [{"ItemType": "Contribution", "Value": "Statement"},
                        {"ItemType": "Contribution", "Value": "The following Statement was made in the House of Commons on Tuesday 1 September."},
                        {"ItemType": "Contribution", "AttributedTo": "The Lord Privy Seal (Baroness Smith of Basildon) (Lab)", "Value": "My Lords, ..."}]}
        q = {"Items": [{"ItemType": "Contribution", "Value": "Question"}, {"ItemType": "Contribution", "Value": "Asked by"}]}
        pnq = {"Items": [{"ItemType": "Contribution", "Value": "Private Notice Question"}]}
        self.assertEqual(oral.classify_lords(st), "Oral statement")
        self.assertIsNone(oral.classify_lords(q))
        self.assertEqual(oral.classify_lords(pnq), "Private Notice Question")

    def test_a_lords_statement_repeat_keeps_the_minister(self):
        st = {"Items": [{"ItemType": "Contribution", "Value": "Statement"},
                        {"ItemType": "Contribution", "Value": "The following Statement was made in the House of Commons on Tuesday 1 September."},
                        {"ItemType": "Contribution", "AttributedTo": "The Lord Privy Seal (Baroness Smith of Basildon) (Lab)", "Value": "My Lords, the Government will..."}]}
        it = oral.parse_debate(st, "Lords", datetime.date(2026, 9, 2), "Direction of Government", "Oral statement", "E5")
        self.assertEqual(it.kind, "Oral statement")
        self.assertEqual(it.minister_name, "The Lord Privy Seal (Baroness Smith of Basildon) (Lab)")
        self.assertIn("the Government will", it.minister_text)

    def test_lords_sections_lists_chamber_items(self):
        tree = [{"Title": "Lords Chamber", "SectionTreeItems": [
            {"Title": "House of Lords", "HRSTag": "hs_Venue", "ExternalId": "v"},
            {"Title": "Direction of Government", "HRSTag": "NewDebate", "ExternalId": "E5"}]}]
        self.assertEqual(oral.lords_sections(tree), [("Direction of Government", "NewDebate", "E5")])


class RegulatorTests(unittest.TestCase):
    NICE = ('<table><tr><th>Title</th><th>Type</th><th>Guidance</th><th>Closes</th></tr>'
            '<tr><td><a href="https://www.nice.org.uk/guidance/gid-ng1/consultation/html-content">Gender dysphoria in '
            'children: puberty blockers [ID1]</a></td><td>Draft guidance</td><td>NICE guideline</td><td>25 September 2026</td></tr>'
            '<tr><td>no link row</td><td>x</td><td>y</td></tr></table>')

    def test_parse_nice(self):
        rows = regulators.parse_nice(self.NICE)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.regulator, "NICE")
        self.assertIn("puberty blockers", r.title)
        self.assertEqual(r.closes, datetime.date(2026, 9, 25))
        self.assertEqual(r.kind, "Draft guidance / NICE guideline")

    def test_parse_citizen_space(self):
        page = ('<ul><li class="item"><a href="/hsc/gender-services/">Children and young people gender service '
                'specification</a> <span>Closes 30 September 2026</span></li>'
                '<li><a href="https://elsewhere.org/x">Elsewhere</a></li></ul>')
        rows = regulators.parse_citizen_space(page, "https://www.engage.england.nhs.uk", "NHS England")
        self.assertEqual([r.url for r in rows], ["https://www.engage.england.nhs.uk/hsc/gender-services/"])
        self.assertEqual(rows[0].closes, datetime.date(2026, 9, 30))

    def test_blocked_sources_are_declared_not_silent(self):
        for name in ("Ofcom", "GMC", "EHRC"):
            self.assertIn(name, regulators.BLOCKED)

        class Client:
            def get_text(self, url, feed, slug, archive=True):
                raise RuntimeError("boom")
        found, gaps = regulators.fetch_all(Client(), log=lambda *_: None)
        self.assertEqual(found, [])
        names = {g[0] for g in gaps}
        self.assertTrue({"Ofcom", "GMC", "EHRC", "NICE", "NHS England"} <= names)


class DevolvedPetitionTests(unittest.TestCase):
    def test_senedd_rows_and_milestones(self):
        payload = {"data": [{"id": 247039, "attributes": {"action": "Reject any badger cull", "background": "bg",
                                                          "signature_count": 15619, "state": "open",
                                                          "threshold_for_referral": 250, "threshold_for_debate": 10000,
                                                          "opened_at": "2026-05-01T00:00:00Z", "closed_at": "2026-11-11T23:59:59Z"}},
                            {"id": 1, "attributes": {"action": "Small", "signature_count": 40, "state": "open",
                                                     "threshold_for_referral": 250, "threshold_for_debate": 10000,
                                                     "closed_at": "2026-10-01T00:00:00Z"}}],
                   "links": {"next": None}}
        rows, nxt = dv_petitions.parse_senedd(payload)
        self.assertIsNone(nxt)
        self.assertEqual(rows[0].key, "wales:247039")
        self.assertEqual(rows[0].url, "https://petitions.senedd.wales/petitions/247039")
        self.assertEqual(rows[0].milestone(), "Passed 10,000: eligible for a Plenary debate")
        self.assertEqual(rows[1].milestone(), "210 to referral; closes 2026-10-01")

    def test_scotland_keeps_only_live_statuses(self):
        rows = dv_petitions.parse_scotland([
            {"PetitionNumber": "PE2248", "PetitionTitle": "Stop prison overcrowding", "PetitionSummary": "Calling on...",
             "SignaturesCollected": "9", "PetitionStatusID": "11", "DatePetitionFirstPublished": "2026-08-26T12:55:04"},
            {"PetitionNumber": "PE0001", "PetitionTitle": "Old", "SignaturesCollected": "0", "PetitionStatusID": "7"}])
        self.assertEqual([r.id for r in rows], ["PE2248"])
        self.assertEqual(rows[0].state, "Under consideration")
        self.assertEqual(rows[0].url, "https://petitions.parliament.scot/petitions/PE2248")
        self.assertEqual(rows[0].opened, "2026-08-26")


class WiringTests(unittest.TestCase):
    def test_the_pull_runs_every_new_sweep_each_in_its_own_try(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        for name in ("sweep_amendments", "sweep_reports", "sweep_judgments", "sweep_oral", "sweep_regulators"):
            self.assertIn("def {0}(".format(name), src)
            self.assertIn("lambda: {0}(".format(name), src)
        self.assertIn('"oral": "statements"', src)
        for feed in ("oral", "amendment", "report", "judgment"):
            self.assertIn('"{0}": 7'.format(feed), src)

    def test_the_store_has_the_tables_and_coverage_watches_them(self):
        from src import db
        conn = db.init_db(sqlite3.connect(":memory:"))
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"bill_amendments", "dv_petitions", "dv_petition_snapshots"} <= names)
        cov = open(os.path.join(ROOT, "tools", "coverage.py"), encoding="utf-8").read()
        for table in ("bill_amendments", "dv_petitions", "dv_petition_snapshots"):
            self.assertIn('("{0}", '.format(table), cov)


class RenderTests(unittest.TestCase):
    def _edition(self, **kw):
        e = digest.Edition(week_commencing="2026-09-07", number=6, mode="normal")
        e.board_rows = []
        for k, v in kw.items():
            setattr(e, k, v)
        return e

    def test_amendments_table(self):
        rows = [{"bill": "Crime and Policing Bill", "stage": "Committee stage", "label": "NC42", "lead": "Matt Vickers",
                 "summary": "Report on conversion practices", "explanatory": "", "decision_word": "negatived on division",
                 "new": False, "newly_decided": True, "url": "https://bills.parliament.uk/bills/3938/stages/19748/amendments/10021041",
                 "why": "A hostile clause fell.", "tag": 3}]
        md = digest.render_amendments(rows)
        self.assertIn("## Amendments to watched Bills", md)
        self.assertIn("| Crime and Policing Bill (Committee stage) | [NC42](https://bills.parliament.uk/bills/3938/stages/19748/amendments/10021041) "
                      "| Matt Vickers | Report on conversion practices | **decided** negatived on division | A hostile clause fell. |", md)

    def test_reports_and_courts_tables_and_placement(self):
        e = self._edition(
            report_rows=[{"date": "2026-09-02", "committee": "Health and Social Care Committee", "type": "Government Response",
                          "is_response": True, "responding_department": "DHSC", "title": "Health and Social Care Committee: Assisted dying safeguards (Government Response)",
                          "url": "https://committees.parliament.uk/publications/54700/", "why": "Sets the line."}],
            judgment_rows=[{"date": "2026-09-03", "court": "Supreme Court", "title": "Supreme Court: For Women Scotland v Scottish Ministers [2025] UKSC 16",
                            "url": "https://caselaw.nationalarchives.gov.uk/uksc/2025/16", "why": "", "excerpt": "sex means biological sex"}],
            deadlines=[{"type": "Consultation", "title": "Open one", "url": "u", "why": "", "deadline": "2026-09-30"}])
        md = digest.render(e)
        self.assertIn("| Wed 2 Sep | Health and Social Care Committee | **Government response** [Assisted dying safeguards]"
                      "(https://committees.parliament.uk/publications/54700/) (DHSC) | Sets the line. |", md)
        self.assertIn("| Thu 3 Sep | Supreme Court | [For Women Scotland v Scottish Ministers [2025] UKSC 16]"
                      "(https://caselaw.nationalarchives.gov.uk/uksc/2025/16) |  |", md)
        self.assertLess(md.index("## Consultations and calls for evidence"), md.index("## Committee reports"))
        self.assertLess(md.index("## Committee reports"), md.index("## Courts"))

    def test_small_batches_get_a_floor_and_truncation_names_the_blocks(self):
        from src import triage
        one = triage._build_payload([triage.TriageItem(id="j", title="t", text="", tier=1, issue_areas=[1], watchlist_hit=False)])
        self.assertGreaterEqual(one["max_tokens"], 2000)
        with self.assertRaises(ValueError) as caught:
            triage._parse_reply({"stop_reason": "max_tokens", "content": [{"type": "thinking"}], "usage": {"output_tokens": 880}})
        self.assertIn("thinking", str(caught.exception))

    def test_one_stray_phrase_does_not_admit_a_judgment_and_migration_hides(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        self.assertIn("if len(matches) < 2 and not (head.matched()", src)
        self.assertIn('if feed == "judgment" and not [a for a in json.loads(r["issue_areas"] or "[]") if a != 11]', src)

    def test_judgments_are_described_not_judged(self):
        """Christopher, 2026-09-07: "With court judgments we can score them but
        just state what's going on. Don't note whether we agree or not." """
        from src import triage
        self.assertIn('an id beginning "judgment:"', triage.SYSTEM_PROMPT)
        self.assertIn("take no side on it", triage.SYSTEM_PROMPT)
        md = digest.render_courts([{"date": "2026-09-03", "court": "Supreme Court", "title": "Supreme Court: A v B",
                                    "url": "u", "why": "Held that X.", "excerpt": ""}])
        self.assertIn("| Handed down | Court | Case | What was decided |", md)
        self.assertIn("The monitor takes no view on a judgment", md)

    def test_empty_rows_render_nothing(self):
        self.assertIsNone(digest.render_amendments([]))
        self.assertIsNone(digest.render_reports([]))
        self.assertIsNone(digest.render_courts([]))


class DevolvedPetitionsWiringTests(unittest.TestCase):
    def test_the_weeklies_collate_and_the_page_groups_by_parliament(self):
        import tempfile
        from src import db, partner
        for wf, nation in (("sp-weekly.yml", "scotland"), ("sd-weekly.yml", "wales")):
            src = open(os.path.join(ROOT, ".github", "workflows", wf), encoding="utf-8").read()
            self.assertIn("dv_petitions.py --nation {0}".format(nation), src)
        conn = db.init_db(sqlite3.connect(":memory:")); conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO dv_petitions (key, nation, id, action, url, state, signatures, areas, matched, tier, "
                     "milestone, first_seen, last_seen) VALUES ('wales:1','wales','1','Protect faith schools',"
                     "'https://petitions.senedd.wales/petitions/1','open',412,'[6]','[]',1,"
                     "'Passed 250: referred to the Petitions Committee','2026-09-06','2026-09-06')")
        conn.execute("INSERT INTO dv_petitions (key, nation, id, action, url, state, signatures, areas, matched, tier, "
                     "milestone, first_seen, last_seen) VALUES ('scotland:PE2248','scotland','PE2248','Migration thing',"
                     "'u','Under consideration',9,'[11]','[]',1,'Under consideration','2026-09-06','2026-09-06')")
        out = tempfile.mkdtemp()
        path = partner.build_petitions_page(out, conn, {6: "Parental rights and education"})
        html = open(path, encoding="utf-8").read()
        self.assertIn("Senedd (1)", html)
        self.assertIn("Protect faith schools", html)
        self.assertNotIn("Migration thing", html)          # area 11 hidden here too
        self.assertNotIn("Holyrood (", html)


if __name__ == "__main__":
    unittest.main()
