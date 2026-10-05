#!/usr/bin/env python3
"""Lightwalker Federated Service Promise 001.

One sovereign Guild may make a customer-facing economic promise while another
sovereign Guild retains the operational capacity authority.

Core laws:
    PROMISOR != CAPACITY HOLDER
    REMOTE CAPACITY PROOF != LOCAL AUTHORITY
    SUBCONTRACT != OWNERSHIP TRANSFER
    UPSTREAM RESERVATION != DOWNSTREAM PERFORMANCE
    DOWNSTREAM FAILURE MUST PROPAGATE WITHOUT HISTORY REWRITE
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_authorization import (
    make_resource_proposal,
    verify_execution_receipt,
)
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_finalization,
    verify_reservation,
)
from lightwalker_guild_treasury import verify_treasury_snapshot
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


REMOTE_PROOF_KIND = "ghot.lightwalker.remote-capacity-proof"
REMOTE_PROOF_VERSION = "0"
PROMISE_KIND = "ghot.lightwalker.federated-service-promise"
PROMISE_VERSION = "0"
REQUEST_KIND = "ghot.lightwalker.federated-subcontract-request"
REQUEST_VERSION = "0"
GRANT_KIND = "ghot.lightwalker.federated-subcontract-grant"
GRANT_VERSION = "0"
COMPLETION_KIND = "ghot.lightwalker.federated-subcontract-completion"
COMPLETION_VERSION = "0"
FAILURE_KIND = "ghot.lightwalker.federated-subcontract-failure"
FAILURE_VERSION = "0"
SETTLEMENT_WITNESS_KIND = "ghot.lightwalker.federated-service-settlement"
SETTLEMENT_WITNESS_VERSION = "0"

REMOTE_PROOF_DOMAIN = "ghot.lightwalker-remote-capacity-proof-signature/v0"
PROMISE_DOMAIN = "ghot.lightwalker-federated-service-promise-signature/v0"
REQUEST_DOMAIN = "ghot.lightwalker-federated-subcontract-request-signature/v0"
GRANT_DOMAIN = "ghot.lightwalker-federated-subcontract-grant-signature/v0"
COMPLETION_DOMAIN = "ghot.lightwalker-federated-subcontract-completion-signature/v0"
FAILURE_DOMAIN = "ghot.lightwalker-federated-subcontract-failure-signature/v0"

REMOTE_PROOF_BYTES = b"GHOT-LightwalkerRemoteCapacityProof-v0|"
PROMISE_BYTES = b"GHOT-LightwalkerFederatedServicePromise-v0|"
REQUEST_BYTES = b"GHOT-LightwalkerFederatedSubcontractRequest-v0|"
GRANT_BYTES = b"GHOT-LightwalkerFederatedSubcontractGrant-v0|"
COMPLETION_BYTES = b"GHOT-LightwalkerFederatedSubcontractCompletion-v0|"
FAILURE_BYTES = b"GHOT-LightwalkerFederatedSubcontractFailure-v0|"

FEDERATED_SERVICE_CAPABILITY = "ghot.lightwalker-federated-service/v0"


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


def _resource_entry(
    snapshot: dict[str, Any],
    resource_entry_id: str,
) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid Treasury snapshot")
    for entry in snapshot["entries"]:
        if entry["entry_id"] == resource_entry_id:
            return entry
    raise LightwalkerEconomyError(
        "resource entry not present in remote Treasury"
    )


def _future_service_obligation(
    offer: dict[str, Any],
    promisor_particular: str,
) -> dict[str, Any]:
    if not verify_exchange_offer(offer):
        raise LightwalkerEconomyError("invalid customer-facing offer")
    if offer["offeror_particular"] != promisor_particular:
        raise LightwalkerEconomyError(
            "federated promisor must be economic offeror"
        )
    obligation = offer["offeror_obligation"]
    if obligation.get("obligation_type") != "future-compute-service":
        raise LightwalkerEconomyError(
            "offeror obligation is not future compute service"
        )
    return obligation


def make_remote_capacity_proof(
    snapshot: dict[str, Any],
    *,
    steward: IdentityKey,
    resource_entry_id: str,
    observed_cut: int,
    valid_through_cut: int,
) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid remote Treasury snapshot")
    if steward.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError(
            "only remote Treasury steward may publish capacity proof"
        )
    entry = _resource_entry(snapshot, resource_entry_id)
    if entry["category"] != "capability" or entry["position"] != "available":
        raise LightwalkerEconomyError(
            "remote proof requires available capability entry"
        )
    measure = entry.get("native_measure")
    if not isinstance(measure, dict):
        raise LightwalkerEconomyError(
            "remote capability lacks native measure"
        )
    observed = _nni(observed_cut, "observed_cut")
    valid = _nni(valid_through_cut, "valid_through_cut")
    if valid < observed:
        raise LightwalkerEconomyError(
            "remote capacity proof validity precedes observation"
        )

    body = {
        "kind": REMOTE_PROOF_KIND,
        "version": REMOTE_PROOF_VERSION,
        "authority": "remote-capacity-evidence-only",
        "capacity_guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "resource_entry_id": entry["entry_id"],
        "resource_subject_ref": entry["subject_ref"],
        "capacity_steward_particular": steward.particular(),
        "native_measure": measure,
        "observed_cut": observed,
        "valid_through_cut": valid,
        "capacity_reserved": False,
        "execution_authority_granted": False,
        "ownership_transfer": False,
        "laws": [
            "PROMISOR != CAPACITY HOLDER",
            "REMOTE CAPACITY PROOF != LOCAL AUTHORITY",
            "CAPACITY PROOF DOES NOT RESERVE RESOURCE",
        ],
    }
    return _signed(
        body,
        id_field="remote_proof_id",
        signer=steward,
        domain=REMOTE_PROOF_DOMAIN,
        byte_domain=REMOTE_PROOF_BYTES,
    )


def verify_remote_capacity_proof(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
) -> bool:
    try:
        if not verify_treasury_snapshot(snapshot):
            return False
        if proof.get("kind") != REMOTE_PROOF_KIND:
            return False
        if proof.get("version") != REMOTE_PROOF_VERSION:
            return False
        if proof.get("authority") != "remote-capacity-evidence-only":
            return False
        if proof.get("capacity_guild_id") != snapshot["guild_id"]:
            return False
        if proof.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if (
            proof.get("capacity_steward_particular")
            != snapshot["steward_particular"]
        ):
            return False
        entry = _resource_entry(
            snapshot, str(proof.get("resource_entry_id"))
        )
        if proof.get("resource_subject_ref") != entry["subject_ref"]:
            return False
        if proof.get("native_measure") != entry.get("native_measure"):
            return False
        if proof.get("capacity_reserved") is not False:
            return False
        if proof.get("execution_authority_granted") is not False:
            return False
        if proof.get("ownership_transfer") is not False:
            return False
        if int(proof.get("valid_through_cut", -1)) < int(
            proof.get("observed_cut", 0)
        ):
            return False
        return _verify_signed(
            proof,
            id_field="remote_proof_id",
            particular_field="capacity_steward_particular",
            domain=REMOTE_PROOF_DOMAIN,
            byte_domain=REMOTE_PROOF_BYTES,
        )
    except Exception:
        return False


def make_federated_service_promise(
    remote_snapshot: dict[str, Any],
    offer: dict[str, Any],
    remote_proof: dict[str, Any],
    *,
    promisor: IdentityKey,
    promised_at_cut: int,
) -> dict[str, Any]:
    if not verify_remote_capacity_proof(
        remote_snapshot, remote_proof
    ):
        raise LightwalkerEconomyError(
            "invalid signed remote capacity proof"
        )
    obligation = _future_service_obligation(
        offer, promisor.particular()
    )
    terms = obligation.get("terms")
    if not isinstance(terms, dict):
        raise LightwalkerEconomyError("service terms missing")
    promised = {
        "unit": _nonempty(terms.get("unit"), "service unit"),
        "quantity": _nni(terms.get("quantity"), "service quantity"),
    }
    if promised["quantity"] <= 0:
        raise LightwalkerEconomyError("service quantity must be > 0")
    proof_measure = remote_proof.get("native_measure")
    if not isinstance(proof_measure, dict):
        raise LightwalkerEconomyError("remote proof lacks native measure")
    if promised["unit"] != proof_measure.get("unit"):
        raise LightwalkerEconomyError(
            "service unit differs from remote capacity"
        )
    if promised["quantity"] > int(proof_measure.get("quantity", -1)):
        raise LightwalkerEconomyError(
            "service promise exceeds remotely proven capacity"
        )
    cut = _nni(promised_at_cut, "promised_at_cut")
    if cut > int(remote_proof["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "remote capacity proof expired before promise"
        )
    if cut > int(offer["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "customer-facing offer expired before promise"
        )

    body = {
        "kind": PROMISE_KIND,
        "version": PROMISE_VERSION,
        "authority": "promisor-economic-promise-only",
        "promisor_particular": promisor.particular(),
        "offer_id": offer["offer_id"],
        "service_obligation_id": obligation["obligation_id"],
        "remote_proof_id": remote_proof["remote_proof_id"],
        "capacity_guild_id": remote_proof["capacity_guild_id"],
        "remote_snapshot_id": remote_proof["snapshot_id"],
        "remote_resource_entry_id": remote_proof["resource_entry_id"],
        "capacity_steward_particular": remote_proof[
            "capacity_steward_particular"
        ],
        "promised_measure": promised,
        "promised_at_cut": cut,
        "valid_through_cut": min(
            int(offer["valid_through_cut"]),
            int(remote_proof["valid_through_cut"]),
        ),
        "capacity_reserved": False,
        "local_execution_authority": False,
        "ownership_transfer": False,
        "laws": [
            "PROMISOR != CAPACITY HOLDER",
            "REMOTE CAPACITY PROOF != LOCAL AUTHORITY",
            "PROMISE != REMOTE RESERVATION",
        ],
    }
    return _signed(
        body,
        id_field="promise_id",
        signer=promisor,
        domain=PROMISE_DOMAIN,
        byte_domain=PROMISE_BYTES,
    )


def verify_federated_service_promise(
    remote_snapshot: dict[str, Any],
    offer: dict[str, Any],
    remote_proof: dict[str, Any],
    promise: dict[str, Any],
) -> bool:
    try:
        if not verify_remote_capacity_proof(
            remote_snapshot, remote_proof
        ):
            return False
        obligation = _future_service_obligation(
            offer, promise["promisor_particular"]
        )
        if promise.get("kind") != PROMISE_KIND:
            return False
        if promise.get("version") != PROMISE_VERSION:
            return False
        if promise.get("authority") != "promisor-economic-promise-only":
            return False
        if promise.get("offer_id") != offer["offer_id"]:
            return False
        if (
            promise.get("service_obligation_id")
            != obligation["obligation_id"]
        ):
            return False
        if promise.get("remote_proof_id") != remote_proof["remote_proof_id"]:
            return False
        if (
            promise.get("capacity_guild_id")
            != remote_proof["capacity_guild_id"]
        ):
            return False
        if promise.get("remote_snapshot_id") != remote_proof["snapshot_id"]:
            return False
        if (
            promise.get("remote_resource_entry_id")
            != remote_proof["resource_entry_id"]
        ):
            return False
        if (
            promise.get("capacity_steward_particular")
            != remote_proof["capacity_steward_particular"]
        ):
            return False
        terms = obligation.get("terms")
        if not isinstance(terms, dict):
            return False
        if promise.get("promised_measure") != {
            "unit": terms.get("unit"),
            "quantity": terms.get("quantity"),
        }:
            return False
        if promise.get("capacity_reserved") is not False:
            return False
        if promise.get("local_execution_authority") is not False:
            return False
        if promise.get("ownership_transfer") is not False:
            return False
        if int(promise.get("promised_at_cut", -1)) < 0:
            return False
        if int(promise["promised_at_cut"]) > int(
            promise["valid_through_cut"]
        ):
            return False
        if int(promise["valid_through_cut"]) > int(
            remote_proof["valid_through_cut"]
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


def make_subcontract_request(
    remote_snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_proof: dict[str, Any],
    promise: dict[str, Any],
    *,
    promisor: IdentityKey,
    requested_at_cut: int,
) -> dict[str, Any]:
    if not verify_federated_service_promise(
        remote_snapshot, offer, remote_proof, promise
    ):
        raise LightwalkerEconomyError(
            "invalid federated service promise"
        )
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError(
            "customer-facing offer has no valid acceptance"
        )
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError("subcontract requester is not promisor")
    cut = _nni(requested_at_cut, "requested_at_cut")
    if cut > int(promise["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "subcontract request occurs after promise backing expires"
        )

    body = {
        "kind": REQUEST_KIND,
        "version": REQUEST_VERSION,
        "authority": "promisor-subcontract-request-only",
        "promisor_particular": promisor.particular(),
        "promise_id": promise["promise_id"],
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "remote_proof_id": remote_proof["remote_proof_id"],
        "capacity_guild_id": remote_proof["capacity_guild_id"],
        "remote_snapshot_id": remote_proof["snapshot_id"],
        "remote_resource_entry_id": remote_proof["resource_entry_id"],
        "requested_measure": promise["promised_measure"],
        "requested_at_cut": cut,
        "reservation_authority": "none",
        "ownership_transfer_requested": False,
        "laws": [
            "SUBCONTRACT REQUEST != REMOTE RESERVATION",
            "REMOTE CAPACITY PROOF != LOCAL AUTHORITY",
            "SUBCONTRACT != OWNERSHIP TRANSFER",
        ],
    }
    return _signed(
        body,
        id_field="request_id",
        signer=promisor,
        domain=REQUEST_DOMAIN,
        byte_domain=REQUEST_BYTES,
    )


def verify_subcontract_request(
    remote_snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_proof: dict[str, Any],
    promise: dict[str, Any],
    request: dict[str, Any],
) -> bool:
    try:
        if not verify_federated_service_promise(
            remote_snapshot, offer, remote_proof, promise
        ):
            return False
        if not verify_exchange_acceptance(offer, acceptance):
            return False
        if request.get("kind") != REQUEST_KIND:
            return False
        if request.get("version") != REQUEST_VERSION:
            return False
        if request.get("authority") != "promisor-subcontract-request-only":
            return False
        if request.get("promisor_particular") != promise["promisor_particular"]:
            return False
        if request.get("promise_id") != promise["promise_id"]:
            return False
        if request.get("offer_id") != offer["offer_id"]:
            return False
        if request.get("acceptance_id") != acceptance["acceptance_id"]:
            return False
        if request.get("remote_proof_id") != remote_proof["remote_proof_id"]:
            return False
        if request.get("remote_snapshot_id") != remote_proof["snapshot_id"]:
            return False
        if request.get("remote_resource_entry_id") != remote_proof["resource_entry_id"]:
            return False
        if request.get("requested_measure") != promise["promised_measure"]:
            return False
        if request.get("reservation_authority") != "none":
            return False
        if request.get("ownership_transfer_requested") is not False:
            return False
        if int(request.get("requested_at_cut", -1)) < 0:
            return False
        if int(request["requested_at_cut"]) > int(
            promise["valid_through_cut"]
        ):
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


def reserve_federated_subcontract(
    current_capacity_snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_proof: dict[str, Any],
    promise: dict[str, Any],
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
        current_capacity_snapshot, remote_proof
    ):
        raise LightwalkerEconomyError(
            "remote proof does not match current capacity snapshot"
        )
    if not verify_subcontract_request(
        current_capacity_snapshot,
        offer,
        acceptance,
        remote_proof,
        promise,
        request,
    ):
        raise LightwalkerEconomyError("invalid subcontract request")
    if (
        capacity_steward.particular()
        != current_capacity_snapshot["steward_particular"]
    ):
        raise LightwalkerEconomyError(
            "only capacity Guild may reserve remote capacity"
        )
    cut = _nni(reserved_at_cut, "reserved_at_cut")
    if cut > int(remote_proof["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "remote capacity proof expired before reservation"
        )

    proposal = make_resource_proposal(
        current_capacity_snapshot,
        proposer=capacity_steward,
        resource_entry_id=remote_proof["resource_entry_id"],
        requested_quantity=int(
            request["requested_measure"]["quantity"]
        ),
        requested_unit=request["requested_measure"]["unit"],
        purpose_ref="federated-subcontract:" + request["request_id"],
        proposed_at_cut=cut,
    )
    authorization, reservation = reservation_store.reserve_and_authorize(
        current_capacity_snapshot,
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
        "authority": "capacity-guild-local-reservation-grant",
        "capacity_guild_id": current_capacity_snapshot["guild_id"],
        "capacity_steward_particular": capacity_steward.particular(),
        "snapshot_id": current_capacity_snapshot["snapshot_id"],
        "remote_proof_id": remote_proof["remote_proof_id"],
        "request_id": request["request_id"],
        "promise_id": promise["promise_id"],
        "proposal_id": proposal["proposal_id"],
        "authorization_id": authorization["authorization_id"],
        "reservation_id": reservation["reservation_id"],
        "resource_entry_id": remote_proof["resource_entry_id"],
        "reserved_measure": request["requested_measure"],
        "executor_particular": authorization["executor_particular"],
        "status": "REMOTE_RESERVED",
        "promisor_execution_authority": False,
        "ownership_transfer": False,
        "laws": [
            "PROMISOR != CAPACITY HOLDER",
            "SUBCONTRACT != OWNERSHIP TRANSFER",
            "UPSTREAM RESERVATION != DOWNSTREAM PERFORMANCE",
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


def verify_subcontract_grant(
    snapshot: dict[str, Any],
    remote_proof: dict[str, Any],
    request: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    grant: dict[str, Any],
) -> bool:
    try:
        if not verify_remote_capacity_proof(snapshot, remote_proof):
            return False
        if not _verify_signed(
            request,
            id_field="request_id",
            particular_field="promisor_particular",
            domain=REQUEST_DOMAIN,
            byte_domain=REQUEST_BYTES,
        ):
            return False
        if request.get("remote_proof_id") != remote_proof["remote_proof_id"]:
            return False
        if request.get("remote_snapshot_id") != snapshot["snapshot_id"]:
            return False
        if request.get("remote_resource_entry_id") != remote_proof["resource_entry_id"]:
            return False
        if request.get("promise_id") != grant.get("promise_id"):
            return False
        if request.get("requested_measure") != grant.get("reserved_measure"):
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
            != "capacity-guild-local-reservation-grant"
        ):
            return False
        if grant.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if grant.get("remote_proof_id") != remote_proof["remote_proof_id"]:
            return False
        if grant.get("request_id") != request["request_id"]:
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
            "federated-subcontract:" + request["request_id"]
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


def make_subcontract_completion(
    snapshot: dict[str, Any],
    remote_proof: dict[str, Any],
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
    if not verify_subcontract_grant(
        snapshot,
        remote_proof,
        request,
        proposal,
        authorization,
        reservation,
        grant,
    ):
        raise LightwalkerEconomyError("invalid subcontract grant")
    if not verify_execution_receipt(
        snapshot, proposal, authorization, execution_receipt
    ):
        raise LightwalkerEconomyError(
            "invalid remote execution receipt"
        )
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError(
            "invalid remote reservation finalization"
        )
    if execution_receipt.get("success") is not True:
        raise LightwalkerEconomyError(
            "failed remote execution cannot prove completion"
        )
    if finalization.get("status") != "CONSUMED":
        raise LightwalkerEconomyError(
            "remote completion requires consumed reservation"
        )
    if (
        capacity_steward.particular()
        != grant["capacity_steward_particular"]
    ):
        raise LightwalkerEconomyError(
            "completion signer is not capacity Guild steward"
        )

    body = {
        "kind": COMPLETION_KIND,
        "version": COMPLETION_VERSION,
        "authority": "capacity-guild-subcontract-performance",
        "capacity_guild_id": grant["capacity_guild_id"],
        "capacity_steward_particular": capacity_steward.particular(),
        "request_id": request["request_id"],
        "promise_id": grant["promise_id"],
        "grant_id": grant["grant_id"],
        "reservation_id": reservation["reservation_id"],
        "execution_receipt_id": execution_receipt["execution_receipt_id"],
        "finalization_id": finalization["finalization_id"],
        "performed_measure": grant["reserved_measure"],
        "status": "FULFILLED",
        "downstream_settlement_created": False,
        "ownership_transfer": False,
        "laws": [
            "UPSTREAM RESERVATION != DOWNSTREAM PERFORMANCE",
            "SUBCONTRACT PERFORMANCE != CUSTOMER SETTLEMENT",
            "SUBCONTRACT != OWNERSHIP TRANSFER",
        ],
    }
    return _signed(
        body,
        id_field="completion_id",
        signer=capacity_steward,
        domain=COMPLETION_DOMAIN,
        byte_domain=COMPLETION_BYTES,
    )


def verify_subcontract_completion(
    grant: dict[str, Any],
    completion: dict[str, Any],
) -> bool:
    try:
        if completion.get("kind") != COMPLETION_KIND:
            return False
        if completion.get("version") != COMPLETION_VERSION:
            return False
        if (
            completion.get("authority")
            != "capacity-guild-subcontract-performance"
        ):
            return False
        if completion.get("grant_id") != grant["grant_id"]:
            return False
        if completion.get("request_id") != grant["request_id"]:
            return False
        if completion.get("promise_id") != grant["promise_id"]:
            return False
        if completion.get("performed_measure") != grant["reserved_measure"]:
            return False
        if completion.get("status") != "FULFILLED":
            return False
        if completion.get("downstream_settlement_created") is not False:
            return False
        if completion.get("ownership_transfer") is not False:
            return False
        if (
            completion.get("capacity_steward_particular")
            != grant["capacity_steward_particular"]
        ):
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


def make_subcontract_failure(
    snapshot: dict[str, Any],
    remote_proof: dict[str, Any],
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
    if not verify_subcontract_grant(
        snapshot,
        remote_proof,
        request,
        proposal,
        authorization,
        reservation,
        grant,
    ):
        raise LightwalkerEconomyError("invalid subcontract grant")
    if not verify_execution_receipt(
        snapshot, proposal, authorization, execution_receipt
    ):
        raise LightwalkerEconomyError(
            "invalid remote execution receipt"
        )
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError(
            "invalid remote reservation finalization"
        )
    if execution_receipt.get("success") is not False:
        raise LightwalkerEconomyError(
            "failure notice requires failed execution"
        )
    if finalization.get("status") != "RELEASED":
        raise LightwalkerEconomyError(
            "failed subcontract must release reservation"
        )
    if (
        capacity_steward.particular()
        != grant["capacity_steward_particular"]
    ):
        raise LightwalkerEconomyError(
            "failure signer is not capacity Guild steward"
        )

    body = {
        "kind": FAILURE_KIND,
        "version": FAILURE_VERSION,
        "authority": "capacity-guild-subcontract-failure",
        "capacity_guild_id": grant["capacity_guild_id"],
        "capacity_steward_particular": capacity_steward.particular(),
        "request_id": request["request_id"],
        "promise_id": grant["promise_id"],
        "grant_id": grant["grant_id"],
        "reservation_id": reservation["reservation_id"],
        "execution_receipt_id": execution_receipt["execution_receipt_id"],
        "finalization_id": finalization["finalization_id"],
        "failed_measure": grant["reserved_measure"],
        "status": "FAILED",
        "capacity_released": True,
        "downstream_performance_proven": False,
        "laws": [
            "DOWNSTREAM FAILURE MUST PROPAGATE WITHOUT HISTORY REWRITE",
            "FAILED SUBCONTRACT != DOWNSTREAM PERFORMANCE",
            "RELEASE != SUCCESS",
        ],
    }
    return _signed(
        body,
        id_field="failure_id",
        signer=capacity_steward,
        domain=FAILURE_DOMAIN,
        byte_domain=FAILURE_BYTES,
    )


def verify_subcontract_failure(
    grant: dict[str, Any],
    failure: dict[str, Any],
) -> bool:
    try:
        if failure.get("kind") != FAILURE_KIND:
            return False
        if failure.get("version") != FAILURE_VERSION:
            return False
        if (
            failure.get("authority")
            != "capacity-guild-subcontract-failure"
        ):
            return False
        if failure.get("grant_id") != grant["grant_id"]:
            return False
        if failure.get("request_id") != grant["request_id"]:
            return False
        if failure.get("promise_id") != grant["promise_id"]:
            return False
        if failure.get("failed_measure") != grant["reserved_measure"]:
            return False
        if failure.get("status") != "FAILED":
            return False
        if failure.get("capacity_released") is not True:
            return False
        if failure.get("downstream_performance_proven") is not False:
            return False
        if (
            failure.get("capacity_steward_particular")
            != grant["capacity_steward_particular"]
        ):
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


def attest_promisor_performance(
    remote_snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_proof: dict[str, Any],
    promise: dict[str, Any],
    request: dict[str, Any],
    grant: dict[str, Any],
    completion: dict[str, Any],
    *,
    promisor: IdentityKey,
) -> dict[str, Any]:
    if not verify_federated_service_promise(
        remote_snapshot, offer, remote_proof, promise
    ):
        raise LightwalkerEconomyError("invalid federated promise")
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid customer acceptance")
    if not verify_subcontract_request(
        remote_snapshot,
        offer,
        acceptance,
        remote_proof,
        promise,
        request,
    ):
        raise LightwalkerEconomyError("invalid subcontract request")
    if grant.get("request_id") != request["request_id"]:
        raise LightwalkerEconomyError(
            "subcontract grant does not answer request"
        )
    if not verify_subcontract_completion(grant, completion):
        raise LightwalkerEconomyError(
            "remote subcontract is not successfully completed"
        )
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError(
            "customer-facing performance signer is not promisor"
        )
    return sign_obligation_performance(
        offer,
        acceptance,
        role="OFFEROR",
        signer=promisor,
        evidence_ref=completion["completion_id"],
    )


def derive_federated_service_settlement(
    remote_snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_proof: dict[str, Any],
    promise: dict[str, Any],
    request: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    grant: dict[str, Any],
    execution_receipt: dict[str, Any],
    finalization: dict[str, Any],
    completion: dict[str, Any],
    promisor_attestation: dict[str, Any],
    customer_attestation: dict[str, Any],
    settlement: dict[str, Any],
) -> dict[str, Any]:
    if not verify_federated_service_promise(
        remote_snapshot, offer, remote_proof, promise
    ):
        raise LightwalkerEconomyError("invalid federated promise")
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid customer acceptance")
    if not verify_subcontract_request(
        remote_snapshot,
        offer,
        acceptance,
        remote_proof,
        promise,
        request,
    ):
        raise LightwalkerEconomyError("invalid subcontract request")
    if not verify_subcontract_grant(
        remote_snapshot,
        remote_proof,
        request,
        proposal,
        authorization,
        reservation,
        grant,
    ):
        raise LightwalkerEconomyError("invalid subcontract grant")
    if not verify_execution_receipt(
        remote_snapshot, proposal, authorization, execution_receipt
    ):
        raise LightwalkerEconomyError(
            "invalid remote execution receipt"
        )
    if execution_receipt.get("success") is not True:
        raise LightwalkerEconomyError(
            "federated settlement requires successful remote execution"
        )
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError(
            "invalid remote reservation finalization"
        )
    if finalization.get("status") != "CONSUMED":
        raise LightwalkerEconomyError(
            "federated settlement requires consumed remote reservation"
        )
    if not verify_subcontract_completion(grant, completion):
        raise LightwalkerEconomyError(
            "invalid remote subcontract completion"
        )
    if completion.get("execution_receipt_id") != execution_receipt[
        "execution_receipt_id"
    ]:
        raise LightwalkerEconomyError(
            "completion does not bind exact remote execution"
        )
    if not verify_obligation_performance(
        offer, acceptance, promisor_attestation
    ):
        raise LightwalkerEconomyError(
            "invalid promisor performance attestation"
        )
    if promisor_attestation.get("role") != "OFFEROR":
        raise LightwalkerEconomyError(
            "promisor attestation must be offeror performance"
        )
    if (
        promisor_attestation.get("evidence_ref")
        != completion["completion_id"]
    ):
        raise LightwalkerEconomyError(
            "promisor performance is not grounded in remote completion"
        )
    if not verify_obligation_performance(
        offer, acceptance, customer_attestation
    ):
        raise LightwalkerEconomyError(
            "invalid customer performance attestation"
        )
    if customer_attestation.get("role") != "ACCEPTOR":
        raise LightwalkerEconomyError(
            "customer attestation must be acceptor performance"
        )
    if not verify_exchange_settlement(
        offer,
        acceptance,
        [promisor_attestation, customer_attestation],
        settlement,
    ):
        raise LightwalkerEconomyError(
            "invalid customer-facing federated settlement"
        )

    body = {
        "kind": SETTLEMENT_WITNESS_KIND,
        "version": SETTLEMENT_WITNESS_VERSION,
        "authority": "derived-federated-service-linkage",
        "promisor_particular": promise["promisor_particular"],
        "capacity_guild_id": remote_proof["capacity_guild_id"],
        "remote_snapshot_id": remote_snapshot["snapshot_id"],
        "remote_proof_id": remote_proof["remote_proof_id"],
        "promise_id": promise["promise_id"],
        "request_id": request["request_id"],
        "grant_id": grant["grant_id"],
        "remote_reservation_id": reservation["reservation_id"],
        "remote_execution_receipt_id": execution_receipt[
            "execution_receipt_id"
        ],
        "completion_id": completion["completion_id"],
        "promisor_attestation_id": promisor_attestation["attestation_id"],
        "customer_attestation_id": customer_attestation["attestation_id"],
        "settlement_id": settlement["settlement_id"],
        "performed_measure": completion["performed_measure"],
        "customer_service_performed": True,
        "capacity_ownership_transferred": False,
        "promisor_remote_execution_authority": False,
        "payment_inferred_from_remote_execution": False,
        "laws": [
            "PROMISOR != CAPACITY HOLDER",
            "REMOTE CAPACITY PROOF != LOCAL AUTHORITY",
            "SUBCONTRACT != OWNERSHIP TRANSFER",
            "UPSTREAM RESERVATION != DOWNSTREAM PERFORMANCE",
            "REMOTE COMPLETION MAY SUPPORT DOWNSTREAM PERFORMANCE EVIDENCE",
        ],
    }
    return {**body, "witness_id": content_address(body)}



def make_federated_evidence_crossing(
    evidence: dict[str, Any],
    *,
    signer: IdentityKey,
    declared_kind: str,
    destination_particular: str,
) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise LightwalkerEconomyError("federated evidence must be object")
    evidence_id = None
    for field in (
        "remote_proof_id",
        "request_id",
        "grant_id",
        "completion_id",
        "failure_id",
        "witness_id",
    ):
        if isinstance(evidence.get(field), str):
            evidence_id = evidence[field]
            break
    if evidence_id is None:
        raise LightwalkerEconomyError(
            "federated evidence lacks content identifier"
        )

    kind = evidence.get("kind")
    if kind in {
        REMOTE_PROOF_KIND,
        GRANT_KIND,
        COMPLETION_KIND,
        FAILURE_KIND,
    }:
        expected_signer = evidence.get("capacity_steward_particular")
    elif kind == REQUEST_KIND:
        expected_signer = evidence.get("promisor_particular")
    elif kind == SETTLEMENT_WITNESS_KIND:
        expected_signer = evidence.get("promisor_particular")
    else:
        raise LightwalkerEconomyError(
            "unsupported federated evidence kind for crossing"
        )
    if signer.particular() != expected_signer:
        raise LightwalkerEconomyError(
            "federated crossing signer does not own artifact role"
        )

    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": "ghot:federated-service",
        "source_history_head": evidence_id,
        "parents": [],
        "declared_kind": declared_kind,
        "payload_refs": [evidence_id],
        "requested_effect": identity_safe(
            {
                "operation": "consider-federated-service-evidence",
                "evidence_id": evidence_id,
                "automatic_reservation_requested": False,
                "automatic_execution_requested": False,
                "ownership_transfer_requested": False,
                "downstream_settlement_requested": False,
            }
        ),
        "capability_ref": FEDERATED_SERVICE_CAPABILITY,
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
            "ghot_profile": "lightwalker-federated-service/v0",
            "remote_proof_is_not_local_authority": True,
            "subcontract_is_not_ownership_transfer": True,
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
            "federated service evidence crossing failed"
        )
    return signed


__all__ = [
    "attest_promisor_performance",
    "derive_federated_service_settlement",
    "make_federated_evidence_crossing",
    "make_federated_service_promise",
    "make_remote_capacity_proof",
    "make_subcontract_completion",
    "make_subcontract_failure",
    "make_subcontract_request",
    "reserve_federated_subcontract",
    "verify_federated_service_promise",
    "verify_remote_capacity_proof",
    "verify_subcontract_completion",
    "verify_subcontract_failure",
    "verify_subcontract_grant",
    "verify_subcontract_request",
]
