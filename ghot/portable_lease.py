#!/usr/bin/env python3
"""Portable GHoT lease crossings using reLATTE V0 envelope/receipt shapes.

V0 security profile:
- canonical JSON
- HMAC-SHA256 over crossing / receipt structure
- shared secret provisioned out-of-band
- crossing replay protection is enforced by LeaseAuthority

The resulting objects are structurally compatible with:
- relatte.crossing-envelope/v0
- relatte.receipt/v0

This HMAC profile is intentionally NOT presented as reLATTE's stronger
public-key identity/source-verification profile.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any


CROSSING_SCHEMA = "relatte.crossing-envelope/v0"
RECEIPT_SCHEMA = "relatte.receipt/v0"
SIGNING_DOMAIN = "ghot.portable-lease-hmac/v0"
CAPABILITY_REF = "ghot.work-lease/v0"

ACTIONS = {"POLL", "CLAIM", "RENEW", "COMPLETE", "ABANDON"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_address(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def secret_bytes(raw: str | bytes) -> bytes:
    return raw if isinstance(raw, bytes) else raw.encode("utf-8")


def key_id(secret: str | bytes) -> str:
    digest = hashlib.sha256(secret_bytes(secret)).hexdigest()
    return f"ghot-shared-secret:{digest[:16]}"


def _signable(value: dict[str, Any]) -> dict[str, Any]:
    clone = copy.deepcopy(value)
    signing = clone.setdefault("signing", {})
    signing["signature"] = ""
    return clone


def signature(secret: str | bytes, value: dict[str, Any]) -> str:
    return hmac.new(
        secret_bytes(secret),
        canonical_bytes(_signable(value)),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(secret: str | bytes, value: dict[str, Any]) -> bool:
    supplied = str((value.get("signing") or {}).get("signature") or "")
    expected = signature(secret, value)
    return bool(supplied) and hmac.compare_digest(supplied, expected)


def _crossing_id(seed: dict[str, Any]) -> str:
    return "relatte-crossing-v0:" + hashlib.sha256(canonical_bytes(seed)).hexdigest()


def make_crossing(
    action: str,
    *,
    secret: str | bytes,
    authority_id: str,
    worker_id: str,
    worker_node_id: str,
    hold_id: str | None = None,
    dispatch_id: str | None = None,
    lease_id: str | None = None,
    lease_seconds: float | None = None,
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

    created = created_at or now()
    effect = {
        "action": action,
        "authority_id": authority_id,
        "worker_id": worker_id,
        "worker_node_id": worker_node_id,
        "hold_id": hold_id,
        "dispatch_id": dispatch_id,
        "lease_id": lease_id,
        "lease_seconds": lease_seconds,
        "child_energy_plan_id": child_energy_plan_id,
        "receipt_id": receipt_id,
        "outcome": outcome,
        "error": error,
        "nonce": nonce or f"nonce-{uuid.uuid4()}",
    }

    seed = {
        "source_particular": f"ghot-worker:{worker_id}",
        "source_world": f"ghot-node:{worker_node_id}",
        "declared_kind": f"GHOT_LEASE_{action}",
        "requested_effect": effect,
        "created_at": created,
    }
    crossing_id = _crossing_id(seed)

    envelope = {
        "schema": CROSSING_SCHEMA,
        "crossing_id": crossing_id,
        "protocol_version": "0",
        "source_particular": seed["source_particular"],
        "source_world": seed["source_world"],
        "source_history_head": None,
        "parents": [],
        "declared_kind": seed["declared_kind"],
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
            "ghot_profile": "portable-work-lease/v0",
            "source_verification_profile": "shared-secret-hmac-v0",
            "public_key_identity_claimed": False,
        },
        "signing": {
            "algorithm": "HMAC-SHA256",
            "public_key": {
                "key_id": key_id(secret),
                "profile": "symmetric-shared-secret-v0",
                "public_key_identity": False,
            },
            "signature": "",
            "domain": SIGNING_DOMAIN,
        },
    }
    envelope["signing"]["signature"] = signature(secret, envelope)
    return envelope


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
    signing = envelope.get("signing")
    if not isinstance(signing, dict):
        errors.append("signing must be an object")
    else:
        for name in ("algorithm", "public_key", "signature", "domain"):
            if name not in signing:
                errors.append(f"signing missing {name}")
    return errors


def _receipt_id(seed: dict[str, Any]) -> str:
    return "relatte-receipt-v0:" + hashlib.sha256(canonical_bytes(seed)).hexdigest()


def make_receipt(
    crossing: dict[str, Any],
    *,
    secret: str | bytes,
    authority_id: str,
    kind: str,
    semantic_effect: str,
    note: str | None,
    lease_extension: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    created = created_at or now()
    seed = {
        "crossing_id": crossing.get("crossing_id"),
        "world_id": f"ghot-authority-world:{authority_id}",
        "receiver_particular": f"ghot-authority:{authority_id}",
        "kind": kind,
        "semantic_effect": semantic_effect,
        "note": note,
        "created_at": created,
        "lease_extension": lease_extension or {},
    }
    receipt_id = _receipt_id(seed)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": receipt_id,
        "crossing_id": crossing.get("crossing_id"),
        "world_id": seed["world_id"],
        "receiver_particular": seed["receiver_particular"],
        "kind": kind,
        "semantic_effect": semantic_effect,
        "contract_ref": "ghot.portable-work-lease-authority@0",
        "pre_state_ref": None,
        "post_state_ref": None,
        "descendant_refs": [],
        "residual_refs": [],
        "note": note,
        "created_at": created,
        "extensions": {
            "ghot_profile": "portable-work-lease/v0",
            "ghot_lease": lease_extension or {},
            "source_verification_profile": "shared-secret-hmac-v0",
            "public_key_identity_claimed": False,
        },
        "signing": {
            "algorithm": "HMAC-SHA256",
            "public_key": {
                "key_id": key_id(secret),
                "profile": "symmetric-shared-secret-v0",
                "public_key_identity": False,
            },
            "signature": "",
            "domain": SIGNING_DOMAIN,
        },
    }
    receipt["signing"]["signature"] = signature(secret, receipt)
    return receipt


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


def verify_receipt(secret: str | bytes, receipt: dict[str, Any]) -> bool:
    return not validate_receipt_shape(receipt) and verify_signature(secret, receipt)


def env_secret(required: bool = True) -> str | None:
    value = os.environ.get("GHOT_LEASE_SHARED_SECRET")
    if value:
        return value
    if required:
        raise RuntimeError(
            "GHOT_LEASE_SHARED_SECRET is required for portable lease crossings"
        )
    return None
