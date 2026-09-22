"""The Bundestag forward agenda (Christopher, 22 September 2026: "The focus
should be on upcoming items and debates with the weekly canvas").

Two properties carry this file.

The first is that NOTHING IS QUIETLY DROPPED. The feed is a rolling window of
about fifteen items with no archive behind it, so anything this collector
skips is gone for good -- there is no later run that can recover it. The first
live run proved the point: it read 6 of 15 agendas because it filtered on
date >= today, and the nine it skipped included Gesundheit, Inneres and
Menschenrechte, the three committees most likely to be on our ground.

The second is that AN EMPTY SECTION MUST SAY WHICH KIND OF EMPTY IT IS.
"Nothing on our ground next month" and "the feed only reaches Friday" render
identically unless the horizon is printed.

Fixtures are cut from the live feed of 2026-09-23.
"""

import datetime
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db


def _load():
    spec = importlib.util.spec_from_file_location(
        "de_agenda", os.path.join(ROOT, "tools", "de_agenda.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ag = _load()
TODAY = "2026-09-23"

# Verbatim shapes from the live feed: a public hearing, a partly-public
# sitting, the plenary agenda, and an amendment notice.
FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0"><channel>
<item>
  <title>Bau, Bauwesen, Wohnen: 30. Sitzung am Mittwoch, 23. September 2026, 16:30 Uhr - öffentliche Anhörung</title>
  <link>https://www.bundestag.de/resource/blob/1200670/30-Sitzung-TO-OeA.pdf</link>
  <guid>https://www.bundestag.de/resource/blob/1200670/30-Sitzung-TO-OeA.pdf</guid>
  <dc:date>2026-09-23T14:30:00Z</dc:date>
</item>
<item>
  <title>Digitales, Staatsmodernisierung: Tagesordnung der 32. Sitzung am Mittwoch, dem 23. September 2026, 14.30 Uhr - teilweise öffentlich*</title>
  <link>https://www.bundestag.de/resource/blob/1216198/TO-32-Sitzung.pdf</link>
  <guid>https://www.bundestag.de/resource/blob/1216198/TO-32-Sitzung.pdf</guid>
  <dc:date>2026-09-23T12:30:00Z</dc:date>
</item>
<item>
  <title>Parlament: Tagesordnung komplett (95. - 97. Sitzung)</title>
  <link>https://www.bundestag.de/resource/blob/473450/TO-komplett.pdf</link>
  <guid>https://www.bundestag.de/resource/blob/473450/TO-komplett.pdf</guid>
  <dc:date>2026-09-22T09:00:00Z</dc:date>
</item>
<item>
  <title>Gesundheit: 1. Ergaenzungsmitteilung der 55. Sitzung - nicht öffentlich</title>
  <link>https://www.bundestag.de/resource/blob/999/55-ErgMi.pdf</link>
  <guid>https://www.bundestag.de/resource/blob/999/55-ErgMi.pdf</guid>
  <dc:date>bogus-date</dc:date>
</item>
</channel></rss>"""


def _conn():
    return db.init_db(db.connect(":memory:"))


class FakeClient:
    """Serves the feed and, for any PDF, a body the caller chose."""

    def __init__(self, feed=FEED, body="", fail=False):
        self.feed, self.body, self.fail = feed, body, fail
        self.fetched = []

    def get_text(self, url, feed, slug, **kw):
        return self.feed

    def get_bytes(self, url, feed, slug, **kw):
        self.fetched.append(url)
        if self.fail:
            raise ValueError("not a pdf")
        return b"%PDF-fake"


class ParseTests(unittest.TestCase):
    def test_every_item_is_parsed_with_its_date_and_time(self):
        items = ag.parse_feed(FEED)
        self.assertEqual(len(items), 4)
        first = items[0]
        self.assertEqual(first[1], "Bau, Bauwesen, Wohnen")
        self.assertEqual(first[3], "2026-09-23")
        self.assertEqual(first[4], "14:30")

    def test_openness_is_read_from_the_feeds_own_wording(self):
        """A public hearing is a sitting we could attend or brief for; a
        closed one is not. 'teilweise öffentlich' must not read as public."""
        self.assertEqual(ag.openness("... - öffentliche Anhörung"), "public")
        self.assertEqual(ag.openness("... - teilweise öffentlich*"),
                         "partly public")
        self.assertEqual(ag.openness("... - nicht öffentlich"), "closed")
        self.assertIsNone(ag.openness("30. Sitzung"))

    def test_an_unreadable_date_does_not_drop_the_item(self):
        """A dateless row is stored and disclosed. Dropped, it would be
        indistinguishable from a week with no sitting -- and the feed has no
        archive, so nothing could ever bring it back."""
        items = ag.parse_feed(FEED)
        bogus = [i for i in items if i[1] == "Gesundheit"]
        self.assertEqual(len(bogus), 1)
        self.assertIsNone(bogus[0][3])


class PullTests(unittest.TestCase):
    def test_it_stores_every_item_and_reports_the_horizon(self):
        conn = _conn()
        seen, new, horizon = ag.pull(conn, FakeClient(), TODAY, log=lambda *a: None)
        self.assertEqual((seen, new), (4, 4))
        self.assertEqual(horizon, "2026-09-23")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM de_agenda")
                         .fetchone()[0], 4)

    def test_a_dateless_item_is_recorded_as_a_gap(self):
        conn = _conn()
        ag.pull(conn, FakeClient(), TODAY, log=lambda *a: None)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE "
                                           "feed = 'de-agenda'")]
        self.assertTrue(any("no readable dc:date" in g for g in gaps), gaps)

    def test_a_re_run_re_stamps_rather_than_duplicating(self):
        """The feed issues Ergänzungsmitteilungen against the same sitting."""
        conn = _conn()
        ag.pull(conn, FakeClient(), TODAY, log=lambda *a: None)
        seen, new, _ = ag.pull(conn, FakeClient(), "2026-09-24",
                               log=lambda *a: None)
        self.assertEqual((seen, new), (4, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM de_agenda")
                         .fetchone()[0], 4)
        self.assertEqual(conn.execute("SELECT DISTINCT last_seen FROM "
                                      "de_agenda").fetchone()[0], "2026-09-24")

    def test_an_unreadable_feed_is_a_gap_not_a_crash(self):
        class Dead(FakeClient):
            def get_text(self, *a, **kw):
                raise ValueError("502")
        conn = _conn()
        seen, new, horizon = ag.pull(conn, Dead(), TODAY, log=lambda *a: None)
        self.assertEqual((seen, new, horizon), (0, 0, None))
        self.assertTrue(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed = "
                                     "'de-agenda'").fetchone()[0])

    def test_a_feed_that_is_not_xml_is_a_gap_not_a_crash(self):
        conn = _conn()
        seen, _, _ = ag.pull(conn, FakeClient(feed="<html>nope"), TODAY,
                             log=lambda *a: None)
        self.assertEqual(seen, 0)
        self.assertTrue(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed = "
                                     "'de-agenda'").fetchone()[0])


class ReadBodiesTests(unittest.TestCase):
    """THE REGRESSION THIS FILE EXISTS FOR."""

    def _tax(self):
        from src import filter as filt
        return (filt.load_taxonomy(os.path.join(ROOT, "config",
                                                "taxonomy-de.yaml")),
                filt.load_watchlist(os.path.join(ROOT, "config",
                                                 "watchlist-de.yaml")))

    def test_it_reads_past_dated_agendas_too(self):
        """The first live run filtered on date >= today and read 6 of 15.
        The nine it skipped included Gesundheit, Inneres and Menschenrechte --
        our three most relevant committees, which had sat the day before. With
        body_read left NULL and the window rolling on, no later run could ever
        have read them."""
        conn = _conn()
        ag.pull(conn, FakeClient(), TODAY, log=lambda *a: None)
        tax, wl = self._tax()
        client = FakeClient()
        ag.read_text = lambda c, url: "Geschlechtsinkongruenz gewährleisten"
        read, matched, failed = ag.read_bodies(conn, client, TODAY, tax, wl,
                                               log=lambda *a: None)
        self.assertEqual(read, 4, "every agenda in the window must be read, "
                                  "including the ones already sat")
        self.assertEqual(matched, 4)

    def test_a_body_is_read_once_even_when_it_fails(self):
        """body_read is stamped either way, or an unreadable agenda is
        retried every week for ever."""
        conn = _conn()
        ag.pull(conn, FakeClient(), TODAY, log=lambda *a: None)
        tax, wl = self._tax()

        def boom(c, url):
            raise ValueError("encrypted pdf")
        ag.read_text = boom
        read, matched, failed = ag.read_bodies(conn, client=FakeClient(),
                                               today=TODAY, tax=tax, wl=wl,
                                               log=lambda *a: None)
        self.assertEqual((read, matched, failed), (0, 0, 4))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM de_agenda WHERE "
                                      "body_read IS NULL").fetchone()[0], 0)
        again = ag.read_bodies(conn, FakeClient(), TODAY, tax, wl,
                               log=lambda *a: None)
        self.assertEqual(again, (0, 0, 0), "a failed read must not be retried")

    def test_drucksache_numbers_are_captured(self):
        """They are the join back to a Vorgang the monitor already tracks."""
        conn = _conn()
        ag.pull(conn, FakeClient(), TODAY, log=lambda *a: None)
        tax, wl = self._tax()
        ag.read_text = lambda c, url: (
            "Tagesordnungspunkt 1\\nGesetzentwurf\\nBT-Drucksache 21/6645\\n"
            "Tagesordnungspunkt 2\\nBT-Drucks. 21/7081")
        ag.read_bodies(conn, FakeClient(), TODAY, tax, wl, log=lambda *a: None)
        import json
        rows = [json.loads(r[0]) for r in conn.execute(
            "SELECT drucksachen FROM de_agenda WHERE drucksachen IS NOT NULL")]
        self.assertTrue(rows)
        self.assertEqual(rows[0], ["21/6645", "21/7081"])

    def test_the_committee_name_is_not_used_as_the_match_title(self):
        """A committee name is broad enough to drag in matches the agenda
        itself does not support, so the body alone is classified."""
        conn = _conn()
        ag.pull(conn, FakeClient(), TODAY, log=lambda *a: None)
        tax, wl = self._tax()
        ag.read_text = lambda c, url: "Nichts von Belang hier."
        read, matched, _ = ag.read_bodies(conn, FakeClient(), TODAY, tax, wl,
                                          log=lambda *a: None)
        self.assertEqual(matched, 0,
                         "a title-driven match would fire on the committee "
                         "name alone")


class RegistrationTests(unittest.TestCase):
    def test_the_feed_is_watched_and_owned_by_the_german_weekly(self):
        """A rolling window with no archive is the WORST source to lose
        silently: a week missed is a week gone."""
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "coverage", os.path.join(ROOT, "tools", "coverage.py"))
        cov = iu.module_from_spec(spec)
        spec.loader.exec_module(cov)
        self.assertIn("de_agenda", [f[0] for f in cov.FEEDS])
        self.assertIn("de_agenda", cov.PIPELINE_FEEDS["Germany weekly"])

    def test_the_weekly_runs_it_and_installs_the_pdf_reader(self):
        with open(os.path.join(ROOT, ".github", "workflows", "de-weekly.yml"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("tools/de_agenda.py", text)
        self.assertIn("pypdf", text,
                      "the agendas are PDFs; without the reader the step "
                      "would collect titles and classify nothing")

    def test_it_is_judged(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "de_triage", os.path.join(ROOT, "tools", "de_triage.py"))
        tri = iu.module_from_spec(spec)
        spec.loader.exec_module(tri)
        self.assertIn("de_agenda", tri.SOURCES)


if __name__ == "__main__":
    unittest.main()
