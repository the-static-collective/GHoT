"""Contract tests for the proposal-only Commons Machine 001."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ghot"))
from commons_machine import persist_simulation, simulate, validate  # noqa: E402

FIXTURE = ROOT / "experiments" / "commons-machine-001.json"


class CommonsMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_one_lever_branches_without_actuation(self) -> None:
        output = simulate(self.scenario)
        decisions = {entry["edge_id"]: entry for entry in output["decisions"]}
        self.assertEqual(decisions["flush-action"]["decision"], "YES")
        self.assertEqual(decisions["wastewater-to-coil-crossing"]["decision"], "REFUSE")
        self.assertEqual(decisions["cooling-idea"]["decision"], "HOLD")
        self.assertEqual(decisions["compute-offer-review"]["decision"], "HOLD")
        self.assertIn("no-unsupervised-cooling", output["unvisited_edges"])
        self.assertTrue(output["no_tasks_executed"])
        self.assertTrue(output["no_dispatch"])
        self.assertTrue(output["no_physical_observations_made"])
        self.assertTrue(all(item["observed_physical_result"] is None for item in output["decisions"]))
        self.assertTrue(all(item["executed"] is False for item in output["decisions"]))

    def test_repeatable_without_mutating_source(self) -> None:
        saved = copy.deepcopy(self.scenario)
        a = simulate(self.scenario)
        b = simulate(self.scenario)
        self.assertEqual(a, b)
        self.assertEqual(self.scenario, saved)

    def test_no_unsourced_live_event_in_simulator(self) -> None:
        scenario = copy.deepcopy(self.scenario)
        scenario["source_event"]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "synthetic"):
            simulate(scenario)

    def test_explicit_media_barrier(self) -> None:
        scenario = copy.deepcopy(self.scenario)
        nodes = {item["id"]: item for item in scenario["nodes"]}
        nodes["coil-coolant"]["medium"] = "coolant"
        result = simulate(scenario)
        decision = next(x for x in result["decisions"] if x["edge_id"] == "wastewater-to-coil-crossing")
        self.assertEqual(decision["decision"], "REFUSE")

    def test_cycle_blocked(self) -> None:
        scenario = copy.deepcopy(self.scenario)
        scenario["edges"].append({"id": "cycle", "from": "audit", "to": "lever", "relation": "inference"})
        with self.assertRaisesRegex(ValueError, "Cycles"):
            validate(scenario)

    def test_duplicate_nodes_blocked(self) -> None:
        scenario = copy.deepcopy(self.scenario)
        scenario["nodes"].append(copy.deepcopy(scenario["nodes"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate(scenario)

    def test_fluid_transfer_requires_quality(self) -> None:
        scenario = copy.deepcopy(self.scenario)
        next(x for x in scenario["nodes"] if x["id"] == "coil-coolant").pop("medium")
        with self.assertRaisesRegex(ValueError, "medium"):
            validate(scenario)

    def test_receipt_is_explicitly_unsigned_and_append_only(self) -> None:
        result = simulate(self.scenario)
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            first = persist_simulation(result, home)
            second = persist_simulation(result, home)
            self.assertNotEqual(first, second)
            a = json.loads(first.read_text(encoding="utf-8"))
            self.assertIsNone(a["signature"])
            self.assertEqual(a["authority"], "none")
            self.assertEqual(a["simulation_sha256"], result["simulation_sha256"])


if __name__ == "__main__":
    unittest.main()
