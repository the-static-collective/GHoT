#!/usr/bin/env python3
"""CARRIED-INTENT-DISPATCH-001: explicit signed dispatch from assignment.

Dispatch is a new receiver-owned crossing. It begins only from a persisted
ASSIGNED_NOT_EXECUTED receipt, revalidates the exact selected body/capability,
persists a prepared signed crossing, executes at most once, and then persists a
signed consequence receipt.

Prepared-but-incomplete state refuses automatic retry because execution outcome
may be unknown.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from carried_intent_assignment import (
    ASSIGNMENT_SCHEMA,
    _entry_for_intent,
    _revalidate_pair,
)
from field_reseed_receiver import _canonical, _home, _read_json
from lan_node import request_task
from reference_node import execute, node_id
from relatte_identity import (
    IdentityKey,
    identity_safe,
    sign_crossing,
    sign_receipt,
    timestamp_now,
    verify_crossing,
    verify_receipt,
)


DISPATCH_RESULT_SCHEMA = "ghot.carried-intent-dispatch-result/v0"
DISPATCH_STATE_SCHEMA = "ghot.carried-intent-dispatch-state/v0"
EXECUTION_PAYLOAD_SCHEMA = "ghot.carried-intent-execution-payload/v0"
CROSSING_SCHEMA = "relatte.crossing-envelope/v0"
RECEIPT_SCHEMA = "relatte.receipt/v0"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _signer() -> IdentityKey:
    root = _home().parent
    return IdentityKey.load_or_create(root / "identity" / "dispatch-p256.pem")


def _dispatch_state_path(entry: Path) -> Path:
    return entry / "dispatch-state.json"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(_canonical(value), encoding="utf-8")
    tmp.replace(path)


def _load_assignment(
    intent_id: str,
) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    entry, admission, intent = _entry_for_intent(intent_id)
    assignment = _read_json(entry / "assignment.json")
    if not isinstance(assignment, dict):
        raise ValueError("CARRIED_INTENT_ASSIGNMENT_REQUIRED")
    if (
        assignment.get("schema") != ASSIGNMENT_SCHEMA
        or assignment.get("intent_id") != intent_id
        or assignment.get("status") != "ASSIGNED_NOT_EXECUTED"
        or assignment.get("semantic_effect") != "assignment-only"
    ):
        raise ValueError("INVALID_CARRIED_INTENT_ASSIGNMENT")
    return entry, admission, intent, assignment


def _execution_payload(
    intent: dict[str, Any],
    assignment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": EXECUTION_PAYLOAD_SCHEMA,
        "intent_id": intent.get("intent_id"),
        "assignment_id": assignment.get("assignment_id"),
        "source_reseed_id": intent.get("source_reseed_id"),
        "source_return_id": intent.get("source_return_id"),
        "door": intent.get("door"),
        "human_note": intent.get("human_note"),
        "receiver_selection": {
            "selected_node_id": assignment.get("selected_node_id"),
            "capability": assignment.get("capability"),
        },
        "laws": [
            "PAYLOAD != AUTHORITY",
            "DOOR != COMMAND",
            "ASSIGNMENT != EXECUTION",
            "EXECUTION IS BOUNDED TO ASSIGNED CAPABILITY",
        ],
    }


def _make_crossing(
    intent: dict[str, Any],
    assignment: dict[str, Any],
    payload: dict[str, Any],
    signer: IdentityKey,
) -> dict[str, Any]:
    selected = assignment.get("revalidated_body") or {}
    selected_particular = selected.get("identity_particular")
    envelope = {
        "schema": CROSSING_SCHEMA,
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": "world:ghot:field-reseed-inbox",
        "source_history_head": "sha256:" + _digest(assignment),
        "parents": [],
        "declared_kind": "GHOT_CARRIED_INTENT_DISPATCH",
        "payload_refs": [{
            "address": "sha256:" + _digest(payload),
            "role": "carried-intent-execution-payload",
            "media_type": "application/json",
        }],
        "requested_effect": identity_safe({
            "action": "EXECUTE_ASSIGNED_CAPABILITY",
            "intent_id": intent.get("intent_id"),
            "assignment_id": assignment.get("assignment_id"),
            "selected_node_id": assignment.get("selected_node_id"),
            "capability": assignment.get("capability"),
        }),
        "capability_ref": assignment.get("capability"),
        "privacy_policy": {
            "transport": "ghot-local-or-selected-lan-v0",
            "payload_encryption": False,
        },
        "audience_policy": identity_safe({
            "selected_node_id": assignment.get("selected_node_id"),
            "selected_identity_particular": selected_particular,
        }),
        "return_address": (
            "ghot:field-reseed-inbox:"
            + str(intent.get("intent_id") or "")
        ),
        "created_at": timestamp_now(),
        "extensions": identity_safe({
            "ghot_profile": "carried-intent-dispatch/v0",
            "assignment_id": assignment.get("assignment_id"),
            "offer_id": assignment.get("offer_id"),
            "source_reseed_id": intent.get("source_reseed_id"),
            "source_return_id": intent.get("source_return_id"),
            "selection_source": assignment.get("selection_source"),
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


def _make_signed_receipt(
    crossing: dict[str, Any],
    assignment: dict[str, Any],
    execution: dict[str, Any],
    signer: IdentityKey,
) -> dict[str, Any]:
    task = execution.get("task") or {}
    raw_receipt = execution.get("receipt") or {}
    status = str(raw_receipt.get("status") or "unknown")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": "",
        "crossing_id": crossing.get("crossing_id"),
        "world_id": "world:ghot:carried-intent-dispatch",
        "receiver_particular": signer.particular(),
        "kind": "EXECUTED",
        "semantic_effect": "bounded-capability-attempt",
        "contract_ref": "ghot.carried-intent-dispatch@0",
        "pre_state_ref": assignment.get("assignment_id"),
        "post_state_ref": raw_receipt.get("receipt_id"),
        "descendant_refs": [
            value
            for value in [
                task.get("task_id"),
                raw_receipt.get("receipt_id"),
            ]
            if isinstance(value, str) and value
        ],
        "residual_refs": [],
        "note": (
            "assigned capability attempt completed with GHoT status "
            + status
        ),
        "created_at": timestamp_now(),
        "extensions": identity_safe({
            "ghot_profile": "carried-intent-dispatch/v0",
            "intent_id": assignment.get("intent_id"),
            "assignment_id": assignment.get("assignment_id"),
            "selected_node_id": assignment.get("selected_node_id"),
            "capability": assignment.get("capability"),
            "execution_status": status,
            "task_id": task.get("task_id"),
            "ghot_receipt_id": raw_receipt.get("receipt_id"),
            "output_sha256": raw_receipt.get("output_sha256"),
            "error": raw_receipt.get("error"),
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


def _validate_execution_binding(
    execution: dict[str, Any],
    assignment: dict[str, Any],
) -> None:
    if not isinstance(execution, dict):
        raise RuntimeError("INVALID_GHOT_EXECUTION_RESULT")
    task = execution.get("task")
    receipt = execution.get("receipt")
    if not isinstance(task, dict) or not isinstance(receipt, dict):
        raise RuntimeError("INCOMPLETE_GHOT_EXECUTION_RESULT")
    if task.get("capability") != assignment.get("capability"):
        raise RuntimeError("EXECUTION_CAPABILITY_MISMATCH")
    if receipt.get("task_id") != task.get("task_id"):
        raise RuntimeError("EXECUTION_RECEIPT_TASK_MISMATCH")
    if receipt.get("capability") != assignment.get("capability"):
        raise RuntimeError("EXECUTION_RECEIPT_CAPABILITY_MISMATCH")
    executor = receipt.get("executor_node_id")
    selected = assignment.get("selected_node_id")
    if isinstance(executor, str) and executor and executor != selected:
        raise RuntimeError("EXECUTION_RECEIPT_BODY_MISMATCH")


def _existing_result(
    state_path: Path,
    assignment_id: str,
) -> dict[str, Any] | None:
    state = _read_json(state_path)
    if state is None:
        return None
    if (
        state.get("schema") != DISPATCH_STATE_SCHEMA
        or state.get("assignment_id") != assignment_id
    ):
        raise RuntimeError("INVALID_STORED_CARRIED_INTENT_DISPATCH")
    if state.get("state") == "completed":
        result = state.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("INVALID_STORED_CARRIED_INTENT_DISPATCH_RESULT")
        return result
    if state.get("state") == "prepared":
        raise RuntimeError(
            "DISPATCH_OUTCOME_UNKNOWN: prepared signed dispatch exists; "
            "refusing automatic re-execution"
        )
    raise RuntimeError("INVALID_CARRIED_INTENT_DISPATCH_STATE")


def dispatch(
    intent_id: str,
    *,
    dispatch_source: str,
    timeout: float = 0.5,
) -> dict[str, Any]:
    source = str(dispatch_source).strip()
    if not source:
        raise ValueError("DISPATCH_SOURCE_REQUIRED")

    entry, _admission, intent, assignment = _load_assignment(intent_id)
    assignment_id = str(assignment.get("assignment_id") or "")
    state_path = _dispatch_state_path(entry)

    existing = _existing_result(state_path, assignment_id)
    if existing is not None:
        return existing

    offered_body = assignment.get("offered_body")
    if not isinstance(offered_body, dict):
        raise ValueError("ASSIGNMENT_OFFERED_BODY_MISSING")
    current_body, current_offer = _revalidate_pair(
        str(assignment.get("selected_node_id") or ""),
        str(assignment.get("capability") or ""),
        offered_body,
        timeout=timeout,
    )

    payload = _execution_payload(intent, assignment)
    signer = _signer()
    crossing = _make_crossing(intent, assignment, payload, signer)
    if not verify_crossing(crossing):
        raise RuntimeError("SIGNED_DISPATCH_CROSSING_INVALID")

    prepared = {
        "schema": DISPATCH_STATE_SCHEMA,
        "state": "prepared",
        "assignment_id": assignment_id,
        "intent_id": intent_id,
        "crossing_id": crossing["crossing_id"],
        "payload_sha256": _digest(payload),
        "dispatch_source": source,
        "prepared_at": timestamp_now(),
        "crossing": crossing,
        "laws": [
            "PREPARED != EXECUTED",
            "AMBIGUOUS OUTCOME != SAFE RETRY",
        ],
    }
    _write_json(state_path, prepared)

    constraints = {
        "carried_intent_id": intent_id,
        "assignment_id": assignment_id,
        "dispatch_crossing_id": crossing["crossing_id"],
        "dispatch_source": source,
        "assigned_node_id": assignment.get("selected_node_id"),
        "assigned_capability": assignment.get("capability"),
        "signed_dispatch_crossing": crossing,
    }

    if current_body.get("location") == "local":
        task, raw_receipt = execute(
            str(assignment.get("capability") or ""),
            payload,
            requester_node_id=node_id(),
            constraints=constraints,
        )
        execution = {"task": task, "receipt": raw_receipt}
    else:
        url = current_body.get("url")
        if not isinstance(url, str) or not url:
            raise RuntimeError("SELECTED_REMOTE_BODY_HAS_NO_EXECUTION_ROUTE")
        execution = request_task(
            url,
            str(assignment.get("capability") or ""),
            payload,
            constraints=constraints,
            requester_node_id=node_id(),
        )

    _validate_execution_binding(execution, assignment)
    signed_receipt = _make_signed_receipt(
        crossing,
        assignment,
        execution,
        signer,
    )
    if not verify_receipt(
        signed_receipt,
        expected_public_key=signer.public_jwk(),
        expected_receiver_particular=signer.particular(),
    ):
        raise RuntimeError("SIGNED_DISPATCH_RECEIPT_INVALID")

    raw_receipt = execution["receipt"]
    result = {
        "schema": DISPATCH_RESULT_SCHEMA,
        "intent_id": intent_id,
        "assignment_id": assignment_id,
        "dispatch_crossing_id": crossing["crossing_id"],
        "selected_node_id": assignment.get("selected_node_id"),
        "capability": assignment.get("capability"),
        "dispatch_source": source,
        "status": (
            "EXECUTED"
            if raw_receipt.get("status") == "ok"
            else "EXECUTION_ERROR"
        ),
        "semantic_effect": "receiver-local-consequence",
        "payload": payload,
        "current_body": current_body,
        "current_capability": current_offer,
        "crossing": crossing,
        "execution": execution,
        "signed_receipt": signed_receipt,
        "completed_at": timestamp_now(),
        "laws": [
            "ASSIGNMENT != EXECUTION",
            "DISPATCH != SUCCESS",
            "EXECUTION != RECEIPT",
            "RECEIPT != TRUTH",
            "EXECUTOR CONSEQUENCE != DONOR AUTHORITY",
            "RETRY REQUIRES EXPLICIT RECOVERY AFTER UNKNOWN OUTCOME",
        ],
    }
    _write_json(state_path, {
        "schema": DISPATCH_STATE_SCHEMA,
        "state": "completed",
        "assignment_id": assignment_id,
        "intent_id": intent_id,
        "crossing_id": crossing["crossing_id"],
        "payload_sha256": _digest(payload),
        "dispatch_source": source,
        "prepared_at": prepared["prepared_at"],
        "completed_at": result["completed_at"],
        "crossing": crossing,
        "result": result,
    })
    return result


def status(intent_id: str) -> dict[str, Any]:
    entry, _admission, _intent, assignment = _load_assignment(intent_id)
    state = _read_json(_dispatch_state_path(entry))
    return {
        "schema": "ghot.carried-intent-dispatch-status/v0",
        "intent_id": intent_id,
        "assignment_id": assignment.get("assignment_id"),
        "status": (
            "EXECUTED"
            if isinstance(state, dict)
            and state.get("state") == "completed"
            and state.get("result", {}).get("status") == "EXECUTED"
            else "EXECUTION_ERROR"
            if isinstance(state, dict)
            and state.get("state") == "completed"
            else "DISPATCH_OUTCOME_UNKNOWN"
            if isinstance(state, dict)
            and state.get("state") == "prepared"
            else "ASSIGNED_NOT_EXECUTED"
        ),
        "dispatch_state": state,
        "laws": [
            "STATUS != AUTHORITY",
            "ASSIGNMENT != EXECUTION",
        ],
    }


def handle(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("CARRIED_INTENT_DISPATCH_REQUEST_REQUIRED")
    action = request.get("action")
    intent_id = str(request.get("intent_id") or "")
    if action == "dispatch":
        return dispatch(
            intent_id,
            dispatch_source=str(request.get("dispatch_source") or ""),
            timeout=float(request.get("timeout", 0.5)),
        )
    if action == "status":
        return status(intent_id)
    raise ValueError("UNKNOWN_CARRIED_INTENT_DISPATCH_ACTION")


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("CARRIED_INTENT_DISPATCH_REQUEST_REQUIRED")
    result = handle(json.loads(raw))
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(json.dumps({"error": f"{type(exc).__name__}: {exc}"}) + "\n")
        raise SystemExit(1)
