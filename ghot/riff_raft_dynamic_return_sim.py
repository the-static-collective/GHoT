#!/usr/bin/env python3
from __future__ import annotations
import json
import unittest
from copy import deepcopy

from riff_raft_quest import propose,QuestHold
from riff_raft_dynamic_return import receive,ReturnHold,BUNDLE,SCHEMA,EXPECTED


class DynamicReturnTests(unittest.TestCase):
    def test_distinct_quest_outcomes_are_not_conflict(self):
        a=propose("A","381654729","rain-retention")
        b=propose("B","918273645","biomass-return")
        self.assertEqual(sum(a["expected_lit_during_fault"]),3)
        self.assertEqual(sum(b["expected_lit_during_fault"]),6)
        self.assertNotEqual(a["quest_sha256"],b["quest_sha256"])
        self.assertEqual(EXPECTED["final"],[True]*9)
    def test_untrusted_abstract_summary_is_not_received(self):
        summary={"schema":BUNDLE,"packet_json":json.dumps({"schema":SCHEMA,
            "comparison":{"distinct_quest_outcomes_verified":True}}),
            "crossing":{"crossing_id":"fake"},
            "receipt":{"kind":"R3_HOLD"},"world_evidence":{"A":{},"B":{}}}
        with self.assertRaisesRegex(ReturnHold,"CROSSING_SIGNATURE_INVALID"):
            receive(summary)
    def test_missing_or_extra_fields_hold(self):
        with self.assertRaises(ReturnHold):receive({})
        with self.assertRaises(ReturnHold):receive(None)
        with self.assertRaises(ReturnHold):receive({"schema":BUNDLE,"inject_shell":True})
    def test_quest_is_not_admission(self):
        q=propose("A","381654729","rain-retention")
        self.assertFalse(q["owner_admission"])
        self.assertFalse(q["game_execution_observed"])
        self.assertFalse(q["actual_soil_change_verified"])


if __name__=="__main__":
    unittest.main(verbosity=2)
