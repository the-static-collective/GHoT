#!/usr/bin/env python3
"""Lightwalker Transition-Aware Execution Gate / Durable Enforcement 001.

Execution recomputes temporal policy state from source evidence at the exact
execution cut. A prior decision is not authority. Exactly one bounded evidence
path may satisfy the gate: fresh legacy permission, current revalidation, or a
verified migration to a distinct current reservation.

Core laws:
    DECISION != ENFORCEMENT
    STALE TEMPORAL INTERSECTION != CURRENT AUTHORITY
    LEGACY PERMISSION MUST BE PROVEN AT EXECUTION TIME
    REVALIDATION RECEIPT != MIGRATION RECEIPT
    NO COMMON PATH != EXECUTION AUTHORITY
    ENFORCEMENT MUST RECOMPUTE FROM SOURCE EVIDENCE
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_finalization,
    verify_reservation,
)
from lightwalker_policy_transition import (
    derive_transition_decision,
    make_migration_receipt,
)
from lightwalker_policy_versioning import (
    derive_active_policy_set,
    verify_revalidation,
)
from lightwalker_transition_composition import (
    derive_temporal_intersection,
)


GATE_KIND = "ghot.lightwalker.transition-aware-execution-gate"
GATE_VERSION = "0"


def _nni(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(
            f"{name} must be a non-negative integer"
        )
    return value


def _recompute_policy_set(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    *,
    policies: list[dict[str, Any]],
    versions: list[dict[str, Any]],
    supplied: dict[str, Any],
    observed_cut: int,
) -> dict[str, Any]:
    expected = derive_active_policy_set(
        promise,
        route_policy,
        policies,
        versions,
        observed_cut=observed_cut,
    )
    if expected != supplied:
        raise LightwalkerEconomyError(
            "policy set is stale or does not recompute from source evidence"
        )
    return expected


def _verify_current_revalidation(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    reservation: dict[str, Any],
    context: dict[str, Any],
    *,
    observed_cut: int,
) -> str:
    required = {
        "policies",
        "versions",
        "previous_policy_set",
        "current_policy_set",
        "candidate",
        "measurements",
        "attestations",
        "prior_binding_id",
        "prior_admission_response_id",
        "revalidation",
    }
    if not required.issubset(context):
        raise LightwalkerEconomyError(
            "revalidation evidence context is incomplete"
        )
    previous = context["previous_policy_set"]
    current = context["current_policy_set"]
    _recompute_policy_set(
        promise,
        route_policy,
        policies=context["policies"],
        versions=context["versions"],
        supplied=previous,
        observed_cut=int(previous["observed_cut"]),
    )
    _recompute_policy_set(
        promise,
        route_policy,
        policies=context["policies"],
        versions=context["versions"],
        supplied=current,
        observed_cut=observed_cut,
    )
    revalidation = context["revalidation"]
    if int(revalidation.get("evaluated_at_cut", -1)) != observed_cut:
        raise LightwalkerEconomyError(
            "revalidation receipt is stale at execution time"
        )
    if not verify_revalidation(
        promise,
        route_policy,
        previous_policy_set=previous,
        current_policy_set=current,
        policies=context["policies"],
        candidate=context["candidate"],
        measurements=context["measurements"],
        attestations=context["attestations"],
        reservation=reservation,
        prior_binding_id=context["prior_binding_id"],
        prior_admission_response_id=context[
            "prior_admission_response_id"
        ],
        revalidation=revalidation,
    ):
        raise LightwalkerEconomyError(
            "revalidation receipt does not recompute"
        )
    if revalidation.get("status") != "COMPLIANT":
        raise LightwalkerEconomyError(
            "current revalidation is noncompliant"
        )
    if revalidation.get("future_execution_permitted") is not True:
        raise LightwalkerEconomyError(
            "current revalidation does not permit execution"
        )
    return revalidation["revalidation_id"]


def _verify_current_migration(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    bundles: list[dict[str, Any]],
    old_reservation: dict[str, Any],
    new_reservation: dict[str, Any],
    context: dict[str, Any],
    *,
    observed_cut: int,
    execution_started_at_cut: int | None,
) -> tuple[str, str]:
    required = {
        "policies",
        "versions",
        "current_policy_set",
        "transition",
        "old_finalization",
        "migration_receipt",
    }
    if not required.issubset(context):
        raise LightwalkerEconomyError(
            "migration evidence context is incomplete"
        )
    current = context["current_policy_set"]
    _recompute_policy_set(
        promise,
        route_policy,
        policies=context["policies"],
        versions=context["versions"],
        supplied=current,
        observed_cut=observed_cut,
    )

    transition = context["transition"]
    bundle = next(
        (
            item
            for item in bundles
            if item["transition"]["transition_id"]
            == transition.get("transition_id")
        ),
        None,
    )
    if bundle is None:
        raise LightwalkerEconomyError(
            "migration transition is not part of current temporal composition"
        )
    if transition.get("mode") != "MIGRATE_BEFORE_EXECUTION":
        raise LightwalkerEconomyError(
            "migration evidence references non-migration transition"
        )

    old_finalization = context["old_finalization"]
    if not verify_finalization(
        old_reservation, old_finalization
    ):
        raise LightwalkerEconomyError(
            "old reservation finalization is invalid"
        )
    if old_finalization.get("status") != "RELEASED":
        raise LightwalkerEconomyError(
            "migration requires released old reservation"
        )

    decision = derive_transition_decision(
        transition,
        old_reservation,
        observed_cut=observed_cut,
        execution_started_at_cut=execution_started_at_cut,
    )
    expected = make_migration_receipt(
        transition,
        decision,
        old_reservation=old_reservation,
        old_finalization=old_finalization,
        new_reservation=new_reservation,
        current_policy_set_id=current["policy_set_id"],
    )
    supplied = context["migration_receipt"]
    if expected != supplied:
        raise LightwalkerEconomyError(
            "migration receipt does not recompute from source evidence"
        )
    if supplied.get("new_reservation_id") != new_reservation["reservation_id"]:
        raise LightwalkerEconomyError(
            "migration receipt does not name execution reservation"
        )
    return supplied["migration_id"], current["policy_set_id"]


def derive_execution_gate(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    bundles: list[dict[str, Any]],
    transition_subject_reservation: dict[str, Any],
    execution_reservation: dict[str, Any],
    supplied_temporal_intersection: dict[str, Any],
    *,
    observed_cut: int,
    execution_started_at_cut: int | None = None,
    revalidation_context: dict[str, Any] | None = None,
    migration_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cut = _nni(observed_cut, "observed_cut")
    current = derive_temporal_intersection(
        promise,
        route_policy,
        bundles,
        transition_subject_reservation,
        observed_cut=cut,
        execution_started_at_cut=execution_started_at_cut,
    )
    if current != supplied_temporal_intersection:
        raise LightwalkerEconomyError(
            "temporal intersection is stale or does not recompute at execution cut"
        )
    if int(current["observed_cut"]) != cut:
        raise LightwalkerEconomyError(
            "temporal intersection does not match execution cut"
        )

    action = current["aggregate_action"]
    revalidation_id = None
    migration_id = None
    current_policy_set_id = None

    if action == "LEGACY_PATH_OPEN":
        if execution_reservation["reservation_id"] != (
            transition_subject_reservation["reservation_id"]
        ):
            raise LightwalkerEconomyError(
                "legacy path may not silently substitute reservation"
            )
        if revalidation_context is not None or migration_context is not None:
            raise LightwalkerEconomyError(
                "legacy path may not mix incompatible evidence types"
            )
        evidence_path = "FRESH_LEGACY_PERMISSION"

    elif action == "REVALIDATION_REQUIRED":
        if execution_reservation["reservation_id"] != (
            transition_subject_reservation["reservation_id"]
        ):
            raise LightwalkerEconomyError(
                "revalidation path may not silently substitute reservation"
            )
        if revalidation_context is None:
            raise LightwalkerEconomyError(
                "current revalidation evidence is required"
            )
        if migration_context is not None:
            raise LightwalkerEconomyError(
                "revalidation receipt is not migration evidence"
            )
        revalidation_id = _verify_current_revalidation(
            promise,
            route_policy,
            execution_reservation,
            revalidation_context,
            observed_cut=cut,
        )
        current_policy_set_id = revalidation_context[
            "current_policy_set"
        ]["policy_set_id"]
        evidence_path = "CURRENT_REVALIDATION"

    elif action == "MIGRATION_REQUIRED":
        if migration_context is None:
            raise LightwalkerEconomyError(
                "current migration evidence is required"
            )
        if revalidation_context is not None:
            raise LightwalkerEconomyError(
                "migration receipt is not revalidation evidence"
            )
        if execution_reservation["reservation_id"] == (
            transition_subject_reservation["reservation_id"]
        ):
            raise LightwalkerEconomyError(
                "migration requires a distinct current reservation"
            )
        migration_id, current_policy_set_id = _verify_current_migration(
            promise,
            route_policy,
            bundles,
            transition_subject_reservation,
            execution_reservation,
            migration_context,
            observed_cut=cut,
            execution_started_at_cut=execution_started_at_cut,
        )
        evidence_path = "VERIFIED_MIGRATION"

    elif action == "NO_COMMON_TRANSITION_PATH":
        raise LightwalkerEconomyError(
            "no common temporal path can authorize execution"
        )
    else:
        raise LightwalkerEconomyError(
            "unsupported temporal execution action"
        )

    body = {
        "kind": GATE_KIND,
        "version": GATE_VERSION,
        "authority": "derived-execution-prerequisite-only",
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "temporal_intersection_id": current[
            "temporal_intersection_id"
        ],
        "transition_subject_reservation_id": (
            transition_subject_reservation["reservation_id"]
        ),
        "execution_reservation_id": execution_reservation[
            "reservation_id"
        ],
        "observed_cut": cut,
        "aggregate_action": action,
        "evidence_path": evidence_path,
        "revalidation_id": revalidation_id,
        "migration_id": migration_id,
        "current_policy_set_id": current_policy_set_id,
        "permitted": True,
        "source_evidence_recomputed": True,
        "temporal_freshness_required": True,
        "reservation_authority": "none",
        "execution_authority": "none",
        "laws": [
            "DECISION != ENFORCEMENT",
            "STALE TEMPORAL INTERSECTION != CURRENT AUTHORITY",
            "LEGACY PERMISSION MUST BE PROVEN AT EXECUTION TIME",
            "REVALIDATION RECEIPT != MIGRATION RECEIPT",
            "NO COMMON PATH != EXECUTION AUTHORITY",
            "ENFORCEMENT MUST RECOMPUTE FROM SOURCE EVIDENCE",
        ],
    }
    return {**body, "execution_gate_id": content_address(body)}


def execute_with_transition_gate(
    store: GuildReservationStore,
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    execution_reservation: dict[str, Any],
    *,
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    bundles: list[dict[str, Any]],
    transition_subject_reservation: dict[str, Any],
    supplied_temporal_intersection: dict[str, Any],
    executor: Any,
    observed_cut: int,
    simulate_success: bool,
    execution_started_at_cut: int | None = None,
    revalidation_context: dict[str, Any] | None = None,
    migration_context: dict[str, Any] | None = None,
    result_ref: str | None = None,
    error: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not verify_reservation(
        snapshot,
        proposal,
        authorization,
        execution_reservation,
    ):
        raise LightwalkerEconomyError(
            "execution reservation is invalid"
        )

    gate = derive_execution_gate(
        promise,
        route_policy,
        bundles,
        transition_subject_reservation,
        execution_reservation,
        supplied_temporal_intersection,
        observed_cut=observed_cut,
        execution_started_at_cut=execution_started_at_cut,
        revalidation_context=revalidation_context,
        migration_context=migration_context,
    )
    if gate.get("permitted") is not True:
        raise LightwalkerEconomyError(
            "transition-aware execution gate did not permit execution"
        )

    receipt, finalization = store.execute_reserved(
        snapshot,
        proposal,
        authorization,
        execution_reservation,
        executor=executor,
        observed_cut=observed_cut,
        simulate_success=simulate_success,
        result_ref=result_ref,
        error=error,
    )
    return gate, receipt, finalization


__all__ = [
    "derive_execution_gate",
    "execute_with_transition_gate",
]
