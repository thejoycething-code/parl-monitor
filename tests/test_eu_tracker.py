"""The EU tracker arc: sign-off gates verdicts structurally, enrichment
never guesses a group, the 5CA refuses to build on unsigned meanings,
and the collector stores EVERY decision event under a matched subject
(taking consists_of[0] cost us the SDG whole-motion roll call while
storing its electronic paragraph split -- found 2026-09-01 against the
official RCV annex).
"""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tracker = _load("make_eu_tracker")
fca = _load("make_eu_5ca")
enrich = _load("eu_meps_enrich")
rolls = _load("eu_rollcalls")


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    enrich.ensure_columns(conn)
    conn.executescript("""
      INSERT INTO eu_meps (person_id, name, country, group_label,
        first_seen, last_seen) VALUES
        ('1', 'Alpha MEP', 'Ireland', 'EPP', 'x', 'x'),
        ('2', 'Beta MEP', 'France', 'Greens/EFA', 'x', 'x'),
        ('3', 'Gamma MEP', 'Poland', 'EPP', 'x', 'x');
      INSERT INTO eu_divisions (vote_id, sitting_id, date, label, favor,
        against, abstention, areas, tier, first_seen, last_seen) VALUES
        ('V-SIGNED', 'S', '2026-07-09', 'Nigeria resolution', 510, 1, 86,
         '[8]', 1, 'x', 'x'),
        ('V-UNSIGNED', 'S', '2026-07-07', 'Urgency request', 331, 304, 11,
         '[7]', 1, 'x', 'x'),
        ('V-NOPOS', 'S', '2026-07-07', 'Electronic split', 440, 146, 50,
         '[7]', 1, 'x', 'x');
      INSERT INTO eu_votes (vote_id, person_id, position) VALUES
        ('V-SIGNED', '1', 'favor'), ('V-SIGNED', '2', 'favor'),
        ('V-SIGNED', '3', 'against'),
        ('V-UNSIGNED', '1', 'against'), ('V-UNSIGNED', '2', 'against');
    """)
    conn.commit()
    return conn


CFG = {"V-SIGNED": {"short": "Nigeria", "our_side": "favor",
                    "meaning_favor": "Backed the resolution.",
                    "meaning_against": "Opposed it.", "signed_off": True},
       "V-UNSIGNED": {"short": "Urgency", "our_side": "against",
                      "meaning_favor": "Fast-tracked scanning.",
                      "meaning_against": "Refused the fast-track.",
                      "signed_off": False}}


class TrackerGateTests(unittest.TestCase):
    def test_unsigned_divisions_carry_no_verdict_fields_at_all(self):
        conn = store()
        tracker.load_config = lambda: CFG
        data = tracker.build_data(conn)
        by_id = {d["id"]: d for d in data["divisions"]}
        self.assertIn("verdict", by_id["V-SIGNED"])
        self.assertNotIn("verdict", by_id["V-UNSIGNED"],
                         "the unsigned meaning must never be embedded")
        self.assertNotIn("verdict", by_id["V-NOPOS"])

    def test_group_cohesion_is_computed_per_division(self):
        conn = store()
        tracker.load_config = lambda: CFG
        data = tracker.build_data(conn)
        signed = next(d for d in data["divisions"] if d["id"] == "V-SIGNED")
        epp = next(g for g in signed["groups"] if g["g"] == "EPP")
        self.assertEqual((epp["favor"], epp["against"]), (1, 1))

    def test_the_template_judges_only_signed_divisions(self):
        src = open(os.path.join(ROOT, "templates", "eu-votes.html"),
                   encoding="utf-8").read()
        self.assertIn('if (!d.verdict) return {cls:"N"', src)
        self.assertIn("NO SIGNED VERDICT", src)


class FcaTests(unittest.TestCase):
    def _cfg(self, tmp_cfg):
        import yaml
        path = os.path.join(ROOT, "config", "eu_divisions.yaml")
        real = yaml.safe_load(open(path, encoding="utf-8"))
        return real

    def test_the_shipped_config_matches_the_sign_off_record(self):
        # Christopher signed three verdicts on 2026-09-01 (Nigeria
        # resolution, ePrivacy fast-track, SDG whole-motion); the SDG
        # paragraph-10 split is PERMANENTLY unverdicted (split-part text
        # unreadable, no name lists). A fourth signed division is fine; a
        # signed verdict on the split is a bug.
        import yaml
        cfg = yaml.safe_load(open(os.path.join(
            ROOT, "config", "eu_divisions.yaml"), encoding="utf-8"))
        signed = {k for k, v in cfg["divisions"].items()
                  if v.get("signed_off")}
        for vote_id in ("MTG-PL-2026-07-09-DEC-195749",
                        "MTG-PL-2026-07-07-DEC-195338",
                        "MTG-PL-2026-07-07-DEC-194870"):
            self.assertIn(vote_id, signed)
        split = cfg["divisions"]["MTG-PL-2026-07-07-DEC-195295"]
        self.assertFalse(split.get("signed_off"))
        self.assertIsNone(split.get("our_side"))

    def test_placements_and_group_defiance_note(self):
        conn = store()
        divisions = [{"vote_id": "V-SIGNED", "short": "Nigeria",
                      "our_side": "favor", "date": "2026-07-09"}]
        rows = fca.placements(conn, divisions)
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(by_name["Alpha MEP"]["column"], "+")
        self.assertEqual(by_name["Gamma MEP"]["column"], "--")
        self.assertEqual(by_name["Beta MEP"]["column"], "+")


class EnrichTests(unittest.TestCase):
    def test_current_group_wants_no_end_date(self):
        mems = [
            {"membershipClassification": "def/ep-entities/EU_POLITICAL_GROUP",
             "organization": "org/5151",
             "memberDuring": {"startDate": "2024-07-16",
                              "endDate": "2024-09-18"}},
            {"membershipClassification": "def/ep-entities/EU_POLITICAL_GROUP",
             "organization": "org/7036",
             "memberDuring": {"startDate": "2024-09-19"}},
            {"membershipClassification": "def/ep-entities/COMMITTEE_PARLIAMENTARY_STANDING",
             "organization": "org/5091", "memberDuring": {}},
        ]
        self.assertEqual(enrich.current_group(mems), "7036")
        self.assertIsNone(enrich.current_group(mems[:1]),
                          "an MEP between groups stays NULL, never guessed")


class MultiEventTests(unittest.TestCase):
    def test_every_decision_event_is_stored_not_just_the_first(self):
        src = open(os.path.join(ROOT, "tools", "eu_rollcalls.py"),
                   encoding="utf-8").read()
        self.assertIn("for full_id in events:", src)
        self.assertNotIn("events[0]", src)


if __name__ == "__main__":
    unittest.main()
