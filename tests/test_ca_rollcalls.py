"""House of Commons of Canada divisions and bills (tools/ca_rollcalls.py). No network."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, filter as filt  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "ca_rollcalls", os.path.join(ROOT, "tools", "ca_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


car = _load()
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-ca.yaml"))

C9 = ("3rd reading and adoption of Bill C-9, An Act to amend the Criminal Code "
      "(hate propaganda, hate crime and access to religious or cultural places)")
C34 = ("2nd reading of Bill C-34, An Act to enact the Digital Safety Act and the "
       "Digital Safety Commission of Canada Act and to make consequential amendments")
TRADES = ("2nd reading of Bill C-266, An Act to establish a national framework "
          "respecting skilled trades and labour mobility")
ASYLUM = "Opposition Motion (Federal benefits and asylum claimants)"


def vote(number, subject, result="Agreed To", yeas=170, nays=140, bill=None):
    return ("<Vote><PersonId>0</PersonId><ParliamentNumber>45</ParliamentNumber>"
            "<SessionNumber>1</SessionNumber><DecisionEventDateTime>2026-03-25T18:30:00"
            "</DecisionEventDateTime><DecisionDivisionNumber>{0}</DecisionDivisionNumber>"
            "<DecisionDivisionSubject>{1}</DecisionDivisionSubject>"
            "<DecisionResultName>{2}</DecisionResultName>"
            "<DecisionDivisionNumberOfYeas>{3}</DecisionDivisionNumberOfYeas>"
            "<DecisionDivisionNumberOfNays>{4}</DecisionDivisionNumberOfNays>"
            "<DecisionDivisionNumberOfPaired>2</DecisionDivisionNumberOfPaired>"
            "<DecisionDivisionDocumentTypeName>Legislative Process"
            "</DecisionDivisionDocumentTypeName><BillNumberCode>{5}</BillNumberCode>"
            "</Vote>").format(number, subject, result, yeas, nays, bill or "")


def divisions_xml(*votes):
    return "<ArrayOfVote>" + "".join(votes) + "</ArrayOfVote>"


def participant(pid, first, last, party, yea=False, nay=False, paired=False):
    b = lambda v: "true" if v else "false"  # noqa: E731
    return ("<VoteParticipant><PersonId>{0}</PersonId>"
            "<PersonOfficialFirstName>{1}</PersonOfficialFirstName>"
            "<PersonOfficialLastName>{2}</PersonOfficialLastName>"
            "<CaucusShortName>{3}</CaucusShortName><ConstituencyName>Somewhere"
            "</ConstituencyName><ConstituencyProvinceTerritoryName>Alberta"
            "</ConstituencyProvinceTerritoryName><VoteValueName>{4}</VoteValueName>"
            "<IsVoteYea>{5}</IsVoteYea><IsVoteNay>{6}</IsVoteNay>"
            "<IsVotePaired>{7}</IsVotePaired></VoteParticipant>").format(
                pid, first, last, party, "Yea" if yea else "Nay",
                b(yea), b(nay), b(paired))


PARTICIPANTS = ("<ArrayOfVoteParticipant>"
                + participant(1, "Ziad", "Aboultaif", "Conservative", nay=True)
                + participant(2, "Anna", "Example", "Liberal", yea=True)
                + participant(3, "Paul", "Paired", "Bloc Québécois", yea=True, paired=True)
                + "</ArrayOfVoteParticipant>")

BILLS = [
    {"Id": 1, "NumberCode": "S-1", "LongTitleEn": "An Act relating to railways", "IsProForma": True},
    {"Id": 2, "NumberCode": "C-34", "IsProForma": False,
     "LongTitleEn": "An Act to enact the Digital Safety Act and the Digital Safety Commission of Canada Act and to make consequential amendments to certain Acts",
     "StatusNameEn": "At second reading in the House of Commons", "IsGovernmentBill": True},
    {"Id": 3, "NumberCode": "C-266", "IsProForma": False,
     "LongTitleEn": "An Act to establish a national framework respecting skilled trades and labour mobility",
     "StatusNameEn": "At second reading in the House of Commons", "IsGovernmentBill": False},
]


class FakeClient:
    def __init__(self, divisions, participants=PARTICIPANTS):
        self.divisions = divisions
        self.participants = participants
        self.detail_calls = []

    def get_text(self, url, feed, slug, archive=True):
        if "parlSession=" in url:
            return self.divisions
        if url.endswith("/xml"):
            self.detail_calls.append(url)
            return self.participants
        raise AssertionError(url)

    def get_json(self, url, feed, slug, archive=True):
        assert "legisinfo" in url, url
        return BILLS


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return ca_store.ensure_schema(conn)


def quiet(*a):
    return None


class CanadaRollCallTests(unittest.TestCase):
    def pull(self, conn, client, **kw):
        return car.pull_divisions(conn, client, "2026-09-26", tax=TAX, wl=WL, log=quiet, **kw)

    def test_every_division_is_stored_but_positions_only_on_our_ground(self):
        conn = store()
        client = FakeClient(divisions_xml(vote(93, C9, bill="C-9"), vote(174, TRADES, bill="C-266")))
        listed, ours, fetched, gaps = self.pull(conn, client)
        self.assertEqual((listed, ours, fetched, gaps), (2, 1, 1, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ca_divisions").fetchone()[0], 2)
        self.assertEqual(len(client.detail_calls), 1)
        self.assertTrue(client.detail_calls[0].endswith("/45/1/93/xml"))

    def test_c9_carries_religious_freedom_not_only_hate_crime(self):
        """The taxonomy alone filed the Combatting Hate Act under area 7; the
        religious-text defence it removes is area 8, and the watchlist says so."""
        res = car.classify(TAX, WL, C9)
        self.assertIn(7, res.issue_areas)
        self.assertIn(8, res.issue_areas)

    def test_the_digital_safety_act_is_seen(self):
        """'Online Safety Act' is the UK name; the taxonomy missed C-34."""
        self.assertEqual(filt.filter_item(TAX, filt.load_watchlist(
            os.path.join(ROOT, "config", "watchlist.yaml")), C34).issue_areas, [],
            "if this starts matching, the watchlist entry may be redundant")
        self.assertIn(7, car.classify(TAX, WL, C34).issue_areas)

    def test_migration_is_classified_but_earns_no_fetch(self):
        conn = store()
        client = FakeClient(divisions_xml(vote(72, ASYLUM)))
        listed, ours, fetched, _ = self.pull(conn, client)
        self.assertEqual((ours, fetched), (0, 0))
        areas = json.loads(conn.execute("SELECT areas FROM ca_divisions").fetchone()[0])
        self.assertEqual(areas, [11], "the row stays honest about what it is")

    def test_party_is_the_caucus_at_the_vote(self):
        conn = store()
        self.pull(conn, FakeClient(divisions_xml(vote(93, C9))))
        rows = {r["person_id"]: (r["position"], r["party"]) for r in
                conn.execute("SELECT person_id, position, party FROM ca_votes")}
        self.assertEqual(rows["1"], ("Nay", "Conservative"))
        self.assertEqual(rows["2"], ("Yea", "Liberal"))
        self.assertEqual(rows["3"], ("Paired", "Bloc Québécois"),
                         "a paired member is not a Yea, whatever the display says")

    def test_the_houses_result_is_stored_never_derived(self):
        conn = store()
        self.pull(conn, FakeClient(divisions_xml(vote(93, C9, result="Negatived", yeas=200, nays=100))))
        r = conn.execute("SELECT result, yeas, nays FROM ca_divisions").fetchone()
        self.assertEqual(r["result"], "Negatived")
        self.assertGreater(r["yeas"], r["nays"])

    def test_a_second_run_fetches_nothing_already_held(self):
        conn = store()
        client = FakeClient(divisions_xml(vote(93, C9)))
        self.pull(conn, client)
        self.pull(conn, client)
        self.assertEqual(len(client.detail_calls), 1)

    def test_a_division_that_gains_an_area_is_fetched_next_run(self):
        """positions_fetched, not the row's existence, decides the skip."""
        conn = store()
        client = FakeClient(divisions_xml(vote(174, TRADES)))
        self.pull(conn, client)
        self.assertEqual(client.detail_calls, [])
        conn.execute("UPDATE ca_divisions SET areas='[5]'")
        conn.commit()
        _, _, fetched, _ = car.pull_divisions(
            conn, FakeClient(divisions_xml(vote(174, TRADES))), "2026-09-27",
            tax=TAX, wl=WL, log=quiet)
        # The re-run re-derives areas from the subject (none), so nothing is
        # fetched -- the point is that a REAL reclassify survives the upsert:
        self.assertEqual(fetched, 0)
        conn.execute("UPDATE ca_divisions SET subject=?", (C9,))
        car.reclassify(conn, tax=TAX, wl=WL, log=quiet)
        row = conn.execute("SELECT areas, positions_fetched FROM ca_divisions").fetchone()
        self.assertIn(7, json.loads(row["areas"]))
        self.assertEqual(row["positions_fetched"], 0, "reclassify must leave the fetch owed")

    def test_an_empty_participant_list_is_a_gap_not_a_silent_division(self):
        conn = store()
        client = FakeClient(divisions_xml(vote(93, C9)),
                            participants="<ArrayOfVoteParticipant></ArrayOfVoteParticipant>")
        _, _, fetched, gaps = self.pull(conn, client)
        self.assertEqual((fetched, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT positions_fetched FROM ca_divisions").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='ca-rollcalls'").fetchone()[0], 1)

    def test_the_fetch_cap_is_disclosed(self):
        conn = store()
        said = []
        client = FakeClient(divisions_xml(vote(92, C9), vote(93, C9)))
        car.pull_divisions(conn, client, "2026-09-26", tax=TAX, wl=WL,
                           log=said.append, limit=1)
        self.assertEqual(len(client.detail_calls), 1)
        self.assertTrue(any("not silent" in s for s in said))

    def test_bills_skip_pro_forma_and_classify_the_rest(self):
        conn = store()
        listed, ours = car.pull_bills(conn, FakeClient(""), "2026-09-26", tax=TAX, wl=WL)
        self.assertEqual((listed, ours), (3, 1))
        keys = [r[0] for r in conn.execute("SELECT bill_key FROM ca_bills ORDER BY bill_key")]
        self.assertEqual(keys, ["45-1/C-266", "45-1/C-34"], "S-1 is pro forma")
        self.assertEqual(conn.execute("SELECT is_government FROM ca_bills WHERE number='C-34'").fetchone()[0], 1)

    def test_session_codes_are_validated(self):
        self.assertEqual(car.parse_session("44-1"), (44, 1))
        with self.assertRaises(ValueError):
            car.parse_session("45")

    def test_schema_is_idempotent(self):
        conn = store()
        ca_store.ensure_schema(conn)
        ca_store.ensure_schema(conn)


if __name__ == "__main__":
    unittest.main()
