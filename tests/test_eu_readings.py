"""The EU 5CA's drafted readings (9 October 2026): drafts place nobody, the
sign-off guide round-trips, a tick cannot sign a reading nobody wrote, and the
absence rule caps ++ for a member who sat that day and did not vote."""

import importlib.util
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, eureadings, readings5ca  # noqa: E402

CONFIG = os.path.join(ROOT, "config", "eu_divisions.yaml")
DOC = os.path.join(ROOT, "docs", "5ca-eu-readings.md")

SIGNED_BY_CHRISTOPHER = {
    "MTG-PL-2026-07-09-DEC-195749", "MTG-PL-2026-07-07-DEC-195338",
    "MTG-PL-2026-07-07-DEC-194870", "MTG-PL-2026-09-15-DEC-195987",
    "MTG-PL-2026-07-09-DEC-195775", "MTG-PL-2026-07-09-DEC-195807",
    "MTG-PL-2026-07-09-DEC-195778", "MTG-PL-2026-09-17-DEC-196806",
    "MTG-PL-2026-09-17-DEC-196809", "MTG-PL-2026-07-08-DEC-195637",
    "MTG-PL-2026-07-08-DEC-195627", "MTG-PL-2026-07-08-DEC-195626",
}


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fca = _load("make_eu_5ca")

SAMPLE = """divisions:
  V-SIGNED:
    short: "Signed by hand"
    date: 2026-07-09
    our_side: favor
    signed_off: true   # Christopher, 2026-09-01

  # --- a family comment ---
  MTG-PL-1-DEC-1:
    short: "Report: whole"
    date: 2026-09-16
    our_side: against
    meaning_favor: "f"
    meaning_against: "a"
    confidence: high
    draft: true
    drafted: "Claude, 9 October 2026"
    signed_off: false
  MTG-PL-1-DEC-2:
    short: "Report: Am 3"
    date: 2026-09-16
    our_side: null
    read_first: "not in the store"
    draft: true
    signed_off: false
  MTG-PL-1-DEC-3:
    short: "Report: § 2"
    date: 2026-09-16
    our_side: null
    placeable: false
    reason: "near-unanimous"
    draft: true
    signed_off: false
"""


class ShippedDraftsTests(unittest.TestCase):
    def setUp(self):
        self.cfg = eureadings.load(CONFIG)

    def test_only_christophers_twelve_are_signed(self):
        signed = {k for k, v in self.cfg.items() if v.get("signed_off")}
        self.assertEqual(signed, SIGNED_BY_CHRISTOPHER)

    def test_every_draft_is_unsigned_and_complete(self):
        drafts = {k: v for k, v in self.cfg.items() if v.get("draft")}
        self.assertGreater(len(drafts), 300)
        for key, e in drafts.items():
            self.assertIs(e.get("signed_off"), False, key)
            self.assertTrue(e.get("drafted"), key)
            if e.get("our_side"):
                self.assertIn(e["our_side"], ("favor", "against"), key)
                self.assertTrue(e.get("meaning_favor") and e.get("meaning_against"), key)
                self.assertIn(e.get("confidence"), ("high", "medium", "low"), key)
            elif e.get("placeable") is False:
                self.assertTrue(e.get("reason"), key)
            else:
                self.assertTrue(e.get("read_first"), key)

    def test_the_5ca_reads_only_signed_divisions(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        for key in self.cfg:
            conn.execute("INSERT INTO eu_divisions (vote_id, date, first_seen, last_seen) "
                         "VALUES (?, ?, 'x', 'x')", (key, str(self.cfg[key].get("date"))))
        got = {d["vote_id"] for d in fca.signed_divisions(conn, CONFIG)}
        self.assertEqual(got, SIGNED_BY_CHRISTOPHER)

    def test_the_guide_is_current(self):
        with open(DOC, encoding="utf-8") as h:
            self.assertEqual(h.read(), eureadings.signoff_markdown(self.cfg),
                             "regenerate: python3 tools/make_eu_5ca.py --signoff-doc")

    def test_the_guide_has_one_box_per_division_and_ticks_only_the_signed(self):
        text = open(DOC, encoding="utf-8").read()
        boxes = readings5ca._TICK.findall(text)
        self.assertEqual({k for _m, k in boxes}, set(self.cfg))
        self.assertEqual(set(readings5ca.ticked_keys(text)), SIGNED_BY_CHRISTOPHER)


class SigningTests(unittest.TestCase):
    def test_status(self):
        cfg = yaml.safe_load(SAMPLE)["divisions"]
        self.assertEqual({k: eureadings.status(v) for k, v in cfg.items()},
                         {"V-SIGNED": "confirmed", "MTG-PL-1-DEC-1": "draft",
                          "MTG-PL-1-DEC-2": "unread", "MTG-PL-1-DEC-3": "draft"})

    def test_sign_keys_signs_drafts_and_skips_a_reading_nobody_wrote(self):
        keys = {"MTG-PL-1-DEC-1", "MTG-PL-1-DEC-2", "MTG-PL-1-DEC-3", "V-SIGNED"}
        new, signed, skipped = eureadings.sign_keys(SAMPLE, keys, "  # Christopher, today")
        self.assertEqual(signed, ["MTG-PL-1-DEC-1", "MTG-PL-1-DEC-3"])
        self.assertEqual(skipped, ["MTG-PL-1-DEC-2"])
        cfg = yaml.safe_load(new)["divisions"]
        self.assertTrue(cfg["MTG-PL-1-DEC-1"]["signed_off"])
        self.assertNotIn("draft", cfg["MTG-PL-1-DEC-1"])
        self.assertEqual(eureadings.status(cfg["MTG-PL-1-DEC-3"]), "unplaceable")
        self.assertIs(cfg["MTG-PL-1-DEC-2"]["signed_off"], False)
        self.assertTrue(cfg["MTG-PL-1-DEC-2"]["draft"])
        self.assertIn("# --- a family comment ---", new)
        self.assertIn("# Christopher, 2026-09-01", new)

    def test_sign_from_doc_round_trip(self):
        tmp = tempfile.mkdtemp()
        try:
            cfg_path = os.path.join(tmp, "eu_divisions.yaml")
            doc_path = os.path.join(tmp, "5ca-eu-readings.md")
            with open(cfg_path, "w", encoding="utf-8") as h:
                h.write(SAMPLE)
            doc = eureadings.signoff_markdown(eureadings.load(cfg_path))
            self.assertIn("### [x] `V-SIGNED`", doc)
            doc = doc.replace("### [ ] `MTG-PL-1-DEC-1`", "### [x] `MTG-PL-1-DEC-1`")
            with open(doc_path, "w", encoding="utf-8") as h:
                h.write(doc)
            signed = eureadings.sign_from_doc(cfg_path, doc_path, today="2026-10-10",
                                              log=lambda *_: None)
            self.assertEqual(signed, ["MTG-PL-1-DEC-1"])
            text = open(cfg_path, encoding="utf-8").read()
            self.assertIn("signed_off: true  # Christopher, 2026-10-10, ticked in "
                          "5ca-eu-readings.md", text)
        finally:
            shutil.rmtree(tmp)


class AbsenceRuleTests(unittest.TestCase):
    def store(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        for col in ("country", "group_label"):
            try:
                conn.execute("ALTER TABLE eu_meps ADD COLUMN {0} TEXT".format(col))
            except sqlite3.OperationalError:
                pass
        conn.executescript("""
          INSERT INTO eu_meps (person_id, name, group_label, first_seen, last_seen) VALUES
            ('1', 'Voted both', 'G', 'x', 'x'), ('2', 'Sat, skipped', 'G', 'x', 'x'),
            ('3', 'Away all day', 'G', 'x', 'x'), ('4', 'Abstained', 'G', 'x', 'x');
          INSERT INTO eu_divisions (vote_id, date, first_seen, last_seen) VALUES
            ('A', '2026-07-09', 'x', 'x'), ('B', '2026-09-17', 'x', 'x'),
            ('C', '2026-09-17', 'x', 'x'), ('D', '2026-09-16', 'x', 'x');
          INSERT INTO eu_votes (vote_id, person_id, position) VALUES
            ('A', '1', 'favor'), ('B', '1', 'favor'),
            ('A', '2', 'favor'), ('D', '2', 'favor'), ('C', '2', 'against'),
            ('A', '3', 'favor'), ('D', '3', 'favor'),
            ('A', '4', 'favor'), ('D', '4', 'favor'), ('B', '4', 'abstention');
        """)
        return conn

    def test_cap_for_a_member_present_that_day(self):
        divisions = [{"vote_id": "A", "short": "a", "our_side": "favor", "date": "2026-07-09"},
                     {"vote_id": "D", "short": "d", "our_side": "favor", "date": "2026-09-16"},
                     {"vote_id": "B", "short": "b", "our_side": "favor", "date": "2026-09-17"}]
        rows = {r["name"]: r for r in fca.placements(self.store(), divisions)}
        self.assertEqual(rows["Voted both"]["column"], "++")
        self.assertEqual(rows["Sat, skipped"]["column"], "+")
        self.assertTrue(rows["Sat, skipped"]["comments"].startswith("CAPPED at +"))
        self.assertEqual(rows["Away all day"]["column"], "++",
                         "absent the whole sitting day is not capped")
        self.assertEqual(rows["Abstained"]["column"], "+")
        self.assertIn("abstained", rows["Abstained"]["comments"])


if __name__ == "__main__":
    unittest.main()
