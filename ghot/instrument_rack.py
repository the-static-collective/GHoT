#!/usr/bin/env python3
"""INSTRUMENT-RACK-001: proposal-only capability cards and portable seed packets.

External adapter manifests become deterministic instrument cards. Cards do not
execute. An explicit dispatch creates a signed crossing, revalidates the exact
card, runs one bounded adapter attempt through the existing GHoT execution
surface, and—on success—returns a content-addressed portable seed packet.
Packet admission is a separate local action and never executes the donor.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from external_adapters import external_executor_records
from reference_node import execute, node_id, now
from relatte_identity import (
    IdentityKey,
    identity_safe,
    sign_crossing,
    sign_receipt,
    timestamp_now,
    verify_crossing,
    verify_receipt,
)


RACK_SCHEMA = "ghot.instrument-rack/v0"
CARD_SCHEMA = "ghot.instrument-card/v0"
DISPATCH_STATE_SCHEMA = "ghot.instrument-dispatch-state/v0"
DISPATCH_RESULT_SCHEMA = "ghot.instrument-dispatch-result/v0"
PACKET_SCHEMA = "ghot.portable-seed-packet/v0"
MATERIAL_SCHEMA = "ghot.seed-material/v0"
CROSSING_SCHEMA = "relatte.crossing-envelope/v0"
RECEIPT_SCHEMA = "relatte.receipt/v0"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _home() -> Path:
    return Path(os.environ.get("GHOT_HOME", ".ghot")).expanduser().resolve()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(_canonical(value), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid stored JSON object: {path}")
    return value


def _card_identity_view(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": CARD_SCHEMA,
        "adapter_id": card.get("adapter_id"),
        "capability": card.get("capability"),
        "manifest_sha256": card.get("manifest_sha256"),
        "protocol": card.get("protocol"),
        "available": card.get("available"),
        "limits": copy.deepcopy(card.get("limits") or {}),
        "status": "PROPOSAL_ONLY",
        "semantic_effect": "none",
    }


def _card_id(card: dict[str, Any]) -> str:
    return "instrument-card-v0:" + _digest(_card_identity_view(card))


def _manifest_digest(path: str) -> str:
    manifest = Path(path).expanduser().resolve()
    if not manifest.is_file():
        raise FileNotFoundError(f"external adapter manifest not found: {manifest}")
    return _sha_bytes(manifest.read_bytes())


def build_instrument_rack() -> dict[str, Any]:
    """Build a deterministic proposal-only rack from opted-in manifests."""
    cards: list[dict[str, Any]] = []
    for executor in external_executor_records():
        external = executor.get("external_adapter")
        if not isinstance(external, dict):
            continue
        adapter_id = str(external.get("adapter_id") or "")
        manifest_path = str(external.get("manifest_path") or "")
        manifest_sha256 = _manifest_digest(manifest_path)
        capability_limits = executor.get("capability_limits") or {}
        for spec in external.get("capability_specs") or []:
            if not isinstance(spec, dict):
                continue
            capability = str(spec.get("capability") or "")
            limits = (
                capability_limits.get(capability, {})
                if isinstance(capability_limits, dict)
                else {}
            )
            card = {
                "schema": CARD_SCHEMA,
                "card_id": "",
                "adapter_id": adapter_id,
                "capability": capability,
                "manifest_path": manifest_path,
                "manifest_sha256": manifest_sha256,
                "protocol": spec.get("protocol"),
                "available": spec.get("available") is True,
                "limits": copy.deepcopy(limits),
                "status": "PROPOSAL_ONLY",
                "semantic_effect": "none",
                "laws": [
                    "RACK != EXECUTION",
                    "CARD != ASSIGNMENT",
                    "CAPABILITY != AUTHORITY",
                ],
            }
            card["card_id"] = _card_id(card)
            cards.append(card)

    cards.sort(key=lambda item: (item["adapter_id"], item["capability"]))
    rack_identity = [_card_identity_view(card) for card in cards]
    return {
        "schema": RACK_SCHEMA,
        "rack_id": "instrument-rack-v0:" + _digest(rack_identity),
        "cards": cards,
        "status": "PROPOSAL_ONLY",
        "semantic_effect": "none",
        "laws": [
            "RACK != EXECUTION",
            "DISCOVERY != SELECTION",
            "CAPABILITY != AUTHORITY",
        ],
    }


def _fresh_card(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict) or candidate.get("schema") != CARD_SCHEMA:
        raise ValueError("INVALID_INSTRUMENT_CARD")
    claimed_id = str(candidate.get("card_id") or "")
    if claimed_id != _card_id(candidate):
        raise ValueError("STALE_OR_TAMPERED_INSTRUMENT_CARD")
    fresh = next(
        (
            item
            for item in build_instrument_rack()["cards"]
            if item["card_id"] == claimed_id
        ),
        None,
    )
    if fresh is None:
        raise ValueError("STALE_OR_TAMPERED_INSTRUMENT_CARD")
    if _canonical(candidate) != _canonical(fresh):
        raise ValueError("STALE_OR_TAMPERED_INSTRUMENT_CARD")
    if fresh.get("available") is not True:
        raise ValueError("INSTRUMENT_CAPABILITY_UNAVAILABLE")
    return fresh


def _signer() -> IdentityKey:
    return IdentityKey.load_or_create(
        _home() / "identity" / "instrument-dispatch-p256.pem"
    )


def _dispatch_id(card: dict[str, Any], payload: Any, source: str) -> str:
    return "instrument-dispatch-v0:" + _digest({
        "card_id": card["card_id"],
        "payload_sha256": _digest(payload),
        "dispatch_source": source,
    })


def _dispatch_path(dispatch_id: str) -> Path:
    digest = dispatch_id.rsplit(":", 1)[-1]
    return _home() / "instrument-rack" / "dispatches" / f"{digest}.json"


def _make_crossing(
    card: dict[str, Any],
    payload: Any,
    dispatch_id: str,
    dispatch_source: str,
    signer: IdentityKey,
) -> dict[str, Any]:
    payload_sha256 = _digest(payload)
    envelope = {
        "schema": CROSSING_SCHEMA,
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": "world:ghot:instrument-rack",
        "source_history_head": "sha256:" + _digest(card),
        "parents": [],
        "declared_kind": "GHOT_INSTRUMENT_DISPATCH",
        "payload_refs": [{
            "address": "sha256:" + payload_sha256,
            "role": "instrument-input",
            "media_type": "application/json",
        }],
        "requested_effect": identity_safe({
            "action": "EXECUTE_SELECTED_INSTRUMENT",
            "dispatch_id": dispatch_id,
            "card_id": card["card_id"],
            "adapter_id": card["adapter_id"],
            "capability": card["capability"],
        }),
        "capability_ref": card["capability"],
        "privacy_policy": {
            "transport": "ghot-local-bounded-adapter-v0",
            "payload_encryption": False,
        },
        "audience_policy": identity_safe({
            "adapter_id": card["adapter_id"],
            "capability": card["capability"],
            "manifest_sha256": card["manifest_sha256"],
        }),
        "return_address": "ghot:instrument-rack:" + dispatch_id,
        "created_at": timestamp_now(),
        "extensions": identity_safe({
            "ghot_profile": "instrument-rack-dispatch/v0",
            "dispatch_source": dispatch_source,
            "card_id": card["card_id"],
            "manifest_sha256": card["manifest_sha256"],
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
    return sign_crossing(envelope, signer)


def _make_receipt(
    crossing: dict[str, Any],
    card: dict[str, Any],
    task: dict[str, Any],
    raw_receipt: dict[str, Any],
    signer: IdentityKey,
) -> dict[str, Any]:
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": "",
        "crossing_id": crossing["crossing_id"],
        "world_id": "world:ghot:instrument-rack",
        "receiver_particular": signer.particular(),
        "kind": "EXECUTED",
        "semantic_effect": "bounded-instrument-attempt",
        "contract_ref": "ghot.instrument-rack@0",
        "pre_state_ref": card["card_id"],
        "post_state_ref": raw_receipt.get("receipt_id"),
        "descendant_refs": [
            value
            for value in [task.get("task_id"), raw_receipt.get("receipt_id")]
            if isinstance(value, str) and value
        ],
        "residual_refs": [],
        "note": (
            "selected donor-owned instrument attempt completed with GHoT status "
            + str(raw_receipt.get("status") or "unknown")
        ),
        "created_at": timestamp_now(),
        "extensions": identity_safe({
            "ghot_profile": "instrument-rack-dispatch/v0",
            "card_id": card["card_id"],
            "adapter_id": card["adapter_id"],
            "capability": card["capability"],
            "execution_status": raw_receipt.get("status"),
            "task_id": task.get("task_id"),
            "ghot_receipt_id": raw_receipt.get("receipt_id"),
            "output_sha256": raw_receipt.get("output_sha256"),
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


def _artifact_map(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        artifact = value.get("artifact")
        if isinstance(artifact, dict):
            return artifact
        for child in value.values():
            found = _artifact_map(child)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _artifact_map(child)
            if found is not None:
                return found
    return None


def _inline_artifacts(donor_result: Any) -> list[dict[str, Any]]:
    artifact = _artifact_map(donor_result)
    if artifact is None:
        return []
    items: list[dict[str, Any]] = []
    for key in sorted(artifact):
        if not key.endswith("_text"):
            continue
        name = key[:-5]
        text_value = artifact.get(key)
        sha_value = artifact.get(name + "_sha256")
        if (
            not isinstance(text_value, str)
            or not isinstance(sha_value, str)
            or not SHA256_RE.fullmatch(sha_value)
        ):
            continue
        raw = text_value.encode("utf-8")
        if _sha_bytes(raw) != sha_value:
            raise ValueError("DONOR_INLINE_ARTIFACT_DIGEST_MISMATCH")
        items.append({
            "name": name,
            "encoding": "utf-8",
            "sha256": sha_value,
            "size_bytes": len(raw),
            "text": text_value,
        })
    return items


def _packet_core(packet: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in packet.items() if key != "packet_id"}


def _build_seed_packet(
    *,
    card: dict[str, Any],
    dispatch_id: str,
    payload: Any,
    crossing: dict[str, Any],
    signed_receipt: dict[str, Any],
    raw_receipt: dict[str, Any],
) -> dict[str, Any]:
    donor_result = raw_receipt.get("output")
    packet = {
        "schema": PACKET_SCHEMA,
        "packet_id": "",
        "source_card_id": card["card_id"],
        "dispatch_id": dispatch_id,
        "dispatch_crossing_id": crossing["crossing_id"],
        "adapter_id": card["adapter_id"],
        "capability": card["capability"],
        "manifest_sha256": card["manifest_sha256"],
        "input_sha256": _digest(payload),
        "donor_result_sha256": _digest(donor_result),
        "ghot_receipt_id": raw_receipt.get("receipt_id"),
        "artifacts": _inline_artifacts(donor_result),
        "donor_result": copy.deepcopy(donor_result),
        "dispatch_crossing": copy.deepcopy(crossing),
        "dispatch_receipt": copy.deepcopy(signed_receipt),
        "status": "PORTABLE_NOT_ADMITTED",
        "semantic_effect": "none",
        "laws": [
            "DONOR RESULT != GHOT SEMANTICS",
            "PACKET != ADMISSION",
            "PORTABLE != AUTHORITY-FREE",
            "ADMISSION != EXECUTION",
        ],
    }
    packet["packet_id"] = "portable-seed-v0:" + _digest(_packet_core(packet))
    return packet


def _existing_dispatch(path: Path, dispatch_id: str) -> dict[str, Any] | None:
    state = _read_json(path)
    if state is None:
        return None
    if (
        state.get("schema") != DISPATCH_STATE_SCHEMA
        or state.get("dispatch_id") != dispatch_id
    ):
        raise RuntimeError("INVALID_STORED_INSTRUMENT_DISPATCH")
    if state.get("state") == "completed":
        result = state.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("INVALID_STORED_INSTRUMENT_DISPATCH_RESULT")
        return result
    if state.get("state") == "prepared":
        raise RuntimeError(
            "INSTRUMENT_DISPATCH_OUTCOME_UNKNOWN: prepared signed dispatch exists; "
            "refusing automatic re-execution"
        )
    raise RuntimeError("INVALID_INSTRUMENT_DISPATCH_STATE")


def dispatch_instrument_card(
    card: Any,
    payload: Any,
    *,
    dispatch_source: str,
) -> dict[str, Any]:
    """Explicitly execute one exact, freshly revalidated instrument card."""
    source = str(dispatch_source).strip()
    if not source:
        raise ValueError("DISPATCH_SOURCE_REQUIRED")
    fresh = _fresh_card(card)
    dispatch_id = _dispatch_id(fresh, payload, source)
    state_path = _dispatch_path(dispatch_id)
    existing = _existing_dispatch(state_path, dispatch_id)
    if existing is not None:
        return existing

    signer = _signer()
    crossing = _make_crossing(fresh, payload, dispatch_id, source, signer)
    if not verify_crossing(crossing):
        raise RuntimeError("SIGNED_INSTRUMENT_DISPATCH_INVALID")

    prepared = {
        "schema": DISPATCH_STATE_SCHEMA,
        "dispatch_id": dispatch_id,
        "state": "prepared",
        "card_id": fresh["card_id"],
        "adapter_id": fresh["adapter_id"],
        "capability": fresh["capability"],
        "payload_sha256": _digest(payload),
        "dispatch_source": source,
        "crossing": crossing,
        "prepared_at": now(),
        "laws": [
            "PREPARED != EXECUTED",
            "AMBIGUOUS OUTCOME != SAFE RETRY",
        ],
    }
    _write_json(state_path, prepared)

    task, raw_receipt = execute(
        fresh["capability"],
        payload,
        requester_node_id=node_id(),
        constraints={
            "instrument_card_id": fresh["card_id"],
            "instrument_dispatch_id": dispatch_id,
            "dispatch_crossing_id": crossing["crossing_id"],
            "dispatch_source": source,
            "bounded_external_adapter_only": True,
            "signed_dispatch_crossing": crossing,
        },
    )
    if task.get("capability") != fresh["capability"]:
        raise RuntimeError("INSTRUMENT_EXECUTION_CAPABILITY_MISMATCH")
    if raw_receipt.get("task_id") != task.get("task_id"):
        raise RuntimeError("INSTRUMENT_RECEIPT_TASK_MISMATCH")
    if raw_receipt.get("capability") != fresh["capability"]:
        raise RuntimeError("INSTRUMENT_RECEIPT_CAPABILITY_MISMATCH")

    signed_receipt = _make_receipt(
        crossing,
        fresh,
        task,
        raw_receipt,
        signer,
    )
    if not verify_receipt(
        signed_receipt,
        expected_public_key=signer.public_jwk(),
        expected_receiver_particular=signer.particular(),
    ):
        raise RuntimeError("SIGNED_INSTRUMENT_RECEIPT_INVALID")

    packet = None
    status = "EXECUTION_ERROR"
    if raw_receipt.get("status") == "ok":
        packet = _build_seed_packet(
            card=fresh,
            dispatch_id=dispatch_id,
            payload=payload,
            crossing=crossing,
            signed_receipt=signed_receipt,
            raw_receipt=raw_receipt,
        )
        status = "EXECUTED"

    result = {
        "schema": DISPATCH_RESULT_SCHEMA,
        "dispatch_id": dispatch_id,
        "card_id": fresh["card_id"],
        "adapter_id": fresh["adapter_id"],
        "capability": fresh["capability"],
        "dispatch_source": source,
        "status": status,
        "semantic_effect": "bounded-instrument-attempt",
        "task": task,
        "execution_receipt": raw_receipt,
        "signed_receipt": signed_receipt,
        "packet": packet,
        "laws": [
            "CARD != ASSIGNMENT",
            "DISPATCH != SUCCESS",
            "EXECUTION != RECEIPT",
            "DONOR RESULT != GHOT SEMANTICS",
        ],
    }
    _write_json(state_path, {
        **prepared,
        "state": "completed",
        "completed_at": now(),
        "result": result,
    })
    return result


def _validate_packet(packet: Any) -> dict[str, Any]:
    if not isinstance(packet, dict) or packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    claimed = str(packet.get("packet_id") or "")
    expected = "portable-seed-v0:" + _digest(_packet_core(packet))
    if claimed != expected:
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    donor_result = packet.get("donor_result")
    if packet.get("donor_result_sha256") != _digest(donor_result):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    crossing = packet.get("dispatch_crossing")
    receipt = packet.get("dispatch_receipt")
    if not isinstance(crossing, dict) or not verify_crossing(crossing):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if not isinstance(receipt, dict) or not verify_receipt(receipt):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if receipt.get("crossing_id") != crossing.get("crossing_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if packet.get("dispatch_crossing_id") != crossing.get("crossing_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    requested = crossing.get("requested_effect") or {}
    audience = crossing.get("audience_policy") or {}
    extensions = receipt.get("extensions") or {}
    payload_refs = crossing.get("payload_refs") or []
    input_ref = next(
        (
            item
            for item in payload_refs
            if isinstance(item, dict) and item.get("role") == "instrument-input"
        ),
        None,
    )
    if (
        not isinstance(input_ref, dict)
        or input_ref.get("address") != "sha256:" + str(packet.get("input_sha256") or "")
    ):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if crossing.get("capability_ref") != packet.get("capability"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if requested.get("dispatch_id") != packet.get("dispatch_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if requested.get("card_id") != packet.get("source_card_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if requested.get("adapter_id") != packet.get("adapter_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if requested.get("capability") != packet.get("capability"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if audience.get("adapter_id") != packet.get("adapter_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if audience.get("capability") != packet.get("capability"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if audience.get("manifest_sha256") != packet.get("manifest_sha256"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if receipt.get("pre_state_ref") != packet.get("source_card_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if receipt.get("post_state_ref") != packet.get("ghot_receipt_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if extensions.get("card_id") != packet.get("source_card_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if extensions.get("adapter_id") != packet.get("adapter_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if extensions.get("capability") != packet.get("capability"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if extensions.get("ghot_receipt_id") != packet.get("ghot_receipt_id"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    if extensions.get("output_sha256") != packet.get("donor_result_sha256"):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    try:
        extracted = _inline_artifacts(donor_result)
    except ValueError as exc:
        raise ValueError("INVALID_PORTABLE_SEED_PACKET") from exc
    if _canonical(packet.get("artifacts") or []) != _canonical(extracted):
        raise ValueError("INVALID_PORTABLE_SEED_PACKET")
    return packet


def admit_seed_packet(
    packet: Any,
    *,
    admission_source: str,
) -> dict[str, Any]:
    """Admit a verified packet as local material without executing anything."""
    source = str(admission_source).strip()
    if not source:
        raise ValueError("ADMISSION_SOURCE_REQUIRED")
    verified = _validate_packet(packet)
    material_id = "seed-material-v0:" + _digest({
        "packet_id": verified["packet_id"],
        "admission_source": source,
    })
    path = (
        _home()
        / "instrument-rack"
        / "materials"
        / f"{material_id.rsplit(':', 1)[-1]}.json"
    )
    existing = _read_json(path)
    if existing is not None:
        if existing.get("material_id") != material_id:
            raise RuntimeError("INVALID_STORED_SEED_MATERIAL")
        return existing

    material = {
        "schema": MATERIAL_SCHEMA,
        "material_id": material_id,
        "source_packet_id": verified["packet_id"],
        "source_card_id": verified["source_card_id"],
        "adapter_id": verified["adapter_id"],
        "capability": verified["capability"],
        "donor_result_sha256": verified["donor_result_sha256"],
        "artifacts": copy.deepcopy(verified.get("artifacts") or []),
        "admission_source": source,
        "status": "ADMITTED_NOT_EXECUTED",
        "semantic_effect": "local-material-only",
        "admitted_at": now(),
        "laws": [
            "PACKET != ADMISSION",
            "ADMISSION != EXECUTION",
            "DONOR RESULT != GHOT SEMANTICS",
            "MATERIAL != KEEP",
        ],
    }
    _write_json(path, material)
    return material


def handle(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("INSTRUMENT_RACK_REQUEST_REQUIRED")
    action = request.get("action")
    if action == "rack":
        return build_instrument_rack()
    if action == "dispatch":
        return dispatch_instrument_card(
            request.get("card"),
            request.get("payload"),
            dispatch_source=str(request.get("dispatch_source") or ""),
        )
    if action == "admit":
        return admit_seed_packet(
            request.get("packet"),
            admission_source=str(request.get("admission_source") or ""),
        )
    raise ValueError("UNKNOWN_INSTRUMENT_RACK_ACTION")


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("INSTRUMENT_RACK_REQUEST_REQUIRED")
    sys.stdout.write(json.dumps(handle(json.loads(raw))))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(json.dumps({"error": f"{type(exc).__name__}: {exc}"}) + "\n")
        raise SystemExit(1)
