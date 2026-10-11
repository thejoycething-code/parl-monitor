"""The 5CA sign-off shortlist (src/shortlist5ca.py, tools/country_5ca.py --shortlist,
the digest's top 5). Temporary stance files; no store, no network, no Slack."""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import shortlist5ca as sl  # noqa: E402

STANCE = c5.header("pl") + """
bill_directions:
  - key: "10/2110"
    direction: against
    status: draft
    why: "Registered cohabitation contracts."

divisions:
  - key: "pl-final-close"
    status: draft
    title: "głosowanie nad całością projektu."
    dated: "2026-09-17"
    chamber: "sejm"
    areas: [9]
    tier: 1
    watched: "10/2110"
    result: "Za 216, Przeciw 214, Abstain 3"
    lobbies: "Za: KO 150, PSL 20, PiS 2. Przeciw: PiS 180, PSL 8. Abstain: Lewica 3"
    vote_kind: final
    yea: -2
    why_yea: "Voted Za: for passing it, against CitizenGO's position."
    nay: 2
  - key: "pl-final-old"
    status: draft
    title: "głosowanie nad całością projektu."
    dated: "2024-02-22"
    chamber: "sejm"
    areas: [9]
    tier: 1
    watched: "10/2110"
    result: "Za 300, Przeciw 100"
    vote_kind: final
    yea: -2
    nay: 2
  - key: "pl-amend"
    status: needs_reading
    title: "poprawka 1"
    dated: "2026-09-17"
    chamber: "sejm"
    areas: [9]
    tier: 1
    watched: "10/2110"
    result: "Za 200, Przeciw 220"
    vote_kind: amendment
    read_first: "An amendment: read it."
  - key: "pl-proc"
    status: draft
    title: "wniosek o uzupełnienie porządku dziennego."
    dated: "2026-09-17"
    chamber: "sejm"
    areas: [9]
    tier: 1
    result: "Za 240, Przeciw 190"
    vote_kind: procedural
    placeable: false
    reason: "Procedural."
  - key: "pl-unanimous"
    status: draft
    title: "głosowanie nad całością projektu."
    dated: "2026-09-10"
    chamber: "sejm"
    areas: [1]
    tier: 1
    watched: "10/999"
    result: "Za 440, Przeciw 2"
    vote_kind: final
    yea: 2
    nay: -2
  - key: "pl-migration"
    status: draft
    title: "głosowanie nad całością projektu."
    dated: "2026-09-17"
    chamber: "sejm"
    areas: [11]
    tier: 1
    result: "Za 216, Przeciw 214"
    vote_kind: final
    yea: 2
    nay: -2
  - key: "pl-done"
    status: confirmed
    confirmed_by: "Christopher"
    confirmed_on: "2026-10-10"
    title: "głosowanie nad całością projektu."
    dated: "2026-09-17"
    chamber: "sejm"
    areas: [9]
    vote_kind: final
    yea: 2
    nay: -2
  - key: "XX/A/1@NR/87#106"
    status: draft
    title: "wniosek o odrzucenie projektu w pierwszym czytaniu."
    dated: "2025-03-01"
    chamber: "sejm"
    areas: [5]
    tier: 1
    result: "Za 100, Przeciw 300"
    vote_kind: reject
    yea: 2
    nay: -2
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.tmp.name, "config")
        self.docs = os.path.join(self.tmp.name, "docs")
        self.camps = os.path.join(self.tmp.name, "campaigns")
        self.briefs = os.path.join(self.tmp.name, "briefs")
        for d in (self.cfg, self.docs, self.camps, self.briefs):
            os.makedirs(d)
        self.stance = os.path.join(self.cfg, "pl_stance.yaml")
        with open(self.stance, "w", encoding="utf-8") as h:
            h.write(STANCE)

    def tearDown(self):
        self.tmp.cleanup()

    def rank(self):
        return sl.rank("pl", self.cfg, None, "2026-10-11", self.camps, self.briefs)

    def keys(self):
        return [it["key"] for it in self.rank()]


class ParseTests(unittest.TestCase):
    def test_tally_reads_the_lobby_labels(self):
        self.assertEqual(sl.tally({"result": "Za 216, Przeciw 214, Abstain 3"}, ("Za", "Przeciw")),
                         (216, 214))
        self.assertEqual(sl.tally({"result": "adopted; Ja / Oui 134, Nee / Non 0, Abstain 1"},
                                  ("Ja / Oui", "Nee / Non")), (134, 0))
        self.assertIsNone(sl.tally({"result": "abgelehnt"}, ("Dafür", "Dagegen")))

    def test_groups_and_splits(self):
        g = sl.groups("Za: KO 150, PSL 20, PiS 2. Przeciw: PiS 180, PSL 8. Abstain: Lewica 3",
                      ("Za", "Przeciw"))
        self.assertEqual(g["PiS"], {"yea": 2, "nay": 180, "abstain": 0})
        self.assertEqual(sl.splits(g), (["PSL", "PiS"], 10))
        derived = sl.groups("Dafür: FPÖ 57. Dagegen: ÖVP 51, SPÖ 41 (counts include members DERIVED "
                            "from their group's vote, X5)", ("Dafür", "Dagegen"))
        self.assertEqual(derived["SPÖ"]["nay"], 41)
        be = sl.groups("Ja / Oui: N-VA 22, Les Engagés 13. Nee / Non: VB 18. Abstain: PS 1",
                       ("Ja / Oui", "Nee / Non"))
        self.assertEqual(be["VB"]["nay"], 18)
        self.assertEqual(sl.groups(None, ("Za", "Przeciw")), {})
        self.assertEqual(sl.splits(sl.groups("Za: ? 3. Przeciw: ? 2", ("Za", "Przeciw"))), ([], 0))


class RankTests(Base):
    def test_decisive_close_split_recent_first_and_the_rest_sink(self):
        keys = self.keys()
        self.assertEqual(keys[0], "pl-final-close")
        self.assertNotIn("pl-done", keys)                       # confirmed: not waiting
        self.assertEqual(keys[-1], "pl-migration")              # collated-only area
        self.assertLess(keys.index("pl-final-close"), keys.index("pl-unanimous"))
        self.assertLess(keys.index("pl-final-old"), keys.index("pl-amend"))
        self.assertLess(keys.index("pl-amend"), keys.index("pl-proc"))
        top = self.rank()[0]
        joined = "; ".join(top["why"])
        for bit in ("a vote on the whole text", "the last such vote on its bill", "close: 216-214",
                    "split PSL, PiS (10 against their group)", "recent", "values proposed"):
            self.assertIn(bit, joined)
        old = next(it for it in self.rank() if it["key"] == "pl-final-old")
        self.assertNotIn("the last such vote on its bill", old["why"])
        un = next(it for it in self.rank() if it["key"] == "pl-unanimous")
        self.assertTrue(any(w.startswith("near-unanimous") for w in un["why"]))

    def test_campaign_outcome_and_brief_lift_a_vote(self):
        before = self.keys().index("XX/A/1@NR/87#106")
        os.makedirs(os.path.join(self.camps, "pl"))
        with open(os.path.join(self.camps, "pl", "pl-test.json"), "w", encoding="utf-8") as h:
            json.dump({"slug": "pl-test", "area": 1, "chamber": "sejm",
                       "outcomes": [{"key": "XX/A/1@NR/87#106"}]}, h)
        after = self.rank()
        it = next(x for x in after if x["key"] == "XX/A/1@NR/87#106")
        self.assertIn("an outcome of campaign pl-test", it["why"])
        self.assertLess([x["key"] for x in after].index(it["key"]), before)
        un = next(x for x in after if x["key"] == "pl-unanimous")
        self.assertIn("on campaign pl-test's ground", un["why"])
        with open(os.path.join(self.briefs, "pl.json"), "w", encoding="utf-8") as h:
            json.dump({"pl-brief": {"key": "10/2110", "ready": False}}, h)
        old = next(x for x in self.rank() if x["key"] == "pl-final-old")
        self.assertIn("feeds brief pl-brief (NOT READY until signed)", old["why"])

    def test_a_motion_is_its_own_text(self):
        e = {"title": "Motie: Motie van het lid X", "watched": "36416", "vote_kind": "final",
             "dated": "2026-01-01"}
        f = {"title": "Wetgeving: Voorstel van wet", "watched": "36416", "vote_kind": "final",
             "dated": "2025-01-01"}
        self.assertEqual(sl.last_decisive({"m": e, "w": f}), {"m", "w"})


class DocumentTests(Base):
    def test_shortlist_document_prints_commands_and_confirms_nothing(self):
        with open(self.stance, encoding="utf-8") as h:
            before = h.read()
        ranked = sl.write_shortlist("pl", self.cfg, self.docs, today="2026-10-11", log=lambda *a: None,
                                    campaigns_dir=self.camps, briefs_dir=self.briefs)
        self.assertEqual(len(ranked), 7)
        with open(self.stance, encoding="utf-8") as h:
            self.assertEqual(h.read(), before)                  # nothing confirmed
        with open(sl.shortlist_path("pl", self.docs), encoding="utf-8") as h:
            doc = h.read()
        self.assertIn("**This list confirms nothing.**", doc)
        self.assertIn("### 1. `pl-final-close`", doc)
        self.assertIn("`python3 tools/country_5ca.py --cc pl --confirm pl-final-close --by Christopher`",
                      doc)
        self.assertIn("--confirm 'XX/A/1@NR/87#106' --by Christopher", doc)   # quoted for the shell
        self.assertIn("first write `yea:`/`nay:`", doc)                         # needs reading
        self.assertIn("## By area", doc)
        self.assertIn("**Proposed:** Za -2, Przeciw +2", doc)
        self.assertNotIn("—", doc)

    def test_nothing_waiting_removes_a_stale_shortlist(self):
        path = sl.shortlist_path("pl", self.docs)
        with open(path, "w") as h:
            h.write("old")
        with open(self.stance, "w", encoding="utf-8") as h:
            h.write(c5.header("pl") + "\nbill_directions: []\n\ndivisions:\n")
        self.assertEqual(sl.write_shortlist("pl", self.cfg, self.docs, log=lambda *a: None), [])
        self.assertFalse(os.path.exists(path))


class DigestTests(Base):
    def test_digest_leads_with_the_top_five(self):
        text = c5.digest_text("2026-10-11", self.cfg, self.docs, countries=("pl",))
        lines = text.splitlines()
        head = lines.index(next(x for x in lines if x.startswith("*Poland*")))
        self.assertIn("sign these first", lines[head])
        self.assertTrue(lines[head + 1].startswith("  1. `pl-final-close`"))
        self.assertTrue(lines[head + 5].startswith("  5. "))
        self.assertIn("Waiting: 5 proposed, 1 procedural, 1 need reading, 1 confirmed", lines[head + 6])
        self.assertIn("docs/5ca-pl-shortlist.md", text)
        self.assertNotIn("watched bill", lines[head + 1])       # the quiet reasons stay out


if __name__ == "__main__":
    unittest.main()
