#!/usr/bin/env python3
"""GHoT Capability Composer — Experiments 004–006.

Discover local + known LAN bodies, filter by truthful capability and liveness,
apply explicit deterministic policy, persist the plan, then execute.
"""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from lan_node import discover_peers, request_task
from epistemic_policy import posture_matching_offers
from liveness_field import LivenessField
from reference_node import body, execute, node_id, now, persist


def parse_payload(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def offers_capability(body_record: dict[str, Any], capability: str) -> bool:
    for offer in body_record.get("offers", []):
        if (
            offer.get("capability") == capability
            and offer.get("available", False)
        ):
            return True
    return False


def candidate_view(candidate: dict[str, Any]) -> dict[str, Any]:
    body_record = candidate["body"]
    system = body_record.get("system") or {}
    power = body_record.get("power") or {}
    return {
        "node_id": candidate["node_id"],
        "location": candidate["location"],
        "url": candidate.get("url"),
        "hostname": system.get("hostname"),
        "architecture": system.get("architecture"),
        "memory_bytes": system.get("memory_bytes"),
        "battery_percent": power.get("battery_percent"),
        "charging": power.get("charging"),
        "power_source": power.get("source"),
        "renewable_surplus": power.get("renewable_surplus"),
        "temperature_c": power.get("temperature_c"),
        "thermal_state": power.get("thermal_state"),
        "load_per_cpu_1m": power.get("load_per_cpu_1m"),
        "power_willingness": power.get("willingness"),
        "power_willingness_reasons": power.get("willingness_reasons"),
        "field_state": candidate.get("field_state"),
        "last_seen": candidate.get("last_seen"),
        "age_seconds": candidate.get("age_seconds"),
        "consecutive_failures": candidate.get("consecutive_failures", 0),
        "quarantine_until": candidate.get("quarantine_until"),
    }


def memory_score(memory_bytes: Any) -> float:
    if not isinstance(memory_bytes, int) or memory_bytes <= 0:
        return 0.0
    gib = memory_bytes / (1024 ** 3)
    return min(gib, 64.0)


def evaluate_candidate(
    candidate: dict[str, Any],
    capability: str,
    *,
    min_battery: float | None,
    prefer_local: bool,
    prefer_plugged_in: bool,
    prefer_memory: bool,
    context_posture: str | None = None,
    excluded_node_ids: set[str] | None = None,
) -> dict[str, Any]:
    body_record = candidate["body"]
    power = body_record.get("power") or {}
    system = body_record.get("system") or {}
    reasons: list[str] = []
    rejected: list[str] = []
    score = 0.0

    excluded = excluded_node_ids or set()
    if candidate["node_id"] in excluded:
        rejected.append("excluded after earlier failed attempt")

    field_state = candidate.get("field_state")
    if field_state != "awake":
        rejected.append(f"body liveness state is {field_state or 'unknown'}, not awake")
    else:
        reasons.append("body is awake in liveness field")

    capability_offers, matching_offers = posture_matching_offers(
        body_record,
        capability,
        context_posture,
    )
    if not capability_offers:
        rejected.append("required capability not offered")
    elif context_posture is not None and not matching_offers:
        rejected.append(f"required context posture not offered: {context_posture}")
    elif not any(offer.get("available", False) for offer in matching_offers):
        power_reasons = []
        for offer in matching_offers:
            power_reasons.extend((offer.get("power") or {}).get("policy_reasons") or [])
        if power_reasons:
            rejected.append("required capability withdrawn: " + "; ".join(power_reasons))
        else:
            rejected.append("required capability currently unavailable")
    elif context_posture is not None:
        reasons.append(f"context posture matches: {context_posture}")

    battery = power.get("battery_percent")
    if min_battery is not None:
        if isinstance(battery, (int, float)):
            if battery < min_battery:
                rejected.append(
                    f"battery {battery}% below minimum {min_battery}%"
                )
            else:
                reasons.append(
                    f"battery {battery}% satisfies minimum {min_battery}%"
                )
        else:
            reasons.append("battery state unknown; minimum cannot be verified")

    if prefer_local and candidate["location"] == "local":
        score += 100.0
        reasons.append("+100 local-body preference")

    if power.get("willingness") == "abundant":
        reasons.append("power willingness is abundant")
    elif power.get("willingness") == "conserve":
        reasons.append("power willingness is conserve")
    elif power.get("willingness") == "critical":
        reasons.append("power willingness is critical")

    if prefer_plugged_in:
        charging = power.get("charging")
        source = str(power.get("source") or "").lower()
        if charging is True or source in {"ac", "mains", "grid", "usb", "solar"}:
            score += 30.0
            reasons.append("+30 powered/charging preference")
        elif charging is False:
            reasons.append("+0 powered preference: running on battery")
        else:
            reasons.append("+0 powered preference: power state unknown")

    if prefer_memory:
        points = memory_score(system.get("memory_bytes"))
        score += points
        if points:
            reasons.append(f"+{points:.2f} memory preference")
        else:
            reasons.append("+0 memory preference: memory unknown")

    return {
        **candidate_view(candidate),
        "eligible": not rejected,
        "score": round(score, 4),
        "reasons": reasons,
        "rejected": rejected,
    }


def gather_candidates(
    timeout: float,
    *,
    field: LivenessField | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    field_store = field or LivenessField()
    local_body = body()
    local_id = local_body["node_id"]

    observations: list[dict[str, Any]] = [{
        "node_id": local_id,
        "body": local_body,
        "url": None,
        "address": None,
    }]
    observations.extend(discover_peers(timeout))
    snapshot = field_store.refresh_observations(observations)

    candidates: list[dict[str, Any]] = []
    for entry in snapshot["bodies"]:
        body_record = entry.get("body") or {"node_id": entry["node_id"], "offers": []}
        candidates.append({
            "node_id": entry["node_id"],
            "location": "local" if entry["node_id"] == local_id else "remote",
            "url": entry.get("url"),
            "body": body_record,
            "field_state": entry.get("state"),
            "last_seen": entry.get("last_seen"),
            "age_seconds": entry.get("age_seconds"),
            "consecutive_failures": entry.get("consecutive_failures", 0),
            "quarantine_until": entry.get("quarantine_until"),
        })

    return candidates, snapshot


def compose_plan(
    capability: str,
    *,
    timeout: float = 2.0,
    min_battery: float | None = None,
    prefer_local: bool = True,
    prefer_plugged_in: bool = False,
    prefer_memory: bool = False,
    context_posture: str | None = None,
    excluded_node_ids: set[str] | None = None,
    composition_id: str | None = None,
    parent_plan_id: str | None = None,
    recomposition_reason: str | None = None,
    field: LivenessField | None = None,
) -> dict[str, Any]:
    excluded = excluded_node_ids or set()
    candidates, field_snapshot = gather_candidates(timeout, field=field)

    evaluated = [
        evaluate_candidate(
            candidate,
            capability,
            min_battery=min_battery,
            prefer_local=prefer_local,
            prefer_plugged_in=prefer_plugged_in,
            prefer_memory=prefer_memory,
            context_posture=context_posture,
            excluded_node_ids=excluded,
        )
        for candidate in candidates
    ]

    eligible = [candidate for candidate in evaluated if candidate["eligible"]]
    eligible.sort(key=lambda item: (-item["score"], item["node_id"]))

    selected = eligible[0] if eligible else None
    if selected is not None:
        selected = {
            **selected,
            "why_selected": (
                [
                    f"highest deterministic score among {len(eligible)} eligible body/bodies",
                    "ties resolve by node_id for reproducibility",
                ]
                + selected["reasons"]
            ),
        }

    plan = {
        "kind": "ghot.plan",
        "version": "0",
        "plan_id": f"plan-{uuid.uuid4()}",
        "composition_id": composition_id,
        "parent_plan_id": parent_plan_id,
        "recomposition_reason": recomposition_reason,
        "created_at": now(),
        "requester_node_id": node_id(),
        "capability": capability,
        "constraints": {
            "min_battery_percent": min_battery,
            "required_liveness_state": "awake",
            "context_posture": context_posture,
        },
        "preferences": {
            "prefer_local": prefer_local,
            "prefer_plugged_in": prefer_plugged_in,
            "prefer_memory": prefer_memory,
        },
        "field_policy": field_snapshot.get("policy") or {},
        "excluded_node_ids": sorted(excluded),
        "candidates": evaluated,
        "selected": selected,
    }
    persist("plan", plan)
    return plan


def execute_plan(
    plan: dict[str, Any],
    payload: Any,
) -> dict[str, Any]:
    selected = plan.get("selected")
    if not selected:
        return {
            "kind": "ghot.composition.result",
            "version": "0",
            "plan": plan,
            "status": "no-eligible-body",
            "execution": None,
        }

    crossing_constraints = {
        **(plan.get("constraints") or {}),
        "composition_id": plan.get("composition_id"),
        "plan_id": plan["plan_id"],
        "selected_node_id": selected["node_id"],
        "selected_field_state": selected.get("field_state"),
        "why_selected": selected["why_selected"],
    }

    if selected["location"] == "local":
        task, receipt = execute(
            plan["capability"],
            payload,
            requester_node_id=plan["requester_node_id"],
            constraints=crossing_constraints,
        )
        execution = {"task": task, "receipt": receipt}
    else:
        url = selected.get("url")
        if not url:
            return {
                "kind": "ghot.composition.result",
                "version": "0",
                "plan": plan,
                "status": "selected-body-has-no-route",
                "execution": None,
            }
        execution = request_task(
            url,
            plan["capability"],
            payload,
            constraints=crossing_constraints,
            requester_node_id=plan["requester_node_id"],
        )

    receipt = execution.get("receipt") or {}
    return {
        "kind": "ghot.composition.result",
        "version": "0",
        "plan": plan,
        "status": receipt.get("status", "unknown"),
        "execution": execution,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compose a capability request across available GHoT bodies."
    )
    parser.add_argument("capability")
    parser.add_argument("payload", nargs="?", default=None)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--min-battery", type=float, default=None)
    parser.add_argument(
        "--no-prefer-local",
        action="store_true",
        help="remove the default locality preference",
    )
    parser.add_argument("--prefer-plugged-in", action="store_true")
    parser.add_argument("--prefer-memory", action="store_true")
    parser.add_argument(
        "--context-posture",
        choices=["fresh", "bounded-window", "lineage-enabled", "owner-local"],
        default=None,
        help="require an offer with this explicit epistemic context posture",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan = compose_plan(
        args.capability,
        timeout=args.timeout,
        min_battery=args.min_battery,
        prefer_local=not args.no_prefer_local,
        prefer_plugged_in=args.prefer_plugged_in,
        prefer_memory=args.prefer_memory,
        context_posture=args.context_posture,
    )

    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0 if plan.get("selected") else 1

    result = execute_plan(plan, parse_payload(args.payload))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
