#!/usr/bin/env python3
"""ECOLOGY ROUTER 001: deterministic adversarial dry-run, no actuators."""
from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from ecology_router import Hold, cold_replay, digest, plan, validate

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/ecology-router-001/world.json"


def world():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def decisions(result):
    return {x["load_id"]: x for x in result["proposals"]}


class RoutingTests(unittest.TestCase):
    def test_survival_first_and_optional_compute_held(self):
        p = plan(world())
        d = decisions(p)
        self.assertEqual(d["fish-aeration"]["decision"], "PROPOSE")
        self.assertEqual(d["fish-aeration"]["source_id"], "solar-bus")
        self.assertEqual(d["ghot-background-render"]["decision"], "HOLD")
        self.assertEqual(p["remaining_supply"]["solar-bus"], 3000)
        self.assertFalse(p["physical_effects"])
        self.assertFalse(p["automatic_dispatch"])
        self.assertFalse(p["owner_admission"])
        self.assertFalse(p["signed_crossing"])

    def test_heat_can_be_proposed_without_electric_conversion(self):
        d = decisions(plan(world()))
        self.assertEqual(d["fish-water-heating"]["source_id"], "insulated-heat-bank")
        self.assertEqual(d["fish-water-heating"]["resource"], "heat")
        self.assertEqual(d["fish-water-heating"]["unit"], "J")
        self.assertEqual(d["ghot-background-render"]["decision"], "HOLD")

    def test_tree_signal_funds_only_information(self):
        d = decisions(plan(world()))
        self.assertEqual(d["orchard-wind-music"]["source_id"], "tree-coil-detector")
        self.assertEqual(d["orchard-wind-music"]["unit"], "events")
        self.assertNotEqual(d["ghot-background-render"]["source_id"], "tree-coil-detector")

    def test_garbage_housing_cannot_skip_material_clearance(self):
        d = decisions(plan(world()))
        self.assertEqual(d["floating-habitat-structure"]["decision"], "HOLD")
        self.assertIn("PERMIT_UNRESOLVED", d["floating-habitat-structure"]["reasons"])
        self.assertIn("ISOLATION_NOT_PROVEN",
                      d["floating-habitat-structure"]["reasons"])

    def test_unverified_wave_energy_not_treated_as_electric_supply(self):
        w = world()
        w["sources"][0]["available_units"] = w["sources"][0]["reserved_units"]
        d = decisions(plan(w))
        self.assertEqual(d["fish-aeration"]["decision"], "HOLD")
        self.assertIn("UNVERIFIED_RESOURCE", d["fish-aeration"]["reasons"])
        self.assertIn("LIFE_SUPPORT_UNFUNDED",
                      d["ghot-background-render"]["reasons"])

    def test_forged_soil_galvanic_voltage_cannot_fund_compute(self):
        w = world()
        w["sources"][0]["available_units"] = 1000
        d = decisions(plan(w))
        self.assertIn("UNVERIFIED_RESOURCE", d["ghot-background-render"]["reasons"])
        self.assertEqual(d["ghot-background-render"]["decision"], "HOLD")

    def test_critical_unfunded_blocks_optional_same_resource(self):
        w = world()
        w["sources"][0]["available_units"] = 6500  # 5500 available, below fish demand
        w["loads"][1]["demand_units"] = 1000
        d = decisions(plan(w))
        self.assertEqual(d["fish-aeration"]["decision"], "HOLD")
        self.assertEqual(d["ghot-background-render"]["decision"], "HOLD")
        self.assertIn("LIFE_SUPPORT_UNFUNDED", d["ghot-background-render"]["reasons"])

    def test_other_rejected_paths_do_not_poison_safe_option(self):
        w = world()
        # Multiple rejected wave/soil paths exist alongside the safe solar link.
        self.assertEqual(decisions(plan(w))["fish-aeration"]["source_id"], "solar-bus")

    def test_stale_solar_offer_refused(self):
        w = world()
        w["sources"][0]["fresh_until_step"] = 0
        d = decisions(plan(w))
        self.assertEqual(d["fish-aeration"]["decision"], "HOLD")
        self.assertIn("STALE_SOURCE", d["fish-aeration"]["reasons"])

    def test_sealed_thermal_exchanger_is_required(self):
        w = world()
        for p in w["paths"]:
            if p["id"] == "heatbank-to-fish":
                p["isolation_ok"] = False
        d = decisions(plan(w))
        self.assertEqual(d["fish-water-heating"]["decision"], "HOLD")
        self.assertIn("ISOLATION_NOT_PROVEN", d["fish-water-heating"]["reasons"])

    def test_wave_storm_and_clearance_flags_hard_gate(self):
        w = world()
        wave = next(s for s in w["sources"] if s["id"] == "wave-converter")
        wave["evidence"] = "synthetic-scenario"
        w["sources"][0]["available_units"] = w["sources"][0]["reserved_units"]
        d = decisions(plan(w))
        self.assertEqual(d["fish-aeration"]["decision"], "HOLD")
        self.assertIn("ENVIRONMENT_UNSAFE", d["fish-aeration"]["reasons"])

    def test_wave_candidate_can_enter_only_as_simulation(self):
        w = world()
        wave = next(s for s in w["sources"] if s["id"] == "wave-converter")
        wave["evidence"] = "synthetic-scenario"
        for p in w["paths"]:
            if p["from"] == "wave-converter":
                p["environment_ok"] = True
        d = decisions(plan(w))
        self.assertEqual(d["fish-aeration"]["source_id"], "wave-converter")
        self.assertFalse(plan(w)["physical_effects"])

    def test_malformed_units_and_foreign_conversion_refused(self):
        w = world()
        w["loads"][0]["unit"] = "joules"
        with self.assertRaises(Hold):
            validate(w)
        w = world()
        next(p for p in w["paths"] if p["id"] == "heatbank-to-fish")["resource"] = "electricity"
        d = decisions(plan(w))
        self.assertEqual(d["fish-water-heating"]["decision"], "HOLD")
        self.assertIn("RESOURCE_OR_UNIT_MISMATCH", d["fish-water-heating"]["reasons"])

    def test_no_fake_signed_attestation_or_autonomy(self):
        w = world()
        w["mode"] = "physical-executed"
        with self.assertRaises(Hold):
            validate(w)
        w = world()
        w["paths"][0]["actuator_command"] = "OPEN_VALVE"
        with self.assertRaises(Hold):
            validate(w)
        w = world()
        w["sources"][0]["evidence"] = "independently-verified"
        with self.assertRaises(Hold):
            validate(w)

    def test_no_boolean_capacity_or_negative_reserve(self):
        w = world()
        w["sources"][0]["available_units"] = True
        with self.assertRaises(Hold):
            validate(w)
        w = world()
        w["sources"][0]["reserved_units"] = -5
        with self.assertRaises(Hold):
            validate(w)

    def test_missing_owner_selection_refused(self):
        w = world()
        w["loads"][0]["selected_by_owner"] = False
        d = decisions(plan(w))
        self.assertEqual(d["fish-aeration"]["decision"], "HOLD")
        self.assertIn("NO_EXPLICIT_OWNER_SELECTION", d["fish-aeration"]["reasons"])

    def test_cold_replay_is_deterministic_and_immutable(self):
        w = world()
        before = deepcopy(w)
        self.assertTrue(cold_replay(w))
        self.assertEqual(before, w)
        self.assertEqual(digest(plan(w)), digest(plan(deepcopy(w))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
