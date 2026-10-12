"""tools/review_sample.py: the blind sample for the Canada agreement test
(Christopher, 8 October 2026: "Option 1, private claude.ai page, members
only"). Pure-function tests on a synthetic population; no store."""

import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("review_sample", os.path.join(ROOT, "tools", "review_sample.py"))
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def pop(fed=60, provs=None):
    provs = provs if provs is not None else {"ab": 40, "sk": 10, "bc": 30, "mb": 3, "on": 25, "qc": 50, "nb": 8}
    out = {"federal": {}}
    for i in range(fed):
        pid = "commons:{0}".format(i)
        out["federal"][pid] = [{"member_id": pid, "jurisdiction": "Federal", "chamber": "House of Commons",
                                "member": "MP {0} (LPC)".format(i), "party": "LPC", "area": a, "area_name": "A{0}".format(a),
                                "column": "+", "evidence": ["e"], "based_on": "x"} for a in (1, 2)]
    for p in rs.SCORED_PROVS:
        out[p] = {}
        for i in range(provs.get(p, 0)):
            pid = "{0}:m{1}".format(p, i)
            out[p][pid] = [{"member_id": pid, "jurisdiction": rs.PROV_NAMES[p], "chamber": "Legislature",
                            "member": "M {0}".format(i), "party": "P", "area": 5, "area_name": "A5",
                            "column": "--", "evidence": ["e"], "based_on": "x"}]
    return out


class AllocateTests(unittest.TestCase):
    def test_floor_then_proportion_and_the_total_holds(self):
        take = rs.allocate({"ab": 40, "sk": 10, "bc": 30, "mb": 3, "on": 25, "qc": 50, "nb": 8})
        self.assertEqual(sum(take.values()), 30)
        self.assertEqual(take["mb"], 3)                    # all it has: short of the floor
        self.assertTrue(all(take[p] >= 4 for p in ("ab", "sk", "bc", "on", "qc", "nb")))
        self.assertGreater(take["qc"], take["sk"])         # the rest goes by size

    def test_never_more_than_a_province_has(self):
        take = rs.allocate({"ab": 2, "sk": 1, "bc": 0, "mb": 0, "on": 0, "qc": 0, "nb": 0})
        self.assertEqual(take, {"ab": 2, "sk": 1, "bc": 0, "mb": 0, "on": 0, "qc": 0, "nb": 0})


class DrawTests(unittest.TestCase):
    def test_items_never_carry_our_column(self):
        items, ours, _ = rs.draw(pop(), "R1")
        self.assertEqual(len(items), 50)                   # "run 50 tests a time"
        for it in items:
            self.assertNotIn("column", it)
            self.assertNotIn("evidence", it)
        self.assertEqual([o["id"] for o in ours], [i["id"] for i in items])
        self.assertTrue(all(o["column"] in ("++", "+", "0", "-", "--") for o in ours))

    def test_the_round_name_seeds_the_draw(self):
        a, _, _ = rs.draw(pop(), "R1")
        b, _, _ = rs.draw(pop(), "R1")
        c, _, _ = rs.draw(pop(), "R2")
        self.assertEqual(a, b)
        self.assertNotEqual([i["member"] for i in a], [i["member"] for i in c])

    def test_one_area_per_member_and_no_exempt_province(self):
        items, _, report = rs.draw(pop(), "R1")
        members = [i["member"] + i["jurisdiction"] for i in items]
        self.assertEqual(len(members), len(set(members)))
        self.assertFalse({"Newfoundland and Labrador", "Nova Scotia", "Prince Edward Island"}
                         & {i["jurisdiction"] for i in items})
        self.assertEqual(report["provinces"]["mb"]["short"], 1)
        self.assertEqual(report["federal_drawn"], 20)


    def test_a_later_round_draws_fresh_people(self):
        r1, _, _ = rs.draw(pop(), "R1")
        prior = {(i["jurisdiction"], i["member"]) for i in r1}
        r2, _, _ = rs.draw(pop(), "R2", prior=prior)
        self.assertFalse(prior & {(i["jurisdiction"], i["member"]) for i in r2})

    def test_earlier_rounds_are_read_from_disk_but_not_this_one(self):
        import json
        import tempfile
        d = tempfile.mkdtemp()
        for name, member in (("R1", "MP 1 (LPC)"), ("R2", "MP 2 (LPC)")):
            os.makedirs(os.path.join(d, name))
            with open(os.path.join(d, name, "items.json"), "w") as h:
                json.dump([{"jurisdiction": "Federal", "member": member}], h)
        self.assertEqual(rs.earlier_rounds("R2", d), {("Federal", "MP 1 (LPC)")})


if __name__ == "__main__":
    unittest.main()
