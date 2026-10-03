#!/usr/bin/env python3
"""Portable GHoT lease crossings using reLATTE Identity + Signature Profile v0.

011 used a bounded shared-secret bridge. 012 upgrades crossings and authority
receipts to the current reLATTE P-256 identity/signature profile.

The signed transport still does not establish human identity, semantic truth,
or admission. Queue authority remains owner-local.
"""

from __future__ import annotations

import uuid
from typing import Any

from relatte_identity import (
    IdentityKey,
    identity_safe,
    normalize_timestamp,
    sign_crossing,
    sign_receipt,
    timestamp_now,
    verify_crossing,
    verify_receipt,
)


CROSSING_SCHEMA = "relatte.crossing-envelope/v0"
RECEIPT_SCHEMA = "relatte.receipt/v0"
CAPABILITY_REF = "ghot.work-lease/v0"

ACTIONS = {"POLL", "CLAIM", "RENEW", "COMPLETE", "ABANDON"}


def make_crossing(
    action: str,
    *,
    signer: IdentityKey,
    authority_id: str,
    worker_id: str,
    worker_node_id: str,
    hold_id: str | None = None,
    dispatch_id: str | None = None,
    lease_id: str | None = None,
    lease_seconds: float | int | None = None,
    child_energy_plan_id: str | None = None,
    receipt_id: str | None = None,
    outcome: str | None = None,
    error: str | None = None,
    return_address: str | None = None,
    created_at: str | None = None,
    nonce: str | None = None,
) -> dict[str, Any]:
    action = action.upper()
    if action not in ACTIONS:
        raise ValueError(f"unknown portable lease action: {action}")

    created = normalize_timestamp(created_at) if created_at else timestamp_now()
    effect = identity_safe({
        "action": action,
        "authority_id": authority_id,
        "worker_id": worker_id,
        "worker_node_id": worker_node_id,
        "hold_id": hold_id,
        "dispatch_id": dispatch_id,
        "lease_id": lease_id,
        "lease_seconds": (
            str(lease_seconds) if lease_seconds is not None else None
        ),
        "child_energy_plan_id": child_energy_plan_id,
        "receipt_id": receipt_id,
        "outcome": outcome,
        "error": error,
        "nonce": nonce or f"nonce-{uuid.uuid4()}",
    })

    envelope = {
        "schema": CROSSING_SCHEMA,
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{worker_node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": f"GHOT_LEASE_{action}",
        "payload_refs": [],
        "requested_effect": effect,
        "capability_ref": CAPABILITY_REF,
        "privacy_policy": {
            "transport": "trusted-lan-v0",
            "payload_encryption": False,
        },
        "audience_policy": {
            "authority_id": authority_id,
        },
        "return_address": return_address,
        "created_at": created,
        "extensions": {
            "ghot_profile": "portable-work-lease/v1",
            "source_verification_profile": "relatte.identity-signature/v0",
            "public_key_identity_claimed": True,
        },
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    return sign_crossing(envelope, signer)


def validate_crossing_shape(envelope: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "crossing_id",
        "protocol_version",
        "source_particular",
        "source_world",
        "declared_kind",
        "payload_refs",
        "created_at",
        "signing",
    }
    missing = sorted(required - set(envelope))
    if missing:
        errors.append("missing: " + ", ".join(missing))
    if envelope.get("schema") != CROSSING_SCHEMA:
        errors.append("wrong crossing schema")
    if envelope.get("protocol_version") != "0":
        errors.append("wrong protocol version")
    if envelope.get("capability_ref") != CAPABILITY_REF:
        errors.append("wrong capability_ref")
    effect = envelope.get("requested_effect")
    if not isinstance(effect, dict):
        errors.append("requested_effect must be an object")
    elif effect.get("action") not in ACTIONS:
        errors.append("unknown requested_effect.action")
    return errors


def make_receipt(
    crossing: dict[str, Any],
    *,
    signer: IdentityKey,
    authority_id: str,
    kind: str,
    semantic_effect: str,
    note: str | None,
    lease_extension: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    created = normalize_timestamp(created_at) if created_at else timestamp_now()
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": "",
        "crossing_id": crossing.get("crossing_id"),
        "world_id": f"ghot-authority-world:{authority_id}",
        "receiver_particular": signer.particular(),
        "kind": kind,
        "semantic_effect": semantic_effect,
        "contract_ref": "ghot.portable-work-lease-authority@1",
        "pre_state_ref": None,
        "post_state_ref": None,
        "descendant_refs": [],
        "residual_refs": [],
        "note": note,
        "created_at": created,
        "extensions": identity_safe({
            "ghot_profile": "portable-work-lease/v1",
            "ghot_lease": lease_extension or {},
            "source_verification_profile": "relatte.identity-signature/v0",
            "public_key_identity_claimed": True,
        }),
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    return sign_receipt(receipt, signer)


def validate_receipt_shape(receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "receipt_id",
        "crossing_id",
        "world_id",
        "receiver_particular",
        "kind",
        "semantic_effect",
        "created_at",
        "signing",
    }
    missing = sorted(required - set(receipt))
    if missing:
        errors.append("missing: " + ", ".join(missing))
    if receipt.get("schema") != RECEIPT_SCHEMA:
        errors.append("wrong receipt schema")
    if receipt.get("kind") == "REFUSED" and receipt.get("semantic_effect") != "none":
        errors.append("REFUSED receipt must have semantic_effect none")
    return errors


__all__ = [
    "IdentityKey",
    "make_crossing",
    "make_receipt",
    "validate_crossing_shape",
    "validate_receipt_shape",
    "verify_crossing",
    "verify_receipt",
]
