"""The yaml config must be exactly what the markdown master generates.

This is what makes "never hand-edit config/taxonomy.yaml" (handoff section 11)
enforceable: edit docs/keyword-taxonomy.md, regenerate, or fail here.
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import generate_taxonomy


class AreaCountTests(unittest.TestCase):
    """Nothing may hardcode how many issue areas there are.

    Adding area 12 on 2026-09-04 broke two tests and would have silently
    skipped the new area's 5CA sheet, because run_monday.py looped over
    `range(1, 12)`. Every consumer must derive the set from the taxonomy,
    which is the only file that knows.
    """

    def test_no_module_hardcodes_the_area_range(self):
        import glob
        bad = []
        for path in (glob.glob(os.path.join(ROOT, "tools", "*.py"))
                     + glob.glob(os.path.join(ROOT, "src", "*.py"))
                     + [os.path.join(ROOT, "run_monday.py")]):
            src = open(path, encoding="utf-8").read()
            for m in re.finditer(r"range\(1,\s*1[0-9]\)", src):
                line_start = src.rfind("\n", 0, m.start()) + 1
                line = src[line_start:src.find("\n", m.start())]
                if line.lstrip().startswith("#"):
                    continue          # a comment recording the old bug
                bad.append("{0}: {1}".format(os.path.basename(path),
                                             line.strip()[:70]))
        self.assertEqual(bad, [], "these hardcode the area range: {0}".format(bad))

    def test_the_area_names_map_covers_every_area(self):
        """src/digest.py names areas by hand; a missing entry prints a
        bare number in the edition."""
        import yaml
        from src import digest
        tax = yaml.safe_load(open(os.path.join(ROOT, "config", "taxonomy.yaml"),
                                  encoding="utf-8"))
        keys = {int(k.split("_", 1)[0]) for k in tax["areas"]}
        self.assertEqual(sorted(keys - set(digest.AREA_NAMES)), [],
                         "areas with no display name")


class TaxonomySyncTests(unittest.TestCase):
    def test_yaml_matches_generated_output(self):
        with open(generate_taxonomy.CONFIG, "r", encoding="utf-8") as handle:
            on_disk = handle.read()
        self.assertEqual(
            on_disk, generate_taxonomy.generate(),
            "config/taxonomy.yaml is out of sync with docs/keyword-taxonomy.md; "
            "run: python3 tools/generate_taxonomy.py")

    def test_master_parses_every_area(self):
        with open(generate_taxonomy.MASTER, "r", encoding="utf-8") as handle:
            version, areas, exclusions = generate_taxonomy.parse_master(handle.read())
        self.assertEqual(version, "1.8")
        self.assertEqual(len(areas), 12)
        # v1.7 (17 Sept 2026): ePrivacy at tier 1. The Parliament's second
        # reading on the chat-control derogation ran to 28 roll calls on
        # 9 July -- two proposals to reject the Council position, and the
        # amendment excluding end-to-end encrypted communications -- and the
        # monitor collected none of them, because the item is labelled
        # "Temporary derogation from the ePrivacy directive ***II" and
        # nothing in the taxonomy said ePrivacy.
        self.assertIn("ePrivacy", areas["7_free_speech_online_safety"]["tier1"])
        # v1.8: "social media" GUARDED in area 6. The EP resolution of 17 Sept
        # on social media and young people matched nothing, because adopted
        # texts are filtered on title alone and EP titles are generic. Bare, the
        # phrase matches 107 corpus rows; guarded it keeps 14.
        self.assertTrue(any("social media" in t for t in areas["6_parental_rights_education"]["tier2"]),
                        "the guarded social media term is missing from area 6")
        self.assertNotIn('"social media"', areas["6_parental_rights_education"]["tier2"],
                         "it must stay GUARDED: bare, it admits press-office traffic")
        # v1.6: prostitution and sexual exploitation, the Nordic-model
        # ground that no area covered.
        self.assertIn("\"commercial sexual exploitation\"",
                      areas["12_prostitution"]["tier1"])
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
        named = sorted(k for k, v in areas.items() if v.get("name"))
        # Area 12 declares one too, from v1.6: its heading (prostitution,
        # trafficking and sexual exploitation) is wider than the key it
        # must keep, and it had never had a 5CA sheet to rename. Any
        # FURTHER label must be a deliberate decision for the same reason
        # -- an existing area's sheets are named from its label.
        self.assertEqual(named, ["12_prostitution",
                                 "7_free_speech_online_safety"])
        # v0.7: child sexual exploitation belongs to area 6, child protection
        # (Christopher 2026-08-20). CSE is all-caps so it matches
        # case-sensitively and cannot fire inside "case" or a lowercase word.
        six = areas["6_parental_rights_education"]
        for term in ('"child sexual exploitation"', '"rape gang*"', "CSE"):
            self.assertIn(term, six["tier2"])


if __name__ == "__main__":
    unittest.main()


class GermanTaxonomyTests(unittest.TestCase):
    """The German master generates its own yaml, and the two taxonomies stay
    the same twelve areas. Added 22 September 2026 with the German first draft.
    """

    def test_yaml_matches_its_own_master(self):
        master, config = generate_taxonomy.MASTERS["de"]
        with open(config, "r", encoding="utf-8") as handle:
            on_disk = handle.read()
        self.assertEqual(
            on_disk, generate_taxonomy.generate(master, "de"),
            "config/taxonomy-de.yaml is out of sync with its master; run: "
            "python3 tools/generate_taxonomy.py --lang de")

    def test_the_header_names_its_own_master_and_command(self):
        """A generated file's header is the only instruction most people read.
        The first German yaml told the reader to edit the ENGLISH master and
        run a command that would have overwritten the English yaml."""
        _master, config = generate_taxonomy.MASTERS["de"]
        with open(config, "r", encoding="utf-8") as handle:
            head = "".join(handle.readlines()[:3])
        self.assertIn("docs/keyword-taxonomy-de.md", head)
        self.assertIn("--lang de", head)
        self.assertNotIn("docs/keyword-taxonomy.md\n", head)

    def test_both_languages_carry_the_same_areas(self):
        """Area keys are CitizenGO's positions, not a country's vocabulary.
        src/intel.area_names() reads the English file for every surface, so a
        German-only key would render as a bare number."""
        import yaml
        loaded = {}
        for lang, (_m, config) in generate_taxonomy.MASTERS.items():
            with open(config, "r", encoding="utf-8") as handle:
                loaded[lang] = set((yaml.safe_load(handle).get("areas") or {}))
        self.assertEqual(loaded["de"], loaded["en"],
                         "the two taxonomies must describe the same areas")


class GermanRegressionTests(unittest.TestCase):
    """The votes the German draft was validated against, locked down.

    Every one was probed live against the real Bundestag on 22 September 2026
    (abgeordnetenwatch polls, legislatures 132 and 161) before the draft was
    committed. If a later edit to the German master stops one of these
    matching, the edit has broken something that was working.
    """

    CASES = [
        ("Änderung des Schwangerschaftskonfliktgesetzes", {1}),
        # The LABEL alone is area 5, the self-ID law. Area 3 came from the
        # vote's intro text in the live probe, where the repealed
        # Transsexuellengesetz and the clinical vocabulary appear -- which
        # is the body-beats-title lesson in German.
        ("Selbstbestimmungsgesetz", {5}),
        ("Selbstbestimmungsgesetz: Änderung des Transsexuellengesetzes "
         "und der Geschlechtsdysphorie-Behandlung Minderjähriger", {3, 5}),
        ("Suizidhilfegesetz", {2}),
        ("Förderung der geschäftsmäßigen Sterbehilfe grundsätzlich", {2}),
        ("Suizidprävention stärken", {2}),
        ("Änderung des Bundeszentralregistergesetzes: Volksverhetzung", {7}),
        ("Streichung des Straftatbestandes der Politikerbeleidigung "
         "zum Schutz der Meinungsfreiheit", {7}),
        ("Aussetzung des Familiennachzugs für subsidiär Schutzberechtigte", {11}),
    ]

    def _filter(self):
        from src import filter as filt
        _master, config = generate_taxonomy.MASTERS["de"]
        return filt, filt.load_taxonomy(config), filt.load_watchlist(
            os.path.join(ROOT, "config", "watchlist.yaml"))

    def test_the_validated_votes_still_match(self):
        filt, tax, wl = self._filter()
        for label, expected in self.CASES:
            got = set(filt.filter_item(tax, wl, label).issue_areas or [])
            self.assertTrue(expected <= got,
                            "{0!r} lost area(s) {1}; got {2}".format(
                                label, sorted(expected - got), sorted(got)))

    def test_ordinary_german_business_is_not_swept_up(self):
        """The counterweight: these are real Bundestag vote labels with
        nothing of ours in them. If the draft starts matching them, a term has
        become too broad -- which in German usually means a bare short word."""
        filt, tax, wl = self._filter()
        for label in ("Sportfördergesetz",
                      "Gebäudemodernisierungsgesetz",
                      "Einführung eines allgemeinen Tempolimits",
                      "Etat des Bundesministeriums für Verkehr",
                      "Vierter Entschließungsantrag der Linken zur GKV-Reform"):
            got = filt.filter_item(tax, wl, label).issue_areas or []
            self.assertEqual(got, [], "{0!r} should match nothing".format(label))
