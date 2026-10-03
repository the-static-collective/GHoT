#!/usr/bin/env python3
"""CARRIED-INTENT-ASSIGNMENT-001: offer and assign without execution.

An admitted ghot.carried-intent/v0 may be shown the current GHoT body/capability
field. A human/external caller then names one exact body and one exact
capability. GHoT revalidates that pair and persists an assignment receipt.

This module never creates a task, invokes an adapter, dispatches remotely, or
calls reference_node.execute().
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from capability_composer import candidate_view, gather_candidates
from field_reseed_receiver import _canonical, _home, _read_json
from reference_node import now, node_id


OFFER_SCHEMA = "ghot.carried-intent-assignment-offer/v0"
ASSIGNMENT_SCHEMA = "ghot.carried-intent-assignment/v0"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _entry_for_intent(intent_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    if not isinstance(intent_id, str) or not intent_id.startswith("ghot-carried-intent-v0:"):
        raise ValueError("INVALID_CARRIED_INTENT_ID")

    for entry in sorted(_home().iterdir()):
        if not entry.is_dir():
            continue
        admission = _read_json(entry / "admission.json")
        if not isinstance(admission, dict):
            continue
        intent = admission.get("intent")
        if isinstance(intent, dict) and intent.get("intent_id") == intent_id:
            if intent.get("schema") != "ghot.carried-intent/v0":
                raise ValueError("INVALID_STORED_CARRIED_INTENT")
            if intent.get("status") != "admitted-not-assigned":
                raise ValueError("CARRIED_INTENT_NOT_ASSIGNABLE")
            return entry, admission, intent
    raise ValueError("CARRIED_INTENT_NOT_FOUND")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(_canonical(value), encoding="utf-8")
    temp.replace(path)


def _available_offer_rows(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    body = candidate.get("body") or {}
    awake = candidate.get("field_state") == "awake"
    rows: list[dict[str, Any]] = []
    for raw in body.get("offers", []):
        capability = raw.get("capability")
        if not isinstance(capability, str) or not capability:
            continue
        available = raw.get("available") is True
        rejected: list[str] = []
        if not awake:
            rejected.append(
                f"body liveness is {candidate.get('field_state') or 'unknown'}, not awake"
            )
        if not available:
            rejected.append("capability is currently unavailable")
        rows.append({
            "capability": capability,
            "available": available,
            "eligible": bool(awake and available),
            "executor": raw.get("executor"),
            "limits": raw.get("limits"),
            "power": raw.get("power"),
            "rejected": rejected,
        })
    rows.sort(key=lambda item: item["capability"])
    return rows


def _offer_body(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "offer_id"}


def verify_offer(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != OFFER_SCHEMA:
        raise ValueError("INVALID_CARRIED_INTENT_ASSIGNMENT_OFFER")
    offer_id = value.get("offer_id")
    if not isinstance(offer_id, str):
        raise ValueError("INVALID_CARRIED_INTENT_ASSIGNMENT_OFFER_ID")
    expected = "ghot-carried-intent-offer-v0:" + _digest(_offer_body(value))
    if offer_id != expected:
        raise ValueError("CARRIED_INTENT_ASSIGNMENT_OFFER_IDENTITY_MISMATCH")
    if not isinstance(value.get("bodies"), list):
        raise ValueError("CARRIED_INTENT_ASSIGNMENT_OFFER_BODIES_MISSING")
    return json.loads(_canonical(value))


def offer(intent_id: str, *, timeout: float = 0.5) -> dict[str, Any]:
    entry, admission, intent = _entry_for_intent(intent_id)
    if (entry / "assignment.json").is_file():
        raise ValueError("CARRIED_INTENT_ALREADY_ASSIGNED")

    candidates, _field = gather_candidates(timeout)
    bodies: list[dict[str, Any]] = []
    for candidate in candidates:
        view = candidate_view(candidate)
        bodies.append({
            **view,
            "offers": _available_offer_rows(candidate),
        })
    bodies.sort(key=lambda item: item["node_id"])

    body = {
        "schema": OFFER_SCHEMA,
        "intent_id": intent_id,
        "intent_sha256": _digest(intent),
        "admission_id": admission.get("admission_id"),
        "source_reseed_id": intent.get("source_reseed_id"),
        "observed_at": now(),
        "requester_node_id": node_id(),
        "bodies": bodies,
        "laws": [
            "ADMISSION != ASSIGNMENT",
            "OFFER != ASSIGNMENT",
            "CAPABILITY != AUTHORITY",
            "BODY AVAILABILITY != SELECTION",
            "NO SCORE != NO INFORMATION",
            "ASSIGNMENT REVALIDATES CURRENT STATE",
        ],
    }
    result = {
        **body,
        "offer_id": "ghot-carried-intent-offer-v0:" + _digest(body),
    }
    _write_json(entry / "assignment-offer.json", result)
    return result


def _find_offered_pair(
    offer_value: dict[str, Any],
    selected_node_id: str,
    capability: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    body = next(
        (
            item for item in offer_value["bodies"]
            if item.get("node_id") == selected_node_id
        ),
        None,
    )
    if body is None:
        raise ValueError("SELECTED_BODY_NOT_IN_OFFER")
    row = next(
        (
            item for item in body.get("offers", [])
            if item.get("capability") == capability
        ),
        None,
    )
    if row is None:
        raise ValueError("SELECTED_CAPABILITY_NOT_IN_BODY_OFFER")
    if row.get("eligible") is not True:
        raise ValueError("SELECTED_BODY_CAPABILITY_PAIR_NOT_ELIGIBLE")
    return body, row


def _revalidate_pair(
    selected_node_id: str,
    capability: str,
    offered_body: dict[str, Any],
    *,
    timeout: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates, _field = gather_candidates(timeout)
    current = next(
        (
            candidate for candidate in candidates
            if candidate.get("node_id") == selected_node_id
        ),
        None,
    )
    if current is None:
        raise RuntimeError("SELECTED_BODY_NO_LONGER_DISCOVERABLE")
    if current.get("field_state") != "awake":
        raise RuntimeError("SELECTED_BODY_NO_LONGER_AWAKE")

    current_view = candidate_view(current)
    offered_particular = offered_body.get("identity_particular")
    current_particular = current_view.get("identity_particular")
    if offered_particular and current_particular != offered_particular:
        raise RuntimeError("SELECTED_BODY_IDENTITY_CHANGED")

    current_offer = next(
        (
            item for item in (current.get("body") or {}).get("offers", [])
            if item.get("capability") == capability
        ),
        None,
    )
    if not isinstance(current_offer, dict):
        raise RuntimeError("SELECTED_CAPABILITY_NO_LONGER_OFFERED")
    if current_offer.get("available") is not True:
        raise RuntimeError("SELECTED_CAPABILITY_NO_LONGER_AVAILABLE")
    return current_view, {
        "capability": capability,
        "available": True,
        "executor": current_offer.get("executor"),
        "limits": current_offer.get("limits"),
        "power": current_offer.get("power"),
    }


def assign(
    intent_id: str,
    offer_value: Any,
    selected_node_id: str,
    capability: str,
    selection_source: str,
    *,
    timeout: float = 0.5,
) -> dict[str, Any]:
    entry, admission, intent = _entry_for_intent(intent_id)
    checked = verify_offer(offer_value)
    if checked.get("intent_id") != intent_id:
        raise ValueError("ASSIGNMENT_OFFER_BOUND_TO_ANOTHER_INTENT")
    if checked.get("admission_id") != admission.get("admission_id"):
        raise ValueError("ASSIGNMENT_OFFER_BOUND_TO_ANOTHER_ADMISSION")
    if checked.get("intent_sha256") != _digest(intent):
        raise ValueError("ASSIGNMENT_OFFER_INTENT_SNAPSHOT_MISMATCH")

    stored_offer = _read_json(entry / "assignment-offer.json")
    if stored_offer is None or _canonical(stored_offer) != _canonical(checked):
        raise ValueError("ASSIGNMENT_OFFER_IS_NOT_CURRENT_RECEIVER_OFFER")

    selected_node_id = str(selected_node_id).strip()
    capability = str(capability).strip()
    source = str(selection_source).strip()
    if not selected_node_id:
        raise ValueError("SELECTED_NODE_ID_REQUIRED")
    if not capability:
        raise ValueError("SELECTED_CAPABILITY_REQUIRED")
    if not source:
        raise ValueError("ASSIGNMENT_SELECTION_SOURCE_REQUIRED")

    offered_body, offered_capability = _find_offered_pair(
        checked, selected_node_id, capability
    )

    identity = {
        "intent_id": intent_id,
        "admission_id": admission.get("admission_id"),
        "offer_id": checked["offer_id"],
        "selected_node_id": selected_node_id,
        "capability": capability,
        "selection_source": source,
    }
    assignment_id = "ghot-carried-intent-assignment-v0:" + _digest(identity)

    existing = _read_json(entry / "assignment.json")
    if existing is not None:
        if existing.get("assignment_id") != assignment_id:
            raise ValueError("CARRIED_INTENT_ALREADY_ASSIGNED_DIFFERENTLY")
        return existing

    current_body, current_offer = _revalidate_pair(
        selected_node_id,
        capability,
        offered_body,
        timeout=timeout,
    )

    assignment = {
        "schema": ASSIGNMENT_SCHEMA,
        "assignment_id": assignment_id,
        **identity,
        "intent_sha256": _digest(intent),
        "offered_body": offered_body,
        "offered_capability": offered_capability,
        "revalidated_body": current_body,
        "revalidated_capability": current_offer,
        "status": "ASSIGNED_NOT_EXECUTED",
        "semantic_effect": "assignment-only",
        "assigned_at": now(),
        "laws": [
            "OFFER != ASSIGNMENT",
            "ASSIGNMENT != EXECUTION",
            "ASSIGNMENT != TASK",
            "SELECTED BODY != AUTHORITY OWNER",
            "CAPABILITY != EXECUTION",
            "DISPATCH REQUIRES A NEW EXPLICIT CROSSING",
        ],
    }
    _write_json(entry / "assignment.json", assignment)
    return assignment


def status(intent_id: str) -> dict[str, Any]:
    entry, admission, intent = _entry_for_intent(intent_id)
    offer_value = _read_json(entry / "assignment-offer.json")
    assignment = _read_json(entry / "assignment.json")
    return {
        "schema": "ghot.carried-intent-assignment-status/v0",
        "intent_id": intent_id,
        "admission_id": admission.get("admission_id"),
        "source_reseed_id": intent.get("source_reseed_id"),
        "status": (
            "ASSIGNED_NOT_EXECUTED"
            if assignment is not None
            else "OFFER_READY"
            if offer_value is not None
            else "ADMITTED_NOT_ASSIGNED"
        ),
        "offer": offer_value,
        "assignment": assignment,
        "laws": [
            "STATUS != EXECUTION",
            "ASSIGNMENT != TASK",
        ],
    }


def handle(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("CARRIED_INTENT_ASSIGNMENT_REQUEST_REQUIRED")
    action = request.get("action")
    intent_id = str(request.get("intent_id") or "")
    if action == "offer":
        return offer(intent_id, timeout=float(request.get("timeout", 0.5)))
    if action == "assign":
        return assign(
            intent_id,
            request.get("offer"),
            str(request.get("selected_node_id") or ""),
            str(request.get("capability") or ""),
            str(request.get("selection_source") or ""),
            timeout=float(request.get("timeout", 0.5)),
        )
    if action == "status":
        return status(intent_id)
    raise ValueError("UNKNOWN_CARRIED_INTENT_ASSIGNMENT_ACTION")


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("CARRIED_INTENT_ASSIGNMENT_REQUEST_REQUIRED")
    result = handle(json.loads(raw))
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(json.dumps({"error": f"{type(exc).__name__}: {exc}"}) + "\n")
        raise SystemExit(1)
