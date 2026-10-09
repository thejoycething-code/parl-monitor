"""Swiss Federal Assembly: businesses, Nationalrat and Staenderat votes
(tools/ch_rollcalls.py). No network: the Staenderat sheets and the OData
answers under tests/fixtures/ch are real files saved by the live run of
9 October 2026; the JSON ones are trimmed to a few dozen rows each."""

import gzip
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ch_store, db  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "ch")


def _load():
    spec = importlib.util.spec_from_file_location(
        "ch_rollcalls", os.path.join(ROOT, "tools", "ch_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


chr_ = _load()
TAX = chr_.Taxonomies()


def blob(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def fixture_json(name):
    with gzip.open(os.path.join(FIX, name), "rt", encoding="utf-8") as fh:
        return json.load(fh)


def store():
    return db.init_db(sqlite3.connect(":memory:"))


class FakeClient:
    """Answers by URL substring; anything unmatched is a FetchError (404)."""

    def __init__(self, json_routes=None, byte_routes=None):
        self.json_routes = json_routes or {}
        self.byte_routes = byte_routes or {}
        self.calls = []

    def _find(self, routes, url):
        for needle, answer in routes.items():
            if needle in url:
                return answer
        raise FetchError(url, "ch-rollcalls", "x", 1, "404")

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.calls.append(url)
        answer = self._find(self.json_routes, url)
        return answer(url) if callable(answer) else answer

    def get_bytes(self, url, feed, slug, timeout=None, first_bytes=None, archive=True):
        self.calls.append(url)
        return self._find(self.byte_routes, url)


def business(bid, title, text="", lang="DE", btype="Mo.", period=52, modified="2026-10-01"):
    return {"ID": bid, "BusinessShortNumber": ch_store.short_number(bid),
            "BusinessTypeAbbreviation": btype, "Title": title, "Description": None,
            "SubmittedText": text, "SubmittedBy": "Muster Hans", "BusinessStatusText": "Erledigt",
            "BusinessStatusDate": "/Date(1790899200000)/", "SubmissionDate": "/Date(1757289600000)/",
            "SubmissionCouncilAbbreviation": "NR", "SubmissionLegislativePeriod": period,
            "ResponsibleDepartmentAbbreviation": "EDI", "TagNames": "Gesundheit",
            "Modified": "/Date(1790899200000)/"}


# --- readers -----------------------------------------------------------------------

class ReaderTests(unittest.TestCase):
    def test_rows_reads_both_odata_shapes(self):
        self.assertEqual(chr_.rows({"d": [{"ID": 1}]}), [{"ID": 1}])
        self.assertEqual(chr_.rows({"d": {"results": [{"ID": 2}], "__next": "u"}}), [{"ID": 2}])
        self.assertEqual(chr_.next_link({"d": {"results": [], "__next": "u"}}), "u")
        self.assertIsNone(chr_.next_link({"d": []}))

    def test_fetch_all_follows_next_and_keeps_json(self):
        pages = {"p1": {"d": {"results": [{"ID": 1}], "__next": "https://x/Business?$skiptoken=1"}},
                 "skiptoken": {"d": {"results": [{"ID": 2}]}}}
        client = FakeClient(json_routes={"skiptoken": pages["skiptoken"], "p1": pages["p1"]})
        got = chr_.fetch_all(client, "https://x/Business?p1", "t")
        self.assertEqual([r["ID"] for r in got], [1, 2])
        self.assertIn("$format=json", client.calls[1])

    def test_odata_date_applies_the_offset_in_minutes(self):
        # 2 October 2026 09:34 UTC, +0120 = CEST
        self.assertEqual(chr_.odata_date("/Date(1790933659740+0120)/"), "2026-10-02")
        self.assertEqual(chr_.odata_date("/Date(1789344000000)/"), "2026-09-14")
        # 23:30 UTC is 01:30 the next day in Bern
        self.assertEqual(chr_.odata_date("/Date(1790897400000+0120)/"), "2026-10-02")
        self.assertIsNone(chr_.odata_date(None))

    def test_short_number(self):
        self.assertEqual(ch_store.short_number(20250059), "25.059")
        self.assertEqual(ch_store.short_number(20262001), "26.2001")
        self.assertEqual(ch_store.short_number(20193743), "19.3743")
        self.assertEqual(ch_store.short_number(20170480), "17.480")

    def test_sr_spellings_follow_the_session_name(self):
        self.assertEqual(chr_.sr_spellings("Herbstsession 2026"), ["2026HS", "2026Herbst"])
        self.assertEqual(chr_.sr_spellings("Frühjahrssession 2024"), ["2024FS", "2024Frühjahr"])
        self.assertEqual(chr_.sr_spellings("Sondersession 4. 2026"), [])


# --- the Staenderat sheets ---------------------------------------------------------

class SrSheetTests(unittest.TestCase):
    def test_new_layout_names_only(self):
        s = chr_.parse_sr_sheet(blob("sr_2026HS_DE.xlsx"))
        self.assertEqual(s["declared"], 203)
        self.assertEqual(len(s["votes"]), 203)
        self.assertEqual(len(s["members"]), 46)
        first = next(iter(s["members"].values()))
        self.assertIsNone(first["person_number"])
        self.assertEqual((first["last_name"], first["first_name"], first["canton_name"],
                          first["parl_group"]), ("Binder-Keller", "Marianne", "Aargau", "M-E"))
        v = next(x for x in s["votes"] if x["key"] == "sr-8426")
        self.assertEqual((v["business_id"], v["date"], v["yes"], v["no"], v["abstain"],
                          v["absent"], v["result"]), (20170480, "2026-09-15", 33, 11, 1, 0, "ja"))
        self.assertEqual(v["meaning_no"], "Einzelantrag Stark (Eintreten)")
        cells = [c for c in v["cells"].values() if c]
        self.assertEqual(cells.count("Ja"), 33)
        self.assertEqual(cells.count("Präsident"), 1)

    def test_old_layout_carries_person_numbers_and_padded_meanings(self):
        s = chr_.parse_sr_sheet(blob("sr_2023WS_DE.xlsx"))
        self.assertEqual((s["declared"], len(s["votes"])), (135, 135))
        first = next(iter(s["members"].values()))
        self.assertEqual(first["person_number"], 4249)
        self.assertEqual(first["canton_name"], "AG")
        v = next(x for x in s["votes"] if x["key"] == "sr-6170")
        self.assertEqual(v["meaning_yes"], "Antrag der Kommission")   # was '... | * | *'
        self.assertEqual(v["date"], "2023-12-05")
        self.assertEqual(v["draft_title"][:22], "Botschaft vom 23. Augu")

    def test_a_vote_with_no_business_is_still_read(self):
        s = chr_.parse_sr_sheet(blob("sr_2025WS_DE.xlsx"))
        self.assertEqual((s["declared"], len(s["votes"])), (226, 226))
        v = next(x for x in s["votes"] if x["key"] == "sr-7875")
        self.assertIsNone(v["business_id"])
        self.assertIn("Anwesend", [c for x in s["votes"] for c in x["cells"].values()])

    def test_positions_every_spelling(self):
        self.assertEqual(chr_.sr_position("Entschuldigt gem. Art. 57 Abs. 4"), "Entschuldigt")
        self.assertEqual(chr_.sr_position("entschuldigt"), "Entschuldigt")
        self.assertEqual(chr_.sr_position("Hat nicht teilgenommen"), "Nicht teilgenommen")
        self.assertEqual(chr_.sr_position("Die Präsidentin/der Präsident stimmt nicht"),
                         "Präsident")
        self.assertEqual(chr_.sr_position("ja"), "Ja")
        self.assertIsNone(chr_.sr_position(""))

    def test_not_a_sheet_raises(self):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("xl/worksheets/sheet1.xml",
                        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
                        '2006/main"><sheetData/></worksheet>')
        with self.assertRaises(ValueError):
            chr_.parse_sr_sheet(buf.getvalue())


class SrNameTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        for pn, first, last, canton in ((4249, "Marianne", "Binder-Keller", "Aargau"),
                                        (1, "Hans", "Muster", "Bern"),
                                        (2, "Hans", "Muster", "Zürich")):
            chr_.store_member(self.conn, {"person_number": pn, "first_name": first,
                                          "last_name": last, "canton_name": canton}, "2026-10-09")
        self.names = chr_.SrNames(self.conn)

    def test_number_row_wins(self):
        self.assertEqual(self.names.resolve({"person_number": 77, "last_name": "X",
                                             "first_name": "Y"}), 77)

    def test_name_then_canton(self):
        self.assertEqual(self.names.resolve({"person_number": None, "last_name": "Binder-Keller",
                                             "first_name": "Marianne"}), 4249)
        self.assertEqual(self.names.resolve({"person_number": None, "last_name": "Muster",
                                             "first_name": "Hans", "canton_name": "Zürich"}), 2)

    def test_never_a_guess(self):
        self.assertIsNone(self.names.resolve({"person_number": None, "last_name": "Muster",
                                              "first_name": "Hans"}))
        self.assertIsNone(self.names.resolve({"person_number": None, "last_name": "Nobody",
                                              "first_name": "At All"}))


# --- classification ----------------------------------------------------------------

class ClassifyTests(unittest.TestCase):
    def test_german_and_french_are_unioned(self):
        de = chr_.parse_business(business(20250415, "Medizinisch unterstützte Fortpflanzung "
                                                    "für alleinstehende Frauen"))
        fr = chr_.parse_business(business(20250415, "Procréation médicalement assistée pour "
                                                    "les femmes seules", lang="FR"))
        a_de, a_fr, areas, terms, tier = chr_.classify_business(TAX, de, fr)
        # The Swiss legal term was not in taxonomy-de; since 10 October 2026
        # the approved Swiss additions (taxonomy-atch) know it.
        self.assertEqual(a_de, [10])
        self.assertEqual(a_fr, [10])        # the French list knows PMA
        self.assertEqual(areas, [10])

    def test_watchlist_by_number_not_title(self):
        de = chr_.parse_business(business(20253944, "Rahmenregulierung im Bereich des "
                                                    "assistierten Suizids"))
        _de, _fr, areas, terms, tier = chr_.classify_business(TAX, de, None)
        self.assertEqual(areas, [2])
        self.assertIn("watch:20253944", terms)
        other = chr_.parse_business(business(20990001, "Rahmenregulierung im Bereich des "
                                                       "assistierten Suizids"))
        # The same title under another number lends no WATCH term. (Since the
        # Swiss additions of 10 October 2026 its own words reach area 2.)
        self.assertNotIn("watch:20990001", chr_.classify_business(TAX, other, None)[3])
        self.assertNotIn("watch:20253944", chr_.classify_business(TAX, other, None)[3])

    def test_watchlist_file_is_sound(self):
        wl = ch_store.watchlist()
        self.assertTrue(wl)
        for bid, (areas, why) in wl.items():
            self.assertTrue(20000000 < bid < 21000000, bid)
            self.assertTrue(areas and all(1 <= a <= 13 for a in areas), bid)
            self.assertGreater(len(why or ""), 20, bid)

    def test_a_vote_is_matched_in_both_languages(self):
        own, terms, tier = chr_.classify_own(TAX, {
            "subject": "Vote final", "meaning_yes": "Adopter le projet",
            "meaning_no": "Rejeter le projet",
            "draft_title": "Loi fédérale sur la procréation médicalement assistée"})
        self.assertEqual(own, [10])
        own, _t, _tier = chr_.classify_own(TAX, {"subject": "Schlussabstimmung",
                                                 "draft_title": "Änderung des Sterbehilfe-Rechts"})
        self.assertEqual(own, [2])


# --- the run, end to end on fakes --------------------------------------------------

def nr_vote(vid, bid, session=5215, subject="Vote final", yes="Adopter le projet"):
    return {"ID": vid, "IdSession": session, "BusinessNumber": bid,
            "BusinessShortNumber": ch_store.short_number(bid), "BillTitle": None,
            "Subject": subject, "MeaningYes": yes, "MeaningNo": "Rejeter le projet",
            "VoteEnd": "/Date(1790933659739)/", "VoteEndWithTimezone": "/Date(1790933659740+0120)/"}


def voting(pn, decision, group="V"):
    return {"IdVote": 1, "PersonNumber": pn, "FirstName": "F{0}".format(pn),
            "LastName": "L{0}".format(pn), "CantonName": "Bern", "ParlGroupCode": group,
            "Decision": decision}


SESSIONS = [{"id": 5215, "name": "Herbstsession 2026", "start": "2026-09-14",
             "end": "2026-10-02", "type": 2, "period": 52}]


class NrVoteTests(unittest.TestCase):
    def test_a_procedural_vote_has_no_business(self):
        rec = nr_vote(32185, 20253944)
        rec.update(BusinessNumber=1, BusinessShortNumber="00.000",
                   Subject="Ordnungsantrag Aeschi Thomas (Rückweisung der Motion 23.3456)")
        d = chr_.parse_nr_vote(rec)
        self.assertIsNone(d["business_id"])
        self.assertIsNone(d["short_number"])
        self.assertEqual(d["date"], "2026-10-02")


class RunTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        for s in SESSIONS:
            self.conn.execute("INSERT INTO ch_sessions (session_id, name, start_date, end_date) "
                              "VALUES (?,?,?,?)", (s["id"], s["name"], s["start"], s["end"]))
        self.client = FakeClient(
            json_routes={
                "Vote?": {"d": [nr_vote(38971, 20253944), nr_vote(38969, 20262001,
                                                                  subject=None, yes="x")]},
                "IdVote%20eq%2038971": {"d": [voting(1, 1), voting(2, 2, "S"), voting(3, 1),
                                              voting(4, 5), voting(5, 7)]},
                "Business?": lambda url: {"d": [business(int(i), "Irgendwas") for i in
                                                re.findall(r"ID%20eq%20(\d+)", url)]},
            },
            byte_routes={"Abstimmungen_SR_2026HS": blob("sr_2026HS_DE.xlsx")})

    def run_all(self, today="2026-10-09"):
        nr, sr, gaps, cache, found, nr_gaps = chr_.pull_divisions(
            self.conn, self.client, TAX, today, SESSIONS, log=lambda *a: None)
        chr_.pull_missing_businesses(self.conn, self.client, TAX, today, log=lambda *a: None)
        chr_.derive_division_areas(self.conn, TAX)
        filled, g2 = chr_.backfill_positions(self.conn, self.client, today, SESSIONS, cache,
                                             log=lambda *a: None)
        chr_.session_counts(self.conn, today, SESSIONS, found, nr_gaps)
        return nr, sr, gaps + g2, filled

    def test_nationalrat_positions_only_on_our_ground_with_tallied_counts(self):
        nr, sr, gaps, filled = self.run_all()
        self.assertEqual(nr, 2)
        self.assertEqual(sr, 203)
        row = self.conn.execute("SELECT areas, yes, no, absent, counts_from, positions, result "
                                "FROM ch_divisions WHERE division_key='nr-38971'").fetchone()
        self.assertEqual(json.loads(row[0]), [2])            # from the watched business
        self.assertEqual(row[1:], (2, 1, 1, "tallied", 5, None))
        off = self.conn.execute("SELECT positions, yes FROM ch_divisions "
                                "WHERE division_key='nr-38969'").fetchone()
        self.assertEqual(off, (0, None))                     # not ours: no positions fetched
        pos = dict(self.conn.execute("SELECT person_number, position FROM ch_votes "
                                     "WHERE division_key='nr-38971'"))
        self.assertEqual(pos[5], "Präsident")
        self.assertEqual(pos[4], "Nicht teilgenommen")

    def test_unresolved_staenderat_names_are_dropped_and_recorded(self):
        # Make one SR vote ours by watching its business, with nobody in ch_members.
        self.conn.execute("INSERT INTO ch_businesses (business_id, areas) VALUES (20170480, '[2]')")
        nr, sr, gaps, filled = self.run_all()
        row = self.conn.execute("SELECT positions, yes, counts_from FROM ch_divisions "
                                "WHERE division_key='sr-8426'").fetchone()
        self.assertEqual(row, (0, 33, "published"))
        gap = self.conn.execute("SELECT detail FROM gaps WHERE detail LIKE 'sr sr-8426%'").fetchone()
        self.assertIn("Binder-Keller, Marianne", gap[0])

    def test_resolved_staenderat_positions_are_stored(self):
        self.conn.execute("INSERT INTO ch_businesses (business_id, areas) VALUES (20170480, '[2]')")
        s = chr_.parse_sr_sheet(blob("sr_2026HS_DE.xlsx"))
        for i, m in enumerate(s["members"].values(), start=1):
            chr_.store_member(self.conn, dict(m, person_number=i), "2026-10-09")
        self.run_all()
        (n,) = self.conn.execute("SELECT COUNT(*) FROM ch_votes WHERE division_key='sr-8426'"
                                 ).fetchone()
        self.assertEqual(n, 46)

    def test_a_second_run_adds_nothing_and_completes_the_session_late(self):
        self.run_all("2026-10-09")
        self.assertIsNone(self.conn.execute(
            "SELECT complete_at FROM ch_sessions WHERE session_id=5215").fetchone()[0])
        nr, sr, gaps, filled = self.run_all("2026-10-30")
        self.assertEqual((nr, sr), (0, 0))
        self.assertEqual(self.conn.execute(
            "SELECT complete_at, nr_votes, sr_votes FROM ch_sessions WHERE session_id=5215"
        ).fetchone(), ("2026-10-30", 2, 203))

    def test_a_missing_staenderat_sheet_is_a_gap_only_after_the_grace(self):
        self.client.byte_routes = {}
        _nr, _sr, gaps, _cache, found, _g = chr_.pull_divisions(
            self.conn, self.client, TAX, "2026-10-09", SESSIONS, log=lambda *a: None)
        self.assertEqual((gaps, found[5215]), (0, False))
        _nr, _sr, gaps, _cache, found, _g = chr_.pull_divisions(
            self.conn, self.client, TAX, "2026-10-30", SESSIONS, log=lambda *a: None)
        self.assertEqual(gaps, 1)
        # every spelling was tried before giving up
        self.assertTrue(any("2026Herbst" in u for u in self.client.calls))


class BatchTests(unittest.TestCase):
    def test_older_businesses_are_read_forty_to_a_request(self):
        conn = store()
        client = FakeClient(json_routes={"Business?": lambda url: {"d": [
            business(int(i), "Irgendwas") for i in re.findall(r"ID%20eq%20(\d+)", url)
            if int(i) != 20100005]}})
        ids = list(range(20100001, 20100001 + 50))
        got, gaps = chr_.refetch_businesses(conn, client, TAX, "2026-10-09", ids,
                                            log=lambda *a: None)
        self.assertEqual(len(client.calls), 4)        # 2 batches x DE and FR
        self.assertEqual((got, gaps), (49, 1))        # the one the service lacks is a gap
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ch_businesses").fetchone()[0], 49)


class SchemaTests(unittest.TestCase):
    def test_tables_are_declared_and_created(self):
        conn = store()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ch_store.TABLES:
            self.assertIn(t, have)
            self.assertIn(t, db.TABLES)


class FixtureTests(unittest.TestCase):
    """The OData answers saved on 9 October 2026 parse as the live run did."""

    def test_votes_and_positions(self):
        votes = [chr_.parse_nr_vote(r) for r in chr_.rows(fixture_json("nr_votes_5215.json.gz"))]
        self.assertTrue(votes)
        self.assertTrue(all(v["key"].startswith("nr-") and v["session_id"] == 5215 for v in votes))
        positions = [chr_.parse_nr_voting(r)
                     for r in chr_.rows(fixture_json("nr_voting_38691.json.gz"))]
        self.assertEqual(len(positions), 200)
        self.assertTrue({p["position"] for p in positions} <= set(chr_.DECISIONS.values()))

    def test_businesses_in_two_languages(self):
        de = chr_.rows(fixture_json("business_de.json.gz"))
        fr = chr_.rows(fixture_json("business_fr.json.gz"))
        pairs = chr_._pair(de, fr)
        self.assertEqual(len(pairs), len(de))
        self.assertTrue(all(d and f and d["id"] == f["id"] for d, f in pairs))

    def test_members(self):
        members = [chr_.parse_member(r) for r in chr_.rows(fixture_json("members.json.gz"))]
        self.assertTrue(members)
        self.assertTrue({m["council"] for m in members} >= {"NR", "SR"})


if __name__ == "__main__":
    unittest.main()
