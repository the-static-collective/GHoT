#!/usr/bin/env python3
"""Lightwalker Multi-Source Federated Service 001.

One customer-facing promise may depend on multiple sovereign capacity sources.
No partial source state is allowed to masquerade as full backing or full
customer performance.

Core laws:
    ONE PROMISE MAY DEPEND ON MULTIPLE SOVEREIGN SOURCES
    PARTIAL RESERVATION != FULL BACKING
    PARTIAL COMPLETION != CUSTOMER PERFORMANCE
    SOURCE FAILURE RELEASES ONLY ITS OWN AUTHORITY
    AGGREGATION != OWNERSHIP
    ALL REQUIRED SUBCONTRACTS MUST COMPLETE BEFORE DOWNSTREAM PERFORMANCE
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
    verify_exchange_offer,
    verify_exchange_settlement,
    verify_obligation_performance,
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


PROMISE_KIND = "ghot.lightwalker.multi-source-service-promise"
PROMISE_VERSION = "0"
REQUEST_KIND = "ghot.lightwalker.multi-source-subcontract-request"
REQUEST_VERSION = "0"
GRANT_KIND = "ghot.lightwalker.multi-source-subcontract-grant"
GRANT_VERSION = "0"
BACKING_KIND = "ghot.lightwalker.multi-source-backing-view"
BACKING_VERSION = "0"
COMPLETION_KIND = "ghot.lightwalker.multi-source-subcontract-completion"
COMPLETION_VERSION = "0"
FAILURE_KIND = "ghot.lightwalker.multi-source-subcontract-failure"
FAILURE_VERSION = "0"
AGGREGATE_KIND = "ghot.lightwalker.multi-source-completion"
AGGREGATE_VERSION = "0"
SETTLEMENT_KIND = "ghot.lightwalker.multi-source-service-settlement"
SETTLEMENT_VERSION = "0"

PROMISE_DOMAIN = "ghot.lightwalker-multi-source-service-promise-signature/v0"
REQUEST_DOMAIN = "ghot.lightwalker-multi-source-subcontract-request-signature/v0"
GRANT_DOMAIN = "ghot.lightwalker-multi-source-subcontract-grant-signature/v0"
COMPLETION_DOMAIN = "ghot.lightwalker-multi-source-subcontract-completion-signature/v0"
FAILURE_DOMAIN = "ghot.lightwalker-multi-source-subcontract-failure-signature/v0"

PROMISE_BYTES = b"GHOT-LightwalkerMultiSourceServicePromise-v0|"
REQUEST_BYTES = b"GHOT-LightwalkerMultiSourceSubcontractRequest-v0|"
GRANT_BYTES = b"GHOT-LightwalkerMultiSourceSubcontractGrant-v0|"
COMPLETION_BYTES = b"GHOT-LightwalkerMultiSourceSubcontractCompletion-v0|"
FAILURE_BYTES = b"GHOT-LightwalkerMultiSourceSubcontractFailure-v0|"

MULTI_SOURCE_CAPABILITY = "ghot.lightwalker-multi-source-service/v0"


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


def _service_obligation(
    offer: dict[str, Any],
    promisor_particular: str,
) -> dict[str, Any]:
    if not verify_exchange_offer(offer):
        raise LightwalkerEconomyError("invalid customer-facing offer")
    if offer["offeror_particular"] != promisor_particular:
        raise LightwalkerEconomyError(
            "multi-source promisor must be economic offeror"
        )
    obligation = offer["offeror_obligation"]
    if obligation.get("obligation_type") != "future-compute-service":
        raise LightwalkerEconomyError(
            "offeror obligation is not future compute service"
        )
    return obligation


def _normalize_sources(
    remote_sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(remote_sources, list) or len(remote_sources) < 2:
        raise LightwalkerEconomyError(
            "multi-source promise requires at least two sovereign sources"
        )
    rows: list[dict[str, Any]] = []
    seen_guilds: set[str] = set()
    seen_proofs: set[str] = set()
    for item in remote_sources:
        snapshot = item.get("snapshot")
        proof = item.get("proof")
        quantity = _nni(item.get("quantity"), "source quantity")
        if quantity <= 0:
            raise LightwalkerEconomyError("source quantity must be > 0")
        if not isinstance(snapshot, dict) or not isinstance(proof, dict):
            raise LightwalkerEconomyError(
                "each source requires snapshot and proof"
            )
        if not verify_remote_capacity_proof(snapshot, proof):
            raise LightwalkerEconomyError(
                "invalid remote capacity proof in source plan"
            )
        guild_id = proof["capacity_guild_id"]
        proof_id = proof["remote_proof_id"]
        if guild_id in seen_guilds:
            raise LightwalkerEconomyError(
                "v0 requires distinct capacity Guilds per source"
            )
        if proof_id in seen_proofs:
            raise LightwalkerEconomyError("duplicate remote proof")
        seen_guilds.add(guild_id)
        seen_proofs.add(proof_id)
        if quantity > int(proof["native_measure"]["quantity"]):
            raise LightwalkerEconomyError(
                "source share exceeds remotely proven capacity"
            )
        row_body = {
            "capacity_guild_id": guild_id,
            "snapshot_id": proof["snapshot_id"],
            "remote_proof_id": proof_id,
            "resource_entry_id": proof["resource_entry_id"],
            "capacity_steward_particular": proof[
                "capacity_steward_particular"
            ],
            "measure": {
                "unit": proof["native_measure"]["unit"],
                "quantity": quantity,
            },
            "valid_through_cut": int(proof["valid_through_cut"]),
        }
        rows.append(
            {
                **row_body,
                "source_id": content_address(row_body),
            }
        )
    return sorted(rows, key=lambda row: row["source_id"])


def make_multi_source_promise(
    offer: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    *,
    promisor: IdentityKey,
    promised_at_cut: int,
) -> dict[str, Any]:
    obligation = _service_obligation(offer, promisor.particular())
    terms = obligation.get("terms")
    if not isinstance(terms, dict):
        raise LightwalkerEconomyError("service terms missing")
    unit = _nonempty(terms.get("unit"), "service unit")
    quantity = _nni(terms.get("quantity"), "service quantity")
    if quantity <= 0:
        raise LightwalkerEconomyError("service quantity must be > 0")

    sources = _normalize_sources(remote_sources)
    if any(row["measure"]["unit"] != unit for row in sources):
        raise LightwalkerEconomyError(
            "all source units must match service obligation"
        )
    source_total = sum(int(row["measure"]["quantity"]) for row in sources)
    if source_total != quantity:
        raise LightwalkerEconomyError(
            "source plan must exactly equal promised service quantity"
        )
    cut = _nni(promised_at_cut, "promised_at_cut")
    backing_valid_through = min(
        int(row["valid_through_cut"]) for row in sources
    )
    if cut > backing_valid_through:
        raise LightwalkerEconomyError(
            "one or more source proofs expired before promise"
        )
    if cut > int(offer["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "customer-facing offer expired before promise"
        )

    body = {
        "kind": PROMISE_KIND,
        "version": PROMISE_VERSION,
        "authority": "promisor-multi-source-economic-promise-only",
        "promisor_particular": promisor.particular(),
        "offer_id": offer["offer_id"],
        "service_obligation_id": obligation["obligation_id"],
        "promised_measure": {
            "unit": unit,
            "quantity": quantity,
        },
        "sources": sources,
        "promised_at_cut": cut,
        "valid_through_cut": min(
            int(offer["valid_through_cut"]),
            backing_valid_through,
        ),
        "sources_reserved": 0,
        "full_backing_proven": False,
        "local_execution_authority": False,
        "ownership_aggregated": False,
        "laws": [
            "ONE PROMISE MAY DEPEND ON MULTIPLE SOVEREIGN SOURCES",
            "PARTIAL RESERVATION != FULL BACKING",
            "AGGREGATION != OWNERSHIP",
        ],
    }
    return _signed(
        body,
        id_field="promise_id",
        signer=promisor,
        domain=PROMISE_DOMAIN,
        byte_domain=PROMISE_BYTES,
    )


def verify_multi_source_promise(
    offer: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
) -> bool:
    try:
        obligation = _service_obligation(
            offer, promise["promisor_particular"]
        )
        normalized = _normalize_sources(remote_sources)
        if promise.get("kind") != PROMISE_KIND:
            return False
        if promise.get("version") != PROMISE_VERSION:
            return False
        if (
            promise.get("authority")
            != "promisor-multi-source-economic-promise-only"
        ):
            return False
        if promise.get("offer_id") != offer["offer_id"]:
            return False
        if (
            promise.get("service_obligation_id")
            != obligation["obligation_id"]
        ):
            return False
        if promise.get("sources") != normalized:
            return False
        terms = obligation.get("terms")
        if not isinstance(terms, dict):
            return False
        if promise.get("promised_measure") != {
            "unit": terms.get("unit"),
            "quantity": terms.get("quantity"),
        }:
            return False
        if promise.get("sources_reserved") != 0:
            return False
        if promise.get("full_backing_proven") is not False:
            return False
        if promise.get("local_execution_authority") is not False:
            return False
        if promise.get("ownership_aggregated") is not False:
            return False
        if int(promise.get("promised_at_cut", -1)) < 0:
            return False
        if int(promise["promised_at_cut"]) > int(
            promise["valid_through_cut"]
        ):
            return False
        return _verify_signed(
            promise,
            id_field="promise_id",
            particular_field="promisor_particular",
            domain=PROMISE_DOMAIN,
            byte_domain=PROMISE_BYTES,
        )
    except Exception:
        return False


def _source_row(
    promise: dict[str, Any],
    source_id: str,
) -> dict[str, Any]:
    matches = [
        row for row in promise["sources"] if row["source_id"] == source_id
    ]
    if len(matches) != 1:
        raise LightwalkerEconomyError("unknown source id")
    return matches[0]


def make_source_request(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    *,
    source_id: str,
    promisor: IdentityKey,
    requested_at_cut: int,
) -> dict[str, Any]:
    if not verify_multi_source_promise(
        offer, remote_sources, promise
    ):
        raise LightwalkerEconomyError("invalid multi-source promise")
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid customer acceptance")
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError("requester is not promisor")
    source = _source_row(promise, source_id)
    cut = _nni(requested_at_cut, "requested_at_cut")
    if cut > int(promise["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "source request occurs after backing validity"
        )
    body = {
        "kind": REQUEST_KIND,
        "version": REQUEST_VERSION,
        "authority": "promisor-source-request-only",
        "promisor_particular": promisor.particular(),
        "promise_id": promise["promise_id"],
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "source_id": source["source_id"],
        "capacity_guild_id": source["capacity_guild_id"],
        "remote_proof_id": source["remote_proof_id"],
        "snapshot_id": source["snapshot_id"],
        "resource_entry_id": source["resource_entry_id"],
        "requested_measure": source["measure"],
        "requested_at_cut": cut,
        "reservation_authority": "none",
        "ownership_transfer_requested": False,
        "laws": [
            "PARTIAL RESERVATION != FULL BACKING",
            "SOURCE REQUEST != SOURCE RESERVATION",
            "AGGREGATION != OWNERSHIP",
        ],
    }
    return _signed(
        body,
        id_field="request_id",
        signer=promisor,
        domain=REQUEST_DOMAIN,
        byte_domain=REQUEST_BYTES,
    )


def verify_source_request(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    request: dict[str, Any],
) -> bool:
    try:
        if not verify_multi_source_promise(
            offer, remote_sources, promise
        ):
            return False
        if not verify_exchange_acceptance(offer, acceptance):
            return False
        source = _source_row(promise, request["source_id"])
        if request.get("kind") != REQUEST_KIND:
            return False
        if request.get("version") != REQUEST_VERSION:
            return False
        if request.get("authority") != "promisor-source-request-only":
            return False
        if request.get("promisor_particular") != promise["promisor_particular"]:
            return False
        if request.get("promise_id") != promise["promise_id"]:
            return False
        if request.get("acceptance_id") != acceptance["acceptance_id"]:
            return False
        if request.get("capacity_guild_id") != source["capacity_guild_id"]:
            return False
        if request.get("remote_proof_id") != source["remote_proof_id"]:
            return False
        if request.get("snapshot_id") != source["snapshot_id"]:
            return False
        if request.get("resource_entry_id") != source["resource_entry_id"]:
            return False
        if request.get("requested_measure") != source["measure"]:
            return False
        if request.get("reservation_authority") != "none":
            return False
        if request.get("ownership_transfer_requested") is not False:
            return False
        return _verify_signed(
            request,
            id_field="request_id",
            particular_field="promisor_particular",
            domain=REQUEST_DOMAIN,
            byte_domain=REQUEST_BYTES,
        )
    except Exception:
        return False


def reserve_source(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
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
    if not verify_remote_capacity_proof(snapshot, proof):
        raise LightwalkerEconomyError("invalid source capacity proof")
    if request.get("snapshot_id") != snapshot["snapshot_id"]:
        raise LightwalkerEconomyError(
            "source request references another snapshot"
        )
    if request.get("remote_proof_id") != proof["remote_proof_id"]:
        raise LightwalkerEconomyError(
            "source request references another proof"
        )
    if request.get("resource_entry_id") != proof["resource_entry_id"]:
        raise LightwalkerEconomyError(
            "source request references another resource"
        )
    if request.get("capacity_guild_id") != snapshot["guild_id"]:
        raise LightwalkerEconomyError(
            "source request references another Guild"
        )
    if not _verify_signed(
        request,
        id_field="request_id",
        particular_field="promisor_particular",
        domain=REQUEST_DOMAIN,
        byte_domain=REQUEST_BYTES,
    ):
        raise LightwalkerEconomyError("invalid source request signature")
    if capacity_steward.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError(
            "only source steward may reserve source capacity"
        )
    cut = _nni(reserved_at_cut, "reserved_at_cut")
    if cut > int(proof["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "source proof expired before reservation"
        )

    proposal = make_resource_proposal(
        snapshot,
        proposer=capacity_steward,
        resource_entry_id=proof["resource_entry_id"],
        requested_quantity=int(
            request["requested_measure"]["quantity"]
        ),
        requested_unit=request["requested_measure"]["unit"],
        purpose_ref="multi-source:" + request["request_id"],
        proposed_at_cut=cut,
    )
    authorization, reservation = reservation_store.reserve_and_authorize(
        snapshot,
        proposal,
        executor_particular=_nonempty(
            executor_particular, "executor_particular"
        ),
        authorized_at_cut=cut,
        expires_after_cut=expires_after_cut,
    )
    body = {
        "kind": GRANT_KIND,
        "version": GRANT_VERSION,
        "authority": "source-guild-local-reservation-grant",
        "capacity_guild_id": snapshot["guild_id"],
        "capacity_steward_particular": capacity_steward.particular(),
        "snapshot_id": snapshot["snapshot_id"],
        "source_id": request["source_id"],
        "request_id": request["request_id"],
        "promise_id": request["promise_id"],
        "remote_proof_id": proof["remote_proof_id"],
        "proposal_id": proposal["proposal_id"],
        "authorization_id": authorization["authorization_id"],
        "reservation_id": reservation["reservation_id"],
        "resource_entry_id": proof["resource_entry_id"],
        "reserved_measure": request["requested_measure"],
        "executor_particular": authorization["executor_particular"],
        "status": "SOURCE_RESERVED",
        "promisor_execution_authority": False,
        "ownership_transfer": False,
        "laws": [
            "PARTIAL RESERVATION != FULL BACKING",
            "AGGREGATION != OWNERSHIP",
            "SOURCE AUTHORITY REMAINS SOURCE-LOCAL",
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


def verify_source_grant(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
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
            != "source-guild-local-reservation-grant"
        ):
            return False
        if grant.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if grant.get("request_id") != request["request_id"]:
            return False
        if grant.get("source_id") != request["source_id"]:
            return False
        if grant.get("remote_proof_id") != proof["remote_proof_id"]:
            return False
        if grant.get("proposal_id") != proposal["proposal_id"]:
            return False
        if grant.get("authorization_id") != authorization["authorization_id"]:
            return False
        if grant.get("reservation_id") != reservation["reservation_id"]:
            return False
        if grant.get("reserved_measure") != request["requested_measure"]:
            return False
        if proposal.get("purpose_ref") != (
            "multi-source:" + request["request_id"]
        ):
            return False
        if grant.get("promisor_execution_authority") is not False:
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


def derive_backing_view(
    promise: dict[str, Any],
    grants: list[dict[str, Any]],
) -> dict[str, Any]:
    grant_by_source: dict[str, dict[str, Any]] = {}
    for grant in grants:
        source_id = grant.get("source_id")
        if not isinstance(source_id, str):
            raise LightwalkerEconomyError("grant missing source id")
        if source_id in grant_by_source:
            raise LightwalkerEconomyError(
                "multiple grants supplied for one source"
            )
        source = _source_row(promise, source_id)
        if grant.get("promise_id") != promise["promise_id"]:
            raise LightwalkerEconomyError(
                "grant belongs to another promise"
            )
        if grant.get("reserved_measure") != source["measure"]:
            raise LightwalkerEconomyError(
                "grant does not exactly reserve source share"
            )
        if grant.get("capacity_guild_id") != source["capacity_guild_id"]:
            raise LightwalkerEconomyError(
                "grant comes from wrong source Guild"
            )
        if not _verify_signed(
            grant,
            id_field="grant_id",
            particular_field="capacity_steward_particular",
            domain=GRANT_DOMAIN,
            byte_domain=GRANT_BYTES,
        ):
            raise LightwalkerEconomyError("invalid source grant signature")
        grant_by_source[source_id] = grant

    required_ids = [row["source_id"] for row in promise["sources"]]
    missing = sorted(
        source_id
        for source_id in required_ids
        if source_id not in grant_by_source
    )
    reserved = sum(
        int(grant["reserved_measure"]["quantity"])
        for grant in grant_by_source.values()
    )
    required = int(promise["promised_measure"]["quantity"])
    status = "COMPLETE" if not missing and reserved == required else "PARTIAL"
    body = {
        "kind": BACKING_KIND,
        "version": BACKING_VERSION,
        "authority": "derived-multi-source-backing-view",
        "promise_id": promise["promise_id"],
        "required_source_ids": sorted(required_ids),
        "grant_ids": sorted(
            grant["grant_id"] for grant in grant_by_source.values()
        ),
        "missing_source_ids": missing,
        "required_measure": promise["promised_measure"],
        "reserved_measure": {
            "unit": promise["promised_measure"]["unit"],
            "quantity": reserved,
        },
        "status": status,
        "execution_authority": "none",
        "ownership_aggregated": False,
        "laws": [
            "PARTIAL RESERVATION != FULL BACKING",
            "AGGREGATION != OWNERSHIP",
        ],
    }
    return {**body, "backing_id": content_address(body)}


def make_source_completion(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
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
    if not verify_source_grant(
        snapshot,
        proof,
        request,
        proposal,
        authorization,
        reservation,
        grant,
    ):
        raise LightwalkerEconomyError("invalid source grant")
    if not verify_execution_receipt(
        snapshot, proposal, authorization, execution_receipt
    ):
        raise LightwalkerEconomyError("invalid source execution receipt")
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError(
            "invalid source reservation finalization"
        )
    if execution_receipt.get("success") is not True:
        raise LightwalkerEconomyError(
            "failed source execution cannot prove completion"
        )
    if finalization.get("status") != "CONSUMED":
        raise LightwalkerEconomyError(
            "source completion requires consumed reservation"
        )
    if (
        capacity_steward.particular()
        != grant["capacity_steward_particular"]
    ):
        raise LightwalkerEconomyError(
            "source completion signer mismatch"
        )
    body = {
        "kind": COMPLETION_KIND,
        "version": COMPLETION_VERSION,
        "authority": "source-guild-subcontract-performance",
        "capacity_guild_id": grant["capacity_guild_id"],
        "capacity_steward_particular": capacity_steward.particular(),
        "source_id": grant["source_id"],
        "request_id": request["request_id"],
        "grant_id": grant["grant_id"],
        "reservation_id": reservation["reservation_id"],
        "execution_receipt_id": execution_receipt["execution_receipt_id"],
        "finalization_id": finalization["finalization_id"],
        "performed_measure": grant["reserved_measure"],
        "status": "FULFILLED",
        "customer_performance_proven": False,
        "ownership_transfer": False,
        "laws": [
            "PARTIAL COMPLETION != CUSTOMER PERFORMANCE",
            "SOURCE COMPLETION != DOWNSTREAM SETTLEMENT",
            "AGGREGATION != OWNERSHIP",
        ],
    }
    return _signed(
        body,
        id_field="completion_id",
        signer=capacity_steward,
        domain=COMPLETION_DOMAIN,
        byte_domain=COMPLETION_BYTES,
    )


def make_source_failure(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
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
    if not verify_source_grant(
        snapshot,
        proof,
        request,
        proposal,
        authorization,
        reservation,
        grant,
    ):
        raise LightwalkerEconomyError("invalid source grant")
    if not verify_execution_receipt(
        snapshot, proposal, authorization, execution_receipt
    ):
        raise LightwalkerEconomyError("invalid source execution receipt")
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError(
            "invalid source reservation finalization"
        )
    if execution_receipt.get("success") is not False:
        raise LightwalkerEconomyError(
            "source failure requires failed execution"
        )
    if finalization.get("status") != "RELEASED":
        raise LightwalkerEconomyError(
            "failed source must release reservation"
        )
    if (
        capacity_steward.particular()
        != grant["capacity_steward_particular"]
    ):
        raise LightwalkerEconomyError("source failure signer mismatch")
    body = {
        "kind": FAILURE_KIND,
        "version": FAILURE_VERSION,
        "authority": "source-guild-subcontract-failure",
        "capacity_guild_id": grant["capacity_guild_id"],
        "capacity_steward_particular": capacity_steward.particular(),
        "source_id": grant["source_id"],
        "request_id": request["request_id"],
        "grant_id": grant["grant_id"],
        "reservation_id": reservation["reservation_id"],
        "execution_receipt_id": execution_receipt["execution_receipt_id"],
        "finalization_id": finalization["finalization_id"],
        "failed_measure": grant["reserved_measure"],
        "status": "FAILED",
        "capacity_released": True,
        "customer_performance_proven": False,
        "laws": [
            "SOURCE FAILURE RELEASES ONLY ITS OWN AUTHORITY",
            "PARTIAL COMPLETION != CUSTOMER PERFORMANCE",
            "FAILURE DOES NOT REWRITE OTHER SOURCES",
        ],
    }
    return _signed(
        body,
        id_field="failure_id",
        signer=capacity_steward,
        domain=FAILURE_DOMAIN,
        byte_domain=FAILURE_BYTES,
    )


def _verify_completion(
    promise: dict[str, Any],
    completion: dict[str, Any],
) -> bool:
    try:
        source = _source_row(promise, completion["source_id"])
        if completion.get("kind") != COMPLETION_KIND:
            return False
        if completion.get("version") != COMPLETION_VERSION:
            return False
        if completion.get("status") != "FULFILLED":
            return False
        if completion.get("capacity_guild_id") != source["capacity_guild_id"]:
            return False
        if completion.get("performed_measure") != source["measure"]:
            return False
        if completion.get("customer_performance_proven") is not False:
            return False
        if completion.get("ownership_transfer") is not False:
            return False
        return _verify_signed(
            completion,
            id_field="completion_id",
            particular_field="capacity_steward_particular",
            domain=COMPLETION_DOMAIN,
            byte_domain=COMPLETION_BYTES,
        )
    except Exception:
        return False


def _verify_failure(
    promise: dict[str, Any],
    failure: dict[str, Any],
) -> bool:
    try:
        source = _source_row(promise, failure["source_id"])
        if failure.get("kind") != FAILURE_KIND:
            return False
        if failure.get("version") != FAILURE_VERSION:
            return False
        if failure.get("status") != "FAILED":
            return False
        if failure.get("capacity_guild_id") != source["capacity_guild_id"]:
            return False
        if failure.get("failed_measure") != source["measure"]:
            return False
        if failure.get("capacity_released") is not True:
            return False
        if failure.get("customer_performance_proven") is not False:
            return False
        return _verify_signed(
            failure,
            id_field="failure_id",
            particular_field="capacity_steward_particular",
            domain=FAILURE_DOMAIN,
            byte_domain=FAILURE_BYTES,
        )
    except Exception:
        return False


def derive_multi_source_completion(
    promise: dict[str, Any],
    completions: list[dict[str, Any]],
    failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    failure_rows = failures or []
    completion_by_source: dict[str, dict[str, Any]] = {}
    failure_by_source: dict[str, dict[str, Any]] = {}

    for completion in completions:
        if not _verify_completion(promise, completion):
            raise LightwalkerEconomyError(
                "invalid source completion"
            )
        source_id = completion["source_id"]
        if source_id in completion_by_source:
            raise LightwalkerEconomyError(
                "duplicate completion for source"
            )
        completion_by_source[source_id] = completion

    for failure in failure_rows:
        if not _verify_failure(promise, failure):
            raise LightwalkerEconomyError("invalid source failure")
        source_id = failure["source_id"]
        if source_id in failure_by_source:
            raise LightwalkerEconomyError(
                "duplicate failure for source"
            )
        if source_id in completion_by_source:
            raise LightwalkerEconomyError(
                "source cannot be both completed and failed"
            )
        failure_by_source[source_id] = failure

    required_ids = [row["source_id"] for row in promise["sources"]]
    missing = sorted(
        source_id
        for source_id in required_ids
        if source_id not in completion_by_source
        and source_id not in failure_by_source
    )
    completed_quantity = sum(
        int(item["performed_measure"]["quantity"])
        for item in completion_by_source.values()
    )
    required_quantity = int(promise["promised_measure"]["quantity"])

    if failure_by_source:
        status = "FAILED"
    elif not missing and completed_quantity == required_quantity:
        status = "COMPLETE"
    else:
        status = "PARTIAL"

    body = {
        "kind": AGGREGATE_KIND,
        "version": AGGREGATE_VERSION,
        "authority": "derived-multi-source-completion",
        "promise_id": promise["promise_id"],
        "required_source_ids": sorted(required_ids),
        "completion_ids": sorted(
            item["completion_id"]
            for item in completion_by_source.values()
        ),
        "failure_ids": sorted(
            item["failure_id"] for item in failure_by_source.values()
        ),
        "missing_source_ids": missing,
        "performed_measure": {
            "unit": promise["promised_measure"]["unit"],
            "quantity": completed_quantity,
        },
        "required_measure": promise["promised_measure"],
        "status": status,
        "customer_performance_proven": False,
        "execution_authority": "none",
        "ownership_aggregated": False,
        "laws": [
            "PARTIAL COMPLETION != CUSTOMER PERFORMANCE",
            "ALL REQUIRED SUBCONTRACTS MUST COMPLETE BEFORE DOWNSTREAM PERFORMANCE",
            "AGGREGATION != OWNERSHIP",
        ],
    }
    return {**body, "aggregate_id": content_address(body)}


def attest_multi_source_performance(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    aggregate: dict[str, Any],
    *,
    promisor: IdentityKey,
) -> dict[str, Any]:
    if not verify_multi_source_promise(
        offer, remote_sources, promise
    ):
        raise LightwalkerEconomyError("invalid multi-source promise")
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid customer acceptance")
    if aggregate.get("kind") != AGGREGATE_KIND:
        raise LightwalkerEconomyError("invalid aggregate completion")
    if aggregate.get("promise_id") != promise["promise_id"]:
        raise LightwalkerEconomyError(
            "aggregate belongs to another promise"
        )
    if aggregate.get("status") != "COMPLETE":
        raise LightwalkerEconomyError(
            "all required source completions are required"
        )
    if aggregate.get("failure_ids"):
        raise LightwalkerEconomyError(
            "failed source blocks customer performance"
        )
    if aggregate.get("performed_measure") != promise["promised_measure"]:
        raise LightwalkerEconomyError(
            "aggregate completion quantity is incomplete"
        )
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError(
            "performance signer is not promisor"
        )
    return sign_obligation_performance(
        offer,
        acceptance,
        role="OFFEROR",
        signer=promisor,
        evidence_ref=aggregate["aggregate_id"],
    )


def derive_multi_source_settlement(
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
            "customer settlement requires complete source aggregate"
        )
    if not verify_obligation_performance(
        offer, acceptance, promisor_attestation
    ):
        raise LightwalkerEconomyError(
            "invalid promisor performance attestation"
        )
    if promisor_attestation.get("role") != "OFFEROR":
        raise LightwalkerEconomyError(
            "promisor attestation role mismatch"
        )
    if (
        promisor_attestation.get("evidence_ref")
        != aggregate["aggregate_id"]
    ):
        raise LightwalkerEconomyError(
            "promisor performance not bound to exact aggregate"
        )
    if not verify_obligation_performance(
        offer, acceptance, customer_attestation
    ):
        raise LightwalkerEconomyError(
            "invalid customer performance attestation"
        )
    if customer_attestation.get("role") != "ACCEPTOR":
        raise LightwalkerEconomyError(
            "customer attestation role mismatch"
        )
    if not verify_exchange_settlement(
        offer,
        acceptance,
        [promisor_attestation, customer_attestation],
        settlement,
    ):
        raise LightwalkerEconomyError(
            "invalid downstream multi-source settlement"
        )
    body = {
        "kind": SETTLEMENT_KIND,
        "version": SETTLEMENT_VERSION,
        "authority": "derived-multi-source-service-linkage",
        "promisor_particular": promise["promisor_particular"],
        "promise_id": promise["promise_id"],
        "source_ids": sorted(
            row["source_id"] for row in promise["sources"]
        ),
        "aggregate_id": aggregate["aggregate_id"],
        "promisor_attestation_id": promisor_attestation["attestation_id"],
        "customer_attestation_id": customer_attestation["attestation_id"],
        "settlement_id": settlement["settlement_id"],
        "performed_measure": aggregate["performed_measure"],
        "customer_service_performed": True,
        "source_ownership_aggregated": False,
        "promisor_remote_execution_authority": False,
        "payment_inferred_from_source_execution": False,
        "laws": [
            "PARTIAL COMPLETION != CUSTOMER PERFORMANCE",
            "AGGREGATION != OWNERSHIP",
            "ALL REQUIRED SUBCONTRACTS MUST COMPLETE BEFORE DOWNSTREAM PERFORMANCE",
        ],
    }
    return {**body, "witness_id": content_address(body)}


def make_multi_source_crossing(
    evidence: dict[str, Any],
    *,
    signer: IdentityKey,
    declared_kind: str,
    destination_particular: str,
) -> dict[str, Any]:
    id_fields = (
        "request_id",
        "grant_id",
        "completion_id",
        "failure_id",
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
            "multi-source evidence lacks content identifier"
        )
    kind = evidence.get("kind")
    if kind == REQUEST_KIND:
        expected = evidence.get("promisor_particular")
    elif kind in {GRANT_KIND, COMPLETION_KIND, FAILURE_KIND}:
        expected = evidence.get("capacity_steward_particular")
    elif kind == SETTLEMENT_KIND:
        expected = evidence.get("promisor_particular")
    else:
        raise LightwalkerEconomyError(
            "unsupported multi-source evidence kind"
        )
    if signer.particular() != expected:
        raise LightwalkerEconomyError(
            "crossing signer does not own evidence role"
        )

    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": "ghot:multi-source-service",
        "source_history_head": evidence_id,
        "parents": [],
        "declared_kind": declared_kind,
        "payload_refs": [evidence_id],
        "requested_effect": identity_safe(
            {
                "operation": "consider-multi-source-service-evidence",
                "evidence_id": evidence_id,
                "automatic_reservation_requested": False,
                "automatic_execution_requested": False,
                "ownership_aggregation_requested": False,
                "downstream_performance_inference_requested": False,
            }
        ),
        "capability_ref": MULTI_SOURCE_CAPABILITY,
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
            "ghot_profile": "lightwalker-multi-source-service/v0",
            "partial_is_not_full": True,
            "aggregation_is_not_ownership": True,
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
        raise LightwalkerEconomyError(
            "multi-source evidence crossing failed"
        )
    return signed


__all__ = [
    "attest_multi_source_performance",
    "derive_backing_view",
    "derive_multi_source_completion",
    "derive_multi_source_settlement",
    "make_multi_source_crossing",
    "make_multi_source_promise",
    "make_source_completion",
    "make_source_failure",
    "make_source_request",
    "reserve_source",
    "verify_multi_source_promise",
    "verify_source_grant",
    "verify_source_request",
]
