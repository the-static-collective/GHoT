#!/usr/bin/env python3
"""Lightwalker Guild Treasury 001.

A Guild Treasury is a signed sovereign inventory of heterogeneous positions.
It is not a single scalar balance and does not derive a universal net worth.

Core laws:
    TREASURY != BALANCE
    INVENTORY != OWNERSHIP
    REFERENCE != CUSTODY
    NATIVE UNIT != UNIVERSAL UNIT
    RESOURCE VIEW != PRICE
    SNAPSHOT != SETTLEMENT
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


ENTRY_KIND = "ghot.lightwalker.guild-treasury-entry"
ENTRY_VERSION = "0"
SNAPSHOT_KIND = "ghot.lightwalker.guild-treasury-snapshot"
SNAPSHOT_VERSION = "0"
VIEW_KIND = "ghot.lightwalker.guild-resource-view"
VIEW_VERSION = "0"

SNAPSHOT_SIGNING_DOMAIN = "ghot.lightwalker-guild-treasury-snapshot-signature/v0"
SNAPSHOT_BYTES_DOMAIN = b"GHOT-LightwalkerGuildTreasurySnapshot-v0|"
SNAPSHOT_CAPABILITY = "ghot.lightwalker-guild-treasury-snapshot/v0"

CATEGORIES = {
    "capability",
    "claim",
    "obligation",
    "right",
    "receipt",
    "credit",
    "money-reference",
}
POSITIONS = {
    "available",
    "encumbered",
    "outstanding",
    "resolved",
    "evidence",
    "external-reference",
}
FORBIDDEN_COLLAPSE_FIELDS = {
    "universal_value",
    "universal_price",
    "net_worth",
    "exchange_rate",
    "conversion_rate",
    "common_unit",
}


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return value


def _assert_no_collapse_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_COLLAPSE_FIELDS:
                raise LightwalkerEconomyError(
                    f"forbidden universal-collapse field at {path}.{key}"
                )
            _assert_no_collapse_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_collapse_fields(item, f"{path}[{index}]")


def make_treasury_entry(
    *,
    category: str,
    position: str,
    subject_ref: str,
    source_ref: str,
    evidence_refs: list[str],
    native_measure: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if category not in CATEGORIES:
        raise LightwalkerEconomyError("unsupported treasury category")
    if position not in POSITIONS:
        raise LightwalkerEconomyError("unsupported treasury position")
    if not isinstance(evidence_refs, list) or any(
        not isinstance(item, str) or not item for item in evidence_refs
    ):
        raise LightwalkerEconomyError("evidence_refs must contain non-empty strings")

    normalized_measure = None
    if native_measure is not None:
        if not isinstance(native_measure, dict):
            raise LightwalkerEconomyError("native_measure must be an object")
        normalized_measure = {
            "unit": _nonempty(native_measure.get("unit"), "native_measure.unit"),
            "quantity": _nonnegative_int(
                native_measure.get("quantity"),
                "native_measure.quantity",
            ),
        }

    normalized_metadata = identity_safe(metadata or {})
    _assert_no_collapse_fields(normalized_metadata)

    body = {
        "kind": ENTRY_KIND,
        "version": ENTRY_VERSION,
        "category": category,
        "position": position,
        "subject_ref": _nonempty(subject_ref, "subject_ref"),
        "source_ref": _nonempty(source_ref, "source_ref"),
        "evidence_refs": list(evidence_refs),
        "native_measure": normalized_measure,
        "metadata": normalized_metadata,
        "laws": [
            "INVENTORY != OWNERSHIP",
            "REFERENCE != CUSTODY",
            "NATIVE UNIT != UNIVERSAL UNIT",
        ],
    }
    return {**body, "entry_id": content_address(body)}


def verify_treasury_entry(entry: dict[str, Any]) -> bool:
    try:
        if not isinstance(entry, dict):
            return False
        if entry.get("kind") != ENTRY_KIND or entry.get("version") != ENTRY_VERSION:
            return False
        if entry.get("category") not in CATEGORIES:
            return False
        if entry.get("position") not in POSITIONS:
            return False
        _assert_no_collapse_fields(entry)
        measure = entry.get("native_measure")
        if measure is not None:
            if not isinstance(measure, dict):
                return False
            _nonempty(measure.get("unit"), "native_measure.unit")
            _nonnegative_int(measure.get("quantity"), "native_measure.quantity")
        body = {key: value for key, value in entry.items() if key != "entry_id"}
        return content_address(body) == entry.get("entry_id")
    except Exception:
        return False


def _snapshot_body(snapshot: dict[str, Any]) -> dict[str, Any]:
    signing = snapshot.get("signing") or {}
    return {
        "kind": snapshot.get("kind"),
        "version": snapshot.get("version"),
        "authority": snapshot.get("authority"),
        "guild_id": snapshot.get("guild_id"),
        "steward_particular": snapshot.get("steward_particular"),
        "prior_snapshot_id": snapshot.get("prior_snapshot_id"),
        "sequence": snapshot.get("sequence"),
        "entries": snapshot.get("entries"),
        "laws": snapshot.get("laws"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    }


def _snapshot_id(snapshot: dict[str, Any]) -> str:
    return content_address(_snapshot_body(snapshot))


def _snapshot_signature_bytes(snapshot: dict[str, Any]) -> bytes:
    return SNAPSHOT_BYTES_DOMAIN + canonical_bytes(
        {
            "snapshot_id": _snapshot_id(snapshot),
            **_snapshot_body(snapshot),
        }
    )


def make_treasury_snapshot(
    *,
    guild_id: str,
    steward: IdentityKey,
    entries: list[dict[str, Any]],
    prior_snapshot_id: str | None = None,
    sequence: int = 0,
) -> dict[str, Any]:
    if not isinstance(entries, list):
        raise LightwalkerEconomyError("entries must be a list")
    for entry in entries:
        if not verify_treasury_entry(entry):
            raise LightwalkerEconomyError("invalid treasury entry")
    ids = [entry["entry_id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise LightwalkerEconomyError("duplicate treasury entry")

    ordered = sorted(entries, key=lambda item: item["entry_id"])
    snapshot = {
        "kind": SNAPSHOT_KIND,
        "version": SNAPSHOT_VERSION,
        "authority": "guild-local-inventory",
        "guild_id": _nonempty(guild_id, "guild_id"),
        "steward_particular": steward.particular(),
        "prior_snapshot_id": prior_snapshot_id,
        "sequence": _nonnegative_int(sequence, "sequence"),
        "entries": ordered,
        "laws": [
            "TREASURY != BALANCE",
            "SNAPSHOT != OWNERSHIP JUDGMENT",
            "SNAPSHOT != UNIVERSAL VALUATION",
            "SNAPSHOT != SETTLEMENT",
        ],
        "snapshot_id": "",
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": steward.public_jwk(),
            "signature": "",
            "domain": SNAPSHOT_SIGNING_DOMAIN,
        },
    }
    snapshot["snapshot_id"] = _snapshot_id(snapshot)
    snapshot["signing"]["signature"] = steward.sign(
        _snapshot_signature_bytes(snapshot)
    )
    return snapshot


def verify_treasury_snapshot(snapshot: dict[str, Any]) -> bool:
    try:
        if not isinstance(snapshot, dict):
            return False
        if snapshot.get("kind") != SNAPSHOT_KIND:
            return False
        if snapshot.get("version") != SNAPSHOT_VERSION:
            return False
        if snapshot.get("authority") != "guild-local-inventory":
            return False
        entries = snapshot.get("entries")
        if not isinstance(entries, list) or any(
            not verify_treasury_entry(item) for item in entries
        ):
            return False
        ids = [item["entry_id"] for item in entries]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            return False
        if snapshot.get("snapshot_id") != _snapshot_id(snapshot):
            return False
        signing = snapshot.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != SNAPSHOT_SIGNING_DOMAIN:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != snapshot.get("steward_particular"):
            return False
        return verify_p256(
            public_key,
            _snapshot_signature_bytes(snapshot),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def next_treasury_snapshot(
    current: dict[str, Any],
    *,
    steward: IdentityKey,
    add_entries: list[dict[str, Any]] | None = None,
    retire_entry_ids: list[str] | None = None,
) -> dict[str, Any]:
    if not verify_treasury_snapshot(current):
        raise LightwalkerEconomyError("invalid current treasury snapshot")
    if steward.particular() != current["steward_particular"]:
        raise LightwalkerEconomyError("steward does not own treasury transition")

    additions = add_entries or []
    retire = set(retire_entry_ids or [])
    known = {item["entry_id"] for item in current["entries"]}
    if not retire.issubset(known):
        raise LightwalkerEconomyError("cannot retire unknown treasury entry")
    for entry in additions:
        if not verify_treasury_entry(entry):
            raise LightwalkerEconomyError("invalid added treasury entry")

    remaining = [item for item in current["entries"] if item["entry_id"] not in retire]
    return make_treasury_snapshot(
        guild_id=current["guild_id"],
        steward=steward,
        entries=remaining + additions,
        prior_snapshot_id=current["snapshot_id"],
        sequence=int(current["sequence"]) + 1,
    )


def make_resource_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")

    counts: dict[str, int] = {}
    native_buckets: dict[str, dict[str, Any]] = {}
    unresolved: list[str] = []
    evidence_only: list[str] = []

    for entry in snapshot["entries"]:
        key = f'{entry["category"]}:{entry["position"]}'
        counts[key] = counts.get(key, 0) + 1

        measure = entry.get("native_measure")
        if measure is not None:
            bucket_key = "|".join(
                [
                    entry["category"],
                    entry["position"],
                    measure["unit"],
                ]
            )
            bucket = native_buckets.setdefault(
                bucket_key,
                {
                    "category": entry["category"],
                    "position": entry["position"],
                    "unit": measure["unit"],
                    "quantity": 0,
                    "entry_ids": [],
                },
            )
            bucket["quantity"] += int(measure["quantity"])
            bucket["entry_ids"].append(entry["entry_id"])

        if entry["position"] in {"outstanding", "encumbered"}:
            unresolved.append(entry["entry_id"])
        if entry["position"] == "evidence":
            evidence_only.append(entry["entry_id"])

    body = {
        "kind": VIEW_KIND,
        "version": VIEW_VERSION,
        "authority": "derived-from-signed-snapshot",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "counts_by_category_position": dict(sorted(counts.items())),
        "native_buckets": [
            native_buckets[key]
            for key in sorted(native_buckets)
        ],
        "unresolved_entry_ids": sorted(unresolved),
        "evidence_entry_ids": sorted(evidence_only),
        "universal_total": None,
        "collapse_status": "REFUSED_BY_PROTOCOL",
        "laws": [
            "RESOURCE VIEW != PRICE",
            "NATIVE BUCKETS MAY NOT BE CROSS-SUMMED BY PROTOCOL",
            "UNIVERSAL TOTAL IS UNDEFINED",
        ],
    }
    return {**body, "view_id": content_address(body)}


def collapse_to_universal_total(snapshot: dict[str, Any]) -> int:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    raise LightwalkerEconomyError(
        "Guild Treasury does not define a universal total or exchange rate"
    )


def make_snapshot_crossing(
    snapshot: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    if signer.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError("snapshot crossing signer must be steward")

    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": snapshot["prior_snapshot_id"],
        "parents": (
            [snapshot["prior_snapshot_id"]]
            if snapshot["prior_snapshot_id"] is not None
            else []
        ),
        "declared_kind": "LIGHTWALKER_GUILD_TREASURY_SNAPSHOT",
        "payload_refs": [
            snapshot["snapshot_id"],
            *[item["entry_id"] for item in snapshot["entries"]],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-guild-treasury-snapshot",
                "guild_id": snapshot["guild_id"],
                "snapshot_id": snapshot["snapshot_id"],
                "automatic_balance_mutation_requested": False,
                "automatic_ownership_inference_requested": False,
                "universal_valuation_requested": False,
            }
        ),
        "capability_ref": SNAPSHOT_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {
            "guild_id": snapshot["guild_id"],
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-guild-treasury/v0",
            "treasury_is_not_balance": True,
            "inventory_is_not_ownership": True,
            "native_units_are_not_converted": True,
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
        raise LightwalkerEconomyError("treasury snapshot crossing failed verification")
    return signed


__all__ = [
    "collapse_to_universal_total",
    "make_resource_view",
    "make_snapshot_crossing",
    "make_treasury_entry",
    "make_treasury_snapshot",
    "next_treasury_snapshot",
    "verify_treasury_entry",
    "verify_treasury_snapshot",
]
