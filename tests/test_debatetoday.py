"""The evening task's first question: was there a key debate today? Nothing here touches the network."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import debatetoday as dt, filter as filt  # noqa: E402

TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))


class FakeClient(object):
    """sectionsforday -> section names; sectiontrees -> a tree; debate -> items."""
    def __init__(self, trees, debates):
        self.trees, self.debates, self.fetched = trees, debates, []

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        if "sectionsforday" in url:
            house = url.split("house=")[1].split("&")[0]
            return list(self.trees.get(house, {}).keys())
        if "sectiontrees" in url:
            house = url.split("house=")[1].split("&")[0]; sec = url.split("section=")[1].split("&")[0]
            return self.trees[house][sec]
        ext = url.rstrip("/").split("/")[-1].replace(".json", "")
        self.fetched.append(ext)
        return self.debates.get(ext)


def node(title, ext):
    return {"Title": title, "ExternalId": ext, "SectionTreeItems": []}


def debate(names, date="2026-09-11"):
    items = [{"ItemType": "Contribution", "MemberId": i + 1, "AttributedTo": n, "Value": "<p>Words words words.</p>",
              "Timecode": "%sT10:%02d:00" % (date, i % 60)} for i, n in enumerate(names)]
    return {"Items": items}


class DebateTodayTests(unittest.TestCase):
    def test_titles_on_our_ground_are_kept_and_the_largest_is_the_key_debate(self):
        trees = {"Commons": {"1": [node("Terminally Ill Adults (End of Life) Bill", "TIA"),
                                   node("Business of the House", "BIZ"),
                                   node("Surrogacy Law and Legal Parenthood", "SUR")]},
                 "Lords": {"2": [node("Roads: Potholes", "POT")]}}
        client = FakeClient(trees, {"TIA": debate(["A%d" % i for i in range(40)]), "SUR": debate(["B%d" % i for i in range(8)])})
        cands = dt.candidates(client, "2026-09-11", TAX, WL, tracker_terms={"Terminally Ill Adults": 2})
        self.assertEqual(sorted(c[3] for c in cands), ["SUR", "TIA"])          # potholes and business are not fetched
        rows = dt.sized(client, "2026-09-11", cands)
        self.assertEqual(sorted(client.fetched), ["SUR", "TIA"])
        top = dt.verdict(rows)
        self.assertEqual((top["ext_id"], top["speakers"]), ("TIA", 40))
        text = dt.report(rows, "2026-09-11")
        self.assertIn("KEY DEBATE: Commons | Terminally Ill Adults (End of Life) Bill | TIA | 40 speakers | areas 2 | last heard 10:39", text)
        self.assertIn("tracker: Terminally Ill Adults", text)

    def test_a_small_debate_is_listed_but_is_not_a_key_debate(self):
        trees = {"Commons": {"1": [node("Surrogacy Law and Legal Parenthood", "SUR")]}, "Lords": {}}
        client = FakeClient(trees, {"SUR": debate(["B%d" % i for i in range(8)])})
        rows = dt.sized(client, "2026-09-11", dt.candidates(client, "2026-09-11", TAX, WL))
        self.assertIsNone(dt.verdict(rows))
        self.assertTrue(dt.report(rows, "2026-09-11").endswith("KEY DEBATE: none"))

    def test_a_quiet_day_says_so(self):
        client = FakeClient({"Commons": {"1": [node("Roads: Potholes", "POT")]}, "Lords": {}}, {})
        rows = dt.sized(client, "2026-09-11", dt.candidates(client, "2026-09-11", TAX, WL))
        self.assertEqual(rows, [])
        self.assertEqual(dt.report(rows, "2026-09-11"), "No debate on our ground on 2026-09-11.\nKEY DEBATE: none")

    def test_a_tracker_phrase_lends_its_issue_area(self):
        areas, reasons = dt.title_areas(TAX, WL, "Health Bill", {"Health Bill": 3})
        self.assertEqual(areas, [3]); self.assertEqual(reasons, ["tracker: Health Bill"])


if __name__ == "__main__":
    unittest.main()
