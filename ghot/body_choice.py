#!/usr/bin/env python3
"""GHoT Body Choice — explicit human/external assignment after discovery.

Discovery produces an offer set. Nothing is assigned automatically.
Assignment names one previously offered body, revalidates that body's current
liveness/capability, then executes exactly one bounded capability request.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from capability_composer import candidate_view, gather_candidates, offers_capability
from lan_node import request_task
from reference_node import ROOT, execute, node_id, now, persist

ASSIGNMENTS = ROOT / "body-choice-assignments"


def _encoded(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _offer_body(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": value["kind"],
        "version": value["version"],
        "capability": value["capability"],
        "observed_at": value["observed_at"],
        "requester_node_id": value["requester_node_id"],
        "candidates": value["candidates"],
        "laws": value["laws"],
    }


def compute_offer_id(value: dict[str, Any]) -> str:
    return f"ghot-body-offer-v0:{_sha256(_offer_body(value))}"


def verify_offer(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("INVALID_BODY_CHOICE_OFFER")
    if value.get("kind") != "ghot.body-choice.offer" or value.get("version") != "0":
        raise ValueError("INVALID_BODY_CHOICE_OFFER")
    if not isinstance(value.get("capability"), str) or not value["capability"]:
        raise ValueError("INVALID_BODY_CHOICE_CAPABILITY")
    candidates = value.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("INVALID_BODY_CHOICE_CANDIDATES")
    expected = compute_offer_id(value)
    if value.get("offer_id") != expected:
        raise ValueError("INVALID_BODY_CHOICE_OFFER_ID")
    return value


def discover_offer(
    capability: str,
    *,
    timeout: float = 0.5,
) -> dict[str, Any]:
    if not isinstance(capability, str) or not capability.strip():
        raise ValueError("capability is required")

    candidates, _field = gather_candidates(timeout)
    presented: list[dict[str, Any]] = []
    for candidate in candidates:
        body_record = candidate.get("body") or {}
        awake = candidate.get("field_state") == "awake"
        offered = offers_capability(body_record, capability)
        matching_offer = next(
            (
                offer for offer in body_record.get("offers", [])
                if offer.get("capability") == capability
            ),
            None,
        )
        available = bool(
            matching_offer
            and matching_offer.get("available") is True
            and awake
        )
        rejected: list[str] = []
        if not awake:
            rejected.append(
                f"liveness is {candidate.get('field_state') or 'unknown'}, not awake"
            )
        if not offered:
            rejected.append("required capability is not currently offered")
        elif matching_offer and matching_offer.get("available") is not True:
            rejected.append("required capability is currently withdrawn")

        presented.append({
            **candidate_view(candidate),
            "eligible": available,
            "matching_offer": matching_offer,
            "rejected": rejected,
        })

    presented.sort(key=lambda item: item["node_id"])
    offer: dict[str, Any] = {
        "kind": "ghot.body-choice.offer",
        "version": "0",
        "offer_id": "pending",
        "capability": capability,
        "observed_at": now(),
        "requester_node_id": node_id(),
        "candidates": presented,
        "laws": [
            "DISCOVERY != TRUST",
            "OFFER != ASSIGNMENT",
            "CAPABILITY != AUTHORITY",
            "BODY CHOICE IS EXPLICIT",
            "ASSIGNMENT REVALIDATES CURRENT STATE",
        ],
    }
    offer["offer_id"] = compute_offer_id(offer)
    persist("body-choice-offer", offer)
    return offer


def _current_candidate(
    selected_node_id: str,
    capability: str,
    *,
    timeout: float,
) -> dict[str, Any]:
    candidates, _field = gather_candidates(timeout)
    current = next(
        (candidate for candidate in candidates if candidate["node_id"] == selected_node_id),
        None,
    )
    if current is None:
        raise RuntimeError("selected body is no longer discoverable")
    if current.get("field_state") != "awake":
        raise RuntimeError("selected body is no longer awake")
    if not offers_capability(current.get("body") or {}, capability):
        raise RuntimeError("selected body no longer offers the required capability")
    return current


def _assignment_request(
    offer: dict[str, Any],
    selected_node_id: str,
    payload: Any,
    selection_source: str,
) -> dict[str, Any]:
    return {
        "offer_id": offer["offer_id"],
        "capability": offer["capability"],
        "requester_node_id": offer["requester_node_id"],
        "selected_node_id": selected_node_id,
        "payload_sha256": _sha256(payload),
        "selection_source": selection_source,
    }


def _assignment_id(request: dict[str, Any]) -> str:
    return f"assignment-v0:{_sha256(request)}"


def _assignment_path(assignment_id: str) -> Path:
    safe = assignment_id.replace(":", "-")
    return ASSIGNMENTS / f"{safe}.json"


def _write_assignment_state(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _existing_assignment_result(
    path: Path,
    assignment_id: str,
    request_sha256: str,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        value.get("kind") != "ghot.body-choice.assignment-state"
        or value.get("version") != "0"
        or value.get("assignment_id") != assignment_id
        or value.get("request_sha256") != request_sha256
    ):
        raise RuntimeError("INVALID_STORED_BODY_ASSIGNMENT")
    if value.get("state") == "completed":
        result = value.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("INVALID_STORED_BODY_ASSIGNMENT_RESULT")
        return result
    if value.get("state") == "prepared":
        raise RuntimeError(
            "ASSIGNMENT_OUTCOME_UNKNOWN: prepared assignment exists; "
            "refusing automatic re-execution"
        )
    raise RuntimeError("INVALID_STORED_BODY_ASSIGNMENT_STATE")


def assign(
    offer_value: Any,
    selected_node_id: str,
    payload: Any,
    *,
    timeout: float = 0.5,
    selection_source: str = "external-explicit",
) -> dict[str, Any]:
    offer = verify_offer(offer_value)
    if not isinstance(selected_node_id, str) or not selected_node_id:
        raise ValueError("selected_node_id is required")

    offered = next(
        (
            candidate for candidate in offer["candidates"]
            if candidate.get("node_id") == selected_node_id
        ),
        None,
    )
    if offered is None:
        raise ValueError("selected body was not present in the offer set")
    if offered.get("eligible") is not True:
        raise ValueError("selected body was not eligible in the offer set")

    request_identity = _assignment_request(
        offer,
        selected_node_id,
        payload,
        selection_source,
    )
    request_sha256 = _sha256(request_identity)
    assignment_id = _assignment_id(request_identity)
    state_path = _assignment_path(assignment_id)
    existing = _existing_assignment_result(
        state_path,
        assignment_id,
        request_sha256,
    )
    if existing is not None:
        return existing

    current = _current_candidate(
        selected_node_id,
        offer["capability"],
        timeout=timeout,
    )

    assignment = {
        "kind": "ghot.assignment",
        "version": "0",
        "assignment_id": assignment_id,
        "offer_id": offer["offer_id"],
        "selected_node_id": selected_node_id,
        "capability": offer["capability"],
        "selection_source": selection_source,
        "created_at": now(),
        "offered_body": offered,
        "revalidated_body": candidate_view(current),
        "laws": [
            "OFFER != ASSIGNMENT",
            "ASSIGNMENT != EXECUTION",
            "SELECTED BODY != AUTHORITY OWNER",
        ],
    }
    persist("assignment", assignment)
    _write_assignment_state(state_path, {
        "kind": "ghot.body-choice.assignment-state",
        "version": "0",
        "assignment_id": assignment_id,
        "request_sha256": request_sha256,
        "state": "prepared",
        "assignment": assignment,
    })

    constraints = {
        "assignment_id": assignment_id,
        "body_offer_id": offer["offer_id"],
        "selected_node_id": selected_node_id,
        "selection_source": selection_source,
    }

    if current["location"] == "local":
        task, receipt = execute(
            offer["capability"],
            payload,
            requester_node_id=offer["requester_node_id"],
            constraints=constraints,
        )
        execution = {"task": task, "receipt": receipt}
    else:
        url = current.get("url")
        if not url:
            raise RuntimeError("selected remote body has no execution route")
        execution = request_task(
            url,
            offer["capability"],
            payload,
            constraints=constraints,
            requester_node_id=offer["requester_node_id"],
        )

    receipt = execution.get("receipt") or {}
    result = {
        "kind": "ghot.body-choice.result",
        "version": "0",
        "assignment": assignment,
        "execution": execution,
        "status": receipt.get("status", "unknown"),
        "laws": [
            "DISCOVERY != TRUST",
            "OFFER != ASSIGNMENT",
            "ASSIGNMENT != EXECUTION",
            "EXECUTION != RECEIPT",
            "RECEIPT != TRUTH",
        ],
    }
    persist("body-choice-result", result)
    _write_assignment_state(state_path, {
        "kind": "ghot.body-choice.assignment-state",
        "version": "0",
        "assignment_id": assignment_id,
        "request_sha256": request_sha256,
        "state": "completed",
        "assignment": assignment,
        "result": result,
    })
    return result


def _stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("JSON request required on stdin")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


def main() -> int:
    try:
        request = _stdin_json()
        action = request.get("action")
        if action == "offer":
            result = discover_offer(
                str(request.get("capability") or ""),
                timeout=float(request.get("timeout", 0.5)),
            )
        elif action == "assign":
            result = assign(
                request.get("offer"),
                str(request.get("selected_node_id") or ""),
                request.get("payload"),
                timeout=float(request.get("timeout", 0.5)),
                selection_source=str(
                    request.get("selection_source") or "external-explicit"
                ),
            )
        else:
            raise ValueError("action must be offer or assign")
        sys.stdout.write(json.dumps(result))
        return 0
    except Exception as exc:
        sys.stderr.write(json.dumps({
            "error": f"{type(exc).__name__}: {exc}"
        }) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
