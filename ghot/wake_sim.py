#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 009."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

from hold_queue import HoldQueue, iso_at
from wake_composer import reevaluate_hold


def candidate(
    node_id: str,
    *,
    willingness: str,
    source: str,
    surplus: bool,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "location": "remote",
        "url": f"http://{node_id}.invalid:7788",
        "field_state": "awake",
        "body": {
            "node_id": node_id,
            "power": {
                "willingness": willingness,
                "source": source,
                "charging": source != "battery",
                "renewable_surplus": surplus,
            },
            "offers": [{
                "kind": "ghot.offer",
                "version": "0",
                "capability": "render.video",
                "available": True,
                "power": {
                    "class": "heavy",
                    "willingness": willingness,
                    "policy_reasons": [],
                },
            }],
        },
    }


def make_hold(hold_id: str, *, expires_at: float | None = None) -> dict[str, Any]:
    return {
        "kind": "ghot.hold",
        "version": "0",
        "hold_id": hold_id,
        "energy_plan_id": f"energy-plan-origin-{uuid.uuid4()}",
        "created_at": iso_at(100.0),
        "expires_at_epoch": expires_at,
        "expires_at": iso_at(expires_at) if expires_at is not None else None,
        "requester_node_id": "sim-requester",
        "capability": "render.video",
        "payload": {"album": "future rearview"},
        "urgency": "background",
        "deferrable": True,
        "data_node_id": None,
        "prefer_surplus_for_background": True,
        "reason": "battery-only heap",
        "release_condition": "re-evaluate when field or power state changes",
        "status": "held",
    }


def main() -> int:
    executed: list[str] = []

    def fake_executor(plan: dict[str, Any], payload: Any) -> dict[str, Any]:
        executed.append(plan["energy_plan_id"])
        receipt = {
            "receipt_id": f"receipt-sim-{uuid.uuid4()}",
            "status": "ok",
            "output": {"payload": payload},
        }
        return {
            "kind": "ghot.energy.result",
            "version": "0",
            "status": "ok",
            "energy_plan": plan,
            "execution": {"receipt": receipt},
        }

    with tempfile.TemporaryDirectory() as tmp:
        queue = HoldQueue(Path(tmp))

        first = queue.enqueue(make_hold("hold-sim-release"), at=100.0)
        battery = [
            candidate(
                "body-battery",
                willingness="normal",
                source="battery",
                surplus=False,
            )
        ]
        still = reevaluate_hold(
            first["hold_id"],
            queue=queue,
            candidates=battery,
            field_policy={},
            executor=fake_executor,
            at=110.0,
            trigger="simulation.battery",
        )
        assert still["status"] == "held"
        assert len(executed) == 0

        solar = [
            candidate(
                "body-solar",
                willingness="abundant",
                source="solar",
                surplus=True,
            )
        ]
        released = reevaluate_hold(
            first["hold_id"],
            queue=queue,
            candidates=solar,
            field_policy={},
            executor=fake_executor,
            at=120.0,
            trigger="simulation.solar_arrived",
        )
        assert released["status"] == "released"
        assert len(executed) == 1
        assert released["energy_plan"]["parent_hold_id"] == first["hold_id"]
        assert (
            released["energy_plan"]["parent_energy_plan_id"]
            == first["energy_plan_id"]
        )

        cancelled = queue.enqueue(make_hold("hold-sim-cancel"), at=130.0)
        queue.cancel(cancelled["hold_id"], "simulation cancel", at=131.0)
        cancel_result = reevaluate_hold(
            cancelled["hold_id"],
            queue=queue,
            candidates=solar,
            field_policy={},
            executor=fake_executor,
            at=132.0,
        )
        assert cancel_result["status"] == "cancelled"
        assert len(executed) == 1

        expiring = queue.enqueue(
            make_hold("hold-sim-expire", expires_at=141.0),
            at=140.0,
        )
        expire_result = reevaluate_hold(
            expiring["hold_id"],
            queue=queue,
            candidates=solar,
            field_policy={},
            executor=fake_executor,
            at=142.0,
        )
        assert expire_result["status"] == "expired"
        assert len(executed) == 1

        final_release = queue.get(first["hold_id"])
        final_cancel = queue.get(cancelled["hold_id"])
        final_expire = queue.get(expiring["hold_id"])

        passed = (
            final_release is not None
            and final_release["status"] == "released"
            and int(final_release["evaluation_count"]) == 1
            and final_cancel is not None
            and final_cancel["status"] == "cancelled"
            and final_expire is not None
            and final_expire["status"] == "expired"
            and len(executed) == 1
        )

        print(json.dumps({
            "simulation_passed": passed,
            "held_then_released": {
                "first_recheck": still["status"],
                "final": final_release,
                "child_plan": released["energy_plan"],
            },
            "cancelled_never_executed": final_cancel,
            "expired_never_executed": final_expire,
            "execution_count": len(executed),
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
