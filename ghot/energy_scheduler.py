#!/usr/bin/env python3
"""GHoT Energy-Aware Scheduler — Experiment 008.

Chooses not only WHERE a capability should run, but whether deferrable work
should run NOW.

Decisions:
    run_here
    run_there
    hold
    no_eligible_body

V0 is deterministic and inspectable. It does not forecast future solar input.
A HOLD means "current field does not justify spending this task yet."
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from typing import Any

from capability_composer import gather_candidates, parse_payload
from hold_queue import HoldQueue, iso_at
from power_field import capability_power_class
from reference_node import execute, node_id, now, persist
from lan_node import request_task


URGENCIES = {"immediate", "normal", "background"}


def _matching_offer(body: dict[str, Any], capability: str) -> dict[str, Any] | None:
    for offer in body.get("offers", []):
        if offer.get("capability") == capability:
            return offer
    return None


def _external_power(power: dict[str, Any]) -> bool:
    source = str(power.get("source") or "").lower()
    return power.get("charging") is True or source in {
        "ac", "mains", "grid", "usb", "solar", "external"
    }


def evaluate_energy_candidate(
    candidate: dict[str, Any],
    capability: str,
    *,
    data_node_id: str | None,
) -> dict[str, Any]:
    body = candidate.get("body") or {}
    power = body.get("power") or {}
    offer = _matching_offer(body, capability)
    reasons: list[str] = []
    rejected: list[str] = []
    score = 0.0

    if candidate.get("field_state") != "awake":
        rejected.append(
            f"body liveness state is {candidate.get('field_state') or 'unknown'}, not awake"
        )

    if offer is None:
        rejected.append("capability not offered")
        power_class = capability_power_class(capability)
        offer_available = False
        offer_power_reasons: list[str] = []
    else:
        power_class = (offer.get("power") or {}).get("class") or capability_power_class(capability)
        offer_available = offer.get("available") is True
        offer_power_reasons = list((offer.get("power") or {}).get("policy_reasons") or [])
        if not offer_available:
            if offer_power_reasons:
                rejected.append("offer withdrawn: " + "; ".join(offer_power_reasons))
            else:
                rejected.append("offer currently unavailable")

    if data_node_id and candidate.get("node_id") == data_node_id:
        score += 120.0
        reasons.append("+120 data already local")

    willingness = str(power.get("willingness") or "normal")
    if willingness == "abundant":
        score += 60.0
        reasons.append("+60 abundant power willingness")
    elif willingness == "normal":
        score += 10.0
        reasons.append("+10 normal power willingness")
    elif willingness == "conserve":
        score -= 40.0
        reasons.append("-40 conserve power willingness")
    elif willingness == "critical":
        score -= 100.0
        reasons.append("-100 critical power willingness")

    if power.get("renewable_surplus") is True:
        score += 40.0
        reasons.append("+40 renewable surplus")

    if _external_power(power):
        score += 20.0
        reasons.append("+20 externally powered/charging")

    if candidate.get("location") == "local":
        score += 5.0
        reasons.append("+5 requester-local execution")

    return {
        "node_id": candidate.get("node_id"),
        "location": candidate.get("location"),
        "url": candidate.get("url"),
        "field_state": candidate.get("field_state"),
        "capability": capability,
        "power_class": power_class,
        "offer_available": offer_available,
        "power_willingness": willingness,
        "power_source": power.get("source"),
        "renewable_surplus": power.get("renewable_surplus"),
        "charging": power.get("charging"),
        "data_local": bool(data_node_id and candidate.get("node_id") == data_node_id),
        "energy_favorable": willingness == "abundant" or _external_power(power),
        "score": round(score, 4),
        "reasons": reasons,
        "rejected": rejected,
        "eligible": not rejected,
    }


def decide_from_candidates(
    candidates: list[dict[str, Any]],
    capability: str,
    *,
    urgency: str = "normal",
    deferrable: bool = False,
    data_node_id: str | None = None,
    prefer_surplus_for_background: bool = True,
) -> dict[str, Any]:
    if urgency not in URGENCIES:
        raise ValueError(f"urgency must be one of {sorted(URGENCIES)}")

    evaluated = [
        evaluate_energy_candidate(
            candidate,
            capability,
            data_node_id=data_node_id,
        )
        for candidate in candidates
    ]
    eligible = [item for item in evaluated if item["eligible"]]
    eligible.sort(key=lambda item: (-item["score"], item["node_id"] or ""))

    inferred_power_class = capability_power_class(capability)
    for item in evaluated:
        if item["power_class"]:
            inferred_power_class = item["power_class"]
            break

    favorable = [item for item in eligible if item["energy_favorable"]]
    favorable.sort(key=lambda item: (-item["score"], item["node_id"] or ""))

    hold_reasons: list[str] = []

    if not eligible:
        known_withdrawn = any(
            "offer withdrawn:" in " ".join(item["rejected"])
            for item in evaluated
        )
        if deferrable and known_withdrawn:
            hold_reasons.append(
                "matching capability exists but current power policy withdrew it"
            )
            action = "hold"
            selected = None
        else:
            action = "no_eligible_body"
            selected = None
    elif (
        urgency == "background"
        and deferrable
        and inferred_power_class == "heavy"
        and prefer_surplus_for_background
        and not favorable
    ):
        action = "hold"
        selected = None
        hold_reasons.append(
            "background heavy work is deferrable and no eligible body has abundant/external power"
        )
    else:
        selected = (favorable[0] if (
            urgency == "background"
            and inferred_power_class == "heavy"
            and favorable
        ) else eligible[0])
        action = "run_here" if selected["location"] == "local" else "run_there"

    return {
        "action": action,
        "capability": capability,
        "urgency": urgency,
        "deferrable": deferrable,
        "power_class": inferred_power_class,
        "data_node_id": data_node_id,
        "prefer_surplus_for_background": prefer_surplus_for_background,
        "candidates": evaluated,
        "selected": selected,
        "hold_reasons": hold_reasons,
    }


def schedule(
    capability: str,
    payload: Any,
    *,
    urgency: str = "normal",
    deferrable: bool = False,
    data_node_id: str | None = None,
    timeout: float = 2.0,
    prefer_surplus_for_background: bool = True,
    execute_now: bool = True,
    hold_for_seconds: float | None = None,
    parent_hold_id: str | None = None,
    parent_energy_plan_id: str | None = None,
    trigger: str | None = None,
) -> dict[str, Any]:
    candidates, field_snapshot = gather_candidates(timeout)
    decision = decide_from_candidates(
        candidates,
        capability,
        urgency=urgency,
        deferrable=deferrable,
        data_node_id=data_node_id,
        prefer_surplus_for_background=prefer_surplus_for_background,
    )

    schedule_id = f"energy-plan-{uuid.uuid4()}"
    record = {
        "kind": "ghot.energy.plan",
        "version": "0",
        "energy_plan_id": schedule_id,
        "created_at": now(),
        "requester_node_id": node_id(),
        "parent_hold_id": parent_hold_id,
        "parent_energy_plan_id": parent_energy_plan_id,
        "trigger": trigger,
        "field_policy": field_snapshot.get("policy") or {},
        "payload": payload,
        **decision,
    }
    persist("energy-plan", record)

    if not execute_now:
        return {
            "kind": "ghot.energy.result",
            "version": "0",
            "status": "planned",
            "energy_plan": record,
            "hold": None,
            "execution": None,
        }

    if decision["action"] == "hold":
        created_epoch = time.time()
        expires_epoch = (
            created_epoch + hold_for_seconds
            if isinstance(hold_for_seconds, (int, float)) and hold_for_seconds > 0
            else None
        )
        hold = {
            "kind": "ghot.hold",
            "version": "0",
            "hold_id": f"hold-{uuid.uuid4()}",
            "energy_plan_id": schedule_id,
            "created_at": iso_at(created_epoch),
            "expires_at_epoch": expires_epoch,
            "expires_at": iso_at(expires_epoch) if expires_epoch is not None else None,
            "requester_node_id": record["requester_node_id"],
            "capability": capability,
            "payload": payload,
            "urgency": urgency,
            "deferrable": deferrable,
            "data_node_id": data_node_id,
            "prefer_surplus_for_background": prefer_surplus_for_background,
            "reason": "; ".join(decision["hold_reasons"]),
            "release_condition": (
                "re-evaluate when field/power state changes; V0 has no predictive wake time"
            ),
            "status": "held",
        }
        hold = HoldQueue().enqueue(hold, at=created_epoch)
        return {
            "kind": "ghot.energy.result",
            "version": "0",
            "status": "held",
            "energy_plan": record,
            "hold": hold,
            "execution": None,
        }

    if decision["action"] == "no_eligible_body":
        return {
            "kind": "ghot.energy.result",
            "version": "0",
            "status": "no-eligible-body",
            "energy_plan": record,
            "hold": None,
            "execution": None,
        }

    selected = decision["selected"]
    constraints = {
        "energy_plan_id": schedule_id,
        "urgency": urgency,
        "deferrable": deferrable,
        "data_node_id": data_node_id,
        "power_class": decision["power_class"],
        "energy_decision": decision["action"],
        "why_selected": selected["reasons"],
    }

    if selected["location"] == "local":
        task, receipt = execute(
            capability,
            payload,
            requester_node_id=record["requester_node_id"],
            constraints=constraints,
        )
        execution = {"task": task, "receipt": receipt}
    else:
        execution = request_task(
            selected["url"],
            capability,
            payload,
            constraints=constraints,
            requester_node_id=record["requester_node_id"],
        )

    receipt = execution.get("receipt") or {}
    return {
        "kind": "ghot.energy.result",
        "version": "0",
        "status": receipt.get("status", "unknown"),
        "energy_plan": record,
        "hold": None,
        "execution": execution,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Schedule a GHoT capability across place + power + time."
    )
    parser.add_argument("capability")
    parser.add_argument("payload", nargs="?", default=None)
    parser.add_argument(
        "--urgency",
        choices=sorted(URGENCIES),
        default="normal",
    )
    parser.add_argument("--deferrable", action="store_true")
    parser.add_argument("--data-node", default=None)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument(
        "--allow-background-battery",
        action="store_true",
        help="do not hold background heavy work merely waiting for favorable power",
    )
    parser.add_argument(
        "--hold-for-seconds",
        type=float,
        default=None,
        help="optional expiry for a HOLD; expired work is never started",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = schedule(
        args.capability,
        parse_payload(args.payload),
        urgency=args.urgency,
        deferrable=args.deferrable,
        data_node_id=args.data_node,
        timeout=args.timeout,
        prefer_surplus_for_background=not args.allow_background_battery,
        execute_now=not args.dry_run,
        hold_for_seconds=args.hold_for_seconds,
    )
    print(json.dumps(result, indent=2))

    if result["status"] in {"ok", "planned", "held"}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
