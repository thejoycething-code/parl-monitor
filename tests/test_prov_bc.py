"""British Columbia (src/ingest/prov_bc.py). No network: fixtures in tests/fixtures/prov/.

THE PROOF (docs/canada-provinces-scope.md): on 19 February 2026 first
reading of the Gender Ideology and Child Protection Act (Tara Armstrong)
was negatived 38-49 -- Rustad for, Eby against. Refused first reading, the
bill never got a number and is absent from the bills JSON: it is stored
from the transcript alone.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_bc as bc  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
DATE = "2026-02-19"
PARL = {"id": 43, "number": 43, "startDate": "2025-02-18", "endDate": "2026-09-22"}


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def resolver():
    rows = bc.terms_from_members(json.loads(fx("bc_members_43.json"))["data"]["allMemberParliaments"]["nodes"], PARL)
    return pn.Resolver({k: m for k, m, t in rows}, [dict(t, member_key=k) for k, m, t in rows]), rows


class SessionTests(unittest.TestCase):
    def test_the_session_code_and_id(self):
        nodes = json.loads(fx("bc_sessions.json"))["data"]["allSessions"]["nodes"]
        s = bc.find_session(nodes, 43, 2)
        self.assertEqual((s["id"], bc.session_code(s)), (206, "43rd2nd"))
        self.assertIsNone(bc.find_session(nodes, 43, 9))

    def test_a_progress_of_bills_reply_for_another_session_is_refused(self):
        """The trap: an unknown key answers 2006 data without complaint."""
        self.assertTrue(bc.check_bills_session(json.loads(fx("bc_bills_206.json")), "43rd2nd"))
        self.assertFalse(bc.check_bills_session(json.loads(fx("bc_bills_wrong_session.json")), "43rd2nd"))


class RosterTests(unittest.TestCase):
    def test_terms_and_the_undated_party(self):
        r, rows = resolver()
        self.assertEqual(len(rows), 93)            # 95 places less two 'Vacant Seat' rows
        keys = {m["name"]: k for k, m, t in rows}
        # API party is one per parliament: Armstrong shows Independent for all of it,
        # though she voted with the Conservative caucus in early 2025. Not dated, so
        # never used as party_at_vote.
        self.assertEqual(r.party_at(keys["Tara Armstrong"], DATE, 43), None)
        self.assertTrue(all(t["party_dated"] == 0 for _, _, t in rows))

    def test_shared_surnames_resolve_by_initial(self):
        r, rows = resolver()
        keys = {m["name"]: k for k, m, t in rows}
        self.assertEqual(r.resolve("L. Neufeld", DATE, 43)[0], keys["Larry Neufeld"])
        self.assertEqual(r.resolve("K. Neufeld", DATE, 43)[0], keys["Korky Neufeld"])
        self.assertEqual(r.resolve("B. Anderson", DATE, 43)[0], keys["Brittny Anderson"])
        self.assertIsNone(r.resolve("Neufeld", DATE, 43)[0])
        self.assertEqual(r.resolve("Chandra Herbert", DATE, 43)[0], keys["Spencer Chandra Herbert"])
        self.assertEqual(r.resolve("Rattée", DATE, 43)[0], keys["Claire Rattée"])


class HansardTests(unittest.TestCase):
    def test_the_listing_takes_house_transcripts_only(self):
        recs = bc.list_records(json.loads(fx("bc_debates_43rd2nd.json")), "43rd2nd")
        self.assertEqual([(d, part, issue) for d, part, issue, _ in recs],
                         [(DATE, "am", "119"), (DATE, "pm", "120")])
        self.assertEqual(recs[0][3], "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.html")

    def test_the_proof_division(self):
        r, rows = resolver()
        names = {k: m["name"] for k, m, t in rows}
        (d,) = bc.parse_hansard(fx("bc_hansard_n119.html"))
        self.assertEqual(d["heading"], "Gender Ideology and Child Protection Act")
        self.assertEqual(d["result"], "Motion negatived on the following division")
        self.assertEqual(d["printed"], {"Yea": 38, "Nay": 49})
        self.assertEqual(d["anchor"], "119B:1030")
        self.assertEqual(bc.stage_of(d["question"]), "First Reading")
        votes = {}
        for pos in ("Yea", "Nay"):
            for label in d["labels"][pos]:
                key, how = r.resolve(label, DATE, 43)
                self.assertIsNotNone(key, label)
                votes[names[key]] = pos
        self.assertEqual(len(votes), 87)
        self.assertEqual(votes["John Rustad"], "Yea")
        self.assertEqual(votes["Tara Armstrong"], "Yea")
        self.assertEqual(votes["Dallas Brodie"], "Yea")
        self.assertEqual(votes["David Eby"], "Nay")
        self.assertEqual(votes["Adrian Dix"], "Nay")
        self.assertEqual(votes["Niki Sharma"], "Nay")

    def test_vote_on_ignores_amendment_acts(self):
        self.assertEqual(bc.vote_on("the question is second reading of Bill M226, Motor Vehicle "
                                    "Amendment Act (No. 2), 2025."), "motion")
        self.assertEqual(bc.vote_on("The question is the amendment to section 3."), "amendment")


class _Client:
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 1.1

    def __init__(self, pages, posts):
        self.pages, self.posts = pages, posts

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.pages[url]

    def post_json(self, url, body, feed, slug, headers=None, timeout=None):
        q = json.loads(body)["query"]
        return self.posts["sessions" if "allSessions" in q else "members"]


class CollectTests(unittest.TestCase):
    def run_collect(self, bills_reply):
        conn = db.init_db(db.connect(":memory:"))
        n119 = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.html"
        n120 = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219pm-Hansard-n120.html"
        texts = {bc.BILL_TEXT.format(b["files"]["nodes"][0]["path"]): "<p>An Act.</p>"
                 for b in json.loads(bills_reply) if b["files"]["nodes"]}
        client = _Client(dict(texts, **{
                          bc.DEBATES.format("43rd2nd"): fx("bc_debates_43rd2nd.json"),
                          bc.BILLS.format(206): bills_reply,
                          n119: "<p class=\"Hansard\">Hansard</p>" + fx("bc_hansard_n119.html"),
                          n120: "<p class=\"Hansard\">Hansard</p><p class=\"Subject-Heading\">Nothing divided</p>"}),
                         {"sessions": json.loads(fx("bc_sessions.json")),
                          "members": json.loads(fx("bc_members_43.json"))})
        ctx = Context(conn, client, "bc", since=DATE, until=DATE, log=lambda *a: None)
        stats = bc.collect(ctx, session="43-2")
        return conn, ctx, stats

    def test_the_proof_lands_in_the_store(self):
        conn, ctx, stats = self.run_collect(fx("bc_bills_206.json"))
        self.assertEqual((stats["records_read"], stats["divisions"], stats["tally_gaps"]), (2, 1, 0))
        row = conn.execute("SELECT division_key, bill_key, stage, yeas, nays, positions_ok, areas, result "
                           "FROM prov_divisions WHERE kind='recorded'").fetchone()
        self.assertEqual(tuple(row), ("bc-43-2-2026-02-19-119.1",
                                      "bc-43-2/x-gender-ideology-and-child-protection-act", "First Reading",
                                      38, 49, 1, "[3, 6]", "Motion negatived on the following division"))
        bill = conn.execute("SELECT number, title_en, sponsor, latest_stage, areas FROM prov_bills "
                            "WHERE bill_key='bc-43-2/x-gender-ideology-and-child-protection-act'").fetchone()
        self.assertEqual(tuple(bill), (None, "Gender Ideology and Child Protection Act", "Tara Armstrong",
                                       "First Reading refused", "[3, 6]"))
        rustad = conn.execute("SELECT v.position, v.party_at_vote FROM prov_votes v JOIN prov_members m "
                              "ON m.prov='bc' AND m.member_key=v.member_key WHERE m.surname='Rustad'").fetchone()
        self.assertEqual(tuple(rustad), ("Yea", None))       # BC party is undated: never joined
        self.assertEqual(ctx.gaps, [])

    def test_a_reply_for_the_wrong_session_is_a_gap_and_stores_no_bills(self):
        conn, ctx, stats = self.run_collect(fx("bc_bills_wrong_session.json"))
        self.assertTrue(any("answered another session" in g for g in ctx.gaps))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_bills WHERE number IS NOT NULL").fetchone()[0], 0)

    def test_no_voice_row_for_a_day_with_only_half_its_transcripts_read(self):
        conn = db.init_db(db.connect(":memory:"))
        ps.store_bill(conn, {"bill_key": "bc-43-2/1", "prov": "bc", "legislature": 43, "session": 2,
                             "number": "1", "stages": [{"stage": "First Reading", "date": DATE}]})
        ctx = Context(conn, _Client({}, {}), "bc", log=lambda *a: None)
        self.assertEqual(bc.store_voice(ctx, 43, 2, set()), 0)
        self.assertEqual(bc.store_voice(ctx, 43, 2, {DATE}), 1)
        row = conn.execute("SELECT kind, stage, yeas FROM prov_divisions").fetchone()
        self.assertEqual(tuple(row), ("voice", "First Reading", None))


if __name__ == "__main__":
    unittest.main()
