"""The new-country 5CA tracker and partner sheet (tools/make_country_5ca_web.py).
Small temporary stores and stance files; no network."""

import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import at_store  # noqa: E402
from src import country5ca as c5  # noqa: E402
import make_country_5ca_web as web  # noqa: E402
from test_country_5ca import PL_STANCE, PL_WL, QUIET, pl_store_at  # noqa: E402

AT_STANCE = c5.header("at") + """
bill_directions:
  - key: "XXVIII/UEA/26"
    direction: with
    status: draft
    why: "Protects the two biological sexes."

divisions:
"""


def at_store_at(path):
    conn = sqlite3.connect(path)
    at_store.ensure_schema(conn)
    conn.execute("INSERT INTO at_items (item_key, gp, chamber, title, areas, tier) VALUES "
                 "('XXVIII/UEA/26', 'XXVIII', 'NR', 'Schutz der biologischen Geschlechter', "
                 "'[5]', 1)")
    conn.execute("INSERT INTO at_divisions (division_key, item_key, date, body, question, "
                 "areas) VALUES ('k1', 'XXVIII/UEA/26', '2025-03-27', 'NR', "
                 "'Unselbständiger Entschließungsantrag', '[5]')")
    conn.executemany("INSERT INTO at_votes (division_key, klub, position) VALUES (?,?,?)",
                     [("k1", "FPÖ", "Dafür"), ("k1", "ÖVP", "Dagegen")])
    conn.executemany("INSERT INTO at_members (pad, name, chamber, klub) VALUES (?,?,?,?)",
                     [("1", "Frau F", "NR", "FPÖ"), ("2", "Herr G", "NR", "FPÖ"),
                      ("3", "Frau O", "NR", "ÖVP")])
    conn.commit()
    conn.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.cfg = os.path.join(t, "config")
        os.makedirs(self.cfg)
        with open(c5.stance_path("pl", self.cfg), "w", encoding="utf-8") as h:
            h.write(PL_STANCE)
        with open(c5.stance_path("at", self.cfg), "w", encoding="utf-8") as h:
            h.write(AT_STANCE)
        self.pl_db = os.path.join(t, "pl.db")
        pl_store_at(self.pl_db).close()
        self.at_db = os.path.join(t, "at.db")
        at_store_at(self.at_db)
        for cc, path, wl in (("pl", self.pl_db, PL_WL), ("at", self.at_db, {"XXVIII/UEA/26": {}})):
            ro = c5.connect_ro(path)
            c5.draft(ro, cc, self.cfg, "2026-10-10", QUIET, wl=wl)
            ro.close()
        self.internal = os.path.join(t, "docs", "5ca-countries.html")
        self.partner = os.path.join(t, "site", "5ca-countries.html")
        self.state = os.path.join(t, "5ca", "country-web-state.json")

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, today="2026-10-11", stores=None):
        stores = {"pl": self.pl_db, "at": self.at_db} if stores is None else stores
        return web.build(["pl", "at"], stores, "/no/such.db", self.cfg, today,
                         self.internal, self.partner, self.state, log=QUIET)

    def read(self, path):
        with open(path, encoding="utf-8") as h:
            return h.read()


class AwaitingTests(Base):
    def test_nothing_confirmed_means_placeholder_and_no_partner_page(self):
        states, partner = self.build()
        self.assertFalse(partner)
        self.assertFalse(os.path.exists(self.partner))
        page = self.read(self.internal)
        pl = c5.counts("pl", self.cfg)
        n = pl["proposed"] + pl["procedural"] + pl["needs_reading"]
        self.assertIn("Awaiting sign-off: {0} readings".format(n), page)
        self.assertIn("Poland (awaiting sign-off: {0})".format(n), page)
        # no placement of any kind, drafted or guessed
        for word in ("Strong ally (", "Strong opponent (", "Anna Adamska", "Frau F"):
            self.assertNotIn(word, page)
        self.assertIn("docs/5ca-pl-readings.md", page)
        self.assertFalse(os.path.exists(self.state))

    def test_awaiting_needs_no_store(self):
        states, _ = self.build(stores={})
        self.assertTrue(all(st["gap"] is None for st in states))

    def test_stale_partner_page_is_removed(self):
        os.makedirs(os.path.dirname(self.partner))
        with open(self.partner, "w") as h:
            h.write("old")
        self.build()
        self.assertFalse(os.path.exists(self.partner))


class ConfirmedTests(Base):
    def setUp(self):
        super().setUp()
        c5.confirm("pl", ["pl-10-1-1"], "Christopher", "2026-10-10", self.cfg, log=QUIET)

    def test_partner_page_carries_confirmed_countries_only(self):
        states, partner = self.build()
        self.assertTrue(partner)
        page = self.read(self.partner)
        self.assertIn('id="cc-pl"', page)
        self.assertNotIn('id="cc-at"', page)                 # Austria: nothing confirmed
        self.assertIn("Anna Adamska", page)
        self.assertIn("Strong ally (1)", page)
        self.assertIn("Strong opponent (1)", page)
        self.assertIn("Marriage and family", page)
        # the internal working layer stays internal
        self.assertNotIn("stance_signers", page)
        self.assertNotIn("readings.md", page)
        self.assertNotIn("signed reading", page)            # confidence tooltips
        internal = self.read(self.internal)
        self.assertIn('id="cc-at"', internal)
        self.assertIn("Austria (awaiting sign-off:", internal)

    def test_drafts_place_no_one_beside_a_confirmed_reading(self):
        states, _ = self.build()
        pl = next(st for st in states if st["cc"] == "pl")
        rows = {r["decision_maker"].split(" (")[0]: r for r in pl["sheets"][0]["rows"]}
        self.assertEqual(rows["Celina Czarnecka"]["column"], "0")   # only a draft says otherwise
        self.assertIn("3 more votes awaiting sign-off, not counted", self.read(self.partner))

    def test_page_and_csv_share_the_gate(self):
        out = os.path.join(self.tmp.name, "csv")
        ro = c5.connect_ro(self.pl_db)
        written = c5.run_sheets(ro, "pl", self.cfg, out, "2026-10-11", QUIET)
        ro.close()
        states, _ = self.build()
        pl = next(st for st in states if st["cc"] == "pl")
        self.assertEqual(len(written), len(pl["sheets"]))

    def test_change_since_last_week(self):
        self.build("2026-10-11")
        self.assertIn("this week is the baseline", self.read(self.partner))
        hist = json.load(open(self.state))
        self.assertIn("pl|sejm|9", hist)
        c5.confirm("pl", ["pl-10-1-4"], "Christopher", "2026-10-17", self.cfg, log=QUIET)
        self.build("2026-10-18")
        page = self.read(self.partner)
        self.assertIn("Since last week:", page)              # Celina now placed by the reject vote

    def test_unreadable_store_fails_closed(self):
        states, partner = self.build(stores={"pl": "/no/such.db"})
        self.assertFalse(partner)
        self.assertIn("Not shown this week", self.read(self.internal))

    def test_unconfirming_withdraws_the_partner_page(self):
        self.build()
        path = c5.stance_path("pl", self.cfg)
        text = self.read(path).replace("status: confirmed", "status: draft")
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        self.build()
        self.assertFalse(os.path.exists(self.partner))


class DerivedTests(Base):
    def test_party_group_rows_are_labelled_derived(self):
        c5.confirm("at", ["k1"], "Christopher", "2026-10-10", self.cfg, log=QUIET)
        states, partner = self.build()
        self.assertTrue(partner)
        page = self.read(self.partner)
        self.assertIn('id="cc-at"', page)
        self.assertIn('Frau F (FPÖ)<span class="tag d">DERIVED</span>', page)
        self.assertIn("carry their group's vote", page)
        self.assertNotIn("[DERIVED]", page)


class NavTests(unittest.TestCase):
    def test_partner_nav_links_the_page_only_when_published(self):
        from src import partner
        with tempfile.TemporaryDirectory() as site:
            self.assertEqual(partner.countries_5ca_nav(site), "")
            open(os.path.join(site, "5ca-countries.html"), "w").close()
            self.assertIn("/5ca-countries.html", partner.countries_5ca_nav(site))


if __name__ == "__main__":
    unittest.main()
