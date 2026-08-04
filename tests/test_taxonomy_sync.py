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
        self.assertEqual(version, "0.4")
        self.assertEqual(len(areas), 11)
        self.assertEqual(len(exclusions), 8)
        self.assertIn("EOTAS", areas["6_parental_rights_education"]["tier1"])
        self.assertIn("\"small boats\"", areas["11_migration"]["tier1"])


if __name__ == "__main__":
    unittest.main()
