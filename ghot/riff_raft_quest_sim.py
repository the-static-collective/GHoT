#!/usr/bin/env python3
from __future__ import annotations
import copy
import unittest

from riff_raft_quest import QuestHold, propose, validate, STAGES


class QuestTests(unittest.TestCase):
    def test_two_distinct_quest_selections(self):
        a=validate(propose("A","381654729","rain-retention"))
        b=validate(propose("B","918273645","biomass-return"))
        self.assertEqual(a["fault_repeater_position"],{"x":-13,"y":66,"z":46})
        self.assertEqual(b["fault_repeater_position"],{"x":17,"y":66,"z":46})
        self.assertEqual(sum(a["expected_lit_during_fault"]),3)
        self.assertEqual(sum(b["expected_lit_during_fault"]),6)
        self.assertNotEqual(a["quest_sha256"],b["quest_sha256"])
        self.assertEqual(a["station_labels"],list(STAGES))
        self.assertFalse(a["game_execution_observed"])
        self.assertFalse(b["owner_admission"])
    def test_deterministic(self):
        self.assertEqual(propose("A","381654729","rain-retention"),
                         propose("A","381654729","rain-retention"))
    def test_priority_cannot_be_invented(self):
        with self.assertRaisesRegex(QuestHold,"PRIORITY_NOT_ALLOWED"):
            propose("A","381654729","secret")
    def test_seed_or_world_mismatch(self):
        with self.assertRaises(QuestHold):propose("A","918273645","rain-retention")
        with self.assertRaises(QuestHold):propose("B","381654729","biomass-return")
        with self.assertRaises(QuestHold):propose("C","381654729","rain-retention")
    def test_wrong_scenario_for_seed(self):
        with self.assertRaises(QuestHold):propose("A","381654729","biomass-return")
    def test_held_quest_cannot_assert_observation(self):
        q=propose("A","381654729","rain-retention")
        q["game_execution_observed"]=True
        with self.assertRaisesRegex(QuestHold,"QUEST_DIFFERENT"):
            validate(q)
    def test_authority_cannot_expand(self):
        q=propose("B","918273645","biomass-return")
        q["owner_admission"]=True
        with self.assertRaises(QuestHold):validate(q)
    def test_position_tamper_rejected(self):
        q=propose("B","918273645","biomass-return")
        q["fault_repeater_position"]["x"]=-13
        with self.assertRaises(QuestHold):validate(q)
    def test_fields_cannot_expand(self):
        q=propose("A","381654729","rain-retention")
        q["execute_immediately"]=True
        with self.assertRaisesRegex(QuestHold,"QUEST_FIELDS_CHANGED"):validate(q)
    def test_strict_digest(self):
        q=propose("A","381654729","rain-retention")
        q["quest_sha256"]="0"*64
        with self.assertRaises(QuestHold):validate(q)


if __name__=="__main__":
    unittest.main(verbosity=2)
