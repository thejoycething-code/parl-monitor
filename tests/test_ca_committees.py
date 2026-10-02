"""Canadian committee evidence (tools/ca_committees.py). No network.

Fixtures are the live pages of 2 October 2026, trimmed: the AMAD 44-1 and
JUST 40-3 meeting lists cut to three and two meetings, the Evidence pages cut
to the lines that link the XML, and the two XML transcripts whole (gzipped).
"""

import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cm = _load("ca_committees")
rt = _load("ca_retag")
TAX = filt.load_taxonomy(cm.TAXONOMY)
WL = filt.load_watchlist(cm.WATCHLIST)
TODAY = "2026-10-02"


def fixture(name):
    path = os.path.join(FIX, name)
    if name.endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            return fh.read().decode("utf-8")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


AMAD_LIST = cm.meetings_url("AMAD", 44, 1)
JUST_LIST = cm.meetings_url("JUST", 40, 3)
PAGES = {
    AMAD_LIST: "ca_cmte_amad_441_meetings.html",
    "https://www.parl.ca/DocumentViewer/en/44-1/AMAD/meeting-10/evidence":
        "ca_cmte_amad_441_10_evidence.html",
    "https://www.parl.ca/Content/Committee/441/AMAD/Evidence/EV11823690/AMADEV10-E.XML":
        "ca_cmte_amad_441_10.xml.gz",
    JUST_LIST: "ca_cmte_just_403_meetings.html",
    "https://www.ourcommons.ca/DocumentViewer/en/40-3/JUST/meeting-11/evidence":
        "ca_cmte_just_403_11_evidence.html",
    "https://www.ourcommons.ca/Content/Committee/403/JUST/Evidence/EV4423056/JUSTEV11-E.XML":
        "ca_cmte_just_403_11.xml.gz",
}


class FakeClient:
    """Serves the fixtures by URL; anything else is a 404."""

    def __init__(self, pages=None, fail=()):
        self.pages = dict(PAGES if pages is None else pages)
        self.fail = set(fail)
        self.calls = []

    def get_text(self, url, feed, slug, archive=True, **kw):
        self.calls.append((url, archive))
        if url in self.fail or url not in self.pages:
            raise FetchError(url, feed, slug, 1,
                             urllib.error.HTTPError(url, 404, "Not Found", {}, None))
        return fixture(self.pages[url])


def quiet(*a):
    return None


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    ca_store.ensure_schema(conn)
    for pid, name, riding in (
            ("89219", "Michael Cooper", "St. Albert—Edmonton"),
            ("88552", "Luc Thériault", "Montcalm"),
            ("1", "Hedy Fry", "Vancouver Centre"),
            # JUST 40-3/11, 13 April 2010
            ("2", "Joe Comartin", "Windsor—Tecumseh"),
            ("3", "Brian Murphy", "Moncton—Riverview—Dieppe")):
        conn.execute("INSERT INTO ca_members (person_id, name, constituency) VALUES (?,?,?)",
                     (pid, name, riding))
    for pid, name in (("senator-1", "Mégie, Marie-Françoise"), ("senator-2", "Kutcher, Stan")):
        conn.execute("INSERT INTO ca_senators (person_id, name) VALUES (?,?)", (pid, name))
    conn.commit()
    return conn


def run(conn, client=None, **kw):
    kw.setdefault("committees", ("AMAD",))
    kw.setdefault("session", "44-1")
    return cm.pull(conn, client or FakeClient(), TODAY, tax=TAX, wl=WL, log=quiet, **kw)


class MeetingListTests(unittest.TestCase):
    def test_the_list_gives_numbers_dates_studies_and_the_evidence_link(self):
        rows = cm.parse_meeting_list(fixture(PAGES[AMAD_LIST]), "AMAD", 44, 1)
        self.assertEqual([r["number"] for r in rows], [10, 11, 12])
        ten = rows[0]
        self.assertEqual(ten["date"], "2022-05-30")
        self.assertEqual(ten["key"], "44-1-AMAD-10")
        self.assertEqual(ten["studies"], ["Committee Business",
                                          "Statutory Review – Medical Assistance in Dying"])
        self.assertEqual(ten["evidence_url"],
                         "https://www.parl.ca/DocumentViewer/en/44-1/AMAD/meeting-10/evidence")

    def test_in_camera_means_no_evidence_link(self):
        twelve = cm.parse_meeting_list(fixture(PAGES[AMAD_LIST]), "AMAD", 44, 1)[2]
        self.assertTrue(twelve["in_camera"])
        self.assertIsNone(twelve["evidence_url"])

    def test_joint_committees_are_read_from_parl_ca(self):
        self.assertTrue(cm.meetings_url("AMAD", 44, 1).startswith("https://www.parl.ca/"))
        self.assertTrue(cm.meetings_url("JUST", 44, 1).startswith("https://www.ourcommons.ca/"))

    def test_the_evidence_page_links_the_xml(self):
        page = "https://www.parl.ca/DocumentViewer/en/44-1/AMAD/meeting-10/evidence"
        self.assertEqual(
            cm.xml_link(fixture(PAGES[page]), page),
            "https://www.parl.ca/Content/Committee/441/AMAD/Evidence/EV11823690/AMADEV10-E.XML")


class TypeTests(unittest.TestCase):
    def test_type_28_is_testimony_whatever_the_label_says(self):
        """The codes are observed, not documented: this pins them."""
        self.assertEqual(cm.role({"aff_type": "28", "label": "Mr. Michael Cooper"}), "witness")
        self.assertEqual(cm.role({"aff_type": "28", "label": "Dr. Ramona Coelho"}), "witness")
        self.assertEqual(cm.role({"aff_type": "36", "label": "The Joint Chair (Hon. Yonah Martin)"}),
                         "chair")
        self.assertEqual(cm.role({"aff_type": "35", "label": "The Chair"}), "chair")
        self.assertEqual(cm.role({"aff_type": "47", "label": "Mr. Michael Cooper"}), "member")
        self.assertEqual(cm.role({"aff_type": "40", "label": "Mr. Luc Thériault"}), "member")

    def test_researchers_and_clerks_are_officers_not_members(self):
        """AMAD 44-1/1-3: Type 26 'Ms. Marlisa Tiedemann (Committee
        Researcher)', Type 27 'The Joint Clerk (Mr. Leif-Erik Aune)'."""
        self.assertEqual(cm.role({"aff_type": "26", "label": "Ms. Marlisa Tiedemann"}), "chair")
        self.assertEqual(cm.role({"aff_type": "27", "label": "Mr. Leif-Erik Aune"}), "chair")

    def test_a_senators_short_first_name_resolves_only_when_labelled_senator(self):
        conn = store()
        sen = cm.Senators(conn)
        self.assertEqual(sen.resolve("Stanley Kutcher", known_senator=True), "senator-2")
        self.assertIsNone(sen.resolve("Stanley Kutcher"))
        self.assertEqual(sen.resolve("Stan Kutcher"), "senator-2")
        self.assertIsNone(sen.resolve("Robert Kutcher", known_senator=True))

    def test_a_lowercase_senator_label_is_still_a_senator(self):
        self.assertTrue(cm._senator_label("senator, Québec (Rougement), ISG"))
        self.assertFalse(cm._senator_label("St. Albert—Edmonton"))

    def test_parse_sitting_carries_the_affiliation_type(self):
        _, ivs = cm.han.parse_sitting(fixture("ca_cmte_amad_441_10.xml.gz"))
        coelho = [i for i in ivs if (i["label"] or "").startswith("Dr. Ramona Coelho")]
        self.assertTrue(coelho)
        self.assertEqual({i["aff_type"] for i in coelho}, {"28"})


class AmadTenTests(unittest.TestCase):
    """AMAD 10, 30 May 2022, Statutory Review – Medical Assistance in Dying."""

    @classmethod
    def setUpClass(cls):
        cls.conn = store()
        cls.summary = run(cls.conn, limit=1)

    def test_one_meeting_read_and_the_in_camera_one_recorded_not_gapped(self):
        self.assertEqual(self.summary["read"], 1)
        self.assertEqual(self.summary["gaps"], 0)
        rows = {r["meeting_key"]: r for r in self.conn.execute("SELECT * FROM ca_committee_meetings")}
        self.assertEqual(rows["44-1-AMAD-10"]["status"], "read")
        self.assertEqual(rows["44-1-AMAD-10"]["interventions"], 162)
        self.assertEqual((rows["44-1-AMAD-10"]["chair"], rows["44-1-AMAD-10"]["members"],
                          rows["44-1-AMAD-10"]["witnesses"]), (42, 57, 63))
        self.assertEqual(rows["44-1-AMAD-10"]["date"], "2022-05-30")
        self.assertTrue(rows["44-1-AMAD-10"]["xml_url"].endswith("AMADEV10-E.XML"))
        self.assertEqual(rows["44-1-AMAD-12"]["status"], "in_camera")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 0)

    def test_michael_cooper_is_a_resolved_member_speech(self):
        rows = self.conn.execute(
            "SELECT * FROM ca_speeches WHERE speaker LIKE 'Mr. Michael Cooper%'").fetchall()
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r["person_id"], "89219")
            self.assertEqual((r["chamber"], r["forum"], r["committee"]),
                             ("commons", "committee", "AMAD"))
            self.assertTrue(r["speech_id"].startswith("cmte-441-AMAD-10-"))
            self.assertEqual(r["sitting_key"], "44-1-AMAD-10")
            self.assertIn("Medical Assistance in Dying", r["subject"])
        self.assertTrue(any("stroke" in (r["text"] or "") for r in rows))

    def test_ramona_coelho_is_testimony_and_never_a_speech(self):
        rows = self.conn.execute(
            "SELECT * FROM ca_testimony WHERE witness='Dr. Ramona Coelho'").fetchall()
        self.assertEqual(len(rows), 16)
        self.assertEqual({r["affiliation"] for r in rows}, {"Physician, As an Individual"})
        self.assertEqual({r["organisation"] for r in rows}, {"As an Individual"})
        self.assertTrue(any("transient suicidality" in (r["text"] or "") for r in rows))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM ca_speeches WHERE speaker LIKE '%Coelho%'").fetchone()[0], 0)

    def test_no_witness_is_ever_in_ca_speeches(self):
        witness_ids = {r[0] for r in self.conn.execute("SELECT db_id FROM ca_testimony")}
        speech_ids = {r[0] for r in self.conn.execute("SELECT db_id FROM ca_speeches")}
        self.assertTrue(witness_ids)
        self.assertEqual(witness_ids & speech_ids, set())
        _, ivs = cm.han.parse_sitting(fixture("ca_cmte_amad_441_10.xml.gz"))
        type28 = {cm.speech_id(44, 1, "AMAD", 10, i["id"]) for i in ivs if i["aff_type"] == "28"}
        stored = {r[0] for r in self.conn.execute("SELECT speech_id FROM ca_speeches")}
        self.assertEqual(type28 & stored, set())

    def test_a_senator_resolves_against_ca_senators_even_when_bare(self):
        """Mégie spoke as DbId 228785 (labelled, Senator) and 288386 (bare)."""
        rows = self.conn.execute("SELECT DISTINCT db_id, person_id, chamber FROM ca_speeches "
                                 "WHERE speaker LIKE '%Mégie%'").fetchall()
        self.assertEqual({r["db_id"] for r in rows}, {"228785", "288386"})
        self.assertEqual({(r["person_id"], r["chamber"]) for r in rows}, {("senator-1", "senate")})

    def test_an_unknown_senator_stays_null_never_minted(self):
        rows = self.conn.execute("SELECT DISTINCT person_id, chamber FROM ca_speeches "
                                 "WHERE speaker LIKE '%Dalphond%'").fetchall()
        self.assertEqual({(r["person_id"], r["chamber"]) for r in rows}, {(None, "senate")})

    def test_a_bare_name_resolves_when_unique(self):
        rows = self.conn.execute("SELECT DISTINCT person_id FROM ca_speeches "
                                 "WHERE speaker='Hon. Hedy Fry'").fetchall()
        self.assertEqual([r[0] for r in rows], ["1"])

    def test_the_chair_is_counted_not_stored(self):
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM ca_speeches WHERE speaker LIKE 'The %'").fetchone()[0], 0)

    def test_committee_db_ids_never_reach_ca_speaker_roles(self):
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ca_speaker_roles").fetchone()[0], 0)

    def test_the_xml_is_archived_and_the_heavy_pages_are_not(self):
        client = FakeClient()
        run(store(), client, limit=1)
        archived = {u.rsplit("/", 1)[-1].split("?")[0]: a for u, a in client.calls}
        self.assertTrue(archived["AMADEV10-E.XML"])
        self.assertFalse(archived["evidence"])
        self.assertFalse(archived["Meetings"])

    def test_the_retag_reproduces_committee_rows(self):
        changes = rt.retag(self.conn, TAX, WL, dry_run=True, log=quiet)
        self.assertEqual(changes, [])


class ResumeTests(unittest.TestCase):
    def test_a_second_run_skips_what_was_read_and_what_was_in_camera(self):
        conn = store()
        run(conn, limit=1)
        client = FakeClient()
        s = run(conn, client, limit=1)
        fetched = [u for u, _ in client.calls]
        self.assertNotIn("https://www.parl.ca/DocumentViewer/en/44-1/AMAD/meeting-10/evidence",
                         fetched)
        self.assertEqual(s["skipped"], 2)   # 10 read, 12 in camera
        # 11 is next; its evidence is not in the fixtures, so it is a gap --
        # recorded, and the meeting gets no row so the next run retries it.
        self.assertEqual(s["read"], 0)
        self.assertEqual(s["gaps"], 1)
        self.assertIsNone(conn.execute("SELECT 1 FROM ca_committee_meetings "
                                       "WHERE meeting_key='44-1-AMAD-11'").fetchone())
        self.assertIn("44-1-AMAD-11", conn.execute("SELECT detail FROM gaps").fetchone()[0])

    def test_a_public_meeting_without_evidence_is_rechecked_not_skipped(self):
        conn = store()
        m = {"key": "44-1-AMAD-99", "committee": "AMAD", "parliament": 44, "session": 1,
             "number": 99, "date": "2026-10-01", "studies": [], "in_camera": False,
             "site_id": "1", "evidence_url": None}
        cm.record_meeting(conn, m, "no_evidence", TODAY)
        self.assertNotIn("44-1-AMAD-99", cm.already_read(conn))

    def test_a_list_that_will_not_load_is_a_gap(self):
        conn = store()
        s = run(conn, FakeClient(fail={AMAD_LIST}))
        self.assertEqual(s["gaps"], 1)
        self.assertIn("meeting list", conn.execute("SELECT detail FROM gaps").fetchone()[0])

    def test_an_evidence_page_with_no_xml_link_is_a_gap(self):
        pages = dict(PAGES)
        pages["https://www.parl.ca/DocumentViewer/en/44-1/AMAD/meeting-10/evidence"] = \
            "ca_cmte_amad_441_meetings.html"
        conn = store()
        s = run(conn, FakeClient(pages), limit=1)
        self.assertEqual((s["read"], s["gaps"]), (0, 1))
        self.assertIn("links no XML", conn.execute("SELECT detail FROM gaps").fetchone()[0])


class Just2010Tests(unittest.TestCase):
    def test_just_40_3_meeting_11_parses(self):
        date, ivs = cm.han.parse_sitting(fixture("ca_cmte_just_403_11.xml.gz"))
        self.assertEqual(date, "2010-04-13")
        self.assertEqual(len(ivs), 200)
        roles = [cm.role(i) for i in ivs]
        self.assertEqual((roles.count("witness"), roles.count("chair"), roles.count("member")),
                         (88, 28, 84))

    def test_the_in_camera_meeting_is_not_a_gap_and_the_session_reads(self):
        conn = store()
        s = run(conn, committees=("JUST",), session="40-3")
        self.assertEqual((s["read"], s["in_camera"], s["gaps"]), (1, 1, 0))
        row = conn.execute("SELECT * FROM ca_committee_meetings WHERE "
                           "meeting_key='40-3-JUST-11'").fetchone()
        self.assertEqual(json.loads(row["studies"]), ["State of Organized Crime",
                                                      "Committee Business"])
        self.assertEqual(row["interventions"], 200)


class TitleGateTests(unittest.TestCase):
    def test_a_gated_committee_reads_only_meetings_titled_on_our_ground(self):
        self.assertTrue(cm.on_our_ground_title(
            TAX, WL, ["Statutory Review – Medical Assistance in Dying"]))
        self.assertFalse(cm.on_our_ground_title(TAX, WL, ["State of Organized Crime"]))
        self.assertFalse(cm.on_our_ground_title(TAX, WL, []))

    def test_off_ground_meetings_of_a_gated_committee_are_never_fetched(self):
        conn = store()
        client = FakeClient()
        s = run(conn, client, committees=(), gated=("JUST",), session="40-3")
        self.assertEqual(s["read"], 0)
        self.assertEqual(s["title_gated"], 2)
        self.assertEqual([u for u, _ in client.calls], [JUST_LIST])

    def test_ids_never_collide_with_hansard(self):
        self.assertEqual(cm.speech_id(44, 1, "AMAD", 10, "11717363"),
                         "cmte-441-AMAD-10-11717363")


if __name__ == "__main__":
    unittest.main()
