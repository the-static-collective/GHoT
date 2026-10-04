#!/usr/bin/env python3
"""Lightwalker Federated Reroute / Substitution 001.

Replace one failed or released sovereign source route without rewriting the
customer-facing promise.

Core laws:
    SOURCE SUBSTITUTION != PROMISE REWRITE
    FAILED SOURCE != FAILED SERVICE
    REROUTE REQUIRES NEW EVIDENCE
    OLD AUTHORITY MUST STOP COUNTING BEFORE SUBSTITUTE AUTHORITY COUNTS
    SUBSTITUTE COMPLETION MAY SATISFY THE SAME DECLARED SERVICE
    ROUTE HISTORY != SERVICE SEMANTICS
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_federated_service import verify_remote_capacity_proof
from lightwalker_guild_authorization import (
    make_resource_proposal,
    verify_execution_receipt,
)
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_finalization,
    verify_reservation,
)
from lightwalker_heterogeneous_exchange import (
    sign_obligation_performance,
    verify_exchange_acceptance,
    verify_exchange_settlement,
    verify_obligation_performance,
)
from lightwalker_multi_source_service import (
    verify_multi_source_promise,
    verify_source_grant,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    identity_safe,
    particular_for_public_key,
    sign_crossing,
    timestamp_now,
    verify_crossing,
    verify_p256,
)


REROUTE_KIND = "ghot.lightwalker.federated-source-reroute"
REROUTE_VERSION = "0"
REQUEST_KIND = "ghot.lightwalker.federated-substitute-request"
REQUEST_VERSION = "0"
GRANT_KIND = "ghot.lightwalker.federated-substitute-grant"
GRANT_VERSION = "0"
COMPLETION_KIND = "ghot.lightwalker.federated-substitute-completion"
COMPLETION_VERSION = "0"
FAILURE_KIND = "ghot.lightwalker.federated-substitute-failure"
FAILURE_VERSION = "0"
BACKING_KIND = "ghot.lightwalker.rerouted-backing-view"
BACKING_VERSION = "0"
AGGREGATE_KIND = "ghot.lightwalker.rerouted-service-completion"
AGGREGATE_VERSION = "0"
SETTLEMENT_KIND = "ghot.lightwalker.rerouted-service-settlement"
SETTLEMENT_VERSION = "0"

REROUTE_DOMAIN = "ghot.lightwalker-federated-source-reroute-signature/v0"
REQUEST_DOMAIN = "ghot.lightwalker-federated-substitute-request-signature/v0"
GRANT_DOMAIN = "ghot.lightwalker-federated-substitute-grant-signature/v0"
COMPLETION_DOMAIN = "ghot.lightwalker-federated-substitute-completion-signature/v0"
FAILURE_DOMAIN = "ghot.lightwalker-federated-substitute-failure-signature/v0"

REROUTE_BYTES = b"GHOT-LightwalkerFederatedSourceReroute-v0|"
REQUEST_BYTES = b"GHOT-LightwalkerFederatedSubstituteRequest-v0|"
GRANT_BYTES = b"GHOT-LightwalkerFederatedSubstituteGrant-v0|"
COMPLETION_BYTES = b"GHOT-LightwalkerFederatedSubstituteCompletion-v0|"
FAILURE_BYTES = b"GHOT-LightwalkerFederatedSubstituteFailure-v0|"

REROUTE_CAPABILITY = "ghot.lightwalker-federated-reroute/v0"


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


def _source_row(promise: dict[str, Any], source_id: str) -> dict[str, Any]:
    matches = [
        row for row in promise["sources"] if row["source_id"] == source_id
    ]
    if len(matches) != 1:
        raise LightwalkerEconomyError("unknown original source slot")
    return matches[0]


def make_reroute(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    *,
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
    if not verify_multi_source_promise(offer, remote_sources, promise):
        raise LightwalkerEconomyError("invalid original service promise")
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid customer acceptance")
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError("reroute signer is not promisor")

    original = _source_row(promise, original_source_id)
    if original_snapshot["snapshot_id"] != original["snapshot_id"]:
        raise LightwalkerEconomyError("original snapshot mismatch")
    if original_proof["remote_proof_id"] != original["remote_proof_id"]:
        raise LightwalkerEconomyError("original proof mismatch")
    if not verify_source_grant(
        original_snapshot,
        original_proof,
        original_request,
        original_proposal,
        original_authorization,
        original_reservation,
        original_grant,
    ):
        raise LightwalkerEconomyError("invalid original source grant")
    if not verify_finalization(
        original_reservation, original_finalization
    ):
        raise LightwalkerEconomyError("invalid original route finalization")
    if original_finalization.get("status") != "RELEASED":
        raise LightwalkerEconomyError(
            "original authority must be released before reroute"
        )

    if not verify_remote_capacity_proof(
        substitute_snapshot, substitute_proof
    ):
        raise LightwalkerEconomyError("invalid substitute capacity proof")
    if (
        substitute_proof["capacity_guild_id"]
        == original["capacity_guild_id"]
    ):
        raise LightwalkerEconomyError(
            "substitute must be a different sovereign source"
        )
    if (
        substitute_proof["native_measure"]["unit"]
        != original["measure"]["unit"]
    ):
        raise LightwalkerEconomyError("substitute unit mismatch")
    if int(substitute_proof["native_measure"]["quantity"]) < int(
        original["measure"]["quantity"]
    ):
        raise LightwalkerEconomyError(
            "substitute proof lacks required slot quantity"
        )

    cut = _nni(rerouted_at_cut, "rerouted_at_cut")
    if cut > int(substitute_proof["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "substitute proof expired before reroute"
        )
    if cut > int(offer["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "customer-facing offer expired before reroute"
        )

    body = {
        "kind": REROUTE_KIND,
        "version": REROUTE_VERSION,
        "authority": "promisor-route-substitution-only",
        "promisor_particular": promisor.particular(),
        "promise_id": promise["promise_id"],
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "original_source_id": original["source_id"],
        "original_capacity_guild_id": original["capacity_guild_id"],
        "original_grant_id": original_grant["grant_id"],
        "original_reservation_id": original_reservation["reservation_id"],
        "original_finalization_id": original_finalization[
            "finalization_id"
        ],
        "original_route_status": "RELEASED",
        "substitute_capacity_guild_id": substitute_proof[
            "capacity_guild_id"
        ],
        "substitute_snapshot_id": substitute_proof["snapshot_id"],
        "substitute_remote_proof_id": substitute_proof["remote_proof_id"],
        "substitute_resource_entry_id": substitute_proof[
            "resource_entry_id"
        ],
        "replacement_measure": original["measure"],
        "rerouted_at_cut": cut,
        "promise_rewritten": False,
        "ownership_transfer": False,
        "old_authority_counts": False,
        "substitute_reserved": False,
        "laws": [
            "SOURCE SUBSTITUTION != PROMISE REWRITE",
            "REROUTE REQUIRES NEW EVIDENCE",
            "OLD AUTHORITY MUST STOP COUNTING BEFORE SUBSTITUTE AUTHORITY COUNTS",
            "ROUTE HISTORY != SERVICE SEMANTICS",
        ],
    }
    return _signed(
        body,
        id_field="reroute_id",
        signer=promisor,
        domain=REROUTE_DOMAIN,
        byte_domain=REROUTE_BYTES,
    )


def verify_reroute(
    promise: dict[str, Any],
    substitute_snapshot: dict[str, Any],
    substitute_proof: dict[str, Any],
    reroute: dict[str, Any],
) -> bool:
    try:
        original = _source_row(
            promise, reroute["original_source_id"]
        )
        if reroute.get("kind") != REROUTE_KIND:
            return False
        if reroute.get("version") != REROUTE_VERSION:
            return False
        if (
            reroute.get("authority")
            != "promisor-route-substitution-only"
        ):
            return False
        if reroute.get("promise_id") != promise["promise_id"]:
            return False
        if (
            reroute.get("promisor_particular")
            != promise["promisor_particular"]
        ):
            return False
        if (
            reroute.get("original_capacity_guild_id")
            != original["capacity_guild_id"]
        ):
            return False
        if reroute.get("original_route_status") != "RELEASED":
            return False
        if not verify_remote_capacity_proof(
            substitute_snapshot, substitute_proof
        ):
            return False
        if (
            reroute.get("substitute_capacity_guild_id")
            != substitute_proof["capacity_guild_id"]
        ):
            return False
        if (
            reroute.get("substitute_snapshot_id")
            != substitute_proof["snapshot_id"]
        ):
            return False
        if (
            reroute.get("substitute_remote_proof_id")
            != substitute_proof["remote_proof_id"]
        ):
            return False
        if (
            reroute.get("substitute_resource_entry_id")
            != substitute_proof["resource_entry_id"]
        ):
            return False
        if reroute.get("replacement_measure") != original["measure"]:
            return False
        if reroute.get("promise_rewritten") is not False:
            return False
        if reroute.get("ownership_transfer") is not False:
            return False
        if reroute.get("old_authority_counts") is not False:
            return False
        if reroute.get("substitute_reserved") is not False:
            return False
        return _verify_signed(
            reroute,
            id_field="reroute_id",
            particular_field="promisor_particular",
            domain=REROUTE_DOMAIN,
            byte_domain=REROUTE_BYTES,
        )
    except Exception:
        return False


def make_substitute_request(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    promise: dict[str, Any],
    substitute_snapshot: dict[str, Any],
    substitute_proof: dict[str, Any],
    reroute: dict[str, Any],
    *,
    promisor: IdentityKey,
    requested_at_cut: int,
) -> dict[str, Any]:
    if not verify_reroute(
        promise, substitute_snapshot, substitute_proof, reroute
    ):
        raise LightwalkerEconomyError("invalid reroute")
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid customer acceptance")
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError("request signer is not promisor")
    cut = _nni(requested_at_cut, "requested_at_cut")
    if cut > int(substitute_proof["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "substitute proof expired before request"
        )
    body = {
        "kind": REQUEST_KIND,
        "version": REQUEST_VERSION,
        "authority": "promisor-substitute-request-only",
        "promisor_particular": promisor.particular(),
        "promise_id": promise["promise_id"],
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "reroute_id": reroute["reroute_id"],
        "original_source_id": reroute["original_source_id"],
        "substitute_capacity_guild_id": substitute_proof[
            "capacity_guild_id"
        ],
        "substitute_snapshot_id": substitute_proof["snapshot_id"],
        "substitute_remote_proof_id": substitute_proof["remote_proof_id"],
        "substitute_resource_entry_id": substitute_proof[
            "resource_entry_id"
        ],
        "requested_measure": reroute["replacement_measure"],
        "requested_at_cut": cut,
        "reservation_authority": "none",
        "ownership_transfer_requested": False,
        "laws": [
            "SOURCE SUBSTITUTION != PROMISE REWRITE",
            "SUBSTITUTE REQUEST != SUBSTITUTE RESERVATION",
            "REROUTE REQUIRES NEW EVIDENCE",
        ],
    }
    return _signed(
        body,
        id_field="request_id",
        signer=promisor,
        domain=REQUEST_DOMAIN,
        byte_domain=REQUEST_BYTES,
    )


def reserve_substitute(
    substitute_snapshot: dict[str, Any],
    substitute_proof: dict[str, Any],
    reroute: dict[str, Any],
    request: dict[str, Any],
    *,
    capacity_steward: IdentityKey,
    executor_particular: str,
    reservation_store: GuildReservationStore,
    reserved_at_cut: int,
    expires_after_cut: int,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    if not verify_remote_capacity_proof(
        substitute_snapshot, substitute_proof
    ):
        raise LightwalkerEconomyError("invalid substitute proof")
    if not _verify_signed(
        request,
        id_field="request_id",
        particular_field="promisor_particular",
        domain=REQUEST_DOMAIN,
        byte_domain=REQUEST_BYTES,
    ):
        raise LightwalkerEconomyError("invalid substitute request")
    if request.get("reroute_id") != reroute["reroute_id"]:
        raise LightwalkerEconomyError("request reroute mismatch")
    if request.get("requested_measure") != reroute["replacement_measure"]:
        raise LightwalkerEconomyError("request measure mismatch")
    if (
        request.get("substitute_snapshot_id")
        != substitute_snapshot["snapshot_id"]
    ):
        raise LightwalkerEconomyError("substitute snapshot mismatch")
    if (
        request.get("substitute_remote_proof_id")
        != substitute_proof["remote_proof_id"]
    ):
        raise LightwalkerEconomyError("substitute proof mismatch")
    if capacity_steward.particular() != substitute_snapshot[
        "steward_particular"
    ]:
        raise LightwalkerEconomyError(
            "only substitute Guild may reserve substitute capacity"
        )

    proposal = make_resource_proposal(
        substitute_snapshot,
        proposer=capacity_steward,
        resource_entry_id=substitute_proof["resource_entry_id"],
        requested_quantity=int(request["requested_measure"]["quantity"]),
        requested_unit=request["requested_measure"]["unit"],
        purpose_ref="reroute:" + reroute["reroute_id"],
        proposed_at_cut=_nni(reserved_at_cut, "reserved_at_cut"),
    )
    authorization, reservation = reservation_store.reserve_and_authorize(
        substitute_snapshot,
        proposal,
        executor_particular=_nonempty(
            executor_particular, "executor_particular"
        ),
        authorized_at_cut=reserved_at_cut,
        expires_after_cut=expires_after_cut,
    )
    body = {
        "kind": GRANT_KIND,
        "version": GRANT_VERSION,
        "authority": "substitute-guild-local-reservation-grant",
        "capacity_guild_id": substitute_snapshot["guild_id"],
        "capacity_steward_particular": capacity_steward.particular(),
        "snapshot_id": substitute_snapshot["snapshot_id"],
        "reroute_id": reroute["reroute_id"],
        "original_source_id": reroute["original_source_id"],
        "request_id": request["request_id"],
        "promise_id": reroute["promise_id"],
        "remote_proof_id": substitute_proof["remote_proof_id"],
        "proposal_id": proposal["proposal_id"],
        "authorization_id": authorization["authorization_id"],
        "reservation_id": reservation["reservation_id"],
        "resource_entry_id": substitute_proof["resource_entry_id"],
        "reserved_measure": request["requested_measure"],
        "executor_particular": authorization["executor_particular"],
        "status": "SUBSTITUTE_RESERVED",
        "old_authority_counts": False,
        "ownership_transfer": False,
        "laws": [
            "OLD AUTHORITY MUST STOP COUNTING BEFORE SUBSTITUTE AUTHORITY COUNTS",
            "SOURCE SUBSTITUTION != PROMISE REWRITE",
            "AGGREGATION != OWNERSHIP",
        ],
    }
    grant = _signed(
        body,
        id_field="grant_id",
        signer=capacity_steward,
        domain=GRANT_DOMAIN,
        byte_domain=GRANT_BYTES,
    )
    return proposal, authorization, reservation, grant


def verify_substitute_grant(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
    reroute: dict[str, Any],
    request: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    grant: dict[str, Any],
) -> bool:
    try:
        if not verify_remote_capacity_proof(snapshot, proof):
            return False
        if not verify_reservation(
            snapshot, proposal, authorization, reservation
        ):
            return False
        if grant.get("kind") != GRANT_KIND:
            return False
        if grant.get("version") != GRANT_VERSION:
            return False
        if (
            grant.get("authority")
            != "substitute-guild-local-reservation-grant"
        ):
            return False
        if grant.get("reroute_id") != reroute["reroute_id"]:
            return False
        if (
            grant.get("original_source_id")
            != reroute["original_source_id"]
        ):
            return False
        if grant.get("request_id") != request["request_id"]:
            return False
        if grant.get("proposal_id") != proposal["proposal_id"]:
            return False
        if grant.get("authorization_id") != authorization[
            "authorization_id"
        ]:
            return False
        if grant.get("reservation_id") != reservation["reservation_id"]:
            return False
        if grant.get("reserved_measure") != reroute["replacement_measure"]:
            return False
        if proposal.get("purpose_ref") != "reroute:" + reroute["reroute_id"]:
            return False
        if grant.get("old_authority_counts") is not False:
            return False
        if grant.get("ownership_transfer") is not False:
            return False
        return _verify_signed(
            grant,
            id_field="grant_id",
            particular_field="capacity_steward_particular",
            domain=GRANT_DOMAIN,
            byte_domain=GRANT_BYTES,
        )
    except Exception:
        return False


def make_substitute_completion(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
    reroute: dict[str, Any],
    request: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    grant: dict[str, Any],
    execution_receipt: dict[str, Any],
    finalization: dict[str, Any],
    *,
    capacity_steward: IdentityKey,
) -> dict[str, Any]:
    if not verify_substitute_grant(
        snapshot,
        proof,
        reroute,
        request,
        proposal,
        authorization,
        reservation,
        grant,
    ):
        raise LightwalkerEconomyError("invalid substitute grant")
    if not verify_execution_receipt(
        snapshot, proposal, authorization, execution_receipt
    ):
        raise LightwalkerEconomyError(
            "invalid substitute execution receipt"
        )
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError(
            "invalid substitute finalization"
        )
    if execution_receipt.get("success") is not True:
        raise LightwalkerEconomyError(
            "failed substitute cannot prove completion"
        )
    if finalization.get("status") != "CONSUMED":
        raise LightwalkerEconomyError(
            "substitute completion requires consumed reservation"
        )
    if capacity_steward.particular() != grant[
        "capacity_steward_particular"
    ]:
        raise LightwalkerEconomyError("substitute completion signer mismatch")
    body = {
        "kind": COMPLETION_KIND,
        "version": COMPLETION_VERSION,
        "authority": "substitute-guild-performance",
        "capacity_guild_id": grant["capacity_guild_id"],
        "capacity_steward_particular": capacity_steward.particular(),
        "reroute_id": reroute["reroute_id"],
        "original_source_id": reroute["original_source_id"],
        "grant_id": grant["grant_id"],
        "reservation_id": reservation["reservation_id"],
        "execution_receipt_id": execution_receipt["execution_receipt_id"],
        "finalization_id": finalization["finalization_id"],
        "performed_measure": reroute["replacement_measure"],
        "status": "FULFILLED",
        "promise_rewritten": False,
        "ownership_transfer": False,
        "laws": [
            "SUBSTITUTE COMPLETION MAY SATISFY THE SAME DECLARED SERVICE",
            "SOURCE SUBSTITUTION != PROMISE REWRITE",
            "ROUTE HISTORY != SERVICE SEMANTICS",
        ],
    }
    return _signed(
        body,
        id_field="completion_id",
        signer=capacity_steward,
        domain=COMPLETION_DOMAIN,
        byte_domain=COMPLETION_BYTES,
    )


def derive_rerouted_backing(
    promise: dict[str, Any],
    *,
    original_grants: list[dict[str, Any]],
    reroutes: list[dict[str, Any]],
    substitute_grants: list[dict[str, Any]],
) -> dict[str, Any]:
    reroute_by_source: dict[str, dict[str, Any]] = {}
    for reroute in reroutes:
        source_id = reroute["original_source_id"]
        if source_id in reroute_by_source:
            raise LightwalkerEconomyError(
                "v0 allows at most one reroute per original source slot"
            )
        reroute_by_source[source_id] = reroute

    original_by_source = {
        grant["source_id"]: grant for grant in original_grants
    }
    substitute_by_source = {
        grant["original_source_id"]: grant
        for grant in substitute_grants
    }
    effective_ids: list[str] = []
    missing: list[str] = []
    reserved = 0
    route_rows: list[dict[str, Any]] = []

    for source in promise["sources"]:
        source_id = source["source_id"]
        reroute = reroute_by_source.get(source_id)
        if reroute is not None:
            grant = substitute_by_source.get(source_id)
            if grant is None:
                missing.append(source_id)
                route_rows.append(
                    {
                        "original_source_id": source_id,
                        "route": "SUBSTITUTED_PENDING",
                        "effective_grant_id": None,
                    }
                )
                continue
            if grant["reroute_id"] != reroute["reroute_id"]:
                raise LightwalkerEconomyError(
                    "substitute grant belongs to another reroute"
                )
            effective_ids.append(grant["grant_id"])
            reserved += int(grant["reserved_measure"]["quantity"])
            route_rows.append(
                {
                    "original_source_id": source_id,
                    "route": "SUBSTITUTE",
                    "effective_grant_id": grant["grant_id"],
                    "retired_original_grant_id": reroute[
                        "original_grant_id"
                    ],
                }
            )
        else:
            grant = original_by_source.get(source_id)
            if grant is None:
                missing.append(source_id)
                route_rows.append(
                    {
                        "original_source_id": source_id,
                        "route": "ORIGINAL_PENDING",
                        "effective_grant_id": None,
                    }
                )
                continue
            effective_ids.append(grant["grant_id"])
            reserved += int(grant["reserved_measure"]["quantity"])
            route_rows.append(
                {
                    "original_source_id": source_id,
                    "route": "ORIGINAL",
                    "effective_grant_id": grant["grant_id"],
                }
            )

    required = int(promise["promised_measure"]["quantity"])
    status = "COMPLETE" if not missing and reserved == required else "PARTIAL"
    body = {
        "kind": BACKING_KIND,
        "version": BACKING_VERSION,
        "authority": "derived-rerouted-backing-view",
        "promise_id": promise["promise_id"],
        "reroute_ids": sorted(
            reroute["reroute_id"] for reroute in reroutes
        ),
        "effective_grant_ids": sorted(effective_ids),
        "missing_source_slot_ids": sorted(missing),
        "routes": sorted(
            route_rows, key=lambda row: row["original_source_id"]
        ),
        "required_measure": promise["promised_measure"],
        "reserved_measure": {
            "unit": promise["promised_measure"]["unit"],
            "quantity": reserved,
        },
        "status": status,
        "execution_authority": "none",
        "ownership_aggregated": False,
        "promise_rewritten": False,
        "laws": [
            "SOURCE SUBSTITUTION != PROMISE REWRITE",
            "OLD AUTHORITY MUST STOP COUNTING BEFORE SUBSTITUTE AUTHORITY COUNTS",
            "ROUTE HISTORY != SERVICE SEMANTICS",
        ],
    }
    return {**body, "backing_id": content_address(body)}


def derive_rerouted_completion(
    promise: dict[str, Any],
    *,
    original_completions: list[dict[str, Any]],
    reroutes: list[dict[str, Any]],
    substitute_completions: list[dict[str, Any]],
) -> dict[str, Any]:
    reroute_by_source = {
        item["original_source_id"]: item for item in reroutes
    }
    original_by_source = {
        item["source_id"]: item for item in original_completions
    }
    substitute_by_source = {
        item["original_source_id"]: item
        for item in substitute_completions
    }

    completion_ids: list[str] = []
    missing: list[str] = []
    performed = 0
    route_rows: list[dict[str, Any]] = []
    for source in promise["sources"]:
        source_id = source["source_id"]
        reroute = reroute_by_source.get(source_id)
        if reroute is not None:
            completion = substitute_by_source.get(source_id)
            if completion is None:
                missing.append(source_id)
                route_rows.append(
                    {
                        "original_source_id": source_id,
                        "route": "SUBSTITUTE_PENDING",
                        "effective_completion_id": None,
                    }
                )
                continue
            if completion["reroute_id"] != reroute["reroute_id"]:
                raise LightwalkerEconomyError(
                    "substitute completion belongs to another reroute"
                )
            completion_ids.append(completion["completion_id"])
            performed += int(
                completion["performed_measure"]["quantity"]
            )
            route_rows.append(
                {
                    "original_source_id": source_id,
                    "route": "SUBSTITUTE",
                    "effective_completion_id": completion[
                        "completion_id"
                    ],
                }
            )
        else:
            completion = original_by_source.get(source_id)
            if completion is None:
                missing.append(source_id)
                route_rows.append(
                    {
                        "original_source_id": source_id,
                        "route": "ORIGINAL_PENDING",
                        "effective_completion_id": None,
                    }
                )
                continue
            completion_ids.append(completion["completion_id"])
            performed += int(
                completion["performed_measure"]["quantity"]
            )
            route_rows.append(
                {
                    "original_source_id": source_id,
                    "route": "ORIGINAL",
                    "effective_completion_id": completion[
                        "completion_id"
                    ],
                }
            )

    required = int(promise["promised_measure"]["quantity"])
    status = "COMPLETE" if not missing and performed == required else "PARTIAL"
    body = {
        "kind": AGGREGATE_KIND,
        "version": AGGREGATE_VERSION,
        "authority": "derived-rerouted-service-completion",
        "promise_id": promise["promise_id"],
        "reroute_ids": sorted(
            reroute["reroute_id"] for reroute in reroutes
        ),
        "effective_completion_ids": sorted(completion_ids),
        "missing_source_slot_ids": sorted(missing),
        "routes": sorted(
            route_rows, key=lambda row: row["original_source_id"]
        ),
        "performed_measure": {
            "unit": promise["promised_measure"]["unit"],
            "quantity": performed,
        },
        "required_measure": promise["promised_measure"],
        "status": status,
        "customer_performance_proven": False,
        "execution_authority": "none",
        "ownership_aggregated": False,
        "promise_rewritten": False,
        "laws": [
            "SUBSTITUTE COMPLETION MAY SATISFY THE SAME DECLARED SERVICE",
            "SOURCE SUBSTITUTION != PROMISE REWRITE",
            "ROUTE HISTORY != SERVICE SEMANTICS",
        ],
    }
    return {**body, "aggregate_id": content_address(body)}


def attest_rerouted_performance(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    promise: dict[str, Any],
    aggregate: dict[str, Any],
    *,
    promisor: IdentityKey,
) -> dict[str, Any]:
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid customer acceptance")
    if aggregate.get("kind") != AGGREGATE_KIND:
        raise LightwalkerEconomyError("invalid rerouted aggregate")
    if aggregate.get("promise_id") != promise["promise_id"]:
        raise LightwalkerEconomyError(
            "aggregate belongs to another promise"
        )
    if aggregate.get("status") != "COMPLETE":
        raise LightwalkerEconomyError(
            "rerouted service is not fully complete"
        )
    if aggregate.get("performed_measure") != promise["promised_measure"]:
        raise LightwalkerEconomyError(
            "rerouted aggregate does not fulfill declared service"
        )
    if aggregate.get("promise_rewritten") is not False:
        raise LightwalkerEconomyError("promise rewrite detected")
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError("performance signer is not promisor")
    return sign_obligation_performance(
        offer,
        acceptance,
        role="OFFEROR",
        signer=promisor,
        evidence_ref=aggregate["aggregate_id"],
    )


def derive_rerouted_settlement(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    promise: dict[str, Any],
    aggregate: dict[str, Any],
    promisor_attestation: dict[str, Any],
    customer_attestation: dict[str, Any],
    settlement: dict[str, Any],
) -> dict[str, Any]:
    if aggregate.get("status") != "COMPLETE":
        raise LightwalkerEconomyError(
            "settlement requires complete rerouted service"
        )
    if not verify_obligation_performance(
        offer, acceptance, promisor_attestation
    ):
        raise LightwalkerEconomyError(
            "invalid promisor performance attestation"
        )
    if (
        promisor_attestation.get("evidence_ref")
        != aggregate["aggregate_id"]
    ):
        raise LightwalkerEconomyError(
            "performance does not bind exact rerouted aggregate"
        )
    if not verify_obligation_performance(
        offer, acceptance, customer_attestation
    ):
        raise LightwalkerEconomyError(
            "invalid customer performance attestation"
        )
    if not verify_exchange_settlement(
        offer,
        acceptance,
        [promisor_attestation, customer_attestation],
        settlement,
    ):
        raise LightwalkerEconomyError(
            "invalid rerouted downstream settlement"
        )
    body = {
        "kind": SETTLEMENT_KIND,
        "version": SETTLEMENT_VERSION,
        "authority": "derived-rerouted-service-linkage",
        "promisor_particular": promise["promisor_particular"],
        "promise_id": promise["promise_id"],
        "reroute_ids": aggregate["reroute_ids"],
        "aggregate_id": aggregate["aggregate_id"],
        "promisor_attestation_id": promisor_attestation["attestation_id"],
        "customer_attestation_id": customer_attestation["attestation_id"],
        "settlement_id": settlement["settlement_id"],
        "performed_measure": aggregate["performed_measure"],
        "customer_service_performed": True,
        "promise_rewritten": False,
        "route_history_preserved": True,
        "ownership_aggregated": False,
        "payment_inferred_from_route_execution": False,
        "laws": [
            "SOURCE SUBSTITUTION != PROMISE REWRITE",
            "SUBSTITUTE COMPLETION MAY SATISFY THE SAME DECLARED SERVICE",
            "ROUTE HISTORY != SERVICE SEMANTICS",
        ],
    }
    return {**body, "witness_id": content_address(body)}


def make_reroute_crossing(
    evidence: dict[str, Any],
    *,
    signer: IdentityKey,
    declared_kind: str,
    destination_particular: str,
) -> dict[str, Any]:
    id_fields = (
        "reroute_id",
        "request_id",
        "grant_id",
        "completion_id",
        "witness_id",
    )
    evidence_id = next(
        (
            evidence[field]
            for field in id_fields
            if isinstance(evidence.get(field), str)
        ),
        None,
    )
    if evidence_id is None:
        raise LightwalkerEconomyError(
            "reroute evidence lacks content identifier"
        )
    kind = evidence.get("kind")
    if kind in {REROUTE_KIND, REQUEST_KIND, SETTLEMENT_KIND}:
        expected = evidence.get("promisor_particular")
    elif kind in {GRANT_KIND, COMPLETION_KIND, FAILURE_KIND}:
        expected = evidence.get("capacity_steward_particular")
    else:
        raise LightwalkerEconomyError(
            "unsupported reroute evidence kind"
        )
    if signer.particular() != expected:
        raise LightwalkerEconomyError(
            "crossing signer does not own reroute evidence role"
        )
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": "ghot:federated-reroute",
        "source_history_head": evidence_id,
        "parents": [],
        "declared_kind": declared_kind,
        "payload_refs": [evidence_id],
        "requested_effect": identity_safe(
            {
                "operation": "consider-federated-reroute-evidence",
                "evidence_id": evidence_id,
                "promise_rewrite_requested": False,
                "automatic_reservation_requested": False,
                "automatic_execution_requested": False,
                "ownership_transfer_requested": False,
            }
        ),
        "capability_ref": REROUTE_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {
            "destination_particular": _nonempty(
                destination_particular, "destination_particular"
            )
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-federated-reroute/v0",
            "promise_is_immutable": True,
            "route_history_is_not_service_semantics": True,
        },
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("reroute crossing failed")
    return signed


__all__ = [
    "attest_rerouted_performance",
    "derive_rerouted_backing",
    "derive_rerouted_completion",
    "derive_rerouted_settlement",
    "make_reroute",
    "make_reroute_crossing",
    "make_substitute_completion",
    "make_substitute_request",
    "reserve_substitute",
    "verify_reroute",
    "verify_substitute_grant",
]
