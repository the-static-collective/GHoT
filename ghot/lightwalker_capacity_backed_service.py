#!/usr/bin/env python3
"""Lightwalker Capacity-Backed Future Service 001.

Verified capacity may support an economic promise. The promise does not reserve,
consume, or prove performance. Acceptance may later create a separate
steward-local reservation against the exact named capacity source.

Core laws:
    CAPACITY PROOF != PROMISE
    PROMISE != RESERVATION
    RESERVATION != PERFORMANCE
    PERFORMANCE != PAYMENT
    FUTURE SERVICE OFFER MUST NAME ITS AUTHORITY SOURCE
    ECONOMIC COMMITMENT MAY ENCUMBER CAPACITY WITHOUT CONSUMING IT
"""

from __future__ import annotations

from pathlib import Path
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


PROMISE_KIND = "ghot.lightwalker.capacity-backed-service-promise"
PROMISE_VERSION = "0"
ENCUMBRANCE_KIND = "ghot.lightwalker.capacity-backed-service-encumbrance"
ENCUMBRANCE_VERSION = "0"
WITNESS_KIND = "ghot.lightwalker.capacity-backed-service-settlement"
WITNESS_VERSION = "0"

PROMISE_DOMAIN = "ghot.lightwalker-capacity-backed-service-promise-signature/v0"
ENCUMBRANCE_DOMAIN = "ghot.lightwalker-capacity-backed-service-encumbrance-signature/v0"
PROMISE_BYTES = b"GHOT-LightwalkerCapacityBackedServicePromise-v0|"
ENCUMBRANCE_BYTES = b"GHOT-LightwalkerCapacityBackedServiceEncumbrance-v0|"

SERVICE_CAPABILITY = "ghot.lightwalker-capacity-backed-service/v0"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nni(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
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
        if particular_for_public_key(public_key) != value.get(particular_field):
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
            byte_domain + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def _resource_entry(
    snapshot: dict[str, Any],
    entry_id: str,
) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    for entry in snapshot["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise LightwalkerEconomyError("capacity source not found in Treasury")


def _service_obligation(
    offer: dict[str, Any],
    *,
    guild_particular: str,
) -> dict[str, Any]:
    if offer.get("offeror_particular") != guild_particular:
        raise LightwalkerEconomyError(
            "capacity-backed service requires Guild as offeror"
        )
    obligation = offer.get("offeror_obligation")
    if not isinstance(obligation, dict):
        raise LightwalkerEconomyError("service obligation missing")
    if obligation.get("obligation_type") != "future-compute-service":
        raise LightwalkerEconomyError(
            "offeror obligation is not future compute service"
        )
    return obligation


def make_capacity_backed_service_promise(
    snapshot: dict[str, Any],
    offer: dict[str, Any],
    *,
    steward: IdentityKey,
    resource_entry_id: str,
    executor_particular: str,
    promised_at_cut: int,
) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid Treasury snapshot")
    if steward.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError(
            "only Treasury steward may make backed service promise"
        )
    if not verify_exchange_offer(offer):
        raise LightwalkerEconomyError("invalid heterogeneous offer")

    obligation = _service_obligation(
        offer,
        guild_particular=steward.particular(),
    )
    terms = obligation.get("terms")
    if not isinstance(terms, dict):
        raise LightwalkerEconomyError("service obligation terms missing")

    entry = _resource_entry(snapshot, resource_entry_id)
    if entry["category"] != "capability" or entry["position"] != "available":
        raise LightwalkerEconomyError(
            "service promise requires available capability entry"
        )
    measure = entry.get("native_measure")
    if not isinstance(measure, dict):
        raise LightwalkerEconomyError("capacity source lacks native measure")

    unit = _nonempty(terms.get("unit"), "service unit")
    quantity = _nni(terms.get("quantity"), "service quantity")
    if quantity <= 0:
        raise LightwalkerEconomyError("service quantity must be > 0")
    if unit != measure["unit"]:
        raise LightwalkerEconomyError(
            "service obligation unit differs from capacity source"
        )
    if quantity > int(measure["quantity"]):
        raise LightwalkerEconomyError(
            "service promise exceeds visible capacity"
        )

    cut = _nni(promised_at_cut, "promised_at_cut")
    if cut > int(offer["valid_through_cut"]):
        raise LightwalkerEconomyError(
            "service promise created after economic offer expiry"
        )

    body = {
        "kind": PROMISE_KIND,
        "version": PROMISE_VERSION,
        "authority": "guild-promise-capacity-referenced",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "resource_entry_id": entry["entry_id"],
        "resource_subject_ref": entry["subject_ref"],
        "steward_particular": steward.particular(),
        "executor_particular": _nonempty(
            executor_particular, "executor_particular"
        ),
        "offer_id": offer["offer_id"],
        "service_obligation_id": obligation["obligation_id"],
        "promised_measure": {
            "unit": unit,
            "quantity": quantity,
        },
        "promised_at_cut": cut,
        "valid_through_cut": int(offer["valid_through_cut"]),
        "capacity_encumbered": False,
        "execution_authority_granted": False,
        "performance_proven": False,
        "laws": [
            "CAPACITY PROOF != PROMISE",
            "PROMISE != RESERVATION",
            "PROMISE DOES NOT ENCUMBER CAPACITY",
            "FUTURE SERVICE OFFER MUST NAME ITS AUTHORITY SOURCE",
        ],
    }
    return _signed(
        body,
        id_field="promise_id",
        signer=steward,
        domain=PROMISE_DOMAIN,
        byte_domain=PROMISE_BYTES,
    )


def verify_capacity_backed_service_promise(
    snapshot: dict[str, Any],
    offer: dict[str, Any],
    promise: dict[str, Any],
) -> bool:
    try:
        if not verify_treasury_snapshot(snapshot):
            return False
        if not verify_exchange_offer(offer):
            return False
        if promise.get("kind") != PROMISE_KIND:
            return False
        if promise.get("version") != PROMISE_VERSION:
            return False
        if promise.get("authority") != "guild-promise-capacity-referenced":
            return False
        if promise.get("guild_id") != snapshot["guild_id"]:
            return False
        if promise.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if promise.get("steward_particular") != snapshot["steward_particular"]:
            return False
        if promise.get("offer_id") != offer["offer_id"]:
            return False
        if promise.get("valid_through_cut") != int(
            offer["valid_through_cut"]
        ):
            return False
        if int(promise.get("promised_at_cut", -1)) < 0:
            return False
        if int(promise["promised_at_cut"]) > int(
            promise["valid_through_cut"]
        ):
            return False
        obligation = _service_obligation(
            offer,
            guild_particular=promise["steward_particular"],
        )
        if promise.get("service_obligation_id") != obligation["obligation_id"]:
            return False
        entry = _resource_entry(
            snapshot, str(promise.get("resource_entry_id"))
        )
        if promise.get("resource_subject_ref") != entry["subject_ref"]:
            return False
        if entry["category"] != "capability" or entry["position"] != "available":
            return False
        measure = entry.get("native_measure")
        promised = promise.get("promised_measure")
        if not isinstance(measure, dict) or not isinstance(promised, dict):
            return False
        terms = obligation.get("terms")
        if not isinstance(terms, dict):
            return False
        if promised != {
            "unit": terms.get("unit"),
            "quantity": terms.get("quantity"),
        }:
            return False
        if promised["unit"] != measure["unit"]:
            return False
        if int(promised["quantity"]) > int(measure["quantity"]):
            return False
        if promise.get("capacity_encumbered") is not False:
            return False
        if promise.get("execution_authority_granted") is not False:
            return False
        if promise.get("performance_proven") is not False:
            return False
        return _verify_signed(
            promise,
            id_field="promise_id",
            particular_field="steward_particular",
            domain=PROMISE_DOMAIN,
            byte_domain=PROMISE_BYTES,
        )
    except Exception:
        return False


def reserve_accepted_service(
    snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    promise: dict[str, Any],
    *,
    steward: IdentityKey,
    reservation_store: GuildReservationStore,
    reserved_at_cut: int,
    expires_after_cut: int,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    if not verify_capacity_backed_service_promise(
        snapshot, offer, promise
    ):
        raise LightwalkerEconomyError(
            "invalid capacity-backed service promise"
        )
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError(
            "service promise has no valid economic acceptance"
        )
    if steward.particular() != promise["steward_particular"]:
        raise LightwalkerEconomyError("promise steward mismatch")

    proposal = make_resource_proposal(
        snapshot,
        proposer=steward,
        resource_entry_id=promise["resource_entry_id"],
        requested_quantity=int(promise["promised_measure"]["quantity"]),
        requested_unit=promise["promised_measure"]["unit"],
        purpose_ref="service-promise:" + promise["promise_id"],
        proposed_at_cut=reserved_at_cut,
    )
    authorization, reservation = reservation_store.reserve_and_authorize(
        snapshot,
        proposal,
        executor_particular=promise["executor_particular"],
        authorized_at_cut=reserved_at_cut,
        expires_after_cut=expires_after_cut,
    )
    body = {
        "kind": ENCUMBRANCE_KIND,
        "version": ENCUMBRANCE_VERSION,
        "authority": "guild-local-service-encumbrance",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "promise_id": promise["promise_id"],
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "proposal_id": proposal["proposal_id"],
        "authorization_id": authorization["authorization_id"],
        "reservation_id": reservation["reservation_id"],
        "resource_entry_id": promise["resource_entry_id"],
        "steward_particular": steward.particular(),
        "reserved_measure": promise["promised_measure"],
        "performance_proven": False,
        "payment_inferred": False,
        "status": "ENCUMBERED",
        "laws": [
            "PROMISE != RESERVATION",
            "RESERVATION != PERFORMANCE",
            "ECONOMIC COMMITMENT MAY ENCUMBER CAPACITY WITHOUT CONSUMING IT",
        ],
    }
    encumbrance = _signed(
        body,
        id_field="encumbrance_id",
        signer=steward,
        domain=ENCUMBRANCE_DOMAIN,
        byte_domain=ENCUMBRANCE_BYTES,
    )
    return proposal, authorization, reservation, encumbrance


def verify_service_encumbrance(
    snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    promise: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    encumbrance: dict[str, Any],
) -> bool:
    try:
        if not verify_capacity_backed_service_promise(
            snapshot, offer, promise
        ):
            return False
        if not verify_exchange_acceptance(offer, acceptance):
            return False
        if not verify_reservation(
            snapshot, proposal, authorization, reservation
        ):
            return False
        if encumbrance.get("kind") != ENCUMBRANCE_KIND:
            return False
        if encumbrance.get("version") != ENCUMBRANCE_VERSION:
            return False
        if encumbrance.get("authority") != "guild-local-service-encumbrance":
            return False
        if encumbrance.get("promise_id") != promise["promise_id"]:
            return False
        if encumbrance.get("offer_id") != offer["offer_id"]:
            return False
        if encumbrance.get("acceptance_id") != acceptance["acceptance_id"]:
            return False
        if encumbrance.get("proposal_id") != proposal["proposal_id"]:
            return False
        if encumbrance.get("authorization_id") != authorization["authorization_id"]:
            return False
        if encumbrance.get("reservation_id") != reservation["reservation_id"]:
            return False
        if encumbrance.get("resource_entry_id") != promise["resource_entry_id"]:
            return False
        if encumbrance.get("steward_particular") != promise["steward_particular"]:
            return False
        if proposal.get("purpose_ref") != "service-promise:" + promise["promise_id"]:
            return False
        if proposal.get("requested_measure") != promise["promised_measure"]:
            return False
        if encumbrance.get("reserved_measure") != promise["promised_measure"]:
            return False
        if encumbrance.get("status") != "ENCUMBERED":
            return False
        if encumbrance.get("performance_proven") is not False:
            return False
        if encumbrance.get("payment_inferred") is not False:
            return False
        return _verify_signed(
            encumbrance,
            id_field="encumbrance_id",
            particular_field="steward_particular",
            domain=ENCUMBRANCE_DOMAIN,
            byte_domain=ENCUMBRANCE_BYTES,
        )
    except Exception:
        return False


def attest_successful_service_performance(
    snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    promise: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    encumbrance: dict[str, Any],
    execution_receipt: dict[str, Any],
    finalization: dict[str, Any],
    *,
    steward: IdentityKey,
) -> dict[str, Any]:
    if not verify_service_encumbrance(
        snapshot,
        offer,
        acceptance,
        promise,
        proposal,
        authorization,
        reservation,
        encumbrance,
    ):
        raise LightwalkerEconomyError("invalid service encumbrance")
    if not verify_execution_receipt(
        snapshot, proposal, authorization, execution_receipt
    ):
        raise LightwalkerEconomyError("invalid service execution receipt")
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError(
            "invalid service reservation finalization"
        )
    if execution_receipt.get("success") is not True:
        raise LightwalkerEconomyError(
            "failed execution cannot prove service performance"
        )
    if finalization.get("status") != "CONSUMED":
        raise LightwalkerEconomyError(
            "service performance requires consumed reservation"
        )
    if steward.particular() != promise["steward_particular"]:
        raise LightwalkerEconomyError("service attestor is not Guild offeror")

    return sign_obligation_performance(
        offer,
        acceptance,
        role="OFFEROR",
        signer=steward,
        evidence_ref=execution_receipt["execution_receipt_id"],
    )


def derive_capacity_backed_service_settlement(
    snapshot: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    promise: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    encumbrance: dict[str, Any],
    execution_receipt: dict[str, Any],
    finalization: dict[str, Any],
    service_attestation: dict[str, Any],
    counterparty_attestation: dict[str, Any],
    settlement: dict[str, Any],
) -> dict[str, Any]:
    if not verify_service_encumbrance(
        snapshot,
        offer,
        acceptance,
        promise,
        proposal,
        authorization,
        reservation,
        encumbrance,
    ):
        raise LightwalkerEconomyError("invalid service encumbrance")
    if not verify_execution_receipt(
        snapshot, proposal, authorization, execution_receipt
    ):
        raise LightwalkerEconomyError("invalid execution receipt")
    if execution_receipt.get("success") is not True:
        raise LightwalkerEconomyError(
            "failed execution cannot support service settlement"
        )
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError("invalid reservation finalization")
    if finalization.get("status") != "CONSUMED":
        raise LightwalkerEconomyError(
            "service settlement requires consumed reservation"
        )
    if not verify_obligation_performance(
        offer, acceptance, service_attestation
    ):
        raise LightwalkerEconomyError(
            "invalid service performance attestation"
        )
    if service_attestation.get("role") != "OFFEROR":
        raise LightwalkerEconomyError(
            "service attestation must be offeror performance"
        )
    if (
        service_attestation.get("evidence_ref")
        != execution_receipt["execution_receipt_id"]
    ):
        raise LightwalkerEconomyError(
            "service performance is not bound to execution receipt"
        )
    if not verify_obligation_performance(
        offer, acceptance, counterparty_attestation
    ):
        raise LightwalkerEconomyError(
            "invalid counterparty performance attestation"
        )
    if counterparty_attestation.get("role") != "ACCEPTOR":
        raise LightwalkerEconomyError(
            "counterparty attestation must be acceptor performance"
        )
    attestations = [service_attestation, counterparty_attestation]
    if not verify_exchange_settlement(
        offer, acceptance, attestations, settlement
    ):
        raise LightwalkerEconomyError(
            "invalid capacity-backed service settlement"
        )

    body = {
        "kind": WITNESS_KIND,
        "version": WITNESS_VERSION,
        "authority": "derived-service-settlement-linkage",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "promise_id": promise["promise_id"],
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "encumbrance_id": encumbrance["encumbrance_id"],
        "reservation_id": reservation["reservation_id"],
        "execution_receipt_id": execution_receipt["execution_receipt_id"],
        "finalization_id": finalization["finalization_id"],
        "service_attestation_id": service_attestation["attestation_id"],
        "counterparty_attestation_id": counterparty_attestation[
            "attestation_id"
        ],
        "settlement_id": settlement["settlement_id"],
        "reserved_measure": reservation["reserved_measure"],
        "service_performed": True,
        "payment_inferred": False,
        "execution_authority": "none",
        "laws": [
            "CAPACITY PROOF != PROMISE",
            "PROMISE != RESERVATION",
            "RESERVATION != PERFORMANCE",
            "PERFORMANCE != PAYMENT",
            "CONSUMPTION != PAYMENT",
        ],
    }
    return {**body, "witness_id": content_address(body)}


def make_capacity_backed_service_crossing(
    witness: dict[str, Any],
    *,
    signer: IdentityKey,
) -> dict[str, Any]:
    if witness.get("kind") != WITNESS_KIND:
        raise LightwalkerEconomyError(
            "invalid capacity-backed service witness"
        )
    if witness.get("execution_authority") != "none":
        raise LightwalkerEconomyError(
            "service settlement witness may not execute"
        )
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f'guild:{witness["guild_id"]}',
        "source_history_head": witness["witness_id"],
        "parents": [
            witness["promise_id"],
            witness["encumbrance_id"],
            witness["execution_receipt_id"],
            witness["settlement_id"],
        ],
        "declared_kind": "LIGHTWALKER_CAPACITY_BACKED_SERVICE_SETTLEMENT",
        "payload_refs": [
            witness["promise_id"],
            witness["reservation_id"],
            witness["execution_receipt_id"],
            witness["settlement_id"],
            witness["witness_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-capacity-backed-service-settlement",
                "witness_id": witness["witness_id"],
                "automatic_execution_requested": False,
                "payment_inference_requested": False,
                "ownership_transfer_requested": False,
            }
        ),
        "capability_ref": SERVICE_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {"guild_id": witness["guild_id"]},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-capacity-backed-service/v0",
            "promise_is_not_reservation": True,
            "reservation_is_not_performance": True,
            "performance_is_not_payment": True,
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
            "capacity-backed service crossing failed verification"
        )
    return signed


__all__ = [
    "attest_successful_service_performance",
    "derive_capacity_backed_service_settlement",
    "make_capacity_backed_service_crossing",
    "make_capacity_backed_service_promise",
    "reserve_accepted_service",
    "verify_capacity_backed_service_promise",
    "verify_service_encumbrance",
]
