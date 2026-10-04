#!/usr/bin/env python3
"""Deterministic native background mining proof for Experiment 031."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def power_record(willingness: str) -> dict[str, Any]:
    abundant = willingness == "abundant"
    return {
        "battery_percent": 90.0 if abundant else 80.0,
        "charging": abundant,
        "source": "solar" if abundant else "battery",
        "renewable_surplus": abundant,
        "temperature_c": 45.0,
        "thermal_state": "normal",
        "load_1m": 0.1,
        "load_5m": 0.1,
        "load_15m": 0.1,
        "load_per_cpu_1m": 0.01,
        "probe": {"simulation": True},
        "willingness": willingness,
        "willingness_reasons": [
            "simulated renewable surplus" if abundant else "simulated ordinary battery"
        ],
    }


def candidate(body_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": body_record["node_id"],
        "location": "local",
        "url": None,
        "body": body_record,
        "field_state": "awake",
        "last_seen": None,
        "age_seconds": 0,
        "consecutive_failures": 0,
        "quarantine_until": None,
    }


def make_hold(root: Path, body_record: dict[str, Any], payload: dict[str, Any]):
    from energy_scheduler import decide_from_candidates
    from hold_queue import HoldQueue
    from reference_node import now, node_id

    decision = decide_from_candidates(
        [candidate(body_record)],
        "ghot.ice-cube/v0",
        urgency="background",
        deferrable=True,
        prefer_surplus_for_background=True,
    )
    assert decision["action"] == "hold"
    hold = {
        "kind": "ghot.hold",
        "version": "0",
        "hold_id": "hold-ice-cube-031",
        "energy_plan_id": "energy-plan-ice-cube-031",
        "created_at": now(),
        "expires_at_epoch": None,
        "expires_at": None,
        "requester_node_id": node_id(),
        "capability": "ghot.ice-cube/v0",
        "payload": payload,
        "urgency": "background",
        "deferrable": True,
        "data_node_id": None,
        "prefer_surplus_for_background": True,
        "reason": "; ".join(decision["hold_reasons"]),
        "release_condition": "wake when power field becomes favorable",
        "status": "held",
    }
    return HoldQueue(root).enqueue(hold)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dogram-repo", type=Path, required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "ghot"
        os.environ["GHOT_HOME"] = str(root)
        os.environ["GHOT_DOGRAM_REPO"] = str(args.dogram_repo.resolve())

        # Imports happen only after GHOT_HOME is bound so every subsystem shares
        # the same temporary body.
        import reference_node
        import capability_composer
        from ice_cube import ICE_CUBE_CAPABILITY
        from organ import OrganDaemon
        from power_field import capability_power_class
        from hold_queue import HoldQueue

        current = {"value": power_record("normal")}
        reference_node.probe_power = lambda: current["value"]
        # capability_composer imported reference_node.body as a function object;
        # its globals still resolve the patched reference_node.probe_power.
        capability_composer.body = reference_node.body

        normal_body = reference_node.body()
        offer = next(
            item for item in normal_body["offers"]
            if item["capability"] == ICE_CUBE_CAPABILITY
        )
        assert offer["available"] is True
        assert offer["power"]["class"] == "heavy"
        assert capability_power_class(ICE_CUBE_CAPABILITY) == "heavy"

        payload = {
            "lucas_index": 2,
            "width": 24,
            "height": 24,
            "max_halley_iter": 8,
            "c_re": "0",
            "c_im": "0",
            "tolerance": "1e-9",
            "fiber_count": 72,
        }
        hold = make_hold(root, normal_body, payload)
        assert hold["status"] == "held"

        # Power changes. No Ice-Cube-specific release path is called: the normal
        # OrganDaemon cycle owns Wake Composer.
        current["value"] = power_record("abundant")

        daemon = OrganDaemon(
            root=root,
            body_probe=reference_node.body,
            peer_discoverer=lambda timeout: [],
            authority_resolver=lambda timeout: [],
            work_runner=lambda urls, worker_id, lease_seconds: {
                "status": "no-trusted-authority",
                "worker_id": worker_id,
            },
            discovery_timeout=0.01,
            authority_timeout=0.01,
            lease_seconds=60,
        )
        state = daemon.cycle()
        wake = state["held_work"]
        assert wake["status"] == "evaluated"
        assert len(wake["results"]) == 1
        release = wake["results"][0]
        assert release["status"] == "released"
        receipt = release["execution"]["execution"]["receipt"]
        assert receipt["status"] == "ok"
        output = receipt["output"]
        assert output["capability"] == ICE_CUBE_CAPABILITY
        assert output["dogram_status"] == "OK"
        assert output["dogram_claim_scope"] == "bounded-math-and-projection-witness/v0"

        stored = HoldQueue(root).get("hold-ice-cube-031")
        assert stored is not None
        assert stored["status"] == "released"
        assert stored["released_receipt_id"] == receipt["receipt_id"]

        result_path = Path(output["result_path"])
        render_path = Path(output["render_path"])
        assert result_path.is_file()
        assert render_path.is_file()
        result = json.loads(result_path.read_text(encoding="utf-8"))
        assert result["dogram_status"] == "OK"
        assert result["specimen_id"] == output["specimen_id"]

        summary = {
            "simulation_passed": True,
            "capability": {
                "id": ICE_CUBE_CAPABILITY,
                "advertised": True,
                "power_class": offer["power"]["class"],
                "artifact_stays_on_executor": offer["limits"][
                    "artifact_stays_on_executor"
                ],
            },
            "ordinary_battery": {
                "decision": "hold",
                "hold_id": hold["hold_id"],
            },
            "surplus_power": {
                "organ_wake_status": wake["status"],
                "hold_status": stored["status"],
                "receipt_status": receipt["status"],
            },
            "verification": {
                "dogram_status": output["dogram_status"],
                "claim_scope": output["dogram_claim_scope"],
                "specimen_id": output["specimen_id"],
                "render_address": output["render_address"],
            },
        }
        print(json.dumps(summary, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
