#!/usr/bin/env python3
"""GHoT Failure-Aware Recomposition — Experiment 005.

A selected body may disappear or fail after planning. This layer preserves the
failed attempt, excludes that body from the next plan, rediscovers the live
heap, and retries until success, exhaustion, or no eligible body remains.

Examples:
    python3 ghot/resilient_composer.py system.hash "hello heap"
    python3 ghot/resilient_composer.py runtime.ffmpeg.version --max-attempts 3
"""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any, Callable

from capability_composer import compose_plan, execute_plan, parse_payload
from liveness_field import LivenessField
from reference_node import node_id, now, persist


Planner = Callable[..., dict[str, Any]]
Executor = Callable[[dict[str, Any], Any], dict[str, Any]]


def _receipt_from_result(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    execution = result.get("execution") or {}
    if not isinstance(execution, dict):
        return {}
    receipt = execution.get("receipt") or {}
    return receipt if isinstance(receipt, dict) else {}


def _record_attempt(
    *,
    composition_id: str,
    ordinal: int,
    plan: dict[str, Any],
    started_at: str,
    finished_at: str,
    outcome: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    selected = plan.get("selected") or {}
    receipt = _receipt_from_result(result)
    attempt = {
        "kind": "ghot.attempt",
        "version": "0",
        "attempt_id": f"attempt-{uuid.uuid4()}",
        "composition_id": composition_id,
        "ordinal": ordinal,
        "plan_id": plan.get("plan_id"),
        "selected_node_id": selected.get("node_id"),
        "selected_location": selected.get("location"),
        "started_at": started_at,
        "finished_at": finished_at,
        "outcome": outcome,
        "receipt_id": receipt.get("receipt_id"),
        "receipt_status": receipt.get("status"),
        "error": error,
        "next_action": next_action,
    }
    persist("attempt", attempt)
    return attempt


def run_resilient(
    capability: str,
    payload: Any,
    *,
    max_attempts: int = 3,
    timeout: float = 2.0,
    min_battery: float | None = None,
    prefer_local: bool = True,
    prefer_plugged_in: bool = False,
    prefer_memory: bool = False,
    planner: Planner = compose_plan,
    executor: Executor = execute_plan,
    field: LivenessField | None = None,
) -> dict[str, Any]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    field_store = field or LivenessField()
    composition_id = f"composition-{uuid.uuid4()}"
    requester = node_id()
    created_at = now()
    excluded: set[str] = set()
    attempts: list[dict[str, Any]] = []
    parent_plan_id: str | None = None
    recomposition_reason: str | None = None
    final_status = "exhausted"
    final_plan_id: str | None = None
    final_receipt_id: str | None = None

    for ordinal in range(1, max_attempts + 1):
        plan = planner(
            capability,
            timeout=timeout,
            min_battery=min_battery,
            prefer_local=prefer_local,
            prefer_plugged_in=prefer_plugged_in,
            prefer_memory=prefer_memory,
            excluded_node_ids=set(excluded),
            composition_id=composition_id,
            parent_plan_id=parent_plan_id,
            recomposition_reason=recomposition_reason,
            field=field_store,
        )
        final_plan_id = plan.get("plan_id")
        selected = plan.get("selected")

        if not selected:
            attempts.append(
                _record_attempt(
                    composition_id=composition_id,
                    ordinal=ordinal,
                    plan=plan,
                    started_at=now(),
                    finished_at=now(),
                    outcome="no-eligible-body",
                    next_action="stop",
                )
            )
            final_status = "no-eligible-body"
            break

        started_at = now()
        try:
            result = executor(plan, payload)
            finished_at = now()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            attempts.append(
                _record_attempt(
                    composition_id=composition_id,
                    ordinal=ordinal,
                    plan=plan,
                    started_at=started_at,
                    finished_at=now(),
                    outcome="transport-error",
                    error=error,
                    next_action=(
                        "recompose" if ordinal < max_attempts else "stop"
                    ),
                )
            )
            field_store.record_failure(selected["node_id"], error)
            excluded.add(selected["node_id"])
            parent_plan_id = plan["plan_id"]
            recomposition_reason = (
                f"selected body {selected['node_id']} failed to complete crossing: {error}"
            )
            if ordinal >= max_attempts:
                final_status = "exhausted"
                break
            continue

        receipt = _receipt_from_result(result)
        status = result.get("status", "unknown")

        if status == "ok":
            field_store.record_success(selected["node_id"])
            final_receipt_id = receipt.get("receipt_id")
            attempts.append(
                _record_attempt(
                    composition_id=composition_id,
                    ordinal=ordinal,
                    plan=plan,
                    started_at=started_at,
                    finished_at=finished_at,
                    outcome="ok",
                    result=result,
                    next_action="stop",
                )
            )
            final_status = "ok"
            break

        attempts.append(
            _record_attempt(
                composition_id=composition_id,
                ordinal=ordinal,
                plan=plan,
                started_at=started_at,
                finished_at=finished_at,
                outcome=f"execution-{status}",
                result=result,
                error=receipt.get("error"),
                next_action=(
                    "recompose" if ordinal < max_attempts else "stop"
                ),
            )
        )
        field_store.record_failure(
            selected["node_id"],
            receipt.get("error") or f"execution status {status}",
        )
        excluded.add(selected["node_id"])
        parent_plan_id = plan["plan_id"]
        recomposition_reason = (
            f"selected body {selected['node_id']} returned status {status}"
        )

        if ordinal >= max_attempts:
            final_status = "exhausted"
            break

    composition = {
        "kind": "ghot.composition",
        "version": "0",
        "composition_id": composition_id,
        "requester_node_id": requester,
        "capability": capability,
        "created_at": created_at,
        "finished_at": now(),
        "max_attempts": max_attempts,
        "attempts": attempts,
        "excluded_node_ids": sorted(excluded),
        "final_status": final_status,
        "final_plan_id": final_plan_id,
        "final_receipt_id": final_receipt_id,
    }
    persist("composition", composition)
    return composition


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute a GHoT capability with failure-aware recomposition."
    )
    parser.add_argument("capability")
    parser.add_argument("payload", nargs="?", default=None)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--min-battery", type=float, default=None)
    parser.add_argument("--no-prefer-local", action="store_true")
    parser.add_argument("--prefer-plugged-in", action="store_true")
    parser.add_argument("--prefer-memory", action="store_true")
    args = parser.parse_args()

    result = run_resilient(
        args.capability,
        parse_payload(args.payload),
        max_attempts=args.max_attempts,
        timeout=args.timeout,
        min_battery=args.min_battery,
        prefer_local=not args.no_prefer_local,
        prefer_plugged_in=args.prefer_plugged_in,
        prefer_memory=args.prefer_memory,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["final_status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
