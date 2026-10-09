#!/usr/bin/env python3
from __future__ import annotations
import json
import unittest
from riff_raft_counterfactual_return import receive,ReturnHold,BUNDLE,SCHEMA
from riff_raft_counterfactual import SOURCE_CROSSING,SOURCE_RECEIPT,SOURCE_PACKET

class ReceiverTests(unittest.TestCase):
    def test_signed_ancestor_is_mandatory(self):
        with self.assertRaises(ReturnHold):receive({})
        with self.assertRaises(ReturnHold):receive(None)
    def test_unsigned_ancestor_cannot_be_promoted(self):
        b={"schema":BUNDLE,"packet_json":json.dumps({"schema":SCHEMA}),
           "crossing":{},"receipt":{},"world_evidence":{"A":{},"B":{}},
           "ancestral_source_004":{}}
        with self.assertRaises(ReturnHold):receive(b)
    def test_source_crossing_is_pinned_to_actual_004(self):
        self.assertTrue(SOURCE_CROSSING.startswith("relatte-crossing-v0:"))
        self.assertTrue(SOURCE_RECEIPT.startswith("relatte-receipt-v0:"))
        self.assertEqual(len(SOURCE_PACKET),64)
    def test_source_ancestor_not_bypassable_by_relabeling(self):
        b={"schema":BUNDLE,"packet_json":json.dumps({"schema":SCHEMA}),
           "crossing":{},"receipt":{},"world_evidence":{"A":{},"B":{}},
           "ancestral_source_004":{
              "crossing":{"crossing_id":"spoof"},
              "receipt":{"receipt_id":"spoof"},
              "packet_json":"{}"}}
        with self.assertRaisesRegex(ReturnHold,"ANCESTRAL_SOURCE_004_NOT_BOUND"):
            receive(b)
if __name__=="__main__":unittest.main(verbosity=2)
