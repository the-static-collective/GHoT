#!/usr/bin/env python3
"""Hostile rehearsal for MAKE GROUND x THE RIFF-RAFT.

Run: python3 ghot/riff_raft_terraformer_sim.py
No network access, machine actuation, ecological installation or signatures.
"""
from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from ecology_router import Hold, digest
from riff_raft import compose
from riff_raft_terraformer import (
    STAGES, balances, bootstrap, next_door,
    simulate_one, validate_state,
)

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def world_and_plan():
    world = load("fixtures/ecology-router-001/world.json")
    topology = load("fixtures/riff-raft-001/topology.json")
    return world, topology, compose(world, topology)


def field_plan():
    _, _, plan = world_and_plan()
    return bootstrap(plan, load("fixtures/riff-raft-002/field.json")), plan


def req(field, cue, turn_id=None):
    return {
        "schema": "ghot.riff-raft-terraform-cue/v0",
        "turn_id": turn_id or ("TURN-" + cue),
        "cue": cue, "operator_id": field["owner_id"],
        "selection": "explicit", "authority_request": "none",
        "admission_request": "none",
    }


def advance(field, plan, count):
    current = field
    for cue in STAGES[:count]:
        current = simulate_one(current, plan, req(current, cue))["field"]
    return current


class TerraformerTests(unittest.TestCase):
    def test_initial_door_is_one_proposal_not_a_command(self):
        field, plan = field_plan()
        door = next_door(field, plan)
        self.assertEqual(door["stage"], "READ_FIELD")
        self.assertEqual(door["decision"], "PROPOSE")
        self.assertTrue(door["requires_new_operator_selection"])
        self.assertFalse(door["physical_actuation"])
        self.assertFalse(door["independent_field_witness"])

    def test_all_nine_cues_operator_selected_one_at_a_time(self):
        field, plan = field_plan()
        initial = deepcopy(field)
        for ix, cue in enumerate(STAGES):
            self.assertEqual(next_door(field, plan)["stage"], cue)
            outcome = simulate_one(field, plan, req(field, cue))
            self.assertFalse(outcome["automatic_next"])
            self.assertFalse(outcome["physical_field_effect"])
            field = outcome["field"]
            self.assertEqual(field["completed"], list(STAGES[:ix+1]))
            self.assertEqual(field["receipts"][-1]["cue"], cue)
        self.assertEqual(next_door(field, plan)["decision"], "COMPLETE_REHEARSAL_ONLY")
        self.assertFalse(next_door(field, plan)["fertility_delta_verified"])
        self.assertEqual(initial["completed"], [])
        self.assertEqual(len(field["receipts"]), 9)
        self.assertTrue(field["flags"]["adjacent_candidate"])

    def test_rain_moves_into_bank_and_runoff_with_no_water_creation(self):
        field, plan = field_plan()
        baseline = balances(field["stocks"])
        field = advance(field, plan, 3)
        self.assertEqual(field["stocks"]["rain_ml"], 0)
        self.assertEqual(field["stocks"]["banked_ml"], 900)
        self.assertEqual(field["stocks"]["runoff_ml"], 300)
        self.assertEqual(balances(field["stocks"]), baseline)

    def test_soil_amendment_is_a_transfer_not_free_mass(self):
        field, plan = field_plan()
        baseline = balances(field["stocks"])
        field = advance(field, plan, 5)
        self.assertEqual(field["stocks"]["banked_ml"], 500)
        self.assertEqual(field["stocks"]["soil_water_ml"], 400)
        self.assertEqual(field["stocks"]["soil_amendment_g"], 300)
        self.assertEqual(balances(field["stocks"]), baseline)

    def test_biomass_compost_and_mulch_follow_conservative_split(self):
        field, plan = field_plan()
        baseline = balances(field["stocks"])
        field = advance(field, plan, 7)
        self.assertEqual(field["stocks"]["imported_biomass_g"], 0)
        self.assertEqual(field["stocks"]["mulch_g"], 240)
        self.assertEqual(field["stocks"]["compost_g"], 220)
        self.assertEqual(field["stocks"]["biomass_loss_g"], 40)
        self.assertEqual(balances(field["stocks"]), baseline)

    def test_only_a_seeding_attempt_not_proven_plant_establishment(self):
        field, plan = field_plan()
        field = advance(field, plan, 6)
        self.assertTrue(field["flags"]["seeds_sown_as_attempt"])
        self.assertEqual(field["stocks"]["native_seeds"], 3)
        self.assertEqual(field["stocks"]["seeds_sown"], 5)
        self.assertNotIn("established_vegetation", field["flags"])

    def test_each_step_exposes_door_without_executing_it(self):
        field, plan = field_plan()
        old = deepcopy(field)
        result = simulate_one(field, plan, req(field, "READ_FIELD"))
        self.assertEqual(result["next_door"]["stage"], "LAY_BONES")
        self.assertEqual(len(result["field"]["completed"]), 1)
        self.assertEqual(field, old)

    def test_early_late_and_hidden_pipeline_refused(self):
        field, plan = field_plan()
        with self.assertRaisesRegex(Hold, "cue order"):
            simulate_one(field, plan, req(field, "CATCH_WATER"))
        bad = dict(req(field, "READ_FIELD"), next_turn="LAY_BONES")
        with self.assertRaisesRegex(Hold, "fields changed"):
            simulate_one(field, plan, bad)

    def test_consumed_turn_no_retry(self):
        field, plan = field_plan()
        result = simulate_one(field, plan, req(field, "READ_FIELD"))
        with self.assertRaisesRegex(Hold, "already consumed"):
            simulate_one(result["field"], plan, req(result["field"], "LAY_BONES", "TURN-READ_FIELD"))

    def test_missing_steward_consent_fails_closed(self):
        field, plan = field_plan()
        field["permissions"]["land_steward_consented"] = False
        field["state_sha256"] = digest({k: v for k, v in field.items() if k != "state_sha256"})
        self.assertEqual(next_door(field, plan)["decision"], "HOLD")
        with self.assertRaisesRegex(Hold, "cue is HOLD"):
            simulate_one(field, plan, req(field, "READ_FIELD"))

    def test_erosion_review_required_before_moving_brush(self):
        field, plan = field_plan()
        field = advance(field, plan, 1)
        field["permissions"]["erosion_plan_reviewed"] = False
        field["state_sha256"] = digest({k: v for k, v in field.items() if k != "state_sha256"})
        self.assertEqual(next_door(field, plan)["decision"], "HOLD")

    def test_water_path_review_required(self):
        field, plan = field_plan()
        field = advance(field, plan, 2)
        field["permissions"]["water_path_reviewed"] = False
        field["state_sha256"] = digest({k: v for k, v in field.items() if k != "state_sha256"})
        self.assertIn("WATER_PATH_REVIEW_MISSING", next_door(field, plan)["reasons"])

    def test_bio_contamination_and_native_origin_hold(self):
        field, plan = field_plan()
        field = advance(field, plan, 5)
        field["permissions"]["native_seed_origin_checked"] = False
        field["permissions"]["biological_contamination_absent"] = False
        field["state_sha256"] = digest({k: v for k, v in field.items() if k != "state_sha256"})
        self.assertIn("NATIVE_ORIGIN_REVIEW_MISSING", next_door(field, plan)["reasons"])
        self.assertIn("CONTAMINATION_SCREEN_MISSING", next_door(field, plan)["reasons"])

    def test_missing_water_hold_no_infinite_growth(self):
        field, plan = field_plan()
        field = advance(field, plan, 2)
        field["stocks"]["rain_ml"] = 0
        field["initial_balances"]["water_ml"] = 0
        field["state_sha256"] = digest({k: v for k, v in field.items() if k != "state_sha256"})
        self.assertIn("INPUT_NOT_AVAILABLE:rain_ml", next_door(field, plan)["reasons"])

    def test_unearned_physical_witness_never_minted(self):
        field, plan = field_plan()
        field = advance(field, plan, 8)
        self.assertEqual(field["completed"][-1], "WITNESS_DELTA")
        self.assertTrue(all(r["independent_field_witness"] is False
                            for r in field["receipts"]))
        self.assertFalse(field["flags"]["adjacent_candidate"])

    def test_fake_field_evidence_in_state_refused(self):
        field, plan = field_plan()
        field["flags"]["ecological_growth_verified"] = True
        field["state_sha256"] = digest({k: v for k, v in field.items() if k != "state_sha256"})
        with self.assertRaisesRegex(Hold, "field flags malformed"):
            validate_state(field, plan)

    def test_tampered_receipt_detected_even_if_state_resealed(self):
        field, plan = field_plan()
        field = advance(field, plan, 1)
        field["receipts"][0]["independent_field_witness"] = True
        field["state_sha256"] = digest({k: v for k, v in field.items() if k != "state_sha256"})
        with self.assertRaises(Hold):
            validate_state(field, plan)

    def test_plan_drift_fails_without_silent_reinterpretation(self):
        field, plan = field_plan()
        other = deepcopy(plan)
        other["routes"][0]["decision"] = "HOLD"
        with self.assertRaisesRegex(Hold, "upstream GHoT plan changed"):
            validate_state(field, other)

    def test_orchard_information_route_withdrawal_fails_closed(self):
        field, plan = field_plan()
        other = deepcopy(plan)
        for row in other["routes"]:
            if row["load_id"] == "orchard-wind-music":
                row["decision"] = "HOLD"
        with self.assertRaisesRegex(Hold, "orchard information route unavailable"):
            validate_state(field, other)

    def test_external_operator_and_admission_requests_refused(self):
        field, plan = field_plan()
        for name, value in (
            ("operator_id", "remote-agent"),
            ("selection", "automatic"),
            ("authority_request", "grant"),
            ("admission_request", "ADMIT"),
        ):
            hostile = req(field, "READ_FIELD")
            hostile[name] = value
            with self.assertRaisesRegex(Hold, "cannot impersonate"):
                simulate_one(field, plan, hostile)

    def test_beyond_final_cue_refused(self):
        field, plan = field_plan()
        field = advance(field, plan, 9)
        with self.assertRaisesRegex(Hold, "already complete"):
            simulate_one(field, plan, req(field, "READ_FIELD", "TURN-EXTRA"))

    def test_replay_determinism_one_cue(self):
        field, plan = field_plan()
        r = req(field, "READ_FIELD")
        a, b = simulate_one(field, plan, r), simulate_one(deepcopy(field), deepcopy(plan), r)
        self.assertEqual(a, b)
        self.assertEqual(a["receipt"]["balances_before"], a["receipt"]["balances_after"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
