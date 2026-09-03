"""What the 2026-09-03 "build it all" pass added, and what it corrected.

Two corrections are pinned here rather than left in a chat log:

1. The CJEU was reachable after all. The courts watch had recorded it as
   out of reach (curia RSS retired, InfoCuria POST-driven, both still
   true); EUR-Lex's public search was never tried and parses cleanly.
2. What the taxonomy actually judges on a court row. The search term is
   passed in WITH the title, and a CJEU search-result title is
   boilerplate, so the term supplies the area. That is evidence the
   court engaged our vocabulary, not an independent judgement of the
   case, and the stored conclusion records which term found it.
"""

import datetime
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


courts = _load("eu_courts")
monitor = _load("eu_monitor")

PAGE = ('<a href="/legal-content/EN/TXT/?uri=CELEX%3A62021CJ0621">x</a>'
        '<span class="title">Judgment of the Court (Grand Chamber) of '
        '16 July 2026.</span>'
        '<a href="/legal-content/EN/TXT/?uri=CELEX%3A62023CC0063">y</a>'
        '<span class="title">Opinion of Advocate General Norkus delivered '
        'on 4 June 2026.</span>')


class FakeClient:
    def __init__(self, html=PAGE):
        self.html = html

    def get_text(self, url, feed, slug, **kw):
        return self.html


class CjeuTests(unittest.TestCase):
    def test_celex_court_and_date_are_parsed(self):
        rows, ok = courts.eurlex_cases(
            FakeClient(), "abortion", datetime.date(2026, 1, 1),
            datetime.date(2026, 9, 3), log=lambda *a: None)
        self.assertTrue(ok)
        self.assertEqual([r["item_id"] for r in rows],
                         ["CJEU:62021CJ0621", "CJEU:62023CC0063"])
        self.assertEqual(rows[0]["doc_type"], "CJEU judgment")
        self.assertEqual(rows[1]["doc_type"], "AG opinion")
        self.assertEqual(rows[0]["date"], "2026-07-16")
        self.assertTrue(rows[0]["url"].endswith("CELEX:62021CJ0621"))

    def test_a_moved_page_shape_stores_nothing_and_reports_a_gap(self):
        """Ids but no titles = the page changed; storing blanks would be
        worse than saying so."""
        html = '<a href="?uri=CELEX%3A62021CJ0621">x</a>'
        logged = []
        rows, ok = courts.eurlex_cases(
            FakeClient(html), "abortion", datetime.date(2026, 1, 1),
            datetime.date(2026, 9, 3), log=logged.append)
        self.assertEqual(rows, [])
        self.assertFalse(ok)
        self.assertIn("page shape moved", " ".join(logged))

    def test_the_docstring_records_the_term_is_the_evidence(self):
        src = open(os.path.join(ROOT, "tools", "eu_courts.py"),
                   encoding="utf-8").read()
        self.assertIn("NOT an independent", src)
        self.assertIn("found by search term", src)


class UnsignedQueueTests(unittest.TestCase):
    def test_labels_show_what_differs_not_what_they_share(self):
        same = ("Ongoing persecution of Christians in Nigeria, notably the "
                "Kawel village massacre — RC-B10-0345/2026/REV1 "
                "– § 1 – Am 2/1")
        other = same.replace("Am 2/1", "Am 2/2")
        a, b = monitor._short_label(same), monitor._short_label(other)
        self.assertNotEqual(a, b, "six identical truncations is the bug")
        self.assertIn("Am 2/1", a)
        self.assertIn("Am 2/2", b)

    def test_a_plain_label_is_simply_shortened(self):
        self.assertEqual(monitor._short_label("Nigeria resolution"),
                         "Nigeria resolution")


class DrainCapTests(unittest.TestCase):
    def test_both_caps_were_raised_with_the_arithmetic_recorded(self):
        for tool, const in (("eu_committees", "DOC_FETCH_CAP"),
                            ("eu_pqs", "FETCH_CAP")):
            src = open(os.path.join(ROOT, "tools", tool + ".py"),
                       encoding="utf-8").read()
            self.assertIn("{0} = 300".format(const), src)


class RecallAuditTests(unittest.TestCase):
    def test_audit_exists_and_stores_nothing(self):
        src = open(os.path.join(ROOT, "tools", "eu_speeches.py"),
                   encoding="utf-8").read()
        self.assertIn("def audit(", src)
        block = src[src.index("def audit("):src.index("def main(")]
        self.assertNotIn("INSERT INTO", block)
        self.assertIn("Christian persecution", src,
                      "the first audit's finding must be acted on")


if __name__ == "__main__":
    unittest.main()
