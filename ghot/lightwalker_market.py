#!/usr/bin/env python3
"""Lightwalker Market 001 — a market without a canonical coin.

Economic objects remain distinct:
    VALUATION != OFFER != ACCEPTANCE != PERFORMANCE != SETTLEMENT

A Realm projection may inform an offer, but it does not compel the offer price.
Acceptance creates a bilateral commitment, not settlement. Settlement is a
deterministic record over two independently signed performance attestations.
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


OFFER_KIND = "ghot.lightwalker.market-offer"
OFFER_VERSION = "0"
ACCEPTANCE_KIND = "ghot.lightwalker.market-acceptance"
ACCEPTANCE_VERSION = "0"
ATTESTATION_KIND = "ghot.lightwalker.performance-attestation"
ATTESTATION_VERSION = "0"
SETTLEMENT_KIND = "ghot.lightwalker.settlement"
SETTLEMENT_VERSION = "0"

OFFER_CAPABILITY = "ghot.lightwalker-market-offer/v0"
ACCEPTANCE_CAPABILITY = "ghot.lightwalker-market-acceptance/v0"
SETTLEMENT_CAPABILITY = "ghot.lightwalker-market-settlement/v0"

ATTESTATION_DOMAIN = b"GHOT-LightwalkerPerformance-v0|"
ATTESTATION_SIGNING_DOMAIN = "ghot.lightwalker-performance-signature/v0"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return value


def _verify_projection(projection: dict[str, Any]) -> bool:
    if not isinstance(projection, dict):
        return False
    if projection.get("kind") != "ghot.lightwalker.assay-projection":
        return False
    if projection.get("version") != "0":
        return False
    projection_id = projection.get("projection_id")
    if not isinstance(projection_id, str):
        return False
    body = {key: value for key, value in projection.items() if key != "projection_id"}
    return content_address(body) == projection_id


def make_offer(
    projection: dict[str, Any],
    *,
    offeror_particular: str,
    deliverable_ref: str,
    asking_unit: str,
    asking_quantity: int,
    valid_through_cut: int,
) -> dict[str, Any]:
    if not _verify_projection(projection):
        raise LightwalkerEconomyError("invalid assay projection")
    body = {
        "kind": OFFER_KIND,
        "version": OFFER_VERSION,
        "authority": "offeror-local",
        "offeror_particular": _nonempty(offeror_particular, "offeror_particular"),
        "projection_id": projection["projection_id"],
        "workmark_id": projection["workmark_id"],
        "deliverable_ref": _nonempty(deliverable_ref, "deliverable_ref"),
        "consideration": {
            "realm_id": projection["realm_id"],
            "unit": _nonempty(asking_unit, "asking_unit"),
            "quantity": _nonnegative_int(asking_quantity, "asking_quantity"),
        },
        "valid_through_cut": _nonnegative_int(valid_through_cut, "valid_through_cut"),
        "laws": [
            "VALUATION != OFFER",
            "OFFER PRICE NEED NOT EQUAL PROJECTION",
            "OFFER != TRANSFER",
            "OFFER MAY EXPIRE UNACCEPTED",
        ],
    }
    return {**body, "offer_id": content_address(body)}


def verify_offer(offer: dict[str, Any]) -> bool:
    if not isinstance(offer, dict):
        return False
    if offer.get("kind") != OFFER_KIND or offer.get("version") != OFFER_VERSION:
        return False
    offer_id = offer.get("offer_id")
    if not isinstance(offer_id, str):
        return False
    body = {key: value for key, value in offer.items() if key != "offer_id"}
    return content_address(body) == offer_id


def make_offer_crossing(
    offer: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not verify_offer(offer):
        raise LightwalkerEconomyError("invalid offer")
    if signer.particular() != offer["offeror_particular"]:
        raise LightwalkerEconomyError("offer signer does not match offeror")

    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": "LIGHTWALKER_MARKET_OFFER",
        "payload_refs": [
            offer["projection_id"],
            offer["workmark_id"],
            offer["offer_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-market-offer",
                "offer_id": offer["offer_id"],
                "automatic_acceptance_requested": False,
                "automatic_settlement_requested": False,
            }
        ),
        "capability_ref": OFFER_CAPABILITY,
        "privacy_policy": {"transport": "replaceable", "payload_encryption": False},
        "audience_policy": {"capability": OFFER_CAPABILITY},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-market-offer/v0",
            "offer_is_not_acceptance": True,
            "offer_is_not_settlement": True,
        },
        "signing": {"algorithm": "", "public_key": {}, "signature": "", "domain": ""},
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("offer crossing failed verification")
    return signed


def accept_offer(
    offer: dict[str, Any],
    *,
    acceptor_particular: str,
    accepted_at_cut: int,
) -> dict[str, Any]:
    if not verify_offer(offer):
        raise LightwalkerEconomyError("invalid offer")
    cut = _nonnegative_int(accepted_at_cut, "accepted_at_cut")
    if cut > int(offer["valid_through_cut"]):
        raise LightwalkerEconomyError("offer expired before acceptance")

    terms = {
        "deliverable_ref": offer["deliverable_ref"],
        "consideration": offer["consideration"],
        "valid_through_cut": offer["valid_through_cut"],
    }
    body = {
        "kind": ACCEPTANCE_KIND,
        "version": ACCEPTANCE_VERSION,
        "authority": "acceptor-local",
        "offer_id": offer["offer_id"],
        "offeror_particular": offer["offeror_particular"],
        "acceptor_particular": _nonempty(acceptor_particular, "acceptor_particular"),
        "accepted_at_cut": cut,
        "terms_digest": content_address(terms),
        "status": "ACCEPTED",
        "laws": [
            "OFFER != ACCEPTANCE",
            "ACCEPTANCE != SETTLEMENT",
            "ACCEPTANCE BINDS ONLY DECLARED TERMS",
        ],
    }
    return {**body, "acceptance_id": content_address(body)}


def verify_acceptance(offer: dict[str, Any], acceptance: dict[str, Any]) -> bool:
    if not verify_offer(offer) or not isinstance(acceptance, dict):
        return False
    if acceptance.get("kind") != ACCEPTANCE_KIND or acceptance.get("version") != ACCEPTANCE_VERSION:
        return False
    if acceptance.get("offer_id") != offer["offer_id"]:
        return False
    if acceptance.get("offeror_particular") != offer["offeror_particular"]:
        return False
    if int(acceptance.get("accepted_at_cut", -1)) > int(offer["valid_through_cut"]):
        return False
    terms = {
        "deliverable_ref": offer["deliverable_ref"],
        "consideration": offer["consideration"],
        "valid_through_cut": offer["valid_through_cut"],
    }
    if acceptance.get("terms_digest") != content_address(terms):
        return False
    acceptance_id = acceptance.get("acceptance_id")
    if not isinstance(acceptance_id, str):
        return False
    body = {key: value for key, value in acceptance.items() if key != "acceptance_id"}
    return content_address(body) == acceptance_id


def make_acceptance_crossing(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not verify_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid acceptance")
    if signer.particular() != acceptance["acceptor_particular"]:
        raise LightwalkerEconomyError("acceptance signer does not match acceptor")

    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": "LIGHTWALKER_MARKET_ACCEPTANCE",
        "payload_refs": [offer["offer_id"], acceptance["acceptance_id"]],
        "requested_effect": identity_safe(
            {
                "operation": "record-market-acceptance",
                "offer_id": offer["offer_id"],
                "acceptance_id": acceptance["acceptance_id"],
                "automatic_settlement_requested": False,
            }
        ),
        "capability_ref": ACCEPTANCE_CAPABILITY,
        "privacy_policy": {"transport": "replaceable", "payload_encryption": False},
        "audience_policy": {"capability": ACCEPTANCE_CAPABILITY},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-market-acceptance/v0",
            "acceptance_is_not_settlement": True,
        },
        "signing": {"algorithm": "", "public_key": {}, "signature": "", "domain": ""},
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("acceptance crossing failed verification")
    return signed


def _attestation_signature_bytes(attestation: dict[str, Any]) -> bytes:
    body = {
        key: value
        for key, value in attestation.items()
        if key not in {"attestation_id", "signing"}
    }
    return ATTESTATION_DOMAIN + canonical_bytes(
        {"attestation_id": content_address(body), **body}
    )


def sign_performance(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    role: str,
    signer: IdentityKey,
    evidence_ref: str,
) -> dict[str, Any]:
    if not verify_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid accepted offer")
    if role not in {"DELIVERY", "CONSIDERATION"}:
        raise LightwalkerEconomyError("unsupported performance role")

    expected_actor = (
        offer["offeror_particular"]
        if role == "DELIVERY"
        else acceptance["acceptor_particular"]
    )
    if signer.particular() != expected_actor:
        raise LightwalkerEconomyError("performance signer does not match role")

    body = {
        "kind": ATTESTATION_KIND,
        "version": ATTESTATION_VERSION,
        "acceptance_id": acceptance["acceptance_id"],
        "offer_id": offer["offer_id"],
        "role": role,
        "actor_particular": signer.particular(),
        "evidence_ref": _nonempty(evidence_ref, "evidence_ref"),
        "status": "FULFILLED",
    }
    attestation_id = content_address(body)
    unsigned = {
        **body,
        "attestation_id": attestation_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": ATTESTATION_SIGNING_DOMAIN,
        },
    }
    unsigned["signing"]["signature"] = signer.sign(
        _attestation_signature_bytes(unsigned)
    )
    return unsigned


def verify_performance_attestation(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestation: dict[str, Any],
) -> bool:
    try:
        if not verify_acceptance(offer, acceptance):
            return False
        if not isinstance(attestation, dict):
            return False
        if attestation.get("kind") != ATTESTATION_KIND or attestation.get("version") != ATTESTATION_VERSION:
            return False
        if attestation.get("acceptance_id") != acceptance["acceptance_id"]:
            return False
        if attestation.get("offer_id") != offer["offer_id"]:
            return False
        role = attestation.get("role")
        if role not in {"DELIVERY", "CONSIDERATION"}:
            return False
        expected_actor = (
            offer["offeror_particular"]
            if role == "DELIVERY"
            else acceptance["acceptor_particular"]
        )
        if attestation.get("actor_particular") != expected_actor:
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


def settle(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestations: list[dict[str, Any]],
) -> dict[str, Any]:
    if not verify_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("cannot settle invalid acceptance")
    if len(attestations) != 2:
        raise LightwalkerEconomyError("settlement requires exactly two performance attestations")
    for attestation in attestations:
        if not verify_performance_attestation(offer, acceptance, attestation):
            raise LightwalkerEconomyError("invalid performance attestation")

    by_role = {item["role"]: item for item in attestations}
    if set(by_role) != {"DELIVERY", "CONSIDERATION"}:
        raise LightwalkerEconomyError("both delivery and consideration are required")

    body = {
        "kind": SETTLEMENT_KIND,
        "version": SETTLEMENT_VERSION,
        "authority": "bilateral-evidence-only",
        "offer_id": offer["offer_id"],
        "acceptance_id": acceptance["acceptance_id"],
        "workmark_id": offer["workmark_id"],
        "projection_id": offer["projection_id"],
        "deliverable_ref": offer["deliverable_ref"],
        "consideration": offer["consideration"],
        "delivery_attestation_id": by_role["DELIVERY"]["attestation_id"],
        "consideration_attestation_id": by_role["CONSIDERATION"]["attestation_id"],
        "status": "SETTLED",
        "laws": [
            "VALUATION != OFFER",
            "OFFER != ACCEPTANCE",
            "ACCEPTANCE != PERFORMANCE",
            "PERFORMANCE != SETTLEMENT",
            "SETTLEMENT != WORKMARK",
            "SETTLEMENT DOES NOT CREATE UNIVERSAL MONEY",
        ],
    }
    return {**body, "settlement_id": content_address(body)}


def verify_settlement(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    attestations: list[dict[str, Any]],
    settlement: dict[str, Any],
) -> bool:
    try:
        expected = settle(offer, acceptance, attestations)
        return expected == settlement
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
    body = {key: value for key, value in settlement.items() if key != "settlement_id"}
    if content_address(body) != settlement.get("settlement_id"):
        raise LightwalkerEconomyError("settlement address mismatch")

    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": "LIGHTWALKER_MARKET_SETTLEMENT",
        "payload_refs": [
            settlement["workmark_id"],
            settlement["projection_id"],
            settlement["offer_id"],
            settlement["acceptance_id"],
            settlement["settlement_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "record-bilateral-settlement",
                "settlement_id": settlement["settlement_id"],
                "mint_authority_requested": False,
                "balance_mutation_requested": False,
                "ownership_transfer_inferred": False,
            }
        ),
        "capability_ref": SETTLEMENT_CAPABILITY,
        "privacy_policy": {"transport": "replaceable", "payload_encryption": False},
        "audience_policy": {"capability": SETTLEMENT_CAPABILITY},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-market-settlement/v0",
            "settlement_is_bilateral_evidence": True,
            "settlement_is_not_workmark": True,
        },
        "signing": {"algorithm": "", "public_key": {}, "signature": "", "domain": ""},
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("settlement crossing failed verification")
    return signed


__all__ = [
    "ACCEPTANCE_KIND",
    "ACCEPTANCE_VERSION",
    "ATTESTATION_KIND",
    "ATTESTATION_VERSION",
    "OFFER_KIND",
    "OFFER_VERSION",
    "SETTLEMENT_KIND",
    "SETTLEMENT_VERSION",
    "accept_offer",
    "make_acceptance_crossing",
    "make_offer",
    "make_offer_crossing",
    "make_settlement_crossing",
    "settle",
    "sign_performance",
    "verify_acceptance",
    "verify_offer",
    "verify_performance_attestation",
    "verify_settlement",
]
