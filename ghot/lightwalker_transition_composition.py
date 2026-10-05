#!/usr/bin/env python3
"""Lightwalker Multi-Policy Transition Composition 001.

Independent policy transitions remain independent. Their temporal decisions are
intersected without rewriting source modes. A legacy execution path remains
open only if every active transition permits it.

Core laws:
    TRANSITION A != TRANSITION B
    TEMPORAL INTERSECTION != MODE REWRITE
    GRACE IN ONE POLICY != GRACE IN ALL POLICIES
    ONE IMMEDIATE REQUIREMENT MAY CLOSE THE LEGACY PATH
    NO COMMON TRANSITION PATH != PERMISSION TO INVENT ONE
    TEMPORAL PROVENANCE MUST SURVIVE COMPOSITION
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_policy_transition import (
    derive_transition_decision,
    verify_policy_transition,
)


INTERSECTION_KIND = "ghot.lightwalker.temporal-policy-intersection"
INTERSECTION_VERSION = "0"


def _nni(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(
            f"{name} must be a non-negative integer"
        )
    return value


def _validate_bundle(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    bundle: dict[str, Any],
) -> None:
    required = {
        "issuer_role",
        "previous_version",
        "current_version",
        "transition",
    }
    if not required.issubset(bundle):
        raise LightwalkerEconomyError(
            "transition bundle is incomplete"
        )
    if not isinstance(bundle["issuer_role"], str) or not bundle["issuer_role"]:
        raise LightwalkerEconomyError(
            "transition bundle issuer_role must be non-empty"
        )
    if not verify_policy_transition(
        promise,
        route_policy,
        bundle["previous_version"],
        bundle["current_version"],
        bundle["transition"],
    ):
        raise LightwalkerEconomyError(
            "invalid transition in composition"
        )


def derive_temporal_intersection(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    bundles: list[dict[str, Any]],
    reservation: dict[str, Any],
    *,
    observed_cut: int,
    execution_started_at_cut: int | None = None,
) -> dict[str, Any]:
    if len(bundles) < 2:
        raise LightwalkerEconomyError(
            "temporal composition requires at least two transitions"
        )
    cut = _nni(observed_cut, "observed_cut")
    seen_transition_ids: set[str] = set()
    seen_lineages: set[str] = set()
    provenance: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    for bundle in bundles:
        _validate_bundle(promise, route_policy, bundle)
        transition = bundle["transition"]
        transition_id = transition["transition_id"]
        lineage_id = transition["lineage_id"]
        if transition_id in seen_transition_ids:
            raise LightwalkerEconomyError(
                "duplicate transition in temporal composition"
            )
        if lineage_id in seen_lineages:
            raise LightwalkerEconomyError(
                "multiple transitions from same policy lineage"
            )
        seen_transition_ids.add(transition_id)
        seen_lineages.add(lineage_id)

        decision = derive_transition_decision(
            transition,
            reservation,
            observed_cut=cut,
            execution_started_at_cut=execution_started_at_cut,
        )
        decisions.append(decision)
        provenance.append({
            "issuer_role": bundle["issuer_role"],
            "issuer_particular": transition["issuer_particular"],
            "lineage_id": lineage_id,
            "previous_policy_version_id": transition[
                "previous_policy_version_id"
            ],
            "current_policy_version_id": transition[
                "current_policy_version_id"
            ],
            "transition_id": transition_id,
            "mode": transition["mode"],
            "decision_id": decision["decision_id"],
            "individual_action": decision["action"],
            "individual_legacy_path_open": decision[
                "legacy_path_open"
            ],
            "individual_revalidation_required": decision[
                "revalidation_required"
            ],
            "individual_migration_required": decision[
                "migration_required"
            ],
            "individual_enforcement_deferred_until_cut": decision[
                "enforcement_deferred_until_cut"
            ],
        })

    execution_started = (
        None
        if execution_started_at_cut is None
        else _nni(execution_started_at_cut, "execution_started_at_cut")
    )
    migration_decisions = [
        decision for decision in decisions
        if decision["migration_required"]
    ]
    revalidation_decisions = [
        decision for decision in decisions
        if decision["revalidation_required"]
    ]
    legacy_decisions = [
        decision for decision in decisions
        if decision["legacy_path_open"]
    ]

    conflicts: list[str] = []
    if migration_decisions and execution_started is not None:
        for decision in migration_decisions:
            effective = next(
                bundle["transition"]["current_effective_from_cut"]
                for bundle in bundles
                if bundle["transition"]["transition_id"]
                == decision["transition_id"]
            )
            if execution_started < int(effective):
                conflicts.append(
                    "MIGRATION_BEFORE_EXECUTION_COLLIDES_WITH_ALREADY_STARTED_WORK"
                )
                break

    if conflicts:
        result = "NO_COMMON_TRANSITION_PATH"
        aggregate_action = "NO_COMMON_TRANSITION_PATH"
        legacy_path_open = False
        revalidation_required = False
        migration_required = False
        enforcement_deferred_until_cut = None
    elif migration_decisions:
        result = "COMMON_PATH"
        aggregate_action = "MIGRATION_REQUIRED"
        legacy_path_open = False
        revalidation_required = bool(revalidation_decisions)
        migration_required = True
        enforcement_deferred_until_cut = None
    elif revalidation_decisions:
        result = "COMMON_PATH"
        aggregate_action = "REVALIDATION_REQUIRED"
        legacy_path_open = False
        revalidation_required = True
        migration_required = False
        enforcement_deferred_until_cut = None
    elif len(legacy_decisions) == len(decisions):
        result = "COMMON_PATH"
        aggregate_action = "LEGACY_PATH_OPEN"
        legacy_path_open = True
        revalidation_required = False
        migration_required = False
        bounds = [
            int(decision["enforcement_deferred_until_cut"])
            for decision in decisions
            if decision["enforcement_deferred_until_cut"] is not None
        ]
        enforcement_deferred_until_cut = (
            min(bounds) if bounds else None
        )
    else:
        result = "NO_COMMON_TRANSITION_PATH"
        aggregate_action = "NO_COMMON_TRANSITION_PATH"
        legacy_path_open = False
        revalidation_required = False
        migration_required = False
        enforcement_deferred_until_cut = None
        conflicts.append("NO_SHARED_TEMPORAL_ACTION")

    blocking_transition_ids = sorted(
        decision["transition_id"]
        for decision in decisions
        if not decision["legacy_path_open"]
    )
    body = {
        "kind": INTERSECTION_KIND,
        "version": INTERSECTION_VERSION,
        "authority": "derived-temporal-intersection-only",
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "reservation_id": reservation["reservation_id"],
        "observed_cut": cut,
        "execution_started_at_cut": execution_started_at_cut,
        "transition_ids": sorted(seen_transition_ids),
        "temporal_provenance": sorted(
            provenance,
            key=lambda row: (
                row["issuer_role"],
                row["transition_id"],
            ),
        ),
        "result": result,
        "aggregate_action": aggregate_action,
        "legacy_path_open": legacy_path_open,
        "revalidation_required": revalidation_required,
        "migration_required": migration_required,
        "enforcement_deferred_until_cut": (
            enforcement_deferred_until_cut
        ),
        "blocking_transition_ids": blocking_transition_ids,
        "conflicts": sorted(set(conflicts)),
        "source_transitions_rewritten": False,
        "mode_override_authority": "none",
        "relaxation_authority": "none",
        "reservation_authority": "none",
        "execution_authority": "none",
        "laws": [
            "TRANSITION A != TRANSITION B",
            "TEMPORAL INTERSECTION != MODE REWRITE",
            "GRACE IN ONE POLICY != GRACE IN ALL POLICIES",
            "ONE IMMEDIATE REQUIREMENT MAY CLOSE THE LEGACY PATH",
            "NO COMMON TRANSITION PATH != PERMISSION TO INVENT ONE",
            "TEMPORAL PROVENANCE MUST SURVIVE COMPOSITION",
        ],
    }
    return {
        **body,
        "temporal_intersection_id": content_address(body),
    }


def verify_temporal_intersection(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    bundles: list[dict[str, Any]],
    reservation: dict[str, Any],
    intersection: dict[str, Any],
) -> bool:
    try:
        expected = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            reservation,
            observed_cut=int(intersection["observed_cut"]),
            execution_started_at_cut=intersection[
                "execution_started_at_cut"
            ],
        )
        return expected == intersection
    except Exception:
        return False


__all__ = [
    "derive_temporal_intersection",
    "verify_temporal_intersection",
]
