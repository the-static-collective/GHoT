#!/usr/bin/env python3
"""MINERAL FIELD 001 integration proof."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import reference_node
from mineral_registry import (
    EXECUTABLE_CAPABILITIES,
    FRACTAL_CAPABILITY,
    MINERAL_REGISTRY,
    OPTIMIZATION_CAPABILITY,
    PARAMETER_SWEEP_CAPABILITY,
    PROCEDURAL_WORLD_CAPABILITY,
    REGISTRY_CAPABILITY,
    execute_mineral_capability,
    registry,
)
from power_field import capability_power_class


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "ghot"

        reference_node.ROOT = root
        reference_node.RECORDS = root / "records"
        reference_node.NODE_ID_FILE = root / "node-id"

        catalog = registry()
        assert catalog["kind"] == "ghot.mineral-registry"
        assert catalog["mineral_count"] == 11

        ids = {item["mineral_id"] for item in catalog["minerals"]}
        expected = {
            "math.fractal.tile/v0",
            "math.topology.mapping-torus/v0",
            "math.projection.nd/v0",
            "science.numeric.simulation/v0",
            "render.raytrace.tile/v0",
            "render.blender.tile/v0",
            "science.protein.search/v0",
            "math.optimization.landscape/v0",
            "world.procedural.chunk/v0",
            "ai.asset.batch/v0",
            "science.parameter-sweep/v0",
        }
        assert ids == expected

        body = reference_node.body()
        offered = {
            item["capability"]
            for item in body["offers"]
            if item.get("available") is True
        }

        assert REGISTRY_CAPABILITY in offered
        for capability in EXECUTABLE_CAPABILITIES:
            assert capability in offered
            assert capability_power_class(capability) == "heavy"
        assert capability_power_class(REGISTRY_CAPABILITY) == "light"

        held_capabilities = {
            item["capability"]
            for item in MINERAL_REGISTRY
            if str(item["status"]).startswith("HOLD")
        }
        assert held_capabilities.isdisjoint(offered)

        payloads = {
            FRACTAL_CAPABILITY: {
                "width": 24,
                "height": 16,
                "max_iter": 32,
            },
            OPTIMIZATION_CAPABILITY: {
                "xmin": -3,
                "xmax": 3,
                "ymin": -2,
                "ymax": 4,
            },
            PARAMETER_SWEEP_CAPABILITY: {
                "r_values": ["2", "5/2", "3", "7/2"],
                "x0": "1/2",
                "steps": 6,
            },
            PROCEDURAL_WORLD_CAPABILITY: {
                "seed": "mineral-field-001",
                "chunk_x": 3,
                "chunk_y": -2,
                "size": 12,
            },
        }

        artifacts = {}
        for capability, payload in payloads.items():
            first = execute_mineral_capability(
                capability,
                payload,
                worker_root=root,
            )
            second = execute_mineral_capability(
                capability,
                payload,
                worker_root=root,
            )
            assert first["artifact_address"] == second["artifact_address"]
            assert first["work_address"] == second["work_address"]
            assert first["result_id"] == second["result_id"]
            assert first["verification_status"] == "UNVERIFIED"
            assert Path(first["artifact_path"]).is_file()
            assert Path(first["result_path"]).is_file()
            artifacts[capability] = first["artifact_address"]

        # Prove the same capabilities are reachable through the ordinary GHoT
        # task/receipt path, not merely as library functions.
        task, receipt = reference_node.execute(
            PARAMETER_SWEEP_CAPABILITY,
            payloads[PARAMETER_SWEEP_CAPABILITY],
        )
        assert task["capability"] == PARAMETER_SWEEP_CAPABILITY
        assert receipt["status"] == "ok"
        assert (
            receipt["output"]["artifact_address"]
            == artifacts[PARAMETER_SWEEP_CAPABILITY]
        )

        _, registry_receipt = reference_node.execute(
            REGISTRY_CAPABILITY,
            None,
        )
        assert registry_receipt["status"] == "ok"
        assert registry_receipt["output"]["mineral_count"] == 11

        # Declared HOLD potential must not silently become an adapter fallback.
        _, held_receipt = reference_node.execute(
            "render.blender.tile/v0",
            {"scene": "not-authorized"},
        )
        assert held_receipt["status"] == "error"
        assert "not offered" in held_receipt["error"]

        native_rows = [
            item
            for item in catalog["minerals"]
            if item["capability"] in EXECUTABLE_CAPABILITIES
        ]
        hold_rows = [
            item
            for item in catalog["minerals"]
            if str(item["status"]).startswith("HOLD")
        ]

        print(json.dumps({
            "simulation_passed": True,
            "registry": {
                "mineral_count": catalog["mineral_count"],
                "native_new_miners": len(native_rows),
                "hold_contracts": len(hold_rows),
                "ice_cube_remains_composed_mineral": True,
            },
            "native_artifacts": artifacts,
            "ordinary_ghot_task_path": True,
            "deterministic_replay": True,
            "held_not_advertised": sorted(held_capabilities),
            "laws": catalog["laws"],
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
