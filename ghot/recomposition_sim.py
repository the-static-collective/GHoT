#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 005.

No network or second machine is required. Fake body A is selected first and
fails at crossing time; body B is then selected and succeeds.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from reference_node import now
from resilient_composer import run_resilient


class NoopField:
    def record_failure(self, node_id: str, reason: str) -> None:
        pass

    def record_success(self, node_id: str) -> None:
        pass


def fake_planner(
    capability: str,
    *,
    excluded_node_ids: set[str] | None = None,
    composition_id: str | None = None,
    parent_plan_id: str | None = None,
    recomposition_reason: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    excluded = excluded_node_ids or set()
    candidates = [
        {
            "node_id": "sim-body-a",
            "location": "remote",
            "url": "http://sim-a.invalid",
            "eligible": "sim-body-a" not in excluded,
            "score": 20,
            "reasons": ["simulation: preferred first body"],
            "rejected": (
                [] if "sim-body-a" not in excluded
                else ["excluded after earlier failed attempt"]
            ),
        },
        {
            "node_id": "sim-body-b",
            "location": "remote",
            "url": "http://sim-b.invalid",
            "eligible": "sim-body-b" not in excluded,
            "score": 10,
            "reasons": ["simulation: fallback body"],
            "rejected": (
                [] if "sim-body-b" not in excluded
                else ["excluded after earlier failed attempt"]
            ),
        },
    ]
    eligible = [x for x in candidates if x["eligible"]]
    eligible.sort(key=lambda x: (-x["score"], x["node_id"]))
    selected = eligible[0] if eligible else None
    if selected:
        selected = {
            **selected,
            "why_selected": ["simulation deterministic selection"],
        }
    return {
        "kind": "ghot.plan",
        "version": "0",
        "plan_id": f"plan-sim-{uuid.uuid4()}",
        "composition_id": composition_id,
        "parent_plan_id": parent_plan_id,
        "recomposition_reason": recomposition_reason,
        "created_at": now(),
        "requester_node_id": "sim-requester",
        "capability": capability,
        "constraints": {},
        "preferences": {},
        "excluded_node_ids": sorted(excluded),
        "candidates": candidates,
        "selected": selected,
    }


def fake_executor(plan: dict[str, Any], payload: Any) -> dict[str, Any]:
    selected = plan["selected"]["node_id"]

    if selected == "sim-body-a":
        raise ConnectionError("simulation: body A disappeared after selection")

    receipt = {
        "kind": "ghot.receipt",
        "version": "0",
        "receipt_id": f"receipt-sim-{uuid.uuid4()}",
        "task_id": f"task-sim-{uuid.uuid4()}",
        "requester_node_id": plan["requester_node_id"],
        "executor_node_id": selected,
        "capability": plan["capability"],
        "status": "ok",
        "started_at": now(),
        "finished_at": now(),
        "output": {
            "echo": payload,
            "simulation": "body B completed fallback",
        },
        "output_sha256": None,
        "error": None,
    }
    return {
        "kind": "ghot.composition.result",
        "version": "0",
        "plan": plan,
        "status": "ok",
        "execution": {
            "task": {
                "kind": "ghot.task",
                "version": "0",
                "task_id": receipt["task_id"],
                "capability": plan["capability"],
                "created_at": now(),
                "requester_node_id": plan["requester_node_id"],
                "input": payload,
                "constraints": {
                    "composition_id": plan["composition_id"],
                    "plan_id": plan["plan_id"],
                },
            },
            "receipt": receipt,
        },
    }


def main() -> int:
    result = run_resilient(
        "system.echo",
        "simulation payload",
        max_attempts=3,
        planner=fake_planner,
        executor=fake_executor,
        field=NoopField(),
    )
    print(json.dumps(result, indent=2))

    attempts = result["attempts"]
    passed = (
        result["final_status"] == "ok"
        and len(attempts) == 2
        and attempts[0]["selected_node_id"] == "sim-body-a"
        and attempts[0]["outcome"] == "transport-error"
        and attempts[0]["next_action"] == "recompose"
        and attempts[1]["selected_node_id"] == "sim-body-b"
        and attempts[1]["outcome"] == "ok"
    )
    print(json.dumps({"simulation_passed": passed}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
