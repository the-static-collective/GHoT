#!/usr/bin/env python3
"""Lightwalker Heterogeneous Exchange 001.

This protocol freezes the claim that exchange can be composed before currency
is standardized.

Two obligations remain typed and incommensurate. The protocol carries them,
binds consent to them, verifies role-local performance, and records bilateral
settlement without inventing a common unit, exchange rate, or universal price.

Core laws:
    OBLIGATION A != OBLIGATION B
    ORIENTATION != PRICE
    CONSENT != PERFORMANCE
    PERFORMANCE != SETTLEMENT
    SETTLEMENT != CONVERSION
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import LightwalkerEconomyError, canonical_bytes, content_address
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


OBLIGATION_KIND = "ghot.lightwalker.exchange-obligation"
OBLIGATION_VERSION = "0"
OFFER_KIND = "ghot.lightwalker.heterogeneous-offer"
OFFER_VERSION = "0"
ACCEPTANCE_KIND = "ghot.lightwalker.heterogeneous-acceptance"
ACCEPTANCE_VERSION = "0"
ATTESTATION_KIND = "ghot.lightwalker.heterogeneous-performance"
ATTESTATION_VERSION = "0"
SETTLEMENT_KIND = "ghot.lightwalker.heterogeneous-settlement"
SETTLEMENT_VERSION = "0"

OFFER_CAPABILITY = "ghot.lightwalker-heterogeneous-offer/v0"
ACCEPTANCE_CAPABILITY = "ghot.lightwalker-heterogeneous-acceptance/v0"
SETTLEMENT_CAPABILITY = "ghot.lightwalker-heterogeneous-settlement/v0"

ATTESTATION_DOMAIN = b"GHOT-LightwalkerHeterogeneousPerformance-v0|"
ATTESTATION_SIGNING_DOMAIN = (
    "ghot.lightwalker-heterogeneous-performance-signature/v0"
)

FORBIDDEN_EQUIVALENCE_KEYS = {
    "price",
    "exchange_rate",
    "common_unit",
    "currency",
    "monetary_amount",
    "equivalent_value",
    "conversion_rate",
}


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return value


def _assert_no_equivalence_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_EQUIVALENCE_KEYS:
                raise LightwalkerEconomyError(
                    f"forbidden implicit-conversion field at {path}.{key}"
                )
            _assert_no_equivalence_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_equivalence_fields(item, f"{path}[{index}]")


def make_obligation(
    *,
    obligation_type: str,
    resource_ref: str,
    terms: dict[str, Any],
    evidence_policy: str,
) -> dict[str, Any]:
    if not isinstance(terms, dict):
        raise LightwalkerEconomyError("obligation terms must be an object")
    _assert_no_equivalence_fields(terms)
    body = {
        "kind": OBLIGATION_KIND,
        "version": OBLIGATION_VERSION,
        "obligation_type": _nonempty(obligation_type, "obligation_type"),
        "resource_ref": _nonempty(resource_ref, "resource_ref"),
        "terms": identity_safe(terms),
        "evidence_policy": _nonempty(evidence_policy, "evidence_policy"),
        "laws": [
            "OBLIGATION TYPE != UNIVERSAL UNIT",
            "OBLIGATION TERMS DO NOT IMPLY EXCHANGE RATE",
        ],
    }
    return {**body, "obligation_id": content_address(body)}


def verify_obligation(obligation: dict[str, Any]) -> bool:
    try:
        if not isinstance(obligation, dict):
            return False
        if obligation.get("kind") != OBLIGATION_KIND:
            return False
        if obligation.get("version") != OBLIGATION_VERSION:
            return False
        _assert_no_equivalence_fields(obligation)
        obligation_id = obligation.get("obligation_id")
        if not isinstance(obligation_id, str):
            return False
        body = {
            key: value
            for key, value in obligation.items()
            if key != "obligation_id"
        }
        return content_address(body) == obligation_id
    except LightwalkerEconomyError:
        return False


def make_exchange_offer(
    *,
    offeror_particular: str,
    offeror_obligation: dict[str, Any],
    acceptor_obligation: dict[str, Any],
    orientation_refs: list[str],
    valid_through_cut: int,
) -> dict[str, Any]:
    if not verify_obligation(offeror_obligation):
        raise LightwalkerEconomyError("invalid offeror obligation")
    if not verify_obligation(acceptor_obligation):
        raise LightwalkerEconomyError("invalid acceptor obligation")
    if not isinstance(orientation_refs, list) or any(
        not isinstance(item, str) or not item for item in orientation_refs
    ):
        raise LightwalkerEconomyError(
            "orientation_refs must be a list of non-empty strings"
        )

    body = {
        "kind": OFFER_KIND,
        "version": OFFER_VERSION,
        "authority": "offeror-local",
        "offeror_particular": _nonempty(
            offeror_particular, "offeror_particular"
        ),
        "offeror_obligation": offeror_obligation,
        "acceptor_obligation": acceptor_obligation,
        "orientation_refs": list(orientation_refs),
        "valid_through_cut": _nonnegative_int(
            valid_through_cut, "valid_through_cut"
        ),
        "laws": [
            "ORIENTATION != PRICE",
            "OBLIGATION A != OBLIGATION B",
            "NO COMMON UNIT REQUIRED",
            "OFFER != ACCEPTANCE",
        ],
    }
    _assert_no_equivalence_fields(body)
    return {**body, "offer_id": content_address(body)}


def verify_exchange_offer(offer: dict[str, Any]) -> bool:
    try:
        if not isinstance(offer, dict):
            return False
        if offer.get("kind") != OFFER_KIND or offer.get("version") != OFFER_VERSION:
            return False
        if not verify_obligation(offer.get("offeror_obligation")):
            return False
        if not verify_obligation(offer.get("acceptor_obligation")):
            return False
        _assert_no_equivalence_fields(offer)
        offer_id = offer.get("offer_id")
        if not isinstance(offer_id, str):
            return False
        body = {key: value for key, value in offer.items() if key != "offer_id"}
        return content_address(body) == offer_id
    except LightwalkerEconomyError:
        return False


def _make_crossing(
    *,
    signer: IdentityKey,
    node_id: str,
    declared_kind: str,
    payload_refs: list[str],
    requested_effect: dict[str, Any],
    capability_ref: str,
    profile: str,
    extensions: dict[str, Any],
) -> dict[str, Any]:
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": declared_kind,
        "payload_refs": payload_refs,
        "requested_effect": identity_safe(requested_effect),
        "capability_ref": capability_ref,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {"capability": capability_ref},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": profile,
            **identity_safe(extensions),
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
        raise LightwalkerEconomyError("heterogeneous crossing failed verification")
    return signed


def make_offer_crossing(
    offer: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not verify_exchange_offer(offer):
        raise LightwalkerEconomyError("invalid heterogeneous offer")
    if signer.particular() != offer["offeror_particular"]:
        raise LightwalkerEconomyError("offer signer does not match offeror")
    return _make_crossing(
        signer=signer,
        node_id=node_id,
        declared_kind="LIGHTWALKER_HETEROGENEOUS_OFFER",
        payload_refs=[
            offer["offeror_obligation"]["obligation_id"],
            offer["acceptor_obligation"]["obligation_id"],
            offer["offer_id"],
        ],
        requested_effect={
            "operation": "consider-heterogeneous-offer",
            "offer_id": offer["offer_id"],
            "automatic_acceptance_requested": False,
            "automatic_conversion_requested": False,
            "automatic_settlement_requested": False,
        },
        capability_ref=OFFER_CAPABILITY,
        profile="lightwalker-heterogeneous-offer/v0",
        extensions={
            "orientation_is_not_price": True,
            "no_common_unit_required": True,
        },
    )


def accept_exchange_offer(
    offer: dict[str, Any],
    *,
    acceptor_particular: str,
    accepted_at_cut: int,
) -> dict[str, Any]:
    if not verify_exchange_offer(offer):
        raise LightwalkerEconomyError("invalid heterogeneous offer")
    cut = _nonnegative_int(accepted_at_cut, "accepted_at_cut")
    if cut > int(offer["valid_through_cut"]):
        raise LightwalkerEconomyError("offer expired before acceptance")

    terms = {
        "offeror_obligation": offer["offeror_obligation"],
        "acceptor_obligation": offer["acceptor_obligation"],
        "orientation_refs": offer["orientation_refs"],
        "valid_through_cut": offer["valid_through_cut"],
    }
    body = {
        "kind": ACCEPTANCE_KIND,
        "version": ACCEPTANCE_VERSION,
        "authority": "acceptor-local",
        "offer_id": offer["offer_id"],
        "offeror_particular": offer["offeror_particular"],
        "acceptor_particular": _nonempty(
            acceptor_particular, "acceptor_particular"
        ),
        "accepted_at_cut": cut,
        "terms_digest": content_address(terms),
        "status": "ACCEPTED",
        "laws": [
            "OFFER != ACCEPTANCE",
            "ACCEPTANCE DOES NOT CREATE CONVERSION RATE",
            "ACCEPTANCE != PERFORMANCE",
            "ACCEPTANCE != SETTLEMENT",
        ],
    }
    return {**body, "acceptance_id": content_address(body)}


def verify_exchange_acceptance(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
) -> bool:
    try:
        if not verify_exchange_offer(offer):
            return False
        if not isinstance(acceptance, dict):
            return False
        if acceptance.get("kind") != ACCEPTANCE_KIND:
            return False
        if acceptance.get("version") != ACCEPTANCE_VERSION:
            return False
        if acceptance.get("offer_id") != offer["offer_id"]:
            return False
        if acceptance.get("offeror_particular") != offer["offeror_particular"]:
            return False
        cut = int(acceptance.get("accepted_at_cut", -1))
        if cut < 0 or cut > int(offer["valid_through_cut"]):
            return False
        terms = {
            "offeror_obligation": offer["offeror_obligation"],
            "acceptor_obligation": offer["acceptor_obligation"],
            "orientation_refs": offer["orientation_refs"],
            "valid_through_cut": offer["valid_through_cut"],
        }
        if acceptance.get("terms_digest") != content_address(terms):
            return False
        acceptance_id = acceptance.get("acceptance_id")
        if not isinstance(acceptance_id, str):
            return False
        body = {
            key: value
            for key, value in acceptance.items()
            if key != "acceptance_id"
        }
        return content_address(body) == acceptance_id
    except (TypeError, ValueError):
        return False


def make_acceptance_crossing(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid heterogeneous acceptance")
    if signer.particular() != acceptance["acceptor_particular"]:
        raise LightwalkerEconomyError("acceptance signer does not match acceptor")
    return _make_crossing(
        signer=signer,
        node_id=node_id,
        declared_kind="LIGHTWALKER_HETEROGENEOUS_ACCEPTANCE",
        payload_refs=[
            offer["offer_id"],
            acceptance["acceptance_id"],
        ],
        requested_effect={
            "operation": "record-heterogeneous-acceptance",
            "offer_id": offer["offer_id"],
            "acceptance_id": acceptance["acceptance_id"],
            "automatic_conversion_requested": False,
            "automatic_settlement_requested": False,
        },
        capability_ref=ACCEPTANCE_CAPABILITY,
        profile="lightwalker-heterogeneous-acceptance/v0",
        extensions={
            "acceptance_is_not_conversion": True,
            "acceptance_is_not_settlement": True,
        },
    )


def _attestation_signature_bytes(attestation: dict[str, Any]) -> bytes:
    body = {
        key: value
        for key, value in attestation.items()
        if key not in {"attestation_id", "signing"}
    }
    return ATTESTATION_DOMAIN + canonical_bytes(
        {"attestation_id": content_address(body), **body}
    )


def sign_obligation_performance(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    role: str,
    signer: IdentityKey,
    evidence_ref: str,
) -> dict[str, Any]:
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid accepted heterogeneous offer")
    if role not in {"OFFEROR", "ACCEPTOR"}:
        raise LightwalkerEconomyError("unsupported heterogeneous role")

    if role == "OFFEROR":
        expected_actor = offer["offeror_particular"]
        obligation = offer["offeror_obligation"]
    else:
        expected_actor = acceptance["acceptor_particular"]
        obligation = offer["acceptor_obligation"]

    if signer.particular() != expected_actor:
        raise LightwalkerEconomyError("performance signer does not match role")

    body = {
        "kind": ATTESTATION_KIND,
        "version": ATTESTATION_VERSION,
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "role": role,
        "actor_particular": expected_actor,
        "obligation_id": obligation["obligation_id"],
        "evidence_ref": _nonempty(evidence_ref, "evidence_ref"),
        "status": "FULFILLED",
    }
    attestation_id = content_address(body)
    signed = {
        **body,
        "attestation_id": attestation_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": ATTESTATION_SIGNING_DOMAIN,
        },
    }
    signed["signing"]["signature"] = signer.sign(
        _attestation_signature_bytes(signed)
    )
    return signed


def verify_obligation_performance(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestation: dict[str, Any],
) -> bool:
    try:
        if not verify_exchange_acceptance(offer, acceptance):
            return False
        if not isinstance(attestation, dict):
            return False
        if attestation.get("kind") != ATTESTATION_KIND:
            return False
        if attestation.get("version") != ATTESTATION_VERSION:
            return False
        if attestation.get("offer_id") != offer["offer_id"]:
            return False
        if attestation.get("acceptance_id") != acceptance["acceptance_id"]:
            return False

        role = attestation.get("role")
        if role == "OFFEROR":
            expected_actor = offer["offeror_particular"]
            obligation = offer["offeror_obligation"]
        elif role == "ACCEPTOR":
            expected_actor = acceptance["acceptor_particular"]
            obligation = offer["acceptor_obligation"]
        else:
            return False

        if attestation.get("actor_particular") != expected_actor:
            return False
        if attestation.get("obligation_id") != obligation["obligation_id"]:
            return False

        body = {
            key: value
            for key, value in attestation.items()
            if key not in {"attestation_id", "signing"}
        }
        if attestation.get("attestation_id") != content_address(body):
            return False

        signing = attestation.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != ATTESTATION_SIGNING_DOMAIN:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != expected_actor:
            return False
        return verify_p256(
            public_key,
            _attestation_signature_bytes(attestation),
            str(signing.get("signature") or ""),
        )
    except (TypeError, ValueError, LightwalkerEconomyError):
        return False


def settle_exchange(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestations: list[dict[str, Any]],
) -> dict[str, Any]:
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError(
            "cannot settle invalid heterogeneous acceptance"
        )
    if len(attestations) != 2:
        raise LightwalkerEconomyError(
            "heterogeneous settlement requires two performance attestations"
        )
    for item in attestations:
        if not verify_obligation_performance(offer, acceptance, item):
            raise LightwalkerEconomyError(
                "invalid heterogeneous performance attestation"
            )
    by_role = {item["role"]: item for item in attestations}
    if set(by_role) != {"OFFEROR", "ACCEPTOR"}:
        raise LightwalkerEconomyError(
            "both heterogeneous obligations must be fulfilled"
        )

    body = {
        "kind": SETTLEMENT_KIND,
        "version": SETTLEMENT_VERSION,
        "authority": "bilateral-evidence-only",
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "offeror_obligation": offer["offeror_obligation"],
        "acceptor_obligation": offer["acceptor_obligation"],
        "orientation_refs": offer["orientation_refs"],
        "offeror_attestation_id": by_role["OFFEROR"]["attestation_id"],
        "acceptor_attestation_id": by_role["ACCEPTOR"]["attestation_id"],
        "status": "SETTLED",
        "laws": [
            "OBLIGATION A != OBLIGATION B",
            "SETTLEMENT != CONVERSION",
            "SETTLEMENT DOES NOT CREATE COMMON UNIT",
            "SETTLEMENT DOES NOT CREATE UNIVERSAL MONEY",
            "BILATERAL PERFORMANCE != GLOBAL VALUATION",
        ],
    }
    _assert_no_equivalence_fields(body)
    return {**body, "settlement_id": content_address(body)}


def verify_exchange_settlement(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestations: list[dict[str, Any]],
    settlement: dict[str, Any],
) -> bool:
    try:
        return settle_exchange(
            offer, acceptance, attestations
        ) == settlement
    except LightwalkerEconomyError:
        return False


def make_settlement_crossing(
    settlement: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not isinstance(settlement, dict):
        raise LightwalkerEconomyError("settlement must be an object")
    _assert_no_equivalence_fields(settlement)
    body = {
        key: value
        for key, value in settlement.items()
        if key != "settlement_id"
    }
    if content_address(body) != settlement.get("settlement_id"):
        raise LightwalkerEconomyError("heterogeneous settlement address mismatch")

    return _make_crossing(
        signer=signer,
        node_id=node_id,
        declared_kind="LIGHTWALKER_HETEROGENEOUS_SETTLEMENT",
        payload_refs=[
            settlement["offeror_obligation"]["obligation_id"],
            settlement["acceptor_obligation"]["obligation_id"],
            settlement["offer_id"],
            settlement["acceptance_id"],
            settlement["settlement_id"],
        ],
        requested_effect={
            "operation": "record-heterogeneous-settlement",
            "settlement_id": settlement["settlement_id"],
            "conversion_rate_requested": False,
            "common_unit_requested": False,
            "mint_authority_requested": False,
            "balance_mutation_requested": False,
            "ownership_transfer_inferred": False,
        },
        capability_ref=SETTLEMENT_CAPABILITY,
        profile="lightwalker-heterogeneous-settlement/v0",
        extensions={
            "settlement_is_bilateral_evidence": True,
            "settlement_is_not_conversion": True,
            "settlement_is_not_currency": True,
        },
    )


__all__ = [
    "ACCEPTANCE_KIND",
    "ACCEPTANCE_VERSION",
    "ATTESTATION_KIND",
    "ATTESTATION_VERSION",
    "FORBIDDEN_EQUIVALENCE_KEYS",
    "OBLIGATION_KIND",
    "OBLIGATION_VERSION",
    "OFFER_KIND",
    "OFFER_VERSION",
    "SETTLEMENT_KIND",
    "SETTLEMENT_VERSION",
    "accept_exchange_offer",
    "make_acceptance_crossing",
    "make_exchange_offer",
    "make_obligation",
    "make_offer_crossing",
    "make_settlement_crossing",
    "settle_exchange",
    "sign_obligation_performance",
    "verify_exchange_acceptance",
    "verify_exchange_offer",
    "verify_exchange_settlement",
    "verify_obligation",
    "verify_obligation_performance",
]
