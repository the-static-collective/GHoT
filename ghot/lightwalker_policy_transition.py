#!/usr/bin/env python3
"""Lightwalker Policy Transition Modes / Grace / Migration 001.

A policy version may declare explicit temporal transition semantics. Transition
mode governs when current-policy enforcement applies to already-existing work;
it does not alter policy content or resource-owner authority.

Core laws:
    TRANSITION MODE != POLICY CONTENT
    GRACE != PERMANENT EXEMPTION
    IN-FLIGHT != UNBOUNDED GRANDFATHERING
    MIGRATION != HISTORY REWRITE
    POLICY ISSUER != RESOURCE OWNER
    DEFERRED ENFORCEMENT != ABSENT ENFORCEMENT
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_policy_versioning import verify_policy_version
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


TRANSITION_KIND = "ghot.lightwalker.policy-transition"
TRANSITION_VERSION = "0"
DECISION_KIND = "ghot.lightwalker.policy-transition-decision"
DECISION_VERSION = "0"
MIGRATION_KIND = "ghot.lightwalker.policy-transition-migration"
MIGRATION_VERSION = "0"

TRANSITION_DOMAIN = "ghot.lightwalker-policy-transition-signature/v0"
TRANSITION_BYTES = b"GHOT-LightwalkerPolicyTransition-v0|"

MODES = {
    "IMMEDIATE_REVALIDATION",
    "GRACE_UNTIL_CUT",
    "FINISH_IN_FLIGHT_ONLY",
    "NEW_WORK_ONLY",
    "MIGRATE_BEFORE_EXECUTION",
}


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nni(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(
            f"{name} must be a non-negative integer"
        )
    return value


def _signed(
    body: dict[str, Any],
    *,
    id_field: str,
    signer: IdentityKey,
    domain: str,
    byte_domain: bytes,
) -> dict[str, Any]:
    item_id = content_address(body)
    value = {
        **body,
        id_field: item_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": domain,
        },
    }
    value["signing"]["signature"] = signer.sign(
        byte_domain + canonical_bytes({id_field: item_id, **body})
    )
    return value


def _verify_signed(
    value: dict[str, Any],
    *,
    id_field: str,
    particular_field: str,
    domain: str,
    byte_domain: bytes,
) -> bool:
    try:
        signing = value.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != domain:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != value.get(
            particular_field
        ):
            return False
        body = {
            key: item
            for key, item in value.items()
            if key not in {id_field, "signing"}
        }
        item_id = value.get(id_field)
        if not isinstance(item_id, str) or content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            byte_domain
            + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def make_policy_transition(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    *,
    previous_version: dict[str, Any],
    current_version: dict[str, Any],
    issuer: IdentityKey,
    mode: str,
    declared_at_cut: int,
    grace_until_cut: int | None = None,
) -> dict[str, Any]:
    if mode not in MODES:
        raise LightwalkerEconomyError("unsupported policy transition mode")
    if not verify_policy_version(
        promise, route_policy, policy=None, version=previous_version
    ):
        raise LightwalkerEconomyError("invalid previous policy version")
    if not verify_policy_version(
        promise, route_policy, policy=None, version=current_version
    ):
        raise LightwalkerEconomyError("invalid current policy version")
    if previous_version["lineage_id"] != current_version["lineage_id"]:
        raise LightwalkerEconomyError(
            "transition versions must share policy lineage"
        )
    if current_version["previous_version_id"] != (
        previous_version["policy_version_id"]
    ):
        raise LightwalkerEconomyError(
            "current version does not directly follow previous version"
        )
    if issuer.particular() != current_version["issuer_particular"]:
        raise LightwalkerEconomyError(
            "transition issuer does not own policy lineage"
        )
    declared = _nni(declared_at_cut, "declared_at_cut")
    effective = int(current_version["effective_from_cut"])
    if declared > effective:
        raise LightwalkerEconomyError(
            "transition must be declared no later than policy effective cut"
        )

    grace = None
    if mode == "GRACE_UNTIL_CUT":
        if grace_until_cut is None:
            raise LightwalkerEconomyError(
                "GRACE_UNTIL_CUT requires grace_until_cut"
            )
        grace = _nni(grace_until_cut, "grace_until_cut")
        if grace < effective:
            raise LightwalkerEconomyError(
                "grace cut may not precede new policy effective cut"
            )
    elif grace_until_cut is not None:
        raise LightwalkerEconomyError(
            "grace_until_cut only applies to GRACE_UNTIL_CUT"
        )

    body = {
        "kind": TRANSITION_KIND,
        "version": TRANSITION_VERSION,
        "authority": "policy-temporal-semantics-only",
        "issuer_particular": issuer.particular(),
        "lineage_id": current_version["lineage_id"],
        "previous_policy_version_id": previous_version["policy_version_id"],
        "current_policy_version_id": current_version["policy_version_id"],
        "current_effective_from_cut": effective,
        "mode": mode,
        "grace_until_cut": grace,
        "declared_at_cut": declared,
        "policy_content_changed": False,
        "resource_owner_authority": "none",
        "reservation_authority": "none",
        "execution_authority": "none",
        "release_authority": "none",
        "laws": [
            "TRANSITION MODE != POLICY CONTENT",
            "GRACE != PERMANENT EXEMPTION",
            "IN-FLIGHT != UNBOUNDED GRANDFATHERING",
            "MIGRATION != HISTORY REWRITE",
            "POLICY ISSUER != RESOURCE OWNER",
            "DEFERRED ENFORCEMENT != ABSENT ENFORCEMENT",
        ],
    }
    return _signed(
        body,
        id_field="transition_id",
        signer=issuer,
        domain=TRANSITION_DOMAIN,
        byte_domain=TRANSITION_BYTES,
    )


def verify_policy_transition(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    previous_version: dict[str, Any],
    current_version: dict[str, Any],
    transition: dict[str, Any],
) -> bool:
    try:
        if transition.get("kind") != TRANSITION_KIND:
            return False
        if transition.get("version") != TRANSITION_VERSION:
            return False
        if transition.get("authority") != "policy-temporal-semantics-only":
            return False
        if transition.get("mode") not in MODES:
            return False
        if transition.get("lineage_id") != current_version["lineage_id"]:
            return False
        if transition.get("previous_policy_version_id") != (
            previous_version["policy_version_id"]
        ):
            return False
        if transition.get("current_policy_version_id") != (
            current_version["policy_version_id"]
        ):
            return False
        if transition.get("current_effective_from_cut") != (
            current_version["effective_from_cut"]
        ):
            return False
        if transition.get("issuer_particular") != (
            current_version["issuer_particular"]
        ):
            return False
        if transition.get("policy_content_changed") is not False:
            return False
        for field in (
            "resource_owner_authority",
            "reservation_authority",
            "execution_authority",
            "release_authority",
        ):
            if transition.get(field) != "none":
                return False
        mode = transition["mode"]
        grace = transition.get("grace_until_cut")
        if mode == "GRACE_UNTIL_CUT":
            if not isinstance(grace, int):
                return False
            if grace < int(current_version["effective_from_cut"]):
                return False
        elif grace is not None:
            return False
        return (
            verify_policy_version(
                promise, route_policy, policy=None, version=previous_version
            )
            and verify_policy_version(
                promise, route_policy, policy=None, version=current_version
            )
            and _verify_signed(
                transition,
                id_field="transition_id",
                particular_field="issuer_particular",
                domain=TRANSITION_DOMAIN,
                byte_domain=TRANSITION_BYTES,
            )
        )
    except Exception:
        return False


def derive_transition_decision(
    transition: dict[str, Any],
    reservation: dict[str, Any],
    *,
    observed_cut: int,
    execution_started_at_cut: int | None = None,
) -> dict[str, Any]:
    cut = _nni(observed_cut, "observed_cut")
    effective = int(transition["current_effective_from_cut"])
    if cut < effective:
        phase = "BEFORE_CURRENT_POLICY_EFFECTIVE"
        action = "LEGACY_POLICY_STILL_CURRENT"
        legacy_path_open = True
        revalidation_required = False
        migration_required = False
        enforcement_deferred_until_cut = effective
    else:
        mode = transition["mode"]
        authorized = int(reservation["authorized_at_cut"])
        expires = int(reservation["expires_after_cut"])
        started = (
            None
            if execution_started_at_cut is None
            else _nni(execution_started_at_cut, "execution_started_at_cut")
        )
        phase = "CURRENT_POLICY_EFFECTIVE"
        legacy_path_open = False
        revalidation_required = False
        migration_required = False
        enforcement_deferred_until_cut = None

        if mode == "IMMEDIATE_REVALIDATION":
            action = "REVALIDATE_NOW"
            revalidation_required = True
        elif mode == "GRACE_UNTIL_CUT":
            grace = int(transition["grace_until_cut"])
            if cut <= grace and cut <= expires:
                action = "ALLOW_LEGACY_DURING_GRACE"
                legacy_path_open = True
                enforcement_deferred_until_cut = grace
            else:
                action = "REVALIDATE_AFTER_GRACE"
                revalidation_required = True
        elif mode == "FINISH_IN_FLIGHT_ONLY":
            if started is not None and started < effective and cut <= expires:
                action = "ALLOW_FINISH_IN_FLIGHT"
                legacy_path_open = True
                enforcement_deferred_until_cut = expires
            else:
                action = "BLOCK_NOT_IN_FLIGHT"
                revalidation_required = True
        elif mode == "NEW_WORK_ONLY":
            if authorized < effective and cut <= expires:
                action = "ALLOW_PREEXISTING_RESERVATION"
                legacy_path_open = True
                enforcement_deferred_until_cut = expires
            else:
                action = "CURRENT_POLICY_REQUIRED_FOR_NEW_WORK"
                revalidation_required = True
        elif mode == "MIGRATE_BEFORE_EXECUTION":
            action = "MIGRATION_REQUIRED"
            migration_required = True
        else:
            raise LightwalkerEconomyError("unsupported transition mode")

    body = {
        "kind": DECISION_KIND,
        "version": DECISION_VERSION,
        "authority": "derived-transition-gate-only",
        "transition_id": transition["transition_id"],
        "mode": transition["mode"],
        "reservation_id": reservation["reservation_id"],
        "reservation_authorized_at_cut": reservation["authorized_at_cut"],
        "reservation_expires_after_cut": reservation["expires_after_cut"],
        "execution_started_at_cut": execution_started_at_cut,
        "observed_cut": cut,
        "phase": phase,
        "action": action,
        "legacy_path_open": legacy_path_open,
        "revalidation_required": revalidation_required,
        "migration_required": migration_required,
        "enforcement_deferred_until_cut": enforcement_deferred_until_cut,
        "policy_content_changed": False,
        "reservation_rewritten": False,
        "resource_owner_action_taken": False,
        "laws": [
            "TRANSITION MODE != POLICY CONTENT",
            "GRACE != PERMANENT EXEMPTION",
            "IN-FLIGHT != UNBOUNDED GRANDFATHERING",
            "MIGRATION != HISTORY REWRITE",
            "POLICY ISSUER != RESOURCE OWNER",
            "DEFERRED ENFORCEMENT != ABSENT ENFORCEMENT",
        ],
    }
    return {**body, "decision_id": content_address(body)}


def make_migration_receipt(
    transition: dict[str, Any],
    decision: dict[str, Any],
    *,
    old_reservation: dict[str, Any],
    old_finalization: dict[str, Any],
    new_reservation: dict[str, Any],
    current_policy_set_id: str,
) -> dict[str, Any]:
    if transition["mode"] != "MIGRATE_BEFORE_EXECUTION":
        raise LightwalkerEconomyError(
            "migration receipt requires MIGRATE_BEFORE_EXECUTION mode"
        )
    if decision.get("transition_id") != transition["transition_id"]:
        raise LightwalkerEconomyError("transition decision mismatch")
    if decision.get("action") != "MIGRATION_REQUIRED":
        raise LightwalkerEconomyError("transition does not require migration")
    if old_finalization.get("reservation_id") != old_reservation["reservation_id"]:
        raise LightwalkerEconomyError("old finalization mismatch")
    if old_finalization.get("status") != "RELEASED":
        raise LightwalkerEconomyError(
            "old reservation must be explicitly released"
        )
    if new_reservation["reservation_id"] == old_reservation["reservation_id"]:
        raise LightwalkerEconomyError(
            "migration requires a distinct new reservation"
        )
    body = {
        "kind": MIGRATION_KIND,
        "version": MIGRATION_VERSION,
        "authority": "derived-migration-linkage-only",
        "transition_id": transition["transition_id"],
        "decision_id": decision["decision_id"],
        "current_policy_set_id": _nonempty(
            current_policy_set_id, "current_policy_set_id"
        ),
        "old_reservation_id": old_reservation["reservation_id"],
        "old_finalization_id": old_finalization["finalization_id"],
        "new_reservation_id": new_reservation["reservation_id"],
        "old_history_rewritten": False,
        "new_reservation_is_continuation": False,
        "ownership_transfer": False,
        "reservation_authority": "none",
        "execution_authority": "none",
        "laws": [
            "MIGRATION != HISTORY REWRITE",
            "POLICY ISSUER != RESOURCE OWNER",
            "RESERVATION A != RESERVATION B",
        ],
    }
    return {**body, "migration_id": content_address(body)}


__all__ = [
    "MODES",
    "derive_transition_decision",
    "make_migration_receipt",
    "make_policy_transition",
    "verify_policy_transition",
]
