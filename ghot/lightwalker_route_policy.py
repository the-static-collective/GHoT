#!/usr/bin/env python3
"""Lightwalker Route Selection / Failover Policy 001.

A bounded policy may rank evidence-backed remote capacity candidates. Selection
is advisory. Source-local admission, reservation, and execution remain separate.

Core laws:
    POLICY != AUTHORITY
    RECOMMENDATION != RESERVATION
    FAILOVER ORDER != GUARANTEE
    SOURCE SELECTION MUST REMAIN EVIDENCE-BACKED
    AUTOMATIC ROUTING MAY NOT ERASE OWNER-LOCAL ADMISSION
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_federated_reroute import make_reroute
from lightwalker_federated_service import verify_remote_capacity_proof
from lightwalker_guild_reservation import GuildReservationStore
from lightwalker_multi_source_service import verify_multi_source_promise
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


POLICY_KIND = "ghot.lightwalker.route-policy"
POLICY_VERSION = "0"
SELECTION_KIND = "ghot.lightwalker.route-selection"
SELECTION_VERSION = "0"
ADMISSION_KIND = "ghot.lightwalker.route-admission-response"
ADMISSION_VERSION = "0"

POLICY_DOMAIN = "ghot.lightwalker-route-policy-signature/v0"
ADMISSION_DOMAIN = "ghot.lightwalker-route-admission-response-signature/v0"
POLICY_BYTES = b"GHOT-LightwalkerRoutePolicy-v0|"
ADMISSION_BYTES = b"GHOT-LightwalkerRouteAdmissionResponse-v0|"


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


def _source_row(
    promise: dict[str, Any],
    source_id: str,
) -> dict[str, Any]:
    rows = [
        row for row in promise["sources"] if row["source_id"] == source_id
    ]
    if len(rows) != 1:
        raise LightwalkerEconomyError("unknown source slot")
    return rows[0]


def _entry(
    snapshot: dict[str, Any],
    resource_entry_id: str,
) -> dict[str, Any]:
    rows = [
        item
        for item in snapshot.get("entries", [])
        if item.get("entry_id") == resource_entry_id
    ]
    if len(rows) != 1:
        raise LightwalkerEconomyError(
            "candidate resource entry missing from Treasury"
        )
    return rows[0]


def make_route_policy(
    offer: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    *,
    source_slot_id: str,
    promisor: IdentityKey,
    ordered_guild_ids: list[str],
    required_capability: str,
    max_proof_age_cuts: int,
    max_failover_hops: int,
    created_at_cut: int,
) -> dict[str, Any]:
    if not verify_multi_source_promise(
        offer, remote_sources, promise
    ):
        raise LightwalkerEconomyError("invalid service promise")
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError("policy signer is not promisor")
    source = _source_row(promise, source_slot_id)
    if not isinstance(ordered_guild_ids, list) or len(
        ordered_guild_ids
    ) < 2:
        raise LightwalkerEconomyError(
            "route policy requires ordered source preferences"
        )
    if len(set(ordered_guild_ids)) != len(ordered_guild_ids):
        raise LightwalkerEconomyError(
            "route policy contains duplicate Guilds"
        )
    if source["capacity_guild_id"] not in ordered_guild_ids:
        raise LightwalkerEconomyError(
            "original source Guild must appear in route order"
        )
    max_age = _nni(max_proof_age_cuts, "max_proof_age_cuts")
    max_hops = _nni(max_failover_hops, "max_failover_hops")
    if max_hops <= 0:
        raise LightwalkerEconomyError("max_failover_hops must be > 0")

    body = {
        "kind": POLICY_KIND,
        "version": POLICY_VERSION,
        "authority": "promisor-routing-policy-only",
        "promisor_particular": promisor.particular(),
        "promise_id": promise["promise_id"],
        "offer_id": offer["offer_id"],
        "source_slot_id": source["source_id"],
        "declared_measure": source["measure"],
        "original_capacity_guild_id": source["capacity_guild_id"],
        "ordered_guild_ids": list(ordered_guild_ids),
        "required_capability": _nonempty(
            required_capability, "required_capability"
        ),
        "max_proof_age_cuts": max_age,
        "max_failover_hops": max_hops,
        "created_at_cut": _nni(created_at_cut, "created_at_cut"),
        "reservation_authority": "none",
        "execution_authority": "none",
        "ownership_authority": "none",
        "laws": [
            "POLICY != AUTHORITY",
            "RECOMMENDATION != RESERVATION",
            "FAILOVER ORDER != GUARANTEE",
            "SOURCE SELECTION MUST REMAIN EVIDENCE-BACKED",
            "AUTOMATIC ROUTING MAY NOT ERASE OWNER-LOCAL ADMISSION",
        ],
    }
    return _signed(
        body,
        id_field="policy_id",
        signer=promisor,
        domain=POLICY_DOMAIN,
        byte_domain=POLICY_BYTES,
    )


def verify_route_policy(
    promise: dict[str, Any],
    policy: dict[str, Any],
) -> bool:
    try:
        source = _source_row(promise, policy["source_slot_id"])
        if policy.get("kind") != POLICY_KIND:
            return False
        if policy.get("version") != POLICY_VERSION:
            return False
        if policy.get("authority") != "promisor-routing-policy-only":
            return False
        if policy.get("promise_id") != promise["promise_id"]:
            return False
        if (
            policy.get("promisor_particular")
            != promise["promisor_particular"]
        ):
            return False
        if policy.get("declared_measure") != source["measure"]:
            return False
        if (
            policy.get("original_capacity_guild_id")
            != source["capacity_guild_id"]
        ):
            return False
        if policy.get("reservation_authority") != "none":
            return False
        if policy.get("execution_authority") != "none":
            return False
        if policy.get("ownership_authority") != "none":
            return False
        ordered = policy.get("ordered_guild_ids")
        if not isinstance(ordered, list) or len(ordered) < 2:
            return False
        if len(set(ordered)) != len(ordered):
            return False
        return _verify_signed(
            policy,
            id_field="policy_id",
            particular_field="promisor_particular",
            domain=POLICY_DOMAIN,
            byte_domain=POLICY_BYTES,
        )
    except Exception:
        return False


def _candidate_row(
    candidate: dict[str, Any],
    *,
    policy: dict[str, Any],
    evaluation_cut: int,
) -> dict[str, Any]:
    snapshot = candidate.get("snapshot")
    proof = candidate.get("proof")
    if not isinstance(snapshot, dict) or not isinstance(proof, dict):
        raise LightwalkerEconomyError(
            "candidate requires snapshot and proof"
        )
    if not verify_remote_capacity_proof(snapshot, proof):
        raise LightwalkerEconomyError("invalid candidate remote proof")
    entry = _entry(snapshot, proof["resource_entry_id"])
    metadata = entry.get("metadata")
    capability = (
        metadata.get("capability")
        if isinstance(metadata, dict)
        else None
    )
    measure = proof["native_measure"]
    age = evaluation_cut - int(proof["observed_cut"])
    reasons: list[str] = []
    if evaluation_cut < int(proof["observed_cut"]):
        reasons.append("PROOF_FROM_FUTURE")
    if evaluation_cut > int(proof["valid_through_cut"]):
        reasons.append("PROOF_EXPIRED")
    if age > int(policy["max_proof_age_cuts"]):
        reasons.append("PROOF_TOO_OLD")
    if measure["unit"] != policy["declared_measure"]["unit"]:
        reasons.append("UNIT_MISMATCH")
    if int(measure["quantity"]) < int(
        policy["declared_measure"]["quantity"]
    ):
        reasons.append("INSUFFICIENT_PROVEN_QUANTITY")
    if capability != policy["required_capability"]:
        reasons.append("CAPABILITY_MISMATCH")
    if proof["capacity_guild_id"] not in policy["ordered_guild_ids"]:
        reasons.append("GUILD_NOT_IN_POLICY")
    return {
        "capacity_guild_id": proof["capacity_guild_id"],
        "snapshot_id": proof["snapshot_id"],
        "remote_proof_id": proof["remote_proof_id"],
        "resource_entry_id": proof["resource_entry_id"],
        "capacity_steward_particular": proof[
            "capacity_steward_particular"
        ],
        "native_measure": measure,
        "capability": capability,
        "proof_observed_cut": int(proof["observed_cut"]),
        "proof_valid_through_cut": int(proof["valid_through_cut"]),
        "proof_age_cuts": age,
        "eligible": not reasons,
        "ineligibility_reasons": reasons,
    }


def select_route(
    promise: dict[str, Any],
    policy: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    evaluation_cut: int,
    excluded_guild_ids: list[str],
    prior_selection_ids: list[str] | None = None,
) -> dict[str, Any]:
    if not verify_route_policy(promise, policy):
        raise LightwalkerEconomyError("invalid route policy")
    cut = _nni(evaluation_cut, "evaluation_cut")
    excluded = list(dict.fromkeys(excluded_guild_ids))
    prior_ids = list(prior_selection_ids or [])
    failover_index = len(prior_ids) + 1
    if failover_index > int(policy["max_failover_hops"]):
        raise LightwalkerEconomyError(
            "route policy failover depth exhausted"
        )

    rows = [
        _candidate_row(
            candidate,
            policy=policy,
            evaluation_cut=cut,
        )
        for candidate in candidates
    ]
    if len(
        {row["remote_proof_id"] for row in rows}
    ) != len(rows):
        raise LightwalkerEconomyError("duplicate candidate proof")

    order = {
        guild_id: index
        for index, guild_id in enumerate(policy["ordered_guild_ids"])
    }
    eligible = [
        row
        for row in rows
        if row["eligible"]
        and row["capacity_guild_id"] not in excluded
    ]
    eligible.sort(
        key=lambda row: (
            order[row["capacity_guild_id"]],
            row["remote_proof_id"],
        )
    )
    selected = eligible[0] if eligible else None

    body = {
        "kind": SELECTION_KIND,
        "version": SELECTION_VERSION,
        "authority": "derived-routing-recommendation-only",
        "policy_id": policy["policy_id"],
        "promise_id": promise["promise_id"],
        "source_slot_id": policy["source_slot_id"],
        "evaluation_cut": cut,
        "failover_index": failover_index,
        "excluded_guild_ids": sorted(excluded),
        "prior_selection_ids": prior_ids,
        "candidate_rows": sorted(
            rows,
            key=lambda row: (
                order.get(row["capacity_guild_id"], 10**9),
                row["remote_proof_id"],
            ),
        ),
        "selection_status": (
            "SELECTED" if selected is not None else "NO_ELIGIBLE_ROUTE"
        ),
        "selected_candidate": selected,
        "reservation_authority": "none",
        "execution_authority": "none",
        "owner_admission_required": True,
        "laws": [
            "POLICY != AUTHORITY",
            "RECOMMENDATION != RESERVATION",
            "FAILOVER ORDER != GUARANTEE",
            "SOURCE SELECTION MUST REMAIN EVIDENCE-BACKED",
            "AUTOMATIC ROUTING MAY NOT ERASE OWNER-LOCAL ADMISSION",
        ],
    }
    return {**body, "selection_id": content_address(body)}


def make_owner_admission_response(
    selection: dict[str, Any],
    snapshot: dict[str, Any],
    proof: dict[str, Any],
    *,
    reservation_store: GuildReservationStore,
    steward: IdentityKey,
    observed_cut: int,
) -> dict[str, Any]:
    selected = selection.get("selected_candidate")
    if selection.get("selection_status") != "SELECTED":
        raise LightwalkerEconomyError(
            "owner admission requires selected route"
        )
    if not isinstance(selected, dict):
        raise LightwalkerEconomyError("selection lacks selected candidate")
    if not verify_remote_capacity_proof(snapshot, proof):
        raise LightwalkerEconomyError("invalid selected remote proof")
    if selected["snapshot_id"] != snapshot["snapshot_id"]:
        raise LightwalkerEconomyError("selected snapshot mismatch")
    if selected["remote_proof_id"] != proof["remote_proof_id"]:
        raise LightwalkerEconomyError("selected proof mismatch")
    if steward.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError(
            "only source steward may answer admission"
        )

    state = reservation_store.capacity_state(
        snapshot, proof["resource_entry_id"]
    )
    required = selected["native_measure"]
    enough = (
        state["unit"] == required["unit"]
        and int(state["unencumbered_quantity"])
        >= int(required["quantity"])
    )
    disposition = "ADMITTABLE" if enough else "REFUSED"
    reason = (
        "OWNER_LOCAL_CAPACITY_AVAILABLE"
        if enough
        else "INSUFFICIENT_UNENCUMBERED_CAPACITY"
    )
    body = {
        "kind": ADMISSION_KIND,
        "version": ADMISSION_VERSION,
        "authority": "owner-local-admission-response-only",
        "selection_id": selection["selection_id"],
        "capacity_guild_id": proof["capacity_guild_id"],
        "capacity_steward_particular": steward.particular(),
        "snapshot_id": snapshot["snapshot_id"],
        "remote_proof_id": proof["remote_proof_id"],
        "resource_entry_id": proof["resource_entry_id"],
        "required_measure": required,
        "owner_local_state": {
            "unit": state["unit"],
            "visible_quantity": state["visible_quantity"],
            "reserved_quantity": state["reserved_quantity"],
            "unencumbered_quantity": state["unencumbered_quantity"],
        },
        "observed_cut": _nni(observed_cut, "observed_cut"),
        "disposition": disposition,
        "reason": reason,
        "reservation_created": False,
        "execution_authority_granted": False,
        "laws": [
            "POLICY != AUTHORITY",
            "RECOMMENDATION != RESERVATION",
            "OWNER ADMISSION RESPONSE != RESERVATION",
            "FAILOVER ORDER != GUARANTEE",
        ],
    }
    return _signed(
        body,
        id_field="admission_response_id",
        signer=steward,
        domain=ADMISSION_DOMAIN,
        byte_domain=ADMISSION_BYTES,
    )


def verify_owner_admission_response(
    selection: dict[str, Any],
    response: dict[str, Any],
) -> bool:
    try:
        selected = selection["selected_candidate"]
        if selection.get("selection_status") != "SELECTED":
            return False
        if response.get("kind") != ADMISSION_KIND:
            return False
        if response.get("version") != ADMISSION_VERSION:
            return False
        if (
            response.get("authority")
            != "owner-local-admission-response-only"
        ):
            return False
        if response.get("selection_id") != selection["selection_id"]:
            return False
        if (
            response.get("capacity_guild_id")
            != selected["capacity_guild_id"]
        ):
            return False
        if response.get("snapshot_id") != selected["snapshot_id"]:
            return False
        if response.get("remote_proof_id") != selected["remote_proof_id"]:
            return False
        if response.get("resource_entry_id") != selected["resource_entry_id"]:
            return False
        if response.get("required_measure") != selected["native_measure"]:
            return False
        if response.get("disposition") not in {
            "ADMITTABLE",
            "REFUSED",
        }:
            return False
        if response.get("reservation_created") is not False:
            return False
        if response.get("execution_authority_granted") is not False:
            return False
        return _verify_signed(
            response,
            id_field="admission_response_id",
            particular_field="capacity_steward_particular",
            domain=ADMISSION_DOMAIN,
            byte_domain=ADMISSION_BYTES,
        )
    except Exception:
        return False


def make_policy_bound_reroute(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    *,
    policy: dict[str, Any],
    selection: dict[str, Any],
    admission_response: dict[str, Any],
    original_source_id: str,
    original_snapshot: dict[str, Any],
    original_proof: dict[str, Any],
    original_request: dict[str, Any],
    original_proposal: dict[str, Any],
    original_authorization: dict[str, Any],
    original_reservation: dict[str, Any],
    original_grant: dict[str, Any],
    original_finalization: dict[str, Any],
    substitute_snapshot: dict[str, Any],
    substitute_proof: dict[str, Any],
    promisor: IdentityKey,
    rerouted_at_cut: int,
) -> dict[str, Any]:
    if not verify_route_policy(promise, policy):
        raise LightwalkerEconomyError("invalid route policy")
    if selection.get("policy_id") != policy["policy_id"]:
        raise LightwalkerEconomyError(
            "selection belongs to another policy"
        )
    if selection.get("source_slot_id") != original_source_id:
        raise LightwalkerEconomyError(
            "selection targets another source slot"
        )
    selected = selection.get("selected_candidate")
    if not isinstance(selected, dict):
        raise LightwalkerEconomyError("no selected candidate")
    if selected["snapshot_id"] != substitute_snapshot["snapshot_id"]:
        raise LightwalkerEconomyError("selected snapshot mismatch")
    if selected["remote_proof_id"] != substitute_proof["remote_proof_id"]:
        raise LightwalkerEconomyError("selected proof mismatch")
    if not verify_owner_admission_response(
        selection, admission_response
    ):
        raise LightwalkerEconomyError(
            "invalid owner-local admission response"
        )
    if admission_response.get("disposition") != "ADMITTABLE":
        raise LightwalkerEconomyError(
            "owner-local source did not admit route"
        )

    reroute = make_reroute(
        offer,
        acceptance,
        remote_sources,
        promise,
        original_source_id=original_source_id,
        original_snapshot=original_snapshot,
        original_proof=original_proof,
        original_request=original_request,
        original_proposal=original_proposal,
        original_authorization=original_authorization,
        original_reservation=original_reservation,
        original_grant=original_grant,
        original_finalization=original_finalization,
        substitute_snapshot=substitute_snapshot,
        substitute_proof=substitute_proof,
        promisor=promisor,
        rerouted_at_cut=rerouted_at_cut,
    )
    return {
        **reroute,
        "route_policy_id": policy["policy_id"],
        "route_selection_id": selection["selection_id"],
        "owner_admission_response_id": admission_response[
            "admission_response_id"
        ],
    }


__all__ = [
    "make_owner_admission_response",
    "make_policy_bound_reroute",
    "make_route_policy",
    "select_route",
    "verify_owner_admission_response",
    "verify_route_policy",
]
