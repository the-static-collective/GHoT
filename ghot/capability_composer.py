#!/usr/bin/env python3
"""GHoT Capability Composer — Experiment 004.

Discover local + LAN bodies, select an eligible executor for a requested
capability using explicit deterministic policy, persist the plan, then execute.

Examples:
    python3 ghot/capability_composer.py system.hash "hello heap" --dry-run
    python3 ghot/capability_composer.py runtime.ffmpeg.version --prefer-memory
    python3 ghot/capability_composer.py system.hash "hello" --min-battery 25
"""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from lan_node import discover_peers, request_task
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
) -> dict[str, Any]:
    body_record = candidate["body"]
    power = body_record.get("power") or {}
    system = body_record.get("system") or {}
    reasons: list[str] = []
    rejected: list[str] = []
    score = 0.0

    if not offers_capability(body_record, capability):
        rejected.append("required capability not offered")

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


def gather_candidates(timeout: float) -> list[dict[str, Any]]:
    local_body = body()
    local_id = local_body["node_id"]

    candidates: list[dict[str, Any]] = [{
        "node_id": local_id,
        "location": "local",
        "url": None,
        "body": local_body,
    }]

    seen = {local_id}
    for peer in discover_peers(timeout):
        peer_body = peer.get("body") or {}
        peer_id = peer.get("node_id") or peer_body.get("node_id")
        if not peer_id or peer_id in seen:
            continue
        seen.add(peer_id)
        candidates.append({
            "node_id": peer_id,
            "location": "remote",
            "url": peer.get("url"),
            "body": peer_body,
        })

    return candidates


def compose_plan(
    capability: str,
    *,
    timeout: float = 2.0,
    min_battery: float | None = None,
    prefer_local: bool = True,
    prefer_plugged_in: bool = False,
    prefer_memory: bool = False,
) -> dict[str, Any]:
    evaluated = [
        evaluate_candidate(
            candidate,
            capability,
            min_battery=min_battery,
            prefer_local=prefer_local,
            prefer_plugged_in=prefer_plugged_in,
            prefer_memory=prefer_memory,
        )
        for candidate in gather_candidates(timeout)
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
        "created_at": now(),
        "requester_node_id": node_id(),
        "capability": capability,
        "constraints": {
            "min_battery_percent": min_battery,
        },
        "preferences": {
            "prefer_local": prefer_local,
            "prefer_plugged_in": prefer_plugged_in,
            "prefer_memory": prefer_memory,
        },
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
        "plan_id": plan["plan_id"],
        "selected_node_id": selected["node_id"],
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan = compose_plan(
        args.capability,
        timeout=args.timeout,
        min_battery=args.min_battery,
        prefer_local=not args.no_prefer_local,
        prefer_plugged_in=args.prefer_plugged_in,
        prefer_memory=args.prefer_memory,
    )

    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0 if plan.get("selected") else 1

    result = execute_plan(plan, parse_payload(args.payload))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
