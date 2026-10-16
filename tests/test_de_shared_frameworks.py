"""Germany in the shared country frameworks (16 October 2026, branch
de-ca-gaps): the reader adapter src/editions/de.py, the same-day vote briefs
(daily reader src/vote_brief_sources.DE), the daily sweep (DIP Vorgänge,
src/day_sweep_sources.DE; the agenda, src/agendas/de.py), the review window
for tools/de_monitor.py, member intelligence (src/member_intel.fetch_de) and
member profiles (profiles/de/).

No network: fixtures under tests/fixtures/de/ (the plenary Tagesordnung's
text as pypdf reads it, the Bundestag's committee index, one committee page
and its members fragment, all of 16 October 2026) and small stores built here.
"""

import contextlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_day_sweep as sweep  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src import country_vote_brief as cvb  # noqa: E402
from src import day_sweep_sources as ds  # noqa: E402
from src import db  # noqa: E402
from src import edition_review as er  # noqa: E402
from src import member_intel as mi  # noqa: E402
from src import member_profiles as mp  # noqa: E402
from src import vote_brief_sources as vs  # noqa: E402
from src.agendas import de as de_agenda  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "de")
TODAY = "2026-10-16"


def _read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def _store():
    conn = db.init_db(db.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def _member(conn, pid, name, party, legislature="161"):
    conn.execute("INSERT INTO de_members (person_id, name, party, parliament, legislature, "
                 "first_seen, last_seen, sitting) VALUES (?,?,?,?,?,?,?,1)",
                 (pid, name, party, "5", legislature, TODAY, TODAY))


def _division(conn, vid, date, label, areas="[1]", tier=1, accepted=1, yes=3, no=1):
    conn.execute("INSERT INTO de_divisions (vote_id, parliament, parliament_label, legislature, "
                 "date, label, yes, no, abstain, absent, accepted, areas, matched_terms, tier, "
                 "document_url, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (vid, "5", "Bundestag", "161", date, label, yes, no, 0, 0, accepted, areas,
                  '["Pränataltest*"]', tier, "https://dserver.bundestag.de/btd/21/038/x.pdf",
                  TODAY, TODAY))


def _vote(conn, vid, pid, pos):
    conn.execute("INSERT INTO de_votes (vote_id, person_id, position) VALUES (?,?,?)",
                 (vid, pid, pos))


def _vorgang(conn, vid, typ, titel, areas="[9]", tier=1, first_seen=TODAY, datum="2026-10-14",
             stand="Überwiesen", prev=None, moved=None):
    conn.execute("INSERT INTO de_vorgaenge (vorgang_id, wahlperiode, titel, vorgangstyp, "
                 "initiative, datum, stand, prev_stand, moved_date, areas, matched_terms, tier, "
                 "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (vid, "21", titel, typ, "Fraktion X", datum, stand, prev, moved, areas,
                  '["Elterngeld*"]', tier, first_seen, TODAY))


def _vote_store():
    conn = _store()
    for pid, name, party in (("1", "Anna A", "SPD"), ("2", "Bert B", "SPD"),
                             ("3", "Cora C", "CDU/CSU"), ("4", "Dirk D", "CDU/CSU"),
                             ("5", "Eva E", "fraktionslos"), ("6", "Fritz F", "SPD")):
        _member(conn, pid, name, party)
    _division(conn, "6715", "2026-10-15",
              "Monitoring der Kassenzulassung des nicht-invasiven Pränataltests (NIPT)")
    for pid, pos in (("1", "yes"), ("2", "no"), ("3", "yes"), ("4", "yes"), ("5", "no"),
                     ("6", "yes")):
        _vote(conn, "6715", pid, pos)
    conn.commit()
    return conn


# --- the reader adapter ----------------------------------------------------------------------

class AdapterTests(unittest.TestCase):
    def test_a_bundestag_vote_with_its_split_and_who_broke_from_their_fraktion(self):
        conn = _vote_store()
        got = [it for it in ce.gather(conn, ce.adapter("de"), "2026-10-10", TODAY)
               if it["kind"] == "vote"]
        self.assertEqual(len(got), 1)
        it = got[0]
        self.assertTrue(any("result as recorded: “angenommen”" in ln for ln in it["lines"]))
        self.assertTrue(any(ln.startswith("By Fraktion") for ln in it["lines"]))
        # Bert broke from the SPD; the fraktionslos member has no line to break.
        self.assertEqual(it["rebels"], ["Bert B (SPD)"])
        self.assertEqual(len(it["positions"]), 6)

    def test_land_votes_and_other_terms_stay_out_of_the_adapter(self):
        conn = _vote_store()
        conn.execute("UPDATE de_divisions SET parliament='15'")
        self.assertEqual([it for it in ce.gather(conn, ce.adapter("de"), "2026-10-10", TODAY)
                          if it["kind"] == "vote"], [])

    def test_vorgaenge_new_questions_and_stage_moves(self):
        conn = _store()
        _vorgang(conn, "1", "Gesetzgebung", "Gesetz zur Reform des Elterngeldes")
        _vorgang(conn, "2", "Kleine Anfrage", "Elterngeldreform 2027")
        _vorgang(conn, "3", "Antrag", "Elterngeld erhöhen", first_seen="2026-09-01",
                 prev="Noch nicht beraten", moved="2026-10-14")
        _vorgang(conn, "4", "Gesetzgebung", "Elterngeld alt", first_seen=TODAY, datum="2025-01-01")
        _vorgang(conn, "5", "Schriftliche Frage", "Abschiebungen", areas="[11]")
        conn.commit()
        got = {it["key"]: it for it in ce.gather(conn, ce.adapter("de"), "2026-10-10", TODAY)}
        self.assertEqual(got["1"]["kind"], "new")
        self.assertEqual(got["2"]["kind"], "question")
        self.assertEqual(got["3"]["kind"], "moved")
        self.assertIn("stage Noch nicht beraten -> Überwiesen", got["3"]["takeaway"])
        self.assertNotIn("4", got)              # first seen now, dated a year ago: a backfill
        self.assertNotIn("5", got)              # migration alone is never shown
        self.assertTrue(got["1"]["url"].startswith("https://dip.bundestag.de/vorgang/"))
        self.assertTrue(got["1"]["url"].endswith("/1"))

    def test_the_older_speeches_table_is_not_read_as_the_shared_one(self):
        conn = _vote_store()
        conn.execute("INSERT INTO de_speeches (speech_id, protocol, date, speaker, excerpt, "
                     "areas, tier, first_seen, last_seen) VALUES "
                     "('p#1','21/1','2026-10-15','X','Text','[1]',1,?,?)", (TODAY, TODAY))
        got = ce.gather(conn, ce.adapter("de"), "2026-10-10", TODAY)   # no IndexError
        self.assertFalse([it for it in got if it["kind"] == "speech"])

    def test_the_shared_vote_pages_leave_germanys_own_page_alone(self):
        from src import country_votes as cv
        self.assertIn("de", mp.SPECS)
        self.assertNotIn("de", cv.COUNTRIES)        # tools/make_de_votes.py's de-votes.html

    def test_the_german_edition_is_not_rendered_from_the_adapter(self):
        # tools/de_monitor.py keeps rendering its own; the review window and the
        # frameworks name Germany apart from the fifteen own editions.
        self.assertNotIn("de", er.OWN)
        self.assertIn("de", er.OTHER)


# --- same-day vote briefs ------------------------------------------------------------------

class FakeClient:
    def __init__(self, routes):
        self.routes = list(routes)
        self.calls = []
        self.throttles = {}

    def _find(self, url):
        for needle, answer in self.routes:
            if needle in url:
                return answer(url) if callable(answer) else answer
        raise FetchError(url, "test", "x", 1, "404")

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.calls.append(url)
        return self._find(url)

    def get_text(self, url, feed, slug, timeout=None, archive=True, **kw):
        self.calls.append(url)
        return self._find(url)

    def set_host_throttle(self, host, seconds):
        self.throttles[host] = seconds


AW_ROBOTS = {"www.abgeordnetenwatch.de": "User-agent: *\nDisallow: /api/v2/\n"}


def Guarded(raw, permissions=None):
    """The daily job's client: robots_guard.guard() over `raw`, with
    abgeordnetenwatch's real robots.txt rule (Disallow: /api/v2/). The
    written permission of 16 October 2026 is what lets the API through."""
    from tests.robots_fakes import RobotsServing
    from src import robots_guard as rg
    serving = RobotsServing(raw, AW_ROBOTS)
    client = rg.GuardedClient(serving, "country-vote-briefs", log=lambda *a, **k: None,
                              exempt=rg.DOCUMENTED_APIS, permissions=permissions)
    client.serving = serving
    return client


def _poll_detail(vid, date, label):
    votes = [{"vote": pos, "mandate": {"id": pid, "label": "{0} (Bundestag 2025 - 2029)".format(n)},
              "fraction": {"label": "{0} (Bundestag 2025 - 2029)".format(f)}}
             for pid, n, f, pos in ((1, "Anna A", "SPD", "yes"), (2, "Bert B", "SPD", "no"),
                                    (3, "Cora C", "CDU/CSU", "yes"))]
    return {"data": {"id": vid, "label": label, "field_poll_date": date, "field_accepted": True,
                     "field_topics": [{"label": "Gesundheit"}], "field_intro": "",
                     "related_data": {"votes": votes}}}


class VoteBriefTests(unittest.TestCase):
    def test_germany_is_briefed_after_the_weekly_and_daily(self):
        self.assertIn("de", cvb.EDITIONS)
        self.assertIn("de", vs.DAILY)
        self.assertNotIn("de", cvb.POSITIONS_LATER)
        with open(os.path.join(ROOT, "jobs", "de-weekly.sh"), encoding="utf-8") as fh:
            job = fh.read()
        self.assertIn("python3 tools/country_vote_briefs.py --country de --send", job)
        self.assertLess(job.index("de_rollcalls.py"), job.index("country_vote_briefs.py"))

    def test_a_tier1_bundestag_vote_is_briefed_once_with_its_fraktion_split(self):
        conn = _vote_store()
        out, ledgers = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out)
        self.addCleanup(shutil.rmtree, ledgers)
        cvb.save(dict(cvb.load("de", ledgers), seeded="2026-10-01"), TODAY, ledgers)
        with contextlib.redirect_stdout(io.StringIO()):
            n = cvb.run(conn, ["de"], "2026-10-10", TODAY, out_dir=out, dm=False,
                        directory=ledgers, log=lambda *_a: None)
        self.assertEqual(n, 1)
        text = open(os.path.join(out, os.listdir(out)[0]), encoding="utf-8").read()
        self.assertIn("Germany vote brief", text)
        self.assertIn("| Group |", text)
        self.assertIn("Bert B (SPD)", text)
        self.assertIn("config/de_stance.yaml is signed by a person", text)
        self.assertNotIn("—", text)

    def test_the_daily_reader_lists_the_newest_votes_and_reads_only_the_window(self):
        listing = {"data": [{"id": 6733, "field_poll_date": "2026-10-16"},
                            {"id": 6731, "field_poll_date": "2026-10-15"},
                            {"id": 6700, "field_poll_date": "2026-10-01"}]}
        raw = FakeClient([
            ("parliament-periods?parliament=5", {"data": [{"id": 161, "label": "Bundestag 2025 - 2029"}]}),
            ("sort_by=field_poll_date", listing),
            ("polls/6733", _poll_detail(6733, "2026-10-16", "Elterngeld für alle")),
            ("polls/6731", _poll_detail(6731, "2026-10-15", "Brennstoffemissionshandel")),
        ])
        conn = db.init_db(db.connect(":memory:"))
        client = Guarded(raw)
        n = vs.DE.collect(conn, client, "2026-10-13", TODAY, log=lambda *_a: None)
        self.assertEqual(n, 2)
        self.assertEqual(client.serving.robots_asked, [], "the written permission skips robots.txt")
        self.assertFalse(any("polls/6700" in u for u in raw.calls))
        self.assertEqual(raw.throttles.get("www.abgeordnetenwatch.de"), 2.5)
        got = conn.execute("SELECT vote_id, date FROM de_divisions ORDER BY vote_id").fetchall()
        self.assertEqual([tuple(r) for r in got], [("6731", "2026-10-15"), ("6733", "2026-10-16")])
        self.assertEqual(conn.execute("SELECT party FROM de_members WHERE person_id='2'")
                         .fetchone()[0], "SPD")

    def test_without_the_permission_the_guard_refuses_the_api(self):
        raw = FakeClient([("parliament-periods", {"data": []})])
        conn = db.init_db(db.connect(":memory:"))
        client = Guarded(raw, permissions=())
        with self.assertRaises(FetchError):
            vs.DE.collect(conn, client, "2026-10-13", TODAY, log=lambda *_a: None)
        self.assertEqual(raw.calls, [], "a refused URL is never requested")
        self.assertEqual(client.serving.robots_asked, ["www.abgeordnetenwatch.de"])

    def test_a_failed_list_is_a_gap_line(self):
        raw = FakeClient([])
        conn = db.init_db(db.connect(":memory:"))
        with self.assertRaises(FetchError):
            vs.DE.collect(conn, Guarded(raw), "2026-10-13", TODAY, log=lambda *_a: None)


# --- the daily sweep -------------------------------------------------------------------------

class SweepTests(unittest.TestCase):
    def test_germany_is_swept_once_a_day(self):
        self.assertIn("de", ds.SWEEP)
        self.assertNotIn("de", ds.LATAM)
        self.assertTrue(ds.DE.ONCE_A_DAY)
        self.assertTrue(ds.DE.AGENDA)

    def test_dip_vorgaenge_dated_in_the_window_are_classified_and_alert(self):
        pages = {"documents": [
            {"id": "339682", "vorgangstyp": "Kleine Anfrage", "wahlperiode": 21,
             "titel": "Elterngeldreform 2027 - Auswirkungen auf Familien", "datum": "2026-10-14",
             "beratungsstand": "Noch nicht beantwortet", "initiative": ["Fraktion X"]},
            {"id": "340464", "vorgangstyp": "Wahl des Präsidiums BR", "wahlperiode": 21,
             "titel": "Wahl des Vorsitzenden der Europakammer", "datum": "2026-10-16"}],
            "cursor": "c1"}
        client = FakeClient([("cursor=c1", {"documents": [], "cursor": "c1"}),
                             ("search.dip.bundestag.de/api/v1/vorgang", pages)])
        conn = db.init_db(db.connect(":memory:"))
        with mock.patch("src.dip.api_key", return_value="k"):
            n = ds.DE.collect(conn, client, "2026-10-13", TODAY, log=lambda *_a: None)
        self.assertEqual(n, 2)
        self.assertTrue(any("f.datum.start=2026-10-14" in u for u in client.calls))
        conn.row_factory = sqlite3.Row
        country, wide = sweep.sweep_country("de")
        got = ce.gather(conn, dataclass_without_agenda(wide), "2026-10-13", TODAY)
        nz = ce.noise_for(country)
        picked = [it for it in got if sweep.qualifies(it, nz)]
        self.assertEqual([it["key"] for it in picked], ["339682"])
        self.assertEqual(picked[0]["kind"], "question")

    def test_no_dip_key_is_a_gap(self):
        conn = db.init_db(db.connect(":memory:"))
        with mock.patch("src.dip.api_key", return_value=None):
            with self.assertRaises(ValueError):
                ds.DE.collect(conn, FakeClient([]), "2026-10-13", TODAY, log=lambda *_a: None)

    def test_an_item_in_a_german_edition_is_not_alerted_again(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with open(os.path.join(d, "de-monitor-2026-10-11.md"), "w", encoding="utf-8") as fh:
            fh.write("- [Gesetz](https://dip.bundestag.de/vorgang/gesetz-zur-x/326650) - why\n")
        self.assertIn("326650", sweep.edition_keys("de", TODAY, directory=d))


def dataclass_without_agenda(country):
    """The widened adapter without the agenda (no agenda table in these stores)."""
    import dataclasses
    inner = country.items

    def items(conn, since, until, wl):
        with mock.patch.object(ds.DE, "AGENDA", False):
            return inner(conn, since, until, wl)
    return dataclasses.replace(country, items=items)


# --- the agenda ------------------------------------------------------------------------------

class AgendaTests(unittest.TestCase):
    def setUp(self):
        self.text = _read("plenary-agenda-2026-10-14.txt")

    def test_the_sittings_and_their_days(self):
        days, term = de_agenda.sittings(self.text)
        self.assertEqual(term, "21")
        self.assertEqual(days["Mi"], ("2026-10-14", "101", "14:00"))
        self.assertEqual(days["Fr"][:2], ("2026-10-16", "103"))

    def test_each_point_with_its_day_drucksachen_and_status(self):
        pts = {p["item_id"]: p for p in de_agenda.parse_plenary(self.text)}
        top4 = pts["plenary:21/101:TOP 4"]
        self.assertEqual(top4["date"], "2026-10-14")
        self.assertEqual(top4["refs"], ["21/8412"])
        self.assertIn("Aufstiegsfortbildungsförderungsgesetzes", top4["title"])
        self.assertEqual(pts["plenary:21/101:TOP 5"]["status"], "abgesetzt")
        self.assertEqual(pts["plenary:21/102:TOP 11 c"]["refs"], ["21/8401"])
        self.assertIn("Mutterschutz", pts["plenary:21/102:TOP 11 c"]["title"])
        self.assertTrue(all(p["date"] for p in pts.values()))
        self.assertEqual(len(pts), len(set(pts)))

    def test_numbered_words_inside_a_point_are_not_a_new_point(self):
        pts = {p["item_id"]: p for p in de_agenda.parse_plenary(self.text)}
        top26 = pts["plenary:21/102:TOP 26 a"]
        self.assertIn("16. Bericht der Bundesregierung", top26["title"])
        self.assertEqual(top26["refs"], ["20/14480", "21/8396"])

    def test_the_feeds_plenary_entries_are_not_committee_sittings(self):
        self.assertTrue(de_agenda.is_plenary("Parlament",
                                             "Parlament: Tagesordnung komplett (104. - 106. Sitzung)"))
        self.assertTrue(de_agenda.full_plenary("Parlament: Tagesordnung komplett (104. - 106. Sitzung)"))
        self.assertFalse(de_agenda.full_plenary("Parlament: Geplanter Ablauf der Plenarsitzung"))
        self.assertFalse(de_agenda.is_plenary("Gesundheit", "Gesundheit: 40. Sitzung"))

    def test_a_committee_sitting_is_dated_by_its_title(self):
        self.assertEqual(de_agenda.committee_date(
            "Forschung: 31. Sitzung am Mittwoch, den 14. Oktober 2026, 9.30 Uhr"),
            ("2026-10-14", "09:30"))
        self.assertEqual(de_agenda.committee_date("Sondersitzung"), (None, None))


# --- the review window -----------------------------------------------------------------------

def _load_de_monitor():
    import importlib.util
    spec = importlib.util.spec_from_file_location("de_monitor_t",
                                                  os.path.join(ROOT, "tools", "de_monitor.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ReviewWindowTests(unittest.TestCase):
    def setUp(self):
        self.dm = _load_de_monitor()
        self.conn = _store()
        _vorgang(self.conn, "111", "Gesetzgebung", "Gesetz zum Elterngeld")
        _vorgang(self.conn, "222", "Gesetzgebung", "Gesetz zum Schutz der Familie")
        self.conn.execute("UPDATE de_vorgaenge SET triage_score=3, why_it_matters='Drafted.'")
        self.conn.commit()

    def test_off_by_default_for_germany_as_for_every_edition(self):
        self.assertFalse(er.enabled("de"))
        self.assertTrue(er.enabled("de", {"countries": {"de": {"review": True}}}))
        self.assertIn("de:", open(os.path.join(ROOT, "config", "edition-review.yaml"),
                                  encoding="utf-8").read())

    def test_no_review_renders_exactly_as_before(self):
        a = self.dm.render_edition(self.conn, TODAY, write=False)
        b = self.dm.render_edition(self.conn, TODAY, review=None, draft_until=None, write=False)
        self.assertEqual(a, b)
        self.assertNotIn("Draft under review", a)

    def test_a_cut_leaves_the_edition_and_an_edit_replaces_the_why_line(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        path, n = self.dm.write_review(self.conn, TODAY, "2026-10-17T06:30+01:00", d)
        self.assertEqual(n, 2)
        text = open(path, encoding="utf-8").read()
        self.assertIn("### item: de|vorgang|111", text)
        text = text.replace("### item: de|vorgang|111\n", "### item: de|vorgang|111\n", 1)
        out, cur = [], None
        for line in text.splitlines():
            if line.startswith("### item:"):
                cur = line.split("item:", 1)[1].strip()
            if cur == "de|vorgang|111" and line.startswith("DECISION:"):
                line = "DECISION: cut"
            if cur == "de|vorgang|222" and line.startswith("TAKEAWAY:"):
                line = "TAKEAWAY: Reviewer's line."
            out.append(line)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
        review = er.load("de", TODAY, d)
        got = self.dm.render_edition(self.conn, TODAY, review=review,
                                     draft_until="2026-10-17T06:30+01:00", write=False)
        self.assertNotIn("Gesetz zum Elterngeld", got)
        self.assertIn("Reviewer's line.", got)
        self.assertIn("Draft under review", got)
        self.assertIn("1 item(s) cut in review", got)
        dm_text = self.dm.dm_summary(self.conn, TODAY, review=review)
        self.assertNotIn("Gesetz zum Elterngeld", dm_text)
        self.assertIn("_Reviewed: 1 cut, 1 edited._", dm_text)
        # a rerun keeps the decisions
        self.dm.write_review(self.conn, TODAY, "2026-10-17T06:30+01:00", d)
        self.assertEqual(er.load("de", TODAY, d).counts(), (1, 1))

    def test_the_publish_step_renders_germany_with_its_own_tool(self):
        import edition_review as tool
        st = {"cc": "de", "date": TODAY, "deadline": "2026-10-17T06:30+01:00"}
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        text, dm_text, path, (n, _w) = tool.render_one(self.conn, st, None, editions_dir=d)
        self.assertTrue(text.startswith("# German Monitor"))
        self.assertTrue(path.endswith("de-monitor-{0}.md".format(TODAY)))
        self.assertEqual(n, 2)
        self.assertFalse(os.listdir(d))          # publish_due writes it, not render_one


# --- member intelligence and profiles -------------------------------------------------------

class MemberIntelTests(unittest.TestCase):
    def test_the_committee_index_pages_and_members(self):
        links = mi.de_committee_links(_read("ausschuesse.html"))
        self.assertIn("/ausschuesse/a13_Bildung-Familie-Senioren-Frauen-und-Jugend", links)
        self.assertIn("/ausschuesse/a13_Bildung-Familie-Senioren-Frauen-und-Jugend/kiko", links)
        self.assertFalse([p for p in links if "anhoerungen" in p or p.endswith("weitere_gremien")])
        name, members = mi.de_committee_page(_read("committee-a13.html"))
        self.assertEqual(name, "Ausschuss für Bildung, Familie, Senioren, Frauen und Jugend")
        self.assertTrue(members.startswith("/ajax/member/de/ausschuesse/a13_"))
        rows = mi.parse_de_committee(_read("committee-members-a13.html"), name, "a13",
                                     {"saskia esken": "68512"})
        self.assertEqual(len(rows), 75)
        esken = rows[0]
        self.assertEqual((esken["name"], esken["member_key"], esken["member_ref"]),
                         ("Saskia Esken", "68512", "1044226"))
        self.assertEqual(esken["role"], "Vorsitzende; ordentliches Mitglied")
        self.assertEqual(esken["group_type"], "SPD")
        storch = [r for r in rows if r["name"] == "Beatrix von Storch"]
        self.assertEqual(storch[0]["role"], "stellvertretendes Mitglied")
        self.assertEqual(sum(1 for r in rows if "stellvertretendes" in (r["role"] or "")), 37)

    def test_names_resolve_to_this_terms_members_without_their_titles(self):
        conn = _store()
        _member(conn, "68495", "Hülya Düber", "CDU/CSU")
        _member(conn, "1", "Max Muster", "SPD")
        _member(conn, "2", "Max Muster", "AfD")             # two of a name: not resolved
        _member(conn, "9", "Old Member", "SPD", legislature="132")
        keys = mi.de_keys(conn)
        self.assertEqual(keys.get("hulya duber"), "68495")
        self.assertNotIn("max muster", keys)
        self.assertNotIn("old member", keys)

    def test_the_nebentaetigkeiten_stay_off_without_chris(self):
        index = '<a href="/ausschuesse/a13_x">x</a>'
        page = ('<title>Ausschuss X - Deutscher Bundestag</title>'
                'data-dataloader-url="/ajax/member/de/ausschuesse/a13_x/1-1"')
        client = FakeClient([("/ajax/member/", _read("committee-members-a13.html")),
                             ("/ausschuesse/a13_x", page), ("/ausschuesse", index)])
        conn = _store()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DE_SIDEJOBS", None)
            with mock.patch("src.robots_guard.guard", lambda c, feed, **kw: c):
                got = mi.fetch_de(conn, client, TODAY, log=lambda *_a: None)
        self.assertEqual(set(got), {"de-ausschuesse"})
        self.assertFalse(any("abgeordnetenwatch" in u for u in client.calls))

    def test_sidejobs_are_the_members_own_items(self):
        reply = {"data": [{"label": "Mitglied des Aufsichtsrates", "job_title_extra": "Einkommen 2025",
                           "income_level": "1", "data_change_date": "2026-10-16",
                           "sidejob_organization": {"label": "Die Autobahn GmbH des Bundes"},
                           "mandates": [{"id": 68814,
                                         "label": "Henning Rehbaum (Bundestag 2025 - 2029)"}]}]}
        rows = mi.parse_de_sidejobs(reply)
        self.assertEqual(rows[0]["member_key"], "68814")
        self.assertEqual(rows[0]["name"], "Henning Rehbaum")
        self.assertEqual(rows[0]["text"], "Mitglied des Aufsichtsrates, Die Autobahn GmbH des Bundes")
        self.assertEqual(rows[0]["paid"], "income level 1")


class ProfileTests(unittest.TestCase):
    def test_this_terms_members_their_votes_and_their_seats(self):
        conn = _vote_store()
        _member(conn, "90", "Earlier Member", "SPD", legislature="132")
        _vote(conn, "6715", "90", "yes")                  # an earlier mandate: no profile
        mi.ensure(conn)
        mi.replace(conn, "de", "de-ausschuesse", TODAY, groups=[mi.group(
            member_key="1", member_ref="1044226", name="Anna A", group_key="a13",
            group_name="Ausschuss für Bildung, Familie, Senioren, Frauen und Jugend",
            role="Vorsitzende; ordentliches Mitglied")])
        data = mp.build(conn, "de", TODAY)
        self.assertNotIn("90", data["members"])
        anna = data["members"]["1"]
        self.assertEqual(len(anna.votes), 1)
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        mp.write(data, d)
        text = open(os.path.join(d, "de", [f for f in os.listdir(os.path.join(d, "de"))
                                           if f.startswith("anna-a")][0]), encoding="utf-8").read()
        self.assertIn("Ausschuss für Bildung, Familie", text)
        self.assertIn("X6", text)


if __name__ == "__main__":
    unittest.main()
