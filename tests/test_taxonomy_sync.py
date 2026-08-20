"""The yaml config must be exactly what the markdown master generates.

This is what makes "never hand-edit config/taxonomy.yaml" (handoff section 11)
enforceable: edit docs/keyword-taxonomy.md, regenerate, or fail here.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import generate_taxonomy


class TaxonomySyncTests(unittest.TestCase):
    def test_yaml_matches_generated_output(self):
        with open(generate_taxonomy.CONFIG, "r", encoding="utf-8") as handle:
            on_disk = handle.read()
        self.assertEqual(
            on_disk, generate_taxonomy.generate(),
            "config/taxonomy.yaml is out of sync with docs/keyword-taxonomy.md; "
            "run: python3 tools/generate_taxonomy.py")

    def test_master_parses_eleven_areas(self):
        with open(generate_taxonomy.MASTER, "r", encoding="utf-8") as handle:
            version, areas, exclusions = generate_taxonomy.parse_master(handle.read())
        self.assertEqual(version, "0.8")
        self.assertEqual(len(areas), 11)
        self.assertEqual(len(exclusions), 8)
        self.assertIn("EOTAS", areas["6_parental_rights_education"]["tier1"])
        self.assertIn("\"small boats\"", areas["11_migration"]["tier1"])
        # v0.5: NI vocabulary, measured against the NIA corpus 2026-08-18.
        self.assertIn("\"relationships and sexuality education\"",
                      areas["6_parental_rights_education"]["tier1"])
        self.assertIn("\"Knowing Our Identity\"",
                      areas["3_gender_medicine_children"]["tier1"])
        self.assertIn("unborn", areas["1_abortion"]["tier2"])
        # v0.6: area 7 widened to civil liberties, Christopher 2026-08-20.
        seven = areas["7_free_speech_online_safety"]
        self.assertIn("\"pandemic treaty\"", seven["tier1"])
        self.assertIn("\"digital ID\"", seven["tier1"])
        self.assertIn("IHR", seven["tier1"])
        # Bare WHO is guarded as well as case-sensitive; the guard must survive
        # the round trip through the generator.
        guard = ' [with: pandemic, treaty, "health regulations", accord]'
        self.assertIn("WHO" + guard, seven["tier2"])
        # v0.8: the name SPELLED OUT is guarded too. Unguarded it filed the NI
        # motion "Addressing the Mental Health Crisis" under area 7 for citing
        # WHO research on mental health.
        self.assertIn('"World Health Organisation"' + guard, seven["tier2"])
        self.assertIn('"World Health Organization"' + guard, seven["tier2"])
        # The display-label override. Only area 7 declares one: make_5ca.py
        # builds CSV filenames from the label, so relabelling an area renames
        # its sheets and the other ten must keep the key-derived label.
        self.assertEqual(seven["name"],
                         "Free speech, privacy and civil liberties")
        named = [k for k, v in areas.items() if v.get("name")]
        self.assertEqual(named, ["7_free_speech_online_safety"])
        # v0.7: child sexual exploitation belongs to area 6, child protection
        # (Christopher 2026-08-20). CSE is all-caps so it matches
        # case-sensitively and cannot fire inside "case" or a lowercase word.
        six = areas["6_parental_rights_education"]
        for term in ('"child sexual exploitation"', '"rape gang*"', "CSE"):
            self.assertIn(term, six["tier2"])


if __name__ == "__main__":
    unittest.main()
