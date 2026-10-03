#!/usr/bin/env python3
"""FIELD-RESEED-RECEIVER-001: receiver-local HOLD and explicit admission.

This surface accepts only a verified reLATTE RECEIVE -> HOLD crossing carrying a
Workbench field reseed. Receiving persists the exact donor reseed under GHoT's
local state. Admission is a second explicit action and still does not execute
the reseed or select an executor.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_RESEED = "workbench.field-reseed/v0"
SCHEMA_RELATTE = "relatte.opaque-roundtrip-result/v0"
DONOR_FAMILY = "organ:static-workbench/field-return"
RECEIVER_WORLD = "world:ghot:field-reseed-inbox"
RECEIVER_PARTICULAR = "particular:ghot:field-reseed-inbox"


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _home() -> Path:
    raw = os.environ.get("GHOT_HOME", "").strip()
    base = Path(raw).expanduser() if raw else Path.home() / ".ghot"
    root = base / "field-reseed-inbox"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _verified_reseed(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA_RESEED:
        raise ValueError("INVALID_FIELD_RESEED_SCHEMA")
    reseed_id = value.get("reseed_id")
    if not isinstance(reseed_id, str) or not reseed_id.startswith("field-reseed-v0:"):
        raise ValueError("INVALID_FIELD_RESEED_ID")
    body = {key: item for key, item in value.items() if key != "reseed_id"}
    expected = "field-reseed-v0:" + _digest(body)
    if reseed_id != expected:
        raise ValueError("FIELD_RESEED_IDENTITY_MISMATCH")
    if value.get("status") != "proposal-only" or value.get("effect") != "none":
        raise ValueError("FIELD_RESEED_IS_NOT_PROPOSAL_ONLY")
    return json.loads(_canonical(value))


def _verified_crossing(value: Any, reseed: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA_RELATTE:
        raise ValueError("INVALID_RELATTE_ROUNDTRIP")

    crossing = value.get("crossing")
    received = value.get("receive_receipt")
    disposition = value.get("disposition_receipt")
    if not all(isinstance(item, dict) for item in (crossing, received, disposition)):
        raise ValueError("INCOMPLETE_RELATTE_ROUNDTRIP")

    crossing_id = crossing.get("crossing_id")
    if (
        not isinstance(crossing_id, str)
        or received.get("crossing_id") != crossing_id
        or disposition.get("crossing_id") != crossing_id
    ):
        raise ValueError("RELATTE_CROSSING_BINDING_MISMATCH")
    if received.get("kind") != "RECEIVED" or received.get("semantic_effect") != "none":
        raise ValueError("RELATTE_RECEIVE_BOUNDARY_NOT_PRESERVED")
    if disposition.get("kind") != "R3_HOLD" or disposition.get("semantic_effect") != "none":
        raise ValueError("RELATTE_HOLD_BOUNDARY_NOT_PRESERVED")
    if received.get("world_id") != RECEIVER_WORLD:
        raise ValueError("RELATTE_WRONG_RECEIVER_WORLD")

    adapter = crossing.get("extensions", {}).get("organ_adapter", {})
    if adapter.get("family_ref") != DONOR_FAMILY:
        raise ValueError("RELATTE_WRONG_DONOR_FAMILY")
    claims = adapter.get("donor_claims")
    if not isinstance(claims, dict):
        raise ValueError("RELATTE_DONOR_CLAIMS_MISSING")
    if claims.get("reseed_id") != reseed.get("reseed_id"):
        raise ValueError("RELATTE_RESEED_BINDING_MISMATCH")

    expected_sha = _digest(reseed)
    refs = crossing.get("payload_refs")
    if not isinstance(refs, list) or not any(
        isinstance(ref, dict)
        and ref.get("address") == "sha256:" + expected_sha
        and ref.get("role") == "field-reseed"
        for ref in refs
    ):
        raise ValueError("RELATTE_RESEED_PAYLOAD_REF_MISMATCH")

    return json.loads(_canonical(value))


def _entry_dir(reseed_id: str) -> Path:
    digest = reseed_id.split(":", 1)[1]
    path = _home() / digest
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("INVALID_RECEIVER_STATE")
    return value


def _write_new_or_same(path: Path, value: dict[str, Any]) -> dict[str, Any]:
    encoded = _canonical(value)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != encoded:
            raise ValueError("RECEIVER_STATE_CONFLICT")
        return json.loads(existing)
    path.write_text(encoded, encoding="utf-8")
    return json.loads(encoded)


def receive(reseed_value: Any, relatte_value: Any) -> dict[str, Any]:
    reseed = _verified_reseed(reseed_value)
    relatte = _verified_crossing(relatte_value, reseed)
    entry = _entry_dir(reseed["reseed_id"])

    snapshot = {
        "schema": "ghot.field-reseed-hold/v0",
        "hold_id": "ghot-field-reseed-hold-v0:" + _digest({
            "reseed_id": reseed["reseed_id"],
            "crossing_id": relatte["crossing"]["crossing_id"],
            "receiver": RECEIVER_PARTICULAR,
        }),
        "reseed_id": reseed["reseed_id"],
        "crossing_id": relatte["crossing"]["crossing_id"],
        "receive_receipt_id": relatte["receive_receipt"].get("receipt_id"),
        "hold_receipt_id": relatte["disposition_receipt"].get("receipt_id"),
        "receiver_world": RECEIVER_WORLD,
        "receiver_particular": RECEIVER_PARTICULAR,
        "status": "HOLD",
        "semantic_effect": "none",
        "donor_reseed": reseed,
        "received_at": _now(),
        "laws": [
            "RECEIVE != ADMISSION",
            "HOLD != EXECUTION",
            "TRANSPORT != AUTHORITY",
            "DONOR PROPOSAL != RECEIVER INTENT",
        ],
    }

    # Time is witness data, not identity. Idempotency is keyed by the stable hold id.
    existing = _read_json(entry / "hold.json")
    if existing is not None:
        comparable_existing = {k: v for k, v in existing.items() if k != "received_at"}
        comparable_new = {k: v for k, v in snapshot.items() if k != "received_at"}
        if comparable_existing != comparable_new:
            raise ValueError("FIELD_RESEED_HOLD_CONFLICT")
        return existing

    (entry / "reseed.json").write_text(_canonical(reseed), encoding="utf-8")
    (entry / "relatte.json").write_text(_canonical(relatte), encoding="utf-8")
    return _write_new_or_same(entry / "hold.json", snapshot)


def admit(hold_id: str, selection_source: str) -> dict[str, Any]:
    if not isinstance(hold_id, str) or not hold_id.startswith("ghot-field-reseed-hold-v0:"):
        raise ValueError("INVALID_FIELD_RESEED_HOLD_ID")
    source = str(selection_source).strip()
    if not source:
        raise ValueError("ADMISSION_SELECTION_SOURCE_REQUIRED")

    found: tuple[Path, dict[str, Any]] | None = None
    for entry in sorted(_home().iterdir()):
        if not entry.is_dir():
            continue
        hold = _read_json(entry / "hold.json")
        if hold is not None and hold.get("hold_id") == hold_id:
            found = (entry, hold)
            break
    if found is None:
        raise ValueError("FIELD_RESEED_HOLD_NOT_FOUND")

    entry, hold = found
    reseed = _read_json(entry / "reseed.json")
    if reseed is None:
        raise ValueError("FIELD_RESEED_DONOR_SNAPSHOT_MISSING")

    identity_body = {
        "hold_id": hold_id,
        "reseed_id": reseed["reseed_id"],
        "selection_source": source,
        "receiver": RECEIVER_PARTICULAR,
    }
    admission_id = "ghot-field-reseed-admission-v0:" + _digest(identity_body)
    intent = {
        "schema": "ghot.carried-intent/v0",
        "intent_id": "ghot-carried-intent-v0:" + _digest({
            "admission_id": admission_id,
            "reseed_id": reseed["reseed_id"],
        }),
        "source_reseed_id": reseed["reseed_id"],
        "source_return_id": reseed.get("source_return_id"),
        "door": reseed.get("door"),
        "human_note": reseed.get("human_note"),
        "status": "admitted-not-assigned",
        "effect": "local-inbox-only",
        "laws": [
            "ADMISSION != ASSIGNMENT",
            "ASSIGNMENT != EXECUTION",
            "CARRIED INTENT != DONOR AUTHORITY",
        ],
    }
    admission = {
        "schema": "ghot.field-reseed-admission/v0",
        "admission_id": admission_id,
        "hold_id": hold_id,
        "reseed_id": reseed["reseed_id"],
        "selection_source": source,
        "receiver_world": RECEIVER_WORLD,
        "receiver_particular": RECEIVER_PARTICULAR,
        "status": "ADMITTED",
        "semantic_effect": "local-inbox-only",
        "intent": intent,
        "admitted_at": _now(),
        "laws": [
            "ADMISSION != ASSIGNMENT",
            "ADMISSION != EXECUTION",
            "RECEIVER CONSEQUENCE != DONOR CONSEQUENCE",
        ],
    }

    existing = _read_json(entry / "admission.json")
    if existing is not None:
        comparable_existing = {k: v for k, v in existing.items() if k != "admitted_at"}
        comparable_new = {k: v for k, v in admission.items() if k != "admitted_at"}
        if comparable_existing != comparable_new:
            raise ValueError("FIELD_RESEED_ADMISSION_CONFLICT")
        return existing
    return _write_new_or_same(entry / "admission.json", admission)


def status() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if _home().is_dir():
        for entry in sorted(_home().iterdir()):
            if not entry.is_dir():
                continue
            hold = _read_json(entry / "hold.json")
            if hold is None:
                continue
            admission = _read_json(entry / "admission.json")
            items.append({
                "reseed_id": hold.get("reseed_id"),
                "hold_id": hold.get("hold_id"),
                "crossing_id": hold.get("crossing_id"),
                "status": "ADMITTED" if admission is not None else "HOLD",
                "admission_id": admission.get("admission_id") if admission else None,
                "intent_id": (
                    admission.get("intent", {}).get("intent_id")
                    if admission else None
                ),
            })
    items.sort(key=lambda item: str(item.get("reseed_id")))
    return {
        "schema": "ghot.field-reseed-inbox-status/v0",
        "receiver_world": RECEIVER_WORLD,
        "receiver_particular": RECEIVER_PARTICULAR,
        "held": sum(1 for item in items if item["status"] == "HOLD"),
        "admitted": sum(1 for item in items if item["status"] == "ADMITTED"),
        "items": items,
        "laws": [
            "INBOX STATE != EXECUTION STATE",
            "ADMITTED != ASSIGNED",
        ],
    }


def handle(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("FIELD_RESEED_RECEIVER_REQUEST_REQUIRED")
    action = request.get("action")
    if action == "receive":
        return receive(request.get("reseed"), request.get("relatte_result"))
    if action == "admit":
        return admit(str(request.get("hold_id") or ""), str(request.get("selection_source") or ""))
    if action == "status":
        return status()
    raise ValueError("UNKNOWN_FIELD_RESEED_RECEIVER_ACTION")


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("FIELD_RESEED_RECEIVER_REQUEST_REQUIRED")
    result = handle(json.loads(raw))
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(json.dumps({
            "error": str(exc),
        }) + "\n")
        raise SystemExit(1)
