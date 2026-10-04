#!/usr/bin/env python3
"""Lightwalker Metabolic Exchange 001.

Bridge heterogeneous bilateral settlement into operational capacity without
collapsing settlement, Treasury admission, lease authority, or consumption.

Core laws:
    SETTLEMENT != CAPACITY
    ACQUISITION != EXECUTION AUTHORITY
    ECONOMIC VALUE != OPERATIONAL CAPACITY
    TREASURY ENTRY != LEASE
    CONSUMPTION != PAYMENT
    ECONOMIC HISTORY + AUTHORITY HISTORY MAY CROSS WITHOUT COLLAPSE
"""

from __future__ import annotations

from typing import Any

from lightwalker_authority_metabolism import (
    METABOLISM_KIND,
    derive_authority_metabolism,
)
from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_treasury import (
    make_treasury_entry,
    verify_treasury_snapshot,
)
from lightwalker_heterogeneous_exchange import (
    verify_exchange_settlement,
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


ACQUISITION_KIND = "ghot.lightwalker.settled-capacity-acquisition"
ACQUISITION_VERSION = "0"
WITNESS_KIND = "ghot.lightwalker.metabolic-exchange"
WITNESS_VERSION = "0"

ACQUISITION_DOMAIN = "ghot.lightwalker-settled-capacity-acquisition-signature/v0"
ACQUISITION_BYTES = b"GHOT-LightwalkerSettledCapacityAcquisition-v0|"
METABOLIC_EXCHANGE_CAPABILITY = "ghot.lightwalker-metabolic-exchange/v0"


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
) -> dict[str, Any]:
    item_id = content_address(body)
    value = {
        **body,
        id_field: item_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": ACQUISITION_DOMAIN,
        },
    }
    value["signing"]["signature"] = signer.sign(
        ACQUISITION_BYTES + canonical_bytes({id_field: item_id, **body})
    )
    return value


def _verify_signed(
    value: dict[str, Any],
    *,
    id_field: str,
    particular_field: str,
) -> bool:
    try:
        signing = value.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != ACQUISITION_DOMAIN:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != value.get(particular_field):
            return False
        body = {
            k: v
            for k, v in value.items()
            if k not in {id_field, "signing"}
        }
        item_id = value.get(id_field)
        if not isinstance(item_id, str) or content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            ACQUISITION_BYTES
            + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def _capacity_obligation_for_guild(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    guild_particular: str,
) -> dict[str, Any]:
    if acceptance.get("acceptor_particular") == guild_particular:
        return offer["offeror_obligation"]
    if offer.get("offeror_particular") == guild_particular:
        return offer["acceptor_obligation"]
    raise LightwalkerEconomyError(
        "Guild is not a party to the heterogeneous exchange"
    )


def _settled_capacity_acquisition_body(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestations: list[dict[str, Any]],
    settlement: dict[str, Any],
    *,
    steward_particular: str,
    guild_id: str,
    capacity_subject_ref: str,
    admitted_at_cut: int,
) -> dict[str, Any]:
    if not verify_exchange_settlement(
        offer, acceptance, attestations, settlement
    ):
        raise LightwalkerEconomyError("invalid heterogeneous settlement")

    obligation = _capacity_obligation_for_guild(
        offer,
        acceptance,
        guild_particular=steward_particular,
    )
    if obligation.get("obligation_type") != "compute-capacity-delivery":
        raise LightwalkerEconomyError(
            "settlement does not deliver compute capacity to Guild"
        )

    terms = obligation.get("terms")
    if not isinstance(terms, dict):
        raise LightwalkerEconomyError("capacity obligation terms missing")
    unit = _nonempty(terms.get("unit"), "capacity unit")
    quantity = _nni(terms.get("quantity"), "capacity quantity")
    if quantity <= 0:
        raise LightwalkerEconomyError("capacity quantity must be > 0")

    matching = [
        item
        for item in attestations
        if item.get("obligation_id") == obligation["obligation_id"]
        and item.get("status") == "FULFILLED"
    ]
    if len(matching) != 1:
        raise LightwalkerEconomyError(
            "capacity obligation needs one exact performance attestation"
        )

    return {
        "kind": ACQUISITION_KIND,
        "version": ACQUISITION_VERSION,
        "authority": "guild-local-capacity-admission",
        "guild_id": _nonempty(guild_id, "guild_id"),
        "steward_particular": steward_particular,
        "settlement_id": settlement["settlement_id"],
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "capacity_obligation_id": obligation["obligation_id"],
        "capacity_performance_attestation_id": matching[0]["attestation_id"],
        "capacity_subject_ref": _nonempty(
            capacity_subject_ref, "capacity_subject_ref"
        ),
        "native_measure": {
            "unit": unit,
            "quantity": quantity,
        },
        "admitted_at_cut": _nni(admitted_at_cut, "admitted_at_cut"),
        "execution_authority_granted": False,
        "ownership_inferred": False,
        "laws": [
            "SETTLEMENT != CAPACITY",
            "ACQUISITION != EXECUTION AUTHORITY",
            "ECONOMIC VALUE != OPERATIONAL CAPACITY",
            "SETTLEMENT EVIDENCE MAY SUPPORT TREASURY ADMISSION",
        ],
    }


def make_settled_capacity_acquisition(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestations: list[dict[str, Any]],
    settlement: dict[str, Any],
    *,
    steward: IdentityKey,
    guild_id: str,
    capacity_subject_ref: str,
    admitted_at_cut: int,
) -> dict[str, Any]:
    body = _settled_capacity_acquisition_body(
        offer,
        acceptance,
        attestations,
        settlement,
        steward_particular=steward.particular(),
        guild_id=guild_id,
        capacity_subject_ref=capacity_subject_ref,
        admitted_at_cut=admitted_at_cut,
    )
    return _signed(
        body,
        id_field="acquisition_id",
        signer=steward,
    )


def verify_settled_capacity_acquisition(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestations: list[dict[str, Any]],
    settlement: dict[str, Any],
    acquisition: dict[str, Any],
) -> bool:
    try:
        expected_body = _settled_capacity_acquisition_body(
            offer,
            acceptance,
            attestations,
            settlement,
            steward_particular=acquisition["steward_particular"],
            guild_id=acquisition["guild_id"],
            capacity_subject_ref=acquisition["capacity_subject_ref"],
            admitted_at_cut=int(acquisition["admitted_at_cut"]),
        )
        actual_body = {
            k: v
            for k, v in acquisition.items()
            if k not in {"acquisition_id", "signing"}
        }
        if expected_body != actual_body:
            return False
        return _verify_signed(
            acquisition,
            id_field="acquisition_id",
            particular_field="steward_particular",
        )
    except Exception:
        return False


def acquisition_to_treasury_entry(
    acquisition: dict[str, Any],
) -> dict[str, Any]:
    if acquisition.get("kind") != ACQUISITION_KIND:
        raise LightwalkerEconomyError("invalid acquisition kind")
    if acquisition.get("execution_authority_granted") is not False:
        raise LightwalkerEconomyError(
            "acquisition may not carry execution authority"
        )
    if not _verify_signed(
        acquisition,
        id_field="acquisition_id",
        particular_field="steward_particular",
    ):
        raise LightwalkerEconomyError("invalid acquisition signature")

    return make_treasury_entry(
        category="capability",
        position="available",
        subject_ref=acquisition["capacity_subject_ref"],
        source_ref=acquisition["acquisition_id"],
        evidence_refs=[
            acquisition["settlement_id"],
            acquisition["capacity_obligation_id"],
            acquisition["capacity_performance_attestation_id"],
            acquisition["acquisition_id"],
        ],
        native_measure=acquisition["native_measure"],
        metadata={
            "economic_source": "heterogeneous-settlement",
            "settlement_id": acquisition["settlement_id"],
            "acquisition_id": acquisition["acquisition_id"],
            "execution_authority": False,
            "ownership_inferred": False,
        },
    )


def derive_metabolic_exchange_witness(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestations: list[dict[str, Any]],
    settlement: dict[str, Any],
    acquisition: dict[str, Any],
    treasury_snapshot: dict[str, Any],
    metabolism: dict[str, Any],
    *,
    root_lease: dict[str, Any],
    descendant_leases: list[dict[str, Any]],
    surrenders: list[dict[str, Any]],
    source_uses: list[dict[str, Any]],
    reclaim_receipts: list[dict[str, Any]],
    reissued_leases: list[dict[str, Any]],
    recycled_uses: list[dict[str, Any]],
    source_observed_cut: int,
    observed_cut: int,
) -> dict[str, Any]:
    if not verify_settled_capacity_acquisition(
        offer, acceptance, attestations, settlement, acquisition
    ):
        raise LightwalkerEconomyError("invalid settled capacity acquisition")
    if not verify_treasury_snapshot(treasury_snapshot):
        raise LightwalkerEconomyError("invalid Treasury snapshot")
    if treasury_snapshot["guild_id"] != acquisition["guild_id"]:
        raise LightwalkerEconomyError("Treasury belongs to another Guild")
    if (
        treasury_snapshot["steward_particular"]
        != acquisition["steward_particular"]
    ):
        raise LightwalkerEconomyError(
            "Treasury steward differs from acquisition steward"
        )

    expected_entry = acquisition_to_treasury_entry(acquisition)
    entry = next(
        (
            item
            for item in treasury_snapshot["entries"]
            if item["entry_id"] == expected_entry["entry_id"]
        ),
        None,
    )
    if entry is None:
        raise LightwalkerEconomyError(
            "Treasury lacks exact acquired capacity entry"
        )

    recomputed_metabolism = derive_authority_metabolism(
        treasury_snapshot,
        root_lease=root_lease,
        descendant_leases=descendant_leases,
        surrenders=surrenders,
        source_uses=source_uses,
        reclaim_receipts=reclaim_receipts,
        reissued_leases=reissued_leases,
        recycled_uses=recycled_uses,
        source_observed_cut=source_observed_cut,
        observed_cut=observed_cut,
    )
    if recomputed_metabolism != metabolism:
        raise LightwalkerEconomyError(
            "supplied metabolism does not match underlying operational history"
        )

    if metabolism.get("kind") != METABOLISM_KIND:
        raise LightwalkerEconomyError("invalid authority metabolism witness")
    if metabolism.get("conservation_status") != "BALANCED":
        raise LightwalkerEconomyError("authority metabolism is not balanced")
    if metabolism.get("spending_authority") != "none":
        raise LightwalkerEconomyError(
            "authority metabolism unexpectedly carries spending authority"
        )
    if metabolism.get("snapshot_id") != treasury_snapshot["snapshot_id"]:
        raise LightwalkerEconomyError(
            "metabolism roots in a different Treasury snapshot"
        )
    if metabolism.get("resource_entry_id") != entry["entry_id"]:
        raise LightwalkerEconomyError(
            "metabolism roots in a different capacity entry"
        )
    if (
        int(metabolism["totals"]["root_quantity"])
        > int(entry["native_measure"]["quantity"])
    ):
        raise LightwalkerEconomyError(
            "operational authority exceeds acquired Treasury capacity"
        )

    body = {
        "kind": WITNESS_KIND,
        "version": WITNESS_VERSION,
        "authority": "derived-economic-operational-linkage",
        "guild_id": treasury_snapshot["guild_id"],
        "settlement_id": settlement["settlement_id"],
        "acquisition_id": acquisition["acquisition_id"],
        "treasury_snapshot_id": treasury_snapshot["snapshot_id"],
        "treasury_entry_id": entry["entry_id"],
        "native_measure": entry["native_measure"],
        "metabolism_id": metabolism["metabolism_id"],
        "metabolism_history_digest": metabolism["history_digest"],
        "economic_authority": "bilateral-evidence-only",
        "operational_authority": "separate-derived-history",
        "execution_authority": "none",
        "ownership_inferred": False,
        "payment_inferred_from_consumption": False,
        "laws": [
            "SETTLEMENT != CAPACITY",
            "ACQUISITION != EXECUTION AUTHORITY",
            "ECONOMIC VALUE != OPERATIONAL CAPACITY",
            "TREASURY ENTRY != LEASE",
            "CONSUMPTION != PAYMENT",
            "ECONOMIC HISTORY + AUTHORITY HISTORY MAY CROSS WITHOUT COLLAPSE",
        ],
    }
    return {**body, "witness_id": content_address(body)}


def make_metabolic_exchange_crossing(
    witness: dict[str, Any],
    *,
    signer: IdentityKey,
) -> dict[str, Any]:
    if witness.get("kind") != WITNESS_KIND:
        raise LightwalkerEconomyError("invalid metabolic exchange witness")
    if witness.get("execution_authority") != "none":
        raise LightwalkerEconomyError(
            "metabolic exchange witness may not execute"
        )
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f'guild:{witness["guild_id"]}',
        "source_history_head": witness["witness_id"],
        "parents": [
            witness["settlement_id"],
            witness["acquisition_id"],
            witness["treasury_snapshot_id"],
            witness["metabolism_id"],
        ],
        "declared_kind": "LIGHTWALKER_METABOLIC_EXCHANGE",
        "payload_refs": [
            witness["settlement_id"],
            witness["acquisition_id"],
            witness["treasury_entry_id"],
            witness["metabolism_id"],
            witness["witness_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-metabolic-exchange-audit",
                "witness_id": witness["witness_id"],
                "automatic_execution_requested": False,
                "payment_inference_requested": False,
                "ownership_transfer_requested": False,
                "mint_authority_requested": False,
            }
        ),
        "capability_ref": METABOLIC_EXCHANGE_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {"guild_id": witness["guild_id"]},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-metabolic-exchange/v0",
            "settlement_is_not_capacity": True,
            "consumption_is_not_payment": True,
            "audit_is_not_execution_authority": True,
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
            "metabolic exchange crossing failed verification"
        )
    return signed


__all__ = [
    "acquisition_to_treasury_entry",
    "derive_metabolic_exchange_witness",
    "make_metabolic_exchange_crossing",
    "make_settled_capacity_acquisition",
    "verify_settled_capacity_acquisition",
]
