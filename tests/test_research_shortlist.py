"""Ranking the 5CA's zeros by who is worth asking."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import research_shortlist as rs


class AdjacencyTests(unittest.TestCase):
    def test_a_near_universal_area_predicts_nothing(self):
        """642 of 650 members have migration evidence, so having it says nothing.
        Without the discriminativeness factor the shortlist ranked members by
        who had the most migration debates -- 120 of them -- which is volume
        pretending to be signal.
        """
        # area 11 held by everyone; area 5 held by two, both of whom hold 8.
        weight = {}
        for i in range(20):
            weight[i] = {11: 50}
        weight[0] = {11: 50, 5: 4, 8: 2}
        weight[1] = {11: 50, 5: 4, 8: 2}
        adj = rs.adjacency(weight, 8)
        self.assertGreater(adj[5], adj[11],
                           "a rare co-occurring area must outrank a universal one")
        self.assertLess(adj[11], 0.05)

    def test_correlation_still_counts(self):
        """An area held by few members but never alongside the target should
        not outrank one that co-occurs."""
        weight = {0: {5: 4, 8: 2}, 1: {5: 4, 8: 2}, 2: {6: 4}, 3: {6: 4}}
        adj = rs.adjacency(weight, 8)
        self.assertGreater(adj[5], adj.get(6, 0))

    def test_target_area_is_excluded_from_its_own_adjacency(self):
        weight = {0: {8: 5, 5: 2}}
        self.assertNotIn(8, rs.adjacency(weight, 8))


class WeightTests(unittest.TestCase):
    def test_kind_weights_match_the_5ca_hierarchy(self):
        """A vote is a commitment; a written question is a gesture."""
        self.assertGreater(rs.KIND_WEIGHT["vote"], rs.KIND_WEIGHT["debate"])
        self.assertGreater(rs.KIND_WEIGHT["debate"], rs.KIND_WEIGHT["edm"])
        self.assertGreater(rs.KIND_WEIGHT["edm-signed"], rs.KIND_WEIGHT["pq"])
