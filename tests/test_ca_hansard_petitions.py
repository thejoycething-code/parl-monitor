"""Canadian Hansard and petitions (tools/ca_hansard.py, tools/ca_petitions.py). No network."""

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


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


han = _load("ca_hansard")
pet = _load("ca_petitions")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-ca.yaml"))


def quiet(*a):
    return None


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    ca_store.ensure_schema(conn)
    for pid, name, riding in (("105774", "Tamara Jansen", "Cloverdale—Langley City"),
                              ("30552", "Kevin Lamoureux", "Winnipeg North"),
                              ("88552", "Luc Thériault", "Montcalm")):
        conn.execute("INSERT INTO ca_members (person_id, name, constituency) VALUES (?,?,?)",
                     (pid, name, riding))
    conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, short_title) "
                 "VALUES ('45-1/S-209', 45, 1, 'S-209', "
                 "'Protecting Young Persons from Exposure to Pornography Act')")
    conn.commit()
    return conn


def iv(ident, label, db_id, *paras, kind="Debate"):
    body = "".join('<ParaText id="p{0}{1}">{2}</ParaText>'.format(ident, i, p)
                   for i, p in enumerate(paras))
    return ('<Intervention Type="{0}" id="{1}"><PersonSpeaking><Affiliation DbId="{2}" '
            'Type="2">{3}</Affiliation>: </PersonSpeaking><Content>{4}</Content>'
            '</Intervention>').format(kind, ident, db_id, label, body)


# "MAID" is a watchlist hit, which is what lets a mid-speech passage qualify:
# per-passage matching admits tier 1 or watchlist only (src/filter.py).
MAID = ("The current law would allow access to MAID for mental illness alone "
        "from March 2027, and we must stop it.")
PORN = "Age verification for pornography sites protects children."
TRADES = "Skilled trades deserve a national framework for labour mobility."

SITTING = """<Hansard><ExtractedInformation>
<ExtractedItem Name="MetaDateNumYear">2026</ExtractedItem>
<ExtractedItem Name="MetaDateNumMonth">09</ExtractedItem>
<ExtractedItem Name="MetaDateNumDay">23</ExtractedItem></ExtractedInformation>
<HansardBody>
 <OrderOfBusiness><OrderOfBusinessTitle>Private Members' Business</OrderOfBusinessTitle>
  <SubjectOfBusiness><Timestamp Hr="17" Mn="40">(1740)</Timestamp>
   <SubjectOfBusinessTitle>Criminal Code</SubjectOfBusinessTitle>
   <SubjectOfBusinessContent>
    <ProceduralText>Bill C‑218. Second reading</ProceduralText>
    {thériault}
    <Timestamp Hr="17" Mn="50">(1750)</Timestamp>
    {chair}
    {lamoureux_full}
    {lamoureux_bare}
   </SubjectOfBusinessContent></SubjectOfBusiness>
  <SubjectOfBusiness><SubjectOfBusinessTitle>Protecting Young Persons from Exposure to Pornography Act</SubjectOfBusinessTitle>
   <SubjectOfBusinessContent>{jansen_porn}</SubjectOfBusinessContent></SubjectOfBusiness>
 </OrderOfBusiness>
 <OrderOfBusiness><OrderOfBusinessTitle>Routine Proceedings</OrderOfBusinessTitle>
  <SubjectOfBusiness><SubjectOfBusinessTitle>Petitions</SubjectOfBusinessTitle>
   <SubjectOfBusinessQualifier>Skilled Trades</SubjectOfBusinessQualifier>
   <SubjectOfBusinessContent>{trades}</SubjectOfBusinessContent></SubjectOfBusiness>
  <SubjectOfBusiness><SubjectOfBusinessQualifier>Medical Assistance in Dying</SubjectOfBusinessQualifier>
   <SubjectOfBusinessContent>{jansen_petition}</SubjectOfBusinessContent></SubjectOfBusiness>
  <SubjectOfBusiness><SubjectOfBusinessQualifier>Medical Assistance in Dying</SubjectOfBusinessQualifier>
   <SubjectOfBusinessContent>{stranger}</SubjectOfBusinessContent></SubjectOfBusiness>
 </OrderOfBusiness>
</HansardBody></Hansard>""".format(
    thériault=iv("1", "Luc Thériault (Montcalm, BQ)", "317900", MAID),
    chair=iv("2", "The Assistant Deputy Speaker (Mrs. Alexandra Mendès)", "319091", MAID),
    lamoureux_full=iv("3", "Hon. Kevin Lamoureux (Parliamentary Secretary to the Leader of "
                           "the Government in the House of Commons, Lib.)", "332542", MAID),
    lamoureux_bare=iv("4", "Hon. Kevin Lamoureux", "332542", MAID, kind="Interjection"),
    jansen_porn=iv("5", "Tamara Jansen (Cloverdale—Langley City, CPC)", "318100", PORN),
    trades=iv("6", "Tamara Jansen", "318100", TRADES),
    jansen_petition=iv("7", "Tamara Jansen", "318100", MAID),
    stranger=iv("8", "Minister of Nowhere", "999999", MAID))


class HansardTests(unittest.TestCase):
    def run_sitting(self, conn=None):
        conn = conn or store()
        date, ivs = han.parse_sitting(SITTING)
        totals = han.store_sitting(conn, "45-1-142", 45, 1, 142, date, ivs, TAX, WL, "2026-09-26")
        return conn, date, ivs, totals

    def speech(self, conn, sid):
        return conn.execute("SELECT * FROM ca_speeches WHERE speech_id=?", (sid,)).fetchone()

    def test_labels_split_into_name_riding_and_party(self):
        self.assertEqual(han.parse_label("Gabriel Hardy (Montmorency—Charlevoix, CPC)"),
                         ("Gabriel Hardy", "Montmorency—Charlevoix", "Conservative"))
        self.assertEqual(han.parse_label("Hon. Kevin Lamoureux"), ("Kevin Lamoureux", None, None))
        self.assertEqual(han.parse_label("Minister of Finance")[0], "Minister of Finance")

    def test_every_intervention_is_read_and_the_chair_counted_not_stored(self):
        conn, date, ivs, totals = self.run_sitting()
        self.assertEqual(date, "2026-09-23")
        self.assertEqual(len(ivs), 8)
        self.assertEqual(totals["chair"], 1)
        self.assertIsNone(self.speech(conn, "2"), "the chair is procedure, not a speech")
        row = conn.execute("SELECT * FROM ca_sittings").fetchone()
        self.assertEqual((row["interventions"], row["chair"]), (8, 1))

    def test_only_our_ground_is_stored(self):
        conn, _, _, totals = self.run_sitting()
        self.assertIsNone(self.speech(conn, "6"), "a skilled-trades petition is not ours")
        self.assertEqual(totals["stored"], 6)

    def test_the_riding_resolves_and_the_role_id_is_remembered(self):
        """Hansard's DbId is a member in a ROLE; the riding resolves the
        person, and the bare second label inherits it through the DbId."""
        conn, *_ = self.run_sitting()
        self.assertEqual(self.speech(conn, "1")["person_id"], "88552")
        self.assertEqual(self.speech(conn, "7")["person_id"], "105774",
                         "bare 'Tamara Jansen' resolved through the remembered DbId")
        roles = {r["db_id"]: r["how"] for r in conn.execute("SELECT * FROM ca_speaker_roles")}
        self.assertEqual(roles["317900"], "riding")

    def test_a_unique_name_is_the_fallback(self):
        conn, *_ = self.run_sitting()
        self.assertEqual(self.speech(conn, "3")["person_id"], "30552")
        self.assertEqual(self.speech(conn, "4")["person_id"], "30552")

    def test_an_unknown_speaker_is_stored_blank_never_guessed(self):
        conn, _, _, totals = self.run_sitting()
        self.assertIsNone(self.speech(conn, "8")["person_id"])
        self.assertEqual(totals["unresolved"], 1)

    def test_time_is_the_last_timestamp_before_the_speech(self):
        conn, *_ = self.run_sitting()
        self.assertEqual(self.speech(conn, "1")["time"], "17:40")
        self.assertEqual(self.speech(conn, "3")["time"], "17:50")

    def test_the_bill_comes_from_procedure_or_the_short_title(self):
        conn, *_ = self.run_sitting()
        self.assertEqual(self.speech(conn, "1")["bill_number"], "C-218",
                         "non-breaking hyphen in 'Bill C‑218' still reads")
        self.assertEqual(self.speech(conn, "5")["bill_number"], "S-209",
                         "a resumed debate prints only the short title")

    def test_an_untitled_subject_inherits_the_petitions_title(self):
        conn, *_ = self.run_sitting()
        self.assertEqual(self.speech(conn, "7")["subject"], "Petitions — Medical Assistance in Dying")
        self.assertEqual(self.speech(conn, "7")["rubric"], "Routine Proceedings")

    def test_the_frontier_is_not_a_gap(self):
        conn = store()

        class Client:
            def get_text(self, url, feed, slug, archive=True):
                if "/142/" in url:
                    return SITTING
                raise FetchError(url, feed, slug, 1, urllib.error.HTTPError(url, 404, "nf", {}, None))

        read, stored, gaps, frontier = han.pull(conn, Client(), "2026-09-26", start=142,
                                                tax=TAX, wl=WL, log=quiet)
        self.assertEqual((read, gaps, frontier), (1, 0, 143))
        self.assertEqual(han.next_sitting(conn, 45, 1), 143)

    def test_a_failed_sitting_is_a_gap_and_the_walk_stops(self):
        conn = store()

        class Client:
            def get_text(self, url, feed, slug, archive=True):
                raise FetchError(url, feed, slug, 4, OSError("reset"))

        read, _, gaps, frontier = han.pull(conn, Client(), "2026-09-26", start=142,
                                           tax=TAX, wl=WL, log=quiet)
        self.assertEqual((read, gaps, frontier), (0, 1, None))
        self.assertEqual(han.next_sitting(conn, 45, 1), 1, "the failed sitting is still owed")


def page(pid, category, prayer, kind="E-petition", presented=None, response=None,
         signatures=100, mp=("Tamara-Jansen", "105774", "Tamara Jansen"), keyword="Euthanasia"):
    hist = "<dt>Open for signature </dt><dd>February 12, 2026, at 10:57 a.m. (EDT)</dd>"
    if presented:
        hist += ('<dt>Presented to the House of Commons </dt><dd><a class="underlined-link" '
                 'href="http://www.ourcommons.ca/Parliamentarians/en/members/{0}({1})"> {2} </a>'
                 '<br /><span>June 17, 2026 (Petition No. {3})</span></dd>').format(
                     mp[0], mp[1], mp[2], presented)
    if response:
        hist += "<dt>Government response tabled</dt><dd>August 19, 2026</dd>"
    resp = ('<div class="pet-reponse" language="en"><h3 class="title">Response by the '
            'Minister of Health</h3><div class="rep-paras"><p class="rep-para">{0}</p></div>'
            '</div>').format(response) if response else ""
    return ('<html><h1 data-cachedDateTime="x">{pid} ({cat})</h1><div class="introDetails">'
            '<ul class="pi-keywords"><li class="indexDetails"> <a href="#">{kw} </a></ul>'
            '<div class="icon"><span>{kind}</span></div></div>'
            '<div class="pet-prayer"><h3>Petition to the House of Commons</h3><div>'
            '<p class="pet-para">{prayer}</p></div></div>'
            '<h2 class="pet-table-col">{sigs} signatures </h2>'
            '<a href="/Parliamentarians/en/members/{m0}({m1})">{m2}</a>'
            '<div class="panel-body history-section"><dl>{hist}</dl></div>{resp}</html>').format(
                pid=pid, cat=category, kind=kind, kw=keyword, prayer=prayer, sigs=signatures,
                m0=mp[0], m1=mp[1], m2=mp[2], hist=hist, resp=resp)


class FakePages:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get_text(self, url, feed, slug, archive=True):
        pid = url.split("Petition=")[1]
        self.calls.append(pid)
        return self.pages.get(pid, "")


def run_for(conn, client, limit=None):
    return pet.Run(conn, client, "2026-09-26", TAX, WL, limit, None, quiet)


class PetitionTests(unittest.TestCase):
    def test_a_presented_e_petition_is_stored_under_its_e_number(self):
        """451-01121 serves the e-7000 page: one petition, two numbers."""
        p = pet.parse_details(page("e-7000", "Health", MAID, presented="451-01121",
                                   response="Health Canada notes the concern."))
        self.assertEqual((p["petition_id"], p["presented_number"]), ("e-7000", "451-01121"))
        self.assertEqual((p["opened"], p["presented"], p["response_tabled"]),
                         ("2026-02-12", "2026-06-17", "2026-08-19"))
        self.assertEqual(p["mp_person_id"], "105774")
        self.assertEqual(p["keywords"], ["Euthanasia"])

    def test_an_unpublished_number_is_empty_not_a_petition(self):
        self.assertIsNone(pet.parse_details(""))

    def test_the_presented_walk_stops_after_three_empties(self):
        conn = store()
        client = FakePages({"451-00001": page("451-00001", "Justice", MAID, kind="Paper petition"),
                            "451-00002": page("e-7000", "Health", TRADES, presented="451-00002")})
        run = run_for(conn, client)
        pet.walk_presented(run)
        self.assertEqual(client.calls, ["451-00001", "451-00002", "451-00003",
                                        "451-00004", "451-00005"])
        self.assertEqual(pet.highest_presented(conn), 2, "the e-page's presented number counts")

    def test_a_failed_page_stops_the_walk(self):
        conn = store()

        class Client(FakePages):
            def get_text(self, url, feed, slug, archive=True):
                raise FetchError(url, feed, slug, 4, OSError("reset"))

        run = run_for(conn, Client({}))
        pet.walk_presented(run)
        self.assertEqual((run.fetched, run.gaps), (1, 1))

    def test_the_open_probe_is_floored_at_the_seed(self):
        """A stored PRESENTED e-7719 must not pull the window below the
        live frontier: e-7810 was missed exactly this way on 26 September."""
        conn = store()
        pet.store(conn, pet.parse_details(page("e-7719", "Health", TRADES, presented="451-01200")),
                  filt.filter_item(TAX, WL, TRADES), "2026-09-26")
        client = FakePages({"e-7810": page("e-7810", "Justice", MAID)})
        run = run_for(conn, client, limit=60)
        pet.probe_open(run)
        self.assertIn("e-7810", client.calls)
        self.assertEqual(client.calls[0], "e-{0}".format(pet.E_SEED + pet.E_AHEAD), "newest first")

    def test_response_text_is_kept_on_our_ground_only(self):
        conn = store()
        client = FakePages({"451-00001": page("451-00001", "Justice", MAID, kind="Paper petition",
                                              response="We will consult."),
                            "451-00002": page("451-00002", "Economy", TRADES, kind="Paper petition",
                                              response="Thank you.", keyword="Labour")})
        pet.walk_presented(run_for(conn, client))
        rows = {r["petition_id"]: r["response_text"] for r in conn.execute("SELECT * FROM ca_petitions")}
        self.assertEqual(rows["451-00001"], "We will consult.")
        self.assertIsNone(rows["451-00002"])

    def test_our_petitions_awaiting_a_response_are_refreshed(self):
        conn = store()
        pet.store(conn, pet.parse_details(page("e-7700", "Justice", MAID)),
                  filt.filter_item(TAX, WL, MAID), "2026-09-01")
        pet.store(conn, pet.parse_details(page("e-7701", "Economy", TRADES, keyword="Labour")),
                  filt.filter_item(TAX, WL, TRADES), "2026-09-01")
        client = FakePages({"e-7700": page("e-7700", "Justice", MAID, signatures=900)})
        pet.refresh_owed(run_for(conn, client))
        self.assertEqual(client.calls, ["e-7700"], "only ours is owed a refresh")
        self.assertEqual(conn.execute("SELECT signatures FROM ca_petitions WHERE "
                                      "petition_id='e-7700'").fetchone()[0], 900)

    def test_the_fetch_cap_is_disclosed(self):
        conn = store()
        run = run_for(conn, FakePages({}), limit=2)
        pet.walk_presented(run)
        self.assertEqual(run.fetched, 2)
        self.assertIn("not silent", run.stopped)


if __name__ == "__main__":
    unittest.main()
