#!/usr/bin/env python3
"""Lightwalker Policy Versioning / Mid-Flight Change 001.

Immutable policy fragments are wrapped in an explicit version lineage. A newer
version may require revalidation of still-live authority, but it cannot rewrite
the older policy, admission, reservation, or work history.

Core laws:
    NEW POLICY != RETROACTIVE REWRITE
    POLICY VERSION != POLICY IDENTITY
    OLD ADMISSION != NEW COMPLIANCE
    RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2
    POLICY CHANGE MAY REQUIRE REVALIDATION
    REVALIDATION != HISTORY ERASURE
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_reservation,
)
from lightwalker_policy_composition import (
    compose_policy_intersection,
    evaluate_policy_intersection,
    verify_policy_fragment,
)
from lightwalker_route_policy import verify_route_policy
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


VERSION_KIND = "ghot.lightwalker.constraint-policy-version"
VERSION_VERSION = "0"
POLICY_SET_KIND = "ghot.lightwalker.active-policy-set"
POLICY_SET_VERSION = "0"
REVALIDATION_KIND = "ghot.lightwalker.policy-revalidation"
REVALIDATION_VERSION = "0"
ROUTE_BINDING_KIND = "ghot.lightwalker.versioned-policy-route-binding"
ROUTE_BINDING_VERSION = "0"

VERSION_DOMAIN = "ghot.lightwalker-constraint-policy-version-signature/v0"
VERSION_BYTES = b"GHOT-LightwalkerConstraintPolicyVersion-v0|"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(
            f"{name} must be a non-empty string"
        )
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
        byte_domain + canonical_bytes(
            {id_field: item_id, **body}
        )
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
        if not isinstance(item_id, str):
            return False
        if content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            byte_domain
            + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def policy_lineage_id(policy: dict[str, Any]) -> str:
    body = {
        "kind": "ghot.lightwalker.policy-lineage-key",
        "issuer_particular": policy["issuer_particular"],
        "issuer_role": policy["issuer_role"],
        "policy_name": policy["policy_name"],
        "promise_id": policy["promise_id"],
        "route_policy_id": policy["route_policy_id"],
        "source_slot_id": policy["source_slot_id"],
    }
    return content_address(body)


def make_policy_version(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    policy: dict[str, Any],
    *,
    issuer: IdentityKey,
    version_number: int,
    effective_from_cut: int,
    declared_at_cut: int,
    previous_version: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not verify_policy_fragment(
        promise, route_policy, policy
    ):
        raise LightwalkerEconomyError(
            "invalid policy fragment"
        )
    if issuer.particular() != policy["issuer_particular"]:
        raise LightwalkerEconomyError(
            "version issuer does not own policy fragment"
        )
    number = _nni(version_number, "version_number")
    if number <= 0:
        raise LightwalkerEconomyError(
            "version_number must be > 0"
        )
    effective = _nni(
        effective_from_cut, "effective_from_cut"
    )
    declared = _nni(declared_at_cut, "declared_at_cut")
    if declared > effective:
        raise LightwalkerEconomyError(
            "policy version may not be declared after effective cut"
        )

    lineage = policy_lineage_id(policy)
    previous_id = None
    if previous_version is None:
        if number != 1:
            raise LightwalkerEconomyError(
                "first policy version must be version 1"
            )
    else:
        if not verify_policy_version(
            promise,
            route_policy,
            policy=None,
            version=previous_version,
        ):
            raise LightwalkerEconomyError(
                "invalid previous policy version"
            )
        if previous_version["lineage_id"] != lineage:
            raise LightwalkerEconomyError(
                "policy version lineage mismatch"
            )
        if number != int(
            previous_version["version_number"]
        ) + 1:
            raise LightwalkerEconomyError(
                "policy version number must increment by one"
            )
        if effective <= int(
            previous_version["effective_from_cut"]
        ):
            raise LightwalkerEconomyError(
                "new policy version must become effective later"
            )
        previous_id = previous_version["policy_version_id"]

    body = {
        "kind": VERSION_KIND,
        "version": VERSION_VERSION,
        "authority": "issuer-policy-version-declaration-only",
        "issuer_particular": issuer.particular(),
        "issuer_role": policy["issuer_role"],
        "policy_name": policy["policy_name"],
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "lineage_id": lineage,
        "version_number": number,
        "fragment_policy_id": policy["policy_id"],
        "previous_version_id": previous_id,
        "effective_from_cut": effective,
        "declared_at_cut": declared,
        "retroactive_rewrite": False,
        "history_rewrite": False,
        "automatic_authority_carry_forward": False,
        "laws": [
            "NEW POLICY != RETROACTIVE REWRITE",
            "POLICY VERSION != POLICY IDENTITY",
            "OLD ADMISSION != NEW COMPLIANCE",
            "RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2",
            "POLICY CHANGE MAY REQUIRE REVALIDATION",
            "REVALIDATION != HISTORY ERASURE",
        ],
    }
    return _signed(
        body,
        id_field="policy_version_id",
        signer=issuer,
        domain=VERSION_DOMAIN,
        byte_domain=VERSION_BYTES,
    )


def verify_policy_version(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    policy: dict[str, Any] | None,
    version: dict[str, Any],
) -> bool:
    try:
        if version.get("kind") != VERSION_KIND:
            return False
        if version.get("version") != VERSION_VERSION:
            return False
        if (
            version.get("authority")
            != "issuer-policy-version-declaration-only"
        ):
            return False
        if version.get("promise_id") != promise["promise_id"]:
            return False
        if version.get("route_policy_id") != route_policy["policy_id"]:
            return False
        if version.get("source_slot_id") != route_policy["source_slot_id"]:
            return False
        if version.get("retroactive_rewrite") is not False:
            return False
        if version.get("history_rewrite") is not False:
            return False
        if (
            version.get("automatic_authority_carry_forward")
            is not False
        ):
            return False
        if int(version.get("version_number", 0)) <= 0:
            return False
        if int(version.get("declared_at_cut", -1)) > int(
            version.get("effective_from_cut", -1)
        ):
            return False
        if policy is not None:
            if not verify_policy_fragment(
                promise, route_policy, policy
            ):
                return False
            if version.get("fragment_policy_id") != policy["policy_id"]:
                return False
            if version.get("lineage_id") != policy_lineage_id(policy):
                return False
            if version.get("issuer_particular") != policy[
                "issuer_particular"
            ]:
                return False
            if version.get("issuer_role") != policy["issuer_role"]:
                return False
            if version.get("policy_name") != policy["policy_name"]:
                return False
        return _verify_signed(
            version,
            id_field="policy_version_id",
            particular_field="issuer_particular",
            domain=VERSION_DOMAIN,
            byte_domain=VERSION_BYTES,
        )
    except Exception:
        return False


def derive_active_policy_set(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    policies: list[dict[str, Any]],
    versions: list[dict[str, Any]],
    *,
    observed_cut: int,
) -> dict[str, Any]:
    cut = _nni(observed_cut, "observed_cut")
    policy_by_id = {
        policy["policy_id"]: policy for policy in policies
    }
    if len(policy_by_id) != len(policies):
        raise LightwalkerEconomyError(
            "duplicate policy fragment"
        )

    groups: dict[str, list[dict[str, Any]]] = {}
    for version in versions:
        policy = policy_by_id.get(
            version.get("fragment_policy_id")
        )
        if policy is None:
            raise LightwalkerEconomyError(
                "policy version references unavailable fragment"
            )
        if not verify_policy_version(
            promise, route_policy, policy, version
        ):
            raise LightwalkerEconomyError(
                "invalid policy version"
            )
        groups.setdefault(
            version["lineage_id"], []
        ).append(version)

    active: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    for lineage_id, rows in groups.items():
        eligible = [
            row
            for row in rows
            if int(row["effective_from_cut"]) <= cut
        ]
        if not eligible:
            raise LightwalkerEconomyError(
                "policy lineage has no active version at observed cut"
            )
        eligible.sort(
            key=lambda row: (
                int(row["version_number"]),
                row["policy_version_id"],
            )
        )
        selected = eligible[-1]
        active.append(selected)
        superseded.extend(
            row
            for row in eligible[:-1]
        )

        selected_number = int(
            selected["version_number"]
        )
        for row in rows:
            if int(row["version_number"]) > selected_number:
                continue
            if row["lineage_id"] != lineage_id:
                raise LightwalkerEconomyError(
                    "policy lineage corruption"
                )

    active_rows = []
    for version in active:
        policy = policy_by_id[version["fragment_policy_id"]]
        active_rows.append(
            {
                "lineage_id": version["lineage_id"],
                "policy_version_id": version[
                    "policy_version_id"
                ],
                "version_number": version["version_number"],
                "fragment_policy_id": policy["policy_id"],
                "issuer_particular": policy["issuer_particular"],
                "issuer_role": policy["issuer_role"],
                "policy_name": policy["policy_name"],
                "effective_from_cut": version["effective_from_cut"],
            }
        )

    body = {
        "kind": POLICY_SET_KIND,
        "version": POLICY_SET_VERSION,
        "authority": "derived-active-policy-set-only",
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "observed_cut": cut,
        "active_versions": sorted(
            active_rows, key=lambda row: row["lineage_id"]
        ),
        "superseded_policy_version_ids": sorted(
            row["policy_version_id"]
            for row in superseded
        ),
        "retroactive_rewrite": False,
        "automatic_authority_carry_forward": False,
        "reservation_authority": "none",
        "laws": [
            "NEW POLICY != RETROACTIVE REWRITE",
            "POLICY VERSION != POLICY IDENTITY",
            "RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2",
            "REVALIDATION != HISTORY ERASURE",
        ],
    }
    return {**body, "policy_set_id": content_address(body)}


def active_policy_fragments(
    policy_set: dict[str, Any],
    policies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    policy_by_id = {
        policy["policy_id"]: policy for policy in policies
    }
    result = []
    for row in policy_set["active_versions"]:
        policy = policy_by_id.get(row["fragment_policy_id"])
        if policy is None:
            raise LightwalkerEconomyError(
                "active policy fragment unavailable"
            )
        result.append(policy)
    return result


def bind_route_to_policy_set(
    policy_set: dict[str, Any],
    *,
    route_binding_id: str,
    reservation_id: str,
    admission_response_id: str,
) -> dict[str, Any]:
    body = {
        "kind": ROUTE_BINDING_KIND,
        "version": ROUTE_BINDING_VERSION,
        "authority": "derived-policy-version-route-linkage",
        "policy_set_id": policy_set["policy_set_id"],
        "promise_id": policy_set["promise_id"],
        "source_slot_id": policy_set["source_slot_id"],
        "route_binding_id": _nonempty(
            route_binding_id, "route_binding_id"
        ),
        "reservation_id": _nonempty(
            reservation_id, "reservation_id"
        ),
        "admission_response_id": _nonempty(
            admission_response_id, "admission_response_id"
        ),
        "active_policy_version_ids": sorted(
            row["policy_version_id"]
            for row in policy_set["active_versions"]
        ),
        "bound_at_cut": policy_set["observed_cut"],
        "retroactive_rewrite": False,
        "authority_carry_forward": False,
        "reservation_authority": "none",
        "laws": [
            "POLICY VERSION != POLICY IDENTITY",
            "RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2",
            "REVALIDATION != HISTORY ERASURE",
        ],
    }
    return {**body, "versioned_binding_id": content_address(body)}


def derive_revalidation(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    *,
    previous_policy_set: dict[str, Any],
    current_policy_set: dict[str, Any],
    policies: list[dict[str, Any]],
    candidate: dict[str, Any],
    measurements: list[dict[str, Any]],
    attestations: list[dict[str, Any]],
    reservation: dict[str, Any],
    prior_binding_id: str,
    prior_admission_response_id: str,
    evaluation_cut: int,
) -> dict[str, Any]:
    cut = _nni(evaluation_cut, "evaluation_cut")
    if previous_policy_set["promise_id"] != promise["promise_id"]:
        raise LightwalkerEconomyError(
            "previous policy set belongs to another promise"
        )
    if current_policy_set["promise_id"] != promise["promise_id"]:
        raise LightwalkerEconomyError(
            "current policy set belongs to another promise"
        )
    if int(current_policy_set["observed_cut"]) < int(
        previous_policy_set["observed_cut"]
    ):
        raise LightwalkerEconomyError(
            "policy set time moved backward"
        )
    if cut < int(current_policy_set["observed_cut"]):
        raise LightwalkerEconomyError(
            "revalidation precedes current policy observation"
        )

    current_policies = active_policy_fragments(
        current_policy_set, policies
    )
    intersection = compose_policy_intersection(
        promise, route_policy, current_policies
    )
    evaluation = evaluate_policy_intersection(
        promise,
        route_policy,
        current_policies,
        intersection,
        [candidate],
        measurements,
        attestations,
        evaluation_cut=cut,
        excluded_guild_ids=[],
    )
    row = evaluation["candidate_rows"][0]
    compliant = (
        evaluation["result"] == "SATISFYING_ROUTES"
        and row["intersection_status"] == "ELIGIBLE"
    )
    body = {
        "kind": REVALIDATION_KIND,
        "version": REVALIDATION_VERSION,
        "authority": "derived-policy-revalidation-only",
        "promise_id": promise["promise_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "reservation_id": reservation["reservation_id"],
        "prior_binding_id": _nonempty(
            prior_binding_id, "prior_binding_id"
        ),
        "prior_admission_response_id": _nonempty(
            prior_admission_response_id,
            "prior_admission_response_id",
        ),
        "previous_policy_set_id": previous_policy_set["policy_set_id"],
        "current_policy_set_id": current_policy_set["policy_set_id"],
        "current_policy_version_ids": sorted(
            row["policy_version_id"]
            for row in current_policy_set["active_versions"]
        ),
        "candidate_remote_proof_id": candidate[
            "proof"
        ]["remote_proof_id"],
        "evaluation_id": evaluation["evaluation_id"],
        "intersection_id": intersection["intersection_id"],
        "evaluated_at_cut": cut,
        "status": "COMPLIANT" if compliant else "NONCOMPLIANT",
        "policy_failures": row["policy_verdicts"],
        "future_execution_permitted": compliant,
        "old_admission_rewritten": False,
        "reservation_rewritten": False,
        "history_erased": False,
        "automatic_release": False,
        "laws": [
            "NEW POLICY != RETROACTIVE REWRITE",
            "OLD ADMISSION != NEW COMPLIANCE",
            "RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2",
            "POLICY CHANGE MAY REQUIRE REVALIDATION",
            "REVALIDATION != HISTORY ERASURE",
        ],
    }
    return {**body, "revalidation_id": content_address(body)}


def verify_revalidation(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    *,
    previous_policy_set: dict[str, Any],
    current_policy_set: dict[str, Any],
    policies: list[dict[str, Any]],
    candidate: dict[str, Any],
    measurements: list[dict[str, Any]],
    attestations: list[dict[str, Any]],
    reservation: dict[str, Any],
    prior_binding_id: str,
    prior_admission_response_id: str,
    revalidation: dict[str, Any],
) -> bool:
    try:
        expected = derive_revalidation(
            promise,
            route_policy,
            previous_policy_set=previous_policy_set,
            current_policy_set=current_policy_set,
            policies=policies,
            candidate=candidate,
            measurements=measurements,
            attestations=attestations,
            reservation=reservation,
            prior_binding_id=prior_binding_id,
            prior_admission_response_id=prior_admission_response_id,
            evaluation_cut=int(revalidation["evaluated_at_cut"]),
        )
        return expected == revalidation
    except Exception:
        return False


def execute_reserved_with_revalidation(
    store: GuildReservationStore,
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    *,
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    previous_policy_set: dict[str, Any],
    current_policy_set: dict[str, Any],
    policies: list[dict[str, Any]],
    candidate: dict[str, Any],
    measurements: list[dict[str, Any]],
    attestations: list[dict[str, Any]],
    prior_binding_id: str,
    prior_admission_response_id: str,
    revalidation: dict[str, Any] | None,
    executor: IdentityKey,
    observed_cut: int,
    simulate_success: bool,
    result_ref: str | None = None,
    error: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not verify_reservation(
        snapshot, proposal, authorization, reservation
    ):
        raise LightwalkerEconomyError(
            "invalid reserved authority"
        )
    cut = _nni(observed_cut, "observed_cut")
    if cut < int(current_policy_set["observed_cut"]):
        raise LightwalkerEconomyError(
            "execution precedes current policy set"
        )
    if revalidation is None:
        raise LightwalkerEconomyError(
            "current policy version requires revalidation"
        )
    if not verify_revalidation(
        promise,
        route_policy,
        previous_policy_set=previous_policy_set,
        current_policy_set=current_policy_set,
        policies=policies,
        candidate=candidate,
        measurements=measurements,
        attestations=attestations,
        reservation=reservation,
        prior_binding_id=prior_binding_id,
        prior_admission_response_id=prior_admission_response_id,
        revalidation=revalidation,
    ):
        raise LightwalkerEconomyError(
            "invalid policy revalidation"
        )
    if revalidation.get("status") != "COMPLIANT":
        raise LightwalkerEconomyError(
            "reservation is noncompliant under current policy version"
        )
    if revalidation.get("future_execution_permitted") is not True:
        raise LightwalkerEconomyError(
            "revalidation does not permit future execution"
        )
    if revalidation.get("current_policy_set_id") != (
        current_policy_set["policy_set_id"]
    ):
        raise LightwalkerEconomyError(
            "revalidation belongs to stale policy set"
        )
    return store.execute_reserved(
        snapshot,
        proposal,
        authorization,
        reservation,
        executor=executor,
        observed_cut=cut,
        simulate_success=simulate_success,
        result_ref=result_ref,
        error=error,
    )


__all__ = [
    "active_policy_fragments",
    "bind_route_to_policy_set",
    "derive_active_policy_set",
    "derive_revalidation",
    "execute_reserved_with_revalidation",
    "make_policy_version",
    "policy_lineage_id",
    "verify_policy_version",
    "verify_revalidation",
]
