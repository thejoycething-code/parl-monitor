"""Devolved government consultations: parsers pinned to probed markup.

Fixtures are cut from live pages fetched 2026-08-22 (consult.gov.scot,
consultations.nidirect.gov.uk, www.gov.wales). The separation rule holds:
dg_consultations never writes items/mp_events and cannot reach the digest.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import devolved

CS_FINDER = """
<ul id="consultations" class="list-unstyled">
  <li class="dss-card consultation-state-open" data-consultation-state="open">
    <h2><a class="cs-no-underline" href="https://consult.gov.scot/mental-health/updates-code/">Updates to the Code of Practice </a></h2>
    <div class="row"><div class="col-md-9">
      <span>  Background   The Scottish Government is consulting on proposed updates.</span>
    </div><div class="col-md-3">
      <div class="cs-date-delta"><span><span>Opened</span> 6 August 2026</span></div>
    </div></div>
  </li>
  <li class="dss-card consultation-state-closed" data-consultation-state="closed">
    <h2><a href="/gone/closed-thing/">Closed thing</a></h2>
  </li>
</ul>
"""

CS_DETAIL = """
<p class="cs-consultation-sidebar-primary-date"><span>Closes</span> 29 Oct 2026</p>
<p class="cs-consultation-sidebar-secondary-date"><span>Opened</span> 6 Aug 2026</p>
"""

GW_INDEX = """
<ul class="index-list__items">
  <li class="index-list__item"><div>
    <div class="index-list__title">
      <a href="/fly-tipping-powers"><span><span>Fly-tipping: conditional cautions</span></span></a>
    </div>
    <div class="index-list__meta">
      <span class="index-list__date"><span><time datetime="2026-08-20T15:41:39Z">20 August 2026</time></span></span>
      <span class="index-list__type">Open consultation</span>
      <span class="index-list__topics"><span class="topics"><span class="from-area">Environment and climate change</span></span></span>
    </div></div>
  </li>
  <li class="index-list__item"><div>
    <div class="index-list__title">
      <a href="/culture-evidence"><span><span>A vision for culture: call for evidence</span></span></a>
    </div>
    <div class="index-list__meta">
      <span class="index-list__type">Open call for evidence</span>
    </div></div>
  </li>
  <li class="index-list__item"><div>
    <div class="index-list__title">
      <a href="/old-thing"><span><span>Old thing</span></span></a>
    </div>
    <div class="index-list__meta">
      <span class="index-list__type">Closed consultation</span>
    </div></div>
  </li>
</ul>
"""

GW_DETAIL = """
<div class="gw-row end-date"><div class="label">Consultation ends:</div>
<div class="item end-date">16 October 2026</div></div>
<div class="gw-row start-date"><div class="label">Consultation launched:</div>
<div class="item"><div><time datetime="2026-08-20T12:00:00Z">20 August 2026</time></div></div></div>
"""


GW_DETAIL_CFE = """
<div class="header-meta"><div class="gw-row end-date"><div class="label">Call for evidence ends:</div>
<div class="item end-date">31 October 2026</div></div>
<div class="gw-row start-date"><div class="label">Call for evidence launched:</div>
<div class="item"><div><time datetime="2026-07-31T12:00:00Z">31 July 2026</time></div></div></div></div>
"""


class CitizenSpaceTests(unittest.TestCase):
    def test_finder_takes_open_only(self):
        out = devolved.parse_citizen_space_finder(
            CS_FINDER, "scotland", "https://consult.gov.scot")
        self.assertEqual(len(out), 1, "consultation-state-closed rows are "
                                      "not open consultations")
        c = out[0]
        self.assertEqual(c.key, "scotland:/mental-health/updates-code/")
        self.assertEqual(c.title, "Updates to the Code of Practice")
        self.assertEqual(c.opened, "2026-08-06")
        self.assertIn("consulting on proposed updates", c.summary)
        self.assertIsNone(c.closes, "the listing shows NO closing date on "
                                    "any of the three sources")

    def test_detail_dates(self):
        self.assertEqual(devolved.parse_citizen_space_detail(CS_DETAIL),
                         ("2026-08-06", "2026-10-29"))


class GovWalesTests(unittest.TestCase):
    def test_index_takes_open_types_including_calls_for_evidence(self):
        out = devolved.parse_govwales_index(GW_INDEX)
        self.assertEqual([c.title for c in out],
                         ["Fly-tipping: conditional cautions",
                          "A vision for culture: call for evidence"])
        self.assertEqual(out[0].key, "wales:/fly-tipping-powers")
        self.assertEqual(out[0].url,
                         "https://www.gov.wales/fly-tipping-powers")
        self.assertEqual(out[0].summary, "Environment and climate change")

    def test_detail_dates(self):
        self.assertEqual(devolved.parse_govwales_detail(GW_DETAIL),
                         ("2026-08-20", "2026-10-16"))

    def test_the_open_filter_is_the_forms_real_param(self):
        """?status=open is SILENTLY IGNORED by gov.wales; the form's radio
        value is field_consultation_status=1 (probed 2026-08-22). Pin the
        URL so nobody 'simplifies' it back."""
        self.assertIn("field_consultation_status=1",
                      devolved.SOURCES["wales"])


class DateTests(unittest.TestCase):
    def test_both_month_forms_parse_and_junk_is_none(self):
        self.assertEqual(devolved.parse_date("29 Oct 2026"), "2026-10-29")
        self.assertEqual(devolved.parse_date("16 October 2026"), "2026-10-16")
        self.assertIsNone(devolved.parse_date("sometime soon"))
        self.assertIsNone(devolved.parse_date(None))


class SeparationTests(unittest.TestCase):
    def test_dg_consultations_writes_its_own_table_only(self):
        with open(os.path.join(ROOT, "tools", "dg_consultations.py"),
                  encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("dg_consultations", source)
        for table in ("items", "mp_events"):
            for verb in ("INTO {0} ", "INTO {0}(", "UPDATE {0} "):
                self.assertNotIn(verb.format(table), source)
        for marker in ("slack", "webhook"):
            self.assertNotIn(marker, source.lower())

    def test_each_weekly_pulls_its_own_nation(self):
        for wf, nation in (("sp-weekly.yml", "scotland"),
                           ("sd-weekly.yml", "wales"),
                           ("ni-weekly.yml", "ni")):
            with open(os.path.join(ROOT, ".github", "workflows", wf),
                      encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("dg_consultations.py --nation " + nation, text,
                          wf + " must pull " + nation)


class WeeklyCadenceTripwireTests(unittest.TestCase):
    """The weekly sweep is a DECISION with a premise, and the premise is
    measurable (Christopher, 24 September 2026: "Keep devolved consultations
    in a weekly sweep as they run for a long time").

    Measured that day over 166 stored consultations: Scotland averages an
    86-day window with the shortest at 30, Wales 78 with the shortest at 28,
    and every NI consultation running under a fortnight is a job fair, a
    bursary form or an event evaluation with no area at all. Six days of
    latency against a four-week window is a fifth of it at worst.

    That reasoning expires the moment something ON OUR GROUND opens with a
    fortnight or less to run -- so the collector watches for it and says so.
    A decision recorded only in a comment is one nobody is told has stopped
    being true.
    """

    def test_the_threshold_is_the_one_the_decision_rests_on(self):
        self.assertEqual(_dgc().SHORT_WINDOW_DAYS, 14)

    def test_the_window_is_measured_from_the_two_dates(self):
        self.assertEqual(_dgc()._window_days("2026-09-01", "2026-09-29"), 28)

    def test_a_missing_date_is_not_a_short_window(self):
        """A dateless consultation must not trip the wire: 'we could not
        parse the date' and 'it closes in a week' are different facts."""
        dg = _dgc()
        self.assertIsNone(dg._window_days(None, "2026-09-29"))
        self.assertIsNone(dg._window_days("2026-09-01", None))
        self.assertIsNone(dg._window_days("not-a-date", "2026-09-29"))

    def test_the_collector_reports_a_short_window_on_our_ground(self):
        """The tripwire must actually print. A guard nobody sees is worse
        than no guard, because it looks like coverage."""
        import inspect
        src = inspect.getsource(_dgc())
        self.assertIn("SHORT WINDOW ON OUR GROUND", src)
        self.assertIn("SHORT_WINDOW_DAYS", src)
        # It fires only for items that MATCHED: a short job-fair survey with
        # no area is exactly what the weekly cadence is allowed to be late
        # on, and NI is full of them. Checked structurally -- the append must
        # be indented deeper than the `if areas:` that guards it -- because
        # the first version of this assertion searched backwards from the
        # CONSTANT's definition near the top of the file and proved nothing.
        lines = src.splitlines()
        guard = next(i for i, l in enumerate(lines) if l.strip() == "if areas:")
        fire = next(i for i, l in enumerate(lines) if "short.append(" in l)
        self.assertGreater(fire, guard, "the tripwire runs before the guard")
        indent = len(lines[guard]) - len(lines[guard].lstrip())
        self.assertGreater(len(lines[fire]) - len(lines[fire].lstrip()), indent,
                           "the tripwire is not inside the on-our-ground branch")


if __name__ == "__main__":
    unittest.main()


def _dgc():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "dg_consultations", os.path.join(ROOT, "tools", "dg_consultations.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(key, title):
    """One open row in the finder's real shape (see CS_FINDER above)."""
    return ('<li class="dss-card consultation-state-open" '
            'data-consultation-state="open">'
            '<h2><a class="cs-no-underline" '
            'href="https://consultations.nidirect.gov.uk{0}">{1}</a></h2>'
            '<div class="row"><div class="col-md-9"><span>Summary.</span></div>'
            '<div class="col-md-3"><div class="cs-date-delta"><span>'
            '<span>Opened</span> 6 August 2026</span></div></div></div>'
            '</li>'.format(key, title))


class CitizenSpacePaginationTests(unittest.TestCase):
    """21 Sept 2026: the NI finder held 107 open consultations over four pages
    and the collector read the first, so 56 had never been stored. Items rise
    onto page one only as those above them close, so a consultation was met
    near the end of its life."""

    def _client(self, pages):
        """pages: {b_start: [(key, title), ...]}. Records the URLs fetched."""
        class C:
            def __init__(self):
                self.urls = []

            def get_text(self, url, feed, slug, archive=True):
                self.urls.append(url)
                start = 0
                if "b_start=" in url:
                    start = int(url.split("b_start=")[1].split("&")[0])
                return ('<ul id="consultations" class="list-unstyled">'
                        + "".join(_row(k, t) for k, t in pages.get(start, []))
                        + "</ul>")
        return C()

    def test_it_pages_with_b_start_until_a_short_page(self):
        dgc = _dgc()
        pages = {0: [("/a%d/" % i, "A%d" % i) for i in range(30)],
                 30: [("/b%d/" % i, "B%d" % i) for i in range(30)],
                 60: [("/c%d/" % i, "C%d" % i) for i in range(17)]}
        client = self._client(pages)
        out = dgc.fetch_open(client, "ni", lambda m: None)
        self.assertEqual(len(out), 77, "every page, not just the first 30")
        self.assertIn("b_start=30", " ".join(client.urls))
        self.assertIn("b_start=60", " ".join(client.urls))
        self.assertNotIn("b_start=0", client.urls[0], "page one carries no b_start")

    def test_a_listing_that_ignores_the_parameter_stops_after_one_extra_fetch(self):
        """?page=2 returned page one again; that is how the paging was missed.
        A renamed b_start must not collect the first page twelve times."""
        dgc = _dgc()
        same = [("/a%d/" % i, "A%d" % i) for i in range(30)]
        client = self._client({0: same, 30: same, 60: same, 90: same})
        out = dgc.fetch_open(client, "ni", lambda m: None)
        self.assertEqual(len(out), 30)
        self.assertEqual(len(client.urls), 2, "one page, one probe, then stop")

    def test_a_single_page_nation_costs_one_fetch(self):
        dgc = _dgc()
        client = self._client({0: [("/s%d/" % i, "S%d" % i) for i in range(13)]})
        out = dgc.fetch_open(client, "scotland", lambda m: None)
        self.assertEqual(len(out), 13)
        self.assertEqual(len(client.urls), 2, "Scotland fits one page; one probe confirms it")

    def test_the_cap_is_disclosed(self):
        dgc = _dgc()
        pages = {i * 30: [("/p%d-%d/" % (i, j), "T%d-%d" % (i, j)) for j in range(30)]
                 for i in range(dgc.CITIZEN_SPACE_MAX_PAGES + 3)}
        said = []
        out = dgc.fetch_open(self._client(pages), "ni", said.append)
        self.assertEqual(len(out), 30 * dgc.CITIZEN_SPACE_MAX_PAGES)
        self.assertTrue(any("capped, later pages unseen" in m for m in said), said)


class GovWalesCallForEvidenceTests(unittest.TestCase):
    """21 Sept 2026: gov.wales labels the same two rows after the exercise, so
    a call for evidence says "Call for evidence ends:". The detail parser
    matched only "Consultation ends:", and the National Cancer Strategy and
    the culture and sport vision sat in the store with no dates at all: the
    actionability gate cannot judge a consultation with no closing date, so
    neither could ever have reached a brief."""

    def test_a_call_for_evidence_yields_both_dates(self):
        self.assertEqual(devolved.parse_govwales_detail(GW_DETAIL_CFE),
                         ("2026-07-31", "2026-10-31"))

    def test_a_consultation_still_yields_both_dates(self):
        self.assertEqual(devolved.parse_govwales_detail(GW_DETAIL),
                         ("2026-08-20", "2026-10-16"))

    def test_a_wording_nobody_has_seen_yet_still_parses(self):
        html = GW_DETAIL_CFE.replace("Call for evidence", "Survey")
        self.assertEqual(devolved.parse_govwales_detail(html),
                         ("2026-07-31", "2026-10-31"))

    def test_a_page_with_no_label_rows_yields_nothing(self):
        self.assertEqual(devolved.parse_govwales_detail("<p>No dates here</p>"),
                         (None, None))
