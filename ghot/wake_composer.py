#!/usr/bin/env python3
"""GHoT Wake Composer — Experiment 009.

Re-evaluates durable HOLDs against the current liveness/power field. A hold can
remain held, release into a child energy plan, expire, or remain inert after
cancellation.

The Wake Composer never invents a future wake time. It reacts to a changed
field or to an explicit wake pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from typing import Any, Callable

from capability_composer import gather_candidates
from energy_scheduler import decide_from_candidates
from hold_queue import HoldQueue, iso_at
from lan_node import request_task
from reference_node import execute, node_id, persist


Executor = Callable[[dict[str, Any], Any], dict[str, Any]]


def _field_fingerprint(candidates: list[dict[str, Any]]) -> str:
    compact = []
    for candidate in candidates:
        body = candidate.get("body") or {}
        power = body.get("power") or {}
        offers = [
            {
                "capability": offer.get("capability"),
                "available": offer.get("available"),
            }
            for offer in body.get("offers", [])
        ]
        compact.append({
            "node_id": candidate.get("node_id"),
            "field_state": candidate.get("field_state"),
            "power_willingness": power.get("willingness"),
            "source": power.get("source"),
            "renewable_surplus": power.get("renewable_surplus"),
            "offers": sorted(offers, key=lambda x: str(x.get("capability"))),
        })
    raw = json.dumps(sorted(compact, key=lambda x: str(x.get("node_id"))), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _child_energy_plan(
    hold: dict[str, Any],
    decision: dict[str, Any],
    *,
    field_policy: dict[str, Any],
    trigger: str,
    at: float,
) -> dict[str, Any]:
    plan = {
        "kind": "ghot.energy.plan",
        "version": "0",
        "energy_plan_id": f"energy-plan-{uuid.uuid4()}",
        "created_at": iso_at(at),
        "requester_node_id": hold["requester_node_id"],
        "parent_hold_id": hold["hold_id"],
        "parent_energy_plan_id": hold["energy_plan_id"],
        "trigger": trigger,
        "field_policy": field_policy,
        "payload": hold.get("payload"),
        **decision,
    }
    persist("energy-plan", plan)
    return plan


def _execute_child(plan: dict[str, Any], payload: Any) -> dict[str, Any]:
    selected = plan.get("selected")
    if not selected:
        return {
            "kind": "ghot.energy.result",
            "version": "0",
            "status": "no-eligible-body",
            "energy_plan": plan,
            "execution": None,
        }

    constraints = {
        "energy_plan_id": plan["energy_plan_id"],
        "parent_hold_id": plan.get("parent_hold_id"),
        "parent_energy_plan_id": plan.get("parent_energy_plan_id"),
        "urgency": plan.get("urgency"),
        "deferrable": plan.get("deferrable"),
        "data_node_id": plan.get("data_node_id"),
        "power_class": plan.get("power_class"),
        "energy_decision": plan.get("action"),
        "why_selected": selected.get("reasons") or [],
    }

    if selected.get("location") == "local":
        task, receipt = execute(
            plan["capability"],
            payload,
            requester_node_id=plan["requester_node_id"],
            constraints=constraints,
        )
        execution = {"task": task, "receipt": receipt}
    else:
        url = selected.get("url")
        if not url:
            return {
                "kind": "ghot.energy.result",
                "version": "0",
                "status": "selected-body-has-no-route",
                "energy_plan": plan,
                "execution": None,
            }
        execution = request_task(
            url,
            plan["capability"],
            payload,
            constraints=constraints,
            requester_node_id=plan["requester_node_id"],
        )

    receipt = execution.get("receipt") or {}
    return {
        "kind": "ghot.energy.result",
        "version": "0",
        "status": receipt.get("status", "unknown"),
        "energy_plan": plan,
        "execution": execution,
    }


def reevaluate_hold(
    hold_id: str,
    *,
    queue: HoldQueue | None = None,
    timeout: float = 2.0,
    candidates: list[dict[str, Any]] | None = None,
    field_policy: dict[str, Any] | None = None,
    executor: Executor | None = None,
    at: float | None = None,
    trigger: str = "hold.wake",
) -> dict[str, Any]:
    when = time.time() if at is None else float(at)
    queue = queue or HoldQueue()
    hold = queue.get(hold_id)

    if hold is None:
        return {"hold_id": hold_id, "status": "missing"}

    if hold.get("status") != "held":
        return {
            "hold_id": hold_id,
            "status": hold.get("status"),
            "action": "inactive",
        }

    if queue.is_expired(hold, at=when):
        expired = queue.expire(hold_id, at=when)
        return {
            "hold_id": hold_id,
            "status": "expired",
            "action": "expire",
            "hold": expired,
        }

    if candidates is None:
        candidates, snapshot = gather_candidates(timeout)
        current_field_policy = snapshot.get("policy") or {}
    else:
        current_field_policy = field_policy or {}

    decision = decide_from_candidates(
        candidates,
        hold["capability"],
        urgency=hold.get("urgency", "normal"),
        deferrable=bool(hold.get("deferrable", False)),
        data_node_id=hold.get("data_node_id"),
        prefer_surplus_for_background=bool(
            hold.get("prefer_surplus_for_background", True)
        ),
    )

    child_plan = _child_energy_plan(
        hold,
        decision,
        field_policy=current_field_policy,
        trigger=trigger,
        at=when,
    )

    if decision["action"] in {"hold", "no_eligible_body"}:
        reason = (
            "; ".join(decision.get("hold_reasons") or [])
            or f"current decision remains {decision['action']}"
        )
        current = queue.note_recheck(
            hold_id,
            child_energy_plan_id=child_plan["energy_plan_id"],
            reason=reason,
            at=when,
        )
        return {
            "hold_id": hold_id,
            "status": "held",
            "action": decision["action"],
            "hold": current,
            "energy_plan": child_plan,
            "execution": None,
        }

    # Re-read immediately before execution. Cancellation/expiry wins the race.
    current = queue.get(hold_id)
    if current is None:
        return {"hold_id": hold_id, "status": "missing", "action": "stop"}
    if current.get("status") != "held":
        return {
            "hold_id": hold_id,
            "status": current.get("status"),
            "action": "stop",
            "energy_plan": child_plan,
        }
    if queue.is_expired(current, at=when):
        expired = queue.expire(hold_id, at=when)
        return {
            "hold_id": hold_id,
            "status": "expired",
            "action": "expire",
            "hold": expired,
            "energy_plan": child_plan,
        }

    runner = executor or _execute_child
    result = runner(child_plan, hold.get("payload"))
    receipt = ((result.get("execution") or {}).get("receipt") or {})
    result_status = result.get("status", "unknown")

    if result_status == "ok":
        released = queue.release(
            hold_id,
            child_energy_plan_id=child_plan["energy_plan_id"],
            receipt_id=receipt.get("receipt_id"),
            at=when,
        )
        return {
            "hold_id": hold_id,
            "status": released.get("status"),
            "action": decision["action"],
            "hold": released,
            "energy_plan": child_plan,
            "execution": result,
        }

    reason = receipt.get("error") or f"release attempt returned {result_status}"
    current = queue.note_recheck(
        hold_id,
        child_energy_plan_id=child_plan["energy_plan_id"],
        reason=reason,
        at=when,
    )
    return {
        "hold_id": hold_id,
        "status": "held",
        "action": "release-attempt-failed",
        "hold": current,
        "energy_plan": child_plan,
        "execution": result,
    }


def wake_all(
    *,
    queue: HoldQueue | None = None,
    timeout: float = 2.0,
    at: float | None = None,
) -> dict[str, Any]:
    when = time.time() if at is None else float(at)
    queue = queue or HoldQueue()
    expired = queue.expire_due(at=when)
    held = queue.list(status="held")

    if not held:
        return {
            "kind": "ghot.wake.result",
            "version": "0",
            "observed_at": iso_at(when),
            "expired": [item["hold_id"] for item in expired],
            "results": [],
        }

    candidates, snapshot = gather_candidates(timeout)
    results = [
        reevaluate_hold(
            hold["hold_id"],
            queue=queue,
            candidates=candidates,
            field_policy=snapshot.get("policy") or {},
            at=when,
            trigger="hold.wake_all",
        )
        for hold in held
    ]
    return {
        "kind": "ghot.wake.result",
        "version": "0",
        "observed_at": iso_at(when),
        "expired": [item["hold_id"] for item in expired],
        "field_fingerprint": _field_fingerprint(candidates),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain and wake GHoT HOLDs.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--all", action="store_true")

    cancel_parser = sub.add_parser("cancel")
    cancel_parser.add_argument("hold_id")
    cancel_parser.add_argument("reason", nargs="?", default="cancelled by operator")

    wake_parser = sub.add_parser("wake")
    wake_parser.add_argument("--timeout", type=float, default=2.0)

    one_parser = sub.add_parser("recheck")
    one_parser.add_argument("hold_id")
    one_parser.add_argument("--timeout", type=float, default=2.0)

    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--timeout", type=float, default=2.0)
    watch_parser.add_argument("--interval", type=float, default=5.0)

    args = parser.parse_args()
    queue = HoldQueue()

    if args.command == "list":
        records = queue.list(status=None if args.all else "held")
        print(json.dumps(records, indent=2))
        return 0

    if args.command == "cancel":
        try:
            result = queue.cancel(args.hold_id, args.reason)
        except KeyError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            return 1
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "recheck":
        result = reevaluate_hold(args.hold_id, queue=queue, timeout=args.timeout)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") != "missing" else 1

    if args.command == "wake":
        print(json.dumps(wake_all(queue=queue, timeout=args.timeout), indent=2))
        return 0

    if args.command == "watch":
        if args.interval <= 0:
            raise SystemExit("--interval must be > 0")

        last_fingerprint: str | None = None
        last_hold_set: tuple[str, ...] | None = None
        try:
            while True:
                queue.expire_due()
                held = queue.list(status="held")
                candidates, _ = gather_candidates(args.timeout)
                fingerprint = _field_fingerprint(candidates)
                hold_set = tuple(sorted(item["hold_id"] for item in held))

                if fingerprint != last_fingerprint or hold_set != last_hold_set:
                    print(json.dumps(wake_all(queue=queue, timeout=args.timeout), indent=2))
                    last_fingerprint = fingerprint
                    last_hold_set = hold_set

                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
