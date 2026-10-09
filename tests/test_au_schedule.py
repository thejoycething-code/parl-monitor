"""Australia's week ahead (tools/au_schedule.py) and its Coming up section
(tools/au_monitor.py). No network: the Register's and the Handbook's own
responses of 9 October 2026, trimmed, in tests/fixtures/au."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIX = os.path.join(ROOT, "tests", "fixtures", "au")

from src import db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aus = _load("au_schedule")
aum = _load("au_monitor")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
TODAY = "2026-10-09"


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


class FakeClient:
    def __init__(self, pages):
        self.pages, self.asked = dict(pages), []

    def get_json(self, url, feed, slug, archive=True, **kw):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "404")
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return json.loads(json.dumps(page))


def pages(**extra):
    out = {aus.OPEN_FOR_DISALLOWANCE: fixture("frl_open_disallowance.json"),
           aus.PARLIAMENTS: fixture("handbook_parliaments.json"),
           aus.SCRUTINY.format("F2026L00816"): fixture("frl_scrutiny_F2026L00816.json")}
    out.update(extra)
    return out


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def run(conn, client, acts_watch=None):
    return aus.run(conn, client, TODAY, tax=TAX, log=lambda *_: None,
                   acts_watch=acts_watch if acts_watch is not None else {})


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.rows = aus.parse_open(fixture("frl_open_disallowance.json"))

    def test_every_open_instrument_comes_with_its_last_days(self):
        self.assertEqual(len(self.rows), 14)
        fuel = next(r for r in self.rows if r["title_id"] == "F2026L00968")
        self.assertEqual((fuel["last_day_house"], fuel["last_day_senate"]),
                         ("2026-10-12", "2026-10-12"))
        self.assertEqual(fuel["acts"], ["C2006A00072"])

    def test_no_clock_is_none_never_the_year_9999(self):
        radio = next(r for r in self.rows if r["title_id"] == "F2026L01200")
        self.assertIsNone(radio["last_day_house"])
        self.assertIsNone(radio["last_day_senate"])

    def test_only_last_days_still_ahead_are_sitting_days(self):
        days = aus.sitting_days(self.rows, TODAY)
        self.assertIn(("house", "2026-10-12"), days)
        self.assertIn(("senate", "2026-11-17"), days)
        # 15 and 17 September are past: the House's clocks ended then.
        self.assertNotIn(("house", "2026-09-17"), days)
        self.assertNotIn(("house", "2026-09-15"), days)
        self.assertTrue(all(d >= TODAY for _c, d in days))

    def test_a_disallowance_motion_names_its_sponsor_and_house(self):
        events = aus.parse_scrutiny(fixture("frl_scrutiny_F2026L00816.json"))
        motion = [e for e in events if e["type"] == "DisallowanceMotion"]
        self.assertEqual(motion, [{"type": "DisallowanceMotion", "date": "2026-09-16",
                                   "house": "senate", "sponsor": "Senator Price"}])
        self.assertEqual([e["type"] for e in events][:2], ["Tabled", "Tabled"])

    def test_the_handbook_says_whether_a_parliament_is_dissolved(self):
        parls = {p["parliament"]: p for p in aus.parse_parliaments(fixture("handbook_parliaments.json"))}
        self.assertIsNone(parls[48]["dissolution"])
        self.assertEqual(parls[47]["dissolution"], "2025-03-28")


class StoreTests(unittest.TestCase):
    def test_a_run_stores_instruments_days_and_parliaments_and_stamps_its_heartbeat(self):
        conn = store()
        s = run(conn, FakeClient(pages()))
        self.assertEqual((s["open"], s["gaps"]), (14, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM au_instruments WHERE open=1").fetchone()[0], 14)
        self.assertGreater(conn.execute("SELECT COUNT(*) FROM au_sitting_days").fetchone()[0], 10)
        self.assertEqual(conn.execute("SELECT note FROM source_runs WHERE source='AU week ahead'")
                         .fetchone()[0][:15], "step heartbeat:")
        self.assertIsNone(conn.execute("SELECT dissolution FROM au_parliaments WHERE parliament=48")
                          .fetchone()[0])

    def test_migration_is_matched_but_not_our_ground_so_no_scrutiny_is_read(self):
        conn = store()
        client = FakeClient(pages())
        s = run(conn, client)
        self.assertEqual(s["ours"], 0)
        self.assertEqual(conn.execute("SELECT areas FROM au_instruments WHERE title_id='F2026L00876'")
                         .fetchone()[0], "[11]")
        self.assertFalse(any("parliamentaryScrutiny" in u for u in client.asked))

    def test_a_watched_act_lends_its_areas_by_register_id_and_the_motion_is_read(self):
        conn = store()
        # Suppose the VET Regulator's Act were watched: its instrument carries
        # a Senate disallowance motion (Senator Price, 16 September 2026).
        vet = next(r for r in aus.parse_open(fixture("frl_open_disallowance.json"))
                   if r["title_id"] == "F2026L00816")
        watch = {vet["acts"][0]: ([6], "test")}
        s = run(conn, FakeClient(pages()), acts_watch=watch)
        self.assertEqual((s["ours"], s["motions"]), (1, 1))
        row = conn.execute("SELECT areas, areas_from, scrutiny FROM au_instruments "
                           "WHERE title_id='F2026L00816'").fetchone()
        self.assertEqual((row[0], row[1]), ("[6]", "act"))
        self.assertIn("Senator Price", row[2])

    def test_an_enabling_act_of_this_parliament_keys_the_instrument_on_its_bill(self):
        conn = store()
        fuel_act = "C2006A00072"
        conn.execute("INSERT INTO au_bills (bill_id, parliament, title, act_id, areas) "
                     "VALUES ('r7999', 48, 'Fuel Bill 2026', ?, '[7]')", (fuel_act,))
        run(conn, FakeClient(pages(**{aus.SCRUTINY.format("F2026L00968"): {
            "parliamentaryScrutiny": []}})))
        row = conn.execute("SELECT bill_id, areas, areas_from FROM au_instruments "
                           "WHERE title_id='F2026L00968'").fetchone()
        self.assertEqual(tuple(row), ("r7999", "[7]", "bill"))

    def test_an_instrument_no_longer_listed_is_closed(self):
        conn = store()
        run(conn, FakeClient(pages()))
        smaller = fixture("frl_open_disallowance.json")
        smaller["value"] = smaller["value"][:2]
        run(conn, FakeClient(pages(**{aus.OPEN_FOR_DISALLOWANCE: smaller})))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM au_instruments WHERE open=1").fetchone()[0], 2)

    def test_more_listed_than_read_is_a_gap(self):
        conn = store()
        capped = fixture("frl_open_disallowance.json")
        capped["@odata.count"] = 600
        s = run(conn, FakeClient(pages(**{aus.OPEN_FOR_DISALLOWANCE: capped})))
        self.assertEqual((s["open"], s["gaps"]), (14, 1))

    def test_a_refused_register_is_a_gap_and_no_heartbeat(self):
        conn = store()
        s = run(conn, FakeClient(pages(**{aus.OPEN_FOR_DISALLOWANCE: FetchError("u", "f", "s", 1, "403")})))
        self.assertEqual(s["gaps"], 1)
        self.assertIsNone(conn.execute("SELECT 1 FROM source_runs WHERE source='AU week ahead'").fetchone())
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='au-schedule'").fetchone()[0], 1)

    def test_a_dry_run_stores_nothing(self):
        conn = store()
        aus.run(conn, FakeClient(pages()), TODAY, tax=TAX, log=lambda *_: None, dry=True,
                acts_watch={})
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM au_instruments").fetchone()[0], 0)


class ComingUpTests(unittest.TestCase):
    def test_never_collected_says_so(self):
        text = aum.render_edition(store(), TODAY)
        self.assertIn("## Coming up", text)
        self.assertIn("tools/au_schedule.py has not run on this store", text)

    def test_the_section_names_the_next_sittings_and_says_what_it_cannot_see(self):
        conn = store()
        run(conn, FakeClient(pages()))
        text = aum.render_edition(conn, TODAY)
        section = text.split("## Coming up")[1].split("\n## ")[0]
        self.assertIn("aph.gov.au, which refuses our collectors", section)
        self.assertIn("**House**: next sitting Monday 12 October", section)
        self.assertIn("17 to 19 November", section)
        self.assertIn("Instruments open for disallowance on our ground: 0 of 14", section)
        self.assertIn("**Monday 12 October**: Parliament next sits", text)
        self.assertNotIn("—", text)
        self.assertIn("*Coming up:* House next sits 12 October", aum.dm_summary(conn, TODAY))

    def test_an_instrument_on_our_ground_shows_its_window_and_motion(self):
        conn = store()
        vet = next(r for r in aus.parse_open(fixture("frl_open_disallowance.json"))
                   if r["title_id"] == "F2026L00816")
        run(conn, FakeClient(pages()), acts_watch={vet["acts"][0]: ([6], "test")})
        section = aum.render_edition(conn, TODAY).split("## Coming up")[1].split("\n## ")[0]
        self.assertIn("F2026L00816", section)
        self.assertIn("House 15 September (passed), Senate no clock running", section)
        self.assertIn("Notice of a disallowance motion**: Senator Price, Senate, 16 September", section)
        self.assertIn("1 disallowance motion(s)", aum.dm_summary(conn, TODAY))

    def test_a_dissolution_leads_the_section(self):
        conn = store()
        dissolved = fixture("handbook_parliaments.json")
        dissolved["value"][0]["DateDissolution"] = "2028-03-01"
        run(conn, FakeClient(pages(**{aus.PARLIAMENTS: dissolved})))
        self.assertIn("was dissolved on 2028-03-01", aum.render_edition(conn, TODAY))

    def test_day_runs_fold_consecutive_days_and_bridge_weekends(self):
        self.assertEqual(aum.day_runs(["2026-10-12", "2026-10-13", "2026-10-15"]),
                         "12 to 13 October, 15 October")
        self.assertEqual(aum.day_runs(["2026-10-15", "2026-10-16", "2026-10-19"]),
                         "15 to 19 October")
        self.assertEqual(aum.day_runs(["2026-10-30", "2026-11-02"]), "30 October to 2 November")


class WatchlistTests(unittest.TestCase):
    def test_the_acts_list_is_keyed_on_register_title_ids(self):
        from src import au_store
        acts = au_store.act_watchlist()
        self.assertIn("C2021A00076", acts)   # Online Safety Act 2021
        for key in acts:
            self.assertRegex(key, r"^C\d{4}A\d{5}$")


if __name__ == "__main__":
    unittest.main()
