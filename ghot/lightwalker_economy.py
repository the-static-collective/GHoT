#!/usr/bin/env python3
"""Lightwalker Economy 001.

This module is deliberately not a cryptocurrency mint.

It turns a bounded, independently verified GHoT Ice Cube result into an
immutable Workmark, then permits sovereign Realms to publish separate,
content-addressed economic projections over that Workmark.

Core laws:
    ACT != WORKMARK
    WORKMARK != MONEY
    DOGRAM VERIFICATION != ECONOMIC VALUATION
    SAME WORKMARK MAY HAVE MANY REALM-LOCAL PROJECTIONS
    PROJECTION MAY NOT REWRITE WORKMARK
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from relatte_identity import (
    IdentityKey,
    identity_safe,
    sign_crossing,
    timestamp_now,
    verify_crossing,
)


WORKMARK_KIND = "ghot.lightwalker.workmark"
WORKMARK_VERSION = "0"
LENS_KIND = "ghot.lightwalker.economic-lens"
LENS_VERSION = "0"
PROJECTION_KIND = "ghot.lightwalker.economic-projection"
PROJECTION_VERSION = "0"
PROJECTION_CAPABILITY = "ghot.lightwalker-economic-projection/v0"


class LightwalkerEconomyError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_address(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _safe_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return value


def mint_workmark_from_ice_cube(result: dict[str, Any]) -> dict[str, Any]:
    """Create a non-monetary Workmark from a verified Ice Cube result."""
    if not isinstance(result, dict):
        raise LightwalkerEconomyError("result must be an object")
    if result.get("kind") != "ghot.ice-cube-result" or result.get("version") != "0":
        raise LightwalkerEconomyError("unsupported Ice Cube result")
    if result.get("dogram_status") != "OK":
        raise LightwalkerEconomyError("Dogram verification must be OK before Workmark birth")

    specimen = result.get("specimen")
    dogram_receipt = result.get("dogram_receipt")
    if not isinstance(specimen, dict) or not isinstance(dogram_receipt, dict):
        raise LightwalkerEconomyError("verified specimen and Dogram receipt are required")

    specimen_address = _nonempty(result.get("specimen_address"), "specimen_address")
    dogram_receipt_address = _nonempty(
        result.get("dogram_receipt_address"), "dogram_receipt_address"
    )
    if content_address(specimen) != specimen_address:
        raise LightwalkerEconomyError("specimen address mismatch")
    if content_address(dogram_receipt) != dogram_receipt_address:
        raise LightwalkerEconomyError("Dogram receipt address mismatch")

    render = specimen.get("render")
    work = specimen.get("work")
    if not isinstance(render, dict) or not isinstance(work, dict):
        raise LightwalkerEconomyError("Ice Cube specimen is missing render/work facts")

    width = _safe_nonnegative_int(work.get("render", {}).get("width"), "render.width")
    height = _safe_nonnegative_int(work.get("render", {}).get("height"), "render.height")

    body = {
        "kind": WORKMARK_KIND,
        "version": WORKMARK_VERSION,
        "authority": "none",
        "contribution_root": specimen_address,
        "birth": {
            "act_kind": "VERIFIED_ARTIFACT",
            "work_address": _nonempty(result.get("work_address"), "work_address"),
            "specimen_address": specimen_address,
            "render_address": _nonempty(result.get("render_address"), "render_address"),
            "dogram_receipt_address": dogram_receipt_address,
            "execution_receipt_id": _nonempty(
                result.get("execution_receipt_id"), "execution_receipt_id"
            ),
            "work_crossing_id": _nonempty(
                result.get("work_crossing_id"), "work_crossing_id"
            ),
        },
        "declared_facts": {
            "family": _nonempty(result.get("family"), "family"),
            "dogram_status": "OK",
            "render_width": width,
            "render_height": height,
            "render_pixel_count": width * height,
        },
        "laws": [
            "WORKMARK != MONEY",
            "WORKMARK != SCORE",
            "WORKMARK != OWNERSHIP",
            "VERIFICATION != VALUATION",
        ],
    }
    return {**body, "workmark_id": content_address(body)}


def verify_workmark(workmark: dict[str, Any]) -> bool:
    if not isinstance(workmark, dict):
        return False
    if workmark.get("kind") != WORKMARK_KIND or workmark.get("version") != WORKMARK_VERSION:
        return False
    if workmark.get("authority") != "none":
        return False
    workmark_id = workmark.get("workmark_id")
    if not isinstance(workmark_id, str):
        return False
    body = {key: value for key, value in workmark.items() if key != "workmark_id"}
    return content_address(body) == workmark_id


def normalize_lens(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LightwalkerEconomyError("lens must be an object")
    if value.get("kind") != LENS_KIND or value.get("version") != LENS_VERSION:
        raise LightwalkerEconomyError("unsupported lens")

    realm_id = _nonempty(value.get("realm_id"), "realm_id")
    policy = value.get("policy")
    if not isinstance(policy, dict):
        raise LightwalkerEconomyError("lens.policy must be an object")

    basis = policy.get("basis")
    if basis == "fixed-per-verified-workmark":
        unit = _nonempty(value.get("unit"), "unit")
        amount = _safe_nonnegative_int(policy.get("amount"), "policy.amount")
        normalized_policy = {
            "basis": basis,
            "amount": amount,
        }
        normalized_unit: str | None = unit
    elif basis == "no-economic-interpretation":
        if value.get("unit") not in (None, ""):
            raise LightwalkerEconomyError(
                "no-economic-interpretation lens must not declare a unit"
            )
        normalized_policy = {"basis": basis}
        normalized_unit = None
    else:
        raise LightwalkerEconomyError("unsupported economic lens basis")

    assumptions = value.get("assumptions", [])
    if not isinstance(assumptions, list) or any(
        not isinstance(item, str) or not item for item in assumptions
    ):
        raise LightwalkerEconomyError("assumptions must be a list of non-empty strings")

    body = {
        "kind": LENS_KIND,
        "version": LENS_VERSION,
        "realm_id": realm_id,
        "unit": normalized_unit,
        "policy": normalized_policy,
        "assumptions": assumptions,
        "authority": "realm-local",
        "laws": [
            "VALUATION POLICY != HISTORY",
            "SAME HISTORY != SAME VALUATION",
            "PROJECTION != HUMAN WORTH",
        ],
    }
    return {**body, "lens_id": content_address(body)}


def project_workmark(
    workmark: dict[str, Any],
    lens: dict[str, Any],
) -> dict[str, Any]:
    """Apply a Realm-local economic lens without mutating the Workmark."""
    if not verify_workmark(workmark):
        raise LightwalkerEconomyError("invalid Workmark")
    normalized_lens = normalize_lens(lens)

    basis = normalized_lens["policy"]["basis"]
    if basis == "fixed-per-verified-workmark":
        quantity: int | None = int(normalized_lens["policy"]["amount"])
        unit: str | None = str(normalized_lens["unit"])
        status = "ELIGIBLE"
    else:
        quantity = None
        unit = None
        status = "NO_ECONOMIC_INTERPRETATION"

    body = {
        "kind": PROJECTION_KIND,
        "version": PROJECTION_VERSION,
        "authority": "realm-local",
        "realm_id": normalized_lens["realm_id"],
        "workmark_id": workmark["workmark_id"],
        "lens_id": normalized_lens["lens_id"],
        "status": status,
        "unit": unit,
        "quantity": quantity,
        "source_facts": {
            "contribution_root": workmark["contribution_root"],
            "dogram_status": workmark["declared_facts"]["dogram_status"],
        },
        "laws": [
            "PROJECTION != WORKMARK",
            "PROJECTION != DOGRAM RECEIPT",
            "PROJECTION MAY NOT REWRITE WORKMARK",
            "REALM-LOCAL VALUE != UNIVERSAL VALUE",
        ],
    }
    return {**body, "projection_id": content_address(body)}


def make_projection_crossing(
    projection: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not isinstance(projection, dict):
        raise LightwalkerEconomyError("projection must be an object")
    expected = projection.get("projection_id")
    body = {key: value for key, value in projection.items() if key != "projection_id"}
    if expected != content_address(body):
        raise LightwalkerEconomyError("projection address mismatch")

    crossing = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": "LIGHTWALKER_ECONOMIC_PROJECTION",
        "payload_refs": [
            projection["workmark_id"],
            projection["lens_id"],
            projection["projection_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-economic-projection",
                "realm_id": projection["realm_id"],
                "projection_id": projection["projection_id"],
                "mint_authority_requested": False,
            }
        ),
        "capability_ref": PROJECTION_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {
            "capability": PROJECTION_CAPABILITY,
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-economic-projection/v0",
            "projection_is_not_payment": True,
            "projection_is_not_workmark": True,
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
        raise LightwalkerEconomyError("new projection crossing failed verification")
    return signed


__all__ = [
    "LENS_KIND",
    "LENS_VERSION",
    "LightwalkerEconomyError",
    "PROJECTION_KIND",
    "PROJECTION_VERSION",
    "WORKMARK_KIND",
    "WORKMARK_VERSION",
    "content_address",
    "make_projection_crossing",
    "mint_workmark_from_ice_cube",
    "normalize_lens",
    "project_workmark",
    "verify_workmark",
]
