#!/usr/bin/env python3
"""THE RIFF-RAFT-001 adversarial offline simulation (no hardware effects)."""
from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from ecology_router import Hold, digest, plan as ecology_plan
from riff_raft import compose, validate_topology

ROOT = Path(__file__).resolve().parents[1]
ECOLOGY = ROOT / "fixtures/ecology-router-001/world.json"
TOPOLOGY = ROOT / "fixtures/riff-raft-001/topology.json"


def setup():
    return (json.loads(ECOLOGY.read_text(encoding="utf-8")),
            json.loads(TOPOLOGY.read_text(encoding="utf-8")))


def rebind(world, topology):
    topology["ecology_world_sha256"] = digest(world)


def rows(result):
    return {r["load_id"]: r for r in result["routes"]}


def edge(topology, name):
    return next(x for x in topology["links"] if x["id"] == name)


class RiffRaftTests(unittest.TestCase):
    def test_name_and_inert_ledger_claims(self):
        w, t = setup()
        result = compose(w, t)
        self.assertEqual(result["name"], "The Riff-Raft")
        for key in ("physical_transfer_performed", "physical_safety_certified",
                    "habitation_permitted", "source_or_destination_admission",
                    "automatic_dispatch", "signed_relatte_crossing"):
            self.assertIs(result[key], False)
        self.assertEqual(result["ecology_world_sha256"], digest(w))
        self.assertEqual(result["topology_sha256"], digest(t))

    def test_fish_aeration_crosses_two_simulated_cable_links(self):
        w, t = setup()
        p = rows(compose(w, t))["fish-aeration"]
        self.assertEqual(p["decision"], "PROPOSE")
        self.assertEqual(p["route_link_ids"],
                         ["solar-to-shore-switch", "shore-switch-to-fish"])
        self.assertEqual(p["source_id"], "solar-bus")
        self.assertEqual(p["proposed_units"], 6000)
        self.assertEqual(p["unit"], "mWh")

    def test_thermal_transfer_uses_distinct_insulated_link(self):
        w, t = setup()
        p = rows(compose(w, t))["fish-water-heating"]
        self.assertEqual(p["decision"], "PROPOSE")
        self.assertEqual(p["route_link_ids"], ["thermal-to-fish"])
        self.assertEqual(p["unit"], "J")

    def test_local_orchard_signal_remains_information_not_power(self):
        w, t = setup()
        p = rows(compose(w, t))["orchard-wind-music"]
        self.assertEqual(p["decision"], "PROPOSE")
        self.assertEqual(p["source_id"], "tree-coil-detector")
        self.assertEqual(p["route_link_ids"], [])
        self.assertEqual(p["unit"], "events")

    def test_initial_background_compute_stays_held(self):
        w, t = setup()
        p = rows(compose(w, t))["ghot-background-render"]
        self.assertEqual(p["decision"], "HOLD")
        self.assertIn("UPSTREAM_HOLD", p["reasons"])

    def test_material_no_construction_without_source_and_transport_clearance(self):
        w, t = setup()
        self.assertEqual(rows(compose(w, t))["floating-habitat-structure"]["decision"], "HOLD")
        path = next(p for p in w["paths"] if p["id"] == "sorted-hdpe-to-platform")
        path["permit_ok"] = path["isolation_ok"] = True
        rebind(w, t)
        self.assertEqual(rows(compose(w, t))["floating-habitat-structure"]["decision"], "HOLD")
        edge(t, "river-to-habitat")["permit_ok"] = True
        edge(t, "river-to-habitat")["isolation_ok"] = True
        result = compose(w, t)
        p = rows(result)["floating-habitat-structure"]
        self.assertEqual(p["decision"], "PROPOSE")
        self.assertEqual(p["route_link_ids"],
                         ["material-yard-to-river", "river-to-habitat"])
        self.assertIs(result["physical_safety_certified"], False)

    def test_fish_is_unreachable_even_when_energy_is_sufficient(self):
        w, t = setup()
        w["sources"][0]["available_units"] = 20000
        next(x for x in w["loads"] if x["id"] == "ghot-background-render")["demand_units"] = 2000
        rebind(w, t)
        self.assertEqual(
            next(x for x in ecology_plan(w)["proposals"]
                 if x["load_id"] == "ghot-background-render")["decision"], "PROPOSE")
        edge(t, "shore-switch-to-fish")["status"] = "withdrawn"
        d = rows(compose(w, t))
        self.assertEqual(d["fish-aeration"]["decision"], "HOLD")
        self.assertEqual(d["ghot-background-render"]["decision"], "HOLD")
        self.assertIn("LIFE_SUPPORT_PATH_NOT_READY",
                      d["ghot-background-render"]["reasons"])

    def test_shared_cable_capacity_cannot_be_spent_twice(self):
        w, t = setup()
        next(x for x in w["loads"] if x["id"] == "ghot-background-render")["demand_units"] = 2000
        rebind(w, t)
        edge(t, "solar-to-shore-switch")["limit_units"] = 7000
        result = compose(w, t)
        d = rows(result)
        self.assertEqual(d["fish-aeration"]["decision"], "PROPOSE")
        self.assertEqual(d["ghot-background-render"]["decision"], "HOLD")
        self.assertEqual(result["remaining_link_units"]["solar-to-shore-switch"], 1000)

    def test_owner_grant_revocation_blocks_route(self):
        w, t = setup()
        edge(t, "solar-to-shore-switch")["owner_grants"] = ["energy-steward"]
        p = rows(compose(w, t))["fish-aeration"]
        self.assertEqual(p["decision"], "HOLD")
        self.assertIn("NO_ELIGIBLE_PHYSICAL_ROUTE", p["reasons"])

    def test_weather_withdrawal_blocks_floating_link(self):
        w, t = setup()
        edge(t, "shore-switch-to-fish")["weather_ok"] = False
        self.assertEqual(rows(compose(w, t))["fish-aeration"]["decision"], "HOLD")

    def test_undocumented_float_hull_does_not_claim_integrity(self):
        w, t = setup()
        next(p for p in t["places"] if p["id"] == "floating-fish-system")[
            "scenario_integrity_ok"] = False
        self.assertEqual(rows(compose(w, t))["fish-aeration"]["decision"], "HOLD")

    def test_wave_storm_routing_cannot_override_ecology_gate(self):
        w, t = setup()
        source = next(x for x in w["sources"] if x["id"] == "wave-converter")
        source["evidence"] = "synthetic-scenario"
        p = next(x for x in w["paths"] if x["id"] == "wave-to-fish")
        p["environment_ok"] = True
        rebind(w, t)
        upstream = next(x for x in ecology_plan(w)["proposals"] if x["load_id"] == "fish-aeration")
        self.assertEqual(upstream["source_id"], "wave-converter")
        self.assertEqual(rows(compose(w, t))["fish-aeration"]["decision"], "HOLD")

    def test_changes_to_ecology_world_refuse_stale_topology_pin(self):
        w, t = setup()
        w["step"] += 1
        with self.assertRaisesRegex(Hold, "topology pin stale"):
            compose(w, t)

    def test_mismatched_resource_carrier_refused(self):
        w, t = setup()
        edge(t, "solar-to-shore-switch")["carrier"] = "radio"
        with self.assertRaisesRegex(Hold, "resource unsupported"):
            validate_topology(t, w)

    def test_no_unverified_physical_readiness_claim(self):
        w, t = setup()
        edge(t, "thermal-to-fish")["scenario_only"] = False
        with self.assertRaisesRegex(Hold, "physical readiness"):
            compose(w, t)

    def test_invalid_node_and_duplicate_link_refused(self):
        w, t = setup()
        t["places"] = t["places"][:-1]  # river landing is now missing
        with self.assertRaisesRegex(Hold, "unknown or self-linked"):
            validate_topology(t, w)
        w, t = setup()
        t["links"].append(deepcopy(t["links"][0]))
        with self.assertRaisesRegex(Hold, "duplicate or invalid link"):
            validate_topology(t, w)

    def test_bad_capacity_and_wrong_units_refused(self):
        w, t = setup()
        edge(t, "thermal-to-fish")["limit_units"] = True
        with self.assertRaises(Hold):
            compose(w, t)
        w, t = setup()
        edge(t, "thermal-to-fish")["unit"] = "mWh"
        with self.assertRaises(Hold):
            compose(w, t)

    def test_failed_link_cannot_promote_upstream_held_material(self):
        w, t = setup()
        edge(t, "river-to-habitat")["permit_ok"] = True
        edge(t, "river-to-habitat")["isolation_ok"] = True
        p = rows(compose(w, t))["floating-habitat-structure"]
        self.assertEqual(p["decision"], "HOLD")
        self.assertIn("UPSTREAM_HOLD", p["reasons"])

    def test_determinism_and_no_state_mutation(self):
        w, t = setup()
        before_w, before_t = deepcopy(w), deepcopy(t)
        a = compose(w, t)
        b = compose(deepcopy(w), deepcopy(t))
        self.assertEqual(a, b)
        self.assertEqual(w, before_w)
        self.assertEqual(t, before_t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
