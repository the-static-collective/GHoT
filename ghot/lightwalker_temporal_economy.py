#!/usr/bin/env python3
"""Lightwalker Economy 002 — time assays the ore.

Consumes Dogram CONTRIBUTION-FIELD-001 Workmarks and measurement receipts.
Dogram measures typed contribution history. A Realm-local lens may then
project an economic quantity from explicitly declared measurements.

The lens remains downstream and attributable:
    WORKMARK != MEASUREMENT != VALUATION
    LATER MEASUREMENT != BIRTH REWRITE
    NEW PROJECTION != RETROACTIVE REPRICING
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import LightwalkerEconomyError, content_address
from relatte_identity import (
    IdentityKey,
    identity_safe,
    sign_crossing,
    timestamp_now,
    verify_crossing,
)


DOGRAM_WORKMARK_SCHEMA = "dogram.workmark/v0-experimental"
DOGRAM_RECEIPT_SCHEMA = "dogram.contribution-field-receipt/v0-experimental"
DOGRAM_MEASUREMENT_VERSION = "CONTRIBUTION-FIELD-001/v0"

ASSAY_LENS_KIND = "ghot.lightwalker.assay-lens"
ASSAY_LENS_VERSION = "0"
ASSAY_PROJECTION_KIND = "ghot.lightwalker.assay-projection"
ASSAY_PROJECTION_VERSION = "0"
ASSAY_CAPABILITY = "ghot.lightwalker-assay-projection/v0"

_WORKMARK_KEYS = {
    "schema",
    "workmark_id",
    "contribution_root",
    "birth_cut",
    "birth_event_id",
    "birth_event_digest",
    "graph_address",
}
_RECEIPT_KEYS = {
    "schema",
    "authority",
    "workmark",
    "cut",
    "field_digest",
    "measurement_version",
    "measurements",
    "incomplete_events",
    "invalid_events",
    "source_event_ids",
    "receipt_digest",
}


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return value


def verify_dogram_workmark(workmark: dict[str, Any]) -> bool:
    if not isinstance(workmark, dict) or set(workmark) != _WORKMARK_KEYS:
        return False
    if workmark.get("schema") != DOGRAM_WORKMARK_SCHEMA:
        return False
    root = workmark.get("contribution_root")
    if not isinstance(root, str) or not root:
        return False
    if workmark.get("graph_address") != f"entity:{root}":
        return False
    body = {
        "schema": workmark["schema"],
        "contribution_root": workmark["contribution_root"],
        "birth_cut": workmark["birth_cut"],
        "birth_event_id": workmark["birth_event_id"],
        "birth_event_digest": workmark["birth_event_digest"],
        "graph_address": workmark["graph_address"],
    }
    return content_address(body) == workmark.get("workmark_id")


def verify_dogram_measurement(receipt: dict[str, Any]) -> bool:
    if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_KEYS:
        return False
    if receipt.get("schema") != DOGRAM_RECEIPT_SCHEMA:
        return False
    if receipt.get("authority") != "none":
        return False
    if receipt.get("measurement_version") != DOGRAM_MEASUREMENT_VERSION:
        return False
    workmark = receipt.get("workmark")
    if not isinstance(workmark, dict) or not verify_dogram_workmark(workmark):
        return False
    measurements = receipt.get("measurements")
    if not isinstance(measurements, dict):
        return False
    if _nonnegative_int(measurements.get("descendant_count"), "descendant_count") < 0:
        return False
    body = {
        "schema": receipt["schema"],
        "authority": receipt["authority"],
        "workmark": receipt["workmark"],
        "cut": receipt["cut"],
        "field_digest": receipt["field_digest"],
        "measurement_version": receipt["measurement_version"],
        "measurements": receipt["measurements"],
        "incomplete_events": receipt["incomplete_events"],
        "invalid_events": receipt["invalid_events"],
        "source_event_ids": receipt["source_event_ids"],
    }
    return content_address(body) == receipt.get("receipt_digest")


def normalize_assay_lens(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LightwalkerEconomyError("assay lens must be an object")
    if value.get("kind") != ASSAY_LENS_KIND or value.get("version") != ASSAY_LENS_VERSION:
        raise LightwalkerEconomyError("unsupported assay lens")

    realm_id = _nonempty(value.get("realm_id"), "realm_id")
    unit = _nonempty(value.get("unit"), "unit")
    policy = value.get("policy")
    if not isinstance(policy, dict) or policy.get("basis") != "base-plus-descendants":
        raise LightwalkerEconomyError("unsupported assay policy")
    base_amount = _nonnegative_int(policy.get("base_amount"), "base_amount")
    per_descendant = _nonnegative_int(
        policy.get("per_descendant"), "per_descendant"
    )
    assumptions = value.get("assumptions", [])
    if not isinstance(assumptions, list) or any(
        not isinstance(item, str) or not item for item in assumptions
    ):
        raise LightwalkerEconomyError("assumptions must be non-empty strings")

    body = {
        "kind": ASSAY_LENS_KIND,
        "version": ASSAY_LENS_VERSION,
        "authority": "realm-local",
        "realm_id": realm_id,
        "unit": unit,
        "policy": {
            "basis": "base-plus-descendants",
            "base_amount": base_amount,
            "per_descendant": per_descendant,
        },
        "assumptions": assumptions,
        "laws": [
            "MEASUREMENT != VALUATION",
            "LENS POLICY != DOGRAM AUTHORITY",
            "NEW MEASUREMENT MAY CREATE NEW PROJECTION",
            "NEW PROJECTION MAY NOT REWRITE OLD PROJECTION",
        ],
    }
    return {**body, "lens_id": content_address(body)}


def project_measurement(
    workmark: dict[str, Any],
    measurement_receipt: dict[str, Any],
    lens: dict[str, Any],
) -> dict[str, Any]:
    if not verify_dogram_workmark(workmark):
        raise LightwalkerEconomyError("invalid Dogram Workmark")
    if not verify_dogram_measurement(measurement_receipt):
        raise LightwalkerEconomyError("invalid Dogram measurement receipt")
    if measurement_receipt["workmark"]["workmark_id"] != workmark["workmark_id"]:
        raise LightwalkerEconomyError("measurement addresses a different Workmark")

    normalized = normalize_assay_lens(lens)
    measurements = measurement_receipt["measurements"]
    descendant_count = _nonnegative_int(
        measurements.get("descendant_count"), "descendant_count"
    )
    policy = normalized["policy"]
    quantity = (
        int(policy["base_amount"])
        + descendant_count * int(policy["per_descendant"])
    )

    body = {
        "kind": ASSAY_PROJECTION_KIND,
        "version": ASSAY_PROJECTION_VERSION,
        "authority": "realm-local",
        "realm_id": normalized["realm_id"],
        "workmark_id": workmark["workmark_id"],
        "lens_id": normalized["lens_id"],
        "measurement_receipt_digest": measurement_receipt["receipt_digest"],
        "cut": measurement_receipt["cut"],
        "status": "ELIGIBLE",
        "unit": normalized["unit"],
        "quantity": quantity,
        "source_metrics": {
            "descendant_count": descendant_count,
            "reachable_descendant_set": list(
                measurements.get("reachable_descendant_set", [])
            ),
            "relation_kind_counts": dict(
                measurements.get("relation_kind_counts", {})
            ),
        },
        "laws": [
            "PROJECTION != WORKMARK",
            "PROJECTION != MEASUREMENT",
            "PROJECTION DOES NOT MUTATE PRIOR PROJECTION",
            "REALM-LOCAL VALUE != UNIVERSAL VALUE",
            "ECONOMIC QUANTITY != HUMAN WORTH",
        ],
    }
    return {**body, "projection_id": content_address(body)}


def make_assay_projection_crossing(
    projection: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not isinstance(projection, dict):
        raise LightwalkerEconomyError("projection must be an object")
    body = {key: value for key, value in projection.items() if key != "projection_id"}
    if content_address(body) != projection.get("projection_id"):
        raise LightwalkerEconomyError("assay projection address mismatch")

    crossing = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": "LIGHTWALKER_ASSAY_PROJECTION",
        "payload_refs": [
            projection["workmark_id"],
            projection["lens_id"],
            projection["measurement_receipt_digest"],
            projection["projection_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-assay-projection",
                "realm_id": projection["realm_id"],
                "projection_id": projection["projection_id"],
                "measurement_cut": projection["cut"],
                "mint_authority_requested": False,
                "retroactive_repricing_requested": False,
            }
        ),
        "capability_ref": ASSAY_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {"capability": ASSAY_CAPABILITY},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-assay-projection/v0",
            "projection_is_not_payment": True,
            "projection_is_not_workmark": True,
            "measurement_is_not_valuation": True,
        },
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    signed = sign_crossing(crossing, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("assay projection crossing failed verification")
    return signed


__all__ = [
    "ASSAY_LENS_KIND",
    "ASSAY_LENS_VERSION",
    "ASSAY_PROJECTION_KIND",
    "ASSAY_PROJECTION_VERSION",
    "make_assay_projection_crossing",
    "normalize_assay_lens",
    "project_measurement",
    "verify_dogram_measurement",
    "verify_dogram_workmark",
]
