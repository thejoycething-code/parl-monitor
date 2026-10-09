"""The Supreme Court collector (tools/us_courts.py). No network.

Every fixture under tests/fixtures/us_scotus/ is a real supremecourt.gov
file fetched 9 October 2026:
  * slipopinion-24.html: the OT2024 opinions page cut to five rows across
    its two tables (Skrmetti, Mahmoud v. Taylor, Free Speech Coalition v.
    Paxton, Catholic Charities, Goldey v. Fields);
  * order-102124zor.pdf: the 21 October 2024 order list (CERTIORARI GRANTED
    with consolidation brackets, then pages of denials);
  * order-121824zr1.pdf: TikTok v. Garland, granted with the names printed
    below the bracketed dockets;
  * order-103024zr.pdf: a stay granted "In the event certiorari is granted",
    which is not a grant of certiorari;
  * docket-24-539.html: Chiles v. Salazar's case information table;
  * qp-24-297.pdf: Mahmoud v. Taylor's question presented.
"""

import importlib.util
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "us_scotus")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


uc = _load("us_courts")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = uc.empty_watchlist()


def text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def blob(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def store():
    return db.init_db(sqlite3.connect(":memory:"))


class OpinionTests(unittest.TestCase):
    rows = {r["rno"]: r for r in uc.parse_slip_page(text("slipopinion-24.html"), "24")}

    def test_both_tables_are_read(self):
        self.assertEqual(sorted(self.rows), [37, 48, 62, 63, 67])

    def test_a_row_carries_the_courts_own_holding(self):
        r = self.rows[48]
        self.assertEqual(r["case_name"], "United States v. Skrmetti")
        self.assertEqual(r["docket"], "23-477")
        self.assertEqual(r["decided"], "2025-06-18")
        self.assertIn("transgender minors", r["summary"])
        self.assertTrue(r["url"].startswith("https://www.supremecourt.gov/opinions/24pdf/"))

    def test_classified_on_the_holding_with_the_name_as_title(self):
        # Party names match nothing unless the taxonomy names the case.
        self.assertEqual(filt.filter_item(TAX, WL, "Mahmoud v. Montgomery County").issue_areas,
                         [])
        self.assertIn(7, uc.classify_case(TAX, WL, self.rows[62]).issue_areas)
        self.assertIn(3, uc.classify_case(TAX, WL, self.rows[48]).issue_areas)
        self.assertIn(6, uc.classify_case(TAX, WL, self.rows[63]).issue_areas)
        self.assertEqual(uc.classify_case(TAX, WL, self.rows[67]).issue_areas, [])

    def test_terms_turn_over_in_october(self):
        self.assertEqual(uc.current_term("2026-09-30"), "25")
        self.assertEqual(uc.current_term("2026-10-05"), "26")


class GrantTests(unittest.TestCase):
    def grants(self, name):
        return uc.parse_grants(uc.pdf_text(blob(name)))

    def test_the_granted_section_with_consolidation_brackets(self):
        self.assertEqual([d for d, _ in self.grants("order-102124zor.pdf")],
                         ["23-1067", "23-1068", "23-1229", "23-7483"])
        names = dict(self.grants("order-102124zor.pdf"))
        self.assertEqual(names["23-1067"], "OKLAHOMA, ET AL. V. EPA, ET AL.")

    def test_names_printed_under_the_brackets_are_left_to_the_docket_page(self):
        self.assertEqual(self.grants("order-121824zr1.pdf"), [("24-656", ""), ("24-657", "")])

    def test_a_stay_conditioned_on_certiorari_is_not_a_grant(self):
        self.assertEqual(self.grants("order-103024zr.pdf"), [])

    def test_grant_vacate_remand_is_not_a_grant(self):
        # Real wording, the 5 October 2026 order list.
        gvr = ("CERTIORARI -- SUMMARY DISPOSITIONS\n"
               "26-48 MULLIN, SEC., DHS, ET AL. V. NAT. TPS ALLIANCE, ET AL.\n"
               "  The petition for a writ of certiorari is granted.  The\n"
               "judgment is vacated, and the case is remanded to the United\n"
               "States Court of Appeals for the Ninth Circuit for further\n")
        self.assertEqual(uc.parse_grants(gvr), [])

    def test_case_names_are_set_in_ordinary_case(self):
        self.assertEqual(uc.case_name("OKLAHOMA, ET AL. V. EPA, ET AL."),
                         "Oklahoma, et al. v. EPA, et al.")

    def test_order_dates_come_from_the_file_name(self):
        self.assertEqual(uc.order_date(uc.BASE + "/orders/courtorders/100526zor_2a34.pdf"),
                         "2026-10-05")


class DocketTests(unittest.TestCase):
    def test_caption_and_question_link(self):
        info = uc.parse_docket(text("docket-24-539.html"))
        self.assertTrue(info["title"].startswith("Kaley Chiles, Petitioner v. Patty Salazar"))
        self.assertEqual(info["qp_url"], "../qp/24-00539qp.pdf")
        self.assertEqual(uc.short_caption(info["title"]), "Kaley Chiles v. Patty Salazar")

    def test_a_question_presented_puts_a_grant_on_our_ground(self):
        qp = uc.question_presented(uc.pdf_text(blob("qp-24-297.pdf")))
        self.assertIn("storybooks", qp)
        res = uc.classify_case(TAX, WL, {"case_name": "Mahmoud v. Taylor", "summary": qp})
        self.assertTrue(uc.on_our_ground(res.issue_areas))


class FakeClient:
    """Serves the fixtures by URL; anything else is refused."""

    def __init__(self, routes):
        self.routes, self.urls = routes, []

    def _get(self, url):
        self.urls.append(url)
        for key, value in self.routes.items():
            if key in url:
                return value
        from src.http import FetchError
        raise FetchError(url, "f", "s", 1, "403 Forbidden")

    def get_text(self, url, feed, slug, **kw):
        return self._get(url)

    def get_bytes(self, url, feed, slug, **kw):
        return self._get(url)


class PullTests(unittest.TestCase):
    def test_opinions_are_stored_and_restamped(self):
        conn = store()
        client = FakeClient({"slipopinion/24": text("slipopinion-24.html")})
        self.assertEqual(uc.pull_opinions(conn, client, "2026-10-09", ["24"], TAX, WL,
                                          log=lambda *a: None)[:2], (5, 4))
        row = conn.execute("SELECT kind, docket, areas FROM us_court_cases "
                           "WHERE case_key='opinion/24/48'").fetchone()
        self.assertEqual(row[:2], ("opinion", "23-477"))

    def test_a_refused_page_is_a_gap(self):
        conn = store()
        _r, _o, gaps = uc.pull_opinions(conn, FakeClient({}), "2026-10-09", ["24"], TAX, WL,
                                        log=lambda *a: None)
        self.assertEqual(gaps, 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed=?",
                                      (uc.FEED,)).fetchone()[0], 1)

    def test_grants_are_read_once_and_the_order_is_remembered(self):
        conn = store()
        listing = ("<a href='/orders/courtorders/102124zor_n758.pdf'>Order List</a>"
                   "<a href='/orders/courtorders/103024zr_f2ah.pdf'>Miscellaneous Order</a>")
        client = FakeClient({"ordersofthecourt/24": listing,
                             "102124zor": blob("order-102124zor.pdf"),
                             "103024zr": blob("order-103024zr.pdf"),
                             "docket/docketfiles/html/public/": text("docket-24-539.html"),
                             "qp/": blob("qp-24-297.pdf")})
        pdfs, grants, _ours, gaps = uc.pull_grants(conn, client, "2026-10-09", ["24"], TAX, WL,
                                                   log=lambda *a: None)
        self.assertEqual((pdfs, grants, gaps), (2, 4, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM us_court_orders").fetchone()[0], 2)
        row = conn.execute("SELECT case_name, decided, order_url FROM us_court_cases "
                           "WHERE case_key='grant/23-1067'").fetchone()
        self.assertEqual(row[0], "Oklahoma, et al. v. EPA, et al.")
        self.assertEqual(row[1], "2024-10-21")
        before = len(client.urls)
        self.assertEqual(uc.pull_grants(conn, client, "2026-10-16", ["24"], TAX, WL,
                                        log=lambda *a: None)[:2], (0, 0))
        self.assertEqual(len(client.urls), before + 1)          # the listing only

    def test_robots_disallowed_paths_are_never_fetched(self):
        self.assertFalse(uc.allowed("https://www.supremecourt.gov/RSS/Cases/JSON/24-539.json"))
        self.assertTrue(uc.allowed(uc.SLIP.format(term="25")))


if __name__ == "__main__":
    unittest.main()
