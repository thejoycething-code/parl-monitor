"""The four pieces that close Germany's remaining gaps against Westminster
(Christopher, 23 September 2026): the deadline layer, stance scoring, the
Constitutional Court, and amendments.

Each one is defended by the property that made it worth building.

PETITIONS are the only German source with a date to act on, so what is tested
is that the deadline is EXACT and comes from the page's own epoch stamps, not
from the "Es bleiben noch: 5 Tage" string a human reads.

STANCE must send the whole speech. Excerpt-only scoring is a failure this repo
has already paid for by name -- Lord Farmer read as supporting the assisted
dying Bill when his surrounding speech was plainly against it (2026-08-11) --
so a German pass reading 400 characters would repeat it in a second language.

AMENDMENTS are admitted by the bill they amend, never by their own title,
which is pure procedure. And the join reports its own denominator, because the
first live run legitimately returned zero and that is exactly when a silent
join failure gets believed.

JUDGMENTS are forward-looking and UNDATED -- the court publishes a stage, never
a judgment date -- so nothing may imply a date it has not given.
"""

import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, stance


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pet = _load("de_petitions")
crt = _load("de_courts")
amd = _load("de_amendments")
stc = _load("de_stance")
TODAY = "2026-09-23"


def _conn():
    return db.init_db(db.connect(":memory:"))


# One card, verbatim in shape from the live feed of 2026-09-23.
CARD = '''
<div class="teaser">
<a class="to-petdetails" href="/petitionen/_2026/_06/_16/Petition_202844.nc.html"
   title="Pauschaler Freibetrag von mindestens 30 Euro" target="_self">
Pauschaler Freibetrag</a>
<span>Es bleiben noch:</span><span>1</span><span>Tage</span>
<span data-start="1786496400000" data-end="1790125200000"></span>
<p>Mitzeichnungen: 96</p><p>Id-Nr.: 202844</p>
</div>
'''


class PetitionDeadlineTests(unittest.TestCase):
    def test_the_deadline_comes_from_the_epoch_not_the_rendered_days(self):
        """A day count derived from "Es bleiben noch: 1 Tage" drifts by a day
        around midnight and is wrong in exactly the week it matters."""
        cards = pet.parse_cards(CARD)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["opened"], "2026-08-12")
        self.assertEqual(cards[0]["closes"], "2026-09-23")

    def test_the_detail_url_is_taken_from_the_card(self):
        """Rebuilt from the id it is dead -- the real path carries the date
        the petition opened. Built that way it did not 404 cleanly either:
        the client retried it with backoff and the run silently stopped
        making progress."""
        cards = pet.parse_cards(CARD)
        self.assertEqual(
            cards[0]["url"],
            "https://epetitionen.bundestag.de/petitionen/_2026/_06/_16/"
            "Petition_202844.nc.html")

    def test_signatures_and_id_are_read(self):
        cards = pet.parse_cards(CARD)
        self.assertEqual(cards[0]["petition_id"], "202844")
        self.assertEqual(cards[0]["signatures"], 96)

    def test_a_card_with_no_dates_is_kept_and_counted(self):
        """Dropped, it is indistinguishable from a petition that never
        existed -- and this source has no archive to recover it from."""
        broken = CARD.replace('data-start="1786496400000" '
                              'data-end="1790125200000"', "")
        cards = pet.parse_cards(broken)
        self.assertEqual(len(cards), 1)
        self.assertIsNone(cards[0]["closes"])

    def test_the_url_is_written_on_a_row_that_already_exists(self):
        """A column only an INSERT can fill is a column existing rows never
        get: exactly how 637 members kept a NULL parliament."""
        conn = _conn()

        class Client:
            def __init__(self):
                self.calls = 0

            def get_text(self, url, feed, slug, **kw):
                self.calls += 1
                return CARD if self.calls == 1 else ""
        conn.execute("INSERT INTO de_petitions (petition_id, title, "
                     "first_seen, last_seen) VALUES ('202844','old',?,?)",
                     (TODAY, TODAY))
        conn.commit()
        pet.pull(conn, Client(), TODAY, log=lambda *a: None)
        url = conn.execute("SELECT url FROM de_petitions WHERE petition_id = "
                           "'202844'").fetchone()[0]
        self.assertTrue(url and url.endswith("Petition_202844.nc.html"), url)


class StanceTests(unittest.TestCase):
    def test_the_german_frame_differs_from_westminsters(self):
        self.assertNotEqual(stance.SYSTEM_PROMPT_DE, stance.SYSTEM_PROMPT)
        self.assertIn("GERMAN", stance.SYSTEM_PROMPT_DE)

    def test_the_frame_is_actually_sent(self):
        """A frame that exists and is never passed is worse than none: the
        run looks German and the judge is reading Westminster's brief."""
        payload = stance._build_payload([], system=stance.SYSTEM_PROMPT_DE)
        self.assertEqual(payload["system"], stance.SYSTEM_PROMPT_DE)
        self.assertEqual(stance._build_payload([])["system"],
                         stance.SYSTEM_PROMPT)

    def test_evidence_carries_the_WHOLE_speech_not_the_excerpt(self):
        """THE ONE THAT MATTERS. src/stance._evidence_text centres its window
        on the excerpt inside the full text; with no full text there is
        nothing to centre in, and excerpt-only scoring flipped Lord Farmer's
        placement on the assisted dying Bill (2026-08-11)."""
        conn = _conn()
        body = "Ich spreche gegen diesen Gesetzentwurf. " * 40
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "party, role, person_id, excerpt, text, areas, tier, first_seen, "
            "last_seen) VALUES ('s1','21/94','2026-09-11','Ein Mitglied',"
            "'SPD','member','p1','Gesetzentwurf',?,'[1]',1,?,?)",
            (body, TODAY, TODAY))
        conn.commit()
        ev = stc.evidence(conn)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].text, body)
        self.assertGreater(len(ev[0].text), len(ev[0].excerpt))
        self.assertTrue(ev[0].ref.startswith("de-speech:"),
                        "German refs must not collide with Westminster's")

    def test_migration_only_speeches_are_not_scored(self):
        """Area 11 renders nowhere, so paying to place members on it buys a
        surface that does not exist."""
        conn = _conn()
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "role, person_id, text, areas, tier, first_seen, last_seen) "
            "VALUES ('s1','21/94','2026-09-11','X','member','p1','...',"
            "'[11]',1,?,?)", (TODAY, TODAY))
        conn.commit()
        self.assertEqual(stc.evidence(conn), [])

    def test_the_chair_is_never_scored(self):
        conn = _conn()
        conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, date, speaker, "
            "role, person_id, text, areas, tier, first_seen, last_seen) "
            "VALUES ('s1','21/94','2026-09-11','Präsidentin','chair','p1',"
            "'Das Wort hat...','[1]',1,?,?)", (TODAY, TODAY))
        conn.commit()
        self.assertEqual(stc.evidence(conn), [])


COURT_PAGE = '''
<p class="h2">Erster Senat</p>
<table><caption><strong>Berichterstatter: Prof. Dr. Harbarth</strong></caption>
<thead><tr><th>Nr.</th><th>Aktenzeichen</th><th>Informationen</th><th>Stand</th></tr></thead>
<tbody>
<tr><td>1.</td><td>1 <abbr title="">BvR</abbr> 2490/24</td>
    <td>Verfassungsbeschwerde zum Schwangerschaftsabbruch und zur Beratung</td>
    <td>Termin noch nicht bestimmt</td></tr>
</tbody></table>
<p class="h2">Zweiter Senat</p>
<table><caption><strong>Berichterstatter: Dr. Müller</strong></caption>
<tbody>
<tr><td>1.</td><td>2 <abbr title="">BvE</abbr> 3/23</td>
    <td>Organstreitverfahren zur Geschäftsordnung</td><td>Beraten</td></tr>
</tbody></table>
'''


class CourtTests(unittest.TestCase):
    def test_cases_are_parsed_with_their_senate(self):
        """A case under the wrong Senate is wrong about which five judges
        decide it, so the page is walked in order rather than table by
        table."""
        cases = crt.parse(COURT_PAGE)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]["case_no"], "1 BvR 2490/24")
        self.assertEqual(cases[0]["senat"], "Erster Senat")
        self.assertEqual(cases[1]["senat"], "Zweiter Senat")

    def test_the_register_letters_survive_their_abbr_tags(self):
        """The court wraps BvR in <abbr>, which is why matching the raw HTML
        found nothing and made the first probe look like an empty page."""
        self.assertEqual(crt.parse(COURT_PAGE)[1]["case_no"], "2 BvE 3/23")

    def test_the_stage_is_kept_verbatim_and_no_date_is_invented(self):
        cases = crt.parse(COURT_PAGE)
        self.assertEqual(cases[0]["stage"], "Termin noch nicht bestimmt")
        for c in cases:
            self.assertNotIn("date", c)

    def test_a_page_that_parses_to_nothing_is_recorded_as_a_gap(self):
        """A parse finding nothing is not a court with nothing listed, and
        this is markup we do not control."""
        conn = _conn()

        class Client:
            def get_text(self, *a, **kw):
                return "<html>redesigned</html>"
        from src import filter as filt
        tax = filt.load_taxonomy(os.path.join(ROOT, "config",
                                              "taxonomy-de.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config",
                                              "watchlist-de.yaml"))
        crt.pull(conn, Client(), TODAY, tax, wl, log=lambda *a: None)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE "
                                           "feed='de-courts'")]
        self.assertTrue(any("markup" in g for g in gaps), gaps)


class AmendmentTests(unittest.TestCase):
    def test_an_amendment_is_admitted_through_the_bill_it_amends(self):
        """Its own title is procedure -- "zu der zweiten Beratung des
        Gesetzentwurfs der Bundesregierung - Drucksachen 21/6130" -- so
        matching it alone finds nothing every week, and a permanently empty
        section reads as a quiet Parliament rather than a broken filter."""
        conn = _conn()
        conn.execute(
            "INSERT INTO de_vorgaenge (vorgang_id, titel, areas, tier, "
            "first_seen, last_seen) VALUES ('333139','Ein Gesetz zur "
            "Schwangerschaft','[1]',1,?,?)", (TODAY, TODAY))
        conn.commit()
        self.assertEqual(amd.ours(conn, "333139"), [1])
        self.assertEqual(amd.ours(conn, "999999"), [])

    def test_the_join_reports_its_own_denominator(self):
        """The first live run returned zero legitimately -- none of the 19
        bills amended this year is one we hold -- and that is exactly when a
        silent join failure gets believed."""
        import inspect
        src = inspect.getsource(amd)
        self.assertIn("parents_seen", src)
        self.assertIn("not a broken join", src)

    def test_the_parent_id_and_title_are_read_from_vorgangsbezug(self):
        doc = {"vorgangsbezug": [{"id": 333139, "titel": "Ein Gesetz"},
                                 {"id": 1, "titel": "Ein anderes"}]}
        self.assertEqual(amd.parents(doc)[0], ("333139", "Ein Gesetz"))

    def test_the_mover_is_read_never_inferred(self):
        doc = {"urheber": [{"titel": "Fraktion der AfD"},
                           {"bezeichnung": "AfWIuG"}]}
        self.assertEqual(amd.urheber_of(doc), "Fraktion der AfD; AfWIuG")
        self.assertIsNone(amd.urheber_of({}))


class RegistrationTests(unittest.TestCase):
    def _cov(self):
        return _load_module("coverage")

    def test_every_new_source_is_watched_and_owned(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "coverage", os.path.join(ROOT, "tools", "coverage.py"))
        cov = iu.module_from_spec(spec)
        spec.loader.exec_module(cov)
        names = [f[0] for f in cov.FEEDS]
        for table in ("de_petitions", "de_petition_snapshots", "de_judgments",
                      "de_amendments"):
            self.assertIn(table, names, table)
            self.assertIn(table, cov.PIPELINE_FEEDS["Germany weekly"], table)

    def test_every_new_source_is_judged(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "de_triage", os.path.join(ROOT, "tools", "de_triage.py"))
        tri = iu.module_from_spec(spec)
        spec.loader.exec_module(tri)
        for table in ("de_petitions", "de_judgments", "de_amendments"):
            self.assertIn(table, tri.SOURCES, table)

    def test_the_weekly_runs_all_four(self):
        with open(os.path.join(ROOT, ".github", "workflows", "de-weekly.yml"),
                  encoding="utf-8") as fh:
            text = fh.read()
        for tool in ("de_petitions.py", "de_courts.py", "de_amendments.py",
                     "de_stance.py"):
            self.assertIn(tool, text, tool)


cte = _load("de_committees")


class CommitteeReportTests(unittest.TestCase):
    """The last section Westminster had and Germany did not (Christopher, 24
    September 2026). A Beschlussempfehlung is the committee telling the House
    what to do with a bill BEFORE the vote."""

    def test_the_pdf_path_is_the_one_dserver_actually_serves(self):
        """VERIFIED against the live server on five papers. Two other
        paddings were tried first and both 404'd -- including the one
        de_amendments.py had been using since the day it was written, which
        made every amendment link in the edition dead."""
        self.assertEqual(cte.paper_url("21/8164"),
                         "https://dserver.bundestag.de/btd/21/081/2108164.pdf")
        self.assertEqual(cte.paper_url("21/1"),
                         "https://dserver.bundestag.de/btd/21/000/2100001.pdf")

    def test_both_tools_build_the_same_url(self):
        """They had two different constructions and only one could be right."""
        self.assertEqual(cte.paper_url("21/8164"), amd.paper_url("21/8164"))
        self.assertEqual(cte.paper_url("21/1"), amd.paper_url("21/1"))

    def test_a_bundesrat_numbered_paper_gets_no_invented_url(self):
        """An Unterrichtung can be numbered '542/26' or 'zu542/26', which
        does not live under /btd/ at all. No link beats a wrong one."""
        for n in ("542/26", "zu542/26", "", None):
            self.assertIsNone(cte.paper_url(n), repr(n))

    def test_a_report_is_classified_on_its_own_title(self):
        """The opposite of an amendment, and the difference is real: an
        Änderungsantrag's title is procedure, a report's names the bill."""
        from src import filter as filt
        tax = filt.load_taxonomy(os.path.join(ROOT, "config",
                                              "taxonomy-de.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config",
                                              "watchlist-de.yaml"))
        got = filt.filter_item(tax, wl,
                               "zu dem Gesetzentwurf der Fraktion der AfD - "
                               "Drucksache 21/6927 - Entwurf eines Gesetzes "
                               "zur Abschaffung des § 188 des "
                               "Strafgesetzbuches")
        self.assertTrue(got.issue_areas,
                        "a report naming a bill on our ground matched nothing")

    def test_the_paper_is_not_listed_as_its_own_parent(self):
        """A title repeats its own number; a report parented to itself would
        make the board look circular."""
        self.assertEqual(
            cte.parents_in_title("zu 21/8164 und Drucksachen 21/4500, "
                                 "21/4784", "21/8164"),
            ["21/4500", "21/4784"])

    def test_the_two_kinds_are_kept_apart(self):
        """A committee recommending something and the Commission laying a
        proposal are different events; the section names both halves."""
        self.assertEqual(cte.kind_of("Beschlussempfehlung und Bericht"),
                         "committee report")
        self.assertEqual(cte.kind_of("Unterrichtung"), "notification")

    def test_late_arriving_fields_are_updated_not_frozen(self):
        """THE TRAP. Of 128 reports sampled, 123 carried a committee -- but
        the two published that morning carried none, because DIP enriches
        afterwards. A write-once collector would leave every report
        permanently committee-less, since the week it is first seen is
        exactly the week the field is missing."""
        import inspect
        src = inspect.getsource(cte)
        self.assertIn("committee=COALESCE(excluded.committee, committee)", src)
        self.assertIn("vorgang_id=COALESCE(excluded.vorgang_id, vorgang_id)",
                      src)

    def test_it_is_registered_everywhere_a_source_must_be(self):
        import importlib.util as iu
        for name, attr, key in (("coverage", "FEEDS", None),
                                ("de_triage", "SOURCES", None)):
            spec = iu.spec_from_file_location(
                name, os.path.join(ROOT, "tools", name + ".py"))
            mod = iu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            got = getattr(mod, attr)
            names = [f[0] for f in got] if attr == "FEEDS" else list(got)
            self.assertIn("de_committee_reports", names, name)
        with open(os.path.join(ROOT, ".github", "workflows",
                               "de-weekly.yml"), encoding="utf-8") as fh:
            self.assertIn("de_committees.py", fh.read())


if __name__ == "__main__":
    unittest.main()
