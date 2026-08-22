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


if __name__ == "__main__":
    unittest.main()
