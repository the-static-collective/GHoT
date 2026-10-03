#!/usr/bin/env python3
"""GHoT Wake Composer — Experiments 009/010/012.

Re-evaluates durable HOLDs against the current field. When a HOLD becomes
runnable, the worker must acquire an exclusive expiring lease before execution.

A healthy local worker renews its lease while work runs. If the selected body
is remote, the owner automatically emits an identity-bound portable DISPATCH
instead of executing through the older direct task transport.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
import uuid
from contextlib import nullcontext
from typing import Any, Callable

from capability_composer import gather_candidates
from energy_scheduler import decide_from_candidates
from hold_queue import HoldQueue, iso_at
from lan_node import request_task
from lease_authority import LeaseAuthority
from reference_node import execute, node_id, persist
from work_lease import WorkLeaseStore


Executor = Callable[[dict[str, Any], Any], dict[str, Any]]


class LeaseHeartbeat:
    def __init__(
        self,
        store: WorkLeaseStore,
        claim: dict[str, Any],
        *,
        lease_seconds: float,
    ) -> None:
        self.store = store
        self.claim = claim
        self.lease_seconds = lease_seconds
        self.interval = max(0.25, min(10.0, lease_seconds / 3.0))
        self.stop = threading.Event()
        self.lost = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.stop.wait(self.interval):
            renewed = self.store.renew(
                self.claim,
                lease_seconds=self.lease_seconds,
            )
            if renewed is None:
                self.lost.set()
                return
            self.claim = renewed

    def __enter__(self) -> "LeaseHeartbeat":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop.set()
        self.thread.join(timeout=max(1.0, self.interval + 0.5))


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
    raw = json.dumps(
        sorted(compact, key=lambda x: str(x.get("node_id"))),
        sort_keys=True,
    )
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
    worker_id: str | None = None,
    lease_seconds: float = 60.0,
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
            "status": expired.get("status"),
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

    selected = decision.get("selected") or {}
    if selected.get("location") == "remote":
        target_particular = selected.get("identity_particular")
        target_public_key = selected.get("identity_public_key")
        if (
            selected.get("identity_available") is not True
            or not target_particular
            or not isinstance(target_public_key, dict)
        ):
            reason = "selected remote body has no usable P-256 identity"
            current = queue.note_recheck(
                hold_id,
                child_energy_plan_id=child_plan["energy_plan_id"],
                reason=reason,
                at=when,
            )
            return {
                "hold_id": hold_id,
                "status": "held",
                "action": "remote-identity-unavailable",
                "hold": current,
                "energy_plan": child_plan,
                "execution": None,
            }

        authority = LeaseAuthority(queue.root)
        existing_dispatch = authority.get_dispatch(hold_id, at=when)
        if (
            existing_dispatch is not None
            and existing_dispatch.get("status") in {"offered", "claimed"}
        ):
            return {
                "hold_id": hold_id,
                "status": "held",
                "action": "remote-dispatch-active",
                "hold": queue.get(hold_id),
                "energy_plan": child_plan,
                "dispatch": existing_dispatch,
                "execution": None,
            }

        try:
            dispatch = authority.prepare_dispatch(
                hold_id,
                target_worker_id=str(selected["node_id"]),
                target_node_id=str(selected["node_id"]),
                target_particular=str(target_particular),
                target_public_key=target_public_key,
                child_energy_plan_id=child_plan["energy_plan_id"],
                at=when,
            )
        except Exception as exc:
            reason = f"automatic remote dispatch failed: {type(exc).__name__}: {exc}"
            current = queue.note_recheck(
                hold_id,
                child_energy_plan_id=child_plan["energy_plan_id"],
                reason=reason,
                at=when,
            )
            return {
                "hold_id": hold_id,
                "status": "held",
                "action": "remote-dispatch-failed",
                "hold": current,
                "energy_plan": child_plan,
                "execution": None,
                "error": reason,
            }

        current = queue.note_recheck(
            hold_id,
            child_energy_plan_id=child_plan["energy_plan_id"],
            reason=(
                "owner automatically dispatched selected remote body "
                + str(selected["node_id"])
            ),
            at=when,
        )
        return {
            "hold_id": hold_id,
            "status": "held",
            "action": "remote-dispatched",
            "hold": current,
            "energy_plan": child_plan,
            "dispatch": dispatch,
            "execution": None,
        }

    actual_worker = worker_id or f"{node_id()}:pid-{os.getpid()}"
    claim_result = queue.claim_for_execution(
        hold_id,
        worker_id=actual_worker,
        lease_seconds=lease_seconds,
        at=when,
    )

    if claim_result.get("status") != "claimed":
        status = claim_result.get("status")
        if status == "busy":
            return {
                "hold_id": hold_id,
                "status": "held",
                "action": "claimed-by-other",
                "energy_plan": child_plan,
                "claim": claim_result.get("claim"),
                "execution": None,
            }
        if status == "inactive":
            return {
                "hold_id": hold_id,
                "status": claim_result.get("hold_status"),
                "action": "stop",
                "energy_plan": child_plan,
                "execution": None,
            }
        return {
            "hold_id": hold_id,
            "status": status,
            "action": status,
            "energy_plan": child_plan,
            "execution": None,
        }

    claim = claim_result["claim"]
    leases = WorkLeaseStore(queue.root)
    runner = executor or _execute_child

    heartbeat_context = (
        LeaseHeartbeat(leases, claim, lease_seconds=lease_seconds)
        if at is None
        else nullcontext()
    )

    try:
        with heartbeat_context as heartbeat:
            result = runner(child_plan, hold.get("payload"))
            if heartbeat is not None and getattr(heartbeat, "lost", None):
                if heartbeat.lost.is_set():
                    return {
                        "hold_id": hold_id,
                        "status": "held",
                        "action": "lease-lost",
                        "energy_plan": child_plan,
                        "claim": claim,
                        "execution": result,
                    }
    except Exception as exc:
        finish_at = time.time() if at is None else when
        reason = f"{type(exc).__name__}: {exc}"
        current = queue.note_recheck(
            hold_id,
            child_energy_plan_id=child_plan["energy_plan_id"],
            reason=reason,
            at=finish_at,
        )
        leases.abandon(claim, reason=reason, at=finish_at)
        return {
            "hold_id": hold_id,
            "status": "held",
            "action": "release-attempt-exception",
            "hold": current,
            "energy_plan": child_plan,
            "claim": claim,
            "execution": None,
            "error": reason,
        }

    finish_at = time.time() if at is None else when
    receipt = ((result.get("execution") or {}).get("receipt") or {})
    result_status = result.get("status", "unknown")

    if result_status == "ok":
        released = queue.release(
            hold_id,
            child_energy_plan_id=child_plan["energy_plan_id"],
            receipt_id=receipt.get("receipt_id"),
            lease_id=claim["lease_id"],
            at=finish_at,
        )
        if released.get("status") == "released":
            leases.finish(
                claim,
                outcome="ok",
                receipt_id=receipt.get("receipt_id"),
                at=finish_at,
            )
            return {
                "hold_id": hold_id,
                "status": "released",
                "action": decision["action"],
                "hold": released,
                "energy_plan": child_plan,
                "claim": claim,
                "execution": result,
            }

        return {
            "hold_id": hold_id,
            "status": released.get("status", "held"),
            "action": "lease-not-current",
            "hold": released,
            "energy_plan": child_plan,
            "claim": claim,
            "execution": result,
        }

    reason = receipt.get("error") or f"release attempt returned {result_status}"
    current = queue.note_recheck(
        hold_id,
        child_energy_plan_id=child_plan["energy_plan_id"],
        reason=reason,
        at=finish_at,
    )
    leases.abandon(claim, reason=reason, at=finish_at)
    return {
        "hold_id": hold_id,
        "status": "held",
        "action": "release-attempt-failed",
        "hold": current,
        "energy_plan": child_plan,
        "claim": claim,
        "execution": result,
    }


def wake_all(
    *,
    queue: HoldQueue | None = None,
    timeout: float = 2.0,
    at: float | None = None,
    worker_id: str | None = None,
    lease_seconds: float = 60.0,
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
    actual_worker = worker_id or f"{node_id()}:pid-{os.getpid()}"
    results = [
        reevaluate_hold(
            hold["hold_id"],
            queue=queue,
            candidates=candidates,
            field_policy=snapshot.get("policy") or {},
            at=at,
            trigger="hold.wake_all",
            worker_id=actual_worker,
            lease_seconds=lease_seconds,
        )
        for hold in held
    ]
    return {
        "kind": "ghot.wake.result",
        "version": "0",
        "observed_at": iso_at(when),
        "worker_id": actual_worker,
        "expired": [item["hold_id"] for item in expired],
        "field_fingerprint": _field_fingerprint(candidates),
        "results": results,
    }


def _add_worker_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--worker-id", default=None)
    parser.add_argument("--lease-seconds", type=float, default=60.0)


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
    _add_worker_args(wake_parser)

    one_parser = sub.add_parser("recheck")
    one_parser.add_argument("hold_id")
    one_parser.add_argument("--timeout", type=float, default=2.0)
    _add_worker_args(one_parser)

    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--timeout", type=float, default=2.0)
    watch_parser.add_argument("--interval", type=float, default=5.0)
    _add_worker_args(watch_parser)

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
        result = reevaluate_hold(
            args.hold_id,
            queue=queue,
            timeout=args.timeout,
            worker_id=args.worker_id,
            lease_seconds=args.lease_seconds,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") != "missing" else 1

    if args.command == "wake":
        print(json.dumps(wake_all(
            queue=queue,
            timeout=args.timeout,
            worker_id=args.worker_id,
            lease_seconds=args.lease_seconds,
        ), indent=2))
        return 0

    if args.command == "watch":
        if args.interval <= 0:
            raise SystemExit("--interval must be > 0")

        actual_worker = args.worker_id or f"{node_id()}:pid-{os.getpid()}"
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
                    print(json.dumps(wake_all(
                        queue=queue,
                        timeout=args.timeout,
                        worker_id=actual_worker,
                        lease_seconds=args.lease_seconds,
                    ), indent=2))
                    last_fingerprint = fingerprint
                    last_hold_set = hold_set

                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
