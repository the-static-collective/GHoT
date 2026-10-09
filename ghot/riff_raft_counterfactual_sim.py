#!/usr/bin/env python3
"""Fail-closed tests for observed-result-driven Riff-Raft counterfactual proposer."""
from __future__ import annotations
import unittest
from riff_raft_counterfactual import (SOURCE_CROSSING,SOURCE_RECEIPT,SOURCE_PACKET,
    REPEATERS,LAMPS,POLICY,CounterfactualHold,select_after_observation)


class CounterfactualTests(unittest.TestCase):
    def test_only_existing_repeater_positions_allowed(self):
        self.assertEqual(REPEATERS,(-28,-13,2,17,32))
        self.assertEqual(len(LAMPS),9)
    def test_observed_counts_produce_bounded_new_interventions(self):
        a_observed=sum(x < -13 for x in LAMPS)
        b_observed=sum(x < 17 for x in LAMPS)
        self.assertEqual((a_observed,b_observed),(3,6))
        a_counter=a_observed+POLICY["A"]["delta"]
        b_counter=b_observed+POLICY["B"]["delta"]
        self.assertEqual((a_counter,b_counter),(5,2))
        self.assertEqual([x for x in REPEATERS if sum(z<x for z in LAMPS)==a_counter],[2])
        self.assertEqual([x for x in REPEATERS if sum(z<x for z in LAMPS)==b_counter],[-28])
    def test_no_unsigned_shortcut(self):
        for x in ({}, {"crossing":{},"receipt":{},"packet_json":"{}",
                       "world_evidence":{}},None):
            with self.assertRaises((KeyError,TypeError,ValueError)):
                select_after_observation(x)
    def test_explicit_source_004_anchor_not_a_wildcard(self):
        self.assertTrue(SOURCE_CROSSING.startswith("relatte-crossing-v0:"))
        self.assertTrue(SOURCE_RECEIPT.startswith("relatte-receipt-v0:"))
        self.assertEqual(len(SOURCE_PACKET),64)
    def test_future_or_external_authority_is_never_auto_granted(self):
        self.assertEqual(set(POLICY),{"A","B"})
        self.assertEqual(POLICY["A"]["name"],"shift-downstream-by-two-stages")
        self.assertEqual(POLICY["B"]["name"],"shift-upstream-by-four-stages")


if __name__=="__main__":
    unittest.main(verbosity=2)
