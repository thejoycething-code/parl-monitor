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

    def test_the_39th_and_40th_file_names_are_listed(self):
        """'20100525am-Hansard-v18n6.htm': volume and number. Until 2 October
        2026 the 39th and 40th Parliaments listed no transcript at all."""
        listing = json.loads(fx("bc_debates_39th2nd_trim.json"))
        recs = bc.list_records(listing, "39th2nd")
        self.assertEqual([(d, part, issue) for d, part, issue, _ in recs],
                         [("2010-05-25", "am", "6"), ("2010-05-25", "pm", "7")])
        self.assertEqual(recs[0][3], "https://lims.leg.bc.ca/hdms/file/Debates/39th2nd/20100525am-Hansard-v18n6.htm")
        self.assertEqual(bc.unread_transcripts(listing), [])
        listing["allHansardFileAttributes"]["nodes"].append({"fileName": "20100526am-Hansard-x9.htm"})
        self.assertEqual(bc.unread_transcripts(listing), ["20100526am-Hansard-x9.htm"])

    ERAS = (("bc_hansard_20100525am_v18n6.htm", [(None, "Committee of the Whole", 31, 44, "S. Simpson")]),
            # '<table border="0" ... class="DivisionTable">': the class not first
            ("bc_hansard_20111019pm_v26n1.htm", [(None, "Second Reading", 43, 32, "Rustad")]),
            # the names run on into a second table after a page break
            ("bc_hansard_20120530pm_v40n1.htm", [(None, "Motion", 45, 38, "Rustad")]),
            ("bc_hansard_20141023am_v16n2.htm", [(None, "Motion", 42, 27, "Horne")]),
            # a StyleLine left open before its table
            ("bc_hansard_20141120am_v18n2.htm", [(None, "Committee of the Whole", 33, 41, "Hammell"),
                                                 (None, "Committee of the Whole", 33, 40, "Hammell")]),
            # '[ Page 8656 ]' printed inside the cell before 'NAYS — 45'
            ("bc_hansard_20150525_pagenumber.htm", [(None, "Committee of the Whole", 31, 45, "Hammell")]),
            # '<TABLE class=DivisionTable>', '<P class=StyleLine>'
            ("bc_hansard_20150526pm_v27n4.htm", [(None, "Third Reading", 35, 41, "Hammell"),
                                                 (None, "Third Reading", 41, 35, "Horne")]),
            ("bc_hansard_20170626pm_n4.html", [("4B:1345", "First Reading", 42, 44, "Kyllo"),
                                               ("4B:1355", "First Reading", 42, 44, "Kyllo")]),
            ("bc_hansard_20210602pm_n82.html", [("82B:1845", "Committee of the Whole", 29, 55, "Ashton")]),
            ("bc_hansard_n119.html", [("119B:1030", "First Reading", 38, 49, "Loewen")]))

    def test_every_markup_since_2009_is_read(self):
        """'DivisionTable' with <th> headers (2026), with <td><p
        class="DivisionHeader"> headers (2009-2017: the 19 gaps of 2017), and
        'division-table' with hyphenated classes (2018-2024: 725 sittings
        read as 0 divisions)."""
        for name, want in self.ERAS:
            page = fx(name)
            got = [(d["anchor"], bc.stage_of(d["question"] or d["business"]), d["printed"].get("Yea"),
                    d["printed"].get("Nay"), d["labels"]["Yea"][0]) for d in bc.parse_hansard(page)]
            self.assertEqual(got, want, name)
            for d in bc.parse_hansard(page):
                self.assertEqual({k: len(v) for k, v in d["labels"].items()}, d["printed"], name)
            self.assertEqual(len(bc._DIVISION_WORDS.findall(page)), len(want), name)
        bill = bc.bill_for(bc.parse_hansard(fx("bc_hansard_20170626pm_n4.html"))[0], {}, 41, 1)
        self.assertEqual(bill, ("bc-41-1/2", None))                    # 'BILL 2 — ...'

    def test_a_unanimous_division_without_names_is_stored_untrusted_not_owed(self):
        """'Motion approved unanimously on a division. [See Votes and
        Proceedings.]' (6 May 2025): a division, but the transcript prints no
        names. The Voting Records index cites it; it must not read as a
        sitting with no division, nor as a gap a re-read could close."""
        (d,) = bc.parse_hansard(fx("bc_hansard_20250506am_n56.html"))
        self.assertTrue(d["no_names"])
        self.assertEqual(bc.stage_of(d["question"]), "First Reading")
        self.assertEqual(d["result"], "Motion approved unanimously on a division. [See Votes and Proceedings.]")
        self.assertEqual(bc.bill_for(d, {}, 43, 1), ("bc-43-1/M213", None))
        # and without the article, in committee (28 March 2023)
        (c,) = bc.parse_hansard(fx("bc_hansard_20230328am_n291.html"))
        self.assertEqual((c["no_names"], c["result"]),
                         (True, "Motion approved unanimously on division. [See Votes and Proceedings.]"))
        conn = db.init_db(db.connect(":memory:"))
        url = "https://lims.leg.bc.ca/hdms/file/Debates/43rd1st/20250506am-Hansard-n56.html"
        ctx = Context(conn, _Client({url: fx("bc_hansard_20250506am_n56.html")}, {}), "bc", log=lambda *a: None)
        ctx.tax = bc.pc.load_taxonomy()
        stored, gaps = bc.read_sitting(ctx, 43, 1, "2025-05-06", "am", "56", url, pn.Resolver({}, []),
                                       bc.pc.load_watchlist("bc"), {})
        self.assertEqual((len(stored), gaps), (1, 0))
        row = conn.execute("SELECT positions_ok, yeas, tally_note FROM prov_divisions").fetchone()
        self.assertEqual(tuple(row)[:2], (0, None))
        self.assertTrue(row[2].startswith("no names"))
        self.assertEqual(ps.summary(conn, "bc")["recorded_no_names"], 1)
        self.assertEqual(ps.summary(conn, "bc")["recorded_gap"], 0)
        self.assertEqual(tuple(conn.execute("SELECT status, divisions FROM prov_sittings").fetchone()), ("ok", 1))

    def test_vote_on_ignores_amendment_acts(self):
        self.assertEqual(bc.vote_on("the question is second reading of Bill M226, Motor Vehicle "
                                    "Amendment Act (No. 2), 2025."), "motion")
        self.assertEqual(bc.vote_on("The question is the amendment to section 3."), "amendment")


CON, IND, NDP = ("Conservative Party of British Columbia", "Independent",
                  "British Columbia New Democratic Party")
LIB, UNITED = "British Columbia Liberal Party", "British Columbia United"


def store_43(conn):
    """The 43rd Parliament's roster terms (api) in a store."""
    for key, m, t in resolver()[1]:
        ps.upsert_member(conn, "bc", key, name=m["name"], surname=m["surname"], given=m["given"],
                         riding=m["riding"], party=m["party"])
        ps.replace_terms(conn, "bc", key, [t], "api", legislature=43)
    return {m["name"]: k for k, m, t in resolver()[1]}


def read_list(conn, name, date, leg=43):
    """Resolve one fixture list against the store's roster and record it."""
    parsed = bc.parse_member_list(fx(name))
    pairs, problems = bc.resolve_member_list(parsed, pn.Resolver.from_conn(conn, "bc"), date, leg)
    for key, party in pairs:
        bc.extend_party(conn, key, leg, party, date)
    return parsed, pairs, problems


class PartyListTests(unittest.TestCase):
    """Each House issue's PDF prints the Assembly's list of members with
    party, and the standings: the dated source the API is not."""

    LISTS = (("bc_hansard_members_20090825.txt", 39, "2009-08-25", 85),
             ("bc_hansard_members_20210412.txt", 42, "2021-04-12", 87),
             ("bc_hansard_members_20240220.txt", 42, "2024-02-20", 87),
             ("bc_hansard_members_20250218.txt", 43, "2025-02-18", 93),
             ("bc_hansard_members_20250402.txt", 43, "2025-04-02", 93),
             ("bc_hansard_members_20260219.txt", 43, "2026-02-19", 93))

    def test_three_layouts_add_up_to_their_standings(self):
        for name, leg, date, n in self.LISTS:
            p = bc.parse_member_list(fx(name))
            self.assertEqual((p["parliament"], p["date"], len(p["entries"])), (leg, date, n), name)
            self.assertIsNone(bc.tally_member_list(p), name)

    def test_the_39th_small_capitals(self):
        """'van Dongen, John (l)', 'huntington, Vicki (ind.)', 'Y amamoto'."""
        p = bc.parse_member_list(fx("bc_hansard_members_20090825.txt"))
        self.assertEqual(p["standings"], {LIB: 49, NDP: 35, IND: 1})
        by = {pn.squash(e["pre"]): e["party"] for e in p["entries"]}
        self.assertEqual((by["vandongen"], by["huntington"], by["yamamoto"], by["dix"]), (LIB, IND, LIB, NDP))

    def test_the_43rd_by_party_with_two_entries_on_a_line(self):
        conn = db.init_db(db.connect(":memory:"))
        keys = store_43(conn)
        p, pairs, problems = read_list(conn, "bc_hansard_members_20260219.txt", "2026-02-19")
        self.assertEqual(problems, [])
        self.assertEqual(len(pairs), 93)
        got = dict(pairs)
        self.assertEqual(got[keys["Jeremy Valeriote"]], "British Columbia Green Party")
        self.assertEqual(got[keys["Rob Botterell"]], "British Columbia Green Party")
        # the API calls these Independent for the whole parliament; that day
        # they sat with the Conservatives
        for name in ("Bruce Banman", "Peter Milobar", "Teresa Wat", "Á'a:líya Warbus"):
            self.assertEqual(got[keys[name]], CON, name)
        self.assertEqual(got[keys["Larry Neufeld"]], CON)
        self.assertEqual(got[keys["Korky Neufeld"]], CON)

    def test_a_list_that_does_not_add_up_is_refused(self):
        text = fx("bc_hansard_members_20250402.txt").replace(
            "Kealy, Jordan ............................................................. Peace River North\n", "")
        p = bc.parse_member_list(text)
        self.assertIn("against standings", bc.tally_member_list(p))
        # a heading we cannot name leaves the entries under it partyless
        text = fx("bc_hansard_members_20250402.txt").replace("INDEPENDENT", "ONE NEW CAUCUS")
        self.assertIn("no party", bc.tally_member_list(bc.parse_member_list(text)))


class DatedPartyTests(unittest.TestCase):
    """Tara Armstrong went Independent between 18 February and 2 April
    2025; Elenore Sturko between 2 April 2025 and 19 February 2026; Adrian
    Dix never changed."""

    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        self.keys = store_43(self.conn)
        for name, date in (("bc_hansard_members_20250218.txt", "2025-02-18"),
                           ("bc_hansard_members_20250402.txt", "2025-04-02"),
                           ("bc_hansard_members_20260219.txt", "2026-02-19")):
            _, _, problems = read_list(self.conn, name, date)
            self.assertEqual(problems, [], name)
        self.r = pn.Resolver.from_conn(self.conn, "bc")

    def party(self, name, date):
        return self.r.party_at(self.keys[name], date, 43)

    def test_one_who_went_independent(self):
        self.assertEqual(self.party("Tara Armstrong", "2025-02-18"), CON)
        self.assertIsNone(self.party("Tara Armstrong", "2025-03-10"))     # the change lies here: no party
        self.assertEqual(self.party("Tara Armstrong", "2025-04-02"), IND)
        self.assertEqual(self.party("Tara Armstrong", "2025-10-01"), IND)  # Independent on both sides
        self.assertEqual(self.party("Elenore Sturko", "2025-04-02"), CON)
        self.assertIsNone(self.party("Elenore Sturko", "2025-10-01"))
        self.assertEqual(self.party("Elenore Sturko", "2026-02-19"), IND)

    def test_one_who_never_changed(self):
        for date in ("2025-02-18", "2025-03-10", "2025-10-01", "2026-02-19"):
            self.assertEqual(self.party("Adrian Dix", date), NDP)
        self.assertIsNone(self.party("Adrian Dix", "2026-03-01"))         # after the last list read

    def test_the_change_window_is_what_bisection_narrows(self):
        windows = bc.change_windows(self.conn, 43)
        self.assertIn(("2025-02-18", "2025-04-02"), windows)
        self.assertIn(("2025-04-02", "2026-02-19"), windows)

    def test_one_who_crossed_the_floor_in_the_42nd(self):
        """Bruce Banman, elected a BC Liberal in 2020, sat as a Conservative
        by February 2024; the API shows him Conservative for the whole 42nd.
        Peter Milobar stayed in the party that renamed itself BC United."""
        conn = db.init_db(db.connect(":memory:"))
        parl = {"id": 42, "number": 42, "startDate": "2020-12-07", "endDate": "2024-09-21"}
        rows = bc.terms_from_members(json.loads(fx("bc_members_42.json"))["data"]["allMemberParliaments"]["nodes"],
                                     parl)
        for key, m, t in rows:
            ps.upsert_member(conn, "bc", key, name=m["name"], surname=m["surname"], given=m["given"])
            ps.replace_terms(conn, "bc", key, [t], "api", legislature=42)
        keys = {m["name"]: k for k, m, t in rows}
        self.assertEqual(next(t["party"] for k, m, t in rows if k == keys["Bruce Banman"]), CON)  # the API
        for name, date in (("bc_hansard_members_20210412.txt", "2021-04-12"),
                           ("bc_hansard_members_20240220.txt", "2024-02-20")):
            _, pairs, problems = read_list(conn, name, date, leg=42)
            self.assertEqual((problems, len(pairs)), ([], 87), name)
        r = pn.Resolver.from_conn(conn, "bc")
        self.assertEqual(r.party_at(keys["Bruce Banman"], "2021-04-12", 42), LIB)
        self.assertIsNone(r.party_at(keys["Bruce Banman"], "2023-10-01", 42))
        self.assertEqual(r.party_at(keys["Bruce Banman"], "2024-02-20", 42), CON)
        self.assertEqual(r.party_at(keys["Peter Milobar"], "2021-04-12", 42), LIB)
        self.assertEqual(r.party_at(keys["Peter Milobar"], "2024-02-20", 42), UNITED)
        self.assertEqual(r.party_at(keys["Adrian Dix"], "2022-11-01", 42), NDP)

    def test_members_the_39th_roster_lacks_are_found_on_the_list(self):
        """The API's roster of the 39th lists the members at its end: Gordon
        Campbell, Iain Black and Barry Penner, who resigned in 2011-12, are
        missing. The 25 August 2009 list names them; allMembers knows them;
        surname, given name and riding together make them members that day."""
        conn = db.init_db(db.connect(":memory:"))
        parl = {"id": 39, "number": 39, "startDate": "2009-08-25", "endDate": "2013-04-16"}
        for key, m, t in bc.terms_from_members(
                json.loads(fx("bc_members_39.json"))["data"]["allMemberParliaments"]["nodes"], parl):
            ps.upsert_member(conn, "bc", key, name=m["name"], surname=m["surname"], given=m["given"])
            ps.replace_terms(conn, "bc", key, [t], "api", legislature=39)
        self.assertIsNone(pn.Resolver.from_conn(conn, "bc").resolve("Campbell", "2009-08-25", 39)[0])
        url = bc.PDF_FILE.format("/Debates/39th1st/H0825am-01.pdf")
        ctx = Context(conn, _Client({}, {"all": json.loads(fx("bc_all_members_trim.json"))},
                                    {url: b"bc_hansard_members_20090825.txt"}), "bc", log=lambda *a: None)
        saved, bc.pdf_text = bc.pdf_text, lambda raw, pages=None: fx(raw.decode())
        try:
            got = bc.read_party_list(ctx, 39, "2009-08-25", url, pn.Resolver.from_conn(conn, "bc"))
        finally:
            bc.pdf_text = saved
        self.assertEqual(len(got["pairs"]), 85)
        self.assertEqual(ctx.gaps, [])
        self.assertEqual(ctx.bc_members_added, 3)
        r = pn.Resolver.from_conn(conn, "bc")
        self.assertEqual(r.resolve("Campbell", "2009-08-25", 39)[0], "166")
        self.assertEqual(r.resolve("I. Black", "2009-08-25", 39)[0], "155")
        self.assertEqual(r.resolve("D. Black", "2009-08-25", 39)[0], "156")
        self.assertEqual(r.resolve("Penner", "2009-08-25", 39)[0], "239")
        self.assertIsNone(r.resolve("Campbell", "2009-09-30", 39)[0])     # only the sittings seen listed
        self.assertEqual(r.party_at("166", "2009-08-25", 39), LIB)
        # 2010's division lists print "Herbert": a reviewed other surname
        self.assertIsNone(r.resolve("Herbert", "2009-08-25", 39)[0])
        self.assertEqual(r.with_record("bc").resolve("Herbert", "2009-08-25", 39), ("13", "other-surname"))

    def test_a_bare_surname_is_the_one_the_list_does_not_name_by_initial(self):
        """3 May 2011: 'Black' and 'D. Black' in one division are Iain and
        Dawn Black. With no 'D. Black' the bare 'Black' stays unresolved."""
        r = pn.Resolver({"155": {"surname": "Black", "given": "Iain"}, "156": {"surname": "Black", "given": "Dawn"}},
                        [{"member_key": k, "legislature": 39, "start": "2009-08-25", "end": "2013-04-16"}
                         for k in ("155", "156")])
        votes = [dict(zip(("member_key", "how"), r.resolve(label, "2011-05-03", 39)), raw_label=label)
                 for label in ("Black", "D. Black")]
        self.assertEqual(votes[0]["member_key"], None)
        bc.settle_by_elimination(votes, r, "2011-05-03", 39)
        self.assertEqual([v["member_key"] for v in votes], ["155", "156"])
        alone = [dict(zip(("member_key", "how"), r.resolve("Black", "2011-05-03", 39)), raw_label="Black")]
        bc.settle_by_elimination(alone, r, "2011-05-03", 39)
        self.assertIsNone(alone[0]["member_key"])

    def test_a_given_name_run_into_its_honorific(self):
        """'Weaver, Dr.Andrew' (41st Parliament, November 2017)."""
        self.assertEqual(bc._given_tokens("Dr.Andrew"), ["andrew"])
        self.assertEqual(bc._given_tokens("Hon. Tamara / Laanas"), ["tamara", "laanas"])

    def test_a_party_left_and_rejoined_keeps_three_terms(self):
        conn = db.init_db(db.connect(":memory:"))
        for date, party in (("2020-01-01", CON), ("2020-03-01", IND), ("2020-05-01", CON), ("2020-02-01", CON)):
            bc.extend_party(conn, "9", 43, party, date)
        rows = conn.execute("SELECT party, start, end FROM prov_member_terms ORDER BY start").fetchall()
        self.assertEqual([tuple(r) for r in rows], [(CON, "2020-01-01", "2020-02-01"),
                                                    (IND, "2020-03-01", "2020-03-01"),
                                                    (CON, "2020-05-01", "2020-05-01")])
        # two parties on one day: none that day
        self.assertEqual(bc.extend_party(conn, "9", 43, IND, "2020-05-01"), "conflict")
        self.assertIsNone(self.resolver_of(conn).party_at("9", "2020-05-01", 43))

    @staticmethod
    def resolver_of(conn):
        return pn.Resolver({}, [dict(zip(("member_key", "legislature", "party", "start", "end", "party_dated",
                                          "source"), t)) for t in conn.execute(
            "SELECT member_key, legislature, party, start, end, party_dated, source FROM prov_member_terms")])

    def test_a_list_printing_another_days_parties_is_refuted_by_its_neighbours(self):
        """The 3 October 2022 morning issue prints 2024's parties; the
        sittings either side print 2022's. A list seen inside a run that was
        only assumed splits the run; once the sittings either side are read
        and agree with each other, the odd list is dropped."""
        conn = db.init_db(db.connect(":memory:"))
        ctx = Context(conn, _Client({}, {}), "bc", log=lambda *a: None)
        bc.extend_party(conn, "7", 42, LIB, "2022-02-08")
        bc.extend_party(conn, "7", 42, LIB, "2023-02-06")
        self.assertEqual(self.resolver_of(conn).party_at("7", "2022-06-01", 42), LIB)   # assumed run
        self.assertEqual(bc.extend_party(conn, "7", 42, CON, "2022-10-03"), "split")
        self.assertIsNone(self.resolver_of(conn).party_at("7", "2022-06-01", 42))       # no longer assumed
        self.assertIn(("7", "2022-10-03"), bc.lone_lists(conn, 42))
        dates = ["2022-02-08", "2022-05-30", "2022-10-03", "2022-10-04", "2023-02-06"]
        self.assertEqual(bc.refute_lone_lists(ctx, 42, dates, set()), 0)    # its neighbours not read yet
        bc.extend_party(conn, "7", 42, LIB, "2022-10-04")
        bc.extend_party(conn, "7", 42, LIB, "2022-05-30")
        self.assertEqual(bc.refute_lone_lists(ctx, 42, dates, {"2022-05-30", "2022-10-04"}), 1)
        rows = conn.execute("SELECT party, start, end FROM prov_member_terms").fetchall()
        self.assertEqual([tuple(r) for r in rows], [(LIB, "2022-02-08", "2023-02-06")])
        self.assertTrue(any("is not the day's" in g for g in ctx.gaps))

    def test_the_october_2022_issue_from_end_to_end(self):
        """Three real issues: 2 June 2022, 3 October 2022 a.m. (n221, which
        prints 2024's parties) and 4 October 2022 a.m. Rustad's change
        (BC Liberal to Independent) makes bisection read n221, whose list
        splits the Liberals' assumed run; its neighbours refute it."""
        conn = db.init_db(db.connect(":memory:"))
        parl = {"id": 42, "number": 42, "startDate": "2020-12-07", "endDate": "2024-09-21"}
        for key, m, t in bc.terms_from_members(
                json.loads(fx("bc_members_42.json"))["data"]["allMemberParliaments"]["nodes"], parl):
            ps.upsert_member(conn, "bc", key, name=m["name"], surname=m["surname"], given=m["given"])
            ps.replace_terms(conn, "bc", key, [t], "api", legislature=42)
        keys = {n: k for k, n in conn.execute("SELECT member_key, name FROM prov_members")}
        issues = (("20220602am-Hansard-n219", "bc_hansard_members_220602am.txt"),
                  ("20221003am-Hansard-n221", "bc_hansard_members_221003am.txt"),
                  ("20221004am-Hansard-n223", "bc_hansard_members_221004am.txt"))
        listing = {"allHansardFileAttributes": {"nodes": [
            {"fileName": f + ".html", "published": True, "debateAttributes": {"nodes": [
                {"pdfLink": "/Debates/42nd3rd/{0}.pdf".format(f), "debateType": {"name": "House"}}]}}
            for f, _ in issues]}}
        blobs = {bc.PDF_FILE.format("/Debates/42nd3rd/{0}.pdf".format(f)): name.encode() for f, name in issues}
        ctx = Context(conn, _Client({}, {}, blobs), "bc", log=lambda *a: None)
        saved, bc.pdf_text = bc.pdf_text, lambda raw, pages=None: fx(raw.decode())
        try:
            self.assertEqual(bc.fetch_party_lists(ctx, 42, 3, listing, {"2022-10-04"}), 3)
        finally:
            bc.pdf_text = saved
        r = pn.Resolver.from_conn(conn, "bc")
        for name in ("Mike Bernier", "Bruce Banman"):
            self.assertEqual([r.party_at(keys[name], d, 42) for d in ("2022-06-02", "2022-10-03", "2022-10-04")],
                             [LIB, LIB, LIB], name)
        self.assertEqual([r.party_at(keys["John Rustad"], d, 42) for d in ("2022-06-02", "2022-10-03", "2022-10-04")],
                         [LIB, None, IND])
        self.assertEqual(r.party_at(keys["Elenore Sturko"], "2022-10-03", 42), None)   # elected September 2022
        self.assertEqual(r.party_at(keys["Elenore Sturko"], "2022-10-04", 42), LIB)
        self.assertTrue(any("2022-10-03: that issue's list is not the day's" in g for g in ctx.gaps))

    def test_a_lone_list_between_two_other_parties_leaves_the_day_without_one(self):
        """John Rustad, 2022: BC Liberal to 2 June, the 3 October morning
        issue's 'Conservative', Independent from the afternoon of 4 October."""
        conn = db.init_db(db.connect(":memory:"))
        ctx = Context(conn, _Client({}, {}), "bc", log=lambda *a: None)
        for date, party in (("2022-06-02", LIB), ("2022-10-03", CON), ("2022-10-04", IND), ("2022-10-05", IND)):
            bc.extend_party(conn, "64", 42, party, date)
        dates = ["2022-06-02", "2022-10-03", "2022-10-04", "2022-10-05"]
        self.assertEqual(bc.refute_lone_lists(ctx, 42, dates, {"2022-06-02", "2022-10-04"}), 1)
        r = self.resolver_of(conn)
        self.assertIsNone(r.party_at("64", "2022-10-03", 42))
        self.assertEqual((r.party_at("64", "2022-06-02", 42), r.party_at("64", "2022-10-04", 42)), (LIB, IND))

    def test_a_real_change_is_confirmed_by_the_next_sitting(self):
        conn = db.init_db(db.connect(":memory:"))
        ctx = Context(conn, _Client({}, {}), "bc", log=lambda *a: None)
        bc.extend_party(conn, "7", 42, LIB, "2023-05-11")
        bc.extend_party(conn, "7", 42, CON, "2023-10-02")
        self.assertIn(("7", "2023-10-02"), bc.lone_lists(conn, 42))
        bc.extend_party(conn, "7", 42, CON, "2023-10-03")
        self.assertNotIn(("7", "2023-10-02"), bc.lone_lists(conn, 42))
        self.assertEqual(bc.change_windows(conn, 42), [("2023-05-11", "2023-10-02")])
        dates = ["2023-05-11", "2023-10-02", "2023-10-03"]
        self.assertEqual(bc.refute_lone_lists(ctx, 42, dates, set(dates)), 0)
        self.assertEqual(self.resolver_of(conn).party_at("7", "2023-10-02", 42), CON)


class _Client:
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 1.1

    def __init__(self, pages, posts, blobs=None):
        self.pages, self.posts, self.blobs = pages, posts, blobs or {}

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.pages[url]

    def get_bytes(self, url, feed, slug, archive=True):
        if url not in self.blobs:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.blobs[url]

    def post_json(self, url, body, feed, slug, headers=None, timeout=None):
        q = json.loads(body)["query"]
        if "allMembers " in q:
            return self.posts.get("all")
        return self.posts["sessions" if "allSessions" in q else "members"]


def fxb(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


class VotesAndProceedingsTests(unittest.TestCase):
    """Hansard prints 61 divisions only as 'approved unanimously on a
    division. [See Votes and Proceedings.]'; the V&P prints their names."""

    def test_the_tables_of_four_years(self):
        got = {}
        for name in ("bc_vp_v140312.htm", "bc_vp_v151007.htm", "bc_vp_v181122.htm", "bc_vp_v260421.htm"):
            got[name] = [(t["unanimous"], sorted(t["bills"]), t["printed"], {k: len(v) for k, v in t["labels"].items()})
                         for t in bc.parse_vp(bc.decode_vp(fxb(name)))]
        self.assertEqual(got["bc_vp_v140312.htm"], [(True, ["9"], {"Yea": 80}, {"Yea": 80})])
        # 7 October 2015 is served as UTF-16
        self.assertEqual(got["bc_vp_v151007.htm"], [(True, ["38"], {"Yea": 68}, {"Yea": 68})])
        # a committee section's unanimous division, then two divided ones, then the House's unanimous one
        self.assertEqual([g[:3] for g in got["bc_vp_v181122.htm"]],
                         [(True, ["45"], {"Yea": 17}), (False, ["45"], {"Yea": 43, "Nay": 39}),
                          (False, ["49"], {"Yea": 43, "Nay": 39}), (True, ["50"], {"Yea": 80})])
        self.assertEqual(got["bc_vp_v260421.htm"], [(True, ["14"], {"Yea": 89}, {"Yea": 89})])

    def test_matching_is_in_order_and_checked_by_bill(self):
        tables = bc.parse_vp(bc.decode_vp(fxb("bc_vp_v181122.htm")))
        days = [{"division_key": "bc-41-3-2018-11-22-195.1", "bill_key": "bc-41-3/45"},
                {"division_key": "bc-41-3-2018-11-22-196.1", "bill_key": "bc-41-3/50"}]
        pairs, why = bc.match_vp(days, tables)
        self.assertIsNone(why)
        self.assertEqual([t["printed"]["Yea"] for _, t in pairs], [17, 80])
        # the bill a division names must be among those the table's paragraphs name
        pairs, why = bc.match_vp([dict(days[0], bill_key="bc-41-3/99"), days[1]], tables)
        self.assertIsNone(pairs)
        self.assertIn("do not match", why)
        # with one Hansard division for two unanimous tables, only a bill only one names will do
        pairs, why = bc.match_vp([days[1]], tables)
        self.assertEqual(pairs[0][1]["printed"]["Yea"], 80)
        self.assertIsNone(bc.match_vp([dict(days[1], bill_key="bc-41-3/55")], tables)[0])
        # Hansard prints the House's division before the committee's: by bill, not by order
        pairs, why = bc.match_vp(list(reversed(days)), tables)
        self.assertEqual([(d["bill_key"], t["printed"]["Yea"]) for d, t in pairs],
                         [("bc-41-3/50", 80), ("bc-41-3/45", 17)])
        # two divisions on one bill, out of order: no unique match, so nothing
        self.assertIsNone(bc.match_vp([days[1], dict(days[0], bill_key="bc-41-3/50")], tables)[0])

    def test_a_private_members_bill_matched_by_its_number(self):
        """6 May 2025: two unanimous divisions in the V&P, one of them printed
        with names in Hansard; 'Bill (No. M 213)' names the other."""
        tables = bc.parse_vp(bc.decode_vp(fxb("bc_vp_v250506.htm")))
        self.assertEqual([(t["unanimous"], sorted(t["bills"]), t["printed"].get("Yea")) for t in tables],
                         [(True, ["M213"], 92), (False, ["5"], 41), (True, [], 89)])
        pairs, why = bc.match_vp([{"division_key": "bc-43-1-2025-05-06-56.1", "bill_key": "bc-43-1/M213"}], tables)
        self.assertEqual(pairs[0][1]["printed"]["Yea"], 92)

    def test_a_committee_divided_nemine_contradicente_as_follows(self):
        """6 November 2014: 'the Committee divided, nemine contradicente as
        follows' -- no 'division' in the sentence."""
        (t,) = bc.parse_vp(bc.decode_vp(fxb("bc_vp_v141106.htm")))
        self.assertEqual((t["unanimous"], t["bills"], t["printed"]), (True, {"2"}, {"Yea": 65}))

    def test_the_older_listings_mark_every_file_unpublished(self):
        files = bc._nodes_vp(json.loads(fx("bc_vp_list_39th2nd.json")))
        self.assertEqual(sorted((f["fileName"], f["date"]) for f in files),
                         [("v100325.htm", "2010-03-25"), ("v110214.htm", "2011-02-14")])

    def setup_43(self, note=None):
        conn = db.init_db(db.connect(":memory:"))
        store_43(conn)
        ps.store_division(conn, {
            "division_key": "bc-43-2-2026-04-21-159.1", "prov": "bc", "legislature": 43, "session": 2,
            "date": "2026-04-21", "seq": "159.1", "kind": "recorded", "bill_key": "bc-43-2/14",
            "stage": "Third Reading", "positions_ok": 0, "votes": [],
            "tally_note": note or ("no names: the transcript records 'Motion approved unanimously on a division. "
                                   "[See Votes and Proceedings.]'; the names are printed only in the Votes and "
                                   "Proceedings")})
        url = bc.VP_FILE.format("/ldp/43rd2nd/votes", "v260421.htm")
        client = _Client({bc.VP_LIST.format("43rd2nd"): fx("bc_vp_list_43rd2nd.json")}, {},
                         {url: fxb("bc_vp_v260421.htm")})
        return conn, Context(conn, client, "bc", log=lambda *a: None)

    def test_the_names_of_a_unanimous_third_reading(self):
        """Bill 14, Forests Statutes Amendment Act, 2026, third reading, 21
        April 2026: 'Motion agreed to nemine contradicente', Yeas — 89."""
        conn, ctx = self.setup_43()
        self.assertEqual(bc.vp_names(ctx, 43, 2, "43rd2nd"), {"vp_named": 1, "vp_not_named": 0})
        row = conn.execute("SELECT positions_ok, yeas, nays, tally_note FROM prov_divisions").fetchone()
        self.assertEqual(tuple(row)[:3], (1, 89, None))
        self.assertTrue(row[3].startswith("names from the Votes and Proceedings: https://lims.leg.bc.ca/pdms/ldp/"
                                          "43rd2nd/votes/v260421.htm"))
        names = {r[0] for r in conn.execute("SELECT m.name FROM prov_votes v JOIN prov_members m "
                                            "ON m.member_key=v.member_key AND m.prov='bc'")}
        self.assertEqual(len(names), 89)
        self.assertTrue({"David Eby", "John Rustad", "Brittny Anderson", "Larry Neufeld", "Tara Armstrong"} <= names)
        self.assertEqual(ctx.gaps, [])
        # tried once: the next run fetches nothing
        ctx.client.blobs, ctx.client.pages = {}, {}
        self.assertEqual(bc.vp_names(ctx, 43, 2, "43rd2nd"), {})
        self.assertEqual(ctx.gaps, [])

    def test_a_day_the_listing_does_not_hold_stays_no_names_and_is_not_tried_again(self):
        conn, ctx = self.setup_43()
        conn.execute("UPDATE prov_divisions SET date='2026-04-22'")
        self.assertEqual(bc.vp_names(ctx, 43, 2, "43rd2nd"), {"vp_named": 0, "vp_not_named": 1})
        note = conn.execute("SELECT tally_note FROM prov_divisions").fetchone()[0]
        self.assertTrue(note.startswith("no names"))
        self.assertIn("Votes and Proceedings read: no Votes and Proceedings listed for 2026-04-22", note)
        self.assertEqual(bc.vp_names(ctx, 43, 2, "43rd2nd"), {})

    def test_a_failed_fetch_is_tried_again(self):
        conn, ctx = self.setup_43()
        ctx.client.blobs = {}
        self.assertEqual(bc.vp_names(ctx, 43, 2, "43rd2nd"), {"vp_named": 0, "vp_not_named": 0})
        self.assertNotIn("Votes and Proceedings read",
                         conn.execute("SELECT tally_note FROM prov_divisions").fetchone()[0])


N119_PDF = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.pdf"


class CollectTests(unittest.TestCase):
    def setUp(self):
        # The PDF itself is 1.4 MB; its member-list text is the fixture.
        self._pdf_text = bc.pdf_text
        bc.pdf_text = lambda raw, pages=None: fx(raw.decode())

    def tearDown(self):
        bc.pdf_text = self._pdf_text

    def run_collect(self, bills_reply, pdfs=True, conn=None, pages=None):
        conn = conn or db.init_db(db.connect(":memory:"))
        n119 = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.html"
        n120 = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219pm-Hansard-n120.html"
        texts = {bc.BILL_TEXT.format(b["files"]["nodes"][0]["path"]): "<p>An Act.</p>"
                 for b in json.loads(bills_reply) if b["files"]["nodes"]}
        served = dict(texts, **{
            bc.DEBATES.format("43rd2nd"): fx("bc_debates_43rd2nd.json"),
            bc.BILLS.format(206): bills_reply,
            n119: "<p class=\"Hansard\">Hansard</p>" + fx("bc_hansard_n119.html"),
            n120: "<p class=\"Hansard\">Hansard</p><p class=\"Subject-Heading\">Nothing divided</p>",
            # the Voting Records index, cut to letter A: it cites n119
            bc.INDEX.format("43rd2nd"): fx("bc_index_43rd2nd.json"),
            bc.FILE.format("/Index/43rd2nd", "2026-votesmhds.htm"): fx("bc_votes_43rd2nd_main.htm"),
            bc.FILE.format("/Index/43rd2nd", "2026-Votesa.htm"): fx("bc_votes_43rd2nd_a.htm")})
        served.update(pages or {})
        client = _Client(served,
                         {"sessions": json.loads(fx("bc_sessions.json")),
                          "members": json.loads(fx("bc_members_43.json"))},
                         {N119_PDF: b"bc_hansard_members_20260219.txt"} if pdfs else {})
        ctx = Context(conn, client, "bc", since=DATE, until=DATE, log=lambda *a: None)
        stats = bc.collect(ctx, session="43-2")
        return conn, ctx, stats

    def test_the_proof_lands_in_the_store(self):
        conn, ctx, stats = self.run_collect(fx("bc_bills_206.json"))
        self.assertEqual((stats["records_read"], stats["divisions"], stats["tally_gaps"]), (2, 1, 0))
        row = conn.execute("SELECT division_key, bill_key, stage, yeas, nays, positions_ok, areas, result "
                           "FROM prov_divisions WHERE kind='recorded'").fetchone()
        # Area 5 since taxonomy v1.17 (9 October 2026): "gender ideology" is a
        # tier 1 term in the American addendum, filed under sex-based rights.
        self.assertEqual(tuple(row), ("bc-43-2-2026-02-19-119.1",
                                      "bc-43-2/x-gender-ideology-and-child-protection-act", "First Reading",
                                      38, 49, 1, "[3, 5, 6]", "Motion negatived on the following division"))
        bill = conn.execute("SELECT number, title_en, sponsor, latest_stage, areas FROM prov_bills "
                            "WHERE bill_key='bc-43-2/x-gender-ideology-and-child-protection-act'").fetchone()
        self.assertEqual(tuple(bill), (None, "Gender Ideology and Child Protection Act", "Tara Armstrong",
                                       "First Reading refused", "[3, 5, 6]"))
        rustad = conn.execute("SELECT v.position, v.party_at_vote FROM prov_votes v JOIN prov_members m "
                              "ON m.prov='bc' AND m.member_key=v.member_key WHERE m.surname='Rustad'").fetchone()
        # Party at the vote: that sitting's own list of members, not the API's
        self.assertEqual(tuple(rustad), ("Yea", CON))
        banman = conn.execute("SELECT v.party_at_vote, m.party FROM prov_votes v JOIN prov_members m "
                              "ON m.prov='bc' AND m.member_key=v.member_key WHERE m.surname='Banman'").fetchone()
        self.assertEqual(tuple(banman), (CON, IND))
        self.assertEqual(stats["votes_with_party"], "87/87")
        self.assertEqual(ctx.gaps, [])

    def test_a_vote_whose_day_has_no_list_carries_no_party(self):
        conn, ctx, stats = self.run_collect(fx("bc_bills_206.json"), pdfs=False)
        self.assertEqual(stats["votes_with_party"], "0/87")
        self.assertTrue(any("no party at the vote that day" in g for g in ctx.gaps))

    def test_votes_stored_before_the_lists_get_their_party_without_a_transcript(self):
        """The repair of the first backfill: re-running the session reads
        the lists and rewrites party_at_vote; the transcript is not fetched
        again (it was read cleanly)."""
        conn, ctx, _ = self.run_collect(fx("bc_bills_206.json"), pdfs=False)
        ctx.client.blobs = {N119_PDF: b"bc_hansard_members_20260219.txt"}
        ctx.client.pages = {k: v for k, v in ctx.client.pages.items() if "Hansard-n1" not in k}
        stats = bc.collect(ctx, session="43-2")
        self.assertEqual((stats["records_read"], stats["votes_with_party"]), (0, "87/87"))

    def test_a_transcript_that_says_division_but_parses_none_is_a_gap(self):
        """The 725 sittings of 2018-2024 were stored 'ok' with 0 divisions."""
        n120 = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219pm-Hansard-n120.html"
        page = ("<p class=\"Hansard\">Hansard</p><p class=\"StyleLine\">Motion negatived on the following "
                "division:</p><table class=\"NewDivisionMarkup\"><tr><td>YEAS — 1</td></tr></table>")
        conn, ctx, stats = self.run_collect(fx("bc_bills_206.json"), pages={n120: page})
        self.assertTrue(any("prints 1 recorded division(s)" in g and "0 parsed" in g for g in ctx.gaps))
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings WHERE record_url=?", (n120,)).fetchone()[0],
                         "gap")

    def test_a_sitting_stored_with_no_division_but_cited_by_the_index_is_read_again(self):
        """The repair of 2018-2024: no raw copy of those transcripts was kept,
        so the Voting Records index says which to read again."""
        n119 = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.html"
        conn, ctx, _ = self.run_collect(fx("bc_bills_206.json"))
        # as the first backfill left it: read, 'ok', no division
        conn.execute("DELETE FROM prov_votes")
        conn.execute("DELETE FROM prov_divisions WHERE kind='recorded'")
        conn.execute("UPDATE prov_sittings SET divisions=0, status='ok' WHERE record_url=?", (n119,))
        conn.commit()
        conn, ctx, stats = self.run_collect(fx("bc_bills_206.json"), conn=conn)
        self.assertEqual(stats["records_read"], 1)          # n119 only; n120 is not cited
        self.assertEqual(stats["index_misses"], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_divisions WHERE kind='recorded'").fetchone()[0], 1)
        self.assertEqual(ctx.gaps, [])

    def test_a_cited_sitting_that_still_parses_none_is_a_gap(self):
        n119 = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.html"
        conn, ctx, stats = self.run_collect(fx("bc_bills_206.json"),
                                            pages={n119: "<p class=\"Hansard\">Hansard</p><p>No table.</p>"})
        self.assertEqual(stats["index_misses"], 1)
        self.assertTrue(any("Voting Records index cites 1 standing vote(s)" in g for g in ctx.gaps))
        self.assertEqual(conn.execute("SELECT status FROM prov_sittings WHERE record_url=?", (n119,)).fetchone()[0],
                         "gap")

    def test_a_voice_decision_stored_while_the_division_was_unread_is_withdrawn(self):
        conn = db.init_db(db.connect(":memory:"))
        ps.store_bill(conn, {"bill_key": "bc-42-2/6", "prov": "bc", "legislature": 42, "session": 2,
                             "number": "6", "stages": [{"stage": "Third Reading", "date": "2021-06-02"}]})
        ctx = Context(conn, _Client({}, {}), "bc", log=lambda *a: None)
        self.assertEqual(bc.store_voice(ctx, 42, 2, {"2021-06-02"}), 1)
        ps.store_division(conn, {"division_key": "bc-42-2-2021-06-02-82.1", "prov": "bc", "legislature": 42,
                                 "session": 2, "date": "2021-06-02", "kind": "recorded", "bill_key": "bc-42-2/6",
                                 "stage": "Third Reading", "votes": []})
        self.assertEqual(bc.store_voice(ctx, 42, 2, {"2021-06-02"}), 0)
        self.assertEqual([r[0] for r in conn.execute("SELECT kind FROM prov_divisions")], ["recorded"])

    def test_a_roster_reread_keeps_other_parliaments_terms(self):
        """The Alberta fault (ffd13b9e): one parliament's re-read must not
        delete a member's terms in another."""
        conn, ctx, _ = self.run_collect(fx("bc_bills_206.json"))
        key = conn.execute("SELECT member_key FROM prov_members WHERE surname='Banman'").fetchone()[0]
        ps.replace_terms(conn, "bc", key, [{"legislature": 42, "party": LIB, "start": "2020-12-07",
                                            "end": "2024-09-21"}], "api", legislature=42)
        bc.fetch_roster(ctx, bc.find_session(json.loads(fx("bc_sessions.json"))["data"]["allSessions"]["nodes"],
                                             43, 2))
        legs = sorted(r[0] for r in conn.execute("SELECT legislature FROM prov_member_terms WHERE member_key=? "
                                                 "AND source='api'", (key,)))
        self.assertEqual(legs, [42, 43])

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
