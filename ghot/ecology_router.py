"""ECOLOGY ROUTER 001: GHoT's inert multi-resource field planner.

A proposal-only adapter for KETTLENODE-001/002, orchard sensor particulars,
marine power candidates and salvage infrastructure. No hardware control and
no reLATTE signing. Consumes no real source capacity.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

SCHEMA = "ghot.ecology-field/v0"
PLAN = "ghot.ecology-plan/v0"
RESOURCES = {
    "electricity": "mWh",
    "heat": "J",
    "freshwater": "mL",
    "nutrients": "mg",
    "information": "events",
    "materials": "g",
}
PRIORITIES = {"life-support": 0, "essential": 1, "optional": 2}
CAP = 10**12


class Hold(ValueError):
    """No allocation was authorized or physically executed."""


def require(test: bool, message: str) -> None:
    if not test:
        raise Hold(message)


def integer(value: Any, label: str, minimum: int = 0) -> int:
    require(type(value) is int and minimum <= value <= CAP, f"invalid {label}")
    return value


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate(world: Any) -> dict:
    require(isinstance(world, dict) and set(world) == {
        "schema", "mode", "step", "sources", "loads", "paths"
    }, "world fields changed")
    require(world["schema"] == SCHEMA and world["mode"] == "simulation-only",
            "only simulation world supported")
    step = integer(world["step"], "step")
    ids = {"sources": set(), "loads": set(), "paths": set()}
    for key in ids:
        require(isinstance(world[key], list), f"{key} must be a list")
        for row in world[key]:
            require(isinstance(row, dict) and isinstance(row.get("id"), str)
                    and bool(row["id"]) and row["id"] not in ids[key],
                    f"invalid or duplicate {key} identity")
            ids[key].add(row["id"])
    for row in world["sources"]:
        require(set(row) == {
            "id", "node", "resource", "unit", "available_units",
            "reserved_units", "evidence", "fresh_until_step", "status",
        }, "source fields changed")
        require(isinstance(row["node"], str) and bool(row["node"]), "source node required")
        require(row["resource"] in RESOURCES and
                row["unit"] == RESOURCES[row["resource"]], "invalid source units")
        available = integer(row["available_units"], "source supply")
        reserved = integer(row["reserved_units"], "source reserve")
        require(reserved <= available, "reserve exceeds source supply")
        integer(row["fresh_until_step"], "freshness")
        require(row["evidence"] in {"synthetic-scenario", "unverified-observation"},
                "unearned evidence class")
        require(row["status"] in {"available", "quarantined"}, "source status invalid")
    for row in world["loads"]:
        require(set(row) == {
            "id", "node", "resource", "unit", "demand_units",
            "priority", "selected_by_owner", "status",
        }, "load fields changed")
        require(isinstance(row["node"], str) and bool(row["node"]), "load node required")
        require(row["resource"] in RESOURCES and
                row["unit"] == RESOURCES[row["resource"]], "invalid load units")
        integer(row["demand_units"], "demand", 1)
        require(row["priority"] in PRIORITIES and
                row["status"] in {"requested", "cancelled"} and
                type(row["selected_by_owner"]) is bool, "invalid load policy")
    for row in world["paths"]:
        require(set(row) == {
            "id", "from", "to", "resource", "unit", "limit_units",
            "isolation_ok", "permit_ok", "environment_ok",
            "owner_reviewed", "status",
        }, "path fields changed")
        require(row["from"] in ids["sources"] and row["to"] in ids["loads"],
                "dangling source or destination")
        require(row["resource"] in RESOURCES and
                row["unit"] == RESOURCES[row["resource"]], "invalid path units")
        integer(row["limit_units"], "path capacity", 1)
        require(all(type(row[field]) is bool for field in
                    ("isolation_ok", "permit_ok", "environment_ok", "owner_reviewed")),
                "invalid path flags")
        require(row["status"] in {"offered", "withdrawn"}, "invalid path status")
    return world


def plan(world: dict[str, Any]) -> dict[str, Any]:
    """Produce inspectable simulations only. No selection is physically enforced.

    Exact typed resource units; no implicit heat->electricity conversion.
    Protect life support before optional work within each resource domain.
    Unverified sources never contribute simulated available capacity.
    """
    validate(world)
    sources = {x["id"]: x for x in world["sources"]}
    remaining = {x["id"]: x["available_units"] - x["reserved_units"]
                 for x in world["sources"]}
    path_remaining = {x["id"]: x["limit_units"] for x in world["paths"]}
    rows: list[dict[str, Any]] = []
    critical_holds: set[str] = set()
    loads = sorted(world["loads"], key=lambda x: (
        PRIORITIES[x["priority"]], x["resource"], x["id"]))

    for load in loads:
        reasons = []
        if load["status"] != "requested":
            reasons.append("LOAD_NOT_REQUESTED")
        if not load["selected_by_owner"]:
            reasons.append("NO_EXPLICIT_OWNER_SELECTION")
        if load["priority"] != "life-support" and load["resource"] in critical_holds:
            reasons.append("LIFE_SUPPORT_UNFUNDED")

        eligible = []
        for path in sorted(world["paths"], key=lambda x: x["id"]):
            if path["to"] != load["id"]:
                continue
            source = sources[path["from"]]
            problems = []
            if (source["resource"] != load["resource"] or
                source["unit"] != load["unit"] or
                path["resource"] != load["resource"] or
                path["unit"] != load["unit"]):
                problems.append("RESOURCE_OR_UNIT_MISMATCH")
            if source["status"] != "available" or path["status"] != "offered":
                problems.append("SOURCE_OR_ROUTE_WITHDRAWN")
            if source["evidence"] != "synthetic-scenario":
                problems.append("UNVERIFIED_RESOURCE")
            if source["fresh_until_step"] < world["step"]:
                problems.append("STALE_SOURCE")
            for flag, code in (
                ("isolation_ok", "ISOLATION_NOT_PROVEN"),
                ("permit_ok", "PERMIT_UNRESOLVED"),
                ("environment_ok", "ENVIRONMENT_UNSAFE"),
                ("owner_reviewed", "OWNER_REVIEW_MISSING"),
            ):
                if path[flag] is not True:
                    problems.append(code)
            if remaining[source["id"]] < load["demand_units"]:
                problems.append("INSUFFICIENT_UNRESERVED_SUPPLY")
            if path_remaining[path["id"]] < load["demand_units"]:
                problems.append("PATH_CAPACITY_EXCEEDED")
            if problems:
                reasons.extend(problems)
            else:
                eligible.append((source, path))

        if eligible and not reasons[:1]:
            # Lexical, explainable and NOT a physically optimal objective.
            source, path = sorted(eligible, key=lambda pair: (
                -remaining[pair[0]["id"]], pair[1]["id"]))[0]
            demand = load["demand_units"]
            remaining[source["id"]] -= demand
            path_remaining[path["id"]] -= demand
            rows.append({
                "load_id": load["id"], "decision": "PROPOSE",
                "source_id": source["id"], "path_id": path["id"],
                "resource": load["resource"], "unit": load["unit"],
                "proposed_units": demand, "reasons": [
                    "OWNER_SELECTED", "SIMULATED_CAPACITY", "CONSTRAINTS_ELIGIBLE",
                ],
            })
        else:
            if load["priority"] == "life-support" and load["status"] == "requested":
                critical_holds.add(load["resource"])
            rows.append({
                "load_id": load["id"], "decision": "HOLD",
                "source_id": None, "path_id": None,
                "resource": load["resource"], "unit": load["unit"],
                "proposed_units": 0,
                "reasons": sorted(set(reasons)) or ["NO_ROUTE_OFFERED"],
            })
    return {
        "schema": PLAN,
        "world_sha256": digest(world),
        "mode": "simulation-only",
        "proposals": rows,
        "remaining_supply": remaining,
        "physical_effects": False,
        "owner_admission": False,
        "signed_crossing": False,
        "automatic_dispatch": False,
        "receipts": [],
    }


def cold_replay(world: dict[str, Any]) -> bool:
    """Verify deterministic planning without mutating the observed world."""
    snapshot = deepcopy(world)
    a = plan(snapshot)
    b = plan(deepcopy(world))
    require(snapshot == world, "planner mutated source world")
    require(a == b, "nondeterministic proposals")
    return True
