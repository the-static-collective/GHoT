#!/usr/bin/env python3
import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "rsc_composer", ROOT / "ghot" / "rsc_composer.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RscComposerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_path = ROOT / "experiments" / "rsc-live-crossing-001.seed.json"
        cls.seed = json.loads(cls.seed_path.read_text(encoding="utf-8"))

    def test_live_crossing_recommends_two_and_holds_one(self):
        packet = MODULE.compose(copy.deepcopy(self.seed))
        ids = [x["crossing_id"] for x in packet["recommended_next_experiments"]]
        self.assertEqual(
            ids,
            ["epistemic-capability-contract", "room-as-rsc-control-surface"],
        )
        self.assertEqual(
            packet["held_crossings"][0]["crossing_id"],
            "radio-as-distributed-epistemic-testbed",
        )
        self.assertTrue(packet["human_selection_required"])

    def test_hold_boundary_cannot_be_recommended(self):
        seed = copy.deepcopy(self.seed)
        crossing = seed["crossings"][0]
        crossing["boundary_checks"][0]["status"] = "hold"
        packet = MODULE.compose(seed)
        ids = [x["crossing_id"] for x in packet["recommended_next_experiments"]]
        self.assertNotIn("epistemic-capability-contract", ids)

    def test_unknown_artifact_reference_is_rejected(self):
        seed = copy.deepcopy(self.seed)
        seed["crossings"][0]["to"].append("ghost-artifact")
        with self.assertRaises(MODULE.SeedError):
            MODULE.compose(seed)


if __name__ == "__main__":
    unittest.main()
